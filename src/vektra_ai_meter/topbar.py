"""Panel top-bar indicator using Qt (PySide6) — no system GTK/AppIndicator deps."""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .autostart import ensure_running_or_exit
from .snapshot import write_snapshot
from .ui.icon import make_tray_icon
from .ui.panel import UsagePanel
from .ui.wayland import ClickAwayFilter

REFRESH_MS = 15_000


def _rich_tooltip(snapshot: dict) -> str:
    lines = ["Vektra AI Meter"]
    summary = snapshot.get("summary") or {}
    highlights = summary.get("highlights") or []
    if highlights:
        lines.extend(highlights)
    else:
        for provider in snapshot.get("providers") or []:
            limits = provider.get("limits") or []
            parts: list[str] = []
            for limit in limits:
                used = limit.get("used_percent")
                if used is None or limit.get("label") == "Session":
                    continue
                label = limit.get("label") or "Limit"
                parts.append(f"{label} {used:.0f}%")
            if parts:
                lines.append(f"{provider.get('label', provider.get('id'))}: {' · '.join(parts)}")
            elif provider.get("sessions", 0) > 0:
                tokens = provider.get("total_tokens_fmt")
                if tokens:
                    lines.append(f"{provider.get('label')}: {tokens} logged (no quota data)")

    peak = summary.get("peak_percent_fmt")
    peak_label = summary.get("peak_label")
    if peak and peak != "—" and peak_label:
        lines.append(f"Peak: {peak_label} {peak}")
    return "\n".join(lines)


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
        self._lock = ensure_running_or_exit()

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
        self.panel.quit_requested.connect(self._quit)
        self._click_away = ClickAwayFilter(self.panel, self.tray)

        self.tray.activated.connect(self._on_activated)

        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh)
        self.timer.start(REFRESH_MS)
        self._refresh()

        self.tray.setIcon(make_tray_icon())
        self.tray.show()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason not in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.Context,
        ):
            return
        if self.panel.isVisible():
            self.panel.hide()
        else:
            self.panel.popup_near_tray(self.tray)

    def _refresh(self) -> None:
        snapshot = write_snapshot()
        self.tray.setToolTip(_rich_tooltip(snapshot))
        self.tray.setIcon(make_tray_icon(_icon_bars(snapshot)))
        self.panel.set_snapshot(snapshot)

    def _quit(self) -> None:
        self.panel.hide()
        self.tray.hide()
        self.app.quit()

    def run(self) -> int:
        return self.app.exec()


def main() -> int:
    return TopBarIndicator().run()


if __name__ == "__main__":
    raise SystemExit(main())