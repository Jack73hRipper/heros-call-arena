"""Buff application skill effect handlers."""
from __future__ import annotations

from app.models.player import PlayerState
from app.models.actions import ActionResult, ActionType
from app.core.skill_effects._helpers import _apply_skill_cooldown


def resolve_buff(
    player: PlayerState,
    skill_def: dict,
    target_x: int | None = None,
    target_y: int | None = None,
    players: dict[str, PlayerState] | None = None,
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a buff skill (e.g., War Cry self-buff, Shield of Faith ally buff).

    Supports self-targeting and ally-targeting based on skill targeting type.
    Supports entity-based targeting via target_id.
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    stat = effect["stat"]
    magnitude = effect["magnitude"]
    duration = effect["duration_turns"]

    # Determine target (self or ally)
    target = player  # default to self
    targeting = skill_def.get("targeting", "self")

    if targeting in ("ally_or_self", "ally_ranged") and players:
        if target_id:
            # Entity-based lookup for ally buffs
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

        # Range check for ally target (uses target's CURRENT position)
        if target.player_id != player.player_id:
            dx = abs(player.position.x - target.position.x)
            dy = abs(player.position.y - target.position.y)
            skill_range = skill_def.get("range", 1)
            if dx > skill_range or dy > skill_range:
                return ActionResult(
                    player_id=player.player_id,
                    username=player.username,
                    action_type=ActionType.SKILL,
                    skill_id=skill_id,
                    success=False,
                    message=f"{player.username} {skill_def['name']} failed — target out of range",
                )

    buff_entry = {
        "buff_id": skill_id,
        "type": "buff",
        "stat": stat,
        "magnitude": magnitude,
        "turns_remaining": duration,
    }
    target.active_buffs.append(buff_entry)

    # Phase 22B: Multi-effect buff — apply secondary HoT if present (Crimson Veil)
    effects = skill_def.get("effects", [])
    if len(effects) > 1 and effects[1].get("type") == "hot":
        hot_effect = effects[1]
        hot_entry = {
            "buff_id": f"{skill_id}_hot",
            "type": "hot",
            "heal_per_tick": hot_effect.get("heal_per_turn", 0),
            "turns_remaining": hot_effect.get("duration_turns", duration),
            "stat": "hot",
            "magnitude": hot_effect.get("heal_per_turn", 0),
        }
        target.active_buffs.append(hot_entry)

    _apply_skill_cooldown(player, skill_def)

    target_name = target.username if target.player_id != player.player_id else "self"
    return ActionResult(
        player_id=player.player_id,
        username=player.username,
        action_type=ActionType.SKILL,
        skill_id=skill_id,
        success=True,
        message=f"{player.username} used {skill_def['name']} on {target_name}",
        target_id=target.player_id,
        target_username=target.username,
        buff_applied={"stat": stat, "magnitude": magnitude, "duration": duration},
    )


def resolve_aoe_buff(
    player: PlayerState,
    skill_def: dict,
    players: dict[str, PlayerState],
) -> ActionResult:
    """Resolve an AoE buff skill centered on self (e.g., Ballad of Might).

    Targeting: self-centered. Applies a buff to all alive allies (including self)
    within Chebyshev radius. Mirrors resolve_aoe_heal pattern but applies a buff
    entry instead of healing.

    Phase 21B: Bard — Ballad of Might (+30% all damage for 3 turns).
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    radius = effect.get("radius", 2)
    stat = effect["stat"]
    magnitude = effect["magnitude"]
    duration = effect["duration_turns"]

    buffed_count = 0
    buffed_names: list[str] = []

    for p in players.values():
        if not p.is_alive or p.team != player.team:
            continue
        dist = max(abs(p.position.x - player.position.x), abs(p.position.y - player.position.y))
        if dist <= radius:
            # Remove existing buff from same skill (refresh, don't stack)
            p.active_buffs = [b for b in p.active_buffs if b.get("buff_id") != skill_id]

            buff_entry = {
                "buff_id": skill_id,
                "type": "buff",
                "stat": stat,
                "magnitude": magnitude,
                "turns_remaining": duration,
            }
            p.active_buffs.append(buff_entry)
            buffed_count += 1
            name = "self" if p.player_id == player.player_id else p.username
            buffed_names.append(name)

    _apply_skill_cooldown(player, skill_def)

    if buffed_count > 0:
        buff_str = ", ".join(buffed_names)
        pct = int((magnitude - 1) * 100)
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — buffed {buffed_count} allies (+{pct}% damage, {duration} turns): {buff_str}",
            buff_applied={"type": "aoe_buff", "stat": stat, "magnitude": magnitude, "duration": duration, "buffed_count": buffed_count},
        )
    else:
        return ActionResult(
            player_id=player.player_id, username=player.username,
            action_type=ActionType.SKILL, skill_id=skill_id, success=True,
            message=f"{player.username} used {skill_def['name']} — no allies in range to buff",
        )


def resolve_damage_absorb(
    player: PlayerState,
    skill_def: dict,
) -> ActionResult:
    """Resolve a damage absorb skill (e.g., Bone Shield).

    Creates a shield that absorbs N incoming damage before breaking.
    Phase 18I: Skeleton identity skill.
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    absorb_amount = effect.get("absorb_amount", 25)
    duration = effect.get("duration_turns", 4)

    # Remove existing absorb buff if present (refresh, don't stack)
    player.active_buffs = [b for b in player.active_buffs if b.get("buff_id") != skill_id]

    absorb_entry = {
        "buff_id": skill_id,
        "type": "damage_absorb",
        "absorb_remaining": absorb_amount,
        "absorb_total": absorb_amount,
        "turns_remaining": duration,
        "stat": None,
        "magnitude": absorb_amount,
    }
    player.active_buffs.append(absorb_entry)
    _apply_skill_cooldown(player, skill_def)

    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} activated {skill_def['name']} (absorbs {absorb_amount} damage)",
        buff_applied={"type": "damage_absorb", "absorb_amount": absorb_amount, "duration": duration},
    )


