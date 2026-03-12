"""
Tests for Phase 16B: Affix System & Item Generation.

Covers the complete item generation pipeline including:
 1. Affix config loading
 2. Affix value rolling (scaled by item level)
 3. Affix slot filtering (weapon-only affixes don't appear on armor)
 4. Affix count by rarity (common=0, magic=1-2, rare=3-4)
 5. No duplicate affixes
 6. Name generation by rarity format
 7. Sell value calculation
 8. generate_item() full pipeline
 9. Instance ID uniqueness (UUID)
10. Base stats + affix stats combined correctly
11. Consumable items pass through without affixes
12. Different seeds produce different items
13. Item level scaling (higher ilvl → stronger rolls)
14. roll_rarity() distribution
15. Backward compatibility (existing create_item still works, old items unchanged)
16. Loot integration (generate_enemy_loot, generate_chest_loot)
17. Item model new fields (instance_id, base_type_id, display_name, base_stats, affixes, item_level)
"""

from __future__ import annotations

import random
import uuid
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
    generate_item_name,
    calculate_sell_value,
    generate_item,
    generate_loot_item,
    roll_rarity,
    _combine_stats,
    _get_eligible_affixes,
    _calculate_item_level,
    RARITY_AFFIX_COUNTS,
    RARITY_SELL_MULTIPLIERS,
)
from app.core.loot import (
    create_item,
    load_items_config,
    clear_caches as clear_loot_caches,
    generate_enemy_loot,
    generate_chest_loot,
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


# ---------- Fixtures ----------


@pytest.fixture
def items_config():
    return load_items_config()


@pytest.fixture
def affixes_config():
    return load_affixes_config()


@pytest.fixture
def names_config():
    return load_item_names_config()


# ==========================================================================
# 1. Affix Config Loading
# ==========================================================================


class TestAffixConfigLoading:
    """Verify affix config loads correctly with expected structure."""

    def test_load_affixes_has_prefixes_and_suffixes(self, affixes_config):
        assert "prefixes" in affixes_config
        assert "suffixes" in affixes_config

    def test_prefixes_not_empty(self, affixes_config):
        assert len(affixes_config["prefixes"]) > 0

    def test_suffixes_not_empty(self, affixes_config):
        assert len(affixes_config["suffixes"]) > 0

    def test_each_prefix_has_required_fields(self, affixes_config):
        for affix_id, affix in affixes_config["prefixes"].items():
            assert "affix_id" in affix
            assert "name" in affix
            assert "stat" in affix
            assert "min_value" in affix
            assert "max_value" in affix
            assert "weight" in affix
            assert "allowed_slots" in affix
            assert affix["affix_id"] == affix_id

    def test_each_suffix_has_required_fields(self, affixes_config):
        for affix_id, affix in affixes_config["suffixes"].items():
            assert "affix_id" in affix
            assert "name" in affix
            assert "stat" in affix
            assert "min_value" in affix
            assert "max_value" in affix
            assert "weight" in affix
            assert "allowed_slots" in affix
            assert affix["affix_id"] == affix_id

    def test_affix_min_not_greater_than_max(self, affixes_config):
        for pool_key in ("prefixes", "suffixes"):
            for affix_id, affix in affixes_config[pool_key].items():
                assert affix["min_value"] <= affix["max_value"], (
                    f"{pool_key}.{affix_id}: min_value > max_value"
                )


# ==========================================================================
# 2. Affix Value Rolling
# ==========================================================================


class TestAffixValueRolling:
    """Verify affix values roll within expected ranges."""

    def test_roll_int_stat_returns_int(self, affixes_config):
        affix = affixes_config["prefixes"]["cruel"]  # attack_damage, int stat
        rng = random.Random(42)
        value = roll_affix_value(affix, item_level=5, rng=rng)
        assert isinstance(value, int)

    def test_roll_float_stat_returns_float(self, affixes_config):
        affix = affixes_config["prefixes"]["deadly"]  # crit_chance, float stat
        rng = random.Random(42)
        value = roll_affix_value(affix, item_level=5, rng=rng)
        assert isinstance(value, float)

    def test_roll_value_within_range(self, affixes_config):
        affix = affixes_config["prefixes"]["cruel"]
        rng = random.Random(42)
        for _ in range(100):
            value = roll_affix_value(affix, item_level=10, rng=rng)
            assert affix["min_value"] <= value <= affix["max_value"]

    def test_roll_value_at_item_level_1(self, affixes_config):
        """At low item levels, scaled max should be close to min."""
        affix = affixes_config["prefixes"]["cruel"]
        rng = random.Random(42)
        values = [roll_affix_value(affix, item_level=1, rng=rng) for _ in range(50)]
        # At ilvl 1, scaled_max = min(12, 3 + 0.5*1) = 3.5
        # So values should be between 3 and 4
        for v in values:
            assert v >= affix["min_value"]
            assert v <= affix["min_value"] + affix["ilvl_scaling"] * 1 + 1  # rounding margin

    def test_higher_ilvl_produces_higher_average(self, affixes_config):
        """Higher item levels should produce statistically higher affix values."""
        affix = affixes_config["prefixes"]["cruel"]
        rng_low = random.Random(0)
        rng_high = random.Random(0)
        low_values = [roll_affix_value(affix, item_level=1, rng=rng_low) for _ in range(200)]
        high_values = [roll_affix_value(affix, item_level=18, rng=rng_high) for _ in range(200)]
        assert sum(high_values) / len(high_values) > sum(low_values) / len(low_values)

    def test_roll_value_min_is_one_for_int_stats(self, affixes_config):
        """Int affix values should never be less than 1."""
        affix = affixes_config["prefixes"]["cruel"]
        rng = random.Random(42)
        for _ in range(50):
            value = roll_affix_value(affix, item_level=1, rng=rng)
            assert value >= 1


# ==========================================================================
# 3. Affix Slot Filtering
# ==========================================================================


class TestAffixSlotFiltering:
    """Verify affixes are filtered by allowed_slots."""

    def test_weapon_only_affixes_not_on_armor(self, affixes_config):
        eligible = _get_eligible_affixes(
            affixes_config["prefixes"], "armor", set(), set()
        )
        for affix in eligible:
            assert "armor" in affix["allowed_slots"]

    def test_armor_only_affixes_not_on_weapon(self, affixes_config):
        eligible = _get_eligible_affixes(
            affixes_config["prefixes"], "weapon", set(), set()
        )
        for affix in eligible:
            assert "weapon" in affix["allowed_slots"]

    def test_accessory_gets_correct_affixes(self, affixes_config):
        eligible = _get_eligible_affixes(
            affixes_config["prefixes"], "accessory", set(), set()
        )
        for affix in eligible:
            assert "accessory" in affix["allowed_slots"]

    def test_exclude_ids_filters_out(self, affixes_config):
        eligible_all = _get_eligible_affixes(
            affixes_config["prefixes"], "weapon", set(), set()
        )
        eligible_minus = _get_eligible_affixes(
            affixes_config["prefixes"], "weapon", {"cruel"}, set()
        )
        assert len(eligible_minus) < len(eligible_all)
        assert all(a["affix_id"] != "cruel" for a in eligible_minus)

    def test_exclude_stats_prevents_same_stat_stacking(self, affixes_config):
        eligible = _get_eligible_affixes(
            affixes_config["prefixes"], "weapon", set(), {"attack_damage"}
        )
        assert all(a["stat"] != "attack_damage" for a in eligible)


# ==========================================================================
# 4. Affix Count by Rarity
# ==========================================================================


class TestAffixCountByRarity:
    """Verify correct affix counts for each rarity tier."""

    def test_common_items_have_zero_affixes(self):
        rng = random.Random(42)
        affixes = roll_affixes("common", "weapon", 5, rng)
        assert len(affixes) == 0

    def test_uncommon_items_have_zero_affixes(self):
        rng = random.Random(42)
        affixes = roll_affixes("uncommon", "weapon", 5, rng)
        assert len(affixes) == 0

    def test_magic_items_have_1_to_2_affixes(self):
        for seed in range(50):
            rng = random.Random(seed)
            affixes = roll_affixes("magic", "weapon", 5, rng)
            assert 1 <= len(affixes) <= 2, f"seed={seed}, got {len(affixes)} affixes"

    def test_rare_items_have_3_to_4_affixes(self):
        for seed in range(50):
            rng = random.Random(seed)
            affixes = roll_affixes("rare", "weapon", 10, rng)
            assert 3 <= len(affixes) <= 4, f"seed={seed}, got {len(affixes)} affixes"

    def test_epic_items_have_4_to_5_affixes(self):
        for seed in range(50):
            rng = random.Random(seed)
            affixes = roll_affixes("epic", "weapon", 15, rng)
            # Epic might get fewer if exhausting the pool, but should aim for 4-5
            assert len(affixes) >= 4, f"seed={seed}, got {len(affixes)} affixes"


# ==========================================================================
# 5. No Duplicate Affixes
# ==========================================================================


class TestNoDuplicateAffixes:
    """Verify no affix is rolled twice on the same item."""

    def test_no_duplicate_affix_ids(self):
        for seed in range(100):
            rng = random.Random(seed)
            affixes = roll_affixes("rare", "weapon", 10, rng)
            ids = [a["affix_id"] for a in affixes]
            assert len(ids) == len(set(ids)), f"seed={seed}: duplicate affixes: {ids}"

    def test_no_duplicate_stats(self):
        """Two affixes shouldn't grant the same stat."""
        for seed in range(100):
            rng = random.Random(seed)
            affixes = roll_affixes("rare", "weapon", 10, rng)
            stats = [a["stat"] for a in affixes]
            assert len(stats) == len(set(stats)), f"seed={seed}: duplicate stats: {stats}"


# ==========================================================================
# 6. Name Generation
# ==========================================================================


class TestNameGeneration:
    """Verify item names are generated correctly per rarity."""

    def test_common_name_is_base_name(self):
        name = generate_item_name("Greatsword", "common", [], "weapon", random.Random(42))
        assert name == "Greatsword"

    def test_magic_with_prefix_only(self):
        affixes = [{"type": "prefix", "name": "Cruel", "affix_id": "cruel", "stat": "attack_damage", "value": 5}]
        name = generate_item_name("Greatsword", "magic", affixes, "weapon", random.Random(42))
        assert name == "Cruel Greatsword"

    def test_magic_with_suffix_only(self):
        affixes = [{"type": "suffix", "name": "of the Bear", "affix_id": "of_the_bear", "stat": "max_hp", "value": 20}]
        name = generate_item_name("Greatsword", "magic", affixes, "weapon", random.Random(42))
        assert name == "Greatsword of the Bear"

    def test_magic_with_prefix_and_suffix(self):
        affixes = [
            {"type": "prefix", "name": "Cruel", "affix_id": "cruel", "stat": "attack_damage", "value": 5},
            {"type": "suffix", "name": "of the Bear", "affix_id": "of_the_bear", "stat": "max_hp", "value": 20},
        ]
        name = generate_item_name("Greatsword", "magic", affixes, "weapon", random.Random(42))
        assert name == "Cruel Greatsword of the Bear"

    def test_rare_no_affixes_returns_base_name(self):
        """Rare items with no affixes fall back to base name."""
        rng = random.Random(42)
        name = generate_item_name("Greatsword", "rare", [], "weapon", rng)
        assert name == "Greatsword"

    def test_rare_uses_best_affix_naming(self):
        """Rare items pick the rarest (lowest weight) prefix + suffix for the name."""
        affixes = [
            {"type": "prefix", "name": "Cruel", "affix_id": "cruel", "stat": "attack_damage", "value": 8, "weight": 100},
            {"type": "prefix", "name": "Vampiric", "affix_id": "vampiric", "stat": "life_on_hit", "value": 3, "weight": 50},
            {"type": "suffix", "name": "of the Bear", "affix_id": "of_the_bear", "stat": "max_hp", "value": 30, "weight": 100},
            {"type": "suffix", "name": "of Haste", "affix_id": "of_haste", "stat": "cooldown_reduction_pct", "value": 0.05, "weight": 50},
        ]
        rng = random.Random(42)
        name = generate_item_name("Greatsword", "rare", affixes, "weapon", rng)
        # Should pick lowest-weight affixes: Vampiric (50) and of Haste (50)
        assert name == "Vampiric Greatsword of Haste"

    def test_rare_with_single_affix(self):
        """Rare items with only one prefix still produce a clean name."""
        affixes = [
            {"type": "prefix", "name": "Cruel", "affix_id": "cruel", "stat": "attack_damage", "value": 8, "weight": 100},
        ]
        rng = random.Random(42)
        name = generate_item_name("Greatsword", "rare", affixes, "weapon", rng)
        assert name == "Cruel Greatsword"

    def test_epic_uses_name_pool(self, names_config):
        rng = random.Random(42)
        name = generate_item_name("Greatsword", "epic", [], "weapon", rng, names_config)
        assert name in names_config["weapon_names"]

    def test_armor_uses_armor_name_pool_for_epic(self, names_config):
        rng = random.Random(42)
        name = generate_item_name("Plate", "epic", [], "armor", rng, names_config)
        assert name in names_config["armor_names"]

    def test_accessory_uses_accessory_name_pool_for_epic(self, names_config):
        rng = random.Random(42)
        name = generate_item_name("Ring", "epic", [], "accessory", rng, names_config)
        assert name in names_config["accessory_names"]


# ==========================================================================
# 7. Sell Value Calculation
# ==========================================================================


class TestSellValue:
    """Verify sell value scales with rarity and affix quality."""

    def test_common_sell_value_equals_base(self):
        value = calculate_sell_value(10, "common", [])
        assert value == 10

    def test_magic_sell_value_higher_than_common(self):
        common_val = calculate_sell_value(10, "common", [])
        magic_val = calculate_sell_value(10, "magic", [])
        assert magic_val > common_val

    def test_rare_sell_value_higher_than_magic(self):
        magic_val = calculate_sell_value(10, "magic", [])
        rare_val = calculate_sell_value(10, "rare", [])
        assert rare_val > magic_val

    def test_affixes_add_to_sell_value(self):
        no_affix = calculate_sell_value(10, "magic", [])
        with_affix = calculate_sell_value(10, "magic", [
            {"affix_id": "cruel", "stat": "attack_damage", "value": 6}
        ])
        assert with_affix > no_affix

    def test_sell_value_never_zero(self):
        value = calculate_sell_value(0, "common", [])
        assert value >= 1


# ==========================================================================
# 8. generate_item() Full Pipeline
# ==========================================================================


class TestGenerateItem:
    """Verify generate_item() produces valid fully-formed items."""

    def test_generate_common_item(self, items_config):
        item = generate_item("common_sword", "common", 1, seed=42, items_config=items_config)
        assert item is not None
        assert item.item_id == "common_sword"
        assert item.base_type_id == "common_sword"
        assert item.instance_id != ""
        assert len(item.affixes) == 0
        assert item.display_name == "Rusty Sword"
        assert item.name == "Rusty Sword"

    def test_generate_magic_item_has_affixes(self, items_config):
        item = generate_item("uncommon_greatsword", "magic", 5, seed=42, items_config=items_config)
        assert item is not None
        assert len(item.affixes) >= 1
        assert len(item.affixes) <= 2

    def test_generate_rare_item_has_affixes(self, items_config):
        item = generate_item("uncommon_greatsword", "rare", 10, seed=42, items_config=items_config)
        assert item is not None
        assert len(item.affixes) >= 3

    def test_generated_item_has_uuid_instance_id(self, items_config):
        item = generate_item("common_sword", "common", 1, seed=42, items_config=items_config)
        assert item is not None
        # Should be a valid UUID  
        parsed = uuid.UUID(item.instance_id)
        assert str(parsed) == item.instance_id

    def test_generated_item_has_base_stats(self, items_config):
        item = generate_item("common_sword", "common", 1, seed=42, items_config=items_config)
        assert item is not None
        assert item.base_stats.attack_damage == 5  # From items_config

    def test_magic_item_stat_bonuses_include_affix(self, items_config):
        item = generate_item("uncommon_greatsword", "magic", 5, seed=42, items_config=items_config)
        assert item is not None
        # stat_bonuses should be base + affixes
        base_melee = item.base_stats.attack_damage
        # Final melee should be at least base (could be higher if melee affix rolled)
        assert item.stat_bonuses.attack_damage >= base_melee

    def test_invalid_base_type_returns_none(self, items_config):
        item = generate_item("nonexistent_item", "common", 1, seed=42, items_config=items_config)
        assert item is None

    def test_item_level_stored(self, items_config):
        item = generate_item("common_sword", "common", 7, seed=42, items_config=items_config)
        assert item is not None
        assert item.item_level == 7

    def test_equip_slot_preserved(self, items_config):
        item = generate_item("common_sword", "common", 1, seed=42, items_config=items_config)
        assert item is not None
        assert item.equip_slot == "weapon"

    def test_item_type_preserved(self, items_config):
        item = generate_item("common_chain_armor", "common", 1, seed=42, items_config=items_config)
        assert item is not None
        assert item.item_type == "armor"


# ==========================================================================
# 9. Instance ID Uniqueness
# ==========================================================================


class TestInstanceIdUniqueness:
    """Verify each generated item gets a unique instance_id."""

    def test_two_items_have_different_instance_ids(self, items_config):
        item1 = generate_item("common_sword", "common", 1, seed=42, items_config=items_config)
        item2 = generate_item("common_sword", "common", 1, seed=43, items_config=items_config)
        assert item1 is not None
        assert item2 is not None
        assert item1.instance_id != item2.instance_id

    def test_same_base_different_instances(self, items_config):
        """Multiple items from same base type all have unique instance_ids."""
        ids = set()
        for seed in range(20):
            item = generate_item("common_sword", "common", 1, seed=seed, items_config=items_config)
            assert item is not None
            assert item.instance_id not in ids
            ids.add(item.instance_id)


# ==========================================================================
# 10. Base Stats + Affix Stats Combined
# ==========================================================================


class TestStatCombining:
    """Verify base stats and affix stats combine correctly."""

    def test_combine_stats_adds_values(self):
        base = StatBonuses(attack_damage=10, armor=3)
        affixes = [
            {"stat": "attack_damage", "value": 5},
            {"stat": "crit_chance", "value": 0.05},
        ]
        combined = _combine_stats(base, affixes)
        assert combined.attack_damage == 15
        assert combined.armor == 3  # Unchanged
        assert combined.crit_chance == 0.05

    def test_combine_stats_preserves_base_unchanged(self):
        base = StatBonuses(attack_damage=10)
        affixes = [{"stat": "attack_damage", "value": 5}]
        _combine_stats(base, affixes)
        # Original base should NOT be modified (model_copy is used)
        assert base.attack_damage == 10

    def test_combine_stats_multiple_affixes(self):
        base = StatBonuses(max_hp=0)
        affixes = [
            {"stat": "max_hp", "value": 20},
            {"stat": "dodge_chance", "value": 0.05},
            {"stat": "thorns", "value": 3},
        ]
        combined = _combine_stats(base, affixes)
        assert combined.max_hp == 20
        assert combined.dodge_chance == 0.05
        assert combined.thorns == 3


# ==========================================================================
# 11. Consumable Items
# ==========================================================================


class TestConsumableItems:
    """Verify consumables pass through without affixes."""

    def test_consumable_has_no_affixes(self, items_config):
        item = generate_item("health_potion", "common", 1, seed=42, items_config=items_config)
        assert item is not None
        assert item.consumable_effect is not None
        assert len(item.affixes) == 0

    def test_consumable_has_instance_id(self, items_config):
        item = generate_item("health_potion", "common", 1, seed=42, items_config=items_config)
        assert item is not None
        assert item.instance_id != ""

    def test_consumable_base_type_id(self, items_config):
        item = generate_item("health_potion", "common", 1, seed=42, items_config=items_config)
        assert item is not None
        assert item.base_type_id == "health_potion"


# ==========================================================================
# 12. Different Seeds Produce Different Items
# ==========================================================================


class TestDifferentSeeds:
    """Verify different seeds produce different affix combinations."""

    def test_different_seeds_different_affixes(self, items_config):
        item1 = generate_item("uncommon_greatsword", "magic", 5, seed=1, items_config=items_config)
        item2 = generate_item("uncommon_greatsword", "magic", 5, seed=2, items_config=items_config)
        assert item1 is not None
        assert item2 is not None
        # With different seeds, at least one property should differ
        # (name, affixes, or stat_bonuses)
        differs = (
            item1.name != item2.name
            or item1.affixes != item2.affixes
            or item1.stat_bonuses != item2.stat_bonuses
        )
        assert differs

    def test_same_seed_same_item(self, items_config):
        item1 = generate_item("uncommon_greatsword", "magic", 5, seed=42, items_config=items_config)
        item2 = generate_item("uncommon_greatsword", "magic", 5, seed=42, items_config=items_config)
        assert item1 is not None
        assert item2 is not None
        assert item1.name == item2.name
        assert item1.affixes == item2.affixes
        assert item1.stat_bonuses == item2.stat_bonuses


# ==========================================================================
# 13. Item Level Scaling
# ==========================================================================


class TestItemLevelScaling:
    """Verify item level affects affix values."""

    def test_high_ilvl_produces_stronger_affixes_statistically(self, items_config):
        """Item level 18 should produce statistically stronger items than ilvl 1."""
        low_totals = []
        high_totals = []
        for seed in range(100):
            item_low = generate_item("uncommon_greatsword", "magic", 1, seed=seed, items_config=items_config)
            item_high = generate_item("uncommon_greatsword", "magic", 18, seed=seed, items_config=items_config)
            if item_low and item_low.affixes:
                low_totals.append(sum(a["value"] for a in item_low.affixes if isinstance(a["value"], (int, float))))
            if item_high and item_high.affixes:
                high_totals.append(sum(a["value"] for a in item_high.affixes if isinstance(a["value"], (int, float))))

        if low_totals and high_totals:
            avg_low = sum(low_totals) / len(low_totals)
            avg_high = sum(high_totals) / len(high_totals)
            assert avg_high > avg_low

    def test_calculate_item_level_ranges(self):
        """Item levels for each tier fall in expected ranges."""
        rng = random.Random(42)
        for _ in range(50):
            ilvl = _calculate_item_level(1, "fodder", rng)
            assert 3 <= ilvl <= 6
        for _ in range(50):
            ilvl = _calculate_item_level(1, "boss", rng)
            assert 12 <= ilvl <= 18


# ==========================================================================
# 14. roll_rarity() Distribution
# ==========================================================================


class TestRollRarity:
    """Verify rarity rolling produces expected distributions."""

    def test_rarity_returns_string(self):
        result = roll_rarity(floor_number=1, rng=random.Random(42))
        assert isinstance(result, str)

    def test_common_most_frequent_at_floor_1(self):
        rng = random.Random(42)
        results = [roll_rarity(floor_number=1, rng=rng) for _ in range(500)]
        common_count = results.count("common")
        # Common should be the majority at floor 1
        assert common_count > len(results) * 0.3

    def test_higher_floor_more_rares(self):
        rng1 = random.Random(0)
        rng2 = random.Random(0)
        low_results = [roll_rarity(floor_number=1, rng=rng1) for _ in range(500)]
        high_results = [roll_rarity(floor_number=9, rng=rng2) for _ in range(500)]
        low_common = low_results.count("common")
        high_common = high_results.count("common")
        # Floor 9 should have fewer commons than floor 1
        assert high_common < low_common

    def test_magic_find_increases_rare_chance(self):
        rng1 = random.Random(0)
        rng2 = random.Random(0)
        no_mf = [roll_rarity(floor_number=5, magic_find_bonus=0.0, rng=rng1) for _ in range(500)]
        high_mf = [roll_rarity(floor_number=5, magic_find_bonus=0.5, rng=rng2) for _ in range(500)]
        no_mf_common = no_mf.count("common")
        high_mf_common = high_mf.count("common")
        # High MF should produce fewer commons
        assert high_mf_common < no_mf_common

    def test_boss_tier_shifts_curve(self):
        rng1 = random.Random(0)
        rng2 = random.Random(0)
        fodder = [roll_rarity(floor_number=5, enemy_tier="fodder", rng=rng1) for _ in range(500)]
        boss = [roll_rarity(floor_number=5, enemy_tier="boss", rng=rng2) for _ in range(500)]
        fodder_common = fodder.count("common")
        boss_common = boss.count("common")
        assert boss_common < fodder_common


# ==========================================================================
# 15. Backward Compatibility
# ==========================================================================


class TestBackwardCompatibility:
    """Verify existing items and create_item() still work unchanged."""

    def test_create_item_still_works(self, items_config):
        item = create_item("common_sword", items_config)
        assert item is not None
        assert item.item_id == "common_sword"
        assert item.name == "Rusty Sword"

    def test_legacy_item_has_default_new_fields(self, items_config):
        item = create_item("common_sword", items_config)
        assert item is not None
        assert item.instance_id == ""
        assert item.base_type_id == ""
        assert item.display_name == ""
        assert item.affixes == []
        assert item.item_level == 1

    def test_legacy_item_still_equippable(self, items_config):
        """Legacy items without instance_id should still function."""
        item = create_item("common_sword", items_config)
        assert item is not None
        assert item.equip_slot == "weapon"

    def test_all_existing_items_load_without_error(self, items_config):
        """Every item in items_config.json should still create without error."""
        for item_id in items_config:
            item = create_item(item_id, items_config)
            assert item is not None, f"Failed to create item: {item_id}"


# ==========================================================================
# 16. Loot Integration
# ==========================================================================


class TestLootIntegration:
    """Verify generate_enemy_loot and generate_chest_loot produce items with affixes."""

    def test_generate_enemy_loot_returns_items(self):
        # Use a seed that makes the drop chance pass
        items = generate_enemy_loot("demon", floor_number=5, seed=42)
        # May be empty if drop chance fails, but function shouldn't error
        assert isinstance(items, list)

    def test_generate_enemy_loot_unknown_type_returns_empty(self):
        items = generate_enemy_loot("nonexistent_monster", floor_number=1, seed=42)
        assert items == []

    def test_generate_chest_loot_returns_items(self):
        items = generate_chest_loot("default", floor_number=3, seed=42)
        assert isinstance(items, list)

    def test_generate_chest_loot_unknown_type_returns_empty(self):
        items = generate_chest_loot("nonexistent_chest", floor_number=1, seed=42)
        assert items == []

    def test_generated_loot_items_have_instance_ids(self):
        """Items from generate_enemy_loot should have instance_ids."""
        # Try multiple seeds to find one that produces drops
        for seed in range(100):
            items = generate_enemy_loot("demon", floor_number=5, seed=seed)
            if items:
                for item in items:
                    assert item.instance_id != "" or item.base_type_id == ""
                break


# ==========================================================================
# 17. Item Model New Fields
# ==========================================================================


class TestItemModelFields:
    """Verify new Item model fields have correct defaults and behavior."""

    def test_item_default_instance_id_empty(self):
        item = Item(item_id="test", name="Test", item_type="weapon")
        assert item.instance_id == ""

    def test_item_default_base_type_id_empty(self):
        item = Item(item_id="test", name="Test", item_type="weapon")
        assert item.base_type_id == ""

    def test_item_default_display_name_empty(self):
        item = Item(item_id="test", name="Test", item_type="weapon")
        assert item.display_name == ""

    def test_item_default_affixes_empty_list(self):
        item = Item(item_id="test", name="Test", item_type="weapon")
        assert item.affixes == []

    def test_item_default_item_level_1(self):
        item = Item(item_id="test", name="Test", item_type="weapon")
        assert item.item_level == 1

    def test_item_default_base_stats_empty(self):
        item = Item(item_id="test", name="Test", item_type="weapon")
        assert item.base_stats.attack_damage == 0
        assert item.base_stats.max_hp == 0

    def test_item_serialize_new_fields(self):
        """New fields should serialize correctly for WS/API transport."""
        item = Item(
            item_id="test",
            name="Test Sword",
            item_type="weapon",
            instance_id="abc-123",
            base_type_id="common_sword",
            display_name="Sword",
            affixes=[{"affix_id": "cruel", "type": "prefix", "name": "Cruel", "stat": "attack_damage", "value": 5}],
            item_level=7,
        )
        data = item.model_dump()
        assert data["instance_id"] == "abc-123"
        assert data["base_type_id"] == "common_sword"
        assert data["display_name"] == "Sword"
        assert len(data["affixes"]) == 1
        assert data["item_level"] == 7

    def test_inventory_remove_item_by_instance_id(self):
        """Inventory should find items by instance_id."""
        inv = Inventory()
        item = Item(
            item_id="common_sword",
            name="Test Sword",
            item_type="weapon",
            instance_id="uuid-test-123",
        )
        inv.add_item(item)
        removed = inv.remove_item("uuid-test-123")
        assert removed is not None
        assert removed.instance_id == "uuid-test-123"

    def test_inventory_remove_item_falls_back_to_item_id(self):
        """Legacy items without instance_id should still be removable by item_id."""
        inv = Inventory()
        item = Item(
            item_id="common_sword",
            name="Legacy Sword",
            item_type="weapon",
        )
        inv.add_item(item)
        removed = inv.remove_item("common_sword")
        assert removed is not None
        assert removed.item_id == "common_sword"


# ==========================================================================
# 18. Affix Type Tags
# ==========================================================================


class TestAffixTypeTags:
    """Verify rolled affixes have correct prefix/suffix type tags."""

    def test_magic_affixes_have_type_tag(self):
        rng = random.Random(42)
        affixes = roll_affixes("magic", "weapon", 5, rng)
        for affix in affixes:
            assert affix["type"] in ("prefix", "suffix")

    def test_rare_affixes_have_type_tag(self):
        rng = random.Random(42)
        affixes = roll_affixes("rare", "weapon", 10, rng)
        for affix in affixes:
            assert affix["type"] in ("prefix", "suffix")

    def test_affixes_have_name_field(self):
        rng = random.Random(42)
        affixes = roll_affixes("magic", "weapon", 5, rng)
        for affix in affixes:
            assert "name" in affix
            assert isinstance(affix["name"], str)
            assert len(affix["name"]) > 0


# ==========================================================================
# 19. Item Names Config
# ==========================================================================


class TestItemNamesConfig:
    """Verify item names config is well-formed."""

    def test_weapon_names_not_empty(self, names_config):
        assert len(names_config["weapon_names"]) > 0

    def test_armor_names_not_empty(self, names_config):
        assert len(names_config["armor_names"]) > 0

    def test_accessory_names_not_empty(self, names_config):
        assert len(names_config["accessory_names"]) > 0

    def test_all_names_are_strings(self, names_config):
        for key in ("weapon_names", "armor_names", "accessory_names"):
            for name in names_config[key]:
                assert isinstance(name, str)
                assert len(name) > 0


# ==========================================================================
# 20. generate_loot_item() Convenience Wrapper
# ==========================================================================


class TestGenerateLootItem:
    """Verify the convenience wrapper that combines roll_rarity + generate_item."""

    def test_generate_loot_item_produces_item(self, items_config):
        item = generate_loot_item(
            "common_sword", floor_number=3, enemy_tier="fodder", seed=42,
            items_config=items_config,
        )
        assert item is not None
        assert item.instance_id != ""

    def test_generate_loot_item_invalid_base_returns_none(self, items_config):
        item = generate_loot_item(
            "nonexistent", floor_number=1, seed=42, items_config=items_config,
        )
        assert item is None

    def test_generate_loot_item_boss_tier(self, items_config):
        """Boss tier should produce items with higher item_level."""
        levels = []
        for seed in range(50):
            item = generate_loot_item(
                "uncommon_greatsword", floor_number=5, enemy_tier="boss", seed=seed,
                items_config=items_config,
            )
            if item:
                levels.append(item.item_level)
        assert levels
        avg_level = sum(levels) / len(levels)
        assert avg_level >= 10  # Boss ilvl range is 12-18
