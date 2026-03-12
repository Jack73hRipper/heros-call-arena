# Phase 23 — Plague Doctor Class (Controller / Debuff Specialist)

**Created:** March 2026
**Status:** Phase 23G Complete
**Previous:** Phase 22 (Blood Knight Class)
**Goal:** Add the Plague Doctor as the 9th playable class — a grimdark battlefield alchemist who controls space with poison clouds, weakens enemy groups, and punishes clustering. Fills the "Controller" role gap: no existing class is primarily about crowd control, area denial, and damage reduction debuffs. The Plague Doctor trades personal DPS for massive team survivability through enemy debuffing — the anti-Bard.

---

## Overview

A masked plague alchemist who weaponizes disease and toxins on the battlefield. Where the Bard amplifies allies ("we kill faster"), the Plague Doctor cripples enemies ("we die slower"). Throws toxic flasks, spreads contagion, and makes entire enemy groups rot from the inside — a grimdark disease vector, not a healer.

**Role:** Controller

### Design Pillars

1. **Area Denial** — The Plague Doctor forces enemies to either spread out or suffer; clustered enemies are punished severely
2. **Debuff-First Identity** — Personal DPS is intentionally low; the class's power budget is spent on weakening enemies and enabling the team
3. **Mirror of the Bard** — The Bard is offensive support (buff allies, amp damage); the Plague Doctor is defensive control (debuff enemies, reduce incoming damage)
4. **Existing System Reuse** — 3 of 4 skills reuse existing effect handlers verbatim; only 1 new debuff stat and 1 minor handler extension needed
5. **Grimdark Alchemist Fantasy** — Plague mask, toxic flasks, noxious clouds — every ability should feel like watching a medieval plague spread

---

## Base Stats

| Stat | Value | Rationale |
|------|-------|-----------|
| **HP** | 85 | Between Mage (70) and Bard (90). Squishy midliner — survives a hit more than Mage but not a frontliner |
| **Melee Damage** | 8 | Weak — same as Confessor/Ranger. Carrying vials, not swords |
| **Ranged Damage** | 12 | Moderate — alchemical flask tosses. Between Bard (10) and Mage (14). Skills do the real work |
| **Armor** | 2 | Light — plague mask and robes. Same tier as Ranger |
| **Vision Range** | 7 | Standard — no reason to be a scout, no reason to be blind |
| **Ranged Range** | 5 | Medium — needs to reach the fight from the midline but not dominate like Ranger (6) |
| **Allowed Weapons** | `["caster", "hybrid"]` | Alchemical implements, staves, wands |
| **Color** | `#50C878` | Emerald green — toxic/poison vibes. Distinct from Ranger's bright green (#40c040) by being more blue-teal |
| **Shape** | `flask` | An alchemical flask/potion bottle silhouette — immediately communicates the class identity |

### Stat Comparison (All Classes)

```
                    HP    Melee  Ranged  Armor  Vision  Range  Role
 Crusader ......   150      20       0      8       5      0   Tank
 Confessor .....   100       8       0      3       6      0   Defensive Support
 Inquisitor ....    80      10       8      4       9      5   Scout
 Ranger ........    80       8      18      2       7      6   Ranged DPS
 Hexblade ......   110      15      12      5       6      4   Hybrid DPS
 Mage ..........    70       6      14      1       7      5   Caster DPS
 Bard ..........    90      10      10      3       7      4   Offensive Support
 Blood Knight ..   100      16       0      4       6      0   Sustain Melee DPS
 Plague Doctor .    85       8      12      2       7      5   Controller
```

### Auto-Attack Damage (1.15× multiplier)

```
 Plague Doctor .. 12 × 1.15 = 14 ranged per hit (range 5)
```

Lower than Ranger (21), Hexblade (17), Mage (16). Similar to Inquisitor auto-attack damage. This is intentional — the Plague Doctor's value comes from skill effects (DoTs, debuffs, slows), not raw auto-attack output.

---

## Skills

### Skill Overview

| Slot | Skill | Effect Type | Target | Range | Cooldown | Summary |
|:----:|-------|------------|--------|:-----:|:--------:|---------|
| 0 | Auto Attack (Ranged) | ranged_damage | entity | 5 | 0 | 1.15× ranged damage (14) |
| 1 | Miasma | aoe_damage_slow (**NEW variant**: ground-targeted) | ground_aoe | 5 | 6 | AoE 10 dmg + 2-turn slow in 2-tile radius |
| 2 | Plague Flask | dot (existing) | enemy_ranged | 5 | 5 | Single-target poison: 7/tick × 4 turns = 28 total |
| 3 | Enfeeble | aoe_debuff (existing) | ground_aoe | 4 | 7 | AoE debuff: enemies deal 25% less damage for 3 turns |
| 4 | Inoculate | buff_cleanse (**NEW**: buff + DoT cleanse) | ally_or_self | 3 | 5 | +3 armor for 3 turns + cleanse all DoTs on target |

### Skill Details

#### Miasma ☁️ (AoE Poison Cloud)

```
Effect Type:   aoe_damage_slow_targeted (NEW — ground-targeted variant of aoe_damage_slow)
Targeting:     ground_aoe
Radius:        2 tiles
Range:         5 tiles
Cooldown:      6 turns
LOS Required:  Yes
Effect:        Deal 10 magic damage and slow all enemies within 2 tiles of target
               tile for 2 turns. Slow prevents movement but allows attacks/skills.
```

**Design:** The Plague Doctor's signature area-denial tool. Unlike Frost Nova (self-centered, melee escape) and Cacophony (self-centered, self-peel), Miasma is lobbed *at range* into an enemy cluster. This is the "force enemies to spread or suffer" button — the defining Controller skill.

**Damage/healing/effect examples:**
```
vs 3 enemies clustered:         10 × 3 = 30 total damage + all slowed 2 turns
vs Crusader (8 armor, 50% eff): max(1, 10 - 4) = 6 damage + slow
vs Ranger (2 armor, 50% eff):   max(1, 10 - 1) = 9 damage + slow
vs Mage (1 armor, 50% eff):     max(1, 10 - 0) = 10 damage + slow
DPT per target (over CD cycle): 10 / 6 = 1.7 per target
```

**Implementation:** New handler `resolve_aoe_damage_slow_targeted()` — based on the existing `resolve_aoe_damage_slow()` (Frost Nova/Cacophony) but uses `target_x`/`target_y` as the AoE center instead of the caster's position. Also add range + LOS validation to center tile (same pattern as `resolve_aoe_debuff()`). ~60 lines — mostly copy of existing handler with center-tile swap.

**Balance lever:** Damage (10), radius (2), slow duration (2), cooldown (6), range (5)

---

#### Plague Flask 🧪 (Single-Target Poison DoT)

```
Effect Type:   dot (EXISTING — same handler as Wither, Venom Gaze)
Targeting:     enemy_ranged
Radius:        — (single target)
Range:         5 tiles
Cooldown:      5 turns
LOS Required:  Yes
Effect:        Poison an enemy — 7 damage per turn for 4 turns (28 total).
               Recasting refreshes duration (same as Wither behavior).
```

**Design:** The Plague Doctor's sustained single-target damage. Compared to Wither (8/tick × 4 = 32, CD 6), Plague Flask does slightly less total (28) on a shorter cooldown (5). This lets the Plague Doctor be a persistent DoT applier — always poisoning *something*. The shorter CD means higher uptime; the lower per-tick means it doesn't outclass the Hexblade's signature curse.

