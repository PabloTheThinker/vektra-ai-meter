#!/usr/bin/env bash
#
# Vektra AI Meter — one-line Linux installer
#
#   curl -fsSL https://vektraindustries.com/ai-tracker/install | bash
#
set -euo pipefail

REPO_URL="${VEKTRA_AI_METER_REPO_URL:-https://github.com/PabloTheThinker/vektra-ai-meter.git}"
INSTALL_ROOT="${VEKTRA_AI_METER_INSTALL_ROOT:-${HOME}/.local/share/vektra-ai-meter}"
APP_DIR="${VEKTRA_AI_METER_APP_DIR:-${INSTALL_ROOT}/app}"
VENV_DIR="${INSTALL_ROOT}/venv"
BIN_DIR="${HOME}/.local/bin"
AUTOSTART_DIR="${HOME}/.config/autostart"
BRANCH="${VEKTRA_AI_METER_BRANCH:-main}"
LOCAL_PREFIX="${HOME}/.local"
LAYER_LIB="${LOCAL_PREFIX}/lib/libgtk4-layer-shell.so.0"
LAYER_SRC="${INSTALL_ROOT}/gtk4-layer-shell-src"
LAYER_REPO="${VEKTRA_LAYER_SHELL_REPO:-https://github.com/wmww/gtk4-layer-shell.git}"

APT_BASE_PACKAGES=(
  python3
  python3-venv
  git
)
APT_INTEGRATION_PACKAGES=(
  pkg-config
  libgtk-4-dev
  libwayland-dev
  wayland-protocols
  gobject-introspection
  libgirepository-2.0-dev
  python3-gi
  gir1.2-gtk-4.0
  meson
  ninja-build
)

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  MAGENTA='\033[0;35m'
  CYAN='\033[0;36m'
  GREEN='\033[0;32m'
  YELLOW='\033[0;33m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  MAGENTA='' CYAN='' GREEN='' YELLOW='' BOLD='' NC=''
fi

ok() { echo -e "${GREEN}✓${NC} $*"; }
log() { echo -e "${CYAN}→${NC} $*"; }
warn() { echo -e "${YELLOW}!${NC} $*"; }

is_wayland() {
  [[ "${XDG_SESSION_TYPE:-}" == "wayland" || -n "${WAYLAND_DISPLAY:-}" ]]
}

have_gtk4_dev() {
  command -v pkg-config >/dev/null 2>&1 && pkg-config --exists gtk4 2>/dev/null
}

have_python_gi() {
  python3 -c "import gi; gi.require_version('Gtk', '4.0')" >/dev/null 2>&1
}

layer_shell_built() {
  [[ -f "$LAYER_LIB" || -f "${LOCAL_PREFIX}/lib/libgtk4-layer-shell.so" ]]
}

sudo_available() {
  [[ "${VEKTRA_SKIP_SUDO:-0}" != "1" ]] && command -v sudo >/dev/null 2>&1
}

