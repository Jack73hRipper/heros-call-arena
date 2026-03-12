"""Miscellaneous utility skill effect handlers."""
from __future__ import annotations

from app.models.player import PlayerState
from app.models.actions import ActionResult, ActionType
from app.core.skill_effects._helpers import _apply_skill_cooldown


def resolve_detection(
    player: PlayerState,
    skill_def: dict,
    players: dict[str, PlayerState],
) -> ActionResult:
    """Resolve a detection skill (e.g., Divine Sense).

    Reveals positions of enemies matching specific creature tags within radius.
    Applies a 'detected' buff to matching enemies so the client can show their positions.
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    detect_radius = effect.get("radius", 12)
    detect_tags = effect.get("detect_tags", ["undead", "demon"])
    reveal_duration = effect.get("duration_turns", 4)

    ai_pos = (player.position.x, player.position.y)
    revealed: list[dict] = []

    for p in players.values():
        if not p.is_alive or p.team == player.team:
            continue
        # Check if enemy has matching tags
        enemy_tags = getattr(p, 'tags', [])
        if not any(tag in enemy_tags for tag in detect_tags):
            continue
        # Check radius (Chebyshev)
        dist = max(abs(p.position.x - ai_pos[0]), abs(p.position.y - ai_pos[1]))
        if dist <= detect_radius:
            # Mark enemy as 'detected' — add a tracking buff readable by FOV
            # Remove existing detect buff first (refresh)
            p.active_buffs = [b for b in p.active_buffs if b.get("buff_id") != f"detected_by_{player.player_id}"]
            detect_entry = {
                "buff_id": f"detected_by_{player.player_id}",
                "type": "detected",
                "source_id": player.player_id,
                "turns_remaining": reveal_duration,
                "stat": None,
                "magnitude": 0,
            }
            p.active_buffs.append(detect_entry)
            revealed.append({
                "player_id": p.player_id,
                "username": p.username,
                "x": p.position.x,
                "y": p.position.y,
                "enemy_type": p.enemy_type,
            })

    _apply_skill_cooldown(player, skill_def)

    if revealed:
        names = ", ".join(r["username"] for r in revealed)
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — revealed {len(revealed)} enemies: {names}",
            buff_applied={"type": "detection", "revealed_count": len(revealed), "revealed": revealed},
        )
    else:
        _apply_skill_cooldown(player, skill_def)  # Still consumes cooldown even if no targets found
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — no Undead or Demons detected nearby",
        )


def resolve_cooldown_reduction(
    player: PlayerState,
    skill_def: dict,
    players: dict[str, PlayerState],
    target_x: int | None = None,
    target_y: int | None = None,
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a cooldown reduction skill targeting an ally or self (e.g., Verse of Haste).

    Targeting: ally_or_self — reduces all active skill cooldowns on the target by N turns.
    Reuses the ally-targeting pattern from resolve_buff.

    Phase 21B: Bard — Verse of Haste (reduce cooldowns by 2).
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    reduction = effect.get("reduction", 2)

    # Determine target (self or ally) — same pattern as resolve_buff
    target = player  # default to self
    targeting = skill_def.get("targeting", "self")

    if targeting in ("ally_or_self", "ally_ranged") and players:
        if target_id:
            candidate = players.get(target_id)
            if candidate and candidate.is_alive and candidate.team == player.team:
                target = candidate
            elif target_id == player.player_id:
                target = player
        elif target_x is not None and target_y is not None:
            if target_x == player.position.x and target_y == player.position.y:
                target = player
            else:
                for p in players.values():
                    if (p.is_alive
                            and p.position.x == target_x
                            and p.position.y == target_y
                            and p.team == player.team):
                        target = p
                        break

        # Range check for ally target
        if target.player_id != player.player_id:
            dx = abs(player.position.x - target.position.x)
            dy = abs(player.position.y - target.position.y)
            skill_range = skill_def.get("range", 3)
            if dx > skill_range or dy > skill_range:
                return ActionResult(
                    player_id=player.player_id, username=player.username,
                    action_type=ActionType.SKILL, skill_id=skill_id, success=False,
                    message=f"{player.username} {skill_def['name']} failed — target out of range",
                )

    # Check target is not an enemy
    if target.team != player.team:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — cannot target enemies",
        )

    # Reduce all active cooldowns on target
    reduced_count = 0
    if hasattr(target, 'cooldowns') and target.cooldowns:
        for cd_skill_id in list(target.cooldowns.keys()):
            remaining = target.cooldowns[cd_skill_id]
            if remaining > 0:
                target.cooldowns[cd_skill_id] = max(0, remaining - reduction)
                reduced_count += 1

    _apply_skill_cooldown(player, skill_def)

    target_name = target.username if target.player_id != player.player_id else "self"
    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} used {skill_def['name']} on {target_name} — reduced {reduced_count} cooldown(s) by {reduction} turn(s)",
        target_id=target.player_id,
        target_username=target.username,
        buff_applied={"type": "cooldown_reduction", "reduction": reduction, "reduced_count": reduced_count},
    )
