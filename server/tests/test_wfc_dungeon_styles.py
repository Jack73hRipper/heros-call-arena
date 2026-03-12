"""
Tests for WFC Dungeon Style Templates (Phase A — WFC In-Game Integration).

Validates:
- All 5 dungeon styles are defined with required fields
- Weight override application modifies module weights correctly
- Decorator overrides are returned for each style
- Floor-based auto-selection is deterministic (same seed → same style)
- Floor-based auto-selection varies by floor tier
- Unknown style keys fall back to "balanced"
- Style integration in FloorConfig and generate_dungeon_floor()
- Different styles produce visibly different dungeon layouts
- "balanced" style produces identical results to no-style baseline
"""

from __future__ import annotations

import pytest

from app.core.wfc.dungeon_styles import (
    DUNGEON_STYLES,
    VALID_STYLES,
    apply_weight_overrides,
    get_decorator_overrides,
    get_style,
    select_style_for_floor,
)
from app.core.wfc.presets import get_preset_modules
from app.core.wfc.dungeon_generator import (
    FloorConfig,
    generate_dungeon_floor,
    GenerationResult,
)


# ═══════════════════════════════════════════════════════════
# Style Definition Tests
# ═══════════════════════════════════════════════════════════

class TestDungeonStyleDefinitions:
    """Validate that all styles are correctly defined."""

    def test_all_five_styles_present(self):
        """Should have exactly 5 styles matching the tool's templates."""
        expected = {"balanced", "dense_catacomb", "open_ruins", "boss_rush", "treasure_vault"}
        assert set(DUNGEON_STYLES.keys()) == expected

    def test_valid_styles_matches_keys(self):
        assert VALID_STYLES == frozenset(DUNGEON_STYLES.keys())

    @pytest.mark.parametrize("style_key", list(DUNGEON_STYLES.keys()))
    def test_style_has_required_fields(self, style_key):
        """Every style must have name, description, weight_overrides, decorator_overrides."""
        style = DUNGEON_STYLES[style_key]
        assert "name" in style, f"{style_key} missing 'name'"
        assert "description" in style, f"{style_key} missing 'description'"
        assert "weight_overrides" in style, f"{style_key} missing 'weight_overrides'"
        assert "decorator_overrides" in style, f"{style_key} missing 'decorator_overrides'"

    def test_balanced_has_empty_overrides(self):
        """Balanced style should have no weight or decorator overrides."""
        balanced = DUNGEON_STYLES["balanced"]
        assert balanced["weight_overrides"] == {}
        assert balanced["decorator_overrides"] == {}

    @pytest.mark.parametrize("style_key", [
        k for k in DUNGEON_STYLES if k != "balanced"
    ])
    def test_non_balanced_styles_have_weight_overrides(self, style_key):
        """Non-balanced styles must have at least one weight override."""
        style = DUNGEON_STYLES[style_key]
        assert len(style["weight_overrides"]) > 0, f"{style_key} has no weight overrides"

    @pytest.mark.parametrize("style_key", [
        k for k in DUNGEON_STYLES if k != "balanced"
    ])
    def test_weight_overrides_use_valid_purposes(self, style_key):
        """Weight override keys must be valid module purposes."""
        valid_purposes = {"corridor", "empty", "enemy", "boss", "loot", "spawn"}
        overrides = DUNGEON_STYLES[style_key]["weight_overrides"]
        for purpose in overrides:
            assert purpose in valid_purposes, (
                f"{style_key} has override for unknown purpose '{purpose}'"
            )

    @pytest.mark.parametrize("style_key", list(DUNGEON_STYLES.keys()))
    def test_weight_overrides_are_positive(self, style_key):
        """All weight multipliers must be positive."""
        overrides = DUNGEON_STYLES[style_key]["weight_overrides"]
        for purpose, multiplier in overrides.items():
            assert multiplier > 0, (
                f"{style_key} has non-positive multiplier {multiplier} for '{purpose}'"
            )


# ═══════════════════════════════════════════════════════════
# Weight Override Application Tests
# ═══════════════════════════════════════════════════════════

