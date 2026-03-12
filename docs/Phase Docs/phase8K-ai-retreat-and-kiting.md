# Phase 8K — AI Retreat Behavior & Kiting

## Overview

Hero allies currently fight to the death once potions run out. A Crusader at 5 HP will keep face-tanking instead of backing up toward the Confessor for healing. A Ranger stuck in melee range will basic-attack instead of stepping back and using their ranged attack. There is no concept of "disengage" or "kite" for hero ally AI — only the **enemy ranged AI** (`_decide_ranged_action`) and the **Scout's Shadow Step escape** (Phase 8E-2) have any form of retreat.

**Goal:** Make AI-controlled party members retreat intelligently when their HP is critically low and they have no potions remaining. Melee units should fall back toward the support ally for healing. Ranged units should kite (step back from melee range to maintain ranged attack distance). The system should feel like your party members have survival instincts instead of being suicidal.

---

## Current State (Diagnosed)

### What DOES Exist for Retreat

| System | Where | What It Does |
|--------|-------|--------------|
| **Enemy ranged AI retreat** | `_decide_ranged_action()` (line ~1274) | Enemy Skeletons retreat if player gets within 2 tiles. Uses `_find_retreat_tile()` to pick the adjacent tile that maximizes Chebyshev distance from the threat. |
| **Scout Shadow Step escape** | `_scout_skill_logic()` (line ~620) | Inquisitor at <30% HP AND adjacent to enemy AND Shadow Step off cooldown → teleports 2-3 tiles away. Uses `_find_shadow_step_escape_tile()` to score tiles by max-distance-from-enemy + bonus if still within ranged range. |
| **Potion drinking** | `_should_use_potion()` (line ~1670) | Hero allies drink potions when HP drops below stance-dependent threshold (25-50%). Runs as highest-priority check in `_decide_stance_action()`. |

### What Does NOT Exist (The Problem)

| Gap | Impact |
|-----|--------|
| **No walk-away retreat for any stance** | All 4 stance handlers (`follow`, `aggressive`, `defensive`, `hold`) have zero retreat logic. If adjacent to an enemy, they attack. If potions are gone, they die. |
| **No kiting for ranged hero allies** | Ranger in `_decide_follow_action()` will rush toward enemies within 3 tiles (line ~1920: `if not is_support and dist_to_target <= 3: move toward enemy`). A Ranger at distance 1 does basic melee instead of stepping back to ranged sweet spot. |
| **No "retreat to healer" pathing** | Injured melee units don't path toward the Confessor for healing. Support positioning (8C-2) only affects the Confessor's own movement, not other units' retreat paths. |
| **No potion-aware retreat** | When potions are exhausted, AI has no fallback survival strategy. The only option below potion threshold is `_should_use_potion()` returning `None` (no potions), then falling through to normal fight-to-the-death behavior. |
| **Hold stance never retreats** | Expected behavior — Hold means "don't move". But this should be documented as intentional. |

### Relevant Code Locations

All changes will be in **`server/app/core/ai_behavior.py`** (currently 2789 lines).

| Location | Line | What's There |
|----------|------|--------------|
| `_decide_stance_action()` | ~1738 | Top-level stance dispatcher. Potion → Skill → Stance. **Retreat check will slot in here.** |
| `_decide_follow_action()` | ~1806 | Follow stance. Enemies visible → pick target → adjacent=ATTACK, dist<=3=rush, else ranged/move. |
| `_decide_aggressive_stance_action()` | ~1979 | Aggressive stance. Similar fight logic, roams within 5 tiles of owner. |
| `_decide_defensive_action()` | ~2123 | Defensive stance. Stays within 2 tiles of owner, only fights nearby enemies. |
| `_decide_hold_action()` | ~2244 | Hold stance. Never moves, attacks in range. **No retreat changes needed.** |
| `_find_retreat_tile()` | ~1421 | Existing helper (used by enemy ranged AI). Finds adjacent tile that maximizes distance from a threat. **Reusable.** |
| `_find_owner()` | ~1600 | Finds the human player who owns a hero ally. |
| `_support_move_preference()` | ~187 | Support positioning helper — routes Confessor toward injured allies. |
| `_POTION_THRESHOLDS` | ~70 | Per-stance HP thresholds for potion usage. |
| `_CLASS_ROLE_MAP` | ~85 | Maps class_id → role (tank/support/ranged_dps/hybrid_dps/scout). |
| `_SHADOW_STEP_ESCAPE_HP_THRESHOLD` | ~63 | 0.30 — Scout escapes with Shadow Step below this. |
| `_pick_best_target()` | ~2486 | Weighted target selection (low HP, threat, distance). |
| `_chebyshev()` | ~1620 | Chebyshev distance helper. |
| `_build_occupied_set()` | ~807 | Builds occupied tile set with pending-move prediction. |

