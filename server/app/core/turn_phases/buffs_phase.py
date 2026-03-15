"""
Buffs Phase — Phase 0.5 + 0.75: Cooldowns, buffs, DoT/HoT, HP regen, totem ticks.

Phase 6B: Tick active buffs.
Phase 11: DoT damage and HoT healing per tick.
Phase 16A: HP regen ticks, CDR applied to skill cooldowns.
Phase 26C: Totem tick processing — healing + searing totem per-turn effects.
"""

from __future__ import annotations

from app.models.player import PlayerState
from app.models.actions import ActionType, ActionResult
from app.core.combat import tick_cooldowns
from app.core.skills import tick_buffs


def _resolve_cooldowns_and_buffs(
    players: dict[str, PlayerState],
    results: list[ActionResult],
    deaths: list[str],
    match_state=None,  # Phase 26C: MatchState for totem tick processing
) -> list[dict]:
    """Phase 0.5 + 0.75 — Tick cooldowns and active buffs for all alive units.

    Phase 11: tick_buffs now applies DoT damage and HoT healing per tick.
    Phase 16A: HP regen ticks, CDR applied to skill cooldowns.
    Phase 26C: Totem tick processing — healing/searing totem per-turn effects.
    Deaths from DoT are tracked in the deaths list.

    Returns:
        buff_changes: List of buff state dicts for units whose buffs ticked.
    """
    # Phase 0.5: Tick cooldowns
    for p in players.values():
        if p.is_alive:
            tick_cooldowns(p)

    # Phase 16A: HP regen — restore hp_regen HP per turn (equipment stat)
    for p in players.values():
        if p.is_alive and p.hp_regen > 0 and p.hp < p.max_hp:
            old_hp = p.hp
            p.hp = min(p.max_hp, p.hp + p.hp_regen)
            healed = p.hp - old_hp
            if healed > 0:
                results.append(ActionResult(
                    player_id=p.player_id,
                    username=p.username,
                    action_type=ActionType.SKILL,
                    skill_id="hp_regen",
                    success=True,
                    message=f"{p.username} regenerates {healed} HP",
                    heal_amount=healed,
                    target_id=p.player_id,
                    target_username=p.username,
                    target_hp_remaining=p.hp,
                    is_tick=True,
                ))

    # Phase 0.75: Tick active buffs (decrement turns, remove expired, apply DoT/HoT)
    buff_changes: list[dict] = []
    for p in players.values():
        if p.is_alive and p.active_buffs:
            old_hp = p.hp
            expired = tick_buffs(p)

            # Log DoT damage ticks
            for buff in p.active_buffs:
                if buff.get("type") == "dot":
                    dmg = buff.get("damage_per_tick", 0)
                    if dmg > 0:
                        results.append(ActionResult(
                            player_id=p.player_id,
                            username=p.username,
                            action_type=ActionType.SKILL,
                            skill_id=buff.get("buff_id", "dot"),
                            success=True,
                            message=f"{p.username} takes {dmg} damage from {buff.get('buff_id', 'DoT')}",
                            damage_dealt=dmg,
                            target_id=p.player_id,
                            target_username=p.username,
                            target_hp_remaining=p.hp,
                            is_tick=True,
                        ))

            # Log HoT healing ticks
            for buff in p.active_buffs:
                if buff.get("type") == "hot":
                    heal = buff.get("heal_per_tick", 0)
                    if heal > 0:
                        actual_heal = min(heal, p.max_hp - old_hp) if old_hp < p.max_hp else 0
                        if actual_heal > 0:
                            results.append(ActionResult(
                                player_id=p.player_id,
                                username=p.username,
                                action_type=ActionType.SKILL,
                                skill_id=buff.get("buff_id", "hot"),
                                success=True,
                                message=f"{p.username} heals {actual_heal} HP from {buff.get('buff_id', 'HoT')}",
                                heal_amount=actual_heal,
                                target_id=p.player_id,
                                target_username=p.username,
                                target_hp_remaining=p.hp,
                                is_tick=True,
                            ))

            # Check if DoT killed this unit
            if not p.is_alive:
                deaths.append(p.player_id)
                results.append(ActionResult(
                    player_id=p.player_id,
                    username=p.username,
                    action_type=ActionType.SKILL,
                    success=True,
                    message=f"{p.username} was killed by damage over time!",
                    killed=True,
                    target_id=p.player_id,
                    target_username=p.username,
                    target_hp_remaining=0,
                ))

            buff_changes.append({
                "player_id": p.player_id,
                "buffs": [b.copy() for b in p.active_buffs],
                "expired": [e.copy() for e in expired],
            })

    # ------------------------------------------------------------------
    # Phase 26C: Totem tick processing — healing + searing totem effects
    # ------------------------------------------------------------------
    if match_state is not None and hasattr(match_state, "totems") and match_state.totems:
        expired_totems: list[dict] = []
        for totem in match_state.totems:
            # Skip already-destroyed totems
            if totem.get("hp", 0) <= 0:
                expired_totems.append(totem)
                continue
            # Skip expired totems
            if totem.get("duration_remaining", 0) <= 0:
                expired_totems.append(totem)
                continue

            totem_team = totem.get("team", "")
            totem_x = totem.get("x", 0)
            totem_y = totem.get("y", 0)
            effect_radius = totem.get("effect_radius", 2)

            if totem.get("type") == "healing_totem":
                heal_per_turn = totem.get("heal_per_turn", 8)
                for p in players.values():
                    if not p.is_alive or p.team != totem_team:
                        continue
                    dist = max(abs(p.position.x - totem_x), abs(p.position.y - totem_y))
                    if dist <= effect_radius:
                        actual_heal = min(heal_per_turn, p.max_hp - p.hp)
                        if actual_heal > 0:
                            p.hp += actual_heal
                            results.append(ActionResult(
                                player_id=totem.get("owner_id", ""),
                                username="Healing Totem",
                                action_type=ActionType.SKILL,
                                skill_id="healing_totem",
                                success=True,
                                message=f"Healing Totem restores {actual_heal} HP to {p.username}",
                                heal_amount=actual_heal,
                                target_id=p.player_id,
                                target_username=p.username,
                                target_hp_remaining=p.hp,
                                is_tick=True,
                            ))

            elif totem.get("type") == "searing_totem":
                damage_per_turn = totem.get("damage_per_turn", 4)
                for p in players.values():
                    if not p.is_alive or p.team == totem_team:
                        continue
                    dist = max(abs(p.position.x - totem_x), abs(p.position.y - totem_y))
                    if dist <= effect_radius:
                        # Searing totem damage now respects armor
                        effective_armor = getattr(p, 'armor', 0)
                        reduced_dmg = max(1, damage_per_turn - effective_armor)
                        old_hp = p.hp
                        p.hp = max(0, p.hp - reduced_dmg)
                        actual_dmg = old_hp - p.hp
                        if p.hp <= 0:
                            p.is_alive = False
                        results.append(ActionResult(
                            player_id=totem.get("owner_id", ""),
                            username="Searing Totem",
                            action_type=ActionType.SKILL,
                            skill_id="searing_totem",
                            success=True,
                            message=f"Searing Totem deals {actual_dmg} damage to {p.username}"
                                    + (f" — {p.username} was killed!" if not p.is_alive else ""),
                            damage_dealt=actual_dmg,
                            target_id=p.player_id,
                            target_username=p.username,
                            target_hp_remaining=p.hp,
                            killed=not p.is_alive,
                            is_tick=True,
                        ))
                        if not p.is_alive and p.player_id not in deaths:
                            deaths.append(p.player_id)

            elif totem.get("type") == "earthgrasp_totem":
                root_duration = totem.get("root_duration", 1)
                rooted_names: list[str] = []
                for p in players.values():
                    if not p.is_alive or p.team == totem_team:
                        continue
                    dist = max(abs(p.position.x - totem_x), abs(p.position.y - totem_y))
                    if dist <= effect_radius:
                        # Refresh existing root (don't stack)
                        p.active_buffs = [b for b in p.active_buffs if b.get("stat") != "rooted"]
                        root_entry = {
                            "buff_id": "earthgrasp",
                            "type": "aoe_root",
                            "stat": "rooted",
                            "source_id": totem.get("owner_id", ""),
                            "turns_remaining": root_duration,
                            "magnitude": 0,
                        }
                        p.active_buffs.append(root_entry)
                        rooted_names.append(p.username)
                if rooted_names:
                    names_str = ", ".join(rooted_names)
                    results.append(ActionResult(
                        player_id=totem.get("owner_id", ""),
                        username="Earthgrasp Totem",
                        action_type=ActionType.SKILL,
                        skill_id="earthgrasp",
                        success=True,
                        message=f"Earthgrasp Totem roots {len(rooted_names)} enem{'y' if len(rooted_names) == 1 else 'ies'}: {names_str}",
                        is_tick=True,
                    ))

            # Tick down duration
            totem["duration_remaining"] = totem.get("duration_remaining", 0) - 1
            if totem["duration_remaining"] <= 0:
                expired_totems.append(totem)

        # Remove expired/destroyed totems
        for t in expired_totems:
            if t in match_state.totems:
                match_state.totems.remove(t)

    return buff_changes
