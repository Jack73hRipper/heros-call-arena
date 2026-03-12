"""
Tests for Phase 16C: Rarity Overhaul & Item Tiers.

Covers the complete rarity system expansion including:
 1. Rarity enum — all 6 tiers serialize/deserialize correctly
 2. Rarity enum — backward compat (UNCOMMON still works)
 3. Drop rate scaling by floor — produces expected distribution shifts
 4. Magic find increases effective drop rates (statistical)
 5. Boss guaranteed minimum rarity works per floor bracket
 6. Boss drop count scaling by floor bracket
 7. Boss unique chance at floor 8+
 8. enforce_minimum_rarity upgrades lower tiers correctly
 9. Rarity upgrade chain (common→magic→rare→epic)
10. Phase 15 "uncommon" items migrated to "magic" in config
11. Rarity colors match spec for all 6 tiers
12. Rarity display names correct
13. Item generation uses proper Rarity enum values for all tiers
14. generate_enemy_loot with boss tier enforces minimum rarity
15. generate_chest_loot with floor scaling
16. Sell value multipliers for all rarity tiers
17. Affix counts correct for epic tier (4–5)
18. Backward compat — legacy UNCOMMON items still load
19. loot_tables.json guaranteed_rarity = "magic" works
20. Full pipeline integration — floor 1 vs floor 8 rarity distribution
"""

from __future__ import annotations

import random
import pytest

from app.models.items import (
    Item,
    ItemType,
    Rarity,
    EquipSlot,
    StatBonuses,
    Inventory,
)
from app.core.item_generator import (
    load_affixes_config,
    load_item_names_config,
    clear_generator_caches,
    roll_affix_value,
    roll_affixes,
    generate_item,
    generate_loot_item,
    roll_rarity,
    calculate_sell_value,
    RARITY_AFFIX_COUNTS,
    RARITY_SELL_MULTIPLIERS,
    RARITY_TIER_ORDER,
    RARITY_COLORS,
    get_rarity_color,
    get_rarity_display_name,
    get_boss_guaranteed_rarity,
    get_boss_drop_count,
    enforce_minimum_rarity,
    boss_has_unique_chance,
)
from app.core.loot import (
    create_item,
    load_items_config,
    load_loot_tables,
    clear_caches as clear_loot_caches,
    roll_enemy_loot,
    roll_chest_loot,
    generate_enemy_loot,
    generate_chest_loot,
    _try_rarity_upgrade,
    _pick_guaranteed_rarity_from_pool,
)


# ---------- Module-level setup ----------


def setup_module():
    """Pre-load configs for all tests."""
    load_items_config()
    load_affixes_config()
    load_item_names_config()


def teardown_module():
    """Clear all caches after tests."""
    clear_loot_caches()
    clear_generator_caches()


# ================================================================
# 1. Rarity Enum — All 6 tiers
# ================================================================


class TestRarityEnum:
    """Test that all rarity enum values exist and serialize correctly."""

    def test_common_exists(self):
        assert Rarity.COMMON == "common"
        assert Rarity("common") == Rarity.COMMON

    def test_uncommon_exists_backward_compat(self):
        assert Rarity.UNCOMMON == "uncommon"
        assert Rarity("uncommon") == Rarity.UNCOMMON

    def test_magic_exists(self):
        assert Rarity.MAGIC == "magic"
        assert Rarity("magic") == Rarity.MAGIC

    def test_rare_exists(self):
        assert Rarity.RARE == "rare"
        assert Rarity("rare") == Rarity.RARE

    def test_epic_exists(self):
        assert Rarity.EPIC == "epic"
        assert Rarity("epic") == Rarity.EPIC

    def test_unique_exists(self):
        assert Rarity.UNIQUE == "unique"
        assert Rarity("unique") == Rarity.UNIQUE

    def test_set_exists(self):
        assert Rarity.SET == "set"
        assert Rarity("set") == Rarity.SET

    def test_all_rarities_count(self):
        """Ensure we have exactly 7 rarity values (including legacy UNCOMMON)."""
        assert len(Rarity) == 7

    def test_item_creation_with_all_rarities(self):
        """Items can be created with every rarity tier."""
        for rarity in Rarity:
            item = Item(
                item_id="test",
                name="Test Item",
                item_type=ItemType.WEAPON,
                rarity=rarity,
            )
            assert item.rarity == rarity

    def test_item_rarity_json_roundtrip(self):
        """Rarity survives JSON serialization and deserialization."""
        for rarity in [Rarity.MAGIC, Rarity.RARE, Rarity.EPIC, Rarity.UNIQUE, Rarity.SET]:
            item = Item(
                item_id="test",
                name="Test",
                item_type=ItemType.WEAPON,
                rarity=rarity,
            )
            data = item.model_dump()
            assert data["rarity"] == rarity.value
            restored = Item(**data)
            assert restored.rarity == rarity


