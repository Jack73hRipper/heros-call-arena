"""
Tests for the Smart Spawn System (Phase 3, Feature 2).

Validates:
- Team spawns land inside designated zones
- Teammates are adjacent (Chebyshev ≤ 2)
- Opposing teams are separated (≥ 5 tiles between zones)
- FFA spawns are spread apart (≥ 5 tiles preferred)
- No spawn lands on an obstacle
- No two players share a position
- BFS fallback works when preferred spots are blocked
- System works across all 9 maps
"""

from __future__ import annotations

import pytest

from app.core.spawn import (
    assign_spawns,
    compute_ffa_spawns,
    compute_team_spawns,
    find_nearest_valid,
    validate_spawn,
    _chebyshev_distance,
    _default_spawn_zones,
    _parse_obstacles,
)
from app.core.map_loader import load_map


# ---- Helpers ----


ALL_MAP_IDS = [
    "open_arena_small",
    "arena_classic",
    "open_arena",
    "maze",
    "islands",
    "open_arena_large",
    "maze_large",
    "islands_large",
    "test_xl",
]


def _build_simple_map(width: int = 15, height: int = 15, obstacles=None):
    """Build a minimal map dict for unit tests."""
    obs = obstacles or []
    return {
        "width": width,
        "height": height,
        "obstacles": [{"x": x, "y": y} for x, y in obs],
        "spawn_zones": {
            "a": {"x_min": 0, "y_min": 0, "x_max": 3, "y_max": 3},
            "b": {"x_min": 11, "y_min": 11, "x_max": 14, "y_max": 14},
            "c": {"x_min": 11, "y_min": 0, "x_max": 14, "y_max": 3},
            "d": {"x_min": 0, "y_min": 11, "x_max": 3, "y_max": 14},
        },
        "ffa_points": [
            {"x": 1, "y": 1},
            {"x": 13, "y": 13},
            {"x": 13, "y": 1},
            {"x": 1, "y": 13},
            {"x": 7, "y": 1},
            {"x": 7, "y": 13},
            {"x": 1, "y": 7},
            {"x": 13, "y": 7},
        ],
    }


# ---- validate_spawn ----


class TestValidateSpawn:
    def test_valid_tile(self):
        assert validate_spawn(5, 5, set(), set(), 15, 15) is True

    def test_out_of_bounds_negative(self):
        assert validate_spawn(-1, 0, set(), set(), 15, 15) is False

    def test_out_of_bounds_over(self):
        assert validate_spawn(15, 0, set(), set(), 15, 15) is False

    def test_on_obstacle(self):
        assert validate_spawn(3, 3, {(3, 3)}, set(), 15, 15) is False

    def test_on_occupied(self):
        assert validate_spawn(5, 5, set(), {(5, 5)}, 15, 15) is False


# ---- find_nearest_valid ----


class TestFindNearestValid:
    def test_target_is_valid(self):
        pos = find_nearest_valid(5, 5, set(), set(), 15, 15)
        assert pos == (5, 5)

    def test_target_blocked_finds_neighbor(self):
        obstacles = {(5, 5)}
        pos = find_nearest_valid(5, 5, obstacles, set(), 15, 15)
        assert pos is not None
        assert pos != (5, 5)
        assert _chebyshev_distance(pos, (5, 5)) == 1

    def test_surrounded_by_obstacles(self):
        # Block a 3x3 area around (5,5), BFS should find tile further out
        obstacles = {(x, y) for x in range(4, 7) for y in range(4, 7)}
        pos = find_nearest_valid(5, 5, obstacles, set(), 15, 15)
        assert pos is not None
        assert pos not in obstacles


# ---- Team-Based Spawning ----


