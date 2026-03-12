# Phase 22 — Blood Knight Class (Drain / Sustain DPS)

**Created:** March 2026
**Status:** Not Started
**Previous:** Phase 21 (Bard Class)
**Goal:** Add the Blood Knight as the eighth playable class — a vampiric melee warrior who sustains through carnage. Fills the missing "self-sufficient melee DPS" niche: a frontliner who doesn't need a healer but pays for that independence with lower burst and no team utility. Enriches party composition by offering an alternative to Crusader for the melee slot that trades tankiness for sustain.

---

## Overview

A cursed knight bound by a blood pact, draining the life force of enemies to fuel an unrelenting assault. Where the Crusader endures through armor and the Confessor through healing, the Blood Knight endures through violence — every strike mends flesh, every kill extends the march. In the grimdark dungeon, they are the tip of the spear that never dulls.

**Role:** Sustain Melee DPS

### Design Pillars

1. **Vampiric Sustain** — Every core ability heals the Blood Knight. They should feel self-sufficient without a Confessor babysitting them.
2. **Melee Commitment** — Zero ranged capability. Once they engage, they're all-in. Positioning matters; being kited is their weakness.
3. **Risk/Reward Tension** — The Blood Knight gets stronger at low HP. Playing aggressively is rewarded; playing safe is suboptimal.
4. **No Team Utility** — Pure selfish DPS/sustain. They contribute nothing to allies (no buffs, no heals). Party value comes entirely from being an unkillable damage threat that frees the Confessor to focus elsewhere.
5. **Grimdark Fantasy** — Blood magic, life drain, crimson visuals. They are feared by allies and enemies alike.

---

## Base Stats

