# Phase 1 Design Document — Build Plan

## Purpose

This document breaks the Phase 1 Arena Prototype into **10 sequential build sections**. Each section is a vertical slice — meaning it produces something testable before moving on. Sections are ordered by dependency: you can't build combat without a turn system, and you can't build a turn system without a server.

**Rule: No section is "done" until its acceptance criteria pass.**

## Design Philosophy: Isleward-Style Queue Model

**Target Gameplay Feel:** Tactical but alive — like Isleward.

Players can queue multiple actions ahead (up to 10), see path previews, and watch them execute in fast ticks (2-5 seconds). The world feels responsive and dynamic, not traditional turn-based-slow, but maintains tactical depth through action queuing and positioning.

**Current Prototype Status:** Sections 1-8 complete. Persistent queue model (up to 10 actions, tick pops first) implemented in Section 7. Next: Section 9 (Match Flow End-to-End) to validate full gameplay loop.

## Platform Notes

**Windows Development Environment:**
- Use `python -m uvicorn` instead of `uvicorn` directly to ensure proper module resolution
- PowerShell's `curl` is an alias for `Invoke-WebRequest`; use `Invoke-WebRequest -UseBasicParsing` for API testing
- When chaining commands in PowerShell, use semicolons (`;`), not `&&`
- Absolute paths are recommended when changing directories to avoid navigation issues

---

## Build Order Overview

```
Section 1: Dev Environment & Project Setup
    │
    ├── Section 2: Server Foundation
    │       │
    │       ├── Section 3: WebSocket Infrastructure
    │       │       │
    │       │       └── Section 5: Lobby System (REST + WS)
    │       │               │
    │       │               └── Section 6: Turn System & Action Queue
    │       │                       │
    │       │                       └── Section 7: Combat Engine Integration
    │       │                               │
    │       │                               └── Section 9: Match Flow End-to-End
    │       │                                       │
    │       │                                       └── Section 10: Polish & Playtesting
    │       │
    ├── Section 4: Frontend Foundation
    │       │
    │       └── Section 8: Game UI (HUD, Combat Log, Actions)
    │
    └── (Sections 4+8 merge with 5+6+7 at Section 9)
```

**Parallel tracks:** Sections 2-3 (backend) and Section 4 (frontend) can be built in parallel. They converge at Section 5 (Lobby) where frontend connects to backend.

---

## Section 1: Dev Environment & Project Setup

**Goal:** Everyone can clone the repo and run both servers with one command each.

### Tasks
- [ ] Initialize Git repository ** WE WILL SET UP GIT REPO AT A LATER DATE **
- [x] Verify Python 3.11+ installed ✅ (v3.11.9)
- [x] Verify Node.js 18+ installed ✅ (v22.19.0)
- [x] Install Redis (or confirm in-memory fallback works) ✅ (in-memory fallback working)
- [x] Install server dependencies: `pip install -r requirements.txt` ✅
- [x] Install client dependencies: `cd client && npm install` ✅
- [x] Verify server starts: `uvicorn app.main:app --reload --port 8000` ✅
- [x] Verify client starts: `npm run dev` ✅
- [x] Confirm `/health` endpoint returns `{"status": "ok"}` ✅
- [x] Confirm Vite proxy forwards `/api/*` to backend ✅

### Files Involved
- [server/requirements.txt](../server/requirements.txt)
- [client/package.json](../client/package.json)
- [client/vite.config.js](../client/vite.config.js)
- [server/app/main.py](../server/app/main.py)

### Acceptance Criteria
- [x] `uvicorn app.main:app --reload` starts without errors ✅
- [x] `npm run dev` starts Vite on port 5173 ✅
- [x] Browser at `http://localhost:5173` shows the React app ✅
- [x] `http://localhost:5173/api/lobby/matches` returns `[]` (proxied to backend) ✅

### Completion Notes
- **Date Completed:** February 11, 2026
- **Python Version:** 3.11.9
- **Node.js Version:** v22.19.0
- **Redis Status:** Not installed; using in-memory fallback (intentional for Phase 1)
- **Server Running:** Background terminal, port 8000
- **Client Running:** Background terminal, port 5173
- **Important:** Use `python -m uvicorn` instead of just `uvicorn` on Windows to ensure proper module resolution

**Quick Reference Commands:**
```powershell
# Start backend (from Arena/server directory)
cd "c:\Users\xjobi\OneDrive\Desktop\MMO PROJECT\Arena\server"
python -m uvicorn app.main:app --reload --port 8000

# Start frontend (from Arena/client directory)
cd "c:\Users\xjobi\OneDrive\Desktop\MMO PROJECT\Arena\client"
npm run dev

# Test endpoints
Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing | Select-Object -ExpandProperty Content
Invoke-WebRequest -Uri http://localhost:5173/api/lobby/matches -UseBasicParsing | Select-Object -ExpandProperty Content

# View running servers
# Backend: http://localhost:8000/docs (Swagger UI)
# Frontend: http://localhost:5173 (React App)
```

**Currently Running Services:**
- ✅ Backend server: Running on port 8000 (auto-reload enabled)
- ✅ Frontend dev server: Running on port 5173 (Vite HMR enabled)
- ⚠️ Redis: Not installed (using in-memory fallback)

---

## Section 2: Server Foundation

**Goal:** FastAPI server with Redis connection, config system, and basic route structure.

**Depends on:** Section 1

### Tasks
- [x] Verify `app/config.py` loads settings with correct defaults ✅
- [x] Verify Redis connection (connect + graceful fallback if unavailable) ✅
- [x] Verify APScheduler starts and shuts down cleanly in lifespan ✅
- [x] Verify lobby routes mount at `/api/lobby/*` ✅
- [x] Verify match routes mount at `/api/match/*` ✅
- [x] Test Pydantic models serialize/deserialize correctly ✅
- [x] Run existing tests: `pytest tests/ -v` ✅

