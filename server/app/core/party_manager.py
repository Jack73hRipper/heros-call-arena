"""
Party Manager — Handles party control, group actions, and stance management.

Extracted from match_manager.py during P2 refactoring.
Manages player-controlled AI allies, group action queueing,
multi-select, stance changes, and party member info.
"""

from __future__ import annotations

# Shared state dicts — imported from match_manager
from app.core.match_manager import (
    _player_states,
    _hero_ally_map,
    _action_queues,
    queue_action,
    clear_player_queue,
)


def is_party_member(match_id: str, player_id: str, unit_id: str) -> bool:
    """Check if unit_id is an allied AI unit that player_id is allowed to control.

    A player can control:
      - Hero allies they own (tracked via _hero_ally_map by owner_username)
      - Generic AI allies on their same team (ai- prefixed, team matches)
    """
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    unit = players.get(unit_id)
    if not player or not unit:
        return False
    if unit.unit_type != "ai":
        return False
    if unit.team != player.team:
        return False
    # Hero allies: check ownership via _hero_ally_map
    ally_map = _hero_ally_map.get(match_id, {})
    if unit_id in ally_map:
        return ally_map[unit_id] == player.username
    # Generic AI allies (ai- prefix, same team): controllable by any human on team
    if unit_id.startswith("ai-") and not unit.enemy_type:
        return True
    return False


def set_party_control(match_id: str, player_id: str, unit_id: str) -> bool:
    """Set a party member as controlled by the player (additive — multi-select).

    Does NOT release previously controlled units.  Multiple units can be
    controlled simultaneously by the same player.

    Returns True if successful, False if not a valid party member.
    """
    if not is_party_member(match_id, player_id, unit_id):
        return False
    players = _player_states.get(match_id, {})
    unit = players.get(unit_id)
    if not unit or not unit.is_alive:
        return False
    unit.controlled_by = player_id
    return True


def release_party_control(match_id: str, player_id: str, unit_id: str | None = None) -> bool:
    """Release player control of a party member (returns it to AI autonomy).

    If unit_id is None, releases ALL units controlled by this player.
    """
    players = _player_states.get(match_id, {})
    released = False
    for uid, u in players.items():
        if u.controlled_by == player_id:
            if unit_id is None or uid == unit_id:
                u.controlled_by = None
                released = True
    return released


def select_all_party(match_id: str, player_id: str) -> list[str]:
    """Select ALL alive party members for control by the player.

    Returns list of unit IDs that were successfully selected.
    """
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player:
        return []
    ally_map = _hero_ally_map.get(match_id, {})
    selected = []
    for uid, u in players.items():
        if uid == player_id:
            continue
        if u.unit_type != "ai" or u.team != player.team:
            continue
        if u.enemy_type:
            continue
        if not u.is_alive:
            continue
        # Check ownership for hero allies
        if uid in ally_map and ally_map[uid] != player.username:
            continue
        u.controlled_by = player_id
        selected.append(uid)
    return selected


def release_all_party(match_id: str, player_id: str) -> list[str]:
    """Release ALL units controlled by this player back to AI autonomy.

    Returns list of unit IDs that were released.
    """
    players = _player_states.get(match_id, {})
    released = []
    for uid, u in players.items():
        if u.controlled_by == player_id:
            u.controlled_by = None
            released.append(uid)
    return released


def queue_group_action(match_id: str, player_id: str, action_type: str,
                       target_x: int | None = None, target_y: int | None = None,
                       skill_id: str | None = None,
                       unit_ids: list[str] | None = None) -> dict:
    """Queue the same action for multiple controlled units.

    If unit_ids is None, queues for all units currently controlled by player_id
    (plus the player themselves).

    Returns {"queued": [unit_id, ...], "failed": [{unit_id, reason}, ...]}.
    """
    from app.models.actions import PlayerAction, ActionType as AT

    players = _player_states.get(match_id, {})
    # Determine which units to issue the action to
    if unit_ids is None:
        # All currently controlled units + player themselves
        target_units = [player_id]
        for uid, u in players.items():
            if u.controlled_by == player_id and uid != player_id:
                target_units.append(uid)
    else:
        target_units = unit_ids

    queued = []
    failed = []
    for uid in target_units:
        # Validate that this player can control this unit
        if uid != player_id and not is_party_member(match_id, player_id, uid):
            failed.append({"unit_id": uid, "reason": "Not a valid party member"})
            continue
        action = PlayerAction(
            player_id=uid,
            action_type=AT(action_type),
            target_x=target_x,
            target_y=target_y,
            skill_id=skill_id,
        )
        result = queue_action(match_id, uid, action)
        if result is True:
            queued.append(uid)
        else:
            reason = result if isinstance(result, str) else "Cannot queue action"
            failed.append({"unit_id": uid, "reason": reason})
    return {"queued": queued, "failed": failed}


