"""
Integration tests for Chunk 3: Lobby UX Redesign (Bugs #5, #7, Lobby Chat).
Tests: AI visible in lobby, in-lobby config updates, lobby chat, host controls.
"""

from app.core.match_manager import (
    create_match, join_match, remove_player,
    change_player_team, get_player_username,
    get_lobby_players_payload, get_match,
    add_lobby_message, get_lobby_chat,
    update_match_config, get_match_config_payload,
    spawn_lobby_ai, set_player_ready, start_match,
)
from app.models.match import MatchConfig, MatchType


# ===== Bug #5: AI Visible in Lobby =====

def test_ai_visible_in_lobby_on_create():
    """AI units should appear in lobby player list when match is created with AI."""
    config = MatchConfig(match_type=MatchType.SOLO_PVE, ai_opponents=3, ai_allies=0)
    match, host = create_match("Host", config)
    mid = match.match_id

    payload = get_lobby_players_payload(mid)

    # Host + 3 AI opponents = 4 entries
    assert len(payload) == 4, f"Expected 4 players in lobby, got {len(payload)}"

    # Check AI units are present
    ai_entries = {pid: p for pid, p in payload.items() if p["unit_type"] == "ai"}
    assert len(ai_entries) == 3, f"Expected 3 AI in lobby, got {len(ai_entries)}"

    # AI should have names (class names), team, and ready status
    for pid, ai in ai_entries.items():
        assert len(ai["username"]) > 0, "AI should have a non-empty username"
        assert ai["team"] == "b"  # AI opponents on team B
        assert ai["is_ready"] is True  # AI always ready
    print("PASS: test_ai_visible_in_lobby_on_create")


def test_ai_allies_in_lobby():
    """AI allies should appear on team A in lobby."""
    config = MatchConfig(match_type=MatchType.MIXED, ai_opponents=2, ai_allies=2)
    match, host = create_match("Host", config)
    mid = match.match_id

    payload = get_lobby_players_payload(mid)

    # Host + 2 allies + 2 opponents = 5
    assert len(payload) == 5

    ai_entries = {pid: p for pid, p in payload.items() if p["unit_type"] == "ai"}
    assert len(ai_entries) == 4

    allies = [p for p in ai_entries.values() if p["team"] == "a"]
    opponents = [p for p in ai_entries.values() if p["team"] == "b"]
    assert len(allies) == 2
    assert len(opponents) == 2
    print("PASS: test_ai_allies_in_lobby")


def test_ai_in_match_state():
    """AI should be in match.ai_ids and match.player_ids during lobby."""
    config = MatchConfig(match_type=MatchType.SOLO_PVE, ai_opponents=2)
    match, host = create_match("Host", config)

    assert len(match.ai_ids) == 2
    # AI should be in player_ids too (for lobby payload filtering)
    ai_in_player_ids = [pid for pid in match.player_ids if pid.startswith("ai-")]
    assert len(ai_in_player_ids) == 2
    print("PASS: test_ai_in_match_state")


# ===== Bug #7: In-Lobby Config Changes =====

def test_host_can_change_map():
    """Host can change map in lobby."""
    config = MatchConfig(match_type=MatchType.PVP)
    match, host = create_match("Host", config)
    mid = match.match_id

    result = update_match_config(mid, host.player_id, {"map_id": "maze"})
    assert result is not None
    assert result["map_id"] == "maze"
    assert match.config.map_id == "maze"
    print("PASS: test_host_can_change_map")


def test_host_can_change_match_type():
    """Host can change match type and AI counts."""
    config = MatchConfig(match_type=MatchType.PVP)
    match, host = create_match("Host", config)
    mid = match.match_id

    result = update_match_config(mid, host.player_id, {
        "match_type": "solo_pve",
        "ai_opponents": 3,
    })
    assert result is not None
    assert result["match_type"] == "solo_pve"
    assert result["ai_opponents"] == 3

    # AI should have been spawned
    payload = get_lobby_players_payload(mid)
    ai_entries = {pid: p for pid, p in payload.items() if p["unit_type"] == "ai"}
    assert len(ai_entries) == 3
    print("PASS: test_host_can_change_match_type")


def test_non_host_cannot_change_config():
    """Non-host player cannot update config."""
    config = MatchConfig(match_type=MatchType.PVP)
    match, host = create_match("Host", config)
    mid = match.match_id

    result = join_match(mid, "Player2")
    _, p2 = result

    result = update_match_config(mid, p2.player_id, {"map_id": "maze"})
    assert result is None
    assert match.config.map_id == "arena_classic"  # Unchanged
    print("PASS: test_non_host_cannot_change_config")


def test_pvp_mode_clears_ai():
    """Switching to PvP mode should clear AI units."""
    config = MatchConfig(match_type=MatchType.MIXED, ai_opponents=3, ai_allies=1)
    match, host = create_match("Host", config)
    mid = match.match_id

    # Verify AI exist
    payload = get_lobby_players_payload(mid)
    ai_count_before = len([p for p in payload.values() if p["unit_type"] == "ai"])
    assert ai_count_before == 4

    # Switch to PvP
    result = update_match_config(mid, host.player_id, {"match_type": "pvp"})
    assert result is not None
    assert result["match_type"] == "pvp"
    assert result["ai_opponents"] == 0
    assert result["ai_allies"] == 0

    payload = get_lobby_players_payload(mid)
    ai_count_after = len([p for p in payload.values() if p["unit_type"] == "ai"])
    assert ai_count_after == 0
    print("PASS: test_pvp_mode_clears_ai")


