# Arena — Changelog

All notable changes to this project will be documented in this file.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

---

## [v0.1.10] - 2026-03-21 — Smarter Heroes, Better Loot

### Fixed
- **Leader explore_room ↔ patrol_move oscillation reduced** — Explore path now checks leader's `_position_history` before returning a MOVE; if the proposed step is a backtrack to last turn's tile, it falls through to patrol. Oscillation pairs dropped 41%, overall oscillation rate down 2.8pp. (`ai_behavior.py` — `_decide_aggressive_action()`, block 4e)
- **Follower trail-moving oscillation eliminated** — `follow_trail_moving` now rejects backtrack steps via position history check. Follower self-oscillations dropped 97%; `stall_breaker_yield` WAITs down 35%; `oscillation_suppressed` WAITs down 70%. (`ai_stances.py` — `_decide_follow_action()`)
- **Explore suppression thresholds tuned** — A↔B cycle detection raised from 6→8 positions, broad stall bounding box from 8→12 positions with ≤2 tile box, suppression cooldown 20→10 turns, lift distance 5→3 Manhattan. `explore_room` decisions up 3.75x; `random_adjacent_move` eliminated. (`ai_behavior.py`)
- **Patrol fallback now directed** — `_random_adjacent_move()` accepts `exploration_hint`; leaders step toward nearest unexplored room entrance (Manhattan distance) instead of random tile. All 10 random fallbacks replaced by 27 directed moves. (`ai_patrol.py`, `ai_behavior.py`)
- **purge_unwanted_items() respects class-lock and armor affinity** — Now mirrors `find_best_party_recipient()` equip gates so melee weapons can't appear as "upgrades" for casters. (`equipment_manager.py`)
- **Leader promotion works for all AI team prefixes** — `deaths_phase.py` now accepts both `"pvpve-ai-"` and `"ai-"` prefixed units. Eliminated 232 wasted `follow_no_owner` WAITs per 10-match sample.
- **Oscillation suppression no longer fires on simple reversals** — Single A→B→A reversal now only clears stale waypoint; WAIT requires extended criteria (6+ positions ≤2 unique tiles or 8+ in ≤3-tile box). Hero `oscillation_suppressed` WAITs down 54%. (`ai_behavior.py`)
- **Displaced equipment redistribution pass** — Phase 28I scans all team inventories after auto-equip, finds best recipient, transfers, and triggers equip. Runs up to 3 cascade passes. Stranded upgrades dropped from 22→0 per match; items traded 5→31; equipment health score 75→95. (`interaction_phase.py`)

### Added
- **Oscillation suppression deadlock broken** — Hard timeout (`_MAX_SUPPRESS_TURNS = 30`) unconditionally lifts suppression after 30 ticks, clears `_visited` history. Leader decisions increased 6.6x; items picked up +37%; items traded +51%. (`ai_behavior.py`)
- **Patrol waypoint all-visited fallback** — `_pick_patrol_waypoint()` detects when all candidates are visited and disables the −15.0 visited penalty for that selection. (`ai_patrol.py`)
- **Follower autonomous wander** — When leader is stationary 5+ ticks, followers make a random adjacent move (`follow_autonomous_wander`) instead of WAITing. (`ai_stances.py`)
- **Dev Overlay: Equipment & Inventory Inspector** — Backtick → Inspect ON → click any unit to see equipment (weapon/armor/accessory with rarity colors, stats, affixes, set info) and scrollable inventory (X/10 capacity, consumable icons). Works on ALL units including AI heroes and enemies via `dev_get_unit_inventory` endpoint. Auto-refreshes every 3s. (7 files: `equipment_manager.py`, `match_manager.py`, `message_handlers.py`, `App.jsx`, `useDevOverlay.js`, `DevOverlayPanel.jsx`, `Arena.jsx`, `_dev-overlay.css`)
- **PVPVE Batch Tool: Equipment Management Report** — `--equipment-report` flag for `batch_pvpve.py` with spawn gear, equipment events, per-team breakdown, final gear, potion economy, diagnostics, health score (0-100), inventory contents, stranded upgrades detection, and batch summary.

### Files Changed
- `server/app/core/ai_behavior.py`
- `server/app/core/ai_stances.py`
- `server/app/core/ai_patrol.py`
- `server/app/core/equipment_manager.py`
- `server/app/core/turn_phases/deaths_phase.py`
- `server/app/core/turn_phases/interaction_phase.py`
- `server/app/core/match_manager.py`
- `server/app/services/message_handlers.py`
- `server/batch_pvpve.py`
- `client/src/App.jsx`
- `client/src/hooks/useDevOverlay.js`
- `client/src/components/DevOverlay/DevOverlayPanel.jsx`
- `client/src/components/Arena/Arena.jsx`
- `client/src/styles/components/_dev-overlay.css`

---

## [v0.1.9b] - 2026-03-20 - Leader Explore/Patrol Oscillation Fix

### Fixed
- **Leader explore_room ↔ patrol_move oscillation reduced** — Team leaders alternated between exploring toward an unexplored room entrance and patrol waypoint scouting on consecutive turns. When explore_room proposed a step back toward the leader's immediately previous tile, the two subsystems fought over direction, creating A→B→A bouncing. The explore_room code path now checks the leader's position history: if the proposed step is a backtrack to last turn's position, it falls through to patrol (which has its own anti-backtrack guard), preventing the two systems from pulling the leader in opposite directions.

### Simulation Results (PvPvE, 150 turns, seed 100)

| Metric | Before (RC1 only) | After (RC1+RC2) | Change |
|--------|-------------------|-----------------|--------|
| `explore_room` ↔ `patrol_move` pairs | 22 | 13 | **-41%** |
| Overall oscillation rate | 12.0% | 9.2% | **-2.8pp** |
| `explore_room` actions | 33 | 131 | **+297%** |
| `patrol_move` actions | 51 | 135 | **+165%** |
| Total hero MOVE actions | 1121 | 1776 | **+58%** |

### Cross-Validation (seed 42, 100 turns)

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Total oscillation events | 112 | 70 | **-37%** |
| Oscillation rate | 9.1% | 7.0% | **-2.1pp** |

### Files Changed
- `server/app/core/ai_behavior.py` — `_decide_aggressive_action()`: Added position history backtrack rejection in the strategic exploration block (4e)

### Test Results
- 4040 tests passing (0 regressions)

---

## [v0.1.9a] - 2026-03-20 - Follower Trail-Moving Oscillation Fix

### Fixed
- **AI followers no longer oscillate between tiles when trailing a moving leader** — When a team leader moved through corridors or doorway chokepoints, followers within distance 1 would trigger the `follow_trail_moving` tether and compete for the same 2-3 adjacent tiles. The movement batch resolver picks winners each tick, shifting the occupied set and causing A* to send losers right back to their previous position on the next turn. This created sustained A→B→A tile-swapping visible as followers rapidly bouncing between two tiles, especially near doors where geometry forces tight formations.

### Root Cause
The `follow_trail_moving` code path in `_decide_follow_action()` had no anti-oscillation guard. It would always return the A* result regardless of whether that step was a backtrack to the follower's immediately previous position. The main oscillation suppressor in `run_ai_decisions()` only catches this when no enemies are nearby (Chebyshev ≤ 3), so the follower bouncing persisted near combat zones.

### Fix
Before the `follow_trail_moving` path returns a MOVE, it now checks the follower's `_position_history` from `ai_behavior.py`. If the proposed next step matches the position the follower occupied last turn (A→B→A), the move is skipped and the follower falls through to idle/chest-seek behavior. This one-tick pause breaks the oscillation cycle without affecting normal trailing when the leader is making forward progress.

### Simulation Results (PvPvE, 150 turns, seed 100)

| Metric | Before Fix | After Fix | Change |
|--------|-----------|-----------|--------|
| `follow_trail_moving` ↔ self oscillations | 61 | 2 | **-97%** |
| `stall_breaker_yield` WAITs | 222 | 144 | **-35%** |
| `oscillation_suppressed` WAITs | 96 | 29 | **-70%** |
| Total A→B→A oscillation events | 252 | 134 | **-47%** |
| Oscillation rate (% of MOVE actions) | 13.8% | 12.0% | **-1.8pp** |
| `follow_trail_moving` actions | 341 | 87 | **-74%** |

### Files Changed
- `server/app/core/ai_stances.py` — `_decide_follow_action()`: Added position history check in the leader-is-moving tether block to reject backtrack steps

### Test Results
- 4040 tests passing (0 regressions)

---

## [v0.1.9] - 2026-03-20 - Match Manager Modularization

**Architecture refactoring** - broke down the monolithic `match_manager.py` (3,220 lines, 55+ functions) into 9 focused sub-modules. Zero gameplay changes; purely internal code quality improvement enabling faster future development.

### Refactored
- **Phase 0:** Created `match_manager_BACKUP.py` safety copy (3,220 lines, 125 KB)
- **Phase 1:** Extracted `match_store.py` - single source of truth for all 14 shared state dicts + `MAX_QUEUE_SIZE` constant
  - `_active_matches`, `_player_states`, `_action_queues`, `_fov_cache`, `_lobby_chat`, `_class_selections`, `_hero_selections`, `_hero_ally_map`, `_username_map`, `_kill_tracker`, `_combat_stats`, `_match_timeline`, `_controlled_hero_map`, `_wave_state`, `_dev_mode_players`
  - Updated 5 already-extracted modules (`hero_manager`, `party_manager`, `equipment_manager`, `wave_spawner`, `auto_target`) to import from `match_store` instead of `match_manager`
- **Phase 2:** Extracted `action_queue.py` - 6 functions for persistent player action queue operations (queue, pop, clear, remove, get) with auto-target-aware clearing
- **Phase 3:** Extracted `fov_manager.py` - FOV cache accessors, team FOV union, dev mode toggles
- **Phase 4:** Extracted `match_payloads.py` - WebSocket payload builders (match start, game state, turn update); pure serializers with no side effects
- **Phase 5:** Extracted `lobby_config.py` - lobby chat, class selection, match config operations
- **Phase 6:** Extracted `loadout_generator.py` - enemy and hero equipment generation with rarity/floor scaling
- **Phase 7:** Extracted `dungeon_manager.py` - dungeon lifecycle, WFC procedural generation, room-based enemy spawning, floor progression
- **Phase 8:** Extracted `pvpve_manager.py` - PVPVE match flow orchestration with team distribution and diagonal-opposite spawn zones

### Added
- `ai_exploration.py` - room graph construction (`build_room_graph`), per-team room discovery/clearance tracking, unexplored room queries; foundation for strategic room-aware exploration
- `batch_pvpve.py` - batch PVPVE simulation runner for validation
- `match-manager-split-plan.md` - architecture plan document
- `phase-strategic-exploration.md` - strategic exploration design spec
- AI behavior audit and stalling analysis documentation

### Maintained
- Backward compatible - `match_manager.py` re-exports all symbols, zero import changes needed in callers
- 4040 tests passing - zero regressions

---

## [v0.1.8] - 2026-03-18 - Dungeon Lighting, Door System, HUD Overhaul & AI Upgrades

**Published release** rolling up v0.1.7a through v0.1.7p. Major additions: prop lighting system with ambient darkness and fog-of-war light modulation, room door system with chokepoint separators, 7 new room archetypes with focal prop budget system, complete HUD overhaul (player/party HP bars, minimap relocation, 4-row grid layout), 7 new skill particle effects, door-aware AI pathfinding for all units, AI chest seeking for hero allies, unique class composition for AI parties, PVPVE location-based chest tiers, loot rarity rebalance, and multiple bug fixes. 3987 tests passing.

See sub-entries below (v0.1.7a--v0.1.7p) for full technical details.

---

## [v0.1.7w] - 2026-03-20 - AI Oscillation Fix (Explore / Chest-Seek / Patrol Conflict)

### Fixed
- **Root cause**: `explore_room`, `aggro_chest_seek`, and `patrol_move` fought over the leader's movement on alternating turns, causing parties to permanently oscillate between 2 tiles (especially after opening a door or spotting a chest).
- **Chest-seek oscillation** — Added `_chest_seek_suppressed` set parallel to `_explore_suppressed`. When oscillation is detected and the leader is stuck in a 2-tile cycle or confined to a 3×3 bounding box, both `explore_room` and `aggro_chest_seek` are suppressed so patrol's stale-area detector can force a distant waypoint. Adjacent chest looting (`_try_loot_adjacent_chest`) remains unaffected.
- **Premature lift prevention** — Suppression now requires a minimum 20-turn cool-down (`_MIN_SUPPRESS_TURNS`) before the centroid-distance lift check (Manhattan ≥ 5) is evaluated. This prevents the explore/patrol sweep where the leader would move 5 tiles toward patrol, lift suppression, then immediately get pulled back by explore.
- **Position history extended** — `_POSITION_HISTORY_LEN` increased from 4 to 8 for better pattern detection across longer oscillation cycles.
- **Cross-system visited history** — `explore_room` moves now feed into patrol's `_visited_history`, letting the stale-area detector count explore_room positions toward its 10-turn threshold.
- **Duplicate discard bug** — Fixed an unconditional `_explore_suppressed.discard()` that was bypassing the centroid-distance gate on every MOVE action.
- 4040 tests passing.

### Impact (10-seed PVPVE validation, 6×6 grid, 200 turns)
- **Before**: All teams stuck at full HP for 200 turns; 0 PVE kills; no combat.
- **After**: Average 13.5 PVE kills/match; team wipes in 8/10 seeds; 4 matches ended early due to elimination; every seed shows active exploration, chest looting, and combat.

---

## [v0.1.7v] - 2026-03-19 - Movement Deadlock Fix (Leader Priority + Stall Breaker)

### Fixed
- **Parties no longer get permanently stuck due to same-target movement deadlocks** — When a team leader and a follower (or multiple followers) both targeted the same tile in the same turn, the movement batch resolver picked one winner by alphabetical player_id. If a follower won, the leader's intent was removed, breaking the movement chain for all downstream units — every unit stayed in place, made the same decisions next turn, and remained deadlocked forever. A 20-seed diagnostic scan found **112 instances** of units issuing 10+ consecutive identical failed moves, with the worst cases lasting 98 turns.

### Root Cause
`resolve_movement_batch()` in combat.py resolved same-target conflicts with a flat priority: `(0 if human else 1, player_id)`. All AI units shared the same tier, so a random follower could beat its own team leader in a tile conflict. This removed the leader's move intent, which broke the chain resolver — nobody moved, and the same AI decisions repeated indefinitely.

