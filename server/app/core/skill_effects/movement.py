"""Movement skill effect handlers."""
from __future__ import annotations

from app.models.player import PlayerState
from app.models.actions import ActionResult, ActionType
from app.core.fov import has_line_of_sight
from app.core.skill_effects._helpers import _apply_skill_cooldown


def resolve_teleport(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    grid_width: int,
    grid_height: int,
) -> ActionResult:
    """Resolve a teleport skill (e.g., Shadow Step).

    Targeting: empty_tile. Validates range, LOS, obstacle, occupied.
    """
    skill_id = skill_def["skill_id"]
    skill_range = skill_def["range"]
    requires_los = skill_def.get("requires_line_of_sight", True)

    if target_x is None or target_y is None:
        return ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.SKILL,
            skill_id=skill_id,
            success=False,
            message=f"{player.username} {skill_def['name']} failed — no target specified",
        )

    # Check bounds (skip if grid dimensions not specified)
    if grid_width > 0 and grid_height > 0 and (
        target_x < 0 or target_x >= grid_width or target_y < 0 or target_y >= grid_height
    ):
        return ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.SKILL,
            skill_id=skill_id,
            success=False,
            message=f"{player.username} {skill_def['name']} failed — target out of bounds",
        )

    # Check range (Chebyshev distance for teleport)
    dx = abs(player.position.x - target_x)
    dy = abs(player.position.y - target_y)
    if max(dx, dy) > skill_range:
        return ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.SKILL,
            skill_id=skill_id,
            success=False,
            message=f"{player.username} {skill_def['name']} failed — target out of range",
        )

    # Can't teleport to own position
    if target_x == player.position.x and target_y == player.position.y:
        return ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.SKILL,
            skill_id=skill_id,
            success=False,
            message=f"{player.username} {skill_def['name']} failed — can't teleport to own position",
        )

    # Check obstacle
    if (target_x, target_y) in obstacles:
        return ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.SKILL,
            skill_id=skill_id,
            success=False,
            message=f"{player.username} {skill_def['name']} failed — target tile blocked",
        )

    # Check occupied by another unit
    for p in players.values():
        if p.is_alive and p.player_id != player.player_id:
            if p.position.x == target_x and p.position.y == target_y:
                return ActionResult(
                    player_id=player.player_id,
                    username=player.username,
                    action_type=ActionType.SKILL,
                    skill_id=skill_id,
                    success=False,
                    message=f"{player.username} {skill_def['name']} failed — target tile occupied",
                )

    # Check LOS
    if requires_los:
        if not has_line_of_sight(
            player.position.x, player.position.y,
            target_x, target_y,
            obstacles,
        ):
            return ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.SKILL,
                skill_id=skill_id,
                success=False,
                message=f"{player.username} {skill_def['name']} failed — no line of sight",
            )

    # Execute teleport
    old_x, old_y = player.position.x, player.position.y
    player.position.x = target_x
    player.position.y = target_y
    _apply_skill_cooldown(player, skill_def)

    return ActionResult(
        player_id=player.player_id,
        username=player.username,
        action_type=ActionType.SKILL,
        skill_id=skill_id,
        success=True,
        message=f"{player.username} used {skill_def['name']} — teleported!",
        from_x=old_x,
        from_y=old_y,
        to_x=target_x,
        to_y=target_y,
    )
