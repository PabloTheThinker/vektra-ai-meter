# Changelog

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