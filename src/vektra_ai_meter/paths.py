from __future__ import annotations

import os
import sys
from pathlib import Path


def install_root() -> Path:
    return Path(
        os.environ.get(
            "VEKTRA_AI_METER_INSTALL_ROOT",
            Path.home() / ".local" / "share" / "vektra-ai-meter",
        )
    )


def app_dir() -> Path:
    return install_root() / "app"


def venv_dir() -> Path:
    return install_root() / "venv"


def venv_python() -> Path:
    return venv_dir() / "bin" / "python"


def venv_pip() -> Path:
    return venv_dir() / "bin" / "pip"


def venv_ai_meter() -> Path:
    return venv_dir() / "bin" / "ai-meter"


def running_in_venv() -> bool:
    prefix = Path(sys.prefix).resolve()
    return prefix == venv_dir().resolve()


def default_repo_url() -> str:
    return os.environ.get(
        "VEKTRA_AI_METER_REPO_URL",
        "https://github.com/PabloTheThinker/vektra-ai-meter.git",
    )


def default_branch() -> str:
    return os.environ.get("VEKTRA_AI_METER_BRANCH", "main")