apt_install() {
  local packages=("$@")
  local missing=()
  local pkg

  for pkg in "${packages[@]}"; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
      missing+=("$pkg")
    fi
  done

  if ((${#missing[@]} == 0)); then
    return 0
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    warn "Missing packages: ${missing[*]}"
    echo "  Install them with your system package manager, then re-run this installer."
    return 1
  fi

  if ! sudo_available; then
    warn "Missing packages: ${missing[*]}"
    echo "  Re-run with sudo available, or install manually then re-run:"
    echo "  sudo apt install -y ${missing[*]}"
    return 1
  fi

  log "Installing system packages (sudo may ask for your password)..."
  if ! sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${missing[@]}"; then
    warn "Could not install system packages (sudo failed or apt error)."
    echo "  Install manually: sudo apt install -y ${missing[*]}"
    return 1
  fi
  ok "System packages installed"
}

ensure_prerequisites() {
  if ! command -v python3 >/dev/null 2>&1 \
    || ! python3 -c "import venv" >/dev/null 2>&1 \
    || ! command -v git >/dev/null 2>&1; then
    apt_install "${APT_BASE_PACKAGES[@]}" || {
      echo "python3, python3-venv, and git are required."
      exit 1
    }
  fi

  if is_wayland && (! have_gtk4_dev || ! have_python_gi); then
    apt_install "${APT_INTEGRATION_PACKAGES[@]}" || true
  fi
}

install_layer_shell() {
  if layer_shell_built; then
    ok "Integrated panel: gtk4-layer-shell present"
    return 0
  fi

  if ! is_wayland; then
    log "X11 session detected — using Qt panel fallback (no layer-shell build needed)."
    return 0
  fi

  if ! have_gtk4_dev; then
    warn "GTK4 build headers still missing — integrated dropdown unavailable."
    echo "  Re-run: curl -fsSL https://vektraindustries.com/ai-tracker/install | bash"
    return 1
  fi

  if ! have_python_gi; then
    warn "python3-gi still missing — integrated dropdown unavailable."
    return 1
  fi

  "$VENV_DIR/bin/pip" install -q meson ninja 2>/dev/null || true
  export PATH="${VENV_DIR}/bin:${PATH}"

  log "Building gtk4-layer-shell (integrated top-bar dropdown)..."
  mkdir -p "${LOCAL_PREFIX}/lib" "${LOCAL_PREFIX}/lib/girepository-1.0"
  if [[ ! -d "$LAYER_SRC/.git" ]]; then
    git clone --depth 1 "$LAYER_REPO" "$LAYER_SRC"
  else
    git -C "$LAYER_SRC" pull --ff-only || true
  fi
  meson setup --reconfigure --prefix="${LOCAL_PREFIX}" --libdir=lib \
    -Dexamples=false -Ddocs=false -Dvapi=false "$LAYER_SRC/build" "$LAYER_SRC" 2>/dev/null \
    || rm -rf "$LAYER_SRC/build" \
    && meson setup --prefix="${LOCAL_PREFIX}" --libdir=lib \
      -Dexamples=false -Ddocs=false -Dvapi=false "$LAYER_SRC/build" "$LAYER_SRC"
  ninja -C "$LAYER_SRC/build"
  ninja -C "$LAYER_SRC/build" install
  ok "Integrated panel: gtk4-layer-shell installed to ${LOCAL_PREFIX}"
}

print_integration_status() {
  if [[ ! -x "$BIN_DIR/ai-meter" ]]; then
    return 0
  fi
  local integrated
  integrated="$("$BIN_DIR/ai-meter" status 2>/dev/null | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print('true' if d.get('integrated_popup') else 'false')" \
    2>/dev/null || echo "false")"
  if [[ "$integrated" == "true" ]]; then
    ok "Integrated top-bar dropdown: ready (click tray icon on Wayland)"
  elif is_wayland; then
    warn "Integrated dropdown not active — Qt panel fallback is running."
    echo "  Re-run: curl -fsSL https://vektraindustries.com/ai-tracker/install | bash"
  else
    ok "Qt panel fallback active (X11)"
  fi
}

BEFORE_VERSION=""
if [[ -x "$VENV_DIR/bin/python" ]]; then
  BEFORE_VERSION="$("$VENV_DIR/bin/python" -c "import importlib.metadata as m; print(m.version('vektra-ai-meter'))" 2>/dev/null || true)"
fi

echo ""
if [[ "${VEKTRA_AI_METER_UPDATE:-0}" == "1" ]]; then
  echo -e "${MAGENTA}${BOLD}Vektra AI Meter${NC} — updating"
else
  echo -e "${MAGENTA}${BOLD}Vektra AI Meter${NC}"
  echo -e "${CYAN}One command — tray icon + integrated top-bar dropdown${NC}"
fi
echo ""

ensure_prerequisites

mkdir -p "$INSTALL_ROOT" "$BIN_DIR" "$AUTOSTART_DIR" "${LOCAL_PREFIX}/lib"

sync_app_repo() {
  if [[ -n "${VEKTRA_AI_METER_APP_DIR:-}" ]]; then
    log "Using app directory: $APP_DIR"
    return 0
  fi

  if [[ -d "$APP_DIR/.git" ]]; then
    log "Updating..."
    # Managed install dir must mirror upstream — discard stale local edits from older installs.
    git -C "$APP_DIR" fetch origin "$BRANCH"
    git -C "$APP_DIR" checkout -f "$BRANCH"
    git -C "$APP_DIR" reset --hard "origin/${BRANCH}"
    git -C "$APP_DIR" clean -fd
    return 0
  fi

  log "Downloading..."
  rm -rf "$APP_DIR"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
}

sync_app_repo

if [[ ! -d "$VENV_DIR" ]]; then
  log "Creating Python environment..."
  python3 -m venv "$VENV_DIR"
fi

log "Installing package (PySide6 included)..."
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q --upgrade "$APP_DIR"

install_layer_shell || true

cat >"$BIN_DIR/ai-meter" <<EOF
#!/usr/bin/env bash
export LD_LIBRARY_PATH="${LOCAL_PREFIX}/lib:\${LD_LIBRARY_PATH:-}"
export GI_TYPELIB_PATH="${LOCAL_PREFIX}/lib/girepository-1.0:\${GI_TYPELIB_PATH:-}"
exec "${VENV_DIR}/bin/ai-meter" "\$@"
EOF
chmod 755 "$BIN_DIR/ai-meter"

log "Configuring autostart (desktop + systemd)..."
"$BIN_DIR/ai-meter" config >/dev/null 2>&1 || true

rm -f "$AUTOSTART_DIR/ai-usage-tracker.desktop" 2>/dev/null || true

AFTER_VERSION="$( "$VENV_DIR/bin/python" -c "import importlib.metadata as m; print(m.version('vektra-ai-meter'))" 2>/dev/null || echo 'unknown' )"

echo ""
if [[ "${VEKTRA_AI_METER_UPDATE:-0}" == "1" ]]; then
  echo -e "${BOLD}Vektra AI Meter updated${NC}"
else
  echo -e "${BOLD}Vektra AI Meter installed${NC}"
fi
echo ""
ok "CLI:       $BIN_DIR/ai-meter"
if [[ -n "$BEFORE_VERSION" && "$BEFORE_VERSION" == "$AFTER_VERSION" ]]; then
  ok "Package:   vektra-ai-meter $AFTER_VERSION (already up to date)"
elif [[ -n "$BEFORE_VERSION" ]]; then
  ok "Package:   vektra-ai-meter $BEFORE_VERSION → $AFTER_VERSION"
else
  ok "Package:   vektra-ai-meter $AFTER_VERSION"
fi
ok "Autostart: enabled on login (desktop + systemd user service)"
print_integration_status
echo ""
if [[ "${VEKTRA_AI_METER_UPDATE:-0}" != "1" ]]; then
  echo "Commands:"
  echo "  ai-meter status"
  echo "  ai-meter reboot"
  echo "  ai-meter update"
  echo "  ai-meter snapshot --write --pretty"
  echo ""
  echo "The meter starts automatically on login — no extra setup steps."
  echo ""
fi

if [[ "${VEKTRA_AI_METER_LAUNCH:-1}" == "1" ]]; then
  pkill -f "${VENV_DIR}/bin/ai-meter" 2>/dev/null || true
  pkill -f "ai-meter popup-server" 2>/dev/null || true
  pkill -f "vektra_ai_meter.popup_server" 2>/dev/null || true
  if [[ "${VEKTRA_AI_METER_UPDATE:-0}" == "1" ]]; then
    log "Restarting panel indicator..."
  else
    log "Starting panel indicator..."
  fi
  if "$BIN_DIR/ai-meter" reboot >/dev/null 2>&1; then
    ok "Panel indicator running — look in your top-bar status area"
  else
    nohup "$BIN_DIR/ai-meter" run >/dev/null 2>&1 &
    ok "Panel indicator running — look in your top-bar status area"
  fi
fi