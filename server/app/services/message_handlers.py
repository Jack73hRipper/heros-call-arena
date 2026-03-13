"""
Message Handlers — Individual handler functions for each WebSocket message type.

Each handler is an async function receiving (ws_manager, match_id, player_id, data)
and returning a sentinel string when the caller should `continue` past the current
message (i.e. the handler already sent an error/response).  A return of None means
the handler completed normally and the loop should proceed to the next receive.

Extracted from websocket.py during P3 refactoring (pure mechanical move).
"""

from __future__ import annotations

from app.models.actions import PlayerAction, ActionType
from app.core.match_manager import (
    set_player_ready,
    start_match,
    get_match,
    get_match_start_payload_for_player,
    get_lobby_players_payload,
    get_wave_state,
    queue_action,
    clear_player_queue,
    remove_last_action,
    get_player_queue,
    change_player_team,
    get_player_username,
    add_lobby_message,
    update_match_config,
    select_class,
    equip_item,
    unequip_item,
    destroy_item,
    select_heroes,
    validate_dungeon_hero_selections,
    is_party_member,
    set_party_control,
    release_party_control,
    get_party_members,
    transfer_item_in_match,
    get_party_member_inventory,
    select_all_party,
    release_all_party,
    queue_group_action,
    queue_group_batch_actions,
    set_unit_stance,
    set_all_stances,
    clear_auto_target,
    set_auto_target,
)
from app.services.scheduler import scheduler_manager

# Sentinel returned by handlers to signal ``continue`` in the receive loop
SKIP = "SKIP"


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

async def handle_action(ws_manager, match_id: str, player_id: str, data: dict):
    """Handle a single queued action (move/attack/ranged/wait/interact/loot/use_item/skill)."""
    action_type = data.get("action_type")
    if action_type not in ("move", "attack", "ranged_attack", "wait", "interact", "loot", "use_item", "skill"):
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": f"Unknown action_type: {action_type}",
        })
        return SKIP

    # Phase 6C: Validate skill_id when action_type is "skill"
    if action_type == "skill":
        skill_id = data.get("skill_id")
        if not skill_id:
            await ws_manager.send_to_player(match_id, player_id, {
                "type": "error",
                "message": "Missing skill_id for skill action",
            })
            return SKIP
        from app.core.skills import get_skill as _ws_get_skill
        if _ws_get_skill(skill_id) is None:
            await ws_manager.send_to_player(match_id, player_id, {
                "type": "error",
                "message": f"Unknown skill_id: {skill_id}",
            })
            return SKIP

    # Party control: if unit_id is specified, queue for that allied unit
    unit_id = data.get("unit_id", player_id)
    if unit_id != player_id:
        if not is_party_member(match_id, player_id, unit_id):
            await ws_manager.send_to_player(match_id, player_id, {
                "type": "error",
                "message": f"Cannot control unit: {unit_id}",
            })
            return SKIP

    # Build PlayerAction and queue it (append to persistent queue)
    action = PlayerAction(
        player_id=unit_id,
        action_type=ActionType(action_type),
        target_x=data.get("target_x"),
        target_y=data.get("target_y"),
        skill_id=data.get("skill_id"),  # Phase 6A: pass skill_id for SKILL actions
        target_id=data.get("target_id"),  # Entity-based targeting
    )
    result = queue_action(match_id, unit_id, action)

    if result is True:
        # Send back the full updated queue
        queue = get_player_queue(match_id, unit_id)
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "action_queued",
            "unit_id": unit_id,
            "action_type": action_type,
            "target_x": data.get("target_x"),
            "target_y": data.get("target_y"),
            "target_id": data.get("target_id"),
            "skill_id": data.get("skill_id"),
            "queue": [{"action_type": a.action_type.value,
                        "target_x": a.target_x, "target_y": a.target_y,
                        "skill_id": a.skill_id}
                       for a in queue],
            "queue_length": len(queue),
        })
    else:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": result if isinstance(result, str)
                else "Cannot queue action",
        })


