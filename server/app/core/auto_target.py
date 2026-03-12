"""
Auto-Target — Persistent auto-target pursuit and skill auto-targeting.

Extracted from match_manager.py during P2 refactoring.
Handles setting/clearing auto-targets, generating chase/attack/skill actions
per tick, and skill range helpers.
"""

from __future__ import annotations

# Shared state dicts — imported from match_manager
from app.core.match_manager import (
    _player_states,
)


def set_auto_target(match_id: str, player_id: str, target_id: str, skill_id: str | None = None) -> bool | str:
    """Set a persistent auto-target for a player, optionally with a skill.

    Validates:
    - Player exists and is alive
    - Target exists and is alive
    - Target is an enemy (different team) — OR ally/self if skill targeting is 'ally_or_self'
    - Player is not targeting themselves (unless skill targeting is 'ally_or_self')

    When skill_id is provided, additional validations:
    - Skill exists in config
    - Player's class can use the skill (cooldown NOT checked — player can approach while cooling)
    - Skill targeting is compatible with target:
        - 'enemy_adjacent' or 'enemy_ranged' → target must be on different team
        - 'ally_or_self' → target must be on same team OR self

    On success, the auto-target is set and will generate actions once the
    player's action queue is empty.  Queue is NOT cleared — if a batch path
    was queued (e.g. right-click), it drains first, then auto-target takes
    over for ongoing pursuit.  (QoL-A change)

    Returns True on success, error string on failure.
    """
    from app.core.skills import get_skill, get_class_skills

    players = _player_states.get(match_id, {})

    player = players.get(player_id)
    if not player or not player.is_alive:
        return "Cannot set auto-target — player not found or dead"

    target = players.get(target_id)
    if not target or not target.is_alive:
        return "Cannot auto-target — target not found or dead"

    # --- Skill validation (Phase 10G) ---
    if skill_id:
        skill_def = get_skill(skill_id)
        if not skill_def:
            return f"Unknown skill: {skill_id}"

        # Check class can use this skill
        allowed = skill_def.get("allowed_classes", [])
        if allowed and player.class_id not in allowed:
            return f"{player.username}'s class ({player.class_id}) cannot use {skill_def['name']}"

        targeting = skill_def.get("targeting", "")

        if targeting == "ally_or_self":
            # Friendly target — must be same team or self
            if player.team != target.team and player_id != target_id:
                return "Cannot use this skill on an enemy"
        elif targeting in ("enemy_adjacent", "enemy_ranged"):
            # Enemy target — must be different team
            if player_id == target_id:
                return "Cannot use this offensive skill on yourself"
            if player.team == target.team:
                return "Cannot use this offensive skill on an ally"
        else:
            # 'self' or 'empty_tile' skills don't use auto-target
            return f"Skill '{skill_def['name']}' does not support auto-targeting"
    else:
        # No skill — melee pursuit (existing behavior)
        if player_id == target_id:
            return "Cannot auto-target yourself"
        if player.team == target.team:
            return "Cannot auto-target an ally on the same team"

    # QoL-A: queue is NOT cleared — let the existing batch path drain first.
    # Auto-target will only generate actions when the queue is empty
    # (tick_loop Step 3.5 skips auto-target if pid already has an action).

    player.auto_target_id = target_id
    player.auto_skill_id = skill_id
    return True


def clear_auto_target(match_id: str, player_id: str) -> None:
    """Clear the auto-target and auto-skill for a player. No-op if not set."""
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if player:
        player.auto_target_id = None
        player.auto_skill_id = None


def get_auto_target(match_id: str, player_id: str) -> str | None:
    """Get the current auto-target_id for a player, or None."""
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if player:
        return player.auto_target_id
    return None


# ---------- Auto-Target Chase Action Generation (Phase 10B / 10G) ----------