def resolve_shield_charges(
    player: PlayerState,
    skill_def: dict,
) -> ActionResult:
    """Resolve a charge-based reflective shield skill (e.g., Ward).

    Grants charges that consume on hit and reflect damage back to attackers.
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    charges = effect.get("charges", 3)
    reflect_damage = effect.get("reflect_damage", 8)
    duration = effect.get("duration_turns", 6)

    # Remove existing ward if present (refresh, don't stack)
    player.active_buffs = [b for b in player.active_buffs if b.get("buff_id") != skill_id]

    ward_entry = {
        "buff_id": skill_id,
        "type": "shield_charges",
        "charges": charges,
        "reflect_damage": reflect_damage,
        "turns_remaining": duration,
        "stat": None,
        "magnitude": reflect_damage,
    }
    player.active_buffs.append(ward_entry)
    _apply_skill_cooldown(player, skill_def)

    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} activated {skill_def['name']} ({charges} charges, reflects {reflect_damage} damage per hit)",
        buff_applied={"type": "shield_charges", "charges": charges, "reflect_damage": reflect_damage, "duration": duration},
    )


def resolve_evasion(
    player: PlayerState,
    skill_def: dict,
) -> ActionResult:
    """Resolve an evasion self-buff (e.g., Evasion).

    Grants dodge charges that negate incoming attacks. Mirrors Ward pattern.
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    charges = effect.get("charges", 2)
    duration = effect.get("duration_turns", 4)

    # Remove existing evasion if present (refresh, don't stack)
    player.active_buffs = [b for b in player.active_buffs if b.get("buff_id") != skill_id]

    evasion_entry = {
        "buff_id": skill_id,
        "type": "evasion",
        "charges": charges,
        "turns_remaining": duration,
        "stat": None,
        "magnitude": 0,
    }
    player.active_buffs.append(evasion_entry)
    _apply_skill_cooldown(player, skill_def)

    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} activated {skill_def['name']} ({charges} dodge charges, lasts {duration} turns)",
        buff_applied={"type": "evasion", "charges": charges, "duration": duration},
    )


