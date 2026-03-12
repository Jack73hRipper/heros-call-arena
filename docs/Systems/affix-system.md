# Affix System — Prefix & Suffix Reference

**Created:** March 3, 2026
**Config:** `server/configs/affixes_config.json`
**Generator:** `server/app/core/item_generator.py`
**Phase:** 16B (Affix System & Item Generation)

---

## Overview

Items in Arena use a **prefix/suffix affix system** inspired by Diablo-style loot. Every dropped item has a **base type** with fixed stats, and then **random affixes** are rolled on top based on rarity tier. Each affix adds a random stat bonus within a defined range, scaled by item level.

The combination of base type + affixes makes every item potentially unique — two "Greatswords" can have completely different stat profiles.

### How Affixes Roll

| Rarity | Prefixes | Suffixes | Total Affixes |
|--------|----------|----------|---------------|
| Common (gray) | 0 | 0 | 0 |
| Magic (blue) | 0–1 | 0–1 | 1–2 (at least 1) |
| Rare (yellow) | 1–2 | 1–2 | 3–4 (at least 3) |
| Epic (purple) | 2–3 | 2–3 | 4–5 |
| Unique (orange) | N/A — fixed curated stats | N/A | N/A |
| Set (green) | N/A — fixed curated stats | N/A | N/A |

### Key Rules

- **No duplicate stats** — an item can't roll two affixes that modify the same stat
- **Slot-filtered** — each affix specifies which equipment slots it can appear on
- **Weight-based selection** — higher weight = more likely to be chosen
- **Item level scaling** — higher item level = higher potential affix values
- **One prefix, one suffix per stat** — the system won't roll e.g. both "Cruel" (prefix, attack_damage) and "of the Wolf" (suffix, attack_damage) on the same item since they share the `attack_damage` stat

### Affix Value Formula

```
effective_max = min(max_value, min_value + ilvl_scaling × item_level)
rolled_value  = random.uniform(min_value, effective_max)
```

At low item levels, affixes roll near their minimum. At high item levels, affixes can reach their maximum.

### Name Generation

```
Magic:   "{Prefix} {BaseName}"           → "Cruel Greatsword"
         "{BaseName} {Suffix}"           → "Greatsword of the Bear"
         "{Prefix} {BaseName} {Suffix}"  → "Cruel Greatsword of the Bear"
Rare:    Random grimdark name            → "Doomcleaver" (affixes shown in tooltip)
Epic:    Random grimdark name            → "The Ashen Verdict"
```

---

## Prefixes (16 total)

Prefixes appear before the item name: *"**Cruel** Greatsword"*

### Offensive Prefixes

| ID | Name | Stat | Min | Max | iLvl Scale | Weight | Slots | Description |
|----|------|------|-----|-----|------------|--------|-------|-------------|
| `cruel` | Cruel | `attack_damage` | 3 | 12 | 0.5 | 100 | weapon | Flat melee damage — bread-and-butter melee prefix |
| `piercing` | Piercing | `ranged_damage` | 3 | 12 | 0.5 | 100 | weapon | Flat ranged damage — bread-and-butter ranged prefix |
| `deadly` | Deadly | `crit_chance` | 2% | 10% | 0.3% | 70 | weapon, accessory | Crit chance — pairs multiplicatively with Savage |
| `savage` | Savage | `crit_damage` | +10% | +50% | 2% | 60 | weapon, accessory | Crit damage multiplier — high ceiling, build-defining |
| `vampiric` | Vampiric | `life_on_hit` | 1 | 5 | 0.3 | 50 | weapon | Sustain through damage — melee-focused |
| `empowered` | Empowered | `skill_damage_pct` | 5% | 20% | 1% | 50 | weapon, accessory | All skill damage — class-agnostic caster stat |
| `penetrating` | Penetrating | `armor_pen` | 1 | 5 | 0.2 | 40 | weapon | Ignores flat armor — strong vs. tanky targets |
| `precise` | Precise | `ranged_damage` | 2 | 8 | 0.4 | 70 | accessory | Ranged damage on accessories — gives Rangers non-weapon options |