async def handle_batch_actions(ws_manager, match_id: str, player_id: str, data: dict):
    """Smart right-click: clear queue then queue multiple actions at once."""
    actions_data = data.get("actions", [])
    valid_types = ("move", "attack", "ranged_attack", "wait", "interact", "loot", "use_item", "skill")

    # Party control: if unit_id is specified, queue for that allied unit
    unit_id = data.get("unit_id", player_id)
    if unit_id != player_id:
        if not is_party_member(match_id, player_id, unit_id):
            await ws_manager.send_to_player(match_id, player_id, {
                "type": "error",
                "message": f"Cannot control unit: {unit_id}",
            })
            return SKIP

    # Clear existing queue first (replace mode)
    clear_player_queue(match_id, unit_id)
    # QoL-A: auto-target is NOT cleared here.  If a right-click enemy sends
    # batch_actions + set_auto_target, the queue drains first and auto-target
    # takes over when the queue is empty.  For non-attack right-clicks, the
    # client sends an explicit clear_auto_target message, and queue_action()
    # also clears any stale auto-target on the first append.

    queued_count = 0
    error_msg = None
    for act in actions_data:
        at = act.get("action_type")
        if at not in valid_types:
            error_msg = f"Unknown action_type in batch: {at}"
            break
        pa = PlayerAction(
            player_id=unit_id,
            action_type=ActionType(at),
            target_x=act.get("target_x"),
            target_y=act.get("target_y"),
            skill_id=act.get("skill_id"),  # Phase 6A
            target_id=act.get("target_id"),  # Entity-based targeting
        )
        result = queue_action(match_id, unit_id, pa)
        if result is True:
            queued_count += 1
        else:
            error_msg = result if isinstance(result, str) else "Cannot queue action"
            break

    queue = get_player_queue(match_id, unit_id)
    if error_msg and queued_count == 0:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": error_msg,
        })
    else:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "queue_updated",
            "unit_id": unit_id,
            "batch": True,
            "queued_count": queued_count,
            "queue": [{"action_type": a.action_type.value,
                        "target_x": a.target_x, "target_y": a.target_y,
                        "skill_id": a.skill_id}
                       for a in queue],
        })


async def handle_clear_queue(ws_manager, match_id: str, player_id: str, data: dict):
    unit_id = data.get("unit_id", player_id)
    if unit_id != player_id and not is_party_member(match_id, player_id, unit_id):
        unit_id = player_id
    count = clear_player_queue(match_id, unit_id)
    # Phase 10B: clear_queue also cancels auto-target pursuit
    clear_auto_target(match_id, unit_id)
    await ws_manager.send_to_player(match_id, player_id, {
        "type": "queue_cleared",
        "unit_id": unit_id,
        "cleared_count": count,
        "queue": [],
    })


async def handle_remove_last(ws_manager, match_id: str, player_id: str, data: dict):
    unit_id = data.get("unit_id", player_id)
    if unit_id != player_id and not is_party_member(match_id, player_id, unit_id):
        unit_id = player_id
    removed = remove_last_action(match_id, unit_id)
    queue = get_player_queue(match_id, unit_id)
    await ws_manager.send_to_player(match_id, player_id, {
        "type": "queue_updated",
        "unit_id": unit_id,
        "removed": removed,
        "queue": [{"action_type": a.action_type.value,
                    "target_x": a.target_x, "target_y": a.target_y,
                    "skill_id": a.skill_id}
                   for a in queue],
    })


# ---------------------------------------------------------------------------
# Party handlers
# ---------------------------------------------------------------------------

async def handle_select_party_member(ws_manager, match_id: str, player_id: str, data: dict):
    """Player selects a party member to control."""
    unit_id = data.get("unit_id")
    if not unit_id:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": "Missing unit_id",
        })
        return SKIP
    success = set_party_control(match_id, player_id, unit_id)
    if success:
        party = get_party_members(match_id, player_id)
        unit_queue = get_player_queue(match_id, unit_id)
        # Include inventory data for the selected unit
        unit_inv = get_party_member_inventory(match_id, player_id, unit_id)
        response = {
            "type": "party_member_selected",
            "unit_id": unit_id,
            "party": party,
            "unit_queue": [{"action_type": a.action_type.value,
                            "target_x": a.target_x, "target_y": a.target_y,
                            "skill_id": a.skill_id}
                           for a in unit_queue],
        }
        if unit_inv:
            response["unit_inventory"] = unit_inv["inventory"]
            response["unit_equipment"] = unit_inv["equipment"]
        await ws_manager.send_to_player(match_id, player_id, response)
    else:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": f"Cannot select party member: {unit_id}",
        })