### Current Priority Chain in `_decide_stance_action()`

```
1. POTION CHECK       → HP below threshold AND potions available? → USE_ITEM
2. [gap — retreat would go here]
3. SKILL DECISION     → Role-appropriate skill available? → SKILL
4. STANCE BEHAVIOR    → follow/aggressive/defensive/hold combat logic
   4a. Adjacent enemy    → ATTACK (basic melee)
   4b. Ranged available  → RANGED_ATTACK
   4c. Move toward       → MOVE
   4d. Regroup/patrol    → MOVE toward owner
   4e. Nothing to do     → WAIT
```

### Current Class Stats Reference

| Class | Role | HP | Melee | Ranged | Armor | Vision | Range |
|-------|------|-----|-------|--------|-------|--------|-------|
| Crusader | Tank | 150 | 20 | 0 | 8 | 5 | 1 |
| Confessor | Support | 100 | 8 | 0 | 3 | 6 | 1 |
| Inquisitor | Scout | 80 | 10 | 8 | 4 | 9 | 5 |
| Ranger | Ranged DPS | 80 | 8 | 18 | 2 | 7 | 6 |
| Hexblade | Hybrid DPS | 110 | 15 | 12 | 5 | 6 | 4 |

---

## Design Principles

1. **Retreat is a MOVEMENT action** — The AI spends its turn moving instead of attacking. This is a meaningful trade-off. Retreating costs DPS but saves the hero's life.
2. **Retreat only triggers when potions are exhausted** — If the AI has potions, it should drink them (Phase 8A handles this). Retreat is the fallback when there's nothing left to drink.
3. **Role-aware retreat thresholds** — Tanks retreat last, supports retreat first. This creates natural frontline/backline behavior.
4. **"Retreat toward healer" creates emergent teamwork** — Injured Crusader backs up toward Confessor, Confessor heals, Crusader re-engages. This loop should happen naturally from the priority chains.
5. **Kiting is separate from retreat** — Ranged units should ALWAYS prefer staying at ranged distance, not just when low HP. Kiting is about optimal positioning, not panic fleeing.
6. **Hold stance never retreats** — Hold means "stand your ground." This is intentional and should not be modified.

---

## Phased Implementation Plan

### Phase 8K-1: Retreat Helpers & Constants

**Files:** `server/app/core/ai_behavior.py`

#### 8K-1a: Retreat HP Thresholds (Constants)

Add per-role retreat thresholds at the top of `ai_behavior.py` alongside existing constants:

```python
# ---------------------------------------------------------------------------
# Phase 8K: AI Retreat Behavior — HP thresholds per role
# ---------------------------------------------------------------------------
# Below these HP% thresholds (AND no potions remaining), hero AI will
# disengage from melee and retreat instead of continuing to fight.
_RETREAT_THRESHOLDS: dict[str, float] = {
    "tank": 0.15,         # Tanks retreat last — they're built to take hits
    "support": 0.35,      # Supports retreat earliest — dead healer = party wipe
    "ranged_dps": 0.25,   # Ranged should be at distance anyway, retreat if caught in melee
    "hybrid_dps": 0.20,   # Hybrid commits to melee, moderate retreat threshold
    "scout": 0.25,        # Scout has Shadow Step escape; walk-retreat is the fallback
}

# Default retreat threshold for unknown roles
_RETREAT_THRESHOLD_DEFAULT = 0.25
```

**Design note:** These thresholds are LOWER than potion thresholds (25-50%) because retreat is the last resort — potions should be tried first. A Crusader at 30% HP with potions will drink; at 30% HP without potions, they keep fighting; at 15% HP without potions, NOW they retreat.