**Damage/healing/effect examples:**
```
vs any target: 7 × 4 = 28 total (DoT ignores armor — true damage)
DPT over cooldown cycle: 28 / 5 = 5.6 effective DPT
Wither comparison:       32 / 6 = 5.3 effective DPT — very close, intentional parity
```

**Implementation:** Reuses `resolve_dot()` identically to Wither. Config-only difference — zero code changes needed for this skill.

**Balance lever:** Damage per tick (7), duration (4), cooldown (5), range (5)

---

#### Enfeeble 💀 (AoE Damage Reduction Debuff)

```
Effect Type:   aoe_debuff (EXISTING — same handler as Dirge of Weakness)
Targeting:     ground_aoe
Radius:        2 tiles
Range:         4 tiles
Cooldown:      7 turns
LOS Required:  Yes
Effect:        All enemies within 2 tiles of target deal 25% LESS damage for 3 turns.
               Applies debuff stat "damage_dealt_multiplier" with magnitude 0.75.
```

**Design:** The Plague Doctor's **crown jewel** and what makes them a true Controller. The Bard's Dirge makes enemies *take more damage* (`damage_taken_multiplier = 1.25` — offensive amplifier). The Plague Doctor's Enfeeble makes enemies *deal less damage* (`damage_dealt_multiplier = 0.75` — defensive controller). Mirror images — both AoE debuffs using `resolve_aoe_debuff()`, completely different strategic purpose.

**Damage/healing/effect examples:**
```
Crusader auto (23 dmg) while enfeebled: 23 × 0.75 = 17 dmg (saves 6/hit)
Ranger auto (21 dmg) while enfeebled:   21 × 0.75 = 16 dmg (saves 5/hit)
Hexblade auto (17 dmg) while enfeebled: 17 × 0.75 = 13 dmg (saves 4/hit)

3 enemies enfeebled over 3 turns (avg 15 DPT each):
  Without: party takes 45 DPT × 3 turns = 135 total
  With:    party takes 34 DPT × 3 turns = 101 total → 34 effective HP saved
  That's equivalent to ~1 free Heal per turn for 3 turns, applied to the whole party
```

**Implementation:** Reuses `resolve_aoe_debuff()` from Dirge of Weakness verbatim. **New debuff stat: `damage_dealt_multiplier`** — this needs to be checked in the combat damage pipeline (Phase 23C). The handler itself needs zero changes; only the combat pipeline needs to read the new stat from active_buffs.

**Balance lever:** Magnitude (0.75 = 25% reduction), radius (2), duration (3), cooldown (7), range (4)

---

#### Inoculate 💉 (Ally Buff + DoT Cleanse)

```
Effect Type:   buff_cleanse (NEW — extends resolve_buff with DoT removal)
Targeting:     ally_or_self
Radius:        — (single target)
Range:         3 tiles
Cooldown:      5 turns
LOS Required:  No
Effect:        Grant target +3 armor for 3 turns. Additionally cleanse ALL active
               DoTs (type "dot") from the target.
```

**Design:** Gives the Plague Doctor a small team-utility niche — they understand poisons, so they can *cure* them too. The +3 armor is moderate (less than Shield of Faith's +5, less than Bulwark's +8) because the DoT cleanse is the real value. Extremely useful in dungeons where enemies apply Wither (32 total damage), Venom Gaze (15 total), and Plaguebow DoT. Also a self-defense option when poisoned.

**Damage/healing/effect examples:**
```
+3 armor for 3 turns:
  vs Crusader (20 melee): saves 3 dmg/hit × ~3 hits = 9 effective HP
  vs Ranger (21 ranged):  saves 3 dmg/hit × ~3 hits = 9 effective HP

DoT cleanse value:
  Cleansing Wither (8/tick × 4 remaining): saves up to 32 HP
  Cleansing Venom Gaze (5/tick × 3 remaining): saves up to 15 HP
  Cleansing any DoT on turn 1: maximum HP savings = full DoT duration
```

**Implementation:** Extends `resolve_buff()` with a minor addition: when the skill's effect has `"cleanse_dots": true`, also strip any entries with `"type": "dot"` from the target's `active_buffs` list. This is a ~5-line addition to the existing buff handler. Alternative: a new thin `resolve_buff_cleanse()` wrapper that calls `resolve_buff()` then strips DoTs.

**Balance lever:** Armor amount (3), duration (3), cooldown (5), range (3). DoT cleanse is binary (on/off) — the lever is cooldown and range.

---

### Complete Plague Doctor Kit

```
Slot 0: Auto Attack — 14 ranged damage at range 5 (1.15× multiplier)
Slot 1: Miasma — Lob a poison cloud at range 5: 10 AoE damage + 2-turn slow (2-tile radius, CD 6)
Slot 2: Plague Flask — Poison a single enemy: 7 dmg/turn × 4 turns = 28 total (CD 5)
Slot 3: Enfeeble — Weaken all enemies in 2-tile radius: deal 25% less damage for 3 turns (CD 7)
Slot 4: Inoculate — Buff ally/self +3 armor for 3 turns + cleanse all DoTs (CD 5)
```

---

## DPS Contribution Analysis

### Direct DPS (Personal)

```
Auto-attack:    14 per turn (ranged, range 5)
Plague Flask:   28 total / 5 CD = 5.6 effective DPT (true damage, ignores armor)
Miasma:         10 flat per target / 6 CD = 1.7 DPT per target (magic damage, 50% armor)

Single-target sustained DPT: 14 + 5.6 = ~20 DPT
  Compare: Ranger ~26 DPT, Hexblade ~22 DPT, Mage ~25 DPT, Bard ~18 DPT

3-target cluster sustained DPT: 14 + 5.6 + (1.7 × 3) = ~25 DPT total
  But the real value is the 30 damage burst + 3-target slow from Miasma

Total personal DPS ranking: LOWEST among ranged classes — intentional.
```

### Team Impact Analysis (Enfeeble + Control)

```
SCENARIO: 4-person party vs 3 enemies, each dealing ~15 effective DPT

Without Plague Doctor:
  Party takes 45 DPT → over 6 turns: 270 total damage absorbed

With Plague Doctor (Enfeeble active 3 of 6 turns):
  3 turns normal: 45 DPT × 3 = 135
  3 turns enfeebled: 45 × 0.75 × 3 = 101
  Total: 236 → saves 34 HP over 6 turns

With Plague Doctor (Miasma slows enabling party to kite 2 turns):
  2 turns of 0 damage from 3 slowed enemies = 90 DPT saved
  Combined with Enfeeble: ~124 effective HP saved over a 6-turn fight

Plague Flask on high-DPS target: 28 true damage (ignores Crusader's 8 armor entirely)

Inoculate cleansing a Wither DoT: saves up to 32 HP on an ally

TOTAL TEAM IMPACT: ~150-180 effective HP per fight through debuffs/control/cleanse.
This is comparable to the Confessor's healing output (Heal 30 + Prayer 32 = 62 per cycle,
~2 cycles per fight = 124 HP) but delivered through a completely different mechanism.
```

**Design summary:** The Plague Doctor is the **anti-Bard**. Bard says "we kill faster" (+30% team damage). Plague Doctor says "we die slower" (-25% enemy damage + slows + DoT cleanse). Together they create the strongest possible team comp. Neither is good alone — both need party context to shine.

---

## AI Behavior (controller role)

### AI Role: `controller`

A new AI role. The Plague Doctor AI stays at midline range, prioritizes high-impact AoE debuffs on enemy clusters, keeps DoTs ticking on high-threat targets, and uses Inoculate reactively on poisoned or injured allies. Falls back to auto-attack from range when skills are on cooldown.

### Decision Priority

