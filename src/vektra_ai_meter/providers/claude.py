from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..util import home, iter_jsonl, parse_iso


@dataclass
class ClaudeStats:
    sessions: int = 0
    active_sessions: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_create_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int = 0
    latest_model: str | None = None
    latest_title: str | None = None
    latest_cwd: str | None = None
    latest_at: datetime | None = None
    today_tokens: int = 0
    today_sessions: int = 0


def _usage_from_message(message: dict[str, Any]) -> dict[str, int]:
    usage = message.get("usage") or {}
    return {
        "input": int(usage.get("input_tokens") or 0),
        "output": int(usage.get("output_tokens") or 0),
        "cache_create": int((usage.get("cache_creation_input_tokens") or 0)),
        "cache_read": int((usage.get("cache_read_input_tokens") or 0)),
    }


def collect_claude_stats() -> ClaudeStats:
    root = home() / ".claude" / "projects"
    stats = ClaudeStats()
    if not root.exists():
        return stats

    today = datetime.now(timezone.utc).date()

    for session_path in root.rglob("*.jsonl"):
        session_input = 0
        session_output = 0
        session_cache_create = 0
        session_cache_read = 0
        session_model: str | None = None
        session_title: str | None = None
        session_cwd: str | None = None
        session_at: datetime | None = None
        has_usage = False

        for row in iter_jsonl(session_path):
            row_type = row.get("type")
            if row_type == "ai-title":
                session_title = row.get("aiTitle") or session_title
            if row_type == "user":
                session_cwd = row.get("cwd") or session_cwd
                session_at = parse_iso(row.get("timestamp")) or session_at
            if row_type == "assistant":
                message = row.get("message") or {}
                usage = _usage_from_message(message)
                if any(usage.values()):
                    has_usage = True
                    session_input += usage["input"]
                    session_output += usage["output"]
                    session_cache_create += usage["cache_create"]
                    session_cache_read += usage["cache_read"]
                session_model = message.get("model") or session_model
                session_cwd = row.get("cwd") or session_cwd
                session_at = parse_iso(row.get("timestamp")) or session_at

        if not has_usage and session_title is None:
            continue

        session_total = session_input + session_output
        stats.sessions += 1
        stats.input_tokens += session_input
        stats.output_tokens += session_output
        stats.cache_create_tokens += session_cache_create
        stats.cache_read_tokens += session_cache_read
        stats.total_tokens += session_total

        if session_at and (datetime.now(timezone.utc) - session_at).total_seconds() < 3600:
            stats.active_sessions += 1

        if session_at and session_at.date() == today:
            stats.today_sessions += 1
            stats.today_tokens += session_total

        if stats.latest_at is None or (session_at and session_at >= stats.latest_at):
            stats.latest_at = session_at
            stats.latest_model = session_model
            stats.latest_title = session_title
            stats.latest_cwd = session_cwd

    return stats