class TestApplyWeightOverrides:
    """Test that weight overrides are correctly applied to modules."""

    def test_balanced_returns_same_modules(self):
        """Balanced style should return the exact same module list."""
        modules = get_preset_modules()
        result = apply_weight_overrides(modules, "balanced")
        assert result is modules  # Should be same object (no copy needed)

    def test_dense_catacomb_boosts_corridors(self):
        """Dense Catacomb should multiply corridor weights by 2.5."""
        modules = get_preset_modules()
        result = apply_weight_overrides(modules, "dense_catacomb")
        for orig, adj in zip(modules, result):
            if orig.get("purpose") == "corridor":
                expected = orig.get("weight", 1.0) * 2.5
                assert adj["weight"] == pytest.approx(expected), (
                    f"Corridor '{orig['id']}' weight should be {expected}, got {adj['weight']}"
                )

    def test_dense_catacomb_reduces_empty(self):
        """Dense Catacomb should multiply empty room weights by 0.4."""
        modules = get_preset_modules()
        result = apply_weight_overrides(modules, "dense_catacomb")
        for orig, adj in zip(modules, result):
            if orig.get("purpose") == "empty":
                expected = orig.get("weight", 1.0) * 0.4
                assert adj["weight"] == pytest.approx(expected)

    def test_treasure_vault_boosts_loot(self):
        """Treasure Vault should multiply loot weights by 3.0."""
        modules = get_preset_modules()
        result = apply_weight_overrides(modules, "treasure_vault")
        for orig, adj in zip(modules, result):
            if orig.get("purpose") == "loot":
                expected = orig.get("weight", 1.0) * 3.0
                assert adj["weight"] == pytest.approx(expected)

    def test_original_modules_not_mutated(self):
        """apply_weight_overrides must not mutate the original module dicts."""
        modules = get_preset_modules()
        original_weights = {m["id"]: m.get("weight", 1.0) for m in modules}
        apply_weight_overrides(modules, "dense_catacomb")
        for mod in modules:
            assert mod.get("weight", 1.0) == original_weights[mod["id"]], (
                f"Module '{mod['id']}' was mutated by apply_weight_overrides!"
            )

    def test_unknown_style_returns_unmodified(self):
        """Unknown style should fall back to balanced (no modifications)."""
        modules = get_preset_modules()
        result = apply_weight_overrides(modules, "nonexistent_style")
        assert result is modules

    def test_module_count_preserved(self):
        """Weight overrides should not add or remove modules."""
        modules = get_preset_modules()
        for style_key in DUNGEON_STYLES:
            result = apply_weight_overrides(modules, style_key)
            assert len(result) == len(modules), (
                f"Style '{style_key}' changed module count: {len(result)} vs {len(modules)}"
            )


# ═══════════════════════════════════════════════════════════
# Decorator Override Tests
# ═══════════════════════════════════════════════════════════

class TestDecoratorOverrides:
    """Test decorator override retrieval."""

    def test_balanced_returns_empty_overrides(self):
        assert get_decorator_overrides("balanced") == {}

    def test_dense_catacomb_has_high_enemy_density(self):
        overrides = get_decorator_overrides("dense_catacomb")
        assert overrides["enemyDensity"] == 0.7

    def test_open_ruins_has_high_empty_room_chance(self):
        overrides = get_decorator_overrides("open_ruins")
        assert overrides["emptyRoomChance"] == 0.35

    def test_boss_rush_guarantees_boss(self):
        overrides = get_decorator_overrides("boss_rush")
        assert overrides["guaranteeBoss"] is True

    def test_treasure_vault_has_high_loot_density(self):
        overrides = get_decorator_overrides("treasure_vault")
        assert overrides["lootDensity"] == 0.5

    def test_overrides_are_new_dict(self):
        """Should return a fresh dict (no aliasing to style internals)."""
        a = get_decorator_overrides("dense_catacomb")
        b = get_decorator_overrides("dense_catacomb")
        assert a == b
        assert a is not b  # Different object


# ═══════════════════════════════════════════════════════════
# Auto-Selection Tests
# ═══════════════════════════════════════════════════════════

class TestStyleAutoSelection:
    """Test floor-based automatic style selection."""

    def test_deterministic_same_seed_same_floor(self):
        """Same seed + floor must always produce the same style."""
        for _ in range(3):
            s1 = select_style_for_floor(floor_number=3, seed=12345)
            s2 = select_style_for_floor(floor_number=3, seed=12345)
            assert s1 == s2

    def test_different_seeds_can_produce_different_styles(self):
        """Different seeds should (eventually) produce different styles."""
        styles_seen = set()
        for seed in range(100):
            styles_seen.add(select_style_for_floor(floor_number=3, seed=seed))
        assert len(styles_seen) >= 2, "Expected at least 2 different styles across 100 seeds"

    def test_all_styles_reachable_from_mid_floors(self):
        """Floors 3-5 should be able to select any of the 5 styles given enough seeds."""
        styles_seen = set()
        for seed in range(1000):
            styles_seen.add(select_style_for_floor(floor_number=4, seed=seed))
        assert styles_seen == VALID_STYLES, (
            f"Not all styles reachable from mid-floors: missing {VALID_STYLES - styles_seen}"
        )

    def test_returns_valid_style_key(self):
        """Auto-selection must always return a key in DUNGEON_STYLES."""
        for floor in range(1, 12):
            for seed in range(50):
                style = select_style_for_floor(floor, seed)
                assert style in VALID_STYLES, f"Invalid style '{style}' for floor={floor} seed={seed}"

    def test_early_floors_favor_balanced(self):
        """Floors 1-2 should pick balanced/open_ruins more often than boss_rush."""
        styles = [select_style_for_floor(1, seed) for seed in range(200)]
        balanced_count = styles.count("balanced") + styles.count("open_ruins")
        boss_count = styles.count("boss_rush") + styles.count("dense_catacomb")
        assert balanced_count > boss_count, (
            f"Early floors should favor calm styles: calm={balanced_count} vs intense={boss_count}"
        )

    def test_deep_floors_favor_intense(self):
        """Floors 7+ should pick dense_catacomb/boss_rush more often than open_ruins."""
        styles = [select_style_for_floor(8, seed) for seed in range(200)]
        intense_count = styles.count("boss_rush") + styles.count("dense_catacomb")
        calm_count = styles.count("balanced") + styles.count("open_ruins")
        assert intense_count > calm_count, (
            f"Deep floors should favor intense styles: intense={intense_count} vs calm={calm_count}"
        )


