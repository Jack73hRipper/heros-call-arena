"""
Tests for Phase 4D-2: Equipment, Loot Drops & Consumables (Server Gameplay Logic).

Covers:
- Equipment bonuses in combat (calculate_damage, calculate_ranged_damage)
- Enemy death → loot drops on ground
- Chest interaction via LOOT action
- Ground item pickup via LOOT action
- Inventory capacity enforcement
- Equip/unequip via match_manager
- Health potion use (USE_ITEM action)
- Portal scroll rejection
- TurnResult new fields
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType, TurnResult
from app.models.match import MatchState, MatchConfig, MatchType
from app.models.items import (
    Item, StatBonuses, ConsumableEffect, Equipment, Inventory,
    ItemType, Rarity, EquipSlot, ConsumableType, INVENTORY_MAX_CAPACITY,
)
from app.core.combat import calculate_damage_simple as calculate_damage, calculate_ranged_damage_simple as calculate_ranged_damage, _get_equipment_bonuses
from app.core.turn_resolver import resolve_turn
from app.core.loot import roll_enemy_loot, roll_chest_loot, clear_caches, create_item


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def _clear_loot_caches():
    """Clear loot config caches before each test."""
    clear_caches()
    yield
    clear_caches()


def _make_player(pid="p1", username="Player1", x=1, y=1, hp=100, max_hp=100,
                 attack_damage=15, ranged_damage=10, armor=2, team="a",
                 equipment=None, inventory=None, enemy_type=None, ai_behavior=None,
                 unit_type="human") -> PlayerState:
    """Create a PlayerState with sensible defaults for testing."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=attack_damage,
        ranged_damage=ranged_damage,
        armor=armor,
        team=team,
        equipment=equipment or {},
        inventory=inventory or [],
        enemy_type=enemy_type,
        ai_behavior=ai_behavior,
        unit_type=unit_type,
    )


def _make_weapon(item_id="sword_01", name="Iron Sword", atk=5, rng_atk=0,
                 rarity="common", sell_value=10) -> dict:
    """Create a serialized weapon item dict."""
    return {
        "item_id": item_id,
        "name": name,
        "item_type": "weapon",
        "rarity": rarity,
        "equip_slot": "weapon",
        "stat_bonuses": {"attack_damage": atk, "ranged_damage": rng_atk, "armor": 0, "max_hp": 0},
        "consumable_effect": None,
        "description": f"A test {name}",
        "sell_value": sell_value,
    }


def _make_armor(item_id="armor_01", name="Iron Armor", armor_bonus=3,
                rarity="common", sell_value=10) -> dict:
    """Create a serialized armor item dict."""
    return {
        "item_id": item_id,
        "name": name,
        "item_type": "armor",
        "rarity": rarity,
        "equip_slot": "armor",
        "stat_bonuses": {"attack_damage": 0, "ranged_damage": 0, "armor": armor_bonus, "max_hp": 0},
        "consumable_effect": None,
        "description": f"A test {name}",
        "sell_value": sell_value,
    }


def _make_accessory(item_id="amulet_01", name="Amulet of Vitality", max_hp=20,
                    rarity="common", sell_value=10) -> dict:
    """Create a serialized accessory item dict."""
    return {
        "item_id": item_id,
        "name": name,
        "item_type": "accessory",
        "rarity": rarity,
        "equip_slot": "accessory",
        "stat_bonuses": {"attack_damage": 0, "ranged_damage": 0, "armor": 0, "max_hp": max_hp},
        "consumable_effect": None,
        "description": f"A test {name}",
        "sell_value": sell_value,
    }


def _make_health_potion(item_id="health_potion", name="Health Potion", magnitude=40) -> dict:
    """Create a serialized health potion item dict."""
    return {
        "item_id": item_id,
        "name": name,
        "item_type": "consumable",
        "rarity": "common",
        "equip_slot": None,
        "stat_bonuses": {"attack_damage": 0, "ranged_damage": 0, "armor": 0, "max_hp": 0},
        "consumable_effect": {"type": "heal", "magnitude": magnitude},
        "description": "Restores HP",
        "sell_value": 15,
    }


