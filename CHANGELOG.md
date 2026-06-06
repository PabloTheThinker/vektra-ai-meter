# Changelog

## [2026-06-06] — graceful shutdown kills ghost tray icons (v0.3.16)

### Fixed
- **Duplicate/ghost tray icon.** On `SIGTERM` (systemd stop, `ai-meter reboot`, `pkill`) the process died before Qt could hide the tray, leaving an orphaned StatusNotifier item on the bus. Some panels (notably COSMIC) never prune these, so every ungraceful restart could leave a second, dead icon behind.
- Added `SIGTERM`/`SIGINT` handlers that route into `app.quit()`, plus an `aboutToQuit` cleanup that hides the tray so the StatusNotifier item is unregistered cleanly. A 200ms wakeup timer keeps the Python interpreter ticking so the signal is delivered while Qt is in its native event loop.

### Note
- This prevents *new* ghosts. An icon orphaned by a pre-0.3.16 process persists in the panel's watcher until the panel/applet restarts or you log out — it cannot be cleared by the new process.

### Verify
```bash
ai-meter reboot          # restart a few times
# the status area should show exactly one Vektra icon, not a growing pile
```

## [2026-06-06] — mtime parse cache for Claude/Codex providers (v0.3.15)

### Performance
- The panel re-collects every 15s. The Claude and Codex providers used to **fully re-parse** every session JSONL on every tick (up to 64 + 42 files), even when nothing changed. Steady-state cost was ~2s of CPU per tick — roughly 13% of a core, continuously, in the background.
- Added an **mtime+size keyed parse cache**: a session file that hasn't changed since the last tick returns its parsed record instantly. Only files that actually changed get re-read.
- Measured: steady-state collection dropped from **~2006 ms → ~2.5 ms** per tick (~800×). The first tick after any session changes re-parses only the changed files.
- Output is byte-identical to the previous implementation — the cross-session "latest rate limit / context window" picks are `max`-by-timestamp, which is associative, so per-session bests folded globally equal the old global scan.

### Internal
- `util.cached_by_mtime()` / `util.prune_cache()` — generic per-path parse memoization, pruned to the active scan window each tick.
- Grok already read only the file tail (`iter_jsonl_tail`), so it was left unchanged.

### Verify
```bash
ai-meter snapshot --write --pretty   # numbers unchanged from before
ai-meter status                       # version: 0.3.15
```

## [2026-06-06] — update exits cleanly after restart (v0.3.14)

### Fixed
- `ai-meter update` and `curl | bash` no longer hang after the final ✓ line — bash was waiting on a background `ai-meter run` (Qt event loop). Restart now uses `ai-meter reboot --no-wait` and fully detaches fallback launches (`disown` / `setsid`).
- `install.sh` no longer `pkill`s the running `ai-meter update` command (patterns are scoped to `run` / `popup-server` only).
- Update finish line is shorter: `✓ Panel indicator restarted` (no need to Ctrl+C).

### Verify
```bash
ai-meter update
# Should return to shell immediately after the last ✓ line
```

## [2026-06-06] — COSMIC tray placement without Qt geometry (v0.3.13)

### Fixed
- **COSMIC:** `QSystemTrayIcon.geometry()` is always empty on Wayland — dropdown no longer falls back to the top-right corner. Tray position is estimated from StatusNotifier registration order + `~/.config/cosmic/com.system76.CosmicPanel.Panel` wing layout.
- Layer-shell anchors pick the nearest horizontal edge (RIGHT for status-area icons) so margins stay stable on wide panels.
- Multi-monitor: screen is chosen from cursor / tray center instead of always `primaryScreen()`.

### Changed
- `VEKTRA_TOP_BAR_HEIGHT` is optional on COSMIC — when unset, bar height is inferred from panel size (`XS`→32, `S`→40, …). Explicit env still overrides (e.g. systemd unit).

### Verify
```bash
ai-meter update
# Click tray — panel should open under the Vektra icon in the status area (not pinned top-right)
# ✕, refresh, click-away, re-click tray should all still work
```

## [2026-06-06] — tray-anchored dropdown on COSMIC/Wayland (v0.3.12)

### Fixed
- Panel opened on the wrong screen edge after the fullscreen `Gtk.Overlay` refactor — restored **CodexBar/codexbar-waybar** compact layer-shell window (TOP+RIGHT or TOP+LEFT under tray).
- Qt tray geometry is sent over IPC on every open so the dropdown drops under your actual status-area icon (COSMIC, multi-monitor).
- Separate fullscreen backdrop (dim) + compact panel surface — panel stays readable and above the dim layer.

### Tuning
- `VEKTRA_TOP_BAR_HEIGHT` (default `36`) — gap below top panel; raise to `40` on COSMIC if the panel clips under the bar.

