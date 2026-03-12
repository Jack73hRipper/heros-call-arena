# Enemy Forge

**Phase 18H — Monster Rarity Content Tool**

A standalone React + Express dev tool for editing, simulating, and previewing all Monster Rarity system data. Follows the same architecture as [Item Forge](item-forge.md).

## Quick Start

```bash
start-enemy-forge.bat
# or manually:
cd tools/enemy-forge
npm install
node server.js &       # API on port 5231
npx vite               # UI  on port 5230
```

Open **http://localhost:5230** in your browser.

## Architecture

| Layer | Tech | Port |
|-------|------|------|
| UI | Vite 5 + React 18 | 5230 |
| API | Express 4 (ESM) | 5231 |

The Vite dev server proxies `/api` requests to the Express backend. The backend reads and writes JSON config files in `server/configs/` with automatic timestamped backups (last 5 kept).

## Tabs

### 1. Enemies
Browse all 25 enemy types in a searchable sidebar. Edit stats (HP, melee damage, ranged damage, armor, vision range, attack range), visual properties (color, shape), identity (role, AI behavior, description), tags, class/skill bindings, boss flag, rarity upgrade eligibility, and excluded affixes. Includes a live canvas preview showing the enemy at each rarity tier with appropriate glow effects.

### 2. Affixes
Browse and edit all 15 affixes with rich descriptions and formatted stats. Features:

- **Summary banner** — Each affix displays a color-coded banner at the top of the detail panel showing all effects in plain English (e.g., "⚔️ +50% Attack Damage", "💥 On death: 20 damage in 2-tile radius")
- **Category color coding** — 9 categories each have a unique color and icon: ⚔️ Offensive (red), 🛡️ Defensive (blue), 💨 Mobility (teal), 💀 On Death (purple), 🎯 On Hit (orange), 🔥 Retaliation (burnt orange), ⚡ Disruption (violet), 🩸 Debuff (pink), 💚 Sustain (green)
- **Sidebar effect previews** — Each affix in the sidebar list shows a 1-line summary of its effects (e.g., "+50% Attack Damage · heals 20% of damage dealt"), category badge, aura/restriction badges
- **Human-readable effect labels** — Dropdown options show "📊 Stat Multiplier", "❄️ On Hit: Slow", "💥 On Death: Explosion" etc. instead of raw snake_case identifiers
- **Formatted stat values** — Multipliers display as "+50%" instead of raw `1.5`, chances as "30%" instead of `0.30`, regen as "3% / turn" instead of `0.03`, durations as "2 turns", etc. Inline hints appear next to every number input
- **Inline help text** — Each effect row includes an italic description explaining what the effect type does in combat (e.g., "Heals for a percentage of damage dealt on each hit")
- **Remove effect button** — Each effect row has a ✕ button to delete individual effects

Each affix has: name, category, aura flag, applies-to filter, effects (stat modifications via flat/percent/override), prefix/suffix name pools for display-name generation, and compatibility rules. Create or delete affixes.

### 3. Champion Types
Edit the 5 champion types (Berserker, Fanatic, Ghostly, Resilient, Possessed). Each has stat modifiers (damage bonus, HP multiplier, enrage threshold, etc.), a visual tint color, and phase-through flag. Includes an auto-generated effect summary.

### 4. Floor Roster
Read-only view of the `_FLOOR_ENEMY_ROSTER` from `dungeon_generator.py`. Shows all 5 floor tiers with per-pool (regular, boss, support) weight bars and detail tables. Weights are parsed from the Python source at startup.

### 5. TTK Simulator
Time-to-kill calculator. Configure a party of 1–5 heroes (class, gear bonus) and an enemy encounter (type, rarity, champion type, affixes). Runs N simulated combat trials to produce: average TTK, kill/wipe rates, danger score (0–100), per-hero DPS and HP remaining. Batch mode simulates every enemy × every rarity tier sorted by danger.

### 6. Spawn Preview
Roll-based distribution preview. Configure a floor number and roll count, then simulate spawn rolls to see actual vs. expected rarity distribution (Normal / Champion / Rare / Super Unique), champion type breakdown, and summary statistics.

### 7. Super Uniques
Create and edit named super unique bosses. Each has: fixed stats (HP, damage, armor), fixed affixes, retinue (follower composition), loot table (drop chance, item count, guaranteed rarity, unique item chance), flavor text, floor range, and visual properties. Includes an encounter preview card.

### 8. Export
Save modified configs back to disk. Shows dirty/clean status per file, line-level diff preview against on-disk version, individual or bulk save, and backup creation log.

## Config Files Read/Written

| Key | File | Purpose |
|-----|------|---------|
| `enemies` | `server/configs/enemies_config.json` | All 25 enemy type definitions |
| `rarity` | `server/configs/monster_rarity_config.json` | Rarity tiers, champion types, affixes, spawn chances |
| `skills` | `server/configs/skills_config.json` | Skill definitions (read-only) |
| `classes` | `server/configs/classes_config.json` | Player class definitions (read-only, for simulator) |
| `combat` | `server/configs/combat_config.json` | Combat constants (read-only, for simulator) |
| `loot_tables` | `server/configs/loot_tables.json` | Loot table definitions |
| `names` | `server/configs/names_config.json` | Name generation pools |
| `super_uniques` | `server/configs/super_uniques_config.json` | Super unique boss definitions |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/configs` | Bulk-read all config files |
| GET | `/api/config/:key` | Read a single config file |
| POST | `/api/config/:key` | Write a config file (creates backup) |
| GET | `/api/roster` | Parse floor roster from dungeon_generator.py |
| GET | `/api/enemy-meta` | Static metadata (roles, AI behaviors, tags, shapes, rarity tiers, etc.) |

## File Structure

```
tools/enemy-forge/
├── package.json
├── vite.config.js
├── index.html
├── server.js               # Express API
└── src/
    ├── main.jsx
    ├── App.jsx             # Root — tabs, config loading, dirty tracking
    ├── styles/
    │   └── main.css        # Grimdark theme (CSS variables)
    └── components/
        ├── EnemyBrowser.jsx      # Sidebar with search, tag/role filters
        ├── EnemyEditor.jsx       # Full enemy stat/visual/skill editor
        ├── AffixEditor.jsx       # Affix browser + rich detail editor (summary banner, color-coded categories, formatted stats, inline help)
        ├── ChampionTypeEditor.jsx # Champion type stat editor
        ├── RosterEditor.jsx      # Read-only floor roster viewer
        ├── Simulator.jsx         # TTK calculator + batch mode
        ├── SpawnPreview.jsx      # Spawn roll distribution preview
        ├── SuperUniqueEditor.jsx # Super unique boss editor
        └── ExportPanel.jsx       # Save/diff/backup panel
```

## Related Systems
- **Phase 18A** — Monster Rarity Data Model (`monster_rarity_config.json`)
- **Phase 18B** — Affix Engine (150 tests)
- **Phase 18C** — Spawn Integration (28 tests)
- **Phase 18D** — Combat Integration (33 tests, auras, on-hit, on-death)
- **Phase 18E–18G** — Super Uniques, Client VFX, Stat Scaling (planned)
- **Phase 18I** — Enemy Identity Skills (Demon Enrage, Bone Shield, Imp Frenzy, Dark Pact, Profane Ward)
