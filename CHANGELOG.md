# Changelog

## [2026-06-06] — layer-shell build without vapigen (v0.3.4)

### Fixed
- `ai-meter update` no longer fails when `vapigen` is missing — meson builds gtk4-layer-shell with `-Dvapi=false` (Python GI only needs introspection, not Vala).
- Stale meson build dirs are wiped and reconfigured on failure.
- Update continues with Qt panel fallback if layer-shell build fails instead of aborting.

### Verify
```bash
ai-meter update
ai-meter status
# integrated_popup: true on Wayland after successful build
```

## [2026-06-06] — Smooth panel + faster refresh (v0.3.3)

### Fixed
- Panel no longer freezes the tray — snapshot collection runs on a background thread.
- Qt panel updates in-place instead of destroying/recreating widgets every 15s.
- Removed expensive `QGraphicsDropShadowEffect` that caused repaint stutter.
- Codex collector no longer double-scans all rollout logs; rate limits parsed in one pass.
- Grok/Claude collectors use tail reads and cap recent file scans.

### Changed
- GTK integrated popup refreshes only when visible; skips rebuild when data unchanged.
- Tray icon caches live bar overlays; footer "Updated Ns ago" ticks without full refresh.
- Polished panel UX: provider badges, accent bars, hover states, smoother progress rows.

### Verify
```bash
ai-meter update
ai-meter status
# Open tray panel — should feel smooth while scrolling and refreshing
```

## [2026-06-06] — Installer git sync fix (v0.3.2)

### Fixed
- Re-run install no longer fails when `~/.local/share/vektra-ai-meter/app` has stale local changes or untracked files from older installs — uses `git reset --hard` + `git clean` instead of `git pull`.
- `ai-meter update` uses the same sync strategy.

### Verify
```bash
curl -fsSL https://vektraindustries.com/ai-tracker/install | bash
```

## [2026-06-06] — True one-command install (v0.3.1)

### Changed
- `curl -fsSL https://vektraindustries.com/ai-tracker/install | bash` now installs apt packages (sudo once), builds gtk4-layer-shell on Wayland, configures autostart, and reboots the meter — no follow-up commands.
- `ai-meter update` also ensures integrated dropdown is built on Wayland after upgrading.

### Verify
```bash
curl -fsSL https://vektraindustries.com/ai-tracker/install | bash
ai-meter status
# integrated_popup: true on Wayland
```

## [2026-06-06] — Full integrated top-bar experience (v0.3.0)

### Added
- **GTK4 layer-shell popup** — macOS/CodexBar-style dropdown anchored to the top panel on Wayland (COSMIC, Sway, KDE).
- `ai-meter popup-server` — integrated dropdown process (auto-started by `ai-meter run`).
- `ai-meter integrate` / `ai-meter integrate --build` — check setup or build gtk4-layer-shell into `~/.local`.
- Installer builds **gtk4-layer-shell** when GTK4 dev headers are present; prints setup steps otherwise.
- `ai-meter status` reports `integrated_popup`, `popup_server_running`, and full `integration` block.
- Click-away close on integrated popup via transparent layer-shell backdrop.

### Changed
- On Wayland + layer-shell: tray click opens integrated popup instead of a separate Qt window.
- Qt panel remains as fallback on X11 or when layer-shell is unavailable.
- `ai-meter reboot` stops orphaned popup-server processes before systemd restart.

### Verify
```bash
sudo apt install -y pkg-config libgtk-4-dev libwayland-dev wayland-protocols \
  gobject-introspection libgirepository-2.0-dev python3-gi gir1.2-gtk-4.0
ai-meter integrate --build
ai-meter reboot
ai-meter status
# integrated_popup: true, popup_server_running: true
```

## [2026-06-06] — Generated tray icon + top-bar dropdown integration (v0.2.9)

### Added
- Generated Vektra tray icon assets (`tray-icon-22/32/64.png`) bundled with the package.
- `VEKTRA_TOP_BAR_HEIGHT` env var (default `36`) to align dropdown under your panel.

### Fixed
- Panel uses `Qt.Tool` surface flags — drops from top bar instead of opening as a separate app window.
- Dropdown anchors flush under the status area / tray icon on Wayland (COSMIC).

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