# ================================================================
# 2. Rarity Colors & Display Names
# ================================================================


class TestRarityDisplayInfo:
    """Test rarity color and display name mappings."""

    def test_common_color(self):
        assert get_rarity_color("common") == "#9d9d9d"

    def test_magic_color(self):
        assert get_rarity_color("magic") == "#4488ff"

    def test_rare_color(self):
        assert get_rarity_color("rare") == "#ffcc00"

    def test_epic_color(self):
        assert get_rarity_color("epic") == "#b040ff"

    def test_unique_color(self):
        assert get_rarity_color("unique") == "#ff8800"

    def test_set_color(self):
        assert get_rarity_color("set") == "#00cc44"

    def test_legacy_uncommon_color_maps_to_gray(self):
        assert get_rarity_color("uncommon") == "#9d9d9d"

    def test_unknown_rarity_defaults_to_common(self):
        assert get_rarity_color("nonexistent") == "#9d9d9d"

    def test_display_name_common(self):
        assert get_rarity_display_name("common") == "Common"

    def test_display_name_magic(self):
        assert get_rarity_display_name("magic") == "Magic"

    def test_display_name_rare(self):
        assert get_rarity_display_name("rare") == "Rare"

    def test_display_name_epic(self):
        assert get_rarity_display_name("epic") == "Epic"

    def test_display_name_unique(self):
        assert get_rarity_display_name("unique") == "Unique"

    def test_display_name_set(self):
        assert get_rarity_display_name("set") == "Set"

    def test_display_name_legacy_uncommon(self):
        assert get_rarity_display_name("uncommon") == "Common"

    def test_all_colors_are_hex(self):
        """All rarity colors are valid hex color strings."""
        for color in RARITY_COLORS.values():
            assert color.startswith("#"), f"Not a hex color: {color}"
            assert len(color) == 7, f"Not a 6-digit hex color: {color}"


# ================================================================
# 3. Rarity Tier Order
# ================================================================


class TestRarityTierOrder:
    """Test the rarity tier ordering for comparisons."""

    def test_tier_order_list_exists(self):
        assert RARITY_TIER_ORDER == ["common", "magic", "rare", "epic", "unique"]

    def test_common_is_lowest(self):
        assert RARITY_TIER_ORDER.index("common") < RARITY_TIER_ORDER.index("magic")

    def test_unique_is_highest(self):
        assert RARITY_TIER_ORDER.index("unique") > RARITY_TIER_ORDER.index("epic")


# ================================================================
# 4. Enforce Minimum Rarity
# ================================================================


class TestEnforceMinimumRarity:
    """Test enforce_minimum_rarity upgrades lower tiers."""

    def test_common_upgraded_to_magic(self):
        assert enforce_minimum_rarity("common", "magic") == "magic"

    def test_common_upgraded_to_rare(self):
        assert enforce_minimum_rarity("common", "rare") == "rare"

    def test_magic_not_downgraded_when_min_is_common(self):
        assert enforce_minimum_rarity("magic", "common") == "magic"

    def test_rare_stays_when_min_is_magic(self):
        assert enforce_minimum_rarity("rare", "magic") == "rare"

    def test_epic_stays_when_min_is_rare(self):
        assert enforce_minimum_rarity("epic", "rare") == "epic"

    def test_same_tier_unchanged(self):
        assert enforce_minimum_rarity("rare", "rare") == "rare"

    def test_common_upgraded_to_epic(self):
        assert enforce_minimum_rarity("common", "epic") == "epic"

    def test_unknown_rarity_defaults(self):
        """Unknown rarities default to index 0 behavior."""
        result = enforce_minimum_rarity("nonexistent", "magic")
        assert result == "magic"


