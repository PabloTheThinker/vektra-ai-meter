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
    return (
        "[Unit]\n"
        "Description=Vektra AI Meter — AI usage in the top bar\n"
        "After=graphical-session.target\n"
        "PartOf=graphical-session.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={exec_path} run\n"
        "Restart=on-failure\n"
        "RestartSec=8\n"
        "\n"
        "[Install]\n"
        "WantedBy=graphical-session.target\n"
    )


def sync_autostart(*, enabled: bool | None = None) -> bool:
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


def _find_running_pid() -> int | None:
    meter = venv_ai_meter()
    patterns = [str(ai_meter_bin())]
    if meter.is_file() and meter != ai_meter_bin():
        patterns.append(str(meter))

    for pattern in patterns:
        result = subprocess.run(
            ["pgrep", "-f", f"{pattern} run"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
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
    )


def status_dict() -> dict:
    status = service_status()
    return {
        "running": status.running,
        "pid": status.pid,
        "autostart": status.autostart,
        "desktop_entry": status.desktop_entry,
        "systemd_unit": status.systemd_unit,
        "systemd_active": status.systemd_active,
        "version": status.version,
        "lock_file": str(lock_path()),
        "desktop_path": str(autostart_desktop_path()),
        "systemd_path": str(systemd_unit_path()),
    }


def _stop_panel() -> None:
    meter = venv_ai_meter()
    patterns = [str(ai_meter_bin())]
    if meter.is_file() and meter != ai_meter_bin():
        patterns.append(str(meter))

    for pattern in patterns:
        subprocess.run(["pkill", "-f", f"{pattern} run"], check=False)

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
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def reboot_panel(*, wait: bool = True) -> ServiceStatus:
    """Stop and restart the top-bar indicator."""
    had_systemd = systemd_unit_path().is_file() and _systemctl_available()

    if had_systemd:
        subprocess.run(
            ["systemctl", "--user", "restart", "vektra-ai-meter.service"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        _stop_panel()
        time.sleep(0.3)
        _start_panel()

    if wait:
        for _ in range(20):
            status = service_status()
            if status.running:
                return status
            time.sleep(0.25)

    return service_status()


def ensure_running_or_exit() -> IO[str]:
    """Single-instance guard for `ai-meter run`."""
    lock = acquire_instance_lock()
    if lock is not None:
        sync_autostart()
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
    sync_autostart()
    return lock