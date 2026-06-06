# Vektra AI Meter

Top-bar AI usage meter for Linux. Track **Grok Build**, **Codex**, and **Claude Code** from local session data — no API keys, no cloud.

One Python package. One install command. PySide6 (Qt) ships via pip — no GTK, AppIndicator, or layer-shell packages to hunt down.

## Install

```bash
curl -fsSL https://vektraindustries.com/ai-tracker/install | bash
```

Requires only **Python 3**, **git**, and **python3-venv** (standard on Pop!_OS / Ubuntu desktop):

```bash
sudo apt install python3 python3-venv git
```

Installs into `~/.local/share/vektra-ai-meter/venv`, puts `ai-meter` on your PATH, and launches the panel indicator.

## What you get

- **Top-bar tray icon** in your panel status area (COSMIC, GNOME, KDE, Xfce)
- **Live quota percentages** — Codex 5h/7d limits, Grok context window (refreshes every 15s)
- **CodexBar-style panel** — click the tray icon for progress bars, reset hints, and per-provider breakdown
- **Dynamic tray meter** — mini bar icon shows usage at a glance (works on Wayland without theme icons)
- **Autostart** on login (XDG desktop entry + systemd user service)
- **Local snapshot** at `~/.local/share/vektra-ai-meter/snapshot.json`

After install, the meter starts automatically — you do not need to run `ai-meter run` manually.

## Commands

```bash
ai-meter status
ai-meter reboot       # restart the top-bar indicator
ai-meter update
ai-meter snapshot --write --pretty
ai-meter print
ai-meter config --autostart true
ai-meter run          # only if autostart is off
```

### Update without reinstalling

```bash
ai-meter update
```

Pulls the latest code from GitHub, upgrades the venv, and restarts the panel indicator. Use `ai-meter update --no-restart` to skip the restart.

## Manual install (developers)

```bash
git clone https://github.com/PabloTheThinker/vektra-ai-meter.git
cd vektra-ai-meter
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
ai-meter run
```

## Data sources (read-only)

| Provider | Location |
|----------|----------|
| **Grok Build** | `~/.grok/sessions/` |
| **Codex** | `~/.codex/sessions/**/rollout-*.jsonl` |
| **Claude Code** | `~/.claude/projects/**/*.jsonl` |

## Layout

```
vektra-ai-meter/
├── pyproject.toml
├── install.sh
└── src/vektra_ai_meter/
    ├── cli.py
    ├── topbar.py
    ├── snapshot.py
    └── providers/
```