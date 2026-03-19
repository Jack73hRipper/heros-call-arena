"""
Tests for Phase 28D — AI Auto-Equip.

Covers:
  - _ROLE_STAT_WEIGHTS constants are defined for all 4 roles
  - score_item_for_role: aggressive prefers damage, support prefers defense
  - score_item_for_role: returns 0.0 for consumables, None, and empty items
  - try_auto_equip: upgrades empty slot, upgrades from common to rare
  - try_auto_equip: does not downgrade from epic to common
  - try_auto_equip: skips consumables (potions not equipped)
  - try_auto_equip: only triggers for AI units (human players unaffected)
  - Integration: passive pickup triggers auto-equip for AI
  - Combat log message generated on AI equip
"""

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType, ActionResult
from app.models.items import INVENTORY_MAX_CAPACITY
from app.core.match_manager import (
    _player_states,
    equip_item,
)
from app.core.equipment_manager import (
    _ROLE_STAT_WEIGHTS,
    score_item_for_role,
    try_auto_equip,
)
from app.core.turn_phases.interaction_phase import _resolve_loot
from app.core.combat import load_combat_config


MATCH_ID = "test_match_28d"


def setup_module():
    load_combat_config()


def teardown_function():
    """Clean up _player_states after each test."""
    _player_states.pop(MATCH_ID, None)


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

def _make_weapon(name="Iron Sword", atk=10, rarity="common") -> dict:
    """Create a weapon item dict for testing."""
    return {
        "item_id": f"{name.lower().replace(' ', '_')}",
        "instance_id": f"inst_{name.lower().replace(' ', '_')}_{rarity}",
        "name": name,
        "item_type": "weapon",
        "rarity": rarity,
        "equip_slot": "weapon",
        "stat_bonuses": {
            "attack_damage": atk,
            "ranged_damage": 0,
            "armor": 0,
            "max_hp": 0,
            "crit_chance": 0.0,
            "crit_damage": 0.0,
            "dodge_chance": 0.0,
            "damage_reduction_pct": 0.0,
        },
        "sell_value": 10,
        "weapon_category": "melee",
    }


def _make_ranged_weapon(name="Short Bow", rdmg=10, rarity="common") -> dict:
    """Create a ranged weapon item dict for testing."""
    return {
        "item_id": f"{name.lower().replace(' ', '_')}",
        "instance_id": f"inst_{name.lower().replace(' ', '_')}_{rarity}",
        "name": name,
        "item_type": "weapon",
        "rarity": rarity,
        "equip_slot": "weapon",
        "stat_bonuses": {
            "attack_damage": 0,
            "ranged_damage": rdmg,
            "armor": 0,
            "max_hp": 0,
            "crit_chance": 0.0,
            "crit_damage": 0.0,
            "dodge_chance": 0.0,
            "damage_reduction_pct": 0.0,
        },
        "sell_value": 10,
        "weapon_category": "ranged",
    }


def _make_armor(name="Iron Plate", armor_val=10, max_hp=0, rarity="common") -> dict:
    """Create an armor item dict for testing."""
    return {
        "item_id": f"{name.lower().replace(' ', '_')}",
        "instance_id": f"inst_{name.lower().replace(' ', '_')}_{rarity}",
        "name": name,
        "item_type": "armor",
        "rarity": rarity,
        "equip_slot": "armor",
        "stat_bonuses": {
            "attack_damage": 0,
            "ranged_damage": 0,
            "armor": armor_val,
            "max_hp": max_hp,
            "crit_chance": 0.0,
            "crit_damage": 0.0,
            "dodge_chance": 0.0,
            "damage_reduction_pct": 0.0,
        },
        "sell_value": 10,
        "armor_category": "heavy",
    }


def _make_support_armor(name="Mystic Robes", armor_val=5, max_hp=20,
                        cdr=0.05, rarity="common") -> dict:
    """Create a support-oriented armor item dict for testing."""
    return {
        "item_id": f"{name.lower().replace(' ', '_')}",
        "instance_id": f"inst_{name.lower().replace(' ', '_')}_{rarity}",
        "name": name,
        "item_type": "armor",
        "rarity": rarity,
        "equip_slot": "armor",
        "stat_bonuses": {
            "attack_damage": 0,
            "ranged_damage": 0,
            "armor": armor_val,
            "max_hp": max_hp,
            "crit_chance": 0.0,
            "crit_damage": 0.0,
            "dodge_chance": 0.0,
            "damage_reduction_pct": 0.0,
            "cooldown_reduction_pct": cdr,
        },
        "sell_value": 10,
        "armor_category": "cloth",
    }


