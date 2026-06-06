# Vektra AI Meter

Vektra Software glance panel for Linux. Track local AI coding agent usage across **Grok Build**, **Codex**, and **Claude Code** from session data on your machine - no API keys, no cloud.

Installs a **panel top-bar indicator** (Ayatana AppIndicator) by default — the same status-area pattern COSMIC, GNOME, and Xfce use for add-ons. Optional frosted desktop card, Waybar, Conky, or eww surfaces share one snapshot.

## Install

```bash
curl -fsSL https://vektraindustries.com/ai-tracker/install | bash
```

Installs `ai-meter` to `~/.local/bin`, enables autostart, and launches the panel indicator in your top bar.

GitHub direct:

```bash
curl -fsSL https://raw.githubusercontent.com/PabloTheThinker/vektra-ai-meter/main/install.sh | bash
```

Re-run anytime to update.

## Quick start

```bash
./install.sh
ai-meter run
```

The default top-bar indicator:
- **Lives in the panel** — compact token count + active sessions beside system icons
- **Click for detail** — Grok, Codex, and Claude breakdown in the menu
- **Autostart** — launches on login via `~/.config/autostart/`

The optional glance panel (`ai-meter widget`) is:
- **Frameless** - rounded frosted card, no title chrome
- **Compact** - small, medium, and large glance sizes
- **Autostart** - launches on login via `~/.config/autostart/`
- **Pinned** - top-right by default (configurable)

### Sizes and placement

```bash
ai-meter config --size small
ai-meter config --size medium
ai-meter config --anchor bottom-right --margin 32
```

### Desktop layer (Wayland)

Pin the meter behind windows on the desktop layer:

```bash
./scripts/install-layer-shell.sh
```

Requires `sudo apt install git meson ninja-build libgtk-4-dev libwayland-dev` first.

## Commands

```bash
ai-meter run
ai-meter topbar
ai-meter widget
ai-meter snapshot --write --pretty
ai-meter print
ai-meter config --interface topbar
ai-meter config --size small
```

Snapshot path: `~/.local/share/vektra-ai-meter/snapshot.json`

## Surfaces

| Surface | Desktop | Command / path |
|---------|---------|----------------|
| **Panel top-bar indicator** | COSMIC, GNOME, Xfce, most DEs with status area | `ai-meter topbar` (default) |
| **GTK glance panel** | COSMIC, GNOME, XFCE, most Wayland/X11 | `ai-meter widget` |
| **Waybar** | Sway, Hyprland, i3 | `widget/waybar/module.sh` |
| **Conky** | X11 WMs | `widget/conky/ai-meter.conkyrc` |
| **eww** | Ricing setups | `widget/eww/` |

## Data sources (read-only)

| Provider | Location | Signals |
|----------|----------|---------|
| **Grok Build** | `~/.grok/sessions/` | model, messages, estimated tokens |
| **Codex** | `~/.codex/sessions/**/rollout-*.jsonl` | tokens, rate limits |
| **Claude Code** | `~/.claude/projects/**/*.jsonl` | per-turn usage, model, session title |

## Layout

```
vektra-ai-meter/
├── cli/ai-meter
├── install.sh
├── src/ai_tracker/
└── widget/
```