async def handle_release_party_member(ws_manager, match_id: str, player_id: str, data: dict):
    """Player releases control of a party member (back to AI)."""
    unit_id = data.get("unit_id")
    release_party_control(match_id, player_id, unit_id)
    party = get_party_members(match_id, player_id)
    await ws_manager.send_to_player(match_id, player_id, {
        "type": "party_member_released",
        "unit_id": unit_id,
        "party": party,
    })


async def handle_select_all_party(ws_manager, match_id: str, player_id: str, data: dict):
    """Select all alive party members for control."""
    selected = select_all_party(match_id, player_id)
    party = get_party_members(match_id, player_id)
    await ws_manager.send_to_player(match_id, player_id, {
        "type": "all_party_selected",
        "selected_ids": selected,
        "party": party,
    })


async def handle_release_all_party(ws_manager, match_id: str, player_id: str, data: dict):
    """Release all units controlled by this player back to AI."""
    released = release_all_party(match_id, player_id)
    party = get_party_members(match_id, player_id)
    await ws_manager.send_to_player(match_id, player_id, {
        "type": "all_party_released",
        "released_ids": released,
        "party": party,
    })


async def handle_group_action(ws_manager, match_id: str, player_id: str, data: dict):
    """Queue the same action for all controlled units (+ player)."""
    action_type = data.get("action_type")
    valid_types = ("move", "attack", "ranged_attack", "wait", "interact", "loot", "use_item", "skill")
    if action_type not in valid_types:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": f"Unknown action_type: {action_type}",
        })
        return SKIP
    unit_ids = data.get("unit_ids")  # optional — defaults to all controlled
    result = queue_group_action(
        match_id, player_id,
        action_type=action_type,
        target_x=data.get("target_x"),
        target_y=data.get("target_y"),
        skill_id=data.get("skill_id"),
        unit_ids=unit_ids,
    )
    # Return per-unit queue state
    all_queues = {}
    for uid in result["queued"]:
        q = get_player_queue(match_id, uid)
        all_queues[uid] = [{"action_type": a.action_type.value,
                            "target_x": a.target_x, "target_y": a.target_y,
                            "skill_id": a.skill_id} for a in q]
    await ws_manager.send_to_player(match_id, player_id, {
        "type": "group_action_queued",
        "queued": result["queued"],
        "failed": result["failed"],
        "queues": all_queues,
    })


async def handle_group_batch_actions(ws_manager, match_id: str, player_id: str, data: dict):
    """Queue per-unit batch paths for multiple units at once."""
    unit_actions = data.get("unit_actions", [])
    result = queue_group_batch_actions(match_id, player_id, unit_actions)
    # Return per-unit queue state
    all_queues = {}
    for entry in result["queued"]:
        uid = entry["unit_id"]
        q = get_player_queue(match_id, uid)
        all_queues[uid] = [{"action_type": a.action_type.value,
                            "target_x": a.target_x, "target_y": a.target_y,
                            "skill_id": a.skill_id} for a in q]
    await ws_manager.send_to_player(match_id, player_id, {
        "type": "group_batch_queued",
        "queued": result["queued"],
        "failed": result["failed"],
        "queues": all_queues,
    })


# ---------------------------------------------------------------------------
# Stance handlers
# ---------------------------------------------------------------------------

async def handle_set_stance(ws_manager, match_id: str, player_id: str, data: dict):
    """Set AI stance for a single hero ally unit."""
    unit_id = data.get("unit_id")
    stance = data.get("stance")
    if not unit_id or not stance:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": "Missing unit_id or stance",
        })
        return SKIP
    success = set_unit_stance(match_id, player_id, unit_id, stance)
    if success:
        party = get_party_members(match_id, player_id)
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "stance_updated",
            "unit_id": unit_id,
            "stance": stance,
            "party": party,
        })
    else:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": f"Cannot set stance for unit: {unit_id}",
        })


async def handle_set_all_stances(ws_manager, match_id: str, player_id: str, data: dict):
    """Set AI stance for ALL hero allies owned by the player."""
    stance = data.get("stance")
    if not stance:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": "Missing stance",
        })
        return SKIP
    updated = set_all_stances(match_id, player_id, stance)
    party = get_party_members(match_id, player_id)
    await ws_manager.send_to_player(match_id, player_id, {
        "type": "all_stances_updated",
        "stance": stance,
        "updated_ids": updated,
        "party": party,
    })


# ---------------------------------------------------------------------------
# Lobby handlers
# ---------------------------------------------------------------------------

