"""
Tests for Phase 7D-2 — Diagonal Door Interaction.

Validates:
- _is_chebyshev_adjacent allows all 8 adjacent tiles
- _is_chebyshev_adjacent rejects non-adjacent tiles (same tile, distance 2+)
- _is_cardinal_adjacent unchanged (still 4-directional only)
- Door INTERACT succeeds from all 8 adjacent tiles (cardinal + diagonal)
- Door INTERACT still fails from distance 2+
- Chest LOOT still requires cardinal adjacency (not affected by door change)
- Chest LOOT fails from diagonal (regression guard)
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.turn_resolver import resolve_turn
from app.core.turn_phases.helpers import _is_cardinal_adjacent, _is_chebyshev_adjacent
from app.core.loot import roll_chest_loot


# ---- Helpers ----

def make_player(pid: str, name: str, x: int, y: int, **kw) -> PlayerState:
    return PlayerState(
        player_id=pid,
        username=name,
        position=Position(x=x, y=y),
        hp=100,
        max_hp=100,
        is_alive=True,
        **kw,
    )


# ---- _is_chebyshev_adjacent unit tests ----

class TestChebyshevAdjacent:
    """Unit tests for the _is_chebyshev_adjacent helper."""

    def test_cardinal_north(self):
        pos = Position(x=5, y=5)
        assert _is_chebyshev_adjacent(pos, 5, 4) is True

    def test_cardinal_south(self):
        pos = Position(x=5, y=5)
        assert _is_chebyshev_adjacent(pos, 5, 6) is True

    def test_cardinal_east(self):
        pos = Position(x=5, y=5)
        assert _is_chebyshev_adjacent(pos, 6, 5) is True

    def test_cardinal_west(self):
        pos = Position(x=5, y=5)
        assert _is_chebyshev_adjacent(pos, 4, 5) is True

    def test_diagonal_ne(self):
        pos = Position(x=5, y=5)
        assert _is_chebyshev_adjacent(pos, 6, 4) is True

    def test_diagonal_nw(self):
        pos = Position(x=5, y=5)
        assert _is_chebyshev_adjacent(pos, 4, 4) is True

    def test_diagonal_se(self):
        pos = Position(x=5, y=5)
        assert _is_chebyshev_adjacent(pos, 6, 6) is True

    def test_diagonal_sw(self):
        pos = Position(x=5, y=5)
        assert _is_chebyshev_adjacent(pos, 4, 6) is True

    def test_same_tile_not_adjacent(self):
        pos = Position(x=5, y=5)
        assert _is_chebyshev_adjacent(pos, 5, 5) is False

    def test_distance_two_not_adjacent(self):
        pos = Position(x=5, y=5)
        assert _is_chebyshev_adjacent(pos, 7, 5) is False

    def test_distance_two_diagonal(self):
        pos = Position(x=5, y=5)
        assert _is_chebyshev_adjacent(pos, 7, 7) is False

    def test_far_away(self):
        pos = Position(x=0, y=0)
        assert _is_chebyshev_adjacent(pos, 10, 10) is False


# ---- _is_cardinal_adjacent unchanged ----

class TestCardinalAdjacentUnchanged:
    """Verify _is_cardinal_adjacent still only allows 4-directional."""

    def test_cardinal_still_works(self):
        pos = Position(x=5, y=5)
        assert _is_cardinal_adjacent(pos, 5, 4) is True
        assert _is_cardinal_adjacent(pos, 5, 6) is True
        assert _is_cardinal_adjacent(pos, 6, 5) is True
        assert _is_cardinal_adjacent(pos, 4, 5) is True

    def test_diagonal_still_rejected(self):
        pos = Position(x=5, y=5)
        assert _is_cardinal_adjacent(pos, 6, 6) is False
        assert _is_cardinal_adjacent(pos, 4, 4) is False
        assert _is_cardinal_adjacent(pos, 6, 4) is False
        assert _is_cardinal_adjacent(pos, 4, 6) is False


# ---- Door INTERACT from all 8 directions ----

class TestDoorInteractAllDirections:
    """Door INTERACT now succeeds from all 8 adjacent tiles."""

    @pytest.mark.parametrize("px,py", [
        (5, 3),  # west (cardinal)
        (7, 3),  # east (cardinal)
        (6, 2),  # north (cardinal)
        (6, 4),  # south (cardinal)
        (5, 2),  # northwest (diagonal)
        (7, 2),  # northeast (diagonal)
        (5, 4),  # southwest (diagonal)
        (7, 4),  # southeast (diagonal)
    ])
    def test_open_door_from_direction(self, px, py):
        """Player can open a door from any of the 8 adjacent tiles."""
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
            f"Door interact failed from ({px},{py})"
        assert door_states["6,3"] == "open"
        assert (6, 3) not in obstacles

    def test_close_door_from_diagonal(self):
        """Player can also close an open door from a diagonal position."""
        players = {"p1": make_player("p1", "Hero", 5, 2)}
        door_states = {"6,3": "open"}
        obstacles = set()

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
        assert (6, 3) in obstacles

    def test_door_interact_fails_distance_two(self):
        """Door INTERACT still fails when player is 2+ tiles away."""
        players = {"p1": make_player("p1", "Hero", 4, 3)}  # 2 tiles west
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
        assert door_states["6,3"] == "closed"

    def test_door_interact_fails_same_tile(self):
        """Door INTERACT fails when player is on the door tile itself."""
        players = {"p1": make_player("p1", "Hero", 6, 3)}
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


# ---- Chest LOOT still cardinal-only ----

class TestChestLootStillCardinal:
    """Chest LOOT interaction preserved as cardinal-only (regression guard)."""

    def test_chest_loot_cardinal_succeeds(self):
        """Chest loot works from cardinal direction."""
        players = {"p1": make_player("p1", "Hero", 5, 3)}
        chest_states = {"6,3": "unopened"}
        ground_items: dict = {}

        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.LOOT,
            target_x=6, target_y=3,
        )]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, set(),
            door_states={},
            chest_states=chest_states,
            ground_items=ground_items,
        )

        loot_results = [r for r in result.actions if r.action_type == ActionType.LOOT]
        assert len(loot_results) == 1
        assert loot_results[0].success is True
        assert chest_states["6,3"] == "opened"

    def test_chest_loot_diagonal_succeeds(self):
        """Chest loot from diagonal position should succeed (Chebyshev adjacency)."""
        players = {"p1": make_player("p1", "Hero", 5, 2)}  # diagonal to (6,3)
        chest_states = {"6,3": "unopened"}
        ground_items: dict = {}

        actions = [PlayerAction(
            player_id="p1",
            action_type=ActionType.LOOT,
            target_x=6, target_y=3,
        )]

        result = resolve_turn(
            "m1", 1, players, actions, 20, 20, set(),
            door_states={},
            chest_states=chest_states,
            ground_items=ground_items,
        )

        loot_results = [r for r in result.actions if r.action_type == ActionType.LOOT]
        assert len(loot_results) == 1
        assert loot_results[0].success is True
        assert chest_states["6,3"] == "opened"  # diagonal is valid (Chebyshev)
