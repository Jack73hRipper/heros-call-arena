# Phase 25 — Revenant Class (Retaliation Tank / Undying Warrior)

**Created:** March 2026
**Status:** Phase 25G Complete
**Previous:** Phase 24 (Tooltip Revamp)
**Goal:** Add the Revenant as the 10th playable class — an undying warrior that punishes attackers through retaliation damage, thorns, and a signature "cheat death" mechanic. Fills the second Tank slot with a fundamentally different playstyle from Crusader: where the Crusader is a defensive wall (armor stacking, shielding, AoE heal), the Revenant is a **threat through punishment** — enemies that focus the Revenant are hurt, and enemies that ignore the Revenant face an unkillable taunter.

---

## Overview

A cursed warrior who has already died once and refuses to die again. Bound between life and death, the Revenant feeds on the damage it receives — every blow struck against it exacts a toll in returned pain, and when finally brought low, it defies death itself and rises again. In the grimdark dungeon, the Revenant is the nightmare at the front of the party: a corpse-knight that won't stop coming.

**Role:** Retaliation Tank

### Design Pillars

1. **Punishment over Prevention** — The Crusader prevents damage (high armor, Bulwark, Shield of Faith). The Revenant *takes* damage but makes enemies pay for every hit. Different defensive philosophy — same result.
2. **Cheat Death Identity** — The signature skill. One revival per long cooldown. This is the skill that defines the Revenant and creates unforgettable gameplay moments — you watch it drop, then it stands back up.
3. **Melee Commitment** — Zero ranged capability, same philosophy as Crusader and Blood Knight. Revenants close the gap and stay engaged.
4. **Frontline Threat** — Even without massive DPS, enemies must deal with the Revenant because ignoring it means eating taunts and thorns. The Revenant forces attention.
5. **Grimdark Undead Fantasy** — Bone armor, spectral glow, rising from death. Every skill should feel like dark necromantic power fueling an unstoppable advance.

---

## Base Stats

| Stat | Value | Rationale |
|------|-------|-----------|
| **HP** | 130 | Second highest after Crusader (150). Needs to be durable enough to absorb damage and feed thorns, but not as raw-tanky as the pure defensive tank. |
| **Melee Damage** | 14 | Moderate-strong melee. Below Crusader (20) and Blood Knight (16) — the Revenant's damage comes from skills and thorns, not raw auto-attacks. Above Inquisitor (10) and Bard (10). |
| **Ranged Damage** | 0 | Pure melee. No ranged capability — must close distance. |
| **Armor** | 5 | Medium armor — same as Hexblade. Noticeably less than Crusader (8). The Revenant *wants* to take some damage to trigger thorns and low-HP mechanics. Too much armor would undermine the design. |
| **Vision Range** | 5 | Frontline tunnel vision — same as Crusader. Tanks see close, scouts see far. |
| **Ranged Range** | 0 | Melee only. |
| **Allowed Weapons** | `["melee", "hybrid"]` | Heavy melee weapons, cursed greatswords, hybrid implements. |
| **Color** | `#708090` | Slate gray — spectral, deathly. Distinct from all existing colors (blue Crusader, dark red Blood Knight, etc.). Evokes tombstones and ghosts. |
| **Shape** | `coffin` | A coffin/sarcophagus silhouette — immediately communicates the undead tank fantasy. Unique from all existing shapes (square, circle, triangle, diamond, star, hexagon, crescent, shield, flask). |

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
 REVENANT ......   130      14       0      5       5      0   Retaliation Tank
```

**Design notes:**
- HP 130 is second only to Crusader (150) — firmly in the "tank" tier. Combined with cheat death, the Revenant's effective HP is much higher.
- Melee 14 is respectable (4th highest) but not scary — the Revenant's threat comes from skills and thorns, not auto-attack DPS.
- Armor 5 is deliberately below Crusader (8) — the Revenant trades raw mitigation for retaliation. Taking damage is part of the plan.
- Vision 5 matches Crusader — both tanks operate at the frontline and rely on scouts for intel.

### Auto-Attack Damage (1.15× multiplier)

```
 Revenant ...... 14 × 1.15 = 16 melee per hit
```

This places Revenant 4th in auto-attack damage behind Crusader (23), Ranger (21 ranged), and Blood Knight (18). The Revenant's total damage output is supplemented significantly by passive thorns and Grave Thorns active reflection.

---

## Skills

### Skill Overview

| Slot | Skill | Effect Type | Target | Range | Cooldown | Summary |
|:----:|-------|------------|--------|:-----:|:--------:|---------|
| 0 | Auto Attack (Melee) | melee_damage | entity | 1 | 0 | 1.15× melee damage (16) |
| 1 | Grave Thorns | `thorns_buff` (**NEW**) | self | 0 | 5 | Reflect 10 damage per hit received for 3 turns |
| 2 | Grave Chains | `ranged_taunt` (**NEW**) | entity | 3 | 5 | Taunt enemy for 3 turns — spectral chains force them to attack you |
| 3 | Undying Will | `cheat_death` (**NEW**) | self | 0 | 10 | When HP reaches 0 within 5 turns, revive with 30% HP instead |
| 4 | Soul Rend | stun_damage (existing) | entity | 1 | 5 | 1.2× melee damage + slow 2 turns |

### Skill Details

#### Grave Thorns 🦴 (Self-Buff — Damage Reflection Aura)

```
Effect Type:   thorns_buff (NEW — based on ward/shield_charges handler)
Targeting:     self
Radius:        — (self only)
Range:         — (self-cast)
Cooldown:      5 turns
LOS Required:  No
Effect:        For 3 turns, any enemy that hits the Revenant with a melee or ranged
               attack takes 10 flat damage in return. No charge limit — all attacks
               during the duration trigger thorns. Does not reduce incoming damage.
