# Enemy Forge System

> **Last updated:** March 3, 2026
> **Status:** Implemented (Phase 18H — complete)
> **Stack:** React 18 + Vite 5 + Express 4 (ESM)
> **Pattern:** Standalone dev tool — matches Audio Workbench / Item Forge pattern
> **Ports:** UI on 5230, API on 5231
> **Source:** `tools/enemy-forge/` (~4,200 lines total)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [File Map](#3-file-map)
4. [Data Flow](#4-data-flow)
5. [API Server](#5-api-server)
6. [Config File Registry](#6-config-file-registry)
7. [Enemies Tab — Browser & Editor](#7-enemies-tab--browser--editor)
8. [Affixes Tab — Monster Affix Editor](#8-affixes-tab--monster-affix-editor)
9. [Champion Types Tab](#9-champion-types-tab)
10. [Floor Roster Tab](#10-floor-roster-tab)
11. [TTK Simulator Tab](#11-ttk-simulator-tab)
12. [Spawn Preview Tab](#12-spawn-preview-tab)
13. [Super Uniques Tab](#13-super-uniques-tab)
14. [Export Tab — Save System & Backup Strategy](#14-export-tab--save-system--backup-strategy)
15. [Sprite Integration](#15-sprite-integration)
16. [Rarity Tier Visual System](#16-rarity-tier-visual-system)
17. [Relationship to Game Systems](#17-relationship-to-game-systems)
18. [Port Assignments](#18-port-assignments)
19. [Quick Start](#19-quick-start)

---

## 1. Overview

The Enemy Forge is a standalone developer tool for creating, editing, balancing, and simulating all Monster Rarity system data in the Arena project. It provides a full visual interface for managing enemies, affixes, champion types, super unique bosses, and spawn distributions — without ever touching JSON by hand.

**Key principles:**

- **Direct config editing** — Reads and writes all enemy-related JSON configs in `server/configs/` directly. Save once, changes are live on next game server restart.
- **Full system awareness** — Loads enemies, rarity tiers, affixes, champion types, super uniques, skills, classes, combat config, loot tables, names, floor rosters, and sprite atlas data simultaneously.
- **Non-destructive** — Creates timestamped backups before every save. Keeps the last 5 backups per config file automatically.
- **Simulation-driven balance** — Monte Carlo TTK simulator lets you test enemy survivability against configurable hero parties before committing changes.
- **Spawn preview** — Roll-based distribution viewer shows actual vs. expected rarity spawns at any floor level.
- **Visual sprite assignment** — Browse the full sprite atlas, assign sprites to enemies, and preview rarity-tier glow effects on a live canvas.
- **Zero game dependencies** — Fully standalone. Does not import any game code, does not need the game server running, and uses its own Express micro-API for file I/O.

**What it manages:**

| System | Entities | Config File |
|--------|----------|-------------|
| Enemy Definitions | 25 enemy types | `enemies_config.json` |
| Monster Affixes | 15 affixes (9 categories) | `monster_rarity_config.json` |
| Champion Types | 5 types (Berserker, Fanatic, Ghostly, Resilient, Possessed) | `monster_rarity_config.json` |
| Rarity Tiers | Normal / Champion / Rare / Super Unique | `monster_rarity_config.json` |
| Super Uniques | Hand-crafted boss encounters | `super_uniques_config.json` |
| Spawn Rules | Floor-based chance scaling | `monster_rarity_config.json` |
| Floor Roster | 5 floor tiers × 3 pools (regular, boss, support) | `dungeon_generator.py` (read-only) |
| Loot Tables | Enemy drop definitions | `loot_tables.json` |
| Name Generation | Prefix/suffix pools for procedural names | `names_config.json` |

---

## 2. Architecture

The tool runs as two processes:

```
┌────────────────────────────────────┐      ┌────────────────────────────────────┐
│  Vite Dev Server (port 5230)       │      │  Express API Server (port 5231)    │
│  React 18 SPA                      │─────▶│  File I/O bridge                   │
│  10 components (2,727 lines)       │ /api │  Config read/write + backup        │
│  TTK Simulator (client-side)       │      │  Python source roster parsing      │
│  Sprite rendering (Canvas API)     │      │  Sprite atlas + sheet serving      │
│  Dirty-tracking + Ctrl+S save     │      │  Static metadata endpoint          │
└────────────────────────────────────┘      └────────────────────────────────────┘
         │                                           │
         │  proxy: /api → :5231                      │  fs.readFileSync / writeFileSync
         │  proxy: /spritesheet.png → :5231          │  fs.copyFileSync (backups)
         ▼                                           ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│  server/configs/                                                               │
│    enemies_config.json          │  monster_rarity_config.json                  │
│    super_uniques_config.json    │  skills_config.json (read-only)              │
│    classes_config.json (r/o)    │  combat_config.json (read-only)              │
│    loot_tables.json             │  names_config.json                           │
└────────────────────────────────────────────────────────────────────────────────┘
         │                                           │
         ▼                                           ▼
┌──────────────────────────────┐   ┌────────────────────────────────────────────┐
│  Assets/Sprites/             │   │  server/app/core/wfc/dungeon_generator.py  │
│  Combined Character Sheet    │   │  _FLOOR_ENEMY_ROSTER (Python literal)      │
│  1-atlas (3).json            │   │  Parsed via regex at API startup           │
│  + client/public/            │   └────────────────────────────────────────────┘
│    spritesheet.png           │
└──────────────────────────────┘
```

The Express API is needed because browsers cannot write to disk. It's a ~318-line server that provides config CRUD, roster parsing from Python source, sprite atlas metadata, and spritesheet file serving.

The Vite dev server proxies `/api/*` and `/spritesheet.png` requests to Express, so the React app sees a single origin.

---

## 3. File Map

```
tools/enemy-forge/
├── package.json                # Dependencies: react 18, express 4, vite 5
├── vite.config.js              # Port 5230, proxy /api → 5231
├── index.html                  # SPA entry point
├── server.js                   # Express micro-API (318 lines)
└── src/
    ├── main.jsx                # React root mount
    ├── App.jsx                 # Root component — tabs, config loading, dirty tracking (308 lines)
    ├── styles/
    │   └── main.css            # Grimdark theme, CSS custom properties (1,187 lines)
    └── components/
        ├── EnemyBrowser.jsx        # Sidebar: search, tag/role filters, sprite thumbs (164 lines)
        ├── EnemyEditor.jsx         # Full enemy stat/visual/skill editor + rarity preview (467 lines)
        ├── AffixEditor.jsx         # Affix browser + detail editor (313 lines)
        ├── ChampionTypeEditor.jsx  # Champion type stat modifier editor (145 lines)
        ├── RosterEditor.jsx        # Read-only floor roster viewer (157 lines)
        ├── Simulator.jsx           # TTK calculator + batch mode (440 lines)
        ├── SpawnPreview.jsx        # Spawn roll distribution preview (203 lines)
        ├── SuperUniqueEditor.jsx   # Super unique boss editor (379 lines)
        ├── ExportPanel.jsx         # Save/diff/backup panel (189 lines)
        └── SpritePicker.jsx        # Visual sprite atlas browser + assignment (270 lines)
```

---

## 4. Data Flow

### Startup Sequence

```
1. App.jsx mounts
2. useEffect → loadData()
3. Parallel fetch:
   ├── GET /api/configs      → all 8 config files loaded at once
   ├── GET /api/enemy-meta   → static metadata (roles, AI, tags, shapes, etc.)
   ├── GET /api/roster       → floor roster parsed from dungeon_generator.py
   └── GET /api/sprites      → sprite atlas JSON for visual picker
4. State populated: configs, meta, roster, spriteAtlas
5. UI renders with Enemies tab active
```

### Edit Cycle

```
1. User modifies a value in any editor component
2. Component calls onUpdate(key, newData) → App.updateConfig()
3. App updates configs state + adds key to dirty Set
4. Save indicator appears: "💾 Save Changes (N)"
5. User clicks Save or presses Ctrl+S
6. App.handleSave() iterates dirty keys:
   └── POST /api/config/:key  (body = full config JSON)
       └── server.js:
           a. Create backup: {filename}.backup-{timestamp}.json
           b. Prune old backups (keep last 5)
           c. Write new config file
7. Dirty set cleared, save status shows "✅ Saved!"
```

### Key Design: Full-Config Writes

The tool always writes the **entire config file** on save, not individual entries. This ensures consistency and simplifies the server. The entry-level CRUD endpoints (`POST /api/config/:key/entry`, `DELETE /api/config/:key/entry/:entryKey`) exist in the API but the React UI uses whole-config saves exclusively.

---

## 5. API Server

The Express server (`server.js`, 318 lines) exposes these endpoints:

### Read Endpoints

| Method | Path | Response | Purpose |
|--------|------|----------|---------|
| GET | `/api/configs` | `{ enemies, rarity, skills, classes, combat, loot_tables, names, super_uniques }` | Bulk-read all 8 config files in one request |
| GET | `/api/config/:key` | Full JSON config | Read a single config by registry key |
| GET | `/api/roster` | `{ tiers: [{ max_floor, pools }] }` | Parse `_FLOOR_ENEMY_ROSTER` from `dungeon_generator.py` |
| GET | `/api/sprites` | `{ sheetFile, sheetWidth, sheetHeight, categories, sprites }` | Sprite atlas metadata from `Combined Character Sheet 1-atlas (3).json` |
| GET | `/api/enemy-meta` | `{ roles, ai_behaviors, tags, shapes, rarity_tiers, affix_categories, rarity_colors, champion_type_ids }` | Static metadata for UI dropdowns and labels |
| GET | `/spritesheet.png` | PNG binary | Serves the combined character spritesheet |

### Write Endpoints

| Method | Path | Body | Purpose |
|--------|------|------|---------|
| POST | `/api/config/:key` | Full config JSON | Overwrite a config file (creates backup first) |
| POST | `/api/config/:key/entry` | `{ entryKey, entryData, section? }` | Add/update a single entry in a config |
| DELETE | `/api/config/:key/entry/:entryKey` | Query: `?section=` | Delete a single entry from a config |

### Backup Strategy

Before every write, the server:
1. Copies the existing file to `{basename}.backup-{Date.now()}.json`
2. Scans for backups matching the same prefix
3. Deletes all but the 5 most recent backups
4. Writes the new data

### Roster Parser

The `/api/roster` endpoint extracts Python data from `dungeon_generator.py` without executing Python. It:
1. Reads the Python source as a string
2. Finds `_FLOOR_ENEMY_ROSTER` by text search
3. Locates the matching `[...]` brackets via depth-tracking
4. Parses the Python tuples `(max_floor, { "pool": [("type", weight)] })` via layered regex:
   - Tier regex: `\(\s*(\d+)\s*,\s*\{...\}\s*\)`
   - Pool regex: `"(\w+)"\s*:\s*\[...\]`
   - Entry regex: `\("(\w+)"\s*,\s*([\d.]+)\)`

This approach avoids Python subprocess dependency and works with any standard formatting of the roster literal.

---

## 6. Config File Registry

The server maps 8 registry keys to JSON files in `server/configs/`:

| Key | File | Writable | Content |
|-----|------|----------|---------|
| `enemies` | `enemies_config.json` | ✅ | All 25 enemy type definitions with stats, visuals, tags, skills |
| `rarity` | `monster_rarity_config.json` | ✅ | Rarity tiers, spawn chances, champion types, 15 affixes, affix rules |
| `skills` | `skills_config.json` | ❌ Read-only | Skill definitions (loaded for class/skill chip display) |
| `classes` | `classes_config.json` | ❌ Read-only | Player class definitions (loaded for simulator hero config) |
| `combat` | `combat_config.json` | ❌ Read-only | Combat constants (loaded for simulator calculations) |
| `loot_tables` | `loot_tables.json` | ✅ | Loot table definitions |
| `names` | `names_config.json` | ✅ | Name generation prefix/suffix pools |
| `super_uniques` | `super_uniques_config.json` | ✅ | Hand-crafted super unique boss definitions |

Read-only configs are loaded by the tool for reference (e.g., the simulator needs class stats and combat formulas) but are never modified by Enemy Forge.

---

## 7. Enemies Tab — Browser & Editor

The Enemies tab uses a master-detail layout: `EnemyBrowser` (left sidebar) + `EnemyEditor` (right detail panel).

### EnemyBrowser (164 lines)

A filterable, searchable list of all enemy types.

**Filtering:**
- **Text search** — matches against enemy ID and display name (case-insensitive)
- **Tag filter** — dropdown auto-populated from all unique tags across enemies (undead, demon, beast, construct, aberration, humanoid)
- **Role filter** — "All" / "Boss Only" / "Non-Boss"

**Sprite thumbnails:** Each list item renders a `BrowserSpriteThumb` sub-component — a 24×24 canvas that draws the enemy's sprite from the loaded spritesheet. Falls back to the enemy's configured color dot if no sprite is assigned.

**Atlas name resolution:** Sprite IDs in the enemy config use `snake_case` (e.g., `undead_knight`), but atlas names use `PascalCase` (e.g., `Undead_Knight_1`). The `getSpriteRegion()` function normalizes by converting atlas names to snake_case and stripping the `_N` variant suffix before matching.

### EnemyEditor (467 lines)

The full editing form for a single enemy. Split into sections:

#### Identity
- **Name** — display name (e.g., "Bone Shambler")
- **Enemy ID** — read-only after creation (e.g., `bone_shambler`)
- **Role** — dropdown with 25 role presets (Swarm, Melee Bruiser, Boss — Demon Overlord, etc.)
- **AI Behavior** — dropdown: aggressive, ranged, support, boss, dummy
- **Description** — free-text textarea

#### Base Stats
Six stat sliders with synchronized range + number inputs:

| Stat | Min | Max | Step | Purpose |
|------|-----|-----|------|---------|
| HP | 1 | 500 | 1 | Base hit points |
| Melee Damage | 0 | 100 | 1 | Base melee attack damage |
| Ranged Damage | 0 | 100 | 1 | Base ranged attack damage |
| Armor | 0 | 50 | 1 | Flat damage reduction |
| Vision Range | 1 | 15 | 1 | FOV detection radius |
| Ranged Range | 0 | 10 | 1 | Ranged attack distance |

#### Stat Callout
Derived metrics displayed as a quick-reference card:
- **Effective HP** — `HP × (1 + Armor/10)` approximation
- **Melee DPS** — melee damage per turn
- **Ranged DPS** — ranged damage per turn
- **Armor** — flat value

#### Visuals
- **Color** — hex color picker for the enemy's map dot / glow tint
- **Shape** — dropdown: circle, square, diamond, triangle, star, hexagon
- **Sprite Picker** — embedded `SpritePicker` component (see [§15](#15-sprite-integration))

#### Tags & Flags
- **Tags** — checkbox group: undead, demon, beast, construct, aberration, humanoid
- **is_boss** — boolean toggle (affects spawn pools, roster placement)
- **allow_rarity_upgrade** — boolean toggle (if false, this enemy always spawns as Normal)

#### Class & Skills
- **class_id** — text input linking to a class definition in `classes_config.json`
- **Skill preview** — if class_id resolves, shows skill chips with icon, name, cooldown, and range for each skill in that class

#### Excluded Affixes
- **excluded_affixes** — comma-separated list of affix IDs that should never roll on this enemy when it spawns as Champion or Rare

#### Rarity Preview Canvas
A 400×100 HTML5 Canvas that renders the enemy at all four rarity tiers side-by-side (Normal → Champion → Rare → Super Unique) with appropriate glow outlines. Uses the actual assigned sprite if available, otherwise draws the configured shape. This provides instant visual feedback for how the enemy will look at each tier in-game.

#### CRUD Operations
- **Create** — opens a form with snake_case ID input, validates uniqueness, creates with sane defaults via `makeDefaultEnemy()` factory
- **Delete** — confirmation dialog, removes from config, clears selection if deleted enemy was selected

---

## 8. Affixes Tab — Monster Affix Editor

`AffixEditor.jsx` (~520 lines) — browse, create, edit, and delete monster affixes with rich descriptions, color-coded categories, and human-readable stat formatting.

Monster affixes are stat/behavior modifiers that roll on Champion and Rare tier enemies. They are distinct from the item affix system (see [affix-system.md](affix-system.md) for item affixes).

### Affix Browser (left panel, 300px)

Filterable list by 9 color-coded categories. Each sidebar item shows:

- **Affix name** (bold)
- **Category badge** — color-coded pill with icon (e.g., ⚔️ Offensive in red, 🛡️ Defensive in blue)
- **AURA badge** — gold indicator if the affix is an aura type
- **Restriction badge** — shows 🏹 ranged only / ⚔️ melee only if applicable
- **Effect summary** — auto-generated 1-line preview of all effects in plain English (e.g., "+50% Attack Damage", "20 damage in 2-tile radius on death")

| Category | Icon | Color | Description |
|----------|------|-------|-------------|
| `offensive` | ⚔️ | Red (#ff4444) | Damage multipliers, bonus damage |
| `defensive` | 🛡️ | Blue (#4488ff) | HP multipliers, armor bonuses, damage reduction |
| `mobility` | 💨 | Teal (#44ddcc) | Movement speed, teleportation |
| `on_death` | 💀 | Purple (#cc44ff) | Effects triggered when the monster dies (explosions, corpse effects) |
| `on_hit` | 🎯 | Orange (#ff8844) | Effects triggered on each attack (life steal, mana burn, slow) |
| `retaliation` | 🔥 | Burnt Orange (#dd6644) | Reflected/thorns damage |
| `disruption` | ⚡ | Violet (#aa44dd) | Crowd control, silence, displacement |
| `debuff` | 🩸 | Pink (#cc6688) | Stat reduction on targets |
| `sustain` | 💚 | Green (#44cc66) | Self-healing, regeneration |

### Summary Banner

When an affix is selected, a prominent banner appears at the top of the detail panel showing:

- Category icon + affix name (large, bold)
- Color-coded left border and gradient background matching the category
- Category badge + AURA badge
- All effects listed in plain English with icons (e.g., "📊 +50% Attack Damage", "💥 On death: 20 damage in 2-tile radius")
- Restriction notice if the affix is limited to melee/ranged

### Affix Detail Editor (right panel)

#### Identity
- **Name** — display name
- **Category** — dropdown with icons and labels (e.g., "⚔️ Offensive", "🛡️ Defensive")
- **Is Aura** — checkbox (aura affixes apply effects in a radius to allies/enemies)
- **Applies To** — dropdown: all / ranged_only / melee_only

#### Effects
Dynamic form for the affix's effect list. Each effect row includes three layers of information:

1. **Effect summary line** — a highlighted bar showing the icon, human-readable description, and a ✕ remove button (e.g., "📊 +50% Attack Damage")
2. **Form fields** — type dropdown (with icons/labels), stat, value inputs with **inline formatted hints** (multiplier `1.5` shows "+50%", chance `0.30` shows "30%", regen `0.03` shows "3% / turn", durations show "2 turns", etc.)
3. **Help text** — italic description explaining what the effect type does in combat

Supported effect types with human-readable labels:

| Effect Type | Label | Icon | Key Fields | Description |
|-------------|-------|------|------------|-------------|
| `stat_multiplier` | Stat Multiplier | 📊 | stat, value | Multiplies a base stat by a factor (1.5 = +50%) |
| `cooldown_reduction_flat` | Cooldown Reduction (Flat) | ⏱️ | value | Reduces all skill cooldowns by N turns |
| `aura_ally_buff` | Aura: Ally Buff | 🔆 | stat, multiplier, radius | Buffs nearby allies each turn |
| `aura_enemy_debuff` | Aura: Enemy Debuff | 🌑 | stat, value, radius | Weakens nearby enemies each turn |
| `on_hit_extend_cooldowns` | On Hit: Extend Cooldowns | ⏳ | turns, target | Extends target's active cooldowns on hit |
| `on_hit_slow` | On Hit: Slow | ❄️ | chance, duration | Chance to slow target on hit |
| `on_death_explosion` | On Death: Explosion | 💥 | damage, radius | AoE damage on death |
| `life_steal_pct` | Life Steal (%) | 🩸 | value | Heals for % of damage dealt |
| `grant_ward` | Ward Shield | 🛡️ | charges, reflect_damage | Absorbs hits and reflects damage |
| `auto_shadow_step` | Auto Teleport | 🌀 | cooldown | Automatically teleports on a timer |
| `set_stat` | Set Stat (Flat) | 📌 | stat, value | Sets a stat to a fixed value |
| `extra_ranged_target` | Extra Ranged Target | 🏹 | count, splash_radius | Fires at additional targets |
| `hp_regen_pct` | HP Regen (% / turn) | 💚 | value | Regenerates % of max HP per turn |

Effects can be added and removed dynamically. Each effect row renders only the fields relevant to that effect type.

#### Name Pools
- **Prefixes** — comma-separated list (e.g., "Blazing, Infernal") for procedural name generation
- **Suffixes** — comma-separated list (e.g., "of Flame, the Scorcher")

The game's name generator combines these with the base enemy name: `"{Prefix} {EnemyName}"` or `"{EnemyName} {Suffix}"`.

#### Compatibility
- **Excluded class skills** — affix IDs that are incompatible
- **Global rules summary** — read-only display of `max_affixes`, `max_auras`, `max_on_death` from `affix_rules`

---

## 9. Champion Types Tab

`ChampionTypeEditor.jsx` (145 lines) — edit the 5 champion type definitions.

Champion types are behavior/stat presets applied to Champion-tier monsters. Each modifies the base enemy in specific ways:

### The 5 Champion Types

| ID | Name | Primary Effect |
|----|------|----------------|
| `berserker` | Berserker | Damage bonus + enrage at low HP |
| `fanatic` | Fanatic | Increased damage + cooldown reduction |
| `ghostly` | Ghostly | Phase through units + dodge chance |
| `resilient` | Resilient | HP multiplier + armor bonus |
| `possessed` | Possessed | Death explosion + bonus damage |

### Editable Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name |
| `color` | hex color | Visual tint applied to the enemy's rendering |
| `damage_bonus` | number | Flat bonus to all damage |
| `enrage_threshold` | 0–1 | HP% at which enrage activates (berserker) |
| `enrage_damage_bonus` | number | Extra damage when enraged |
| `cooldown_reduction` | number | Flat cooldown reduction on all skills |
| `dodge_chance` | 0–1 | Probability to avoid incoming attacks |
| `hp_multiplier` | number | Multiplicative HP scaling (1.0 = no change) |
| `armor_bonus` | number | Flat armor increase |
| `death_explosion_damage` | number | Damage dealt on death in a radius |
| `death_explosion_radius` | number | Tile radius of death explosion |
| `phase_through` | boolean | Can move through other units (ghostly) |

### Effect Summary

The editor auto-generates a natural language description from all non-null fields. For example, a Berserker type might display:

> *"Deals +5 bonus damage. Enrages at 30% HP for +8 extra damage. Tinted #ff4444."*

---

## 10. Floor Roster Tab

`RosterEditor.jsx` (157 lines) — read-only viewer for the dungeon floor enemy roster.

The floor roster defines which enemies can spawn on each floor range in procedurally generated dungeons. This data lives in `dungeon_generator.py` as a Python literal (`_FLOOR_ENEMY_ROSTER`) and is parsed by the API server at startup (see [§5 Roster Parser](#roster-parser)).

### Data Structure

```
Floor Tiers (5 brackets):
  ├── Tier 1: Floors 1–3
  │   ├── regular pool: [(enemy_type, weight), ...]
  │   ├── boss pool:    [(enemy_type, weight), ...]
  │   └── support pool: [(enemy_type, weight), ...]
  ├── Tier 2: Floors 4–6
  │   ├── regular / boss / support pools
  ...
  └── Tier 5: Floors 13+
      └── regular / boss / support pools
```

### Visualization Features

- **Tier selector** — tab buttons for each floor bracket (labels computed from `max_floor` values)
- **Weight bar charts** — horizontal stacked bars per pool, segments proportional to each enemy's weight, colored by the enemy's configured color
- **Normalization warnings** — alert shown if pool weights don't sum to 1.0
- **Detail table** — columns: color dot, enemy_type, display name, role, raw weight, percentage, HP, melee/ranged damage
- **Summary card** — total tier count, total unique enemy types across all rosters

This tab is read-only because the roster is defined in Python source code. Modifications must be made directly in `server/app/core/wfc/dungeon_generator.py`.

---

## 11. TTK Simulator Tab

`Simulator.jsx` (440 lines) — Monte Carlo time-to-kill calculator and encounter balancer.

### Party Configuration

Configure a party of 1–5 heroes:

| Field | Range | Description |
|-------|-------|-------------|
| Party Size | 1–5 | Number of heroes in the encounter |
| Class (per hero) | dropdown | Hero class (loads base stats from `classes_config.json`) |
| Gear Damage Bonus | 0–50 | Simulated equipment damage increase |
| Gear Armor Bonus | 0–30 | Simulated equipment armor increase |
| Gear HP Bonus | 0–200 | Simulated equipment HP increase |

Hero base stats are loaded from `classes_config.json` with fallback defaults (HP: 50, damage: 8, armor: 2) if a class definition is missing.

### Enemy Configuration

| Field | Options | Description |
|-------|---------|-------------|
| Enemy Type | dropdown (all enemies) | Base enemy to simulate against |
| Rarity Tier | Normal / Champion / Rare | Rarity tier to apply |
| Champion Type | dropdown (if Champion) | Which champion type to apply |
| Affixes | checkboxes (if Rare) | Which affixes to apply |
| Trials | 50–1000 | Number of Monte Carlo runs |

### Rarity Scaling Pipeline

The `applyRarityScaling()` function computes the enemy's effective stats through a 3-stage pipeline:

```
1. Base Stats (from enemies_config)
   ↓
2. Rarity Tier Multipliers (from rarity config tier definitions)
   → hp_multiplier, damage_multiplier, armor_bonus, xp_multiplier
   ↓
3. Champion Type Bonuses (if champion tier)
   → hp_multiplier (stacks multiplicatively), damage_bonus, armor_bonus
   ↓
4. Affix Stat Multipliers (if rare tier)
   → each affix's stat_multiplier effects applied multiplicatively
   ↓
= Final Effective Stats
```

### Combat Simulation Algorithm

`simulateEncounter()` runs a simplified turn-based combat loop:

```
For each trial (N trials):
  1. Initialize hero party (HP, damage, armor from effective stats)
  2. Initialize enemy (scaled HP, damage, armor)
  3. Loop up to 100 turns:
     a. Each living hero attacks:
        → damage_dealt = max(1, hero_damage - enemy_armor)
        → enemy_hp -= damage_dealt
        → track per-hero total damage
     b. If enemy HP ≤ 0 → record kill at this turn, break
     c. Enemy attacks one random living hero:
        → damage_dealt = max(1, enemy_damage - hero_armor)
        → hero_hp -= damage_dealt
     d. If all heroes dead → record wipe at this turn, break
  4. If 100 turns reached → record timeout (neither kill nor wipe)
```

### Output Metrics

| Metric | Formula | Description |
|--------|---------|-------------|
| Avg TTK | mean(turns where enemy killed) | Average turns to kill |
| Kill Rate | kills / trials × 100 | % of trials where heroes win |
| Wipe Rate | wipes / trials × 100 | % of trials where all heroes die |
| Avg Heroes Alive | mean(surviving heroes) | Average survivors per trial |
| Avg Hero HP | mean(remaining hero HP) | Average leftover HP |
| Danger Score | `wipeRate×100 + (1 - avgAlive/partySize)×50`, clamped 0–100 | Composite difficulty rating |
| Per-Hero DPS | hero_total_damage / turns_alive | Damage output per hero per turn |

### Batch Mode

"Simulate All" tests every enemy type × 3 rarity tiers (Normal, Champion, Rare) with 50 trials each. Results are sorted by danger score descending. This provides a full balance overview across the entire enemy roster.

---

## 12. Spawn Preview Tab

`SpawnPreview.jsx` (203 lines) — roll-based rarity distribution preview.

### Configuration

| Input | Range | Description |
|-------|-------|-------------|
| Floor Number | 1–20 | Dungeon floor level |
| Number of Rolls | 50–1000 | How many spawn rolls to simulate |

### Spawn Chance Algorithm

`rollRarity()` implements the game's rarity roll logic:

```
floor_bonus = floor × floor_bonus_per_level

champion_chance = champion_base_chance + floor_bonus
rare_chance     = rare_base_chance + floor_bonus

roll = Math.random()

if roll < rare_chance       → Rare
else if roll < rare_chance + champion_chance → Champion  
else                        → Normal

(Super Unique uses a separate per-floor 25% check)
```

Champion types are rolled uniformly from the 5 defined types via `rollChampionType()`.

### Output

- **Effective Chances callout** — shows floor bonus, champion %, rare % at the selected floor
- **Distribution bar chart** — horizontal bars for Normal / Champion / Rare / Super Unique with count and percentage
- **Champion type breakdown** — if any champions rolled, shows per-type distribution bars colored by each type's visual tint
- **Summary table** — tier, count, %, and expected % (calculated from config formulas)

---

## 13. Super Uniques Tab

`SuperUniqueEditor.jsx` (379 lines) — create and edit hand-crafted super unique boss encounters.

Super Uniques are named, themed boss enemies with fixed stats, fixed affixes, follower retinues, custom loot tables, and flavor text. They are the Monster Rarity system's equivalent of Diablo II's super unique monsters.

### Browser (left panel)

Scrollable list showing each super unique with color dot, name, and title. Below the list, a **Spawn Rules summary** displays global settings: `per_floor_chance`, `max_per_run`, `min_floor`.

### Editor Fields

#### Identity
| Field | Type | Description |
|-------|------|-------------|
| Name | string | Super unique name (e.g., "Groth the Defiler") |
| Title | string | Subtitle (e.g., "Keeper of the Ossuary") |
| Flavor Text | textarea | Italic narrative description |
| Base Enemy | dropdown | Base enemy type to derive from |
| Floor Range | min–max | Floor levels where this boss can appear |
| Room Type | string | Dungeon room type restriction |
| Color | hex picker | Visual tint |
| Shape | dropdown | Fallback shape if no sprite |

#### Fixed Stats
Override stats that replace the base enemy's values:

| Stat | Type | Description |
|------|------|-------------|
| HP | number | Hit points (overrides base) |
| Melee Damage | number | Melee attack damage |
| Ranged Damage | number | Ranged attack damage |
| Armor | number | Flat damage reduction |

#### Fixed Affixes
Checkbox list of all affixes from `monster_rarity_config.json`. Unlike Champion/Rare enemies that roll random affixes, Super Uniques have a curated, fixed set that defines their identity.

#### Tags
Checkbox group: undead, demon, beast, construct, aberration, humanoid.

#### Retinue
Dynamic list of followers that spawn alongside the super unique:

| Field | Type | Description |
|-------|------|-------------|
| Enemy Type | dropdown | Follower enemy type |
| Count | number | How many of this type to spawn |

Retinue entries can be added and removed dynamically. This creates themed encounters (e.g., a necromancer boss spawning with skeleton warriors).

#### Loot Table
Dedicated loot rewards for defeating this super unique:

| Field | Type | Description |
|-------|------|-------------|
| Drop Chance | 0–1 | Probability of any loot dropping |
| Min Items | number | Minimum items dropped |
| Max Items | number | Maximum items dropped |
| Guaranteed Rarity | dropdown | Minimum rarity of drops (common/magic/rare/epic) |
| Unique Item Chance | 0–1 | Probability one drop is a unique item |

#### Encounter Preview Card
A formatted read-only display showing the super unique as a player would see it: stylized name + title, flavor text, stat callout, affixes list with names, retinue composition, and floor range.

---

## 14. Export Tab — Save System & Backup Strategy

`ExportPanel.jsx` (189 lines) — the persistence layer for the entire tool.

### Dirty Tracking

The root `App.jsx` maintains a `dirty` Set of config keys. Any modification to any config via `updateConfig()` adds that key to the dirty set. The header shows a "💾 Save Changes (N)" button when dirty configs exist.

### Save Flow

1. **Per-config save** — "Save" button next to each dirty config
2. **Bulk save** — "Save All" saves every dirty config sequentially
3. **Keyboard shortcut** — Ctrl+S (or Cmd+S) triggers bulk save

Each save sends `POST /api/config/:key` with the full config JSON body. The server creates a timestamped backup before writing.

### Diff Viewer

Before saving, you can preview changes with the built-in diff viewer:

1. Click "Diff" next to a dirty config
2. The tool fetches the on-disk version via `GET /api/config/:key`
3. Both versions are JSON-stringified and compared line-by-line
4. Added lines shown with `+` prefix (green), removed with `-` prefix (red)
5. Display capped at 100 changed lines for performance

### Backup Information

The export panel displays:
- All 4 writable config file paths on disk
- Backup naming convention: `{filename}.backup-{timestamp}.json`
- Retention policy: last 5 backups kept, older deleted automatically

### Results Panel

After saving, shows per-config success/failure status with the backup filename that was created.

---

## 15. Sprite Integration

`SpritePicker.jsx` (270 lines) — embedded within the Enemy Editor for visual sprite assignment.

### Atlas System

The tool reads the sprite atlas at `Assets/Sprites/Combined Character Sheet 1-atlas (3).json`, which contains metadata for every sprite region on the combined character spritesheet.

The spritesheet image (`client/public/spritesheet.png`) is served by the Express API and loaded as an HTML5 `Image` object for Canvas rendering.

### Name Resolution Pipeline

Atlas sprites use PascalCase with numeric variant suffixes (e.g., `Undead_Knight_1`, `Undead_Knight_2`, `Undead_Knight_3`). Enemy configs use snake_case IDs without variant suffix (e.g., `undead_knight`). The resolution pipeline:

```
Atlas Name:  "Undead_Knight_2"
    ↓ Strip variant suffix (_N)
Base Name:   "Undead_Knight"
    ↓ PascalCase → snake_case
Sprite ID:   "undead_knight"
    ↓ Match against enemy.sprite_id
✅ Match found → use atlas coordinates for rendering
```

### Sprite Grouping

`groupSpritesByBase()` groups all atlas sprites by their base name using regex `^(.+?)_(\d+)$`. This collapses variant sprites into groups:

```
Atlas entries:              Groups:
  Demon_1                    Demon (3 variants)
  Demon_2                      ├── Demon_1
  Demon_3                      ├── Demon_2
  Undead_Knight_1              └── Demon_3
  Undead_Knight_2            Undead_Knight (2 variants)
  Undead_Knight_3              ├── Undead_Knight_1
                               ├── Undead_Knight_2
                               └── Undead_Knight_3
```

### Assignment

Clicking a sprite group in the browser:
1. Sets `enemy.sprite_id` to the base snake_case key (e.g., `undead_knight`)
2. Sets `enemy.sprite_variants` to the group's variant count (e.g., `3`)

Clearing the assignment removes both fields, and the enemy falls back to shape rendering (colored geometric shape).

### Filtering

- **Category filter** — dropdown populated from atlas `categories` array (default: "Monsters")
- **Text search** — filters sprite groups by base name (case-insensitive)

---

## 16. Rarity Tier Visual System

The Enemy Editor includes a 400×100 canvas preview that renders the selected enemy at all four rarity tiers side-by-side. This is powered by the `drawPreview()` function.

### Rendering Pipeline

```
For each tier (Normal, Champion, Rare, Super Unique):
  1. Calculate position (equally spaced across 400px width)
  2. Draw glow outline (tier-specific color):
     - Normal:       white (#ffffff)
     - Champion:     blue  (#6688ff)
     - Rare:         gold  (#ffcc00)
     - Super Unique: purple (#cc66ff)
  3. If sprite assigned:
     → Draw cropped sprite from spritesheet at tile position
  4. Else:
     → Draw configured shape (circle/square/diamond/triangle/star/hexagon)
        filled with enemy's color
  5. Draw tier label below
```

### Shape Drawing

The `drawShape()` helper supports 6 geometric shapes via Canvas path operations:
- **circle** — `arc()` with configurable radius
- **square** — `rect()` centered on position
- **diamond** — 4-point rotated square path
- **triangle** — 3-point equilateral path
- **star** — 5-point star via alternating inner/outer radius points
- **hexagon** — 6-point regular polygon

---

## 17. Relationship to Game Systems

The Enemy Forge edits config files consumed by several game server systems:

### Direct Config Consumers

| Config File | Server Module | Purpose |
|-------------|---------------|---------|
| `enemies_config.json` | `match_manager.py`, `wave_spawner.py` | Enemy type definitions, stat lookup |
| `monster_rarity_config.json` | `monster_rarity.py` | Rarity rolling, affix application, champion types, spawn chances |
| `super_uniques_config.json` | `monster_rarity.py` | Super unique encounter spawning |
| `loot_tables.json` | `loot.py` | Enemy-specific drop tables |
| `names_config.json` | `monster_rarity.py` | Procedural name generation for champions/rares |

### System Integration Map

```
Enemy Forge (this tool)
    │
    ├──writes──▶ enemies_config.json ──read by──▶ match_manager.py (spawn enemies)
    │                                             wave_spawner.py (wave composition)
    │                                             monster_rarity.py (stat lookup)
    │                                             ai_behavior.py (AI type dispatch)
    │
    ├──writes──▶ monster_rarity_config.json ──read by──▶ monster_rarity.py
    │               │                                      ├── roll_monster_rarity()
    │               │                                      ├── apply_affixes()
    │               │                                      ├── generate_name()
    │               │                                      └── spawn_champion_pack()
    │               │
    │               ├── rarity_tiers (hp/dmg multipliers)
    │               ├── champion_types (5 presets)
    │               ├── affixes (15 modifiers)
    │               ├── affix_rules (max counts)
    │               └── spawn_chances (floor scaling)
    │
    ├──writes──▶ super_uniques_config.json ──read by──▶ monster_rarity.py
    │               └── spawn_rules, per-encounter definitions
    │
    ├──writes──▶ loot_tables.json ──read by──▶ loot.py
    │               └── roll_enemy_loot(), roll_chest_loot()
    │
    ├──writes──▶ names_config.json ──read by──▶ monster_rarity.py
    │               └── generate_name() (prefix + base + suffix)
    │
    ├──reads───▶ skills_config.json (class skill display)
    ├──reads───▶ classes_config.json (simulator hero stats)
    ├──reads───▶ combat_config.json (simulator parameters)
    │
    └──reads───▶ dungeon_generator.py → _FLOOR_ENEMY_ROSTER (floor roster viewer)
```

### Related Documentation

| Document | Location | Relationship |
|----------|----------|-------------|
| Affix System (Items) | [affix-system.md](affix-system.md) | Different system — item prefixes/suffixes, not monster affixes |
| Phase 18 Core | [phase18-monster-rarity-core.md](../Phase%20Docs/phase18-monster-rarity-core.md) | Phase design spec for rarity data model + affix engine + spawn + combat |
| Phase 18 Content | [phase18-monster-rarity-content.md](../Phase%20Docs/phase18-monster-rarity-content.md) | Phase design spec for this tool (18H), super uniques (18G), client VFX (18E–18F) |
| Enemy Forge Tool Ref | [enemy-forge.md](../Tools/enemy-forge.md) | Quick-reference tool documentation |
| Combat System | [combat-system-overview.md](combat-system-overview.md) | How damage/armor/affixes resolve in actual combat |

---

## 18. Port Assignments

| Port | Service | Protocol |
|------|---------|----------|
| 5230 | Vite dev server (React UI) | HTTP |
| 5231 | Express API server | HTTP |

These ports are hardcoded in `vite.config.js` (`strictPort: true`) and `server.js`. They sit alongside other tool ports:

| Tool | UI Port | API Port |
|------|---------|----------|
| Audio Workbench | 5210 | 5211 |
| Item Forge | 5220 | 5221 |
| **Enemy Forge** | **5230** | **5231** |

---

## 19. Quick Start

```bash
# Option 1: Launch script
start-enemy-forge.bat

# Option 2: Manual launch
cd tools/enemy-forge
npm install              # first time only
node server.js &         # API on port 5231
npx vite                 # UI on port 5230 (opens browser)
```

Open **http://localhost:5230** in your browser. The tool loads all config files on startup. Edit enemies, affixes, champion types, or super uniques, then press **Ctrl+S** or click the Save button to write changes back to disk.

### Workflow

1. **Browse** — use the Enemies tab to review existing enemy definitions
2. **Edit** — modify stats, visuals, tags, skills, or create new enemies
3. **Simulate** — switch to TTK Simulator to test balance against hero parties
4. **Tune affixes** — use the Affixes tab to adjust monster modifier effects
5. **Preview spawns** — check Spawn Preview for rarity distribution at target floor levels
6. **Craft bosses** — use Super Uniques to design hand-crafted encounter experiences
7. **Review roster** — confirm floor roster composition looks correct
8. **Export** — save all changes, review diffs, and verify backups were created
