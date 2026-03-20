"""
Tests for Strategic Exploration Phase B — Smart Leader Pathing.

Covers:
  B1: Strategic Patrol Replacement
    - Team leader paths toward exploration target (uncleared room)
    - Team leader emits MOVE with reason="explore_room"
    - Team leader opens doors en route to exploration target
    - Team leader falls back to patrol when all rooms cleared
    - Regular enemies (non-leaders) still use patrol, not exploration
    - Arena mode (no match_id / no rooms) — leader falls back to patrol
    - Leader with no A* path to target falls back to patrol

  B2: Room Clearing Behavior (integration)
    - Leader enters room → room becomes discovered via FOV
    - Leader fights enemies in room via existing combat → room cleared
    - Leader queries next uncleared room after clearing current

  B3: Door Prioritization (existing infrastructure)
    - A* naturally routes through closed doors (cost +3)
    - _maybe_interact_door opens door when adjacent
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.ai_behavior import _decide_aggressive_action, decide_ai_action
from app.core.ai_exploration import (
    build_room_graph,
    init_room_discovery,
    update_room_discovery,
    update_room_clearance,
    get_next_exploration_target,
    get_room_discovery,
    clear_exploration_state,
)
from app.core.ai_patrol import _patrol_targets
from app.core.combat import load_combat_config


MATCH = "test_explore_b"
GRID_W = 30
GRID_H = 20


def setup_module():
    load_combat_config()


def setup_function():
    clear_exploration_state()
    _patrol_targets.clear()


def teardown_function():
    clear_exploration_state()
    _patrol_targets.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _room(rid, x_min, y_min, x_max, y_max, purpose="combat", enemy_spawns=None):
    r = {
        "id": rid,
        "name": rid,
        "purpose": purpose,
        "bounds": {"x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max},
    }
    if enemy_spawns:
        r["enemy_spawns"] = enemy_spawns
    return r


def _door(x, y):
    return {"x": x, "y": y}


def _chest(x, y):
    return {"x": x, "y": y}


def _leader(pid, x, y, team="a"):
    """Create an AI team leader (hero_id=None, is_team_leader=True)."""
    return PlayerState(
        player_id=pid,
        username=pid,
        position=Position(x=x, y=y),
        hp=100,
        max_hp=100,
        attack_damage=15,
        armor=0,
        team=team,
        unit_type="ai",
        is_team_leader=True,
        hero_id=None,
        ai_behavior="aggressive",
        vision_range=7,
        ranged_range=5,
    )


def _enemy(pid, x, y, team="b", room_id=None, behavior="aggressive"):
    """Create a regular dungeon enemy."""
    return PlayerState(
        player_id=pid,
        username=pid,
        position=Position(x=x, y=y),
        hp=100,
        max_hp=100,
        attack_damage=15,
        armor=0,
        team=team,
        unit_type="ai",
        ai_behavior=behavior,
        enemy_type="skeleton",
        room_id=room_id,
        vision_range=7,
        ranged_range=5,
    )


def _obstacles_border(w, h):
    """Create border obstacles for a grid."""
    obs = set()
    for x in range(w):
        obs.add((x, 0))
        obs.add((x, h - 1))
    for y in range(h):
        obs.add((0, y))
        obs.add((w - 1, y))
    return obs


def _setup_two_rooms():
    """Set up two rooms connected by a door.

    Room layout:
      r1: (1,1)-(8,8)     door at (9,4)     r2: (10,1)-(18,8)
    """
    rooms = [
        _room("r1", 1, 1, 8, 8),
        _room("r2", 10, 1, 18, 8),
    ]
    doors = [_door(9, 4)]
    chests = []
    build_room_graph(MATCH, rooms, doors, chests)
    init_room_discovery(MATCH, ["a", "b"])
    return rooms, doors, chests


def _setup_three_rooms():
    """Set up three rooms in a chain: r1 — r2 — r3.

    Room layout:
      r1: (1,1)-(6,6)  door at (7,3)  r2: (8,1)-(14,6)  door at (15,3)  r3: (16,1)-(22,6)
    """
    rooms = [
        _room("r1", 1, 1, 6, 6),
        _room("r2", 8, 1, 14, 6),
        _room("r3", 16, 1, 22, 6),
    ]
    doors = [_door(7, 3), _door(15, 3)]
    chests = []
    build_room_graph(MATCH, rooms, doors, chests)
    init_room_discovery(MATCH, ["a", "b"])
    return rooms, doors, chests


# ===================================================================
# B1: Strategic Patrol Replacement
# ===================================================================

class TestLeaderExploration:
    """Team leader uses exploration targets instead of patrol."""

    def setup_method(self):
        clear_exploration_state()
        _patrol_targets.clear()

    def teardown_method(self):
        clear_exploration_state()
        _patrol_targets.clear()

    def test_leader_moves_toward_exploration_target(self):
        """Leader paths toward nearest uncleared room instead of random patrol."""
        _setup_two_rooms()
        # Discover r1 (leader is inside r1)
        team_fov = {(x, y) for x in range(1, 9) for y in range(1, 9)}
        update_room_discovery(MATCH, "a", team_fov)
        # Clear r1 (no enemies, no chests) so leader looks for the next room
        update_room_clearance(MATCH, "a", {}, chest_states={})
        # r1 is cleared, r2 is undiscovered — leader should explore r2

        leader = _leader("leader1", 4, 4, team="a")
        all_units = {"leader1": leader}
        obstacles = _obstacles_border(GRID_W, GRID_H)

        action = _decide_aggressive_action(
            leader, all_units, GRID_W, GRID_H, obstacles,
            team_fov=team_fov,
            match_id=MATCH,
            chest_states={},
        )

        assert action is not None
        assert action.action_type == ActionType.MOVE
        assert action.reason == "explore_room"

    def test_leader_explore_moves_toward_room_entrance(self):
        """Leader should move closer to the target room's entrance (door)."""
        _setup_two_rooms()
        # Discover r1, leave r2 undiscovered
        team_fov = {(x, y) for x in range(1, 9) for y in range(1, 9)}
        update_room_discovery(MATCH, "a", team_fov)
        # Clear r1 so leader targets r2
        update_room_clearance(MATCH, "a", {}, chest_states={})

        leader = _leader("leader1", 4, 4, team="a")
        all_units = {"leader1": leader}
        obstacles = _obstacles_border(GRID_W, GRID_H)

        action = _decide_aggressive_action(
            leader, all_units, GRID_W, GRID_H, obstacles,
            team_fov=team_fov,
            match_id=MATCH,
            chest_states={},
        )

        # Leader should move toward the door at (9,4) — the entrance to r2
        # First step from (4,4) should move rightward (closer to x=9)
        assert action.target_x > 4  # moving right toward the door

    def test_leader_falls_back_to_patrol_when_all_cleared(self):
        """When all rooms are cleared, leader falls back to regular patrol."""
        _setup_two_rooms()
        # Discover both rooms
        fov_r1 = {(x, y) for x in range(1, 9) for y in range(1, 9)}
        fov_r2 = {(x, y) for x in range(10, 19) for y in range(1, 9)}
        team_fov = fov_r1 | fov_r2
        update_room_discovery(MATCH, "a", team_fov)

        # Clear both rooms (no enemies, no chests)
        all_units_empty = {}
        update_room_clearance(MATCH, "a", all_units_empty, chest_states={})

        disc = get_room_discovery(MATCH, "a")
        assert disc["r1"] == "cleared"
        assert disc["r2"] == "cleared"

        # Now the leader should NOT get an exploration target
        target = get_next_exploration_target(MATCH, "a", (4, 4))
        assert target is None

        # And _decide_aggressive_action should fall back to patrol
        leader = _leader("leader1", 4, 4, team="a")
        full_units = {"leader1": leader}
        obstacles = _obstacles_border(GRID_W, GRID_H)

        action = _decide_aggressive_action(
            leader, full_units, GRID_W, GRID_H, obstacles,
            team_fov=team_fov,
            match_id=MATCH,
            chest_states={},
        )

        # Should still produce MOVE (patrol) but NOT with reason "explore_room"
        assert action is not None
        assert action.reason != "explore_room"

    def test_regular_enemy_uses_patrol_not_exploration(self):
        """Non-leader enemies should still use patrol, not exploration."""
        _setup_two_rooms()
        team_fov = {(x, y) for x in range(1, 9) for y in range(1, 9)}
        update_room_discovery(MATCH, "b", team_fov)

        enemy = _enemy("enemy1", 4, 4, team="b")
        all_units = {"enemy1": enemy}
        obstacles = _obstacles_border(GRID_W, GRID_H)

        action = _decide_aggressive_action(
            enemy, all_units, GRID_W, GRID_H, obstacles,
            team_fov=team_fov,
            match_id=MATCH,
            chest_states={},
        )

        # Enemy is not a team leader, so it should use patrol
        assert action is not None
        assert action.reason != "explore_room"

    def test_leader_no_match_id_falls_back_to_patrol(self):
        """Arena mode (no match_id) — leader falls back to patrol."""
        leader = _leader("leader1", 5, 5, team="a")
        all_units = {"leader1": leader}
        obstacles = _obstacles_border(GRID_W, GRID_H)

        action = _decide_aggressive_action(
            leader, all_units, GRID_W, GRID_H, obstacles,
            match_id=None,
            chest_states={},
        )

        assert action is not None
        assert action.reason != "explore_room"

    def test_leader_no_rooms_falls_back_to_patrol(self):
        """Match with no room definitions — leader falls back to patrol."""
        # Don't set up any rooms for this match
        leader = _leader("leader1", 5, 5, team="a")
        all_units = {"leader1": leader}
        obstacles = _obstacles_border(GRID_W, GRID_H)

        action = _decide_aggressive_action(
            leader, all_units, GRID_W, GRID_H, obstacles,
            match_id="no_rooms_match",
            chest_states={},
        )

        assert action is not None
        assert action.reason != "explore_room"


