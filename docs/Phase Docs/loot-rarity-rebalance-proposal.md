# Loot Rarity Rebalance Proposal

**Date:** March 17, 2026  
**Status:** Proposed  
**Affects:** `item_generator.py`, `loot.py`, `loot_tables.json`

---

## Problem Statement

Rare (yellow) and higher-tier items drop far too frequently on early floors. On floor 1, a normal enemy kill produces a **Rare item ~12% of the time** — roughly 1 in 8 drops. Chests are even worse because `generate_chest_loot()` uses `enemy_tier="mid"` for *all* non-boss chests, inflating Rare rates to **~13.4% from a wooden chest on floor 1**.

The result: yellow-name items don't feel special. Players see them constantly from the start, and there's little sense of loot progression between floor 1 and floor 9.

---

## Current Rates (Old)

### Base Rarity Weights

| Rarity | Weight | Color |
|--------|--------|-------|
| Common | 60.0 | Gray `#9d9d9d` |
| Magic | 25.0 | Blue `#4488ff` |
| **Rare** | **12.0** | **Yellow `#ffcc00`** |
| Epic | 2.5 | Purple `#b040ff` |
| Unique | 0.5 | Orange `#ff8800` |

### Floor Bonuses (Old)

| Floors | Bonus |
|--------|-------|
| 1–2 | 0.00 |
| 3–4 | 0.15 |
| 5–6 | 0.35 |
| 7–8 | 0.60 |
| 9+ | 1.00 |

### Current Floor 1 Drop Rates

| Source | Common | Magic | Rare | Epic | Unique |
|--------|--------|-------|------|------|--------|
| Normal enemy (fodder) | 59.9% | 25.2% | **11.9%** | 2.5% | 0.5% |
| Wooden chest (uses mid) | 55.4% | 28.0% | **13.3%** | 2.8% | 0.6% |
| Boss chest (uses elite) | 49.8% | 31.4% | **15.0%** | 3.2% | 0.6% |
| Champion (fodder +0.25 MF) | 54.5% | 28.5% | **13.6%** | 2.9% | 0.6% |
| Rare monster (fodder +0.50 MF) | 49.9% | 31.3% | **14.9%** | 3.2% | 0.6% |

### Current Floor Progression (Fodder, MF=0)

| Floor | Common | Magic | Rare | Epic | Unique |
|-------|--------|-------|------|------|--------|
| 1 | 59.9% | 25.2% | 11.9% | 2.5% | 0.5% |
| 5 | 49.8% | 31.4% | 15.0% | 3.2% | 0.6% |
| 9 | 34.4% | 40.9% | 19.7% | 4.1% | 0.8% |

**Floor 1→9 Rare delta: only +7.8 percentage points.** Not enough to feel meaningful.

---

## Root Causes

1. **Rare base weight of 12.0 is too generous** — ~1 in 8 drops is Rare before any bonuses
2. **All chests use `enemy_tier="mid"`** — wooden chests on floor 1 roll like mid-tier monsters
3. **Floor scaling is too flat** — the 0.0→1.0 bonus range doesn't create enough spread
4. **Common weight formula is too gentle** — `max(0.2, 1.0 - bonus * 0.3)` barely moves the needle

---

## Proposed Changes

### Change 1: New Base Rarity Weights

| Rarity | Old Weight | **New Weight** | Change |
|--------|-----------|---------------|--------|
| Common | 60.0 | **70.0** | +10.0 |
| Magic | 25.0 | **20.0** | -5.0 |
| **Rare** | **12.0** | **7.0** | **-5.0** |
| Epic | 2.5 | **1.2** | -1.3 |
| Unique | 0.5 | **0.3** | -0.2 |

**File:** `item_generator.py` → `_BASE_RARITY_WEIGHTS`  
**File:** `loot_tables.json` → `rarity_config.base_rates`

### Change 2: Steeper Floor Bonus Curve

| Floors | Old Bonus | **New Bonus** | Change |
|--------|----------|-------------|--------|
| 1–2 | 0.00 | **0.00** | — |
| 3–4 | 0.15 | **0.20** | +0.05 |
| 5–6 | 0.35 | **0.50** | +0.15 |
| 7–8 | 0.60 | **0.90** | +0.30 |
| 9+ | 1.00 | **1.40** | +0.40 |

**File:** `item_generator.py` → `_FLOOR_BONUS`  
**File:** `loot_tables.json` → `rarity_config.floor_bonuses`

### Change 3: Common Weight Reduction Formula

```
Old: common_weight = base * max(0.2, 1.0 - (floor_bonus + tier_bonus) * 0.3)
New: common_weight = base * max(0.2, 1.0 - (floor_bonus + tier_bonus) * 0.4)
```

The `0.3` → `0.4` multiplier makes common items fall off faster on deeper floors, creating more room for magic/rare upgrades to fill the gap.

**File:** `item_generator.py` → `roll_rarity()`

### Change 4: Chest Tier Mapping Fix

Chests should use an `enemy_tier` that matches their actual quality, not blanket "mid" for everything.

| Chest Type | Old Tier | **New Tier** | Rationale |
|-----------|---------|-------------|-----------|
| Wooden | mid | **fodder** | Basic chest = basic loot |
| Iron | mid | **fodder** | Still early-game chest |
| Gold | mid | **mid** | Unchanged — gold chest earns mid |
| Obsidian | mid | **elite** | Rare chest deserves elite quality |
| Boss Chest | elite | **boss** | Boss room reward deserves boss tier |

