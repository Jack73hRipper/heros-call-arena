# Phase 18 — Monster Rarity & Affix System (Content, Visuals & Tooling)

**Created:** March 3, 2026
**Status:** 18H Complete · 18I Complete · 18G Complete · 18E Complete · 18F Complete
**Previous:** Phase 17 (Mage Class)
**Goal:** Client presentation of enhanced monsters, loot integration, hand-crafted super uniques, the Enemy Forge balance tool, and enemy identity skill additions.

> **Companion Document:** [phase18-monster-rarity-core.md](phase18-monster-rarity-core.md) — Phases 18A–18D (data model, affix engine, spawn integration, combat integration)

---

## Table of Contents

1. [Phase 18E — Client Visual Feedback](#1-phase-18e--client-visual-feedback)
2. [Phase 18F — Loot Integration](#2-phase-18f--loot-integration)
3. [Phase 18G — Super Uniques](#3-phase-18g--super-uniques)
4. [Phase 18H — Enemy Forge Tool](#4-phase-18h--enemy-forge-tool)
5. [Phase 18I — Enemy Identity Skills](#5-phase-18i--enemy-identity-skills)

---

## 1. Phase 18E — Client Visual Feedback

**Goal:** Players must immediately see what tier a monster is. Name colors, glow effects, particles, and the enemy panel all need to reflect rarity.
**Depends on:** 18C (rarity data in WebSocket broadcast)

### 1.1 Name Color System

The server broadcasts `monster_rarity`, `display_name`, and `champion_type` on each player state. The client uses these to render:

| Tier | Name Color | Display Name | Example |
|---|---|---|---|
| Normal | `#ffffff` (white) | Base name | "Skeleton" |
| Champion | `#6688ff` (blue) | "Champion {name}" | "Champion Skeleton" |
| Rare | `#ffcc00` (gold) | Generated name | "Blazing Skeleton the Pyreborn" |
| Super Unique | `#cc66ff` (purple) | Fixed name | "Griswold the Blacksmith" |

### 1.2 Canvas Rendering — Unit Decorations

In `unitRenderer.js`, add rarity-based visual layers:

| Layer | Normal | Champion | Rare | Super Unique |
|---|---|---|---|---|
| **Name text** | White, standard size | Blue, standard size | Gold, slightly larger | Purple, larger + bold |
| **Outline glow** | None | Thin blue pulse (2px) | Thick gold pulse (3px) | Purple + particles |
| **Shape border** | Default | Blue border | Gold border | Purple border |
| **Champion type tint** | — | Overlay tint from `visual_tint` config | — | — |
| **Affix particle hints** | — | — | 1 small looping particle per affix type (fire ember, frost shard, etc.) | Same as rare |
| **Size modifier** | 1.0× | 1.0× | 1.1× (slightly larger sprite/shape) | 1.2× |

### 1.3 Champion Type Visual Effects

| Champion Type | Visual | How |
|---|---|---|
| Berserker | Red tint, pulsing when enraged | Tint overlay in `unitRenderer.js`. Below 30% HP: faster pulse |
| Fanatic | Yellow tint, speed-line trail | Tint + 2-frame motion blur trail |
| Ghostly | Semi-transparent (50% alpha) | `globalAlpha = 0.5` during draw |
| Resilient | Grey/stone tint, thicker outline | Grey tint + 4px outline |
| Possessed | Dark purple shadow wisps | Small particle emitter attached to unit (use existing particle system) |

### 1.4 Affix Visual Indicators

Small ambient particle effects on the unit to hint at affixes (subtle, not overwhelming):

| Affix | Particle Hint |
|---|---|
| Fire Enchanted | Tiny ember particles orbiting unit |
| Cold Enchanted | Small frost crystal sparkles |
| Thorns | Spike/thorn shapes poking out of shape border |
| Might Aura | Faint red circle pulsing at aura radius |
| Conviction Aura | Faint dark circle pulsing at aura radius |
| Shielded | Existing Ward blue shield visual |
| Teleporter | Occasional flicker/displacement effect |
| Regenerating | Faint green ticking sparkle |

### 1.5 Enemy Panel Updates

The Enemy Panel (`client/src/components/EnemyPanel/`) shows targeted enemy info. Update to display:

- **Rarity tier** — colored badge next to name (or colored name)
- **Champion type** — e.g. "⚔ Berserker" tag below name
- **Active affixes** — small icon row with tooltip on hover showing affix name + description
- **Display name** — use `display_name` instead of base `enemy_type` name

### 1.6 Minimap Indicators

On the minimap (`minimapRenderer.js`):
- Champions: blue dot (instead of default red)
- Rares: gold dot (larger than normal)
- Super Uniques: purple dot (largest)

### 1.7 Combat Log Formatting

When enhanced enemies act or die, the combat log should use colored names:
- `<span style="color: #ffcc00">Blazing Skeleton the Pyreborn</span> attacks Aldric for 28 damage!`
- On death: `Champion Skeleton (Berserker) has been slain!`

### 1.8 Death Effects

| Trigger | Visual |
|---|---|
| Fire Enchanted on-death explosion | Burst of fire particles (2-tile radius) + screen shake on nearby heroes |
| Possessed on-death explosion | Purple explosion particles (1-tile radius) |
| Rare death | Gold loot explosion particles (celebrate the kill) |
| Super Unique death | Large purple + gold particle burst |

### 1.9 Implementation Checklist

| # | Task | File(s) | Status |
|---|---|---|---|
| E1 | Parse `monster_rarity`, `display_name`, `champion_type`, `affixes` from player state broadcast | `combatReducer.js` | ✅ |
| E2 | Add rarity-based name color rendering in `unitRenderer.js` | `unitRenderer.js` | ✅ |
| E3 | Add outline glow / pulse effect per rarity tier | `unitRenderer.js` | ✅ |
| E4 | Add champion type tint overlay (alpha blend per `visual_tint`) | `unitRenderer.js` | ✅ |
| E5 | Add affix ambient particle effects (fire embers, frost, thorns, etc.) | `ParticleManager.js`, `Arena.jsx` | ✅ |
| E6 | Add Ghostly transparency rendering (`globalAlpha = 0.5`) | `unitRenderer.js` | ✅ |
| E7 | Update Enemy Panel to show rarity badge, champion type, affix icons | Enemy Panel components | ✅ |
| E8 | Update minimap dot colors for champion/rare/super unique | `minimapRenderer.js` | ✅ |
| E9 | Update combat log to use colored display names | `CombatLog/` components | ✅ |
| E10 | Add on-death explosion particle effects (Fire Enchanted, Possessed) | `ParticleManager.js` | ✅ |
| E11 | Add rare/super unique death celebration particles | `ParticleManager.js` | ✅ |
| E12 | Add new particle preset JSON files for affix effects | `client/public/particle-presets/affixes.json` | ✅ |

**Exit Criteria:** Players can visually distinguish Normal/Champion/Rare/Super Unique at a glance. Enhanced enemies have colored names, glow outlines, ambient particles, and proper panel display. Deaths produce appropriate effects.

---

## 2. Phase 18F — Loot Integration

**Goal:** Enhanced monsters drop better loot. Champions, Rares, and Super Uniques have boosted drop rates and guaranteed rarities.
**Depends on:** 18C (rarity data on spawned enemies), existing loot system in `loot.py`

### 2.1 Drop Modifiers by Monster Rarity

The existing `loot.py` → `roll_enemy_loot()` function looks up the enemy's loot table by `enemy_type`. We augment this with rarity bonuses:

| Tier | Drop Chance Bonus | Bonus Items | Guaranteed Rarity | MF Bonus |
|---|---|---|---|---|
| Normal | +0% | +0 | None | +0% |
| Champion | +50% | +1 | None | +25% |
| Rare | +100% (always drops) | +2 | magic+ | +50% |
| Super Unique | +100% (always drops) | +3 | rare+ | +100% |

### 2.2 How It Works

```python
def roll_enemy_loot(enemy_type, monster_rarity=None, floor_number=1, killer_magic_find=0):
    """Enhanced loot rolling that accounts for monster rarity tier."""
    
    table = get_loot_table(enemy_type)
    rarity_config = get_rarity_tier(monster_rarity or "normal")
    
    # 1. Modify drop chance
    effective_drop_chance = min(1.0, table["drop_chance"] + rarity_config["loot_drop_chance_bonus"])
    
    # 2. Roll for drop
    if random.random() > effective_drop_chance:
        return []
    
    # 3. Determine item count (base + bonus)
    base_count = random.randint(table["min_items"], table["max_items"])
    total_count = base_count + rarity_config["loot_bonus_items"]
    
    # 4. Roll items with guaranteed rarity floor
    items = []
    for i in range(total_count):
        item = roll_item_from_pools(table["pools"], floor_number, killer_magic_find)
        if i == 0 and rarity_config["loot_guaranteed_rarity"]:
            item = ensure_minimum_rarity(item, rarity_config["loot_guaranteed_rarity"])
        items.append(item)
    
    return items
```

### 2.3 Gold Bonus

Enhanced enemies also drop bonus gold (future gold drop system):

| Tier | Gold Multiplier |
|---|---|
| Normal | 1.0× |
| Champion | 1.5× |
| Rare | 2.5× |
| Super Unique | 5.0× |

### 2.4 Kill Notification

When a Rare or Super Unique dies, broadcast a special event for the client to display:

```json
{
  "type": "elite_kill",
  "monster_rarity": "rare",
  "display_name": "Blazing Skeleton the Pyreborn",
  "killer_id": "player_123",
  "loot_items": [...]
}
```

The client can show a brief center-screen notification: **"Blazing Skeleton the Pyreborn has been vanquished!"**

### 2.5 Implementation Checklist

| # | Task | File(s) | Status |
|---|---|---|---|
| F1 | Update `roll_enemy_loot()` to accept `monster_rarity` parameter | `server/app/core/loot.py` | ✅ Done |
| F2 | Apply drop chance bonus, bonus item count, guaranteed rarity floor per tier | `server/app/core/loot.py` | ✅ Done |
| F3 | Update `_resolve_deaths()` to pass `monster_rarity` to loot roller | `server/app/core/turn_resolver.py` | ✅ Done |
| F4 | Add gold multiplier for enhanced enemies (when gold drops are implemented) | `server/app/core/loot.py` | ✅ Done |
| F5 | Broadcast `elite_kill` event for rare/super unique deaths | `server/app/core/turn_resolver.py` | ✅ Done |
| F6 | Client: handle `elite_kill` event — center-screen notification | `combatReducer.js`, new notification component | ✅ Done |
| F7 | Write tests: loot bonus math, guaranteed rarity enforcement, bonus item counts | `server/tests/test_loot_rarity.py` | ✅ Done (38 tests) |

**Exit Criteria:** Champions drop noticeably more/better loot. Rares always drop with magic+ guaranteed. Super Uniques feel rewarding. Kill notifications appear for elite kills.

---

## 3. Phase 18G — Super Uniques

**Goal:** Hand-crafted named bosses with fixed locations, fixed affixes, unique flavor text, and special loot tables.
**Depends on:** 18D (affix combat effects working), 18F (loot tier scaling)

### 3.1 Design Philosophy

Super Uniques are the "Rakanishu" / "The Countess" / "Pindleskin" of our game. They:
- Appear at **fixed dungeon locations** (specific floor + specific room type, or specific map checkpoints)
- Have **fixed affixes** (not random) — their encounter is designed
- Have a **unique name and flavor text**
- Can have a **fixed retinue** of specific followers
- Have a **unique loot table** with chance at exclusive items
- Are **repeatable** across dungeon runs but always the same fight

### 3.2 New Config: `server/configs/super_uniques_config.json`

```json
{
  "super_uniques": {
    "malgris_the_defiler": {
      "id": "malgris_the_defiler",
      "base_enemy": "demon",
      "name": "Malgris the Defiler",
      "title": "Pit Lord of the Lower Catacombs",
      "flavor_text": "The stench of brimstone precedes him. None who enter his domain leave unscathed.",
      "floor_range": [3, 5],
      "room_type": "boss",
      "base_hp": 420,
      "base_melee_damage": 30,
      "base_armor": 10,
      "affixes": ["extra_strong", "fire_enchanted"],
      "retinue": [
        { "enemy_type": "imp", "count": 3 },
        { "enemy_type": "acolyte", "count": 1 }
      ],
      "loot_table": {
        "drop_chance": 1.0,
        "min_items": 3,
        "max_items": 4,
        "guaranteed_rarity": "rare",
        "unique_item_chance": 0.15,
        "pools": [
          { "weight": 30, "items": ["uncommon_greatsword", "uncommon_warhammer"] },
          { "weight": 25, "items": ["uncommon_plate_armor", "uncommon_shadow_cloak"] },
          { "weight": 20, "items": ["uncommon_sigil_ring", "uncommon_skull_pendant"] },
          { "weight": 15, "items": ["greater_health_potion"] },
          { "weight": 10, "items": ["portal_scroll"] }
        ]
      },
      "tags": ["demon"],
      "color": "#ff2200",
      "shape": "star"
    },
    "serelith_bonequeen": {
      "id": "serelith_bonequeen",
      "base_enemy": "necromancer",
      "name": "Serelith, Bonequeen",
      "title": "Mistress of the Ossuary",
      "flavor_text": "She was a healer once. Now she raises the dead and binds them with sinew and spite.",
      "floor_range": [5, 7],
      "room_type": "boss",
      "base_hp": 480,
      "base_melee_damage": 10,
      "base_ranged_damage": 20,
      "base_armor": 8,
      "affixes": ["regenerating", "might_aura", "cold_enchanted"],
      "retinue": [
        { "enemy_type": "skeleton", "count": 4 },
        { "enemy_type": "undead_caster", "count": 1 }
      ],
      "loot_table": {
        "drop_chance": 1.0,
        "min_items": 3,
        "max_items": 5,
        "guaranteed_rarity": "rare",
        "unique_item_chance": 0.20,
        "pools": [
          { "weight": 30, "items": ["uncommon_staff", "uncommon_wand"] },
          { "weight": 25, "items": ["uncommon_robes", "uncommon_vestments"] },
          { "weight": 25, "items": ["uncommon_skull_pendant", "uncommon_sigil_ring"] },
          { "weight": 20, "items": ["greater_health_potion", "portal_scroll"] }
        ]
      },
      "tags": ["undead"],
      "color": "#bb44ff",
      "shape": "star"
    },
    "gorvek_ironhide": {
      "id": "gorvek_ironhide",
      "base_enemy": "construct",
      "name": "Gorvek Ironhide",
      "title": "Eternal Sentinel of the Vault",
      "flavor_text": "Forged in an age before memory. Its makers are dust but their guardian endures.",
      "floor_range": [7, 9],
      "room_type": "boss",
      "base_hp": 700,
      "base_melee_damage": 28,
      "base_armor": 18,
      "affixes": ["stone_skin", "thorns", "shielded"],
      "retinue": [
        { "enemy_type": "construct", "count": 2 }
      ],
      "loot_table": {
        "drop_chance": 1.0,
        "min_items": 4,
        "max_items": 5,
        "guaranteed_rarity": "rare",
        "unique_item_chance": 0.25,
        "pools": [
          { "weight": 30, "items": ["uncommon_plate_armor", "uncommon_brigandine"] },
          { "weight": 25, "items": ["uncommon_greatsword", "uncommon_warhammer"] },
          { "weight": 25, "items": ["uncommon_sigil_ring", "uncommon_crit_charm"] },
          { "weight": 20, "items": ["greater_health_potion", "portal_scroll"] }
        ]
      },
      "tags": ["construct"],
      "color": "#556677",
      "shape": "star"
    },
    "the_hollow_king": {
      "id": "the_hollow_king",
      "base_enemy": "undead_knight",
      "name": "The Hollow King",
      "title": "Usurper of the Throne Eternal",
      "flavor_text": "A crown of black iron sits upon a skull that remembers its coronation. He will not yield his throne.",
      "floor_range": [9, 99],
      "room_type": "boss",
      "base_hp": 800,
      "base_melee_damage": 35,
      "base_armor": 16,
      "affixes": ["extra_strong", "cursed", "stone_skin", "conviction_aura"],
      "retinue": [
        { "enemy_type": "demon_knight", "count": 2 },
        { "enemy_type": "dark_priest", "count": 1 }
      ],
      "loot_table": {
        "drop_chance": 1.0,
        "min_items": 4,
        "max_items": 6,
        "guaranteed_rarity": "epic",
        "unique_item_chance": 0.35,
        "pools": [
          { "weight": 25, "items": ["uncommon_greatsword", "uncommon_warhammer", "uncommon_flail"] },
          { "weight": 25, "items": ["uncommon_plate_armor", "uncommon_shadow_cloak"] },
          { "weight": 20, "items": ["uncommon_sigil_ring", "uncommon_skull_pendant", "uncommon_crit_charm"] },
          { "weight": 15, "items": ["greater_health_potion"] },
          { "weight": 15, "items": ["portal_scroll"] }
        ]
      },
      "tags": ["undead"],
      "color": "#220044",
      "shape": "star"
    }
  },

  "spawn_rules": {
    "_comment": "Super uniques have a chance to replace the normal boss on eligible floors.",
    "per_floor_chance": 0.25,
    "max_per_run": 1,
    "min_floor": 3
  }
}
```

### 3.3 Spawn Logic

1. When generating a boss room on an eligible floor, check if any super uniques match the floor range
2. Roll against `per_floor_chance` (25%)
3. If triggered, replace the normal boss with the super unique + its fixed retinue
4. Max 1 super unique per dungeon run
5. Super unique uses its own stats (overrides base enemy stats entirely)

### 3.4 Implementation Checklist

| # | Task | File(s) | Status |
|---|---|---|---|
| G1 | Create `server/configs/super_uniques_config.json` with initial 4 super uniques | `super_uniques_config.json` | ✅ |
| G2 | Add super unique config loader with caching + validation | `server/app/core/monster_rarity.py` | ✅ |
| G3 | Add super unique spawn logic in `map_exporter.py` — replace boss on eligible floors | `map_exporter.py` | ✅ |
| G4 | Add super unique creation function — apply fixed stats, affixes, retinue | `monster_rarity.py` | ✅ |
| G5 | Add super unique loot table support in `loot.py` | `loot.py` | ✅ |
| G6 | Client: purple name rendering, large death particle burst | `unitRenderer.js`, particle presets | deferred (client) |
| G7 | Client: flavor text display on target (Enemy Panel tooltip) | Enemy Panel components | deferred (client) |
| G8 | Write tests: super unique spawning conditions, stat overrides, retinue creation, loot tables | `test_super_uniques.py` | ✅ (63 tests) |

**Exit Criteria:** Super uniques spawn in eligible dungeon runs with their fixed retinue. They use their own stats and loot tables. Client shows purple names and flavor text.

---

## 4. Phase 18H — Enemy Forge Tool

**Goal:** A standalone dev tool (following the Item Forge pattern) for creating, editing, balancing, and simulating enemies, affixes, and floor rosters.
**Depends on:** 18A–18D (all server systems in place to test against)

### 4.1 Architecture

Following the existing tool pattern (`tools/item-forge/`):

```
tools/enemy-forge/
├── index.html
├── package.json
├── vite.config.js
├── server.js              # Express server to read/write config files
└── src/
    ├── main.jsx
    ├── App.jsx
    ├── components/
    │   ├── EnemyBrowser.jsx       # Browse/filter all 24 enemy types
    │   ├── EnemyEditor.jsx        # Edit enemy stats, skills, tags, colors
    │   ├── AffixEditor.jsx        # Browse/edit/create affixes
    │   ├── ChampionTypeEditor.jsx # Edit champion type definitions
    │   ├── RosterEditor.jsx       # Floor roster weight editor (drag & drop)
    │   ├── Simulator.jsx          # TTK calculator + encounter simulator
    │   ├── SpawnPreview.jsx       # Preview spawn rolls for a floor
    │   ├── SuperUniqueEditor.jsx  # Create/edit super unique encounters
    │   └── ExportPanel.jsx        # Save to config files
    └── styles/
        └── main.css
```

### 4.2 Feature: Enemy Browser

- Left sidebar listing all enemies from `enemies_config.json`
- Filter by tag (undead, demon, beast, etc.), role, is_boss
- Color-coded by creature family
- Click to load into the editor
- Search bar for quick filtering

### 4.3 Feature: Enemy Editor

- **Stat sliders** — HP, melee damage, ranged damage, armor, vision range, ranged range
- **Role dropdown** — Swarm, Standard, Priority, Bruiser, Elite, Boss
- **AI behavior** dropdown — aggressive, ranged, boss, support, dummy
- **Class ID** dropdown — connects to skill kit from `class_skills` in skills_config
- **Tags** — multi-select checkboxes (undead, demon, beast, construct, aberration, humanoid)
- **Skills preview** — read-only display of what skills this enemy has based on class_id
- **Color picker** + **Shape selector** — visual preview
- **Sprite variant count** — how many visual variants exist
- **Excluded affixes** — multi-select for affixes that shouldn't roll on this enemy
- **Allow rarity upgrade** — toggle
- **Live preview** — canvas rendering showing what the enemy looks like at each rarity tier

### 4.4 Feature: Affix Editor

- Browse all affixes from `monster_rarity_config.json`
- Edit effects, prefix/suffix name pools, categories
- Create new custom affixes
- Compatibility rule editor (forbidden combos, ranged-only, etc.)
- Preview: "What would this affix do to a Demon?" — show stat diff

### 4.5 Feature: Roster Editor

- Visual grid showing all 5 floor tiers
- Each tier shows regular, boss, and support pools
- Drag-and-drop enemy types between pools
- Weight sliders per enemy per pool
- Validation: weights sum displayed, warnings for missing enemy types
- Preview: "Generate 50 rooms at floor 5" — show enemy distribution chart

### 4.6 Feature: TTK Simulator

This is the killer feature for balancing:

- **Party configuration** — pick 1–5 heroes with classes and approximate gear
- **Enemy configuration** — pick an enemy type + rarity tier + champion type/affixes
- **Simulate N encounters** — run the combat math (damage/armor/healing/buffs) for N turns
- **Output:**
  - Average TTK (turns to kill) for the enemy
  - Average hero HP remaining
  - Average healing consumed
  - DPS breakdown by hero
  - "Danger score" — how close heroes came to dying
- **Batch mode:** Simulate all enemies at all rarity tiers → export a balance spreadsheet
- **Compare mode:** Side-by-side before/after when adjusting a stat

### 4.7 Feature: Spawn Preview

- Select a floor number
- Click "Generate 100 spawns"
- See distribution: 82 Normal, 10 Champion (3 Berserker, 2 Fanatic, ...), 5 Rare, 0 Super Unique
- Pie chart + breakdown table
- Adjust spawn chances and see results in real-time

### 4.8 Feature: Super Unique Editor

- Create/edit super unique entries
- Set fixed stats, affixes, retinue, loot table
- Flavor text editor with preview
- Test spawn: "What does this encounter look like?" — show the super unique + retinue stats

### 4.9 Feature: Export Panel

- **Save Enemy Config** → writes to `server/configs/enemies_config.json`
- **Save Rarity Config** → writes to `server/configs/monster_rarity_config.json`
- **Save Super Uniques** → writes to `server/configs/super_uniques_config.json`
- **Update Floor Rosters** → writes to `server/app/core/wfc/dungeon_generator.py` (the `_FLOOR_ENEMY_ROSTER` constant)
- **Diff preview** — show what changed before saving
- **Backup** — auto-backup .bak files before overwriting

### 4.10 Launch Script

```
start-enemy-forge.bat
```

Following the pattern of existing tools.

### 4.11 Implementation Checklist

| # | Task | File(s) | Status |
|---|---|---|---|
| H1 | Scaffold `tools/enemy-forge/` with Vite + React + Express (copy from item-forge pattern) | `tools/enemy-forge/` | ✅ |
| H2 | Implement `server.js` — config read/write endpoints for enemies, rarity, super uniques, rosters | `server.js` | ✅ |
| H3 | Implement Enemy Browser component (list, filter, search) | `EnemyBrowser.jsx` | ✅ |
| H4 | Implement Enemy Editor component (stat sliders, role, AI, tags, skills preview, canvas preview) | `EnemyEditor.jsx` | ✅ |
| H5 | Implement Affix Editor component (browse, edit, create, compatibility rules) | `AffixEditor.jsx` | ✅ |
| H6 | Implement Roster Editor component (floor tier view, weight bars, read-only) | `RosterEditor.jsx` | ✅ |
| H7 | Implement TTK Simulator (party config, enemy config, N-encounter simulation, stat output) | `Simulator.jsx` | ✅ |
| H8 | Implement Spawn Preview (floor selection, N-roll distribution, charts) | `SpawnPreview.jsx` | ✅ |
| H9 | Implement Super Unique Editor (stats, affixes, retinue, loot, flavor text) | `SuperUniqueEditor.jsx` | ✅ |
| H10 | Implement Export Panel (save to configs, diff preview, backup) | `ExportPanel.jsx` | ✅ |
| H11 | Create `start-enemy-forge.bat` launch script | root | ✅ |
| H12 | Add tool to README.md tool list | `README.md` | ✅ |
| H13 | Write tool documentation | `docs/Tools/enemy-forge.md` | ✅ |

**Exit Criteria:** Enemy Forge launches, loads all config files, allows editing/creating enemies and affixes, simulates encounters with TTK output, and exports valid config files.

---

## 5. Phase 18I — Enemy Identity Skills

**Goal:** Give skill-less enemies tactical identity. This is the deferred work from the HP Rebalance doc — Demon Enrage, Skeleton Bone Shield, Imp Frenzy Aura, and Dark Priest/Acolyte differentiation.
**Depends on:** 18D (combat integration patterns established), benefits from 18H (forge tool for balance testing)

### 5.1 New Skills

These are new entries in `server/configs/skills_config.json` with corresponding combat logic:

#### Demon — Enrage (Passive/Triggered)

```json
{
  "skill_id": "enrage",
  "name": "Enrage",
  "description": "When HP drops below 30%, permanently gain +50% melee damage.",
  "icon": "🔥",
  "targeting": "passive",
  "range": 0,
  "cooldown_turns": 0,
  "effects": [
    { "type": "passive_enrage", "hp_threshold": 0.30, "damage_multiplier": 1.5 }
  ],
  "allowed_classes": ["demon_enrage"],
  "requires_line_of_sight": false,
  "is_passive": true
}
```

- **AI Integration:** No action needed — triggers automatically in `combat.py` when damage brings HP below threshold
- **Visual:** Red pulsing aura (use Berserker champion visual as template)
- **Combat log:** "Demon flies into a rage! +50% melee damage!"

#### Skeleton — Bone Shield (Self-Buff)

```json
{
  "skill_id": "bone_shield",
  "name": "Bone Shield",
  "description": "Create a barrier of bone fragments that absorbs the next 25 damage.",
  "icon": "🦴",
  "targeting": "self",
  "range": 0,
  "cooldown_turns": 6,
  "effects": [
    { "type": "damage_absorb", "absorb_amount": 25, "duration_turns": 4 }
  ],
  "allowed_classes": ["skeleton"],
  "requires_line_of_sight": false
}
```

- **AI Integration:** `_ranged_dps_skill_logic` — Cast when an enemy enters vision range (prioritize before attacking)
- **Visual:** White/bone-colored shield bubble around skeleton
- **New effect type:** `damage_absorb` — needs implementation in `combat.py` (absorb shield reduces incoming damage, depletes, then breaks)

#### Imp — Frenzy Aura (Pack Passive)

```json
{
  "skill_id": "frenzy_aura",
  "name": "Frenzy Aura",
  "description": "All imps within 2 tiles gain +3 melee damage. Stacks with other imp auras.",
  "icon": "👹",
  "targeting": "passive",
  "range": 2,
  "cooldown_turns": 0,
  "effects": [
    { "type": "passive_aura_ally_buff", "stat": "attack_damage", "value": 3, "radius": 2, "requires_tag": "imp_frenzy" }
  ],
  "allowed_classes": ["imp_frenzy"],
  "requires_line_of_sight": false,
  "is_passive": true
}
```

- **Imp tag:** Add `"imp_frenzy"` as a hidden tag to imps for aura filtering (only buffs other imps)
- **AI Integration:** Passive — no AI needed, resolved in `_resolve_auras()` (same infrastructure as Might Aura from 18D)
- **Stacking:** Each imp provides +3; 4 clustered imps = +9 each (8+9=17 per hit)
- **Visual:** Faint orange connection lines between nearby imps

#### Dark Priest — Dark Pact (Ally Damage Buff)

Replace Shield of Faith with Dark Pact:

```json
{
  "skill_id": "dark_pact",
  "name": "Dark Pact",
  "description": "Infuse an ally with dark power — +25% melee damage for 3 turns.",
  "icon": "🩸",
  "targeting": "ally",
  "range": 4,
  "cooldown_turns": 5,
  "effects": [
    { "type": "buff", "stat": "melee_damage_multiplier", "magnitude": 1.25, "duration_turns": 3 }
  ],
  "allowed_classes": ["dark_priest"],
  "requires_line_of_sight": false
}
```

- **AI Integration:** `_support_skill_logic` — Buff highest-damage ally in range that doesn't already have Dark Pact active
- **Identity shift:** Dark Priest = offensive enabler (Heal + Dark Pact). Kill it before it buffs the Werewolf.

#### Acolyte — Profane Ward (Ally Damage Reduction)

Replace Shield of Faith with Profane Ward:

```json
{
  "skill_id": "profane_ward",
  "name": "Profane Ward",
  "description": "Shield an ally with dark wards — take 30% less damage for 3 turns.",
  "icon": "🛡️",
  "targeting": "ally_or_self",
  "range": 3,
  "cooldown_turns": 6,
  "effects": [
    { "type": "buff", "stat": "damage_reduction_pct", "magnitude": 0.30, "duration_turns": 3 }
  ],
  "allowed_classes": ["acolyte"],
  "requires_line_of_sight": false
}
```

- **AI Integration:** `_support_skill_logic` — Ward lowest-HP ally in range
- **Identity shift:** Acolyte = defensive sustain (Heal + Profane Ward). Less priority than Dark Priest but extends fights.

### 5.2 New Effect Types Required

| Effect Type | Where | Description |
|---|---|---|
| `passive_enrage` | `combat.py` / `turn_resolver.py` | Check HP threshold after damage; if crossed, apply permanent buff |
| `damage_absorb` | `combat.py` | Shield that absorbs N damage before breaking; tracked as a special buff |
| `passive_aura_ally_buff` | `tick_loop.py` → `_resolve_auras()` | Tag-filtered aura (only buffs units with matching tag) |

### 5.3 Skill Assignment Changes

Update `class_skills` in `skills_config.json`:

| Enemy | Old Skills | New Skills |
|---|---|---|
| **Demon** | *(none)* | `enrage` (passive) |
| **Skeleton** | `evasion` | `evasion`, `bone_shield` |
| **Imp** | *(none)* | `frenzy_aura` (passive) |
| **Dark Priest** | `heal`, `shield_of_faith` | `heal`, `dark_pact` |
| **Acolyte** | `heal`, `shield_of_faith` | `heal`, `profane_ward` |

Also requires new class_id mappings:
- Demon gets `class_id: "demon_enrage"` (or just add enrage to demon behavior)
- Imp gets a `class_id: "imp_frenzy"` (or tag-based passive)
- Dark Priest gets `class_id: "dark_priest"` (distinct from `acolyte`)

### 5.4 Implementation Checklist

| # | Task | File(s) | Status |
|---|---|---|---|
| I1 | Add `enrage` skill to `skills_config.json` | `skills_config.json` | ✅ Done |
| I2 | Implement `passive_enrage` effect in `turn_resolver.py` — trigger on HP threshold cross | `turn_resolver.py`, `skills.py` | ✅ Done |
| I3 | Add `bone_shield` skill to `skills_config.json` | `skills_config.json` | ✅ Done |
| I4 | Implement `damage_absorb` effect type — absorb shield mechanic | `skills.py`, `combat.py` | ✅ Done |
| I5 | Add `frenzy_aura` skill to `skills_config.json` | `skills_config.json` | ✅ Done |
| I6 | Implement tag-filtered passive aura in `_resolve_auras()` | `turn_resolver.py` | ✅ Done |
| I7 | Add `dark_pact` skill to `skills_config.json` | `skills_config.json` | ✅ Done |
| I8 | Add `profane_ward` skill to `skills_config.json` | `skills_config.json` | ✅ Done |
| I9 | Update AI support logic to prioritize Dark Pact on highest-damage ally | `ai_skills.py` | ✅ Done |
| I10 | Update `class_skills` assignments for Demon, Skeleton, Imp, Dark Priest, Acolyte | `skills_config.json` | ✅ Done |
| I11 | Update `enemies_config.json` — new `class_id` values where needed | `enemies_config.json` | ✅ Done |
| I12 | Add particle effects for new skills (enrage aura, bone shield, frenzy connection, dark pact) | particle presets | |
| I13 | Write tests: enrage triggers at threshold, bone shield absorbs damage, frenzy aura stacks, dark pact buffs ally, profane ward reduces damage | `test_enemy_skills.py` | ✅ Done (42 tests) |

**Exit Criteria:** All 5 skill-less or duplicate-kit enemies now have unique tactical identities. Each skill functions in combat with appropriate AI usage. Visual effects in place (I12 pending).

---

## File Impact Summary (Phases 18E–18I)

| File | Phase | Changes |
|---|---|---|
| `client/src/canvas/unitRenderer.js` | 18E | Rarity name colors, glow outlines, champion tints, Ghostly alpha, size modifiers |
| `client/src/canvas/overlayRenderer.js` | 18E | On-death explosion visuals |
| `client/src/canvas/minimapRenderer.js` | 18E | Rarity-colored minimap dots |
| `client/src/canvas/particles/ParticleManager.js` | 18E, 18I | Affix ambient particles, death effects, skill particles |
| `client/public/particle-presets/affixes.json` | 18E | New preset file for affix particle effects |
| `client/src/components/EnemyPanel/` | 18E, 18G | Rarity badge, affix icons, super unique flavor text |
| `client/src/components/CombatLog/` | 18E | Colored enemy names in combat log |
| `client/src/context/reducers/combatReducer.js` | 18E, 18F | Parse rarity fields, handle `elite_kill` event |
| `server/app/core/loot.py` | 18F | Rarity-scaled drop chances, bonus items, guaranteed rarity |
| `server/app/core/turn_resolver.py` | 18F | Pass `monster_rarity` to loot roller, broadcast `elite_kill` |
| **NEW** `server/configs/super_uniques_config.json` | 18G | 4 initial super unique definitions |
| `server/app/core/monster_rarity.py` | 18G | Super unique config loader, spawn logic, creation function |
| `server/app/core/wfc/map_exporter.py` | 18G | Super unique boss replacement logic |
| **NEW** `tools/enemy-forge/` | 18H | Full standalone tool (Vite + React + Express) |
| **NEW** `start-enemy-forge.bat` | 18H | Launch script |
| **NEW** `docs/Tools/enemy-forge.md` | 18H | Tool documentation |
| `server/configs/skills_config.json` | 18I | 5 new skills, updated class_skills assignments |
| `server/configs/enemies_config.json` | 18I | Updated class_id for Demon, Imp, Dark Priest |
| `server/app/core/combat.py` | 18I | `passive_enrage`, `damage_absorb` effect implementations |
| `server/app/services/tick_loop.py` | 18I | Tag-filtered passive aura (Imp Frenzy) |
| `server/app/core/ai_skills.py` | 18I | Dark Pact targeting logic |
| **NEW** `server/tests/test_enemy_skills.py` | 18I | Tests for all 5 new enemy skills |
| `README.md` | 18H | Add Enemy Forge to tool list |

---

## Full Phase Summary (18A–18I)

| Phase | Name | Doc | Key Deliverables |
|---|---|---|---|
| **18A** | Monster Rarity Data Model | [Core](phase18-monster-rarity-core.md) | Config schema, PlayerState fields, EnemyDefinition extensions |
| **18B** | Affix Engine | [Core](phase18-monster-rarity-core.md) | Roller, stat application, name generation, minion creation |
| **18C** | Spawn Integration | [Core](phase18-monster-rarity-core.md) | Dungeon gen + wave spawner wired to affix engine |
| **18D** | Combat Integration | [Core](phase18-monster-rarity-core.md) | Auras, on-hit effects, on-death explosions, ghostly, teleporter |
| **18E** | Client Visual Feedback | [Content](phase18-monster-rarity-content.md) | Name colors, glows, particles, enemy panel, minimap, combat log |
| **18F** | Loot Integration | [Content](phase18-monster-rarity-content.md) | Tier-scaled drops, bonus items, guaranteed rarity, kill notifications |
| **18G** | Super Uniques | [Content](phase18-monster-rarity-content.md) | 4 hand-crafted bosses with fixed affixes, retinue, loot tables |
| **18H** | Enemy Forge Tool | [Content](phase18-monster-rarity-content.md) | Standalone balance/create/test tool with TTK simulator |
| **18I** | Enemy Identity Skills | [Content](phase18-monster-rarity-content.md) | 5 new skills for Demon, Skeleton, Imp, Dark Priest, Acolyte |