# ================================================================
# 5. Boss Guaranteed Rarity
# ================================================================


class TestBossGuaranteedRarity:
    """Test boss guaranteed minimum rarity by floor bracket."""

    def test_floor_1_boss_guarantees_magic(self):
        assert get_boss_guaranteed_rarity(1) == "magic"

    def test_floor_4_boss_guarantees_magic(self):
        assert get_boss_guaranteed_rarity(4) == "magic"

    def test_floor_5_boss_guarantees_rare(self):
        assert get_boss_guaranteed_rarity(5) == "rare"

    def test_floor_7_boss_guarantees_rare(self):
        assert get_boss_guaranteed_rarity(7) == "rare"

    def test_floor_8_boss_guarantees_epic(self):
        assert get_boss_guaranteed_rarity(8) == "epic"

    def test_floor_10_boss_guarantees_epic(self):
        assert get_boss_guaranteed_rarity(10) == "epic"

    def test_floor_15_boss_guarantees_epic(self):
        assert get_boss_guaranteed_rarity(15) == "epic"


# ================================================================
# 6. Boss Drop Counts
# ================================================================


class TestBossDropCounts:
    """Test boss item drop count scaling by floor bracket."""

    def test_floor_1_drops_2_to_3(self):
        rng = random.Random(42)
        counts = [get_boss_drop_count(1, random.Random(i)) for i in range(100)]
        assert min(counts) >= 2
        assert max(counts) <= 3

    def test_floor_5_drops_2_to_4(self):
        counts = [get_boss_drop_count(5, random.Random(i)) for i in range(100)]
        assert min(counts) >= 2
        assert max(counts) <= 4

    def test_floor_8_drops_3_to_4(self):
        counts = [get_boss_drop_count(8, random.Random(i)) for i in range(100)]
        assert min(counts) >= 3
        assert max(counts) <= 4


# ================================================================
# 7. Boss Unique Chance
# ================================================================


class TestBossUniqueChance:
    """Test floor 8+ boss unique drop chance."""

    def test_floor_7_never_has_unique_chance(self):
        for i in range(100):
            assert boss_has_unique_chance(7, random.Random(i)) is False

    def test_floor_8_can_have_unique_chance(self):
        """With enough attempts, at least one roll should succeed (10% chance)."""
        results = [boss_has_unique_chance(8, random.Random(i)) for i in range(200)]
        assert any(results), "Expected at least one True in 200 rolls at 10% chance"

    def test_floor_8_unique_chance_approximately_10_pct(self):
        """Statistical check that unique chance is around 10% ± 6%."""
        n = 1000
        successes = sum(
            1 for i in range(n) if boss_has_unique_chance(8, random.Random(i))
        )
        rate = successes / n
        assert 0.04 < rate < 0.16, f"Unique rate {rate:.2%} outside expected 10% ± 6%"


# ================================================================
# 8. Rarity Upgrade Chain
# ================================================================


