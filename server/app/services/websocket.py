"""
WebSocket Manager — Handles player connections and message broadcasting.

ConnectionManager tracks active WebSocket connections per match.
The websocket_endpoint dispatches incoming messages to handlers in
message_handlers.py.  The game-loop tick lives in tick_loop.py.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.match_manager import (
    remove_player,
    get_match,
    get_match_players,
    get_alive_count,
    get_player_username,
    _active_matches,
)
from app.services.tick_loop import match_tick  # noqa: F401 — re-export
from app.services.message_handlers import dispatch_message

router = APIRouter()


class ConnectionManager:
    """Tracks active WebSocket connections per match."""

    def __init__(self):
        # match_id -> {player_id -> WebSocket}
        self._connections: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, match_id: str, player_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if match_id not in self._connections:
            self._connections[match_id] = {}
        self._connections[match_id][player_id] = websocket
        print(f"[WS] Player {player_id} connected to match {match_id}")

    def disconnect(self, match_id: str, player_id: str) -> None:
        if match_id in self._connections:
            self._connections[match_id].pop(player_id, None)
            if not self._connections[match_id]:
                del self._connections[match_id]
        print(f"[WS] Player {player_id} disconnected from match {match_id}")

    async def send_to_player(self, match_id: str, player_id: str, data: dict) -> None:
        ws = self._connections.get(match_id, {}).get(player_id)
        if ws and ws.client_state == WebSocketState.CONNECTED:
            try:
                await ws.send_json(data)
            except Exception:
                pass

    async def broadcast_to_match(self, match_id: str, data: dict, exclude: str | None = None) -> None:
        """Broadcast to all players in a match. Optionally exclude one player_id."""
        connections = self._connections.get(match_id, {})
        for pid, ws in list(connections.items()):
            if pid == exclude:
                continue
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(data)
            except Exception:
                pass  # Handle stale connections gracefully

    def get_match_connections(self, match_id: str) -> dict[str, WebSocket]:
        return self._connections.get(match_id, {})

    def get_connection_count(self, match_id: str) -> int:
        return len(self._connections.get(match_id, {}))


ws_manager = ConnectionManager()


@router.websocket("/ws/{match_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, match_id: str, player_id: str):
    """
    WebSocket endpoint for a player in a match.

    Messages from client:
      {"type": "action", "action_type": "move", "target_x": 5, "target_y": 3}
      {"type": "action", "action_type": "attack", "target_x": 5, "target_y": 3}
      {"type": "action", "action_type": "ranged_attack", "target_x": 5, "target_y": 3}
      {"type": "action", "action_type": "wait"}
      {"type": "ready"}

    Messages from server:
      {"type": "turn_result", ...}
      {"type": "match_start", ...}
      {"type": "match_end", ...}
      {"type": "player_joined", ...}
      {"type": "error", "message": "..."}
    """
    # ── Diagnostic: log match/player state at connection time ──
    match = get_match(match_id)
    players = get_match_players(match_id) if match else {}
    if match and player_id in players:
        print(f"[WS] ✓ Connect OK: match={match_id} player={player_id} "
              f"status={match.status} players={list(players.keys())}")
    else:
        print(f"[WS] ✗ Connect MISMATCH: match={match_id} player={player_id} "
              f"match_found={match is not None} "
              f"player_found={player_id in players} "
              f"active_matches={list(_active_matches.keys())} "
              f"match_players={list(players.keys())}")

    await ws_manager.connect(match_id, player_id, websocket)

    try:
        while True:
            # Receive raw text first so we can handle malformed JSON
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                await ws_manager.send_to_player(match_id, player_id, {
                    "type": "error",
                    "message": "Invalid JSON",
                })
                continue

            if not isinstance(data, dict) or "type" not in data:
                await ws_manager.send_to_player(match_id, player_id, {
                    "type": "error",
                    "message": "Message must be a JSON object with a 'type' field",
                })
                continue

            # Dispatch to the appropriate handler in message_handlers.py
            await dispatch_message(ws_manager, match_id, player_id, data)

    except WebSocketDisconnect:
        ws_manager.disconnect(match_id, player_id)

        # Get username before removing (for broadcast)
        username = get_player_username(match_id, player_id)

        # Always broadcast disconnect so other clients aren't left waiting
        await ws_manager.broadcast_to_match(match_id, {
            "type": "player_disconnected",
            "player_id": player_id,
            "username": username or "Unknown",
        })

        match = get_match(match_id)
        if not match:
            # Match was already cleaned up (e.g., REST leave removed last player)
            return

        if match.status == "in_progress":
            # Mid-match disconnect: mark dead, clean up
            removed_name = remove_player(match_id, player_id)
            if removed_name is None:
                return  # Already removed by REST leave endpoint
            # If only 0-1 alive players remain, the tick will resolve victory
            alive = get_alive_count(match_id)
            if alive <= 1:
                print(f"[Match] Match {match_id} — not enough players, will resolve on next tick")
        else:
            # Lobby-phase disconnect: clean up ghost player
            removed_name = remove_player(match_id, player_id)
            if removed_name is None:
                return  # Already removed by REST leave endpoint