**File:** `loot.py` → `generate_chest_loot()` — replace the blanket `chest_tier = "elite" if is_boss_chest else "mid"` with a mapping.

---

## Proposed Rates (Simulated — 100k rolls each)

### Floor 1 Drop Rates

| Source | Common | Magic | Rare | Epic | Unique |
|--------|--------|-------|------|------|--------|
| Normal enemy (fodder) | 71.0% | 20.2% | **7.2%** | 1.3% | 0.3% |
| Wooden chest (fodder) | 71.0% | 20.2% | **7.2%** | 1.3% | 0.3% |
| Boss chest (elite) | 60.9% | 27.5% | **9.6%** | 1.6% | 0.4% |
| Champion (+0.25 MF) | 66.2% | 23.6% | **8.3%** | 1.4% | 0.4% |
| Rare monster (+0.50 MF) | 62.0% | 26.7% | **9.3%** | 1.6% | 0.4% |

### Floor Progression (Fodder, MF=0)

| Floor | Common | Magic | Rare | Epic | Unique |
|-------|--------|-------|------|------|--------|
| 1 | 71.0% | 20.2% | 7.2% | 1.3% | 0.3% |
| 3 | 65.2% | 24.4% | 8.6% | 1.5% | 0.4% |
| 5 | 56.6% | 30.5% | 10.6% | 1.8% | 0.5% |
| 7 | 45.3% | 38.5% | 13.4% | 2.3% | 0.6% |
| 9 | 31.0% | 48.4% | 16.9% | 2.9% | 0.7% |

**Floor 1→9 Rare delta: +9.7 percentage points** (up from +7.8 old). Deeper floors feel noticeably more rewarding.

### Chest Progression (at earliest available floor)

| Chest | Tier | Floor | Common | Magic | Rare | Epic | Unique |
|-------|------|-------|--------|-------|------|------|--------|
| Wooden | fodder | 1 | 71.0% | 20.2% | 7.2% | 1.3% | 0.3% |
| Iron | fodder | 2 | 71.0% | 20.2% | 7.2% | 1.3% | 0.3% |
| Gold | mid | 4 | 60.9% | 27.5% | 9.6% | 1.6% | 0.4% |
| Obsidian | elite | 7 | 35.3% | 45.4% | 15.8% | 2.8% | 0.7% |
| Boss Chest | boss | 1 | 53.7% | 32.5% | 11.3% | 1.9% | 0.5% |

---

## Before/After Comparison — Floor 1 Fodder

| Rarity | OLD | NEW | Delta |
|--------|-----|-----|-------|
| Common | 59.9% | 71.0% | +11.1% |
| Magic | 25.2% | 20.2% | -5.0% |
| **Rare** | **11.9%** | **7.2%** | **-4.7%** |
| Epic | 2.5% | 1.3% | -1.2% |
| Unique | 0.5% | 0.3% | -0.2% |

### Before/After — Floor 1 Wooden Chest

| Rarity | OLD (mid tier) | NEW (fodder tier) | Delta |
|--------|---------------|-------------------|-------|
| Common | 55.4% | 71.0% | +15.6% |
| Magic | 28.0% | 20.2% | -7.8% |
| **Rare** | **13.3%** | **7.2%** | **-6.1%** |
| Epic | 2.8% | 1.3% | -1.5% |
| Unique | 0.6% | 0.3% | -0.3% |

---

## Design Intent

- **Floor 1 Rare (yellow) drops from ~12% to ~7%** — still ~1 in 14 drops, frequent enough to not feel punishing, rare enough to be exciting
- **Wooden/Iron chests no longer inflate rarity** — opening an early chest gives the same rates as killing a monster, not better
- **Gold/Obsidian/Boss chests are now more differentiated** — each tier feels like a meaningful upgrade
- **Floor progression is steeper** — floor 9 magic items are nearly half of all drops, rare items triple from floor 1
- **Epic items are genuinely rare early** — 1.3% on floor 1 (~1 in 77) makes purple drops feel electric
- **The system still respects ARPG dopamine** — you'll still find yellow items regularly, just not every few minutes on floor 1

---

## Files to Modify

| File | What Changes |
|------|-------------|
| `server/app/core/item_generator.py` | `_BASE_RARITY_WEIGHTS`, `_FLOOR_BONUS`, common weight formula in `roll_rarity()` |
| `server/app/core/loot.py` | Chest tier mapping in `generate_chest_loot()` |
| `server/configs/loot_tables.json` | `rarity_config.base_rates`, `rarity_config.floor_bonuses` (mirror of code values) |

---

## Unchanged Systems

- **Boss guaranteed rarity** (floor 1–4 → magic, 5–7 → rare, 8+ → epic) — no change
- **Monster rarity MF bonuses** (champion +0.25, rare +0.50, super unique +1.0) — no change
- **Unique/Set drop system** — no change
- **Chest tier spawn weights** (wooden 50, iron 30, gold 15, obsidian 5) — no change
- **Chest floor gating** (iron 2+, gold 4+, obsidian 7+) — no change
- **Enemy drop chances** (demon 0.6, skeleton 0.5, etc.) — no change
- **Item level calculation** — no change
- **Affix counts per rarity** — no change
