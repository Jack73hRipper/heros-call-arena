# Enemy Roster System — Procedural Dungeon Spawning Overhaul

**Date:** February 24, 2026  
**Scope:** Procedural dungeon enemy variety  
**Files Modified:** 3 files, 5 new tests

---

## Problem

The procedural dungeon system used a **single enemy type per floor tier**. The old `_FLOOR_ENEMY_TYPES` mapping assigned exactly ONE regular enemy ("E") and ONE boss ("B") per floor range:

```
Floors 1-2:  ALL regular enemies = skeleton,  boss = demon
Floors 3-4:  ALL regular enemies = demon,     boss = undead_knight
Floors 5-6:  ALL regular enemies = wraith,    boss = undead_knight
Floors 7-8:  ALL regular enemies = werewolf,  boss = reaper
Floors 9+:   ALL regular enemies = construct, boss = reaper
```

This meant **every "E" tile on a given floor became the same enemy type** — zero intra-floor variety. Additionally, **4 of 11 combat enemies never spawned** in procedural dungeons at all:

| Never Spawned | Role |
|---|---|
| `imp` | Swarm |
| `dark_priest` | Enemy Healer |
| `medusa` | Debuff Caster |
| `acolyte` | Enemy Support |

---

## Solution: Weighted Enemy Rosters

Replaced the single-type mapping with **weighted enemy pools per floor tier**, organized into three roles:

### Roles

| Role | Tile | Description |
|---|---|---|
| **regular** | `E` | Standard enemies — each "E" tile draws independently from the weighted pool |
| **boss** | `B` | Boss/elite enemies — "B" tiles draw from the boss pool |
| **support** | — | Healer/support enemies — rooms with 2+ regular enemies have a 30% chance to swap one into a support unit |

### Floor Rosters

| Floor Tier | Regular Pool | Boss Pool | Support Pool |
|---|---|---|---|
| **1-2** (Early) | skeleton 45%, imp 35%, acolyte 20% | demon 100% | dark_priest 70%, acolyte 30% |
| **3-4** (Mid-early) | demon 35%, skeleton 25%, imp 20%, medusa 20% | undead_knight 100% | dark_priest 50%, acolyte 50% |
| **5-6** (Mid) | wraith 30%, medusa 25%, demon 20%, werewolf 15%, imp 10% | undead_knight 60%, reaper 40% | dark_priest 40%, acolyte 30%, medusa 30% |
| **7-8** (Late) | werewolf 30%, construct 25%, wraith 25%, medusa 20% | reaper 100% | dark_priest 50%, acolyte 50% |
| **9+** (Deep) | construct 25%, werewolf 25%, wraith 20%, demon 15%, medusa 15% | reaper 70%, undead_knight 30% | dark_priest 40%, acolyte 30%, medusa 30% |

### Support Swap Mechanic

When a room has **2 or more regular "E" tiles**, there is a **30% chance** (`_SUPPORT_SWAP_CHANCE`) that one enemy slot becomes a **support unit** drawn from the support pool. This creates tactical encounters where players must prioritize targets (kill the healer first!).

---

## Files Changed

### `server/app/core/wfc/dungeon_generator.py`

- **Replaced** `_FLOOR_ENEMY_TYPES` single-type mapping with `_FLOOR_ENEMY_ROSTER` weighted pools
- **Derived** `_FLOOR_ENEMY_TYPES` automatically from roster (highest-weighted entry) for backward compatibility
- **Added** `_SUPPORT_SWAP_CHANCE = 0.30` constant
- **Added** `_pick_weighted(pool, rng_func)` — weighted random selection helper
- **Added** `resolve_enemy_for_tile(tile, roster, rng_func, is_support_swap)` — public enemy resolution API
- **Added** `get_floor_roster(floor_number)` — returns the roster for a given floor
- **Updated** `validate_enemy_types()` to iterate all roster entries (not just primary types)
- **Updated** `FloorConfig` — added `enemy_roster` field alongside existing `enemy_types`
- **Updated** `FloorConfig.from_floor_number()` — populates both `enemy_types` and `enemy_roster`
- **Updated** `generate_dungeon_floor()` — passes `enemy_roster` and `seed` to `export_to_game_map()`

### `server/app/core/wfc/map_exporter.py`

- **Added** `enemy_roster` and `seed` parameters to `export_to_game_map()`
- **Added** `_resolve_enemy()` inner function — uses roster when available, falls back to legacy `enemy_types` dict
- **Added** per-room regular enemy pre-count for support swap eligibility
- **Added** per-room support tracking (max one support swap per room)
- Each "E" tile now independently draws from the weighted pool via seeded RNG (deterministic)
- Each "B" tile draws from the boss pool

### `server/tests/test_wfc_dungeon.py`

- **Updated** `test_generated_enemies_match_floor_types` → `test_generated_enemies_match_floor_roster` — validates enemies come from the full roster pool
- **Added** `test_floor_roster_has_all_roles` — verifies each floor tier has regular/boss/support pools with 2+ regular types
- **Added** `test_roster_produces_varied_enemies` — 50 rolls confirms multiple distinct enemy IDs
- **Added** `test_support_swap_produces_support_enemies` — verifies support swap draws from the support pool
- **Added** `test_legacy_enemy_types_derived_from_roster` — confirms backward-compatible `enemy_types` accessor

---

## Backward Compatibility

- `FloorConfig.enemy_types` still works as a `{"E": str, "B": str}` dict (auto-derived from highest-weighted roster entries)
- `export_to_game_map()` falls back to the old `enemy_types` dict if `enemy_roster` is `None`
- The output format (`room["enemy_spawns"]` with `enemy_type` strings) is completely unchanged
- `_spawn_dungeon_enemies()` in `match_manager.py` required **zero changes**
- All legacy tests continue to pass with identical assertions

## Test Results

- **1641 tests passed, 0 failures** (up from 1636 — 5 new tests added)
- Full backward compatibility verified across all 42 test files

---

## Design Notes

- **Deterministic**: All roster picks use seeded RNG (`floor_seed`) — same seed + floor = same enemies every time
- **Tunable**: Weights are relative floats; adjusting `("imp", 0.35)` → `("imp", 0.50)` increases imp frequency without touching other code
- **Extensible**: Adding a new enemy to `enemies_config.json` only requires adding it to the appropriate roster tier(s)
- **No new dependencies**: Uses only stdlib `random.Random` for weighted selection
