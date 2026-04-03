# Phase 25R — Revenant Class Rework (Wrath of the Damned)

**Created:** April 2026
**Status:** Phase 25R-F Complete
**Previous:** Phase 25G (Original Revenant Implementation)
**Goal:** Redesign the Revenant's ability kit to give it a distinct identity, meaningful decision-making, and a satisfying gameplay loop. The current kit (Grave Thorns, Grave Chains, Undying Will, Soul Rend) is passive, lacks synergy, and plays as a worse Crusader. The rework transforms the Revenant into a **damage-through-punishment** bruiser tank with abilities that interact with each other and reward skilled play.

---

## Problem Statement

### Why the Current Revenant Feels Bad

1. **No synergy loop.** The four abilities (Grave Thorns, Grave Chains, Undying Will, Soul Rend) are disconnected tools. Compare to Blood Knight where every ability feeds into the others (lifesteal → sustain → stay low → Blood Frenzy → more lifesteal).

2. **Passive gameplay.** Three of four skills are either self-buffs or reactive:
   - Grave Thorns: press it and wait to get hit (12 dmg/hit is modest)
   - Undying Will: press it and hope you die at the right time (8-turn CD means mistiming wastes it entirely)
   - Grave Chains: single-target taunt — Crusader already has AoE taunt
   - Soul Rend: "hit harder once" — no excitement

3. **It's a worse Crusader.** Both are melee tanks with 6 armor and 5 vision. Crusader gets AoE taunt, hard CC (stun), team healing (Holy Ground), and massive armor buff (Bulwark). The Revenant offers less in every dimension.

4. **No active decision-making.** The optimal play is always: Thorns → walk at enemies → Soul Rend when adjacent → Undying Will when low. No adaptation, no reads, no exciting moments.

5. **No "moment."** Every good class has a defining moment: Blood Knight's Blood Frenzy power spike at low HP, Hexblade's Shadow Step → Double Strike burst, Mage's Fireball nuke, Shaman's clutch Soul Anchor save. The Revenant's "moment" (Undying Will revive) is passive — it happens *to* you, not *because* of you.

---

## Design Philosophy

### Core Fantasy

> *A cursed warrior who feeds on pain. Every wound makes it stronger, and death only makes it angrier.*

### Design Pillars (Updated)

1. **Wounded = Dangerous** — The Revenant's abilities scale with missing HP or have conditional upgrades when below health thresholds. Taking damage isn't a problem — it's fuel.
2. **Active Retaliation** — Instead of passively reflecting damage, the Revenant actively punishes enemies for engaging it. Abilities create "lose-lose" scenarios for opponents.
3. **Synergy Loop** — Every ability feeds into the others. Root → Thorns aura → empowered Soul Rend → Undying Fury climax. Clear gameplay arc per fight.
4. **The Fury Moment** — When the Revenant "dies" and enters Fury state, it should feel like an unstoppable horror movie monster. This is the class's signature moment.
5. **Melee Commitment** — Still zero ranged capability. Grasp of the Grave gives the Revenant tools to *keep* enemies in melee.

---

## Base Stats (Unchanged)

| Stat | Value | Notes |
|------|-------|-------|
| HP | 130 | Second highest — needs to absorb hits to power the kit |
| Melee Damage | 16 | High base melee — rewards staying in the fight |
| Ranged Damage | 0 | Pure melee |
| Armor | 6 | Solid armor — but the kit rewards taking damage, not avoiding it |
| Vision Range | 5 | Frontline tunnel vision |
| Ranged Range | 0 | Melee only |
| Allowed Weapons | `["melee", "hybrid"]` | Unchanged |
| Color | `#708090` (Slate) | Unchanged |
| Shape | `coffin` | Unchanged |

---

## New Skill Kit

### Skill Overview

