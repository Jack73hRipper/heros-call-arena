"""
Tests for in-match dungeon inventory management.

Covers:
- transfer_item_in_match: basic transfer between party members
- transfer_item_in_match: transfer from player to party member
- transfer_item_in_match: transfer from party member to player
- transfer_item_in_match: rejected when destination full
- transfer_item_in_match: rejected for invalid item index
- transfer_item_in_match: rejected for non-party member
- transfer_item_in_match: rejected for dead units
- transfer_item_in_match: rejected for same unit
- get_party_member_inventory: returns inventory for party member
- get_party_member_inventory: returns inventory for self
- get_party_member_inventory: rejected for non-party member
- Party member selected includes inventory data
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.match import MatchState, MatchStatus
from app.models.items import INVENTORY_MAX_CAPACITY
from app.core.match_manager import (
    transfer_item_in_match,
    get_party_member_inventory,
    is_party_member,
    set_party_control,
    get_party_members,
    _active_matches,
    _player_states,
    _hero_ally_map,
)


# ---------- Item Fixtures ----------

def _make_weapon(item_id="sword_01", name="Rusty Sword", atk=5):
    return {
        "item_id": item_id,
        "name": name,
        "item_type": "weapon",
        "rarity": "common",
        "equip_slot": "weapon",
        "stat_bonuses": {"attack_damage": atk, "ranged_damage": 0, "armor": 0, "max_hp": 0},
        "description": "A test weapon.",
        "sell_value": 10,
    }


def _make_armor(item_id="armor_01", name="Leather Armor", armor_bonus=3):
    return {
        "item_id": item_id,
        "name": name,
        "item_type": "armor",
        "rarity": "common",
        "equip_slot": "armor",
        "stat_bonuses": {"attack_damage": 0, "ranged_damage": 0, "armor": armor_bonus, "max_hp": 0},
        "description": "A test armor.",
        "sell_value": 8,
    }


def _make_potion(item_id="potion_01", name="Health Potion"):
    return {
        "item_id": item_id,
        "name": name,
        "item_type": "consumable",
        "rarity": "common",
        "equip_slot": None,
        "stat_bonuses": {},
        "consumable_effect": {"type": "heal", "magnitude": 30},
        "description": "Restores HP.",
        "sell_value": 5,
    }


# ==========================================================================
# Test Class: In-Match Item Transfer
# ==========================================================================

class TestTransferItemInMatch:
    """Test transfer_item_in_match from match_manager."""

    def setup_method(self):
        """Set up a match with a player and a hero ally."""
        self.match_id = "test_transfer_match"
        match = MatchState(
            match_id=self.match_id,
            host_id="player1",
            player_ids=["player1", "hero_ally_1"],
        )
        match.status = MatchStatus.IN_PROGRESS
        _active_matches[self.match_id] = match

        # Player (human)
        self.player = PlayerState(
            player_id="player1",
            username="Hero",
            position=Position(x=1, y=1),
            hp=100, max_hp=100,
            attack_damage=15, armor=2,
            team="a",
            unit_type="human",
            inventory=[_make_weapon(), _make_potion()],
            equipment={},
        )

        # Hero ally (AI, same team, controllable)
        self.ally = PlayerState(
            player_id="hero_ally_1",
            username="Ally",
            position=Position(x=2, y=1),
            hp=80, max_hp=80,
            attack_damage=12, armor=1,
            team="a",
            unit_type="ai",
            inventory=[_make_armor()],
            equipment={},
        )

        # Enemy (different team, not controllable)
        self.enemy = PlayerState(
            player_id="enemy_1",
            username="Goblin",
            position=Position(x=5, y=5),
            hp=50, max_hp=50,
            attack_damage=8, armor=0,
            team="b",
            unit_type="ai",
            enemy_type="demon",
            inventory=[_make_weapon(item_id="enemy_sword")],
            equipment={},
        )

        _player_states[self.match_id] = {
            "player1": self.player,
            "hero_ally_1": self.ally,
            "enemy_1": self.enemy,
        }

        # Register ally ownership
        _hero_ally_map[self.match_id] = {"hero_ally_1": "Hero"}

    def teardown_method(self):
        _active_matches.pop(self.match_id, None)
        _player_states.pop(self.match_id, None)
        _hero_ally_map.pop(self.match_id, None)

    def test_transfer_player_to_ally(self):
        """Transfer an item from player to party member."""
        result = transfer_item_in_match(
            self.match_id, "player1", "player1", "hero_ally_1", 0
        )
        assert result is not None
        assert result["from_unit_id"] == "player1"
        assert result["to_unit_id"] == "hero_ally_1"
        assert result["item"]["item_id"] == "sword_01"
        # Player lost the sword, ally gained it
        assert len(self.player.inventory) == 1  # only potion left
        assert len(self.ally.inventory) == 2    # armor + sword
        assert self.ally.inventory[-1]["item_id"] == "sword_01"

    def test_transfer_ally_to_player(self):
        """Transfer an item from party member to player."""
        result = transfer_item_in_match(
            self.match_id, "player1", "hero_ally_1", "player1", 0
        )
        assert result is not None
        assert result["from_unit_id"] == "hero_ally_1"
        assert result["to_unit_id"] == "player1"
        assert result["item"]["item_id"] == "armor_01"
        assert len(self.ally.inventory) == 0
        assert len(self.player.inventory) == 3  # sword + potion + armor

    def test_transfer_ally_to_ally(self):
        """Transfer between two party members (need a second ally)."""
        ally2 = PlayerState(
            player_id="hero_ally_2",
            username="Ally2",
            position=Position(x=3, y=1),
            hp=70, max_hp=70,
            attack_damage=10, armor=1,
            team="a",
            unit_type="ai",
            inventory=[],
            equipment={},
        )
        _player_states[self.match_id]["hero_ally_2"] = ally2
        _hero_ally_map[self.match_id]["hero_ally_2"] = "Hero"

        result = transfer_item_in_match(
            self.match_id, "player1", "hero_ally_1", "hero_ally_2", 0
        )
        assert result is not None
        assert len(self.ally.inventory) == 0
        assert len(ally2.inventory) == 1
        assert ally2.inventory[0]["item_id"] == "armor_01"

    def test_transfer_rejected_destination_full(self):
        """Transfer rejected when destination inventory is full."""
        # Fill ally inventory to max
        for i in range(INVENTORY_MAX_CAPACITY - 1):
            self.ally.inventory.append(_make_potion(item_id=f"potion_{i}"))
        assert len(self.ally.inventory) == INVENTORY_MAX_CAPACITY

        result = transfer_item_in_match(
            self.match_id, "player1", "player1", "hero_ally_1", 0
        )
        assert result is None
        # Nothing changed
        assert len(self.player.inventory) == 2

    def test_transfer_rejected_invalid_index(self):
        """Transfer rejected for out-of-range item index."""
        result = transfer_item_in_match(
            self.match_id, "player1", "player1", "hero_ally_1", 99
        )
        assert result is None

        result = transfer_item_in_match(
            self.match_id, "player1", "player1", "hero_ally_1", -1
        )
        assert result is None

    def test_transfer_rejected_non_party_member(self):
        """Transfer rejected when target is not a party member (enemy)."""
        result = transfer_item_in_match(
            self.match_id, "player1", "player1", "enemy_1", 0
        )
        assert result is None
        assert len(self.player.inventory) == 2  # unchanged

    def test_transfer_rejected_dead_source(self):
        """Transfer rejected when source unit is dead."""
        self.player.is_alive = False
        result = transfer_item_in_match(
            self.match_id, "player1", "player1", "hero_ally_1", 0
        )
        assert result is None

    def test_transfer_rejected_dead_destination(self):
        """Transfer rejected when destination unit is dead."""
        self.ally.is_alive = False
        result = transfer_item_in_match(
            self.match_id, "player1", "player1", "hero_ally_1", 0
        )
        assert result is None

    def test_transfer_rejected_same_unit(self):
        """Transfer rejected when source and destination are the same."""
        result = transfer_item_in_match(
            self.match_id, "player1", "player1", "player1", 0
        )
        assert result is None

    def test_transfer_returns_inventories(self):
        """Transfer result includes updated inventories for both units."""
        result = transfer_item_in_match(
            self.match_id, "player1", "player1", "hero_ally_1", 0
        )
        assert result is not None
        assert "from_inventory" in result
        assert "to_inventory" in result
        assert "from_equipment" in result
        assert "to_equipment" in result
        assert len(result["from_inventory"]) == 1
        assert len(result["to_inventory"]) == 2

    def test_transfer_nonexistent_match(self):
        """Transfer rejected for nonexistent match."""
        result = transfer_item_in_match(
            "no_such_match", "player1", "player1", "hero_ally_1", 0
        )
        assert result is None

    def test_transfer_nonexistent_unit(self):
        """Transfer rejected for nonexistent unit IDs."""
        result = transfer_item_in_match(
            self.match_id, "player1", "player1", "no_such_unit", 0
        )
        assert result is None
        result = transfer_item_in_match(
            self.match_id, "player1", "no_such_unit", "hero_ally_1", 0
        )
        assert result is None


# ==========================================================================
# Test Class: Get Party Member Inventory
# ==========================================================================

class TestGetPartyMemberInventory:
    """Test get_party_member_inventory from match_manager."""

    def setup_method(self):
        self.match_id = "test_party_inv"
        match = MatchState(
            match_id=self.match_id,
            host_id="player1",
            player_ids=["player1", "hero_ally_1"],
        )
        match.status = MatchStatus.IN_PROGRESS
        _active_matches[self.match_id] = match

        self.player = PlayerState(
            player_id="player1",
            username="Hero",
            position=Position(x=1, y=1),
            hp=100, max_hp=100,
            team="a",
            unit_type="human",
            inventory=[_make_weapon()],
            equipment={"weapon": _make_armor()},
        )
        self.ally = PlayerState(
            player_id="hero_ally_1",
            username="Ally",
            position=Position(x=2, y=1),
            hp=80, max_hp=80,
            team="a",
            unit_type="ai",
            inventory=[_make_potion()],
            equipment={},
        )
        self.enemy = PlayerState(
            player_id="enemy_1",
            username="Goblin",
            position=Position(x=5, y=5),
            hp=50, max_hp=50,
            team="b",
            unit_type="ai",
            enemy_type="demon",
            inventory=[],
            equipment={},
        )
        _player_states[self.match_id] = {
            "player1": self.player,
            "hero_ally_1": self.ally,
            "enemy_1": self.enemy,
        }
        _hero_ally_map[self.match_id] = {"hero_ally_1": "Hero"}

    def teardown_method(self):
        _active_matches.pop(self.match_id, None)
        _player_states.pop(self.match_id, None)
        _hero_ally_map.pop(self.match_id, None)

    def test_get_own_inventory(self):
        """Player can get their own inventory."""
        result = get_party_member_inventory(self.match_id, "player1", "player1")
        assert result is not None
        assert result["unit_id"] == "player1"
        assert len(result["inventory"]) == 1
        assert result["inventory"][0]["item_id"] == "sword_01"

    def test_get_ally_inventory(self):
        """Player can get their party member's inventory."""
        result = get_party_member_inventory(self.match_id, "player1", "hero_ally_1")
        assert result is not None
        assert result["unit_id"] == "hero_ally_1"
        assert len(result["inventory"]) == 1
        assert result["inventory"][0]["item_id"] == "potion_01"

    def test_get_enemy_inventory_rejected(self):
        """Player cannot get enemy's inventory."""
        result = get_party_member_inventory(self.match_id, "player1", "enemy_1")
        assert result is None

    def test_get_nonexistent_unit_rejected(self):
        """Getting inventory for nonexistent unit returns None."""
        result = get_party_member_inventory(self.match_id, "player1", "no_such_unit")
        assert result is None

    def test_inventory_result_includes_equipment(self):
        """Inventory result includes equipment dict."""
        result = get_party_member_inventory(self.match_id, "player1", "player1")
        assert "equipment" in result
        assert result["equipment"].get("weapon") is not None
