"""
Combat Phase — Phase 2 + 3: Ranged and melee attack resolution.

Includes entity-based target resolution, LOS checks, cooldowns,
dodge/evasion, affix on-hit effects, thorns, ward reflect, plaguebow,
Grimfang on-kill, Soulreaver lifesteal, Wraithmantle retaliate.
Phase 26C: Totem targeting — enemies can attack and destroy totems.
"""

from __future__ import annotations

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType, ActionResult
from app.core.combat import (
    calculate_damage,
    calculate_ranged_damage,
    apply_damage,
    is_adjacent,
    can_ranged_attack,
    apply_ranged_cooldown,
    are_allies,
    apply_affix_on_hit_effects,
)
from app.core.skills import is_stunned, trigger_evasion_dodge
from app.core.turn_phases.portal_phase import _is_channeling


# ---------- Phase 26C: Totem Targeting Helper ----------

def _try_damage_totem(
    attacker: PlayerState,
    target_x: int | None,
    target_y: int | None,
    match_state,
    results: list[ActionResult],
    attack_type: str,  # "melee" or "ranged"
) -> bool:
    """Check if there is an enemy totem at the target tile and damage it.

    Totems have no armor — damage is applied directly to totem.hp.
    Returns True if a totem was found and attacked, False otherwise.
    """
    if match_state is None or target_x is None or target_y is None:
        return False
    if not hasattr(match_state, "totems") or not match_state.totems:
        return False

    for totem in match_state.totems:
        if totem.get("x") == target_x and totem.get("y") == target_y:
            # Don't attack your own team's totem
            if totem.get("team") == attacker.team:
                return False
            # Calculate damage (use melee or ranged base damage)
            if attack_type == "melee":
                damage = getattr(attacker, "attack_damage", 10)
            else:
                damage = getattr(attacker, "ranged_damage", 10)
            totem["hp"] = max(0, totem.get("hp", 0) - damage)
            killed = totem["hp"] <= 0
            totem_name = totem.get("type", "totem").replace("_", " ").title()
            action_type = ActionType.ATTACK if attack_type == "melee" else ActionType.RANGED_ATTACK
            results.append(ActionResult(
                player_id=attacker.player_id,
                username=attacker.username,
                action_type=action_type,
                success=True,
                message=f"{attacker.username} hit {totem_name} for {damage} damage"
                        + (f" — {totem_name} was destroyed!" if killed else f" ({totem['hp']} HP remaining)"),
                damage_dealt=damage,
                target_hp_remaining=totem["hp"],
            ))
            # Remove destroyed totem
            if killed and totem in match_state.totems:
                match_state.totems.remove(totem)
            return True

    return False


def _resolve_entity_target(
    action: PlayerAction,
    players: dict[str, PlayerState],
    attacker: PlayerState,
    ally_target: bool = False,
) -> "PlayerState | None":
    """Look up the intended target using entity-based targeting (target_id).

    Falls back to tile-based lookup if no target_id is set (backward compat).
    For enemy targeting: ensures target is alive and not on the same team.
    For ally targeting (ally_target=True): ensures target is alive and same team.

    Returns the target PlayerState, or None if no valid target found.
    """
    # --- Entity-based lookup (preferred) ---
    if action.target_id:
        candidate = players.get(action.target_id)
        if candidate and candidate.is_alive:
            if ally_target:
                if candidate.team == attacker.team or candidate.player_id == attacker.player_id:
                    return candidate
            else:
                if not are_allies(attacker, candidate):
                    return candidate
        return None

    # --- Tile-based fallback (backward compat) ---
    if action.target_x is None or action.target_y is None:
        return None
    for p in players.values():
        if p.is_alive and p.position.x == action.target_x and p.position.y == action.target_y:
            if ally_target:
                if p.team == attacker.team or p.player_id == attacker.player_id:
                    return p
            else:
                if not are_allies(attacker, p):
                    return p
            break
    return None