def _get_skill_effective_range(skill_def: dict, player: "PlayerState") -> int:
    """Determine the effective range for a skill.

    - 'enemy_adjacent' → 1 (Chebyshev distance)
    - 'enemy_ranged' with range=0 → player.ranged_range (from class config)
    - 'enemy_ranged' with range>0 → skill.range
    - 'ally_or_self' → skill.range (Chebyshev distance)
    """
    targeting = skill_def.get("targeting", "")
    skill_range = skill_def.get("range", 0)

    if targeting == "enemy_adjacent":
        return 1
    elif targeting == "enemy_ranged":
        return player.ranged_range if skill_range == 0 else skill_range
    elif targeting == "ally_or_self":
        return max(skill_range, 1)
    return 1


def _is_in_skill_range(
    player_pos: tuple[int, int],
    target_pos: tuple[int, int],
    effective_range: int,
    targeting_type: str,
) -> bool:
    """Check if player is within skill range of target.

    - 'enemy_adjacent' → Chebyshev distance ≤ 1 (and not same tile)
    - 'enemy_ranged' → Euclidean distance ≤ effective_range
    - 'ally_or_self' → Chebyshev distance ≤ effective_range
    """
    import math

    dx = abs(player_pos[0] - target_pos[0])
    dy = abs(player_pos[1] - target_pos[1])

    if targeting_type == "enemy_adjacent":
        return max(dx, dy) <= 1 and (dx + dy) > 0
    elif targeting_type == "enemy_ranged":
        dist = math.sqrt(dx * dx + dy * dy)
        return dist <= effective_range
    elif targeting_type == "ally_or_self":
        return max(dx, dy) <= effective_range
    return False


def _find_class_auto_attack(player: "PlayerState") -> tuple:
    """Find the class's auto-attack skill (is_auto_attack=True).

    Returns (skill_id, skill_def) or (None, None) if not found.
    """
    from app.core.skills import get_class_skills, get_skill
    if not player.class_id:
        return None, None
    for sid in get_class_skills(player.class_id):
        sdef = get_skill(sid)
        if sdef and sdef.get("is_auto_attack"):
            return sid, sdef
    return None, None


