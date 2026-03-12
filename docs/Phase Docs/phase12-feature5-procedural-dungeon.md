# Phase 12 Feature 5 — Procedural Dungeon Integration (WFC)

## Overview

Server-side Python port of the WFC (Wave Function Collapse) Dungeon Lab tool, enabling **runtime procedural dungeon generation** for dungeon run matches. When a DUNGEON match starts without a pre-existing static map, the server generates a unique dungeon floor on the fly using a seeded, deterministic WFC algorithm.

**Status:** Core implementation complete — generation, connectivity, decoration, export, and match integration all functional. High-priority tasks (rendering, UI, spawn guarantee, enemy validation) complete. **Multi-floor dungeon support fully implemented** — stairs interaction, floor transition, and party descent all working. **Module variety expansion complete** — 20 new modules with 3 new socket types (narrow, wide, gated) for Diablo 2-style spatial variety. 50/50 WFC tests passing, 1641/1641 full suite passing.

---

## What Has Been Done

### 1. Python WFC Engine (`server/app/core/wfc/`)

Full port of the JavaScript-based WFC Dungeon Lab tool (~1,355 lines JS → ~1,400 lines Python) across 8 files:

| File | Lines | Purpose |
|---|---|---|
| `__init__.py` | 32 | Package init, public API exports |
| `module_utils.py` | ~183 | Module data structures, socket derivation, rotation expansion |
| `wfc_engine.py` | ~440 | Core WFC collapse algorithm + BFS constraint propagation |
| `connectivity.py` | ~250 | Flood-fill region detection + A* tunnel carving |
| `room_decorator.py` | ~357 | Post-generation content assignment (enemies, loot, boss, spawn) |
| `map_exporter.py` | ~213 | Convert WFC output to game-compatible map dict |
| `presets.py` | ~1050 | 49 preset module definitions (6×6 tiles each) |
| `dungeon_generator.py` | ~275 | High-level API with floor scaling |

### 2. Module Library (49 Presets)

All modules are 6×6 tiles with auto-derived socket patterns for edge compatibility. Expanded from 29 to 49 modules (~163 rotation variants) with 3 new socket types for Diablo 2-style spatial variety:

**Original Modules (29):**
- **Filler (1):** Solid Wall
- **Corridors (5):** Straight, L-Turn, T-Junction, Crossroads, Doored
- **Rooms – Flexible (5):** Dead End, Passthrough, Corner, Three-Way, Hub
- **Rooms – Fixed Purpose (5):** Spawn Room, Enemy Den, Skeleton Hall, Treasury, Boss Chamber
- **Grand Rooms – 2-Module (3):** Grand Hall, Grand Hall Pillared, Grand End
- **Grand Rooms – 4-Module Corners (4):** Closed, Open, Double, Pillared
- **Grand Rooms – Fixed Purpose (4):** Grand Enemy Den, Grand Boss Arena, Grand Treasury, Grand Spawn Hall
- **Grand Room Interior (2):** Grand Center, Grand Edge

**Variety Expansion Modules (20):**
- **Narrow Corridors (5):** Narrow Straight, Narrow L-Turn, Narrow T-Junction, Narrow Crossroads, Narrow Doored — 1-wide squeeze passages for ambush chokepoints and secret routes
- **Transition Modules (2):** Narrow-to-Standard Widener, Standard-to-Wide Vestibule — bridges between different socket widths, creating natural spatial flow shifts
- **Asymmetric Rooms (5):** Alcove Room (std+narrow), Side Passage Room (std passthrough+narrow side), Narrow Dead End, Antechamber (std+wide), Wide Dead End Room — rooms with different socket types per edge for varied entry/exit rhythm
- **New Room Shapes (5):** Pillar Room (LOS-breaking cover), Ring Room (central pillar, kite-friendly), Crypt Niche Room (recessed alcoves), Guard Post (3-way junction room), Gatehouse (door-framed entries)
- **Corridor Variants (3):** Ambush Corridor (std corridor with side alcove for enemy placement), Zigzag Corridor (winding passthrough), Collapsed Corridor (partial blockage chokepoint)

**Socket System (5 patterns):**

| Socket | Pattern | Width | Use |
|--------|---------|-------|-----|
| Wall | `WWWWWW` | 0 | Solid wall, no connection |
| Standard | `WWOOWW` | 2-wide | Primary corridor/room connections |
| Narrow | `WWWOWW` | 1-wide | Squeeze corridors, secret passages, chokepoints |
| Wide | `WOOOOW` | 4-wide | Grand room interiors, vestibule transitions |
| Narrow (rotated) | `WWOWWW` | 1-wide | Auto-derived from narrow module rotations |

