"""
AI Stance Behavior — Stance-based AI decision logic for hero allies.

Extracted from ai_behavior.py (P1 refactoring — pure mechanical move).

Implements:
  - Stance dispatch (_decide_stance_action)
  - Follow stance (default): stay close to owner, fight nearby enemies
  - Aggressive stance: pursue enemies freely within 5 tiles of owner
  - Defensive stance: stay within 2 tiles of owner, only attack nearby
  - Hold stance: never move, attack enemies in range
  - Potion usage helper (_should_use_potion)
  - Retreat logic (_should_retreat, _find_retreat_destination)
  - Door interaction helper (_maybe_interact_door)
  - Owner lookup (_find_owner)
"""

from __future__ import annotations

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.fov import compute_fov, has_line_of_sight
from app.core.combat import is_adjacent, is_in_range, get_combat_config
from app.core.ai_pathfinding import (
    _build_occupied_set,
    get_next_step_toward,
)
from app.core.ai_skills import (
    _get_role_for_class,
    _support_move_preference,
    _offensive_support_move_preference,
    _decide_skill_usage,
)
from app.core.ai_memory import (
    _update_enemy_memory,
    _pursue_memory_target,
    _reinforce_ally,
    _pick_best_target,
)
from app.core.ai_patrol import _patrol_targets


# ---------------------------------------------------------------------------
# Phase 8A: AI Potion Usage — HP thresholds per stance
# ---------------------------------------------------------------------------
# Below these HP% thresholds, hero AI will drink a potion instead of fighting.
_POTION_THRESHOLDS: dict[str, float] = {
    "follow": 0.40,       # Balanced — drink when moderately hurt
    "aggressive": 0.25,   # Reckless — push damage, drink only when critical
    "defensive": 0.50,    # Cautious — drink early to stay topped off
    "hold": 0.40,         # Same as follow — stationary but not suicidal
}

# ---------------------------------------------------------------------------
# Phase 8K: AI Retreat Behavior — HP thresholds per role
# ---------------------------------------------------------------------------
# Below these HP% thresholds (AND no potions remaining), hero AI will
# disengage from melee and retreat instead of continuing to fight.
_RETREAT_THRESHOLDS: dict[str, float] = {
    "tank": 0.15,         # Tanks retreat last — they're built to take hits
    "retaliation_tank": 0.15,  # Revenant — same as tank; cheat_death suppresses retreat entirely (custom check below)
    "support": 0.35,      # Supports retreat earliest — dead healer = party wipe
    "ranged_dps": 0.25,   # Ranged should be at distance anyway, retreat if caught in melee
    "caster_dps": 0.30,   # Caster is glass cannon — retreat earlier than other ranged
    "hybrid_dps": 0.20,   # Hybrid commits to melee, moderate retreat threshold
    "scout": 0.25,        # Scout has Shadow Step escape; walk-retreat is the fallback
    "sustain_dps": 0.20,  # Blood Knight — only retreats when sustain is exhausted (custom check below)
    "controller": 0.30,   # Plague Doctor — squishy midliner, retreat early like caster_dps
    "totemic_support": 0.35,  # Shaman — backline support, retreat early like support
    "offensive_support": 0.30,  # Bard — squishy backline buffer, retreat early
}

# Default retreat threshold for unknown roles
_RETREAT_THRESHOLD_DEFAULT = 0.25

# ---------------------------------------------------------------------------
# Phase 26D: Totem Awareness — AI heroes recognize healing totems as safe zones
# ---------------------------------------------------------------------------
# Max distance at which AI will consider retreating toward a healing totem.
_TOTEM_RETREAT_MAX_DIST = 8
# Totem proximity bonus weight for kiting tile selection (higher = stronger pull).
_TOTEM_KITE_BIAS_WEIGHT = 2

# ---------------------------------------------------------------------------
# Valid AI Stances (Phase 7C)
# ---------------------------------------------------------------------------

VALID_STANCES = {"follow", "aggressive", "defensive", "hold"}


# ---------------------------------------------------------------------------
# Stance Owner Lookup (Phase 7C)
# ---------------------------------------------------------------------------

def _find_owner(ai: PlayerState, all_units: dict[str, PlayerState]) -> PlayerState | None:
    """Find the human player who owns this hero ally.

    Owner is the human on the same team.  For multi-player scenarios, the
    owner is the player whose ``controlled_by`` matches, or falling back
    to any human on the same team.
    """
    # If explicitly controlled, find that controller
    if ai.controlled_by:
        owner = all_units.get(ai.controlled_by)
        if owner and owner.is_alive:
            return owner

    # Fallback: find any alive human on the same team
    for u in all_units.values():
        if u.unit_type == "human" and u.team == ai.team and u.is_alive:
            return u

    # Phase 27: PVPVE AI teams have no human — follow the team leader instead
    for u in all_units.values():
        if (
            getattr(u, 'is_team_leader', False)
            and u.team == ai.team
            and u.is_alive
            and u.player_id != ai.player_id
        ):
            return u
    return None


def _chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Chebyshev distance between two points."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _find_nearest_healing_totem(
    match_state,
    team: str,
    pos: tuple[int, int],
    max_dist: int = _TOTEM_RETREAT_MAX_DIST,
) -> dict | None:
    """Find the nearest alive, same-team healing totem within *max_dist* tiles.

    Returns the totem dict (with x, y, effect_radius, etc.) or None.
    Used by retreat logic and combat positioning to bias AI toward totem
    heal zones without hard-locking them.

    Phase 26D: Totem Awareness.
    """
    if match_state is None or not hasattr(match_state, "totems"):
        return None
    best: dict | None = None
    best_dist = max_dist + 1
    for totem in match_state.totems:
        if totem.get("type") != "healing_totem":
            continue
        if totem.get("team") != team:
            continue
        if totem.get("hp", 0) <= 0:
            continue
        if totem.get("duration_remaining", 0) <= 0:
            continue
        tx, ty = totem.get("x", 0), totem.get("y", 0)
        dist = _chebyshev(pos, (tx, ty))
        if dist < best_dist:
            best_dist = dist
            best = totem
    return best


def _tile_inside_totem_radius(
    tile: tuple[int, int],
    totem: dict,
) -> bool:
    """Check whether *tile* is within the healing totem's effect radius."""
    tx, ty = totem.get("x", 0), totem.get("y", 0)
    radius = totem.get("effect_radius", 2)
    return _chebyshev(tile, (tx, ty)) <= radius


# ---------------------------------------------------------------------------
# Phase 26D: Totem-Biased Movement Helper
# ---------------------------------------------------------------------------
# Threshold: AI will prefer totem proximity when hurt below this % HP.
_TOTEM_DRIFT_HP_THRESHOLD = 0.80

