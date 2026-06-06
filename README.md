# Vektra AI Meter

Top-bar AI usage meter for Linux. Track **Grok Build**, **Codex**, and **Claude Code** from local session data — no API keys, no cloud.

One command from Vektra installs everything: Python package, system dependencies (via `sudo apt` when needed), **GTK4 layer-shell** build on Wayland, autostart, and launch. PySide6 (Qt) powers the tray; the integrated dropdown anchors to the top panel like CodexBar on macOS.

## Install

```bash
curl -fsSL https://vektraindustries.com/ai-tracker/install | bash
```

That single command installs system packages (may prompt for your password once on Ubuntu/Pop!_OS), builds the integrated dropdown on Wayland, enables autostart, and starts the meter. No follow-up steps.

Installs into `~/.local/share/vektra-ai-meter/venv`, puts `ai-meter` on your PATH, and launches the panel indicator.

## What you get

- **Top-bar tray icon** in your panel status area (COSMIC, GNOME, KDE, Xfce)
- **Live quota percentages** — Codex 5h/7d limits, Grok context window (refreshes every 15s)
- **CodexBar-style panel** — click the tray icon for progress bars, reset hints, and per-provider breakdown
- **Integrated top-bar dropdown (Wayland)** — GTK4 layer-shell popup anchored under the panel (not a separate Qt window)
- **Dynamic tray meter** — mini bar icon shows usage at a glance (works on Wayland without theme icons)
- **Autostart** on login (XDG desktop entry + systemd user service)
- **Local snapshot** at `~/.local/share/vektra-ai-meter/snapshot.json`

After install, the meter starts automatically — you do not need to run `ai-meter run` manually.

## Commands

```bash
ai-meter status
ai-meter reboot       # restart the top-bar indicator
ai-meter integrate    # diagnose integrated dropdown (rarely needed)
ai-meter update
ai-meter snapshot --write --pretty
ai-meter print
ai-meter config --autostart true
ai-meter run          # only if autostart is off
```

### Integrated dropdown (Wayland / COSMIC)

After install, `ai-meter status` should show `integrated_popup: true`. The installer handles this automatically on Wayland. If something failed (e.g. sudo was skipped), re-run the same install command. X11 desktops use the Qt panel fallback.

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