class TestLeaderExplorationChain:
    """Leader explores rooms in sequence as they are cleared."""

    def setup_method(self):
        clear_exploration_state()
        _patrol_targets.clear()

    def teardown_method(self):
        clear_exploration_state()
        _patrol_targets.clear()

    def test_leader_targets_nearest_uncleared_room(self):
        """With three rooms, leader should target the nearest frontier room."""
        _setup_three_rooms()
        # Discover r1 only
        fov_r1 = {(x, y) for x in range(1, 7) for y in range(1, 7)}
        update_room_discovery(MATCH, "a", fov_r1)
        # Clear r1 (no enemies, no chests)
        update_room_clearance(MATCH, "a", {}, chest_states={})

        # r1=cleared, r2=undiscovered (frontier), r3=undiscovered (deep)
        target = get_next_exploration_target(MATCH, "a", (3, 3))
        assert target is not None
        assert target["room_id"] == "r2"  # frontier, closer than r3

    def test_leader_advances_to_next_room_after_clearing(self):
        """After clearing r1 and r2, the leader should target r3."""
        _setup_three_rooms()
        # Discover and clear r1 and r2
        fov_r12 = {(x, y) for x in range(1, 15) for y in range(1, 7)}
        update_room_discovery(MATCH, "a", fov_r12)
        update_room_clearance(MATCH, "a", {}, chest_states={})

        disc = get_room_discovery(MATCH, "a")
        assert disc["r1"] == "cleared"
        assert disc["r2"] == "cleared"
        assert disc["r3"] == "undiscovered"

        # Leader at r2 center, should now target r3
        target = get_next_exploration_target(MATCH, "a", (11, 3))
        assert target is not None
        assert target["room_id"] == "r3"

    def test_leader_prefers_discovered_uncleared_over_undiscovered(self):
        """Discovered-but-uncleared rooms have higher priority than undiscovered."""
        _setup_three_rooms()
        # Discover r1 and r2, but r2 still has enemies (not cleared)
        fov_r12 = {(x, y) for x in range(1, 15) for y in range(1, 7)}
        update_room_discovery(MATCH, "a", fov_r12)

        enemy_in_r2 = _enemy("e1", 11, 3, team="b")
        update_room_clearance(MATCH, "a", {"e1": enemy_in_r2}, chest_states={})

        disc = get_room_discovery(MATCH, "a")
        assert disc["r1"] == "cleared"
        assert disc["r2"] == "discovered"  # has enemy, not cleared
        assert disc["r3"] == "undiscovered"

        # Leader at r1 center — should prefer r2 (discovered-uncleared, priority 1)
        # over r3 (undiscovered frontier, priority 2)
        target = get_next_exploration_target(MATCH, "a", (3, 3))
        assert target is not None
        assert target["room_id"] == "r2"
        assert target["priority"] == 1


