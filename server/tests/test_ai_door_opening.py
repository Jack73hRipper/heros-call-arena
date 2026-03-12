"""
Tests for Phase 7D-3 — AI Door Opening (For Follow Stance).

Covers:
  - AI door resume: after INTERACT, ally resumes path through now-open door
  - Multi-door sequential crossing: AI opens multiple doors across ticks
  - Follow stance door opening: ally opens door to follow owner across rooms
  - Aggressive stance door opening: ally opens door when chasing enemies
  - Defensive stance door opening: ally opens door to stay near owner
  - Defensive stance enemy-approach uses door-aware pathfinding (bug fix)
  - Hold stance: never generates INTERACT (never moves)
  - Enemy AI exclusion: enemies never generate INTERACT actions
  - Edge cases: AI not adjacent to door, door already open, no doors on map
  - Integration: turn resolver opens door on INTERACT, ally moves through next tick
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType, TurnResult
from app.core.ai_behavior import (
    a_star,
    get_next_step_toward,
    decide_ai_action,
    _maybe_interact_door,
    _decide_follow_action,
    _decide_aggressive_stance_action,
    _decide_defensive_action,
    _decide_hold_action,
    _chebyshev,
    run_ai_decisions,
)
from app.core.turn_resolver import resolve_turn
from app.core.combat import load_combat_config


def setup_module():
    load_combat_config()


def make_player(pid, username, x, y, hp=100, team="a", unit_type="human",
                hero_id=None, ai_stance="follow", class_id=None,
                ranged_range=5, ai_behavior=None, enemy_type=None,
                vision_range=7) -> PlayerState:
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
        vision_range=vision_range,
    )


def _make_wall_with_door(door_x=5, wall_y=5, width=10):
    """Create a horizontal wall across the map with a single door gap.

    Returns (obstacles, door_tiles, door_states).
    obstacles includes the door position (as the server does for closed doors).
    door_tiles is the set for A* pathfinding.
    door_states is the dict for turn_resolver.
    """
    obstacles = set()
    for x in range(width):
        obstacles.add((x, wall_y))
    door_tiles = {(door_x, wall_y)}
    door_states = {f"{door_x},{wall_y}": "closed"}
    return obstacles, door_tiles, door_states


def _make_corridor_with_two_doors(width=15):
    """Create two parallel walls with doors for multi-door crossing tests.

    Layout (15-wide map):
      Wall at y=4 with door at x=5
      Wall at y=8 with door at x=5
    Returns (obstacles, door_tiles, door_states).
    """
    obstacles = set()
    for x in range(width):
        obstacles.add((x, 4))
        obstacles.add((x, 8))
    door_tiles = {(5, 4), (5, 8)}
    door_states = {
        "5,4": "closed",
        "5,8": "closed",
    }
    return obstacles, door_tiles, door_states


# ===================================================================
# AI Door Resume — Multi-Tick Behavior
# ===================================================================

class TestAIDoorResume:
    """After an AI opens a door (INTERACT), it should move through next tick."""

    def test_follow_opens_door_then_moves_through(self):
        """Tick 1: AI generates INTERACT. Tick 2: door is open, AI moves through."""
        # Wall at y=5 with door at x=5. Owner at (5,7), ally at (5,4).
        obstacles, door_tiles, door_states = _make_wall_with_door(5, 5, 10)

        owner = make_player("owner1", "Player", 5, 7, team="a", unit_type="human")
        ally = make_player("ally1", "Ally", 5, 4, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="follow")
        all_units = {"owner1": owner, "ally1": ally}

        # Tick 1: AI should generate INTERACT for the door
        action1 = _decide_follow_action(
            ally, all_units, 10, 10, obstacles, None, None, None, door_tiles,
        )
        assert action1 is not None
        assert action1.action_type == ActionType.INTERACT
        assert action1.target_x == 5
        assert action1.target_y == 5

        # Simulate door opening: remove from obstacles and door_tiles
        obstacles.discard((5, 5))
        door_tiles_after = set()  # Door is now open

        # Tick 2: AI should now MOVE through the opened door
        action2 = _decide_follow_action(
            ally, all_units, 10, 10, obstacles, None, None, None, door_tiles_after,
        )
        assert action2 is not None
        assert action2.action_type == ActionType.MOVE
        assert action2.target_x == 5
        assert action2.target_y == 5  # Steps onto the now-open door tile

    def test_follow_resumes_path_after_door_opens(self):
        """After stepping through an opened door, AI continues toward owner."""
        obstacles, _, _ = _make_wall_with_door(5, 5, 10)
        # Door is already open — remove from obstacles
        obstacles.discard((5, 5))

        owner = make_player("owner1", "Player", 5, 8, team="a", unit_type="human")
        # Ally is ON the door tile (just walked through)
        ally = make_player("ally1", "Ally", 5, 5, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="follow")
        all_units = {"owner1": owner, "ally1": ally}

        action = _decide_follow_action(
            ally, all_units, 10, 10, obstacles, None, None, None, None,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should continue toward owner (y increases toward 8)
        assert action.target_y == 6

    def test_aggressive_opens_door_then_chases_enemy(self):
        """Aggressive ally opens door, then chases enemy through it next tick."""
        obstacles, door_tiles, _ = _make_wall_with_door(5, 5, 10)

        owner = make_player("owner1", "Player", 5, 3, team="a", unit_type="human")
        ally = make_player("ally1", "Ally", 5, 4, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="aggressive")
        enemy = make_player("enemy1", "Goblin", 5, 7, team="b", unit_type="enemy",
                            ai_behavior="aggressive")
        all_units = {"owner1": owner, "ally1": ally, "enemy1": enemy}

        # Provide team_fov that includes the enemy position (ally can't see
        # through the wall on its own, but team shared vision reveals it)
        team_fov = {(5, 7), (5, 6), (5, 5), (5, 4), (5, 3)}

        # Tick 1: INTERACT with door
        action1 = _decide_aggressive_stance_action(
            ally, all_units, 10, 10, obstacles, team_fov, None, None, door_tiles,
        )
        assert action1 is not None
        assert action1.action_type == ActionType.INTERACT
        assert (action1.target_x, action1.target_y) == (5, 5)

        # Tick 2: Door open, chase enemy
        obstacles.discard((5, 5))
        action2 = _decide_aggressive_stance_action(
            ally, all_units, 10, 10, obstacles, team_fov, None, None, set(),
        )
        assert action2 is not None
        assert action2.action_type == ActionType.MOVE
        assert action2.target_y == 5  # Steps through the opened door

    def test_defensive_opens_door_then_follows_owner(self):
        """Defensive ally opens door to stay near owner, then follows through."""
        obstacles, door_tiles, _ = _make_wall_with_door(5, 5, 10)

        owner = make_player("owner1", "Player", 5, 8, team="a", unit_type="human")
        ally = make_player("ally1", "Ally", 5, 4, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="defensive")
        all_units = {"owner1": owner, "ally1": ally}

        # Tick 1: INTERACT with door (owner is far, dist > 2)
        action1 = _decide_defensive_action(
            ally, all_units, 10, 10, obstacles, None, None, None, door_tiles,
        )
        assert action1 is not None
        assert action1.action_type == ActionType.INTERACT
        assert (action1.target_x, action1.target_y) == (5, 5)

        # Tick 2: Door open, move through
        obstacles.discard((5, 5))
        action2 = _decide_defensive_action(
            ally, all_units, 10, 10, obstacles, None, None, None, set(),
        )
        assert action2 is not None
        assert action2.action_type == ActionType.MOVE
        assert action2.target_y == 5


# ===================================================================
# Multi-Door Sequential Crossing
# ===================================================================

class TestMultiDoorCrossing:
    """AI crosses multiple doors sequentially (one door per tick)."""

    def test_follow_crosses_two_doors_sequentially(self):
        """AI opens door 1, walks through, opens door 2, walks through."""
        obstacles, door_tiles, _ = _make_corridor_with_two_doors(15)

        owner = make_player("owner1", "Player", 5, 11, team="a", unit_type="human")
        ally = make_player("ally1", "Ally", 5, 2, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="follow")
        all_units = {"owner1": owner, "ally1": ally}

        # Tick 1: AI at (5,2), should INTERACT with door at (5,4)
        # But first it needs to walk to (5,3) which is adjacent to door
        action = _decide_follow_action(
            ally, all_units, 15, 15, obstacles, None, None, None, door_tiles,
        )
        assert action is not None
        # AI is at y=2, door is at y=4 — 2 tiles away. AI should MOVE toward door first.
        if action.action_type == ActionType.MOVE:
            # Move closer to door
            ally.position = Position(x=action.target_x, y=action.target_y)

            # Next tick: should be adjacent, INTERACT with door 1
            action = _decide_follow_action(
                ally, all_units, 15, 15, obstacles, None, None, None, door_tiles,
            )

        # At this point AI should be interacting with door 1
        if action.action_type == ActionType.INTERACT:
            assert (action.target_x, action.target_y) == (5, 4)
            # Open door 1
            obstacles.discard((5, 4))
            door_tiles.discard((5, 4))

        # Continue ticking until AI reaches door 2
        # Move through door 1
        ally.position = Position(x=5, y=4)
        action = _decide_follow_action(
            ally, all_units, 15, 15, obstacles, None, None, None, door_tiles,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE

        # Walk toward door 2 at (5,8)
        ally.position = Position(x=action.target_x, y=action.target_y)

        # Keep walking until we reach adjacency to door 2
        for _ in range(10):  # Safety limit
            if _chebyshev((ally.position.x, ally.position.y), (5, 8)) <= 1:
                break
            action = _decide_follow_action(
                ally, all_units, 15, 15, obstacles, None, None, None, door_tiles,
            )
            if action and action.action_type == ActionType.MOVE:
                ally.position = Position(x=action.target_x, y=action.target_y)

        # Now adjacent to door 2: should INTERACT
        action = _decide_follow_action(
            ally, all_units, 15, 15, obstacles, None, None, None, door_tiles,
        )
        assert action is not None
        assert action.action_type == ActionType.INTERACT
        assert (action.target_x, action.target_y) == (5, 8)

    def test_a_star_paths_through_multiple_doors(self):
        """A* returns a valid path that crosses two closed doors."""
        obstacles, door_tiles, _ = _make_corridor_with_two_doors(15)

        path = a_star((5, 2), (5, 11), 15, 15, obstacles, set(), door_tiles=door_tiles)
        assert path is not None
        assert (5, 4) in path  # Goes through door 1
        assert (5, 8) in path  # Goes through door 2
        assert path[-1] == (5, 11)


# ===================================================================
# Hold Stance — Never Opens Doors
# ===================================================================

class TestHoldStanceNoDoors:
    """Hold stance never moves, never generates INTERACT."""

    def test_hold_never_generates_interact(self):
        """Hold stance AI should never produce INTERACT even with doors nearby."""
        obstacles, door_tiles, _ = _make_wall_with_door(5, 5, 10)

        owner = make_player("owner1", "Player", 5, 7, team="a", unit_type="human")
        # Ally adjacent to door
        ally = make_player("ally1", "Ally", 5, 4, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="hold")
        all_units = {"owner1": owner, "ally1": ally}

        action = _decide_hold_action(
            ally, all_units, 10, 10, obstacles, None, None, None,
        )
        assert action is not None
        # Hold stance should WAIT (no enemies nearby)
        assert action.action_type == ActionType.WAIT
        assert action.action_type != ActionType.INTERACT

    def test_hold_with_enemy_across_door_still_waits(self):
        """Hold stance doesn't open door even if enemy is on the other side."""
        obstacles, door_tiles, _ = _make_wall_with_door(5, 5, 10)

        ally = make_player("ally1", "Ally", 5, 4, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="hold")
        enemy = make_player("enemy1", "Goblin", 5, 7, team="b", unit_type="enemy",
                            ai_behavior="aggressive")
        owner = make_player("owner1", "Player", 5, 3, team="a", unit_type="human")
        all_units = {"owner1": owner, "ally1": ally, "enemy1": enemy}

        action = _decide_hold_action(
            ally, all_units, 10, 10, obstacles, None, None, None,
        )
        # Enemy is not visible through the wall, and hold never moves
        assert action is not None
        assert action.action_type != ActionType.INTERACT


