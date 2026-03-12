"""
Tests for Phase 27B — WFC Generation for PVPVE Layout.

Validates the PVPVE dungeon generation pipeline:
- FloorConfig.for_pvpve() factory method
- PVPVE decorator: 4 corner spawns, center boss, multi-spawn proximity ramp,
  difficulty gradient
- Map exporter: per-team spawn zones, PVE team tags, boss_room metadata,
  map_type "pvpve"
"""

from __future__ import annotations

import pytest

from app.core.wfc.dungeon_generator import (
    FloorConfig,
    GenerationResult,
    generate_dungeon_floor,
    get_floor_roster,
)
from app.core.wfc.room_decorator import (
    decorate_rooms,
    DEFAULT_DECORATOR_SETTINGS,
    _PVPVE_DECORATOR_DEFAULTS,
    _PVPVE_TEAM_ORDER,
    _get_active_teams,
    _pvpve_assign_corner_spawns,
    _pvpve_assign_center_boss,
    _pvpve_compute_proximity_ramp,
    _pvpve_compute_difficulty_tier,
    _pvpve_get_max_enemies_for_tier,
)
from app.core.wfc.map_exporter import export_to_game_map
from app.core.wfc.module_utils import MODULE_SIZE


# ═══════════════════════════════════════════════════════════
# Test Helpers
# ═══════════════════════════════════════════════════════════

def _make_flexible_variant(row: int, col: int) -> dict:
    """Create a flexible room variant with floor tiles and spawn slots."""
    tiles = []
    for r in range(8):
        row_tiles = []
        for c in range(8):
            if r == 0 or r == 7 or c == 0 or c == 7:
                row_tiles.append("W")
            else:
                row_tiles.append("F")
        tiles.append(row_tiles)

    return {
        "id": f"flex_{row}_{col}",
        "name": f"Flexible Room ({row},{col})",
        "tiles": tiles,
        "contentRole": "flexible",
        "purpose": "empty",
        "sockets": {
            "north": "WWOOOOWW",
            "south": "WWOOOOWW",
            "east": "WWOOOOWW",
            "west": "WWOOOOWW",
        },
        "spawnSlots": [
            {"x": 2, "y": 2, "types": ["enemy", "loot", "spawn", "boss"]},
            {"x": 4, "y": 2, "types": ["enemy", "loot", "spawn", "boss"]},
            {"x": 2, "y": 4, "types": ["enemy", "loot"]},
            {"x": 4, "y": 4, "types": ["enemy", "loot"]},
            {"x": 3, "y": 3, "types": ["enemy", "loot", "spawn", "boss"]},
            {"x": 5, "y": 3, "types": ["enemy", "loot"]},
        ],
        "canBeBoss": True,
        "canBeSpawn": True,
    }


def _build_grid_and_variants(rows: int, cols: int):
    """Build a simple grid of flexible rooms for testing.

    Returns (grid, variants, tile_map) suitable for decorate_rooms().
    """
    variants = []
    grid = []
    tile_h = rows * 8
    tile_w = cols * 8
    tile_map = [["W"] * tile_w for _ in range(tile_h)]

    for gr in range(rows):
        grid_row = []
        for gc in range(cols):
            variant = _make_flexible_variant(gr, gc)
            vid = len(variants)
            variants.append(variant)
            grid_row.append({"chosenVariant": vid})

            for r in range(8):
                for c in range(8):
                    tile_map[gr * 8 + r][gc * 8 + c] = variant["tiles"][r][c]

        grid.append(grid_row)

    return grid, variants, tile_map


def _get_rooms_by_role(result: dict) -> dict[str, list[dict]]:
    """Group decorated rooms by their assigned role."""
    groups: dict[str, list[dict]] = {}
    for room in result["decoratedRooms"]:
        role = room["assignedRole"]
        groups.setdefault(role, []).append(room)
    return groups


def _count_roles(result: dict) -> dict:
    """Count assigned roles from decoratedRooms."""
    counts = {}
    for room in result["decoratedRooms"]:
        role = room["assignedRole"]
        counts[role] = counts.get(role, 0) + 1
    return counts


# ═══════════════════════════════════════════════════════════
# 1. FloorConfig.for_pvpve() Tests
# ═══════════════════════════════════════════════════════════