### Fix (Phase 30)
- **Leader Priority (Fix A):** The same-target conflict priority now uses three tiers: `human (0) > team leader (1) > follower (2)`, with alphabetical player_id as tiebreaker within tiers. Leaders always win tile conflicts against their own followers, ensuring they keep moving. Once the leader moves, followers pathfind to the leader's new position, naturally breaking cascading deadlocks.
- **Stall Breaker (Fix B):** Non-leader units that have been at the same position for 3+ consecutive turns while issuing MOVE actions are forced to WAIT on alternating turns, using a deterministic parity derived from the player_id. This ensures that when two followers deadlock on the same target tile, they yield on different turns — one passes while the other waits — breaking follower-vs-follower stalemates that leader priority alone doesn't resolve.

### Simulation Results (PvPvE, 100 turns, 16 seeds)

| Metric | Before Fix | After Fix | Change |
|--------|-----------|-----------|--------|
| Units with 10+ repeated identical moves | 112 | ~10 | **~91% reduction** |
| Worst-case streak (turns stuck) | 98 | ~37 | **62% shorter** |
| Seed 400 Team A final distance from spawn | ~3 tiles (stuck) | ~16 tiles (progressing) | **Fixed** |

### Files Changed
- `server/app/core/combat.py` — `_priority()` in `resolve_movement_batch()` now returns 3-tier priority: human (0) > team leader (1) > follower (2)
- `server/app/core/ai_behavior.py` — Added stall breaker after oscillation suppression: forces WAIT on alternating turns when position unchanged for 3+ turns

### Test Results
- 3,993 tests passing (0 failures)

---

## [v0.1.7u] - 2026-03-19 - Door Swap Displacement Fix

### Fixed
- **AI units no longer get stuck at doors due to friendly swap injection** — When a party leader chose INTERACT to open a door, a trailing follower could MOVE onto the leader's tile in the same turn. The Friendly Swap Injection system (Phase 1 — movement) would then displace the leader backward to make room. By the time Phase 1.5 (door interactions) resolved, the leader was no longer adjacent to the door, causing the INTERACT to fail silently. The leader would re-queue INTERACT next turn, get swapped again, and loop — sometimes failing 3+ consecutive times at the same door while the rest of the party went idle.

### Root Cause
Phase ordering: Movement (Phase 1) resolves before Door Interactions (Phase 1.5). The swap injection had no awareness of pending INTERACT actions, so it would displace any stationary same-team unit — including one about to open a door.

### Fix
- **Swap Protection (Fix A):** Before resolving movement, collect all `player_id`s with pending INTERACT actions (door opens, not portal/stairs). During Friendly Swap Injection, skip any occupant in that set — they must not be displaced from their door-adjacent tile.
- **Failure Logging (Fix C):** Surface `⚠ INTERACT FAILED` lines in batch PvPvE verbose output whenever a door interaction doesn't resolve, for future diagnostics.

### Simulation Results (PvPvE, 200 turns)

| Seed | Pre-Fix Failures | Post-Fix Failures |
|------|-----------------|------------------|
| 100 | 7 / 11 (64%) | 0 / 4 (0%) |
| 200 | 5 / 19 (26%) | 0 / 9 (0%) |
| 500 | 1 / 7 (14%) | 0 / 6 (0%) |
| **5-match batch (seed 1000)** | — | **0 / 38 (0%)** |

### Files Changed
- `server/app/core/turn_phases/movement_phase.py` — Added `interacting_pids` parameter to `_resolve_movement()`; swap injection skips occupants with pending INTERACT actions
- `server/app/core/turn_resolver.py` — Computes `door_interacting_pids` set from interact actions; passes to `_resolve_movement()`
- `server/batch_pvpve.py` — Added failed INTERACT logging to `log_turn_results()`

### Test Results
- 3,911 tests passing (1 pre-existing unrelated failure in TestGreedSigil)

---

## [v0.1.7t] - 2026-03-19 - AI Hero Stalling Fixes (Follow Tightening, Leader Tether, Idle Trailing)

### Fixed
- **AI hero followers no longer stall for 5–17+ consecutive turns** — Three distinct stalling patterns were identified via PvPvE batch simulation analysis and fixed. Combined, these eliminate the worst hero idle behavior across all game modes (PvP, PvE, PvPvE, and human player parties).

### Pattern 1: Follower Spawn Congestion (biggest impact)
- **Before:** Followers evaluated `dist_to_owner <= 2` at spawn and hit the WAIT fallback. Teams would idle for 5–9 turns at match start while the leader walked far enough away to trigger the regroup threshold.
- **Fix:** Reduced the follow-stance idle threshold from `dist_to_owner > 2` to `> 1` in `_decide_follow_action()`. Followers now only WAIT when literally adjacent (distance 1), not within a 2-tile radius.
- **Impact:** Early game (T1–T20) went from 5–9 consecutive WAITs per follower down to 0–2 scattered WAITs. Applies to all hero allies including human player party companions.

### Pattern 2: Corridor Gridlock / Leader Tether
- **Before:** When a leader was moving and followers were already adjacent, followers would idle even as the leader walked away. In corridors, 3–4 followers would cluster on the same tile trying to reach the leader.
- **Fix:** Added a "leader-is-moving" tether in `_decide_follow_action()`. When the owner's position changed since last tick (checked via `_position_history` from `ai_behavior.py`), adjacent followers attempt to trail the leader to maintain loose formation.
- **Impact:** Prevents formation pile-ups in corridors. The 17-turn streak (Team D Hexblade 2) is eliminated entirely.

### Pattern 3: Post-Combat / Idle Stalling
- **Before:** After combat ended, hero allies in the aggressive behavior path hit an explicit `WAIT` at step 4c ("hold position instead of patrolling"). Combined with the follow-stance idle threshold, entire parties would freeze until the leader found a new target.
- **Fix:** Hero allies at step 4c now trail their leader when idle instead of WAITing permanently. They path toward the owner when distance > 1, matching the follow-stance behavior. Only WAIT when already adjacent.
- **Impact:** Eliminates 10–94 turn idle streaks that occurred when followers lost sight of all enemies.

### Batch Simulation Results (PvPvE, 6x6 grid, 150 turns)

| Metric | Pre-Fix | Post-Fix |
|--------|---------|----------|
| Worst WAIT streak | 17 turns | **4 turns** |
| Team A WAIT% | 15.2% | **12.7%** |
| Team B WAIT% | 9.0% | **6.3%** |
| Team C WAIT% | 12.8% | **5.7%** |
| Team D WAIT% | 17.4% | **3.3%** |

### Files Changed
- `server/app/core/ai_stances.py` — `_decide_follow_action()`: Priority 3 idle threshold `> 2` → `> 1`; added leader-is-moving tether block that checks `_position_history` for owner movement
- `server/app/core/ai_behavior.py` — Added `_last_combat_tick` dict, `_ai_tick_counter`, `_POST_COMBAT_FOLLOW_GRACE` for post-combat tracking; step 4c in `_decide_aggressive_action()` now trails owner instead of permanent WAIT; cleanup in `run_ai_decisions()` and `clear_ai_patrol_state()`

### Test Results
- 3993 tests passing (0 new, 0 regressions)

---

## [v0.1.7s] - 2026-03-19 - Batch PVPVE Accuracy Fixes

### Fixed
- **Batch PVPVE AI teams now use follow-stance behavior matching live matches** — All 4 teams had their followers forcibly converted to independent aggressive AI, causing every unit to scatter solo across the dungeon. In live PVPVE, each team has 1 leader (aggressive) and 4 followers (follow-stance) who cluster within 2-4 tiles of their leader. Teams B/C/D now keep their original stance setup. Team A followers are re-parented to Team A's leader instead of the removed dummy host, preserving follow-stance behavior.
- **Batch PVPVE AI can now see and loot ground items and chests** — `run_ai_decisions()` was missing `ground_items` and `chest_states` parameters that the live tick loop passes. AI units in batch simulations would ignore treasure chests and ground loot entirely, diverging from live dungeon behavior.

### Impact
These two fixes eliminate the most significant behavioral divergences between batch PVPVE simulations and live PVPVE dungeons. Batch results will now show coordinated team movement, group engagements, and chest/loot interaction — matching what players actually experience.

### Files Changed
- `server/batch_pvpve.py` — Replaced blanket aggressive conversion with leader re-parenting for Team A; removed unnecessary follower conversion for Teams B/C/D; added `ground_items` and `chest_states` kwargs to `run_ai_decisions()` call

---

## [v0.1.7r] - 2026-03-18 - PVPVE AI Team Chest Seeking Fix

### Fixed
- **PVPVE AI opponent hero parties now open and loot treasure chests** — In PVPVE mode, the 3 AI opponent hero teams would walk past treasure chests without ever interacting with them. The v0.1.7n chest-seeking feature only worked for hero allies (stance-based AI); PVPVE team leaders and their followers were completely excluded.

### Root Cause
PVPVE team leaders are spawned without `hero_id` or `ai_stance` (both `None`), so they bypass the stance-based AI gate in `decide_ai_action()` and fall through to `_decide_aggressive_action()`. That function's signature did not accept `chest_states` at all — it had no chest-seeking logic of any kind. PVPVE followers do enter the stance path (they have `hero_id` + `ai_stance="follow"`), but since the leader never stops near chests, followers are perpetually chasing and never reach their idle chest-seeking priority.

| Unit | Code Path | Had chest_states? | Result |
|------|-----------|-------------------|--------|
| PVPVE Leader | `_decide_aggressive_action` | **No** | Never looted |
| PVPVE Follower | `_decide_stance_action` → follow | Yes | Rarely — always chasing leader |

### Fix
- Added `chest_states` parameter to `_decide_aggressive_action()`
- Added chest-seeking logic (step 4b2) in the idle section for hero party AI (`enemy_type is None`): first checks for adjacent chests to loot (`_try_loot_adjacent_chest`), then pathfinds toward the nearest unopened chest (`_find_nearest_unopened_chest`) within the aggressive seek range (6 tiles)
- Threaded `chest_states` from `decide_ai_action()` through to `_decide_aggressive_action()`
- Imported `_CHEST_SEEK_MAX_RANGE`, `_find_nearest_unopened_chest`, and `_try_loot_adjacent_chest` from `ai_stances.py` into `ai_behavior.py`
- Dungeon enemies (`enemy_type` set) are excluded from chest seeking — only hero party AI units (PVPVE teams, player allies) can loot
- Priority order preserved: Potions → Skills → Combat → Memory Pursuit → Reinforce Ally → **Chest Seeking** → Hero Wait → Ground Loot → Patrol
- With leaders now stopping at chests, followers naturally end up nearby and can trigger their own stance-based chest looting

### Files Changed
- `server/app/core/ai_behavior.py` — Added `chest_states` param to `_decide_aggressive_action`; added step 4b2 chest-seeking logic for hero party AI; imported chest helpers from `ai_stances`
- `server/tests/test_ai_chest_seeking.py` — 6 new tests: PVPVE leader loots adjacent chest, moves toward chest, ignores opened chests, combat takes priority, dungeon enemies excluded, no crash without chest_states

### Test Results
- 3993 tests passing (6 new, 0 regressions)

---

## [v0.1.7q] - 2026-03-18 - AI Hero Anti-Oscillation Fix

### Fixed
- **AI hero parties no longer oscillate (swap places) when patrolling or exploring** — Units would get stuck in an A→B→A loop, bouncing between two positions on alternating turns. This was most visible when a party of heroes was navigating corridors or open areas with no enemies nearby — the entire group would stall out with members endlessly trading tiles.

### Root Cause
The `allow_team_swap` flag (added in v0.1.7o) correctly lets A* path through same-team allies, but the cooperative movement prediction system (`pending_moves`) causes A* to compute different optimal paths each turn as the occupied-set shifts. On turn N, unit A vacates tile X and moves to tile Y; on turn N+1, the occupied set is reversed so A* sends the unit right back to X. No per-unit memory existed to detect or prevent this backtracking.

### Fix
- Added per-unit **position history** tracking (`_position_history`) in the AI decision orchestrator (`run_ai_decisions`). Each unit's last 4 positions are recorded across turns.
- After each AI MOVE decision, the system checks whether the target tile matches the unit's position from the previous turn (A→B→A detection).
- If oscillation is detected **and** no enemy is within 3 tiles (Chebyshev distance), the MOVE is suppressed to a WAIT. This breaks the oscillation loop while preserving legitimate combat maneuvers (kiting, retreating, chasing).
- Position history is cleaned up alongside patrol/memory state on unit death and match end.

### Technical Details
- The combat exemption range (`_OSCILLATION_COMBAT_RANGE = 3`) ensures kiting, retreat, and pursuit behaviors are never disrupted — oscillation is only suppressed during idle exploration/patrolling
- The fix is applied universally to all AI units (hero parties and PVE enemies) at the orchestrator level, requiring no changes to individual behavior functions
- One-turn WAIT from suppression is sufficient to break the cycle: the next turn, the occupied set will have shifted enough for A* to find a non-oscillating path

### Files Changed
- `server/app/core/ai_behavior.py` — Added `_position_history` dict, `_POSITION_HISTORY_LEN`, `_OSCILLATION_COMBAT_RANGE` constants; added oscillation detection post-processing in `run_ai_decisions`; added history cleanup in `clear_ai_patrol_state`

---

## [v0.1.7p] - 2026-03-18 - Unique Class Composition for AI Parties

### Changed
- **AI parties no longer have duplicate classes** — Each AI team (allies, opponents, PVPVE teams) now spawns with all-unique class compositions. Previously `random.choice()` selected classes independently per slot, frequently producing duplicate classes on the same team (e.g. two Crusaders, three Rangers). Now classes are pre-selected as a unique set per team using `random.sample()`-style logic before spawning.
- **Manually specified class slots respected** — When a player locks in specific classes via the lobby config (`ai_ally_classes` / `ai_opponent_classes`), those are honored first. Remaining random slots are filled from the pool of unused classes, ensuring no duplicates against manually-picked classes either.
- **Cross-team duplicates still allowed** — Only intra-team duplicates are prevented. Team A and Team B can still independently field the same class (mirror matches are fine). Each team gets its own unique draw from the 11-class pool.
- **PVPVE AI teams included** — The same unique-composition logic applies to PVPVE AI hero teams, which previously also used pure random selection per unit.