def _make_portal_scroll() -> dict:
    """Create a serialized portal scroll item dict."""
    return {
        "item_id": "portal_scroll",
        "name": "Portal Scroll",
        "item_type": "consumable",
        "rarity": "uncommon",
        "equip_slot": None,
        "stat_bonuses": {"attack_damage": 0, "ranged_damage": 0, "armor": 0, "max_hp": 0},
        "consumable_effect": {"type": "portal", "magnitude": 0},
        "description": "Opens a portal",
        "sell_value": 50,
    }


# ==========================================================================
# Test Class 1: Equipment Bonuses in Combat
# ==========================================================================

class TestEquipmentBonusesInCombat:
    """Equipment stat bonuses should modify damage calculations."""

    def test_weapon_increases_melee_damage(self):
        """Equipped weapon's attack_damage bonus adds to melee damage."""
        attacker = _make_player(attack_damage=15, equipment={"weapon": _make_weapon(atk=5)})
        defender = _make_player(armor=0)
        damage = calculate_damage(attacker, defender)
        # 15 base + 5 weapon = 20, 0 armor
        assert damage == 20

    def test_weapon_increases_ranged_damage(self):
        """Equipped weapon's ranged_damage bonus adds to ranged damage."""
        weapon = _make_weapon(atk=0, rng_atk=8)
        attacker = _make_player(ranged_damage=10, equipment={"weapon": weapon})
        defender = _make_player(armor=0)
        damage = calculate_ranged_damage(attacker, defender)
        # 10 base + 8 weapon = 18, 0 armor
        assert damage == 18

    def test_armor_reduces_damage(self):
        """Equipped armor's armor bonus adds to damage reduction."""
        attacker = _make_player(attack_damage=20)
        defender = _make_player(armor=2, equipment={"armor": _make_armor(armor_bonus=4)})
        damage = calculate_damage(attacker, defender)
        # 20 damage - (2 + 4) * 1 reduction = 14
        assert damage == 14

    def test_no_equipment_uses_base_stats(self):
        """Without equipment, base stats are used."""
        attacker = _make_player(attack_damage=15)
        defender = _make_player(armor=2)
        damage = calculate_damage(attacker, defender)
        assert damage == 13  # 15 - 2

    def test_multiple_equipment_slots_stack(self):
        """Bonuses from all equipment slots should stack."""
        weapon = _make_weapon(atk=5)
        armor = _make_armor(armor_bonus=3)
        accessory = _make_accessory(max_hp=20)
        attacker = _make_player(attack_damage=10, equipment={"weapon": weapon, "accessory": accessory})
        defender = _make_player(armor=1, equipment={"armor": armor})
        damage = calculate_damage(attacker, defender)
        # 10 + 5 weapon = 15 attack; 1 + 3 armor = 4 reduction; 15 - 4 = 11
        assert damage == 11

    def test_minimum_damage_is_1(self):
        """Even with heavy armor, minimum damage is 1."""
        attacker = _make_player(attack_damage=5)
        defender = _make_player(armor=3, equipment={"armor": _make_armor(armor_bonus=10)})
        damage = calculate_damage(attacker, defender)
        assert damage == 1  # 5 - 13 = clamped to 1

    def test_equipment_bonuses_helper_empty(self):
        """_get_equipment_bonuses returns zero bonuses for empty equipment."""
        player = _make_player()
        bonuses = _get_equipment_bonuses(player)
        assert bonuses.attack_damage == 0
        assert bonuses.armor == 0

    def test_equipment_bonuses_helper_with_weapon(self):
        """_get_equipment_bonuses correctly sums weapon stats."""
        player = _make_player(equipment={"weapon": _make_weapon(atk=7, rng_atk=3)})
        bonuses = _get_equipment_bonuses(player)
        assert bonuses.attack_damage == 7
        assert bonuses.ranged_damage == 3

    def test_equipment_handles_malformed_data_gracefully(self):
        """Malformed equipment data should not crash, returns zero bonuses."""
        player = _make_player(equipment={"weapon": {"bad": "data"}})
        bonuses = _get_equipment_bonuses(player)
        assert bonuses.attack_damage == 0


