"""Direct damage skill effect handlers."""
from __future__ import annotations

from app.models.player import PlayerState, Position
from app.models.actions import ActionResult, ActionType
from app.core.fov import has_line_of_sight
from app.core.skill_effects._helpers import _apply_skill_cooldown, _resolve_skill_entity_target


def resolve_multi_hit(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a multi-hit melee skill (e.g., Double Strike).

    Targeting: enemy_adjacent, range 1.
    Each hit applies armor reduction separately.
    Supports entity-based targeting via target_id.
    """
    from app.core.combat import _get_equipment_bonuses, get_combat_config
    from app.core.skills import get_melee_buff_multiplier, get_damage_taken_multiplier, get_damage_dealt_multiplier

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    hits = effect.get("hits", 2)
    damage_multiplier = effect.get("damage_multiplier", 0.6)

    # Entity-based target resolution (preferred)
    target = _resolve_skill_entity_target(player, target_id, target_x, target_y, players, ally_target=False)

    if target is None:
        if target_x is None or target_y is None:
            return ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.SKILL,
                skill_id=skill_id,
                success=False,
                message=f"{player.username} {skill_def['name']} failed — no target specified",
            )
        return ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.SKILL,
            skill_id=skill_id,
            success=False,
            message=f"{player.username} {skill_def['name']} failed — no enemy at target",
        )

    # Must be adjacent (check against target's CURRENT position)
    dx = abs(player.position.x - target.position.x)
    dy = abs(player.position.y - target.position.y)
    if dx > 1 or dy > 1 or (dx == 0 and dy == 0):
        return ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.SKILL,
            skill_id=skill_id,
            success=False,
            message=f"{player.username} {skill_def['name']} failed — target not adjacent",
        )

    # Calculate per-hit damage with equipment bonuses
    config = get_combat_config()
    atk_bonuses = _get_equipment_bonuses(player)
    def_bonuses = _get_equipment_bonuses(target)

    # Include melee buff multiplier
    melee_mult = get_melee_buff_multiplier(player)
    raw_damage = int((player.attack_damage + atk_bonuses.attack_damage) * melee_mult)
    # Phase 16A: skill_damage_pct bonus
    skill_dmg_pct = getattr(player, 'skill_damage_pct', 0.0)
    raw_damage = int(raw_damage * (1.0 + skill_dmg_pct))
    effective_armor = target.armor + def_bonuses.armor
    # Phase 16A: armor pen
    effective_armor = max(0, effective_armor - getattr(player, 'armor_pen', 0))
    armor_reduction = effective_armor * config.get("armor_reduction_per_point", 1)

    # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
    dmg_taken_mult = get_damage_taken_multiplier(target)
    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble)
    dmg_dealt_mult = get_damage_dealt_multiplier(player)

    total_damage = 0
    killed = False
    for i in range(hits):
        if not target.is_alive:
            break
        hit_raw = int(raw_damage * damage_multiplier)
        hit_damage = max(1, hit_raw - armor_reduction)
        if dmg_taken_mult != 1.0:
            hit_damage = max(1, int(hit_damage * dmg_taken_mult))
        if dmg_dealt_mult != 1.0:
            hit_damage = max(1, int(hit_damage * dmg_dealt_mult))
        target.hp = max(0, target.hp - hit_damage)
        total_damage += hit_damage
        if target.hp <= 0:
            target.is_alive = False
            killed = True

    _apply_skill_cooldown(player, skill_def, dealt_damage=True)

    return ActionResult(
        player_id=player.player_id,
        username=player.username,
        action_type=ActionType.SKILL,
        skill_id=skill_id,
        success=True,
        message=f"{player.username} used {skill_def['name']} on {target.username} for {total_damage} damage ({hits} hits)"
                + (f" — {target.username} was killed!" if killed else ""),
        target_id=target.player_id,
        target_username=target.username,
        damage_dealt=total_damage,
        target_hp_remaining=target.hp,
        killed=killed,
    )


def resolve_ranged_skill(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a ranged damage skill (e.g., Power Shot).

    Targeting: enemy_ranged. Uses player's ranged_range if skill range == 0.
    Requires LOS if specified.
    Supports entity-based targeting via target_id.
    """
    from app.core.combat import _get_equipment_bonuses, get_combat_config, is_in_range
    from app.core.skills import get_ranged_buff_multiplier, get_damage_taken_multiplier, get_damage_dealt_multiplier

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    damage_multiplier = effect.get("damage_multiplier", 1.0)
    skill_range = skill_def["range"] if skill_def["range"] > 0 else player.ranged_range
    requires_los = skill_def.get("requires_line_of_sight", True)

    # Entity-based target resolution (preferred)
    target = _resolve_skill_entity_target(player, target_id, target_x, target_y, players, ally_target=False)

    if target is None:
        if target_x is None or target_y is None:
            return ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.SKILL,
                skill_id=skill_id,
                success=False,
                message=f"{player.username} {skill_def['name']} failed — no target specified",
            )
        return ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.SKILL,
            skill_id=skill_id,
            success=False,
            message=f"{player.username} {skill_def['name']} failed — no enemy at target",
        )

    # Check range against target's CURRENT position
    target_pos = Position(x=target.position.x, y=target.position.y)
    if not is_in_range(player.position, target_pos, skill_range):
        return ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.SKILL,
            skill_id=skill_id,
            success=False,
            message=f"{player.username} {skill_def['name']} failed — target out of range",
        )

    # Check LOS against target's CURRENT position
    if requires_los:
        if not has_line_of_sight(
            player.position.x, player.position.y,
            target.position.x, target.position.y,
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

    # Calculate boosted ranged damage with equipment bonuses
    config = get_combat_config()
    atk_bonuses = _get_equipment_bonuses(player)
    def_bonuses = _get_equipment_bonuses(target)
    ranged_mult = get_ranged_buff_multiplier(player)
    raw_damage = int((player.ranged_damage + atk_bonuses.ranged_damage) * ranged_mult * damage_multiplier)
    # Phase 16A: skill_damage_pct bonus
    skill_dmg_pct = getattr(player, 'skill_damage_pct', 0.0)
    raw_damage = int(raw_damage * (1.0 + skill_dmg_pct))
    effective_armor = target.armor + def_bonuses.armor
    # Phase 16A: armor pen
    effective_armor = max(0, effective_armor - getattr(player, 'armor_pen', 0))
    reduction = effective_armor * config.get("armor_reduction_per_point", 1)
    damage = max(1, raw_damage - reduction)
    # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
    dmg_taken_mult = get_damage_taken_multiplier(target)
    if dmg_taken_mult != 1.0:
        damage = max(1, int(damage * dmg_taken_mult))
    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble)
    dmg_dealt_mult = get_damage_dealt_multiplier(player)
    if dmg_dealt_mult != 1.0:
        damage = max(1, int(damage * dmg_dealt_mult))

    target.hp = max(0, target.hp - damage)
    killed = target.hp <= 0
    if killed:
        target.is_alive = False

    _apply_skill_cooldown(player, skill_def, dealt_damage=True)

    return ActionResult(
        player_id=player.player_id,
        username=player.username,
        action_type=ActionType.SKILL,
        skill_id=skill_id,
        success=True,
        message=f"{player.username} used {skill_def['name']} on {target.username} for {damage} damage"
                + (f" — {target.username} was killed!" if killed else ""),
        target_id=target.player_id,
        target_username=target.username,
        damage_dealt=damage,
        target_hp_remaining=target.hp,
        killed=killed,
    )


