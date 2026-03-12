# Bug Log

## Bug #10 — "Failed - No valid target" Target Desync (Entity-Based Targeting Fix)

**Date:** June 2025
**Phase:** Cross-phase (affects combat core)
**Severity:** High — causes attacks & skills to consistently miss moving targets, skeleton archers can kite indefinitely
**Status:** Fixed

### Symptoms

1. Melee attacks, ranged attacks, and skills frequently report "Failed - No valid target" or "no enemy at target" in the combat log
2. Skeleton archers kite for an extremely long time because attacks fail repeatedly when they move
3. Heals miss allies who move before the heal resolves
4. The issue worsens with kiting AI behaviors (ranged enemies that move away each turn)

### Root Cause

The turn resolution order is:

```
Phase 1:   Movement
Phase 1.9: Skills
Phase 2:   Ranged attacks
Phase 3:   Melee attacks
```

All targeting stored the target's **tile position** (`target_x`, `target_y`) at action queue time (AI decision or player click). Movement resolves **first** in Phase 1, so by the time attacks/skills resolve, the target has moved off the targeted tile. The resolver checks the targeted tile for an occupant and finds nobody → "no valid target".

- Skills (Phase 1.9): No tracking at all
- Ranged attacks (Phase 2): No tracking
- Melee attacks (Phase 3): Partial fix via `pre_move_occupants` — only works if target remained adjacent

### Solution: Hybrid Entity + Tile Targeting (Option D)

Added `target_id` field to `PlayerAction` for **entity-based targeting**. Actions that target a specific entity (attacks, heals, buffs, DoTs, etc.) now include `target_id` — the `player_id` of the intended target. At resolution time, the resolver looks up the target by ID to find their **current position**, then validates range/LOS against that position.

Tile-based targeting (`target_x`/`target_y` without `target_id`) is preserved as a fallback for:
- Future AoE/ground-targeted skills
- Teleport skills (e.g., Shadow Step)
- Backward compatibility

### Files Modified

**Server — Model:**
- `server/app/models/actions.py` — Added `target_id: str | None = None` to `PlayerAction`

**Server — Resolvers (consumers):**
- `server/app/core/turn_resolver.py` — Added `_resolve_entity_target()` helper; updated `_resolve_ranged()` and `_resolve_melee()` to look up target by entity ID first
- `server/app/core/skills.py` — Added `_resolve_skill_entity_target()` helper; updated `resolve_skill_action()` dispatcher and all 7 entity-targeted skill handlers: `resolve_heal`, `resolve_multi_hit`, `resolve_ranged_skill`, `resolve_buff`, `resolve_dot`, `resolve_hot`, `resolve_holy_damage`

**Server — Action creators (producers):**
- `server/app/core/ai_behavior.py` — Added `target_id=target.player_id` to all 10 ATTACK/RANGED_ATTACK PlayerAction creations
- `server/app/core/ai_skills.py` — Added `target_id` parameter to `_try_skill()` builder; updated all 18 entity-targeted skill call sites
- `server/app/core/auto_target.py` — Added `target_id` to SKILL and ATTACK action creations
- `server/app/services/message_handlers.py` — Added `target_id` passthrough from WebSocket messages in both `handle_queue_action` and `handle_batch_actions`

**Client — Action senders:**
- `client/src/hooks/useCanvasInput.js` — Added `target_id: occupant.pid` to attack, ranged_attack, and skill action messages
- `client/src/components/BottomBar/BottomBar.jsx` — Added `target_id` to self-target and target-first skill messages
- `client/src/canvas/pathfinding.js` — Added `target_id: occupant.pid` to smart right-click attack actions

**Tests:**
- `server/tests/test_target_desync.py` — 15 tests total: 9 original bug reproduction tests + 6 new fix verification tests. All passing. 1501 total project tests pass with 0 regressions.

### Design Notes

- Entity lookup uses `target_id` first; falls back to tile-based if not provided
- Range and LOS are **re-validated** against the target's current position after entity lookup
- If the target moved out of range (even with entity targeting), the attack correctly fails
- Self-buff skills (war_cry, ward) don't need `target_id` since the resolver has self-fallback logic
- Tile-targeted skills (shadow_step, divine_sense) don't use `target_id`

---

