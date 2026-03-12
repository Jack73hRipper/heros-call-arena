# Friendly Swap Movement

**Feature:** Allow the player (and later, AI) to walk into a same-team ally to swap positions.

**Problem:** In narrow hallways and doorways, friendly units block each other. The player cannot walk through a stationary ally, and hero AI cannot pathfind through friendlies — even though the server's batch movement resolver *already supports* swap resolution when both units submit MOVE intents.

**Root cause:** Neither the client nor the AI ever *requests* a move onto an ally's tile, so the swap path in `resolve_movement_batch` never triggers.

---

## Current Architecture (Reference)

| Layer | File | Behavior |
|-------|------|----------|
| WASD input | `client/src/hooks/useWASDMovement.js` L121-123 | Blocks move if `occupiedMap` has any unit on target tile (regardless of team) |
| Click-to-move highlights | `client/src/hooks/useHighlights.js` L96-98 | **Already allows** clicking ally tiles (Phase 7A-2) — shows move highlight on same-team tiles |
| Right-click smart pathfinding | `client/src/canvas/pathfinding.js` L287-295 | Excludes `friendlyUnitKeys` from occupied set — A* can path *through* allies |
| Server batch resolver | `server/app/core/combat.py` L600-815 | Full swap/chain/rotation detection — **already works** when both units have MOVE intents |
| Server movement phase | `server/app/core/turn_phases/movement_phase.py` | Builds move intents from player actions, delegates to `resolve_movement_batch` — no swap injection for stationary allies |
| AI pathfinding | `server/app/core/ai_pathfinding.py` L24-80 | `_build_occupied_set` treats all other alive units as impassable (except vacating pending movers) |
| AI stances | `server/app/core/ai_stances.py` | Hero allies (follow/aggressive/defensive/hold) pathfind using occupied set — blocked by stationary same-team units |

**What already works:**
- `resolve_movement_batch` handles swaps/chains/rotations when both units submit MOVE (tested in `test_cooperative_movement.py` — `TestSwapMovement`)
- Click-to-move highlights (Phase 7A-2) already show ally-occupied tiles as valid move targets
- Right-click `generateSmartActions` already excludes friendly units from the A* blocked set

**What's missing:**
- WASD blocks ally tiles client-side (never sends the move)
- Server doesn't inject a reciprocal MOVE for a stationary ally being "pushed"
- AI pathfinding doesn't know it can walk through allies via swap

---

## Phase 1 — Player-Initiated Friendly Swap

**Scope:** The human player can walk into a same-team ally (WASD or click) to swap positions. The stationary ally is automatically pushed to the player's vacated tile.

### 1A — Client: Allow WASD Move onto Ally Tile

**File:** `client/src/hooks/useWASDMovement.js`

**Current code (L121-123):**
```js
// Occupied check (skip self — we're moving away from our own tile)
const occupant = occ[`${tx},${ty}`];
if (occupant && occupant.pid !== uid) return;
```

**Change:** Allow the move if the occupant is a same-team ally.

```js
// Occupied check — allow walking into same-team allies (server handles swap)
const occupant = occ[`${tx},${ty}`];
if (occupant && occupant.pid !== uid) {
  // Block WASD into enemies, but allow same-team for friendly swap
  if (!occupant.team || occupant.team !== propsRef.current.myTeam) return;
}
```

**New prop required:** `myTeam` must be passed into `useWASDMovement` and stored in `propsRef.current`. Check where `useWASDMovement` is called (likely `Arena.jsx` or a parent component) and add `myTeam` to the destructured props.

**Test:** WASD into a same-team ally should now send the MOVE action to the server instead of silently blocking.

### 1B — Server: Inject Reciprocal Move for Stationary Ally

**File:** `server/app/core/turn_phases/movement_phase.py`

**Where:** After building `move_intents` (after the for-loop at ~L80) and before calling `resolve_movement_batch`.

**Logic:**
1. Build a set of player IDs that already have a MOVE intent this tick.
2. For each move intent, check if the target tile is occupied by a same-team, alive, non-moving ally.
3. If yes, and the ally is NOT in `hold` stance, inject a synthetic MOVE intent for that ally → the mover's current position.
4. Pass all intents (original + synthetic) to `resolve_movement_batch`.

