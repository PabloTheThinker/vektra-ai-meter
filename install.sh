#!/usr/bin/env bash
#
# Vektra AI Meter — one-line Linux installer
#
#   curl -fsSL https://vektraindustries.com/ai-tracker/install | bash
#
# Or directly from GitHub:
#   curl -fsSL https://raw.githubusercontent.com/PabloTheThinker/vektra-ai-meter/main/install.sh | bash
#
set -euo pipefail

REPO_URL="${VEKTRA_AI_METER_REPO_URL:-https://github.com/PabloTheThinker/vektra-ai-meter.git}"
INSTALL_DIR="${VEKTRA_AI_METER_INSTALL_DIR:-${HOME}/.local/share/vektra-ai-meter/app}"
BRANCH="${VEKTRA_AI_METER_BRANCH:-main}"

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  MAGENTA='\033[0;35m'
  CYAN='\033[0;36m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  MAGENTA='' CYAN='' BOLD='' NC=''
fi

echo ""
echo -e "${MAGENTA}${BOLD}Vektra AI Meter${NC}"
echo -e "${CYAN}Top-bar panel meter for Grok, Codex, and Claude${NC}"
echo ""

if ! command -v git >/dev/null 2>&1; then
  echo "git is required. Install with: sudo apt install git"
  exit 1
fi

mkdir -p "$(dirname "$INSTALL_DIR")"

if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo -e "${CYAN}→${NC} Updating existing install..."
  git -C "$INSTALL_DIR" fetch origin "$BRANCH"
  git -C "$INSTALL_DIR" checkout "$BRANCH"
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
else
  echo -e "${CYAN}→${NC} Downloading..."
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

export VEKTRA_AI_METER_LAUNCH_WIDGET="${VEKTRA_AI_METER_LAUNCH_WIDGET:-1}"
exec bash "$INSTALL_DIR/scripts/bootstrap.sh"