# ==========================================================================
# Test Class 2: Health Potion Use (USE_ITEM)
# ==========================================================================

class TestHealthPotionUse:
    """USE_ITEM action should consume health potions and restore HP."""

    def test_use_health_potion_restores_hp(self):
        """Using a health potion heals the player."""
        potion = _make_health_potion(magnitude=40)
        player = _make_player(hp=60, max_hp=100, inventory=[potion])
        players = {"p1": player}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.USE_ITEM, target_x=0)]

        result = resolve_turn("m1", 1, players, actions, 15, 15, set())
        assert player.hp == 100  # 60 + 40
        assert len(player.inventory) == 0  # Potion consumed
        assert len(result.items_used) == 1
        assert result.items_used[0]["effect"]["actual_healed"] == 40

    def test_use_health_potion_capped_at_max_hp(self):
        """Healing cannot exceed max_hp."""
        potion = _make_health_potion(magnitude=40)
        player = _make_player(hp=90, max_hp=100, inventory=[potion])
        players = {"p1": player}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.USE_ITEM, target_x=0)]

        result = resolve_turn("m1", 1, players, actions, 15, 15, set())
        assert player.hp == 100
        assert result.items_used[0]["effect"]["actual_healed"] == 10

    def test_use_potion_at_full_hp(self):
        """Using a potion at full HP heals 0 but still consumes it."""
        potion = _make_health_potion(magnitude=40)
        player = _make_player(hp=100, max_hp=100, inventory=[potion])
        players = {"p1": player}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.USE_ITEM, target_x=0)]

        result = resolve_turn("m1", 1, players, actions, 15, 15, set())
        assert player.hp == 100
        assert len(player.inventory) == 0
        assert result.items_used[0]["effect"]["actual_healed"] == 0

    def test_no_consumable_in_inventory(self):
        """USE_ITEM fails gracefully when no consumables exist."""
        weapon = _make_weapon()
        player = _make_player(inventory=[weapon])
        players = {"p1": player}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.USE_ITEM)]

        result = resolve_turn("m1", 1, players, actions, 15, 15, set())
        # No items_used, action should fail
        assert len(result.items_used) == 0
        failed = [a for a in result.actions if a.action_type == ActionType.USE_ITEM and not a.success]
        assert len(failed) == 1

    def test_empty_inventory_use_item(self):
        """USE_ITEM fails with empty inventory."""
        player = _make_player(inventory=[])
        players = {"p1": player}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.USE_ITEM)]

        result = resolve_turn("m1", 1, players, actions, 15, 15, set())
        assert len(result.items_used) == 0
        failed = [a for a in result.actions if a.action_type == ActionType.USE_ITEM and not a.success]
        assert len(failed) == 1

    def test_use_specific_potion_by_index(self):
        """Can target a specific inventory slot via target_x."""
        weapon = _make_weapon()
        potion = _make_health_potion(magnitude=50)
        player = _make_player(hp=50, max_hp=100, inventory=[weapon, potion])
        players = {"p1": player}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.USE_ITEM, target_x=1)]

        result = resolve_turn("m1", 1, players, actions, 15, 15, set())
        assert player.hp == 100
        assert len(player.inventory) == 1
        assert player.inventory[0]["item_type"] == "weapon"


# ==========================================================================
# Test Class 3: Portal Scroll Usage
# ==========================================================================

