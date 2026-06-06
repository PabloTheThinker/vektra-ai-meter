from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..util import cached_by_mtime, home, iter_jsonl, parse_iso, prune_cache, unix_ts

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


@dataclass
class _ClaudeSession:
    input: int = 0
    output: int = 0
    cache_create: int = 0
    cache_read: int = 0
    model: str | None = None
    title: str | None = None
    cwd: str | None = None
    at: datetime | None = None
    counts: bool = False  # has usage or a title — i.e. contributes to totals


# Per-session parse cache keyed on (mtime_ns, size). Session JSONL is append-only,
# so an unchanged signature means an unchanged parse — skip the full re-read.
_CLAUDE_SESSION_CACHE: dict[Path, tuple[tuple[int, int], _ClaudeSession]] = {}


def _parse_claude_session(path: Path) -> _ClaudeSession:
    rec = _ClaudeSession()
    has_usage = False
    for row in iter_jsonl(path):
        row_type = row.get("type")
        if row_type == "ai-title":
            rec.title = row.get("aiTitle") or rec.title
        if row_type == "user":
            rec.cwd = row.get("cwd") or rec.cwd
            rec.at = parse_iso(row.get("timestamp")) or rec.at
        if row_type == "assistant":
            message = row.get("message") or {}
            usage = _usage_from_message(message)
            if any(usage.values()):
                has_usage = True
                rec.input += usage["input"]
                rec.output += usage["output"]
                rec.cache_create += usage["cache_create"]
                rec.cache_read += usage["cache_read"]
            rec.model = message.get("model") or rec.model
            rec.cwd = row.get("cwd") or rec.cwd
            rec.at = parse_iso(row.get("timestamp")) or rec.at
    rec.counts = has_usage or rec.title is not None
    return rec


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
    scan_paths = paths[:MAX_CLAUDE_SCAN]
    prune_cache(_CLAUDE_SESSION_CACHE, set(scan_paths))
    for session_path in scan_paths:
        seen_session_ids.add(session_path.stem)
        rec = cached_by_mtime(_CLAUDE_SESSION_CACHE, session_path, _parse_claude_session)
        if rec is None or not rec.counts:
            continue

        session_total = rec.input + rec.output
        stats.sessions += 1
        stats.input_tokens += rec.input
        stats.output_tokens += rec.output
        stats.cache_create_tokens += rec.cache_create
        stats.cache_read_tokens += rec.cache_read
        stats.total_tokens += session_total

        if rec.at and rec.at.date() == today:
            stats.today_sessions += 1
            stats.today_tokens += session_total

        if stats.latest_at is None or (rec.at and rec.at >= stats.latest_at):
            stats.latest_at = rec.at
            stats.latest_model = rec.model
            stats.latest_title = rec.title
            stats.latest_cwd = rec.cwd

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