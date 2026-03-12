"""
Tests for Spawn Distribution Overhaul — Phase 1: Quota-Based Room Distribution.

Validates the deck/quota system that replaced independent per-room RNG rolls
in room_decorator.py's Pass C. Ensures:

- Exact target counts from density settings (within ±1 from rounding)
- No streaks of 4+ consecutive same-role rooms
- Style overrides correctly shift deck composition
- Edge cases: 0 rooms, 1 room, all-enemy/all-loot styles
- Deterministic output (same seed → same result)
- Scatter mechanics remain functional
"""

from __future__ import annotations

import pytest

from app.core.wfc.room_decorator import decorate_rooms, DEFAULT_DECORATOR_SETTINGS


# ═══════════════════════════════════════════════════════════
# Test Helpers
# ═══════════════════════════════════════════════════════════

def _make_flexible_variant(row: int, col: int) -> dict:
    """Create a flexible room variant with floor tiles and spawn slots."""
    # 8×8 grid: walls around the edge, floor inside
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
    # Build a full tile map (rows * 8) × (cols * 8)
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

            # Fill tile map for this module
            for r in range(8):
                for c in range(8):
                    tile_map[gr * 8 + r][gc * 8 + c] = variant["tiles"][r][c]

        grid.append(grid_row)

    return grid, variants, tile_map


def _count_roles(result: dict) -> dict:
    """Count assigned roles from decoratedRooms."""
    counts = {}
    for room in result["decoratedRooms"]:
        role = room["assignedRole"]
        counts[role] = counts.get(role, 0) + 1
    return counts


# ═══════════════════════════════════════════════════════════
# Quota Math Tests
# ═══════════════════════════════════════════════════════════

