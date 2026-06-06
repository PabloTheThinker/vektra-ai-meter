from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..limits import UsageLimit, context_limit, limit_from_window
from ..util import home, iter_jsonl, parse_iso


@dataclass
class GrokStats:
    sessions: int = 0
    active_sessions: int = 0
    messages: int = 0
    latest_model: str | None = None
    latest_title: str | None = None
    latest_cwd: str | None = None
    latest_at: datetime | None = None
    estimated_tokens: int = 0
    today_messages: int = 0
    today_sessions: int = 0
    context_window_pct: float | None = None
    context_used_tokens: int | None = None
    context_window_tokens: int | None = None
    limits: list[UsageLimit] = field(default_factory=list)


def _read_summary(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def _session_tokens(updates_path: Path) -> int:
    peak = 0
    for row in iter_jsonl(updates_path):
        meta = row.get("_meta") or {}
        params = row.get("params") or {}
        nested = params.get("_meta") or {}
        for source in (meta, nested):
            total = source.get("totalTokens")
            if isinstance(total, (int, float)):
                peak = max(peak, int(total))
    return peak


def _read_summary_tokens(updates_path: Path) -> int:
    return _session_tokens(updates_path)


def _read_signals(summary_path: Path) -> dict[str, Any]:
    signals_path = summary_path.parent / "signals.json"
    if not signals_path.exists():
        return {}
    try:
        with signals_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _apply_signals(stats: GrokStats, signals: dict[str, Any]) -> None:
    usage = signals.get("contextWindowUsage")
    used = signals.get("contextTokensUsed")
    window = signals.get("contextWindowTokens")
    stats.limits = []
    if usage is not None:
        stats.context_window_pct = float(usage)
    if used is not None:
        stats.context_used_tokens = int(used)
    if window is not None:
        stats.context_window_tokens = int(window)

    context = context_limit(
        label="Context",
        used_tokens=stats.context_used_tokens,
        window_tokens=stats.context_window_tokens,
    )
    if context:
        stats.limits.append(context)
    elif stats.context_window_pct is not None:
        item = limit_from_window(
            label="Context",
            used_percent=stats.context_window_pct,
        )
        if item:
            stats.limits.append(item)


def collect_grok_stats() -> GrokStats:
    root = home() / ".grok" / "sessions"
    stats = GrokStats()
    if not root.exists():
        return stats

    today = datetime.now(timezone.utc).date()

    for summary_path in root.rglob("summary.json"):
        summary = _read_summary(summary_path)
        info = summary.get("info") or summary
        updated_at = parse_iso(summary.get("updated_at") or summary.get("last_active_at"))
        created_at = parse_iso(summary.get("created_at"))
        session_at = updated_at or created_at

        stats.sessions += 1
        messages = int(summary.get("num_chat_messages") or summary.get("num_messages") or 0)
        stats.messages += messages

        updates_path = summary_path.parent / "updates.jsonl"
        session_tokens = _read_summary_tokens(updates_path) if updates_path.exists() else 0
        stats.estimated_tokens += session_tokens

        if session_at and (datetime.now(timezone.utc) - session_at).total_seconds() < 3600:
            stats.active_sessions += 1

        if session_at and session_at.date() == today:
            stats.today_sessions += 1
            stats.today_messages += messages

        model = summary.get("current_model_id")
        title = summary.get("generated_title") or summary.get("session_summary")
        cwd = info.get("cwd")

        if stats.latest_at is None or (session_at and session_at >= stats.latest_at):
            stats.latest_at = session_at
            stats.latest_model = model
            stats.latest_title = title
            stats.latest_cwd = cwd
            _apply_signals(stats, _read_signals(summary_path))

    return stats