| Slot | Skill | Icon | Target | Range | CD | Summary |
|:----:|-------|:----:|--------|:-----:|:--:|---------|
| 0 | Auto Attack (Melee) | — | Adjacent enemy | 1 | 0 | 1.15× melee damage (unchanged) |
| 1 | Grasp of the Grave | ⛓️ | Enemy (ranged) | 4 | 4 | Root enemy for 1 turn. Below 50% HP: root for 2 turns instead. (LOS required) |
| 2 | Death's Embrace | 🦴 | Self (AoE r=1) | 0 | 5 | Thorns aura: reflect 8 dmg/hit + gain +2 armor + heal 3 HP each time you're hit. Lasts 4 turns. |
| 3 | Soul Rend | ⚔️ | Adjacent enemy | 1 | 3 | 1.3× melee damage. Below 50% HP: 1.8× damage + 3-turn bleed (5 dmg/turn, ignores armor). |
| 4 | Undying Fury | 💀 | Self (passive trigger) | 0 | 12 | When you would die: revive at 25% HP + enter 3-turn Fury (50% melee damage, CC immune, auto-attacks heal 25% of damage dealt). Consumed on trigger. |

---

### Skill 1: Grasp of the Grave ⛓️

**Replaces:** Grave Chains

```
Skill ID:       grasp_of_the_grave
Type:           Ranged Root (NEW effect type: ranged_root)
Targeting:      enemy_ranged
Range:          4 tiles
Cooldown:       4 turns
LOS:            Required
Allowed Classes: ["revenant"]
```

**Effect:**
- Root the target enemy in place for 1 turn (cannot move, can still attack/cast)
- **Empowered (below 50% HP):** Root duration increases to 2 turns
- Does NOT deal damage — pure CC

**Design Notes:**
- Replaces the old single-target taunt (Grave Chains) with a more impactful and interactive CC
- Root is more useful than taunt: prevents kiting, locks enemies in Death's Embrace aura, stops fleeing targets
- The HP-conditional upgrade creates a moment of "oh no, the Revenant is wounded AND it just locked me down"
- 4-turn CD makes it the most frequently used CC in the kit — the Revenant's "get over here" tool
- Rooted enemies can still attack, so this isn't an oppressive stun — it's positioning control

**JSON Definition:**
```json
{
  "skill_id": "grasp_of_the_grave",
  "name": "Grasp of the Grave",
  "description": "Root enemy for 1 turn. Below 50% HP: root for 2 turns instead.",
  "flavor": "Spectral chains erupt from hallowed ground — the grave will not release its grip.",
  "icon": "⛓️",
  "targeting": "enemy_ranged",
  "range": 4,
  "cooldown_turns": 4,
  "mana_cost": 0,
  "effects": [
    {
      "type": "ranged_root",
      "root_duration": 1,
      "empowered_hp_threshold": 0.50,
      "empowered_root_duration": 2
    }
  ],
  "allowed_classes": ["revenant"],
  "requires_line_of_sight": true
}
```

**Particles:** Ghostly green chains erupt from ground at target's feet. Empowered version: chains glow brighter, ground cracks beneath target.

---

### Skill 2: Death's Embrace 🦴

**Replaces:** Grave Thorns

```
Skill ID:       deaths_embrace
Type:           Self-Buff (thorns + armor + heal-on-hit)
Targeting:      self
Range:          0
Cooldown:       5 turns
LOS:            Not required
Allowed Classes: ["revenant"]
```

**Effect:**
- For 4 turns, the Revenant gains an aura with three simultaneous effects:
  1. **Thorns:** Attackers take 8 flat damage per hit (ignores armor, same as old thorns mechanic)
  2. **Armor Boost:** +2 armor for the duration
  3. **Leech on Hit Taken:** Heal 3 HP each time the Revenant is hit by any attack (melee or ranged)

**Design Notes:**
- The old Grave Thorns reflected 12 damage but did nothing else — one-dimensional
- Death's Embrace reflects less per hit (8 vs 12) but adds survivability through +2 armor and 3 HP healed per hit
- Net effect when hit: enemy takes 8 thorns, Revenant heals 3 and has +2 armor. That's a 13-point swing per attack.
- Combined with 6 base armor → 8 effective armor during Embrace, approaching Crusader levels
- The heal-on-hit synergizes with the "take damage to get stronger" identity — getting hit sustains you
- 80% uptime (4/5 turns) is the same uptime ratio as the old Grave Thorns (4/5)
- Pairs naturally with Grasp of the Grave: root an enemy in your aura range so they have to hit you

