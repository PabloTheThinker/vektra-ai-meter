from __future__ import annotations

from importlib import resources
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap

from .theme import usage_color

_ICON_CACHE: dict[int, QPixmap] = {}
_LIVE_ICON_CACHE: dict[tuple[float | None, ...], QIcon] = {}


def _asset_path(size: int) -> Path | None:
    try:
        pkg = resources.files("vektra_ai_meter").joinpath("assets", f"tray-icon-{size}.png")
        with resources.as_file(pkg) as path:
            if path.is_file():
                return path
    except (ModuleNotFoundError, FileNotFoundError, TypeError):
        pass

    local = Path(__file__).resolve().parent.parent / "assets" / f"tray-icon-{size}.png"
    return local if local.is_file() else None


def _brand_pixmap(size: int) -> QPixmap | None:
    if size in _ICON_CACHE:
        return _ICON_CACHE[size]

    path = _asset_path(size)
    if path is None:
        return None

    image = QImage(str(path))
    if image.isNull():
        return None

    pixmap = QPixmap.fromImage(image)
    _ICON_CACHE[size] = pixmap
    return pixmap


def _bar_key(bars: list[float | None] | None) -> tuple[float | None, ...]:
    values = list(bars or [])
    while len(values) < 3:
        values.append(None)
    return tuple(round(value, 1) if value is not None else None for value in values[:3])


def _draw_bars(painter: QPainter, size: int, bars: list[float | None]) -> None:
    values = list(bars or [])
    while len(values) < 3:
        values.append(None)
    values = values[:3]

    gap = max(2, size // 11)
    bar_w = max(3, (size - gap * (len(values) + 1)) // len(values))
    x = gap
    bar_h = size - gap * 2
    track = QColor(63, 63, 70, 180)

    for value in values:
        painter.setBrush(track)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(x, gap, bar_w, bar_h, 2, 2)

        if value is not None:
            fill_h = max(2, int(bar_h * min(100.0, max(0.0, value)) / 100.0))
            painter.setBrush(QColor(usage_color(value)))
            painter.drawRoundedRect(x, gap + (bar_h - fill_h), bar_w, fill_h, 2, 2)

        x += bar_w + gap


def make_tray_icon(bars: list[float | None] | None = None) -> QIcon:
    """Tray icon: generated Vektra asset; live bars overlaid when quota data exists."""
    size = 22
    brand = _brand_pixmap(size)
    has_live = bars and any(value is not None for value in bars)

    if brand is not None and not has_live:
        return QIcon(brand)

    key = _bar_key(bars)
    if key in _LIVE_ICON_CACHE:
        return _LIVE_ICON_CACHE[key]

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    if brand is not None:
        painter.setOpacity(0.35)
        painter.drawPixmap(0, 0, brand)
        painter.setOpacity(1.0)

    _draw_bars(painter, size, bars or [])
    painter.end()

    icon = QIcon(pixmap)
    _LIVE_ICON_CACHE[key] = icon
    if len(_LIVE_ICON_CACHE) > 48:
        _LIVE_ICON_CACHE.pop(next(iter(_LIVE_ICON_CACHE)))
    return icon