# Phase 21 — Bard Class (Offensive Support / Battle Hymn)

**Created:** March 2026  
**Status:** Phase 21G Complete (Sprite Integration)  
**Previous:** Phase 20 (Turn Resolver File Split)  
**Goal:** Add the Bard as the game's first offensive support class, introducing party-wide damage buffs, enemy debuffs, cooldown reduction, and AoE crowd control. Fills the critical gap between the Confessor (defensive support) and DPS classes.

---

## Overview

The Bard is a grimdark war-poet who sings dark hymns and battle chants to empower allies and demoralize enemies. Where the Confessor keeps the party **alive**, the Bard makes the party **lethal**. Support through offense, not defense.

**Role:** Offensive Support / Debuffer

### Design Pillars

1. **Force multiplier** — The Bard's value comes from amplifying the entire party's output
2. **Offensive support** — Buffs team damage, debuffs enemy defense, accelerates cooldowns
3. **Distinct from Confessor** — Confessor heals/shields; Bard empowers/weakens
4. **Moderate self-sufficiency** — Decent hybrid stats; Cacophony for self-peel; not helpless solo
5. **Grimdark tone** — War dirges, battle hymns, cacophonous shrieks — not happy tavern songs

---

## Base Stats

| Stat | Value | Rationale |
|------|-------|-----------|
| **HP** | 90 | Between Confessor (100) and Ranger (80) — moderate survivability |
| **Melee Damage** | 10 | Decent melee, same as Inquisitor — can hold their own |
| **Ranged Damage** | 10 | Moderate ranged; balanced hybrid baseline |
| **Armor** | 3 | Same as Confessor — light armor, relies on positioning |
| **Vision Range** | 7 | Standard — not a scout, not blind |
| **Ranged Range** | 4 | Medium range — needs to stay near the action to buff allies |
| **Allowed Weapons** | Caster, Hybrid | Lutes, wands, hybrid instruments |
| **Color** | `#d4a017` | Deep gold/amber — distinct from Confessor's bright yellow (#f0e060) |
| **Shape** | Crescent | Unique — suggests a lute or sound wave |

### Stat Comparison (All Classes)

```
                  HP    Melee  Ranged  Armor  Vision  Range  Role
 Crusader ....   150      20       0      8       5      0   Tank
 Confessor ...   100       8       0      3       6      0   Defensive Support
 Inquisitor ..    80      10       8      4       9      5   Scout
 Ranger ......    80       8      18      2       7      6   Ranged DPS
 Hexblade ....   110      15      12      5       6      4   Hybrid DPS
 Mage ........    70       6      14      1       7      5   Caster DPS
 BARD ........    90      10      10      3       7      4   Offensive Support
```

**Design notes:**
- HP 90 is 7th-class median — survives longer than Mage/Ranger/Inquisitor, falls before Confessor/Hexblade/Crusader
- Melee 10 + Ranged 10 = jack-of-all-trades, master of none
- Armor 3 matches Confessor (support peers)
- Range 4 forces the Bard to position mid-line (not safely at max range like Ranger)

### Auto-Attack Damage (1.15× multiplier)

```
 Bard ........ 10 × 1.15 = 11.5 ranged per hit (range 4)
              10 × 1.15 = 11.5 melee per hit (if adjacent)
```

Lowest auto-attack DPS of any non-Confessor class. Intentional — the Bard's value is buffs, not personal damage.

---

## Skills

### Skill Overview

| Slot | Skill | Effect Type | Target | Range | Cooldown | Summary |
|:----:|-------|------------|--------|:-----:|:--------:|---------|
| 0 | Auto Attack (Ranged) | ranged_damage | entity | 4 | 0 | 1.15× ranged damage |
| 1 | Ballad of Might | aoe_buff (**NEW**) | self AoE (r=3) | — | 6 | +30% damage to allies in radius |
| 2 | Dirge of Weakness | aoe_debuff (**NEW**) | ground AoE (r=2) | 4 | 7 | Enemies take +25% damage |
| 3 | Verse of Haste | cooldown_reduction (**NEW**) | ally_or_self | 4 | 6 | Reduce target's cooldowns by 2 |
| 4 | Cacophony | aoe_damage_slow (existing) | self AoE (r=2) | — | 6 | 10 dmg + 2-turn slow |

### Skill Details

#### Ballad of Might 🎵 (AoE Ally Damage Buff)

```
Effect Type:   aoe_buff (NEW)
Targeting:     self (centered AoE)
Radius:        3 tiles
Cooldown:      6 turns
LOS Required:  No
Effect:        All allies within 3 tiles gain +30% melee AND ranged damage for 3 turns
```

**Design:** The Bard's signature move. Stay near your Crusader and Hexblade, sing Ballad of Might, and their next attacks hit significantly harder.

**Damage amplification examples (3-turn buff):**
```
 Crusader auto: 23 → 30 (+7/hit, +21 over 3 turns)
 Hexblade auto: 17 → 22 (+5/hit, +15 over 3 turns)
 Ranger auto:   21 → 27 (+6/hit, +18 over 3 turns)
 Mage auto:     16 → 21 (+5/hit, +15 over 3 turns)
```