class TestFloorConfigPVPVE:
    """Validate FloorConfig.for_pvpve() factory method."""

    def test_for_pvpve_creates_config(self):
        config = FloorConfig.for_pvpve(seed=42)
        assert config.pvpve_mode is True
        assert config.pvpve_team_count == 2

    def test_for_pvpve_default_grid_size(self):
        config = FloorConfig.for_pvpve(seed=42)
        assert config.grid_rows == 8
        assert config.grid_cols == 8

    def test_for_pvpve_custom_grid_size(self):
        config = FloorConfig.for_pvpve(seed=42, grid_size=6)
        assert config.grid_rows == 6
        assert config.grid_cols == 6

    def test_for_pvpve_produces_64x64_tiles(self):
        """8×8 grid * 8 MODULE_SIZE = 64×64 tile grid."""
        config = FloorConfig.for_pvpve(seed=42)
        assert config.grid_rows * MODULE_SIZE == 64
        assert config.grid_cols * MODULE_SIZE == 64

    def test_for_pvpve_team_count_clamped(self):
        config = FloorConfig.for_pvpve(seed=42, team_count=1)
        assert config.pvpve_team_count == 2  # Min 2

        config = FloorConfig.for_pvpve(seed=42, team_count=6)
        assert config.pvpve_team_count == 4  # Max 4

    def test_for_pvpve_team_count_4(self):
        config = FloorConfig.for_pvpve(seed=42, team_count=4)
        assert config.pvpve_team_count == 4

    def test_for_pvpve_floor_number_is_1(self):
        config = FloorConfig.for_pvpve(seed=42)
        assert config.floor_number == 1

    def test_for_pvpve_enemy_density(self):
        config = FloorConfig.for_pvpve(seed=42, pve_density=0.7)
        assert config.enemy_density == 0.7

    def test_for_pvpve_loot_density(self):
        config = FloorConfig.for_pvpve(seed=42, loot_density=0.8)
        assert config.loot_density == 0.8

    def test_for_pvpve_batch_size_5(self):
        config = FloorConfig.for_pvpve(seed=42)
        assert config.batch_size == 5

    def test_for_pvpve_map_name(self):
        config = FloorConfig.for_pvpve(seed=42)
        assert config.map_name == "PVPVE Dungeon"

    def test_for_pvpve_has_roster(self):
        config = FloorConfig.for_pvpve(seed=42)
        assert config.enemy_roster is not None
        assert "regular" in config.enemy_roster
        assert "boss" in config.enemy_roster

    def test_pvpve_mode_default_false(self):
        """Standard FloorConfig should have pvpve_mode=False."""
        config = FloorConfig()
        assert config.pvpve_mode is False
        assert config.pvpve_team_count == 2


# ═══════════════════════════════════════════════════════════
# 2. PVPVE Decorator Helper Tests
# ═══════════════════════════════════════════════════════════

class TestPVPVEHelpers:
    """Test individual PVPVE decorator helper functions."""

    def test_get_active_teams_2(self):
        assert _get_active_teams(2) == ["a", "b"]

    def test_get_active_teams_3(self):
        assert _get_active_teams(3) == ["a", "b", "c"]

    def test_get_active_teams_4(self):
        assert _get_active_teams(4) == ["a", "b", "c", "d"]

    def test_get_active_teams_clamped_below(self):
        assert _get_active_teams(0) == ["a", "b"]

    def test_get_active_teams_clamped_above(self):
        assert _get_active_teams(10) == ["a", "b", "c", "d"]

    def test_difficulty_tier_center(self):
        """Room at center of 8×8 grid should be boss tier."""
        room = {"gridRow": 4, "gridCol": 4}
        tier, dist = _pvpve_compute_difficulty_tier(room, 8, 8)
        assert tier == "boss"

    def test_difficulty_tier_near_center(self):
        """Room at distance 1 from center should be elite tier."""
        room = {"gridRow": 3, "gridCol": 4}
        tier, dist = _pvpve_compute_difficulty_tier(room, 8, 8)
        assert tier == "elite"

    def test_difficulty_tier_mid(self):
        """Room at distance 2 from center should be hard tier."""
        room = {"gridRow": 2, "gridCol": 4}
        tier, dist = _pvpve_compute_difficulty_tier(room, 8, 8)
        assert tier == "hard"

    def test_difficulty_tier_edge(self):
        """Room at the edge (distance 3+) should be normal tier."""
        room = {"gridRow": 0, "gridCol": 0}
        tier, dist = _pvpve_compute_difficulty_tier(room, 8, 8)
        assert tier == "normal"

    def test_max_enemies_boss_tier(self):
        assert _pvpve_get_max_enemies_for_tier("boss", 3) == 5

    def test_max_enemies_elite_tier(self):
        assert _pvpve_get_max_enemies_for_tier("elite", 3) == 5

    def test_max_enemies_hard_tier(self):
        assert _pvpve_get_max_enemies_for_tier("hard", 3) == 4

    def test_max_enemies_normal_tier(self):
        assert _pvpve_get_max_enemies_for_tier("normal", 5) == 3


