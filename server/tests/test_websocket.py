"""
Tests for WebSocket infrastructure — connection tracking, messaging, malformed handling.
"""

import asyncio
import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.services.websocket import ws_manager
from app.core.match_manager import (
    create_match, get_match_players, remove_match,
    _active_matches, _player_states, _action_queues,
)


@pytest.fixture(autouse=True)
def clear_connections():
    """Reset WS manager and match state between tests."""
    ws_manager._connections.clear()
    _active_matches.clear()
    _player_states.clear()
    _action_queues.clear()
    yield
    ws_manager._connections.clear()
    _active_matches.clear()
    _player_states.clear()
    _action_queues.clear()


class TestWebSocketConnection:
    def test_connect_and_disconnect(self):
        client = TestClient(app)
        with client.websocket_connect("/ws/test123/player1") as ws:
            assert ws_manager.get_connection_count("test123") == 1
        # After disconnect, connection is cleaned up
        assert ws_manager.get_connection_count("test123") == 0

    def test_two_players_same_match(self):
        client = TestClient(app)
        with client.websocket_connect("/ws/test123/player1") as ws1:
            with client.websocket_connect("/ws/test123/player2") as ws2:
                assert ws_manager.get_connection_count("test123") == 2

    def test_ready_broadcast(self):
        client = TestClient(app)
        with client.websocket_connect("/ws/test123/player1") as ws1:
            with client.websocket_connect("/ws/test123/player2") as ws2:
                ws1.send_json({"type": "ready"})
                # Both players should receive the broadcast
                msg1 = ws1.receive_json()
                msg2 = ws2.receive_json()
                assert msg1["type"] == "player_ready"
                assert msg1["player_id"] == "player1"
                assert msg2["type"] == "player_ready"
                assert msg2["player_id"] == "player1"

    def test_action_queued_ack(self):
        """Action queued when player exists in a real match."""
        match, player = create_match("TestPlayer")
        mid = match.match_id
        pid = player.player_id
        match.status = "in_progress"  # Must be in-progress for actions
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            ws.send_json({"type": "action", "action_type": "move", "target_x": 5, "target_y": 3})
            msg = ws.receive_json()
            assert msg["type"] == "action_queued"
            assert msg["action_type"] == "move"

    def test_disconnect_broadcast(self):
        client = TestClient(app)
        with client.websocket_connect("/ws/test123/player2") as ws2:
            with client.websocket_connect("/ws/test123/player1") as ws1:
                pass  # player1 disconnects when exiting this block
            msg = ws2.receive_json()
            assert msg["type"] == "player_disconnected"
            assert msg["player_id"] == "player1"


class TestMalformedMessages:
    def test_invalid_json(self):
        client = TestClient(app)
        with client.websocket_connect("/ws/test123/player1") as ws:
            ws.send_text("not valid json {{{")
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "Invalid JSON" in msg["message"]

    def test_missing_type_field(self):
        client = TestClient(app)
        with client.websocket_connect("/ws/test123/player1") as ws:
            ws.send_json({"foo": "bar"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "type" in msg["message"]

    def test_unknown_action_type(self):
        client = TestClient(app)
        with client.websocket_connect("/ws/test123/player1") as ws:
            ws.send_json({"type": "action", "action_type": "fly"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "fly" in msg["message"]

    def test_unknown_message_type(self):
        client = TestClient(app)
        with client.websocket_connect("/ws/test123/player1") as ws:
            ws.send_json({"type": "dance"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "dance" in msg["message"]

    def test_server_survives_malformed_messages(self):
        """Server doesn't crash — subsequent valid messages still work."""
        match, player = create_match("TestPlayer")
        mid = match.match_id
        pid = player.player_id
        match.status = "in_progress"
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            ws.send_text("garbage")
            err = ws.receive_json()
            assert err["type"] == "error"

            # Valid message still works
            ws.send_json({"type": "action", "action_type": "wait"})
            msg = ws.receive_json()
            assert msg["type"] == "action_queued"
            assert msg["action_type"] == "wait"