def resolve_conditional_buff(
    player: PlayerState,
    skill_def: dict,
) -> ActionResult:
    """Resolve a conditional self-buff skill (e.g., Blood Frenzy).

    Requires the caster to be below a certain HP threshold to activate.
    On success: applies instant heal + melee damage buff for N turns.
    On failure (HP too high): returns success=False, does NOT consume cooldown.
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    hp_threshold = effect.get("hp_threshold", 0.40)
    instant_heal = effect.get("instant_heal", 15)
    stat = effect.get("stat", "melee_damage_multiplier")
    magnitude = effect.get("magnitude", 1.5)
    duration = effect.get("duration_turns", 3)

    # HP threshold check — must be BELOW threshold to activate
    if player.max_hp <= 0 or (player.hp / player.max_hp) >= hp_threshold:
        return ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.SKILL,
            skill_id=skill_id,
            success=False,
            message=f"{player.username} {skill_def['name']} failed — not wounded enough (need below {int(hp_threshold * 100)}% HP)",
        )

    # Apply instant heal (capped at max_hp)
    old_hp = player.hp
    player.hp = min(player.max_hp, player.hp + instant_heal)
    actual_heal = player.hp - old_hp

    # Apply buff
    buff_entry = {
        "buff_id": skill_id,
        "type": "buff",
        "stat": stat,
        "magnitude": magnitude,
        "turns_remaining": duration,
    }
    player.active_buffs.append(buff_entry)

    _apply_skill_cooldown(player, skill_def)

    return ActionResult(
        player_id=player.player_id,
        username=player.username,
        action_type=ActionType.SKILL,
        skill_id=skill_id,
        success=True,
        message=f"{player.username} used {skill_def['name']} — healed {actual_heal} HP, gained +{int((magnitude - 1) * 100)}% melee damage for {duration} turns",
        target_id=player.player_id,
        target_username=player.username,
        buff_applied={"stat": stat, "magnitude": magnitude, "duration": duration, "heal": actual_heal},
    )


def resolve_thorns_buff(
    player: PlayerState,
    skill_def: dict,
) -> ActionResult:
    """Resolve a thorns self-buff (Grave Thorns).

    Grants a thorns aura — any attacker that hits the Revenant takes flat
    retaliation damage per hit for the buff duration. No charge limit.
    Phase 25B: Revenant Grave Thorns skill.
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    thorns_damage = effect.get("thorns_damage", 10)
    duration = effect.get("duration_turns", 3)

    # Remove existing thorns buff if present (refresh, don't stack)
    player.active_buffs = [b for b in player.active_buffs if b.get("buff_id") != skill_id]

    thorns_entry = {
        "buff_id": skill_id,
        "type": "thorns_buff",
        "stat": "thorns_damage",
        "magnitude": thorns_damage,
        "turns_remaining": duration,
    }
    player.active_buffs.append(thorns_entry)
    _apply_skill_cooldown(player, skill_def)

    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} activated {skill_def['name']} (reflects {thorns_damage} damage per hit, {duration} turns)",
        buff_applied={"type": "thorns_buff", "thorns_damage": thorns_damage, "duration": duration},
    )