def _make_potion() -> dict:
    """Create a health potion dict."""
    return {
        "item_id": "health_potion",
        "name": "Health Potion",
        "item_type": "consumable",
        "rarity": "common",
        "equip_slot": None,
        "stat_bonuses": {},
        "consumable_effect": {"type": "heal", "magnitude": 40},
        "sell_value": 15,
    }


def _make_enemy(ai_behavior="aggressive", x=5, y=5, pid="enemy1",
                inventory=None, equipment=None,
                hp=200, max_hp=200, enemy_type=None) -> PlayerState:
    """Create an AI hero party unit.

    Phase 28-FIX: enemy_type=None means this is a hero party AI (not a dungeon
    monster). Passive pickup and auto-equip are guarded behind enemy_type is None.
    """
    unit = PlayerState(
        player_id=pid,
        username=f"Test {ai_behavior.title()}",
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=15,
        ranged_damage=10,
        armor=2,
        team="b",
        unit_type="ai",
        hero_id=None,
        ai_behavior=ai_behavior,
        enemy_type=enemy_type,
        ranged_range=5,
        vision_range=7,
        inventory=inventory or [],
        equipment=equipment or {},
    )
    return unit


def _make_player(x=10, y=10, pid="player1") -> PlayerState:
    """Create a human player unit."""
    return PlayerState(
        player_id=pid,
        username="Test Player",
        position=Position(x=x, y=y),
        hp=100,
        max_hp=100,
        attack_damage=10,
        team="a",
        unit_type="human",
        vision_range=7,
    )


def _register_in_match(*units: PlayerState) -> None:
    """Register units in _player_states for equip_item to find them."""
    _player_states[MATCH_ID] = {u.player_id: u for u in units}


# ---------------------------------------------------------------------------
# 1. Role Stat Weights Constants
# ---------------------------------------------------------------------------

class TestRoleStatWeights:
    """Verify _ROLE_STAT_WEIGHTS has all expected roles."""

    def test_aggressive_weights_exist(self):
        assert "aggressive" in _ROLE_STAT_WEIGHTS
        assert _ROLE_STAT_WEIGHTS["aggressive"]["attack_damage"] == 3.0

    def test_ranged_weights_exist(self):
        assert "ranged" in _ROLE_STAT_WEIGHTS
        assert _ROLE_STAT_WEIGHTS["ranged"]["ranged_damage"] == 3.0

    def test_boss_weights_exist(self):
        assert "boss" in _ROLE_STAT_WEIGHTS
        assert _ROLE_STAT_WEIGHTS["boss"]["max_hp"] == 2.5

    def test_support_weights_exist(self):
        assert "support" in _ROLE_STAT_WEIGHTS
        assert _ROLE_STAT_WEIGHTS["support"]["cooldown_reduction_pct"] == 2.5


# ---------------------------------------------------------------------------
# 2. score_item_for_role
# ---------------------------------------------------------------------------

class TestScoreItemForRole:
    """Test the item scoring function."""

    def test_aggressive_prefers_damage(self):
        """Aggressive role scores a sword (+10 atk) > robe (+10 armor)."""
        sword = _make_weapon("Sword", atk=10)
        robe = _make_armor("Robe", armor_val=10)

        sword_score = score_item_for_role(sword, "aggressive")
        robe_score = score_item_for_role(robe, "aggressive")

        assert sword_score > robe_score
        # sword: 10 * 3.0 = 30.0 (attack_damage)
        # robe:  10 * 1.0 = 10.0 (armor)
        assert sword_score == 30.0
        assert robe_score == 10.0

    def test_support_prefers_defense(self):
        """Support role scores armor+hp > pure attack damage."""
        sword = _make_weapon("Sword", atk=10)
        robe = _make_support_armor("Robe", armor_val=8, max_hp=15, cdr=0.05)

        sword_score = score_item_for_role(sword, "support")
        robe_score = score_item_for_role(robe, "support")

        # sword: 10 * 0 (attack_damage not in support weights) = 0
        # robe: 8 * 2.5 + 15 * 3.0 + 0.05 * 2.5 = 20 + 45 + 0.125 = 65.125
        assert robe_score > sword_score

    def test_ranged_prefers_ranged_damage(self):
        """Ranged role scores ranged weapon > melee weapon."""
        bow = _make_ranged_weapon("Bow", rdmg=10)
        sword = _make_weapon("Sword", atk=10)

        bow_score = score_item_for_role(bow, "ranged")
        sword_score = score_item_for_role(sword, "ranged")

        # bow: 10 * 3.0 = 30.0 (ranged_damage)
        # sword: 10 * 0 = 0 (attack_damage not in ranged weights)
        assert bow_score > sword_score

    def test_consumable_returns_zero(self):
        """Consumables (potions) score 0 — they should never be compared."""
        potion = _make_potion()
        assert score_item_for_role(potion, "aggressive") == 0.0

    def test_none_item_returns_zero(self):
        assert score_item_for_role(None, "aggressive") == 0.0

    def test_empty_dict_returns_zero(self):
        assert score_item_for_role({}, "aggressive") == 0.0

    def test_unknown_role_falls_back_to_aggressive(self):
        """Unknown role uses aggressive weights as fallback."""
        sword = _make_weapon("Sword", atk=10)
        assert score_item_for_role(sword, "unknown_role") == 30.0  # 10 * 3.0

    def test_boss_prefers_tanky_items(self):
        """Boss role values max_hp and armor highly."""
        tanky_armor = _make_armor("Shield", armor_val=10, max_hp=20)
        boss_score = score_item_for_role(tanky_armor, "boss")
        # armor: 10 * 2.0 + max_hp: 20 * 2.5 = 20 + 50 = 70
        assert boss_score == 70.0


