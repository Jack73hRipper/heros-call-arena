# Phase 10 — Auto-Target & Melee Pursuit System

## Overview

Right-clicking an enemy currently computes a one-time A* path to an adjacent tile and queues a single melee attack at the enemy's **coordinates at the time of the click**. If the enemy moves even one tile before the attack resolves, the attack whiffs and the player stands idle — no further pursuit, no re-engagement. The player must manually right-click again every turn to chase a fleeing enemy.

**Goal:** When a player right-clicks an enemy, the unit should **persistently chase and melee attack** that enemy until:
- The target dies
- The player issues any new command (right-click elsewhere, queue an action, use a skill)
- The player explicitly cancels (Escape / clear queue)
- The target becomes permanently unreachable

This is essentially giving human-controlled units a simplified version of the AI's aggressive chase behavior. The system should feel like: *"right-click enemy = auto-pilot melee that enemy."*

---

## Current State (Diagnosed)

### How Melee Works Now

**Client side** ([client/src/canvas/pathfinding.js](../../client/src/canvas/pathfinding.js) — `generateSmartActions()`):
1. Player right-clicks an enemy tile
2. A* computes path from player to a tile adjacent to the enemy
3. Builds action list: `[MOVE, MOVE, ..., ATTACK(enemy_x, enemy_y)]`
4. Sends as `batch_actions` → server replaces queue with this list

**Server side** ([server/app/services/websocket.py](../../server/app/services/websocket.py) — `match_tick()`):
1. Each tick, `pop_next_actions()` pops the first action from each player's queue
2. Turn resolver processes one action per player per tick
3. Movement resolves in Phase 1, melee in Phase 3

**Turn Resolver** ([server/app/core/turn_resolver.py](../../server/app/core/turn_resolver.py) — melee section):
1. Looks for an enemy at `(target_x, target_y)`
2. If nobody there, checks `pre_move_occupants` to see if the original occupant moved but is still adjacent
3. If the enemy moved out of range → **miss** → no retry

### The Problem
- The `ATTACK` action stores **coordinates**, not a **target entity ID**
- The action queue is a static list computed once — it doesn't adapt to target movement
- Once the queue is consumed or the attack misses, the player goes idle
- No mechanism exists for "keep doing this until interrupted"

### Relevant Files
| File | Role |
|------|------|
| `server/app/models/player.py` | `PlayerState` — needs new `auto_target_id` field |
| `server/app/models/actions.py` | `PlayerAction` — attack actions use coordinate targeting |
| `server/app/core/match_manager.py` | Action queue management — `queue_action()`, `pop_next_actions()` |
| `server/app/services/websocket.py` | WS message handling + tick loop — needs auto-target integration |
| `server/app/core/turn_resolver.py` | Melee resolution (Phase 3) — no changes needed |
| `server/app/core/combat.py` | `is_adjacent()`, `calculate_damage()` — no changes needed |
| `server/app/core/ai_behavior.py` | AI chase logic — reference for server-side pathfinding (A*, `_astar()`) |
| `client/src/canvas/pathfinding.js` | `generateSmartActions()` — sends batch on right-click |
| `client/src/components/Arena/Arena.jsx` | Right-click handler, canvas rendering |
| `client/src/context/GameStateContext.jsx` | Client state — needs `autoTargetId` tracking |
| `client/src/hooks/useWebSocket.js` | WS message processing |
| `client/src/components/HUD/HUD.jsx` | HUD — target indicator display |

---

## Architecture Decision

### Why Server-Side Auto-Target (not client-side re-queuing)

| Approach | Pros | Cons |
|----------|------|------|
| **Client re-queues every tick** | Simple concept | Race conditions, network latency, client must be perfectly responsive, doubles WS traffic |
| **Server auto-retry failed attacks** | Minimal changes | Only works if enemy is still adjacent — doesn't handle chasing |
| **Pre-compute longer move+attack chains** | No new systems | Stale coordinates — enemy changes position every turn |
| **Server-side auto-target (chosen)** | Server knows live positions, zero stale data, one WS message, works with party members, mirrors AI behavior | New state field, new tick logic |

The **server-side auto-target** approach is cleanest because:
- The server always has everyone's live positions — no stale coordinates
- It integrates naturally with `pop_next_actions()`: if the queue is empty but `auto_target_id` is set, generate the chase action just-in-time using the target's **current** position
- Works seamlessly with party members (they already have server-side AI — this is the same pattern)
- No extra network traffic per turn — one `set_auto_target` message replaces repeated `batch_actions`
- AI already has this exact behavior (`_decide_aggressive_stance_action`) — we reuse the same A* and adjacency logic

---

## Phased Implementation Plan

### Phase 10A — Server Model & Auto-Target State
**Priority: FOUNDATION — Everything builds on this**

**Files:** `server/app/models/player.py`, `server/app/core/match_manager.py`

#### 10A-1: Add `auto_target_id` to PlayerState