def resolve_holy_damage(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a holy damage skill (e.g., Rebuke the Wicked, Exorcism).

    Deals base damage with bonus damage vs Undead/Demon tagged enemies.
    Supports entity-based targeting via target_id.
    """
    from app.core.combat import _get_equipment_bonuses, get_combat_config
    from app.core.skills import get_effective_armor, get_damage_taken_multiplier, get_damage_dealt_multiplier

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    base_damage = effect.get("base_damage", 20)
    bonus_vs_tags = effect.get("bonus_vs_tags", [])
    bonus_multiplier = effect.get("bonus_multiplier", 1.5)
    skill_range = skill_def.get("range", 5)
    requires_los = skill_def.get("requires_line_of_sight", True)

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

    # Range check against target's CURRENT position
    from app.core.combat import is_in_range
    target_pos = Position(x=target.position.x, y=target.position.y)
    if not is_in_range(player.position, target_pos, skill_range):
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

    # Check creature tags for bonus damage
    has_bonus = any(tag in getattr(target, 'tags', []) for tag in bonus_vs_tags)
    final_damage = int(base_damage * bonus_multiplier) if has_bonus else base_damage

    # Phase 16A: holy_damage_pct and skill_damage_pct bonuses
    holy_pct = getattr(player, 'holy_damage_pct', 0.0)
    skill_pct = getattr(player, 'skill_damage_pct', 0.0)
    final_damage = int(final_damage * (1.0 + holy_pct + skill_pct))

    # Apply armor reduction
    config = get_combat_config()
    effective_armor = get_effective_armor(target)
    reduction = effective_armor * config.get("armor_reduction_per_point", 1)
    damage = max(1, final_damage - reduction)
    # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
    dmg_taken_mult = get_damage_taken_multiplier(target)
    if dmg_taken_mult != 1.0:
        damage = max(1, int(damage * dmg_taken_mult))
    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble)
    dmg_dealt_mult = get_damage_dealt_multiplier(player)
    if dmg_dealt_mult != 1.0:
        damage = max(1, int(damage * dmg_dealt_mult))

    target.hp = max(0, target.hp - damage)
    killed = target.hp <= 0
    if killed:
        target.is_alive = False

    _apply_skill_cooldown(player, skill_def, dealt_damage=True)

    bonus_text = " (holy bonus!)" if has_bonus else ""
    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} used {skill_def['name']} on {target.username} for {damage} damage{bonus_text}"
                + (f" — {target.username} was killed!" if killed else ""),
        target_id=target.player_id, target_username=target.username,
        damage_dealt=damage, target_hp_remaining=target.hp, killed=killed,
    )


def resolve_stun_damage(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a melee attack that stuns the target (e.g., Shield Bash).

    Targeting: enemy_adjacent, range 1.
    Deals reduced melee damage and applies a stun debuff.
    """
    from app.core.combat import _get_equipment_bonuses, get_combat_config
    from app.core.skills import get_melee_buff_multiplier, get_effective_armor, get_damage_taken_multiplier, get_damage_dealt_multiplier

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    damage_multiplier = effect.get("damage_multiplier", 0.7)
    stun_duration = effect.get("stun_duration", 1)

    # Entity-based target resolution
    target = _resolve_skill_entity_target(player, target_id, target_x, target_y, players, ally_target=False)

    if target is None:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no enemy at target",
        )

    # Must be adjacent
    dx = abs(player.position.x - target.position.x)
    dy = abs(player.position.y - target.position.y)
    if dx > 1 or dy > 1 or (dx == 0 and dy == 0):
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — target not adjacent",
        )

    # Calculate damage
    config = get_combat_config()
    atk_bonuses = _get_equipment_bonuses(player)
    melee_mult = get_melee_buff_multiplier(player)
    raw_damage = int((player.attack_damage + atk_bonuses.attack_damage) * melee_mult * damage_multiplier)
    # Phase 16A: skill_damage_pct bonus
    skill_dmg_pct = getattr(player, 'skill_damage_pct', 0.0)
    raw_damage = int(raw_damage * (1.0 + skill_dmg_pct))
    effective_armor = get_effective_armor(target)
    reduction = effective_armor * config.get("armor_reduction_per_point", 1)
    damage = max(1, raw_damage - reduction)
    # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
    dmg_taken_mult = get_damage_taken_multiplier(target)
    if dmg_taken_mult != 1.0:
        damage = max(1, int(damage * dmg_taken_mult))
    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble)
    dmg_dealt_mult = get_damage_dealt_multiplier(player)
    if dmg_dealt_mult != 1.0:
        damage = max(1, int(damage * dmg_dealt_mult))

    target.hp = max(0, target.hp - damage)
    killed = target.hp <= 0
    if killed:
        target.is_alive = False

    # Apply stun debuff (only if target survived)
    stun_applied = False
    cc_immune = False
    if not killed and target.is_alive:
        # Phase 16D: Check Ironwill Plate CC immunity
        from app.core.item_generator import get_all_equipped_unique_effects
        for eff in get_all_equipped_unique_effects(target.equipment):
            if eff.get("type") == "cc_immunity" and "stun" in eff.get("immune_to", []):
                cc_immune = True
                break

        if cc_immune:
            stun_applied = False
        else:
            # Don't stack stuns — refresh if already stunned
            target.active_buffs = [b for b in target.active_buffs if b.get("type") != "stun"]
            stun_entry = {
                "buff_id": skill_id,
                "type": "stun",
                "source_id": player.player_id,
                "turns_remaining": stun_duration,
                "stat": None,
                "magnitude": 0,
            }
            target.active_buffs.append(stun_entry)
            stun_applied = True

    _apply_skill_cooldown(player, skill_def, dealt_damage=True)

    if cc_immune:
        stun_msg = " — RESISTED (CC immune)!"
    else:
        stun_msg = f" — STUNNED for {stun_duration} turn(s)!" if stun_applied else ""
    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} used {skill_def['name']} on {target.username} for {damage} damage{stun_msg}"
                + (f" — {target.username} was killed!" if killed else ""),
        target_id=target.player_id, target_username=target.username,
        damage_dealt=damage, target_hp_remaining=target.hp, killed=killed,
        buff_applied={"type": "stun", "duration": stun_duration} if stun_applied else None,
    )