### Technical Details
- With 11 classes and max party size of 5, there are 462 unique team compositions possible (C(11,5)), ensuring strong variety across matches
- Fallback to `random.choice()` exists for the impossible edge case where slots exceed available classes (11 classes, 5 max team = never triggered)
- The `class_name_counts` naming logic (e.g. "Mage 2") is retained as a safety net but should no longer activate in normal play

### Files Changed
- `server/app/core/match_manager.py` — `_spawn_ai_units()`: replaced per-slot `random.choice()` with pre-selected unique class lists for both ally and opponent loops; `_spawn_pvpve_ai_teams()`: replaced per-unit `random.choice()` with per-team shuffled unique picks

---

## [v0.1.7o] - 2026-03-18 - PVPVE Team Leader Deadlock Fix

### Fixed
- **PVPVE AI teams no longer freeze at spawn in narrow corridors** — One of the 3 AI opponent teams would consistently stand idle at their spawn point for the entire match. This was most visible when a team spawned in a 2-tile wide hallway: the leader would oscillate between two tiles while all 4 followers stood still.

### Root Cause
The PVPVE team leader uses aggressive AI behavior (`_decide_aggressive_action`), which calls `_build_occupied_set` **without** `allow_team_swap`. This means the leader treated its own 4 followers as impassable obstacles. In a compact BFS spawn formation within a narrow corridor, A* pathfinding would fail because followers blocked every viable path. The leader would fall back to `_random_adjacent_move`, oscillating between the 1-2 free adjacent tiles. Meanwhile, followers use `_decide_follow_action` which WAITs when the leader is within 2 tiles (Chebyshev distance). Result: permanent deadlock — leader can't escape, followers won't move.

The follower stance system (`_decide_stance_action`) already used `allow_team_swap=ai.team` to let followers path through allies. The leader's aggressive behavior path was missing the same treatment.

### Fix
- `_decide_aggressive_action` now computes `allow_swap = ai.team` for hero party AI (`enemy_type is None`) and passes it to all `_build_occupied_set` calls. Dungeon enemies (`enemy_type` set) retain the original behavior.
- `_patrol_action` now accepts an `allow_team_swap` parameter and propagates it to `_build_occupied_set`, so patrol waypoint pathfinding also respects team swap.
- The movement resolver's existing friendly swap injection (Phase 1B) handles the actual tile collision at resolution time — no new swap logic needed.

### Files Changed
- `server/app/core/ai_behavior.py` — 6 `_build_occupied_set` calls in `_decide_aggressive_action` now pass `allow_team_swap` for hero party AI
- `server/app/core/ai_patrol.py` — `_patrol_action` accepts and forwards `allow_team_swap`
- `server/tests/test_movement_prediction.py` — Updated pending_moves test to use dungeon enemies (enemy_type set) so it tests the prediction feature in isolation; added new test verifying hero party AI can path through same-team allies

---

## [v0.1.7n] - 2026-03-18 - AI Chest Seeking (Hero Allies)

### Added
- **Hero AI parties now open treasure chests** — When idle (no visible enemies), AI-controlled hero allies will seek out and open nearby unopened chests. Previously only the human player could open chests; AI heroes would walk past them.
- **Per-stance seek ranges** — Each stance has a tuned maximum chest-seeking range: Follow (4 tiles), Aggressive (6 tiles), Defensive (3 tiles). Hold stance never moves but will loot chests it happens to be adjacent to.
- **Defensive tether respected** — Defensive heroes will only path toward chests if doing so keeps them within 2 tiles of their owner, preserving the defensive tether constraint.
- **Inventory-full guard** — AI will not seek chests when inventory is full (`INVENTORY_MAX_CAPACITY`), avoiding pointless pathfinding.
- **Two-tick chest interaction** — When not adjacent, AI pathfinds toward the chest (MOVE). Once adjacent (Chebyshev distance 1), AI emits `ActionType.LOOT` targeting the chest tile, which is resolved by the existing `_resolve_loot()` interaction phase.

### Technical Details
- `tick_loop.py`: Now passes `chest_states` to `run_ai_decisions()`
- `ai_behavior.py`: `run_ai_decisions()` and `decide_ai_action()` accept and forward `chest_states` to stance dispatch
- `ai_stances.py`: New utility functions `_find_nearest_unopened_chest()` and `_try_loot_adjacent_chest()`; `_decide_stance_action()` forwards `chest_states` to all four stance handlers
- `_decide_follow_action()`: Seeks chests when idle and close to owner (Priority 4, after combat/regroup)
- `_decide_aggressive_stance_action()`: Seeks chests when idle after memory pursuit and ally reinforcement
- `_decide_defensive_action()`: Seeks chests when idle, respects 2-tile owner tether
- `_decide_hold_action()`: Loots adjacent chests in the no-enemies early-return path (never moves)
- Priority order preserved: Potions → Portal → Retreat → Skills → Combat → Regroup → Chest Seeking → Wait

### Files Changed
- `server/app/services/tick_loop.py` — Pass `chest_states` to AI layer
- `server/app/core/ai_behavior.py` — Thread `chest_states` through `run_ai_decisions()` → `decide_ai_action()`
- `server/app/core/ai_stances.py` — Chest-seeking helpers + per-stance chest behavior
- `server/tests/test_ai_chest_seeking.py` — 26 new tests

### Test Results
- 3986 tests passing (26 new, 0 regressions)

---

## [v0.1.7m] - 2026-03-17 - AI Door Opening (All Units)

### Changed
- **All AI can now open doors** — Enemy AI (aggressive, ranged, boss, support) and allied party members all use door-aware A* pathfinding and will open closed doors when they are on the planned path. Previously only hero ally stances (follow/aggressive/defensive) could interact with doors; enemy AI was explicitly blocked from doing so, causing enemies to get stuck behind closed doors in dungeon layouts.
- **Door-aware pathfinding propagated to AI sub-systems** — `_pursue_memory_target()`, `_reinforce_ally()`, and `_patrol_action()` now accept and forward `door_tiles`, so AI memory pursuit, ally reinforcement, and patrol scouting all path through closed doors at elevated cost (+3 vs +1).
- **A* still prefers open routes** — The existing weighted cost system (door step = 3, normal step = 1) remains, so AI will always prefer open paths but won't get stuck when a door is the only option.
- **Multi-tick door crossing preserved** — The existing pattern (tick 1: INTERACT to open door → tick 2: MOVE through) applies identically to enemy AI as it does to hero allies.

### Technical Details
- `decide_ai_action()`: Removed enemy-exclusion gate; all behaviors now receive `door_tiles`
- `_decide_aggressive_action()`: Added `door_tiles` param, door-aware `get_next_step_toward()` calls, `_maybe_interact_door()` checks at all movement decision points
- `_decide_ranged_action()`: Same door-awareness additions
- `_decide_boss_action()`: Same door-awareness additions (room-leashed pathfinding also door-aware)
- `_decide_support_behavior()`: Same door-awareness additions
- `ai_memory.py`: `_pursue_memory_target()` and `_reinforce_ally()` now accept `door_tiles`, use door-aware pathfinding, and check for door interaction
- `ai_patrol.py`: `_patrol_action()` now accepts `door_tiles`, passes to both `a_star()` and `get_next_step_toward()`, checks for door interaction
- Lazy imports used in `ai_memory.py` and `ai_patrol.py` to avoid circular dependency with `ai_stances.py`
- Tests updated: old "enemy cannot open doors" regression tests converted to "enemy can open doors" positive tests

### Files Changed
- `server/app/core/ai_behavior.py` — Door-aware enemy AI behaviors
- `server/app/core/ai_memory.py` — Door-aware memory pursuit + ally reinforcement
- `server/app/core/ai_patrol.py` — Door-aware patrol scouting
- `server/app/core/ai_stances.py` — Pass `door_tiles` to memory/reinforce helpers
- `server/tests/test_ai_door_opening.py` — Updated enemy door tests
- `server/tests/test_door_pathfinding.py` — Updated enemy door tests

### Test Results
- 3792 tests passing (0 regressions)

---

## [v0.1.7l] - 2026-03-17 - Loot Rarity Rebalance

### Changed
- **Base rarity weights rebalanced** — Rare items drop ~7% on floor 1 (down from ~12%), making yellow-name items feel special again. Full weight changes:
  | Rarity | Old Weight | New Weight |
  |--------|-----------|-----------|
  | Common | 60.0 | 70.0 |
  | Magic | 25.0 | 20.0 |
  | Rare | 12.0 | 7.0 |
  | Epic | 2.5 | 1.2 |
  | Unique | 0.5 | 0.3 |
- **Steeper floor bonus curve** — Deeper floors now feel significantly more rewarding. Floor 1→9 Rare delta increased from +7.8pp to +9.7pp:
  | Floors | Old Bonus | New Bonus |
  |--------|----------|----------|
  | 1–2 | 0.00 | 0.00 |
  | 3–4 | 0.15 | 0.20 |
  | 5–6 | 0.35 | 0.50 |
  | 7–8 | 0.60 | 0.90 |
  | 9+ | 1.00 | 1.40 |
- **Common weight reduction formula** — Multiplier changed from `0.3` to `0.4`, making common items fall off faster on deeper floors.
- **Chest tier mapping fix** — Wooden/Iron chests now use `fodder` tier instead of `mid`, Gold uses `mid`, Obsidian uses `elite`, Boss uses `boss`. Early chests no longer inflate rarity beyond what killing a normal enemy would give.

### Files Changed
- `server/app/core/item_generator.py` — `_BASE_RARITY_WEIGHTS`, `_FLOOR_BONUS`, common weight formula in `roll_rarity()`
- `server/app/core/loot.py` — Chest-to-enemy-tier mapping in `generate_chest_loot()`
- `server/configs/loot_tables.json` — `rarity_config.base_rates` and `rarity_config.floor_bonuses`
- `docs/Phase Docs/loot-rarity-rebalance-proposal.md` — Design proposal (reference)

---

## [v0.1.7k] - 2026-03-17 - Ambient Darkness Pass (Torch Light Contrast)

### Added
- **`drawAmbientDarknessPass()`** in `PropLighting.js` — New rendering pass that overlays semi-transparent darkness on all **visible** tiles, then carves out bright pools around light-emitting props. Creates genuine contrast so torches, braziers, and candelabras feel like real illumination rather than faint color washes on an already-bright scene.
  - Uses a wider carve-out radius (1.3× the glow radius) with quadratic falloff so the light-to-dark transition is smooth and natural.
  - Darkness alpha is fully removed at light source centers and gradually restored at the falloff edge.
  - Cached per theme/room configuration — no per-frame recalculation.
- **Per-theme `ambientDarkness`** config value in `ambient` section of all 11 dungeon themes. Controls the base darkness level (0.0 = no effect, higher = darker). Thematically darker dungeons (Bleeding Catacombs 0.40, Cursed Shrine 0.42, Fungal Grotto 0.40) are gloomier than lighter ones (Forgotten Cellar 0.30, Pale Ossuary 0.30).

### Changed
- **Light source intensities boosted** — All prop light sources increased 2–3× to pop against the darker ambient:
  | Prop | Old Intensity → New | Old Radius → New |
  |------|---------------------|------------------|
  | torch_sconce | 0.08 → 0.22 | 2.5 → 3.0 |
  | brazier | 0.10 → 0.28 | 3.0 → 3.5 |
  | candelabra | 0.09 → 0.24 | 3.0 → 3.5 |
  | ritual_circle | 0.10 → 0.22 | 3.5 → 4.0 |
  | mushroom_cluster | 0.07 → 0.16 | 2.0 → 2.5 |
  | fountain | 0.05 → 0.14 | 1.8 → 2.5 |
  | altar | 0.04 → 0.12 | 1.5 → 2.0 |
- **`ArenaRenderer.js`** — Ambient darkness pass inserted into render pipeline after unit rendering, before fog overlay. Only activates for dungeon maps with rooms and an active theme.
- **`PropLighting.js`** — `clearLightCache()` now also clears the ambient light map cache.

### Per-Theme Ambient Darkness Values
| Theme | ambientDarkness | Feel |
|-------|----------------|------|
| Bleeding Catacombs | 0.40 | Heavy gloom |
| Ashen Undercroft | 0.35 | Moderate |
| Drowned Sanctum | 0.38 | Deep underwater murk |
| Hollowed Cathedral | 0.32 | Slightly lighter (candelabras) |
| Iron Depths | 0.38 | Industrial dark |
| Forgotten Cellar | 0.30 | Lighter rustic |
| Pale Ossuary | 0.30 | Lighter bone-white |
| Silent Vault | 0.35 | Moderate |
| Fungal Grotto | 0.40 | Heavy (bioluminescent contrast) |
| Frozen Crypt | 0.35 | Moderate icy |
| Cursed Shrine | 0.42 | Heaviest (ritual darkness) |

### Files Changed
- `client/src/canvas/PropLighting.js` — `drawAmbientDarknessPass()` function + ambient light map cache + boosted LIGHT_SOURCES intensities/radii
- `client/src/canvas/ArenaRenderer.js` — import + call `drawAmbientDarknessPass()` before fog pass
- `client/src/canvas/ThemeEngine.js` — `ambientDarkness` added to all 11 built-in theme `ambient` configs
- `server/configs/themes/*.json` — `ambientDarkness` added to all 11 theme JSON files

---

## [v0.1.7j] - 2026-03-17 - Prop Lighting System (Multi-Tile Glow + Fog Modulation + Particles)

### Added
- **`PropLighting.js`** — New rendering module that gives light-emitting props (torches, braziers, candelabras, ritual circles, mushroom clusters, fountains, altars) multi-tile radial glow effects. Uses additive blending (`globalCompositeOperation: 'lighter'`) with radial gradients that span 1.5–3.5 tiles from the prop center, creating warm pools of light visible across adjacent tiles.
  - `collectLightSources()` — Mirrors TileProps.js deterministic placement logic (cellHash, `_resolvePosition`, focal/accent priority, budget) to identify which props land on which tiles. No server changes required.
  - `drawPropGlowPass()` — Renders the actual glow: additive radial gradients with per-prop color, radius, and intensity. Fire-type props (torch, brazier, candelabra) have randomized flicker via sine-wave offsets. Magic-type props (ritual circle, mushroom cluster) have smooth pulse animation.
  - `buildFogLightMap()` / `getFogLightMap()` — Returns a `Map<string, number>` of tile-key → fog alpha reduction. Props carve a soft hole in the fog-of-war overlay, making revealed tiles near light sources appear brighter. Uses quadratic falloff, capped at 0.3 alpha reduction per tile.
  - Light source cache keyed by theme ID + room count to avoid recalculating every frame.
