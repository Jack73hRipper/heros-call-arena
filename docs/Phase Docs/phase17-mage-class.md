# Phase 17 — Mage Class (First Caster DPS)

**Created:** June 2026  
**Status:** Implementation Complete  
**Previous:** Phase 16G (Client UI & Loot Presentation)  
**Goal:** Add the Mage as the game's first pure caster DPS class, introducing the `magic_damage` damage type and establishing the template for future caster classes.

---

## Overview

The Mage is a glass-cannon caster who deals **area-of-effect magic damage** and controls space through slows and teleportation. Unlike existing physical damage classes, the Mage introduces the `magic_damage` type, which **bypasses 50% of enemy armor** — giving casters a distinct advantage against heavily-armored targets while remaining vulnerable to rushdown.

### Design Pillars

1. **Highest burst AoE in the game** — Fireball and Arcane Barrage punish clustered enemies
2. **Magic bypasses armor** — 50% armor effectiveness creates a distinct role vs. physical DPS
3. **Glass cannon** — Lowest HP (70) and armor (1) of any class; relies on positioning and Blink
4. **Kiting playstyle** — Ranger-style AI keeps distance; Frost Nova + Blink provide escape tools

---

## Base Stats

| Stat | Value | Notes |
|------|-------|-------|
| **HP** | 70 | Lowest in game (tied intent — fragile caster) |
| **Melee Damage** | 6 | Emergency only; weakest melee |
| **Ranged Damage** | 14 | Primary stat; used by Fireball & Arcane Barrage multipliers |
| **Armor** | 1 | Near-zero physical protection |
| **Vision Range** | 7 | Standard |
| **Ranged Range** | 5 | Same as Ranger; enables backline positioning |
| **Allowed Weapons** | Caster, Hybrid | Staff/wand category support for Phase 16 items |
| **Color** | `#e07020` | Warm orange — distinct from all existing class colors |
| **Shape** | Hexagon | Unique 6-sided shape; suggests arcane geometry |

### Stat Comparison

| Class | HP | Melee | Ranged | Armor | Range | Role |
|-------|---:|------:|-------:|------:|------:|------|
| Crusader | 150 | 20 | 0 | 8 | — | Tank |
| Confessor | 100 | 8 | 0 | 3 | — | Support |
| Inquisitor | 80 | 10 | 8 | 4 | 4 | Scout |
| Ranger | 80 | 4 | 18 | 2 | 5 | Ranged DPS |
| Hexblade | 110 | 15 | 12 | 5 | 3 | Hybrid DPS |
| **Mage** | **70** | **6** | **14** | **1** | **5** | **Caster DPS** |

---

## Skills

### Skill Overview

| Skill | Effect Type | Damage | Range | Cooldown | Target |
|-------|------------|--------|-------|----------|--------|
| Auto Attack (Ranged) | ranged_damage | 1.0× | 5 | 0 | entity |
| Fireball | magic_damage | 2.0× ranged | 5 | 5 | entity (LOS) |
| Frost Nova | aoe_damage_slow | 12 flat | radius 2 (self) | 6 | self_aoe |
| Arcane Barrage | aoe_damage | 1.0× ranged | 5 | 5 | ground_aoe (r=1) |
| Blink | teleport | — | 4 | 5 | tile |

### Skill Details

#### Fireball (magic_damage)
```
Type:       magic_damage (NEW effect type)
Base:       ranged_damage × 2.0 multiplier
Range:      5 tiles
Cooldown:   5 turns
LOS:        Required
Targeting:  Single entity
Armor:      50% effectiveness (magic partially ignores armor)
Bonuses:    skill_damage_pct + magic_damage_pct
```
**Design:** The Mage's bread-and-butter nuke. At 14 base ranged × 2.0 = 28 raw damage, reduced by only half armor. Against a Crusader (8 armor), this deals `max(1, 28 - 4) = 24` vs. a physical attack dealing `max(1, 28 - 8) = 20`. The armor bypass becomes more impactful as enemy armor scales.

#### Frost Nova (aoe_damage_slow)
```
Type:       aoe_damage_slow (NEW effect type)
Base:       12 flat damage
Radius:     2 tiles (self-centered)
Cooldown:   6 turns
Targeting:  Self-centered AoE
Armor:      50% effectiveness
Slow:       2-turn duration
Bonuses:    skill_damage_pct + magic_damage_pct
```
**Design:** Defensive/utility AoE. Self-centered means the Mage must be near enemies to use it — a deliberate risk/reward for a glass cannon. The 2-turn slow enables kiting escape or lets allies catch fleeing enemies. The 12 flat damage is modest but guaranteed vs. clusters.

