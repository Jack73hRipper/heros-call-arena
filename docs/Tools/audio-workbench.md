# Audio Workbench

> **Last updated:** March 2, 2026  
> **Status:** Implemented  
> **Stack:** React 18 + Vite + Express micro-API  
> **Port:** UI on 5210, API on 5211

---

## Overview

The Audio Workbench is a standalone dev tool for testing, categorizing, and managing all sound effects in the Arena project. It reads and writes `client/public/audio-effects.json` directly — hit Save and your changes are live the next time the game loads.

## Quick Start

```bash
start-audio-workbench.bat
```

Or manually:
```bash
cd tools/audio-workbench
npm install
start /B node server.js    # API server on :5211
npx vite                    # UI on :5210
```

## Features

### 1. Sound Browser (📁 tab)

- **Browse all audio files** on disk across all category directories (combat, skills, buffs, ui, items, events, movement, music)
- **Play any sound** with one click — waveform visualization shows amplitude bars
- **Filter** by category, mapped/unmapped/broken status, and free-text search
- **Sort** by name, category, or file size
- **Quick-map** orphaned files — adds them to `_soundFiles` with one click
- **Validation badges:**
  - **MAPPED** (green) — file is in `_soundFiles` and the file exists on disk
  - **UNMAPPED** (yellow) — file exists on disk but isn't referenced in the config
  - **BROKEN** (red) — key exists in `_soundFiles` but the file is missing from disk

### 2. Mapping Editor (🎛️ tab)

- **Section sidebar** — navigate between Sound Files registry, Combat, Skills, Environment, Events, UI, and Music sections
- **Sound Files Manager** — add/remove `_soundFiles` entries, play any key, compare sounds
- **Event mapping editor** — expand any event mapping to:
  - **Adjust volume** (0–1 slider)
  - **Adjust pitch variance** (0–20% slider)
  - **Change the sound key** for single-key mappings
  - **Manage variant arrays** — add/remove sounds from variant groups, preview each variant individually
  - **Play random variant** — simulates the game's random-pick behavior

### 3. Compare Panel (⚖️ tab)

- **A/B testing** — add up to 6 sounds from the Browser or Editor, then toggle between them
- **Real-time adjustments** — volume and pitch variance sliders affect playback immediately
- **Loop mode** — toggle looping to compare ambient or long sounds
- **Next (A/B)** — cycles through sounds sequentially
- **Random** — picks a random sound from the compare list (simulates variant behavior)

### 4. Asset Library (📦 tab)

- **Browse the full Helton Yan Pixel Combat sound pack** (~1000+ WAV files) located in `Assets/Audio/`
- **Grouped by sound name** — variants of the same sound appear in collapsible groups
- **Filter** by category (EXPLOSION, MELEE, HIT, CAST, BUFF, PROJECTILE, etc.) and text search
- **Preview** any variant with waveform visualization and inline playback
- **Replace mode** — select an existing game sound key, browse the library, and replace it with one click
- **Import as new** — copy any library sound into a game audio category folder
- **Add to Compare** — send library sounds to the Compare Panel for A/B testing against game sounds

### 5. Save Button (💾)

- **Writes** updated `audio-effects.json` back to `client/public/audio-effects.json`
- **Auto-backup** — creates a timestamped backup before every save, keeps the last 5
- **Unsaved indicator** — yellow dot appears when you have uncommitted changes
- **Instant feedback** — button shows "Saving...", "✓ Saved!", or "✗ Error"

## Architecture

```
tools/audio-workbench/
├── server.js              # Express micro-API for file I/O (~200 lines)
├── package.json
├── vite.config.js         # Port 5210, proxies /api to :5211
├── index.html
└── src/
    ├── main.jsx
    ├── App.jsx            # Root — data loading, save, tab routing
    ├── components/
    │   ├── SoundBrowser.jsx    # File browser & preview panel
    │   ├── MappingEditor.jsx   # Config section editor
    │   ├── ComparePanel.jsx    # A/B comparison panel
    │   ├── AssetLibrary.jsx    # Library browser & import/replace
    │   └── Waveform.jsx        # Web Audio waveform visualization
    └── styles/
        └── workbench.css       # Grimdark-themed styling
```

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/config` | Read `audio-effects.json` |
| POST | `/api/config` | Write updated config (with auto-backup) |
| GET | `/api/sounds` | List all audio files on disk recursively |
| GET | `/api/categories` | List audio subdirectories |
| POST | `/api/import` | Copy a file into a category directory |
| GET | `/api/library` | List all files in the Helton Yan asset library |
| POST | `/api/library/import` | Copy a library file into a game audio category |
| GET | `/audio/*` | Static file serving for game audio playback |
| GET | `/library/*` | Static file serving for asset library preview |

### How Save Works

1. The UI serializes the in-memory config as JSON
2. POST to `/api/config` sends it to the Express server
3. Server creates a backup (`audio-effects.backup-{timestamp}.json`)
4. Server overwrites `client/public/audio-effects.json`
5. Old backups beyond the 5 most recent are pruned
6. The game's Vite dev server hot-serves files from `client/public/`, so changes are available on next page load

## Port Assignments

| Tool | Port |
|------|------|
| Game frontend | 5173 |
| Particle Lab | 5180 |
| Theme Designer | 5200 |
| **Audio Workbench UI** | **5210** |
| **Audio Workbench API** | **5211** |

## Dependencies

- **React 18** + **Vite 5** (matches all other tools)
- **Express 4** — minimal file I/O server
- **cors** — allows the Vite dev server to reach the API
- **Web Audio API** — native browser, no audio libraries
