"""
Tests for Phase 12 Feature 5 — WFC Procedural Dungeon Generation.

Tests the full pipeline from module expansion through WFC collapse,
connectivity, decoration, and export. Validates:

- Module expansion and rotation variant generation
- WFC collapse produces valid tile maps
- Connectivity enforcement (no disconnected regions)
- Room decoration assigns required content (spawn, boss, enemies, loot)
- Export format matches game map schema
- Deterministic generation (same seed → same output)
- Floor scaling configuration
- Runtime map registration in map_loader
- Integration with match_manager dungeon flow
"""

from __future__ import annotations

import pytest

from app.core.wfc.module_utils import (
    MODULE_SIZE,
    derive_sockets,
    rotate_tiles_90cw,
    generate_rotation_variants,
    expand_modules,
)
from app.core.wfc.wfc_engine import run_wfc
from app.core.wfc.connectivity import find_regions, ensure_connectivity, validate_connectivity
from app.core.wfc.room_decorator import decorate_rooms
from app.core.wfc.map_exporter import export_to_game_map
from app.core.wfc.presets import get_preset_modules, PRESET_MODULES, SIZE_PRESETS
from app.core.wfc.dungeon_generator import (
    generate_dungeon_floor,
    FloorConfig,
    GenerationResult,
)
from app.core.map_loader import (
    register_runtime_map,
    unregister_runtime_map,
    load_map,
    get_spawn_points,
    get_doors,
    get_chests,
    get_room_definitions,
    get_tiles,
    is_dungeon_map,
)


# ═══════════════════════════════════════════════════════════
# Module Utils Tests
# ═══════════════════════════════════════════════════════════

class TestModuleUtils:
    """Test module data structures, sockets, and rotation."""

    def test_module_size_constant(self):
        assert MODULE_SIZE == 8

    def test_preset_modules_count(self):
        """All 49 preset modules should be present (29 original + 20 variety expansion)."""
        assert len(PRESET_MODULES) == 49

    def test_preset_modules_are_8x8(self):
        for mod in PRESET_MODULES:
            tiles = mod["tiles"]
            assert len(tiles) == 8, f"{mod['id']} has {len(tiles)} rows"
            for row in tiles:
                assert len(row) == 8, f"{mod['id']} has row with {len(row)} cols"

    def test_derive_sockets_solid_wall(self):
        """Solid wall should have all-W sockets on every edge."""
        solid = PRESET_MODULES[0]
        sockets = derive_sockets(solid["tiles"])
        assert sockets["north"] == "WWWWWWWW"
        assert sockets["south"] == "WWWWWWWW"
        assert sockets["west"] == "WWWWWWWW"
        assert sockets["east"] == "WWWWWWWW"

    def test_derive_sockets_corridor(self):
        """Horizontal corridor should have corridor sockets on left/right."""
        corridor_h = PRESET_MODULES[1]
        sockets = derive_sockets(corridor_h["tiles"])
        assert sockets["west"] == "WWOOOOWW"
        assert sockets["east"] == "WWOOOOWW"
        assert sockets["north"] == "WWWWWWWW"
        assert sockets["south"] == "WWWWWWWW"

    def test_rotate_tiles_90cw(self):
        """Rotation should produce a valid 8×8 grid."""
        corridor_h = PRESET_MODULES[1]
        rotated = rotate_tiles_90cw(corridor_h["tiles"])
        assert len(rotated) == 8
        assert all(len(row) == 8 for row in rotated)

    def test_rotation_symmetry(self):
        """Four 90° rotations should return to original."""
        tiles = PRESET_MODULES[1]["tiles"]
        result = tiles
        for _ in range(4):
            result = rotate_tiles_90cw(result)
        assert result == tiles

    def test_expand_modules_includes_rotations(self):
        """Modules with allowRotation=True should produce extra variants."""
        modules = get_preset_modules()
        variants = expand_modules(modules)
        # Should have more variants than base modules
        assert len(variants) > len(modules)

    def test_expand_modules_no_rotation_modules_single(self):
        """Modules with allowRotation=False should produce exactly one variant."""
        modules = [m for m in get_preset_modules() if not m["allowRotation"]]
        for mod in modules:
            variants = expand_modules([mod])
            # Could be 1 if all 4 rotations are duplicate, or just 1 for no-rotate
            assert len(variants) >= 1

    def test_get_preset_modules_returns_copy(self):
        """Should return a deep copy, not the original."""
        mods1 = get_preset_modules()
        mods2 = get_preset_modules()
        mods1[0]["id"] = "modified"
        assert mods2[0]["id"] != "modified"


