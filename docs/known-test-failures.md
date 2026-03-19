# Known Recurring Test Failures — Bug Log

**Created:** March 18, 2026  
**Purpose:** Track pre-existing test failures observed during Phase 21 implementation.

---

## Bug 1: TestBloodpact.test_low_hp_bonus_inactive_above_threshold

**File:** `server/tests/test_phase16d_unique_items.py` (line 508)  
**Status:** FIXED (March 18, 2026)  
**Severity:** Low — test reliability issue, not a gameplay bug  

### Root Cause

The Bloodpact HP threshold logic in `combat.py` was **correct** — the bonus properly only applies below 30% HP. The test was flaky because neither `calculate_damage()` call passed a seeded RNG. With the default 5% crit chance (`PlayerState.crit_chance = 0.05`), one call could randomly crit (damage × 1.5 = 45) while the other didn't (30), breaking the equality assertion.

### Fix

Added `rng=_FixedRng(0.99)` to both `calculate_damage()` calls in `test_low_hp_bonus_active` and `test_low_hp_bonus_inactive_above_threshold`, matching the pattern used by all other combat tests in the file. This ensures no crit fires, making the tests deterministic.

---

## Bug 2: Non-deterministic Crit Test (Flaky)

**File:** `server/tests/test_turn_resolver.py` — `TestCombat.test_adjacent_attack_deals_damage`  
**Status:** FIXED (March 18, 2026)  
**Severity:** Low — test reliability issue, not a gameplay bug  

### Root Cause

Same underlying cause as Bug 1. The `make_player()` helper in `test_turn_resolver.py` did not set `crit_chance`, so players inherited the default 5% crit chance. Since `resolve_turn()` calls `calculate_damage()` without a seeded RNG, random crits could change damage from the expected 15 to 22 (15 × 1.5), breaking exact assertions like `assert damage_dealt == 15`.

### Fix

Added `crit_chance=0.0` to the `make_player()` helper in `test_turn_resolver.py`. This eliminates random crit interference for all turn resolver combat tests without changing the game logic.