```

**Design:** The bread-and-butter retaliation tool. Unlike Hexblade's Ward (reflect with charge limits), Grave Thorns has infinite procs but lower per-hit damage and shorter duration. This rewards being focused by multiple enemies — a pack of 3 enemies hitting the Revenant takes 30 thorns damage per round. The Revenant *wants* to be surrounded.

**Damage/healing/effect examples:**
```
Thorns active, 3 enemies attacking Revenant per turn:
  3 × 10 = 30 thorns damage per turn (spread across attackers)
  Over 3 turns: 90 total thorns damage from buff alone

Thorns active, 1 enemy (boss) attacking:
  1 × 10 = 10 thorns damage per turn
  Over 3 turns: 30 total thorns damage

Compare to Ward (Hexblade): 3 charges × 8 reflect = 24 total max
Grave Thorns vs 3 enemies: 90 total — much higher ceiling but no damage absorption
```

**Implementation:** New handler `resolve_thorns_buff()`. Similar to Ward but applies a `thorns_active` buff with duration instead of charges. In the combat pipeline (`combat.py`), after applying damage to a target with `thorns_active` buff, deal flat thorns damage back to the attacker. ~40 lines for handler + ~15 lines for combat.py integration.

**Balance lever:** Thorns damage per hit (10), duration (3 turns), cooldown (5)

---

#### Grave Chains ⛓️ (Ranged Taunt — Spectral Binding)

```
Effect Type:   ranged_taunt (NEW — ranged taunt with forced_target buff)
Targeting:     entity (enemy within 3 tiles)
Radius:        — (single target)
Range:         3 tiles
Cooldown:      5 turns
LOS Required:  Yes
Effect:        Spectral chains erupt from the ground beneath the target enemy,
               binding their aggression to the Revenant. The target is taunted for
               3 turns (forced to attack the Revenant). No displacement — pure
               taunt at range.
