# Phase 7 — Party Movement & AI Overhaul

## Overview

This phase addresses the core gameplay issues preventing fluid dungeon exploration with a party. The current systems allow only one-unit-at-a-time control, have no cooperative pathfinding, lack AI behavior stances, and treat closed doors as impassable walls during path planning. Moving a party through a dungeon — especially down hallways — is the single biggest friction point in the game right now.

**Goal:** Make dungeon exploration with a party feel natural and responsive. A player should be able to move their entire party through a dungeon with minimal micromanagement while retaining fine-grained tactical control when needed.

---

## Current Problems (Diagnosed)

### Problem 1: Single-Unit Selection Only
- **Root cause:** `set_party_control()` in `match_manager.py` enforces one controlled unit per player. Selecting a new unit automatically releases the previous one.
- **Client:** `Arena.jsx` click handler toggles a single `activeUnitId`. No shift-click, no group selection.
- **Impact:** Moving 4 party members requires 4 separate select → right-click → select → right-click cycles. Extremely tedious.

### Problem 2: Units Block Each Other (Hallway Gridlock)
- **Root cause:** Both server and client A* treat ALL other alive units as impassable (`occupied` set). When multiple allies path toward the same area, they compute paths against current positions — not future positions. The first unit processed claims a tile, blocking later units.
- **Server `turn_resolver.py`:** Movement is resolved sequentially in `move_actions` list order. First mover wins contested tiles. Later movers get "failed to move" and stop dead.
- **Client `pathfinding.js`:** `generateSmartActions()` builds the occupied set from current positions. If two allies are told to move down a 1-wide hallway, only the first one gets a valid path — the second sees the first as blocking.
- **Impact:** Allies frequently stop mid-path, jam up in hallways, and require individual re-pathing. In a 1-tile-wide corridor, it's nearly impossible to move a party.

### Problem 3: No AI Behavior Stances
- **Root cause:** Hero ally AI has only two modes: "aggressive chase" when enemies are visible, or "WAIT" when idle. There is no follow, defensive, or guard mode.
- **`ai_behavior.py`:** Hero allies skip patrol (return WAIT) but otherwise use the same aggressive/ranged logic as dungeon enemies. There is no concept of "follow the player" or "stay close."
- **Impact:** After combat, allies stand wherever they finished fighting. The player must manually select each one and move them. Allies don't regroup, don't follow, and don't stay in formation.

### Problem 4: Pathfinding Ignores Doors Between Rooms
- **Root cause:** Closed doors are in the `obstacles` set. A* cannot path through obstacles — it routes around them. Since dungeon rooms are connected by doors, cross-room pathfinding often produces bizarre routes that go through long hallways or fails entirely.
- **Client `pathfinding.js`:** `aStar()` treats `obstacleSet` (which includes closed doors) as impassable. It can path adjacent to a closed door, but cannot plan a path *through* a door.
- **Server `ai_behavior.py`:** Same issue. AI cannot pathfind through closed doors at all. AI has no door-opening behavior.
- **Impact:** Right-clicking from one room to another either fails or generates crazy long paths. Players must manually walk to each door, interact, then path into the next room.

### Problem 5: Door Interaction Requires Cardinal Adjacency
- **Root cause:** `turn_resolver.py` door interaction check enforces `dx + dy == 1` (Manhattan distance = 1), which means only the 4 cardinal tiles (N/S/E/W) can interact with a door. Diagonal tiles are rejected.
- **Impact:** Players standing diagonally adjacent must reposition before interacting. Since movement uses 8-directional, players frequently end up diagonal to doors and can't interact.

---

## Phased Implementation Plan

### Phase 7A — Cooperative Pathfinding & Movement Resolution
**Priority: CRITICAL — Fixes the biggest gameplay blocker**

The core pathfinding and movement resolution must be rewritten to handle groups of units moving together without blocking each other.

#### 7A-1: Server-Side Cooperative Movement Resolution
**Files:** `server/app/core/turn_resolver.py`, `server/app/core/combat.py`

**Current behavior:** Movement resolves sequentially. First mover wins. Later movers fail.

**New behavior — Simultaneous Swap-Aware Resolution:**
1. Collect all MOVE actions for this tick
2. Build a move-intent map: `{unit_id: target_tile}`
3. Detect conflicts:
   - **Same target:** Two+ units want the same tile → both continue to valid tiles or priority resolution (player > AI, then by ID)
   - **Swap conflicts:** Unit A wants B's tile and B wants A's tile → allow swap (both moves succeed)
   - **Chain moves:** A→B's tile, B→C's tile, C→empty → resolve as chain (all succeed)
   - **Ally pass-through:** If unit A and unit B are on the same team and A's path goes through B's current tile but B is also moving away, allow it (B will vacate)
4. Resolve all non-conflicting moves simultaneously
5. Failed moves: unit stays in place (no cascading failures)

**Key changes:**
- Replace sequential move loop with batch conflict resolver
- Add `resolve_movement_batch(move_actions, players, obstacles)` function
- Keep `is_valid_move()` for single-step validation but add team-aware logic
- Same-team units that are both moving should not block each other

#### 7A-2: Client-Side Multi-Unit Pathfinding
**Files:** `client/src/canvas/pathfinding.js`

**Current behavior:** A* builds occupied set from all alive units. Allies block pathfinding.

**New behavior — Ally-Aware Pathfinding:**
- `generateSmartActions()` accepts a `friendlyUnits` set (same-team unit positions)
- Friendly units are **excluded** from the occupied set when pathfinding
- Path preview shows the intended path without being blocked by allies who may also be moving
- When multiple units are selected and given move orders, compute paths with mutual exclusion (each unit's target is not blocked by other selected units' current positions)

#### 7A-3: Movement Prediction for Queued Paths
**Files:** `client/src/canvas/pathfinding.js`, `server/app/core/ai_behavior.py`

- When computing paths for multiple units, simulate their movement step-by-step to avoid future-tick collisions
- If unit A is on tile (3,5) moving to (3,6) and unit B needs to cross (3,5), B's path should account for A vacating (3,5) next tick
- Keep it simple: allies with queued movement are treated as "will vacate" their current tile

**Tests to add:**
- `test_cooperative_movement.py`: Two allies moving through same hallway don't block
- `test_swap_movement.py`: Two allies swapping positions succeeds
- `test_chain_movement.py`: Chain of 3+ allies shifting in a line all succeed
- `test_contested_tile.py`: Two units targeting same empty tile — one wins, other waits
- `test_movement_regression.py`: Existing single-unit movement unchanged