### Verify
```bash
ai-meter update
# Click tray icon — panel should appear directly under the meter icon, top-right area
```

## [2026-06-06] — clean update output + single version source (v0.3.11)

### Fixed
- `ai-meter update` now runs the same `install.sh` as the curl installer — matching ✓/→ output, no confusing `(package declares 0.3.6)` line.
- Version comes from one place: `pyproject.toml` → pip metadata (`importlib.metadata`); stale hardcoded `__version__` removed.
- Update shows `already up to date` when the package version did not change.

### Verify
```bash
ai-meter update
# Should end with: Package: vektra-ai-meter 0.3.11 (already up to date)
ai-meter status   # version field matches
```

## [2026-06-06] — fix stuck unclickable panel (v0.3.10)

### Fixed
- Replaced dual layer-shell windows (fullscreen backdrop + panel) with a **single** fullscreen `Gtk.Overlay` window — backdrop was stacking above the panel and eating all clicks.
- Hide/show now uses `set_opacity(0/1)` + `can_target` on one mapped surface (no `set_visible(False)` crash, actually disappears visually).

### Verify
```bash
ai-meter update
# ✕, ↻ refresh, and click-away should all work; tray reopens after dismiss
```

## [2026-06-06] — popup server survives hide / click-away (v0.3.9)

### Fixed
- **Root cause:** `set_visible(False)` on layer-shell overlay windows crashed the GTK popup server (zombie PID, dead socket). Panel now hides via CSS opacity + `can_target(False)` while keeping surfaces mapped.
- `PopupApp.hold()` keeps the GTK application alive as a safety net.
- `popup_server_running()` now requires a live PID (not zombie) **and** a responsive Unix socket.
- Tray restarts the popup server forcibly when `show` IPC fails instead of trusting a stale PID file.

### Verify
```bash
ai-meter update
# Open → click away → click tray (panel reopens; popup.pid process stays alive, not Z)
```

## [2026-06-06] — fix panel not reopening after click-away (v0.3.8)

### Fixed
- Tray click now always sends `show` instead of `toggle`, so a compositor-dismissed panel (click-away) no longer leaves internal state stuck "open".
- Popup syncs `visible` from GTK `notify::visible` when the layer-shell surface is hidden externally.
- `toggle()` and `show()` base open/close on actual `window.get_visible()`, not a stale flag.
- Show is deferred to the GTK main loop via `idle_add` so layer-shell remap is reliable after hide.

### Verify
```bash
ai-meter update
# Open panel → click away to close → click tray icon (should reopen)
```

## [2026-06-06] — popup reopen + live Claude sessions (v0.3.7)

### Fixed
- GTK dropdown reopen after closing with ✕: `show()` now calls `set_visible(True)` before `present()` (layer-shell windows stayed hidden after close).
- Popup collects a fresh snapshot in the background whenever it opens, so Claude/Grok/Codex data is current instead of up to 15s stale.
- Tray click kicks off an immediate refresh before toggling the integrated popup.
- Claude active sessions now come from live `~/.claude/sessions/*.json` PIDs instead of a 1-hour jsonl mtime guess; brand-new sessions count even before token usage is logged.

### Verify
```bash
ai-meter update
# Open dropdown → close with ✕ → click tray icon again (should reopen)
# With Claude terminals open, panel should show matching active session count
```

## [2026-06-06] — update auto-restart uses fresh code (v0.3.6)

### Fixed
- `ai-meter update` now re-invokes `ai-meter reboot` as a subprocess after pip upgrade — restart always uses the newly installed code, not stale in-memory modules from before the upgrade.
- Integration rebuild during update also runs via the fresh CLI (`ai-meter integrate --build`).
- Update returns a non-zero exit code if auto-restart fails, with a clear `ai-meter reboot` hint.

### Verify
```bash
ai-meter update
# should end with reboot success + popup_server_running: true
```

## [2026-06-06] — reboot + popup-server fix (v0.3.5)

### Fixed
- `ai-meter reboot` now fully stops tray + popup, clears stale locks, and waits for a new PID.
- Integrated popup server launches via `python -c` import (fixes broken `-m` relative-import crash).
- Popup server gets `LD_PRELOAD` + `VEKTRA_LAYER_SHELL_PRELOADED` in env (fixes execve breaking `python -c`).
- Popup server processes are killed correctly on reboot (system python + module patterns).
- Reboot waits for integrated dropdown server to come up on Wayland.
- `ai-meter run` no longer spawns `systemctl enable --now` on every start (was racing reboot).

### Verify
```bash
ai-meter update
ai-meter reboot
ai-meter status
# popup_server_running: true on Wayland
```

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