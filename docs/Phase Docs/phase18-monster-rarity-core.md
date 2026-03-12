# Phase 18 — Monster Rarity & Affix System (Core Engine)

**Created:** March 3, 2026
**Status:** Phase 18D Complete (18A–18D all complete)
**Previous:** Phase 17 (Mage Class)
**Goal:** Transform the enemy system from flat stat blocks into a Diablo 2-inspired tiered monster system with affixes, champion packs, rare leaders with minions, and super uniques.

> **Companion Document:** [phase18-monster-rarity-content.md](phase18-monster-rarity-content.md) — Phases 18E–18I (client visuals, loot integration, super uniques, Enemy Forge tool, enemy identity skills)

---

## Table of Contents

1. [Current System Audit](#1-current-system-audit)
2. [Design Overview](#2-design-overview)
3. [Phase 18A — Monster Rarity Data Model](#3-phase-18a--monster-rarity-data-model)
4. [Phase 18B — Affix Engine](#4-phase-18b--affix-engine)
5. [Phase 18C — Spawn Integration](#5-phase-18c--spawn-integration)
6. [Phase 18D — Combat Integration](#6-phase-18d--combat-integration)

---

## 1. Current System Audit

### 1.1 Enemy Roster (24 types)

| Category | Enemies | Skill Count | Notes |
|---|---|---|---|
| **Swarm/Fodder** | Imp, Insectoid, Evil Snail, Goblin Spearman | 0 each | Pure stat sticks, no tactical identity |
| **Standard Melee** | Ghoul (Double Strike), Shade (Shadow Step) | 1 each | Minimal identity via single skill |
| **Standard Ranged** | Skeleton (Evasion), Caster, Undead Caster (Wither) | 0–1 each | Skeleton got Evasion, Caster has nothing |
| **Priority/Support** | Dark Priest (Heal+Shield), Acolyte (Heal+Shield), Medusa (Venom Gaze+Power Shot) | 2 each | Dark Priest & Acolyte identical kits |
| **Bruiser** | Demon (0 skills), Werewolf (War Cry+Double Strike), Wraith (Wither+Shadow Step) | 0–2 | Demon is a high-stat zero-skill block |
| **Elite** | Demon Knight (War Cry), Imp Lord (War Cry), Horror (Shadow Step+Wither), Construct (Ward) | 1–2 | Some skill overlap |
| **Boss** | Undead Knight (Shield Bash+Bulwark), Reaper (Wither+Soul Reap), Necromancer (Wither+Soul Reap), Demon Lord (War Cry+Double Strike), Construct Guardian (Ward+Bulwark) | 2 each | Reaper/Necromancer share identical kits |
| **Special** | Training Dummy | 0 | Invulnerable test target |

### 1.2 What We Have (hooks to build on)

- **Weighted enemy rosters** per floor tier (5 tiers in `dungeon_generator.py`)
- **Support swap mechanic** (30% chance in rooms with 2+ enemies)
- **Creature tags** (undead, demon, beast, construct, aberration, humanoid) — used by holy damage skills
- **`is_boss` flag** — visual distinction + guaranteed loot
- **`class_id` + `class_skills`** mapping — enemies use player skill framework
- **Per-enemy loot tables** with drop_chance, pools, guaranteed rarity
- **Floor-scaled rarity** bonuses for loot (common → magic → rare → epic → unique)
- **Buff/debuff system** with stat modifiers, duration, ticking effects
- **5 AI behavior types** (aggressive, ranged, boss, support, dummy)
- **5 AI role handlers** (support, tank, ranged_dps, hybrid_dps, scout)
- **Sprite variant system** (`sprite_variant` field, per-enemy max variants)

### 1.3 The Gap

Every skeleton is the same skeleton. No variation within a type. The `is_boss` flag is a binary toggle — there's nothing between "normal" and "boss." D2's magic is that you never know what modifiers a monster pack will have. A "Lightning Enchanted Extra Strong" skeleton is a completely different fight than a normal one. We need:

1. **Monster rarity tiers** — Normal / Champion / Rare / Super Unique
2. **An affix system** — Modifiers that alter stats, add on-hit effects, on-death effects, auras
3. **Pack spawning** — Rare monsters spawn with minions
4. **Visual/name differentiation** — Players must see at a glance what they're fighting
5. **Loot scaling** — Better monsters = better drops

---

## 2. Design Overview

### 2.1 Monster Rarity Tiers

| Tier | D2 Equivalent | Name Color | Stat Scaling | Affixes | Minions | Loot Bonus |
|---|---|---|---|---|---|---|
| **Normal** | Normal | White | Base stats | None | No | Base drop table |
| **Champion** | Champion | Blue | +40% HP, +20% damage, +3 armor | 1 inherent "champion type" | No (spawns in groups of 2–3 champions) | +50% drop chance, +1 guaranteed item |
| **Rare** | Rare/Unique | Gold | +70% HP, +30% damage, +5 armor | 2–3 random affixes | 2–3 normal minions of same base type | +100% drop chance, guaranteed magic+, bonus item roll |
| **Super Unique** | Super Unique | Purple | Hand-tuned per enemy | Fixed affixes (2–4) | Optional fixed retinue | Unique loot table, chance at unique items |

### 2.2 Champion Types (Inherent — one per champion)

Champions don't get random affixes. Instead they get ONE inherent type that defines their identity:

| Champion Type | Effect | Visual Cue |
|---|---|---|
| **Berserker** | +30% damage, +20% move priority. Enrages below 30% HP for +50% damage | Red tint / pulsing glow |
| **Fanatic** | +25% attack speed (reduced skill cooldowns by 1 turn, min 1) | Yellow tint / speed lines |
| **Ghostly** | 25% dodge chance, can move through occupied tiles | Semi-transparent / fade effect |
| **Resilient** | +50% HP (stacks with champion base), +5 armor | Stone/grey tint / thick outline |
| **Possessed** | On death: explodes for 15 damage in 1-tile radius | Dark purple glow / shadow wisps |

### 2.3 Affix Pool (for Rare enemies — 2–3 random picks, no duplicates)

Affixes are the heart of the system. Each maps to existing combat mechanics:

| Affix | Category | Effect | Maps To |
|---|---|---|---|
| **Extra Strong** | Offensive | +50% melee damage | `attack_damage` multiplier |
| **Extra Fast** | Offensive | All skill cooldowns reduced by 2 turns (min 1) | Cooldown modification |
| **Might Aura** | Offensive | Allies within 2 tiles deal +25% damage | Buff system (aura) |
| **Cursed** | Offensive | On hit: extend victim's cooldowns by 1 turn | Debuff on-hit effect |
| **Stone Skin** | Defensive | +50% base armor | `armor` multiplier |
| **Spectral Hit** | Defensive | 20% life steal on all attacks | `life_on_hit` or % heal on damage |
| **Shielded** | Defensive | Starts with Ward (3 charges, 10 reflect damage) | Existing Ward skill effect |
| **Teleporter** | Mobility | Shadow Step every 3 turns (auto-cast when target far) | Existing Shadow Step |
| **Fire Enchanted** | On-Death | Explodes on death: 20 damage in 2-tile radius | AoE damage event in `_resolve_deaths` |
| **Cold Enchanted** | On-Hit | Attacks slow target for 1 turn (30% chance) | Existing slow debuff |
| **Thorns** | Retaliation | Attackers take 8 damage per melee hit | Existing `thorns` stat |
| **Mana Burn** | Disruption | On hit: +2 turns to victim's highest active cooldown | Cooldown manipulation |
| **Conviction Aura** | Debuff | Enemies within 2 tiles lose 3 armor | Debuff aura |
| **Multishot** | Ranged | Ranged attacks hit 1 additional random target within 2 tiles | Extra damage event |
| **Regenerating** | Sustain | Recovers 3% max HP per turn | `hp_regen` stat |

**Affix Compatibility Rules:**
- Max 3 affixes per Rare enemy
- No duplicate affixes
- Max 1 aura affix (Might OR Conviction — not both)
- Max 1 on-death affix
- Mobility affixes (Teleporter) excluded from enemies that already have Shadow Step

### 2.4 Naming Convention

| Tier | Name Format | Example |
|---|---|---|
| Normal | `{base_name}` | "Skeleton" |
| Champion | `Champion {base_name}` | "Champion Skeleton" (blue) |
| Rare | `{prefix} {base_name} the {suffix}` | "Blazing Skeleton the Unyielding" (gold) |
| Super Unique | `{fixed_name}` | "Griswold the Blacksmith" (purple) |

**Rare Name Pools** (generated from affixes):

| Affix | Possible Prefixes | Possible Suffixes |
|---|---|---|
| Extra Strong | Mighty, Brutal, Savage | of Ruin, the Crusher, the Destroyer |
| Stone Skin | Iron, Adamant, Hardened | the Unbreaking, the Immovable |
| Fire Enchanted | Blazing, Infernal, Scorching | of Cinders, the Pyreborn |
| Cold Enchanted | Frozen, Glacial, Bitter | of Frost, the Chilling |
| Teleporter | Flickering, Phasing, Shifting | the Elusive, the Unbound |
| Cursed | Hexed, Accursed, Profane | of Misery, the Blighted |
| Thorns | Barbed, Spiked, Jagged | of Thorns, the Spined |
| Might Aura | Commanding, Warlord, Rallying | the Commander, the Warbringer |
| Spectral Hit | Draining, Leeching, Vampiric | the Hungering, the Blooddrinker |
| Regenerating | Regenerating, Festering, Undying | the Unkillable, the Deathless |

---

## 3. Phase 18A — Monster Rarity Data Model

**Goal:** Define the data structures, config files, and model extensions.
**Scope:** Config schemas only — no behavior changes.

### 3.1 New Config: `server/configs/monster_rarity_config.json`

```json
{
  "rarity_tiers": {
    "normal": {
      "tier_id": "normal",
      "name": "Normal",
      "name_color": "#ffffff",
      "hp_multiplier": 1.0,
      "damage_multiplier": 1.0,
      "armor_bonus": 0,
      "affix_count": 0,
      "minion_count": 0,
      "loot_drop_chance_bonus": 0.0,
      "loot_bonus_items": 0,
      "loot_guaranteed_rarity": null,
      "xp_multiplier": 1.0
    },
    "champion": {
      "tier_id": "champion",
      "name": "Champion",
      "name_color": "#6688ff",
      "hp_multiplier": 1.4,
      "damage_multiplier": 1.2,
      "armor_bonus": 3,
      "affix_count": 0,
      "champion_type_count": 1,
      "pack_size": [2, 3],
      "loot_drop_chance_bonus": 0.5,
      "loot_bonus_items": 1,
      "loot_guaranteed_rarity": null,
      "xp_multiplier": 1.5
    },
    "rare": {
      "tier_id": "rare",
      "name": "Rare",
      "name_color": "#ffcc00",
      "hp_multiplier": 1.7,
      "damage_multiplier": 1.3,
      "armor_bonus": 5,
      "affix_count": [2, 3],
      "minion_count": [2, 3],
      "loot_drop_chance_bonus": 1.0,
      "loot_bonus_items": 2,
      "loot_guaranteed_rarity": "magic",
      "xp_multiplier": 2.0
    },
    "super_unique": {
      "tier_id": "super_unique",
      "name": "Super Unique",
      "name_color": "#cc66ff",
      "hp_multiplier": null,
      "damage_multiplier": null,
      "armor_bonus": null,
      "affix_count": null,
      "loot_drop_chance_bonus": 2.0,
      "loot_bonus_items": 3,
      "loot_guaranteed_rarity": "rare",
      "xp_multiplier": 3.0
    }
  },

  "champion_types": {
    "berserker": {
      "type_id": "berserker",
      "name": "Berserker",
      "damage_bonus": 0.30,
      "enrage_threshold": 0.30,
      "enrage_damage_bonus": 0.50,
      "visual_tint": "#ff4444"
    },
    "fanatic": {
      "type_id": "fanatic",
      "name": "Fanatic",
      "cooldown_reduction": 1,
      "visual_tint": "#ffcc44"
    },
    "ghostly": {
      "type_id": "ghostly",
      "name": "Ghostly",
      "dodge_chance": 0.25,
      "phase_through_units": true,
      "visual_tint": "#aaccff"
    },
    "resilient": {
      "type_id": "resilient",
      "name": "Resilient",
      "hp_multiplier": 1.5,
      "armor_bonus": 5,
      "visual_tint": "#888899"
    },
    "possessed": {
      "type_id": "possessed",
      "name": "Possessed",
      "death_explosion_damage": 15,
      "death_explosion_radius": 1,
      "visual_tint": "#9944cc"
    }
  },

  "affixes": {
    "extra_strong": {
      "affix_id": "extra_strong",
      "name": "Extra Strong",
      "category": "offensive",
      "effects": [
        { "type": "stat_multiplier", "stat": "attack_damage", "value": 1.5 }
      ],
      "prefixes": ["Mighty", "Brutal", "Savage", "Hulking"],
      "suffixes": ["of Ruin", "the Crusher", "the Destroyer"]
    },
    "extra_fast": {
      "affix_id": "extra_fast",
      "name": "Extra Fast",
      "category": "offensive",
      "effects": [
        { "type": "cooldown_reduction_flat", "value": 2 }
      ],
      "prefixes": ["Swift", "Frenzied", "Relentless"],
      "suffixes": ["the Quick", "of Haste", "the Blurred"]
    },
    "might_aura": {
      "affix_id": "might_aura",
      "name": "Might Aura",
      "category": "offensive",
      "is_aura": true,
      "effects": [
        { "type": "aura_ally_buff", "stat": "attack_damage", "multiplier": 1.25, "radius": 2 }
      ],
      "prefixes": ["Commanding", "Warlord", "Rallying"],
      "suffixes": ["the Commander", "the Warbringer"]
    },
    "cursed": {
      "affix_id": "cursed",
      "name": "Cursed",
      "category": "offensive",
      "effects": [
        { "type": "on_hit_extend_cooldowns", "turns": 1 }
      ],
      "prefixes": ["Hexed", "Accursed", "Profane"],
      "suffixes": ["of Misery", "the Blighted", "the Cursed"]
    },
    "stone_skin": {
      "affix_id": "stone_skin",
      "name": "Stone Skin",
      "category": "defensive",
      "effects": [
        { "type": "stat_multiplier", "stat": "armor", "value": 1.5 }
      ],
      "prefixes": ["Iron", "Adamant", "Hardened", "Stonebound"],
      "suffixes": ["the Unbreaking", "the Immovable"]
    },
    "spectral_hit": {
      "affix_id": "spectral_hit",
      "name": "Spectral Hit",
      "category": "defensive",
      "effects": [
        { "type": "life_steal_pct", "value": 0.20 }
      ],
      "prefixes": ["Draining", "Leeching", "Vampiric"],
      "suffixes": ["the Hungering", "the Blooddrinker"]
    },
    "shielded": {
      "affix_id": "shielded",
      "name": "Shielded",
      "category": "defensive",
      "effects": [
        { "type": "grant_ward", "charges": 3, "reflect_damage": 10 }
      ],
      "prefixes": ["Warded", "Fortified", "Aegis"],
      "suffixes": ["the Protected", "the Shielded"]
    },
    "teleporter": {
      "affix_id": "teleporter",
      "name": "Teleporter",
      "category": "mobility",
      "effects": [
        { "type": "auto_shadow_step", "cooldown": 3 }
      ],
      "excludes_class_skills": ["shadow_step"],
      "prefixes": ["Flickering", "Phasing", "Shifting"],
      "suffixes": ["the Elusive", "the Unbound"]
    },
    "fire_enchanted": {
      "affix_id": "fire_enchanted",
      "name": "Fire Enchanted",
      "category": "on_death",
      "effects": [
        { "type": "on_death_explosion", "damage": 20, "radius": 2 }
      ],
      "prefixes": ["Blazing", "Infernal", "Scorching", "Embered"],
      "suffixes": ["of Cinders", "the Pyreborn"]
    },
    "cold_enchanted": {
      "affix_id": "cold_enchanted",
      "name": "Cold Enchanted",
      "category": "on_hit",
      "effects": [
        { "type": "on_hit_slow", "chance": 0.30, "duration": 1 }
      ],
      "prefixes": ["Frozen", "Glacial", "Bitter", "Rimefrost"],
      "suffixes": ["of Frost", "the Chilling"]
    },
    "thorns": {
      "affix_id": "thorns",
      "name": "Thorns",
      "category": "retaliation",
      "effects": [
        { "type": "set_stat", "stat": "thorns", "value": 8 }
      ],
      "prefixes": ["Barbed", "Spiked", "Jagged"],
      "suffixes": ["of Thorns", "the Spined"]
    },
    "mana_burn": {
      "affix_id": "mana_burn",
      "name": "Mana Burn",
      "category": "disruption",
      "effects": [
        { "type": "on_hit_extend_cooldowns", "turns": 2, "target": "highest_active" }
      ],
      "prefixes": ["Nullifying", "Draining", "Silencing"],
      "suffixes": ["the Voidspark", "of Negation"]
    },
    "conviction_aura": {
      "affix_id": "conviction_aura",
      "name": "Conviction Aura",
      "category": "debuff",
      "is_aura": true,
      "effects": [
        { "type": "aura_enemy_debuff", "stat": "armor", "value": -3, "radius": 2 }
      ],
      "prefixes": ["Dreaded", "Withering", "Corroding"],
      "suffixes": ["of Dread", "the Unmaker"]
    },
    "multishot": {
      "affix_id": "multishot",
      "name": "Multishot",
      "category": "offensive",
      "effects": [
        { "type": "extra_ranged_target", "count": 1, "splash_radius": 2 }
      ],
      "applies_to": "ranged_only",
      "prefixes": ["Splitting", "Forking", "Twin-bolt"],
      "suffixes": ["of Barrage", "the Volley"]
    },
    "regenerating": {
      "affix_id": "regenerating",
      "name": "Regenerating",
      "category": "sustain",
      "effects": [
        { "type": "hp_regen_pct", "value": 0.03 }
      ],
      "prefixes": ["Regenerating", "Festering", "Undying"],
      "suffixes": ["the Unkillable", "the Deathless"]
    }
  },

  "affix_rules": {
    "max_affixes": 3,
    "max_auras": 1,
    "max_on_death": 1,
    "forbidden_combinations": [
      ["might_aura", "conviction_aura"]
    ],
    "ranged_only_affixes": ["multishot"],
    "melee_only_affixes": []
  },

  "spawn_chances": {
    "_comment": "Chance per eligible spawn point to upgrade from Normal. Floor bonuses stack additively.",
    "champion_base_chance": 0.08,
    "rare_base_chance": 0.03,
    "floor_bonus_per_level": 0.01,
    "boss_tiles_never_upgrade": true,
    "max_enhanced_per_room": 2,
    "min_floor_for_champions": 1,
    "min_floor_for_rares": 3
  }
}
```

### 3.2 Model Extensions — `PlayerState`

Add new fields to `PlayerState` in `server/app/models/player.py`:

```python
# Phase 18A: Monster rarity system
monster_rarity: str | None = None          # "normal", "champion", "rare", "super_unique"
champion_type: str | None = None           # "berserker", "fanatic", "ghostly", "resilient", "possessed"
affixes: list[str] = Field(default_factory=list)  # ["extra_strong", "fire_enchanted", ...]
display_name: str | None = None            # Generated name: "Blazing Skeleton the Pyreborn"
minion_owner_id: str | None = None         # For rare minions: ID of the rare that spawned them
is_minion: bool = False                    # True if spawned as a rare's minion pack
```

### 3.3 Model Extensions — `EnemyDefinition`

Add optional field to `EnemyDefinition` in `server/app/models/player.py`:

```python
# Phase 18A: Affix exclusions (affixes that don't make sense on this enemy)
excluded_affixes: list[str] = Field(default_factory=list)
# Phase 18A: Whether this enemy can be upgraded to champion/rare
allow_rarity_upgrade: bool = True  # False for training_dummy, bosses handled separately
```

### 3.4 Implementation Checklist

| # | Task | File(s) | Status |
|---|---|---|---|
| A1 | Create `monster_rarity_config.json` with tiers, champion types, affixes, rules, spawn chances | `server/configs/monster_rarity_config.json` | |
| A2 | Add `monster_rarity`, `champion_type`, `affixes`, `display_name`, `minion_owner_id`, `is_minion` to `PlayerState` | `server/app/models/player.py` | |
| A3 | Add `excluded_affixes`, `allow_rarity_upgrade` to `EnemyDefinition` | `server/app/models/player.py` | |
| A4 | Update `enemies_config.json` — set `allow_rarity_upgrade: false` for `training_dummy`, add `excluded_affixes` where needed (e.g. Construct excludes `shielded` since it already has Ward) | `server/configs/enemies_config.json` | |
| A5 | Create config loader: `load_monster_rarity_config()` with caching, add to startup validation | `server/app/models/player.py` or new `server/app/core/monster_rarity.py` | |
| A6 | Add startup validation: all affix IDs exist, all champion type IDs exist, forbidden combos reference real affixes | `server/app/core/monster_rarity.py` | |
| A7 | Write tests: config loads, validation catches bad IDs, model fields serialize correctly | `server/tests/test_monster_rarity.py` | |

**Exit Criteria:** Config loads and validates at server startup. Model fields exist on `PlayerState`/`EnemyDefinition`. Zero behavior changes. All existing tests pass.

---

## 4. Phase 18B — Affix Engine

**Goal:** Build the server-side engine that rolls monster rarity, selects affixes, generates names, and applies stat modifiers.
**Depends on:** 18A (data model + config)

### 4.1 New Module: `server/app/core/monster_rarity.py`

Core functions:

```python
def load_monster_rarity_config() -> dict:
    """Load and cache monster_rarity_config.json."""

def roll_monster_rarity(floor_number: int, rng: random.Random) -> str:
    """Roll whether a spawn becomes normal/champion/rare.
    
    Uses spawn_chances from config + floor bonus.
    Returns: "normal", "champion", or "rare"
    """

def roll_champion_type(rng: random.Random) -> str:
    """Pick a random champion type from the pool.
    
    Returns: e.g. "berserker", "fanatic", etc.
    """

def roll_affixes(
    enemy_def: EnemyDefinition,
    count: int,
    rng: random.Random,
) -> list[str]:
    """Roll N random affixes respecting compatibility rules.
    
    - No duplicates
    - Max 1 aura
    - Max 1 on-death
    - Respects enemy excluded_affixes
    - Respects ranged_only / melee_only restrictions
    - Checks forbidden_combinations
    Returns: list of affix_id strings
    """

def generate_rare_name(base_name: str, affixes: list[str], rng: random.Random) -> str:
    """Generate a D2-style rare name from affix prefix/suffix pools.
    
    Format: '{prefix} {base_name} the {suffix}'
    Prefix drawn from first affix, suffix drawn from second affix.
    """

def apply_rarity_to_player(
    player: PlayerState,
    rarity: str,
    champion_type: str | None,
    affixes: list[str],
    display_name: str | None,
) -> None:
    """Apply rarity tier stat scaling + champion type bonuses + affix stat modifiers.
    
    This mutates the PlayerState in-place:
    - Multiplies HP by tier hp_multiplier (and champion type bonus if applicable)
    - Multiplies damage by tier damage_multiplier
    - Adds tier armor_bonus
    - Applies champion type effects (dodge, cooldown reduction, etc.)
    - Applies affix stat effects (extra_strong multiplier, stone_skin, thorns, etc.)
    - Sets monster_rarity, champion_type, affixes, display_name fields
    """

def create_minions(
    rare_player: PlayerState,
    enemy_def: EnemyDefinition,
    count: int,
    room_id: str | None,
    rng: random.Random,
) -> list[PlayerState]:
    """Create Normal-tier minions for a Rare leader.
    
    Minions are the same base enemy type, Normal rarity, with minion_owner_id
    set to the rare's player_id. Returns list of PlayerState to be added to match.
    """
```

### 4.2 Affix Application Order

When `apply_rarity_to_player` is called, modifiers stack in this order:

1. **Base stats** from `enemies_config.json` (already applied via `apply_enemy_stats`)
2. **Tier multipliers** — HP × `hp_multiplier`, damage × `damage_multiplier`, armor + `armor_bonus`
3. **Champion type** — Additional multipliers/bonuses (Resilient: HP × 1.5 again, Ghostly: set dodge, etc.)
4. **Affix stat modifiers** — Applied sequentially: `stat_multiplier`, `set_stat`, `life_steal_pct`, `hp_regen_pct`, `grant_ward`
5. **Recalculate max_hp** — Set `hp = max_hp` after all HP modifications

### 4.3 Name Generation Details

```
Rare with [extra_strong, fire_enchanted, stone_skin]:
  Prefix pool: ["Mighty", "Brutal", "Savage"] (from extra_strong)
  Suffix pool: ["of Cinders", "the Pyreborn"] (from fire_enchanted)
  → "Brutal Skeleton the Pyreborn"

Champion:
  → "Champion Skeleton" (always this format, colored blue)

Super Unique:
  → Fixed name from super_unique config (Phase 18G)
```

### 4.4 Implementation Checklist

| # | Task | File(s) | Status |
|---|---|---|---|
| B1 | Extend `server/app/core/monster_rarity.py` — added Phase 18B engine functions | `monster_rarity.py` | Done |
| B2 | Implement `roll_monster_rarity()` with floor scaling + min floor requirements | `monster_rarity.py` | Done |
| B3 | Implement `roll_champion_type()` — random selection from pool | `monster_rarity.py` | Done |
| B4 | Implement `roll_affixes()` with all compatibility rules (aura, on-death, forbidden, excluded, ranged_only, class skills) | `monster_rarity.py` | Done |
| B5 | Implement `generate_rare_name()` — D2-style "{prefix} {base} {suffix}" from affix pools | `monster_rarity.py` | Done |
| B6 | Implement `apply_rarity_to_player()` — tier scaling + champion type + affix stat modifiers + HP recalc | `monster_rarity.py` | Done |
| B7 | Implement `create_minions()` — Normal-tier spawn dicts linked to rare leader | `monster_rarity.py` | Done |
| B8 | Write 71 tests: rarity rolling distribution (8), champion type (3), affix rules (12), name generation (7), stat application (21), minion creation (10), end-to-end flows (4), plus 6 existing 18A tests updated | `test_monster_rarity.py` | Done |

**Exit Criteria:** All rarity/affix functions work in isolation. Stat math is verified by tests. No integration with spawn or combat yet. **MET — 150 tests passing (79 Phase 18A + 71 Phase 18B), 2249 total suite.**

---

## 5. Phase 18C — Spawn Integration

**Goal:** Wire the affix engine into dungeon generation and wave spawning so enhanced enemies actually appear in-game.
**Depends on:** 18B (affix engine)

### 5.1 Dungeon Generator Integration

In `dungeon_generator.py` / `map_exporter.py`:

After `resolve_enemy_for_tile()` picks a base enemy type, call the rarity roller:

```python
# In map_exporter.py — export_to_game_map() where enemy spawns are built
base_enemy_id = resolve_enemy_for_tile(tile, roster, rng_func, is_support_swap)

# NEW: Roll for monster rarity upgrade
rarity = roll_monster_rarity(floor_number, rng)
champion_type = None
affixes = []
display_name = None

enemy_def = get_enemy_definition(base_enemy_id)
if enemy_def and enemy_def.allow_rarity_upgrade:
    if rarity == "champion":
        champion_type = roll_champion_type(rng)
        display_name = f"Champion {enemy_def.name}"
    elif rarity == "rare":
        affix_count = rng.randint(*rarity_config["rare"]["affix_count"])
        affixes = roll_affixes(enemy_def, affix_count, rng)
        display_name = generate_rare_name(enemy_def.name, affixes, rng)

# Store rarity metadata in spawn data for match_manager to use
enemy_spawn = {
    "enemy_type": base_enemy_id,
    "monster_rarity": rarity,
    "champion_type": champion_type,
    "affixes": affixes,
    "display_name": display_name,
}
```

### 5.2 Match Manager Integration

In `match_manager.py` — `_spawn_dungeon_enemies()`:

After calling `apply_enemy_stats()`, apply the rarity upgrade:

```python
apply_enemy_stats(player, enemy_type, room_id)

# NEW: Apply monster rarity if present in spawn data
spawn_data = ...  # from room enemy_spawns
if spawn_data.get("monster_rarity") and spawn_data["monster_rarity"] != "normal":
    apply_rarity_to_player(
        player,
        rarity=spawn_data["monster_rarity"],
        champion_type=spawn_data.get("champion_type"),
        affixes=spawn_data.get("affixes", []),
        display_name=spawn_data.get("display_name"),
    )
    
    # Spawn minions for Rare enemies
    if spawn_data["monster_rarity"] == "rare":
        minion_count = rng.randint(*rarity_config["rare"]["minion_count"])
        minions = create_minions(player, enemy_def, minion_count, room_id, rng)
        for minion in minions:
            _player_states[match_id][minion.player_id] = minion
```

### 5.3 Wave Spawner Integration

In `wave_spawner.py` — `_spawn_next_wave()`:

Add optional rarity rolling for wave enemies. Later waves get higher chances:

```python
# Wave config can optionally specify forced rarities:
# { "enemy_type": "skeleton", "force_rarity": "champion" }
# Otherwise, roll based on wave number as pseudo-floor
```

### 5.4 Champion Pack Spawning

When a spawn rolls "champion," the system spawns 2–3 champions of the same base type together. This requires:

1. The initial "E" tile enemy rolls champion
2. 1–2 additional champion copies are spawned on adjacent open floor tiles in the same room
3. All share the same champion type (e.g., all "Berserker Champions")
4. Each gets independent sprite variant

### 5.5 Minion Placement

Rare minions need open floor tiles near their leader:

1. Find 2–3 open floor tiles within 2 tiles of the Rare's spawn position
2. If insufficient space, spawn fewer minions (min 1)
3. Minions get `minion_owner_id` = rare's `player_id`
4. Minions are Normal tier (no upgrades)

### 5.6 Implementation Checklist

| # | Task | File(s) | Status |
|---|---|---|---|
| C1 | Update `map_exporter.py` — add rarity rolling to enemy spawn data | `map_exporter.py` | Done |
| C2 | Update `match_manager.py` `_spawn_dungeon_enemies()` — apply rarity + spawn minions | `match_manager.py` | Done |
| C3 | Update `wave_spawner.py` — add rarity support to wave spawns | `wave_spawner.py` | Done |
| C4 | Implement champion pack spawning (2–3 same-type champions on adjacent tiles) | `match_manager.py` | Done |
| C5 | Implement minion placement (find open tiles near rare leader) | `match_manager.py` | Done |
| C6 | Update `room_decorator.py` — ensure rooms have enough floor space for minion packs | `room_decorator.py` | Skipped — rooms already have sufficient floor space |
| C7 | Add `monster_rarity`, `champion_type`, `affixes`, `display_name` to WebSocket broadcast (player state serialization) | `match_manager.py` (`get_players_snapshot`, `advance_floor`) | Done |
| C8 | Write tests: spawns produce enhanced enemies at expected rates, champion packs spawn correctly, rare minions link to leader, floor scaling works | `test_monster_rarity_spawn.py` (28 tests, 6 classes) | Done |

**Exit Criteria:** Enhanced enemies spawn in dungeons and wave arena. Rarity metadata is broadcast to clients. All stats correctly applied. Minion packs appear near rare leaders. **All criteria met — Phase 18C complete.**

---

## 6. Phase 18D — Combat Integration

**Goal:** Make affix effects actually function during combat — auras tick, on-hit effects trigger, on-death explosions fire.
**Depends on:** 18C (enemies spawning with affixes in-game)

### 6.1 Aura System

Auras apply their effect at the start of each turn tick:

- **Might Aura:** Find all allies within radius → apply temporary +25% damage buff (1-turn duration, refreshed each tick)
- **Conviction Aura:** Find all enemies within radius → apply temporary -3 armor debuff (1-turn, refreshed)
- Auras only function while the aura source is alive
- Uses existing buff system (`active_buffs`) with a special `is_aura` flag to prevent stacking display

**Integration point:** `tick_loop.py` → `match_tick()` — add `_resolve_auras()` step before combat resolution

### 6.2 On-Hit Effects

Triggered in `combat.py` whenever an attack lands:

- **Cursed:** After damage applied → extend victim's lowest-remaining cooldown by 1 turn
- **Cold Enchanted:** 30% chance → apply 1-turn slow debuff to victim
- **Mana Burn:** After damage → extend victim's highest active cooldown by 2 turns
- **Spectral Hit:** After damage dealt → heal attacker for 20% of damage dealt

**Integration point:** `combat.py` → after damage calculation, check attacker's `affixes` list and apply effects

### 6.3 On-Death Effects

Triggered in `turn_resolver.py` → `_resolve_deaths()`:

- **Fire Enchanted:** Explosion — deal 20 damage to all units within 2 tiles
- **Possessed (champion type):** Explosion — deal 15 damage within 1 tile
- Both trigger particle effects (handled in 18E)

**Integration point:** `turn_resolver.py` → `_resolve_deaths()` — after marking death, check `affixes`/`champion_type` for on-death effects, append damage events

### 6.4 Passive/Stat Effects (Already Handled in 18B)

These are applied at spawn time and need no combat-time logic:

- **Extra Strong:** Damage already multiplied
- **Extra Fast:** Cooldowns already reduced
- **Stone Skin:** Armor already increased
- **Thorns:** `thorns` stat already set (existing thorns damage code triggers automatically)
- **Regenerating:** `hp_regen` already set (if hp_regen ticks exist; if not, add to tick loop)

### 6.5 Special: Ghostly Champion

- **Phase through units:** Ghostly champions can move through occupied tiles
- **Integration:** `ai_pathfinding.py` → `_neighbors()` — when building the walkable grid, if the moving unit has `champion_type == "ghostly"`, don't exclude occupied tiles from the neighbor set
- Also need to update `_build_occupied_set()` to pass through the unit's champion type

### 6.6 Special: Teleporter Affix

- Enemies with Teleporter affix gain an auto-cast Shadow Step on a 3-turn internal cooldown
- **Integration:** `ai_behavior.py` — in the AI decision loop, check if the unit has the `teleporter` affix and the internal cooldown has elapsed, and if target is more than 3 tiles away, auto-cast Shadow Step toward them
- Uses existing Shadow Step skill infrastructure

### 6.7 Special: HP Regeneration

If `hp_regen` ticking doesn't already exist in the tick loop:

- Add `_resolve_regeneration()` step in `tick_loop.py`
- Each alive unit with `hp_regen > 0` recovers that amount (capped at `max_hp`)
- For Regenerating affix: 3% of `max_hp` per turn

### 6.8 Special: Shielded Affix

- At spawn, grants 3 Ward charges with 10 reflect damage
- Uses existing Ward buff system (`shield_charges` effect type)
- Apply as initial buff in `apply_rarity_to_player()` or on first tick

### 6.9 Minion Behavior on Leader Death

When a Rare leader dies:

- Minions (linked via `minion_owner_id`) become "unlinked" — they lose room leashing and roam freely
- Optional: Minions could scatter/flee for 2 turns before going aggressive (future polish)

**Integration point:** `turn_resolver.py` → `_resolve_deaths()` — when a rare dies, find all minions and clear their `room_id`

### 6.10 Implementation Checklist

| # | Task | File(s) | Status |
|---|---|---|---|
| D1 | Add `_resolve_auras()` to tick loop — Might Aura + Conviction Aura as refreshing 1-turn buffs/debuffs | `turn_resolver.py` | ✅ Done |
| D2 | Add on-hit effect hooks in `combat.py` — Cursed, Cold Enchanted, Mana Burn, Spectral Hit | `combat.py` | ✅ Done |
| D3 | Add on-death effects in `_resolve_deaths()` — Fire Enchanted explosion, Possessed explosion | `turn_resolver.py` | ✅ Done |
| D4 | Implement Ghostly phase-through in `ai_pathfinding.py` | `ai_pathfinding.py`, `ai_behavior.py` | ✅ Done |
| D5 | Implement Teleporter auto-cast in `ai_behavior.py` | `ai_behavior.py` | ✅ Done |
| D6 | Add `_resolve_regeneration()` to tick loop (or verify existing hp_regen logic) | `tick_loop.py` | ✅ Verified (existing hp_regen ticking in _resolve_cooldowns_and_buffs) |
| D7 | Apply Shielded affix as initial Ward buff at spawn | `monster_rarity.py` | ✅ Verified (already handled by _apply_affix_effect in apply_rarity_to_player) |
| D8 | Handle minion unlinking on rare leader death | `turn_resolver.py` | ✅ Done |
| D9 | Add on-death explosion events to turn results for client broadcast | `turn_resolver.py` | ✅ Done |
| D10 | Write tests: aura buff/debuff application, on-hit cooldown extension, on-death AoE damage, ghostly pathfinding, regen ticking, minion unlinking | `test_monster_rarity_combat.py` | ✅ Done (33 tests) |

**Exit Criteria:** All affix effects function in combat. Auras tick, on-hit effects fire, deaths trigger explosions, ghostly can phase through units. Full test coverage for each effect. **✅ ALL MET — 2272 tests passing.**

---

## File Impact Summary

| File | Changes |
|---|---|
| **NEW** `server/configs/monster_rarity_config.json` | Full config (tiers, champions, affixes, rules, spawn chances) |
| **NEW** `server/app/core/monster_rarity.py` | Affix engine (roll, apply, name gen, minion creation) |
| **NEW** `server/tests/test_monster_rarity.py` | Unit tests for 18A–18B |
| **NEW** `server/tests/test_monster_rarity_combat.py` | Combat integration tests for 18D |
| `server/app/models/player.py` | PlayerState + EnemyDefinition new fields |
| `server/configs/enemies_config.json` | `allow_rarity_upgrade`, `excluded_affixes` fields |
| `server/app/core/wfc/map_exporter.py` | Rarity rolling during export |
| `server/app/core/match_manager.py` | Apply rarity at spawn, minion placement |
| `server/app/core/wave_spawner.py` | Rarity support for waves |
| `server/app/services/tick_loop.py` | `_resolve_auras()`, `_resolve_regeneration()` |
| `server/app/core/combat.py` | On-hit affix hooks |
| `server/app/core/turn_resolver.py` | On-death effects, minion unlinking |
| `server/app/core/ai_behavior.py` | Teleporter auto-cast |
| `server/app/core/ai_pathfinding.py` | Ghostly phase-through |

---

## Balance Tuning Targets

These values are starting points — the Enemy Forge tool (Phase 18H) will let us simulate and adjust:

| Parameter | Value | Rationale |
|---|---|---|
| Champion HP multiplier | 1.4× | A 240 HP Demon → 336 HP. Tough but not boss-level. |
| Rare HP multiplier | 1.7× | A 240 HP Demon → 408 HP. Mini-boss feel. |
| Champion damage multiplier | 1.2× | Noticeable but not lethal spike. |
| Rare damage multiplier | 1.3× | Combined with affixes, creates real threat. |
| Champion spawn rate (base) | 8% | ~1 per dungeon floor at early levels. |
| Rare spawn rate (base) | 3% | Uncommon enough to feel special. |
| Floor bonus per level | +1% | Floor 9 = 8+9=17% champion, 3+9=12% rare. |
| Max enhanced per room | 2 | Prevents rooms from being all champions. |