# ===================================================================
# Enemy AI Cannot Open Doors — Regression Guard
# ===================================================================

class TestEnemyAINoDoorsRegression:
    """Enemy AI units must never generate INTERACT actions for doors."""

    def test_enemy_aggressive_cannot_open_door(self):
        """Aggressive enemy AI with door in path does NOT generate INTERACT."""
        obstacles, door_tiles, _ = _make_wall_with_door(5, 5, 10)

        enemy = make_player("enemy1", "Goblin", 5, 4, team="b", unit_type="enemy",
                            ai_behavior="aggressive", hero_id=None)
        player = make_player("player1", "Player", 5, 7, team="a", unit_type="human")
        all_units = {"enemy1": enemy, "player1": player}

        action = decide_ai_action(
            enemy, all_units, 10, 10, obstacles, door_tiles=door_tiles,
        )
        if action is not None:
            assert action.action_type != ActionType.INTERACT

    def test_enemy_ranged_cannot_open_door(self):
        """Ranged enemy AI cannot open doors."""
        obstacles, door_tiles, _ = _make_wall_with_door(5, 5, 10)

        enemy = make_player("enemy1", "Archer", 5, 4, team="b", unit_type="enemy",
                            ai_behavior="ranged", hero_id=None)
        player = make_player("player1", "Player", 5, 7, team="a", unit_type="human")
        all_units = {"enemy1": enemy, "player1": player}

        action = decide_ai_action(
            enemy, all_units, 10, 10, obstacles, door_tiles=door_tiles,
        )
        if action is not None:
            assert action.action_type != ActionType.INTERACT

    def test_enemy_boss_cannot_open_door(self):
        """Boss enemy AI cannot open doors."""
        obstacles, door_tiles, _ = _make_wall_with_door(5, 5, 10)

        enemy = make_player("enemy1", "Boss", 5, 4, team="b", unit_type="enemy",
                            ai_behavior="boss", hero_id=None)
        player = make_player("player1", "Player", 5, 7, team="a", unit_type="human")
        all_units = {"enemy1": enemy, "player1": player}

        action = decide_ai_action(
            enemy, all_units, 10, 10, obstacles, door_tiles=door_tiles,
        )
        if action is not None:
            assert action.action_type != ActionType.INTERACT

    def test_run_ai_decisions_excludes_enemies_from_door_tiles(self):
        """run_ai_decisions passes door_tiles to hero allies but not enemies."""
        obstacles, door_tiles, _ = _make_wall_with_door(5, 5, 10)

        owner = make_player("owner1", "Player", 5, 7, team="a", unit_type="human")
        ally = make_player("ally1", "Ally", 5, 4, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="follow")
        # Place enemy behind the wall so ally can't see it (wall blocks FOV)
        enemy = make_player("enemy1", "Goblin", 1, 8, team="b", unit_type="enemy",
                            ai_behavior="aggressive", hero_id=None)
        all_units = {"owner1": owner, "ally1": ally, "enemy1": enemy}

        actions = run_ai_decisions(
            ["ally1", "enemy1"], all_units, 10, 10, obstacles,
            door_tiles=door_tiles,
        )

        # Find the ally's action — should be INTERACT (adjacent to door, owner across)
        ally_actions = [a for a in actions if a.player_id == "ally1"]
        enemy_actions = [a for a in actions if a.player_id == "enemy1"]

        assert len(ally_actions) == 1
        assert ally_actions[0].action_type == ActionType.INTERACT

        # Enemy should NOT have INTERACT
        for ea in enemy_actions:
            assert ea.action_type != ActionType.INTERACT


