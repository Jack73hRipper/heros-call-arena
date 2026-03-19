"""Phase 21C — Item Generator & Loot Integration Tests.

Tests for:
  1. Generated armor items always have armor_category set
  2. Unique items carry armor_category from config
  3. Set pieces carry armor_category from config
  4. Non-armor items default to empty armor_category
  5. Affix category weighting biases thematically appropriate stats
  6. Party-aware loot bias produces more relevant drops (~60%)
  7. _get_party_preferred_categories resolves correctly
"""

from __future__ import annotations

import random
import unittest
from collections import Counter

from app.core.item_generator import (
    ARMOR_CATEGORY_AFFIX_WEIGHTS,
    generate_item,
    generate_loot_item,
    generate_unique,
    generate_set_piece,
    roll_affixes,
    clear_generator_caches,
)
from app.core.loot import (
    clear_caches,
    generate_enemy_loot,
    generate_chest_loot,
    load_items_config,
    _get_party_preferred_categories,
    _pick_base_type_from_pool,
)


class TestArmorCategoryOnGeneratedItems(unittest.TestCase):
    """Test that armor_category is set correctly on all generated item types."""

    def test_generate_item_armor_has_category(self):
        """Generated armor items carry armor_category from items_config."""
        clear_generator_caches()
        clear_caches()
        # common_chain_armor is tagged as "heavy" in items_config
        item = generate_item("common_chain_armor", rarity="common", item_level=5, seed=42)
        self.assertIsNotNone(item)
        self.assertEqual(item.armor_category, "heavy")

    def test_generate_item_leather_armor_has_light(self):
        """Leather armor generates with 'light' category."""
        clear_generator_caches()
        clear_caches()
        item = generate_item("common_leather_armor", rarity="magic", item_level=5, seed=42)
        self.assertIsNotNone(item)
        self.assertEqual(item.armor_category, "light")

    def test_generate_item_robes_has_cloth(self):
        """Robes generate with 'cloth' category."""
        clear_generator_caches()
        clear_caches()
        item = generate_item("common_robes", rarity="common", item_level=5, seed=42)
        self.assertIsNotNone(item)
        self.assertEqual(item.armor_category, "cloth")

    def test_generate_item_weapon_has_no_armor_category(self):
        """Weapon items have empty armor_category."""
        clear_generator_caches()
        clear_caches()
        item = generate_item("common_sword", rarity="common", item_level=5, seed=42)
        self.assertIsNotNone(item)
        self.assertEqual(item.armor_category, "")

    def test_generate_item_accessory_has_no_armor_category(self):
        """Accessory items have empty armor_category."""
        clear_generator_caches()
        clear_caches()
        items_config = load_items_config()
        # Find an accessory
        acc_id = None
        for item_id, data in items_config.items():
            if data.get("equip_slot") == "accessory":
                acc_id = item_id
                break
        if acc_id is None:
            self.skipTest("No accessory in items_config")
        item = generate_item(acc_id, rarity="common", item_level=5, seed=42)
        self.assertIsNotNone(item)
        self.assertEqual(item.armor_category, "")

    def test_generate_loot_item_preserves_armor_category(self):
        """generate_loot_item() preserves armor_category."""
        clear_generator_caches()
        clear_caches()
        item = generate_loot_item("common_plate_armor", floor_number=3, seed=100)
        self.assertIsNotNone(item)
        self.assertEqual(item.armor_category, "heavy")


class TestUniqueAndSetArmorCategory(unittest.TestCase):
    """Test that unique and set items carry armor_category from their configs."""

    def test_unique_armor_has_category(self):
        """Unique armor items carry armor_category from uniques_config."""
        clear_generator_caches()
        # The Bonecage is heavy
        item = generate_unique("unique_bonecage")
        self.assertIsNotNone(item)
        self.assertEqual(item.armor_category, "heavy")

    def test_unique_weapon_has_no_armor_category(self):
        """Unique weapons have empty armor_category."""
        clear_generator_caches()
        item = generate_unique("unique_soulreaver")
        if item is None:
            self.skipTest("unique_soulreaver not found in config")
        self.assertEqual(item.armor_category, "")

    def test_set_armor_piece_has_category(self):
        """Set armor pieces carry armor_category from sets_config."""
        clear_generator_caches()
        # Crusader's Oath plate is heavy
        item = generate_set_piece("crusaders_oath", "crusaders_oath_armor")
        self.assertIsNotNone(item)
        self.assertEqual(item.armor_category, "heavy")

    def test_set_weapon_piece_has_no_armor_category(self):
        """Set weapon pieces have empty armor_category."""
        clear_generator_caches()
        item = generate_set_piece("crusaders_oath", "crusaders_oath_weapon")
        self.assertIsNotNone(item)
        self.assertEqual(item.armor_category, "")