def generate_auto_target_action(
    match_id: str,
    player_id: str,
    all_units: dict[str, "PlayerState"],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    door_tiles: set[tuple[int, int]] | None = None,
) -> "PlayerAction | None":
    """Generate a chase/attack/skill action for a player with an active auto-target.

    Called once per tick for players/party members whose action queue is empty
    but who have an active ``auto_target_id``.  Produces exactly ONE action
    (MOVE, ATTACK, SKILL, WAIT, or INTERACT) — the same granularity as AI behaviour.

    Extended decision logic (Phase 10G):
      1. Validate target (alive, appropriate team based on skill targeting type).
         If invalid → clear auto-target, return None.
      2. If auto_skill_id is set:
         a. Resolve effective range for the skill.
         b. Check if the skill can still be used (class restriction etc.).
            Cooldown is NOT a blocker — player can approach while cooling.
         c. If non-auto-attack skill on cooldown AND in range → fall back to
            class auto-attack (so combat continues between spell casts).
         d. If auto-attack on cooldown AND in range → WAIT (shouldn't happen, cd=0).
         e. If not in range → MOVE toward target (close gap).
         f. If in range AND off cooldown:
            - For skills requiring LOS: check LOS → if blocked, MOVE to reposition.
            - Return SKILL action with target's current coordinates.
         f. If not in range → A* toward target → MOVE one step.
      3. If auto_skill_id is NOT set (existing melee pursuit behavior):
         a. If adjacent → ATTACK.
         b. If not adjacent → MOVE toward target.
      4. If unreachable → clear auto-target, return None.

    Returns:
        A ``PlayerAction`` for this tick, or ``None`` when the auto-target
        was cleared (target dead / unreachable).
    """
    from app.models.actions import PlayerAction, ActionType
    from app.core.ai_behavior import a_star, _build_occupied_set
    from app.core.skills import get_skill, can_use_skill

    player = all_units.get(player_id)
    if not player or not player.is_alive:
        clear_auto_target(match_id, player_id)
        return None

    target_id = player.auto_target_id
    if not target_id:
        return None

    target = all_units.get(target_id)
    auto_skill_id = player.auto_skill_id

    # --- 1. Validate target ---
    if not target or not target.is_alive:
        clear_auto_target(match_id, player_id)
        return None

    # Team validation depends on whether a skill is set and its targeting type
    if auto_skill_id:
        skill_def = get_skill(auto_skill_id)
        if not skill_def:
            # Skill no longer exists — cancel
            clear_auto_target(match_id, player_id)
            return None
        targeting = skill_def.get("targeting", "")

        if targeting == "ally_or_self":
            # Friendly target — must be same team or self
            if target.team != player.team and target_id != player_id:
                clear_auto_target(match_id, player_id)
                return None
        else:
            # Enemy target — must be different team
            if target.team == player.team:
                clear_auto_target(match_id, player_id)
                return None
    else:
        # No skill — melee pursuit, must be enemy (existing behavior)
        if target.team == player.team:
            clear_auto_target(match_id, player_id)
            return None

    player_pos = (player.position.x, player.position.y)
    target_pos = (target.position.x, target.position.y)

    # --- 2. Skill auto-target (Phase 10G) ---
    if auto_skill_id and skill_def:
        # Check if the skill can still be used (ignoring cooldown)
        can_use, reason = can_use_skill(player, auto_skill_id)
        if not can_use:
            cd_remaining = player.cooldowns.get(auto_skill_id, 0)
            if cd_remaining > 0:
                pass  # Just on cooldown — keep approaching or waiting
            else:
                # Genuinely can't use this skill (class restriction, etc.) — cancel
                clear_auto_target(match_id, player_id)
                return None

        effective_range = _get_skill_effective_range(skill_def, player)
        in_range = _is_in_skill_range(player_pos, target_pos, effective_range, targeting)
        on_cooldown = player.cooldowns.get(auto_skill_id, 0) > 0

        if in_range:
            if on_cooldown:
                # Spell on cooldown — fall back to class auto-attack so
                # combat continues between spell casts (auto-attack has cd=0).
                if not skill_def.get("is_auto_attack"):
                    aa_id, aa_def = _find_class_auto_attack(player)
                    if aa_id and aa_def:
                        aa_tgt = aa_def.get("targeting", "")
                        aa_range = _get_skill_effective_range(aa_def, player)
                        if _is_in_skill_range(player_pos, target_pos, aa_range, aa_tgt):
                            # Auto-attack in range → fire it
                            return PlayerAction(
                                player_id=player_id,
                                action_type=ActionType.SKILL,
                                skill_id=aa_id,
                                target_x=target_pos[0],
                                target_y=target_pos[1],
                                target_id=target_id,
                            )
                        else:
                            # In spell range but not auto-attack range → move closer
                            return _generate_move_toward(
                                match_id, player_id, player_pos, target_pos,
                                all_units, grid_width, grid_height, obstacles, door_tiles,
                            )
                # Auto-attack skill itself on cooldown (shouldn't happen, cd=0)
                # or no class auto-attack found → WAIT in position
                return PlayerAction(
                    player_id=player_id,
                    action_type=ActionType.WAIT,
                    target_x=player_pos[0],
                    target_y=player_pos[1],
                )

            # In range and off cooldown → check LOS if required
            if skill_def.get("requires_line_of_sight", False):
                from app.core.fov import has_line_of_sight
                if not has_line_of_sight(
                    player_pos[0], player_pos[1],
                    target_pos[0], target_pos[1],
                    obstacles,
                ):
                    # In range but no LOS — move to reposition
                    return _generate_move_toward(
                        match_id, player_id, player_pos, target_pos,
                        all_units, grid_width, grid_height, obstacles, door_tiles,
                    )

            # Cast the skill!
            return PlayerAction(
                player_id=player_id,
                action_type=ActionType.SKILL,
                skill_id=auto_skill_id,
                target_x=target_pos[0],
                target_y=target_pos[1],
                target_id=target_id,
            )
        else:
            # Not in range → move toward target
            return _generate_move_toward(
                match_id, player_id, player_pos, target_pos,
                all_units, grid_width, grid_height, obstacles, door_tiles,
            )

    # --- 3. No skill — class-aware auto-attack (replaces old melee-only pursuit) ---
    # Look up the class's auto-attack skill and use it if available.
    # This ensures Ranger uses ranged auto-attack, melee classes use melee, etc.
    from app.core.skills import get_class_skills as _get_class_skills, get_skill as _get_skill_def
    auto_attack_skill_id = None
    auto_attack_skill_def = None
    if player.class_id:
        class_skill_ids = _get_class_skills(player.class_id)
        for sid in class_skill_ids:
            sdef = _get_skill_def(sid)
            if sdef and sdef.get("is_auto_attack"):
                auto_attack_skill_id = sid
                auto_attack_skill_def = sdef
                break

    if auto_attack_skill_id and auto_attack_skill_def:
        # Use the skill auto-target path for the class's auto-attack
        aa_targeting = auto_attack_skill_def.get("targeting", "")
        effective_range = _get_skill_effective_range(auto_attack_skill_def, player)
        in_range = _is_in_skill_range(player_pos, target_pos, effective_range, aa_targeting)
        # Auto-attack has 0 cooldown, so no need to check cooldown

        if in_range:
            # In range → check LOS if required
            if auto_attack_skill_def.get("requires_line_of_sight", False):
                from app.core.fov import has_line_of_sight as _has_los
                if not _has_los(
                    player_pos[0], player_pos[1],
                    target_pos[0], target_pos[1],
                    obstacles,
                ):
                    # In range but no LOS — move to reposition
                    return _generate_move_toward(
                        match_id, player_id, player_pos, target_pos,
                        all_units, grid_width, grid_height, obstacles, door_tiles,
                    )

            # Cast the auto-attack skill
            return PlayerAction(
                player_id=player_id,
                action_type=ActionType.SKILL,
                skill_id=auto_attack_skill_id,
                target_x=target_pos[0],
                target_y=target_pos[1],
                target_id=target_id,
            )
        else:
            # Not in range → move toward target
            return _generate_move_toward(
                match_id, player_id, player_pos, target_pos,
                all_units, grid_width, grid_height, obstacles, door_tiles,
            )

    # Fallback: no auto-attack skill found — use legacy melee pursuit
    from app.core.combat import is_adjacent as _is_adj
    from app.models.player import Position as _Pos
    if _is_adj(_Pos(x=player_pos[0], y=player_pos[1]),
               _Pos(x=target_pos[0], y=target_pos[1])):
        return PlayerAction(
            player_id=player_id,
            action_type=ActionType.ATTACK,
            target_x=target_pos[0],
            target_y=target_pos[1],
            target_id=target_id,
        )

    # Not adjacent → move toward target
    return _generate_move_toward(
        match_id, player_id, player_pos, target_pos,
        all_units, grid_width, grid_height, obstacles, door_tiles,
    )


