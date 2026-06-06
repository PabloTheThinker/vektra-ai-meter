from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from ..layershell import preload_layer_shell
from ..util import snapshot_path

preload_layer_shell()

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import GLib, Gtk, Gtk4LayerShell  # noqa: E402

from .theme import (  # noqa: E402
    BG,
    BORDER,
    BORDER_SUBTLE,
    PANEL_WIDTH,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
    provider_style,
    usage_color,
    window_title,
)

CSS = f"""
window.vektra-popup {{
  background-color: transparent;
}}
.vektra-root {{
  background-color: {BG};
  color: {TEXT};
  border-radius: 14px;
  border: 1px solid {BORDER};
  min-width: {PANEL_WIDTH}px;
}}
.vektra-header {{
  padding: 14px 16px 10px 16px;
}}
.vektra-title {{
  font-size: 14px;
  font-weight: 700;
}}
.vektra-subtitle {{
  font-size: 10px;
  color: {TEXT_DIM};
}}
.vektra-pill {{
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid {BORDER_SUBTLE};
}}
.vektra-divider {{
  background-color: {BORDER_SUBTLE};
  min-height: 1px;
  margin: 0 16px;
}}
.vektra-body {{
  padding: 8px 16px 12px 16px;
}}
.vektra-card {{
  background-color: #18181b;
  border: 1px solid {BORDER};
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 10px;
}}
.vektra-provider-name {{
  font-size: 13px;
  font-weight: 700;
}}
.vektra-provider-meta {{
  font-size: 10px;
  color: {TEXT_DIM};
}}
.vektra-window-label {{
  font-size: 11px;
  color: {TEXT_MUTED};
}}
.vektra-reset {{
  font-size: 10px;
  color: {TEXT_DIM};
}}
.vektra-percent {{
  font-size: 13px;
  font-weight: 700;
}}
.vektra-footer {{
  padding: 8px 16px 12px 16px;
  border-top: 1px solid {BORDER_SUBTLE};
  font-size: 10px;
  color: {TEXT_DIM};
}}
.vektra-iconbtn {{
  min-width: 30px;
  min-height: 30px;
  padding: 0;
  border-radius: 8px;
}}
.vektra-backdrop {{
  background-color: rgba(0, 0, 0, 0.01);
}}
progressbar.vektra-bar progress {{
  background-color: #22c55e;
  border-radius: 3px;
}}
progressbar.vektra-bar.warning progress {{
  background-color: #f59e0b;
}}
progressbar.vektra-bar.critical progress {{
  background-color: #ef4444;
}}
progressbar trough {{
  background-color: #27272a;
  border-radius: 3px;
  min-height: 6px;
}}
"""