def _totem_biased_step(
    ai_pos: tuple[int, int],
    next_step: tuple[int, int],
    move_target: tuple[int, int],
    match_state,
    team: str,
    hp_ratio: float,
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
) -> tuple[int, int]:
    """Nudge a planned movement step toward a healing totem when hurt.

    When the AI is below ``_TOTEM_DRIFT_HP_THRESHOLD`` and there is an
    active healing totem nearby, check whether an alternative adjacent
    tile is both:
      (a) inside the totem's effect radius, AND
      (b) does not increase distance to the move target compared to
          staying at the current position (i.e. no net progress loss).

    If such a tile exists, return it instead.  Otherwise return the
    original *next_step* unchanged.

    This creates a gentle *drift* toward the totem zone during normal
    combat without overriding the AI's primary goal.

    Phase 26D: Totem Awareness — soft combat positioning.
    """
    if hp_ratio >= _TOTEM_DRIFT_HP_THRESHOLD:
        return next_step  # Healthy enough — no bias needed

    totem = _find_nearest_healing_totem(match_state, team, ai_pos)
    if totem is None:
        return next_step  # No totem to drift toward

    # Already inside the totem radius — no need to change anything
    if _tile_inside_totem_radius(ai_pos, totem):
        return next_step

    # If the planned step already lands us in the totem, great
    if _tile_inside_totem_radius(next_step, totem):
        return next_step

    # Look for an alternative neighbor inside the totem that doesn't lose
    # progress toward the target.
    current_target_dist = _chebyshev(ai_pos, move_target)
    totem_pos = (totem["x"], totem["y"])
    best_alt: tuple[int, int] | None = None
    best_totem_dist = 999

    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = ai_pos[0] + dx, ai_pos[1] + dy
            if not (0 <= nx < grid_width and 0 <= ny < grid_height):
                continue
            if (nx, ny) in obstacles or (nx, ny) in occupied:
                continue
            # Must not lose net progress toward target
            if _chebyshev((nx, ny), move_target) > current_target_dist:
                continue
            td = _chebyshev((nx, ny), totem_pos)
            if td <= totem.get("effect_radius", 2) and td < best_totem_dist:
                best_totem_dist = td
                best_alt = (nx, ny)

    return best_alt if best_alt is not None else next_step


# ---------------------------------------------------------------------------
# Door Interaction Helper (Phase 7D-1)
# ---------------------------------------------------------------------------

def _maybe_interact_door(
    ai: PlayerState,
    next_step: tuple[int, int],
    door_tiles: set[tuple[int, int]] | None,
) -> PlayerAction | None:
    """Check if the AI's planned next step is a closed door.

    If adjacent (Chebyshev) to a closed door that's on the path, return
    INTERACT instead of MOVE.  Next tick the door will be open and A*
    will path through normally.

    Only hero allies should call this — enemy AI must NOT open doors.

    Args:
        ai: The AI unit considering the move.
        next_step: The (x, y) tile that A* says to step onto next.
        door_tiles: Set of closed-door positions (or None if no doors).

    Returns:
        A PlayerAction(INTERACT) if the next step is a closed door and
        the AI is adjacent to it, otherwise None (caller should proceed
        with the original MOVE action).
    """
    if not door_tiles or next_step not in door_tiles:
        return None

    ai_pos = (ai.position.x, ai.position.y)
    if _chebyshev(ai_pos, next_step) == 1:
        return PlayerAction(
            player_id=ai.player_id,
            action_type=ActionType.INTERACT,
            target_x=next_step[0],
            target_y=next_step[1],
        )
    return None


# ---------------------------------------------------------------------------
# Phase 8K: AI Retreat Helpers
# ---------------------------------------------------------------------------

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

    # Phase 22D: sustain_dps (Blood Knight) — custom retreat logic.
    # Blood Knight only retreats when ALL sustain is exhausted:
    # HP < 20% AND both Blood Frenzy and Blood Strike on cooldown.
    # This prevents retreating when lifesteal skills could save them.
    if role == "sustain_dps":
        blood_frenzy_cd = ai.cooldowns.get("blood_frenzy", 0)
        blood_strike_cd = ai.cooldowns.get("blood_strike", 0)
        if blood_frenzy_cd <= 0 or blood_strike_cd <= 0:
            return False  # Still has sustain available — fight on

    # Phase 25 fix: retaliation_tank (Revenant) — never retreat while cheat_death
    # buff is active. Undying Will is the safety net that emboldens aggression;
    # retreating with cheat_death up wastes the buff and undermines the design.
    if role == "retaliation_tank":
        has_cheat_death = any(
            b.get("stat") == "cheat_death" for b in ai.active_buffs
        )
        if has_cheat_death:
            return False  # Cheat death active — stand and fight

    # Must be in active danger (enemy within 2 tiles)
    ai_pos = (ai.position.x, ai.position.y)
    in_danger = any(
        _chebyshev(ai_pos, (e.position.x, e.position.y)) <= 2
        for e in enemies
    )

    return in_danger


