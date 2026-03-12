# Phase 16 — Diablo-Inspired Item & Equipment Overhaul

**Created:** March 2, 2026  
**Status:** 16A, 16B, 16C Complete — Implementation Phase  
**Previous:** Phase 15 (Complete Dungeon Experience — Rare tier, enemy affixes, co-op)  
**Goal:** Transform the item system from static config lookups into a Diablo-style RNG loot engine with expanded stats, random affixes, unique/set items, and the "GG item hunt" that drives replayability.

---

## The Problem

Phase 15 adds a Rare item tier and depth-scaled drop rates — a meaningful improvement. But the fundamental limitation remains: **every item is a static, hand-authored config entry.** Every "Soulforged Blade" that drops is identical to every other "Soulforged Blade." There's no randomness, no variance, no reason to compare two items of the same type.

The game currently has:
- **4 stats:** `attack_damage`, `ranged_damage`, `armor`, `max_hp`
- **3 equip slots:** weapon, armor, accessory
- **~29 items** (18 original + 10 rare from Phase 15 + 1 consumable)
- **3 rarity tiers** (post-Phase 15): Common, Uncommon, Rare
- **Zero random rolls** — items are deterministic config lookups
- **No class restrictions** — any class equips anything
- **Flat armor only** — no percentage-based defense, no offensive secondary stats

In Diablo terms, this is a game where every item is a white/blue item with fixed stats. The loot loop — the core motivator for dungeon-crawling — has a very low ceiling.

### What Makes Diablo's Loot Compelling

1. **Every drop is unique** — random affixes mean two swords are never the same
2. **Stats interact multiplicatively** — crit chance × crit damage, CDR × skill damage, etc.
3. **Chase items exist** — Uniques and Sets with build-defining effects
4. **Trade-offs are real** — offensive vs. defensive stats, DPS vs. survivability
5. **Magic Find creates gear tension** — wear MF gear to find better gear, or wear combat gear to survive

Phase 16 brings all five pillars to Arena.

---

## Table of Contents

