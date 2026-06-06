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


def _tray_geometry_known(tray: QSystemTrayIcon) -> bool:
    geo = tray.geometry()
    return geo.isValid() and geo.width() > 0 and geo.height() > 0


def panel_origin(tray: QSystemTrayIcon, panel_width: int, panel_height: int) -> tuple[QPoint, int]:
    """Return dropdown position and caret offset (x within panel)."""
    anchor = tray_anchor_rect(tray)
    screen = QApplication.primaryScreen()
    available = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

    if _tray_geometry_known(tray):
        center_x = anchor.center().x()
        x = center_x - panel_width // 2
        y = anchor.bottom() + 2
        caret_x = center_x - x
    else:
        x = available.right() - panel_width - 12
        y = available.top() + 6
        caret_x = panel_width - 36

    if y + panel_height > available.bottom():
        y = max(available.top() + 6, anchor.y() - panel_height - 4)
        caret_x = panel_width - 36

    x = min(max(available.left() + 8, x), available.right() - panel_width - 8)
    y = min(max(available.top() + 4, y), available.bottom() - panel_height - 8)
    caret_x = max(18, min(panel_width - 18, caret_x))
    return QPoint(x, y), caret_x


def show_panel_near_tray(panel: QWidget, tray: QSystemTrayIcon) -> None:
    """Drop the usage panel down from the top-bar tray icon."""
    panel.adjustSize()
    origin, caret_x = panel_origin(tray, panel.width(), panel.height())
    if hasattr(panel, "caret"):
        panel.caret.set_offset(caret_x)
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