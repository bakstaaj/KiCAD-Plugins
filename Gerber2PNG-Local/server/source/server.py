"""Serve the local Gerber2PNG UI and bridge its LightBurn REST API calls."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


HOST = "127.0.0.1"
PORT = 4172
LIGHTBURN_URL = "http://localhost:19520"
DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
ALLOWED_ORIGINS = {
    "top-left", "top-center", "top-right",
    "middle-left", "center", "middle-right",
    "bottom-left", "bottom-center", "bottom-right",
}
lightburn_secret: str | None = None


def json_bytes(value: dict) -> bytes:
    return json.dumps(value).encode("utf-8")


def find_lightburn_executable() -> str | None:
    """Find the newest installed LightBurn executable on Windows."""
    candidates: list[tuple[tuple[int, ...], str]] = []
    configured = os.environ.get("LIGHTBURN_EXE")
    if configured and os.path.isfile(configured):
        return configured
    if sys.platform == "win32":
        try:
            import winreg

            uninstall_roots = (
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            )
            for hive, root_path in uninstall_roots:
                try:
                    root = winreg.OpenKey(hive, root_path)
                except OSError:
                    continue
                with root:
                    for index in range(winreg.QueryInfoKey(root)[0]):
                        try:
                            subkey = winreg.OpenKey(root, winreg.EnumKey(root, index))
                            with subkey:
                                name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                if "lightburn" not in name.lower():
                                    continue
                                icon = winreg.QueryValueEx(subkey, "DisplayIcon")[0].strip('"')
                                install_dir = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                path = icon if os.path.isfile(icon) else os.path.join(install_dir, "LightBurn.exe")
                                if not os.path.isfile(path):
                                    continue
                                version_match = re.search(r"(\d+(?:\.\d+)+)", name)
                                version = tuple(int(part) for part in version_match.group(1).split(".")) if version_match else (0,)
                                candidates.append((version, path))
                        except OSError:
                            continue
        except ImportError:
            pass
    for path in (
        r"C:\Program Files\LightBurn_PreRelease\LightBurn.exe",
        r"C:\Program Files\LightBurn\LightBurn.exe",
        r"C:\Program Files (x86)\LightBurn\LightBurn.exe",
    ):
        if os.path.isfile(path):
            candidates.append(((0,), path))
    if candidates:
        return max(candidates, key=lambda item: item[0])[1]
    return None


def launch_lightburn() -> str | None:
    executable = find_lightburn_executable()
    if not executable:
        return None
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([executable], close_fds=True, creationflags=flags)
    return executable


def pair_with_lightburn() -> dict:
    payload = json_bytes({"application_name": "Gerber2PNG", "capabilities": ["upload"]})
    request = Request(
        f"{LIGHTBURN_URL}/api/connect",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=40) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as error:
        # The LightBurn API only listens while the desktop app is running. Start
        # it on the first refused connection, then wait for its API to come up.
        try:
            executable = launch_lightburn()
        except OSError as launch_error:
            raise RuntimeError(f"Could not start LightBurn: {launch_error}") from launch_error
        if not executable:
            raise RuntimeError("Could not find LightBurn. Install it or set the LIGHTBURN_EXE environment variable, then try again.") from error
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            time.sleep(1)
            try:
                with urlopen(request, timeout=40) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError:
                raise
            except (URLError, TimeoutError):
                continue
        raise RuntimeError("LightBurn did not start its API within 60 seconds. Open LightBurn and try again.") from error


class LocalHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def _send_json(self, status: int, value: dict) -> None:
        body = json_bytes(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/api/lightburn/status":
            self._send_json(200, {"connected": lightburn_secret is not None})
            return
        super().do_GET()

    def do_POST(self) -> None:
        global lightburn_secret

        if self.path == "/api/lightburn/connect":
            try:
                result = pair_with_lightburn()
                secret = result.get("secret")
                if result.get("status") != "ok" or not isinstance(secret, str) or not secret:
                    self._send_json(502, {"error": "LightBurn did not return an approved pairing secret."})
                    return
                lightburn_secret = secret
                self._send_json(200, {"connected": True})
            except HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")
                self._send_json(502, {"error": detail or f"LightBurn pairing failed ({error.code})."})
            except (URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as error:
                self._send_json(502, {"error": f"Could not pair with LightBurn: {error}"})
            return

        if self.path == "/api/lightburn/upload":
            if lightburn_secret is None:
                self._send_json(401, {"error": "Pair with LightBurn before importing a PNG."})
                return

            try:
                x = float(self.headers["X-Position-X"])
                y = float(self.headers["X-Position-Y"])
                origin = self.headers["X-Origin"]
                filename = self.headers["X-Filename"]
                if not (abs(x) < 1e9 and abs(y) < 1e9):
                    raise ValueError("Position must be a finite millimeter value.")
                if origin not in ALLOWED_ORIGINS:
                    raise ValueError("Choose a valid image anchor point.")
                if not filename or len(filename) > 180:
                    raise ValueError("The PNG filename is invalid.")
            except (KeyError, ValueError) as error:
                self._send_json(400, {"error": str(error) or "Position and filename are required."})
                return

            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            minute = str(int(time.time()) // 60).encode("ascii")
            token = hmac.new(lightburn_secret.encode("utf-8"), minute, hashlib.sha256).hexdigest()
            safe_filename = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
            request = Request(
                f"{LIGHTBURN_URL}/api/file/upload",
                data=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/octet-stream",
                    "X-Filename": safe_filename,
                    "X-Position-X": str(x),
                    "X-Position-Y": str(y),
                    "X-Origin": origin,
                },
                method="POST",
            )
            try:
                with urlopen(request, timeout=30) as response:
                    result = json.loads(response.read().decode("utf-8"))
                self._send_json(200, {"accepted": True, "filename": safe_filename, **result})
            except HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")
                if error.code == 401:
                    lightburn_secret = None
                    self._send_json(401, {"error": "LightBurn pairing expired. Pair again and retry."})
                else:
                    self._send_json(error.code, {"error": detail or f"LightBurn import failed ({error.code})."})
            except (URLError, TimeoutError, json.JSONDecodeError) as error:
                self._send_json(502, {"error": f"Could not send the PNG to LightBurn: {error}"})
            return

        self._send_json(404, {"error": "Unknown local API endpoint."})


if __name__ == "__main__":
    if not os.path.isdir(DIST_DIR):
        raise SystemExit(f"Build the app first; dist folder not found: {DIST_DIR}")
    server = ThreadingHTTPServer((HOST, PORT), LocalHandler)
    print(f"Gerber2PNG local server: http://{HOST}:{PORT}")
    print("LightBurn API bridge: http://localhost:19520")
    server.serve_forever()