**Implementation:** Clone of `resolve_aoe_heal` pattern — iterate allies in radius, apply buff entry `{stat: "all_damage_multiplier", magnitude: 1.3, turns_remaining: 3}` to each.

**Balance lever:** Buff magnitude (30%), duration (3 turns), radius (3), cooldown (6).

---

#### Dirge of Weakness 💀 (AoE Enemy Debuff)

```
Effect Type:   aoe_debuff (NEW)
Targeting:     ground_aoe (click tile)
Radius:        2 tiles
Range:         4 tiles
Cooldown:      7 turns
LOS Required:  Yes
Effect:        All enemies within 2 tiles of target take +25% more damage for 3 turns
```

**Design:** The offensive counterpart to Ballad of Might. Instead of buffing allies, curse enemies to be more vulnerable. Drop it on a champion pack and the entire party shreds them.

**Effective damage increase (party of 4 hitting debuffed targets):**
```
 Crusader 23 → 29 (+6)
 Hexblade 17 → 21 (+4)
 Ranger   21 → 26 (+5)
 Mage     16 → 20 (+4)
 Total: +19 extra damage per team turn × 3 turns = +57 bonus team damage
```

**Implementation:** Clone of `resolve_aoe_damage` targeting pattern — iterate enemies in radius of target tile, apply debuff entry `{type: "debuff", stat: "damage_taken_multiplier", magnitude: 1.25, turns_remaining: 3}`.

**Balance lever:** Vulnerability magnitude (25%), duration (3 turns), radius (2), range (4), cooldown (7).

---

#### Verse of Haste ⏩ (Cooldown Reduction)

```
Effect Type:   cooldown_reduction (NEW)
Targeting:     ally_or_self
Range:         4 tiles
Cooldown:      6 turns
LOS Required:  No
Effect:        Reduce all of target's active skill cooldowns by 2 turns instantly
```

**Design:** Unique utility no other class offers. Used on the Confessor? Their Heal comes back 2 turns sooner. Used on the Mage? Fireball is ready 2 turns early = +28 bonus damage.

**High-value targets for Verse of Haste:**
```
 Mage:       Fireball back 2 turns early → +28 bonus damage
 Ranger:     Power Shot back 2 turns early → +32 bonus damage
 Crusader:   Taunt back 2 turns early → survival utility
 Confessor:  Heal back 2 turns early → +30 HP party sustain
 Hexblade:   Wither/Ward refreshed → +16 DoT or defensive uptime
```

**Implementation:** New `resolve_cooldown_reduction` handler — find ally target (reuse ally_or_self pattern from `resolve_buff`), iterate `target.skill_cooldowns`, subtract 2 from each (min 0).

**Balance lever:** Cooldown reduction amount (2 turns), range (4), self cooldown (6).

---

#### Cacophony 🔊 (AoE Damage + Slow)

```
Effect Type:   aoe_damage_slow (EXISTING — same as Frost Nova)
Targeting:     self (centered AoE)
Radius:        2 tiles
Cooldown:      6 turns
LOS Required:  No
Effect:        Deal 10 flat damage to all enemies in radius + slow for 2 turns
```

**Design:** The Bard's only real offensive ability and emergency self-peel. Mechanically identical to Mage's Frost Nova but tuned weaker (10 damage vs 12) since the Bard isn't a DPS class. The slow is the real value — lets the Bard escape melee threats or set up allies for kills.

**Implementation:** Reuses existing `resolve_aoe_damage_slow` handler. No new code needed — just a config entry.

**Balance lever:** Flat damage (10), slow duration (2 turns), radius (2), cooldown (6).

---

### Complete Bard Kit

```
Slot 0: Auto Attack (Ranged) — 11.5 dmg, range 4
Slot 1: Ballad of Might — AoE +30% damage to allies in radius 3, 3 turns, CD 6
Slot 2: Dirge of Weakness — AoE enemies take +25% more damage, radius 2, CD 7
Slot 3: Verse of Haste — Reduce ally's cooldowns by 2, range 4, CD 6
Slot 4: Cacophony — 10 AoE damage + 2-turn slow, self radius 2, CD 6
```

---

## DPS Contribution Analysis

### Direct DPS (Personal)

```
 Auto-attack only: 11.5 per turn (lowest non-Confessor in game)
 Cacophony: 10 AoE damage, CD 6 → 1.7 DPS equivalent (per target)
```

The Bard's personal DPS is intentionally low.

### Team DPS Amplification (The Real Value)

**Scenario: 4-person party (Crusader + Hexblade + Ranger + Bard) vs boss**

Without Bard buffs:
```
 Crusader:  23/turn
 Hexblade:  17/turn
 Ranger:    21/turn
 Team DPS:  61/turn (excluding Bard's 11.5)
```

With Ballad of Might active (+30%):
```
 Crusader:  30/turn (+7)
 Hexblade:  22/turn (+5)
 Ranger:    27/turn (+6)
 Team DPS:  79/turn (+18/turn for 3 turns = +54 bonus damage)
```

With Dirge of Weakness on boss (+25% damage taken):
```
 All incoming: ×1.25
 Team DPS:     79 × 1.25 = 99/turn (+38 over unbuffed)
```

