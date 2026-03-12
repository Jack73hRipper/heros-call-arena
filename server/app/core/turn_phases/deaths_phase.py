"""
Deaths Phase — Phase 3.5 + 3.75 + 4: Death loot, permadeath, explosions, victory.

Phase 16B: Affix-based enemy loot generation.
Phase 18D: On-death explosion effects, minion unlinking.
Phase 18F: Rarity-scaled drops, elite kill broadcasts.
Phase 18G: Super unique dedicated loot tables.
Phase 25C: Cheat death — Revenant Undying Will revive intercept.
Phase 26C: Soul Anchor — Shaman ally death prevention (survive at 1 HP).
"""

from __future__ import annotations

import math

from app.models.player import PlayerState
from app.models.actions import ActionType, ActionResult
from app.core.combat import apply_damage, check_victory, check_team_victory
from app.core.loot import generate_enemy_loot


def _resolve_deaths(
    match_id: str,
    deaths: list[str],
    players: dict[str, PlayerState],
    ground_items: dict[str, list] | None,
    results: list[ActionResult],
    loot_drops: list[dict],
    floor_number: int = 1,
    dropped_unique_ids: set[str] | None = None,
    dropped_set_piece_ids: set[str] | None = None,
    elite_kills: list[dict] | None = None,
) -> list[dict]:
    """Phase 3.5 + 3.75 — Loot drops from deaths, kill tracking, and permadeath.

    Phase 16B: Uses generate_enemy_loot() with floor/tier/MF context for
    affix-bearing item generation. Falls back gracefully for arena/non-dungeon.
    Phase 18F: Passes monster_rarity to loot roller for tier-scaled drops.
    Broadcasts elite_kill events for rare/super_unique deaths.
    Phase 25C: Pre-pass checks for cheat_death buff (Undying Will) and revives
    instead of processing death.

    Returns:
        hero_deaths: List of hero permadeath event dicts.
    """
    # Phase 25C: Cheat death pre-pass — revive units with cheat_death buff
    revived_ids: list[str] = []
    for death_pid in deaths:
        dead_unit = players.get(death_pid)
        if not dead_unit:
            continue
        cheat_death_buff = next(
            (b for b in dead_unit.active_buffs if b.get("stat") == "cheat_death"),
            None,
        )
        if cheat_death_buff:
            revive_hp_pct = cheat_death_buff.get("revive_hp_pct", 0.30)
            revive_hp = max(1, math.floor(dead_unit.max_hp * revive_hp_pct))
            dead_unit.hp = revive_hp
            dead_unit.is_alive = True
            # Consume the buff (one-time use)
            dead_unit.active_buffs = [
                b for b in dead_unit.active_buffs if b.get("stat") != "cheat_death"
            ]
            revived_ids.append(death_pid)
            results.append(ActionResult(
                player_id=death_pid,
                username=dead_unit.username,
                action_type=ActionType.SKILL,
                skill_id="undying_will",
                success=True,
                message=f"{dead_unit.username} defies death! Revives with {revive_hp} HP!",
                target_id=death_pid,
                target_username=dead_unit.username,
                target_hp_remaining=revive_hp,
                heal_amount=revive_hp,
            ))

    # Phase 26C: Soul Anchor pre-pass — save anchored units from death at 1 HP
    for death_pid in deaths:
        if death_pid in revived_ids:
            continue  # Already saved by cheat_death
        dead_unit = players.get(death_pid)
        if not dead_unit:
            continue
        soul_anchor = next(
            (b for b in dead_unit.active_buffs if b.get("stat") == "soul_anchor"),
            None,
        )
        if soul_anchor:
            survive_hp = soul_anchor.get("survive_hp", 1)
            dead_unit.hp = survive_hp
            dead_unit.is_alive = True
            # Consume the buff (one-time use)
            dead_unit.active_buffs = [
                b for b in dead_unit.active_buffs if b.get("stat") != "soul_anchor"
            ]
            revived_ids.append(death_pid)
            results.append(ActionResult(
                player_id=death_pid,
                username=dead_unit.username,
                action_type=ActionType.SKILL,
                skill_id="soul_anchor",
                success=True,
                message=f"Soul Anchor saves {dead_unit.username} from death! ({survive_hp} HP)",
                target_id=death_pid,
                target_username=dead_unit.username,
                target_hp_remaining=survive_hp,
                heal_amount=survive_hp,
            ))

    # Remove revived units from deaths list
    if revived_ids:
        deaths[:] = [d for d in deaths if d not in revived_ids]

    # Phase 3.5: Loot drops from enemy deaths (Phase 16B: affix generator)
    if ground_items is not None:
        for death_pid in deaths:
            dead_unit = players.get(death_pid)
            if not dead_unit:
                continue
            enemy_type = getattr(dead_unit, 'enemy_type', None)
            if not enemy_type:
                continue  # Only enemies drop loot, not players (for now)

            # Derive enemy tier from unit properties
            is_boss = getattr(dead_unit, 'is_boss', False)
            if is_boss:
                enemy_tier = "boss"
            elif getattr(dead_unit, 'base_hp', 0) >= 300:
                enemy_tier = "elite"
            elif getattr(dead_unit, 'base_hp', 0) >= 150:
                enemy_tier = "mid"
            else:
                enemy_tier = "fodder"

            # Phase 18F: Get monster rarity from the dead unit
            unit_monster_rarity = getattr(dead_unit, 'monster_rarity', None)

            # Find the killer's magic_find_pct from action results
            killer_mf = 0.0
            killer_class = ""
            killer_id = None
            for result_action in results:
                if result_action.killed and result_action.target_id == death_pid:
                    killer = players.get(result_action.player_id)
                    if killer:
                        killer_mf = getattr(killer, 'magic_find_pct', 0.0)
                        killer_class = getattr(killer, 'class_id', '')
                        killer_id = result_action.player_id
                    break

            # Phase 18G: Super uniques use their own dedicated loot tables
            if unit_monster_rarity == "super_unique":
                from app.core.loot import roll_super_unique_loot
                su_id = getattr(dead_unit, 'super_unique_id', None) or enemy_type
                dropped_items = roll_super_unique_loot(
                    super_unique_id=su_id,
                    magic_find_pct=killer_mf,
                )
            else:
                dropped_items = generate_enemy_loot(
                    enemy_type,
                    floor_number=floor_number,
                    enemy_tier=enemy_tier,
                    magic_find_pct=killer_mf,
                    dropped_unique_ids=dropped_unique_ids,
                    dropped_set_piece_ids=dropped_set_piece_ids,
                    player_class=killer_class,
                    monster_rarity=unit_monster_rarity,
                )

            if dropped_items:
                death_key = f"{dead_unit.position.x},{dead_unit.position.y}"
                item_dicts = [item.model_dump() for item in dropped_items]
                if death_key not in ground_items:
                    ground_items[death_key] = []
                ground_items[death_key].extend(item_dicts)
                loot_drops.append({
                    "x": dead_unit.position.x,
                    "y": dead_unit.position.y,
                    "enemy_type": enemy_type,
                    "enemy_name": dead_unit.username,
                    "items": item_dicts,
                })

            # Phase 18F: Broadcast elite_kill event for rare/super_unique deaths
            if unit_monster_rarity in ("rare", "super_unique") and elite_kills is not None:
                display_name = getattr(dead_unit, 'display_name', None) or dead_unit.username
                elite_kill_event = {
                    "type": "elite_kill",
                    "monster_rarity": unit_monster_rarity,
                    "display_name": display_name,
                    "enemy_type": enemy_type,
                    "killer_id": killer_id,
                    "x": dead_unit.position.x,
                    "y": dead_unit.position.y,
                }
                if dropped_items:
                    elite_kill_event["loot_items"] = [
                        {"name": item.name, "rarity": item.rarity if isinstance(item.rarity, str) else item.rarity.value}
                        for item in dropped_items
                    ]
                elite_kills.append(elite_kill_event)

    # Phase 3.75: Kill tracking & permadeath
    from app.core.match_manager import track_kill, handle_hero_permadeath

    hero_deaths: list[dict] = []

    # Build killer map from action results: who killed whom this turn
    for result_action in results:
        if result_action.killed and result_action.target_id:
            dead_unit = players.get(result_action.target_id)
            if dead_unit and dead_unit.unit_type == "ai":
                track_kill(match_id, result_action.player_id,
                          victim_is_boss=getattr(dead_unit, 'is_boss', False))

    # Handle permadeath for human heroes that died
    for death_pid in deaths:
        dead_unit = players.get(death_pid)
        if not dead_unit:
            continue
        if dead_unit.unit_type == "human" and dead_unit.hero_id:
            hero_death = handle_hero_permadeath(match_id, death_pid)
            if hero_death:
                hero_deaths.append(hero_death)

    # --- Phase 18D: On-death explosion effects ---
    from app.core.monster_rarity import get_affix, get_champion_type as get_ct

    explosion_deaths: list[str] = []  # Track additional deaths from explosions

    for death_pid in deaths:
        dead_unit = players.get(death_pid)
        if not dead_unit:
            continue

        dead_pos = (dead_unit.position.x, dead_unit.position.y)

        # Check Fire Enchanted (on_death_explosion affix)
        for affix_id in getattr(dead_unit, 'affixes', []):
            affix_data = get_affix(affix_id)
            if not affix_data:
                continue
            if affix_data.get("category") != "on_death":
                continue
            for effect in affix_data.get("effects", []):
                if effect.get("type") == "on_death_explosion":
                    explosion_damage = effect.get("damage", 20)
                    explosion_radius = effect.get("radius", 2)
                    # Deal damage to all units within radius
                    for uid, unit in players.items():
                        if uid == death_pid or not unit.is_alive:
                            continue
                        dist = max(
                            abs(unit.position.x - dead_pos[0]),
                            abs(unit.position.y - dead_pos[1]),
                        )
                        if dist <= explosion_radius:
                            killed_by_explosion = apply_damage(unit, explosion_damage)
                            results.append(ActionResult(
                                player_id=death_pid,
                                username=dead_unit.username,
                                action_type=ActionType.SKILL,
                                skill_id=f"on_death_{affix_id}",
                                success=True,
                                message=f"{dead_unit.username}'s {affix_data['name']} explodes for {explosion_damage} damage to {unit.username}!"
                                        + (f" — {unit.username} was killed!" if killed_by_explosion else ""),
                                target_id=uid,
                                target_username=unit.username,
                                damage_dealt=explosion_damage,
                                target_hp_remaining=unit.hp,
                                killed=killed_by_explosion,
                            ))
                            if killed_by_explosion and uid not in deaths:
                                explosion_deaths.append(uid)

        # Check Possessed champion type (death explosion)
        if getattr(dead_unit, 'champion_type', None) == "possessed":
            ct_config = get_ct("possessed")
            if ct_config:
                explosion_damage = ct_config.get("death_explosion_damage", 15)
                explosion_radius = ct_config.get("death_explosion_radius", 1)
                for uid, unit in players.items():
                    if uid == death_pid or not unit.is_alive:
                        continue
                    dist = max(
                        abs(unit.position.x - dead_pos[0]),
                        abs(unit.position.y - dead_pos[1]),
                    )
                    if dist <= explosion_radius:
                        killed_by_explosion = apply_damage(unit, explosion_damage)
                        results.append(ActionResult(
                            player_id=death_pid,
                            username=dead_unit.username,
                            action_type=ActionType.SKILL,
                            skill_id="possessed_explosion",
                            success=True,
                            message=f"{dead_unit.username}'s Possessed spirit explodes for {explosion_damage} damage to {unit.username}!"
                                    + (f" — {unit.username} was killed!" if killed_by_explosion else ""),
                            target_id=uid,
                            target_username=unit.username,
                            damage_dealt=explosion_damage,
                            target_hp_remaining=unit.hp,
                            killed=killed_by_explosion,
                        ))
                        if killed_by_explosion and uid not in deaths:
                            explosion_deaths.append(uid)

    # Add explosion deaths to the main deaths list
    deaths.extend(explosion_deaths)

    # --- Phase 18D: Minion unlinking on rare leader death ---
    for death_pid in deaths:
        dead_unit = players.get(death_pid)
        if not dead_unit:
            continue
        # If a rare leader dies, unlink its minions (remove room leash)
        if getattr(dead_unit, 'monster_rarity', None) == "rare":
            for uid, unit in players.items():
                if getattr(unit, 'minion_owner_id', None) == death_pid and unit.is_alive:
                    unit.room_id = None  # Remove room leash — minions roam freely

    # --- Phase 27: PVPVE team leader promotion on death ---
    # If a team leader dies, promote the next alive teammate so the group
    # keeps a cohesive anchor instead of scattering.
    for death_pid in deaths:
        dead_unit = players.get(death_pid)
        if not dead_unit:
            continue
        if not getattr(dead_unit, 'is_team_leader', False):
            continue
        if not dead_unit.player_id.startswith("pvpve-ai-"):
            continue
        # Find next alive PVPVE AI teammate on the same team
        for uid, unit in players.items():
            if (
                uid != death_pid
                and unit.is_alive
                and unit.team == dead_unit.team
                and uid.startswith("pvpve-ai-")
            ):
                unit.is_team_leader = True
                # Clear hero_id so the new leader falls through to aggressive AI
                unit.hero_id = None
                break

    return hero_deaths


def _resolve_victory(
    players: dict[str, PlayerState],
    team_a: list[str] | None,
    team_b: list[str] | None,
    team_c: list[str] | None,
    team_d: list[str] | None,
    match_type: str | None = None,
) -> str | None:
    """Phase 4 — Check for team or FFA victory.

    Phase 27D: When *match_type* is ``"pvpve"``, units on the ``"pve"`` team
    are excluded from the survivor count so that PVE enemies being alive
    does not prevent a PVPVE victory from being declared.
    """
    use_teams = team_a is not None and team_b is not None

    if use_teams:
        # Phase 27D: exclude PVE team from victory calculation in PVPVE matches
        excluded = {"pve"} if match_type == "pvpve" else None
        team_result = check_team_victory(
            list(players.values()), team_a, team_b,
            team_c=team_c, team_d=team_d,
            excluded_teams=excluded,
        )
        if team_result:
            return team_result  # "team_a", "team_b", "team_c", "team_d", or "draw"
        return None
    else:
        return check_victory(list(players.values()))
