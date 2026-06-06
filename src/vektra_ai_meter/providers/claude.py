from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..util import home, iter_jsonl, parse_iso, unix_ts

MAX_CLAUDE_SCAN = 64


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


def _live_session_records() -> list[dict[str, Any]]:
    sessions_dir = home() / ".claude" / "sessions"
    live: list[dict[str, Any]] = []
    if not sessions_dir.exists():
        return live

    for path in sessions_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue

        pid = data.get("pid")
        if pid is not None:
            try:
                os.kill(int(pid), 0)
            except (OSError, ValueError, ProcessLookupError):
                continue
        live.append(data)
    return live


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
    live_sessions = _live_session_records()
    seen_session_ids: set[str] = set()

    today = datetime.now(timezone.utc).date()

    if not root.exists():
        stats.active_sessions = len(live_sessions)
        stats.sessions = len(live_sessions)
        for live in live_sessions:
            session_id = str(live.get("sessionId") or "")
            if session_id:
                seen_session_ids.add(session_id)
            updated_at = unix_ts(live.get("updatedAt"))
            if updated_at and (stats.latest_at is None or updated_at >= stats.latest_at):
                stats.latest_at = updated_at
                stats.latest_cwd = live.get("cwd") or stats.latest_cwd
        return stats

    paths = sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for session_path in paths[:MAX_CLAUDE_SCAN]:
        seen_session_ids.add(session_path.stem)
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

        if session_at and session_at.date() == today:
            stats.today_sessions += 1
            stats.today_tokens += session_total

        if stats.latest_at is None or (session_at and session_at >= stats.latest_at):
            stats.latest_at = session_at
            stats.latest_model = session_model
            stats.latest_title = session_title
            stats.latest_cwd = session_cwd

    for live in live_sessions:
        session_id = str(live.get("sessionId") or "")
        if session_id and session_id not in seen_session_ids:
            stats.sessions += 1
            seen_session_ids.add(session_id)

        updated_at = unix_ts(live.get("updatedAt"))
        if updated_at and (stats.latest_at is None or updated_at >= stats.latest_at):
            stats.latest_at = updated_at
            stats.latest_cwd = live.get("cwd") or stats.latest_cwd

    stats.active_sessions = len(live_sessions)
    return stats