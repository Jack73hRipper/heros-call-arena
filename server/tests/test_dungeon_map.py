"""
Tests for Phase 4B-1 — Dungeon Map Format & Server Foundation.

Validates:
- Dungeon map loads correctly with rooms, corridors, doors, chests
- get_doors() returns correct door positions and initial states
- get_chests() returns correct chest positions
- get_room_definitions() returns all named rooms with bounds
- MatchType.DUNGEON creates a valid match
- Party spawns in start room at valid spawn tiles
- Door/chest state dicts initialized on match creation
- Existing arena maps load without errors (no regression)
- Tile-grid obstacle generation works correctly
"""

from __future__ import annotations

import pytest

from app.core.map_loader import (
    load_map,
    get_obstacles,
    get_spawn_points,
    get_doors,
    get_chests,
    get_room_definitions,
    get_tiles,
    get_map_dimensions,
    is_dungeon_map,
)
from app.core.match_manager import (
    create_match,
    start_match,
    get_match,
    get_match_players,
    get_dungeon_state,
)
from app.models.match import MatchConfig, MatchType, MatchStatus
from app.models.actions import ActionType


# ---- Constants ----

DUNGEON_MAP = "dungeon_test"

ARENA_MAPS = [
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


# ---- Helpers ----

def _clean_state():
    """Clear in-memory stores between tests."""
    from app.core import match_manager, map_loader
    match_manager._active_matches.clear()
    match_manager._player_states.clear()
    match_manager._action_queues.clear()
    match_manager._fov_cache.clear()
    match_manager._lobby_chat.clear()
    match_manager._class_selections.clear()
    # Clear map cache so each test gets a fresh load
    map_loader._loaded_maps.clear()


# ---- Map Loading Tests ----


class TestDungeonMapLoading:
    def setup_method(self):
        _clean_state()

    def test_dungeon_map_loads(self):
        """Dungeon map loads without error."""
        data = load_map(DUNGEON_MAP)
        assert data["name"] == "Dungeon Test"
        assert data["width"] == 20
        assert data["height"] == 20

    def test_dungeon_map_type(self):
        """is_dungeon_map returns True for dungeon, False for arena."""
        assert is_dungeon_map(DUNGEON_MAP) is True
        assert is_dungeon_map("arena_classic") is False

    def test_map_dimensions(self):
        w, h = get_map_dimensions(DUNGEON_MAP)
        assert w == 20
        assert h == 20

    def test_tiles_grid_exists(self):
        """Dungeon map has a tiles grid with correct dimensions."""
        tiles = get_tiles(DUNGEON_MAP)
        assert tiles is not None
        assert len(tiles) == 20  # 20 rows
        assert all(len(row) == 20 for row in tiles)  # 20 cols each

    def test_tiles_grid_none_for_arena(self):
        """Arena maps return None for get_tiles."""
        tiles = get_tiles("arena_classic")
        assert tiles is None


class TestDungeonDoors:
    def setup_method(self):
        _clean_state()

    def test_get_doors_returns_all(self):
        """get_doors() returns all 9 doors from dungeon map."""
        doors = get_doors(DUNGEON_MAP)
        assert len(doors) == 9

    def test_door_positions(self):
        """Doors are at expected positions."""
        doors = get_doors(DUNGEON_MAP)
        positions = {(d["x"], d["y"]) for d in doors}
        expected = {
            (6, 3), (9, 3),     # horizontal corridor start↔enemy1
            (3, 6), (3, 9),     # vertical corridor start↔loot
            (12, 6), (12, 9),   # vertical corridor enemy1↔enemy2
            (6, 12), (9, 12),   # horizontal corridor loot↔enemy2
            (13, 15),           # corridor enemy2↔boss
        }
        assert positions == expected

    def test_door_initial_state(self):
        """All doors start closed."""
        doors = get_doors(DUNGEON_MAP)
        assert all(d["state"] == "closed" for d in doors)

    def test_doors_in_tiles_grid(self):
        """Door positions in doors array match 'D' tiles in the grid."""
        doors = get_doors(DUNGEON_MAP)
        tiles = get_tiles(DUNGEON_MAP)
        for d in doors:
            assert tiles[d["y"]][d["x"]] == "D", f"Door at ({d['x']},{d['y']}) not 'D' in tiles"

    def test_doors_empty_for_arena(self):
        """Arena maps return empty doors list."""
        doors = get_doors("arena_classic")
        assert doors == []


class TestDungeonChests:
    def setup_method(self):
        _clean_state()

    def test_get_chests_returns_all(self):
        """get_chests() returns all 3 chests from dungeon map."""
        chests = get_chests(DUNGEON_MAP)
        assert len(chests) == 3

    def test_chest_positions(self):
        """Chests are at expected positions in loot room."""
        chests = get_chests(DUNGEON_MAP)
        positions = {(c["x"], c["y"]) for c in chests}
        expected = {(2, 12), (4, 12), (3, 13)}
        assert positions == expected

    def test_chests_in_tiles_grid(self):
        """Chest positions match 'X' tiles in the grid."""
        chests = get_chests(DUNGEON_MAP)
        tiles = get_tiles(DUNGEON_MAP)
        for c in chests:
            assert tiles[c["y"]][c["x"]] == "X", f"Chest at ({c['x']},{c['y']}) not 'X' in tiles"

    def test_chests_empty_for_arena(self):
        """Arena maps return empty chests list."""
        chests = get_chests("arena_classic")
        assert chests == []


class TestDungeonRooms:
    def setup_method(self):
        _clean_state()

    def test_room_count(self):
        """Dungeon has 5 rooms."""
        rooms = get_room_definitions(DUNGEON_MAP)
        assert len(rooms) == 5

    def test_room_ids(self):
        """All expected room IDs present."""
        rooms = get_room_definitions(DUNGEON_MAP)
        ids = {r["id"] for r in rooms}
        assert ids == {"start_room", "enemy_room_1", "loot_room", "enemy_room_2", "boss_room"}

    def test_room_purposes(self):
        """Rooms have correct purposes."""
        rooms = get_room_definitions(DUNGEON_MAP)
        purpose_map = {r["id"]: r["purpose"] for r in rooms}
        assert purpose_map["start_room"] == "spawn"
        assert purpose_map["enemy_room_1"] == "enemy"
        assert purpose_map["enemy_room_2"] == "enemy"
        assert purpose_map["loot_room"] == "loot"
        assert purpose_map["boss_room"] == "boss"

    def test_room_bounds(self):
        """Each room has valid bounds with x_min < x_max and y_min < y_max."""
        rooms = get_room_definitions(DUNGEON_MAP)
        for room in rooms:
            b = room["bounds"]
            assert b["x_min"] < b["x_max"], f"Room {room['id']} x bounds invalid"
            assert b["y_min"] < b["y_max"], f"Room {room['id']} y bounds invalid"

    def test_enemy_spawn_points_in_rooms(self):
        """Enemy spawns fall within their room bounds."""
        rooms = get_room_definitions(DUNGEON_MAP)
        for room in rooms:
            if "enemy_spawns" not in room:
                continue
            b = room["bounds"]
            for sp in room["enemy_spawns"]:
                assert b["x_min"] <= sp["x"] <= b["x_max"], \
                    f"Enemy spawn ({sp['x']},{sp['y']}) outside room {room['id']} x"
                assert b["y_min"] <= sp["y"] <= b["y_max"], \
                    f"Enemy spawn ({sp['x']},{sp['y']}) outside room {room['id']} y"

    def test_rooms_empty_for_arena(self):
        """Arena maps return empty rooms list."""
        rooms = get_room_definitions("arena_classic")
        assert rooms == []


class TestDungeonObstacles:
    def setup_method(self):
        _clean_state()

    def test_obstacles_generated_from_tiles(self):
        """Dungeon obstacles derived from W and D tiles in the grid."""
        obstacles = get_obstacles(DUNGEON_MAP)
        assert len(obstacles) > 0

    def test_walls_are_obstacles(self):
        """All 'W' tiles are in the obstacles set."""
        tiles = get_tiles(DUNGEON_MAP)
        obstacles = get_obstacles(DUNGEON_MAP)
        for y, row in enumerate(tiles):
            for x, ch in enumerate(row):
                if ch == "W":
                    assert (x, y) in obstacles, f"Wall ({x},{y}) not in obstacles"

    def test_doors_are_obstacles(self):
        """All 'D' tiles (closed doors) are in obstacles set."""
        doors = get_doors(DUNGEON_MAP)
        obstacles = get_obstacles(DUNGEON_MAP)
        for d in doors:
            assert (d["x"], d["y"]) in obstacles, \
                f"Door ({d['x']},{d['y']}) not in obstacles"

    def test_floors_not_obstacles(self):
        """Floor, corridor, spawn, and chest tiles are NOT obstacles."""
        tiles = get_tiles(DUNGEON_MAP)
        obstacles = get_obstacles(DUNGEON_MAP)
        passable = {"F", "C", "S", "X"}
        for y, row in enumerate(tiles):
            for x, ch in enumerate(row):
                if ch in passable:
                    assert (x, y) not in obstacles, \
                        f"Passable tile ({x},{y}) = '{ch}' found in obstacles"

    def test_spawn_points_not_on_obstacles(self):
        """All spawn points are on walkable tiles."""
        spawns = get_spawn_points(DUNGEON_MAP)
        obstacles = get_obstacles(DUNGEON_MAP)
        for sx, sy in spawns:
            assert (sx, sy) not in obstacles, f"Spawn ({sx},{sy}) is on an obstacle"


# ---- Arena Regression Tests ----


class TestArenaRegression:
    """Ensure all existing arena maps still load and work correctly."""

    def setup_method(self):
        _clean_state()

    @pytest.mark.parametrize("map_id", ARENA_MAPS)
    def test_arena_map_loads(self, map_id):
        data = load_map(map_id)
        assert data["width"] > 0
        assert data["height"] > 0

    @pytest.mark.parametrize("map_id", ARENA_MAPS)
    def test_arena_obstacles_from_array(self, map_id):
        """Arena maps still use the obstacles array (not tiles grid)."""
        obstacles = get_obstacles(map_id)
        # All arena maps have at least some obstacles
        assert isinstance(obstacles, set)

    @pytest.mark.parametrize("map_id", ARENA_MAPS)
    def test_arena_no_dungeon_data(self, map_id):
        """Arena maps have no doors, chests, or rooms."""
        assert get_doors(map_id) == []
        assert get_chests(map_id) == []
        assert get_room_definitions(map_id) == []
        assert is_dungeon_map(map_id) is False


# ---- Match Creation Tests ----


class TestDungeonMatchCreation:
    def setup_method(self):
        _clean_state()

    def test_create_dungeon_match(self):
        """Can create a match with dungeon map and DUNGEON type."""
        config = MatchConfig(
            map_id=DUNGEON_MAP,
            match_type=MatchType.DUNGEON,
            max_players=5,
        )
        match, host = create_match("Hero", config=config)
        assert match.config.map_id == DUNGEON_MAP
        assert match.config.match_type == MatchType.DUNGEON
        assert host.username == "Hero"

    def test_dungeon_spawn_in_start_room(self):
        """Host spawns at a valid spawn point inside the start room."""
        config = MatchConfig(
            map_id=DUNGEON_MAP,
            match_type=MatchType.DUNGEON,
            max_players=5,
        )
        match, host = create_match("Hero", config=config)
        # Start room bounds: x_min=1, y_min=1, x_max=5, y_max=5
        pos = host.position
        assert 1 <= pos.x <= 5, f"Spawn x={pos.x} outside start room"
        assert 1 <= pos.y <= 5, f"Spawn y={pos.y} outside start room"

    def test_dungeon_state_initialized_on_start(self):
        """Door/chest states populated when dungeon match starts."""
        config = MatchConfig(
            map_id=DUNGEON_MAP,
            match_type=MatchType.DUNGEON,
            max_players=5,
        )
        match, host = create_match("Hero", config=config)

        # Set ready and start
        from app.core.match_manager import set_player_ready
        set_player_ready(match.match_id, host.player_id, True)
        started = start_match(match.match_id)
        assert started is True

        # Verify dungeon state
        updated_match = get_match(match.match_id)
        assert len(updated_match.door_states) == 9
        assert all(v == "closed" for v in updated_match.door_states.values())
        assert len(updated_match.chest_states) == 3
        assert all(v == "unopened" for v in updated_match.chest_states.values())

    def test_dungeon_state_key_format(self):
        """Door/chest state keys are 'x,y' strings."""
        config = MatchConfig(
            map_id=DUNGEON_MAP,
            match_type=MatchType.DUNGEON,
            max_players=5,
        )
        match, host = create_match("Hero", config=config)
        from app.core.match_manager import set_player_ready
        set_player_ready(match.match_id, host.player_id, True)
        start_match(match.match_id)

        updated_match = get_match(match.match_id)
        # Check a known door position
        assert "6,3" in updated_match.door_states
        assert "13,15" in updated_match.door_states
        # Check a known chest position
        assert "2,12" in updated_match.chest_states

    def test_get_dungeon_state_helper(self):
        """get_dungeon_state returns door + chest state dict."""
        config = MatchConfig(
            map_id=DUNGEON_MAP,
            match_type=MatchType.DUNGEON,
            max_players=5,
        )
        match, host = create_match("Hero", config=config)
        from app.core.match_manager import set_player_ready
        set_player_ready(match.match_id, host.player_id, True)
        start_match(match.match_id)

        state = get_dungeon_state(match.match_id)
        assert state is not None
        assert "door_states" in state
        assert "chest_states" in state

    def test_get_dungeon_state_none_for_arena(self):
        """get_dungeon_state returns None for arena matches."""
        match, host = create_match("Warrior")
        assert get_dungeon_state(match.match_id) is None

    def test_arena_match_no_dungeon_state(self):
        """Arena match start does not populate door/chest states."""
        match, host = create_match("Warrior")
        from app.core.match_manager import set_player_ready
        set_player_ready(match.match_id, host.player_id, True)
        start_match(match.match_id)
        updated = get_match(match.match_id)
        assert updated.door_states == {}
        assert updated.chest_states == {}


# ---- Enum Tests ----


class TestNewEnums:
    def test_action_type_interact(self):
        assert ActionType.INTERACT == "interact"
        assert ActionType.INTERACT.value == "interact"

    def test_action_type_loot(self):
        assert ActionType.LOOT == "loot"
        assert ActionType.LOOT.value == "loot"

    def test_match_type_dungeon(self):
        assert MatchType.DUNGEON == "dungeon"
        assert MatchType.DUNGEON.value == "dungeon"

    def test_existing_action_types_unchanged(self):
        """Original action types still work."""
        assert ActionType.MOVE == "move"
        assert ActionType.ATTACK == "attack"
        assert ActionType.RANGED_ATTACK == "ranged_attack"
        assert ActionType.WAIT == "wait"

    def test_existing_match_types_unchanged(self):
        """Original match types still work."""
        assert MatchType.PVP == "pvp"
        assert MatchType.SOLO_PVE == "solo_pve"
        assert MatchType.MIXED == "mixed"