#### 8K-1b: `_has_potions()` Helper

A small helper to check if an AI has any heal-type potions remaining, without building the full `_should_use_potion` action. This is needed to determine if retreat should activate (retreat only fires when potions are exhausted).

```python
def _has_heal_potions(ai: PlayerState) -> bool:
    """Check if the AI has any heal consumables in inventory.

    Returns True if at least one item in inventory is a consumable with
    heal effect. Does not check HP threshold or cooldowns — purely an
    inventory scan.

    Used by retreat logic: retreat only triggers when potions are exhausted.
    """
    for item in ai.inventory:
        if not isinstance(item, dict):
            continue
        if item.get("item_type") != "consumable":
            continue
        effect = item.get("consumable_effect")
        if not effect or not isinstance(effect, dict):
            continue
        if effect.get("type") == "heal":
            return True
    return False
```

#### 8K-1c: `_should_retreat()` Decision Helper

Core retreat decision function. Returns `True` when ALL of the following are true:
1. AI HP is at or below the role-specific retreat threshold
2. AI has no heal potions remaining in inventory
3. AI is adjacent to or within 2 tiles of an enemy (in active danger)
4. AI's stance is NOT "hold" (hold units never move)

```python
def _should_retreat(
    ai: PlayerState,
    enemies: list[PlayerState],
) -> bool:
    """Determine if the AI should retreat from combat.

    Returns True when:
      1. HP is at or below the role-specific retreat threshold
      2. No heal potions remaining in inventory
      3. At least one enemy is within 2 tiles (in active danger)
      4. Stance is not 'hold' (hold units never move)

    This check runs AFTER the potion check in _decide_stance_action().
    If potions were available, _should_use_potion() would have already
    returned a USE_ITEM action before we get here.

    Args:
        ai: The AI unit.
        enemies: List of visible enemies (pre-computed in _decide_stance_action).

    Returns:
        True if the AI should disengage and retreat.
    """
    # Hold stance: never retreat (never moves by design)
    stance = ai.ai_stance or "follow"
    if stance == "hold":
        return False

    # Check HP threshold based on role
    role = _get_role_for_class(ai.class_id) if ai.class_id else None
    threshold = _RETREAT_THRESHOLDS.get(role, _RETREAT_THRESHOLD_DEFAULT) if role else _RETREAT_THRESHOLD_DEFAULT

    if ai.max_hp <= 0:
        return False
    if ai.hp / ai.max_hp > threshold:
        return False  # HP is OK, no need to retreat

    # Only retreat when potions are exhausted
    if _has_heal_potions(ai):
        return False  # Still have potions — potion check should handle this

    # Must be in active danger (enemy within 2 tiles)
    ai_pos = (ai.position.x, ai.position.y)
    in_danger = any(
        _chebyshev(ai_pos, (e.position.x, e.position.y)) <= 2
        for e in enemies
    )

    return in_danger
```

#### 8K-1d: `_find_retreat_destination()` — Smart Retreat Target Selection

This is the core positioning logic. Unlike the simple `_find_retreat_tile()` (which just picks the adjacent tile farthest from the threat), this function decides WHERE to retreat TO based on party context.

```python
def _find_retreat_destination(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    door_tiles: set[tuple[int, int]] | None = None,
) -> PlayerAction | None:
    """Find the best retreat action for a low-HP hero ally.

    Retreat target priority:
      1. Move toward alive support ally (Confessor) — they can heal us
      2. Move toward owner (human player) — safety in numbers
      3. Move away from nearest enemy — generic flee

    For each target, uses A* pathfinding (door-aware) and returns a MOVE action
    toward the first step of the path to the retreat destination.

    Returns MOVE action, or None if completely stuck (cornered, surrounded).
    """
```

**Retreat target priority logic:**

1. **Find alive support ally within ~8 tiles:** Scan `all_units` for alive same-team units with `_get_role_for_class(unit.class_id) == "support"`. If found and within reasonable distance (≤8 tiles), path toward them. The Confessor has Heal (range 3), so getting within 3 tiles is the actual goal — the Confessor's `_support_skill_logic()` will then heal the retreating unit next tick.