def resolve_cheat_death(
    player: PlayerState,
    skill_def: dict,
) -> ActionResult:
    """Resolve a cheat-death self-buff (Undying Will).

    Places a buff on self. If the player's HP reaches 0 while the buff is
    active, they revive at a percentage of max HP instead of dying.
    The buff is consumed on trigger or expires after duration.
    Phase 25B: Revenant Undying Will skill.
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    revive_hp_pct = effect.get("revive_hp_pct", 0.30)
    duration = effect.get("duration_turns", 5)

    # Remove existing cheat death buff if present (refresh, don't stack)
    player.active_buffs = [b for b in player.active_buffs if b.get("buff_id") != skill_id]

    cheat_death_entry = {
        "buff_id": skill_id,
        "type": "cheat_death",
        "stat": "cheat_death",
        "revive_hp_pct": revive_hp_pct,
        "turns_remaining": duration,
        "magnitude": 0,
    }
    player.active_buffs.append(cheat_death_entry)
    _apply_skill_cooldown(player, skill_def)

    revive_pct_str = int(revive_hp_pct * 100)
    return ActionResult(
        player_id=player.player_id, username=player.username,
        action_type=ActionType.SKILL, skill_id=skill_id, success=True,
        message=f"{player.username} activated {skill_def['name']} (revive at {revive_pct_str}% HP if killed, {duration} turns)",
        buff_applied={"type": "cheat_death", "revive_hp_pct": revive_hp_pct, "duration": duration},
    )


def resolve_buff_cleanse(
    player: PlayerState,
    skill_def: dict,
    target_x: int | None = None,
    target_y: int | None = None,
    players: dict[str, PlayerState] | None = None,
    target_id: str | None = None,
) -> ActionResult:
    """Resolve a buff + DoT cleanse skill (e.g., Inoculate).

    Targeting: ally_or_self — applies a stat buff to the target AND removes all
    active DoT effects from the target's active_buffs.

    Phase 23B: Plague Doctor — Inoculate (+3 armor, 3 turns, cleanse all DoTs).
    """
    skill_id = skill_def["skill_id"]
    effect = skill_def["effects"][0]
    stat = effect["stat"]
    magnitude = effect["magnitude"]
    duration = effect["duration_turns"]
    cleanse_dots = effect.get("cleanse_dots", False)

    # Determine target (self or ally) — same logic as resolve_buff()
    target = player  # default to self
    targeting = skill_def.get("targeting", "self")

    if targeting in ("ally_or_self", "ally_ranged") and players:
        if target_id:
            # Entity-based lookup for ally buffs
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

        # Range check for ally target (uses target's CURRENT position)
        if target.player_id != player.player_id:
            dx = abs(player.position.x - target.position.x)
            dy = abs(player.position.y - target.position.y)
            skill_range = skill_def.get("range", 3)
            if max(dx, dy) > skill_range:
                return ActionResult(
                    player_id=player.player_id,
                    username=player.username,
                    action_type=ActionType.SKILL,
                    skill_id=skill_id,
                    success=False,
                    message=f"{player.username} {skill_def['name']} failed — target out of range",
                )

    # Apply stat buff
    buff_entry = {
        "buff_id": skill_id,
        "type": "buff",
        "stat": stat,
        "magnitude": magnitude,
        "turns_remaining": duration,
    }
    target.active_buffs.append(buff_entry)

    # Cleanse DoTs if configured
    dots_cleansed = 0
    if cleanse_dots:
        original_count = len(target.active_buffs)
        target.active_buffs = [b for b in target.active_buffs if b.get("type") != "dot"]
        dots_cleansed = original_count - len(target.active_buffs)

    _apply_skill_cooldown(player, skill_def)

    target_name = target.username if target.player_id != player.player_id else "self"
    cleanse_str = f", cleansed {dots_cleansed} DoT(s)" if dots_cleansed > 0 else ""
    return ActionResult(
        player_id=player.player_id,
        username=player.username,
        action_type=ActionType.SKILL,
        skill_id=skill_id,
        success=True,
        message=f"{player.username} used {skill_def['name']} on {target_name} (+{magnitude} {stat} for {duration} turns{cleanse_str})",
        target_id=target.player_id,
        target_username=target.username,
        buff_applied={"stat": stat, "magnitude": magnitude, "duration": duration, "dots_cleansed": dots_cleansed},
    )