# ---------------------------------------------------------------------------
# 3. try_auto_equip
# ---------------------------------------------------------------------------

class TestTryAutoEquip:
    """Test the auto-equip decision function."""

    def test_equip_upgrade_empty_slot(self):
        """AI with no weapon picks up sword → auto-equips it (score > 0)."""
        sword = _make_weapon("Iron Sword", atk=10)
        enemy = _make_enemy(inventory=[sword])
        _register_in_match(enemy)

        results = try_auto_equip(enemy, MATCH_ID)

        assert len(results) == 1
        assert results[0]["slot"] == "weapon"
        assert results[0]["equipped"]["name"] == "Iron Sword"
        assert len(enemy.inventory) == 0  # Sword moved from inventory to equipment

    def test_equip_upgrade_better_weapon(self):
        """AI with common sword picks up rare sword → equips rare."""
        common_sword = _make_weapon("Common Sword", atk=5, rarity="common")
        rare_sword = _make_weapon("Rare Sword", atk=15, rarity="rare")

        enemy = _make_enemy(
            inventory=[rare_sword],
            equipment={"weapon": common_sword},
        )
        _register_in_match(enemy)

        results = try_auto_equip(enemy, MATCH_ID)

        assert len(results) == 1
        assert enemy.equipment["weapon"]["name"] == "Rare Sword"
        # Common sword should be back in inventory (swap)
        assert any(it["name"] == "Common Sword" for it in enemy.inventory)

    def test_no_downgrade(self):
        """AI with epic armor picks up common armor → keeps epic."""
        epic_armor = _make_armor("Epic Plate", armor_val=20, rarity="epic")
        common_armor = _make_armor("Rusty Plate", armor_val=3, rarity="common")

        enemy = _make_enemy(
            inventory=[common_armor],
            equipment={"armor": epic_armor},
        )
        _register_in_match(enemy)

        results = try_auto_equip(enemy, MATCH_ID)

        assert len(results) == 0
        assert enemy.equipment["armor"]["name"] == "Epic Plate"
        assert len(enemy.inventory) == 1  # Common stays in inventory

    def test_skips_consumables(self):
        """AI picks up potion → does not try to equip it."""
        potion = _make_potion()
        enemy = _make_enemy(inventory=[potion])
        _register_in_match(enemy)

        results = try_auto_equip(enemy, MATCH_ID)

        assert len(results) == 0
        assert len(enemy.inventory) == 1  # Potion stays in inventory

    def test_equip_multiple_slots(self):
        """AI with sword and armor in inventory → equips both."""
        sword = _make_weapon("Good Sword", atk=12)
        armor = _make_armor("Good Plate", armor_val=8)
        enemy = _make_enemy(inventory=[sword, armor])
        _register_in_match(enemy)

        results = try_auto_equip(enemy, MATCH_ID)

        assert len(results) == 2
        assert enemy.equipment.get("weapon") is not None
        assert enemy.equipment.get("armor") is not None
        assert len(enemy.inventory) == 0

    def test_empty_inventory_returns_empty(self):
        """AI with empty inventory → no equip results."""
        enemy = _make_enemy(inventory=[])
        _register_in_match(enemy)

        results = try_auto_equip(enemy, MATCH_ID)
        assert results == []

    def test_role_affects_equip_decision(self):
        """Support AI prefers defensive gear over offensive gear in same slot."""
        # Create two weapons: one offensive, one with defensive stats
        offensive = _make_weapon("Dagger", atk=10)
        # Make a "caster" weapon with CDR-oriented stats
        defensive_weapon = {
            "item_id": "staff",
            "instance_id": "inst_staff_magic",
            "name": "Mystic Staff",
            "item_type": "weapon",
            "rarity": "magic",
            "equip_slot": "weapon",
            "stat_bonuses": {
                "attack_damage": 2,
                "ranged_damage": 0,
                "armor": 0,
                "max_hp": 15,
                "cooldown_reduction_pct": 0.05,
                "skill_damage_pct": 0.10,
            },
            "weapon_category": "caster",
        }

        # Support AI with dagger equipped, staff in inventory
        enemy = _make_enemy(
            ai_behavior="support",
            inventory=[defensive_weapon],
            equipment={"weapon": offensive},
        )
        _register_in_match(enemy)

        results = try_auto_equip(enemy, MATCH_ID)

        # Support should swap to staff (max_hp*3.0 + cdr*2.5 + skill*2.0 > atk*0)
        # Staff score: 15*3.0 + 0.05*2.5 + 0.10*2.0 = 45 + 0.125 + 0.2 = 45.325
        # Dagger score for support: attack_damage is not in support weights → 0
        assert len(results) == 1
        assert enemy.equipment["weapon"]["name"] == "Mystic Staff"