### Key Implementation Details
- `config.py` reads `ARENA_` prefixed env vars or `.env` file
- Redis is optional for dev — `RedisManager` logs warning and continues if Redis is down
- All game settings (tick rate, grid size, player limits) come from `config.py`

### Files Involved
- [server/app/main.py](../server/app/main.py) — Lifespan, middleware, route registration
- [server/app/config.py](../server/app/config.py) — Settings with defaults
- [server/app/services/redis_client.py](../server/app/services/redis_client.py)
- [server/app/services/scheduler.py](../server/app/services/scheduler.py)
- [server/app/models/](../server/app/models/) — All Pydantic schemas

### Acceptance Criteria
- [x] Server starts, logs `[Arena] Server started — tick rate: 10.0s` ✅
- [x] `GET /health` returns `{"status": "ok", "version": "0.1.0"}` ✅
- [x] `GET /docs` shows FastAPI auto-generated Swagger UI ✅
- [x] `pytest tests/ -v` — all existing tests pass ✅ (24/24 passed)
- [x] Changing `ARENA_TICK_RATE_SECONDS=5` in env changes tick rate ✅

### Completion Notes
- **Date Completed:** February 11, 2026
- **Config Verification:** All 10 settings load correct defaults; `ARENA_` env prefix overrides work
- **Redis Status:** Graceful fallback confirmed — logs `[Redis] Connection failed (...) — running without Redis (in-memory only)` and continues
- **APScheduler:** Starts on lifespan startup, shuts down cleanly on shutdown (confirmed via logs)
- **Route Mounting:** `/api/lobby/matches` returns `[]`; `/api/match/{id}` returns 404 for unknown IDs (correct)
- **Swagger UI:** Available at `http://localhost:8000/docs` (status 200)
- **Pydantic Models:** All 7 models tested (PlayerState, MatchState, MatchSummary, PlayerAction, ActionResult, TurnResult, request models) — serialize/deserialize round-trips pass
- **Tests:** 24/24 passed in 0.22s (test_combat: 13, test_match: 5, test_turn_resolver: 6)

---

## Section 3: WebSocket Infrastructure

**Goal:** Players can connect via WebSocket, server tracks connections, and messages flow both directions.

**Depends on:** Section 2

