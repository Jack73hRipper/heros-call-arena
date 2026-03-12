# Project Cleanup Plan

**Created:** March 4, 2026
**Current state:** ~31,400 files / ~1,358 MB — Phases 1 & 2 complete (572 MB recovered, ~19,685 files eliminated)

---

## Phase 1 — Instant Wins (Safe, Zero Risk) ✅ COMPLETED

**Completed:** March 4, 2026
**Result:** Removed 252 files, recovered 250.2 MB (51,092 → 50,840 files / 1,930 → 1,680 MB)

| Step | What was removed | Files | Size |
|------|-----------------|-------|------|
| 1A | `client/dist/` (Vite build output) | 128 | 243.7 MB |
| 1B | `.pytest_cache/` | 4 | <0.1 MB |
| 1C | `server/**/__pycache__/` (8 directories) | 121 | 6.1 MB |
| **Total** | | **253** | **~250 MB** |

**Priority:** ~~HIGH — Do this now~~ DONE
**Estimated recovery:** ~250 MB, ~130 files
**Risk:** None — everything here is recreated automatically

### 1A. Delete `client/dist/`

This is a Vite build output folder. It's just a compiled copy of your frontend + all your public assets (audio, sprites). Already in `.gitignore`.

```powershell
Remove-Item -Recurse -Force "client\dist"
```

- **Recovers:** ~244 MB, 128 files
- **To rebuild later:** `cd client && npm run build`
- **Note:** You do NOT need `dist/` for development — `npm run dev` serves directly from `src/` and `public/`

### ~~1B. Delete all tool `node_modules/`~~ — SKIPPED

> **Not practical** — tools are used daily. Deleting and reinstalling every day wastes time.
> The real fix is **Phase 2 (npm workspaces)** which keeps tools working while cutting ~330 MB permanently.

### 1B. Delete `.pytest_cache/`

Pytest's internal cache. Rebuilt automatically on next test run.

```powershell
Remove-Item -Recurse -Force ".pytest_cache"
```

- **Recovers:** negligible (4 files)

### 1C. Clean Python `__pycache__/` directories

Compiled `.pyc` bytecode files. Python recreates them automatically on import.

```powershell
Get-ChildItem -Path "server" -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
```

- **Recovers:** ~6 MB

---

## Phase 2 — Consolidate Tool Dependencies (The Big Win) ✅ COMPLETED

**Completed:** March 4, 2026
**Result:** Consolidated 9 separate `node_modules/` into 1 shared workspace — recovered 322 MB, eliminated 19,432 files

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| `node_modules` directories | 9 | 1 | -8 |
| Total size | 374.1 MB | 52.1 MB | **322 MB** |
| Total files | 31,940 | 12,508 | **19,432 files** |

### What Was Done

1. **Created `tools/package.json`** — npm workspace root referencing all 9 tools
2. **Deleted all 9 individual `node_modules/`** — removed 374.1 MB of duplicate packages
3. **Ran `npm install` from `tools/`** — created single shared `node_modules/` (52.1 MB, 175 packages)
4. **Updated all 9 `start-*.bat` files** — each now runs `npm install` from the `tools/` workspace root before `cd`-ing into the tool subdirectory
5. **Verified all dependencies resolve** — react, react-dom, vite, express, cors, concurrently all confirmed working from every tool subdirectory

### Files Changed

| File | Change |
|------|--------|
| `tools/package.json` | Created — workspace root |
| `tools/package-lock.json` | Created — lockfile |
| `tools/node_modules/` | Created — shared packages |
| `start-audio-workbench.bat` | Updated — install from `tools/` root |
| `start-cave-automata.bat` | Updated — install from `tools/` root |
| `start-dungeon-wfc.bat` | Updated — install from `tools/` root |
| `start-enemy-forge.bat` | Updated — install from `tools/` root |
| `start-item-forge.bat` | Updated — install from `tools/` root |
| `start-module-decorator.bat` | Updated — install from `tools/` root |
| `start-particle-lab.bat` | Updated — install from `tools/` root |
| `start-sprite-cataloger.bat` | Updated — install from `tools/` root |
| `start-theme-designer.bat` | Updated — install from `tools/` root |

### Problem (Reference)

All 9 tools used nearly identical dependencies:

| Tool | Dependencies |
|------|-------------|
| cave-automata | react, react-dom, vite, @vitejs/plugin-react |
| dungeon-wfc | react, react-dom, vite, @vitejs/plugin-react |
| module-decorator | react, react-dom, vite, @vitejs/plugin-react |
| particle-lab | react, react-dom, vite, @vitejs/plugin-react |
| sprite-cataloger | react, react-dom, vite, @vitejs/plugin-react |
| theme-designer | react, react-dom, vite, @vitejs/plugin-react |
| audio-workbench | react, react-dom, vite, @vitejs/plugin-react, express, cors, concurrently |
| enemy-forge | react, react-dom, vite, @vitejs/plugin-react, express, cors |
| item-forge | react, react-dom, vite, @vitejs/plugin-react, express, cors |

### Solution Applied: npm Workspaces

`tools/package.json`:
```json
{
  "name": "arena-tools",
  "private": true,
  "workspaces": [
    "audio-workbench",
    "cave-automata",
    "dungeon-wfc",
    "enemy-forge",
    "item-forge",
    "module-decorator",
    "particle-lab",
    "sprite-cataloger",
    "theme-designer"
  ]
}
```

