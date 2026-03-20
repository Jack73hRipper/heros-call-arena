"""
Action Queue — Persistent per-player action queue CRUD.

Extracted from match_manager.py as Phase 2 of the match-manager-split.
All queue operations import shared state from match_store.
"""

from __future__ import annotations

from app.core.match_store import _action_queues, _player_states, MAX_QUEUE_SIZE


def queue_action(match_id: str, player_id: str, action) -> bool | str:
    """Append an action to a player's persistent queue.

    Returns True on success, or an error string on failure.

    Phase 10B: Queueing a repositioning action (MOVE, INTERACT, LOOT) clears
    auto-target since it signals a new navigational intent.
    Combat actions (SKILL, ATTACK, RANGED_ATTACK, USE_ITEM) preserve
    auto-target so auto-attacks resume automatically after the queued
    action resolves — "skill weaving" without losing pursuit.
    """
    from app.models.actions import ActionType

    if match_id not in _action_queues:
        _action_queues[match_id] = {}
    # Verify player is alive
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player or not player.is_alive:
        return "Cannot queue action — you are dead"

    if player_id not in _action_queues[match_id]:
        _action_queues[match_id][player_id] = []

    if len(_action_queues[match_id][player_id]) >= MAX_QUEUE_SIZE:
        return f"Queue full — maximum {MAX_QUEUE_SIZE} actions"

    # Phase 10B / Balance-pass: Only repositioning actions break auto-target.
    # Combat actions (skills, attacks, items) preserve the pursuit so
    # auto-attacks fill every tick the player isn't actively casting.
    _PRESERVE_AUTO_TARGET = {
        ActionType.SKILL,
        ActionType.ATTACK,
        ActionType.RANGED_ATTACK,
        ActionType.USE_ITEM,
        ActionType.WAIT,
    }
    if player.auto_target_id is not None:
        action_type = getattr(action, 'action_type', None)
        if action_type not in _PRESERVE_AUTO_TARGET:
            player.auto_target_id = None
            player.auto_skill_id = None

    _action_queues[match_id][player_id].append(action)
    return True


def pop_next_actions(match_id: str) -> dict:
    """Pop the first action from each player's queue for this tick.

    Returns {player_id: PlayerAction} for players who have queued actions.
    Remaining actions stay in the queue for future ticks.
    """
    match_queues = _action_queues.get(match_id, {})
    actions = {}
    for pid, queue in list(match_queues.items()):
        if queue:
            actions[pid] = queue.pop(0)
        # Clean up empty queues
        if not queue:
            match_queues.pop(pid, None)
    return actions


def get_and_clear_actions(match_id: str) -> dict:
    """DEPRECATED — kept for backward compatibility.
    Use pop_next_actions() for the persistent queue model.
    """
    return pop_next_actions(match_id)


def clear_player_queue(match_id: str, player_id: str) -> int:
    """Clear all queued actions for a player. Returns number of actions cleared."""
    match_queues = _action_queues.get(match_id, {})
    queue = match_queues.get(player_id, [])
    count = len(queue)
    match_queues.pop(player_id, None)
    return count


def remove_last_action(match_id: str, player_id: str) -> bool:
    """Remove the last queued action for a player. Returns True if an action was removed."""
    match_queues = _action_queues.get(match_id, {})
    queue = match_queues.get(player_id, [])
    if queue:
        queue.pop()
        if not queue:
            match_queues.pop(player_id, None)
        return True
    return False


def get_player_queue(match_id: str, player_id: str) -> list:
    """Get a copy of a player's current action queue."""
    match_queues = _action_queues.get(match_id, {})
    return list(match_queues.get(player_id, []))
