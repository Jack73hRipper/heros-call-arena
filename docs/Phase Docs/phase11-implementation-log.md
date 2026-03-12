# Phase 11: Class Identity & Tactical Depth — Implementation Log

## Overview

Phase 11 adds class-defining skills, creature tags, and 5 new backend systems to
support damage-over-time, healing-over-time, charge-based shields, holy damage,
and detection/reveal mechanics. All 3 under-defined classes (Hexblade, Inquisitor,
Confessor) now have 4 skills each with distinct tactical identities.

**Status:** Core implementation complete. Server validated — all imports clean, configs load correctly.

---

## Files Modified

### Backend (server/)

| File | Changes |
|------|---------|
| `app/models/player.py` | Added `tags: list[str]` field to `PlayerState` and `EnemyDefinition`. Updated `apply_enemy_stats()` to copy tags from enemy definition to player state. |
| `app/core/skills.py` | Major expansion — 5 new effect handlers, upgraded tick system, generic stat pipeline, ward/reflect mechanics. ~500 lines added. |
| `app/core/combat.py` | `calculate_damage()` and `calculate_ranged_damage()` now use `get_effective_armor()` instead of manual armor calculation. Armor buffs (Shield of Faith) now automatically apply. |
| `app/core/turn_resolver.py` | `_resolve_cooldowns_and_buffs()` expanded to process DoT damage ticks, HoT healing ticks, and DoT kills with proper ActionResult logging. Ward reflect integrated into `_resolve_melee()` and `_resolve_ranged()`. |
| `app/core/ai_skills.py` | Three role handlers fully rewritten: `_support_skill_logic()` (7 priorities), `_scout_skill_logic()` (5 priorities), `_hybrid_dps_skill_logic()` (5 priorities). Added `_find_heal_candidates()` helper. |
| `configs/skills_config.json` | 7 new skills added, `class_skills` updated for Confessor (4 skills), Inquisitor (4 skills), Hexblade (4 skills). |
| `configs/enemies_config.json` | Added `tags` to all 3 existing enemies. Added 2 new enemy types: `imp` and `dark_priest`. |

### Frontend (client/)

| File | Changes |
|------|---------|
| `src/components/HeaderBar/HeaderBar.jsx` | `formatBuffName()`: 8 new entries. `formatBuffEffect()`: handles DoT, HoT, shield_charges, detection, armor buffs. Buff pills now show per-type icons and CSS classes. |
| `src/components/CombatLog/CombatLog.jsx` | `LOG_COLORS`: 6 new log types — `dot_damage`, `hot_heal`, `holy_damage`, `shield_reflect`, `detection`, `buff`. |
| `src/context/reducers/combatReducer.js` | Buff-applied actions now classified by type (DoT→`dot_damage`, HoT→`hot_heal`, shields→`shield_reflect`, detection→`detection`, armor→`buff`). Holy damage skills (`rebuke`, `exorcism`) get distinct `holy_damage` log type. |
| `src/styles/main.css` | 5 new buff pill CSS variants: `.buff-dot` (red), `.buff-hot` (green), `.buff-shield` (blue), `.buff-detection` (purple), `.buff-armor` (gold). |

---

## New Systems

### 1. Damage-over-Time (DoT)

- **Config:** `effects[].type = "dot"` with `damage_per_tick`, `duration_turns`
- **Application:** `resolve_dot()` validates range + LOS, prevents stacking same DoT
- **Tick:** `tick_buffs()` applies damage each turn, generates ActionResults for combat log
- **Death:** DoT can kill — death is tracked and logged
- **Used by:** Wither (Hexblade)

### 2. Healing-over-Time (HoT)

- **Config:** `effects[].type = "hot"` with `heal_per_tick`, `duration_turns`
- **Application:** `resolve_hot()` supports ally_or_self targeting with range check
- **Tick:** `tick_buffs()` heals each turn, generates ActionResults for combat log
- **Used by:** Prayer (Confessor)

### 3. Charge-Based Shields (Ward)

