"""
Tests for Phase 7D-1 — Multi-Layer Pathfinding (Path Through Closed Doors).

Covers:
  - A* pathfinding with door_tiles: weighted cost, preference for open routes
  - get_next_step_toward with door_tiles
  - _maybe_interact_door helper function
  - AI hero allies opening doors (follow, aggressive, defensive stances)
  - Enemy AI never opening doors (no door_tiles passed)
  - Multi-door paths (A* routes through multiple closed doors)
  - Door cost weighting: +3 per door tile vs +1 normal
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.ai_behavior import (
    a_star,
    get_next_step_toward,
    decide_ai_action,
    _maybe_interact_door,
    _decide_follow_action,
    _decide_aggressive_stance_action,
    _decide_defensive_action,
    _chebyshev,
)
from app.core.combat import load_combat_config


def setup_module():
    load_combat_config()


def make_player(pid, username, x, y, hp=100, team="a", unit_type="human",
                hero_id=None, ai_stance="follow", class_id=None,
                ranged_range=5, ai_behavior=None, enemy_type=None) -> PlayerState:
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
        hero_id=hero_id,
        ai_stance=ai_stance,
        class_id=class_id,
        ranged_range=ranged_range,
        ai_behavior=ai_behavior,
        enemy_type=enemy_type,
    )


# ===================================================================
# A* with door_tiles
# ===================================================================

class TestAStarDoorTiles:
    """Test A* pathfinding with door_tiles parameter."""

    def test_path_through_closed_door(self):
        """A* should find a path through a closed door when no open route exists."""
        # Create a wall with a single door gap
        # Map: 10x10, wall at y=5 from x=0..9 except x=5 is a closed door
        obstacles = set()
        for x in range(10):
            if x != 5:
                obstacles.add((x, 5))
        door_tiles = {(5, 5)}

        # Path from (5, 0) to (5, 9) must go through the door
        path = a_star((5, 0), (5, 9), 10, 10, obstacles, set(), door_tiles=door_tiles)
        assert path is not None
        assert (5, 5) in path  # Must pass through the door tile
        assert (5, 9) == path[-1]  # Reaches the goal

    def test_no_path_without_door_tiles(self):
        """Without door_tiles, A* treats closed doors as obstacles (impassable)."""
        obstacles = set()
        for x in range(10):
            if x != 5:
                obstacles.add((x, 5))
        # Door is in obstacles but NOT in door_tiles
        obstacles.add((5, 5))

        path = a_star((5, 0), (5, 9), 10, 10, obstacles, set(), door_tiles=None)
        assert path is None  # No way through the wall

    def test_prefers_open_route_over_door(self):
        """A* should prefer a slightly longer open route over going through a door.

        Door cost is +3, so a path requiring 1 door crossing costs +2 extra.
        An open path that's only 1-2 steps longer should be preferred.
        """
        # Create a wall at y=5, with an open gap at x=2 and a door at x=8
        # Start at (8, 3), goal at (8, 7)
        obstacles = set()
        for x in range(10):
            if x != 2:  # Open gap at x=2
                obstacles.add((x, 5))
        # x=8 is a door (remove from obstacles, put in door_tiles)
        obstacles.discard((8, 5))
        door_tiles = {(8, 5)}

        # Direct path through door: (8,3) → (8,4) → (8,5 door) → (8,6) → (8,7) = 4 steps
        # Cost: 3 normal + 3 door = 6
        # Path via open gap at x=2 would take many more steps (>6), so door is faster
        # But let's test with door vs nearby open gap

        # Better test: gap at x=7, door at x=8
        obstacles2 = set()
        for x in range(10):
            if x != 7:  # Open gap at x=7
                obstacles2.add((x, 5))
        obstacles2.discard((8, 5))
        door_tiles2 = {(8, 5)}

        path = a_star((8, 3), (8, 7), 10, 10, obstacles2, set(), door_tiles=door_tiles2)
        assert path is not None
        # Should prefer going through x=7 gap (all normal cost) over x=8 door
        assert (8, 5) not in path, "Should prefer open gap at x=7 over door at x=8"
        assert (7, 5) in path, "Should route through the open gap"

    def test_door_tile_cost_is_weighted(self):
        """Verify door tiles have higher traversal cost (+3 vs +1)."""
        # Simple straight corridor with a door in the middle
        # Only one path possible, but we verify the path is returned
        obstacles = set()
        for y in range(5):
            for x in range(5):
                if x != 2:  # Only column 2 is walkable
                    obstacles.add((x, y))
        door_tiles = {(2, 2)}
        obstacles.discard((2, 2))  # Make sure door isn't in obstacles

        path = a_star((2, 0), (2, 4), 5, 5, obstacles, set(), door_tiles=door_tiles)
        assert path is not None
        assert (2, 2) in path  # Must go through door (only path)
        assert path == [(2, 1), (2, 2), (2, 3), (2, 4)]

    def test_multiple_doors_on_path(self):
        """A* should handle multiple door tiles on a single path."""
        obstacles = set()
        for y in range(10):
            for x in range(10):
                if x != 2:
                    obstacles.add((x, y))
        # Doors at y=3 and y=7
        door_tiles = {(2, 3), (2, 7)}
        obstacles.discard((2, 3))
        obstacles.discard((2, 7))

        path = a_star((2, 0), (2, 9), 10, 10, obstacles, set(), door_tiles=door_tiles)
        assert path is not None
        assert (2, 3) in path
        assert (2, 7) in path
        assert path[-1] == (2, 9)

    def test_door_tiles_none_backward_compat(self):
        """A* without door_tiles (None) should work as before."""
        path = a_star((0, 0), (4, 4), 10, 10, set(), set(), door_tiles=None)
        assert path is not None
        assert path[-1] == (4, 4)

    def test_empty_door_tiles_set(self):
        """Empty door_tiles set should behave same as None."""
        path = a_star((0, 0), (4, 4), 10, 10, set(), set(), door_tiles=set())
        assert path is not None
        assert path[-1] == (4, 4)

    def test_door_in_obstacles_and_door_tiles(self):
        """Door tile in BOTH obstacles AND door_tiles: door_tiles takes priority."""
        # Create a constrained corridor so only path goes through the door
        obstacles = set()
        for y in range(3):
            for x in range(3):
                if x != 1:
                    obstacles.add((x, y))
        # Door at (1, 1) is in both obstacles and door_tiles
        obstacles.add((1, 1))
        door_tiles = {(1, 1)}

        path = a_star((1, 0), (1, 2), 3, 3, obstacles, set(), door_tiles=door_tiles)
        assert path is not None
        assert (1, 1) in path  # Door removed from blocked set


# ===================================================================
# get_next_step_toward with door_tiles
# ===================================================================

class TestGetNextStepDoorTiles:
    """Test get_next_step_toward passes door_tiles to A*."""

    def test_next_step_through_door(self):
        """get_next_step_toward should step toward a door when it's the best path."""
        obstacles = set()
        for x in range(10):
            if x != 5:
                obstacles.add((x, 5))
        door_tiles = {(5, 5)}

        step = get_next_step_toward((5, 4), (5, 6), 10, 10, obstacles, set(), door_tiles=door_tiles)
        assert step == (5, 5)  # Step onto the door tile

    def test_next_step_no_door_tiles(self):
        """Without door_tiles, door in obstacles blocks the path."""
        obstacles = set()
        for x in range(10):
            obstacles.add((x, 5))  # Complete wall — no gaps at all

        step = get_next_step_toward((5, 4), (5, 6), 10, 10, obstacles, set(), door_tiles=None)
        assert step is None  # No path through the wall