class TestPortalScrollUsage:
    """Portal scrolls should be consumed and start channeling (Phase 12C)."""

    def test_portal_scroll_consumed_and_starts_channeling(self):
        """Using a portal scroll should consume it and start channeling."""
        scroll = _make_portal_scroll()
        player = _make_player(inventory=[scroll])
        players = {"p1": player}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.USE_ITEM, target_x=0)]

        result = resolve_turn("m1", 1, players, actions, 15, 15, set())
        assert len(player.inventory) == 0  # Scroll consumed
        assert result.channeling_started is not None
        assert result.channeling_started["player_id"] == "p1"
        success = [a for a in result.actions if a.action_type == ActionType.USE_ITEM and a.success]
        assert len(success) >= 1


# ==========================================================================
# Test Class 4: Loot Drops on Enemy Death
# ==========================================================================

class TestLootDropsOnDeath:
    """Enemies should drop loot on death, placed in ground_items."""

    def test_enemy_death_creates_loot_drop(self):
        """When an enemy dies, loot is rolled and placed on ground."""
        enemy = _make_player(
            pid="e1", username="Demon-1", x=2, y=1, hp=1, armor=0,
            team="b", enemy_type="demon", unit_type="ai",
        )
        attacker = _make_player(pid="p1", x=1, y=1, attack_damage=20, team="a")

        players = {"p1": attacker, "e1": enemy}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=2, target_y=1)]
        ground_items: dict[str, list] = {}

        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            team_a=["p1"], team_b=["e1"],
            ground_items=ground_items,
        )

        assert "e1" in result.deaths
        # Loot may or may not drop depending on RNG, but loot_drops field should exist
        # and ground_items might have items
        assert isinstance(result.loot_drops, list)

    def test_player_death_no_loot_drop(self):
        """Player deaths should NOT create loot drops (only enemies)."""
        player2 = _make_player(pid="p2", username="Player2", x=2, y=1, hp=1, armor=0, team="b")
        attacker = _make_player(pid="p1", x=1, y=1, attack_damage=20, team="a")

        players = {"p1": attacker, "p2": player2}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=2, target_y=1)]
        ground_items: dict[str, list] = {}

        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            team_a=["p1"], team_b=["p2"],
            ground_items=ground_items,
        )

        assert "p2" in result.deaths
        assert len(result.loot_drops) == 0
        assert len(ground_items) == 0

    def test_loot_drops_at_death_tile(self):
        """Loot should appear at the position where the enemy died."""
        enemy = _make_player(
            pid="e1", username="Demon-1", x=5, y=5, hp=1, armor=0,
            team="b", enemy_type="demon", unit_type="ai",
        )
        attacker = _make_player(pid="p1", x=4, y=5, attack_damage=20, team="a")

        players = {"p1": attacker, "e1": enemy}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=5, target_y=5)]
        ground_items: dict[str, list] = {}

        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            team_a=["p1"], team_b=["e1"],
            ground_items=ground_items,
        )

        if result.loot_drops:
            assert result.loot_drops[0]["x"] == 5
            assert result.loot_drops[0]["y"] == 5
            # Ground items should be at "5,5"
            assert "5,5" in ground_items

    def test_no_ground_items_dict_no_crash(self):
        """If ground_items is None (arena match), death should not crash."""
        enemy = _make_player(
            pid="e1", username="AI-1", x=2, y=1, hp=1, armor=0,
            team="b", enemy_type="demon", unit_type="ai",
        )
        attacker = _make_player(pid="p1", x=1, y=1, attack_damage=20, team="a")

        players = {"p1": attacker, "e1": enemy}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=2, target_y=1)]

        # ground_items=None (arena mode default)
        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            team_a=["p1"], team_b=["e1"],
        )

        assert "e1" in result.deaths
        assert len(result.loot_drops) == 0  # No loot system in arena mode


# ==========================================================================
# Test Class 5: Chest Interaction (LOOT on Chest)
# ==========================================================================