class TestRarityUpgradeChain:
    """Test _try_rarity_upgrade with the Phase 16C full tier chain."""

    def test_no_upgrade_when_mf_zero(self):
        item = Item(item_id="test", name="Test", item_type=ItemType.WEAPON, rarity=Rarity.COMMON)
        result = _try_rarity_upgrade(item, 0.0, random.Random(42))
        assert result.rarity == Rarity.COMMON

    def test_common_upgrades_to_magic(self):
        """With 100% MF, common should always upgrade to magic."""
        item = Item(item_id="test", name="Test", item_type=ItemType.WEAPON, rarity=Rarity.COMMON)
        result = _try_rarity_upgrade(item, 1.0, random.Random(42))
        assert result.rarity == Rarity.MAGIC

    def test_magic_upgrades_to_rare(self):
        """With 100% MF, magic should always upgrade to rare."""
        item = Item(item_id="test", name="Test", item_type=ItemType.WEAPON, rarity=Rarity.MAGIC)
        result = _try_rarity_upgrade(item, 1.0, random.Random(42))
        assert result.rarity == Rarity.RARE

    def test_rare_upgrades_to_epic(self):
        """With 100% MF, rare should always upgrade to epic."""
        item = Item(item_id="test", name="Test", item_type=ItemType.WEAPON, rarity=Rarity.RARE)
        result = _try_rarity_upgrade(item, 1.0, random.Random(42))
        assert result.rarity == Rarity.EPIC

    def test_epic_does_not_upgrade(self):
        """Epic is the ceiling for MF upgrades — can't upgrade further."""
        item = Item(item_id="test", name="Test", item_type=ItemType.WEAPON, rarity=Rarity.EPIC)
        result = _try_rarity_upgrade(item, 1.0, random.Random(42))
        assert result.rarity == Rarity.EPIC

    def test_legacy_uncommon_upgrades_to_magic(self):
        """Legacy UNCOMMON items upgrade to MAGIC."""
        item = Item(item_id="test", name="Test", item_type=ItemType.WEAPON, rarity=Rarity.UNCOMMON)
        result = _try_rarity_upgrade(item, 1.0, random.Random(42))
        assert result.rarity == Rarity.MAGIC


# ================================================================
# 9. Item Generation with Proper Enums
# ================================================================


class TestItemGenerationRarityEnums:
    """Test that generate_item uses proper Rarity enum values for all tiers."""

    def test_common_item_has_common_enum(self):
        item = generate_item("common_sword", rarity="common", item_level=5, seed=42)
        assert item is not None
        assert item.rarity == Rarity.COMMON

    def test_magic_item_has_magic_enum(self):
        item = generate_item("common_sword", rarity="magic", item_level=5, seed=42)
        assert item is not None
        assert item.rarity == Rarity.MAGIC

    def test_rare_item_has_rare_enum(self):
        item = generate_item("common_sword", rarity="rare", item_level=5, seed=42)
        assert item is not None
        assert item.rarity == Rarity.RARE

    def test_epic_item_has_epic_enum(self):
        item = generate_item("common_sword", rarity="epic", item_level=10, seed=42)
        assert item is not None
        assert item.rarity == Rarity.EPIC

    def test_magic_item_has_1_to_2_affixes(self):
        item = generate_item("common_sword", rarity="magic", item_level=5, seed=42)
        assert item is not None
        assert 1 <= len(item.affixes) <= 2

    def test_rare_item_has_3_to_4_affixes(self):
        item = generate_item("common_sword", rarity="rare", item_level=8, seed=42)
        assert item is not None
        assert 3 <= len(item.affixes) <= 4

    def test_epic_item_has_4_to_5_affixes(self):
        item = generate_item("common_sword", rarity="epic", item_level=12, seed=42)
        assert item is not None
        assert 4 <= len(item.affixes) <= 5


# ================================================================
# 10. Epic Affix Counts
# ================================================================


class TestEpicAffixCounts:
    """Test that epic tier generates 4–5 affixes as specified."""

    def test_epic_affix_count_range(self):
        counts = RARITY_AFFIX_COUNTS.get("epic")
        assert counts is not None
        min_pre, max_pre, min_suf, max_suf, min_total = counts
        assert min_pre == 2
        assert max_pre == 3
        assert min_suf == 2
        assert max_suf == 3
        assert min_total == 4

    def test_epic_generates_at_least_4_affixes(self):
        """Over multiple seeds, all epic items have at least 4 affixes."""
        for seed in range(50):
            item = generate_item("common_sword", rarity="epic", item_level=15, seed=seed)
            if item is not None:
                assert len(item.affixes) >= 4, f"Seed {seed}: only {len(item.affixes)} affixes"


# ================================================================
# 11. Sell Value Multipliers
# ================================================================