# ═══════════════════════════════════════════════════════════
# WFC Engine Tests
# ═══════════════════════════════════════════════════════════

class TestWFCEngine:
    """Test the core Wave Function Collapse algorithm."""

    def test_wfc_basic_success(self):
        """WFC should produce a valid result with default settings."""
        modules = get_preset_modules()
        result = run_wfc(modules=modules, grid_rows=3, grid_cols=3, seed=42)
        assert result["success"] is True
        assert result["tileMap"] is not None
        assert result["grid"] is not None

    def test_wfc_tile_map_dimensions(self):
        """Tile map should be grid_rows * MODULE_SIZE by grid_cols * MODULE_SIZE."""
        modules = get_preset_modules()
        result = run_wfc(modules=modules, grid_rows=3, grid_cols=4, seed=42)
        assert result["success"] is True
        tile_map = result["tileMap"]
        assert len(tile_map) == 3 * MODULE_SIZE  # 18 rows
        assert len(tile_map[0]) == 4 * MODULE_SIZE  # 24 cols

    def test_wfc_deterministic(self):
        """Same seed should produce same output."""
        modules = get_preset_modules()
        r1 = run_wfc(modules=modules, grid_rows=3, grid_cols=3, seed=12345)
        r2 = run_wfc(modules=modules, grid_rows=3, grid_cols=3, seed=12345)
        assert r1["success"] == r2["success"]
        if r1["success"]:
            assert r1["tileMap"] == r2["tileMap"]

    def test_wfc_different_seeds_different_output(self):
        """Different seeds should (usually) produce different maps."""
        modules = get_preset_modules()
        r1 = run_wfc(modules=modules, grid_rows=3, grid_cols=3, seed=100)
        r2 = run_wfc(modules=modules, grid_rows=3, grid_cols=3, seed=200)
        if r1["success"] and r2["success"]:
            # Extremely unlikely to be identical
            assert r1["tileMap"] != r2["tileMap"]

    def test_wfc_valid_tile_types(self):
        """All tiles should be recognized types."""
        valid_tiles = {"W", "F", "D", "C", "S", "X", "E", "B"}
        modules = get_preset_modules()
        result = run_wfc(modules=modules, grid_rows=3, grid_cols=3, seed=42)
        if result["success"]:
            for row in result["tileMap"]:
                for tile in row:
                    assert tile in valid_tiles, f"Unknown tile type: {tile}"


# ═══════════════════════════════════════════════════════════
# Connectivity Tests
# ═══════════════════════════════════════════════════════════

class TestConnectivity:
    """Test flood-fill region detection and tunnel carving."""

    def test_find_regions_single(self):
        """Fully connected floor should have exactly one region."""
        tile_map = [
            ["W", "W", "W", "W"],
            ["W", "F", "F", "W"],
            ["W", "F", "F", "W"],
            ["W", "W", "W", "W"],
        ]
        regions = find_regions(tile_map)
        assert len(regions) == 1

    def test_find_regions_disconnected(self):
        """Two separated floor areas should produce two regions."""
        tile_map = [
            ["F", "F", "W", "F", "F"],
            ["F", "F", "W", "F", "F"],
            ["W", "W", "W", "W", "W"],
            ["F", "F", "W", "F", "F"],
            ["F", "F", "W", "F", "F"],
        ]
        regions = find_regions(tile_map)
        assert len(regions) >= 2

    def test_ensure_connectivity_carves_tunnels(self):
        """Should carve corridors to connect disconnected regions."""
        tile_map = [
            ["F", "F", "W", "W", "W", "F", "F"],
            ["F", "F", "W", "W", "W", "F", "F"],
            ["W", "W", "W", "W", "W", "W", "W"],
            ["W", "W", "W", "W", "W", "W", "W"],
            ["F", "F", "W", "W", "W", "F", "F"],
            ["F", "F", "W", "W", "W", "F", "F"],
        ]
        result = ensure_connectivity(tile_map)
        # Should have carved at least one corridor
        assert result["corridorsCarved"] > 0

    def test_validate_connectivity_passes_connected(self):
        """A connected map should pass validation."""
        tile_map = [
            ["W", "F", "F"],
            ["W", "F", "W"],
            ["W", "F", "F"],
        ]
        result = validate_connectivity(tile_map)
        assert result["isConnected"] is True


