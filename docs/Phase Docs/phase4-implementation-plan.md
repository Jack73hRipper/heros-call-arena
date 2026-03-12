# Phase 4: Implementation Plan — Sub-Phase Breakdown

## Decisions Locked In

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Persistence | JSON file storage | Simple, no external deps, upgradeable later |
| Arena mode | Keep both modes | Dungeon is additive, arena PvP stays as separate mode |
| Visuals | Colored shapes + class labels | Sprite integration deferred; shapes replaced later |
| Party size | Flexible 1-5 | Solo runs allowed, maximum freedom |
| Dungeon maps | Handcrafted (not procedural) | Phase 4 only; procedural gen in Phase 5+ |
| Loot rarity | Common + Uncommon only | Diablo-style affixes deferred to Phase 5+ |

---

## Sub-Phase Overview

| Sub-Phase | Name | Est. Duration | Dependencies |
|-----------|------|---------------|-------------|
| **4A** | Class System Foundation | 3-4 days | None (builds on existing) | ✅ Complete |
| **4B-1** | Dungeon Map Format & Server Foundation | 1-2 days | 4A (classes used in dungeon) | ✅ Complete |
| **4B-2** | Door Mechanics, FOV & Dungeon Rendering | 1-2 days | 4B-1 (consumes map data layer) | ✅ Complete |
| **4C** | Enemy Types & Enhanced AI | 3-4 days | 4A + 4B-2 (enemies need classes + dungeon maps) | ✅ Complete |
| **4D-1** | Item Models, Configs & Loot Generation | 1.5-2 days | 4C (needs enemy types for loot tables) | ✅ Complete |
| **4D-2** | Equipment, Loot Drops & Consumables (Server Logic) | 1.5-2 days | 4D-1 (needs item models + loot generation) | ✅ Complete |
| **4D-3** | Client Inventory UI & Ground Item Rendering | 1-1.5 days | 4D-2 (needs server API stable) | ✅ Complete |
| **4E-1** | Hero Models, Persistence & Town REST API | 1.5-2 days | 4D-3 (heroes need classes + equippable items) | ✅ Complete |
| **4E-2** | Match Integration & Permadeath | 1.5-2 days | 4E-1 (needs hero models + persistence layer) | ✅ Complete |
| **4E-3** | Town Hub Client UI | 1-1.5 days | 4E-2 (needs stable server API for hero management) | ✅ Complete |
| **4F** | Dungeon Run Loop & Escape | 3-4 days | All above (full loop ties everything together) |
| **4G** | AI Parties & Polish | 3-4 days | All above (enemy parties use all systems) |

**Total estimated: 24-32 days (5-6.5 weeks)**

> **Note on 4B split:** Phase 4B was split into two sub-phases (4B-1, 4B-2) after two failed attempts where the monolithic scope consumed all available context memory before completion. The split isolates data-layer work (map format, models, loader) from gameplay-logic + rendering work (doors, FOV, viewport), giving each sub-phase a clear validation checkpoint.

> **Note on 4D split:** Phase 4D was split into three sub-phases (4D-1, 4D-2, 4D-3) following the same pattern. The loot & inventory system spans item models, config files, loot tables, equipment bonuses in combat, loot drop mechanics on death/chest, consumable usage in the turn resolver, and a full client inventory UI — touching 13+ files across all layers. The split isolates: (1) pure data/models, (2) server gameplay logic, and (3) client UI, each with a clear validation checkpoint.

> **Note on 4E split:** Phase 4E was proactively split into three sub-phases (4E-1, 4E-2, 4E-3) following the proven pattern. Hero hiring & persistence spans new persistence infrastructure, new data models, new REST routes, match manager integration, permadeath hooks, gold economy, and an entirely new client screen with complex UI flows — touching 10+ new and modified files across all layers. The split isolates: (1) models/persistence/REST API (pure data layer, no match integration), (2) match lifecycle integration + permadeath (server logic, no client UI), and (3) Town Hub client UI (consuming stable 4E-2 API).

```
4A ──→ 4B-1 ──→ 4B-2 ──→ 4C ──→ 4D-1 ──→ 4D-2 ──→ 4D-3 ──→ 4E-1 ──→ 4E-2 ──→ 4E-3 ──→ 4F ──→ 4G
Class   MapData   Doors/    Enemies  Items/   Equip/    Client   Models    Match     Town    Loop   Parties
                  FOV/Render          Config   Loot/     Inventory Persist   Integrate  Hub UI
                                               Combat             & REST    & Perma-
                                                                            death
```

---

## Phase 4A — Class System Foundation

**Goal:** 5 playable classes with distinct stats, selectable in lobby, working in existing arena maps.

**Duration:** 3-4 days

### Deliverables

1. **Class config file** (`server/configs/classes_config.json`)
   - 5 classes: Crusader, Confessor, Inquisitor, Ranger, Hexblade
   - Per-class: `class_id`, `name`, `role`, `base_hp`, `base_melee_damage`, `base_ranged_damage`, `base_armor`, `base_vision_range`, `color`, `shape`
   
2. **Server model changes**
   - `PlayerState` gains `class_id` field (default: null for backward compat)
   - New `ClassDefinition` Pydantic model
   - Class loader utility (reads `classes_config.json`, caches in memory)

3. **Combat system updates**
   - `combat.py`: Use per-class stats from `PlayerState` instead of flat globals
   - `calculate_damage()` / `calculate_ranged_damage()` pull from player's stats
   - `can_ranged_attack()` uses class-specific range if applicable

4. **Match manager updates**
   - `match_manager.py`: Class selection support in lobby
   - AI spawning assigns random classes (or configured classes)
   - Stats assigned from class config at spawn time

5. **Lobby/waiting room updates**
   - New REST endpoint or WS message: `class_select` (player picks class)
   - WS broadcast: `class_changed` to all lobby members
   - Waiting room UI shows class selection dropdown per player
   - Class card: show name, role, stats preview

6. **Renderer updates**
   - `ArenaRenderer.js`: Different colors per class
   - Class label rendered below player name
   - Unique shape per class (circle, triangle, square, diamond, star)

7. **GameState context**
   - New state field: `playerClass`, per-player class tracking in `players` map
   - Reducer handles `class_changed` action

### Files Affected

| File | Changes |
|------|---------|
| `server/configs/classes_config.json` | **NEW** — class definitions |
| `server/app/models/player.py` | Add `class_id` to `PlayerState`, new `ClassDefinition` model |
| `server/app/core/combat.py` | Use per-player stats instead of flat values |
| `server/app/core/match_manager.py` | Class selection, class-based AI spawning |
| `server/app/core/ai_behavior.py` | Minor — AI actions may vary by class (future) |
| `server/app/services/websocket.py` | Handle `class_select` message, broadcast `class_changed` |
| `server/app/routes/lobby.py` | Class selection endpoint (or via WS only) |
| `client/src/context/GameStateContext.jsx` | Class state tracking |
| `client/src/components/WaitingRoom/WaitingRoom.jsx` | Class selection UI |
| `client/src/components/HUD/HUD.jsx` | Show class info |
| `client/src/canvas/ArenaRenderer.js` | Class-based colors/shapes |
| `server/configs/combat_config.json` | May become fallback/default values |

### Testing Criteria
- [x] Each class has visually distinct appearance in arena
- [x] Class stats affect combat outcomes (Crusader tanks more, Ranger hits harder at range)
- [x] Class selection persists through match start
- [x] AI units spawn with random classes
- [x] Existing arena mode still works with classes
- [x] All existing tests pass (backward compat with `class_id=null`)

### Balance Targets (Starting Point)

| Class | HP | Melee Dmg | Ranged Dmg | Armor | Vision | Range |
|-------|-----|-----------|------------|-------|--------|-------|
| Crusader | 150 | 20 | 0 | 8 | 5 | 1 (melee only) |
| Confessor | 100 | 8 | 0 | 3 | 6 | 1 (melee only, heal future) |
| Inquisitor | 80 | 10 | 8 | 4 | 9 | 5 |
| Ranger | 80 | 8 | 18 | 2 | 7 | 6 |
| Hexblade | 110 | 15 | 12 | 5 | 6 | 4 |

> **Note:** Confessor healing ability is deferred. In 4A they are a low-damage support unit. Healing comes as a class ability in a later sub-phase or 4D (as consumable potions).

### Implementation Notes (Completed Feb 13, 2026)

**Key decisions made during implementation:**
- `ranged_range` added as a per-player field on `PlayerState` (default: 5). This allows each class to have a different ranged attack distance. The turn resolver and AI behavior now read this from the player instead of the global `combat_config.json`.
- Class selection is optional — `class_id=null` preserves full backward compatibility with existing default stats from `combat_config.json`.
- AI units receive random class assignments at spawn time via `apply_class_stats()`.
- Class data is served to the frontend via `GET /api/lobby/classes` REST endpoint, fetched once on app mount.
- Class selection in lobby uses the existing WebSocket pattern: `class_select` message → `class_changed` broadcast.
- Renderer now supports 5 distinct shapes: circle (Confessor), square (Crusader), triangle (Inquisitor), diamond (Ranger), star (Hexblade).
- All class colors and shapes are config-driven from `classes_config.json`.
- **164 existing tests pass** with zero modifications needed — full backward compatibility confirmed.

**New files created:**
- `server/configs/classes_config.json` — All 5 class definitions with stats, colors, shapes

**Files modified:**
- `server/app/models/player.py` — Added `class_id`, `ranged_range`, `ClassDefinition` model, class loader utility, `apply_class_stats()`
- `server/app/core/match_manager.py` — Class selection tracking, AI class assignment, class info in all payloads
- `server/app/core/turn_resolver.py` — Per-player `ranged_range` instead of global config
- `server/app/core/ai_behavior.py` — Per-unit `ranged_range` for AI decisions
- `server/app/services/websocket.py` — `class_select` message handler
- `server/app/routes/lobby.py` — `GET /api/lobby/classes` endpoint
- `client/src/App.jsx` — Fetch classes on mount, handle `class_changed` WS message
- `client/src/context/GameStateContext.jsx` — `CLASS_CHANGED`, `SET_AVAILABLE_CLASSES` reducers
- `client/src/components/WaitingRoom/WaitingRoom.jsx` — Class selection card UI
- `client/src/components/HUD/HUD.jsx` — Class display in match info and player list
- `client/src/canvas/ArenaRenderer.js` — Class-based colors, 5 unique shapes, class label rendering
- `client/src/styles/main.css` — Class selection panel CSS

---

## Phase 4B-1 — Dungeon Map Format & Server Foundation

**Goal:** New map data format with rooms, corridors, doors, and chests. Handcrafted test dungeon. Server can load, parse, and create dungeon matches — but no gameplay logic or client rendering yet.

**Duration:** 1-2 days

> **Why this is a separate sub-phase:** The original 4B touched 10+ files across data, logic, and rendering layers simultaneously. Isolating the data layer here means 4B-1 can be validated (map loads, match creates, tests pass) before any door-logic or renderer work begins. This prevents context-memory blowout and gives a clean checkpoint.

### Deliverables - Do not over complicate this process this is only a test map.

1. **Extended map format** (`server/configs/maps/dungeon_test.json`)
   - Tile types: `floor`, `wall`, `door` (closed/open), `chest`, `corridor`, `spawn`
   - Room definitions: named rooms with bounds, purpose (spawn, loot, enemy, boss)
   - Corridor connections between rooms
   - Entity placements: enemy spawn points, chest positions
   - 20x20 or 25x25 grid

2. **Map loader extension**
   - `map_loader.py`: Parse new tile types (`door`, `chest`, `corridor`, `spawn`)
   - `get_doors()` — returns list of door positions with initial open/closed state
   - `get_chests()` — returns list of chest positions
   - `get_room_definitions()` — returns named rooms with bounds and purpose
   - Backward compat: existing arena maps still load fine (no new required fields)

3. **Model scaffolding (enums & state fields only — no logic)**
   - `ActionType.INTERACT` and `ActionType.LOOT` added to enum (no turn resolver logic yet)
   - `MatchType.DUNGEON` added to match model
   - Door state dict and chest state dict added to match state tracking

4. **Basic dungeon match creation**
   - `match_manager.py`: Dungeon match type recognized, uses dungeon maps
   - Party spawns in start room (uses room definitions from map)
   - Victory condition placeholder: all enemies dead (logic refined in 4F)
   - Door/chest initial state populated from map data on match creation

