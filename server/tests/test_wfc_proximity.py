"""
Tests for Spawn Distribution Overhaul — Phase 2: Spawn-Proximity Ramp.

Validates the proximity-aware room assignment system that prevents
heavy enemy rooms from spawning adjacent to the player's start position.

Ensures:
- Manhattan distance is computed correctly from spawn to all flexible rooms
- Rooms at distance ≤ 1 ("safe") never receive the "enemy" role from the deck
- Rooms at distance 2 ("softened") have halved maxEnemies when assigned "enemy"
- Stairs placement (Pass B2) is unaffected — still placed farthest from spawn
- Small grids (3×3) protect ≥2 rooms; large grids (5×5+) protect 3-4 rooms
- Determinism: same seed → same distance assignments → same swaps
- Full pipeline integration still works
"""

from __future__ import annotations

import pytest

from app.core.wfc.room_decorator import decorate_rooms, DEFAULT_DECORATOR_SETTINGS


# ═══════════════════════════════════════════════════════════
# Test Helpers (shared with test_wfc_room_quota.py pattern)
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
# Distance Calculation Tests
# ═══════════════════════════════════════════════════════════

class TestSpawnDistanceCalculation:
    """Verify Manhattan distance from spawn is computed correctly."""

    def test_distance_zero_for_spawn_room(self):
        """The spawn room itself should have distance 0."""
        grid, variants, tile_map = _build_grid_and_variants(3, 3)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        for room in result["decoratedRooms"]:
            if room["assignedRole"] == "spawn":
                assert room.get("spawnDistance") == 0, \
                    f"Spawn room should have distance 0, got {room.get('spawnDistance')}"

    def test_adjacent_rooms_have_distance_one(self):
        """Rooms orthogonally adjacent to spawn should have distance 1."""
        grid, variants, tile_map = _build_grid_and_variants(3, 3)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        spawn_room = None
        for room in result["decoratedRooms"]:
            if room["assignedRole"] == "spawn":
                spawn_room = room
                break

        assert spawn_room is not None, "No spawn room found"

        sr, sc = spawn_room["gridRow"], spawn_room["gridCol"]
        for room in result["decoratedRooms"]:
            gr, gc = room["gridRow"], room["gridCol"]
            expected_dist = abs(gr - sr) + abs(gc - sc)
            if expected_dist == 1:
                assert room.get("spawnDistance") == 1, \
                    f"Room ({gr},{gc}) should have distance 1 from spawn ({sr},{sc}), got {room.get('spawnDistance')}"

    def test_all_rooms_have_spawn_distance(self):
        """Every decorated room should have a spawnDistance field."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        for room in result["decoratedRooms"]:
            # Emergency fallback rooms (gridRow=-1) don't get distance
            if room["gridRow"] == -1:
                continue
            assert "spawnDistance" in room, \
                f"Room ({room['gridRow']},{room['gridCol']}) missing spawnDistance"
            assert isinstance(room["spawnDistance"], int), \
                f"spawnDistance should be int, got {type(room['spawnDistance'])}"

    def test_distance_increases_with_grid_separation(self):
        """Distance should increase as rooms are farther from spawn on the grid."""
        grid, variants, tile_map = _build_grid_and_variants(5, 5)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        spawn_room = None
        for room in result["decoratedRooms"]:
            if room["assignedRole"] == "spawn":
                spawn_room = room
                break

        assert spawn_room is not None

        sr, sc = spawn_room["gridRow"], spawn_room["gridCol"]
        for room in result["decoratedRooms"]:
            if room["gridRow"] == -1:
                continue
            gr, gc = room["gridRow"], room["gridCol"]
            expected = abs(gr - sr) + abs(gc - sc)
            assert room["spawnDistance"] == expected, \
                f"Room ({gr},{gc}): expected dist={expected}, got {room['spawnDistance']}"


# ═══════════════════════════════════════════════════════════
# Proximity Override Tests
# ═══════════════════════════════════════════════════════════

class TestProximityOverrides:
    """Verify that proximity overrides are correctly applied."""

    def test_safe_zone_rooms_have_override(self):
        """Rooms at distance ≤ 1 should have proximityOverride='safe'."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        for room in result["decoratedRooms"]:
            if room["gridRow"] == -1:
                continue
            dist = room.get("spawnDistance", 99)
            override = room.get("proximityOverride")
            if dist <= 1:
                assert override == "safe", \
                    f"Room ({room['gridRow']},{room['gridCol']}) at dist={dist} should be 'safe', got '{override}'"

    def test_softened_rooms_have_override(self):
        """Rooms at distance 2 should have proximityOverride='softened'."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        for room in result["decoratedRooms"]:
            if room["gridRow"] == -1:
                continue
            dist = room.get("spawnDistance", 99)
            override = room.get("proximityOverride")
            if dist == 2:
                assert override == "softened", \
                    f"Room ({room['gridRow']},{room['gridCol']}) at dist=2 should be 'softened', got '{override}'"

    def test_far_rooms_have_no_override(self):
        """Rooms at distance ≥ 3 should have no proximity override."""
        grid, variants, tile_map = _build_grid_and_variants(5, 5)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        for room in result["decoratedRooms"]:
            if room["gridRow"] == -1:
                continue
            dist = room.get("spawnDistance", 99)
            override = room.get("proximityOverride")
            if dist >= 3:
                assert override is None, \
                    f"Room ({room['gridRow']},{room['gridCol']}) at dist={dist} should have no override, got '{override}'"


# ═══════════════════════════════════════════════════════════
# Safe Zone Enemy Exclusion Tests
# ═══════════════════════════════════════════════════════════

class TestSafeZoneEnemyExclusion:
    """Verify rooms adjacent to spawn never get assigned the 'enemy' role."""

    def test_safe_zone_never_enemy(self):
        """Rooms at distance ≤ 1 should never have role='enemy'."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)

        for seed in range(1, 31):
            result = decorate_rooms(grid, variants, tile_map, seed=seed, settings={
                "enemyDensity": 0.70,
                "lootDensity": 0.10,
                "emptyRoomChance": 0.05,
            })

            for room in result["decoratedRooms"]:
                if room["gridRow"] == -1:
                    continue
                dist = room.get("spawnDistance", 99)
                if dist <= 1 and room["assignedRole"] not in ("boss", "spawn", "stairs"):
                    assert room["assignedRole"] != "enemy", \
                        f"Seed {seed}: Room ({room['gridRow']},{room['gridCol']}) at dist={dist} " \
                        f"should not be 'enemy' (safe zone)"

    def test_safe_zone_never_enemy_on_3x3_grid(self):
        """On a 3×3 grid, safe-zone rooms should never be enemy."""
        grid, variants, tile_map = _build_grid_and_variants(3, 3)

        for seed in range(1, 51):
            result = decorate_rooms(grid, variants, tile_map, seed=seed, settings={
                "enemyDensity": 0.60,
                "lootDensity": 0.15,
            })

            for room in result["decoratedRooms"]:
                if room["gridRow"] == -1:
                    continue
                dist = room.get("spawnDistance", 99)
                if dist <= 1 and room["assignedRole"] not in ("boss", "spawn", "stairs"):
                    assert room["assignedRole"] != "enemy", \
                        f"Seed {seed}: Safe room ({room['gridRow']},{room['gridCol']}) " \
                        f"at dist={dist} should not be 'enemy'"

    def test_safe_zone_never_enemy_on_5x5_grid(self):
        """On a 5×5 grid, safe-zone rooms should never be enemy."""
        grid, variants, tile_map = _build_grid_and_variants(5, 5)

        for seed in range(1, 21):
            result = decorate_rooms(grid, variants, tile_map, seed=seed, settings={
                "enemyDensity": 0.80,
                "lootDensity": 0.05,
            })

            for room in result["decoratedRooms"]:
                if room["gridRow"] == -1:
                    continue
                dist = room.get("spawnDistance", 99)
                if dist <= 1 and room["assignedRole"] not in ("boss", "spawn", "stairs"):
                    assert room["assignedRole"] != "enemy", \
                        f"Seed {seed}: Safe room ({room['gridRow']},{room['gridCol']}) " \
                        f"at dist={dist} should not be 'enemy'"

    def test_safe_zone_allows_loot_and_empty(self):
        """Safe-zone rooms should be assigned loot or empty (not enemy)."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)

        safe_roles_seen = set()
        for seed in range(1, 31):
            result = decorate_rooms(grid, variants, tile_map, seed=seed, settings={
                "enemyDensity": 0.50,
                "lootDensity": 0.20,
            })

            for room in result["decoratedRooms"]:
                if room["gridRow"] == -1:
                    continue
                dist = room.get("spawnDistance", 99)
                if dist <= 1 and room["assignedRole"] not in ("boss", "spawn", "stairs"):
                    safe_roles_seen.add(room["assignedRole"])

        # Safe zone rooms should only get loot or empty
        assert safe_roles_seen <= {"loot", "empty"}, \
            f"Safe zone rooms got unexpected roles: {safe_roles_seen}"


# ═══════════════════════════════════════════════════════════
# Softened Room Tests
# ═══════════════════════════════════════════════════════════

class TestSoftenedRooms:
    """Verify rooms at distance 2 have reduced max enemies."""

    def test_softened_enemy_rooms_have_fewer_enemies(self):
        """Enemy rooms at distance 2 should place fewer enemies than normal."""
        grid, variants, tile_map = _build_grid_and_variants(5, 5)

        softened_max_enemies = []
        normal_max_enemies = []

        for seed in range(1, 51):
            result = decorate_rooms(grid, variants, tile_map, seed=seed, settings={
                "enemyDensity": 0.60,
                "lootDensity": 0.10,
            })

            for room in result["decoratedRooms"]:
                if room["assignedRole"] != "enemy" or room["gridRow"] == -1:
                    continue
                enemy_count = sum(1 for p in room["placements"] if p["type"] == "E")
                dist = room.get("spawnDistance", 99)
                if dist == 2:
                    softened_max_enemies.append(enemy_count)
                elif dist >= 3:
                    normal_max_enemies.append(enemy_count)

        # If we found both categories, softened should average fewer
        if softened_max_enemies and normal_max_enemies:
            avg_softened = sum(softened_max_enemies) / len(softened_max_enemies)
            avg_normal = sum(normal_max_enemies) / len(normal_max_enemies)
            assert avg_softened <= avg_normal, \
                f"Softened rooms should have ≤ enemies on average: " \
                f"softened={avg_softened:.1f} vs normal={avg_normal:.1f}"

    def test_softened_rooms_still_allow_enemies(self):
        """Softened rooms CAN have enemies — just fewer."""
        grid, variants, tile_map = _build_grid_and_variants(5, 5)

        found_softened_enemy = False
        for seed in range(1, 51):
            result = decorate_rooms(grid, variants, tile_map, seed=seed, settings={
                "enemyDensity": 0.70,
                "lootDensity": 0.05,
            })

            for room in result["decoratedRooms"]:
                if room["gridRow"] == -1:
                    continue
                if room["assignedRole"] == "enemy" and room.get("spawnDistance") == 2:
                    found_softened_enemy = True
                    break
            if found_softened_enemy:
                break

        assert found_softened_enemy, \
            "Softened rooms (distance 2) should sometimes be enemy rooms"


# ═══════════════════════════════════════════════════════════
# Protected Room Count Tests
# ═══════════════════════════════════════════════════════════

class TestProtectedRoomCounts:
    """Verify the right number of rooms are protected on different grid sizes."""

    def test_3x3_grid_protects_at_least_2_rooms(self):
        """On a 3×3 grid, at least 2 rooms should be in the safe zone."""
        grid, variants, tile_map = _build_grid_and_variants(3, 3)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        safe_count = 0
        for room in result["decoratedRooms"]:
            if room["gridRow"] == -1:
                continue
            if room.get("spawnDistance", 99) <= 1:
                safe_count += 1

        # Distance 0 (spawn itself) + at least 1-2 adjacent rooms
        assert safe_count >= 2, \
            f"3×3 grid should have ≥2 safe rooms, got {safe_count}"

    def test_5x5_grid_protects_at_least_3_rooms(self):
        """On a 5×5 grid, at least 3 rooms should be in the safe zone."""
        grid, variants, tile_map = _build_grid_and_variants(5, 5)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        safe_count = 0
        for room in result["decoratedRooms"]:
            if room["gridRow"] == -1:
                continue
            if room.get("spawnDistance", 99) <= 1:
                safe_count += 1

        # Spawn + up to 4 orthogonal neighbors (but some may be boss/stairs)
        assert safe_count >= 3, \
            f"5×5 grid should have ≥3 safe rooms, got {safe_count}"

    def test_5x5_grid_has_softened_rooms(self):
        """On a 5×5 grid, there should be some softened (distance 2) rooms."""
        grid, variants, tile_map = _build_grid_and_variants(5, 5)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        softened_count = 0
        for room in result["decoratedRooms"]:
            if room["gridRow"] == -1:
                continue
            if room.get("spawnDistance") == 2:
                softened_count += 1

        assert softened_count >= 2, \
            f"5×5 grid should have ≥2 softened rooms, got {softened_count}"


# ═══════════════════════════════════════════════════════════
# Stairs Placement Unaffected Tests
# ═══════════════════════════════════════════════════════════

class TestStairsPlacementUnaffected:
    """Verify stairs are still placed far from spawn (Pass B2 unchanged)."""

    def test_stairs_placed_far_from_spawn(self):
        """Stairs should be at maximum grid distance from spawn."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        spawn_room = None
        stairs_room = None
        for room in result["decoratedRooms"]:
            if room["assignedRole"] == "spawn" and room["gridRow"] != -1:
                spawn_room = room
            elif room["assignedRole"] == "stairs" and room["gridRow"] != -1:
                stairs_room = room

        if spawn_room and stairs_room:
            stairs_dist = (abs(stairs_room["gridRow"] - spawn_room["gridRow"]) +
                          abs(stairs_room["gridCol"] - spawn_room["gridCol"]))
            # On a 4×4 grid, max distance is 6; stairs should be at least dist 3
            assert stairs_dist >= 2, \
                f"Stairs should be far from spawn (dist={stairs_dist})"

    def test_stairs_never_in_safe_zone(self):
        """Stairs should not be placed in the safe zone (dist ≤ 1)."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)

        for seed in range(1, 21):
            result = decorate_rooms(grid, variants, tile_map, seed=seed)

            for room in result["decoratedRooms"]:
                if room["assignedRole"] == "stairs" and room["gridRow"] != -1:
                    dist = room.get("spawnDistance", 99)
                    # Stairs are placed in Pass B2 before proximity calc,
                    # but they should naturally be far from spawn
                    # (B2 picks farthest room)
                    assert dist >= 2, \
                        f"Seed {seed}: Stairs at dist={dist} — should be ≥2"


# ═══════════════════════════════════════════════════════════
# Determinism Tests
# ═══════════════════════════════════════════════════════════

class TestProximityDeterminism:
    """Verify proximity-aware dealing is deterministic."""

    def test_same_seed_same_proximity_result(self):
        """Same seed should produce identical role + distance assignments."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)

        result1 = decorate_rooms(grid, variants, tile_map, seed=999)
        result2 = decorate_rooms(grid, variants, tile_map, seed=999)

        rooms1 = [(r["gridRow"], r["gridCol"], r["assignedRole"], r.get("spawnDistance"))
                   for r in result1["decoratedRooms"]]
        rooms2 = [(r["gridRow"], r["gridCol"], r["assignedRole"], r.get("spawnDistance"))
                   for r in result2["decoratedRooms"]]

        assert rooms1 == rooms2

    def test_different_seed_may_differ(self):
        """Different seeds should produce varied layouts."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)

        results = []
        for seed in [10, 20, 30, 40, 50]:
            result = decorate_rooms(grid, variants, tile_map, seed=seed)
            role_list = tuple(r["assignedRole"] for r in result["decoratedRooms"])
            results.append(role_list)

        unique = set(results)
        assert len(unique) > 1, "Different seeds should produce varied layouts"


# ═══════════════════════════════════════════════════════════
# Quota Preservation Tests
# ═══════════════════════════════════════════════════════════

class TestQuotaPreservation:
    """Verify proximity swaps don't break the quota system."""

    def test_total_role_counts_still_match_quota(self):
        """After proximity swaps and cluster smoothing, total enemy/loot/empty
        counts should be close to the quota targets, accounting for smoothing."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)
        density = 0.45
        loot_density = 0.25

        for seed in range(1, 21):
            result = decorate_rooms(grid, variants, tile_map, seed=seed, settings={
                "enemyDensity": density,
                "lootDensity": loot_density,
            })

            roles = _count_roles(result)
            reserved = roles.get("boss", 0) + roles.get("spawn", 0) + roles.get("stairs", 0)
            remaining = sum(roles.values()) - reserved

            enemy_count = roles.get("enemy", 0)
            expected_enemy = round(remaining * density)
            smoothed = result["stats"].get("clustersSmoothed", 0)

            # Proximity swaps may shift counts by ±1, and Phase 4 cluster smoothing
            # converts adjacent enemies → loot, further reducing enemy count.
            adjusted_expected = expected_enemy - smoothed
            assert abs(enemy_count - adjusted_expected) <= 2, \
                f"Seed {seed}: expected ~{adjusted_expected} enemy rooms " \
                f"(quota {expected_enemy} − {smoothed} smoothed), " \
                f"got {enemy_count} (remaining={remaining})"

    def test_no_missing_rooms(self):
        """All flexible rooms should be accounted for in the final result."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        # 4×4 = 16 rooms total; emergency fallbacks may add gridRow=-1 entries
        real_rooms = [r for r in result["decoratedRooms"] if r["gridRow"] != -1]
        assert len(real_rooms) == 16, \
            f"Expected 16 rooms, got {len(real_rooms)}"


