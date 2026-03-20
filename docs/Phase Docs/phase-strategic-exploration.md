# Phase: Strategic Dungeon Exploration

**Status:** Sub-Phase A Complete · Sub-Phase B Complete · Sub-Phase C Pending  
**Date:** March 19, 2026  
**Goal:** Replace aimless AI patrol with room-aware strategic exploration so hero parties systematically clear entire dungeons.

---

## Problem Statement

AI hero parties don't explore the whole dungeon. They leave rooms unchecked, miss treasure chests, and idle when they should be pushing deeper. The root cause is that neither team leaders nor followers have any awareness of dungeon topology — rooms, connectivity, or discovery state.

---

## Current System Analysis

### Architecture Overview

All AI flows through `decide_ai_action()` in `ai_behavior.py`, which dispatches to two paths:

| Unit Type | Dispatch Path | Exploration Driver |
|-----------|--------------|-------------------|
| **Team Leader** (`hero_id=None`, `is_team_leader=True`) | `_decide_aggressive_action()` → patrol fallback | `_patrol_action()` — center-biased random waypoints |
| **Hero Follower** (`hero_id` set, `ai_stance="follow"`) | `_decide_stance_action()` → `_decide_follow_action()` | Trail owner → chest seek (4 tiles) → WAIT |

### Key Files

| File | Role |
|------|------|
| `server/app/core/ai_behavior.py` | Main dispatch + aggressive enemy AI (used by team leaders) |
| `server/app/core/ai_stances.py` | Stance-based hero follower behavior (follow/aggressive/defensive/hold) |
| `server/app/core/ai_patrol.py` | Waypoint-based patrol (center-biased random tile selection) |
| `server/app/core/ai_memory.py` | Enemy memory (3-turn), target selection, ally reinforcement |
| `server/app/core/ai_pathfinding.py` | A* pathfinding with door-aware costs |
| `server/app/core/match_manager.py` | Match setup, room bounds caching, dungeon state init |
| `server/app/core/map_loader.py` | Map JSON loading — rooms, doors, chests, spawn points |
| `server/app/services/tick_loop.py` | Game loop — triggers AI decisions each tick |

### Team Leader Idle Chain (current)

When the leader has no visible enemies, the decision chain in `_decide_aggressive_action()` is:

```
1. Pursue memory targets (_pursue_memory_target)     → remembered enemy positions, expires in 10 ticks
2. Reinforce ally (_reinforce_ally)                   → path to teammate in combat
3. Seek chests (_find_nearest_unopened_chest)          → within 6 tiles Manhattan
4. Trail owner — N/A for leaders
5. Scavenge ground loot (_find_nearest_ground_loot)   → within 5 tiles Manhattan
6. PATROL (_patrol_action)                            → center-biased random waypoint
```

Step 6 is the only exploration mechanism. It picks random walkable tiles biased toward the map center via `_pick_patrol_waypoint()`.

### Hero Follower Idle Chain (current — follow stance)

```
1. Regroup to owner if dist > 4 (or 6 for sustain_dps/retaliation_tank)
2. Fight visible enemies near owner
3. If no enemies AND dist_to_owner > 1 → trail owner
4. If adjacent to owner AND owner moving → keep trailing
5. Try loot adjacent chest (Chebyshev ≤ 1)
6. Seek unopened chest within 4 tiles Manhattan
7. WAIT
```

Step 7 is the terminal state. **Followers never explore, patrol, or seek new areas.**

### Patrol System Details (`ai_patrol.py`)

`_pick_patrol_waypoint()` scores every walkable tile on the map:

```python
score = dist_from_self + center_bonus * 0.5 + visited_penalty
# dist_from_self:  Manhattan distance from AI (higher = better, wants to move far)
# center_bonus:    Proximity to map center (biases toward contested areas)
# visited_penalty: -15 if tile was in recent visit history (30-tile buffer)
```

Top 8 candidates are selected, one chosen randomly. This means:
- **No room awareness** — doesn't know rooms exist
- **No door awareness** — won't target doors to open new areas
- **Center bias** — edges and corners are systematically ignored
- **No content awareness** — doesn't know chests or enemies exist beyond FOV
- **Visited history is tiny** — only 30 tiles remembered, easily re-patrols same area

### Existing Infrastructure We Can Leverage