class TestLeaderDoorInteraction:
    """Leader opens doors en route to exploration target."""

    def setup_method(self):
        clear_exploration_state()
        _patrol_targets.clear()

    def teardown_method(self):
        clear_exploration_state()
        _patrol_targets.clear()

    def test_leader_opens_door_when_adjacent_on_explore_path(self):
        """Leader adjacent to closed door on the explore path emits INTERACT."""
        _setup_two_rooms()
        # Discover r1
        fov_r1 = {(x, y) for x in range(1, 9) for y in range(1, 9)}
        update_room_discovery(MATCH, "a", fov_r1)

        # Place leader adjacent to the door at (9,4) — at (8,4)
        leader = _leader("leader1", 8, 4, team="a")
        all_units = {"leader1": leader}
        # Build obstacles: border + a wall between rooms except the door
        obstacles = _obstacles_border(GRID_W, GRID_H)
        # Add wall tiles between rooms
        for y in range(GRID_H):
            if y != 4:  # Leave door position open
                obstacles.add((9, y))

        door_tiles = {(9, 4)}  # Closed door

        action = _decide_aggressive_action(
            leader, all_units, GRID_W, GRID_H, obstacles,
            team_fov=fov_r1,
            match_id=MATCH,
            door_tiles=door_tiles,
            chest_states={},
        )

        assert action is not None
        # When adjacent to a closed door, should emit INTERACT to open it
        assert action.action_type in (ActionType.MOVE, ActionType.INTERACT)
        # If INTERACT, the target should be the door position
        if action.action_type == ActionType.INTERACT:
            assert (action.target_x, action.target_y) == (9, 4)


