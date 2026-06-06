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


def _socket_responsive() -> bool:
    if not SOCKET_PATH.exists():
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(0.4)
            client.connect(str(SOCKET_PATH))
            client.sendall(b"refresh\n")
            return True
    except OSError:
        return False


def _pid_alive(pid: int) -> bool:
    try:
        import os

        os.kill(pid, 0)
    except OSError:
        return False

    try:
        stat = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8")
        state = stat.split(")", 1)[1].split()[0]
        if state == "Z":
            return False
    except (OSError, IndexError):
        pass
    return True


def popup_server_running() -> bool:
    if not PID_PATH.exists():
        return _socket_responsive()
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return _socket_responsive()
    if not _pid_alive(pid):
        return False
    return _socket_responsive()


def toggle_popup() -> bool:
    return send_command("toggle")


def show_popup() -> bool:
    return send_command("show")


def hide_popup() -> bool:
    return send_command("hide")


def refresh_popup() -> bool:
    return send_command("refresh")