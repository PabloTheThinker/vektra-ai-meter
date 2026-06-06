from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from .config import Config
from .paths import venv_ai_meter
from .util import data_dir


@dataclass
class ServiceStatus:
    running: bool
    pid: int | None
    autostart: bool
    desktop_entry: bool
    systemd_unit: bool
    systemd_active: bool
    version: str | None
    popup_server_running: bool = False


def lock_path() -> Path:
    return data_dir() / "ai-meter.lock"


def autostart_desktop_path() -> Path:
    return Path.home() / ".config" / "autostart" / "vektra-ai-meter.desktop"


def systemd_unit_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / "vektra-ai-meter.service"


def ai_meter_bin() -> Path:
    user_bin = Path.home() / ".local" / "bin" / "ai-meter"
    if user_bin.is_file():
        return user_bin
    return venv_ai_meter()


def _desktop_content(*, enabled: bool) -> str:
    exec_path = ai_meter_bin()
    hidden = "true" if not enabled else "false"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Vektra AI Meter\n"
        "Comment=Top-bar AI usage meter for Grok, Codex, and Claude\n"
        f"Exec={exec_path} run\n"
        "Icon=utilities-system-monitor\n"
        "Terminal=false\n"
        f"Hidden={hidden}\n"
        "Categories=Utility;\n"
        "StartupNotify=false\n"
        "X-GNOME-Autostart-enabled=true\n"
        "X-GNOME-Autostart-Delay=3\n"
    )


def _systemd_content() -> str:
    exec_path = ai_meter_bin()
    local = Path.home() / ".local"
    return (
        "[Unit]\n"
        "Description=Vektra AI Meter — AI usage in the top bar\n"
        "After=graphical-session.target\n"
        "PartOf=graphical-session.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={exec_path} run\n"
        f"Environment=LD_LIBRARY_PATH={local}/lib\n"
        f"Environment=GI_TYPELIB_PATH={local}/lib/girepository-1.0\n"
        "Environment=VEKTRA_TOP_BAR_HEIGHT=36\n"
        "Restart=on-failure\n"
        "RestartSec=8\n"
        "\n"
        "[Install]\n"
        "WantedBy=graphical-session.target\n"
    )


def _panel_env() -> dict[str, str]:
    from .gtk_launch import gtk_env

    return gtk_env()