def resolve_aoe_damage(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
) -> ActionResult:
    """Resolve an AoE damage skill (e.g., Volley).

    Targeting: ground_aoe — player targets a tile, all enemies within radius take damage.
    Requires LOS to the center tile. Damage is calculated per-target with armor reduction.
    """
    from app.core.combat import _get_equipment_bonuses, get_combat_config, is_in_range
    from app.core.skills import get_ranged_buff_multiplier, get_effective_armor, get_damage_taken_multiplier, get_damage_dealt_multiplier

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    radius = effect.get("radius", 2)
    damage_multiplier = effect.get("damage_multiplier", 0.5)
    skill_range = skill_def.get("range", 5)
    requires_los = skill_def.get("requires_line_of_sight", True)

    if target_x is None or target_y is None:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no target specified",
        )

    # Range check to center tile
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

    # Calculate base damage
    config = get_combat_config()
    atk_bonuses = _get_equipment_bonuses(player)
    ranged_mult = get_ranged_buff_multiplier(player)
    base_raw = int((player.ranged_damage + atk_bonuses.ranged_damage) * ranged_mult * damage_multiplier)
    # Phase 16A: skill_damage_pct bonus
    skill_dmg_pct = getattr(player, 'skill_damage_pct', 0.0)
    base_raw = int(base_raw * (1.0 + skill_dmg_pct))

    # Find all enemies within radius of target tile
    total_damage = 0
    hits = 0
    kills = 0
    killed_ids: list[str] = []
    hit_names: list[str] = []
    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble) — computed once for caster
    dmg_dealt_mult = get_damage_dealt_multiplier(player)

    for p in players.values():
        if not p.is_alive or p.team == player.team:
            continue
        dist = max(abs(p.position.x - target_x), abs(p.position.y - target_y))
        if dist <= radius:
            # Per-target armor reduction
            effective_armor = get_effective_armor(p)
            reduction = effective_armor * config.get("armor_reduction_per_point", 1)
            damage = max(1, base_raw - reduction)
            # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
            dmg_taken_mult = get_damage_taken_multiplier(p)
            if dmg_taken_mult != 1.0:
                damage = max(1, int(damage * dmg_taken_mult))
            if dmg_dealt_mult != 1.0:
                damage = max(1, int(damage * dmg_dealt_mult))
            p.hp = max(0, p.hp - damage)
            total_damage += damage
            hits += 1
            hit_names.append(f"{p.username}({damage})")
            if p.hp <= 0:
                p.is_alive = False
                kills += 1
                killed_ids.append(p.player_id)

    _apply_skill_cooldown(player, skill_def, dealt_damage=True)

    if hits > 0:
        hit_str = ", ".join(hit_names)
        kill_str = f" — {kills} killed!" if kills > 0 else ""
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — hit {hits} enemies for {total_damage} total damage: {hit_str}{kill_str}",
            damage_dealt=total_damage, killed=kills > 0,
            to_x=target_x, to_y=target_y,
            buff_applied={"type": "aoe_damage", "hits": hits, "kills": kills, "killed_ids": killed_ids},
        )
    else:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — no enemies in the blast radius",
            to_x=target_x, to_y=target_y,
        )


