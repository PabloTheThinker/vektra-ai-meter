from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..limits import UsageLimit, context_limit, has_window_limits, parse_codex_rate_limits
from ..util import cached_by_mtime, home, iter_jsonl, parse_iso, prune_cache, unix_ts

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


@dataclass
class _CodexSession:
    input: int = 0
    output: int = 0
    reasoning: int = 0
    cached: int = 0
    total: int = 0
    model: str | None = None
    cwd: str | None = None
    title: str | None = None
    at: datetime | None = None
    active: bool = False
    mtime_epoch: float = 0.0
    # latest rate-limit window seen in this session (folded globally by max ts)
    rate_ts: str | None = None
    rate_limits: dict[str, Any] | None = None
    # latest context-window candidate in this session (folded globally by max ts)
    ctx_ts: str | None = None
    ctx_tokens: int = 0
    ctx_window: int | None = None


# Per-session parse cache keyed on (mtime_ns, size). Rollout JSONL is append-only.
_CODEX_SESSION_CACHE: dict[Path, tuple[tuple[int, int], _CodexSession]] = {}


def _parse_codex_session(path: Path) -> _CodexSession:
    rec = _CodexSession()
    try:
        rec.mtime_epoch = path.stat().st_mtime
    except OSError:
        rec.mtime_epoch = 0.0

    for row in iter_jsonl(path):
        row_type = row.get("type")
        payload = row.get("payload") or {}

        if row_type == "session_meta":
            rec.title = _session_title(row) or rec.title
            rec.cwd = payload.get("cwd") or rec.cwd
            rec.at = parse_iso(payload.get("timestamp")) or rec.at

        if row_type == "turn_context":
            turn = payload or {}
            rec.model = turn.get("model") or rec.model
            rec.cwd = turn.get("cwd") or rec.cwd
            rec.at = parse_iso(row.get("timestamp")) or rec.at

        if row_type == "event_msg" and payload.get("type") == "token_count":
            info = payload.get("info") or {}
            usage = info.get("total_token_usage") or info.get("last_token_usage") or {}
            rec.input = max(rec.input, int(usage.get("input_tokens") or 0))
            rec.output = max(rec.output, int(usage.get("output_tokens") or 0))
            rec.reasoning = max(rec.reasoning, int(usage.get("reasoning_output_tokens") or 0))
            rec.cached = max(rec.cached, int(usage.get("cached_input_tokens") or 0))
            rec.total = max(rec.total, int(usage.get("total_tokens") or 0))
            rec.at = parse_iso(row.get("timestamp")) or rec.at

            ts = str(row.get("timestamp") or "")
            rec.rate_ts, rec.rate_limits = _note_rate_limits(
                payload, ts, best_ts=rec.rate_ts, best_limits=rec.rate_limits
            )

            context_window = info.get("model_context_window")
            if context_window and rec.total:
                if rec.ctx_ts is None or ts > rec.ctx_ts:
                    rec.ctx_ts = ts
                    rec.ctx_tokens = rec.total
                    rec.ctx_window = int(context_window)

        if row_type == "event_msg" and payload.get("type") == "task_started":
            rec.active = True

    return rec


def collect_codex_stats() -> CodexStats:
    root = home() / ".codex" / "sessions"
    stats = CodexStats()
    if not root.exists():
        return stats

    now = datetime.now(timezone.utc)
    today = now.date()
    today_sessions: set[Path] = set()
    latest_context_tokens = 0
    latest_context_window: int | None = None
    latest_context_ts: str | None = None

    paths = sorted(root.rglob("rollout-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    stats.sessions = len(paths)
    best_rate_ts: str | None = None
    best_rate_limits: dict[str, Any] | None = None

    scan_paths = paths[:MAX_CODEX_FULL_PARSE]
    prune_cache(_CODEX_SESSION_CACHE, set(scan_paths))

    for path in scan_paths:
        rec = cached_by_mtime(_CODEX_SESSION_CACHE, path, _parse_codex_session)
        if rec is None:
            continue

        # Fold this session's rate-limit / context candidates into the global best.
        best_rate_ts, best_rate_limits = _note_rate_limits(
            {"rate_limits": rec.rate_limits} if rec.rate_limits else {},
            rec.rate_ts or "",
            best_ts=best_rate_ts,
            best_limits=best_rate_limits,
        )
        if rec.ctx_window and rec.ctx_ts and (latest_context_ts is None or rec.ctx_ts > latest_context_ts):
            latest_context_ts = rec.ctx_ts
            latest_context_tokens = rec.ctx_tokens
            latest_context_window = rec.ctx_window

        if rec.total <= 0 and rec.input <= 0 and rec.output <= 0:
            continue

        recent = False
        if rec.at and (now - rec.at).total_seconds() < 3600:
            recent = True
        if rec.mtime_epoch and (now.timestamp() - rec.mtime_epoch) < 3600:
            recent = True

        if rec.active and recent:
            stats.active_sessions += 1
        stats.input_tokens += rec.input
        stats.output_tokens += rec.output
        stats.reasoning_tokens += rec.reasoning
        stats.cached_tokens += rec.cached
        stats.total_tokens += rec.total or (rec.input + rec.output + rec.reasoning)

        if rec.at and rec.at.date() == today:
            stats.today_tokens += rec.total or (rec.input + rec.output + rec.reasoning)
            today_sessions.add(path)

        if stats.latest_at is None or (rec.at and rec.at >= stats.latest_at):
            stats.latest_at = rec.at
            stats.latest_model = rec.model
            stats.latest_cwd = rec.cwd
            stats.latest_title = rec.title

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