### Defensive Prefixes

| ID | Name | Stat | Min | Max | iLvl Scale | Weight | Slots | Description |
|----|------|------|-----|-----|------------|--------|-------|-------------|
| `armored` | Armored | `armor` | 1 | 6 | 0.3 | 80 | weapon, armor, accessory | Flat armor — universal defensive filler |
| `thorned` | Thorned | `thorns` | 2 | 8 | 0.4 | 40 | armor | Flat reflect damage — punishes attackers |
| `sturdy` | Sturdy | `max_hp` | 8 | 40 | 2.0 | 80 | armor, accessory | Flat HP — fills the "no HP prefix" gap |
| `resilient` | Resilient | `damage_reduction_pct` | 2% | 8% | 0.4% | 45 | armor | % damage reduction — stacks with flat armor |
| `regenerating` | Regenerating | `hp_regen` | 1 | 5 | 0.3 | 45 | armor | HP per turn — sustained survivability |

### Class/Build Prefixes

| ID | Name | Stat | Min | Max | iLvl Scale | Weight | Slots | Description |
|----|------|------|-----|-----|------------|--------|-------|-------------|
| `venomous` | Venomous | `dot_damage_pct` | 5% | 20% | 1% | 35 | weapon, accessory | DoT damage — Hexblade (Wither), Ranger (poison) |
| `holy` | Holy | `holy_damage_pct` | 5% | 20% | 1% | 35 | weapon, accessory | Holy damage — Confessor (Exorcism), Inquisitor (Rebuke) |
| `blessed` | Blessed | `heal_power_pct` | 5% | 15% | 0.8% | 40 | weapon, armor | Heal power — Confessor healing builds |

---

## Suffixes (15 total)

Suffixes appear after the item name: *"Greatsword **of the Bear**"*

### Defensive Suffixes

| ID | Name | Stat | Min | Max | iLvl Scale | Weight | Slots | Description |
|----|------|------|-----|-----|------------|--------|-------|-------------|
| `of_the_bear` | of the Bear | `max_hp` | 10 | 60 | 3.0 | 100 | weapon, armor, accessory | Flat HP — highest weight suffix, universal |
| `of_iron` | of Iron | `armor` | 2 | 8 | 0.4 | 90 | armor, accessory | Flat armor — staple defensive suffix |
| `of_evasion` | of Evasion | `dodge_chance` | 2% | 10% | 0.4% | 60 | armor, accessory | Dodge chance — avoidance builds |
| `of_resilience` | of Resilience | `damage_reduction_pct` | 2% | 12% | 0.5% | 50 | armor, accessory | % DR — strong scaling at high values |
| `of_thorns` | of Thorns | `thorns` | 1 | 6 | 0.3 | 40 | armor, accessory | Reflect damage as suffix — pairs with Thorned prefix but stat dedup prevents doubling |

### Sustain Suffixes

| ID | Name | Stat | Min | Max | iLvl Scale | Weight | Slots | Description |
|----|------|------|-----|-----|------------|--------|-------|-------------|
| `of_regeneration` | of Regeneration | `hp_regen` | 1 | 8 | 0.5 | 55 | armor, accessory | HP per turn — strong in long dungeon runs |
| `of_the_leech` | of the Leech | `life_on_hit` | 1 | 4 | 0.2 | 45 | armor, accessory | Life on hit as suffix — non-weapon sustain option |

### Offensive Suffixes