def resolve_aoe_magic_damage(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
) -> ActionResult:
    """Resolve an AoE magic damage skill (e.g., Arcane Barrage).

    Like resolve_aoe_damage but uses 50% armor effectiveness (magic damage).
    """
    from app.core.combat import _get_equipment_bonuses, get_combat_config, is_in_range
    from app.core.skills import get_ranged_buff_multiplier, get_effective_armor, get_damage_taken_multiplier, get_damage_dealt_multiplier

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    radius = effect.get("radius", 2)
    damage_multiplier = effect.get("damage_multiplier", 0.5)
    skill_range = skill_def.get("range", 5)
    requires_los = skill_def.get("requires_line_of_sight", True)

    if target_x is None or target_y is None:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no target specified",
        )

    target_pos = Position(x=target_x, y=target_y)
    if not is_in_range(player.position, target_pos, skill_range):
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — target out of range",
        )

    if requires_los and not has_line_of_sight(
        player.position.x, player.position.y, target_x, target_y, obstacles,
    ):
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no line of sight",
        )

    config = get_combat_config()
    atk_bonuses = _get_equipment_bonuses(player)
    ranged_mult = get_ranged_buff_multiplier(player)
    base_raw = int((player.ranged_damage + atk_bonuses.ranged_damage) * ranged_mult * damage_multiplier)
    skill_dmg_pct = getattr(player, 'skill_damage_pct', 0.0)
    magic_dmg_pct = getattr(player, 'magic_damage_pct', 0.0)
    base_raw = int(base_raw * (1.0 + skill_dmg_pct + magic_dmg_pct))

    total_damage = 0
    hits = 0
    kills = 0
    killed_ids: list[str] = []
    hit_names: list[str] = []
    dmg_dealt_mult = get_damage_dealt_multiplier(player)

    for p in players.values():
        if not p.is_alive or p.team == player.team:
            continue
        dist = max(abs(p.position.x - target_x), abs(p.position.y - target_y))
        if dist <= radius:
            # Magic: 50% armor effectiveness
            effective_armor = get_effective_armor(p)
            magic_armor = int(effective_armor * 0.5)
            reduction = magic_armor * config.get("armor_reduction_per_point", 1)
            damage = max(1, base_raw - reduction)
            dmg_taken_mult = get_damage_taken_multiplier(p)
            if dmg_taken_mult != 1.0:
                damage = max(1, int(damage * dmg_taken_mult))
            if dmg_dealt_mult != 1.0:
                damage = max(1, int(damage * dmg_dealt_mult))
            p.hp = max(0, p.hp - damage)
            total_damage += damage
            hits += 1
            hit_names.append(f"{p.username}({damage})")
            if p.hp <= 0:
                p.is_alive = False
                kills += 1
                killed_ids.append(p.player_id)

    _apply_skill_cooldown(player, skill_def, dealt_damage=True)

    if hits > 0:
        hit_str = ", ".join(hit_names)
        kill_str = f" — {kills} killed!" if kills > 0 else ""
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — hit {hits} enemies for {total_damage} total damage: {hit_str}{kill_str}",
            damage_dealt=total_damage, killed=kills > 0,
            to_x=target_x, to_y=target_y,
            buff_applied={"type": "aoe_magic_damage", "hits": hits, "kills": kills, "killed_ids": killed_ids},
        )
    else:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — no enemies in the blast radius",
            to_x=target_x, to_y=target_y,
        )


