"""Debuff and crowd-control skill effect handlers."""
from __future__ import annotations

from app.models.player import PlayerState, Position
from app.models.actions import ActionResult, ActionType
from app.core.fov import has_line_of_sight
from app.core.skill_effects._helpers import _apply_skill_cooldown, _resolve_skill_entity_target


def resolve_dot(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a Damage-over-Time skill (e.g., Wither).

    Applies a DoT debuff to an enemy. Damage is applied each turn by tick_buffs().
    Cannot stack multiple of the same DoT on the same target.
    Supports entity-based targeting via target_id.
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    damage_per_tick = effect.get("damage_per_tick", 6)
    # Phase 16A: dot_damage_pct bonus
    dot_pct = getattr(player, 'dot_damage_pct', 0.0)
    damage_per_tick = int(damage_per_tick * (1.0 + dot_pct))
    duration = effect.get("duration_turns", 4)
    skill_range = skill_def.get("range", 3)
    requires_los = skill_def.get("requires_line_of_sight", True)

    # Phase 16E: Set bonus — DoT duration bonus (e.g., Voidwalker Wither +1/+2 turns)
    from app.core.set_bonuses import get_set_skill_modifiers
    set_modifiers = get_set_skill_modifiers(player.active_set_bonuses)
    if skill_id in set_modifiers:
        duration += set_modifiers[skill_id].get("duration_bonus", 0)

    # Entity-based target resolution (preferred)
    target = _resolve_skill_entity_target(player, target_id, target_x, target_y, players, ally_target=False)

    if target is None:
        if target_x is None or target_y is None:
            return ActionResult(
                player_id=player.player_id, username=player.username,
                action_type=ActionType.SKILL, skill_id=skill_id, success=False,
                message=f"{player.username} {skill_def['name']} failed — no target specified",
            )
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no enemy at target",
        )

    # Range check against target's CURRENT position (Chebyshev)
    dx = abs(player.position.x - target.position.x)
    dy = abs(player.position.y - target.position.y)
    if max(dx, dy) > skill_range:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — target out of range",
        )

    # LOS check against target's CURRENT position
    if requires_los and not has_line_of_sight(
        player.position.x, player.position.y, target.position.x, target.position.y, obstacles,
    ):
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no line of sight",
        )

    # Check for existing DoT of same type — refresh duration instead of failing
    refreshed = False
    for buff in target.active_buffs:
        if buff.get("buff_id") == skill_id and buff.get("type") == "dot":
            buff["turns_remaining"] = duration
            buff["damage_per_tick"] = damage_per_tick
            buff["source_id"] = player.player_id
            buff["magnitude"] = damage_per_tick
            refreshed = True
            break

    if not refreshed:
        # Apply new DoT debuff to target
        dot_entry = {
            "buff_id": skill_id,
            "type": "dot",
            "source_id": player.player_id,
            "damage_per_tick": damage_per_tick,
            "turns_remaining": duration,
            "stat": None,
            "magnitude": damage_per_tick,
        }
        target.active_buffs.append(dot_entry)

    _apply_skill_cooldown(player, skill_def, dealt_damage=True)

    total_damage = damage_per_tick * duration
    verb = "refreshed" if refreshed else "cursed"
    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} {verb} {target.username} with {skill_def['name']} ({damage_per_tick} dmg/turn for {duration} turns, {total_damage} total)",
        target_id=target.player_id, target_username=target.username,
        buff_applied={"type": "dot", "damage_per_tick": damage_per_tick, "duration": duration},
    )


