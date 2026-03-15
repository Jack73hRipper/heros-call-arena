# Arena — Class Overview (Source of Truth)

> **Last updated:** March 14, 2026
>
> Single reference document for all 11 playable classes — base stats, skills, roles, and design identity.
> Values are pulled directly from `classes_config.json`, `skills_config.json`, and `combat_config.json`.

---

## Table of Contents

1. [Global Combat Rules](#global-combat-rules)
2. [Class Comparison Table](#class-comparison-table)
3. [Auto-Attack Reference](#auto-attack-reference)
4. [Class Profiles](#class-profiles)
   - [Crusader](#1-crusader--tank)
   - [Confessor](#2-confessor--support)
   - [Inquisitor](#3-inquisitor--scout)
   - [Ranger](#4-ranger--ranged-dps)
   - [Hexblade](#5-hexblade--hybrid-dps)
   - [Mage](#6-mage--caster-dps)
   - [Bard](#7-bard--offensive-support)
   - [Blood Knight](#8-blood-knight--sustain-melee-dps)
   - [Plague Doctor](#9-plague-doctor--controller)
   - [Revenant](#10-revenant--retaliation-tank)
   - [Shaman](#11-shaman--totemic-healer)
5. [Skill Quick Reference](#skill-quick-reference)
6. [Weapon Category Access](#weapon-category-access)
7. [Design Notes & Balance Philosophy](#design-notes--balance-philosophy)

---

## Global Combat Rules

| Mechanic | Value |
|----------|-------|
| Turn tick rate | 1 second |
| Armor reduction | Flat −1 damage per armor point |
| Minimum damage | 1 (can never deal 0) |
| Base crit chance | 5% |
| Base crit damage | 1.5× |
| Crit damage cap | 3.0× |
| Dodge cap | 40% |
| Damage reduction cap | 50% |
| Cooldown reduction cap | 30% |
| Gold per enemy kill | 10g |
| Gold per boss kill | 50g |
| Gold dungeon clear bonus | 25g |
| Max skill slots | 6 (1 auto-attack + up to 4 active skills) |

### Damage Formulas

```
Melee:   max(1, (base_melee + weapon_bonus) × buff_multiplier − target_armor)
Ranged:  max(1, (base_ranged + weapon_bonus) × buff_multiplier − target_armor)
Magic:   max(1, (base_ranged × multiplier) − floor(target_armor × 0.5))
         (magic bypasses 50% of armor)
DoT:     Ignores armor entirely (ticks as debuff damage)
Holy:    Flat damage reduced by armor; bonus multiplier vs Undead/Demon tags
```

---

## Class Comparison Table

| Class | Role | HP | Melee | Ranged | Armor | Vision | Range | Shape | Color |
|-------|------|----|-------|--------|-------|--------|-------|-------|-------|
| **Crusader** | Tank | 135 | 14 | 0 | 6 | 5 | 1 | Square | Blue `#4a8fd0` |
| **Confessor** | Support | 100 | 8 | 0 | 3 | 6 | 1 | Circle | Yellow `#f0e060` |
| **Inquisitor** | Scout | 90 | 10 | 12 | 4 | 9 | 5 | Triangle | Purple `#a050f0` |
| **Ranger** | Ranged DPS | 80 | 8 | 18 | 2 | 7 | 6 | Diamond | Green `#40c040` |
| **Hexblade** | Hybrid DPS | 110 | 15 | 12 | 5 | 6 | 4 | Star | Red `#e04040` |
| **Mage** | Caster DPS | 80 | 6 | 14 | 2 | 7 | 5 | Hexagon | Orange `#e07020` |
| **Bard** | Offensive Support | 110 | 10 | 12 | 4 | 7 | 4 | Crescent | Gold `#d4a017` |
| **Blood Knight** | Sustain Melee DPS | 100 | 16 | 0 | 4 | 6 | 0 | Shield | Dark Red `#8B0000` |
| **Plague Doctor** | Controller | 95 | 8 | 12 | 3 | 7 | 5 | Flask | Emerald `#50C878` |
| **Revenant** | Retaliation Tank | 130 | 16 | 0 | 6 | 5 | 0 | Coffin | Slate `#708090` |
| **Shaman** | Totemic Healer | 95 | 8 | 10 | 3 | 7 | 4 | Totem | Bronze `#8B6914` |

### Stat Extremes

| Stat | Highest | Lowest |
|------|---------|--------|
| HP | Crusader (135) | Mage (80) |
| Melee Damage | Blood Knight / Revenant (16) | Mage (6) |
| Ranged Damage | Ranger (18) | Confessor / Crusader / Blood Knight / Revenant (0) |
| Armor | Crusader / Revenant (6) | Mage / Ranger (2) |
| Vision | Inquisitor (9) | Crusader / Revenant (5) |
| Range | Ranger (6) | Crusader / Confessor / Blood Knight / Revenant (0–1 melee) |

---

## Auto-Attack Reference

All classes have either `auto_attack_melee` (1.15× melee damage) or `auto_attack_ranged` (1.15× ranged damage).

| Class | Type | Base × 1.15 | Effective Auto |
|-------|------|-------------|----------------|
| Crusader | Melee | 14 × 1.15 | **16.1** |
| Confessor | Melee | 8 × 1.15 | **9.2** |
| Inquisitor | Ranged | 12 × 1.15 | **13.8** |
| Ranger | Ranged | 18 × 1.15 | **20.7** |
| Hexblade | Melee | 15 × 1.15 | **17.3** |
| Mage | Ranged | 14 × 1.15 | **16.1** |
| Bard | Ranged | 12 × 1.15 | **13.8** |
| Blood Knight | Melee | 16 × 1.15 | **18.4** |
| Plague Doctor | Ranged | 12 × 1.15 | **13.8** |
| Revenant | Melee | 16 × 1.15 | **18.4** |
| Shaman | Ranged | 10 × 1.15 | **11.5** |

---

## Class Profiles

---

### 1. Crusader — Tank

> *Heavy-armored frontline warrior. High HP, high armor, melee only.*

**Identity:** The party's anchor. Draws aggro with Taunt, absorbs damage with Bulwark, stuns priority targets with Shield Bash, and off-heals adjacent allies with Holy Ground. Zero ranged capability, worst vision — needs the team to be his eyes.

| Stat | Value |
|------|-------|
| HP | 135 |
| Melee Damage | 14 |
| Ranged Damage | 0 |
| Armor | 6 |
| Vision Range | 5 |
| Ranged Range | 1 (melee) |
| Weapons | Melee, Hybrid |

#### Skills

| Slot | Skill | Icon | Target | Range | CD | Effect |
|:----:|-------|:----:|--------|:-----:|:--:|--------|
| 0 | Auto Attack | — | Adjacent enemy | 1 | 0 | 1.15× melee damage |
| 1 | Taunt | 🗣️ | Self (AoE r=2) | 2 | 5 | Force enemies within 2 tiles to target you for 2 turns |
| 2 | Shield Bash | 🛡️💥 | Adjacent enemy | 1 | 4 | 0.7× melee damage + stun 1 turn |
| 3 | Holy Ground | ✝️ | Self (AoE r=1) | 1 | 5 | Heal all allies within 1 tile for 15 HP |
| 4 | Bulwark | 🏰 | Self | 0 | 5 | +8 armor for 4 turns |

#### Damage Examples (0 armor target)

- Auto-attack: 14 × 1.15 = **16** per hit
- Shield Bash: 14 × 0.7 = **10** + stun
- Bulwark active: 6 + 8 = **14 total armor** (near-immune to low-damage attackers)

---

### 2. Confessor — Support

> *Divine support unit. The primary healer with burst heal, HoT, armor buffs, and holy offense.*

**Identity:** Keeps the party alive. Burst Heal for emergencies, Prayer for sustained healing, Shield of Faith to harden a target, and Exorcism for offensive contribution — especially devastating against undead/demon enemies. Low personal damage but irreplaceable sustain.

| Stat | Value |
|------|-------|
| HP | 100 |
| Melee Damage | 8 |
| Ranged Damage | 0 |
| Armor | 3 |
| Vision Range | 6 |
| Ranged Range | 1 (melee) |
| Weapons | Melee, Caster, Hybrid |

#### Skills

| Slot | Skill | Icon | Target | Range | CD | Effect |
|:----:|-------|:----:|--------|:-----:|:--:|--------|
| 0 | Auto Attack | — | Adjacent enemy | 1 | 0 | 1.15× melee damage |
| 1 | Heal | 💚 | Ally or Self | 3 | 4 | Restore 30 HP |
| 2 | Shield of Faith | ✨ | Ally or Self | 3 | 5 | +5 armor for 3 turns |
| 3 | Exorcism | ☀️ | Enemy (ranged) | 5 | 4 | 20 holy damage (40 vs Undead/Demon) |
| 4 | Prayer | 🙏 | Ally or Self | 4 | 6 | 8 HP/turn for 4 turns (32 total) |

#### Healing Output

- Heal: **30 HP** instant (CD 4) → 7.5 HPT
- Prayer: **32 HP** over 4 turns (CD 6) → 5.3 HPT
- Combined sustained: ~12.8 HPT when both cycling
- Holy Ground (via Crusader): adds another 15 HP burst if stacked near tank

---

### 3. Inquisitor — Scout

> *Far-seeing hybrid. Best vision range, moderate mixed damage, team debuff amplifier.*

**Identity:** The party's eyes and force multiplier. Best vision in the game (9 tiles), Seal of Judgment marks enemies to take +25% damage from all sources, Rebuke delivers holy burst damage (bonus vs undead/demon), Power Shot for ranged damage, and Shadow Step for repositioning. Wins games through smart target selection, not raw DPS.

| Stat | Value |
|------|-------|
| HP | 90 |
| Melee Damage | 10 |
| Ranged Damage | 12 |
| Armor | 4 |
| Vision Range | 9 |
| Ranged Range | 5 |
| Weapons | Ranged, Caster, Hybrid |

#### Skills

| Slot | Skill | Icon | Target | Range | CD | Effect |
|:----:|-------|:----:|--------|:-----:|:--:|--------|
| 0 | Auto Attack | — | Enemy (ranged) | 5 | 0 | 1.15× ranged damage |
| 1 | Power Shot | 🎯 | Enemy (ranged) | 5 | 7 | 1.8× ranged damage |
| 2 | Shadow Step | 👤 | Empty tile | 3 | 4 | Teleport to tile (LOS required) |
| 3 | Seal of Judgment | ⚖️ | Enemy (ranged) | 6 | 4 | 20 holy damage + mark: +25% damage taken for 3 turns |
| 4 | Rebuke the Wicked | ⚡ | Enemy (ranged) | 6 | 5 | 28 holy damage (42 vs Undead/Demon) |

#### Damage Examples (vs 4 armor)

- Auto-attack: 12 × 1.15 − 4 = **~10** per hit
- Power Shot: 12 × 1.8 − 4 = **~18**
- Seal of Judgment: 20 − 4 = **16** + mark
- Rebuke: 28 − 4 = **24** (38 vs tagged)
- Sealed target takes +25% from all allies — the Inquisitor's unique team contribution

---

### 4. Ranger — Ranged DPS

> *Deadly at range with the longest attack reach. Fragile up close.*

**Identity:** Pure ranged damage dealer. Highest ranged damage (18) with longest range (6 tiles). Excels at kiting — Crippling Shot roots pursuers, Evasion dodges attacks, Volley punishes clusters. The most dangerous class at range, the most vulnerable in melee.

| Stat | Value |
|------|-------|
| HP | 80 |
| Melee Damage | 8 |
| Ranged Damage | 18 |
| Armor | 2 |
| Vision Range | 7 |
| Ranged Range | 6 |
| Weapons | Ranged, Hybrid |

#### Skills

| Slot | Skill | Icon | Target | Range | CD | Effect |
|:----:|-------|:----:|--------|:-----:|:--:|--------|
| 0 | Auto Attack | — | Enemy (ranged) | 6 | 0 | 1.15× ranged damage |
| 1 | Power Shot | 🎯 | Enemy (ranged) | 6 | 7 | 1.8× ranged damage |
| 2 | Volley | 🏹🌧️ | Ground AoE (r=2) | 5 | 7 | 0.5× ranged damage to all enemies in radius |
| 3 | Evasion | 💨 | Self | 0 | 6 | Dodge next 2 attacks (lasts 4 turns) |
| 4 | Crippling Shot | 🦵🏹 | Enemy (ranged) | 6 | 5 | 0.8× ranged damage + slow 2 turns |

#### Damage Examples (vs 0 armor)

- Auto-attack: 18 × 1.15 = **~21** per hit
- Power Shot: 18 × 1.8 = **~32**
- Volley: 18 × 0.5 = **~9** per target (AoE — value scales with enemy count)
- Crippling Shot: 18 × 0.8 = **~14** + slow

---

### 5. Hexblade — Hybrid DPS

> *Dark warrior equally dangerous in melee and at range.*

**Identity:** Versatile damage dealer who adapts to any situation. Opens with Wither (ranged DoT) to start ticking armor-ignoring damage, pops Ward for reflect shield, then Shadow Steps into melee for Double Strike burst. Punishes enemies who engage him (reflect) and those who flee (DoT). Jack of all trades, master of pressure.

| Stat | Value |
|------|-------|
| HP | 110 |
| Melee Damage | 15 |
| Ranged Damage | 12 |
| Armor | 5 |
| Vision Range | 6 |
| Ranged Range | 4 |
| Weapons | Melee, Ranged, Caster, Hybrid (all) |

#### Skills

| Slot | Skill | Icon | Target | Range | CD | Effect |
|:----:|-------|:----:|--------|:-----:|:--:|--------|
| 0 | Auto Attack | — | Adjacent enemy | 1 | 0 | 1.15× melee damage |
| 1 | Double Strike | ⚔️⚔️ | Adjacent enemy | 1 | 3 | 2 hits × 0.7× melee damage (1.4× total) |
| 2 | Shadow Step | 👤 | Empty tile | 3 | 4 | Teleport to tile (LOS required) |
| 3 | Wither | 🩸 | Enemy (ranged) | 4 | 5 | 8 damage/turn for 4 turns (32 total, ignores armor) |
| 4 | Ward | 🛡️ | Self | 0 | 6 | 4 charges — attackers take 8 reflected damage per hit |

#### Damage Examples (vs 0 armor)

- Auto-attack: 15 × 1.15 = **~17** per hit
- Double Strike: 15 × 0.7 × 2 = **~21** total
- Wither: 8 × 4 = **32** total (ignores armor, refreshable)
- Ward reflect: 4 × 8 = **32** max reflected damage

**Note:** Hexblade uses `auto_attack_melee` — the `base_ranged_damage: 12` and `ranged_range: 4` are legacy stats; the class is a melee auto-attacker with ranged spells (Wither).

---

### 6. Mage — Caster DPS

> *Glass cannon spellcaster. Devastating AoE and burst magic, but the most fragile class in the game.*

**Identity:** The highest burst and AoE damage dealer. Magic damage bypasses 50% of armor, giving Mages a unique advantage against tanks. Fireball for single-target nuking, Arcane Barrage for clusters, Frost Nova for self-peel + AoE slow, and Blink for emergency escape. Lowest HP and armor — one mistake means death.

| Stat | Value |
|------|-------|
| HP | 80 |
| Melee Damage | 6 |
| Ranged Damage | 14 |
| Armor | 2 |
| Vision Range | 7 |
| Ranged Range | 5 |
| Weapons | Caster, Hybrid |

#### Skills

| Slot | Skill | Icon | Target | Range | CD | Effect |
|:----:|-------|:----:|--------|:-----:|:--:|--------|
| 0 | Auto Attack | — | Enemy (ranged) | 5 | 0 | 1.15× ranged damage |
| 1 | Fireball | 🔥 | Enemy (ranged) | 5 | 4 | 2.0× magic damage (armor 50% effective) |
| 2 | Frost Nova | ❄️ | Self (AoE r=2) | 0 | 6 | 16 flat damage + slow 2 turns to all enemies in radius |
| 3 | Arcane Barrage | ✨ | Ground AoE (r=1) | 5 | 5 | 1.0× magic damage to all enemies in radius (armor 50% effective) |
| 4 | Blink | 💫 | Empty tile | 4 | 5 | Teleport to tile (LOS required) |

#### Damage Examples (vs 4 armor)

- Auto-attack: 14 × 1.15 − 4 = **~12** per hit
- Fireball: 14 × 2.0 − 2 (half armor) = **~26** (vs 4 armor)
- Fireball vs Crusader (6 armor): 28 − 3 = **~25** (physical would deal 28 − 6 = 22)
- Arcane Barrage: 14 × 1.0 − 2 (half armor) = **~12** per target (AoE, magic armor rules)
- Frost Nova: **16** flat + slow (AoE self-centered)

---

### 7. Bard — Offensive Support

> *War-poet who empowers allies with battle hymns and debilitates enemies with dark dirges.*

**Identity:** The team's force multiplier. Where the Confessor keeps the party alive, the Bard makes the party lethal. Ballad of Might gives +40% damage to nearby allies, Dirge of Weakness makes enemies take +30% damage, Verse of Haste accelerates ally cooldowns, and Cacophony provides self-peel with AoE damage + slow. Support through offense, not defense.

| Stat | Value |
|------|-------|
| HP | 110 |
| Melee Damage | 10 |
| Ranged Damage | 12 |
| Armor | 4 |
| Vision Range | 7 |
| Ranged Range | 4 |
| Weapons | Caster, Hybrid |

#### Skills

| Slot | Skill | Icon | Target | Range | CD | Effect |
|:----:|-------|:----:|--------|:-----:|:--:|--------|
| 0 | Auto Attack | — | Enemy (ranged) | 4 | 0 | 1.15× ranged damage |
| 1 | Ballad of Might | 🎵 | Self (AoE r=3) | 0 | 5 | +40% damage to all allies within 3 tiles for 3 turns |
| 2 | Dirge of Weakness | 💀 | Ground AoE (r=2) | 4 | 5 | +30% damage taken by enemies in radius for 3 turns |
| 3 | Verse of Haste | ⏩ | Ally or Self | 4 | 5 | Reduce all skill cooldowns by 2 turns |
| 4 | Cacophony | 🔊 | Self (AoE r=2) | 0 | 5 | 11 damage + slow 2 turns to all enemies in radius |

#### Team Value Examples

- Ballad on a 4-ally team for 3 turns: effectively ~96% of a DPS slot's output
- Dirge + Ballad stacked: allies deal 1.4× damage to targets taking 1.3× damage = **1.82× effective damage**
- Verse of Haste on a Mage: Fireball back online 2 turns early

---

### 8. Blood Knight — Sustain Melee DPS

> *Vampiric warrior who drains the life force of enemies to sustain an unrelenting melee assault. Self-sufficient but selfish — no team utility.*

**Identity:** The self-healing bruiser. Highest base melee damage (tied with Revenant at 16), Blood Strike heals while dealing damage, Crimson Veil buffs damage + adds HoT, Sanguine Burst is AoE lifesteal, and Blood Frenzy turns low HP into a power spike. Thrives in prolonged melee fights where it out-sustains opponents. Zero team contribution — pure selfish damage and self-healing.

| Stat | Value |
|------|-------|
| HP | 100 |
| Melee Damage | 16 |
| Ranged Damage | 0 |
| Armor | 4 |
| Vision Range | 6 |
| Ranged Range | 0 (melee only) |
| Weapons | Melee, Hybrid |

#### Skills

| Slot | Skill | Icon | Target | Range | CD | Effect |
|:----:|-------|:----:|--------|:-----:|:--:|--------|
| 0 | Auto Attack | — | Adjacent enemy | 1 | 0 | 1.15× melee damage |
| 1 | Blood Strike | 🩸 | Entity (adjacent) | 1 | 4 | 1.4× melee damage + heal 40% of damage dealt |
| 2 | Crimson Veil | 🌑 | Self | 0 | 6 | +30% melee damage + 6 HP/turn for 3 turns |
| 3 | Sanguine Burst | 💉 | Self (AoE r=1) | 0 | 7 | 0.7× melee damage to nearby enemies + heal 50% of total |
| 4 | Blood Frenzy | 🔥 | Self | 0 | 8 | Below 40% HP: heal 15 HP + 50% melee damage for 3 turns |

#### Damage & Healing Examples (vs 0 armor)

- Auto-attack: 16 × 1.15 = **~18** per hit
- Blood Strike: 16 × 1.4 = **~22** damage, heals **~9** HP
- Crimson Veil active auto: 16 × 1.3 × 1.15 = **~24** per hit + 6 HPT
- Sanguine Burst (3 adjacent enemies): 16 × 0.7 × 3 = **~34** total, heals **~17**
- Blood Frenzy + Crimson Veil auto: 16 × 1.5 × 1.3 × 1.15 = **~36** per hit

---

### 9. Plague Doctor — Controller

> *Masked alchemist who weaponizes disease and toxins. Weakens groups, denies space, and makes enemies rot from the inside.*

**Identity:** Attrition and area denial. Miasma creates dangerous zones of damage + slow, Plague Flask ticks armor-ignoring DoT over time, Enfeeble cripples enemy damage output by -25%, and Inoculate cleanses DoTs and adds armor — making the Plague Doctor both an offensive debuffer and a defensive cleanser. Wins by grinding enemies down rather than bursting them.

| Stat | Value |
|------|-------|
| HP | 95 |
| Melee Damage | 8 |
| Ranged Damage | 12 |
| Armor | 3 |
| Vision Range | 7 |
| Ranged Range | 5 |
| Weapons | Caster, Hybrid |

#### Skills

| Slot | Skill | Icon | Target | Range | CD | Effect |
|:----:|-------|:----:|--------|:-----:|:--:|--------|
| 0 | Auto Attack | — | Enemy (ranged) | 5 | 0 | 1.15× ranged damage |
| 1 | Miasma | ☁️ | Ground AoE (r=2) | 5 | 6 | 10 damage + slow 2 turns to enemies in radius |
| 2 | Plague Flask | 🧪 | Enemy (ranged) | 5 | 4 | 8 damage/turn for 4 turns (32 total, ignores armor) |
| 3 | Enfeeble | 💀 | Ground AoE (r=2) | 4 | 5 | -25% damage dealt by enemies in radius for 4 turns |
| 4 | Inoculate | 💉 | Ally or Self | 4 | 5 | +3 armor for 3 turns + cleanse all DoTs |

#### Damage Examples

- Auto-attack: 12 × 1.15 − armor = **~14 raw** per hit
- Plague Flask: 8 × 4 = **32** total (ignores armor, refreshable)
- Miasma: **10** per target + slow (AoE)
- Combined DoT + AoE on 3 enemies: 32 + 30 = **62** over 4 turns
- Enfeeble on Crusader: 16 auto → **12** (saves ~4 damage per hit for 4 turns)

---

### 10. Revenant — Retaliation Tank

> *Undying warrior that punishes attackers with thorns and defies death itself. The more enemies focus it, the deadlier it becomes.*

**Identity:** The "hit me, I dare you" tank. Grave Thorns reflects 12 damage per hit received, Grave Chains forces a single target to attack you (ranged taunt), Undying Will lets you cheat death and revive at 30% HP, and Soul Rend slows fleeing enemies. Unlike the Crusader who mitigates damage, the Revenant *takes* damage deliberately and punishes attackers for it.

| Stat | Value |
|------|-------|
| HP | 130 |
| Melee Damage | 16 |
| Ranged Damage | 0 |
| Armor | 6 |
| Vision Range | 5 |
| Ranged Range | 0 (melee only) |
| Weapons | Melee, Hybrid |

#### Skills

| Slot | Skill | Icon | Target | Range | CD | Effect |
|:----:|-------|:----:|--------|:-----:|:--:|--------|
| 0 | Auto Attack | — | Adjacent enemy | 1 | 0 | 1.15× melee damage |
| 1 | Grave Thorns | 🦴 | Self | 0 | 5 | Reflect 12 damage per hit received for 4 turns |
| 2 | Grave Chains | ⛓️ | Enemy (ranged) | 4 | 5 | Taunt single enemy for 3 turns |
| 3 | Undying Will | 💀 | Self | 0 | 8 | If you die within 5 turns, revive at 30% HP instead |
| 4 | Soul Rend | ⚔️ | Adjacent enemy | 1 | 4 | 1.5× melee damage + slow 2 turns |

#### Damage & Retaliation Examples (vs 0 armor)

- Auto-attack: 16 × 1.15 = **~18** per hit
- Soul Rend: 16 × 1.5 = **~24** + slow
- Grave Thorns (3 attackers, 4 turns): up to **144** reflected damage
- Undying Will revive: at 130 HP → revives at **39 HP**
- Grave Chains + Grave Thorns combo: force someone to hit you and take 12 per swing

---

### 11. Shaman — Totemic Healer

> *Dark ritualist who heals and supports through persistent bone totems. Rewards party positioning — allies near totems thrive, scattered allies suffer.*

**Identity:** Zone-based support through persistent totems. Healing Totem creates an AoE heal zone, Searing Totem creates an AoE damage zone, Soul Anchor prevents an ally's death, and Earthgrasp roots enemies in place. Unlike the Confessor who targets individuals, the Shaman controls areas. Powerful when the party plays around totem placement, weak when scattered.

| Stat | Value |
|------|-------|
| HP | 95 |
| Melee Damage | 8 |
| Ranged Damage | 10 |
| Armor | 3 |
| Vision Range | 7 |
| Ranged Range | 4 |
| Weapons | Caster, Hybrid |

#### Skills

| Slot | Skill | Icon | Target | Range | CD | Effect |
|:----:|-------|:----:|--------|:-----:|:--:|--------|
| 0 | Auto Attack | — | Enemy (ranged) | 4 | 0 | 1.15× ranged damage |
| 1 | Healing Totem | 🪵 | Ground AoE (r=2) | 4 | 6 | Place totem (20 HP): heals allies in radius 8 HP/turn for 4 turns. Max 1 active. |
| 2 | Searing Totem | 🔥 | Ground AoE (r=2) | 4 | 6 | Place totem (20 HP): deals 4 damage/turn (reduced by armor) to enemies in radius for 4 turns. Max 1 active. |
| 3 | Soul Anchor | ⚓ | Ally or Self | 4 | 10 | Mark target — if they would die within 4 turns, survive at 1 HP instead. One-time trigger. |
| 4 | Earthgrasp Totem | 🩸 | Ground AoE (r=2) | 4 | 7 | Place totem (20 HP): roots all enemies within 2 tiles each turn for 4 turns. Rooted enemies cannot move but can still attack. Max 1 active. |

#### Healing & Damage Examples

- Auto-attack: 10 × 1.15 = **~12 raw** per hit
- Healing Totem (2 allies in range, 4 turns): 8 × 2 × 4 = **64** total healing
- Searing Totem vs 0 armor (3 enemies, 4 turns): 4 × 3 × 4 = **48** total
- Searing Totem vs Crusader (6 armor): max(1, 4−6) = **1**/turn (tanks shrug it off)
- Soul Anchor: prevents one death — game-changing on a carry
- Earthgrasp Totem (3 enemies in range, 4 turns): 1-turn root refreshed each turn — persistent CC while totem stands
- Totem has 20 HP — enemies can destroy it to break free

---

## Skill Quick Reference

### All Player Skills (sorted by class)

| Class | Skill | Type | CD | Key Effect |
|-------|-------|------|----|------------|
| **Crusader** | Taunt | CC | 5 | AoE taunt r=2, 2 turns |
| | Shield Bash | Melee+Stun | 4 | 0.7× damage + 1-turn stun |
| | Holy Ground | AoE Heal | 5 | 15 HP to adjacent allies |
| | Bulwark | Self Buff | 5 | +8 armor, 4 turns |
| **Confessor** | Heal | Heal | 4 | 30 HP instant |
| | Shield of Faith | Buff | 5 | +5 armor to ally, 3 turns |
| | Exorcism | Holy Damage | 4 | 20 dmg (40 vs Undead/Demon) |
| | Prayer | HoT | 6 | 8 HP/turn, 4 turns (32 total) |
| **Inquisitor** | Power Shot | Ranged | 7 | 1.8× ranged damage |
| | Shadow Step | Mobility | 4 | Teleport 3 tiles |
| | Seal of Judgment | Debuff+Dmg | 4 | 20 holy + mark +25% taken, 3 turns |
| | Rebuke the Wicked | Holy Damage | 5 | 28 dmg (42 vs Undead/Demon) |
| **Ranger** | Power Shot | Ranged | 7 | 1.8× ranged damage |
| | Volley | AoE Ranged | 7 | 0.5× ranged to r=2 |
| | Evasion | Dodge | 6 | Dodge 2 attacks, 4 turns |
| | Crippling Shot | Ranged+CC | 5 | 0.8× ranged + slow 2 turns |
| **Hexblade** | Double Strike | Melee | 3 | 2 × 0.7× melee (1.4× total) |
| | Shadow Step | Mobility | 4 | Teleport 3 tiles |
| | Wither | DoT | 5 | 8/turn × 4 turns (32 total, ignores armor) |
| | Ward | Reflect Shield | 6 | 4 charges, 8 reflect per hit |
| **Mage** | Fireball | Magic Nuke | 4 | 2.0× magic damage (50% armor bypass) |
| | Frost Nova | AoE+CC | 6 | 16 flat dmg + slow r=2, 2 turns |
| | Arcane Barrage | AoE Magic | 5 | 1.0× magic to r=1 (50% armor bypass) |
| | Blink | Mobility | 5 | Teleport 4 tiles |
| **Bard** | Ballad of Might | AoE Buff | 5 | +40% damage to allies r=3, 3 turns |
| | Dirge of Weakness | AoE Debuff | 5 | +30% damage taken r=2, 3 turns |
| | Verse of Haste | CDR | 5 | -2 turns all cooldowns on target |
| | Cacophony | AoE+CC | 5 | 11 dmg + slow r=2, 2 turns |
| **Blood Knight** | Blood Strike | Lifesteal | 4 | 1.4× melee + heal 40% dealt |
| | Crimson Veil | Self Buff | 6 | +30% melee + 6 HP/turn, 3 turns |
| | Sanguine Burst | AoE Lifesteal | 7 | 0.7× melee r=1 + heal 50% total |
| | Blood Frenzy | Conditional | 8 | Below 40% HP: heal 15 + 50% melee, 3 turns |
| **Plague Doctor** | Miasma | AoE+CC | 6 | 10 dmg + slow r=2, 2 turns |
| | Plague Flask | DoT | 4 | 8/turn × 4 turns (32 total, ignores armor) |
| | Enfeeble | AoE Debuff | 5 | -25% damage dealt r=2, 4 turns |
| | Inoculate | Buff+Cleanse | 5 | +3 armor, 3 turns + cleanse DoTs |
| **Revenant** | Grave Thorns | Thorns | 5 | Reflect 12/hit, 4 turns |
| | Grave Chains | Ranged Taunt | 5 | Taunt 1 enemy, 3 turns |
| | Undying Will | Cheat Death | 8 | Revive at 30% HP within 5 turns |
| | Soul Rend | Melee+CC | 4 | 1.5× melee + slow 2 turns |
| **Shaman** | Healing Totem | Totem Heal | 6 | 8 HP/turn to allies r=2, 4 turns |
| | Searing Totem | Totem Damage | 6 | 4 dmg/turn (−armor) to enemies r=2, 4 turns |
| | Soul Anchor | Death Prevent | 10 | Ally survives death at 1 HP, 4-turn window |
| | Earthgrasp | AoE Root | 7 | Root enemies r=2, 2 turns |

---

## Weapon Category Access

| Class | Melee | Ranged | Caster | Hybrid |
|-------|:-----:|:------:|:------:|:------:|
| Crusader | ✓ | — | — | ✓ |
| Confessor | ✓ | — | ✓ | ✓ |
| Inquisitor | — | ✓ | ✓ | ✓ |
| Ranger | — | ✓ | — | ✓ |
| Hexblade | ✓ | ✓ | ✓ | ✓ |
| Mage | — | — | ✓ | ✓ |
| Bard | — | — | ✓ | ✓ |
| Blood Knight | ✓ | — | — | ✓ |
| Plague Doctor | — | — | ✓ | ✓ |
| Revenant | ✓ | — | — | ✓ |
| Shaman | — | — | ✓ | ✓ |

---

## Design Notes & Balance Philosophy

### Role Distribution (11 classes)

| Role Category | Classes | Count |
|--------------|---------|:-----:|
| **Tank** | Crusader, Revenant | 2 |
| **Healer/Support** | Confessor, Shaman | 2 |
| **Offensive Support** | Bard | 1 |
| **Melee DPS** | Hexblade, Blood Knight | 2 |
| **Ranged DPS** | Ranger | 1 |
| **Caster DPS** | Mage | 1 |
| **Scout/Utility** | Inquisitor | 1 |
| **Controller** | Plague Doctor | 1 |

### Key Differentiators Between Similar Roles

**Crusader vs Revenant (Tanks):**
- Crusader: Damage *mitigation* — high armor, Bulwark, Taunt, off-heals. Protects allies.
- Revenant: Damage *retaliation* — thorns, cheat death, forced aggro. Punishes attackers.

**Confessor vs Shaman (Healers):**
- Confessor: *Targeted* healing — burst heal, HoT, single-target armor buff. Reactive.
- Shaman: *Zone* healing — totem placement, AoE root, death prevention. Proactive/positional.

**Hexblade vs Blood Knight (Melee DPS):**
- Hexblade: *Versatile* — ranged DoT, reflect, teleport. Hybrid pressure from any range.
- Blood Knight: *Sustain* — pure melee, lifesteal on everything. Out-sustains in prolonged fights.

**Bard vs Confessor (Supports):**
- Confessor: Keeps the party *alive* (heals, shields, Prayer).
- Bard: Makes the party *lethal* (damage buffs, enemy debuffs, cooldown reduction).

### Balance Target

All classes aim for ~50% win rate in randomized 5v5 team compositions. Recent batch PvP simulations (March 2026) show all 11 classes within the 46–54% range after tuning passes.

> **Note (v0.1.5):** Pre-v0.1.5 batch PvP data is unreliable — Team A units were frozen due to a dummy-host AI ownership bug causing all matches to draw. Win rates were corrected after the fix in v0.1.5.

### Damage Type Summary

| Damage Type | Armor Interaction | Used By |
|-------------|-------------------|---------|
| Physical (melee/ranged) | Full armor reduction | Most classes |
| Magic | 50% armor effectiveness | Mage (Fireball, Frost Nova, Arcane Barrage) |
| Holy | Full armor reduction, bonus vs tags | Inquisitor (Rebuke, Seal), Confessor (Exorcism) |
| DoT (Wither, Plague Flask) | Ignores armor entirely | Hexblade, Plague Doctor |
| Reflect/Thorns | Ignores armor | Hexblade (Ward), Revenant (Grave Thorns) |
| Totem (Searing) | Reduced by armor | Shaman |

---

## AI Behavior Notes (v0.1.4–v0.1.5e)

Recent updates introduced role-aware AI stances and support-class positioning logic. These don't change class stats or skill effects, but significantly affect how classes play in practice.

### Stance System (v0.1.4)

| Stance | Support Behavior | Ranged DPS Behavior |
|--------|-----------------|--------------------|
| **Aggressive** | Position near allies, not enemies | Kite in formation (Bard uses ally centroid) |
| **Defensive** | Stay near allies | Range-based kiting (Controllers ≤3 tiles, others ≤2) |
| **Follow** | Ally-aware positioning (not generic nearest-ally) | Standard follow |
| **Hold** | Smart target selection via `_pick_best_target()` | Smart target selection |

### Confessor AI (v0.1.5e)

- **Shield of Faith** now fires after reposition check (priority 4.0 → 4.7), fixing ~56% self-cast rate
- Reposition threshold raised (60% → 80% HP) — Confessor seeks injured allies earlier
- Tank-aware movement: prioritizes most injured ally below 60% HP → tank outside heal range → nearest ally

### Shaman AI (v0.1.5f)

- Anti-clumping: Shaman ignores other support allies when choosing movement targets
- Movement priority: (1) Stay near own healing totem → (2) Injured tank <70% HP → (3) Nearest tank → (4) Most injured ally → (5) Nearest ally

---

> **Source files:** `server/configs/classes_config.json`, `server/configs/skills_config.json`, `server/configs/combat_config.json`
>
> When stats change, update this document to stay in sync with the configs.
