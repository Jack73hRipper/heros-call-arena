# Match Manager Split Plan

**Date:** March 19, 2026  
**File:** `server/app/core/match_manager.py`  
**Current size:** 3,220 lines · 55+ functions · 14 state dicts  
**Target:** Thin orchestrator (~300 lines) + 8 focused sub-modules  
**Precedent:** Phase 20 turn_resolver split (2,240 → 267 line orchestrator + 10 sub-modules)

---

## Why Split?

`match_manager.py` has grown into a god-module handling match lifecycle, action queues, payload serialization, lobby features, FOV caching, dungeon generation, PVPVE flow, and equipment loadouts. Five modules have already been extracted (auto_target, party_manager, hero_manager, equipment_manager, wave_spawner), but the remaining 3,220 lines still mix too many concerns.

---

## Safety Rules

1. **Keep the original file** — rename to `match_manager_BACKUP.py` before any edits
2. **Re-export everything** — `match_manager.py` re-exports all public symbols from sub-modules so **zero import changes** are needed in callers
3. **Run full test suite** after each phase to catch regressions immediately
4. **One module at a time** — extract, re-export, test, commit; then move to the next

---

## Architecture: Shared State Store

The key insight is that 14 in-memory dicts are the shared backbone. Extracting them first breaks the circular-dependency chain that currently forces everything into one file.

```
match_store.py          ← All 14 state dicts live here (single source of truth)
    ↑
    ├── match_manager.py        ← Thin orchestrator (lifecycle + AI spawn + re-exports)
    ├── action_queue.py         ← Action queue CRUD
    ├── match_payloads.py       ← WS payload builders
    ├── lobby_config.py         ← Lobby chat, config, class selection
    ├── fov_manager.py          ← FOV cache + dev mode
    ├── dungeon_manager.py      ← Dungeon lifecycle + enemy spawning
    ├── pvpve_manager.py        ← PVPVE match flow
    ├── loadout_generator.py    ← Enemy + hero equipment generation
    │
    ├── party_manager.py        ← (already extracted)
    ├── hero_manager.py         ← (already extracted)
    ├── equipment_manager.py    ← (already extracted)
    ├── wave_spawner.py         ← (already extracted)
    └── auto_target.py          ← (already extracted)
```

---

## Phase-by-Phase Extraction

### Phase 0: Backup & Baseline

- [x] Copy `match_manager.py` → `match_manager_BACKUP.py` ✅ (125 KB, 2026-03-19)

---

### Phase 1: `match_store.py` — Shared State (Foundation) ✅

**Status:** Complete — 2026-03-19 · 4040/4040 tests passing

This is the critical first step. All 14 state dicts move here, and every module (including the 5 already-extracted ones) imports from `match_store` instead of `match_manager`.

**Moves to `match_store.py`:**

| Symbol | Type | Line in Original |
|--------|------|-----------------|
| `_active_matches` | `dict[str, MatchState]` | 30 |
| `_player_states` | `dict[str, dict[str, PlayerState]]` | 31 |
| `_action_queues` | `dict[str, dict[str, list]]` | 34 |
| `_fov_cache` | `dict[str, dict[str, set]]` | 37 |
| `_lobby_chat` | `dict[str, list[dict]]` | 40 |
| `_class_selections` | `dict[str, dict[str, str]]` | 43 |
| `_hero_selections` | `dict[str, dict[str, list[str]]]` | 47 |
| `_hero_ally_map` | `dict[str, dict[str, str]]` | 51 |
| `_username_map` | `dict[str, dict[str, str]]` | 55 |
| `_kill_tracker` | `dict[str, dict[str, dict]]` | 58 |
| `_combat_stats` | `dict[str, dict[str, dict]]` | 61 |
| `_match_timeline` | `dict[str, list[dict]]` | 64 |
| `_controlled_hero_map` | `dict[str, dict[str, str]]` | 68 |
| `_wave_state` | `dict[str, dict]` | 71 |
| `_dev_mode_players` | `dict[str, set[str]]` | 74 |
| `MAX_QUEUE_SIZE` | `int` (10) | 76 |