**Estimated scope:** ~200 lines server, ~100 lines client, ~150 lines tests

---

### Phase 7B — Multi-Unit Selection & Group Commands
**Priority: HIGH — Quality of life for party control**

#### 7B-1: Server-Side Multi-Control
**Files:** `server/app/core/match_manager.py`, `server/app/services/websocket.py`, `server/app/models/player.py`

**Current behavior:** `set_party_control()` releases previous unit. One controlled per player.

**New behavior:**
- Remove the "release previous" logic from `set_party_control()`
- Track `controlled_by` on multiple units simultaneously
- New WS messages:
  - `select_all_party` → sets `controlled_by` on all alive party members
  - `release_all_party` → clears `controlled_by` on all units
  - `group_action` → queues the same action (with offset positions) for multiple units
  - `group_batch_actions` → queues smart right-click paths for multiple selected units
- `get_controlled_unit_ids()` returns all controlled IDs (already works with multiple)

#### 7B-2: Client-Side Multi-Selection UI
**Files:** `client/src/components/Arena/Arena.jsx`, `client/src/context/GameStateContext.jsx`, `client/src/components/PartyPanel/PartyPanel.jsx`

**New interactions:**
- **Shift-click** on ally: toggle-add/remove from selection (multi-select)
- **Ctrl+A** or "Select All" button: select all alive party members + self
- **Click empty space:** deselect all (existing behavior preserved)
- **Click single ally (no shift):** select only that ally (existing behavior)
- State: `activeUnitIds: Set<string>` replaces `activeUnitId: string|null`

#### 7B-3: Group Right-Click Movement
**Files:** `client/src/canvas/pathfinding.js`, `client/src/components/Arena/Arena.jsx`

**New behavior for multi-unit right-click:**
- When multiple units are selected and player right-clicks a tile:
  1. Compute path for the "leader" (the player character, or nearest selected unit) to the target
  2. Assign nearby destination tiles to other selected units (spread around the target in a compact cluster)
  3. Compute individual paths for each unit to their assigned destination
  4. Send `group_batch_actions` with all unit paths
- **Destination spreading:** Use BFS from target tile to find N walkable tiles near the target (same logic as spawn.py formations). Assign units to nearest available destination.
- If target is in a hallway (1-tile wide), queue units in a line behind the leader rather than bunching up

**PartyPanel updates:**
- Show selection state for all units (highlight multiple)
- "Select All" / "Deselect All" buttons
- Queue count per unit
- Group action indicator when multiple selected

**Tests to add:**
- `test_multi_select.py`: Select/deselect multiple units, validate controlled_by state
- `test_group_movement.py`: Group right-click generates correct per-unit paths
- `test_group_action_validation.py`: Server validates all units in group command

**Estimated scope:** ~150 lines server, ~250 lines client, ~100 lines tests

---

### Phase 7C — AI Behavior Stances
**Priority: HIGH — Makes party feel alive between combat**

#### 7C-1: Stance Model & Server Logic
**Files:** `server/app/models/player.py`, `server/app/core/ai_behavior.py`, `server/app/core/match_manager.py`

**New field:** `ai_stance: str = "follow"` on `PlayerState` (for hero allies only)

**Stances:**

| Stance | Behavior When Idle | Behavior In Combat | Notes |
|--------|-------------------|-------------------|-------|
| **Follow** (default) | Path toward owner, stay within 2 tiles | Fight normally (aggressive/ranged) but always return to owner afterward | Best default — party moves together |
| **Aggressive** | Roam within 5 tiles of owner seeking enemies | Pursue and fight enemies aggressively, may chase far from owner | For clearing rooms |
| **Defensive** | Stay within 2 tiles of owner | Only attack enemies within 2 tiles, prioritize self-preservation | For keeping squishies safe |
| **Hold Position** | Stand still (WAIT) | Attack enemies within range but never move from current tile | For blocking chokepoints / holding ground |

**Follow stance implementation (the big one):**
```
if stance == "follow":
    owner = get_owner(unit)  # player who owns this hero ally
    distance_to_owner = chebyshev(unit.position, owner.position)
    if distance_to_owner > 2 and no_enemies_visible:
        # Path toward owner
        path = a_star(unit.pos, owner.pos, ...)
        return MOVE to first step
    elif distance_to_owner > 4:
        # Even in combat, break off and regroup
        return MOVE toward owner
    else:
        # Close enough — fight or wait
        return normal_combat_or_wait()
```

**Key design decisions:**
- Follow is the **default** stance — newly hired heroes start in follow mode
- Stance is per-hero, persists across turns
- During follow, allies maintain a "formation offset" relative to the player so they don't all pile on the same tile
- Follow ignores enemies unless they attack first (approach within 2 tiles) OR owner is in combat

#### 7C-2: Stance WS Protocol & State
**Files:** `server/app/services/websocket.py`, `server/app/models/player.py`

**New WS messages:**
- `set_stance` → `{unit_id, stance}` — sets stance for one unit
- `set_all_stances` → `{stance}` — sets stance for all party members
- Stance included in `party_members` snapshot and `match_start` payload

#### 7C-3: Stance UI ✅ COMPLETED
**Files:** `client/src/components/PartyPanel/PartyPanel.jsx`, `client/src/context/GameStateContext.jsx`, `client/src/canvas/ArenaRenderer.js`, `client/src/components/Arena/Arena.jsx`, `client/src/styles/main.css`

**Implementation completed 2026-02-15:**

**PartyPanel changes:**
- Each party member row has 4 stance toggle buttons (⇢ Follow, ⚔ Aggressive, 🛡 Defensive, ⚓ Hold)
- Active stance shown with colored highlight + matching border/background
- Group stance buttons row: one-click to set all party members to a stance
- Per-member stances update via `set_stance` WS message; group via `set_all_stances`
- Party member cards refactored from single `<button>` to `<div>` with inner clickable area + stance row

**Keyboard shortcuts (Arena.jsx):**
- F1-F4: Select individual party member by index
- Ctrl+1-4: Quick-set stance (1=Follow, 2=Aggressive, 3=Defensive, 4=Hold) for selected unit(s)
- Ctrl+A: Select all (existing, enhanced with stance support)

**Visual indicators on canvas (ArenaRenderer.js):**
- Follow: faint dashed tether line from ally to owner + ⇢ icon below unit
- Aggressive: pulsing red ring + ⚔ icon below unit
- Defensive: static blue ring + 🛡 icon below unit
- Hold Position: dashed grey ring + ⚓ icon below unit
- `renderFrame()` now accepts `partyMembers` parameter for stance rendering
- `drawStanceIndicators()` function renders all stance visuals, respects FOV visibility