- **Fog-of-war light modulation** — `ThemeEngine.drawFog()` now accepts a `fogLightMap` parameter. For revealed tiles near light sources, the explored-fog alpha is reduced proportionally, creating visible light pockets that penetrate the fog. Unrevealed and invisible tiles are unaffected.
- **5 new particle presets** in `ambient.json`:
  - `prop-candelabra-glow` — Warm yellow-orange flame particles drifting upward
  - `prop-ritual-pulse` — Ring-shaped accent-colored magic particles
  - `prop-bioluminescent-spore` — Slow green drifting spore particles for mushroom clusters
  - `prop-brazier-embers` — Hot fire embers with upward drift
  - `prop-fountain-mist` — Cool blue mist particles for fountain props
- **Prop particle attachment** in `ParticleManager.js` — New `updatePropParticles(dungeonRooms, theme)` method follows the established zone emitter pattern to create persistent looping particle emitters at light-emitting prop positions. `PROP_PRESET_MAP` routes each prop type to its particle preset. Emitters are automatically created and destroyed as room data changes.

### Changed
- **`dungeonRenderer.js`** — Rendering pipeline now includes a glow pass after room overlays and before fog. `drawFog()` signature updated to accept `dungeonRooms` for fog light map construction.
- **`ArenaRenderer.js`** — `drawFog()` call updated to pass `dungeonRooms` through to the fog renderer.
- **`ThemeEngine.js`** — `drawFog()` rewritten to support per-tile fog alpha modulation. Parses base explored-fog alpha from the theme tint string, then reduces it for tiles intersected by the fog light map (minimum alpha floor of 0.15).
- **`ParticleManager.js`** — Added `_propEmitters` Map, `PROP_PRESET_MAP` static, `updatePropParticles()` method, `_cleanupPropEmitters()` safety net in tick loop, and cleanup in `destroy()`.
- **`Arena.jsx`** — New `useEffect` wires `updatePropParticles()` when `dungeonRooms` changes, following the same pattern as ground zone emitters.

### Light Source Configuration
| Prop | Radius (tiles) | Intensity | Color | Animation |
|------|----------------|-----------|-------|-----------|
| torch_sconce | 2.5 | 0.08 | Warm orange | Fire flicker |
| brazier | 3.0 | 0.10 | Deep orange | Fire flicker |
| candelabra | 3.0 | 0.09 | Bright gold | Fire flicker |
| ritual_circle | 3.5 | 0.10 | Theme accent | Pulse (1.2s) |
| mushroom_cluster | 2.0 | 0.07 | Theme accent | Pulse (0.8s) |
| fountain | 1.8 | 0.05 | Cool blue | None |
| altar | 1.5 | 0.04 | Theme accent | None |

### Files Changed
- `client/src/canvas/PropLighting.js` — **NEW** (~270 lines) — glow pass rendering, fog light map, light source collection
- `client/src/canvas/dungeonRenderer.js` — import + glow pass call + drawFog signature update
- `client/src/canvas/ThemeEngine.js` — `drawFog()` rewritten for light-modulated fog
- `client/src/canvas/ArenaRenderer.js` — pass dungeonRooms to drawFog
- `client/public/particle-presets/ambient.json` — 5 new prop particle presets
- `client/src/canvas/particles/ParticleManager.js` — prop emitter management system
- `client/src/components/Arena/Arena.jsx` — useEffect wiring for prop particles

### Notes
- FoV bonus (light sources increasing visible tile radius) is deferred to a future phase.
- No server changes required — all prop positions are resolved client-side using the existing deterministic placement algorithm.
- Pre-existing test failure in `TestBloodpact.test_low_hp_bonus_inactive_above_threshold` (unrelated unique item damage test). 3710 other tests passing.

---

## [v0.1.7i] - 2026-03-17 - Room Door System (Chokepoint Separators)

### Added
- **`door_placer.py`** — New post-decoration pass in the WFC generation pipeline that scans module boundaries and inserts wall separators with 1-tile door gaps at room entrances. Runs between `decorate_rooms()` and `export_to_game_map()`, so it has full knowledge of room roles.
- **Per-boundary door rolling** — Each module boundary is independently evaluated via seeded PRNG. Some entrances get a wall separator creating a tactical chokepoint, others stay wide open for variety.
- **Role-aware door chances** — Door probability is context-sensitive:
  - Spawn rooms: never doored (0%) — avoids frustrating the player at start
  - Boss rooms: high door chance (70%) — dramatic chokepoint before the boss
  - Grand interior joins (6+ tile openings): never doored (0%) — preserves multi-module rooms
  - Narrow openings (2-wide): slightly elevated (55%) — natural door spot
  - Corridor↔corridor: low chance (15%) — corridors stay open
  - Standard room entrances: 45% base chance
- **Per-style `doorChance` tuning** — Each dungeon style now overrides the base door probability:
  - Balanced: 0.45 (default)
  - Dense Catacomb: 0.60 (claustrophobic, more chokepoints)
  - Open Ruins: 0.20 (spacious, fewer barriers)
  - Boss Rush: 0.55 (tactical gates before encounters)
  - Treasure Vault: 0.50 (guarded rooms)
- **Door tiles re-enabled in map export** — `_normalize_tile()` no longer strips `D` tiles to `F`. Door tiles now survive to the exported game map and are collected into the `doors[]` array with `state: "closed"`.

### Changed
- **`dungeon_generator.py`** — Pipeline now runs `insert_room_doors()` as step 3.5 between decoration and export. Door placement stats included in generation metadata.
- **`map_exporter.py`** — `_normalize_tile()` updated: `D` tiles are preserved (previously converted to `F` with "doors disabled" comment). Only `E` and `B` markers are normalized to `F`.
- **`dungeon_styles.py`** — All 5 dungeon styles now include `doorChance` in their `decorator_overrides` dict.

### Notes
- Door gameplay mechanics (interaction_phase.py `_resolve_doors`) were already fully implemented — closed doors block movement, players toggle via INTERACT. This change provides the doors for it to operate on.
- Client rendering (dungeonRenderer.js door tile handling, ThemeEngine door drawing, RoomOverlays.js door archway highlights) was already implemented — doors will render immediately with no client changes needed.
- 3792 tests passing.

---

## [v0.1.7h] - 2026-03-17 - Prop Placement Overhaul (Budget + Focal System)

### Changed
- **Prop budget system** — Every room archetype now has a `maxProps` cap that limits how many prop slots can activate. Prevents visual clutter by stopping placement once the budget is reached. Budgets tuned per archetype: boss=5, enemy=3, empty=2, shrine=3, library=2, etc.
- **Focal prop groups** — Boss, prison, cathedral, ritual, torture, and ossuary archetypes now have a `focal` array of mutually exclusive center props. Exactly one is chosen via weighted random (seeded), giving each room instance a unique identity — e.g. a boss room might feature an altar OR a throne OR a ritual circle, never all three. Weights are scaled by theme affinity so thematically inappropriate props are filtered out.
- **Overlay-prop deduplication** — Removed props from `ARCHETYPE_PROP_SLOTS` that were already drawn by the archetype overlay functions, eliminating visual doubling:
  - Boss: removed `pillar` at corners (overlay draws corner pillars)
  - Shrine: removed `altar`, `brazier`, `banner` (overlay draws altar+braziers+banners)
  - Library: removed `bookshelf` on all walls (overlay draws full wall bookshelves)
  - Prison: removed `chains` on L/R walls (overlay draws chains+iron bars)
  - Flooded: removed `puddle` at random_floor/center (overlay draws floor puddles)
  - Empty: removed `rubble` at corners (overlay draws corner rubble)
  - Enemy: removed `weapon_rack` at wall_top and `torch_sconce` (overlay draws torches+rack lines)
  - Armory: removed `weapon_rack` at wall_top (overlay draws weapon pegs there)
- **Reduced prop chances** — Lowered base chance values across all archetypes. Enemy braziers from 0.7→0.5, loot barrels from 0.4→0.3, empty rubble from 0.5→0.4, graveyard tombstones from 0.8→0.75, etc. Combined with the budget cap, rooms now feel deliberately furnished rather than randomly scattered.
- **Restructured `ARCHETYPE_PROP_SLOTS` data format** — Changed from flat arrays to `{ maxProps, focal?, accents }` objects. Focal props are always placed at center; accents sorted by position priority (structural first, scatter last) before budget evaluation.
- **New `_pickFocal()` helper** — Weighted random selection from focal group, filtered by theme affinity. Ensures each room type feels distinct across playthroughs while respecting theme constraints.
- **Updated `drawRoomProps()` engine** — Now processes focal prop first (claiming 1 budget slot), then iterates accent props in priority order, stopping when `maxProps` is reached. Each slot activation counts as 1 toward budget regardless of how many tiles it covers (corners=4 tiles but 1 budget slot).

### Fixed
- Boss rooms no longer spawn altar + throne + ritual circle simultaneously (focal group picks exactly one)
- Shrine rooms no longer double-draw altar/braziers/banners (overlay handles those, props removed)
- Library rooms no longer draw bookshelf props on walls where the overlay already renders full bookshelves
- Prison rooms no longer double-draw chains on left/right walls
- Empty rooms no longer draw rubble at corners on top of the overlay's hand-placed corner rubble
- Enemy rooms no longer draw torch sconces and weapon racks that overlap with overlay torches and rack lines

### Files Changed
- `tools/theme-designer/src/engine/tileProps.js` — restructured `ARCHETYPE_PROP_SLOTS` (array→object with maxProps/focal/accents), added `_pickFocal()`, rewrote `drawRoomProps()` with budget system
- `tools/theme-designer/src/components/ObjectBrowser.jsx` — updated archetype placement iteration to handle new focal/accents data shape
- `client/src/canvas/TileProps.js` — mirrored all structural changes (budget, focal, drawRoomProps rewrite)

---

## [v0.1.7g] - 2026-03-17 - Room Archetype Expansion (7 New Archetypes)

### Added
- **7 new room archetypes** for the Dungeon Theme Designer, bringing total from 10 to 17:
  - **Grand Cathedral** — towering nave with central aisle, rose window motif on top wall, vertical wall streaks for height illusion, accent floor border
  - **Ritual Chamber** — arcane summoning room with dark ambient wash, central radial glow, floor rune marks, corner darkening, containment ring
  - **Torture Chamber** — blood-stained floor patches, scratched floor marks, heavy corner vignette, metal fixture brackets on walls
  - **Burial Ground** — earthy muted wash, disturbed soil patches, faint ground mist gradient, grave row path markers
  - **Armory** — clean maintained floor, metal wall trim with highlight, organized weapon pegs on walls, warm torchlight glow spots, door-to-center path
  - **Ossuary** — pale bone-white undertone, horizontal bone-stack texture on side walls, wall alcove recesses, flanking candle warm spots
  - **Fungal Grotto** — bioluminescent accent wash, radial glow pools, damp wall sheen, organic wall-edge blobs, floating spore dust motes
- **Prop slot definitions** for armory (weapon_rack, barrel, torch_sconce, chains), ossuary (skull_pile, coffin, candelabra, tombstone, altar), and fungal_grotto (mushroom_cluster, puddle, web, rubble)
- Cathedral, ritual, torture, and graveyard archetypes already had prop slots defined — now fully registered with labels, descriptions, and overlay draw functions

### Files Changed
- `tools/theme-designer/src/engine/roomArchetypes.js` — added 7 entries to `ROOM_ARCHETYPES`, 7 overlay draw functions, 7 switch cases in `drawRoomOverlay()`
- `tools/theme-designer/src/engine/tileProps.js` — added `ARCHETYPE_PROP_SLOTS` entries for armory, ossuary, fungal_grotto

---

## [v0.1.7f] - 2026-03-16 - Party HP Panel Centering & Instant Population Fix

### Fixed
- **Party HP panels biased to the left** — `.party-vitals` had `flex: 1` which stretched the container to fill all remaining space in the vitals row, overriding the `justify-content: center` on the parent. Removed `flex: 1` and `overflow-x: auto` so the party vitals container is content-sized and the vitals row correctly centers all HP panels (player + party) over the viewport.
- **Party HP bars missing on first frame** — only the player's own HP panel appeared at match start; party member HP panels didn't populate until after the first tick. The `MATCH_START` handler in `combatReducer` reset `partyMembers` to `[]`, and party data was only sent via the `queue_updated` message after the first turn resolved. Added `party` data to the server's `match_start` payload (`get_match_start_payload_for_player`) and updated the client's `MATCH_START` handler to use `action.payload.party` if present, so all party HP bars render immediately when the match begins.

### Files Changed
- `client/src/styles/components/_player-vitals.css` — removed `flex: 1` and `overflow-x: auto` from `.party-vitals`
- `server/app/core/match_manager.py` — `get_match_start_payload_for_player()` now includes `party` array via `get_party_members()`
- `client/src/context/reducers/combatReducer.js` — `MATCH_START` handler uses `action.payload.party || []` instead of hardcoded `[]`

---

## [v0.1.7e] - 2026-03-16 - Dungeon HUD Layout Overhaul

### Changed
- **Minimap relocated to right panel** — moved from an absolute overlay in the top-right of the game viewport to the right sidebar, positioned above the target bar (HUD). The minimap now fills the full panel width (~270px) as a squared-off panel matching the width of the HUD, Party, and Enemy panels below it. Tile size auto-scales to fill the panel based on map dimensions.
- **Player HP bar relocated above viewport** — the PlayerVitals frame (gradient HP bar with class identity row) moved from an absolute overlay at the bottom-left of the canvas to a dedicated vitals row between the action bar and the game viewport. It now sits outside the viewport area entirely rather than hovering over it.
- **Combat Meter button labeled** — the "⚔" combat meter toggle button in the action bar now displays a "Meter" text label below the icon, making its purpose clearer to players
- **Arena grid layout expanded** — grid changed from 3-row to 4-row layout (`auto auto auto 1fr`) to accommodate the new vitals row; left panel and right panel span rows 3–4 so they remain full-height

### Added
- **PartyVitals component** — new component that displays HP bars for all party members side by side using the same gradient bar style as the player's own PlayerVitals. Each party member gets a class-colored top accent border, class icon + name, player name, and a 20px gradient HP bar with HP text centered inside. Includes the same color-coded HP states (green >50%, amber 25–50%, red ≤25%, grey dead), danger pulse animation at low HP, and dead state desaturation.
- **Vitals row** (`arena-vitals-row`) — new grid row in the arena layout that contains the player's HP bar on the left and party HP bars side by side next to it, all between the action bar and the game canvas

