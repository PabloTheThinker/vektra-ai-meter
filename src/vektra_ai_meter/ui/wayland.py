from __future__ import annotations

import os

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget


def is_wayland() -> bool:
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    return session == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))


class TrayAnchor(QWidget):
    """Tiny tool window used as Wayland transient parent for the usage panel."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.resize(1, 1)


def tray_anchor_rect(tray: QSystemTrayIcon) -> QRect:
    geo = tray.geometry()
    if geo.isValid() and geo.width() > 0 and geo.height() > 0:
        return geo

    screen = QApplication.primaryScreen()
    if screen is None:
        return QRect(100, 100, 1, 1)

    available = screen.availableGeometry()
    # Top panel on most Linux desktops — anchor near the right status area.
    return QRect(available.right() - 48, available.top() + 4, 24, 24)


def panel_origin(tray: QSystemTrayIcon, panel_width: int) -> QPoint:
    anchor = tray_anchor_rect(tray)
    x = anchor.x() + max(0, (anchor.width() - panel_width) // 2)
    y = anchor.y() + anchor.height() + 8
    return QPoint(x, y)


def bind_transient_parent(panel: QWidget, anchor: QWidget) -> None:
    app = QApplication.instance()
    if app is not None:
        app.processEvents()

    panel_handle = panel.windowHandle()
    anchor_handle = anchor.windowHandle()
    if panel_handle is None or anchor_handle is None:
        return
    panel_handle.setTransientParent(anchor_handle)