**JSON Definition:**
```json
{
  "skill_id": "deaths_embrace",
  "name": "Death's Embrace",
  "description": "Thorns aura: reflect 8 dmg/hit + gain +2 armor + heal 3 HP when hit. Lasts 4 turns.",
  "flavor": "Bone shards erupt from dead flesh — every blow feeds the hunger within.",
  "icon": "🦴",
  "targeting": "self",
  "range": 0,
  "cooldown_turns": 5,
  "mana_cost": 0,
  "effects": [
    {
      "type": "deaths_embrace_buff",
      "thorns_damage": 8,
      "armor_bonus": 2,
      "heal_on_hit_taken": 3,
      "duration_turns": 4
    }
  ],
  "allowed_classes": ["revenant"],
  "requires_line_of_sight": false
}
```

**Particles:** Dark bone/shard aura swirling around the Revenant. When hit: brief green heal flash + red thorns pulse outward.

---

### Skill 3: Soul Rend ⚔️ (Reworked)

**Replaces:** Soul Rend (same name, reworked effect)

```
Skill ID:       soul_rend
Type:           Melee Damage + Conditional Bleed
Targeting:      enemy_adjacent
Range:          1
Cooldown:       3 turns
LOS:            Not required
Allowed Classes: ["revenant"]
```

**Effect:**
- **Normal (HP ≥ 50%):** Deal 1.3× melee damage to adjacent enemy
- **Empowered (HP < 50%):** Deal 1.8× melee damage + apply 3-turn bleed (5 damage/turn, ignores armor)

**Damage Calculations (vs 0 armor):**
- Normal: `16 × 1.3 = ~21 damage`
- Empowered: `16 × 1.8 = ~29 damage` + `5 × 3 = 15 bleed` = **44 total**
- Empowered vs 6 armor: `max(1, 29 − 6) = 23` + `15 bleed` = **38 total**

**Design Notes:**
- Replaces the old Soul Rend (1.5× damage + slow) which was bland
- The conditional mode creates a distinct gameplay inflection at 50% HP — the Revenant "transforms"
- 3-turn CD (down from 4) makes this the bread-and-butter combat ability
- Below 50% HP, this rivals Power Shot (1.8× ranged, CD 7) in single-hit damage and adds a bleed on top
- The bleed (5/turn, ignores armor, 3 turns = 15 total) synergizes with the "attrition" identity
- Pairs with Death's Embrace: you're getting healed while hitting, AND your hits become devastating when wounded
- Clear signal to enemies: "the wounded Revenant hits MUCH harder — do you focus it or leave it alone?"

**JSON Definition:**
```json
{
  "skill_id": "soul_rend",
  "name": "Soul Rend",
  "description": "1.3× melee damage. Below 50% HP: 1.8× damage + bleed (5/turn for 3 turns).",
  "flavor": "A cursed blade tears at the soul — and a wounded Revenant strikes with the fury of the damned.",
  "icon": "⚔️",
  "targeting": "enemy_adjacent",
  "range": 1,
  "cooldown_turns": 3,
  "mana_cost": 0,
  "effects": [
    {
      "type": "melee_damage_conditional_bleed",
      "damage_multiplier": 1.3,
      "empowered_hp_threshold": 0.50,
      "empowered_damage_multiplier": 1.8,
      "bleed_damage_per_turn": 5,
      "bleed_duration": 3
    }
  ],
  "allowed_classes": ["revenant"],
  "requires_line_of_sight": false
}
```

**Particles:** Normal: dark slash effect. Empowered: larger crimson slash + dripping blood particles on target (bleed indicator).

---

### Skill 4: Undying Fury 💀

**Replaces:** Undying Will