5. **Tests for map data layer**
   - Dungeon map loads without errors
   - Room definitions parsed correctly (count, names, bounds)
   - Door/chest positions extracted
   - Arena maps still load fine (no regression)
   - Dungeon match creates with party in start room


### Files Affected

| File | Changes |
|------|---------|
| `server/configs/maps/dungeon_test.json` | **NEW** — handcrafted dungeon map |
| `server/app/core/map_loader.py` | New tile type parsing, `get_doors()`, `get_chests()`, `get_room_definitions()` |
| `server/app/models/actions.py` | Add `INTERACT`, `LOOT` to `ActionType` enum |
| `server/app/models/match.py` | Add `DUNGEON` to `MatchType`, door/chest state dicts |
| `server/app/core/match_manager.py` | Dungeon match creation, start-room spawning, state init |
| `server/tests/test_dungeon_map.py` | **NEW** — map loading, room parsing, match creation tests |

### Testing Criteria
- [x] Dungeon map loads correctly with rooms, corridors, doors, chests
- [x] `get_doors()` returns correct door positions and initial states
- [x] `get_chests()` returns correct chest positions
- [x] `get_room_definitions()` returns all named rooms with bounds
- [x] `MatchType.DUNGEON` creates a valid match
- [x] Party spawns in start room at valid spawn tiles
- [x] Door/chest state dicts initialized on match creation
- [x] Existing arena maps load without errors (no regression)
- [x] All existing tests pass (164+) — **228 total (164 existing + 64 new)**

### Validation Checkpoint

> **Before starting 4B-2:** Server starts, dungeon map loads, ~~`GET /api/lobby/maps` includes dungeon option~~, dungeon match creates with party in start room, all existing tests pass. No client changes yet.
>
> **Note:** The lobby map dropdown is a hardcoded array in `WaitingRoom.jsx`. Adding the dungeon map to the dropdown (and the `DUNGEON` match type to the match-type selector) is a **4B-2 deliverable** since 4B-1 is server/data only.

### Implementation Notes (Completed Feb 13, 2026)

**Key decisions made during implementation:**
- **No manual obstacles array** in `dungeon_test.json` — dungeon obstacles are auto-derived from the `tiles` grid. `get_obstacles()` now reads the tile grid for any map with a `tiles` field (dungeon), treating `W` (wall) and `D` (door) characters as blocking. Arena maps still fall back to the legacy `obstacles` array. This eliminates hand-maintaining hundreds of wall positions.
- **Tile grid format:** 20×20 array of single-character strings with a `tile_legend` mapping (`W`=wall, `F`=floor, `D`=door, `C`=corridor, `S`=spawn, `X`=chest). This is both human-readable and machine-parseable.
- **Door/chest state stored on `MatchState`** using `"x,y"` string keys (e.g. `"6,3": "closed"`) for JSON serialization compatibility. Populated by `_init_dungeon_state()` at match start.
- **`is_dungeon_map()`** checks `map_type == "dungeon"` in the JSON. The match start logic triggers dungeon init for either `MatchType.DUNGEON` OR a dungeon-type map (belt-and-suspenders).
- **Backward compatibility is total:** all 6 new map_loader functions return empty results for arena maps, `door_states`/`chest_states` default to empty dicts, and `ActionType.INTERACT`/`LOOT` are enum values only (no turn resolver logic yet).

**Dungeon layout (simple, functional):**
```
5 rooms connected by 1-tile-wide corridors:
- Start Room (1,1)-(5,5) — party spawns here
- Enemy Room 1 "Demon Den" (10,1)-(15,5) — 2 enemy spawns
- Loot Room "Treasury" (1,10)-(5,14) — 3 chests
- Enemy Room 2 "Skeleton Hall" (10,10)-(15,14) — 2 enemy spawns
- Boss Room "Throne of the Undead Knight" (14,16)-(18,18) — 1 boss spawn

9 doors (all start closed), 3 chests (all start unopened)
Corridors connect rooms horizontally and vertically.
```

**New files created:**
- `server/configs/maps/dungeon_test.json` — 20×20 dungeon map with tile grid, rooms, doors, chests
- `server/tests/test_dungeon_map.py` — 64 tests across 8 test classes

**Files modified:**
- `server/app/core/map_loader.py` — `get_obstacles()` tile-grid aware; added `get_doors()`, `get_chests()`, `get_room_definitions()`, `get_tiles()`, `is_dungeon_map()`
- `server/app/models/actions.py` — `INTERACT`, `LOOT` added to `ActionType` enum
- `server/app/models/match.py` — `DUNGEON` added to `MatchType`; `door_states`, `chest_states` added to `MatchState`
- `server/app/core/match_manager.py` — Import dungeon helpers; `_init_dungeon_state()` called on dungeon match start; `get_dungeon_state()` helper added

**What the next developer needs to know for 4B-2:**
1. The dungeon map is **not yet visible in the lobby UI**. The `MAPS` array in `client/src/components/WaitingRoom/WaitingRoom.jsx` (line 4) is hardcoded. Add `{ id: 'dungeon_test', label: 'Dungeon Test 20×20' }` and add `{ id: 'dungeon', label: 'Dungeon' }` to the `MATCH_TYPES` array.
2. Closed doors are in the obstacles set now (blocking movement). When a door opens in 4B-2, the obstacles set must be refreshed or door tiles checked dynamically in movement validation.
3. The `tiles` grid is the source of truth for the dungeon layout. The `doors` and `chests` arrays hold metadata (state), while the grid holds positions. Both are validated as consistent by the test suite.
4. `door_states` and `chest_states` live on `MatchState` and are ready for the turn resolver to mutate (INTERACT opens a door, LOOT opens a chest).
5. `get_tiles()` returns the full 20×20 grid that the client renderer will need for tile-type-aware rendering.

---

## Phase 4B-2 — Door Mechanics, FOV & Dungeon Rendering

**Goal:** Doors become functional (open/close via INTERACT action), FOV respects door state, client renders the dungeon with viewport scrolling. The dungeon is fully playable (movement + combat) after this sub-phase.

**Duration:** 1-2 days

**Depends on:** 4B-1 (map format, models, and match creation must be working)

> **Why this is a separate sub-phase:** With the data layer locked in from 4B-1, this sub-phase focuses purely on gameplay logic (turn resolver, FOV, movement validation) and client rendering. Starting from a known-good server state prevents cascading confusion between data bugs and logic bugs.

### Deliverables

1. **Door mechanics (server logic)**
   - `turn_resolver.py`: New interaction phase (after movement, before ranged)
   - INTERACT action: player adjacent to closed door → door opens (permanent for Phase 4)
   - Open doors allow movement through; closed doors block movement
   - `combat.py` / movement validation: `is_valid_move()` checks door state

2. **FOV updates**
   - `fov.py`: Closed doors block vision (treated as walls for shadowcasting)
   - Open doors allow vision (treated as floor for shadowcasting)
   - FOV recalculates when door state changes

3. **Client renderer — dungeon tile visuals**
   - `ArenaRenderer.js`: New tile rendering for dungeon-specific types
   - Closed door: brown filled square; Open door: brown outline
   - Chest: yellow square (interactive visual)
   - Corridor: darker floor tone than room floor
   - Room floor: standard floor with subtle boundary lines

4. **Viewport / camera system**
   - If dungeon map > visible area, viewport scrolls to center on player
   - Auto-center on active player each turn
   - Smooth or snap scrolling (keep simple — snap is fine for Phase 4)

5. **Client UI updates**
   - `ActionBar.jsx`: Interact button (enabled when adjacent to closed door)
   - `GameStateContext.jsx`: Track door states and chest states from server
   - Door state updates broadcast to all players on change

### Files Affected

| File | Changes |
|------|---------|
| `server/app/core/turn_resolver.py` | Interaction phase, INTERACT action processing |
| `server/app/core/fov.py` | Door-aware shadowcasting (closed=wall, open=floor) |
| `server/app/core/combat.py` | `is_valid_move()` respects door open/closed state |
| `server/app/services/websocket.py` | Broadcast door state changes |
| `client/src/canvas/ArenaRenderer.js` | Door/chest/corridor/room tile rendering, viewport/camera |
| `client/src/components/ActionBar/ActionBar.jsx` | Interact button |
| `client/src/context/GameStateContext.jsx` | Door/chest state tracking, door-change reducer |

### Testing Criteria
- [x] INTERACT action opens a closed door
- [x] Closed doors block movement (player cannot walk through)
- [x] Open doors allow movement (player can walk through)
- [x] Closed doors block LOS/FOV (shadowcasting treats as wall)
- [x] Open doors allow LOS/FOV (shadowcasting treats as floor)
- [x] FOV recalculates correctly after a door opens
- [x] Renderer shows dungeon correctly (rooms, corridors, doors, chests)
- [x] Viewport centers on player and handles larger map sizes
- [x] Interact button appears when adjacent to a closed door
- [x] Existing arena maps and combat unaffected
- [x] All existing tests pass (228+) — **268 total (228 existing + 40 new)**

### Validation Checkpoint

> **Before starting 4C:** Full dungeon is playable — doors open on interact, FOV respects door state, renderer shows all dungeon tiles, viewport scrolls on larger maps. Movement + combat work in dungeon. All arena tests still pass.

### Implementation Notes (Completed Feb 13, 2026)

**Key decisions made during implementation:**
- **FOV requires no code changes.** The shadowcasting algorithm already takes an `obstacles` set parameter. Closed doors are in the set (block vision), open doors are removed (allow vision). This "works for free" because `get_obstacles_with_door_states()` computes the live obstacle set each tick.
- **Turn resolution order:** Cooldowns → Movement → **Interactions (doors)** → Ranged → Melee → Death → Victory. Doors open *between* movement and ranged, so a ranged shot through a just-opened door in the same turn will succeed.
- **Obstacles set is mutated in-place** when a door opens during the interact phase. This means all subsequent phases (ranged LOS checks, melee adjacency) use the updated obstacle set within the same tick.
- **Viewport is snap-scroll auto-center only** — the camera centers on the player's position each frame with no mouse-drag panning. This keeps the implementation simple for Phase 4.
- **Door interaction is cardinal-only** — players must be directly up/down/left/right of a door to open it. Diagonal adjacency does not count.
- **`is_valid_move()` unchanged** — it already checks `(target_x, target_y) in obstacles`. Because the obstacle set is recomputed per tick with door state awareness, closed doors naturally block movement and open doors naturally allow it.
- **`combat.py` unchanged** — ranged LOS uses `has_line_of_sight()` which checks the obstacles set. Same principle: door-aware obstacle set means ranged attacks are automatically blocked by closed doors and allowed through open doors.

**New file created:**
- `server/tests/test_dungeon_doors.py` — 40 tests across 11 test classes covering door interaction, movement blocking, FOV/LOS, ranged attacks through doors, phase timing, and `TurnResult.door_changes`

**Files modified (server):**
- `server/app/core/turn_resolver.py` — Added `_is_cardinal_adjacent()` helper; `resolve_turn()` gains `door_states` parameter; new Phase 1.5 interaction phase processes `INTERACT` actions, opens closed doors, mutates obstacles in-place, tracks `door_changes`; `TurnResult` returned with `door_changes`
- `server/app/models/actions.py` — `TurnResult` gained `door_changes: list[dict]` field
- `server/app/core/map_loader.py` — Added `get_obstacles_with_door_states(map_id, door_states)` that computes obstacles then removes open doors
- `server/app/core/match_manager.py` — Updated imports; `get_match_start_payload()` includes dungeon data (`tiles`, `tile_legend`, `door_states`, `chest_states`, `is_dungeon`); `dungeon_test` added to `valid_maps`
- `server/app/services/websocket.py` — Tick uses `get_obstacles_with_door_states()` for live obstacle computation; passes `door_states` to `resolve_turn()`; broadcasts `door_changes`, `door_states`, `chest_states` in turn result; `"interact"` added to valid action types