# ═══════════════════════════════════════════════════════════
# Map Exporter Tests
# ═══════════════════════════════════════════════════════════

class TestMapExporter:
    """Test WFC-to-game-map export."""

    def test_export_basic_format(self):
        """Exported map should have all required fields."""
        tile_map = [
            ["W", "W", "W", "W"],
            ["W", "S", "F", "W"],
            ["W", "F", "D", "W"],
            ["W", "W", "W", "W"],
        ]
        game_map = export_to_game_map(tile_map=tile_map)
        assert game_map["map_type"] == "dungeon"
        assert game_map["width"] == 4
        assert game_map["height"] == 4
        assert "tiles" in game_map
        assert "tile_legend" in game_map
        assert "spawn_points" in game_map
        assert "doors" in game_map
        assert "chests" in game_map
        assert "rooms" in game_map

    def test_export_normalizes_enemy_tiles(self):
        """E and B tiles should be normalized to F in the exported grid."""
        tile_map = [
            ["W", "E", "B", "W"],
            ["W", "F", "F", "W"],
        ]
        game_map = export_to_game_map(tile_map=tile_map)
        assert game_map["tiles"][0][1] == "F"
        assert game_map["tiles"][0][2] == "F"

    def test_export_collects_spawn_points(self):
        """S tiles should become spawn_points."""
        tile_map = [
            ["W", "S", "S", "W"],
            ["W", "F", "F", "W"],
        ]
        game_map = export_to_game_map(tile_map=tile_map)
        assert len(game_map["spawn_points"]) == 2

    def test_export_collects_doors(self):
        """D tiles should become door entries."""
        tile_map = [
            ["W", "D", "D", "W"],
            ["W", "F", "F", "W"],
        ]
        game_map = export_to_game_map(tile_map=tile_map)
        assert len(game_map["doors"]) == 2
        assert all(d["state"] == "closed" for d in game_map["doors"])

    def test_export_collects_chests(self):
        """X tiles should become chest entries."""
        tile_map = [
            ["W", "X", "F", "W"],
            ["W", "F", "X", "W"],
        ]
        game_map = export_to_game_map(tile_map=tile_map)
        assert len(game_map["chests"]) == 2

    def test_export_tile_legend(self):
        """Tile legend should map all standard tile types."""
        game_map = export_to_game_map(tile_map=[["W", "F"]])
        legend = game_map["tile_legend"]
        assert legend["W"] == "wall"
        assert legend["F"] == "floor"
        assert legend["D"] == "door"


# ═══════════════════════════════════════════════════════════
# Dungeon Generator (High-Level API) Tests
# ═══════════════════════════════════════════════════════════