| ID | Name | Stat | Min | Max | iLvl Scale | Weight | Slots | Description |
|----|------|------|-----|-----|------------|--------|-------|-------------|
| `of_the_wolf` | of the Wolf | `attack_damage` | 2 | 8 | 0.4 | 70 | weapon, accessory | Flat melee damage suffix — mirrors "of the Bear" for damage |
| `of_the_hawk` | of the Hawk | `ranged_damage` | 2 | 8 | 0.4 | 70 | weapon, accessory | Flat ranged damage suffix — Ranger power suffix |
| `of_precision` | of Precision | `crit_chance` | 1% | 6% | 0.3% | 50 | weapon, armor | Crit as suffix — enables crit stacking on non-accessory slots |
| `of_the_sage` | of the Sage | `skill_damage_pct` | 3% | 12% | 0.8% | 45 | armor | Skill damage on armor — caster gear identity |

### Utility Suffixes

| ID | Name | Stat | Min | Max | iLvl Scale | Weight | Slots | Description |
|----|------|------|-----|-----|------------|--------|-------|-------------|
| `of_haste` | of Haste | `cooldown_reduction_pct` | 3% | 12% | 0.5% | 50 | weapon, armor, accessory | CDR — universally desirable for skill-based builds |
| `of_mending` | of Mending | `heal_power_pct` | 5% | 20% | 1% | 35 | weapon, accessory | Heal power — Confessor suffix |
| `of_greed` | of Greed | `gold_find_pct` | 5% | 30% | 1.5% | 30 | armor, accessory | Gold find — farming quality-of-life |
| `of_fortune` | of Fortune | `magic_find_pct` | 3% | 20% | 1% | 30 | armor, accessory | Magic find — the gear tension stat (MF gear vs. combat gear) |

---

## Slot Coverage Matrix

What affixes can appear on each equipment slot:

### Weapon Prefixes & Suffixes

| Prefix | Stat | Suffix | Stat |
|--------|------|--------|------|
| Cruel | attack_damage | of the Bear | max_hp |
| Piercing | ranged_damage | of Haste | CDR |
| Deadly | crit_chance | of the Wolf | attack_damage |
| Savage | crit_damage | of the Hawk | ranged_damage |
| Vampiric | life_on_hit | of Precision | crit_chance |
| Armored | armor | of Mending | heal_power_pct |
| Empowered | skill_damage_pct | | |
| Penetrating | armor_pen | | |
| Venomous | dot_damage_pct | | |
| Holy | holy_damage_pct | | |
| Blessed | heal_power_pct | | |
| **11 prefixes** | | **6 suffixes** | |

### Armor Prefixes & Suffixes

| Prefix | Stat | Suffix | Stat |
|--------|------|--------|------|
| Thorned | thorns | of the Bear | max_hp |
| Armored | armor | of Iron | armor |
| Sturdy | max_hp | of Evasion | dodge_chance |
| Resilient | damage_reduction_pct | of Haste | CDR |
| Regenerating | hp_regen | of Regeneration | hp_regen |
| Blessed | heal_power_pct | of the Leech | life_on_hit |
| | | of Resilience | damage_reduction_pct |
| | | of Precision | crit_chance |
| | | of Thorns | thorns |
| | | of the Sage | skill_damage_pct |
| | | of Greed | gold_find_pct |
| | | of Fortune | magic_find_pct |
| **6 prefixes** | | **12 suffixes** | |

### Accessory Prefixes & Suffixes

| Prefix | Stat | Suffix | Stat |
|--------|------|--------|------|
| Deadly | crit_chance | of the Bear | max_hp |
| Savage | crit_damage | of Iron | armor |
| Armored | armor | of Evasion | dodge_chance |
| Empowered | skill_damage_pct | of Haste | CDR |
| Precise | ranged_damage | of Regeneration | hp_regen |
| Sturdy | max_hp | of the Leech | life_on_hit |
| Venomous | dot_damage_pct | of Resilience | damage_reduction_pct |
| Holy | holy_damage_pct | of Thorns | thorns |
| | | of the Wolf | attack_damage |
| | | of the Hawk | ranged_damage |
| | | of Mending | heal_power_pct |
| | | of Greed | gold_find_pct |
| | | of Fortune | magic_find_pct |
| **8 prefixes** | | **13 suffixes** | |