```

**Design:** The Revenant's engage/threat tool. Spectral chains bind the enemy's aggression to the Revenant — a compulsion that forces them to path toward and attack the caster. This solves the Crusader's biggest weakness — ranged enemies kiting — by forcing them to close distance themselves. Combined with Grave Thorns, taunted enemies walk into melee and eat thorns for every hit. The enemy does the work of closing the gap.

**Damage/healing/effect examples:**
```
Ranger at distance 3: taunted 3 turns → must path toward and attack Revenant
  → Ranger forced to melee Revenant (9 dmg melee vs Revenant's 5 armor = 4 dmg/turn)
  → Meanwhile Revenant melee = 16 dmg vs Ranger's 2 armor = 14 dmg/turn
  → If Grave Thorns active: Ranger takes additional 10/hit

Mage at distance 2: taunted 3 turns → must close to melee range
  → Mage forced into melee (6 dmg melee vs 5 armor = 1 dmg/turn)
  → Revenant melee = 16 dmg vs Mage's 1 armor = 15 dmg/turn

Enemy behind a wall: taunted — will path around obstacles to reach Revenant
```

**Implementation:** New handler `resolve_ranged_taunt()`. Step 1: validate target is enemy, within range, LOS check. Step 2: apply taunt buff (`forced_target` = caster.id, `duration_turns` = 3). Step 3: set cooldown, log message. Reuses existing taunt buff structure — no forced movement, no pathfinding edge cases. ~25 lines total.

**Balance lever:** Taunt duration (3 turns), range (3), cooldown (5)

---

#### Undying Will 💀 (Cheat Death — Pre-Cast Resurrection)

```
Effect Type:   cheat_death (NEW — unique mechanic)
Targeting:     self
Radius:        — (self only)
Range:         — (self-cast)
Cooldown:      10 turns
LOS Required:  No
Effect:        Place a "cheat death" buff on self lasting 5 turns. If the Revenant's
               HP drops to 0 while this buff is active, instead of dying: cleanse
               the lethal damage, set HP to 30% of max HP, and remove the buff.
               If the buff expires without triggering, it's wasted (cooldown still spent).
```

**Design:** The Revenant's signature, identity-defining skill. This is the "oh my god they got back up" moment. The 10-turn cooldown is the longest in the game, and the 5-turn window means you must predict when you'll need it — cast it too early and it expires, cast it too late and you're already dead. This creates genuinely interesting pre-fight decision making.

**Damage/healing/effect examples:**
```
Revenant (130 max HP) casts Undying Will:
  → Buff active for 5 turns
  → Turn 3: Revenant takes lethal damage...
  → Instead of death: HP set to 130 × 0.30 = 39 HP
  → Buff removed. Cooldown starts (10 turns).

Effective HP calculation:
  Without Undying Will: 130 HP
  With Undying Will:    130 + 39 = 169 effective HP (exceeds Crusader's 150!)
  With armor 5: even more effective HP from reduction

Failure case: Revenant casts at full HP, never gets brought to 0 in 5 turns
  → Buff expires unused, 10-turn cooldown wasted
```

**Implementation:** New handler `resolve_cheat_death()`. Applies a `cheat_death` buff with `duration_turns: 5` and `revive_hp_pct: 0.30`. In the deaths phase (`deaths_phase.py`), before marking a player as dead, check for `cheat_death` buff. If present: set HP to `floor(max_hp * revive_hp_pct)`, remove the buff, add a combat log entry ("Revenant defies death!"), trigger a particle effect. ~30 lines handler + ~20 lines deaths_phase integration.

**Balance lever:** Revive HP percentage (30%), buff duration window (5 turns), cooldown (10)

---

#### Soul Rend ⚔️ (Melee Strike + Slow)

```
Effect Type:   stun_damage (EXISTING — reuse with slow variant, same as Shield Bash pattern)
Targeting:     entity (adjacent enemy)
Radius:        — (single target)
Range:         1 tile (melee)
Cooldown:      5 turns
LOS Required:  No
Effect:        Deal 1.2× melee damage to target. Apply 2-turn slow (prevents movement
               but allows attacks/skills).
```

**Design:** The Revenant's offensive/utility melee strike. Deals moderate damage and roots the enemy in place — preventing them from escaping once the taunt from Grave Chains wears off. The slow + taunt combo creates a "black hole" effect: a taunted enemy is forced to approach and attack, then gets slowed so they can't escape — stuck in melee with a thorns-buffed, potentially cheat-death-armed Revenant. Nightmare fuel.

**Damage/healing/effect examples:**
```
Revenant (14 melee) vs Ranger (2 armor):
  Raw: 14 × 1.2 = 17 damage (truncated)
  After armor: 17 - 2 = 15 final damage + 2-turn slow

Revenant (14 melee) vs Crusader (8 armor):
  Raw: 14 × 1.2 = 17 damage
  After armor: 17 - 8 = 9 final damage + 2-turn slow

With Crimson Veil combo (Bard Ballad: +30% all damage):
  Raw: (14 × 1.3) × 1.2 = 22 damage
  After armor (2): 22 - 2 = 20 final damage + 2-turn slow

Combo: Grave Chains → Soul Rend → enemy stuck in melee for ~5 turns
```

**Implementation:** Reuse the existing `stun_damage` handler pattern from Shield Bash, but apply "slow" instead of "stun" (slow allows attacks, stun prevents everything). This may require a minor variant or a parameter check (`slow_duration` vs `stun_duration`). If the handler already supports both, just wire it up. ~10 lines max.

**Balance lever:** Damage multiplier (1.2), slow duration (2 turns), cooldown (5)

---

### Complete Revenant Kit

```
Slot 0: Auto Attack (Melee) — 16 melee damage per hit (1.15×)
Slot 1: Grave Thorns — Reflect 10 damage per hit for 3 turns (CD 5)
Slot 2: Grave Chains — Taunt enemy for 3 turns at range 3 (CD 5)
Slot 3: Undying Will — Cheat death within 5 turns, revive at 30% HP (CD 10)
Slot 4: Soul Rend — 1.2× melee damage + 2-turn slow (CD 5)
```

---

## DPS Contribution Analysis

### Direct DPS (Personal)

```
Auto-attack:     16 damage per turn (vs 0 armor)
Soul Rend:       17 damage / 5 turns = 3.4 DPT
Grave Thorns:    0 direct DPS (retaliation only)
Grave Chains:    0 damage
Undying Will:    0 damage

Total auto + skill DPT: 16 + 3.4 = 19.4 DPT (vs 0 armor)

Compare:
  Crusader:     23 auto + ~6 DPT skills = ~29 DPT
  Blood Knight: 18 auto + ~10 DPT skills = ~28 DPT
  Hexblade:     17 auto + ~12 DPT skills = ~29 DPT
  Revenant:     16 auto + 3.4 DPT skills = ~19.4 DPT + thorns
```

### Retaliation DPS (Unique to Revenant)

```
Grave Thorns active, 2 enemies hitting Revenant:
  20 thorns damage per turn × 3 turns = 60 damage over CD cycle
  60 / 5 = 12 effective DPT from thorns

Total with thorns (vs 2 attackers): 19.4 + 12 = 31.4 DPT
Total with thorns (vs 3 attackers): 19.4 + 18 = 37.4 DPT

Conclusion: Revenant's total damage output scales with how many enemies focus them.
Low personal DPS is compensated by thorns in multi-enemy scenarios (PvE dungeon).
```

### Survivability Analysis

```
Effective HP without Undying Will:  130 HP + 5 armor
Effective HP with Undying Will:     130 + 39 = 169 HP + 5 armor
Crusader comparison:                150 HP + 8 armor (+ Bulwark for 16 armor total)

The Revenant is less tanky per turn but has a higher effective HP ceiling.
Crusader mitigates steadily; Revenant absorbs the big spike.
```

---

## AI Behavior (tank role variant)

### AI Role: `retaliation_tank`

The Revenant AI is an aggressive frontline anchor. It charges toward enemies, casts thorns proactively, uses Grave Chains to taunt ranged enemies into melee, and activates Undying Will when health gets dangerously low. Unlike the Crusader AI (which holds position and uses Bulwark defensively), the Revenant AI actively seeks engagement.

### Decision Priority

```
1. Undying Will → If HP < 40% and buff not already active, cast preemptively
2. Grave Thorns → If 2+ enemies within 2 tiles and buff not active, cast for max retaliation
3. Grave Chains → If a ranged enemy is within 3 tiles and not adjacent, taunt them
4. Soul Rend → If adjacent enemy exists and skill off cooldown, slow them
5. Auto-attack → Fallback, target nearest enemy
```

### Positioning

- **Aggressive approach** — moves toward nearest enemy cluster, prioritizing groups over singles
- Uses `_tank_move_preference()` (same as Crusader) to charge toward enemies
- Retreat condition: only retreats if HP < 20% AND Undying Will is on cooldown (no safety net)
- If Undying Will is available, never retreats (the safety net emboldens aggressive play)

### Smart Targeting Logic

```python
# Grave Chains targeting:
# Score each enemy by: is_ranged × 3 + distance_to_revenant + (is_squishy × 2)
# Taunt the highest-scoring ranged/squishy enemy
# Prioritize: Mage > Ranger > Bard > Confessor > others
```

---

## New Effect Types

### Summary

| Effect Type | Complexity | Based On | Handler |
|-------------|-----------|----------|---------|
| `thorns_buff` | Low | `ward` / `shield_charges` | `resolve_thorns_buff()` |
| `ranged_taunt` | Low | `taunt` (existing forced_target buff) | `resolve_ranged_taunt()` |
| `cheat_death` | Medium | `evasion` (buff with trigger) | `resolve_cheat_death()` |

### Effect Type Details

#### `thorns_buff` — Self-Buff: Reflect Damage Per Hit (Grave Thorns)

```python
def resolve_thorns_buff(player, action, skill_def, players, ...):
    """Apply a thorns aura — attackers take flat damage per hit."""
    # Step 1: Apply buff {"stat": "thorns_damage", "magnitude": 10, "duration_turns": 3}
    # Step 2: Set cooldown
    # Step 3: Return ActionResult (buff applied)
```

**Combat pipeline integration:**
In `combat.py`, after dealing melee/ranged damage to a target, check if the target has a `thorns_damage` buff. If yes, deal `buff.magnitude` flat damage back to the attacker (ignores armor — it's retaliation magic).

#### `ranged_taunt` — Ranged Taunt (Grave Chains)

```python
def resolve_ranged_taunt(player, action, skill_def, players, ...):
    """Taunt an enemy at range — spectral chains force them to attack the caster."""
    # Step 1: Validate target is enemy, within range, LOS check
    # Step 2: Apply taunt buff (forced_target = caster.id, duration_turns = 3)
    # Step 3: Set cooldown
    # Step 4: Return ActionResult (taunt applied)
```

#### `cheat_death` — Pre-Cast Death Prevention (Undying Will)

```python
def resolve_cheat_death(player, action, skill_def, players, ...):
    """Place a cheat-death buff on self. If lethal damage is received, revive instead."""
    # Step 1: Apply buff {"stat": "cheat_death", "revive_hp_pct": 0.30, "duration_turns": 5}
    # Step 2: Set cooldown
    # Step 3: Return ActionResult (buff applied)
```

**Deaths phase integration:**
In `deaths_phase.py`, before marking a player as dead (HP <= 0), check for `cheat_death` buff. If present: set `player.hp = floor(player.max_hp * revive_hp_pct)`, remove the buff, add combat log entry, trigger particle effect — do NOT mark as dead.

### Buff/Debuff System Integration

**New stat: `thorns_damage`**

Locations that must be updated:
1. `server/app/core/combat.py` — `apply_melee_damage()` / `apply_ranged_damage()` — after dealing damage, check target for `thorns_damage` buff and deal flat damage back to attacker
2. `server/app/core/turn_phases/buffs_phase.py` — tick down `thorns_damage` buff duration like any other buff

**New stat: `cheat_death`**

Locations that must be updated:
1. `server/app/core/turn_phases/deaths_phase.py` — before marking player dead, check for `cheat_death` buff
2. `server/app/core/turn_phases/buffs_phase.py` — tick down `cheat_death` buff duration

**New mechanic: ranged taunt**

No new locations required — reuses existing `forced_target` taunt buff structure. The only difference from melee-range taunt is that `resolve_ranged_taunt()` validates a longer range (3 tiles) and requires LOS. No forced movement, no pathfinding changes.

---

## Implementation Phases

### Phase 25A — Config & Data Model (Foundation)

**Goal:** Add Revenant to classes and skills configs. Wire up the data layer. Zero logic changes.

**Files Modified:**
| File | Change |
|------|--------|
| `server/configs/classes_config.json` | Add `revenant` class definition |
| `server/configs/skills_config.json` | Add 4 skills + `class_skills.revenant` mapping |

**Config: `classes_config.json`**
```json
"revenant": {
  "class_id": "revenant",
  "name": "Revenant",
  "role": "Retaliation Tank",
  "description": "Undying warrior that punishes attackers with thorns and defies death itself. Takes damage deliberately to retaliate — the more enemies focus it, the deadlier it becomes.",
  "base_hp": 130,
  "base_melee_damage": 14,
  "base_ranged_damage": 0,
  "base_armor": 5,
  "base_vision_range": 5,
  "ranged_range": 0,
  "allowed_weapon_categories": ["melee", "hybrid"],
  "color": "#708090",
  "shape": "coffin"
}
```

**Config: `skills_config.json`** — 4 new skills:
```json
"grave_thorns": {
  "skill_id": "grave_thorns",
  "name": "Grave Thorns",
  "description": "Reflect 10 damage per hit received for 3 turns.",
  "flavor": "Bone shards erupt from dead flesh — every blow draws blood from the attacker.",
  "icon": "🦴",
  "targeting": "self",
  "range": 0,
  "cooldown_turns": 5,
  "mana_cost": 0,
  "effects": [
    { "type": "thorns_buff", "thorns_damage": 10, "duration_turns": 3 }
  ],
  "allowed_classes": ["revenant"],
  "requires_line_of_sight": false
},
"grave_chains": {
  "skill_id": "grave_chains",
  "name": "Grave Chains",
  "description": "Taunt an enemy for 3 turns — spectral chains force them to attack you.",
  "flavor": "Chains erupt from hallowed ground, dragging at the enemy's will — the grave demands their attention.",
  "icon": "⛓️",
  "targeting": "enemy_ranged",
  "range": 3,
  "cooldown_turns": 5,
  "mana_cost": 0,
  "effects": [
    { "type": "ranged_taunt", "taunt_duration": 3 }
  ],
  "allowed_classes": ["revenant"],
  "requires_line_of_sight": true
},
"undying_will": {
  "skill_id": "undying_will",
  "name": "Undying Will",
  "description": "If you would die within 5 turns, revive at 30% HP instead.",
  "flavor": "Death is a door — and the Revenant holds the key.",
  "icon": "💀",
  "targeting": "self",
  "range": 0,
  "cooldown_turns": 10,
  "mana_cost": 0,
  "effects": [
    { "type": "cheat_death", "revive_hp_pct": 0.30, "duration_turns": 5 }
  ],
  "allowed_classes": ["revenant"],
  "requires_line_of_sight": false
},
"soul_rend": {
  "skill_id": "soul_rend",
  "name": "Soul Rend",
  "description": "1.2× melee damage + slow for 2 turns.",
  "flavor": "A cursed blade tears at the soul, crippling the victim's will to flee.",
  "icon": "⚔️",
  "targeting": "enemy_adjacent",
  "range": 1,
  "cooldown_turns": 5,
  "mana_cost": 0,
  "effects": [
    { "type": "melee_damage_slow", "damage_multiplier": 1.2, "slow_duration": 2 }
  ],
  "allowed_classes": ["revenant"],
  "requires_line_of_sight": false
}
```

**`class_skills` mapping:**
```json
"revenant": ["auto_attack_melee", "grave_thorns", "grave_chains", "undying_will", "soul_rend"]
```

**Tests (Phase 25A):**
- Revenant class loads from config with correct stats (HP 130, melee 14, ranged 0, armor 5, vision 5, range 0)
- Revenant class has correct color (#708090) and shape (coffin)
- All 4 skills load from config with correct properties
- `class_skills["revenant"]` maps to correct 5 skills
- `can_use_skill()` validates Revenant skills for revenant class
- `can_use_skill()` rejects Revenant skills for non-revenant classes
- Revenant allowed_weapon_categories is ["melee", "hybrid"]
- Existing class tests still pass (regression check)

**Estimated tests:** 8–10

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass before proceeding.

---

### Phase 25B — Effect Handlers (Core Mechanics)

**Goal:** Implement 3 new effect type handlers (`thorns_buff`, `ranged_taunt`, `cheat_death`) and 1 existing-variant (`melee_damage_slow`), connect them to `resolve_skill_action()`.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/skills.py` | Add `resolve_thorns_buff()`, `resolve_ranged_taunt()`, `resolve_cheat_death()`, `resolve_melee_damage_slow()` handlers + dispatcher branches |
| `server/app/core/turn_phases/skills_phase.py` | Update dispatcher if needed |

#### Handler 1: `resolve_thorns_buff()` (~25 lines)

```
Input:  player, action, skill_def, players
Logic:  1. Apply buff: {"stat": "thorns_damage", "magnitude": 10, "duration_turns": 3}
        2. Set skill cooldown
        3. Log combat message
Output: ActionResult with buff_applied
```

#### Handler 2: `resolve_ranged_taunt()` (~25 lines)

```
Input:  player, action, skill_def, players, obstacles, grid_w, grid_h
Logic:  1. Validate target exists, is enemy, within range
        2. Check LOS to target
        3. Apply taunt buff (forced_target = caster.id, duration = 3)
        4. Set cooldown, log message
Output: ActionResult with damage=0, taunt_applied=True
```

#### Handler 3: `resolve_cheat_death()` (~20 lines)

```
Input:  player, action, skill_def
Logic:  1. Apply buff: {"stat": "cheat_death", "revive_hp_pct": 0.30, "duration_turns": 5}
        2. Set skill cooldown
        3. Log combat message
Output: ActionResult with buff_applied
```

#### Handler 4: `resolve_melee_damage_slow()` (~30 lines)

```
Input:  player, action, skill_def, players
Logic:  1. Validate target is adjacent enemy
        2. Calculate damage: floor(base_melee × damage_multiplier) - target_armor
        3. Apply damage (min 1)
        4. Apply slow debuff (duration = slow_duration)
        5. Set cooldown, log message
Output: ActionResult with damage dealt + slow applied
```

#### Dispatcher Update

```python
elif effect_type == "thorns_buff":
    return resolve_thorns_buff(player, action, skill_def, ...)
elif effect_type == "ranged_taunt":
    return resolve_ranged_taunt(player, action, skill_def, ...)
elif effect_type == "cheat_death":
    return resolve_cheat_death(player, action, skill_def, ...)
elif effect_type == "melee_damage_slow":
    return resolve_melee_damage_slow(player, action, skill_def, ...)
```

**Tests (Phase 25B):**

*Grave Thorns (thorns_buff):*
- Grave Thorns applies thorns_damage buff with magnitude 10 and duration 3
- Grave Thorns sets cooldown to 5
- Grave Thorns buff expires after 3 turns
- Grave Thorns can be recast after cooldown

*Grave Chains (ranged_taunt):*
- Grave Chains applies taunt (forced_target) to enemy within range 3
- Grave Chains taunt lasts 3 turns (forced_target set)
- Grave Chains requires LOS
- Grave Chains fails on ally (wrong target type)
- Grave Chains fails on out-of-range target
- Grave Chains sets cooldown to 5

*Undying Will (cheat_death):*
- Undying Will applies cheat_death buff with duration 5
- Undying Will sets cooldown to 10
- Cheat death buff expires after 5 turns if not triggered

*Soul Rend (melee_damage_slow):*
- Soul Rend deals 1.2× melee damage to adjacent enemy
- Soul Rend applies 2-turn slow
- Soul Rend respects armor (flat subtraction)
- Soul Rend minimum damage is 1
- Soul Rend fails on non-adjacent target
- Soul Rend sets cooldown to 5

**Estimated tests:** 16–20

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass.

---

### Phase 25C — Buff System Integration (Thorns + Cheat Death)

**Goal:** Wire thorns damage reflection into the combat pipeline and cheat death into the death resolution pipeline.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/combat.py` | After dealing melee/ranged damage, check target for thorns_damage buff → deal flat damage back to attacker |
| `server/app/core/turn_phases/deaths_phase.py` | Before marking player dead, check for cheat_death buff → revive instead |
| `server/app/core/turn_phases/buffs_phase.py` | Ensure thorns_damage and cheat_death buffs tick down correctly |

#### Thorns Integration (combat.py)

```python
# After applying damage to target:
thorns_buff = next((b for b in target.buffs if b.get("stat") == "thorns_damage"), None)
if thorns_buff and attacker:
    thorns_dmg = thorns_buff["magnitude"]
    attacker.hp = max(0, attacker.hp - thorns_dmg)
    # Log: "{target} reflects {thorns_dmg} thorns damage to {attacker}"
```

#### Cheat Death Integration (deaths_phase.py)

```python
# Before marking player as dead (hp <= 0):
cheat_death = next((b for b in player.buffs if b.get("stat") == "cheat_death"), None)
if cheat_death:
    revive_hp = max(1, int(player.max_hp * cheat_death["revive_hp_pct"]))
    player.hp = revive_hp
    player.buffs = [b for b in player.buffs if b.get("stat") != "cheat_death"]
    # Log: "{player} defies death! Revives with {revive_hp} HP!"
    # Do NOT mark as dead
```

**Tests (Phase 25C):**

*Thorns damage:*
- Attacker takes 10 thorns damage when hitting a thorns-buffed target (melee)
- Attacker takes 10 thorns damage when hitting a thorns-buffed target (ranged)
- Thorns damage ignores attacker's armor
- Thorns damage can kill the attacker (attacker HP → 0)
- Thorns damage does not trigger if buff expired
- Multiple attackers each take thorns damage independently
- Thorns damage does not apply to skill damage (only auto-attacks)

*Cheat death:*
- Player with cheat_death buff revives at 30% max HP instead of dying
- Cheat death buff is consumed (removed) after triggering
- Cheat death does not trigger if buff has expired
- Cheat death sets HP correctly (floor of 30% × max_hp)
- Player without cheat_death buff dies normally (regression)
- Cheat death only triggers once (buff consumed)
- Cheat death revived player can act on following turns

**Estimated tests:** 14–16

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass.

---

### Phase 25D — AI Behavior (retaliation_tank role)

**Goal:** Implement AI decision-making so Revenant heroes and AI-controlled Revenants play the aggressive retaliation tank strategy.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/ai_skills.py` | Add `"revenant": "retaliation_tank"` to `_CLASS_ROLE_MAP` |
| `server/app/core/ai_skills.py` | Add `_retaliation_tank_skill_logic()` function |
| `server/app/core/ai_skills.py` | Add `"retaliation_tank"` branch to dispatcher |

#### AI Decision Logic

```python
def _retaliation_tank_skill_logic(ai, enemies, all_units, grid_w, grid_h, obstacles):
    """Revenant AI: aggressive retaliation tank — punish attackers, taunt ranged, cheat death."""

    # 1. Undying Will → if HP < 40% max and no cheat_death buff active
    # 2. Grave Thorns → if 2+ enemies within 2 tiles and no thorns buff active
    # 3. Grave Chains → if a ranged enemy within 3 tiles, not adjacent — taunt them
    # 4. Soul Rend → if adjacent enemy exists, slow them
    # 5. Fallback — auto-attack
    return None
```

**Tests (Phase 25D):**
- Revenant AI casts Undying Will when HP < 40% and no cheat_death buff
- Revenant AI does not cast Undying Will when HP > 40%
- Revenant AI does not cast Undying Will when cheat_death buff already active
- Revenant AI casts Grave Thorns when 2+ enemies nearby and no thorns active
- Revenant AI uses Grave Chains on ranged enemy not adjacent
- Revenant AI prefers taunting squishier targets (Mage > Ranger > others)
- Revenant AI uses Soul Rend on adjacent enemy
- Revenant AI falls back to auto-attack when all skills on cooldown
- Revenant AI charges toward enemy groups (aggressive positioning)
- Revenant AI does not retreat when Undying Will is available

**Estimated tests:** 10–12

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass.

---

### Phase 25E — Frontend Integration (Rendering + UI)

**Goal:** Add Revenant to the client — coffin shape rendering, class selection, colors, icons, inventory portrait.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/canvas/renderConstants.js` | Add revenant to `CLASS_COLORS`, `CLASS_SHAPES`, `CLASS_NAMES` |
| `client/src/canvas/unitRenderer.js` | Add `coffin` shape rendering case |
| `client/src/components/WaitingRoom/WaitingRoom.jsx` | Add coffin icon to shape map |
| `client/src/components/Inventory/Inventory.jsx` | Add coffin SVG path to `CLASS_SHAPE_PATHS` |
| `client/src/components/Inventory/Inventory.jsx` | Add skill buff names to `formatBuffName` / `formatBuffEffect` |

#### renderConstants.js additions

```javascript
// CLASS_COLORS
revenant: '#708090',

// CLASS_SHAPES
revenant: 'coffin',

// CLASS_NAMES
revenant: 'Revenant',
```

#### unitRenderer.js — Coffin Shape

```javascript
case 'coffin': {
  // A coffin/sarcophagus shape — tapered pentagon wider at shoulders, narrower at feet
  const hw = half * 0.65;  // half width
  const hh = half * 0.95;  // half height
  ctx.beginPath();
  ctx.moveTo(cx - hw * 0.6, cy - hh);          // top left (narrow head)
  ctx.lineTo(cx + hw * 0.6, cy - hh);          // top right (narrow head)
  ctx.lineTo(cx + hw, cy - hh * 0.4);          // shoulder right (wider)
  ctx.lineTo(cx + hw * 0.5, cy + hh);          // bottom right (narrow foot)
  ctx.lineTo(cx - hw * 0.5, cy + hh);          // bottom left (narrow foot)
  ctx.lineTo(cx - hw, cy - hh * 0.4);          // shoulder left (wider)
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  break;
}
```

#### WaitingRoom.jsx — Shape icon

```
cls.shape === 'coffin' ? '⚰️' : ...
```

#### Inventory.jsx — SVG portrait path

```javascript
coffin: <path d="M 38 5 L 62 5 L 72 30 L 60 95 L 40 95 L 28 30 Z" />,
```

#### Inventory.jsx — Buff name formatting

```javascript
// formatBuffName:
grave_thorns: 'Grave Thorns',
undying_will: 'Undying Will',
soul_rend: 'Soul Rend',

// formatBuffEffect:
if (buff.stat === 'thorns_damage') return `Reflects ${buff.magnitude} dmg per hit`;
if (buff.stat === 'cheat_death') return `Revive at ${Math.round(buff.revive_hp_pct * 100)}% HP if killed`;
```

**Tests (Phase 25E):** Visual verification — manual checklist:
- [ ] Revenant appears in class selection screen
- [ ] Coffin shape renders correctly on canvas
- [ ] Color (#708090 slate gray) displays correctly and is distinguishable
- [ ] Revenant name shows in nameplate
- [ ] Inventory portrait shows coffin shape
- [ ] Thorns and cheat death buff icons display correctly in HUD
- [ ] Skill icons appear in bottom bar with correct names

---

### Phase 25F — Particle Effects & Audio (Polish)

**Goal:** Add visual and audio feedback for Revenant skills.

**Files Modified:**
| File | Change |
|------|--------|
| `client/public/particle-presets/skills.json` | Add revenant skill effects |
| `client/public/particle-presets/buffs.json` | Add thorns aura + cheat death glow |
| `client/public/audio-effects.json` | Add revenant audio triggers |
| `client/src/audio/soundMap.js` | Add revenant sound mappings |

#### Particle Effects

| Skill | Particle Effect | Description |
|-------|----------------|-------------|
| Grave Thorns | `revenant-thorns-aura` | Orbiting bone shard particles around the Revenant (gray/white) |
| Grave Chains | `revenant-chains-taunt` | Spectral chains erupting from ground beneath target (gray/green ghostly) |
| Undying Will | `revenant-undying-activate` | Dark purple/gray aura pulse on cast |
| Undying Will (trigger) | `revenant-revive-burst` | Dramatic resurrection explosion — ground cracks, spectral energy erupts |
| Soul Rend | `revenant-soul-rend` | Dark slash effect with ghostly trail |

#### Audio

| Skill | Sound | Category |
|-------|-------|----------|
| Grave Thorns | Bone cracking / grinding | skills |
| Grave Chains | Chain rattling + ghostly moan | skills |
| Undying Will (cast) | Deep ominous hum | skills |
| Undying Will (trigger) | Dramatic resurrection chord | skills |
| Soul Rend | Ghostly slash | skills |

**Tests (Phase 25F):** Manual verification only.
- [ ] Each skill triggers correct particle effect
- [ ] Thorns aura visible on Revenant when active
- [ ] Undying Will revival effect is dramatic and noticeable
- [ ] Audio plays on skill use
- [ ] No console errors from missing assets

---

### Phase 25G — Sprite Integration (Optional)

**Goal:** Add Revenant sprite variants from the character sheet atlas.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/canvas/SpriteLoader.js` | Add revenant sprite variants |

*This phase depends on finding suitable sprites in the existing atlas. If no revenant-appropriate sprites exist, the coffin shape fallback works perfectly.*

---

## Implementation Order & Dependencies

```
Phase 25A (Config)             ← No dependencies, pure data
    ↓
Phase 25B (Effect Handlers)    ← Depends on 25A (needs skill definitions)
    ↓
Phase 25C (Buff Integration)   ← Depends on 25B (needs handlers working)
    ↓
Phase 25D (AI Behavior)        ← Depends on 25B (needs handlers working)
    ↓
Phase 25E (Frontend)           ← Depends on 25A — can parallel with 25C/25D
    ↓
Phase 25F (Polish)             ← Depends on 25E (needs rendering working)
    ↓
Phase 25G (Sprites)            ← Optional, last
```

**Parallelizable:** 25C + 25D can run in parallel after 25B. 25E can start after 25A.

---

## Test Summary

| Phase | Test Count | Focus |
|-------|:----------:|-------|
| 25A — Config | 8–10 | Class/skill loading, validation |
| 25B — Effect Handlers | 16–20 | Handler logic, edge cases |
| 25C — Buff Integration | 14–16 | Thorns reflection, cheat death in combat/death pipeline |
| 25D — AI Behavior | 10–12 | AI decision logic, targeting |
| 25E — Frontend | 0 (manual) | Visual verification |
| 25F — Polish | 0 (manual) | Particles, audio |
| **Total** | **48–58** | |

---

## Tuning Levers

| Parameter | Initial Value | Reduce If... | Increase If... |
|-----------|:------------:|--------------|----------------|
| HP | 130 | Too tanky with cheat death (effective 169 HP) | Dies too fast before cheat death triggers |
| Melee Damage | 14 | Thorns + melee combo kills too fast | Revenant ignored because no threat |
| Armor | 5 | Thorns don't trigger enough (not taking damage) | Dies before thorns/cheat death matter |
| Thorns Damage | 10 per hit | Multi-enemy packs melt (30+/turn retaliation) | Enemies feel no punishment for focusing Revenant |
| Thorns Duration | 3 turns | Too much uptime (15 turns of thorns per 5 CD cycle = 60%) | Buff expires before enemies engage |
| Grave Chains Range | 3 tiles | Backline enemies taunted too easily | Ranged enemies ignore Revenant completely |
| Taunt Duration | 3 turns | Forced melee is too punishing for squishies | Enemies escape immediately after taunt |
| Grave Chains CD | 5 turns | Available too often (60% uptime) | Too much downtime between taunts |
| Undying Will CD | 10 turns | Available too often | One use per fight feels bad |
| Undying Will Duration | 5 turns | Too easy to time perfectly | Window too narrow, wastes cooldown |
| Revive HP % | 30% | Revives with enough HP to re-tank effectively | Revives and dies immediately |
| Soul Rend Multiplier | 1.2× | Too much damage for a tank skill | Doesn't feel impactful |
| Soul Rend Slow | 2 turns | Combined with taunt creates inescapable 5-turn lock | Enemies escape before combo completes |

### Known Balance Risks

1. **Cheat Death + Confessor Heal:** A Revenant that revives at 39 HP and immediately gets healed by a Confessor (30 HP heal) is at 69 HP — essentially a second life. This is intentional but may need the 10-turn cooldown lengthened if parties abuse it.
2. **Grave Chains + Soul Rend Lock:** Taunting a Ranger/Mage to force them into melee and then slowing them for 2 turns may be too punishing for squishy classes. Mitigation: Mage has Blink (escape), Ranger has Evasion. The enemy still walks under their own power (they aren't displaced), so movement-blocking terrain or allies can interfere. Classes without escape tools are at risk.
3. **Thorns vs Multi-Enemy PvE:** In dungeon corridors with 3+ enemies hitting the Revenant, thorns deal 30+ damage per turn passively. Combined with auto-attacks, the Revenant may clear packs too efficiently for a tank. Monitor and reduce thorns per-hit if needed.
4. **Stacking with Hexblade Ward:** If a Revenant equips Ward-granting items, they could have both thorns AND reflect charges. This is acceptable but may overload retaliation damage.

---

## Future Enhancements (Post-Phase 25)

- **Passive: Unyielding** — "Gain +1 armor for every 20% HP missing" — a soft passive that increases tankiness at low HP, synergizing with the risk-reward of Undying Will
- **Grave Chains Upgrade** — Taunt duration scales with missing HP (2 turns at full HP, 4 turns below 30% HP)
- **Soul Link** — Tether to an ally; 30% of damage they take is redirected to the Revenant. Proper off-tank utility skill.

---

## Phase Checklist

- [x] **25A** — Revenant added to `classes_config.json`
- [x] **25A** — 4 skills added to `skills_config.json`
- [x] **25A** — `class_skills.revenant` mapping added
- [x] **25A** — Config loading tests pass (61 tests)
- [x] **25A** — Revenant names added to `names_config.json` (15 names)
- [x] **25A** — Stale count assertions updated in older test files
- [x] **25B** — `resolve_thorns_buff()` handler implemented
- [x] **25B** — `resolve_ranged_taunt()` handler implemented
- [x] **25B** — `resolve_cheat_death()` handler implemented
- [x] **25B** — `resolve_melee_damage_slow()` handler implemented
- [x] **25B** — `resolve_skill_action()` dispatcher updated
- [x] **25B** — All handler tests pass (32 tests)
- [x] **25C** — Thorns damage reflection wired into combat.py (melee + ranged, stacks with equipment thorns)
- [x] **25C** — Cheat death wired into deaths_phase.py (pre-pass revive, buff consumed, min 1 HP)
- [x] **25C** — Buff tick-down working for thorns and cheat_death (standard tick, verified expiry)
- [x] **25C** — Buff integration tests pass (26 tests)
- [x] **25D** — `_retaliation_tank_skill_logic()` implemented
- [x] **25D** — `_CLASS_ROLE_MAP` updated with revenant (30 entries)
- [x] **25D** — AI behavior tests pass (26 tests)
- [x] **25D** — Stale `_CLASS_ROLE_MAP` count assertions updated (4 test files: 29→30)
- [x] **25D** — `known_roles` set updated in `test_ai_skills.py` (added `retaliation_tank`)
- [x] **25D** — `_decide_skill_usage()` dispatcher branch added for `retaliation_tank`
- [x] **25E** — `renderConstants.js` updated
- [x] **25E** — Coffin shape renders in `unitRenderer.js`
- [x] **25E** — WaitingRoom class select shows Revenant
- [x] **25E** — Inventory portrait & buff names updated
- [ ] **25F** — Particle effects added
- [ ] **25F** — Audio triggers added
- [x] **25G** — Reaver_1 sprite mapped to revenant class (SpriteLoader.js + profile.py HERO_SPRITE_VARIANTS)
- [x] Balance pass after playtesting (March 7 2026 — see Update Log)

---

## Post-Implementation Cleanup

After all phases complete:

1. **Update `README.md`:**
   - Add Revenant to the class count in the Features table  
   - Add phase 25 to the Documentation → Phase Specs list
   - Update the status line at the top
   - Update the test count

2. **Update `docs/Current Phase.md`:**
   - Add phase 25 milestone entry with test counts

3. **Update `docs/Game stats references/game-balance-reference.md`:**
   - Add Revenant stat block

4. **Final test run:**
   - `pytest server/tests/` — ALL tests pass, zero failures
   - Record final test count

---

## Update Log

### March 7 2026 — Revenant Balance Pass

**Problem:** Revenant was significantly underperforming compared to the Crusader across DPS, survivability, and AI efficiency.

**Stat Changes (classes_config.json):**
- `base_melee_damage` 14 → 16 (closer to Crusader's 18)
- `base_armor` 5 → 6 (still below Crusader's 8, but less punishing)

**Skill Tuning (skills_config.json):**
- **Grave Thorns:** `thorns_damage` 10 → 12, `duration_turns` 3 → 4 (more uptime & retaliation value)
- **Grave Chains:** `range` 3 → 4 (wider taunt window for pulling ranged threats)
- **Undying Will:** `cooldown_turns` 10 → 8 (cheat-death available more often)
- **Soul Rend:** `damage_multiplier` 1.2× → 1.5×, `cooldown_turns` 5 → 4 (real burst threat)

**AI Priority Reorder (ai_skills.py — `_retaliation_tank_skill_logic`):**
1. Undying Will (HP < 40%) — unchanged
2. **Soul Rend** (adjacent enemy) — promoted from #4
3. Grave Thorns (enemies nearby) — demoted from #2
4. Grave Chains (ranged taunt) — demoted from #3
- `_GRAVE_CHAINS_RANGE` constant 3 → 4

**Rationale:** The old AI wasted 2–3 turns on self-buffs before dealing any damage, making the Revenant feel passive and easy to ignore. Promoting Soul Rend to #2 means the Revenant now threatens adjacent enemies immediately while still self-buffing when nothing is in melee range.

**Test Updates:** All 4 Revenant test files updated (25A config, 25B handlers, 25C buff integration, 25D AI). Full suite: **3578 passed, 0 failed.**

---

**Document Version:** 1.4
**Created:** March 2026
**Status:** Phase 25G Complete — 3578 tests passing (post-balance pass)
**Prerequisites:** Phase 24 (Tooltip Revamp) Complete
