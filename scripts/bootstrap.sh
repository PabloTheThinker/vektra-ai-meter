#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${HOME}/.local/bin"
DESKTOP_DIR="${HOME}/.local/share/applications"
AUTOSTART_DIR="${HOME}/.config/autostart"
CONFIG_DIR="${HOME}/.config/vektra-ai-meter"

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  CYAN='\033[0;36m'
  GREEN='\033[0;32m'
  YELLOW='\033[0;33m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  CYAN='' GREEN='' YELLOW='' BOLD='' NC=''
fi

log() { echo -e "${CYAN}→${NC} $*"; }
ok() { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }

require_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 is required. Install with: sudo apt install python3"
    exit 1
  fi
  ok "Python $(python3 --version | awk '{print $2}')"
}

require_topbar() {
  if python3 -c "import gi; gi.require_version('Gtk','3.0'); gi.require_version('AyatanaAppIndicator3','0.1'); from gi.repository import Gtk, AyatanaAppIndicator3" 2>/dev/null; then
    ok "Panel indicator support (Ayatana AppIndicator)"
    return 0
  fi
  warn "Panel indicator bindings missing"
  echo "Install with:"
  echo "  sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1"
  exit 1
}

require_gtk4() {
  if python3 -c "import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk" 2>/dev/null; then
    ok "GTK 4 available"
    return 0
  fi
  warn "GTK 4 Python bindings missing"
  echo "Install with:"
  echo "  sudo apt install python3-gi gir1.2-gtk-4.0"
  exit 1
}

detect_interface() {
  if [[ -n "${VEKTRA_AI_METER_INTERFACE:-}" ]]; then
    echo "$VEKTRA_AI_METER_INTERFACE"
    return
  fi
  if [[ -f "$CONFIG_DIR/config.json" ]]; then
    python3 - <<'PY' 2>/dev/null || echo topbar
import json, os
path = os.path.expanduser("~/.config/vektra-ai-meter/config.json")
with open(path, encoding="utf-8") as f:
    data = json.load(f)
print(data.get("interface", "topbar"))
PY
    return
  fi
  echo "topbar"
}

require_python

INTERFACE="$(detect_interface)"
if [[ "$INTERFACE" == "widget" ]]; then
  require_gtk4
else
  INTERFACE="topbar"
  require_topbar
fi

mkdir -p "$BIN_DIR" "$DESKTOP_DIR" "$AUTOSTART_DIR" "$CONFIG_DIR"

cat >"$BIN_DIR/ai-meter" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export VEKTRA_AI_METER_ROOT="$ROOT"
export PYTHONPATH="\$VEKTRA_AI_METER_ROOT/src\${PYTHONPATH:+:\$PYTHONPATH}"
export LD_LIBRARY_PATH="\${HOME}/.local/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
export GI_TYPELIB_PATH="\${HOME}/.local/lib/girepository-1.0\${GI_TYPELIB_PATH:+:\$GI_TYPELIB_PATH}"
exec python3 "\$VEKTRA_AI_METER_ROOT/cli/ai-meter" "\$@"
EOF
chmod 755 "$BIN_DIR/ai-meter"

if [[ ! -f "$CONFIG_DIR/config.json" ]]; then
  cat >"$CONFIG_DIR/config.json" <<'EOF'
{
  "interface": "topbar",
  "size": "medium",
  "anchor": "top-right",
  "margin": 24,
  "autostart": true,
  "desktop_mode": true
}
EOF
else
  python3 - <<'PY'
import json
from pathlib import Path

path = Path.home() / ".config" / "vektra-ai-meter" / "config.json"
data = json.loads(path.read_text(encoding="utf-8"))
if "interface" not in data:
    data["interface"] = "topbar"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
fi

RUN_CMD="${BIN_DIR}/ai-meter run"
if [[ "$INTERFACE" == "widget" ]]; then
  RUN_CMD="${BIN_DIR}/ai-meter widget"
fi

cat >"$DESKTOP_DIR/vektra-ai-meter.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Vektra AI Meter
GenericName=AI Usage Meter
Comment=Top-bar indicator for Grok, Codex, and Claude usage
Exec=${RUN_CMD}
Icon=utilities-system-monitor
Terminal=false
Categories=Utility;System;
StartupNotify=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF

cat >"$AUTOSTART_DIR/vektra-ai-meter.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Vektra AI Meter
Comment=Autostart Vektra AI Meter panel indicator
Exec=${RUN_CMD}
Icon=utilities-system-monitor
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=3
EOF

rm -f "$AUTOSTART_DIR/ai-usage-tracker.desktop" "$DESKTOP_DIR/ai-usage-tracker.desktop" 2>/dev/null || true

echo ""
echo -e "${BOLD}Vektra AI Meter installed${NC}"
echo ""
ok "CLI:       $BIN_DIR/ai-meter"
ok "App dir:   $ROOT"
ok "Interface: $INTERFACE"
ok "Config:    $CONFIG_DIR/config.json"
ok "Autostart: enabled on login"
echo ""
echo "Commands:"
echo "  ai-meter run"
echo "  ai-meter topbar"
echo "  ai-meter widget"
echo "  ai-meter snapshot --write --pretty"
echo "  ai-meter config --interface topbar"
echo ""
echo "Update later:"
echo "  curl -fsSL https://vektraindustries.com/ai-tracker/install | bash"
echo ""

if [[ "${VEKTRA_AI_METER_LAUNCH_WIDGET:-1}" == "1" ]]; then
  pkill -f "ai-meter widget" 2>/dev/null || true
  pkill -f "ai-meter topbar" 2>/dev/null || true
  pkill -f "ai-meter run" 2>/dev/null || true
  log "Launching panel indicator..."
  nohup "$RUN_CMD" >/dev/null 2>&1 &
  ok "Panel indicator started — look in your top bar status area"
fi