**Files modified (client):**
- `client/src/canvas/ArenaRenderer.js` — `DUNGEON_COLORS` constants; `drawDungeonTiles()` renders wall/floor/corridor/spawn/door/chest tiles with distinct visuals (closed door = brown filled + handle, open door = brown outline + ○, chest = gold box + clasp); `computeViewport()` for snap-scroll camera; `renderFrame()` accepts dungeon params; `drawFog()` and `drawDamageFloaters()` accept viewport offsets; interact queue preview in `drawQueuePreview()`
- `client/src/components/Arena/Arena.jsx` — Viewport computation via `computeViewport()`; `interactHighlights` memo for cardinally adjacent closed doors; click/hover handlers apply viewport offset; interact action mode; `obstacleSet` includes closed doors; queue preview handles interact; tile tooltip shows door/chest state
- `client/src/components/ActionBar/ActionBar.jsx` — 🚪 Interact button (shown only in dungeon, enabled when adjacent to closed door); queue display handles interact actions
- `client/src/context/GameStateContext.jsx` — Dungeon state fields (`isDungeon`, `tiles`, `tileLegend`, `doorStates`, `chestStates`); `MATCH_START` captures dungeon data; `TURN_RESULT` updates door/chest states from server
- `client/src/components/WaitingRoom/WaitingRoom.jsx` — Added `dungeon_test` map and `dungeon` match type to lobby dropdowns
- `client/src/styles/main.css` — `.btn-interact.active`, `.btn-interact:disabled`, `.queue-item.queue-interact` with gold/brown color scheme

### Known Bugs & Changes Needed (To Address Before or During 4C)

> **These are known issues identified during 4B-2 implementation. They do NOT block 4C but should be addressed soon.**
>
> **Update (Feb 13, 2026):** All bugs resolved pre-4F. See bug-log.md entries #10, #11, #12 for full details.

| # | Bug / Change | Severity | Status | Description |
|---|-------------|----------|--------|-------------|
| 1 | **Doors should toggle open/closed** | Medium | ✅ Fixed | ~~Currently doors can only be opened (permanently).~~ Turn resolver Phase 1.5 now toggles doors open↔closed. Client updated to show interact highlights on all doors (open and closed). See bug-log.md #10. |
| 2 | **Interact should be queueable at any distance** | Medium | ✅ Fixed | ~~Currently the 🚪 Interact button is only enabled when adjacent.~~ ActionBar now enables the button when any door exists on the map. Interact highlights show all visible doors. Server adjacency check unchanged. See bug-log.md #11. |
| 3 | **Selected hero should join as AI ally, not overwrite human** | High | ✅ Fixed | Hero selection now spawns an AI ally unit with the hero's stats/gear on team "a" instead of copying hero data onto the human player. Added `_hero_ally_map` tracking, `_spawn_hero_ally()`, `_remove_hero_ally()`. Permadeath and post-match persistence updated for ally ownership lookup. See bug-log.md #12. |