class TestTeamSpawns:
    def test_basic_two_teams(self):
        map_data = _build_simple_map()
        rosters = {"a": ["p1", "p2"], "b": ["p3", "p4"]}
        result = assign_spawns(rosters, map_data, is_ffa=False)

        assert len(result) == 4
        # All positions unique
        positions = list(result.values())
        assert len(set(positions)) == 4

    def test_teammates_are_adjacent(self):
        map_data = _build_simple_map()
        rosters = {"a": ["p1", "p2", "p3"], "b": ["p4", "p5"]}
        result = assign_spawns(rosters, map_data, is_ffa=False)

        # Team A members should all be within Chebyshev distance 2 of each other
        team_a_pos = [result["p1"], result["p2"], result["p3"]]
        for i in range(len(team_a_pos)):
            for j in range(i + 1, len(team_a_pos)):
                dist = _chebyshev_distance(team_a_pos[i], team_a_pos[j])
                assert dist <= 2, (
                    f"Teammates {team_a_pos[i]} and {team_a_pos[j]} too far apart: {dist}"
                )

    def test_teams_in_correct_zones(self):
        map_data = _build_simple_map()
        zones = map_data["spawn_zones"]
        rosters = {"a": ["p1", "p2"], "b": ["p3", "p4"]}
        result = assign_spawns(rosters, map_data, is_ffa=False)

        # Team A should be in zone A
        for pid in ["p1", "p2"]:
            x, y = result[pid]
            z = zones["a"]
            assert z["x_min"] <= x <= z["x_max"], f"{pid} at {x},{y} outside zone A x"
            assert z["y_min"] <= y <= z["y_max"], f"{pid} at {x},{y} outside zone A y"

        # Team B should be in zone B
        for pid in ["p3", "p4"]:
            x, y = result[pid]
            z = zones["b"]
            assert z["x_min"] <= x <= z["x_max"], f"{pid} at {x},{y} outside zone B x"
            assert z["y_min"] <= y <= z["y_max"], f"{pid} at {x},{y} outside zone B y"

    def test_opposing_teams_separated(self):
        map_data = _build_simple_map()
        rosters = {"a": ["p1", "p2"], "b": ["p3", "p4"]}
        result = assign_spawns(rosters, map_data, is_ffa=False)

        for a_pid in ["p1", "p2"]:
            for b_pid in ["p3", "p4"]:
                dist = _chebyshev_distance(result[a_pid], result[b_pid])
                assert dist >= 5, (
                    f"Teams too close: {a_pid}@{result[a_pid]} vs "
                    f"{b_pid}@{result[b_pid]}, dist={dist}"
                )

    def test_no_obstacle_overlap(self):
        obs = [(1, 1), (2, 2), (0, 0)]
        map_data = _build_simple_map(obstacles=obs)
        rosters = {"a": ["p1", "p2"]}
        result = assign_spawns(rosters, map_data, is_ffa=False)

        obstacle_set = set(obs)
        for pid, pos in result.items():
            assert pos not in obstacle_set, f"{pid} spawned on obstacle at {pos}"

    def test_no_duplicate_positions(self):
        map_data = _build_simple_map()
        rosters = {"a": ["p1", "p2", "p3", "p4"], "b": ["p5", "p6", "p7", "p8"]}
        result = assign_spawns(rosters, map_data, is_ffa=False)

        positions = list(result.values())
        assert len(set(positions)) == len(positions), "Duplicate spawn positions found"

    def test_four_teams(self):
        map_data = _build_simple_map()
        rosters = {"a": ["p1", "p2"], "b": ["p3", "p4"], "c": ["p5"], "d": ["p6"]}
        result = assign_spawns(rosters, map_data, is_ffa=False)

        assert len(result) == 6
        assert len(set(result.values())) == 6

    def test_single_player_team(self):
        map_data = _build_simple_map()
        rosters = {"a": ["p1"], "b": ["p2"]}
        result = assign_spawns(rosters, map_data, is_ffa=False)

        assert len(result) == 2
        # Should be far apart
        dist = _chebyshev_distance(result["p1"], result["p2"])
        assert dist >= 5