def sync_autostart(*, enabled: bool | None = None, activate: bool = False) -> bool:
    """Write desktop + systemd autostart entries. Returns effective enabled state."""
    config = Config().load()
    if enabled is None:
        enabled = config.autostart
    else:
        config.autostart = enabled
        config.save()

    desktop_path = autostart_desktop_path()
    desktop_path.parent.mkdir(parents=True, exist_ok=True)
    desktop_path.write_text(_desktop_content(enabled=enabled), encoding="utf-8")

    unit_path = systemd_unit_path()
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(_systemd_content(), encoding="utf-8")

    if _systemctl_available():
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if activate:
            if enabled:
                subprocess.run(
                    ["systemctl", "--user", "enable", "--now", "vektra-ai-meter.service"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.run(
                    ["systemctl", "--user", "disable", "--now", "vektra-ai-meter.service"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
    return enabled


def _systemctl_available() -> bool:
    try:
        subprocess.run(
            ["systemctl", "--user", "status"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _systemd_active() -> bool:
    if not _systemctl_available():
        return False
    result = subprocess.run(
        ["systemctl", "--user", "is-active", "vektra-ai-meter.service"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() == "active"


def _run_process_patterns() -> list[str]:
    meter = venv_ai_meter()
    patterns = [
        str(ai_meter_bin()),
        str(meter),
        "vektra_ai_meter",
    ]
    unique: list[str] = []
    for pattern in patterns:
        if pattern and pattern not in unique:
            unique.append(pattern)
    return unique


def _find_running_pid() -> int | None:
    for pattern in _run_process_patterns():
        result = subprocess.run(
            ["pgrep", "-f", f"{pattern}.* run"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            try:
                pid = int(line.strip())
            except ValueError:
                continue
            if pid != os.getpid():
                return pid
    return None


def acquire_instance_lock() -> IO[str] | None:
    """Return an open lock handle, or None if another instance is running."""
    path = lock_path()
    handle = open(path, "w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def service_status() -> ServiceStatus:
    from .ipc import popup_server_running

    config = Config().load()
    version: str | None = None
    try:
        import importlib.metadata

        version = importlib.metadata.version("vektra-ai-meter")
    except Exception:
        pass

    pid = _find_running_pid()
    return ServiceStatus(
        running=pid is not None,
        pid=pid,
        autostart=config.autostart,
        desktop_entry=autostart_desktop_path().is_file(),
        systemd_unit=systemd_unit_path().is_file(),
        systemd_active=_systemd_active(),
        version=version,
        popup_server_running=popup_server_running(),
    )


def status_dict() -> dict:
    from .integrate import integration_status
    from .ipc import popup_server_running

    status = service_status()
    integration = integration_status()
    return {
        "running": status.running,
        "pid": status.pid,
        "autostart": status.autostart,
        "desktop_entry": status.desktop_entry,
        "systemd_unit": status.systemd_unit,
        "systemd_active": status.systemd_active,
        "version": status.version,
        "integrated_popup": integration["integrated_popup"],
        "popup_server_running": popup_server_running(),
        "layer_shell_lib": integration["layer_shell_lib"],
        "integration": integration,
        "lock_file": str(lock_path()),
        "desktop_path": str(autostart_desktop_path()),
        "systemd_path": str(systemd_unit_path()),
    }


def _popup_server_patterns() -> list[str]:
    return [
        "vektra_ai_meter.popup_server",
        "ai-meter popup-server",
        f"{ai_meter_bin()} popup-server",
        "run_popup_server()",
    ]


def _stop_popup_server() -> None:
    from .ipc import PID_PATH, SOCKET_PATH

    if PID_PATH.exists():
        try:
            pid = int(PID_PATH.read_text(encoding="utf-8").strip())
            os.kill(pid, 15)
            time.sleep(0.15)
        except (OSError, ValueError):
            pass

    for pattern in _popup_server_patterns():
        subprocess.run(["pkill", "-f", pattern], check=False)

    try:
        PID_PATH.unlink(missing_ok=True)
        SOCKET_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def _stop_panel() -> None:
    for pattern in _run_process_patterns():
        subprocess.run(["pkill", "-f", f"{pattern}.* run"], check=False)

    _stop_popup_server()

    try:
        lock_path().unlink(missing_ok=True)
    except OSError:
        pass


def _start_panel() -> None:
    launcher = ai_meter_bin()
    if not launcher.is_file():
        return
    subprocess.Popen(
        [str(launcher), "run"],
        env=_panel_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _wait_for_stop(*, timeout_s: float = 5.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _find_running_pid() is None:
            return True
        time.sleep(0.15)
    return _find_running_pid() is None


def _wait_for_start(*, old_pid: int | None = None, timeout_s: float = 10.0) -> ServiceStatus:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = service_status()
        if status.running and (old_pid is None or status.pid != old_pid):
            return status
        time.sleep(0.25)
    return service_status()


def _wait_for_popup_server(*, timeout_s: float = 8.0) -> bool:
    from .ipc import popup_server_running

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if popup_server_running():
            return True
        time.sleep(0.25)
    return popup_server_running()


def reboot_panel(*, wait: bool = True) -> ServiceStatus:
    """Stop and restart the top-bar indicator."""
    from .integrate import integration_status

    old_pid = _find_running_pid()
    use_systemd = systemd_unit_path().is_file() and _systemctl_available()
    want_popup = integration_status()["integrated_popup"]

    _stop_panel()
    _wait_for_stop()

    if use_systemd:
        subprocess.run(
            ["systemctl", "--user", "stop", "vektra-ai-meter.service"],
            check=False,
            capture_output=True,
            text=True,
        )
        _wait_for_stop()
        result = subprocess.run(
            ["systemctl", "--user", "start", "vektra-ai-meter.service"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            print(f"systemd start failed: {detail}", file=sys.stderr)
            _start_panel()
    else:
        time.sleep(0.2)
        _start_panel()

    if wait:
        status = _wait_for_start(old_pid=old_pid)
        if want_popup and status.running:
            _wait_for_popup_server()
            status = service_status()
        return status
    return service_status()


def ensure_running_or_exit() -> IO[str]:
    """Single-instance guard for `ai-meter run`."""
    lock = acquire_instance_lock()
    if lock is not None:
        sync_autostart(activate=False)
        return lock

    status = service_status()
    if status.running:
        print(
            f"Vektra AI Meter is already running (pid {status.pid}). "
            "Check your top-bar status area.",
            file=sys.stderr,
        )
        raise SystemExit(0)

    print(
        "Another ai-meter instance holds the lock but no process was found. "
        "Removing stale lock and starting…",
        file=sys.stderr,
    )
    try:
        lock_path().unlink(missing_ok=True)
    except OSError:
        pass
    lock = acquire_instance_lock()
    if lock is None:
        print("Failed to acquire instance lock.", file=sys.stderr)
        raise SystemExit(1)
    sync_autostart(activate=False)
    return lock