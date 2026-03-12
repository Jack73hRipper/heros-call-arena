# Enemy HP Rebalance & Identity Roadmap

**Date:** February 24, 2026  
**Scope:** Enemy survivability pass + future enemy identity improvements  
**Files Modified:** `server/configs/enemies_config.json`, `server/tests/test_enemy_types.py`

---

## Problem

Enemies were dying so fast that players couldn't even tab-target to them before they were dead. A full 5-hero party outputs **~82 raw auto-attack damage per turn** (before skills), meaning:

- **Imp** (30 HP) — dead before anyone registers it spawned  
- **Skeleton** (60 HP) — dead in under 1 turn of group focus  
- **Wraith/Acolyte** (70 HP) — dead in 1 turn, never gets to use Wither or Heal  
- **Dark Priest** (80 HP) — "kill the healer" is moot when it's already dead  

The game felt like "shoot whatever, they die" instead of the intended "we need to DPS this target down first as a group."

### Root Cause

HP pools were tuned for 1-2 hero encounters, not a full party. Six of eleven enemies had less HP than a **Confessor** (100 HP, the squishiest player class). Roles like "healer" and "caster DPS" never had time to express because the enemies died before using their second ability.

---

## Changes Applied — HP & Armor Rebalance

### Before → After

| Enemy | Role | Old HP | **New HP** | Old Armor | **New Armor** | TTK Change |
|---|---|---|---|---|---|---|
| **Imp** | Swarm | 30 | **70** | 0 | **1** | ~0.4 → ~1 turn (still swarmy, but survives a hit) |
| **Skeleton** | Ranged Sniper | 60 | **125** | 1 | **2** | ~0.8 → ~2 turns |
| **Wraith** | Caster DPS | 70 | **145** | 2 | **3** | ~1 → ~2-3 turns (gets to Wither + Shadow Step) |
| **Acolyte** | Support | 70 | **150** | 2 | **3** | ~1 → ~2-3 turns (actually heals before dying) |
| **Dark Priest** | Healer | 80 | **170** | 3 | **4** | ~1.2 → ~3 turns (heals 2-3 times) |
| **Medusa** | Debuff Caster | 90 | **180** | 3 | **4** | ~1.3 → ~3 turns (Venom Gaze + Power Shot combo) |
| **Demon** | Melee Bruiser | 120 | **240** | 4 | **5** | ~2 → ~4 turns |
| **Werewolf** | Melee Elite | 130 | **290** | 5 | **6** | ~2.3 → ~5-6 turns |
| **Construct** | Tank | 160 | **320** | 10 | **10** | ~5 → ~9-10 turns (unchanged armor) |
| **Undead Knight** | Boss | 200 | **425** | 10 | **12** | ~6 → ~14-16 turns |
| **Reaper** | Boss | 250 | **525** | 8 | **10** | ~6 → ~13-15 turns |

### Design Goals by Tier

| Tier | Enemies | Target TTK (party focus) | Intent |
|---|---|---|---|
| **Trash** | Imp | ~1 turn | Still dies fast in groups, but not instant. Swarmy feel preserved. |
| **Standard** | Skeleton, Wraith, Acolyte | ~2-3 turns | Long enough for roles to matter. Players choose who to burn first. |
| **Priority** | Dark Priest, Medusa | ~3 turns | Healers/debuffers survive long enough to force "kill this first" decisions. |
| **Bruiser** | Demon | ~4 turns | Meaty frontliner that pressures the Crusader while DPS works. |
| **Elite** | Werewolf | ~5-6 turns | True group DPS check. War Cry + Double Strike makes it scary. |
| **Wall** | Construct | ~9-10 turns | Slow-burn tank. Punishes you for ignoring it (Ward reflect). |
| **Boss** | Undead Knight, Reaper | ~13-16 turns | Multi-minute encounters. Party coordination required. |

### Unchanged Stats

All damage values, skill kits, AI behaviors, vision ranges, ranged ranges, colors, shapes, tags, and boss flags remain **unchanged**. Only `base_hp` and `base_armor` were adjusted.

---

## Test Updates

Three test assertions in `test_enemy_types.py` referenced hardcoded HP/armor values:

| Test | Old Assertion | New Assertion |
|---|---|---|
| `test_demon_definition` | `base_hp == 120` | `base_hp == 240` |
| `test_skeleton_definition` | `base_hp == 60` | `base_hp == 125` |
| `test_undead_knight_definition` | `base_hp == 200`, `base_armor == 10` | `base_hp == 425`, `base_armor == 12` |

---

## Future Development: Enemy Identity Skills

### Problem

Three enemies — **Demon**, **Skeleton**, and **Imp** — have zero skills. They are pure stat sticks with no tactical identity beyond "hits hard" or "dies fast." Even with the HP buff, they don't create interesting decisions. The spellcasting enemies (Wraith, Medusa, Werewolf, etc.) are far more engaging because their skills force target priority choices.

Additionally, **Dark Priest** and **Acolyte** share the *exact same skill kit* (Heal + Shield of Faith) with the same `support` AI. They're functionally identical, just with different tags and minor stat differences.

### Proposed Skill Additions

#### Demon — *Enrage* (Passive/Triggered)

```
Trigger ..... Activates when HP drops below 30%
Effect ...... +50% melee damage for the rest of the fight (18 → 27 per hit)
Duration .... Permanent (once triggered)
AI Impact ... Demon becomes more dangerous as fight drags on
Tactical .... Forces the party to commit — either burn it fast before enrage,
              or swap targets and deal with a raging demon later.
```

**Why this fits:** The Demon's identity is "ferocious melee attacker." An enrage mechanic at low HP creates a burn-or-kite decision. Do you finish it off before it enrages, or switch to the healer and deal with a 27-damage demon pounding your Crusader?

**Alternative option — *Charge*:**
```
Type ......... Mobility + Damage  Range ...... 3 tiles
Cooldown ..... 5 turns            Effect ..... Leap to target, deal 1.3× melee
Tactical .... Lets demons close gaps on kiting Rangers. Makes positioning matter.
```

---

#### Skeleton — *Bone Shield* (Self-Buff)

```
Type ......... Self-Buff          Cooldown ... 6 turns
Effect ...... Absorb the next 25 damage (shield HP, not armor)
Duration .... Until depleted or 4 turns
AI Impact ... Skeleton activates when an enemy enters its vision range
Tactical .... Adds a "break the shield first" mechanic. You need to pop the
              barrier before your real damage sticks.
```

**Why this fits:** Skeletons are glass cannons — high ranged DPS but fragile. A damage-absorb shield gives them a "you have to work through this" moment without changing their core feel. It also rewards focus-firing: one hero pops the shield, then the next lands the real hit.

**Alternative option — *Aimed Shot* (Charged Attack):**
```
Type ......... Ranged Attack      Range ...... 5 tiles
Cooldown ..... 5 turns            Effect ..... 2.0× ranged damage (28 damage)
Charge ...... 1-turn windup (visible to player, can be interrupted by stun/root)
Tactical .... Creates "interrupt that skeleton before it fires" pressure.
```

---

#### Imp — *Frenzy Aura* (Pack Buff)

```
Type ......... Passive Aura       Range ...... 2 tiles (adjacent imps)
Effect ...... All imps within 2 tiles gain +3 melee damage (+8 → +11)
Stacking .... Each imp provides the aura, so 4 clustered imps = +9 each (8+9=17)
AI Impact ... Imps swarm tighter to stack the buff
Tactical .... Killing the first imp weakens the rest. Creates a "thin the herd"
              priority — each imp you kill reduces pack damage significantly.
```

**Why this fits:** Imps are swarmers. A pack-scaling buff makes them dangerous in numbers but weak individually. It rewards AoE (Volley) and creates satisfying "break the swarm" moments. A lone imp is harmless; six imps in a cluster are terrifying.

**Alternative option — *Suicide Pounce*:**
```
Type ......... Melee + Self-Kill  Range ...... 2 tiles (leap)
Cooldown ..... One-time use       Effect ..... Leap to target, deal 20 damage, imp dies
Trigger ..... Below 50% HP        
Tactical .... Imps become "deal with me now or I'll kamikaze your healer."
```

---

### Differentiating Dark Priest vs. Acolyte

Currently both have Heal + Shield of Faith. Proposed rework:

#### Dark Priest — *Offensive Support* (keep Heal, replace Shield of Faith)