def resolve_taunt(
    player: PlayerState,
    skill_def: dict,
    players: dict[str, PlayerState],
) -> ActionResult:
    """Resolve a taunt skill — force nearby enemies to target the caster.

    Targeting: self (emanates from caster). Affects all enemies within radius.
    Applies a taunt debuff that AI will respect for target selection.
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    radius = effect.get("radius", 2)
    duration = effect.get("duration_turns", 2)

    # Phase 16D: Warden's Oath — taunt range bonus
    from app.core.item_generator import get_all_equipped_unique_effects
    for eff in get_all_equipped_unique_effects(player.equipment):
        if eff.get("type") == "taunt_range_bonus":
            radius += eff.get("value", 0)

    # Phase 16E: Set bonus — taunt duration bonus
    from app.core.set_bonuses import get_set_skill_modifiers
    set_modifiers = get_set_skill_modifiers(player.active_set_bonuses)
    if "taunt" in set_modifiers:
        duration += set_modifiers["taunt"].get("duration_bonus", 0)

    taunted_enemies: list[str] = []
    for p in players.values():
        if not p.is_alive or p.team == player.team:
            continue
        dist = max(abs(p.position.x - player.position.x), abs(p.position.y - player.position.y))
        if dist <= radius:
            # Remove existing taunt (refresh, don't stack from same source)
            p.active_buffs = [b for b in p.active_buffs if b.get("type") != "taunt"]
            taunt_entry = {
                "buff_id": skill_id,
                "type": "taunt",
                "source_id": player.player_id,
                "turns_remaining": duration,
                "stat": None,
                "magnitude": 0,
            }
            p.active_buffs.append(taunt_entry)
            taunted_enemies.append(p.username)

    _apply_skill_cooldown(player, skill_def)

    if taunted_enemies:
        names = ", ".join(taunted_enemies)
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — taunted {len(taunted_enemies)} enemies: {names}",
            buff_applied={"type": "taunt", "duration": duration, "count": len(taunted_enemies)},
        )
    else:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — no enemies in range to taunt",
        )


def resolve_aoe_debuff(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
) -> ActionResult:
    """Resolve an AoE debuff skill at a target tile (e.g., Dirge of Weakness).

    Targeting: ground_aoe — player targets a tile, all enemies within radius of that
    tile receive a debuff. Validates range + LOS to the center tile.

    Phase 21B: Bard — Dirge of Weakness (+25% damage taken for 3 turns).
    """
    from app.core.combat import is_in_range

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    radius = effect.get("radius", 2)
    stat = effect["stat"]
    magnitude = effect["magnitude"]
    duration = effect["duration_turns"]
    skill_range = skill_def.get("range", 4)
    requires_los = skill_def.get("requires_line_of_sight", True)

    if target_x is None or target_y is None:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no target specified",
        )

    # Range check to center tile (Chebyshev)
    target_pos = Position(x=target_x, y=target_y)
    if not is_in_range(player.position, target_pos, skill_range):
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — target out of range",
        )

    # LOS check to center tile
    if requires_los and not has_line_of_sight(
        player.position.x, player.position.y, target_x, target_y, obstacles,
    ):
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no line of sight",
        )

    debuffed_count = 0
    debuffed_names: list[str] = []

    for p in players.values():
        if not p.is_alive or p.team == player.team:
            continue
        dist = max(abs(p.position.x - target_x), abs(p.position.y - target_y))
        if dist <= radius:
            # Remove existing debuff from same skill (refresh, don't stack)
            p.active_buffs = [b for b in p.active_buffs if b.get("buff_id") != skill_id]

            debuff_entry = {
                "buff_id": skill_id,
                "type": "debuff",
                "stat": stat,
                "magnitude": magnitude,
                "turns_remaining": duration,
            }
            p.active_buffs.append(debuff_entry)
            debuffed_count += 1
            debuffed_names.append(p.username)

    _apply_skill_cooldown(player, skill_def)

    if debuffed_count > 0:
        debuff_str = ", ".join(debuffed_names)
        pct = int((magnitude - 1) * 100)
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — debuffed {debuffed_count} enemies (+{pct}% damage taken, {duration} turns): {debuff_str}",
            to_x=target_x, to_y=target_y,
            buff_applied={"type": "aoe_debuff", "stat": stat, "magnitude": magnitude, "duration": duration, "debuffed_count": debuffed_count},
        )
    else:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — no enemies in the debuff radius",
            to_x=target_x, to_y=target_y,
        )


def resolve_targeted_debuff(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a targeted single-enemy debuff (e.g., Seal of Judgment).

    Applies a debuff to one enemy target within range + LOS.
    If base_damage is specified, also deals holy damage before applying the debuff.
    Uses the same damage_taken_multiplier system as Dirge of Weakness.
    """
    from app.core.combat import is_in_range, get_combat_config
    from app.core.skills import get_effective_armor, get_damage_taken_multiplier, get_damage_dealt_multiplier

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    stat = effect["stat"]
    magnitude = effect["magnitude"]
    duration = effect["duration_turns"]
    base_damage = effect.get("base_damage", 0)
    skill_range = skill_def.get("range", 6)
    requires_los = skill_def.get("requires_line_of_sight", True)

    target = _resolve_skill_entity_target(player, target_id, target_x, target_y, players, ally_target=False)

    if target is None:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no enemy at target",
        )

    target_pos = Position(x=target.position.x, y=target.position.y)
    if not is_in_range(player.position, target_pos, skill_range):
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — target out of range",
        )

    if requires_los and not has_line_of_sight(
        player.position.x, player.position.y, target.position.x, target.position.y, obstacles,
    ):
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no line of sight",
        )

    # Deal holy damage if base_damage is specified
    damage = 0
    killed = False
    if base_damage > 0:
        config = get_combat_config()
        effective_armor = get_effective_armor(target)
        reduction = effective_armor * config.get("armor_reduction_per_point", 1)
        damage = max(1, base_damage - reduction)
        # Apply damage multipliers
        dmg_taken_mult = get_damage_taken_multiplier(target)
        if dmg_taken_mult != 1.0:
            damage = max(1, int(damage * dmg_taken_mult))
        dmg_dealt_mult = get_damage_dealt_multiplier(player)
        if dmg_dealt_mult != 1.0:
            damage = max(1, int(damage * dmg_dealt_mult))
        target.hp = max(0, target.hp - damage)
        killed = target.hp <= 0
        if killed:
            target.is_alive = False

    # Apply debuff (only if target survives)
    if not killed:
        # Remove existing debuff from same skill (refresh, don't stack)
        target.active_buffs = [b for b in target.active_buffs if b.get("buff_id") != skill_id]

        debuff_entry = {
            "buff_id": skill_id,
            "type": "debuff",
            "stat": stat,
            "magnitude": magnitude,
            "turns_remaining": duration,
        }
        target.active_buffs.append(debuff_entry)

    _apply_skill_cooldown(player, skill_def, dealt_damage=base_damage > 0)

    pct = int((magnitude - 1) * 100)
    dmg_text = f" for {damage} damage" if damage > 0 else ""
    mark_text = f" — +{pct}% damage taken for {duration} turns" if not killed else ""
    kill_text = f" — {target.username} was killed!" if killed else ""
    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} used {skill_def['name']} on {target.username}{dmg_text}{mark_text}{kill_text}",
        target_id=target.player_id, target_username=target.username,
        killed=killed,
        buff_applied={"type": "targeted_debuff", "stat": stat, "magnitude": magnitude, "duration": duration, "damage": damage},
    )


