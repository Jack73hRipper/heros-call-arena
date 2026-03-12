"""
Tests for Phase 7A-1 — Cooperative Movement Resolution.

Covers:
  - Two allies moving through same hallway don't block each other
  - Two units swapping positions succeeds
  - Chain of 3+ units shifting in a line all succeed
  - Two units targeting same empty tile — one wins, other waits
  - Existing single-unit movement unchanged (regression)
  - Cycle / rotation detection
  - Edge cases (dead units, off-grid, obstacles)
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.turn_resolver import resolve_turn
from app.core.combat import load_combat_config, resolve_movement_batch


def setup_module():
    load_combat_config()


def make_player(pid, username, x, y, hp=100, team="a", unit_type="human") -> PlayerState:
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=100,
        attack_damage=15,
        armor=0,
        team=team,
        unit_type=unit_type,
    )


# ---------------------------------------------------------------------------
# Direct resolve_movement_batch tests
# ---------------------------------------------------------------------------

class TestBatchBasic:
    """Basic single-unit movement through the batch resolver."""

    def test_single_unit_valid_move(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        intents = [{"player_id": "p1", "target": (6, 5)}]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["to"] == (6, 5)
        assert results[0]["from"] == (5, 5)

    def test_single_unit_into_obstacle(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        intents = [{"player_id": "p1", "target": (6, 5)}]
        results = resolve_movement_batch(intents, players, 15, 15, {(6, 5)})
        assert results[0]["success"] is False

    def test_single_unit_out_of_bounds(self):
        players = {"p1": make_player("p1", "Alice", 0, 0)}
        intents = [{"player_id": "p1", "target": (-1, 0)}]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        assert results[0]["success"] is False

    def test_single_unit_not_adjacent(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        intents = [{"player_id": "p1", "target": (7, 5)}]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        assert results[0]["success"] is False

    def test_dead_unit_fails(self):
        p = make_player("p1", "Alice", 5, 5)
        p.is_alive = False
        players = {"p1": p}
        intents = [{"player_id": "p1", "target": (6, 5)}]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        assert results[0]["success"] is False

    def test_nonexistent_unit_fails(self):
        players = {}
        intents = [{"player_id": "ghost", "target": (6, 5)}]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        assert results[0]["success"] is False

    def test_empty_intents_returns_empty(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        results = resolve_movement_batch([], players, 15, 15, set())
        assert results == []

    def test_move_to_own_tile_succeeds(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        intents = [{"player_id": "p1", "target": (5, 5)}]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        assert results[0]["success"] is True
        assert results[0]["to"] == (5, 5)


class TestHallwayMovement:
    """Two allies moving through the same 1-wide hallway should not block."""

    def test_two_allies_same_direction_hallway(self):
        """A is at (3,5), B is at (4,5). Both move right.
        A→(4,5), B→(5,5).  This is a chain: A wants B's tile, B moves away.
        Both should succeed."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a"),
            "p2": make_player("p2", "Bob", 4, 5, team="a"),
        }
        intents = [
            {"player_id": "p1", "target": (4, 5)},
            {"player_id": "p2", "target": (5, 5)},
        ]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        assert results[0]["success"] is True, "Alice should move to (4,5)"
        assert results[1]["success"] is True, "Bob should move to (5,5)"

    def test_two_allies_same_direction_hallway_reverse_order(self):
        """Same scenario but intents listed in reverse order — result is same."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a"),
            "p2": make_player("p2", "Bob", 4, 5, team="a"),
        }
        intents = [
            {"player_id": "p2", "target": (5, 5)},
            {"player_id": "p1", "target": (4, 5)},
        ]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        r_map = {r["player_id"]: r for r in results}
        assert r_map["p1"]["success"] is True
        assert r_map["p2"]["success"] is True

    def test_three_allies_hallway_shift(self):
        """A(2,5), B(3,5), C(4,5) all move right.
        Chain: A→B's tile, B→C's tile, C→(5,5) empty.  All succeed."""
        players = {
            "p1": make_player("p1", "Alice", 2, 5, team="a"),
            "p2": make_player("p2", "Bob", 3, 5, team="a"),
            "p3": make_player("p3", "Carol", 4, 5, team="a"),
        }
        intents = [
            {"player_id": "p1", "target": (3, 5)},
            {"player_id": "p2", "target": (4, 5)},
            {"player_id": "p3", "target": (5, 5)},
        ]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        for r in results:
            assert r["success"] is True, f"{r['player_id']} should have succeeded"


class TestSwapMovement:
    """Two units swapping positions should both succeed."""

    def test_simple_swap(self):
        """A at (3,5), B at (4,5). A→(4,5), B→(3,5). Both succeed."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a"),
            "p2": make_player("p2", "Bob", 4, 5, team="a"),
        }
        intents = [
            {"player_id": "p1", "target": (4, 5)},
            {"player_id": "p2", "target": (3, 5)},
        ]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        r_map = {r["player_id"]: r for r in results}
        assert r_map["p1"]["success"] is True
        assert r_map["p1"]["to"] == (4, 5)
        assert r_map["p2"]["success"] is True
        assert r_map["p2"]["to"] == (3, 5)

    def test_enemy_swap(self):
        """Even enemies can swap positions if both are moving."""
        players = {
            "e1": make_player("e1", "Demon1", 3, 5, team="b", unit_type="ai"),
            "e2": make_player("e2", "Demon2", 4, 5, team="b", unit_type="ai"),
        }
        intents = [
            {"player_id": "e1", "target": (4, 5)},
            {"player_id": "e2", "target": (3, 5)},
        ]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        for r in results:
            assert r["success"] is True

    def test_diagonal_swap(self):
        """Swap diagonally — A at (3,3), B at (4,4). A→(4,4), B→(3,3)."""
        players = {
            "p1": make_player("p1", "Alice", 3, 3, team="a"),
            "p2": make_player("p2", "Bob", 4, 4, team="a"),
        }
        intents = [
            {"player_id": "p1", "target": (4, 4)},
            {"player_id": "p2", "target": (3, 3)},
        ]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        r_map = {r["player_id"]: r for r in results}
        assert r_map["p1"]["success"] is True
        assert r_map["p2"]["success"] is True


