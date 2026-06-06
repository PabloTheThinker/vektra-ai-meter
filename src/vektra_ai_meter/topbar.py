"""Panel top-bar indicator using Qt (PySide6) — no system GTK/AppIndicator deps."""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .snapshot import write_snapshot
from .util import fmt_tokens

REFRESH_MS = 20_000


def _compact_label(snapshot: dict) -> str:
    summary = snapshot.get("summary") or {}
    total = summary.get("total_tokens_fmt", "—")
    active = summary.get("active_sessions", 0)
    return f"{total} · {active} active"


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

        icon = QIcon.fromTheme("utilities-system-monitor")
        if icon.isNull():
            icon = QIcon.fromTheme("dialog-information")

        self.tray = QSystemTrayIcon(icon)
        self.tray.setToolTip("Vektra AI Meter")
        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)

        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh)
        self.timer.start(REFRESH_MS)
        self._refresh()

        self.tray.show()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.menu.popup(self.tray.geometry().center())

    def _refresh(self) -> None:
        snapshot = write_snapshot()
        label = _compact_label(snapshot)
        self.tray.setToolTip(f"Vektra AI Meter\n{label}")
        self._rebuild_menu(snapshot)

    def _rebuild_menu(self, snapshot: dict) -> None:
        self.menu.clear()

        summary = snapshot.get("summary") or {}
        header = QAction(
            f"Total {summary.get('total_tokens_fmt', '—')} · "
            f"{summary.get('active_sessions', 0)} active",
            self.menu,
        )
        header.setEnabled(False)
        self.menu.addAction(header)
        self.menu.addSeparator()

        for provider in snapshot.get("providers") or []:
            parts = [f"{provider.get('label')}: {fmt_tokens(provider.get('total_tokens'))}"]
            if provider.get("rate_primary") and provider["rate_primary"] != "—":
                parts.append(f"5h {provider['rate_primary']}")
            if provider.get("active_sessions"):
                parts.append(f"{provider['active_sessions']} active")
            item = QAction(" · ".join(parts), self.menu)
            item.setEnabled(False)
            self.menu.addAction(item)

        self.menu.addSeparator()
        refresh = QAction("Refresh now", self.menu)
        refresh.triggered.connect(self._refresh)
        self.menu.addAction(refresh)

        quit_action = QAction("Quit", self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)

    def run(self) -> int:
        return self.app.exec()


def main() -> int:
    return TopBarIndicator().run()


if __name__ == "__main__":
    raise SystemExit(main())