# ---- FFA Spawning ----


class TestFFASpawns:
    def test_basic_ffa(self):
        map_data = _build_simple_map()
        rosters = {"a": ["p1", "p2", "p3", "p4"]}
        result = assign_spawns(rosters, map_data, is_ffa=True)

        assert len(result) == 4
        assert len(set(result.values())) == 4

    def test_ffa_minimum_distance(self):
        map_data = _build_simple_map()
        rosters = {"a": ["p1", "p2", "p3", "p4"]}
        result = assign_spawns(rosters, map_data, is_ffa=True)

        positions = list(result.values())
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dist = _chebyshev_distance(positions[i], positions[j])
                assert dist >= 5, (
                    f"FFA players too close: {positions[i]} and {positions[j]}, dist={dist}"
                )

    def test_ffa_no_obstacles(self):
        obs = [(1, 1), (13, 13)]
        map_data = _build_simple_map(obstacles=obs)
        rosters = {"a": ["p1", "p2", "p3", "p4"]}
        result = assign_spawns(rosters, map_data, is_ffa=True)

        obstacle_set = set(obs)
        for pid, pos in result.items():
            assert pos not in obstacle_set, f"{pid} spawned on obstacle at {pos}"

    def test_ffa_8_players(self):
        map_data = _build_simple_map()
        rosters = {"a": [f"p{i}" for i in range(8)]}
        result = assign_spawns(rosters, map_data, is_ffa=True)

        assert len(result) == 8
        assert len(set(result.values())) == 8

    def test_ffa_no_duplicate_positions(self):
        map_data = _build_simple_map()
        rosters = {"a": [f"p{i}" for i in range(8)]}
        result = assign_spawns(rosters, map_data, is_ffa=True)

        positions = list(result.values())
        assert len(set(positions)) == len(positions)


# ---- Real Map Integration ----