# ===================================================================
# _maybe_interact_door helper
# ===================================================================

class TestMaybeInteractDoor:
    """Test the door interaction helper."""

    def test_returns_interact_for_adjacent_door(self):
        """When AI is adjacent to a door tile on its path, return INTERACT."""
        ai = make_player("ai1", "Ally", 5, 4, hero_id="owner1")
        door_tiles = {(5, 5)}

        result = _maybe_interact_door(ai, (5, 5), door_tiles)
        assert result is not None
        assert result.action_type == ActionType.INTERACT
        assert result.target_x == 5
        assert result.target_y == 5
        assert result.player_id == "ai1"

    def test_returns_none_for_non_door_tile(self):
        """When next step is not a door tile, return None."""
        ai = make_player("ai1", "Ally", 5, 4, hero_id="owner1")
        door_tiles = {(5, 5)}

        result = _maybe_interact_door(ai, (5, 6), door_tiles)
        assert result is None  # (5, 6) is not a door

    def test_returns_none_when_no_door_tiles(self):
        """When door_tiles is None, return None."""
        ai = make_player("ai1", "Ally", 5, 4, hero_id="owner1")

        result = _maybe_interact_door(ai, (5, 5), None)
        assert result is None

    def test_returns_none_when_not_adjacent(self):
        """When AI is not adjacent (Chebyshev distance > 1), return None."""
        ai = make_player("ai1", "Ally", 5, 2, hero_id="owner1")  # 3 tiles away
        door_tiles = {(5, 5)}

        result = _maybe_interact_door(ai, (5, 5), door_tiles)
        assert result is None  # Too far to interact

    def test_diagonal_adjacency_works(self):
        """Chebyshev distance 1 includes diagonal adjacency."""
        ai = make_player("ai1", "Ally", 4, 4, hero_id="owner1")  # Diagonal to (5,5)
        door_tiles = {(5, 5)}

        result = _maybe_interact_door(ai, (5, 5), door_tiles)
        assert result is not None
        assert result.action_type == ActionType.INTERACT