**What the next developer needs to know for 4C:**
1. The dungeon is fully playable — movement, combat, door interaction (toggle open/closed), FOV, and viewport all work end-to-end.
2. All 268 tests pass (228 from 4A/4B-1 + 40 new from 4B-2). Zero regressions.
3. The door state system is designed for easy extension: `door_states` dict on `MatchState` with `"x,y"` string keys. Toggle (bug #1) is now implemented — interact phase handles both open→closed and closed→open.
4. The viewport system (`computeViewport()` in ArenaRenderer.js) is auto-center only. If mouse-drag panning is needed later, the viewport computation would need to be extracted to Arena.jsx state.
5. Enemy rooms in `dungeon_test.json` have `enemy_spawns` arrays ready for 4C to use.
6. The `DUNGEON_COLORS` constant in ArenaRenderer.js defines all tile colors — easy to tweak visuals.
7. Chest interaction (`LOOT` action type) is enum-only — no turn resolver logic yet. That's a 4D deliverable.

---

## Phase 4C — Enemy Types & Enhanced AI ✅ Complete

**Goal:** 3 distinct enemy types populating dungeon rooms. Enemies behave differently based on type.

**Duration:** 3-4 days

### Implementation Summary

Phase 4C introduces typed dungeon enemies with distinct AI behavior profiles and room-based spawning. Key design decisions:
- **2 enemies per enemy room**, 1 boss per boss room (as defined in dungeon map JSON)
- **Static spawns** — enemies spawn once at match start, no respawning
- **3 AI behavior profiles**: aggressive (melee chase), ranged (kiting/distance), boss (room guardian)
- **Room leashing** — enemies stay in their assigned rooms via obstacle injection into A* pathfinding

### Deliverables

1. **Enemy type config** (`server/configs/enemies_config.json`) ✅
   - Demon: 120 HP, 18 melee damage, 4 armor, aggressive behavior, diamond shape (#cc3333)
   - Skeleton: 60 HP, 14 ranged damage, ranged behavior, range 5, triangle shape (#c8c8c8)
   - Undead Knight (boss): 200 HP, 25 melee damage, 10 armor, boss behavior, star shape (#6633aa)

2. **AI behavior profiles** ✅
   - `ai_behavior.py`: Behavior dispatch based on `ai_behavior` field
   - Aggressive profile: Chase → melee attack, room-leashed when assigned to room
   - Ranged profile: Maintain 3-4 tile distance, retreat when within 2 tiles, prioritize ranged attacks, melee as last resort
   - Boss profile: Guard room, only engage enemies inside room bounds, return to room center when idle, never leave room
   - Fallback: existing aggressive behavior for untyped AI (arena backward compatibility)
   - Room leashing via `_add_room_leash_obstacles()` — injects out-of-room tiles as obstacles for A*
   - `_find_retreat_tile()` — ranged AI finds adjacent tile maximizing distance from threat

3. **Room-based spawning** ✅
   - `_spawn_dungeon_enemies()` in `match_manager.py` reads room definitions and `enemy_spawns` with `enemy_type` metadata
   - Enemies spawned at defined positions on match start
   - Room bounds cached per match via `set_room_bounds()` / `clear_room_bounds()` for AI leashing
   - Enemy naming: "Demon-1", "Skeleton-2", "Undead Knight" (boss gets full name, no suffix)

4. **Enemy stat differentiation** ✅
   - `EnemyDefinition` model in `player.py` with per-type stats
   - `apply_enemy_stats()` configures PlayerState from enemy config
   - `PlayerState` new fields: `enemy_type`, `ai_behavior`, `room_id`, `is_boss`
   - Renderer: `ENEMY_COLORS`, `ENEMY_SHAPES`, `ENEMY_NAMES` maps in `ArenaRenderer.js`
   - Boss glow effect (purple ring) on canvas

5. **Combat log enhancement** ✅
   - New log types: `boss_kill` (#ff44ff), `enemy_spawn` (#cc3333), `room_cleared` (#4af59f)
   - Boss kill detection in `GameStateContext.jsx` — checks `is_boss` on killed target
   - Server payloads (`match_start`, `players_snapshot`, `lobby_players`) include `enemy_type`, `ai_behavior`, `is_boss`

### Files Affected

| File | Changes |
|------|---------|
| `server/configs/enemies_config.json` | **NEW** — 3 enemy type definitions with stats, behavior, visuals |
| `server/app/core/ai_behavior.py` | 3 behavior profiles (aggressive/ranged/boss), room leashing, retreat logic, room bounds cache |
| `server/app/core/match_manager.py` | `_spawn_dungeon_enemies()`, room bounds setup, payload updates |
| `server/app/models/player.py` | `enemy_type`, `ai_behavior`, `room_id`, `is_boss` fields; `EnemyDefinition` model; config loader |
| `server/configs/maps/dungeon_test.json` | `enemy_type` metadata on all `enemy_spawns` entries |
| `server/app/services/websocket.py` | `run_ai_decisions()` call passes `match_id` |
| `client/src/canvas/ArenaRenderer.js` | Enemy colors, shapes, names, boss glow, type labels |
| `client/src/components/CombatLog/CombatLog.jsx` | New log type colors (`boss_kill`, `enemy_spawn`, `room_cleared`) |
| `client/src/context/GameStateContext.jsx` | Boss kill detection in TURN_RESULT handler |
| `server/tests/test_enemy_types.py` | **NEW** — 43 tests across 10 test classes |

### Testing Criteria
- [x] 3 enemy types spawn in correct dungeon rooms
- [x] Melee Demon charges and attacks in melee
- [x] Ranged Skeleton maintains distance and shoots
- [x] Undead Knight guards room, high HP/dmg fight
- [x] Enemies stay in their rooms (don't wander freely)
- [x] Existing arena AI unaffected
- [x] Combat log shows enemy type names
- [x] Boss glow rendered on canvas
- [x] Server payloads include enemy_type, ai_behavior, is_boss

### Validation Checkpoint
- **311 tests passing** (43 new + 268 existing, 0 failures)
- Enemy config loads 3 types with correct stats
- Dungeon spawns 5 enemies (2 demons, 2 skeletons, 1 boss) at correct positions
- AI behavior dispatch routes to correct profile based on enemy_type
- Room leashing prevents enemies from leaving assigned rooms
- Ranged AI retreats from close enemies, prefers ranged attacks at distance
- Boss AI only engages targets inside its room
- Arena backward compatibility: untyped AI uses aggressive fallback
- All server payloads include new enemy fields

---

## Phase 4D — Loot & Inventory System

**Goal:** Items drop from enemies and chests. Heroes equip gear. Consumables (potions, scrolls) usable in dungeon.

**Duration:** 4-5 days (split into 3 sub-phases)

> **Note on 4D split:** Like 4B before it, Phase 4D was proactively split into three sub-phases to prevent context memory exhaustion. The loot & inventory system spans item models, config files, loot tables, equipment bonuses in combat, loot drop/pickup mechanics, consumable usage, and a full client inventory UI — touching 13+ files across server data, server logic, and client layers. Each sub-phase isolates one layer with a clear validation checkpoint.

```
4D-1 ──→ 4D-2 ──→ 4D-3
Models    Logic    UI
& Config  & Combat
```

### Open Design Questions (Resolved in 4D-1)

| # | Question | Decision |
|---|----------|----------|
| 1 | Shared party inventory or individual hero inventories? | **Individual hero inventories** — 10 slots per hero, lost on permadeath |
| 8 | Loot distribution: free-for-all or auto-distribute? | **Ground pickup + solo auto-loot** — solo: items → inventory; party: items → ground |
| 11 | Confessor healing: consumable-only or class ability? | **Consumable-only** — Health Potions (40 HP) / Greater Health Potions (75 HP). Class ability deferred to Phase 5+ |

---

### Phase 4D-1 — Item Models, Configs & Loot Generation (Server Data Layer)

**Goal:** Define all item/inventory data models, create item and loot table config files, and implement loot generation as a pure utility function. No gameplay logic, no combat integration, no client changes.

**Duration:** 1.5-2 days

**Depends on:** 4C (needs enemy types defined for loot tables)

> **Why this is a separate sub-phase:** Same pattern as 4B-1. Isolating the data layer means item models, config schemas, and loot roll logic can be fully validated before any turn resolver, combat, or client work begins. Prevents cascading bugs between data bugs and logic bugs.

#### Deliverables

1. **Item model** (`server/app/models/items.py` — **NEW**)
   - `Item`: `item_id`, `name`, `item_type` (weapon/armor/accessory/consumable), `rarity` (common/uncommon), `stat_bonuses` dict, `description`
   - `ConsumableEffect`: type (heal/portal), magnitude
   - `EquipSlot` enum: WEAPON, ARMOR, ACCESSORY
   - `Inventory`: list of items, max capacity (10 slots)

2. **Item config** (`server/configs/items_config.json` — **NEW**)
   - Common weapons: +5 to +10 damage
   - Common armor: +3 to +6 armor
   - Common accessories: +20 to +30 HP
   - Uncommon weapons: +10 to +15 damage
   - Uncommon armor: +6 to +10 armor
   - Uncommon accessories: +30 to +50 HP
   - Health Potion: restore 30-50 HP
   - Portal Scroll: party-wide dungeon escape

3. **Loot table config** (`server/configs/loot_tables.json` — **NEW**)
   - Per enemy type: drop chance, loot pool
   - Per chest type: guaranteed items, loot pool
   - Boss: guaranteed uncommon drop
   - Configurable drop rates

4. **Loot generation utility** (pure function in `items.py` or new `loot.py`)
   - `roll_loot_table(enemy_type or chest_type)` → returns list of `Item` objects
   - Uses config-driven probabilities, no match/combat integration yet
   - Deterministic seed option for testing

5. **`PlayerState` scaffolding**
   - `equipment` dict (weapon/armor/accessory slots) — default empty
   - `inventory` list — default empty
   - Fully backward compatible (empty defaults, no behavioral changes)

#### Files Affected

| File | Changes |
|------|---------|
| `server/app/models/items.py` | **NEW** — Item, ConsumableEffect, EquipSlot, Inventory models |
| `server/configs/items_config.json` | **NEW** — all item definitions |
| `server/configs/loot_tables.json` | **NEW** — drop tables per enemy/chest type |
| `server/app/models/player.py` | Add `equipment`, `inventory` to `PlayerState` (empty defaults) |
| `server/tests/test_items.py` | **NEW** — item model validation, config loading, loot roll tests |

#### Testing Criteria
- [x] `Item` model validates all item types from config
- [x] `items_config.json` loads and parses without errors
- [x] `loot_tables.json` loads and references only valid item IDs
- [x] `roll_loot_table()` produces items matching configured probabilities
- [x] Boss loot table guarantees at least one uncommon item
- [x] `PlayerState` with empty `equipment`/`inventory` is backward compatible
- [x] All 311+ existing tests pass with no modifications — **398 total (311 existing + 87 new)**

#### Validation Checkpoint

> **Before starting 4D-2:** All item models instantiate correctly, config files load and validate, loot generation produces correct items from tables, `PlayerState` has equipment/inventory fields with safe defaults, all existing tests pass. No combat changes, no turn resolver changes, no client changes.

#### Implementation Notes (Completed Feb 13, 2026)

**Design decisions resolved:**
- **Individual hero inventories** — each hero has a personal 10-slot bag. Ties into permadeath (hero dies = inventory lost).
- **Ground pickup, solo auto-loot** — solo play: loot goes straight to hero's inventory. Party play: items drop on ground for pickup. This gives parties tactical choice without friction in solo.
- **Consumable-only healing** — Confessor class ability deferred to Phase 5+. All healing via Health Potions (40 HP) and Greater Health Potions (75 HP).

**Key decisions made during implementation:**
- **Item model is a value object** — `Item` instances are freely copyable between inventories, ground, equipment slots. No unique instance IDs (items of the same `item_id` are fungible). Unique instance IDs can be added in Phase 5 if needed for affix systems.
- **Equipment and inventory on `PlayerState` are raw dicts/lists** — stored as JSON-serializable plain data for Redis compatibility. Convert to `Item`/`Equipment`/`Inventory` model instances when needed for logic. This avoids complex nested Pydantic serialization issues.
- **`StatBonuses` model** — single flat model for all stat modifiers (attack_damage, ranged_damage, armor, max_hp). Equipment.total_bonuses() sums across all slots. Clean API for 4D-2 combat integration.
- **Loot generation is pure-functional** — `roll_enemy_loot()` and `roll_chest_loot()` are stateless, config-driven, with optional deterministic seed for testing. No match/combat coupling. `validate_loot_tables()` cross-checks all item_id references.
- **Weighted pool system** — each loot table has multiple pools with relative weights. A pool is chosen by weighted random, then a random item from that pool. This gives clean control over rarity distribution without complex per-item probability math.
- **Boss guaranteed uncommon** — `guaranteed_rarity: "uncommon"` in loot table config forces the first rolled item to be uncommon. Remaining items roll normally from pools.
- **`sell_value` on every item** — pre-populated for Phase 4F merchant system. Common: 10-18g, Uncommon: 35-60g, Consumables: 15-50g.
- **18 items defined** — 3 common weapons, 3 common armor, 2 common accessories, 3 uncommon weapons, 2 uncommon armor, 2 uncommon accessories, 2 health potions, 1 portal scroll.

**New files created:**
- `server/app/models/items.py` — `Item`, `StatBonuses`, `ConsumableEffect`, `Equipment`, `Inventory`, `ItemType`, `Rarity`, `EquipSlot`, `ConsumableType` enums and models
- `server/configs/items_config.json` — 18 item definitions with full stats, descriptions, sell values
- `server/configs/loot_tables.json` — 3 enemy loot tables (demon, skeleton, undead_knight) + 2 chest loot tables (default, boss_chest)
- `server/app/core/loot.py` — Config loaders, `create_item()`, `roll_enemy_loot()`, `roll_chest_loot()`, `roll_loot_table()`, `validate_loot_tables()`
- `server/tests/test_items.py` — 87 tests across 9 test classes

**Files modified:**
- `server/app/models/player.py` — Added `equipment: dict` and `inventory: list` fields to `PlayerState` (empty defaults, fully backward compatible)

**What the next developer needs to know for 4D-2:**
1. `Equipment` and `Inventory` models in `items.py` have full equip/unequip/add/remove logic — ready for combat integration.
2. `equipment`/`inventory` on `PlayerState` are raw dicts/lists (not model instances). Use `Equipment(**ps.equipment)` and `Inventory(items=[Item(**i) for i in ps.inventory])` to convert when needed.
3. `roll_enemy_loot(enemy_type)` returns `list[Item]` — call on enemy death, place in `ground_items`.
4. `roll_chest_loot(chest_type)` returns `list[Item]` — call on chest interaction, add to inventory or ground.
5. `Equipment.total_bonuses()` returns a `StatBonuses` with summed modifiers — use in `calculate_damage()` and `calculate_ranged_damage()`.
6. Loot config caches are module-level singletons. Call `clear_caches()` in tests for isolation (the test fixture does this automatically).
7. `MatchState` already has `ground_items` as a delivery target — it needs to be added (currently only `door_states`/`chest_states` exist). This is a 4D-2 task.

---

### Phase 4D-2 — Equipment, Loot Drops & Consumables (Server Gameplay Logic)

**Goal:** Equipment stat bonuses affect combat. Enemies drop loot on death. Chests generate items on interaction. Ground items can be picked up. Health potions heal. Full server-side loot loop working.

**Duration:** 1.5-2 days

**Depends on:** 4D-1 (needs item models, configs, and loot generation utility)

> **Why this is a separate sub-phase:** This is the hardest part of 4D — integrating loot into combat, the turn resolver, and match state. Isolating it from client work means every mechanic can be fully tested via the existing test suite and WS message inspection before any JSX is written.

#### Deliverables

1. **Equipment bonuses in combat**
   - `combat.py`: `calculate_damage()` adds weapon `stat_bonuses.attack_damage` to attacker's base
   - `combat.py`: `calculate_ranged_damage()` adds weapon `stat_bonuses.ranged_damage` to attacker's base
   - Defender armor calculation adds equipment `stat_bonuses.armor`
   - Equipment HP bonus applied at equip time (increases `max_hp` and `hp`)

2. **Ground items tracking**
   - `MatchState` gains `ground_items: dict[str, list[Item]]` — keyed by `"x,y"` string (same pattern as `door_states`)
   - Items persist on ground until picked up

3. **Enemy death → loot drop**
   - Turn resolver death phase: on enemy death, call `roll_loot_table(enemy_type)`, place resulting items in `ground_items` at death tile
   - `TurnResult` gains `loot_drops: list[dict]` field — `[{x, y, items: [...]}]`

4. **Chest interaction (`LOOT` action)**
   - Turn resolver: player cardinally adjacent to unopened chest + `LOOT` action → generate items from chest loot table → add to player's inventory (overflow to ground) → mark chest as `"opened"` in `chest_states`
   - `TurnResult` gains `chest_opened: list[dict]` field — `[{x, y, items: [...]}]`

5. **Ground item pickup (`LOOT` action on item tile)**
   - Player standing on tile with `ground_items` + `LOOT` action → move items to player's `inventory`
   - Inventory cap enforced (10 slots) — excess items stay on ground
   - `TurnResult` gains `items_picked_up: list[dict]` field

6. **Equip/unequip via WS messages**
   - `equip_item` message: move item from inventory to equipment slot, apply stat bonuses
   - `unequip_item` message: move item from equipment slot to inventory, remove stat bonuses
   - Broadcast updated player stats to all clients
   - Reject equip if wrong slot type (e.g., armor in weapon slot)

7. **`USE_ITEM` action — Health Potion**
   - `ActionType.USE_ITEM` added to actions enum
   - Turn resolver item-use phase (after cooldowns, before movement): consume potion → restore HP (capped at `max_hp`) → remove from inventory
   - `TurnResult` gains `items_used: list[dict]` field — `[{player_id, item_id, effect}]`

8. **Portal Scroll**
   - Stored in inventory only — actual escape mechanic deferred to 4F
   - `USE_ITEM` on portal scroll returns a message: "Portal scrolls can only be used in dungeon escape (coming in 4F)"

#### Files Affected

| File | Changes |
|------|---------|
| `server/app/core/combat.py` | Equipment bonuses in `calculate_damage()`, `calculate_ranged_damage()` |
| `server/app/core/turn_resolver.py` | Item-use phase, loot drop on death, chest interaction, ground item pickup |
| `server/app/core/match_manager.py` | `ground_items` init, loot generation calls, equip/unequip logic |
| `server/app/models/match.py` | Add `ground_items` to `MatchState` |
| `server/app/models/actions.py` | Add `USE_ITEM` to `ActionType`, new fields on `TurnResult` |
| `server/app/services/websocket.py` | `equip_item`, `unequip_item`, `use_item` message handlers; loot broadcast |
| `server/tests/test_loot_combat.py` | **NEW** — equipment bonuses, loot drops, chest interaction, inventory cap, potion heal |

#### Testing Criteria
- [x] Equipped weapon increases melee/ranged damage in `calculate_damage()`
- [x] Equipped armor increases damage reduction in combat
- [x] Enemy death produces loot on death tile (via `ground_items`)
- [x] Boss death guarantees uncommon loot drop
- [x] Chest interaction generates items, marks chest opened
- [x] Opened chest cannot be looted again
- [x] Standing on ground items + LOOT → items move to inventory
- [x] Inventory cap enforced — excess items stay on ground
- [x] Equip/unequip updates player stats correctly
- [x] Health Potion restores HP (capped at max_hp), consumed on use
- [x] Portal Scroll stored but not usable yet
- [x] All 398+ existing tests pass — **446 total (398 existing + 48 new)**

#### Validation Checkpoint

> **Before starting 4D-3:** Kill an enemy → items appear in `ground_items`. Interact with chest → items generated. Pick up items → inventory fills. Equip gear → combat stats change. Use potion → heal. All server logic validated via tests. No client UI yet.

#### Implementation Notes (Completed Feb 13, 2026)

**Key decisions made during implementation:**
- **Equipment bonuses are read lazily per combat calculation** — `_get_equipment_bonuses()` in `combat.py` deserializes raw dict equipment into `Item`/`Equipment` models, calls `total_bonuses()`, and returns a `StatBonuses`. This avoids storing derived stats and always reflects the current equipment state. Gracefully handles malformed equipment data (returns zero bonuses).
- **Turn resolution order updated:** Item Use → Cooldowns → Movement → Interactions (doors) → **Loot Actions (chests + ground pickup)** → Ranged → Melee → **Death + Loot Drops** → Victory. Item use happens first so potions heal before combat. Loot drops happen after death so items appear at the death tile immediately.
- **Loot drops are enemy-only** — only units with `enemy_type` set (AI enemies) drop loot on death. Player deaths produce no loot drops. This preserves arena mode behavior.
- **Chest loot overflows to ground** — when a player loots a chest and their inventory is full, excess items are placed on the ground at the chest tile. The ground_items dict at that key is created on demand.
- **USE_ITEM uses target_x as inventory index** — to specify which item to use, `target_x` on the `PlayerAction` is repurposed as an inventory index. If not provided, the first consumable in inventory is used. This avoids adding custom fields to the action model.
- **Portal scroll rejection is non-destructive** — attempting to use a portal scroll returns a failure message mentioning Phase 4F but does NOT consume the scroll.
- **Equip/unequip is a WS message, not a turn action** — `equip_item` and `unequip_item` are instant (not queued into the turn system). They execute immediately when the WS message is received, apply stat changes, and broadcast the update.
- **Max HP bonus on equip is additive** — equipping an accessory with `max_hp: +30` increases both `max_hp` and current `hp` by 30. Unequipping reduces `max_hp` and clamps `hp` to the new max.
- **ground_items on MatchState uses "x,y" string keys** — same pattern as `door_states` and `chest_states` for JSON serialization compatibility.
- **Loot drops in turn_result are FOV-filtered** — the websocket tick only sends `loot_drops` for tiles visible to the player.
- **Private inventory/equipment sent per-tick** — each player receives `my_inventory` and `my_equipment` in every `turn_result` payload, ensuring the client always has current data.

**New files created:**
- `server/tests/test_loot_combat.py` — 48 tests across 12 test classes covering all 4D-2 deliverables

**Files modified:**
- `server/app/models/actions.py` — Added `USE_ITEM` to `ActionType` enum; added `loot_drops`, `chest_opened`, `items_picked_up`, `items_used` fields to `TurnResult`
- `server/app/models/match.py` — Added `ground_items: dict[str, list]` to `MatchState`
- `server/app/core/combat.py` — Added `_get_equipment_bonuses()` helper; `calculate_damage()` and `calculate_ranged_damage()` now include equipment stat bonuses for both attacker and defender
- `server/app/core/turn_resolver.py` — New Phase 0 (item use: health potions, portal scroll rejection), Phase 1.75 (loot: chest interaction + ground pickup), Phase 3.5 (loot drops on death); accepts `chest_states` and `ground_items` parameters; returns full loot event data
- `server/app/core/match_manager.py` — `_init_dungeon_state()` initializes `ground_items`; `get_dungeon_state()` returns `ground_items`; new `equip_item()`, `unequip_item()`, `_apply_equipment_stats()`, `_remove_equipment_stats()` functions
- `server/app/services/websocket.py` — Tick passes `chest_states`/`ground_items` to `resolve_turn()`; broadcasts loot events, ground_items, and per-player inventory/equipment in turn_result; `"loot"` and `"use_item"` added to valid action types; `equip_item` and `unequip_item` WS message handlers with stat broadcast

**What the next developer needs to know for 4D-3:**
1. Every `turn_result` payload now includes `my_inventory` (list of item dicts) and `my_equipment` (dict of slot → item dict or null) for the receiving player.
2. `ground_items` is included in the `turn_result` payload for dungeon matches — keyed by `"x,y"`, each value is a list of item dicts. The client should render loot sparkle/icons at these positions.
3. `loot_drops` in the payload is already FOV-filtered — only drops visible to the player are included.
4. `chest_opened` contains `added_to_inventory` and `overflow_to_ground` sublists for UI feedback.
5. `items_used` contains `effect.actual_healed` for potion use feedback.
6. `equip_item` WS message format: `{"type": "equip_item", "item_id": "sword_01"}` → response: `{"type": "item_equipped", "slot": "weapon", "equipped": {...}, "unequipped": {...} or null, "player_stats": {...}}`
7. `unequip_item` WS message format: `{"type": "unequip_item", "slot": "weapon"}` → response: `{"type": "item_unequipped", "slot": "weapon", "unequipped": {...}, "player_stats": {...}}`
8. LOOT action for chests: `{"type": "action", "action_type": "loot", "target_x": 4, "target_y": 5}` (target is the chest tile). LOOT for ground pickup: `{"type": "action", "action_type": "loot"}` (no target — picks up items at player's current tile).
9. USE_ITEM action: `{"type": "action", "action_type": "use_item", "target_x": 0}` where target_x is inventory index of the consumable to use.

---

### Phase 4D-3 — Client Inventory UI & Ground Item Rendering

**Goal:** Full client-side loot experience — see items on the ground, pick them up, view inventory, equip/unequip gear, use consumables. All consuming the stable 4D-2 server API.

**Duration:** 1-1.5 days

**Depends on:** 4D-2 (needs stable server API for all loot/inventory/equip messages)

> **Why this is a separate sub-phase:** With the server API locked in from 4D-2, the client work is purely consuming known WS message shapes. This is the least risky part and can be validated visually end-to-end.

#### Deliverables

1. **Inventory component** (`client/src/components/Inventory/Inventory.jsx` — **NEW**)
   - 3 equipment slots (weapon/armor/accessory) with slot labels and item cards
   - 10-slot bag grid showing inventory items
   - Click to equip/unequip (sends `equip_item` / `unequip_item` WS message)
   - Use consumable button (sends `use_item` WS message)
   - Rarity color coding (common = white/gray, uncommon = green)
   - Item tooltip: name, type, rarity, stat bonuses, description

2. **Ground item rendering** (`ArenaRenderer.js`)
   - Sparkle/icon overlay on tiles with dropped loot
   - Chest visual state: unopened (gold box) vs opened (open box, dimmed)
   - Loot highlight when player stands on a tile with items

3. **ActionBar updates** (`ActionBar.jsx`)
   - 🎒 Loot button (enabled when standing on ground items OR adjacent to unopened chest)
   - Potion quick-use button (if player has health potion in inventory)
   - Queue display handles `loot` and `use_item` actions

4. **GameState context** (`GameStateContext.jsx`)
   - New state fields: `inventory`, `equipment`, `groundItems`
   - Reducers: `LOOT_DROP` (enemy dies → items on ground), `CHEST_OPENED` (chest → items), `ITEMS_PICKED_UP` (ground → inventory), `ITEM_EQUIPPED`, `ITEM_UNEQUIPPED`, `ITEM_USED`
   - Ground items updated from `turn_result` payload

5. **HUD updates** (`HUD.jsx`)
   - Equipment summary line: equipped weapon/armor/accessory names
   - Inventory count: "Bag: 3/10"
   - Potion count if carrying health potions

6. **Loot pickup prompt**
   - Visual notification/highlight when player stands on a tile with ground items
   - "Items here! Press Loot to pick up" indicator

#### Files Affected

| File | Changes |
|------|---------|
| `client/src/components/Inventory/Inventory.jsx` | **NEW** — full inventory UI |
| `client/src/canvas/ArenaRenderer.js` | Ground item sparkle, chest state visuals, loot highlight |
| `client/src/components/ActionBar/ActionBar.jsx` | Loot button, potion quick-use button |
| `client/src/context/GameStateContext.jsx` | Inventory/equipment/groundItems state + reducers |
| `client/src/components/HUD/HUD.jsx` | Equipment summary, bag count, potion count |
| `client/src/components/Arena/Arena.jsx` | Loot action mode, ground item click handling |
| `client/src/styles/main.css` | Inventory panel CSS, rarity colors, loot prompt styles |

#### Testing Criteria
- [x] Inventory panel shows equipped items in correct slots
- [x] Bag grid shows inventory items with rarity colors
- [x] Click equip/unequip sends correct WS message, UI updates
- [x] Use potion button works, item consumed, HP updates in HUD
- [x] Ground items render as sparkle on dungeon tiles
- [x] Chest visual updates from unopened → opened
- [x] Loot button enabled at correct times (ground items / adjacent chest)
- [ ] Full end-to-end: kill enemy → see loot → pick up → inventory → equip → stat change visible
- [x] Existing arena mode UI unaffected

#### Validation Checkpoint

> **Before starting 4E:** Full visual loot loop working in client. Kill enemy → loot sparkle on ground → pick up → see in inventory → equip → HUD stat change → use potion → heal visible. All tests pass.

#### Implementation Notes (Completed Feb 13, 2026)

**Key decisions made during implementation:**
- **Inventory/equipment state is updated per-tick** — the `TURN_RESULT` reducer reads `my_inventory` and `my_equipment` from every server payload, ensuring the client always reflects server truth. No optimistic local updates for loot pickup.
- **Equip/unequip is instant via WS** — `item_equipped` and `item_unequipped` WS message types are routed from `App.jsx` → `ITEM_EQUIPPED` / `ITEM_UNEQUIPPED` reducers which update inventory/equipment state immediately. `player_stats_updated` broadcasts update the players map for other clients.
- **Ground items updated from `turn_result`** — the `ground_items` dict is delivered by the server each tick for dungeon matches. The client stores it as-is in `groundItems` state.
- **Loot log entries generated client-side** — `TURN_RESULT` reducer generates combat log entries from `loot_drops`, `chest_opened`, `items_picked_up`, and `items_used` payload fields with gold (`loot`) and green (`heal`) coloring.
- **Inventory component is sidebar-only, dungeon-only** — the `<Inventory>` panel renders between ActionBar and CombatLog in the sidebar. It's conditionally shown only when `isDungeon` is true. Arena mode is completely unaffected.
- **Click-to-equip/use in bag grid** — clicking an equippable item sends `equip_item` WS message; clicking a consumable sends `use_item` action with the inventory index. Equipment slots click-to-unequip.
- **Item tooltips are inline** — hovering any slot shows a tooltip at the bottom of the inventory panel with full item details (name, rarity, stats, description, sell value, action hint).
- **Ground items rendered as pulsing sparkle** — `drawGroundItems()` renders a pulsing glow + ✦ icon on tiles with loot. Uncommon items glow green, common glow gold. Item count badge shown for 2+ items.
- **Loot highlight on player's tile** — when the player stands on ground items, a dashed gold border pulses on their tile and a "Items here! Press 🎒 Loot to pick up" prompt appears at the bottom of the canvas.
- **ActionBar Loot button** — prioritizes adjacent chest interaction (sends `loot` action with chest coords) over ground pickup (sends `loot` action with no target). Potion quick-use button shows count and sends `use_item` with the first health potion's inventory index.
- **Queue display** — loot and use_item actions render with descriptive labels ("🎒 Loot Chest → (x,y)", "🎒 Pick Up Items", "🧪 Use Potion").
- **Rarity color system** — common items use default gray/white, uncommon items get green borders and text (`#4caf50`). Applied consistently to equipment slots, bag grid, tooltips, and HUD.
- **CombatLog new colors** — `loot` type = gold (#daa520), `heal` type = light green (#88ff88).

**New files created:**
- `client/src/components/Inventory/Inventory.jsx` — Full inventory UI with 3 equipment slots, 10-slot bag grid, item tooltips, click-to-equip/unequip/use

**Files modified:**
- `client/src/context/GameStateContext.jsx` — Added `inventory`, `equipment`, `groundItems` to initial state; `MATCH_START` resets loot state; `TURN_RESULT` reads `my_inventory`/`my_equipment`/`ground_items`/`loot_drops`/`chest_opened`/`items_picked_up`/`items_used`; added `ITEM_EQUIPPED`, `ITEM_UNEQUIPPED`, `PLAYER_STATS_UPDATED` reducers; loot/heal combat log entries
- `client/src/App.jsx` — Routes `item_equipped`, `item_unequipped`, `player_stats_updated` WS messages to dispatcher
- `client/src/canvas/ArenaRenderer.js` — Added `drawGroundItems()` (pulsing sparkle + item count), `drawLootHighlight()` (dashed border); `renderFrame()` accepts `groundItems` and `lootHighlightTile` params
- `client/src/components/ActionBar/ActionBar.jsx` — Added 🎒 Loot button (ground items + adjacent chest), 🧪 Potion quick-use button with count, queue display for `loot`/`use_item` actions
- `client/src/components/Arena/Arena.jsx` — Imports Inventory; pulls `groundItems` from state; computes `lootHighlightTile` memo; passes `groundItems`/`lootHighlightTile` to renderer; ground items in tooltip; loot prompt overlay; mounts `<Inventory>` in sidebar
- `client/src/components/HUD/HUD.jsx` — Equipment summary (weapon/armor/accessory names with rarity coloring), bag count (x/10), potion count
- `client/src/components/CombatLog/CombatLog.jsx` — Added `loot` (gold) and `heal` (green) log type colors
- `client/src/styles/main.css` — Inventory panel, equipment slots, bag grid, item tooltips, rarity color system, loot/potion button styles, queue item colors, loot prompt animation, HUD equipment summary

**What the next developer needs to know for 4E:**
1. The full client loot loop is complete — all server data from 4D-2 is consumed and rendered.
2. All 446 server tests pass. No server files were modified in 4D-3.
3. The `inventory` and `equipment` state fields are raw dicts/lists matching the server's `PlayerState.inventory` and `PlayerState.equipment` format.
4. The `<Inventory>` component accepts `sendAction` as a prop to send `equip_item`/`unequip_item` WS messages.
5. Arena mode is completely unaffected — all dungeon UI (Inventory panel, Loot button, Potion button, equipment summary, ground items) is gated behind `isDungeon`.
6. The one remaining unchecked testing criterion (full end-to-end visual loop) requires manual playtesting with a running server.

---

## Phase 4E — Hero Hiring & Persistence

**Goal:** Persistent hero roster, tavern hiring, gold economy, permadeath. Heroes survive between dungeon runs.

**Duration:** 4-5 days (split into 3 sub-phases)

> **Note on 4E split:** Like 4B and 4D before it, Phase 4E was proactively split into three sub-phases to prevent context memory exhaustion. Hero hiring & persistence spans new persistence infrastructure, new data models, new REST routes, match manager integration, permadeath hooks, gold economy, and an entirely new client screen with complex UI flows — touching 10+ new and modified files across server data, server logic, and client layers. Each sub-phase isolates one layer with a clear validation checkpoint.

```
4E-1 ──→ 4E-2 ──→ 4E-3
Models    Match     Town
Persist   Integrate Hub UI
& REST    & Perma-
          death
```

### Open Design Questions (Resolve in 4E-1)

| # | Question | Decision |
|---|----------|----------|
| 2 | Starting gold amount? | 100g |
| 3 | Hiring costs per class (flat or stat-scaled)? | For now 100g |
| 9 | Hero name generation: procedural or curated list? | For now just make a curated lsit |
| 10 | Bank storage in town (yes/no, capacity)? | *Defer to later date* |

---

### Phase 4E-1 — Hero Models, Persistence & Town REST API (Server Data Layer)

**Goal:** Define all hero/profile data models, implement JSON-based persistence, create hero generation system, and expose Town REST endpoints for hiring and roster management. No match integration, no turn resolver changes, no client changes.

**Duration:** 1.5-2 days

**Depends on:** 4D-3 (heroes need classes + equippable items)

> **Why this is a separate sub-phase:** Same proven pattern as 4B-1 and 4D-1. Isolating the data layer means hero models, persistence, name generation, and REST endpoints can be fully validated (via tests + curl/Postman) before any match manager or client work begins. Prevents cascading bugs between persistence bugs and gameplay-logic bugs.

#### Deliverables

1. **Player profile model** (`server/app/models/profile.py` — **NEW**)
   - `PlayerProfile`: `player_id`, `username`, `gold`, `heroes` list, `bank` (item storage)
   - `Hero`: `hero_id`, `name`, `class_id`, `base_stats` (with stat variation), `equipment`, `inventory`, `is_alive`, `hire_cost`
   - Starting gold: configurable (e.g., 100 gold)
   - Stat variation: base class stats ± small random range (e.g., ±10%)

2. **Persistence layer** (`server/app/services/persistence.py` — **NEW**)
   - JSON file-based storage (`server/data/players/{username}.json`)
   - `save_profile(profile)` — write to disk atomically
   - `load_profile(username)` — read from disk, return `PlayerProfile`
   - `create_default_profile(username)` — new player with starting gold, empty roster
   - Auto-create profile on first access (no separate registration step)
   - Graceful handling of missing/corrupt files (log warning, create fresh)
   - Profile survives server restarts

3. **Hero generation system**
   - Name generator config (`server/configs/names_config.json` — **NEW**) — curated name list per class theme
   - `generate_tavern_heroes(count=5)` — creates heroes across all classes with stat variation
   - Hiring cost scaled by total stat points (better stats = higher cost)
   - Tavern pool stored per-player (refreshable)

4. **Town REST endpoints** (`server/app/routes/town.py` — **NEW**, mounted at `/api/town`)
   - `GET /api/town/profile?username=X` — load or create player profile (gold, hero count)
   - `GET /api/town/tavern?username=X` — get available heroes for hire (generates if empty)
   - `POST /api/town/hire` — spend gold, add hero to roster `{username, hero_id}`
   - `GET /api/town/roster?username=X` — list all owned heroes with stats/gear
   - `POST /api/town/tavern/refresh` — refresh the tavern pool `{username}`

5. **`server/app/main.py` update**
   - Mount `town_router` at `/api/town`
   - Ensure `server/data/players/` directory created on startup if missing

6. **Tests** (`server/tests/test_heroes.py` — **NEW**)
   - Profile model validation (create, serialize, deserialize)
   - Persistence save/load (write to disk, read back, verify)
   - Corrupt/missing file handling
   - Hero generation (stat variation within bounds, names unique)
   - Tavern generation (correct count, all classes represented)
   - Hiring flow (gold deducted, hero added to roster, duplicate hire rejected)
   - REST endpoint integration tests

#### Files Affected

| File | Changes |
|------|---------|
| `server/app/models/profile.py` | **NEW** — `PlayerProfile`, `Hero`, `HeroStats` models |
| `server/app/services/persistence.py` | **NEW** — JSON file save/load/create |
| `server/configs/names_config.json` | **NEW** — curated name lists per class |
| `server/app/routes/town.py` | **NEW** — tavern, hiring, roster REST endpoints |
| `server/app/main.py` | Mount town router, ensure data directory exists |
| `server/tests/test_heroes.py` | **NEW** — hero model, persistence, generation, hiring tests |

#### Testing Criteria
- [x] `PlayerProfile` and `Hero` models validate correctly
- [x] `save_profile()` / `load_profile()` round-trip produces identical data
- [x] Missing profile file → auto-creates default profile
- [x] Corrupt JSON file → logs warning, creates fresh profile
- [x] `generate_tavern_heroes()` produces heroes with stat variation within bounds
- [x] Hero names are unique within a tavern pool
- [x] Hiring deducts correct gold, adds hero to roster
- [x] Cannot hire with insufficient gold
- [x] Cannot hire same hero twice
- [x] REST endpoints return correct data via integration tests
- [x] Profile persists across server restarts (file on disk)
- [x] All 446+ existing tests pass with no modifications — **521 total (446 existing + 75 new)**

#### Validation Checkpoint

> **Before starting 4E-2:** REST endpoints work via curl/Postman. Profile saves to disk and loads back correctly. Tavern generates heroes with stat variation. Hiring deducts gold and adds hero to roster. All existing tests pass. No match manager changes, no client changes.

### Implementation Notes (Completed Feb 13, 2026)

**Key decisions made during implementation:**
- `HeroStats` model is separate from `PlayerState` stats — Hero stores base stats with variation, and 4E-2 will copy these into `PlayerState` at match join.
- Stat variation applies ±10% to all stats except `ranged_range` (exact copy from class config). Minimum stat value is 1 (never 0 or negative for non-zero bases). Zero base stats stay zero (e.g., Crusader ranged_damage=0).
- Hire cost scales by total stat power: `BASE_HIRE_COST + total_stat_points * 0.15`. This means stronger stat rolls cost more gold. Crusaders (high HP+armor) naturally cost more than Confessors.
- Tavern pool is stored per-player on `PlayerProfile.tavern_pool` and persists until manually refreshed. This prevents the pool from changing on every page load.
- Names are drawn from `names_config.json` with class-specific pools (15 names each), a generic fallback pool (10 names), and a numbered fallback (e.g., "Crusader #1") if all names are exhausted.
- Persistence uses atomic writes (write temp file → rename) to prevent corruption on crash.
- Username sanitization for filenames: non-alphanumeric characters replaced with underscores.
- `HERO_ROSTER_MAX = 10` — dead heroes don't count toward the cap (only alive heroes).
- The names config cache is module-level in `town.py` routes, cleared in tests for isolation.

**New files created:**
- `server/app/models/profile.py` — `PlayerProfile`, `Hero`, `HeroStats` models; `generate_hero()`, `generate_tavern_heroes()`, stat variation utilities
- `server/app/services/persistence.py` — JSON file save/load/create/delete, atomic writes, auto-create on first access
- `server/configs/names_config.json` — 15 curated names per class (5 classes) + 10 generic fallback names
- `server/app/routes/town.py` — 5 REST endpoints: GET profile, GET tavern, POST hire, GET roster, POST tavern/refresh
- `server/tests/test_heroes.py` — 75 tests across 10 test classes

**Files modified:**
- `server/app/main.py` — Mount `town_router` at `/api/town`; ensure `server/data/players/` directory on startup

---

### Phase 4E-2 — Match Integration & Permadeath (Server Gameplay Logic)

**Goal:** Connect persistent heroes to the match lifecycle. Hero's class, stats, and equipment load into `PlayerState` at match join. Permadeath removes dead heroes permanently. Post-match persistence saves loot and gold back to profile.

**Duration:** 1.5-2 days

**Depends on:** 4E-1 (needs hero models, persistence layer, and profile CRUD working)

> **Why this is a separate sub-phase:** This is the hardest part of 4E — integrating persistence into the match lifecycle, death handling, and post-match flow. Isolating it from client work means every mechanic can be fully tested via the existing test suite and REST/WS inspection before any JSX is written.

#### Deliverables

1. **Hero selection at match join**
   - `create_match()` / `join_match()` accept optional `hero_id` parameter
   - When `hero_id` provided: load hero from profile → apply `class_id`, stats (with variation), `equipment`, `inventory` to `PlayerState`
   - Equipment bonuses applied at spawn (reuse existing `_apply_equipment_stats` pattern from `match_manager.py`)
   - New `hero_id` field on `PlayerState` to track which persistent hero is in-match
   - Reject join if hero is dead (`is_alive=false`) or already in another match

2. **Permadeath on hero death**
   - Turn resolver death phase: if dead player has `hero_id`, call persistence to mark `is_alive=false`
   - Dead hero's equipment and inventory are lost (cleared on profile)
   - Auto-save profile immediately on death
   - `TurnResult` gains `hero_deaths: list[dict]` field — `[{hero_id, hero_name, class_id, lost_items: [...]}]`

3. **Post-match persistence**
   - On match end / dungeon escape: persist surviving heroes' `inventory` and `equipment` back to profile
   - Gold rewards: configurable gold per enemy killed, bonus for boss kill
   - Gold config added to `server/configs/combat_config.json` or similar
   - Save updated gold to profile
   - `match_end` payload includes per-hero outcome: `survived`/`died`, items kept, gold earned

4. **WS/REST updates for hero selection**
   - `hero_select` WS message in lobby — player selects which hero to bring into dungeon
   - Broadcast `hero_selected` to lobby (other players see teammate's hero choice)
   - Lobby payload includes hero info for each player (name, class, stats preview)
   - Modify `start_match()` to validate all dungeon players have selected a hero

5. **Tests** (`server/tests/test_hero_persistence.py` — **NEW**)
   - Hero loads into `PlayerState` with correct stats/equipment
   - Equipment bonuses applied at match start
   - Permadeath: hero marked dead on profile after death in match
   - Dead hero's gear cleared on profile
   - Post-match save: surviving hero inventory/equipment updated
   - Gold earned from kills persisted to profile
   - Cannot join match with dead hero
   - Cannot join match without selecting a hero (dungeon mode)
   - Arena mode unaffected (no hero required)

#### Files Affected

| File | Changes |
|------|---------|
| `server/app/core/match_manager.py` | Hero loading at join, `hero_id` on `PlayerState`, permadeath hook, post-match save |
| `server/app/core/turn_resolver.py` | Minor — death phase triggers permadeath callback |
| `server/app/models/player.py` | Add `hero_id` field to `PlayerState` |
| `server/app/models/actions.py` | Add `hero_deaths` to `TurnResult` |
| `server/app/services/websocket.py` | `hero_select` message handler, hero info in lobby payload, `hero_deaths` broadcast |
| `server/app/routes/lobby.py` | `hero_id` parameter on create/join endpoints |
| `server/configs/combat_config.json` | Gold reward values (per enemy kill, boss bonus) |
| `server/tests/test_hero_persistence.py` | **NEW** — hero→match integration, permadeath, post-match persistence |

#### Testing Criteria
- [x] Hero's class/stats/equipment correctly loaded into `PlayerState`
- [x] Equipment bonuses from persistent gear applied in combat
- [x] Permadeath: dead hero marked `is_alive=false` on profile
- [x] Dead hero's equipment/inventory cleared on profile
- [x] Surviving hero's inventory/equipment persisted after match end
- [x] Gold earned from kills saved to profile
- [x] Cannot join dungeon match with dead hero
- [x] Cannot start dungeon match without hero selection
- [x] Arena mode completely unaffected (no hero_id required)
- [x] `match_end` payload includes per-hero outcomes
- [x] All 521+ existing tests pass (arena backward compat) — **556 total (521 existing + 35 new)**

#### Validation Checkpoint

> **Before starting 4E-3:** Create a hero via REST (4E-1) → select hero in lobby via WS → start dungeon → hero's gear/stats used in combat → if hero dies, profile updated with `is_alive=false` and gear cleared → if hero survives, loot/gold persisted to profile → verify via `GET /api/town/roster`. All tests pass. No client UI yet — testable via WS tools and REST calls.

### Implementation Notes (Completed Feb 13, 2026)

**Key decisions made during implementation:**
- `hero_id` added as an optional field on `PlayerState` (default: `None`). This links an in-match player to their persistent `Hero` on the player's profile. Arena mode players have `hero_id=None` — complete backward compatibility.
- Hero selection is tracked in a new `_hero_selections` dict in `match_manager.py` (match_id → player_id → hero_id). Selection persists through match start, similar to `_class_selections`.
- `_load_heroes_at_match_start()` is called after class selection but before dungeon state init. It copies hero stats, equipment, and inventory from the profile onto the `PlayerState`, then applies equipment stat bonuses.
- Equipment bonuses are applied at load time via `_apply_hero_equipment_bonuses()` — iterates all equipped items and applies `max_hp` bonuses (the only stat bonus currently supported).
- Permadeath is handled by `handle_hero_permadeath()` — called from the turn resolver's death phase for any dead unit with a `hero_id`. Marks the hero `is_alive=False`, clears equipment/inventory, saves profile immediately.
- Kill tracking uses a per-match `_kill_tracker` dict: match_id → player_id → {enemy_kills, boss_kills}. The turn resolver calls `track_kill()` for each enemy killed by iterating resolved action results that have `killed=True`.
- Post-match persistence (`_persist_post_match()`) runs inside `end_match()`. For surviving heroes: copies PlayerState inventory/equipment back to Hero on profile, awards gold (configurable: 10g/enemy, 50g/boss, 25g clear bonus), increments `matches_survived` and `enemies_killed` counters. Dead heroes are skipped (permadeath already handled mid-match).
- Gold rewards are configurable via `combat_config.json`: `gold_per_enemy_kill` (10), `gold_per_boss_kill` (50), `gold_dungeon_clear_bonus` (25).
- Dungeon matches validate hero selection at match start: `validate_dungeon_hero_selections()` is called when all players are ready. If any human player hasn't selected a hero, the match start is blocked with an error message. Arena matches skip this check entirely.
- `hero_select` WS message handler validates hero ownership, alive status, and stores the selection. ~~Also auto-sets `class_select` to match the hero's class~~ (removed in pre-4F bug fix — hero now spawns as AI ally, human keeps own class).
- `hero_selected` WS broadcast includes hero name, class, and stats so other lobby members can see teammate hero choices.
- `hero_deaths` field added to `TurnResult` — populated by the turn resolver when heroes die. Each entry contains `hero_id`, `hero_name`, `class_id`, `player_id`, `username`, and `lost_items` list.
- `match_end` payload extended with `hero_outcomes` dict — per-player status (survived/died), gold earned, kill counts. Built by `get_match_end_payload()`.
- Lobby players payload (`get_lobby_players_payload`) now includes `hero_id` for players who have selected a hero.
- **~~556~~ 559 tests pass** — 521 existing + 35 new + 3 net from pre-4F bug-fix refactoring (hero-as-ally, door toggle). See bug-log.md #10-#12.

**Post-4E-2 refactor (pre-4F bug fixes, Feb 13, 2026):**
- Hero selection changed from "play as hero" to "hero joins as AI ally." `select_hero()` now calls `_spawn_hero_ally()` to create an AI unit with the hero's stats/gear on team "a". Human player keeps their own class and default stats.
- Added `_hero_ally_map` tracking dict (`match_id → {ai_unit_id → owner_username}`) for ownership tracking through permadeath and post-match persistence.
- `_load_heroes_at_match_start()` short-circuits if hero allies already spawned.
- `handle_hero_permadeath()` and `_persist_post_match()` updated to use `_hero_ally_map` for owner lookup.
- `hero_select` WS handler no longer calls `select_class()` — human keeps own class.
- Tests in `test_hero_persistence.py` rewritten for hero-as-ally flow (find ally by `hero_id` + `unit_type=="ai"`).

**New files created:**
- `server/tests/test_hero_persistence.py` — 35 tests across 9 test classes

**Files modified:**
- `server/app/models/player.py` — Added `hero_id` field to `PlayerState`
- `server/app/models/actions.py` — Added `hero_deaths` field to `TurnResult`
- `server/configs/combat_config.json` — Added `gold_per_enemy_kill`, `gold_per_boss_kill`, `gold_dungeon_clear_bonus` values
- `server/app/core/match_manager.py` — Added `_hero_selections`, `_username_map`, `_kill_tracker` tracking dicts; `select_hero()`, `get_hero_selection()`, `_load_heroes_at_match_start()`, `_apply_hero_equipment_bonuses()`, `handle_hero_permadeath()`, `track_kill()`, `get_kill_tracker()`, `_persist_post_match()`, `get_match_end_payload()`, `validate_dungeon_hero_selections()` functions; updated `create_match()`, `join_match()`, `start_match()`, `end_match()`, `remove_match()`, `get_lobby_players_payload()`
- `server/app/core/turn_resolver.py` — Added Phase 3.75 (kill tracking + permadeath) in death phase; imports `track_kill`, `handle_hero_permadeath` from match_manager; `hero_deaths` populated and returned in `TurnResult`
- `server/app/services/websocket.py` — Imported new match_manager functions; added `hero_select` WS message handler; added hero validation before match start; added `hero_deaths` to turn_result payload; added `hero_outcomes` to match_end payload

**What the next developer needs to know for 4E-3:**
1. Hero selection in lobby sends `hero_select` WS message with `{hero_id}` → server responds with `hero_selected` broadcast including hero name, class, stats.
2. `hero_selected` WS message shape: `{type: "hero_selected", player_id, username, hero_id, hero_name, class_id, stats: {hp, max_hp, attack_damage, ranged_damage, armor, vision_range, ranged_range}, players: {...}}`
3. `hero_deaths` in `turn_result` payload contains `[{hero_id, hero_name, class_id, player_id, username, lost_items: [...]}]` — use this for the permadeath notification UI.
4. `match_end` payload now includes `hero_outcomes: {player_id: {player_id, username, hero_id?, status: "survived"|"died", enemy_kills?, boss_kills?, gold_earned?}}`.
5. Dungeon match start is blocked if any human player hasn't selected a hero — the error message is broadcast to all players.
6. Arena mode is completely unaffected — no hero_id, no hero selection needed, no permadeath.
7. The class is auto-set when a hero is selected (hero's class_id → class_select), so the lobby class display works correctly.
8. Gold rewards are configurable in `combat_config.json` — currently 10g/enemy, 50g/boss, 25g clear bonus per surviving hero.

---

### Phase 4E-3 — Town Hub Client UI

**Goal:** Full client-side town experience — hire heroes, view roster, select hero for dungeon, see permadeath results. All consuming the stable 4E-1 REST API and 4E-2 WS integration.

**Duration:** 1-1.5 days

**Depends on:** 4E-2 (needs stable server API for all hero management and match integration)

> **Why this is a separate sub-phase:** With the server API locked in from 4E-1/4E-2, the client work is purely consuming known REST endpoints and WS message shapes. This is the least risky part and can be validated visually end-to-end.

#### Deliverables

1. **Town Hub screen** (`client/src/components/TownHub/TownHub.jsx` — **NEW**)
   - New `'town'` screen state in `App.jsx`
   - Navigation: Lobby → Town Hub → create/join dungeon (or Arena)
   - Sections: Hiring Hall tab, Hero Roster tab, (Merchant placeholder for 4F)
   - Gold display prominently shown
   - "Enter Arena" button bypasses hero selection (existing arena flow preserved)

2. **Hiring Hall component** (`client/src/components/TownHub/HiringHall.jsx` — **NEW**)
   - Fetches `GET /api/town/tavern` to display available heroes
   - Hero card: name, class icon/color, stat preview (HP, damage, armor), hire cost
   - Stat variation shown as comparison to base class values (e.g., "+5 HP", "-2 armor")
   - Hire button (sends `POST /api/town/hire`, updates gold and roster)
   - Refresh tavern button (sends `POST /api/town/tavern/refresh`)
   - Disabled hire button if insufficient gold

3. **Hero Roster component** (`client/src/components/TownHub/HeroRoster.jsx` — **NEW**)
   - Fetches `GET /api/town/roster` to display owned heroes
   - Hero card: name, class, stats, equipped gear, inventory count
   - "Select for Dungeon" button → sets `selectedHeroId`
   - Dead heroes shown grayed out with "Fallen" label (or hidden, configurable)
   - Selected hero highlighted with border

4. **GameState context updates** (`GameStateContext.jsx`)
   - New state fields: `heroes` (roster list), `selectedHeroId`, `gold`, `tavernHeroes`
   - New reducer actions: `SET_PROFILE` (gold + heroes from REST), `SET_TAVERN` (available heroes), `HIRE_HERO` (add to roster, deduct gold), `SELECT_HERO` (set selectedHeroId), `HERO_DIED` (remove from roster on permadeath notification)
   - `inventory`/`equipment` state initialized from selected hero on `MATCH_START`

5. **Screen flow integration** (`App.jsx`)
   - Login → Lobby → Town Hub → select hero → create/join dungeon → play → post-match → Town Hub
   - Fetch profile on entering Town Hub (`GET /api/town/profile`)
   - Pass `hero_id` when creating/joining dungeon match
   - Post-match screen: summary of hero outcome (survived/died, loot kept, gold earned)
   - Permadeath notification: prominent death screen showing lost hero name + gear list
   - "Back to Town" button returns to Town Hub with updated roster

6. **WS message routing** (`App.jsx`)
   - Route `hero_selected` WS messages to dispatcher (lobby hero info)
   - Route `hero_deaths` in `turn_result` / `match_end` to `HERO_DIED` reducer

7. **CSS** (`main.css`)
   - Town Hub layout, tab navigation, hero cards, hiring hall grid
   - Gold display styling, hire/select button states
   - Rarity colors applied to hero equipment preview
   - Permadeath death screen (dark overlay, prominent message)
   - Fallen hero styling (grayscale, strikethrough)

#### Files Affected

| File | Changes |
|------|---------|
| `client/src/components/TownHub/TownHub.jsx` | **NEW** — town hub screen with tab navigation |
| `client/src/components/TownHub/HiringHall.jsx` | **NEW** — hero hiring UI |
| `client/src/components/TownHub/HeroRoster.jsx` | **NEW** — owned heroes view + dungeon selection |
| `client/src/App.jsx` | New `'town'` screen state, profile fetch, hero_id in match join, WS routing |
| `client/src/context/GameStateContext.jsx` | Profile/hero/gold state + reducers |
| `client/src/styles/main.css` | Town Hub, hero cards, death screen CSS |

#### Testing Criteria
- [x] Town Hub screen displays with Hiring Hall and Hero Roster tabs
- [x] Hiring Hall shows available heroes with correct stats and costs
- [x] Hire button deducts gold and adds hero to roster
- [x] Insufficient gold disables hire button
- [x] Hero Roster shows all owned heroes with stats and gear
- [x] "Select for Dungeon" sets hero and enables dungeon join
- [x] Cannot start dungeon without selecting a hero
- [x] Arena mode accessible without hero selection
- [x] Post-match returns to Town Hub with updated roster/gold
- [x] Permadeath notification shows hero name and lost gear
- [x] Dead heroes shown as fallen in roster
- [ ] Full end-to-end: hire hero → select → enter dungeon → fight → survive/die → back to town
- [x] Existing arena mode UI completely unaffected

#### Validation Checkpoint

> **Before starting 4F:** Full visual loop working. Login → Town Hub → hire hero → select hero → join dungeon → fight → escape or die → Town Hub with updated roster + gold. Permadeath removes dead heroes. All tests pass.

#### Implementation Notes (Completed Feb 13, 2026)

**Key decisions made during implementation:**
- **Screen flow:** `lobby` → `town` → `waiting` → `arena` → `postmatch` → `town`. The "Town Hub" button on the Lobby screen is the primary entry point. Arena mode is accessible via "Enter Arena" from Town Hub (bypasses hero selection entirely).
- **Post-match screen** replaces direct transition back to lobby — `match_end` WS message now transitions to a `postmatch` screen that shows hero outcomes, gold earned, kill counts, and permadeath notifications before allowing navigation back to Town Hub.
- **Profile/hero state preserved across match transitions** — `LEAVE_MATCH` reducer now preserves `gold`, `heroes`, and `availableClasses` (previously reset everything to `initialState`).
- **Hero selection auto-sends on WS connect** — when creating a dungeon from Town Hub, `selectedHeroId` is stored in context. On entering WaitingRoom, a `useEffect` auto-sends the `hero_select` WS message once the WebSocket connection is established.
- **Dungeon match creation from Town Hub** — "Enter Dungeon" creates the match via `POST /api/lobby/create` with `dungeon_test` map and `dungeon` match type, then navigates to WaitingRoom.
- **Stat variation display** — Hiring Hall hero cards show stat differences from class base values with green (+) and red (-) indicators. This helps players evaluate hero quality.
- **Tavern refresh is explicit** — the "New Heroes" button triggers `POST /api/town/tavern/refresh`. Pool persists until manually refreshed.
- **Fallen heroes section** — dead heroes are shown grayed out with strikethrough text and grayscale icons in a collapsible section below the active roster.
- **Merchant tab placeholder** — a "(Soon)" labeled disabled tab is ready for Phase 4F.
- **No server files modified** — 4E-3 is a pure client sub-phase. All 559 server tests continue to pass (556 from 4E-2 + 3 net from pre-4F bug fixes).

**New files created:**
- `client/src/components/TownHub/TownHub.jsx` — Town Hub screen with tab navigation, gold display, dungeon/arena entry buttons
- `client/src/components/TownHub/HiringHall.jsx` — Tavern hero hiring UI with stat comparison, hire/refresh functionality
- `client/src/components/TownHub/HeroRoster.jsx` — Owned heroes view with dungeon selection, equipment preview, fallen heroes section

**Files modified:**
- `client/src/App.jsx` — Added `'town'` and `'postmatch'` screen states; `TownHub` import and routing; `PostMatchScreen` inline component; `hero_selected` and `hero_deaths` WS message routing; `handleEnterDungeon()` creates dungeon match from town; `handleBackToTown()` for post-match flow; `LEAVE_MATCH` now goes to town when username exists
- `client/src/context/GameStateContext.jsx` — Added `gold`, `heroes`, `tavernHeroes`, `selectedHeroId`, `heroDeaths`, `heroOutcomes`, `postMatchSummary` to initial state; Added `SET_PROFILE`, `SET_TAVERN`, `HIRE_HERO`, `SELECT_HERO`, `HERO_SELECTED`, `HERO_DIED`, `SET_POST_MATCH_SUMMARY`, `CLEAR_POST_MATCH` reducers; `MATCH_END` stores `hero_outcomes`; `LEAVE_MATCH` preserves town/hero state
- `client/src/components/Lobby/Lobby.jsx` — Added `onEnterTown` prop; "🏰 Town Hub" button in lobby actions
- `client/src/components/WaitingRoom/WaitingRoom.jsx` — Auto-sends `hero_select` WS message when entering with pre-selected hero
- `client/src/styles/main.css` — Town Hub layout, tab navigation, hero cards, hiring hall grid, roster grid, gold display, stat diff colors, fallen hero styling, post-match screen, permadeath notification, action button variants

**What the next developer needs to know for 4F:**
1. The full hero persistence loop is complete — hire, equip, fight, persist, permadeath all work.
2. Town Hub has a Merchant placeholder tab ready for 4F to populate.
3. `selectedHeroId` is passed to `create_match`/`join_match` — 4F's party formation extends this.
4. Post-match flow returns to Town Hub — 4F adds the portal scroll escape mechanic that triggers this flow mid-match.
5. Gold is persisted on profile — 4F adds merchant buy/sell to complete the economy loop.
6. The `hero_deaths` payload includes `lost_items` — 4F can use this for the death summary screen.
7. Arena mode is completely unaffected — no hero required, no town required.
8. Screen flow: `lobby` → `town` → `waiting` → `arena` → `postmatch` → `town`. The postmatch screen shows hero outcomes with gold earned and kill counts.
9. The `PostMatchScreen` component is inline in `App.jsx` — 4F may want to extract it to its own file if it grows.
10. `LEAVE_MATCH` reducer now preserves `gold`, `heroes`, and `availableClasses` state across transitions.
11. All 559 server tests pass (556 from 4E-2 + 3 net from pre-4F bug fixes). No server files were modified in 4E-3. Client builds cleanly (0 errors).

---

## Phase 4F — Dungeon Run Loop & Escape

**Goal:** Complete gameplay loop — town → hire → party → dungeon → loot → escape/die → town.

**Duration:** 3-4 days

### Deliverables

1. **Portal scroll mechanic**
   - USE_ITEM on portal scroll = party-wide escape
   - All living party members extracted with their loot
   - Dead members remain dead (permadeath already applied)
   - Match ends, all players returned to town
   - Loot transferred to hero inventory / bank

2. **Dungeon victory conditions**
   - Option A: All enemies dead = dungeon cleared (auto-extract or continue looting)
   - Option B: Boss killed = portal appears (interact to leave)
   - Portal scroll: escape anytime (even mid-fight)
   - Party wipe: all heroes dead = match ends, all loot lost

3. **Post-dungeon flow**
   - Return to town hub
   - Loot from dungeon run persisted to hero inventory / bank
   - Dead heroes removed from roster
   - Gold from run available

4. **Merchant system**
   - REST endpoints: `GET /merchant/stock`, `POST /merchant/sell`, `POST /merchant/buy`
   - Sell items for gold (common = 10-25g, uncommon = 25-75g)
   - Buy portal scrolls (50-100g each)
   - Buy basic starter gear (common quality)
   - Client: `Merchant` component in town hub

5. **Party formation**
   - Lobby for dungeon mode: select hero from roster
   - Party leader starts dungeon run
   - Flexible 1-5 party members
   - Each player brings one hero

6. **Screen flow update**
   ```
   Login → Lobby → Town Hub → [Arena (existing) OR Dungeon Lobby]
                    ↕              ↓
               Hire/Shop      Dungeon Run
                    ↕              ↓
               Hero Roster    Escape/Die → Town Hub
   ```

### Files Affected

| File | Changes |
|------|---------|
| `server/app/core/match_manager.py` | Dungeon end conditions, portal escape, post-run processing |
| `server/app/services/websocket.py` | Portal escape broadcast, dungeon-end messages |
| `server/app/services/persistence.py` | Post-run save (loot, death, gold) |
| `server/app/routes/town.py` | Merchant endpoints |
| `client/src/App.jsx` | Screen flow: town ↔ dungeon ↔ post-run |
| `client/src/components/TownHub/Merchant.jsx` | **NEW** — buy/sell UI |
| `client/src/components/Arena/Arena.jsx` | Portal escape button/action |
| `client/src/components/ActionBar/ActionBar.jsx` | Portal scroll usage |
| `client/src/context/GameStateContext.jsx` | Post-run state, merchant state |

### Testing Criteria
- [ ] Portal scroll escapes entire party
- [ ] Loot persists after successful escape
- [ ] Party wipe = all loot lost
- [ ] Merchant buy/sell works correctly
- [ ] Full loop: hire hero → enter dungeon → kill enemies → loot → escape → sell loot → repeat
- [ ] Solo run (1 player) works
- [ ] 5 player party works
- [ ] Dead heroes don't return to town

---

## Phase 4G — AI Parties & Polish

**Goal:** AI-controlled enemy parties simulate PvP encounters. Balance pass. Full gameplay loop stress testing.

**Duration:** 3-4 days

### Deliverables

1. **AI enemy parties**
   - 3-4 units using player classes (e.g., 1 Crusader, 1 Confessor, 2 Rangers)
   - Spawned in dungeon rooms or patrol corridors
   - 1-2 enemy parties per dungeon run

2. **Group AI behavior**
   - Coordinated movement (stay in formation)
   - Role-based tactics: tank in front, healer/ranged in back
   - Focus-fire on weakest player target
   - Retreat behavior when outnumbered (if losing badly)

3. **Enemy party loot**
   - Defeat enemy party → loot all their equipped gear (100% drop rate)
   - High-risk, high-reward encounter
   - Gear quality: equipped uncommon items

4. **Balance pass**
   - Class stat tuning based on playtesting
   - Enemy difficulty scaling
   - Loot drop rate adjustment
   - Gold economy balancing (hiring costs vs loot income)
   - Portal scroll pricing

5. **Polish**
   - Combat log improvements (detailed class/enemy info)
   - Death screen with lost hero/gear summary
   - Dungeon run summary (enemies killed, loot found, time spent)
   - Bug fixing from integration testing
   - Edge case handling (disconnect mid-dungeon, empty party, etc.)

6. **Integration test suite**
   - Full loop automated tests
   - Permadeath verification tests
   - Loot generation and distribution tests
   - AI party encounter tests
   - Persistence save/load tests

### Files Affected

| File | Changes |
|------|---------|
| `server/app/core/ai_behavior.py` | Group AI, role-based tactics, formation movement |
| `server/app/core/match_manager.py` | Enemy party spawning, party loot drops |
| `server/configs/enemies_config.json` | Enemy party compositions |
| `server/configs/maps/dungeon_test.json` | Enemy party spawn positions |
| `client/src/canvas/ArenaRenderer.js` | Enemy party visuals, polish |
| `client/src/components/CombatLog/CombatLog.jsx` | Enhanced messages |
| `server/tests/` | **NEW** test files for Phase 4 systems |
| Various | Bug fixes, balance tweaks |

### Testing Criteria
- [ ] AI parties spawn and behave as coordinated groups
- [ ] Tank-in-front, ranged-in-back formation works
- [ ] Defeating enemy party drops their equipped gear
- [ ] Full 5-run playtest without crashes or data loss
- [ ] Permadeath persists correctly across multiple runs
- [ ] Gold economy feels balanced (can hire new hero after 2-3 successful runs)
- [ ] All existing arena mode tests still pass

---

## Open Design Questions (To Resolve During Development)

These will be resolved as we hit each sub-phase. Decisions will be documented here.

| # | Question | Resolve By | Decision |
|---|----------|------------|----------|
| 1 | Shared party inventory or individual hero inventories? | 4D-1 | Individual hero inventories (10 slots per hero, lost on permadeath) ✅ |
| 2 | Starting gold amount? | 4E | *TBD* |
| 3 | Hiring costs per class (flat or stat-scaled)? | 4E | *TBD* |
| 4 | Loot sell values? | 4F | *TBD* |
| 5 | Portal scroll cost? | 4F | *TBD* |
| 6 | How many enemies per room? | 4C | 2 per enemy room, 1 boss per boss room ✅ |
| 7 | Static enemy spawns or respawning? | 4C | Static spawns, no respawning ✅ |
| 8 | Loot distribution: free-for-all or auto-distribute? | 4D-1 | Ground pickup + solo auto-loot (solo: items → inventory; party: items → ground) ✅ |
| 9 | Hero name generation: procedural or curated list? | 4E | *TBD* |
| 10 | Bank storage in town (yes/no, capacity)? | 4E | *TBD* |
| 11 | Confessor healing: consumable-only or class ability? | 4D-1 | Consumable-only (potions). Class ability deferred to Phase 5+ ✅ |
| 12 | Dungeon clear condition: all enemies OR boss only? | 4F | *TBD* |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Inventory system complexity bloats 4D | Timeline slip | Keep minimal: 3 equip slots, 10 bag slots, no sorting/filtering. **Mitigated further by 4D split into 4D-1/4D-2/4D-3** |
| AI party behavior too complex | 4G delays | Start with "individuals that stay near each other", upgrade to tactics if time allows |
| Persistence corruption/bugs | Data loss | Auto-backup before save, validation on load, recovery fallback |
| Balance wildly off | Unfun gameplay | Tune numbers in config files (not code), iterate quickly |
| Scope creep from "cool ideas" | Phase never ends | Strict scope: if it's not in this doc, it goes to Phase 5 |
| Backward compat breaks arena mode | Regression | Run full test suite (446+ tests) after each sub-phase |
| AI context memory exhaustion | Incomplete implementation, cascading bugs | Split large sub-phases (4B split done, **4D split done**, **4E split done**); validate at checkpoints before proceeding |

---

## Success Criteria (Phase 4 Complete)

- [ ] 5 distinct classes playable with unique stats
- [ ] Handcrafted dungeon with rooms, corridors, doors
- [ ] 3 enemy types with distinct behaviors
- [ ] Loot drops, equipment, consumables working
- [ ] Persistent heroes with permadeath
- [ ] Town hub: hire heroes, manage roster, buy/sell
- [ ] Full gameplay loop: hire → dungeon → loot → escape → sell → repeat
- [ ] AI enemy parties in dungeon
- [ ] Existing arena mode still functional
- [ ] 0 critical bugs in core loop

---

**Document Version:** 1.7  
**Created:** February 13, 2026  
**Last Updated:** February 13, 2026 — 4E-3 complete; ready for 4F  
**Parent Doc:** [Phase 4: Grimdark Dungeon Crawler](phase4-grimdark-dungeon.md)  
**Status:** 4A Complete, 4B-1 Complete, 4B-2 Complete, 4C Complete, 4D-1 Complete, 4D-2 Complete, 4D-3 Complete, 4E-1 Complete, 4E-2 Complete, 4E-3 Complete — Ready for 4F