## Bug #9 — Dungeon Entry Stuck in Lobby (Phase 4E Race Condition)

**Date:** February 13, 2026
**Phase:** 4E-3 (Town Hub Client UI)
**Severity:** Critical — completely blocks dungeon entry
**Status:** Fixed

### Symptoms

1. Player goes to Town Hub → hires hero → selects hero for dungeon
2. Player is transferred to the lobby/waiting room
3. No indication of hero selected for the dungeon is shown
4. Player clicks "Ready Up" → button goes greyed out and nothing happens
5. Player is stuck in the lobby permanently

### Root Causes

Three compounding issues created this bug:

#### Root Cause #1 — `hero_select` WebSocket message silently dropped (race condition)

When the player clicks "Enter Dungeon" from the Town Hub, `App.jsx` dispatches `JOIN_MATCH` (setting `matchId`/`playerId`) and `SELECT_HERO`, then transitions to the waiting screen. React re-renders and the `useWebSocket` hook begins opening a new WebSocket connection — but this is **asynchronous** (takes ~50-200ms for the handshake).

Meanwhile, `WaitingRoom.jsx` mounts and immediately fires a `useEffect` that tries to send the `hero_select` message. But `sendAction` in `useWebSocket.js` silently drops the message because the WebSocket is still in `CONNECTING` state:

```js
// useWebSocket.js — old code
const sendAction = useCallback((action) => {
  if (wsRef.current?.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify(action));
  }
  // ← no else, no retry, no queue — message lost forever
}, []);
```

The effect dependencies (`selectedHeroId`, `sendAction`) never change again, so the effect never re-fires. The server never receives `hero_select`.

**Files involved:**
- `client/src/components/WaitingRoom/WaitingRoom.jsx` (lines 47-51)
- `client/src/hooks/useWebSocket.js` (lines 51-55)

#### Root Cause #2 — Server validation blocks match start without feedback

When the player clicks "Ready Up", the server's ready handler calls `validate_dungeon_hero_selections()`. Since `hero_select` was never received, the server's `_hero_selections` dict is empty. Validation fails with `"username has not selected a hero"`.

The server then:
1. Broadcasts an `error` message
2. Un-readies the player server-side via `set_player_ready(match_id, player_id, False)`
3. Does **not** broadcast a `player_ready` update reflecting the un-ready state

**Files involved:**
- `server/app/services/websocket.py` (lines 500-512)
- `server/app/core/match_manager.py` (lines 1391-1413)

#### Root Cause #3 — Error invisible + button permanently disabled

Three UI issues compound to make the player completely stuck:

- **Error not shown:** The `error` WS message is only `console.error`'d in `App.jsx` — never displayed in the UI
- **Button stays greyed:** `WaitingRoom.jsx` sets `setIsReady(true)` optimistically before the server responds. The server un-readies the player, but the local `isReady` React state is never set back to `false`
- **No un-ready broadcast:** The server calls `set_player_ready(false)` but never sends a WebSocket update to the client

**Files involved:**
- `client/src/App.jsx` (lines 108-110)
- `client/src/components/WaitingRoom/WaitingRoom.jsx` (lines 63-66)

### Fixes Applied

#### Fix 1 — Message queue in `useWebSocket.js`

Added a `pendingQueueRef` that buffers messages sent while the WebSocket is still connecting. On `ws.onopen`, all pending messages are flushed. Also exposed a `wsReady` boolean state so consuming components know when the connection is live.

```js
// New behavior: queue messages while connecting, flush on open
const sendAction = useCallback((action) => {
  if (wsRef.current?.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify(action));
  } else {
    pendingQueueRef.current.push(action);
  }
}, []);
```

#### Fix 2 — `hero_select` effect depends on `wsReady`

The `WaitingRoom.jsx` `useEffect` for auto-sending `hero_select` now depends on `wsReady`, making it re-fire once the WebSocket connection is actually established (belt-and-suspenders alongside the queue).

#### Fix 3 — Server broadcasts `player_ready` after un-readying

In `websocket.py`, when hero validation fails, the server now: (1) un-readies the player first, (2) broadcasts the error, (3) broadcasts an updated `player_ready` message with the corrected lobby state. This ensures the client receives the un-ready status.

#### Fix 4 — Error messages shown in UI