```
New Skill: Dark Pact
Type ......... Ally Buff          Range ...... 4 tiles
Cooldown ..... 5 turns            Duration ... 3 turns
Effect ...... Target ally gains +25% damage for 3 turns
AI Impact ... Prioritizes buffing the highest-damage ally (Demon, Werewolf)
Tactical .... Kill the Dark Priest before it buffs the Werewolf, or you're
              dealing with a 27-damage (or War Cry'd 55-damage) monster.
```

**Identity:** Dark Priest = offensive enabler. Heals AND buffs ally damage. Highest priority target because it multiplies the danger of every other enemy.

#### Acolyte — *Defensive Support* (keep as-is, add new skill)

```
New Skill: Profane Ward (replace Shield of Faith)
Type ......... Damage Reduction   Range ...... 3 tiles
Cooldown ..... 6 turns            Duration ... 3 turns  
Effect ...... Target ally takes 30% less damage for 3 turns
AI Impact ... Prioritizes warding the lowest-HP ally
Tactical .... Less dangerous than Dark Priest, but makes enemies tankier.
              Creates "do we kill the Acolyte to remove wards, or power through?"
```

**Identity:** Acolyte = defensive sustain. Heals and reduces incoming damage. Lower priority than Dark Priest but still extends fights significantly.

---

### Summary: Enemy Identity Matrix (Current → Proposed)

| Enemy | Current Skills | Proposed Addition | Tactical Identity |
|---|---|---|---|
| **Imp** | — | Frenzy Aura (pack buff) | Dangerous in numbers, weak alone. AoE check. |
| **Skeleton** | — | Bone Shield (damage absorb) | Break the shield, then burst. Rewards focus fire. |
| **Demon** | — | Enrage (low-HP damage buff) | Burn it fast or deal with a raging bruiser. |
| **Dark Priest** | Heal, Shield of Faith | Heal + **Dark Pact** (ally damage buff) | Kill-first priority — multiplies ally danger. |
| **Acolyte** | Heal, Shield of Faith | Heal + **Profane Ward** (damage reduction) | Sustain specialist — makes everything tankier. |
| **Wraith** | Wither, Shadow Step | *(keep as-is)* | DoT pressure + evasion. Already has identity. |
| **Medusa** | Venom Gaze, Power Shot | *(keep as-is)* | Poison + burst. Already has identity. |
| **Werewolf** | War Cry, Double Strike | *(keep as-is)* | Melee threat — War Cry is terrifying. |
| **Construct** | Ward | *(keep as-is)* | Damage sponge + reflect. Already has identity. |
| **Undead Knight** | — | *Future: Cleave (AoE melee)* | Boss frontliner. Punishes clustered parties. |
| **Reaper** | Wither, Soul Reap | *(keep as-is)* | Boss caster. Already the scariest enemy. |

### Priority Order for Implementation

1. **Demon — Enrage** (simplest — triggered passive, no targeting logic needed)
2. **Imp — Frenzy Aura** (passive aura, needs proximity check)
3. **Skeleton — Bone Shield** (self-buff, similar to existing Ward implementation)
4. **Dark Priest / Acolyte skill differentiation** (skill swap + new AI behavior)
5. **Undead Knight — Cleave** (new AoE melee pattern for bosses)

### Wave Arena Impact

The wave arena compositions in `wave_arena.json` will automatically benefit from these HP increases since they reference enemy types by ID. Wave 1 (2× Skeleton) goes from 120 total HP to 250. Wave 8 (2× Undead Knight + 2× Demon) goes from 640 to 1330. This should make later waves feel like real endurance tests.

### Balance Watch Items

- **Confessor sustain:** With enemies living 2-3× longer, Confessor healing (30 HP on CD 4, Prayer 32 over 4 turns) becomes much more valuable. Monitor whether Confessor feels mandatory.
- **Wither/DoT value increase:** Armor-bypassing DoT (Wither 24, Venom Gaze 15) scales up in relative value against higher-HP targets. Watch for Hexblade/Wraith being disproportionately strong.
- **Potion economy:** Health Potions (40 HP) and Greater Health Potions (75 HP) may need cost adjustments if fights are longer and more potion-intensive.
- **Gold income:** With enemies taking longer to kill, gold-per-minute drops. May need to increase `gold_per_enemy_kill` from 10 to 15-20 to maintain progression pace.
