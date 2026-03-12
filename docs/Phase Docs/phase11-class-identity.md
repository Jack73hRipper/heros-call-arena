# Phase 9: Class Identity & Tactical Depth — Design Document

## Overview

**Goal:** Define clear identities for Hexblade, Inquisitor, and Confessor. Add tactical enemy variety with swarm and healer units.

**Timeline:** 3 weeks  
**Status:** Planning Phase  
**Prerequisites:** Phase 8K complete

---

## Current State

**What's Working:**
- Combat feels balanced (1-second ticks, targeting system polished)
- Wave arena testing shows good AI ally/enemy interactions
- Armor system is fine (flat reduction works for intended class roles)
- 5 distinct classes with clear roles

**What Needs Work:**
- Hexblade lacks thematic identity
- Inquisitor lacks clear scout/demon hunter feel
- Confessor has only 1 utility skill (needs more support options)
- Only 3 enemy types (need swarm and priority-target variety)

---

## Phase 9 Scope

### Focus Areas

**Class Identity:**
1. Hexblade: Curse specialist with DoT and reflective defense
2. Inquisitor: Divine demon hunter with detection and holy smite
3. Confessor: Full support kit with buffs, healing, and holy offense

**Enemy Variety:**
4. Imp: Swarm unit (low HP, high numbers)
5. Dark Priest: Enemy healer (priority target)

**Not Included:**
- New classes
- Item system changes
- Map additions
- Armor formula rework (current system is balanced)

---

## Feature 1: Hexblade Identity - Curse Specialist

**Theme:** Dark magic warrior who inflicts curses, damage-over-time, and punishes attackers with reflective barriers.

### New Abilities

#### **Wither** (DoT Curse)
```
Type: Curse/Damage-Over-Time
Range: 3 tiles
Effect: Deal 6 damage per turn for 4 turns (24 total damage)
Cooldown: 6 turns
LOS: Yes
Targeting: Enemy
```

**Design notes:**
- Higher total damage than Double Strike (24 vs 18) but delayed
- Requires target tracking over multiple turns
- Cannot stack multiple Withers on same target
- 3-tile range allows casting without melee adjacency

---

#### **Ward** (Reflective Self-Shield)
```
Type: Self-Buff
Range: Self only
Effect: Gain 3 charges. When attacked, attacker takes 8 damage and consume 1 charge.
Duration: 6 turns (or until all charges consumed)
Cooldown: 6 turns
```

**Design notes:**
- 3 charges = reflects up to 3 attacks (24 total reflected damage)
- Good uptime: 6-turn duration with 6-turn cooldown (can maintain ~50% uptime if used on cooldown)
- Does not reduce incoming damage (you still take full hit)
- Strategic use: Pop before boss, before Imp swarm, or before multi-hit abilities

---

### Complete Hexblade Kit

```
1. Double Strike - 2 hits × 60% melee damage (18 total), 3-turn cooldown
2. Shadow Step - Teleport 4 tiles, 5-turn cooldown
3. Wither - 6 dmg/turn for 4 turns (24 total), 3-tile range, 6-turn cooldown
4. Ward - 3 charges of 8 reflected damage, 6-turn duration, 6-turn cooldown
```

**Identity achieved:** Dark magic hybrid who curses enemies, sustains through reflection, and adapts between melee/ranged.

---

## Feature 2: Inquisitor Identity - Divine Demon Hunter

**Theme:** Scout and holy warrior who excels at detecting and eliminating Undead/Demon threats. Best vision in game (9 tiles) with divine powers.

### New Abilities

#### **Divine Sense** (Detection)
```
Type: Detection/Utility
Range: 12 tiles radius (area around caster)
Effect: Reveals all Undead/Demon enemies for 4 turns
        (Shows position only, not full FOV of area)
Cooldown: 7 turns
Targeting: Self (AoE detection)
```

**Design notes:**
- 12-tile radius covers most of a 20×20 room
- Only reveals Undead/Demons (not all enemy types)
- Shows enemy position markers, doesn't grant vision of tiles
- Strategic use: Scout rooms, track boss, locate hiding enemies

---

#### **Rebuke the Wicked** (Holy Smite)
```
Type: Damage (Holy/Ranged)
Range: 6 tiles
Effect: Deal 28 damage
        Bonus: +50% damage vs Undead/Demons (42 total)
Cooldown: 5 turns
LOS: Yes
Targeting: Enemy
```

**Design notes:**
- 42 damage vs Undead/Demons (highest burst in game against themed enemies)
- 28 damage vs others (still respectable)
- 6-tile range (longer than standard 5, fits "smite from afar" theme)
- Makes Inquisitor premier Undead/Demon killer

---

### Complete Inquisitor Kit

```
1. Power Shot - 1.8× ranged damage (14 total), 5-turn cooldown
2. Shadow Step - Teleport 4 tiles, 5-turn cooldown
3. Divine Sense - Reveal Undead/Demons in 12-tile radius for 4 turns, 7-turn cooldown
4. Rebuke the Wicked - 28 damage (42 vs Undead/Demons), 6-tile range, 5-turn cooldown
```