Add a new optional field to `PlayerState` that stores the player_id of the entity being auto-targeted.

```python
# In PlayerState (after ai_stance):
# Phase 10A: Auto-target — persistent melee pursuit target
# When set, the server generates chase/attack actions each tick if the player's queue is empty.
# Cleared when: target dies, player issues a new command, player cancels, target unreachable.
auto_target_id: str | None = None
```

**Constraints:**
- Default `None` (no auto-target)
- Must not persist across matches (ephemeral, in-match only)
- JSON-serializable (it's just a string)

#### 10A-2: Match Manager Helpers

Add helpers to `match_manager.py` for managing auto-target state:

```python
def set_auto_target(match_id: str, player_id: str, target_id: str) -> bool | str:
    """Set a persistent auto-target for a player.
    
    Validates:
    - Player exists and is alive
    - Target exists and is alive
    - Target is an enemy (different team)
    
    Returns True on success, error string on failure.
    """

def clear_auto_target(match_id: str, player_id: str) -> None:
    """Clear the auto-target for a player. No-op if not set."""

def get_auto_target(match_id: str, player_id: str) -> str | None:
    """Get the current auto-target_id for a player, or None."""
```

**Key behavior:** `set_auto_target` also clears the player's action queue (the auto-target replaces any existing plan). This mirrors how `batch_actions` already clears the queue before replacing it.

#### 10A-3: Tests

**New file:** `server/tests/test_auto_target.py`

| Test | Description |
|------|-------------|
| `test_set_auto_target_valid` | Player targets alive enemy → `auto_target_id` is set |
| `test_set_auto_target_clears_queue` | Setting auto-target clears any existing action queue |
| `test_set_auto_target_invalid_ally` | Cannot auto-target same-team unit → error |
| `test_set_auto_target_invalid_dead` | Cannot auto-target dead unit → error |
| `test_set_auto_target_invalid_self` | Cannot auto-target self → error |
| `test_clear_auto_target` | Clearing sets `auto_target_id` to None |
| `test_clear_auto_target_noop` | Clearing when not set is a no-op |
| `test_get_auto_target` | Returns current target_id or None |

**Estimated scope:** ~30 lines model change, ~60 lines helpers, ~100 lines tests

---

### Phase 10B — Server-Side Chase Action Generation
**Priority: CORE — The beating heart of the feature**

**Files:** `server/app/services/websocket.py`, `server/app/core/match_manager.py`

#### 10B-1: `generate_auto_target_action()` Function

A new function in `match_manager.py` that generates the appropriate action for a player who has an active auto-target and an empty queue. This runs once per tick, producing a single `PlayerAction`.

```python
def generate_auto_target_action(
    match_id: str,
    player_id: str,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    door_tiles: set[tuple[int, int]] | None = None,
) -> PlayerAction | None:
    """Generate a chase/attack action for a player with an active auto-target.
    
    Decision logic:
    1. Validate target is still alive — if dead, clear auto-target, return None
    2. If adjacent to target → return ATTACK(target.position.x, target.position.y)
    3. If not adjacent → A* path to adjacent tile → return MOVE(next_step)
       - If path crosses a closed door → return INTERACT(door_tile) instead
    4. If unreachable (A* returns None) → clear auto-target, return None
    
    Returns:
        PlayerAction to execute this tick, or None if auto-target was cleared.
    """
```

**Key design points:**
- Reuses the server-side `_astar()` function from `ai_behavior.py` (or a shared version)
- Produces exactly ONE action per tick (move OR attack OR interact) — same as AI behavior
- Automatically clears auto-target when target dies or is unreachable
- Does NOT clear auto-target on a failed move (might be temporarily blocked — retry next tick)

#### 10B-2: Integration into `match_tick()`

Insert auto-target action generation into the tick loop in `websocket.py`, **after** popping queued actions but **before** adding implicit waits.

```python
# In match_tick(), after Step 3 (pop_next_actions):

# --- Step 3.5: Generate auto-target actions for players with empty queues ---
for pid, unit in all_units.items():
    if not unit.is_alive or unit.unit_type != "human":
        continue
    if pid in raw_actions:
        continue  # Player has a queued action — don't override
    if unit.auto_target_id:
        auto_action = generate_auto_target_action(
            match_id, pid, all_units,
            grid_width, grid_height, obstacles,
            door_tiles=door_tiles,
        )
        if auto_action:
            action_list.append(auto_action)
            submitted_ids.add(pid)  # Prevent implicit wait
```

**Important ordering:**
- Step 2: AI decisions (existing)
- Step 3: Pop human queued actions (existing)
- **Step 3.5: Auto-target actions (NEW) — only for humans with empty queues**
- Step 4: Implicit waits for everyone else (existing)

This means:
- If a player has queued actions (from right-click, manual queue, etc.), those take priority
- The auto-target only fires when the queue runs dry
- The initial right-click still queues the A*-computed path as `batch_actions` — the auto-target kicks in afterward to keep chasing

#### 10B-3: Auto-Target Invalidation

The auto-target must be cleared in these scenarios:

| Trigger | Where | Logic |
|---------|-------|-------|
| Target dies | `match_tick()`, after turn resolution | Check deaths list — if `auto_target_id` is in deaths, clear |
| Player queues any new action | `queue_action()` | Any `queue_action()` call clears `auto_target_id` |
| Player sends `batch_actions` | `websocket.py` WS handler | `batch_actions` already clears queue — also clear auto-target |
| Player sends `clear_queue` | `websocket.py` WS handler | Explicit cancel — also clear auto-target |
| Target becomes unreachable | `generate_auto_target_action()` | A* returns null → clear auto-target |
| Match ends | Implicit | Match state is destroyed |

**Critical:** `queue_action()` clearing auto-target means that ANY new command (right-click elsewhere, click a skill, queue a move) automatically cancels pursuit. This is the correct UX — new commands override old ones.

#### 10B-4: Party Member Support

Party members (controlled AI allies) should also support auto-target. When a player right-clicks an enemy while controlling a party member, the auto-target is set on that member's `PlayerState`.

In `match_tick()`, extend Step 3.5 to also check party members:

```python
# Also generate auto-target actions for controlled party members
for pid, unit in all_units.items():
    if not unit.is_alive:
        continue
    if unit.controlled_by and unit.auto_target_id:
        if pid not in submitted_ids and pid not in raw_actions:
            auto_action = generate_auto_target_action(
                match_id, pid, all_units,
                grid_width, grid_height, obstacles,
                door_tiles=door_tiles,
            )
            if auto_action:
                action_list.append(auto_action)
                submitted_ids.add(pid)
```

#### 10B-5: Tests

**Extend:** `server/tests/test_auto_target.py`

| Test | Description |
|------|-------------|
| `test_auto_target_attack_when_adjacent` | Unit adjacent to target → generates ATTACK at target's current coords |
| `test_auto_target_chase_when_distant` | Unit 3 tiles away → generates MOVE toward target |
| `test_auto_target_door_interaction` | Path crosses closed door → generates INTERACT |
| `test_auto_target_clears_on_target_death` | Target dies → auto-target cleared, returns None |
| `test_auto_target_clears_on_unreachable` | A* returns null → auto-target cleared |
| `test_auto_target_no_override_queued_actions` | Player has queued actions → auto-target doesn't fire |
| `test_auto_target_fires_when_queue_empty` | Queue empty with auto-target set → generates action |
| `test_queue_action_clears_auto_target` | Queueing any action clears auto-target |
| `test_batch_actions_clears_auto_target` | batch_actions WS message clears auto-target |
| `test_clear_queue_clears_auto_target` | clear_queue WS message clears auto-target |
| `test_auto_target_party_member` | Party member with auto-target generates chase action |
| `test_auto_target_uses_live_position` | Target moves → next tick attacks at new position (not stale) |

**Estimated scope:** ~80 lines core logic, ~40 lines tick integration, ~200 lines tests

---

### Phase 10C — WebSocket Protocol & Client Messages
**Priority: HIGH — Connects client to server**

**Files:** `server/app/services/websocket.py`, `client/src/hooks/useWebSocket.js`, `client/src/context/GameStateContext.jsx`

#### 10C-1: Server WS Handler — `set_auto_target` Message

Add a new WS message type that the client sends when right-clicking an enemy:

```json
{
  "type": "set_auto_target",
  "target_id": "enemy_abc123",
  "unit_id": "player_id_or_party_member_id"
}
```

Server handler in `websocket.py`:
1. Validate `target_id` is an alive enemy of a different team
2. Call `set_auto_target(match_id, unit_id, target_id)`
3. Respond with confirmation:

```json
{
  "type": "auto_target_set",
  "unit_id": "player_id",
  "target_id": "enemy_abc123",
  "target_username": "Skeleton Warrior"
}
```

#### 10C-2: Server WS Handler — `clear_auto_target` Message

```json
{
  "type": "clear_auto_target",
  "unit_id": "player_id_or_party_member_id"
}
```

Response:
```json
{
  "type": "auto_target_cleared",
  "unit_id": "player_id"
}
```

#### 10C-3: Auto-Target Cleared Notification

When auto-target is cleared automatically (target died, unreachable), the server should push a notification to the player so the client can update its UI:

```json
{
  "type": "auto_target_cleared",
  "unit_id": "player_id",
  "reason": "target_died" | "unreachable" | "new_command"
}
```

#### 10C-4: Include Auto-Target in Turn Result

Add auto-target state to the per-player `turn_result` payload so the client stays in sync:

```json
{
  "type": "turn_result",
  ...
  "auto_targets": {
    "player_id": "enemy_abc123",
    "party_member_id": null
  }
}
```

#### 10C-5: Client State — `GameStateContext` updates

Add to game state:
```javascript
// In GameStateContext initial state:
autoTargetId: null,      // Current player's auto-target
partyAutoTargets: {},    // { unitId: targetId } for party members
```

Handle messages in reducer:
- `auto_target_set` → set `autoTargetId` (or update `partyAutoTargets`)
- `auto_target_cleared` → clear `autoTargetId` (or entry in `partyAutoTargets`)
- `turn_result` with `auto_targets` → sync state

#### 10C-6: Protocol Documentation

Update `docs/websocket-protocol.md` with the new message types.

**Estimated scope:** ~60 lines server WS handlers, ~40 lines client state, ~20 lines docs

---

### Phase 10D — Client Integration & Right-Click Behavior
**Priority: HIGH — The player-facing change**

**Files:** `client/src/components/Arena/Arena.jsx`, `client/src/canvas/pathfinding.js`

#### 10D-1: Right-Click on Enemy — Send Auto-Target

Modify `handleContextMenu` in `Arena.jsx`. When the player right-clicks an enemy:

1. **Keep existing behavior:** Compute A* path and send `batch_actions` (move + attack) for the initial approach
2. **Add new behavior:** Also send `set_auto_target` with the enemy's `player_id`
3. The batch handles the initial path; when the queue runs dry, the server's auto-target takes over

```javascript
// In handleContextMenu, after generateSmartActions returns an attack intent:
if (result.intent === 'attack') {
  // Send the initial path as batch_actions (existing)
  sendAction({ type: 'batch_actions', actions: result.actions, unit_id: unitId });
  
  // Also set auto-target for persistent pursuit (NEW)
  const targetInfo = occupiedMap[targetKey];
  if (targetInfo) {
    sendAction({ type: 'set_auto_target', target_id: targetInfo.pid, unit_id: unitId });
  }
}
```

#### 10D-2: Right-Click Elsewhere — Clear Auto-Target

Any right-click that is NOT an enemy attack (move to tile, interact with door, loot chest) should clear the auto-target. This happens naturally because `batch_actions` clears auto-target on the server (10B-3), but we should also send an explicit `clear_auto_target` for clarity:

```javascript
// In handleContextMenu, for non-attack intents:
if (result.intent !== 'attack') {
  // batch_actions already clears server-side, but also clear client state
  sendAction({ type: 'clear_auto_target', unit_id: unitId });
}
```

#### 10D-3: Manual Actions Clear Auto-Target

When the player uses the action mode buttons (Move, Attack, Ranged, Skill), the auto-target should clear. Since all these go through `queue_action()` which clears auto-target server-side (10B-3), the client just needs to update local state:

In `handleCanvasClick`:
```javascript
// Any manual action mode click clears auto-target locally
if (autoTargetId) {
  dispatch({ type: 'CLEAR_AUTO_TARGET' });
}
```

#### 10D-4: Escape Key Clears Auto-Target

Add Escape key handler (or extend existing `clear_queue` shortcut) to also clear auto-target:

```javascript
// In keyboard handler:
if (e.key === 'Escape') {
  sendAction({ type: 'clear_queue', unit_id: effectiveUnitId });
  sendAction({ type: 'clear_auto_target', unit_id: effectiveUnitId });
  dispatch({ type: 'SET_ACTION_MODE', payload: null });
  dispatch({ type: 'CLEAR_AUTO_TARGET' });
}
```

#### 10D-5: Group Right-Click Auto-Target

When multiple units are selected (Phase 7B group right-click) and the target is an enemy, set auto-target for all selected units:

```javascript
// In group right-click handler, when target is an enemy:
for (const unitId of selectedUnitIds) {
  sendAction({ type: 'set_auto_target', target_id: targetInfo.pid, unit_id: unitId });
}
```

**Estimated scope:** ~40 lines Arena.jsx changes, ~10 lines pathfinding.js, ~15 lines keyboard handler

---

### Phase 10E — Visual Feedback & HUD
**Priority: MEDIUM — Polish, but important for player understanding**

**Files:** `client/src/canvas/ArenaRenderer.js`, `client/src/components/HUD/HUD.jsx`, `client/src/components/Arena/Arena.jsx`

#### 10E-1: Target Indicator on Canvas

Render a visual indicator on the auto-targeted enemy so the player knows who they're pursuing. Options (implement the simplest that looks good):

- **Target reticle:** Small crosshair/brackets drawn around the enemy sprite
- **Pulsing red outline:** Animated ring around the targeted enemy
- **Connecting line:** Thin dashed line from attacker to target (may be noisy on large maps)

Recommended: **Pulsing brackets** — `[ ]` corners rendered around the target tile, pulsing opacity with a sine wave (similar to existing selection ring logic).

```javascript
// In renderFrame(), after drawing units:
if (autoTargetId && players[autoTargetId]) {
  const target = players[autoTargetId];
  drawTargetReticle(ctx, target.position.x, target.position.y, frameTime);
}
```

The reticle should only render if the target is within the player's FOV (visible tiles). Use the same visibility check as unit rendering.

#### 10E-2: HUD Target Display

Show the auto-target's name and HP in the HUD panel, similar to a "target frame" in MMOs:

```
┌──────────────┐
│ ⚔ Targeting: │
│ Skeleton War. │
│ ████░░ 45/80 │
└──────────────┘
```

- Show target name, HP bar, HP numbers
- Show "Pursuing..." text when not adjacent (chasing)
- Show "Attacking!" text when adjacent (within melee range)
- Fade/hide when no auto-target is set

#### 10E-3: Combat Log Messages

Add informational messages to the combat log when auto-target is set/cleared:

- `"⚔ Auto-targeting: Skeleton Warrior"`
- `"⚔ Target eliminated: Skeleton Warrior"`
- `"⚔ Target lost — unreachable"`
- `"⚔ Pursuit cancelled"`

These use the existing `ADD_COMBAT_LOG` dispatch pattern.

#### 10E-4: Cursor Feedback

When hovering over an enemy with no action mode active, change the cursor to `crosshair` to hint that right-clicking will auto-target. Currently the cursor is `default` outside of action modes.

**Estimated scope:** ~50 lines renderer, ~40 lines HUD, ~20 lines combat log, ~5 lines cursor

---

### Phase 10F — Edge Cases & Robustness
**Priority: MEDIUM — Prevents bugs in complex scenarios**

**Files:** `server/app/core/match_manager.py`, `server/app/services/websocket.py`

#### 10F-1: Target Switches Team (Edge Case)

If the target somehow changes team (unlikely in current design, but future-proofing):
- `generate_auto_target_action()` should validate `target.team != player.team` each tick
- If they're now allies → clear auto-target

#### 10F-2: Multiple Units Targeting Same Enemy

No issues here — multiple attackers can all auto-target the same enemy. When the enemy dies, all their auto-targets clear simultaneously.

#### 10F-3: Dead Player Cleanup

When a player dies:
- Clear their `auto_target_id` (they can't chase while dead)
- Also clear any OTHER player's auto-target if they were targeting the now-dead player
- This is partially handled in `match_tick()` death cleanup already, but needs explicit auto-target clearing

#### 10F-4: Auto-Target During Dungeon Exploration

In dungeon mode, the auto-target should work through doors:
- `generate_auto_target_action()` passes `door_tiles` to A* so paths can go through closed doors
- When the next step is a closed door tile → return INTERACT (same as AI door-opening behavior)
- This mirrors existing Phase 7D-1 door-aware A* behavior

#### 10F-5: Stale Auto-Target on Reconnect

If a player disconnects and reconnects:
- `auto_target_id` persists on `PlayerState` (it's an in-memory field)
- The reconnect payload should include `auto_target_id` so the client can restore the target indicator
- If the target died while disconnected, the next tick clears it automatically

#### 10F-6: Tests

**Extend:** `server/tests/test_auto_target.py`

| Test | Description |
|------|-------------|
| `test_auto_target_multi_attackers` | 3 units targeting same enemy → all get actions, all clear on death |
| `test_auto_target_dead_player_cleanup` | Dead player's auto-target is cleared |
| `test_auto_target_dungeon_doors` | Chase path through closed door → INTERACT action |
| `test_auto_target_ally_check` | Target somehow on same team → auto-target cleared |
| `test_auto_target_persists_across_ticks` | Auto-target stays set across multiple ticks while chasing |
| `test_auto_target_attack_every_tick` | Adjacent to target → ATTACK generated every tick until dead |

**Estimated scope:** ~30 lines edge case logic, ~120 lines tests

---

## Sub-Phase Summary

| Phase | Name | Scope | Dependencies |
|-------|------|-------|--------------|
| **10A** | Server Model & Auto-Target State | `PlayerState` field + match_manager helpers + tests | None |
| **10B** | Server-Side Chase Action Generation | Core tick logic + invalidation + party support + tests | 10A |
| **10C** | WebSocket Protocol & Client Messages | WS handlers + client state + docs | 10A, 10B |
| **10D** | Client Integration & Right-Click | Arena.jsx right-click changes + keyboard handlers | 10C |
| **10E** | Visual Feedback & HUD | Target reticle, HUD frame, combat log, cursor | 10D |
| **10F** | Edge Cases & Robustness | Death cleanup, dungeon doors, reconnect, multi-target | 10B |

### Recommended Implementation Order

```
10A  →  10B  →  10C  →  10D  →  10E
                  ↓
                10F (can be done in parallel with 10D/10E)
```

**10A → 10B** is the critical path — once chase action generation works server-side, the feature is functionally complete even before client changes (you could test by manually sending WS messages).

**10C → 10D** wires it up to the UI.

**10E** is polish (but important for player understanding).

**10F** hardens edge cases and can be tackled alongside 10D/10E.

---

## Estimated Total Scope

| Category | Lines |
|----------|-------|
| Server model + helpers | ~90 |
| Server tick logic | ~120 |
| Server WS handlers | ~60 |
| Client state + messages | ~40 |
| Client Arena.jsx changes | ~65 |
| Client renderer + HUD | ~115 |
| Tests | ~420 |
| Docs | ~20 |
| **Total** | **~930 lines** |

**Estimated sessions:** 2–3 focused sessions (10A+10B in session 1, 10C+10D in session 2, 10E+10F in session 3).

---

## What This Does NOT Change

- **Turn resolver** — No changes to melee/ranged resolution logic. Attacks still resolve the same way. Auto-target just ensures the attack action has fresh coordinates each tick.
- **AI behavior** — Enemy AI and party AI continue using their existing stance/decision systems. Auto-target only applies to human-controlled units (and controlled party members).
- **Action queue model** — The persistent queue still works exactly the same. Auto-target is a fallback that generates actions only when the queue is empty.
- **Combat math** — Damage, armor, equipment bonuses, buffs — all untouched.
- **Pathfinding** — Client A* and server A* unchanged. Auto-target reuses the existing server `_astar()`.

---

## Implementation Log

### 10A-1: Add `auto_target_id` to PlayerState — DONE
- Added `auto_target_id: str | None = None` field to `PlayerState` in `server/app/models/player.py`
- Placed after `ai_stance` field with descriptive Phase 10A comments
- Defaults to `None` (no auto-target), ephemeral in-match only, JSON-serializable

### 10A-2: Match Manager Helpers — DONE
- Added three helper functions to `server/app/core/match_manager.py` under a new `# ---------- Auto-Target (Phase 10A) ----------` section:
  - `set_auto_target(match_id, player_id, target_id)` — Validates player alive, target alive, different teams, not self. Clears action queue on success. Returns `True` or error string.
  - `clear_auto_target(match_id, player_id)` — Sets `auto_target_id` to `None`. No-op if not set or player doesn't exist.
  - `get_auto_target(match_id, player_id)` — Returns current `auto_target_id` or `None`.

### 10A-3: Tests — DONE
- Created `server/tests/test_auto_target.py` with 15 tests across 3 test classes:
  - **TestSetAutoTarget** (8 tests): valid target, clears queue, invalid ally, invalid dead, invalid self, nonexistent target, dead player, replaces existing
  - **TestClearAutoTarget** (3 tests): clear active, no-op when unset, nonexistent player
  - **TestGetAutoTarget** (4 tests): when set, when None, nonexistent player, after clear
- All 15 tests passing

### 10B-1: `generate_auto_target_action()` Function — DONE
- Added `generate_auto_target_action()` to `server/app/core/match_manager.py` under a new `# ---------- Auto-Target Chase Action Generation (Phase 10B) ----------` section
- Reuses `a_star()` and `_build_occupied_set()` from `ai_behavior.py` for pathfinding
- Decision logic: validate target → if adjacent ATTACK → if not adjacent A* path → if next step is closed door INTERACT → else MOVE → if unreachable clear auto-target
- Produces exactly one `PlayerAction` per tick (same granularity as AI behavior)
- Automatically clears `auto_target_id` when target dies, is on same team, or is unreachable

### 10B-2: Integration into `match_tick()` — DONE
- Added Step 3.5 in `server/app/services/websocket.py` `match_tick()` between popping queued actions and adding implicit waits
- Iterates all alive units; generates auto-target actions for human players and controlled party members whose queue is empty and who have `auto_target_id` set
- Players with queued actions are skipped — queued actions always take priority
- Added `generate_auto_target_action` and `clear_auto_target` to the import block from `match_manager`

### 10B-3: Auto-Target Invalidation — DONE
- **`queue_action()`**: Now clears `auto_target_id` when any new action is manually queued (new command overrides pursuit)
- **`batch_actions` WS handler**: Calls `clear_auto_target()` after clearing queue (new right-click path replaces pursuit)
- **`clear_queue` WS handler**: Calls `clear_auto_target()` when player explicitly cancels queue
- **Death cleanup in `match_tick()`**: After broadcasting turn results:
  - Clears dead player's own auto-target
  - Iterates all units and clears any auto-target pointing at the dead player
- **`generate_auto_target_action()` self-clears**: When target is dead, unreachable, or same team

### 10B-4: Party Member Support — DONE
- Step 3.5 in `match_tick()` checks both `unit_type == "human"` and `controlled_by` (party members)
- `generate_auto_target_action()` is unit-agnostic — works for any unit with `auto_target_id` set
- Party members can be auto-targeted via `set_auto_target()` using their unit_id

### 10B-5: Tests — DONE
- Extended `server/tests/test_auto_target.py` from 15 to 33 tests across 9 test classes:
  - **TestGenerateAutoTargetAction** (9 tests): attack when adjacent, diagonal adjacent, chase when distant, clears on target death, clears on unreachable, no action without auto-target, clears on same team, uses live position, dead player clears
  - **TestAutoTargetDoorInteraction** (1 test): path through closed door generates INTERACT
  - **TestAutoTargetInvalidation** (2 tests): queue_action clears auto-target, no override of queued actions
  - **TestAutoTargetPartyMember** (2 tests): party member chase, party member adjacent attack
  - **TestAutoTargetPersistence** (2 tests): persists across ticks, attack every tick when adjacent
  - **TestAutoTargetMultipleAttackers** (2 tests): both get actions, all clear on death
- All 33 tests passing, full suite 1433 tests passing with zero regressions

### 10C-1: Server WS Handler — `set_auto_target` Message — DONE
- Added `set_auto_target` and `get_auto_target` imports to `server/app/services/websocket.py`
- New WS handler for `set_auto_target` message:
  - Accepts `target_id` (required) and `unit_id` (optional, defaults to sender)
  - Validates party control when `unit_id` differs from sender (reuses `is_party_member()` check)
  - Calls `set_auto_target(match_id, unit_id, target_id)` from match_manager
  - On success: responds with `auto_target_set` containing `unit_id`, `target_id`, `target_username`
  - On failure: responds with `error` containing the validation error message

### 10C-2: Server WS Handler — `clear_auto_target` Message — DONE
- New WS handler for `clear_auto_target` message:
  - Accepts `unit_id` (optional, defaults to sender)
  - Validates party control for non-self units
  - Calls `clear_auto_target(match_id, unit_id)`
  - Responds with `auto_target_cleared` with `unit_id` and `reason: "cancelled"`

### 10C-3: Auto-Target Cleared Notification — DONE
- **Death cleanup**: When a target dies and other units had it auto-targeted, the server now sends `auto_target_cleared` with `reason: "target_died"` to the controlling player (human player or party member's `controlled_by`)
- **Unreachable/invalid**: Step 3.5 in `match_tick()` now tracks `prev_target` before calling `generate_auto_target_action()`. If the function clears the auto-target (returns None and `auto_target_id` is now None), sends `auto_target_cleared` with `reason: "target_died"` or `reason: "unreachable"` depending on target state
- Notifications are sent to the controlling player (`unit.controlled_by or pid`)

### 10C-4: Include Auto-Target in Turn Result — DONE
- Added `auto_targets` field to the per-player `turn_result` payload
- Built after party inventory section: iterates player + party members, collecting `{unit_id: auto_target_id}` for any unit with an active auto-target
- Only included in payload when at least one auto-target is active (avoids clutter)
- When no `auto_targets` field present in turn_result, client clears all auto-target state

### 10C-5: Client State — `GameStateContext` Updates — DONE
- Added to initial state:
  - `autoTargetId: null` — current player's auto-target enemy ID
  - `partyAutoTargets: {}` — `{unitId: targetId}` for party members
- Added reducer cases:
  - `AUTO_TARGET_SET` — sets `autoTargetId` (for self) or updates `partyAutoTargets` (for party member)
  - `AUTO_TARGET_CLEARED` — clears `autoTargetId` (for self) or removes entry from `partyAutoTargets` (for party member)
  - `CLEAR_AUTO_TARGET` — client-initiated clear of own `autoTargetId`
- `TURN_RESULT` reducer now syncs auto-target state from `auto_targets` field in payload
- `MATCH_START` reducer now resets `autoTargetId` and `partyAutoTargets`
- Added WS message routing in `App.jsx`:
  - `auto_target_set` → dispatches `AUTO_TARGET_SET`
  - `auto_target_cleared` → dispatches `AUTO_TARGET_CLEARED`

### 10C-6: Protocol Documentation — DONE
- Updated `docs/websocket-protocol.md` with new Phase 10C section:
  - Client → Server: `set_auto_target`, `clear_auto_target`
  - Server → Client: `auto_target_set`, `auto_target_cleared`, `turn_result.auto_targets`
  - Documented all fields, reason codes, and usage
- Bumped version from 5.0 to 6.0

### 10D-1: Right-Click on Enemy — Send Auto-Target — DONE
- Modified `handleContextMenu` in `client/src/components/Arena/Arena.jsx`
- After sending `batch_actions` for the initial A*-computed path, now also sends `set_auto_target` with the enemy's `player_id` and the acting unit's ID
- Uses `result.intent === 'attack'` to detect enemy right-clicks (from `generateSmartActions` return value)
- Supports party member control: uses `activeUnitId` when `isControllingAlly` is true
- Added `autoTargetId` to the `gameState` destructuring for use by other 10D handlers

### 10D-2: Right-Click Elsewhere — Clear Auto-Target — DONE
- When `result.intent` is NOT `'attack'` (move, interact, loot), sends `clear_auto_target` to server and dispatches `CLEAR_AUTO_TARGET` to client state
- This is belt-and-suspenders: `batch_actions` already clears auto-target server-side (10B-3), but the explicit clear updates client state immediately and avoids any sync issues

### 10D-3: Manual Actions Clear Auto-Target — DONE
- Added auto-target clearing check at the top of `handleCanvasClick` (before any action mode processing)
- When `autoTargetId` is set and the player clicks in any action mode (move, attack, ranged, interact, skill), dispatches `CLEAR_AUTO_TARGET`
- Server-side `queue_action()` already clears auto-target (10B-3), so this is the client-side sync
- Added `autoTargetId` to `handleCanvasClick` dependency array

### 10D-4: Escape Key Clears Auto-Target — DONE
- Added new `useEffect` in `Arena.jsx` with `handleEscapeKey` listener for the Escape key
- On Escape:
  1. Sends `clear_queue` to server (with `unit_id` when controlling an ally)
  2. Sends `clear_auto_target` to server (with `unit_id` when controlling an ally)
  3. Dispatches `SET_ACTION_MODE(null)` to clear any active action mode
  4. Dispatches `CLEAR_AUTO_TARGET` to clear client auto-target state
  5. Dispatches `QUEUE_CLEARED` to update client queue display
- Ignores key events when typing in input/textarea fields
- Only active during `matchStatus === 'in_progress'`

### 10D-5: Group Right-Click Auto-Target — DONE
- Extended the group right-click handler in `handleContextMenu` (Phase 7B-3 section)
- After sending `group_batch_actions`, checks if the target tile has an enemy occupant
- If enemy: sends `set_auto_target` for each unit in `selectedUnitIds`, targeting the enemy's `pid`
- If not enemy (movement/interact): sends `clear_auto_target` for each selected unit to cancel any existing pursuits
- Uses `occupiedMap` to detect enemy presence and `myTeam` for team comparison

### 10E-1: Target Indicator on Canvas — DONE
- Added `drawTargetReticle()` function to `client/src/canvas/ArenaRenderer.js`
- Renders pulsing red bracket corners `[ ]` around auto-targeted enemy tiles
- Four bracket arms drawn at each corner with `Math.sin(Date.now() / 350)` pulse animation
- Includes subtle outer glow ring for additional visibility
- Uses `ctx.save()`/`ctx.restore()` to avoid leaking state
- Added `autoTargetId` and `partyAutoTargets` parameters to `renderFrame()` signature
- Collects all active auto-targets (player + party members) into a Set for deduplication
- Only renders reticle for targets that are alive and within the player's FOV (`visibleTiles` check)
- Updated `Arena.jsx` to pass `autoTargetId` and `partyAutoTargets` to `renderFrame()` (added to both call and dependency array)
- Added `partyAutoTargets` to the `gameState` destructuring in `Arena.jsx`

### 10E-2: HUD Target Display — DONE
- Extended `client/src/components/HUD/HUD.jsx` to show an auto-target frame when pursuing an enemy
- Added `autoTargetId` and `activeUnitId` to gameState destructuring
- Computes adjacency between active unit and target to determine status text:
  - "Attacking!" when adjacent (dx ≤ 1 && dy ≤ 1, Manhattan distance > 0)
  - "Pursuing..." when not adjacent (chasing)
- Target frame displays:
  - Header with ⚔ icon and "Targeting:" label
  - Target username
  - HP bar (gradient red fill with smooth width transition)
  - HP text (current / max)
  - Status text ("Pursuing..." in gold, "Attacking!" in red with pulsing animation)
- HUD now renders when `hasAutoTarget` is true (in addition to existing cooldown/equipment/queue checks)
- Added CSS styles in `client/src/styles/main.css`:
  - `.hud-auto-target` container with red-tinted background and border
  - HP bar with gradient fill and smooth transition
  - Status text with color coding and `pulse-text` keyframe animation for "Attacking!" state

### 10E-3: Combat Log Messages — DONE
- Added combat log dispatches in `client/src/App.jsx` when auto-target WS messages are received:
  - `auto_target_set`: Logs `"⚔ Auto-targeting: {target_username}"`
  - `auto_target_cleared` with `reason: "target_died"`: Logs `"⚔ Target eliminated"`
  - `auto_target_cleared` with `reason: "unreachable"`: Logs `"⚔ Target lost — unreachable"`
  - `auto_target_cleared` with `reason: "cancelled"`: Logs `"⚔ Pursuit cancelled"`
- Uses existing `ADD_COMBAT_LOG` dispatch pattern with `type: 'system'`
- Messages only fire for server-acknowledged events (not client-side state clears)

### 10E-4: Cursor Feedback — DONE
- Updated canvas cursor logic in `client/src/components/Arena/Arena.jsx`
- When no action mode is active: cursor changes to `crosshair` when hovering over an enemy tile
- Enemy detection uses `occupiedMap` lookup with team comparison (`occupant.team !== myTeam`)
- Only active when player is alive (`isAlive` check)
- Falls through to `default` cursor for friendly units, empty tiles, and obstacles
- Existing `actionMode ? 'crosshair'` behavior preserved as top priority

