# Changelog

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