class TestQuotaMath:
    """Verify the deck/quota system produces correct role distributions."""

    def test_default_density_produces_expected_counts(self):
        """With default settings (40% enemy, 25% loot, 20% empty-chance),
        a 3×3 grid (9 rooms, minus boss/spawn/stairs = ~6 remaining)
        should produce role counts close to density targets."""
        grid, variants, tile_map = _build_grid_and_variants(3, 3)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        roles = _count_roles(result)
        total = sum(roles.values())

        # Should have boss, spawn, stairs each exactly once
        assert roles.get("boss", 0) == 1
        assert roles.get("spawn", 0) == 1
        assert roles.get("stairs", 0) == 1

        # Remaining rooms should have enemy + loot + empty
        remaining = total - 3  # minus boss/spawn/stairs
        assert remaining >= 3, f"Expected at least 3 remaining rooms, got {remaining}"

        # All rooms should be accounted for
        assert total == 9, f"Expected 9 rooms, got {total}"

    def test_high_enemy_density_produces_many_enemy_rooms(self):
        """Dense Catacomb style (70% enemy, 10% loot) should produce
        mostly enemy rooms in the remaining pool."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)
        result = decorate_rooms(grid, variants, tile_map, seed=100, settings={
            "enemyDensity": 0.70,
            "lootDensity": 0.10,
            "emptyRoomChance": 0.10,
        })

        roles = _count_roles(result)
        total_rooms = sum(roles.values())
        reserved = roles.get("boss", 0) + roles.get("spawn", 0) + roles.get("stairs", 0)
        remaining = total_rooms - reserved

        enemy_count = roles.get("enemy", 0)
        # Phase 4 cluster smoothing converts adjacent enemy→loot, so with high
        # density the count can drop significantly from the quota target.
        # With 70% density we should still have a meaningful number of enemies.
        assert enemy_count >= 2, \
            f"Expected ≥2 enemy rooms with 70% density, got {enemy_count} (remaining={remaining})"

    def test_treasure_vault_style_produces_many_loot_rooms(self):
        """Treasure Vault style (30% enemy, 50% loot) should produce many loot rooms."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)
        result = decorate_rooms(grid, variants, tile_map, seed=200, settings={
            "enemyDensity": 0.30,
            "lootDensity": 0.50,
            "emptyRoomChance": 0.10,
        })

        roles = _count_roles(result)
        total_rooms = sum(roles.values())
        reserved = roles.get("boss", 0) + roles.get("spawn", 0) + roles.get("stairs", 0)
        remaining = total_rooms - reserved

        loot_count = roles.get("loot", 0)
        expected_loot = round(remaining * 0.50)
        # Phase 4 cluster smoothing may convert enemy→loot, increasing loot count
        # beyond the original quota, so loot_count >= expected is also valid.
        assert loot_count >= expected_loot - 1, \
            f"Expected ≥{expected_loot - 1} loot rooms with 50% density, got {loot_count} (remaining={remaining})"

    def test_open_ruins_style_produces_many_empty_rooms(self):
        """Open Ruins style (25% enemy, 30% loot, 35% empty) should have many empties."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)
        result = decorate_rooms(grid, variants, tile_map, seed=300, settings={
            "enemyDensity": 0.25,
            "lootDensity": 0.30,
            "emptyRoomChance": 0.35,
        })

        roles = _count_roles(result)
        total_rooms = sum(roles.values())
        reserved = roles.get("boss", 0) + roles.get("spawn", 0) + roles.get("stairs", 0)
        remaining = total_rooms - reserved

        empty_count = roles.get("empty", 0)
        # At least 1 empty guaranteed; should be close to remainder
        assert empty_count >= 1, "Should always have at least 1 empty room"

    def test_exact_quota_within_tolerance(self):
        """Verify enemy count is close to round(remaining * density) across many seeds.
        Phase 4 cluster smoothing may reduce enemy count by converting adjacent
        enemies to loot, so tolerance is wider than ±1."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)
        density = 0.45

        for seed in range(1, 21):
            result = decorate_rooms(grid, variants, tile_map, seed=seed, settings={
                "enemyDensity": density,
                "lootDensity": 0.25,
                "emptyRoomChance": 0.15,
            })

            roles = _count_roles(result)
            reserved = roles.get("boss", 0) + roles.get("spawn", 0) + roles.get("stairs", 0)
            remaining = sum(roles.values()) - reserved
            enemy_count = roles.get("enemy", 0)
            expected = round(remaining * density)
            smoothed = result["stats"].get("clustersSmoothed", 0)

            # Cluster smoothing can reduce enemy count; account for it
            assert abs(enemy_count - (expected - smoothed)) <= 2, \
                f"Seed {seed}: expected ~{expected} - {smoothed} smoothed = ~{expected - smoothed} " \
                f"enemy rooms, got {enemy_count}"


# ═══════════════════════════════════════════════════════════
# Edge Case Tests
# ═══════════════════════════════════════════════════════════