Modules with different socket types per edge (e.g., Alcove Room: standard south + narrow east) create asymmetric spatial flow. Transition modules bridge between socket widths so WFC can seamlessly connect narrow passages to standard corridors to grand halls.

**Generation stats:** 100/100 success rate across random seeds. 44+ unique module types actively used per 50-seed batch. ~17ms generation time for 3×3 grids.

### 3. Generation Pipeline

```
get_preset_modules()
    → expand_modules() — generate rotation variants, deduplicate
        → run_wfc() — entropy-based collapse + BFS propagation
            → ensure_connectivity() — flood-fill + A* tunnel carving
                → decorate_rooms() — assign content to flexible rooms
                    → export_to_game_map() — convert to game JSON format
```

### 4. Map Loader Runtime Support (`server/app/core/map_loader.py`)

Added runtime map registration/unregistration:
- `register_runtime_map(map_id, map_data)` — Store a generated map in memory
- `unregister_runtime_map(map_id)` — Clean up on match end
- All existing accessors (`load_map`, `get_obstacles`, `get_tiles`, etc.) transparently support runtime maps

### 5. Match Manager Integration (`server/app/core/match_manager.py`)

- **`start_match()`** — For DUNGEON matches without a static map, calls `_generate_procedural_dungeon()` before `_init_dungeon_state()`
- **`_generate_procedural_dungeon()`** — Generates a WFC dungeon, registers as `wfc_<match_id>`, updates match config and resolves spawn positions
- **`_is_static_dungeon_map()`** — Determines if a map_id refers to an existing static map file
- **`remove_match()`** — Cleans up the runtime map on match end

### 6. Floor Scaling System

`FloorConfig.from_floor_number(seed, floor_number)` automatically scales:

| Parameter | Floor 1-2 | Floor 3-5 | Floor 6-8 | Floor 9+ |
|---|---|---|---|---|
| Grid Size | 3×3 (18×18 tiles) | 4×4 (24×24 tiles) | 5×5 (30×30 tiles) | 6×6 (36×36 tiles) |
| Enemy Density | 60-65% | 70-80% | 85-95% | 100% |
| Loot Density | 30-32% | 34-38% | 40-44% | 46%+ |
| Enemy Types | skeleton/demon | demon/undead_knight | undead_knight | undead_knight |

### 7. Test Suite (`server/tests/test_wfc_dungeon.py`)

50 tests covering:
- Module utils: size, sockets, rotation, expansion, deep copy
- WFC engine: success, dimensions, determinism, seed variation, tile types
- Connectivity: region detection, tunnel carving, validation
- Map exporter: format, normalization, spawn/door/chest extraction, tile legend
- Dungeon generator: full pipeline, format, determinism, scaling, stats, error handling
- Runtime maps: registration, loading, unregistration
- Full integration: generate → register → load → validate chain
- Spawn room guarantee: multi-seed placement, emergency fallback, count limits, empty map edge case
- Enemy type validation: config existence, depth variation, grid progression, density scaling, type matching

---

## What Needs to Be Done

### High Priority

1. **Client-Side Rendering Support** ✅ **VERIFIED**
   - ~~Handle `wfc_<match_id>` map IDs in the client~~ — map IDs never reach the client; `tiles` + `tileLegend` arrays are sent directly via WebSocket
   - ~~Verify fog-of-war works correctly with WFC-sized maps~~ — FOV uses coordinate-based Sets, fully size-agnostic
   - ~~Test minimap rendering~~ — minimap not yet implemented (planned as Phase 12 Feature 7); nothing to test
   - **Conclusion:** The existing `drawDungeonTiles()` + `computeViewport()` pipeline handles WFC-generated dungeons transparently with no code changes needed

2. **Dungeon Run UI Integration** ✅ **DONE**
   - Added "Procedural (WFC)" / "Classic Dungeon" toggle in TownHub with styled buttons and description hint
   - `App.jsx` `handleEnterDungeon()` now accepts `dungeonType` param; sends `map_id: 'procedural'` for WFC generation or `'dungeon_test'` for classic
   - WaitingRoom shows procedural dungeon badge + info when `map_id === 'procedural'`
   - Added CSS styles for dungeon type selector (`.town-dungeon-type`, `.btn-dungeon-type`, `.procedural-badge`)
   - Server's `_is_static_dungeon_map('procedural')` returns `False` → triggers `_generate_procedural_dungeon()` automatically