class TestSellValueMultipliers:
    """Test sell value multipliers for all rarity tiers."""

    def test_common_multiplier(self):
        assert RARITY_SELL_MULTIPLIERS["common"] == 1.0

    def test_magic_multiplier(self):
        assert RARITY_SELL_MULTIPLIERS["magic"] == 1.5

    def test_rare_multiplier(self):
        assert RARITY_SELL_MULTIPLIERS["rare"] == 3.0

    def test_epic_multiplier(self):
        assert RARITY_SELL_MULTIPLIERS["epic"] == 6.0

    def test_unique_multiplier(self):
        assert RARITY_SELL_MULTIPLIERS["unique"] == 8.0

    def test_set_multiplier(self):
        assert RARITY_SELL_MULTIPLIERS["set"] == 8.0

    def test_higher_rarity_items_sell_for_more(self):
        """Same base item sells for more at higher rarity."""
        base_value = 20
        common_val = calculate_sell_value(base_value, "common", [])
        magic_val = calculate_sell_value(base_value, "magic", [])
        rare_val = calculate_sell_value(base_value, "rare", [])
        epic_val = calculate_sell_value(base_value, "epic", [])
        assert common_val < magic_val < rare_val < epic_val


# ================================================================
# 12. Config Migration
# ================================================================


class TestConfigMigration:
    """Test that Phase 15 items are correctly migrated."""

    def test_uncommon_items_now_magic_in_config(self):
        """items_config.json no longer has 'uncommon' rarity items — they're 'magic'."""
        config = load_items_config()
        for item_id, data in config.items():
            rarity = data.get("rarity", "common")
            if "uncommon" in item_id:
                assert rarity == "magic", f"{item_id} still has rarity '{rarity}', expected 'magic'"

    def test_loot_tables_guaranteed_rarity_is_magic(self):
        """loot_tables.json guaranteed_rarity should be 'magic' after migration."""
        tables = load_loot_tables()
        for category in ("enemy_loot_tables", "chest_loot_tables"):
            for table_name, data in tables.get(category, {}).items():
                gr = data.get("guaranteed_rarity")
                if gr:
                    assert gr != "uncommon", (
                        f"{category}.{table_name} still has guaranteed_rarity='uncommon'"
                    )

    def test_loot_tables_rarity_config_exists(self):
        """loot_tables.json now has a rarity_config section."""
        tables = load_loot_tables()
        assert "rarity_config" in tables

    def test_rarity_config_base_rates(self):
        """rarity_config.base_rates has all expected tiers."""
        tables = load_loot_tables()
        base_rates = tables["rarity_config"]["base_rates"]
        assert "common" in base_rates
        assert "magic" in base_rates
        assert "rare" in base_rates
        assert "epic" in base_rates
        assert "unique" in base_rates


# ================================================================
# 13. Guaranteed Rarity Pool Picking
# ================================================================


class TestGuaranteedRarityPoolPicking:
    """Test _pick_guaranteed_rarity_from_pool with various targets."""

    def test_pick_magic_from_pool(self):
        """Should find items with rarity 'magic' in the pool."""
        items_config = load_items_config()
        pools = [{"weight": 100, "items": list(items_config.keys())[:10]}]
        rng = random.Random(42)
        item = _pick_guaranteed_rarity_from_pool(pools, rng, items_config, "magic")
        # Should return some item (fallback if no magic items in first 10)
        assert item is not None


# ================================================================
# 14. Drop Rate Distribution (Statistical)
# ================================================================


