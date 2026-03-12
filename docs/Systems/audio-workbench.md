# Audio Workbench System

> **Last updated:** March 2, 2026  
> **Status:** Implemented  
> **Stack:** React 18 + Vite + Express micro-API  
> **Pattern:** Standalone dev tool — matches Particle Lab / Theme Designer pattern  
> **Ports:** UI on 5210, API on 5211

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [File Map](#3-file-map)
4. [Data Flow](#4-data-flow)
5. [API Server](#5-api-server)
6. [Sound Browser Panel](#6-sound-browser-panel)
7. [Mapping Editor Panel](#7-mapping-editor-panel)
8. [Compare Panel](#8-compare-panel)
9. [Asset Library Panel](#9-asset-library-panel)
10. [Waveform Visualization](#10-waveform-visualization)
11. [Validation Engine](#11-validation-engine)
12. [Save System & Backup Strategy](#12-save-system--backup-strategy)
13. [Audio Playback Engine](#13-audio-playback-engine)
14. [Relationship to Game Audio System](#14-relationship-to-game-audio-system)
15. [Port Assignments](#15-port-assignments)
16. [Quick Start](#16-quick-start)

---

## 1. Overview

The Audio Workbench is a standalone developer tool for testing, categorizing, and managing all sound effects and music in the Arena project. It provides a visual interface for editing `audio-effects.json` — the game's data-driven sound configuration — without ever touching JSON by hand.

**Key principles:**

- **Direct config editing** — Reads and writes `client/public/audio-effects.json` directly. Save once, changes are live on next game load.
- **Full disk awareness** — Scans `client/public/audio/` recursively to detect all files, including orphaned (unmapped) and broken (missing) references.
- **Non-destructive** — Creates timestamped backups before every save. Keeps the last 5 backups automatically.
- **A/B comparison** — Compare up to 6 sounds side-by-side with real-time volume/pitch adjustments.
- **Asset library browser** — Browse the full Helton Yan sound pack (~1000+ WAV files), preview any sound, and import/replace game sounds without touching files manually.
- **Zero game dependencies** — The tool is fully standalone. It does not import any game code, does not need the game server running, and uses raw Web Audio API for playback.

---

## 2. Architecture

The tool runs as two processes:

```
┌─────────────────────────────────┐      ┌───────────────────────────────────┐
│  Vite Dev Server (port 5210)    │      │  Express API Server (port 5211)   │
│  React 18 SPA                   │─────▶│  File I/O bridge                  │
│  Web Audio playback             │ /api │  Static audio file serving        │
│  Waveform visualization         │      │  Asset library scanning           │
│  Asset Library browser           │      │  Config read/write + backup       │
└─────────────────────────────────┘      └───────────────────────────────────┘
         │                                          │
         │  fetch(/audio/...)                       │  fs.readFileSync / writeFileSync
         │  fetch(/library/...)                     │
         ▼                                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  client/public/audio/             client/public/audio-effects.json  │
│  110 audio files (99 WAV + 11 MP3)   ~415 line JSON config         │
│  8 category directories                                             │
└─────────────────────────────────────────────────────────────────────┘
         │
         │  /library/* static serve
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Assets/Audio/Helton Yan's Pixel Combat - Single Files/             │
│  ~1000+ WAV files (full sound pack, read-only)                      │
│  Categories: EXPLOSION, MELEE, HIT, CAST, BUFF, PROJECTILE, etc.   │
└─────────────────────────────────────────────────────────────────────┘
```

The Express API is needed because browsers cannot write to disk. It's a ~200-line server that provides:
- Static file serving for audio playback and library previews
- JSON config read/write with auto-backup
- Recursive directory scanning for file and library discovery
- Asset library import (copy files from library → game audio folder)

The Vite dev server proxies `/api` calls to port 5211, so the React app communicates with the API seamlessly.

---

## 3. File Map

### Tool Files (`tools/audio-workbench/`)

| File | Purpose | ~Lines |
|------|---------|--------|
| `server.js` | Express micro-API — config I/O, file listing, audio serving, backup system | 130 |
| `package.json` | Dependencies: React 18, Vite 5, Express 4, cors, concurrently | 27 |
| `vite.config.js` | Port 5210, proxy `/api` → `:5211` | 24 |
| `index.html` | HTML entry point — grimdark dark theme base | 17 |
| `src/main.jsx` | React mount point | 9 |
| `src/App.jsx` | Root component — data loading, save handler, tab routing, validation engine | 248 |
| `src/components/SoundBrowser.jsx` | File browser panel — filter, sort, preview, quick-map | 220 |
| `src/components/MappingEditor.jsx` | Config section editor — volume/pitch sliders, variant management | 310 |
| `src/components/ComparePanel.jsx` | A/B comparison panel — side-by-side playback with adjustments | 170 |
| `src/components/AssetLibrary.jsx` | Asset library browser — preview, import & replace from Helton Yan pack | 310 |
| `src/components/Waveform.jsx` | Web Audio waveform amplitude bar visualization | 100 |
| `src/styles/workbench.css` | Full grimdark-themed CSS — matches Arena project visual style | 380 |

### Launch Script

| File | Purpose |
|------|---------|
| `start-audio-workbench.bat` | One-click launcher — `npm install`, starts API + Vite |

### Files Read/Written

| Path | Access | Purpose |
|------|--------|---------|
| `client/public/audio-effects.json` | Read + Write | The game's data-driven sound config |
| `client/public/audio/**/*` | Read (static serve) | All sound files on disk |
| `client/public/audio-effects.backup-*.json` | Write (auto) | Timestamped backups before each save |
| `Assets/Audio/Helton Yan's Pixel Combat - Single Files/*` | Read (static serve) | Full sound pack library for browsing & import |

---

## 4. Data Flow

### On Load

```
App.jsx mounts
  ├── GET /api/config      → parse audio-effects.json → setConfig(obj)
  └── GET /api/sounds      → recursive walk of audio/ → setDiskFiles([...])
        │
        ▼
  validation = useMemo(config, diskFiles)
    ├── orphaned: files on disk not in _soundFiles
    └── broken: keys in _soundFiles with no file on disk
```

### On Edit

```
User adjusts a slider / adds a variant / maps a file
  ├── updateConfig(prev => next)   → deep-clone, mutate, return
  ├── setDirty(true)               → "● Unsaved changes" indicator
  └── setSaveStatus(null)          → ready for save
```

### On Save

```
User clicks 💾 Save
  ├── POST /api/config  { body: config }
  │     ├── server copies current file → audio-effects.backup-{timestamp}.json
  │     ├── server writes new config → audio-effects.json
  │     └── server prunes backups beyond the 5 most recent
  ├── setSaveStatus('saved')  → "✓ Saved!" for 2.5s
  └── setDirty(false)
```

### On Playback

```
User clicks ▶ on any sound
  ├── getAudioCtx()  → create or resume AudioContext (handles browser autoplay)
  ├── fetch(API_BASE + filePath)  → ArrayBuffer
  ├── ctx.decodeAudioData(buf)    → AudioBuffer
  ├── createBufferSource()        → connect to gain → connect to destination
  └── source.start()              → source.onended sets playingPath = null
```

---

## 5. API Server

The Express server (`server.js`) provides five endpoints:

### Endpoints

| Method | Path | Request Body | Response | Purpose |
|--------|------|-------------|----------|---------|
| `GET` | `/api/config` | — | Full `audio-effects.json` as JSON | Load the current config |
| `POST` | `/api/config` | JSON object (updated config) | `{ success, backup }` | Write config with auto-backup |
| `GET` | `/api/sounds` | — | `{ files: [...], totalCount }` | List all audio files on disk |
| `GET` | `/api/categories` | — | `{ categories: [...] }` | List audio subdirectories |
| `POST` | `/api/import` | `{ sourcePath, category, fileName }` | `{ success, path }` | Copy a file into a category dir |
| `GET` | `/api/library` | — | `{ files: [...], totalCount, available }` | List all files in Helton Yan asset library |
| `POST` | `/api/library/import` | `{ libraryFileName, category, newFileName }` | `{ success, path, size }` | Copy a library file into a game audio category |
| `GET` | `/audio/*` | — | Static file | Audio file serving for game sounds |
| `GET` | `/library/*` | — | Static file | Audio file serving for library preview |

### Static File Serving

Audio files are served at `/audio/*` via `express.static(AUDIO_DIR)`, pointing to `client/public/audio/`. Asset library files are served at `/library/*` via `express.static(ASSET_LIBRARY_DIR)`, pointing to the Helton Yan sound pack. This allows the browser to fetch and decode any sound file for playback and waveform visualization.

### Backup System

On every `POST /api/config`:

1. **Copy** the existing `audio-effects.json` → `audio-effects.backup-{Date.now()}.json`
2. **Write** the new config to `audio-effects.json` (formatted with 2-space indent)
3. **Prune** — sort backup files by timestamp, keep only the 5 most recent, delete the rest

Backups live alongside the config in `client/public/` and are ignored by the game.

---

## 6. Sound Browser Panel

**Tab:** 📁 Sound Browser

The primary file discovery and preview interface. Scans all 110 audio files across 8 category directories.

### Controls

| Control | Type | Purpose |
|---------|------|---------|
| Search box | Text input | Filter by filename, path, or sound key |
| Category dropdown | Select | Filter by directory: all, buffs, combat, events, items, movement, music, skills, ui |
| Status filter | Select | All files / Mapped only / Unmapped only / Broken refs |
| Sort selector | Select | Sort by name, category, or file size |

### Per-File Row

Each row shows:

| Element | Description |
|---------|-------------|
| ▶ / ⏹ button | Play/stop the sound |
| Waveform | Compact amplitude bar visualization (140×32px) |
| Filename | Bold, truncated with ellipsis |
| Category | Color-coded category tag |
| File size | Human-readable (KB/MB) |
| Sound key | If mapped, shows the `_soundFiles` key |
| Status badge | **MAPPED** (green), **UNMAPPED** (yellow), or **BROKEN** (red) |
| Quick-map button | For unmapped files — generates a key from filename and adds to `_soundFiles` |
| Compare button | Adds the sound to the Compare panel |

### Quick-Map Logic

When an orphaned file is quick-mapped:

1. The filename is converted to a key: `melee-hit_sword-slash.wav` → `melee_hit_sword_slash`
2. An entry is added to `config._soundFiles[key] = filePath`
3. The config is marked dirty (requires Save to persist)

---

## 7. Mapping Editor Panel

**Tab:** 🎛️ Mapping Editor

Provides a full editor for all sections of `audio-effects.json`.

### Section Sidebar

| Section | Icon | Contents |
|---------|------|----------|
| Sound Files | 📋 | The `_soundFiles` registry — all key → path mappings |
| Combat | ⚔️ | `melee_hit`, `melee_crit`, `ranged_hit`, `miss`, `dodge`, `block`, `death`, `skill_cast`, `heal`, `buff_apply`, `stun_hit`, `potion_use`, `loot_pickup` |
| Skills | ✨ | Per-skill overrides: `taunt`, `shield_bash`, `holy_ground`, `heal`, `shadow_step`, `war_cry`, etc. (21 skills) |
| Environment | 🏰 | `door_open`, `chest_open` |
| Events | 🎯 | `portal_channel`, `portal_open`, `wave_clear`, `floor_descend`, `match_start`, `match_end` |
| UI | 🖱️ | `click`, `confirm`, `cancel`, `equip`, `buy`, `sell` |
| Music | 🎵 | Playlist tracks (11 MP3 files) |

### Sound Files Manager

- **Add entry** — text fields for key and path, + Add button
- **Per-entry row** — play button, key (monospace), path, compare button, delete button
- Entries are sorted alphabetically by key

### Event Mapping Editor

Each event mapping row is expandable. The collapsed header shows:

| Element | Description |
|---------|-------------|
| Event name | Bold label (e.g., `melee_hit`, `block`) |
| Variant count badge | "9 variants" in blue if applicable |
| Single key arrow | "→ skill_taunt" if single-key mapping |
| Volume display | `vol: 0.8` |
| Pitch display | `pitch±: 0.1` |
| Quick-play button | Plays the sound (or random variant) |

When expanded, the detail panel shows:

| Control | Type | Range | Purpose |
|---------|------|-------|---------|
| Comment | Text (read-only) | — | The `_comment` field from config |
| Volume slider | Range input | 0.00 – 1.00 (step 0.05) | Sets `volume` on the mapping |
| Pitch Variance slider | Range input | ±0% – ±20% (step 1%) | Sets `pitchVariance` on the mapping |
| Sound Key selector | Dropdown | All `_soundFiles` keys | For single-key mappings — change which sound plays |
| Variant list | Indexed list | — | Each variant: index, play button, waveform, key, compare, remove |
| Add variant dropdown | Select | All unmapped keys | Add a new sound to the variant array |

---

## 8. Compare Panel

**Tab:** ⚖️ Compare

A/B testing interface for auditioning sounds side-by-side. Holds up to 6 sounds.

### How Sounds Get Here

Any sound in the Browser or Editor can be sent to Compare via the ⚖️ button. Duplicates are rejected. Switching to the Compare tab happens automatically when a sound is added.

### Controls

| Control | Type | Purpose |
|---------|------|---------|
| Volume slider | Range 0–100% | Adjusts gain node in real-time (even on currently-playing sound) |
| Pitch Variance slider | Range ±0–20% | Applies random pitch shift on each play |
| Loop toggle | Checkbox | Enables `source.loop = true` for ambient/music comparison |
| Next (A/B) button | Button | Plays sounds sequentially — cycles 1 → 2 → 3 → ... → 1 |
| Random button | Button | Picks a random sound from the list (simulates variant behavior) |
| Clear button | Button | Removes all sounds from the compare list |

### Sound Cards

Each sound is displayed as a card with:

- **Number badge** — position in the list (1–6)
- **Label** — filename or sound key
- **Waveform** — full-size amplitude visualization (280×48px)
- **Play/Stop button** — large, full-width
- **File path** — monospace, truncated

The currently-playing card gets a blue border highlight.

---

## 9. Asset Library Panel

The Asset Library panel (`AssetLibrary.jsx`) provides a browser for the full Helton Yan Pixel Combat sound pack located at `Assets/Audio/Helton Yan's Pixel Combat - Single Files/`. This lets developers preview, compare, and import sounds from the asset library directly into the game's audio folder — without manually copying files.

### Data Source

On mount, the component fetches `GET /api/library` which returns all files in the library with parsed metadata:
- **category** — extracted from the filename prefix (e.g., `EXPLOSION`, `MELEE`, `HIT`, `CAST`)
- **displayName** — human-readable name parsed from the filename
- **variant** — variant number from the filename suffix

Files are grouped by sound name so that all variants of the same sound appear together in a collapsible group.

### Two Modes of Operation

| Mode | Workflow | Result |
|------|----------|--------|
| **Replace existing** | Select a game sound key → browse library → click "Replace" on a variant | Copies library file to game audio folder, updates `_soundFiles` key in config |
| **Import as new** | Browse library → pick a target category → click "Import" | Copies library file to game audio folder (no config change — it becomes an orphan for mapping later) |

### Replace Workflow Detail

1. User clicks 📦 **Asset Library** tab
2. A blue banner shows **"Replace Mode"** with a dropdown of all existing sound keys (from config)
3. User selects a key (e.g., `hit_sword_1`)
4. User browses/filters library sounds, previews with waveform + play button
5. User clicks **"Replace"** on a variant
6. `POST /api/library/import` copies the file to the appropriate category folder
7. The config's `_soundFiles` entry for that key is updated to point to the new file
8. `onRefreshDiskFiles()` re-fetches the file list so all panels stay in sync

### Features

- **Category filter** — dropdown to filter by sound category (EXPLOSION, MELEE, etc.)
- **Text search** — filter by display name
- **Waveform previews** — each variant shows a small waveform visualization
- **Play/Stop** — inline playback for quick auditioning
- **Add to Compare** — send any library sound to the Compare Panel for A/B testing
- **Grouped variants** — sounds with multiple variants are collapsible groups

---

## 10. Waveform Visualization

The `Waveform` component renders amplitude bars from decoded audio data using the Web Audio API's `decodeAudioData()`.

### How It Works

1. `fetch(src)` → `ArrayBuffer`
2. `audioContext.decodeAudioData(buf)` → `AudioBuffer`
3. Extract channel 0 float data: `audioBuffer.getChannelData(0)`
4. Divide samples into 80 bars (or fewer for compact mode)
5. For each bar, compute average absolute amplitude across its sample range
6. Draw rectangle: height proportional to amplitude, centered vertically

### Modes

| Mode | Canvas Size | Bar Count | Used In |
|------|-------------|-----------|---------|
| Normal | 280 × 48px | 80 bars | Compare Panel cards |
| Compact | 140 × 32px | ~47 bars | Sound Browser rows, Variant list rows |

### Color States

| State | Bar Color | Meaning |
|-------|-----------|---------|
| Idle | `#6e8efb` (blue) | Not playing |
| Playing | `#ff6b6b` (red) | Currently playing |

Waveforms are decoded once per URL and cached in a ref. Subsequent renders (e.g., play state changes) only redraw the canvas without re-fetching.

---

## 11. Validation Engine

The validation engine runs as a `useMemo` in `App.jsx`, recomputed whenever `config` or `diskFiles` change.

### What It Detects

| Issue | Detection Logic | UI Indicator |
|-------|----------------|--------------|
| **Orphaned files** | File exists in `client/public/audio/` but no `_soundFiles` entry references its path | Yellow "UNMAPPED" badge + header count |
| **Broken references** | Key exists in `_soundFiles` but the referenced path has no matching file on disk | Red "BROKEN" badge + header count |
| **Mapped files** | File on disk AND referenced in `_soundFiles` | Green "MAPPED" badge |

### Header Summary

The app header always shows:
- `{N} files` — total disk files detected
- `{N} mapped` — entries in `_soundFiles`
- `{N} unmapped` (yellow badge) — orphaned file count (if > 0)
- `{N} broken` (red badge) — broken reference count (if > 0)

### Sound Browser Integration

The status filter dropdown lets you isolate:
- **All files** — everything on disk
- **Mapped only** — files that are properly configured
- **Unmapped only** — orphaned files that need assignment
- **Broken refs** — virtual entries showing keys that point to missing files

---

## 12. Save System & Backup Strategy

### Save Flow

1. User makes changes → `dirty` flag set to `true` → header shows "● Unsaved changes"
2. User clicks 💾 Save → `POST /api/config` sends the full config object
3. Server creates backup: `audio-effects.backup-{Date.now()}.json`
4. Server writes `audio-effects.json` with 2-space indentation
5. Server prunes old backups (keeps newest 5)
6. UI shows "✓ Saved!" for 2.5 seconds, then resets

### Button States

| Condition | Button Text | Style |
|-----------|------------|-------|
| No changes | 💾 Save (disabled) | Dimmed |
| Unsaved changes | 💾 Save (enabled) | Green |
| Saving in progress | Saving... | Pulsing animation |
| Save succeeded | ✓ Saved! | Green (auto-clears after 2.5s) |
| Save failed | ✗ Error | Red |

### Backup Files

Backups are stored in `client/public/` alongside the config:

```
client/public/
├── audio-effects.json                          ← current config
├── audio-effects.backup-1709337600000.json     ← auto-backup
├── audio-effects.backup-1709337500000.json
├── audio-effects.backup-1709337400000.json
├── audio-effects.backup-1709337300000.json
└── audio-effects.backup-1709337200000.json     ← oldest kept (5 max)
```

### Reload Button

The ⟳ Reload button re-fetches both the config and disk files from the API, discarding any unsaved in-memory changes. Useful after manually editing files or adding new sounds to disk.

---

## 13. Audio Playback Engine

All playback uses the native Web Audio API — no libraries, matching the game's approach.

### Shared AudioContext

A single `AudioContext` is created lazily on first user interaction (via `getAudioCtx()`). It's stored in a `useRef` and passed down to all panels. If the context is in the `suspended` state (browser autoplay policy), it's resumed automatically.

### Playback Pattern

```javascript
const ctx = getAudioCtx();
const response = await fetch(url);
const arrayBuf = await response.arrayBuffer();
const audioBuf = await ctx.decodeAudioData(arrayBuf);

const source = ctx.createBufferSource();
source.buffer = audioBuf;
source.connect(ctx.destination);  // or through a gain node
source.onended = () => setPlayingPath(null);
source.start();
```

### Compare Panel Enhancements

The Compare panel adds additional processing:

| Feature | Implementation |
|---------|---------------|
| Volume control | `GainNode` between source and destination, updated in real-time |
| Pitch variance | `source.playbackRate.value = 1.0 + random(-pitchVariance, +pitchVariance)` |
| Loop mode | `source.loop = true` |

### Playback Toggle

Clicking the play button on an already-playing sound stops it (`source.stop()`). Clicking a different sound stops the current one first, then starts the new one (one-at-a-time playback).

---

## 14. Relationship to Game Audio System

The Audio Workbench edits the same `audio-effects.json` that the game's `AudioManager` reads at runtime.

```
Audio Workbench                         Game Client
─────────────────                       ───────────
writes audio-effects.json  ──────────▶  AudioManager reads on init()
                                        preloads all _soundFiles
                                        maps events → sounds
                                        plays via Web Audio API
```

### What Changes Take Effect

| Change in Workbench | Game Effect |
|---------------------|-------------|
| Edit volume on a mapping | Sound plays at new volume next game load |
| Edit pitchVariance | Pitch randomization range changes |
| Change a sound key | Different sound file plays for that event |
| Add/remove variant | Variant pool changes for random selection |
| Add new `_soundFiles` entry | New sound preloaded and available |
| Remove `_soundFiles` entry | Sound silently skipped (no errors) |

### No Code Changes Required

The game's audio system was designed from the start to be data-driven. The Workbench edits only the JSON config, never any JavaScript. The `AudioManager` re-reads the config on initialization (page refresh or game start), picking up all changes automatically.

---

## 15. Port Assignments

| Service | Port | Tool |
|---------|------|------|
| Game backend (FastAPI) | 8000 | — |
| Game frontend (Vite) | 5173 | — |
| Particle Lab | 5180 | `tools/particle-lab/` |
| Theme Designer | 5200 | `tools/theme-designer/` |
| **Audio Workbench UI** | **5210** | `tools/audio-workbench/` |
| **Audio Workbench API** | **5211** | `tools/audio-workbench/server.js` |

All tools can run simultaneously without port conflicts.

---

## 16. Quick Start

### One-Click

```bash
start-audio-workbench.bat
```

This runs `npm install`, starts the Express API server in the background, then launches Vite. The browser opens automatically to `http://localhost:5210`.

### Manual

```bash
cd tools/audio-workbench
npm install

# Terminal 1 — API server
node server.js              # Listening on http://localhost:5211

# Terminal 2 — UI
npx vite                    # Listening on http://localhost:5210
```

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| react | ^18.3.0 | UI framework |
| react-dom | ^18.3.0 | React DOM renderer |
| express | ^4.18.0 | Micro-API server for file I/O |
| cors | ^2.8.5 | Cross-origin requests (Vite → Express) |
| @vitejs/plugin-react | ^4.2.0 | Vite React plugin (dev) |
| vite | ^5.4.0 | Dev server + bundler (dev) |
| concurrently | ^8.2.0 | Run multiple processes (dev) |

Zero external audio dependencies — all playback uses the native Web Audio API.
