#!/usr/bin/env bash
#
# Vektra AI Meter — one-line Linux installer
#
#   curl -fsSL https://vektraindustries.com/ai-tracker/install | bash
#
set -euo pipefail

REPO_URL="${VEKTRA_AI_METER_REPO_URL:-https://github.com/PabloTheThinker/vektra-ai-meter.git}"
INSTALL_ROOT="${VEKTRA_AI_METER_INSTALL_ROOT:-${HOME}/.local/share/vektra-ai-meter}"
APP_DIR="${INSTALL_ROOT}/app"
VENV_DIR="${INSTALL_ROOT}/venv"
BIN_DIR="${HOME}/.local/bin"
AUTOSTART_DIR="${HOME}/.config/autostart"
BRANCH="${VEKTRA_AI_METER_BRANCH:-main}"

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  MAGENTA='\033[0;35m'
  CYAN='\033[0;36m'
  GREEN='\033[0;32m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  MAGENTA='' CYAN='' GREEN='' BOLD='' NC=''
fi

ok() { echo -e "${GREEN}✓${NC} $*"; }
log() { echo -e "${CYAN}→${NC} $*"; }

echo ""
echo -e "${MAGENTA}${BOLD}Vektra AI Meter${NC}"
echo -e "${CYAN}Top-bar panel meter for Grok, Codex, and Claude${NC}"
echo ""

for cmd in python3 git; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "$cmd is required."
    echo "Install with: sudo apt install python3 git"
    exit 1
  fi
done

if ! python3 -c "import venv" 2>/dev/null; then
  echo "python3-venv is required."
  echo "Install with: sudo apt install python3-venv"
  exit 1
fi

mkdir -p "$INSTALL_ROOT" "$BIN_DIR" "$AUTOSTART_DIR"

if [[ -d "$APP_DIR/.git" ]]; then
  log "Updating..."
  git -C "$APP_DIR" fetch origin "$BRANCH"
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
else
  log "Downloading..."
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

if [[ ! -d "$VENV_DIR" ]]; then
  log "Creating Python environment..."
  python3 -m venv "$VENV_DIR"
fi

log "Installing package (PySide6 included)..."
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q --upgrade "$APP_DIR"

cat >"$BIN_DIR/ai-meter" <<EOF
#!/usr/bin/env bash
exec "${VENV_DIR}/bin/ai-meter" "\$@"
EOF
chmod 755 "$BIN_DIR/ai-meter"

log "Configuring autostart (desktop + systemd)..."
"$VENV_DIR/bin/ai-meter" config >/dev/null 2>&1 || true

rm -f "$AUTOSTART_DIR/ai-usage-tracker.desktop" 2>/dev/null || true

echo ""
echo -e "${BOLD}Vektra AI Meter installed${NC}"
echo ""
ok "CLI:       $BIN_DIR/ai-meter"
ok "Package:   vektra-ai-meter $( "$VENV_DIR/bin/python" -c "import importlib.metadata as m; print(m.version('vektra-ai-meter'))" 2>/dev/null || echo '0.2.0' )"
ok "Autostart: enabled on login (desktop + systemd user service)"
echo ""
echo "Commands:"
echo "  ai-meter status"
echo "  ai-meter update"
echo "  ai-meter snapshot --write --pretty"
echo ""
echo "The meter starts automatically on login — no need to run ai-meter run manually."
echo ""

if [[ "${VEKTRA_AI_METER_LAUNCH:-1}" == "1" ]]; then
  pkill -f "${VENV_DIR}/bin/ai-meter" 2>/dev/null || true
  log "Launching panel indicator..."
  nohup "$BIN_DIR/ai-meter" run >/dev/null 2>&1 &
  ok "Look in your top-bar status area"
fi