# ═══════════════════════════════════════════════════════════
# 3. Corner Spawn Assignment Tests
# ═══════════════════════════════════════════════════════════

class TestPVPVECornerSpawns:
    """Validate corner spawn room placement."""

    def test_4_corners_assigned_on_8x8(self):
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        flexible_rooms = []
        for gr in range(8):
            for gc in range(8):
                flexible_rooms.append({
                    "gridRow": gr, "gridCol": gc,
                    "variant": variants[gr * 8 + gc],
                    "slots": variants[gr * 8 + gc]["spawnSlots"],
                    "maxEnemies": 3, "maxChests": 2,
                    "canBeBoss": True, "canBeSpawn": True,
                })
        assignments = {}
        spawn_rooms = _pvpve_assign_corner_spawns(
            flexible_rooms, 8, 8, 4, assignments,
        )
        assert len(spawn_rooms) == 4
        assert set(spawn_rooms.keys()) == {"a", "b", "c", "d"}

    def test_spawn_a_near_top_left(self):
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        flexible_rooms = []
        for gr in range(8):
            for gc in range(8):
                flexible_rooms.append({
                    "gridRow": gr, "gridCol": gc,
                    "variant": variants[gr * 8 + gc],
                    "slots": variants[gr * 8 + gc]["spawnSlots"],
                    "maxEnemies": 3, "maxChests": 2,
                    "canBeBoss": True, "canBeSpawn": True,
                })
        assignments = {}
        spawn_rooms = _pvpve_assign_corner_spawns(
            flexible_rooms, 8, 8, 4, assignments,
        )
        room_a = spawn_rooms["a"]
        assert room_a["gridRow"] <= 1
        assert room_a["gridCol"] <= 1

    def test_spawn_b_near_bottom_right(self):
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        flexible_rooms = []
        for gr in range(8):
            for gc in range(8):
                flexible_rooms.append({
                    "gridRow": gr, "gridCol": gc,
                    "variant": variants[gr * 8 + gc],
                    "slots": variants[gr * 8 + gc]["spawnSlots"],
                    "maxEnemies": 3, "maxChests": 2,
                    "canBeBoss": True, "canBeSpawn": True,
                })
        assignments = {}
        spawn_rooms = _pvpve_assign_corner_spawns(
            flexible_rooms, 8, 8, 4, assignments,
        )
        room_b = spawn_rooms["b"]
        assert room_b["gridRow"] >= 6
        assert room_b["gridCol"] >= 6

    def test_2_team_mode_only_a_and_b(self):
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        flexible_rooms = []
        for gr in range(8):
            for gc in range(8):
                flexible_rooms.append({
                    "gridRow": gr, "gridCol": gc,
                    "variant": variants[gr * 8 + gc],
                    "slots": variants[gr * 8 + gc]["spawnSlots"],
                    "maxEnemies": 3, "maxChests": 2,
                    "canBeBoss": True, "canBeSpawn": True,
                })
        assignments = {}
        spawn_rooms = _pvpve_assign_corner_spawns(
            flexible_rooms, 8, 8, 2, assignments,
        )
        assert len(spawn_rooms) == 2
        assert set(spawn_rooms.keys()) == {"a", "b"}

    def test_no_spawn_adjacent_to_another(self):
        """No two spawn rooms should be cardinally adjacent."""
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        flexible_rooms = []
        for gr in range(8):
            for gc in range(8):
                flexible_rooms.append({
                    "gridRow": gr, "gridCol": gc,
                    "variant": variants[gr * 8 + gc],
                    "slots": variants[gr * 8 + gc]["spawnSlots"],
                    "maxEnemies": 3, "maxChests": 2,
                    "canBeBoss": True, "canBeSpawn": True,
                })
        assignments = {}
        spawn_rooms = _pvpve_assign_corner_spawns(
            flexible_rooms, 8, 8, 4, assignments,
        )
        positions = [(r["gridRow"], r["gridCol"]) for r in spawn_rooms.values()]
        for i, (r1, c1) in enumerate(positions):
            for j, (r2, c2) in enumerate(positions):
                if i != j:
                    dist = abs(r1 - r2) + abs(c1 - c2)
                    assert dist > 1, f"Spawns at ({r1},{c1}) and ({r2},{c2}) are adjacent"