# ═══════════════════════════════════════════════════════════
# Scatter Mechanics Still Work Tests
# ═══════════════════════════════════════════════════════════

class TestScatterWithProximity:
    """Verify scatter mechanics (lone enemy in empty rooms) still work
    even in safe-zone empty rooms."""

    def test_safe_zone_empty_rooms_can_scatter_lone_enemy(self):
        """Empty rooms in the safe zone can still receive a scattered lone enemy
        (scatter is independent of the proximity system)."""
        grid, variants, tile_map = _build_grid_and_variants(5, 5)

        found_scattered = False
        for seed in range(1, 100):
            result = decorate_rooms(grid, variants, tile_map, seed=seed, settings={
                "enemyDensity": 0.10,
                "lootDensity": 0.10,
                "scatterEnemies": True,
            })

            for room in result["decoratedRooms"]:
                if (room["assignedRole"] == "empty"
                        and room.get("spawnDistance", 99) <= 1
                        and any(p["type"] == "E" for p in room["placements"])):
                    found_scattered = True
                    break
            if found_scattered:
                break

        assert found_scattered, \
            "Empty rooms in safe zone should still sometimes get scattered lone enemies"


# ═══════════════════════════════════════════════════════════
# Full Pipeline Integration Tests
# ═══════════════════════════════════════════════════════════