With BOTH Ballad + Dirge active (multiplicative):
```
 Team DPS:  61 × 1.30 × 1.25 = 99/turn (vs 61 unbuffed = +62% total team increase)
```

**Net: The Bard contributes more effective damage through buffs/debuffs than any DPS class contributes personally.** This is the intended design — the Bard is useless solo but invaluable in a party.

### Verse of Haste Value

Accelerating a Mage's Fireball by 2 turns = +28 damage  
Accelerating a Ranger's Power Shot by 2 turns = +32 damage  
**Better than any single auto-attack in the game.**

---

## AI Behavior (offensive_support role)

### New AI Role: `offensive_support`

The Bard AI uses a **backline buffer** strategy, staying near allies and prioritizing team empowerment:

### Decision Priority

```
1. Ballad of Might   → if 1+ ally within radius 3, off cooldown
2. Dirge of Weakness  → if 2+ enemies clustered (within radius 2 of a tile), off cooldown
3. Verse of Haste     → on the ally with the highest-value skill on cooldown, off cooldown
4. Cacophony          → if enemy adjacent (self-peel emergency)
5. Auto-attack        → fallback, target nearest enemy in range
```

### Positioning

- Reuses `_support_move_preference()` — stay 2-3 tiles behind frontline, near allies
- Does NOT charge enemies; follows the party
- Retreats if adjacent to enemy and Cacophony is on cooldown

### Verse of Haste Target Selection (AI Logic)

```python
# Score each ally by: sum of (remaining cooldown) for each skill with cooldown > 2
# Pick ally with highest total cooldown score (most "wasted" potential)
# Tiebreaker: prioritize DPS classes > support > tank
```

---

## New Effect Types

### Summary

| Effect Type | Complexity | Based On | Handler |
|-------------|-----------|----------|---------|
| `aoe_buff` | Low | `resolve_aoe_heal` pattern | `resolve_aoe_buff()` |
| `aoe_debuff` | Low | `resolve_aoe_damage` targeting + debuff | `resolve_aoe_debuff()` |
| `cooldown_reduction` | Low | `resolve_buff` ally targeting | `resolve_cooldown_reduction()` |

`Cacophony` reuses the **existing** `aoe_damage_slow` type. No new code needed for that skill.

### Effect Type Details

#### `aoe_buff` — AoE Ally Buff (Ballad of Might)

```python
def resolve_aoe_buff(player, skill_def, players):
    """AoE buff centered on self — apply buff to all allies in radius.
    Mirrors resolve_aoe_heal but applies a buff entry instead of healing."""
    radius = effect["radius"]
    stat = effect["stat"]           # "all_damage_multiplier"
    magnitude = effect["magnitude"] # 1.3
    duration = effect["duration_turns"]  # 3

    for ally in allies_in_radius:
        ally.active_buffs.append({
            "buff_id": skill_id, "type": "buff",
            "stat": stat, "magnitude": magnitude,
            "turns_remaining": duration,
        })
```

#### `aoe_debuff` — AoE Enemy Debuff (Dirge of Weakness)

```python
def resolve_aoe_debuff(player, action, skill_def, players, obstacles):
    """AoE debuff at target tile — apply debuff to all enemies in radius.
    Targeting like resolve_aoe_damage, buff application like resolve_buff."""
    # Validate range + LOS to target tile
    # Iterate enemies within radius of (target_x, target_y)
    for enemy in enemies_in_radius:
        enemy.active_buffs.append({
            "buff_id": skill_id, "type": "debuff",
            "stat": "damage_taken_multiplier",
            "magnitude": magnitude,   # 1.25
            "turns_remaining": duration,
        })
```

#### `cooldown_reduction` — Ally Cooldown Reduction (Verse of Haste)

```python
def resolve_cooldown_reduction(player, action, skill_def, players, target_id):
    """Reduce all active cooldowns on target ally by N turns.
    Ally targeting reuses resolve_buff's ally_or_self pattern."""
    reduction = effect["reduction"]  # 2
    for skill_id_key, remaining in target.skill_cooldowns.items():
        if remaining > 0:
            target.skill_cooldowns[skill_id_key] = max(0, remaining - reduction)
```

### Buff System Integration: `damage_taken_multiplier`

The `damage_taken_multiplier` debuff (from Dirge of Weakness) needs to be checked in the damage resolution path:

**In `combat.py` — `calculate_damage` and `calculate_ranged_damage`:**
```python
# After calculating base damage, before returning:
damage_taken_mult = get_damage_taken_multiplier(target)  # checks active_buffs for debuffs
final_damage = max(1, int(raw_damage * damage_taken_mult))
```

**In `skills.py` — all damage handlers (melee, ranged, magic, holy, aoe):**
```python
# Same pattern — apply target's damage_taken_multiplier
```

### Buff System Integration: `all_damage_multiplier`

The `all_damage_multiplier` buff (from Ballad of Might) is checked when calculating damage output:

**In `skills.py` — `get_melee_buff_multiplier` and `get_ranged_buff_multiplier`:**
```python
# Add: check for all_damage_multiplier buff
for buff in player.active_buffs:
    if buff.get("stat") == "all_damage_multiplier":
        multiplier *= buff["magnitude"]
```

