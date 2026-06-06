from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from .theme import usage_color


def _qcolor(hex_value: str) -> QColor:
    return QColor(hex_value)


def make_tray_icon(bars: list[float | None] | None = None) -> QIcon:
    """Draw a CodexBar-style multi-bar meter for the status tray."""
    size = 22
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    values = list(bars or [])
    while len(values) < 3:
        values.append(None)
    values = values[:3]

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    track = _qcolor("#3f3f46")
    gap = 2
    bar_w = max(3, (size - gap * (len(values) + 1)) // len(values))
    x = gap
    bar_h = size - gap * 2

    for value in values:
        painter.setBrush(track)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(x, gap, bar_w, bar_h, 2, 2)

        if value is not None:
            fill_h = max(2, int(bar_h * min(100.0, max(0.0, value)) / 100.0))
            painter.setBrush(_qcolor(usage_color(value)))
            painter.drawRoundedRect(x, gap + (bar_h - fill_h), bar_w, fill_h, 2, 2)

        x += bar_w + gap

    painter.end()
    return QIcon(pixmap)