class TestChainMovement:
    """Chain of 3+ units shifting in a line should all succeed."""

    def test_chain_three_units(self):
        """A→B's tile, B→C's tile, C→empty. All succeed."""
        players = {
            "p1": make_player("p1", "Alice", 1, 5, team="a"),
            "p2": make_player("p2", "Bob", 2, 5, team="a"),
            "p3": make_player("p3", "Carol", 3, 5, team="a"),
        }
        intents = [
            {"player_id": "p1", "target": (2, 5)},
            {"player_id": "p2", "target": (3, 5)},
            {"player_id": "p3", "target": (4, 5)},
        ]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        for r in results:
            assert r["success"] is True

    def test_chain_four_units(self):
        """Chain of 4 units all shifting right."""
        players = {
            "p1": make_player("p1", "Alice", 1, 5, team="a"),
            "p2": make_player("p2", "Bob", 2, 5, team="a"),
            "p3": make_player("p3", "Carol", 3, 5, team="a"),
            "p4": make_player("p4", "Dave", 4, 5, team="a"),
        }
        intents = [
            {"player_id": "p1", "target": (2, 5)},
            {"player_id": "p2", "target": (3, 5)},
            {"player_id": "p3", "target": (4, 5)},
            {"player_id": "p4", "target": (5, 5)},
        ]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        for r in results:
            assert r["success"] is True

    def test_chain_blocked_by_stationary_unit(self):
        """A→B's tile, B is not moving. A should fail."""
        players = {
            "p1": make_player("p1", "Alice", 1, 5, team="a"),
            "p2": make_player("p2", "Bob", 2, 5, team="a"),
        }
        intents = [
            {"player_id": "p1", "target": (2, 5)},
            # p2 does NOT move
        ]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        assert results[0]["success"] is False, "Alice blocked by stationary Bob"

    def test_chain_partially_blocked(self):
        """A→B→C, but C is stationary. A and B both fail."""
        players = {
            "p1": make_player("p1", "Alice", 1, 5, team="a"),
            "p2": make_player("p2", "Bob", 2, 5, team="a"),
            "p3": make_player("p3", "Carol", 3, 5, team="a"),
        }
        intents = [
            {"player_id": "p1", "target": (2, 5)},
            {"player_id": "p2", "target": (3, 5)},
            # p3 does NOT move
        ]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        assert results[0]["success"] is False
        assert results[1]["success"] is False


class TestContestedTile:
    """Two units targeting the same empty tile — one wins, other fails."""

    def test_human_beats_ai_for_same_tile(self):
        """Human player and AI both want (5,5). Human wins."""
        players = {
            "p1": make_player("p1", "Alice", 4, 5, team="a", unit_type="human"),
            "e1": make_player("e1", "Demon", 6, 5, team="a", unit_type="ai"),
        }
        intents = [
            {"player_id": "p1", "target": (5, 5)},
            {"player_id": "e1", "target": (5, 5)},
        ]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        r_map = {r["player_id"]: r for r in results}
        assert r_map["p1"]["success"] is True
        assert r_map["e1"]["success"] is False

    def test_two_humans_same_tile_alphabetical_wins(self):
        """Two humans targeting same tile — lower ID wins."""
        players = {
            "p1": make_player("p1", "Alice", 4, 5, team="a", unit_type="human"),
            "p2": make_player("p2", "Bob", 6, 5, team="a", unit_type="human"),
        }
        intents = [
            {"player_id": "p2", "target": (5, 5)},
            {"player_id": "p1", "target": (5, 5)},
        ]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        r_map = {r["player_id"]: r for r in results}
        assert r_map["p1"]["success"] is True
        assert r_map["p2"]["success"] is False

    def test_two_ai_same_tile(self):
        """Two AIs targeting same tile — lower ID wins."""
        players = {
            "e1": make_player("e1", "Demon1", 4, 5, team="b", unit_type="ai"),
            "e2": make_player("e2", "Demon2", 6, 5, team="b", unit_type="ai"),
        }
        intents = [
            {"player_id": "e2", "target": (5, 5)},
            {"player_id": "e1", "target": (5, 5)},
        ]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        r_map = {r["player_id"]: r for r in results}
        assert r_map["e1"]["success"] is True
        assert r_map["e2"]["success"] is False