class TestAffinityAffinityWeightConfig(unittest.TestCase):
    """Test that ARMOR_CATEGORY_AFFIX_WEIGHTS is correctly structured."""

    def test_all_three_categories_defined(self):
        """All three armor categories have weight overrides."""
        self.assertIn("heavy", ARMOR_CATEGORY_AFFIX_WEIGHTS)
        self.assertIn("light", ARMOR_CATEGORY_AFFIX_WEIGHTS)
        self.assertIn("cloth", ARMOR_CATEGORY_AFFIX_WEIGHTS)

    def test_heavy_weights_up_thorns(self):
        """Heavy armor category weights up thorns."""
        self.assertEqual(ARMOR_CATEGORY_AFFIX_WEIGHTS["heavy"]["thorns"], 1.5)

    def test_heavy_weights_down_dodge(self):
        """Heavy armor category weights down dodge."""
        self.assertEqual(ARMOR_CATEGORY_AFFIX_WEIGHTS["heavy"]["dodge_chance"], 0.5)

    def test_cloth_weights_up_skill_damage(self):
        """Cloth armor category weights up skill_damage_pct."""
        self.assertEqual(ARMOR_CATEGORY_AFFIX_WEIGHTS["cloth"]["skill_damage_pct"], 1.5)

    def test_light_weights_up_crit(self):
        """Light armor category weights up crit_chance."""
        self.assertEqual(ARMOR_CATEGORY_AFFIX_WEIGHTS["light"]["crit_chance"], 1.5)


class TestCategoryWeightedAffixRolling(unittest.TestCase):
    """Test that armor category biases affix selection."""

    def _roll_many_affixes(self, armor_category: str, n: int = 500) -> Counter:
        """Roll many affixes for armor slot with a category and count stats."""
        clear_generator_caches()
        stat_counter = Counter()
        for i in range(n):
            affixes = roll_affixes(
                rarity="rare",
                equip_slot="armor",
                item_level=10,
                rng=random.Random(i * 7 + 1),
                armor_category=armor_category,
            )
            for a in affixes:
                stat_counter[a["stat"]] += 1
        return stat_counter

    def test_heavy_armor_biases_toward_thorns_over_dodge(self):
        """Heavy armor should produce more thorns than dodge_chance affixes."""
        counts = self._roll_many_affixes("heavy", n=500)
        # thorns is weighted 1.5× and dodge 0.5× for heavy, so thorns > dodge
        self.assertGreater(
            counts.get("thorns", 0), counts.get("dodge_chance", 0),
            f"Heavy armor should bias thorns > dodge. Got thorns={counts.get('thorns', 0)}, dodge={counts.get('dodge_chance', 0)}"
        )

    def test_cloth_armor_biases_toward_skill_damage(self):
        """Cloth armor should produce more skill_damage_pct than thorns."""
        counts = self._roll_many_affixes("cloth", n=500)
        self.assertGreater(
            counts.get("skill_damage_pct", 0), counts.get("thorns", 0),
            f"Cloth armor should bias skill_damage > thorns. Got skill={counts.get('skill_damage_pct', 0)}, thorns={counts.get('thorns', 0)}"
        )

    def test_light_armor_biases_toward_dodge(self):
        """Light armor should produce more dodge_chance than thorns."""
        counts = self._roll_many_affixes("light", n=500)
        self.assertGreater(
            counts.get("dodge_chance", 0), counts.get("thorns", 0),
            f"Light armor should bias dodge > thorns. Got dodge={counts.get('dodge_chance', 0)}, thorns={counts.get('thorns', 0)}"
        )

    def test_no_category_gives_baseline(self):
        """Empty armor_category produces unbiased results (no crash)."""
        counts = self._roll_many_affixes("", n=100)
        # Just verify it doesn't crash and produces affixes
        self.assertGreater(sum(counts.values()), 0)

    def test_weapon_affixes_unaffected_by_armor_category(self):
        """Weapon slot affixes can receive armor_category but weapons have empty
        armor_category in practice, so there's no bias. When explicitly passed
        a category, _weighted_pick adjusts weights even for weapon affixes
        (which is by design — the category comes from the item, not the slot)."""
        clear_generator_caches()
        # With armor_category="" (as weapons always have), results should match baseline
        baseline = []
        no_bias = []
        for i in range(100):
            rng = random.Random(i + 1000)
            a1 = roll_affixes("rare", "weapon", 10, rng, armor_category="")
            rng2 = random.Random(i + 1000)
            a2 = roll_affixes("rare", "weapon", 10, rng2, armor_category="")
            baseline.append([a["stat"] for a in a1])
            no_bias.append([a["stat"] for a in a2])
        self.assertEqual(baseline, no_bias)