3. **Spawn Room Guarantee** ✅ **DONE**
   - Added 3-tier fallback in `room_decorator.py`:
     1. First try: flexible rooms with `canBeSpawn=True` (existing behavior)
     2. Fallback: any flexible room with floor slots
     3. Last resort: `_place_emergency_spawns()` — places S tiles on first available interior floor tiles
   - Emergency fallback appends a synthetic "Emergency Spawn (fallback)" room to decorated rooms
   - Added 4 tests: spawn always placed across seeds, emergency fallback placement, count enforcement, empty-map edge case
   - `map_exporter.py` already has its own fallback (uses first floor tiles if no S tiles found) — defense in depth

4. **Enemy Type Scaling Validation** ✅ **DONE**
   - Added `validate_enemy_types()` function that checks all floor-scaling enemy types exist in `enemies_config.json`
   - Expanded floor enemy progression from 3 tiers to 5 tiers for more variety:
     - Floors 1-2: skeleton + demon boss
     - Floors 3-4: demon + undead_knight boss
     - Floors 5-6: wraith + undead_knight boss
     - Floors 7-8: werewolf + reaper boss
     - Floor 9+: construct + reaper boss
   - Added `_KNOWN_ENEMY_TYPES` constant for documentation
   - Exported `validate_enemy_types` from `wfc/__init__.py`
   - Added 5 tests: config validation, depth variation, grid progression, density scaling, enemy type matching

### Medium Priority

5. **Multi-Floor Dungeon Support** ✅ **DONE**
   - ~~Wire floor progression: on staircase interaction, generate floor N+1~~ — Pressing E on stairs tile triggers `enter_stairs` interact action → turn resolver validates → tick loop calls `advance_floor()` → generates next WFC floor
   - ~~Add staircase/exit tile type to module presets~~ — Stairs tile (`T`) already existed in WFC presets and room_decorator; now has full interaction support
   - ~~Persist dungeon state (seed, current floor, cleared rooms) across floors~~ — `MatchState` tracks `current_floor`, `dungeon_seed`, `stairs_unlocked`; seed chain: `floor_seed = (base_seed + floor * 7919) & 0xFFFFFFFF`
   - ~~Track floor completion (all enemies cleared → unlock staircase)~~ — `get_stairs_info()` auto-unlocks stairs when all `team_b` enemies are dead
   - Full implementation details in **Multi-Floor Dungeon Implementation** section below

6. **Seed Selection UI**
   - Allow players to input custom seed for reproducible runs
   - Display seed in post-match summary for sharing

7. **Fallback Map Pool**
   - Pre-generate a pool of 10-20 maps at server startup for instant fallback
   - Use fallback pool if runtime generation fails or takes too long

8. **Performance Profiling**
   - Benchmark generation time across grid sizes (current: ~300ms for 3×3)
   - Profile memory usage for large grids (6×6 = 36×36 tiles)
   - Consider async generation for 5×5+ grids if blocking becomes an issue

### Low Priority

9. **Module Library Expansion** ✅ **DONE** (Variety Expansion)
   - ~~Add theme-specific module sets (crypt, cave, castle)~~ — Added 20 new modules with 3 new socket types (narrow, wide, transition) providing Diablo 2-style spatial variety
   - Support custom module loading from JSON config files
   - Add weighted theme mixing (e.g., 70% crypt + 30% cave)
   - Per-biome module weight profiles (catacombs favor corridors, cathedral favors grand halls)

10. **Map Serialization**
    - Save generated maps to disk for replay/debugging
    - Export format compatible with the WFC Dungeon Lab tool for visual inspection

---

## Multi-Floor Dungeon Implementation

### Overview

Full end-to-end floor transition system modeled after the Portal Extraction system (Phase 12C). When all enemies on a floor are defeated, the stairs tile unlocks. Any party member standing on the stairs tile can press E to descend, taking the **entire party** to the next procedurally generated floor.

### Data Flow

```
Client: E-key on stairs tile
  → WebSocket: { type: "action", action_type: "interact", target_id: "enter_stairs" }
    → turn_resolver: _resolve_stairs() validates position + unlock state
      → TurnResult: floor_advance=True, new_floor_number=N+1
        → tick_loop: calls advance_floor(match_id)
          → match_manager: generates new WFC floor, respawns enemies, moves party
            → WebSocket broadcast: { type: "floor_advance", ... } to all players
              → Client: FLOOR_ADVANCE reducer resets map, FOV, enemies, combat log
```

### Backend Changes

