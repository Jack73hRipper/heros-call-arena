"""
Tests for match manager — match lifecycle operations.
"""

from app.core.match_manager import (
    create_match,
    join_match,
    list_matches,
    set_player_ready,
    start_match,
    get_match,
    remove_match,
)
from app.models.match import MatchStatus


class TestMatchLifecycle:
    def setup_method(self):
        """Clean state between tests."""
        # Clear in-memory stores
        from app.core import match_manager
        match_manager._active_matches.clear()
        match_manager._player_states.clear()

    def test_create_match(self):
        match, player = create_match("Alice")
        assert match.status == MatchStatus.WAITING
        assert player.username == "Alice"
        assert match.host_id == player.player_id

    def test_join_match(self):
        match, host = create_match("Alice")
        result = join_match(match.match_id, "Bob")
        assert result is not None
        joined_match, bob = result
        assert len(joined_match.player_ids) == 2
        assert bob.username == "Bob"

    def test_join_full_match_returns_none(self):
        from app.models.match import MatchConfig
        match, _ = create_match("Alice", MatchConfig(max_players=2))
        join_match(match.match_id, "Bob")
        result = join_match(match.match_id, "Charlie")
        assert result is None

    def test_list_matches(self):
        create_match("Alice")
        create_match("Bob")
        matches = list_matches()
        assert len(matches) == 2

    def test_ready_and_start(self):
        match, host = create_match("Alice")
        join_match(match.match_id, "Bob")
        set_player_ready(match.match_id, host.player_id, True)

        from app.core.match_manager import get_match_players
        players = get_match_players(match.match_id)
        bob_id = [pid for pid in players if pid != host.player_id][0]

        all_ready = set_player_ready(match.match_id, bob_id, True)
        assert all_ready is True

        started = start_match(match.match_id)
        assert started is True
        assert get_match(match.match_id).status == MatchStatus.IN_PROGRESS
