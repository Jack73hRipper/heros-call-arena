"""
Tests for Phase 4D-1: Item models, configs, and loot generation.

Covers:
- Item model creation and validation
- Equipment and Inventory model operations
- items_config.json loading and parsing
- loot_tables.json loading and cross-reference validation
- Loot generation (roll_enemy_loot, roll_chest_loot, roll_loot_table)
- Boss guaranteed uncommon drops
- PlayerState backward compatibility with new equipment/inventory fields
- Deterministic seeded rolls for reproducibility
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.items import (
    ConsumableEffect,
    ConsumableType,
    Equipment,
    EquipSlot,
    Inventory,
    Item,
    ItemType,
    Rarity,
    StatBonuses,
    INVENTORY_MAX_CAPACITY,
)
from app.models.player import PlayerState, Position
from app.core.loot import (
    clear_caches,
    create_item,
    get_all_item_ids,
    get_items_by_rarity,
    load_items_config,
    load_loot_tables,
    roll_chest_loot,
    roll_enemy_loot,
    roll_loot_table,
    validate_loot_tables,
)


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def _clear_loot_caches():
    """Clear loot config caches before each test for isolation."""
    clear_caches()
    yield
    clear_caches()


# ============================================================
# 1. Item Model Tests
# ============================================================

class TestItemModel:
    """Test Item Pydantic model creation and validation."""

    def test_create_weapon(self):
        item = Item(
            item_id="test_sword",
            name="Test Sword",
            item_type=ItemType.WEAPON,
            rarity=Rarity.COMMON,
            equip_slot=EquipSlot.WEAPON,
            stat_bonuses=StatBonuses(attack_damage=10),
        )
        assert item.item_id == "test_sword"
        assert item.item_type == ItemType.WEAPON
        assert item.rarity == Rarity.COMMON
        assert item.equip_slot == EquipSlot.WEAPON
        assert item.stat_bonuses.attack_damage == 10
        assert item.stat_bonuses.ranged_damage == 0

    def test_create_armor(self):
        item = Item(
            item_id="test_armor",
            name="Test Armor",
            item_type=ItemType.ARMOR,
            equip_slot=EquipSlot.ARMOR,
            stat_bonuses=StatBonuses(armor=5),
        )
        assert item.equip_slot == EquipSlot.ARMOR
        assert item.stat_bonuses.armor == 5

    def test_create_accessory(self):
        item = Item(
            item_id="test_ring",
            name="Test Ring",
            item_type=ItemType.ACCESSORY,
            equip_slot=EquipSlot.ACCESSORY,
            stat_bonuses=StatBonuses(max_hp=30),
        )
        assert item.equip_slot == EquipSlot.ACCESSORY
        assert item.stat_bonuses.max_hp == 30

    def test_create_consumable(self):
        item = Item(
            item_id="test_potion",
            name="Test Potion",
            item_type=ItemType.CONSUMABLE,
            equip_slot=None,
            consumable_effect=ConsumableEffect(type=ConsumableType.HEAL, magnitude=40),
        )
        assert item.item_type == ItemType.CONSUMABLE
        assert item.equip_slot is None
        assert item.consumable_effect is not None
        assert item.consumable_effect.type == ConsumableType.HEAL
        assert item.consumable_effect.magnitude == 40

    def test_create_portal_scroll(self):
        item = Item(
            item_id="test_scroll",
            name="Test Portal Scroll",
            item_type=ItemType.CONSUMABLE,
            consumable_effect=ConsumableEffect(type=ConsumableType.PORTAL, magnitude=0),
        )
        assert item.consumable_effect.type == ConsumableType.PORTAL
        assert item.consumable_effect.magnitude == 0

    def test_item_defaults(self):
        item = Item(item_id="bare", name="Bare", item_type=ItemType.WEAPON)
        assert item.rarity == Rarity.COMMON
        assert item.equip_slot is None
        assert item.consumable_effect is None
        assert item.description == ""
        assert item.sell_value == 0
        assert item.stat_bonuses.attack_damage == 0

    def test_stat_bonuses_defaults(self):
        bonuses = StatBonuses()
        assert bonuses.attack_damage == 0
        assert bonuses.ranged_damage == 0
        assert bonuses.armor == 0
        assert bonuses.max_hp == 0

    def test_item_serialization_roundtrip(self):
        item = Item(
            item_id="test_sword",
            name="Test Sword",
            item_type=ItemType.WEAPON,
            rarity=Rarity.UNCOMMON,
            equip_slot=EquipSlot.WEAPON,
            stat_bonuses=StatBonuses(attack_damage=12),
            description="A test weapon",
            sell_value=35,
        )
        data = item.model_dump()
        restored = Item(**data)
        assert restored.item_id == item.item_id
        assert restored.rarity == Rarity.UNCOMMON
        assert restored.stat_bonuses.attack_damage == 12


# ============================================================
# 2. Equipment Model Tests
# ============================================================

class TestEquipmentModel:
    """Test Equipment model operations."""

    def _make_weapon(self, item_id="sword", attack=10):
        return Item(
            item_id=item_id, name="Sword", item_type=ItemType.WEAPON,
            equip_slot=EquipSlot.WEAPON, stat_bonuses=StatBonuses(attack_damage=attack),
        )

    def _make_armor(self, item_id="plate", armor_val=5):
        return Item(
            item_id=item_id, name="Plate", item_type=ItemType.ARMOR,
            equip_slot=EquipSlot.ARMOR, stat_bonuses=StatBonuses(armor=armor_val),
        )

    def _make_accessory(self, item_id="ring", hp=20):
        return Item(
            item_id=item_id, name="Ring", item_type=ItemType.ACCESSORY,
            equip_slot=EquipSlot.ACCESSORY, stat_bonuses=StatBonuses(max_hp=hp),
        )

    def test_empty_equipment(self):
        eq = Equipment()
        assert eq.weapon is None
        assert eq.armor is None
        assert eq.accessory is None
        assert eq.equipped_items() == []

    def test_equip_weapon(self):
        eq = Equipment()
        weapon = self._make_weapon()
        prev = eq.equip(weapon)
        assert prev is None
        assert eq.weapon is not None
        assert eq.weapon.item_id == "sword"

    def test_equip_replaces_existing(self):
        eq = Equipment()
        old_weapon = self._make_weapon("old_sword", 5)
        new_weapon = self._make_weapon("new_sword", 15)
        eq.equip(old_weapon)
        prev = eq.equip(new_weapon)
        assert prev is not None
        assert prev.item_id == "old_sword"
        assert eq.weapon.item_id == "new_sword"

    def test_unequip(self):
        eq = Equipment()
        eq.equip(self._make_weapon())
        removed = eq.unequip(EquipSlot.WEAPON)
        assert removed is not None
        assert removed.item_id == "sword"
        assert eq.weapon is None

    def test_unequip_empty_slot(self):
        eq = Equipment()
        removed = eq.unequip(EquipSlot.WEAPON)
        assert removed is None

    def test_equip_consumable_rejected(self):
        eq = Equipment()
        potion = Item(
            item_id="potion", name="Potion", item_type=ItemType.CONSUMABLE,
            equip_slot=None,
        )
        prev = eq.equip(potion)
        assert prev is None  # No slot for consumable
        assert eq.weapon is None
        assert eq.armor is None
        assert eq.accessory is None

    def test_total_bonuses_all_slots(self):
        eq = Equipment()
        eq.equip(self._make_weapon(attack=10))
        eq.equip(self._make_armor(armor_val=6))
        eq.equip(self._make_accessory(hp=30))
        bonuses = eq.total_bonuses()
        assert bonuses.attack_damage == 10
        assert bonuses.armor == 6
        assert bonuses.max_hp == 30

    def test_total_bonuses_empty(self):
        eq = Equipment()
        bonuses = eq.total_bonuses()
        assert bonuses.attack_damage == 0
        assert bonuses.armor == 0
        assert bonuses.max_hp == 0

    def test_equipped_items_list(self):
        eq = Equipment()
        eq.equip(self._make_weapon())
        eq.equip(self._make_armor())
        items = eq.equipped_items()
        assert len(items) == 2

    def test_get_slot(self):
        eq = Equipment()
        eq.equip(self._make_weapon())
        assert eq.get_slot(EquipSlot.WEAPON) is not None
        assert eq.get_slot(EquipSlot.ARMOR) is None


# ============================================================
# 3. Inventory Model Tests
# ============================================================

class TestInventoryModel:
    """Test Inventory model operations."""

    def _make_item(self, item_id="item"):
        return Item(item_id=item_id, name=f"Item {item_id}", item_type=ItemType.WEAPON)

    def test_empty_inventory(self):
        inv = Inventory()
        assert len(inv.items) == 0
        assert inv.is_full() is False
        assert inv.free_slots() == INVENTORY_MAX_CAPACITY

    def test_add_item(self):
        inv = Inventory()
        result = inv.add_item(self._make_item("sword"))
        assert result is True
        assert len(inv.items) == 1

    def test_add_item_full(self):
        inv = Inventory()
        for i in range(INVENTORY_MAX_CAPACITY):
            inv.add_item(self._make_item(f"item_{i}"))
        assert inv.is_full() is True
        result = inv.add_item(self._make_item("overflow"))
        assert result is False
        assert len(inv.items) == INVENTORY_MAX_CAPACITY

    def test_remove_item(self):
        inv = Inventory()
        inv.add_item(self._make_item("sword"))
        removed = inv.remove_item("sword")
        assert removed is not None
        assert removed.item_id == "sword"
        assert len(inv.items) == 0

    def test_remove_item_not_found(self):
        inv = Inventory()
        removed = inv.remove_item("nonexistent")
        assert removed is None

    def test_remove_first_matching(self):
        inv = Inventory()
        inv.add_item(self._make_item("potion"))
        inv.add_item(self._make_item("potion"))
        inv.remove_item("potion")
        assert len(inv.items) == 1
        assert inv.items[0].item_id == "potion"

    def test_has_item(self):
        inv = Inventory()
        inv.add_item(self._make_item("sword"))
        assert inv.has_item("sword") is True
        assert inv.has_item("shield") is False

    def test_count_item(self):
        inv = Inventory()
        inv.add_item(self._make_item("potion"))
        inv.add_item(self._make_item("potion"))
        inv.add_item(self._make_item("sword"))
        assert inv.count_item("potion") == 2
        assert inv.count_item("sword") == 1
        assert inv.count_item("shield") == 0

    def test_free_slots(self):
        inv = Inventory()
        inv.add_item(self._make_item("a"))
        inv.add_item(self._make_item("b"))
        assert inv.free_slots() == INVENTORY_MAX_CAPACITY - 2

    def test_get_consumables(self):
        inv = Inventory()
        inv.add_item(Item(item_id="sword", name="Sword", item_type=ItemType.WEAPON))
        inv.add_item(Item(
            item_id="potion", name="Potion", item_type=ItemType.CONSUMABLE,
            consumable_effect=ConsumableEffect(type=ConsumableType.HEAL, magnitude=40),
        ))
        consumables = inv.get_consumables()
        assert len(consumables) == 1
        assert consumables[0].item_id == "potion"


# ============================================================
# 4. Items Config Loading Tests
# ============================================================

class TestItemsConfig:
    """Test items_config.json loading and parsing."""

    def test_config_file_exists(self):
        config_path = Path(__file__).resolve().parent.parent / "configs" / "items_config.json"
        assert config_path.exists(), "items_config.json not found"

    def test_config_loads_successfully(self):
        config = load_items_config()
        assert isinstance(config, dict)
        assert len(config) > 0

    def test_all_items_have_required_fields(self):
        config = load_items_config()
        required_fields = {"item_id", "name", "item_type"}
        for item_id, data in config.items():
            for field in required_fields:
                assert field in data, f"Item '{item_id}' missing field '{field}'"

    def test_all_items_create_valid_models(self):
        """Every item in config should produce a valid Item model via create_item()."""
        config = load_items_config()
        for item_id in config:
            item = create_item(item_id)
            assert item is not None, f"create_item('{item_id}') returned None"
            assert item.item_id == item_id

    def test_common_weapons_exist(self):
        config = load_items_config()
        common_weapons = [
            iid for iid, d in config.items()
            if d.get("item_type") == "weapon" and d.get("rarity") == "common"
        ]
        assert len(common_weapons) >= 2, "Expected at least 2 common weapons"

    def test_uncommon_weapons_exist(self):
        """Phase 16C: 'uncommon' migrated to 'magic'."""
        config = load_items_config()
        magic_weapons = [
            iid for iid, d in config.items()
            if d.get("item_type") == "weapon" and d.get("rarity") == "magic"
        ]
        assert len(magic_weapons) >= 2, "Expected at least 2 magic weapons"

    def test_common_armor_exists(self):
        config = load_items_config()
        common_armor = [
            iid for iid, d in config.items()
            if d.get("item_type") == "armor" and d.get("rarity") == "common"
        ]
        assert len(common_armor) >= 2, "Expected at least 2 common armor pieces"

    def test_uncommon_armor_exists(self):
        """Phase 16C: 'uncommon' migrated to 'magic'."""
        config = load_items_config()
        magic_armor = [
            iid for iid, d in config.items()
            if d.get("item_type") == "armor" and d.get("rarity") == "magic"
        ]
        assert len(magic_armor) >= 1, "Expected at least 1 magic armor piece"

    def test_accessories_exist(self):
        config = load_items_config()
        accessories = [
            iid for iid, d in config.items()
            if d.get("item_type") == "accessory"
        ]
        assert len(accessories) >= 2, "Expected at least 2 accessories"

    def test_health_potion_exists(self):
        item = create_item("health_potion")
        assert item is not None
        assert item.item_type == ItemType.CONSUMABLE
        assert item.consumable_effect is not None
        assert item.consumable_effect.type == ConsumableType.HEAL
        assert item.consumable_effect.magnitude > 0

    def test_greater_health_potion_exists(self):
        item = create_item("greater_health_potion")
        assert item is not None
        assert item.consumable_effect.type == ConsumableType.HEAL
        assert item.consumable_effect.magnitude > create_item("health_potion").consumable_effect.magnitude

    def test_portal_scroll_exists(self):
        item = create_item("portal_scroll")
        assert item is not None
        assert item.item_type == ItemType.CONSUMABLE
        assert item.consumable_effect.type == ConsumableType.PORTAL

    def test_weapon_stat_bonuses_in_range(self):
        """Weapons must have meaningful stats — either raw damage or hybrid stat budgets."""
        config = load_items_config()
        secondary_stats = {
            "crit_chance", "crit_damage", "skill_damage_pct", "armor_pen",
            "holy_damage_pct", "dot_damage_pct", "life_on_hit", "cooldown_reduction_pct",
        }
        for iid, data in config.items():
            if data.get("item_type") != "weapon":
                continue
            bonuses = data.get("stat_bonuses", {})
            total_dmg = bonuses.get("attack_damage", 0) + bonuses.get("ranged_damage", 0)
            has_secondary = any(bonuses.get(s, 0) > 0 for s in secondary_stats)
            if data.get("rarity") == "common":
                if has_secondary:
                    # Hybrid weapons trade raw damage for secondary stats
                    assert total_dmg >= 2, f"Common hybrid weapon '{iid}' has {total_dmg} total damage (too low even for hybrid)"
                else:
                    assert 5 <= total_dmg <= 10, f"Common weapon '{iid}' has {total_dmg} total damage"
            elif data.get("rarity") in ("uncommon", "magic"):
                if has_secondary:
                    assert total_dmg >= 3, f"Magic hybrid weapon '{iid}' has {total_dmg} total damage (too low even for hybrid)"
                else:
                    assert total_dmg >= 10, f"Magic weapon '{iid}' has {total_dmg} total damage"

    def test_armor_stat_bonuses_in_range(self):
        """Armor must have meaningful stats — either raw armor or hybrid stat budgets."""
        config = load_items_config()
        secondary_stats = {
            "dodge_chance", "skill_damage_pct", "thorns", "heal_power_pct",
            "damage_reduction_pct", "hp_regen", "max_hp",
        }
        for iid, data in config.items():
            if data.get("item_type") != "armor":
                continue
            bonuses = data.get("stat_bonuses", {})
            armor_val = bonuses.get("armor", 0)
            has_secondary = any(bonuses.get(s, 0) > 0 for s in secondary_stats)
            if data.get("rarity") == "common":
                if has_secondary:
                    assert armor_val >= 1, f"Common hybrid armor '{iid}' has {armor_val} armor (too low even for hybrid)"
                else:
                    assert 3 <= armor_val <= 6, f"Common armor '{iid}' has {armor_val} armor"
            elif data.get("rarity") in ("uncommon", "magic"):
                if has_secondary:
                    assert armor_val >= 2, f"Magic hybrid armor '{iid}' has {armor_val} armor (too low even for hybrid)"
                else:
                    assert armor_val >= 6, f"Magic armor '{iid}' has {armor_val} armor"

    def test_accessory_hp_bonuses_in_range(self):
        """Accessories must have meaningful stats — either raw HP or hybrid stat budgets."""
        config = load_items_config()
        secondary_stats = {
            "crit_chance", "crit_damage", "skill_damage_pct", "cooldown_reduction_pct",
            "damage_reduction_pct", "holy_damage_pct", "dot_damage_pct",
            "heal_power_pct", "gold_find_pct", "magic_find_pct", "life_on_hit",
            "armor",
        }
        for iid, data in config.items():
            if data.get("item_type") != "accessory":
                continue
            bonuses = data.get("stat_bonuses", {})
            hp_val = bonuses.get("max_hp", 0)
            has_secondary = any(bonuses.get(s, 0) > 0 for s in secondary_stats)
            if data.get("rarity") == "common":
                if has_secondary:
                    # Hybrid accessories trade HP for secondary stats
                    assert hp_val >= 0, f"Common hybrid accessory '{iid}' has negative max_hp"
                else:
                    assert 20 <= hp_val <= 30, f"Common accessory '{iid}' has {hp_val} max_hp"
            elif data.get("rarity") in ("uncommon", "magic"):
                if has_secondary:
                    assert hp_val >= 0, f"Magic hybrid accessory '{iid}' has negative max_hp"
                else:
                    assert hp_val >= 30, f"Magic accessory '{iid}' has {hp_val} max_hp"

    def test_get_all_item_ids(self):
        ids = get_all_item_ids()
        assert len(ids) >= 15, f"Expected at least 15 items, got {len(ids)}"

    def test_get_items_by_rarity(self):
        """Phase 16C: 'uncommon' migrated to 'magic'."""
        common = get_items_by_rarity("common")
        magic = get_items_by_rarity("magic")
        assert len(common) > 0
        assert len(magic) > 0
        # No overlap
        assert set(common).isdisjoint(set(magic))

    def test_all_items_have_sell_value(self):
        config = load_items_config()
        for iid, data in config.items():
            assert "sell_value" in data, f"Item '{iid}' missing sell_value"
            assert data["sell_value"] >= 0, f"Item '{iid}' has negative sell_value"


# ============================================================
# 5. Loot Tables Config Tests
# ============================================================

class TestLootTablesConfig:
    """Test loot_tables.json loading and cross-reference validation."""

    def test_config_file_exists(self):
        config_path = Path(__file__).resolve().parent.parent / "configs" / "loot_tables.json"
        assert config_path.exists(), "loot_tables.json not found"

    def test_config_loads_successfully(self):
        tables = load_loot_tables()
        assert "enemy_loot_tables" in tables
        assert "chest_loot_tables" in tables

    def test_enemy_tables_defined(self):
        tables = load_loot_tables()
        enemy_tables = tables["enemy_loot_tables"]
        assert "demon" in enemy_tables, "Missing loot table for demon"
        assert "skeleton" in enemy_tables, "Missing loot table for skeleton"
        assert "undead_knight" in enemy_tables, "Missing loot table for undead_knight"

    def test_chest_tables_defined(self):
        tables = load_loot_tables()
        chest_tables = tables["chest_loot_tables"]
        assert "default" in chest_tables, "Missing default chest loot table"

    def test_all_item_references_valid(self):
        """Every item_id referenced in loot tables must exist in items_config."""
        errors = validate_loot_tables()
        assert errors == [], f"Loot table validation errors:\n" + "\n".join(errors)

    def test_enemy_tables_have_required_fields(self):
        tables = load_loot_tables()
        for name, table in tables["enemy_loot_tables"].items():
            assert "drop_chance" in table, f"Enemy table '{name}' missing drop_chance"
            assert "pools" in table, f"Enemy table '{name}' missing pools"
            assert 0.0 <= table["drop_chance"] <= 1.0, f"Enemy table '{name}' invalid drop_chance"

    def test_chest_tables_have_required_fields(self):
        tables = load_loot_tables()
        for name, table in tables["chest_loot_tables"].items():
            assert "pools" in table, f"Chest table '{name}' missing pools"
            assert "min_items" in table, f"Chest table '{name}' missing min_items"
            assert "max_items" in table, f"Chest table '{name}' missing max_items"

    def test_boss_has_guaranteed_uncommon(self):
        """Phase 16C: guaranteed_rarity migrated from 'uncommon' to 'magic'."""
        tables = load_loot_tables()
        boss_table = tables["enemy_loot_tables"]["undead_knight"]
        assert boss_table.get("guaranteed_rarity") == "magic", \
            "Boss (undead_knight) should have guaranteed_rarity = magic"

    def test_boss_has_100_percent_drop(self):
        tables = load_loot_tables()
        boss_table = tables["enemy_loot_tables"]["undead_knight"]
        assert boss_table["drop_chance"] == 1.0, "Boss should have 100% drop chance"

    def test_pool_weights_positive(self):
        tables = load_loot_tables()
        for category in ("enemy_loot_tables", "chest_loot_tables"):
            for name, table in tables[category].items():
                for i, pool in enumerate(table.get("pools", [])):
                    assert pool.get("weight", 0) > 0, \
                        f"{category}.{name}.pools[{i}] has non-positive weight"

    def test_pool_items_non_empty(self):
        tables = load_loot_tables()
        for category in ("enemy_loot_tables", "chest_loot_tables"):
            for name, table in tables[category].items():
                for i, pool in enumerate(table.get("pools", [])):
                    assert len(pool.get("items", [])) > 0, \
                        f"{category}.{name}.pools[{i}] has empty items list"


# ============================================================
# 6. Loot Generation Tests
# ============================================================

class TestLootGeneration:
    """Test loot rolling functions."""

    def test_roll_enemy_loot_demon(self):
        """Demon loot should be empty or contain items (60% chance)."""
        # Use seed for determinism
        items = roll_enemy_loot("demon", seed=42)
        # With seed=42, result is deterministic
        assert isinstance(items, list)
        for item in items:
            assert isinstance(item, Item)

    def test_roll_enemy_loot_skeleton(self):
        items = roll_enemy_loot("skeleton", seed=42)
        assert isinstance(items, list)

    def test_roll_enemy_loot_boss_always_drops(self):
        """Boss should always drop loot (100% chance)."""
        for seed in range(50):
            items = roll_enemy_loot("undead_knight", seed=seed)
            assert len(items) >= 2, f"Boss dropped {len(items)} items with seed={seed}, expected >= 2"

    def test_roll_enemy_loot_boss_guarantees_uncommon(self):
        """Phase 16C: Boss should guarantee at least one magic item."""
        for seed in range(50):
            items = roll_enemy_loot("undead_knight", seed=seed)
            rarities = [item.rarity for item in items]
            assert Rarity.MAGIC in rarities, \
                f"Boss loot with seed={seed} had no magic: {[i.name for i in items]}"

    def test_roll_enemy_loot_unknown_type_returns_empty(self):
        items = roll_enemy_loot("nonexistent_enemy", seed=0)
        assert items == []

    def test_roll_chest_loot_default(self):
        items = roll_chest_loot("default", seed=42)
        assert isinstance(items, list)
        assert len(items) >= 1, "Default chest should drop at least 1 item"

    def test_roll_chest_loot_boss_chest(self):
        items = roll_chest_loot("boss_chest", seed=42)
        assert isinstance(items, list)
        assert len(items) >= 2, "Boss chest should drop at least 2 items"

    def test_roll_chest_loot_boss_chest_guarantees_uncommon(self):
        """Phase 16C: Boss chest should guarantee at least one magic item."""
        for seed in range(50):
            items = roll_chest_loot("boss_chest", seed=seed)
            rarities = [item.rarity for item in items]
            assert Rarity.MAGIC in rarities, \
                f"Boss chest with seed={seed} had no magic: {[i.name for i in items]}"

    def test_roll_chest_loot_unknown_type_returns_empty(self):
        items = roll_chest_loot("nonexistent_chest", seed=0)
        assert items == []

    def test_roll_loot_table_enemy_interface(self):
        items = roll_loot_table("demon", source_category="enemy", seed=42)
        assert isinstance(items, list)

    def test_roll_loot_table_chest_interface(self):
        items = roll_loot_table("default", source_category="chest", seed=42)
        assert isinstance(items, list)

    def test_roll_loot_table_invalid_category(self):
        items = roll_loot_table("demon", source_category="invalid", seed=42)
        assert items == []

    def test_deterministic_seeded_rolls(self):
        """Same seed should produce identical results."""
        items1 = roll_enemy_loot("demon", seed=12345)
        items2 = roll_enemy_loot("demon", seed=12345)
        assert len(items1) == len(items2)
        for a, b in zip(items1, items2):
            assert a.item_id == b.item_id

    def test_different_seeds_can_vary(self):
        """Different seeds should eventually produce different results."""
        results: set[tuple[str, ...]] = set()
        for seed in range(100):
            items = roll_enemy_loot("undead_knight", seed=seed)
            key = tuple(item.item_id for item in items)
            results.add(key)
        # Boss always drops 2-3 items, with multiple possible combinations
        assert len(results) > 1, "Expected some variety in loot rolls across 100 seeds"

    def test_demon_drop_chance_approximately_correct(self):
        """Over many rolls, demon (60% chance) should drop roughly 60% of the time."""
        drops = 0
        trials = 1000
        for seed in range(trials):
            items = roll_enemy_loot("demon", seed=seed)
            if len(items) > 0:
                drops += 1
        rate = drops / trials
        assert 0.45 <= rate <= 0.75, f"Demon drop rate was {rate:.2%}, expected ~60%"

    def test_skeleton_drop_chance_approximately_correct(self):
        """Over many rolls, skeleton (50% chance) should drop roughly 50% of the time."""
        drops = 0
        trials = 1000
        for seed in range(trials):
            items = roll_enemy_loot("skeleton", seed=seed)
            if len(items) > 0:
                drops += 1
        rate = drops / trials
        assert 0.35 <= rate <= 0.65, f"Skeleton drop rate was {rate:.2%}, expected ~50%"


# ============================================================
# 7. create_item() Factory Tests
# ============================================================

class TestCreateItem:
    """Test the create_item() factory function."""

    def test_create_known_item(self):
        item = create_item("common_sword")
        assert item is not None
        assert item.item_id == "common_sword"
        assert item.item_type == ItemType.WEAPON
        assert item.stat_bonuses.attack_damage > 0

    def test_create_consumable_item(self):
        item = create_item("health_potion")
        assert item is not None
        assert item.consumable_effect is not None
        assert item.consumable_effect.type == ConsumableType.HEAL

    def test_create_unknown_item_returns_none(self):
        item = create_item("nonexistent_item_xyz")
        assert item is None

    def test_create_all_config_items(self):
        """Every item_id in config should create a valid Item."""
        ids = get_all_item_ids()
        for item_id in ids:
            item = create_item(item_id)
            assert item is not None, f"create_item('{item_id}') failed"
            assert item.item_id == item_id


# ============================================================
# 8. PlayerState Backward Compatibility Tests
# ============================================================

class TestPlayerStateBackwardCompat:
    """Verify PlayerState works with new equipment/inventory fields."""

    def test_default_equipment_empty(self):
        ps = PlayerState(player_id="p1", username="test")
        assert ps.equipment == {}
        assert isinstance(ps.equipment, dict)

    def test_default_inventory_empty(self):
        ps = PlayerState(player_id="p1", username="test")
        assert ps.inventory == []
        assert isinstance(ps.inventory, list)

    def test_existing_fields_unchanged(self):
        ps = PlayerState(player_id="p1", username="test")
        assert ps.hp == 100
        assert ps.max_hp == 100
        assert ps.attack_damage == 15
        assert ps.ranged_damage == 10
        assert ps.armor == 2
        assert ps.vision_range == 7
        assert ps.ranged_range == 5
        assert ps.is_alive is True
        assert ps.unit_type == "human"
        assert ps.team == "a"
        assert ps.class_id is None
        assert ps.enemy_type is None

    def test_serialization_with_empty_equipment(self):
        ps = PlayerState(player_id="p1", username="test")
        data = ps.model_dump()
        assert "equipment" in data
        assert "inventory" in data
        restored = PlayerState(**data)
        assert restored.equipment == {}
        assert restored.inventory == []

    def test_serialization_with_populated_equipment(self):
        """Equipment/inventory stored as raw dicts should serialize/deserialize."""
        ps = PlayerState(player_id="p1", username="test")
        ps.equipment = {"weapon": {"item_id": "common_sword", "name": "Rusty Sword"}}
        ps.inventory = [{"item_id": "health_potion", "name": "Health Potion"}]
        data = ps.model_dump()
        restored = PlayerState(**data)
        assert restored.equipment["weapon"]["item_id"] == "common_sword"
        assert len(restored.inventory) == 1
        assert restored.inventory[0]["item_id"] == "health_potion"

    def test_legacy_player_state_no_equipment_field(self):
        """Simulates loading old data that doesn't have equipment/inventory fields."""
        legacy_data = {
            "player_id": "old_p1",
            "username": "legacy_user",
            "hp": 100,
            "max_hp": 100,
        }
        ps = PlayerState(**legacy_data)
        assert ps.equipment == {}
        assert ps.inventory == []