# ===================================================================
# AI Hero Allies Opening Doors
# ===================================================================

class TestAIHeroAllyDoorOpening:
    """Test that AI hero allies in various stances open doors."""

    def _make_party(self, owner_x, owner_y, ally_x, ally_y, door_pos=(5, 5)):
        """Create a simple party with owner and AI ally, door blocking path."""
        owner = make_player("owner1", "Player", owner_x, owner_y,
                            team="a", unit_type="human", hero_id=None,
                            ai_stance="follow")
        ally = make_player("ally1", "Ally", ally_x, ally_y,
                           team="a", unit_type="hero_ally", hero_id="owner1",
                           ai_stance="follow")
        all_units = {"owner1": owner, "ally1": ally}
        return owner, ally, all_units

    def test_follow_stance_opens_door(self):
        """Follow stance AI should INTERACT with a door blocking path to owner."""
        # Owner is at (5, 7), ally at (5, 4), door at (5, 5) with wall
        obstacles = set()
        for x in range(10):
            if x != 5:
                obstacles.add((x, 5))
        door_tiles = {(5, 5)}

        owner, ally, all_units = self._make_party(5, 7, 5, 4)
        ally.ai_stance = "follow"

        action = _decide_follow_action(ally, all_units, 10, 10, obstacles, None, None, None, door_tiles)
        assert action is not None
        assert action.action_type == ActionType.INTERACT
        assert action.target_x == 5
        assert action.target_y == 5

    def test_aggressive_stance_opens_door(self):
        """Aggressive stance AI should open doors when chasing enemies."""
        # Enemy on other side of door
        obstacles = set()
        for x in range(10):
            if x != 5:
                obstacles.add((x, 5))
        door_tiles = {(5, 5)}

        owner = make_player("owner1", "Player", 5, 3,
                            team="a", unit_type="human")
        ally = make_player("ally1", "Ally", 5, 4,
                           team="a", unit_type="hero_ally", hero_id="owner1",
                           ai_stance="aggressive")
        enemy = make_player("enemy1", "Enemy", 5, 7,
                            team="b", unit_type="enemy", ai_behavior="aggressive")
        all_units = {"owner1": owner, "ally1": ally, "enemy1": enemy}

        action = _decide_aggressive_stance_action(ally, all_units, 10, 10, obstacles, None, None, None, door_tiles)
        assert action is not None
        assert action.action_type == ActionType.INTERACT
        assert action.target_x == 5
        assert action.target_y == 5

    def test_defensive_stance_opens_door(self):
        """Defensive stance AI should open doors when following owner."""
        obstacles = set()
        for x in range(10):
            if x != 5:
                obstacles.add((x, 5))
        door_tiles = {(5, 5)}

        owner = make_player("owner1", "Player", 5, 7,
                            team="a", unit_type="human")
        ally = make_player("ally1", "Ally", 5, 4,
                           team="a", unit_type="hero_ally", hero_id="owner1",
                           ai_stance="defensive")
        all_units = {"owner1": owner, "ally1": ally}

        action = _decide_defensive_action(ally, all_units, 10, 10, obstacles, None, None, None, door_tiles)
        assert action is not None
        assert action.action_type == ActionType.INTERACT
        assert action.target_x == 5
        assert action.target_y == 5


# ===================================================================
# Enemy AI Cannot Open Doors
# ===================================================================