To reinstall from scratch: `cd tools && npm install`

---

## Phase 3 — Archive Design Source Files (Low Effort)

**Priority:** LOW — Do when convenient
**Estimated recovery:** ~310 MB from working directory
**Risk:** None if you keep a backup

### 3A. `Assets/Audio/` — Duplicate of `client/public/audio/`

All 80 sound effects and 11 music tracks in `Assets/Audio/Selected/` and `Assets/Audio/Music/` are already copied into `client/public/audio/` (which is where the game actually loads them from).

- `Assets/Audio/Selected/` — 80 files, ~150 MB → all present in `client/public/audio/`
- `Assets/Audio/Music/` — 11 files, ~50 MB → all present in `client/public/audio/music/`

**Options:**
- **Option A:** Delete `Assets/Audio/` entirely (the game uses `client/public/audio/`)
- **Option B:** Move `Assets/Audio/` to an external backup/cloud drive as "original source" archive
- **Recovers:** ~200 MB

### 3B. `Assets/Character Sheet/` — GIMP Source Files

13 `.xcf` files totaling ~98 MB. These are the raw GIMP design files for your spritesheets. The game uses the compiled `client/public/spritesheet.png` (8.7 MB).

**Options:**
- Keep them if you plan to edit sprites in GIMP
- Move to external storage if you're done editing
- **Recovers:** ~98 MB

### 3C. `Assets/Walls and Objects/` — Source PSD Files

PSD files + license for wall/object art assets. Small (~1.2 MB) — not urgent.

---

## Phase 4 — Optional Deep Clean (Future Consideration)

**Priority:** LOWEST — Only if you want a minimal footprint
**Risk:** Varies

### 4A. Trim `client/node_modules/`

At 670 MB and 12,401 files, this is the single largest directory. Unlike the tools, you can't easily delete this since you're actively developing. But you could:

- Run `npm prune` to remove unused packages
- Audit with `npx depcheck` to find unused dependencies in `package.json`
- Consider switching to `pnpm` (uses hard links, saves ~50-70% disk space)

### 4B. Slim Down `.venv/`

At 74 MB and 5,644 files, this is modest. You could:

- Recreate it fresh: `python -m venv .venv --clear && pip install -r requirements.txt`
- This removes any leftover packages from earlier experiments

### 4C. Add `client/dist/` cleanup to workflow

Add to the start scripts or a `clean.bat`:

```bat
@echo off
echo Cleaning build artifacts...
if exist client\dist rmdir /s /q client\dist
if exist .pytest_cache rmdir /s /q .pytest_cache
echo Done.
```

---

## Quick Reference: What's Safe to Delete vs. What to Keep

### SAFE TO DELETE (regenerated automatically)

| Path | Recreated By |
|------|-------------|
| `client/node_modules/` | `cd client && npm install` |
| `client/dist/` | `cd client && npm run build` |
| `tools/*/node_modules/` | `cd tools/<name> && npm install` |
| `.venv/` | `python -m venv .venv && pip install -r server/requirements.txt` |
| `.pytest_cache/` | Auto-created on next `pytest` run |
| `server/**/__pycache__/` | Auto-created on next Python import |

### KEEP — Your Real Project

| Path | What It Is |
|------|-----------|
| `server/app/` | Python backend source code |
| `server/configs/` | Game configuration (maps, classes, enemies, items, etc.) |
| `server/tests/` | 2,515 tests across 57 files |
| `server/data/players/` | Saved player profiles |
| `client/src/` | React frontend source code |
| `client/public/` | Game assets (audio, sprites, particles) |
| `client/electron/` | Electron desktop wrapper |
| `client/package.json` | Frontend dependency recipe |
| `client/vite.config.js` | Build configuration |
| `tools/` (source files) | 9 development tools + atlas generator |
| `tools/*/package.json` | Tool dependency recipes |
| `docs/` | Project documentation |
| `Assets/` | Design source files (GIMP, PSD) |
| `server/requirements.txt` | Python dependency recipe |
| `*.bat` files | Launch scripts |
| `README.md` | Project readme |

---

## One-Shot Cleanup Script (Phase 1 — Safe Deletions)

Save as `cleanup.bat` in the project root, or run these commands in PowerShell:

```powershell
# Phase 1 — Safe cleanup (everything regenerates automatically)
Write-Host "Cleaning build artifacts and dependency caches..."

# 1A: Vite build output
if (Test-Path "client\dist") { Remove-Item -Recurse -Force "client\dist"; Write-Host "  Removed client\dist" }

# 1B: Pytest cache
if (Test-Path ".pytest_cache") { Remove-Item -Recurse -Force ".pytest_cache"; Write-Host "  Removed .pytest_cache" }

# 1C: Python bytecode caches
Get-ChildItem -Path "server" -Recurse -Directory -Filter "__pycache__" | ForEach-Object { Remove-Item -Recurse -Force $_.FullName; Write-Host "  Removed $($_.FullName)" }

Write-Host "`nDone! Recovered ~250 MB."
Write-Host "To rebuild client dist: cd client && npm run build"
```

> **Note:** Tool `node_modules/` are NOT deleted here since tools are used daily.
> Run Phase 2 (npm workspaces) to consolidate them instead — saves ~330 MB permanently with no workflow disruption.
