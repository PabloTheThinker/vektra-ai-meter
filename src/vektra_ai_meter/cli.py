from __future__ import annotations

import argparse
import json
import sys

from .config import Config
from .snapshot import build_snapshot, write_snapshot
from .util import snapshot_path


def cmd_snapshot(args: argparse.Namespace) -> int:
    snapshot = write_snapshot() if args.write else build_snapshot()
    if args.pretty:
        print(json.dumps(snapshot, indent=2, default=str))
    else:
        print(json.dumps(snapshot, default=str))
    if args.write:
        print(snapshot_path(), file=sys.stderr)
    return 0


def cmd_topbar(_args: argparse.Namespace) -> int:
    from .topbar import main as topbar_main

    return topbar_main()


def cmd_run(_args: argparse.Namespace) -> int:
    return cmd_topbar(_args)


def cmd_config(args: argparse.Namespace) -> int:
    from .autostart import sync_autostart

    config = Config().load()
    if args.autostart is not None:
        enabled = args.autostart == "true"
        sync_autostart(enabled=enabled, activate=True)
    else:
        sync_autostart(activate=True)
    config = Config().load()
    print(
        json.dumps(
            {"autostart": config.autostart, "path": str(config.path)},
            indent=2,
        )
    )
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    from .autostart import status_dict

    print(json.dumps(status_dict(), indent=2))
    return 0


def cmd_print(_args: argparse.Namespace) -> int:
    path = snapshot_path()
    if not path.exists():
        write_snapshot()
    print(path.read_text(encoding="utf-8"))
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    from .update import run_update

    return run_update(restart=not args.no_restart)


def cmd_popup_server(_args: argparse.Namespace) -> int:
    import os

    from .gtk_launch import (
        POPUP_SERVER_BOOT,
        _python_has_gi,
        gtk_python_available,
        gtk_python_executable,
        popup_server_env,
    )

    if not gtk_python_available():
        print(
            "python3-gi is required for the integrated dropdown.\n"
            "Install: sudo apt install python3-gi gir1.2-gtk-4.0",
            file=sys.stderr,
        )
        return 1

    if not _python_has_gi(sys.executable):
        executable = gtk_python_executable()
        if executable is not None:
            os.execve(
                str(executable),
                [str(executable), "-c", POPUP_SERVER_BOOT],
                popup_server_env(),
            )

    from .popup_server import run_popup_server

    return run_popup_server()


def cmd_integrate(args: argparse.Namespace) -> int:
    from .integrate import run_integrate

    return run_integrate(build=args.build, force=args.force)


def cmd_reboot(args: argparse.Namespace) -> int:
    from .autostart import reboot_panel
    from .integrate import integration_status

    if not args.no_wait:
        print("Restarting Vektra AI Meter...")
    status = reboot_panel(wait=not args.no_wait)
    if args.no_wait:
        return 0

    if not status.running:
        print(
            "Restart issued but the panel is not running yet. "
            "Try: ai-meter status",
            file=sys.stderr,
        )
        return 1

    lines = [f"Done. Tray running (pid {status.pid})."]
    if integration_status()["integrated_popup"]:
        if status.popup_server_running:
            lines.append("Integrated dropdown server is up.")
        else:
            lines.append(
                "Tray is up but the integrated dropdown server is still starting — "
                "click the tray icon in a few seconds."
            )
    print(" ".join(lines))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Vektra AI Meter for Linux")
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="Build usage snapshot JSON")
    snap.add_argument(
        "--write",
        action="store_true",
        help="Write ~/.local/share/vektra-ai-meter/snapshot.json",
    )
    snap.add_argument("--pretty", action="store_true")
    snap.set_defaults(func=cmd_snapshot)

    run = sub.add_parser("run", help="Launch the panel top-bar indicator")
    run.set_defaults(func=cmd_run)

    topbar = sub.add_parser("topbar", help="Launch the panel top-bar indicator")
    topbar.set_defaults(func=cmd_topbar)

    cfg = sub.add_parser("config", help="View or update settings")
    cfg.add_argument("--autostart", choices=["true", "false"])
    cfg.set_defaults(func=cmd_config)

    status = sub.add_parser("status", help="Show panel process and autostart state")
    status.set_defaults(func=cmd_status)

    show = sub.add_parser("print", help="Print cached snapshot JSON")
    show.set_defaults(func=cmd_print)

    upd = sub.add_parser("update", help="Pull latest release and upgrade the install")
    upd.add_argument(
        "--no-restart",
        action="store_true",
        help="Skip restarting the panel indicator after update",
    )
    upd.set_defaults(func=cmd_update)

    reboot = sub.add_parser("reboot", help="Restart the panel top-bar indicator")
    reboot.add_argument(
        "--no-wait",
        action="store_true",
        help="Restart in the background and exit immediately (used by install/update)",
    )
    reboot.set_defaults(func=cmd_reboot)

    popup = sub.add_parser(
        "popup-server",
        help="GTK4 layer-shell integrated dropdown (internal)",
    )
    popup.set_defaults(func=cmd_popup_server)

    integrate = sub.add_parser(
        "integrate",
        help="Set up GTK4 layer-shell integrated top-bar dropdown (Wayland)",
    )
    integrate.add_argument(
        "--build",
        action="store_true",
        help="Build gtk4-layer-shell into ~/.local when dependencies are installed",
    )
    integrate.add_argument(
        "--force",
        action="store_true",
        help="Rebuild gtk4-layer-shell even if already present",
    )
    integrate.set_defaults(func=cmd_integrate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())