### Tasks
- [x] Verify `ConnectionManager` tracks connections by match_id + player_id ✅
- [x] Implement WebSocket endpoint at `/ws/{match_id}/{player_id}` ✅
- [x] Handle connection open → add to manager ✅
- [x] Handle connection close → remove from manager, broadcast disconnect ✅
- [x] Client sends JSON → server receives and echoes/acks ✅
- [x] Server broadcasts to all players in a match ✅
- [x] Handle malformed messages gracefully (don't crash) ✅
- [x] Write a manual test: open two browser tabs, both connect to same match_id ✅

### Key Implementation Details
- WebSocket uses native FastAPI WebSocket (not socket.io) for simplicity
- `ConnectionManager` is a singleton — one instance for the whole server
- Each message has a `type` field for routing (see [websocket-protocol.md](websocket-protocol.md))
- Connection drops are caught via `WebSocketDisconnect` exception

### Files Involved
- [server/app/services/websocket.py](../server/app/services/websocket.py)
- [server/tests/test_websocket.py](../server/tests/test_websocket.py) — Automated WS tests
- [server/tests/ws_test.html](../server/tests/ws_test.html) — Manual browser test page

### Acceptance Criteria
- [x] Two browser tabs connect to `ws://localhost:8000/ws/test123/player1` and `ws://localhost:8000/ws/test123/player2` ✅
- [x] Sending `{"type": "ready"}` from one tab → the other tab receives `{"type": "player_ready", "player_id": "player1"}` ✅
- [x] Closing one tab → the other receives `{"type": "player_disconnected", ...}` ✅
- [x] Server logs connections and disconnections ✅

### Completion Notes
- **Date Completed:** February 11, 2026
- **Automated Tests:** 10 new tests in `test_websocket.py` (5 connection tests + 5 malformed message tests) — all pass
- **Total Test Suite:** 34/34 passing
- **Malformed Message Handling:** Invalid JSON, missing `type` field, unknown `action_type`, unknown message types all return `{"type": "error", "message": "..."}` without crashing
- **Manual Test Page:** `server/tests/ws_test.html` — open directly in browser, supports connect/disconnect, ready, move, attack, wait, and malformed message testing
- **Broadcast:** Added `exclude` parameter to `broadcast_to_match()` for future use
- **Connection Safety:** Added `WebSocketState.CONNECTED` check before sending to prevent stale connection errors

---

## Section 4: Frontend Foundation

**Goal:** React app renders a 15x15 canvas grid with placeholder players. No server connection yet.

**Depends on:** Section 1

### Tasks
- [x] Verify React app renders with dark theme styling ✅
- [x] Implement `ArenaRenderer.js` — draw 15x15 grid on canvas ✅
- [x] Draw obstacle tiles (darker squares) at positions from map config ✅
- [x] Draw player tokens (colored circles with username labels) ✅
- [x] Draw at least 2 hardcoded test players on the grid ✅
- [x] Canvas scales properly (15 × 40px = 600px square) ✅
- [x] Implement screen routing: lobby view ↔ arena view ✅
- [x] `GameStateContext` reducer handles basic state transitions ✅

### Key Implementation Details
- Canvas uses 40px tile size — grid is 600×600 pixels
- Players are colored circles; each player gets a unique color (8-color palette)
- Obstacles from `arena_classic.json` are drawn as dark filled squares
- No server data yet — use hardcoded test state for rendering validation
- `renderFrame()` orchestrates all canvas drawing in correct layer order

### Files Involved
- [client/src/App.jsx](../client/src/App.jsx)
- [client/src/canvas/ArenaRenderer.js](../client/src/canvas/ArenaRenderer.js)
- [client/src/components/Arena/Arena.jsx](../client/src/components/Arena/Arena.jsx)
- [client/src/components/Lobby/Lobby.jsx](../client/src/components/Lobby/Lobby.jsx)
- [client/src/context/GameStateContext.jsx](../client/src/context/GameStateContext.jsx)
- [client/src/styles/main.css](../client/src/styles/main.css)

### Acceptance Criteria
- [x] Browser shows a 600x600 dark canvas with a 15x15 grid ✅
- [x] 9 obstacle tiles visible (center cross + 4 pillars per map config) ✅
- [x] 2 test player tokens visible at spawn positions with labels ✅
- [x] Lobby screen shows "Create Match" and "Join Match" buttons ✅
- [x] Clicking between lobby/arena screens works ✅

### Completion Notes
- **Date Completed:** February 11, 2026
- **Canvas Features:** Full `renderFrame()` function draws background, grid lines, obstacles, and players with HP bars + username labels in correct z-order
- **Player Rendering:** Colored circles with white outline, bold username label above, color-coded HP bar below (green > 50%, yellow > 25%, red otherwise); dead players shown as X markers
- **Test Players:** Alice (1,1) at 100 HP and Bob (13,1) at 75 HP rendered as hardcoded test data
- **Lobby Flow:** Username entry screen → lobby with Create/Join/Preview buttons → arena view; "Leave Match" returns to lobby
- **GameState Reducer:** Handles SET_USERNAME, JOIN_MATCH, UPDATE_PLAYERS, MATCH_START, TURN_RESULT, QUEUE_ACTION, CLEAR_ACTION, MATCH_END, LEAVE_MATCH
- **Styles:** Dark theme (#1a1a2e background), styled HUD panel, combat log, player list with dead state, disabled button styling
- **Vite Build:** Clean — no errors or warnings

---

## Section 5: Lobby System

**Goal:** Players can create a match, join it by ID, see each other in the lobby, and ready up. Frontend talks to backend.

**Depends on:** Sections 2, 3, 4

### Tasks

**Backend:**
- [x] `POST /api/lobby/create` — creates match, returns match_id + player_id ✅
- [x] `GET /api/lobby/matches` — lists available matches ✅
- [x] `POST /api/lobby/join/{match_id}` — joins match, returns player_id + spawn position ✅
- [x] `GET /api/match/{match_id}` — returns full match state + player list ✅
- [x] `POST /api/match/{match_id}/ready` — toggles ready, returns whether all ready ✅
- [x] WebSocket: broadcast `player_joined` when someone joins ✅
- [x] WebSocket: broadcast `player_ready` when someone readies ✅
- [x] WebSocket: broadcast `match_start` when all players ready ✅

**Frontend:**
- [x] Username input screen (text field + "Enter Arena" button) ✅
- [x] Lobby: fetch and display match list from `GET /api/lobby/matches` ✅
- [x] "Create Match" button → calls POST create → navigates to waiting room ✅
- [x] "Join Match" button → select from list → calls POST join → waiting room ✅
- [x] Waiting room: show player list, ready button, match ID ✅
- [x] Connect WebSocket when entering waiting room ✅
- [x] Update player list in real time when others join/ready ✅
- [x] Auto-transition to arena when `match_start` message received ✅

### Files Involved
- [server/app/routes/lobby.py](../server/app/routes/lobby.py)
- [server/app/routes/match.py](../server/app/routes/match.py)
- [server/app/core/match_manager.py](../server/app/core/match_manager.py)
- [server/app/services/websocket.py](../server/app/services/websocket.py)
- [client/src/components/Lobby/Lobby.jsx](../client/src/components/Lobby/Lobby.jsx)
- [client/src/components/WaitingRoom/WaitingRoom.jsx](../client/src/components/WaitingRoom/WaitingRoom.jsx) *(new)*
- [client/src/hooks/useWebSocket.js](../client/src/hooks/useWebSocket.js)
- [client/src/context/GameStateContext.jsx](../client/src/context/GameStateContext.jsx)
- [client/src/App.jsx](../client/src/App.jsx)
- [client/src/styles/main.css](../client/src/styles/main.css)

### Acceptance Criteria
- [x] Open two browser tabs → enter usernames "Alice" and "Bob" ✅
- [x] Alice creates a match → sees waiting room with match ID ✅
- [x] Bob sees match in list → joins it → both see each other in waiting room ✅
- [x] Both click "Ready" → match auto-starts → both transition to arena view ✅
- [x] Both players appear on the canvas grid at their spawn positions ✅

### Completion Notes
- **Date Completed:** February 11, 2026
- **Backend Changes:** `lobby.py` broadcasts `player_joined` on join; `match.py` ready endpoint broadcasts `player_ready` + `match_start`; `websocket.py` ready handler wired to `set_player_ready()` and `start_match()`; `match_manager.py` added `get_match_start_payload()`, `get_player_joined_payload()`, `get_lobby_players_payload()` helpers
- **Frontend Changes:** `Lobby.jsx` rewritten with API calls, match list polling (3s), create/join flow; new `WaitingRoom.jsx` component with real-time player list, ready status, and auto-transition; `App.jsx` updated with `waiting` screen state; `GameStateContext.jsx` added `PLAYER_JOINED`, `PLAYER_READY`, `PLAYER_DISCONNECTED` reducer actions + `lobbyPlayers`, `gridWidth`, `gridHeight`, `obstacles`, `tickRate` state
- **WebSocket Fix:** `useWebSocket.js` refactored to use ref for message callback — prevents reconnection on every re-render
- **Vite Fix:** Moved `index.html` from `client/public/` to `client/` (Vite project root)
- **CSS:** Added styles for match list items, join buttons, error messages, waiting room, player ready states
- **Tests:** 34/34 backend tests passing
- **Manual Testing:** Two-tab flow verified — create match, join, ready up, match starts, both transition to arena

---

## Section 6: Turn System & Action Queue

**Goal:** Server ticks every 10 seconds, players can queue actions, and the tick resolves + broadcasts results.

**Depends on:** Section 5

### Tasks

**Backend:**
- [x] When match starts, `scheduler_manager.add_match_tick()` schedules recurring tick ✅
- [x] Each tick: collect all queued actions from connected players ✅
- [x] Store queued actions in-memory (dict of match_id → {player_id → action}) ✅
- [x] On tick fire: pass actions to `turn_resolver.resolve_turn()` ✅
- [x] Broadcast `turn_result` to all players via WebSocket ✅
- [x] Increment `match.current_turn` ✅
- [x] Handle "no action" = automatic wait ✅
- [x] When match ends, `scheduler_manager.remove_match_tick()` cleans up ✅

**Frontend:**
- [x] Turn timer countdown display (10 → 0, resets each tick) ✅
- [x] Action submission via WebSocket: `{"type": "action", "action_type": "move", "target_x": 5, "target_y": 3}` ✅
- [x] Visual confirmation when action is queued ("Action Queued: Move to 5,3") ✅
- [x] On `turn_result` message: update all player positions, HP, alive status ✅
- [x] Combat log: append action result messages from turn_result ✅

### Key Implementation Details
- Action queue is **last-write-wins** — if a player submits two actions, only the last one counts
- The tick callback is async and uses `ws_manager.broadcast_to_match()` directly
- Timer on frontend is cosmetic — server is authoritative on when ticks fire
- Empty turns (all players wait) still broadcast a turn_result with no actions

### Files Involved
- [server/app/services/scheduler.py](../server/app/services/scheduler.py)
- [server/app/services/websocket.py](../server/app/services/websocket.py)
- [server/app/core/turn_resolver.py](../server/app/core/turn_resolver.py)
- [client/src/hooks/useWebSocket.js](../client/src/hooks/useWebSocket.js)
- [client/src/context/GameStateContext.jsx](../client/src/context/GameStateContext.jsx)

### Acceptance Criteria
- [x] After match starts, server logs `Tick 1`, `Tick 2`, etc. every 10 seconds ✅
- [x] Player submits a move action → next tick resolves it → player position updates on both clients ✅
- [x] If no action submitted → player waits → turn_result still broadcasts ✅
- [x] Turn number increments correctly ✅
- [x] Frontend timer counts down 10 → 0, resets on each tick ✅

### Completion Notes
- **Date Completed:** February 11, 2026
- **Tick System:** APScheduler `add_match_tick()` called on match start, `remove_match_tick()` on match end/victory
- **Action Queue:** In-memory `_action_queues` dict in `match_manager.py` — last-write-wins, cleared each tick
- **Turn Resolution:** `match_tick()` async callback in `websocket.py` — collects actions, resolves via `turn_resolver.resolve_turn()`, broadcasts `turn_result` + `match_end` if winner, auto-`wait` for idle players
- **Frontend Timer:** Cosmetic countdown (100ms interval), resets on each `turn_result` message
- **Tests:** 34/34 passing (updated 2 WS tests to use real matches for action queue validation)

### ✅ Migration Notes — Isleward-Style Queue Model (COMPLETE)
**Previous Implementation:** Single action per tick, queue clears after resolution (last-write-wins)

**Current Implementation (Section 7):** Persistent queue (up to 10 actions), tick consumes first action, rest remain queued

**Changes Completed:**
- ✅ Modified `_action_queues` to store list of actions per player (max 10)
- ✅ Updated `match_tick()` to pop first action from each player's queue via `pop_next_actions()`
- ✅ Added queue manipulation endpoints: `clear_queue`, `remove_last_action`, `get_queue`
- ✅ Frontend path preview showing queued movement tiles with numbered indicators (1→2→3)
- ⏳ Tick rate optimization deferred to Section 10 for live playtesting

---

## Section 7: Combat Engine Integration

**Goal:** Implement basic combat with Isleward-style persistent action queues. Validate that the queue + tick rhythm feels tactical but alive.

**Depends on:** Section 6

**Design Philosophy:** This section focuses on **feeling** over perfect balance. The goal is to prove the Isleward-style queue model works: players can queue multiple actions ahead, see them preview visually, and watch them execute in tick-based rhythm that feels responsive yet tactical.

### Game Design Specifications

**Isleward-Style Queue Model:**
- Players can queue **up to 10 actions** ahead
- Each tick consumes the **first action** from the queue, rest remain
- Players can **clear or modify** their queue before actions execute
- Visual path preview shows queued movement tiles with numbers (1, 2, 3...)
- Attack indicators show queued attacks on enemy tiles

**Combat Rules (Minimalist - Subject to Tuning):**
- **Damage Formula:** `attacker.damage - defender.armor` (minimum 1 damage)
  - Default damage: 15
  - Default armor: 2
  - Typical hit: 13 damage
- **Adjacency:** 8-directional (including diagonals)
- **Starting HP:** 100
- **Death:** Player dies at 0 HP, remaining queue clears, becomes spectator
- **Victory:** Last player alive wins

**Turn Resolution Order:**
1. Process movement actions first (all players)
2. Process attack actions second (all players)
3. Apply damage and check for deaths
4. Broadcast turn_result with all action outcomes
5. Check victory condition (1 or 0 players alive)
6. If match over, broadcast match_end and stop scheduler

**Important:** If action target is invalid when it executes (e.g., attack on empty tile after enemy moved), action fails gracefully with message to player.

### Tasks

**Backend - Persistent Queue System:**
- [x] Modify `match_manager._action_queues` to store list of actions per player (max 10) ✅
- [x] Update `match_tick()` to pop first action from queue instead of clearing ✅
- [x] Add `POST /api/match/{match_id}/clear_queue` endpoint ✅
- [x] Add `POST /api/match/{match_id}/remove_last_action` endpoint ✅
- [x] Validate queue length (reject if > 10 actions) ✅

**Backend - Combat Logic:**
- [x] Create `combat.py` module with damage calculation function ✅ (already existed from Section 2)
- [x] Wire attack actions through `turn_resolver.resolve_turn()` ✅ (already wired from Section 6)
- [x] Implement adjacency check (8 directions) ✅ (already existed from Section 2)
- [x] HP reduction and death tracking in match state ✅ (already wired from Section 6)
- [x] Dead players' queues are cleared and actions ignored ✅
- [x] Victory check after each turn: if ≤ 1 player alive → winner ✅ (already wired from Section 6)
- [x] Broadcast `match_end` with winner info and stats ✅ (already wired from Section 6)
- [x] Stop tick scheduler when match ends ✅ (already wired from Section 6)
- [x] Clean up match data after match ends ✅ (already wired from Section 6)

**Frontend - Queue Visualization:**
- [x] Path preview: highlight tiles for queued movement with numbers (1→2→3) ✅
- [x] Attack preview: show attack indicators on queued target tiles ✅ (red crosshair on attack targets)
- [x] Queue display UI: show list of queued actions with ability to clear/modify ✅
  - **Note:** Queue display built into ActionBar with color-coded queue list, Undo and Clear buttons
- [x] Visual feedback: queued tiles remain highlighted until action executes ✅

**Frontend - Combat Feedback:**
- [x] Click adjacent enemy tile → queue attack action (added to queue, not replacing) ✅
- [x] Show damage numbers on canvas after attacks resolve (floating text animation) ✅
- [x] HP bars update in real time from turn_result messages ✅ (already wired from Section 8)
- [x] Death: eliminated player sees "You have been eliminated" overlay + spectator mode ✅ (already wired from Section 8)
- [x] Victory: winner sees "Victory!" overlay ✅ (already wired from Section 8)
- [x] All players see post-match summary: kills, damage dealt, turns survived ✅
- [x] "Return to Lobby" button after match ends ✅ (already wired from Section 8)

**Tick Rate Tuning:**
- [ ] Test match at 10 seconds (current baseline)
- [ ] Test match at 5 seconds (feels more responsive?)
- [ ] Test match at 3 seconds (too fast?)
- [ ] Document findings: which tick rate achieves "tactical but alive" feel?

**Note:** Tick rate tuning deferred to Section 10 (Polish & Playtesting) where it can be evaluated with full end-to-end gameplay.

### Files Involved
- [server/app/core/match_manager.py](../server/app/core/match_manager.py) (updated queue to list structure, added pop/clear/remove functions)
- [server/app/routes/match.py](../server/app/routes/match.py) (added queue management endpoints)
- [server/app/services/websocket.py](../server/app/services/websocket.py) (updated tick callback for persistent queues, queue WS handlers)
- [client/src/context/GameStateContext.jsx](../client/src/context/GameStateContext.jsx) (added actionQueue, damageFloaters state)
- [client/src/App.jsx](../client/src/App.jsx) (updated WS message handlers for queue)
- [client/src/components/Arena/Arena.jsx](../client/src/components/Arena/Arena.jsx) (queue preview tiles, damage floaters, match stats)
- [client/src/canvas/ArenaRenderer.js](../client/src/canvas/ArenaRenderer.js) (path preview, attack preview, damage floaters)
- [client/src/components/ActionBar/ActionBar.jsx](../client/src/components/ActionBar/ActionBar.jsx) (queue list display, undo/clear buttons)
- [client/src/components/HUD/HUD.jsx](../client/src/components/HUD/HUD.jsx) (queue count display)
- [client/src/styles/main.css](../client/src/styles/main.css) (queue display, match stats CSS)
- [server/tests/test_queue.py](../server/tests/test_queue.py) (new — 14 persistent queue tests)
- [server/app/core/combat.py](../server/app/core/combat.py) (unchanged — already complete from Section 2)
- [server/app/core/turn_resolver.py](../server/app/core/turn_resolver.py) (unchanged — already wired from Section 6)

### Acceptance Criteria
- [x] Alice queues 3 moves → ticks 1-3 execute them sequentially → Alice arrives at destination ✅
- [x] Bob queues: move, move, attack Alice → executes over 3 ticks → Alice takes damage on tick 3 ✅
- [x] Alice clears her queue mid-execution → remaining actions are canceled ✅
- [x] Canvas shows numbered path preview (1, 2, 3) for queued movements ✅
- [x] Queue display shows: "Queue: Move North → Move East → Attack (5,3)" ✅
- [x] Alice attacks Bob (adjacent) → Bob's HP decreases by 13 (15 damage - 2 armor) ✅
- [x] Bob's HP reaches 0 → Bob sees "Eliminated" overlay, Alice sees "Victory!" overlay ✅
- [x] Attack on non-adjacent tile fails with message: "Target out of range" ✅
- [x] Attack on empty tile fails with message: "No target at this location" ✅
- [x] Post-match screen shows: winner, kills per player, damage dealt ✅
- [ ] Test at 10s/5s/3s tick rates → document which feels best *(deferred to Section 10)*
- [x] `pytest tests/test_combat.py -v` — all tests pass ✅
- [x] `pytest tests/test_turn_resolver.py -v` — all tests pass (updated for queues) ✅

### Success Metrics for This Section
**The goal is to validate the feel, not perfect balance:**
- [ ] Queueing 3-5 actions ahead feels natural and tactical *(needs live playtesting — Section 10)*
- [ ] Tick rate makes the world feel "alive" (not too slow, not too chaotic) *(needs live playtesting — Section 10)*
- [ ] Players can read and react to opponents' queued actions *(needs live playtesting — Section 10)*
- [x] Combat is understandable and satisfying (damage feedback is clear) ✅
- [ ] Match length is reasonable (5-10 minutes for 2-4 players) *(needs live playtesting — Section 10)*

**Note:** Balance tuning (exact damage values, HP amounts) happens in Section 10. Focus here is on proving the queue + combat loop works.

### Completion Notes
- **Date Completed:** February 11, 2026
- **Queue Migration:** `_action_queues` changed from `dict[str, dict[str, PlayerAction]]` to `dict[str, dict[str, list]]` with `MAX_QUEUE_SIZE=10`
- **New Backend Functions:** `pop_next_actions()` (pops first action per player per tick), `clear_player_queue()`, `remove_last_action()`, `get_player_queue()`
- **New REST Endpoints:** `POST /clear_queue`, `POST /remove_last_action`, `GET /queue/{player_id}`
- **WebSocket Updates:** Tick callback uses `pop_next_actions()`, sends `queue_updated` after tick, handles `clear_queue` and `remove_last` messages, clears dead players' queues
- **Frontend Queue UI:** ActionBar shows queue count (X/10), color-coded queue list (move=blue, attack=red, wait=gray), Undo and Clear buttons, queue full indicator
- **Path Preview:** `drawQueuePreview()` renders numbered tiles with dashed connection lines, red crosshair for attack targets
- **Damage Floaters:** `drawDamageFloaters()` renders animated floating damage text on canvas
- **Match Stats:** Post-match stats table showing kills and damage dealt per player
- **State Changes:** Added `actionQueue` and `damageFloaters` to GameStateContext; new reducer actions: `QUEUE_UPDATED`, `QUEUE_CLEARED`, `CLEAR_FLOATERS`
- **Tests:** 48/48 passing (14 new queue tests in `test_queue.py`)
- **Build:** Vite build clean — 166KB JS, 9.8KB CSS
- **Note:** `combat.py` and `turn_resolver.py` required no changes — combat logic was already fully implemented from Sections 2 and 6
- **Deferred:** Tick rate tuning deferred to Section 10 for live playtesting evaluation

---

## Section 8: Game UI (HUD, Combat Log, Action Buttons)

**Goal:** Complete the in-game user interface — everything a player needs to play.

**Depends on:** Section 4 (can be built in parallel with Sections 5-7, wired up at Section 9)

### Tasks

**HUD Panel:**
- [x] Player's own HP bar (color-coded: green → yellow → red) ✅
- [x] Current turn number display ✅
- [x] Turn timer countdown bar (visual, not just text) ✅
- [x] Current queued action indicator ("Queued: Move to 5,3") ✅

**Action Buttons:**
- [x] "Move" mode — click a tile to queue movement ✅
- [x] "Attack" mode — click an adjacent enemy tile to queue attack ✅
- [x] "Wait" button — explicitly queue a wait action ✅
- [x] Visual feedback: highlight valid target tiles when mode is selected ✅
- [x] Disable actions when player is dead ✅

**Combat Log:**
- [x] Scrolling text feed showing all turn results ✅
- [x] Color-coded messages: damage (red), movement (blue), kills (orange), system (gray) ✅
- [x] Auto-scroll to latest entry ✅
- [x] Show turn separator lines (`--- Turn 5 ---`) ✅

**Player List:**
- [x] All players listed with: username, HP bar, alive/dead status ✅
- [x] Dead players grayed out ✅
- [x] Highlight current player ✅

**Canvas Interactions:**
- [x] Click on tile → highlight it ✅
- [x] In move mode: show valid movement tiles (adjacent, unblocked) ✅
- [x] In attack mode: show attackable tiles (adjacent tiles with enemies) ✅
- [x] Hover tooltip: show tile coordinates and occupant info ✅

### Files Involved
- [client/src/components/Arena/Arena.jsx](../client/src/components/Arena/Arena.jsx)
- [client/src/components/HUD/](../client/src/components/HUD/) *(create)*
- [client/src/components/CombatLog/](../client/src/components/CombatLog/) *(create)*
- [client/src/canvas/ArenaRenderer.js](../client/src/canvas/ArenaRenderer.js)
- [client/src/styles/main.css](../client/src/styles/main.css)

### Acceptance Criteria
- [x] HP bar shows and changes color as damage is taken ✅
- [x] Turn timer visually counts down each tick ✅
- [x] Clicking "Move" then a tile shows the highlight and queues the action ✅
- [x] Combat log shows colored, readable messages for every action ✅
- [x] Player list shows all players with live HP updates ✅
- [x] Dead player's UI is locked (can't submit actions) ✅

### Completion Notes
- **Date Completed:** February 11, 2026
- **New Components:** `HUD.jsx` (HP bar, timer, player list, queued action), `CombatLog.jsx` (scrolling color-coded feed), `ActionBar.jsx` (Move/Attack/Wait mode buttons)
- **Canvas Interactions:** `pixelToTile()` converter, click handler dispatches move/attack based on actionMode, hover shows tile tooltip with coordinates and occupant info
- **Highlights:** Blue tiles for valid moves (adjacent, unblocked, unoccupied), red tiles for valid attacks (adjacent enemies)
- **Match End:** Victory/Defeat overlay with return-to-lobby button; death banner for spectating after elimination
- **Styles:** Full HUD, action bar, timer bar, combat log, match end overlay, death banner CSS

---

## Section 9: Match Flow End-to-End

**Goal:** Complete gameplay loop — from login through lobby, match, combat, victory, and back to lobby. Validate the Isleward-style queue system works in real matches.

**Depends on:** Sections 5, 6, 7, 8

### Tasks
- [X] Full flow test: username → lobby → create → join → ready → play → win → lobby
- [ ] Handle edge cases:
  - [X] Player disconnects mid-match (remove from match, notify others, clear their queue)
  - [X] Player tries to join a match that's already started → error
  - [ ] Player tries to act when dead → actions ignored, queue cleared
  - [ ] Two players move to same tile simultaneously → second one fails gracefully
  - [ ] Player queues 11+ actions → reject with error message
  - [ ] Player clears queue mid-tick → works correctly, no stale actions
  - [ ] Target moves away before queued attack executes → attack fails with message
- [ ] Match timer: if 15 minutes elapse, end match (highest HP wins, or draw)
- [ ] Reconnection: if WebSocket drops, player can reconnect and see current match state + their remaining queue
- [ ] 4-player match test: create match, 4 players join, full combat with queued actions to winner
- [ ] Validate all WebSocket messages match expected protocol (turn_result, match_end format)
- [ ] Queue persistence across disconnects: if player reconnects within 30 seconds, their queue is preserved

### Isleward-Style Queue Testing Scenarios
- [ ] **Tactical movement:** Player queues path around obstacle → executes over multiple ticks
- [ ] **Combat combo:** Player queues: move → move → attack → move away → executes as planned
- [ ] **Reaction test:** Alice sees Bob's queued path → Alice adjusts her queue to intercept
- [ ] **Queue overflow:** Player rapidly clicks 15 tiles → only first 10 are queued
- [ ] **Mid-queue modification:** Player queues 5 actions → clears after 2 execute → remaining 3 canceled
- [ ] **Simultaneous queue execution:** 4 players all have full queues → all execute correctly without conflicts

### Files Involved
- All server and client files — this is integration testing

### Acceptance Criteria
- [ ] Complete match with 2 players: lobby → queued combat → winner → back to lobby
- [ ] Complete match with 4 players: all see correct state, queues execute, one wins
- [ ] Disconnecting player is handled gracefully (no crash, others notified, their queue cleared)
- [ ] Player can queue up to 10 actions, 11th is rejected with clear error message
- [ ] Queue clear/modify works instantly without waiting for tick
- [ ] Match timeout works (15 min → highest HP wins or draw)
- [ ] Failed actions (target moved away, target out of range) show clear messages in combat log
- [ ] No console errors in browser during full match
- [ ] No unhandled exceptions on server during full match
- [ ] Path preview updates correctly as queue changes
- [ ] All players see synchronized combat log with queued action executions

### Performance Validation
- [ ] 4 players each with full 10-action queues → turn resolution < 100ms
- [ ] No lag when rapidly clicking to queue actions
- [ ] Path preview rendering doesn't drop FPS below 60

---

## Section 10: Polish, Balance & Playtesting

**Goal:** Tune the Isleward-style queue + tick system to feel tactical but alive. Validate the core loop is fun before committing to Phase 2.

**Depends on:** Section 9

### Tasks

**Tick Rate & Feel Tuning (PRIORITY):**
- [ ] Play 5+ matches at **10 second ticks** (current baseline) → document feel
- [ ] Play 5+ matches at **5 second ticks** → does it feel more responsive? Too fast?
- [ ] Play 5+ matches at **3 second ticks** → Isleward-like responsiveness? Too chaotic?
- [ ] **Decision:** Pick optimal tick rate that achieves "tactical but alive" feel
- [ ] Document findings: what tick rate makes players want to keep playing?
- [ ] Test queue depth: is 10 actions right, or should it be 5? 15?
- [ ] Evaluate queue preview: is path numbering clear? Do players use it tactically?

**Balance Tuning via JSON Configs:**
- [ ] Play 10+ matches, track: match length, kill counts, movement patterns, queue usage
- [ ] Tune via JSON configs (no code changes):
  - [ ] `combat_config.json` — HP (100 too high?), damage (15 too weak?), armor (2 too low?)
  - [ ] `maps/arena_classic.json` — obstacle layout (too open? too cramped?), spawn positions
- [ ] Evaluate map size: is 15x15 right for 4 players? Try 12x12 or 18x18?
- [ ] Evaluate: does combat need skills/abilities, or is basic move+attack enough for Phase 1?

**Isleward-Style Gameplay Validation:**
- [ ] **Key Question:** Does queueing multiple actions feel tactical and intentional?
- [ ] **Key Question:** Can players read opponents' queued paths and respond?
- [ ] **Key Question:** Does the world feel "alive" or does it still feel turn-based-slow?
- [ ] **Key Question:** Is there emergent tactical depth (baiting, positioning, timing)?
- [ ] If any answer is "no" → what needs to change for Phase 2?

**Bugs & Edge Cases:**
- [ ] Stress test: 8 players in one match, all with full 10-action queues
- [ ] Rapid action submission: spam click 50 tiles → queue handles gracefully
- [ ] Multiple matches running simultaneously (2-3 matches, 12+ total players)
- [ ] Browser refresh mid-match → reconnect works, queue preserved
- [ ] Long-idle players (5+ minutes of no input)
- [ ] Queue manipulation spam: rapidly clear/re-queue actions
- [ ] Network lag simulation: 100ms, 500ms, 1000ms latency → still playable?

**Performance:**
- [ ] Turn resolution time < 100ms for 8 players (each with full queues)
- [ ] WebSocket message latency < 50ms local
- [ ] Canvas renders at 60fps even with path previews for 4 players
- [ ] No memory leaks over 30+ turn match
- [ ] Action queue operations (add/clear) don't cause frame drops

**Documentation:**
- [ ] Update game rules doc with final tick rate and combat values
- [ ] Document known issues / tech debt for Phase 2:
  - [ ] What features were cut for time?
  - [ ] What parts of the code need refactoring?
  - [ ] What performance issues remain?
- [ ] Write Phase 1 retrospective: 
  - [ ] Did the Isleward-style queue model work?
  - [ ] What surprised us (good and bad)?
  - [ ] Is the core loop fun enough for Phase 2?
  - [ ] Go/no-go recommendation for persistent world

### Acceptance Criteria
- [ ] 3+ people (not the developer) have played and given feedback
- [ ] Average match lasts 5-10 minutes (not too quick, not too grindy)
- [ ] Feedback includes "I want to play again" or "this feels good" or equivalent
- [ ] Optimal tick rate is chosen and documented with reasoning
- [ ] Queue system is validated: players intentionally use multi-action queues
- [ ] No crash bugs or exploits in standard gameplay
- [ ] Performance targets met (100ms resolution, 60fps, no leaks)
- [ ] **Phase 2 go/no-go decision is documented with clear reasoning**

### Success Metrics
**Quantitative:**
- Match completion rate > 90% (players don't rage-quit mid-match)
- Average actions queued per turn > 2 (players are using the queue system)
- Turn resolution consistency: 95%+ of ticks fire within 100ms of scheduled time

**Qualitative:**
- "The queueing system makes me feel smart/tactical"
- "I can see what my opponent is doing and react"
- "The pace feels right — not too slow, not too fast"
- "One more match!" (players want to keep playing)

**Go/No-Go Criteria for Phase 2:**
- ✅ **GO:** Players enjoy the queue + tick rhythm, want more depth (skills, territory)
- ❌ **NO-GO:** Core loop feels tedious, players don't engage with queue system, tick rate can't be tuned to feel good
- 🤔 **PIVOT:** Core loop has potential but needs significant rework before Phase 2

---

## Progress Tracker

| Section | Status | Notes |
|---------|--------|-------|
| 1. Dev Environment & Setup | ✅ Complete | Python 3.11.9, Node.js v22.19.0, Redis fallback working |
| 2. Server Foundation | ✅ Complete | Config, Redis fallback, routes, models, 24/24 tests passing |
| 3. WebSocket Infrastructure | ✅ Complete | ConnectionManager, broadcast, malformed handling, 34/34 tests |
| 4. Frontend Foundation | ✅ Complete | Canvas renderer, 15x15 grid, obstacles, player tokens, screen routing |
| 5. Lobby System | ✅ Complete | REST + WS lobby flow, WaitingRoom, match list polling, ready/start |
| 6. Turn System & Action Queue | ✅ Complete | APScheduler tick, action queue, turn_result broadcast, 34/34 tests |
| 7. Combat Engine Integration | ✅ Complete | Persistent queue (10 actions), path preview, damage floaters, 48/48 tests |
| 8. Game UI (HUD, Log, Actions) | ✅ Complete | HUD, CombatLog, ActionBar, canvas interactions, highlights |
| 9. Match Flow End-to-End | ⬜ Not Started | |
| 10. Polish & Playtesting | ⬜ Not Started | |

**Status Key:** ⬜ Not Started · 🔨 In Progress · ✅ Complete

---

## Estimated Timeline

| Week | Sections | Key Milestone | Status |
|------|----------|---------------|--------|
| Week 1 | 1, 2, 3, 4 | Two players connected on a grid | ✅ **Complete** (4/4) |
| Week 2 | 5, 6, 7 | Two players can fight to the death | ✅ **Complete** (Sections 5, 6, 7, 8 all complete) |
| Week 3 | 9 | 4-player match plays start to finish | ⬜ Not Started |
| Week 4 | 10 | Playtested, balanced, Phase 2 decision made | ⬜ Not Started |

**Current Date:** February 11, 2026 — Week 1, Day 1

---

**Document Version:** 1.5  
**Last Updated:** February 11, 2026 — Sections 1-8 completed  
**Parent Spec:** [Phase 1 Arena Prototype](phase1-arena-prototype.md)

**Changelog:**
- **v1.5** (Feb 11, 2026): Section 7 completed — Persistent action queue (10 max), path preview with numbered tiles, damage floaters, queue UI in ActionBar (undo/clear), match stats, 48/48 tests passing, vite build clean
- **v1.4** (Feb 11, 2026): Sections 6 + 8 completed — Turn system with APScheduler tick, action queue, turn_result broadcast; Full game UI with HUD, CombatLog, ActionBar, canvas click interactions, tile highlights, match end overlay
- **v1.3** (Feb 11, 2026): Section 5 Lobby System completed — full create/join/ready/start flow working, WaitingRoom component added, Vite index.html fix
- **v1.2** (Feb 11, 2026): Sections 2-4 marked complete; Section 5 Lobby System implementation started
- **v1.1** (Feb 11, 2026): Section 1 completed; added Windows platform notes and quick reference commands
- **v1.0** (Feb 11, 2026): Initial document creation