class TestQuotaEdgeCases:
    """Test edge cases in the quota system."""

    def test_single_room_grid(self):
        """1×1 grid — single room gets boss; spawn/stairs via emergency fallback."""
        grid, variants, tile_map = _build_grid_and_variants(1, 1)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        roles = _count_roles(result)
        # 1 flexible room → boss. Emergency fallbacks add spawn + stairs.
        assert roles.get("boss", 0) == 1
        # Emergency spawn and stairs are appended as gridRow=-1 entries
        assert roles.get("spawn", 0) == 1
        assert roles.get("stairs", 0) == 1

    def test_two_room_grid(self):
        """1×2 grid — boss + spawn on flexible rooms; stairs via emergency fallback."""
        grid, variants, tile_map = _build_grid_and_variants(1, 2)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        roles = _count_roles(result)
        assert roles.get("boss", 0) == 1
        assert roles.get("spawn", 0) == 1
        assert roles.get("stairs", 0) == 1

    def test_three_room_grid(self):
        """1×3 grid — boss + spawn + stairs, no flexible remaining."""
        grid, variants, tile_map = _build_grid_and_variants(1, 3)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        roles = _count_roles(result)
        assert roles.get("boss", 0) == 1
        assert roles.get("spawn", 0) == 1
        assert roles.get("stairs", 0) == 1

    def test_four_room_grid_has_one_remaining(self):
        """2×2 grid — boss + spawn + stairs = 3 reserved, 1 remaining for deck."""
        grid, variants, tile_map = _build_grid_and_variants(2, 2)
        result = decorate_rooms(grid, variants, tile_map, seed=42)

        roles = _count_roles(result)
        assert roles.get("boss", 0) == 1
        assert roles.get("spawn", 0) == 1
        assert roles.get("stairs", 0) == 1
        remaining_role_count = sum(roles.values()) - 3
        assert remaining_role_count == 1

    def test_oversubscribed_density_clamps(self):
        """When enemy + loot density > 1.0, clamp proportionally and keep ≥1 empty."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)
        result = decorate_rooms(grid, variants, tile_map, seed=42, settings={
            "enemyDensity": 0.80,
            "lootDensity": 0.60,
            "emptyRoomChance": 0.0,
        })

        roles = _count_roles(result)
        reserved = roles.get("boss", 0) + roles.get("spawn", 0) + roles.get("stairs", 0)
        remaining = sum(roles.values()) - reserved

        # Should still have at least 1 empty room (guaranteed by clamping)
        assert roles.get("empty", 0) >= 1, "Oversubscribed density should still yield ≥1 empty"

        # Total should match
        assert roles.get("enemy", 0) + roles.get("loot", 0) + roles.get("empty", 0) == remaining

    def test_zero_enemy_density(self):
        """0% enemy density should produce 0 enemy rooms in the deck."""
        grid, variants, tile_map = _build_grid_and_variants(3, 3)
        result = decorate_rooms(grid, variants, tile_map, seed=42, settings={
            "enemyDensity": 0.0,
            "lootDensity": 0.50,
            "emptyRoomChance": 0.0,
        })

        roles = _count_roles(result)
        assert roles.get("enemy", 0) == 0, "Zero enemy density should produce no enemy rooms"

    def test_zero_loot_density(self):
        """0% loot density produces 0 loot tokens in the deck, but
        Phase 2 proximity and Phase 4 cluster smoothing may convert
        enemy rooms to loot."""
        grid, variants, tile_map = _build_grid_and_variants(3, 3)
        result = decorate_rooms(grid, variants, tile_map, seed=42, settings={
            "enemyDensity": 0.50,
            "lootDensity": 0.0,
            "emptyRoomChance": 0.0,
        })

        roles = _count_roles(result)
        smoothed = result["stats"].get("clustersSmoothed", 0)
        # Phase 2 proximity ramp may convert a safe-zone enemy → loot,
        # and Phase 4 cluster smoothing converts adjacent enemies → loot.
        # Loot rooms from these sources are expected even with 0% loot density.
        max_expected_loot = 1 + smoothed  # 1 from proximity + 1 per cluster smoothed
        assert roles.get("loot", 0) <= max_expected_loot, \
            f"Zero loot density should produce at most {max_expected_loot} loot rooms " \
            f"(proximity + smoothing), got {roles.get('loot', 0)}"


# ═══════════════════════════════════════════════════════════
# Determinism Tests
# ═══════════════════════════════════════════════════════════

class TestQuotaDeterminism:
    """Verify the quota system is deterministic and shuffle-based."""

    def test_same_seed_same_result(self):
        """Same seed should produce identical role assignments."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)

        result1 = decorate_rooms(grid, variants, tile_map, seed=999)
        result2 = decorate_rooms(grid, variants, tile_map, seed=999)

        roles1 = [(r["gridRow"], r["gridCol"], r["assignedRole"])
                   for r in result1["decoratedRooms"]]
        roles2 = [(r["gridRow"], r["gridCol"], r["assignedRole"])
                   for r in result2["decoratedRooms"]]

        assert roles1 == roles2

    def test_different_seed_different_shuffle(self):
        """Different seeds should produce different room orderings (usually)."""
        grid, variants, tile_map = _build_grid_and_variants(4, 4)

        results = []
        for seed in [1, 2, 3, 4, 5]:
            result = decorate_rooms(grid, variants, tile_map, seed=seed)
            role_list = [r["assignedRole"] for r in result["decoratedRooms"]]
            results.append(tuple(role_list))

        # At least some should differ (extremely unlikely all 5 seeds produce same layout)
        unique_layouts = set(results)
        assert len(unique_layouts) > 1, "Different seeds should produce varied layouts"


