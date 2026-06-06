from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..limits import UsageLimit, context_limit, has_window_limits, parse_codex_rate_limits
from ..util import home, iter_jsonl, parse_iso, unix_ts

MAX_CODEX_FULL_PARSE = 42


@dataclass
class CodexStats:
    sessions: int = 0
    active_sessions: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    latest_model: str | None = None
    latest_cwd: str | None = None
    latest_title: str | None = None
    latest_at: datetime | None = None
    rate_primary_pct: float | None = None
    rate_secondary_pct: float | None = None
    rate_primary_resets_at: datetime | None = None
    rate_secondary_resets_at: datetime | None = None
    plan_type: str | None = None
    context_window: int | None = None
    context_used_tokens: int | None = None
    today_tokens: int = 0
    today_sessions: int = 0
    limits: list[UsageLimit] = field(default_factory=list)


def _session_title(payload: dict[str, Any]) -> str | None:
    meta = payload.get("payload") or {}
    if payload.get("type") != "session_meta":
        return None
    cwd = meta.get("cwd")
    if cwd:
        return Path(cwd).name
    return meta.get("id")


def _note_rate_limits(
    payload: dict[str, Any],
    row_ts: str,
    *,
    best_ts: str | None,
    best_limits: dict[str, Any] | None,
) -> tuple[str | None, dict[str, Any] | None]:
    limits = payload.get("rate_limits") or (payload.get("info") or {}).get("rate_limits")
    if not limits or not has_window_limits(limits):
        return best_ts, best_limits
    if best_ts is None or row_ts > best_ts:
        return row_ts, limits
    return best_ts, best_limits


def _apply_rate_limits(stats: CodexStats, limits: dict[str, Any] | None) -> None:
    if not limits:
        return

    primary = limits.get("primary") or {}
    secondary = limits.get("secondary") or {}
    if primary.get("used_percent") is not None:
        stats.rate_primary_pct = float(primary["used_percent"])
        stats.rate_primary_resets_at = unix_ts(primary.get("resets_at"))
    if secondary.get("used_percent") is not None:
        stats.rate_secondary_pct = float(secondary["used_percent"])
        stats.rate_secondary_resets_at = unix_ts(secondary.get("resets_at"))
    stats.plan_type = limits.get("plan_type") or stats.plan_type
    stats.limits = parse_codex_rate_limits(
        limits,
        resets={
            "primary": stats.rate_primary_resets_at,
            "secondary": stats.rate_secondary_resets_at,
        },
    )


def collect_codex_stats() -> CodexStats:
    root = home() / ".codex" / "sessions"
    stats = CodexStats()
    if not root.exists():
        return stats

    today = datetime.now(timezone.utc).date()
    seen_sessions: set[Path] = set()
    today_sessions: set[Path] = set()
    latest_context_tokens = 0
    latest_context_window: int | None = None
    latest_context_ts: str | None = None

    paths = sorted(root.rglob("rollout-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    stats.sessions = len(paths)
    best_rate_ts: str | None = None
    best_rate_limits: dict[str, Any] | None = None

    for path in paths[:MAX_CODEX_FULL_PARSE]:
        seen_sessions.add(path)
        file_mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        session_input = 0
        session_output = 0
        session_reasoning = 0
        session_cached = 0
        session_total = 0
        session_model: str | None = None
        session_cwd: str | None = None
        session_title: str | None = None
        session_at: datetime | None = None
        session_active = False

        for row in iter_jsonl(path):
            row_type = row.get("type")
            payload = row.get("payload") or {}

            if row_type == "session_meta":
                session_title = _session_title(row) or session_title
                session_cwd = payload.get("cwd") or session_cwd
                session_at = parse_iso(payload.get("timestamp")) or session_at

            if row_type == "turn_context":
                turn = payload or {}
                session_model = turn.get("model") or session_model
                session_cwd = turn.get("cwd") or session_cwd
                session_at = parse_iso(row.get("timestamp")) or session_at

            if row_type == "event_msg" and payload.get("type") == "token_count":
                info = payload.get("info") or {}
                usage = info.get("total_token_usage") or info.get("last_token_usage") or {}
                session_input = max(session_input, int(usage.get("input_tokens") or 0))
                session_output = max(session_output, int(usage.get("output_tokens") or 0))
                session_reasoning = max(
                    session_reasoning, int(usage.get("reasoning_output_tokens") or 0)
                )
                session_cached = max(session_cached, int(usage.get("cached_input_tokens") or 0))
                session_total = max(session_total, int(usage.get("total_tokens") or 0))
                session_at = parse_iso(row.get("timestamp")) or session_at

                ts = str(row.get("timestamp") or "")
                best_rate_ts, best_rate_limits = _note_rate_limits(
                    payload,
                    ts,
                    best_ts=best_rate_ts,
                    best_limits=best_rate_limits,
                )

                context_window = info.get("model_context_window")
                if context_window and session_total:
                    if latest_context_ts is None or ts > latest_context_ts:
                        latest_context_ts = ts
                        latest_context_tokens = session_total
                        latest_context_window = int(context_window)

            if row_type == "event_msg" and payload.get("type") == "task_started":
                session_active = True

        if session_total <= 0 and session_input <= 0 and session_output <= 0:
            continue

        recent = False
        if session_at and (datetime.now(timezone.utc) - session_at).total_seconds() < 3600:
            recent = True
        if (datetime.now(timezone.utc) - file_mtime).total_seconds() < 3600:
            recent = True

        if session_active and recent:
            stats.active_sessions += 1
        stats.input_tokens += session_input
        stats.output_tokens += session_output
        stats.reasoning_tokens += session_reasoning
        stats.cached_tokens += session_cached
        stats.total_tokens += session_total or (session_input + session_output + session_reasoning)

        if session_at and session_at.date() == today:
            stats.today_tokens += session_total or (session_input + session_output + session_reasoning)
            today_sessions.add(path)

        if stats.latest_at is None or (session_at and session_at >= stats.latest_at):
            stats.latest_at = session_at
            stats.latest_model = session_model
            stats.latest_cwd = session_cwd
            stats.latest_title = session_title

    stats.today_sessions = len(today_sessions)
    stats.context_window = latest_context_window
    stats.context_used_tokens = latest_context_tokens or None

    _apply_rate_limits(stats, best_rate_limits)

    if not stats.limits:
        context = context_limit(
            label="Session",
            used_tokens=stats.context_used_tokens,
            window_tokens=stats.context_window,
        )
        if context:
            stats.limits.append(context)

    return stats