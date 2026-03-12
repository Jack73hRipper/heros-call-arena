# Phase 2: Arena Plus — Design Document

## Overview

**Goal:** Expand the Phase 1 arena prototype with AI opponents, tactical depth (FOV + ranged combat), and map variety to validate core gameplay loop and replayability.

**Timeline:** 5 weeks + 2 weeks bug fixes 
**Status:** Phase 2.1 — Bug Fixes Required Before Phase 3  
**Prerequisites:** Phase 1 complete and tested

---

## Phase 2.1: Critical Bug Fixes & Improvements

**Status:** Must be completed and tested before Phase 3 planning begins.

### Bug Fix Priority: All Critical

**All bugs listed below must be fixed and validated before moving to Phase 3. No bugs will be deferred.**

**Total: 8 bugs identified + 1 new feature (lobby chat). All resolved.**

---

### Bug #1: Team Assignment Broken in PvP Matches — ✅ FIXED (Chunk 2)

**Issue Observed:**
When multiple human players join a PvP match, all players are assigned to the same team, resulting in immediate victory after the first turn. The system appears to be treating all humans as allies regardless of match type selection.

**Expected Behavior:**
- In PvP mode, players should be able to manually select which team they want to join (Team A, B, C, or D)
- Players on opposing teams should be able to attack each other
- Victory condition should trigger only when all members of one team are eliminated

**Fix Required:**
- Implement team selection system in the match lobby
- Ensure match type correctly assigns players to appropriate teams
- Validate that PvP matches allow cross-team combat

**Fix Applied:**
- Added `change_player_team()` function to `match_manager.py` — moves player between teams during lobby phase
- Added `team_select` WS message type for real-time team switching
- Added `POST /api/lobby/{match_id}/team` REST endpoint as alternative
- Server broadcasts `team_changed` to all lobby members with updated player list
- WaitingRoom UI shows team selection dropdown (Team A / B / C / D) next to each player
- `get_lobby_players_payload()` now includes `team` and `unit_type` fields
- `TEAM_CHANGED` reducer added to GameStateContext
- **Expanded to 4 teams in Chunk 2.5** — `MatchState` has `team_c`/`team_d`, victory checks support 2-4 teams dynamically

---

### Bug #2: Tick Rate Too Slow — ✅ FIXED (Chunk 1)

**Issue Observed:**
Current tick rate of 10 seconds feels excessively slow during gameplay. Players experience long wait times between actions, making matches feel sluggish.

**Expected Behavior:**
Tick rate should be 5 seconds to create more responsive gameplay while maintaining the tactical turn-based feel.

**Fix Required:**
Change tick rate from 10 seconds to 5 seconds in match configuration.

**Fix Applied:**
- Changed default `TICK_RATE_SECONDS` from 10.0 → 5.0 in `server/app/config.py`
- Changed default `tick_rate` from 10.0 → 5.0 in `MatchConfig` model (`server/app/models/match.py`)
- Both server global default and per-match config default now 5 seconds
- Still overridable via `ARENA_TICK_RATE_SECONDS` env variable

---

### Bug #3: AI Behavior - Lack of Active Scouting — ✅ FIXED (Chunk 1)

**Issue Observed:**
AI opponents remain passive at their spawn locations until a player enters their field of view. They do not actively explore the map or hunt for players. This makes AI feel static and predictable rather than like active opponents.

**Player Experience:**
"The AI just seems to hang out where they spawn instead of going hunting."

**Expected Behavior:**
AI should actively patrol and explore the map when no enemies are visible, creating the sense that they are hunting for players. AI should feel proactive, not purely reactive.

**Fix Required:**
Improve AI behavior to include active exploration/scouting when no enemies are in field of view. AI should move around the map, not idle at spawn.

**Fix Applied:**
- Replaced random adjacent wander with waypoint-based scouting system in `server/app/core/ai_behavior.py`
- AI now picks distant patrol waypoints (prefers far, unvisited tiles) and navigates toward them via A* pathfinding
- Added `_patrol_targets` dict: persistent waypoint memory per AI unit
- Added `_visited_history` dict: tracks last 15 visited tiles to avoid revisiting same areas
- Waypoint scoring: prioritizes distance from current position + penalizes recently visited tiles
- Randomized top-8 candidate selection prevents all AI from converging on same waypoint
- Patrol target cleared when enemies spotted (resumes fresh scouting after losing target)
- Dead AI state cleaned up automatically in `run_ai_decisions`
- Added `clear_ai_patrol_state()` called on match end to prevent stale memory across matches
- Fallback to random adjacent move only when A* cannot find any valid path

---

### Bug #4: Team Field of View Not Shared — ✅ FIXED (Chunk 1)

**Issue Observed:**
Players on the same team cannot see what their teammates see. Each player only has their individual field of view, even when working with allies. This makes team coordination difficult and feels isolating.

**Player Experience:**
Team FOV sharing is more important than initially expected. Not being able to see teammates' vision hinders gameplay and makes team matches feel disconnected.

**Expected Behavior:**
Players on the same team should share field of view. If Player A can see an area and Player B cannot, Player B should still be able to see that area because their teammate can see it.

**Fix Required:**
Implement shared team vision so all teammates see the combined field of view of all team members.