**CSS (main.css):**
- `.party-stance-group` — group stance buttons row
- `.btn-stance-group` — individual group stance button
- `.party-member-clickable` — inner clickable area within member card
- `.party-member-stances` — per-unit stance toggle row
- `.btn-stance` / `.btn-stance-active` — individual stance toggle buttons

**All 1009 existing tests pass — no regressions.**

**Tests to add:**
- `test_stances.py`: Each stance produces correct AI behavior
- `test_follow_stance.py`: Ally follows owner, maintains distance, regroups after combat
- `test_defensive_stance.py`: Ally only attacks nearby, doesn't chase
- `test_hold_stance.py`: Ally never moves, attacks in range only
- `test_stance_persistence.py`: Stance persists across turns, survives match state changes

**Estimated scope:** ~200 lines server, ~150 lines client, ~200 lines tests

---

### Phase 7D — Door-Aware Pathfinding
**Priority: HIGH — Cross-room navigation is broken without it**

#### Deep Diagnostic (2026-02-15)

A thorough code audit was performed on all systems involved in 7D. The following findings should guide implementation and prevent the confusion that occurred in prior attempts.

##### Finding 1: Both A* Implementations Are Uniform-Cost — Must Be Upgraded to Weighted

**Server `a_star()` (`ai_behavior.py` line 160):** Uses `tentative_g = g_score[current] + 1` — every step costs exactly 1. There is no support for variable tile cost.

**Client `aStar()` (`pathfinding.js` line 111):** Uses `stepCost = isDiagonal ? 1.001 : 1` — nearly uniform cost (the 0.001 is only to prefer cardinal paths aesthetically).

**Impact:** The 7D plan calls for closed doors to have elevated traversal cost (e.g., 3 instead of 1). Both A* functions must be modified to accept a `doorSet` parameter and apply elevated cost when a neighbor tile is in that set. This is NOT a simple "remove doors from obstacles" change — the cost function itself needs modification.

**Recommended approach:**
- Add optional `door_tiles: set` parameter to both A* functions
- When computing `tentative_g`, check if the neighbor is in `door_tiles` → add door crossing cost (e.g., +3 instead of +1)
- Keep the door tiles OUT of the blocked/obstacle set so A* CAN path through them
- Return the same path format (list of tiles) — the cost is internal to A*

##### Finding 2: `generateSmartActions` Has Conflicting Intent Detection

**`pathfinding.js` lines 263-274:** When the user clicks directly on a closed door tile, intent detection matches case 2 ("closed door → interact intent") and correctly paths *adjacent to* the door + inserts INTERACT.

But for 7D (path *through* a door to a room beyond), the user clicks a **floor tile beyond the door**. Intent detection hits case 5 ("empty walkable tile → move"). Today this fails because the door is in the obstacle set and A* can't path through.

**The fix must handle both scenarios:**
1. Click on a door tile: path adjacent + INTERACT (existing behavior, preserved)
2. Click on a tile beyond a door: A* paths *through* the door tile, then post-processing detects door crossings and inserts INTERACT actions before each crossing

**Post-processing logic for case 2:**
```
for each step in path:
    if step is a closed door tile (in doorStates):
        insert INTERACT action targeting (step.x, step.y) before the MOVE onto that tile
        insert MOVE action to step onto the door tile after it opens
```

This changes the action sequence from `[MOVE, MOVE, MOVE]` to `[MOVE, MOVE, INTERACT(door), MOVE(through door), MOVE, MOVE]`.

**Critical detail:** After inserting INTERACT + the extra step, the total action count increases. The `maxActions` parameter (default 10) must account for these insertions, or paths through multiple doors may silently truncate.

##### Finding 3: `_is_cardinal_adjacent` Is Shared Between Doors AND Chests

**`turn_resolver.py` line 51:** `_is_cardinal_adjacent()` is used at:
- Line 339: Door INTERACT validation
- Line 410: Chest LOOT validation

**Decision required for 7D-2:** If we change this function to Chebyshev adjacency (`max(abs(dx), abs(dy)) == 1`), chests will ALSO become diagonally interactable. Options:
- **Option A (recommended):** Create a new `_is_chebyshev_adjacent()` function, use it for doors only. Keep cardinal for chests. Rename current function to `_is_cardinal_adjacent()` (already named that).
- **Option B:** Change the shared function. Both doors and chests become 8-directional. Simpler but changes chest behavior.

##### Finding 4: AI Has No INTERACT Action Generation Capability

**`ai_behavior.py`:** All AI decision functions (`_decide_follow_action`, `_decide_aggressive_stance_action`, etc.) only return MOVE, ATTACK, RANGED_ATTACK, WAIT, or SKILL actions. The AI **never generates ActionType.INTERACT**. This is a new capability that must be added.

**Multi-tick planning challenge:** The AI framework returns exactly **one** `PlayerAction` per tick. For door opening, the AI needs:
- Tick N: Return INTERACT (to open the door)
- Tick N+1: Return MOVE (to walk through the now-open door)

The AI must "remember" it was trying to path through a door. Currently there is no path-memory mechanism for this. The AI has `_enemy_memory` and `_patrol_targets` dicts, but nothing for "I'm in the middle of opening a door."

**Recommended approach — simple, no new state needed:**
1. Each tick, AI computes its path using door-aware A*
2. Before returning a MOVE, check: "Is the next tile a closed door?"
3. If yes and AI is adjacent (Chebyshev) to the door → return INTERACT instead of MOVE
4. Next tick, the door is open, the obstacle set is updated, normal A* resumes the path
5. **No path memory needed** — the path just recomputes each tick. The door is now open, so the path goes through it naturally.

This is elegant because the turn resolver processes INTERACT (phase 1.5) before MOVE (phase 2), and `obstacles.discard()` is called in-place. So a *different* unit could even move through that door in the same tick. The AI ally just needs to wait one tick.

**Critical constraint:** Only hero allies (`hero_id is not None`) should open doors. Enemy AI (`unit_type == "ai"`, `hero_id is None`) must NOT open doors — this preserves room isolation for dungeon design.

##### Finding 5: Turn Resolver Phase Ordering Is Favorable