---

## Implementation Phases

### Phase 21A — Config & Data Model (Foundation)

**Goal:** Add Bard to classes and skills configs. Wire up the data layer.

**Files Modified:**
| File | Change |
|------|--------|
| `server/configs/classes_config.json` | Add `bard` class definition |
| `server/configs/skills_config.json` | Add 4 Bard skills + `class_skills.bard` mapping |

**Config: `classes_config.json`**
```json
"bard": {
  "class_id": "bard",
  "name": "Bard",
  "role": "Offensive Support",
  "description": "War-poet who empowers allies with battle hymns and debilitates enemies with dark dirges.",
  "base_hp": 90,
  "base_melee_damage": 10,
  "base_ranged_damage": 10,
  "base_armor": 3,
  "base_vision_range": 7,
  "ranged_range": 4,
  "allowed_weapon_categories": ["caster", "hybrid"],
  "color": "#d4a017",
  "shape": "crescent"
}
```

**Config: `skills_config.json`** — 4 new skills:
```json
"ballad_of_might": {
  "skill_id": "ballad_of_might",
  "name": "Ballad of Might",
  "description": "Sing a war hymn — all allies within 2 tiles gain +30% melee and ranged damage for 3 turns.",
  "icon": "🎵",
  "targeting": "self",
  "range": 0,
  "cooldown_turns": 6,
  "mana_cost": 0,
  "effects": [{
    "type": "aoe_buff",
    "radius": 2,
    "stat": "all_damage_multiplier",
    "magnitude": 1.3,
    "duration_turns": 3
  }],
  "allowed_classes": ["bard"],
  "requires_line_of_sight": false
},
"dirge_of_weakness": {
  "skill_id": "dirge_of_weakness",
  "name": "Dirge of Weakness",
  "description": "Chant a dirge of doom — all enemies within 2 tiles of target take 25% more damage for 3 turns.",
  "icon": "💀",
  "targeting": "ground_aoe",
  "range": 4,
  "cooldown_turns": 7,
  "mana_cost": 0,
  "effects": [{
    "type": "aoe_debuff",
    "radius": 2,
    "stat": "damage_taken_multiplier",
    "magnitude": 1.25,
    "duration_turns": 3
  }],
  "allowed_classes": ["bard"],
  "requires_line_of_sight": true
},
"verse_of_haste": {
  "skill_id": "verse_of_haste",
  "name": "Verse of Haste",
  "description": "Accelerate an ally's recovery — reduce all skill cooldowns by 2 turns.",
  "icon": "⏩",
  "targeting": "ally_or_self",
  "range": 3,
  "cooldown_turns": 6,
  "mana_cost": 0,
  "effects": [{
    "type": "cooldown_reduction",
    "reduction": 2
  }],
  "allowed_classes": ["bard"],
  "requires_line_of_sight": false
},
"cacophony": {
  "skill_id": "cacophony",
  "name": "Cacophony",
  "description": "Unleash a deafening shriek — deal 10 damage and slow all enemies within 2 tiles for 2 turns.",
  "icon": "🔊",
  "targeting": "self",
  "range": 0,
  "cooldown_turns": 6,
  "mana_cost": 0,
  "effects": [{
    "type": "aoe_damage_slow",
    "radius": 2,
    "base_damage": 10,
    "slow_duration": 2
  }],
  "allowed_classes": ["bard"],
  "requires_line_of_sight": false
}
```

**`class_skills` mapping:**
```json
"bard": ["auto_attack_ranged", "ballad_of_might", "dirge_of_weakness", "verse_of_haste", "cacophony"]
```

**Tests (Phase 21A):**
- Bard class loads from config
- All 4 skills load from config
- `class_skills["bard"]` maps correctly
- `can_use_skill()` validates Bard skills for bard class
- `can_use_skill()` rejects Bard skills for non-bard classes

**Estimated tests:** 8–10

---

### Phase 21B — New Effect Handlers (Core Mechanics)

**Goal:** Implement the 3 new effect type handlers and wire them into `resolve_skill_action`.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/skills.py` | Add `resolve_aoe_buff()`, `resolve_aoe_debuff()`, `resolve_cooldown_reduction()` |
| `server/app/core/skills.py` | Add 3 new branches to `resolve_skill_action()` dispatcher |

#### Handler 1: `resolve_aoe_buff()` (~40 lines)

```
Input:  player, skill_def, players
Logic:  1. Get radius, stat, magnitude, duration from effects[0]
        2. Iterate all alive allies on same team within Chebyshev radius
        3. Append buff entry to each ally's active_buffs
        4. Apply skill cooldown
Output: ActionResult with success message listing buffed allies
```

**Buff entry format:**
```json
{
  "buff_id": "ballad_of_might",
  "type": "buff",
  "stat": "all_damage_multiplier",
  "magnitude": 1.3,
  "turns_remaining": 3
}
```

#### Handler 2: `resolve_aoe_debuff()` (~60 lines)

```
Input:  player, action (target_x, target_y), skill_def, players, obstacles
Logic:  1. Validate range from player to target tile (Chebyshev)
        2. Validate LOS from player to target tile (if required)
        3. Get radius, stat, magnitude, duration from effects[0]
        4. Iterate all alive enemies (different team) within radius of target tile
        5. Append debuff entry to each enemy's active_buffs
        6. Apply skill cooldown