`App.jsx` now dispatches `SET_LOBBY_ERROR` on receiving an `error` WS message. `GameStateContext.jsx` gained a `lobbyError` state field and `SET_LOBBY_ERROR` reducer. `WaitingRoom.jsx` renders an error banner when `lobbyError` is set (dismissible with ✕ button).

#### Fix 5 — `isReady` state resets on server rejection

`WaitingRoom.jsx` gained a `useEffect` that monitors the server's `is_ready` state for the current player. If the server un-readies the player (via `PLAYER_READY` broadcast), the local `isReady` state resets and the button becomes clickable again.

### Files Modified

| File | Changes |
| ---- | ------- |
| `client/src/hooks/useWebSocket.js` | Message queue, `wsReady` state, flush on open |
| `client/src/components/WaitingRoom/WaitingRoom.jsx` | `wsReady` prop, hero_select depends on wsReady, isReady reset effect, error banner |
| `client/src/App.jsx` | `SET_LOBBY_ERROR` dispatch on error WS message, pass `wsReady` to WaitingRoom |
| `client/src/context/GameStateContext.jsx` | `lobbyError` initial state, `SET_LOBBY_ERROR` reducer, clear error on `PLAYER_READY` |
| `server/app/services/websocket.py` | Un-ready before error broadcast, second `player_ready` broadcast after un-ready |
| `client/src/styles/main.css` | `.lobby-error-banner` styles |

### Regression Bug — `players` not defined

During the fix, the `isReady` reset `useEffect` referenced a `players` variable that was declared later in the component body (line 106), causing a runtime `ReferenceError` that prevented the WaitingRoom from rendering at all. Fixed by extracting `const lobbyPlayers = gameState.lobbyPlayers || {}` above the effect and referencing that instead.

### Test Results

- **556 server tests pass** (0 failures, 0 regressions)
- **Client builds cleanly** (0 errors)

---

## Bug #10 — Doors Can Only Open, Never Close

**Date:** February 13, 2026
**Phase:** 4B-2 (identified), fixed pre-4F
**Severity:** Medium
**Status:** Fixed

### Symptoms

Interacting with an open door does nothing. Doors are permanently open once toggled. The player cannot close doors to block enemy movement or line of sight.

### Root Cause

The turn resolver's Phase 1.5 interact logic only handled `"closed"` → `"open"` transitions. There was no code path for closing an already-open door. The client also only showed interact highlights for closed doors and only enabled the Interact button when adjacent to a closed door.

### Fixes Applied

#### Fix 1 — Turn resolver toggle logic (`server/app/core/turn_resolver.py`)

Phase 1.5 "Resolve Interactions" now checks the current door state and toggles:
- **Closed → Open:** Removes tile from obstacles, sets state to `"open"`, appends `door_changes` with `state: "open"`
- **Open → Closed:** Adds tile back to obstacles, sets state to `"closed"`, appends `door_changes` with `state: "closed"`

#### Fix 2 — Client interact highlights (`client/src/components/Arena/Arena.jsx`)

`interactHighlights` useMemo now iterates ALL `doorStates` entries (both `"closed"` and `"open"`) instead of only checking 4 cardinal directions for closed doors.

#### Fix 3 — ActionBar button (`client/src/components/ActionBar/ActionBar.jsx`)

`hasAdjacentDoor` renamed to `hasDoors` — now checks `Object.keys(doorStates).length > 0` instead of requiring cardinal adjacency. Button title updated to clarify toggle behavior.

### Files Modified

| File | Changes |
| ---- | ------- |
| `server/app/core/turn_resolver.py` | Phase 1.5 toggle logic for open→closed |
| `client/src/components/Arena/Arena.jsx` | interactHighlights shows all doors |
| `client/src/components/ActionBar/ActionBar.jsx` | Button enabled when any doors exist |
| `server/tests/test_dungeon_doors.py` | `test_fail_already_open` → `test_toggle_close_open_door` |

### Test Results

- **559 server tests pass** (3 net new from test restructuring, 0 regressions)
- **Client builds cleanly** (0 errors)

---

## Bug #11 — Interact Button Only Enabled When Adjacent to Door

**Date:** February 13, 2026
**Phase:** 4B-2 (identified), fixed pre-4F
**Severity:** Medium
**Status:** Fixed

### Symptoms

