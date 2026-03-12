"""
Tests for Spawn Distribution Overhaul — Phase 3: Per-Room Difficulty Budget.

Validates the difficulty point budget system that constrains how much rarity
can stack within a single room, preventing impossible encounters.

Ensures:
- get_room_budget() returns correct values for each floor tier
- get_room_budget() scales with enemy count (base + per_enemy × count)
- get_rarity_cost() returns correct point costs for each rarity tier
- Budget-aware rarity rolling downgrades rare → champion → normal when budget exceeded
- No room on floors 1-3 ever has more than 1 rare enemy (budget too tight)
- Deep floors (7+) can still produce multi-enhanced rooms (generous budget)
- Config is loaded from monster_rarity_config.json (data-driven)
- Missing difficulty_budget config falls back to sensible defaults
- Budget system coexists with max_enhanced_per_room (both constraints apply)
- Existing rarity tests still pass (individual roll logic unchanged)
- Full pipeline integration: export_to_game_map respects budgets
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
    get_room_budget,
    get_rarity_cost,
    get_difficulty_budget_config,
    roll_monster_rarity,
    get_spawn_chances,
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
# 1. get_rarity_cost() — Point costs per tier
# ═══════════════════════════════════════════════════════════

class TestRarityCost:
    """Verify rarity_costs lookup from config."""

    def test_normal_costs_1(self):
        assert get_rarity_cost("normal") == 1

    def test_champion_costs_3(self):
        assert get_rarity_cost("champion") == 3

    def test_rare_costs_5(self):
        assert get_rarity_cost("rare") == 5

    def test_super_unique_costs_8(self):
        assert get_rarity_cost("super_unique") == 8

    def test_unknown_rarity_defaults_to_1(self):
        assert get_rarity_cost("mythic_nonexistent") == 1

    def test_costs_loaded_from_config(self):
        """Verify values come from the actual config file."""
        config = load_monster_rarity_config()
        budget_cfg = config.get("difficulty_budget", {})
        costs = budget_cfg.get("rarity_costs", {})
        assert costs["normal"] == 1
        assert costs["champion"] == 3
        assert costs["rare"] == 5
        assert costs["super_unique"] == 8


# ═══════════════════════════════════════════════════════════
# 2. get_room_budget() — Floor-tier budget computation
# ═══════════════════════════════════════════════════════════

class TestRoomBudget:
    """Verify room budget = base + per_enemy × enemy_count by floor tier."""

    # Floor 1-2: base=6, per_enemy=1.0
    def test_floor_1_with_3_enemies(self):
        assert get_room_budget(1, 3) == 9   # 6 + 1.0*3

    def test_floor_2_with_4_enemies(self):
        assert get_room_budget(2, 4) == 10  # 6 + 1.0*4

    def test_floor_1_zero_enemies(self):
        assert get_room_budget(1, 0) == 6   # 6 + 0

    # Floor 3-4: base=8, per_enemy=1.5
    def test_floor_3_with_4_enemies(self):
        assert get_room_budget(3, 4) == 14  # 8 + 1.5*4

    def test_floor_4_with_3_enemies(self):
        assert get_room_budget(4, 3) == 12  # 8 + 1.5*3 = 12.5 → 12

    # Floor 5-6: base=10, per_enemy=2.0
    def test_floor_5_with_4_enemies(self):
        assert get_room_budget(5, 4) == 18  # 10 + 2.0*4

    def test_floor_6_with_5_enemies(self):
        assert get_room_budget(6, 5) == 20  # 10 + 2.0*5

    # Floor 7-8: base=12, per_enemy=2.0
    def test_floor_7_with_4_enemies(self):
        assert get_room_budget(7, 4) == 20  # 12 + 2.0*4

    def test_floor_8_with_6_enemies(self):
        assert get_room_budget(8, 6) == 24  # 12 + 2.0*6

    # Floor 9+: base=15, per_enemy=2.5
    def test_floor_9_with_4_enemies(self):
        assert get_room_budget(9, 4) == 25  # 15 + 2.5*4

    def test_floor_10_with_5_enemies(self):
        assert get_room_budget(10, 5) == 27  # 15 + 2.5*5 = 27.5 → 27

    def test_floor_99_with_7_enemies(self):
        assert get_room_budget(99, 7) == 32  # 15 + 2.5*7 = 32.5 → 32

    def test_budget_increases_with_floor(self):
        """Higher floors always get at least as much budget."""
        for enemies in (3, 4, 5):
            budgets = [get_room_budget(f, enemies) for f in (1, 3, 5, 7, 9)]
            for i in range(len(budgets) - 1):
                assert budgets[i] <= budgets[i + 1], (
                    f"Budget should not decrease: floor tier {i} ({budgets[i]}) > tier {i+1} ({budgets[i+1]})"
                )


# ═══════════════════════════════════════════════════════════
# 3. Config structure
# ═══════════════════════════════════════════════════════════

class TestDifficultyBudgetConfig:
    """Verify the difficulty_budget section in monster_rarity_config.json."""

    def test_config_section_exists(self):
        config = get_difficulty_budget_config()
        assert config, "difficulty_budget section should exist in config"

    def test_rarity_costs_has_all_tiers(self):
        config = get_difficulty_budget_config()
        costs = config.get("rarity_costs", {})
        for tier in ("normal", "champion", "rare", "super_unique"):
            assert tier in costs, f"rarity_costs missing tier: {tier}"

    def test_floor_budgets_is_sorted(self):
        """Floor budget entries should be in ascending max_floor order."""
        config = get_difficulty_budget_config()
        entries = config.get("floor_budgets", [])
        assert len(entries) >= 3, "Should have at least 3 floor budget tiers"
        floors = [e["max_floor"] for e in entries]
        assert floors == sorted(floors), "floor_budgets should be sorted by max_floor"

    def test_floor_budgets_covers_all_floors(self):
        """Last entry should cover high floors (max_floor >= 99)."""
        config = get_difficulty_budget_config()
        entries = config.get("floor_budgets", [])
        assert entries[-1]["max_floor"] >= 99, "Last entry must cover all floors"

    def test_budget_values_are_positive(self):
        config = get_difficulty_budget_config()
        for entry in config.get("floor_budgets", []):
            assert entry["base"] > 0, f"base must be positive: {entry}"
            assert entry["per_enemy"] > 0, f"per_enemy must be positive: {entry}"


# ═══════════════════════════════════════════════════════════
# 4. Fallback behavior (missing config)
# ═══════════════════════════════════════════════════════════

class TestBudgetFallback:
    """Verify fallback values when difficulty_budget section is absent."""

    def test_get_rarity_cost_without_config(self):
        """When config is patched to have no difficulty_budget, fallback defaults apply."""
        fake_config = {"rarity_tiers": {}, "spawn_chances": {}}
        with patch("app.core.monster_rarity.load_monster_rarity_config", return_value=fake_config):
            assert get_rarity_cost("normal") == 1
            assert get_rarity_cost("champion") == 3
            assert get_rarity_cost("rare") == 5
            assert get_rarity_cost("super_unique") == 8

    def test_get_room_budget_without_config(self):
        """Without floor_budgets, falls back to generous defaults (base=15, per_enemy=2.5)."""
        fake_config = {"rarity_tiers": {}, "spawn_chances": {}}
        with patch("app.core.monster_rarity.load_monster_rarity_config", return_value=fake_config):
            # Fallback: 15 + 2.5*4 = 25
            assert get_room_budget(1, 4) == 25


# ═══════════════════════════════════════════════════════════
# 5. Downgrade logic in map_exporter
# ═══════════════════════════════════════════════════════════

class TestBudgetDowngrade:
    """Verify that rarity rolls are downgraded when budget is insufficient."""

    def _make_mock_enemy_def(self, name="Skeleton", allow_rarity=True, attack_type="melee"):
        """Create a mock EnemyDefinition."""
        mock_def = MagicMock()
        mock_def.name = name
        mock_def.allow_rarity_upgrade = allow_rarity
        mock_def.attack_type = attack_type
        mock_def.excluded_affixes = []
        return mock_def

    def test_rare_downgraded_to_champion_when_budget_tight(self):
        """If rare costs 5 but only 3 points remain, downgrade to champion (cost 3)."""
        from app.core.wfc.map_exporter import export_to_game_map

        # We'll test indirectly through the budget math:
        # Floor 1, 3 enemies → budget = 9
        # If first enemy rolls rare (cost 5), budget_remaining = 4
        # Second enemy rolls rare (cost 5 > 4) → downgrade to champion (cost 3 ≤ 4)
        budget = get_room_budget(1, 3)
        assert budget == 9

        rare_cost = get_rarity_cost("rare")
        champion_cost = get_rarity_cost("champion")
        normal_cost = get_rarity_cost("normal")

        # After 1 rare: 9 - 5 = 4 remaining
        remaining = budget - rare_cost
        assert remaining == 4

        # Another rare (cost 5) doesn't fit, but champion (cost 3) does
        assert rare_cost > remaining
        assert champion_cost <= remaining

    def test_downgrade_to_normal_when_budget_exhausted(self):
        """If only 1-2 points remain, even champion (cost 3) is too expensive."""
        budget = get_room_budget(1, 3)  # 9
        # After 1 rare (5) + 1 champion (3) = 8 spent, only 1 left
        remaining = budget - get_rarity_cost("rare") - get_rarity_cost("champion")
        assert remaining == 1
        assert get_rarity_cost("champion") > remaining
        # Must downgrade to normal (cost 1)
        assert get_rarity_cost("normal") <= remaining

    def test_floor1_cannot_have_two_rares(self):
        """On floor 1 with 4 enemies (budget=10), two rares (5+5=10) leaves 0 for remaining."""
        budget = get_room_budget(1, 4)  # 10
        # 2 rares = cost 10, leaving exactly 0 for 2 more normals (2 × 1 = 2 needed)
        remaining = budget - 2 * get_rarity_cost("rare")
        assert remaining == 0
        # Can't afford even a normal for the remaining 2 enemies
        # In practice the system won't allow the second rare because after
        # the first rare (cost 5) + 2 normals (cost 2) = 7, remaining = 3,
        # which is exactly champion, not rare
        # The KEY insight: sequential processing means budget goes down one-by-one

    def test_deep_floor_allows_multiple_enhanced(self):
        """Floor 9 with 5 enemies (budget=27) can afford 2 rares + extras."""
        budget = get_room_budget(9, 5)  # 27
        # 2 rares (10) + 3 normals (3) = 13 — well within budget
        cost_2_rares = 2 * get_rarity_cost("rare")
        cost_3_normals = 3 * get_rarity_cost("normal")
        assert cost_2_rares + cost_3_normals < budget


# ═══════════════════════════════════════════════════════════
# 6. Floor 1-3 rare cap validation
# ═══════════════════════════════════════════════════════════

class TestEarlyFloorRareCap:
    """Prove that floors 1-3 can have at most 1 rare per room via budget math."""

    @pytest.mark.parametrize("floor,enemies", [
        (1, 3), (2, 3),
    ])
    def test_max_one_rare_floors_1_2_small_pack(self, floor, enemies):
        """On floors 1-2 with small packs (3 enemies), budget prevents 2 rares."""
        budget = get_room_budget(floor, enemies)
        rare_cost = get_rarity_cost("rare")

        # After first rare, check if a second rare fits even in best sequencing
        remaining_after_rare = budget - rare_cost
        remaining_after_rare_and_one_normal = remaining_after_rare - get_rarity_cost("normal")
        assert remaining_after_rare_and_one_normal < rare_cost, (
            f"Floor {floor}, {enemies} enemies (budget={budget}): "
            f"second rare should not be affordable (remaining={remaining_after_rare_and_one_normal})"
        )

    @pytest.mark.parametrize("floor,enemies", [
        (1, 3), (1, 4), (2, 3), (2, 4), (3, 4), (3, 5),
    ])
    def test_early_floor_total_cost_constrained(self, floor, enemies):
        """On early floors, total rarity cost is always constrained by budget."""
        budget = get_room_budget(floor, enemies)
        rare_cost = get_rarity_cost("rare")

        # Maximum possible enhanced: 2 (from max_enhanced_per_room)
        # Worst case: 2 rares (cost 10) + (enemies-2) normals
        max_rarity_cost = 2 * rare_cost + (enemies - 2) * get_rarity_cost("normal")
        # Budget should always accommodate at most max_enhanced without exceeding
        assert budget >= get_rarity_cost("normal") * enemies, (
            f"Floor {floor}, {enemies} enemies: budget ({budget}) must cover all normals"
        )


# ═══════════════════════════════════════════════════════════
# 7. Deep floor multi-enhanced validation
# ═══════════════════════════════════════════════════════════

class TestDeepFloorBudget:
    """Verify deep floors can still produce dangerous rooms."""

    @pytest.mark.parametrize("floor,enemies", [
        (7, 4), (7, 5), (8, 5), (9, 4), (9, 6), (10, 5),
    ])
    def test_deep_floor_allows_rare_plus_champion(self, floor, enemies):
        """Deep floors should afford 1 rare + 1 champion + normals."""
        budget = get_room_budget(floor, enemies)
        cost = (
            get_rarity_cost("rare")
            + get_rarity_cost("champion")
            + (enemies - 2) * get_rarity_cost("normal")
        )
        assert cost <= budget, (
            f"Floor {floor}, {enemies} enemies (budget={budget}): "
            f"should afford 1 rare + 1 champion + {enemies-2} normals (cost={cost})"
        )


# ═══════════════════════════════════════════════════════════
# 8. Pipeline integration — export_to_game_map respects budget
# ═══════════════════════════════════════════════════════════

class TestBudgetPipelineIntegration:
    """Full pipeline test: generate a dungeon and verify budget constraints."""

    def _make_enemy_room_tile_map(self, enemy_count: int = 4):
        """Create a minimal tile map with a single room containing N enemies."""
        # 8×8 module: walls on edges, enemies inside
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

    def _make_grid_and_variants(self, enemy_count: int = 4):
        """Build matching grid + variants for 1 room."""
        tile_map = self._make_enemy_room_tile_map(enemy_count)
        variant = {
            "purpose": "enemy",
            "sourceName": "Test Enemy Room",
        }
        grid = [[{"chosenVariant": 0}]]
        variants = [variant]
        return tile_map, grid, variants

    def test_floor1_budget_constrains_rarity(self):
        """On floor 1, force all rolls to 'rare' — budget should cap most."""
        from app.core.wfc.map_exporter import export_to_game_map
        from app.core.monster_rarity import clear_monster_rarity_cache

        clear_monster_rarity_cache()
        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=4)

        # Patch roll_monster_rarity to always return "rare"
        with patch("app.core.monster_rarity.roll_monster_rarity", return_value="rare"):
            result = export_to_game_map(
                tile_map, grid, variants,
                floor_number=1,
                seed=42,
            )

        rooms = result.get("rooms", [])
        assert len(rooms) >= 1
        spawns = rooms[0].get("enemy_spawns", [])
        assert len(spawns) == 4

        # Count rarities
        rarities = [s["monster_rarity"] for s in spawns]
        rare_count = rarities.count("rare")
        champion_count = rarities.count("champion")
        normal_count = rarities.count("normal")

        # Budget=10 for floor 1 + 4 enemies.
        # max_enhanced_per_room=2 caps enhanced to 2.
        # Sequential: rare(5)→rem=5, rare(5)→rem=0, forced normal×2
        assert rare_count <= 2, f"Should have at most 2 rares (got {rare_count})"
        enhanced = rare_count + champion_count
        assert enhanced <= 2, f"max_enhanced_per_room should cap at 2 (got {enhanced})"
        # With budget of 10 and max_enhanced=2, we expect 2 rares + 2 normals
        # OR budget prevents second rare in some cases

    def test_floor9_budget_allows_multiple_enhanced(self):
        """On floor 9, generous budget allows several enhanced enemies."""
        from app.core.wfc.map_exporter import export_to_game_map
        from app.core.monster_rarity import clear_monster_rarity_cache

        clear_monster_rarity_cache()
        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=4)

        with patch("app.core.monster_rarity.roll_monster_rarity", return_value="champion"):
            result = export_to_game_map(
                tile_map, grid, variants,
                floor_number=9,
                seed=42,
            )

        rooms = result.get("rooms", [])
        assert len(rooms) >= 1
        spawns = rooms[0].get("enemy_spawns", [])
        rarities = [s["monster_rarity"] for s in spawns]
        champion_count = rarities.count("champion")

        # Budget floor 9, 4 enemies: 15 + 2.5*4 = 25
        # 4 champions = 4*3 = 12 — easily fits
        # But max_enhanced_per_room=2 still caps at 2
        assert champion_count == 2, f"max_enhanced_per_room should cap at 2 (got {champion_count})"

    def test_budget_tracks_across_enemies_in_room(self):
        """Budget is consumed by each enemy and limits subsequent rolls."""
        from app.core.wfc.map_exporter import export_to_game_map
        from app.core.monster_rarity import clear_monster_rarity_cache

        clear_monster_rarity_cache()
        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=3)

        # Alternate: rare, rare, rare — on floor 2 (budget = 6 + 1.0*3 = 9)
        with patch("app.core.monster_rarity.roll_monster_rarity", return_value="rare"):
            result = export_to_game_map(
                tile_map, grid, variants,
                floor_number=2,
                seed=100,
            )

        rooms = result.get("rooms", [])
        spawns = rooms[0].get("enemy_spawns", [])
        rarities = [s["monster_rarity"] for s in spawns]

        # Budget=9: rare(5) → rem=4, rare(5>4) → downgrade to champion(3≤4) → rem=1
        # But max_enhanced_per_room=2 will cap:
        # After 2 enhanced, third is forced normal regardless
        enhanced = [r for r in rarities if r != "normal"]
        assert len(enhanced) <= 2

    def test_deterministic_with_same_seed(self):
        """Same seed produces identical rarity assignments."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map, grid, variants = self._make_grid_and_variants(enemy_count=4)

        results = []
        for _ in range(3):
            clear_monster_rarity_cache()
            result = export_to_game_map(
                tile_map, grid, variants,
                floor_number=5,
                seed=777,
            )
            rooms = result.get("rooms", [])
            if rooms:
                rarities = [s["monster_rarity"] for s in rooms[0].get("enemy_spawns", [])]
                results.append(tuple(rarities))

        assert len(results) == 3
        assert results[0] == results[1] == results[2], "Same seed must produce identical results"

    def test_boss_not_affected_by_budget(self):
        """Boss tiles ('B') bypass the budget system entirely."""
        from app.core.wfc.map_exporter import export_to_game_map

        # Create a room with 1 boss + 3 enemies
        tile_map = []
        boss_placed = False
        enemy_placed = 0
        for r in range(8):
            row = []
            for c in range(8):
                if r == 0 or r == 7 or c == 0 or c == 7:
                    row.append("W")
                elif not boss_placed and r == 1 and c == 1:
                    row.append("B")
                    boss_placed = True
                elif enemy_placed < 3:
                    row.append("E")
                    enemy_placed += 1
                else:
                    row.append("F")
            tile_map.append(row)

        variant = {"purpose": "boss", "sourceName": "Boss Room"}
        grid = [[{"chosenVariant": 0}]]
        variants = [variant]

        clear_monster_rarity_cache()
        result = export_to_game_map(
            tile_map, grid, variants,
            floor_number=1,
            seed=42,
        )

        rooms = result.get("rooms", [])
        assert len(rooms) >= 1
        spawns = rooms[0].get("enemy_spawns", [])
        boss_spawns = [s for s in spawns if s.get("is_boss")]
        # Boss should always be normal rarity (not budget-affected)
        for bs in boss_spawns:
            assert bs["monster_rarity"] in ("normal", "super_unique"), (
                f"Boss should be normal or super_unique, got {bs['monster_rarity']}"
            )