Output: ActionResult with success message listing debuffed enemies
```

**Debuff entry format:**
```json
{
  "buff_id": "dirge_of_weakness",
  "type": "debuff",
  "stat": "damage_taken_multiplier",
  "magnitude": 1.25,
  "turns_remaining": 3
}
```

#### Handler 3: `resolve_cooldown_reduction()` (~50 lines)

```
Input:  player, action (target_x, target_y), skill_def, players, target_id
Logic:  1. Resolve target (ally_or_self, reuse pattern from resolve_buff)
        2. Validate range from player to target (Chebyshev)
        3. Get reduction amount from effects[0]
        4. Iterate target.skill_cooldowns, subtract reduction (min 0)
        5. Count how many cooldowns were actually reduced
        6. Apply skill cooldown to caster
Output: ActionResult with success message listing cooldowns accelerated
```

#### Dispatcher Update

Add 3 new branches to `resolve_skill_action()`:
```python
elif effect_type == "aoe_buff":
    return resolve_aoe_buff(player, skill_def, players)
elif effect_type == "aoe_debuff":
    return resolve_aoe_debuff(player, action, skill_def, players, obstacles)
elif effect_type == "cooldown_reduction":
    return resolve_cooldown_reduction(player, action, skill_def, players, target_id=tid)
```

**Tests (Phase 21B):**

*Ballad of Might (aoe_buff):*
- Buff applies to all allies in radius 2
- Buff does NOT apply to enemies in radius
- Buff does NOT apply to dead allies
- Buff does NOT apply to allies outside radius (distance 3+)
- Bard receives own buff (self included as ally)
- Buff has correct stat, magnitude, duration
- Cooldown applied after use
- Multiple uses refresh (don't stack duplicate buffs)

*Dirge of Weakness (aoe_debuff):*
- Debuff applies to all enemies in radius 2 of target tile
- Debuff does NOT apply to allies
- Debuff does NOT apply to enemies outside radius
- Fails if target tile out of range (Chebyshev > 4)
- Fails if no LOS to target tile
- Debuff has correct stat, magnitude, duration
- Cooldown applied after use
- Debuff expires after 3 turns (via tick_buffs)

*Verse of Haste (cooldown_reduction):*
- Reduces all active cooldowns on target ally by 2
- Cooldowns don't go below 0
- Works on self
- Works on ally within range 3
- Fails if target out of range
- Fails if target is enemy (different team)
- Does nothing if target has no active cooldowns (still succeeds)
- Cooldown applied to caster after use

*Cacophony (existing aoe_damage_slow):*
- Already tested via Mage Frost Nova tests
- Add 1 test: Bard's Cacophony deals 10 damage (not 12 like Frost Nova)

**Estimated tests:** 25–30

---

### Phase 21C — Buff System Integration (damage_taken_multiplier + all_damage_multiplier)

**Goal:** Wire the new buff/debuff stats into the damage calculation pipeline so they actually affect combat.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/skills.py` | Update `get_melee_buff_multiplier()` and `get_ranged_buff_multiplier()` to check `all_damage_multiplier` |
| `server/app/core/skills.py` | Add `get_damage_taken_multiplier()` helper |
| `server/app/core/combat.py` | Apply `damage_taken_multiplier` in damage resolution |
| `server/app/core/turn_phases/combat_phase.py` | Apply multiplier in melee/ranged combat |
| `server/app/core/skills.py` | Apply multiplier in skill damage handlers |

#### `all_damage_multiplier` Integration

In `get_melee_buff_multiplier()` and `get_ranged_buff_multiplier()`:
```python
# Existing: checks melee_damage_multiplier / ranged_damage_multiplier
# Add: also check all_damage_multiplier
for buff in player.active_buffs:
    if buff.get("stat") == "all_damage_multiplier" and buff.get("type") == "buff":
        multiplier *= buff["magnitude"]
```

This is minimal — 4-5 lines added to 2 existing functions. All melee/ranged damage already calls these multiplier functions, so Ballad of Might works everywhere automatically.

#### `damage_taken_multiplier` Integration

New helper function:
```python
def get_damage_taken_multiplier(player: PlayerState) -> float:
    """Return the combined damage-taken multiplier from all active debuffs."""
    mult = 1.0
    for buff in player.active_buffs:
        if buff.get("stat") == "damage_taken_multiplier":
            mult *= buff["magnitude"]
    return mult
```

Apply in damage resolution (6 locations):
1. `combat.py` — `calculate_damage_simple()` (melee auto-attack)
2. `combat.py` — `calculate_ranged_damage_simple()` (ranged auto-attack)
3. `skills.py` — `resolve_multi_hit()` (Double Strike, etc.)
4. `skills.py` — `resolve_ranged_skill()` (Power Shot, etc.)
5. `skills.py` — `resolve_magic_damage()` (Fireball, etc.)
6. `skills.py` — `resolve_holy_damage()` (Rebuke, Exorcism)