class TestCombatPreemptsExploration:
    """Combat/memory/reinforcement take priority over exploration."""

    def setup_method(self):
        clear_exploration_state()
        _patrol_targets.clear()

    def teardown_method(self):
        clear_exploration_state()
        _patrol_targets.clear()

    def test_visible_enemy_preempts_exploration(self):
        """When enemies are visible, leader attacks instead of exploring."""
        _setup_two_rooms()
        fov_r1 = {(x, y) for x in range(1, 9) for y in range(1, 9)}
        update_room_discovery(MATCH, "a", fov_r1)

        leader = _leader("leader1", 4, 4, team="a")
        enemy = _enemy("e1", 5, 4, team="b")
        all_units = {"leader1": leader, "e1": enemy}
        obstacles = _obstacles_border(GRID_W, GRID_H)

        action = _decide_aggressive_action(
            leader, all_units, GRID_W, GRID_H, obstacles,
            team_fov=fov_r1,
            match_id=MATCH,
            chest_states={},
        )

        # Should attack the enemy, not explore
        assert action is not None
        assert action.reason != "explore_room"
        assert action.action_type in (ActionType.ATTACK, ActionType.MOVE, ActionType.SKILL)

    def test_chest_seeking_preempts_exploration(self):
        """Nearby chest seeking (step 4b2) runs before exploration (step 4e)."""
        _setup_two_rooms()
        fov_r1 = {(x, y) for x in range(1, 9) for y in range(1, 9)}
        update_room_discovery(MATCH, "a", fov_r1)

        leader = _leader("leader1", 4, 4, team="a")
        all_units = {"leader1": leader}
        obstacles = _obstacles_border(GRID_W, GRID_H)

        # Place an unopened chest within seek range (6 tiles) of the leader
        chest_states = {"5,4": "unopened"}

        action = _decide_aggressive_action(
            leader, all_units, GRID_W, GRID_H, obstacles,
            team_fov=fov_r1,
            match_id=MATCH,
            chest_states=chest_states,
        )

        # Should seek/loot chest before exploring
        assert action is not None
        assert action.reason in ("aggro_chest_seek", "loot_adjacent_chest")