# ============================================================
# 9. Config Cross-Validation Tests
# ============================================================

class TestConfigCrossValidation:
    """Test that configs are internally consistent."""

    def test_loot_tables_reference_only_valid_items(self):
        errors = validate_loot_tables()
        assert errors == [], f"Cross-validation errors:\n" + "\n".join(errors)

    def test_all_enemy_types_have_loot_tables(self):
        """Every enemy in enemies_config.json should have a loot table."""
        enemies_path = Path(__file__).resolve().parent.parent / "configs" / "enemies_config.json"
        with open(enemies_path, "r") as f:
            enemies = json.load(f).get("enemies", {})

        tables = load_loot_tables()
        enemy_tables = tables.get("enemy_loot_tables", {})

        for enemy_id in enemies:
            assert enemy_id in enemy_tables, \
                f"Enemy '{enemy_id}' has no loot table in loot_tables.json"

    def test_item_types_match_equip_slots(self):
        """Weapons should have weapon slot, armor should have armor slot, etc."""
        config = load_items_config()
        type_to_slot = {
            "weapon": "weapon",
            "armor": "armor",
            "accessory": "accessory",
        }
        for iid, data in config.items():
            item_type = data.get("item_type")
            if item_type in type_to_slot:
                expected_slot = type_to_slot[item_type]
                assert data.get("equip_slot") == expected_slot, \
                    f"Item '{iid}' is type '{item_type}' but equip_slot='{data.get('equip_slot')}'"
            elif item_type == "consumable":
                assert data.get("equip_slot") is None, \
                    f"Consumable '{iid}' should have equip_slot=null"

    def test_consumables_have_effects(self):
        """All consumable items should have a consumable_effect defined."""
        config = load_items_config()
        for iid, data in config.items():
            if data.get("item_type") == "consumable":
                assert "consumable_effect" in data and data["consumable_effect"] is not None, \
                    f"Consumable '{iid}' missing consumable_effect"
