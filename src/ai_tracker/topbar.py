#!/usr/bin/env python3
"""Panel top-bar indicator via Ayatana AppIndicator (COSMIC, GNOME, Xfce, etc.)."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
from gi.repository import GLib, Gtk  # noqa: E402

from .snapshot import write_snapshot
from .util import fmt_tokens

REFRESH_SECONDS = 20
INDICATOR_ID = "vektra-ai-meter"


def _compact_label(snapshot: dict) -> str:
    summary = snapshot.get("summary") or {}
    total = summary.get("total_tokens_fmt", "—")
    active = summary.get("active_sessions", 0)
    return f"{total} · {active} active"


class TopBarIndicator:
    def __init__(self) -> None:
        self.indicator = AppIndicator.Indicator.new(
            INDICATOR_ID,
            "utilities-system-monitor",
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_title("Vektra AI Meter")
        self.menu = Gtk.Menu()
        self.indicator.set_menu(self.menu)
        GLib.timeout_add_seconds(REFRESH_SECONDS, self._on_refresh)
        self._on_refresh()

    def _on_refresh(self, *_args) -> bool:
        snapshot = write_snapshot()
        self.indicator.set_label(_compact_label(snapshot), "Vektra AI Meter")
        self._rebuild_menu(snapshot)
        return True

    def _rebuild_menu(self, snapshot: dict) -> None:
        for child in self.menu.get_children():
            self.menu.remove(child)

        summary = snapshot.get("summary") or {}
        header = Gtk.MenuItem(
            label=f"Total {summary.get('total_tokens_fmt', '—')} · "
            f"{summary.get('active_sessions', 0)} active"
        )
        header.set_sensitive(False)
        self.menu.append(header)
        self.menu.append(Gtk.SeparatorMenuItem())

        for provider in snapshot.get("providers") or []:
            parts = [f"{provider.get('label')}: {fmt_tokens(provider.get('total_tokens'))}"]
            if provider.get("rate_primary") and provider["rate_primary"] != "—":
                parts.append(f"5h {provider['rate_primary']}")
            if provider.get("active_sessions"):
                parts.append(f"{provider['active_sessions']} active")
            item = Gtk.MenuItem(label=" · ".join(parts))
            item.set_sensitive(False)
            self.menu.append(item)

        self.menu.append(Gtk.SeparatorMenuItem())
        refresh = Gtk.MenuItem(label="Refresh now")
        refresh.connect("activate", lambda *_: self._on_refresh())
        self.menu.append(refresh)

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda *_: Gtk.main_quit())
        self.menu.append(quit_item)

        self.menu.show_all()

    def run(self) -> int:
        Gtk.main()
        return 0


def main() -> int:
    return TopBarIndicator().run()


if __name__ == "__main__":
    raise SystemExit(main())