**Identity achieved:** Divine scout who detects threats and eliminates Undead/Demons with holy power. Strong mobility, best vision, anti-demon specialist.

---

## Feature 3: Confessor Identity - Full Support

**Theme:** Healer and buffer who keeps the party alive and empowered. Only class with multi-target healing and protective buffs.

### New Abilities

#### **Shield of Faith** (Defensive Buff)
```
Type: Buff/Support
Range: 3 tiles
Effect: Grant ally +5 armor for 3 turns
Cooldown: 5 turns
Targeting: Ally or Self
```

**Design notes:**
- +5 armor is significant (reduces damage by 5 per hit for 3 turns)
- Can self-cast if needed
- Stacks with equipment armor

---

#### **Exorcism** (Holy Offense)
```
Type: Damage (Holy/Ranged)
Range: 5 tiles
Effect: Deal 20 holy damage
        Bonus: +100% damage vs Undead/Demons (40 total)
Cooldown: 4 turns
LOS: Yes
Targeting: Enemy
```

**Design notes:**
- 40 damage vs Undead/Demons (Confessor's only offensive tool)
- 20 damage vs others (respectable for support class)
- Shorter cooldown than Rebuke (4 vs 5 turns) but less base damage
- Gives Confessor threat against priority targets

---

#### **Prayer** (Heal Over Time)
```
Type: Heal/Support
Range: 4 tiles (longer than Heal)
Effect: Heal 8 HP per turn for 4 turns (32 total healing)
Cooldown: 6 turns
Targeting: Ally or Self
```

**Design notes:**
- 32 total healing vs Heal's instant 30 (slightly more efficient)
- Heal over time = better sustain in long fights, worse in emergencies
- 4-tile range (longer than Heal's 3) = safer positioning
- Complements instant Heal (use Prayer for sustained damage, Heal for burst healing)

---

### Complete Confessor Kit

```
1. Heal - Heal 30 HP instantly, 3-tile range, 4-turn cooldown
2. Shield of Faith - Grant ally +5 armor for 3 turns, 3-tile range, 5-turn cooldown
3. Exorcism - 20 damage (40 vs Undead/Demons), 5-tile range, 4-turn cooldown
4. Prayer - Heal 8 HP/turn for 4 turns (32 total), 4-tile range, 6-turn cooldown
```

**Identity achieved:** Full support with burst healing, sustained healing, damage prevention, and holy offense. Can contribute to fights while keeping party alive.

---

## Feature 4: Imp - Swarm Enemy

**Purpose:** Low-HP enemy that appears in large groups. Forces AoE, target switching, or gets overwhelmed.

### Stats

```
HP ......... 30        Melee Dmg .. 8
Armor ...... 0         Vision ..... 6
AI ......... Aggressive (rush nearest target)
Spawn ...... Groups of 4-6
Gold ....... 5g per kill
Loot ....... 20% drop rate, common items only
```

### Behavior

**AI Pattern:**
1. Spawn as group (4-6 imps together)
2. Rush nearest player target
3. No retreat or tactical behavior
4. Die easily (2-3 hits from most classes)

**Tactical Challenge:**
- 4 imps = 32 damage if all hit (threatening)
- 6 imps = 48 damage (deadly to squishy classes)
- Forces target switching or AoE (when available)
- Low gold/loot individually but adds up

**Wave Arena Integration:**
- Wave 2: 6× Imp (pure swarm)
- Wave 5: 3× Imp + 1× Demon (mixed threat)
- Wave 7: 4× Imp + 2× Skeleton (ranged support for swarm)

---

## Feature 5: Dark Priest - Enemy Healer

**Purpose:** Priority target that extends fights by healing allies. Forces tactical focus-fire.

### Stats

```
HP ......... 80        Melee Dmg .. 6
Ranged ..... 10        Armor ...... 3
Range ...... 5         Vision ..... 7
Skills ..... Heal (30 HP, 3-tile range, 4-turn cooldown)
AI ......... Heal allies → Flee if adjacent → Ranged attack
Gold ....... 15g
Loot ....... 60% drop rate, 1-2 common items
```

### Behavior

**AI Priority:**
1. **Heal allies** if any ally below 50% HP and in range (3 tiles)
2. **Flee 3 tiles away** if enemy adjacent
3. **Ranged attack** if no allies need healing and enemy in range
4. **Move toward allies** if isolated

**Tactical Challenge:**
- Healing 30 HP every 4 turns extends fights significantly
- Must identify and prioritize or match becomes war of attrition
- Flees when approached = ranged classes excel, melee must chase
- 80 HP = survives 5-6 hits (tankier than Skeleton, less than Demon)

**Wave Arena Integration:**
- Wave 4: 1× Dark Priest + 2× Demon (healer protected by tanks)
- Wave 6: 1× Dark Priest + 1× Undead Knight (boss + support)
- Wave 8: 2× Dark Priest + 2× Demon (double healer chaos)

---

## Development Timeline

### Week 1: Class Abilities

**Backend:**
- Add Wither, Ward, Divine Sense, Rebuke, Shield of Faith, Exorcism, Prayer to skills config
- Implement Ward charge system (3 charges, consume on hit, reflect damage)
- Implement DoT system for Wither (damage per turn tracking)
- Implement HoT system for Prayer (healing per turn tracking)
- Update turn resolver to process DoT/HoT each tick

**Frontend:**
- Update ActionBar to show new skills
- Add charge counter for Ward (display 3/2/1 charges remaining)
- Add DoT/HoT status indicators on units (debuff/buff icons)
- Update combat log for new skill messages

**Testing:**
- Each skill works as designed
- Ward charges consume correctly
- Wither DoT applies and ticks correctly
- Divine Sense reveals Undead/Demons only
- Rebuke/Exorcism bonus damage applies to correct enemy types

---

### Week 2: New Enemies

**Backend:**
- Add Imp and Dark Priest to enemies config
- Implement Imp group spawn logic (4-6 together)
- Implement Dark Priest AI (heal priority, flee behavior)
- Update wave arena with new enemy compositions

**Frontend:**
- Add Imp sprite/visual
- Add Dark Priest sprite/visual
- Update enemy rendering for new types

**Testing:**
- Imps spawn in groups correctly
- Dark Priest heals allies and flees when approached
- New wave compositions are balanced

---

### Week 3: Balance & Polish

**Focus:**
- Playtest all new abilities extensively
- Tune cooldowns/damage if needed
- Adjust enemy HP/damage based on testing
- Update combat log clarity
- Bug fixes

**Testing:**
- 10+ wave arena runs with new classes
- Hexblade Ward uptime feels right (not infinite, but reliable)
- Confessor feels useful (not just "heal bot")
- Inquisitor excels vs Undead/Demons
- Imps feel threatening but not overwhelming
- Dark Priest extends fights without making them tedious

---

## Balance Summary

### Skill Power Budget

| Class | Ability | Type | Damage/Effect | Cooldown | Power Rating |
|-------|---------|------|---------------|----------|--------------|
| **Hexblade** | Double Strike | Burst | 18 instant | 3 turns | High |
| | Shadow Step | Mobility | Teleport 4 | 5 turns | High |
| | Wither | DoT | 24 over 4 turns | 6 turns | High |
| | Ward | Defense | Reflect 24 (3×8) | 6 turns | Medium |
| **Inquisitor** | Power Shot | Burst | 14 instant | 5 turns | Medium |
| | Shadow Step | Mobility | Teleport 4 | 5 turns | High |
| | Divine Sense | Utility | Reveal Undead/Demons | 7 turns | Medium |
| | Rebuke | Burst | 42 vs Undead | 5 turns | Very High |
| **Confessor** | Heal | Support | 30 instant | 4 turns | High |
| | Shield of Faith | Support | +5 armor × 3 turns | 5 turns | High |
| | Exorcism | Burst | 40 vs Undead | 4 turns | High |
| | Prayer | Support | 32 over 4 turns | 6 turns | Medium |

### Enemy Power Budget

| Enemy | HP | Armor | Damage | Special | Threat Level |
|-------|----|----|--------|---------|--------------|
| Skeleton | 60 | 1 | 6 melee, 14 ranged | - | Low |
| Demon | 120 | 4 | 18 melee | - | Medium |
| Undead Knight | 200 | 10 | 25 melee | - | High (Boss) |
| **Imp** | 30 | 0 | 8 melee | Swarm (4-6) | Medium (Group) |
| **Dark Priest** | 80 | 3 | 6 melee, 10 ranged | Heal 30 HP | High (Priority) |

---

## Success Criteria

**Phase 9 is complete when:**

- ✅ Hexblade has clear curse/reflection identity
- ✅ Inquisitor has clear demon hunter/scout identity
- ✅ Confessor has full support kit (4 abilities)
- ✅ All new skills functional and balanced
- ✅ Imp swarms provide tactical challenge
- ✅ Dark Priest forces priority targeting
- ✅ Wave arena includes new enemy types
- ✅ 10+ successful playtests with no critical bugs
- ✅ All classes feel complete and distinct

---

## Post-Phase 9 Considerations

**What's Next (Phase 10+ options):**

**If game feels complete:**
- Polish pass (visual effects, sound, UI improvements)
- Deployment (host online for friends)
- Content additions (more maps, more enemy types)

**If game needs more depth:**
- AoE abilities (fireball, arrow rain, etc.)
- Status effects (stun, slow, root, poison)
- More enemy types (casters, summoners, elites)
- Rare/Epic item tiers

**Decision made after Phase 9 playtesting.**

---

**Document Version:** 1.0  
**Created:** February 2026  
**Status:** Planning Phase  
**Prerequisites:** Phase 8K Complete