# ---------------------------------------------------------------------------
# 4. Integration — Passive Pickup + Auto-Equip
# ---------------------------------------------------------------------------

class TestPassivePickupAutoEquip:
    """Test that auto-equip triggers after passive loot pickup for AI units.

    NOTE: These tests require auto-equip to be wired into _resolve_loot,
    Phase 28E wired auto-equip into _resolve_loot.  Tests now pass.
    """

    def test_ai_auto_equips_after_pickup(self):
        """AI enemy picks up a weapon from ground → auto-equips it."""
        sword = _make_weapon("Ground Sword", atk=10)
        enemy = _make_enemy(x=5, y=5)
        _register_in_match(enemy)

        ground_items = {"5,5": [sword]}
        players = {enemy.player_id: enemy}

        results: list[ActionResult] = []
        items_picked_up: list[dict] = []
        _resolve_loot(
            loot_actions=[],
            players=players,
            chest_states=None,
            ground_items=ground_items,
            results=results,
            chest_opened=[],
            items_picked_up=items_picked_up,
            match_id=MATCH_ID,
        )

        # Sword should have been picked up AND equipped
        assert enemy.equipment.get("weapon") is not None
        assert enemy.equipment["weapon"]["name"] == "Ground Sword"
        # Check that equip log message was generated
        equip_msgs = [r for r in results if "equipped" in (r.message or "")]
        assert len(equip_msgs) >= 1

    def test_human_player_no_auto_equip(self):
        """Human player picks up item → no auto-equip triggered."""
        sword = _make_weapon("Player Sword", atk=10)
        player = _make_player(x=3, y=3)
        _register_in_match(player)

        ground_items = {"3,3": [sword]}
        players = {player.player_id: player}

        results: list[ActionResult] = []
        items_picked_up: list[dict] = []
        _resolve_loot(
            loot_actions=[],
            players=players,
            chest_states=None,
            ground_items=ground_items,
            results=results,
            chest_opened=[],
            items_picked_up=items_picked_up,
        )

        # Item in inventory, but NOT auto-equipped
        assert len(player.inventory) == 1
        assert player.equipment.get("weapon") is None

    def test_ai_equip_combat_log_message(self):
        """AI equip events produce descriptive combat log messages."""
        sword = _make_weapon("Darksteel Blade", atk=15)
        enemy = _make_enemy(x=5, y=5, pid="demon1")
        _register_in_match(enemy)

        ground_items = {"5,5": [sword]}
        players = {enemy.player_id: enemy}

        results: list[ActionResult] = []
        items_picked_up: list[dict] = []
        _resolve_loot(
            loot_actions=[],
            players=players,
            chest_states=None,
            ground_items=ground_items,
            results=results,
            chest_opened=[],
            items_picked_up=items_picked_up,
            match_id=MATCH_ID,
        )

        equip_msgs = [r for r in results if "equipped" in (r.message or "")]
        assert len(equip_msgs) == 1
        assert "Darksteel Blade" in equip_msgs[0].message