```
Skill ID:       undying_fury
Type:           Self-Buff (cheat death + rage state)
Targeting:      self
Range:          0
Cooldown:       12 turns
LOS:            Not required
Allowed Classes: ["revenant"]
```

**Effect:**
- **Cast:** Place the Undying Fury buff on self (5-turn duration window)
- **Trigger (on lethal damage):** Instead of dying:
  1. Revive at 25% max HP (`floor(130 × 0.25) = 32 HP`)
  2. Enter **Fury** state for 3 turns:
     - +50% melee damage (stacks with other buffs)
     - Immune to CC (roots, slows, stuns, taunts)
     - Auto-attacks heal for 25% of damage dealt (lifesteal)
  3. Buff is consumed (one-time trigger)
- If the 5-turn window expires without triggering, the buff is wasted

**Fury State Damage Examples (vs 0 armor):**
- Auto-attack during Fury: `16 × 1.5 × 1.15 = ~28 damage`, heals `~7 HP`
- Soul Rend (empowered, during Fury): `16 × 1.8 × 1.5 = ~43 damage` + bleed
- Death's Embrace + Fury: reflecting 8/hit, healing 3/hit from Embrace + 7/auto from lifesteal = massive sustain

**Design Notes:**
- Replaces the old Undying Will (passive cheat death at 30% HP, CD 8)
- CD increased to 12 (from original 8) — this should be a rare, pivotal moment, not a routine safety net
- Old version just revived you at 30% HP. New version revives at 25% HP (less) BUT gives you a terrifying 3-turn power spike — this is YOUR moment
- The Fury state is the Revenant's "big play": enemies have to decide whether to keep fighting a CC-immune lifesteal monster or disengage
- CC immunity during Fury prevents enemies from just stunning and ignoring the revived Revenant
- Lifesteal on autos during Fury synergizes with the +50% damage — bigger hits = bigger heals
- Pairs beautifully with Death's Embrace: if Embrace is still up when Fury triggers, you're reflecting + healing on hit taken + healing on hit dealt + bonus damage. Near-unkillable for 3 turns.
- The 5-turn activation window (same as old Undying Will) means you still need to time when you cast it — but the payoff for correct timing is much higher
- Still consumed on trigger — one death cheat per 12 turns

**JSON Definition:**
```json
{
  "skill_id": "undying_fury",
  "name": "Undying Fury",
  "description": "If you die within 5 turns: revive at 25% HP + enter Fury (3 turns: +50% damage, CC immune, autos heal 25%).",
  "flavor": "Death is a door — and the Revenant kicks it down. What returns is far worse than what fell.",
  "icon": "💀",
  "targeting": "self",
  "range": 0,
  "cooldown_turns": 12,
  "mana_cost": 0,
  "effects": [
    {
      "type": "undying_fury",
      "activation_window": 5,
      "revive_hp_pct": 0.25,
      "fury_duration": 3,
      "fury_damage_multiplier": 1.5,
      "fury_cc_immune": true,
      "fury_lifesteal_pct": 0.25
    }
  ],
  "allowed_classes": ["revenant"],
  "requires_line_of_sight": false
}
```

**Particles:** On cast: dark skull aura (similar to old Undying Will). On trigger: dramatic resurrection burst — ground cracks, red/green energy explosion, Revenant glows with rage aura for Fury duration.

---

## Gameplay Loop

### The Ideal Fight Arc

```
Turn 1:  Cast Death's Embrace (thorns + armor + heal-on-hit active)
Turn 2:  Close distance, Grasp of the Grave a priority target (rooted)
Turn 3:  Soul Rend the rooted target (at full HP: 1.3× damage)
Turn 4:  Auto-attack, taking hits → thorns reflect, heal-on-hit sustains
Turn 5:  HP drops below 50% → Soul Rend transforms (1.8× + bleed!)
Turn 6:  Death's Embrace expires → recast (CD 5 matches duration 4)
Turn 7:  Grasp empowered (below 50% → 2-turn root)
Turn 8:  HP critical → cast Undying Fury (safety net)
Turn 9:  "Killed" → revive at 32 HP → FURY STATE ACTIVATES
Turn 10: Fury turn 1: 28 damage autos, healing 7/hit, CC immune
Turn 11: Fury turn 2: Soul Rend empowered + Fury = 43 damage + bleed
Turn 12: Fury turn 3: still dangerous, enemies scramble
```

