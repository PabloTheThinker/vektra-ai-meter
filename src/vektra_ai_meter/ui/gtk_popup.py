from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

from ..layershell import preload_layer_shell
from ..util import snapshot_display_digest, snapshot_path

preload_layer_shell()

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import GLib, Gtk, Gtk4LayerShell  # noqa: E402

from .placement import PANEL_HEIGHT, PanelPlacement, compute_panel_placement  # noqa: E402
from .theme import (  # noqa: E402
    BG,
    BG_CARD,
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
  letter-spacing: -0.2px;
}}
.vektra-subtitle {{
  font-size: 10px;
  color: {TEXT_DIM};
}}
.vektra-pill {{
  padding: 5px 11px;
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
  background-color: {BG_CARD};
  border: 1px solid {BORDER};
  border-radius: 12px;
  margin-bottom: 10px;
}}
.vektra-card-accent {{
  min-width: 3px;
  border-top-left-radius: 12px;
  border-bottom-left-radius: 12px;
}}
.vektra-badge {{
  min-width: 30px;
  min-height: 30px;
  border-radius: 9px;
  font-size: 11px;
  font-weight: 700;
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
  font-weight: 500;
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
  background-color: #141416;
  border: 1px solid {BORDER};
}}
.vektra-backdrop-window {{
  background-color: rgba(0, 0, 0, 0.32);
}}
progressbar.vektra-bar progress {{
  background-color: #22c55e;
  border-radius: 4px;
  min-height: 7px;
}}
progressbar.vektra-bar.warning progress {{
  background-color: #f59e0b;
}}
progressbar.vektra-bar.critical progress {{
  background-color: #ef4444;
}}
progressbar trough {{
  background-color: #27272a;
  border-radius: 4px;
  min-height: 7px;
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


def ago_label(iso_value: str | None) -> str:
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
        self._placement: PanelPlacement | None = None
        self.body_box: Gtk.Box | None = None
        self.pills_box: Gtk.Box | None = None
        self.footer_label: Gtk.Label | None = None
        self._digest: str | None = None
        self._generated_at: str | None = None
        self._footer_timer_id: int | None = None
        self._refresh_btn: Gtk.Button | None = None
        self._show_generation = 0

    def _is_open(self) -> bool:
        return self.visible

    def _set_layer_open(self, open_: bool) -> None:
        for widget in (self.backdrop, self.window):
            if widget is None:
                continue
            if open_:
                widget.set_opacity(1.0)
                widget.set_can_target(True)
                widget.set_visible(True)
            else:
                widget.set_opacity(0.0)
                widget.set_can_target(False)

    def _apply_panel_placement(self, placement: PanelPlacement) -> None:
        if self.window is None:
            return
        self._placement = placement
        for edge in (
            Gtk4LayerShell.Edge.TOP,
            Gtk4LayerShell.Edge.BOTTOM,
            Gtk4LayerShell.Edge.LEFT,
            Gtk4LayerShell.Edge.RIGHT,
        ):
            Gtk4LayerShell.set_anchor(self.window, edge, False)
        Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.TOP, True)
        if placement.anchor_left:
            Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.LEFT, True)
            Gtk4LayerShell.set_margin(self.window, Gtk4LayerShell.Edge.LEFT, placement.margin_left)
            Gtk4LayerShell.set_margin(self.window, Gtk4LayerShell.Edge.RIGHT, 0)
        else:
            Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.RIGHT, True)
            Gtk4LayerShell.set_margin(self.window, Gtk4LayerShell.Edge.RIGHT, placement.margin_right)
            Gtk4LayerShell.set_margin(self.window, Gtk4LayerShell.Edge.LEFT, 0)
        Gtk4LayerShell.set_margin(self.window, Gtk4LayerShell.Edge.TOP, placement.margin_top)

    def set_tray_geometry(
        self,
        tray_rect: tuple[int, int, int, int] | None,
        screen_rect: tuple[int, int, int, int] | None,
    ) -> None:
        placement = compute_panel_placement(tray=tray_rect, screen=screen_rect)
        self._apply_panel_placement(placement)

    def _build_backdrop(self) -> Gtk.Window:
        backdrop = Gtk.Window(application=self.app)
        backdrop.add_css_class("vektra-backdrop-window")
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

    def build(self) -> Gtk.Window:
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode("utf-8"))
        display = Gtk.Window().get_display()
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self._build_backdrop()

        win = Gtk.ApplicationWindow(application=self.app)
        win.add_css_class("vektra-popup")
        win.set_decorated(False)
        win.set_resizable(False)
        win.set_default_size(PANEL_WIDTH, PANEL_HEIGHT)

        Gtk4LayerShell.init_for_window(win)
        Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.OVERLAY)
        Gtk4LayerShell.set_keyboard_mode(win, Gtk4LayerShell.KeyboardMode.ON_DEMAND)
        self._apply_panel_placement(compute_panel_placement())

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

        self._refresh_btn = Gtk.Button(label="↻")
        self._refresh_btn.add_css_class("vektra-iconbtn")
        self._refresh_btn.set_tooltip_text("Refresh")
        self._refresh_btn.connect("clicked", lambda *_: self.refresh(force=True))
        header.append(self._refresh_btn)

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
        self._set_layer_open(False)
        return win

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

    def _badge(self, provider_id: str) -> Gtk.Widget:
        style = provider_style(provider_id)
        badge = Gtk.Label(label=style["badge"])
        badge.add_css_class("vektra-badge")
        badge.set_valign(Gtk.Align.CENTER)
        badge.set_halign(Gtk.Align.CENTER)
        rgba = style["accent"]
        badge.get_style_context().add_provider(
            self._badge_provider(rgba),
            Gtk.STYLE_PROVIDER_PRIORITY_USER,
        )
        return badge

    def _style_provider(self, selector: str, rules: str) -> Gtk.CssProvider:
        provider = Gtk.CssProvider()
        provider.load_from_data(f"{selector} {{ {rules} }}".encode("utf-8"))
        return provider

    def _badge_provider(self, accent: str) -> Gtk.CssProvider:
        return self._style_provider(
            ".vektra-badge",
            f"background-color: {accent}22; color: {accent};",
        )

    def _pill_provider(self, accent: str, border: str) -> Gtk.CssProvider:
        provider = Gtk.CssProvider()
        provider.load_from_data(
            (
                f".vektra-pill {{ background-color: {accent}18; "
                f"border-color: {border}55; color: {TEXT}; }}"
            ).encode("utf-8")
        )
        return provider

    def _provider_card(self, provider: dict) -> Gtk.Widget:
        pid = str(provider.get("id") or "")
        style = provider_style(pid)
        accent = style["accent"]

        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        card.add_css_class("vektra-card")

        accent_bar = Gtk.Box()
        accent_bar.add_css_class("vektra-card-accent")
        accent_bar.get_style_context().add_provider(
            self._style_provider(".vektra-card-accent", f"background-color: {accent};"),
            Gtk.STYLE_PROVIDER_PRIORITY_USER,
        )
        accent_bar.set_size_request(3, -1)
        card.append(accent_bar)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        body.set_margin_start(12)
        body.set_margin_end(12)
        body.set_margin_top(12)
        body.set_margin_bottom(12)
        body.set_hexpand(True)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header.append(self._badge(pid))

        name_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name_col.set_hexpand(True)
        name = Gtk.Label(label=provider.get("label") or style["name"], xalign=0.0)
        name.add_css_class("vektra-provider-name")
        name_col.append(name)

        subtitle_parts = []
        if provider.get("subtitle"):
            subtitle_parts.append(str(provider["subtitle"]))
        if provider.get("model"):
            subtitle_parts.append(str(provider["model"]))
        if subtitle_parts:
            sub = Gtk.Label(label=" · ".join(subtitle_parts), xalign=0.0, wrap=True)
            sub.add_css_class("vektra-provider-meta")
            name_col.append(sub)
        header.append(name_col)

        meta_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        if provider.get("plan_type"):
            plan = Gtk.Label(label=str(provider["plan_type"]).capitalize(), xalign=1.0)
            plan.add_css_class("vektra-provider-meta")
            plan.get_style_context().add_provider(
                self._style_provider("label", f"color: {accent}; font-weight: 600;"),
                Gtk.STYLE_PROVIDER_PRIORITY_USER,
            )
            meta_col.append(plan)
        if provider.get("active_sessions"):
            active = Gtk.Label(label=f"{provider['active_sessions']} active", xalign=1.0)
            active.add_css_class("vektra-provider-meta")
            meta_col.append(active)
        header.append(meta_col)
        body.append(header)
        card.append(body)

        limits = provider.get("limits") or []
        if limits:
            for limit in limits:
                body.append(self._limit_row(limit))
        else:
            tokens = provider.get("total_tokens_fmt")
            msg = "No quota windows detected in local sessions."
            if tokens:
                msg += f"\n{tokens} tokens logged."
            empty = Gtk.Label(label=msg, xalign=0.0, wrap=True)
            empty.add_css_class("vektra-provider-meta")
            body.append(empty)

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
            pct.get_style_context().add_provider(
                self._style_provider("label", f"color: {usage_color(float(used))};"),
                Gtk.STYLE_PROVIDER_PRIORITY_USER,
            )
            bar_row.append(pct)
            row.append(bar_row)
            used_fmt = limit.get("used_tokens_fmt")
            limit_fmt = limit.get("limit_tokens_fmt")
            if used_fmt and limit_fmt:
                detail = Gtk.Label(label=f"{used_fmt} of {limit_fmt}", xalign=0.0)
                detail.add_css_class("vektra-reset")
                row.append(detail)
        return row

    def _render_snapshot(self, snapshot: dict) -> None:
        if self.body_box is None or self.pills_box is None or self.footer_label is None:
            return

        self._clear(self.pills_box)
        self._clear(self.body_box)

        providers = snapshot.get("providers") or []
        has_pills = False
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
                pill.get_style_context().add_provider(
                    self._pill_provider(style["accent"], usage_color(peak)),
                    Gtk.STYLE_PROVIDER_PRIORITY_USER,
                )
                self.pills_box.append(pill)
                has_pills = True

        if not has_pills:
            waiting = Gtk.Label(label="Waiting for quota data from local sessions", xalign=0.0)
            waiting.add_css_class("vektra-provider-meta")
            self.pills_box.append(waiting)

        visible_providers = [
            provider
            for provider in providers
            if provider.get("sessions", 0) > 0 or provider.get("limits")
        ]
        if not visible_providers:
            empty = Gtk.Label(label="No provider sessions found on this machine.", xalign=0.0)
            empty.add_css_class("vektra-provider-meta")
            self.body_box.append(empty)
        else:
            for provider in visible_providers:
                self.body_box.append(self._provider_card(provider))

        self._generated_at = snapshot.get("generated_at")
        self.footer_label.set_text(ago_label(self._generated_at))

    def refresh(self, *, force: bool = False) -> None:
        snapshot = load_snapshot()
        digest = snapshot_display_digest(snapshot)
        if not force and digest == self._digest:
            self._generated_at = snapshot.get("generated_at")
            if self.footer_label is not None:
                self.footer_label.set_text(ago_label(self._generated_at))
            return

        self._digest = digest
        self._render_snapshot(snapshot)

    def _collect_and_refresh(self) -> None:
        try:
            from ..snapshot import write_snapshot

            snapshot = write_snapshot()
        except Exception:
            return
        GLib.idle_add(self._apply_collected_snapshot, snapshot)

    def _apply_collected_snapshot(self, snapshot: dict) -> bool:
        if not self.visible:
            return False
        digest = snapshot_display_digest(snapshot)
        if digest == self._digest:
            self._generated_at = snapshot.get("generated_at")
            if self.footer_label is not None:
                self.footer_label.set_text(ago_label(self._generated_at))
            return False
        self._digest = digest
        self._render_snapshot(snapshot)
        return False

    def _start_footer_timer(self) -> None:
        if self._footer_timer_id is not None:
            return
        self._footer_timer_id = GLib.timeout_add(1000, self._tick_footer)

    def _stop_footer_timer(self) -> None:
        if self._footer_timer_id is None:
            return
        GLib.source_remove(self._footer_timer_id)
        self._footer_timer_id = None

    def _tick_footer(self) -> bool:
        if self.footer_label is not None and self.visible:
            self.footer_label.set_text(ago_label(self._generated_at))
        return True

    def _present_windows(self, generation: int) -> bool:
        if generation != self._show_generation or self.window is None:
            return False

        self._set_layer_open(True)
        Gtk4LayerShell.set_keyboard_mode(self.window, Gtk4LayerShell.KeyboardMode.ON_DEMAND)
        if self.backdrop is not None:
            self.backdrop.present()
        self.window.present()
        self.visible = True
        self._start_footer_timer()
        threading.Thread(target=self._collect_and_refresh, daemon=True).start()
        return False

    def show(
        self,
        *,
        tray_rect: tuple[int, int, int, int] | None = None,
        screen_rect: tuple[int, int, int, int] | None = None,
    ) -> None:
        if self.window is None:
            return

        self.set_tray_geometry(tray_rect, screen_rect)
        self.refresh(force=True)
        if self._is_open():
            self._set_layer_open(True)
            if self.backdrop is not None:
                self.backdrop.present()
            self.window.present()
            self._start_footer_timer()
            threading.Thread(target=self._collect_and_refresh, daemon=True).start()
            return

        self._show_generation += 1
        generation = self._show_generation
        GLib.idle_add(self._present_windows, generation)

    def hide(self) -> None:
        if self.window is None:
            return
        self._show_generation += 1
        self.visible = False
        self._stop_footer_timer()
        self._set_layer_open(False)

    def toggle(self) -> None:
        if self._is_open():
            self.hide()
        else:
            self.show()