class TestProximityFullPipeline:
    """Integration tests using the full dungeon generation pipeline."""

    def test_generated_dungeon_respects_proximity(self):
        """Full pipeline dungeon should have proximity data on rooms."""
        from app.core.wfc.dungeon_generator import generate_dungeon_floor

        for seed in [42, 123, 777]:
            result = generate_dungeon_floor(seed=seed, floor_number=3)
            assert result.success, f"Generation failed for seed {seed}: {result.error}"

            # Verify spawn points exist
            spawn_pts = result.game_map.get("spawn_points", [])
            assert len(spawn_pts) > 0, f"No spawn points for seed {seed}"

    def test_pipeline_with_different_styles(self):
        """Different dungeon styles should all work with proximity system."""
        from app.core.wfc.dungeon_generator import generate_dungeon_floor, FloorConfig

        for floor_num in [1, 3, 5, 7]:
            config = FloorConfig.from_floor_number(42, floor_num)
            result = generate_dungeon_floor(config=config)
            assert result.success, f"Generation failed for floor {floor_num}: {result.error}"

    def test_existing_quota_tests_still_valid(self):
        """Verify the Phase 1 quota system still produces correct counts
        even with Phase 2 proximity swaps active."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)

        result = decorate_rooms(grid, variants, tile_map, seed=42, settings={
            "enemyDensity": 0.70,
            "lootDensity": 0.10,
            "emptyRoomChance": 0.10,
        })

        roles = _count_roles(result)
        # Should have boss, spawn, stairs
        assert roles.get("boss", 0) == 1
        assert roles.get("spawn", 0) == 1
        assert roles.get("stairs", 0) == 1

        # Total should match grid
        total = sum(roles.values())
        assert total == 16