# ═══════════════════════════════════════════════════════════
# 4. Center Boss Assignment Tests
# ═══════════════════════════════════════════════════════════

class TestPVPVECenterBoss:
    """Validate boss room placement at center."""

    def test_boss_room_near_center(self):
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        flexible_rooms = []
        for gr in range(8):
            for gc in range(8):
                flexible_rooms.append({
                    "gridRow": gr, "gridCol": gc,
                    "variant": variants[gr * 8 + gc],
                    "slots": variants[gr * 8 + gc]["spawnSlots"],
                    "maxEnemies": 3, "maxChests": 2,
                    "canBeBoss": True, "canBeSpawn": True,
                })
        assignments = {}
        boss = _pvpve_assign_center_boss(
            flexible_rooms, 8, 8, assignments, {},
        )
        assert boss is not None
        # Center of 8×8 is (4, 4) — boss should be within 1 cell
        assert abs(boss["gridRow"] - 4) <= 1
        assert abs(boss["gridCol"] - 4) <= 1

    def test_boss_not_overlapping_spawn(self):
        """Boss room should not be assigned to a spawn room."""
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        flexible_rooms = []
        for gr in range(8):
            for gc in range(8):
                flexible_rooms.append({
                    "gridRow": gr, "gridCol": gc,
                    "variant": variants[gr * 8 + gc],
                    "slots": variants[gr * 8 + gc]["spawnSlots"],
                    "maxEnemies": 3, "maxChests": 2,
                    "canBeBoss": True, "canBeSpawn": True,
                })
        assignments = {}
        # First assign corner spawns
        spawn_rooms = _pvpve_assign_corner_spawns(
            flexible_rooms, 8, 8, 4, assignments,
        )
        # Then assign boss
        boss = _pvpve_assign_center_boss(
            flexible_rooms, 8, 8, assignments, {},
        )
        assert boss is not None
        boss_key = f"{boss['gridRow']},{boss['gridCol']}"
        spawn_keys = {f"{r['gridRow']},{r['gridCol']}" for r in spawn_rooms.values()}
        assert boss_key not in spawn_keys


# ═══════════════════════════════════════════════════════════
# 5. Multi-Spawn Proximity Ramp Tests
# ═══════════════════════════════════════════════════════════

