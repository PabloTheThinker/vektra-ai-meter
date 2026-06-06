# Changelog

## [2026-06-06] — CodexBar-inspired panel polish (v0.2.8)

### Changed
- Refined popover: drop shadow, provider accent bars, brand badges, summary pills.
- Quota rows match CodexBar layout — window title, reset countdown, thin bar, bold %.
- Humanized window labels (`5-hour window`, `Weekly`, `Context window`).
- Header refresh ↻ + close ✕; footer shows `Updated Ns ago`.
- Provider subtitles show project + model; plan badge for Codex.

## [2026-06-06] — Panel dropdown + close button

### Changed
- Usage panel drops down from the top-bar tray icon with an upward caret (CodexBar-style).
- Replaced **Quit** with a header **×** close button — closes the panel only; tray keeps running.

## [2026-06-06] — `ai-meter reboot` command

### Added
- `ai-meter reboot` — restarts the top-bar indicator via systemd (or direct launch fallback).

### Changed
- `ai-meter update` restart path now uses the shared reboot logic.

## [2026-06-06] — Linux top-bar parity: autostart, limits UX, Wayland panel

### Added
- `ai-meter status` — shows running pid, autostart, desktop entry, and systemd user service state.
- Systemd user service (`vektra-ai-meter.service`) alongside XDG autostart for reliable login startup.
- Single-instance lock so autostart and manual `ai-meter run` never spawn duplicates.
- CodexBar-style rich tray tooltip with per-provider quota lines (5h, 7d, Context %).
- Panel shows remaining %, token counts (e.g. `154.7K / 200K`), plan type, and reset countdowns.

### Fixed
- Wayland/COSMIC panel: removed tray anchor transient window (source of grabbing-popup errors).
- Click-away close via global event filter instead of `WindowDeactivate` / `Qt.Popup`.

### Changed
- `ai-meter config` syncs desktop + systemd autostart entries.
- Install script configures autostart automatically — no manual `ai-meter run` after login.

### Verify
```bash
ai-meter update
ai-meter status
ai-meter snapshot --write --pretty
# Click tray icon in top-bar status area
```

## [2026-06-06] — Wayland panel fix (no grabbing popup)

### Fixed
- COSMIC/Wayland `Failed to create grabbing popup` — panel now uses a stay-on-top Tool window with a tray anchor transient parent instead of `Qt.Popup`.
- Removed `QMenu` context menu (also broken on Wayland); Refresh/Quit live in the panel.
- Panel auto-hides on focus loss; positions near tray or top-right status area fallback.

## [2026-06-06] — CodexBar-style usage panel and Wayland tray fixes

### Added
- Custom popup panel with per-provider progress bars, reset hints, Refresh/Quit actions.
- Dynamic tray icon: mini multi-bar meter tinted by usage (inspired by CodexBar).

### Fixed
- `QSystemTrayIcon::setVisible: No Icon set` on desktops without Freedesktop theme icons.
- Wayland `Failed to create grabbing popup` by replacing `QMenu.popup()` with a Qt popup panel.

### Changed
- Left/right tray click opens the usage panel; context menu kept as a minimal fallback.

## [2026-06-06] — Real-time usage limits and percentages

### Added
- Tray label and menu now show live quota percentages (Codex 5h/7d windows, Grok context window).
- Snapshot `summary.peak_percent` / `highlights` and per-provider `limits` arrays.

### Fixed
- Codex rate-limit parsing ignored valid 5h/7d data when a newer `premium` token event had empty windows.

### Changed
- Top-bar refresh interval reduced to 15s for nearer real-time updates.

### Verify
```bash
ai-meter snapshot --write --pretty
ai-meter update
```