import configparser
import os
import platform
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional

if platform.system() == "Darwin":
    DEFAULT_CONFIG = """[paths]
        git = /opt/homebrew/bin/git
        git_gui = /opt/homebrew/bin/git gui"""
else:
    DEFAULT_CONFIG = """[paths]
        git = git
        git_gui = git gui"""

config = configparser.ConfigParser()
config.read_string(DEFAULT_CONFIG)
config.read(os.path.dirname(__file__) + "/config.ini")

git: str = config["paths"]["git"]
git_gui: str = config["paths"]["git_gui"]


def _git_path_to_platform_path(path: str) -> Path:
    if sys.platform == "win32" and path.startswith("/"):
        cygpath = Path(git).parent / "cygpath.exe"
        if cygpath.is_file():
            try:
                converted = subprocess.run(
                    [str(cygpath), "-w", path],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5,
                ).stdout.strip()
                if converted:
                    path = converted
            except (OSError, subprocess.SubprocessError):
                pass

        if path.startswith("/"):
            if len(path) >= 3 and path[1].isalpha() and path[2] == "/":
                path = f"{path[1]}:{path[2:]}"
            else:
                msys_root = Path(git).parent.parent.parent
                path = str(msys_root.joinpath(*path.lstrip("/").split("/")))
    return Path(path)


def __run(command: str, cwd: Path) -> str:
    args = f"{git} {command}"
    if sys.platform != "win32":
        args = shlex.split(args)
    process = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    process.wait()
    output = ""
    if process.stdout:
        output = process.stdout.read()
    if process.returncode == 0:
        return output
    error = f"Error: Failed to '{git} {command}', received: {output}"
    raise RuntimeError(error)


def version() -> str:
    return __run("version", Path("."))


def init(path: Path) -> str:
    return __run("init", path)


def toplevel(path: Path) -> Optional[Path]:
    if path.exists():
        try:
            result = __run("rev-parse --show-toplevel", path).strip()
            if result:
                return _git_path_to_platform_path(result)
        except RuntimeError:
            pass
    return None


def guitool(repo_dir: Path) -> subprocess.Popen:
    args = git_gui
    if sys.platform != "win32":
        args = shlex.split(args)
    env = os.environ.copy()
    # Git for Windows/MSYS2 may report its git-dir as a POSIX path (for
    # example /home/.../.git). git-gui's Tcl file operations need native
    # Windows paths, so pass the resolved repository locations explicitly.
    git_dir = __run("rev-parse --absolute-git-dir", repo_dir).strip()
    env["GIT_DIR"] = str(_git_path_to_platform_path(git_dir))
    env["GIT_WORK_TREE"] = str(repo_dir.resolve())
    git_path = Path(git)
    cygpath = git_path.parent / "cygpath.exe"
    if sys.platform == "win32" and cygpath.is_file():
        msys_root = git_path.parent.parent.parent
        msys_bin_dirs = (
            msys_root / "ucrt64" / "bin",
            msys_root / "usr" / "bin",
        )
        extra_paths = [str(path) for path in msys_bin_dirs if path.is_dir()]
        env["PATH"] = os.pathsep.join(extra_paths + [env.get("PATH", "")])
    return subprocess.Popen(
        args,
        cwd=repo_dir,
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


__all__ = ["version", "init", "toplevel", "guitool"]