#### Arcane Barrage (aoe_damage)
```
Type:       aoe_damage (existing effect type)
Base:       ranged_damage × 1.0 multiplier
Radius:     1 tile
Range:      5 tiles
Cooldown:   5 turns
Targeting:  Ground AoE (clicks tile, hits all enemies in radius)
```
**Design:** Ranged AoE for punishing clusters without self-endangering. Lower per-target damage than Fireball (14 vs 28) but can hit multiple enemies. Uses the existing `aoe_damage` effect type with physical armor rules (not magic bypass). Useful against tightly-packed groups.

#### Blink (teleport)
```
Type:       teleport (existing effect type)
Range:      4 tiles
Cooldown:   5 turns
LOS:        Required
Targeting:  Empty tile
```
**Design:** The Mage's primary survivability tool. Reuses the same `teleport` effect type as Hexblade's Shadow Step. 4-tile range allows escaping melee contact or repositioning for line-of-sight. The AI uses it defensively (escape when low HP + adjacent enemy) and offensively (gap-close to enter casting range).

---

## DPS Analysis

### Single-Target DPS (Sustained)

**Rotation:** Fireball (turn 1) → 4× auto-attack → Fireball (turn 6) → ...

| Component | Damage per Hit | Hits per 10 turns | Total |
|-----------|---------------:|-------------------:|------:|
| Fireball | 28 raw | 2 | 56 |
| Auto-attack | 14 raw | 8 | 112 |
| **Total raw** | | | **168** |
| **DPS (raw)** | | | **16.8/turn** |

vs. Ranger comparison:
- Ranger: Power Shot (36) + 4× auto (18 each) = 108 / 5 turns = **21.6 DPS raw**
- Mage: Fireball (28) + 4× auto (14 each) = 84 / 5 turns = **16.8 DPS raw**
- **But:** Mage armor bypass means effective DPS exceeds raw vs. armored targets

### AoE DPS (Clustered Enemies)

Against 3 clustered enemies:
- Arcane Barrage: 14 × 3 = 42 damage
- Frost Nova: 12 × 3 = 36 damage + 2-turn slow
- **Total AoE burst:** 78 damage across 3 targets

No other class can match this AoE output.

### vs. Armor Comparison (Fireball vs Power Shot)

| Target Armor | Power Shot (36 phys) | Fireball (28 magic) | Magic Advantage |
|:-----------:|:--------------------:|:-------------------:|:---------------:|
| 0 | 36 | 28 | -8 |
| 4 | 32 | 26 | -6 |
| 8 | 28 | 24 | -4 |
| 12 | 24 | 22 | -2 |
| 16 | 20 | 20 | 0 (breakeven) |
| 20 | 16 | 18 | +2 |
| 24 | 12 | 16 | +4 |

**Takeaway:** Mage falls behind Ranger in raw single-target DPS but closes the gap against armored targets and far exceeds in AoE scenarios. This is the intended niche.

---

## AI Behavior (caster_dps role)

The Mage AI uses a **kiting caster** strategy, adapted from the Ranger's ranged_dps template with priority adjustments for AoE and escape:

### Decision Priority

1. **Frost Nova** — if 2+ enemies within radius 2, OR 1 adjacent enemy + HP < 40%
2. **Blink (escape)** — if adjacent enemy + HP < 40% (after Frost Nova attempt)
3. **Fireball** — highest-HP enemy in range with LOS
4. **Arcane Barrage** — if 2+ enemies within radius 1 of a reachable tile
5. **Blink (offensive)** — gap-close if no enemies in range but some within Blink+cast range
6. **Auto-attack** — fallback if all skills on cooldown

### Positioning

- Reuses `_find_shadow_step_escape_tile()` for Blink escape (find tile 3+ away from nearest enemy)
- Reuses `_find_shadow_step_offensive_tile()` for Blink gap-close (find tile within cast range of target)
- Ranger-style kiting: prefers maintaining max cast range, retreats from melee engagement

---

## Survivability Analysis

| Threat | Turns to Kill Mage (70 HP) | Mage Response |
|--------|:--------------------------:|---------------|
| Crusader (20 melee, adjacent) | 4 turns | Frost Nova slow → Blink away → kite |
| Ranger (18 ranged) | 4 turns | Blink to break LOS, or close for Frost Nova |
| Hexblade (15 melee + Shadow Step) | 5 turns | Frost Nova if dived → Blink escape |
| Imp swarm (5 × 6 dmg) | 3 turns | Frost Nova AoE clears 2-3, Blink repositions |

