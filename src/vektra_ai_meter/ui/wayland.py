from __future__ import annotations

import os

from PySide6.QtCore import QEvent, QObject, QPoint, QRect
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget


def is_wayland() -> bool:
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    return session == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))


def tray_anchor_rect(tray: QSystemTrayIcon) -> QRect:
    geo = tray.geometry()
    if geo.isValid() and geo.width() > 0 and geo.height() > 0:
        return geo

    screen = QApplication.primaryScreen()
    if screen is None:
        return QRect(100, 100, 1, 1)

    available = screen.availableGeometry()
    return QRect(available.right() - 48, available.top() + 4, 24, 24)


def panel_origin(tray: QSystemTrayIcon, panel_width: int, panel_height: int) -> QPoint:
    anchor = tray_anchor_rect(tray)
    screen = QApplication.primaryScreen()
    available = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

    x = anchor.x() + max(0, (anchor.width() - panel_width) // 2)
    y = anchor.y() + anchor.height() + 8

    if y + panel_height > available.bottom():
        y = max(available.top() + 8, anchor.y() - panel_height - 8)

    x = min(max(available.left() + 8, x), available.right() - panel_width - 8)
    y = min(max(available.top() + 8, y), available.bottom() - panel_height - 8)
    return QPoint(x, y)


def show_panel_near_tray(panel: QWidget, tray: QSystemTrayIcon) -> None:
    """Position and show the usage panel without Wayland grabbing-popup windows."""
    panel.adjustSize()
    origin = panel_origin(tray, panel.width(), panel.height())
    panel.move(origin)
    panel.show()
    panel.raise_()
    if not is_wayland():
        panel.activateWindow()


class ClickAwayFilter(QObject):
    """Hide the panel when the user clicks outside it (Wayland-safe)."""

    def __init__(self, panel: QWidget, tray: QSystemTrayIcon) -> None:
        super().__init__()
        self._panel = panel
        self._tray = tray
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if not self._panel.isVisible():
            return False
        if event.type() != QEvent.Type.MouseButtonPress:
            return False

        global_pos = event.globalPosition().toPoint()
        if self._panel.frameGeometry().contains(global_pos):
            return False

        tray_rect = tray_anchor_rect(self._tray)
        if tray_rect.contains(global_pos):
            return False

        self._panel.hide()
        return False