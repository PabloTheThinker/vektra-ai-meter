from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def home() -> Path:
    return Path.home()


def data_dir() -> Path:
    path = home() / ".local" / "share" / "vektra-ai-meter"
    path.mkdir(parents=True, exist_ok=True)
    return path


def snapshot_path() -> Path:
    return data_dir() / "snapshot.json"


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def unix_ts(value: int | float | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    yield payload
    except OSError:
        return


def fmt_tokens(value: int | float | None) -> str:
    if value is None:
        return "—"
    number = int(value)
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if number >= 1_000:
        return f"{number / 1_000:.1f}K"
    return str(number)


def fmt_percent(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.0f}%"