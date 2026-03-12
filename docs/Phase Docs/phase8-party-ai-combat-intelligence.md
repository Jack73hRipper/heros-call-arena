# Phase 8 — Party AI Combat Intelligence

## Overview

Hero allies in the party currently fight like mindless zombies. They only melee, ranged attack, or wait — never using potions, skills, or any class-aware tactics. A Confessor with a Heal spell stands next to a dying ally and basic attacks an enemy instead of healing. A Crusader with War Cry and Double Strike never uses either. A Ranger with 6 potions dies without drinking one.

**Goal:** Make AI-controlled party members feel competent. They should use potions when hurt, use their class skills intelligently, and fight according to their role. The system must be extensible for future classes (same role archetypes: Tank, Support, Ranged DPS, Hybrid DPS, Scout).

---

## Current State (Diagnosed)

### What AI CAN Do
- Move toward enemies (A* pathfinding, door-aware)
- Basic melee attack (adjacent enemies)
- Basic ranged attack (cooldown-aware, LOS-aware)
- Follow/Aggressive/Defensive/Hold stances (movement behavior)
- Open doors (INTERACT action)
- Target selection (weighted: low HP, threatening, distance)
- Ally reinforcement (path toward allies in combat)
- Enemy memory (pursue last-known positions)

### What AI CANNOT Do
- **Never drinks potions** — `USE_ITEM` action exists in turn resolver (Phase 0) but AI never generates it
- **Never uses skills** — `SKILL` action exists in turn resolver (Phase 1.9) but AI never generates it
- **No class-aware behavior** — Confessor fights identically to Crusader
- **No self-preservation** — AI fights to the death with full potion inventory
- **No healing allies** — Confessor Heal skill (range 1, ally_or_self) is never used by AI
- **No buff management** — Crusader War Cry (2x melee, 2 turns) is never activated
- **No skill-over-basic preference** — Double Strike (120% damage) is always worse to skip

### Relevant Files
| File | Role |
|------|------|
| `server/app/core/ai_behavior.py` | AI decision engine (1930 lines) — all changes go here |
| `server/app/core/turn_resolver.py` | Resolves actions per phase — USE_ITEM (Phase 0), SKILL (Phase 1.9) |
| `server/app/core/skills.py` | Skill config, validation (`can_use_skill`), effect handlers |
| `server/app/core/combat.py` | Damage calc, adjacency, range, LOS checks |
| `server/app/models/actions.py` | `ActionType.USE_ITEM`, `ActionType.SKILL`, `PlayerAction` model |
| `server/app/models/player.py` | `PlayerState` — inventory, cooldowns, active_buffs, class_id, hp/max_hp |
| `server/configs/skills_config.json` | 5 skills, class_skills mapping |
| `server/configs/items_config.json` | health_potion (40 HP), greater_health_potion (75 HP) |
| `server/configs/classes_config.json` | 5 classes with base stats |
| `server/configs/combat_config.json` | Global combat tuning values |

### Current Skills Reference
| Skill | Classes | Targeting | Range | Cooldown | Effect |
|-------|---------|-----------|-------|----------|--------|
| Heal | Confessor | ally_or_self | 3 | 4 turns | Restore 30 HP |
| Double Strike | Crusader, Hexblade | enemy_adjacent | 1 | 3 turns | 2 hits × 60% damage |
| Power Shot | Ranger, Inquisitor | enemy_ranged | class ranged_range | 5 turns | 1.8× ranged damage |
| War Cry | Crusader | self | 0 | 5 turns | Buff: 2× melee damage for 2 turns |
| Shadow Step | Hexblade, Inquisitor | empty_tile | 3 | 4 turns | Teleport to tile (LOS required) |

### Current Class Stats Reference
| Class | Role | HP | Melee | Ranged | Armor | Vision | Range |
|-------|------|-----|-------|--------|-------|--------|-------|
| Crusader | Tank | 150 | 20 | 0 | 8 | 5 | 1 |
| Confessor | Support | 100 | 8 | 0 | 3 | 6 | 1 |
| Inquisitor | Scout | 80 | 10 | 8 | 4 | 9 | 5 |
| Ranger | Ranged DPS | 80 | 8 | 18 | 2 | 7 | 6 |
| Hexblade | Hybrid DPS | 110 | 15 | 12 | 5 | 6 | 4 |

---

## Phased Implementation Plan

### Phase 8A — AI Potion Usage
**Priority: CRITICAL — Heroes die with full potion inventories**

**Files:** `server/app/core/ai_behavior.py`, `server/tests/test_ai_potions.py`

#### 8A-1: `_should_use_potion()` Helper Function

Create a standalone helper that checks whether an AI unit should drink a potion this tick. This runs at the TOP of stance decision logic — survival takes priority over everything.

```python
def _should_use_potion(
    ai: PlayerState,
    hp_threshold: float = 0.40,
) -> PlayerAction | None:
    """Check if AI should use a health potion.

    Returns USE_ITEM action if:
    1. AI is alive
    2. HP is at or below threshold (% of max_hp)
    3. AI has a consumable with heal effect in inventory
    4. AI is not already at full HP

    Prefers greater_health_potion over health_potion when both available
    (uses highest magnitude first).

    Args:
        ai: The AI unit's PlayerState.
        hp_threshold: HP fraction below which AI will drink (default 0.40 = 40%).

    Returns:
        PlayerAction(USE_ITEM) with target_x = inventory index, or None.
    """
```

**Decision logic:**
- Check `ai.hp / ai.max_hp <= hp_threshold`
- Scan `ai.inventory` for items where `item_type == "consumable"` and `consumable_effect.type == "heal"`
- Sort by `magnitude` descending (prefer Greater Health Potion 75 HP over Health Potion 40 HP)
- Return `PlayerAction(player_id=ai.player_id, action_type=ActionType.USE_ITEM, target_x=inventory_index)`
- If no potions found or HP is full, return `None`

**Threshold per stance (tuning knob):**
| Stance | Default Threshold | Rationale |
|--------|-------------------|-----------|
| Follow | 40% | Balanced — drink when moderately hurt |
| Aggressive | 50% | Reckless — push damage, drink only when critical |
| Defensive | 50% | Cautious — drink early to stay topped off |
| Hold | 40% | Same as follow — stationary but not suicidal |

These thresholds should be constants at the top of `ai_behavior.py` so they're easy to tune later.

#### 8A-2: Integration into Stance Functions

Insert the potion check as the **first priority** in `_decide_stance_action()` — before any stance-specific logic fires.