---

## Weight Distribution

Weights determine how likely each affix is to be selected during rolling. Higher weight = more common.

### Prefix Weights (total: 940)

| Weight | Affixes | Category |
|--------|---------|----------|
| 100 | Cruel, Piercing | Core damage — most common |
| 80 | Armored, Sturdy | Core defense — very common |
| 70 | Deadly, Precise | Crit/ranged — common |
| 60 | Savage | Crit damage — above average |
| 50 | Vampiric, Empowered | Sustain/skill — moderate |
| 45 | Resilient, Regenerating | Defensive niche — moderate |
| 40 | Thorned, Penetrating, Blessed | Niche builds — less common |
| 35 | Venomous, Holy | Class-specific — rare |

### Suffix Weights (total: 830)

| Weight | Affixes | Category |
|--------|---------|----------|
| 100 | of the Bear | HP — most common suffix |
| 90 | of Iron | Armor — very common |
| 70 | of the Wolf, of the Hawk | Flat damage — common |
| 60 | of Evasion | Dodge — above average |
| 55 | of Regeneration | HP regen — moderate |
| 50 | of Haste, of Resilience, of Precision | Utility/defense — moderate |
| 45 | of the Leech, of the Sage | Sustain/caster — moderate |
| 40 | of Thorns | Reflect — less common |
| 35 | of Mending | Heal power — less common |
| 30 | of Greed, of Fortune | MF/GF farming — rare |

---

## Stat Coverage Summary

Which stats can appear as prefixes, suffixes, or both:

| Stat | Prefix | Suffix | Notes |
|------|--------|--------|-------|
| `attack_damage` | Cruel | of the Wolf | Melee builds can double-dip on weapons |
| `ranged_damage` | Piercing, Precise | of the Hawk | Ranged builds have weapon + accessory options |
| `crit_chance` | Deadly | of Precision | Available on almost all slots |
| `crit_damage` | Savage | — | Prefix only — keeps crit damage rare |
| `armor` | Armored | of Iron | Universal defensive coverage |
| `max_hp` | Sturdy | of the Bear | Most common defensive stats |
| `life_on_hit` | Vampiric | of the Leech | Weapon (prefix) or armor/accessory (suffix) |
| `thorns` | Thorned | of Thorns | Can't stack on same item (stat dedup) |
| `hp_regen` | Regenerating | of Regeneration | Can't stack on same item (stat dedup) |
| `damage_reduction_pct` | Resilient | of Resilience | Can't stack on same item (stat dedup) |
| `dodge_chance` | — | of Evasion | Suffix only — keeps dodge scarce |
| `cooldown_reduction_pct` | — | of Haste | Suffix only — prevents CDR stacking abuse |
| `skill_damage_pct` | Empowered | of the Sage | Prefix on weapons, suffix on armor |
| `armor_pen` | Penetrating | — | Prefix only, weapon only — prevents armor becoming useless |
| `heal_power_pct` | Blessed | of Mending | Prefix on weapon/armor, suffix on weapon/accessory |
| `dot_damage_pct` | Venomous | — | Prefix only — class-specific |
| `holy_damage_pct` | Holy | — | Prefix only — class-specific |
| `gold_find_pct` | — | of Greed | Suffix only — farming stat |
| `magic_find_pct` | — | of Fortune | Suffix only — farming stat |

---

## Removed Affixes

| ID | Name | Stat | Reason Removed |
|----|------|------|----------------|
| `swift` | Swift | `move_speed` | **Game-breaking in 1-tile/turn system.** Base movement is 1 tile per turn; even +1 move_speed doubles mobility, breaking AI pathfinding assumptions, enabling unkitable ranged builds, and invalidating crowd control. Movement speed is reserved exclusively for curated unique/set items with deliberate trade-offs (e.g., Grimfang's on-kill haste buff, The Bonecage's −3 penalty). |