def _reset_hint(value: str | None) -> str:
    if not value:
        return ""
    try:
        raw = value.replace("Z", "+00:00")
        resets = datetime.fromisoformat(raw)
        if resets.tzinfo is None:
            resets = resets.replace(tzinfo=timezone.utc)
        delta = resets - datetime.now(timezone.utc)
        minutes = int(delta.total_seconds() // 60)
        if minutes <= 0:
            return "Resets soon"
        if minutes < 60:
            return f"Resets in {minutes}m"
        hours = minutes // 60
        if hours < 48:
            return f"Resets in {hours}h"
        return f"Resets in {hours // 24}d"
    except ValueError:
        return ""


def _ago_label(iso_value: str | None) -> str:
    if not iso_value:
        return ""
    try:
        raw = iso_value.replace("Z", "+00:00")
        generated = datetime.fromisoformat(raw)
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        seconds = int((datetime.now(timezone.utc) - generated).total_seconds())
        if seconds < 5:
            return "Updated just now"
        if seconds < 60:
            return f"Updated {seconds}s ago"
        if seconds < 3600:
            return f"Updated {seconds // 60}m ago"
        return f"Updated {seconds // 3600}h ago"
    except ValueError:
        return ""


def load_snapshot() -> dict:
    path = snapshot_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


class IntegratedPopup:
    def __init__(self, application: Gtk.Application) -> None:
        self.app = application
        self.window: Gtk.Window | None = None
        self.backdrop: Gtk.Window | None = None
        self.visible = False
        self.body_box: Gtk.Box | None = None
        self.pills_box: Gtk.Box | None = None
        self.footer_label: Gtk.Label | None = None

    def build(self) -> Gtk.Window:
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode("utf-8"))
        display = Gtk.Window().get_display()
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        win = Gtk.ApplicationWindow(application=self.app)
        win.add_css_class("vektra-popup")
        win.set_decorated(False)
        win.set_resizable(False)
        win.set_default_size(PANEL_WIDTH, 420)

        Gtk4LayerShell.init_for_window(win)
        Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.OVERLAY)
        Gtk4LayerShell.set_anchor(win, Gtk4LayerShell.Edge.TOP, True)
        Gtk4LayerShell.set_anchor(win, Gtk4LayerShell.Edge.RIGHT, True)
        top_margin = int(os.environ.get("VEKTRA_TOP_BAR_HEIGHT", "36"))
        Gtk4LayerShell.set_margin(win, Gtk4LayerShell.Edge.TOP, top_margin)
        Gtk4LayerShell.set_margin(win, Gtk4LayerShell.Edge.RIGHT, 10)
        Gtk4LayerShell.set_keyboard_mode(win, Gtk4LayerShell.KeyboardMode.ON_DEMAND)

        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key)
        win.add_controller(key)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.add_css_class("vektra-root")
        win.set_child(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.add_css_class("vektra-header")
        title_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_col.set_hexpand(True)
        title = Gtk.Label(label="Vektra AI Meter", xalign=0.0)
        title.add_css_class("vektra-title")
        subtitle = Gtk.Label(label="AI usage limits", xalign=0.0)
        subtitle.add_css_class("vektra-subtitle")
        title_col.append(title)
        title_col.append(subtitle)
        header.append(title_col)

        refresh = Gtk.Button(label="↻")
        refresh.add_css_class("vektra-iconbtn")
        refresh.set_tooltip_text("Refresh")
        refresh.connect("clicked", lambda *_: self.refresh())
        header.append(refresh)

        close = Gtk.Button(label="✕")
        close.add_css_class("vektra-iconbtn")
        close.set_tooltip_text("Close")
        close.connect("clicked", lambda *_: self.hide())
        header.append(close)
        root.append(header)

        self.pills_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        pills_wrap = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        pills_wrap.set_margin_start(16)
        pills_wrap.set_margin_end(16)
        pills_wrap.set_margin_bottom(8)
        pills_wrap.append(self.pills_box)
        root.append(pills_wrap)

        root.append(self._divider())

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(280)
        self.body_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.body_box.add_css_class("vektra-body")
        scroll.set_child(self.body_box)
        root.append(scroll)

        self.footer_label = Gtk.Label(label="", xalign=0.5)
        self.footer_label.add_css_class("vektra-footer")
        root.append(self.footer_label)

        self.window = win
        self._ensure_backdrop()
        self.refresh()
        return win

    def _ensure_backdrop(self) -> Gtk.Window:
        if self.backdrop is not None:
            return self.backdrop

        backdrop = Gtk.Window(application=self.app)
        backdrop.add_css_class("vektra-backdrop")
        backdrop.set_decorated(False)
        backdrop.set_can_focus(False)

        Gtk4LayerShell.init_for_window(backdrop)
        Gtk4LayerShell.set_layer(backdrop, Gtk4LayerShell.Layer.OVERLAY)
        for edge in (
            Gtk4LayerShell.Edge.TOP,
            Gtk4LayerShell.Edge.BOTTOM,
            Gtk4LayerShell.Edge.LEFT,
            Gtk4LayerShell.Edge.RIGHT,
        ):
            Gtk4LayerShell.set_anchor(backdrop, edge, True)
        Gtk4LayerShell.set_keyboard_mode(backdrop, Gtk4LayerShell.KeyboardMode.NONE)

        click = Gtk.GestureClick()
        click.connect("pressed", lambda *_: self.hide())
        backdrop.add_controller(click)

        self.backdrop = backdrop
        return backdrop

    def _divider(self) -> Gtk.Widget:
        box = Gtk.Box()
        box.add_css_class("vektra-divider")
        return box

    def _clear(self, box: Gtk.Box) -> None:
        while child := box.get_first_child():
            box.remove(child)

    def _on_key(self, _ctl, keyval, _kc, _state) -> bool:
        if keyval == 0xFF1B:
            self.hide()
            return True
        return False

    def _level_bar(self, percent: float) -> Gtk.Widget:
        bar = Gtk.LevelBar()
        bar.set_value(percent / 100.0)
        bar.add_css_class("vektra-bar")
        color = usage_color(percent)
        bar.set_tooltip_text(f"{percent:.0f}% used")
        bar.add_css_class("ok" if percent < 70 else "warning" if percent < 90 else "critical")
        return bar

    def _provider_card(self, provider: dict) -> Gtk.Widget:
        pid = str(provider.get("id") or "")
        style = provider_style(pid)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("vektra-card")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name = Gtk.Label(label=provider.get("label") or style["name"], xalign=0.0)
        name.add_css_class("vektra-provider-name")
        name.set_hexpand(True)
        header.append(name)
        if provider.get("plan_type"):
            plan = Gtk.Label(label=str(provider["plan_type"]).capitalize(), xalign=1.0)
            plan.add_css_class("vektra-provider-meta")
            header.append(plan)
        card.append(header)

        subtitle_parts = []
        if provider.get("subtitle"):
            subtitle_parts.append(str(provider["subtitle"]))
        if provider.get("model"):
            subtitle_parts.append(str(provider["model"]))
        if subtitle_parts:
            sub = Gtk.Label(label=" · ".join(subtitle_parts), xalign=0.0, wrap=True)
            sub.add_css_class("vektra-provider-meta")
            card.append(sub)

        limits = provider.get("limits") or []
        if limits:
            for limit in limits:
                card.append(self._limit_row(limit))
        else:
            tokens = provider.get("total_tokens_fmt")
            msg = "No quota windows in local sessions."
            if tokens:
                msg += f" ({tokens} logged)"
            empty = Gtk.Label(label=msg, xalign=0.0, wrap=True)
            empty.add_css_class("vektra-provider-meta")
            card.append(empty)

        return card

    def _limit_row(self, limit: dict) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        label = Gtk.Label(label=window_title(str(limit.get("label") or "Limit")), xalign=0.0)
        label.add_css_class("vektra-window-label")
        label.set_hexpand(True)
        header.append(label)
        reset = _reset_hint(limit.get("resets_at"))
        if reset:
            reset_lbl = Gtk.Label(label=reset, xalign=1.0)
            reset_lbl.add_css_class("vektra-reset")
            header.append(reset_lbl)
        row.append(header)

        used = limit.get("used_percent")
        if used is not None:
            bar_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            bar = Gtk.ProgressBar()
            bar.add_css_class("vektra-bar")
            state = "critical" if float(used) >= 90 else "warning" if float(used) >= 70 else "ok"
            if state != "ok":
                bar.add_css_class(state)
            bar.set_fraction(min(1.0, max(0.0, float(used) / 100.0)))
            bar.set_hexpand(True)
            bar_row.append(bar)
            pct = Gtk.Label(label=f"{float(used):.0f}%")
            pct.add_css_class("vektra-percent")
            bar_row.append(pct)
            row.append(bar_row)
            used_fmt = limit.get("used_tokens_fmt")
            limit_fmt = limit.get("limit_tokens_fmt")
            if used_fmt and limit_fmt:
                detail = Gtk.Label(label=f"{used_fmt} of {limit_fmt}", xalign=0.0)
                detail.add_css_class("vektra-reset")
                row.append(detail)
        return row

    def refresh(self) -> None:
        if self.body_box is None or self.pills_box is None or self.footer_label is None:
            return
        snapshot = load_snapshot()
        self._clear(self.pills_box)
        self._clear(self.body_box)

        providers = snapshot.get("providers") or []
        for provider in providers:
            peak = None
            peak_label = ""
            for limit in provider.get("limits") or []:
                used = limit.get("used_percent")
                if used is None or limit.get("label") == "Session":
                    continue
                if peak is None or float(used) > peak:
                    peak = float(used)
                    peak_label = str(limit.get("label") or "")
            if peak is not None:
                style = provider_style(str(provider.get("id") or ""))
                short = style["name"].split()[0]
                pill = Gtk.Label(label=f"{short} {peak_label} {peak:.0f}%")
                pill.add_css_class("vektra-pill")
                self.pills_box.append(pill)

        if not providers:
            empty = Gtk.Label(label="No provider sessions found.", xalign=0.0)
            empty.add_css_class("vektra-provider-meta")
            self.body_box.append(empty)
        else:
            for provider in providers:
                if provider.get("sessions", 0) > 0 or provider.get("limits"):
                    self.body_box.append(self._provider_card(provider))

        self.footer_label.set_text(_ago_label(snapshot.get("generated_at")))

    def show(self) -> None:
        if self.window is None:
            return
        self.refresh()
        backdrop = self._ensure_backdrop()
        backdrop.set_visible(True)
        self.window.present()
        self.visible = True

    def hide(self) -> None:
        if self.window is None:
            return
        if self.backdrop is not None:
            self.backdrop.set_visible(False)
        self.window.set_visible(False)
        self.visible = False

    def toggle(self) -> None:
        if self.visible:
            self.hide()
        else:
            self.show()