def resolve_ranged_damage_slow(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a ranged damage + slow skill (e.g., Crippling Shot).

    Targeting: enemy_ranged. Deals reduced ranged damage and applies a slow debuff.
    Slow prevents movement but allows attacks/skills.
    """
    from app.core.combat import _get_equipment_bonuses, get_combat_config, is_in_range
    from app.core.skills import get_ranged_buff_multiplier, get_effective_armor, get_damage_taken_multiplier, get_damage_dealt_multiplier

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    damage_multiplier = effect.get("damage_multiplier", 0.8)
    slow_duration = effect.get("slow_duration", 2)
    skill_range = skill_def["range"] if skill_def["range"] > 0 else player.ranged_range
    requires_los = skill_def.get("requires_line_of_sight", True)

    # Entity-based target resolution
    target = _resolve_skill_entity_target(player, target_id, target_x, target_y, players, ally_target=False)

    if target is None:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no enemy at target",
        )

    # Range check
    target_pos = Position(x=target.position.x, y=target.position.y)
    if not is_in_range(player.position, target_pos, skill_range):
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

    # Calculate damage
    config = get_combat_config()
    atk_bonuses = _get_equipment_bonuses(player)
    ranged_mult = get_ranged_buff_multiplier(player)
    raw_damage = int((player.ranged_damage + atk_bonuses.ranged_damage) * ranged_mult * damage_multiplier)
    # Phase 16A: skill_damage_pct bonus
    skill_dmg_pct = getattr(player, 'skill_damage_pct', 0.0)
    raw_damage = int(raw_damage * (1.0 + skill_dmg_pct))
    effective_armor = get_effective_armor(target)
    reduction = effective_armor * config.get("armor_reduction_per_point", 1)
    damage = max(1, raw_damage - reduction)
    # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
    dmg_taken_mult = get_damage_taken_multiplier(target)
    if dmg_taken_mult != 1.0:
        damage = max(1, int(damage * dmg_taken_mult))
    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble)
    dmg_dealt_mult = get_damage_dealt_multiplier(player)
    if dmg_dealt_mult != 1.0:
        damage = max(1, int(damage * dmg_dealt_mult))

    target.hp = max(0, target.hp - damage)
    killed = target.hp <= 0
    if killed:
        target.is_alive = False

    # Apply slow debuff (only if target survived)
    slow_applied = False
    if not killed and target.is_alive:
        # Refresh existing slow
        target.active_buffs = [b for b in target.active_buffs if b.get("type") != "slow"]
        slow_entry = {
            "buff_id": skill_id,
            "type": "slow",
            "source_id": player.player_id,
            "turns_remaining": slow_duration,
            "stat": None,
            "magnitude": 0,
        }
        target.active_buffs.append(slow_entry)
        slow_applied = True

    _apply_skill_cooldown(player, skill_def, dealt_damage=True)

    slow_msg = f" — SLOWED for {slow_duration} turn(s)!" if slow_applied else ""
    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} used {skill_def['name']} on {target.username} for {damage} damage{slow_msg}"
                + (f" — {target.username} was killed!" if killed else ""),
        target_id=target.player_id, target_username=target.username,
        damage_dealt=damage, target_hp_remaining=target.hp, killed=killed,
        buff_applied={"type": "slow", "duration": slow_duration} if slow_applied else None,
    )


def resolve_magic_damage(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a magic damage skill (e.g., Fireball).

    Magic damage uses ranged_damage as its base stat but applies a
    magic_damage_pct bonus instead of ranged-specific bonuses.
    Partially ignores armor (50% armor effectiveness vs magic).
    Supports entity-based targeting via target_id.
    """
    from app.core.combat import _get_equipment_bonuses, get_combat_config, is_in_range
    from app.core.skills import get_ranged_buff_multiplier, get_damage_taken_multiplier, get_damage_dealt_multiplier

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    damage_multiplier = effect.get("damage_multiplier", 2.0)
    skill_range = skill_def["range"] if skill_def["range"] > 0 else player.ranged_range
    requires_los = skill_def.get("requires_line_of_sight", True)

    # Entity-based target resolution
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

    # Range check against target's CURRENT position
    target_pos = Position(x=target.position.x, y=target.position.y)
    if not is_in_range(player.position, target_pos, skill_range):
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — target out of range",
        )

    # LOS check against target's CURRENT position
    if requires_los and not has_line_of_sight(
        player.position.x, player.position.y,
        target.position.x, target.position.y,
        obstacles,
    ):
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no line of sight",
        )

    # Calculate magic damage: uses ranged_damage base × multiplier
    config = get_combat_config()
    atk_bonuses = _get_equipment_bonuses(player)
    ranged_mult = get_ranged_buff_multiplier(player)
    raw_damage = int((player.ranged_damage + atk_bonuses.ranged_damage) * ranged_mult * damage_multiplier)

    # Phase 17: skill_damage_pct + magic_damage_pct bonuses
    skill_dmg_pct = getattr(player, 'skill_damage_pct', 0.0)
    magic_dmg_pct = getattr(player, 'magic_damage_pct', 0.0)
    raw_damage = int(raw_damage * (1.0 + skill_dmg_pct + magic_dmg_pct))

    # Magic damage partially ignores armor (50% armor effectiveness)
    def_bonuses = _get_equipment_bonuses(target)
    effective_armor = target.armor + def_bonuses.armor
    effective_armor = max(0, effective_armor - getattr(player, 'armor_pen', 0))
    magic_armor = int(effective_armor * 0.5)  # Magic ignores 50% of armor
    reduction = magic_armor * config.get("armor_reduction_per_point", 1)
    damage = max(1, raw_damage - reduction)
    # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
    dmg_taken_mult = get_damage_taken_multiplier(target)
    if dmg_taken_mult != 1.0:
        damage = max(1, int(damage * dmg_taken_mult))
    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble)
    dmg_dealt_mult = get_damage_dealt_multiplier(player)
    if dmg_dealt_mult != 1.0:
        damage = max(1, int(damage * dmg_dealt_mult))

    target.hp = max(0, target.hp - damage)
    killed = target.hp <= 0
    if killed:
        target.is_alive = False

    _apply_skill_cooldown(player, skill_def, dealt_damage=True)

    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} used {skill_def['name']} on {target.username} for {damage} magic damage"
                + (f" — {target.username} was killed!" if killed else ""),
        target_id=target.player_id, target_username=target.username,
        damage_dealt=damage, target_hp_remaining=target.hp, killed=killed,
    )