**Migration steps:**
1. Create `match_store.py` with all dicts + constant
2. In `match_manager.py`, replace dict definitions with: `from app.core.match_store import *`
3. Update 5 already-extracted modules to import from `match_store`:
   - `hero_manager.py` — imports `_active_matches, _player_states, _hero_selections, _hero_ally_map, _username_map, _kill_tracker, _combat_stats, _match_timeline, _controlled_hero_map`
   - `party_manager.py` — imports `_player_states, _hero_ally_map, _action_queues`
   - `equipment_manager.py` — imports `_player_states`
   - `wave_spawner.py` — imports `_wave_state, _active_matches, _player_states`
   - `auto_target.py` — imports `_player_states`
4. Run tests — should be 100% green with zero import changes in callers

---

### Phase 2: `action_queue.py` — Action Queue ✅

**Status:** Complete — 2026-03-19 · 4040/4040 tests passing

**~100 lines** | 6 functions

Self-contained queue logic with no outbound dependencies beyond `match_store`.

**Moves to `action_queue.py`:**

| Function | Lines | Purpose |
|----------|-------|---------|
| `queue_action()` | 714–760 | Append action to player queue, auto-target handling |
| `pop_next_actions()` | 761–777 | Pop first action per player for tick |
| `get_and_clear_actions()` | 778–784 | Deprecated wrapper |
| `clear_player_queue()` | 785–793 | Clear all queued actions |
| `remove_last_action()` | 794–805 | Remove last queued action |
| `get_player_queue()` | 806–812 | Get copy of queue |

**Re-export in `match_manager.py`:**
```python
from app.core.action_queue import (
    queue_action, pop_next_actions, get_and_clear_actions,
    clear_player_queue, remove_last_action, get_player_queue,
)
```

---

### Phase 3: `fov_manager.py` — FOV Cache & Dev Mode ✅

**Status:** Complete — 2026-03-19 · 4040/4040 tests passing

**~80 lines** | 6 functions

Pure cache accessors. Zero coupling to game logic.

**Moves to `fov_manager.py`:**

| Function | Lines | Purpose |
|----------|-------|---------|
| `_compute_initial_fov()` | 834–862 | Compute FOV for all units at match start |
| `set_fov_cache()` | 1177–1183 | Store computed FOV |
| `get_fov_cache()` | 1184–1188 | Read cached FOV |
| `get_team_fov()` | 1189–1203 | Union of team members' FOV |
| `set_dev_mode()` | 1204–1214 | Enable/disable dev mode |
| `is_dev_mode()` | 1215–1219 | Check dev mode status |

**Re-export in `match_manager.py`:**
```python
from app.core.fov_manager import (
    _compute_initial_fov, set_fov_cache, get_fov_cache,
    get_team_fov, set_dev_mode, is_dev_mode,
)
```

---

### Phase 4: `match_payloads.py` — Payload Builders ✅

**Status:** Complete — 2026-03-19 · 4040/4040 tests passing

**~300 lines** | 5 functions

These are pure serializers — read state, produce dicts. No side effects.

**Moves to `match_payloads.py`:**

| Function | Lines | Purpose |
|----------|-------|---------|
| `get_match_start_payload()` | 863–992 | Full match_start WS message |
| `get_match_start_payload_for_player()` | 993–1047 | Per-player FOV-filtered payload |
| `get_player_joined_payload()` | 1048–1064 | player_joined broadcast payload |
| `get_lobby_players_payload()` | 1065–1113 | Lobby player list payload |
| `get_players_snapshot()` | 1114–1168 | Compact unit state for turn_result |

**Dependencies:** Reads from `match_store` dicts, calls `get_team_fov`, `get_fov_cache`, `get_party_members`, `get_match_teams` (all available via imports). Skills loader used inline.

**Re-export in `match_manager.py`:**
```python
from app.core.match_payloads import (
    get_match_start_payload, get_match_start_payload_for_player,
    get_player_joined_payload, get_lobby_players_payload,
    get_players_snapshot,
)
```

---

### Phase 5: `lobby_config.py` — Lobby Chat, Config & Class Selection ✅

**Status:** Complete — 2026-03-19 · 4040/4040 tests passing

**~300 lines** | 7 functions

All lobby-phase operations: chat, config updates, class picker, AI spawning trigger.

**Moves to `lobby_config.py`:**