def queue_group_batch_actions(match_id: str, player_id: str,
                              unit_actions: list[dict]) -> dict:
    """Queue per-unit batch actions for multiple units at once.

    Each entry in unit_actions: {"unit_id": str, "actions": [{"action_type", "target_x", "target_y", "skill_id"}, ...]}
    Clears existing queue for each unit before queueing new actions (replace mode).

    Returns {"queued": [{unit_id, count}, ...], "failed": [{unit_id, reason}, ...]}.
    """
    from app.models.actions import PlayerAction, ActionType as AT

    queued = []
    failed = []
    valid_types = ("move", "attack", "ranged_attack", "wait", "interact", "loot", "use_item", "skill")

    for entry in unit_actions:
        uid = entry.get("unit_id")
        actions = entry.get("actions", [])
        if not uid:
            failed.append({"unit_id": uid, "reason": "Missing unit_id"})
            continue
        # Validate that this player can control this unit
        if uid != player_id and not is_party_member(match_id, player_id, uid):
            failed.append({"unit_id": uid, "reason": "Not a valid party member"})
            continue

        # Clear existing queue (replace mode)
        clear_player_queue(match_id, uid)

        count = 0
        error = None
        for act in actions:
            at = act.get("action_type")
            if at not in valid_types:
                error = f"Unknown action_type: {at}"
                break
            pa = PlayerAction(
                player_id=uid,
                action_type=AT(at),
                target_x=act.get("target_x"),
                target_y=act.get("target_y"),
                skill_id=act.get("skill_id"),
            )
            result = queue_action(match_id, uid, pa)
            if result is True:
                count += 1
            else:
                error = result if isinstance(result, str) else "Cannot queue action"
                break

        if count > 0:
            queued.append({"unit_id": uid, "count": count})
        if error:
            failed.append({"unit_id": uid, "reason": error})

    return {"queued": queued, "failed": failed}


def get_controlled_unit_ids(match_id: str) -> set[str]:
    """Return set of AI unit IDs that are currently player-controlled and have queued actions.

    Used during tick processing to skip AI decisions for these units.
    """
    players = _player_states.get(match_id, {})
    match_queues = _action_queues.get(match_id, {})
    controlled = set()
    for uid, u in players.items():
        if u.controlled_by and u.unit_type == "ai":
            # Only skip AI if the controlling player has queued an action for this unit
            if uid in match_queues and match_queues[uid]:
                controlled.add(uid)
    return controlled


# ---------- Phase 7C: Stance Management ----------

def set_unit_stance(match_id: str, player_id: str, unit_id: str, stance: str) -> bool:
    """Set the AI stance for a single hero ally unit.

    Returns True if successful, False if invalid unit/stance.
    Only hero allies (with hero_id) support stances.
    """
    from app.core.ai_behavior import VALID_STANCES
    if stance not in VALID_STANCES:
        return False
    if not is_party_member(match_id, player_id, unit_id):
        return False
    players = _player_states.get(match_id, {})
    unit = players.get(unit_id)
    if not unit or not unit.is_alive:
        return False
    unit.ai_stance = stance
    return True


def set_all_stances(match_id: str, player_id: str, stance: str) -> list[str]:
    """Set the AI stance for ALL alive hero allies owned by the player.

    Returns list of unit IDs that were successfully updated.
    """
    from app.core.ai_behavior import VALID_STANCES
    if stance not in VALID_STANCES:
        return []
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player:
        return []
    ally_map = _hero_ally_map.get(match_id, {})
    updated = []
    for uid, u in players.items():
        if uid == player_id:
            continue
        if u.unit_type != "ai" or u.team != player.team:
            continue
        if u.enemy_type:
            continue
        if not u.is_alive:
            continue
        # Check ownership for hero allies
        if uid in ally_map and ally_map[uid] != player.username:
            continue
        u.ai_stance = stance
        updated.append(uid)
    return updated


def get_party_members(match_id: str, player_id: str) -> list[dict]:
    """Get list of party member info for a player (allies they can control)."""
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player:
        return []
    ally_map = _hero_ally_map.get(match_id, {})
    party = []
    for uid, u in players.items():
        if uid == player_id:
            continue
        if u.unit_type != "ai" or u.team != player.team:
            continue
        # Skip enemy-type AI (dungeon enemies)
        if u.enemy_type:
            continue
        # Check ownership for hero allies
        if uid in ally_map and ally_map[uid] != player.username:
            continue
        party.append({
            "unit_id": uid,
            "username": u.username,
            "class_id": u.class_id,
            "hp": u.hp,
            "max_hp": u.max_hp,
            "is_alive": u.is_alive,
            "hero_id": u.hero_id,
            "controlled_by": u.controlled_by,
            "position": {"x": u.position.x, "y": u.position.y},
            "ai_stance": u.ai_stance,
        })
    return party