**Fix Applied:**
- Added `get_team_fov()` function to `server/app/core/match_manager.py` — merges all team members' individual FOV caches into a union set
- Updated `match_tick()` in `server/app/services/websocket.py` to pre-compute team FOV (`team_a_fov`, `team_b_fov`) once per tick
- Each human player now receives the combined FOV of their entire team (including AI allies)
- `visible_tiles` in turn_result payload is the full team FOV
- Player/unit filtering and action filtering both use team FOV
- FFA mode (no teams) falls back to individual FOV
- Allies-always-visible safety check retained as redundant fallback
- AI still uses individual FOV for its own decision-making (AI doesn't benefit from team FOV — intentional to keep AI fair)

---

### Bug #5: AI Units Not Visible in Lobby Player List — ✅ FIXED (Chunk 3)

**Issue Observed:**
When AI opponents or AI allies are added to a match, they do not appear in the lobby player list. Players cannot see how many AI units exist or which teams they are assigned to before the match starts.

**Expected Behavior:**
AI units should appear in the lobby player list alongside human players, showing:
- AI unit name (e.g., "AI-1", "AI-2")
- AI type (AI Opponent or AI Ally)
- Current team assignment
- Ready status

This allows players to see full team composition before match start and enables team assignment for AI units.

**Fix Required:**
Add AI units to the lobby player list display with clear labeling and team indicators.

**Fix Applied:**
- AI units now spawn at match creation time (not just match start) via `_spawn_ai_units()` called from `create_match()`
- `_spawn_ai_units()` adds AI to `match.player_ids`, `match.ai_ids`, and appropriate team lists during WAITING phase
- `get_lobby_players_payload()` returns AI units alongside humans (filtered by `player_ids` safety belt)
- AI units have `is_ready=True` by default (always ready)
- `set_player_ready()` only checks human players for ready threshold (AI don't block start)
- WaitingRoom shows AI with 🤖 badge, Ally/Opponent label, team badge, and always-ready indicator
- `_clear_ai_units()` + `_spawn_ai_units()` support re-spawning when host changes config in lobby

---

### Bug #6: Ghost Players Persist After Leaving Lobby — ✅ FIXED (Chunk 2 + Chunk 2.5)

**Issue Observed:**
When a player joins a lobby but then leaves, a ghost/duplicate entry of that player remains in the lobby. This creates phantom players in the player list.

**Expected Behavior:**
When a player leaves the lobby, their entry should be completely removed from the player list for all remaining players. No duplicate or ghost entries should persist.

**Fix Required:**
Properly clean up player state when disconnecting or explicitly leaving lobby. Ensure all clients receive player removal notification and update their UI accordingly.

**Fix Applied (Chunk 2):**
- `remove_player()` now also removes from `team_a`/`team_b` lists (previously only `player_ids`)
- `remove_player()` returns the player's username for broadcast messages
- WS disconnect handler now calls `remove_player()` in lobby phase (previously only in-progress — root cause of ghost players)
- `player_disconnected` broadcast now includes `username` field
- Added `POST /api/lobby/leave/{match_id}` REST endpoint for explicit leave
- WaitingRoom "Leave Match" button calls REST leave endpoint before client-side state reset
- `PLAYER_DISCONNECTED` reducer logs username in combat log instead of generic message

**Deep Fix Applied (Chunk 2.5):**
- Root cause: `remove_player()` only set `is_alive = False` but never removed the player entry from `_player_states` — so `get_lobby_players_payload()` continued to include ghost entries
- During WAITING phase, `remove_player()` now fully deletes the player from `_player_states`
- Returns `None` if player was already removed — prevents double-broadcast from REST + WS disconnect race
- `get_lobby_players_payload()` now cross-references `match.player_ids` as safety filter
- WS disconnect handler guards against double-removal and already-cleaned-up matches
- Empty waiting matches auto-removed when last human leaves

---

### Bug #7: Match Configuration Should Be Inside Lobby (UX Redesign) — ✅ FIXED (Chunk 3)

**Issue Observed:**
Currently, match configuration (map selection, AI count, match type) happens before creating the lobby. Once the lobby is created, these settings are locked. Players joining later cannot see or participate in configuration decisions.

**Expected Behavior:**
Match configuration should happen inside the lobby after it's been created. All players should be able to see the current configuration. The match host should be able to adjust settings while players are in the lobby.

**Desired Lobby Screen Layout:**
- Player list (with team selection dropdowns for each player)
- Map selection dropdown (host only)
- Add/remove AI opponent buttons (host only)
- Add/remove AI ally buttons (host only)
- AI units listed with team assignment options (host only)
- Chat window for player communication
- Start Match button (host only)
- Leave Lobby button (all players)

**Team Selection:**
All players should be able to manually select which team (Team A or Team B) they want to join via dropdown next to their name in the player list.

**Fix Required:**
Redesign lobby UX to move all match configuration controls into the lobby screen itself. Implement host-only controls for match settings. Add team selection dropdowns for all players.

**Fix Applied:**
- Added `update_match_config()` in `match_manager.py` — host-only config changes during WAITING phase
- Added `lobby_config` WS message type + `POST /api/lobby/{match_id}/config` REST endpoint
- Config changes broadcast `config_changed` to all lobby members in real-time
- WaitingRoom redesigned with host-only controls: map dropdown, mode buttons, AI sliders
- Non-host players see read-only config values
- Create/Join responses include `config` payload so clients sync immediately
- `GameStateContext` tracks `lobbyConfig`, `CONFIG_CHANGED` reducer keeps it current
- PvP mode auto-clears AI counts; AI count changes trigger re-spawn in lobby

---

### Bug #8: Lobby Config Controls Lock After One Change — ✅ FIXED (Chunk 4)

**Issue Observed:**
When the host changes any lobby setting (map, game mode, AI sliders), all config controls immediately grey out and become unresponsive. The host can make exactly one change, then all dropdowns, buttons, and sliders lock as if they are a non-host player.

**Expected Behavior:**
The host should be able to make unlimited config changes while in the lobby. Changing the map should not prevent changing the game mode or AI counts, and vice versa.

**Root Cause:**
`update_match_config()` in `match_manager.py` returned a config dict **without `host_id`**. When the server broadcast `config_changed`, the client's `CONFIG_CHANGED` reducer **replaced** `lobbyConfig` entirely with the incoming config. Since `host_id` was missing (`undefined`), the WaitingRoom check `config.host_id === gameState.playerId` evaluated to `false`, switching all host controls to read-only mode.

**Fix Applied:**
- **Server:** Added `"host_id": match.host_id` to the return dict in `update_match_config()` — now matches what `get_match_config_payload()` already returns
- **Client:** Changed `CONFIG_CHANGED` reducer to **merge** incoming config with existing `lobbyConfig` (`{ ...state.lobbyConfig, ...action.payload.config }`) instead of replacing it — ensures no fields are lost even if server omits them

**Files Changed:** `server/app/core/match_manager.py`, `client/src/context/GameStateContext.jsx`

---

### New Feature Addition: Lobby Chat Window — ✅ COMPLETE (Chunk 3)

**Requirement:**
While redesigning the lobby UX (Bug #7), add a chat window to the lobby screen so players can communicate while waiting for the match to start.

**Specifications:**
- Chat window visible to all players in lobby
- Messages are lobby-scoped (only visible to players in that specific lobby)
- Basic text input and message display
- Messages show sender name
- Chat history persists while in lobby (clears when match starts)

---

## Testing Requirements (Phase 2.1)

All bugs must be validated as fixed through the following test scenarios:

### Test Scenario 1: PvP Team Assignment
- 4 human players join lobby
- Players manually select teams: 2 on Team A, 2 on Team B
- Match starts with proper team assignments
- Players can attack enemies on opposing team
- Match continues until one team is eliminated
- Victory awarded to surviving team

**Pass Criteria:** No immediate victory, cross-team combat works, correct team wins.

---

### Test Scenario 2: Tick Rate Validation
- Start any match configuration
- Measure time between turn resolutions
- Confirm tick rate is 5 seconds (not 10 seconds)
- Gameplay feels more responsive than previous version

**Pass Criteria:** Ticks fire every 5 seconds consistently.

---

### Test Scenario 3: AI Active Scouting
- Solo PvE match: 1 human vs 3 AI opponents
- Observe AI behavior when human is not in AI field of view
- AI should move around map, explore, patrol
- AI should not remain stationary at spawn location

**Pass Criteria:** AI actively moves and explores when no enemies are visible.

---

### Test Scenario 4: Shared Team Vision
- 2 human players on Team A vs 2 AI opponents on Team B
- Player A moves to one side of map
- Player B moves to opposite side of map
- Both players should see everything either teammate can see
- Test by having Player A spot enemy - Player B should see it too

**Pass Criteria:** Both teammates see combined field of view from both positions.

---

### Test Scenario 5: AI in Lobby List
- Create match with AI opponents and AI allies
- All AI units appear in lobby player list
- AI units show name, type (opponent/ally), and team assignment
- Host can modify AI team assignments in lobby

**Pass Criteria:** All AI visible in lobby with correct information displayed.

---

### Test Scenario 6: Player Disconnect Cleanup
- 3 players join lobby
- 1 player leaves lobby (disconnect or explicit leave)
- Remaining 2 players see updated player list (player removed)
- No duplicate/ghost entries remain
- Repeat test with different disconnect scenarios

**Pass Criteria:** Clean player removal with no ghost entries.

---

### Test Scenario 7: In-Lobby Configuration
- Create lobby (empty initially)
- Players join lobby
- Host adjusts map selection, adds AI units, configures teams
- All players see configuration changes in real-time
- Players select their own teams via dropdowns
- Host starts match with final configuration

**Pass Criteria:** All configuration controls work in-lobby, changes visible to all players.

---

### Test Scenario 8: Lobby Chat
- Players in lobby send messages
- All players in lobby receive and see messages
- Messages show correct sender names
- Chat persists while in lobby
- Chat clears when match starts

**Pass Criteria:** Chat functional and scoped to lobby.

---

## Phase 2.1 Completion Criteria

**Phase 2.1 is complete when:**
- All 8 bugs are fixed
- All 8 test scenarios pass
- Lobby chat is functional
- No regressions in Phase 1 or Phase 2 features
- At least 3 full matches completed without critical bugs

**Only after Phase 2.1 completion can Phase 3 planning begin.**

---

## Phase 2.1 Implementation Progress

### Chunk 1: Server-Side Logic Fixes — ✅ COMPLETE (Feb 12, 2026)

**Scope:** Bugs #2, #3, #4 — isolated server-side changes, no UI modifications needed.

| Bug | Status | Files Changed |
|-----|--------|---------------|
| #2 Tick rate 10s → 5s | ✅ Fixed | `config.py`, `models/match.py` |
| #3 AI active scouting | ✅ Fixed | `core/ai_behavior.py`, `services/websocket.py` |
| #4 Shared team FOV | ✅ Fixed | `core/match_manager.py`, `services/websocket.py` |

**Testing:**
- All module imports verified clean
- AI scouting tested: picks distant waypoints, navigates via A*, no idle at spawn
- Team FOV merge tested: union of teammate vision confirmed (4+4 tiles = 7 unique)
- Existing test suite: all tests passing (pre-existing turn resolver failures fixed in Chunk 2.5)

### Chunk 2: Lobby State Management — ✅ COMPLETE (Feb 12, 2026)

**Scope:** Bugs #1, #6 — player state cleanup and PvP team selection backend + frontend.

| Bug | Status | Files Changed |
|-----|--------|---------------|
| #6 Ghost players on disconnect | ✅ Fixed | `core/match_manager.py`, `services/websocket.py`, `routes/lobby.py`, `WaitingRoom.jsx` |
| #1 PvP team assignment | ✅ Fixed | `core/match_manager.py`, `services/websocket.py`, `routes/lobby.py`, `GameStateContext.jsx`, `App.jsx`, `WaitingRoom.jsx`, `main.css` |

**Bug #6 Fixes Applied:**
- `remove_player()` now also cleans `team_a`/`team_b` lists (previously only removed from `player_ids`, leaving ghost entries in team lists)
- `remove_player()` now returns the removed player's username for richer disconnect broadcasts
- WS disconnect handler now calls `remove_player()` in **both** lobby and in-progress phases (previously lobby disconnects were skipped — root cause of ghost players)
- `player_disconnected` WS broadcast now includes `username` field (previously anonymous)
- Added `POST /api/lobby/leave/{match_id}` REST endpoint for explicit lobby leave
- WaitingRoom "Leave Match" button now calls the REST leave endpoint before dispatching `LEAVE_MATCH`
- `PLAYER_DISCONNECTED` reducer updated to include username in combat log message

**Bug #6 Deep Fix (Chunk 2.5):**
- Root cause: `remove_player()` only set `is_alive = False` but never removed the player entry from `_player_states` during lobby phase — so `get_lobby_players_payload()` continued to include ghost entries
- Fix: During WAITING phase, `remove_player()` now fully deletes the player from `_player_states` (not just marks dead)
- `remove_player()` returns `None` if player was already removed — prevents double-broadcast from REST leave + WS disconnect race condition
- `get_lobby_players_payload()` now filters to only include players whose IDs are in `match.player_ids` (safety belt)
- Empty waiting matches auto-cleanup: when last human leaves, match is removed from `_active_matches` so it doesn't linger in lobby list

**Bug #1 Fixes Applied:**
- Added `change_player_team()` function in `match_manager.py` — moves a player between Team A, B, C, or D during lobby phase
- Added `get_player_username()` helper function in `match_manager.py`
- Added `team_select` WS message type — players send `{ "type": "team_select", "team": "a"|"b"|"c"|"d" }` to switch teams
- Server broadcasts `team_changed` WS message to all lobby members with updated player list
- Added `POST /api/lobby/{match_id}/team` REST endpoint (alternative to WS for team changes)
- `get_lobby_players_payload()` now includes `unit_type` and `team` fields in response
- Added `TEAM_CHANGED` reducer action to `GameStateContext.jsx`
- `App.jsx` WS handler routes `team_changed` messages to `TEAM_CHANGED` dispatcher
- WaitingRoom UI shows team selection dropdown (A / B / C / D) for current player and team badge for other players
- Added CSS styles for `.team-select`, `.team-badge`, `.team-a`, `.team-b`, `.team-c`, `.team-d`

**Testing:**
- All module imports verified clean (match_manager, lobby routes, websocket)
- 6 integration tests written and passing (`tests/test_chunk2.py`):
  - `test_create_and_join` — host + player both start on team A
  - `test_change_team` — player switches to team B correctly
  - `test_change_team_invalid` — rejects invalid team ("e") or nonexistent player
  - `test_remove_player_cleans_teams` — removal cleans player_ids + team lists
  - `test_get_player_username` — returns username or None
  - `test_lobby_payload_includes_team` — lobby payload has `team` and `unit_type` fields
- Client builds cleanly (`vite build` — 0 errors)
- No lint/type errors across all modified files

### Chunk 2.5: Ghost Player Deep Fix + 4-Team System — ✅ COMPLETE (Feb 12, 2026)

**Scope:** Persistent ghost player root cause fix + expanding team system from 2 to 4 teams.

| Item | Status | Files Changed |
|------|--------|---------------|
| Ghost player deep fix | ✅ Fixed | `core/match_manager.py`, `services/websocket.py` |
| 4-team system | ✅ Complete | `models/match.py`, `core/match_manager.py`, `core/combat.py`, `core/turn_resolver.py`, `services/websocket.py`, `routes/lobby.py`, `WaitingRoom.jsx`, `GameStateContext.jsx`, `HUD.jsx`, `main.css` |
| Pre-existing test fixes | ✅ Fixed | `tests/test_turn_resolver.py`, `tests/test_chunk2.py` |

**Ghost Player Deep Fix:**
- Root cause identified: `remove_player()` only set `is_alive = False` but never removed the player entry from `_player_states` during lobby phase, so `get_lobby_players_payload()` kept returning ghost entries
- `remove_player()` now fully deletes from `_player_states` during WAITING phase
- Returns `None` if player was already removed (prevents duplicate broadcasts from REST leave + WS disconnect race)
- `get_lobby_players_payload()` now cross-references `match.player_ids` as safety filter
- WS disconnect handler guards against double-removal and already-cleaned-up matches
- Empty waiting matches auto-removed when last human player leaves

**4-Team System:**
- `MatchState` model: added `team_c` and `team_d` lists
- `change_player_team()`: accepts "a", "b", "c", "d" (was "a", "b")
- `remove_player()`: cleans all 4 team lists
- `get_match_teams()`: returns 4-tuple `(team_a, team_b, team_c, team_d)`
- `match_start` payload: includes `team_c` and `team_d` arrays
- `check_team_victory()`: dynamically supports 2-4 teams — only considers teams with members, last team standing wins
- `resolve_turn()`: passes all 4 team lists to victory check
- `match_tick()`: computes FOV per-team for all 4 teams, maps player team letter to FOV via lookup dict
- `team_select` WS + REST: accepts "a", "b", "c", "d"
- Victory display: "Team A/B/C/D wins!" for all 4 teams
- WaitingRoom dropdown: 4 team options (A, B, C, D)
- HUD: labels, colors, and team detection for all 4 teams
- CSS: `.team-c` (green) and `.team-d` (yellow) badge styles
- ArenaRenderer: already used `isSameTeam` comparison — no changes needed

**Pre-existing Test Fixes:**
- `test_adjacent_attack_deals_damage` and `test_lethal_attack_triggers_death` in `test_turn_resolver.py` were failing because they didn't assign players to opposing teams (so `are_allies()` blocked the attack)
- Fixed by assigning `team = "a"`/`team = "b"` and passing `team_a`/`team_b` lists to `resolve_turn()`
- `test_change_team_invalid` in `test_chunk2.py` updated: now tests team "e" as invalid (since "c" and "d" are valid)

**Testing:**
- Full test suite: **48 tests passing, 0 failures**
- Client builds cleanly (`vite build` — 0 errors)
- All Python imports verified clean

### Chunk 3: Lobby UX Redesign — ✅ COMPLETE (Feb 12, 2026)

**Scope:** Bugs #5, #7 + Lobby Chat — frontend + backend overhaul of lobby screen.

| Item | Status | Files Changed |
|------|--------|---------------|
| #5 AI visible in lobby | ✅ Fixed | `core/match_manager.py`, `WaitingRoom.jsx`, `main.css` |
| #7 Config inside lobby | ✅ Fixed | `core/match_manager.py`, `services/websocket.py`, `routes/lobby.py`, `WaitingRoom.jsx`, `GameStateContext.jsx`, `App.jsx`, `Lobby.jsx`, `main.css` |
| Lobby Chat | ✅ Complete | `core/match_manager.py`, `services/websocket.py`, `WaitingRoom.jsx`, `GameStateContext.jsx`, `App.jsx`, `main.css` |

**Bug #5 Fixes Applied:**
- AI units now spawn during match creation (not just match start) so they appear in lobby player list immediately
- `_spawn_ai_units()` rewritten to support re-spawning on config change (clears old AI first via `_clear_ai_units()`)
- AI units added to `match.player_ids` and `match.ai_ids` during lobby phase
- `get_lobby_players_payload()` returns AI units alongside humans (already filtered by `player_ids`)
- AI units show in WaitingRoom with 🤖 badge, Ally/Opponent label, team badge, and always-ready status
- `set_player_ready()` now only checks human players for ready status (AI are always ready)

**Bug #7 Fixes Applied:**
- Added `update_match_config()` in `match_manager.py` — host-only config updates during lobby phase
- Supported config fields: `map_id`, `match_type`, `ai_opponents`, `ai_allies`
- PvP mode auto-clears AI counts; AI slider changes trigger re-spawn
- Added `lobby_config` WS message type — host sends `{ type: "lobby_config", config: {...} }`
- Server validates host ownership, applies changes, re-spawns AI if needed, broadcasts `config_changed` to all
- Added `POST /api/lobby/{match_id}/config` REST endpoint (alternative to WS)
- Added `GET /api/lobby/{match_id}/config` REST endpoint for polling
- `get_match_config_payload()` returns current config including `host_id`
- WaitingRoom redesigned: host sees map dropdown, mode buttons, AI sliders; non-host sees read-only values
- Config changes broadcast in real-time to all lobby members
- Create/Join endpoints now return config and chat payload
- `GameStateContext` stores `lobbyConfig` state, `CONFIG_CHANGED` reducer updates it
- `App.jsx` routes `config_changed` WS messages to dispatcher

**Lobby Chat Fixes Applied:**
- Added `_lobby_chat` dict in `match_manager.py` — stores messages per match (max 100)
- Added `add_lobby_message()` — validates match is in WAITING, caps message at 500 chars
- Added `get_lobby_chat()` — returns chat history for a match
- Chat cleared on match start (`start_match()`) and match removal (`remove_match()`)
- Added `lobby_chat` WS message type — player sends `{ type: "lobby_chat", message: "..." }`
- Server broadcasts `chat_message` to all lobby members with sender name + timestamp
- Added `GET /api/lobby/{match_id}/chat` REST endpoint for loading chat history
- Join endpoint returns existing chat history so late-joining players see past messages
- WaitingRoom has chat window with auto-scroll, message input, and send button
- `GameStateContext` stores `lobbyChat` array, `CHAT_MESSAGE` reducer appends new messages
- `App.jsx` routes `chat_message` WS messages to dispatcher
- Messages show sender name with visual distinction for own messages

**Testing:**
- 14 integration tests written and passing (`tests/test_chunk3.py`):
  - `test_ai_visible_in_lobby_on_create` — AI opponents appear in lobby on match creation
  - `test_ai_allies_in_lobby` — AI allies appear on team A with correct labels
  - `test_ai_in_match_state` — AI IDs tracked in match.ai_ids and match.player_ids
  - `test_host_can_change_map` — host updates map via config API
  - `test_host_can_change_match_type` — host switches between PvP/PvE/Mixed
  - `test_non_host_cannot_change_config` — non-host config changes rejected
  - `test_pvp_mode_clears_ai` — switching to PvP removes all AI units
  - `test_config_change_respawns_ai` — changing AI count re-spawns correct number
  - `test_get_match_config_payload` — config payload includes all expected fields
  - `test_lobby_chat_basic` — host can send and retrieve chat messages
  - `test_lobby_chat_multiple_players` — multiple players' messages interleave correctly
  - `test_lobby_chat_not_in_game` — chat blocked when match is in_progress
  - `test_lobby_chat_message_truncated` — messages over 500 chars are truncated
  - `test_ready_check_ignores_ai` — ready check only considers human players
- Full test suite: **62 tests passing, 0 failures**
- Client builds cleanly (`vite build` — 0 errors)

### Chunk 4: Lobby Config Lock Fix — ✅ COMPLETE (Feb 12, 2026)

**Scope:** Bug #8 — host config controls lock after one change.

| Bug | Status | Files Changed |
|-----|--------|---------------|
| #8 Config controls lock | ✅ Fixed | `core/match_manager.py`, `GameStateContext.jsx` |

**Bug #8 Fixes Applied:**
- `update_match_config()` return dict was missing `host_id` — added `"host_id": match.host_id` to match `get_match_config_payload()`
- `CONFIG_CHANGED` reducer replaced `lobbyConfig` entirely — changed to spread-merge `{ ...state.lobbyConfig, ...action.payload.config }` so no fields are lost

**Testing:**
- Full test suite: **68 tests passing, 0 failures**
- Client builds cleanly (0 errors)

---

## Design Philosophy

**Core Principle:** Validate that the tick-based queue system supports:
1. **AI opponents** that feel challenging and fair
2. **Tactical depth** through vision limitations and combat options
3. **Replayability** through varied environments

**Stay Themeless:** Continue using abstract visuals (colored shapes, geometric tokens) to maintain flexibility for future theming (fantasy, sci-fi, modern, abstract).

**Terminology Standards:**
- "Units" (not heroes, characters, or monsters)
- "Actions" (not spells, abilities, or attacks)
- "Matches" (not battles, missions, or games)
- "Combatants" (humans or AI)

---

## Phase 2 Feature Set

### Feature 1: Three Map Varieties

**Purpose:** Test if environmental variation creates strategic depth and replayability.

**Specifications:**
- All maps remain 15x15 grid
- JSON-driven configurations
- Three distinct layouts:

**Map A: "Open Arena"**
- Obstacle density: 10-15%
- Layout: Minimal walls, large open spaces
- Strategic emphasis: Ranged combat advantage, positioning critical
- Spawn points: 8 positions around perimeter

**Map B: "Maze"**
- Obstacle density: 40-50%
- Layout: Narrow corridors, tight corners
- Strategic emphasis: Close-quarters combat, ambush opportunities
- Spawn points: 8 positions distributed through maze sections

**Map C: "Islands"**
- Obstacle density: 30%
- Layout: Clustered obstacles creating distinct zones
- Strategic emphasis: Zone control, flanking maneuvers
- Spawn points: 8 positions on different "islands"

**Lobby Integration:**
- Map selection dropdown during match creation
- Map preview thumbnail (optional for Phase 2)
- Default: Random selection if not specified

**Testing Questions:**
- Do players develop map preferences?
- Does map choice affect match outcomes?
- Do different maps encourage different tactics?
- Is 15x15 still the right size, or should maps vary in dimensions?

---

### Feature 2: AI Opponent System

**Purpose:** Enable solo testing and validate that non-human combatants work within the tick/queue system.

**Core Requirements:**
- AI entities function identically to players (position, HP, action queue, tick-based resolution)
- AI spawn at match start alongside humans
- AI respect field of view (cannot "see" through obstacles)
- AI use same action types as players (move, melee attack, ranged attack)

**AI Behavior (Phase 2: Single Behavior)**

**Aggressive AI:**
- **Decision Loop (each tick):**
  1. Calculate field of view
  2. Identify visible enemies
  3. If no enemies visible → patrol/idle
  4. If enemies visible → select nearest enemy as target
  5. If adjacent to target → queue melee attack
  6. If target in ranged attack range (and cooldown ready) → queue ranged attack
  7. Otherwise → queue move toward target

**AI Action Queue:**
- Uses same queue system as players (max 10 actions)
- For Phase 2: AI queues only 1 action per tick (simple reactive behavior)
- Future: AI could queue multiple actions for more complex tactics

**AI Stats:**
- HP: 100 (same as players)
- Melee damage: 15 (same as players)
- Ranged damage: 10 (same as players)
- Armor: 2 (same as players)
- Vision range: 7 tiles (same as players)

**AI Limitations (Intentional):**
- No "cheating" - AI cannot see through fog of war
- No perfect prediction - AI reacts to current state, doesn't predict player queues
- No difficulty scaling in Phase 2 (add Easy/Medium/Hard in Phase 3)

**Implementation Notes:**
- AI decision logic runs during tick processing, before action resolution
- AI treated as first-class combatants in all match systems
- Death, victory, combat log messages apply equally to AI

---

### Feature 3: Match Type Flexibility

**Purpose:** Support solo practice, PvP, PvE, and mixed human/AI scenarios.

**Match Types:**

**Pure PvP (Current System)**
- 2-8 human players
- No AI
- Existing lobby flow unchanged

**Solo PvE**
- 1 human player
- 1-7 AI opponents
- Player tests mechanics, learns maps, practices tactics

**Mixed Combatants**
- Any combination of humans and AI
- Total combatants ≤ 8
- Examples:
  - 2 humans + 6 AI opponents
  - 4 humans + 4 AI opponents
  - 1 human + 2 AI allies + 5 AI opponents

**Allied AI**
- Lobby creator can designate AI as allies (on player team)
- Allied AI target enemies, not teammates
- Allied AI function autonomously (no player control)
- Win condition: Team-based (human + allied AI win/lose together)

**Lobby Configuration:**

**Match Creation Screen:**
```
Create Match
├── Map Selection: [Open Arena ▼]
├── Match Type:
│   ○ PvP Only (humans only)
│   ○ Solo PvE (1 human vs AI)
│   ○ Mixed (configure below)
├── Human Slots: [1-8]
├── AI Opponents: [0-7]
├── AI Allies: [0-7]
└── Total Combatants: [X/8]
```

**Validation:**
- Total combatants (humans + AI opponents + AI allies) ≤ 8
- At least 2 total combatants required
- Solo PvE requires exactly 1 human slot

**Team Assignment:**
- **Team A:** Human players + AI allies
- **Team B:** AI opponents
- Teams cannot attack their own members
- Victory: Last team standing (all members of opposing team eliminated)

**Edge Case - AI vs AI:**
- If all humans disconnect/eliminated: AI continues until one team wins
- Match ends normally, logs final result

---

### Feature 4: Ranged Attack

**Purpose:** Add tactical depth through combat positioning and range management.

**Specifications:**

**Range:** 5 tiles from attacker position

**Line of Sight Required:**
- Must have clear path to target (no obstacles blocking)
- Uses same FOV calculation as vision
- Diagonal shots allowed if path is clear

**Targeting:**
- Can target any visible tile within range
- Attack fails if target tile is empty (no damage, cooldown consumed)
- Attack fails if target moves before action executes (queued attack on old position)

**Damage:** 10 (reduced from melee's 15)

**Cooldown:** 3 turns after use
- Tracked per player/AI
- Cooldown applies even if attack misses/fails
- Cannot queue ranged attack while on cooldown (action rejected)

**UI Indicators:**
- Action bar shows ranged attack button with cooldown counter
- When selected, highlight valid target tiles (in range + line of sight)
- Combat log shows ranged attack messages distinctly from melee

**Tactical Implications:**
- Ranged allows safer damage output (stay back, poke)
- Melee remains higher DPS if you can close distance
- Obstacles create safe zones from ranged attacks
- Cooldown prevents ranged spam, forces tactical timing

**Balance Philosophy (Phase 2):**
- Lower damage than melee compensates for safety
- Cooldown creates meaningful choice: "Do I ranged now or save for better moment?"
- Open maps favor ranged; maze maps favor melee

---

### Feature 5: Field of View (FOV)

**Purpose:** Add fog of war to create information asymmetry, scouting value, and ambush opportunities.

**Specifications:**

**Vision Range:** 7 tiles radius from unit position

**Line of Sight:**
- Blocked by obstacles
- Uses pure Python recursive shadowcasting algorithm (server-side, in `app/core/fov.py`)
- Bresenham's line algorithm for line-of-sight checks
- Recalculated each tick as units move

**What You Can See (Within FOV):**
- Enemy unit positions
- Enemy HP values
- Enemy queued action count (but not details)
- Allied unit positions (teammates)
- Obstacles and terrain
- Loot (if implemented in future)

**What You Cannot See (Outside FOV):**
- Enemy positions (units hidden in fog)
- Enemy HP or status
- Whether tiles are occupied

**Rendering:**
- Canvas grays out tiles outside FOV
- Units outside FOV are not rendered
- Last-known positions NOT shown (full fog of war)

**AI FOV:**
- AI units have independent FOV (7 tile radius)
- AI cannot "see" players outside their FOV
- Allied AI do NOT share vision with players (Phase 2 - independent)
- AI decision-making only uses visible information

**Team Vision (Phase 2):**
- Teammates do NOT share vision automatically
- Each unit (human or allied AI) has individual FOV
- Future Phase could add shared team vision

**Gameplay Implications:**
- **Scouting:** Moving forward reveals new areas
- **Ambush:** Units can hide around obstacles
- **Positioning:** High-ground/central positions see more
- **AI Behavior:** AI won't pursue if you break line of sight

**Combat Log:**
- Show actions only from visible units
- If enemy attacks you from outside FOV: "You were attacked from the shadows!"
- Encourages awareness and positioning

---

## Technical Architecture Updates

### New Entities

**Enemy AI Unit:**
- Inherits/mirrors player entity structure
- Fields: `id`, `name`, `type` (AI), `team`, `x`, `y`, `hp`, `alive`, `action_queue`, `vision_range`, `cooldowns`
- AI name generation: "AI-1", "AI-2", etc. (themeless)

**Map Configuration:**
- JSON structure: `{ "name", "width", "height", "obstacles": [{x, y}], "spawn_points": [{x, y}] }`
- Loaded at match creation based on selection

### Modified Systems

**Match State:**
- Add `ai_units` list alongside `players`
- Track teams: `team_a: [player_ids + ai_ally_ids]`, `team_b: [ai_opponent_ids]`
- Victory check: If all units of one team eliminated → opposing team wins

**Turn Resolution:**
- Before processing actions: run AI decision logic for all AI units
- AI actions added to queue just like player actions
- Process all actions (player + AI) in resolution phase

**FOV Calculation:**
- Each tick, calculate FOV for all units (players + AI)
- Store FOV results in match state
- Use FOV to filter what information is sent to each client
- AI decision logic only receives visible enemies

**Action Validation:**
- Ranged attack: check range, check line of sight, check cooldown
- Move: existing validation (tile walkable, not occupied)
- Melee: existing validation (adjacency)

**Cooldown Tracking:**
- Add `cooldowns` dict to each unit: `{ "ranged_attack": 0 }`
- Each tick, decrement cooldowns by 1 (min 0)
- On ranged attack use: set cooldown to 3
- Reject action if cooldown > 0

---

## Testing & Validation

### Feature Testing Checklist

**Map Varieties:**
- [ ] All 3 maps load correctly
- [ ] Obstacles render properly on each map
- [ ] Spawn points distribute combatants evenly
- [ ] Players can select maps in lobby
- [ ] Different maps create noticeably different gameplay

**AI Opponents:**
- [ ] AI spawns at match start
- [ ] AI moves toward visible enemies
- [ ] AI attacks when adjacent (melee)
- [ ] AI uses ranged attack when in range
- [ ] AI stops pursuing when enemy leaves FOV
- [ ] AI respects obstacles (doesn't walk through walls)
- [ ] AI death/victory handled correctly

**Match Types:**
- [ ] Pure PvP works (no regression)
- [ ] Solo PvE: 1 human vs 3 AI plays correctly
- [ ] Mixed: 2 humans + 2 AI allies vs 4 AI opponents plays correctly
- [ ] Allied AI targets enemies, not teammates
- [ ] Team victory condition works (last team standing)
- [ ] Lobby validation prevents invalid configurations

**Ranged Attack:**
- [ ] Ranged attack works at 5 tile range
- [ ] Line of sight blocking works (obstacles prevent shots)
- [ ] Damage reduced to 10 (vs melee 15)
- [ ] Cooldown applies (3 turns)
- [ ] Cannot ranged attack while on cooldown
- [ ] Attack fails gracefully if target moves away

**Field of View:**
- [ ] FOV calculates correctly (7 tile radius)
- [ ] Obstacles block vision
- [ ] Canvas grays out unseen tiles
- [ ] Units outside FOV are hidden
- [ ] AI cannot see through walls
- [ ] AI stops pursuing when player leaves FOV
- [ ] Combat log only shows visible actions

### Integration Testing

**Full Match Scenarios:**

**Scenario 1: Solo PvE**
- 1 human vs 3 AI (Open Arena map)
- Human uses ranged + melee to eliminate all AI
- AI pursues human, attacks when visible
- Match ends when all AI defeated

**Scenario 2: Team Battle**
- 2 humans + 2 AI allies vs 4 AI opponents (Maze map)
- Humans coordinate with allied AI
- FOV creates ambush opportunities
- Last team standing wins

**Scenario 3: Map Variety**
- Play same configuration (2v2) on all 3 maps
- Observe tactical differences
- Identify preferred map

**Scenario 4: Cooldown Management**
- Player uses ranged attack
- Verify 3-turn cooldown
- Attempt ranged attack during cooldown (should fail)
- After 3 turns, ranged available again

### Performance Benchmarks

- [ ] FOV calculation for 8 units: < 50ms
- [ ] AI decision logic for 8 AI: < 100ms
- [ ] Turn resolution (8 units, mixed actions): < 200ms
- [ ] Canvas rendering with FOV graying: 60fps maintained
- [ ] No memory leaks over 30-turn match

---

## Success Metrics

### Quantitative Metrics

**AI Quality:**
- AI completes matches without crashes: 100%
- AI makes "sensible" moves (pursues visible enemies): >80% of actions
- AI doesn't get stuck on obstacles: <5% of matches

**Replayability:**
- Players complete matches on all 3 maps: >90%
- Map preference variance: No single map >50% preferred (indicates all maps viable)

**Tactical Depth:**
- Ranged attack usage: 20-40% of attack actions (not ignored, not dominant)
- Cooldown expiry before use: <30% (indicates intentional timing, not spam)
- FOV-based ambushes: Observed in >25% of matches

**Performance:**
- Turn resolution time: <200ms for 8 combatants
- Client FPS: >55fps average (with FOV rendering)
- Zero crashes in 20 consecutive matches

### Qualitative Metrics

**Playtesting Feedback Questions:**

**AI Evaluation:**
- Does AI feel like a legitimate opponent?
- Is AI too easy, too hard, or appropriately challenging?
- Do AI behaviors feel predictable or exploitable?

**Map Evaluation:**
- Which map is most fun? Why?
- Do maps feel different, or same with different visuals?
- Is 15x15 the right size, or too large/small?

**FOV Evaluation:**
- Does fog of war add tension and tactical depth?
- Is vision range (7 tiles) too limiting or too generous?
- Do ambushes feel rewarding or frustrating?

**Ranged Combat Evaluation:**
- Is ranged attack useful, or is melee always better?
- Does 3-turn cooldown feel right (too long, too short)?
- Does range (5 tiles) create meaningful positioning choices?

**Overall:**
- Would you play this again?
- What's most fun about Phase 2 additions?
- What feels tedious or frustrating?

---

## Development Phases

### Week 1: Maps + FOV ✅ COMPLETE

**Backend:**
- ✅ Create map JSON loading system
- ✅ Implement FOV calculation using pure Python recursive shadowcasting
- ✅ Update match state to store per-unit FOV (via `_fov_cache` in match_manager)
- ✅ Filter broadcast data based on recipient FOV (per-player in websocket.py)

**Frontend:**
- ✅ Render 3 new map configurations
- ✅ Implement canvas FOV graying/hiding (drawFog in ArenaRenderer)
- ✅ Add map selection to lobby UI (dropdown in Lobby.jsx)
- Test FOV with manual player positioning

**Milestone:** Two players can play on all 3 maps with functional fog of war

---

### Week 2: Ranged Attack + Cooldowns ✅ COMPLETE

**Backend:**
- ✅ Add ranged attack action type (ActionType.RANGED_ATTACK)
- ✅ Implement line-of-sight validation (Bresenham in fov.py, can_ranged_attack in combat.py)
- ✅ Add cooldown tracking to unit state (cooldowns dict on PlayerState)
- ✅ Update turn resolver for ranged attack handling (Phase 2 in turn_resolver.py)

**Frontend:**
- ✅ Add ranged attack button to action bar (🏹 Ranged with cooldown counter)
- ✅ Show cooldown counter on button (disabled when on cooldown)
- ✅ Highlight valid ranged targets (orange highlights in Arena.jsx)
- ✅ Combat log shows ranged attack results (orange color in CombatLog)

**Milestone:** Player can use ranged attack with cooldown system working

---

### Week 3: AI System ✅ COMPLETE

**Backend:**
- ✅ Create AI entity model (uses PlayerState with unit_type='ai')
- ✅ Implement aggressive AI behavior logic (ai_behavior.py with A* pathfinding)
- ✅ AI decision loop integrated into tick processing (run_ai_decisions called in match_tick)
- ✅ AI respects FOV in decision-making (compute_fov per AI unit)

**Frontend:**
- ✅ Render AI units (diamond shapes in ArenaRenderer)
- ✅ AI actions appear in combat log
- ✅ AI death/victory handled in UI (HUD shows AI badges, team victory)

**Milestone:** Solo PvE match (1 human vs 3 AI) completes successfully

---

### Week 4: Lobby + Match Types ✅ COMPLETE

**Backend:**
- ✅ Update lobby endpoints to support match type configuration (MatchConfig with match_type, ai_opponents, ai_allies)
- ✅ AI spawn logic (_spawn_ai_units in match_manager.py)
- ✅ Team assignment and tracking (team_a/team_b in MatchState)
- ✅ Team-based victory condition (check_team_victory in combat.py)

**Frontend:**
- ✅ Match creation UI with AI configuration (Lobby.jsx: map select, match type, AI sliders)
- ✅ Team indicators in HUD (team colors, labels)
- ✅ Allied AI visual differentiation from enemies (🤖 badges, ally/enemy labels)
- ✅ Match summary shows team results (Team A/B wins)

**Milestone:** Mixed match (2 humans + 2 AI allies vs 4 AI) completes with team victory

---

### Week 5: Integration, Testing, Polish — PAUSED FOR BUG FIXES

**Status:** Week 5 activities paused. Critical bugs discovered during playtesting require fixes before continuing.

**Issues Found:**
- See Phase 2.1: Critical Bug Fixes & Improvements section above
- 7 critical bugs identified
- All bugs must be fixed before Phase 3 planning

**Original Week 5 Focus:**
- Full integration testing (all scenarios)
- Balance tuning (ranged damage, cooldowns, AI aggression)
- Bug fixes from playtesting
- Performance optimization (FOV calculations)
- Gather structured feedback

**Revised Week 5 Focus:**
- Fix all Phase 2.1 bugs (estimated 2 weeks)
- Complete all Phase 2.1 test scenarios
- Validate no regressions in existing features
- Resume original Week 5 activities after bug fixes complete

**Milestone:** Phase 2.1 bug fixes complete, then Phase 2 complete, ready for Phase 3 planning

---

### Week 6-7: Phase 2.1 Bug Fixes — CURRENT PRIORITY

**Focus:** Fix all 7 critical bugs identified in playtesting

**Required Fixes:**
1. Team assignment broken in PvP matches
2. Tick rate too slow (10s → 5s)
3. AI behavior - lack of active scouting
4. Team field of view not shared
5. AI units not visible in lobby player list
6. Ghost players persist after leaving lobby
7. Match configuration should be inside lobby (UX redesign)
8. Lobby config controls lock after one change

**New Feature:**
- Lobby chat window

**Deliverables:**
- All bugs fixed (8 total)
- All Phase 2.1 test scenarios passing
- Lobby UX redesigned with in-lobby configuration
- Chat functionality working

**Milestone:** Phase 2.1 complete, resume Phase 2 integration testing

---

## Phase 2 → Phase 3 Transition

**BLOCKED:** Phase 3 planning cannot begin until Phase 2.1 bug fixes are complete and validated.

### Go/No-Go Criteria (After Phase 2.1 Complete)

**GREEN LIGHT for Phase 3 if:**
- All Phase 2.1 bugs fixed and validated
- AI feels challenging and fair (not exploitable or frustrating)
- FOV adds tactical depth (players actively use vision mechanics)
- Ranged attack creates positioning gameplay (not ignored or dominant)
- Maps provide variety (different tactics emerge on different maps)
- Shared team vision improves team gameplay
- Players request more content (skills, loot, progression)

**YELLOW LIGHT (iterate Phase 2) if:**
- AI needs behavior improvements (too easy, too predictable)
- Balance issues (ranged too weak/strong, FOV too limiting/generous)
- Technical performance problems (lag, FPS drops)
- Need more maps or match types before adding complexity

**RED LIGHT (pivot or stop) if:**
- Core loop still not fun even with additions
- AI fundamentally doesn't work with tick system
- FOV makes game too frustrating (can't find enemies)
- Players don't engage with new mechanics

### Phase 3 Direction (Conditional on Green Light)

**Decision will be made after Phase 2.1 completion and additional playtesting.**

**Option A: More Depth (Still Match-Based)**
- Skills/abilities system (3-5 abilities per unit)
- Loot drops (health, damage, speed pickups)
- Match-scoped progression (level up during match)
- More AI behaviors (defensive, support, ranged-focused)

**Option B: Persistent World**
- Territory control layer
- Player structures (buildings, defenses)
- Guild/faction systems
- Match results affect persistent world state

**Option C: Content Expansion**
- 10+ maps with themes
- Multiple game modes (Deathmatch, King of Hill, Horde)
- AI difficulty levels (Easy, Medium, Hard, Elite)
- Cosmetic customization (unit appearance)

**Phase 3 direction to be discussed after Phase 2.1 validation.**

---

## Known Limitations (Phase 2)

**Intentional Constraints:**
- Single AI behavior (aggressive only)
- No AI difficulty scaling
- Independent FOV (no shared team vision)
- AI queues only 1 action per tick (reactive, not strategic)
- No loot or progression systems
- No skills beyond move/melee/ranged
- Themeless (abstract visuals continue)

**Technical Debt Accepted:**
- AI pathfinding uses A* with Chebyshev distance heuristic (much better than basic step-toward; avoids getting stuck on obstacles)
- No client-side prediction for FOV changes (slight delay on reveal)
- Match size still capped at 8 (not stress-tested with more combatants)

**These limitations are acceptable for Phase 2 validation goals. Address in Phase 3 if needed.**

---

## Appendix: Configuration Examples

### Map JSON Structure

```json
{
  "name": "Open Arena",
  "width": 15,
  "height": 15,
  "obstacles": [
    {"x": 7, "y": 7},
    {"x": 7, "y": 8},
    {"x": 8, "y": 7},
    {"x": 8, "y": 8}
  ],
  "spawn_points": [
    {"x": 1, "y": 1},
    {"x": 13, "y": 1},
    {"x": 1, "y": 13},
    {"x": 13, "y": 13},
    {"x": 7, "y": 1},
    {"x": 1, "y": 7},
    {"x": 13, "y": 7},
    {"x": 7, "y": 13}
  ]
}
```

### AI Configuration (Match Creation Payload)

```json
{
  "match_type": "mixed",
  "map": "maze",
  "max_players": 2,
  "ai_opponents": 4,
  "ai_allies": 2,
  "tick_rate": 5
}
```

---

**Document Version:** 2.0  
**Created:** February 12, 2026  
**Last Updated:** February 12, 2026  
**Status:** Implementation Complete — Testing Phase  
**Prerequisites:** Phase 1 Arena Prototype Complete  

---

## Implementation Notes for Next Agent

### Architecture Decisions Made

1. **FOV is 100% server-side.** The server computes FOV for every unit each tick using recursive shadowcasting (`app/core/fov.py`). The client receives a `visible_tiles` array and renders fog based on it. There is NO client-side FOV computation.

2. **AI uses PlayerState, not a separate model.** AI units are regular `PlayerState` objects with `unit_type="ai"`. They live in the same `_player_states` dict as humans. This simplifies combat resolution — everything treats them identically.

3. **A* pathfinding with Chebyshev heuristic.** AI uses true A* pathfinding (`app/core/ai_behavior.py`) instead of simple step-toward. This prevents AI from getting stuck on obstacles. The heuristic allows 8-directional movement.

4. **Turn resolution is 4-phase.** Order: tick cooldowns → resolve movement → resolve ranged → resolve melee. This means ranged fires after movement (you can dodge), but melee fires last (closing distance is rewarded).

5. **FOV cache lives in match_manager.** `_fov_cache[match_id]` stores `{player_id: set_of_visible_tiles}`. It's recalculated twice per tick (before AI decisions, and after movement resolution). Cleared on match removal.

6. **Team system is simple.** Team A = humans + AI allies. Team B = AI opponents. `are_allies()` in combat.py prevents friendly fire in both melee and ranged. Victory is checked via `check_team_victory()`.

7. **Lobby sends config as nested JSON body.** The `/api/lobby/create` endpoint expects `{ "request": { "username": "..." }, "config": { "map_id": "...", "match_type": "...", ... } }`. FastAPI unpacks this into `PlayerJoinRequest` + `MatchConfig`.

### Key File Map

| File | Purpose |
|------|--------|
| `server/app/core/fov.py` | Recursive shadowcasting + Bresenham LOS |
| `server/app/core/ai_behavior.py` | A* pathfinding + aggressive AI decision loop |
| `server/app/core/combat.py` | Melee + ranged damage, cooldowns, team victory |
| `server/app/core/turn_resolver.py` | 4-phase resolution (cooldown→move→ranged→melee) |
| `server/app/core/match_manager.py` | Match lifecycle, AI spawning, FOV cache, team assignment |
| `server/app/services/websocket.py` | Tick loop, FOV computation, AI execution, per-player broadcasts |
| `server/configs/maps/*.json` | 4 map definitions: arena_classic, open_arena, maze, islands |
| `client/src/context/GameStateContext.jsx` | Client state: FOV, teams, AI IDs, action modes |
| `client/src/canvas/ArenaRenderer.js` | Canvas rendering: fog overlay, AI diamonds, ranged highlights |
| `client/src/components/Lobby/Lobby.jsx` | Match config UI: map select, match type, AI sliders |

### Known Gaps / Future Work

- **No unit tests for new code.** `fov.py`, `ai_behavior.py`, and updated `combat.py`/`turn_resolver.py` need test coverage. The old tests in `tests/` may need updating for the new function signatures.
- **No shared team vision.** Each unit has independent FOV. Phase 3 could add shared team vision.
- **AI queues 1 action per tick.** Intentionally simple for Phase 2. Phase 3 could add multi-action AI planning.
- **No AI difficulty scaling.** All AI use the same aggressive behavior. Phase 3 could add Easy/Medium/Hard.
- **No client-side prediction.** FOV reveals have a 1-tick delay. Could add optimistic prediction in Phase 3.
- **WebSocket `match_tick` is the hot path.** If performance degrades with 8 units, profile FOV + A* first.
- **The `PlayerJoinRequest` model** is in `server/app/models/player.py` — it has just a `username: str` field.
- **Redis is not used.** All state is in-memory Python dicts. Redis client exists but match state uses `_active_matches` / `_player_states` dicts in match_manager.py.
- **Min players to start is 2** (set in `config.py`). For Solo PvE testing, you may need to set `ARENA_MIN_PLAYERS_TO_START=1` as an env variable, OR the AI spawning may count toward this — verify during testing.

---

## Phase 2.1 Refinement: AI Behavior & Team Colors — ✅ FIXED

**Date:** February 12, 2026

### Refinement #1: AI Too Passive / Only Uses Ranged Attacks — ✅ FIXED

**Issue Observed:**
Enemy AI appeared sluggish and mostly stationary. Combat logs showed AI units only performing ranged attacks. They did not actively close distance to engage in melee combat, making fights slow and AI feel passive. AI-vs-AI fights (allied AI vs enemy AI) also appeared non-existent because both sides stood at range trading slow ranged shots that the player rarely could see (due to FOV filtering).

**Root Cause:**
The AI decision priority in `decide_ai_action()` was: melee (if adjacent) → **ranged (if in range + LOS + cooldown ready)** → move toward target. Since AI spawn points on most maps are within 5-tile ranged range of each other, the AI would fire a ranged shot (10 dmg, 3-turn cooldown), then idle for 3 turns, then fire again. With 100 HP and 2 armor (8 net damage per shot), an AI-vs-AI ranged duel took ~50 turns (~4 minutes) to resolve. The AI **never closed distance** because ranged always took priority over movement.

**Fix Applied:**
Rewrote the AI combat decision priority in `server/app/core/ai_behavior.py` to be melee-aggressive:

1. **Adjacent → melee attack** (unchanged, 15 damage per turn)
2. **Within 3 tiles → always rush to melee** (A* pathfinding, ignores ranged)
3. **Within 3 tiles + can't move → ranged fallback** (blocked by obstacles/units)
4. **Far away (>3 tiles) + ranged ready + LOS → ranged harass** (shoot while closing)
5. **Far away + no ranged → move toward target** (A* pathfinding)
6. **Completely stuck + ranged ready → ranged** (last resort)
7. **Completely stuck + no ranged → wait**

**Impact:**
- AI now actively closes distance every turn, reaching melee range within 2-3 turns
- Melee fights resolve in ~8 turns (15 dmg - 2 armor = 13 dmg/turn vs 100 HP) instead of ~50
- AI-vs-AI fights now happen quickly and visibly
- Ranged is still used at long range as harassment, preserving tactical variety

**Files Changed:** `server/app/core/ai_behavior.py`

---

### Refinement #2: Enemy AI and Allied AI Don't Fight Each Other — ✅ FIXED

**Issue Observed:**
Enemy AI (team B) and allied AI (team A) did not appear to engage each other in combat. Players expected AI from opposing teams to fight.

**Root Cause:**
The targeting logic was actually correct — `unit.team == ai.team` properly identifies enemies vs allies. Both allied and enemy AI would target each other. However, **Refinement #1 masked this**: both AIs stood at ranged distance trading very slow shots (1 shot every 4 turns, ~8 damage each). Since this happened outside the player's FOV in most cases, the player never saw it in their combat log. The 50-turn resolution time meant AI-vs-AI fights almost never concluded during a normal match.

**Fix Applied:**
Solved entirely by Refinement #1. With the new melee-aggressive priority, AI on opposing teams now rush each other and engage in melee combat, which resolves quickly. No additional targeting logic changes were needed.

**Files Changed:** Same as Refinement #1 — `server/app/core/ai_behavior.py`

---

### Refinement #3: Same-Team Units Have Different Colors — ✅ FIXED

**Issue Observed:**
Players on the same team displayed in different colors (e.g., human allies as blue, AI allies as green). Enemies similarly showed as both red (human) and orange-red (AI). This made it confusing to identify who was on which team during a match.

**Root Cause:**
`getUnitColor()` in `client/src/canvas/ArenaRenderer.js` assigned 4 different colors based on whether a unit was human or AI AND whether they were ally or enemy:
- Self / Human ally: Blue `#4a9ff5`
- AI ally: **Green** `#4af59f`
- Human enemy: Red `#f54a4a`
- AI enemy: **Orange-red** `#ff6644`

This caused same-team units to appear in different colors, defeating the purpose of team coloring.

**Fix Applied:**
Simplified `getUnitColor()` to use **team-based coloring only**:
- Self / Any ally (human or AI): **Blue** `#4a9ff5`
- Any enemy (human or AI): **Red** `#f54a4a`

The human vs AI distinction is already visually communicated by **shape** (circles for humans, diamonds for AI), so color no longer needs to encode this information.

Updated `TEAM_COLORS` constant to remove `ai_ally` and `ai_enemy` entries.

**Files Changed:** `client/src/canvas/ArenaRenderer.js`

---

### Refinement Summary

| # | Issue | Root Cause | Fix | Files |
|---|-------|-----------|-----|-------|
| R1 | AI passive / ranged-only | Ranged priority > move priority | Melee-aggressive AI: rush within 3 tiles, ranged only at distance | `ai_behavior.py` |
| R2 | AI teams don't fight | Masked by slow ranged duels + FOV hiding | Solved by R1 — fast melee engagement | `ai_behavior.py` |
| R3 | Same-team different colors | 4 colors by unit_type + team | 2 colors by team only (shape = unit_type) | `ArenaRenderer.js` |

---

## AI Intelligence Overhaul — 5 Targeted Fixes (Feb 12, 2026)

**Status:** ✅ COMPLETE

**Problem Statement:**
AI behavior was functional but unintelligent. Specific issues observed:
1. AI wanders aimlessly near spawn instead of seeking enemy targets
2. Ally AI ignores shared team FOV — doesn't react to enemies you've spotted
3. AI loses all awareness of enemies the moment they leave individual FOV
4. Ally AI never reinforces teammates under attack
5. Target selection is purely distance-based (ignores low-HP or threatening enemies)

**Design Principle:** Smart but not overcomplicated. All fixes are targeted additions to the existing pursue → melee → ranged → patrol decision chain. No architectural rewrite needed.

---

### AI Fix #1: Shared Team FOV for AI — ✅ COMPLETE

**Problem:** AI computed only its own individual FOV via `compute_fov()` and used that exclusively to spot enemies. The server already computed shared team FOV via `get_team_fov()` for human players, but this data was never passed to AI decision logic.

**Impact:** Ally AI couldn't see enemies that you or other teammates had spotted. AI felt disconnected from the team.

**Fix Applied:**
- Added optional `team_fov: set[tuple[int, int]] | None` parameter to `decide_ai_action()`
- Added optional `team_fov_map: dict[str, set[tuple[int, int]]] | None` parameter to `run_ai_decisions()`
- AI now uses the union of its own FOV + team shared FOV to detect enemies: `visible_tiles = own_fov | team_fov`
- In `websocket.py`, pre-compute team FOV map **between** Step 1 (FOV computation) and Step 2 (AI decisions), then pass `ai_team_fov_map` into `run_ai_decisions()`
- AI on team "a" gets team A's combined FOV, team "b" gets team B's, etc.

**Files Changed:** `server/app/core/ai_behavior.py`, `server/app/services/websocket.py`

---

### AI Fix #2: Last-Known Enemy Memory — ✅ COMPLETE

**Problem:** When an enemy walked out of FOV, AI immediately forgot about them and switched to aimless patrol. This caused the frustrating "chase → lose sight for 1 tile → wander to opposite corner" behavior.

**Fix Applied:**
- Added module-level `_enemy_memory` dict: `{ai_id: {enemy_id: (x, y, turns_since_seen)}}`
- New `_update_enemy_memory()` function called every decision tick:
  - Visible enemies: store/refresh position (age = 0)
  - Non-visible enemies: increment age by 1
  - Dead or expired enemies (age > 3 turns): remove from memory
- New `_pursue_memory_target()` function:
  - When AI has no visible enemies, checks memory for last-known positions
  - Picks the freshest (lowest age) target, paths toward it via A*
  - If AI reaches the remembered position and enemy isn't there, clears that entry
- Memory expiry constant `_MEMORY_EXPIRY_TURNS = 3` (configurable)
- Memory cleaned up for dead AI units and on match end via `clear_ai_patrol_state()`

**Decision Priority:**
When no enemies are visible: Memory targets → Ally reinforcement → Patrol (falls through in order)

**Files Changed:** `server/app/core/ai_behavior.py`

---

### AI Fix #3: Ally Reinforcement Behavior — ✅ COMPLETE

**Problem:** When a teammate was in combat (adjacent to an enemy), idle AI with no targets would ignore the fight entirely and wander off on patrol routes. Teams never felt coordinated.

**Fix Applied:**
- New `_reinforce_ally()` function checks if any same-team ally is adjacent to an enemy
- If an ally is in combat, the idle AI paths toward the nearest embattled ally instead of patrolling
- Uses existing `is_adjacent()` from the combat module to detect ally-in-combat status
- Picks nearest ally in combat by Manhattan distance, paths via A*
- Only triggers when AI has no visible enemies AND no memory targets (lower priority than direct engagement)

**Behavior Flow (no enemies visible):**
1. Check last-known enemy positions → pursue if any
2. Check if any ally is fighting → move to reinforce
3. Fall back to patrol scouting

**Files Changed:** `server/app/core/ai_behavior.py`

---

### AI Fix #4: Center-Biased Patrol Waypoints — ✅ COMPLETE

**Problem:** `_pick_patrol_waypoint()` scored candidates purely by **distance from AI** (farthest = best). This meant AI spawned on one edge of the map would patrol to the opposite edge, then the opposite corner, then back — never naturally moving through the center where combat is most likely to happen.

**Fix Applied:**
- Reworked scoring formula in `_pick_patrol_waypoint()`:
  - **Distance from self:** Still valued (want to move away from current area)
  - **Center proximity bonus:** New — tiles closer to map center score higher (multiplied by 0.5 weight)
  - **Visited penalty:** Increased from -3.0 to -5.0 (stronger avoidance of revisited tiles)
- `center_x = grid_width / 2.0`, `center_y = grid_height / 2.0` computed per call
- `center_bonus = max(0, grid_width - dist_to_center)` — higher when tile is closer to center
- Still uses top-8 randomized selection to prevent AI convergence

**Net Effect:** AI naturally sweeps toward the map center and contested areas instead of hugging map edges near their spawn.

**Files Changed:** `server/app/core/ai_behavior.py`

---

### AI Fix #5: Weighted Target Selection — ✅ COMPLETE

**Problem:** Target selection used `min(enemies, key=manhattan_distance)` — pure distance only. This caused AI to ignore a 5 HP enemy in favor of a 100 HP one that was 1 tile closer. AI also didn't prioritize enemies threatening their allies.

**Fix Applied:**
- New `_pick_best_target()` function replaces the simple `min(distance)`:
  - **Distance penalty:** -1 per Chebyshev tile (closer is better)
  - **Low HP bonus:** +5 if target is below 30% max HP (focus fire on wounded)
  - **Threat bonus:** +3 if target is adjacent to an ally (protect teammates)
- Returns the highest-scored enemy
- Uses `max(enemies, key=target_score)` for selection

**Scoring Example (15×15 map):**
| Scenario | Distance | HP% | Near Ally? | Score |
|----------|----------|-----|-----------|-------|
| 3 tiles, full HP, alone | -3 | 0 | 0 | **-3** |
| 5 tiles, 20% HP, alone | -5 | +5 | 0 | **0** |
| 4 tiles, full HP, hitting ally | -4 | 0 | +3 | **-1** |
| 2 tiles, 10% HP, hitting ally | -2 | +5 | +3 | **+6** ← top priority |

**Files Changed:** `server/app/core/ai_behavior.py`

---

### AI Overhaul — WebSocket Integration Change

**File:** `server/app/services/websocket.py`

**Change:** In `match_tick()`, team FOV is now pre-computed **between** Step 1 (FOV computation for all units) and Step 2 (AI decisions). The `ai_team_fov_map` dict is built as `{"a": team_a_fov, "b": team_b_fov, ...}` and passed into `run_ai_decisions()` via the new `team_fov_map` keyword argument.

Previously, team FOV was only calculated in Step 6 (for human player payloads). Now it's calculated earlier so AI can benefit from it too.

---

### AI Overhaul Summary

| # | Fix | What Changed | Key New Functions |
|---|-----|-------------|------------------|
| 1 | Shared team FOV | AI uses ally vision to spot enemies | Modified `decide_ai_action()`, `run_ai_decisions()` |
| 2 | Last-known enemy memory | AI pursues enemies after they leave FOV (3 turns) | `_update_enemy_memory()`, `_pursue_memory_target()` |
| 3 | Ally reinforcement | Idle AI paths to help teammates in combat | `_reinforce_ally()` |
| 4 | Center-biased patrol | Waypoints favor map center over random far tiles | Modified `_pick_patrol_waypoint()` |
| 5 | Weighted target selection | Scores enemies by HP, threat, and distance | `_pick_best_target()` |

**Files Changed:** `server/app/core/ai_behavior.py`, `server/app/services/websocket.py`

**AI Decision Priority (full chain):**
```
1. Dead? → skip
2. Visible enemies? → engage (weighted target selection)
   a. Adjacent → melee attack
   b. Within 3 tiles → rush to melee
   c. Far + ranged ready + LOS → ranged attack
   d. Otherwise → A* path toward target
3. No visible enemies:
   a. Last-known enemy position in memory? → pursue
   b. Ally in combat? → reinforce
   c. None of the above → patrol (center-biased waypoints)
```