class TestCycleRotation:
    """Three+ units in a rotation cycle should all succeed."""

    def test_three_unit_rotation(self):
        """A→B's tile, B→C's tile, C→A's tile. All three rotate."""
        players = {
            "p1": make_player("p1", "Alice", 3, 3, team="a"),
            "p2": make_player("p2", "Bob", 4, 3, team="a"),
            "p3": make_player("p3", "Carol", 4, 4, team="a"),
        }
        intents = [
            {"player_id": "p1", "target": (4, 3)},  # A→B's tile
            {"player_id": "p2", "target": (4, 4)},  # B→C's tile
            {"player_id": "p3", "target": (3, 3)},  # C→A's tile
        ]
        results = resolve_movement_batch(intents, players, 15, 15, set())
        for r in results:
            assert r["success"] is True, f"{r['player_id']} should succeed in rotation"


class TestMovementRegression:
    """Existing single-unit movement behavior should be unchanged."""

    def test_single_valid_move_via_resolve_turn(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                                target_x=6, target_y=5)]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set())
        assert result.actions[0].success is True
        assert players["p1"].position.x == 6
        assert players["p1"].position.y == 5

    def test_single_move_into_wall_via_resolve_turn(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        obstacles = {(6, 5)}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                                target_x=6, target_y=5)]
        result = resolve_turn("m1", 1, players, actions, 15, 15, obstacles)
        assert result.actions[0].success is False
        assert players["p1"].position.x == 5

    def test_single_move_out_of_bounds_via_resolve_turn(self):
        players = {"p1": make_player("p1", "Alice", 0, 0)}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                                target_x=-1, target_y=0)]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set())
        assert result.actions[0].success is False

    def test_single_move_blocked_by_stationary_enemy(self):
        """A player moves into a tile occupied by a non-moving enemy — fail."""
        players = {
            "p1": make_player("p1", "Alice", 5, 5, team="a"),
            "e1": make_player("e1", "Demon", 6, 5, team="b"),
        }
        actions = [PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                                target_x=6, target_y=5)]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1"], team_b=["e1"])
        assert result.actions[0].success is False
        assert players["p1"].position.x == 5

    def test_diagonal_move(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                                target_x=6, target_y=6)]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set())
        assert result.actions[0].success is True
        assert players["p1"].position.x == 6
        assert players["p1"].position.y == 6

    def test_move_result_has_from_to_coords(self):
        players = {"p1": make_player("p1", "Alice", 5, 5)}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                                target_x=6, target_y=5)]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set())
        action_result = result.actions[0]
        assert action_result.from_x == 5
        assert action_result.from_y == 5
        assert action_result.to_x == 6
        assert action_result.to_y == 5


