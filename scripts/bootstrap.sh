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

require_gtk() {
  if python3 -c "import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk" 2>/dev/null; then
    ok "GTK 4 available"
    return 0
  fi
  warn "GTK 4 Python bindings missing"
  echo "Install with:"
  echo "  sudo apt install python3-gi gir1.2-gtk-4.0"
  exit 1
}

require_python
require_gtk

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
  "size": "medium",
  "anchor": "top-right",
  "margin": 24,
  "autostart": true,
  "desktop_mode": true
}
EOF
fi

cat >"$DESKTOP_DIR/vektra-ai-meter.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Vektra AI Meter
GenericName=Glance Panel
Comment=Frosted glance panel for Grok, Codex, and Claude usage
Exec=${BIN_DIR}/ai-meter widget
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
Comment=Autostart Vektra AI Meter glance panel
Exec=${BIN_DIR}/ai-meter widget
Icon=utilities-system-monitor
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=3
EOF

echo ""
echo -e "${BOLD}Vektra AI Meter installed${NC}"
echo ""
ok "CLI:       $BIN_DIR/ai-meter"
ok "App dir:   $ROOT"
ok "Config:    $CONFIG_DIR/config.json"
ok "Autostart: enabled on login"
echo ""
echo "Commands:"
echo "  ai-meter widget"
echo "  ai-meter snapshot --write --pretty"
echo "  ai-meter config --size small"
echo ""
echo "Update later:"
echo "  curl -fsSL https://vektraindustries.com/ai-tracker/install | bash"
echo ""

if [[ "${VEKTRA_AI_METER_LAUNCH_WIDGET:-1}" == "1" ]]; then
  log "Launching glance panel..."
  nohup "$BIN_DIR/ai-meter" widget >/dev/null 2>&1 &
  ok "Glance panel started"
fi