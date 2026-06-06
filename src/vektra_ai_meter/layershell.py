from __future__ import annotations

import os
import sys
from pathlib import Path


def _candidate_libs() -> list[Path]:
    explicit = os.environ.get("VEKTRA_LAYER_SHELL_LIB", "").strip()
    home_local = Path.home() / ".local"
    arch = os.uname().machine
    arch_dirs = {
        "x86_64": "x86_64-linux-gnu",
        "aarch64": "aarch64-linux-gnu",
    }
    multiarch = arch_dirs.get(arch, arch)

    paths: list[Path] = []
    if explicit:
        paths.append(Path(explicit))
    paths.extend(
        [
            home_local / "lib" / "libgtk4-layer-shell.so",
            home_local / "lib" / "libgtk4-layer-shell.so.0",
            Path(f"/usr/lib/{multiarch}/libgtk4-layer-shell.so.0"),
            Path(f"/usr/lib/{multiarch}/libgtk4-layer-shell.so"),
            Path("/usr/lib/libgtk4-layer-shell.so.0"),
            Path("/usr/lib64/libgtk4-layer-shell.so.0"),
        ]
    )
    return paths


def find_layer_shell_lib() -> Path | None:
    for path in _candidate_libs():
        if path.is_file():
            return path
    return None


def ensure_local_paths() -> None:
    local = Path.home() / ".local"
    lib = local / "lib"
    girepo = lib / "girepository-1.0"
    if lib.is_dir():
        current = os.environ.get("LD_LIBRARY_PATH", "")
        if str(lib) not in current.split(":"):
            os.environ["LD_LIBRARY_PATH"] = f"{lib}:{current}" if current else str(lib)
    if girepo.is_dir():
        current = os.environ.get("GI_TYPELIB_PATH", "")
        if str(girepo) not in current.split(":"):
            os.environ["GI_TYPELIB_PATH"] = f"{girepo}:{current}" if current else str(girepo)


def preload_layer_shell() -> None:
    ensure_local_paths()
    """Re-exec with LD_PRELOAD so gtk4-layer-shell registers before libwayland-client."""
    if os.environ.get("VEKTRA_LAYER_SHELL_PRELOADED") == "1":
        return
    lib = find_layer_shell_lib()
    if lib is None:
        return
    env = os.environ.copy()
    existing = env.get("LD_PRELOAD", "")
    env["LD_PRELOAD"] = f"{lib}:{existing}" if existing else str(lib)
    env["VEKTRA_LAYER_SHELL_PRELOADED"] = "1"
    os.execve(sys.executable, [sys.executable, *sys.argv], env)


def layer_shell_available() -> bool:
    from .gtk_launch import gtk_python_available

    if find_layer_shell_lib() is None or not gtk_python_available():
        return False
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Gtk4LayerShell", "1.0")
    except (ImportError, ValueError):
        return False
    return True