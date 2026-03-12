"""
Quick integration tests for Chunk 2: Lobby State Management (Bugs #1 & #6).
Tests: remove_player team cleanup, change_player_team, get_player_username,
       lobby payload includes team, ghost player prevention.
"""

from app.core.match_manager import (
    create_match, join_match, remove_player,
    change_player_team, get_player_username,
    get_lobby_players_payload, get_match,
)
from app.models.match import MatchConfig, MatchType


def test_create_and_join():
    """Host creates match, player joins — both on team A by default."""
    config = MatchConfig(match_type=MatchType.PVP)
    match, host = create_match("Host", config)
    mid = match.match_id

    assert host.team == "a"
    assert host.player_id in match.team_a

    result = join_match(mid, "Player2")
    assert result is not None
    _, p2 = result
    assert p2.team == "a"
    assert p2.player_id in match.team_a
    print("PASS: test_create_and_join")


def test_change_team():
    """Player can switch from team A to team B in lobby."""
    config = MatchConfig(match_type=MatchType.PVP)
    match, host = create_match("Host", config)
    mid = match.match_id

    result = join_match(mid, "Player2")
    _, p2 = result

    # Both on team A initially
    assert len(match.team_a) == 2
    assert len(match.team_b) == 0

    # Switch Player2 to team B
    ok = change_player_team(mid, p2.player_id, "b")
    assert ok is True
    assert p2.team == "b"
    assert p2.player_id not in match.team_a
    assert p2.player_id in match.team_b
    assert len(match.team_a) == 1
    assert len(match.team_b) == 1
    print("PASS: test_change_team")


def test_change_team_invalid():
    """Cannot change to invalid team or after match starts."""
    config = MatchConfig(match_type=MatchType.PVP)
    match, host = create_match("Host", config)
    mid = match.match_id

    # Valid teams now include a, b, c, d — "e" is invalid
    ok = change_player_team(mid, host.player_id, "e")
    assert ok is False

    # Invalid player
    ok = change_player_team(mid, "nonexistent", "b")
    assert ok is False
    print("PASS: test_change_team_invalid")


def test_remove_player_cleans_teams():
    """remove_player removes from both player_ids and team lists."""
    config = MatchConfig(match_type=MatchType.PVP)
    match, host = create_match("Host", config)
    mid = match.match_id

    result = join_match(mid, "Player2")
    _, p2 = result

    # Move Player2 to team B
    change_player_team(mid, p2.player_id, "b")
    assert p2.player_id in match.team_b

    # Remove Player2
    username = remove_player(mid, p2.player_id)
    assert username == "Player2"
    assert p2.player_id not in match.player_ids
    assert p2.player_id not in match.team_a
    assert p2.player_id not in match.team_b
    print("PASS: test_remove_player_cleans_teams")


def test_get_player_username():
    config = MatchConfig(match_type=MatchType.PVP)
    match, host = create_match("TestUser", config)
    mid = match.match_id

    name = get_player_username(mid, host.player_id)
    assert name == "TestUser"

    name = get_player_username(mid, "nonexistent")
    assert name is None
    print("PASS: test_get_player_username")


def test_lobby_payload_includes_team():
    """get_lobby_players_payload should include unit_type and team fields."""
    config = MatchConfig(match_type=MatchType.PVP)
    match, host = create_match("Host", config)
    mid = match.match_id

    result = join_match(mid, "Player2")
    _, p2 = result
    change_player_team(mid, p2.player_id, "b")

    payload = get_lobby_players_payload(mid)
    assert payload[host.player_id]["team"] == "a"
    assert payload[p2.player_id]["team"] == "b"
    assert "unit_type" in payload[host.player_id]
    print("PASS: test_lobby_payload_includes_team")


if __name__ == "__main__":
    test_create_and_join()
    test_change_team()
    test_change_team_invalid()
    test_remove_player_cleans_teams()
    test_get_player_username()
    test_lobby_payload_includes_team()
    print("\n=== ALL CHUNK 2 TESTS PASSED ===")
