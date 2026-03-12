"""
Tick Loop — The game loop callback invoked by APScheduler every tick.

Computes FOV, runs AI decisions, collects queued actions, resolves the turn,
broadcasts FOV-filtered results to each player, and handles wave advancement
and match-end logic.

Extracted from websocket.py during P3 refactoring (pure mechanical move).
"""

from __future__ import annotations

from app.models.actions import PlayerAction, ActionType
from app.core.match_manager import (
    get_match,
    get_match_players,
    get_players_snapshot,
    increment_turn,
    pop_next_actions,
    clear_player_queue,
    get_player_queue,
    get_match_teams,
    get_ai_ids,
    set_fov_cache,
    get_fov_cache,
    get_team_fov,
    get_dungeon_state,
    get_stairs_info,
    advance_floor,
    get_controlled_unit_ids,
    get_party_members,
    advance_wave_if_cleared,
    is_wave_map,
    all_waves_complete,
    generate_auto_target_action,
    clear_auto_target,
    get_match_end_payload,
    end_match,
    get_player_username,
    queue_action,
    track_damage_dealt,
    track_damage_taken,
    track_healing_done,
    track_items_looted,
    track_turn_survived,
    record_turn_events,
    save_match_report,
)
from app.core.turn_resolver import resolve_turn
from app.core.map_loader import get_obstacles_with_door_states, load_map, is_dungeon_map
from app.core.fov import compute_fov
from app.core.ai_behavior import run_ai_decisions, clear_ai_patrol_state
from app.services.scheduler import scheduler_manager


