# Vektra AI Meter

Vektra Software glance panel for Linux. Track local AI coding agent usage across **Grok Build**, **Codex**, and **Claude Code** from session data on your machine - no API keys, no cloud.

One frosted desktop card, three glance sizes, and optional Waybar, Conky, or eww surfaces fed by a shared snapshot.

## Install

```bash
curl -fsSL https://vektraindustries.com/ai-tracker/install | bash
```

Installs `ai-meter` to `~/.local/bin`, enables autostart, and launches the glance panel.

GitHub direct:

```bash
curl -fsSL https://raw.githubusercontent.com/PabloTheThinker/vektra-ai-meter/main/install.sh | bash
```

Re-run anytime to update.

## Quick start

```bash
./install.sh
ai-meter widget
```

The glance panel is:
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
ai-meter widget
ai-meter snapshot --write --pretty
ai-meter print
ai-meter config --size small
```

Snapshot path: `~/.local/share/vektra-ai-meter/snapshot.json`

## Surfaces

| Surface | Desktop | Command / path |
|---------|---------|----------------|
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