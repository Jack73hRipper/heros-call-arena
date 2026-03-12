"""
Lobby Routes — Create, list, and join matches.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.match import MatchConfig, MatchSummary
from app.models.player import PlayerJoinRequest, get_all_classes
from app.core.match_manager import (
    create_match,
    join_match,
    list_matches,
    get_match,
    get_player_joined_payload,
    get_lobby_players_payload,
    remove_player,
    change_player_team,
    get_player_username,
    update_match_config,
    get_match_config_payload,
    get_lobby_chat,
)
from app.services.websocket import ws_manager

router = APIRouter()


@router.get("/matches", response_model=list[MatchSummary])
async def get_matches():
    """List all available matches."""
    return list_matches()


@router.post("/create")
async def create_new_match(request: PlayerJoinRequest, config: MatchConfig | None = None):
    """Create a new match. The creator becomes the host."""
    match, player = create_match(request.username, config)
    return {
        "match_id": match.match_id,
        "player_id": player.player_id,
        "username": player.username,
        "status": match.status,
        "position": {"x": player.position.x, "y": player.position.y},
        "config": get_match_config_payload(match.match_id),
        "players": get_lobby_players_payload(match.match_id),
    }


@router.post("/join/{match_id}")
async def join_existing_match(match_id: str, request: PlayerJoinRequest):
    """Join an existing match by ID."""
    result = join_match(match_id, request.username)
    if not result:
        raise HTTPException(status_code=400, detail="Match not found, full, or already started")
    match, player = result

    # Broadcast player_joined to all connected players in this match
    payload = get_player_joined_payload(match_id, player.player_id)
    if payload:
        await ws_manager.broadcast_to_match(match_id, payload, exclude=player.player_id)

    return {
        "match_id": match.match_id,
        "player_id": player.player_id,
        "username": player.username,
        "player_count": len(match.player_ids),
        "position": {"x": player.position.x, "y": player.position.y},
        "players": get_lobby_players_payload(match_id),
        "config": get_match_config_payload(match_id),
        "chat": get_lobby_chat(match_id),
    }


@router.post("/leave/{match_id}")
async def leave_match(match_id: str, request: PlayerJoinRequest):
    """Leave a lobby/match. Cleans up player state and notifies others."""
    match = get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # Find the player_id by username in this match
    from app.core.match_manager import get_match_players
    players = get_match_players(match_id)
    player_id = None
    for pid, p in players.items():
        if p.username == request.username:
            player_id = pid
            break
    if not player_id:
        raise HTTPException(status_code=400, detail="Player not found in match")

    username = remove_player(match_id, player_id)

    # Broadcast player_disconnected to remaining players
    await ws_manager.broadcast_to_match(match_id, {
        "type": "player_disconnected",
        "player_id": player_id,
        "username": username or request.username,
    })

    return {"status": "ok", "message": f"{request.username} left the match"}


class TeamChangeRequest(BaseModel):
    player_id: str
    team: str  # "a" or "b"


@router.post("/{match_id}/team")
async def change_team(match_id: str, request: TeamChangeRequest):
    """Change a player's team assignment in the lobby."""
    match = get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.status != "waiting":
        raise HTTPException(status_code=400, detail="Cannot change teams after match starts")
    if request.team not in ("a", "b", "c", "d"):
        raise HTTPException(status_code=400, detail="Team must be 'a', 'b', 'c', or 'd'")

    success = change_player_team(match_id, request.player_id, request.team)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to change team")

    username = get_player_username(match_id, request.player_id)

    # Broadcast team change to all players
    await ws_manager.broadcast_to_match(match_id, {
        "type": "team_changed",
        "player_id": request.player_id,
        "username": username,
        "team": request.team,
        "players": get_lobby_players_payload(match_id),
    })

    return {
        "status": "ok",
        "player_id": request.player_id,
        "team": request.team,
    }


class ConfigUpdateRequest(BaseModel):
    player_id: str
    config: dict  # {map_id?, match_type?, ai_opponents?, ai_allies?}


@router.post("/{match_id}/config")
async def update_config(match_id: str, request: ConfigUpdateRequest):
    """Update match configuration in lobby. Host-only."""
    match = get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.status != "waiting":
        raise HTTPException(status_code=400, detail="Cannot change config after match starts")
    if request.player_id != match.host_id:
        raise HTTPException(status_code=403, detail="Only the host can change match configuration")

    result = update_match_config(match_id, request.player_id, request.config)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to update config")

    # Broadcast config change + updated player list (AI may have changed)
    await ws_manager.broadcast_to_match(match_id, {
        "type": "config_changed",
        "config": result,
        "players": get_lobby_players_payload(match_id),
    })

    return {"status": "ok", "config": result}


@router.get("/{match_id}/config")
async def get_config(match_id: str):
    """Get current match configuration."""
    config = get_match_config_payload(match_id)
    if not config:
        raise HTTPException(status_code=404, detail="Match not found")
    return config


@router.get("/{match_id}/chat")
async def get_chat(match_id: str):
    """Get lobby chat history."""
    match = get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return {"messages": get_lobby_chat(match_id)}


@router.get("/classes")
async def get_classes():
    """Get all available character classes and their stats."""
    all_classes = get_all_classes()
    return {
        "classes": {
            cid: {
                "class_id": c.class_id,
                "name": c.name,
                "role": c.role,
                "description": c.description,
                "base_hp": c.base_hp,
                "base_melee_damage": c.base_melee_damage,
                "base_ranged_damage": c.base_ranged_damage,
                "base_armor": c.base_armor,
                "base_vision_range": c.base_vision_range,
                "ranged_range": c.ranged_range,
                "color": c.color,
                "shape": c.shape,
            }
            for cid, c in all_classes.items()
        }
    }