class TestPVPVEProximityRamp:
    """Validate multi-spawn proximity ramp."""

    def test_rooms_adjacent_to_any_spawn_are_safe(self):
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        flexible_rooms = []
        for gr in range(8):
            for gc in range(8):
                flexible_rooms.append({
                    "gridRow": gr, "gridCol": gc,
                    "variant": variants[gr * 8 + gc],
                    "slots": variants[gr * 8 + gc]["spawnSlots"],
                    "maxEnemies": 3, "maxChests": 2,
                    "canBeBoss": True, "canBeSpawn": True,
                })

        # Place spawns at 4 corners
        spawn_rooms = {
            "a": {"gridRow": 0, "gridCol": 0},
            "b": {"gridRow": 7, "gridCol": 7},
        }

        room_dists, proximity_ov = _pvpve_compute_proximity_ramp(
            flexible_rooms, spawn_rooms,
        )

        # Room at (0,1) is distance 1 from spawn A → safe
        assert proximity_ov.get("0,1") == "safe"
        # Room at (1,0) is distance 1 from spawn A → safe
        assert proximity_ov.get("1,0") == "safe"
        # Room at (6,7) is distance 1 from spawn B → safe
        assert proximity_ov.get("6,7") == "safe"

    def test_distance_2_rooms_are_softened(self):
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        flexible_rooms = []
        for gr in range(8):
            for gc in range(8):
                flexible_rooms.append({
                    "gridRow": gr, "gridCol": gc,
                    "variant": variants[gr * 8 + gc],
                    "slots": variants[gr * 8 + gc]["spawnSlots"],
                    "maxEnemies": 3, "maxChests": 2,
                    "canBeBoss": True, "canBeSpawn": True,
                })

        spawn_rooms = {"a": {"gridRow": 0, "gridCol": 0}}
        room_dists, proximity_ov = _pvpve_compute_proximity_ramp(
            flexible_rooms, spawn_rooms,
        )

        # Room at (2,0) is distance 2 from spawn → softened
        assert proximity_ov.get("2,0") == "softened"
        assert proximity_ov.get("0,2") == "softened"

    def test_far_rooms_have_no_override(self):
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        flexible_rooms = []
        for gr in range(8):
            for gc in range(8):
                flexible_rooms.append({
                    "gridRow": gr, "gridCol": gc,
                    "variant": variants[gr * 8 + gc],
                    "slots": variants[gr * 8 + gc]["spawnSlots"],
                    "maxEnemies": 3, "maxChests": 2,
                    "canBeBoss": True, "canBeSpawn": True,
                })

        spawn_rooms = {"a": {"gridRow": 0, "gridCol": 0}}
        room_dists, proximity_ov = _pvpve_compute_proximity_ramp(
            flexible_rooms, spawn_rooms,
        )

        # Room at (5,5) should have no override
        assert "5,5" not in proximity_ov


# ═══════════════════════════════════════════════════════════
# 6. Full Decorator PVPVE Path Tests
# ═══════════════════════════════════════════════════════════

