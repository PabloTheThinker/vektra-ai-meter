"""Panel top-bar indicator using Qt tray + GTK4 layer-shell integrated popup."""

from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .autostart import ensure_running_or_exit
from .gtk_launch import popup_server_argv, popup_server_env
from .ipc import PID_PATH, SOCKET_PATH, popup_server_running, refresh_popup, show_popup
from .layershell import layer_shell_available
from .paths import venv_ai_meter
from .snapshot import write_snapshot
from .ui.icon import make_tray_icon
from .ui.panel import UsagePanel
from .ui.wayland import ClickAwayFilter, is_wayland, screen_for_tray, tray_anchor_rect
from .util import snapshot_display_digest

REFRESH_MS = 15_000
FOOTER_TICK_MS = 1_000


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


def _launcher() -> Path:
    user = Path.home() / ".local" / "bin" / "ai-meter"
    if user.is_file():
        return user
    return venv_ai_meter()


def _integrated_mode() -> bool:
    return is_wayland() and layer_shell_available()


class SnapshotSignals(QObject):
    finished = Signal(dict)
    failed = Signal(str)


class SnapshotTask(QRunnable):
    def __init__(self, signals: SnapshotSignals) -> None:
        super().__init__()
        self.signals = signals

    def run(self) -> None:
        try:
            self.signals.finished.emit(write_snapshot())
        except Exception as exc:  # noqa: BLE001 — surface collector failures in tray tooltip
            self.signals.failed.emit(str(exc))


class TopBarIndicator:
    def __init__(self) -> None:
        self._lock = ensure_running_or_exit()
        self.integrated = _integrated_mode()

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

        self.panel: UsagePanel | None = None
        self._click_away: ClickAwayFilter | None = None
        if self.integrated:
            self._ensure_popup_server()
        else:
            self.panel = UsagePanel()
            self.panel.refresh_requested.connect(self._refresh)
            self._click_away = ClickAwayFilter(self.panel, self.tray)

        self.tray.activated.connect(self._on_activated)

        self._refreshing = False
        self._last_snapshot: dict | None = None
        self._last_digest: str | None = None
        self._pool = QThreadPool.globalInstance()
        self._signals = SnapshotSignals()
        self._signals.finished.connect(self._apply_snapshot)
        self._signals.failed.connect(self._on_refresh_failed)

        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh)
        self.timer.start(REFRESH_MS)

        self.footer_timer = QTimer()
        self.footer_timer.timeout.connect(self._tick_footer)
        self.footer_timer.start(FOOTER_TICK_MS)

        self._refresh()

        self.tray.setIcon(make_tray_icon())
        self.tray.show()

        self._install_signal_handlers()

    def _popup_show_geometry(self) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
        anchor = tray_anchor_rect(self.tray)
        screen = screen_for_tray(self.tray)
        if screen is None:
            return (
                (anchor.x(), anchor.y(), anchor.width(), anchor.height()),
                (0, 0, 1920, 1080),
            )
        full = screen.geometry()
        return (
            (anchor.x(), anchor.y(), anchor.width(), anchor.height()),
            (full.x(), full.y(), full.width(), full.height()),
        )

    def _ensure_popup_server(self, *, force: bool = False) -> None:
        if not force and popup_server_running():
            return
        if force:
            import os

            try:
                pid = int(PID_PATH.read_text(encoding="utf-8").strip())
                os.kill(pid, 15)
            except (OSError, ValueError, ProcessLookupError):
                pass
            try:
                PID_PATH.unlink(missing_ok=True)
                SOCKET_PATH.unlink(missing_ok=True)
            except OSError:
                pass
        launcher = _launcher()
        if not launcher.is_file():
            return
        subprocess.Popen(
            popup_server_argv(),
            env=popup_server_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        for _ in range(30):
            if popup_server_running():
                return
            time.sleep(0.1)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason not in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.Context,
        ):
            return

        if self.integrated:
            if not popup_server_running():
                self._ensure_popup_server()
            self._refresh()
            tray_rect, screen_rect = self._popup_show_geometry()
            if not show_popup(tray_rect=tray_rect, screen_rect=screen_rect):
                self._ensure_popup_server(force=True)
                time.sleep(0.15)
                show_popup(tray_rect=tray_rect, screen_rect=screen_rect)
            return

        if self.panel is None:
            return
        if self.panel.isVisible():
            self.panel.hide()
        else:
            if self._last_snapshot is not None:
                self.panel.set_snapshot(self._last_snapshot, digest=self._last_digest)
            self.panel.popup_near_tray(self.tray)

    @Slot(str)
    def _on_refresh_failed(self, message: str) -> None:
        self._refreshing = False
        if self.panel is not None:
            self.panel.set_refreshing(False)
        self.tray.setToolTip(f"Vektra AI Meter\nRefresh failed: {message}")

    @Slot(dict)
    def _apply_snapshot(self, snapshot: dict) -> None:
        self._refreshing = False
        self._last_snapshot = snapshot
        digest = snapshot_display_digest(snapshot)
        self._last_digest = digest

        self.tray.setToolTip(_rich_tooltip(snapshot))
        self.tray.setIcon(make_tray_icon(_icon_bars(snapshot)))

        if self.integrated:
            refresh_popup()
        elif self.panel is not None:
            self.panel.set_refreshing(False)
            if self.panel.isVisible():
                self.panel.set_snapshot(snapshot, digest=digest)

    def _tick_footer(self) -> None:
        if self.panel is not None and self.panel.isVisible():
            self.panel.tick_footer()

    def _refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        if self.panel is not None and self.panel.isVisible():
            self.panel.set_refreshing(True)
        self._pool.start(SnapshotTask(self._signals))

    def _install_signal_handlers(self) -> None:
        """Quit cleanly on SIGTERM/SIGINT so the tray icon is unregistered.

        systemd stop / `reboot` / pkill all send SIGTERM. Without this, the process
        dies before Qt hides the QSystemTrayIcon, leaving an orphaned StatusNotifier
        item on the bus — a ghost icon some panels (COSMIC) never prune. We hide the
        tray on aboutToQuit and route the signals into Qt's event loop. A short timer
        keeps the Python interpreter ticking so the handler is actually delivered
        while Qt is in its native loop.
        """
        self.app.aboutToQuit.connect(self._cleanup)
        try:
            signal.signal(signal.SIGTERM, lambda *_: self.app.quit())
            signal.signal(signal.SIGINT, lambda *_: self.app.quit())
        except (ValueError, OSError):
            # Not on the main thread (shouldn't happen here) — skip rather than crash.
            return
        self._signal_wakeup = QTimer()
        self._signal_wakeup.timeout.connect(lambda: None)
        self._signal_wakeup.start(200)

    def _cleanup(self) -> None:
        try:
            self.tray.hide()
        except Exception:  # noqa: BLE001 — best-effort teardown, never block quit
            pass

    def run(self) -> int:
        return self.app.exec()


def main() -> int:
    return TopBarIndicator().run()


if __name__ == "__main__":
    raise SystemExit(main())