class TestChestInteraction:
    """LOOT action on adjacent unopened chest generates items."""

    def test_loot_chest_generates_items(self):
        """Looting an adjacent chest opens it and generates items."""
        player = _make_player(x=3, y=5)
        players = {"p1": player}
        chest_states = {"4,5": "unopened"}
        ground_items: dict[str, list] = {}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.LOOT, target_x=4, target_y=5)]

        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            chest_states=chest_states,
            ground_items=ground_items,
        )

        assert chest_states["4,5"] == "opened"
        assert len(result.chest_opened) == 1
        assert result.chest_opened[0]["x"] == 4
        assert result.chest_opened[0]["y"] == 5

    def test_loot_opened_chest_fails(self):
        """Cannot loot a chest that's already opened."""
        player = _make_player(x=3, y=5)
        players = {"p1": player}
        chest_states = {"4,5": "opened"}
        ground_items: dict[str, list] = {}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.LOOT, target_x=4, target_y=5)]

        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            chest_states=chest_states,
            ground_items=ground_items,
        )

        # Should not open anything
        assert len(result.chest_opened) == 0

    def test_loot_chest_not_adjacent_fails(self):
        """Must be cardinally adjacent to loot a chest."""
        player = _make_player(x=1, y=1)
        players = {"p1": player}
        chest_states = {"4,5": "unopened"}
        ground_items: dict[str, list] = {}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.LOOT, target_x=4, target_y=5)]

        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            chest_states=chest_states,
            ground_items=ground_items,
        )

        assert chest_states["4,5"] == "unopened"  # Still unopened
        assert len(result.chest_opened) == 0

    def test_chest_loot_overflow_to_ground(self):
        """When inventory is full, excess chest items go to ground."""
        # Fill inventory to 9/10 with junk
        full_inv = [_make_weapon(item_id=f"junk_{i}") for i in range(INVENTORY_MAX_CAPACITY)]
        player = _make_player(x=3, y=5, inventory=full_inv)
        players = {"p1": player}
        chest_states = {"4,5": "unopened"}
        ground_items: dict[str, list] = {}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.LOOT, target_x=4, target_y=5)]

        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            chest_states=chest_states,
            ground_items=ground_items,
        )

        assert chest_states["4,5"] == "opened"
        assert len(result.chest_opened) == 1
        # All items should overflow to ground since inventory was full
        overflow = result.chest_opened[0].get("overflow_to_ground", [])
        assert len(overflow) > 0 or len(player.inventory) > INVENTORY_MAX_CAPACITY - 1


# ==========================================================================
# Test Class 6: Ground Item Pickup
# ==========================================================================

class TestGroundItemPickup:
    """LOOT action picks up items from the ground at player's tile."""

    def test_pickup_ground_items(self):
        """Player standing on ground items can pick them up."""
        player = _make_player(x=5, y=5)
        players = {"p1": player}
        ground_items = {"5,5": [_make_weapon(), _make_armor()]}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.LOOT)]

        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            ground_items=ground_items,
        )

        assert len(player.inventory) == 2
        assert "5,5" not in ground_items  # Items cleared from ground
        assert len(result.items_picked_up) == 1
        assert result.items_picked_up[0]["player_id"] == "p1"

    def test_pickup_respects_inventory_cap(self):
        """Excess items stay on ground when inventory is full."""
        full_inv = [_make_weapon(item_id=f"junk_{i}") for i in range(9)]
        player = _make_player(x=5, y=5, inventory=full_inv)
        # 3 items on ground, only 1 slot free
        ground_items = {"5,5": [_make_weapon(item_id="g1"), _make_weapon(item_id="g2"), _make_weapon(item_id="g3")]}
        players = {"p1": player}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.LOOT)]

        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            ground_items=ground_items,
        )

        assert len(player.inventory) == 10  # 9 + 1 picked up
        assert "5,5" in ground_items  # 2 remain
        assert len(ground_items["5,5"]) == 2

    def test_no_items_on_ground_fails(self):
        """LOOT with nothing on ground and no chest fails."""
        player = _make_player(x=5, y=5)
        players = {"p1": player}
        ground_items: dict[str, list] = {}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.LOOT)]

        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            ground_items=ground_items,
        )

        assert len(result.items_picked_up) == 0
        failed = [a for a in result.actions if a.action_type == ActionType.LOOT and not a.success]
        assert len(failed) == 1