2. **Path toward owner:** If no support ally is alive/nearby, fall back to moving toward the human player (via `_find_owner()`). Staying grouped is safer than fleeing alone.

3. **Generic flee (last resort):** If owner is dead or same position, use `_find_retreat_tile()` to pick the adjacent tile farthest from the nearest enemy. This is the existing helper from Phase 4C enemy ranged AI.

**Important — door-awareness:** Retreat pathing must use `door_tiles` parameter (passed through from `_decide_stance_action`) so heroes can retreat through closed doors if needed.

**`_maybe_interact_door()` integration:** If the first step of the retreat path is a closed door tile, return INTERACT instead of MOVE (same pattern used by all stance functions since Phase 7D-1).

---

### Phase 8K-2: Integration into Stance Dispatch

**Files:** `server/app/core/ai_behavior.py`

#### 8K-2a: New Priority Layer in `_decide_stance_action()`

Insert the retreat check between the potion check and the skill decision. The updated priority chain becomes:

```python
def _decide_stance_action(ai, all_units, grid_width, grid_height, obstacles, ...):
    stance = ai.ai_stance or "follow"

    # --- Priority 1: Potion check (highest priority) ---
    threshold = _POTION_THRESHOLDS.get(stance, 0.40)
    potion_action = _should_use_potion(ai, hp_threshold=threshold)
    if potion_action:
        return potion_action

    # --- Pre-compute visible enemies (existing Phase 8F-2 code) ---
    # ... (compute FOV, find visible enemies, store in pre_enemies) ...

    # --- Priority 2: RETREAT CHECK (new - Phase 8K) ---
    if _should_retreat(ai, pre_enemies):
        retreat_action = _find_retreat_destination(
            ai, pre_enemies, all_units,
            grid_width, grid_height, obstacles,
            occupied, door_tiles,
        )
        if retreat_action:
            return retreat_action
        # If retreat failed (cornered), fall through to skills/combat
        # — fighting is better than doing nothing when you can't escape

    # --- Priority 3: Skill decision ---
    skill_action = _decide_skill_usage(ai, pre_enemies, all_units, ...)
    if skill_action:
        return skill_action

    # --- Priority 4: Stance behavior ---
    ...
```

**Why between potion and skill, not after skill?**
- If AI has a heal skill (Confessor), it should self-heal rather than retreat. The skill logic already handles this — `_support_skill_logic()` heals self at <50% HP.
- BUT: a non-support unit (Crusader at 10% HP, no potions, no heal skill) should retreat BEFORE trying to Double Strike. A dead Crusader deals 0 DPS. Retreating toward the Confessor lets them get healed and come back.
- Exception: if retreat fails (cornered, no walkable tiles), fall through to skill/combat — dying while fighting is better than dying while WAITing.

**Why compute occupied set early?** The retreat destination function needs the `occupied` set for A* pathfinding. Currently `occupied` is built inside each stance function. To avoid duplicate computation, compute it once in `_decide_stance_action()` after the FOV pre-compute, then pass it to both the retreat function and the stance function.

This requires a small refactor: the 4 stance functions (`follow`, `aggressive`, `defensive`, `hold`) need to accept an optional `precomputed_occupied` parameter — same pattern already used for `precomputed_visible_tiles` and `precomputed_enemies` (Phase 8F-2).

#### 8K-2b: Occupied Set Pre-computation

Add `occupied = _build_occupied_set(all_units, ai.player_id, pending_moves)` into `_decide_stance_action()` alongside the existing FOV pre-compute, then forward it to stance handlers.

```python
    # Pre-compute shared context (existing FOV + new occupied set)
    ai_pos = (ai.position.x, ai.position.y)
    own_fov = compute_fov(...)
    visible_tiles = (own_fov | team_fov) if team_fov else own_fov
    pre_enemies = [...]  # existing code

    occupied = _build_occupied_set(all_units, ai.player_id, pending_moves)  # NEW

    # Retreat check uses occupied
    if _should_retreat(ai, pre_enemies):
        retreat_action = _find_retreat_destination(
            ai, pre_enemies, all_units,
            grid_width, grid_height, obstacles,
            occupied, door_tiles,
        )
        ...
```

