# Stance System Overhaul — Role-Aware AI Stances

## Overview

The stance system (Follow, Aggressive, Defensive, Hold) was implemented in Phase 7C when only 5 classes existed and AI decision-making was limited. Since then, the class roster has grown to 11 hero classes across 11 roles, and extensive role-aware logic has been added to Follow and Aggressive stances — but **Defensive and Hold were never updated**. A Mage on Defensive walks into melee exactly like a Crusader. A Hold-stance tank attacks a random adjacent enemy instead of the most dangerous one.

**Goal:** Make all 4 stances role-aware so that class identity is preserved regardless of stance choice. Fix bugs in existing stance handlers. Ensure support/ranged/caster classes don't lose their intelligence when the player switches them off Follow.

---

## Current State (Diagnosed)

### Role-Awareness Per Stance

| Feature | Follow | Aggressive | Defensive | Hold |
|---------|--------|------------|-----------|------|
| Support positioning | ✅ (4 roles) | ❌ | ❌ | N/A |
| Ranged kiting | ✅ (6 roles) | ✅ (5 roles*) | ❌ | N/A |
| Variable kite thresholds | ✅ | ✅ | ❌ | N/A |
| Bard ally-centroid kiting | ✅ | ❌ | ❌ | N/A |
| Totem-biased kiting | ✅ | ✅ | ❌ | N/A |
| Totem-biased movement | ✅ | ✅ | ❌ | N/A |
| Controller hold-position | ✅ | ✅ | ❌ | N/A |
| Extended leash by role | ✅ | ❌ | ❌ | N/A |
| `_pick_best_target` | ✅ | ✅ | ✅ | ❌ |
| Skills (pre-dispatch) | ✅ | ✅ | ✅ | ✅ |
| Retreat (pre-dispatch) | ✅ | ✅ | ✅ | ❌ |

*Aggressive is missing `offensive_support` (Bard) from its `is_ranged_role` set — Bards don't kite in Aggressive.

### Current 11 Hero Classes & Roles

| Class | Role | Archetype | Key Stance Issue |
|-------|------|-----------|-----------------|
| Crusader | tank | Melee frontline | — (fine) |
| Confessor | support | Backline healer | Defensive/Aggressive: charges enemies instead of positioning near allies |
| Inquisitor | scout | Ranged skirmisher | Defensive: walks into melee |
| Ranger | ranged_dps | Pure ranged | Defensive: walks into melee |
| Hexblade | hybrid_dps | Melee + utility | — (fine) |
| Mage | caster_dps | Glass cannon caster | Defensive: walks into melee |
| Bard | offensive_support | Buffer/kiter | Aggressive: doesn't kite (bug). Defensive: walks into melee |
| Blood Knight | sustain_dps | Melee lifesteal | — (fine) |
| Plague Doctor | controller | Ranged debuffer | Defensive: walks into melee (worst case — 85 HP caster) |
| Revenant | retaliation_tank | Thorns tank | — (fine) |
| Shaman | totemic_support | Totem placer | Defensive: walks into melee |

### Relevant Files

| File | Role |
|------|------|
| `server/app/core/ai_stances.py` | All 4 stance handlers + retreat + potion + shared dispatch |
| `server/app/core/ai_skills.py` | `_CLASS_ROLE_MAP`, `_decide_skill_usage()`, role skill handlers |
| `server/app/core/ai_behavior.py` | Re-exports from ai_stances, `_find_retreat_tile` |
| `server/app/core/ai_memory.py` | `_pick_best_target`, `_update_enemy_memory` |
| `server/app/core/party_manager.py` | `set_unit_stance`, `set_all_stances`, stance validation |

---

## Phase S1 — Quick Fixes (Bug Fixes) ✅ COMPLETE

Two small, surgical changes. No design decisions needed — these are clearly bugs or oversights.

**Completed:** 2026-03-13 · 3747 tests passing (0 regressions)

### S1-A: Fix Bard Kiting in Aggressive Stance

**Problem:** In `_decide_aggressive_stance_action()`, the `is_ranged_role` check does not include `offensive_support`, so Bards on Aggressive stance don't kite. They DO kite in Follow stance. This is a copy-paste gap from when Bard was added.

**Fix:** Add `"offensive_support"` to the `is_ranged_role` role tuple in `_decide_aggressive_stance_action()`.

**File:** `server/app/core/ai_stances.py`

**Before:**
```python
is_ranged_role = role in ("ranged_dps", "scout", "caster_dps", "controller", "totemic_support") if role else False
```

**After:**
```python
is_ranged_role = role in ("ranged_dps", "scout", "caster_dps", "controller", "totemic_support", "offensive_support") if role else False
```