**`turn_resolver.py`:** INTERACT resolves in phase 1.5, MOVE in phase 2. When a door is opened in phase 1.5, `obstacles.discard((x, y))` mutates the obstacle set immediately. This means:
- **Same tick:** Other units that submitted MOVE actions through that tile WILL succeed (the obstacle is gone before movement resolves)
- **The human player can interact + another ally can walk through in the same tick** — no wasted turn
- **The AI ally cannot interact + move in the same tick** (one action per tick) — expected behavior, not a bug

This is actually a nice property. If the player manually opens a door, their follow-stance allies can immediately path through it next tick.

##### Finding 6: Obstacle Set Sync Is Already Correct

**Client:** `obstacleSet` in `Arena.jsx` is a `useMemo` that depends on `[obstacles, isDungeon, doorStates]`. When `doorStates` changes (via TURN_RESULT reducer in `GameStateContext.jsx`), `obstacleSet` recalculates. Open doors are removed from obstacles on the client automatically. **No sync issues here.**

**Server:** `get_obstacles_with_door_states()` is called fresh every tick in `match_tick()`. Open doors are always excluded. **No sync issues here either.**

##### Finding 7: Dungeon Layout Creates Multi-Door Corridors

**`dungeon_test.json`:** The map has corridors like start_room → enemy_room_1 that pass through TWO doors: `(6,3)` and `(9,3)` with corridor tiles `(7,3), (8,3)` between them. A party moving from one room to another must:
1. Path to door 1 → interact → walk through
2. Walk corridor
3. Path to door 2 → interact → walk through

For a single player right-clicking across rooms, `generateSmartActions` must produce: `[MOVE, MOVE, INTERACT(door1), MOVE(through door1), MOVE(corridor), MOVE(corridor), INTERACT(door2), MOVE(through door2), MOVE, MOVE]` — potentially 10+ actions for a cross-dungeon path.

For AI allies in follow stance, they will handle this naturally tick-by-tick (interact, move, move, interact, move) — no issue, just slower.

**The `maxActions = 10` queue limit may need to be increased** for dungeon maps, or the path may truncate mid-corridor, leaving the player stranded between doors.

##### Finding 8: `computeGroupRightClick` and `generateGroupPaths` Need Door Awareness Too

**`pathfinding.js` lines 358-395:** `generateGroupPaths` calls `generateSmartActions` for each unit sequentially with `pendingMoves` prediction. The `spreadDestinations` BFS also uses `obstacleSet` to find walkable tiles near the target.

If the target tile is in a room beyond a closed door:
- `spreadDestinations` won't search past the door (it respects `obstacleSet`)
- Follower units won't get valid destinations in the target room
- Group movement to another room will partially fail

**Fix:** Pass `doorSet` to `spreadDestinations` so doors don't block BFS expansion. Or: run `spreadDestinations` with doors removed from obstacles.

---

#### 7D-1: Multi-Layer Pathfinding (Path Through Closed Doors)
**Files:** `client/src/canvas/pathfinding.js`, `server/app/core/ai_behavior.py`

**Current behavior:** Closed doors are obstacles. A* cannot path through them.

**New behavior — Door-Aware A* with interaction cost:**

**Step 1: Upgrade A* to support weighted door tiles (BOTH server and client)**
- Add optional `door_tiles` parameter to `aStar()` (client) and `a_star()` (server)
- Remove door positions from the obstacle/blocked set
- When computing `tentative_g` for a neighbor that is in `door_tiles`, add elevated cost (e.g., +3) instead of +1
- This makes A* prefer routes that avoid doors when a floor-only path exists, but will route through doors when necessary
- The A* output (path as list of tiles) is unchanged — the cost is internal

**Step 2: Client `generateSmartActions()` post-processing**
- After A* returns a path, scan for tiles that are in `doorStates` as `"closed"`
- For each door tile in the path, insert an INTERACT action before the MOVE onto that tile
- Adjust `maxActions` accounting for inserted INTERACT actions or increase queue limit for dungeons
- Preserve existing "click on door directly" behavior (case 2 in intent detection) — no regression

**Step 3: Client `obstacleSet` construction change (`Arena.jsx`)**
- Stop adding closed doors to `obstacleSet` for A* purposes
- Instead, build a separate `doorSet` from closed doors in `doorStates`
- Pass `doorSet` to A* functions
- Closed doors are still visually rendered as obstacles / interactable objects — no rendering change

**Step 4: Server obstacle handling change (`match_tick` in `websocket.py`)**
- Build a `door_tiles` set from `door_states` (closed doors only)
- Pass `door_tiles` alongside `obstacles` to `run_ai_decisions()`
- `obstacles` no longer includes closed doors when used for AI A* pathfinding
- Movement validation in `turn_resolver.py` still needs closed doors in obstacles (to block walking onto a closed door without interacting) — so `resolve_turn` keeps using the current `obstacles` set that includes closed doors