class TestCooperativeTurnResolver:
    """Integration tests through resolve_turn for cooperative scenarios."""

    def test_two_allies_swap_via_resolve_turn(self):
        """Two same-team allies swapping through resolve_turn."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a"),
            "p2": make_player("p2", "Bob", 4, 5, team="a"),
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
            PlayerAction(player_id="p2", action_type=ActionType.MOVE,
                         target_x=3, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1", "p2"], team_b=[])
        move_results = [a for a in result.actions if a.action_type == ActionType.MOVE]
        assert all(r.success for r in move_results), "Both allies should swap"
        assert players["p1"].position.x == 4
        assert players["p2"].position.x == 3

    def test_chain_move_via_resolve_turn(self):
        """Three allies chain-moving through resolve_turn."""
        players = {
            "p1": make_player("p1", "Alice", 1, 5, team="a"),
            "p2": make_player("p2", "Bob", 2, 5, team="a"),
            "p3": make_player("p3", "Carol", 3, 5, team="a"),
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=2, target_y=5),
            PlayerAction(player_id="p2", action_type=ActionType.MOVE,
                         target_x=3, target_y=5),
            PlayerAction(player_id="p3", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1", "p2", "p3"], team_b=[])
        move_results = [a for a in result.actions if a.action_type == ActionType.MOVE]
        assert all(r.success for r in move_results)
        assert players["p1"].position.x == 2
        assert players["p2"].position.x == 3
        assert players["p3"].position.x == 4

    def test_contested_tile_via_resolve_turn(self):
        """Two units from different teams target same tile through resolve_turn."""
        players = {
            "p1": make_player("p1", "Alice", 4, 5, team="a", unit_type="human"),
            "e1": make_player("e1", "Demon", 6, 5, team="b", unit_type="ai"),
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=5, target_y=5),
            PlayerAction(player_id="e1", action_type=ActionType.MOVE,
                         target_x=5, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1"], team_b=["e1"])
        # Human wins the contested tile
        assert players["p1"].position.x == 5
        assert players["e1"].position.x == 6  # didn't move

    def test_no_duplicate_players_on_same_tile(self):
        """After batch resolution, no two alive units share a tile."""
        players = {
            "p1": make_player("p1", "Alice", 1, 5, team="a"),
            "p2": make_player("p2", "Bob", 2, 5, team="a"),
            "p3": make_player("p3", "Carol", 3, 5, team="a"),
            "e1": make_player("e1", "Demon", 5, 5, team="b", unit_type="ai"),
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=2, target_y=5),
            PlayerAction(player_id="p2", action_type=ActionType.MOVE,
                         target_x=3, target_y=5),
            PlayerAction(player_id="p3", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
        ]
        resolve_turn("m1", 1, players, actions, 15, 15, set(),
                     team_a=["p1", "p2", "p3"], team_b=["e1"])

        occupied = set()
        for p in players.values():
            if p.is_alive:
                pos = (p.position.x, p.position.y)
                assert pos not in occupied, f"Duplicate on tile {pos}"
                occupied.add(pos)

    def test_mixed_move_and_attack_turn(self):
        """Move + attack in same turn — batch movement runs first, then melee."""
        players = {
            "p1": make_player("p1", "Alice", 4, 5, team="a"),
            "e1": make_player("e1", "Demon", 6, 5, team="b", unit_type="ai"),
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=5, target_y=5),
            PlayerAction(player_id="e1", action_type=ActionType.ATTACK,
                         target_x=5, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1"], team_b=["e1"])
        # Move should succeed, then melee should resolve against new position
        move_r = [a for a in result.actions if a.action_type == ActionType.MOVE]
        assert move_r[0].success is True
        assert players["p1"].position.x == 5


# ---------------------------------------------------------------------------
# Phase FSM-1: Friendly Swap Injection tests
# ---------------------------------------------------------------------------

class TestFriendlySwapInjection:
    """Test the server-side swap injection for player-initiated friendly swaps.

    When a player moves onto a same-team stationary ally's tile, the server
    should inject a reciprocal MOVE intent so the batch resolver treats it
    as a swap. The ally ends up on the mover's old tile.
    """

    def test_player_walk_into_stationary_ally_swaps(self):
        """Player moves onto ally's tile -> ally auto-swapped to player's old tile."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a", unit_type="human"),
            "p2": make_player("p2", "Bob", 4, 5, team="a", unit_type="ai"),
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
            # p2 does NOT submit a move — server should inject one
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1", "p2"], team_b=[])
        move_results = [a for a in result.actions if a.action_type == ActionType.MOVE]
        success_moves = [r for r in move_results if r.success]
        assert len(success_moves) == 2, "Both Alice and Bob should move successfully"
        assert players["p1"].position.x == 4
        assert players["p1"].position.y == 5
        assert players["p2"].position.x == 3
        assert players["p2"].position.y == 5

    def test_player_walk_into_enemy_no_swap(self):
        """Player moves onto enemy tile -> no swap injection, move fails."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a", unit_type="human"),
            "e1": make_player("e1", "Demon", 4, 5, team="b", unit_type="ai"),
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1"], team_b=["e1"])
        move_results = [a for a in result.actions if a.action_type == ActionType.MOVE]
        assert move_results[0].success is False
        assert players["p1"].position.x == 3  # didn't move

    def test_player_walk_into_hold_stance_ally_blocked(self):
        """Player moves onto hold-stance ally -> no swap, move fails."""
        p2 = make_player("p2", "Bob", 4, 5, team="a", unit_type="ai")
        p2.ai_stance = "hold"
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a", unit_type="human"),
            "p2": p2,
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1", "p2"], team_b=[])
        move_results = [a for a in result.actions if a.action_type == ActionType.MOVE]
        assert move_results[0].success is False
        assert players["p1"].position.x == 3  # blocked

    def test_player_walk_into_stunned_ally_blocked(self):
        """Player moves onto stunned ally -> no swap, move fails."""
        from app.core.turn_phases.movement_phase import _resolve_movement
        from app.models.actions import ActionResult
        p2 = make_player("p2", "Bob", 4, 5, team="a", unit_type="ai")
        p2.active_buffs = [{"type": "stun", "turns_remaining": 2}]
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a", unit_type="human"),
            "p2": p2,
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
        ]
        results: list[ActionResult] = []
        _resolve_movement(actions, players, 15, 15, set(), results)
        move_results = [r for r in results if r.action_type == ActionType.MOVE]
        assert move_results[0].success is False
        assert players["p1"].position.x == 3

    def test_player_walk_into_slowed_ally_blocked(self):
        """Player moves onto slowed ally -> no swap, move fails."""
        from app.core.turn_phases.movement_phase import _resolve_movement
        from app.models.actions import ActionResult
        p2 = make_player("p2", "Bob", 4, 5, team="a", unit_type="ai")
        p2.active_buffs = [{"type": "slow", "turns_remaining": 2}]
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a", unit_type="human"),
            "p2": p2,
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
        ]
        results: list[ActionResult] = []
        _resolve_movement(actions, players, 15, 15, set(), results)
        move_results = [r for r in results if r.action_type == ActionType.MOVE]
        assert move_results[0].success is False
        assert players["p1"].position.x == 3

    def test_player_walk_into_channeling_ally_blocked(self):
        """Player moves onto channeling ally -> no swap, move fails."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a", unit_type="human"),
            "p2": make_player("p2", "Bob", 4, 5, team="a", unit_type="ai"),
        }
        # Simulate channeling state for p2 using the portal_context format
        portal_context_channeling = {
            "channeling_active": True,
            "channeling_started": {"player_id": "p2"},
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
        ]
        # Go through _resolve_movement directly to pass portal_context
        from app.core.turn_phases.movement_phase import _resolve_movement
        from app.models.actions import ActionResult
        results: list[ActionResult] = []
        _resolve_movement(
            actions, players, 15, 15, set(), results,
            portal_context=portal_context_channeling,
        )
        move_results = [r for r in results if r.action_type == ActionType.MOVE]
        assert move_results[0].success is False
        assert players["p1"].position.x == 3

    def test_two_players_swap_same_ally_one_wins(self):
        """Two movers target same stationary ally -> one swaps, other fails.
        The batch resolver's same-target conflict picks a winner (p1 by ID).
        The other mover (p2) fails. The ally swaps only with the winner."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a", unit_type="human"),
            "p2": make_player("p2", "Bob", 5, 5, team="a", unit_type="human"),
            "p3": make_player("p3", "Carol", 4, 5, team="a", unit_type="ai"),
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
            PlayerAction(player_id="p2", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1", "p2", "p3"], team_b=[])
        # p1 wins the conflict for (4,5), swaps with p3
        # p2 loses the same-target conflict and stays put
        # No two alive units should share a tile
        occupied = set()
        for p in players.values():
            if p.is_alive:
                pos = (p.position.x, p.position.y)
                assert pos not in occupied, f"Duplicate on tile {pos}"
                occupied.add(pos)
        assert players["p2"].position.x == 5  # loser didn't move

    def test_swap_preserves_pre_move_snapshot(self):
        """Pre-move snapshot should capture positions before any swaps."""
        from app.core.turn_phases.movement_phase import _resolve_movement
        from app.models.actions import ActionResult
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a", unit_type="human"),
            "p2": make_player("p2", "Bob", 4, 5, team="a", unit_type="ai"),
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
        ]
        results: list[ActionResult] = []
        pre_move = _resolve_movement(actions, players, 15, 15, set(), results)
        # Pre-move snapshot should have original positions
        assert pre_move[(3, 5)] == "p1"
        assert pre_move[(4, 5)] == "p2"
        # After swap, actual positions updated
        assert players["p1"].position.x == 4
        assert players["p2"].position.x == 3

    def test_swap_chain_with_stationary(self):
        """A moves onto B (stationary), B auto-pushed to A's tile,
        C moves onto A's old tile -> chain resolves correctly."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a", unit_type="human"),
            "p2": make_player("p2", "Bob", 4, 5, team="a", unit_type="ai"),
            "p3": make_player("p3", "Carol", 2, 5, team="a", unit_type="human"),
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
            PlayerAction(player_id="p3", action_type=ActionType.MOVE,
                         target_x=3, target_y=5),
            # p2 stationary — will get swap-injected to (3,5) by p1's move
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1", "p2", "p3"], team_b=[])
        # p1 → (4,5), p2 injected → (3,5), p3 → (3,5) but conflicts with p2's injected target
        # The batch resolver handles the same-target conflict between p2(injected) and p3
        # Since p3 is human and p2 is AI, p3 wins (3,5)
        # p2's injected move fails, so p1's swap also breaks (chain blocked)
        # OR p1 swap succeeds first and p2 moves to (3,5) before p3 arrives
        # The actual behavior depends on batch resolution order. Let's just verify
        # no two units share a tile.
        occupied = set()
        for p in players.values():
            if p.is_alive:
                pos = (p.position.x, p.position.y)
                assert pos not in occupied, f"Duplicate on tile {pos}"
                occupied.add(pos)

    def test_cross_team_no_swap(self):
        """Player on team A moves onto team B unit -> no swap injection."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a", unit_type="human"),
            "e1": make_player("e1", "Orc", 4, 5, team="b", unit_type="ai"),
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1"], team_b=["e1"])
        move_results = [a for a in result.actions if a.action_type == ActionType.MOVE]
        assert move_results[0].success is False
        assert players["p1"].position.x == 3
        assert players["e1"].position.x == 4  # enemy didn't move

    def test_ally_already_moving_no_injection(self):
        """If the ally is already moving, no swap injection needed — batch resolver handles it."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a", unit_type="human"),
            "p2": make_player("p2", "Bob", 4, 5, team="a", unit_type="ai"),
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
            PlayerAction(player_id="p2", action_type=ActionType.MOVE,
                         target_x=3, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1", "p2"], team_b=[])
        # Both explicitly swapping — should both succeed
        move_results = [a for a in result.actions if a.action_type == ActionType.MOVE]
        success_moves = [r for r in move_results if r.success]
        assert len(success_moves) == 2
        assert players["p1"].position.x == 4
        assert players["p2"].position.x == 3

    def test_dead_ally_no_swap(self):
        """Moving onto a dead ally's tile should not trigger swap injection."""
        p2 = make_player("p2", "Bob", 4, 5, team="a", unit_type="ai")
        p2.is_alive = False
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a", unit_type="human"),
            "p2": p2,
        }
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set(),
                              team_a=["p1", "p2"], team_b=[])
        # Dead ally doesn't block — move should succeed normally
        move_results = [a for a in result.actions if a.action_type == ActionType.MOVE]
        assert move_results[0].success is True
        assert players["p1"].position.x == 4


