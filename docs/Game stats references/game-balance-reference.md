# Arena — Game Balance Reference

> Comprehensive overview of all classes, skills, enemies, items, and combat mechanics.
> Generated for balancing & expansion planning.
> **Last updated:** February 24, 2026

---

## Balance Pass Changelog

### February 24, 2026 — Ranger/Inquisitor Tuning + Auto-Attack Buff

**Problem:** Damage was 95% ability / 5% auto-attack. Ranger and Inquisitor
dominated the damage meter — Power Shot was ~50% of Ranger's total damage,
Rebuke the Wicked was ~65% of Inquisitor's total damage.

**Changes applied:**

| Change | Before | After | Impact |
|--------|--------|-------|--------|
| Rebuke cooldown | 5 turns | **7 turns** | ~36% DPT reduction |
| Rebuke base damage | 28 | **24** | 24 vs normal, 36 vs tagged (was 28/42) |
| Power Shot cooldown | 5 turns | **7 turns** | ~25% DPT reduction for Ranger |
| Volley cooldown | 5 turns | **7 turns** | Reduced AoE spam frequency |
| Auto-attack melee multiplier | 1.0× | **1.15×** | +15% melee auto-attack for all melee classes |
| Auto-attack ranged multiplier | 1.0× | **1.15×** | +15% ranged auto-attack for Ranger |

**Expected outcome:** Longer cooldowns force more auto-attack ticks between
abilities, while the 1.15× auto-attack buff makes those ticks more meaningful.
Target ratio shifts from 95/5 → ~75-80/20 ability/auto-attack split.

### Phase 12 — Class Skill Expansion

- **Crusader**: Lost Double Strike + War Cry (burst DPS). Gained Taunt, Shield Bash,
  Holy Ground, Bulwark (full tank kit with CC, AoE heal, armor buff).
- **Ranger**: Gained Volley (AoE), Evasion (dodge), Crippling Shot (ranged + root).
  All 5 classes now have 4/4 skill slots filled.

---

## Table of Contents

