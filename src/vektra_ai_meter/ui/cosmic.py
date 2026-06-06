"""COSMIC desktop helpers — tray placement when Qt geometry is unavailable."""

from __future__ import annotations

import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path

TRAY_TITLE = "Vektra AI Meter"

# Symbolic tray cell = icon + padding×2 (cosmic-panel-config PanelSize).
_CELL_WIDTH: dict[str, int] = {
    "XS": 32,
    "S": 40,
    "M": 56,
    "L": 64,
    "XL": 80,
}

_BAR_HEIGHT: dict[str, int] = {
    "XS": 32,
    "S": 40,
    "M": 48,
    "L": 56,
    "XL": 64,
}

_STATUS_AREA_ID = "com.system76.CosmicAppletStatusArea"
_CONFIG_ROOT = Path.home() / ".config" / "cosmic" / "com.system76.CosmicPanel.Panel" / "v1"


def is_cosmic() -> bool:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
    return "COSMIC" in desktop.upper()


def _read_config_key(name: str, default: str = "") -> str:
    path = _CONFIG_ROOT / name
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return default


def panel_size_name() -> str:
    raw = _read_config_key("size", "XS")
    if raw.startswith("Custom("):
        match = re.search(r"Custom\((\d+)\)", raw)
        if match:
            return raw
    return raw if raw in _CELL_WIDTH else "XS"


def panel_cell_width(size: str | None = None) -> int:
    size = size or panel_size_name()
    if size.startswith("Custom("):
        match = re.search(r"Custom\((\d+)\)", size)
        if match:
            px = max(16, int(match.group(1)))
            px = px // 4 * 4
            return max(24, px // 2 + (px // 4) * 2)
    return _CELL_WIDTH.get(size, 32)


def panel_bar_height(size: str | None = None) -> int:
    size = size or panel_size_name()
    if size.startswith("Custom("):
        match = re.search(r"Custom\((\d+)\)", size)
        if match:
            px = max(16, int(match.group(1)))
            px = px // 4 * 4
            return max(24, min(64, px))
    return _BAR_HEIGHT.get(size, 32)


def cosmic_top_bar_height() -> int:
    """Panel thickness for gtk4-layer-shell margin_top when env is unset."""
    return panel_bar_height()


@lru_cache(maxsize=1)
def _right_wing_applet_ids() -> list[str]:
    raw = _read_config_key("plugins_wings")
    if not raw:
        return [_STATUS_AREA_ID]
    right_match = re.search(
        r"\],\s*\[\s*((?:\"[^\"]+\"\s*,?\s*)+)\s*\]\s*\)",
        raw,
        re.DOTALL,
    )
    if not right_match:
        return [_STATUS_AREA_ID]
    return re.findall(r"\"([^\"]+)\"", right_match.group(1))


def _right_wing_cells_after_status_area(cell: int, spacing: int) -> int:
    ids = _right_wing_applet_ids()
    if _STATUS_AREA_ID not in ids:
        return 0
    idx = ids.index(_STATUS_AREA_ID)
    tail = ids[idx + 1 :]
    if not tail:
        return 0
    # One cell per applet after the status area, plus spacing gaps between them.
    return len(tail) * cell + max(0, len(tail) - 1) * spacing


def _panel_spacing() -> int:
    raw = _read_config_key("spacing", "0")
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _panel_margin() -> int:
    raw = _read_config_key("margin", "0")
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def _busctl_property(service: str, path: str, interface: str, prop: str) -> str | None:
    try:
        proc = subprocess.run(
            [
                "busctl",
                "--user",
                "get-property",
                service,
                path,
                interface,
                prop,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _status_notifier_services() -> list[str]:
    raw = _busctl_property(
        "org.kde.StatusNotifierWatcher",
        "/StatusNotifierWatcher",
        "org.kde.StatusNotifierWatcher",
        "RegisteredStatusNotifierItems",
    )
    if not raw:
        return []
    return re.findall(r"\"([^\"]+)\"", raw)


def _status_notifier_title(service: str) -> str | None:
    for path in ("/StatusNotifierItem", f"/org/ayatana/NotificationItem/{service.split(':')[-1]}"):
        raw = _busctl_property(service, path, "org.kde.StatusNotifierItem", "Title")
        if raw and raw.startswith("s "):
            return raw[2:].strip('"')
    return None


def status_notifier_tray_index(title: str = TRAY_TITLE) -> tuple[int, int] | None:
    """Return (index, total) of our tray icon in the status area, or None."""
    services = _status_notifier_services()
    if not services:
        return None
    for i, service in enumerate(services):
        if _status_notifier_title(service) == title:
            return i, len(services)
    return None


def estimate_tray_rect(
    screen: tuple[int, int, int, int],
    *,
    title: str = TRAY_TITLE,
) -> tuple[int, int, int, int] | None:
    """
    Estimate tray icon global rect on COSMIC when QSystemTrayIcon.geometry() is empty.

    Uses StatusNotifier registration order and cosmic-panel wing layout.
    """
    if not is_cosmic():
        return None

    placement = status_notifier_tray_index(title)
    if placement is None:
        return None

    index, total = placement
    sx, sy, sw, _sh = screen
    cell = panel_cell_width()
    spacing = _panel_spacing()
    margin = _panel_margin()

    tail_px = _right_wing_cells_after_status_area(cell, spacing)
    status_width = total * cell + max(0, total - 1) * spacing

    # Right wing: [.. StatusArea (n icons) .. tail applets ..] flush to screen right.
    tray_right = sx + sw - margin - tail_px
    tray_left = tray_right - status_width + index * (cell + spacing)
    tray_top = sy + margin + max(0, (panel_bar_height() - cell) // 2)

    return (tray_left, tray_top, cell, cell)