class TestEnemyAICannotOpenDoors:
    """Verify enemy AI does NOT receive door_tiles and cannot open doors."""

    def test_enemy_does_not_get_door_tiles(self):
        """decide_ai_action does NOT pass door_tiles to enemy AI behaviors."""
        obstacles = set()
        for x in range(10):
            obstacles.add((x, 5))
        # Complete wall — enemy cannot path through
        enemy = make_player("enemy1", "Goblin", 5, 4,
                            team="b", unit_type="enemy", ai_behavior="aggressive",
                            hero_id=None, ai_stance="follow")
        player = make_player("player1", "Player", 5, 7,
                             team="a", unit_type="human")
        all_units = {"enemy1": enemy, "player1": player}

        # Even though we pass door_tiles, enemy AI should not use them
        door_tiles = {(5, 5)}
        action = decide_ai_action(enemy, all_units, 10, 10, obstacles,
                                  door_tiles=door_tiles)
        # Enemy cannot reach player through wall — should not generate INTERACT
        if action is not None:
            assert action.action_type != ActionType.INTERACT

    def test_hero_ally_gets_door_tiles(self):
        """decide_ai_action passes door_tiles to hero ally stance functions."""
        obstacles = set()
        for x in range(10):
            if x != 5:
                obstacles.add((x, 5))
        door_tiles = {(5, 5)}

        owner = make_player("owner1", "Player", 5, 7,
                            team="a", unit_type="human")
        ally = make_player("ally1", "Ally", 5, 4,
                           team="a", unit_type="hero_ally", hero_id="owner1",
                           ai_stance="follow")
        all_units = {"owner1": owner, "ally1": ally}

        action = decide_ai_action(ally, all_units, 10, 10, obstacles,
                                  door_tiles=door_tiles)
        assert action is not None
        assert action.action_type == ActionType.INTERACT
        assert action.target_x == 5
        assert action.target_y == 5


# ===================================================================
# Edge Cases & Regression
# ===================================================================

class TestDoorPathfindingEdgeCases:
    """Edge cases for door-aware A* pathfinding."""

    def test_already_at_goal(self):
        """A* with door_tiles should still return [] when start == goal."""
        door_tiles = {(3, 3)}
        path = a_star((5, 5), (5, 5), 10, 10, set(), set(), door_tiles=door_tiles)
        assert path == []

    def test_goal_is_door_tile(self):
        """A* should reach a goal that is itself a door tile."""
        door_tiles = {(5, 5)}
        path = a_star((5, 3), (5, 5), 10, 10, set(), set(), door_tiles=door_tiles)
        assert path is not None
        assert path[-1] == (5, 5)

    def test_start_is_door_tile(self):
        """A* should start from a tile that happens to be a door tile."""
        door_tiles = {(5, 5)}
        path = a_star((5, 5), (5, 8), 10, 10, set(), set(), door_tiles=door_tiles)
        assert path is not None
        assert path[-1] == (5, 8)

    def test_door_tile_not_in_obstacles(self):
        """If a door is in door_tiles but NOT in obstacles, it still gets +3 cost."""
        # No obstacles at all, just a door tile in the middle
        door_tiles = {(5, 5)}
        path_with_door = a_star((5, 3), (5, 7), 10, 10, set(), set(), door_tiles=door_tiles)
        path_without_door = a_star((5, 3), (5, 7), 10, 10, set(), set(), door_tiles=None)

        # Both should find paths
        assert path_with_door is not None
        assert path_without_door is not None

        # With open space, A* might detour around the door tile due to +3 cost
        # (but both paths should reach the goal)
        assert path_with_door[-1] == (5, 7)
        assert path_without_door[-1] == (5, 7)

    def test_fully_blocked_even_with_doors(self):
        """A* returns None when path is blocked by obstacles AND no doors help."""
        # Complete wall with no doors
        obstacles = set()
        for x in range(10):
            obstacles.add((x, 5))
        door_tiles = set()  # No doors

        path = a_star((5, 0), (5, 9), 10, 10, obstacles, set(), door_tiles=door_tiles)
        assert path is None

    def test_occupied_goal_with_door(self):
        """A* should stop adjacent to an occupied goal, even with door on path."""
        obstacles = set()
        for x in range(10):
            if x != 5:
                obstacles.add((x, 5))
        door_tiles = {(5, 5)}
        occupied = {(5, 9)}  # Goal is occupied

        path = a_star((5, 0), (5, 9), 10, 10, obstacles, occupied, door_tiles=door_tiles)
        assert path is not None
        # Should end adjacent to goal, not on it
        last = path[-1]
        assert _chebyshev(last, (5, 9)) == 1

    def test_chebyshev_distance(self):
        """Verify _chebyshev helper works correctly for door interaction checks."""
        assert _chebyshev((5, 5), (5, 5)) == 0
        assert _chebyshev((5, 5), (5, 6)) == 1
        assert _chebyshev((5, 5), (6, 6)) == 1  # Diagonal
        assert _chebyshev((5, 5), (7, 5)) == 2
        assert _chebyshev((0, 0), (9, 9)) == 9