### Decision Points

Players must make real choices:
- **When to Embrace?** Early for value or save for a push?
- **Grasp target selection** — root the ranged DPS trying to kite? Root the healer to stop them running? Root the melee chasing your support?
- **Soul Rend timing** — use it above 50% for safe damage, or hold it for the empowered version?
- **Undying Fury timing** — cast too early and the 5-turn window expires. Cast too late and you die before pressing the button. This is the skill-ceiling moment.

---

## Comparison: Old vs New

| Aspect | Old Kit | New Kit |
|--------|---------|---------|
| **Thorns** | 12 flat damage/hit, nothing else | 8 damage/hit + 2 armor + 3 HP heal/hit |
| **CC** | Single-target taunt (Grave Chains) | Ranged root, empowered at low HP (Grasp) |
| **Damage skill** | 1.5× + slow (Soul Rend) | 1.3×/1.8× conditional + bleed (Soul Rend) |
| **Cheat death** | Revive at 30% HP, done | Revive at 25% HP + 3-turn Fury state (50% dmg, CC immune, lifesteal) |
| **Synergy** | None — 4 disconnected tools | Full loop: root → thorns → empowered strikes → Fury climax |
| **Decision-making** | Always the same | HP-conditional transforms, timing windows, target selection |
| **Identity** | "Worse Crusader" | "Damage-through-punishment bruiser — the more you hurt it, the worse it gets for you" |

---

## Comparison: Revenant vs Crusader (Both Tanks)

| Aspect | Crusader | Revenant (Reworked) |
|--------|----------|---------------------|
| **Tank Style** | Damage prevention (armor, shields) | Damage punishment (thorns, lifesteal, revenge) |
| **CC** | AoE taunt (r=2) + single stun | Ranged root (single, empowered at low HP) |
| **Team Utility** | Holy Ground (AoE heal) | None — selfish tank |
| **Damage** | Low (auto-attacks only) | High when wounded (empowered Soul Rend, Fury) |
| **Survivability** | Bulwark (+8 armor), high base armor | Death's Embrace heal-on-hit, cheat death + Fury |
| **Win Condition** | Outlast everything | Get hit → get angry → kill everything |
| **Weakness** | Low damage, needs team to kill | No team utility, vulnerable to kiting |

---

## Implementation Checklist

### Phase 25R-A: Config & Data Model ✅ COMPLETE
- [x] Update `skills_config.json` — removed old 4 skills (grave_thorns, grave_chains, undying_will, soul_rend), added new 4 skills (grasp_of_the_grave, deaths_embrace, soul_rend, undying_fury)
- [x] Update `class_skills` mapping in `skills_config.json` → `["auto_attack_melee", "grasp_of_the_grave", "deaths_embrace", "soul_rend", "undying_fury"]`
- [x] Verify `classes_config.json` base stats unchanged — confirmed (130 HP, 16 melee, 6 armor, coffin shape)
- [x] `names_config.json` — no changes needed (names are class-level, not skill-level)
- [x] Fixed regression tests: `test_skills.py` and `test_phase26a_shaman_config.py` updated to reference new skill IDs
- [x] JSON validated, 3892 non-Revenant tests passing (3890 + 2 fixed)

### Phase 25R-B: Effect Handlers (server/app/core/skill_effects/) ✅ COMPLETE
- [x] New handler: `resolve_ranged_root()` in debuff.py for Grasp of the Grave
  - Standard range/LOS checks
  - Apply `root` debuff (cannot move, can attack)
  - HP-conditional duration check (1 turn normal, 2 turns if caster < 50% HP)
  - CC immunity check (Fury state targets resist root)
