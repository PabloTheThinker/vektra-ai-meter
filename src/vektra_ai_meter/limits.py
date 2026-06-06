from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass
class UsageLimit:
    label: str
    used_percent: float | None = None
    remaining_percent: float | None = None
    resets_at: datetime | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if isinstance(data.get("resets_at"), datetime):
            data["resets_at"] = data["resets_at"].isoformat()
        return data

    def compact(self) -> str:
        if self.used_percent is not None:
            return f"{self.label} {self.used_percent:.0f}%"
        if self.remaining_percent is not None:
            return f"{self.label} {self.remaining_percent:.0f}% left"
        if self.detail:
            return f"{self.label} {self.detail}"
        return self.label


def window_label(minutes: int | None) -> str:
    if minutes is None:
        return "Limit"
    if minutes % 10_080 == 0 and minutes >= 10_080:
        weeks = minutes // 10_080
        return f"{weeks}w" if weeks > 1 else "7d"
    if minutes % 60 == 0 and minutes >= 60:
        hours = minutes // 60
        return f"{hours}h"
    return f"{minutes}m"


def limit_from_window(
    *,
    label: str,
    used_percent: float | None,
    window_minutes: int | None = None,
    resets_at: datetime | None = None,
) -> UsageLimit | None:
    if used_percent is None:
        return None
    name = label or window_label(window_minutes)
    remaining = max(0.0, 100.0 - float(used_percent))
    return UsageLimit(
        label=name,
        used_percent=float(used_percent),
        remaining_percent=remaining,
        resets_at=resets_at,
        detail=f"{used_percent:.0f}% used",
    )


def context_limit(
    *,
    label: str,
    used_tokens: int | None,
    window_tokens: int | None,
) -> UsageLimit | None:
    if not used_tokens or not window_tokens or window_tokens <= 0:
        return None
    used_percent = min(100.0, (used_tokens / window_tokens) * 100.0)
    remaining = max(0.0, 100.0 - used_percent)
    return UsageLimit(
        label=label,
        used_percent=round(used_percent, 1),
        remaining_percent=round(remaining, 1),
        detail=f"{used_percent:.0f}% of window",
    )


def parse_codex_rate_limits(limits: dict[str, Any], *, resets: dict[str, datetime | None]) -> list[UsageLimit]:
    parsed: list[UsageLimit] = []

    primary = limits.get("primary") or {}
    secondary = limits.get("secondary") or {}
    primary_limit = limit_from_window(
        label=window_label(primary.get("window_minutes")),
        used_percent=_float_or_none(primary.get("used_percent")),
        window_minutes=primary.get("window_minutes"),
        resets_at=resets.get("primary"),
    )
    secondary_limit = limit_from_window(
        label=window_label(secondary.get("window_minutes")),
        used_percent=_float_or_none(secondary.get("used_percent")),
        window_minutes=secondary.get("window_minutes"),
        resets_at=resets.get("secondary"),
    )
    if primary_limit:
        parsed.append(primary_limit)
    if secondary_limit:
        parsed.append(secondary_limit)

    credits = limits.get("credits") or {}
    if credits and not parsed:
        balance = credits.get("balance")
        unlimited = credits.get("unlimited")
        if unlimited:
            parsed.append(UsageLimit(label="Credits", detail="unlimited"))
        elif balance is not None:
            parsed.append(UsageLimit(label="Credits", detail=str(balance)))

    individual = limits.get("individual_limit") or {}
    if individual.get("used_percent") is not None:
        item = limit_from_window(
            label=limits.get("limit_name") or limits.get("limit_id") or "Quota",
            used_percent=_float_or_none(individual.get("used_percent")),
            window_minutes=individual.get("window_minutes"),
        )
        if item:
            parsed.append(item)

    return parsed


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def has_window_limits(limits: dict[str, Any]) -> bool:
    primary = limits.get("primary") or {}
    secondary = limits.get("secondary") or {}
    individual = limits.get("individual_limit") or {}
    return any(
        bucket.get("used_percent") is not None
        for bucket in (primary, secondary, individual)
    )


def limits_to_dicts(items: list[UsageLimit]) -> list[dict[str, Any]]:
    return [item.to_dict() for item in items]


def headline_limit(items: list[UsageLimit]) -> str | None:
    for item in items:
        if item.used_percent is not None:
            return item.compact()
    for item in items:
        if item.detail:
            return item.compact()
    return None