"""Summoning / totem / zone skill effect handlers."""
from __future__ import annotations

from app.models.player import PlayerState, Position
from app.models.actions import ActionResult, ActionType
from app.core.fov import has_line_of_sight
from app.core.skill_effects._helpers import _apply_skill_cooldown, _resolve_skill_entity_target


def resolve_place_totem(
    player: PlayerState,
    action,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    match_state=None,
) -> ActionResult:
    """Place a totem on an empty tile. Creates a persistent ground entity.

    Shared handler for Healing Totem, Searing Totem, and Earthgrasp Totem —
    dispatches based on the ``totem_type`` field in the skill effect definition.

    Healing Totem: heals all allies within radius each turn.
    Searing Totem: damages all enemies within radius each turn.
    Earthgrasp Totem: roots all enemies within radius each turn.
    Totems are destructible (have HP). Max 1 of each type per Shaman.

    Phase 26B: Shaman — Healing Totem / Searing Totem.
    Phase 26G: Earthgrasp Totem conversion.
    """
    from app.core.combat import is_in_range
    import uuid

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    totem_type = effect.get("totem_type", "healing")  # "healing" or "searing"
    totem_hp = effect.get("totem_hp", 20)
    heal_per_turn = effect.get("heal_per_turn", 0)
    damage_per_turn = effect.get("damage_per_turn", 0)
    root_duration = effect.get("root_duration", 0)
    effect_radius = effect.get("effect_radius", 2)
    duration_turns = effect.get("duration_turns", 4)
    skill_range = skill_def.get("range", 4)
    requires_los = skill_def.get("requires_line_of_sight", True)

    target_x = getattr(action, "target_x", None)
    target_y = getattr(action, "target_y", None)

    # Validate target tile provided
    if target_x is None or target_y is None:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no target specified",
        )

    # Range check (Chebyshev) from caster to target tile
    target_pos = Position(x=target_x, y=target_y)
    if not is_in_range(player.position, target_pos, skill_range):
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — target out of range",
        )

    # LOS check from caster to target tile
    if requires_los and not has_line_of_sight(
        player.position.x, player.position.y, target_x, target_y, obstacles,
    ):
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no line of sight",
        )

    # Check target tile is not a wall/obstacle
    if (target_x, target_y) in obstacles:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — tile is blocked",
        )

    # Check target tile is not occupied by any alive unit
    for p in players.values():
        if p.is_alive and p.position.x == target_x and p.position.y == target_y:
            return ActionResult(
                player_id=player.player_id, username=player.username,
                action_type=ActionType.SKILL, skill_id=skill_id, success=False,
                message=f"{player.username} {skill_def['name']} failed — tile is occupied",
            )

    # Need match_state to store totems
    if match_state is None:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no match state",
        )

    # Determine the full totem type name
    full_totem_type = f"{totem_type}_totem"  # "healing_totem" or "searing_totem"

    # Remove any existing totem of THIS TYPE from this Shaman (max 1 per type)
    match_state.totems = [
        t for t in match_state.totems
        if not (t["type"] == full_totem_type and t["owner_id"] == player.player_id)
    ]

    # Create totem entity
    totem_entity = {
        "id": str(uuid.uuid4()),
        "type": full_totem_type,
        "owner_id": player.player_id,
        "x": target_x,
        "y": target_y,
        "hp": totem_hp,
        "max_hp": totem_hp,
        "heal_per_turn": heal_per_turn,
        "damage_per_turn": damage_per_turn,
        "root_duration": root_duration,
        "effect_radius": effect_radius,
        "duration_remaining": duration_turns,
        "team": player.team,
    }
    match_state.totems.append(totem_entity)

    _apply_skill_cooldown(player, skill_def)

    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} placed {skill_def['name']} at ({target_x}, {target_y})",
        to_x=target_x, to_y=target_y,
        buff_applied={"type": "totem_placed", "totem_type": full_totem_type,
                       "x": target_x, "y": target_y, "duration": duration_turns},
    )


def resolve_soul_anchor(
    player: PlayerState,
    action,
    skill_def: dict,
    players: dict[str, PlayerState],
    target_id: str | None = None,
) -> ActionResult:
    """Apply a cheat-death buff (Soul Anchor) to an ally or self.

    If the anchored ally would die while the buff is active, their HP is set
    to 1 instead and the buff is consumed (one-time trigger). Only 1 Soul
    Anchor can be active per Shaman — recasting removes the previous one.

    Phase 26B: Shaman — Soul Anchor skill.
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    survive_hp = effect.get("survive_hp", 1)
    duration = effect.get("duration_turns", 4)
    skill_range = skill_def.get("range", 4)

    target_x = getattr(action, "target_x", None)
    target_y = getattr(action, "target_y", None)

    # Entity-based target resolution (ally_target=True for ally_or_self targeting)
    target = _resolve_skill_entity_target(player, target_id, target_x, target_y, players, ally_target=True)

    if target is None:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no valid target",
        )

    # Range check (Chebyshev) — self is always in range
    if target.player_id != player.player_id:
        dx = abs(player.position.x - target.position.x)
        dy = abs(player.position.y - target.position.y)
        if max(dx, dy) > skill_range:
            return ActionResult(
                player_id=player.player_id, username=player.username,
                action_type=ActionType.SKILL, skill_id=skill_id, success=False,
                message=f"{player.username} {skill_def['name']} failed — target out of range",
            )

    # Remove any existing soul_anchor buff cast by THIS Shaman on ANY target (max 1)
    for p in players.values():
        p.active_buffs = [
            b for b in p.active_buffs
            if not (b.get("stat") == "soul_anchor" and b.get("caster_id") == player.player_id)
        ]

    # Apply soul_anchor buff to target
    anchor_entry = {
        "buff_id": "soul_anchor",
        "type": "soul_anchor",
        "stat": "soul_anchor",
        "caster_id": player.player_id,
        "turns_remaining": duration,
        "magnitude": 0,
        "survive_hp": survive_hp,
    }
    target.active_buffs.append(anchor_entry)

    _apply_skill_cooldown(player, skill_def)

    target_name = target.username if target.player_id != player.player_id else "self"
    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} anchored {target_name}'s soul — survives death at {survive_hp} HP for {duration} turns",
        target_id=target.player_id,
        target_username=target.username,
        buff_applied={"type": "soul_anchor", "survive_hp": survive_hp, "duration": duration},
    )