- [x] New handler: `resolve_deaths_embrace()` in buff.py for Death's Embrace
  - Apply triple buff: thorns_damage + armor_bonus + heal_on_hit_taken
  - All three share the same duration and buff_id
  - Thorns uses existing thorns mechanics in combat.py
  - Armor bonus uses existing buff armor stacking
  - Heal-on-hit-taken is a NEW mechanic: check in `calculate_damage` / `calculate_ranged_damage`
- [x] Rework handler: `resolve_melee_damage_conditional_bleed()` in damage.py for Soul Rend
  - Check caster HP ratio
  - Normal mode: 1.3× melee damage, no bleed
  - Empowered mode: 1.8× melee damage + apply bleed DoT (5/turn, 3 turns, ignores armor)
  - Bleed uses existing DoT tick mechanics
- [x] Rework handler: `resolve_undying_fury()` in buff.py for Undying Fury
  - On cast: apply `undying_fury` buff with 5-turn activation window
  - Stores fury_duration, fury_damage_multiplier, fury_cc_immune, fury_lifesteal_pct on buff entry
  - On lethal damage (in deaths_phase.py — Phase 25R-C): check for `undying_fury` buff
  - Trigger: revive at 25% HP, remove `undying_fury` buff, apply `fury_state` buff (3 turns)
  - Fury buff: melee_damage_multiplier 1.5, cc_immune flag, lifesteal_pct 0.25
- [x] Wired all 4 new effect types into `resolve_skill_action()` dispatcher in skills.py
- [x] Updated `__init__.py` exports for all 4 new handlers
- [x] 3855 non-Revenant tests passing (0 regressions from 25R-A baseline)

### Phase 25R-C: Combat Integration ✅ COMPLETE
- [x] `calculate_damage` / `calculate_ranged_damage`: add heal_on_hit_taken check for Death's Embrace
  - Defender heals `magnitude` HP each time they are hit (melee or ranged)
  - New combat_info keys: `heal_on_hit_taken_healed`, `fury_lifesteal_healed`
- [x] `deaths_phase.py`: update cheat death check — detect `undying_fury` type buff
  - On trigger: apply `fury_state` buff with `stat: melee_damage_multiplier`, `cc_immune: True`, `fury_lifesteal_pct`
  - Fury state buff uses existing `get_melee_buff_multiplier()` for +50% damage (no extra wiring needed)
  - Updated skill_id and message to distinguish Undying Fury from legacy Undying Will
- [x] `buffs_phase.py`: fury_state buff ticks down correctly via existing `tick_buffs()` (no changes needed)
  - Added CC immunity check to earthgrasp totem root application (cc_immune units resist root)
- [x] `combat.py`: apply fury lifesteal on auto-attacks when fury_state buff active
  - Checks attacker's active_buffs for `type == "fury_state"`, heals `fury_lifesteal_pct` × damage dealt
  - Works in both `calculate_damage` (melee) and `calculate_ranged_damage` (ranged)
- [x] `combat_phase.py`: added combat log messages for heal_on_hit_taken and fury_lifesteal (both melee and ranged)
- [x] `movement_phase.py` / root handling: already exists from Phase 26C Earthgrasp Totem — `is_rooted()` checks `stat == "rooted"`, Grasp of the Grave uses same stat. No changes needed.
- [x] 3855 non-Revenant tests passing (0 regressions from 25R-B baseline)

### Phase 25R-D: AI Behavior ✅ COMPLETE
- [x] Update `_CLASS_ROLE_MAP` — revenant stays as `retaliation_tank`, comment updated to reference new skill kit
- [x] Rewrite `_retaliation_tank_skill_logic()` in ai_skills.py:
  - Priority 1: Undying Fury if HP < 35% and no undying_fury/fury_state buff active and off CD
  - Priority 2: Soul Rend on adjacent enemy (targets lowest-HP; empowered below 50% HP → 1.8× + bleed)
  - Priority 3: Death's Embrace if no embrace buff active and enemies within 2 tiles
  - Priority 4: Grasp of the Grave on ranged/kiting enemy within 4 tiles with LOS (skips already-rooted; scores by squishy priority + ranged bonus + low-HP fleeing bonus)
  - Priority 5: Fall through to auto-attack
