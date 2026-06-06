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


def _git_sync(app: Path, branch: str) -> None:
    if not (app / ".git").is_dir():
        return
    if not which("git"):
        raise UpdateError("git is required to update from a cloned install.")
    _run(["git", "-C", str(app), "fetch", "origin", branch])
    _run(["git", "-C", str(app), "checkout", "-f", branch])
    _run(["git", "-C", str(app), "reset", "--hard", f"origin/{branch}"])
    _run(["git", "-C", str(app), "clean", "-fd"])


def _pip_upgrade(app: Path, pip: Path) -> None:
    _run([str(pip), "install", "-q", "--upgrade", "pip"])
    if (app / "pyproject.toml").is_file():
        _run([str(pip), "install", "-q", "--upgrade", str(app)])
        return
    repo = default_repo_url()
    branch = default_branch()
    _run([str(pip), "install", "-q", "--upgrade", f"git+{repo}@{branch}"])


def _launcher() -> Path:
    from .autostart import ai_meter_bin

    return ai_meter_bin()


def _ensure_integration() -> None:
    from .ui.wayland import is_wayland

    if not is_wayland():
        return

    launcher = _launcher()
    if not launcher.is_file():
        return

    # Run via the freshly installed CLI so post-pip integrate logic is current.
    result = subprocess.run(
        [str(launcher), "integrate", "--build"],
        check=False,
        text=True,
    )
    if result.returncode != 0:
        print(
            "Warning: integrated dropdown build skipped — Qt panel fallback remains active.",
            file=sys.stderr,
        )


def _restart_topbar() -> bool:
    """Restart using the newly installed ai-meter (not in-process stale modules)."""
    launcher = _launcher()
    if not launcher.is_file():
        print(
            f"Update installed but launcher not found at {launcher}.",
            file=sys.stderr,
        )
        return False

    result = subprocess.run([str(launcher), "reboot"], check=False)
    return result.returncode == 0


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
            _git_sync(app, branch)
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
        if _restart_topbar():
            return 0
        print("Update installed but auto-restart failed. Run: ai-meter reboot", file=sys.stderr)
        return 1

    return 0