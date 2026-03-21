# Phase 28 QoL — AI Hero Equipment Intelligence Improvements

**Created:** March 20, 2026  
**Status:** ✅ COMPLETE  
**Previous:** Phase 28 (Enemy AI Equipment) — base system complete (loadouts, auto-equip, party distribution, item purging)  
**Goal:** Six targeted improvements to make AI hero party equipment behavior smarter, more efficient, and closer to what a real player would do.

---

## Already Completed (This Session)

- **28-QoL-0a: Common Starting Gear** — Hero loadouts now generate at `"common"` rarity instead of `"mid"` tier-boosted rarity. AI teams start on equal footing with human players.  
  - **File:** `server/app/core/loadout_generator.py` — `generate_hero_loadout()` (L173)

- **28-QoL-0b: Item Purge System** — After auto-equip + party distribution, AI heroes destroy equippable items that are not an upgrade for any living team member. Consumables are always kept.  
  - **File:** `server/app/core/equipment_manager.py` — `purge_unwanted_items()` (L586)  
  - **File:** `server/app/core/turn_phases/interaction_phase.py` — Phase 28G block (L342)

- **28-QoL-1: Accessory Slot Generation** — `generate_hero_loadout()` now generates a random common-rarity accessory after the armor block, filling the previously empty accessory slot. AI heroes spawn with all 3 equipment slots filled.  
  - **File:** `server/app/core/loadout_generator.py` — `# --- Accessory ---` block (~L258)

