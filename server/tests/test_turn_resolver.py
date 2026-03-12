"""
Tests for turn resolver — action resolution order and correctness.
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.turn_resolver import resolve_turn
from app.core.combat import load_combat_config


def setup_module():
    load_combat_config()


def make_player(pid, username, x, y, hp=100, damage=15, armor=0) -> PlayerState:
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=100,
        attack_damage=damage,
        armor=armor,
    )


class TestMovement:
    def test_valid_move(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.MOVE, target_x=6, target_y=5)]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set())
        assert result.actions[0].success is True
        assert players["p1"].position.x == 6

    def test_move_into_wall(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        obstacles = {(6, 5)}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.MOVE, target_x=6, target_y=5)]
        result = resolve_turn("m1", 1, players, actions, 15, 15, obstacles)
        assert result.actions[0].success is False
        assert players["p1"].position.x == 5  # Didn't move

    def test_move_out_of_bounds(self):
        players = {"p1": make_player("p1", "Alice", 0, 0)}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.MOVE, target_x=-1, target_y=0)]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set())
        assert result.actions[0].success is False


class TestCombat:
    def test_adjacent_attack_deals_damage(self):
        players = {
            "p1": make_player("p1", "Alice", 5, 5, damage=15),
            "p2": make_player("p2", "Bob", 6, 5, hp=100),
        }
        # Put players on opposing teams so are_allies() doesn't block the attack
        players["p1"].team = "a"
        players["p2"].team = "b"
        actions = [PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=6, target_y=5)]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1"], team_b=["p2"])
        assert result.actions[0].success is True
        assert result.actions[0].damage_dealt == 15
        assert players["p2"].hp == 85

    def test_attack_out_of_range_fails(self):
        players = {
            "p1": make_player("p1", "Alice", 5, 5),
            "p2": make_player("p2", "Bob", 8, 5),
        }
        actions = [PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=8, target_y=5)]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set())
        assert result.actions[0].success is False

    def test_lethal_attack_triggers_death(self):
        players = {
            "p1": make_player("p1", "Alice", 5, 5, damage=15),
            "p2": make_player("p2", "Bob", 6, 5, hp=10),
        }
        # Put players on opposing teams so are_allies() doesn't block the attack
        players["p1"].team = "a"
        players["p2"].team = "b"
        actions = [PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=6, target_y=5)]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1"], team_b=["p2"])
        assert result.actions[0].killed is True
        assert "p2" in result.deaths
        assert result.winner == "team_a"  # Team-based victory now


class TestMeleeTargetTracking:
    """Melee attacks should track targets that move but stay in range."""

    def test_melee_hits_target_that_moved_but_still_adjacent(self):
        """Enemy at (6,5) moves to (6,6) — still adjacent to attacker at (5,5)."""
        players = {
            "p1": make_player("p1", "Alice", 5, 5, damage=15),
            "p2": make_player("p2", "Bob", 6, 5, hp=100),
        }
        players["p1"].team = "a"
        players["p2"].team = "b"
        actions = [
            PlayerAction(player_id="p2", action_type=ActionType.MOVE, target_x=6, target_y=6),
            PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=6, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1"], team_b=["p2"])
        # Movement should succeed
        move_results = [r for r in result.actions if r.action_type == ActionType.MOVE]
        assert move_results[0].success is True
        # Melee should still hit because Bob is at (6,6), still adjacent to (5,5)
        attack_results = [r for r in result.actions if r.action_type == ActionType.ATTACK]
        assert attack_results[0].success is True
        assert attack_results[0].damage_dealt == 15
        assert players["p2"].hp == 85

    def test_melee_misses_target_that_moved_out_of_range(self):
        """Enemy at (6,5) moves to (7,5) — no longer adjacent to attacker at (5,5)."""
        players = {
            "p1": make_player("p1", "Alice", 5, 5, damage=15),
            "p2": make_player("p2", "Bob", 6, 5, hp=100),
        }
        players["p1"].team = "a"
        players["p2"].team = "b"
        actions = [
            PlayerAction(player_id="p2", action_type=ActionType.MOVE, target_x=7, target_y=5),
            PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=6, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1"], team_b=["p2"])
        # Movement should succeed
        move_results = [r for r in result.actions if r.action_type == ActionType.MOVE]
        assert move_results[0].success is True
        # Melee should miss — Bob moved to (7,5), 2 tiles away
        attack_results = [r for r in result.actions if r.action_type == ActionType.ATTACK]
        assert attack_results[0].success is False
        assert players["p2"].hp == 100

    def test_melee_hits_target_that_did_not_move(self):
        """Normal case — target stays put, melee lands as usual."""
        players = {
            "p1": make_player("p1", "Alice", 5, 5, damage=15),
            "p2": make_player("p2", "Bob", 6, 5, hp=100),
        }
        players["p1"].team = "a"
        players["p2"].team = "b"
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=6, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1"], team_b=["p2"])
        attack_results = [r for r in result.actions if r.action_type == ActionType.ATTACK]
        assert attack_results[0].success is True
        assert players["p2"].hp == 85

    def test_melee_tracks_diagonal_move_still_adjacent(self):
        """Enemy at (6,5) moves diagonally to (5,6) — still adjacent to (5,5)."""
        players = {
            "p1": make_player("p1", "Alice", 5, 5, damage=15),
            "p2": make_player("p2", "Bob", 6, 5, hp=100),
        }
        players["p1"].team = "a"
        players["p2"].team = "b"
        actions = [
            PlayerAction(player_id="p2", action_type=ActionType.MOVE, target_x=5, target_y=6),
            PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=6, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1"], team_b=["p2"])
        attack_results = [r for r in result.actions if r.action_type == ActionType.ATTACK]
        assert attack_results[0].success is True
        assert players["p2"].hp == 85

    def test_melee_tracks_but_kills_correctly(self):
        """Tracked melee attack should still kill the target."""
        players = {
            "p1": make_player("p1", "Alice", 5, 5, damage=15),
            "p2": make_player("p2", "Bob", 6, 5, hp=10),
        }
        players["p1"].team = "a"
        players["p2"].team = "b"
        actions = [
            PlayerAction(player_id="p2", action_type=ActionType.MOVE, target_x=6, target_y=6),
            PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=6, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1"], team_b=["p2"])
        attack_results = [r for r in result.actions if r.action_type == ActionType.ATTACK]
        assert attack_results[0].success is True
        assert attack_results[0].killed is True
        assert "p2" in result.deaths