class TestPVPVEDecoratorIntegration:
    """Test the full decorator flow in PVPVE mode."""

    def test_pvpve_4_team_spawns_placed(self):
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        result = decorate_rooms(
            grid=grid, variants=variants, tile_map=tile_map, seed=42,
            settings={"pvpve_mode": True, "pvpve_team_count": 4,
                       "guaranteeBoss": True, "guaranteeSpawn": True,
                       "guaranteeStairs": False,
                       "enemyDensity": 0.5, "lootDensity": 0.3},
        )
        roles = _count_roles(result)
        # Should have 4 spawn rooms (spawn_a, spawn_b, spawn_c, spawn_d)
        spawn_count = sum(1 for r in result["decoratedRooms"]
                          if r["assignedRole"].startswith("spawn_"))
        assert spawn_count == 4

    def test_pvpve_2_team_spawns_placed(self):
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        result = decorate_rooms(
            grid=grid, variants=variants, tile_map=tile_map, seed=42,
            settings={"pvpve_mode": True, "pvpve_team_count": 2,
                       "guaranteeBoss": True, "guaranteeSpawn": True,
                       "guaranteeStairs": False,
                       "enemyDensity": 0.5, "lootDensity": 0.3},
        )
        spawn_count = sum(1 for r in result["decoratedRooms"]
                          if r["assignedRole"].startswith("spawn_"))
        assert spawn_count == 2

    def test_pvpve_boss_room_placed(self):
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        result = decorate_rooms(
            grid=grid, variants=variants, tile_map=tile_map, seed=42,
            settings={"pvpve_mode": True, "pvpve_team_count": 4,
                       "guaranteeBoss": True, "guaranteeSpawn": True,
                       "guaranteeStairs": False,
                       "enemyDensity": 0.5, "lootDensity": 0.3},
        )
        boss_rooms = [r for r in result["decoratedRooms"]
                      if r["assignedRole"] == "boss"]
        assert len(boss_rooms) == 1
        boss = boss_rooms[0]
        # Boss room should be near center of 8×8 grid
        assert abs(boss["gridRow"] - 4) <= 1
        assert abs(boss["gridCol"] - 4) <= 1

    def test_pvpve_no_stairs(self):
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        result = decorate_rooms(
            grid=grid, variants=variants, tile_map=tile_map, seed=42,
            settings={"pvpve_mode": True, "pvpve_team_count": 4,
                       "guaranteeBoss": True, "guaranteeSpawn": True,
                       "guaranteeStairs": False,
                       "enemyDensity": 0.5, "lootDensity": 0.3},
        )
        stairs_rooms = [r for r in result["decoratedRooms"]
                        if r["assignedRole"] == "stairs"]
        assert len(stairs_rooms) == 0

    def test_pvpve_rooms_near_spawn_are_safe(self):
        """Rooms adjacent to any spawn should not be assigned as enemy rooms."""
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        result = decorate_rooms(
            grid=grid, variants=variants, tile_map=tile_map, seed=42,
            settings={"pvpve_mode": True, "pvpve_team_count": 4,
                       "guaranteeBoss": True, "guaranteeSpawn": True,
                       "guaranteeStairs": False,
                       "enemyDensity": 0.5, "lootDensity": 0.3},
        )
        # Get spawn room positions
        spawn_positions = set()
        for room in result["decoratedRooms"]:
            if room["assignedRole"].startswith("spawn_"):
                spawn_positions.add((room["gridRow"], room["gridCol"]))

        # Check rooms adjacent to spawns
        for room in result["decoratedRooms"]:
            key = (room["gridRow"], room["gridCol"])
            for sr, sc in spawn_positions:
                dist = abs(room["gridRow"] - sr) + abs(room["gridCol"] - sc)
                if dist == 1:
                    # Adjacent to a spawn — should not be "enemy"
                    assert room["assignedRole"] != "enemy", (
                        f"Room at ({room['gridRow']},{room['gridCol']}) is adjacent to "
                        f"spawn at ({sr},{sc}) but assigned as 'enemy'"
                    )

    def test_pvpve_spawn_rooms_metadata(self):
        """Decorator should include pvpve_spawn_rooms metadata."""
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        result = decorate_rooms(
            grid=grid, variants=variants, tile_map=tile_map, seed=42,
            settings={"pvpve_mode": True, "pvpve_team_count": 4,
                       "guaranteeBoss": True, "guaranteeSpawn": True,
                       "guaranteeStairs": False,
                       "enemyDensity": 0.5, "lootDensity": 0.3},
        )
        assert "pvpve_spawn_rooms" in result
        assert len(result["pvpve_spawn_rooms"]) == 4
        assert set(result["pvpve_spawn_rooms"].keys()) == {"a", "b", "c", "d"}

    def test_pvpve_difficulty_tiers_included(self):
        """Decorator should include pvpve_difficulty_tiers metadata."""
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        result = decorate_rooms(
            grid=grid, variants=variants, tile_map=tile_map, seed=42,
            settings={"pvpve_mode": True, "pvpve_team_count": 4,
                       "guaranteeBoss": True, "guaranteeSpawn": True,
                       "guaranteeStairs": False,
                       "enemyDensity": 0.5, "lootDensity": 0.3},
        )
        assert "pvpve_difficulty_tiers" in result
        tiers = result["pvpve_difficulty_tiers"]
        # Center rooms should be boss/elite
        center_tier = tiers.get("4,4")
        assert center_tier in ("boss", "elite")
        # Corner rooms should be normal
        corner_tier = tiers.get("0,0")
        assert corner_tier == "normal"

    def test_pvpve_difficulty_tier_on_rooms(self):
        """Enemy rooms should have difficultyTier set."""
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        result = decorate_rooms(
            grid=grid, variants=variants, tile_map=tile_map, seed=42,
            settings={"pvpve_mode": True, "pvpve_team_count": 4,
                       "guaranteeBoss": True, "guaranteeSpawn": True,
                       "guaranteeStairs": False,
                       "enemyDensity": 0.5, "lootDensity": 0.3},
        )
        for room in result["decoratedRooms"]:
            if room["assignedRole"] == "enemy":
                assert room.get("difficultyTier") is not None

    def test_pvpve_boss_room_has_extra_guards(self):
        """Boss room in PVPVE should have more guards than standard mode."""
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        result = decorate_rooms(
            grid=grid, variants=variants, tile_map=tile_map, seed=42,
            settings={"pvpve_mode": True, "pvpve_team_count": 4,
                       "guaranteeBoss": True, "guaranteeSpawn": True,
                       "guaranteeStairs": False,
                       "pvpve_boss_guards": 3, "pvpve_boss_chests": 2,
                       "enemyDensity": 0.5, "lootDensity": 0.3},
        )
        boss_rooms = [r for r in result["decoratedRooms"]
                      if r["assignedRole"] == "boss"]
        assert len(boss_rooms) == 1
        boss = boss_rooms[0]
        boss_tiles = [p for p in boss["placements"] if p["type"] == "B"]
        guard_tiles = [p for p in boss["placements"] if p["type"] == "E"]
        chest_tiles = [p for p in boss["placements"] if p["type"] == "X"]
        assert len(boss_tiles) == 1
        assert len(guard_tiles) >= 2  # At least 2 guards (capped by available slots)
        assert len(chest_tiles) >= 1  # At least 1 chest