async def handle_ready(ws_manager, match_id: str, player_id: str, data: dict):
    """Player signals ready; if all ready, validate heroes and start the match."""
    # Import match_tick here to avoid circular imports
    from app.services.tick_loop import match_tick

    all_ready = set_player_ready(match_id, player_id, True)

    # Broadcast player_ready with current lobby state
    await ws_manager.broadcast_to_match(match_id, {
        "type": "player_ready",
        "player_id": player_id,
        "players": get_lobby_players_payload(match_id),
    })

    # If all players ready, validate hero selections then start
    if all_ready:
        # Validate dungeon hero selections (4E-2)
        hero_valid, hero_error, offending_pid = validate_dungeon_hero_selections(match_id)
        if not hero_valid:
            # Un-ready the offending player (not the sender)
            # so the player who hasn't selected heroes must fix the issue
            if offending_pid:
                set_player_ready(match_id, offending_pid, False)
            else:
                set_player_ready(match_id, player_id, False)
            await ws_manager.broadcast_to_match(match_id, {
                "type": "error",
                "message": f"Cannot start: {hero_error}",
            })
            # Broadcast updated ready state so client resets
            await ws_manager.broadcast_to_match(match_id, {
                "type": "player_ready",
                "player_id": offending_pid or player_id,
                "players": get_lobby_players_payload(match_id),
            })
            return SKIP

        start_match(match_id)
        # Send per-player match_start with FOV-filtered data
        connections = ws_manager.get_match_connections(match_id)
        started = False
        for pid in connections:
            player_payload = get_match_start_payload_for_player(match_id, pid)
            if player_payload:
                await ws_manager.send_to_player(match_id, pid, player_payload)
                started = True
        if started:
            # Broadcast wave 1 info if this is a wave map
            wave_state = get_wave_state(match_id)
            if wave_state and wave_state["current_wave"] >= 1:
                wave_config = wave_state["wave_config"]
                waves = wave_config.get("waves", [])
                if waves:
                    w1 = waves[0]
                    await ws_manager.broadcast_to_match(match_id, {
                        "type": "wave_started",
                        "match_id": match_id,
                        "wave_number": w1.get("wave_number", 1),
                        "wave_name": w1.get("name", "Wave 1"),
                        "enemy_count": len(w1.get("enemies", [])),
                        "total_waves": wave_state["total_waves"],
                    })
            # Schedule recurring tick
            match = get_match(match_id)
            tick_rate = match.config.tick_rate if match else 10.0
            scheduler_manager.add_match_tick(match_id, match_tick, tick_rate)
            print(f"[Match] Match {match_id} started! Tick every {tick_rate}s")


async def handle_team_select(ws_manager, match_id: str, player_id: str, data: dict):
    """Player wants to switch teams in lobby."""
    new_team = data.get("team")
    if new_team not in ("a", "b", "c", "d"):
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": "Invalid team — must be 'a', 'b', 'c', or 'd'",
        })
        return SKIP
    success = change_player_team(match_id, player_id, new_team)
    if success:
        username = get_player_username(match_id, player_id)
        await ws_manager.broadcast_to_match(match_id, {
            "type": "team_changed",
            "player_id": player_id,
            "username": username,
            "team": new_team,
            "players": get_lobby_players_payload(match_id),
        })
    else:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": "Cannot change team — match may have started or invalid request",
        })


async def handle_lobby_chat(ws_manager, match_id: str, player_id: str, data: dict):
    """Player sends a chat message in lobby."""
    message_text = data.get("message", "").strip()
    if not message_text:
        return SKIP
    msg = add_lobby_message(match_id, player_id, message_text)
    if msg:
        await ws_manager.broadcast_to_match(match_id, {
            "type": "chat_message",
            "sender": msg["sender"],
            "sender_id": msg["sender_id"],
            "message": msg["message"],
            "timestamp": msg["timestamp"],
        })


async def handle_lobby_config(ws_manager, match_id: str, player_id: str, data: dict):
    """Host updates match config in lobby."""
    updates = data.get("config", {})
    result = update_match_config(match_id, player_id, updates)
    if result:
        await ws_manager.broadcast_to_match(match_id, {
            "type": "config_changed",
            "config": result,
            "players": get_lobby_players_payload(match_id),
        })
    else:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": "Cannot update config — not host or match already started",
        })


