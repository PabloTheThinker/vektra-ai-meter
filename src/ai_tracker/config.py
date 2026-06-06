from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class WidgetConfig:
    interface: str = "topbar"
    size: str = "medium"
    anchor: str = "top-right"
    margin: int = 24
    autostart: bool = True
    desktop_mode: bool = True

    @property
    def path(self) -> Path:
        config_dir = Path.home() / ".config" / "vektra-ai-meter"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.json"

    def load(self) -> WidgetConfig:
        if not self.path.exists():
            return self
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self
        interface = str(data.get("interface", self.interface))
        if interface not in ("topbar", "widget"):
            interface = self.interface
        return WidgetConfig(
            interface=interface,
            size=str(data.get("size", self.size)),
            anchor=str(data.get("anchor", self.anchor)),
            margin=int(data.get("margin", self.margin)),
            autostart=bool(data.get("autostart", self.autostart)),
            desktop_mode=bool(data.get("desktop_mode", self.desktop_mode)),
        )

    def save(self) -> None:
        self.path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


SIZE_PRESETS = {
    "small": (172, 172),
    "medium": (320, 220),
    "large": (320, 360),
}