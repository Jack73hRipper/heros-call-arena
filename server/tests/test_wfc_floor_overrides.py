"""
Tests for Spawn Distribution Overhaul — Phase 5: Early-Floor Rarity Tuning.

Validates the floor_overrides system that reduces early-floor spike danger
by applying per-floor-tier caps to enhanced enemy count, rare affix count,
and rare minion count.

Ensures:
- get_floor_override() returns correct overrides for each floor tier
- get_floor_override() returns empty dict for uncovered floors (6+)
- Missing floor_overrides config is backward-compatible (empty dict)
- Floor 1-3 rooms never have more than 1 enhanced enemy
- Floor 1-3 rares have at most 2 affixes
- Floor 4-5 rares get exactly 2 affixes
- Floor 6+ behavior is unchanged from base config
- Floor-specific max_rare_minions caps minion spawning
- Config is backward-compatible (missing floor_overrides → base values)
- Full pipeline integration: export_to_game_map respects floor overrides
"""

from __future__ import annotations

import json
import random
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.core.monster_rarity import (
    load_monster_rarity_config,
    clear_monster_rarity_cache,
    get_floor_override,
    get_spawn_chances,
    get_room_budget,
    get_rarity_cost,
)


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear monster rarity config cache before each test."""
    clear_monster_rarity_cache()
    yield
    clear_monster_rarity_cache()


# ═══════════════════════════════════════════════════════════
# 1. get_floor_override() — Floor-tier override lookup
# ═══════════════════════════════════════════════════════════

class TestFloorOverrideLookup:
    """Verify floor_overrides lookup returns correct tier for each floor."""

    def test_floor_1_returns_tier_1_override(self):
        override = get_floor_override(1)
        assert override.get("max_floor") == 3

    def test_floor_2_returns_tier_1_override(self):
        override = get_floor_override(2)
        assert override.get("max_floor") == 3

    def test_floor_3_returns_tier_1_override(self):
        override = get_floor_override(3)
        assert override.get("max_floor") == 3

    def test_floor_4_returns_tier_2_override(self):
        override = get_floor_override(4)
        assert override.get("max_floor") == 5

    def test_floor_5_returns_tier_2_override(self):
        override = get_floor_override(5)
        assert override.get("max_floor") == 5

    def test_floor_6_returns_empty_dict(self):
        """Floors 6+ have no overrides — use base config values."""
        override = get_floor_override(6)
        assert override == {}

    def test_floor_10_returns_empty_dict(self):
        override = get_floor_override(10)
        assert override == {}

    def test_floor_99_returns_empty_dict(self):
        override = get_floor_override(99)
        assert override == {}


# ═══════════════════════════════════════════════════════════
# 2. Floor override config values
# ═══════════════════════════════════════════════════════════

class TestFloorOverrideValues:
    """Verify the specific override values for each floor tier."""

    def test_tier_1_max_enhanced_is_1(self):
        override = get_floor_override(1)
        assert override.get("max_enhanced_per_room") == 1

    def test_tier_1_max_rare_minions_is_1(self):
        override = get_floor_override(1)
        assert override.get("max_rare_minions") == 1

    def test_tier_1_rare_affix_count_is_1_2(self):
        override = get_floor_override(2)
        assert override.get("rare_affix_count") == [1, 2]

    def test_tier_2_max_enhanced_is_2(self):
        override = get_floor_override(4)
        assert override.get("max_enhanced_per_room") == 2

    def test_tier_2_max_rare_minions_is_2(self):
        override = get_floor_override(5)
        assert override.get("max_rare_minions") == 2

    def test_tier_2_rare_affix_count_is_2_2(self):
        override = get_floor_override(4)
        assert override.get("rare_affix_count") == [2, 2]


# ═══════════════════════════════════════════════════════════
# 3. Config structure in monster_rarity_config.json
# ═══════════════════════════════════════════════════════════

class TestFloorOverrideConfig:
    """Verify the floor_overrides section exists and is well-formed."""

    def test_floor_overrides_in_spawn_chances(self):
        spawn_chances = get_spawn_chances()
        assert "floor_overrides" in spawn_chances

    def test_floor_overrides_is_list(self):
        spawn_chances = get_spawn_chances()
        assert isinstance(spawn_chances["floor_overrides"], list)

    def test_floor_overrides_has_two_tiers(self):
        spawn_chances = get_spawn_chances()
        overrides = spawn_chances["floor_overrides"]
        assert len(overrides) == 2

    def test_each_tier_has_required_keys(self):
        spawn_chances = get_spawn_chances()
        overrides = spawn_chances["floor_overrides"]
        required_keys = {"max_floor", "max_enhanced_per_room", "max_rare_minions", "rare_affix_count"}
        for tier in overrides:
            for key in required_keys:
                assert key in tier, f"Floor override tier missing key: {key}"

    def test_floor_overrides_sorted_ascending(self):
        spawn_chances = get_spawn_chances()
        overrides = spawn_chances["floor_overrides"]
        for i in range(len(overrides) - 1):
            assert overrides[i]["max_floor"] < overrides[i + 1]["max_floor"], (
                f"floor_overrides should be sorted ascending by max_floor"
            )


# ═══════════════════════════════════════════════════════════
# 4. Backward compatibility — missing floor_overrides
# ═══════════════════════════════════════════════════════════

class TestFloorOverrideBackwardCompat:
    """Verify behavior when floor_overrides is absent from config."""

    def test_missing_floor_overrides_returns_empty_dict(self):
        """If config has no floor_overrides key, get_floor_override returns {}."""
        fake_config = {
            "spawn_chances": {
                "champion_base_chance": 0.04,
                "max_enhanced_per_room": 2,
            },
            "rarity_tiers": {},
        }
        with patch("app.core.monster_rarity._config_cache", fake_config):
            with patch("app.core.monster_rarity.load_monster_rarity_config", return_value=fake_config):
                override = get_floor_override(1)
                assert override == {}

    def test_empty_floor_overrides_returns_empty_dict(self):
        """If floor_overrides is an empty list, all floors get no overrides."""
        fake_config = {
            "spawn_chances": {
                "floor_overrides": [],
                "max_enhanced_per_room": 2,
            },
            "rarity_tiers": {},
        }
        with patch("app.core.monster_rarity._config_cache", fake_config):
            with patch("app.core.monster_rarity.load_monster_rarity_config", return_value=fake_config):
                override = get_floor_override(1)
                assert override == {}


# ═══════════════════════════════════════════════════════════
# 5. Pipeline integration — max_enhanced_per_room overrides
# ═══════════════════════════════════════════════════════════

class TestFloorOverrideMaxEnhanced:
    """Verify floor-specific max_enhanced_per_room in export pipeline."""

    @staticmethod
    def _make_enemy_room_tile_map(enemy_count: int = 4):
        tile_map = []
        enemy_placed = 0
        for r in range(8):
            row = []
            for c in range(8):
                if r == 0 or r == 7 or c == 0 or c == 7:
                    row.append("W")
                elif enemy_placed < enemy_count:
                    row.append("E")
                    enemy_placed += 1
                else:
                    row.append("F")
            tile_map.append(row)
        return tile_map

    @staticmethod
    def _make_grid_and_variants(enemy_count: int = 4):
        tile_map = TestFloorOverrideMaxEnhanced._make_enemy_room_tile_map(enemy_count)
        variant = {"purpose": "enemy", "sourceName": "Test Enemy Room"}
        grid = [[{"chosenVariant": 0}]]
        variants = [variant]
        return tile_map, grid, variants

    def test_floor_1_max_1_enhanced(self):
        """On floor 1, even with all-champion rolls, only 1 enhanced enemy allowed."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=4)

        with patch("app.core.monster_rarity.roll_monster_rarity", return_value="champion"):
            result = export_to_game_map(
                tile_map, grid, variants,
                floor_number=1,
                seed=42,
            )

        rooms = result.get("rooms", [])
        assert len(rooms) >= 1
        spawns = rooms[0].get("enemy_spawns", [])
        enhanced = [s for s in spawns if s["monster_rarity"] != "normal"]
        assert len(enhanced) <= 1, (
            f"Floor 1 should allow at most 1 enhanced enemy (got {len(enhanced)})"
        )

    def test_floor_3_max_1_enhanced(self):
        """Floor 3 still in tier 1 — max 1 enhanced."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=3)

        with patch("app.core.monster_rarity.roll_monster_rarity", return_value="rare"):
            result = export_to_game_map(
                tile_map, grid, variants,
                floor_number=3,
                seed=42,
            )

        rooms = result.get("rooms", [])
        spawns = rooms[0].get("enemy_spawns", [])
        enhanced = [s for s in spawns if s["monster_rarity"] != "normal"]
        assert len(enhanced) <= 1, (
            f"Floor 3 should allow at most 1 enhanced enemy (got {len(enhanced)})"
        )

    def test_floor_4_allows_2_enhanced(self):
        """Floor 4 enters tier 2 — max 2 enhanced (same as base config)."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=4)

        with patch("app.core.monster_rarity.roll_monster_rarity", return_value="champion"):
            result = export_to_game_map(
                tile_map, grid, variants,
                floor_number=4,
                seed=42,
            )

        rooms = result.get("rooms", [])
        spawns = rooms[0].get("enemy_spawns", [])
        enhanced = [s for s in spawns if s["monster_rarity"] != "normal"]
        assert len(enhanced) == 2, (
            f"Floor 4 should allow exactly 2 enhanced enemies (got {len(enhanced)})"
        )

    def test_floor_6_uses_base_config(self):
        """Floor 6 has no override — uses base max_enhanced_per_room=2."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=4)

        with patch("app.core.monster_rarity.roll_monster_rarity", return_value="champion"):
            result = export_to_game_map(
                tile_map, grid, variants,
                floor_number=6,
                seed=42,
            )

        rooms = result.get("rooms", [])
        spawns = rooms[0].get("enemy_spawns", [])
        enhanced = [s for s in spawns if s["monster_rarity"] != "normal"]
        assert len(enhanced) == 2, (
            f"Floor 6 should use base max_enhanced_per_room=2 (got {len(enhanced)})"
        )


# ═══════════════════════════════════════════════════════════
# 6. Pipeline integration — rare_affix_count overrides
# ═══════════════════════════════════════════════════════════

class TestFloorOverrideAffixCount:
    """Verify floor-specific rare affix count in export pipeline."""

    @staticmethod
    def _make_grid_and_variants(enemy_count: int = 1):
        tile_map = []
        enemy_placed = 0
        for r in range(8):
            row = []
            for c in range(8):
                if r == 0 or r == 7 or c == 0 or c == 7:
                    row.append("W")
                elif enemy_placed < enemy_count:
                    row.append("E")
                    enemy_placed += 1
                else:
                    row.append("F")
            tile_map.append(row)
        variant = {"purpose": "enemy", "sourceName": "Test Room"}
        grid = [[{"chosenVariant": 0}]]
        variants = [variant]
        return tile_map, grid, variants

    def test_floor_1_rare_gets_1_or_2_affixes(self):
        """Floor 1-3 rares should get 1-2 affixes (not 2-3)."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=1)

        results = set()
        for seed in range(50):
            clear_monster_rarity_cache()
            with patch("app.core.monster_rarity.roll_monster_rarity", return_value="rare"):
                result = export_to_game_map(
                    tile_map, grid, variants,
                    floor_number=1,
                    seed=seed,
                )

            rooms = result.get("rooms", [])
            if rooms:
                spawns = rooms[0].get("enemy_spawns", [])
                for s in spawns:
                    if s["monster_rarity"] == "rare":
                        affix_count = len(s.get("affixes", []))
                        results.add(affix_count)
                        assert affix_count <= 2, (
                            f"Floor 1 rare should have at most 2 affixes (got {affix_count})"
                        )

        # Should see both 1 and 2 across 50 seeds (statistical)
        assert 1 in results or 2 in results, "Should produce at least one rare with affixes"

    def test_floor_3_rare_max_2_affixes(self):
        """Floor 3 rares capped at 2 affixes."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=1)

        for seed in range(20):
            clear_monster_rarity_cache()
            with patch("app.core.monster_rarity.roll_monster_rarity", return_value="rare"):
                result = export_to_game_map(
                    tile_map, grid, variants,
                    floor_number=3,
                    seed=seed,
                )

            rooms = result.get("rooms", [])
            if rooms:
                spawns = rooms[0].get("enemy_spawns", [])
                for s in spawns:
                    if s["monster_rarity"] == "rare":
                        affix_count = len(s.get("affixes", []))
                        assert affix_count <= 2, (
                            f"Floor 3 rare should have at most 2 affixes (got {affix_count})"
                        )

    def test_floor_4_rare_gets_exactly_2_affixes(self):
        """Floor 4-5 rares should always get exactly 2 affixes."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=1)

        for seed in range(20):
            clear_monster_rarity_cache()
            with patch("app.core.monster_rarity.roll_monster_rarity", return_value="rare"):
                result = export_to_game_map(
                    tile_map, grid, variants,
                    floor_number=4,
                    seed=seed,
                )

            rooms = result.get("rooms", [])
            if rooms:
                spawns = rooms[0].get("enemy_spawns", [])
                for s in spawns:
                    if s["monster_rarity"] == "rare":
                        affix_count = len(s.get("affixes", []))
                        assert affix_count == 2, (
                            f"Floor 4 rare should have exactly 2 affixes (got {affix_count})"
                        )

    def test_floor_7_rare_uses_base_2_3_affixes(self):
        """Floor 7+ uses base config — rares get 2-3 affixes."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=1)

        results = set()
        for seed in range(50):
            clear_monster_rarity_cache()
            with patch("app.core.monster_rarity.roll_monster_rarity", return_value="rare"):
                result = export_to_game_map(
                    tile_map, grid, variants,
                    floor_number=7,
                    seed=seed,
                )

            rooms = result.get("rooms", [])
            if rooms:
                spawns = rooms[0].get("enemy_spawns", [])
                for s in spawns:
                    if s["monster_rarity"] == "rare":
                        affix_count = len(s.get("affixes", []))
                        results.add(affix_count)
                        assert 2 <= affix_count <= 3, (
                            f"Floor 7 rare should have 2-3 affixes (got {affix_count})"
                        )

        # Across 50 seeds we expect to see both 2 and 3
        assert len(results) >= 1, "Should produce at least some rare affixes"


# ═══════════════════════════════════════════════════════════
# 7. Floor override interaction with difficulty budget
# ═══════════════════════════════════════════════════════════

class TestFloorOverrideBudgetInteraction:
    """Verify floor overrides work alongside the difficulty budget system."""

    @staticmethod
    def _make_grid_and_variants(enemy_count: int = 4):
        tile_map = []
        enemy_placed = 0
        for r in range(8):
            row = []
            for c in range(8):
                if r == 0 or r == 7 or c == 0 or c == 7:
                    row.append("W")
                elif enemy_placed < enemy_count:
                    row.append("E")
                    enemy_placed += 1
                else:
                    row.append("F")
            tile_map.append(row)
        variant = {"purpose": "enemy", "sourceName": "Test Room"}
        grid = [[{"chosenVariant": 0}]]
        variants = [variant]
        return tile_map, grid, variants

    def test_floor_1_both_budget_and_override_constrain(self):
        """On floor 1, both budget AND max_enhanced=1 apply — strictest wins."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=4)

        # Force all to rare — budget=10, rare costs 5, but max_enhanced=1 caps first
        with patch("app.core.monster_rarity.roll_monster_rarity", return_value="rare"):
            result = export_to_game_map(
                tile_map, grid, variants,
                floor_number=1,
                seed=42,
            )

        rooms = result.get("rooms", [])
        spawns = rooms[0].get("enemy_spawns", [])
        enhanced = [s for s in spawns if s["monster_rarity"] != "normal"]
        assert len(enhanced) <= 1, (
            f"Floor 1 override (max_enhanced=1) should cap at 1 even with budget room"
        )

    def test_floor_5_budget_allows_2_champions(self):
        """Floor 5: max_enhanced=2 and budget=18 easily fits 2 champions (3×2=6)."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=4)

        with patch("app.core.monster_rarity.roll_monster_rarity", return_value="champion"):
            result = export_to_game_map(
                tile_map, grid, variants,
                floor_number=5,
                seed=42,
            )

        rooms = result.get("rooms", [])
        spawns = rooms[0].get("enemy_spawns", [])
        enhanced = [s for s in spawns if s["monster_rarity"] != "normal"]
        assert len(enhanced) == 2


# ═══════════════════════════════════════════════════════════
# 8. Determinism
# ═══════════════════════════════════════════════════════════

class TestFloorOverrideDeterminism:
    """Verify same seed produces identical results with floor overrides."""

    @staticmethod
    def _make_grid_and_variants(enemy_count: int = 3):
        tile_map = []
        enemy_placed = 0
        for r in range(8):
            row = []
            for c in range(8):
                if r == 0 or r == 7 or c == 0 or c == 7:
                    row.append("W")
                elif enemy_placed < enemy_count:
                    row.append("E")
                    enemy_placed += 1
                else:
                    row.append("F")
            tile_map.append(row)
        variant = {"purpose": "enemy", "sourceName": "Test Room"}
        grid = [[{"chosenVariant": 0}]]
        variants = [variant]
        return tile_map, grid, variants

    def test_floor_1_deterministic(self):
        """Same seed on floor 1 produces identical overridden output."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=3)

        results = []
        for _ in range(3):
            clear_monster_rarity_cache()
            result = export_to_game_map(
                tile_map, grid, variants,
                floor_number=1,
                seed=777,
            )
            rooms = result.get("rooms", [])
            if rooms:
                rarities = tuple(s["monster_rarity"] for s in rooms[0].get("enemy_spawns", []))
                affix_counts = tuple(len(s.get("affixes", [])) for s in rooms[0].get("enemy_spawns", []))
                results.append((rarities, affix_counts))

        assert len(results) == 3
        assert results[0] == results[1] == results[2], "Same seed must produce identical results"

    def test_floor_4_deterministic(self):
        """Same seed on floor 4 produces identical overridden output."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=3)

        results = []
        for _ in range(3):
            clear_monster_rarity_cache()
            result = export_to_game_map(
                tile_map, grid, variants,
                floor_number=4,
                seed=999,
            )
            rooms = result.get("rooms", [])
            if rooms:
                rarities = tuple(s["monster_rarity"] for s in rooms[0].get("enemy_spawns", []))
                affix_counts = tuple(len(s.get("affixes", [])) for s in rooms[0].get("enemy_spawns", []))
                results.append((rarities, affix_counts))

        assert len(results) == 3
        assert results[0] == results[1] == results[2], "Same seed must produce identical results"


# ═══════════════════════════════════════════════════════════
# 9. Edge cases
# ═══════════════════════════════════════════════════════════

class TestFloorOverrideEdgeCases:
    """Test edge cases in floor override logic."""

    def test_floor_0_returns_tier_1(self):
        """Floor 0 (invalid but possible) should match first tier."""
        override = get_floor_override(0)
        assert override.get("max_floor") == 3

    def test_negative_floor_returns_tier_1(self):
        """Negative floor should match first tier (≤ max_floor=3)."""
        override = get_floor_override(-1)
        assert override.get("max_floor") == 3

    def test_single_enemy_room_floor_1_allows_champion(self):
        """Single enemy on floor 1: max_enhanced=1 allows 1 champion."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map = []
        enemy_placed = 0
        for r in range(8):
            row = []
            for c in range(8):
                if r == 0 or r == 7 or c == 0 or c == 7:
                    row.append("W")
                elif enemy_placed < 1:
                    row.append("E")
                    enemy_placed += 1
                else:
                    row.append("F")
            tile_map.append(row)

        variant = {"purpose": "enemy", "sourceName": "Test Room"}
        grid = [[{"chosenVariant": 0}]]
        variants = [variant]

        with patch("app.core.monster_rarity.roll_monster_rarity", return_value="champion"):
            result = export_to_game_map(
                tile_map, grid, variants,
                floor_number=1,
                seed=42,
            )

        rooms = result.get("rooms", [])
        spawns = rooms[0].get("enemy_spawns", [])
        assert len(spawns) == 1
        assert spawns[0]["monster_rarity"] == "champion", (
            "Single enemy room on floor 1 should allow the 1 champion"
        )

    def test_override_does_not_affect_boss_tiles(self):
        """Boss ('B') tiles are never affected by floor overrides."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map = []
        for r in range(8):
            row = []
            for c in range(8):
                if r == 0 or r == 7 or c == 0 or c == 7:
                    row.append("W")
                elif r == 1 and c == 1:
                    row.append("B")
                else:
                    row.append("F")
            tile_map.append(row)

        variant = {"purpose": "boss", "sourceName": "Boss Room"}
        grid = [[{"chosenVariant": 0}]]
        variants = [variant]

        result = export_to_game_map(
            tile_map, grid, variants,
            floor_number=1,
            seed=42,
        )

        rooms = result.get("rooms", [])
        assert len(rooms) >= 1
        spawns = rooms[0].get("enemy_spawns", [])
        boss_spawns = [s for s in spawns if s.get("is_boss")]
        for bs in boss_spawns:
            assert bs["monster_rarity"] in ("normal", "super_unique"), (
                f"Boss should be normal or super_unique, got {bs['monster_rarity']}"
            )
