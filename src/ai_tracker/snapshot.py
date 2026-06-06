from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

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
    today_tokens: int
    model: str | None
    subtitle: str | None
    rate_primary: str | None = None
    rate_secondary: str | None = None


def _provider_view(provider_id: str, label: str, grok: GrokStats, codex: CodexStats, claude: ClaudeStats) -> ProviderView:
    if provider_id == "grok":
        return ProviderView(
            id="grok",
            label=label,
            sessions=grok.sessions,
            active_sessions=grok.active_sessions,
            total_tokens=grok.estimated_tokens,
            today_tokens=grok.today_messages,
            model=grok.latest_model,
            subtitle=grok.latest_title or (grok.latest_cwd and grok.latest_cwd.split("/")[-1]),
        )
    if provider_id == "codex":
        return ProviderView(
            id="codex",
            label=label,
            sessions=codex.sessions,
            active_sessions=codex.active_sessions,
            total_tokens=codex.total_tokens,
            today_tokens=codex.today_tokens,
            model=codex.latest_model,
            subtitle=codex.latest_title or (codex.latest_cwd and codex.latest_cwd.split("/")[-1]),
            rate_primary=fmt_percent(codex.rate_primary_pct),
            rate_secondary=fmt_percent(codex.rate_secondary_pct),
        )
    return ProviderView(
        id="claude",
        label=label,
        sessions=claude.sessions,
        active_sessions=claude.active_sessions,
        total_tokens=claude.total_tokens,
        today_tokens=claude.today_tokens,
        model=claude.latest_model,
        subtitle=claude.latest_title or (claude.latest_cwd and claude.latest_cwd.split("/")[-1]),
    )


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

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_tokens": total_tokens,
            "total_tokens_fmt": fmt_tokens(total_tokens),
            "today_tokens": today_tokens,
            "today_tokens_fmt": fmt_tokens(today_tokens),
            "active_sessions": active_sessions,
            "providers_online": sum(1 for item in providers if item.sessions > 0),
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