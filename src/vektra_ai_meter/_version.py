from __future__ import annotations

import importlib.metadata
import re
from pathlib import Path


def _pyproject_version() -> str:
    for parent in Path(__file__).resolve().parents:
        pyproject = parent / "pyproject.toml"
        if not pyproject.is_file():
            continue
        match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M)
        if match:
            return match.group(1)
    return "0.0.0"


def resolve_version() -> str:
    try:
        return importlib.metadata.version("vektra-ai-meter")
    except importlib.metadata.PackageNotFoundError:
        return _pyproject_version()