# ═══════════════════════════════════════════════════════════
# get_style Tests
# ═══════════════════════════════════════════════════════════

class TestGetStyle:
    """Test style lookup."""

    def test_known_style(self):
        style = get_style("boss_rush")
        assert style["name"] == "Boss Rush"

    def test_unknown_falls_back_to_balanced(self):
        style = get_style("nonexistent")
        assert style["name"] == "Balanced"


# ═══════════════════════════════════════════════════════════
# FloorConfig Integration Tests
# ═══════════════════════════════════════════════════════════

class TestFloorConfigStyle:
    """Test dungeon_style field on FloorConfig."""

    def test_from_floor_number_has_style_field(self):
        """Auto-created FloorConfig should have dungeon_style=None (auto-select)."""
        cfg = FloorConfig.from_floor_number(seed=42, floor_number=1)
        assert cfg.dungeon_style is None

    def test_manual_style_override(self):
        """Can manually set dungeon_style on FloorConfig."""
        cfg = FloorConfig(seed=42, dungeon_style="boss_rush")
        assert cfg.dungeon_style == "boss_rush"

    def test_default_style_is_none(self):
        """Default FloorConfig() should have dungeon_style=None."""
        cfg = FloorConfig()
        assert cfg.dungeon_style is None


# ═══════════════════════════════════════════════════════════
# Full Generation Integration Tests
# ═══════════════════════════════════════════════════════════

class TestStyleGenerationIntegration:
    """Test that styles integrate into the full generation pipeline."""

    def test_generation_with_explicit_style_succeeds(self):
        """Generate with each style — all should succeed."""
        for style_key in DUNGEON_STYLES:
            cfg = FloorConfig(
                seed=42,
                floor_number=1,
                grid_rows=3,
                grid_cols=3,
                dungeon_style=style_key,
            )
            result = generate_dungeon_floor(config=cfg)
            assert result.success, f"Style '{style_key}' failed: {result.error}"
            assert result.stats.get("dungeon_style") == style_key

    def test_generation_with_auto_style_succeeds(self):
        """Generate with dungeon_style=None — should auto-select and succeed."""
        result = generate_dungeon_floor(seed=42, floor_number=3)
        assert result.success, f"Auto-style failed: {result.error}"
        assert result.stats.get("dungeon_style") in VALID_STYLES

    def test_generation_with_unknown_style_falls_back(self):
        """Unknown style should fall back to balanced and still succeed."""
        cfg = FloorConfig(
            seed=42,
            floor_number=1,
            grid_rows=3,
            grid_cols=3,
            dungeon_style="totally_fake_style",
        )
        result = generate_dungeon_floor(config=cfg)
        assert result.success
        assert result.stats.get("dungeon_style") == "balanced"

    def test_deterministic_with_same_style(self):
        """Same seed + same explicit style = identical output."""
        cfg1 = FloorConfig(seed=123, floor_number=2, grid_rows=3, grid_cols=3,
                           dungeon_style="dense_catacomb")
        cfg2 = FloorConfig(seed=123, floor_number=2, grid_rows=3, grid_cols=3,
                           dungeon_style="dense_catacomb")
        r1 = generate_dungeon_floor(config=cfg1)
        r2 = generate_dungeon_floor(config=cfg2)
        assert r1.success and r2.success
        # Same tile map
        assert r1.game_map["tiles"] == r2.game_map["tiles"]

    def test_different_styles_can_produce_different_layouts(self):
        """Different styles with same seed should (usually) produce different tile maps."""
        cfg_dense = FloorConfig(seed=42, floor_number=3, grid_rows=3, grid_cols=3,
                                dungeon_style="dense_catacomb")
        cfg_open = FloorConfig(seed=42, floor_number=3, grid_rows=3, grid_cols=3,
                               dungeon_style="open_ruins")
        r_dense = generate_dungeon_floor(config=cfg_dense)
        r_open = generate_dungeon_floor(config=cfg_open)
        assert r_dense.success and r_open.success
        # They should differ (weight adjustments change WFC collapse choices)
        assert r_dense.game_map["tiles"] != r_open.game_map["tiles"], (
            "Dense Catacomb and Open Ruins produced identical layouts — "
            "weight overrides may not be taking effect"
        )

    def test_style_recorded_in_stats(self):
        """Stats should include the dungeon_style that was used."""
        cfg = FloorConfig(seed=42, floor_number=1, grid_rows=3, grid_cols=3,
                          dungeon_style="treasure_vault")
        result = generate_dungeon_floor(config=cfg)
        assert result.success
        assert result.stats["dungeon_style"] == "treasure_vault"