async def match_tick(match_id: str) -> None:
    """
    Called by APScheduler every tick_rate seconds for an active match.
    Computes FOV, runs AI decisions, collects queued actions, resolves the turn,
    and broadcasts FOV-filtered results to each player.
    """
    # Import ws_manager here to avoid circular imports
    from app.services.websocket import ws_manager

    match = get_match(match_id)
    if not match or match.status != "in_progress":
        scheduler_manager.remove_match_tick(match_id)
        return

    # Increment turn
    turn_number = increment_turn(match_id)
    print(f"[Tick] Match {match_id} — Turn {turn_number}")

    # Load map data
    map_id = match.config.map_id
    map_data = load_map(map_id)
    grid_width = map_data.get("width", 15)
    grid_height = map_data.get("height", 15)

    # Get dungeon state (door/chest/ground_items states) — None for arena maps
    dungeon_state = get_dungeon_state(match_id)
    door_states = dungeon_state["door_states"] if dungeon_state else None
    chest_states = dungeon_state["chest_states"] if dungeon_state else None
    ground_items = dungeon_state["ground_items"] if dungeon_state else None

    # Compute obstacles honouring current door states (open doors passable)
    obstacles = get_obstacles_with_door_states(map_id, door_states)

    # Phase 7D-1: Build a set of closed-door tiles for door-aware A*.
    # AI pathfinding uses this to plan paths *through* closed doors at
    # elevated cost.  The obstacles set still contains closed doors for
    # movement validation (turn_resolver blocks MOVE onto closed doors).
    door_tiles: set[tuple[int, int]] | None = None
    if door_states:
        door_tiles = set()
        for key, state in door_states.items():
            if state == "closed":
                parts = key.split(",")
                if len(parts) == 2:
                    door_tiles.add((int(parts[0]), int(parts[1])))
        if not door_tiles:
            door_tiles = None

    # Get all units (players + AI)
    all_units = get_match_players(match_id)
    team_a, team_b, team_c, team_d = get_match_teams(match_id)
    ai_ids = get_ai_ids(match_id)

    # --- Step 1: Compute FOV for all alive units ---
    for uid, unit in all_units.items():
        if unit.is_alive and not unit.extracted:
            fov = compute_fov(
                unit.position.x, unit.position.y,
                unit.vision_range,
                grid_width, grid_height,
                obstacles,
            )
            set_fov_cache(match_id, uid, fov)

    # --- Step 2: Run AI decisions (with shared team FOV) ---
    # Pre-compute team FOV so AI can use shared ally vision
    pre_team_a_fov = get_team_fov(match_id, team_a) if team_a else set()
    pre_team_b_fov = get_team_fov(match_id, team_b) if team_b else set()
    pre_team_c_fov = get_team_fov(match_id, team_c) if team_c else set()
    pre_team_d_fov = get_team_fov(match_id, team_d) if team_d else set()
    ai_team_fov_map = {
        "a": pre_team_a_fov,
        "b": pre_team_b_fov,
        "c": pre_team_c_fov,
        "d": pre_team_d_fov,
    }

    ai_actions = run_ai_decisions(
        ai_ids, all_units, grid_width, grid_height, obstacles,
        team_fov_map=ai_team_fov_map,
        match_id=match_id,
        controlled_ids=get_controlled_unit_ids(match_id),
        door_tiles=door_tiles,
        portal=match.portal,
        match_state=match,
    )

    # --- Step 3: Pop first action from each human player's queue ---
    raw_actions = pop_next_actions(match_id)

    # Clear queues for dead or extracted players
    for pid, p in all_units.items():
        if not p.is_alive or p.extracted:
            clear_player_queue(match_id, pid)

    # Convert popped player actions dict to list
    action_list = []
    for pid, action in raw_actions.items():
        player = all_units.get(pid)
        if player and player.is_alive and not player.extracted:
            action_list.append(action)

    # Add AI actions
    action_list.extend(ai_actions)

    # --- Step 3.5: Generate auto-target actions for players with empty queues ---
    # Human-controlled units (and controlled party members) with an active
    # auto_target_id but no queued action get a chase/attack action generated
    # server-side using the target's *current* position.  This is the core of
    # the Phase 10 persistent melee pursuit system.
    connections = ws_manager.get_match_connections(match_id)
    submitted_ids = {a.player_id for a in action_list}
    for pid, unit in all_units.items():
        if not unit.is_alive or unit.extracted:
            continue
        if pid in submitted_ids or pid in raw_actions:
            continue
        # Only process human players and controlled party members
        is_human = unit.unit_type == "human"
        is_controlled = bool(unit.controlled_by)
        if not (is_human or is_controlled):
            continue
        if unit.auto_target_id:
            prev_target = unit.auto_target_id
            auto_action = generate_auto_target_action(
                match_id, pid, all_units,
                grid_width, grid_height, obstacles,
                door_tiles=door_tiles,
            )
            if auto_action:
                action_list.append(auto_action)
                submitted_ids.add(pid)
            elif prev_target and not unit.auto_target_id:
                # Auto-target was cleared by generate_auto_target_action
                # (target died or unreachable) — notify the controlling player
                notify_pid = unit.controlled_by or pid
                if notify_pid in connections:
                    # Determine reason: target dead or unreachable
                    target_unit = all_units.get(prev_target)
                    reason = "target_died" if (not target_unit or not target_unit.is_alive) else "unreachable"
                    await ws_manager.send_to_player(match_id, notify_pid, {
                        "type": "auto_target_cleared",
                        "unit_id": pid,
                        "reason": reason,
                    })

    # Add implicit "wait" for human players who didn't submit an action
    for pid, p in all_units.items():
        if p.is_alive and not p.extracted and pid not in submitted_ids and p.unit_type == "human":
            action_list.append(PlayerAction(
                player_id=pid,
                action_type=ActionType.WAIT,
            ))

    # --- Step 4: Resolve the turn ---
    use_teams = bool(team_a or team_b or team_c or team_d)
    match_is_dungeon = is_dungeon_map(map_id) or (match.config.match_type in ("dungeon", "pvpve"))

    # Phase 12-5: Get stairs info for floor transition
    stairs_info = get_stairs_info(match_id) if match_is_dungeon else None
    stairs_positions = stairs_info["positions"] if stairs_info else None
    stairs_unlocked = stairs_info["unlocked"] if stairs_info else False

    turn_result = resolve_turn(
        match_id=match_id,
        turn_number=turn_number,
        players=all_units,
        actions=action_list,
        grid_width=grid_width,
        grid_height=grid_height,
        obstacles=obstacles,
        team_a=team_a if use_teams else None,
        team_b=team_b if use_teams else None,
        team_c=team_c if use_teams else None,
        team_d=team_d if use_teams else None,
        door_states=door_states,
        chest_states=chest_states,
        ground_items=ground_items,
        is_dungeon=match_is_dungeon,
        match_channeling=match.channeling,
        match_portal=match.portal,
        stairs_positions=stairs_positions,
        stairs_unlocked=stairs_unlocked,
        floor_number=getattr(match, 'current_floor', 1),
        match_state=match,
    )

    # Phase 12C: Persist updated channeling/portal state back to MatchState
    # Reconstruct state from TurnResult event fields
    if turn_result.channeling_started and not turn_result.portal_spawned:
        # New channeling started this turn, hasn't completed yet
        match.channeling = {
            "player_id": turn_result.channeling_started["player_id"],
            "action": "portal",
            "turns_remaining": turn_result.channeling_started["turns_remaining"],
            "tile_x": turn_result.channeling_started["tile_x"],
            "tile_y": turn_result.channeling_started["tile_y"],
        }
    elif turn_result.channeling_tick:
        # Ongoing channeling, still in progress
        if match.channeling:
            match.channeling["turns_remaining"] = turn_result.channeling_tick["turns_remaining"]
        else:
            match.channeling = None
    elif turn_result.portal_spawned:
        # Channeling completed — portal spawned, channeling cleared
        match.channeling = None
    elif match.channeling and not turn_result.channeling_tick and not turn_result.channeling_started:
        # Channeling was active but no tick event — caster died, channel cancelled
        match.channeling = None

    if turn_result.portal_spawned:
        match.portal = {
            "active": True,
            "x": turn_result.portal_spawned["x"],
            "y": turn_result.portal_spawned["y"],
            "turns_remaining": turn_result.portal_spawned["turns_remaining"],
            "owner_id": turn_result.portal_spawned["owner_id"],
        }
    elif turn_result.portal_tick:
        if match.portal:
            match.portal["turns_remaining"] = turn_result.portal_tick["turns_remaining"]
    elif turn_result.portal_expired:
        match.portal = None

    # --- Step 4.5: Track combat stats from this turn's results ---
    for act in turn_result.actions:
        if act.damage_dealt and act.damage_dealt > 0:
            track_damage_dealt(match_id, act.player_id, act.damage_dealt)
            if act.target_id:
                track_damage_taken(match_id, act.target_id, act.damage_dealt)
        if act.heal_amount and act.heal_amount > 0:
            track_healing_done(match_id, act.player_id, act.heal_amount)
    for iu in turn_result.items_used:
        eff = iu.get("effect", {})
        if eff.get("type") == "heal" and eff.get("actual_healed", 0) > 0:
            track_healing_done(match_id, iu["player_id"], eff["actual_healed"])
    for ip in turn_result.items_picked_up:
        item_count = len(ip.get("items", []))
        if item_count > 0:
            track_items_looted(match_id, ip["player_id"], item_count)
    # Track turns survived for all alive units
    for uid, unit in all_units.items():
        if unit.is_alive:
            track_turn_survived(match_id, uid, turn_number)

    # --- Step 4.6: Record turn events for Arena Analyst timeline ---
    record_turn_events(match_id, turn_number, turn_result, all_units)

    # --- Step 5: Recompute FOV after movement ---
    for uid, unit in all_units.items():
        if unit.is_alive and not unit.extracted:
            fov = compute_fov(
                unit.position.x, unit.position.y,
                unit.vision_range,
                grid_width, grid_height,
                obstacles,
            )
            set_fov_cache(match_id, uid, fov)

    # --- Step 6: Build and send FOV-filtered payloads to each human player ---
    # Use shared team FOV: each player sees the combined vision of all teammates
    full_snapshot = get_players_snapshot(match_id)

    # Pre-compute team FOV for each team (all alive members, including AI)
    team_a_fov = get_team_fov(match_id, team_a) if team_a else set()
    team_b_fov = get_team_fov(match_id, team_b) if team_b else set()
    team_c_fov = get_team_fov(match_id, team_c) if team_c else set()
    team_d_fov = get_team_fov(match_id, team_d) if team_d else set()

    # Map team letter to precomputed FOV
    team_fov_map = {
        "a": team_a_fov,
        "b": team_b_fov,
        "c": team_c_fov,
        "d": team_d_fov,
    }

    for pid in connections:
        # Determine which team this player is on and use the team's combined FOV
        player_data = full_snapshot.get(pid, {})
        player_team = player_data.get("team", "")

        player_fov = team_fov_map.get(player_team)
        if not player_fov:
            # Fallback to individual FOV (e.g. FFA mode with no teams)
            player_fov = get_fov_cache(match_id, pid)

        # Filter players snapshot: only include units visible in this player's FOV
        # Always include the player themselves
        filtered_players = {}
        for uid, data in full_snapshot.items():
            if uid == pid:
                filtered_players[uid] = data
                continue
            pos = data["position"]
            if (pos["x"], pos["y"]) in player_fov:
                filtered_players[uid] = data
            elif data["team"] == full_snapshot.get(pid, {}).get("team"):
                # Allies are always visible (show position even out of FOV)
                filtered_players[uid] = data

        # Filter actions: only include actions involving visible units
        filtered_actions = []
        for a in turn_result.actions:
            action_dict = a.model_dump()
            # Show action if actor is visible or player is the target
            actor_unit = all_units.get(a.player_id)
            if actor_unit and (actor_unit.position.x, actor_unit.position.y) in player_fov:
                filtered_actions.append(action_dict)
            elif a.target_id == pid:
                # Player was attacked from outside FOV
                action_dict["message"] = "You were attacked from the shadows!"
                filtered_actions.append(action_dict)

        payload = {
            "type": "turn_result",
            "match_id": match_id,
            "turn_number": turn_number,
            "actions": filtered_actions,
            "deaths": turn_result.deaths,
            "winner": turn_result.winner,
            "players": filtered_players,
            "visible_tiles": list(player_fov) if player_fov else [],
        }

        # Phase 26C: Include totem data, FOV-filtered
        if match.totems:
            visible_totems = [
                t for t in match.totems
                if (t.get("x"), t.get("y")) in player_fov
            ] if player_fov else list(match.totems)
            if visible_totems:
                payload["totems"] = visible_totems

        # Include door changes for dungeon matches
        if turn_result.door_changes:
            payload["door_changes"] = turn_result.door_changes
        if dungeon_state:
            payload["door_states"] = dungeon_state["door_states"]
            payload["chest_states"] = dungeon_state["chest_states"]
            payload["ground_items"] = dungeon_state["ground_items"]

        # Include loot events (Phase 4D-2)
        if turn_result.loot_drops:
            # Filter loot drops to only visible tiles
            visible_drops = [
                drop for drop in turn_result.loot_drops
                if (drop["x"], drop["y"]) in player_fov
            ] if player_fov else turn_result.loot_drops
            if visible_drops:
                payload["loot_drops"] = visible_drops
        if turn_result.chest_opened:
            payload["chest_opened"] = turn_result.chest_opened
        if turn_result.items_picked_up:
            payload["items_picked_up"] = turn_result.items_picked_up
        if turn_result.items_used:
            payload["items_used"] = turn_result.items_used

        # Include hero death events (Phase 4E-2: permadeath)
        if turn_result.hero_deaths:
            payload["hero_deaths"] = turn_result.hero_deaths

        # Phase 18F: Include elite kill notifications (rare/super unique deaths)
        if turn_result.elite_kills:
            payload["elite_kills"] = turn_result.elite_kills

        # Phase 12C: Include portal scroll state
        if match.portal:
            payload["portal"] = match.portal
        if match.channeling:
            payload["channeling"] = match.channeling
        if turn_result.portal_spawned:
            payload["portal_spawned"] = turn_result.portal_spawned
        if turn_result.portal_expired:
            payload["portal_expired"] = True
        if turn_result.extractions:
            payload["extractions"] = turn_result.extractions

        # Phase 12-5: Include stairs unlock state and floor number
        if stairs_info:
            payload["stairs_unlocked"] = stairs_info["unlocked"]
            payload["current_floor"] = stairs_info["current_floor"]

        # Include player's own inventory/equipment for private state
        player_unit = all_units.get(pid)
        if player_unit:
            payload["my_inventory"] = player_unit.inventory
            payload["my_equipment"] = player_unit.equipment

        # Include party member inventories so controlled unit inventory stays synced
        party = get_party_members(match_id, pid)
        if party:
            party_invs = {}
            for pm in party:
                pm_unit = all_units.get(pm["unit_id"])
                if pm_unit:
                    party_invs[pm["unit_id"]] = {
                        "inventory": list(pm_unit.inventory),
                        "equipment": dict(pm_unit.equipment),
                    }
            if party_invs:
                payload["party_inventories"] = party_invs

        # Phase 10C-4 / 10G-3: Include auto-target + skill state so client stays in sync
        auto_targets = {}
        player_unit_at = all_units.get(pid)
        if player_unit_at and player_unit_at.auto_target_id:
            auto_targets[pid] = {
                "target_id": player_unit_at.auto_target_id,
                "skill_id": player_unit_at.auto_skill_id,
            }
        if party:
            for pm in party:
                pm_unit = all_units.get(pm["unit_id"])
                if pm_unit and pm_unit.auto_target_id:
                    auto_targets[pm["unit_id"]] = {
                        "target_id": pm_unit.auto_target_id,
                        "skill_id": pm_unit.auto_skill_id,
                    }
        if auto_targets:
            payload["auto_targets"] = auto_targets

        await ws_manager.send_to_player(match_id, pid, payload)

    # After turn broadcast, send each human player their remaining queue + party info
    for pid in connections:
        queue = get_player_queue(match_id, pid)
        queue_payload = {
            "type": "queue_updated",
            "queue": [{"action_type": a.action_type.value,
                        "target_x": a.target_x, "target_y": a.target_y,
                        "skill_id": a.skill_id}
                       for a in queue],
        }
        # Include party member info for players with allies
        party = get_party_members(match_id, pid)
        if party:
            queue_payload["party"] = party
        await ws_manager.send_to_player(match_id, pid, queue_payload)

    # Clear dead players' queues and auto-targets after broadcasting
    for death_pid in turn_result.deaths:
        clear_player_queue(match_id, death_pid)
        clear_auto_target(match_id, death_pid)
        # Also clear any other unit's auto-target if it was targeting this dead unit
        # and notify the owning player (Phase 10C-3)
        for uid, unit in all_units.items():
            if unit.auto_target_id == death_pid:
                clear_auto_target(match_id, uid)
                # Determine who to notify: the human player controlling this unit
                notify_pid = unit.controlled_by or uid
                if notify_pid in connections:
                    await ws_manager.send_to_player(match_id, notify_pid, {
                        "type": "auto_target_cleared",
                        "unit_id": uid,
                        "reason": "target_died",
                    })

    # --- Wave Spawner: advance wave if current wave is cleared ---
    wave_info = advance_wave_if_cleared(match_id)

    # --- Phase 12-5: Floor Advance via Stairs ---
    if turn_result.floor_advance and match_is_dungeon:
        floor_data = advance_floor(match_id)
        if floor_data:
            new_floor = floor_data["floor_number"]
            turn_result.new_floor_number = new_floor

            # Build per-player floor_advance payloads with initial FOV
            new_all_units = get_match_players(match_id)
            new_map_data = load_map(match.config.map_id)
            new_grid_w = new_map_data.get("width", 15)
            new_grid_h = new_map_data.get("height", 15)
            new_obstacles = get_obstacles_with_door_states(match.config.map_id, match.door_states)

            for pid in connections:
                # Compute this player's team FOV on the new floor
                player_data_new = new_all_units.get(pid)
                if not player_data_new:
                    continue
                player_team_new = player_data_new.team
                new_team_a, new_team_b, new_team_c, new_team_d = get_match_teams(match_id)
                team_map_new = {"a": new_team_a, "b": new_team_b, "c": new_team_c, "d": new_team_d}
                team_members = team_map_new.get(player_team_new, [])
                team_fov_new = get_team_fov(match_id, team_members)

                floor_payload = {
                    "type": "floor_advance",
                    "match_id": match_id,
                    "floor_number": new_floor,
                    "grid_width": floor_data["grid_width"],
                    "grid_height": floor_data["grid_height"],
                    "tiles": floor_data["tiles"],
                    "tile_legend": floor_data["tile_legend"],
                    "obstacles": floor_data["obstacles"],
                    "door_states": floor_data["door_states"],
                    "chest_states": floor_data["chest_states"],
                    "players": floor_data["players"],
                    "is_dungeon": True,
                    "visible_tiles": list(team_fov_new) if team_fov_new else [],
                    "stairs_unlocked": False,
                }
                if match.theme_id:
                    floor_payload["theme_id"] = match.theme_id
                await ws_manager.send_to_player(match_id, pid, floor_payload)

            print(f"[Floor] Match {match_id} — Descended to Floor {new_floor}")
            # After floor advance, suppress any winner — the match continues
            turn_result.winner = None
            return  # Skip match-end checks this tick; next tick processes new floor

    if wave_info:
        # A new wave just spawned — broadcast to all players
        wave_payload = {
            "type": "wave_started",
            "match_id": match_id,
            "wave_number": wave_info["wave_number"],
            "wave_name": wave_info["wave_name"],
            "enemy_count": wave_info["enemy_count"],
            "total_waves": wave_info["total_waves"],
        }
        await ws_manager.broadcast_to_match(match_id, wave_payload)
        print(f"[Wave] Match {match_id} — Wave {wave_info['wave_number']}/{wave_info['total_waves']}: {wave_info['wave_name']} ({wave_info['enemy_count']} enemies)")

    # Suppress victory for wave maps until all waves are cleared
    if turn_result.winner and is_wave_map(match_id) and not all_waves_complete(match_id):
        turn_result.winner = None  # More waves to go — suppress victory

    # Check for match end
    if turn_result.winner:
        winner_display = ""
        team_labels = {
            "team_a": "Team A wins!",
            "team_b": "Team B wins!",
            "team_c": "Team C wins!",
            "team_d": "Team D wins!",
            "draw": "Draw!",
            "dungeon_extract": "Dungeon Escaped!",
            "party_wipe": "Party Wiped!",
        }
        if turn_result.winner in team_labels:
            winner_display = team_labels[turn_result.winner]
        else:
            # FFA — winner is a player_id
            winner_player = all_units.get(turn_result.winner)
            if winner_player:
                winner_display = winner_player.username

        end_payload = {
            "type": "match_end",
            "match_id": match_id,
            "winner": turn_result.winner,
            "winner_username": winner_display,
            "final_turn": turn_number,
        }

        # Include per-hero outcomes (Phase 4E-2) + combat stats
        hero_outcomes = get_match_end_payload(match_id)
        end_payload.update(hero_outcomes)

        await ws_manager.broadcast_to_match(match_id, end_payload)

        # Arena Analyst: save match report before cleanup
        save_match_report(match_id, turn_result.winner, turn_number)

        end_match(match_id)
        clear_ai_patrol_state()  # Clean up AI scouting memory
        scheduler_manager.remove_match_tick(match_id)
        print(f"[Match] Match {match_id} ended — winner: {winner_display}")