def resolve_aoe_damage_slow(
    player: PlayerState,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
) -> ActionResult:
    """Resolve a self-centered AoE damage + slow skill (e.g., Frost Nova).

    Targeting: self-centered. Deals flat magic damage and applies slow to all
    enemies within radius. Slow prevents movement but allows attacks/skills.
    """
    from app.core.combat import get_combat_config
    from app.core.skills import get_damage_dealt_multiplier, get_effective_armor, get_damage_taken_multiplier

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    radius = effect.get("radius", 2)
    base_damage = effect.get("base_damage", 12)
    slow_duration = effect.get("slow_duration", 2)

    # Phase 17: skill_damage_pct + magic_damage_pct bonuses on base damage
    skill_dmg_pct = getattr(player, 'skill_damage_pct', 0.0)
    magic_dmg_pct = getattr(player, 'magic_damage_pct', 0.0)
    base_damage = int(base_damage * (1.0 + skill_dmg_pct + magic_dmg_pct))

    total_damage = 0
    hits = 0
    kills = 0
    slowed_count = 0
    hit_names: list[str] = []
    killed_ids: list[str] = []

    config = get_combat_config()
    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble) — computed once for caster
    dmg_dealt_mult = get_damage_dealt_multiplier(player)

    for p in players.values():
        if not p.is_alive or p.team == player.team:
            continue
        dist = max(abs(p.position.x - player.position.x), abs(p.position.y - player.position.y))
        if dist <= radius:
            # Magic damage: 50% armor effectiveness
            effective_armor = get_effective_armor(p)
            magic_armor = int(effective_armor * 0.5)
            reduction = magic_armor * config.get("armor_reduction_per_point", 1)
            damage = max(1, base_damage - reduction)
            # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
            dmg_taken_mult = get_damage_taken_multiplier(p)
            if dmg_taken_mult != 1.0:
                damage = max(1, int(damage * dmg_taken_mult))
            if dmg_dealt_mult != 1.0:
                damage = max(1, int(damage * dmg_dealt_mult))

            p.hp = max(0, p.hp - damage)
            total_damage += damage
            hits += 1
            hit_names.append(f"{p.username}({damage})")

            if p.hp <= 0:
                p.is_alive = False
                kills += 1
                killed_ids.append(p.player_id)
            else:
                # Apply slow debuff to surviving enemies
                p.active_buffs = [b for b in p.active_buffs if b.get("type") != "slow"]
                slow_entry = {
                    "buff_id": skill_id,
                    "type": "slow",
                    "source_id": player.player_id,
                    "turns_remaining": slow_duration,
                    "stat": None,
                    "magnitude": 0,
                }
                p.active_buffs.append(slow_entry)
                slowed_count += 1

    _apply_skill_cooldown(player, skill_def, dealt_damage=hits > 0)

    if hits > 0:
        hit_str = ", ".join(hit_names)
        slow_str = f" — {slowed_count} SLOWED for {slow_duration} turn(s)!" if slowed_count > 0 else ""
        kill_str = f" — {kills} killed!" if kills > 0 else ""
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — hit {hits} enemies for {total_damage} total magic damage: {hit_str}{slow_str}{kill_str}",
            damage_dealt=total_damage, killed=kills > 0,
            buff_applied={"type": "aoe_damage_slow", "hits": hits, "kills": kills, "slowed": slowed_count, "killed_ids": killed_ids},
        )
    else:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — no enemies in the blast radius",
        )


