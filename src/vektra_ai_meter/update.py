from __future__ import annotations

import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path
from shutil import which

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


def _restart_topbar() -> bool:
    launcher = _launcher()
    if not launcher.is_file():
        print(
            f"Update installed but launcher not found at {launcher}.",
            file=sys.stderr,
        )
        return False

    result = subprocess.run([str(launcher), "reboot"], check=False)
    return result.returncode == 0


def _run_install_script(*, restart: bool) -> int:
    install_sh = app_dir() / "install.sh"
    if not install_sh.is_file():
        return -1

    env = os.environ.copy()
    env["VEKTRA_AI_METER_UPDATE"] = "1"
    env["VEKTRA_AI_METER_LAUNCH"] = "1" if restart else "0"
    result = subprocess.run(["bash", str(install_sh)], env=env, check=False)
    return result.returncode


def _run_python_update(*, restart: bool) -> int:
    pip = venv_pip()
    app = app_dir()
    before = _installed_version()

    try:
        branch = default_branch()
        if (app / ".git").is_dir():
            print(f"→ Pulling latest from {default_repo_url()} ({branch})...")
            _git_sync(app, branch)
        print("→ Upgrading Python package...")
        _pip_upgrade(app, pip)
    except UpdateError as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        return 1

    after = _installed_version()
    if before == after:
        print(f"✓ Already up to date — vektra-ai-meter {after}")
    else:
        print(f"✓ Updated vektra-ai-meter {before} → {after}")

    if restart:
        print("→ Restarting panel indicator...")
        if _restart_topbar():
            print("✓ Panel indicator running")
            return 0
        print("Update installed but auto-restart failed. Run: ai-meter reboot", file=sys.stderr)
        return 1

    return 0


def run_update(*, restart: bool = True) -> int:
    if not venv_dir().is_dir() or not venv_pip().is_file():
        print(
            "Vektra AI Meter is not installed. Run:\n"
            "  curl -fsSL https://vektraindustries.com/ai-tracker/install | bash",
            file=sys.stderr,
        )
        return 1

    code = _run_install_script(restart=restart)
    if code >= 0:
        return code

    print("")
    print("Vektra AI Meter — updating")
    print("")
    return _run_python_update(restart=restart)