**Critical subtlety:** A* can path *through* a door tile, but the unit should NOT step onto a closed door tile via a MOVE action — it must INTERACT first. The A* treats it as traversable (with cost), but `generateSmartActions` inserts INTERACT before the step. On the server side, the movement validator (`is_valid_move`) should still reject MOVE onto a closed door. The INTERACT+MOVE pair handles it correctly across two ticks (or in the same tick for the player's queued actions since INTERACT resolves before MOVE).

#### 7D-2: Diagonal Door Interaction
**Files:** `server/app/core/turn_resolver.py`

**Current behavior:** `_is_cardinal_adjacent()` at line 51 — `(dx + dy) == 1`, cardinal only.

**New behavior:** Add `_is_chebyshev_adjacent()` function: `max(abs(dx), abs(dy)) == 1` — 8-directional adjacency.

**Implementation:**
- Add new function `_is_chebyshev_adjacent(pos, tx, ty)` alongside existing `_is_cardinal_adjacent()`
- Replace the adjacency check for door INTERACT (line 339) with `_is_chebyshev_adjacent()`
- **Keep** `_is_cardinal_adjacent()` for chest LOOT (line 410) — chests stay cardinal-only
- This is a ~5 line change with big impact on feel

**Important for AI door opening (7D-3):** Since AI uses 8-directional movement, they will frequently end up diagonal to a door. The AI's "am I adjacent to the door?" check MUST use chebyshev adjacency to match the server validation. Otherwise the AI generates an INTERACT that the server rejects.

#### 7D-3: AI Door Opening (For Follow Stance)
**Files:** `server/app/core/ai_behavior.py`

**Implementation approach (stateless — no path memory needed):**

```python
def _maybe_interact_door(ai, next_step, door_tiles, obstacles):
    """Check if the AI's planned next step is a closed door.
    
    If adjacent to a closed door that's on the path, return INTERACT
    instead of MOVE. Next tick the door will be open and A* will
    path through normally.
    """
    if door_tiles and next_step in door_tiles:
        # Check if we're adjacent (chebyshev) to the door
        ai_pos = (ai.position.x, ai.position.y)
        if _chebyshev(ai_pos, next_step) == 1:
            return PlayerAction(
                player_id=ai.player_id,
                action_type=ActionType.INTERACT,
                target_x=next_step[0],
                target_y=next_step[1],
            )
    return None  # Not a door, proceed with MOVE
```

**Integration points — add door check before every MOVE return in stance functions:**
- `_decide_follow_action()`: Before returning MOVE toward owner (2 locations)
- `_decide_aggressive_stance_action()`: Before returning MOVE toward enemy or owner (3 locations)
- `_decide_defensive_action()`: Before returning MOVE toward owner (1 location)
- `_decide_hold_action()`: Never moves, no change needed
- Enemy AI functions (`_decide_aggressive_action`, `_decide_ranged_action`, `_decide_boss_action`): **No changes** — enemies cannot open doors

**Parameters change:** All stance functions must receive `door_tiles` parameter. This propagates from:
- `run_ai_decisions()` → `decide_ai_action()` → `_decide_stance_action()` → individual stance functions
- `run_ai_decisions()` receives `door_tiles` from `match_tick()` in `websocket.py`

**Flow for a follow-stance ally crossing rooms:**
1. Tick N: A* computes path through closed door. Next step IS the door tile. AI returns INTERACT.
2. Tick N: INTERACT resolves in phase 1.5, door opens, obstacles updated.
3. Tick N+1: A* recomputes, door is now open (not in obstacles or door_tiles). AI returns MOVE onto the floor tile.
4. AI continues following owner normally.

**Tests to add:**
- `test_door_pathfinding.py`: Weighted A* returns valid path through closed door with higher cost, prefers open routes when available
- `test_door_post_processing.py`: `generateSmartActions` inserts INTERACT before door crossings in multi-door paths
- `test_diagonal_door_interact.py`: INTERACT succeeds from all 8 adjacent tiles, cardinal adjacency preserved for chests
- `test_ai_door_opening.py`: Follow-stance ally generates INTERACT when adjacent to closed door on path to owner
- `test_ai_door_resume.py`: After INTERACT, ally resumes path through now-open door next tick
- `test_enemy_no_door.py`: Enemy AI still cannot open doors — never generates INTERACT (regression test)
- `test_multi_door_path.py`: Path through 2+ doors inserts correct number of INTERACT actions
- `test_max_actions_with_doors.py`: Queue limit handles INTERACT insertions without truncating mid-corridor
- `test_group_movement_through_doors.py`: `computeGroupRightClick` with target room behind a door works correctly

**Estimated scope:** ~200 lines server, ~150 lines client, ~200 lines tests

---

### Phase 7E — Polish & Quality of Life
**Priority: MEDIUM — Refinement after core systems work**

#### 7E-1: Pathfinding Preview Improvements ✅ COMPLETED
- Show path preview for ALL selected units simultaneously (different colors per unit)
- Show door interaction points on path preview (door icon overlay)
- Show formation preview at destination (ghost outlines of where units will end up)
- Ghost paths recalculate in real-time as the cursor moves

#### 7E-2: Keyboard Shortcuts
- **Tab**: Cycle through party members (select next alive ally)
- **F1-F4**: Select specific party member by index
- **Ctrl+A**: Select all party members
- **1-4**: Quick-set stance for selected unit(s)
- **Space**: Select self (return to player character)
- **Escape**: Deselect all, cancel action mode

#### 7E-3: Smart Hallway Movement
- Detect when the target area is in a narrow corridor (1-2 tiles wide)
- Instead of clustering, queue units in single-file behind the leader
- Units automatically space 1 tile apart in corridors
- Leader unit stops if a party member falls more than 5 tiles behind (in follow mode)

#### 7E-4: Movement Feedback & Error Recovery
- When a move fails (blocked), show a brief red flash on the unit
- Auto-requeue: if a move fails because an ally is temporarily blocking, automatically retry next tick instead of discarding the action
- Show a "regrouping" indicator when allies are pathfinding back to the player
- Queue visualization: show remaining path as dotted line on canvas

#### 7E-5: Combat Integration
- "All Attack" command: all selected units target the same enemy
- "Focus Fire" indicator: show which enemy the group is targeting
- Selected allies auto-acquire targets near the player during follow mode
- After combat, follow-stance allies automatically regroup to the player (no manual re-positioning)

**Estimated scope:** ~150 lines server, ~300 lines client

---

## Implementation Order & Dependencies

```
Phase 7A (Cooperative Pathfinding)     ← START HERE — Foundation for everything
  ├── 7A-1: Server cooperative movement
  ├── 7A-2: Client ally-aware pathfinding  
  └── 7A-3: Movement prediction
          │
Phase 7B (Multi-Selection)             ← Depends on 7A (needs cooperative paths)
  ├── 7B-1: Server multi-control
  ├── 7B-2: Client multi-selection UI
  └── 7B-3: Group right-click movement
          │
Phase 7C (AI Stances)                  ← Depends on 7A (follow needs cooperative paths)
  ├── 7C-1: Stance model & AI logic
  ├── 7C-2: WS protocol & state
  └── 7C-3: Stance UI & visuals
          │
Phase 7D (Door-Aware Pathfinding)      ← Can start after 7A, benefits from 7C
  ├── 7D-1: Door-cost A* pathfinding
  ├── 7D-2: Diagonal door interaction
  └── 7D-3: AI door opening
          │
Phase 7E (Polish & QoL)               ← After 7A-7D are stable
  ├── 7E-1: Path preview improvements
  ├── 7E-2: Keyboard shortcuts
  ├── 7E-3: Smart hallway movement
  ├── 7E-4: Movement feedback
  └── 7E-5: Combat integration
```

**Note:** Phase 7D-2 (diagonal door interaction) is a tiny standalone fix that can be done at any time — it's a one-line change in `turn_resolver.py`.

---

## Files Affected (Summary)

### Server
| File | Changes |
|------|---------|
| `server/app/core/turn_resolver.py` | Batch movement resolution, diagonal door interaction |
| `server/app/core/ai_behavior.py` | Ally-aware A*, follow/defensive/hold stances, door opening AI |
| `server/app/core/combat.py` | Team-aware `is_valid_move()` helper |
| `server/app/core/match_manager.py` | Multi-unit control, stance management, group commands |
| `server/app/models/player.py` | `ai_stance` field |
| `server/app/services/websocket.py` | New WS messages (group actions, stances, multi-select) |
| `client/src/canvas/pathfinding.js` | Door-cost A*, ally-exclusion, group path generation |
| `client/src/components/Arena/Arena.jsx` | Multi-select click handling, group right-click |
| `client/src/components/PartyPanel/PartyPanel.jsx` | Multi-select UI, stance controls, group buttons |
| `client/src/context/GameStateContext.jsx` | `activeUnitIds` set, stance state, group reducers |
| `client/src/canvas/ArenaRenderer.js` | Multi-unit highlights, stance icons, path previews |
| `client/src/components/BottomBar/BottomBar.jsx` | Group action display, stance indicator |

### New Test Files
| File | Coverage |
|------|----------|
| `server/tests/test_cooperative_movement.py` | Swap, chain, hallway, contested tile movement |
| `server/tests/test_multi_select.py` | Multi-unit control, group commands |
| `server/tests/test_stances.py` | All 4 stances, follow regrouping |
| `server/tests/test_door_pathfinding.py` | Door-cost A*, AI door opening, diagonal interaction |

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Cooperative movement breaks existing single-unit movement | Medium | Full regression test suite (858 existing tests), new tests cover edge cases |
| Follow stance AI gets stuck or loops | Medium | Distance thresholds, "arrived" state, loop detection (same tile 3+ ticks → WAIT) |
| Door-aware A* performance with many doors | Low | Doors are a small set (~5-15 per map), cost increase is minimal |
| Multi-select UI feels clunky | Medium | Start with simple shift-click + "Select All", iterate based on feel |
| Group movement in narrow corridors still jams | Medium | Phase 7E-3 specifically targets this with single-file detection |

---

## Recommendation: Start With 7A

Phase 7A (Cooperative Pathfinding) is the foundation. Without it, multi-select and stances will still feel frustrating because units will block each other. The server-side batch movement resolver (7A-1) is the single most impactful change — it eliminates the "first mover wins" problem that causes hallway gridlock.

I recommend this session order:
1. **7A-1** first (server batch movement) — immediately testable, biggest impact
2. **7D-2** quick win (diagonal doors) — one-line fix, instant feel improvement
3. **7A-2** (client ally-aware pathfinding) — paths stop looking broken immediately
4. **7C** (stances, especially Follow) — party suddenly feels alive
5. **7B** (multi-select) — group control becomes possible
6. **7D-1 + 7D-3** (door pathfinding) — cross-room navigation fixed
7. **7E** (polish) — refinement

Total estimated new code: ~850 lines server, ~900 lines client, ~570 lines tests

---

## Implementation Log

### 7D-1: Multi-Layer Pathfinding (Path Through Closed Doors) — COMPLETE
**Date:** 2025-06-16
**Tests:** 27 new tests in `test_door_pathfinding.py` (1064 total, 0 failures)

**Summary:** Upgraded both server and client A* pathfinding to support weighted door tiles. Closed doors are no longer hard obstacles — A* can plan paths through them at elevated cost (+3 per door tile vs +1 normal). The system auto-inserts INTERACT actions before MOVE onto closed doors, and AI hero allies open doors autonomously via a stateless per-tick check.

**Server changes (`ai_behavior.py`):**
- `a_star()`: Added `door_tiles` parameter. Removes door tiles from blocked set, applies +3 step cost for door neighbors. g_score type changed from int to float.
- `get_next_step_toward()`: Added `door_tiles` parameter, passes through to `a_star()`.
- `_maybe_interact_door()`: NEW helper — checks if AI's next A* step is a closed door. If adjacent (Chebyshev distance 1), returns INTERACT action. Otherwise None (caller proceeds with MOVE).
- `decide_ai_action()`: Added `door_tiles` parameter. Only passes to hero ally stance functions; enemy AI does NOT receive door_tiles (enemies cannot open doors).
- `_decide_stance_action()`: Propagates `door_tiles` to follow/aggressive/defensive handlers. Hold stance unchanged (never moves).
- `_decide_follow_action()`: All 4 `get_next_step_toward` calls pass `door_tiles`; every MOVE return is wrapped with `_maybe_interact_door` check.
- `_decide_aggressive_stance_action()`: All path calls updated; door interaction checks on 4 MOVE locations (rush, move toward target, path back to owner).
- `_decide_defensive_action()`: Path call updated; door interaction check added.
- `run_ai_decisions()`: Accepts and passes `door_tiles` to `decide_ai_action()`.

**Server changes (`websocket.py`):**
- `match_tick()`: Builds `door_tiles` set from `door_states` dict (closed doors only), passes to `run_ai_decisions()`.

**Client changes (`pathfinding.js`):**
- `aStar()`: Added `doorTiles` parameter. Removes door tiles from blocked set, applies +3 door cost to step cost calculation.
- `_buildActionsWithDoorInteractions()`: NEW function — scans A* path for closed door tiles, inserts INTERACT action before MOVE onto each door, respects maxActions.
- `generateSmartActions()`: Added `doorSet` parameter. All 5 intent cases (attack, interact, chest, loot, move) pass `doorSet` to `aStar()` and use `_buildActionsWithDoorInteractions()`.
- `generateGroupPaths()`: Added `doorSet` parameter, passes to `generateSmartActions()`.
- `spreadDestinations()`: Added `doorSet` parameter. BFS expansion passes through door tiles (not valid destinations but don't block expansion to rooms beyond).
- `computeGroupRightClick()`: Added `doorSet` parameter, passes to `spreadDestinations()` and `generateGroupPaths()`.

**Client changes (`Arena.jsx`):**
- Added `doorSet` useMemo: Builds `Set<string>` of closed door positions from `doorStates`.
- `handleContextMenu`: Both group right-click (`computeGroupRightClick`) and single right-click (`generateSmartActions`) pass `doorSet`. Added to dependency array.
- `obstacleSet` still includes closed doors (for rendering/tile highlights). `doorSet` is a separate layer for A* only.

**Test coverage (`test_door_pathfinding.py` — 27 tests):**
- `TestAStarDoorTiles` (8 tests): Path through door, no path without door_tiles, prefers open route, weighted cost, multiple doors, backward compat, empty set, overlapping obstacles+door_tiles.
- `TestGetNextStepDoorTiles` (2 tests): Step through door, blocked without door_tiles.
- `TestMaybeInteractDoor` (5 tests): Adjacent door returns INTERACT, non-door returns None, no door_tiles returns None, non-adjacent returns None, diagonal adjacency works.
- `TestAIHeroAllyDoorOpening` (3 tests): Follow/aggressive/defensive stances open doors.
- `TestEnemyAICannotOpenDoors` (2 tests): Enemy AI ignores door_tiles, hero ally receives door_tiles.
- `TestDoorPathfindingEdgeCases` (7 tests): Already at goal, goal is door, start is door, door not in obstacles, fully blocked, occupied goal with door, chebyshev distance helper.

**Design decisions:**
- Door cost +3 (not +2 or +5): Makes A* prefer open routes when detour is ≤2 extra steps, but still paths through doors when necessary. Tunable.
- Stateless AI door opening: No path memory needed. Each tick A* recomputes; `_maybe_interact_door` checks immediate next step. Next tick door is open, A* routes normally.
- Enemy AI exclusion: `decide_ai_action` short-circuits — enemy behaviors never receive `door_tiles`. This is by design (enemies don't open doors).
- obstacleSet/doorSet split: Closed doors remain in obstacleSet for move highlight rendering (can't walk onto a closed door). doorSet is a separate layer passed only to A* pathfinding functions.
### 7D-2: Diagonal Door Interaction — COMPLETE
**Date:** 2026-02-15
**Tests:** 27 new tests in `test_diagonal_door_interact.py` (1091 total, 0 failures)

**Summary:** Door INTERACT actions now accept 8-directional (Chebyshev) adjacency instead of cardinal-only. Players and AI can open/close doors from diagonal positions. Chest LOOT remains cardinal-only — no behavioral change for chests.

**Server changes (`turn_resolver.py`):**
- `_is_chebyshev_adjacent()`: NEW function — returns True when `max(abs(dx), abs(dy)) == 1` (8-directional adjacency). Added alongside existing `_is_cardinal_adjacent()`.
- Door INTERACT validation (Phase 1.5): Changed from `_is_cardinal_adjacent()` to `_is_chebyshev_adjacent()`. Players can now interact with doors from any of the 8 surrounding tiles.
- Chest LOOT validation (Phase 1.75): **Unchanged** — still uses `_is_cardinal_adjacent()`. Chests require cardinal adjacency.

**Existing test update (`test_dungeon_doors.py`):**
- `test_fail_diagonal_not_cardinal` → renamed to `test_diagonal_adjacency_valid_for_door_interaction`. Now asserts diagonal door INTERACT **succeeds** (door opens, obstacle removed).
- Import updated to include `_is_chebyshev_adjacent`.

**New test coverage (`test_diagonal_door_interact.py` — 27 tests):**
- `TestChebyshevAdjacent` (12 tests): All 4 cardinal + 4 diagonal directions return True. Same tile, distance 2, distance 2 diagonal, far away all return False.
- `TestCardinalAdjacentUnchanged` (2 tests): Cardinal still works for 4 directions, diagonal still rejected — regression guard.
- `TestDoorInteractAllDirections` (12 tests): Parametrized open from all 8 positions, close from diagonal, fail at distance 2, fail on same tile.
- `TestChestLootStillCardinal` (2 tests): Chest loot succeeds from cardinal, fails from diagonal — regression guard.

**Design decisions:**
- Option A chosen (per phase doc Finding 3): Separate `_is_chebyshev_adjacent()` function used only for doors. `_is_cardinal_adjacent()` preserved for chests. No shared behavior change.
- ~10 lines of server code changed, no client changes needed. Big quality-of-life improvement — players using 8-directional movement no longer need to reposition to interact with doors.

### 7D-3: AI Door Opening (For Follow Stance) — COMPLETE
**Date:** 2026-02-15
**Tests:** 27 new tests in `test_ai_door_opening.py` (1090 total, 0 failures)

**Summary:** Hero ally AI in all movement-capable stances (follow, aggressive, defensive) can now autonomously open closed doors when their A*-computed path crosses a door tile. The implementation is stateless — no path memory needed. Each tick, A* computes a door-aware path; if the next step is a closed door and the AI is adjacent (Chebyshev distance 1), it returns INTERACT instead of MOVE. Next tick, the door is open and A* paths through normally. Enemy AI is explicitly excluded — enemies never open doors.

**Bug fix (`ai_behavior.py`):**
- `_decide_defensive_action()`: The "move toward nearby enemy" branch (within 2 tiles) was missing the `door_tiles` parameter in its `get_next_step_toward()` call. Fixed to pass `door_tiles`, ensuring defensive allies can path through doors even when approaching nearby enemies.

**Core implementation (completed as part of 7D-1, verified and tested here):**
- `_maybe_interact_door()`: Stateless helper — checks if AI's next A* step is a closed door. If adjacent (Chebyshev distance 1), returns INTERACT action. Otherwise None (caller proceeds with MOVE).
- `_decide_follow_action()`: All 4 `get_next_step_toward()` calls pass `door_tiles`; every MOVE return is wrapped with `_maybe_interact_door()` check.
- `_decide_aggressive_stance_action()`: All path calls updated; door interaction checks on 4 MOVE locations (rush, move toward target, path back to owner).
- `_decide_defensive_action()`: Path-to-owner MOVE has door check. Enemy-approach MOVE now also has door check (bug fix).
- `_decide_hold_action()`: No changes — never moves, never opens doors.
- `decide_ai_action()`: Passes `door_tiles` to hero ally stance functions only. Enemy AI behaviors never receive `door_tiles`.
- `run_ai_decisions()`: Accepts `door_tiles` from `match_tick()` and passes to `decide_ai_action()`.

**Multi-tick door crossing flow:**
1. Tick N: A* computes path through closed door. Next step IS the door tile. AI is adjacent → returns INTERACT.
2. Tick N: Turn resolver processes INTERACT in phase 1.5. Door opens. `obstacles.discard()` mutates in-place.
3. Tick N+1: A* recomputes. Door is open (not in obstacles or door_tiles). AI returns MOVE onto the now-open tile.
4. AI continues following owner / chasing enemy / staying near owner normally.

**Test coverage (`test_ai_door_opening.py` — 27 tests):**
- `TestAIDoorResume` (4 tests): Follow/aggressive/defensive open door then move through next tick; follow resumes path after stepping through opened door.
- `TestMultiDoorCrossing` (2 tests): Follow stance crosses two doors sequentially over multiple ticks; A* returns valid path through multiple closed doors.
- `TestHoldStanceNoDoors` (2 tests): Hold stance never generates INTERACT even with adjacent door; hold with enemy across door still waits.
- `TestEnemyAINoDoorsRegression` (4 tests): Aggressive/ranged/boss enemy AI cannot open doors; `run_ai_decisions` excludes enemies from `door_tiles` while passing to hero allies.
- `TestDefensiveStanceDoorFix` (1 test): Defensive stance enemy-approach uses door-aware A* (validates bug fix).
- `TestAIDoorEdgeCases` (7 tests): AI not adjacent moves closer first; already-open door = just MOVE; no doors on map = normal movement; diagonal adjacency triggers INTERACT; ally on former door tile; empty door_tiles set; `_maybe_interact_door` returns None for same-tile.
- `TestTurnResolverDoorIntegration` (2 tests): AI INTERACT action opens door in turn resolver; two-tick flow with opener ally + follower ally moving through.
- `TestAllStancesDoorBehavior` (5 tests): Summarized per-stance verification — follow/aggressive/defensive open doors, hold does not, `decide_ai_action` dispatches correctly.

**Design decisions:**
- Stateless AI door opening: No path memory needed. Each tick A* recomputes; `_maybe_interact_door` checks immediate next step. Next tick door is open, A* routes normally. Elegant and simple.
- Enemy AI exclusion: `decide_ai_action` short-circuits — enemy behaviors never receive `door_tiles`. This preserves room isolation for dungeon design (enemies stay in their rooms).
- Hold stance exemption: Hold stance never moves, so it never encounters a door in its path. No special handling needed.
- Chebyshev adjacency for door INTERACT: Matches the 7D-2 change to `turn_resolver.py`. AI diagonally adjacent to a door can open it, consistent with player behavior.

### 7E-1: Pathfinding Preview Improvements — COMPLETE
**Date:** 2026-02-15
**Tests:** 1118 existing tests pass (0 failures), client builds cleanly

**Summary:** Added real-time hover path previews for all selected units. When the mouse hovers over any tile, ghost paths are computed and rendered for each selected unit (or the single active unit) showing the route they would take if right-clicked. Multi-unit previews use distinct colors per unit. Door interaction points on paths display door icons (🚪). Formation ghost circles show where each unit would end up at the destination. Previews recalculate in real-time as the cursor moves across tiles.

**Client changes (`pathfinding.js`):**
- `computeHoverPreview()`: NEW export function — computes hover path previews for all selected units. For a single unit, calls `generateSmartActions()` to get path/actions. For multi-selected units, calls `computeGroupRightClick()` to get group paths with BFS formation spreading. Returns per-unit data: `{unitId, path, actions, destTile, intent}`. Handles edge cases: dead units, invalid tiles, obstacles, doors, chests, enemies.
- Validates target tile (rejects hard obstacles, allows doors/enemies/chests).
- Filters to alive units with known positions.
- Extracts destination tile from last MOVE action in each unit's action list.

**Client changes (`ArenaRenderer.js`):**
- `PREVIEW_COLORS` constant: 5-color palette (cyan, green, orange, purple, gold) with per-color line/fill/ghost/door variants at appropriate alpha levels.
- `drawHoverPathPreviews()`: NEW export function — renders translucent ghost paths for each unit:
  - **Path fill**: Translucent colored rectangles on each path tile.
  - **Path line**: Dashed colored line connecting path tiles (6px dash, 4px gap).
  - **Path dots**: Small colored circles at each path step for directionality.
  - **Door icons**: At each INTERACT action in the path, renders a 🚪 icon with colored border + brown background overlay.
  - **Formation ghost**: At each unit's destination, renders a translucent colored circle with dashed outline ring + outer glow ring.
- `renderFrame()`: Added `hoverPreviews` parameter. Draws hover previews BEFORE committed queue preview, so committed paths (numbered tiles) appear on top of ghost previews. Draw order: highlights → **hover previews** → queue preview → ground items → units → fog → floaters.

**Client changes (`Arena.jsx`):**
- Import: Added `computeHoverPreview` from pathfinding.
- `handleCanvasMouseMove`: Optimized with functional `setHoveredTile` update — only creates new state objects when tile coordinates actually change. Prevents unnecessary re-renders and useMemo recomputations when the mouse moves within the same tile.
- `hoverPreviews` useMemo: Computes path previews for all selected (or active) units to the hovered tile. Dependencies: `hoveredTile`, `selectedUnitIds`, `effectiveUnitId`, `players`, `obstacleSet`, `occupiedMap`, `doorStates`, `doorSet`, `friendlyUnitKeys`, and other pathfinding inputs. Returns `null` when:
  - No hovered tile, unit is dead, match not in progress.
  - `actionMode` is active (attack/ranged/skill/interact highlights take precedence).
- `renderFrame` call: Passes `hoverPreviews` prop. Added to dependency array.

**Features implemented:**
1. **Multi-unit color-coded paths**: Each selected unit gets a distinct color from the 5-color palette (cyan/green/orange/purple/gold). Single-unit preview uses cyan.
2. **Door interaction overlays**: When a path crosses a closed door, a 🚪 icon with colored border is rendered at the door tile, indicating the unit will auto-interact.
3. **Formation ghost preview**: Translucent colored circles at each unit's destination show where the formation would end up. Multi-unit destinations use BFS spreading.
4. **Real-time cursor tracking**: Paths recalculate only when the cursor crosses tile boundaries (not on every pixel), using optimized state comparison in `handleCanvasMouseMove`.
5. **Disabled during action modes**: Hover preview is suppressed when the player is in attack/ranged/skill/interact mode, since those modes have their own highlight systems.

**Performance considerations:**
- A* on 25×25 grid takes <5ms per call. With 4 units via `computeGroupRightClick`, total is ~20ms per tile boundary crossing — well within frame budget.
- `useMemo` with stable `hoveredTile` references prevents redundant recomputations.
- Previews drawn as lightweight canvas primitives (arcs, lines, rects) — negligible render cost.

**Design decisions:**
- Hover preview renders BEFORE committed queue preview in draw order. This means committed paths (numbered blue tiles from `drawQueuePreview`) appear on top, providing clear visual hierarchy.
- The 5-color palette was chosen for maximum contrast against the dark dungeon/arena backgrounds and each other.
- Ghost circles at destinations use 0.32× tile radius (slightly smaller than unit circles) so they don't overlap with actual units.
- `actionMode` suppression: When attack/skill/interact mode is active, the mode-specific highlights are more useful than path previews.
- Single-unit preview: Even without multi-select, hovering shows a path preview for the active unit — a significant QoL improvement.