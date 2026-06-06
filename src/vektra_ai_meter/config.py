from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Config:
    autostart: bool = True

    @property
    def path(self) -> Path:
        config_dir = Path.home() / ".config" / "vektra-ai-meter"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.json"

    def load(self) -> Config:
        if not self.path.exists():
            return self
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self
        return Config(autostart=bool(data.get("autostart", self.autostart)))

    def save(self) -> None:
        self.path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")