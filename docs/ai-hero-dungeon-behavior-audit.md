# AI Hero Dungeon Behavior Audit — March 19, 2026

Findings from headless PvPvE batch simulation (`seed 42`, 8x8 grid, 5 heroes/team, 300 turn limit).  
Match ended in a **DRAW** — no team won in 300 turns due to multiple stalling bugs.

---

## BUG 1: Shaman Totem Spam — `match_state` not threaded to `_decide_skill_usage`

**Severity:** Critical  
**Affected teams:** Any team whose leader or follower is a Shaman (or any totem-using class)  
**Observed:** Team C Shaman leader cast `searing_totem` every time it came off cooldown from **T30 to T300** (270 turns), rarely moving. The entire party was pinned fighting a single PVE skeleton for the whole match.

### Root Cause

`_decide_skill_usage()` in `ai_skills.py` accepts an optional `match_state` parameter to check active totems via `match_state.totems`. However, **none of the 4 call sites pass `match_state`**, so it's always `None`.

Inside `_totemic_support_skill_logic` (ai_skills.py ~line 1910):
```python
my_totems: list[dict] = []
if match_state is not None and hasattr(match_state, "totems"):
    my_totems = [t for t in match_state.totems if t.get("owner_id") == ai.player_id]

has_searing_totem = any(t["type"] == "searing_totem" for t in my_totems)
```
With `match_state=None`, `my_totems` is always `[]`, so `has_searing_totem` is always `False` → the Shaman recasts every 6 turns.

### Affected Call Sites

All 4 behavior functions call `_decide_skill_usage` without `match_state`:

| # | File | Line | Behavior |
|---|------|------|----------|
| 1 | `ai_behavior.py` | 924 | `_decide_aggressive_action` |
| 2 | `ai_behavior.py` | 584 | `_decide_support_behavior` |
| 3 | `ai_behavior.py` | 1285 | `_decide_ranged_action` |
| 4 | `ai_behavior.py` | 1536 | `_decide_boss_action` |

Additionally, the 4 behavior functions themselves don't accept `match_state` as a parameter, and the dispatcher `decide_ai_action()` (which does receive `match_state`) doesn't pass it down:

| Function | Accepts `match_state`? |
|----------|----------------------|
| `decide_ai_action()` (line 314) | Yes ✓ |
| `_decide_aggressive_action()` (line 669) | **No** |
| `_decide_support_behavior()` (line 419) | **No** |
| `_decide_ranged_action()` (line 1133) | **No** |
| `_decide_boss_action()` (line 1433) | **No** |

### Fix

1. Add `match_state=None` parameter to all 4 behavior function signatures.
2. Pass `match_state=match_state` from `decide_ai_action()` dispatcher to each behavior call (~line 405–413).
3. Forward `match_state=match_state` in each behavior's call to `_decide_skill_usage()`.

---

## BUG 2: Patrol Bounce Loop — Leader stuck oscillating between 2 tiles

**Severity:** Critical  
**Affected teams:** Any team whose leader enters patrol mode near a map edge or dead-end  
**Observed:** Team B Mage leader bounced between `(61,62)` ↔ `(61,61)` with reason `[patrol_move]` from **T243 to T300** (57 turns). Entire 5-unit party was effectively frozen.

### What happens each turn

1. Mage is at `(61,62)`, waypoint system sees it arrived (or needs new waypoint).
2. `_pick_patrol_waypoint` selects a center-biased distant waypoint.
3. A* returns `(61,61)` as the first step toward it.
4. Next turn at `(61,61)`, the waypoint is re-evaluated (possibly unreachable / already there / new pick).
5. A* returns `(61,62)` or the AI oscillates back.
6. Repeat forever.

### Root Cause (ai_patrol.py)

**Weak visited-tile penalty**: The visited history is 15 tiles with only a `-5.0` penalty. On a 64×64 map, center-bonus scoring easily outweighs this, so the AI keeps picking waypoints that funnel through the same chokepoint.

**Oscillation suppressor misses this pattern** (ai_behavior.py ~line 1690): The existing detector checks if `target == history[-2]` (exact A→B→A in 2 ticks). But the patrol bounce can evade it because:
- The oscillation is mediated by the waypoint system (not a simple retreat→advance).
- When suppressed to WAIT, the history shifts and the next tick allows the move through again.

### Fix Options

- **Option A**: Increase visited history from 15 → 30+ and penalty from `-5.0` → `-15.0` or higher.
- **Option B**: In `_patrol_action`, after A* returns the next step, reject it if it's the tile the AI just came from (i.e. `next_step == _visited_history[ai_id][-2]` if available), and instead pick a new waypoint.
- **Option C**: Add a stale-position detector — if a leader has been in the same 3×3 area for N turns (e.g. 10) with no combat, force a new waypoint at least 15+ tiles away from current position.
- **Recommended**: Combine B + C for robust fix.

### Fix Applied — March 19, 2026

**Combined A + B + C** implemented across `ai_patrol.py` and `ai_behavior.py`. All 3993 tests passing.

**Option A — Stronger visited-tile penalty:**
- `_MAX_VISIT_HISTORY` raised from `15` → `30` (longer memory of where the AI has been).
- Visited-tile scoring penalty increased from `-5.0` → `-15.0` (now strong enough to overcome center-bonus on 64×64 maps, which was the core reason the AI kept funneling through the same chokepoint).

**Option B — Back-step rejection in `_patrol_action`:**
- After `get_next_step_toward()` returns the next tile, the patrol system now checks if `next_step == _visited_history[ai_id][-2]` (the tile we just came from).
- If so, the current waypoint is discarded and `_pick_patrol_waypoint()` is called again with a `min_distance=5` floor to force a meaningfully different direction.
- If the replacement waypoint *also* tries to back-step, falls back to `_random_adjacent_move()` to guarantee forward progress.