1. [Stat Expansion](#16a--stat-expansion)
2. [Affix System & Item Generation](#16b--affix-system--item-generation)
3. [Rarity Overhaul & Item Tiers](#16c--rarity-overhaul--item-tiers)
4. [Unique Items](#16d--unique-items)
5. [Set Items](#16e--set-items)
6. [Equipment Slot Expansion](#16f--equipment-slot-expansion)
7. [Client UI & Loot Presentation](#16g--client-ui--loot-presentation)
8. [Balance & Tuning Pass](#16h--balance--tuning-pass)

---

## Phase Dependency Map

```
Phase 15 (Rare tier, depth-scaling, enemy affixes)
    │
    ▼
  16A — Stat Expansion (FOUNDATION — everything depends on this)
    │
    ├──► 16B — Affix System (needs new stats to roll)
    │      │
    │      ├──► 16C — Rarity Overhaul (needs affix system for Magic/Rare generation)
    │      │      │
    │      │      ├──► 16D — Unique Items (needs rarity tiers established)
    │      │      └──► 16E — Set Items (needs rarity tiers established)
    │      │
    │      └──► 16G — Client UI (needs affix data to display)
    │
    ├──► 16F — Equipment Slot Expansion (independent, needs stat foundation)
    │
    └──► 16H — Balance & Tuning Pass (final, after everything is in)
```

---

## 16A — Stat Expansion

**Effort:** Medium  
**Risk:** Medium — touches the core damage formula in `combat.py`  
**Prerequisite:** None (this IS the foundation)

### The Problem

The current 4-stat system (`attack_damage`, `ranged_damage`, `armor`, `max_hp`) cannot support interesting item differentiation. Even with random value ranges, "this sword has +11 melee vs. +12 melee" doesn't create excitement. We need stats that interact with combat in multiplicative and build-defining ways.

### New Stats

Organized by implementation complexity:

#### Tier 1 — Drop-In Stats (damage formula changes only)

| Stat | Key | Type | Range | Effect |
|------|-----|------|-------|--------|
| Critical Hit Chance | `crit_chance` | `float` | 0–50% | % chance each attack/skill deals bonus damage |
| Critical Hit Damage | `crit_damage` | `float` | 150–300% | Damage multiplier on critical hits (default: 150%) |
| Dodge Chance | `dodge_chance` | `float` | 0–40% | % chance to completely avoid an incoming attack |
| Damage Reduction % | `damage_reduction_pct` | `float` | 0–50% | Percentage-based armor (applied after flat armor) |
| HP Regeneration | `hp_regen` | `int` | 0–15 | HP restored per turn (ticks in buff phase) |

#### Tier 2 — New Interactions (small combat system hooks)

| Stat | Key | Type | Range | Effect |
|------|-----|------|-------|--------|
| Life on Hit | `life_on_hit` | `int` | 0–10 | HP restored on each successful melee or ranged hit |
| Cooldown Reduction | `cooldown_reduction_pct` | `float` | 0–30% | % reduction to all skill cooldowns (min 1 turn) |
| Skill Damage % | `skill_damage_pct` | `float` | 0–40% | % bonus to all skill damage (not auto-attacks) |
| Thorns | `thorns` | `int` | 0–12 | Flat damage reflected to attacker on every hit taken |
| Gold Find % | `gold_find_pct` | `float` | 0–80% | % bonus gold from enemy kills |
| Magic Find % | `magic_find_pct` | `float` | 0–60% | % bonus chance that drops upgrade to the next rarity tier |

#### Tier 3 — Class/Build-Defining

| Stat | Key | Type | Range | Effect |
|------|-----|------|-------|--------|
| Holy Damage % | `holy_damage_pct` | `float` | 0–40% | % bonus to Exorcism, Rebuke, and tagged-bonus damage |
| DoT Damage % | `dot_damage_pct` | `float` | 0–40% | % bonus to Wither and Venom Gaze tick damage |
| Heal Power % | `heal_power_pct` | `float` | 0–40% | % bonus to all healing done (Heal, Prayer, Holy Ground) |
| Armor Penetration | `armor_pen` | `int` | 0–8 | Ignore X points of target's flat armor |

### Updated Damage Formula

```
Current:
  final = max(1, (base_dmg + weapon_bonus) × buff_mult − target_armor)

Proposed:
  raw_damage   = (base_dmg + weapon_bonus) × buff_mult × (1 + skill_damage_pct if skill else 0)
  armor_after_pen = max(0, target_armor − attacker_armor_pen)
  post_armor   = max(1, raw_damage − armor_after_pen)
  post_pct_dr  = max(1, post_armor × (1 − target_damage_reduction_pct))
  
  # Crit check
  is_crit      = random() < attacker_crit_chance
  crit_mult    = attacker_crit_damage / 100 if is_crit else 1.0
  
  # Dodge check (rolled before crit)
  is_dodged    = random() < target_dodge_chance
  
  final_damage = 0 if is_dodged else max(1, post_pct_dr × crit_mult)
  
  # Life on hit (attacker heals after dealing damage)
  if final_damage > 0 and attacker_life_on_hit > 0:
      attacker.hp = min(attacker.max_hp, attacker.hp + attacker_life_on_hit)
  
  # Thorns (target reflects damage back)
  if final_damage > 0 and target_thorns > 0:
      attacker.hp = max(0, attacker.hp − target_thorns)
```

### Expanded `StatBonuses` Model

```python
class StatBonuses(BaseModel):
    """Stat modifiers granted by an equipped item."""
    # Existing (Phase 4D)
    attack_damage: int = 0
    ranged_damage: int = 0
    armor: int = 0
    max_hp: int = 0
    
    # Phase 16A — Tier 1
    crit_chance: float = 0.0          # 0.0–0.50 (0–50%)
    crit_damage: float = 0.0          # 0.0–1.50 (additive with base 1.5×)
    dodge_chance: float = 0.0         # 0.0–0.40 (0–40%)
    damage_reduction_pct: float = 0.0 # 0.0–0.50 (0–50%)
    hp_regen: int = 0
    move_speed: int = 0
    
    # Phase 16A — Tier 2
    life_on_hit: int = 0
    cooldown_reduction_pct: float = 0.0  # 0.0–0.30 (0–30%)
    skill_damage_pct: float = 0.0        # 0.0–0.40 (0–40%)
    thorns: int = 0
    gold_find_pct: float = 0.0           # 0.0–0.80 (0–80%)
    magic_find_pct: float = 0.0          # 0.0–0.60 (0–60%)
    
    # Phase 16A — Tier 3
    holy_damage_pct: float = 0.0      # 0.0–0.40 (0–40%)
    dot_damage_pct: float = 0.0       # 0.0–0.40 (0–40%)
    heal_power_pct: float = 0.0       # 0.0–0.40 (0–40%)
    armor_pen: int = 0
```

### Expanded `PlayerState` Effective Stats

New fields on `PlayerState` for combat-computed effective stats:

```python
# Phase 16A: Expanded combat stats (computed from base + equipment + buffs)
crit_chance: float = 0.05       # Default 5% base crit chance
crit_damage: float = 1.5        # Default 150% crit multiplier
dodge_chance: float = 0.0
damage_reduction_pct: float = 0.0
hp_regen: int = 0
move_speed: int = 0
life_on_hit: int = 0
cooldown_reduction_pct: float = 0.0
skill_damage_pct: float = 0.0
thorns: int = 0
gold_find_pct: float = 0.0
magic_find_pct: float = 0.0
holy_damage_pct: float = 0.0
dot_damage_pct: float = 0.0
heal_power_pct: float = 0.0
armor_pen: int = 0
```

### Files Changed

| File | Changes |
|------|---------|
| `server/app/models/items.py` | Expand `StatBonuses` with all new stat fields |
| `server/app/models/player.py` | Add effective stat fields to `PlayerState` |
| `server/app/core/combat.py` | New damage formula with crit, dodge, armor pen, % DR, life on hit, thorns |
| `server/app/core/equipment_manager.py` | Aggregate new stats from equipment, apply/remove on equip/unequip |
| `server/app/core/turn_resolver.py` | HP regen tick in buff phase, CDR application to cooldowns |
| `server/app/core/skills.py` | `skill_damage_pct` multiplier on skill damage, `heal_power_pct` on heals |
| `server/app/core/loot.py` | `magic_find_pct` applied during rarity roll upgrade |
| `server/app/core/match_manager.py` | `gold_find_pct` applied to gold reward calculation |
| `server/configs/combat_config.json` | Add `base_crit_chance`, `base_crit_damage`, `crit_damage_cap`, `dodge_cap` |
| `client/src/utils/itemUtils.js` | `formatStatBonuses()` updated for all new stats |
| `client/src/components/Inventory/` | Tooltip display for new stats |
| `client/src/components/HeaderBar/` | Show crit/dodge/regen in hero stat display |

### Tests

- All new stats default to 0/base values — existing items unchanged
- Crit chance 0% → never crits; 100% → always crits (deterministic seed)
- Crit damage multiplier applied correctly on crit hits
- Dodge chance 0% → never dodges; 100% → always dodges (deterministic seed)
- Dodge prevents all damage (0 damage dealt)
- Damage reduction % applied after flat armor (multiplicative stacking)
- HP regen ticks each turn, capped at max_hp
- Life on hit heals attacker, capped at max_hp, only on successful hit
- Thorns reflects damage to attacker, can kill attacker
- Armor penetration reduces effective armor, can't go below 0
- Skill damage % applies to skill damage but NOT auto-attacks
- Heal power % applies to Heal, Prayer ticks, and Holy Ground
- Cooldown reduction reduces all skill cooldowns, minimum 1 turn
- Move speed adds tiles to movement range
- Gold find % increases gold rewards
- Magic find % increases rarity upgrade chance in loot rolls
- Equipment stat aggregation sums all new stats correctly
- Negative overflow prevention (no stat below 0 after unequip)
- Backward compatibility: all existing items/tests unchanged

### 16A Implementation Log

**Status:** ✅ Complete  
**Completed:** Session 1  
**Test results:** 1725 passed (60 new Phase 16A tests + 1665 existing — 0 regressions)

#### Files Modified (Server)

| File | Changes |
|------|---------|
| `server/app/models/items.py` | `StatBonuses` expanded from 4 to 20 fields (16 new stats); `Equipment.total_bonuses()` aggregates all new stats |
| `server/app/models/player.py` | `PlayerState` — 16 new effective stat fields with defaults (`crit_chance=0.05`, `crit_damage=1.5`, rest 0) |
| `server/app/models/actions.py` | `ActionResult.is_crit: bool = False` field added |
| `server/configs/combat_config.json` | 6 new cap values: `base_crit_chance`, `base_crit_damage`, `crit_damage_cap`, `dodge_cap`, `damage_reduction_cap`, `cooldown_reduction_cap` |
| `server/app/core/combat.py` | **Major rewrite** — `calculate_damage()` and `calculate_ranged_damage()` now return `tuple[int, dict]` with 7-step pipeline: Dodge → Raw → Armor Pen → Flat Armor → %DR → Crit → Life on Hit → Thorns. Added `_simple` backward-compat wrappers. |
| `server/app/core/equipment_manager.py` | `_recalculate_effective_stats()` — aggregates 16 new stats from equipment with configurable caps. Called after every equip/unequip. |
| `server/app/core/turn_resolver.py` | HP regen ticking in `_resolve_cooldowns_and_buffs()`; melee/ranged phases unpack `(damage, combat_info)` tuples; stat-based dodge, crit tags, life-on-hit messages, thorns damage/kill tracking |
| `server/app/core/skills.py` | CDR in `_apply_skill_cooldown()`; `skill_damage_pct` in multi_hit/ranged_skill/stun_damage/aoe_damage/ranged_damage_slow; `heal_power_pct` in heal/aoe_heal; `dot_damage_pct` in dot; `holy_damage_pct` in holy_damage |
| `server/app/core/loot.py` | `magic_find_pct` parameter on `roll_enemy_loot()` and `roll_chest_loot()`; `_try_rarity_upgrade()` helper (common → uncommon) |
| `server/app/core/hero_manager.py` | `gold_find_pct` bonus applied to both gold calculation locations (post-match persist + match-end outcomes) |

#### Files Modified (Client)

| File | Changes |
|------|---------|
| `client/src/utils/itemUtils.js` | `formatStatBonuses()` expanded to display all 16 new stats with proper formatting (%, flat) |

#### Files Modified (Tests)

| File | Changes |
|------|---------|
| `server/tests/test_combat.py` | Import alias: `calculate_damage_simple as calculate_damage` for backward compat |
| `server/tests/test_skills_combat.py` | Import aliases for `_simple` wrappers |
| `server/tests/test_loot_combat.py` | Import aliases for `_simple` wrappers |
| `server/tests/test_phase16a_stat_expansion.py` | **New — 60 tests** covering crit, dodge, DR, armor pen, HP regen, life on hit, thorns, CDR, skill damage %, heal power %, DoT/HoT %, holy damage %, move speed, gold find, magic find, equipment aggregation + caps, backward compat wrappers, StatBonuses model, PlayerState defaults, full pipeline integration |

#### Key Design Decisions

1. **Crit chance capped at 50%** — hardcoded `min(0.50, ...)` in the damage formula prevents 100% crit builds
2. **Dodge cap 40%** — configurable in `combat_config.json`, prevents untouchable builds  
3. **Stat-based dodge is separate from Evasion skill buff** — both checked independently in turn_resolver
4. **`_simple` wrappers for backward compat** — all existing callers that expected `int` returns now use `calculate_damage_simple()` / `calculate_ranged_damage_simple()` which skip crit/dodge/thorns
5. **Equipment stat caps applied at equip time** — `_recalculate_effective_stats()` enforces caps when gear changes, not during every damage calc
6. **Life on hit fires BEFORE thorns** — attacker heals first, then takes thorns damage; if thorns kills them, they still dealt the hit

---

## 16B — Affix System & Item Generation

**Effort:** Large  
**Risk:** Medium — this is the biggest architectural change (items go from static → generated)  
**Prerequisite:** 16A (new stats must exist for affixes to roll)

### The Problem

Every item is a static entry in `items_config.json`. There's no randomness in what drops. Two players who both find a "Tempered Greatsword" have identical items. This kills the loot hunt — there's no reason to pick up a second copy of anything.

### The Solution: Prefix/Suffix Affix System

Items gain a **base type** with fixed base stats, then **random affixes** are rolled on top. Each affix adds a random stat bonus within a defined range. The combination of base type + affixes makes every item potentially unique.

### Item Identity: Instance IDs

Every dropped item receives a **unique instance ID** (UUID). Items are no longer identified solely by `item_id` — that becomes the `base_type_id`. The instance has its own generated stats.

```python
class Item(BaseModel):
    instance_id: str              # UUID — unique per drop (NEW)
    base_type_id: str             # References items_config base type (was item_id)
    item_id: str                  # Kept for backward compat — equals base_type_id for non-affix items
    name: str                     # Generated name (e.g., "Cruel Greatsword of the Bear")
    display_name: str             # Base name without affixes (e.g., "Greatsword")
    item_type: ItemType
    rarity: Rarity
    equip_slot: EquipSlot | None
    stat_bonuses: StatBonuses     # Base stats + affix stats combined
    base_stats: StatBonuses       # Base type stats only (for tooltip comparison)
    affixes: list[dict]           # [{affix_id, type: "prefix"|"suffix", stat, value}, ...]
    item_level: int = 1           # Determines affix roll ranges
    description: str = ""
    sell_value: int = 0           # Base value × rarity multiplier
```

### Affix Definitions

New config file: `server/configs/affixes_config.json`

```json
{
  "prefixes": {
    "cruel": {
      "affix_id": "cruel",
      "name": "Cruel",
      "stat": "attack_damage",
      "min_value": 3,
      "max_value": 12,
      "ilvl_scaling": 0.5,
      "weight": 100,
      "allowed_slots": ["weapon"],
      "description": "Increases melee damage"
    },
    "piercing": {
      "affix_id": "piercing",
      "name": "Piercing",
      "stat": "ranged_damage",
      "min_value": 3,
      "max_value": 12,
      "ilvl_scaling": 0.5,
      "weight": 100,
      "allowed_slots": ["weapon"],
      "description": "Increases ranged damage"
    },
    "deadly": {
      "affix_id": "deadly",
      "name": "Deadly",
      "stat": "crit_chance",
      "min_value": 0.02,
      "max_value": 0.10,
      "ilvl_scaling": 0.003,
      "weight": 70,
      "allowed_slots": ["weapon", "accessory"],
      "description": "Increases critical hit chance"
    },
    "savage": {
      "affix_id": "savage",
      "name": "Savage",
      "stat": "crit_damage",
      "min_value": 0.10,
      "max_value": 0.50,
      "ilvl_scaling": 0.02,
      "weight": 60,
      "allowed_slots": ["weapon", "accessory"],
      "description": "Increases critical hit damage"
    },
    "vampiric": {
      "affix_id": "vampiric",
      "name": "Vampiric",
      "stat": "life_on_hit",
      "min_value": 1,
      "max_value": 5,
      "ilvl_scaling": 0.3,
      "weight": 50,
      "allowed_slots": ["weapon"],
      "description": "Heals on hit"
    },
    "thorned": {
      "affix_id": "thorned",
      "name": "Thorned",
      "stat": "thorns",
      "min_value": 2,
      "max_value": 8,
      "ilvl_scaling": 0.4,
      "weight": 40,
      "allowed_slots": ["armor"],
      "description": "Reflects damage to attackers"
    },
    "armored": {
      "affix_id": "armored",
      "name": "Armored",
      "stat": "armor",
      "min_value": 1,
      "max_value": 6,
      "ilvl_scaling": 0.3,
      "weight": 80,
      "allowed_slots": ["weapon", "armor", "accessory"],
      "description": "Increases armor"
    },
    "empowered": {
      "affix_id": "empowered",
      "name": "Empowered",
      "stat": "skill_damage_pct",
      "min_value": 0.05,
      "max_value": 0.20,
      "ilvl_scaling": 0.01,
      "weight": 50,
      "allowed_slots": ["weapon", "accessory"],
      "description": "Increases skill damage"
    },
    "penetrating": {
      "affix_id": "penetrating",
      "name": "Penetrating",
      "stat": "armor_pen",
      "min_value": 1,
      "max_value": 5,
      "ilvl_scaling": 0.2,
      "weight": 40,
      "allowed_slots": ["weapon"],
      "description": "Ignores target armor"
    },
    "venomous": {
      "affix_id": "venomous",
      "name": "Venomous",
      "stat": "dot_damage_pct",
      "min_value": 0.05,
      "max_value": 0.20,
      "ilvl_scaling": 0.01,
      "weight": 35,
      "allowed_slots": ["weapon", "accessory"],
      "description": "Increases damage over time effects"
    },
    "holy": {
      "affix_id": "holy",
      "name": "Holy",
      "stat": "holy_damage_pct",
      "min_value": 0.05,
      "max_value": 0.20,
      "ilvl_scaling": 0.01,
      "weight": 35,
      "allowed_slots": ["weapon", "accessory"],
      "description": "Increases holy damage"
    },
    "sturdy": {
      "affix_id": "sturdy",
      "name": "Sturdy",
      "stat": "max_hp",
      "min_value": 8,
      "max_value": 40,
      "ilvl_scaling": 2.0,
      "weight": 80,
      "allowed_slots": ["armor", "accessory"],
      "description": "Increases maximum HP"
    },
    "precise": {
      "affix_id": "precise",
      "name": "Precise",
      "stat": "ranged_damage",
      "min_value": 2,
      "max_value": 8,
      "ilvl_scaling": 0.4,
      "weight": 70,
      "allowed_slots": ["accessory"],
      "description": "Increases ranged damage"
    },
    "blessed": {
      "affix_id": "blessed",
      "name": "Blessed",
      "stat": "heal_power_pct",
      "min_value": 0.05,
      "max_value": 0.15,
      "ilvl_scaling": 0.008,
      "weight": 40,
      "allowed_slots": ["weapon", "armor"],
      "description": "Increases healing done"
    },
    "resilient": {
      "affix_id": "resilient",
      "name": "Resilient",
      "stat": "damage_reduction_pct",
      "min_value": 0.02,
      "max_value": 0.08,
      "ilvl_scaling": 0.004,
      "weight": 45,
      "allowed_slots": ["armor"],
      "description": "Reduces incoming damage by a percentage"
    },
    "regenerating": {
      "affix_id": "regenerating",
      "name": "Regenerating",
      "stat": "hp_regen",
      "min_value": 1,
      "max_value": 5,
      "ilvl_scaling": 0.3,
      "weight": 45,
      "allowed_slots": ["armor"],
      "description": "Regenerates HP each turn"
    }
  },
  "suffixes": {
    "of_the_bear": {
      "affix_id": "of_the_bear",
      "name": "of the Bear",
      "stat": "max_hp",
      "min_value": 10,
      "max_value": 60,
      "ilvl_scaling": 3.0,
      "weight": 100,
      "allowed_slots": ["weapon", "armor", "accessory"],
      "description": "Increases maximum HP"
    },
    "of_iron": {
      "affix_id": "of_iron",
      "name": "of Iron",
      "stat": "armor",
      "min_value": 2,
      "max_value": 8,
      "ilvl_scaling": 0.4,
      "weight": 90,
      "allowed_slots": ["armor", "accessory"],
      "description": "Increases armor"
    },
    "of_evasion": {
      "affix_id": "of_evasion",
      "name": "of Evasion",
      "stat": "dodge_chance",
      "min_value": 0.02,
      "max_value": 0.10,
      "ilvl_scaling": 0.004,
      "weight": 60,
      "allowed_slots": ["armor", "accessory"],
      "description": "Increases dodge chance"
    },
    "of_haste": {
      "affix_id": "of_haste",
      "name": "of Haste",
      "stat": "cooldown_reduction_pct",
      "min_value": 0.03,
      "max_value": 0.12,
      "ilvl_scaling": 0.005,
      "weight": 50,
      "allowed_slots": ["weapon", "armor", "accessory"],
      "description": "Reduces skill cooldowns"
    },
    "of_greed": {
      "affix_id": "of_greed",
      "name": "of Greed",
      "stat": "gold_find_pct",
      "min_value": 0.05,
      "max_value": 0.30,
      "ilvl_scaling": 0.015,
      "weight": 30,
      "allowed_slots": ["armor", "accessory"],
      "description": "Increases gold from kills"
    },
    "of_fortune": {
      "affix_id": "of_fortune",
      "name": "of Fortune",
      "stat": "magic_find_pct",
      "min_value": 0.03,
      "max_value": 0.20,
      "ilvl_scaling": 0.01,
      "weight": 30,
      "allowed_slots": ["armor", "accessory"],
      "description": "Increases item rarity chance"
    },
    "of_the_leech": {
      "affix_id": "of_the_leech",
      "name": "of the Leech",
      "stat": "life_on_hit",
      "min_value": 1,
      "max_value": 4,
      "ilvl_scaling": 0.2,
      "weight": 45,
      "allowed_slots": ["armor", "accessory"],
      "description": "Heals on hit"
    },
    "of_regeneration": {
      "affix_id": "of_regeneration",
      "name": "of Regeneration",
      "stat": "hp_regen",
      "min_value": 1,
      "max_value": 8,
      "ilvl_scaling": 0.5,
      "weight": 55,
      "allowed_slots": ["armor", "accessory"],
      "description": "Regenerates HP each turn"
    },
    "of_resilience": {
      "affix_id": "of_resilience",
      "name": "of Resilience",
      "stat": "damage_reduction_pct",
      "min_value": 0.02,
      "max_value": 0.12,
      "ilvl_scaling": 0.005,
      "weight": 50,
      "allowed_slots": ["armor", "accessory"],
      "description": "Reduces incoming damage by a percentage"
    },
    "of_mending": {
      "affix_id": "of_mending",
      "name": "of Mending",
      "stat": "heal_power_pct",
      "min_value": 0.05,
      "max_value": 0.20,
      "ilvl_scaling": 0.01,
      "weight": 35,
      "allowed_slots": ["weapon", "accessory"],
      "description": "Increases healing done"
    },
    "of_the_hawk": {
      "affix_id": "of_the_hawk",
      "name": "of the Hawk",
      "stat": "ranged_damage",
      "min_value": 2,
      "max_value": 8,
      "ilvl_scaling": 0.4,
      "weight": 70,
      "allowed_slots": ["weapon", "accessory"],
      "description": "Increases ranged damage"
    },
    "of_the_wolf": {
      "affix_id": "of_the_wolf",
      "name": "of the Wolf",
      "stat": "attack_damage",
      "min_value": 2,
      "max_value": 8,
      "ilvl_scaling": 0.4,
      "weight": 70,
      "allowed_slots": ["weapon", "accessory"],
      "description": "Increases melee damage"
    },
    "of_precision": {
      "affix_id": "of_precision",
      "name": "of Precision",
      "stat": "crit_chance",
      "min_value": 0.01,
      "max_value": 0.06,
      "ilvl_scaling": 0.003,
      "weight": 50,
      "allowed_slots": ["weapon", "armor"],
      "description": "Increases critical hit chance"
    },
    "of_thorns": {
      "affix_id": "of_thorns",
      "name": "of Thorns",
      "stat": "thorns",
      "min_value": 1,
      "max_value": 6,
      "ilvl_scaling": 0.3,
      "weight": 40,
      "allowed_slots": ["armor", "accessory"],
      "description": "Reflects damage to attackers"
    },
    "of_the_sage": {
      "affix_id": "of_the_sage",
      "name": "of the Sage",
      "stat": "skill_damage_pct",
      "min_value": 0.03,
      "max_value": 0.12,
      "ilvl_scaling": 0.008,
      "weight": 45,
      "allowed_slots": ["armor"],
      "description": "Increases skill damage"
    }
  }
}
```

### Affix Rolling Rules

| Rarity | Prefixes | Suffixes | Total Affixes |
|--------|----------|----------|---------------|
| Common (white) | 0 | 0 | 0 |
| Magic (blue) | 0–1 | 0–1 | 1–2 (at least 1) |
| Rare (yellow) | 1–2 | 1–2 | 3–4 (at least 3) |
| Epic (purple) | 2–3 | 2–3 | 4–5 |
| Unique (orange) | N/A — fixed curated stats | N/A | N/A |
| Set (green) | N/A — fixed curated stats | N/A | N/A |

### Affix Value Scaling by Item Level

```python
def roll_affix_value(affix: dict, item_level: int, rng: random.Random) -> float | int:
    """Roll a stat value for an affix, scaled by item level.
    
    value = uniform(min_value, min_value + ilvl_scaling × item_level)
    capped at max_value.
    """
    scaled_max = min(
        affix["max_value"],
        affix["min_value"] + affix["ilvl_scaling"] * item_level
    )
    raw = rng.uniform(affix["min_value"], max(affix["min_value"], scaled_max))
    
    # Round to int for int stats, 2 decimal places for float stats
    if isinstance(affix["min_value"], int):
        return round(raw)
    return round(raw, 2)
```

### Item Level by Source

| Source | Item Level |
|--------|-----------|
| Swarm enemy drops | 1–3 |
| Fodder enemy drops | 3–6 |
| Mid-tier enemy drops | 5–9 |
| Elite enemy drops | 8–13 |
| Boss enemy drops | 12–18 |
| Default chests | Floor × 2 |
| Boss chests | Floor × 2 + 4 |
| Merchant stock | 4–8 (common/magic only) |

### Name Generation

```
Common:   "{BaseName}"                           → "Greatsword"
Magic:    "{Prefix} {BaseName}"                  → "Cruel Greatsword"
          "{BaseName} {Suffix}"                  → "Greatsword of the Bear"
          "{Prefix} {BaseName} {Suffix}"         → "Cruel Greatsword of the Bear"
Rare:     Random grimdark name from name pool    → "Doomcleaver", "Sorrow's Edge"
          (affixes shown in tooltip, not name)
Epic:     Random grimdark name from name pool    → "The Ashen Verdict"
Unique:   Fixed curated name                     → "Soulreaver"
Set:      Fixed curated name                     → "Crusader's Oath"
```

Rare/Epic name pool stored in `server/configs/item_names_config.json`:
```json
{
  "weapon_names": [
    "Doomcleaver", "Sorrow's Edge", "The Voidfang", "Bonegrinder",
    "Nightfall", "Ashbringer", "Grimtooth", "Deathwhisper",
    "Bloodharvest", "The Dark Promise", "Ironwill", "Plaguebane",
    "Oathkeeper", "Blackthorn", "Duskrend", "Wraithblade"
  ],
  "armor_names": [
    "Dreadplate", "Shadowshroud", "The Iron Casket", "Bonecage",
    "Nightmantle", "Ashweave", "Grimhide", "Deathward",
    "Bloodmail", "The Dark Shell", "Ironbark", "Plagueskin",
    "Oathguard", "Blackiron", "Duskwrap", "Wraithveil"
  ],
  "accessory_names": [
    "Doomsigil", "Sorrow's Grasp", "The Void Eye", "Bonecharm",
    "Nightwhisper", "Ashmark", "Grimtoken", "Deathward",
    "Bloodpact", "The Dark Seal", "Ironwill Signet", "Plaguebrand",
    "Oathbound", "Blackstone", "Duskgem", "Wraithlink"
  ]
}
```

### Base Type Definitions

The existing items in `items_config.json` become **base types**. Their fixed `stat_bonuses` become the item's base stats. Affixes are rolled on top.

Example: An `uncommon_greatsword` base type has `+12 melee` base stats.  
When it drops as a Magic item with the "Deadly" prefix:  
→ Final stats: `+12 melee, +4% crit chance`

When it drops as a Rare item with "Deadly" + "Vampiric" prefixes and "of the Bear" + "of Haste" suffixes:  
→ Final stats: `+12 melee, +7% crit chance, +3 life on hit, +40 HP, +8% CDR`

Same base weapon, completely different item. **This is the GG hunt.**

### Item Generation Pipeline

New module: `server/app/core/item_generator.py`

```python
def generate_item(
    base_type_id: str,
    rarity: Rarity,
    item_level: int,
    seed: int | None = None,
    magic_find_bonus: float = 0.0,
) -> Item:
    """Generate a complete item instance with random affixes.
    
    1. Load base type from items_config
    2. Determine affix count based on rarity
    3. Roll prefix/suffix affixes from allowed pools (filtered by equip_slot)
    4. Roll affix values scaled by item_level
    5. Combine base stats + affix stats
    6. Generate name
    7. Calculate sell value (base × rarity multiplier × affix count bonus)
    8. Return fully-formed Item with unique instance_id
    """

def roll_rarity(
    floor_number: int,
    enemy_tier: str,
    magic_find_bonus: float = 0.0,
    rng: random.Random | None = None,
) -> Rarity:
    """Determine item rarity with floor depth and magic find factored in.
    
    Base rates adjusted by floor_number (deeper = rarer).
    magic_find_bonus adds % chance to upgrade each roll one tier higher.
    """
```

### Sell Value Formula

```
sell_value = base_sell_value × rarity_multiplier + sum(affix_value_bonuses)

Rarity multipliers:
  Common:   1.0×
  Magic:    1.5×
  Rare:     3.0×
  Epic:     6.0×
  Unique:   8.0×
  Set:      8.0×

Each affix adds: affix_value / affix_max_value × 10 gold (scales with roll quality)
```

### Files Changed

| File | Changes |
|------|---------|
| `server/configs/affixes_config.json` | **NEW** — all prefix/suffix definitions |
| `server/configs/item_names_config.json` | **NEW** — grimdark random name pools |
| `server/app/core/item_generator.py` | **NEW** — `generate_item()`, `roll_rarity()`, affix rolling |
| `server/app/models/items.py` | Add `instance_id`, `base_type_id`, `display_name`, `base_stats`, `affixes`, `item_level` to `Item` |
| `server/app/core/loot.py` | Replace `create_item()` calls with `generate_item()` — items now rolled, not looked up |
| `server/configs/items_config.json` | Refactored as base type definitions (existing items preserved) |

### Tests

- `generate_item()` produces valid Item with UUID instance_id
- Common items have 0 affixes
- Magic items have 1–2 affixes
- Rare items have 3–4 affixes
- Affix values fall within min/max range for given item level
- Affix slot filtering works (weapon-only affixes don't appear on armor)
- No duplicate affixes (can't roll "Cruel" twice)
- Name generation matches rarity format rules
- sell_value scales correctly with rarity and affix quality
- Item level 1 produces lower affix values than item level 18 (statistical)
- `magic_find_pct` increases rarity upgrade rate (statistical)
- Two items generated from same base type with different seeds produce different stats
- Backward compatibility: existing non-affix items still load and function

### 16B Implementation Log

**Status:** ✅ Complete  
**Completed:** Session 2 (March 2, 2026)  
**Test results:** 1817 passed (92 new Phase 16B tests + 1725 existing — 0 regressions)

#### Files Created

| File | Purpose |
|------|---------|
| `server/configs/affixes_config.json` | 16 prefix definitions (cruel, piercing, deadly, savage, vampiric, thorned, armored, empowered, penetrating, venomous, holy, sturdy, precise, blessed, resilient, regenerating) and 15 suffix definitions (of_the_bear, of_iron, of_evasion, of_haste, of_greed, of_fortune, of_the_leech, of_regeneration, of_resilience, of_mending, of_the_hawk, of_the_wolf, of_precision, of_thorns, of_the_sage). Each affix has weight, allowed_slots, ilvl_scaling, min/max values. |
| `server/configs/item_names_config.json` | 32 grimdark weapon names, 32 armor names, 32 accessory names for Rare/Epic item name generation. |
| `server/app/core/item_generator.py` | Core generation module: `generate_item()`, `roll_rarity()`, `roll_affixes()`, `roll_affix_value()`, `generate_item_name()`, `calculate_sell_value()`, `generate_loot_item()`, `_combine_stats()`, `_get_eligible_affixes()`, `_calculate_item_level()`. Config loaders for affixes and item names with caching. |
| `server/tests/test_phase16b_affix_system.py` | 92 tests across 20 test classes covering: config loading, value rolling, slot filtering, affix counts by rarity, duplicate prevention, name generation, sell value, full pipeline, instance_id uniqueness, stat combining, consumables passthrough, seed determinism, ilvl scaling, rarity distribution, backward compat, loot integration, model fields, type tags, names config, convenience wrapper. |

#### Files Modified

| File | Changes |
|------|---------|
| `server/app/models/items.py` | `Item` model expanded with 6 new fields: `instance_id` (str, default ""), `base_type_id` (str, default ""), `display_name` (str, default ""), `base_stats` (StatBonuses, default factory), `affixes` (list[dict], default factory), `item_level` (int, default 1). `Inventory.remove_item()` updated to try `instance_id` match first, then fall back to `item_id`. All defaults ensure full backward compatibility with existing items. |
| `server/app/core/loot.py` | Added `generate_enemy_loot()` and `generate_chest_loot()` functions that use the item_generator to produce affix-bearing items. Added `_pick_base_type_from_pool()` helper. Original `create_item()`, `roll_enemy_loot()`, `roll_chest_loot()` kept intact for backward compat. |
| `server/app/core/equipment_manager.py` | `equip_item()` updated to search inventory by `instance_id` first, then fall back to `item_id` — correctly handles generated items where multiple copies of the same base type may exist with different affixes. |

#### Key Design Decisions

1. **Additive approach** — all new functions exist alongside old ones. `create_item()` still works for static items. `generate_item()` is the new path for affix items. No existing code broken.
2. **Rarity string-based internally** — `roll_rarity()` returns a rarity string ("common", "magic", "rare", "epic") used inside the generator. Mapped to existing `Rarity` enum values for backward compat (magic/rare/epic → `UNCOMMON` for now). Phase 16C will add the proper `MAGIC`, `RARE`, `EPIC` enum values.
3. **No duplicate stats on one item** — affix rolling tracks `used_stats` to prevent e.g. two "+armor" affixes stacking. Each stat can only appear once per item.
4. **Slot-filtered affixes** — weapon-only affixes (cruel, vampiric, penetrating) never appear on armor. Armor-only affixes (thorned, of_resilience) never appear on weapons. This ensures items make thematic sense.
5. **Item level from tier + floor** — enemy tier determines the base ilvl range, floor adds a small bonus. Boss ilvl 12–18, fodder ilvl 3–6. Higher ilvl = higher maximum affix rolls.
6. **Consumable passthrough** — health potions, portal scrolls, etc. get `instance_id` and `base_type_id` but no affixes. They pass through the generator unchanged.
7. **instance_id for equip** — `equip_item()` prefers `instance_id` match when present, enabling correct equipping of specific generated items when multiple copies of the same base type exist in inventory.

---

## 16C — Rarity Overhaul & Item Tiers

**Effort:** Small–Medium  
**Risk:** Low — additive (new enum values, drop rate config)  
**Prerequisite:** 16B (affix system determines what rarities actually mean)

### Updated Rarity Tiers

| Tier | Enum | Color (Hex) | CSS Variable | Affix Count | Drop Rate (base) |
|------|------|-------------|-------------|-------------|-------------------|
| Common | `COMMON` | `#9d9d9d` (gray) | `--rarity-common` | 0 | 60% |
| Magic | `MAGIC` | `#4488ff` (blue) | `--rarity-magic` | 1–2 | 25% |
| Rare | `RARE` | `#ffcc00` (yellow) | `--rarity-rare` | 3–4 | 12% |
| Epic | `EPIC` | `#b040ff` (purple) | `--rarity-epic` | 4–5 | 2.5% |
| Unique | `UNIQUE` | `#ff8800` (orange) | `--rarity-unique` | Fixed | 0.5% (separate table) |
| Set | `SET` | `#00cc44` (green) | `--rarity-set` | Fixed | 0.3% (separate table) |

> **Note:** Phase 15's `RARE = "rare"` (blue) becomes `MAGIC` in Phase 16. Phase 15's rare items are retroactively reclassified as Magic-tier base types. The new `RARE` is the yellow Diablo-style rare with 3–4 random affixes. This is a semantic rename handled during the 16C migration.

### Migration from Phase 15 Rarity

| Phase 15 Name | Phase 15 Color | Phase 16 Name | Phase 16 Color | Reason |
|---------------|----------------|---------------|----------------|--------|
| Common | gray | Common | gray | Unchanged |
| Uncommon | green | Common | gray | Folded into base type variants |
| Rare (blue) | blue | Magic (blue) | blue | Renamed to match Diablo convention |
| *(new)* | | Rare (yellow) | yellow | True RNG rares with 3–4 affixes |
| *(new)* | | Epic (purple) | purple | Premium RNG with 4–5 affixes |
| *(new)* | | Unique (orange) | orange | Hand-curated chase items |
| *(new)* | | Set (green) | green | Set bonus chase items |

### Drop Rate Scaling by Floor & Magic Find

```
effective_rate[tier] = base_rate[tier] × (1 + floor_bonus) × (1 + magic_find_pct)

Floor bonuses:
  Floor 1–2:  0.0  (base rates)
  Floor 3–4:  0.15 (+15%)
  Floor 5–6:  0.35 (+35%)
  Floor 7–8:  0.60 (+60%)
  Floor 9+:   1.00 (+100%)

Example: Rare base rate 12%, floor 7 (+60%), 20% MF from gear:
  12% × 1.60 × 1.20 = 23% chance per item to be Rare-tier
```

### Boss Drop Override

Bosses always drop at least one item of their guaranteed minimum rarity:

| Boss Tier | Guaranteed Minimum | Items Dropped |
|-----------|--------------------|---------------|
| All bosses | Magic (blue) | 2–3 |
| Boss on floor 5+ | Rare (yellow) | 2–4 |
| Boss on floor 8+ | Epic (purple) | 3–4, 10% chance for Unique/Set |

### Files Changed

| File | Changes |
|------|---------|
| `server/app/models/items.py` | Expand `Rarity` enum: `MAGIC`, `EPIC`, `UNIQUE`, `SET`; rename existing `UNCOMMON` handling |
| `server/configs/loot_tables.json` | Updated rarity references, floor-scaled rate config |
| `server/app/core/loot.py` | `roll_rarity()` uses floor + magic find; boss guaranteed rarity logic |
| `server/app/core/item_generator.py` | Epic affix count (4–5) |
| `client/src/canvas/renderConstants.js` | All rarity color constants |
| `client/src/styles/base/_variables.css` | All rarity CSS variables |
| `client/src/canvas/overlayRenderer.js` | Ground item sparkles per rarity color |
| Migration script | Reclassify Phase 15 "Rare" items to "Magic" |

### Tests

- All 6 rarity tiers serialize/deserialize correctly
- Drop rate scaling by floor produces expected distributions (statistical)
- Magic find increases effective drop rates
- Boss guaranteed minimum rarity works per floor bracket
- Phase 15 rare items correctly migrated to Magic tier
- Rarity colors render correctly for all tiers on ground and in inventory

### 16C Implementation Log

**Status:** COMPLETE  
**Tests:** 95 new tests (1912 total, 0 failures)

#### Files Created

| File | Purpose |
|------|---------|
| `server/tests/test_phase16c_rarity_overhaul.py` | 95 tests covering enum serialization, rarity colors/display names, tier ordering, enforce_minimum_rarity, boss guaranteed rarity, boss drop counts, boss unique chance, rarity upgrade chain, item generation with all tiers, epic affix counts, sell value multipliers, config migration, guaranteed rarity pool picking, drop rate distribution (statistical), boss loot integration, backward compatibility, and full pipeline integration |

#### Files Modified

| File | Changes |
|------|---------|
| `server/app/models/items.py` | Expanded `Rarity` enum from 2 values (COMMON, UNCOMMON) to 7 (COMMON, UNCOMMON, MAGIC, RARE, EPIC, UNIQUE, SET). UNCOMMON kept for backward compat with saved data. |
| `server/app/core/item_generator.py` | Rarity enum mappings updated from placeholder UNCOMMON to proper enums. Added `RARITY_TIER_ORDER`, `RARITY_COLORS`, `get_rarity_color()`, `get_rarity_display_name()`, `get_boss_guaranteed_rarity()`, `get_boss_drop_count()`, `enforce_minimum_rarity()`, `boss_has_unique_chance()`. |
| `server/app/core/loot.py` | `_try_rarity_upgrade()` expanded to full chain: COMMON→MAGIC, UNCOMMON→MAGIC, MAGIC→RARE, RARE→EPIC. New `_pick_guaranteed_rarity_from_pool()` generalizes any target rarity. Boss drop count/minimum rarity enforcement in `generate_enemy_loot()`. |
| `server/configs/loot_tables.json` | All `guaranteed_rarity: "uncommon"` → `"magic"`. New `rarity_config` section with `base_rates`, `floor_bonuses`, `boss_guaranteed_rarity`, `boss_drop_counts`, `boss_unique_chance_floor8`. |
| `server/configs/items_config.json` | All items with `"rarity": "uncommon"` migrated to `"rarity": "magic"` (7 equippable + 2 consumables). |
| `client/src/canvas/overlayRenderer.js` | `RARITY_COLORS` expanded to 7 tiers. Sparkle/glow logic changed from binary `hasUncommon` to priority-based using `RARITY_PRIORITY` array and per-tier `SPARKLE_COLORS`. |
| `client/src/styles/base/_variables.css` | Added 6 CSS custom properties: `--rarity-common`, `--rarity-magic`, `--rarity-rare`, `--rarity-epic`, `--rarity-unique`, `--rarity-set`. |
| `client/src/utils/itemUtils.js` | Added `RARITY_COLORS`, `getRarityColor()`, `getRarityDisplayName()` exports. |
| `client/src/styles/components/_inventory.css` | All 7 rarity selector groups expanded for magic/rare/epic/unique/set variants using CSS variables. |
| `client/src/styles/town/_gear-management.css` | `.rarity-border-*` and `.gear-tooltip.rarity-border-*` expanded for all 6 tiers. |
| `client/src/styles/town/_hero-roster.css` | `.hero-equip-tag.rarity-*` and hover states expanded for all 6 tiers with Phase 16C colors. |
| `client/src/styles/screens/_post-match.css` | `.lost-item.rarity-*` classes expanded for all 6 tiers. |
| `client/src/components/TownHub/Bank.jsx` | `RARITY_COLORS` object expanded from 2 entries to 7 entries. |
| `client/src/components/TownHub/Merchant.jsx` | `RARITY_COLORS` object expanded from 2 entries to 7 entries. |
| `server/tests/test_items.py` | 7 tests updated: "uncommon" references → "magic" to match migration. |
| `server/tests/test_phase16a_stat_expansion.py` | 1 test updated: `UNCOMMON` → `MAGIC` in rarity upgrade assertion. |
| `server/tests/test_loot_combat.py` | 1 test fixed: crit-aware damage assertion (pre-existing flaky test). |

#### Key Design Decisions

1. **Legacy UNCOMMON preserved** — `Rarity.UNCOMMON` enum value kept for backward compatibility with saved player data. New code uses MAGIC exclusively.
2. **Full upgrade chain** — MF rarity upgrades follow COMMON→MAGIC→RARE→EPIC. Epic is the ceiling for MF-based upgrades; Unique/Set drop via separate boss mechanics only.
3. **Boss floor brackets** — Floor 1–4: Magic minimum, Floor 5–7: Rare minimum, Floor 8+: Epic minimum with 10% chance for Unique/Set.
4. **Boss drop scaling** — Floor 1–4: 2–3 items, Floor 5–7: 2–4 items, Floor 8+: 3–4 items.
5. **Generalized guaranteed rarity** — `_pick_guaranteed_rarity_from_pool()` works for any target rarity, not just "uncommon". Includes backward compat fallback for legacy data.
6. **Priority-based sparkle rendering** — Canvas overlay finds the highest rarity item on each tile and renders the appropriate sparkle color, rather than binary uncommon-or-not.
7. **CSS variable-driven styling** — All rarity colors flow through CSS custom properties in `_variables.css`, making theme changes trivial.

---

## 16D — Unique Items

**Effort:** Medium  
**Risk:** Low — purely additive content  
**Prerequisite:** 16C (Unique rarity tier must exist)

### Design Philosophy

Unique items are **hand-curated, build-defining** items with fixed stats and special properties. They don't use the affix system — their stats are authored specifically. They should make you say "oh HELL yes" when they drop. Each unique should push the player toward a specific playstyle or class.

### Unique Item Roster (16 items)

#### Weapons (6)

| ID | Name | Slot | Key Stats | Special Effect | Best For |
|----|------|------|-----------|----------------|----------|
| `unique_soulreaver` | Soulreaver | Weapon | +15 melee, +5 life on hit | Heals 15% of melee damage dealt | Crusader, Hexblade |
| `unique_whisper` | The Whisper | Weapon | +10 ranged, +8% crit | Critical hits deal 3× instead of 1.5× | Ranger, Inquisitor |
| `unique_grimfang` | Grimfang | Weapon | +20 melee, +5% crit | On kill: +25% move speed for 2 turns | Hexblade |
| `unique_dawnbreaker` | Dawnbreaker | Weapon | +12 melee, +25% holy dmg | Exorcism/Rebuke cooldowns reduced by 2 turns | Confessor, Inquisitor |
| `unique_plaguebow` | Plaguebow | Weapon | +16 ranged, +20% DoT dmg | Ranged hits apply 4 damage/turn poison for 2 turns | Ranger |
| `unique_voidedge` | Voidedge | Weapon | +14 melee, +14 ranged | All damage ignores 50% of target armor | Hexblade, Inquisitor |

#### Armor (5)

| ID | Name | Slot | Key Stats | Special Effect | Best For |
|----|------|------|-----------|----------------|----------|
| `unique_bonecage` | The Bonecage | Armor | +10 armor, +40 HP, −3 move speed | Take 15% less damage from all sources | Crusader |
| `unique_shadowshroud` | Shadowshroud | Armor | +5 armor, +5% dodge, +10% CDR | Shadow Step cooldown reduced by 2 turns | Hexblade, Inquisitor |
| `unique_penitent_mail` | Penitent Mail | Armor | +6 armor, +60 HP | Healing received increased by 30% | Crusader, Confessor |
| `unique_wraithmantle` | Wraithmantle | Armor | +4 armor, +10% dodge | On dodge: deal 10 damage to attacker | Ranger |
| `unique_ironwill` | Ironwill Plate | Armor | +14 armor, +20 HP | Immune to stun and root | Crusader |

#### Accessories (5)

| ID | Name | Slot | Key Stats | Special Effect | Best For |
|----|------|------|-----------|----------------|----------|
| `unique_eye_of_malice` | Eye of Malice | Accessory | +8% crit, +20% skill dmg | Skills that deal critical hits have no cooldown on next use | All DPS |
| `unique_bloodpact` | Bloodpact Ring | Accessory | +80 HP, +4 life on hit | At below 30% HP: +40% damage | All |
| `unique_greed_sigil` | Sigil of Greed | Accessory | +50% gold find, +30% magic find | −15% damage dealt | MF farming |
| `unique_wardens_oath` | Warden's Oath | Accessory | +6 armor, +4 thorns, +30 HP | Taunt radius increased by 1 tile | Crusader |
| `unique_prayer_beads` | Prayer Beads | Accessory | +30% heal power, +4 hp regen, +40 HP | Prayer heals all adjacent allies (not just target) | Confessor |

### Unique Drop Rules

- Uniques have a **separate drop table** — they don't compete with normal rarity rolls
- Base chance: 0.5% per item dropped (modified by magic find and floor depth)
- Only drop from Elite and Boss tier enemies
- Weighted by enemy type → class-appropriate uniques drop more often from thematic enemies
  - Undead bosses → holy weapon uniques weighted higher
  - Demon bosses → melee weapon uniques weighted higher
- Each unique can only drop **once per dungeon run** (no duplicates in a single run)

### Implementation

New config file: `server/configs/uniques_config.json`

Special effects are implemented as **item tags** that the combat system checks:

```python
# In combat.py damage resolution:
if attacker_has_unique("unique_voidedge"):
    effective_armor = target_armor * 0.5  # Ignore 50% armor

# In turn_resolver.py buff phase:
if player_has_unique("unique_penitent_mail"):
    heal_amount = base_heal * 1.30  # +30% healing received
```

### Files Changed

| File | Changes |
|------|---------|
| `server/configs/uniques_config.json` | **NEW** — 16 unique item definitions with special effects |
| `server/app/core/item_generator.py` | `generate_unique()` function, unique drop roll in loot pipeline |
| `server/app/core/combat.py` | Check for unique weapon/armor effects in damage calc |
| `server/app/core/turn_resolver.py` | Check for unique effects in buff/heal/skill phases |
| `server/app/core/skills.py` | Unique-specific cooldown modifications |
| `client/src/canvas/overlayRenderer.js` | Orange beam/glow for unique ground drops |

### Tests

- All 16 uniques load from config and hydrate correctly
- Unique stats apply on equip, remove on unequip
- Each special effect works as described (16 test cases)
- Uniques only drop from Elite/Boss tier enemies
- No duplicate unique drops per dungeon run
- Magic find increases unique drop chance
- Unique items display correctly in inventory with orange rarity

### 16D Implementation Log

**Status:** COMPLETE  
**Tests:** 82 new tests (1994 total, 0 failures)

#### Files Created

| File | Purpose |
|------|---------|
| `server/configs/uniques_config.json` | All 16 unique item definitions with curated stats, special effects, drop rules, and enemy-type weighting |
| `server/tests/test_phase16d_unique_items.py` | 82 tests covering config loading, unique generation (parametrized over all 16 IDs), equipment helpers, drop rolling, all 16 special effects in isolation, loot integration, and backward compatibility |

#### Files Modified

| File | Changes |
|------|---------|
| `server/app/core/item_generator.py` | Added `load_uniques_config()`, `generate_unique(unique_id)`, `get_all_unique_ids()`, `get_unique_definition()`, `roll_unique_drop()` (weighted drop roll with tier/floor/MF scaling), `has_unique_equipped()`, `get_unique_special_effect()`, `get_all_equipped_unique_effects()`. Added `_uniques_cache` cleared by `clear_generator_caches()`. |
| `server/app/core/combat.py` | Both `calculate_damage()` and `calculate_ranged_damage()` updated. Collects attacker/defender unique effects from equipped gear. Implements: Soulreaver melee lifesteal (15%), The Whisper 3× crit override, Voidedge 50% armor ignore, The Bonecage 15% flat DR, Bloodpact +40% damage below 30% HP, Sigil of Greed −15% damage penalty, Wraithmantle dodge retaliate (10 damage), Plaguebow 2-turn poison DoT (4 dmg/turn). New combat_info keys: `unique_lifesteal_healed`, `dodge_retaliate_damage`, `plaguebow_applied`, `plaguebow_dot`. |
| `server/app/core/turn_resolver.py` | Ranged section: Plaguebow DoT poison buff creation and application after ranged kills/hits, with combat log message. Melee section: Grimfang on-kill haste buff (+move_speed for 2 turns, refreshes), Soulreaver lifesteal combat log message, Wraithmantle dodge retaliate combat log with kill tracking. |
| `server/app/core/skills.py` | `_apply_skill_cooldown()` gains `dealt_damage` parameter; applies Dawnbreaker CDR (exorcism/rebuke −2), Shadowshroud CDR (shadow_step −2), Eye of Malice crit-reset (if `dealt_damage=True`, rolls crit chance to reset cooldown to 0). All 7 damage-dealing skill resolvers pass `dealt_damage=True`. `resolve_stun_damage()` checks Ironwill Plate CC immunity (resists stun/root). `resolve_heal()` and `resolve_hot()` apply Penitent Mail +30% healing bonus. `resolve_hot()` applies Prayer Beads AoE heal to all adjacent same-team allies. `resolve_taunt()` applies Warden's Oath taunt range +1. |
| `server/app/core/loot.py` | `generate_enemy_loot()` gains `dropped_unique_ids` parameter. After normal item generation, calls `roll_unique_drop()` for elite/boss enemies. Unique appended to loot list and tracked in `dropped_unique_ids` set for per-run dedup. |
| `client/src/canvas/overlayRenderer.js` | Added bright vertical beam column for `unique` and `set` rarity ground drops — gradient beam from tile center upward (2.5 tiles high), outer wider glow, and pulsing core at base. Uses existing `SPARKLE_COLORS` orange (#ff8800) for unique rarity. |

#### Key Design Decisions

1. **Effects via affixes list** — Unique special effects are stored in the item's `affixes` array as entries with `type="unique_effect"` and an `effect` sub-dict carrying the full effect data. This avoids adding new fields to the Item model while keeping effects co-located with the item.
2. **Equipment-based lookups** — `has_unique_equipped()` and `get_all_equipped_unique_effects()` scan the player's equipment dict at combat time, so effects are always in sync with what's actually equipped.
3. **Weighted enemy-type drops** — `enemy_type_weights` in the config maps enemy types (undead, demon, beast, corrupted) to weighted unique ID lists, so thematically appropriate uniques drop more often from matching enemies.
4. **Per-run dedup** — `dropped_unique_ids` set is passed through the loot pipeline to enforce the "max 1 of each unique per run" rule without requiring global state.
5. **Combat pipeline integration** — Offensive unique effects (Voidedge, Bloodpact, Greed Sigil, Whisper) apply in the damage calculation functions; defensive effects (Bonecage, Wraithmantle) apply in the defender's damage reduction/dodge checks; skill effects (Dawnbreaker, Shadowshroud, Eye of Malice, Ironwill, Penitent Mail, Warden's Oath, Prayer Beads) apply in the skill resolution functions.
6. **Plaguebow & Grimfang as buff-based** — Both effects create temporary buffs (poison DoT, haste) through the existing buff system rather than custom state, keeping the turn resolver clean.
7. **Backward compatibility** — All unique effects are opt-in checks; players without uniques hit no new code paths. Existing items and combat flow are unaffected.

---

## 16E — Set Items

**Effort:** Medium  
**Risk:** Medium — set bonus tracking is a new subsystem  
**Prerequisite:** 16C (Set rarity tier must exist)

### Design Philosophy

Set items provide moderate-to-good base stats individually, but unlock powerful **set bonuses** when wearing multiple pieces from the same set. This creates a compelling "I found 2/3 pieces, I NEED to find the third" chase.

### Set Roster (5 sets, 3 pieces each = 15 items)

#### Crusader's Oath (Tank Set)

| Piece | Slot | Stats |
|-------|------|-------|
| Crusader's Oath Warhammer | Weapon | +14 melee, +20 HP |
| Crusader's Oath Plate | Armor | +10 armor, +30 HP |
| Crusader's Oath Signet | Accessory | +4 armor, +40 HP |

| Pieces | Set Bonus |
|--------|-----------|
| 2/3 | +4 armor, +30 HP, Taunt duration +1 turn |
| 3/3 | +8 armor, +80 HP, Taunt duration +1 turn, Bulwark also grants +4 thorns |

#### Voidwalker's Regalia (Hexblade Set)

| Piece | Slot | Stats |
|-------|------|-------|
| Voidwalker Blade | Weapon | +12 melee, +10 ranged, +3% crit |
| Voidwalker Cloak | Armor | +6 armor, +5% dodge, +20 HP |
| Voidwalker Seal | Accessory | +15% DoT damage, +30 HP |

| Pieces | Set Bonus |
|--------|-----------|
| 2/3 | +10% skill damage, Wither duration +1 turn |
| 3/3 | +20% skill damage, Wither duration +2 turns, Ward reflects +4 per charge |

#### Deadeye's Arsenal (Ranger Set)

| Piece | Slot | Stats |
|-------|------|-------|
| Deadeye Longbow | Weapon | +16 ranged, +5% crit |
| Deadeye Leathers | Armor | +5 armor, +8% dodge, +20 HP |
| Deadeye Scope | Accessory | +30% crit damage, +20 HP |

| Pieces | Set Bonus |
|--------|-----------|
| 2/3 | +10% crit chance, Power Shot cooldown −1 |
| 3/3 | +15% crit chance, +50% crit damage, critical ranged hits pierce to 1 adjacent enemy |

#### Faith's Radiance (Confessor Set)

| Piece | Slot | Stats |
|-------|------|-------|
| Radiant Staff | Weapon | +8 melee, +25% heal power |
| Radiant Vestments | Armor | +6 armor, +50 HP |
| Radiant Halo | Accessory | +15% holy damage, +40 HP |

| Pieces | Set Bonus |
|--------|-----------|
| 2/3 | +15% heal power, Heal cooldown −1 turn |
| 3/3 | +30% heal power, Heal cooldown −1, Exorcism applies 1-turn stun vs tagged |

#### Seeker's Judgment (Inquisitor Set)

| Piece | Slot | Stats |
|-------|------|-------|
| Seeker's Crossbow | Weapon | +8 melee, +10 ranged, +10% holy damage |
| Seeker's Coat | Armor | +5 armor, +6% CDR, +30 HP |
| Seeker's Eye | Accessory | +6% crit, +20% skill damage |

| Pieces | Set Bonus |
|--------|-----------|
| 2/3 | Rebuke cooldown −2, Divine Sense also reveals non-tagged enemies |
| 3/3 | Rebuke cooldown −2, Divine Sense reveals all + grants +10% damage vs revealed, Shadow Step range +1 |

### Set Bonus System Architecture

New module: `server/app/core/set_bonuses.py`

```python
def calculate_active_set_bonuses(equipment: dict) -> list[dict]:
    """Given a hero's equipment, determine which set bonuses are active.
    
    Returns list of active bonus dicts:
    [{"set_id": "crusaders_oath", "pieces": 2, "bonuses": {...}}, ...]
    """

def apply_set_bonuses(player: PlayerState, active_sets: list[dict]) -> None:
    """Apply stat bonuses from active sets to the player's effective stats."""

def get_set_skill_modifiers(player: PlayerState, active_sets: list[dict]) -> dict:
    """Return skill-specific modifiers from set bonuses.
    
    e.g., {"taunt": {"duration_bonus": 1}, "wither": {"duration_bonus": 2}}
    """
```

Tracked on `PlayerState`:
```python
active_set_bonuses: list[dict] = Field(default_factory=list)
# Recalculated whenever equipment changes
```

### Set Bonus Recalculation

Triggered whenever a hero equips or unequips an item:
1. `equipment_manager.py` calls `calculate_active_set_bonuses()`
2. Old set bonuses are removed from effective stats
3. New set bonuses are applied
4. Set bonus state sent to client in equipment update message

### Drop Rules

- Set items share the same drop table as Uniques (0.3% base chance per item)
- Only drop from Elite and Boss tier enemies
- Weighted by set theme → undead dungeon themes weight Crusader/Confessor sets higher, etc.
- Each set piece can only drop once per dungeon run

### Files Changed

| File | Changes |
|------|---------|
| `server/configs/sets_config.json` | **NEW** — 5 sets with piece definitions and set bonus tiers |
| `server/app/core/set_bonuses.py` | **NEW** — set bonus calculation, stat application, skill modifiers |
| `server/app/core/equipment_manager.py` | Trigger set bonus recalculation on equip/unequip |
| `server/app/core/skills.py` | Apply set-based cooldown reductions and effect modifications |
| `server/app/core/combat.py` | Apply set-based combat modifiers (pierce, stun on holy, etc.) |
| `client/src/components/Inventory/` | Set piece indicator (green name, "2/3 Crusader's Oath"), set bonus tooltip |
| `client/src/components/HeaderBar/` | Active set bonus icons |

### Tests

- 0/3 pieces → no set bonus active
- 2/3 pieces → tier 1 bonus active, tier 2 not active
- 3/3 pieces → both tier 1 and tier 2 bonuses active
- Unequipping a set piece removes the set bonus
- Set stat bonuses aggregate correctly with equipment and affix bonuses
- Set skill modifiers apply (cooldown reductions, duration bonuses)
- Set combat modifiers work (pierce, stun, thorns)
- Set items display with green rarity and set name in tooltip
- Each set piece drops only once per dungeon run

### 16E Implementation Log

**Status:** COMPLETE  
**Tests:** 104 new tests (2098 total, 0 new failures)

#### Files Created

| File | Purpose |
|------|---------|
| `server/configs/sets_config.json` | All 5 set definitions (Crusader's Oath, Voidwalker's Regalia, Deadeye's Arsenal, Faith's Radiance, Seeker's Judgment) with 3 pieces each, 2 bonus tiers per set, skill_modifiers, special_effects, drop_rules (base 0.3%, elite/boss only, floor scaling), and class_affinity_weights |
| `server/app/core/set_bonuses.py` | Core set bonus module: `load_sets_config()`, `calculate_active_set_bonuses()`, `get_set_stat_totals()`, `apply_set_stat_bonuses()`, `remove_set_stat_bonuses()`, `get_set_skill_modifiers()`, `get_set_special_effects()`. Highest tier replaces lower tiers (Diablo convention). |
| `server/tests/test_phase16e_set_items.py` | 104 tests: config loading (9), set piece generation parametrized over all 15 pieces (30+), bonus calculation at 0/1/2/3 thresholds, stat application/removal with cap checks, skill modifiers for all 5 sets, special effects (Deadeye pierce), drop rolling (tier restriction, dedup, MF scaling, boss 3×, floor scaling, class affinity weighting), loot integration, PlayerState storage, backward compatibility, get_set_definition, cache clearing |

#### Files Modified

| File | Changes |
|------|---------|
| `server/app/models/player.py` | Added `active_set_bonuses: list[dict] = Field(default_factory=list)` to PlayerState for storing current set bonus state |
| `server/app/core/equipment_manager.py` | Added `_recalculate_set_bonuses(player)` function. Called after both `equip_item` and `unequip_item` stat recalculation. Removes old set bonuses, calculates new active bonuses from current equipment, applies stat bonuses, and stores result on PlayerState. Added `active_set_bonuses` to equip/unequip return dicts for client sync. |
| `server/app/core/item_generator.py` | Added `generate_set_piece(set_id, piece_id)`, `get_all_set_piece_ids()`, `roll_set_drop()` (weighted drop roll with tier/floor/MF/class-affinity scaling). Updated `clear_generator_caches()` to also clear set cache. Set items use `Rarity.SET`, carry `affixes=[{type:"set_bonus", name:setName, value:setId}]` for client display. |
| `server/app/core/loot.py` | `generate_enemy_loot()` gains `dropped_set_piece_ids` and `player_class` parameters. After unique drop roll, calls `roll_set_drop()` for elite/boss enemies with per-run deduplication tracking. |
| `server/app/core/skills.py` | Three integration points: (1) `_apply_skill_cooldown()` applies set bonus CDR from `get_set_skill_modifiers()` after unique CDR checks; (2) `resolve_taunt()` applies set bonus taunt duration bonus (Crusader's Oath); (3) `resolve_dot()` applies set bonus DoT duration bonus (Voidwalker's Regalia Wither). |
| `client/src/utils/itemUtils.js` | Added `getItemSetInfo(item)` to extract set metadata from item affixes, and `formatSetBonuses(activeSets)` to format active set bonuses for tooltip display. |
| `tools/item-forge/src/components/SetEditor.jsx` | Fixed stat key display: removed `.slice(0, 8)` from both piece stat inputs and bonus stat inputs so all 20 stats are editable. Updated header comment to reflect 16E implementation. |

#### Key Design Decisions

1. **Separate set_bonuses.py module** — Set bonus logic is isolated from item_generator.py and equipment_manager.py, providing a clean interface for stat/skill/effect queries.
2. **Highest tier replaces lower tiers** — `get_set_stat_totals()` uses only the highest active bonus tier's stat bonuses per set. This matches Diablo convention — the 3-piece bonus replaces the 2-piece stat bonus, not cumulative.
3. **Skill modifiers via highest tier** — `get_set_skill_modifiers()` also uses only the highest tier, so a 3-piece set's skill modifiers (which typically include the 2-piece modifiers too) are definitive.
4. **Equipment-triggered recalculation** — `_recalculate_set_bonuses()` runs after every equip/unequip operation, ensuring set bonuses are always synchronized with actual equipment state.
5. **Per-run dedup** — Same pattern as unique items: `dropped_set_piece_ids` set passed through the loot pipeline prevents duplicate set pieces within a single dungeon run.
6. **Class affinity weighting** — Drop pool uses weighted random selection, with each class having 3× weight for their primary set and 1.5× for a secondary set, creating meaningful class-targeted loot.
7. **Backward compatibility** — All set bonus checks are opt-in. Players without set items have an empty `active_set_bonuses` list and encounter no new code paths.

---

## 16F — Equipment Slot Expansion

**Effort:** Small–Medium  
**Risk:** Medium — UI changes needed, but server logic is straightforward  
**Prerequisite:** 16A (new stats must exist)

### New Equipment Slots

Expand from 3 slots to 5 slots:

| Slot | Current? | Purpose |
|------|----------|---------|
| `weapon` | ✅ Existing | Offensive stats (melee/ranged damage, crit, armor pen) |
| `armor` | ✅ Existing | Defensive stats (armor, HP, damage reduction, dodge) |
| `accessory` | ✅ Existing | Utility stats (CDR, magic find, gold find, mixed) |
| `helmet` | **NEW** | Mixed offensive/defensive (crit, skill damage, HP, armor) |
| `boots` | **NEW** | Movement & utility (move speed, dodge, HP regen, gold find) |

### Why These Slots?

- **Helmet** adds a second item slot for offensive/defensive hybrid stats, increasing build diversity
- **Boots** are the natural home for move_speed, dodge, and utility stats — they create meaningful trade-offs (do I wear fast boots or tanky boots?)
- Both slots add more "inventory Tetris" — more items to find, compare, and upgrade
- 5 slots × 4+ affixes per rare item = potentially 20+ stat bonuses interacting — that's Diablo territory

### New Base Types

#### Helmets (6)

| ID | Name | Rarity | Stats |
|----|------|--------|-------|
| `common_leather_cap` | Leather Cap | Common | +1 armor, +10 HP |
| `common_iron_helm` | Iron Helm | Common | +2 armor, +15 HP |
| `magic_warhelm` | Tempered Warhelm | Magic base | +4 armor, +20 HP |
| `magic_cowl_of_shadows` | Cowl of Shadows | Magic base | +2 armor, +3% crit |
| `magic_circlet` | Bone Circlet | Magic base | +10% skill damage, +20 HP |
| `magic_crown` | Warlord's Crown | Magic base | +3 armor, +8% CDR |

#### Boots (6)

| ID | Name | Rarity | Stats |
|----|------|--------|-------|
| `common_leather_boots` | Leather Boots | Common | +1 move speed |
| `common_iron_greaves` | Iron Greaves | Common | +2 armor |
| `magic_windrunners` | Windrunner Boots | Magic base | +1 move speed, +3% dodge |
| `magic_ironfoot` | Ironfoot Greaves | Magic base | +4 armor, +15 HP |
| `magic_stalker_boots` | Stalker Boots | Magic base | +1 move speed, +10% gold find |
| `magic_pilgrims_sandals` | Pilgrim's Sandals | Magic base | +3 hp regen, +20 HP |

### Implementation

```python
class EquipSlot(str, Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    ACCESSORY = "accessory"
    HELMET = "helmet"     # NEW
    BOOTS = "boots"       # NEW
```

`Equipment` model gains `helmet` and `boots` slots. `total_bonuses()` iterates over all 5 slots.

### Files Changed

| File | Changes |
|------|---------|
| `server/app/models/items.py` | Add `HELMET`, `BOOTS` to `EquipSlot`; update `Equipment` model |
| `server/app/core/equipment_manager.py` | Handle 5 slots in equip/unequip/stat aggregation |
| `server/configs/items_config.json` | Add 12 new base type items (6 helmets, 6 boots) |
| `server/configs/loot_tables.json` | Add helmet/boots to enemy and chest loot pools |
| `server/configs/affixes_config.json` | Add `"helmet"` and `"boots"` to affix `allowed_slots` |
| `client/src/components/Inventory/` | 5-slot equipment grid (add helmet and boots slots) |
| `client/src/styles/components/_inventory.css` | Updated equipment layout |

### Tests

- Helmet and boots equip/unequip correctly
- Stat bonuses from all 5 slots aggregate correctly
- Can't equip a weapon in a helmet slot (slot validation)
- Inventory full check accounts for helmet/boots unequip space
- Affixes roll on helmet/boots with correct allowed_slots filtering
- UI renders 5 equipment slots correctly

---

## 16G — Client UI & Loot Presentation

**Effort:** Medium  
**Risk:** Low — visual/UX only, no server logic  
**Prerequisite:** 16B (affix data must exist to display)

### Item Tooltips

Redesigned tooltip showing full item information:

```
┌───────────────────────────────┐
│  ★ Doomcleaver                │  ← Name (rarity colored)
│  Rare Greatsword              │  ← Rarity + base type
│  Item Level: 14               │
│                               │
│  +12 Melee Damage             │  ← Base stats (gray)
│  ────────────────             │
│  +7% Critical Chance          │  ← Affix stats (blue)
│  +3 Life on Hit               │
│  +40 Max HP                   │
│  +8% Cooldown Reduction       │
│  ────────────────             │
│  Sell: 94 gold                │
│                               │
│  "Forged in the deep dark."   │  ← Flavor text
└───────────────────────────────┘
```

For Set items, add set bonus info:

```
│  ── Crusader's Oath (2/3) ──  │  ← Set name + piece count
│  ✓ +4 Armor, +30 HP          │  ← Active bonus (green)
│  ✓ Taunt duration +1          │
│  ○ +8 Armor, +80 HP          │  ← Inactive bonus (gray)
│  ○ Bulwark grants +4 thorns   │
```

### Item Comparison

When hovering an item with one equipped in the same slot, show stat delta:

```
┌──── EQUIPPED ────┬──── COMPARING ────┐
│  Iron Mace       │  Doomcleaver      │
│  +8 Melee        │  +12 Melee (+4) ▲ │
│                  │  +7% Crit (new) ▲ │
│                  │  +3 LoH (new) ▲   │
│  +0 HP           │  +40 HP (+40) ▲   │
└──────────────────┴───────────────────┘
```

Green ▲ = upgrade, Red ▼ = downgrade, Yellow ● = new stat not on current item.

### Ground Loot Visuals

| Rarity | Ground Effect |
|--------|---------------|
| Common | Small gray sparkle (existing) |
| Magic | Blue sparkle, slight pulse |
| Rare | Yellow sparkle, moderate pulse, subtle beam |
| Epic | Purple sparkle, strong pulse, visible beam |
| Unique | Orange sparkle, bright beam, screen-edge notification |
| Set | Green sparkle, bright beam, screen-edge notification |

### Rarity-Colored Names Everywhere

All item name display points use rarity coloring:
- Inventory grid
- Equipment slots
- Loot popup (Phase 15 loot overhaul)
- Ground item labels (ALT-to-show)
- Merchant UI
- Combat log ("Player picked up **Doomcleaver**" in yellow)
- Post-match run summary

### "Item Dropped" Notification

When a Rare+ item drops on screen, show a brief notification:

```
┌─────────────────────────────┐
│  ★ RARE ITEM DROPPED ★      │
│  Doomcleaver                 │
│  Greatsword · Floor 5        │
└─────────────────────────────┘
```

Fades after 3 seconds. Epic/Unique/Set notifications are larger and persist longer.

### Files Changed

| File | Changes |
|------|---------|
| `client/src/utils/itemUtils.js` | `formatStatBonuses()` for all new stats; `compareItems()` utility; `getRarityColor()` |
| `client/src/components/Inventory/ItemTooltip.jsx` | **NEW** or refactored — full tooltip with affixes, set bonuses, comparison |
| `client/src/components/Inventory/EquipmentPanel.jsx` | 5-slot grid with rarity borders |
| `client/src/canvas/overlayRenderer.js` | Rarity-specific ground effects (beams, glows) |
| `client/src/components/HUD/LootNotification.jsx` | **NEW** — rare+ drop notification component |
| `client/src/styles/components/_inventory.css` | Rarity color borders, tooltip styling |
| `client/src/styles/base/_variables.css` | All rarity color CSS variables |

### Tests

- Tooltip renders all stat types correctly
- Set bonus tooltip shows active/inactive correctly
- Item comparison shows correct +/− delta
- Rarity colors match spec for all 6 tiers
- Loot notification triggers for Rare+ drops only
- Ground loot visuals scale with rarity

### 16G Implementation Log

**Status:** ✅ Complete  
**Server tests:** 2100 passed (0 regressions — client-only phase)

#### Files Created

| File | Purpose |
|------|---------|
| `client/src/components/Inventory/ItemTooltip.jsx` | Standalone Diablo-style tooltip — rarity-colored name, base type + item level, base stats (gray) vs affix stats (blue), set bonus section with active/inactive indicators (✓/○), item comparison panel (▲ up / ▼ down / new / lost), sell value, flavor text |
| `client/src/components/HUD/LootNotification.jsx` | Rare+ drop notification — auto-fade timer per rarity tier, high-tier (epic/unique/set) enlarged, click-to-dismiss, slide-in animation |

#### Files Modified

| File | Changes |
|------|---------|
| `client/src/utils/itemUtils.js` | Added `STAT_DEFINITIONS` (20 stats with key/label/format), `compareItems()` returning deltas with direction, `formatItemStatSections()` separating base vs affix stats, `isNotableRarity()`, `RARITY_NOTIFICATION_CONFIG` (duration/icon/label per tier), exported `RARITY_COLORS`, added `formatStatValue()` helper |
| `client/src/components/Inventory/Inventory.jsx` | Replaced inline ItemTooltip with new standalone import; passes `equippedItem` prop for comparison (bag items compare against equipped item in same slot) |
| `client/src/canvas/overlayRenderer.js` | Rewrote `drawGroundItems()` with 4-tier rarity-scaled ground effects: (1) All rarities get tile glow with scaling intensity/pulse, (2) Rare → subtle beam (4px, 1.5× height), (3) Epic → visible beam + outer glow + base pulse (5px, 2×), (4) Unique/Set → bright beam + wide outer glow + core pulse (6px, 2.5×). Common sparkle recolored from gold to gray |
| `client/src/styles/components/_inventory.css` | ~150 lines new CSS: tooltip ilvl, base-stats/affix-stats sections, separator, set-bonus-section, comparison rows (up/down/new/lost colors), loot-notification-container (fixed top-right z-700), per-rarity notification styles, fade transition, slideIn keyframes |
| `client/src/components/Arena/Arena.jsx` | Added LootNotification import + `isNotableRarity` import, `lootNotifications` state + `lootNotifIdRef`, useEffect watching `groundItems` to detect new Rare+ drops, `handleDismissLootNotif` callback, rendered `<LootNotification>` in JSX |

#### Design Decisions

1. **Loot notifications as local Arena state** — not a global reducer entry. They are ephemeral visual elements with no persistence or server round-trip.
2. **Ground item detection via `groundItems` diffing** — a `prevGroundItemsRef` tracks previous state; on change, new items are identified by `instance_id` match (or fallback to `item_id` + `name`), and Rare+ items generate notifications.
3. **4-tier beam system** — Common/Magic get tile glow only; Rare adds a subtle beam; Epic adds a visible beam with outer glow; Unique/Set get bright beam with pulsing core. This ensures players can visually distinguish rarity at a glance on the game grid.
4. **ItemTooltip extracted as standalone component** — reusable across Inventory, future Town shops, and trade UIs (Phase 16 Open Question #2).

---

## 16H — Balance & Tuning Pass

**Effort:** Medium  
**Risk:** Low — tuning numbers, not architecture  
**Prerequisite:** All of 16A–16G (final pass after everything is in)

### Stat Budget Guidelines

Each rarity tier has a **stat budget** — the total "power points" an item should provide:

| Rarity | Stat Budget | Example |
|--------|-------------|---------|
| Common | 5–10 pts | +8 melee (8 pts) |
| Magic | 10–20 pts | +8 melee (8 pts) + 4% crit (8 pts) = 16 pts |
| Rare | 20–35 pts | 4 affixes totaling ~28 pts |
| Epic | 35–50 pts | 5 affixes totaling ~42 pts |
| Unique | 40–60 pts | Curated to be strong but not strictly BiS for every build |
| Set (per piece) | 25–35 pts | Individually weaker than Rare, but set bonus adds ~20+ pts |

### Stat Point Equivalencies

To balance cross-stat items, define exchange rates:

| Stat | Points per Unit |
|------|----------------|
| +1 melee/ranged damage | 1 pt |
| +1 armor | 1.5 pt |
| +10 max HP | 2 pt |
| +1% crit chance | 2 pt |
| +10% crit damage | 1.5 pt |
| +1% dodge | 2 pt |
| +1% damage reduction | 2.5 pt |
| +1 hp regen | 1.5 pt |
| +1 move speed | 5 pt |
| +1 life on hit | 2 pt |
| +1% CDR | 2 pt |
| +1% skill damage | 1.5 pt |
| +1 thorns | 1 pt |
| +1% gold find | 0.5 pt |
| +1% magic find | 1 pt |
| +1% holy/dot/heal | 1.5 pt |
| +1 armor pen | 2 pt |

### Stat Caps

Hard caps prevent degenerate stacking:

| Stat | Hard Cap | Reasoning |
|------|----------|-----------|
| Crit Chance | 50% | Beyond 50%, every other hit crits — too deterministic |
| Crit Damage | 300% (3.0×) | Higher makes crits one-shot everything |
| Dodge Chance | 40% | Beyond 40%, melee enemies become non-threats |
| Damage Reduction % | 50% | Can't reduce damage by more than half |
| CDR | 30% | Skills should always have meaningful cooldowns |
| Move Speed | +2 tiles | More than +2 breaks the tactical movement game |
| Magic Find | 60% | Prevents farming gear from trivializing rarity progression |

### Thorns Scaling Concern

Thorns could become oppressive on tanky Crusaders (high HP, high armor, high thorns = you can't attack them without killing yourself). **Cap thorns at 12** and make thorns damage subject to the attacker's armor.

### Armor Rework Consideration

The existing flat armor system creates extreme results at high values (16+ armor from Crusader + Bulwark makes most attacks deal minimum damage). Phase 16's `damage_reduction_pct` and `armor_pen` partially address this, but a full armor rework could be considered:

```
Option A (keep flat + add % DR): Current plan. Flat armor + percentage DR stack.
  Good: Simple, backward compatible. % DR handles what flat can't.
  Risk: Very high flat armor still walls low-damage sources.

Option B (convert to diminishing returns): armor / (armor + K)
  Good: Smooth scaling, no hard walls.
  Risk: Requires rebalancing ALL armor values on ALL items and classes.

Recommendation: Ship with Option A (16A's plan). If flat armor proves problematic
with the new stat ecosystem, convert to Option B in a future balance patch.
```

### Post-Implementation Testing Plan

1. **Solo dungeon run testing** — run 20 full dungeon clears, catalog every item drop
2. **RNG distribution audit** — statistical tests on affix value distributions
3. **Power curve check** — compare floor 1 party vs. floor 8 fully-geared party
4. **Class balance with gear** — ensure no class is strictly BiS for all item slots
5. **Set bonus testing** — verify 2/3 and 3/3 bonuses feel impactful but not required
6. **Unique balance** — verify uniques are exciting but not mandatory
7. **Magic Find feedback loop** — ensure MF gear creates genuine "DPS vs MF" tension
8. **Economy check** — gold costs, sell values, merchant pricing feel balanced

---

## Implementation Timeline (Recommended)

| Sub-Phase | Description | Effort | Dependencies |
|-----------|-------------|--------|--------------|
| **16A** | Stat Expansion | ~3 sessions | Phase 15 complete |
| **16B** | Affix System & Item Generation | ~4 sessions | 16A |
| **16C** | Rarity Overhaul & Item Tiers | ~2 sessions | 16B |
| **16F** | Equipment Slot Expansion | ~2 sessions | 16A (can parallel with 16B) |
| **16D** | Unique Items | ~2 sessions | 16C |
| **16E** | Set Items | ~3 sessions | 16C |
| **16G** | Client UI & Loot Presentation | ~3 sessions | 16B |
| **16H** | Balance & Tuning Pass | ~2 sessions | 16A–16G complete |
| | **Total** | **~21 sessions** | |

### Recommended Execution Order

```
Week 1–2:  16A (Stat Expansion) — the foundation
Week 2–3:  16B (Affix System) — the heart of the overhaul
Week 3:    16C (Rarity Overhaul) + 16F (Slot Expansion) — in parallel
Week 4:    16D (Uniques) + 16E (Sets) — content authoring
Week 5:    16G (Client UI) — visual polish
Week 5–6:  16H (Balance Pass) — final tuning
```

---

## Summary: Before vs. After

| Aspect | Before (Phase 15) | After (Phase 16) |
|--------|-------------------|-------------------|
| Stats | 4 (`melee`, `ranged`, `armor`, `max_hp`) | 20 (+ crit, dodge, CDR, life on hit, thorns, MF, etc.) |
| Rarity tiers | 3 (Common, Uncommon, Rare) | 6 (Common, Magic, Rare, Epic, Unique, Set) |
| Item uniqueness | Static — every copy identical | Every drop is unique (random affixes) |
| Equip slots | 3 (weapon, armor, accessory) | 5 (+ helmet, boots) |
| Total base item types | ~29 | ~53 (+ 12 helmets/boots, + 12 new base types) |
| Unique items | 0 | 16 (hand-curated chase items) |
| Set items | 0 | 15 (5 class-themed sets × 3 pieces) |
| Affix system | None | 31 affixes (16 prefix, 15 suffix) |
| Build diversity | "Equip highest numbers" | Crit builds, sustain builds, MF builds, CDR builds, tank builds, etc. |
| GG item potential | None — every item is known | Infinite — the perfect Rare with ideal affixes is the endgame chase |
| Damage formula | `base − armor` | Crit, dodge, armor pen, % DR, life on hit, thorns, skill scaling |

---

## Open Questions

1. **Class-restricted items?** Should some items require a specific class to equip? (e.g., "Crusader Only" weapons) — Currently deferred. Any class can wear anything, but Set items are *designed* for specific classes via their bonuses.

2. **Item trading between players?** In co-op (Phase 15G–H), can players trade items? If so, this needs a trade UI and server validation.

3. **Inventory expansion?** 10 slots with 5 equipment slots means only 5 free bag spaces. Consider expanding to 15–20 slots, or adding a "stash" tab.

4. **Item socketing?** A future phase could add gem sockets to items for even more customization. Deferred — the affix system provides enough depth for now.

5. **Enchanting/rerolling?** A gold sink that lets players reroll one affix on a Rare+ item. Very Diablo 3. Good candidate for post-16 polish.
