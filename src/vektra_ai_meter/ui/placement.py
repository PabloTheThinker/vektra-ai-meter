from __future__ import annotations

import os
from dataclasses import dataclass

from .theme import PANEL_WIDTH

PANEL_HEIGHT = 420


def top_bar_height() -> int:
    raw = os.environ.get("VEKTRA_TOP_BAR_HEIGHT", "36")
    try:
        return max(24, min(64, int(raw)))
    except ValueError:
        return 36


@dataclass(frozen=True)
class PanelPlacement:
    margin_top: int
    margin_left: int
    margin_right: int
    anchor_left: bool


def compute_panel_placement(
    *,
    panel_width: int = PANEL_WIDTH,
    tray: tuple[int, int, int, int] | None = None,
    screen: tuple[int, int, int, int] | None = None,
) -> PanelPlacement:
    """Mirror Qt `panel_origin` for gtk4-layer-shell margins (CodexBar-style)."""
    bar_h = top_bar_height()
    if screen is None:
        screen = (0, 0, 1920, 1080)
    sx, sy, sw, _sh = screen

    if tray is None or tray[2] <= 0 or tray[3] <= 0:
        return PanelPlacement(
            margin_top=bar_h,
            margin_left=10,
            margin_right=10,
            anchor_left=False,
        )

    tx, ty, tw, th = tray
    center_x = tx + tw // 2
    panel_x = center_x - panel_width // 2
    panel_x = min(max(sx + 6, panel_x), sx + sw - panel_width - 6)
    panel_y = max(ty + th + 1, sy + bar_h)

    return PanelPlacement(
        margin_top=panel_y - sy,
        margin_left=panel_x - sx,
        margin_right=10,
        anchor_left=True,
    )