class TestRealMaps:
    """Test smart spawn against all 9 actual map configs."""

    @pytest.mark.parametrize("map_id", ALL_MAP_IDS)
    def test_team_spawn_no_overlaps(self, map_id):
        map_data = load_map(map_id)
        rosters = {"a": ["p1", "p2"], "b": ["p3", "p4"]}
        result = assign_spawns(rosters, map_data, is_ffa=False)

        positions = list(result.values())
        assert len(set(positions)) == len(positions), f"Overlapping spawns on {map_id}"

    @pytest.mark.parametrize("map_id", ALL_MAP_IDS)
    def test_team_spawn_not_on_obstacles(self, map_id):
        map_data = load_map(map_id)
        obstacles = _parse_obstacles(map_data)
        rosters = {"a": ["p1", "p2"], "b": ["p3", "p4"]}
        result = assign_spawns(rosters, map_data, is_ffa=False)

        for pid, pos in result.items():
            assert pos not in obstacles, f"{pid} on obstacle at {pos} on map {map_id}"

    @pytest.mark.parametrize("map_id", ALL_MAP_IDS)
    def test_team_spawn_in_bounds(self, map_id):
        map_data = load_map(map_id)
        w, h = map_data["width"], map_data["height"]
        rosters = {"a": ["p1", "p2"], "b": ["p3", "p4"]}
        result = assign_spawns(rosters, map_data, is_ffa=False)

        for pid, (x, y) in result.items():
            assert 0 <= x < w, f"{pid} x={x} out of bounds on {map_id}"
            assert 0 <= y < h, f"{pid} y={y} out of bounds on {map_id}"

    @pytest.mark.parametrize("map_id", ALL_MAP_IDS)
    def test_ffa_spawn_no_overlaps(self, map_id):
        map_data = load_map(map_id)
        rosters = {"a": [f"p{i}" for i in range(8)]}
        result = assign_spawns(rosters, map_data, is_ffa=True)

        positions = list(result.values())
        assert len(set(positions)) == len(positions), f"Overlapping FFA spawns on {map_id}"

    @pytest.mark.parametrize("map_id", ALL_MAP_IDS)
    def test_ffa_spawn_not_on_obstacles(self, map_id):
        map_data = load_map(map_id)
        obstacles = _parse_obstacles(map_data)
        rosters = {"a": [f"p{i}" for i in range(8)]}
        result = assign_spawns(rosters, map_data, is_ffa=True)

        for pid, pos in result.items():
            assert pos not in obstacles, f"{pid} on obstacle at {pos} on {map_id}"

    @pytest.mark.parametrize("map_id", ALL_MAP_IDS)
    def test_team_spawn_opposing_teams_separated(self, map_id):
        map_data = load_map(map_id)
        rosters = {"a": ["p1", "p2"], "b": ["p3", "p4"]}
        result = assign_spawns(rosters, map_data, is_ffa=False)

        for a_pid in ["p1", "p2"]:
            for b_pid in ["p3", "p4"]:
                dist = _chebyshev_distance(result[a_pid], result[b_pid])
                assert dist >= 5, (
                    f"Teams too close on {map_id}: {a_pid}@{result[a_pid]} vs "
                    f"{b_pid}@{result[b_pid]}, dist={dist}"
                )

    @pytest.mark.parametrize("map_id", ALL_MAP_IDS)
    def test_team_spawn_teammates_compact(self, map_id):
        map_data = load_map(map_id)
        rosters = {"a": ["p1", "p2", "p3"], "b": ["p4", "p5"]}
        result = assign_spawns(rosters, map_data, is_ffa=False)

        # Team A: all within Chebyshev 2 of each other
        team_a_pos = [result[f"p{i}"] for i in range(1, 4)]
        for i in range(len(team_a_pos)):
            for j in range(i + 1, len(team_a_pos)):
                dist = _chebyshev_distance(team_a_pos[i], team_a_pos[j])
                assert dist <= 2, (
                    f"Teammates too far on {map_id}: {team_a_pos[i]} and "
                    f"{team_a_pos[j]}, dist={dist}"
                )

    @pytest.mark.parametrize("map_id", ALL_MAP_IDS)
    def test_full_8_player_team_match(self, map_id):
        """4v4 team match — all 8 positions valid."""
        map_data = load_map(map_id)
        obstacles = _parse_obstacles(map_data)
        w, h = map_data["width"], map_data["height"]
        rosters = {
            "a": ["p1", "p2", "p3", "p4"],
            "b": ["p5", "p6", "p7", "p8"],
        }
        result = assign_spawns(rosters, map_data, is_ffa=False)

        assert len(result) == 8
        positions = list(result.values())
        assert len(set(positions)) == 8, "Duplicate positions"
        for pos in positions:
            assert pos not in obstacles, f"On obstacle: {pos}"
            assert 0 <= pos[0] < w and 0 <= pos[1] < h, f"Out of bounds: {pos}"


# ---- Default Zones ----


class TestDefaultZones:
    def test_default_zones_12x12(self):
        zones = _default_spawn_zones(12, 12)
        assert set(zones.keys()) == {"a", "b", "c", "d"}
        # Zone A should be top-left
        assert zones["a"]["x_min"] == 0
        assert zones["a"]["y_min"] == 0

    def test_default_zones_25x25(self):
        zones = _default_spawn_zones(25, 25)
        # Zone B should be bottom-right
        assert zones["b"]["x_max"] == 24
        assert zones["b"]["y_max"] == 24

    def test_zone_separation(self):
        """Opposing team zones should have ≥5 tiles between them on any map size."""
        for size in [12, 15, 20, 25]:
            zones = _default_spawn_zones(size, size)
            a_max_x = zones["a"]["x_max"]
            b_min_x = zones["b"]["x_min"]
            gap = b_min_x - a_max_x - 1
            assert gap >= 5, f"Zone gap too small on {size}x{size}: {gap}"