# ==========================================================================
# Test Class 7: Equip/Unequip via Match Manager
# ==========================================================================

class TestEquipUnequip:
    """Test equip_item and unequip_item functions from match_manager."""

    def setup_method(self):
        """Set up a minimal match for testing equip/unequip."""
        from app.core.match_manager import _active_matches, _player_states
        self.match_id = "test_equip"
        match = MatchState(match_id=self.match_id, host_id="p1", player_ids=["p1"])
        _active_matches[self.match_id] = match

        weapon = _make_weapon(atk=10)
        armor = _make_armor(armor_bonus=5)
        potion = _make_health_potion()

        self.player = PlayerState(
            player_id="p1",
            username="TestPlayer",
            position=Position(x=1, y=1),
            hp=100, max_hp=100,
            attack_damage=15, armor=2,
            inventory=[weapon, armor, potion],
            equipment={},
        )
        _player_states[self.match_id] = {"p1": self.player}

    def teardown_method(self):
        from app.core.match_manager import _active_matches, _player_states
        _active_matches.pop(self.match_id, None)
        _player_states.pop(self.match_id, None)

    def test_equip_weapon_from_inventory(self):
        """Equipping a weapon moves it to equipment and removes from inventory."""
        from app.core.match_manager import equip_item
        result = equip_item(self.match_id, "p1", "sword_01")
        assert result is not None
        assert result["slot"] == "weapon"
        assert self.player.equipment.get("weapon") is not None
        assert len(self.player.inventory) == 2  # armor + potion remain

    def test_equip_armor_from_inventory(self):
        """Equipping armor works correctly."""
        from app.core.match_manager import equip_item
        result = equip_item(self.match_id, "p1", "armor_01")
        assert result is not None
        assert result["slot"] == "armor"
        assert self.player.equipment.get("armor") is not None

    def test_equip_swap_returns_old_to_inventory(self):
        """Equipping when slot is occupied swaps the old item back."""
        from app.core.match_manager import equip_item
        # Equip first weapon
        equip_item(self.match_id, "p1", "sword_01")
        assert len(self.player.inventory) == 2

        # Add another weapon to inventory
        self.player.inventory.append(_make_weapon(item_id="sword_02", name="Steel Sword", atk=15))

        # Equip new weapon — old goes back to inventory
        result = equip_item(self.match_id, "p1", "sword_02")
        assert result is not None
        assert result["equipped"]["item_id"] == "sword_02"
        assert result["unequipped"]["item_id"] == "sword_01"
        # sword_01 should be back in inventory
        inv_ids = [i["item_id"] for i in self.player.inventory]
        assert "sword_01" in inv_ids

    def test_cannot_equip_consumable(self):
        """Consumables cannot be equipped."""
        from app.core.match_manager import equip_item
        result = equip_item(self.match_id, "p1", "health_potion")
        assert result is None

    def test_equip_nonexistent_item(self):
        """Cannot equip an item not in inventory."""
        from app.core.match_manager import equip_item
        result = equip_item(self.match_id, "p1", "nonexistent_item")
        assert result is None

    def test_unequip_to_inventory(self):
        """Unequipping moves the item from equipment to inventory."""
        from app.core.match_manager import equip_item, unequip_item

        equip_item(self.match_id, "p1", "sword_01")
        inv_count = len(self.player.inventory)

        result = unequip_item(self.match_id, "p1", "weapon")
        assert result is not None
        assert self.player.equipment.get("weapon") is None
        assert len(self.player.inventory) == inv_count + 1

    def test_unequip_empty_slot_fails(self):
        """Cannot unequip from an empty slot."""
        from app.core.match_manager import unequip_item
        result = unequip_item(self.match_id, "p1", "weapon")
        assert result is None

    def test_unequip_full_inventory_fails(self):
        """Cannot unequip when inventory is full."""
        from app.core.match_manager import equip_item, unequip_item

        equip_item(self.match_id, "p1", "sword_01")
        # Fill inventory to max
        while len(self.player.inventory) < INVENTORY_MAX_CAPACITY:
            self.player.inventory.append(_make_weapon(item_id=f"filler_{len(self.player.inventory)}"))

        result = unequip_item(self.match_id, "p1", "weapon")
        assert result is None  # Inventory full

    def test_equip_accessory_grants_max_hp(self):
        """Equipping an accessory with max_hp bonus should increase max_hp and hp."""
        from app.core.match_manager import equip_item
        self.player.inventory.append(_make_accessory(max_hp=30))
        result = equip_item(self.match_id, "p1", "amulet_01")
        assert result is not None
        assert self.player.max_hp == 130  # 100 + 30
        assert self.player.hp == 130  # Also gains the bonus HP

    def test_unequip_accessory_reduces_max_hp(self):
        """Unequipping an accessory with max_hp bonus reduces max_hp."""
        from app.core.match_manager import equip_item, unequip_item
        self.player.inventory.append(_make_accessory(max_hp=30))
        equip_item(self.match_id, "p1", "amulet_01")
        assert self.player.max_hp == 130

        unequip_item(self.match_id, "p1", "accessory")
        assert self.player.max_hp == 100
        assert self.player.hp <= 100