Pattern at each location:
```python
# After calculating pre-armor damage:
dmg_taken_mult = get_damage_taken_multiplier(target)
final_damage = max(1, int(final_damage * dmg_taken_mult))
```

**Tests (Phase 21C):**

*all_damage_multiplier:*
- Melee auto-attack damage increased by 30% with Ballad active
- Ranged auto-attack damage increased by 30% with Ballad active
- Skill melee damage (Double Strike) increased by 30%
- Skill ranged damage (Power Shot) increased by 30%
- Magic damage (Fireball) increased by 30%
- Multiplier stacks with existing War Cry (multiplicative)
- Multiplier expires when buff ticks down to 0

*damage_taken_multiplier:*
- Target with Dirge takes 25% more melee damage
- Target with Dirge takes 25% more ranged damage
- Target with Dirge takes 25% more skill damage
- Target with Dirge takes 25% more magic damage
- Multiplier expires when debuff ticks down
- Multiplier stacks with Ballad (multiplicative)
- Minimum damage still 1

*Combined (Ballad + Dirge):*
- Attacker has Ballad (+30%), target has Dirge (+25%) → total = 1.3 × 1.25 = 1.625× damage
- Verify with concrete damage numbers

**Estimated tests:** 15–18

---

### Phase 21D — AI Behavior (offensive_support role)

**Goal:** Implement `offensive_support` AI role so Bard AI heroes and AI-controlled Bards make smart decisions.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/ai_skills.py` | Add `"bard": "offensive_support"` to `_CLASS_ROLE_MAP` |
| `server/app/core/ai_skills.py` | Add `_offensive_support_skill_logic()` function |
| `server/app/core/ai_skills.py` | Add `"offensive_support"` branch to dispatcher |

#### AI Decision Logic

```python
def _offensive_support_skill_logic(ai, enemies, all_units, grid_w, grid_h, obstacles):
    """Offensive support AI: buff allies → debuff enemies → reduce cooldowns → self-peel."""

    allies = [u for u in all_units.values()
              if u.is_alive and u.team == ai.team and u.player_id != ai.player_id]

    # 1. Ballad of Might — if 2+ allies in radius 2
    allies_in_range = [a for a in allies if chebyshev(ai, a) <= 2]
    if len(allies_in_range) >= 2 and can_use("ballad_of_might"):
        return skill_action("ballad_of_might", target=self)

    # 2. Dirge of Weakness — if 2+ enemies clustered
    best_tile = find_best_aoe_tile(enemies, radius=2, max_range=4)
    if best_tile and best_tile.count >= 2 and can_use("dirge_of_weakness"):
        return skill_action("dirge_of_weakness", target=best_tile)

    # 3. Verse of Haste — on ally with most wasted cooldown potential
    best_ally = max(allies_in_range_3, key=total_cooldown_score)
    if best_ally and best_ally.score > 2 and can_use("verse_of_haste"):
        return skill_action("verse_of_haste", target=best_ally)

    # 4. Cacophony — if enemy adjacent (self-peel)
    adjacent_enemies = [e for e in enemies if chebyshev(ai, e) <= 1]
    if adjacent_enemies and can_use("cacophony"):
        return skill_action("cacophony", target=self)

    # 5. Fallback — auto-attack
    return None
```

#### Positioning

Reuses existing `_support_move_preference()` — stays near allies, avoids frontline.

**Tests (Phase 21D):**
- Bard AI uses Ballad when 2+ allies in range
- Bard AI skips Ballad when fewer than 2 allies in range
- Bard AI uses Dirge on clustered enemies (2+)
- Bard AI uses Verse of Haste on ally with highest cooldown debt
- Bard AI uses Cacophony when enemy adjacent
- Bard AI falls back to auto-attack when all skills on cooldown
- Bard AI positioning stays behind frontline

**Estimated tests:** 8–12

---

### Phase 21E — Frontend Integration (Rendering + UI)

**Goal:** Add Bard to the client — shape rendering, class selection, colors, icons, inventory portrait.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/canvas/renderConstants.js` | Add bard to `CLASS_COLORS`, `CLASS_SHAPES`, `CLASS_NAMES` |
| `client/src/canvas/unitRenderer.js` | Add `crescent` shape rendering case |
| `client/src/components/WaitingRoom/WaitingRoom.jsx` | Add crescent icon to shape map (`☽`) |
| `client/src/components/Inventory/Inventory.jsx` | Add crescent SVG path to `CLASS_SHAPE_PATHS` |
| `client/src/components/Inventory/Inventory.jsx` | Add bard buff names to `formatBuffName` |

#### renderConstants.js additions

```javascript
// CLASS_COLORS
bard: '#d4a017',

// CLASS_SHAPES
bard: 'crescent',

// CLASS_NAMES
bard: 'Bard',
```

#### unitRenderer.js — Crescent Shape

```javascript
case 'crescent': {
  // Crescent moon / sound wave shape
  ctx.beginPath();
  ctx.arc(cx, ey, radius, 0.3 * Math.PI, 1.7 * Math.PI, false);
  ctx.arc(cx + radius * 0.35, ey, radius * 0.7, 1.7 * Math.PI, 0.3 * Math.PI, true);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  break;
}
```