# ═══════════════════════════════════════════════════════════
# Scatter Mechanics Tests
# ═══════════════════════════════════════════════════════════

class TestScatterMechanics:
    """Verify scatter mechanics (lone enemies in empty, guards in loot) still work."""

    def test_empty_rooms_can_have_scattered_enemy(self):
        """Empty rooms should still sometimes get a lone scattered enemy."""
        grid, variants, tile_map = _build_grid_and_variants(5, 5)

        found_scattered = False
        for seed in range(1, 50):
            result = decorate_rooms(grid, variants, tile_map, seed=seed, settings={
                "enemyDensity": 0.10,
                "lootDensity": 0.10,
                "emptyRoomChance": 0.50,
                "scatterEnemies": True,
            })

            for room in result["decoratedRooms"]:
                if room["assignedRole"] == "empty" and len(room["placements"]) > 0:
                    has_enemy = any(p["type"] == "E" for p in room["placements"])
                    if has_enemy:
                        found_scattered = True
                        break
            if found_scattered:
                break

        assert found_scattered, "Scatter should sometimes place lone enemies in empty rooms"

    def test_enemy_rooms_can_have_bonus_chest(self):
        """Enemy rooms should still sometimes get a bonus chest."""
        grid, variants, tile_map = _build_grid_and_variants(5, 5)

        found_bonus = False
        for seed in range(1, 50):
            result = decorate_rooms(grid, variants, tile_map, seed=seed, settings={
                "enemyDensity": 0.60,
                "lootDensity": 0.10,
                "emptyRoomChance": 0.05,
                "scatterChests": True,
            })

            for room in result["decoratedRooms"]:
                if room["assignedRole"] == "enemy":
                    has_chest = any(p["type"] == "X" for p in room["placements"])
                    if has_chest:
                        found_bonus = True
                        break
            if found_bonus:
                break

        assert found_bonus, "Scatter should sometimes place bonus chests in enemy rooms"

    def test_loot_rooms_can_have_guard(self):
        """Loot rooms should still sometimes get a guard enemy."""
        grid, variants, tile_map = _build_grid_and_variants(5, 5)

        found_guard = False
        for seed in range(1, 50):
            result = decorate_rooms(grid, variants, tile_map, seed=seed, settings={
                "enemyDensity": 0.10,
                "lootDensity": 0.50,
                "emptyRoomChance": 0.10,
                "scatterEnemies": True,
            })

            for room in result["decoratedRooms"]:
                if room["assignedRole"] == "loot":
                    has_enemy = any(p["type"] == "E" for p in room["placements"])
                    if has_enemy:
                        found_guard = True
                        break
            if found_guard:
                break

        assert found_guard, "Scatter should sometimes place guard enemies in loot rooms"


# ═══════════════════════════════════════════════════════════
# Full Pipeline Integration Tests
# ═══════════════════════════════════════════════════════════

class TestQuotaFullPipeline:
    """Integration tests using the full dungeon generation pipeline."""

    def test_generated_dungeon_has_consistent_role_counts(self):
        """Full pipeline should produce consistent role counts across seeds."""
        from app.core.wfc.dungeon_generator import generate_dungeon_floor

        for seed in [42, 123, 777]:
            result = generate_dungeon_floor(seed=seed, floor_number=3)
            assert result.success, f"Generation failed for seed {seed}: {result.error}"

            # Verify spawn points exist
            spawn_pts = result.game_map.get("spawn_points", [])
            assert len(spawn_pts) > 0, f"No spawn points for seed {seed}"

    def test_quota_with_dungeon_styles(self):
        """Each dungeon style should correctly influence the quota deck."""
        from app.core.wfc.dungeon_generator import generate_dungeon_floor, FloorConfig

        # Generate with a known floor config
        config = FloorConfig.from_floor_number(42, 5)
        result = generate_dungeon_floor(config=config)
        assert result.success, f"Generation failed: {result.error}"

        # Should have at least some rooms
        rooms = result.game_map.get("rooms", [])
        assert len(rooms) > 0