The 🚪 Interact button is grayed out unless the player is cardinally adjacent to a closed door. Players cannot queue an interact action on a distant door to execute later when they walk up to it.

### Root Cause

The ActionBar computed `hasAdjacentDoor` by checking the 4 cardinal tiles around the player for closed doors. The Arena click handler in interact mode also only highlighted adjacent closed doors. This meant the interact action couldn't be queued from a distance, despite the server already correctly validating adjacency at resolution time.

### Fix Applied

Decoupled "can queue" (client) from "can execute" (server):
- **ActionBar:** `hasDoors` checks `Object.keys(doorStates).length > 0` — button enabled whenever any door exists on the map
- **Arena:** Interact highlights now show ALL doors (open and closed), not just adjacent ones
- **Server:** No changes needed — `turn_resolver.py` already correctly rejects non-adjacent interactions

### Files Modified

| File | Changes |
| ---- | ------- |
| `client/src/components/ActionBar/ActionBar.jsx` | Removed adjacency check for button enable |
| `client/src/components/Arena/Arena.jsx` | Interact highlights show all visible doors |

### Test Results

- Same as Bug #10 (fixed in same session)

---

## Bug #12 — Selected Hero Joins as Human Player Instead of AI Ally

**Date:** February 13, 2026
**Phase:** 4E-2 (identified), fixed pre-4F
**Severity:** High — hero stats overwrite human player, breaking the designed flow
**Status:** Fixed

### Symptoms

When a player selects a hero for a dungeon match, the hero's stats/equipment/inventory are copied directly onto the human player's `PlayerState`. The hero should instead spawn as a separate AI ally unit on the player's team, fighting alongside the human player.

### Root Cause

`_load_heroes_at_match_start()` in `match_manager.py` was designed to copy hero data onto the human `PlayerState`. The original 4E-2 implementation treated hero selection as "play as this hero" rather than "bring this hero as an ally."

### Fixes Applied

#### Fix 1 — Hero spawns as AI ally on `select_hero()` (`server/app/core/match_manager.py`)

Added `_hero_ally_map` tracking dict (`match_id → {ai_unit_id → owner_username}`). When `select_hero()` is called for a dungeon match:
1. Removes any previous hero ally via `_remove_hero_ally()`
2. Calls `_spawn_hero_ally()` which creates an AI unit with the hero's name, class, stats, equipment, and inventory on team `"a"`
3. Applies equipment bonuses to the AI ally
4. Registers the ally in `_hero_ally_map` for owner tracking

#### Fix 2 — `_load_heroes_at_match_start()` short-circuits

Now returns early if `_hero_ally_map` has entries for the match — hero stats are already loaded onto the AI ally at selection time.

#### Fix 3 — Permadeath uses `_hero_ally_map` for owner lookup

`handle_hero_permadeath()` updated to look up the owner username from `_hero_ally_map` when the dead unit is an AI hero ally (not a human player).

#### Fix 4 — Post-match persistence iterates all units

`_persist_post_match()` now iterates all units with a `hero_id` (not just human players), using `_hero_ally_map` for owner username lookup to save loot/gold/stats back to the correct player profile.

#### Fix 5 — `match_end` payload includes AI hero allies

`get_match_end_payload()` updated to include AI hero ally outcomes keyed by their unit ID.

#### Fix 6 — WebSocket handler simplified

Removed `select_class()` call from `hero_select` handler — the human player keeps their own class; the hero's class is only on the AI ally.

### Files Modified

| File | Changes |
| ---- | ------- |
| `server/app/core/match_manager.py` | `_hero_ally_map`, `_spawn_hero_ally()`, `_remove_hero_ally()`, updated `select_hero()`, `_load_heroes_at_match_start()`, `handle_hero_permadeath()`, `_persist_post_match()`, `get_match_end_payload()`, `create_match()`, `remove_match()` |
| `server/app/services/websocket.py` | Removed `select_class()` from `hero_select` handler |
| `server/tests/test_hero_persistence.py` | Rewrote `TestHeroLoadingAtMatchStart`, `TestPermadeath`, `TestPostMatchPersistence`, `TestMatchEndPayload` for hero-as-ally flow |

### Test Results

- **559 server tests pass** (0 regressions, tests rewritten for new flow)
- **Client builds cleanly** (0 errors)