The stance handlers already compute `occupied` internally via `_build_occupied_set()`. When the pre-computed value is passed, they should reuse it instead. This also eliminates 1 redundant `_build_occupied_set()` call per AI hero per tick (same optimization pattern as the FOV pre-compute from Phase 8F-2).

---

### Phase 8K-3: Ranged Kiting (Ranger & Inquisitor)

**Files:** `server/app/core/ai_behavior.py`

This is separate from the low-HP retreat system. Kiting is about **optimal positioning** for ranged attackers, regardless of HP level.

#### The Problem

In `_decide_follow_action()` (and `_decide_aggressive_stance_action()`), when enemies are visible:

```python
# Current code (line ~1920 in _decide_follow_action):
# Close enough to rush → melee (non-support only)
if not is_support and dist_to_target <= 3:
    next_step = get_next_step_toward(ai_pos, target_pos, ...)
    return MOVE toward enemy
```

A Ranger at distance 1 from an enemy hits this branch and moves INTO the enemy to melee. A Ranger should NEVER rush to melee — they should step back to maintain ranged distance. Similarly, if a Ranger is adjacent to an enemy, the current code returns `ATTACK` (basic melee for 8 damage) instead of stepping back and using `RANGED_ATTACK` (18 damage at range).

#### The Fix: Role-Aware Melee Rush Gate

Add a check: ranged-role units (`ranged_dps`, `scout`) should NOT use the "rush to melee" branch. Instead, they should:

1. **If adjacent to enemy:** Step back using `_find_retreat_tile()` (reuse existing helper). Pick the tile that maximizes distance from the threat, ideally staying within ranged range.
2. **If within 2-3 tiles (too close for comfort):** Also step back, don't rush forward.
3. **If at ranged sweet spot (3-6 tiles):** Fire ranged attack (existing logic handles this).
4. **If too far:** Move closer (existing logic handles this).

```python
# Modified logic in _decide_follow_action() and _decide_aggressive_stance_action():

if enemies:
    target = _pick_best_target(ai, enemies, all_units)
    target_pos = Position(x=target.position.x, y=target.position.y)
    dist_to_target = _chebyshev(ai_pos, (target.position.x, target.position.y))

    # --- Phase 8K-3: Ranged kiting ---
    is_ranged_role = role in ("ranged_dps", "scout") if role else False

    if is_ranged_role and dist_to_target <= 2:
        # Too close — step away to maintain ranged distance
        retreat_tile = _find_retreat_tile(
            ai_pos, (target.position.x, target.position.y),
            grid_width, grid_height, obstacles, occupied,
        )
        if retreat_tile:
            return PlayerAction(
                player_id=ai_id, action_type=ActionType.MOVE,
                target_x=retreat_tile[0], target_y=retreat_tile[1],
            )
        # Can't step back — melee as last resort (fall through)

    # Adjacent → melee (melee/hybrid units, or ranged units that can't kite)
    if is_adjacent(ai.position, target_pos):
        return PlayerAction(
            player_id=ai_id, action_type=ActionType.ATTACK,
            target_x=target.position.x, target_y=target.position.y,
        )

    # Rush to melee — ONLY for melee/hybrid roles (not ranged)
    if not is_support and not is_ranged_role and dist_to_target <= 3:
        next_step = get_next_step_toward(...)
        return MOVE toward enemy
    
    # Ranged attack if available (existing logic — unchanged)
    ...
```

**Affected stance functions:**
- `_decide_follow_action()` — primary stance, needs kiting
- `_decide_aggressive_stance_action()` — also has the "rush to melee" branch
- `_decide_defensive_action()` — only engages within 2 tiles, kiting here would conflict with the "stay near owner" constraint. **Skip kiting for defensive stance** — the 2-tile owner leash already provides natural positioning.
- `_decide_hold_action()` — never moves. **No changes needed.**

**What about hybrid_dps (Hexblade)?**
Hexblade has `ranged_range=4` and `ranged_damage=12`, but their melee damage (15) is higher and they have Double Strike. Hexblade SHOULD rush to melee — that's their design. They already have Shadow Step to gap-close (Phase 8E-3). Do NOT add kiting to hybrid_dps.

---

### Phase 8K-4: Tests

