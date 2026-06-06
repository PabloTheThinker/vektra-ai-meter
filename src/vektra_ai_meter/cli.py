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
        sync_autostart(enabled=enabled)
    else:
        sync_autostart()
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


def cmd_reboot(_args: argparse.Namespace) -> int:
    from .autostart import reboot_panel

    print("Restarting Vektra AI Meter...")
    status = reboot_panel()
    if status.running:
        print(f"Done. Running (pid {status.pid}). Check your top-bar status area.")
        return 0
    print(
        "Restart issued but the panel is not running yet. "
        "Try: ai-meter status",
        file=sys.stderr,
    )
    return 1


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
    reboot.set_defaults(func=cmd_reboot)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())