async def handle_class_select(ws_manager, match_id: str, player_id: str, data: dict):
    """Player selects a class in lobby."""
    class_id = data.get("class_id")
    if not class_id:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": "Missing class_id",
        })
        return SKIP
    success = select_class(match_id, player_id, class_id)
    if success:
        username = get_player_username(match_id, player_id)
        await ws_manager.broadcast_to_match(match_id, {
            "type": "class_changed",
            "player_id": player_id,
            "username": username,
            "class_id": class_id,
            "players": get_lobby_players_payload(match_id),
        })
    else:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": f"Invalid class selection: {class_id}",
        })


async def handle_hero_select(ws_manager, match_id: str, player_id: str, data: dict):
    """Player selects persistent heroes for dungeon match (4E-2, multi-hero support)."""
    hero_ids = data.get("hero_ids")
    # Backward compat: accept single hero_id too
    if not hero_ids:
        single_id = data.get("hero_id")
        if single_id:
            hero_ids = [single_id]
    if not hero_ids or len(hero_ids) == 0:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": "Missing hero_ids",
        })
        return SKIP
    results = select_heroes(match_id, player_id, hero_ids)
    if results:
        username = get_player_username(match_id, player_id)
        await ws_manager.broadcast_to_match(match_id, {
            "type": "hero_selected",
            "player_id": player_id,
            "username": username,
            "hero_ids": [r["hero_id"] for r in results],
            "heroes": results,
            # Backward compat: include first hero's info at top level
            "hero_id": results[0]["hero_id"],
            "hero_name": results[0]["hero_name"],
            "class_id": results[0]["class_id"],
            "stats": results[0]["stats"],
            "players": get_lobby_players_payload(match_id),
        })
        # Heroes are now spawned as AI allies — human keeps their own class
    else:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": f"Cannot select heroes: one or more heroes not found, dead, or not yours",
        })


# ---------------------------------------------------------------------------
# Inventory / Equipment handlers
# ---------------------------------------------------------------------------

async def handle_transfer_item(ws_manager, match_id: str, player_id: str, data: dict):
    """Transfer item between party members' inventories (in-match)."""
    from_unit_id = data.get("from_unit_id")
    to_unit_id = data.get("to_unit_id")
    item_index = data.get("item_index")
    if from_unit_id is None or to_unit_id is None or item_index is None:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": "Missing from_unit_id, to_unit_id, or item_index",
        })
        return SKIP
    result = transfer_item_in_match(
        match_id, player_id, from_unit_id, to_unit_id, int(item_index)
    )
    if result:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "item_transferred",
            **result,
        })
    else:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": "Cannot transfer item — invalid units, full inventory, or item not found",
        })


async def handle_get_party_inventory(ws_manager, match_id: str, player_id: str, data: dict):
    """Request a party member's inventory/equipment."""
    unit_id = data.get("unit_id")
    if not unit_id:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": "Missing unit_id",
        })
        return SKIP
    inv_data = get_party_member_inventory(match_id, player_id, unit_id)
    if inv_data:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "party_inventory",
            **inv_data,
        })
    else:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": f"Cannot access inventory for: {unit_id}",
        })


async def handle_equip_item(ws_manager, match_id: str, player_id: str, data: dict):
    """Player equips an item from inventory to equipment slot.
    Supports party members via optional unit_id field."""
    item_id = data.get("item_id")
    unit_id = data.get("unit_id", player_id)
    if not item_id:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": "Missing item_id",
        })
        return SKIP
    result = equip_item(match_id, unit_id, item_id)
    if result:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "item_equipped",
            **result,
        })
        # Broadcast updated player stats to all clients
        await ws_manager.broadcast_to_match(match_id, {
            "type": "player_stats_updated",
            "player_id": unit_id,
            "stats": result["player_stats"],
        })
    else:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": f"Cannot equip item: {item_id}",
        })


async def handle_unequip_item(ws_manager, match_id: str, player_id: str, data: dict):
    """Player unequips an item from equipment slot back to inventory.
    Supports party members via optional unit_id field."""
    slot = data.get("slot")
    unit_id = data.get("unit_id", player_id)
    if not slot:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": "Missing slot",
        })
        return SKIP
    result = unequip_item(match_id, unit_id, slot)
    if result:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "item_unequipped",
            **result,
        })
        # Broadcast updated player stats to all clients
        await ws_manager.broadcast_to_match(match_id, {
            "type": "player_stats_updated",
            "player_id": unit_id,
            "stats": result["player_stats"],
        })
    else:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": f"Cannot unequip from slot: {slot}",
        })


