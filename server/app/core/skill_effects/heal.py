"""Healing skill effect handlers — resolve_heal, resolve_hot, resolve_aoe_heal."""
from __future__ import annotations

from app.models.player import PlayerState
from app.models.actions import ActionResult, ActionType
from app.core.skill_effects._helpers import _apply_skill_cooldown


def resolve_heal(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a heal skill — restore HP to self or an adjacent ally.

    Targeting: ally_or_self, range 3 (Chebyshev).
    Supports entity-based targeting via target_id (falls back to tile coords).
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    magnitude = effect["magnitude"]

    # Find the target
    target: PlayerState | None = None

    if target_id:
        # Entity-based lookup
        candidate = players.get(target_id)
        if candidate and candidate.is_alive:
            if candidate.player_id == player.player_id:
                target = player
            elif candidate.team == player.team:
                target = candidate
    elif target_x is None or target_y is None:
        # Default to self
        target = player
    elif target_x == player.position.x and target_y == player.position.y:
        target = player
    else:
        # Look for an ally at target position (tile-based fallback)
        for p in players.values():
            if (p.is_alive
                    and p.position.x == target_x
                    and p.position.y == target_y
                    and p.player_id != player.player_id):
                # Must be an ally (same team)
                if p.team == player.team:
                    target = p
                break

    if target is None:
        return ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.SKILL,
            skill_id=skill_id,
            success=False,
            message=f"{player.username} Heal failed — no valid target",
        )

    # Check range (must be within 1 tile or self)
    if target.player_id != player.player_id:
        dx = abs(player.position.x - target.position.x)
        dy = abs(player.position.y - target.position.y)
        if dx > skill_def["range"] or dy > skill_def["range"]:
            return ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.SKILL,
                skill_id=skill_id,
                success=False,
                message=f"{player.username} Heal failed — target out of range",
            )

    # Apply heal (Phase 16A: heal_power_pct bonus)
    heal_power = getattr(player, 'heal_power_pct', 0.0)
    effective_magnitude = int(magnitude * (1.0 + heal_power))

    # Phase 16D: Penitent Mail — healing received bonus on target
    from app.core.item_generator import get_all_equipped_unique_effects
    for eff in get_all_equipped_unique_effects(target.equipment):
        if eff.get("type") == "healing_received_bonus":
            effective_magnitude = int(effective_magnitude * (1.0 + eff.get("value", 0)))

    old_hp = target.hp
    target.hp = min(target.max_hp, target.hp + effective_magnitude)
    healed = target.hp - old_hp
    _apply_skill_cooldown(player, skill_def)

    target_name = target.username if target.player_id != player.player_id else "self"
    return ActionResult(
        player_id=player.player_id,
        username=player.username,
        action_type=ActionType.SKILL,
        skill_id=skill_id,
        success=True,
        message=f"{player.username} healed {target_name} for {healed} HP",
        target_id=target.player_id,
        target_username=target.username,
        heal_amount=healed,
        target_hp_remaining=target.hp,
    )