**New file:** `server/tests/test_ai_retreat.py`

#### Retreat Decision Tests (`_should_retreat`)

| Test | Description |
|------|-------------|
| `test_should_retreat_low_hp_no_potions` | AI at 10% HP, no potions, enemy adjacent → returns True |
| `test_should_not_retreat_has_potions` | AI at 10% HP, has potions, enemy adjacent → returns False (potions handle this) |
| `test_should_not_retreat_hp_above_threshold` | AI at 50% HP, no potions, enemy adjacent → returns False |
| `test_should_not_retreat_no_enemies_nearby` | AI at 10% HP, no potions, enemy 5 tiles away → returns False (not in danger) |
| `test_should_not_retreat_hold_stance` | AI at 10% HP, no potions, enemy adjacent, hold stance → returns False |
| `test_retreat_threshold_per_role` | Tank retreats at 15%, support at 35%, ranged at 25%, etc. |
| `test_should_not_retreat_full_hp` | AI at 100% HP, no potions, enemy adjacent → returns False |
| `test_retreat_null_class` | class_id=None → uses default threshold, no crash |

#### `_has_heal_potions` Tests

| Test | Description |
|------|-------------|
| `test_has_heal_potions_with_health_potion` | Inventory has health_potion → True |
| `test_has_heal_potions_empty_inventory` | Empty inventory → False |
| `test_has_heal_potions_only_equipment` | Inventory has sword only → False |
| `test_has_heal_potions_only_portal_scroll` | Portal scroll (non-heal consumable) → False |
| `test_has_heal_potions_mixed_inventory` | Mix of gear + potions → True |

#### Retreat Destination Tests (`_find_retreat_destination`)

| Test | Description |
|------|-------------|
| `test_retreat_toward_confessor` | Injured Crusader retreats toward alive Confessor |
| `test_retreat_toward_owner_no_support` | No Confessor alive → retreats toward owner |
| `test_retreat_away_from_enemy_no_allies` | No allies alive → moves away from nearest enemy |
| `test_retreat_path_door_aware` | Retreat path goes through closed door → returns INTERACT |
| `test_retreat_cornered_returns_none` | Surrounded by walls + enemies → returns None (fall through to fight) |
| `test_retreat_prefers_support_over_owner` | Both support ally + owner available → paths toward support |
| `test_retreat_support_too_far` | Confessor alive but 15 tiles away → falls back to owner |

#### Integration Tests (Priority Chain)

| Test | Description |
|------|-------------|
| `test_priority_potion_over_retreat` | AI at 10% HP WITH potions → drinks potion, not retreat |
| `test_priority_retreat_over_skill` | AI at 10% HP, no potions, adjacent enemy → retreats, not Double Strike |
| `test_retreat_fallthrough_to_skill_when_cornered` | Cornered (retreat fails) → uses skill instead |
| `test_retreat_fallthrough_to_attack_when_cornered` | Cornered + skills on CD → basic attacks |
| `test_follow_stance_retreat` | Follow stance AI at retreat threshold → retreats |
| `test_aggressive_stance_retreat` | Aggressive stance AI at retreat threshold → retreats |
| `test_defensive_stance_retreat` | Defensive stance AI at retreat threshold → retreats |
| `test_hold_stance_no_retreat` | Hold stance AI at retreat threshold → attacks (never moves) |

#### Kiting Tests (Ranged Classes)

