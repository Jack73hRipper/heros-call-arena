# Audio System

> **Last updated:** March 2, 2026  
> **Status:** Implemented (Phase 15D)  
> **Approach:** Native Web Audio API — no libraries  
> **Pattern:** ParticleManager-mirror singleton, data-driven JSON config

---

## Table of Contents

1. [Architecture](#1-architecture)
2. [File Map](#2-file-map)
3. [Gain Node Graph](#3-gain-node-graph)
4. [Data-Driven Config (audio-effects.json)](#4-data-driven-config-audio-effectsjson)
5. [Sound Asset Inventory](#5-sound-asset-inventory)
6. [Event Triggers](#6-event-triggers)
7. [UI Sound System](#7-ui-sound-system)
8. [Volume Settings & Persistence](#8-volume-settings--persistence)
9. [Sound Throttling](#9-sound-throttling)
10. [Tab-Visibility Guard](#10-tab-visibility-guard)
11. [Browser Autoplay Policy](#11-browser-autoplay-policy)
12. [Adding New Sounds](#12-adding-new-sounds)
13. [What Still Needs to Be Done](#13-what-still-needs-to-be-done)

---

## 1. Architecture

The audio system mirrors the `ParticleManager` pattern: a plain JS singleton class held via `useRef`, with an `init() → resume() → destroy()` lifecycle. It is entirely client-side — the server has no audio awareness.

**Key design principles:**

- **Data-driven** — All sound-to-event mapping lives in `audio-effects.json`. Swap sounds by editing JSON, no code changes needed.
- **Singleton** — One `AudioManager` instance per session, created in `App.jsx` via `useAudio()`.
- **Gain node routing** — Four-channel gain graph (SFX, Ambient, UI → Master → destination) for independent volume control.
- **Silent fail** — Unmapped sound keys produce no audio and no errors. Safe to reference keys before assets exist.
- **React integration** — Three hooks (`useAudio`, `useAudioEvents`, `useAmbientAudio`) plus a context provider (`AudioProvider`) bridge the singleton to the React tree.

---

## 2. File Map

### Core Files (`client/src/audio/`)

| File | Purpose | ~Lines |
|------|---------|--------|
| `AudioManager.js` | Web Audio API singleton — all playback, volume, throttling, preloading | 660 |
| `soundMap.js` | `SOUND_KEYS` constants + `SOUND_CATEGORIES` enum + `validateEffectMap()` diagnostic | 143 |
| `useAudio.js` | React hooks: `useAudio()`, `useAudioEvents()`, `useAmbientAudio()`, `useGlobalUIClickSounds()` | 213 |
| `AudioContext.jsx` | React context: `AudioProvider`, `useUISound()`, `useAudioSettings()` | 97 |
| `index.js` | Barrel export for all audio modules | 9 |

### Config & Assets

| Path | Purpose |
|------|---------|
| `client/public/audio-effects.json` | Data-driven event → sound mapping (version 2, ~398 lines) |
| `client/public/audio/` | Sound files organized by category (99 .wav files) |
| `client/public/audio/README.md` | Asset attribution and organization notes |

### Dev Tool

| Path | Purpose |
|------|---------|
| `tools/audio-workbench/` | Standalone workbench for previewing, mapping, comparing, and importing sounds |
| `Assets/Audio/Helton Yan's Pixel Combat - Single Files/` | Full sound pack library (~1000+ WAV files) — browsable via the Workbench's Asset Library tab |

### UI Components

| File | Purpose |
|------|---------|
| `client/src/components/VolumeSettings/VolumeSettings.jsx` | Floating volume control widget (mute toggle + slider panel) |
| `client/src/styles/components/_volume-settings.css` | Grimdark-themed styling for volume controls |

### Modified Integration Points

| File | Changes |
|------|---------|
| `client/src/App.jsx` | Imports `useAudio`, `useAmbientAudio`, `AudioProvider`, `VolumeSettings`. Creates AudioManager singleton, passes volume controls to context, wires game events in WS handler (portal/wave/floor), renders VolumeSettings. |
| `client/src/components/Arena/Arena.jsx` | Imports `useAudioEvents`, accepts `audioManager` prop, calls `useAudioEvents(audioManager, lastTurnActions, players)` for per-turn combat sounds. |
| `client/src/styles/main.css` | Added `@import './components/_volume-settings.css'` |

---

## 3. Gain Node Graph

```
Source (one-shot) ─→ perSoundGain ─→ sfxGain ─────┐
                                                    │
Ambient loop ─────→ fadeGain ──────→ ambientGain ──┤─→ masterGain ─→ destination
                                                    │
UI source ────────→ perSoundGain ──→ uiGain ───────┘
```

Each channel has independent volume (0–1). The master gain node applies global volume and handles mute (sets gain to 0). Per-sound gain nodes allow individual volume multipliers from the JSON config.

**Default volumes:**

| Channel | Default | Purpose |
|---------|---------|---------|
| Master | 0.7 | Global multiplier |
| SFX | 1.0 | Combat hits, skills, deaths |
| Ambient | 0.4 | Looping background tracks |
| UI | 0.6 | Button clicks, menu feedback |

---

## 4. Data-Driven Config (audio-effects.json)

The JSON file has these top-level sections:

```json
{
  "_version": 2,
  "_soundFiles": { ... },     // key → file path mapping (preload registry)
  "combat": { ... },          // melee_hit, ranged_hit, miss, block, death, etc.
  "skills": { ... },          // Per-skill sound overrides (21 skills mapped)
  "environment": { ... },     // door_open, chest_open
  "events": { ... },          // portal_channel, portal_open, wave_clear, floor_descend, match_start, match_end
  "ui": { ... }               // click, confirm, cancel, error
}
```

### Mapping format

Each event maps to either a single sound or a variant array:

```json
"melee_hit": {
  "variants": ["melee_hit_1", "melee_hit_2", ..., "melee_hit_9"],
  "volume": 0.9,
  "pitchVariance": 0.08
}
```

When `variants` is present, the AudioManager picks one at random each play. `pitchVariance: 0.08` means ±8% playback rate randomization for natural variation.

### `_soundFiles` section

This is the canonical key → file path registry. Every sound that should be preloaded on init must have an entry here:

```json
"melee_hit_1": "/audio/combat/melee-hit_sword-slash.wav",
"skill_heal":  "/audio/skills/skill_rpg-heal.wav"
```

Paths are relative to `client/public/` (served at root by Vite).

---

## 5. Sound Asset Inventory

**Source:** "Helton Yan's Pixel Combat — Single Files" (Assets/Audio/RPG Sound Pack/)  
**Total:** 99 .wav files across 7 subdirectories

| Directory | Files | Sounds Covered |
|-----------|-------|----------------|
| `combat/` | 41 | Melee hits (9), crits (2), ranged (6), miss (4), dodge (1), block (7), death (5), stun (3), retro variants |
| `skills/` | 26 | All 21 skill abilities across 5 classes + generic cast |
| `buffs/` | 7 | Buff application, war cry, defensive, heal, aura |
| `ui/` | 11 | Button clicks (5), confirm (2), cancel, error, hover, select |
| `items/` | 8 | Potion use, loot pickup, chest open, door open, coin |
| `events/` | 7 | Portal channel, portal open, wave clear, floor descend, match start/end, level up |
| `movement/` | 3 | Footstep variants |

### Variant coverage

| Sound Event | Variants | Purpose |
|-------------|----------|---------|
| `melee_hit` | 9 | Natural variety in auto-attacks |
| `block` | 7 | Shields / parries feel different each time |
| `ranged_hit` | 6 | Arrow/projectile impacts |
| `death` | 5 | Different death sounds per kill |
| `ui_click` | 5 | Button press variety |
| `miss` | 4 | Whiff sounds |
| `stun_hit` | 3 | Stun/CC landing |
| `melee_crit` | 2 | Critical hits feel impactful |
| `ui_confirm` | 2 | Big button presses |

---

## 6. Event Triggers

### Combat sounds (per-turn via `useAudioEvents`)

Wired in `Arena.jsx`. Fires once per turn when `lastTurnActions` updates (same bus as particles):

| Action Type | Sound Played | Notes |
|-------------|-------------|-------|
| `attack` (success) | `melee_hit` variants | Random pick from 9 |
| `attack` (damage ≥ 25) | `melee_crit` variants | Mirrors ParticleManager's `HIGH_DAMAGE_THRESHOLD` |
| `ranged_attack` (success) | `ranged_hit` variants | |
| `attack`/`ranged` + `killed` | `death` variants | Stacks with hit sound |
| `skill` | Per-skill mapping or `skill_cast` fallback | 21 skills mapped individually |
| `use_item` | `potion_use` | |
| `loot` | `loot_pickup` | |
| Failed + "dodged" | `dodge` | Parsed from action message |
| Failed + "blocked" | `block` variants | |
| Failed (miss) | `miss` variants | |

### Environment sounds (per-turn via `processEnvironment`)

| Trigger | Sound |
|---------|-------|
| `doorChanges` array non-empty | `door_open` |
| `chestOpened` array non-empty | `chest_open` |

### Game event sounds (via `processEvent` in WS handler)

Wired in `App.jsx` WebSocket message handler and `setScreen` callback:

| Event | WS Trigger | Sound |
|-------|-----------|-------|
| `match_start` | Screen transitions to `'arena'` | Match fanfare |
| `match_end` | Screen transitions to `'postmatch'` | Victory/defeat |
| `portal_open` | `turn_result.portal_spawned === true` | Portal activation |
| `portal_channel` | `turn_result.channeling === true` | Channeling loop |
| `wave_clear` | `wave_started` WS message | Wave completion |
| `floor_descend` | `floor_advance` WS message | Descending deeper |

### Ambient tracks (via `useAmbientAudio`)

Automatic switching based on current screen:

| Screen | Ambient Key | Notes |
|--------|-------------|-------|
| `'town'` | `ambient_town` | *(Not yet sourced — see §13)* |
| `'arena'` (PvP) | `ambient_arena` | *(Not yet sourced)* |
| `'arena'` (dungeon) | `ambient_dungeon` | *(Not yet sourced)* |
| `'lobby'` / `'postmatch'` | *(stops ambient)* | Fade-out on exit |

---

## 7. UI Sound System

UI sounds use a two-pronged approach to avoid modifying every component individually:

### A. Global Click Delegation (`useGlobalUIClickSounds`)

A single `document.addEventListener('click', handler, true)` in capture phase detects button clicks by CSS class and plays the appropriate sound:

| Selector | Sound | Notes |
|----------|-------|-------|
| `[data-ui-sound="custom_key"]` | Custom key | Override via data attribute |
| `.grim-btn--lg`, `.grim-btn--ember`, `.grim-btn--verdant`, `.grim-btn--crimson` | `confirm` | Big action buttons |
| `.grim-btn` (other variants) | `click` | Standard buttons |
| `.town-nav-item` | `click` | Town navigation tabs |
| `.skill-slot-btn` | `click` | Skill bar buttons |
| `.btn-bar` | `click` | Bottom bar actions |

### B. React Context (`useUISound` / `useAudioSettings`)

For components that need direct access:

```jsx
const { playUI, withClick, withConfirm } = useUISound();

// Direct call
<button onClick={() => playUI('click')}>

// Convenience wrapper — plays sound then fires callback
<button onClick={withConfirm(handleSubmit)}>
```

### C. Custom override

Any element can set `data-ui-sound="key_name"` to play a specific sound on click, overriding the CSS-class detection. Set `data-ui-sound=""` (empty string) to suppress sound for an element.

---

## 8. Volume Settings & Persistence

### VolumeSettings Component

A floating widget fixed to the **top-right corner** of every screen (`z-index: 9999`):

- **Speaker icon** — Click to toggle mute. Icon shows red X when muted.
- **Chevron button** — Click to expand/collapse the slider panel.
- **4 sliders** — Master, SFX, Ambient, UI (0–100%, mapped to 0.0–1.0).
- **"Mute All" button** — Full mute toggle at the bottom of the panel.
- **Outside-click dismissal** — Panel closes when clicking elsewhere.

### localStorage Persistence

Settings are saved to `localStorage` key `arena_audio_settings` on every volume change and mute toggle. On init, `AudioManager._loadSettings()` restores them. Format:

```json
{
  "masterVolume": 0.7,
  "sfxVolume": 1.0,
  "ambientVolume": 0.4,
  "uiVolume": 0.6,
  "muted": false
}
```

Settings survive page reloads and session restarts.

---

## 9. Sound Throttling

Prevents audio chaos on large turns (e.g., 6-party AoE with multiple kills):

| Mechanism | Value | Purpose |
|-----------|-------|---------|
| **Max concurrent voices** | 6 | Hard cap on simultaneous SFX sources. Extra sounds are silently dropped. |
| **Per-key cooldown** | 80ms | Same sound key cannot fire again within 80ms. Prevents identical sound stacking. |
| **Voice tracking** | `source.onended` | Active voice count decremented when each source finishes playback. |

These limits apply only to SFX. UI and ambient sounds are not throttled.

---

## 10. Tab-Visibility Guard

Mirrors the particle system's `_hidden` flag approach:

1. **`_hidden` flag** — Tracks `document.hidden`, updated via `visibilitychange` listener.
2. **Guard methods** — `processActions()`, `processEnvironment()`, and `processEvent()` return early if `_hidden === true`.
3. **Effect:** No sounds queue up while the tab is hidden. When the user returns, only current-frame sounds play — no burst of stale audio.

`playUI()` is intentionally **not** guarded — the tab must be visible for UI clicks to happen.

---

## 11. Browser Autoplay Policy

Modern browsers require a user gesture before audio can play. The system handles this with:

1. **AudioContext created in `'suspended'` state** — Standard browser behavior.
2. **`resumeAudio()` on first click** — Wired to `App.jsx`'s root `<div onClick={resumeAudio}>`. First click anywhere resumes the context.
3. **Safe to call repeatedly** — `resume()` checks `context.state === 'suspended'` before acting.

---

## 12. Adding New Sounds

### Manual Method

1. Place the `.wav` / `.ogg` / `.mp3` file in `client/public/audio/<category>/`
2. Add a `key → path` entry to `audio-effects.json` → `_soundFiles`
3. Reference the key in the appropriate section (`combat`, `skills`, `events`, `ui`, etc.)
4. AudioManager preloads everything in `_soundFiles` on init — no code changes needed

For variant arrays, add the new key to the `variants` array of the relevant mapping.

### Via Audio Workbench (Recommended)

The Audio Workbench's **Asset Library** panel provides a GUI workflow:

1. Open the workbench: `start-audio-workbench.bat`
2. Click the 📦 **Asset Library** tab
3. Browse or search the Helton Yan sound pack by category
4. Preview sounds with waveform visualization and inline playback
5. **Import as new** — copies the file to the appropriate game audio category folder
6. **Replace existing** — select a game sound key, pick a replacement, and the tool imports the file and updates the config
7. Switch to the 🎛️ **Mapping Editor** tab to wire the new sound to game events
8. Click 💾 **Save** — changes are live on next game load

---

## 13. What Still Needs to Be Done

### Priority 1 — Ambient Music Tracks

The ambient loop infrastructure is fully built and wired (`playAmbient()`/`stopAmbient()` with crossfade, `useAmbientAudio()` hook switching by screen). But **no actual music files exist** in the project yet.

**Needed:**

| Key | Used On | Requirements |
|-----|---------|-------------|
| `ambient_town` | Town hub screen | Looping, atmospheric, low-key medieval/dark fantasy feel |
| `ambient_arena` | PvP arena matches | Looping, tense, combat-ready |
| `ambient_dungeon` | Dungeon runs | Looping, ominous, exploratory |

These must be **loopable** (seamless start/end). The current "Helton Yan's Pixel Combat" pack contains only short SFX — no music tracks. Separate assets need to be sourced (e.g., Kevin MacLeod, Incompetech, or similar royalty-free libraries).

Once files are placed in `client/public/audio/ambient/` and added to `_soundFiles` in the JSON, the system will pick them up automatically with no code changes.

### Priority 2 — Movement / Footstep Sounds

Three footstep variants exist (`movement/step_*.wav`) and have `_soundFiles` entries, but **they are not wired to any trigger yet**. Options:

- **Per-move action:** Play a footstep on `action_type === 'move'` in `processActions()`.
- **Tile-type variation:** Different sounds for stone/grass/water tiles (requires tile metadata).
- **Throttling consideration:** With 6+ party members moving every turn, footsteps could dominate the mix. May need lower volume or heavy cooldown.

### Priority 3 — Additional Sound Events

Currently unmapped events that could benefit from audio:

| Event | Potential Sound | Notes |
|-------|----------------|-------|
| Buff expiration | Subtle fade/dispel sound | When buff `turns_remaining` hits 0 |
| Level up | Fanfare jingle | On XP threshold |
| Enemy spawn | Growl/roar | On wave start in dungeons |
| Party member death | Specific death knell | Distinct from enemy death |
| Skill cooldown ready | Subtle "ding" | When a skill becomes available again |
| Inventory full | Error/warning | When loot fails due to full inventory |
| Critical heal | Distinct heal variant | Similar to crit hit distinction |

### Priority 4 — Positional Audio (Future)

Web Audio API supports `PannerNode` for 3D spatial audio. Could tie sound panning to the entity's position relative to the player's canvas viewport:

- Hits on the left side of the screen pan left
- Distant sounds are quieter
- Would require passing position data to `play()` calls

This is a significant enhancement and not currently planned.

### Priority 5 — Sound Preview / Testing Tool ✅ IMPLEMENTED

The **Audio Workbench** (`tools/audio-workbench/`) was built as a standalone dev tool that fulfills and exceeds this requirement:

- Lists all mapped sounds from `audio-effects.json` — with MAPPED/UNMAPPED/BROKEN validation badges
- Plays each on click for preview with waveform visualization
- Shows variant arrays and lets you cycle through them
- Validates all `_soundFiles` paths against disk — broken references highlighted in red
- **A/B comparison panel** — compare up to 6 sounds side-by-side with volume/pitch controls
- **Asset Library browser** — browse the full Helton Yan sound pack (~1000+ WAV files), preview any sound, and import/replace game sounds directly from the library
- **Replace workflow** — select an existing game sound key, pick a replacement from the library, and the tool copies the file and updates the config automatically

See: `docs/Systems/audio-workbench.md` and `docs/Tools/audio-workbench.md` for full documentation.

---

## Appendix A — Skill Sound Mapping

All 21 class skills are individually mapped:

| Class | Skill | Sound Key |
|-------|-------|-----------|
| **Crusader** | Taunt | `skill_taunt` |
| | Shield Bash | `skill_shield_bash` |
| | Holy Ground | `skill_holy_ground` |
| | Bulwark | `skill_bulwark` |
| **Ranger** | Power Shot | `skill_power_shot` |
| | Volley | `skill_volley` |
| | Evasion | `skill_evasion` |
| | Crippling Shot | `skill_crippling_shot` |
| **Confessor** | Heal | `skill_heal` |
| | Rebuke | `skill_rebuke` |
| | Exorcism | `skill_exorcism` |
| | Prayer | `skill_prayer` |
| **Inquisitor** | Wither | `skill_wither` |
| | Shadow Step | `skill_shadow_step` |
| | Drain Life | `skill_drain_life` |
| | Hex | `skill_hex` |
| **Hexblade** | War Cry | `skill_war_cry` |
| | Double Strike | `skill_double_strike` |
| | Whirlwind | `skill_whirlwind` |
| | Blade Fury | `skill_blade_fury` |
| *(generic fallback)* | Any unmapped skill | `skill_cast` |

## Appendix B — Dependencies

- **Zero external dependencies.** The audio system uses only the native Web Audio API.
- **React 18** — Hooks for lifecycle management.
- **Vite** — Serves audio files from `client/public/` at root path.
- **Electron** — Audio works in Electron's Chromium runtime identically to browser.