| Asset | Location | Details |
|-------|----------|---------|
| Room definitions | `map_loader.get_room_definitions()` | `{id, name, purpose, bounds, enemy_spawns}` |
| Room bounds cache | `ai_behavior._room_bounds_cache` | Already computed at match start via `set_room_bounds()` |
| Door positions | `map_loader.get_doors()` | Door (x, y) positions per map |
| Door states | `match.door_states` | `{"{x},{y}": "closed"|"open"}` |
| Chest states | `match.chest_states` | `{"{x},{y}": "unopened"|"opened"}` |
| FOV per unit | `fov.compute_fov()` | Recomputed each tick |
| Team shared FOV | `tick_loop.match_tick()` | Union of all team FOV |
| A* pathfinding | `ai_pathfinding.a_star()` | Door-aware (closed door = +3 cost) |

**Not currently available (must be built):**
- Room adjacency graph (which rooms connect to which)
- Per-team room discovery state
- Per-team room clearance state
- Exploration target selection

---

## Three Identified Gaps

### Gap 1: No Room Awareness

Neither leader nor followers know which rooms exist beyond their FOV. The leader patrols randomly instead of systematically visiting rooms. A room 20 tiles away with 3 chests and enemies is invisible to the AI decision system.

### Gap 2: Leader Patrol Is Aimless

`_pick_patrol_waypoint()` picks random tiles biased to map center. It has no concept of:
- Doors that could be opened to reveal new areas
- Rooms that haven't been visited
- Content (chests, enemies) that exists in unexplored rooms
- Systematic coverage of the dungeon

### Gap 3: Followers Are Purely Reactive

When idle and near their owner:
- Chest seek range is only 4 tiles (follow) or 6 tiles (aggressive)
- If no chest is within range → **WAIT indefinitely**
- No concept of spreading out to cover a room
- No concept of "the room we're in has chests in the far corner"

---

## Implementation Plan

### Sub-Phase A: Room Graph & Discovery Tracking (Foundation)

**New file:** `server/app/core/ai_exploration.py`

#### A1: Room Adjacency Graph

Build a room connectivity graph at match start from existing room/door data:

```
Input:  room_definitions (bounds), door_positions
Output: {room_id: [connected_room_ids]}
```

Logic:
- For each door, determine which two rooms it connects (door position falls on/between room bounds)
- Corridors connecting rooms are identified by tiles between room bounds
- Store as adjacency list: `_room_graph[match_id] = {room_id: set(neighbor_ids)}`
- Built once at match start in `_init_dungeon_state()`

#### A2: Room Discovery State

Track per-team room discovery:

```python
_room_discovery[match_id] = {
    "a": {room_id: "undiscovered" | "discovered" | "cleared"},
    "b": { ... },
    ...
}
```

State transitions:
- `undiscovered` → `discovered`: Any team member's FOV includes tiles inside the room bounds
- `discovered` → `cleared`: All enemies in the room are dead AND all chests in the room are opened (or no enemies/chests existed)

Update trigger: Each tick, after FOV is computed, check if any team's FOV overlaps any undiscovered room for that team. For `discovered → cleared`, check after deaths and chest interactions.

#### A3: Exploration Target API

```python
def get_next_exploration_target(match_id: str, team: str, current_pos: tuple) -> dict | None:
    """Return the best next room to explore.
    
    Returns: {room_id, center: (x,y), entrance: (x,y), priority}
    Priority: uncleared > discovered-uncleared > undiscovered
    Tiebreaker: proximity (A* distance or Manhattan)
    """
```

#### Files Modified
- **New:** `server/app/core/ai_exploration.py` (~150–200 lines)
- **Modified:** `server/app/core/match_manager.py` — call `build_room_graph()` and `init_room_discovery()` during `_init_dungeon_state()`
- **Modified:** `server/app/services/tick_loop.py` — call `update_room_discovery()` after FOV computation each tick

---

### Sub-Phase B: Smart Leader Pathing (Core Behavior Change)

Replace the leader's patrol fallback with room-aware exploration.

#### B1: Strategic Patrol Replacement

In `_decide_aggressive_action()` (ai_behavior.py), replace step 4e (patrol fallback) for team leaders:

**Current:**
```python
# 4e: Fall back to patrol (enemy AI only)
return _patrol_action(ai, grid_width, grid_height, obstacles, all_units, ...)
```