#### `server/app/models/match.py`
Added 3 fields to `MatchState`:
- `current_floor: int = 1` — tracks which floor the party is on
- `dungeon_seed: int = 0` — base seed for deterministic floor chain
- `stairs_unlocked: bool = False` — whether stairs are interactable

#### `server/app/models/actions.py`
Added 2 fields to `TurnResult`:
- `floor_advance: bool = False` — signals a floor transition occurred
- `new_floor_number: int | None = None` — the floor number being descended to

#### `server/app/core/turn_resolver.py`
- New `_resolve_stairs()` function (~60 lines) — Phase 0.9 in resolution pipeline (between extraction and movement)
- Checks: player submitted `enter_stairs` interact action, player is standing on a stairs tile, stairs are unlocked
- Sets `stairs_context["floor_advance"] = True` when valid
- `resolve_turn()` gained 2 new params: `stairs_positions`, `stairs_unlocked`
- Door interaction filter updated to exclude both `enter_portal` and `enter_stairs` target_ids
- TurnResult construction now includes `floor_advance` and `new_floor_number` from stairs_context

#### `server/app/core/match_manager.py`
- **`get_stairs_info(match_id)`** — Returns `{"positions": [(x,y),...], "unlocked": bool, "current_floor": int}`. Auto-unlocks stairs when all `team_b` entities are dead.
- **`advance_floor(match_id)`** (~120 lines) — Full floor transition:
  1. Increments `match.current_floor`
  2. Unregisters old runtime map
  3. Generates new WFC floor via `_generate_procedural_dungeon()`
  4. Re-initializes dungeon state (obstacles, doors, chests, tile legend)
  5. Removes old enemies from entity pool
  6. Spawns new enemies for the floor
  7. Moves all party members to new spawn points
  8. Clears action queues, auto-targets, FOV, portal/channeling state
  9. Resets `stairs_unlocked = False`
  10. Returns full floor payload dict for broadcasting
- **`_generate_procedural_dungeon()`** — Updated to use `match.current_floor` instead of hardcoded `1`; stores seed in `match.dungeon_seed`
- **`get_match_start_payload()`** — Now includes `current_floor` and `stairs_unlocked` in dungeon payloads

#### `server/app/services/tick_loop.py`
- Before `resolve_turn()`: fetches stairs info via `get_stairs_info()`, passes `stairs_positions` and `stairs_unlocked` to resolver
- After resolution: if `turn_result.floor_advance` is True, calls `advance_floor()`, builds per-player payloads with FOV data, broadcasts `floor_advance` message to each player, suppresses winner/victory handling, and returns early
- Broadcast payload includes `stairs_unlocked` and `current_floor` for each tick

### Frontend Changes

#### `client/src/hooks/useKeyboardShortcuts.js`
- E-key handler: new stairs interaction at Priority 0.5 (between portal [Priority 0] and ground items [Priority 1])
- Reads player's tile from `tiles[py][px]`, looks up `tileLegend[tileChar]` to check for `'stairs'`
- If unlocked → sends `interact` action with `target_id: 'enter_stairs'`
- If locked → adds combat log message: "The stairs are blocked — defeat all enemies first!"
- New params: `tiles`, `tileLegend`, `stairsUnlocked`

#### `client/src/context/reducers/combatReducer.js`
- `MATCH_START` case: initializes `currentFloor` and `stairsUnlocked` from payload
- `TURN_RESULT` case: updates `stairsUnlocked` and `currentFloor` from each tick's payload
- New `FLOOR_ADVANCE` case (~45 lines): full map state reset — updates grid dimensions, tiles, tileLegend, obstacles, doorStates, chestStates, clears groundItems, rebuilds FOV Set from `visible_tiles`, resets portal/channeling/autoTargets/floaters, adds combat log entry "Descended to Floor N"

#### `client/src/App.jsx`
- WebSocket `handleMessage`: new `case 'floor_advance'` routes to `FLOOR_ADVANCE` dispatch

#### `client/src/components/Arena/Arena.jsx`
- Passes `tiles`, `tileLegend`, and `stairsUnlocked` to `useKeyboardShortcuts()` hook

### Stairs Unlock Logic

Stairs auto-unlock when all `team_b` (enemy) entities are dead:
```python
def get_stairs_info(match_id):
    enemies_alive = any(
        e for e in match.entities.values()
        if e.team == "team_b" and e.current_hp > 0
    )
    match.stairs_unlocked = not enemies_alive
    return {
        "positions": stairs_positions,
        "unlocked": match.stairs_unlocked,
        "current_floor": match.current_floor
    }
```

### Floor Generation Chain

