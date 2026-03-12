"""
Tests for Phase 4B-2 — Door Mechanics, FOV & Movement Integration.

Validates:
- INTERACT action opens a closed door via turn_resolver
- INTERACT fails when not cardinally adjacent
- INTERACT fails when target is not a closed door
- INTERACT ignored in arena mode (no door_states)
- Closed doors block movement (in obstacles set)
- Open doors allow movement (removed from obstacles)
- Closed doors block FOV / line of sight
- Open doors allow FOV / line of sight
- FOV recalculates correctly after a door opens mid-turn
- get_obstacles_with_door_states() honours live door states
- Door changes appear in TurnResult
- Ranged attacks blocked by closed doors, allowed through open doors
- Multiple doors can be opened in the same turn
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType, TurnResult
from app.core.turn_resolver import resolve_turn
from app.core.turn_phases.helpers import _is_cardinal_adjacent, _is_chebyshev_adjacent
from app.core.combat import load_combat_config, is_valid_move
from app.core.fov import compute_fov, has_line_of_sight
from app.core.map_loader import (
    get_obstacles,
    get_obstacles_with_door_states,
    get_doors,
    is_dungeon_map,
)


# ---- Setup ----

DUNGEON_MAP = "dungeon_test"


def setup_module():
    load_combat_config()


def _clean_map_cache():
    from app.core import map_loader
    map_loader._loaded_maps.clear()


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


# ======================================================================
# Cardinal adjacency helper
# ======================================================================


class TestCardinalAdjacency:
    def test_adjacent_north(self):
        pos = Position(x=5, y=5)
        assert _is_cardinal_adjacent(pos, 5, 4) is True

    def test_adjacent_south(self):
        pos = Position(x=5, y=5)
        assert _is_cardinal_adjacent(pos, 5, 6) is True

    def test_adjacent_east(self):
        pos = Position(x=5, y=5)
        assert _is_cardinal_adjacent(pos, 6, 5) is True

    def test_adjacent_west(self):
        pos = Position(x=5, y=5)
        assert _is_cardinal_adjacent(pos, 4, 5) is True

    def test_diagonal_not_cardinal(self):
        pos = Position(x=5, y=5)
        assert _is_cardinal_adjacent(pos, 6, 6) is False
        assert _is_cardinal_adjacent(pos, 4, 4) is False
        assert _is_cardinal_adjacent(pos, 6, 4) is False
        assert _is_cardinal_adjacent(pos, 4, 6) is False

    def test_same_tile_not_adjacent(self):
        pos = Position(x=5, y=5)
        assert _is_cardinal_adjacent(pos, 5, 5) is False

    def test_two_away_not_adjacent(self):
        pos = Position(x=5, y=5)
        assert _is_cardinal_adjacent(pos, 7, 5) is False
        assert _is_cardinal_adjacent(pos, 5, 7) is False


# ======================================================================
# INTERACT action — turn resolver
# ======================================================================


class TestInteractOpensDoor:
    """INTERACT action opens a closed door and updates state."""

    def test_open_closed_door(self):
        """Player cardinally adjacent to a closed door can open it."""
        # Door at (6,3); player at (5,3) — adjacent east
        players = {"p1": make_player("p1", "Hero", 5, 3)}
        door_states = {"6,3": "closed", "9,3": "closed"}
        obstacles = {(6, 3), (9, 3), (0, 0)}  # walls + doors

        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.INTERACT,
            target_x=6, target_y=3,
        )]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            door_states=door_states,
        )

        # Action succeeded
        interact_results = [a for a in result.actions if a.action_type == ActionType.INTERACT]
        assert len(interact_results) == 1
        assert interact_results[0].success is True

        # Door state mutated
        assert door_states["6,3"] == "open"
        assert door_states["9,3"] == "closed"  # untouched

        # Obstacle removed
        assert (6, 3) not in obstacles
        assert (9, 3) in obstacles  # untouched

        # door_changes in result
        assert len(result.door_changes) == 1
        assert result.door_changes[0] == {"x": 6, "y": 3, "state": "open"}

    def test_open_door_from_all_cardinal_directions(self):
        """Player can open a door from any cardinal direction."""
        for px, py in [(5, 3), (7, 3), (6, 2), (6, 4)]:
            players = {"p1": make_player("p1", "Hero", px, py)}
            door_states = {"6,3": "closed"}
            obstacles = {(6, 3)}

            actions = [PlayerAction(
                player_id="p1",
                action_type=ActionType.INTERACT,
                target_x=6, target_y=3,
            )]

            result = resolve_turn(
                "m1", 1, players, actions, 20, 20, obstacles,
                door_states=door_states,
            )

            assert result.actions[0].success is True, \
                f"Failed from ({px},{py})"
            assert door_states["6,3"] == "open"


class TestInteractFails:
    """INTERACT action fails under invalid conditions."""

    def test_diagonal_adjacency_valid_for_door_interaction(self):
        """Diagonal adjacency IS valid for door interaction (Chebyshev distance 1)."""
        players = {"p1": make_player("p1", "Hero", 5, 2)}  # diagonal to (6,3)
        door_states = {"6,3": "closed"}
        obstacles = {(6, 3)}

        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.INTERACT,
            target_x=6, target_y=3,
        )]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            door_states=door_states,
        )

        assert result.actions[0].success is True
        assert door_states["6,3"] == "open"  # door opened
        assert (6, 3) not in obstacles  # obstacle removed

    def test_fail_too_far(self):
        """INTERACT fails when more than 1 tile away."""
        players = {"p1": make_player("p1", "Hero", 4, 3)}
        door_states = {"6,3": "closed"}
        obstacles = {(6, 3)}

        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.INTERACT,
            target_x=6, target_y=3,
        )]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            door_states=door_states,
        )

        assert result.actions[0].success is False

    def test_toggle_close_open_door(self):
        """Interacting with an open door closes it (toggle behavior)."""
        players = {"p1": make_player("p1", "Hero", 5, 3)}
        door_states = {"6,3": "open"}
        obstacles = set()  # open door already removed

        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.INTERACT,
            target_x=6, target_y=3,
        )]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            door_states=door_states,
        )

        assert result.actions[0].success is True
        assert door_states["6,3"] == "closed"
        assert (6, 3) in obstacles  # Re-added to obstacles
        assert len(result.door_changes) == 1
        assert result.door_changes[0]["state"] == "closed"

    def test_fail_not_a_door(self):
        """INTERACT on a non-door tile fails."""
        players = {"p1": make_player("p1", "Hero", 5, 3)}
        door_states = {"6,3": "closed"}  # door exists at 6,3, NOT at 5,4
        obstacles = {(6, 3)}

        # Interact with (5,4) — valid floor tile, not a door
        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.INTERACT,
            target_x=5, target_y=4,
        )]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            door_states=door_states,
        )

        assert result.actions[0].success is False

    def test_fail_dead_player(self):
        """Dead player cannot interact."""
        p = make_player("p1", "Hero", 5, 3)
        p.hp = 0
        p.is_alive = False
        players = {"p1": p}
        door_states = {"6,3": "closed"}
        obstacles = {(6, 3)}

        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.INTERACT,
            target_x=6, target_y=3,
        )]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            door_states=door_states,
        )

        # Dead player action is skipped entirely
        interact_results = [a for a in result.actions if a.action_type == ActionType.INTERACT]
        assert len(interact_results) == 0
        assert door_states["6,3"] == "closed"

    def test_no_interact_in_arena_mode(self):
        """When door_states is None (arena), interact actions are ignored."""
        players = {"p1": make_player("p1", "Hero", 5, 3)}
        obstacles = {(6, 3)}

        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.INTERACT,
            target_x=6, target_y=3,
        )]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            door_states=None,
        )

        # No interact results processed
        interact_results = [a for a in result.actions if a.action_type == ActionType.INTERACT]
        assert len(interact_results) == 0
        assert len(result.door_changes) == 0


class TestMultipleDoors:
    """Multiple doors can be opened in a single turn."""

    def test_two_players_open_two_doors(self):
        """Two different players open two different doors simultaneously."""
        players = {
            "p1": make_player("p1", "Alice", 5, 3),
            "p2": make_player("p2", "Bob", 10, 3),
        }
        door_states = {"6,3": "closed", "9,3": "closed"}
        obstacles = {(6, 3), (9, 3)}

        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.INTERACT,
                         target_x=6, target_y=3),
            PlayerAction(player_id="p2", action_type=ActionType.INTERACT,
                         target_x=9, target_y=3),
        ]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            door_states=door_states,
        )

        interact_ok = [a for a in result.actions
                       if a.action_type == ActionType.INTERACT and a.success]
        assert len(interact_ok) == 2
        assert door_states["6,3"] == "open"
        assert door_states["9,3"] == "open"
        assert (6, 3) not in obstacles
        assert (9, 3) not in obstacles
        assert len(result.door_changes) == 2


# ======================================================================
# Movement and door obstacles
# ======================================================================


class TestDoorBlocksMovement:
    """Closed doors in the obstacle set prevent movement."""

    def test_closed_door_blocks_move(self):
        """Player cannot walk onto a closed door tile."""
        players = {"p1": make_player("p1", "Hero", 5, 3)}
        door_states = {"6,3": "closed"}
        obstacles = {(6, 3)}

        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.MOVE,
            target_x=6, target_y=3,
        )]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            door_states=door_states,
        )

        assert result.actions[0].success is False
        assert players["p1"].position.x == 5  # didn't move

    def test_open_door_allows_move(self):
        """Player can walk through an open door tile."""
        players = {"p1": make_player("p1", "Hero", 5, 3)}
        door_states = {"6,3": "open"}
        obstacles = set()  # open door not in obstacles

        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.MOVE,
            target_x=6, target_y=3,
        )]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            door_states=door_states,
        )

        assert result.actions[0].success is True
        assert players["p1"].position.x == 6

    def test_move_after_door_opens_same_turn(self):
        """After door opens in the interact phase, subsequent actions
        (in later phases) see the updated obstacle set. In the same
        turn, movement is resolved BEFORE interact, so movement onto
        a just-opened door in the same turn would fail. But a RANGED
        attack through it should work."""
        # Door at (6,3). Player 1 adjacent to open it.
        # Player 2 wants to move onto (6,3) — movement resolves FIRST,
        # so the door is still closed during move phase.
        players = {
            "p1": make_player("p1", "Alice", 5, 3),
            "p2": make_player("p2", "Bob", 6, 2),
        }
        door_states = {"6,3": "closed"}
        obstacles = {(6, 3)}

        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.INTERACT,
                         target_x=6, target_y=3),
            PlayerAction(player_id="p2", action_type=ActionType.MOVE,
                         target_x=6, target_y=3),
        ]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            door_states=door_states,
        )

        move_result = [a for a in result.actions if a.action_type == ActionType.MOVE][0]
        # Movement resolved before interact → move fails
        assert move_result.success is False
        # But the door DID open
        assert door_states["6,3"] == "open"


class TestIsValidMoveWithDoors:
    """Direct tests of is_valid_move involving door obstacles."""

    def test_blocked_by_closed_door(self):
        obstacles = {(6, 3)}
        pos = Position(x=5, y=3)
        assert is_valid_move(pos, 6, 3, 20, 20, obstacles, set()) is False

    def test_pass_through_open_door(self):
        obstacles = set()  # door removed
        pos = Position(x=5, y=3)
        assert is_valid_move(pos, 6, 3, 20, 20, obstacles, set()) is True


# ======================================================================
# get_obstacles_with_door_states
# ======================================================================


class TestObstaclesWithDoorStates:
    def setup_method(self):
        _clean_map_cache()

    def test_no_door_states_returns_base_obstacles(self):
        """When door_states is None, returns same as get_obstacles."""
        base = get_obstacles(DUNGEON_MAP)
        result = get_obstacles_with_door_states(DUNGEON_MAP, None)
        assert result == base

    def test_all_closed_matches_base(self):
        """When all doors are closed, result matches base obstacles."""
        doors = get_doors(DUNGEON_MAP)
        door_states = {f"{d['x']},{d['y']}": "closed" for d in doors}
        base = get_obstacles(DUNGEON_MAP)
        result = get_obstacles_with_door_states(DUNGEON_MAP, door_states)
        assert result == base

    def test_open_door_removed(self):
        """An open door is removed from the obstacle set."""
        doors = get_doors(DUNGEON_MAP)
        door_states = {f"{d['x']},{d['y']}": "closed" for d in doors}
        # Open one door
        door_states["6,3"] = "open"

        result = get_obstacles_with_door_states(DUNGEON_MAP, door_states)
        assert (6, 3) not in result

        # Other doors still present
        assert (9, 3) in result

    def test_multiple_open_doors_removed(self):
        """Multiple open doors all removed from obstacles."""
        doors = get_doors(DUNGEON_MAP)
        door_states = {f"{d['x']},{d['y']}": "closed" for d in doors}
        door_states["6,3"] = "open"
        door_states["3,6"] = "open"
        door_states["13,15"] = "open"

        result = get_obstacles_with_door_states(DUNGEON_MAP, door_states)
        assert (6, 3) not in result
        assert (3, 6) not in result
        assert (13, 15) not in result
        # Remaining closed doors still obstacles
        assert (9, 3) in result
        assert (12, 6) in result

    def test_walls_never_removed(self):
        """Walls remain in obstacles even when all doors are open."""
        doors = get_doors(DUNGEON_MAP)
        door_states = {f"{d['x']},{d['y']}": "open" for d in doors}

        result = get_obstacles_with_door_states(DUNGEON_MAP, door_states)
        # (0,0) is a wall in dungeon_test
        assert (0, 0) in result


# ======================================================================
# FOV and Line of Sight with doors
# ======================================================================


class TestFOVWithDoors:
    """Closed doors block FOV; open doors allow vision through."""

    def _make_corridor_scenario(self, door_in_obstacles: bool):
        """Build a simple corridor: player at (3,3), door at (5,3).

        Corridor from (0,3) to (10,3) with walls above/below.
        A door at (5,3) optionally blocks sight.
        """
        obstacles = set()
        # Walls above and below corridor (y=2 and y=4 from x=0..10)
        for x in range(11):
            obstacles.add((x, 2))
            obstacles.add((x, 4))
        if door_in_obstacles:
            obstacles.add((5, 3))
        return obstacles

    def test_closed_door_blocks_fov(self):
        """FOV cannot see past a closed door."""
        obstacles = self._make_corridor_scenario(door_in_obstacles=True)

        visible = compute_fov(3, 3, 8, 20, 20, obstacles)
        # Tile before door is visible
        assert (4, 3) in visible
        # Door tile itself is visible (shadowcasting marks blocking tiles visible)
        assert (5, 3) in visible
        # Tile behind door is NOT visible
        assert (6, 3) not in visible
        assert (7, 3) not in visible

    def test_open_door_allows_fov(self):
        """FOV can see through an open door."""
        obstacles = self._make_corridor_scenario(door_in_obstacles=False)

        visible = compute_fov(3, 3, 8, 20, 20, obstacles)
        # Can see through where door was
        assert (5, 3) in visible
        assert (6, 3) in visible
        assert (7, 3) in visible

    def test_closed_door_blocks_los(self):
        """LOS check fails through a closed door."""
        obstacles = {(5, 3)}  # door
        assert has_line_of_sight(3, 3, 7, 3, obstacles) is False

    def test_open_door_allows_los(self):
        """LOS check succeeds when door is removed."""
        obstacles = set()
        assert has_line_of_sight(3, 3, 7, 3, obstacles) is True

    def test_fov_recalculates_after_door_opens(self):
        """Simulates a door being opened and FOV recomputed.

        This mimics the real game flow: obstacles are mutated when a
        door opens, so any subsequent FOV computation (next tick) will
        see through the doorway.
        """
        obstacles = self._make_corridor_scenario(door_in_obstacles=True)

        # Before opening — can't see past door
        vis_before = compute_fov(3, 3, 8, 20, 20, obstacles)
        assert (6, 3) not in vis_before

        # Open the door — remove from obstacles (same mutation as turn_resolver)
        obstacles.discard((5, 3))

        # After opening — can see past where door was
        vis_after = compute_fov(3, 3, 8, 20, 20, obstacles)
        assert (5, 3) in vis_after
        assert (6, 3) in vis_after
        assert (7, 3) in vis_after


class TestFOVWithDungeonMap:
    """FOV tests using the actual dungeon_test map data."""

    def setup_method(self):
        _clean_map_cache()

    def test_fov_blocked_by_closed_door_on_map(self):
        """Using actual dungeon_test obstacles, closed door at (6,3) blocks FOV."""
        obstacles = get_obstacles(DUNGEON_MAP)
        # Player at (5,3) — just west of door at (6,3)
        visible = compute_fov(5, 3, 8, 20, 20, obstacles)
        # Should see the door tile but NOT beyond it
        assert (6, 3) in visible
        assert (7, 3) not in visible

    def test_fov_through_open_door_on_map(self):
        """When door at (6,3) is open, FOV extends through it."""
        doors = get_doors(DUNGEON_MAP)
        door_states = {f"{d['x']},{d['y']}": "closed" for d in doors}
        door_states["6,3"] = "open"

        obstacles = get_obstacles_with_door_states(DUNGEON_MAP, door_states)
        visible = compute_fov(5, 3, 8, 20, 20, obstacles)
        # Now can see through the doorway
        assert (6, 3) in visible
        assert (7, 3) in visible


# ======================================================================
# Ranged attacks and doors
# ======================================================================


class TestRangedAttacksAndDoors:
    """Ranged attacks respect door LOS blocking."""

    def test_ranged_blocked_by_closed_door(self):
        """Ranged attack through a closed door fails (LOS blocked)."""
        # Player at (3,3), target at (7,3), closed door at (5,3)
        players = {
            "p1": make_player("p1", "Alice", 3, 3, damage=15),
            "p2": make_player("p2", "Bob", 7, 3, hp=100),
        }
        players["p1"].team = "a"
        players["p2"].team = "b"
        players["p1"].ranged_range = 10
        players["p1"].ranged_damage = 10
        # Ensure no ranged cooldown
        players["p1"].cooldowns.pop("ranged_attack", None)

        obstacles = {(5, 3)}  # closed door
        door_states = {"5,3": "closed"}

        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.RANGED_ATTACK,
            target_x=7, target_y=3,
        )]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            team_a=["p1"], team_b=["p2"],
            door_states=door_states,
        )

        ranged_results = [a for a in result.actions
                          if a.action_type == ActionType.RANGED_ATTACK]
        assert len(ranged_results) == 1
        assert ranged_results[0].success is False

    def test_ranged_through_open_door(self):
        """Ranged attack through an open door succeeds."""
        players = {
            "p1": make_player("p1", "Alice", 3, 3, damage=15),
            "p2": make_player("p2", "Bob", 7, 3, hp=100),
        }
        players["p1"].team = "a"
        players["p2"].team = "b"
        players["p1"].ranged_range = 10
        players["p1"].ranged_damage = 10
        # Ensure no ranged cooldown
        players["p1"].cooldowns.pop("ranged_attack", None)

        obstacles = set()  # door is open, removed from obstacles
        door_states = {"5,3": "open"}

        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.RANGED_ATTACK,
            target_x=7, target_y=3,
        )]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            team_a=["p1"], team_b=["p2"],
            door_states=door_states,
        )

        ranged_results = [a for a in result.actions
                          if a.action_type == ActionType.RANGED_ATTACK]
        assert len(ranged_results) == 1
        assert ranged_results[0].success is True


# ======================================================================
# TurnResult door_changes field
# ======================================================================


class TestTurnResultDoorChanges:
    """Verify door_changes field in TurnResult."""

    def test_door_changes_empty_when_no_interact(self):
        """No door changes when no interact actions."""
        players = {"p1": make_player("p1", "Hero", 5, 5)}
        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.MOVE,
            target_x=6, target_y=5,
        )]

        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        assert result.door_changes == []

    def test_door_changes_empty_in_arena(self):
        """No door changes in arena mode (door_states=None)."""
        players = {"p1": make_player("p1", "Hero", 5, 5)}
        actions = []
        result = resolve_turn("m1", 1, players, actions, 20, 20, set(),
                              door_states=None)
        assert result.door_changes == []

    def test_door_changes_populated_on_open(self):
        """door_changes contains entry when a door is opened."""
        players = {"p1": make_player("p1", "Hero", 5, 3)}
        door_states = {"6,3": "closed"}
        obstacles = {(6, 3)}

        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.INTERACT,
            target_x=6, target_y=3,
        )]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            door_states=door_states,
        )

        assert len(result.door_changes) == 1
        change = result.door_changes[0]
        assert change["x"] == 6
        assert change["y"] == 3
        assert change["state"] == "open"

    def test_failed_interact_no_door_change(self):
        """Failed INTERACT does not produce door_changes."""
        players = {"p1": make_player("p1", "Hero", 4, 3)}  # too far
        door_states = {"6,3": "closed"}
        obstacles = {(6, 3)}

        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.INTERACT,
            target_x=6, target_y=3,
        )]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            door_states=door_states,
        )

        assert len(result.door_changes) == 0


# ======================================================================
# Integration: Interact + subsequent phases
# ======================================================================


class TestInteractPhaseTiming:
    """Verify that door opens between movement and ranged phases,
    so ranged attacks in the same turn can fire through a just-opened door."""

    def test_ranged_after_interact_same_turn(self):
        """Player A opens door, Player B fires ranged through it — same turn.

        Resolution order: movement → interact → ranged.
        So the door opens BEFORE the ranged shot resolves.
        """
        # Door at (5,3). Opener at (4,3). Shooter at (2,3). Target at (8,3).
        players = {
            "opener": make_player("opener", "Alice", 4, 3),
            "shooter": make_player("shooter", "Bob", 2, 3, damage=15),
            "target": make_player("target", "Eve", 8, 3, hp=100),
        }
        players["shooter"].team = "a"
        players["target"].team = "b"
        players["opener"].team = "a"
        players["shooter"].ranged_range = 10
        players["shooter"].ranged_damage = 10
        # Ensure no ranged cooldown
        players["shooter"].cooldowns.pop("ranged_attack", None)

        door_states = {"5,3": "closed"}
        obstacles = {(5, 3)}

        actions = [
            PlayerAction(player_id="opener", action_type=ActionType.INTERACT,
                         target_x=5, target_y=3),
            PlayerAction(player_id="shooter", action_type=ActionType.RANGED_ATTACK,
                         target_x=8, target_y=3),
        ]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, obstacles,
            team_a=["opener", "shooter"], team_b=["target"],
            door_states=door_states,
        )

        # Door opened
        assert door_states["5,3"] == "open"
        assert (5, 3) not in obstacles

        # Ranged attack should succeed because door opened before ranged phase
        ranged_results = [a for a in result.actions
                          if a.action_type == ActionType.RANGED_ATTACK]
        assert len(ranged_results) == 1
        assert ranged_results[0].success is True