### Files Changed
- `client/src/components/Arena/Arena.jsx` — moved MinimapPanel from canvas overlays to right panel (above HUD); moved PlayerVitals from canvas overlay to vitals row; added PartyVitals import and render
- `client/src/components/PlayerVitals/PartyVitals.jsx` — new component
- `client/src/components/PlayerVitals/PlayerVitals.jsx` — unchanged (styles updated in CSS)
- `client/src/components/MinimapPanel/MinimapPanel.jsx` — updated tile size calculation to fill panel width (~270px)
- `client/src/components/BottomBar/BottomBar.jsx` — added "Meter" label text to combat meter toggle button
- `client/src/styles/layout/_arena.css` — 4-row grid, vitals row styles, updated row spans for left/right/canvas
- `client/src/styles/layout/_minimap.css` — changed from absolute overlay to flow element with aspect-ratio 1/1 and full width
- `client/src/styles/components/_player-vitals.css` — removed absolute positioning; added PartyVitals/party-vital styles
- `client/src/styles/components/_combat-meter.css` — flex-direction column on btn-meter, added meter-label styles

---

## [v0.1.7d] - 2026-03-16 - Inventory Panel Width & Overflow Fix

### Fixed
- **Inventory overlay panel too narrow** — text (item names, buff pills, stat rows, context strip) was overflowing to the right and creating a horizontal scrollbar
  - Widened base panel from 340–440px to 420–560px (`width: max-content` up to max-width)
  - Widened large-screen breakpoint (1201px+) from 360–480px to 440–600px
  - Widened medium breakpoint (769–1200px) from 340–440px to 420–560px
  - Widened small-medium breakpoint (501–768px) from 320px min to 400px min
  - Added `overflow-x: hidden` to prevent horizontal scrollbar
  - Added `max-width: 100%` to equipment slot item names for proper ellipsis truncation
  - Added `overflow: hidden` and `max-width: 100%` to buff list and bag slot item info
  - Added `flex-wrap: wrap` and `overflow: hidden` to dungeon context strip

### Files Changed
- `client/src/styles/components/_inventory.css` — panel width increases, overflow protection

---

## [v0.1.7c] - 2026-03-16 - Player Vitals HP Bar Overhaul

### Added
- **PlayerVitals component** — new dedicated HP frame overlay anchored to the bottom-left of the game canvas, replacing the tiny inline HP bar that was buried in the header
  - **20px tall gradient HP bar** with HP text centered inside (white text with dark shadow for readability)
  - **Class identity row** — class-colored top accent border, class icon + class name + player name
  - **Color-coded HP states** — green gradient (>50%), amber gradient (25–50%), red gradient (<25%), grey (dead)
  - **Low-HP danger pulse** — red glow animation on the frame border when HP ≤ 25%
  - **Dead state** — desaturated and dimmed frame with "💀 DEAD" text
  - **Responsive scaling** — shrinks bar and frame on smaller viewports (<800px height)
- **`_player-vitals.css`** — full stylesheet with gradients, inner shadows, pulse animation, and responsive rules

### Changed
- **HeaderBar** — removed inline HP bar section (label, bar, value) to reduce top-bar clutter; turn/timer/mode/class/buffs remain
- **Arena layout** — PlayerVitals renders as an overlay inside the canvas area (bottom-left corner), near the player's natural focus area beside the action bar

### Removed
- **Header HP CSS** — removed `.header-hp`, `.header-hp-label`, `.header-hp-bar-bg`, `.header-hp-bar-fill`, `.header-hp-value` styles (no longer needed)

### Files Changed
- `client/src/components/PlayerVitals/PlayerVitals.jsx` — new component
- `client/src/styles/components/_player-vitals.css` — new stylesheet
- `client/src/components/HeaderBar/HeaderBar.jsx` — removed HP bar section
- `client/src/styles/components/_header-bar.css` — removed HP styles
- `client/src/components/Arena/Arena.jsx` — import and render PlayerVitals in canvas area
- `client/src/styles/main.css` — added `_player-vitals.css` import

---

## [v0.1.7b] - 2026-03-16 - Missing Particle Effects Pass

### Added
- **Seal of Judgment particles** — gold/holy branded star burst on target with diamond rune extras and a golden projectile trail (Inquisitor)
- **Blink particles** — arcane blue star burst at destination + fading departure trail at origin, visually distinct from Shadow Step's dark-bolt (Mage)
- **Bone Shield particles** — bone-colored triangle fragments orbit the caster on cast + persistent bone-shard aura while active (Skeleton enemy)
- **Dark Pact particles** — purple dark-magic burst on target with diamond-trail link wisps at caster + persistent purple aura while buffed (Dark Priest enemy)
- **Profane Ward particles** — expanding lavender circles on target + persistent lavender aura while damage reduction is active (Acolyte enemy)
- **Enrage particles** — dramatic fire ignition burst (white→gold→red→crimson) when HP drops below 30% + persistent flame aura while enraged (Demon Enrage enemy)
- **Frenzy Aura particles** — orange/red ring pulse on activation + persistent smoldering aura while the imp buff aura is active (Imp Lord enemy)
- **6 new buff auras** — `buff-aura-bone-shield`, `buff-aura-dark-pact`, `buff-aura-profane-ward`, `buff-aura-enrage`, `buff-aura-frenzy` persistent looping effects; `dark_pact` and `profane_ward` buff_id overrides added
- **3 new buff_status types** — `damage_absorb`, `passive_enrage`, `passive_aura_ally_buff` now have persistent aura visuals

### Changed
- **`particle-effects.json`** — added skill mappings for `seal_of_judgment`, `blink`, `bone_shield`, `dark_pact`, `profane_ward`, `enrage`, `frenzy_aura`; added `buff_id_overrides` for `dark_pact` and `profane_ward`; added `buff_status` entries for `damage_absorb`, `passive_enrage`, `passive_aura_ally_buff`

### Files Changed
- `client/public/particle-effects.json` — 7 new skill mappings, 3 new buff_status types, 2 new buff_id overrides
- `client/public/particle-presets/skills.json` — 12 new presets (seal-judgment-brand, seal-judgment-runes, seal-judgment-trail, blink-arrival, blink-departure, bone-shield-cast, dark-pact-cast, dark-pact-link, profane-ward-cast, enrage-ignite, frenzy-aura-pulse)
- `client/public/particle-presets/buffs.json` — 6 new aura presets (buff-aura-bone-shield, buff-aura-dark-pact, buff-aura-profane-ward, buff-aura-enrage, buff-aura-frenzy)

---

## [v0.1.7a] - 2026-03-16 - PVPVE Chest Tier Overhaul

### Added
- **PVPVE location-based chest tiers** — PVPVE mode now uses a centrality-based tier system instead of floor-depth gating. Chests closer to the map center (boss room area) roll higher tiers, creating a risk/reward dynamic where better loot requires venturing into contested territory.
  - **Edge zone** (team spawn corners): ~57% Wooden, ~28% Iron, ~11% Gold, ~3% Obsidian
  - **Mid zone** (midfield rooms): ~31% Wooden, ~37% Iron, ~22% Gold, ~11% Obsidian
  - **Center zone** (boss area): ~11% Wooden, ~25% Iron, ~40% Gold, ~24% Obsidian
- **`pvpve_tier_weights` config** — new section in `chest_tier_config` defines per-zone (edge/mid/center) spawn weights for PVPVE mode, independent of floor-range gating
- **`roll_chest_tier_pvpve()`** — new loot function that accepts a `centrality` value (0.0 = map edge, 1.0 = map center) and selects the appropriate zone weight table

### Fixed
- **PVPVE chests no longer all Wooden** — previously, PVPVE mode was always floor 1, so the floor-range gating meant only Wooden chests (floor 1+) were eligible. Iron (floor 2+), Gold (floor 4+), and Obsidian (floor 7+) could never spawn. The new centrality system bypasses floor gating entirely.

### Changed
- **`_init_dungeon_state()`** — now detects PVPVE match type and computes Euclidean centrality for each chest position relative to the map center. PVPVE chests use `roll_chest_tier_pvpve()` while standard dungeon chests continue using the floor-based `roll_chest_tier()`.

### Files Changed
- `server/configs/loot_tables.json` — added `pvpve_tier_weights` section with edge/mid/center weight tables
- `server/app/core/loot.py` — added `roll_chest_tier_pvpve()` function
- `server/app/core/match_manager.py` — updated `_init_dungeon_state()` with PVPVE centrality logic, added `get_map_dimensions` import

---

## [v0.1.7] - 2026-03-15 - Chest Tier System & Visual Redesign

### Added
- **Chest tier system** — 5 distinct chest tiers replace the single generic chest:
  - **Wooden Chest** (floors 1+, weight 50) — 1-2 common-leaning items
  - **Iron Chest** (floors 2+, weight 30) — 1-3 items, better uncommon drop rates
  - **Gold Chest** (floors 4+, weight 15) — 2-3 items, guaranteed magic+ rarity
  - **Obsidian Chest** (floors 7+, weight 5) — 2-4 items, guaranteed rare+ rarity
  - **Boss Chest** (boss rooms only) — unchanged from previous boss_chest behavior
- **Chest tier config** in `loot_tables.json` — new `chest_tier_config` section defines tier spawn weights, floor ranges, and loot table mappings
- **4 new chest loot tables** — `wooden`, `iron`, `gold`, `obsidian` with progressively better weighted pools
- **Chest tier visual redesign** — all chests now render as detailed barrel-lidded treasure chests with:
  - 3D shading (dark right edge, highlight left edge)
  - Visible lid with overhang and border
  - 2 horizontal metal band straps
  - Center latch/lock with keyhole detail
  - Opened state shows interior cavity, tilted-back lid, and hinge dots
  - Tier-specific glow effects (gold glow for Gold, purple glow for Obsidian, red glow for Boss)
- **Tier-specific color palettes** — each tier has unique body, band, latch, and lid colors
- **Tier-aware minimap** — minimap chest dots now use tier-specific colors instead of a single gold dot
- **Client utility modules**:
  - `chestUtils.js` — chest state parsing, tier config lookup, minimap color helper
  - `chestRenderer.js` — shared detailed chest drawing function used by ThemeEngine and dungeonRenderer

### Changed
- **Chest state format** — `chest_states` values changed from `"unopened"/"opened"` to `"unopened:tier"/"opened:tier"` (e.g. `"unopened:iron"`, `"opened:gold"`). Full backward compatibility with plain `"unopened"`/`"opened"` maintained.
- **`_init_dungeon_state`** — now rolls a chest tier for each chest based on floor number and boss room context using `roll_chest_tier()`
- **`generate_chest_loot`** — now falls back to the `"default"` loot table when an unknown chest type is passed, instead of returning empty
- **`_resolve_loot` (interaction_phase)** — extracts chest tier from state and passes it to `generate_chest_loot` for tier-appropriate drops
- **ThemeEngine** — chest case now delegates to shared `drawChestIcon()` with tier info passed via `extra.chestTier`
- **dungeonRenderer** — flat-color fallback chest replaced with tier-aware `drawChestIcon()`
- **Theme Designer tool** — `tilePatterns.js` `drawChest()` updated with detailed rendering matching the game
- **Pathfinding & keyboard shortcuts** — updated to recognize `"unopened:tier"` format via `startsWith` checks

### Files Changed
- `server/configs/loot_tables.json` — added `chest_tier_config`, 4 new chest loot tables (wooden, iron, gold, obsidian)
- `server/app/core/loot.py` — added `roll_chest_tier()`, updated `generate_chest_loot()` fallback
- `server/app/core/match_manager.py` — `_init_dungeon_state()` now rolls chest tiers
- `server/app/core/turn_phases/interaction_phase.py` — `_resolve_loot()` parses tier from chest state
- `client/src/utils/chestUtils.js` — new (chest tier config, state parsing)
- `client/src/canvas/chestRenderer.js` — new (detailed chest icon drawing)
- `client/src/canvas/dungeonRenderer.js` — updated chest drawing + imports
- `client/src/canvas/ThemeEngine.js` — updated chest drawing to use `drawChestIcon`
- `client/src/canvas/minimapRenderer.js` — tier-aware chest minimap colors
- `client/src/canvas/renderConstants.js` — updated default chest colors
- `client/src/canvas/pathfinding.js` — updated `startsWith` checks for new state format
- `client/src/hooks/useKeyboardShortcuts.js` — updated `startsWith` check for E key chest detection
- `tools/theme-designer/src/engine/tilePatterns.js` — updated `drawChest()` with detailed rendering
- `server/tests/test_dungeon_map.py` — updated assertion for new chest state format
- `server/tests/test_phase16b_affix_system.py` — updated test for fallback behavior

---

## [v0.1.6b] - 2026-03-15 - Hero Permadeath Bug Fix

### Fixed
- **Hero permadeath now applies to all heroes** — AI hero allies (party members) were not triggering permadeath when killed in dungeon runs. Only the human-controlled hero was checked (`unit_type == "human"`), but party allies spawn as `unit_type == "ai"` with a valid `hero_id`. Changed the condition to check for `hero_id` presence regardless of unit type, so all roster heroes are properly marked dead and removed from the active roster on death.

### Files Changed
- `server/app/core/turn_phases/deaths_phase.py` — permadeath condition changed from `unit_type == "human" and hero_id` to just `hero_id`

---

## [v0.1.6a] - 2026-03-15 - Custom Cursor & Game Icon

### Added
- **Custom game cursor** — `MouseFinal.png` resized to 32×32 and applied as the in-game cursor site-wide via CSS (`cursor.png` in `client/public/`). Replaces default browser cursor on all elements including buttons and interactive controls.
- **Game icon** — `icon 1.ico` / `icon 1.png` set as the official app icon:
  - Electron game window icon (`client/public/favicon.ico`)
  - Browser favicon (`<link>` tags in `index.html` for `.ico` and `.png`)
  - Electron builder icon for Windows/Mac/Linux builds
  - Launcher window icon + system tray icon (`launcher/assets/icon.ico`)
  - Launcher electron-builder config updated

### Files Changed
- `client/public/cursor.png` — new (32×32 resized from `Assets/Sprites/MouseFinal.png`)
- `client/public/favicon.ico` — new (from `Assets/Sprites/icon 1.ico`)
- `client/public/favicon.png` — new (from `Assets/Sprites/icon 1.png`)
- `launcher/assets/icon.ico` — new (from `Assets/Sprites/icon 1.ico`)
- `client/src/styles/base/_reset.css` — added custom cursor rules
- `client/index.html` — added favicon `<link>` tags
- `launcher/main.js` — added `icon` property to BrowserWindow
- `launcher/package.json` — added `icon` to electron-builder win config

