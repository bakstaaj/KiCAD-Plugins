import json
import os
import subprocess
import time
from urllib.error import URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import urlopen


def _frontend_is_ready(frontend_url):
    try:
        with urlopen(frontend_url, timeout=0.5) as response:
            if response.status != 200:
                return False
            page = response.read(65536)

        parsed_url = urlsplit(frontend_url)
        status_url = urlunsplit(
            (parsed_url.scheme, parsed_url.netloc, "/api/lightburn/status", "", "")
        )
        with urlopen(status_url, timeout=0.5) as response:
            if response.status != 200:
                return False
            status = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError):
        return False
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False

    return (
        b"Gerber2Png" in page
        and b"/vendor/pcb-stackup.min.js" in page
        and isinstance(status, dict)
        and isinstance(status.get("connected"), bool)
    )


def ensure_frontend_server(frontend_url, python_executable, app_root):
    """Start the local production frontend only if its page is not responding."""
    if _frontend_is_ready(frontend_url):
        return False

    dist_dir = os.path.join(app_root, "dist")
    server_script = os.path.join(app_root, "server.py")
    required_files = (
        os.path.join(dist_dir, "index.html"),
        os.path.join(dist_dir, "vendor", "pcb-stackup.min.js"),
        server_script,
    )
    missing_files = [path for path in required_files if not os.path.isfile(path)]
    if missing_files:
        raise RuntimeError(
            "Required files are missing from the local Gerber2PNG build: "
            + ", ".join(missing_files)
        )
    if not os.path.isfile(python_executable):
        raise RuntimeError(
            "Python for the local Gerber2PNG server was not found: "
            + python_executable
        )

    port = urlsplit(frontend_url).port
    if port is None:
        raise RuntimeError("The local Gerber2PNG URL does not specify a port.")

    process = subprocess.Popen(
        [
            python_executable,
            server_script,
        ],
        cwd=app_root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if _frontend_is_ready(frontend_url):
            return True
        if process.poll() is not None:
            break
        time.sleep(0.25)

    if process.poll() is None:
        process.terminate()
        process.wait(timeout=2)
    raise RuntimeError(
        "Could not start the local Gerber2PNG service at " + frontend_url
    )