| Function | Lines | Purpose |
|----------|-------|---------|
| `select_class()` | 511–535 | Player selects a class in lobby |
| `get_class_selection()` | 536–540 | Read player's class pick |
| `add_lobby_message()` | 1255–1283 | Add lobby chat message |
| `get_lobby_chat()` | 1284–1290 | Get all lobby messages |
| `update_match_config()` | 1291–1455 | Host changes match config |
| `get_match_config_payload()` | 1470–1501 | Serialize current config |
| `spawn_lobby_ai()` | 1456–1469 | Trigger AI spawn in lobby |

**Notes:** `update_match_config` calls `_spawn_ai_units` which stays in `match_manager.py`. Import it from there (or pass as callback). `spawn_lobby_ai` similarly delegates.

**Re-export in `match_manager.py`:**
```python
from app.core.lobby_config import (
    select_class, get_class_selection, add_lobby_message, get_lobby_chat,
    update_match_config, get_match_config_payload, spawn_lobby_ai,
)
```

---

### Phase 6: `loadout_generator.py` — Equipment Loadouts ✅

**Status:** Complete — 2026-03-19 · 4040/4040 tests passing

**~200 lines** | 3 functions + 4 constants

Completely self-contained item generation logic. No match state reads.

**Moves to `loadout_generator.py`:**

| Symbol | Lines | Purpose |
|--------|-------|---------|
| `_RARITY_TIERS` | 2614 | Rarity tier order list |
| `_MONSTER_RARITY_BONUS` | 2617 | Rarity bonus by monster tier |
| `_CLASS_ARMOR_POOL` | 2773 | Armor category by class pref |
| `_MATCH_TIER_BONUS` | 2782 | Match tier → rarity offset |
| `generate_enemy_loadout()` | 2627–2727 | Roll equipment for enemy |
| `_apply_loadout_to_unit()` | 2728–2771 | Assign gear + recalc stats |
| `generate_hero_loadout()` | 2772–2873 | Roll class-appropriate hero gear |

**Re-export in `match_manager.py`:**
```python
from app.core.loadout_generator import (
    generate_enemy_loadout, _apply_loadout_to_unit, generate_hero_loadout,
    _RARITY_TIERS, _MONSTER_RARITY_BONUS, _CLASS_ARMOR_POOL, _MATCH_TIER_BONUS,
)
```

---

### Phase 7: `dungeon_manager.py` — Dungeon Lifecycle & Enemy Spawning

**Status:** Complete — 2026-03-19 · 4040/4040 tests passing

**~600 lines** | 8 functions

All dungeon-specific logic: procedural generation, door/chest state, stairs, floor advancement, and enemy spawning with rarity integration.

**Moves to `dungeon_manager.py`:**

| Function | Lines | Purpose |
|----------|-------|---------|
| `_is_static_dungeon_map()` | 2116–2129 | Check if map is a static dungeon file |
| `_generate_procedural_dungeon()` | 2130–2201 | WFC dungeon generation |
| `_init_dungeon_state()` | 2202–2289 | Populate door/chest/ground items |
| `_init_exploration_state()` | 2290–2314 | Build room graph, init discovery |
| `get_dungeon_state()` | 2315–2331 | Return door/chest/ground state |
| `get_stairs_info()` | 2332–2367 | Stairs positions + unlock check |
| `advance_floor()` | 2368–2613 | Full floor-advance sequence |
| `_spawn_dungeon_enemies()` | 2874–3161 | Spawn enemies with rarity/packs/minions |

**Dependencies:** Calls `_compute_initial_fov` (from fov_manager), `_apply_loadout_to_unit` (from loadout_generator), map_loader, monster_rarity, spawn, ai_behavior, ai_exploration. All available via normal imports.

**Re-export in `match_manager.py`:**
```python
from app.core.dungeon_manager import (
    _is_static_dungeon_map, _generate_procedural_dungeon,
    _init_dungeon_state, _init_exploration_state,
    get_dungeon_state, get_stairs_info, advance_floor,
    _spawn_dungeon_enemies,
)
```

---

### Phase 8: `pvpve_manager.py` — PVPVE Match Flow ✅

**Status:** Complete — 2026-03-19 · 4040/4040 tests passing

**~400 lines** | 5 functions + 1 constant

The full PVPVE pipeline: team distribution, dungeon generation, PVE enemy spawning.

