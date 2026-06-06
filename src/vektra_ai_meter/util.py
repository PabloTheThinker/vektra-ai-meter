from __future__ import annotations

import hashlib
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


def iter_jsonl_tail(path: Path, max_bytes: int = 48_000) -> Iterator[dict[str, Any]]:
    """Read recent JSONL lines from the end of a file (cheap quota/session peek)."""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(size - max_bytes)
                handle.readline()
            chunk = handle.read().decode("utf-8", errors="ignore")
    except OSError:
        return

    for line in chunk.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            yield payload


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


def snapshot_display_digest(snapshot: dict[str, Any]) -> str:
    """Stable digest of panel-visible fields (excludes generated_at)."""
    payload = {
        "providers": [
            {
                "id": provider.get("id"),
                "sessions": provider.get("sessions"),
                "active_sessions": provider.get("active_sessions"),
                "model": provider.get("model"),
                "subtitle": provider.get("subtitle"),
                "plan_type": provider.get("plan_type"),
                "limits": provider.get("limits"),
            }
            for provider in snapshot.get("providers") or []
        ],
        "summary": {
            key: (snapshot.get("summary") or {}).get(key)
            for key in ("peak_percent", "peak_label", "highlights")
        },
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]