---

## [v0.1.6] - 2026-03-14 - AI & Team Fixes

**Summary:** Six bug fixes and AI improvements targeting PVPVE team assignment, totem targeting, Confessor AI, and multi-support positioning. Rolls up v0.1.5–v0.1.5f changes into a published release.

### Bug Fixes
- **PVPVE lobby team ignored** — `_assign_pvpve_teams()` no longer force-distributes players round-robin; respects lobby-chosen team (v0.1.5)
- **PVPVE index-based team detection** — `_spawn_pvpve_ai_teams()` now reads actual `player.team` instead of using list index (v0.1.5b)
- **Hero ally hardcoded to Team A** — `_spawn_hero_ally()` now reads owner's team field (v0.1.5b)
- **Ground-placement skills hijacked by auto-target** — Added `isPlacementSkill()` check to bypass auto-select for totem skills (v0.1.5c)
- **Shield of Faith self-cast** — Excluded caster from SoF candidate loop; moved SoF to Priority 4.7 after reposition check (v0.1.5e)
- **Multi-support clumping** — Support roles now exclude other supports from nearest-ally movement fallback (v0.1.5f)

### AI Improvements
- **Confessor tank-aware positioning** — Proactively moves toward tank-role allies when outside heal range (v0.1.5d)
- **Reposition threshold raised 60% → 80%** — Confessor starts closing distance earlier (v0.1.5d)
- **Check B tank drift threshold** — Introduced `_TANK_REPOSITION_THRESHOLD = 5` so Exorcism fires at medium range (v0.1.5e)
- **Support anti-clump anchoring** — `_support_move_preference()` and `_totemic_support_move_preference()` prefer non-support allies as anchors (v0.1.5f)

---

## [v0.1.5f] - 2026-03-14 - Multi-Support Anti-Clumping Fix

### Improvement — `server/app/core/ai_skills.py`

- **Support-role nearest-ally filtering** — `_support_move_preference()` (Confessor) and `_totemic_support_move_preference()` (Shaman) now exclude other support-role allies from their "nearest ally" movement fallback. Previously, when no allies were injured and the tank was within heal range, each support would pick the **nearest ally** as its movement anchor — which was often the other support. This caused Confessor + Shaman (and similar double-support comps) to gravitate toward each other, clump away from the frontline, and oscillate tiles as the batch movement resolver repeatedly blocked their identical move targets. Both functions now prefer non-support allies (tanks, DPS) as movement anchors, only falling back to support allies if no other teammates are alive. Added `_SUPPORT_ROLES` constant (`support`, `offensive_support`, `totemic_support`) for the filter.

---

## [v0.1.5e] - 2026-03-14 - Confessor AI Healing & Targeting Fixes

### Bug Fix — `server/app/core/ai_skills.py`

- **Shield of Faith self-cast bug** — `_support_skill_logic()` SoF candidate loop included the caster itself. Confessor has the lowest base HP (100) so it always had the lowest HP% and self-cast SoF ~56% of the time, wasting the buff on a backline unit. Added `if unit.player_id == ai.player_id: continue` to match the existing Dark Pact self-exclusion pattern. SoF now always targets an ally (typically the tank).

- **SoF priority blocks repositioning** — Shield of Faith was at Priority 4, firing BEFORE the Priority 4.5 reposition check. When the tank drifted out of heal range and needed healing, the Confessor would cast SoF (often on itself) instead of repositioning toward the hurt tank. Moved SoF to Priority 4.7 so the reposition check runs first. If the tank is far and hurt, the Confessor walks toward them instead of buffing.

- **Check B too aggressive** — The v0.1.5d "suppress Exorcism when tank is far" check used `_SUPPORT_HEAL_RANGE` (3 tiles) as its threshold, forcing reposition whenever the tank was >3 tiles away. This caused 64% of turns to be wasted on repositioning. Introduced `_TANK_REPOSITION_THRESHOLD = 5` so Exorcism can fire at medium range (4–5 tiles) while still triggering reposition when the tank is truly far (>5 tiles).

### Tests — `server/tests/test_confessor_diagnostic.py`

- 14 diagnostic tests verifying the three fixes: SoF never self-casts, reposition no longer blocks Exorcism at medium range, and SoF no longer prevents repositioning toward hurt tanks. Includes a 200-turn simulation asserting 0% SoF self-cast rate and <50% reposition rate.

---

## [v0.1.5d] - 2026-03-14 - Confessor AI Positioning Overhaul

### Improvement — `server/app/core/ai_skills.py`

- **Tank-aware support positioning** — `_support_move_preference()` now identifies tank-role allies (Crusader `tank`, Revenant `retaliation_tank`, Blood Knight `sustain_dps`) and proactively moves toward them when the Confessor is outside heal range (3 tiles). Previously the Confessor only moved toward **most injured** or **nearest** ally, causing it to drift behind the party while the tank advanced into combat. New priority order: (1) most injured ally below 60% HP, (2) tank-role ally outside heal range, (3) nearest ally.

- **Raised reposition threshold from 60% → 80%** — The "Priority 4.5" reposition check in `_support_skill_logic()` now uses a dedicated `_REPOSITION_ALLY_THRESHOLD` of 0.80 instead of the heal threshold (0.60). The Confessor will start closing distance toward out-of-range allies much earlier, before they become critical. This prevents the pattern where the Confessor spams Exorcism from range 5 while the tank slowly drops from 70% → 30% HP out of heal range.

- **Suppress Exorcism when tank is drifting out of range** — Added a second reposition check (Check B) that returns `None` when any tank-role ally is beyond heal range (3 tiles), regardless of their HP%. This forces the stance handler to move the Confessor toward the tank instead of casting Exorcism from the back line. Exorcism (range 5) greatly exceeds Heal (range 3), which previously created a positioning trap where the Confessor could DPS comfortably but couldn't heal.

- **New constants** — Added `_REPOSITION_ALLY_THRESHOLD` (0.80), `_TANK_ROLES` set (`{"tank", "retaliation_tank", "sustain_dps"}`), and `_SUPPORT_HEAL_RANGE` (3) for tank-proximity calculations.

---

## [v0.1.5c] - 2026-03-13 - Ground Placement Skill Targeting Fix

### Bug Fix — `client/src/components/BottomBar/BottomBar.jsx`

- **Ground-placement skills (totems) hijacked by auto-target system** — Skills with `targeting: "ground_aoe"` and a `place_totem` effect (Healing Totem, Searing Totem, Earthgrasp Totem) were treated as enemy-targeting skills by the auto-target system. When enemies were in FoV, pressing a totem skill button would auto-select the nearest enemy and initiate pursuit instead of entering tile-selection mode for placement. Fixed by adding an `isPlacementSkill()` check that detects `place_totem` effects and bypasses both the target-first casting path (Phase 10G-6) and the `findNearestTarget()` auto-select. Totem skills now always enter tile-selection mode regardless of nearby enemies. Affects all classes with ground-placement skills.

---

## [v0.1.5b] - 2026-03-13 - PVPVE Team Assignment Fix (Upstream)

### Bug Fix — `server/app/core/match_manager.py`

- **`_spawn_pvpve_ai_teams()` used index-based team detection** — When determining which teams were occupied by humans, the function used player list index (`active_teams[i % team_count]`) instead of each player's actual `player.team` value. With 2 humans both on Team A in a 4-team match, it incorrectly computed `human_teams = {"a", "b"}` instead of `{"a"}`. This meant enemy AI teams would only fill C and D, leaving Team B empty — and the cascading mismatch caused Player 2 to appear on the wrong team. Fixed to read actual `player.team` from lobby selections.

### Bug Fix — `server/app/core/hero_manager.py`

- **`_spawn_hero_ally()` hardcoded `team="a"`** — Hero allies were always spawned with `team="a"` and appended to `match.team_a`, ignoring the owner's actual team. Fixed to read the owner player's `team` field and append to the correct team list. This ensures hero allies follow their owner to whichever team they've selected in the lobby.

### Tests — `server/tests/test_pvpve_ai_teams.py`

- Updated `test_ai_teams_skip_human_occupied_teams` to explicitly place humans on separate teams (A and B) before asserting AI skips those teams.
- Added `test_ai_teams_fill_all_non_human_slots_when_same_team` — verifies that when 2 humans are both on Team A, AI enemy teams correctly fill all remaining slots (B, C, D).

---

## [v0.1.5] - 2026-03-13 - PVPVE Team Assignment Fix

### Bug Fix — `server/app/core/match_manager.py`

- **PVPVE lobby team ignored** — `_assign_pvpve_teams()` was force-distributing human players round-robin across teams, overriding whatever team they chose in the War Room lobby. If two players both picked Team A, Player 2 would be silently moved to Team B at match start and spawn in a different corner alone. Fixed to respect each player's lobby-chosen team when it's a valid active team for the match. Round-robin fallback only applies if a player's team isn't one of the active PVPVE teams (e.g., on Team D in a 2-team match).

---

## [v0.1.4] - 2026-03-13 - Stance System Overhaul, Destroy Item & Audio Fixes

**Summary:** Major AI stance overhaul making all 4 stances (Follow, Aggressive, Defensive, Hold) role-aware so class identity is preserved regardless of stance choice. New inventory destroy-item feature. Audio polish fixes.

### Stance System Overhaul (Phases S1–S3) — `server/app/core/ai_stances.py`, `server/tests/test_stances.py`

- **S1-A: Bard Aggressive kiting fix** — Added `offensive_support` to `is_ranged_role` set in `_decide_aggressive_stance_action()` so Bards kite in Aggressive (was already working in Follow). Added `ally_positions` calculation for Bard kiting direction to stay near ally centroid.
- **S1-B: Hold stance smart targeting** — Replaced naive `for enemy in enemies` iteration with `_pick_best_target()` for both melee (adjacent enemies) and ranged (in-range + LOS enemies) target selection in `_decide_hold_action()`.
- **S2-A: Defensive match_state** — Added `match_state=None` parameter to `_decide_defensive_action()` for totem awareness.
- **S2-B: Defensive ranged kiting** — Ranged classes (Mage, Ranger, Inquisitor, Plague Doctor, Bard, Shaman) now kite in Defensive stance with role-specific thresholds (controller ≤ 3, totemic_support ≤ 1, others ≤ 2). Kite moves tethered within 2 tiles of owner.
- **S2-C: Defensive ranged engagement** — Ranged roles now engage enemies at their full attack range instead of hardcoded 2-tile limit. Melee classes unchanged.
- **S2-D: Defensive support positioning** — Support classes (Confessor, Bard, Shaman) on Defensive now position near allies using role-specific move preference functions instead of charging enemies.
- **S2-E: Defensive totem-biased movement** — Added `_totem_biased_step` to Defensive movement paths and controller hold-position logic. Re-checks tether after totem bias.
- **S3-A: Aggressive support positioning** — Support classes on Aggressive now use ally positioning instead of charging enemies. Added `is_support` detection, excluded support from melee rush block.
- **S3-B: Bard ally-proximity kiting** — Already handled by S1-A.

### Audio Fixes — `client/public/audio-effects.json`, `client/src/audio/AudioManager.js`

- Wither cast sound → `shadow-step_teleport-downer.wav` (softer dark tone, vol 0.55)
- Wither DoT tick → `debuff_speed-debuff.wav` (subtler pulse, vol 0.25)
- Healing Totem pulse → `heal-alt_healing-gusts.wav` (gentle nature sound, vol 0.25)
- Registered `heal_alt` in `_soundFiles` for preloading

### 3747 tests passing, 0 regressions.

---

## [Feature] - 2026-03-13 - Destroy Item from Inventory

**Summary:** Players can now permanently destroy unwanted items from their bag during dungeon runs. Previously, once a player's 10-slot inventory filled up, there was no way to discard items to make room for better loot. Each bag slot now has a destroy button (🗑) with a two-click confirmation to prevent accidents.

### Added — `server/app/core/equipment_manager.py`

- **`destroy_item()`** — New function that removes an item from a player's inventory by instance_id or item_id. Returns the updated inventory list. Validates player exists and is alive.

### Changed — `server/app/core/match_manager.py`

- **Re-export block** — Added `destroy_item` to the equipment_manager re-exports so existing importers can access it via match_manager

### Changed — `server/app/services/message_handlers.py`

- **`handle_destroy_item()`** — New async WS handler accepting `{ type: "destroy_item", item_id, unit_id? }`. Calls `destroy_item()` and responds with `item_destroyed` message containing the updated inventory
- **`MESSAGE_HANDLERS`** — Added `"destroy_item": handle_destroy_item` entry
- **Imports** — Added `destroy_item` to the match_manager import block

### Changed — `client/src/App.jsx`

- **WS message dispatch** — Added `case 'item_destroyed'` that dispatches `ITEM_DESTROYED` action to the reducer

### Changed — `client/src/context/GameStateContext.jsx`

- **`INVENTORY_ACTIONS`** — Added `'ITEM_DESTROYED'` to the action routing set so it reaches the inventory reducer

### Changed — `client/src/context/reducers/inventoryReducer.js`

- **`case 'ITEM_DESTROYED'`** — New reducer case that updates `state.inventory` (or `partyInventories` for party members) with the server-provided updated inventory array

### Changed — `client/src/components/Inventory/Inventory.jsx`

- **`confirmDestroyId` state** — New state variable tracking which item is awaiting destruction confirmation
- **`handleDestroyItem()`** — New callback implementing two-click confirm: first click sets confirm state (button turns red), second click sends the `destroy_item` WS message
- **Bag slot actions** — Wrapped transfer and new destroy buttons in a `.bag-slot-actions` container. Destroy button (🗑/✕) shown on all items when alive, not just when transfer is available

### Changed — `client/src/styles/components/_inventory.css`

- **`.bag-slot-actions`** — Flex container for the action button group
- **`.bag-destroy-btn`** — Styled to match the existing transfer button aesthetic with red hover state
- **`.bag-destroy-btn.destroy-confirm`** — Red filled background with pulse animation for the confirmation state
- **`@keyframes pulse-destroy`** — Subtle pulsing animation to draw attention to the confirm state

---

## [Feature] - 2026-03-12 - Launcher Install Progress Bar (Launcher v1.1.0)

**Summary:** Added a real-time progress bar during the game extraction/install phase. Previously the launcher showed "INSTALLING..." with no visual feedback, making it look frozen. Now reuses the same smooth animated progress bar from the download phase, showing file-by-file extraction progress.