**Moves to `pvpve_manager.py`:**

| Symbol | Lines | Purpose |
|--------|-------|---------|
| `_PVPVE_TEAM_KEYS` | 1501 | Team assignment order constant |
| `_start_pvpve_match()` | 1502–1552 | Full PVPVE init orchestrator |
| `_spawn_pvpve_ai_teams()` | 1553–1674 | Spawn AI hero teams |
| `_assign_pvpve_teams()` | 1675–1782 | Distribute players across teams |
| `_generate_pvpve_dungeon()` | 1783–1848 | Generate WFC PVPVE dungeon |
| `_spawn_pvpve_enemies()` | 1849–2115 | Spawn PVE enemies in PVPVE |

**Dependencies:** Calls `_resolve_smart_spawns`, `_apply_lobby_class_selections`, `_init_dungeon_state`, `_init_exploration_state`, `_load_heroes_at_match_start` (available via imports from match_manager, dungeon_manager, hero_manager). Calls `generate_hero_loadout`, `_apply_loadout_to_unit` (from loadout_generator).

**Re-export in `match_manager.py`:**
```python
from app.core.pvpve_manager import (
    _start_pvpve_match, _spawn_pvpve_ai_teams, _assign_pvpve_teams,
    _generate_pvpve_dungeon, _spawn_pvpve_enemies, _PVPVE_TEAM_KEYS,
)
```

---

## What Stays in `match_manager.py` (~300 lines)

The orchestrator retains the match lifecycle core + arena AI spawning + all re-exports.

### Functions Remaining:

| Function | Lines | Reason to Keep |
|----------|-------|----------------|
| `create_match()` | 76–129 | Core lifecycle |
| `join_match()` | 130–168 | Core lifecycle |
| `get_match()` | 169–172 | 1-liner accessor |
| `get_match_players()` | 173–176 | 1-liner accessor |
| `list_matches()` | 177–194 | Core lifecycle |
| `set_player_ready()` | 195–221 | Core lifecycle |
| `start_match()` | 222–286 | Orchestrator — calls into all sub-modules |
| `_spawn_ai_units()` | 287–458 | Arena AI spawning (tightly coupled to start_match) |
| `_clear_ai_units()` | 459–481 | Companion to _spawn_ai_units |
| `_ensure_ai_spawned()` | 482–510 | Companion to _spawn_ai_units |
| `_apply_lobby_class_selections()` | 496–510 | Called by start_match + pvpve |
| `_resolve_smart_spawns()` | 541–585 | Called by start_match + pvpve |
| `end_match()` | 586–594 | Core lifecycle |
| `remove_match()` | 595–621 | Core lifecycle (cleanup) |
| `remove_player()` | 622–676 | Core lifecycle |
| `change_player_team()` | 677–704 | Core lifecycle |
| `get_player_username()` | 705–713 | 1-liner accessor |
| `get_match_teams()` | 1220–1227 | 1-liner accessor |
| `get_ai_ids()` | 1228–1254 | 1-liner accessor |
| `get_alive_count()` | 1169–1176 | 1-liner accessor |
| `increment_turn()` | 825–833 | 1-liner mutator |

### Re-export Blocks (all existing + new):

```python
# --- Re-exports from sub-modules (backwards compatibility) ---
from app.core.match_store import *                    # state dicts
from app.core.action_queue import ...                 # Phase 2
from app.core.fov_manager import ...                  # Phase 3
from app.core.match_payloads import ...               # Phase 4
from app.core.lobby_config import ...                 # Phase 5
from app.core.loadout_generator import ...            # Phase 6
from app.core.dungeon_manager import ...              # Phase 7
from app.core.pvpve_manager import ...                # Phase 8
from app.core.auto_target import ...                  # (existing)
from app.core.party_manager import ...                # (existing)
from app.core.hero_manager import ...                 # (existing)
from app.core.equipment_manager import ...            # (existing)
from app.core.wave_spawner import ...                 # (existing)
```

---

## Line Count Summary