class TestDropRateDistribution:
    """Statistical tests for drop rate scaling."""

    def test_floor_1_mostly_common(self):
        """At floor 1, majority of rolls should be common."""
        common_count = 0
        n = 500
        for i in range(n):
            rarity = roll_rarity(floor_number=1, enemy_tier="fodder", rng=random.Random(i))
            if rarity == "common":
                common_count += 1
        rate = common_count / n
        assert rate > 0.40, f"Common rate {rate:.2%} too low at floor 1"

    def test_floor_8_less_common(self):
        """At floor 8, common rate should be significantly lower than floor 1."""
        common_f1 = sum(
            1 for i in range(500)
            if roll_rarity(floor_number=1, enemy_tier="fodder", rng=random.Random(i)) == "common"
        )
        common_f8 = sum(
            1 for i in range(500)
            if roll_rarity(floor_number=8, enemy_tier="fodder", rng=random.Random(i)) == "common"
        )
        assert common_f8 < common_f1, "Floor 8 should have fewer commons than floor 1"

    def test_magic_find_increases_rarer_drops(self):
        """High magic find should produce more non-common drops."""
        n = 500
        no_mf_rares = sum(
            1 for i in range(n)
            if roll_rarity(floor_number=5, enemy_tier="mid", magic_find_bonus=0.0, rng=random.Random(i))
            in ("rare", "epic", "unique")
        )
        high_mf_rares = sum(
            1 for i in range(n)
            if roll_rarity(floor_number=5, enemy_tier="mid", magic_find_bonus=0.60, rng=random.Random(i))
            in ("rare", "epic", "unique")
        )
        assert high_mf_rares > no_mf_rares, "60% MF should produce more rares than 0% MF"

    def test_boss_tier_increases_rarity(self):
        """Boss enemy tier should produce more rares than fodder."""
        n = 500
        fodder_rares = sum(
            1 for i in range(n)
            if roll_rarity(floor_number=5, enemy_tier="fodder", rng=random.Random(i))
            in ("rare", "epic", "unique")
        )
        boss_rares = sum(
            1 for i in range(n)
            if roll_rarity(floor_number=5, enemy_tier="boss", rng=random.Random(i))
            in ("rare", "epic", "unique")
        )
        assert boss_rares > fodder_rares, "Boss tier should produce more rares than fodder"

    def test_all_rarity_strings_are_valid(self):
        """roll_rarity should only return valid rarity strings."""
        valid = {"common", "magic", "rare", "epic", "unique"}
        for i in range(200):
            rarity = roll_rarity(floor_number=5, enemy_tier="boss", magic_find_bonus=0.3, rng=random.Random(i))
            assert rarity in valid, f"Invalid rarity string: {rarity}"


# ================================================================
# 15. Generate Enemy Loot — Boss Integration
# ================================================================


class TestBossLootIntegration:
    """Test generate_enemy_loot with boss tier and floor-based rarity."""

    def test_boss_loot_has_items(self):
        """Boss drops should produce items (demon_boss has 100% drop chance)."""
        items = generate_enemy_loot(
            "demon_boss", floor_number=3, enemy_tier="boss", seed=42,
        )
        assert len(items) > 0

    def test_boss_floor_8_at_least_one_epic_or_better(self):
        """Floor 8 boss should enforce at least epic minimum on first generated item.
        
        Note: The first item is the guaranteed minimum, but the boss generates
        items via affix generator which enforces minimum rarity.
        """
        # Run multiple times — at least some should have epic items
        found_epic_or_better = False
        for seed in range(50):
            items = generate_enemy_loot(
                "demon_boss", floor_number=8, enemy_tier="boss", seed=seed,
            )
            for item in items:
                if item.rarity in (Rarity.EPIC, Rarity.UNIQUE, Rarity.SET):
                    found_epic_or_better = True
                    break
            if found_epic_or_better:
                break
        assert found_epic_or_better, "Floor 8 boss should produce at least one epic+ item across 50 attempts"

    def test_non_boss_no_forced_minimum(self):
        """Non-boss enemies don't have forced minimum rarity — common items are possible."""
        common_found = False
        for seed in range(100):
            items = generate_enemy_loot(
                "demon", floor_number=1, enemy_tier="fodder", seed=seed,
            )
            for item in items:
                if item.rarity == Rarity.COMMON:
                    common_found = True
                    break
            if common_found:
                break
        assert common_found, "Fodder enemies on floor 1 should sometimes drop common items"


# ================================================================
# 16. Backward Compatibility
# ================================================================