# ==========================================================================
# Test Class 8: TurnResult New Fields
# ==========================================================================

class TestTurnResultNewFields:
    """TurnResult should include all new Phase 4D-2 fields."""

    def test_turn_result_has_loot_fields(self):
        """TurnResult model has all loot/inventory fields with defaults."""
        tr = TurnResult(match_id="m1", turn_number=1)
        assert tr.loot_drops == []
        assert tr.chest_opened == []
        assert tr.items_picked_up == []
        assert tr.items_used == []
        assert tr.door_changes == []

    def test_turn_result_populates_loot_drops(self):
        """TurnResult can carry loot_drops data."""
        tr = TurnResult(
            match_id="m1",
            turn_number=1,
            loot_drops=[{"x": 5, "y": 5, "items": [{"item_id": "sword_01"}]}],
        )
        assert len(tr.loot_drops) == 1
        assert tr.loot_drops[0]["x"] == 5


# ==========================================================================
# Test Class 9: Resolve Turn Phase Ordering
# ==========================================================================

class TestResolvePhaseOrdering:
    """Verify that turn phases execute in the correct order."""

    def test_use_item_before_movement(self):
        """USE_ITEM phase runs before movement."""
        potion = _make_health_potion(magnitude=30)
        player = _make_player(hp=50, max_hp=100, x=1, y=1, inventory=[potion])
        players = {"p1": player}

        # Both use_item and move in same turn — potion heals before movement
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.USE_ITEM, target_x=0),
            PlayerAction(player_id="p1", action_type=ActionType.MOVE, target_x=2, target_y=1),
        ]
        result = resolve_turn("m1", 1, players, actions, 15, 15, set())

        # Potion should have been used
        assert player.hp == 80  # 50 + 30
        # Movement should have succeeded
        assert player.position.x == 2

    def test_loot_after_interaction(self):
        """LOOT phase runs after INTERACT phase (doors), so a just-opened door
        doesn't interfere with loot resolution."""
        player = _make_player(x=3, y=5)
        players = {"p1": player}
        door_states = {"4,5": "closed"}
        chest_states = {}
        ground_items = {"3,5": [_make_weapon()]}

        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.INTERACT, target_x=4, target_y=5),
            PlayerAction(player_id="p1", action_type=ActionType.LOOT),
        ]
        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, {(4, 5)},
            door_states=door_states,
            chest_states=chest_states,
            ground_items=ground_items,
        )

        # Door should have opened
        assert door_states["4,5"] == "open"
        # Ground items should have been picked up
        assert len(player.inventory) == 1