| Module | Est. Lines | Functions |
|--------|-----------|-----------|
| `match_store.py` | ~75 | 0 (state only) |
| `action_queue.py` | ~100 | 6 |
| `fov_manager.py` | ~80 | 6 |
| `match_payloads.py` | ~300 | 5 |
| `lobby_config.py` | ~300 | 7 |
| `loadout_generator.py` | ~200 | 3 |
| `dungeon_manager.py` | ~600 | 8 |
| `pvpve_manager.py` | ~400 | 6 |
| **match_manager.py** (orchestrator) | **~300** | **~20 + re-exports** |
| **Total** | **~2,355** | — |

> Original: 3,220 lines in 1 file → ~2,355 lines across 9 files  
> Net reduction from deduplicating boilerplate (shared imports, repeated comments)

---

## Execution Order & Testing

| Step | Action | Test Command | Expected |
|------|--------|-------------|----------|
| 0 | Backup + baseline | `pytest tests/ -q` | Record pass count |
| 1 | Extract `match_store.py` + update all imports | `pytest tests/ -q` | Same pass count |
| 2 | Extract `action_queue.py` + re-export | `pytest tests/ -q` | 4040 passed ✅ |
| 3 | Extract `fov_manager.py` + re-export | `pytest tests/ -q` | 4040 passed ✅ |
| 4 | Extract `match_payloads.py` + re-export | `pytest tests/ -q` | 4040 passed ✅ |
| 5 | Extract `lobby_config.py` + re-export | `pytest tests/ -q` | 4040 passed ✅ |
| 6 | Extract `loadout_generator.py` + re-export | `pytest tests/ -q` | 4040 passed ✅ |
| 7 | Extract `dungeon_manager.py` + re-export | `pytest tests/ -q` | 4040 passed ✅ |
| 8 | Extract `pvpve_manager.py` + re-export | `pytest tests/ -q` | 4040 passed ✅ |
| 9 | Final cleanup + verify backup comparison | `pytest tests/ -q` | Same pass count |

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Circular imports | `match_store.py` holds ALL state — sub-modules import from store, not from each other |
| Broken imports in callers | Re-export every symbol from `match_manager.py` — zero caller changes needed |
| Test regressions | Run full suite after EACH phase; roll back if any failures |
| Missed private references | Tests access `_active_matches`, `_player_states`, etc. — re-exported from match_store through match_manager |
| `start_match()` orchestration | Stays in match_manager as the central coordinator — calls into sub-modules |

---

## Files That Import `match_manager` (No Changes Needed)

These files will continue to work unchanged due to re-exports:

- `server/app/services/tick_loop.py` (42 symbols)
- `server/app/services/message_handlers.py` (38 symbols)
- `server/app/services/websocket.py` (4 symbols)
- `server/app/routes/lobby.py` (13 symbols)
- `server/app/routes/match.py` (10 symbols)
- `server/app/core/turn_phases/deaths_phase.py` (2 symbols, inline)
- `server/batch_pvp.py` (25 symbols)
- `server/batch_pvpve.py` (25 symbols)
- `server/tests/test_match.py`, `test_queue.py`, `test_websocket.py`, `test_dungeon_map.py`, `test_enemy_types.py`, `test_enemy_loadouts.py`, `test_enemy_auto_equip.py`, `test_auto_target.py`, `test_hero_persistence.py`, `test_hero_party_loadouts.py`, `test_dungeon_inventory.py`, `test_group_movement.py`, `test_multi_select.py`, `test_stances.py`, `test_wave_arena.py`, `test_ws_skills.py`, `test_chunk2.py`, `test_chunk3.py`, `test_pvpve_ai_teams.py`, `test_pvpve_phase_c.py`, `test_pvpve_team_cohesion.py`, `test_loot_combat.py`, `test_party_item_distribution.py`, `test_monster_rarity_spawn.py`, `test_phase16a_stat_expansion.py`

## Already-Extracted Modules That Need `match_store` Migration (Phase 1)

These 5 files currently import state dicts from `match_manager` — update to import from `match_store`:

| File | Current Import Source | Symbols |
|------|---------------------|---------|
| `hero_manager.py` | `match_manager` | 8 state dicts |
| `party_manager.py` | `match_manager` | 3 state dicts + 2 functions |
| `equipment_manager.py` | `match_manager` | 1 state dict |
| `wave_spawner.py` | `match_manager` | 3 state dicts |
| `auto_target.py` | `match_manager` | 1 state dict |
