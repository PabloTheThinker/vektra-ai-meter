from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .limits import headline_limit, limits_to_dicts
from .providers.claude import ClaudeStats, collect_claude_stats
from .providers.codex import CodexStats, collect_codex_stats
from .providers.grok import GrokStats, collect_grok_stats
from .util import fmt_percent, fmt_tokens, snapshot_path


@dataclass
class ProviderView:
    id: str
    label: str
    sessions: int
    active_sessions: int
    total_tokens: int
    total_tokens_fmt: str
    today_tokens: int
    model: str | None
    subtitle: str | None
    rate_primary: str | None = None
    rate_secondary: str | None = None
    limits: list[dict[str, Any]] = field(default_factory=list)
    limit_headline: str | None = None
    plan_type: str | None = None


def _primary_secondary(limits: list) -> tuple[str | None, str | None]:
    primary = None
    secondary = None
    for item in limits:
        if item.used_percent is None:
            continue
        label = (item.label or "").lower()
        if primary is None and label not in {"7d", "7w"}:
            primary = fmt_percent(item.used_percent)
        elif secondary is None:
            secondary = fmt_percent(item.used_percent)
    return primary, secondary


def _provider_view(
    provider_id: str,
    label: str,
    grok: GrokStats,
    codex: CodexStats,
    claude: ClaudeStats,
) -> ProviderView:
    if provider_id == "grok":
        limits = grok.limits
        primary, secondary = _primary_secondary(limits)
        return ProviderView(
            id="grok",
            label=label,
            sessions=grok.sessions,
            active_sessions=grok.active_sessions,
            total_tokens=grok.estimated_tokens,
            total_tokens_fmt=fmt_tokens(grok.estimated_tokens),
            today_tokens=grok.today_messages,
            model=grok.latest_model,
            subtitle=grok.latest_title or (grok.latest_cwd and grok.latest_cwd.split("/")[-1]),
            rate_primary=primary,
            rate_secondary=secondary,
            limits=limits_to_dicts(limits),
            limit_headline=headline_limit(limits),
        )
    if provider_id == "codex":
        limits = codex.limits
        primary, secondary = _primary_secondary(limits)
        if primary is None and codex.rate_primary_pct is not None:
            primary = fmt_percent(codex.rate_primary_pct)
        if secondary is None and codex.rate_secondary_pct is not None:
            secondary = fmt_percent(codex.rate_secondary_pct)
        return ProviderView(
            id="codex",
            label=label,
            sessions=codex.sessions,
            active_sessions=codex.active_sessions,
            total_tokens=codex.total_tokens,
            total_tokens_fmt=fmt_tokens(codex.total_tokens),
            today_tokens=codex.today_tokens,
            model=codex.latest_model,
            subtitle=codex.latest_title or (codex.latest_cwd and codex.latest_cwd.split("/")[-1]),
            rate_primary=primary,
            rate_secondary=secondary,
            limits=limits_to_dicts(limits),
            limit_headline=headline_limit(limits),
            plan_type=codex.plan_type,
        )
    limits = getattr(claude, "limits", [])
    primary, secondary = _primary_secondary(limits)
    return ProviderView(
        id="claude",
        label=label,
        sessions=claude.sessions,
        active_sessions=claude.active_sessions,
        total_tokens=claude.total_tokens,
        total_tokens_fmt=fmt_tokens(claude.total_tokens),
        today_tokens=claude.today_tokens,
        model=claude.latest_model,
        subtitle=claude.latest_title or (claude.latest_cwd and claude.latest_cwd.split("/")[-1]),
        rate_primary=primary,
        rate_secondary=secondary,
        limits=limits_to_dicts(limits),
        limit_headline=headline_limit(limits),
    )


def _usage_summary(providers: list[ProviderView]) -> dict[str, Any]:
    highlights: list[str] = []
    peak_pct: float | None = None
    peak_label: str | None = None

    for provider in providers:
        for limit in provider.limits or []:
            used = limit.get("used_percent")
            if used is None:
                continue
            window_label = limit.get("label") or provider.label
            if window_label == "Session":
                continue
            label = window_label
            highlights.append(f"{provider.label} {label} {used:.0f}%")
            if peak_pct is None or float(used) > peak_pct:
                peak_pct = float(used)
                peak_label = f"{provider.label} {label}"

    return {
        "peak_percent": peak_pct,
        "peak_label": peak_label,
        "peak_percent_fmt": fmt_percent(peak_pct) if peak_pct is not None else None,
        "highlights": highlights,
    }


def build_snapshot() -> dict[str, Any]:
    grok = collect_grok_stats()
    codex = collect_codex_stats()
    claude = collect_claude_stats()

    providers = [
        _provider_view("grok", "Grok Build", grok, codex, claude),
        _provider_view("codex", "Codex", grok, codex, claude),
        _provider_view("claude", "Claude Code", grok, codex, claude),
    ]

    total_tokens = sum(item.total_tokens for item in providers)
    today_tokens = sum(item.today_tokens for item in providers)
    active_sessions = sum(item.active_sessions for item in providers)
    usage = _usage_summary(providers)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_tokens": total_tokens,
            "total_tokens_fmt": fmt_tokens(total_tokens),
            "today_tokens": today_tokens,
            "today_tokens_fmt": fmt_tokens(today_tokens),
            "active_sessions": active_sessions,
            "providers_online": sum(1 for item in providers if item.sessions > 0),
            **usage,
        },
        "providers": [asdict(item) for item in providers],
        "raw": {
            "grok": asdict(grok),
            "codex": asdict(codex),
            "claude": asdict(claude),
        },
    }


def write_snapshot() -> dict[str, Any]:
    snapshot = build_snapshot()
    path = snapshot_path()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, default=str)
    return snapshot