def resolve_ranged_taunt(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a ranged single-target taunt (Grave Chains).

    Spectral chains force a single enemy to attack the caster for N turns.
    Unlike the AoE melee-range Taunt, this targets one enemy at range and
    requires line of sight.
    Phase 25B: Revenant Grave Chains skill.
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    taunt_duration = effect.get("taunt_duration", 3)
    skill_range = skill_def.get("range", 3)
    requires_los = skill_def.get("requires_line_of_sight", True)

    # Entity-based target resolution
    target = _resolve_skill_entity_target(player, target_id, target_x, target_y, players, ally_target=False)

    if target is None:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no enemy at target",
        )

    # Range check (Chebyshev distance)
    dx = abs(player.position.x - target.position.x)
    dy = abs(player.position.y - target.position.y)
    if max(dx, dy) > skill_range:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — target out of range",
        )

    # LOS check
    if requires_los and not has_line_of_sight(
        player.position.x, player.position.y, target.position.x, target.position.y, obstacles,
    ):
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no line of sight",
        )

    # Remove existing taunt on this target (refresh, don't stack)
    target.active_buffs = [b for b in target.active_buffs if b.get("type") != "taunt"]

    taunt_entry = {
        "buff_id": skill_id,
        "type": "taunt",
        "source_id": player.player_id,
        "turns_remaining": taunt_duration,
        "stat": None,
        "magnitude": 0,
    }
    target.active_buffs.append(taunt_entry)
    _apply_skill_cooldown(player, skill_def)

    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} used {skill_def['name']} on {target.username} — taunted for {taunt_duration} turns",
        target_id=target.player_id, target_username=target.username,
        buff_applied={"type": "taunt", "duration": taunt_duration},
    )


def resolve_aoe_root(
    player: PlayerState,
    action,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
) -> ActionResult:
    """Root all enemies within radius of target tile.

    Rooted enemies CANNOT MOVE but CAN still attack and use skills.
    Root is a new CC type distinct from slow and stun.

    Phase 26B: Shaman — Earthgrasp skill.
    """
    from app.core.combat import is_in_range

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    radius = effect.get("radius", 2)
    root_duration = effect.get("root_duration", 2)
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

    # Find all enemies within radius of target tile and apply root
    rooted_count = 0
    rooted_names: list[str] = []

    for p in players.values():
        if not p.is_alive or p.team == player.team:
            continue
        dist = max(abs(p.position.x - target_x), abs(p.position.y - target_y))
        if dist <= radius:
            # Refresh existing root (don't stack)
            p.active_buffs = [b for b in p.active_buffs if b.get("stat") != "rooted"]
            root_entry = {
                "buff_id": "earthgrasp",
                "type": "aoe_root",
                "stat": "rooted",
                "source_id": player.player_id,
                "turns_remaining": root_duration,
                "magnitude": 0,
            }
            p.active_buffs.append(root_entry)
            rooted_count += 1
            rooted_names.append(p.username)

    _apply_skill_cooldown(player, skill_def)

    if rooted_count > 0:
        names_str = ", ".join(rooted_names)
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — rooted {rooted_count} enem{'y' if rooted_count == 1 else 'ies'}: {names_str} for {root_duration} turn(s)!",
            to_x=target_x, to_y=target_y,
            buff_applied={"type": "aoe_root", "rooted_count": rooted_count, "duration": root_duration},
        )
    else:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — no enemies in range to root",
            to_x=target_x, to_y=target_y,
            buff_applied={"type": "aoe_root", "rooted_count": 0, "duration": root_duration},
        )