- **Config:** `effects[].type = "shield_charges"` with `charges`, `reflect_damage`
- **Application:** `resolve_shield_charges()` refreshes existing ward (no stacking)
- **Trigger:** `trigger_ward_reflect()` called from `_resolve_melee()` and `_resolve_ranged()` after damage — consumes a charge, deals reflect damage to attacker, can kill attacker
- **Tick:** Charges expire by consumption or when `turns_remaining` hits 0
- **Used by:** Ward (Hexblade)

### 4. Holy Damage

- **Config:** `effects[].type = "holy_damage"` with `base_damage`, `bonus_vs_tags`, `bonus_multiplier`
- **Resolution:** `resolve_holy_damage()` checks range + LOS, applies bonus multiplier vs tagged enemies, reduces by effective armor
- **Used by:** Rebuke (Inquisitor — 28 base, ×1.5 vs undead/demon), Exorcism (Confessor — 20 base, ×2.0 vs undead/demon)

### 5. Detection/Reveal

- **Config:** `effects[].type = "detection"` with `radius`, `detect_tags`, `duration_turns`
- **Resolution:** `resolve_detection()` finds enemies matching tags within radius, applies "detected" buff to them
- **Used by:** Divine Sense (Inquisitor)

### 6. Generic Stat Pipeline

- **`get_armor_buff_bonus(player)`** — sums all `stat="armor"` buffs
- **`get_effective_armor(player)`** — returns `player.armor + armor buff bonus`
- **Integration:** `calculate_damage()` and `calculate_ranged_damage()` use `get_effective_armor()` instead of manual armor math; armor buffs automatically work everywhere

### 7. Creature Tags

- **Model:** `tags: list[str]` on both `PlayerState` and `EnemyDefinition`
- **Config:** All enemies tagged (`demon`, `undead`)
- **Used by:** Holy damage bonus targeting, Detection reveal filtering

---

## New Skills (7 total)

| Skill | Class | Effect Type | Key Stats | Cooldown |
|-------|-------|-------------|-----------|----------|
| **Wither** | Hexblade | DoT | 6 dmg/turn × 4 turns, range 3 | 6 |
| **Ward** | Hexblade | Shield Charges | 3 charges × 8 reflect damage | 6 |
| **Divine Sense** | Inquisitor | Detection | Radius 12, reveals undead/demon | 7 |
| **Rebuke** | Inquisitor | Holy Damage | 28 base / 42 vs tagged, range 6 | 5 |
| **Shield of Faith** | Confessor | Buff (armor) | +5 armor × 3 turns, range 3 | 5 |
| **Exorcism** | Confessor | Holy Damage | 20 base / 40 vs tagged, range 5 | 4 |
| **Prayer** | Confessor | HoT | 8 hp/turn × 4 turns, range 4 | 6 |

---

## Updated Class Skill Loadouts

| Class | Skills |
|-------|--------|
| **Crusader** | War Cry, Double Strike |
| **Confessor** | Heal, Shield of Faith, Exorcism, Prayer |
| **Inquisitor** | Power Shot, Shadow Step, Divine Sense, Rebuke |
| **Ranger** | Power Shot |
| **Hexblade** | Double Strike, Shadow Step, Wither, Ward |

---

## New Enemy Types (2)

| Enemy | HP | Melee | Ranged | Armor | Tags | Behavior |
|-------|----|-------|--------|-------|------|----------|
| **Imp** | 30 | 8 | 0 | 0 | demon | Aggressive (swarm) |
| **Dark Priest** | 80 | 6 | 10 | 3 | undead | Support (ranged healer) |

---

## AI Role Handler Updates

### Confessor (Support) — 7 Priorities
1. Heal self (below 50% HP)
2. Heal most injured ally (below 60% HP)
3. Prayer (HoT) on injured ally (if Heal on cooldown, no existing HoT)
4. Shield of Faith on most injured ally (no stacking)
5. Exorcism on tagged enemy in range (holy bonus)
6. Exorcism on any enemy in range
7. Fall through to basic attack

### Inquisitor (Scout) — 5 Priorities
1. Shadow Step escape (below 30% HP, adjacent enemies)
2. Rebuke on tagged enemy in range (holy bonus, prioritized)
3. Rebuke on nearest enemy in range
4. Power Shot on enemy in range + LOS
5. Shadow Step offensive gap-close (enemy > 4 tiles away)
- Divine Sense used when no enemies are visible