def resolve_hot(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a Heal-over-Time skill (e.g., Prayer).

    Applies a HoT buff to self or ally. Healing is applied each turn by tick_buffs().
    Supports entity-based targeting via target_id.
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    heal_per_tick = effect.get("heal_per_tick", 8)
    # Phase 16A: heal_power_pct bonus
    heal_power = getattr(player, 'heal_power_pct', 0.0)
    heal_per_tick = int(heal_per_tick * (1.0 + heal_power))
    duration = effect.get("duration_turns", 4)
    skill_range = skill_def.get("range", 4)

    # Find target (self or ally)
    target = player
    if target_id:
        # Entity-based lookup
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

    if target is None:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no valid target",
        )

    # Range check
    if target.player_id != player.player_id:
        dx = abs(player.position.x - target.position.x)
        dy = abs(player.position.y - target.position.y)
        if max(dx, dy) > skill_range:
            return ActionResult(
                player_id=player.player_id, username=player.username,
                action_type=ActionType.SKILL, skill_id=skill_id, success=False,
                message=f"{player.username} {skill_def['name']} failed — target out of range",
            )

    # Phase 16D: Penitent Mail — healing received bonus on target
    from app.core.item_generator import get_all_equipped_unique_effects
    actual_heal_per_tick = heal_per_tick
    for eff in get_all_equipped_unique_effects(target.equipment):
        if eff.get("type") == "healing_received_bonus":
            actual_heal_per_tick = int(actual_heal_per_tick * (1.0 + eff.get("value", 0)))

    # Phase 16D: Prayer Beads — AoE heal (prayer heals all adjacent allies too)
    aoe_heal = False
    for eff in get_all_equipped_unique_effects(player.equipment):
        if eff.get("type") == "prayer_aoe_heal":
            aoe_heal = True
            break

    aoe_targets = []
    if aoe_heal:
        for p in players.values():
            if (p.is_alive and p.team == player.team
                    and p.player_id != target.player_id):
                dist = max(abs(p.position.x - player.position.x),
                           abs(p.position.y - player.position.y))
                if dist <= 1:
                    # Apply HoT to adjacent ally too
                    ally_heal_tick = heal_per_tick
                    for eff in get_all_equipped_unique_effects(p.equipment):
                        if eff.get("type") == "healing_received_bonus":
                            ally_heal_tick = int(ally_heal_tick * (1.0 + eff.get("value", 0)))
                    ally_hot = {
                        "buff_id": skill_id,
                        "type": "hot",
                        "source_id": player.player_id,
                        "heal_per_tick": ally_heal_tick,
                        "turns_remaining": duration,
                        "stat": None,
                        "magnitude": ally_heal_tick,
                    }
                    p.active_buffs.append(ally_hot)
                    aoe_targets.append(p.username)

    # Apply HoT buff to primary target
    hot_entry = {
        "buff_id": skill_id,
        "type": "hot",
        "source_id": player.player_id,
        "heal_per_tick": actual_heal_per_tick,
        "turns_remaining": duration,
        "stat": None,
        "magnitude": actual_heal_per_tick,
    }
    target.active_buffs.append(hot_entry)
    _apply_skill_cooldown(player, skill_def)

    target_name = target.username if target.player_id != player.player_id else "self"
    total_heal = actual_heal_per_tick * duration
    aoe_msg = f" (also heals: {', '.join(aoe_targets)})" if aoe_targets else ""
    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} used {skill_def['name']} on {target_name} (+{actual_heal_per_tick} HP/turn for {duration} turns, {total_heal} total){aoe_msg}",
        target_id=target.player_id, target_username=target.username,
        heal_amount=0,  # No instant heal — comes from ticks
        buff_applied={"type": "hot", "heal_per_tick": actual_heal_per_tick, "duration": duration},
    )


def resolve_aoe_heal(
    player: PlayerState,
    skill_def: dict,
    players: dict[str, PlayerState],
) -> ActionResult:
    """Resolve an AoE heal skill centered on self (e.g., Holy Ground).

    Targeting: self. Heals all allies (including self) within radius.
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    radius = effect.get("radius", 1)
    magnitude = effect.get("magnitude", 15)
    # Phase 16A: heal_power_pct bonus
    heal_power = getattr(player, 'heal_power_pct', 0.0)
    magnitude = int(magnitude * (1.0 + heal_power))

    total_healed = 0
    healed_count = 0
    healed_names: list[str] = []

    for p in players.values():
        if not p.is_alive or p.team != player.team:
            continue
        dist = max(abs(p.position.x - player.position.x), abs(p.position.y - player.position.y))
        if dist <= radius:
            old_hp = p.hp
            p.hp = min(p.max_hp, p.hp + magnitude)
            actual_heal = p.hp - old_hp
            if actual_heal > 0:
                total_healed += actual_heal
                healed_count += 1
                name = "self" if p.player_id == player.player_id else p.username
                healed_names.append(f"{name}(+{actual_heal})")

    _apply_skill_cooldown(player, skill_def)

    if healed_count > 0:
        heal_str = ", ".join(healed_names)
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — healed {healed_count} allies for {total_healed} total HP: {heal_str}",
            heal_amount=total_healed,
            buff_applied={"type": "aoe_heal", "healed_count": healed_count, "total_healed": total_healed},
        )
    else:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — no allies in range to heal",
        )
