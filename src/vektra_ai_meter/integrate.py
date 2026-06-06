from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .layershell import find_layer_shell_lib, layer_shell_available
from .paths import venv_pip
from .util import data_dir


def _local_prefix() -> Path:
    return Path.home() / ".local"


def _layer_src() -> Path:
    return data_dir() / "gtk4-layer-shell-src"


def _layer_repo() -> str:
    return os.environ.get(
        "VEKTRA_LAYER_SHELL_REPO",
        "https://github.com/wmww/gtk4-layer-shell.git",
    )


def integration_status() -> dict:
    lib = find_layer_shell_lib()
    return {
        "wayland": _is_wayland(),
        "layer_shell_lib": str(lib or ""),
        "layer_shell_ready": layer_shell_available(),
        "integrated_popup": _is_wayland() and layer_shell_available(),
        "build_deps": _build_deps_status(),
        "setup_command": INTEGRATE_DEPS_CMD,
    }


INTEGRATE_DEPS_CMD = (
    "sudo apt install -y pkg-config libgtk-4-dev libwayland-dev wayland-protocols "
    "gobject-introspection libgirepository-2.0-dev python3-gi gir1.2-gtk-4.0"
)


def _is_wayland() -> bool:
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    return session == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))


def _build_deps_status() -> dict[str, bool]:
    return {
        "pkg_config": shutil.which("pkg-config") is not None,
        "gtk4_dev": _pkg_config_exists("gtk4"),
        "python_gi": _python_gi_ok(),
        "meson": shutil.which("meson") is not None,
        "ninja": shutil.which("ninja") is not None,
    }


def _pkg_config_exists(name: str) -> bool:
    if shutil.which("pkg-config") is None:
        return False
    result = subprocess.run(
        ["pkg-config", "--exists", name],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _python_gi_ok() -> bool:
    from .gtk_launch import gtk_python_available

    return gtk_python_available()


def build_layer_shell(*, force: bool = False) -> tuple[bool, str]:
    """Build gtk4-layer-shell into ~/.local when dev dependencies are present."""
    local = _local_prefix()
    layer_lib = local / "lib" / "libgtk4-layer-shell.so.0"
    if not force and layer_lib.is_file() and layer_shell_available():
        return True, f"Already integrated ({layer_lib})"

    deps = _build_deps_status()
    if not deps["pkg_config"] or not deps["gtk4_dev"] or not deps["python_gi"]:
        return False, (
            "Missing system dependencies for the integrated dropdown.\n"
            "Re-run the one-line installer:\n"
            "  curl -fsSL https://vektraindustries.com/ai-tracker/install | bash"
        )

    pip = venv_pip() if venv_pip().is_file() else Path(sys.executable).parent / "pip"
    subprocess.run([str(pip), "install", "-q", "meson", "ninja"], check=False)

    src = _layer_src()
    repo = _layer_repo()
    src.parent.mkdir(parents=True, exist_ok=True)
    local_lib = local / "lib"
    girepo = local_lib / "girepository-1.0"
    local_lib.mkdir(parents=True, exist_ok=True)
    girepo.mkdir(parents=True, exist_ok=True)

    if not (src / ".git").is_dir():
        subprocess.run(["git", "clone", "--depth", "1", repo, str(src)], check=True)
    else:
        subprocess.run(
            ["git", "-C", str(src), "pull", "--ff-only"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    build_dir = src / "build"
    env = os.environ.copy()
    venv_bin = pip.parent
    env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"

    subprocess.run(
        [
            "meson",
            "setup",
            f"--prefix={local}",
            "--libdir=lib",
            "-Dexamples=false",
            "-Ddocs=false",
            str(build_dir),
            str(src),
        ],
        check=True,
        env=env,
    )
    subprocess.run(["ninja", "-C", str(build_dir)], check=True, env=env)
    subprocess.run(["ninja", "-C", str(build_dir), "install"], check=True, env=env)

    if not layer_shell_available():
        return False, (
            "gtk4-layer-shell was built but GObject introspection failed to load.\n"
            f"Ensure {girepo} contains Gtk4LayerShell-1.0.typelib and re-login."
        )
    return True, f"Integrated panel ready ({find_layer_shell_lib()})"


def run_integrate(*, build: bool = False, force: bool = False) -> int:
    status = integration_status()
    if status["integrated_popup"] and not build:
        print("Integrated top-bar dropdown is ready.")
        print(f"  layer_shell_lib: {status['layer_shell_lib']}")
        print("Run `ai-meter reboot` to switch from the Qt fallback panel.")
        return 0

    if not status["wayland"]:
        print(
            "Integrated dropdown is for Wayland desktops (COSMIC, Sway, KDE).\n"
            "On X11 the Qt panel fallback is used automatically.",
            file=sys.stderr,
        )
        return 1

    if not build:
        missing = [name for name, ok in status["build_deps"].items() if not ok]
        print("Integrated top-bar dropdown is not set up yet.")
        if missing:
            print(f"  Missing: {', '.join(missing)}")
        print(
            "\nRe-run the one-line installer:\n"
            "  curl -fsSL https://vektraindustries.com/ai-tracker/install | bash"
        )
        return 1

    ok, message = build_layer_shell(force=force)
    print(message)
    if not ok:
        return 1

    print("\nNext: ai-meter reboot")
    return 0