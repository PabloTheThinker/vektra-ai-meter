from __future__ import annotations

import os

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget

from .cosmic import estimate_tray_rect, is_cosmic
from .placement import top_bar_height
from .theme import PANEL_WIDTH


def is_wayland() -> bool:
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    return session == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))


def _screen_tuple(screen) -> tuple[int, int, int, int]:
    geo = screen.geometry()
    return (geo.x(), geo.y(), geo.width(), geo.height())


def screen_for_tray(tray: QSystemTrayIcon):
    geo = tray.geometry()
    if geo.isValid() and geo.width() > 0 and geo.height() > 0:
        screen = QApplication.screenAt(geo.center())
        if screen is not None:
            return screen
    cursor_screen = QApplication.screenAt(QCursor.pos())
    if cursor_screen is not None:
        return cursor_screen
    return QApplication.primaryScreen()


def tray_anchor_rect(tray: QSystemTrayIcon) -> QRect:
    geo = tray.geometry()
    if geo.isValid() and geo.width() > 0 and geo.height() > 0:
        return geo

    screen = screen_for_tray(tray)
    if screen is None:
        return QRect(100, 0, 24, 24)

    screen_rect = _screen_tuple(screen)
    if is_cosmic():
        estimated = estimate_tray_rect(screen_rect)
        if estimated is not None:
            x, y, w, h = estimated
            return QRect(x, y, w, h)

    full = screen.geometry()
    bar_h = top_bar_height()
    return QRect(full.right() - 40, full.top() + max(0, (bar_h - 24) // 2), 24, 24)


def _tray_geometry_known(tray: QSystemTrayIcon) -> bool:
    geo = tray.geometry()
    return geo.isValid() and geo.width() > 0 and geo.height() > 0


def panel_origin(tray: QSystemTrayIcon, panel_width: int, panel_height: int) -> tuple[QPoint, int]:
    """Anchor dropdown flush under the top panel / tray icon."""
    anchor = tray_anchor_rect(tray)
    screen = screen_for_tray(tray)
    full = screen.geometry() if screen else QRect(0, 0, 1920, 1080)
    bar_h = top_bar_height()

    center_x = anchor.center().x()
    x = center_x - panel_width // 2
    y = anchor.bottom() + 1
    caret_x = center_x - x

    if not _tray_geometry_known(tray):
        caret_x = panel_width - 32

    x = min(max(full.left() + 6, x), full.right() - panel_width - 6)
    y = max(full.top() + bar_h, y)
    caret_x = max(20, min(panel_width - 20, caret_x))
    return QPoint(x, y), caret_x


def apply_dropdown_window_flags(panel: QWidget) -> None:
    """Tool surface that stays attached to the top bar — not a normal app window."""
    panel.setWindowFlags(
        Qt.WindowType.Tool
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
        | Qt.WindowType.WindowDoesNotAcceptFocus
    )
    panel.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
    panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    panel.setAttribute(Qt.WidgetAttribute.WA_X11DoNotAcceptFocus, True)


def show_panel_near_tray(panel: QWidget, tray: QSystemTrayIcon) -> None:
    """Drop the usage panel from the top-bar tray — integrated, not a separate app window."""
    apply_dropdown_window_flags(panel)
    panel.adjustSize()
    origin, caret_x = panel_origin(tray, panel.width(), panel.height())
    if hasattr(panel, "caret"):
        panel.caret.set_offset(caret_x)
    panel.move(origin)
    panel.show()
    panel.raise_()


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