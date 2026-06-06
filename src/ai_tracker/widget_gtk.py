#!/usr/bin/env python3
from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from .config import SIZE_PRESETS, WidgetConfig
from .layer_shell import configure_desktop_widget
from .snapshot import write_snapshot
from .util import fmt_tokens

REFRESH_SECONDS = 20

CSS = """
.desktop-widget {
  background-color: rgba(22, 24, 30, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 22px;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.28);
}
.widget-title {
  color: rgba(255, 255, 255, 0.92);
  font-size: 12px;
  font-weight: 700;
}
.widget-subtitle {
  color: rgba(255, 255, 255, 0.48);
  font-size: 10px;
}
.hero-value {
  color: #ffffff;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.03em;
}
.hero-label {
  color: rgba(255, 255, 255, 0.48);
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.stat-chip {
  background-color: rgba(255, 255, 255, 0.06);
  border-radius: 14px;
  padding: 8px 10px;
}
.stat-chip-value {
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
}
.stat-chip-label {
  color: rgba(255, 255, 255, 0.45);
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
}
.provider-card {
  background-color: rgba(255, 255, 255, 0.05);
  border-radius: 16px;
  padding: 10px 12px;
}
.provider-name {
  color: rgba(255, 255, 255, 0.88);
  font-size: 11px;
  font-weight: 600;
}
.provider-meta {
  color: rgba(255, 255, 255, 0.42);
  font-size: 9px;
}
.provider-value {
  color: #ffffff;
  font-size: 12px;
  font-weight: 700;
}
.dot {
  min-width: 8px;
  min-height: 8px;
  border-radius: 999px;
}
.grok-dot { background-color: #f97316; }
.codex-dot { background-color: #10b981; }
.claude-dot { background-color: #c084fc; }
"""


class TrackerWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, config: WidgetConfig) -> None:
        super().__init__(application=app)
        self.config = config
        width, height = SIZE_PRESETS.get(config.size, SIZE_PRESETS["medium"])
        self.set_default_size(width, height)
        self.set_resizable(config.size == "large")
        self.add_css_class("desktop-widget")

        self.set_decorated(False)
        self.set_title("AI Usage")

        self._layer_shell = configure_desktop_widget(self, config.anchor, config.margin)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_margin_top(16)
        root.set_margin_bottom(16)
        root.set_margin_start(16)
        root.set_margin_end(16)
        self.set_child(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_box.set_hexpand(True)
        title = Gtk.Label(label="Vektra AI Meter")
        title.add_css_class("widget-title")
        title.set_halign(Gtk.Align.START)
        subtitle = Gtk.Label(label="Grok · Codex · Claude")
        subtitle.add_css_class("widget-subtitle")
        subtitle.set_halign(Gtk.Align.START)
        title_box.append(title)
        title_box.append(subtitle)
        header.append(title_box)
        root.append(header)

        if config.size == "small":
            self._build_small(root)
        elif config.size == "large":
            self._build_large(root)
        else:
            self._build_medium(root)

        self._setup_drag()
        GLib.timeout_add_seconds(REFRESH_SECONDS, self._on_refresh)
        self._on_refresh()

    def _setup_drag(self) -> None:
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        self._drag_offset_x = 0.0
        self._drag_offset_y = 0.0
        self.add_controller(drag)

    def _on_drag_begin(self, _gesture: Gtk.GestureDrag, _x: float, _y: float) -> None:
        self._drag_offset_x = 0.0
        self._drag_offset_y = 0.0

    def _on_drag_update(self, _gesture: Gtk.GestureDrag, offset_x: float, offset_y: float) -> None:
        if self._layer_shell:
            return
        self._drag_offset_x += offset_x
        self._drag_offset_y += offset_y

    def _build_small(self, root: Gtk.Box) -> None:
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.total_value = Gtk.Label(label="—")
        self.total_value.add_css_class("hero-value")
        self.total_value.set_halign(Gtk.Align.START)
        hero_label = Gtk.Label(label="Total Tokens")
        hero_label.add_css_class("hero-label")
        hero_label.set_halign(Gtk.Align.START)
        hero.append(self.total_value)
        hero.append(hero_label)
        root.append(hero)

        self.provider_rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        root.append(self.provider_rows_box)

    def _build_medium(self, root: Gtk.Box) -> None:
        hero_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.total_value = self._stat_chip(hero_row, "TOTAL")
        self.today_value = self._stat_chip(hero_row, "TODAY")
        self.active_value = self._stat_chip(hero_row, "ACTIVE")
        root.append(hero_row)

        self.provider_rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.append(self.provider_rows_box)

    def _build_large(self, root: Gtk.Box) -> None:
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.total_value = Gtk.Label(label="—")
        self.total_value.add_css_class("hero-value")
        self.total_value.set_halign(Gtk.Align.START)
        total_label = Gtk.Label(label="Total Tokens")
        total_label.add_css_class("hero-label")
        total_label.set_halign(Gtk.Align.START)
        hero.append(self.total_value)
        hero.append(total_label)
        root.append(hero)

        chips = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.today_value = self._stat_chip(chips, "TODAY")
        self.active_value = self._stat_chip(chips, "ACTIVE")
        root.append(chips)

        self.provider_rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.append(self.provider_rows_box)

        self.updated_label = Gtk.Label(label="")
        self.updated_label.add_css_class("provider-meta")
        self.updated_label.set_halign(Gtk.Align.START)
        root.append(self.updated_label)

    def _stat_chip(self, parent: Gtk.Box, label: str) -> Gtk.Label:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.add_css_class("stat-chip")
        box.set_hexpand(True)
        value = Gtk.Label(label="—")
        value.add_css_class("stat-chip-value")
        value.set_halign(Gtk.Align.START)
        caption = Gtk.Label(label=label)
        caption.add_css_class("stat-chip-label")
        caption.set_halign(Gtk.Align.START)
        box.append(value)
        box.append(caption)
        parent.append(box)
        return value

    def _on_refresh(self) -> bool:
        snapshot = write_snapshot()
        summary = snapshot.get("summary") or {}

        if hasattr(self, "total_value"):
            self.total_value.set_text(summary.get("total_tokens_fmt", "—"))
        if hasattr(self, "today_value"):
            self.today_value.set_text(summary.get("today_tokens_fmt", "—"))
        if hasattr(self, "active_value"):
            self.active_value.set_text(str(summary.get("active_sessions", 0)))

        while child := self.provider_rows_box.get_first_child():
            self.provider_rows_box.remove(child)

        for provider in snapshot.get("providers") or []:
            self.provider_rows_box.append(self._provider_row(provider))

        if hasattr(self, "updated_label"):
            generated = snapshot.get("generated_at", "")
            self.updated_label.set_text(f"Updated {generated[:19].replace('T', ' ')} UTC")

        return True

    def _provider_row(self, provider: dict) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        card.add_css_class("provider-card")

        dot = Gtk.Box()
        dot.add_css_class("dot")
        dot.add_css_class(f"{provider.get('id', 'grok')}-dot")

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text.set_hexpand(True)
        name = Gtk.Label(label=provider.get("label", "Provider"))
        name.add_css_class("provider-name")
        name.set_halign(Gtk.Align.START)
        meta = Gtk.Label(label=self._provider_meta(provider), xalign=0)
        meta.add_css_class("provider-meta")
        meta.set_wrap(True)
        text.append(name)
        text.append(meta)

        value = Gtk.Label(label=fmt_tokens(provider.get("total_tokens")))
        value.add_css_class("provider-value")

        card.append(dot)
        card.append(text)
        card.append(value)
        return card

    @staticmethod
    def _provider_meta(provider: dict) -> str:
        parts = []
        if provider.get("model"):
            parts.append(str(provider["model"]))
        if provider.get("rate_primary") and provider["rate_primary"] != "—":
            parts.append(f"5h {provider['rate_primary']}")
        if provider.get("active_sessions"):
            parts.append(f"{provider['active_sessions']} active")
        return " · ".join(parts) or f"{provider.get('sessions', 0)} sessions"


class TrackerApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id="com.vektraindustries.vektra-ai-meter")
        self.window: TrackerWindow | None = None

    def do_activate(self) -> None:
        if self.window is not None:
            self.window.present()
            return

        css = Gtk.CssProvider()
        css.load_from_data(CSS.encode("utf-8"))
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

        config = WidgetConfig().load()
        self.window = TrackerWindow(self, config)
        self.window.present()


def main() -> int:
    app = TrackerApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())