def _resolve_ranged(
    ranged_actions: list[PlayerAction],
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    config: dict,
    results: list[ActionResult],
    deaths: list[str],
    portal_context: dict | None = None,
    match_state=None,  # Phase 26C: MatchState for totem targeting
) -> None:
    """Phase 2 — Resolve ranged attacks with LOS and cooldown validation."""
    ranged_cd = config.get("ranged_cooldown", 3)

    for action in ranged_actions:
        player = players.get(action.player_id)
        if not player or not player.is_alive:
            continue
        if action.target_x is None or action.target_y is None:
            continue

        # Phase 12C: Extracted heroes skip all phases
        if player.extracted:
            continue
        # Phase 12C: Channeling players cannot attack
        if portal_context and _is_channeling(player.player_id, portal_context):
            continue

        # Phase 12: Stunned units cannot attack
        if is_stunned(player):
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.RANGED_ATTACK,
                success=False,
                message=f"{player.username} is stunned and cannot attack!",
            ))
            continue

        # --- Entity-based target resolution ---
        # Look up the intended target by ID (falls back to tile if no target_id)
        target = _resolve_entity_target(action, players, player)

        # If we found a target by entity ID, validate range/LOS against
        # the target's CURRENT position (they may have moved this turn)
        if target:
            actual_tx, actual_ty = target.position.x, target.position.y
        else:
            actual_tx, actual_ty = action.target_x, action.target_y

        # Validate ranged attack — use per-player ranged_range (class-based)
        player_range = getattr(player, 'ranged_range', config.get("ranged_range", 5))
        can_fire, reason = can_ranged_attack(
            player, actual_tx, actual_ty, player_range, obstacles
        )

        if not can_fire:
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.RANGED_ATTACK,
                success=False,
                message=f"{player.username} ranged attack failed — {reason}",
            ))
            continue

        # Apply cooldown regardless of hit/miss
        apply_ranged_cooldown(player, ranged_cd)

        if not target:
            # Phase 26C: Check if a totem is at the target tile
            totem_hit = _try_damage_totem(
                player, actual_tx, actual_ty, match_state, results, "ranged"
            )
            if totem_hit:
                continue
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.RANGED_ATTACK,
                success=False,
                message=f"{player.username} ranged attack missed — no enemy at target",
            ))
            continue

        # Phase 12: Evasion dodge check — target may dodge the attack entirely
        if trigger_evasion_dodge(target):
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.RANGED_ATTACK,
                success=False,
                message=f"{player.username} shot at {target.username} — DODGED!",
                target_id=target.player_id,
                target_username=target.username,
            ))
            continue

        damage, combat_info = calculate_ranged_damage(player, target)

        # Phase 16A: Dodge from stat-based dodge chance (separate from Evasion buff)
        if combat_info["is_dodged"]:
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.RANGED_ATTACK,
                success=False,
                message=f"{player.username} shot at {target.username} — DODGED!",
                target_id=target.player_id,
                target_username=target.username,
            ))
            continue

        killed = apply_damage(target, damage)

        # Phase 16A: Build enhanced combat message
        crit_tag = " (CRIT!)" if combat_info["is_crit"] else ""
        results.append(ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.RANGED_ATTACK,
            success=True,
            message=f"{player.username} shot {target.username} for {damage} damage{crit_tag}"
                    + (f" — {target.username} was killed!" if killed else ""),
            target_id=target.player_id,
            target_username=target.username,
            damage_dealt=damage,
            target_hp_remaining=target.hp,
            killed=killed,
            is_crit=combat_info["is_crit"],
        ))

        if killed:
            deaths.append(target.player_id)

        # Phase 18D: Affix on-hit effects (Cursed, Cold Enchanted, Mana Burn, Spectral Hit)
        if damage > 0 and getattr(player, 'affixes', None):
            import random as _rng_mod
            apply_affix_on_hit_effects(player, target, damage, combat_info)
            for affix_effect in combat_info.get("affix_on_hit", []):
                if affix_effect["effect"] == "slow":
                    results.append(ActionResult(
                        player_id=player.player_id,
                        username=player.username,
                        action_type=ActionType.RANGED_ATTACK,
                        success=True,
                        message=f"{player.username}'s Cold Enchanted slows {target.username} for {affix_effect['duration']} turn(s)!",
                        target_id=target.player_id,
                        target_username=target.username,
                        is_tick=True,
                    ))
                elif affix_effect["effect"] == "life_steal":
                    results.append(ActionResult(
                        player_id=player.player_id,
                        username=player.username,
                        action_type=ActionType.RANGED_ATTACK,
                        success=True,
                        message=f"{player.username}'s Spectral Hit heals {affix_effect['healed']} HP!",
                        heal_amount=affix_effect["healed"],
                        target_id=player.player_id,
                        target_username=player.username,
                        target_hp_remaining=player.hp,
                        is_tick=True,
                    ))
                elif affix_effect["effect"] == "extend_cooldown":
                    results.append(ActionResult(
                        player_id=player.player_id,
                        username=player.username,
                        action_type=ActionType.RANGED_ATTACK,
                        success=True,
                        message=f"{player.username}'s {affix_effect['affix'].replace('_', ' ').title()} extends {target.username}'s cooldowns by {affix_effect['turns_added']} turn(s)!",
                        target_id=target.player_id,
                        target_username=target.username,
                        is_tick=True,
                    ))

        # Phase 16D: Plaguebow poison DoT — apply to target on ranged hit
        if combat_info.get("plaguebow_applied") and target.is_alive:
            dot_info = combat_info.get("plaguebow_dot", {})
            poison_buff = {
                "buff_id": dot_info.get("dot_id", "plaguebow_poison"),
                "type": "dot",
                "turns_remaining": dot_info.get("duration", 2),
                "damage_per_tick": dot_info.get("damage_per_tick", 4),
                "source": player.player_id,
            }
            if not hasattr(target, 'active_buffs'):
                target.active_buffs = []
            # Don't stack — refresh if already present
            target.active_buffs = [b for b in target.active_buffs if b.get("buff_id") != poison_buff["buff_id"]]
            target.active_buffs.append(poison_buff)
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.RANGED_ATTACK,
                success=True,
                message=f"{player.username}'s Plaguebow poisons {target.username} ({dot_info.get('damage_per_tick', 4)} dmg/turn for {dot_info.get('duration', 2)} turns)",
                target_id=target.player_id,
                target_username=target.username,
                is_tick=True,
            ))

        # Phase 16A: Life on hit message
        if combat_info["life_on_hit_healed"] > 0:
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.RANGED_ATTACK,
                success=True,
                message=f"{player.username} healed {combat_info['life_on_hit_healed']} HP from Life on Hit",
                heal_amount=combat_info["life_on_hit_healed"],
                target_id=player.player_id,
                target_username=player.username,
                target_hp_remaining=player.hp,
                is_tick=True,
            ))

        # Phase 16A: Thorns damage message
        if combat_info["thorns_damage"] > 0:
            thorns_killed = not player.is_alive
            results.append(ActionResult(
                player_id=target.player_id,
                username=target.username,
                action_type=ActionType.RANGED_ATTACK,
                success=True,
                message=f"{target.username}'s Thorns reflects {combat_info['thorns_damage']} damage to {player.username}!"
                        + (f" — {player.username} was killed!" if thorns_killed else ""),
                target_id=player.player_id,
                target_username=player.username,
                damage_dealt=combat_info["thorns_damage"],
                target_hp_remaining=player.hp,
                killed=thorns_killed,
            ))
            if thorns_killed:
                deaths.append(player.player_id)

        # Phase 11: Ward reflect on ranged hits too
        if target.is_alive or not killed:
            from app.core.skills import trigger_ward_reflect
            reflected = trigger_ward_reflect(target, player)
            if reflected > 0:
                attacker_killed = not player.is_alive
                results.append(ActionResult(
                    player_id=target.player_id,
                    username=target.username,
                    action_type=ActionType.SKILL,
                    skill_id="ward",
                    success=True,
                    message=f"{target.username}'s Ward reflects {reflected} damage to {player.username}!"
                            + (f" — {player.username} was killed!" if attacker_killed else ""),
                    target_id=player.player_id,
                    target_username=player.username,
                    damage_dealt=reflected,
                    target_hp_remaining=player.hp,
                    killed=attacker_killed,
                ))
                if attacker_killed:
                    deaths.append(player.player_id)


