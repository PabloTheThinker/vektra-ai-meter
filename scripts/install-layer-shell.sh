#!/usr/bin/env bash
set -euo pipefail

# Installs gtk4-layer-shell to ~/.local for Vektra desktop-layer glance panels.
# Requires: git meson ninja libgtk-4-dev libwayland-dev

PREFIX="${HOME}/.local"
BUILD_DIR="${HOME}/.cache/vektra-ai-meter/gtk4-layer-shell"

for cmd in git meson ninja pkg-config; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing dependency: $cmd"
    echo "Install with:"
    echo "  sudo apt install git meson ninja-build libgtk-4-dev libwayland-dev"
    exit 1
  fi
done

mkdir -p "$(dirname "$BUILD_DIR")"
if [[ ! -d "$BUILD_DIR/.git" ]]; then
  git clone --depth 1 https://github.com/wmww/gtk4-layer-shell "$BUILD_DIR"
fi

meson setup "$BUILD_DIR/build" "$BUILD_DIR" --prefix="$PREFIX" --libdir=lib
ninja -C "$BUILD_DIR/build"
ninja -C "$BUILD_DIR/build" install

echo
echo "Installed gtk4-layer-shell to $PREFIX"
echo "Restart the widget:"
echo "  pkill -f 'ai-meter widget' || true"
echo "  ai-meter widget"