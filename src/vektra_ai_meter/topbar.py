"""Panel top-bar indicator using Qt (PySide6) — no system GTK/AppIndicator deps."""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .snapshot import write_snapshot
from .ui.icon import make_tray_icon
from .ui.panel import UsagePanel

REFRESH_MS = 15_000


def _compact_label(snapshot: dict) -> str:
    summary = snapshot.get("summary") or {}
    peak = summary.get("peak_percent_fmt")
    if peak and peak != "—":
        peak_label = summary.get("peak_label")
        if peak_label:
            return f"{peak_label} {peak}"
        return f"Peak {peak}"

    total = summary.get("total_tokens_fmt", "—")
    active = summary.get("active_sessions", 0)
    return f"{total} · {active} active"


def _icon_bars(snapshot: dict) -> list[float | None]:
    bars: list[float | None] = []
    for provider in snapshot.get("providers") or []:
        peak: float | None = None
        for limit in provider.get("limits") or []:
            used = limit.get("used_percent")
            if used is None or limit.get("label") == "Session":
                continue
            value = float(used)
            peak = value if peak is None else max(peak, value)
        bars.append(peak)
    while len(bars) < 3:
        bars.append(None)
    return bars[:4]


class TopBarIndicator:
    def __init__(self) -> None:
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Vektra AI Meter")
        self.app.setQuitOnLastWindowClosed(False)

        if not QSystemTrayIcon.isSystemTrayAvailable():
            print(
                "System tray is not available on this desktop. "
                "Enable the status area / tray applet in your panel settings.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        self.tray = QSystemTrayIcon()
        self.tray.setToolTip("Vektra AI Meter")

        self.panel = UsagePanel()
        self.panel.refresh_requested.connect(self._refresh)
        self.panel.quit_requested.connect(self.app.quit)

        self.fallback_menu = QMenu()
        refresh_action = QAction("Refresh now", self.fallback_menu)
        refresh_action.triggered.connect(self._refresh)
        self.fallback_menu.addAction(refresh_action)
        quit_action = QAction("Quit", self.fallback_menu)
        quit_action.triggered.connect(self.app.quit)
        self.fallback_menu.addAction(quit_action)
        self.tray.setContextMenu(self.fallback_menu)

        self.tray.activated.connect(self._on_activated)

        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh)
        self.timer.start(REFRESH_MS)
        self._refresh()

        self.tray.setIcon(make_tray_icon())
        self.tray.show()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.Context,
        ):
            if self.panel.isVisible():
                self.panel.hide()
            else:
                self.panel.popup_near_tray(self.tray)

    def _refresh(self) -> None:
        snapshot = write_snapshot()
        label = _compact_label(snapshot)
        self.tray.setToolTip(f"Vektra AI Meter\n{label}")
        self.tray.setIcon(make_tray_icon(_icon_bars(snapshot)))
        self.panel.set_snapshot(snapshot)

    def run(self) -> int:
        return self.app.exec()


def main() -> int:
    return TopBarIndicator().run()


if __name__ == "__main__":
    raise SystemExit(main())