**New (for team leaders only):**
```python
# 4e: Strategic exploration for team leaders; patrol fallback for dungeon enemies
if getattr(ai, 'is_team_leader', False):
    target = get_next_exploration_target(match_id, ai.team, ai_pos)
    if target:
        # Path to target room entrance/center
        next_step = get_next_step_toward(ai_pos, target["entrance"], ...)
        if next_step:
            return PlayerAction(MOVE, reason="explore_room")
# Regular enemies still patrol
return _patrol_action(...)
```

#### B2: Room Clearing Behavior

When the leader arrives inside a target room:
- Existing combat logic handles fighting enemies (they become visible via FOV)
- Existing chest-seeking handles nearby chests (within 6 tiles)
- Room marked `cleared` once all enemies dead + chests opened
- Leader then queries for next uncleared room

#### B3: Door Prioritization

When pathing to an unexplored room, the A* path will naturally route through closed doors (cost +3). The existing `_maybe_interact_door()` already handles opening doors when adjacent. No change needed — the foundation handles this.

#### Files Modified
- **Modified:** `server/app/core/ai_behavior.py` — replace patrol fallback for team leaders with exploration target pathing (~40 lines changed)

---

### Sub-Phase C: Enhanced Follower Awareness (Party Coordination)

Upgrade follower idle behavior so they help clear rooms instead of clustering on the leader.

#### C1: Room-Aware Chest Seeking

In `_decide_follow_action()` and `_decide_aggressive_stance_action()` (ai_stances.py), when the standard chest seek finds nothing:

**Current:**
```python
max_range = _CHEST_SEEK_MAX_RANGE.get("follow", 4)
chest_target = _find_nearest_unopened_chest(ai, chest_states, max_range)
# If None → WAIT
```

**New:**
```python
max_range = _CHEST_SEEK_MAX_RANGE.get("follow", 4)
chest_target = _find_nearest_unopened_chest(ai, chest_states, max_range)
if not chest_target:
    # Expand search to current room bounds if we're inside a room
    room = get_current_room(match_id, ai.position.x, ai.position.y)
    if room:
        room_range = max(room.width, room.height)
        chest_target = _find_nearest_unopened_chest(ai, chest_states, room_range)
```

This means followers will seek chests anywhere in the room they're currently in, not just within 4 tiles.

#### C2: Spread-Out Behavior When Clearing

When idle in a room with the owner and no enemies visible, instead of WAITing, followers spread toward unlooted chests or unexplored corners of the room:

```python
# After standard chest seek fails AND we're in the same room as owner:
# If room has unexplored corners (tiles not in visit history), drift toward them
# This creates a "sweep" effect where the party fans out to cover the room
```

#### C3: Post-Combat Follow Impulse Extension

The existing `_POST_COMBAT_FOLLOW_GRACE` is 5 ticks. After combat, followers trail the leader for 5 ticks then WAIT. This should be extended or replaced with: "trail leader until leader stops moving OR we enter a new room."

#### Files Modified
- **Modified:** `server/app/core/ai_stances.py` — room-aware chest range expansion + spread behavior (~60 lines)

---

### Sub-Phase D: Exploration Completion & Backtracking

#### D1: Exploration Progress Tracking

```python
def get_exploration_progress(match_id: str, team: str) -> dict:
    """Return exploration stats for a team.
    
    Returns: {
        total_rooms, discovered_rooms, cleared_rooms,
        total_chests, opened_chests,
        exploration_pct, clearance_pct
    }
    """
```

#### D2: Backtrack to Missed Rooms

When a leader reaches a dead end (no adjacent uncleared rooms), backtrack to the nearest uncleared room even if it requires crossing already-explored territory. The room graph adjacency makes this a simple BFS from current room to find nearest uncleared.

#### D3: Extraction Readiness

When all rooms are cleared (100% clearance), the team leader should path toward the portal/stairs. This integrates with the existing Phase 12C portal extraction logic.

#### Files Modified
- **Modified:** `server/app/core/ai_exploration.py` — add progress tracking + backtrack logic (~40 lines)
- **Modified:** `server/app/core/ai_behavior.py` — extraction trigger when fully cleared (~10 lines)

---

## Implementation Order

```
Sub-Phase A (Foundation)     — Must be first. All other phases depend on room graph + discovery state.
Sub-Phase B (Leader Pathing) — Highest impact. This alone may solve 80% of the exploration problem.
Sub-Phase C (Follower Awareness) — Polish. Improves room-clearing efficiency and chest coverage.
Sub-Phase D (Completion Logic) — Final touches. Backtracking and extraction awareness.
```