---

## Design Philosophy

### Why These Weights?

- **Core stats (100)** — damage and HP should appear on most items so items always feel useful
- **Defense (80–90)** — armor and HP are common but not boring; they're the baseline
- **Offense (60–70)** — crit, ranged damage are exciting but shouldn't dominate every drop
- **Utility (45–55)** — CDR, sustain, skill damage are build-defining but should feel special
- **Niche (30–40)** — MF, GF, thorns, class-specific stats are chase affixes

### Why Some Stats Are Prefix-Only or Suffix-Only?

- **Crit damage (prefix only)** — if both prefix AND suffix existed, Rare items could stack enormous crit multipliers
- **Dodge (suffix only)** — dodge is already capped at 40%; limiting sources keeps it scarce
- **CDR (suffix only)** — CDR is capped at 30%; prefix + suffix would trivialize the cap
- **Armor Pen (prefix only)** — too much armor pen would make armor stat worthless
- **Class stats (prefix only)** — DoT%, Holy%, and Heal Power% as prefixes means they only appear on "intentional" items, not random armor drops

### Slot Design Philosophy

- **Weapons** — most offensive prefixes, fewer suffixes → weapons are the damage source
- **Armor** — most defensive suffixes, fewer prefixes → armor is the survivability source  
- **Accessories** — broadest variety of both → accessories are the "build glue" that fills gaps

---

## Class Build Archetypes

What a well-geared character of each class might look for:

### Crusader (Melee Tank)
- **Weapon:** Cruel + of the Bear / of the Wolf
- **Armor:** Sturdy / Resilient + of Iron / of Resilience
- **Accessory:** Armored + of the Bear

### Confessor (Healer)
- **Weapon:** Blessed / Holy + of Mending
- **Armor:** Blessed / Sturdy + of Regeneration / of the Sage
- **Accessory:** Empowered + of the Bear / of Haste

### Inquisitor (Ranged Caster)
- **Weapon:** Empowered / Holy + of the Hawk / of Haste
- **Armor:** Sturdy + of the Sage / of Haste
- **Accessory:** Deadly / Savage + of the Hawk / of Precision

### Ranger (Ranged DPS)
- **Weapon:** Piercing + of the Hawk / of Precision
- **Armor:** Sturdy + of Evasion / of Precision
- **Accessory:** Precise / Deadly + of the Hawk / of Evasion

### Hexblade (Hybrid DPS)
- **Weapon:** Venomous / Cruel + of the Wolf / of Haste
- **Armor:** Sturdy + of the Sage / of Evasion
- **Accessory:** Venomous / Savage + of the Wolf / of Haste

---

## Modification Guide

### Adding a New Affix

1. Add entry to `server/configs/affixes_config.json` under `prefixes` or `suffixes`
2. Required fields: `affix_id`, `name`, `stat`, `min_value`, `max_value`, `ilvl_scaling`, `weight`, `allowed_slots`, `description`
3. The `stat` must match a field name in `StatBonuses` (see `server/app/models/items.py`)
4. Run tests: `python -m pytest server/tests/ -x -q`
5. Update this reference doc

### Adjusting Balance

- **Too common?** Lower the `weight`
- **Too strong at high levels?** Lower `ilvl_scaling` or `max_value`
- **Appearing on wrong items?** Adjust `allowed_slots`
- **Too weak early game?** Raise `min_value`

### Adding a New Stat

1. Add field to `StatBonuses` in `server/app/models/items.py`
2. Add field to `PlayerState` in `server/app/models/player.py`
3. Add aggregation in `equipment_manager.py` → `_recalculate_effective_stats()`
4. Add combat/skill integration as needed
5. Add display in `client/src/utils/itemUtils.js` → `formatStatBonuses()`
6. Create affixes that use the new stat
7. Update this reference doc
