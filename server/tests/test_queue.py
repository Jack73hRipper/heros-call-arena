"""
Tests for persistent action queue — Section 7 queue model.
Queue up to 10 actions, tick pops first, clear/modify operations.
"""

from app.core.match_manager import (
    create_match,
    start_match,
    queue_action,
    pop_next_actions,
    clear_player_queue,
    remove_last_action,
    get_player_queue,
    get_match_players,
    MAX_QUEUE_SIZE,
    _active_matches,
    _player_states,
    _action_queues,
)
from app.models.actions import PlayerAction, ActionType


def setup_function():
    """Clean state between tests."""
    _active_matches.clear()
    _player_states.clear()
    _action_queues.clear()


def _create_started_match():
    """Helper: create a match with 2 players in IN_PROGRESS state."""
    match, host = create_match("Alice")
    from app.core.match_manager import join_match
    result = join_match(match.match_id, "Bob")
    _, bob = result
    start_match(match.match_id)
    return match.match_id, host.player_id, bob.player_id


class TestQueueAppend:
    def test_queue_single_action(self):
        mid, alice, bob = _create_started_match()
        action = PlayerAction(player_id=alice, action_type=ActionType.MOVE, target_x=2, target_y=1)
        result = queue_action(mid, alice, action)
        assert result is True
        queue = get_player_queue(mid, alice)
        assert len(queue) == 1
        assert queue[0].action_type == ActionType.MOVE

    def test_queue_multiple_actions(self):
        mid, alice, bob = _create_started_match()
        for i in range(5):
            action = PlayerAction(player_id=alice, action_type=ActionType.MOVE, target_x=i, target_y=0)
            result = queue_action(mid, alice, action)
            assert result is True
        queue = get_player_queue(mid, alice)
        assert len(queue) == 5

    def test_queue_max_10_actions(self):
        mid, alice, bob = _create_started_match()
        for i in range(MAX_QUEUE_SIZE):
            action = PlayerAction(player_id=alice, action_type=ActionType.WAIT)
            result = queue_action(mid, alice, action)
            assert result is True

        # 11th action should be rejected
        action = PlayerAction(player_id=alice, action_type=ActionType.WAIT)
        result = queue_action(mid, alice, action)
        assert isinstance(result, str)
        assert "full" in result.lower()

    def test_queue_dead_player_rejected(self):
        mid, alice, bob = _create_started_match()
        players = get_match_players(mid)
        players[alice].is_alive = False

        action = PlayerAction(player_id=alice, action_type=ActionType.WAIT)
        result = queue_action(mid, alice, action)
        assert isinstance(result, str)
        assert "dead" in result.lower()

    def test_queue_mixed_action_types(self):
        mid, alice, bob = _create_started_match()
        queue_action(mid, alice, PlayerAction(player_id=alice, action_type=ActionType.MOVE, target_x=2, target_y=1))
        queue_action(mid, alice, PlayerAction(player_id=alice, action_type=ActionType.MOVE, target_x=3, target_y=1))
        queue_action(mid, alice, PlayerAction(player_id=alice, action_type=ActionType.ATTACK, target_x=4, target_y=1))
        queue_action(mid, alice, PlayerAction(player_id=alice, action_type=ActionType.WAIT))

        queue = get_player_queue(mid, alice)
        assert len(queue) == 4
        assert queue[0].action_type == ActionType.MOVE
        assert queue[1].action_type == ActionType.MOVE
        assert queue[2].action_type == ActionType.ATTACK
        assert queue[3].action_type == ActionType.WAIT