def _generate_move_toward(
    match_id: str,
    player_id: str,
    player_pos: tuple[int, int],
    target_pos: tuple[int, int],
    all_units: dict[str, "PlayerState"],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    door_tiles: set[tuple[int, int]] | None = None,
) -> "PlayerAction | None":
    """A* pathfind toward the target and return a single MOVE or INTERACT action.

    If A* finds no path, clears auto-target and returns None.
    If the next step is a closed door and we're adjacent, returns INTERACT.
    Otherwise returns MOVE one step along the path.
    """
    from app.models.actions import PlayerAction, ActionType
    from app.core.ai_behavior import a_star, _build_occupied_set

    occupied = _build_occupied_set(all_units, player_id)
    path = a_star(
        player_pos,
        target_pos,
        grid_width,
        grid_height,
        obstacles,
        occupied,
        door_tiles=door_tiles,
    )

    if not path:
        # Unreachable — clear auto-target
        clear_auto_target(match_id, player_id)
        return None

    next_step = path[0]

    # If next step is a closed door, interact with it instead of moving
    if door_tiles and next_step in door_tiles:
        dx = abs(player_pos[0] - next_step[0])
        dy = abs(player_pos[1] - next_step[1])
        if max(dx, dy) == 1:
            return PlayerAction(
                player_id=player_id,
                action_type=ActionType.INTERACT,
                target_x=next_step[0],
                target_y=next_step[1],
            )

    # Normal move toward target
    return PlayerAction(
        player_id=player_id,
        action_type=ActionType.MOVE,
        target_x=next_step[0],
        target_y=next_step[1],
    )