**Expected lifespan:** 6-10 turns in combat with AI kiting behavior. The Mage trades survivability for burst and AoE — a deliberate glass cannon design.

---

## Implementation Details

### New Effect Types

Two new skill effect types were added to the combat resolution system:

1. **`magic_damage`** — Single-target magic damage with 50% armor effectiveness
   - Handler: `resolve_magic_damage()` in `skills.py`
   - Formula: `max(1, (base_ranged × multiplier × (1 + skill_pct + magic_pct)) - (armor × 0.5))`

2. **`aoe_damage_slow`** — Self-centered AoE damage + slow debuff
   - Handler: `resolve_aoe_damage_slow()` in `skills.py`
   - Formula: `max(1, (flat_damage × (1 + skill_pct + magic_pct)) - (armor × 0.5))`
   - Applies slow debuff to surviving targets

### New Player Stat

- **`magic_damage_pct`** — Percentage bonus to magic damage (0.0 default)
  - Added to `PlayerState` model in `player.py`
  - Used by `resolve_magic_damage()` and `resolve_aoe_damage_slow()` handlers
  - Designed for Phase 16 item affixes (e.g., "Staff of Immolation: +15% magic damage")

### Files Modified

| File | Change |
|------|--------|
| `server/configs/classes_config.json` | Added mage class definition |
| `server/configs/skills_config.json` | Added 4 skills + class_skills mapping |
| `server/app/core/skills.py` | Added `magic_damage` and `aoe_damage_slow` handlers |
| `server/app/core/ai_skills.py` | Added `caster_dps` role + AI logic |
| `server/app/models/player.py` | Added `magic_damage_pct` stat |
| `client/src/canvas/renderConstants.js` | Added mage color, shape, name |
| `client/src/canvas/unitRenderer.js` | Added hexagon shape rendering |
| `client/src/canvas/SpriteLoader.js` | Added 7 mage sprite variants |
| `client/src/components/WaitingRoom/WaitingRoom.jsx` | Added hexagon icon |

### Sprite Variants

7 mage sprites from the Combined Character Sheet atlas:
- `mage` (Mage_1): `{x:1890, y:1350}`
- `mage_2`: `{x:270, y:810}`
- `mage_3`: `{x:0, y:270}`
- `mage_4`: `{x:0, y:2700}`
- `mage_5`: `{x:2700, y:540}`
- `mage_6`: `{x:2430, y:540}`
- `mage_7`: `{x:1890, y:270}`

---

## Tuning Notes

These values are initial and should be adjusted based on playtesting:

- **Fireball multiplier (2.0×):** May need reduction to 1.8× if burst is too high
- **Frost Nova radius (2):** Large radius; consider reducing to 1 if too oppressive
- **Frost Nova slow duration (2 turns):** May extend to 3 if Mage dies too fast
- **Blink range (4):** Generous; can reduce to 3 if escape is too reliable
- **Base HP (70):** Can raise to 80 if Mage dies instantly in PvE
- **Armor bypass (50%):** Core identity; avoid changing unless creating a dedicated resistance stat
- **Cooldowns:** All set to 5-6 turns; if rotation feels dead, consider reducing Fireball to 4

### Future Enhancements

- **Particle effects:** Fireball trail, Frost Nova expanding ring, Arcane Barrage rain, Blink flash
- **Unique items:** Staff with +magic_damage_pct, orb with AoE radius+1, etc.
- **Mage-specific affixes:** Spell penetration, mana (future resource), cast speed
- **Additional caster classes:** Necromancer (summons), Warlock (DoT), Druid (shapeshifter) — all using magic_damage_pct

---

## Phase Checklist

- [x] Mage added to classes_config.json
- [x] 4 skills added to skills_config.json
- [x] magic_damage effect handler implemented
- [x] aoe_damage_slow effect handler implemented
- [x] caster_dps AI role implemented
- [x] magic_damage_pct stat added to PlayerState
- [x] Frontend rendering (hexagon shape, color, name)
- [x] Sprite mappings (7 variants)
- [x] WaitingRoom hexagon icon
- [x] Design document written
- [ ] Particle effects (deferred — tune after playtesting)
- [ ] Balance pass (after playtesting data)