Each floor uses a deterministic seed derived from the base seed:
```python
floor_seed = (base_seed + floor_number * 7919) & 0xFFFFFFFF
```
This ensures:
- Same base seed → same floor sequence every time
- Different floors get different layouts
- `FloorConfig.from_floor_number()` handles grid size, enemy density, loot density, and enemy type scaling automatically

### Validation

- **0 lint/type errors** across all 8 modified files
- **46/46 WFC dungeon tests** passing
- **1629/1629 full test suite** passing — zero regressions

---

## Future Enhancements

### Multi-Floor Architecture
- **Vertical Connectivity:** Staircases linking floors with position mapping
- **Persistent Seed Chain:** `floor_seed = (base_seed + floor * 7919) & 0xFFFFFFFF` already implemented
- **Progressive Difficulty:** Floor scaling system in place, needs staircase/portal trigger
- **Floor Memory:** Return to previously visited floors with cleared state preserved

### Biome/Theme System
- Module variants with different tile art per biome (crypt, forest, void)
- Per-floor biome assignment or gradual transition
- Biome-specific enemy tables and loot pools

### Boss Floor Generation
- Special rules for boss floors (larger arena, scripted layout constraints)
- Multi-module boss arenas with pinned placements
- Pre-generated boss room templates that WFC connects to corridors

### Challenge Modes
- **Time Attack:** Fixed seed, compete for fastest clear
- **Endless:** Infinite floor progression with leaderboarding
- **Daily Dungeon:** Server-wide shared seed, one attempt per day

### Multi-Module Room Intelligence
- Detect and preserve adjacency groups of grand room modules
- Room-level content distribution across multi-module rooms
- Grand room decorations: pillars, traps, treasure piles

### WFC Algorithm Improvements
- **Backtracking:** Instead of full restart on contradiction, undo last N placements
- **Constraint Softening:** Allow "close enough" socket matches with priority penalties
- **Regional Pinning:** Pin specific room types at map corners or center
- **History-Based Weights:** Track which modules were used and boost underrepresented ones

### Module & Connection Variety (Future)
- **Per-biome module pools:** Catacombs favor narrow corridors + crypt niches; Cathedral favors grand halls + pillar rooms; Cave favors collapsed corridors + zigzags
- **Socket affinity weights:** Modules closer to spawn prefer standard sockets; deeper modules unlock narrow/wide entries for progressive architectural variety
- **Corridor decoration events:** 15% chance a corridor gets a wandering enemy, 5% chance for a ground item — breaks up empty corridors
- **Directional flow / critical path:** Pin spawn and boss at map extremes, creating a main "spine" with side branches for optional content

---

## File Reference

### New Files Created
```
server/app/core/wfc/
├── __init__.py           — Package init + public API
├── module_utils.py       — Module structures, sockets, rotation
├── wfc_engine.py         — Core WFC algorithm
├── connectivity.py       — Flood-fill + A* tunneling
├── room_decorator.py     — Content assignment to rooms
├── map_exporter.py       — WFC → game map conversion
├── presets.py            — 29 preset module definitions
└── dungeon_generator.py  — High-level generation API

server/tests/
└── test_wfc_dungeon.py   — 50 tests for the full pipeline
```

### Modified Files
```
server/app/core/map_loader.py    — Added register/unregister_runtime_map()
server/app/core/match_manager.py — Added _generate_procedural_dungeon(),
                                    _is_static_dungeon_map(), cleanup in remove_match(),
                                    get_stairs_info(), advance_floor()
server/app/models/match.py       — Added current_floor, dungeon_seed, stairs_unlocked
server/app/models/actions.py     — Added floor_advance, new_floor_number to TurnResult
server/app/core/turn_resolver.py — Added _resolve_stairs() phase, stairs params
server/app/services/tick_loop.py — Added stairs info passing + floor advance handling
client/src/hooks/useKeyboardShortcuts.js — E-key stairs interaction
client/src/context/reducers/combatReducer.js — FLOOR_ADVANCE case + floor state
client/src/App.jsx               — floor_advance WebSocket handler
client/src/components/Arena/Arena.jsx — stairs props to keyboard hook
```

### Key API

```python
from app.core.wfc import generate_dungeon_floor, FloorConfig

# Auto-scaled from floor number
result = generate_dungeon_floor(seed=42, floor_number=1)
if result.success:
    game_map = result.game_map  # Ready for map_loader registration

# Full control
config = FloorConfig(seed=42, floor_number=3, grid_rows=5, grid_cols=5)
result = generate_dungeon_floor(config=config)
```