| Test | Description |
|------|-------------|
| `test_ranger_kites_when_adjacent` | Ranger adjacent to enemy → steps back instead of melee |
| `test_ranger_kites_when_distance_2` | Ranger 2 tiles from enemy → steps back to ranged sweet spot |
| `test_ranger_attacks_ranged_at_distance` | Ranger at 4 tiles → fires ranged attack (no kiting needed) |
| `test_ranger_melee_when_cornered` | Ranger adjacent, can't step back (wall) → melee as fallback |
| `test_inquisitor_kites_same_as_ranger` | Inquisitor (scout role) kites identically to Ranger |
| `test_crusader_does_not_kite` | Crusader adjacent → melee attacks normally (tank doesn't kite) |
| `test_hexblade_does_not_kite` | Hexblade adjacent → melee attacks (hybrid doesn't kite) |
| `test_confessor_does_not_kite` | Confessor has no ranged — support positioning already handled by 8C-2 |
| `test_ranger_kiting_follow_stance` | Follow stance: Ranger kites correctly |
| `test_ranger_kiting_aggressive_stance` | Aggressive stance: Ranger kites correctly |
| `test_ranger_no_kiting_defensive_stance` | Defensive stance: kiting skipped (owner-leash takes priority) |
| `test_ranger_no_kiting_hold_stance` | Hold stance: never moves (implicit — no kiting possible) |

#### Guard / Regression Tests

| Test | Description |
|------|-------------|
| `test_enemy_ai_no_retreat` | Enemy AI at 5% HP → fights normally (enemies never use hero retreat) |
| `test_enemy_ai_no_kiting_via_stances` | Enemy ranged AI still uses its own `_decide_ranged_action` kiting (unchanged) |
| `test_retreat_does_not_affect_full_hp_combat` | AI at 100% HP → normal combat behavior unchanged |
| `test_legacy_null_class_no_crash` | class_id=None → no retreat crash, default threshold used |

---

## Updated Priority Chain (After Implementation)

```
1. POTION CHECK       → HP below threshold AND potions available? → USE_ITEM
2. RETREAT CHECK (8K) → HP below retreat threshold AND no potions AND in danger? → MOVE (toward healer/owner/away)
3. SKILL DECISION     → Role-appropriate skill available? → SKILL
4. STANCE BEHAVIOR    → follow/aggressive/defensive/hold combat logic
   4a. KITE CHECK (8K-3) → Ranged role adjacent to enemy? → MOVE (step back)
   4b. Adjacent enemy    → ATTACK (basic melee)
   4c. Ranged available  → RANGED_ATTACK
   4d. Rush to melee     → MOVE (melee/hybrid only, NOT ranged roles)
   4e. Move toward       → MOVE
   4f. Regroup/patrol    → MOVE toward owner
   4g. Nothing to do     → WAIT
```

Note: Retreat (step 2) is in `_decide_stance_action()` centrally, while kiting (step 4a) is inside each stance function's combat logic.

---

## Emergent Behaviors (Expected)

After implementation, a dungeon fight should look like this:

1. **Full HP, potions available:** All heroes fight normally (no change from current behavior).
2. **HP drops below potion threshold:** Hero drinks a potion (Phase 8A — already works).
3. **Potions exhausted, HP drops below retreat threshold:** Hero disengages from melee and paths toward the Confessor.
4. **Confessor sees injured ally within range 3:** Confessor heals the retreating hero (Phase 8C — already works).
5. **Hero gets healed back above retreat threshold:** Hero re-engages in combat (normal stance behavior resumes).
6. **If Confessor is dead:** Hero retreats toward owner, or away from enemies. Will eventually die, but lives longer than face-tanking.
7. **Ranger gets caught in melee:** Steps back 1-2 tiles, fires ranged attack from safe distance. Never willingly stands in melee range.

---

## Reusable Existing Code

| Function | How It's Reused |
|----------|----------------|
| `_find_retreat_tile()` | Used by kiting (8K-3) for step-back tile selection. Already proven in enemy ranged AI. |
| `_find_owner()` | Used by retreat destination fallback (path toward owner). |
| `_get_role_for_class()` | Used for role-specific retreat thresholds and kiting gates. |
| `_chebyshev()` | Used for distance checks (danger zone, support ally proximity). |
| `_build_occupied_set()` | Used by retreat pathing. Will be pre-computed in `_decide_stance_action()`. |
| `get_next_step_toward()` | A* pathfinding for retreat destination. Door-aware. |
| `_maybe_interact_door()` | Retreat through closed doors. |
| `_has_heal_potions()` | NEW — extracted from `_should_use_potion()` logic for lightweight inventory check. |

---

## Implementation Order & Dependencies

```
Phase 8K-1: Retreat Helpers & Constants
  └─ No dependencies. Constants + 3 helper functions.
  └─ ~100 lines code

Phase 8K-2: Integration into _decide_stance_action()
  └─ Depends on 8K-1 (helpers must exist).
  └─ ~30 lines refactor (insert retreat check, pre-compute occupied set)

Phase 8K-3: Ranged Kiting
  └─ No dependency on 8K-1/8K-2 (independent logic in stance functions).
  └─ Can be implemented in parallel with 8K-1/8K-2.
  └─ ~50 lines code (in _decide_follow_action + _decide_aggressive_stance_action)

Phase 8K-4: Tests                                          ✅ COMPLETE
  └─ Depends on 8K-1 + 8K-2 + 8K-3 (all logic must exist to test).
  └─ 52 tests total (32 new retreat/integration + 20 existing kiting)
```

**Total estimated scope:** ~180 lines production code, ~400 lines tests

---

## Config Changes

No config file modifications required. All behavior is driven by constants in `ai_behavior.py`:
- `_RETREAT_THRESHOLDS` — per-role HP thresholds
- `_RETREAT_THRESHOLD_DEFAULT` — fallback for unknown roles

Optional future: Move these to `ai_config.json` (Phase 8H) alongside potion thresholds for external tuning.

---

## Files Modified

| File | Changes |
|------|---------|
| `server/app/core/ai_behavior.py` | New constants (`_RETREAT_THRESHOLDS`), 3 new helpers (`_has_heal_potions`, `_should_retreat`, `_find_retreat_destination`), refactored `_decide_stance_action()` (retreat priority layer + occupied pre-compute), modified `_decide_follow_action()` (kiting gate), modified `_decide_aggressive_stance_action()` (kiting gate) |

## Files Created

| File | Purpose |
|------|---------|
| `server/tests/test_ai_retreat.py` | ~40 tests covering retreat decisions, destinations, kiting, integration, and regression guards |

---

## Edge Cases & Guardrails

| Edge Case | Expected Behavior |
|-----------|-------------------|
| AI cornered (walls + enemies on all sides) | `_find_retreat_destination()` returns None → fall through to skill/attack. Fighting is better than doing nothing. |
| All allies dead (no support, no owner) | Retreat uses `_find_retreat_tile()` to move away from nearest enemy (generic flee). |
| AI at exactly retreat threshold HP | Retreat triggers (threshold check is `<=`). |
| AI with 0 max_hp (edge case / data error) | `_should_retreat()` returns False (guard: `max_hp <= 0`). |
| Enemy AI at low HP | Enemy AI never routes through `_decide_stance_action()` — uses `_decide_aggressive_action` / `_decide_ranged_action` / `_decide_boss_action`. Completely unaffected. |
| Hold stance at low HP, no potions | No retreat (Hold never moves). Falls through to skill check, then ranged/melee attack if possible, else WAIT. Will die in place — this is by design. |
| Defensive retreat conflicts with owner-leash | Retreat paths toward support/owner, which naturally stays within the defensive leash radius. If retreat tile is outside 2-tile leash, the defensive stance's own leash check won't override because retreat fires BEFORE stance dispatch. This is correct — survival > positioning constraint. |
| Ranger kites into wall | `_find_retreat_tile()` returns None → falls through to melee attack as last resort. |
| Ranger kites away from one enemy into adjacency with another | `_find_retreat_tile()` only considers the primary threat, not all enemies. Acceptable trade-off — kiting to a suboptimal tile is still better than standing in melee with the original threat. Future improvement: score kite tiles against ALL nearby enemies. |

---

## Success Criteria

After Phase 8K is complete:

1. **Crusader at 15% HP, no potions** → Disengages from melee and paths toward Confessor. Confessor heals. Crusader re-engages above threshold.
2. **Confessor at 35% HP, no potions** → Flees from melee threats toward owner/away. Does NOT stay to heal allies when their own life is at risk.
3. **Ranger adjacent to enemy, any HP** → Steps back 1-2 tiles and fires ranged attack (18 damage >> 8 melee damage). Never voluntarily stays in melee.
4. **Hexblade adjacent to enemy** → Stays and melee attacks (does NOT kite — hybrid is melee-committed).
5. **Hold stance at 5% HP** → Stands ground and attacks. Dies in place. Intentional.
6. **Enemy AI at 5% HP** → Fights normally. No regression from hero retreat logic.
7. **Party synergy loop** → Tank retreats → Confessor heals → Tank returns. This should happen multiple times in a long fight.
