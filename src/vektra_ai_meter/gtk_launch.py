from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _system_python() -> Path | None:
    for candidate in ("/usr/bin/python3", "/bin/python3"):
        path = Path(candidate)
        if path.is_file():
            return path
    found = shutil.which("python3")
    return Path(found) if found else None


def _python_has_gi(executable: Path | str) -> bool:
    result = subprocess.run(
        [
            str(executable),
            "-c",
            "import gi; gi.require_version('Gtk', '4.0')",
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def package_site_paths() -> list[str]:
    spec = importlib.util.find_spec("vektra_ai_meter")
    if spec is None or not spec.submodule_search_locations:
        return []
    root = Path(next(iter(spec.submodule_search_locations))).parent
    return [str(root)]


def gtk_env() -> dict[str, str]:
    local = Path.home() / ".local"
    env = os.environ.copy()
    lib = local / "lib"
    girepo = lib / "girepository-1.0"
    if lib.is_dir():
        env["LD_LIBRARY_PATH"] = (
            f"{lib}:{env['LD_LIBRARY_PATH']}" if env.get("LD_LIBRARY_PATH") else str(lib)
        )
    if girepo.is_dir():
        env["GI_TYPELIB_PATH"] = (
            f"{girepo}:{env['GI_TYPELIB_PATH']}"
            if env.get("GI_TYPELIB_PATH")
            else str(girepo)
        )
    for site in package_site_paths():
        env["PYTHONPATH"] = (
            f"{site}:{env['PYTHONPATH']}" if env.get("PYTHONPATH") else site
        )
    return env


def gtk_python_executable() -> Path | str | None:
    if _python_has_gi(sys.executable):
        return sys.executable
    system = _system_python()
    if system is not None and _python_has_gi(system):
        return system
    return None


def gtk_python_available() -> bool:
    return gtk_python_executable() is not None


def popup_server_argv() -> list[str]:
    from .paths import venv_ai_meter

    if _python_has_gi(sys.executable):
        user = Path.home() / ".local" / "bin" / "ai-meter"
        if user.is_file():
            return [str(user), "popup-server"]
        if venv_ai_meter().is_file():
            return [str(venv_ai_meter()), "popup-server"]

    executable = gtk_python_executable()
    if executable is not None:
        return [str(executable), "-m", "vektra_ai_meter.popup_server"]

    user = Path.home() / ".local" / "bin" / "ai-meter"
    if user.is_file():
        return [str(user), "popup-server"]
    return [str(venv_ai_meter()), "popup-server"]