- **28-QoL-2: Weapon Class-Lock in Party Distribution** — `find_best_party_recipient()` now checks `allowed_weapon_categories` before scoring a weapon for a party member. Weapons are only routed to members whose class can actually equip them, preventing wasted transfers → purges.  
  - **File:** `server/app/core/equipment_manager.py` — class-lock guard in `find_best_party_recipient()` (~L578)  
  - **Test fix:** `server/tests/test_party_item_distribution.py` — Updated `test_item_goes_to_best_user` to use `weapon_category: "caster"` (matching the Mage's allowed categories) instead of `"ranged"`.

- **28-QoL-3: Potion Sharing Among Party Members** — New `balance_team_potions()` function redistributes consumables across AI hero team members until all are within ±1 of the average. Integrated as Phase 28H after the purge pass.  
  - **File:** `server/app/core/equipment_manager.py` — `balance_team_potions()` (~L669)  
  - **File:** `server/app/core/turn_phases/interaction_phase.py` — Phase 28H block after Phase 28G purge

- **28-QoL-4: Inventory Capacity Check in Distribution** — `find_best_party_recipient()` now skips members whose inventory is at or above `INVENTORY_MAX_CAPACITY` (10). Prevents items from being routed to full inventories.  
  - **File:** `server/app/core/equipment_manager.py` — capacity guard in `find_best_party_recipient()` member loop

- **28-QoL-5: Armor Affinity Awareness in Item Scoring** — `find_best_party_recipient()` now applies an affinity multiplier when routing armor: matching `preferred_armor` gets a `(1 + armor_affinity_bonus)×` boost; mismatched armor gets a `0.7×` penalty. Classes should now prefer their natural armor type.  
  - **File:** `server/app/core/equipment_manager.py` — affinity scoring in `find_best_party_recipient()` delta calculation

- **28-QoL-6: Equalized Scavenge Ranges** — `_SCAVENGE_MAX_RANGE` rebalanced: aggressive 5→3, ranged 3→4, support 3→5. Support heroes (furthest from combat) now sweep the widest area for ground loot.  
  - **File:** `server/app/core/ai_behavior.py` — `_SCAVENGE_MAX_RANGE` (~L123)  
  - **Test fix:** `server/tests/test_enemy_loot_pickup.py` — Updated `TestScavengeConstants` assertions to match new values

---

## Feature 1: Accessory Slot Generation

**Problem:** `generate_hero_loadout()` produces a weapon and armor but **no accessory**. AI heroes start with an empty accessory slot. They can only obtain one from ground loot — which may never happen in a short PVPVE match. Real players start with all three slots filled.

**Fix:**  
Add an accessory generation block to `generate_hero_loadout()` after the armor section. Pick a random accessory from `items_config` where `equip_slot == "accessory"`, generate at `"common"` rarity (matching the new baseline), and add to the equipment dict.

**Files to change:**
| File | Change |
|------|--------|
| `server/app/core/loadout_generator.py` | Add `# --- Accessory ---` block after armor block (~L250). Filter `items_config` for `equip_slot == "accessory"`, exclude consumables, `rng.choice()` from candidates, `generate_item(rarity="common")`, assign to `equipment["accessory"]`. |

**Validation:**
- Existing tests pass
- Batch PVP/PVPVE: verify AI heroes spawn with all 3 slots filled
- Inspect via dev overlay to confirm accessory appears

---

## Feature 2: Weapon Class-Lock in Party Distribution

**Problem:** `find_best_party_recipient()` scores items purely on stat weights and does not check `allowed_weapon_categories`. A high-damage sword could be routed to a Mage who cannot equip swords. The Mage receives it in inventory → `try_auto_equip()` silently rejects it (class-lock check in `equip_item()`) → the purge system destroys it. The team loses a potentially valuable weapon.

**Fix:**  
Add a weapon class-lock gate inside `find_best_party_recipient()`. When evaluating a weapon for a party member, skip that member if the weapon's `weapon_category` is not in their class's `allowed_weapon_categories`.

**Files to change:**
| File | Change |
|------|--------|
| `server/app/core/equipment_manager.py` | In `find_best_party_recipient()` (~L543), inside the member loop: if `slot == "weapon"`, load `class_def` for that member's `class_id`, and `continue` if `weapon_category not in class_def.allowed_weapon_categories`. |

**Validation:**
- Existing tests pass
- Run batch PVPVE and confirm weapons only route to members who can equip them
- Check combat log for absence of "destroyed [weapon] (no upgrade)" messages for class-locked items

---

## Feature 3: Potion Sharing Among Party Members

**Problem:** Consumables are explicitly excluded from party distribution (`find_best_party_recipient()` returns `None` for consumables). If one hero picks up 4 potions and a teammate has 0, no sharing happens. This reduces team survivability — a frontline Crusader might die with zero potions while the backline Ranger is hoarding 5.

**Fix:**  
Add a potion-sharing pass after the Phase 28F distribution in `interaction_phase.py`. For each AI hero unit that picked up consumables, count potions per team member. If any member has fewer potions, transfer excess until the team is roughly balanced (each member within ±1 of the average).

**Files to change:**
| File | Change |
|------|--------|
| `server/app/core/equipment_manager.py` | Add `balance_team_potions(team_members: list) -> list[dict]`. Counts potions per member, transfers from highest-count → lowest-count until balanced or capacity prevents it. Returns list of transfer event dicts for combat log. |
| `server/app/core/turn_phases/interaction_phase.py` | After the Phase 28G purge block (~L360), add a Phase 28H block that calls `balance_team_potions()` on the full team when `is_ai_hero` is true. Emit combat log messages for each transfer. |

**Validation:**
- Existing tests pass
- Batch PVPVE: observe potion counts across team members staying roughly balanced
- Edge case: team with 1 potion total → should go to lowest-HP member or just stay put

---

## Feature 4: Inventory Capacity Check in Distribution

**Problem:** `find_best_party_recipient()` does not check whether the recommended recipient has inventory space. If a member has 10/10 inventory, the item transfer silently fails (the item is removed from sender but the `append` on a full inventory still succeeds since Python lists have no max — but the member now exceeds the intended capacity). This can cause items to bypass `INVENTORY_MAX_CAPACITY`.

**Fix:**  
Add an inventory capacity check inside `find_best_party_recipient()`. Skip any member whose inventory is at or above `INVENTORY_MAX_CAPACITY`.

**Files to change:**
| File | Change |
|------|--------|
| `server/app/core/equipment_manager.py` | In `find_best_party_recipient()` (~L543), inside the member loop: import `INVENTORY_MAX_CAPACITY`, add `if len(member.inventory) >= INVENTORY_MAX_CAPACITY: continue` before scoring. |

**Validation:**
- Existing tests pass
- Edge case: all team members at 10/10 → item should stay with picker (or be purged)
- Verify no unit ever exceeds 10 inventory items in batch PVPVE logs

---

## Feature 5: Armor Affinity Awareness in Item Scoring

**Problem:** `score_item_for_role()` evaluates items on raw stat bonuses × role weights, but ignores the **armor affinity bonus** system. When a class wears their `preferred_armor` category, they get a configurable % bonus to that armor's base stats (via `_recalculate_effective_stats`). This means:

- A cloth robe with 5 armor on a Confessor (cloth preferred, 20% affinity) is really worth 6 effective armor
- A heavy plate with 8 armor on the same Confessor gives exactly 8 (no affinity bonus)
- The scorer picks the plate (8 > 5) but the real effective value is 8 vs 6 — a smaller gap than it appears, and the Confessor loses other affinity-boosted stats

This leads to suboptimal armor assignments, especially cross-category routing.

**Fix:**  
In `score_item_for_role()`, when scoring armor items, check if the item's `armor_category` matches the member's class `preferred_armor`. If it does, multiply the score by `(1 + armor_affinity_bonus)` to reflect the true effective value.

Alternatively, add a simpler approach: in `find_best_party_recipient()`, apply a **penalty multiplier** (e.g., 0.7×) when routing armor to a non-matching class, rather than modifying the scorer globally.

**Files to change:**
| File | Change |
|------|--------|
| `server/app/core/equipment_manager.py` | **Option A (preferred):** In `find_best_party_recipient()`, when `slot == "armor"`, load the member's `class_def`, check `preferred_armor` vs `item.armor_category`. If mismatch, apply `delta *= 0.7` penalty. If match, apply `delta *= 1.0 + class_def.armor_affinity_bonus` boost. |

**Validation:**
- Existing tests pass
- Batch PVPVE: cloth classes should mostly end up wearing cloth, heavy classes wearing heavy
- Edge case: a magic cloth armor vs a common heavy armor for a heavy class → heavy should still win

---

## Feature 6: Equalized Scavenge Ranges

**Problem:** Current scavenge ranges in `_SCAVENGE_MAX_RANGE`:
```python
"aggressive": 5,
"ranged":     3,
"support":    3,
```

Aggressive melee heroes get the longest loot-seeking range (5 tiles), but they're typically the most engaged in combat. Support and ranged heroes hang back and have more idle turns — they're better positioned to detour for loot, yet only search 3 tiles.

**Fix:**  
Equalize scavenge ranges so all roles search equally, or slightly favor support/ranged who are more likely to be idle near loot:

```python
_SCAVENGE_MAX_RANGE = {
    "aggressive": 3,
    "ranged":     4,
    "support":    5,
}
```

This way support heroes (who are furthest from combat) sweep the widest area, ranged heroes grab nearby items, and aggressive heroes focus on fighting with only short-range opportunistic pickups.

**Files to change:**
| File | Change |
|------|--------|
| `server/app/core/ai_behavior.py` | Update `_SCAVENGE_MAX_RANGE` dict (~L123). Change aggressive from 5→3, ranged from 3→4, support from 3→5. |

**Validation:**
- Existing tests pass
- Batch PVPVE: support heroes should pick up more loot, aggressive heroes should spend less time running after drops
- No behavior change for dungeon monsters (they already skip scavenging via `enemy_type` guard)

---

## Implementation Order

Recommended sequence (least risky → most complex):

| Order | Feature | Risk | Effort |
|-------|---------|------|--------|
| 1 | Feature 6: Scavenge ranges | Trivial — constant change | ~1 min |
| 2 | Feature 4: Inventory capacity check | Low — single guard clause | ~2 min |
| 3 | Feature 1: Accessory generation | Low — follows existing weapon/armor pattern | ~5 min |
| 4 | Feature 2: Weapon class-lock in distribution | Low — mirrors existing equip_item check | ~5 min |
| 5 | Feature 5: Armor affinity scoring | Medium — scoring interaction | ~10 min |
| 6 | Feature 3: Potion sharing | Medium — new function + integration | ~15 min |

**Total estimated scope:** ~6 targeted edits across 3 files, all backward-compatible.

---

## Test Strategy

All features should:
1. Pass existing 4040+ test suite (no regressions)
2. Be verifiable via **batch PVPVE** (`start-batch-pvpve.bat`) — run 50+ matches, inspect logs
3. Be visually verifiable via **dev overlay** equipment inspector (real-time equipment/inventory inspection)