def test_config_change_respawns_ai():
    """Changing AI count respawns AI with new count."""
    config = MatchConfig(match_type=MatchType.SOLO_PVE, ai_opponents=2)
    match, host = create_match("Host", config)
    mid = match.match_id

    # Start with 2 AI
    payload = get_lobby_players_payload(mid)
    ai_count = len([p for p in payload.values() if p["unit_type"] == "ai"])
    assert ai_count == 2

    # Change to 4 AI
    result = update_match_config(mid, host.player_id, {"ai_opponents": 4})
    assert result["ai_opponents"] == 4

    payload = get_lobby_players_payload(mid)
    ai_count = len([p for p in payload.values() if p["unit_type"] == "ai"])
    assert ai_count == 4
    print("PASS: test_config_change_respawns_ai")


def test_get_match_config_payload():
    """get_match_config_payload returns correct config dict."""
    config = MatchConfig(match_type=MatchType.MIXED, map_id="islands", ai_opponents=2, ai_allies=1)
    match, host = create_match("Host", config)
    mid = match.match_id

    payload = get_match_config_payload(mid)
    assert payload is not None
    assert payload["map_id"] == "islands"
    assert payload["match_type"] == "mixed"
    assert payload["ai_opponents"] == 2
    assert payload["ai_allies"] == 1
    assert payload["host_id"] == host.player_id
    print("PASS: test_get_match_config_payload")


# ===== Lobby Chat =====

def test_lobby_chat_basic():
    """Players can send and retrieve chat messages."""
    config = MatchConfig(match_type=MatchType.PVP)
    match, host = create_match("Host", config)
    mid = match.match_id

    msg = add_lobby_message(mid, host.player_id, "Hello world!")
    assert msg is not None
    assert msg["sender"] == "Host"
    assert msg["message"] == "Hello world!"

    messages = get_lobby_chat(mid)
    assert len(messages) == 1
    assert messages[0]["sender"] == "Host"
    print("PASS: test_lobby_chat_basic")


def test_lobby_chat_multiple_players():
    """Multiple players can chat."""
    config = MatchConfig(match_type=MatchType.PVP)
    match, host = create_match("Host", config)
    mid = match.match_id

    result = join_match(mid, "Player2")
    _, p2 = result

    add_lobby_message(mid, host.player_id, "Hello!")
    add_lobby_message(mid, p2.player_id, "Hi there!")

    messages = get_lobby_chat(mid)
    assert len(messages) == 2
    assert messages[0]["sender"] == "Host"
    assert messages[1]["sender"] == "Player2"
    print("PASS: test_lobby_chat_multiple_players")


def test_lobby_chat_not_in_game():
    """Cannot send chat after match starts."""
    config = MatchConfig(match_type=MatchType.PVP)
    match, host = create_match("Host", config)
    mid = match.match_id

    result = join_match(mid, "Player2")
    _, p2 = result

    set_player_ready(mid, host.player_id, True)
    set_player_ready(mid, p2.player_id, True)
    start_match(mid)

    msg = add_lobby_message(mid, host.player_id, "Should fail")
    assert msg is None
    print("PASS: test_lobby_chat_not_in_game")


def test_lobby_chat_message_truncated():
    """Long messages get truncated to 500 chars."""
    config = MatchConfig(match_type=MatchType.PVP)
    match, host = create_match("Host", config)
    mid = match.match_id

    long_msg = "x" * 1000
    msg = add_lobby_message(mid, host.player_id, long_msg)
    assert msg is not None
    assert len(msg["message"]) == 500
    print("PASS: test_lobby_chat_message_truncated")


# ===== Ready Check with AI =====

def test_ready_check_ignores_ai():
    """Ready check should only consider human players, not AI."""
    config = MatchConfig(match_type=MatchType.SOLO_PVE, ai_opponents=3)
    match, host = create_match("Host", config)
    mid = match.match_id

    # Only 1 human needed for PvE — should be ready when host readies up
    all_ready = set_player_ready(mid, host.player_id, True)
    assert all_ready is True
    print("PASS: test_ready_check_ignores_ai")


if __name__ == "__main__":
    test_ai_visible_in_lobby_on_create()
    test_ai_allies_in_lobby()
    test_ai_in_match_state()
    test_host_can_change_map()
    test_host_can_change_match_type()
    test_non_host_cannot_change_config()
    test_pvp_mode_clears_ai()
    test_config_change_respawns_ai()
    test_get_match_config_payload()
    test_lobby_chat_basic()
    test_lobby_chat_multiple_players()
    test_lobby_chat_not_in_game()
    test_lobby_chat_message_truncated()
    test_ready_check_ignores_ai()
    print("\n=== ALL CHUNK 3 TESTS PASSED ===")