**Also add Bard ally-proximity kiting** (present in Follow, missing in Aggressive):
When computing `_find_retreat_tile` for Bards in Aggressive, pass `ally_positions` so the kite direction stays near the ally centroid — matching Follow stance behavior.

**Test:** Run existing AI test suite. Manual test: put a Bard on Aggressive in a dungeon, verify they step back from adjacent enemies instead of meleeing.

**Status:** ✅ Implemented — added `"offensive_support"` to `is_ranged_role` tuple and added `ally_positions` calculation for Bard kiting in `_decide_aggressive_stance_action()`.

---

### S1-B: Add Target Prioritization to Hold Stance

**Problem:** `_decide_hold_action()` iterates enemies in arbitrary order and attacks the first adjacent one found. Follow and Aggressive use `_pick_best_target()` which scores targets by HP, threat, and distance. Hold should use the same scoring — standing still doesn't mean fighting stupidly.

**Fix:** Replace the naive iteration with `_pick_best_target()` for both melee and ranged target selection.

**File:** `server/app/core/ai_stances.py`

**Current Hold logic (melee):**
```python
# Check for adjacent enemies → melee
for enemy in enemies:
    target_pos = Position(x=enemy.position.x, y=enemy.position.y)
    if is_adjacent(ai.position, target_pos):
        return PlayerAction(
            player_id=ai_id, action_type=ActionType.ATTACK,
            target_x=enemy.position.x, target_y=enemy.position.y,
        )
```

**New Hold logic (melee):**
```python
# Check for adjacent enemies → melee (use _pick_best_target for smart selection)
adjacent_enemies = [
    e for e in enemies
    if is_adjacent(ai.position, Position(x=e.position.x, y=e.position.y))
]
if adjacent_enemies:
    target = _pick_best_target(ai, adjacent_enemies, all_units)
    return PlayerAction(
        player_id=ai_id, action_type=ActionType.ATTACK,
        target_x=target.position.x, target_y=target.position.y,
    )
```

**Same for ranged:** filter enemies to those in range + LOS, then use `_pick_best_target` on that filtered list instead of taking the first match.

**New Hold logic (ranged):**
```python
# Check for ranged targets (with smart target selection)
ranged_cd = ai.cooldowns.get("ranged_attack", 0)
if ranged_cd == 0:
    ranged_enemies = [
        e for e in enemies
        if is_in_range(ai.position, Position(x=e.position.x, y=e.position.y), ranged_range)
        and has_line_of_sight(ai.position.x, ai.position.y, e.position.x, e.position.y, obstacles)
    ]
    if ranged_enemies:
        target = _pick_best_target(ai, ranged_enemies, all_units)
        return PlayerAction(
            player_id=ai_id, action_type=ActionType.RANGED_ATTACK,
            target_x=target.position.x, target_y=target.position.y,
        )
```

**Test:** Run existing tests. Manual test: put a tank on Hold adjacent to 2 enemies (one low HP, one full HP) — verify it attacks the low HP target rather than a random one.

**Status:** ✅ Implemented — replaced naive `for enemy in enemies` iteration with `_pick_best_target()` for both melee (adjacent enemies) and ranged (in-range + LOS enemies) target selection in `_decide_hold_action()`.

---

## Phase S2 — Role-Aware Defensive Stance ✅ COMPLETE

The biggest gap. Defensive is the stance players would naturally put squishy classes on (Mage, Confessor, Ranger), yet it's the stance that strips all class intelligence. This phase makes Defensive respect class roles while maintaining its core identity: **stay close to the owner, fight conservatively.**

**Completed:** 2026-03-13 · 3747 tests passing (0 regressions)

### S2-A: Accept `match_state` Parameter

**Problem:** `_decide_defensive_action()` doesn't accept `match_state`, so totem awareness is impossible.

**Fix:** Add `match_state=None` parameter to the function signature and pass it from `_decide_stance_action()`.

**Files:** `server/app/core/ai_stances.py`

**Status:** ✅ Implemented — added `match_state=None` to `_decide_defensive_action()` signature and updated dispatch call in `_decide_stance_action()` to pass `match_state=match_state`.

---

### S2-B: Add Ranged Kiting to Defensive

**Problem:** Ranged classes on Defensive walk into melee when engaging enemies within 2 tiles. A Plague Doctor (85 HP, 3 armor) on Defensive walks up and punches enemies.