class TestQueuePopFirst:
    def test_pop_returns_first_action(self):
        mid, alice, bob = _create_started_match()
        queue_action(mid, alice, PlayerAction(player_id=alice, action_type=ActionType.MOVE, target_x=2, target_y=1))
        queue_action(mid, alice, PlayerAction(player_id=alice, action_type=ActionType.ATTACK, target_x=3, target_y=1))

        popped = pop_next_actions(mid)
        assert alice in popped
        assert popped[alice].action_type == ActionType.MOVE

        # Second action remains in queue
        queue = get_player_queue(mid, alice)
        assert len(queue) == 1
        assert queue[0].action_type == ActionType.ATTACK

    def test_pop_from_multiple_players(self):
        mid, alice, bob = _create_started_match()
        queue_action(mid, alice, PlayerAction(player_id=alice, action_type=ActionType.MOVE, target_x=2, target_y=1))
        queue_action(mid, bob, PlayerAction(player_id=bob, action_type=ActionType.ATTACK, target_x=1, target_y=1))

        popped = pop_next_actions(mid)
        assert alice in popped
        assert bob in popped
        assert popped[alice].action_type == ActionType.MOVE
        assert popped[bob].action_type == ActionType.ATTACK

    def test_pop_empty_queue_returns_nothing(self):
        mid, alice, bob = _create_started_match()
        popped = pop_next_actions(mid)
        assert alice not in popped
        assert bob not in popped

    def test_pop_exhausts_queue_over_multiple_ticks(self):
        mid, alice, bob = _create_started_match()
        for i in range(3):
            queue_action(mid, alice, PlayerAction(
                player_id=alice, action_type=ActionType.MOVE, target_x=i, target_y=0))

        # Tick 1 — pops first
        popped = pop_next_actions(mid)
        assert popped[alice].target_x == 0
        assert len(get_player_queue(mid, alice)) == 2

        # Tick 2 — pops second
        popped = pop_next_actions(mid)
        assert popped[alice].target_x == 1
        assert len(get_player_queue(mid, alice)) == 1

        # Tick 3 — pops third (last)
        popped = pop_next_actions(mid)
        assert popped[alice].target_x == 2
        assert len(get_player_queue(mid, alice)) == 0

        # Tick 4 — empty
        popped = pop_next_actions(mid)
        assert alice not in popped


class TestQueueManagement:
    def test_clear_queue(self):
        mid, alice, bob = _create_started_match()
        for i in range(5):
            queue_action(mid, alice, PlayerAction(player_id=alice, action_type=ActionType.WAIT))

        count = clear_player_queue(mid, alice)
        assert count == 5
        assert len(get_player_queue(mid, alice)) == 0

    def test_clear_empty_queue(self):
        mid, alice, bob = _create_started_match()
        count = clear_player_queue(mid, alice)
        assert count == 0

    def test_remove_last_action(self):
        mid, alice, bob = _create_started_match()
        queue_action(mid, alice, PlayerAction(player_id=alice, action_type=ActionType.MOVE, target_x=2, target_y=1))
        queue_action(mid, alice, PlayerAction(player_id=alice, action_type=ActionType.ATTACK, target_x=3, target_y=1))

        removed = remove_last_action(mid, alice)
        assert removed is True
        queue = get_player_queue(mid, alice)
        assert len(queue) == 1
        assert queue[0].action_type == ActionType.MOVE  # Attack was removed

    def test_remove_last_from_empty_queue(self):
        mid, alice, bob = _create_started_match()
        removed = remove_last_action(mid, alice)
        assert removed is False

    def test_pop_then_add_more(self):
        """Simulate: player queues 3, tick pops 1, player adds 2 more."""
        mid, alice, bob = _create_started_match()
        for i in range(3):
            queue_action(mid, alice, PlayerAction(
                player_id=alice, action_type=ActionType.MOVE, target_x=i, target_y=0))

        # Tick pops first
        pop_next_actions(mid)
        assert len(get_player_queue(mid, alice)) == 2

        # Player adds 2 more
        queue_action(mid, alice, PlayerAction(
            player_id=alice, action_type=ActionType.ATTACK, target_x=5, target_y=5))
        queue_action(mid, alice, PlayerAction(
            player_id=alice, action_type=ActionType.WAIT))
        assert len(get_player_queue(mid, alice)) == 4