### Changed - `launcher/lib/extractor.js`

- **`extract()`** - Added `onProgress` callback option
- **`extractWithProgress()`** - New helper that extracts entries one at a time via `extractEntryTo()` instead of `extractAllTo()`, calling `onProgress(extracted, total)` after each file

### Changed - `launcher/main.js`

- **start-install handler** - Extract step now passes `onProgress` callback that sends `extract-progress` IPC events to the renderer with `{extracted, total}` counts

### Changed - `launcher/preload.js`

- **`onExtractProgress`** - New IPC bridge method exposing the `extract-progress` event to the renderer

### Changed - `launcher/renderer.js`

- **`applyState('installing')`** - Now shows the progress bar (reset to 0%) instead of hiding it
- **`onExtractProgress` listener** - Updates progress bar with smooth animation showing file count (e.g. "45% - 230 / 512 files")
- **Progress bar visibility** - Now stays visible during both `downloading` and `installing` states

---

## [Bugfix] - 2026-03-12 - Town Hub Hero Portraits Missing (v0.1.3)

**Summary:** Fixed hero portraits not displaying in Town Hub screens (Hero Roster, Hiring Hall, Merchant). Same root cause as v0.1.2 — absolute asset path under Electron's `file://` protocol.

### Changed — `client/src/components/TownHub/HeroSprite.jsx`

- **CSS `backgroundImage`** — Changed from `url(/spritesheet.png)` to `` url(${import.meta.env.BASE_URL}spritesheet.png) `` so the spritesheet resolves correctly in deployed Electron builds

---

## [Bugfix] — 2026-03-12 — Missing Sprites, Audio & Particles in Deployed Build

**Summary:** Fixed all static asset paths that broke when the game was loaded via Electron's `file://` protocol in deployed (installed) builds. Sprites, tiles, skill icons, audio, and particle effects were all missing for testers despite being correctly included in the build zip. Dev mode via `start-game.bat` was unaffected because Vite's dev server resolves `/` paths to the project root.

**Root cause:** All static asset paths in the codebase used absolute root-relative paths (e.g. `/spritesheet.png`, `/audio/combat/swing.wav`). In development, Vite's dev server maps `/` to the project's `public/` folder, so these work. In production Electron builds, the app loads via `file://` protocol from `dist/index.html`. Under `file://`, a leading `/` resolves to the **filesystem root** (e.g. `C:\spritesheet.png`), not the app's `dist/` folder. The Vite config already sets `base: './'` for Electron builds, which fixes JS/CSS bundle paths, but hardcoded asset constants in source code are not affected by Vite's `base` setting.

**Impact:** This was the cause of missing sprites and sounds reported during the first online test. All game logic, UI components, API calls, and WebSocket connections were unaffected (those use full HTTP URLs from `serverUrl.js`).

### Changed — `client/src/canvas/SpriteLoader.js`

- **`SPRITESHEET_PATH`** — Changed from `'/spritesheet.png'` to `` `${import.meta.env.BASE_URL}spritesheet.png` `` — resolves to `./spritesheet.png` in Electron builds, `/spritesheet.png` in dev

### Changed — `client/src/canvas/TileLoader.js`

- **`TILESHEET_PATH`** — Changed from `'/tilesheet.png'` to `` `${import.meta.env.BASE_URL}tilesheet.png` ``

### Changed — `client/src/components/BottomBar/SkillIconMap.js`

- **`SKILL_ICON_SHEET`** — Changed from `'/skill-icons.png'` to `` `${import.meta.env.BASE_URL}skill-icons.png` ``

### Changed — `client/src/audio/AudioManager.js`

- **`init()`** — Audio effects JSON fetch now uses `${baseUrl}audio-effects.json` instead of `/audio-effects.json`
- **`_preloadBuffer()`** — Sound file URLs from `audio-effects.json` (e.g. `/audio/combat/swing.wav`) are now normalized: leading `/` is replaced with `import.meta.env.BASE_URL`
- **`_playTrack()`** — Music track paths from `audio-effects.json` receive the same normalization

### Changed — `client/src/canvas/particles/ParticleManager.js`

- **`init()`** — Particle presets and effects JSON fetches now use `${baseUrl}particle-presets.json` and `${baseUrl}particle-effects.json` instead of absolute paths
- **Category file fetches** — Individual preset category files (e.g. `particle-presets/combat.json`) now use `${baseUrl}${file}` instead of `/${file}`

---

## [Bugfix] — 2026-03-12 — Batch PVP Team A Frozen AI

**Summary:** Fixed a bug where Team A units in batch PVP matches would return WAIT every turn instead of fighting, causing most matches to hit the max turn limit (200) and end as draws. Skills, attacks, and movement were all working correctly — the root cause was an AI ownership lookup failure.

**Root cause:** Team A units are spawned as `ai_allies` with `hero_id` and `ai_stance="follow"`, which routes them into the stance-based AI system (`_decide_stance_action`). The stance system calls `_find_owner()` to locate the human player they should follow. In batch PVP mode, the only "human" is a dummy host that gets removed from `all_units` after match creation. With no owner found, `_find_owner()` returns `None` and the follow stance falls back to WAIT. Team B (`ai_opponents`) was unaffected because those units have `hero_id=None` and fall through to independent aggressive AI.

**Note:** This bug was not caused by the Refactor 1A skills split. PVPVE mode is also unaffected — it handles leaderless AI teams correctly by designating one unit per team as `is_team_leader=True`, which `_find_owner()` uses as a fallback.

### Changed — `server/batch_pvp.py`

- **`run_headless_match()`** — After removing the dummy host, Team A units now have their `hero_id` cleared, `ai_stance` set to `None`, and `ai_behavior` set to `"aggressive"`. This converts them from stance-based hero allies (which need a human owner) into independent AI combatants — identical behavior to Team B. Both teams now use the same AI decision engine for fair simulation.

---

## [Balance] — 2026-03-11 — Monster Rarity & Wave Arena Balance Pass

**Summary:** Addressed oppressive damage spikes from rarity-upgraded (champion/rare) monsters in the wave arena and dungeons. The wave spawner was missing the difficulty budget and enhanced-per-room cap systems that dungeons use, allowing uncapped rarity stacking. Additionally, several affix multipliers were tuned down to reduce multiplicative damage escalation that could one-shot tanks.

**Root cause:** The wave spawner (`_spawn_next_wave`) called `roll_monster_rarity()` per enemy with zero guardrails — no `max_enhanced_per_room` cap, no `difficulty_budget` downgrade, and no `floor_overrides` for affix count limits. A single wave could produce multiple rares with full 2-3 affixes each. Combined with multiplicative damage stacking (tier × champion × affix × aura), a rare Extra Strong ghoul with Might Aura nearby could deal 27+ damage/hit vs a crusader's 135 HP.

### Changed — `server/app/core/wave_spawner.py`

- **`_spawn_next_wave()`** — Ported difficulty budget and cap enforcement from dungeon `map_exporter.py`:
  - Tracks `wave_enhanced_count` per wave, capped by `max_enhanced_per_room` from config (respects `floor_overrides`)
  - Computes per-wave `difficulty_budget` via `get_room_budget(wave_number, enemy_count)` — deducts `get_rarity_cost()` per enemy, downgrades rare→champion→normal if over budget
  - Reads `floor_overrides` via `get_floor_override(wave_number)` to apply early-wave affix count caps (e.g. 1-2 affixes on waves 1-3 instead of 2-3)
  - Supports per-wave `max_rarity` field from wave config — downgrades rolled rarity if it exceeds the wave's declared cap

### Changed — `server/configs/maps/wave_arena.json`

- **Waves 1-3** — Added `"max_rarity": "normal"` — no rarity upgrades allowed on introductory waves
- **Waves 4-5** — Added `"max_rarity": "champion"` — champions allowed but rares blocked
- **Waves 6-10** — Unchanged (full rarity range, constrained by budget system)

### Changed — `server/configs/monster_rarity_config.json`

- **`extra_strong` affix** — Damage multiplier reduced from 1.5× to **1.3×** (was the single largest damage spike source)
- **`might_aura` affix** — Ally damage multiplier reduced from 1.25× to **1.15×** (was amplifying entire packs multiplicatively)
- **`conviction_aura` affix** — Enemy armor reduction reduced from -3 to **-2** (was devastating low-armor classes: -3 from 2 armor = near-zero)
- **`floor_bonus_per_level`** — Rarity chance scaling reduced from 0.015 to **0.01** per wave/floor (softens the rarity ramp on later waves)

### Before/After — Damage Comparison (Rare Extra Strong Ghoul vs Crusader)

| Scenario | Before | After |
|---|---|---|
| Raw hit (no aura) | 21 dmg (7 hits to kill) | 17 dmg (8 hits to kill) |
| With Might Aura nearby | 27 dmg (5 hits to kill) | 19 dmg (8 hits to kill) |
| + Conviction Aura debuff | 30 dmg (5 hits to kill) | 20 dmg (7 hits to kill) |

### Tests — 3,775 passing

- Updated 5 test assertions in `test_monster_rarity.py` to match new `extra_strong` (1.3×) and `floor_bonus_per_level` (0.01) values

---

## [Refactor 1A] — 2026-06-21 — Split skills.py into skill_effects/ sub-package

**Summary:** Extracted all 30 `resolve_*` skill-effect handler functions from the monolithic `skills.py` (3,818 lines) into a new `server/app/core/skill_effects/` sub-package with 7 domain-specific modules. `skills.py` retains config loading, validation, buff/CC/ward helpers, and the central `resolve_skill_action` dispatcher. All 3,774 tests pass; all existing import paths remain backward-compatible via re-exports.

### Added — `server/app/core/skill_effects/` (new sub-package)

- **`_helpers.py`** — Shared helpers: `_apply_skill_cooldown`, `_resolve_skill_entity_target`
- **`heal.py`** — 3 handlers: `resolve_heal`, `resolve_hot`, `resolve_aoe_heal`
- **`damage.py`** — 13 handlers: `resolve_multi_hit`, `resolve_ranged_skill`, `resolve_holy_damage`, `resolve_stun_damage`, `resolve_aoe_damage`, `resolve_aoe_magic_damage`, `resolve_ranged_damage_slow`, `resolve_magic_damage`, `resolve_aoe_damage_slow`, `resolve_lifesteal_damage`, `resolve_lifesteal_aoe`, `resolve_aoe_damage_slow_targeted`, `resolve_melee_damage_slow`
- **`buff.py`** — 9 handlers: `resolve_buff`, `resolve_aoe_buff`, `resolve_damage_absorb`, `resolve_shield_charges`, `resolve_evasion`, `resolve_conditional_buff`, `resolve_thorns_buff`, `resolve_cheat_death`, `resolve_buff_cleanse`
- **`debuff.py`** — 6 handlers: `resolve_dot`, `resolve_taunt`, `resolve_aoe_debuff`, `resolve_targeted_debuff`, `resolve_ranged_taunt`, `resolve_aoe_root`
- **`movement.py`** — 1 handler: `resolve_teleport`
- **`summon.py`** — 2 handlers: `resolve_place_totem`, `resolve_soul_anchor`
- **`utility.py`** — 2 handlers: `resolve_detection`, `resolve_cooldown_reduction`
- **`__init__.py`** — Re-exports all 36 public symbols for `from app.core.skill_effects import ...`

### Changed — `server/app/core/skills.py`

- Reduced from ~3,818 lines to ~580 lines
- Retains: config loading (`load_skills_config`, `get_skill`, `get_all_skills`, etc.), validation (`can_use_skill`), buff helpers (`tick_buffs`, `get_melee_buff_multiplier`, etc.), CC helpers (`is_stunned`, `is_slowed`, etc.), ward/absorb helpers, and the `resolve_skill_action` dispatcher
- Dispatcher now calls handlers imported from `skill_effects` sub-modules
- Bottom-of-file re-exports ensure `from app.core.skills import resolve_heal` continues to work across all 43 consumer files (13 app + 30 test files)

### Architecture — Circular Import Avoidance

- `_helpers.py` imports only from `app.models` (no circular risk)
- Sub-modules that need skills helpers (e.g., `get_effective_armor`) use **lazy imports** inside function bodies: `from app.core.skills import get_effective_armor`
- `skills.py` imports from `skill_effects` at the bottom of the file, after all local functions are defined

---

## [Phase 27D] — 2026-03-09 — PVPVE Victory Conditions & PVE Team

**Summary:** Implements PVPVE victory logic so that the match correctly ends when only one player team survives, regardless of how many PVE enemies remain alive. PVE enemies on the `"pve"` team are excluded from the victory calculation. Player teams are hostile to each other and to PVE enemies. PVE enemies target all player teams equally. 21 new Phase D tests, 37 total PVPVE tests passing.

### Changed — `server/app/core/combat.py`

- **`check_team_victory()`** — Added optional `excluded_teams: set[str] | None` parameter. When provided (e.g. `{"pve"}`), units on excluded teams are filtered out before counting survivors. PVE enemies being alive no longer blocks PVPVE victory.

### Changed — `server/app/core/turn_phases/deaths_phase.py`

- **`_resolve_victory()`** — Added optional `match_type: str | None` parameter. When `match_type == "pvpve"`, passes `excluded_teams={"pve"}` to `check_team_victory()`.

### Changed — `server/app/core/turn_resolver.py`

- **`resolve_turn()`** — Derives `match_type` from `match_state.config.match_type` and passes it to `_resolve_victory()` for PVPVE exclusion logic.

### Changed — `server/app/services/tick_loop.py`

- **`match_tick()`** — Added PVE team FOV computation: when `match.team_pve` is populated, adds a `"pve"` entry to `ai_team_fov_map` so PVE enemies share vision with nearby PVE allies.

### Tests — `server/tests/test_pvpve.py`

- **`TestCheckTeamVictoryExcludedTeams`** (7 tests): Victory with excluded PVE, draw when all player teams dead, 4-team scenarios, backward compatibility.
- **`TestResolveVictoryPVPVE`** (3 tests): `_resolve_victory()` integration with match_type exclusion.
- **`TestPVEAITargeting`** (5 tests): PVE enemies hostile to all player teams, PVE allies with each other.
- **`TestPlayerTeamsHostile`** (6 tests): Inter-team hostility, same-team allies, player-vs-PVE hostility.

---

## [Phase 27C] — 2026-03-09 — PVPVE Match Manager Flow