- [x] Updated AI constants: `_UNDYING_FURY_HP_THRESHOLD` (0.35), `_DEATHS_EMBRACE_MIN_NEARBY` (1), `_DEATHS_EMBRACE_NEARBY_RANGE` (2), `_GRASP_OF_THE_GRAVE_RANGE` (4), `_SOUL_REND_EMPOWERED_THRESHOLD` (0.50), `_GRASP_TARGET_PRIORITY` (includes shaman)
- [x] Update AI stance retreat threshold — Revenant never retreats during Fury state (fury_state buff) OR while cheat_death (undying_fury) buff is active
- [x] Updated `_decide_skill_usage()` dispatcher comment for retaliation_tank role
- [x] 3855 non-Revenant tests passing (0 regressions from 25R-C baseline)

### Phase 25R-E: Client / UI ✅ COMPLETE
- [x] Update skill tooltip data for new 4 skills
  - `skillInfo.js`: Replaced `grave_thorns`, `grave_chains`, `undying_will`, old `soul_rend` entries with `grasp_of_the_grave`, `deaths_embrace`, reworked `soul_rend`, `undying_fury`
  - Updated names, icons, descriptions, cooldowns, ranges, and targeting types to match Phase 25R design spec
- [x] Add particle definitions for Grasp, Death's Embrace, Soul Rend (empowered), Undying Fury trigger
  - `particle-effects.json`: Replaced old 4 skill→effect mappings with new skill IDs
    - `grasp_of_the_grave` → `revenant-grasp-chains` + `revenant-grasp-ground-crack` (extras)
    - `deaths_embrace` → `revenant-embrace-aura` + `revenant-embrace-bone-shards` (extras)
    - `undying_fury` → reuses `revenant-undying-activate` (updated tags)
    - `soul_rend` → `revenant-soul-rend` + `revenant-soul-rend-empowered` (extras)
  - `particle-presets/skills.json`: Replaced old `revenant-thorns-cast` and `revenant-chains-taunt` presets with 4 new presets:
    - `revenant-grasp-chains` — ghostly green chains erupting upward at target feet (ring spawn, spectral green gradient)
    - `revenant-grasp-ground-crack` — ground debris triangles beneath rooted target
    - `revenant-embrace-aura` — dark bone/shard aura swirling around caster (ring spawn, dark earth tones)
    - `revenant-embrace-bone-shards` — bone shard triangles flying outward from caster
    - `revenant-soul-rend-empowered` — larger crimson slash burst for empowered mode (red gradient, 35 particles)
  - Kept existing `revenant-undying-activate`, `revenant-revive-burst`, `revenant-revive-ground-crack` (reused for Undying Fury cast + trigger)
  - Updated `revenant-soul-rend` version to 2 (unchanged visuals, kept for normal-mode hits)
- [x] Update skillbar icons
  - `SkillIconMap.js`: Replaced old 4 skill entries in both `SKILL_SPRITE_MAP` (null/emoji fallback) and `EMOJI_FALLBACKS` with new skill IDs
  - Icons: ⛓️ (Grasp), 🦴 (Embrace), ⚔️ (Soul Rend), 💀 (Undying Fury) — matching Phase 25R spec
- [x] Add `formatEffect()` cases in `SkillTooltip.jsx` for 4 new effect types:
  - `ranged_root` — displays root duration + empowered threshold/duration
  - `deaths_embrace_buff` — displays thorns, armor, heal-on-hit, duration
  - `melee_damage_conditional_bleed` — displays normal/empowered multipliers + bleed damage
  - `undying_fury` — displays activation window, revive %, Fury stats (damage, CC immune, lifesteal)
- [x] Add `computeDamageEstimate()` case for `melee_damage_conditional_bleed` — shows normal + empowered + bleed total estimates