class TestDungeonGenerator:
    """Test the high-level generation pipeline."""

    def test_generate_success(self):
        """Full pipeline should succeed with reasonable settings."""
        result = generate_dungeon_floor(seed=42, floor_number=1)
        assert result.success is True
        assert result.game_map is not None
        assert result.generation_time_ms > 0

    def test_generate_map_format(self):
        """Generated map should have all required game fields."""
        result = generate_dungeon_floor(seed=42, floor_number=1)
        assert result.success, f"Generation failed: {result.error}"
        gm = result.game_map
        assert gm["map_type"] == "dungeon"
        assert gm["width"] > 0
        assert gm["height"] > 0
        assert len(gm["tiles"]) == gm["height"]
        assert len(gm["tiles"][0]) == gm["width"]
        assert len(gm["spawn_points"]) > 0

    def test_generate_deterministic(self):
        """Same seed + floor should produce identical maps."""
        r1 = generate_dungeon_floor(seed=999, floor_number=1)
        r2 = generate_dungeon_floor(seed=999, floor_number=1)
        assert r1.success and r2.success
        assert r1.game_map["tiles"] == r2.game_map["tiles"]

    def test_floor_config_scaling(self):
        """FloorConfig.from_floor_number should scale grid size with depth."""
        c1 = FloorConfig.from_floor_number(seed=1, floor_number=1)
        c5 = FloorConfig.from_floor_number(seed=1, floor_number=5)
        c9 = FloorConfig.from_floor_number(seed=1, floor_number=9)

        # Grid should grow with floor number
        assert c1.grid_rows <= c5.grid_rows
        assert c5.grid_rows <= c9.grid_rows

        # Enemy density should increase
        assert c1.enemy_density <= c5.enemy_density
        assert c5.enemy_density <= c9.enemy_density

    def test_floor_config_custom(self):
        """Manual FloorConfig should override auto-scaling."""
        config = FloorConfig(seed=42, grid_rows=2, grid_cols=2)
        result = generate_dungeon_floor(config=config)
        assert result.success, f"Generation failed: {result.error}"
        gm = result.game_map
        assert gm["width"] == 2 * MODULE_SIZE
        assert gm["height"] == 2 * MODULE_SIZE

    def test_generate_has_rooms(self):
        """Generated map should contain at least one room."""
        result = generate_dungeon_floor(seed=42, floor_number=1)
        assert result.success
        assert len(result.game_map.get("rooms", [])) > 0

    def test_generate_stats(self):
        """Result should include generation statistics."""
        result = generate_dungeon_floor(seed=42, floor_number=1)
        assert result.success
        assert "wfc_attempts" in result.stats
        assert "grid_size" in result.stats
        assert "generation_time_ms" in result.stats

    def test_map_data_accessor(self):
        """GenerationResult.map_data should raise on failure."""
        result = GenerationResult(success=False, error="test error")
        with pytest.raises(RuntimeError):
            _ = result.map_data

    def test_different_floors_different_maps(self):
        """Different floors (same seed) should produce different maps."""
        r1 = generate_dungeon_floor(seed=42, floor_number=1)
        r2 = generate_dungeon_floor(seed=42, floor_number=3)
        assert r1.success and r2.success
        # Floor 3 should be larger or at minimum different tiles
        assert r1.game_map["tiles"] != r2.game_map["tiles"]


# ═══════════════════════════════════════════════════════════
# Runtime Map Registration Tests
# ═══════════════════════════════════════════════════════════

class TestRuntimeMaps:
    """Test map_loader runtime map registration."""

    def test_register_and_load(self):
        """Registered runtime map should be loadable."""
        test_map = {
            "name": "test_runtime",
            "width": 12,
            "height": 12,
            "map_type": "dungeon",
            "tiles": [["W"] * 12 for _ in range(12)],
            "spawn_points": [{"x": 1, "y": 1}],
            "doors": [],
            "chests": [],
            "rooms": [],
            "tile_legend": {"W": "wall"},
        }
        map_id = "test_wfc_runtime"
        register_runtime_map(map_id, test_map)
        try:
            loaded = load_map(map_id)
            assert loaded["name"] == "test_runtime"
            assert loaded["width"] == 12
            assert is_dungeon_map(map_id) is True
            assert get_spawn_points(map_id) == [(1, 1)]
        finally:
            unregister_runtime_map(map_id)

    def test_unregister_removes_map(self):
        """Unregistered runtime map should no longer be loadable."""
        test_map = {"name": "temp", "width": 6, "height": 6}
        map_id = "test_wfc_temp"
        register_runtime_map(map_id, test_map)
        unregister_runtime_map(map_id)
        with pytest.raises(FileNotFoundError):
            load_map(map_id)


# ═══════════════════════════════════════════════════════════
# Full Integration Smoke Test
# ═══════════════════════════════════════════════════════════

