from __future__ import annotations

# CodexBar-inspired dark popover palette
BG = "#0c0c0e"
BG_ELEVATED = "#141416"
BG_CARD = "#18181b"
BORDER = "#2a2a2e"
BORDER_SUBTLE = "#232326"
TEXT = "#f4f4f5"
TEXT_MUTED = "#a1a1aa"
TEXT_DIM = "#71717a"
ACCENT = "#a855f7"  # Vektra magenta
PANEL_WIDTH = 380

PROVIDER_STYLES: dict[str, dict[str, str]] = {
    "grok": {
        "accent": "#f97316",
        "badge": "G",
        "name": "Grok Build",
    },
    "codex": {
        "accent": "#10b981",
        "badge": "C",
        "name": "Codex",
    },
    "claude": {
        "accent": "#e07a5f",
        "badge": "Cl",
        "name": "Claude Code",
    },
}

WINDOW_TITLES: dict[str, str] = {
    "5h": "5-hour window",
    "7d": "Weekly",
    "Context": "Context window",
    "Session": "Session context",
}


def usage_color(percent: float) -> str:
    if percent >= 90:
        return "#ef4444"
    if percent >= 70:
        return "#f59e0b"
    return "#22c55e"


def usage_state(percent: float | None) -> str:
    if percent is None:
        return "idle"
    if percent >= 90:
        return "critical"
    if percent >= 70:
        return "warning"
    return "ok"


def window_title(label: str) -> str:
    return WINDOW_TITLES.get(label, label)


def provider_style(provider_id: str) -> dict[str, str]:
    return PROVIDER_STYLES.get(
        provider_id,
        {"accent": ACCENT, "badge": "?", "name": provider_id},
    )