**Option C — Stale-position detector:**
- New module-level state: `_stale_area_counter` dict, `_STALE_AREA_THRESHOLD = 10`, `_STALE_FORCE_MIN_DIST = 15`.
- Every patrol tick, the last 10 visited positions are checked. If all fit within a 3×3 bounding box (`max - min <= 2` on both axes), the AI is considered "stuck."
- When stuck, `_pick_patrol_waypoint()` is called with `min_distance=15`, filtering out any candidate closer than 15 Manhattan tiles. This guarantees the AI picks a far-off breakout waypoint.
- If the map is too small / crowded for a 15-tile distant waypoint, the function gracefully retries without the distance floor.

**Cleanup:**
- `_stale_area_counter` is imported into `ai_behavior.py` and properly cleaned up in both the dead-unit handler and `clear_ai_patrol_state()`.

**Files changed:**
- `server/app/core/ai_patrol.py` — All three options implemented here (constants, `_patrol_action`, `_pick_patrol_waypoint`).
- `server/app/core/ai_behavior.py` — Import of `_stale_area_counter`, cleanup in dead-unit handler + `clear_ai_patrol_state()`.

---

## BUG 3: Ranged Kite Oscillation — Inquisitor bounces between 2 tiles while fighting

**Severity:** Moderate  
**Affected teams:** Any team with a ranged leader fighting a melee target  
**Observed:** Team D Inquisitor 2 alternated between `(17,9)` and `(18,9)` for 100+ turns:
- `aggro_pathfind_toward_target` → move to `(18,9)`
- `aggro_kite_retreat` → move back to `(17,9)`
- Fire ranged attack / skill between moves

### Root Cause (ai_behavior.py, aggressive behavior)

The kite-retreat distance threshold and the approach threshold overlap. The AI:
1. Is at range 2 → approaches to range 1 (`aggro_pathfind_toward_target`)
2. Now adjacent → retreats 1 tile (`aggro_kite_retreat`)
3. Now at range 2 again → cycle repeats

The AI IS fighting (casting skills, doing damage), so it's not a complete stall, but the positional oscillation wastes movement actions and slows kill speed.

### Fix Options

- **Option A**: After a kite retreat, suppress re-approach for 1–2 turns (prefer ranged attack at current distance).
- **Option B**: Only kite-retreat if the AI took melee damage last turn, not just because an enemy is adjacent.
- **Option C**: Integrate with oscillation suppressor — if the kite→approach cycle is detected, hold position and ranged attack instead of moving.

---

## BUG 4: Follower Cascade Stall — Entire party freezes when leader stalls

**Severity:** Systemic (amplifies Bugs 1–3)  
**Affected teams:** All  
**Observed:** When Team B's Mage leader bounced (Bug 2):
- **Revenant**: `WAIT [follow_idle]` every turn (within 1 tile of leader, leader not moving)
- **Confessor/Crusader/Inquisitor**: `[follow_trail_owner]` chasing the leader's bounce, shuffling back and forth between 3–4 tiles

### Root Cause (ai_stances.py, `_decide_follow_action`)

Followers decide based on distance to owner:
- `dist_to_owner <= 1` + no visible enemies + leader didn't move → `follow_idle` (WAIT)
- `dist_to_owner > 1` → pathfind toward owner (`follow_trail_owner`)

When a leader bounces, some followers hover at distance 1 (idle), others trail at distance 2+ (chase). None of them explore independently or seek enemies on their own.

### Fix Options

- **Option A**: If a follower has been in `follow_idle` for N turns (e.g. 5+) with no combat, temporarily switch to independent patrol-like behavior to scout nearby rooms.
- **Option B**: Give followers a "boredom" timer — after N idle turns, they widen their aggro range or path toward the nearest unexplored area rather than hugging the leader.
- **Note**: This is less urgent if Bug 2 (patrol bounce) is fixed, since leaders would stop stalling. But it would add resilience against any future stall scenarios.

---

## Simulation Summary

| Team | Leader | Behavior | Issue |
|------|--------|----------|-------|
| A | Shaman | Fighting Team D near (20,10) | Mostly healthy — engaged in combat throughout. Some totem spam (Bug 1) but had enemies nearby so still functional. |
| B | Mage | Patrol bounce at (61,62)↔(61,61) | **Frozen from T243–T300** (Bug 2 + Bug 4). Never found other teams. |
| C | Shaman | Stuck near (45,1) spamming totems | **Stalled from T30–T300** (Bug 1 + Bug 4). Never explored beyond spawn area. |
| D | Inquisitor 2 | Kite-oscillating vs Team A | Fighting but inefficient (Bug 3). Position bounced between 2 tiles for 100+ turns. |

### Priority for Fixes

1. **Bug 1** (match_state threading) — Straightforward code change, 4 call sites. Biggest impact: Shamans will stop wasting turns on redundant totems.
2. **Bug 2** (patrol bounce) — Needs patrol system improvement. Prevents entire parties from stalling at map edges.
3. **Bug 3** (kite oscillation) — Lower priority, AI is still fighting. Quality-of-life improvement for combat efficiency.
4. **Bug 4** (follower cascade) — Systemic amplifier. Fixing Bugs 1–2 removes the main triggers; standalone fix is optional hardening.

### Reproduction

```bash
cd server
python batch_pvpve.py --seed 42 --verbose --log pvpve_debug_analysis.txt --ascii-every 10
```

Full movement log saved to `server/pvpve_debug_analysis.txt`.