```python
def _decide_stance_action(ai, all_units, ...):
    stance = ai.ai_stance or "follow"
    
    # --- Potion check (highest priority) ---
    threshold = _POTION_THRESHOLDS.get(stance, 0.40)
    potion_action = _should_use_potion(ai, hp_threshold=threshold)
    if potion_action:
        return potion_action
    
    # --- Existing stance dispatch ---
    if stance == "hold":
        ...
```

**Why at the top of `_decide_stance_action` and not inside each individual stance:**
- Single integration point — no code duplication across 4 stance functions
- Potions resolve in Phase 0 of turn_resolver (before movement, combat, skills), so there's no conflict with other actions
- Easy to extend when new stances are added

**Important constraint:** The turn resolver only processes ONE action per unit per tick. If the AI returns `USE_ITEM`, it will not also move or attack that tick. This is correct — drinking a potion costs your turn, which creates a meaningful tactical trade-off.

#### 8A-3: Tests

**New file:** `server/tests/test_ai_potions.py`

| Test | Description |
|------|-------------|
| `test_ai_drinks_potion_when_low_hp` | AI at 30% HP with health potion → returns USE_ITEM |
| `test_ai_no_potion_when_healthy` | AI at 80% HP with potions → returns normal combat action |
| `test_ai_no_potion_when_inventory_empty` | AI at 20% HP with empty inventory → returns normal action |
| `test_ai_prefers_greater_potion` | AI has both potion types → uses greater_health_potion first |
| `test_ai_potion_threshold_per_stance` | Aggressive stance doesn't drink at 30% (threshold 25%) |
| `test_ai_potion_full_hp` | AI at max_hp with low threshold edge case → doesn't drink |
| `test_ai_potion_only_heal_consumables` | Portal scroll in inventory doesn't trigger potion logic |
| `test_ai_potion_action_format` | Returned USE_ITEM has correct target_x (inventory index) |
| `test_ai_potion_skips_non_hero` | Enemy AI units never drink potions (hero_id check) |

**Estimated scope:** ~60 lines helper + integration, ~150 lines tests

---

### Phase 8B — AI Skill Decision Framework ✅ COMPLETED
**Priority: HIGH — Skills are the entire class identity**
**Status: IMPLEMENTED — 2025-02-15**

**Files Modified:**
- `server/app/core/ai_behavior.py` — Added `_CLASS_ROLE_MAP`, `_get_role_for_class()`, `_try_skill()`, `_decide_skill_usage()`, 5 stub role handlers, and integration into `_decide_stance_action()`
- `server/app/core/skills.py` — Read-only (imported `can_use_skill`)

**Files Created:**
- `server/tests/test_ai_skills.py` — 19 tests covering role mapping, `_try_skill()` validation, and `_decide_skill_usage()` dispatch

**Implementation Summary:**
- **8B-1:** `_decide_skill_usage()` dispatches to role-specific handlers based on `class_id → role` mapping
- **8B-2:** `_CLASS_ROLE_MAP` maps all 5 classes to roles (tank, support, scout, ranged_dps, hybrid_dps)
- **8B-3:** `_try_skill()` wraps `can_use_skill()` and returns a `PlayerAction(SKILL)` or `None`
- **8B-4:** 19 tests all passing — role mapping (4), `_try_skill` (6), dispatch (9)
- **Integration:** Skill decision runs after potion check, before stance dispatch in `_decide_stance_action()`. Pre-computes FOV + visible enemies once and passes them to the skill framework.
- **Stub handlers:** All 5 role handlers (`_support_skill_logic`, `_tank_skill_logic`, `_ranged_dps_skill_logic`, `_hybrid_dps_skill_logic`, `_scout_skill_logic`) return `None` — actual logic deferred to 8C/8D/8E.
- **No regressions:** All 28 Phase 8A potion tests still pass.

**Test Results:** `19 passed in 0.21s` (8B) + `28 passed in 0.22s` (8A regression check)

**Files:** `server/app/core/ai_behavior.py`, `server/app/core/skills.py` (read-only), `server/tests/test_ai_skills.py`

#### 8B-1: `_decide_skill_usage()` Framework Function

A role-based skill decision framework. This function is called after the potion check but before basic attack logic. It uses class_id to dispatch to role-specific skill logic.

```python
def _decide_skill_usage(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Evaluate whether the AI should use a skill instead of basic attack.

    Dispatches to role-specific handlers based on class_id.
    Returns SKILL action or None (fall through to basic attack logic).

    Future-proof: New classes map to existing role handlers.
    """
    class_id = ai.class_id
    if not class_id:
        return None

    role = _get_role_for_class(class_id)

    if role == "support":
        return _support_skill_logic(ai, enemies, all_units, grid_width, grid_height, obstacles)
    elif role == "tank":
        return _tank_skill_logic(ai, enemies, all_units, obstacles)
    elif role == "ranged_dps":
        return _ranged_dps_skill_logic(ai, enemies, all_units, obstacles)
    elif role == "hybrid_dps":
        return _hybrid_dps_skill_logic(ai, enemies, all_units, grid_width, grid_height, obstacles)
    elif role == "scout":
        return _scout_skill_logic(ai, enemies, all_units, grid_width, grid_height, obstacles)
    
    return None
```

#### 8B-2: Role Registry (Future-Class-Friendly)

Instead of hardcoding class names in AI logic, map class_id → role, then write AI logic per role. When new classes are added, they just need a role mapping entry.

```python
# Role mapping — add new classes here, AI behavior follows automatically
_CLASS_ROLE_MAP: dict[str, str] = {
    "crusader": "tank",
    "confessor": "support",
    "inquisitor": "scout",
    "ranger": "ranged_dps",
    "hexblade": "hybrid_dps",
}

def _get_role_for_class(class_id: str) -> str | None:
    """Get the AI behavior role for a class. None = no special skill logic."""
    return _CLASS_ROLE_MAP.get(class_id)
```

**Why role-based, not class-based:**
- Adding a "Paladin" (Tank) → map to "tank" → gets War Cry + Double Strike behavior for free
- Adding a "Druid" (Support) → map to "support" → gets heal-priority behavior
- Adding a "Warlock" (Hybrid DPS) → map to "hybrid_dps" → gets Shadow Step + melee combo behavior
- Role handlers are reusable; class-specific overrides can be added later if needed

#### 8B-3: Core Validation Helper

Wrap the existing `can_use_skill()` from `skills.py` into a convenience helper that also checks targeting constraints before returning an action:

```python
def _try_skill(
    ai: PlayerState,
    skill_id: str,
    target_x: int | None = None,
    target_y: int | None = None,
) -> PlayerAction | None:
    """Attempt to build a SKILL action if the skill is usable.

    Returns PlayerAction(SKILL) if can_use_skill passes, else None.
    """
    can_use, _reason = can_use_skill(ai, skill_id)
    if not can_use:
        return None
    return PlayerAction(
        player_id=ai.player_id,
        action_type=ActionType.SKILL,
        skill_id=skill_id,
        target_x=target_x,
        target_y=target_y,
    )
```

#### 8B-4: Tests

**New file:** `server/tests/test_ai_skills.py` (framework tests only — role-specific tests in 8C/8D/8E)

| Test | Description |
|------|-------------|
| `test_role_mapping_all_classes` | All 5 classes map to a valid role |
| `test_role_mapping_unknown_class` | Unknown class_id → returns None |
| `test_decide_skill_dispatches_to_role` | Confessor dispatches to support, Crusader to tank, etc. |
| `test_try_skill_on_cooldown` | Skill on cooldown → returns None |
| `test_try_skill_wrong_class` | Wrong class for skill → returns None |
| `test_try_skill_success` | Valid skill + off cooldown → returns SKILL action |
| `test_no_skills_for_null_class` | class_id=None (legacy) → returns None, no crash |

**Estimated scope:** ~80 lines framework + helpers, ~100 lines tests

---

### Phase 8C — Support Role AI (Confessor: Heal) ✅ COMPLETED
**Priority: HIGH — Healing is the most impactful missing AI behavior**
**Status: IMPLEMENTED — 2025-02-15**

**Files Modified:**
- `server/app/core/ai_behavior.py` — Replaced `_support_skill_logic()` stub with full heal decision logic, added `_support_move_preference()` helper, added `_HEAL_SELF_THRESHOLD` / `_HEAL_ALLY_THRESHOLD` constants, integrated support positioning modifier into `_decide_follow_action()`
- `server/configs/skills_config.json` — Increased Heal range from 1 → 3 (Chebyshev) to make healing practical at non-adjacent distances
- `server/app/core/skills.py` — Updated docstring for `resolve_heal()` to reflect new range 3
- `server/tests/test_skills.py` — Updated `test_heal_skill_definition` assertion: range 1 → 3
- `server/tests/test_skills_combat.py` — Updated `test_heal_out_of_range` to use distance 4 (beyond new range 3)

**Files Created:**
- `server/tests/test_ai_support.py` — 28 tests covering heal decision logic, positioning, dispatch integration, and guard tests

**Implementation Summary:**
- **8C-1:** `_support_skill_logic()` — Full heal decision engine:
  - Priority 1: Self-heal if below 50% HP (self-preservation)
  - Priority 2: Heal most injured ally within range 3 if below 60% HP
  - Priority 3: Return `None` → fall through to basic attack logic
  - Reads heal range from `skills_config.json` dynamically (future-proof)
  - Uses `_try_skill()` for cooldown/class validation
  - Sorts candidates by HP% ascending (heals most hurt first)
- **8C-2:** `_support_move_preference()` — Positioning helper:
  - Support units prefer moving toward injured allies over enemies
  - Falls back to nearest ally (stay grouped) when no one is hurt
  - Integrated into `_decide_follow_action()`: support-role units move toward allies instead of charging enemies when skill check returned None
  - Non-support units completely unaffected (guard check on class role)
- **Heal Range Increase:** Range 1 → 3 in `skills_config.json`. Applied to both AI and player usage. The old range was too short for the Confessor to be effective — they had to be adjacent (melee range) to heal, which defeated the purpose of a backline support.
- **No regressions:** All 1165 tests pass (28 new + 1137 existing including 28 Phase 8A + 19 Phase 8B).

**Test Results:** `28 passed in 0.23s` (8C) + `1165 passed in 5.01s` (full suite)

**Files:** `server/app/core/ai_behavior.py`, `server/tests/test_ai_support.py`

#### 8C-1: `_support_skill_logic()` — Heal Decision

The Support role's primary job is keeping allies alive. Heal is the only support skill currently, but this handler should be structured for future support skills (group heal, damage mitigation buff, etc.).

```python
def _support_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Support role AI: prioritize healing injured allies over attacking.

    Priority:
    1. Heal self if below 50% HP (self-preservation)
    2. Heal adjacent ally with lowest HP% if they're below 60% HP
    3. Return None → fall through to basic attack logic
    """
```

**Heal target selection:**
1. **Self-heal check:** If `ai.hp / ai.max_hp < 0.50` and heal off cooldown → heal self (`target_x=ai.position.x, target_y=ai.position.y`)
2. **Ally scan:** Find all alive same-team allies within range 1 (adjacent, 8-direction Chebyshev)
3. **Filter:** Only allies below 60% max HP
4. **Sort:** By HP percentage ascending (heal the most hurt ally first)
5. **Heal ally:** Return SKILL action with `target_x/y` = ally position
6. **No one needs healing:** Return `None` → the stance handler continues with normal attack/move logic

**Healing vs. Combat priority:**
The support AI should heal instead of attacking UNLESS no one needs healing. This means:
- Confessor sees an adjacent enemy AND an adjacent ally at 40% HP → **heals the ally** (correct choice)
- Confessor sees an adjacent enemy AND all allies above 60% → **attacks the enemy** (nothing to heal)
- This is handled by calling `_decide_skill_usage()` before basic attack logic in the stance function

#### 8C-2: Confessor Positioning Behavior (Support Stance Modifier)

Confessors should stay BEHIND the frontline, not rush into melee. This is a modification to how the existing stance functions work for support role units. When the support AI has no skill to use and falls through to basic attack/move logic, we add a preference:

- **In combat (enemies visible):** Move toward injured allies rather than toward enemies. If no allies are hurt, move toward the nearest ally (stay grouped, don't solo charge)
- **If already adjacent to an enemy with no one to heal:** Attack (don't just stand there)
- This is a soft modifier — not a whole new stance. It adjusts the move target preference within the existing follow/aggressive/defensive behavior.

**Implementation:** Add a `_support_move_preference()` helper that returns a preferred move target position (injured ally > nearest ally > enemy). Call it from within the existing stance combat flow for support-role units when `_decide_skill_usage()` returns `None` and the unit needs to move.

#### 8C-3: Tests

**New file:** `server/tests/test_ai_support.py`

| Test | Description |
|------|-------------|
| `test_confessor_heals_low_hp_ally` | Adjacent ally at 40% HP → heals ally |
| `test_confessor_heals_self_when_low` | Self at 45% HP, no adjacent allies → heals self |
| `test_confessor_heals_lowest_ally` | Two adjacent allies at 40% and 60% → heals the 40% one |
| `test_confessor_attacks_when_all_healthy` | Adjacent enemy, all allies above 60% → attacks |
| `test_confessor_heal_on_cooldown_attacks` | Ally at 30% but Heal on cooldown → attacks instead |
| `test_confessor_heal_range_check` | Ally at 30% HP but 3 tiles away → doesn't heal (range 1) |
| `test_confessor_prioritizes_heal_over_attack` | Adjacent enemy AND adjacent hurt ally → heals |
| `test_confessor_heal_doesnt_overheal` | Ally missing 10 HP → still heals (game caps at max_hp) |
| `test_confessor_no_heal_at_full_hp` | All allies at 100% → attacks/moves normally |
| `test_support_role_positioning` | Confessor prefers moving toward injured ally over enemy |

**Estimated scope:** ~100 lines skill logic + positioning, ~200 lines tests

---

### Phase 8D — Tank Role AI (Crusader: War Cry + Double Strike) ✅ COMPLETED
**Priority: HIGH — Tanks should feel powerful and tactical**
**Status: IMPLEMENTED — 2025-02-15**

**Files Modified:**
- `server/app/core/ai_behavior.py` — Replaced `_tank_skill_logic()` stub with full War Cry + Double Strike decision logic
- `server/tests/test_ai_skills.py` — Updated `test_dispatch_returns_none_when_handler_returns_none` to account for live tank handler (skills on CD + buff active to trigger None return)

**Files Created:**
- `server/tests/test_ai_tank.py` — 23 tests covering War Cry usage, Double Strike usage, combo flow, dispatch integration, and guard tests

**Implementation Summary:**
- **8D-1:** `_tank_skill_logic()` — Full tank skill decision engine:
  - Priority 1: War Cry if enemies visible AND off cooldown AND no `melee_damage_multiplier` buff active (self-buff before engagement)
  - Priority 2: Double Strike if adjacent to enemy AND off cooldown (120% > 100% basic melee — strictly superior)
  - Priority 3: Return `None` → fall through to basic melee/move logic
  - Uses `_try_skill()` for cooldown/class validation
  - Uses `_pick_best_target()` among adjacent enemies for Double Strike target selection (focuses low-HP targets)
  - Combo flow is emergent: War Cry → Double Strike next turn (2 × 60% × 2.0 = 240% damage!) → basic attacks while on CD → cycle repeats
- **8D-2:** Integration verified: `_decide_skill_usage()` dispatches to `_tank_skill_logic()` for crusader class via role mapping
- **No regressions:** All 1216 tests pass (23 new + 1193 existing including 28 Phase 8A + 19 Phase 8B + 28 Phase 8C).

**Test Results:** `23 passed in 0.26s` (8D) + `1216 passed in 5.18s` (full suite)

**Files:** `server/app/core/ai_behavior.py`, `server/tests/test_ai_tank.py`

**Files:** `server/app/core/ai_behavior.py`, `server/tests/test_ai_tank.py`

#### 8D-1: `_tank_skill_logic()` — War Cry + Double Strike

Tank role AI should use combat skills aggressively to maximize melee output.

```python
def _tank_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Tank role AI: buff before engagement, Double Strike over basic melee.

    Priority:
    1. If enemies visible AND War Cry off CD AND no melee_damage_multiplier buff active:
       → Use War Cry (buff self before engaging)
    2. If adjacent to enemy AND Double Strike off CD:
       → Use Double Strike (120% damage > 100% basic melee)
    3. Return None → fall through to basic melee/move logic
    """
```

**War Cry usage logic:**
- Check `ai.active_buffs` for any buff with `stat == "melee_damage_multiplier"` — if one already active, skip War Cry
- Only use War Cry when enemies are visible (don't waste it before combat)
- War Cry is self-targeting → `target_x/y = None` (or ai's own position)
- After War Cry, next tick the AI will have 2x melee and should prefer Double Strike for devastating 2 × 60% × 2.0 = 240% damage

**Double Strike usage logic:**
- Only use when adjacent to an enemy (targeting = `enemy_adjacent`)
- Always prefer over basic melee when off cooldown (2 × 60% = 120% > 100%)
- Target selection: use `_pick_best_target()` among adjacent enemies
- `target_x/y` = enemy position

**Combo awareness:**
- Ideal AI turn sequence: War Cry → (next tick) Double Strike → basic attack → basic attack → Double Strike ready again
- The AI doesn't need explicit combo sequencing — the priority order naturally produces this:
  1. War Cry fires the first turn enemies are visible (if no buff)
  2. Next turn, buff is active, Double Strike is used if adjacent
  3. Double Strike goes on 3-turn CD, War Cry buff lasts 2 turns
  4. War Cry comes off 5-turn CD later, cycle repeats

#### 8D-2: Tests

**New file:** `server/tests/test_ai_tank.py`

| Test | Description |
|------|-------------|
| `test_crusader_war_cry_before_engagement` | Enemies visible, 3 tiles away, War Cry off CD → uses War Cry |
| `test_crusader_no_war_cry_if_buffed` | Already has melee_damage_multiplier buff → skips War Cry |
| `test_crusader_double_strike_adjacent` | Adjacent to enemy, DS off CD → uses Double Strike |
| `test_crusader_double_strike_over_basic` | Adjacent to enemy, DS off CD → prefers DS over ATTACK |
| `test_crusader_basic_attack_ds_on_cooldown` | Adjacent to enemy, DS on CD → falls through to basic ATTACK |
| `test_crusader_war_cry_not_wasted_no_enemies` | No enemies visible → doesn't War Cry |
| `test_crusader_war_cry_on_cooldown` | War Cry on CD, adjacent enemy → uses Double Strike or ATTACK |
| `test_crusader_combo_sequence` | Multi-turn: War Cry → Double Strike → basic → basic → DS |
| `test_crusader_ds_target_selection` | Two adjacent enemies, one low HP → DS targets low HP one |

**Estimated scope:** ~60 lines skill logic, ~180 lines tests

---

### Phase 8E — Ranged DPS / Scout / Hybrid Role AI
**Priority: MEDIUM — Completes the skill coverage for all 5 classes**

**Files:** `server/app/core/ai_behavior.py`, `server/tests/test_ai_ranged.py`, `server/tests/test_ai_hybrid.py`

#### 8E-1: `_ranged_dps_skill_logic()` — Power Shot (Ranger) ✅ COMPLETED
**Status: IMPLEMENTED — 2026-02-15**

**Files Modified:**
- `server/app/core/ai_behavior.py` — Replaced `_ranged_dps_skill_logic()` stub with full Power Shot decision logic

**Files Created:**
- `server/tests/test_ai_ranged.py` — 17 tests covering Power Shot usage, target selection, LOS/range validation, dispatch integration, and guard tests

**Implementation Summary:**
- **Priority 1:** Power Shot if enemy in ranged range (class `ranged_range`) + LOS + off cooldown → use Power Shot (1.8× damage >> 1.0× basic ranged — strictly superior)
- **Priority 2:** Return `None` → fall through to basic ranged/melee logic
- Uses `_pick_best_target()` for weighted target selection (low-HP, threatening, close)
- Falls back to secondary targets when best target is out of range or blocked by obstacles
- Uses `_try_skill()` for cooldown/class validation before checking range/LOS
- Power Shot range uses class `ranged_range` (Ranger=6, Inquisitor=5) — matches basic ranged attack range
- **No regressions:** All 1233 tests pass (17 new + 1216 existing)

**Test Results:** `17 passed in 0.23s` (8E-1) + `1233 passed in 5.85s` (full suite)

```python
def _ranged_dps_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Ranged DPS role: prefer Power Shot over basic ranged when available.

    Priority:
    1. If enemy in ranged range + LOS + Power Shot off CD:
       → Use Power Shot (1.8x damage >> basic ranged 1.0x)
    2. Return None → fall through to basic ranged/melee logic
    """
```

**Logic:**
- Find the best target using `_pick_best_target()`
- Check range (`is_in_range`) + LOS (`has_line_of_sight`) + Power Shot cooldown
- Power Shot uses class `ranged_range` (matches basic ranged range)
- Always prefer Power Shot over basic RANGED_ATTACK when off cooldown — it's strictly superior
- If Power Shot on CD → return None → existing ranged attack logic fires

#### 8E-2: `_scout_skill_logic()` — Power Shot + Shadow Step (Inquisitor) ✅ COMPLETED
**Status: IMPLEMENTED — 2026-02-15**

**Files Modified:**
- `server/app/core/ai_behavior.py` — Replaced `_scout_skill_logic()` stub with full Power Shot + Shadow Step decision logic. Added `_SHADOW_STEP_ESCAPE_HP_THRESHOLD` (0.30) and `_SHADOW_STEP_OFFENSIVE_MIN_DISTANCE` (4) constants. Added 3 helper functions: `_find_valid_shadow_step_tiles()`, `_find_shadow_step_escape_tile()`, `_find_shadow_step_offensive_tile()`.

**Files Created:**
- `server/tests/test_ai_scout.py` — 37 tests covering escape Shadow Step, Power Shot, offensive Shadow Step, priority chain, tile-finding helpers, dispatch integration, and guard tests.

**Implementation Summary:**
- **Priority 1 — Shadow Step escape:** If HP < 30% AND adjacent to enemy AND Shadow Step off cooldown → teleport to the tile that maximizes distance from the nearest enemy. Escape tile scoring: primary weight on min-enemy-distance (×10), bonus (+5) if tile is still within ranged_range (retreat to shoot). Uses `_find_valid_shadow_step_tiles()` to enumerate valid destinations (within range 3, in bounds, not obstacles/occupied, has LOS).
- **Priority 2 — Power Shot:** If enemy in range + LOS + off cooldown → use Power Shot (1.8× damage). Same logic as ranged DPS: picks best target via `_pick_best_target()`, falls back to secondary targets if best is blocked. Uses class `ranged_range` (Inquisitor = 5).
- **Priority 3 — Shadow Step offense:** If closest enemy > 4 tiles away AND Shadow Step off cooldown → teleport closer but NOT adjacent (Inquisitor prefers ranged distance). `_find_shadow_step_offensive_tile()` filters tiles to keep 2+ Chebyshev distance from target, then minimizes distance. Falls back to adjacent tiles only if no 2+ distance tiles exist.
- **Helper functions:** `_find_valid_shadow_step_tiles()` enumerates all legal Shadow Step destinations (shared by both escape and offensive logic). `_find_shadow_step_escape_tile()` and `_find_shadow_step_offensive_tile()` apply role-specific scoring. These helpers are reusable for the Hexblade hybrid_dps implementation in 8E-3.
- **No regressions:** All 1270 tests pass (37 new + 1233 existing including 28 Phase 8A + 19 Phase 8B + 28 Phase 8C + 23 Phase 8D + 17 Phase 8E-1).

**Test Results:** `37 passed in 0.25s` (8E-2) + `1270 passed in 5.63s` (full suite)

```python
def _scout_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Scout role: Power Shot for offense, Shadow Step for repositioning.

    Priority:
    1. Shadow Step escape: if HP < 30% AND adjacent to enemy AND Shadow Step off CD:
       → Teleport 2-3 tiles away from enemy (defensive escape)
    2. Power Shot: if enemy in range + LOS + off CD:
       → Use Power Shot
    3. Shadow Step offense: if enemy > 4 tiles away AND Shadow Step off CD:
       → Teleport closer (within 2 tiles of target, but not adjacent)
    4. Return None → fall through to basic attack/move
    """
```

**Shadow Step target selection (escape):**
- Find tiles within range 3, with LOS, not occupied, not obstacles
- Score by distance FROM the nearest enemy (maximize distance)
- Prefer tiles still within ranged range of the enemy (retreat to shoot)

**Shadow Step target selection (offensive):**
- Find tiles within range 3 of self, with LOS
- Score by distance TO the target enemy (minimize distance, but stay 2+ tiles away)
- Don't teleport adjacent — Inquisitor prefers ranged distance

#### 8E-3: `_hybrid_dps_skill_logic()` — Double Strike + Shadow Step (Hexblade) ✅ COMPLETED
**Status: IMPLEMENTED — 2026-02-15**

**Files Modified:**
- `server/app/core/ai_behavior.py` — Replaced `_hybrid_dps_skill_logic()` stub with full Double Strike + Shadow Step gap-close decision logic. Added `_SHADOW_STEP_GAPCLOSER_MIN_DISTANCE` (3) constant. Added `_find_shadow_step_gapcloser_tile()` helper function.

**Files Created:**
- `server/tests/test_ai_hybrid.py` — 33 tests covering Double Strike usage, Shadow Step gap-close, priority chain, tile-finding helper, dispatch integration, and guard tests.

**Implementation Summary:**
- **Priority 1 — Double Strike:** If adjacent to enemy AND off cooldown → use Double Strike (2 × 60% = 120% damage — strictly superior to basic melee). Uses `_pick_best_target()` among adjacent enemies for target selection (focuses low-HP targets). Uses `_try_skill()` for cooldown/class validation.
- **Priority 2 — Shadow Step gap-close:** If closest enemy > 3 tiles away AND Shadow Step off cooldown → teleport ADJACENT to enemy (Hexblade wants melee, unlike Inquisitor who prefers range). `_find_shadow_step_gapcloser_tile()` prefers tiles at Chebyshev distance 1 from the target enemy, tiebreaks by minimum distance from AI position. Falls back to closest available tile if no adjacent-to-enemy tiles exist within SS range 3.
- **Priority 3:** Return `None` → fall through to basic attack/move logic.
- **Design distinction from Scout:** Hexblade does NOT escape with Shadow Step. Hexblades commit to melee and rely on their higher HP (110) and armor (5). The Scout (Inquisitor) escapes when low HP; the Hexblade gap-closes to get into melee.
- **Helper function:** `_find_shadow_step_gapcloser_tile()` reuses `_find_valid_shadow_step_tiles()` (shared with Scout) for tile enumeration, then applies Hexblade-specific scoring (adjacent-to-enemy priority, AI-distance tiebreak).
- **No regressions:** All 1303 tests pass (33 new + 1270 existing including 28 Phase 8A + 19 Phase 8B + 28 Phase 8C + 23 Phase 8D + 17 Phase 8E-1 + 37 Phase 8E-2).

**Test Results:** `33 passed in 0.26s` (8E-3) + `1303 passed in 6.09s` (full suite)

```python
def _hybrid_dps_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Hybrid DPS role: gap-close with Shadow Step, finish with Double Strike.

    Priority:
    1. If adjacent to enemy + Double Strike off CD:
       → Double Strike (120% damage)
    2. If enemy > 3 tiles away + Shadow Step off CD:
       → Shadow Step to adjacent tile (gap close for melee)
    3. Return None → fall through to basic attack/move
    """
```

**Shadow Step target selection (offensive gap-close):**
- Find tiles within Shadow Step range 3 of self, with LOS
- Score by adjacency to the target enemy (prefer tiles adjacent to target for immediate melee next turn)
- Hexblade wants to be IN melee, unlike Inquisitor who prefers range

#### 8E-4: Tests

**New file:** `server/tests/test_ai_ranged.py`

| Test | Description |
|------|-------------|
| `test_ranger_power_shot_when_available` | Enemy in range + LOS + PS off CD → uses Power Shot |
| `test_ranger_basic_ranged_when_ps_on_cd` | Enemy in range + PS on CD → basic RANGED_ATTACK |
| `test_ranger_power_shot_requires_los` | Enemy in range but no LOS → doesn't use PS |
| `test_ranger_power_shot_target_selection` | Multiple enemies in range → picks best target |

**New file:** `server/tests/test_ai_hybrid.py`

| Test | Description |
|------|-------------|
| `test_hexblade_double_strike_adjacent` | Adjacent enemy + DS off CD → uses Double Strike |
| `test_hexblade_shadow_step_gap_close` | Enemy 5 tiles away + SS off CD → teleports adjacent |
| `test_hexblade_shadow_step_target_tile` | Teleport target is adjacent to enemy, not occupied |
| `test_hexblade_shadow_step_requires_los` | No LOS to any valid tile → doesn't teleport |
| `test_hexblade_ds_over_basic_melee` | Adjacent + DS off CD → prefers DS over ATTACK |
| `test_inquisitor_escape_shadow_step` | HP < 30% + adjacent enemy + SS off CD → teleports away |
| `test_inquisitor_escape_tile_selection` | Escape tile maximizes distance from enemy |
| `test_inquisitor_power_shot_over_basic` | In range + PS off CD → uses Power Shot |
| `test_inquisitor_offensive_shadow_step` | Enemy far + SS off CD + PS on CD → teleports closer |

**Estimated scope:** ~150 lines skill logic (3 handlers), ~250 lines tests

---

### Phase 8F — Integration & Priority Chain Polish
**Priority: MEDIUM — Ensures everything works together correctly**

**Files:** `server/app/core/ai_behavior.py`, `server/tests/test_ai_integration.py`

#### 8F-1: Complete Priority Chain ✅ COMPLETED
**Status: IMPLEMENTED — 2026-02-15**

**Files Created:**
- `server/tests/test_ai_integration.py` — 30 tests covering the complete priority chain, enemy AI exclusion, all-class validation, legacy/null class guards, multi-hero party scenarios, player-controlled hero exclusion, stance-variation consistency, and role mapping integration.

**Implementation Summary:**
- **Priority chain verified:** The existing `_decide_stance_action()` already implements the correct 3-tier priority chain (Potion → Skill → Stance) from Phases 8A/8B. No code changes needed — the chain was correctly built incrementally across 8A–8E.
- **30 integration tests:** Comprehensive end-to-end tests organized into 8 test classes:
  - `TestPriorityChain` (7 tests): Potion beats skill, skill beats attack, fallthrough to WAIT/MOVE
  - `TestEnemyAIExclusion` (4 tests): Enemy AI never drinks potions or uses skills (hero_id guard)
  - `TestAllClassesValidActions` (5 tests): All 5 classes produce valid actions in combat
  - `TestLegacyNullClass` (3 tests): class_id=None and unknown class_id don't crash
  - `TestMultiHeroPartySkills` (2 tests): Mixed party with different classes using different skills/potions in same tick
  - `TestControlledHeroExclusion` (2 tests): Human players and dead heroes excluded from AI logic
  - `TestPriorityChainAcrossStances` (5 tests): Priority chain works identically for follow/aggressive/defensive/hold
  - `TestRoleMappingIntegration` (2 tests): All 5 classes have roles, roles drive correct skill dispatch
- **No regressions:** All 1333 tests pass (30 new + 1303 existing).

**Test Results:** `30 passed in 0.27s` (8F-1) + `1333 passed in 6.23s` (full suite)

After all phases, the AI decision priority chain in `_decide_stance_action()` should be:

```
1. POTION CHECK     →  HP below threshold? Drink potion (USE_ITEM)
2. SKILL DECISION   →  Role-appropriate skill available? Use it (SKILL)
3. STANCE BEHAVIOR  →  Existing follow/aggressive/defensive/hold logic
   3a. Adjacent enemy    → ATTACK (basic melee)
   3b. Ranged available  → RANGED_ATTACK
   3c. Move toward       → MOVE
   3d. Regroup/patrol    → MOVE toward owner
   3e. Nothing to do     → WAIT
```

**Important:** Steps 1 and 2 happen BEFORE the stance dispatch (`_decide_follow_action`, etc.). The stance functions handle step 3, which only fires if no potion or skill was chosen.

#### 8F-2: Skill Decision Integration Point ✅ COMPLETED
**Status: IMPLEMENTED — 2026-02-15**

**Files Modified:**
- `server/app/core/ai_behavior.py` — Refactored `_decide_stance_action()` to pass pre-computed `visible_tiles` and `pre_enemies` to all 4 stance handlers. Updated `_decide_follow_action()`, `_decide_aggressive_stance_action()`, `_decide_defensive_action()`, and `_decide_hold_action()` to accept optional `precomputed_visible_tiles` and `precomputed_enemies` parameters. When provided, stance functions skip their own `compute_fov()` + enemy scan. When called directly (e.g., from tests), they fall back to self-computing as before.
- `server/tests/test_ai_integration.py` — Added 10 new tests in `TestPrecomputedFOVIntegration` class covering FOV-once verification for all 4 stances, consistency between pre-computed and self-computed paths, fallback behavior, team_fov integration, and empty-enemy edge case.

**Implementation Summary:**
- **Option A chosen** (pre-compute in `_decide_stance_action()`): FOV and visible enemies are computed once in `_decide_stance_action()`, then forwarded as `precomputed_visible_tiles` and `precomputed_enemies` keyword arguments to the dispatched stance handler.
- **Backward compatible:** All stance functions accept the new parameters as optional kwargs with `None` defaults. When called directly (without pre-computed data), they compute their own FOV — no existing call sites break.
- **Performance:** Eliminates 1 redundant `compute_fov()` call per AI hero per tick. For a 4-hero party, this saves 4 shadowcasting computations per turn (the most CPU-intensive operation in the AI decision pipeline).
- **10 new tests** organized in `TestPrecomputedFOVIntegration`:
  - `test_fov_computed_once_follow_stance` — Follow: compute_fov called exactly once
  - `test_fov_computed_once_aggressive_stance` — Aggressive: compute_fov called exactly once
  - `test_fov_computed_once_defensive_stance` — Defensive: compute_fov called exactly once
  - `test_fov_computed_once_hold_stance` — Hold: compute_fov called exactly once
  - `test_precomputed_enemies_match_self_computed` — Pre-computed path produces same action as self-computed
  - `test_stance_function_fallback_without_precomputed` — Direct call without pre-computed data still works
  - `test_precomputed_data_with_team_fov` — team_fov properly merged into pre-computed visible_tiles
  - `test_no_enemies_precomputed_empty_list` — Empty enemy list forwarded correctly
  - `test_aggressive_stance_consistent_with_precomputed` — Aggressive: integrated vs direct consistency
  - `test_defensive_stance_consistent_with_precomputed` — Defensive: integrated vs direct consistency
- **No regressions:** All 1343 tests pass (10 new + 1333 existing).

**Test Results:** `40 passed in 0.25s` (8F integration) + `1343 passed in 5.28s` (full suite)

The skill decision needs contextual information that the stance functions compute (visible enemies, FOV, etc.). Two approaches:

**Option A — Pre-compute in `_decide_stance_action()`:**
Compute visible enemies once, pass to `_decide_skill_usage()`, then pass to stance function. This avoids redundant FOV computation.

```python
def _decide_stance_action(ai, all_units, grid_width, grid_height, obstacles, team_fov, ...):
    # 1. Potion check
    potion_action = _should_use_potion(ai, threshold)
    if potion_action:
        return potion_action
    
    # 2. Pre-compute shared context
    own_fov = compute_fov(...)
    visible_tiles = (own_fov | team_fov) if team_fov else own_fov
    enemies = [find visible enemies...]
    
    # 3. Skill decision (uses pre-computed enemies)
    skill_action = _decide_skill_usage(ai, enemies, all_units, grid_width, grid_height, obstacles)
    if skill_action:
        return skill_action
    
    # 4. Stance behavior (pass pre-computed enemies to avoid re-computing FOV)
    ...
```

**Option B — Compute inside each handler:**
Simpler but wastes CPU on redundant FOV. Not recommended for 4+ party members.

**Recommendation:** Option A. Pre-compute FOV and enemies once, pass them through. This requires a minor refactor of stance functions to accept a pre-computed enemy list instead of computing their own FOV, but it's worth the performance gain and cleaner architecture.

#### 8F-3: Enemy AI Exclusion Guard

All new AI intelligence is for **hero allies only** (units with `hero_id is not None`). Enemy AI (dungeon enemies) must never use potions or skills. The existing guard at the top of `decide_ai_action()` already handles this:

```python
if ai.hero_id is not None and ai.ai_stance:
    return _decide_stance_action(...)  # ← All new logic lives here
```

Dungeon enemies use `_decide_aggressive_action`, `_decide_ranged_action`, `_decide_boss_action` — none of which will be modified. This is the same exclusion pattern used for door-opening (Phase 7D).

#### 8F-4: Tests

**File:** `server/tests/test_ai_integration.py` (extended with 8F-2 tests)

| Test | Phase | Description |
|------|-------|-------------|
| `test_priority_potion_over_skill` | 8F-1 | AI at 20% HP with heal skill + potion → drinks potion (USE_ITEM) |
| `test_priority_skill_over_attack` | 8F-1 | AI at 80% HP adjacent to enemy + DS off CD → uses Double Strike |
| `test_priority_attack_when_no_skills` | 8F-1 | All skills on CD → falls through to basic ATTACK |
| `test_enemy_ai_no_potions` | 8F-1 | Enemy AI at 10% HP with potions in inventory → never drinks |
| `test_enemy_ai_no_skills` | 8F-1 | Enemy AI adjacent to ally → uses ATTACK, not skills |
| `test_all_classes_produce_valid_actions` | 8F-1 | Each class produces valid actions in various combat scenarios |
| `test_legacy_null_class_no_crash` | 8F-1 | class_id=None unit → no skills, no crash |
| `test_multi_hero_party_skills` | 8F-1 | 4-hero party: Confessor heals, Crusader War Crys, Ranger Power Shots — all in same tick |
| `test_controlled_hero_no_ai_skill` | 8F-1 | Player-controlled hero → AI skill logic skipped |
| `test_fov_computed_once_follow_stance` | 8F-2 | Follow stance: compute_fov called exactly 1 time, not duplicated |
| `test_fov_computed_once_aggressive_stance` | 8F-2 | Aggressive stance: compute_fov called exactly 1 time |
| `test_fov_computed_once_defensive_stance` | 8F-2 | Defensive stance: compute_fov called exactly 1 time |
| `test_fov_computed_once_hold_stance` | 8F-2 | Hold stance: compute_fov called exactly 1 time |
| `test_precomputed_enemies_match_self_computed` | 8F-2 | Pre-computed enemy list produces same action as self-computed |
| `test_stance_function_fallback_without_precomputed` | 8F-2 | Direct stance call without pre-computed data still works |
| `test_precomputed_data_with_team_fov` | 8F-2 | team_fov properly merged and forwarded with pre-computed data |
| `test_no_enemies_precomputed_empty_list` | 8F-2 | Empty enemy list forwarded correctly → WAIT |
| `test_aggressive_stance_consistent_with_precomputed` | 8F-2 | Aggressive: integrated vs direct call produces same result |
| `test_defensive_stance_consistent_with_precomputed` | 8F-2 | Defensive: integrated vs direct call produces same result |

**Actual scope (8F-1 + 8F-2 combined):** ~40 lines refactor in ai_behavior.py + 40 tests (30 from 8F-1 + 10 from 8F-2) in test_ai_integration.py

---

## Additional Improvements & QoL (Future Phases)

### AI Loot Pickup (Phase 8G — Low Priority)
Hero allies currently ignore ground items. They could:
- Automatically pick up potions when walking over them (if inventory not full)
- Prioritize picking up consumables over equipment
- Never equip items (leave gear decisions to the player)
- Only pick up when no enemies visible (don't waste combat turns looting)

### AI Difficulty Tuning Config (Phase 8H — Medium Priority)
Create an `ai_config.json` for tunable AI parameters:
```json
{
  "potion_thresholds": {
    "follow": 0.40,
    "aggressive": 0.25,
    "defensive": 0.50,
    "hold": 0.40
  },
  "heal_self_threshold": 0.50,
  "heal_ally_threshold": 0.60,
  "war_cry_requires_enemies_visible": true,
  "shadow_step_escape_hp_threshold": 0.30,
  "shadow_step_offensive_min_distance": 4,
  "skill_usage_enabled": true,
  "potion_usage_enabled": true
}
```
This lets you tune AI behavior without code changes, and add a "difficulty" slider later (Easy AI = higher potion threshold, uses skills less often; Hard AI = lower threshold, perfect skill usage).

### Skill Priority Modifiers Per Stance (Phase 8I — Low Priority)
Stance should influence skill usage, not just movement:
- **Aggressive stance:** Offensive skill priority (War Cry, Double Strike, Power Shot) — never uses defensive Shadow Step escape
- **Defensive stance:** Heal threshold raised to 70%, Shadow Step used defensively, War Cry only when owner is nearby
- **Hold stance:** Uses ranged skills only (Power Shot, Heal) — never Shadow Step (would break hold)

### Combat Log Narration (Phase 8J — QoL Polish)
When AI uses skills, the combat log should be clear:
- `"Ser Aldric uses War Cry! Next melee attack deals 2× damage."`
- `"Sister Maeve heals Brother Kael for 30 HP."`
- `"Shadow Fang uses Double Strike on Demon — 12 + 12 = 24 damage!"`
- Currently skill actions already generate log entries through the turn resolver, but verifying AI-triggered skill logs look correct is worth a QoL pass.

### AI Retreat Behavior (Phase 8K — Medium Priority)
Low-HP melee fighters (Crusader/Hexblade) currently fight to the death in melee. They could:
- Disengage from melee when below 20% HP and potion on cooldown (no potions left)
- Move toward the Confessor (support ally) to receive healing
- Only applies when a support ally is alive and within ~5 tiles

### Smart Potion Conservation (Phase 8L — Low Priority)
AI currently doesn't reason about potion scarcity:
- If only 1 potion left, raise the threshold (drink at 20% instead of 40%)
- If 5+ potions, lower the threshold (drink at 50% — be generous)
- Scale threshold: `adjusted = base_threshold - (potion_count - 2) * 0.05`
- This prevents AI from burning through all potions in the first room

### Future Class Extensibility Checklist
When adding a new class, the following touchpoints need updating:
1. `classes_config.json` — Add class definition with stats
2. `skills_config.json` — Add skills + update `class_skills` mapping
3. `ai_behavior.py` — Add entry to `_CLASS_ROLE_MAP` (just one line if role matches existing handler)
4. If the new class has a NEW role (e.g., "summoner", "controller"):
   - Add new `_<role>_skill_logic()` handler
   - Add role to the dispatch in `_decide_skill_usage()`
   - Add corresponding test file

---

## Implementation Order & Dependencies

```
Phase 8A: AI Potion Usage
  └─ No dependencies. Can be implemented standalone.
  └─ ~60 lines code + ~150 lines tests

Phase 8B: AI Skill Framework
  └─ No dependencies (reads skills.py, no modifications to it).
  └─ ~80 lines code + ~100 lines tests

Phase 8C: Support Role (Confessor Heal)
  └─ Depends on 8B (framework + role dispatch).
  └─ ~100 lines code + ~200 lines tests

Phase 8D: Tank Role (Crusader War Cry + Double Strike)
  └─ Depends on 8B (framework + role dispatch).
  └─ Can be parallel with 8C.
  └─ ~60 lines code + ~180 lines tests

Phase 8E: Ranged/Scout/Hybrid Roles
  └─ Depends on 8B (framework + role dispatch).
  └─ Can be parallel with 8C/8D.
  └─ ~150 lines code + ~250 lines tests

Phase 8F: Integration & Priority Chain
  └─ Depends on 8A + 8B + 8C + 8D + 8E (ties everything together).
  └─ ~80 lines refactor + ~200 lines tests
```

**Total estimated scope:** ~530 lines production code, ~1,080 lines tests

---

## Testing Strategy

- Each phase has its own test file for isolation
- Integration tests (8F) verify the full priority chain
- Enemy AI regression: every test file includes a guard test confirming enemy AI is unaffected
- Legacy/null-class regression: tests verify class_id=None units don't crash
- Arena backward compat: arena mode (no heroes, no inventory) continues to work
- All tests use the existing `PlayerState` test fixtures and mock pattern from the existing 1118-test suite

---

## Config Changes

No config file modifications required for Phases 8A through 8F. All behavior is driven by reading existing configs (`skills_config.json`, `items_config.json`, `classes_config.json`, `combat_config.json`).

Optional: Phase 8H adds `ai_config.json` for tuning thresholds without code changes.

---

## Success Criteria

After all phases complete, a dungeon run with a mixed party should look like:

1. **Confessor** hangs back from frontline, heals injured allies before attacking, keeps the party alive
2. **Crusader** charges in with War Cry active, uses Double Strike on every cooldown cycle
3. **Ranger** stays at range, fires Power Shot when available, uses basic ranged otherwise
4. **Hexblade** Shadow Steps to gap-close, Double Strikes in melee, retreats via teleport when low
5. **Inquisitor** scouts with best vision, Power Shots from range, escapes via Shadow Step when cornered
6. **All heroes** drink health potions when hurt instead of dying with full inventories
7. **Enemy AI** is completely unchanged — no potions, no skills, no regression