**Summary:** Implements the PVPVE match initialization pipeline in the match manager. When a PVPVE match starts, the system generates a procedural PVPVE dungeon, distributes players across 2–4 teams, spawns each team in their designated corner zone, initializes dungeon state (doors, chests), spawns all PVE enemies on the dedicated `"pve"` team, and computes initial FOV. Floor advancement and stairs are disabled for PVPVE (single-floor mode).

### Added — `match_manager.py`

- **`_PVPVE_TEAM_KEYS`** — Constant list `["a", "b", "c", "d"]` for team assignment ordering.
- **`_start_pvpve_match(match_id)`** — Top-level PVPVE initialization orchestrator. Calls team assignment → dungeon generation → smart spawns → class stats → dungeon state init → PVE enemy spawning in sequence.
- **`_assign_pvpve_teams(match_id)`** — Distributes human players + AI allies across teams. Host always goes to team A. Others round-robin across active teams. AI allies fill remaining team slots round-robin. Clears old team lists before reassignment. Updates each player's `.team` field.
- **`_generate_pvpve_dungeon(match)`** — Generates a WFC procedural dungeon using `FloorConfig.for_pvpve()`. Registers the map as `pvpve_{match_id}`. Assigns a random dungeon theme and stores the dungeon seed.
- **`_spawn_pvpve_enemies(match_id)`** — Spawns PVE enemies from room definitions. All enemies placed on `team="pve"` (read from spawn data). Enemy IDs tracked in `match.team_pve` (not in team_a/b/c/d). Full monster rarity system support: champion packs, rare minions, super unique bosses with retinue.

### Changed — `match_manager.py`

- **`start_match()`** — Added PVPVE branch that delegates to `_start_pvpve_match()` before the standard dungeon/PVP flow. Non-PVPVE matches unchanged.
- **`get_stairs_info()`** — Returns empty stairs for PVPVE matches (no stairs in single-floor mode).
- **`advance_floor()`** — Returns `None` immediately for PVPVE matches (no floor advancement).
- **`remove_match()`** — Now also cleans up `pvpve_{match_id}` runtime maps in addition to `wfc_{match_id}`.

### Tests

- 22 new tests in `test_pvpve_phase_c.py`:
  - `TestAssignPVPVETeams` (7 tests) — Host on team A, 2-team round-robin, 4-team distribution, 3-team (no team D), AI distribution, player.team field updates, old list clearing.
  - `TestPVPVEMatchStart` (5 tests) — Match starts successfully, pvpve_ map prefix, dungeon seed stored, theme assigned, dungeon state initialized.
  - `TestPVPVEEnemySpawning` (5 tests) — PVE enemies on "pve" team, team_pve populated, PVE IDs not in player teams, PVE are AI units, PVE tracked in ai_ids.
  - `TestPVPVEFOV` (1 test) — FOV computed for all alive units across all teams.
  - `TestPVPVENoFloorAdvancement` (3 tests) — No stairs info, advance_floor returns None, floor stays at 1.
  - `TestPVPVECleanup` (1 test) — remove_match unregisters PVPVE runtime map.

### Regression

- 3717 passing (+22 new) · 1 pre-existing failure (unrelated `test_turn_resolver.py` melee tracking assertion)

---

## [Phase 27B] — 2026-03-09 — PVPVE WFC Generation Pipeline

**Summary:** Extends the WFC dungeon generation engine to produce PVPVE-specific layouts. The decorator places 2–4 team spawn rooms in grid corners, a center boss room, applies a multi-spawn proximity ramp (safe → softened → normal), and computes a difficulty gradient (normal → hard → elite → boss) based on Manhattan distance to center. The map exporter tags all PVE enemies with `"team": "pve"`, collects per-team spawn zones, and emits `boss_room` metadata.

### Added — `dungeon_generator.py`

- **`FloorConfig.pvpve_mode`** (bool, default False) — Enables PVPVE layout generation.
- **`FloorConfig.pvpve_team_count`** (int, default 2) — Number of player teams (2–4).
- **`FloorConfig.for_pvpve()`** — Factory classmethod producing a FloorConfig optimized for PVPVE: 8×8 grid, floor 1, mid-tier roster, batch_size=5, balanced style, `empty_room_chance=0.15`.
- Updated `generate_dungeon_floor()` to inject `pvpve_mode`, `pvpve_team_count`, and `guaranteeStairs: False` into decorator settings when in PVPVE mode. Passes PVPVE params and decoration result to the map exporter.

### Added — `room_decorator.py`

- **`_PVPVE_DECORATOR_DEFAULTS`** — Config block for PVPVE-specific decorator settings (boss_guards, boss_chests, safe/softened enemy caps).
- **`_PVPVE_TEAM_CORNERS`** — Maps teams a–d to grid corners: a→top-left, b→bottom-right, c→top-right, d→bottom-left.
- **`_PVPVE_DIFFICULTY_TIERS`** — Distance-based difficulty tiers: boss (dist 0, 5 enemies), elite (dist 1, 5), hard (dist 2, 4), normal (3+, 3).
- **`_get_active_teams(team_count)`** — Returns active team letters based on count (clamped 2–4).
- **`_pvpve_assign_corner_spawns()`** — Places spawn rooms near target corners using `_find_nearest_flexible()`.
- **`_pvpve_assign_center_boss()`** — Places boss room at grid center, avoiding assigned rooms.
- **`_pvpve_compute_proximity_ramp()`** — Multi-spawn proximity ramp: distance 1 = "safe", distance 2 = "softened".
- **`_pvpve_compute_difficulty_tier()`** — Manhattan distance to center → tier name.
- **`_pvpve_get_max_enemies_for_tier()`** — Per-tier enemy count cap.
- Refactored `decorate_rooms()` with a PVPVE branch: corner spawns → center boss → proximity ramp → difficulty gradient. Standard dungeon path preserved unchanged.
- Phase 4 tile placement: PVPVE boss rooms get configurable extra guards + chests. Spawn-prefixed roles handled in placement and stats.
- Return value includes `pvpve_spawn_rooms` (team → {gridRow, gridCol}) and `pvpve_difficulty_tiers` when in PVPVE mode.

### Added — `map_exporter.py`

- **`export_to_game_map()`** — New params: `pvpve_mode`, `pvpve_team_count`, `decoration_result`.
- **Per-team spawn points** (`spawn_points_by_team`) — Groups S-tile spawn points by team using decorator's `pvpve_spawn_rooms` grid-cell lookup.
- **PVE team tagging** — All enemy spawns (regular E, boss B, super_unique, retinue) get `"team": "pve"` when in PVPVE mode.
- **Per-team spawn zones** — Built from grouped spawn points (expanded ±2 tiles for formation room), keyed by team letter.
- **Boss room metadata** — `boss_room` dict with id, bounds, enemy_spawns, chests.
- **Map type** — Set to `"pvpve"` instead of `"dungeon"` when in PVPVE mode.
- Top-level output includes `pvpve_team_count`, `spawn_points_by_team`, `boss_room`.

### Tests

- 63 new tests in `test_pvpve_phase_b.py`:
  - `TestFloorConfigPVPVE` (13 tests) — factory defaults, grid size, team clamping, density, roster, map name.
  - `TestPVPVEHelpers` (13 tests) — active teams, difficulty tiers, max enemies per tier.
  - `TestPVPVECornerSpawns` (5 tests) — 4-corner placement, 2-team mode, near-top-left/bottom-right, no adjacent spawns.
  - `TestPVPVECenterBoss` (2 tests) — near-center placement, no overlap with spawns.
  - `TestPVPVEProximityRamp` (3 tests) — safe/softened/no-override at correct distances.
  - `TestPVPVEDecoratorIntegration` (9 tests) — 4-team spawns, 2-team spawns, boss placement, no stairs, safe adjacency, metadata, difficulty tiers, boss guards.
  - `TestPVPVEExporter` (11 tests) — map_type, team_count, spawn zones, spawn points, enemy PVE tags, boss metadata, standard mode unchanged.
  - `TestPVPVEFullPipeline` (7 tests) — end-to-end generation, map type, dimensions, spawn zones, PVE tags, determinism.

### Regression

- All 335 existing WFC tests pass unchanged.

---

## [Phase 27A] — 2026-03-09 — PVPVE Data Model & Match Type

**Summary:** Foundation data model for the new PVPVE competitive dungeon mode. Adds the `PVPVE` match type enum, PVPVE-specific configuration fields on `MatchConfig`, and a `team_pve` list on `MatchState` for tracking PVE enemy IDs separately from player teams.

### Added

- **`MatchType.PVPVE`** — New enum value `"pvpve"` for competitive dungeon matches where 2–4 player teams fight PVE enemies and each other.

- **`MatchConfig` PVPVE fields:**
  - `pvpve_team_count` (int, default 2) — Number of player teams (2–4).
  - `pvpve_pve_density` (float, default 0.5) — PVE enemy density multiplier (0.0–1.0).
  - `pvpve_boss_enabled` (bool, default True) — Whether to spawn a center boss.
  - `pvpve_loot_density` (float, default 0.5) — Chest/loot density multiplier.
  - `pvpve_grid_size` (int, default 8) — WFC grid size for map generation.

- **`MatchState.team_pve`** — List of PVE enemy IDs (`list[str]`, default empty). Tracks PVE enemies separately so they can be excluded from player team victory checks.

### Tests

- 16 new tests in `test_pvpve.py`:
  - `TestMatchTypePVPVE` (5 tests) — enum existence, serialization, deserialization, config assignment, JSON round-trip.
  - `TestMatchConfigPVPVEFields` (7 tests) — default values for all 5 fields, custom values, full round-trip.
  - `TestMatchStatePVPVE` (4 tests) — empty default, ID storage, round-trip, full state with all teams + PVE.

### Test count

- 3632 passing (+16 new) · 1 pre-existing failure (unrelated `test_phase16d_unique_items.py`)

---

## [Phase 26D] — 2026-03-07 — AI Totem Awareness

**Summary:** AI-controlled heroes now recognize active healing totems as safe zones. They will retreat toward totems when critically injured, prefer kiting in the direction of a totem, and gently drift toward totem heal zones during normal combat when hurt — without being hard-locked to the totem's position.

### Added

- **`_find_nearest_healing_totem()` helper** — Scans `match_state.totems` for the closest alive, same-team healing totem within a configurable distance (`_TOTEM_RETREAT_MAX_DIST = 8` tiles). Returns the totem dict or `None`. Used by retreat, kiting, and combat positioning logic.

- **`_tile_inside_totem_radius()` helper** — Quick Chebyshev check for whether a tile is within a totem's `effect_radius`.

- **`_totem_biased_step()` helper** — Soft drift function for normal combat movement. When an AI hero is below 80% HP (`_TOTEM_DRIFT_HP_THRESHOLD`) and a healing totem is nearby, nudges the planned movement step toward a tile inside the totem's radius — but only if it doesn't lose progress toward the AI's actual move target. Creates a gentle "gravity well" effect without overriding combat goals.

- **Retreat Priority 1.5: Healing Totem** — New retreat destination slotted between "path toward support ally" (Priority 1) and "path toward owner" (Priority 2) in `_find_retreat_destination()`. When a low-HP hero triggers retreat and there's an active same-team healing totem within 8 tiles, the hero paths toward the totem center. If already inside the totem's effect radius, falls through to the next priority (no unnecessary repositioning).

- **Totem-biased kiting** — In both Follow and Aggressive stance kiting (Phase 8K-3), ranged roles now score retreat tiles with a totem proximity bonus (`_TOTEM_KITE_BIAS_WEIGHT = 2`). When stepping away from a melee threat, the AI prefers tiles that are inside (or closer to) a healing totem radius, while still maximizing distance from the threat. Falls back to the original retreat tile if no totem is active.

- **Totem-biased combat movement** — In both Follow and Aggressive stance "move toward target" phases, the planned A* step is passed through `_totem_biased_step()` when the AI is hurt. This causes injured heroes to naturally drift into totem heal zones during regular fighting without changing their target priorities.

- **Constants:**
  - `_TOTEM_RETREAT_MAX_DIST = 8` — Max distance for AI to consider retreating toward a totem
  - `_TOTEM_KITE_BIAS_WEIGHT = 2` — Scoring bonus when a kite tile is inside totem radius
  - `_TOTEM_DRIFT_HP_THRESHOLD = 0.80` — HP ratio below which soft drift activates

### Changed

- **`_find_retreat_destination()` signature** — Added optional `match_state=None` parameter to access `match_state.totems` for the new Priority 1.5 totem retreat.

- **`_decide_stance_action()` retreat call** — Now forwards `match_state=match_state` to `_find_retreat_destination()`.

- **`_decide_follow_action()` signature** — Added optional `match_state=None` parameter. Stance dispatch now forwards `match_state`.

- **`_decide_aggressive_stance_action()` signature** — Added optional `match_state=None` parameter. Stance dispatch now forwards `match_state`.

- **Follow stance kiting block** — Replaced simple `_find_retreat_tile` with totem-biased tile scoring when a healing totem is active.

- **Aggressive stance kiting block** — Same totem-biased tile scoring as Follow stance.

- **Follow stance movement** — Final "Move toward target" step now passes through `_totem_biased_step()`.

- **Aggressive stance movement** — Final "Move toward target" step now passes through `_totem_biased_step()`.

### File Changed

- `server/app/core/ai_stances.py` — All changes confined to this single file (~120 lines added).

### Not Changed

- **Hold stance** — Never moves; no totem awareness needed (by design).
- **Defensive stance** — 2-tile owner leash already constrains positioning; adding totem bias would conflict with the "stay near owner" mandate. No changes.
- **Enemy AI** — Enemies have no totem awareness (intentional — they don't cooperate with player totems).
- **Shaman's own AI** — The Shaman's totem placement logic (`_totemic_support_skill_logic` in `ai_skills.py`) is unchanged. The Shaman already places totems intelligently; this change makes *other* heroes aware of those totems.

### Design Notes

- **Soft preference, not hard lock** — No AI behavior is overridden. Totem proximity is a tiebreaker / secondary factor in every case. Heroes still chase enemies, still attack, still regroup with the owner. The totem is simply an attractive "safe zone" that the AI knows about.
- **Three tiers of totem awareness:**
  1. **Retreat** (strongest) — Critical HP heroes actively path TO the totem
  2. **Kiting** (medium) — Ranged heroes prefer kite directions near the totem
  3. **Combat drift** (gentlest) — Hurt heroes nudge toward totem during normal movement
- **All 3605 tests pass** (1 pre-existing failure in `test_phase16d_unique_items.py` unrelated to this change). 675 AI-specific tests pass with zero regressions.