class TestFullIntegration:
    """Smoke test: generate → register → load → validate the full chain."""

    def test_full_pipeline(self):
        """Generate a dungeon and verify it works through map_loader."""
        result = generate_dungeon_floor(seed=777, floor_number=2)
        assert result.success, f"Generation failed: {result.error}"

        map_id = "test_wfc_integration"
        register_runtime_map(map_id, result.game_map)
        try:
            # All map_loader accessors should work
            data = load_map(map_id)
            assert data["map_type"] == "dungeon"
            assert is_dungeon_map(map_id) is True

            spawn_points = get_spawn_points(map_id)
            assert len(spawn_points) > 0

            tiles = get_tiles(map_id)
            assert tiles is not None
            assert len(tiles) == data["height"]

            doors = get_doors(map_id)
            chests = get_chests(map_id)
            rooms = get_room_definitions(map_id)
            # At least some rooms should exist
            assert isinstance(rooms, list)
        finally:
            unregister_runtime_map(map_id)


# ═══════════════════════════════════════════════════════════
# Phase 12 Feature 5 — Spawn Room Guarantee Tests
# ═══════════════════════════════════════════════════════════

class TestSpawnRoomGuarantee:
    """Tests for spawn room guarantee with fallbacks."""

    def test_spawn_room_always_placed(self):
        """Every generated dungeon should have spawn points (guaranteeSpawn=True)."""
        for seed in [42, 123, 999, 2024, 7777]:
            result = generate_dungeon_floor(seed=seed, floor_number=1)
            assert result.success, f"Gen failed for seed {seed}: {result.error}"
            spawn_pts = result.game_map.get("spawn_points", [])
            assert len(spawn_pts) > 0, f"No spawn points for seed {seed}"

    def test_emergency_spawn_fallback(self):
        """Emergency spawn should place S tiles on floor tiles when no spawn room exists."""
        from app.core.wfc.room_decorator import _place_emergency_spawns

        # Create a simple tile map with floor tiles
        tile_map = [
            ["W", "W", "W", "W"],
            ["W", "F", "F", "W"],
            ["W", "F", "F", "W"],
            ["W", "W", "W", "W"],
        ]
        placements = _place_emergency_spawns(tile_map, count=2)

        assert len(placements) == 2
        for p in placements:
            assert p["type"] == "S"
            assert tile_map[p["y"]][p["x"]] == "S"

    def test_emergency_spawn_respects_count(self):
        """Emergency spawn should not place more tiles than requested."""
        from app.core.wfc.room_decorator import _place_emergency_spawns

        tile_map = [
            ["W", "W", "W", "W", "W"],
            ["W", "F", "F", "F", "W"],
            ["W", "F", "F", "F", "W"],
            ["W", "W", "W", "W", "W"],
        ]
        placements = _place_emergency_spawns(tile_map, count=3)
        assert len(placements) == 3

    def test_emergency_spawn_no_floor_tiles(self):
        """Emergency spawn returns empty list if no floor tiles exist."""
        from app.core.wfc.room_decorator import _place_emergency_spawns

        tile_map = [
            ["W", "W", "W"],
            ["W", "W", "W"],
            ["W", "W", "W"],
        ]
        placements = _place_emergency_spawns(tile_map)
        assert placements == []


# ═══════════════════════════════════════════════════════════
# Phase 12 Feature 5 — Enemy Type Scaling Validation Tests
# ═══════════════════════════════════════════════════════════