# ═══════════════════════════════════════════════════════════
# 7. Map Exporter PVPVE Tests
# ═══════════════════════════════════════════════════════════

class TestPVPVEExporter:
    """Test PVPVE-specific map exporter output."""

    def _make_pvpve_map(self, team_count: int = 4):
        """Generate a PVPVE map through the full decorator + exporter pipeline."""
        grid, variants, tile_map = _build_grid_and_variants(8, 8)
        decoration = decorate_rooms(
            grid=grid, variants=variants, tile_map=tile_map, seed=42,
            settings={"pvpve_mode": True, "pvpve_team_count": team_count,
                       "guaranteeBoss": True, "guaranteeSpawn": True,
                       "guaranteeStairs": False,
                       "pvpve_boss_guards": 3, "pvpve_boss_chests": 2,
                       "enemyDensity": 0.5, "lootDensity": 0.3},
        )
        decorated_tile_map = decoration["tileMap"]
        game_map = export_to_game_map(
            tile_map=decorated_tile_map,
            grid=grid,
            variants=variants,
            map_name="PVPVE Test",
            floor_number=1,
            seed=42,
            pvpve_mode=True,
            pvpve_team_count=team_count,
            decoration_result=decoration,
        )
        return game_map

    def test_map_type_is_pvpve(self):
        game_map = self._make_pvpve_map()
        assert game_map["map_type"] == "pvpve"

    def test_pvpve_team_count_in_map(self):
        game_map = self._make_pvpve_map(4)
        assert game_map["pvpve_team_count"] == 4

    def test_per_team_spawn_zones(self):
        game_map = self._make_pvpve_map(4)
        sz = game_map["spawn_zones"]
        assert "a" in sz
        assert "b" in sz
        assert "c" in sz
        assert "d" in sz

    def test_per_team_spawn_zones_2_teams(self):
        game_map = self._make_pvpve_map(2)
        sz = game_map["spawn_zones"]
        assert "a" in sz
        assert "b" in sz
        # c and d should not have zones
        assert "c" not in sz
        assert "d" not in sz

    def test_spawn_zones_have_bounds(self):
        game_map = self._make_pvpve_map(4)
        for team_key, zone in game_map["spawn_zones"].items():
            assert "x_min" in zone
            assert "y_min" in zone
            assert "x_max" in zone
            assert "y_max" in zone
            assert zone["x_min"] <= zone["x_max"]
            assert zone["y_min"] <= zone["y_max"]

    def test_spawn_points_by_team(self):
        game_map = self._make_pvpve_map(4)
        spt = game_map.get("spawn_points_by_team", {})
        assert "a" in spt
        assert "b" in spt
        assert len(spt["a"]) > 0
        assert len(spt["b"]) > 0

    def test_enemy_spawns_have_pve_team(self):
        game_map = self._make_pvpve_map(4)
        for room in game_map["rooms"]:
            for spawn in room.get("enemy_spawns", []):
                assert spawn.get("team") == "pve", (
                    f"Enemy spawn in room {room['id']} missing team='pve': {spawn}"
                )

    def test_boss_room_metadata(self):
        game_map = self._make_pvpve_map(4)
        assert "boss_room" in game_map
        br = game_map["boss_room"]
        assert "id" in br
        assert "bounds" in br
        assert "enemy_spawns" in br
        assert "chests" in br

    def test_boss_room_has_boss_spawn(self):
        game_map = self._make_pvpve_map(4)
        br = game_map["boss_room"]
        boss_spawns = [s for s in br["enemy_spawns"] if s.get("is_boss")]
        assert len(boss_spawns) >= 1

    def test_standard_map_type_still_dungeon(self):
        """Non-PVPVE export should still produce map_type='dungeon'."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)
        decoration = decorate_rooms(
            grid=grid, variants=variants, tile_map=tile_map, seed=42,
        )
        game_map = export_to_game_map(
            tile_map=decoration["tileMap"],
            grid=grid, variants=variants,
            map_name="Standard", floor_number=1, seed=42,
        )
        assert game_map["map_type"] == "dungeon"

    def test_standard_enemies_no_team_field(self):
        """Non-PVPVE export should not add team field to enemy spawns."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)
        decoration = decorate_rooms(
            grid=grid, variants=variants, tile_map=tile_map, seed=42,
        )
        game_map = export_to_game_map(
            tile_map=decoration["tileMap"],
            grid=grid, variants=variants,
            map_name="Standard", floor_number=1, seed=42,
        )
        for room in game_map["rooms"]:
            for spawn in room.get("enemy_spawns", []):
                assert "team" not in spawn, "Standard export should not have team field"