async def handle_destroy_item(ws_manager, match_id: str, player_id: str, data: dict):
    """Player permanently destroys an item from their inventory.
    Supports party members via optional unit_id field."""
    item_id = data.get("item_id")
    unit_id = data.get("unit_id", player_id)
    if not item_id:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": "Missing item_id",
        })
        return SKIP
    result = destroy_item(match_id, unit_id, item_id)
    if result:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "item_destroyed",
            **result,
        })
    else:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": f"Cannot destroy item: {item_id}",
        })


# ---------------------------------------------------------------------------
# Auto-Target handlers (Phase 10C)
# ---------------------------------------------------------------------------

async def handle_set_auto_target(ws_manager, match_id: str, player_id: str, data: dict):
    """Player right-clicked an enemy or pressed skill with selected target."""
    target_id = data.get("target_id")
    unit_id = data.get("unit_id", player_id)
    skill_id = data.get("skill_id")  # Phase 10G: optional skill for auto-cast
    if not target_id:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": "Missing target_id for set_auto_target",
        })
        return SKIP
    # Validate party control if targeting for a party member
    if unit_id != player_id:
        if not is_party_member(match_id, player_id, unit_id):
            await ws_manager.send_to_player(match_id, player_id, {
                "type": "error",
                "message": f"Cannot control unit: {unit_id}",
            })
            return SKIP
    result = set_auto_target(match_id, unit_id, target_id, skill_id=skill_id)
    if result is True:
        # Look up target username for client display
        target_username = get_player_username(match_id, target_id) or target_id
        response = {
            "type": "auto_target_set",
            "unit_id": unit_id,
            "target_id": target_id,
            "target_username": target_username,
        }
        # Phase 10G: Include skill info when a skill was specified
        if skill_id:
            from app.core.skills import get_skill
            skill_def = get_skill(skill_id)
            response["skill_id"] = skill_id
            response["skill_name"] = skill_def["name"] if skill_def else skill_id
        await ws_manager.send_to_player(match_id, player_id, response)
    else:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": result if isinstance(result, str) else "Cannot set auto-target",
        })


async def handle_clear_auto_target(ws_manager, match_id: str, player_id: str, data: dict):
    """Player explicitly cancels auto-target pursuit."""
    unit_id = data.get("unit_id", player_id)
    if unit_id != player_id:
        if not is_party_member(match_id, player_id, unit_id):
            unit_id = player_id
    clear_auto_target(match_id, unit_id)
    await ws_manager.send_to_player(match_id, player_id, {
        "type": "auto_target_cleared",
        "unit_id": unit_id,
        "reason": "cancelled",
    })


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

MESSAGE_HANDLERS = {
    "action": handle_action,
    "batch_actions": handle_batch_actions,
    "clear_queue": handle_clear_queue,
    "remove_last": handle_remove_last,
    "select_party_member": handle_select_party_member,
    "release_party_member": handle_release_party_member,
    "select_all_party": handle_select_all_party,
    "release_all_party": handle_release_all_party,
    "group_action": handle_group_action,
    "group_batch_actions": handle_group_batch_actions,
    "set_stance": handle_set_stance,
    "set_all_stances": handle_set_all_stances,
    "ready": handle_ready,
    "team_select": handle_team_select,
    "lobby_chat": handle_lobby_chat,
    "lobby_config": handle_lobby_config,
    "class_select": handle_class_select,
    "hero_select": handle_hero_select,
    "transfer_item": handle_transfer_item,
    "get_party_inventory": handle_get_party_inventory,
    "equip_item": handle_equip_item,
    "unequip_item": handle_unequip_item,
    "destroy_item": handle_destroy_item,
    "set_auto_target": handle_set_auto_target,
    "clear_auto_target": handle_clear_auto_target,
}


async def dispatch_message(ws_manager, match_id: str, player_id: str, data: dict) -> str | None:
    """
    Route an incoming WS message to the appropriate handler.

    Returns SKIP when the handler wants the caller to ``continue`` in the
    receive loop, or None on normal completion.  Returns SKIP for unknown
    message types after sending an error.
    """
    msg_type = data.get("type")
    handler = MESSAGE_HANDLERS.get(msg_type)
    if handler:
        return await handler(ws_manager, match_id, player_id, data)
    else:
        await ws_manager.send_to_player(match_id, player_id, {
            "type": "error",
            "message": f"Unknown message type: {msg_type}",
        })
        return SKIP