**Pseudocode:**
```python
# --- Friendly Swap Injection ---
# After move_intents is fully built, detect player-initiated swaps.
# If a mover targets a same-team stationary ally (not in hold stance),
# inject a reciprocal MOVE so the batch resolver handles it as a swap.
moving_pids = {mi["player_id"] for mi in move_intents}
swap_intents: list[dict] = []

for mi in move_intents:
    mover = players.get(mi["player_id"])
    if not mover:
        continue
    target_tile = mi["target"]
    # Find who's standing on the target tile
    for p in players.values():
        if not p.is_alive or p.extracted:
            continue
        if p.player_id == mi["player_id"]:
            continue
        if (p.position.x, p.position.y) != target_tile:
            continue
        # Found occupant on target tile
        if p.team != mover.team:
            break  # Cross-team — no swap
        if p.player_id in moving_pids:
            break  # Already moving — batch resolver handles naturally
        if getattr(p, 'ai_stance', None) == 'hold':
            break  # Hold stance — refuse swap
        # Inject reciprocal move: ally → mover's current position
        mover_pos = (mover.position.x, mover.position.y)
        swap_intents.append({
            "player_id": p.player_id,
            "target": mover_pos,
        })
        break

move_intents.extend(swap_intents)
```

**Edge cases handled:**
- Hold-stance allies refuse swap (they're told to stand still)
- Cross-team units are never swapped (only same-team)
- If the ally is already moving, the existing batch resolver handles it naturally
- Multiple players trying to swap with the same ally: `resolve_movement_batch` same-target-conflict resolution picks a winner (human > AI, then ID tiebreak)
- Stunned/slowed allies: these never make it into `move_intents` since their MOVE was already filtered above — the swap injection loop only checks `players`, so we need a guard:

```python
# Additional guard: don't swap stunned/slowed/channeling allies
from app.core.skills import is_stunned, is_slowed
if is_stunned(p) or is_slowed(p):
    break
if portal_context and _is_channeling(p.player_id, portal_context):
    break
```

### 1C — Server: Action Result Messages for Swaps

When a swap occurs, both units get a successful MOVE result from the batch resolver. The existing result-building code (`movement_phase.py` L87-105) already handles this — it updates positions and creates ActionResult messages for every successful move. No changes needed here.

**Optional enhancement:** Add a distinct message so the combat log can say "Alice swapped places with Bob" instead of two separate "moved to" messages.

```python
# In the results loop, after position updates:
# Check if this was a swap (player moved to where an ally was, and ally moved to player's old pos)
# If so, add a swap-specific log message
```

### 1D — Client: Visual Feedback (Optional Polish)

- Move highlight on ally tiles could use a distinct color (e.g., blue swap indicator vs. green move indicator)  
- Short "swap" animation or particle effect when two units exchange tiles
- Combat log message: "{Player} swapped places with {Ally}"

### 1E — Tests

**File:** `server/tests/test_cooperative_movement.py` (extend existing)

New test class: `TestFriendlySwapInjection`

| Test | Description |
|------|-------------|
| `test_player_walk_into_stationary_ally_swaps` | Player moves onto ally's tile → ally auto-swapped to player's old tile |
| `test_player_walk_into_enemy_no_swap` | Player moves onto enemy tile → no swap injection (treated as normal blocked move) |
| `test_player_walk_into_hold_stance_ally_blocked` | Player moves onto hold-stance ally → no swap, move fails |
| `test_player_walk_into_stunned_ally_blocked` | Player moves onto stunned ally → no swap, move fails |
| `test_player_walk_into_slowed_ally_blocked` | Player moves onto slowed ally → no swap, move fails |
| `test_player_walk_into_channeling_ally_blocked` | Player moves onto channeling ally → no swap, move fails |
| `test_two_players_swap_same_ally_one_wins` | Two movers target same stationary ally → one swaps, other fails |
| `test_swap_preserves_pre_move_snapshot` | Melee target tracking still uses correct pre-move positions after swap |
| `test_swap_chain_with_stationary` | A moves onto B (stationary), B auto-pushed to A's tile, C moves onto A's old tile → chain resolves correctly |
| `test_cross_team_no_swap` | Player on team A moves onto team B ally → no swap injection |

### Implementation Order

1. **1B** — Server swap injection (core mechanic)
2. **1E** — Tests (validate core mechanic works)
3. **1A** — Client WASD fix (enables player to trigger it)
4. **1C** — Action result messages (combat log polish)
5. **1D** — Visual feedback (optional polish)

### Files Modified (Phase 1)

| File | Change Type |
|------|------------|
| `server/app/core/turn_phases/movement_phase.py` | Add swap injection logic before `resolve_movement_batch` call |
| `client/src/hooks/useWASDMovement.js` | Relax occupied check for same-team allies |
| `server/tests/test_cooperative_movement.py` | Add `TestFriendlySwapInjection` test class |

### Files NOT Modified (Phase 1)

| File | Reason |
|------|--------|
| `server/app/core/combat.py` | `resolve_movement_batch` already handles swaps — no changes needed |
| `client/src/hooks/useHighlights.js` | Move highlights already include ally tiles (Phase 7A-2) |
| `client/src/canvas/pathfinding.js` | `generateSmartActions` already excludes friendly units — right-click path already works through allies |
| `client/src/hooks/useCanvasInput.js` | Click-to-move already permits clicking ally tiles (via moveHighlights) |
| `server/app/core/ai_pathfinding.py` | AI changes are Phase 2 |
| `server/app/core/ai_stances.py` | AI changes are Phase 2 |
| `server/app/core/ai_behavior.py` | AI changes are Phase 2 |

### Phase 1 — Implementation Log (March 7, 2026)

**Status: COMPLETE** — 12 new tests, 3408 total tests passing, 0 failures.

#### 1B — Server Swap Injection ✅
- **File:** `server/app/core/turn_phases/movement_phase.py`
- Added friendly swap injection logic after building `move_intents` and before calling `resolve_movement_batch`
- Builds `moving_pids` set to detect already-moving allies (no duplicate injection)
- Tracks `injected_allies` set to prevent multiple movers from injecting swaps for the same stationary ally
- Guards: cross-team blocked, already-moving blocked, hold stance blocked, stunned blocked, slowed blocked, channeling blocked, dead/extracted skipped

#### 1E — Tests ✅
- **File:** `server/tests/test_cooperative_movement.py`
- Added `TestFriendlySwapInjection` class with 12 tests:
  - `test_player_walk_into_stationary_ally_swaps` — happy path swap
  - `test_player_walk_into_enemy_no_swap` — cross-team blocked
  - `test_player_walk_into_hold_stance_ally_blocked` — hold stance refuses
  - `test_player_walk_into_stunned_ally_blocked` — stunned ally can't be swapped
  - `test_player_walk_into_slowed_ally_blocked` — slowed ally can't be swapped
  - `test_player_walk_into_channeling_ally_blocked` — channeling ally can't be swapped
  - `test_two_players_swap_same_ally_one_wins` — dedup: only first mover swaps
  - `test_swap_preserves_pre_move_snapshot` — melee tracking unbroken
  - `test_swap_chain_with_stationary` — chain + swap no duplicate tiles
  - `test_cross_team_no_swap` — enemy tiles never trigger swap
  - `test_ally_already_moving_no_injection` — explicit swap still works
  - `test_dead_ally_no_swap` — dead ally doesn't block, normal move succeeds
- Note: stunned/slowed/channeling tests use `_resolve_movement` directly to avoid buff tick interference from `_resolve_cooldowns_and_buffs`

#### 1A — Client WASD Fix ✅
- **File:** `client/src/hooks/useWASDMovement.js`
- Added `myTeam` prop to destructured params and `propsRef.current`
- Changed occupied check from hard-block to team-aware: enemies blocked, same-team allies allowed
- **File:** `client/src/components/Arena/Arena.jsx`
- Passed `myTeam` into `useWASDMovement` call

#### 1C — Action Result Messages ✅
- **File:** `server/app/core/turn_phases/movement_phase.py`
- Added swap detection in results loop: tracks `swap_injected_pids` set
- Injected allies get combat log message: "{Player} swapped places with {Mover}" instead of generic "moved to" message

#### 1D — Visual Feedback (Deferred)
- Move highlights already show ally tiles as valid targets (Phase 7A-2)
- Distinct swap color/animation can be added as future polish

---

## Phase 2 — AI-Initiated Friendly Swaps

**Scope:** Hero AI allies can pathfind through and swap with same-team units. Enemy AI is excluded (no enemy swap behavior).

### 2A — AI Pathfinding: Allow Pathing Through Same-Team

**File:** `server/app/core/ai_pathfinding.py`

**Function:** `_build_occupied_set`

**Current behavior:** All alive units (except the excluded unit) are treated as impassable. Same-team allies block A* just like enemies.

**Change:** Add an optional parameter to exclude same-team units from the occupied set. When enabled, A* will plan paths through allies, knowing the swap injection (Phase 1B) will resolve the collision.

```python
def _build_occupied_set(
    all_units: dict[str, PlayerState],
    exclude_id: str,
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    ghostly: bool = False,
    allow_team_swap: str | None = None,  # NEW: team letter to exclude from occupied
) -> set[tuple[int, int]]:
```

When `allow_team_swap` is set (e.g., `"a"`), units on that team are excluded from the occupied set — A* can plan paths through them.

**Guard:** Only exclude allies that are NOT in `hold` stance and NOT stunned/slowed. Hold-stance allies are intentionally immovable.

```python
# Inside the loop:
if allow_team_swap and u.team == allow_team_swap:
    # Don't block same-team allies (swap will handle it)
    # Unless they're in hold stance (immovable by design)
    if getattr(u, 'ai_stance', None) == 'hold':
        occupied.add(pos)
        continue
    if is_stunned(u) or is_slowed(u):
        occupied.add(pos)
        continue
    continue  # Skip — A* can path through this ally
```

### 2B — Server Movement Phase: Extend Swap Injection for AI

**File:** `server/app/core/turn_phases/movement_phase.py`

The swap injection logic from Phase 1B already works for any mover (human or AI). When an AI hero submits a MOVE onto a same-team stationary ally, the same injection logic creates a reciprocal MOVE. **No additional changes needed** — the Phase 1B implementation is team-based, not player-type-based.

### 2C — Stance Handlers: Pass Team Swap Flag

**File:** `server/app/core/ai_stances.py`

Each stance handler (`_decide_follow_action`, `_decide_aggressive_stance_action`, `_decide_defensive_action`) calls `_build_occupied_set`. Update these calls to pass `allow_team_swap=ai.team`:

```python
# Before (in each stance handler):
occupied = _build_occupied_set(all_units, ai_id, pending_moves)

# After:
occupied = _build_occupied_set(all_units, ai_id, pending_moves, allow_team_swap=ai.team)
```

**Hold stance exception:** `_decide_hold_action` should NOT pass `allow_team_swap` because hold-stance units never move — allowing swap pathfinding is pointless for units that won't move.

### 2D — Enemy AI: No Changes (Intentional)

Enemy AI behavior functions (`_decide_aggressive_action`, `_decide_ranged_action`, `_decide_boss_action`, `_decide_support_behavior`) should **NOT** use `allow_team_swap`. Reasons:

1. **Tactical:** Enemies blocking each other in doorways is a core part of the chokepoint strategy. If enemies could swap freely, the player's ability to create defensive formations would be weakened.
2. **Lore/feel:** Enemies are less coordinated than a trained party of heroes.
3. **Balance:** Enemy packs already have ghostly champions (Phase 18D) that can phase through units. Adding free swaps on top would make enemies too mobile.

### 2E — Anti-Oscillation Guard

**Risk:** Two AI heroes in a 1-wide hallway could pathfind *through* each other on alternating ticks, swapping back and forth endlessly without making progress.

**Mitigation — Swap Cooldown:**

Add a per-unit swap cooldown tracked in `_resolve_movement`:

```python
# Module-level: track last swap tick per unit
_last_swap_tick: dict[str, int] = {}  # {unit_id: last_turn_swapped}
_SWAP_COOLDOWN = 2  # Cannot swap again for 2 turns after a swap
```

Before injecting a swap intent, check:
```python
if p.player_id in _last_swap_tick:
    if current_turn - _last_swap_tick[p.player_id] < _SWAP_COOLDOWN:
        break  # Ally swapped too recently — skip
```

After a successful swap, record:
```python
_last_swap_tick[mover_pid] = current_turn
_last_swap_tick[swapped_pid] = current_turn
```

**Note:** The cooldown should NOT apply to player-initiated swaps (Phase 1). Only AI-initiated swaps need the oscillation guard. This means the swap injection logic needs to know whether the mover is human or AI.

### 2F — Retreat Through Allies

**File:** `server/app/core/ai_stances.py`

**Current:** `_find_retreat_destination` uses `_build_occupied_set` which blocks on allies. A retreating support hero stuck behind a tank in a hallway cannot escape.

**Change:** When retreating, use `allow_team_swap=ai.team` so the retreating hero can swap past the tank. This is a high-value improvement — the exact scenario (healer trapped behind melee) is a common frustration.

```python
# In _find_retreat_destination:
occupied = _build_occupied_set(
    all_units, ai_id, pending_moves=None,
    allow_team_swap=ai.team,
)
```

### 2G — Tests

**File:** `server/tests/test_cooperative_movement.py` (extend) or new `server/tests/test_friendly_swap_ai.py`

| Test | Description |
|------|-------------|
| `test_hero_ai_pathfinds_through_ally` | Hero AI in follow stance can plan a path through a stationary ally |
| `test_hero_ai_swap_creates_valid_move` | AI move onto ally tile → swap injection creates reciprocal intent → batch resolver approves both |
| `test_hold_stance_ally_not_swappable_by_ai` | AI cannot swap with a hold-stance ally |
| `test_enemy_ai_does_not_swap` | Enemy AI does not gain team-swap pathfinding |
| `test_oscillation_prevented` | Two AI heroes don't swap back and forth on consecutive ticks (cooldown enforced) |
| `test_retreat_through_ally` | Low-HP support hero retreats through melee ally via swap |
| `test_swap_cooldown_does_not_affect_player` | Player-initiated swaps ignore the AI cooldown |
| `test_ai_swap_with_stunned_ally_blocked` | AI cannot swap with a stunned same-team ally |

### Implementation Order

1. **2A** — AI pathfinding `allow_team_swap` parameter
2. **2C** — Stance handlers pass team swap flag
3. **2E** — Anti-oscillation cooldown guard
4. **2F** — Retreat through allies
5. **2G** — Tests
6. **2D** — Verify enemy AI unchanged (regression tests)

### Files Modified (Phase 2)

| File | Change Type |
|------|------------|
| `server/app/core/ai_pathfinding.py` | Add `allow_team_swap` param to `_build_occupied_set` |
| `server/app/core/ai_stances.py` | Pass `allow_team_swap` in follow/aggressive/defensive/retreat handlers |
| `server/app/core/turn_phases/movement_phase.py` | Add swap cooldown tracking + AI-only cooldown check |
| `server/tests/test_cooperative_movement.py` or new test file | Add Phase 2 test class |

### Files NOT Modified (Phase 2)

| File | Reason |
|------|--------|
| `server/app/core/combat.py` | Batch resolver unchanged |
| `server/app/core/ai_behavior.py` | Enemy AI functions — intentionally NOT given swap ability |
| `client/*` | No client changes needed — Phase 1 already handled all client-side fixes |

### Phase 2 — Implementation Log (March 7, 2026)

**Status: COMPLETE** — 8 new tests, 3416 total tests passing, 0 failures.

#### 2A — AI Pathfinding: allow_team_swap ✅
- **File:** `server/app/core/ai_pathfinding.py`
- Added `allow_team_swap: str | None = None` parameter to `_build_occupied_set`
- When set (e.g. `"a"`), same-team allies are excluded from the occupied set so A* can plan paths through them
- Guards: hold-stance allies remain blocked (immovable by design), stunned/slowed allies remain blocked (can't be swapped)
- Added `from app.core.skills import is_stunned, is_slowed` import
- Backward compatible: `None` default preserves existing behavior for all callers

#### 2C — Stance Handlers: Pass Team Swap Flag ✅
- **File:** `server/app/core/ai_stances.py`
- Updated shared precomputed occupied set in `_decide_stance_action` to pass `allow_team_swap=ai.team`
- This flows through to follow/aggressive/defensive stance handlers AND retreat logic via `precomputed_occupied`
- Updated portal retreat occupied set to also pass `allow_team_swap=ai.team`
- Hold stance is intentionally excluded — it never moves, so swap pathfinding is irrelevant

#### 2D — Enemy AI: No Changes (Verified) ✅
- Enemy AI behavior functions (`_decide_aggressive_action`, `_decide_ranged_action`, etc.) in `ai_behavior.py` do NOT call `_build_occupied_set` with `allow_team_swap`
- Enemy AI is excluded by design — verified via `test_enemy_ai_does_not_swap` test
- Chokepoint strategy preserved: enemies blocking each other in doorways remains a core tactical mechanic

#### 2E — Anti-Oscillation Cooldown Guard ✅
- **File:** `server/app/core/turn_phases/movement_phase.py`
- Added module-level `_last_swap_tick: dict[str, int]` tracking and `_SWAP_COOLDOWN = 2`
- Added `reset_swap_cooldowns()` helper for test isolation
- Added `current_turn: int = 0` parameter to `_resolve_movement`
- Cooldown check runs in swap injection loop: only applies when `mover.unit_type != 'human'` (AI movers only)
- After successful swap, both participants' IDs are recorded with the current turn number
- Player-initiated swaps are always exempt from the cooldown
- **File:** `server/app/core/turn_resolver.py`
- Passes `current_turn=turn_number` to `_resolve_movement` call

#### 2F — Retreat Through Allies ✅
- No separate code change needed — the shared precomputed occupied set in `_decide_stance_action` (updated in 2C) already flows into `_find_retreat_destination` via the `occupied` parameter
- Retreat pathfinding automatically benefits from `allow_team_swap` since the occupied set excludes same-team allies
- Verified via `test_retreat_through_ally` test: low-HP healer can now path through tank in a 1-wide corridor

#### 2G — Tests ✅
- **File:** `server/tests/test_cooperative_movement.py`
- Added `TestFriendlySwapAI` class with 8 tests:
  - `test_hero_ai_pathfinds_through_ally` — `_build_occupied_set` excludes same-team allies with `allow_team_swap`, blocks enemies
  - `test_hero_ai_swap_creates_valid_move` — AI mover triggers swap injection, both units move successfully
  - `test_hold_stance_ally_not_swappable_by_ai` — hold-stance ally stays in occupied set AND blocks swap injection
  - `test_enemy_ai_does_not_swap` — enemy AI without `allow_team_swap` keeps allies blocked
  - `test_oscillation_prevented` — 3-turn scenario: swap at T1, blocked at T2 (cooldown), allowed at T3 (expired)
  - `test_retreat_through_ally` — corridor scenario: healer paths through tank with `allow_team_swap`, blocked without it
  - `test_swap_cooldown_does_not_affect_player` — human player can swap even when ally has active AI cooldown
  - `test_ai_swap_with_stunned_ally_blocked` — stunned ally stays blocked in both occupied set and swap injection

---

## Risk Assessment

| Risk | Phase | Severity | Mitigation |
|------|-------|----------|------------|
| Tank pushed out of chokepoint by player walking into them | 1 | Medium | Only the mover initiates; hold-stance allies refuse |
| Melee target tracking broken by swap | 1 | Low | `pre_move_occupants` snapshot already captures positions before any movement |
| Two movers try to swap same stationary ally | 1 | Low | `resolve_movement_batch` same-target-conflict picks one winner |
| AI oscillation (swap back-and-forth) | 2 | Medium | 2-turn swap cooldown for AI-initiated swaps |
| Enemy chokepoint strategy weakened | 2 | High | Enemy AI explicitly excluded from team-swap pathfinding |
| AI hero swaps ally during melee engagement | 2 | Low | Swap only triggers when AI's A* plans through an ally — if the ally is already fighting, the AI would path around or wait |
| Ghostly champion + swap stacking | 2 | None | Ghostly already returns empty occupied set — no interaction |
| Portal extraction disrupted by swap | 1-2 | Low | Channeling allies refuse swap (guard in place) |

---

## Summary

| | Phase 1 | Phase 2 |
|---|---------|---------|
| **Who can initiate** | Human player only | Human player + Hero AI allies |
| **Server files** | `movement_phase.py` | `ai_pathfinding.py`, `ai_stances.py`, `movement_phase.py` |
| **Client files** | `useWASDMovement.js` | None |
| **Test files** | `test_cooperative_movement.py` | `test_cooperative_movement.py` or new file |
| **Estimated new code** | ~40 lines server + ~5 lines client | ~30 lines server |
| **New tests** | ~10 tests | ~8 tests |
| **Risk to existing behavior** | Low — only changes what happens when you walk into a friendly | Medium — changes how AI pathfinds (but enemy AI untouched) |