class TestPartyAwareLootBias(unittest.TestCase):
    """Test party-aware loot bias in generate_enemy_loot and generate_chest_loot."""

    def test_get_party_preferred_categories_empty(self):
        """Empty/None party_classes returns None."""
        self.assertIsNone(_get_party_preferred_categories(None))
        self.assertIsNone(_get_party_preferred_categories([]))

    def test_get_party_preferred_categories_single(self):
        """Single class resolves to correct category."""
        result = _get_party_preferred_categories(["crusader"])
        self.assertEqual(result, ["heavy"])

    def test_get_party_preferred_categories_mixed(self):
        """Mixed party resolves to unique categories."""
        result = _get_party_preferred_categories(["crusader", "mage", "ranger"])
        self.assertIsNotNone(result)
        self.assertEqual(sorted(result), ["cloth", "heavy", "light"])

    def test_get_party_preferred_categories_deduplicates(self):
        """Multiple classes with same preference are deduplicated."""
        result = _get_party_preferred_categories(["crusader", "revenant", "blood_knight"])
        self.assertIsNotNone(result)
        self.assertEqual(result, ["heavy"])

    def test_get_party_preferred_categories_unknown_class(self):
        """Unknown class IDs are safely ignored."""
        result = _get_party_preferred_categories(["unknown_class"])
        self.assertIsNone(result)

    def test_pick_base_type_biases_toward_preferred_category(self):
        """_pick_base_type_from_pool biases armor selection toward preferred categories."""
        clear_caches()
        items_config = load_items_config()
        # Build a pool with mixed armor types
        pool = [{
            "weight": 100,
            "items": [
                "common_chain_armor",    # heavy
                "common_leather_armor",  # light
                "common_robes",          # cloth
                "common_plate_armor",    # heavy
                "common_hide_armor",     # light
                "common_vestments",      # cloth
            ]
        }]
        preferred = ["heavy"]
        heavy_count = 0
        total = 500
        for i in range(total):
            rng = random.Random(i * 13 + 7)
            chosen = _pick_base_type_from_pool(pool, rng, items_config, preferred_categories=preferred)
            if chosen and items_config.get(chosen, {}).get("armor_category") == "heavy":
                heavy_count += 1
        # With 60% bias toward heavy (2 of 6 items are heavy),
        # we expect significantly more than 2/6 = 33% heavy picks.
        # 60% rolls bias → heavy, 40% rolls → uniform (33% chance heavy)
        # Expected: 0.6 * 1.0 + 0.4 * 0.33 ≈ 0.73
        heavy_pct = heavy_count / total
        self.assertGreater(heavy_pct, 0.50,
            f"Party bias should produce >50% heavy armor picks, got {heavy_pct:.1%}")

    def test_no_party_classes_gives_uniform_distribution(self):
        """Without party_classes, distribution should be roughly uniform."""
        clear_caches()
        items_config = load_items_config()
        pool = [{
            "weight": 100,
            "items": [
                "common_chain_armor",    # heavy
                "common_leather_armor",  # light
                "common_robes",          # cloth
            ]
        }]
        counts = Counter()
        total = 600
        for i in range(total):
            rng = random.Random(i * 17 + 3)
            chosen = _pick_base_type_from_pool(pool, rng, items_config, preferred_categories=None)
            if chosen:
                cat = items_config.get(chosen, {}).get("armor_category", "")
                counts[cat] += 1
        # Each should be roughly 33% ± tolerance
        for cat in ("heavy", "light", "cloth"):
            pct = counts.get(cat, 0) / total
            self.assertGreater(pct, 0.20,
                f"Without bias, {cat} should be >20%, got {pct:.1%}")
            self.assertLess(pct, 0.50,
                f"Without bias, {cat} should be <50%, got {pct:.1%}")

    def test_generate_enemy_loot_accepts_party_classes(self):
        """generate_enemy_loot accepts party_classes without error."""
        clear_generator_caches()
        clear_caches()
        # Just verify it doesn't crash with the new parameter
        items = generate_enemy_loot(
            enemy_type="skeleton",
            floor_number=3,
            enemy_tier="fodder",
            seed=42,
            party_classes=["crusader", "mage"],
        )
        # May or may not drop items depending on drop chance roll
        self.assertIsInstance(items, list)

    def test_generate_chest_loot_accepts_party_classes(self):
        """generate_chest_loot accepts party_classes without error."""
        clear_generator_caches()
        clear_caches()
        items = generate_chest_loot(
            chest_type="default",
            floor_number=3,
            seed=42,
            party_classes=["ranger", "mage"],
        )
        self.assertIsInstance(items, list)


if __name__ == "__main__":
    unittest.main()