def _resolve_melee(
    melee_actions: list[PlayerAction],
    players: dict[str, PlayerState],
    pre_move_occupants: dict[tuple[int, int], str],
    results: list[ActionResult],
    deaths: list[str],
    portal_context: dict | None = None,
    match_state=None,  # Phase 26C: MatchState for totem targeting
) -> None:
    """Phase 3 — Resolve melee attacks with target tracking through movement."""
    for action in melee_actions:
        player = players.get(action.player_id)
        if not player or not player.is_alive:
            continue

        # Phase 12C: Extracted heroes skip all phases
        if player.extracted:
            continue
        # Phase 12C: Channeling players cannot attack
        if portal_context and _is_channeling(player.player_id, portal_context):
            continue

        # Phase 12: Stunned units cannot attack
        if is_stunned(player):
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.ATTACK,
                success=False,
                message=f"{player.username} is stunned and cannot attack!",
            ))
            continue

        if action.target_x is None or action.target_y is None:
            continue

        # --- Entity-based target resolution (preferred) ---
        target = _resolve_entity_target(action, players, player)

        # --- Tile-based fallback with pre_move_occupants tracking ---
        if not target:
            target_pos = Position(x=action.target_x, y=action.target_y)

            # First: look for an enemy still at the originally-targeted tile
            for p in players.values():
                if p.is_alive and p.position.x == action.target_x and p.position.y == action.target_y:
                    if not are_allies(player, p):
                        target = p
                    break

            # Second: if nobody is there anymore, the target may have moved.
            # Look up who was at that tile before movement and check if they're
            # still within melee range.
            if not target:
                original_occupant_id = pre_move_occupants.get((action.target_x, action.target_y))
                if original_occupant_id and original_occupant_id != player.player_id:
                    candidate = players.get(original_occupant_id)
                    if (candidate and candidate.is_alive
                            and not are_allies(player, candidate)
                            and is_adjacent(player.position, candidate.position)):
                        target = candidate

        # Check adjacency against the target's actual current position
        if target:
            if not is_adjacent(player.position, target.position):
                results.append(ActionResult(
                    player_id=player.player_id,
                    username=player.username,
                    action_type=ActionType.ATTACK,
                    success=False,
                    message=f"{player.username} attack missed — target out of range",
                ))
                continue
        else:
            # No target found at original tile or tracked through movement
            target_pos = Position(x=action.target_x, y=action.target_y)
            if not is_adjacent(player.position, target_pos):
                results.append(ActionResult(
                    player_id=player.player_id,
                    username=player.username,
                    action_type=ActionType.ATTACK,
                    success=False,
                    message=f"{player.username} attack missed — target out of range",
                ))
            else:
                # Phase 26C: Check if a totem is at the target tile
                totem_hit = _try_damage_totem(
                    player, action.target_x, action.target_y, match_state, results, "melee"
                )
                if not totem_hit:
                    results.append(ActionResult(
                        player_id=player.player_id,
                        username=player.username,
                        action_type=ActionType.ATTACK,
                        success=False,
                        message=f"{player.username} attack missed — no enemy at target",
                    ))
            continue

        # Phase 12: Evasion dodge check — target may dodge the melee attack
        if trigger_evasion_dodge(target):
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.ATTACK,
                success=False,
                message=f"{player.username} attacked {target.username} — DODGED!",
                target_id=target.player_id,
                target_username=target.username,
            ))
            continue

        damage, combat_info = calculate_damage(player, target)

        # Phase 16A: Dodge from stat-based dodge chance (separate from Evasion buff)
        if combat_info["is_dodged"]:
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.ATTACK,
                success=False,
                message=f"{player.username} attacked {target.username} — DODGED!",
                target_id=target.player_id,
                target_username=target.username,
            ))
            continue

        killed = apply_damage(target, damage)

        # Phase 18D: Affix on-hit effects (Cursed, Cold Enchanted, Mana Burn, Spectral Hit)
        if damage > 0 and getattr(player, 'affixes', None):
            apply_affix_on_hit_effects(player, target, damage, combat_info)
            for affix_effect in combat_info.get("affix_on_hit", []):
                if affix_effect["effect"] == "slow":
                    results.append(ActionResult(
                        player_id=player.player_id,
                        username=player.username,
                        action_type=ActionType.ATTACK,
                        success=True,
                        message=f"{player.username}'s Cold Enchanted slows {target.username} for {affix_effect['duration']} turn(s)!",
                        target_id=target.player_id,
                        target_username=target.username,
                        is_tick=True,
                    ))
                elif affix_effect["effect"] == "life_steal":
                    results.append(ActionResult(
                        player_id=player.player_id,
                        username=player.username,
                        action_type=ActionType.ATTACK,
                        success=True,
                        message=f"{player.username}'s Spectral Hit heals {affix_effect['healed']} HP!",
                        heal_amount=affix_effect["healed"],
                        target_id=player.player_id,
                        target_username=player.username,
                        target_hp_remaining=player.hp,
                        is_tick=True,
                    ))
                elif affix_effect["effect"] == "extend_cooldown":
                    results.append(ActionResult(
                        player_id=player.player_id,
                        username=player.username,
                        action_type=ActionType.ATTACK,
                        success=True,
                        message=f"{player.username}'s {affix_effect['affix'].replace('_', ' ').title()} extends {target.username}'s cooldowns by {affix_effect['turns_added']} turn(s)!",
                        target_id=target.player_id,
                        target_username=target.username,
                        is_tick=True,
                    ))

        # Phase 16A: Build enhanced combat message
        crit_tag = " (CRIT!)" if combat_info["is_crit"] else ""
        results.append(ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.ATTACK,
            success=True,
            message=f"{player.username} hit {target.username} for {damage} damage{crit_tag}"
                    + (f" — {target.username} was killed!" if killed else ""),
            target_id=target.player_id,
            target_username=target.username,
            damage_dealt=damage,
            target_hp_remaining=target.hp,
            killed=killed,
            is_crit=combat_info["is_crit"],
        ))

        if killed:
            deaths.append(target.player_id)

            # Phase 16D: Grimfang on-kill haste buff
            from app.core.item_generator import get_all_equipped_unique_effects
            melee_unique_effects = get_all_equipped_unique_effects(player.equipment)
            for effect in melee_unique_effects:
                if effect.get("type") == "on_kill_buff":
                    haste_buff = {
                        "buff_id": effect.get("buff_id", "grimfang_haste"),
                        "type": effect.get("buff_type", "move_speed_bonus"),
                        "turns_remaining": effect.get("duration", 2),
                        "value": effect.get("value", 1),
                        "source": player.player_id,
                    }
                    if not hasattr(player, 'active_buffs'):
                        player.active_buffs = []
                    # Refresh existing buff
                    player.active_buffs = [b for b in player.active_buffs if b.get("buff_id") != haste_buff["buff_id"]]
                    player.active_buffs.append(haste_buff)
                    # Apply move speed bonus immediately
                    player.move_speed += effect.get("value", 1)
                    results.append(ActionResult(
                        player_id=player.player_id,
                        username=player.username,
                        action_type=ActionType.ATTACK,
                        success=True,
                        message=f"{player.username}'s Grimfang grants +{effect.get('value', 1)} move speed for {effect.get('duration', 2)} turns!",
                        target_id=player.player_id,
                        target_username=player.username,
                        is_tick=True,
                    ))

        # Phase 16D: Unique lifesteal message (Soulreaver)
        if combat_info.get("unique_lifesteal_healed", 0) > 0:
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.ATTACK,
                success=True,
                message=f"{player.username}'s Soulreaver healed {combat_info['unique_lifesteal_healed']} HP",
                heal_amount=combat_info["unique_lifesteal_healed"],
                target_id=player.player_id,
                target_username=player.username,
                target_hp_remaining=player.hp,
                is_tick=True,
            ))

        # Phase 16D: Dodge retaliate message (Wraithmantle)
        if combat_info.get("dodge_retaliate_damage", 0) > 0:
            retaliate_killed = not player.is_alive
            results.append(ActionResult(
                player_id=target.player_id,
                username=target.username,
                action_type=ActionType.ATTACK,
                success=True,
                message=f"{target.username}'s Wraithmantle deals {combat_info['dodge_retaliate_damage']} damage to {player.username}!"
                        + (f" — {player.username} was killed!" if retaliate_killed else ""),
                target_id=player.player_id,
                target_username=player.username,
                damage_dealt=combat_info["dodge_retaliate_damage"],
                target_hp_remaining=player.hp,
                killed=retaliate_killed,
            ))
            if retaliate_killed:
                deaths.append(player.player_id)

        # Phase 16A: Life on hit message
        if combat_info["life_on_hit_healed"] > 0:
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.ATTACK,
                success=True,
                message=f"{player.username} healed {combat_info['life_on_hit_healed']} HP from Life on Hit",
                heal_amount=combat_info["life_on_hit_healed"],
                target_id=player.player_id,
                target_username=player.username,
                target_hp_remaining=player.hp,
                is_tick=True,
            ))

        # Phase 16A: Thorns damage message
        if combat_info["thorns_damage"] > 0:
            thorns_killed = not player.is_alive
            results.append(ActionResult(
                player_id=target.player_id,
                username=target.username,
                action_type=ActionType.ATTACK,
                success=True,
                message=f"{target.username}'s Thorns reflects {combat_info['thorns_damage']} damage to {player.username}!"
                        + (f" — {player.username} was killed!" if thorns_killed else ""),
                target_id=player.player_id,
                target_username=player.username,
                damage_dealt=combat_info["thorns_damage"],
                target_hp_remaining=player.hp,
                killed=thorns_killed,
            ))
            if thorns_killed:
                deaths.append(player.player_id)

        # Phase 11: Ward reflect — if target has Ward, reflect damage back to attacker
        if target.is_alive or not killed:
            from app.core.skills import trigger_ward_reflect
            reflected = trigger_ward_reflect(target, player)
            if reflected > 0:
                attacker_killed = not player.is_alive
                results.append(ActionResult(
                    player_id=target.player_id,
                    username=target.username,
                    action_type=ActionType.SKILL,
                    skill_id="ward",
                    success=True,
                    message=f"{target.username}'s Ward reflects {reflected} damage to {player.username}!"
                            + (f" — {player.username} was killed!" if attacker_killed else ""),
                    target_id=player.player_id,
                    target_username=player.username,
                    damage_dealt=reflected,
                    target_hp_remaining=player.hp,
                    killed=attacker_killed,
                ))
                if attacker_killed:
                    deaths.append(player.player_id)
