# Item Forge — Dev Tool Documentation

> **Location:** `tools/item-forge/`  
> **Launch:** `start-item-forge.bat`  
> **Ports:** UI on `5220`, API on `5221`  
> **Architecture:** React 18 + Vite 5 frontend, Express 4 micro-API backend  

## Overview

Item Forge is a standalone development tool for creating, editing, balancing, and simulating the game's item/equipment system. It reads and writes the JSON config files in `server/configs/` directly, with automatic backup-on-save (keeps last 5 per config).

## Tabs

### 1. ⚡ Affixes (Prefix/Suffix Editor)

- **Sortable table** of all prefixes and suffixes with columns: Type, Name, Stat, Min, Max, iLvl Scale, Weight, Slots
- **Filters:** type (prefix/suffix), slot, stat
- **Weight distribution bar** — colored segments showing relative roll probability with hover tooltips
- **Edit modal** with value preview at item levels 1/5/10/15/18
- **Create new affix** with prefix/suffix type selector, all 20 stat types available
- **Delete with confirmation**

### 2. 🗡️ Base Items

- **Sortable/filterable table** with dynamic stat columns (only shows stats in use)
- **Filters:** search, slot, rarity, item type
- **Stat budget calculation** using Phase 16H point equivalencies
- **Budget color coding:** green = in range, yellow = under, red = over for rarity tier
- **Edit/Create modal** with all 20 stat inputs and budget bar visualization
- Rarity-colored labels and slot badges

### 3. ⭐ Uniques

- **Card grid layout** with unique-orange border styling
- Each card shows: stats, stat budget, special effect, flavor text, best-for classes
- **Drop rules summary** (base chance, min tier, max per run, MF scaling, floor scaling)
- **Filter** by slot, class, search
- **Edit/Create modal** with special effect editor (effect_id, type, value, description)
- Best-for class checkbox group

### 4. 🛡️ Sets

- **Set card layout** with set-green border styling
- Each set shows: pieces (with slot badges), stat bonuses, set bonuses (2-piece, 3-piece)
- **Class affinity filter**
- **Create/Edit modal** with:
  - Dynamic piece management (add/remove pieces)
  - Per-piece stat editing
  - Multi-tier set bonus editing
- Handles missing `sets_config.json` gracefully (Phase 16E scaffold)

### 5. 🎲 Item Simulator

Three sub-tabs:

#### Generator
- **Roll random items** with configurable rarity, slot, and item level
- Roll 1, 10, or 100 items at once
- **Card grid** showing item name, stats, budget, affixes (color-coded prefix/suffix tags)
- **Pin & compare** — click to pin an item, see stat deltas (▲/▼) on all other items
- Items show full generated names (prefix + base + suffix)

#### Distribution
- **Monte Carlo simulation** — generate 100–10,000 items
- **Affix frequency chart** — bar graph showing how often each affix appears
- **Stat averages table** — avg, min, max, appearance % for each stat
- **Budget distribution histogram** — 10-bin chart with in-range/out-of-range coloring
- Target budget range overlay per rarity

#### Drop Rates
- **Interactive calculator** with sliders for dungeon floor (1–12) and magic find (0–60%)
- **Boss kill toggle** for guaranteed rarity and unique chance
- **Rarity distribution bar** — visual percentage breakdown with smooth transitions
- **Effective rates table** — base %, effective %, "1 in N drops" column
- **Boss bonuses panel** — guaranteed minimum rarity, unique chance, drop count ranges
- **Floor bonus progression** — visual step display showing each floor range bonus

## Config Files Managed

| Config Key | File | Description |
|-----------|------|-------------|
| `affixes` | `affixes_config.json` | 12 prefixes + 10 suffixes with weights, stat scaling, slot restrictions |
| `items` | `items_config.json` | ~18 base item types with stat bonuses, slots, rarities |
| `uniques` | `uniques_config.json` | 16 unique items with special effects, class affinities, drop rules |
| `item_names` | `item_names_config.json` | Display name mappings |
| `loot_tables` | `loot_tables.json` | Rarity rates, floor bonuses, boss rules, enemy loot pools |
| `combat` | `combat_config.json` | Combat stats, formulas |
| `sets` | `sets_config.json` | Set definitions (created by tool if missing) |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/configs` | Load all 7 config files at once |
| GET | `/api/config/:key` | Load a single config |
| POST | `/api/config/:key` | Write full config (creates backup) |
| POST | `/api/config/:key/entry` | Add/update single entry |
| DELETE | `/api/config/:key/entry/:entryKey` | Delete entry |
| GET | `/api/stats-meta` | Stat metadata: labels, types, budget points, caps, rarity rules |

## Backup System

Every save creates a timestamped backup: `filename.backup-1234567890.json`

Only the 5 most recent backups are kept per config file. Backups are stored alongside the original config in `server/configs/`.

## Tech Stack

- **Frontend:** React 18, Vite 5, single-page app
- **Backend:** Express 4 with CORS, direct JSON file I/O
- **Styling:** Custom grimdark CSS with CSS variables for rarity colors
- **Pattern:** Same architecture as `tools/audio-workbench/`

## File Structure

```
tools/item-forge/
├── package.json
├── vite.config.js
├── index.html
├── server.js                    # Express API (port 5221)
└── src/
    ├── main.jsx                 # React entry point
    ├── styles/
    │   └── forge.css            # Full grimdark theme (~500 lines)
    └── components/
        ├── AffixEditor.jsx      # Prefix/suffix browser & editor
        ├── BaseItemEditor.jsx   # Base item type editor with budget calc
        ├── UniqueEditor.jsx     # Unique item card editor
        ├── SetEditor.jsx        # Set item manager & creator
        └── ItemSimulator.jsx    # Generator, distribution & drop rates
```
