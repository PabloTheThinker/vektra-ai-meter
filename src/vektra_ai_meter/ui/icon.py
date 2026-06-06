from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap


def _usage_color(percent: float) -> QColor:
    if percent >= 85:
        return QColor("#ef4444")
    if percent >= 60:
        return QColor("#f59e0b")
    return QColor("#22c55e")


def make_tray_icon(bars: list[float | None] | None = None) -> QIcon:
    """Draw a tiny multi-bar meter icon (CodexBar-style) for the status tray."""
    size = 22
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    values = list(bars or [])
    while len(values) < 3:
        values.append(None)
    values = values[:4]

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    track = QColor("#3f3f46")
    gap = 2
    bar_w = max(2, (size - gap * (len(values) + 1)) // len(values))
    x = gap

    for value in values:
        height = size - gap * 2
        painter.setBrush(track)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(x, gap, bar_w, height, 1, 1)

        if value is not None:
            fill = max(2, int(height * min(100.0, max(0.0, value)) / 100.0))
            painter.setBrush(_usage_color(value))
            painter.drawRoundedRect(x, gap + (height - fill), bar_w, fill, 1, 1)

        x += bar_w + gap

    painter.end()
    return QIcon(pixmap)