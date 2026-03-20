"""
Tests for Strategic Exploration Phase A — Room Graph & Discovery Tracking.

Covers:
  - A1: Room adjacency graph construction
    - Two rooms connected by a door
    - Three rooms in a chain
    - Room with no doors (isolated)
    - Multiple doors between same rooms
  - A2: Room discovery state
    - init_room_discovery sets all rooms to undiscovered
    - update_room_discovery transitions undiscovered → discovered when FOV overlaps
    - FOV outside room bounds doesn't trigger discovery
    - update_room_clearance transitions discovered → cleared when no enemies + chests opened
    - Clearance blocked by alive enemies in room
    - Clearance blocked by unopened chests
  - A3: Exploration target API
    - Prefers discovered-uncleared over undiscovered
    - Prefers frontier (adjacent to known) over deep unknown
    - Returns None when all rooms cleared
    - Closest room wins within same priority tier
  - Helpers:
    - get_current_room returns correct room or None
    - get_exploration_progress returns correct stats
    - clear_exploration_state cleans up
"""

from app.core.ai_exploration import (
    build_room_graph,
    init_room_discovery,
    update_room_discovery,
    update_room_clearance,
    get_next_exploration_target,
    get_current_room,
    get_exploration_progress,
    get_room_discovery,
    get_room_graph,
    get_room_info,
    clear_exploration_state,
)
from app.models.player import PlayerState, Position


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _room(rid, x_min, y_min, x_max, y_max, purpose="combat", name=None, enemy_spawns=None):
    """Create a minimal room definition dict."""
    r = {
        "id": rid,
        "name": name or rid,
        "purpose": purpose,
        "bounds": {"x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max},
    }
    if enemy_spawns:
        r["enemy_spawns"] = enemy_spawns
    return r


def _door(x, y, state="closed"):
    return {"x": x, "y": y, "state": state}


def _chest(x, y):
    return {"x": x, "y": y}


def _unit(pid, x, y, team="b", alive=True):
    return PlayerState(
        player_id=pid,
        username=pid,
        position=Position(x=x, y=y),
        hp=50 if alive else 0,
        max_hp=50,
        attack_damage=10,
        armor=0,
        team=team,
        unit_type="ai",
        is_alive=alive,
        vision_range=7,
    )


MATCH = "test_explore"


def _cleanup():
    clear_exploration_state()


def setup_function():
    _cleanup()


def teardown_function():
    _cleanup()


# ===================================================================
# A1: Room Adjacency Graph
# ===================================================================

class TestRoomGraph:
    """Tests for build_room_graph."""

    def setup_method(self):
        _cleanup()

    def test_two_rooms_connected_by_door(self):
        rooms = [
            _room("r1", 0, 0, 5, 5),
            _room("r2", 7, 0, 12, 5),
        ]
        doors = [_door(6, 2)]  # Between r1 and r2
        graph = build_room_graph(MATCH, rooms, doors)

        assert "r1" in graph
        assert "r2" in graph
        assert "r2" in graph["r1"]
        assert "r1" in graph["r2"]

    def test_three_rooms_chain(self):
        rooms = [
            _room("r1", 0, 0, 5, 5),
            _room("r2", 7, 0, 12, 5),
            _room("r3", 14, 0, 19, 5),
        ]
        doors = [
            _door(6, 2),   # r1 ↔ r2
            _door(13, 2),  # r2 ↔ r3
        ]
        graph = build_room_graph(MATCH, rooms, doors)

        assert "r2" in graph["r1"]
        assert "r1" in graph["r2"]
        assert "r3" in graph["r2"]
        assert "r2" in graph["r3"]
        # r1 and r3 are NOT directly connected
        assert "r3" not in graph["r1"]
        assert "r1" not in graph["r3"]

    def test_isolated_room_no_doors(self):
        rooms = [
            _room("r1", 0, 0, 5, 5),
            _room("r2", 20, 20, 25, 25),  # Far away, no door
        ]
        doors = []
        graph = build_room_graph(MATCH, rooms, doors)

        assert graph["r1"] == set()
        assert graph["r2"] == set()

    def test_multiple_doors_same_rooms(self):
        rooms = [
            _room("r1", 0, 0, 5, 5),
            _room("r2", 7, 0, 12, 5),
        ]
        doors = [
            _door(6, 1),  # Both doors between r1 and r2
            _door(6, 4),
        ]
        graph = build_room_graph(MATCH, rooms, doors)

        # Still just one adjacency edge (set deduplicates)
        assert graph["r1"] == {"r2"}
        assert graph["r2"] == {"r1"}

    def test_chest_mapping(self):
        rooms = [_room("r1", 0, 0, 5, 5)]
        chests = [_chest(2, 3), _chest(4, 4)]
        build_room_graph(MATCH, rooms, [], chests)

        info = get_room_info(MATCH)
        assert "r1" in info

    def test_room_center_computed(self):
        rooms = [_room("r1", 0, 0, 10, 6)]
        build_room_graph(MATCH, rooms, [])

        info = get_room_info(MATCH)
        assert info["r1"]["center"] == (5, 3)

    def test_empty_rooms_list(self):
        graph = build_room_graph(MATCH, [], [])
        assert graph == {}


# ===================================================================
# A2: Room Discovery State
# ===================================================================

class TestRoomDiscovery:
    """Tests for init/update room discovery and clearance."""

    def setup_method(self):
        _cleanup()

    def _setup_two_rooms(self):
        rooms = [
            _room("r1", 0, 0, 5, 5),
            _room("r2", 7, 0, 12, 5),
        ]
        doors = [_door(6, 2)]
        build_room_graph(MATCH, rooms, doors)
        init_room_discovery(MATCH, ["a", "b"])

    def test_init_all_undiscovered(self):
        self._setup_two_rooms()
        disc = get_room_discovery(MATCH, "a")
        assert disc["r1"] == "undiscovered"
        assert disc["r2"] == "undiscovered"

    def test_fov_overlap_discovers_room(self):
        self._setup_two_rooms()
        # FOV tiles inside r1 bounds (0-5, 0-5)
        fov = {(2, 2), (3, 3)}
        newly = update_room_discovery(MATCH, "a", fov)
        assert "r1" in newly
        assert get_room_discovery(MATCH, "a")["r1"] == "discovered"
        # r2 still undiscovered
        assert get_room_discovery(MATCH, "a")["r2"] == "undiscovered"

    def test_fov_outside_room_no_discovery(self):
        self._setup_two_rooms()
        # FOV tiles outside both rooms
        fov = {(6, 6), (15, 15)}
        newly = update_room_discovery(MATCH, "a", fov)
        assert newly == []
        assert get_room_discovery(MATCH, "a")["r1"] == "undiscovered"

    def test_already_discovered_not_rediscovered(self):
        self._setup_two_rooms()
        fov = {(2, 2)}
        update_room_discovery(MATCH, "a", fov)
        # Second call should not re-report
        newly = update_room_discovery(MATCH, "a", fov)
        assert newly == []

    def test_clearance_no_enemies_no_chests(self):
        rooms = [_room("r1", 0, 0, 5, 5)]
        build_room_graph(MATCH, rooms, [], [])
        init_room_discovery(MATCH, ["a"])
        # Discover the room first
        update_room_discovery(MATCH, "a", {(2, 2)})
        assert get_room_discovery(MATCH, "a")["r1"] == "discovered"

        # Clear: no enemies, no chests
        cleared = update_room_clearance(MATCH, "a", {}, {})
        assert "r1" in cleared
        assert get_room_discovery(MATCH, "a")["r1"] == "cleared"

    def test_clearance_blocked_by_alive_enemy(self):
        rooms = [_room("r1", 0, 0, 5, 5)]
        build_room_graph(MATCH, rooms, [], [])
        init_room_discovery(MATCH, ["a"])
        update_room_discovery(MATCH, "a", {(2, 2)})

        # Enemy inside room
        units = {"e1": _unit("e1", 3, 3, team="b", alive=True)}
        cleared = update_room_clearance(MATCH, "a", units, {})
        assert cleared == []
        assert get_room_discovery(MATCH, "a")["r1"] == "discovered"

    def test_clearance_blocked_by_unopened_chest(self):
        rooms = [_room("r1", 0, 0, 5, 5)]
        chests = [_chest(2, 4)]
        build_room_graph(MATCH, rooms, [], chests)
        init_room_discovery(MATCH, ["a"])
        update_room_discovery(MATCH, "a", {(2, 2)})

        # No enemies but chest still unopened
        chest_states = {"2,4": "unopened:wooden"}
        cleared = update_room_clearance(MATCH, "a", {}, chest_states)
        assert cleared == []

    def test_clearance_succeeds_after_chest_opened(self):
        rooms = [_room("r1", 0, 0, 5, 5)]
        chests = [_chest(2, 4)]
        build_room_graph(MATCH, rooms, [], chests)
        init_room_discovery(MATCH, ["a"])
        update_room_discovery(MATCH, "a", {(2, 2)})

        # Chest opened
        chest_states = {"2,4": "opened:wooden"}
        cleared = update_room_clearance(MATCH, "a", {}, chest_states)
        assert "r1" in cleared

    def test_dead_enemy_does_not_block_clearance(self):
        rooms = [_room("r1", 0, 0, 5, 5)]
        build_room_graph(MATCH, rooms, [], [])
        init_room_discovery(MATCH, ["a"])
        update_room_discovery(MATCH, "a", {(2, 2)})

        # Dead enemy inside room
        units = {"e1": _unit("e1", 3, 3, team="b", alive=False)}
        cleared = update_room_clearance(MATCH, "a", units, {})
        assert "r1" in cleared

    def test_same_team_unit_does_not_block_clearance(self):
        rooms = [_room("r1", 0, 0, 5, 5)]
        build_room_graph(MATCH, rooms, [], [])
        init_room_discovery(MATCH, ["a"])
        update_room_discovery(MATCH, "a", {(2, 2)})

        # Friendly unit inside room (same team "a")
        units = {"a1": _unit("a1", 3, 3, team="a", alive=True)}
        cleared = update_room_clearance(MATCH, "a", units, {})
        assert "r1" in cleared

    def test_undiscovered_room_not_checked_for_clearance(self):
        rooms = [_room("r1", 0, 0, 5, 5)]
        build_room_graph(MATCH, rooms, [], [])
        init_room_discovery(MATCH, ["a"])
        # r1 is still undiscovered — clearance should not process it
        cleared = update_room_clearance(MATCH, "a", {}, {})
        assert cleared == []

    def test_independent_team_tracking(self):
        self._setup_two_rooms()
        # Team A discovers r1
        update_room_discovery(MATCH, "a", {(2, 2)})
        assert get_room_discovery(MATCH, "a")["r1"] == "discovered"
        # Team B hasn't discovered anything
        assert get_room_discovery(MATCH, "b")["r1"] == "undiscovered"


# ===================================================================
# A3: Exploration Target API
# ===================================================================

class TestExplorationTarget:
    """Tests for get_next_exploration_target."""

    def setup_method(self):
        _cleanup()

    def _setup_three_rooms(self):
        """r1 -- r2 -- r3 chain layout."""
        rooms = [
            _room("r1", 0, 0, 5, 5),
            _room("r2", 7, 0, 12, 5),
            _room("r3", 14, 0, 19, 5),
        ]
        doors = [_door(6, 2), _door(13, 2)]
        build_room_graph(MATCH, rooms, doors)
        init_room_discovery(MATCH, ["a"])

    def test_all_undiscovered_picks_closest(self):
        self._setup_three_rooms()
        # Standing at (2,2), closest room center is r1 (2,2), but r1 is undiscovered
        target = get_next_exploration_target(MATCH, "a", (2, 2))
        assert target is not None
        # All are priority 3 (deep unknown, none adjacent to known)
        # r1 center=(2,2) dist=0; closest
        assert target["room_id"] == "r1"

    def test_prefers_discovered_uncleared_over_undiscovered(self):
        self._setup_three_rooms()
        # Discover r1 (but don't clear it)
        update_room_discovery(MATCH, "a", {(2, 2)})

        # Standing near r3 center (16,2)
        target = get_next_exploration_target(MATCH, "a", (16, 2))
        assert target is not None
        # r1 is discovered-uncleared (priority 1), r2 is frontier (priority 2), r3 is unknown
        # Priority 1 wins regardless of distance
        assert target["room_id"] == "r1"
        assert target["priority"] == 1

    def test_prefers_frontier_over_deep_unknown(self):
        self._setup_three_rooms()
        # Discover and clear r1
        update_room_discovery(MATCH, "a", {(2, 2)})
        update_room_clearance(MATCH, "a", {}, {})

        # Now r2 is frontier (adjacent to cleared r1), r3 is deep unknown
        target = get_next_exploration_target(MATCH, "a", (2, 2))
        assert target is not None
        assert target["room_id"] == "r2"
        assert target["priority"] == 2

    def test_returns_none_when_all_cleared(self):
        rooms = [_room("r1", 0, 0, 5, 5)]
        build_room_graph(MATCH, rooms, [], [])
        init_room_discovery(MATCH, ["a"])
        update_room_discovery(MATCH, "a", {(2, 2)})
        update_room_clearance(MATCH, "a", {}, {})

        target = get_next_exploration_target(MATCH, "a", (2, 2))
        assert target is None

    def test_entrance_points_to_door(self):
        self._setup_three_rooms()
        # Discover and clear r1
        update_room_discovery(MATCH, "a", {(2, 2)})
        update_room_clearance(MATCH, "a", {}, {})

        # Target should be r2, entrance should be the door at (6,2)
        target = get_next_exploration_target(MATCH, "a", (2, 2))
        assert target is not None
        assert target["room_id"] == "r2"
        assert target["entrance"] == (6, 2)

    def test_no_rooms_returns_none(self):
        build_room_graph(MATCH, [], [])
        init_room_discovery(MATCH, ["a"])
        target = get_next_exploration_target(MATCH, "a", (5, 5))
        assert target is None

    def test_closest_within_same_priority(self):
        """When multiple rooms share the same priority, pick the closest."""
        rooms = [
            _room("r1", 0, 0, 5, 5),        # center=(2,2)
            _room("r2", 7, 0, 12, 5),       # center=(9,2)
            _room("r3", 0, 7, 5, 12),       # center=(2,9)
        ]
        # No doors — all disconnected, all deep unknown (priority 3)
        build_room_graph(MATCH, rooms, [])
        init_room_discovery(MATCH, ["a"])

        # Standing at (8, 2) — closest center is r2 (9,2) at dist 1
        target = get_next_exploration_target(MATCH, "a", (8, 2))
        assert target is not None
        assert target["room_id"] == "r2"


# ===================================================================
# Helpers
# ===================================================================

class TestHelpers:
    """Tests for get_current_room, get_exploration_progress, clear."""

    def setup_method(self):
        _cleanup()

    def test_get_current_room_inside(self):
        rooms = [_room("r1", 0, 0, 5, 5)]
        build_room_graph(MATCH, rooms, [])

        result = get_current_room(MATCH, 3, 3)
        assert result is not None
        assert result["room_id"] == "r1"

    def test_get_current_room_outside(self):
        rooms = [_room("r1", 0, 0, 5, 5)]
        build_room_graph(MATCH, rooms, [])

        result = get_current_room(MATCH, 10, 10)
        assert result is None

    def test_get_current_room_on_boundary(self):
        rooms = [_room("r1", 0, 0, 5, 5)]
        build_room_graph(MATCH, rooms, [])

        # On the boundary edge — should be inside
        result = get_current_room(MATCH, 5, 5)
        assert result is not None
        assert result["room_id"] == "r1"

    def test_exploration_progress_all_undiscovered(self):
        rooms = [_room("r1", 0, 0, 5, 5), _room("r2", 7, 0, 12, 5)]
        build_room_graph(MATCH, rooms, [])
        init_room_discovery(MATCH, ["a"])

        prog = get_exploration_progress(MATCH, "a")
        assert prog["total_rooms"] == 2
        assert prog["discovered_rooms"] == 0
        assert prog["cleared_rooms"] == 0
        assert prog["exploration_pct"] == 0.0

    def test_exploration_progress_partial(self):
        rooms = [_room("r1", 0, 0, 5, 5), _room("r2", 7, 0, 12, 5)]
        build_room_graph(MATCH, rooms, [])
        init_room_discovery(MATCH, ["a"])

        update_room_discovery(MATCH, "a", {(2, 2)})  # Discover r1
        prog = get_exploration_progress(MATCH, "a")
        assert prog["discovered_rooms"] == 1
        assert prog["exploration_pct"] == 50.0

    def test_exploration_progress_fully_cleared(self):
        rooms = [_room("r1", 0, 0, 5, 5)]
        build_room_graph(MATCH, rooms, [])
        init_room_discovery(MATCH, ["a"])
        update_room_discovery(MATCH, "a", {(2, 2)})
        update_room_clearance(MATCH, "a", {}, {})

        prog = get_exploration_progress(MATCH, "a")
        assert prog["total_rooms"] == 1
        assert prog["discovered_rooms"] == 1
        assert prog["cleared_rooms"] == 1
        assert prog["exploration_pct"] == 100.0
        assert prog["clearance_pct"] == 100.0

    def test_exploration_progress_no_rooms(self):
        prog = get_exploration_progress(MATCH, "a")
        assert prog["total_rooms"] == 0

    def test_clear_exploration_state(self):
        rooms = [_room("r1", 0, 0, 5, 5)]
        build_room_graph(MATCH, rooms, [])
        init_room_discovery(MATCH, ["a"])

        clear_exploration_state(MATCH)

        assert get_room_graph(MATCH) == {}
        assert get_room_discovery(MATCH, "a") == {}
        assert get_room_info(MATCH) == {}

    def test_clear_all_exploration_state(self):
        rooms = [_room("r1", 0, 0, 5, 5)]
        build_room_graph("m1", rooms, [])
        build_room_graph("m2", rooms, [])
        init_room_discovery("m1", ["a"])
        init_room_discovery("m2", ["a"])

        clear_exploration_state()  # No match_id → clear all
        assert get_room_graph("m1") == {}
        assert get_room_graph("m2") == {}
