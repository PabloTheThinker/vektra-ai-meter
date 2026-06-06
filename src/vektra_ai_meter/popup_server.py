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
            data = conn.recv(64).decode("utf-8", errors="ignore").strip().lower()
            if data == "toggle":
                app_popup.schedule_toggle()
            elif data == "show":
                app_popup.schedule_show()
            elif data == "hide":
                app_popup.schedule_hide()
            elif data == "refresh":
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

        def schedule_show(self) -> None:
            GLib.idle_add(self.popup.show)

        def schedule_hide(self) -> None:
            GLib.idle_add(self.popup.hide)

        def schedule_refresh(self) -> None:
            GLib.idle_add(self._refresh_if_visible)

        def _refresh_if_visible(self) -> bool:
            if self.popup.visible:
                self.popup.refresh()
            return False

        def do_activate(self) -> None:  # noqa: N802
            if self.popup.window is None:
                self.popup.build()
                self.popup.window.set_visible(False)

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