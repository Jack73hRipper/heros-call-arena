# AI Hero Party Stalling Analysis

**Date:** March 19, 2026  
**Method:** PvPvE batch simulation (`batch_pvpve.py --verbose --grid-size 6 --max-turns 150 --log movement-analysis.txt`)  
**Match:** 6x6 grid (48x48 tiles), 4 teams of 5 heroes, 25 PVE enemies, cursed_shrine theme

---

## Summary

AI hero parties generally behave well but exhibit periodic stalling where heroes stop moving for 5–17+ consecutive turns. Three distinct patterns were identified, all rooted in the follow-stance idle logic and occupied-tile pathfinding.

---

## Stalling Patterns

### Pattern 1: Follower Spawn Congestion (Most Common)

**What happens:** At match start, teams spawn in tight clusters (1–2 tiles apart). Followers immediately evaluate `dist_to_owner <= 2` and hit the WAIT fallback. They sit idle until the leader walks far enough away (>2 tiles) to trigger the regroup threshold.

**Evidence from simulation:**
- Team C: 4 of 5 heroes WAITing T1–T9 (Mage 2: 9 consecutive, Ranger: 7 consecutive, Blood Knight: 5 consecutive)
- Team A: Revenant 9 WAITs, Shaman 9 WAITs, Inquisitor 9 WAITs in first 20 turns
- Team D: Shaman 10 WAITs, Hexblade 2: 7 WAITs in first 20 turns

**Root cause code:**

File: `server/app/core/ai_stances.py`, function `_decide_follow_action()`, Priority 3 (~line 1090):
```python
# Priority 3: No enemies — if too far from owner (>2), path toward them
if dist_to_owner > 2:
    next_step = get_next_step_toward(...)
    ...

# Close enough, no enemies — Phase 29A: seek nearby unopened chests
# ... chest seeking ...

return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)  # ← STUCK HERE
```

The `dist_to_owner > 2` threshold creates a dead zone where followers are "close enough" to idle but the leader hasn't moved far enough to trigger regroup.

**Fix:** Reduce the idle follow distance from `> 2` to `> 1`. Followers should only WAIT when literally adjacent (distance 1), not within a 2-tile radius. This makes followers start trailing the leader one turn earlier, preventing the spawn pile-up.

**Implementation:**
- File: `server/app/core/ai_stances.py`
- In `_decide_follow_action()`, change `if dist_to_owner > 2:` to `if dist_to_owner > 1:`
- This is the Priority 3 block (no enemies, path toward owner)

---

### Pattern 2: Corridor Gridlock / Occupied-Tile Blocking

**What happens:** When multiple followers try to pathfind toward the same leader position in narrow corridors, A* returns `None` for several of them because tiles are occupied. Even with `allow_team_swap` enabled, when 3–4 units all target the same 1-tile goal simultaneously, the pathfinder can't resolve valid steps for everyone.

**Evidence from simulation:**
- Team D, T25–T29: 4 of 5 heroes WAITing simultaneously while the leader (Plague Doctor) oscillated back and forth. All clustered around (15–16, 42–43).
- Team D Hexblade 2: 17 consecutive WAITs (T17–T33) — the longest stall observed. The team was moving through a corridor section and the Hexblade couldn't find a path to follow.

**Root cause code:**

File: `server/app/core/ai_stances.py`, Priority 1 regroup block (~line 900):
```python
follow_leash = 6 if role in ("sustain_dps", "retaliation_tank") else 4
if dist_to_owner > follow_leash:
    next_step = get_next_step_toward(...)
    if next_step:
        ...
    return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)  # ← A* failed
```

And generally throughout the follow action where `get_next_step_toward()` returns `None`.

**Fix:** Add a "leader is moving" tether — when the leader's position changed since last turn and the follower is idle, the follower should attempt to path toward the leader even within the normal idle threshold. This prevents the cluster from forming in the first place.

**Implementation approach:**
- Track leader's previous position (can use the existing `_POSITION_HISTORY` dict in `ai_behavior.py`)
- In `_decide_follow_action()`, after the idle `dist_to_owner <= 2` check, add: if the owner moved this turn (position differs from last known), attempt to path toward them regardless of distance threshold
- This gives followers "momentum" — they keep moving as long as the leader is moving

---

### Pattern 3: Post-Combat Stalling

**What happens:** After combat ends and all enemies in FOV are dead, hero allies with `hero_id is not None` hit the explicit "hold position" WAIT in the aggressive behavior path. Combined with the follow-stance `dist <= 2 → WAIT`, the whole party freezes until the leader finds a new target, chest, or memory location.