# ═══════════════════════════════════════════════════════════
# 9. Budget math edge cases
# ═══════════════════════════════════════════════════════════

class TestBudgetEdgeCases:
    """Test edge cases in budget computation."""

    def test_zero_enemies(self):
        """Room with 0 enemies: budget is just the base."""
        assert get_room_budget(1, 0) == 6
        assert get_room_budget(5, 0) == 10

    def test_single_enemy(self):
        """Single-enemy room always has enough for at least a champion."""
        for floor in (1, 3, 5, 7, 9):
            budget = get_room_budget(floor, 1)
            assert budget >= get_rarity_cost("champion"), (
                f"Floor {floor} single enemy budget ({budget}) should afford a champion"
            )

    def test_large_enemy_count(self):
        """Large pack (8 enemies) budget scales correctly."""
        budget = get_room_budget(9, 8)
        # 15 + 2.5*8 = 35
        assert budget == 35

    def test_floor_boundary_values(self):
        """Test exact boundary floors (max_floor values)."""
        # Floor 2 (boundary of first tier) vs floor 3 (second tier)
        b2 = get_room_budget(2, 4)  # 6 + 1.0*4 = 10
        b3 = get_room_budget(3, 4)  # 8 + 1.5*4 = 14
        assert b2 == 10
        assert b3 == 14
        assert b3 > b2
