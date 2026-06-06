from __future__ import annotations

import importlib.metadata
import subprocess
import sys
from pathlib import Path
from shutil import which

from . import __version__
from .paths import (
    app_dir,
    default_branch,
    default_repo_url,
    venv_dir,
    venv_pip,
)


class UpdateError(Exception):
    pass


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except FileNotFoundError as exc:
        raise UpdateError(f"Command not found: {cmd[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise UpdateError(f"Command failed: {' '.join(cmd)}") from exc


def _installed_version() -> str:
    try:
        return importlib.metadata.version("vektra-ai-meter")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _git_pull(app: Path, branch: str) -> None:
    if not (app / ".git").is_dir():
        return
    if not which("git"):
        raise UpdateError("git is required to update from a cloned install.")
    _run(["git", "-C", str(app), "fetch", "origin", branch])
    _run(["git", "-C", str(app), "checkout", branch])
    _run(["git", "-C", str(app), "pull", "--ff-only", "origin", branch])


def _pip_upgrade(app: Path, pip: Path) -> None:
    _run([str(pip), "install", "-q", "--upgrade", "pip"])
    if (app / "pyproject.toml").is_file():
        _run([str(pip), "install", "-q", "--upgrade", str(app)])
        return
    repo = default_repo_url()
    branch = default_branch()
    _run([str(pip), "install", "-q", "--upgrade", f"git+{repo}@{branch}"])


def _ensure_integration() -> None:
    from .integrate import build_layer_shell
    from .ui.wayland import is_wayland

    if not is_wayland():
        return
    ok, message = build_layer_shell()
    if ok and "Already integrated" not in message:
        print(message)


def _restart_topbar() -> None:
    from .autostart import reboot_panel

    reboot_panel()


def run_update(*, restart: bool = True) -> int:
    pip = venv_pip()
    app = app_dir()

    if not venv_dir().is_dir() or not pip.is_file():
        print(
            "Vektra AI Meter venv not found. Install first:\n"
            "  curl -fsSL https://vektraindustries.com/ai-tracker/install | bash",
            file=sys.stderr,
        )
        return 1

    before = _installed_version()
    print(f"Current version: {before}")

    try:
        branch = default_branch()
        if (app / ".git").is_dir():
            print(f"Pulling latest from {default_repo_url()} ({branch})...")
            _git_pull(app, branch)
        else:
            print("No git checkout found — upgrading package from GitHub...")
        print("Upgrading Python package...")
        _pip_upgrade(app, pip)
        print("Ensuring integrated top-bar dropdown...")
        _ensure_integration()
    except UpdateError as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        return 1

    after = _installed_version()
    print(f"Updated: {before} → {after} (package declares {__version__})")

    if restart:
        print("Restarting panel indicator...")
        _restart_topbar()
        print("Done. Check your top-bar status area.")

    return 0