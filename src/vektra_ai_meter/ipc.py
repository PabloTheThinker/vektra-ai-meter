from __future__ import annotations

import socket
from pathlib import Path

from .util import data_dir

SOCKET_PATH = data_dir() / "popup.sock"
PID_PATH = data_dir() / "popup.pid"


def send_command(command: str) -> bool:
    path = SOCKET_PATH
    if not path.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(1.5)
            client.connect(str(path))
            client.sendall(f"{command.strip()}\n".encode("utf-8"))
            return True
    except OSError:
        return False


def popup_server_running() -> bool:
    if not PID_PATH.exists():
        return SOCKET_PATH.exists()
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return SOCKET_PATH.exists()
    try:
        import os

        os.kill(pid, 0)
        return True
    except OSError:
        return False


def toggle_popup() -> bool:
    return send_command("toggle")


def show_popup() -> bool:
    return send_command("show")


def hide_popup() -> bool:
    return send_command("hide")


def refresh_popup() -> bool:
    return send_command("refresh")