| Stat | Value | Rationale |
|------|-------|-----------|
| **HP** | 100 | Mid-range — same as Confessor. Sustain comes from healing, not raw HP pool. Lower than Crusader (150) and Hexblade (110), higher than squishies (70-80). |
| **Melee Damage** | 16 | Second highest melee (behind Crusader's 20). Needs to deal enough damage that lifesteal returns meaningful HP. Higher than Hexblade (15) in melee because Blood Knight has zero ranged fallback. |
| **Ranged Damage** | 0 | Pure melee. No ranged capability at all — this is the core weakness. |
| **Armor** | 4 | Medium armor — same as Inquisitor. Not a tank; they survive through healing, not damage reduction. Lower than Hexblade (5) and Crusader (8). |
| **Vision Range** | 6 | Standard frontline vision — same as Confessor and Hexblade. Not a scout. |
| **Ranged Range** | 0 | Melee only. Must close distance to be effective. |
| **Allowed Weapons** | `["melee", "hybrid"]` | Same as Crusader — melee weapons and hybrid weapons. No ranged or caster weapons. |
| **Color** | `#8B0000` | Dark Red (Crimson) — distinct from Hexblade's bright red (#e04040) and Crusader's blue (#4a8fd0). Evokes blood magic. |
| **Shape** | `shield` | A pointed kite shield / heraldic shield shape — suggests a fallen knight. Distinct from all existing shapes (square, circle, triangle, diamond, star, hexagon, crescent). |

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
```

### Auto-Attack Damage (1.15× multiplier)

```
 Blood Knight .. 16 × 1.15 = 18 melee per hit
```

This places Blood Knight third in auto-attack DPS behind Crusader (23) and Ranger (21 ranged), tied conceptually with Hexblade (17). The difference is that Blood Knight's auto-attacks trigger lifesteal effects, making each hit contribute to survival.

---

## Skills

### Skill Overview

| Slot | Skill | Effect Type | Target | Range | Cooldown | Summary |
|:----:|-------|------------|--------|:-----:|:--------:|---------|
| 0 | Auto Attack (Melee) | melee | entity | 1 | 0 | 1.15× melee (18) damage |
| 1 | Blood Strike | `lifesteal_damage` (**NEW**) | entity | 1 | 4 | 1.4× melee damage, heal 40% of damage dealt |
| 2 | Crimson Veil | `buff` (existing) | self | 0 | 6 | +30% melee damage + heal 6 HP per hit for 3 turns |
| 3 | Sanguine Burst | `lifesteal_aoe` (**NEW**) | self | 0 | 7 | 0.7× melee damage to all enemies within 1 tile, heal 50% of total damage dealt |
| 4 | Blood Frenzy | `buff` (existing) | self | 0 | 8 | Below 40% HP: +50% melee damage + 15 HP instant heal. Fails above 40% HP. |

### Skill Details

#### Blood Strike 🩸 (Vampiric Melee Strike)

```
Effect Type:   lifesteal_damage (NEW — based on melee_damage handler)
Targeting:     entity (adjacent enemy)
Radius:        — (single target)
Range:         1 tile (melee)
Cooldown:      4 turns
LOS Required:  No
Effect:        Deal 1.4× melee damage to target. Heal self for 40% of damage dealt.
```

**Design:** The bread-and-butter sustain tool. Used on cooldown to maintain HP during sustained fights. Moderate damage with reliable healing. This is what makes the Blood Knight self-sufficient in PvE — they can trade blows with enemies and come out ahead on HP.

**Damage/healing examples:**
```
Blood Knight (16 melee, 4 armor target):
  Raw: 16 × 1.4 = 22 damage
  After armor: 22 - 4 = 18 final damage
  Heal: 18 × 0.40 = 7 HP healed

Blood Knight (16 melee, 8 armor Crusader):
  Raw: 16 × 1.4 = 22 damage
  After armor: 22 - 8 = 14 final damage
  Heal: 14 × 0.40 = 5 HP healed

With Crimson Veil active (1.3× mult → effectively 16 × 1.3 = 20.8 base):
  Raw: 20 × 1.4 = 29 damage (truncated from 20.8 × 1.4)
  After armor (4): 29 - 4 = 25 final damage  
  Heal: 25 × 0.40 = 10 HP healed
```

**Implementation:** Clone `resolve_multi_hit()` pattern. Single hit instead of double. After calculating final damage and applying it, heal the caster for `floor(final_damage * heal_pct)`. The heal respects `max_hp` cap.

**Balance lever:** Damage multiplier (1.4), heal percentage (40%), cooldown (4)

---

#### Crimson Veil 🌑 (Self-Buff — Damage + Lifesteal Aura)

```
Effect Type:   buff (existing — self-targeting compound buff)
Targeting:     self
Radius:        — (self only)
Range:         — (self-cast)
Cooldown:      6 turns
LOS Required:  No
Effect:        For 3 turns: +30% melee damage AND heal 6 HP at start of each turn (HoT component).
```

**Design:** The "turn on" button. Activating Crimson Veil transforms the Blood Knight from a moderate threat into a sustained damage machine. The HoT provides baseline sustain even when not attacking (e.g., while moving to engage). Combos powerfully with Blood Strike — the damage buff increases Blood Strike's healing since lifesteal is based on damage dealt.

**Damage/healing examples:**
```
Auto-attack with Crimson Veil:
  16 × 1.15 × 1.3 = 23.9 → 23 melee per hit (vs 18 without)
  +6 HP/turn passive heal

Blood Strike with Crimson Veil:
  16 × 1.3 × 1.4 = 29 damage (before armor)
  Lifesteal = 40% of post-armor → substantially more than without Veil

Over 3 turns (just buff + auto):
  Heal: 3 × 6 = 18 HP from HoT
  Damage boost: ~5 extra damage per auto × 3 = 15 extra damage
```

**Implementation:** Use existing `resolve_buff()`. The `melee_damage_multiplier` stat is already wired into `get_melee_buff_multiplier()`. The HoT component uses a second effect entry with the existing `hot` buff stat — this is a multi-effect skill (effects array with 2 entries). The buff handler already iterates effects and applies all of them.

Actually, looking at the existing system more carefully: the buff handler applies a single buff. For the compound buff (damage + HoT), we have two approaches:
1. Two separate buff entries in the effects array (the existing multi-effect system handles this)
2. A single buff with a custom stat that we check in both the damage pipeline and the tick system

The cleanest approach: **two effects** in the skill definition — one `buff` for the damage multiplier, one `hot`-style effect for the passive heal. Since `resolve_skill_action()` dispatches on `effects[0].type`, we'll use `buff` as primary and handle the secondary HoT in the buff handler by checking for additional effects.

**Simpler approach:** Make this a standard `buff` (melee_damage_multiplier: 1.3, 3 turns) + add a separate HoT buff entry. The `resolve_buff()` handler already supports applying the buff. For the HoT, we add a second buff with `stat: "hot"` and `magnitude: 6`. The existing `tick_buffs()` already processes HoT ticks. This just needs the buff to be applied alongside the damage buff — we'll add that logic in a small extension to `resolve_buff()` for multi-effect buff skills.

**Balance lever:** Damage multiplier (1.3), HoT per turn (6), duration (3 turns), cooldown (6)

---

#### Sanguine Burst 💉 (AoE Lifesteal)

```
Effect Type:   lifesteal_aoe (NEW — based on aoe_damage handler)
Targeting:     self (AoE around caster)
Radius:        1 tile
Range:         — (self-cast)
Cooldown:      7 turns
LOS Required:  No
Effect:        Deal 0.7× melee damage to all enemies within 1 tile. Heal self for 50% of TOTAL damage dealt.
```

**Design:** The "I'm surrounded and I love it" skill. The healing scales with the number of enemies hit, creating a powerful incentive to wade into packs. Against 1 enemy it's mediocre (less damage and less healing than Blood Strike). Against 3+ enemies it's the strongest sustain tool in the kit. This is the skill that makes Blood Knight a PvE dungeon-crawling monster.

**Damage/healing examples:**
```
Blood Knight (16 melee) vs 1 enemy (4 armor):
  Raw: 16 × 0.7 = 11 damage
  After armor: 11 - 4 = 7 final damage
  Heal: 7 × 0.50 = 3 HP healed (underwhelming)

Blood Knight vs 3 enemies (4 armor each):
  Raw per enemy: 11, after armor: 7 each
  Total damage: 21
  Heal: 21 × 0.50 = 10 HP healed (solid)

Blood Knight vs 5 enemies (4 armor each):
  Total damage: 35
  Heal: 35 × 0.50 = 17 HP healed (excellent)

With Crimson Veil active vs 3 enemies:
  Raw per enemy: 16 × 1.3 × 0.7 = 14, after armor: 10 each
  Total damage: 30
  Heal: 30 × 0.50 = 15 HP healed
```

**Implementation:** Clone `resolve_aoe_damage()` pattern (the Mage's Arcane Barrage handler). Change center to caster position instead of target tile. After accumulating total damage dealt across all hits, heal the caster for `floor(total_damage * heal_pct)`.

**Balance lever:** Damage multiplier (0.7), heal percentage (50%), radius (1), cooldown (7)

---

#### Blood Frenzy 🔥 (Low-HP Emergency Burst)

```
Effect Type:   buff (existing — conditional self-buff)
Targeting:     self
Radius:        — (self only)
Range:         — (self-cast)
Cooldown:      8 turns
LOS Required:  No
Effect:        REQUIRES below 40% HP to activate. Instantly heal 15 HP, then gain +50% melee damage for 3 turns.
```

**Design:** The "second wind" panic button. Embodies the risk/reward pillar — you're rewarded for being at low HP with a massive damage spike AND an emergency heal that can pull you back from the brink. The HP threshold prevents it from being a generic damage steroid. The long cooldown (8 turns) ensures it's a once-per-major-fight ability. Failing the HP check wastes nothing (no cooldown consumed), so there's no punishment for fat-fingering it.

**Damage/healing examples:**
```
Activation at 35/100 HP:
  Instant heal: 35 + 15 = 50 HP (back to fighting shape)
  Next 3 turns auto-attack: 16 × 1.15 × 1.5 = 27 per hit (vs 18 normally)
  Blood Strike during frenzy: 16 × 1.5 × 1.4 = 33 damage (before armor)
    Lifesteal: ~12 HP healed per strike vs 4-armor target

With BOTH Crimson Veil AND Blood Frenzy active:
  16 × 1.15 × 1.3 × 1.5 = 35 per auto-attack hit
  (Compare: Crusader hits for 23. Blood Knight temporarily out-damages the tank.)
  This is the peak power window — short, devastating, risky.
```

**Implementation:** Use existing `resolve_buff()` with a pre-check. Before applying the buff, verify `player.hp / player.max_hp < 0.40`. If check fails, return `success=False` with message "Not wounded enough to activate Blood Frenzy" and do NOT consume cooldown. If check passes, heal 15 HP (capped at max_hp), then apply `melee_damage_multiplier: 1.5` buff for 3 turns.

This requires a small addition in the resolve_buff handler — or better, a dedicated `resolve_blood_frenzy()` handler that wraps the HP check + heal + buff application. Since the HP threshold is a new mechanic, a dedicated ~30-line handler is cleaner than overloading the generic buff handler.

**Balance lever:** HP threshold (40%), instant heal (15), damage multiplier (1.5), duration (3 turns), cooldown (8)

---

### Complete Blood Knight Kit

```
Slot 0: Auto Attack — 1.15× melee (18 dmg). Reliable baseline damage.
Slot 1: Blood Strike — 1.4× melee + 40% lifesteal. Bread-and-butter sustain (CD 4).
Slot 2: Crimson Veil — +30% damage + 6 HP/turn HoT for 3 turns. "Turn on" button (CD 6).
Slot 3: Sanguine Burst — 0.7× melee AoE (1 tile) + 50% lifesteal on total. Pack-clearing sustain (CD 7).
Slot 4: Blood Frenzy — Requires <40% HP. Heal 15 + 50% damage for 3 turns. Emergency burst (CD 8).
```

---

## DPS Contribution Analysis

### Direct DPS (Personal)

```
Auto-attack DPS: 18 per turn (16 × 1.15) — 3rd highest behind Crusader (23) and Ranger (21)

Sustained DPS (rotation over 8 turns, 0-armor target):
  Turn 1: Crimson Veil (0 damage, enables buff)
  Turn 2: Blood Strike = 29 damage, heal 11
  Turn 3: Auto = 23 damage
  Turn 4: Auto = 23 damage (Veil expires)
  Turn 5: Auto = 18 damage
  Turn 6: Blood Strike = 22 damage, heal 8
  Turn 7: Auto = 18 damage
  Turn 8: Auto = 18 damage
  Total: 151 damage / 8 turns = ~18.9 DPT
  Total healing: ~19 HP self-healed + 18 from HoT = ~37 HP

Compare (auto-attack only, same 8 turns):
  Crusader: 23 × 8 = 184 damage, 0 healing
  Hexblade: 17 × 8 = 136 damage, 0 healing (not counting Wither)
  Blood Knight: 151 damage, 37 healing

Blood Knight trades ~15% less raw damage than Crusader for ~37 HP sustain.
```

### Survivability Analysis

```
Blood Knight effective HP (10-turn fight, active rotation):
  Base: 100 HP
  Blood Strike × 2: ~16-20 HP healed
  Crimson Veil HoT: 18 HP over 3 turns
  Blood Frenzy heal: 15 HP (triggered once at low HP)
  Total effective HP: ~149-153 HP over a prolonged fight

Compare to Crusader:
  150 HP + 8 armor (flat reduction applies every hit)
  vs Blood Knight: 100 HP + 4 armor + ~50 HP healed

Against 15-damage-per-hit enemy:
  Crusader takes: 15 - 8 = 7 per hit → 150/7 = 21 hits to kill
  Blood Knight takes: 15 - 4 = 11 per hit → (100+50)/11 ≈ 13 hits to kill

Crusader is still tankier. Blood Knight compensates by killing faster.
```

### Pack Sustain Scenario (PvE Focus)

```
Blood Knight vs 4 enemies (12 dmg each, 3 armor):
  Incoming: 4 × (12-4) = 32 damage/turn
  
  Turn 1: Crimson Veil → 0 damage, sets up
  Turn 2: Sanguine Burst → 4 × (16×1.3×0.7 - 3) = 4 × 11 = 44 dmg, heal 22
           Net HP: -32 + 22 + 6(HoT) = -4 HP
  Turn 3: Blood Strike → 16×1.3×1.4 - 3 = 26 dmg, heal 10
           Net HP: -32 + 10 + 6(HoT) = -16 HP
  
  Blood Knight can sustain against 4 enemies for ~5-6 turns before needing
  Blood Frenzy. With Confessor support, nearly unkillable in trash packs.
```

---

## AI Behavior (`sustain_dps` role)

### AI Role: `sustain_dps`

The Blood Knight AI plays aggressively — charging into the nearest enemy cluster and using sustain skills to stay alive. It prioritizes Blood Frenzy when wounded, Crimson Veil for sustained fights, Sanguine Burst when surrounded, and Blood Strike as the default damage/heal skill. It never retreats unless at critical HP with all cooldowns spent.

### Decision Priority

```
1. Blood Frenzy   → HP < 40% and skill off cooldown (emergency)
2. Crimson Veil   → Off cooldown, NOT already active, enemies adjacent or within 2 tiles (in-combat buff)
3. Sanguine Burst → 2+ enemies adjacent (AoE value threshold)
4. Blood Strike   → 1+ enemy adjacent, off cooldown, HP < max (skip at full HP — lifesteal wasted as overheal)
5. Auto-attack    → Fallback, target nearest enemy
```

### Positioning

- **Aggressive frontline** — charges toward nearest enemy cluster, similar to Crusader AI movement
- Reuse `_aggressive_move_preference()` (same as Crusader/Hexblade melee approach)
- Follow-stance leash widened to 6 tiles (vs default 4) so Blood Knight doesn't regroup mid-fight
- Retreat condition: HP < 20% AND Blood Frenzy on cooldown AND Blood Strike on cooldown (all sustain exhausted)
- Unlike Crusader, does NOT taunt or protect allies — purely selfish movement

### Smart Targeting Logic

```python
def _sustain_dps_skill_logic(ai, enemies, all_units, grid_w, grid_h, obstacles):
    """Blood Knight AI: prioritize sustain when wounded, AoE when surrounded."""
    
    # 1. Blood Frenzy — emergency heal + damage when low HP
    if ai.hp / ai.max_hp < 0.40:
        if can_use_skill(ai, "blood_frenzy"):
            return make_skill_action(ai, "blood_frenzy", target=ai)  # self-cast
    
    # 2. Crimson Veil — activate when in or entering melee (skip if already active)
    has_crimson_veil = any(b.buff_id == "crimson_veil" for b in ai.active_buffs)
    if not has_crimson_veil and can_use_skill(ai, "crimson_veil"):
        adjacent_enemies = [e for e in enemies if is_adjacent(ai.position, e.position)]
        nearby_enemies = [e for e in enemies if distance(ai, e) <= 2]
        if adjacent_enemies or nearby_enemies:
            return make_skill_action(ai, "crimson_veil", target=ai)  # self-cast
    
    # 3. Sanguine Burst — AoE when 2+ enemies adjacent
    if can_use_skill(ai, "sanguine_burst"):
        adjacent_enemies = [e for e in enemies if is_adjacent(ai.position, e.position)]
        if len(adjacent_enemies) >= 2:
            return make_skill_action(ai, "sanguine_burst", target=ai)  # self-cast
    
    # 4. Blood Strike — sustain on adjacent enemy (skip at full HP — lifesteal wasted)
    if ai.hp < ai.max_hp and can_use_skill(ai, "blood_strike"):
        adjacent_enemies = [e for e in enemies if is_adjacent(ai.position, e.position)]
        if adjacent_enemies:
            target = min(adjacent_enemies, key=lambda e: e.hp)  # focus lowest HP
            return make_skill_action(ai, "blood_strike", target=target)
    
    # 5. Fallback — auto-attack
    return None
```

---

## New Effect Types

### Summary

| Effect Type | Complexity | Based On | Handler |
|-------------|-----------|----------|---------|
| `lifesteal_damage` | Low | `melee_damage` (resolve_multi_hit) | `resolve_lifesteal_damage()` |
| `lifesteal_aoe` | Medium | `aoe_damage` (resolve_aoe_damage) | `resolve_lifesteal_aoe()` |

### Effect Type Details

#### `lifesteal_damage` — Single-Target Melee + Heal (Blood Strike)

```python
def resolve_lifesteal_damage(player, target_x, target_y, skill_def, players, obstacles, target_id=None):
    """Deal melee damage to adjacent enemy, heal caster for % of damage dealt."""
    # Step 1: Find target (by target_id or position) — same as resolve_multi_hit
    # Step 2: Validate adjacency and alive status
    # Step 3: Calculate damage = floor(player.attack_damage * buff_multiplier * damage_multiplier) - target_armor
    # Step 4: Apply damage to target (min 1)
    # Step 5: Calculate heal = floor(final_damage * heal_pct)
    # Step 6: Heal caster (capped at max_hp)
    # Step 7: Set cooldown
    # Step 8: Return ActionResult with damage dealt + HP healed in message
```

#### `lifesteal_aoe` — AoE Melee + Heal (Sanguine Burst)

```python
def resolve_lifesteal_aoe(player, skill_def, players, obstacles):
    """Deal melee damage to all enemies in radius around caster, heal for % of total."""
    # Step 1: Find all enemies within radius of caster position
    # Step 2: For each enemy: calculate damage = floor(attack_damage * buff_mult * damage_mult) - armor
    # Step 3: Apply damage to each enemy (min 1), accumulate total_damage_dealt
    # Step 4: Calculate heal = floor(total_damage_dealt * heal_pct)
    # Step 5: Heal caster (capped at max_hp)
    # Step 6: Set cooldown
    # Step 7: Return ActionResult listing enemies hit + total heal
```

### Buff/Debuff System Integration

**No new buff stats.** All buffs use existing system entries:
- `melee_damage_multiplier` — already in `get_melee_buff_multiplier()` (used by Crimson Veil and Blood Frenzy)
- `hot` ticks — already in `tick_buffs()` (used by Crimson Veil HoT component)

The Blood Frenzy HP threshold is checked in the handler before applying the buff — it does not introduce a new buff stat. The instant heal is a direct `player.hp` modification in the handler, not a buff tick.

---

## Implementation Phases

### Phase 22A — Config & Data Model (Foundation)

**Goal:** Add Blood Knight to classes and skills configs. Wire up the data layer. Zero logic changes.

**Files Modified:**
| File | Change |
|------|--------|
| `server/configs/classes_config.json` | Add `blood_knight` class definition |
| `server/configs/skills_config.json` | Add 4 skills + `class_skills.blood_knight` mapping |

**Config: `classes_config.json`**
```json
"blood_knight": {
  "class_id": "blood_knight",
  "name": "Blood Knight",
  "role": "Sustain Melee DPS",
  "description": "Vampiric warrior who drains the life force of enemies to sustain an unrelenting melee assault. Self-sufficient but selfish — no team utility.",
  "base_hp": 100,
  "base_melee_damage": 16,
  "base_ranged_damage": 0,
  "base_armor": 4,
  "base_vision_range": 6,
  "ranged_range": 0,
  "allowed_weapon_categories": ["melee", "hybrid"],
  "color": "#8B0000",
  "shape": "shield"
}
```

**Config: `skills_config.json`** — 4 new skills:
```json
"blood_strike": {
  "skill_id": "blood_strike",
  "name": "Blood Strike",
  "description": "A vampiric strike — deal 1.4x melee damage and heal yourself for 40% of damage dealt.",
  "icon": "🩸",
  "targeting": "entity",
  "range": 1,
  "cooldown_turns": 4,
  "mana_cost": 0,
  "effects": [
    { "type": "lifesteal_damage", "damage_multiplier": 1.4, "heal_pct": 0.40 }
  ],
  "allowed_classes": ["blood_knight"],
  "requires_line_of_sight": false
},
"crimson_veil": {
  "skill_id": "crimson_veil",
  "name": "Crimson Veil",
  "description": "Shroud yourself in stolen vitality — gain +30% melee damage and heal 6 HP/turn for 3 turns.",
  "icon": "🌑",
  "targeting": "self",
  "range": 0,
  "cooldown_turns": 6,
  "mana_cost": 0,
  "effects": [
    { "type": "buff", "stat": "melee_damage_multiplier", "magnitude": 1.3, "duration_turns": 3 },
    { "type": "hot", "heal_per_turn": 6, "duration_turns": 3 }
  ],
  "allowed_classes": ["blood_knight"],
  "requires_line_of_sight": false
},
"sanguine_burst": {
  "skill_id": "sanguine_burst",
  "name": "Sanguine Burst",
  "description": "Erupt in a fountain of stolen blood — deal 0.7x melee damage to all enemies within 1 tile and heal for 50% of total damage dealt.",
  "icon": "💉",
  "targeting": "self",
  "range": 0,
  "cooldown_turns": 7,
  "mana_cost": 0,
  "effects": [
    { "type": "lifesteal_aoe", "radius": 1, "damage_multiplier": 0.7, "heal_pct": 0.50 }
  ],
  "allowed_classes": ["blood_knight"],
  "requires_line_of_sight": false
},
"blood_frenzy": {
  "skill_id": "blood_frenzy",
  "name": "Blood Frenzy",
  "description": "Channel your wounds into rage — if below 40% HP, instantly heal 15 HP and gain +50% melee damage for 3 turns.",
  "icon": "🔥",
  "targeting": "self",
  "range": 0,
  "cooldown_turns": 8,
  "mana_cost": 0,
  "effects": [
    { "type": "conditional_buff", "hp_threshold": 0.40, "instant_heal": 15, "stat": "melee_damage_multiplier", "magnitude": 1.5, "duration_turns": 3 }
  ],
  "allowed_classes": ["blood_knight"],
  "requires_line_of_sight": false
}
```

**`class_skills` mapping:**
```json
"blood_knight": ["auto_attack_melee", "blood_strike", "crimson_veil", "sanguine_burst", "blood_frenzy"]
```

**Tests (Phase 22A):**
- Blood Knight class loads from config with correct stats (HP=100, melee=16, ranged=0, armor=4, vision=6, range=0)
- Blood Knight color is `#8B0000` and shape is `shield`
- Blood Strike skill loads with `lifesteal_damage` effect type, multiplier 1.4, heal_pct 0.40
- Crimson Veil skill loads with `buff` + `hot` effect types  
- Sanguine Burst skill loads with `lifesteal_aoe` effect type, radius 1
- Blood Frenzy skill loads with `conditional_buff` effect type, threshold 0.40
- `class_skills["blood_knight"]` maps to 5 correct skills in order
- `can_use_skill()` validates Blood Knight skills for blood_knight class
- `can_use_skill()` rejects Blood Knight skills for non-blood_knight classes
- Existing class tests still pass (regression check)

**Estimated tests:** 10

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass before proceeding.

---

### Phase 22B — Effect Handlers (Core Mechanics)

**Goal:** Implement 2 new effect type handlers (`lifesteal_damage`, `lifesteal_aoe`) and 1 conditional buff handler (`conditional_buff`), then connect them to the `resolve_skill_action()` dispatcher. Wire Crimson Veil's multi-effect (buff + HoT) through the existing buff handler.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/skills.py` | Add `resolve_lifesteal_damage()`, `resolve_lifesteal_aoe()`, `resolve_conditional_buff()` handlers |
| `server/app/core/skills.py` | Add 3 dispatcher branches in `resolve_skill_action()` |
| `server/app/core/skills.py` | Extend `resolve_buff()` to process secondary HoT effect in multi-effect buff skills |

#### Handler 1: `resolve_lifesteal_damage()` (~50 lines)

```
Input:  player, target_x, target_y, skill_def, players, obstacles, target_id
Logic:  1. Find target by target_id or position (clone from resolve_multi_hit)
        2. Validate adjacency (range 1) and target alive + enemy
        3. Calculate raw damage: floor(attack_damage * buff_mult * damage_multiplier)
        4. Subtract target armor → final_damage = max(1, raw - armor)
        5. Apply damage_taken_multiplier (Bard Dirge compat)
        6. Apply damage to target, check death
        7. Calculate heal: floor(final_damage * heal_pct)
        8. Heal caster: min(max_hp, hp + heal)
        9. Set cooldown, return ActionResult
Output: ActionResult with damage dealt, HP healed, and target death status
```

#### Handler 2: `resolve_lifesteal_aoe()` (~60 lines)

```
Input:  player, skill_def, players, obstacles
Logic:  1. Get caster position as AoE center
        2. Find all alive enemies within radius (Chebyshev distance)
        3. For each enemy: calc damage = max(1, floor(atk * buff_mult * mult) - armor)
        4. Apply damage, accumulate total_damage_dealt, track kills
        5. Calculate heal: floor(total_damage_dealt * heal_pct)
        6. Heal caster (capped at max_hp)
        7. Set cooldown, return ActionResult listing enemies hit + heal
Output: ActionResult with total damage, enemies hit count, HP healed
```

#### Handler 3: `resolve_conditional_buff()` (~40 lines)

```
Input:  player, skill_def
Logic:  1. Check HP threshold: if player.hp / player.max_hp >= threshold → fail (no CD consumed)
        2. Apply instant heal: player.hp = min(max_hp, hp + instant_heal)
        3. Apply melee_damage_multiplier buff for N turns (same as resolve_buff)
        4. Set cooldown, return ActionResult
Output: ActionResult with heal amount and buff applied, or failure message
```

#### Dispatcher Update

```python
# Add to resolve_skill_action():
elif effect_type == "lifesteal_damage":
    return resolve_lifesteal_damage(player, action.target_x, action.target_y, skill_def, players, obstacles, target_id=tid)
elif effect_type == "lifesteal_aoe":
    return resolve_lifesteal_aoe(player, skill_def, players, obstacles)
elif effect_type == "conditional_buff":
    return resolve_conditional_buff(player, skill_def)
```

#### Crimson Veil Multi-Effect

Crimson Veil's `effects[0]` is `buff` (melee_damage_multiplier) — it routes to `resolve_buff()`. The `resolve_buff()` handler needs a small extension: after applying the primary buff, check if `skill_def["effects"]` has additional entries. If `effects[1].type == "hot"`, add a HoT buff entry to `player.active_buffs` with `stat: "hot"`, `magnitude: heal_per_turn`, `remaining_turns: duration`. The existing `tick_buffs()` already processes HoT entries.

**Tests (Phase 22B):**

*Blood Strike (lifesteal_damage):*
- Blood Strike deals 1.4x melee damage to adjacent enemy
- Blood Strike heals caster for 40% of damage dealt
- Blood Strike respects target armor (min 1 damage)
- Blood Strike heal does not exceed max HP
- Blood Strike fails against non-adjacent target (too far)
- Blood Strike fails against dead target
- Blood Strike fails against ally
- Blood Strike sets cooldown to 4
- Blood Strike applies buff multiplier (Crimson Veil combo)
- Blood Strike target death triggers correctly

*Crimson Veil (buff + hot multi-effect):*
- Crimson Veil applies melee_damage_multiplier 1.3 for 3 turns
- Crimson Veil applies HoT that heals 6/turn for 3 turns
- Crimson Veil HoT heals on buff tick
- Crimson Veil buff multiplier affects Blood Strike damage
- Crimson Veil buff multiplier affects auto-attack damage
- Crimson Veil sets cooldown to 6

*Sanguine Burst (lifesteal_aoe):*
- Sanguine Burst hits all enemies within 1 tile of caster
- Sanguine Burst does not hit allies
- Sanguine Burst deals 0.7x melee damage per target
- Sanguine Burst heals for 50% of total damage dealt
- Sanguine Burst heal scales with number of enemies hit
- Sanguine Burst respects enemy armor (min 1 per target)
- Sanguine Burst heals nothing if no enemies in range (but still consumes CD)
- Sanguine Burst sets cooldown to 7
- Sanguine Burst kills trigger correctly

*Blood Frenzy (conditional_buff):*
- Blood Frenzy activates when HP < 40%
- Blood Frenzy FAILS when HP >= 40% (returns success=False)
- Blood Frenzy does NOT consume cooldown on failure
- Blood Frenzy heals 15 HP instantly on activation
- Blood Frenzy heal does not exceed max HP
- Blood Frenzy applies melee_damage_multiplier 1.5 for 3 turns
- Blood Frenzy sets cooldown to 8 on success
- Blood Frenzy stacks multiplicatively with Crimson Veil (1.3 × 1.5 = 1.95)

**Estimated tests:** 30–34

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass.

---

### Phase 22C — Buff System Integration

**Phase 22C — Skipped (no new buff types)**

All effects use existing buff system entries:
- `melee_damage_multiplier` — already wired in `get_melee_buff_multiplier()`
- `hot` buff ticks — already wired in `tick_buffs()`
- `damage_taken_multiplier` — already wired (for Dirge compat)

The only integration point is the multi-effect extension in `resolve_buff()` for Crimson Veil, which is handled in Phase 22B.

---

### Phase 22D — AI Behavior (`sustain_dps` role)

**Goal:** Implement AI decision-making so Blood Knight AI heroes and AI-controlled Blood Knights play intelligently.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/ai_skills.py` | Add `"blood_knight": "sustain_dps"` to `_CLASS_ROLE_MAP` |
| `server/app/core/ai_skills.py` | Add `_sustain_dps_skill_logic()` function (~60 lines) |
| `server/app/core/ai_skills.py` | Add `"sustain_dps"` branch to skill dispatcher |

#### AI Decision Logic

```python
def _sustain_dps_skill_logic(ai, enemies, all_units, grid_w, grid_h, obstacles):
    """Blood Knight AI: aggressive sustain melee — prioritize survival skills when wounded,
    AoE when surrounded, single-target lifesteal as default."""

    adjacent_enemies = [e for e in enemies if is_adjacent(ai.position, e.position)]
    
    # 1. Blood Frenzy — emergency when low HP
    if ai.max_hp > 0 and (ai.hp / ai.max_hp) < 0.40:
        if can_use_skill(ai, "blood_frenzy"):
            return _make_self_skill_action(ai, "blood_frenzy")
    
    # 2. Crimson Veil — pre-engagement buff when enemies nearby
    if can_use_skill(ai, "crimson_veil"):
        nearby = [e for e in enemies if _chebyshev(ai.position, e.position) <= 2]
        if adjacent_enemies or nearby:
            return _make_self_skill_action(ai, "crimson_veil")
    
    # 3. Sanguine Burst — AoE when 2+ enemies adjacent
    if can_use_skill(ai, "sanguine_burst") and len(adjacent_enemies) >= 2:
        return _make_self_skill_action(ai, "sanguine_burst")
    
    # 4. Blood Strike — default sustain on adjacent enemy
    if can_use_skill(ai, "blood_strike") and adjacent_enemies:
        target = min(adjacent_enemies, key=lambda e: e.hp)
        return _make_entity_skill_action(ai, "blood_strike", target)
    
    # 5. Fallback
    return None
```

**Tests (Phase 22D):**
- Blood Knight AI mapped to `sustain_dps` role in `_CLASS_ROLE_MAP`
- Blood Knight AI uses Blood Frenzy when HP < 40%
- Blood Knight AI skips Blood Frenzy when HP >= 40%
- Blood Knight AI uses Crimson Veil when enemies within 2 tiles
- Blood Knight AI skips Crimson Veil when no enemies nearby
- Blood Knight AI uses Sanguine Burst when 2+ enemies adjacent
- Blood Knight AI skips Sanguine Burst when only 1 enemy adjacent
- Blood Knight AI uses Blood Strike on lowest-HP adjacent enemy
- Blood Knight AI falls back to auto-attack when all skills on cooldown
- Blood Knight AI prioritizes Blood Frenzy over other skills when low HP

**Estimated tests:** 10

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass.

---

### Phase 22E — Frontend Integration (Rendering + UI)

**Goal:** Add Blood Knight to the client — shape rendering, class selection, colors, icons, inventory portrait.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/canvas/renderConstants.js` | Add blood_knight to `CLASS_COLORS`, `CLASS_SHAPES`, `CLASS_NAMES` |
| `client/src/canvas/unitRenderer.js` | Add `shield` shape rendering case |
| `client/src/components/WaitingRoom/WaitingRoom.jsx` | Add shield icon to shape map |
| `client/src/components/Inventory/Inventory.jsx` | Add shield SVG path to `CLASS_SHAPE_PATHS` |
| `client/src/components/Inventory/Inventory.jsx` | Add skill buff names to `formatBuffName` / `formatBuffEffect` |

#### renderConstants.js additions

```javascript
// CLASS_COLORS
blood_knight: '#8B0000',

// CLASS_SHAPES
blood_knight: 'shield',

// CLASS_NAMES
blood_knight: 'Blood Knight',
```

#### unitRenderer.js — Shield Shape

```javascript
case 'shield': {
  // Kite shield / heraldic shield — pointed bottom, curved top
  const shW = r * 0.85;
  const shH = r * 1.1;
  ctx.beginPath();
  ctx.moveTo(cx, cy - shH);                        // top center
  ctx.quadraticCurveTo(cx + shW, cy - shH * 0.6,   // top-right curve
                       cx + shW, cy - shH * 0.1);   // right shoulder
  ctx.lineTo(cx + shW * 0.5, cy + shH * 0.5);      // right lower
  ctx.lineTo(cx, cy + shH);                         // bottom point
  ctx.lineTo(cx - shW * 0.5, cy + shH * 0.5);      // left lower
  ctx.lineTo(cx - shW, cy - shH * 0.1);             // left shoulder  
  ctx.quadraticCurveTo(cx - shW, cy - shH * 0.6,   // top-left curve
                       cx, cy - shH);                // back to top
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  break;
}
```

#### WaitingRoom.jsx — Shape icon

```
cls.shape === 'shield' ? '🛡' : ...
```

#### Inventory.jsx — SVG portrait path

```javascript
shield: <path d="M12 2 C16 2 20 4 20 8 L18 18 12 22 6 18 4 8 C4 4 8 2 12 2Z" />,
```

#### Inventory.jsx — Buff name formatting

```javascript
// formatBuffName:
crimson_veil: 'Crimson Veil',
blood_frenzy: 'Blood Frenzy',

// formatBuffEffect:
// No new buff stats needed — melee_damage_multiplier and hot already formatted
```

**Tests (Phase 22E):** Visual verification — manual checklist:
- [ ] Blood Knight appears in class selection screen
- [ ] Shield shape renders correctly on canvas
- [ ] Color (#8B0000 dark red) displays correctly and is distinguishable from Hexblade red (#e04040)
- [ ] Blood Knight name shows in nameplate
- [ ] Inventory portrait shows shield shape
- [ ] Crimson Veil buff icon displays in HUD
- [ ] Blood Frenzy buff icon displays in HUD
- [ ] Skill icons appear in bottom bar with correct names

---

### Phase 22F — Particle Effects & Audio (Polish)

**Goal:** Add visual and audio feedback for Blood Knight skills.

**Files Modified:**
| File | Change |
|------|--------|
| `client/public/particle-presets/skills.json` | Add blood_knight skill effects |
| `client/public/particle-presets/buffs.json` | Add Crimson Veil + Blood Frenzy buff auras |
| `client/public/audio-effects.json` | Add blood_knight audio triggers |
| `client/src/audio/soundMap.js` | Add blood_knight sound mappings |

#### Particle Effects

| Skill | Particle Effect | Description |
|-------|----------------|-------------|
| Blood Strike | `blood-strike-drain` | Dark red slash + crimson wisps flowing from target back to caster |
| Crimson Veil | `crimson-veil-aura` | Swirling dark red mist aura around caster for buff duration |
| Sanguine Burst | `sanguine-burst-nova` | Outward crimson explosion ring + blood droplets, then healing wisps inward |
| Blood Frenzy | `blood-frenzy-ignite` | Intense pulsing crimson glow + red energy spikes radiating from caster |

#### Audio

| Skill | Sound | Category |
|-------|-------|----------|
| Blood Strike | Wet slash + ethereal drain whoosh | skills |
| Crimson Veil | Low hum + swirling wind intensifying | skills |
| Sanguine Burst | Visceral burst + liquid splash | skills |
| Blood Frenzy | Heartbeat accelerating + rage roar | skills |

**Tests (Phase 22F):** Manual verification only.
- [ ] Each skill triggers correct particle effect
- [ ] Crimson Veil aura visible on Blood Knight for buff duration
- [ ] Blood Frenzy glow visible on Blood Knight for buff duration
- [ ] Audio plays on skill use
- [ ] No console errors from missing assets

---

### Phase 22G — Sprite Integration (Optional)

**Goal:** Add Blood Knight sprite variants from the character sheet atlas.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/canvas/SpriteLoader.js` | Add blood_knight sprite variants |

*This phase depends on finding suitable sprites in the existing atlas. If no blood_knight-appropriate sprites exist, the shield shape fallback works perfectly.*

---

## Implementation Order & Dependencies

```
Phase 22A (Config)           ← No dependencies, pure data
    ↓
Phase 22B (Effect Handlers)  ← Depends on 22A (needs skill definitions)
    ↓
Phase 22C (Buff Integration) ← SKIPPED — no new buff types
    ↓
Phase 22D (AI Behavior)      ← Depends on 22B (needs handlers working)
    ↓
Phase 22E (Frontend)         ← Depends on 22A — can parallel with 22D
    ↓
Phase 22F (Polish)           ← Depends on 22E (needs rendering working)
    ↓
Phase 22G (Sprites)          ← Optional, last
```

**Parallelizable:** 22D + 22E can run in parallel after 22B.

---

## Test Summary

| Phase | Test Count | Focus |
|-------|:----------:|-------|
| 22A — Config | 10 | Class/skill loading, validation |
| 22B — Effect Handlers | 49 | Lifesteal, AoE lifesteal, conditional buff, combos |
| 22C — Buff Integration | 0 (skipped) | — |
| 22D — AI Behavior | 10 | AI decision logic |
| 22E — Frontend | 0 (manual) | Visual verification |
| 22F — Polish | 0 (manual) | Particles, audio |
| **Total** | **~69–73** | |

---

## Tuning Levers

| Parameter | Initial Value | Reduce If... | Increase If... |
|-----------|:------------:|--------------|----------------|
| HP | 100 | Too survivable with lifesteal | Dies too fast before sustain kicks in |
| Melee Damage | 16 | Lifesteal healing too high (damage-derived) | Not enough threat / too easily ignored |
| Armor | 4 | Too tanky (combined with lifesteal) | Dies to burst before skills come online |
| Blood Strike multiplier | 1.4 | Too much single-target burst | Not competitive with Crusader auto-attack |
| Blood Strike heal % | 40% | Unkillable in 1v1 melee | Sustain too weak to matter |
| Blood Strike cooldown | 4 | Perma-sustain, never needs healer | Sustain windows too narrow |
| Crimson Veil damage buff | 1.3× | Combined with Frenzy too much burst | Buff window doesn't feel impactful |
| Crimson Veil HoT | 6/turn | Passive sustain too strong | HoT feels irrelevant |
| Crimson Veil cooldown | 6 | Near-permanent uptime | Too rare to define playstyle |
| Sanguine Burst multiplier | 0.7× | AoE clear too fast | AoE feels pointless vs auto-attacking |
| Sanguine Burst heal % | 50% | Pack sustain trivializes PvE | No reason to use over Blood Strike |
| Sanguine Burst radius | 1 | Too many enemies hit | Can't reach enough enemies to heal from |
| Blood Frenzy HP threshold | 40% | Too easy to activate | Too risky to use |
| Blood Frenzy instant heal | 15 | Emergency heal too safe | Doesn't save you from death |
| Blood Frenzy damage buff | 1.5× | Burst window too oppressive | Doesn't feel like a power spike |
| Blood Frenzy cooldown | 8 | Available too often | Once-per-fight feels bad |

### Known Balance Risks

1. **Unkillable in PvE trash:** If Blood Strike + Sanguine Burst cycling keeps a Blood Knight at full HP through trash packs, they completely replace Confessor as the sustain plan. **Mitigation:** Heal percentages are tuned low enough that burst damage (3+ enemies, champion packs) still chunks them. They sustain against steady pressure, not spike damage.

2. **Crimson Veil + Blood Frenzy stacking:** The multiplicative stack (1.3 × 1.5 = 1.95× melee damage) gives a brief window where Blood Knight out-damages even Crusader. **Mitigation:** This requires being below 40% HP, so the Blood Knight is at real risk of dying during this window. The Frenzy's 8-turn cooldown also limits how often this occurs.

3. **PvP 1v1 dominance against melee:** Blood Knight with lifesteal may be nearly impossible for Crusader or Hexblade to kill in prolonged melee trades. **Mitigation:** Blood Knight has 4 armor vs Crusader's 8 — they take significantly more damage per hit. Crusader's Taunt + Shield Bash stun disrupts Blood Knight's rotation. Hexblade's Wither DoT ignores armor and ticks through lifesteal.

4. **Kiting vulnerability:** Blood Knight has zero ranged options and no gap-closer. Ranger and Mage can kite indefinitely. **Mitigation:** This is intentional and the class's primary counter. Blood Knight must rely on party members (Bard slow, Inquisitor detection) to deal with ranged threats.

---

## Future Enhancements (Post-Phase 22)

- **Blood Pact (passive):** Below 25% HP, auto-attacks gain +20% lifesteal. Would add even more low-HP reward synergy but needs careful balance testing.
- **Crimson Weapon Enchant:** Cosmetic — Blood Knight's melee weapon glows crimson during Crimson Veil buff. Purely visual.
- **Blood Knight Set Items:** Equipment set designed for Blood Knight — "Sanguine Regalia" with set bonuses that amplify lifesteal or reduce Blood Frenzy threshold.
- **Blood Link:** Future skill concept — tether to an ally, sharing a portion of damage they receive while healing the Blood Knight. Would break the "no utility" pillar but could be an interesting evolution.

---

## Phase Checklist

- [x] **22A** — Blood Knight added to `classes_config.json`
- [x] **22A** — 4 skills added to `skills_config.json` (blood_strike, crimson_veil, sanguine_burst, blood_frenzy)
- [x] **22A** — `class_skills.blood_knight` mapping added
- [x] **22A** — Config loading tests pass (60 tests)
- [x] **22A** — Blood Knight names added to `names_config.json` (15 names)
- [x] **22A** — `auto_attack_melee` allowed_classes updated to include `blood_knight`
- [x] **22A** — Existing test regressions fixed (class count 7→8, skill count 36→40)
- [x] **22B** — `resolve_lifesteal_damage()` handler implemented
- [x] **22B** — `resolve_lifesteal_aoe()` handler implemented
- [x] **22B** — `resolve_conditional_buff()` handler implemented
- [x] **22B** — `resolve_buff()` extended for multi-effect HoT (Crimson Veil)
- [x] **22B** — `resolve_skill_action()` dispatcher updated (3 new branches)
- [x] **22B** — All handler tests pass (49 tests)
- [ ] **22C** — Skipped — no new buff types
- [x] **22D** — `_sustain_dps_skill_logic()` implemented
- [x] **22D** — `_CLASS_ROLE_MAP["blood_knight"] = "sustain_dps"` added
- [x] **22D** — AI behavior tests pass (22 tests)
- [x] **22D** — Regression fixes: role map count 27→28, sustain_dps added to known roles
- [x] **22E** — `renderConstants.js` updated (color, shape, name)
- [x] **22E** — Shield shape renders in `unitRenderer.js`
- [x] **22E** — WaitingRoom class select shows Blood Knight
- [x] **22E** — Inventory portrait & buff names updated
- [x] **22E** — HeaderBar buff names updated (crimson_veil, blood_frenzy)
- [x] **22F** — Particle effects added (4 skill effects + 2 buff auras)
- [x] **22F** — Audio triggers added
- [x] **22G** — Sprite variants mapped (4 variants: BloodKnight_Female_1, Blood_Knight_Female_2, Blood_Knight_Female_3, Blood_Knight_Male_1)
- [x] **AI Polish** — Crimson Veil: skip re-cast when buff already active (matches Crusader Bulwark/War Cry pattern)
- [x] **AI Polish** — Blood Strike: skip at full HP to avoid wasting lifesteal as overheal (save CD for when sustain matters)
- [ ] Balance pass after playtesting

---

## Post-Implementation Cleanup

After all phases complete:

1. **Update `README.md`:**
   - Add Blood Knight to the class count in the Features table (8 Playable Classes)
   - Add Phase 22 to the Documentation → Phase Specs list
   - Update the status line at the top
   - Update the test count

2. **Update `docs/Current Phase.md`:**
   - Add Phase 22 milestone entry with test counts

3. **Update `docs/Game stats references/game-balance-reference.md`:**
   - Add Blood Knight stat block
   - Add Blood Knight skills (Blood Strike, Crimson Veil, Sanguine Burst, Blood Frenzy)
   - Update class comparison table
   - Add Blood Knight auto-attack DPS entry
   - Add Blood Knight TTK tables

4. **Final test run:**
   - `pytest server/tests/` — ALL tests pass, zero failures
   - Record final test count

---

**Document Version:** 1.2
**Created:** March 5, 2026
**Status:** AI Polish Pass — Crimson Veil buff-already-active guard, Blood Strike full-HP skip
**Prerequisites:** Phase 21 (Bard) Complete
