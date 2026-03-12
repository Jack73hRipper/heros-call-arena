# Phase 26 — Shaman Class (Totemic Healer / Area Support)

## Pre-Implementation Checklist

Before starting, gather this context:

- [ ] Read `README.md` for full project structure and architecture
- [ ] Read `server/configs/classes_config.json` for existing class definitions
- [ ] Read `server/configs/skills_config.json` for existing skills and effect types
- [ ] Read `server/app/core/skills.py` for the skill resolver and existing handlers
- [ ] Read `server/app/core/combat.py` for the damage pipeline
- [ ] Read `server/app/core/ai_skills.py` for AI role maps and skill logic
- [ ] Read `client/src/canvas/renderConstants.js` for class colors/shapes/names
- [ ] Read `client/src/canvas/unitRenderer.js` for shape rendering
- [ ] Read `docs/Game stats references/game-balance-reference.md` for balance context

---

**Created:** March 2026
**Status:** Phase 26F Complete (Particle Effects & Audio)
**Previous:** Phase 25 (Revenant Class)
**Goal:** Add the Shaman as the 11th playable class — a dark ritualist who controls the battlefield through persistent totems, crowd control, and death prevention. Fills the second Healer slot with a fundamentally different support philosophy from Confessor: where the Confessor heals reactively (burst heal on a damaged ally), the Shaman heals **proactively** by placing healing zones and shapes the fight with a damage totem, root CC, and ally death prevention. Creates a new "totem" entity system — persistent ground objects with effects and limited HP — and introduces "root" as a new CC type.

---

## Overview

A grim tribal ritualist who communes with dark spirits through bone totems planted into the earth. The Shaman doesn't touch the wounded — they plant a totem, and the spirits do the mending. Where the Confessor is a battlefield medic running to every injury, the Shaman is a strategist who prepares the ground before the fight. In dungeon corridors and choke points, a well-placed totem turns a dangerous room into a sanctuary.

**Role:** Totemic Healer / Area Support

### Design Pillars

1. **Dual Totem System** — The Shaman's identity IS totems. Two totem types — Healing Totem (sustains allies) and Searing Totem (punishes enemies) — create persistent battlefield zones. Managing two totems simultaneously gives the Shaman a unique strategic minigame no other class has.
2. **Totem as Entity** — Totems are placed on the ground as destructible objects. Enemies can kill totems (they have HP). This creates tactical counter-play: do enemies focus the healing totem? The searing totem? The party? A unique mechanic not yet in the game.
3. **Battlefield Architect** — The Shaman shapes the fight before it happens. Healing zones for allies, damage zones for enemies, roots to pin enemies in the damage zone, and a soul anchor to prevent death. Every skill interacts with the others to create a satisfying tactical loop.
4. **Distinct from Confessor** — Confessor = reactive single-target burst healing + holy damage. Shaman = proactive AoE persistent healing + zone control + crowd control. Confessor is better when one person is focused; Shaman is better when the whole party takes sustained damage and the battlefield can be shaped.
5. **Grimdark Ritualist Fantasy** — Bone totems, dark spirits, spectral hands, rattling chants. Not a friendly nature shaman — a grim spiritualist who commands the dead to bind, burn, and mend.

---

## Base Stats