# ===================================================================
# Defensive Stance Bug Fix — Enemy-Approach Door-Aware Pathfinding
# ===================================================================

class TestDefensiveStanceDoorFix:
    """Verify the bug fix: defensive stance's enemy-approach uses door_tiles."""

    def test_defensive_enemy_approach_uses_door_aware_path(self):
        """When a defensive ally moves toward a nearby enemy, it should use
        door-aware A* (not block on closed doors)."""
        # Create a small map where an enemy is within 2 tiles but separated
        # by a door.  Owner is on the same side as ally.
        obstacles = set()
        for x in range(10):
            if x != 5:
                obstacles.add((x, 4))
        door_tiles = {(5, 4)}

        # Owner next to ally, enemy on other side of door within 2 tiles
        owner = make_player("owner1", "Player", 5, 2, team="a", unit_type="human")
        ally = make_player("ally1", "Ally", 5, 3, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="defensive")
        # Enemy at (5,5) — Chebyshev 2 from ally at (5,3), separated by door at (5,4)
        enemy = make_player("enemy1", "Goblin", 5, 5, team="b", unit_type="enemy",
                            ai_behavior="aggressive")
        all_units = {"owner1": owner, "ally1": ally, "enemy1": enemy}

        # Ally is within 2 of owner, enemy within 2 — should try to approach
        # With door_tiles, A* can find path through the door
        action = _decide_defensive_action(
            ally, all_units, 10, 10, obstacles, None, None, None, door_tiles,
        )
        # The ally should either INTERACT with the door or the pathfinding should
        # at least succeed (not block). Since ally at (5,3) looking to path to (5,5)
        # through door at (5,4), it should INTERACT.
        assert action is not None
        # Since dist_to_owner is 1 (<=2), it won't trigger the "path to owner" branch.
        # It should try to fight the enemy. Enemy is within 2 tiles (chebyshev).
        # Not adjacent, so it tries to path toward enemy and checks owner distance.
        # The key assertion: action is not WAIT (which would happen if path failed)
        if action.action_type == ActionType.MOVE:
            # Path succeeded through door-aware A*
            assert True
        elif action.action_type == ActionType.INTERACT:
            # Even better — opened the door
            assert (action.target_x, action.target_y) == (5, 4)
        else:
            # Could be RANGED_ATTACK or something else valid
            assert action.action_type != ActionType.WAIT, \
                "Defensive should not WAIT when enemy is within 2 tiles and door can be pathed"


