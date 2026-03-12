"""
Match Routes — In-match state and control endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.player import PlayerReadyRequest
from app.core.match_manager import (
    get_match,
    get_match_players,
    set_player_ready,
    start_match,
    get_match_start_payload,
    get_match_start_payload_for_player,
    get_lobby_players_payload,
    clear_player_queue,
    remove_last_action,
    get_player_queue,
)
from app.services.websocket import ws_manager

router = APIRouter()


class QueueRequest(BaseModel):
    player_id: str


@router.get("/{match_id}")
async def get_match_state(match_id: str):
    """Get current match state."""
    match = get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    players = get_match_players(match_id)
    return {
        "match": match.model_dump(),
        "players": {pid: p.model_dump() for pid, p in players.items()},
    }


@router.post("/{match_id}/ready")
async def player_ready(match_id: str, request: PlayerReadyRequest):
    """Set player ready status. Match starts when all players are ready."""
    all_ready = set_player_ready(match_id, request.player_id, request.ready)

    # Broadcast updated ready state to all players
    await ws_manager.broadcast_to_match(match_id, {
        "type": "player_ready",
        "player_id": request.player_id,
        "players": get_lobby_players_payload(match_id),
    })

    if all_ready:
        start_match(match_id)
        # Send per-player match_start with FOV-filtered data
        connections = ws_manager.get_match_connections(match_id)
        for pid in connections:
            player_payload = get_match_start_payload_for_player(match_id, pid)
            if player_payload:
                await ws_manager.send_to_player(match_id, pid, player_payload)
        print(f"[Match] Match {match_id} started!")
        return {"status": "match_starting", "all_ready": True}

    return {"status": "waiting", "all_ready": False}


@router.post("/{match_id}/clear_queue")
async def clear_queue(match_id: str, request: QueueRequest):
    """Clear all queued actions for a player."""
    match = get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    count = clear_player_queue(match_id, request.player_id)

    # Notify the player via WS
    await ws_manager.send_to_player(match_id, request.player_id, {
        "type": "queue_cleared",
        "cleared_count": count,
    })

    return {"status": "ok", "cleared_count": count}


@router.post("/{match_id}/remove_last_action")
async def remove_last(match_id: str, request: QueueRequest):
    """Remove the last queued action for a player."""
    match = get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    removed = remove_last_action(match_id, request.player_id)

    if removed:
        # Send updated queue back to player
        queue = get_player_queue(match_id, request.player_id)
        await ws_manager.send_to_player(match_id, request.player_id, {
            "type": "queue_updated",
            "queue": [{"action_type": a.action_type.value,
                        "target_x": a.target_x, "target_y": a.target_y}
                       for a in queue],
        })
        return {"status": "ok", "removed": True, "queue_length": len(queue)}

    return {"status": "ok", "removed": False}


@router.get("/{match_id}/queue/{player_id}")
async def get_queue(match_id: str, player_id: str):
    """Get a player's current action queue."""
    match = get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    queue = get_player_queue(match_id, player_id)
    return {
        "queue": [{"action_type": a.action_type.value,
                    "target_x": a.target_x, "target_y": a.target_y}
                   for a in queue],
        "queue_length": len(queue),
    }
