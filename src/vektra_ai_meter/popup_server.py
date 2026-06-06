from __future__ import annotations

import os
import socket
import sys
import threading
from pathlib import Path

from .ipc import PID_PATH, SOCKET_PATH
from .layershell import layer_shell_available, preload_layer_shell

preload_layer_shell()


def _socket_listener(app_popup, stop_event: threading.Event) -> None:
    if SOCKET_PATH.exists():
        try:
            SOCKET_PATH.unlink()
        except OSError:
            pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(SOCKET_PATH))
    server.listen(5)
    server.settimeout(0.5)

    while not stop_event.is_set():
        try:
            conn, _addr = server.accept()
        except (TimeoutError, socket.timeout):
            continue
        except OSError:
            break
        try:
            data = conn.recv(128).decode("utf-8", errors="ignore").strip()
            parts = data.split()
            cmd = parts[0].lower() if parts else ""
            if cmd == "toggle":
                app_popup.schedule_toggle()
            elif cmd == "show":
                tray_rect = None
                screen_rect = None
                if len(parts) >= 9:
                    try:
                        nums = [int(value) for value in parts[1:9]]
                        tray_rect = (nums[0], nums[1], nums[2], nums[3])
                        screen_rect = (nums[4], nums[5], nums[6], nums[7])
                    except ValueError:
                        tray_rect = None
                        screen_rect = None
                app_popup.schedule_show(tray_rect, screen_rect)
            elif cmd == "hide":
                app_popup.schedule_hide()
            elif cmd == "refresh":
                app_popup.schedule_refresh()
        finally:
            conn.close()

    server.close()
    try:
        SOCKET_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def run_popup_server() -> int:
    if not layer_shell_available():
        print(
            "Integrated top-bar popup requires gtk4-layer-shell.\n"
            "Re-run: curl -fsSL https://vektraindustries.com/ai-tracker/install | bash",
            file=sys.stderr,
        )
        return 1

    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk  # noqa: E402

    from .ui.gtk_popup import IntegratedPopup  # noqa: E402

    class PopupApp(Gtk.Application):
        def __init__(self) -> None:
            super().__init__(application_id="com.vektraindustries.ai-meter.popup")
            self.popup = IntegratedPopup(self)
            self._stop = threading.Event()

        def schedule_toggle(self) -> None:
            GLib.idle_add(self._toggle)

        def schedule_show(
            self,
            tray_rect: tuple[int, int, int, int] | None = None,
            screen_rect: tuple[int, int, int, int] | None = None,
        ) -> None:
            GLib.idle_add(self._show, tray_rect, screen_rect)

        def _show(
            self,
            tray_rect: tuple[int, int, int, int] | None,
            screen_rect: tuple[int, int, int, int] | None,
        ) -> bool:
            self.popup.show(tray_rect=tray_rect, screen_rect=screen_rect)
            return False

        def schedule_hide(self) -> None:
            GLib.idle_add(self.popup.hide)

        def schedule_refresh(self) -> None:
            GLib.idle_add(self._refresh_if_visible)

        def _refresh_if_visible(self) -> bool:
            if self.popup.visible:
                self.popup.refresh()
            return False

        def do_activate(self) -> None:  # noqa: N802
            # Stay alive when every layer-shell surface is hidden (click-away / close).
            self.hold()

            if self.popup.window is None:
                self.popup.build()

            PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
            listener = threading.Thread(
                target=_socket_listener,
                args=(self, self._stop),
                daemon=True,
            )
            listener.start()

        def _toggle(self) -> bool:
            self.popup.toggle()
            return False

        def do_shutdown(self) -> None:  # noqa: N802
            self._stop.set()
            try:
                PID_PATH.unlink(missing_ok=True)
            except OSError:
                pass
            Gtk.Application.do_shutdown(self)

    app = PopupApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(run_popup_server())