**Fix:** After determining an enemy is within engagement range, check if the unit is a ranged role. If so, and if the enemy is too close (same kite thresholds as Follow: controller ≤ 3, totemic_support ≤ 1, others ≤ 2), attempt to step back — but with a constraint: the kite tile must stay within 2 tiles of the owner (Defensive's core tether).

**Logic:**
```
if is_ranged_role and dist_to_target <= kite_threshold:
    retreat_tile = _find_retreat_tile(...)
    if retreat_tile and _chebyshev(retreat_tile, owner_pos) <= 2:
        return MOVE to retreat_tile
    # Can't kite without breaking tether — fall through to ranged/melee
```

This preserves the Defensive identity (never leave the owner's side) while preventing squishy ranged classes from suiciding into melee.

**Status:** ✅ Implemented — added kite threshold logic (controller ≤ 3, totemic_support ≤ 1, others ≤ 2), `_find_retreat_tile` with Bard ally-proximity kiting, and totem-biased kiting scan. All kite moves are tethered to owner (≤ 2 tiles). Updated test `test_ranger_no_kiting_defensive_stance` → `test_ranger_kites_defensive_stance` to reflect new correct behavior.

---

### S2-C: Expand Defensive Engagement Range for Ranged Classes

**Problem:** Defensive only engages enemies within 2 tiles of the AI unit. A Ranger on Defensive with a 5-tile ranged attack range ignores enemies at 4 tiles away and stands idle. The player put them on Defensive to stay safe, not to stop shooting.

**Fix:** For ranged roles, expand the engagement range to include enemies within `ranged_range` of the AI unit (not just 2 tiles), as long as:
1. The AI doesn't need to move beyond 2 tiles from the owner to attack
2. The attack is a ranged attack (not closing to melee)

**Logic:**
```python
if is_ranged_role:
    # Ranged classes engage at their full range from current position
    engageable_enemies = [
        e for e in enemies
        if is_in_range(ai.position, e_pos, ranged_range)
        and has_line_of_sight(...)
    ]
else:
    # Melee classes: only engage within 2 tiles (existing behavior)
    engageable_enemies = [
        e for e in enemies
        if _chebyshev(ai_pos, (e.position.x, e.position.y)) <= 2
    ]
```

Melee classes retain the existing 2-tile engagement limit unchanged.

**Status:** ✅ Implemented — ranged roles now use `engageable_enemies` filtered by `ranged_range` instead of hardcoded 2-tile limit. Melee classes unchanged.

---

### S2-D: Add Support Positioning to Defensive

**Problem:** Confessor, Bard, and Shaman on Defensive charge toward enemies instead of positioning near allies. A Confessor on Defensive should hover near the owner to heal them, not walk toward the nearest goblin.

**Fix:** When a support role on Defensive has no immediately engageable enemies, and is within 2 tiles of the owner, use the appropriate support move preference function (`_support_move_preference`, `_offensive_support_move_preference`, `_totemic_support_move_preference`) to decide positioning — but constrain movement to stay within 2 tiles of the owner.

For support roles, when enemies ARE present, still use `_pick_best_target` for combat but don't rush toward them — let the enemy come to the support. Support on Defensive should be reactive, not proactive.

**Status:** ✅ Implemented — added `is_support` check with role-specific move preference routing (`_support_move_preference`, `_offensive_support_move_preference`, `_totemic_support_move_preference`). Support classes position near allies instead of charging enemies, tethered within 2 tiles of owner.

---

### S2-E: Add Totem-Biased Movement to Defensive

**Problem:** Defensive never calls `_totem_biased_step` or `_find_nearest_healing_totem`. Units on Defensive near a Shaman's totem don't benefit from the soft drift toward the heal zone.

**Fix:** When Defensive units do move (toward owner or toward engagement), apply `_totem_biased_step` — same as Follow/Aggressive. Requires `match_state` from S2-A.

**Status:** ✅ Implemented — `_totem_biased_step` applied to three movement paths: (1) returning to owner, (2) engagement movement, (3) totem-biased kiting scan. Also added controller hold-position logic (wait when ranged on CD + enemies within 4 tiles). Re-checks tether constraint after totem bias to prevent drift beyond 2 tiles.

---

### S2 Testing

- Existing AI test suite must pass (no regressions).
- Manual tests:
  - Mage on Defensive: should ranged-attack enemies at range 5 without moving toward them. If enemy gets adjacent, should attempt to kite back (but stay within 2 of owner).
  - Confessor on Defensive: should position near owner/allies, heal when appropriate, only melee if enemy is adjacent.
  - Crusader on Defensive: behavior should be unchanged from current (melee within 2 tiles, stay near owner).
  - Ranger on Defensive: should shoot enemies at range 5, kite if they close in.
  - Plague Doctor on Defensive: should kite at dist ≤ 3 (within tether), use ranged and skills from safe distance.

---

## Phase S3 — Role-Aware Aggressive Stance (Support Positioning) ✅ COMPLETE

**Completed:** 2026-03-13 · 3747 tests passing (0 regressions)

### S3-A: Add Support Positioning to Aggressive

**Problem:** Confessor, Bard, and Shaman on Aggressive charge straight at enemies and die. A Confessor on Aggressive should still stay near allies — "aggressive" means "pursue fights freely," not "become a melee warrior."

**Fix:** Mirror the Follow stance's support positioning logic into Aggressive. When a support role on Aggressive has enemies visible, use the appropriate move preference function to determine movement target instead of charging toward the enemy.

Add `is_support` check (same roles as Follow: `support`, `offensive_support`, `controller`, `totemic_support`) and use the corresponding `_*_move_preference` function for the movement target. Also exclude support roles from the "Close → rush to melee" block so they don't charge at enemies within 3 tiles.

**Changes made to `_decide_aggressive_stance_action()` in `server/app/core/ai_stances.py`:**

1. Added `is_support` role detection after `is_ranged_role`:
```python
is_support = role in ("support", "offensive_support", "controller", "totemic_support") if role else False
```

2. Excluded support roles from the melee rush block:
```python
# Close → rush to melee (non-ranged, non-support only)
if not is_ranged_role and not is_support and dist_to_target <= 3:
```

3. Replaced hardcoded enemy-targeting movement with support-aware positioning:
```python
if is_support:
    if role == "totemic_support":
        ally_target = _totemic_support_move_preference(ai, all_units, match_state=match_state)
    elif role == "offensive_support":
        ally_target = _offensive_support_move_preference(ai, all_units)
    else:
        ally_target = _support_move_preference(ai, all_units)
    agg_move_target = ally_target if ally_target else (target.position.x, target.position.y)
else:
    agg_move_target = (target.position.x, target.position.y)
```

The wider 5-tile owner leash on Aggressive still applies — supports on Aggressive will position near allies but roam further from the owner than Follow.

**File:** `server/app/core/ai_stances.py` — `_decide_aggressive_stance_action()`

**Status:** ✅ Implemented — added `is_support` detection, excluded support from melee rush, added role-specific move preference routing (`_support_move_preference`, `_offensive_support_move_preference`, `_totemic_support_move_preference`). Support classes now position near allies instead of charging enemies on Aggressive stance.

---

### S3-B: Add Bard Ally-Proximity Kiting to Aggressive

**Problem:** Follow stance passes `ally_positions` to `_find_retreat_tile` for Bards so kite direction stays near the ally centroid (maintaining Ballad aura coverage). Aggressive doesn't do this — Bards on Aggressive kite in random directions.

**Fix:** In the kiting block of `_decide_aggressive_stance_action()`, add the same `ally_positions` calculation for `offensive_support` that exists in Follow.

**Status:** ✅ Already implemented as part of Phase S1-A — the `ally_positions` calculation for `offensive_support` Bard kiting was added to Aggressive's kiting block when fixing the missing `offensive_support` role in S1-A. No additional changes needed.

---

### S3 Testing

- ✅ All 3747 existing tests pass (0 regressions).
- Manual tests:
  - Confessor on Aggressive: should fight (pursue enemies within 5 tiles of owner) but stay near allies to heal, not charge frontline.
  - Bard on Aggressive: should kite from adjacent enemies AND bias kite direction toward allies.
  - Crusader/Hexblade on Aggressive: behavior unchanged (they're not support roles).

---

## Implementation Order & Dependencies

```
Phase S1 (Quick Fixes)         — No dependencies, can implement immediately
  ├── S1-A: Fix Bard kiting in Aggressive
  └── S1-B: Add _pick_best_target to Hold

Phase S2 (Defensive Overhaul)  — Independent of S1
  ├── S2-A: Accept match_state (required by S2-E)
  ├── S2-B: Ranged kiting (independent)
  ├── S2-C: Expanded ranged engagement (independent)
  ├── S2-D: Support positioning (independent)
  └── S2-E: Totem-biased movement (depends on S2-A)

Phase S3 (Aggressive Support)  — Independent of S1/S2
  ├── S3-A: Support positioning
  └── S3-B: Bard ally-proximity kiting (depends on S1-A being done)
```

All phases modify a single file: `server/app/core/ai_stances.py`. No client changes needed. No new dependencies. No config changes.

---

## Success Criteria

After all phases:
- Every hero class retains its role identity in all 4 stances
- Ranged classes never walk into melee on Defensive
- Support classes always prioritize ally positioning over enemy charging
- Hold stance makes smart target choices
- No regressions in existing Follow stance behavior
- All existing tests pass