#### WaitingRoom.jsx — Shape icon

Add `crescent` to the ternary chain:
```
cls.shape === 'crescent' ? '☽' : ...
```

#### Inventory.jsx — SVG portrait path

```javascript
crescent: <path d="M22,4 A13,13 0 1,1 22,28 A9,9 0 1,0 22,4 Z" />,
```

#### Inventory.jsx — Buff name formatting

Add to `formatBuffName`:
```javascript
ballad_of_might: 'Ballad of Might',
dirge_of_weakness: 'Dirge of Weakness',
verse_of_haste: 'Verse of Haste',
cacophony: 'Cacophony',
```

Add to `formatBuffEffect`:
```javascript
if (buff.stat === 'all_damage_multiplier') return `${((buff.magnitude - 1) * 100).toFixed(0)}% damage`;
if (buff.stat === 'damage_taken_multiplier') return `+${((buff.magnitude - 1) * 100).toFixed(0)}% damage taken`;
```

**Tests (Phase 21E):** Visual verification — no automated tests needed for rendering. Manual checklist:
- [ ] Bard appears in class selection screen
- [ ] Crescent shape renders on canvas
- [ ] Gold color (#d4a017) displays correctly
- [ ] Bard name shows in nameplate
- [ ] Inventory portrait shows crescent
- [ ] Buff/debuff icons display correctly in HUD
- [ ] Skill icons appear in bottom bar

---

### Phase 21F — Particle Effects & Audio (Polish)

**Goal:** Add visual and audio feedback for Bard skills.

**Files Modified:**
| File | Change |
|------|--------|
| `client/public/particle-presets/skills.json` | Add bard skill effects |
| `client/public/particle-presets/buffs.json` | Add ballad/dirge buff auras |
| `client/public/audio-effects.json` | Add bard audio triggers |
| `client/src/audio/soundMap.js` | Add bard sound mappings |

#### Particle Effects

| Skill | Particle Effect | Description |
|-------|----------------|-------------|
| Ballad of Might | `ballad-buff-pulse` | Gold expanding rings from Bard, gold sparkles on buffed allies |
| Dirge of Weakness | `dirge-debuff-cloud` | Purple-black miasma cloud on target area, dark wisps on debuffed enemies |
| Verse of Haste | `verse-haste-trail` | Blue-white streaks flowing from Bard to target ally |
| Cacophony | `cacophony-blast` | White/gold shockwave expanding from Bard (similar to Frost Nova ring) |

#### Audio

| Skill | Sound | Category |
|-------|-------|----------|
| Ballad of Might | Ascending chord, brass/horn swell | skills |
| Dirge of Weakness | Low droning chant, minor key | skills |
| Verse of Haste | Quick ascending harp arpeggio | skills |
| Cacophony | Harsh dissonant blast, like a warhorn | skills |

**Tests (Phase 21F):** Manual verification only.
- [ ] Each skill triggers correct particle effect
- [ ] Buff auras visible on affected units
- [ ] Audio plays on skill use

---

### Phase 21G — Sprite Integration (Optional)

**Goal:** Add Bard sprite variants from the character sheet atlas.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/canvas/SpriteLoader.js` | Add bard sprite variants |

*This phase depends on finding suitable sprites in the existing atlas. If no bard-appropriate sprites exist, the crescent shape fallback works perfectly.*

---

## Implementation Order & Dependencies

```
Phase 21A (Config)         ← No dependencies, pure data
    ↓
Phase 21B (Effect Handlers) ← Depends on 21A (needs skill definitions)
    ↓
Phase 21C (Buff Integration) ← Depends on 21B (needs buff entries to exist)
    ↓
Phase 21D (AI Behavior)     ← Depends on 21B (needs handlers working)
    ↓
Phase 21E (Frontend)        ← Depends on 21A (needs class config) — can parallel with 21C/21D
    ↓
Phase 21F (Polish)          ← Depends on 21E (needs rendering working)
    ↓
Phase 21G (Sprites)         ← Optional, last
```

**Parallelizable:** 21C + 21D can be done in parallel after 21B. 21E can start after 21A.

---

## Test Summary

| Phase | Test Count | Focus |
|-------|:----------:|-------|
| 21A — Config | 8–10 | Class/skill loading, validation |
| 21B — Effect Handlers | 25–30 | 3 new handlers, edge cases |
| 21C — Buff Integration | 15–18 | Damage multipliers in combat pipeline |
| 21D — AI Behavior | 8–12 | AI decision logic |
| 21E — Frontend | 0 (manual) | Visual verification |
| 21F — Polish | 0 (manual) | Particles, audio |
| **Total** | **56–70** | |

---

## Tuning Levers

These values are initial estimates and should be adjusted after playtesting:

| Parameter | Initial Value | Reduce If... | Increase If... |
|-----------|:------------:|--------------|----------------|
| Ballad damage buff | +30% | Team damage too high in parties | Bard feels low-impact |
| Ballad duration | 3 turns | Uptime too high (50% with CD 6) | Buff expires before meaningful use |
| Ballad radius | 3 | Too easy to buff entire party | Hard to position near enough allies |
| Dirge vulnerability | +25% | Stacking with Ballad too powerful | Debuff doesn't feel impactful |
| Dirge duration | 3 turns | — | Enemies die before debuff matters |
| Dirge cooldown | 7 turns | — | Feels too infrequent |
| Verse CD reduction | 2 turns | Too powerful on long-CD skills | Doesn't feel impactful |
| Cacophony damage | 10 | — | Bard can't self-peel effectively |
| Base HP | 90 | — | Dies too fast in PvE |
| Base ranged damage | 10 | — | Auto-attack feels useless |

### Known Balance Risks

1. **Ballad + Dirge stacking:** Combined 62.5% team damage increase may be too strong. Consider making them non-multiplicative (additive caps) if testing shows burst is too high.
2. **Verse of Haste on Mage:** Getting Fireball back 2 turns early is enormous. May need to cap reduction at 1 for high-cooldown skills, or make Verse CD 7+.
3. **Solo Bard:** Intentionally weak solo — 11.5 auto-attack with no burst. This is by design but may feel bad in solo PvE. Consider adding a stronger personal damage skill if solo play suffers.

---

## Future Enhancements (Post-Phase 21)

- **Bard-specific item affixes:** +song duration, +buff radius, +cooldown reduction power
- **Additional songs:** Battle March (+movement speed), Lullaby (AoE sleep), Requiem (AoE DoT)
- **Song-swapping mechanic:** Bard can only maintain 1 song at a time (toggle system)
- **Unique items:** Lute of the Damned (+15% song potency), War Drum (+1 buff radius)
- **Enemy Bard:** Dark Minstrel enemy type that debuffs players

---

## Phase Checklist

- [x] **21A** — Bard added to `classes_config.json`
- [x] **21A** — 4 skills added to `skills_config.json`
- [x] **21A** — `class_skills.bard` mapping added
- [x] **21A** — Config loading tests pass (51 tests)
- [x] **21B** — `resolve_aoe_buff()` implemented
- [x] **21B** — `resolve_aoe_debuff()` implemented
- [x] **21B** — `resolve_cooldown_reduction()` implemented
- [x] **21B** — `resolve_skill_action()` dispatcher updated
- [x] **21B** — All handler tests pass (40 tests)
- [x] **21C** — `all_damage_multiplier` integrated into buff multiplier functions
- [x] **21C** — `damage_taken_multiplier` integrated into damage pipeline
- [x] **21C** — `get_damage_taken_multiplier()` helper added to skills.py
- [x] **21C** — Buff integration tests pass (36 tests)
- [x] **21D** — `offensive_support` AI role implemented
- [x] **21D** — `_CLASS_ROLE_MAP` updated
- [x] **21D** — AI behavior tests pass (34 tests)
- [x] **21E** — `renderConstants.js` updated
- [x] **21E** — Crescent shape renders in `unitRenderer.js`
- [x] **21E** — WaitingRoom class select shows Bard
- [x] **21E** — Inventory portrait & buff names updated
- [x] **21F** — Particle effects added
- [x] **21F** — Audio triggers added
- [x] **21G** — Sprite variants mapped (Bard_1 + Mage_8 added to SpriteLoader)
- [x] Balance pass — song range tuning (March 2026)

---

## Dev Log

### March 7 2026 — Balance Pass: Song Range Tuning

**Problem:** During playtesting, Ballad of Might (radius 2) and Verse of Haste (range 3) were falling short when the tank/DPS pressed forward to chase enemies. The Bard AI uses `_support_move_preference()` which keeps it 2-3 tiles behind the frontline — with radius 2, allies at the front edge regularly fell outside buff range mid-combat.

**Changes:**

| Parameter | Before | After | Rationale |
|-----------|:------:|:-----:|----------|
| Ballad of Might radius | 2 | **3** | Self-centered AoE needs to cover allies who are naturally 2-3 tiles ahead. Radius 3 (7×7 Chebyshev) gives breathing room without being global. |
| Verse of Haste range | 3 | **4** | Matches Confessor's Prayer range. The Bard's most strategic single-target support skill needs margin for mid-combat positioning. |
| `_BALLAD_MIN_ALLIES` (AI) | 2 | **1** | A +30% buff on even one Crusader or Hexblade is high-value (+7/hit × 3 turns = +21 bonus damage). Requiring 2 allies caused the AI to skip Ballad too often in spread-out fights. |

**Files modified:**
- `server/configs/skills_config.json` — Ballad radius 2→3, Verse range 3→4
- `server/app/core/ai_skills.py` — `_BALLAD_MIN_ALLIES` 2→1

**Risk assessment:** Ballad radius 3 covers a 7×7 area — larger but still requires the Bard to be within 3 tiles of allies. Not global; positioning still matters. Verse range 4 matches existing support skill precedent (Confessor Prayer). Lowering Ballad AI threshold to 1 ally increases Ballad uptime but the buff itself is unchanged.

---

**Document Version:** 1.6  
**Created:** March 2026  
**Status:** Phase 21G Complete (Sprite Integration) — Balance tuning in progress  
**Prerequisites:** Phase 20 Complete