1. [Combat Mechanics](#combat-mechanics)
2. [Player Classes](#player-classes)
3. [Skills / Abilities](#skills--abilities)
4. [Enemies / Monsters](#enemies--monsters)
5. [Items & Equipment](#items--equipment)
6. [Loot Tables](#loot-tables)
7. [Wave Arena Composition](#wave-arena-composition)
8. [Balance Observations & Gaps](#balance-observations--gaps)

---

## Combat Mechanics

```
Turn tick rate ........... 1 second
Base health (fallback) ... 100 HP
Base melee dmg (fallback)  15
Base ranged dmg (fallback) 10
Default ranged range ..... 5 tiles
Ranged cooldown .......... 3 turns
Armor reduction .......... 1 damage per armor point (flat)
Minimum damage ........... 1 (can never deal 0)
Default vision range ..... 7 tiles
Gold per enemy kill ...... 10g
Gold per boss kill ....... 50g
Gold dungeon clear bonus . 25g
```

### Damage Formula

```
Melee:  final = max(1, (base_melee + weapon_bonus) × buff_multiplier − (target_armor + armor_bonus))
Ranged: final = max(1, (base_ranged + weapon_bonus) × buff_multiplier − (target_armor + armor_bonus))
```

Armor is a **flat subtraction** — every point of armor reduces incoming damage by 1.

---

## Player Classes

### Crusader — Tank

```
HP ......... 150       Melee Dmg .. 20
Armor ...... 8         Ranged Dmg . 0
Vision ..... 5         Range ...... 0 (melee only)
Shape ...... Square    Color ...... Blue (#4a8fd0)
Skills ..... Taunt, Shield Bash, Holy Ground, Bulwark
```

Heavy-armored frontline warrior. Highest HP (150), highest melee damage (20),
highest armor (8), but zero ranged capability and the worst vision (5).
Full 4-skill tank kit: Taunt forces nearby enemies to target you, Shield Bash
stuns + deals 0.7× melee damage, Holy Ground provides AoE healing to adjacent
allies (15 HP), and Bulwark grants +8 armor for 4 turns. Pure frontline anchor.

---

### Confessor — Support

```
HP ......... 100       Melee Dmg .. 8
Armor ...... 3         Ranged Dmg . 0
Vision ..... 6         Range ...... 0 (melee only)
Shape ...... Circle    Color ...... Yellow (#f0e060)
Skills ..... Heal, Shield of Faith, Exorcism, Prayer
```

Divine support. Moderate HP, low damage, low armor. The primary healer with a full
4-skill kit: instant Heal, Prayer (HoT over 4 turns), Shield of Faith (+5 armor buff
on allies), and Exorcism (holy damage with ×2.0 bonus vs undead/demon). Excels at
sustaining the party while contributing meaningful damage against tagged enemies.

---

### Inquisitor — Scout

```
HP ......... 80        Melee Dmg .. 10
Armor ...... 4         Ranged Dmg . 8
Vision ..... 9         Range ...... 5
Shape ...... Triangle  Color ...... Purple (#a050f0)
Skills ..... Power Shot, Shadow Step, Divine Sense, Rebuke
```

Far-seeing demon hunter. Low HP, moderate damage split, decent armor, and the
**best vision in the game** (9 tiles). Full 4-skill kit: Power Shot for ranged burst,
Shadow Step for mobility, Rebuke for holy damage (28 base, ×1.5 vs undead/demon),
and Divine Sense to reveal tagged enemies in a 12-tile radius. Excels at detecting
and punishing undead/demon targets from range.

---

### Ranger — Ranged DPS

```
HP ......... 80        Melee Dmg .. 8
Armor ...... 2         Ranged Dmg . 18
Vision ..... 7         Range ...... 6
Shape ...... Diamond   Color ...... Green (#40c040)
Skills ..... Power Shot, Volley, Evasion, Crippling Shot
```

Dedicated ranged DPS. **Highest ranged damage** (18) with longest range (6 tiles).
Fragile — lowest armor (2). Full 4-skill kit: Power Shot for single-target burst
(1.8× ranged), Volley for AoE (0.5× ranged in 2-tile radius), Evasion to dodge
2 incoming attacks, and Crippling Shot (0.8× ranged + 2-turn root). Excels at
kiting and sustained ranged pressure.

---

### Hexblade — Hybrid DPS

```
HP ......... 110       Melee Dmg .. 15
Armor ...... 5         Ranged Dmg . 12
Vision ..... 6         Range ...... 4
Shape ...... Star      Color ...... Red (#e04040)
Skills ..... Double Strike, Shadow Step, Wither, Ward
```

Dark warrior hybrid. Good HP, strong across both melee and ranged, decent armor.
Full 4-skill kit: Double Strike for melee burst, Shadow Step for gap-close,
Wither (DoT curse dealing 8 dmg/turn × 4 turns = 32 total, refreshable), and Ward (3 charges
of 8 reflect damage). Opens fights with Ward + Wither at range, then closes to
melee. The reflect shield punishes attackers who engage in melee.

---

### Class Comparison (side-by-side)

```
                  HP    Melee  Ranged  Armor  Vision  Range  Skills
 Crusader ....   150      20       0      8       5      0     4/4 ✓
 Confessor ...   100       8       0      3       6      0     4/4 ✓
 Inquisitor ..    80      10       8      4       9      5     4/4 ✓
 Ranger ......    80       8      18      2       7      6     4/4 ✓
 Hexblade ....   110      15      12      5       6      4     4/4 ✓
```

### Auto-Attack Damage (1.15× multiplier)

```
 Crusader ....  20 × 1.15 = 23 melee per hit
 Confessor ...   8 × 1.15 =  9 melee per hit
 Inquisitor ..  10 × 1.15 = 12 melee per hit
 Ranger ......  18 × 1.15 = 21 ranged per hit
 Hexblade ....  15 × 1.15 = 17 melee per hit
```

### Effective DPS (per turn, no gear, vs. 0 armor)

```
 Crusader ....  23 auto-attack    Taunt (CD 5), Shield Bash → 14 + stun (CD 4),
                                  Holy Ground → 15 AoE heal (CD 5), Bulwark +8 armor (CD 5)
 Confessor ...   9 auto-attack    Heals 30 HP (CD 4), Prayer 8/turn×4, Exorcism 20 (40 vs tagged),
                                  Shield of Faith +5 armor (CD 5)
 Inquisitor ..  12 auto-attack    8 ranged (CD 0), Power Shot → 14 (CD 7),
                                  Rebuke 24 (36 vs tagged, CD 7), Shadow Step (CD 4)
 Ranger ......   8 melee / 21 ranged auto   Power Shot → 32 (CD 7), Volley AoE (CD 7),
                                             Evasion dodge 2 (CD 6), Crippling Shot (CD 5)
 Hexblade ....  17 auto-attack   12 ranged (CD 0), DS → 18, Wither 8/turn×4=32 total, Ward reflect
```

### Turns to Kill (auto-attack only, no gear, no skills, 1.15× multiplier)

**Attacker: Crusader (23 auto-attack)**
```
 vs Crusader (150hp / 8a) ... 10 turns (15 effective dmg/hit)
 vs Confessor (100hp / 3a) ..  5 turns (20 effective dmg/hit)
 vs Inquisitor (80hp / 4a) ..  5 turns (19 effective dmg/hit)
 vs Ranger (80hp / 2a) ......  4 turns (21 effective dmg/hit)
 vs Hexblade (110hp / 5a) ...  7 turns (18 effective dmg/hit)
```

**Attacker: Confessor (9 auto-attack)**
```
 vs Crusader (150hp / 8a) ... 150 turns ⚠ (1 effective dmg/hit — armor floor)
 vs Confessor (100hp / 3a) ..  17 turns (6 effective dmg/hit)
 vs Inquisitor (80hp / 4a) ..  16 turns (5 effective dmg/hit)
 vs Ranger (80hp / 2a) ......  12 turns (7 effective dmg/hit)
 vs Hexblade (110hp / 5a) ...  28 turns (4 effective dmg/hit)
```

**Attacker: Inquisitor (12 auto-attack)**
```
 vs Crusader (150hp / 8a) ...  38 turns (4 effective dmg/hit)
 vs Confessor (100hp / 3a) ..  12 turns (9 effective dmg/hit)
 vs Inquisitor (80hp / 4a) ..  10 turns (8 effective dmg/hit)
 vs Ranger (80hp / 2a) ......   8 turns (10 effective dmg/hit)
 vs Hexblade (110hp / 5a) ...  16 turns (7 effective dmg/hit)
```

**Attacker: Ranger (21 ranged auto-attack, 9 melee auto-attack)**
```
 Ranged:
 vs Crusader (150hp / 8a) ...  12 turns (13 effective dmg/hit)
 vs Confessor (100hp / 3a) ..   6 turns (18 effective dmg/hit)
 vs Inquisitor (80hp / 4a) ..   5 turns (17 effective dmg/hit)
 vs Ranger (80hp / 2a) ......   5 turns (19 effective dmg/hit)
 vs Hexblade (110hp / 5a) ...   7 turns (16 effective dmg/hit)

 Melee:
 vs Crusader (150hp / 8a) ... 150 turns ⚠ (1 effective dmg/hit — armor floor)
 vs Confessor (100hp / 3a) ..  17 turns (6 effective dmg/hit)
 vs Inquisitor (80hp / 4a) ..  16 turns (5 effective dmg/hit)
 vs Ranger (80hp / 2a) ......  12 turns (7 effective dmg/hit)
 vs Hexblade (110hp / 5a) ...  28 turns (4 effective dmg/hit)
```

**Attacker: Hexblade (17 auto-attack)**
```
 vs Crusader (150hp / 8a) ...  17 turns (9 effective dmg/hit)
 vs Confessor (100hp / 3a) ..   8 turns (14 effective dmg/hit)
 vs Inquisitor (80hp / 4a) ..   7 turns (13 effective dmg/hit)
 vs Ranger (80hp / 2a) ......   6 turns (15 effective dmg/hit)
 vs Hexblade (110hp / 5a) ...  10 turns (12 effective dmg/hit)
```

> **Note:** Confessor and Ranger deal only 1 damage per melee hit to Crusader
> (8 dmg − 8 armor = min 1). This highlights the flat armor scaling issue.

---

## Skills / Abilities

### Heal 💚

```
Type ......... Support           Targeting .. Ally or Self
Range ........ 3 tiles           Cooldown ... 4 turns
Mana Cost .... 0                 LOS Req .... No
Effect ....... Heal 30 HP
Classes ...... Confessor
```

---

### Double Strike ⚔️⚔️

```
Type ......... Melee Attack      Targeting .. Adjacent enemy
Range ........ 1 (melee)         Cooldown ... 3 turns
Mana Cost .... 0                 LOS Req .... No
Effect ....... 2 hits × 60% melee damage each
Classes ...... Hexblade
```

Damage by user:
```
 Hexblade:  2 × (15 × 0.6) = 18 total
```

---

### Power Shot 🎯

```
Type ......... Ranged Attack     Targeting .. Enemy (ranged)
Range ........ Class range       Cooldown ... 7 turns
Mana Cost .... 0                 LOS Req .... Yes
Effect ....... 1.8× ranged damage
Classes ...... Ranger, Inquisitor
```

Damage by user:
```
 Ranger:      18 × 1.8 = 32 damage
 Inquisitor:   8 × 1.8 = 14 damage
```

---

### War Cry 📯

```
Type ......... Self Buff         Targeting .. Self
Range ........ 0                 Cooldown ... 5 turns
Mana Cost .... 0                 LOS Req .... No
Effect ....... 2× melee damage for 2 turns
Classes ...... (Enemy only: Werewolf)
```

With War Cry active: Werewolf melee = 22 × 2.0 = **44 damage per hit**

---

### Shadow Step 👤

```
Type ......... Mobility          Targeting .. Empty tile
Range ........ 3 tiles           Cooldown ... 4 turns
Mana Cost .... 0                 LOS Req .... Yes
Effect ....... Teleport to target tile
Classes ...... Hexblade, Inquisitor
```

---

### Wither 🩸 (Phase 11)

```
Type ......... DoT Curse         Targeting .. Enemy (ranged)
Range ........ 4 tiles           Cooldown ... 6 turns
Mana Cost .... 0                 LOS Req .... Yes
Effect ....... 8 damage per turn for 4 turns (32 total, ignores armor)
Classes ...... Hexblade
```

Damage bypasses armor since it ticks as a debuff. Recasting on an already-affected
target **refreshes the duration** (resets to 4 turns) instead of failing.
Hexblade AI targets the highest-HP enemy without an existing Wither.

---

### Ward 🛡️ (Phase 11)

```
Type ......... Shield (Charges)  Targeting .. Self
Range ........ 0                 Cooldown ... 6 turns
Mana Cost .... 0                 LOS Req .... No
Effect ....... 3 charges; each charge reflects 8 damage to melee/ranged attacker
Classes ...... Hexblade
```

Total reflect potential: 3 × 8 = **24 damage** reflected back. Charges are consumed
on hit (one per attack), and expire when all charges are used or duration ends.
Reflect damage can kill the attacker.

---

### Rebuke the Wicked ⚔️✨ (Phase 11)

```
Type ......... Holy Damage       Targeting .. Enemy (ranged)
Range ........ 6 tiles           Cooldown ... 7 turns
Mana Cost .... 0                 LOS Req .... Yes
Effect ....... 24 base damage; ×1.5 vs Undead/Demon (36 damage)
Classes ...... Inquisitor
```

Damage vs. armor tiers:
```
                    vs 0 Armor   vs 4 Armor   vs 8 Armor   vs 10 Armor
 vs Normal ......      24           20           16            14
 vs Undead/Demon       36           32           28            26
```

---

### Divine Sense 👁️ (Phase 11)

```
Type ......... Detection         Targeting .. Self
Range ........ 0 (12-tile radius) Cooldown .. 7 turns
Mana Cost .... 0                 LOS Req .... No
Effect ....... Reveals all Undead/Demon enemies within 12-tile radius for 4 turns
Classes ...... Inquisitor
```

Applies a "detected" buff to matching enemies. Pairs with Inquisitor’s 9-tile
vision for map-wide awareness. AI uses this when no enemies are currently visible.

---

### Shield of Faith ✨ (Phase 11)

```
Type ......... Armor Buff        Targeting .. Ally or Self
Range ........ 3 tiles           Cooldown ... 5 turns
Mana Cost .... 0                 LOS Req .... No
Effect ....... +5 armor for 3 turns
Classes ...... Confessor
```

Stacks with base armor and equipment armor via the generic stat pipeline.
Effective armor increase by class:
```
 Crusader (8 base) → 13 armor   (melee becomes near-immune to low-dmg)
 Confessor (3 base) → 8 armor   (reaches Crusader-level protection)
 Inquisitor (4 base) → 9 armor  (survives melee encounters)
 Ranger (2 base) → 7 armor      (major survivability boost)
 Hexblade (5 base) → 10 armor   (Undead Knight-level protection)
```

---

### Exorcism ✝️ (Phase 11)

```
Type ......... Holy Damage       Targeting .. Enemy (ranged)
Range ........ 5 tiles           Cooldown ... 4 turns
Mana Cost .... 0                 LOS Req .... Yes
Effect ....... 20 base damage; ×2.0 vs Undead/Demon (40 damage)
Classes ...... Confessor
```

Lower base than Rebuke but higher bonus multiplier and shorter cooldown.
Damage vs. armor tiers:
```
                    vs 0 Armor   vs 4 Armor   vs 8 Armor   vs 10 Armor
 vs Normal ......      20           16           12            10
 vs Undead/Demon       40           36           32            30
```

---

### Prayer 🙏 (Phase 11)

```
Type ......... HoT (Heal over Time) Targeting . Ally or Self
Range ........ 4 tiles           Cooldown ... 6 turns
Mana Cost .... 0                 LOS Req .... No
Effect ....... Heals 8 HP per turn for 4 turns (32 total)
Classes ...... Confessor
```

More total healing than Heal (32 vs 30) but spread over 4 turns.
Does not stack on the same target. AI uses Prayer when Heal is on cooldown.

---

### Taunt 🗣️ (Phase 12)

```
Type ......... Crowd Control     Targeting .. Self (AoE)
Range ........ 2 tiles (radius)  Cooldown ... 5 turns
Mana Cost .... 0                 LOS Req .... No
Effect ....... Force all enemies within 2 tiles to target you for 2 turns
Classes ...... Crusader
```

Core tank skill. Forces nearby enemies to attack the Crusader, protecting
squishier party members. Crusader's high HP (150) and armor (8) make this
sustainable. Pairs with Bulwark (+8 armor) for massive effective HP.

---

### Shield Bash 🛡️💥 (Phase 12)

```
Type ......... Melee + Stun      Targeting .. Adjacent enemy
Range ........ 1 (melee)         Cooldown ... 4 turns
Mana Cost .... 0                 LOS Req .... No
Effect ....... 0.7× melee damage + stun target for 1 turn
Classes ...... Crusader
```

Damage by user:
```
 Crusader:  20 × 0.7 = 14 damage + 1-turn stun
```

Lower damage than auto-attack but the stun is invaluable — prevents an enemy
from acting for 1 full turn. Best used on high-damage targets (Werewolf, Reaper).

---

### Holy Ground ✝️ (Phase 12)

```
Type ......... AoE Heal          Targeting .. Self (AoE)
Range ........ 1 tile (radius)   Cooldown ... 5 turns
Mana Cost .... 0                 LOS Req .... No
Effect ....... Heal all allies within 1 tile for 15 HP
Classes ...... Crusader
```

Gives the Crusader off-healer capability. Heals all adjacent allies for 15 HP
each. Less potent than Confessor's Heal (30 HP single-target) but hits multiple
allies simultaneously. Encourages tight formation play.

---

### Bulwark 🏰 (Phase 12)

```
Type ......... Self Buff         Targeting .. Self
Range ........ 0                 Cooldown ... 5 turns
Mana Cost .... 0                 LOS Req .... No
Effect ....... +8 armor for 4 turns
Classes ...... Crusader
```

Massive armor buff. Crusader (8 base) → 16 armor, reducing incoming damage
by 16 per hit. At 16 armor, most enemies deal minimum damage (1 per hit).
Combined with Shield of Faith from a Confessor (+5 more), Crusader can reach
21 armor for near-total melee immunity.

---

### Volley 🏹🌧️ (Phase 12)

```
Type ......... AoE Ranged        Targeting .. Ground (AoE)
Range ........ 5 tiles           Cooldown ... 7 turns
Mana Cost .... 0                 LOS Req .... Yes
Effect ....... 0.5× ranged damage to all enemies within 2-tile radius
Classes ...... Ranger
```

Damage by user:
```
 Ranger:  18 × 0.5 = 9 damage per enemy hit
```

The game's first player AoE damage skill. Hits all enemies in a 2-tile radius.
Against 3+ enemies, total damage output exceeds Power Shot. Pairs well with
Crusader's Taunt to cluster enemies for maximum hits.

---

### Evasion 💨 (Phase 12)

```
Type ......... Dodge (Charges)   Targeting .. Self
Range ........ 0                 Cooldown ... 6 turns
Mana Cost .... 0                 LOS Req .... No
Effect ....... Dodge the next 2 attacks. Lasts up to 4 turns.
Classes ...... Ranger
```

Defensive survival tool. Ranger's low HP (80) and armor (2) make this critical.
2 dodge charges can nullify 2 incoming attacks entirely — potentially saving
40-80+ damage. Best activated when enemies are closing to melee range.

---

### Crippling Shot 🦵🏹 (Phase 12)

```
Type ......... Ranged + Root     Targeting .. Enemy (ranged)
Range ........ Class range       Cooldown ... 5 turns
Mana Cost .... 0                 LOS Req .... Yes
Effect ....... 0.8× ranged damage + root target for 2 turns (cannot move)
Classes ...... Ranger
```

Damage by user:
```
 Ranger:  18 × 0.8 = 14 damage + 2-turn root
```

Kiting enabler. Roots a target in place for 2 turns, giving the Ranger time
to maintain distance. Effective against charging melee threats (Demon, Werewolf,
Crusader). Lower damage than Power Shot but the CC is worth the trade.

---

### Venom Gaze 🐍 (Enemy Skill)

```
Type ......... DoT (Poison)      Targeting .. Enemy (ranged)
Range ........ 4 tiles           Cooldown ... 5 turns
Mana Cost .... 0                 LOS Req .... Yes
Effect ....... 5 poison damage per turn for 3 turns (15 total, ignores armor)
Classes ...... Medusa (enemy only)
```

Weaker than Wither (15 total vs 24) but with shorter cooldown and longer range.
AI targets the highest-HP enemy without an existing Venom Gaze DoT.

---

### Soul Reap 💀 (Enemy Skill)

```
Type ......... Ranged Attack     Targeting .. Enemy (ranged)
Range ........ 4 tiles           Cooldown ... 4 turns
Mana Cost .... 0                 LOS Req .... Yes
Effect ....... 2.0× ranged damage
Classes ...... Reaper (enemy only)
```

Damage: Reaper (15 ranged) × 2.0 = **30 damage per cast**. Compare to Power Shot
(Ranger 32, Inquisitor 14). Combined with Wither DoT, the Reaper deals massive
sustained + burst damage at range.

---

### Skill Allocation Per Class

**Player Classes:**
```
 Crusader ....  Taunt, Shield Bash, Holy Ground,
                Bulwark .............................. 4 / 4 slots ✓
 Confessor ...  Heal, Shield of Faith, Exorcism, Prayer  4 / 4 slots ✓
 Inquisitor ..  Power Shot, Shadow Step, Divine Sense,
                Rebuke ............................... 4 / 4 slots ✓
 Ranger ......  Power Shot, Volley, Evasion,
                Crippling Shot ....................... 4 / 4 slots ✓
 Hexblade ....  Double Strike, Shadow Step, Wither,
                Ward ................................. 4 / 4 slots ✓
```

**Enemy Classes (spellcasting enemies):**
```
 Wraith ......  Wither, Shadow Step .................... 2 skills
 Medusa ......  Venom Gaze, Power Shot ................. 2 skills
 Acolyte .....  Heal, Shield of Faith .................. 2 skills
 Werewolf ....  War Cry, Double Strike ................. 2 skills
 Reaper ......  Wither, Soul Reap ...................... 2 skills
 Construct ...  Ward ................................... 1 skill
 Necromancer .  Wither, Soul Reap ...................... 2 skills  (Phase 13)
 Demon Lord ..  War Cry, Double Strike ................. 2 skills  (Phase 13)
 Const. Guard.  Ward, Bulwark .......................... 2 skills  (Phase 13)
 Und. Knight .  Shield Bash, Bulwark ................... 2 skills  (Phase 13)
 Demon Knight  War Cry ................................ 1 skill   (Phase 13)
 Imp Lord ....  War Cry ................................ 1 skill   (Phase 13)
 Horror ......  Shadow Step, Wither .................... 2 skills  (Phase 13)
 Ghoul .......  Double Strike .......................... 1 skill   (Phase 13)
 Skeleton ....  Evasion ................................ 1 skill   (Phase 13)
 Und. Caster .  Wither ................................. 1 skill   (Phase 13)
 Shade .......  Shadow Step ............................ 1 skill   (Phase 13)
```

Total: 17/22 enemies with skills (was 6/22 pre-Phase 13)

### Skill Damage vs. Armor Tiers

```
                              vs 0 Armor   vs 4 Armor   vs 8 Armor  vs 10 Armor
 Auto-Attack Melee (Crus) .       23            19           15         13
 Auto-Attack Melee (Hex) ..       17            13            9          7
 Auto-Attack Ranged (Ranger)      21            17           13         11
 Double Strike (Hexblade)         18            10            2          2 (min)
 Double Strike (Werewolf)         26            18           10          6
 Power Shot (Ranger) ....         32            28           24         22
 Power Shot (Inquisitor)          14            10            6          4
 Power Shot (Medusa) ....         22            18           14         12
 Shield Bash (Crusader) ..        14            10            6          4
 Crippling Shot (Ranger) .        14            10            6          4
 Volley per target (Ranger)        9             5            1          1 (min)
 War Cry + Melee (Werewolf)       44            40           36         34
 Soul Reap (Reaper) .....         30            26           22         20
 Rebuke (Inquisitor) ....         24            20           16         14
 Rebuke vs Tagged .......         36            32           28         26
 Exorcism (Confessor) ...         20            16           12         10
 Exorcism vs Tagged .....         40            36           32         30
 Wither (DoT, 4 turns) ..         24*           24*          24*        24*
 Venom Gaze (DoT, 3 turns)       15*           15*          15*        15*
 Ward Reflect (3 charges)         24†           24†          24†        24†
```

\* Wither bypasses armor (DoT ticks ignore armor reduction).
† Ward total reflect = 3 charges × 8 damage. Reflect also ignores armor.

---

## Enemies / Monsters

### Demon — Melee Bruiser

```
HP ......... 240       Melee Dmg .. 18
Armor ...... 5         Ranged Dmg . 0
Vision ..... 5         Range ...... 1 (melee only)
AI ......... Aggressive          Boss ....... No
Color ...... Red (#cc3333)       Shape ...... Diamond
Tags ....... demon
```

Ferocious melee attacker. Charges into close range and mauls targets.
Comparable to a Hexblade in stats but melee-only.
Vulnerable to Rebuke (×1.5) and Exorcism (×2.0) holy damage.

---

### Skeleton — Ranged Sniper

```
HP ......... 125       Melee Dmg .. 6
Armor ...... 2         Ranged Dmg . 14
Vision ..... 7         Range ...... 5
AI ......... Ranged               Boss ....... No
Color ...... Gray (#c8c8c8)      Shape ...... Triangle
Tags ....... undead
Class ID ... skeleton              Skills ..... Evasion
```

Fragile but deadly at range. Keeps distance and peppers targets with arrows.
Glass cannon — low HP and armor make it easy to burst down. Evasion lets it
dodge 2 incoming attacks, making it annoying to trade with at range.
Vulnerable to Rebuke (×1.5) and Exorcism (×2.0) holy damage.

---

### Undead Knight — Boss (Room Guardian)

```
HP ......... 425       Melee Dmg .. 25
Armor ...... 12        Ranged Dmg . 0
Vision ..... 6         Range ...... 1 (melee only)
AI ......... Boss                 Boss ....... Yes
Color ...... Purple (#6633aa)    Shape ...... Star
Tags ....... undead
Class ID ... undead_knight         Skills ..... Shield Bash, Bulwark
```

Heavily armored undead lord. Guards its throne room and crushes intruders.
12 armor makes it nearly immune to low-damage attackers. Shield Bash deals
17.5 damage + 1-turn stun. Bulwark pushes armor to 20, making it nearly
impervious. Combined stun + armor wall makes this a terrifying room guardian.
Vulnerable to Rebuke (×1.5) and Exorcism (×2.0) holy damage.
Wither DoT bypasses its armor entirely (24 guaranteed damage).

---

### Imp — Swarm (Phase 11)

```
HP ......... 70        Melee Dmg .. 8
Armor ...... 1         Ranged Dmg . 0
Vision ..... 6         Range ...... 1 (melee only)
AI ......... Aggressive          Boss ....... No
Color ...... Orange (#ff6644)    Shape ...... Triangle
Tags ....... demon
```

Frail but dangerous in numbers. Minimal armor means nearly every attack deals
full damage. Appears in groups of 4–6 to swarm melee fighters. Ideal targets
for Ward reflect (8 reflect damage kills an Imp in ~9 hits).
Vulnerable to Rebuke (×1.5) and Exorcism (×2.0) holy damage.

---

### Dark Priest — Enemy Support (Phase 11)

```
HP ......... 170       Melee Dmg .. 6
Armor ...... 4         Ranged Dmg . 10
Vision ..... 7         Range ...... 5
AI ......... Support              Boss ....... No
Color ...... Purple (#8844aa)    Shape ...... Circle
Tags ....... undead
Class ID ... acolyte              Skills ..... Heal, Shield of Faith
```

Enemy healer/support unit. Uses Heal to restore wounded allies and Shield of Faith
to buff their armor. Stays at range, retreats from melee, and falls back to ranged
attacks. Priority target — kill it before it sustains the rest of the pack.
Vulnerable to Rebuke (×1.5) and Exorcism (×2.0) holy damage.

---

### Wraith — Caster DPS

```
HP ......... 145       Melee Dmg .. 10
Armor ...... 3         Ranged Dmg . 0
Vision ..... 7         Range ...... 1 (melee only)
AI ......... Aggressive          Boss ....... No
Color ...... Blue (#6699cc)      Shape ...... Diamond
Tags ....... undead
Class ID ... wraith               Skills ..... Wither, Shadow Step
```

Spectral undead that phases through combat, cursing targets with withering decay
and vanishing before retaliation. Opens with Wither (6 dmg/turn × 4 turns = 24
armor-bypassing damage) then uses Shadow Step to reposition. Low HP and armor
make it fragile if caught, but its DoT pressure forces the party to prioritize it.
Vulnerable to Rebuke (×1.5) and Exorcism (×2.0) holy damage.

---

### Medusa — Debuff Caster

```
HP ......... 180       Melee Dmg .. 8
Armor ...... 4         Ranged Dmg . 12
Vision ..... 7         Range ...... 5
AI ......... Ranged               Boss ....... No
Color ...... Green (#44aa66)     Shape ...... Circle
Tags ....... beast
Class ID ... medusa               Skills ..... Venom Gaze, Power Shot
```

Serpentine horror whose venomous gaze poisons from afar. Leads with Venom Gaze
(5 dmg/turn × 3 turns = 15 armor-bypassing damage) then follows up with Power
Shot (12 × 1.8 = 21.6 ranged burst). Stays at range and kites. The `beast` tag
means holy damage bonuses do NOT apply — Rebuke and Exorcism deal normal damage.

---

### Acolyte — Enemy Support

```
HP ......... 150       Melee Dmg .. 6
Armor ...... 3         Ranged Dmg . 0
Vision ..... 6         Range ...... 1 (melee only)
AI ......... Support              Boss ....... No
Color ...... Pink (#aa4488)      Shape ...... Circle
Tags ....... demon
Class ID ... acolyte              Skills ..... Heal, Shield of Faith
```

Dark ritualist that mends demonic allies and shields them with profane wards. Uses
Heal (30 HP, CD 4) to restore wounded allies and Shield of Faith (+5 armor, 3 turns)
to buff their defenses. Kill it first or the fight never ends. Support AI prioritizes
healing, retreats from melee combat, and stays near injured allies.
Vulnerable to Rebuke (×1.5) and Exorcism (×2.0) holy damage.

---

### Werewolf — Melee Elite

```
HP ......... 290       Melee Dmg .. 22
Armor ...... 6         Ranged Dmg . 0
Vision ..... 6         Range ...... 1 (melee only)
AI ......... Aggressive          Boss ....... No
Color ...... Brown (#8B6914)     Shape ...... Diamond
Tags ....... beast
Class ID ... werewolf             Skills ..... War Cry, Double Strike
```

Savage beast that howls before unleashing a flurry of claw strikes. Toughest
non-boss regular enemy — 290 HP exceeds every hero class. War Cry doubles its
melee to 44 damage for 2 turns; Double Strike deals 2 × (22 × 0.6) = 26.4 burst.
The combination makes it extremely dangerous in melee. The `beast` tag means
holy damage bonuses do NOT apply.

---

### Reaper — Boss (Death Caster)

```
HP ......... 525       Melee Dmg .. 20
Armor ...... 10        Ranged Dmg . 15
Vision ..... 7         Range ...... 4
AI ......... Boss                 Boss ....... Yes
Color ...... Dark (#1a1a2e)      Shape ...... Star
Tags ....... undead
Class ID ... reaper               Skills ..... Wither, Soul Reap
```

Hooded harbinger of death. Curses victims with Wither (6 dmg/turn × 4 turns = 24
armor-bypassing damage) and reaps souls with Soul Reap (15 × 2.0 = 30 ranged
damage, range 4). With 525 HP and 10 armor, it's extraordinarily tanky and deals
damage at range. Unlike the Undead Knight, the Reaper has both strong melee (20)
AND ranged capability (15 base + skills).
Vulnerable to Rebuke (×1.5) and Exorcism (×2.0) holy damage.
Wither DoT bypasses its armor entirely (24 guaranteed damage from Hexblade).

---

### Construct — Tank

```
HP ......... 320       Melee Dmg .. 14
Armor ...... 10        Ranged Dmg . 0
Vision ..... 4         Range ...... 1 (melee only)
AI ......... Aggressive          Boss ....... No
Color ...... Gray (#7a7a8a)      Shape ...... Square
Tags ....... construct
Class ID ... construct            Skills ..... Ward
```

Animated stone guardian with impenetrable armor. Uses Ward (3 charges × 8 reflect
damage = 24 potential reflect) to punish attackers. With 10 armor and 320 HP, it's
a wall that low-damage classes struggle against. The `construct` tag means holy
damage bonuses do NOT apply — Rebuke and Exorcism deal normal damage. Slow
(vision 4) but nearly indestructible without DoT or high-damage skills.

---

### Imp Lord — Elite Imp Commander *(NEW)*

```
HP ......... 180       Melee Dmg .. 16
Armor ...... 4         Ranged Dmg . 0
Vision ..... 6         Range ...... 1 (melee only)
AI ......... Aggressive          Boss ....... No
Color ...... Dark Orange (#cc4400) Shape .... Star
Tags ....... demon
Class ID ... imp_lord              Skills ..... War Cry
```

A towering imp chieftain wreathed in hellfire. Commands lesser imps with a
rallying war cry that doubles its fury. War Cry → 32 melee damage for 2 turns.
Tougher than a standard Imp (180 HP vs 70) with double the melee damage.

---

### Demon Lord — Boss (Demon Overlord) *(NEW)*

```
HP ......... 480       Melee Dmg .. 28
Armor ...... 9         Ranged Dmg . 0
Vision ..... 6         Range ...... 1 (melee only)
AI ......... Boss                 Boss ....... Yes
Color ...... Crimson (#991111)   Shape ...... Star
Tags ....... demon
Class ID ... demon_lord            Skills ..... War Cry, Double Strike
```

A colossal demon warlord radiating malice. The apex predator of demonkind.
War Cry doubles melee to 56 damage per hit for 2 turns. Double Strike deals
2 × (28 × 0.6) = 33.6 burst damage. Highest melee damage of any enemy,
now with abilities to match. Pair Crusader Taunt + Bulwark to survive its onslaught.

---

### Demon Knight — Armored Demon Elite *(NEW)*

```
HP ......... 260       Melee Dmg .. 20
Armor ...... 8         Ranged Dmg . 0
Vision ..... 5         Range ...... 1 (melee only)
AI ......... Aggressive          Boss ....... No
Color ...... Dark Red (#aa2222)  Shape ...... Diamond
Tags ....... demon
Class ID ... demon_knight          Skills ..... War Cry
```

A demon clad in blackened plate armor. Rallies with a war cry before cleaving
through defenses with doubled fury. War Cry → 40 melee damage for 2 turns.
Compared to the base Demon (240 HP, 5 armor), the Demon Knight trades some HP
for significantly more armor (8 vs 5) and stronger melee (20 vs 18).

---

### Construct Guardian — Boss (Arcane Construct) *(NEW)*

```
HP ......... 550       Melee Dmg .. 22
Armor ...... 14        Ranged Dmg . 0
Vision ..... 5         Range ...... 1 (melee only)
AI ......... Boss                 Boss ....... Yes
Color ...... Dark Gray (#5a5a6a) Shape ...... Star
Tags ....... construct
Class ID ... construct_guardian    Skills ..... Ward, Bulwark
```

A massive arcane automaton forged to guard ancient vaults. The tankiest enemy in the
game — 550 HP and 14 armor. Ward reflects 24 total damage back at attackers. Bulwark
pushes armor to 22, making nearly every attack deal minimum damage (1 per hit).
Requires DoT (Wither), high-damage skills, or sustained ranged pressure to bring down.

---

### Ghoul — Fast Undead *(NEW)*

```
HP ......... 100       Melee Dmg .. 14
Armor ...... 2         Ranged Dmg . 0
Vision ..... 6         Range ...... 1 (melee only)
AI ......... Aggressive          Boss ....... No
Color ...... Sickly Green (#66aa77) Shape ... Triangle
Tags ....... undead
Class ID ... ghoul                 Skills ..... Double Strike
```

A ravenous undead horror that strikes with terrifying speed. Frail but relentless —
hits harder than Skeletons or Acolytes at 14 melee damage despite only 100 HP.
Double Strike deals 2 × (14 × 0.6) = 16.8 burst damage for a frenzied feel.
Vulnerable to Rebuke (×1.5) and Exorcism (×2.0) holy damage.

---

### Necromancer — Boss (Death Mage) *(NEW)*

```
HP ......... 380       Melee Dmg .. 8
Armor ...... 6         Ranged Dmg . 16
Vision ..... 7         Range ...... 5
AI ......... Boss                 Boss ....... Yes
Color ...... Deep Purple (#442266) Shape .... Star
Tags ....... undead
Class ID ... necromancer           Skills ..... Wither, Soul Reap
```

A master of dark sorcery who commands the dead. Curses victims with Wither
(6 dmg/turn × 4 turns = 24 armor-bypassing damage) and reaps souls with
Soul Reap (16 × 2.0 = 32 ranged burst). The scariest ranged caster boss —
higher ranged damage than the Reaper (16 vs 15) with the same deadly skill kit.
Vulnerable to Rebuke (×1.5) and Exorcism (×2.0) holy damage.

---

### Undead Caster — Skeleton Mage *(NEW)*

```
HP ......... 120       Melee Dmg .. 6
Armor ...... 2         Ranged Dmg . 16
Vision ..... 7         Range ...... 5
AI ......... Ranged               Boss ....... No
Color ...... Pale Purple (#9966bb) Shape .... Triangle
Tags ....... undead
Class ID ... undead_caster         Skills ..... Wither
```

A reanimated sorcerer that hurls bolts of necrotic energy and curses targets
with withering decay from afar. Comparable to a Skeleton but with stronger
ranged damage (16 vs 14) and Wither DoT (24 armor-bypassing damage over 4 turns).
Fragile — rush it down before its sustained output adds up.
Vulnerable to Rebuke (×1.5) and Exorcism (×2.0) holy damage.

---

### Horror — Eldritch Aberration *(NEW)*

```
HP ......... 240       Melee Dmg .. 18
Armor ...... 6         Ranged Dmg . 0
Vision ..... 5         Range ...... 1 (melee only)
AI ......... Aggressive          Boss ....... No
Color ...... Eldritch Purple (#553366) Shape . Diamond
Tags ....... aberration
Class ID ... horror                Skills ..... Shadow Step, Wither
Variants ... 2 (Horror_1, Horror_2)
```

A writhing mass of tentacles and malice from beyond the veil. Stat-wise comparable
to the Demon (same HP and melee) but with more armor (6 vs 5). Teleports through
shadows with Shadow Step and curses victims with Wither (24 armor-bypassing DoT).
The most terrifying non-boss enemy — a tankier Wraith with the same deadly kit.

---

### Insectoid — Bug Swarm *(NEW)*

```
HP ......... 80        Melee Dmg .. 12
Armor ...... 3         Ranged Dmg . 0
Vision ..... 6         Range ...... 1 (melee only)
AI ......... Aggressive          Boss ....... No
Color ...... Yellow-Green (#889922) Shape ... Triangle
Tags ....... beast
Variants ... 2 (Insectoid_1, Insectoid_2)
```

A chitinous insect creature that attacks in skittering packs. Individually
moderate — tougher than Imps (80 HP, 3 armor) with respectable melee damage (12).
Best treated like a sturdier swarm unit. The `beast` tag means holy damage
bonuses do NOT apply.

---

### Dark Caster — Generic Mage *(NEW)*

```
HP ......... 100       Melee Dmg .. 6
Armor ...... 2         Ranged Dmg . 14
Vision ..... 7         Range ...... 5
AI ......... Ranged               Boss ....... No
Color ...... Orange (#cc6600)    Shape ...... Circle
Tags ....... (none)
Variants ... 2 (Caster_1, Caster_2)
```

A robed spellcaster channeling destructive magic from a safe distance. Stat-wise
identical to the Skeleton in damage output (14 ranged, 6 melee) but with slightly
lower HP (100 vs 125). No creature tags mean it is NOT vulnerable to any bonus
damage — neither holy, nor any future type-specific multipliers.

---

### Evil Snail — Armored Pest *(NEW)*

```
HP ......... 60        Melee Dmg .. 10
Armor ...... 6         Ranged Dmg . 0
Vision ..... 3         Range ...... 1 (melee only)
AI ......... Aggressive          Boss ....... No
Color ...... Green (#77aa44)     Shape ...... Circle
Tags ....... beast
```

A surprisingly dangerous gastropod with a rock-hard shell. Lowest vision in the
game (3 tiles) — extremely slow to react. But 6 armor on only 60 HP makes it
disproportionately tanky for its tier. Low-damage classes struggle against its
shell. The `beast` tag means holy damage bonuses do NOT apply. A novelty encounter.

---

### Goblin Spearman — Humanoid Fodder *(NEW)*

```
HP ......... 90        Melee Dmg .. 12
Armor ...... 3         Ranged Dmg . 0
Vision ..... 6         Range ...... 1 (melee only)
AI ......... Aggressive          Boss ....... No
Color ...... Goblin Green (#668833) Shape ... Triangle
Tags ....... humanoid
```

A scrawny goblin wielding a crude spear. Individually unremarkable — 90 HP with
12 melee is below-average. But in groups they can pressure fragile ranged classes.
The `humanoid` tag is a new creature category; holy damage bonuses do NOT apply.

---

### Shade — Shadow Creature *(NEW)*

```
HP ......... 130       Melee Dmg .. 14
Armor ...... 3         Ranged Dmg . 0
Vision ..... 7         Range ...... 1 (melee only)
AI ......... Aggressive          Boss ....... No
Color ...... Dark Blue-Gray (#334455) Shape .. Diamond
Tags ....... undead
Class ID ... shade                 Skills ..... Shadow Step
```

A flickering shadow given terrible form. Phases through space with Shadow Step
to strike from unexpected angles. With 130 HP and 14 melee damage it sits
between the Ghoul and Wraith in power — a solid mid-tier undead melee threat.
Vulnerable to Rebuke (×1.5) and Exorcism (×2.0) holy damage.

---

### Enemy Tier Overview

```
 TIER         Enemies                                             HP Range    Armor Range
 ──────────   ──────────────────────────────────────────────────   ─────────   ───────────
 Swarm        Imp, Evil Snail, Insectoid                           60–80       0–6
 Fodder       Goblin Spearman, Ghoul, Dark Caster, Undead Caster,
              Skeleton, Shade                                      90–130      2–3
 Mid          Wraith, Acolyte, Dark Priest, Imp Lord, Medusa       145–180     3–4
 Elite        Demon, Horror, Demon Knight, Werewolf, Construct     240–320     5–10
 Boss         Necromancer, Undead Knight, Demon Lord, Reaper,
              Construct Guardian                                   380–550     6–14
```

---

### Enemy vs. Class Comparison

```
                    HP    Melee  Ranged  Armor  Vision Tags         AI          Skills
 Imp ..........     70      8       0      1     6    demon        Aggressive  —
 Evil Snail ...     60     10       0      6     3    beast        Aggressive  —
 Insectoid ....     80     12       0      3     6    beast        Aggressive  —
 Goblin Spear .     90     12       0      3     6    humanoid     Aggressive  —
 Ghoul ........    100     14       0      2     6    undead       Aggressive  Double Strike
 Dark Caster ..    100      6      14      2     7    (none)       Ranged      —
 Undead Caster     120      6      16      2     7    undead       Ranged      Wither
 Skeleton .....    125      6      14      2     7    undead       Ranged      Evasion
 Shade ........    130     14       0      3     7    undead       Aggressive  Shadow Step
 Wraith .......    145     10       0      3     7    undead       Aggressive  Wither, Shadow Step
 Acolyte ......    150      6       0      3     6    demon        Support     Heal, Shield of Faith
 Construct ....    320     14       0     10     4    construct    Aggressive  Ward
 Dark Priest ..    170      6      10      4     7    undead       Support     Heal, Shield of Faith
 Imp Lord .....    180     16       0      4     6    demon        Aggressive  War Cry
 Medusa .......    180      8      12      4     7    beast        Ranged      Venom Gaze, Power Shot
 Horror .......    240     18       0      6     5    aberration   Aggressive  Shadow Step, Wither
 Demon ........    240     18       0      5     5    demon        Aggressive  —
 Demon Knight .    260     20       0      8     5    demon        Aggressive  War Cry
 Werewolf .....    290     22       0      6     6    beast        Aggressive  War Cry, Double Strike
 Necromancer ..    380      8      16      6     7    undead       Boss        Wither, Soul Reap
 Und. Knight ..    425     25       0     12     6    undead       Boss        Shield Bash, Bulwark
 Demon Lord ...    480     28       0      9     6    demon        Boss        War Cry, Double Strike
 Reaper .......    525     20      15     10     7    undead       Boss        Wither, Soul Reap
 Const. Guard .    550     22       0     14     5    construct    Boss        Ward, Bulwark
```

### Turns for Each Class to Kill Each Enemy (auto-attack only, 1.15×, no gear)

Organized by enemy tier. Formula: `ceil(HP / max(1, auto_attack − armor))`.

**Swarm Tier (Imp, Evil Snail, Insectoid)**
```
                        vs Imp      vs Evil Snail  vs Insectoid
                        70/1a       60/6a          80/3a
 Crusader (23 melee) ..  4           4              4
 Confessor (9 melee) ..  9          20             14
 Inquisitor (12 melee)   7          10              9
 Ranger (21 ranged) ...  4           4              5
 Hexblade (17 melee) ..  5           6              6
```

**Fodder Tier (Goblin, Ghoul, Dark Caster, Undead Caster, Skeleton, Shade)**
```
                        vs Goblin  vs Ghoul  vs D.Caster  vs U.Caster  vs Skeleton  vs Shade
                        90/3a      100/2a    100/2a       120/2a       125/2a       130/3a
 Crusader (23 melee) ..  5          5         5            6            6            7
 Confessor (9 melee) .. 15         15        15           18           18           22
 Inquisitor (12 melee)  10         10        10           12           13           15
 Ranger (21 ranged) ...  5          6         6            7            7            8
 Hexblade (17 melee) ..  7          7         7            8            9           10
```

**Mid Tier (Wraith, Acolyte, Dark Priest, Imp Lord, Medusa)**
```
                        vs Wraith  vs Acolyte  vs D.Priest  vs Imp Lord  vs Medusa
                        145/3a     150/3a      170/4a       180/4a       180/4a
 Crusader (23 melee) ..  8          8           9           10           10
 Confessor (9 melee) .. 25         25          34           36           36
 Inquisitor (12 melee)  17         17          22           23           23
 Ranger (21 ranged) ...  9          9          10           11           11
 Hexblade (17 melee) .. 11         11          14           14           14
```

**Elite Tier (Demon, Horror, Demon Knight, Werewolf, Construct)**
```
                        vs Demon   vs Horror  vs D.Knight  vs Werewolf  vs Construct
                        240/5a     240/6a     260/8a       290/6a       320/10a
 Crusader (23 melee) .. 14         15         18           18           25
 Confessor (9 melee) .. 60         80        260 ⚠         97          320 ⚠
 Inquisitor (12 melee)  35         40         65           49          160 ⚠
 Ranger (21 ranged) ... 15         16         20           20           30
 Hexblade (17 melee) .. 20         22         29           27           46
```

**Boss Tier (Necromancer, Undead Knight, Demon Lord, Reaper, Construct Guardian)**
```
                        vs Necro   vs Und.Kn  vs D.Lord  vs Reaper  vs C.Guard
                        380/6a     425/12a    480/9a     525/10a    550/14a
 Crusader (23 melee) .. 23         39         35         41         62
 Confessor (9 melee) . 127        425 ⚠      480 ⚠     525 ⚠      550 ⚠
 Inquisitor (12 melee)  64        425 ⚠      160        263 ⚠      550 ⚠
 Ranger (21 ranged) ... 26         48         40         48          79
 Hexblade (17 melee) .. 35         85         60         75         184
```

> ⚠ Confessor and Inquisitor deal only 1 dmg/hit to high-armor targets at melee
> (armor ≥ attack). These matchups are effectively impossible without skills.
> Wither DoT (24 dmg, bypasses armor) and holy damage skills remain critical.
> Ranger ranged auto-attacks (21) handle armored targets far better than melee.

### Holy Damage vs. Tagged Enemies

Only enemies with `undead` or `demon` tags take bonus holy damage.
Enemies tagged `beast`, `construct`, `aberration`, `humanoid`, or untagged take
normal (non-bonus) damage from Rebuke and Exorcism.

```
                        vs Imp    vs Demon   vs D.Knight  vs Acolyte  vs Imp Lord  vs D.Lord
                        70/1a     240/5a     260/8a       150/3a      180/4a       480/9a
                        (demon)   (demon)    (demon)      (demon)     (demon)      (demon)

 Rebuke (24 base, ×1.5 tagged, CD 7)
   Damage per cast ...   35        31          28           33          32           27
   Casts to kill .....    2         8          10            5           6           18

 Exorcism (20 base, ×2.0 tagged, CD 4)
   Damage per cast ...   39        35          32           37          36           31
   Casts to kill .....    2         7           9            5           5           16

                        vs Skel.  vs Ghoul   vs U.Caster  vs Shade   vs Wraith   vs D.Priest  vs Und.Kn   vs Necro   vs Reaper
                        125/2a    100/2a     120/2a       130/3a     145/3a      170/4a       425/12a     380/6a     525/10a
                        (undead)  (undead)   (undead)     (undead)   (undead)    (undead)     (undead)    (undead)   (undead)

 Rebuke (24 base, ×1.5 tagged, CD 7)
   Damage per cast ...   34        34          34           33          33          32           24          30         26
   Casts to kill .....    4         3           4            4           5           6           18          13         21

 Exorcism (20 base, ×2.0 tagged, CD 4)
   Damage per cast ...   38        38          38           37          37          36           28          34         30
   Casts to kill .....    4         3           4            4           4           5           16          12         18

 Wither (6/turn × 4 turns, CD 6) — bypasses armor
   Total per cast ....   24        24          24           24          24          24           24          24         24
```

> **Not vulnerable to holy damage:** Medusa (beast), Werewolf (beast), Insectoid (beast),
> Evil Snail (beast), Construct (construct), Construct Guardian (construct),
> Horror (aberration), Dark Caster (none), Goblin Spearman (humanoid).
> Rebuke deals 24 / Exorcism deals 20 vs those targets (normal damage minus armor).

---

## Items & Equipment

**Equipment Slots:** Weapon, Armor, Accessory (3 total)

### Weapons

```
 COMMON
 ──────────────────────────────────────────────────────
 Rusty Sword ........... +5 melee                 10g
 Iron Mace ............. +8 melee                 15g
 Shortbow .............. +8 ranged                12g

 UNCOMMON
 ──────────────────────────────────────────────────────
 Tempered Greatsword ... +12 melee                35g
 Blessed Warhammer ..... +10 melee, +10 HP        45g
 Yew Longbow ........... +14 ranged               40g
```

### Armor

```
 COMMON
 ──────────────────────────────────────────────────────
 Chainmail Shirt ....... +3 armor                 10g
 Leather Vest .......... +4 armor                 12g
 Dented Breastplate .... +6 armor                 18g

 UNCOMMON
 ──────────────────────────────────────────────────────
 Reinforced Plate ...... +8 armor, +10 HP         50g
 Shadow Cloak .......... +6 armor, +20 HP         45g
```

### Accessories

```
 COMMON
 ──────────────────────────────────────────────────────
 Iron Ring ............. +20 HP                   10g
 Bone Amulet ........... +30 HP                   15g

 UNCOMMON
 ──────────────────────────────────────────────────────
 Sigil Ring ............ +3 melee, +3 ranged, +30 HP   55g
 Skull Pendant ......... +2 armor, +50 HP              60g
```

### Consumables

```
 Health Potion ......... Heal 40 HP     Sell: 15g   Buy: 25g   (Common)
 Greater Health Potion . Heal 75 HP     Sell: 35g   Buy: 55g   (Uncommon)
 Portal Scroll ......... Party escape   Sell: 50g   Buy: 75g   (Uncommon)
```

### Best-in-Slot Power Spikes (Full Uncommon Gear)

**Crusader BiS:**
```
 Weapon .... Tempered Greatsword (+12 melee)
 Armor ..... Reinforced Plate (+8 armor, +10 HP)
 Accessory . Skull Pendant (+2 armor, +50 HP)
 TOTALS:     32 melee, 18 armor, 210 HP
```

**Ranger BiS:**
```
 Weapon .... Yew Longbow (+14 ranged)
 Armor ..... Shadow Cloak (+6 armor, +20 HP)
 Accessory . Sigil Ring (+3 ranged, +30 HP)
 TOTALS:     35 ranged, 8 armor, 130 HP
```

**Hexblade BiS:**
```
 Weapon .... Tempered Greatsword (+12 melee)
 Armor ..... Shadow Cloak (+6 armor, +20 HP)
 Accessory . Sigil Ring (+3 melee, +3 ranged, +30 HP)
 TOTALS:     30 melee, 15 ranged, 11 armor, 160 HP
```

---

## Loot Tables

### Enemy Drops

```
 Enemy              Drop %   Items   Rarity          Notable Loot
 ────────────────   ──────   ─────   ──────────────  ────────────────────────────
 SWARM TIER
 Evil Snail          35%     1       Common          Potions, accessories
 Imp                 40%     1       Common          Potions, accessories
 Insectoid           40%     1       Common          Potions, leather armor

 FODDER TIER
 Ghoul               45%     1       Common          Potions, accessories, leather
 Goblin Spearman     45%     1       Common          Weapons, leather/chain armor
 Skeleton            50%     1       Common          Bows, leather armor
 Acolyte             50%     1       Common/Uncommon Potions, skull pendant (15%)
 Shade               50%     1       Common/Uncommon Shadow cloak, skull pendant (15%)
 Dark Caster         50%     1       Common/Uncommon Bows, sigil ring (15%)
 Undead Caster       50%     1       Common/Uncommon Bows, skull pendant (15%)

 MID TIER
 Dark Priest         55%     1-2     Common/Uncommon Sigil ring (20%)
 Wraith              55%     1       Common/Uncommon Shadow cloak, skull pendant (15%)
 Demon               60%     1       Common          Weapons, armor, potions
 Medusa              60%     1-2     Common/Uncommon Longbow, sigil ring (20%)
 Construct           60%     1-2     Common/Uncommon Plate armor, warhammer (20%)
 Horror              60%     1-2     Common/Uncommon Shadow cloak, skull pendant (20%)

 ELITE TIER
 Imp Lord            65%     1-2     Common/Uncommon Sigil ring, skull pendant (20%)
 Demon Knight        65%     1-2     Common/Uncommon Greatsword, plate armor (20%)
 Werewolf            65%     1-2     Common/Uncommon Greatsword, warhammer (20%)

 BOSS TIER
 Necromancer        100%     2-3     Guaranteed Unc  Shadow cloak, skull pendant, portal scroll
 Undead Knight      100%     2-3     Guaranteed Unc  Greatsword, plate, portal scroll
 Demon Lord         100%     2-3     Guaranteed Unc  Greatsword, plate, portal scroll
 Reaper             100%     2-3     Guaranteed Unc  Weapons, armor, portal scroll
 Construct Guard.   100%     2-3     Guaranteed Unc  Plate, warhammer, portal scroll
```

### Chest Loot

```
 Default Chest ... 1-2 items, mostly Common, 10% chance Uncommon
 Boss Chest ...... 2-3 items, Guaranteed Uncommon
```

---

## Wave Arena Composition

8 waves of escalating difficulty:

```
 Wave  Name             Enemies                         Total HP  Armor
 ────  ───────────────  ──────────────────────────────  ────────  ─────
   1   Scouts           2× Skeleton                       120       2
   2   Melee Rush       2× Demon                          240       8
   3   Mixed Threat     1× Demon, 2× Skeleton             240       6
   4   Heavy Assault    3× Demon                          360      12
   5   Firing Line      2× Demon, 2× Skeleton             360      10
   6   Champion         1× Undead Knight, 2× Skeleton     320      12
   7   Onslaught        1× UK, 2× Demon, 2× Skeleton     560      20
   8   Final Stand      2× Undead Knight, 2× Demon        640      28
                                                        ─────     ───
                        TOTAL                            2,840      98
```

---

## Balance Observations & Gaps

### Identified Issues

1. **Flat armor scaling is extreme.**
   At 1:1 flat reduction, high-armor targets (Crusader at 8, Undead Knight at 10)
   become nearly immune to low-damage attackers. Confessor and Ranger deal only
   1 damage per melee hit to a Crusader. A percentage-based or diminishing-returns
   armor system would smooth this out.
   *Partially mitigated (Phase 11):* Wither DoT bypasses armor entirely. Holy
   damage skills give Confessor and Inquisitor meaningful damage against armored
   targets. Shield of Faith provides +5 armor to any ally, helping squishy classes.

2. **~~Confessor is severely underequipped.~~** ✅ *Resolved (Phase 11).*
   Now has 4/4 skills: Heal, Shield of Faith, Exorcism, Prayer. Full support kit
   with healing (instant + HoT), defensive buffing, and holy offense.

3. **~~Ranger only has 1 skill.~~** ✅ *Resolved (Phase 12).*
   Now has 4/4 skills: Power Shot, Volley (AoE), Evasion (dodge), Crippling Shot
   (ranged + root). Full ranged DPS + kiting kit.

4. **~~Only 3 enemy types.~~** ✅ *Resolved (Enemy Expansion + Feb 2026 Sprite Batch).*
   Now **24 enemy types** across 5 tiers with creature tags and diverse AI.
   - Phase 11: Added Imp (demon swarm) and Dark Priest (undead support)
   - Enemy Expansion: Added Wraith (caster), Medusa (ranged DPS), Acolyte
     (support), Werewolf (elite melee), Reaper (boss), Construct (tank)
   - Feb 2026 Sprite Batch: Added 13 new enemies — Imp Lord, Demon Lord,
     Demon Knight, Construct Guardian, Ghoul, Necromancer, Undead Caster,
     Horror (×2 variants), Insectoid (×2 variants), Dark Caster (×2 variants),
     Evil Snail, Goblin Spearman, Shade
   - New creature tags introduced: `aberration` (Horror), `humanoid` (Goblin)
   - All 5 tiers populated: Swarm, Fodder, Mid, Elite, Boss

5. **No mana system.**
   All skills have mana_cost: 0. The field exists but isn't used.
   Skills are purely cooldown-gated.

6. **Only 2 rarity tiers.**
   Common and Uncommon. No Rare/Epic/Legendary items. Low power ceiling.

7. **No class-restricted items.**
   Any class can equip any weapon. Confessor with a Greatsword gets
   +12 melee despite being a support.

8. **~~Hexblade is the best all-rounder with no real weakness.~~** *Partially resolved (Phase 11).*
   Now has a clear identity as a dark curse/reflect hybrid. Ward + Wither give
   tactical depth but don't increase raw DPS. Other classes now have equally
   strong skill kits to compete.

9. **~~No AoE abilities.~~** ✅ *Resolved (Phase 12).*
   Volley (Ranger) hits all enemies in 2-tile radius. Holy Ground (Crusader)
   heals all allies in 1-tile radius. AoE adds depth to wave content.

10. **~~No status effects / crowd control.~~** *Mostly resolved (Phase 11 + 12).*
    DoT (Wither), HoT (Prayer), armor buffs (Shield of Faith/Bulwark), charge-based
    shields (Ward/Evasion), detection (Divine Sense), stun (Shield Bash), root
    (Crippling Shot), and taunt (Taunt) are now implemented. Remaining:
    - No bleed (stacking DoT)
    - No generic debuff framework (stat reduction)
    - No slow (reduced movement range)

### Phase 11 Balance Impact

**Confessor** went from the weakest class (1 skill, 8 melee, no utility beyond
healing) to a strong support with 4 complementary skills. Exorcism gives real
damage output (40 vs tagged enemies), Prayer provides efficient sustained healing
(32 total over 4 turns), and Shield of Faith makes any ally significantly tankier.

**Inquisitor** gained a clear demon-hunter identity. Rebuke deals 36 damage to
tagged enemies (was 42 pre-balance, nerfed in balance pass). Divine Sense
provides unique strategic value — no other class can reveal enemy positions at
12-tile range.

**Hexblade** shifted from "generic all-rounder" to "curse/melee hybrid." Wither
provides 24 guaranteed damage that bypasses armor, making Hexblade the best class
for wearing down heavily armored targets. Ward's reflect mechanic creates a
risk/reward dynamic for enemies engaging in melee.

### Phase 12 Skill Expansion

**Crusader** received a full tank identity overhaul. Lost Double Strike and War Cry
(burst DPS skills) and gained Taunt, Shield Bash, Holy Ground, and Bulwark.
Now a pure frontline anchor with crowd control (taunt + stun), self-sustain
(holy ground AoE heal), and extreme durability (bulwark +8 armor). DPS dropped
significantly — Crusader is now the lowest damage class on the meter, but brings
irreplaceable utility that enables the rest of the party.

**Ranger** expanded from 1/4 to 4/4 skills. Power Shot remains the core burst,
but Volley adds AoE, Evasion adds survivability, and Crippling Shot adds CC.
The class can now kite effectively (Crippling Shot roots → 2 free ranged turns)
and contribute in multi-target fights (Volley).

**All 5 classes now have 4/4 skill slots filled.**

### Enemy Expansion Balance Impact

The addition of 6 spellcasting enemies significantly changes combat dynamics:

- **Wraith** (Wither + Shadow Step) is the first enemy that bypasses armor with
  DoT, punishing high-armor parties. Shadow Step lets it reposition unpredictably.
- **Medusa** (Venom Gaze + Power Shot) introduces enemy ranged DoT pressure.
  Parties must prioritize her or suffer sustained poison ticking.
- **Acolyte** (Heal + Shield of Faith) is the first enemy healer — parties must
  focus Acolytes early or face prolonged fights as they sustain other enemies.
- **Werewolf** (War Cry + Double Strike) is a dangerous elite melee fighter.
  War Cry + high base attack (22) makes it a serious single-target threat.
- **Reaper** (Wither + Soul Reap) is the second boss tier. Soul Reap's 2.0×
  multiplier on 15 base attack deals 30 damage, killing most heroes in 3-4 hits.
  Wither provides additional sustained pressure.
- **Construct** (Ward) introduces reflect damage — melee-heavy parties take chip
  damage when attacking. Its 10 armor and 320 HP make it highly durable.

### February 2026 — Sprite Batch Enemy Expansion

13 new enemies added from the sprite batch, organized into tiers:

**New Bosses (+3):** Demon Lord (480 HP, 28 melee — highest melee in game),
Necromancer (380 HP, 16 ranged — highest ranged among enemies), Construct
Guardian (550 HP, 14 armor — tankiest enemy in game). These provide boss-tier
threat for demon, undead, and construct encounter themes respectively.

**New Elites (+2):** Demon Knight (260 HP, 8 armor — armored demon variant) and
Horror (240 HP, 6 armor — aberration bruiser with new `aberration` tag).

**New Mid-tier (+1):** Imp Lord (180 HP — elite imp commander bridging swarm
and elite tiers).

**New Fodder (+4):** Ghoul (100 HP, 14 melee — fast undead), Undead Caster
(120 HP, 16 ranged — skeleton mage), Dark Caster (100 HP, 14 ranged — untagged
generic mage), Shade (130 HP, 14 melee — mid-tier shadow undead).

**New Swarm (+2):** Insectoid (80 HP — beast swarmer), Evil Snail (60 HP, 6
armor — tanky novelty pest), Goblin Spearman (90 HP — humanoid melee fodder).

**New creature tags:** `aberration` (Horror), `humanoid` (Goblin Spearman).
Neither tag triggers holy damage bonuses.

**No skills assigned yet** — all 13 new enemies use auto-attack only. ~~Skill
assignment is planned for a future pass.~~ ✅ *Resolved (Phase 13 — Enemy Skill Expansion).*
11 of 13 received skills; Imp, Insectoid, Dark Caster, Evil Snail, and Goblin Spearman
remain auto-attack-only as intentional simple enemies.

### Phase 13 — Enemy Skill Expansion (February 28, 2026)

11 enemies gained skills using existing effects. No new skill types were created.

**Boss tier impact (all 5 bosses now have abilities):**
- **Necromancer** (Wither + Soul Reap) — Death mage boss. Wither DoT (24 armor-bypass) +
  Soul Reap burst (16 × 2.0 = 32 damage). The scariest ranged caster encounter.
- **Demon Lord** (War Cry + Double Strike) — Overlord boss. War Cry → 56 melee per hit
  for 2 turns. Double Strike = 2 × (28 × 0.6) = 33.6 burst. Absolute freight train.
- **Construct Guardian** (Ward + Bulwark) — Arcane tank boss. Ward reflects 24 total
  damage back. Bulwark pushes armor from 14 → 22. Nearly unkillable without DoTs.
- **Undead Knight** (Shield Bash + Bulwark) — Room guardian boss. Shield Bash = 17.5
  damage + 1-turn stun. Bulwark → 20 armor. Locks targets down and walls up.

**Elite tier impact:**
- **Demon Knight** (War Cry) — Armored commander. War Cry → 40 melee for 2 turns.
- **Imp Lord** (War Cry) — Imp chieftain. War Cry → 32 melee for 2 turns.
- **Horror** (Shadow Step + Wither) — Aberration. Teleports in and applies 24 DoT.
  Same kit as Wraith but at 240 HP / 6 armor — the most terrifying non-boss.

**Fodder/mid tier impact:**
- **Ghoul** (Double Strike) — Frenzied undead. DS = 2 × (14 × 0.6) = 16.8 burst.
- **Skeleton** (Evasion) — Ranged sniper dodges 2 attacks. Annoying to trade with.
- **Undead Caster** (Wither) — Skeleton mage adds 24 DoT to ranged output.
- **Shade** (Shadow Step) — Shadow creature teleports to strike from unexpected angles.

**Result:** 17/22 enemies now have skills (was 6/22). Total AI role map: 22 entries (5 hero + 17 enemy).

### Expansion Suggestions (Updated Post-Phase 12)

**New Skills (Remaining Gaps):**
```
 Crusader .... Holy Charge (gap-close + damage)
 Hexblade .... Life Drain (melee heal-on-hit)
 Inquisitor .. Smite (execute low-HP tagged enemies)
 Confessor ... Sanctuary (damage immunity 1 turn, ally)
 Ranger ...... Trap (place on ground, roots enemy that walks over it)
```

**New Enemies (Remaining Gaps):**
```
 Spider ....... Poison DoT on hit, moderate stats
 Lich ......... Boss caster, AoE + summons, very high HP
 Dragon ....... Ultimate boss encounter, multi-phase fight
```
*Implemented (24 total):* Imp, Dark Priest, Wraith, Medusa, Acolyte, Werewolf,
Reaper, Construct, Imp Lord, Demon Lord, Demon Knight, Construct Guardian,
Ghoul, Necromancer, Undead Caster, Horror, Insectoid, Dark Caster, Evil Snail,
Goblin Spearman, Shade

**~~Enemy Skills Needed (13 new enemies have no skills):~~** ✅ *Resolved (Phase 13).*
11 of 13 received skills. Remaining auto-attack-only by design:
```
 Imp ............... Swarm fodder (70 HP). Skills would slow group AI processing.
 Insectoid ......... Swarm fodder (80 HP). Simple by design.
 Dark Caster ....... Generic untagged mage (100 HP). Could get Power Shot later.
 Evil Snail ........ Novelty enemy (60 HP). Its charm is being a dumb gastropod.
 Goblin Spearman ... Basic humanoid fodder (90 HP). Simple cannon fodder.
```

**New Items:**
```
 Rare tier weapons/armor (slot between Uncommon and Epic)
 Class-specific items with unique effects
 Shields as a separate equipment slot
 Items that enhance specific skills
```

**Status Effects (Remaining Gaps):**
```
 Bleed .... Stacking DoT
 Curse .... Reduced stats for N turns
 Slow ..... Reduced movement range
```
*Implemented:* DoT (Wither/Venom Gaze), HoT (Prayer), Armor Buff (Shield of Faith/Bulwark),
Charge Shield (Ward), Evasion, Detection (Divine Sense), Stun (Shield Bash),
Root (Crippling Shot), Taunt

**Armor Rework:**
```
 Current:  flat reduction (armor points subtract from damage)
 Consider: percentage reduction → armor / (armor + K)
           where K = 50 gives: 8 armor = 13.8% reduction
                               10 armor = 16.7% reduction
           This prevents low-damage classes from being hard-walled.
 Note:     Phase 11 partially mitigates via armor-bypassing DoT and holy damage.
```