**Recommended approach:** Implement A + B together, run batch PvPvE simulations to measure exploration coverage improvement, then proceed to C + D.

---

## Testing Strategy

### Unit Tests (new test file: `tests/test_ai_exploration.py`)

- Room graph construction from mock room/door data
- Discovery state transitions (undiscovered → discovered → cleared)
- Exploration target selection (nearest uncleared room)
- Edge cases: single room maps, fully cleared dungeons, disconnected rooms

### Integration Tests (batch PvPvE simulations)

Run `batch_pvpve.py` with multiple seeds and measure:

| Metric | Current (estimate) | Target |
|--------|-------------------|--------|
| Rooms discovered per team | ~40–60% | 90%+ |
| Chests opened per team | ~30–50% | 80%+ |
| Average turns to clear dungeon | N/A (never fully clears) | < 150 turns |
| Teams extracting at portal | Rare | Common |

### Regression Tests

- Existing PvP arena tests must still pass (no rooms → exploration disabled)
- Existing door interaction tests
- Existing chest looting tests
- Existing pathfinding tests
- Existing stance behavior tests

---

## Constants & Tuning Parameters

| Constant | Proposed Value | Location | Purpose |
|----------|---------------|----------|---------|
| `_ROOM_DISCOVER_OVERLAP` | 1 tile | `ai_exploration.py` | Min FOV tiles inside room to mark discovered |
| `_ROOM_CLEAR_REQUIRES_CHESTS` | True | `ai_exploration.py` | Whether chest opening is required for clearance |
| `_LEADER_EXPLORE_PRIORITY_LOOT` | 1.5 | `ai_exploration.py` | Priority multiplier for loot rooms |
| `_LEADER_EXPLORE_PRIORITY_ENEMY` | 1.0 | `ai_exploration.py` | Priority multiplier for enemy rooms |
| `_FOLLOWER_ROOM_CHEST_RANGE` | room size | `ai_stances.py` | Expanded chest range when inside a room |
| `_SPREAD_IDLE_RANGE` | 3 tiles | `ai_stances.py` | How far followers spread when idle in a room |

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Room graph incorrect for WFC dungeons | Medium | Validate with multiple seeds; handle rooms with no doors |
| Leader gets stuck pathing between rooms | Low | Fallback to existing patrol if A* to target fails |
| Followers drift too far during spread | Low | Constrain spread to room bounds + owner leash |
| Performance impact of per-tick discovery update | Low | Only check undiscovered rooms (shrinking set); skip when team has no new FOV |
| Breaks existing PvP arena behavior | Very Low | Guard all exploration code behind `if room_definitions exist` check |

---

## Implementation Log

### Sub-Phase A: Room Graph & Discovery Tracking — COMPLETE

**Date:** March 19, 2026  
**Tests:** 35 new tests (4028 total, 0 regressions)

#### Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `server/app/core/ai_exploration.py` | ~340 | Room graph, discovery state, exploration target API |
| `server/tests/test_ai_exploration.py` | ~340 | 35 unit tests covering all Phase A functionality |

#### Files Modified

| File | Change |
|------|--------|
| `server/app/core/match_manager.py` | Import `ai_exploration`; added `_init_exploration_state()` helper called at all 3 `_init_dungeon_state` sites; added `clear_exploration_state()` at match cleanup |
| `server/app/services/tick_loop.py` | Import `ai_exploration`; added Step 1.5 per-tick `update_room_discovery()` + `update_room_clearance()` after FOV computation, before AI decisions |

#### What Was Built

**A1 — Room Adjacency Graph (`build_room_graph`)**
- Constructs a bidirectional graph: `{room_id: set(neighbor_room_ids)}`
- Maps doors to the rooms they connect (tolerance-based boundary matching)
- Maps chests to their containing rooms
- Caches room center positions, bounds, and enemy spawn locations
- Built once at match start, rebuilt on floor transitions

**A2 — Room Discovery State (`init_room_discovery`, `update_room_discovery`, `update_room_clearance`)**
- Per-team tracking: `{room_id: "undiscovered" | "discovered" | "cleared"}`
- `undiscovered → discovered`: triggered when team FOV overlaps room bounds (≥1 tile)
- `discovered → cleared`: triggered when no alive enemies inside room AND all room chests opened
- Updated every tick (Step 1.5 in tick_loop) using pre-computed team FOV
- Only checks undiscovered/discovered rooms (shrinking set per tick)