```
1. Enfeeble   → 2+ enemies within AoE radius, off cooldown, enemies NOT already enfeebled
2. Miasma     → 2+ enemies clustered within range, off cooldown
3. Plague Flask → enemy without active DoT in range, prefer highest-HP target
4. Inoculate  → ally with active DoT, OR ally below 50% HP, within range
5. Auto-attack → nearest enemy in range (fallback)
```

### Positioning

- **Midline** — stays 3-4 tiles behind the front line, similar to Bard/Mage positioning
- Reuses `_support_move_preference()` pattern (stay near allies, don't charge)
- **Retreat:** if any enemy is adjacent AND HP < 40%, move away from nearest enemy
- **No aggressive charge** — never runs toward enemies; relies on range 5 to contribute

### Smart Targeting Logic

```python
# Enfeeble targeting: find tile that hits most un-enfeebled enemies
for enemy in enemies:
    tile = (enemy.x, enemy.y)
    if dist(ai, tile) > enfeeble_range: continue
    if not LOS(ai, tile): continue
    count = sum(1 for e in enemies
                if dist(e, tile) <= radius
                and "enfeeble" not in e.active_buffs)
    if count > best_count: best = tile

# Miasma targeting: same pattern but for most enemies in radius
# (reuse same AoE cluster-scoring logic)

# Plague Flask targeting: prefer enemy without DoT, highest HP
candidates = [e for e in enemies if not has_dot(e) and in_range(ai, e, 5) and LOS(ai, e)]
target = max(candidates, key=lambda e: e.hp) if candidates else None

# Inoculate targeting: prefer ally with DoT, then lowest-HP ally
allies_with_dot = [a for a in allies if has_dot(a) and in_range(ai, a, 3)]
if allies_with_dot: target = allies_with_dot[0]
else: target = min([a for a in allies if a.hp/a.max_hp < 0.5], key=lambda a: a.hp/a.max_hp)
```

---

## New Effect Types

### Summary

| Effect Type | Complexity | Based On | Handler |
|-------------|-----------|----------|---------|
| `aoe_damage_slow_targeted` | Low | `resolve_aoe_damage_slow()` + `resolve_aoe_debuff()` targeting | `resolve_aoe_damage_slow_targeted()` |
| `buff_cleanse` | Low | `resolve_buff()` + DoT strip | `resolve_buff_cleanse()` |

### Effect Type Details

#### `aoe_damage_slow_targeted` — Ground-Targeted AoE Damage + Slow (Miasma)

```python
def resolve_aoe_damage_slow_targeted(
    player, action, skill_def, players, obstacles, grid_width=20, grid_height=20
):
    """Ground-targeted AoE: deal magic damage + apply slow to enemies in radius of target tile.

    Based on resolve_aoe_damage_slow() (Frost Nova) but targets a tile at range
    instead of being self-centered. Range + LOS validation to center tile.
    """
    # Step 1: Validate target_x/target_y provided
    # Step 2: Range check (Chebyshev) from caster to target tile
    # Step 3: LOS check from caster to target tile
    # Step 4: Find all enemies within radius of target tile
    # Step 5: Deal magic damage (50% armor effectiveness) + apply slow debuff
    # Step 6: Apply cooldown
    # Step 7: Return ActionResult with hit/slow/kill counts
```

#### `buff_cleanse` — Buff + DoT Cleanse (Inoculate)

```python
def resolve_buff_cleanse(
    player, skill_def, target_x, target_y, players, target_id=None
):
    """Apply a buff to ally/self AND cleanse all active DoTs from the target.

    Based on resolve_buff() with added DoT removal.
    """
    # Step 1: Resolve target (self or ally) — same logic as resolve_buff()
    # Step 2: Range check
    # Step 3: Apply armor buff (same as resolve_buff)
    # Step 4: Remove all entries with type="dot" from target.active_buffs
    # Step 5: Apply cooldown
    # Step 6: Return ActionResult with buff + cleanse info
```

### Buff/Debuff System Integration

**New stat: `damage_dealt_multiplier`**

This is the inverse of `damage_taken_multiplier` (Bard's Dirge). Applied to the *attacker* as a debuff, it reduces all outgoing damage.

Locations that must be updated:

1. `server/app/core/skills.py` — Add `get_damage_dealt_multiplier(player)` helper function (follows exact pattern of `get_damage_taken_multiplier()` — iterate `active_buffs`, multiply values where `stat == "damage_dealt_multiplier"`)

2. `server/app/core/combat.py` — `calculate_damage()` — After computing `final_damage` and applying `dmg_taken_mult`, also apply:
   ```python
   dmg_dealt_mult = get_damage_dealt_multiplier(attacker)
   if dmg_dealt_mult != 1.0:
       final_damage = max(1, int(final_damage * dmg_dealt_mult))
   ```

3. `server/app/core/combat.py` — `calculate_damage_simple()` — Same addition as above

4. `server/app/core/combat.py` — `calculate_ranged_damage()` — Same addition as above

5. `server/app/core/combat.py` — `calculate_ranged_damage_simple()` — Same addition as above

6. `server/app/core/skills.py` — Any skill damage handlers that bypass the main combat pipeline (e.g., `resolve_aoe_damage_slow`, `resolve_aoe_damage`, magic damage handlers) — check and apply `get_damage_dealt_multiplier()` on the caster if the attacker has the debuff. **Note:** For Enfeeble, the debuff is on the *attacker*, not the skill target. The existing `aoe_damage_slow` and `aoe_damage` handlers already check `get_damage_taken_multiplier()` on the *defender* — we need to also check `get_damage_dealt_multiplier()` on the *attacker* in those handlers.

---

## Implementation Phases

### Phase 23A — Config & Data Model (Foundation)

**Goal:** Add Plague Doctor to classes and skills configs. Wire up the data layer. Zero logic changes.

**Files Modified:**
| File | Change |
|------|--------|
| `server/configs/classes_config.json` | Add `plague_doctor` class definition |
| `server/configs/skills_config.json` | Add 4 skills + `class_skills.plague_doctor` mapping |

**Config: `classes_config.json`**
```json
"plague_doctor": {
  "class_id": "plague_doctor",
  "name": "Plague Doctor",
  "role": "Controller",
  "description": "Masked alchemist who weaponizes disease and toxins. Weakens groups, denies space, and makes enemies rot from the inside.",
  "base_hp": 85,
  "base_melee_damage": 8,
  "base_ranged_damage": 12,
  "base_armor": 2,
  "base_vision_range": 7,
  "ranged_range": 5,
  "allowed_weapon_categories": ["caster", "hybrid"],
  "color": "#50C878",
  "shape": "flask"
}
```

**Config: `skills_config.json`** — 4 new skills:

```json
"miasma": {
  "skill_id": "miasma",
  "name": "Miasma",
  "description": "Lob a toxic cloud at a target area — deal 10 magic damage and slow all enemies within 2 tiles for 2 turns.",
  "icon": "☁️",
  "targeting": "ground_aoe",
  "range": 5,
  "cooldown_turns": 6,
  "mana_cost": 0,
  "effects": [
    { "type": "aoe_damage_slow_targeted", "radius": 2, "base_damage": 10, "slow_duration": 2 }
  ],
  "allowed_classes": ["plague_doctor"],
  "requires_line_of_sight": true
},
"plague_flask": {
  "skill_id": "plague_flask",
  "name": "Plague Flask",
  "description": "Hurl a vial of pestilence at an enemy — deal 7 poison damage per turn for 4 turns (28 total). Recasting refreshes duration.",
  "icon": "🧪",
  "targeting": "enemy_ranged",
  "range": 5,
  "cooldown_turns": 5,
  "mana_cost": 0,
  "effects": [
    { "type": "dot", "damage_per_tick": 7, "duration_turns": 4 }
  ],
  "allowed_classes": ["plague_doctor"],
  "requires_line_of_sight": true
},
"enfeeble": {
  "skill_id": "enfeeble",
  "name": "Enfeeble",
  "description": "Release a cloud of enervating toxin — all enemies within 2 tiles of target deal 25% less damage for 3 turns.",
  "icon": "💀",
  "targeting": "ground_aoe",
  "range": 4,
  "cooldown_turns": 7,
  "mana_cost": 0,
  "effects": [
    { "type": "aoe_debuff", "radius": 2, "stat": "damage_dealt_multiplier", "magnitude": 0.75, "duration_turns": 3 }
  ],
  "allowed_classes": ["plague_doctor"],
  "requires_line_of_sight": true
},
"inoculate": {
  "skill_id": "inoculate",
  "name": "Inoculate",
  "description": "Administer an antitoxin — grant ally or self +3 armor for 3 turns and cleanse all active poison/DoT effects.",
  "icon": "💉",
  "targeting": "ally_or_self",
  "range": 3,
  "cooldown_turns": 5,
  "mana_cost": 0,
  "effects": [
    { "type": "buff_cleanse", "stat": "armor", "magnitude": 3, "duration_turns": 3, "cleanse_dots": true }
  ],
  "allowed_classes": ["plague_doctor"],
  "requires_line_of_sight": false
}
```

**`class_skills` mapping:**
```json
"plague_doctor": ["auto_attack_ranged", "miasma", "plague_flask", "enfeeble", "inoculate"]
```

**Also update `auto_attack_ranged` allowed_classes** to include `"plague_doctor"`.

**Tests (Phase 23A):**
- Plague Doctor class loads from config with correct stats (HP 85, melee 8, ranged 12, armor 2, vision 7, range 5)
- Plague Doctor color is `#50C878` and shape is `flask`
- All 4 skills load from config with correct properties (miasma, plague_flask, enfeeble, inoculate)
- `class_skills["plague_doctor"]` maps to correct 5 skills (auto_attack_ranged + 4 class skills)
- `can_use_skill()` validates miasma for plague_doctor
- `can_use_skill()` validates plague_flask for plague_doctor
- `can_use_skill()` validates enfeeble for plague_doctor
- `can_use_skill()` validates inoculate for plague_doctor
- `can_use_skill()` rejects plague_doctor skills for non-plague_doctor classes
- Existing class tests still pass (regression check)

**Estimated tests:** 8–10

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass before proceeding.

---

### Phase 23B — Effect Handlers (Core Mechanics)

**Goal:** Implement 2 new effect type handlers (`aoe_damage_slow_targeted`, `buff_cleanse`), wire 2 existing skills (Plague Flask via `dot`, Enfeeble via `aoe_debuff`) through existing handlers, and connect all to the `resolve_skill_action()` dispatcher.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/skills.py` | Add `resolve_aoe_damage_slow_targeted()` handler (~60 lines) |
| `server/app/core/skills.py` | Add `resolve_buff_cleanse()` handler (~50 lines) |
| `server/app/core/skills.py` | Add 2 dispatcher branches in `resolve_skill_action()` |

#### Handler 1: `resolve_aoe_damage_slow_targeted()` (~60 lines)

```
Input:  player, target_x, target_y, skill_def, players, obstacles
Logic:  1. Validate target_x/target_y provided
        2. Range check (Chebyshev) from caster to target tile
        3. LOS check from caster to target tile
        4. Find all living enemies within radius of target tile
        5. Deal magic damage (50% armor) to each + apply slow debuff
        6. Apply cooldown
Output: ActionResult with hit count, total damage, slow count, kill tracking
```

#### Handler 2: `resolve_buff_cleanse()` (~50 lines)

```
Input:  player, skill_def, target_x, target_y, players, target_id
Logic:  1. Resolve target (self or ally, same as resolve_buff)
        2. Range check (Chebyshev) from caster to target
        3. Apply armor buff entry to target.active_buffs
        4. Strip all entries where type == "dot" from target.active_buffs
        5. Apply cooldown
Output: ActionResult with buff info + number of DoTs cleansed
```

#### Dispatcher Update

```python
# Add to resolve_skill_action():
elif effect_type == "aoe_damage_slow_targeted":
    return resolve_aoe_damage_slow_targeted(
        player, action.target_x, action.target_y, skill_def, players, obstacles
    )
elif effect_type == "buff_cleanse":
    return resolve_buff_cleanse(
        player, skill_def, action.target_x, action.target_y, players, target_id=tid
    )
```

**Tests (Phase 23B):**

*Miasma (aoe_damage_slow_targeted):*
- Miasma deals damage to enemies within radius of target tile
- Miasma does NOT damage allies within radius
- Miasma applies slow debuff to surviving enemies
- Miasma does NOT apply slow to killed enemies
- Miasma fails when target tile is out of range
- Miasma fails when no LOS to target tile
- Miasma applies cooldown after use
- Miasma with no enemies in radius succeeds (empty blast message)
- Miasma damage uses magic armor (50% effectiveness)
- Miasma respects `skill_damage_pct` and `magic_damage_pct` bonuses

*Plague Flask (dot — existing handler):*
- Plague Flask applies DoT to target (7 dmg/tick, 4 turns)
- Plague Flask refreshes duration on recast to same target
- Plague Flask fails when target is out of range
- Plague Flask fails when no LOS to target
- Plague Flask applies cooldown after use
- Plague Flask damage_per_tick is correct (7)

*Enfeeble (aoe_debuff — existing handler):*
- Enfeeble applies damage_dealt_multiplier debuff (0.75) to enemies in radius
- Enfeeble does NOT debuff allies
- Enfeeble refreshes debuff on recast (doesn't stack)
- Enfeeble fails when target tile is out of range
- Enfeeble fails when no LOS to target tile
- Enfeeble applies cooldown after use
- Enfeeble with no enemies in radius succeeds (empty blast message)

*Inoculate (buff_cleanse):*
- Inoculate grants +3 armor buff to target for 3 turns
- Inoculate cleanses active DoT effects from target
- Inoculate cleanses multiple DoTs simultaneously
- Inoculate works when target has no DoTs (just applies armor buff)
- Inoculate can target self
- Inoculate can target ally within range
- Inoculate fails when ally is out of range
- Inoculate applies cooldown after use

**Estimated tests:** 28–32

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass.

---

### Phase 23C — Buff System Integration (damage_dealt_multiplier)

**Goal:** Wire the new `damage_dealt_multiplier` debuff stat into the damage calculation pipeline so Enfeeble actually reduces enemy outgoing damage.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/skills.py` | Add `get_damage_dealt_multiplier()` helper function |
| `server/app/core/combat.py` | Apply `damage_dealt_multiplier` in `calculate_damage()` |
| `server/app/core/combat.py` | Apply `damage_dealt_multiplier` in `calculate_damage_simple()` |
| `server/app/core/combat.py` | Apply `damage_dealt_multiplier` in `calculate_ranged_damage()` |
| `server/app/core/combat.py` | Apply `damage_dealt_multiplier` in `calculate_ranged_damage_simple()` |

#### `get_damage_dealt_multiplier()` — New helper in skills.py

```python
def get_damage_dealt_multiplier(player: PlayerState) -> float:
    """Return the combined damage-dealt multiplier from all active debuffs.

    Phase 23C: Used by Enfeeble (damage_dealt_multiplier debuff).
    Values < 1.0 mean the unit deals LESS damage.
    Multiplicative stacking if multiple sources apply.
    """
    mult = 1.0
    for buff in player.active_buffs:
        if buff.get("stat") == "damage_dealt_multiplier":
            mult *= buff["magnitude"]
    return mult
```

#### Combat Pipeline Integration

In each of the 4 damage functions, after the existing `dmg_taken_mult` block, add:

```python
# Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble)
dmg_dealt_mult = get_damage_dealt_multiplier(attacker)
if dmg_dealt_mult != 1.0:
    final_damage = max(1, int(final_damage * dmg_dealt_mult))
```

Import `get_damage_dealt_multiplier` in the existing import lines where `get_damage_taken_multiplier` is already imported.

**Tests (Phase 23C):**

*damage_dealt_multiplier in melee:*
- Enfeebled attacker deals reduced melee damage (0.75×)
- Enfeebled attacker's melee damage minimum is still 1
- Enfeeble debuff expires and melee damage returns to normal
- damage_dealt_multiplier stacks multiplicatively with damage_taken_multiplier

*damage_dealt_multiplier in ranged:*
- Enfeebled attacker deals reduced ranged damage (0.75×)
- Enfeebled attacker's ranged damage minimum is still 1
- Enfeeble debuff expires and ranged damage returns to normal

*damage_dealt_multiplier in simple calcs:*
- calculate_damage_simple applies damage_dealt_multiplier
- calculate_ranged_damage_simple applies damage_dealt_multiplier

*Edge cases:*
- Multiple Enfeeble sources stack multiplicatively (0.75 × 0.75 = 0.5625)
- Both Enfeeble (damage_dealt_multiplier=0.75) and Dirge (damage_taken_multiplier=1.25) apply correctly together
- No crash when damage_dealt_multiplier is exactly 1.0 (no debuff)

**Estimated tests:** 18

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass.

---

### Phase 23D — AI Behavior (controller role)

**Goal:** Implement AI decision-making so Plague Doctor AI heroes and AI-controlled Plague Doctors play intelligently — prioritizing cluster debuffs, maintaining DoTs, and supporting allies.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/ai_skills.py` | Add `"plague_doctor": "controller"` to `_CLASS_ROLE_MAP` |
| `server/app/core/ai_skills.py` | Add `_controller_skill_logic()` function (~100 lines) |
| `server/app/core/ai_skills.py` | Add `"controller"` branch to `_decide_skill_usage()` dispatcher |

#### AI Decision Logic

```python
# Constants
_ENFEEBLE_MIN_ENEMIES = 2      # Minimum enemies in AoE to justify Enfeeble
_MIASMA_MIN_ENEMIES = 2        # Minimum enemies in AoE to justify Miasma
_INOCULATE_HP_THRESHOLD = 0.50 # Ally HP ratio below which Inoculate is considered

def _controller_skill_logic(ai, enemies, all_units, grid_width, grid_height, obstacles):
    """Controller role (Plague Doctor): debuff enemies, apply DoTs, support allies.

    Phase 23D implementation.

    Priority:
      1. Enfeeble:     2+ non-enfeebled enemies in AoE, off cooldown
      2. Miasma:       2+ enemies clustered within range, off cooldown
      3. Plague Flask:  enemy in range without active DoT (prefer highest HP)
      4. Inoculate:    ally with active DoT OR ally below 50% HP
      5. Return None → fall through to basic attack logic
    """

    # 1. Enfeeble — AoE debuff on enemy clusters
    #    Scan enemies, find best tile that hits 2+ un-enfeebled targets.
    #    Same scoring logic as Bard's Dirge of Weakness.

    # 2. Miasma — AoE damage + slow on clusters
    #    Find best tile that hits 2+ enemies within radius.
    #    LOS + range check to center tile.

    # 3. Plague Flask — single-target DoT on highest-HP un-poisoned enemy
    #    Filter enemies: in range, LOS, no active DoT from us.
    #    Pick highest HP to maximize DoT value.

    # 4. Inoculate — buff+cleanse ally with worst condition
    #    Priority: ally with active DoT > ally below 50% HP > self with DoT.

    # 5. Fallback: return None
    return None
```

#### Dispatcher Update

```python
# In _decide_skill_usage():
elif role == "controller":
    return _controller_skill_logic(ai, enemies, all_units, grid_width, grid_height, obstacles)
```

**Tests (Phase 23D):**
- Plague Doctor AI uses Enfeeble when 2+ enemies in AoE radius
- Plague Doctor AI skips Enfeeble when fewer than 2 enemies in range
- Plague Doctor AI skips Enfeeble when enemies already have enfeeble debuff
- Plague Doctor AI uses Miasma when 2+ enemies clustered
- Plague Doctor AI uses Plague Flask on enemy without active DoT
- Plague Doctor AI prefers highest-HP enemy for Plague Flask
- Plague Doctor AI uses Inoculate on ally with active DoT
- Plague Doctor AI uses Inoculate on ally below 50% HP (no DoT)
- Plague Doctor AI falls back to auto-attack when all skills on cooldown
- Plague Doctor AI positioning stays at midline (not charging)
- Plague Doctor AI is correctly mapped in `_CLASS_ROLE_MAP`
- Plague Doctor AI dispatches through `_decide_skill_usage()` correctly

**Estimated tests:** 10–12

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass.

---

### Phase 23E — Frontend Integration (Rendering + UI)

**Goal:** Add Plague Doctor to the client — shape rendering, class selection, colors, icons, inventory portrait.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/canvas/renderConstants.js` | Add plague_doctor to `CLASS_COLORS`, `CLASS_SHAPES`, `CLASS_NAMES` |
| `client/src/canvas/unitRenderer.js` | Add `flask` shape rendering case |
| `client/src/components/WaitingRoom/WaitingRoom.jsx` | Add flask icon to shape map |
| `client/src/components/Inventory/Inventory.jsx` | Add flask SVG path to `CLASS_SHAPE_PATHS` |
| `client/src/components/Inventory/Inventory.jsx` | Add enfeeble/inoculate buff names to `formatBuffName` / `formatBuffEffect` |

#### renderConstants.js additions

```javascript
// CLASS_COLORS
plague_doctor: '#50C878',

// CLASS_SHAPES
plague_doctor: 'flask',

// CLASS_NAMES
plague_doctor: 'Plague Doctor',
```

#### unitRenderer.js — Flask Shape

```javascript
case 'flask': {
  // Alchemical flask — round bottom tapering to a narrow neck with a small opening
  const r = halfTile * 0.75;
  ctx.beginPath();
  // Neck (narrow top)
  ctx.moveTo(cx - r * 0.2, cy - r);
  ctx.lineTo(cx + r * 0.2, cy - r);
  ctx.lineTo(cx + r * 0.2, cy - r * 0.5);
  // Shoulders
  ctx.lineTo(cx + r * 0.7, cy - r * 0.2);
  // Round body
  ctx.quadraticCurveTo(cx + r, cy + r * 0.3, cx + r * 0.5, cy + r * 0.8);
  ctx.lineTo(cx - r * 0.5, cy + r * 0.8);
  ctx.quadraticCurveTo(cx - r, cy + r * 0.3, cx - r * 0.7, cy - r * 0.2);
  // Back to neck
  ctx.lineTo(cx - r * 0.2, cy - r * 0.5);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  break;
}
```

#### WaitingRoom.jsx — Shape icon

```javascript
cls.shape === 'flask' ? '🧪' : ...
```

#### Inventory.jsx — SVG portrait path

```javascript
flask: <path d="M 42 10 L 58 10 L 58 25 L 72 38 Q 82 55 72 75 L 68 82 L 32 82 L 28 75 Q 18 55 28 38 L 42 25 Z" />,
```

#### Inventory.jsx — Buff name formatting

```javascript
// formatBuffName:
enfeeble: 'Enfeeble',
inoculate: 'Inoculate',
miasma: 'Miasma',
plague_flask: 'Plague Flask',

// formatBuffEffect:
if (buff.stat === 'damage_dealt_multiplier') {
  const pct = Math.round((1 - buff.magnitude) * 100);
  return `-${pct}% damage dealt`;
}
```

**Tests (Phase 23E):** Visual verification — manual checklist:
- [ ] Plague Doctor appears in class selection screen
- [ ] Flask shape renders correctly on canvas (emerald green)
- [ ] Color (#50C878) displays correctly and is distinguishable from Ranger green
- [ ] Plague Doctor name shows in nameplate
- [ ] Inventory portrait shows flask
- [ ] Enfeeble debuff icon displays correctly in HUD (shows "-25% damage dealt")
- [ ] Miasma slow icon displays correctly in HUD
- [ ] Inoculate buff icon displays correctly (+3 armor)
- [ ] Skill icons appear in bottom bar with correct names

---

### Phase 23F — Particle Effects & Audio (Polish)

**Goal:** Add visual and audio feedback for Plague Doctor skills.

**Files Modified:**
| File | Change |
|------|--------|
| `client/public/particle-presets/skills.json` | Add plague_doctor skill effects |
| `client/public/particle-presets/buffs.json` | Add enfeeble debuff aura + inoculate buff aura |
| `client/public/audio-effects.json` | Add plague_doctor audio triggers |
| `client/src/audio/soundMap.js` | Add plague_doctor sound mappings |

#### Particle Effects

| Skill | Particle Effect | Description |
|-------|----------------|-------------|
| Miasma | `plague-miasma-cloud` | Sickly green-yellow expanding toxic cloud at target location, particles drift outward and fade |
| Plague Flask | `plague-flask-impact` | Small emerald splash on hit, trailing green poison drips, green particle DoT ticks |
| Enfeeble | `plague-enfeeble-wave` | Murky green shockwave expanding from target tile, dark wisps clinging to affected enemies |
| Inoculate | `plague-inoculate-heal` | Clean white-green upward sparkles on target, green motes ascending (cleansing visual) |

#### Audio

| Skill | Sound | Category |
|-------|-------|----------|
| Miasma | Glass breaking + hissing gas release | skills |
| Plague Flask | Cork pop + liquid splash + sizzle | skills |
| Enfeeble | Low rumbling whoosh + distant groans | skills |
| Inoculate | Clean chime + liquid pouring | skills |

**Tests (Phase 23F):** Manual verification only.
- [ ] Each skill triggers correct particle effect
- [ ] Enfeeble debuff aura visible on affected enemies (sickly green glow)
- [ ] Inoculate buff aura visible on buffed ally (clean green shimmer)
- [ ] Miasma slow icon visible on slowed enemies
- [ ] Audio plays on skill use
- [ ] No console errors from missing assets

---

### Phase 23G — Sprite Integration

**Goal:** Add Plague Doctor sprite variants from the character sheet atlas.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/canvas/SpriteLoader.js` | Add `plague_doctor`, `plague_doctor_2`, `plague_doctor_3` to `SPRITE_MAP`; add `plague_doctor: 3` to `HERO_SPRITE_VARIANTS` |
| `Assets/Sprites/Combined Character Sheet 1-atlas (3).json` | Fixed `Witch_Doctor3` category from `"Monsters"` → `"Heros"` |

**Sprite Mapping (Witch_Doctor → plague_doctor):**

| Atlas Name | SPRITE_MAP Key | Position | Variant |
|------------|---------------|----------|---------|
| `Witch_Doctor1` | `plague_doctor` | x:2160, y:2430 | 1 (default) |
| `Witch_Doctor2` | `plague_doctor_2` | x:2160, y:2700 | 2 |
| `Witch_Doctor3` | `plague_doctor_3` | x:2430, y:2430 | 3 |

All sprites are 270×270 on the 4096×3072 sheet. 3 variants available — same as Blood Knight (4) tier, more than Bard (1).

---

## Implementation Order & Dependencies

```
Phase 23A (Config)           ← No dependencies, pure data
    ↓
Phase 23B (Effect Handlers)  ← Depends on 23A (needs skill definitions)
    ↓
Phase 23C (Buff Integration) ← Depends on 23B (needs enfeeble debuff stat wired)
    ↓
Phase 23D (AI Behavior)      ← Depends on 23B (needs handlers working)
    ↓
Phase 23E (Frontend)         ← Depends on 23A — can parallel with 23C/23D
    ↓
Phase 23F (Polish)           ← Depends on 23E (needs rendering working)
    ↓
Phase 23G (Sprites)          ← Optional, last
```

**Parallelizable:** 23C + 23D can run in parallel after 23B. 23E can start after 23A.

---

## Test Summary

| Phase | Test Count | Focus |
|-------|:----------:|-------|
| 23A — Config | 61 | Class/skill loading, validation |
| 23B — Effect Handlers | 28–32 | Handler logic: Miasma, Plague Flask, Enfeeble, Inoculate |
| 23C — Buff Integration | 18 | damage_dealt_multiplier in damage pipeline + skill handlers |
| 23D — AI Behavior | 10–12 | AI decision logic for controller role |
| 23E — Frontend | 0 (manual) | Visual verification |
| 23F — Polish | 0 (manual) | Particles, audio |
| **Total** | **56–66** | |

---

## Tuning Levers

| Parameter | Initial Value | Reduce If... | Increase If... |
|-----------|:------------:|--------------|----------------|
| Plague Doctor HP | 85 | Too survivable for a controller | Dies too quickly before skills matter |
| Plague Doctor Ranged Damage | 12 | Auto-attack DPS is too competitive | Can't contribute when skills are on CD |
| Miasma base damage | 10 | AoE burst is too strong vs clusters | Not impactful enough to justify CD 6 |
| Miasma radius | 2 | Too easy to hit entire team | Hard to hit 2+ enemies consistently |
| Miasma slow duration | 2 turns | Slow is too oppressive | Enemies recover before party capitalizes |
| Miasma cooldown | 6 turns | Too spammable (oppressive) | Too long — class feels inactive |
| Plague Flask damage/tick | 7 | Outclasses Wither (8) in DPT | Not enough pressure as main damage tool |
| Plague Flask duration | 4 turns | Total damage too high | DoT doesn't last long enough to matter |
| Plague Flask cooldown | 5 turns | Too much DoT uptime | Can't keep at least 1 target poisoned |
| Enfeeble magnitude | 0.75 (25% reduction) | Tanks become unkillable with PD support | Damage reduction not noticeable |
| Enfeeble radius | 2 | Too easy to hit whole team | Hard to debuff meaningful targets |
| Enfeeble duration | 3 turns | Debuff window too long | Expires before party benefits |
| Enfeeble cooldown | 7 turns | Too much uptime for such strong effect | PD feels useless waiting for it |
| Inoculate armor bonus | 3 | Overshadows Confessor's Shield of Faith | Not worth the cooldown over other skills |
| Inoculate cooldown | 5 turns | DoT cleanse available too often | Can't react to enemy DoTs in time |

### Known Balance Risks

1. **Enfeeble + Confessor = unkillable parties:** A party with both a Confessor (healing) and Plague Doctor (damage reduction) may be extremely hard to kill. The Enfeeble magnitude (25%) is intentionally lower than Dirge's bonus (25%) to partially offset this, but the combination with healing could be oppressive. **Mitigation:** Enfeeble's 7-turn cooldown limits uptime to ~43%; increase cooldown to 8 if parties are too durable.

2. **Enfeeble + Bard Dirge stacking:** If Enfeeble (-25% damage dealt) and Dirge (+25% damage taken) are both active, the combined effect is enemies dealing 0.75× damage that then gets amplified 1.25× on the defender... which nets to 0.9375× (only 6% reduction). This is actually fine — the danger would be if they stacked additively. Verify multiplicative stacking in tests.

3. **Low personal DPS in solo play:** The Plague Doctor is designed as a multiplayer class. In solo PvE, the low personal DPS (worst among ranged) may feel frustrating. The DoTs (Plague Flask) and auto-attacks are the solo fallback, but the class will clearly underperform compared to a Ranger or Mage when alone. **Mitigation:** This is acceptable — the class fantasy is "team force multiplier." Document this expectation.

---

## Future Enhancements (Post-Phase 23)

- **Contagion mechanic:** Plague Flask DoT spreads to adjacent enemies when the target dies. Would require a new "on-death propagation" system.
- ~~**Persistent ground zones:** Miasma leaves a lingering toxic cloud on the tile for 2-3 turns. Would require a new "terrain effect" system.~~ ✅ Implemented — see Miasma Visual Zone changelog entry
- **Plague Doctor enemy type:** Add a Plague Doctor NPC enemy in dungeons that uses Miasma and Plague Flask — would reuse all existing handlers.
- **Antidote consumable item:** A single-use item that does what Inoculate does, available to all classes from the merchant.

---

## Phase Checklist

- [x] **23A** — Plague Doctor added to `classes_config.json`
- [x] **23A** — 4 skills added to `skills_config.json` (miasma, plague_flask, enfeeble, inoculate)
- [x] **23A** — `class_skills.plague_doctor` mapping added
- [x] **23A** — `auto_attack_ranged.allowed_classes` includes plague_doctor
- [x] **23A** — Config loading tests pass (61 tests)
- [x] **23B** — `resolve_aoe_damage_slow_targeted()` handler implemented
- [x] **23B** — `resolve_buff_cleanse()` handler implemented
- [x] **23B** — `resolve_skill_action()` dispatcher updated with 2 new branches
- [x] **23B** — All handler tests pass (Miasma, Plague Flask, Enfeeble, Inoculate) — 38 tests
- [x] **23C** — `get_damage_dealt_multiplier()` helper added to skills.py
- [x] **23C** — `damage_dealt_multiplier` applied in `calculate_damage()`
- [x] **23C** — `damage_dealt_multiplier` applied in `calculate_damage_simple()`
- [x] **23C** — `damage_dealt_multiplier` applied in `calculate_ranged_damage()`
- [x] **23C** — `damage_dealt_multiplier` applied in `calculate_ranged_damage_simple()`
- [x] **23C** — `damage_dealt_multiplier` applied in 11 skill damage handlers (resolve_multi_hit, resolve_ranged_skill, resolve_holy_damage, resolve_stun_damage, resolve_aoe_damage, resolve_ranged_damage_slow, resolve_magic_damage, resolve_aoe_damage_slow, resolve_lifesteal_damage, resolve_lifesteal_aoe, resolve_aoe_damage_slow_targeted)
- [x] **23C** — Buff integration tests pass (18 tests)
- [ ] **23D** — `_controller_skill_logic()` implemented
- [ ] **23D** — `_CLASS_ROLE_MAP` updated with `"plague_doctor": "controller"`
- [ ] **23D** — `_decide_skill_usage()` dispatcher updated with `"controller"` branch
- [ ] **23D** — AI behavior tests pass
- [x] **23E** — `renderConstants.js` updated (color, shape, name)
- [x] **23E** — Flask shape renders in `unitRenderer.js`
- [x] **23E** — WaitingRoom class select shows Plague Doctor with 🧪 icon
- [x] **23E** — Inventory portrait shows flask + buff names updated
- [x] **23E** — HeaderBar.jsx CLASS_COLORS, CLASS_NAMES, buff formatting updated
- [x] **23E** — MeterBar.jsx CLASS_COLORS updated
- [x] **23F** — Particle effects added (miasma cloud, flask splash, enfeeble wave, inoculate sparkle)
- [x] **23F** — Audio triggers added (4 skills)
- [x] **23G** — Sprite variants mapped (3 Witch_Doctor sprites → plague_doctor, plague_doctor_2, plague_doctor_3)
- [ ] Balance pass after playtesting

---

## Post-Implementation Cleanup

After all phases complete:

1. **Update `README.md`:**
   - Update class count from "6 Playable Classes" to include Plague Doctor (should be 9 with Bard + Blood Knight)
   - Add Phase 23 to the Documentation → Phase Specs list
   - Update the status line at the top
   - Update the test count

2. **Update `docs/Current Phase.md`:**
   - Add Phase 23 milestone entry with test counts

3. **Update `docs/Game stats references/game-balance-reference.md`:**
   - Add Plague Doctor stat block
   - Add Plague Doctor to class comparison table
   - Add Plague Doctor skills to skills section
   - Add auto-attack and TTK calculations

4. **Update `docs/new-class-implementation-template.md`:**
   - Update CURRENT CLASS STAT REFERENCE comment to include Plague Doctor
   - Add `flask` to existing shapes list
   - Add `damage_dealt_multiplier` to existing effect types list if not already covered

5. **Final test run:**
   - `pytest server/tests/` — ALL tests pass, zero failures
   - Record final test count

---

## Fix Log

### Fix 1 — Plague Doctor Walking Into Melee (March 7, 2026)

**Problem:** Plague Doctor AI hero was frequently walking into melee range and getting nearly killed. Observed repeatedly in gameplay — the Plague Doctor would charge toward enemies when skills were on cooldown instead of staying at midline range.

**Root Cause:** The `"controller"` role (added in Phase 23D for `_CLASS_ROLE_MAP` and `_controller_skill_logic()`) was never integrated into the **stance movement code** in `ai_stances.py`. When all skills were on cooldown, the skill decision returned `None` and the stance handler took over. Since `"controller"` was not recognized as a support or ranged role, the Plague Doctor:

1. **Did NOT kite** — ranged kiting (Phase 8K-3) only applied to `ranged_dps`, `scout`, `caster_dps`. The controller role was excluded, so the Plague Doctor never stepped back when enemies got within 2 tiles.
2. **Rushed into melee** — The "close enough to rush" check (`not is_support and not is_ranged_role and dist <= 3`) evaluated to `True` for controller, causing the Plague Doctor to path directly toward enemies within 3 tiles.
3. **Moved toward enemies, not allies** — Only `"support"` and `"offensive_support"` used `_support_move_preference()` to stay grouped with allies. Controller moved toward the enemy target instead.
4. **Low retreat threshold** — No `_RETREAT_THRESHOLDS` entry for `"controller"`, so it defaulted to 0.25 (25% HP = ~21 HP). For an 85 HP squishy caster, this was far too low.

**Files Modified:**

| File | Change |
|------|--------|
| `server/app/core/ai_stances.py` | Added `"controller": 0.30` to `_RETREAT_THRESHOLDS` (retreat at 30% HP like caster_dps) |
| `server/app/core/ai_stances.py` | Added `"controller"` to `is_support` check in `_decide_follow_action()` — now uses `_support_move_preference()` to stay near allies |
| `server/app/core/ai_stances.py` | Added `"controller"` to `is_ranged_role` check in `_decide_follow_action()` — now kites at dist <= 2 and won't rush melee at dist <= 3 |
| `server/app/core/ai_stances.py` | Added `"controller"` to `is_ranged_role` check in `_decide_aggressive_stance_action()` — same kiting + no melee rush fix |

**Bonus fix:** Also added `"totemic_support"` (Shaman) to all the same checks — the Shaman had the identical undetected bug since it's also a backline support class that should never charge into melee.

**Expected behavior after fix:**
- Plague Doctor stays at midline range 3-4 tiles behind frontline
- Kites away when enemies get within 2 tiles
- Never rushes toward enemies at close range
- Prefers positioning near allies over chasing enemies
- Retreats at 30% HP (~25 HP) instead of 25% (~21 HP) when out of potions

---

**Document Version:** 1.7
**Created:** March 6, 2026
**Last Updated:** March 8, 2026
**Status:** Phase 23G Complete + Fix 1 + Fix 2 + Miasma Visual Zone
**Prerequisites:** Phase 22 (Blood Knight) Complete

---

### Fix 2 — Plague Doctor Still Drifting Into Melee (March 8, 2026)

**Problem:** Despite Fix 1 adding `"controller"` to `is_ranged_role` and `is_support`, the Plague Doctor AI still drifted into melee range over multiple turns. Three deeper issues caused this:

1. **`_support_move_preference()` ignores enemy positions** — returns the nearest/most-injured ally's position with zero regard for enemies. If the nearest ally is a Crusader brawling in melee, the PD walks straight into the frontline to "stay grouped."
2. **3-turn ranged cooldown + 5-7 turn skill CDs = long idle windows** — After firing, the PD has nothing to do for ~3 turns but move, and that movement goes toward frontline allies per issue 1, progressively closing distance each turn.
3. **Kite threshold too tight (dist <= 2)** — For a range-5/85-HP controller, the enemy essentially had to be adjacent before the PD stepped back. Combined with the forward drift, the PD oscillated: walk forward 3 turns → kite back 1 tile → walk forward again.

**Root Cause Analysis (turn-by-turn):**
```
Turn 1: PD at dist 5 from enemy. Fires ranged. (ranged CD = 3, skills on CD)
Turn 2: dist 5. Can't shoot. Skills on CD. Walks toward ally → dist 4.
Turn 3: dist 4. Can't shoot. Skills on CD. Walks toward ally → dist 3.
Turn 4: dist 3. Ranged ready, fires. (but dist 3 < old kite threshold 2 → no kite)
Turn 5: dist 3. Can't shoot. Walks toward ally → dist 2. NOW kites back → dist 3.
Turn 6: dist 3. Repeat cycle — oscillating at melee frontier.
```

**Fixes Applied:**

| # | Fix | File | Detail |
|---|-----|------|--------|
| 2a | Widened kite threshold for controller | `ai_stances.py` | `_kite_threshold = 3 if role == "controller" else 2` — PD now starts backing off at dist 3 instead of dist 2. Applied in both `_decide_follow_action()` and `_decide_aggressive_stance_action()`. |
| 2b | Controller holds position when idle | `ai_stances.py` | New check: when `role == "controller"` and `ranged_cd > 0` and nearest enemy is within 4 tiles → return `WAIT` instead of walking toward ally. Prevents the "slowly creeping forward through idle turns" problem. Only advances toward allies when enemies are far (dist > 4). |
| 3 | Miasma as defensive slow on single target | `ai_skills.py` | Miasma now fires on 1 enemy when that enemy is within 4 tiles (defensive slow). Normal 2+ cluster threshold still applies at safe distance. Gives the PD something useful to do between cooldowns instead of being idle. |

**Expected behavior after fix:**
```
Turn 1: PD at dist 5 from enemy. Fires ranged. (ranged CD = 3)
Turn 2: dist 5. Can't shoot. Enemy in range (dist <= 4)? No (5 > 4). Walks toward ally.
Turn 3: dist 4. Can't shoot. Enemy within 4 → WAIT. Holds position.
Turn 4: dist 4. Ranged ready, fires.
Turn 5: dist 4. Can't shoot. Enemy within 4 → WAIT. Holds position.
   ... PD maintains dist 4-5, exactly where a range-5 controller should be.

If enemy closes to dist 3 → kite triggers → PD steps back to dist 4.
If only 1 enemy at dist 3-4 → Miasma fires as defensive slow.
```

**Tests Added:** 10 tests in `server/tests/test_phase23_fix2_plague_doctor_kite.py`
- `TestControllerWidenedKite` (2 tests) — PD kites at dist 3 in follow + aggressive
- `TestControllerHoldPosition` (4 tests) — WAIT when idle + enemies medium-range, MOVE when enemies far, RANGED_ATTACK when off CD
- `TestMiasmaSingleTargetSlow` (4 tests) — fires on 1 close enemy, skips 1 far enemy, still fires on 2+ far, enfeeble still prioritized

**Test updated:** `test_phase23d_plague_doctor_ai.py::TestMiasma::test_skips_miasma_with_one_enemy` — enemy moved from dist 3 to dist 5 so it correctly tests the "no miasma on single far target" behavior without conflicting with Fix 3.

---

### Miasma / Enfeeble Persistent AoE Ground Zone Visual (March 7, 2026)

**Problem:** Miasma has a 2-tile radius AoE but there was no visual indicator of the affected area. The one-shot burst particle (`plague-miasma-cloud`) had a `spawnRadius` of only 6px (well under 1 tile) and played for ~1.2 seconds then vanished. Players had no way to see where the toxic cloud actually was or how large the zone was. Same issue for Enfeeble's 2-tile radius.

**Solution:** Implemented a persistent ground zone overlay system (modeled on the Shaman totem radius indicator) plus improved particles.

**Changes:**

| File | Change |
|------|--------|
| `client/src/context/GameStateContext.jsx` | Added `groundZones: []` to initial state |
| `client/src/context/reducers/combatReducer.js` | `TURN_RESULT`: scans actions for Miasma/Enfeeble hits, creates zone objects with position/radius/duration, decrements each turn, removes expired zones. Resets on `MATCH_START` and `FLOOR_ADVANCE` |
| `client/src/canvas/overlayRenderer.js` | New `drawGroundZones()` function — renders pulsing translucent fill (two concentric layers), rotating dashed border ring, 6 animated orbiting gas wisps, center glow, turn counter. Fade-out on last turn |
| `client/src/canvas/ArenaRenderer.js` | `drawGroundZones` imported, re-exported, called in `renderFrame()` (drawn after ground items, before units). Added `groundZones` parameter |
| `client/src/components/Arena/Arena.jsx` | `groundZones` threaded through state → renderParams → dirty deps → renderFrame call. Continuous rAF redraws when zones/totems exist. `useEffect` calls `updateGroundZones()` on particle manager |
| `client/src/canvas/particles/ParticleManager.js` | `_zoneEmitters` map + `updateGroundZones()` method creates/destroys looping emitters matched to active zones. `_cleanupZoneEmitters()` in tick loop |
| `client/public/particle-presets/skills.json` | `plague-miasma-cloud` v2: `spawnRadius` 6→48px, `burstCount` 50→80, `duration` 1.2→2.5s, particles drift upward. `plague-miasma-wisps` v2: ring expanded to 56px, longer lifetimes. Two new looping presets: `plague-miasma-zone-ambient` (green, 12/sec), `plague-enfeeble-zone-ambient` (purple, 8/sec) |

**Zone colors:**
- Miasma: `#50C878` (emerald green) — 2-tile radius, 2-turn duration
- Enfeeble: `#8844aa` (dark purple) — 2-tile radius, 3-turn duration