### Hexblade (Hybrid DPS) — 5 Priorities
1. Ward (if no active ward and enemies visible)
2. Wither on highest-HP enemy in range (no stacking, prefers tanky targets)
3. Double Strike on adjacent enemy
4. Shadow Step gap-close (enemy > 3 tiles away)
5. Fall through to basic attack

---

## Frontend Display

- **Buff pills** show per-type icons: 🩸 DoT, 💚 HoT, 🛡️ Shield, 👁️ Detection, ✨ Armor, 🔷 Default
- **Shield charges** display as `3ch` instead of `3t` (charges, not turns)
- **Combat log** uses distinct colors: gold for holy damage, dark red for DoT ticks, green for HoT ticks, blue for shield reflect, purple for detection

---

## Architecture Notes

- All new effect types follow the existing pattern: config defines the skill → `resolve_skill_action()` dispatches to the right handler → handler produces `ActionResult` → turn resolver processes results
- The generic stat pipeline (`get_effective_armor()`) is extensible — adding `get_effective_melee_damage()` or similar follows the same pattern
- Creature tags are a general-purpose system — new tags can be added to enemies without code changes
- Ward reflect hooks into existing melee/ranged resolution phases — no new turn phases needed
- DoT/HoT ticks happen during the buff tick phase (phase 2 of turn resolution), before any other combat
- Enemy skill usage is **not** implemented — enemies dispatch AI by `class_id` which they don't have. Enemy skills would be a future phase feature

---

## Known Limitations / Future Work

1. ~~**Enemy skill usage**~~ ✅ *Resolved.* Enemies now have `class_id` fields and `_decide_skill_usage()` is wired into all three enemy behaviors (aggressive, ranged, boss). A new "support" behavior was also added. See "Enemy Expansion" section below.
2. **Divine Sense visual** — Detection applies a "detected" buff to enemies but the frontend doesn't visually highlight detected enemies on the canvas (would need canvas renderer integration).
3. **Ward visual feedback** — No particle effect or canvas visual when Ward reflects damage. Could integrate with the particle system (Phase 9).
4. **Floaters for ticks** — DoT damage ticks and HoT heal ticks generate combat log entries but not floating damage numbers on the canvas. Would need additional floater logic in `combatReducer.js`.
5. **Crusader and Ranger** — Still have only 1-2 skills. Future phases could add defensive/utility skills.

---

## Enemy Expansion — Spellcasting Enemies & New Types

### Overview

Added 6 new spell-casting enemy types and wired the enemy AI skill infrastructure end-to-end.
Enemies now have `class_id` fields that map them into the existing AI skill role system,
allowing them to cast skills from the same skill framework that hero allies use.

### Infrastructure Changes

**Enemy Spellcasting Pipeline:**
- `EnemyDefinition` model: Added `class_id: str | None = None` field
- `apply_enemy_stats()`: Now copies `class_id` from enemy definition to `PlayerState`
- `_decide_aggressive_action()`: Added `_decide_skill_usage()` call before basic attacks
- `_decide_ranged_action()`: Added `_decide_skill_usage()` call before retreat logic
- `_decide_boss_action()`: Added `_decide_skill_usage()` call before melee attack
- New `_decide_support_behavior()`: Full support AI for enemy healers (~100 lines)
- `_CLASS_ROLE_MAP`: Extended with 6 enemy class mappings

### New Enemies (6)

| Enemy | HP | Melee | Ranged | Armor | Vision | Range | Tags | AI | Role | Class ID | Skills |
|-------|----|-------|--------|-------|--------|-------|------|-----|------|----------|--------|
| **Wraith** | 70 | 10 | 0 | 2 | 7 | 1 | undead | Aggressive | Caster DPS | wraith | Wither, Shadow Step |
| **Medusa** | 90 | 8 | 12 | 3 | 7 | 5 | beast | Ranged | Debuff Caster | medusa | Venom Gaze, Power Shot |
| **Acolyte** | 70 | 6 | 0 | 2 | 6 | 1 | demon | Support | Enemy Support | acolyte | Heal, Shield of Faith |
| **Werewolf** | 130 | 22 | 0 | 5 | 6 | 1 | beast | Aggressive | Melee Elite | werewolf | War Cry, Double Strike |
| **Reaper** | 250 | 20 | 15 | 8 | 7 | 4 | undead | Boss | Death Caster | reaper | Wither, Soul Reap |
| **Construct** | 160 | 14 | 0 | 10 | 4 | 1 | construct | Aggressive | Tank | construct | Ward |