def _find_retreat_destination(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    door_tiles: set[tuple[int, int]] | None = None,
    match_state=None,
) -> PlayerAction | None:
    """Find the best retreat action for a low-HP hero ally.

    Retreat target priority:
      1. Move toward alive support ally (Confessor) — they can heal us
      1.5. Move toward an active healing totem (Phase 26D — Totem Awareness)
      2. Move toward owner (human player) — safety in numbers
      3. Move away from nearest enemy — generic flee

    For each target, uses A* pathfinding (door-aware) and returns a MOVE
    action toward the first step of the path to the retreat destination.

    Returns MOVE action, or None if completely stuck (cornered, surrounded).
    """
    ai_id = ai.player_id
    ai_pos = (ai.position.x, ai.position.y)

    # --- Priority 1: Move toward alive support ally within 8 tiles ---
    best_support: PlayerState | None = None
    best_support_dist = 999
    for unit in all_units.values():
        if not unit.is_alive or unit.player_id == ai.player_id:
            continue
        if unit.team != ai.team:
            continue
        unit_role = _get_role_for_class(unit.class_id) if unit.class_id else None
        if unit_role != "support":
            continue
        dist = _chebyshev(ai_pos, (unit.position.x, unit.position.y))
        if dist <= 8 and dist < best_support_dist:
            best_support = unit
            best_support_dist = dist

    if best_support:
        # Already adjacent to support — no need to move closer
        if best_support_dist <= 1:
            pass  # Fall through to totem / owner / generic flee
        else:
            support_pos = (best_support.position.x, best_support.position.y)
            next_step = get_next_step_toward(
                ai_pos, support_pos,
                grid_width, grid_height, obstacles, occupied,
                door_tiles,
            )
            if next_step:
                door_action = _maybe_interact_door(ai, next_step, door_tiles)
                if door_action:
                    return door_action
                return PlayerAction(
                    player_id=ai_id,
                    action_type=ActionType.MOVE,
                    target_x=next_step[0],
                    target_y=next_step[1],
                )

    # --- Priority 1.5: Move toward an active healing totem (Phase 26D) ---
    # Healing totems are stationary ground heal zones. If one exists on our
    # team, retreat into its radius so we passively receive healing each turn.
    # This is preferred over running to the owner because the totem actively
    # heals; it slots between "path to support" and "path to owner".
    totem = _find_nearest_healing_totem(match_state, ai.team, ai_pos)
    if totem:
        totem_pos = (totem["x"], totem["y"])
        totem_radius = totem.get("effect_radius", 2)
        # Already inside the totem's heal zone — no need to reposition
        if _chebyshev(ai_pos, totem_pos) <= totem_radius:
            pass  # Fall through — we're already being healed
        else:
            # Path toward the totem center (getting within radius is enough)
            next_step = get_next_step_toward(
                ai_pos, totem_pos,
                grid_width, grid_height, obstacles, occupied,
                door_tiles,
            )
            if next_step:
                door_action = _maybe_interact_door(ai, next_step, door_tiles)
                if door_action:
                    return door_action
                return PlayerAction(
                    player_id=ai_id,
                    action_type=ActionType.MOVE,
                    target_x=next_step[0],
                    target_y=next_step[1],
                )

    # --- Priority 2: Move toward owner ---
    owner = _find_owner(ai, all_units)
    if owner:
        owner_pos = (owner.position.x, owner.position.y)
        owner_dist = _chebyshev(ai_pos, owner_pos)
        if owner_dist > 1:
            next_step = get_next_step_toward(
                ai_pos, owner_pos,
                grid_width, grid_height, obstacles, occupied,
                door_tiles,
            )
            if next_step:
                door_action = _maybe_interact_door(ai, next_step, door_tiles)
                if door_action:
                    return door_action
                return PlayerAction(
                    player_id=ai_id,
                    action_type=ActionType.MOVE,
                    target_x=next_step[0],
                    target_y=next_step[1],
                )

    # --- Priority 3: Generic flee — move away from nearest enemy ---
    if enemies:
        nearest_enemy = min(
            enemies,
            key=lambda e: _chebyshev(ai_pos, (e.position.x, e.position.y)),
        )
        nearest_pos = (nearest_enemy.position.x, nearest_enemy.position.y)
        # Import _find_retreat_tile from ai_behavior (it stays there)
        from app.core.ai_behavior import _find_retreat_tile
        retreat_tile = _find_retreat_tile(
            ai_pos, nearest_pos,
            grid_width, grid_height, obstacles, occupied,
        )
        if retreat_tile:
            door_action = _maybe_interact_door(ai, retreat_tile, door_tiles)
            if door_action:
                return door_action
            return PlayerAction(
                player_id=ai_id,
                action_type=ActionType.MOVE,
                target_x=retreat_tile[0],
                target_y=retreat_tile[1],
            )

    # Completely stuck — cornered, surrounded. Return None so caller
    # falls through to skill/combat.
    return None