### Phase 25R-F: Audio ✅ COMPLETE
- [x] New SFX: `grasp_of_the_grave` — mapped to `cast_strong-energy.wav` (earth energy root, consistent with Shaman earthgrasp)
- [x] Update SFX: `deaths_embrace` — mapped to `cast_hollow-spell.wav` (dark ominous aura activation)
- [x] Update SFX: `soul_rend` — kept `soul-reap_gore-pierce.wav` for normal mode; added `skill_soul_rend_empowered` → `melee-crit_sword-critical.wav` for empowered mode (deeper, more aggressive)
- [x] New SFX: `undying_fury_trigger` — mapped to `portal-open_flare-nova.wav` (dramatic resurrection explosion, adapted from old undying_revive)
- [x] Reuse: `undying_fury` cast — mapped to `cast_hollow-spell.wav` (adapted from old `undying_will` cast sound)
- [x] Updated `audio-effects.json` — replaced old Revenant `_soundFiles` keys and `skills` section entries with new skill IDs
- [x] Updated `AudioManager.js` — changed `undying_will` special handler to `undying_fury`; added empowered Soul Rend detection via `buff_applied` (bleed = empowered)
- [x] Updated `soundMap.js` — replaced old SOUND_KEYS constants (GRAVE_THORNS, GRAVE_CHAINS, UNDYING_WILL, UNDYING_REVIVE) with new ones (GRASP_OF_THE_GRAVE, DEATHS_EMBRACE, UNDYING_FURY, UNDYING_FURY_TRIGGER, SOUL_REND_EMPOWERED)
- [x] Updated `generate_sfx.py` (audio workbench) — renamed generator functions, add registration entries, synth metadata, and new `gen_soul_rend_empowered()` generator

### Phase 25R-G: Tests
- [ ] Update `test_phase25a_revenant_config.py` — new skill IDs, new effect types
- [ ] Update `test_phase25b_revenant_handlers.py` — new handler tests for all 4 skills
- [ ] Update `test_phase25c_revenant_buff_integration.py` — new thorns+heal-on-hit, fury state integration
- [ ] Update `test_phase25d_revenant_ai.py` — new AI priority chain
- [ ] Add test: Soul Rend normal vs empowered HP threshold
- [ ] Add test: Grasp root duration normal vs empowered
- [ ] Add test: Undying Fury trigger → fury state applied with correct properties
- [ ] Add test: Fury state lifesteal on auto-attacks
- [ ] Add test: Fury state CC immunity (roots/slows/stuns don't apply)
- [ ] Add test: Fury state expires after 3 turns
- [ ] Add test: Death's Embrace heal-on-hit-taken triggers on melee and ranged hits
- [ ] Regression: existing Crusader/Blood Knight/Shaman tests still pass

### Phase 25R-H: Documentation
- [ ] Update `class-overview.md` — Revenant section
- [ ] Update `phase25-revenant-class.md` — add rework addendum or replace
- [ ] Update `game-balance-reference.md` if it references Revenant skills

---

## Risks & Considerations

1. **Root mechanic may already exist** — Earthgrasp Totem (Shaman) applies roots. Check if the existing root debuff handling in movement_phase.py can be reused for Grasp of the Grave. If so, Grasp just applies the same debuff type.

2. **Fury state power level** — 3 turns of +50% damage + CC immune + lifesteal is very strong. Monitor in batch PVP testing. Tuning levers: reduce fury_damage_multiplier (1.5 → 1.3), reduce fury_lifesteal_pct (0.25 → 0.15), reduce fury_duration (3 → 2).

3. **Heal-on-hit-taken is new** — No existing skill uses this mechanic. Needs new code in `calculate_damage` and `calculate_ranged_damage`. Should be straightforward — check for buff, heal the defender.

4. **Test count impact** — The 4 existing Revenant test files (phases 25A–25D) reference old skill IDs extensively. Most tests will need updating rather than writing from scratch. Expect ~80% test rewrite for Revenant-specific files.

5. **Backward compatibility** — Any saved player data with old Revenant skills in cooldown state will need graceful handling (cooldowns for removed skills should be silently dropped).