### New Skills (2)

| Skill | Class | Type | Key Stats | Cooldown |
|-------|-------|------|-----------|----------|
| **Venom Gaze** | Medusa | DoT | 5 dmg/turn × 3 turns = 15 total, range 4 | 5 |
| **Soul Reap** | Reaper | Ranged Damage | 2.0× ranged damage, range 4 | 4 |

### Updated Skill Access (existing skills shared with enemies)

| Skill | Original Classes | Added Enemy Classes |
|-------|-----------------|---------------------|
| Heal | Confessor | + Acolyte |
| Shield of Faith | Confessor | + Acolyte |
| Double Strike | Crusader, Hexblade | + Werewolf |
| War Cry | Crusader | + Werewolf |
| Shadow Step | Hexblade, Inquisitor | + Wraith |
| Wither | Hexblade | + Wraith, Reaper |
| Ward | Hexblade | + Construct |
| Power Shot | Ranger, Inquisitor | + Medusa |

### New Creature Tags

- `beast` — Medusa, Werewolf (not vulnerable to holy damage)
- `construct` — Construct (not vulnerable to holy damage)

### AI Role Mappings

| Enemy Class ID | AI Role | Behavior |
|----------------|---------|----------|
| wraith | hybrid_dps | Wither → Shadow Step gap-close |
| medusa | ranged_dps | Venom Gaze (DoT) → Power Shot |
| acolyte | support | Heal allies → Shield of Faith → retreat |
| werewolf | tank | War Cry (self-buff) → Double Strike |
| reaper | hybrid_dps | Wither → Soul Reap from range |
| construct | tank | Ward (self-shield) → melee |

### Files Modified

| File | Changes |
|------|---------|
| `configs/enemies_config.json` | Added 6 new enemies with `class_id` fields; added `class_id: "acolyte"` to existing dark_priest |
| `configs/skills_config.json` | 2 new skills (venom_gaze, soul_reap); updated `allowed_classes` on 7 existing skills; added 6 enemy `class_skills` entries |
| `configs/loot_tables.json` | Added loot tables for all 6 new enemies + imp + dark_priest |
| `app/models/player.py` | Added `class_id` field to `EnemyDefinition`; wired into `apply_enemy_stats()` |
| `app/core/ai_skills.py` | Extended `_CLASS_ROLE_MAP` with 6 enemy classes; added Venom Gaze to ranged_dps handler; added Soul Reap to hybrid_dps handler |
| `app/core/ai_behavior.py` | Wired `_decide_skill_usage()` into aggressive, ranged, and boss behaviors; added "support" behavior dispatch + `_decide_support_behavior()` function |
| `src/canvas/SpriteLoader.js` | Added 7 sprite regions (wraith, medusa, acolyte, werewolf, reaper, construct, undead_knight) |
| `src/canvas/renderConstants.js` | Added all 11 enemies to `ENEMY_COLORS`, `ENEMY_SHAPES`, `ENEMY_NAMES` |

### Test Updates

Pre-existing tests were written before Phase 11 skills were added to hero classes and before enemy spellcasting was wired. Updated test expectations across 8 test files:
- `test_ai_hybrid.py` — Added wither cooldowns to isolate double_strike tests
- `test_ai_scout.py` — Added rebuke/divine_sense cooldowns to isolate power_shot tests
- `test_ai_support.py` — Added shield_of_faith/exorcism/prayer cooldowns to isolate heal tests
- `test_ai_integration.py` — Updated enemy skill exclusion test to reflect new spellcasting design
- `test_ai_skills.py` — Updated role map count (5 → 11)
- `test_enemy_types.py` — Updated enemy count (3 → 11)
- `test_skills.py` — Updated skill counts, allowed_classes lists, class_skills expectations
- `test_ws_skills.py` — Updated class_skills expectations for all hero classes

**All 1495 tests passing.**