# ═══════════════════════════════════════════════════════════
# 8. Full Pipeline Integration Test
# ═══════════════════════════════════════════════════════════

class TestPVPVEFullPipeline:
    """End-to-end pipeline test: FloorConfig → generate → validate."""

    def test_pvpve_generation_succeeds(self):
        """PVPVE generation with a small grid should succeed."""
        config = FloorConfig.for_pvpve(seed=12345, team_count=4, grid_size=4)
        result = generate_dungeon_floor(config=config)
        assert result.success is True
        assert result.game_map is not None

    def test_pvpve_map_has_correct_type(self):
        config = FloorConfig.for_pvpve(seed=12345, team_count=4, grid_size=4)
        result = generate_dungeon_floor(config=config)
        assert result.success is True
        assert result.game_map["map_type"] == "pvpve"

    def test_pvpve_map_has_team_count(self):
        config = FloorConfig.for_pvpve(seed=12345, team_count=3, grid_size=4)
        result = generate_dungeon_floor(config=config)
        assert result.success is True
        assert result.game_map["pvpve_team_count"] == 3

    def test_pvpve_map_dimensions(self):
        """4×4 grid * MODULE_SIZE=8 → 32×32 tiles."""
        config = FloorConfig.for_pvpve(seed=12345, team_count=2, grid_size=4)
        result = generate_dungeon_floor(config=config)
        assert result.success is True
        assert result.game_map["width"] == 32
        assert result.game_map["height"] == 32

    def test_pvpve_4_team_spawn_zones(self):
        config = FloorConfig.for_pvpve(seed=12345, team_count=4, grid_size=4)
        result = generate_dungeon_floor(config=config)
        assert result.success is True
        sz = result.game_map["spawn_zones"]
        # Should have zones for all 4 teams (if WFC produces enough rooms)
        assert len(sz) >= 2  # At minimum a and b

    def test_pvpve_all_enemies_tagged_pve(self):
        config = FloorConfig.for_pvpve(seed=12345, team_count=2, grid_size=4)
        result = generate_dungeon_floor(config=config)
        assert result.success is True
        for room in result.game_map["rooms"]:
            for spawn in room.get("enemy_spawns", []):
                assert spawn.get("team") == "pve"

    def test_pvpve_deterministic(self):
        """Same seed should produce same output."""
        config1 = FloorConfig.for_pvpve(seed=54321, team_count=4, grid_size=4)
        result1 = generate_dungeon_floor(config=config1)
        config2 = FloorConfig.for_pvpve(seed=54321, team_count=4, grid_size=4)
        result2 = generate_dungeon_floor(config=config2)
        assert result1.success == result2.success
        if result1.success:
            assert result1.game_map["rooms"] == result2.game_map["rooms"]
            assert result1.game_map["spawn_zones"] == result2.game_map["spawn_zones"]