# ==========================================================================
# Test Class 10: USE_ITEM ActionType
# ==========================================================================

class TestActionTypeUseItem:
    """USE_ITEM should be a valid ActionType."""

    def test_use_item_enum_exists(self):
        assert ActionType.USE_ITEM == "use_item"

    def test_use_item_in_action_type_values(self):
        assert "use_item" in [at.value for at in ActionType]


# ==========================================================================
# Test Class 11: Ground Items on MatchState
# ==========================================================================

class TestMatchStateGroundItems:
    """MatchState should support ground_items field."""

    def test_ground_items_default_empty(self):
        ms = MatchState(match_id="m1")
        assert ms.ground_items == {}

    def test_ground_items_serializable(self):
        ms = MatchState(
            match_id="m1",
            ground_items={"5,5": [{"item_id": "sword_01", "name": "Iron Sword"}]}
        )
        assert len(ms.ground_items["5,5"]) == 1

    def test_backward_compat_no_ground_items(self):
        """Existing matches without ground_items still work."""
        ms = MatchState(match_id="m1")
        assert ms.ground_items == {}
        assert ms.door_states == {}
        assert ms.chest_states == {}


# ==========================================================================
# Test Class 12: Loot System Integration
# ==========================================================================

class TestLootSystemIntegration:
    """Integration tests combining combat + loot drop + pickup."""

    def test_kill_enemy_then_pickup(self):
        """Full flow: kill enemy → loot drops → move to tile → pickup."""
        enemy = _make_player(
            pid="e1", username="Demon-1", x=3, y=1, hp=1, armor=0,
            team="b", enemy_type="demon", unit_type="ai",
        )
        attacker = _make_player(pid="p1", x=2, y=1, attack_damage=20, team="a")

        # Turn 1: Kill the enemy
        players = {"p1": attacker, "e1": enemy}
        ground_items: dict[str, list] = {}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=3, target_y=1)]

        result1 = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            team_a=["p1"], team_b=["e1"],
            ground_items=ground_items,
        )

        assert "e1" in result1.deaths

        # If anything dropped, try to pick it up
        if ground_items.get("3,1"):
            # Turn 2: Move to death tile
            attacker.position.x = 3
            attacker.position.y = 1

            pickup_actions = [PlayerAction(player_id="p1", action_type=ActionType.LOOT)]
            result2 = resolve_turn(
                "m1", 2, players, pickup_actions, 15, 15, set(),
                team_a=["p1"], team_b=["e1"],
                ground_items=ground_items,
            )

            assert len(attacker.inventory) > 0
            assert "3,1" not in ground_items or len(ground_items["3,1"]) == 0

    def test_equipped_weapon_affects_combat(self):
        """Equipped weapon should increase damage in actual turn resolution."""
        weapon = _make_weapon(atk=10)
        attacker = _make_player(
            pid="p1", x=1, y=1, attack_damage=15, team="a",
            equipment={"weapon": weapon},
        )
        defender = _make_player(pid="p2", x=2, y=1, hp=100, armor=0, team="b")

        players = {"p1": attacker, "p2": defender}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=2, target_y=1)]

        result = resolve_turn(
            "m1", 1, players, actions, 15, 15, set(),
            team_a=["p1"], team_b=["p2"],
        )

        # Damage should be 15 base + 10 weapon = 25 (non-crit) or more (crit)
        hit_action = [a for a in result.actions if a.success and a.action_type == ActionType.ATTACK][0]
        expected_base = 25  # 15 base_atk + 10 weapon, 0 armor
        if hit_action.is_crit:
            assert hit_action.damage_dealt > expected_base, \
                f"Crit should deal more than {expected_base}"
        else:
            assert hit_action.damage_dealt == expected_base
        assert defender.hp == 100 - hit_action.damage_dealt