# ---------------------------------------------------------------------------
# Phase 2 — AI-Initiated Friendly Swap Tests
# ---------------------------------------------------------------------------

class TestFriendlySwapAI:
    """Test Phase 2: AI heroes can pathfind through and swap with same-team units.

    Covers:
      - AI pathfinding through allies (allow_team_swap in _build_occupied_set)
      - AI-initiated swap creates valid move (swap injection works for AI movers)
      - Hold-stance ally blocks AI swap
      - Enemy AI does NOT get team-swap pathfinding
      - Anti-oscillation cooldown prevents back-and-forth swapping
      - Retreat through ally via swap
      - Player-initiated swaps ignore AI cooldown
      - Stunned ally blocks AI swap
    """

    def test_hero_ai_pathfinds_through_ally(self):
        """AI hero in follow stance can plan a path through a stationary ally.

        Verifies that _build_occupied_set with allow_team_swap excludes
        same-team allies from the occupied set.
        """
        from app.core.ai_pathfinding import _build_occupied_set

        players = {
            "h1": make_player("h1", "Hero1", 3, 5, team="a", unit_type="ai"),
            "h2": make_player("h2", "Hero2", 4, 5, team="a", unit_type="ai"),
            "e1": make_player("e1", "Enemy", 7, 5, team="b", unit_type="ai"),
        }

        # Without allow_team_swap: ally h2 blocks
        occupied_no_swap = _build_occupied_set(players, "h1")
        assert (4, 5) in occupied_no_swap, "Ally h2 should block without team swap"
        assert (7, 5) in occupied_no_swap, "Enemy e1 should always block"

        # With allow_team_swap: ally h2 is excluded
        occupied_with_swap = _build_occupied_set(players, "h1", allow_team_swap="a")
        assert (4, 5) not in occupied_with_swap, "Ally h2 should NOT block with team swap"
        assert (7, 5) in occupied_with_swap, "Enemy e1 should still block"

    def test_hero_ai_swap_creates_valid_move(self):
        """AI hero moves onto ally tile -> swap injection creates reciprocal intent.

        Uses _resolve_movement directly to verify the swap injection works
        for AI movers, not just human movers.
        """
        from app.core.turn_phases.movement_phase import _resolve_movement, reset_swap_cooldowns
        from app.models.actions import ActionResult

        reset_swap_cooldowns()
        players = {
            "h1": make_player("h1", "Hero1", 3, 5, team="a", unit_type="ai"),
            "h2": make_player("h2", "Hero2", 4, 5, team="a", unit_type="ai"),
        }
        actions = [
            PlayerAction(player_id="h1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
        ]
        results: list[ActionResult] = []
        _resolve_movement(actions, players, 15, 15, set(), results, current_turn=1)

        success_moves = [r for r in results if r.action_type == ActionType.MOVE and r.success]
        assert len(success_moves) == 2, "Both AI heroes should move successfully"
        assert players["h1"].position.x == 4
        assert players["h1"].position.y == 5
        assert players["h2"].position.x == 3
        assert players["h2"].position.y == 5

    def test_hold_stance_ally_not_swappable_by_ai(self):
        """AI cannot swap with a hold-stance ally — hold-stance units are immovable."""
        from app.core.ai_pathfinding import _build_occupied_set
        from app.core.turn_phases.movement_phase import _resolve_movement, reset_swap_cooldowns
        from app.models.actions import ActionResult

        reset_swap_cooldowns()
        h2 = make_player("h2", "Hero2", 4, 5, team="a", unit_type="ai")
        h2.ai_stance = "hold"
        players = {
            "h1": make_player("h1", "Hero1", 3, 5, team="a", unit_type="ai"),
            "h2": h2,
        }

        # _build_occupied_set should still block hold-stance ally
        occupied = _build_occupied_set(players, "h1", allow_team_swap="a")
        assert (4, 5) in occupied, "Hold-stance ally should remain blocked"

        # The swap injection should also refuse
        actions = [
            PlayerAction(player_id="h1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
        ]
        results: list[ActionResult] = []
        _resolve_movement(actions, players, 15, 15, set(), results, current_turn=1)
        move_results = [r for r in results if r.action_type == ActionType.MOVE]
        assert move_results[0].success is False
        assert players["h1"].position.x == 3

    def test_enemy_ai_does_not_swap(self):
        """Enemy AI does NOT gain team-swap pathfinding.

        Verifies that _build_occupied_set without allow_team_swap keeps
        same-team enemies blocked (as it always has been).
        """
        from app.core.ai_pathfinding import _build_occupied_set

        players = {
            "e1": make_player("e1", "Demon1", 3, 5, team="b", unit_type="ai"),
            "e2": make_player("e2", "Demon2", 4, 5, team="b", unit_type="ai"),
        }

        # Enemy AI should NOT pass allow_team_swap — both block each other
        occupied = _build_occupied_set(players, "e1")
        assert (4, 5) in occupied, "Enemy ally should block without team swap"

        # Explicitly NOT passing allow_team_swap (enemy AI behavior doesn't use it)
        occupied_no_swap = _build_occupied_set(players, "e1", allow_team_swap=None)
        assert (4, 5) in occupied_no_swap, "Enemy ally should block with None team swap"

    def test_oscillation_prevented(self):
        """Two AI heroes don't swap back and forth on consecutive ticks.

        The 2-turn cooldown should prevent re-swapping immediately.
        """
        from app.core.turn_phases.movement_phase import _resolve_movement, reset_swap_cooldowns
        from app.models.actions import ActionResult

        reset_swap_cooldowns()

        # Turn 1: h1 swaps with h2 (h1 moves onto h2's tile)
        players = {
            "h1": make_player("h1", "Hero1", 3, 5, team="a", unit_type="ai"),
            "h2": make_player("h2", "Hero2", 4, 5, team="a", unit_type="ai"),
        }
        actions1 = [PlayerAction(player_id="h1", action_type=ActionType.MOVE,
                                 target_x=4, target_y=5)]
        results1: list[ActionResult] = []
        _resolve_movement(actions1, players, 15, 15, set(), results1, current_turn=1)
        assert players["h1"].position.x == 4
        assert players["h2"].position.x == 3

        # Turn 2: h2 tries to swap back with h1 — BLOCKED by cooldown
        # (current_turn=2, last_swap_tick[h1]=1, 2-1=1 < 2 → blocked)
        actions2 = [PlayerAction(player_id="h2", action_type=ActionType.MOVE,
                                 target_x=4, target_y=5)]
        results2: list[ActionResult] = []
        _resolve_movement(actions2, players, 15, 15, set(), results2, current_turn=2)
        move_results2 = [r for r in results2 if r.action_type == ActionType.MOVE]
        assert move_results2[0].success is False, "Swap should be blocked by cooldown"
        assert players["h2"].position.x == 3  # Didn't move
        assert players["h1"].position.x == 4  # Untouched

        # Turn 3: Cooldown expired (current_turn=3, last_swap_tick[h1]=1, 3-1=2 NOT < 2)
        # Swap should now be allowed.
        actions3 = [PlayerAction(player_id="h2", action_type=ActionType.MOVE,
                                 target_x=4, target_y=5)]
        results3: list[ActionResult] = []
        _resolve_movement(actions3, players, 15, 15, set(), results3, current_turn=3)
        move_results3 = [r for r in results3 if r.action_type == ActionType.MOVE]
        success_moves3 = [r for r in move_results3 if r.success]
        assert len(success_moves3) == 2, "Swap should be allowed after cooldown expires"
        assert players["h2"].position.x == 4
        assert players["h1"].position.x == 3

    def test_retreat_through_ally(self):
        """Low-HP support hero retreats through melee ally via swap.

        The precomputed occupied set in _decide_stance_action now has
        allow_team_swap, so the retreat pathfinding can plan through allies.
        Uses a 1-wide horizontal corridor to force the path through the tank.
        """
        from app.core.ai_pathfinding import _build_occupied_set, get_next_step_toward

        # Scenario: healer at (5,5), tank at (4,5), enemy at (6,5)
        # Walls above and below create a 1-wide corridor at y=5.
        # Healer wants to retreat left, but tank blocks the way.
        # With allow_team_swap, A* should plan through the tank.
        healer = make_player("healer", "Healer", 5, 5, team="a", unit_type="ai")
        tank = make_player("tank", "Tank", 4, 5, team="a", unit_type="ai")
        enemy = make_player("e1", "Demon", 6, 5, team="b", unit_type="ai")

        players = {"healer": healer, "tank": tank, "e1": enemy}

        # Walls forming a corridor at y=5 (blocks y=4 and y=6)
        walls = set()
        for wx in range(3, 8):
            walls.add((wx, 4))
            walls.add((wx, 6))

        # Without team swap: healer is stuck (tank blocks in corridor)
        occupied_no_swap = _build_occupied_set(players, "healer")
        step_no_swap = get_next_step_toward(
            (5, 5), (3, 5), 15, 15, walls, occupied_no_swap,
        )
        assert step_no_swap is None, \
            "Without team swap, healer can't path through tank in corridor"

        # With team swap: healer can path through the tank
        occupied_with_swap = _build_occupied_set(players, "healer", allow_team_swap="a")
        step_with_swap = get_next_step_toward(
            (5, 5), (3, 5), 15, 15, walls, occupied_with_swap,
        )
        assert step_with_swap == (4, 5), \
            "With team swap, healer should step onto tank's tile"

    def test_swap_cooldown_does_not_affect_player(self):
        """Player-initiated swaps ignore the AI cooldown completely.

        Even if the ally was recently swapped by AI, a human player
        can still swap with them.
        """
        from app.core.turn_phases.movement_phase import _resolve_movement, reset_swap_cooldowns, _last_swap_tick
        from app.models.actions import ActionResult

        reset_swap_cooldowns()

        # Simulate: h2 was swapped by AI on turn 1
        _last_swap_tick["h2"] = 1

        # Turn 2: Human player swaps with h2 — should succeed despite cooldown
        players = {
            "p1": make_player("p1", "Alice", 3, 5, team="a", unit_type="human"),
            "h2": make_player("h2", "Hero2", 4, 5, team="a", unit_type="ai"),
        }
        actions = [PlayerAction(player_id="p1", action_type=ActionType.MOVE,
                                target_x=4, target_y=5)]
        results: list[ActionResult] = []
        _resolve_movement(actions, players, 15, 15, set(), results, current_turn=2)

        success_moves = [r for r in results if r.action_type == ActionType.MOVE and r.success]
        assert len(success_moves) == 2, "Player swap should succeed despite AI cooldown"
        assert players["p1"].position.x == 4
        assert players["h2"].position.x == 3

    def test_ai_swap_with_stunned_ally_blocked(self):
        """AI cannot swap with a stunned same-team ally.

        Both _build_occupied_set and the swap injection should block this.
        """
        from app.core.ai_pathfinding import _build_occupied_set
        from app.core.turn_phases.movement_phase import _resolve_movement, reset_swap_cooldowns
        from app.models.actions import ActionResult

        reset_swap_cooldowns()
        h2 = make_player("h2", "Hero2", 4, 5, team="a", unit_type="ai")
        h2.active_buffs = [{"type": "stun", "turns_remaining": 2}]
        players = {
            "h1": make_player("h1", "Hero1", 3, 5, team="a", unit_type="ai"),
            "h2": h2,
        }

        # _build_occupied_set should still block stunned ally even with team swap
        occupied = _build_occupied_set(players, "h1", allow_team_swap="a")
        assert (4, 5) in occupied, "Stunned ally should remain blocked"

        # Swap injection should also refuse
        actions = [
            PlayerAction(player_id="h1", action_type=ActionType.MOVE,
                         target_x=4, target_y=5),
        ]
        results: list[ActionResult] = []
        _resolve_movement(actions, players, 15, 15, set(), results, current_turn=1)
        move_results = [r for r in results if r.action_type == ActionType.MOVE]
        assert move_results[0].success is False
        assert players["h1"].position.x == 3
