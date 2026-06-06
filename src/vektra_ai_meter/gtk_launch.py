from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

POPUP_SERVER_BOOT = (
    "from vektra_ai_meter.popup_server import run_popup_server; "
    "raise SystemExit(run_popup_server())"
)


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


def popup_server_env() -> dict[str, str]:
    """Environment for the GTK popup — LD_PRELOAD must be set before Python starts."""
    from .layershell import find_layer_shell_lib

    env = gtk_env()
    layer_lib = find_layer_shell_lib()
    if layer_lib is not None:
        existing = env.get("LD_PRELOAD", "")
        env["LD_PRELOAD"] = f"{layer_lib}:{existing}" if existing else str(layer_lib)
        env["VEKTRA_LAYER_SHELL_PRELOADED"] = "1"
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
    """Launch argv for the GTK integrated popup process."""
    from .paths import venv_ai_meter

    executable = gtk_python_executable()
    if executable is not None:
        return [str(executable), "-c", POPUP_SERVER_BOOT]

    user = Path.home() / ".local" / "bin" / "ai-meter"
    if user.is_file():
        return [str(user), "popup-server"]
    return [str(venv_ai_meter()), "popup-server"]