# ---------------------------------------------------------------------------
# Phase 8A: AI Potion Usage Helper
# ---------------------------------------------------------------------------

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
        hp_threshold: HP fraction at or below which AI will drink (default 0.40 = 40%).

    Returns:
        PlayerAction(USE_ITEM) with target_x = inventory index, or None.
    """
    if not ai.is_alive:
        return None

    # Don't drink at full HP
    if ai.hp >= ai.max_hp:
        return None

    # Check HP threshold
    if ai.max_hp <= 0:
        return None
    if ai.hp / ai.max_hp > hp_threshold:
        return None

    # Scan inventory for heal consumables
    heal_candidates: list[tuple[int, int]] = []  # (inventory_index, magnitude)
    for idx, item in enumerate(ai.inventory):
        if not isinstance(item, dict):
            continue
        if item.get("item_type") != "consumable":
            continue
        effect = item.get("consumable_effect")
        if not effect or not isinstance(effect, dict):
            continue
        if effect.get("type") != "heal":
            continue
        magnitude = effect.get("magnitude", 0)
        heal_candidates.append((idx, magnitude))

    if not heal_candidates:
        return None

    # Sort by magnitude descending — prefer greater_health_potion (75) over health_potion (40)
    heal_candidates.sort(key=lambda c: c[1], reverse=True)
    best_index = heal_candidates[0][0]

    return PlayerAction(
        player_id=ai.player_id,
        action_type=ActionType.USE_ITEM,
        target_x=best_index,
    )


# ---------------------------------------------------------------------------
# Phase 7C: Stance-Based AI Behavior Dispatch
# ---------------------------------------------------------------------------

def _decide_stance_action(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    team_fov: set[tuple[int, int]] | None = None,
    match_id: str | None = None,
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    door_tiles: set[tuple[int, int]] | None = None,
    portal: dict | None = None,
    match_state=None,
) -> PlayerAction | None:
    """Dispatch to the correct stance handler for hero allies (Phase 7C).

    Stances:
      - follow (default): stay close to owner, fight nearby enemies, regroup
      - aggressive: fight enemies freely, roam within 5 tiles of owner
      - defensive: stay within 2 tiles of owner, only attack nearby enemies
      - hold: never move, only attack enemies in range from current position

    Phase 8A: Potion check runs FIRST — survival takes priority over everything.
    Phase 8B: Skill decision runs SECOND — role-appropriate skills before basic attacks.
    Phase 12C: Portal retreat runs SECOND (after potions) — when portal is active,
               hero allies pathfind to the portal tile and queue INTERACT to extract.
    """
    stance = ai.ai_stance or "follow"

    # --- Phase 8A: Potion check (highest priority) ---
    threshold = _POTION_THRESHOLDS.get(stance, 0.40)
    potion_action = _should_use_potion(ai, hp_threshold=threshold)
    if potion_action:
        return potion_action

    # --- Phase 12C: Portal retreat (second priority — after potions) ---
    # When a portal is active, hero allies override all other behavior to
    # pathfind to the portal tile and extract. This ensures the party auto-
    # evacuates without requiring the player to manually control each hero.
    if portal and portal.get("active"):
        portal_x, portal_y = portal["x"], portal["y"]
        ai_x, ai_y = ai.position.x, ai.position.y

        if ai_x == portal_x and ai_y == portal_y:
            # Already on the portal tile — send INTERACT to enter portal
            # (turn_resolver._resolve_extractions handles the actual extraction)
            return PlayerAction(
                player_id=ai.player_id,
                action_type=ActionType.INTERACT,
                target_id="enter_portal",
            )

        # Not on portal — pathfind toward it
        # Phase 2 (Friendly Swap): allow_team_swap so AI can path through allies to reach portal
        occupied = _build_occupied_set(all_units, ai.player_id, pending_moves, allow_team_swap=ai.team)
        # Remove the portal tile from occupied so we can path onto it
        occupied.discard((portal_x, portal_y))
        step = get_next_step_toward(
            (ai_x, ai_y), (portal_x, portal_y),
            grid_width, grid_height, obstacles, occupied,
            door_tiles=door_tiles,
        )
        if step:
            sx, sy = step
            # If the step is a door tile, interact with the door first
            if door_tiles and (sx, sy) in door_tiles:
                door_action = _maybe_interact_door(ai, (sx, sy), door_tiles)
                if door_action:
                    return door_action
            return PlayerAction(
                player_id=ai.player_id,
                action_type=ActionType.MOVE,
                target_x=sx,
                target_y=sy,
            )
        # If pathfinding failed (blocked), fall through to normal behavior
        # so the hero still fights instead of standing still

    # --- Phase 8B: Pre-compute visible enemies for skill decision ---
    ai_pos = (ai.position.x, ai.position.y)
    own_fov = compute_fov(
        ai.position.x, ai.position.y, ai.vision_range,
        grid_width, grid_height, obstacles,
    )
    visible_tiles = (own_fov | team_fov) if team_fov else own_fov

    pre_enemies: list[PlayerState] = []
    for unit in all_units.values():
        if not unit.is_alive or unit.player_id == ai.player_id or unit.team == ai.team:
            continue
        if (unit.position.x, unit.position.y) in visible_tiles:
            pre_enemies.append(unit)

    # --- Phase 8K-2b: Pre-compute occupied set (shared by retreat + stance handlers) ---
    # Phase 2 (Friendly Swap): Hero AI uses allow_team_swap so A* can plan paths
    # through same-team allies.  Hold stance is excluded (dispatched separately below
    # and never moves, so swap pathfinding is irrelevant).
    occupied = _build_occupied_set(all_units, ai.player_id, pending_moves, allow_team_swap=ai.team)

    # --- Phase 8K-2a: Retreat check (second priority — after potions, before skills) ---
    if _should_retreat(ai, pre_enemies):
        retreat_action = _find_retreat_destination(
            ai, pre_enemies, all_units,
            grid_width, grid_height, obstacles,
            occupied, door_tiles,
            match_state=match_state,
        )
        if retreat_action:
            return retreat_action
        # If retreat failed (cornered), fall through to skills/combat
        # — fighting is better than doing nothing when you can't escape

    # --- Phase 8B: Skill decision (third priority) ---
    skill_action = _decide_skill_usage(
        ai, pre_enemies, all_units, grid_width, grid_height, obstacles,
        match_state=match_state,
    )
    if skill_action:
        return skill_action

    # --- Stance dispatch (pass pre-computed FOV + enemies + occupied to avoid redundant computation) ---
    if stance == "hold":
        return _decide_hold_action(ai, all_units, grid_width, grid_height, obstacles, team_fov, match_id, pending_moves, precomputed_visible_tiles=visible_tiles, precomputed_enemies=pre_enemies)
    elif stance == "defensive":
        return _decide_defensive_action(ai, all_units, grid_width, grid_height, obstacles, team_fov, match_id, pending_moves, door_tiles, precomputed_visible_tiles=visible_tiles, precomputed_enemies=pre_enemies, precomputed_occupied=occupied)
    elif stance == "aggressive":
        return _decide_aggressive_stance_action(ai, all_units, grid_width, grid_height, obstacles, team_fov, match_id, pending_moves, door_tiles, precomputed_visible_tiles=visible_tiles, precomputed_enemies=pre_enemies, precomputed_occupied=occupied, match_state=match_state)
    else:
        # "follow" or unknown → follow behavior
        return _decide_follow_action(ai, all_units, grid_width, grid_height, obstacles, team_fov, match_id, pending_moves, door_tiles, precomputed_visible_tiles=visible_tiles, precomputed_enemies=pre_enemies, precomputed_occupied=occupied, match_state=match_state)


# ---------------------------------------------------------------------------
# Follow Stance (Phase 7C — Default)
# ---------------------------------------------------------------------------

def _decide_follow_action(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    team_fov: set[tuple[int, int]] | None = None,
    match_id: str | None = None,
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    door_tiles: set[tuple[int, int]] | None = None,
    precomputed_visible_tiles: set[tuple[int, int]] | None = None,
    precomputed_enemies: list[PlayerState] | None = None,
    precomputed_occupied: set[tuple[int, int]] | None = None,
    match_state=None,
) -> PlayerAction | None:
    """Follow stance: stay close to owner, fight nearby enemies, regroup after combat.

    Behavior:
      1. If distance to owner > 4: break off combat and move toward owner (regroup)
      2. If distance to owner > 2 and no enemies visible: path toward owner
      3. If enemies visible and within 2 tiles of owner: fight normally (aggressive)
      4. If close enough and no enemies: wait

    Phase 7D-1: Uses door-aware A* so hero allies can path through closed doors
    to follow their owner across rooms.  When the next step in the path is a
    closed door tile, returns INTERACT instead of MOVE (the door opens, and
    next tick A* resumes the path normally).

    Phase 8F-2: Accepts pre-computed visible_tiles and enemies from
    _decide_stance_action() to avoid redundant FOV computation.
    """
    ai_id = ai.player_id
    ai_pos = (ai.position.x, ai.position.y)
    config = get_combat_config()
    ranged_range = getattr(ai, 'ranged_range', config.get("ranged_range", 5))

    owner = _find_owner(ai, all_units)
    if not owner:
        # No owner found — fall back to wait
        return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)

    owner_pos = (owner.position.x, owner.position.y)
    dist_to_owner = _chebyshev(ai_pos, owner_pos)

    # Use pre-computed FOV + enemies if available (Phase 8F-2), else compute
    if precomputed_visible_tiles is not None and precomputed_enemies is not None:
        visible_tiles = precomputed_visible_tiles
        enemies = list(precomputed_enemies)
    else:
        own_fov = compute_fov(
            ai.position.x, ai.position.y, ai.vision_range,
            grid_width, grid_height, obstacles,
        )
        visible_tiles = (own_fov | team_fov) if team_fov else own_fov

        enemies: list[PlayerState] = []
        for unit in all_units.values():
            if not unit.is_alive or unit.player_id == ai_id or unit.team == ai.team:
                continue
            if (unit.position.x, unit.position.y) in visible_tiles:
                enemies.append(unit)

    _update_enemy_memory(ai_id, enemies, all_units)
    # Phase 8K-2b: Reuse pre-computed occupied set if available
    occupied = precomputed_occupied if precomputed_occupied is not None else _build_occupied_set(all_units, ai_id, pending_moves)

    # Priority 1: If too far from owner, regroup even during combat.
    # Phase 22D: sustain_dps (Blood Knight) gets a wider leash (6 tiles)
    # because they need to commit to melee and shouldn't keep regrouping
    # mid-fight. Phase 25 fix: retaliation_tank (Revenant) also gets 6-tile
    # leash — needs to stay engaged in melee to maximize thorns retaliation.
    # Other roles use 4 tiles.
    role = _get_role_for_class(ai.class_id) if ai.class_id else None
    follow_leash = 6 if role in ("sustain_dps", "retaliation_tank") else 4
    if dist_to_owner > follow_leash:
        _patrol_targets.pop(ai_id, None)
        next_step = get_next_step_toward(
            ai_pos, owner_pos, grid_width, grid_height, obstacles, occupied, door_tiles,
        )
        if next_step:
            # Phase 7D-1: If next step is a closed door, INTERACT instead of MOVE
            door_action = _maybe_interact_door(ai, next_step, door_tiles)
            if door_action:
                return door_action
            return PlayerAction(
                player_id=ai_id, action_type=ActionType.MOVE,
                target_x=next_step[0], target_y=next_step[1],
            )
        return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)

    # Priority 2: If enemies visible and close to owner, fight
    if enemies:
        _patrol_targets.pop(ai_id, None)
        target = _pick_best_target(ai, enemies, all_units)
        target_pos = Position(x=target.position.x, y=target.position.y)

        # --- Phase 8C: Support role positioning modifier ---
        # Support units prefer moving toward allies instead of charging enemies.
        # If no one needs healing (skill check already returned None), stay grouped.
        role = _get_role_for_class(ai.class_id) if ai.class_id else None
        # Phase 21D: offensive_support (Bard) also stays near allies.
        # Phase 23 fix: controller (Plague Doctor) stays near allies — midline caster, not a charger.
        # Phase 26 fix: totemic_support (Shaman) stays near allies — backline support.
        is_support = role in ("support", "offensive_support", "controller", "totemic_support") if role else False
        # Phase 23 fix: controller (Plague Doctor) kites like ranged — 85 HP, range 5, should never be in melee.
        # Phase 26 fix: totemic_support (Shaman) also kites — backline support class.
        # Bard fix: offensive_support should kite — 90 HP / 3 armor, ranged_range 4, dies fast in melee.
        is_ranged_role = role in ("ranged_dps", "scout", "caster_dps", "controller", "totemic_support", "offensive_support") if role else False

        dist_to_target = _chebyshev(ai_pos, (target.position.x, target.position.y))
        ranged_cd = ai.cooldowns.get("ranged_attack", 0)

        # --- Phase 8K-3: Ranged kiting (Phase 26D: totem-biased) ---
        # Ranged roles (Ranger, Inquisitor, Mage, Plague Doctor, Shaman) step back
        # when too close to enemy instead of staying in melee. Kiting preserves ranged advantage.
        # Phase 26D: When kiting, prefer stepping toward a healing totem's radius.
        # Fix 2: Controller (Plague Doctor) kites at dist <= 3 — range 5 caster should
        # start backing off sooner than dist 2 to maintain midline positioning.
        # Shaman only kites when adjacent (dist 1) — needs to stay close to
        # frontline for totem placement.  Other ranged roles kite at dist 2-3.
        _kite_threshold = 3 if role == "controller" else (1 if role == "totemic_support" else 2)
        if is_ranged_role and dist_to_target <= _kite_threshold:
            from app.core.ai_behavior import _find_retreat_tile
            # Phase 21E-2: Bard ally-proximity kiting — when retreating,
            # prefer tiles that stay near the ally centroid so buff auras
            # maintain coverage (mirrors ai_behavior.py logic).
            ally_positions = None
            if role == "offensive_support":
                ally_positions = [
                    (u.position.x, u.position.y)
                    for u in all_units.values()
                    if u.is_alive and u.team == ai.team and u.player_id != ai.player_id
                ]
            retreat_tile = _find_retreat_tile(
                ai_pos, (target.position.x, target.position.y),
                grid_width, grid_height, obstacles, occupied,
                ally_positions=ally_positions,
            )
            # Phase 26D: Totem-biased kiting — among valid retreat tiles,
            # prefer one inside (or closer to) a healing totem's radius.
            totem = _find_nearest_healing_totem(match_state, ai.team, ai_pos) if match_state else None
            if retreat_tile and totem:
                totem_pos = (totem["x"], totem["y"])
                best_tile = retreat_tile
                best_score = -_chebyshev(retreat_tile, totem_pos)
                # Rescan neighbors for a tile that is both safe AND closer to totem
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = ai_pos[0] + dx, ai_pos[1] + dy
                        if not (0 <= nx < grid_width and 0 <= ny < grid_height):
                            continue
                        if (nx, ny) in obstacles or (nx, ny) in occupied:
                            continue
                        threat_dist = _chebyshev((nx, ny), (target.position.x, target.position.y))
                        if threat_dist <= 1:
                            continue  # Don't step into melee range
                        totem_dist = _chebyshev((nx, ny), totem_pos)
                        # Score: distance from threat + bonus for being near/inside totem
                        score = threat_dist + (_TOTEM_KITE_BIAS_WEIGHT if totem_dist <= totem.get("effect_radius", 2) else -totem_dist)
                        if score > best_score:
                            best_score = score
                            best_tile = (nx, ny)
                return PlayerAction(
                    player_id=ai_id, action_type=ActionType.MOVE,
                    target_x=best_tile[0], target_y=best_tile[1],
                )
            if retreat_tile:
                return PlayerAction(
                    player_id=ai_id, action_type=ActionType.MOVE,
                    target_x=retreat_tile[0], target_y=retreat_tile[1],
                )
            # Can't step back — fall through to melee as last resort

        # Adjacent → melee (even support attacks if next to enemy w/ nothing to heal)
        if is_adjacent(ai.position, target_pos):
            return PlayerAction(
                player_id=ai_id, action_type=ActionType.ATTACK,
                target_x=target.position.x, target_y=target.position.y,
            )

        if is_support:
            # Each support role has its own positioning logic:
            # - Shaman: stay near frontline tank for totem coverage
            # - Bard: move toward ally centroid for maximum Ballad coverage
            # - Confessor/others: chase nearest or most injured ally
            if role == "totemic_support":
                from app.core.ai_skills import _totemic_support_move_preference
                ally_target = _totemic_support_move_preference(ai, all_units, match_state=match_state)
            elif role == "offensive_support":
                ally_target = _offensive_support_move_preference(ai, all_units)
            else:
                ally_target = _support_move_preference(ai, all_units)
            if ally_target:
                move_target = ally_target
            else:
                move_target = (target.position.x, target.position.y)
        else:
            move_target = (target.position.x, target.position.y)

        # Close enough to rush → melee (non-support, non-ranged only)
        if not is_support and not is_ranged_role and dist_to_target <= 3:
            next_step = get_next_step_toward(
                ai_pos, (target.position.x, target.position.y),
                grid_width, grid_height, obstacles, occupied, door_tiles,
            )
            if next_step:
                door_action = _maybe_interact_door(ai, next_step, door_tiles)
                if door_action:
                    return door_action
                return PlayerAction(
                    player_id=ai_id, action_type=ActionType.MOVE,
                    target_x=next_step[0], target_y=next_step[1],
                )

        # Ranged attack if available
        if ranged_cd == 0 and is_in_range(ai.position, target_pos, ranged_range):
            if has_line_of_sight(
                ai.position.x, ai.position.y,
                target.position.x, target.position.y, obstacles,
            ):
                return PlayerAction(
                    player_id=ai_id, action_type=ActionType.RANGED_ATTACK,
                    target_x=target.position.x, target_y=target.position.y,
                )

        # Fix 2: Controller hold-position — when skills and ranged are on CD,
        # the Plague Doctor should NOT walk toward frontline allies.  Holding
        # position preserves the range advantage, preventing the slow creep
        # into melee that occurs across several "idle" turns between cooldowns.
        # Only advance toward allies when enemies are far enough away (> 4 tiles)
        # that forward movement won't bring us into danger.
        if role == "controller" and ranged_cd > 0:
            nearest_enemy_dist = min(
                (_chebyshev(ai_pos, (e.position.x, e.position.y)) for e in enemies),
                default=999,
            )
            if nearest_enemy_dist <= 4:
                # Enemies within medium range — hold position, don't advance
                return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)

        # Move toward target (support: toward ally; others: toward enemy)
        next_step = get_next_step_toward(
            ai_pos, move_target,
            grid_width, grid_height, obstacles, occupied, door_tiles,
        )
        if next_step:
            # Phase 26D: Soft drift toward healing totem when hurt
            if match_state and ai.max_hp > 0:
                next_step = _totem_biased_step(
                    ai_pos, next_step, move_target, match_state, ai.team,
                    ai.hp / ai.max_hp, grid_width, grid_height, obstacles, occupied,
                )
            door_action = _maybe_interact_door(ai, next_step, door_tiles)
            if door_action:
                return door_action
            return PlayerAction(
                player_id=ai_id, action_type=ActionType.MOVE,
                target_x=next_step[0], target_y=next_step[1],
            )

        return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)

    # Priority 3: No enemies — if too far from owner (>2), path toward them
    if dist_to_owner > 2:
        next_step = get_next_step_toward(
            ai_pos, owner_pos, grid_width, grid_height, obstacles, occupied, door_tiles,
        )
        if next_step:
            door_action = _maybe_interact_door(ai, next_step, door_tiles)
            if door_action:
                return door_action
            return PlayerAction(
                player_id=ai_id, action_type=ActionType.MOVE,
                target_x=next_step[0], target_y=next_step[1],
            )

    # Close enough, no enemies — wait
    return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)


# ---------------------------------------------------------------------------
# Aggressive Stance (Phase 7C)
# ---------------------------------------------------------------------------

def _decide_aggressive_stance_action(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    team_fov: set[tuple[int, int]] | None = None,
    match_id: str | None = None,
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    door_tiles: set[tuple[int, int]] | None = None,
    precomputed_visible_tiles: set[tuple[int, int]] | None = None,
    precomputed_enemies: list[PlayerState] | None = None,
    precomputed_occupied: set[tuple[int, int]] | None = None,
    match_state=None,
) -> PlayerAction | None:
    """Aggressive stance: pursue enemies freely within 5 tiles of owner.

    Behavior:
      1. If enemies visible: fight aggressively (standard combat AI)
      2. No enemies: if within 5 tiles of owner, roam seeking enemies (reinforce allies)
      3. If > 5 tiles from owner: path back toward owner

    Phase 7D-1: Uses door-aware A* so hero allies can path through closed doors.

    Phase 8F-2: Accepts pre-computed visible_tiles and enemies from
    _decide_stance_action() to avoid redundant FOV computation.
    """
    ai_id = ai.player_id
    ai_pos = (ai.position.x, ai.position.y)
    config = get_combat_config()
    ranged_range = getattr(ai, 'ranged_range', config.get("ranged_range", 5))

    owner = _find_owner(ai, all_units)
    owner_pos = (owner.position.x, owner.position.y) if owner else ai_pos

    # Use pre-computed FOV + enemies if available (Phase 8F-2), else compute
    if precomputed_visible_tiles is not None and precomputed_enemies is not None:
        enemies = list(precomputed_enemies)
    else:
        own_fov = compute_fov(
            ai.position.x, ai.position.y, ai.vision_range,
            grid_width, grid_height, obstacles,
        )
        visible_tiles = (own_fov | team_fov) if team_fov else own_fov

        enemies: list[PlayerState] = []
        for unit in all_units.values():
            if not unit.is_alive or unit.player_id == ai_id or unit.team == ai.team:
                continue
            if (unit.position.x, unit.position.y) in visible_tiles:
                enemies.append(unit)

    _update_enemy_memory(ai_id, enemies, all_units)
    # Phase 8K-2b: Reuse pre-computed occupied set if available
    occupied = precomputed_occupied if precomputed_occupied is not None else _build_occupied_set(all_units, ai_id, pending_moves)

    dist_to_owner = _chebyshev(ai_pos, owner_pos) if owner else 0

    # If enemies visible, fight aggressively
    if enemies:
        _patrol_targets.pop(ai_id, None)
        target = _pick_best_target(ai, enemies, all_units)
        target_pos = Position(x=target.position.x, y=target.position.y)

        dist_to_target = _chebyshev(ai_pos, (target.position.x, target.position.y))
        ranged_cd = ai.cooldowns.get("ranged_attack", 0)
        role = _get_role_for_class(ai.class_id) if ai.class_id else None
        # Phase 23 fix: controller (Plague Doctor) kites like ranged — should never rush melee.
        # Phase 26 fix: totemic_support (Shaman) also kites — backline support class.
        is_ranged_role = role in ("ranged_dps", "scout", "caster_dps", "controller", "totemic_support") if role else False

        # --- Phase 8K-3: Ranged kiting (Phase 26D: totem-biased) ---
        # Ranged roles step back when too close to enemy. Kiting preserves ranged advantage.
        # Phase 26D: When kiting, prefer stepping toward a healing totem's radius.
        # Fix 2: Controller (Plague Doctor) kites at dist <= 3 in aggressive stance too.
        # Shaman only kites when adjacent (dist 1) — needs to stay close to
        # frontline for totem placement.
        _kite_threshold = 3 if role == "controller" else (1 if role == "totemic_support" else 2)
        if is_ranged_role and dist_to_target <= _kite_threshold:
            from app.core.ai_behavior import _find_retreat_tile
            retreat_tile = _find_retreat_tile(
                ai_pos, (target.position.x, target.position.y),
                grid_width, grid_height, obstacles, occupied,
            )
            totem = _find_nearest_healing_totem(match_state, ai.team, ai_pos) if match_state else None
            if retreat_tile and totem:
                totem_pos = (totem["x"], totem["y"])
                best_tile = retreat_tile
                best_score = -_chebyshev(retreat_tile, totem_pos)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = ai_pos[0] + dx, ai_pos[1] + dy
                        if not (0 <= nx < grid_width and 0 <= ny < grid_height):
                            continue
                        if (nx, ny) in obstacles or (nx, ny) in occupied:
                            continue
                        threat_dist = _chebyshev((nx, ny), (target.position.x, target.position.y))
                        if threat_dist <= 1:
                            continue
                        totem_dist = _chebyshev((nx, ny), totem_pos)
                        score = threat_dist + (_TOTEM_KITE_BIAS_WEIGHT if totem_dist <= totem.get("effect_radius", 2) else -totem_dist)
                        if score > best_score:
                            best_score = score
                            best_tile = (nx, ny)
                return PlayerAction(
                    player_id=ai_id, action_type=ActionType.MOVE,
                    target_x=best_tile[0], target_y=best_tile[1],
                )
            if retreat_tile:
                return PlayerAction(
                    player_id=ai_id, action_type=ActionType.MOVE,
                    target_x=retreat_tile[0], target_y=retreat_tile[1],
                )
            # Can't step back — fall through to melee as last resort

        # Adjacent → melee
        if is_adjacent(ai.position, target_pos):
            return PlayerAction(
                player_id=ai_id, action_type=ActionType.ATTACK,
                target_x=target.position.x, target_y=target.position.y,
            )

        # Close → rush to melee (non-ranged only)
        if not is_ranged_role and dist_to_target <= 3:
            next_step = get_next_step_toward(
                ai_pos, (target.position.x, target.position.y),
                grid_width, grid_height, obstacles, occupied, door_tiles,
            )
            if next_step:
                door_action = _maybe_interact_door(ai, next_step, door_tiles)
                if door_action:
                    return door_action
                return PlayerAction(
                    player_id=ai_id, action_type=ActionType.MOVE,
                    target_x=next_step[0], target_y=next_step[1],
                )

        # Ranged if available
        if ranged_cd == 0 and is_in_range(ai.position, target_pos, ranged_range):
            if has_line_of_sight(
                ai.position.x, ai.position.y,
                target.position.x, target.position.y, obstacles,
            ):
                return PlayerAction(
                    player_id=ai_id, action_type=ActionType.RANGED_ATTACK,
                    target_x=target.position.x, target_y=target.position.y,
                )

        # Fix 2: Controller hold-position in aggressive stance — same idea as follow stance.
        # Don't walk toward the enemy when skills and ranged are on CD; hold position instead.
        if role == "controller" and ranged_cd > 0:
            nearest_enemy_dist = min(
                (_chebyshev(ai_pos, (e.position.x, e.position.y)) for e in enemies),
                default=999,
            )
            if nearest_enemy_dist <= 4:
                return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)

        # Move toward target
        agg_move_target = (target.position.x, target.position.y)
        next_step = get_next_step_toward(
            ai_pos, agg_move_target,
            grid_width, grid_height, obstacles, occupied, door_tiles,
        )
        if next_step:
            # Phase 26D: Soft drift toward healing totem when hurt
            if match_state and ai.max_hp > 0:
                next_step = _totem_biased_step(
                    ai_pos, next_step, agg_move_target, match_state, ai.team,
                    ai.hp / ai.max_hp, grid_width, grid_height, obstacles, occupied,
                )
            door_action = _maybe_interact_door(ai, next_step, door_tiles)
            if door_action:
                return door_action
            return PlayerAction(
                player_id=ai_id, action_type=ActionType.MOVE,
                target_x=next_step[0], target_y=next_step[1],
            )

        return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)

    # No enemies — check distance to owner
    if dist_to_owner > 5:
        # Too far from owner — path back
        next_step = get_next_step_toward(
            ai_pos, owner_pos, grid_width, grid_height, obstacles, occupied, door_tiles,
        )
        if next_step:
            door_action = _maybe_interact_door(ai, next_step, door_tiles)
            if door_action:
                return door_action
            return PlayerAction(
                player_id=ai_id, action_type=ActionType.MOVE,
                target_x=next_step[0], target_y=next_step[1],
            )

    # Within range — try to reinforce allies or pursue memory
    memory_action = _pursue_memory_target(ai, all_units, grid_width, grid_height, obstacles, pending_moves)
    if memory_action:
        return memory_action

    reinforce = _reinforce_ally(ai, all_units, grid_width, grid_height, obstacles, pending_moves)
    if reinforce:
        return reinforce

    return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)


# ---------------------------------------------------------------------------
# Defensive Stance (Phase 7C)
# ---------------------------------------------------------------------------

def _decide_defensive_action(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    team_fov: set[tuple[int, int]] | None = None,
    match_id: str | None = None,
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    door_tiles: set[tuple[int, int]] | None = None,
    precomputed_visible_tiles: set[tuple[int, int]] | None = None,
    precomputed_enemies: list[PlayerState] | None = None,
    precomputed_occupied: set[tuple[int, int]] | None = None,
) -> PlayerAction | None:
    """Defensive stance: stay within 2 tiles of owner, only attack nearby enemies.

    Behavior:
      1. If distance to owner > 2: path toward owner (prioritize staying close)
      2. If enemies within 2 tiles: attack (melee or ranged if adjacent/close)
      3. Otherwise: wait near owner

    Phase 7D-1: Uses door-aware A* so hero allies can path through closed doors.

    Phase 8F-2: Accepts pre-computed visible_tiles and enemies from
    _decide_stance_action() to avoid redundant FOV computation.
    """
    ai_id = ai.player_id
    ai_pos = (ai.position.x, ai.position.y)
    config = get_combat_config()
    ranged_range = getattr(ai, 'ranged_range', config.get("ranged_range", 5))

    owner = _find_owner(ai, all_units)
    if not owner:
        return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)

    owner_pos = (owner.position.x, owner.position.y)
    dist_to_owner = _chebyshev(ai_pos, owner_pos)

    # Use pre-computed FOV + enemies if available (Phase 8F-2), else compute
    if precomputed_visible_tiles is not None and precomputed_enemies is not None:
        enemies = list(precomputed_enemies)
    else:
        own_fov = compute_fov(
            ai.position.x, ai.position.y, ai.vision_range,
            grid_width, grid_height, obstacles,
        )
        visible_tiles = (own_fov | team_fov) if team_fov else own_fov

        enemies: list[PlayerState] = []
        for unit in all_units.values():
            if not unit.is_alive or unit.player_id == ai_id or unit.team == ai.team:
                continue
            if (unit.position.x, unit.position.y) in visible_tiles:
                enemies.append(unit)

    _update_enemy_memory(ai_id, enemies, all_units)
    # Phase 8K-2b: Reuse pre-computed occupied set if available
    occupied = precomputed_occupied if precomputed_occupied is not None else _build_occupied_set(all_units, ai_id, pending_moves)

    # Priority 1: If too far from owner, move back
    if dist_to_owner > 2:
        next_step = get_next_step_toward(
            ai_pos, owner_pos, grid_width, grid_height, obstacles, occupied, door_tiles,
        )
        if next_step:
            door_action = _maybe_interact_door(ai, next_step, door_tiles)
            if door_action:
                return door_action
            return PlayerAction(
                player_id=ai_id, action_type=ActionType.MOVE,
                target_x=next_step[0], target_y=next_step[1],
            )

    # Priority 2: Only engage enemies within 2 tiles of this unit
    nearby_enemies = [
        e for e in enemies
        if _chebyshev(ai_pos, (e.position.x, e.position.y)) <= 2
    ]

    if nearby_enemies:
        target = _pick_best_target(ai, nearby_enemies, all_units)
        target_pos = Position(x=target.position.x, y=target.position.y)

        # Adjacent → melee
        if is_adjacent(ai.position, target_pos):
            return PlayerAction(
                player_id=ai_id, action_type=ActionType.ATTACK,
                target_x=target.position.x, target_y=target.position.y,
            )

        # Ranged if available and in range
        ranged_cd = ai.cooldowns.get("ranged_attack", 0)
        if ranged_cd == 0 and is_in_range(ai.position, target_pos, ranged_range):
            if has_line_of_sight(
                ai.position.x, ai.position.y,
                target.position.x, target.position.y, obstacles,
            ):
                return PlayerAction(
                    player_id=ai_id, action_type=ActionType.RANGED_ATTACK,
                    target_x=target.position.x, target_y=target.position.y,
                )

        # Move toward nearby enemy (but only if staying within 2 of owner)
        next_step = get_next_step_toward(
            ai_pos, (target.position.x, target.position.y),
            grid_width, grid_height, obstacles, occupied, door_tiles,
        )
        if next_step:
            new_dist = _chebyshev(next_step, owner_pos)
            if new_dist <= 2:
                return PlayerAction(
                    player_id=ai_id, action_type=ActionType.MOVE,
                    target_x=next_step[0], target_y=next_step[1],
                )

    # No nearby threats — wait near owner
    return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)


# ---------------------------------------------------------------------------
# Hold Position Stance (Phase 7C)
# ---------------------------------------------------------------------------

def _decide_hold_action(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    team_fov: set[tuple[int, int]] | None = None,
    match_id: str | None = None,
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
    precomputed_visible_tiles: set[tuple[int, int]] | None = None,
    precomputed_enemies: list[PlayerState] | None = None,
) -> PlayerAction | None:
    """Hold Position stance: never move, attack enemies in range.

    Behavior:
      1. Never moves from current tile
      2. If adjacent enemy: melee attack
      3. If enemy in ranged range + LOS + cooldown ready: ranged attack
      4. Otherwise: wait

    Phase 8F-2: Accepts pre-computed visible_tiles and enemies from
    _decide_stance_action() to avoid redundant FOV computation.
    """
    ai_id = ai.player_id
    config = get_combat_config()
    ranged_range = getattr(ai, 'ranged_range', config.get("ranged_range", 5))

    # Use pre-computed FOV + enemies if available (Phase 8F-2), else compute
    if precomputed_visible_tiles is not None and precomputed_enemies is not None:
        enemies = list(precomputed_enemies)
    else:
        own_fov = compute_fov(
            ai.position.x, ai.position.y, ai.vision_range,
            grid_width, grid_height, obstacles,
        )
        visible_tiles = (own_fov | team_fov) if team_fov else own_fov

        enemies: list[PlayerState] = []
        for unit in all_units.values():
            if not unit.is_alive or unit.player_id == ai_id or unit.team == ai.team:
                continue
            if (unit.position.x, unit.position.y) in visible_tiles:
                enemies.append(unit)

    if not enemies:
        return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)

    # Check for adjacent enemies → melee
    for enemy in enemies:
        target_pos = Position(x=enemy.position.x, y=enemy.position.y)
        if is_adjacent(ai.position, target_pos):
            return PlayerAction(
                player_id=ai_id, action_type=ActionType.ATTACK,
                target_x=enemy.position.x, target_y=enemy.position.y,
            )

    # Check for ranged targets
    ranged_cd = ai.cooldowns.get("ranged_attack", 0)
    if ranged_cd == 0:
        for enemy in enemies:
            target_pos = Position(x=enemy.position.x, y=enemy.position.y)
            if is_in_range(ai.position, target_pos, ranged_range):
                if has_line_of_sight(
                    ai.position.x, ai.position.y,
                    enemy.position.x, enemy.position.y, obstacles,
                ):
                    return PlayerAction(
                        player_id=ai_id, action_type=ActionType.RANGED_ATTACK,
                        target_x=enemy.position.x, target_y=enemy.position.y,
                    )

    # No targets in range — hold position
    return PlayerAction(player_id=ai_id, action_type=ActionType.WAIT)