| Stat | Value | Rationale |
|------|-------|-----------|
| **HP** | 95 | Between Bard (90) and Confessor (100). Slightly squishier than Confessor — the Shaman should stay behind the frontline, not beside it. |
| **Melee Damage** | 8 | Weak — same as Confessor and Ranger. Staff whacks, not warrior strikes. |
| **Ranged Damage** | 10 | Moderate — same as Bard. Spirit bolt at range for basic attacks. Skills are where the class shines. |
| **Armor** | 3 | Light — same as Confessor and Bard. Support tier armor. |
| **Vision Range** | 7 | Standard — no reason to be a scout, no reason to be blind. |
| **Ranged Range** | 4 | Medium range — same as Bard and Hexblade. Needs to reach the fight to plant totems nearby but stays behind tanks. |
| **Allowed Weapons** | `["caster", "hybrid"]` | Ritual staves, spirit fetishes, wands. Same categories as Bard/Mage. |
| **Color** | `#8B6914` | Dark goldenrod / burnt umber — earthy, tribal, distinct from Bard's amber (#d4a017) and Confessor's bright yellow (#f0e060). Evokes bone, earth, and ritual. **Note:** this was previously the werewolf enemy color — update ENEMY_COLORS to use a slightly different shade if needed. |
| **Shape** | `totem` | A totem pole silhouette — stacked segments/faces, immediately communicates the class identity. Unique from all existing shapes. |

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
 Revenant ......   130      14       0      5       5      0   Retaliation Tank
 SHAMAN ........    95       8      10      3       7      4   Totemic Healer
```

**Design notes:**
- HP 95 is mid-tier — survives longer than Mage/Ranger/Inquisitor but not a frontliner.
- Melee 8 + Ranged 10 mirrors Confessor's "low personal damage, high support value" pattern.
- Identical armor (3) to Confessor — they're peers in durability; the difference is in *how* they heal.
- Range 4 means the Shaman places totems from behind the frontline, not from max range.

### Auto-Attack Damage (1.15× multiplier)

```
 Shaman ........ 10 × 1.15 = 11.5 ranged per hit (range 4)
```

Identical to Bard auto-attack. Lowest-tier personal DPS. The Shaman's value is entirely in totem placement and utility — personal damage is an afterthought.

---

## Skills

### Skill Overview

| Slot | Skill | Effect Type | Target | Range | Cooldown | Summary |
|:----:|-------|------------|--------|:-----:|:--------:|---------|
| 0 | Auto Attack (Ranged) | ranged_damage | entity | 4 | 0 | 1.15× ranged damage (11.5) |
| 1 | Healing Totem | `place_totem` (**NEW**) | ground_aoe | 4 | 6 | Place a totem that heals all allies within 2 tiles for 8 HP/turn for 4 turns. Totem has 20 HP. |
| 2 | Searing Totem | `place_totem` (**NEW**) | ground_aoe | 4 | 6 | Place a totem that deals 6 magic damage/turn to all enemies within 2 tiles for 4 turns. Totem has 20 HP. Max 1 of each totem type. |
| 3 | Soul Anchor | `soul_anchor` (**NEW**) | ally_or_self | 4 | 10 | Mark an ally — if they would die within 4 turns, they survive at 1 HP instead. Consumed on trigger. |
| 4 | Earthgrasp | `aoe_root` (**NEW**) | ground_aoe | 4 | 7 | Root all enemies within radius 2 for 2 turns — can't move, CAN still attack/use skills. |

### Skill Details

#### Healing Totem 🪵 (Persistent AoE Heal Zone)

```
Effect Type:   place_totem (NEW — creates a destructible ground entity with AoE heal pulse)
Targeting:     ground_aoe (target an empty tile)
Radius:        2 tiles (healing radius around the totem)
Range:         4 tiles (where the totem can be placed)
Cooldown:      6 turns
LOS Required:  Yes (must see the placement tile)
Effect:        Place a Healing Totem on an empty tile. The totem is a destructible
               entity with 20 HP. Each turn, it heals all allies within 2 tiles
               for 8 HP. The totem lasts 4 turns, then crumbles. Enemies can attack
               and destroy the totem. Only 1 Healing Totem can be active per Shaman.
```

**Design:** The Shaman's signature skill. Unlike Confessor's Heal (30 HP burst, single target, CD 4), the Healing Totem provides 8 HP/turn to *everyone* nearby for 4 turns — potentially 32 HP per ally in a 4-person party = 128 total healing vs Confessor's 30. But enemies can destroy the totem, and allies must stay in range. High ceiling, higher skill floor.

**Damage/healing/effect examples:**
```
Healing Totem, 3 allies in radius for full 4 turns:
  8 HP × 3 allies × 4 turns = 96 total healing
  Equivalent to 3.2× Confessor Heals over the same period

Healing Totem, 1 ally in radius for 4 turns:
  8 HP × 1 ally × 4 turns = 32 total healing
  Slightly better than 1 Confessor Heal (30) but requires positioning

Healing Totem destroyed after 2 turns by enemy:
  8 HP × 3 allies × 2 turns = 48 total healing
  Still more than 1 Confessor Heal, but half the potential

Compare Confessor over 6 turns (Heal CD 4 + Prayer CD 6):
  Heal (30) + Prayer (8/turn × 4 = 32) = 62 HP to one ally
  Shaman totem to 3 allies: 96 HP total — better throughput but fragile
```

**Implementation:** New handler `resolve_place_totem()`. Creates a new "totem" entity at the target tile — a lightweight object stored in match state (similar to how doors/chests work, but with HP and a per-turn heal pulse). The totem needs:
- Position (x, y)
- HP (20) — enemies can target it like a unit
- Heal radius (2)
- Heal per tick (8)
- Duration remaining (4)
- Owner ID (shaman who placed it)

In `server/app/core/turn_phases/buffs_phase.py` (or `server/app/services/tick_loop.py`), process active totems each turn: heal allies in radius, tick down duration, check if destroyed. ~80 lines for handler + ~40 lines for totem tick logic.

**Balance lever:** Totem HP (20), heal per turn (8), heal radius (2), duration (4 turns), cooldown (6), placement range (4), max active per type (1)

---

#### Searing Totem 🔥 (Persistent AoE Damage Zone)

```
Effect Type:   place_totem (NEW — same totem entity system as Healing Totem, damage variant)
Targeting:     ground_aoe (target an empty tile)
Radius:        2 tiles (damage radius around the totem)
Range:         4 tiles (where the totem can be placed)
Cooldown:      6 turns
LOS Required:  Yes (must see the placement tile)
Effect:        Place a Searing Totem on an empty tile. The totem is a destructible
               entity with 20 HP. Each turn, it deals 6 damage to all enemies within
               2 tiles. The totem lasts 4 turns, then crumbles. Enemies can attack
               and destroy the totem. Only 1 Searing Totem can be active per Shaman.
               (Can coexist with 1 Healing Totem — max 1 of each type.)
```

**Design:** The Shaman's offensive partner to the Healing Totem. Where the Healing Totem sustains allies, the Searing Totem punishes enemies who remain in an area. This creates true battlefield zoning — the Shaman defines "safe" and "dangerous" areas of the map with their two totems. The dual-totem system is the Shaman's unique minigame: placement, timing, and deciding which totem takes priority when cooldowns align.

Critically, the Searing Totem synergizes with Earthgrasp — root enemies in the damage zone and they eat 6 damage/turn with no escape. This is the Shaman's core combo.

**Damage/healing/effect examples:**
```
Searing Totem, 3 enemies in radius for full 4 turns:
  6 damage × 3 enemies × 4 turns = 72 total damage
  Comparable to a Mage Fireball (28 damage) x2.5 — but over time and conditional

Searing Totem, 1 enemy in radius for 4 turns:
  6 damage × 1 enemy × 4 turns = 24 total damage
  Modest single-target value — the totem shines with multiple enemies

Searing Totem destroyed after 2 turns by enemy:
  6 damage × 3 enemies × 2 turns = 36 total damage
  Still solid, and the enemy spent attacks on the totem instead of your party

Searing Totem + Earthgrasp combo (enemies rooted for 2 turns):
  6 damage × 3 enemies × 2 guaranteed turns = 36 damage (guaranteed)
  + potential 2 more turns if enemies don't move away after root expires

Compare to Plague Doctor Miasma (10 damage + slow, AoE, one-shot):
  Searing Totem: 72 potential damage vs Miasma: 10 damage
  Totem is higher total but spread over turns and destructible
```

**Implementation:** Reuses the `resolve_place_totem()` handler built for Healing Totem. The handler dispatches based on `totem_type` field in the skill effect definition. Searing Totem creates a totem entity with `damage_per_turn` instead of `heal_per_turn`. The totem tick logic in `buffs_phase.py` processes both types. ~20 additional lines (mostly in the tick logic to handle damage variant).

**Balance lever:** Totem HP (20), damage per turn (6), damage radius (2), duration (4 turns), cooldown (6), placement range (4), max active per type (1)

---

#### Soul Anchor ⚓ (Ally Death Prevention)

```
Effect Type:   soul_anchor (NEW — applies a cheat-death buff to an ally)
Targeting:     ally_or_self (target an ally or self)
Radius:        — (single target)
Range:         4 tiles
Cooldown:      10 turns
LOS Required:  No
Effect:        Mark an ally with Soul Anchor for 4 turns. If the anchored ally
               would receive a killing blow during that time, their HP is set to
               1 instead. The Soul Anchor is consumed upon triggering (one-time
               use per cast). Only 1 Soul Anchor can be active per Shaman.
```

**Design:** The Shaman's high-impact insurance policy. This is similar to Revenant's Undying Will (self-only cheat death), but cast on an *ally* — a first in the game. The long cooldown (10 turns — longest of any Shaman skill) means it must be used wisely. Do you anchor the Crusader before a boss room? Save it for the Mage who's always in danger? Use it on yourself when low?

This creates dramatic moments: your Ranger takes a lethal hit, drops to 1 HP, and the Soul Anchor crumbles — now you rush to heal them before the next attack finishes the job. High tension, high skill expression.

**Damage/healing/effect examples:**
```
Anchored Crusader (150 HP) takes 160 damage hit (would kill):
  Without Soul Anchor: Crusader dies (150 - 160 = dead)
  With Soul Anchor: Crusader set to 1 HP, anchor consumed
  Crusader is alive but in extreme danger — needs immediate healing

Anchored Mage (70 HP, currently 25 HP) takes 30 damage:
  Without Soul Anchor: Mage dies (25 - 30 = dead after armor)
  With Soul Anchor: Mage set to 1 HP, anchor consumed
  Glass cannon saved — the Shaman's totems or Confessor must stabilize them

Soul Anchor expires unused after 4 turns:
  No effect — the anchor simply fades
  The 10-turn cooldown means this was a "wasted" cast
  Good Shamans time it to the danger window, bad Shamans waste it pre-emptively

Compare to Revenant's Undying Will:
  Undying Will: self-only, revives at 30% HP, 5-turn window, CD 10
  Soul Anchor: ally-target, survives at 1 HP, 4-turn window, CD 10
  Undying Will is safer (30% HP vs 1 HP) but selfish
  Soul Anchor is riskier (1 HP) but altruistic — requires follow-up healing
```

**Implementation:** New handler `resolve_soul_anchor()`. Applies a `soul_anchor` buff to the target ally's `active_buffs` list: `{"buff_id": "soul_anchor", "type": "soul_anchor", "stat": "soul_anchor", "caster_id": player.player_id, "turns_remaining": 4, "magnitude": 0}`. In the death pipeline (`deaths_phase.py`), before registering a death, check for `soul_anchor` buff in `dead_unit.active_buffs` — if present, set HP to 1 and remove the buff. Same pattern as Revenant's `cheat_death` in `deaths_phase.py` but for others. ~30 lines for handler + ~15 lines for deaths_phase.py integration.

**Balance lever:** Duration window (4 turns), cooldown (10 turns), survive HP (1), range (4), max active anchors (1)

---

#### Earthgrasp 🩸 (AoE Root — New CC Type)

```
Effect Type:   aoe_root (NEW — applies root debuff to enemies in target area)
Targeting:     ground_aoe (target a tile)
Radius:        2 tiles
Range:         4 tiles
Cooldown:      7 turns
LOS Required:  Yes
Effect:        Spectral hands erupt from the ground. All enemies within 2 tiles of
               the target tile are rooted for 2 turns. Rooted enemies CANNOT MOVE
               but CAN still attack and use skills. Rooted enemies can be attacked
               normally. Root is a new CC type distinct from slow and stun.
```

**Design:** Introduces **root** as a new crowd control type — a middle ground between slow (reduced movement, can still act) and stun (cannot act at all). Rooted enemies are pinned in place but fully combat-capable. This is distinct from every existing CC:
- **Slow** (Frost Nova, Miasma, Crippling Shot) — enemies can still move, just less
- **Stun** (Shield Bash) — enemy can't do anything for 1 turn
- **Root** (Earthgrasp) — enemies can attack and use skills but cannot reposition

The key synergy: root enemies ON TOP of the Searing Totem. They eat 6 damage/turn for 2 turns with no escape. This is the Shaman's signature combo — Earthgrasp into Searing Totem (or vice versa) creates a kill zone.

Also counters melee enemies hard — a rooted warrior can't close distance to your backline. But ranged enemies can still shoot freely, so it's not always dominant.

**Damage/healing/effect examples:**
```
3 melee enemies rooted 3 tiles away from your party:
  They cannot move for 2 turns — your Ranger, Mage, and Bard have 2 free turns
  of ranged attacks without taking melee damage
  Ranger: 2 turns × ~20 damage = ~40 damage dealt freely
  Effective value: 40+ damage enabled by denying enemy movement

3 enemies rooted inside Searing Totem radius:
  6 damage × 3 enemies × 2 turns (root) = 36 guaranteed totem damage
  + any ranged attacks from party during that time
  The root ensures they can't walk out of the searing zone

1 ranged enemy rooted:
  They can still shoot — root is less effective vs ranged enemies
  But they can't reposition for better LOS or to escape your melee fighters

Compare to Frost Nova (Mage): 12 damage + slow, 2 tiles, self-centered, CD 6
  Earthgrasp: 0 damage, root (stronger CC), 2 tiles, ground-targeted (range 4), CD 7
  Earthgrasp is stronger CC but deals no damage and is longer cooldown
  Frost Nova is self-centered (Mage in danger), Earthgrasp is remote (Shaman safe)

Compare to Miasma (Plague Doctor): 10 damage + slow, 2 tiles, ground-targeted, CD 6
  Earthgrasp: 0 damage, root (much stronger CC), same radius/targeting, CD 7
  Earthgrasp trades damage for a hard CC that completely prevents movement
```

**Implementation:** New handler `resolve_aoe_root()`. Finds all enemies within radius of target tile and applies a `rooted` debuff to each enemy's `active_buffs`: `{"buff_id": "earthgrasp", "type": "aoe_root", "stat": "rooted", "turns_remaining": 2, "magnitude": 0}`. In `skills.py`, add a new `is_rooted()` helper (following the `is_stunned()` / `is_slowed()` pattern). In the movement phase (`movement_phase.py`), import `is_rooted` from `skills.py` and check — if present, skip the unit's movement (they stay in place). The unit can still perform combat and skill actions. ~25 lines for handler + ~5 lines for `is_rooted()` helper + ~10 lines for movement_phase.py integration.

**Balance lever:** Root duration (2 turns), radius (2 tiles), cooldown (7), range (4)

---

### Complete Shaman Kit

```
Slot 0: Auto Attack (Ranged) — 11.5 ranged damage per hit (1.15×, range 4)
Slot 1: Healing Totem  — Place a totem that heals allies within 2 tiles for 8 HP/turn for 4 turns (CD 6)
Slot 2: Searing Totem  — Place a totem that deals 6 damage/turn to enemies within 2 tiles for 4 turns (CD 6)
Slot 3: Soul Anchor    — Mark an ally — if they’d die within 4 turns, survive at 1 HP instead (CD 10)
Slot 4: Earthgrasp     — Root all enemies within 2 tiles of target for 2 turns (CD 7)
```

**The Synergy Loop:**
1. **Healing Totem** near your party → sustained healing zone
2. **Searing Totem** in enemy territory → sustained damage zone
3. **Earthgrasp** enemies near the Searing Totem → they’re stuck eating damage
4. **Soul Anchor** on whoever’s in the most danger → insurance policy

Every skill interacts with the others. The Shaman is a battlefield architect.

---

## DPS Contribution Analysis

### Direct DPS (Personal)

```
Auto-attack:     11.5 damage per turn (vs 0 armor)
Searing Totem:   6 damage/turn to enemies in radius (up to 4 turns)
Earthgrasp:      0 direct damage (CC only)
Soul Anchor:     0 damage (utility)

Total personal DPT: 11.5 auto + 6-18 totem = 17.5-29.5 (with totem active)
```

### Team Impact (Healing + Damage + CC + Death Prevention)

```
Healing Totem (3 allies, 4 turns):
  96 total healing → equivalent to 3.2× Confessor Heals
  HPS (healing per turn-slot): 96 / 6 CD = 16 HP/turn average

Searing Totem (3 enemies, 4 turns):
  72 total damage → comparable to 2.5× Fireballs
  DPT: 72 / 6 CD = 12 damage-equivalent per turn
  With Earthgrasp combo: 36 guaranteed damage (2 rooted turns)

Earthgrasp (3 melee enemies rooted, 2 turns):
  Enables ~40-80 free ranged damage from party (enemies can't close distance)
  Denies ~30-60 melee damage against party (enemies can't reach)
  DPT equivalent: varies heavily — extremely high vs melee-heavy encounters

Soul Anchor:
  Prevents 1 death per 10-turn cooldown cycle
  Value: incalculable in permadeath dungeon runs
  In sustained fights: roughly equivalent to a full heal on the target

Full combo over 10 turns:
  Healing Totem (96 heal) + Searing Totem (72 dmg) + Earthgrasp (40+ enabled)
  + Soul Anchor (1 death prevented) + auto-attacks (115 dmg)
  Total value: 200+ damage/healing + CC + death prevention

Compare to Confessor over same period:
  Heal (30 ×2) + Prayer (32 ×2) + Shield of Faith (15 prevented ×2) + Exorcism (20 ×2)
  = ~125 healing + 40 damage + 30 prevented
  Shaman: higher AoE throughput, more utility, less burst single-target

Conclusion: Much higher theoretical output than original kit, but conditional on:
  - Allies staying in range of Healing Totem
  - Enemies staying in range of Searing Totem (Earthgrasp helps!)
  - Totems not being destroyed
  - Soul Anchor timing on the right target
```

---

## AI Behavior (totemic_support role)

### AI Role: `totemic_support`

The Shaman AI is a backline support that prioritizes placing totems strategically — Healing Totem near injured allies, Searing Totem near enemy clusters — while using Earthgrasp to lock enemies in the damage zone and Soul Anchor to protect endangered frontliners. It stays behind the frontline and avoids melee combat. The Shaman AI is positioning-aware: it considers where allies and enemies are clustered to maximize totem value.

### Decision Priority

```
1. Healing Totem → If 1+ allies within 4 tiles are below 70% HP and no active healing totem exists
2. Searing Totem → If 1+ enemies are within range and no active searing totem exists
3. Earthgrasp   → If 1+ enemies within range (scoring still prefers multi-target & searing totem combos)
4. Soul Anchor  → If a frontline ally (Crusader/Revenant/Blood Knight) is below 30% HP and no active anchor
5. Auto-attack  → Fallback, target nearest enemy in range
```

### Positioning

- **Backline support** — stays 2-3 tiles behind the frontline
- Uses `_support_move_preference()` (same as Confessor) to stay near the party centroid
- Places Healing Totems between itself and the party center (maximizing ally time near totem)
- Places Searing Totems toward the enemy approach vector (enemies walk into damage)
- Retreat conditions: if any enemy is adjacent and no allies within 2 tiles, move away

### Smart Targeting Logic

```python
# Healing Totem placement:
# Score each empty tile within range:
#   +3 per injured ally within totem radius 2
#   +1 per healthy ally within totem radius 2
#   -2 if enemy within 1 tile of placement (totem will be destroyed)
# Place at highest scoring tile

# Searing Totem placement:
# Score each empty tile within range:
#   +3 per enemy within totem radius 2
#   +2 per rooted enemy within totem radius 2 (Earthgrasp combo!)
#   -1 if ally within 1 tile of placement (want offensive positioning)
# Place at highest scoring tile

# Earthgrasp targeting:
# Score each ground tile within range:
#   +4 per enemy within root radius 2
#   +3 per enemy within active searing totem radius (combo!)
#   +2 per melee enemy (root is stronger vs melee)
# Target highest scoring tile

# Soul Anchor targeting:
# Choose ally with: lowest current HP percentage
# Prefer tanks (Crusader, Revenant) that are actively taking damage
# Don't anchor if no ally below 40% HP (save it for emergencies)
```

---

## New Effect Types

### Summary

| Effect Type | Complexity | Based On | Handler |
|-------------|-----------|----------|---------|
| `place_totem` | High | New entity system (similar to door/chest objects) | `resolve_place_totem()` |
| `soul_anchor` | Medium | `cheat_death` pattern (Revenant) but ally-targeted | `resolve_soul_anchor()` |
| `aoe_root` | Medium | `aoe_damage_slow` pattern but root CC instead | `resolve_aoe_root()` |

Note: The `place_totem` handler is shared by both Healing Totem and Searing Totem — the `totem_type` field in the skill effect config determines which variant to create.

### Effect Type Details

#### `place_totem` — Create Destructible Totem Entity (Healing Totem / Searing Totem)

```python
def resolve_place_totem(player, action, skill_def, players, match_state, ...):
    """Place a totem on an empty tile. Creates a persistent entity."""
    # Step 1: Validate target tile is empty (no unit, no obstacle)
    # Step 2: Check LOS to target tile
    # Step 3: Determine totem_type from skill effect ("healing" or "searing")
    # Step 4: Remove any existing totem of THIS TYPE from this Shaman (max 1 per type)
    #         (A Shaman CAN have 1 healing + 1 searing simultaneously)
    # Step 5: Create totem entity:
    #         {
    #           "id": generate_id(),
    #           "type": totem_type,  # "healing_totem" or "searing_totem"
    #           "owner_id": player.id,
    #           "x": target_x, "y": target_y,
    #           "hp": 20, "max_hp": 20,
    #           "heal_per_turn": 8 (healing) or 0 (searing),
    #           "damage_per_turn": 0 (healing) or 6 (searing),
    #           "effect_radius": 2,
    #           "duration_remaining": 4,
    #           "team": player.team
    #         }
    # Step 6: Add totem to match_state.totems list
    # Step 7: Set cooldown, log message
    # Return ActionResult with totem_placed=True
```

**Totem tick logic (runs each turn in buffs_phase or tick_loop):**
```python
for totem in match_state.totems:
    if totem["type"] == "healing_totem":
        # Heal allies in radius
        for ally in alive_allies_in_radius(totem, totem["effect_radius"]):
            heal_amount = min(totem["heal_per_turn"], ally.max_hp - ally.hp)
            ally.hp += heal_amount
    elif totem["type"] == "searing_totem":
        # Damage enemies in radius
        for enemy in alive_enemies_in_radius(totem, totem["effect_radius"]):
            enemy.hp = max(0, enemy.hp - totem["damage_per_turn"])
            # Note: searing totem damage ignores armor (spirit fire)
    # Tick down duration
    totem["duration_remaining"] -= 1
    # Remove if expired or destroyed
    if totem["duration_remaining"] <= 0 or totem["hp"] <= 0:
        match_state.totems.remove(totem)
```

**Totem targeting (enemies can attack totems):**
Totems occupy a tile and can be targeted by enemy units. When attacked, totems take damage (no armor). This requires adding totems to the "valid targets" list in the combat phase. ~20 lines in `combat_phase.py`.

#### `soul_anchor` — Ally Death Prevention (Soul Anchor)

```python
def resolve_soul_anchor(player, action, skill_def, players, ...):
    """Apply a cheat-death buff to an ally."""
    # Step 1: Validate target is an alive ally (or self) within range
    # Step 2: Remove any existing soul_anchor buffs from this Shaman's targets (max 1)
    #         target.active_buffs = [b for b in target.active_buffs if b.get("stat") != "soul_anchor"]
    # Step 3: Apply soul_anchor buff to target's active_buffs:
    #         {"buff_id": "soul_anchor", "type": "soul_anchor", "stat": "soul_anchor",
    #          "caster_id": player.player_id, "turns_remaining": 4, "magnitude": 0}
    # Step 4: Set cooldown, log message
    # Return ActionResult with anchor_applied=True
```

**Death pipeline integration (death prevention — same location as cheat_death in deaths_phase.py):**
```python
# In deaths_phase.py _resolve_deaths(), alongside the cheat_death pre-pass:
if dead_unit.hp <= 0:
    soul_anchor = next(
        (b for b in dead_unit.active_buffs if b.get("stat") == "soul_anchor"), None
    )
    if soul_anchor:
        dead_unit.hp = 1
        dead_unit.is_alive = True
        dead_unit.active_buffs = [
            b for b in dead_unit.active_buffs if b.get("stat") != "soul_anchor"
        ]
        # Log: "Soul Anchor saves {target} from death! (1 HP)"
        # Don't register death — add to revived_ids
```

#### `aoe_root` — Ground-Targeted AoE Root (Earthgrasp)

```python
def resolve_aoe_root(player, action, skill_def, players, obstacles, ...):
    """Root all enemies within radius of target tile."""
    # Step 1: Validate target tile is within range
    # Step 2: Check LOS to target tile
    # Step 3: Find all enemies within radius of target tile
    # Step 4: Apply rooted debuff to each enemy's active_buffs:
    #         {"buff_id": "earthgrasp", "type": "aoe_root", "stat": "rooted",
    #          "turns_remaining": 2, "magnitude": 0}
    # Step 5: Set cooldown, log message
    # Return ActionResult with enemies_rooted=count
```

**Movement pipeline integration (root enforcement):**
```python
# In skills.py, add helper (following is_stunned/is_slowed pattern):
def is_rooted(player: PlayerState) -> bool:
    return any(b.get("stat") == "rooted" for b in player.active_buffs)

# In movement_phase.py, import and check (alongside is_stunned/is_slowed):
from app.core.skills import is_stunned, is_slowed, is_rooted

# Before processing a unit's movement (after the stunned/slowed checks):
if is_rooted(player):
    # Skip movement entirely — unit stays in place
    # Unit can still attack and use skills this turn
    results.append(ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.MOVE, success=False,
        message=f"{player.username} is rooted and cannot move!",
    ))
    continue
```

### Buff/Debuff System Integration

**New stat: `soul_anchor`**

Locations that must be updated:
1. `server/app/core/turn_phases/deaths_phase.py` — in `_resolve_deaths()`, alongside the `cheat_death` pre-pass, check `dead_unit.active_buffs` for `soul_anchor` buff, set HP to 1, set `is_alive = True`, and consume buff
2. `server/app/core/turn_phases/buffs_phase.py` — tick down soul_anchor `turns_remaining`; if expired, remove from `active_buffs`

**New stat: `rooted`**

Locations that must be updated:
1. `server/app/core/skills.py` — add `is_rooted()` helper function (following `is_stunned()` / `is_slowed()` pattern at lines 265-275)
2. `server/app/core/turn_phases/movement_phase.py` — import `is_rooted` from `skills.py` and add check alongside existing `is_stunned` / `is_slowed` checks; if rooted, skip movement (unit stays in place)
3. `server/app/core/turn_phases/buffs_phase.py` — tick down rooted `turns_remaining` in `active_buffs`; if expired, remove
4. `server/app/core/ai_behavior.py` — AI should not attempt movement when rooted (early exit)

**New entity type: `totem` (shared by healing_totem and searing_totem)**

Locations that must be updated:
1. `server/app/models/match.py` — add `totems: list` field to MatchState
2. `server/app/core/turn_phases/buffs_phase.py` — process totem ticks (heal allies / damage enemies, tick down, remove expired/destroyed)
3. `server/app/core/turn_phases/combat_phase.py` — allow enemies to target and damage totems
4. `server/app/services/tick_loop.py` — include totem data in state broadcast to client
5. `client/src/canvas/dungeonRenderer.js` or `overlayRenderer.js` — render totem sprites on map

No new buff stats needed for existing handlers — all 4 skills use new effect types.

---

## Implementation Phases

### Phase 26A — Config & Data Model (Foundation)

**Goal:** Add Shaman to classes and skills configs. Add `totems` field to match state. Wire up the data layer. Zero logic changes.

**Files Modified:**
| File | Change |
|------|--------|
| `server/configs/classes_config.json` | Add `shaman` class definition |
| `server/configs/skills_config.json` | Add 4 skills + `class_skills.shaman` mapping |
| `server/app/models/match.py` | Add `totems: list = []` to MatchState |

**Config: `classes_config.json`**
```json
"shaman": {
  "class_id": "shaman",
  "name": "Shaman",
  "role": "Totemic Healer",
  "description": "Dark ritualist who heals and supports through persistent bone totems. Rewards party positioning — allies near totems thrive, scattered allies suffer.",
  "base_hp": 95,
  "base_melee_damage": 8,
  "base_ranged_damage": 10,
  "base_armor": 3,
  "base_vision_range": 7,
  "ranged_range": 4,
  "allowed_weapon_categories": ["caster", "hybrid"],
  "color": "#8B6914",
  "shape": "totem"
}
```

**Config: `skills_config.json`** — 4 new skills:
```json
"healing_totem": {
  "skill_id": "healing_totem",
  "name": "Healing Totem",
  "description": "Place a totem that heals allies within 2 tiles for 8 HP/turn for 4 turns. Totem has 20 HP. Max 1 active.",
  "flavor": "Bone and spirit fused — the dead mend the living.",
  "icon": "🪵",
  "targeting": "ground_aoe",
  "range": 4,
  "cooldown_turns": 6,
  "mana_cost": 0,
  "effects": [
    { "type": "place_totem", "totem_type": "healing", "totem_hp": 20, "heal_per_turn": 8, "effect_radius": 2, "duration_turns": 4 }
  ],
  "allowed_classes": ["shaman"],
  "requires_line_of_sight": true
},
"searing_totem": {
  "skill_id": "searing_totem",
  "name": "Searing Totem",
  "description": "Place a totem that deals 6 damage/turn to enemies within 2 tiles for 4 turns. Totem has 20 HP. Max 1 active.",
  "flavor": "A totem of blackened bone that crackles with ancestral fury — the spirits punish those who trespass.",
  "icon": "🔥",
  "targeting": "ground_aoe",
  "range": 4,
  "cooldown_turns": 6,
  "mana_cost": 0,
  "effects": [
    { "type": "place_totem", "totem_type": "searing", "totem_hp": 20, "damage_per_turn": 6, "effect_radius": 2, "duration_turns": 4 }
  ],
  "allowed_classes": ["shaman"],
  "requires_line_of_sight": true
},
"soul_anchor": {
  "skill_id": "soul_anchor",
  "name": "Soul Anchor",
  "description": "Mark an ally — if they would die within 4 turns, survive at 1 HP instead. One-time trigger.",
  "flavor": "The spirits refuse to release this soul — not yet.",
  "icon": "⚓",
  "targeting": "ally_or_self",
  "range": 4,
  "cooldown_turns": 10,
  "mana_cost": 0,
  "effects": [
    { "type": "soul_anchor", "survive_hp": 1, "duration_turns": 4 }
  ],
  "allowed_classes": ["shaman"],
  "requires_line_of_sight": false
},
"earthgrasp": {
  "skill_id": "earthgrasp",
  "name": "Earthgrasp",
  "description": "Root all enemies within 2 tiles of target for 2 turns. Cannot move, can still attack.",
  "flavor": "Spectral hands claw up from the earth — the dead hold the living in place.",
  "icon": "🩸",
  "targeting": "ground_aoe",
  "range": 4,
  "cooldown_turns": 7,
  "mana_cost": 0,
  "effects": [
    { "type": "aoe_root", "radius": 2, "root_duration": 2 }
  ],
  "allowed_classes": ["shaman"],
  "requires_line_of_sight": true
}
```

**`class_skills` mapping:**
```json
"shaman": ["auto_attack_ranged", "healing_totem", "searing_totem", "soul_anchor", "earthgrasp"]
```

**Tests (Phase 26A):**
- Shaman class loads from config with correct stats (HP 95, melee 8, ranged 10, armor 3, vision 7, range 4)
- Shaman class has correct color (#8B6914) and shape (totem)
- All 4 skills load from config with correct properties
- Healing Totem and Searing Totem both have `place_totem` effect type with correct totem_type
- Soul Anchor has `soul_anchor` effect type with correct survive_hp and duration
- Earthgrasp has `aoe_root` effect type with correct radius and root_duration
- `class_skills["shaman"]` maps to correct 5 skills (auto_attack, healing_totem, searing_totem, soul_anchor, earthgrasp)
- `can_use_skill()` validates Shaman skills for shaman class
- `can_use_skill()` rejects Shaman skills for non-shaman classes
- Shaman allowed_weapon_categories is ["caster", "hybrid"]
- MatchState.totems field exists and defaults to empty list
- Existing class tests still pass (regression check)

**Estimated tests:** 12–14

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass before proceeding.

---

### Phase 26B — Effect Handlers (Core Mechanics)

**Goal:** Implement 3 new effect type handlers (`place_totem`, `soul_anchor`, `aoe_root`). The `place_totem` handler is shared by both Healing Totem and Searing Totem, dispatching based on `totem_type`.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/skills.py` | Add `resolve_place_totem()`, `resolve_soul_anchor()`, `resolve_aoe_root()` handlers + dispatcher branches |
| `server/app/core/turn_phases/skills_phase.py` | Update dispatcher if needed |

#### Handler 1: `resolve_place_totem()` (~80 lines)

```
Input:  player, action, skill_def, players, match_state, obstacles
Logic:  1. Validate target tile is empty (no unit, no wall, no chest/door)
        2. Check LOS to target tile
        3. Read totem_type from skill effect ("healing" or "searing")
        4. Remove any existing totem of THIS TYPE from this Shaman (max 1 per type)
           (Shaman CAN have 1 healing + 1 searing simultaneously)
        5. Create totem entity dict:
           - healing: {heal_per_turn: 8, damage_per_turn: 0}
           - searing: {heal_per_turn: 0, damage_per_turn: 6}
        6. Add to match_state.totems
        7. Set cooldown, log message
Output: ActionResult with totem_placed=True
```

#### Handler 2: `resolve_soul_anchor()` (~30 lines)

```
Input:  player, action, skill_def, players
Logic:  1. Validate target is alive ally (or self) within range
        2. Remove any existing soul_anchor buff from this Shaman's previous targets (max 1)
        3. Apply soul_anchor buff to target's active_buffs:
           {buff_id: "soul_anchor", type: "soul_anchor", stat: "soul_anchor",
            caster_id: player.player_id, turns_remaining: 4, magnitude: 0}
        4. Set cooldown, log message
Output: ActionResult with anchor_applied=True
```

#### Handler 3: `resolve_aoe_root()` (~25 lines)

```
Input:  player, action, skill_def, players, obstacles
Logic:  1. Validate target tile within range
        2. Check LOS to target tile
        3. Find all enemies within radius (2) of target tile
        4. Apply rooted debuff to each enemy's active_buffs:
           {buff_id: "earthgrasp", type: "aoe_root", stat: "rooted",
            turns_remaining: 2, magnitude: 0}
        5. Set cooldown, log message
Output: ActionResult with enemies_rooted=count
```

#### Dispatcher Update

**IMPORTANT:** `resolve_skill_action()` currently does not accept `match_state` in its signature. The `place_totem` handler needs `match_state` to create/manage totem entities. This requires:
1. Extending `resolve_skill_action()` signature to add `match_state: MatchState | None = None`
2. Updating the caller in `skills_phase.py` `_resolve_skills()` (line ~84) to pass `match_state`
3. Only the `place_totem` branch uses it — all other branches are unaffected

```python
# Updated resolve_skill_action signature:
def resolve_skill_action(
    player, action, skill_def, players, obstacles,
    grid_width=20, grid_height=20,
    match_state=None,  # Phase 26: Required for place_totem (totem entity access)
) -> ActionResult:

# New dispatcher branches:
elif effect_type == "place_totem":
    return resolve_place_totem(player, action, skill_def, players, obstacles, match_state)
elif effect_type == "soul_anchor":
    return resolve_soul_anchor(player, action, skill_def, players, target_id=tid)
elif effect_type == "aoe_root":
    return resolve_aoe_root(player, action, skill_def, players, obstacles)
```

**Tests (Phase 26B):**

*Healing Totem (place_totem — healing variant):*
- Healing Totem creates healing totem entity at target tile
- Healing Totem fails on occupied tile (unit present)
- Healing Totem fails on wall tile
- Healing Totem requires LOS
- Placing second healing totem removes the first (max 1 per type)
- Healing totem has correct HP (20), effect radius (2), heal per turn (8), duration (4)
- Healing Totem sets cooldown to 6

*Searing Totem (place_totem — searing variant):*
- Searing Totem creates searing totem entity at target tile
- Searing Totem fails on occupied tile
- Searing Totem fails on wall tile
- Searing Totem requires LOS
- Placing second searing totem removes the first (max 1 per type)
- Searing totem has correct HP (20), effect radius (2), damage per turn (6), duration (4)
- Searing Totem sets cooldown to 6
- Shaman can have 1 healing + 1 searing totem simultaneously

*Soul Anchor:*
- Soul Anchor applies soul_anchor buff to target ally
- Soul Anchor can target self
- Soul Anchor fails on enemy targets
- Soul Anchor fails on out-of-range targets
- Second Soul Anchor replaces the first (max 1 active)
- Soul Anchor buff stores correct caster_id and duration (4 turns)
- Soul Anchor sets cooldown to 10

*Earthgrasp:*
- Earthgrasp applies rooted debuff to all enemies within radius 2 of target
- Earthgrasp does not root allies
- Earthgrasp requires LOS to target tile
- Earthgrasp fails on out-of-range target
- Rooted debuff has correct duration (2 turns)
- Earthgrasp sets cooldown to 7
- Multiple enemies rooted in single cast

**Estimated tests:** 28–32

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass.

---

### Phase 26C — System Integration (Totem Ticks + Soul Anchor + Root)

**Goal:** Wire totem per-turn effects (healing + damage) into the tick loop, make totems targetable by enemies, wire Soul Anchor death prevention into the combat pipeline, and wire root CC into the movement phase.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/turn_phases/buffs_phase.py` | Add totem tick processing (heal allies / damage enemies, tick down, remove expired/destroyed) |
| `server/app/core/turn_phases/deaths_phase.py` | Add soul_anchor death prevention check (alongside cheat_death pre-pass) |
| `server/app/core/skills.py` | Add `is_rooted()` helper function (following `is_stunned()` / `is_slowed()` pattern) |
| `server/app/core/turn_phases/movement_phase.py` | Import `is_rooted` and add rooted check — skip movement for rooted units |
| `server/app/core/turn_phases/combat_phase.py` | Allow enemies to target and damage totems |
| `server/app/services/tick_loop.py` | Include totem data in state broadcast |
| `server/app/core/turn_phases/skills_phase.py` | Update `resolve_skill_action()` call to pass `match_state` |

#### Totem Tick Integration (buffs_phase.py)

```python
# Process totems each turn
for totem in list(match_state.totems):
    if totem["hp"] <= 0 or totem["duration_remaining"] <= 0:
        match_state.totems.remove(totem)
        continue
    if totem["type"] == "healing_totem":
        # Heal allies in radius
        for player in alive_allies(totem["team"], players):
            dist = chebyshev(player.x, player.y, totem["x"], totem["y"])
            if dist <= totem["effect_radius"]:
                heal = min(totem["heal_per_turn"], player.max_hp - player.hp)
                player.hp += heal
                # Log: "Healing Totem restores {heal} HP to {player}"
    elif totem["type"] == "searing_totem":
        # Damage enemies in radius
        for enemy in alive_enemies(totem["team"], players):
            dist = chebyshev(enemy.x, enemy.y, totem["x"], totem["y"])
            if dist <= totem["effect_radius"]:
                enemy.hp = max(0, enemy.hp - totem["damage_per_turn"])
                # Log: "Searing Totem deals {dmg} to {enemy}"
    totem["duration_remaining"] -= 1
```

#### Soul Anchor Integration (deaths_phase.py — alongside cheat_death pre-pass)

```python
# In _resolve_deaths(), add soul_anchor check alongside the cheat_death pre-pass:
for death_pid in deaths:
    dead_unit = players.get(death_pid)
    if not dead_unit:
        continue
    # Existing: cheat_death check ...
    # NEW: soul_anchor check
    soul_anchor = next(
        (b for b in dead_unit.active_buffs if b.get("stat") == "soul_anchor"), None
    )
    if soul_anchor:
        dead_unit.hp = 1
        dead_unit.is_alive = True
        dead_unit.active_buffs = [
            b for b in dead_unit.active_buffs if b.get("stat") != "soul_anchor"
        ]
        revived_ids.append(death_pid)
        # Log: "Soul Anchor saves {dead_unit.username} from death! (1 HP)"
```

#### Root Enforcement (skills.py + movement_phase.py)

```python
# In skills.py, add helper alongside is_stunned() / is_slowed():
def is_rooted(player: PlayerState) -> bool:
    """Check if a player is rooted (cannot move, can still attack/skill)."""
    return any(b.get("stat") == "rooted" for b in player.active_buffs)

# In movement_phase.py, add import and check:
from app.core.skills import is_stunned, is_slowed, is_rooted

# In _resolve_movement(), after is_stunned/is_slowed checks (~line 88):
if is_rooted(player):
    results.append(ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.MOVE, success=False,
        message=f"{player.username} is rooted and cannot move!",
    ))
    continue
```

#### Totem Targeting (combat_phase.py)

```python
# When an AI enemy selects a target, totems are valid targets
# Totem priority: lower than player targets, but:
#   - Searing totems are high priority (they're dealing damage)
#   - Healing totems are medium priority (they're sustaining the party)
# Totems have no armor — damage is applied directly to totem.hp
```

**Tests (Phase 26C):**

*Totem ticks (healing):*
- Healing Totem heals all allies within radius each turn
- Healing Totem does not heal enemies
- Healing Totem does not overheal (respects max_hp)
- Healing Totem expires after duration (4 turns)
- Destroyed totem (HP 0) is removed immediately
- Totem healing stacks with other heals (Confessor, etc.)
- Multiple allies healed in same turn

*Totem ticks (searing):*
- Searing Totem damages all enemies within radius each turn
- Searing Totem does not damage allies
- Searing Totem ignores armor (spirit fire)
- Searing Totem expires after duration (4 turns)
- Destroyed searing totem stops dealing damage
- Searing Totem can kill enemies (reduce to 0 HP)
- Multiple enemies damaged in same turn

*Both totems coexisting:*
- Healing and Searing totems tick independently in same turn
- Both totems can be active simultaneously from same Shaman
- Replacing one totem type doesn't affect the other

*Soul Anchor death prevention:*
- Anchored ally survives killing blow at 1 HP
- Soul Anchor is consumed after triggering (one-time use)
- Soul Anchor expires after 4 turns if not triggered
- Soul Anchor works against melee damage
- Soul Anchor works against ranged damage
- Soul Anchor works against skill/DoT damage
- Only 1 Soul Anchor active per Shaman

*Root CC (movement phase):*
- Rooted enemy cannot move (stays in place)
- Rooted enemy CAN still attack adjacent targets
- Rooted enemy CAN still use skills
- Root expires after 2 turns
- Root does not affect allies
- Multiple enemies can be rooted simultaneously

*Totem targeting:*
- Enemy can attack and damage a totem
- Totem takes full damage (no armor)
- Totem dies when HP reaches 0
- Dead totem stops healing/dealing damage

**Estimated tests:** 28–34

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass.

---

### Phase 26D — AI Behavior (totemic_support role)

**Goal:** Implement AI decision-making so Shaman heroes and AI-controlled Shamans place totems strategically and support the party.

**Files Modified:**
| File | Change |
|------|--------|
| `server/app/core/ai_skills.py` | Add `"shaman": "totemic_support"` to `_CLASS_ROLE_MAP` |
| `server/app/core/ai_skills.py` | Add `_totemic_support_skill_logic()` function |
| `server/app/core/ai_skills.py` | Add `"totemic_support"` branch to dispatcher |

#### AI Decision Logic

```python
def _totemic_support_skill_logic(ai, enemies, all_units, grid_w, grid_h, obstacles):
    """Shaman AI: dual totem placement, earthgrasp combos, soul anchor on endangered allies."""

    # 1. Healing Totem → if 2+ allies below 70% HP within 4 tiles and no active healing totem
    #    Pick placement tile: maximize injured allies in heal radius, avoid enemies
    # 2. Searing Totem → if 2+ enemies clustered and no active searing totem
    #    Pick placement tile: maximize enemies in damage radius
    #    Bonus: prefer tiles where enemies are rooted (Earthgrasp combo!)
    # 3. Earthgrasp → if 2+ enemies within range, especially near active searing totem
    #    Target tile that roots most enemies within searing totem radius
    # 4. Soul Anchor → if a frontline ally below 30% HP and no active anchor
    #    Prefer tanks; don't anchor if no ally in danger
    # 5. Fallback — auto-attack nearest enemy in range
    return None
```

**Tests (Phase 26D):**
- Shaman AI places Healing Totem when 2+ allies injured
- Shaman AI does not place totem when no allies are injured
- Shaman AI places healing totem near the largest injured ally cluster
- Shaman AI avoids placing totem adjacent to enemies
- Shaman AI places Searing Totem when 2+ enemies clustered
- Shaman AI prefers Searing Totem placement near rooted enemies (combo awareness)
- Shaman AI uses Earthgrasp when enemies are near active Searing Totem
- Shaman AI uses Earthgrasp to root melee enemies approaching the party
- Shaman AI uses Soul Anchor on low-HP frontline ally (below 30%)
- Shaman AI does not waste Soul Anchor when no ally is endangered
- Shaman AI falls back to auto-attack when all skills on cooldown
- Shaman AI stays behind frontline (support positioning)
- Shaman AI retreats when enemies are adjacent and no allies nearby

**Estimated tests:** 13–15

**Post-phase gate:** Run `pytest server/tests/` — ALL tests must pass.

---

### Phase 26E — Frontend Integration (Rendering + UI)

**Goal:** Add Shaman to the client — totem shape rendering, class selection, colors, icons, totem map rendering, inventory portrait.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/canvas/renderConstants.js` | Add shaman to `CLASS_COLORS`, `CLASS_SHAPES`, `CLASS_NAMES` |
| `client/src/canvas/unitRenderer.js` | Add `totem` shape rendering case |
| `client/src/canvas/overlayRenderer.js` | Add totem entity rendering on map (heal radius indicator) |
| `client/src/components/WaitingRoom/WaitingRoom.jsx` | Add totem icon to shape map |
| `client/src/components/Inventory/Inventory.jsx` | Add totem SVG path to `CLASS_SHAPE_PATHS` |
| `client/src/components/Inventory/Inventory.jsx` | Add skill buff names to `formatBuffName` / `formatBuffEffect` |

#### renderConstants.js additions

```javascript
// CLASS_COLORS
shaman: '#8B6914',

// CLASS_SHAPES
shaman: 'totem',

// CLASS_NAMES
shaman: 'Shaman',
```

#### unitRenderer.js — Totem Shape (for the Shaman unit itself)

```javascript
case 'totem': {
  // A totem pole — stacked rectangular segments with a wider base
  const hw = half * 0.4;   // narrow width
  const hh = half * 0.9;   // tall
  ctx.beginPath();
  // Top segment (head)
  ctx.moveTo(cx - hw * 0.8, cy - hh);
  ctx.lineTo(cx + hw * 0.8, cy - hh);
  ctx.lineTo(cx + hw, cy - hh * 0.3);
  // Middle segment (body)
  ctx.lineTo(cx + hw * 1.2, cy - hh * 0.3);
  ctx.lineTo(cx + hw * 1.2, cy + hh * 0.3);
  // Bottom segment (base — wider)
  ctx.lineTo(cx + hw * 1.4, cy + hh * 0.3);
  ctx.lineTo(cx + hw * 1.4, cy + hh);
  ctx.lineTo(cx - hw * 1.4, cy + hh);
  ctx.lineTo(cx - hw * 1.4, cy + hh * 0.3);
  ctx.lineTo(cx - hw * 1.2, cy + hh * 0.3);
  ctx.lineTo(cx - hw * 1.2, cy - hh * 0.3);
  ctx.lineTo(cx - hw, cy - hh * 0.3);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  break;
}
```

#### overlayRenderer.js — Totem Entity Rendering

```javascript
// Render totems on the map (from match_state.totems)
for (const totem of totems) {
  // Draw totem body (small icon on tile)
  // Healing totem: green/amber glow + heal radius indicator (soft green circle)
  // Searing totem: red/orange glow + damage radius indicator (soft red circle)
  // Draw HP bar above totem
  // Draw remaining duration indicator
}

// Render root effect on rooted enemies
for (const unit of units) {
  if (unit.active_buffs?.some(b => b.stat === 'rooted')) {
    // Draw spectral hands/chains around unit's feet
    // Subtle brown/grey ground effect
  }
}
```

---

## Changelog

### Healing Totem Tank Priority & Shaman Positioning Fix (March 2026)

**Problem:** Shaman AI hangs far behind the frontline and ignores the tank. The Crusader pushes forward to engage enemies, but the Shaman retreats backward due to kiting, then places Healing Totems near backline allies instead of covering the tank who is absorbing all the damage. The gap between the Shaman and tank grows over multiple turns until the tank is entirely outside totem placement range.

**Root causes identified:**
1. **No tank awareness in Healing Totem scoring** — `_find_best_totem_tile()` scored injured allies at +3 and healthy allies at +1 regardless of role. A hurt Ranger at the back scored identically to a hurt Crusader at the front, so the totem often landed near the backline cluster rather than the tank.
2. **Generic support movement chased "most injured" ally** — `_support_move_preference()` moved the Shaman toward whichever ally had the lowest HP%, typically a backliner who took a stray hit, instead of advancing toward the frontline tank who will continuously need healing.
3. **Kiting threshold too aggressive** — The Shaman was classified as `is_ranged_role` with a kite threshold of 2 tiles. Any enemy within 2 tiles triggered a retreat, constantly pushing the Shaman away from the frontline and outside totem placement range (4 tiles).

**Changes:**
| File | Change |
|------|--------|
| `server/app/core/ai_skills.py` | Added `_HEALING_TOTEM_TANK_CLASSES = {"crusader", "revenant", "blood_knight"}` constant |
| `server/app/core/ai_skills.py` | Healing totem tile scoring: injured tank +5 (was +3), healthy tank +2 (was +1), non-tank allies unchanged (+3/+1) |
| `server/app/core/ai_skills.py` | Added `_totemic_support_move_preference()` — tank-priority movement for Shaman. Priority: (1) move toward own healing totem if active, (2) move toward most injured tank, (3) move toward nearest tank, (4) fallback to most injured ally, (5) nearest ally |
| `server/app/core/ai_stances.py` | Follow stance: Shaman uses `_totemic_support_move_preference()` instead of generic `_support_move_preference()` |
| `server/app/core/ai_stances.py` | Follow stance kite threshold: `totemic_support` changed from 2 → 1 (only kites when adjacent) |
| `server/app/core/ai_stances.py` | Aggressive stance kite threshold: `totemic_support` changed from 2 → 1 |
| `server/app/core/ai_behavior.py` | Enemy AI kite threshold: `totemic_support` changed from 2 → 1 |

**Design rationale:**
- **Tank-weighted scoring (+5/+2 vs +3/+1):** Ensures the Healing Totem strongly prefers tiles covering the tank. With a party of 1 tank + 2 backliners all injured, a tile covering the tank scores +5 vs the backline centroid scoring +6 (2×3) — close enough that proximity and enemy-penalty tiebreakers often favor the tank tile. Previously the backline always won at +6 vs +3.
- **Tank-priority movement:** The Shaman needs to stay within totem placement range (4 tiles) of the frontline. By moving toward the tank instead of the most injured random ally, the Shaman naturally advances with the party. When a healing totem IS active, the Shaman drifts toward it instead (staying in its own heal zone).
- **Kite threshold 1:** The Shaman should only retreat when an enemy is literally adjacent (melee range). At distance 2, the Shaman has time to place a totem or auto-attack. The old threshold of 2 caused the Shaman to flee from enemies that the tank was actively engaging, creating the ever-growing gap. The Shaman still retreats when HP drops below 35% via the retreat threshold system.
- **`_HEALING_TOTEM_TANK_CLASSES` excludes Hexblade:** Hexblade is a hybrid DPS that can self-sustain, not a dedicated tank. The Shaman should prioritize true tanks (Crusader, Revenant, Blood Knight) who rely on external healing.

**Tests:** 3775 passed (0 failed)

### AI Totem Usage Balance Pass (March 2026)

**Problem:** Shaman AI was extremely conservative with Searing Totem and Earthgrasp. Healing Totem was used regularly but the other two offensive/CC skills were almost never cast.

**Root causes identified:**
1. `_SEARING_TOTEM_MIN_ENEMIES = 2` — required 2+ enemies in range to place Searing Totem, so it never fired in single-enemy fights
2. `_EARTHGRASP_MIN_ENEMIES = 2` — required 2+ un-rooted enemies for a minimum score of 8, so it never fired against a single target
3. Healing Totem monopolized the priority chain (fires at 1 injured ally, which is almost always true in combat), leaving Searing Totem and Earthgrasp only a chance during the 6-turn cooldown window — where they then failed due to the 2-enemy minimums

**Changes:**
| File | Change |
|------|--------|
| `server/app/core/ai_skills.py` | `_SEARING_TOTEM_MIN_ENEMIES`: 2 → 1 |
| `server/app/core/ai_skills.py` | `_EARTHGRASP_MIN_ENEMIES`: 2 → 1 |
| `server/app/core/ai_skills.py` | Earthgrasp `min_score` threshold: 8 → 4 (1 enemy × 4 pts), removed separate searing-combo override |
| `server/tests/test_phase26d_shaman_ai.py` | Updated `test_places_searing_totem_single_enemy` — now asserts searing totem fires with 1 enemy |
| `server/tests/test_phase26d_shaman_ai.py` | Added `test_uses_earthgrasp_single_enemy` — asserts earthgrasp fires on 1 un-rooted enemy |
| `server/tests/test_phase26d_shaman_ai.py` | Updated docstrings and comments to reflect new thresholds |

**Design rationale:** The tile-scoring system already naturally prefers placements that catch multiple enemies (3 pts per enemy in searing radius, 4 pts per un-rooted enemy for earthgrasp + combo/melee bonuses). Lowering the *gate* from 2→1 lets the skills fire in single-target fights while the scoring ensures optimal multi-target placement when available. Already-rooted enemies still score only 1 pt each, so re-rooting 2 rooted enemies (2 pts) stays below the threshold of 4 — preventing wasteful casts. Totems are still limited to 1-per-type with 6-turn cooldowns, preventing spam.

**Tests:** 35 passed (0 failed)

#### WaitingRoom.jsx — Shape icon

```
cls.shape === 'totem' ? '🪵' : ...
```

#### Inventory.jsx — SVG portrait path

```javascript
totem: <path d="M 40 10 L 60 10 L 65 35 L 70 35 L 70 65 L 75 65 L 75 90 L 25 90 L 25 65 L 30 65 L 30 35 L 35 35 Z" />,
```

#### Inventory.jsx — Buff name formatting

```javascript
// formatBuffName (keyed by buff_id):
healing_totem: 'Healing Totem',
searing_totem: 'Searing Totem',
soul_anchor: 'Soul Anchor',
earthgrasp: 'Earthgrasp',

// formatBuffEffect (keyed by buff.stat / buff.type):
if (buff.stat === 'soul_anchor') return `Survives killing blow at 1 HP`;
if (buff.stat === 'rooted') return `Cannot move — can still attack`;
```

**Tests (Phase 26E):** Visual verification — manual checklist:
- [ ] Shaman appears in class selection screen
- [ ] Totem shape renders correctly on canvas
- [ ] Color (#8B6914 dark goldenrod) displays correctly and is distinguishable from Bard/Confessor
- [ ] Shaman name shows in nameplate
- [ ] Placed Healing Totem renders on map with green heal radius indicator
- [ ] Placed Searing Totem renders on map with red damage radius indicator
- [ ] Totem HP bars visible for both totem types
- [ ] Rooted enemies have visible root effect on their tile
- [ ] Soul Anchor buff icon displays in ally's buff bar
- [ ] Inventory portrait shows totem shape
- [ ] Skill icons appear in bottom bar with correct names

---

### Phase 26F — Particle Effects & Audio (Polish)

**Goal:** Add visual and audio feedback for Shaman skills.

**Files Modified:**
| File | Change |
|------|--------|
| `client/public/particle-presets/skills.json` | Add shaman skill effects |
| `client/public/particle-presets/buffs.json` | Add dual totem pulses + root effect + soul anchor buff |
| `client/public/audio-effects.json` | Add shaman audio triggers |
| `client/src/audio/soundMap.js` | Add shaman sound mappings |

#### Particle Effects

| Skill | Particle Effect | Description |
|-------|----------------|-------------|
| Healing Totem (place) | `shaman-totem-place` | Ground eruption — bones rising from earth, green spirit glow |
| Healing Totem (pulse) | `shaman-totem-heal-pulse` | Soft green/amber heal waves pulsing outward each turn |
| Searing Totem (place) | `shaman-searing-totem-place` | Ground eruption — bones rising from earth, red/orange fire glow |
| Searing Totem (pulse) | `shaman-searing-totem-pulse` | Angry red/orange damage waves pulsing outward each turn |
| Soul Anchor (cast) | `shaman-soul-anchor` | Ethereal anchor symbol descends onto ally, ghostly chain links |
| Soul Anchor (trigger) | `shaman-soul-anchor-save` | Dramatic burst — spectral hands pulling ally back from death |
| Earthgrasp | `shaman-earthgrasp` | Spectral hands erupt from ground across the AoE, grasping upward |
| Earthgrasp (rooted) | `shaman-earthgrasp-hold` | Persistent ghostly hands circling each rooted enemy's feet |

#### Audio

| Skill | Sound | Category |
|-------|-------|----------|
| Healing Totem | Bone cracking + spirit hum | skills |
| Searing Totem | Bone cracking + fire crackle | skills |
| Soul Anchor | Deep ethereal chord + anchor thud | skills |
| Soul Anchor (trigger) | Dramatic spirit shriek + glass shatter | skills |
| Earthgrasp | Earth rumble + grabbing/scraping | skills |
| Totem heal tick | Soft spirit exhale | buffs |
| Totem searing tick | Low fire sizzle | buffs |

**Tests (Phase 26F):** Manual verification only.
- [ ] Each skill triggers correct particle effect
- [ ] Healing totem heal pulse visible each turn (green)
- [ ] Searing totem damage pulse visible each turn (red)
- [ ] Earthgrasp shows spectral hands across AoE
- [ ] Rooted enemies have persistent root visual
- [ ] Soul Anchor save triggers dramatic visual + audio
- [ ] Audio plays on skill use
- [ ] No console errors from missing assets

---

### Phase 26G — Sprite Integration (Optional)

**Goal:** Add Shaman sprite variants from the character sheet atlas.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/canvas/SpriteLoader.js` | Add shaman sprite variants |

*This phase depends on finding suitable sprites in the existing atlas. If no shaman-appropriate sprites exist, the totem shape fallback works perfectly.*

---

## Implementation Order & Dependencies

```
Phase 26A (Config + Data Model)   ← No dependencies, pure data
    ↓
Phase 26B (Effect Handlers)       ← Depends on 26A (needs skill definitions + totems list)
    ↓
Phase 26C (System Integration)    ← Depends on 26B (needs handlers working + totem entities)
    ↓
Phase 26D (AI Behavior)           ← Depends on 26B (needs handlers working)
    ↓
Phase 26E (Frontend)              ← Depends on 26A — can parallel with 26C/26D
    ↓
Phase 26F (Polish)                ← Depends on 26E (needs rendering working)
    ↓
Phase 26G (Sprites)               ← Optional, last
```

**Parallelizable:** 26C + 26D can run in parallel after 26B. 26E can start after 26A.

**Note:** Phase 26C is more substantial than typical classes due to the Totem entity system. This is new infrastructure that future classes/features can also use (e.g., damage totems, ward totems, enemy totems, trap entities).

---

## Test Summary

| Phase | Test Count | Focus |
|-------|:----------:|-------|
| 26A — Config | 12–14 | Class/skill loading, validation, totems model, soul_anchor/rooted types |
| 26B — Effect Handlers | 28–32 | Totem placement (both types), soul anchor grant/trigger, earthgrasp root |
| 26C — System Integration | 28–34 | Dual totem ticks, searing damage, soul anchor death prevention, root movement blocking, totem targeting |
| 26D — AI Behavior | 13–15 | AI decision logic, dual totem strategy, soul anchor timing, earthgrasp targeting |
| 26E — Frontend | 0 (manual) | Visual verification |
| 26F — Polish | 0 (manual) | Particles, audio |
| **Total** | **81–95** | |

---

## Tuning Levers

| Parameter | Initial Value | Reduce If... | Increase If... |
|-----------|:------------:|--------------|----------------|
| HP | 95 | Shaman survives too long without needing protection | Shaman dies before totems matter |
| Healing Totem HP | 20 | AI ignores totems (too hard to kill) | Totems die in 1 hit (too fragile) |
| Healing Totem Heal/Turn | 8 | Full-party heals rival Confessor burst (96 total is a lot) | Totem healing feels inconsequential |
| Healing Totem Duration | 4 turns | Too much sustained healing per cast | Totem dies before healing enough |
| Healing Totem Radius | 2 tiles | Whole party always in range (no positioning tension) | Too hard to group for healing |
| Searing Totem HP | 20 | AI ignores totems (too hard to kill) | Totems die in 1 hit (too fragile) |
| Searing Totem Dmg/Turn | 6 | Passive damage too high for no-cost upkeep | Damage negligible, not worth casting |
| Searing Totem Duration | 4 turns | Too much total passive damage | Not enough turns to contribute meaningfully |
| Searing Totem Radius | 2 tiles | Too easy to catch all enemies | Enemies avoid it trivially |
| Totem Placement Range | 4 tiles | Shaman never has to move closer to fight | Shaman has to stand in danger to place |
| Soul Anchor Duration | 4 turns | Too easy to pre-cast and forget | Window too tight to time correctly |
| Soul Anchor Cooldown | 10 | Near-permanent uptime, trivializes key deaths | Feels like a once-per-fight niche ability |
| Earthgrasp Root Duration | 2 turns | Enemies locked down too long, frustrating | Root expires before allies can capitalize |
| Earthgrasp Radius | 2 tiles | Too easy to root entire team | Hard to catch more than 1 enemy |
| Earthgrasp Cooldown | 7 | Near-permanent root uptime (root lasts 2, CD 7 = manageable) | Feels unusable, too long between casts |

### Known Balance Risks

1. **Healing Totem + Confessor Stacking:** A Shaman totem healing 8/turn on top of Confessor Heal (30 burst) + Prayer (8/turn HoT) makes the party nearly unkillable in sustained fights. Mitigation: enemies can destroy the totem (20 HP is fragile), and having two totems forces the Shaman to split attention between healing and damage.
2. **Searing Totem + Earthgrasp Combo:** Rooting enemies inside the Searing Totem radius guarantees 2 turns of 6 damage each (12 total) with no escape. This is the intended synergy loop, but if Earthgrasp radius or root duration increase, this becomes oppressive. Monitor total passive damage output.
3. **Soul Anchor + Confessor Heal:** Soul Anchor saves at 1 HP, and a Confessor can immediately burst-heal that ally back to safety. This duo may trivialize death mechanics. Mitigation: Soul Anchor's 10-turn CD means it's a once-per-fight ability, and the Shaman has to predict who will need it.
4. **Dual Totem Management Complexity:** Having two active totems (1 healing + 1 searing) is a lot of board state for AI to manage and for players to track. Both totems are destructible (20 HP each), so enemies have two targets to focus. This is intentional but needs UI clarity.
5. **Root as New CC Type:** Root is a completely new CC type that prevents movement but allows attacks/skills. Edge cases: what if a rooted unit tries to use a movement-based skill? What about knockback effects on rooted units? These need careful testing in Phase 26C.
6. **Shaman Color vs Werewolf:** The Shaman's dark goldenrod (#8B6914) is the same as the werewolf enemy color in `ENEMY_COLORS`. This could cause confusion in visual identification. Consider shifting the werewolf to a slightly different shade during implementation.

---

## Future Enhancements (Post-Phase 26)

- **Ward Totem** — A defensive totem that grants +2 armor to all allies within 2 tiles (persistent aura, not a timed buff). Would be a third totem type, but max 2 active totems means the Shaman must choose which two types to deploy. Creates meaningful totem management decisions.
- **Totem Recall** — A utility skill that teleports all active totems to new tiles near the Shaman. For repositioning mid-fight without recasting and resetting durations.
- **Spirit Walk** — Teleport to an active totem's location. Gives the Shaman an escape tool tied to totem placement. Great synergy with placing a searing totem deep in enemy lines then teleporting to it.
- **Totemic Mastery (Passive)** — After both totems are active for 2+ turns simultaneously, gain a stacking buff (+2% healing, +1 damage per turn). Rewards maintaining both totems.
- **Shaman Enemy Type** — An enemy Shaman that places hostile totems (damage totems, debuff totems). Would use the same totem entity system built in Phase 26C.
- **Earth Shield** — A targeted buff that absorbs the next X damage taken, then shatters and roots all adjacent enemies for 1 turn. Ties into the root theme.

---

## Phase Checklist

- [x] **26A** — Shaman added to `classes_config.json`
- [x] **26A** — 4 skills added to `skills_config.json` (healing_totem, searing_totem, soul_anchor, earthgrasp)
- [x] **26A** — `class_skills.shaman` mapping added
- [x] **26A** — `totems` field added to MatchState (supports dual totems)
- [x] **26A** — Shaman added to `auto_attack_ranged` allowed_classes
- [x] **26A** — 15 Shaman names added to `names_config.json`
- [x] **26A** — Config loading tests pass (70 tests)
- [x] **26A** — Full regression suite passes (3486 tests, 0 failures)
- [x] **26B** — `resolve_place_totem()` handler implemented (supports healing + searing types)
- [x] **26B** — `resolve_soul_anchor()` handler implemented
- [x] **26B** — `resolve_aoe_root()` handler implemented
- [x] **26B** — `resolve_skill_action()` dispatcher updated with 3 new effect types + `match_state` threaded through call chain
- [x] **26B** — All handler tests pass (41 tests, 3527 total, 0 failures)
- [x] **26C** — Healing totem tick healing wired into buffs_phase.py
- [x] **26C** — Searing totem tick damage wired into buffs_phase.py
- [x] **26C** — Soul anchor death prevention wired into deaths_phase.py
- [x] **26C** — Root movement blocking wired into movement_phase.py
- [x] **26C** — Totems targetable by enemies in combat_phase.py
- [x] **26C** — Totem data included in state broadcast (both types)
- [x] **26C** — System integration tests pass (42 tests, 3569 total, 0 failures)
- [x] **26D** — `_totemic_support_skill_logic()` implemented (dual totem + soul anchor + earthgrasp)
- [x] **26D** — `_CLASS_ROLE_MAP` updated with shaman (31 entries)
- [x] **26D** — `_find_best_totem_tile()` helper for smart totem placement
- [x] **26D** — `match_state` threaded through AI call chain (4 files)
- [x] **26D** — AI behavior tests pass (34 tests, 3602 total, 0 new failures)
- [x] **26E** — `renderConstants.js` updated (CLASS_COLORS #8B6914, CLASS_SHAPES totem, CLASS_NAMES Shaman; werewolf shifted to #9B7924)
- [x] **26E** — Totem shape renders in `unitRenderer.js` (stacked segments with carved face divisions)
- [x] **26E** — Healing Totem entity renders on map (green radius, bone totem body, HP bar, duration)
- [x] **26E** — Searing Totem entity renders on map (red radius, dark totem body, HP bar, duration)
- [x] **26E** — Rooted enemies have visual root effect (spectral tendrils + ground ring)
- [x] **26E** — Soul Anchor buff icon displays on anchored ally (ghostly anchor symbol)
- [x] **26E** — WaitingRoom class select shows Shaman (🪵 totem icon)
- [x] **26E** — Inventory portrait & buff names updated (totem SVG, 4 buff names, soul_anchor + rooted effect descriptions)
- [x] **26E** — Totems state wired through GameStateContext → combatReducer → Arena.jsx → renderFrame
- [x] **26E** — 3603 tests passing, 0 failures
- [x] **26F** — Particle effects added (10 skill presets + 5 buff/cc presets = 15 total)
- [x] **26F** — Audio triggers added (5 skill sounds mapped to existing audio files)
- [x] **26F** — particle-effects.json wired: 4 skill mappings (healing_totem, searing_totem, soul_anchor, earthgrasp) + rooted cc_status + soul_anchor buff_status
- [x] **26F** — soundMap.js updated with 5 new SOUND_KEYS (SKILL_HEALING_TOTEM, SKILL_SEARING_TOTEM, SKILL_SOUL_ANCHOR, SKILL_SOUL_ANCHOR_SAVE, SKILL_EARTHGRASP)
- [x] **26F** — All JSON validated, 3603 tests passing, 0 failures
- [ ] **26G** — Sprite variants mapped (or skipped)
- [ ] Balance pass after playtesting

---

## Post-Implementation Cleanup

After all phases complete:

1. **Update `README.md`:**
   - Add Shaman to the class count in the Features table
   - Add phase 26 to the Documentation → Phase Specs list
   - Update the status line at the top
   - Update the test count

2. **Update `docs/Current Phase.md`:**
   - Add phase 26 milestone entry with test counts

3. **Update `docs/Game stats references/game-balance-reference.md`:**
   - Add Shaman stat block

4. **Final test run:**
   - `pytest server/tests/` — ALL tests pass, zero failures
   - Record final test count

---

**Document Version:** 1.0
**Created:** March 2026
**Status:** Not Started
**Prerequisites:** Phase 25 (Revenant Class) Complete