def resolve_lifesteal_damage(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a lifesteal melee skill (e.g., Blood Strike).

    Targeting: entity (adjacent enemy), range 1.
    Deals melee damage × multiplier, then heals caster for heal_pct of damage dealt.
    Heal is based on post-armor final damage and is capped at max_hp.
    """
    from app.core.combat import _get_equipment_bonuses, get_combat_config
    from app.core.skills import get_melee_buff_multiplier, get_effective_armor, get_damage_taken_multiplier, get_damage_dealt_multiplier

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    damage_multiplier = effect.get("damage_multiplier", 1.4)
    heal_pct = effect.get("heal_pct", 0.40)

    # Entity-based target resolution
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

    # Must be adjacent (range 1 — Chebyshev distance)
    dx = abs(player.position.x - target.position.x)
    dy = abs(player.position.y - target.position.y)
    if dx > 1 or dy > 1 or (dx == 0 and dy == 0):
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — target not adjacent",
        )

    # Calculate damage
    config = get_combat_config()
    atk_bonuses = _get_equipment_bonuses(player)
    melee_mult = get_melee_buff_multiplier(player)
    raw_damage = int((player.attack_damage + atk_bonuses.attack_damage) * melee_mult * damage_multiplier)
    # Phase 16A: skill_damage_pct bonus
    skill_dmg_pct = getattr(player, 'skill_damage_pct', 0.0)
    raw_damage = int(raw_damage * (1.0 + skill_dmg_pct))
    effective_armor = get_effective_armor(target)
    reduction = effective_armor * config.get("armor_reduction_per_point", 1)
    damage = max(1, raw_damage - reduction)
    # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
    dmg_taken_mult = get_damage_taken_multiplier(target)
    if dmg_taken_mult != 1.0:
        damage = max(1, int(damage * dmg_taken_mult))
    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble)
    dmg_dealt_mult = get_damage_dealt_multiplier(player)
    if dmg_dealt_mult != 1.0:
        damage = max(1, int(damage * dmg_dealt_mult))

    # Apply damage
    target.hp = max(0, target.hp - damage)
    killed = target.hp <= 0
    if killed:
        target.is_alive = False

    # Lifesteal heal — based on post-armor final damage, capped at max_hp
    heal_amount = int(damage * heal_pct)
    if heal_amount > 0 and player.is_alive:
        player.hp = min(player.max_hp, player.hp + heal_amount)

    _apply_skill_cooldown(player, skill_def, dealt_damage=True)

    heal_msg = f", healed {heal_amount} HP" if heal_amount > 0 else ""
    kill_msg = f" — {target.username} was killed!" if killed else ""
    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} used {skill_def['name']} on {target.username} for {damage} damage{heal_msg}{kill_msg}",
        target_id=target.player_id, target_username=target.username,
        damage_dealt=damage, target_hp_remaining=target.hp, killed=killed,
        buff_applied={"type": "lifesteal", "heal": heal_amount},
    )


def resolve_lifesteal_aoe(
    player: PlayerState,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
) -> ActionResult:
    """Resolve a self-centered AoE lifesteal skill (e.g., Sanguine Burst).

    Targeting: self-centered AoE. Deals melee damage × multiplier to all enemies
    within radius (Chebyshev distance). Heals caster for heal_pct of TOTAL damage dealt.
    """
    from app.core.combat import _get_equipment_bonuses, get_combat_config
    from app.core.skills import get_melee_buff_multiplier, get_effective_armor, get_damage_taken_multiplier, get_damage_dealt_multiplier

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    radius = effect.get("radius", 1)
    damage_multiplier = effect.get("damage_multiplier", 0.7)
    heal_pct = effect.get("heal_pct", 0.50)

    # Calculate base melee damage with buffs
    config = get_combat_config()
    atk_bonuses = _get_equipment_bonuses(player)
    melee_mult = get_melee_buff_multiplier(player)
    base_raw = int((player.attack_damage + atk_bonuses.attack_damage) * melee_mult * damage_multiplier)
    # Phase 16A: skill_damage_pct bonus
    skill_dmg_pct = getattr(player, 'skill_damage_pct', 0.0)
    base_raw = int(base_raw * (1.0 + skill_dmg_pct))

    # Find all enemies within radius of caster position
    total_damage = 0
    hits = 0
    kills = 0
    killed_ids: list[str] = []
    hit_names: list[str] = []
    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble) — computed once for caster
    dmg_dealt_mult = get_damage_dealt_multiplier(player)

    for p in players.values():
        if not p.is_alive or p.team == player.team:
            continue
        dist = max(abs(p.position.x - player.position.x), abs(p.position.y - player.position.y))
        if dist <= radius and dist > 0:  # dist > 0: don't hit self
            # Per-target armor reduction
            effective_armor = get_effective_armor(p)
            reduction = effective_armor * config.get("armor_reduction_per_point", 1)
            damage = max(1, base_raw - reduction)
            # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
            dmg_taken_mult = get_damage_taken_multiplier(p)
            if dmg_taken_mult != 1.0:
                damage = max(1, int(damage * dmg_taken_mult))
            if dmg_dealt_mult != 1.0:
                damage = max(1, int(damage * dmg_dealt_mult))
            p.hp = max(0, p.hp - damage)
            total_damage += damage
            hits += 1
            hit_names.append(f"{p.username}({damage})")
            if p.hp <= 0:
                p.is_alive = False
                kills += 1
                killed_ids.append(p.player_id)

    # Lifesteal heal — based on TOTAL damage dealt across all targets
    heal_amount = int(total_damage * heal_pct) if total_damage > 0 else 0
    if heal_amount > 0 and player.is_alive:
        player.hp = min(player.max_hp, player.hp + heal_amount)

    _apply_skill_cooldown(player, skill_def, dealt_damage=hits > 0)

    if hits > 0:
        hit_str = ", ".join(hit_names)
        heal_msg = f" — healed {heal_amount} HP" if heal_amount > 0 else ""
        kill_str = f" — {kills} killed!" if kills > 0 else ""
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — hit {hits} enemies for {total_damage} total damage: {hit_str}{heal_msg}{kill_str}",
            damage_dealt=total_damage, killed=kills > 0,
            buff_applied={"type": "lifesteal_aoe", "hits": hits, "kills": kills, "heal": heal_amount, "killed_ids": killed_ids},
        )
    else:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — no enemies in range",
        )


def resolve_aoe_damage_slow_targeted(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
) -> ActionResult:
    """Resolve a ground-targeted AoE damage + slow skill (e.g., Miasma).

    Targeting: ground_aoe — player targets a tile at range, all enemies within
    radius of that tile take magic damage and are slowed. Based on
    resolve_aoe_damage_slow() (Frost Nova) but uses target_x/target_y as the
    AoE center instead of the caster's position.

    Phase 23B: Plague Doctor — Miasma.
    """
    from app.core.combat import get_combat_config, is_in_range
    from app.core.skills import get_damage_dealt_multiplier, get_effective_armor, get_damage_taken_multiplier

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    radius = effect.get("radius", 2)
    base_damage = effect.get("base_damage", 10)
    slow_duration = effect.get("slow_duration", 2)
    skill_range = skill_def.get("range", 5)
    requires_los = skill_def.get("requires_line_of_sight", True)

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

    # Phase 17: skill_damage_pct + magic_damage_pct bonuses on base damage
    skill_dmg_pct = getattr(player, 'skill_damage_pct', 0.0)
    magic_dmg_pct = getattr(player, 'magic_damage_pct', 0.0)
    base_damage = int(base_damage * (1.0 + skill_dmg_pct + magic_dmg_pct))

    total_damage = 0
    hits = 0
    kills = 0
    slowed_count = 0
    hit_names: list[str] = []
    killed_ids: list[str] = []

    config = get_combat_config()
    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble) — computed once for caster
    dmg_dealt_mult = get_damage_dealt_multiplier(player)

    for p in players.values():
        if not p.is_alive or p.team == player.team:
            continue
        dist = max(abs(p.position.x - target_x), abs(p.position.y - target_y))
        if dist <= radius:
            # Magic damage: 50% armor effectiveness
            effective_armor = get_effective_armor(p)
            magic_armor = int(effective_armor * 0.5)
            reduction = magic_armor * config.get("armor_reduction_per_point", 1)
            damage = max(1, base_damage - reduction)
            # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
            dmg_taken_mult = get_damage_taken_multiplier(p)
            if dmg_taken_mult != 1.0:
                damage = max(1, int(damage * dmg_taken_mult))
            if dmg_dealt_mult != 1.0:
                damage = max(1, int(damage * dmg_dealt_mult))

            p.hp = max(0, p.hp - damage)
            total_damage += damage
            hits += 1
            hit_names.append(f"{p.username}({damage})")

            if p.hp <= 0:
                p.is_alive = False
                kills += 1
                killed_ids.append(p.player_id)
            else:
                # Apply slow debuff to surviving enemies
                p.active_buffs = [b for b in p.active_buffs if b.get("type") != "slow"]
                slow_entry = {
                    "buff_id": skill_id,
                    "type": "slow",
                    "source_id": player.player_id,
                    "turns_remaining": slow_duration,
                    "stat": None,
                    "magnitude": 0,
                }
                p.active_buffs.append(slow_entry)
                slowed_count += 1

    _apply_skill_cooldown(player, skill_def, dealt_damage=hits > 0)

    if hits > 0:
        hit_str = ", ".join(hit_names)
        slow_str = f" — {slowed_count} SLOWED for {slow_duration} turn(s)!" if slowed_count > 0 else ""
        kill_str = f" — {kills} killed!" if kills > 0 else ""
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — hit {hits} enemies for {total_damage} total magic damage: {hit_str}{slow_str}{kill_str}",
            damage_dealt=total_damage, killed=kills > 0,
            to_x=target_x, to_y=target_y,
            buff_applied={"type": "aoe_damage_slow_targeted", "hits": hits, "kills": kills, "slowed": slowed_count, "killed_ids": killed_ids},
        )
    else:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — no enemies in the blast radius",
            to_x=target_x, to_y=target_y,
        )


def resolve_melee_damage_slow(
    player: PlayerState,
    target_x: int | None,
    target_y: int | None,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a melee damage + slow skill (Soul Rend).

    Targeting: enemy_adjacent. Deals melee damage scaled by a multiplier,
    then applies a slow debuff preventing movement (but allowing attacks/skills).
    Phase 25B: Revenant Soul Rend skill.
    """
    from app.core.combat import _get_equipment_bonuses, get_combat_config
    from app.core.skills import get_melee_buff_multiplier, get_effective_armor, get_damage_taken_multiplier, get_damage_dealt_multiplier

    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    damage_multiplier = effect.get("damage_multiplier", 1.2)
    slow_duration = effect.get("slow_duration", 2)

    # Entity-based target resolution
    target = _resolve_skill_entity_target(player, target_id, target_x, target_y, players, ally_target=False)

    if target is None:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — no enemy at target",
        )

    # Must be adjacent (Chebyshev distance 1)
    dx = abs(player.position.x - target.position.x)
    dy = abs(player.position.y - target.position.y)
    if dx > 1 or dy > 1 or (dx == 0 and dy == 0):
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=False,
            message=f"{player.username} {skill_def['name']} failed — target not adjacent",
        )

    # Calculate damage (melee-based)
    config = get_combat_config()
    atk_bonuses = _get_equipment_bonuses(player)
    melee_mult = get_melee_buff_multiplier(player)
    raw_damage = int((player.attack_damage + atk_bonuses.attack_damage) * melee_mult * damage_multiplier)
    # Phase 16A: skill_damage_pct bonus
    skill_dmg_pct = getattr(player, 'skill_damage_pct', 0.0)
    raw_damage = int(raw_damage * (1.0 + skill_dmg_pct))
    effective_armor = get_effective_armor(target)
    reduction = effective_armor * config.get("armor_reduction_per_point", 1)
    damage = max(1, raw_damage - reduction)
    # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
    dmg_taken_mult = get_damage_taken_multiplier(target)
    if dmg_taken_mult != 1.0:
        damage = max(1, int(damage * dmg_taken_mult))
    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble)
    dmg_dealt_mult = get_damage_dealt_multiplier(player)
    if dmg_dealt_mult != 1.0:
        damage = max(1, int(damage * dmg_dealt_mult))

    target.hp = max(0, target.hp - damage)
    killed = target.hp <= 0
    if killed:
        target.is_alive = False

    # Apply slow debuff (only if target survived)
    slow_applied = False
    if not killed and target.is_alive:
        # Refresh existing slow
        target.active_buffs = [b for b in target.active_buffs if b.get("type") != "slow"]
        slow_entry = {
            "buff_id": skill_id,
            "type": "slow",
            "source_id": player.player_id,
            "turns_remaining": slow_duration,
            "stat": None,
            "magnitude": 0,
        }
        target.active_buffs.append(slow_entry)
        slow_applied = True

    _apply_skill_cooldown(player, skill_def, dealt_damage=True)

    slow_msg = f" — SLOWED for {slow_duration} turn(s)!" if slow_applied else ""
    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} used {skill_def['name']} on {target.username} for {damage} damage{slow_msg}"
                + (f" — {target.username} was killed!" if killed else ""),
        target_id=target.player_id, target_username=target.username,
        damage_dealt=damage, target_hp_remaining=target.hp, killed=killed,
        buff_applied={"type": "slow", "duration": slow_duration} if slow_applied else None,
    )