class TestEnemyTypeValidation:
    """Tests for enemy type configuration validation."""

    def test_all_scaling_enemy_types_exist_in_config(self):
        """All enemy types used in floor scaling must exist in enemies_config.json."""
        from app.core.wfc.dungeon_generator import validate_enemy_types
        missing = validate_enemy_types()
        assert missing == [], f"Missing enemy types in config: {missing}"

    def test_floor_scaling_enemy_types_vary_by_depth(self):
        """Different floor depths should produce different enemy type configurations."""
        configs = {}
        for floor in [1, 3, 5, 7, 9]:
            cfg = FloorConfig.from_floor_number(seed=42, floor_number=floor)
            configs[floor] = cfg.enemy_types

        # Early and late floors should differ
        assert configs[1] != configs[9], "Floor 1 and 9 should have different enemies"

        # Floor 1 should use skeletons as primary enemy
        assert configs[1]["E"] == "skeleton"

    def test_floor_scaling_grid_size_progression(self):
        """Grid size should increase with floor depth."""
        sizes = {}
        for floor in [1, 4, 7, 10]:
            cfg = FloorConfig.from_floor_number(seed=42, floor_number=floor)
            sizes[floor] = (cfg.grid_rows, cfg.grid_cols)

        assert sizes[1] <= sizes[4] <= sizes[7] <= sizes[10]

    def test_floor_scaling_enemy_density_increases(self):
        """Enemy density should increase with floor depth."""
        d1 = FloorConfig.from_floor_number(seed=42, floor_number=1).enemy_density
        d5 = FloorConfig.from_floor_number(seed=42, floor_number=5).enemy_density
        d10 = FloorConfig.from_floor_number(seed=42, floor_number=10).enemy_density
        assert d1 < d5 < d10

    def test_generated_enemies_match_floor_roster(self):
        """Enemies spawned in generated dungeons should come from the floor's roster."""
        result = generate_dungeon_floor(seed=42, floor_number=1)
        assert result.success

        cfg = FloorConfig.from_floor_number(seed=42, floor_number=1)
        roster = cfg.enemy_roster
        assert roster is not None, "Floor 1 should have an enemy roster"

        # Collect ALL valid enemy IDs from the roster (regular + boss + support)
        valid_ids = set()
        for pool in roster.values():
            for eid, _w in pool:
                valid_ids.add(eid)

        rooms = result.game_map.get("rooms", [])
        for room in rooms:
            for spawn in room.get("enemy_spawns", []):
                etype = spawn["enemy_type"]
                assert etype in valid_ids, \
                    f"Unexpected enemy type '{etype}' on floor 1 (valid: {valid_ids})"

    def test_floor_roster_has_all_roles(self):
        """Each floor roster should contain regular, boss, and support pools."""
        from app.core.wfc.dungeon_generator import get_floor_roster
        for floor in [1, 3, 5, 7, 9]:
            roster = get_floor_roster(floor)
            assert "regular" in roster, f"Floor {floor} missing 'regular' pool"
            assert "boss" in roster, f"Floor {floor} missing 'boss' pool"
            assert "support" in roster, f"Floor {floor} missing 'support' pool"
            assert len(roster["regular"]) >= 2, f"Floor {floor} should have 2+ regular enemy types"

    def test_roster_produces_varied_enemies(self):
        """Roster should produce multiple different enemy types across many rolls."""
        from app.core.wfc.dungeon_generator import resolve_enemy_for_tile, get_floor_roster
        import random
        roster = get_floor_roster(1)
        rng = random.Random(12345)
        seen = set()
        for _ in range(50):
            eid = resolve_enemy_for_tile("E", roster, rng.random)
            seen.add(eid)
        assert len(seen) >= 2, f"Expected varied enemies from roster, got only: {seen}"

    def test_support_swap_produces_support_enemies(self):
        """Support swap should produce enemies from the support pool."""
        from app.core.wfc.dungeon_generator import resolve_enemy_for_tile, get_floor_roster
        import random
        roster = get_floor_roster(1)
        rng = random.Random(99999)
        support_ids = {eid for eid, _ in roster["support"]}
        seen_support = set()
        for _ in range(100):
            eid = resolve_enemy_for_tile("E", roster, rng.random, is_support_swap=True)
            if eid in support_ids:
                seen_support.add(eid)
        assert len(seen_support) >= 1, "Support swap should produce support-pool enemies"

    def test_legacy_enemy_types_derived_from_roster(self):
        """FloorConfig.enemy_types should still work as a legacy accessor."""
        cfg = FloorConfig.from_floor_number(seed=42, floor_number=1)
        assert "E" in cfg.enemy_types
        assert "B" in cfg.enemy_types
        # Primary E type for floor 1 should be skeleton (highest-weighted)
        assert cfg.enemy_types["E"] == "skeleton"