**A3 — Exploration Target API (`get_next_exploration_target`)**
- Returns best room for a team leader to explore next
- Priority: discovered-uncleared (P1) > frontier/undiscovered-adjacent (P2) > deep unknown (P3)
- Tiebreaker: Manhattan distance to room center (closest wins)
- Returns door entrance position when routing through known territory to frontier rooms
- Returns `None` when all rooms cleared (signals extraction readiness)

**Helpers:** `get_current_room`, `get_exploration_progress`, `get_room_discovery`, `get_room_graph`, `clear_exploration_state`

#### Key Design Decisions

1. **All exploration logic is guarded by room existence** — arena maps (no rooms) silently skip all exploration initialization and tick updates
2. **Discovery update runs before AI decisions** so the current tick's FOV produces discovery state that AI can immediately act on
3. **Clearance requires both enemy kills AND chest looting** (configurable via `_ROOM_CLEAR_REQUIRES_CHESTS`)
4. **Module caches are match-scoped** and cleaned up at match end via `clear_exploration_state()`

---

### Sub-Phase B: Smart Leader Pathing — COMPLETE

**Date:** March 19, 2026  
**Tests:** 12 new tests (4040 total, 0 regressions)

#### Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `server/tests/test_ai_exploration_b.py` | ~490 | 12 unit tests covering all Phase B functionality |

#### Files Modified

| File | Change |
|------|--------|
| `server/app/core/ai_behavior.py` | Import `get_next_exploration_target`, `get_current_room` from `ai_exploration`; replaced patrol fallback (step 4e) for team leaders with exploration target pathing — ~20 lines added |

#### What Was Built

**B1 — Strategic Patrol Replacement**
- In `_decide_aggressive_action()`, step 4e now checks `is_team_leader` + `match_id`
- Team leaders query `get_next_exploration_target()` for the best uncleared/undiscovered room
- Leader paths toward the room entrance (door position) using existing A* + `get_next_step_toward()`
- If A* finds no path or no exploration target exists, falls back to regular patrol
- Regular dungeon enemies (`is_team_leader=False`) still use `_patrol_action()` unchanged
- Emits `reason="explore_room"` for debugging/tracing

**B2 — Room Clearing Behavior (No Code Change)**
- When the leader enters a target room, existing FOV triggers `update_room_discovery()` → room becomes "discovered"
- Existing combat logic handles visible enemies (step 5+ in aggressive action)
- Existing chest-seeking (step 4b2) handles nearby chests
- `update_room_clearance()` (tick loop Step 1.5) marks the room "cleared" once enemies dead + chests opened
- Leader then re-queries `get_next_exploration_target()` for the next room

**B3 — Door Prioritization (No Code Change)**
- A* already treats closed doors as +3 cost walkable tiles (Phase 7D-1)
- `_maybe_interact_door()` already emits INTERACT when adjacent to a closed door
- Both mechanisms work seamlessly with explore-room pathing

#### Test Coverage

| Test Class | Tests | Validates |
|------------|-------|-----------|
| `TestLeaderExploration` | 6 | Leader explores, moves toward entrance, patrol fallback when all cleared, enemies use patrol, arena mode fallback, no rooms fallback |
| `TestLeaderExplorationChain` | 3 | Nearest frontier targeting, sequential room clearing, discovered-uncleared priority |
| `TestLeaderDoorInteraction` | 1 | Door INTERACT emitted when adjacent on explore path |
| `TestCombatPreemptsExploration` | 2 | Visible enemies preempt exploration, chest seeking preempts exploration |

#### Key Design Decisions

1. **Minimal code change** — only ~20 lines added to `ai_behavior.py`; all exploration intelligence lives in `ai_exploration.py` (Phase A)
2. **Graceful degradation** — if `match_id` is None, rooms don't exist, or A* fails, the leader silently falls back to patrol
3. **Priority chain preserved** — exploration is step 4e (lowest priority idle action); memory pursuit, ally reinforcement, chest seeking, loot scavenging, and trail-owner all still run first
4. **No changes to enemy AI** — only `is_team_leader=True` units use exploration; dungeon enemies keep their existing patrol/leash behavior