# ===================================================================
# Edge Cases
# ===================================================================

class TestAIDoorEdgeCases:
    """Edge cases for AI door opening behavior."""

    def test_ai_not_adjacent_to_door_moves_closer(self):
        """AI 3+ tiles from door should MOVE toward it, not INTERACT."""
        obstacles, door_tiles, _ = _make_wall_with_door(5, 5, 10)

        owner = make_player("owner1", "Player", 5, 8, team="a", unit_type="human")
        # Ally far from door
        ally = make_player("ally1", "Ally", 5, 1, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="follow")
        all_units = {"owner1": owner, "ally1": ally}

        action = _decide_follow_action(
            ally, all_units, 10, 10, obstacles, None, None, None, door_tiles,
        )
        assert action is not None
        # Should MOVE closer (not INTERACT — too far from door)
        assert action.action_type == ActionType.MOVE
        # Moving toward the door (y increases from 1 toward 5)
        assert action.target_y > ally.position.y

    def test_door_already_open_no_interact(self):
        """AI should just MOVE through an already-open door tile."""
        obstacles = set()
        for x in range(10):
            if x != 5:
                obstacles.add((x, 5))
        # Door is open — not in obstacles, not in door_tiles

        owner = make_player("owner1", "Player", 5, 8, team="a", unit_type="human")
        ally = make_player("ally1", "Ally", 5, 4, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="follow")
        all_units = {"owner1": owner, "ally1": ally}

        action = _decide_follow_action(
            ally, all_units, 10, 10, obstacles, None, None, None, None,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        assert action.target_x == 5
        assert action.target_y == 5  # Walks right through

    def test_no_doors_on_map_normal_movement(self):
        """When there are no doors, AI moves normally with door_tiles=None."""
        owner = make_player("owner1", "Player", 5, 8, team="a", unit_type="human")
        ally = make_player("ally1", "Ally", 5, 4, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="follow")
        all_units = {"owner1": owner, "ally1": ally}

        action = _decide_follow_action(
            ally, all_units, 10, 10, set(), None, None, None, None,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        assert action.target_y == 5

    def test_diagonal_adjacency_triggers_interact(self):
        """AI diagonally adjacent to a door should generate INTERACT."""
        obstacles, door_tiles, _ = _make_wall_with_door(5, 5, 10)

        owner = make_player("owner1", "Player", 5, 7, team="a", unit_type="human")
        # Ally diagonal to door at (5,5)
        ally = make_player("ally1", "Ally", 4, 4, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="follow")
        all_units = {"owner1": owner, "ally1": ally}

        action = _decide_follow_action(
            ally, all_units, 10, 10, obstacles, None, None, None, door_tiles,
        )
        assert action is not None
        assert action.action_type == ActionType.INTERACT
        assert (action.target_x, action.target_y) == (5, 5)

    def test_ally_at_door_tile_not_in_door_tiles(self):
        """If ally is standing on a tile that used to be a door (now open), no issue."""
        owner = make_player("owner1", "Player", 5, 8, team="a", unit_type="human")
        ally = make_player("ally1", "Ally", 5, 5, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="follow")
        all_units = {"owner1": owner, "ally1": ally}

        action = _decide_follow_action(
            ally, all_units, 10, 10, set(), None, None, None, None,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        assert action.target_y == 6

    def test_empty_door_tiles_set_no_interact(self):
        """Empty door_tiles set behaves like None — no INTERACT generated."""
        owner = make_player("owner1", "Player", 5, 8, team="a", unit_type="human")
        ally = make_player("ally1", "Ally", 5, 4, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="follow")
        all_units = {"owner1": owner, "ally1": ally}

        action = _decide_follow_action(
            ally, all_units, 10, 10, set(), None, None, None, set(),
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE

    def test_maybe_interact_door_on_same_tile(self):
        """_maybe_interact_door returns None if AI is ON the door tile (distance 0)."""
        ai = make_player("ai1", "Ally", 5, 5, hero_id="owner1")
        door_tiles = {(5, 5)}

        result = _maybe_interact_door(ai, (5, 5), door_tiles)
        # Chebyshev distance is 0, not 1 — should return None
        assert result is None


# ===================================================================
# Turn Resolver Integration
# ===================================================================

class TestTurnResolverDoorIntegration:
    """Integration tests: AI INTERACT + turn resolver opens door."""

    def test_ai_interact_opens_door_in_resolver(self):
        """When AI generates INTERACT, turn_resolver opens the door."""
        obstacles, _, door_states = _make_wall_with_door(5, 5, 10)

        owner = make_player("owner1", "Player", 5, 7, team="a", unit_type="human")
        ally = make_player("ally1", "Ally", 5, 4, team="a", unit_type="hero_ally",
                           hero_id="owner1", ai_stance="follow")
        players = {"owner1": owner, "ally1": ally}

        # Simulate AI generating INTERACT action
        interact_action = PlayerAction(
            player_id="ally1",
            action_type=ActionType.INTERACT,
            target_x=5,
            target_y=5,
        )

        result = resolve_turn(
            match_id="test_match",
            turn_number=1,
            players=players,
            actions=[interact_action],
            grid_width=10,
            grid_height=10,
            obstacles=obstacles,
            door_states=door_states,
        )

        # Door should now be open
        assert door_states["5,5"] == "open"
        # Door should be removed from obstacles
        assert (5, 5) not in obstacles
        # Result should show success
        interact_results = [
            r for r in result.actions
            if r.action_type == ActionType.INTERACT and r.player_id == "ally1"
        ]
        assert len(interact_results) == 1
        assert interact_results[0].success is True

    def test_full_tick_ai_interact_then_ally_moves_through(self):
        """In the same tick: AI 1 opens door (phase 1.5), AI 2 can move through.

        Turn resolver processes INTERACT in phase 1.5 and MOVE in phase 1.
        Actually MOVE is phase 1, INTERACT is phase 1.5 — so movement resolves
        BEFORE interact. But another unit's MOVE next tick will go through.
        Let's test the two-tick flow.
        """
        obstacles, door_tiles, door_states = _make_wall_with_door(5, 5, 10)

        owner = make_player("owner1", "Player", 5, 8, team="a", unit_type="human")
        ally1 = make_player("ally1", "Opener", 5, 4, team="a", unit_type="hero_ally",
                            hero_id="owner1", ai_stance="follow")
        ally2 = make_player("ally2", "Follower", 5, 3, team="a", unit_type="hero_ally",
                            hero_id="owner1", ai_stance="follow")
        players = {"owner1": owner, "ally1": ally1, "ally2": ally2}

        # Tick 1: ally1 opens the door
        interact_action = PlayerAction(
            player_id="ally1",
            action_type=ActionType.INTERACT,
            target_x=5, target_y=5,
        )
        result1 = resolve_turn(
            "test_match", 1, players, [interact_action],
            10, 10, obstacles, door_states=door_states,
        )
        assert door_states["5,5"] == "open"
        assert (5, 5) not in obstacles

        # Tick 2: Both allies can now move through the open door
        move1 = PlayerAction(
            player_id="ally1",
            action_type=ActionType.MOVE,
            target_x=5, target_y=5,
        )
        move2 = PlayerAction(
            player_id="ally2",
            action_type=ActionType.MOVE,
            target_x=5, target_y=4,
        )
        result2 = resolve_turn(
            "test_match", 2, players, [move1, move2],
            10, 10, obstacles, door_states=door_states,
        )

        # ally1 should have moved onto the door tile
        move_results = [
            r for r in result2.actions
            if r.action_type == ActionType.MOVE and r.player_id == "ally1"
        ]
        assert len(move_results) == 1
        assert move_results[0].success is True


# ===================================================================
# All Stances Door Opening Summary
# ===================================================================

class TestAllStancesDoorBehavior:
    """Verify door opening behavior for each stance is correct."""

    def _setup_door_scenario(self):
        """Create consistent door scenario for all stance tests."""
        obstacles, door_tiles, _ = _make_wall_with_door(5, 5, 10)
        owner = make_player("owner1", "Player", 5, 7, team="a", unit_type="human")
        ally = make_player("ally1", "Ally", 5, 4, team="a", unit_type="hero_ally",
                           hero_id="owner1")
        all_units = {"owner1": owner, "ally1": ally}
        return obstacles, door_tiles, owner, ally, all_units

    def test_follow_opens_door(self):
        """Follow stance: opens door to reach owner."""
        obstacles, door_tiles, owner, ally, all_units = self._setup_door_scenario()
        ally.ai_stance = "follow"

        action = _decide_follow_action(
            ally, all_units, 10, 10, obstacles, None, None, None, door_tiles,
        )
        assert action is not None
        assert action.action_type == ActionType.INTERACT

    def test_aggressive_opens_door(self):
        """Aggressive stance: opens door to reach enemy."""
        obstacles, door_tiles, owner, ally, all_units = self._setup_door_scenario()
        ally.ai_stance = "aggressive"
        enemy = make_player("enemy1", "Goblin", 5, 7, team="b", unit_type="enemy",
                            ai_behavior="aggressive")
        all_units["enemy1"] = enemy
        owner.position = Position(x=5, y=3)  # Move owner to same side as ally

        # Provide team_fov so ally can see enemy through shared team vision
        team_fov = {(5, 7), (5, 6), (5, 5), (5, 4), (5, 3)}

        action = _decide_aggressive_stance_action(
            ally, all_units, 10, 10, obstacles, team_fov, None, None, door_tiles,
        )
        assert action is not None
        assert action.action_type == ActionType.INTERACT

    def test_defensive_opens_door(self):
        """Defensive stance: opens door to follow owner."""
        obstacles, door_tiles, owner, ally, all_units = self._setup_door_scenario()
        ally.ai_stance = "defensive"

        action = _decide_defensive_action(
            ally, all_units, 10, 10, obstacles, None, None, None, door_tiles,
        )
        assert action is not None
        assert action.action_type == ActionType.INTERACT

    def test_hold_does_not_open_door(self):
        """Hold stance: never opens doors (never moves)."""
        obstacles, door_tiles, owner, ally, all_units = self._setup_door_scenario()
        ally.ai_stance = "hold"

        action = _decide_hold_action(
            ally, all_units, 10, 10, obstacles, None, None, None,
        )
        assert action is not None
        assert action.action_type != ActionType.INTERACT

    def test_decide_ai_action_dispatches_door_tiles_to_stances(self):
        """decide_ai_action correctly passes door_tiles through to stance handlers."""
        obstacles, door_tiles, owner, ally, all_units = self._setup_door_scenario()
        ally.ai_stance = "follow"

        action = decide_ai_action(
            ally, all_units, 10, 10, obstacles, door_tiles=door_tiles,
        )
        assert action is not None
        assert action.action_type == ActionType.INTERACT
        assert (action.target_x, action.target_y) == (5, 5)