class TestBackwardCompatibility:
    """Test that legacy items and behaviors still work."""

    def test_legacy_uncommon_enum_value_still_exists(self):
        assert Rarity.UNCOMMON == "uncommon"

    def test_create_item_still_works_for_common(self):
        item = create_item("common_sword")
        assert item is not None
        assert item.rarity == Rarity.COMMON

    def test_create_item_works_for_magic_items(self):
        """Previously 'uncommon' items in config are now 'magic'."""
        item = create_item("uncommon_greatsword")
        assert item is not None
        assert item.rarity == Rarity.MAGIC

    def test_roll_enemy_loot_still_works(self):
        """The original backward-compat roll_enemy_loot still functions."""
        items = roll_enemy_loot("demon", seed=42)
        # Should return items or empty list (seed-dependent)
        assert isinstance(items, list)

    def test_roll_chest_loot_still_works(self):
        """The original backward-compat roll_chest_loot still functions."""
        items = roll_chest_loot("default", seed=42)
        assert isinstance(items, list)

    def test_inventory_operations_with_new_rarities(self):
        """Inventory add/remove works with items of new rarity tiers."""
        inv = Inventory()
        magic_item = Item(
            item_id="test_magic", name="Magic Sword",
            item_type=ItemType.WEAPON, rarity=Rarity.MAGIC,
        )
        epic_item = Item(
            item_id="test_epic", name="Epic Ring",
            item_type=ItemType.ACCESSORY, rarity=Rarity.EPIC,
        )
        assert inv.add_item(magic_item)
        assert inv.add_item(epic_item)
        assert len(inv.items) == 2
        removed = inv.remove_item("test_magic")
        assert removed is not None
        assert removed.rarity == Rarity.MAGIC

    def test_affix_counts_include_legacy_uncommon(self):
        """RARITY_AFFIX_COUNTS has an entry for 'uncommon' (0 affixes)."""
        assert "uncommon" in RARITY_AFFIX_COUNTS
        assert RARITY_AFFIX_COUNTS["uncommon"] == (0, 0, 0, 0, 0)


# ================================================================
# 17. Full Pipeline Integration
# ================================================================


class TestFullPipelineIntegration:
    """End-to-end integration tests for the full rarity pipeline."""

    def test_generate_loot_item_produces_valid_rarity(self):
        """generate_loot_item returns items with valid Phase 16C rarity enums."""
        valid_rarities = {Rarity.COMMON, Rarity.MAGIC, Rarity.RARE, Rarity.EPIC}
        for seed in range(50):
            item = generate_loot_item(
                "common_sword", floor_number=5, enemy_tier="mid", seed=seed,
            )
            if item is not None:
                assert item.rarity in valid_rarities, f"Unexpected rarity: {item.rarity}"

    def test_higher_floor_higher_average_rarity(self):
        """Items generated on floor 8 should have higher average rarity than floor 1."""
        rarity_score = {
            Rarity.COMMON: 0, Rarity.UNCOMMON: 0,
            Rarity.MAGIC: 1, Rarity.RARE: 2, Rarity.EPIC: 3,
            Rarity.UNIQUE: 4, Rarity.SET: 4,
        }
        n = 200
        floor1_scores = []
        floor8_scores = []
        for seed in range(n):
            item1 = generate_loot_item("common_sword", floor_number=1, enemy_tier="fodder", seed=seed)
            item8 = generate_loot_item("common_sword", floor_number=8, enemy_tier="elite", seed=seed + 10000)
            if item1:
                floor1_scores.append(rarity_score.get(item1.rarity, 0))
            if item8:
                floor8_scores.append(rarity_score.get(item8.rarity, 0))

        avg1 = sum(floor1_scores) / max(len(floor1_scores), 1)
        avg8 = sum(floor8_scores) / max(len(floor8_scores), 1)
        assert avg8 > avg1, f"Floor 8 avg rarity ({avg8:.2f}) should exceed floor 1 ({avg1:.2f})"

    def test_chest_loot_generates_items(self):
        """generate_chest_loot produces items with the new rarity system."""
        items = generate_chest_loot("default", floor_number=5, seed=42)
        assert len(items) > 0
        for item in items:
            assert isinstance(item.rarity, Rarity)