**Evidence from simulation:**
- Team C Blood Knight: 10 consecutive WAITs (T43–T52) immediately after a combat engagement ended
- Team A Inquisitor: 5 consecutive WAITs (T11–T15) between combat phases
- Team D Shaman: 7 consecutive WAITs (T25–T31) post-combat idle

**Root cause code:**

File: `server/app/core/ai_behavior.py`, `_decide_aggressive_action()`, Step 4c (~line 813):
```python
# 4c: Party members (hero allies) hold position instead of patrolling.
# This prevents aimless wandering that hinders gameplay.
if ai.hero_id is not None:
    return PlayerAction(player_id=ai.player_id, action_type=ActionType.WAIT)
```

This is intentional to prevent aimless wandering, but it causes multi-turn stalling when the leader is also idle or exploring slowly.

**Fix:** Add a post-combat follow impulse. After enemies die within sight, give followers a 3–5 turn grace period where they trail the leader instead of immediately going idle. This keeps the party advancing together after clearing a room.

**Implementation approach:**
- Add a per-unit `_last_combat_turn` tracker (dict in ai_behavior.py module scope)
- When a follower sees enemies or takes a combat action, record the turn number
- In the Step 4c "hold position" check, if `current_turn - _last_combat_turn[ai_id] <= 5`, skip the WAIT and instead path toward the leader (same logic as follow stance Priority 3)
- After 5 idle turns post-combat, resume normal WAIT behavior

---

## Match Statistics

| Team | Total Actions | MOVE | SKILL | ATTACK | RANGED | WAIT | WAIT % |
|------|--------------|------|-------|--------|--------|------|--------|
| A | 750 | 398 | 225 | 4 | 3 | 114 | 15.2% |
| B | 652 | 313 | 243 | 28 | 7 | 59 | 9.0% |
| C | 445 | 291 | 74 | 10 | 9 | 57 | 12.8% |
| D | 661 | 321 | 209 | 2 | 9 | 115 | 17.4% |
| PVE | 2015 | 134 | 58 | 47 | 20 | 1755 | 87.1% |

PVE WAIT% is expected (room-leashed enemies idle when no targets nearby).

### Worst Wait Streaks (Hero Parties Only)

| Hero | Max Streak | Start Turn | Total WAIT% | All Streaks (3+) |
|------|-----------|------------|-------------|-------------------|
| Team D Hexblade 2 | 17 turns | T17 | 26% | T1x3, T17x17, T36x4, T41x7 |
| Team C Blood Knight | 10 turns | T43 | 18% | T4x5, T43x10 |
| Team C Mage 2 | 9 turns | T1 | 16% | T1x9, T43x3 |
| Team D Mage 3 | 9 turns | T39 | 20% | T14x3, T23x7, T39x9 |
| Team A Revenant | 8 turns | T9 | 19% | T9x8, T34x4, T53x6, T89x4 |
| Team C Ranger | 7 turns | T1 | 11% | T1x7, T46x4 |
| Team D Shaman | 7 turns | T25 | 21% | T1x4, T17x3, T25x7, T45x5 |

---

## Implementation Priority

1. **Fix Pattern 1 first** (spawn congestion) — simplest change, biggest impact. One-line threshold change in `ai_stances.py`.
2. **Fix Pattern 3 second** (post-combat stalling) — moderate complexity, adds a combat memory tracker to `ai_behavior.py`.
3. **Fix Pattern 2 last** (corridor gridlock) — most complex, requires leader movement tracking and tether logic.

---

## Key Files

| File | Relevance |
|------|-----------|
| `server/app/core/ai_stances.py` | Follow stance decision logic, idle threshold, regroup leash |
| `server/app/core/ai_behavior.py` | Aggressive behavior, hero ally hold-position, patrol fallback |
| `server/app/core/ai_pathfinding.py` | A* pathfinding, occupied-set building, friendly swap |
| `server/app/core/ai_memory.py` | Enemy memory tracking, target persistence |
| `server/app/core/ai_patrol.py` | Waypoint patrol (enemy-only, not relevant to hero stalling) |

## Testing

After implementing fixes, re-run:
```
python batch_pvpve.py --verbose --grid-size 6 --max-turns 150 --log movement-post-fix.txt
```

**Success criteria:**
- Max consecutive WAIT streak for any hero should drop from 17 to <5
- Overall hero team WAIT% should drop from 12–17% to <8%
- No regressions in combat behavior (heroes should still fight, kite, and retreat normally)
- Early game (T1–T20) should show near-zero WAIT for followers
