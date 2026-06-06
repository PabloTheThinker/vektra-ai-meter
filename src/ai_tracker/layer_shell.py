from __future__ import annotations

from ctypes import CDLL
from typing import Any

LayerShell: Any | None = None


def _try_load() -> Any | None:
    global LayerShell
    if LayerShell is not None:
        return LayerShell

    import gi

    for name in (
        "libgtk4-layer-shell.so.0",
        "libgtk4-layer-shell.so",
        "libgtk4-layer-shell-1.so.0",
    ):
        try:
            CDLL(name)
            gi.require_version("Gtk4LayerShell", "1.0")
            from gi.repository import Gtk4LayerShell as _LayerShell

            LayerShell = _LayerShell
            return LayerShell
        except (OSError, ValueError, ImportError):
            continue
    return None


def configure_desktop_widget(window: Any, anchor: str, margin: int) -> bool:
    layer = _try_load()
    if layer is None:
        return False

    layer.init_for_window(window)
    layer.set_layer(window, layer.Layer.BOTTOM)
    layer.set_exclusive_zone(window, 0)

    anchors = {
        "top-left": (True, False, True, False),
        "top-right": (True, False, False, True),
        "bottom-left": (False, True, True, False),
        "bottom-right": (False, True, False, True),
    }
    top, bottom, left, right = anchors.get(anchor, anchors["top-right"])
    layer.set_anchor(window, layer.Edge.TOP, top)
    layer.set_anchor(window, layer.Edge.BOTTOM, bottom)
    layer.set_anchor(window, layer.Edge.LEFT, left)
    layer.set_anchor(window, layer.Edge.RIGHT, right)

    if top:
        layer.set_margin(window, layer.Edge.TOP, margin)
    if bottom:
        layer.set_margin(window, layer.Edge.BOTTOM, margin)
    if left:
        layer.set_margin(window, layer.Edge.LEFT, margin)
    if right:
        layer.set_margin(window, layer.Edge.RIGHT, margin)

    layer.set_keyboard_mode(window, layer.KeyboardMode.NONE)
    return True