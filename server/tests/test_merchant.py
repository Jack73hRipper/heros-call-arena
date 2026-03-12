"""
Tests for Phase 5 Feature 6: Merchant buy/sell system.

Covers:
- Merchant stock endpoint returns items with buy prices
- Buy item: gold deducted, item added to hero inventory
- Buy item: insufficient gold rejected
- Buy item: inventory full rejected
- Buy item: dead hero rejected
- Buy item: invalid item rejected
- Sell item: gold credited, item removed from hero inventory
- Sell item: invalid index rejected
- Sell item: dead hero rejected
- Sell multiplier applied correctly
- Merchant config loading and caching
- End-to-end buy→sell flow
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.profile import (
    Hero,
    HeroStats,
    PlayerProfile,
    STARTING_GOLD,
)
from app.models.items import INVENTORY_MAX_CAPACITY
from app.services.persistence import save_profile, load_or_create_profile


# ---------- Fixtures ----------

@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Redirect persistence to a temp directory for test isolation."""
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    monkeypatch.setattr(
        "app.services.persistence._data_dir", players_dir
    )
    return players_dir


@pytest.fixture
def test_profile(temp_data_dir):
    """Create a test profile with one alive hero and sufficient gold."""
    hero = Hero(
        hero_id="hero-merchant-test",
        name="Test Knight",
        class_id="crusader",
        stats=HeroStats(hp=100, max_hp=100, attack_damage=15, ranged_damage=10, armor=2),
        equipment={},
        inventory=[],
        is_alive=True,
        hire_cost=50,
    )
    profile = PlayerProfile(
        username="merchant_tester",
        gold=500,
        heroes=[hero],
    )
    save_profile(profile)
    return profile


@pytest.fixture
def rich_profile(temp_data_dir):
    """Create a test profile with lots of gold for buy testing."""
    hero = Hero(
        hero_id="hero-rich",
        name="Rich Hero",
        class_id="ranger",
        stats=HeroStats(),
        equipment={},
        inventory=[],
        is_alive=True,
    )
    profile = PlayerProfile(
        username="rich_merchant",
        gold=10000,
        heroes=[hero],
    )
    save_profile(profile)
    return profile


@pytest.fixture
def profile_with_items(temp_data_dir):
    """Create a test profile with items in hero inventory for selling."""
    items = [
        {
            "item_id": "common_sword",
            "name": "Rusty Sword",
            "item_type": "weapon",
            "rarity": "common",
            "equip_slot": "weapon",
            "stat_bonuses": {"attack_damage": 5, "ranged_damage": 0, "armor": 0, "max_hp": 0},
            "description": "A battered blade.",
            "sell_value": 10,
        },
        {
            "item_id": "uncommon_greatsword",
            "name": "Tempered Greatsword",
            "item_type": "weapon",
            "rarity": "uncommon",
            "equip_slot": "weapon",
            "stat_bonuses": {"attack_damage": 12, "ranged_damage": 0, "armor": 0, "max_hp": 0},
            "description": "Well-forged steel.",
            "sell_value": 35,
        },
        {
            "item_id": "health_potion",
            "name": "Health Potion",
            "item_type": "consumable",
            "rarity": "common",
            "equip_slot": None,
            "stat_bonuses": {"attack_damage": 0, "ranged_damage": 0, "armor": 0, "max_hp": 0},
            "consumable_effect": {"type": "heal", "magnitude": 40},
            "description": "Restores 40 HP.",
            "sell_value": 15,
        },
    ]
    hero = Hero(
        hero_id="hero-seller",
        name="Seller Hero",
        class_id="hexblade",
        stats=HeroStats(),
        equipment={},
        inventory=items,
        is_alive=True,
    )
    profile = PlayerProfile(
        username="seller_tester",
        gold=200,
        heroes=[hero],
    )
    save_profile(profile)
    return profile


@pytest.fixture
def full_inventory_profile(temp_data_dir):
    """Create a profile where the hero's inventory is full (10 items)."""
    items = [
        {
            "item_id": f"common_sword",
            "name": "Rusty Sword",
            "item_type": "weapon",
            "rarity": "common",
            "equip_slot": "weapon",
            "stat_bonuses": {"attack_damage": 5, "ranged_damage": 0, "armor": 0, "max_hp": 0},
            "description": "A battered blade.",
            "sell_value": 10,
        }
        for _ in range(INVENTORY_MAX_CAPACITY)
    ]
    hero = Hero(
        hero_id="hero-full",
        name="Full Bag Hero",
        class_id="crusader",
        stats=HeroStats(),
        equipment={},
        inventory=items,
        is_alive=True,
    )
    profile = PlayerProfile(
        username="full_bag_tester",
        gold=1000,
        heroes=[hero],
    )
    save_profile(profile)
    return profile


# ============================================================
# 1. Merchant Stock Endpoint
# ============================================================

class TestMerchantStock:
    """Test GET /api/town/merchant/stock endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self, temp_data_dir):
        from fastapi.testclient import TestClient
        from app.main import app
        import app.routes.town as town_module
        town_module._merchant_cache = None
        self.client = TestClient(app)

    def test_stock_returns_items(self):
        resp = self.client.get("/api/town/merchant/stock")
        assert resp.status_code == 200
        data = resp.json()
        assert "stock" in data
        assert len(data["stock"]) > 0

    def test_stock_items_have_required_fields(self):
        resp = self.client.get("/api/town/merchant/stock")
        data = resp.json()
        for item in data["stock"]:
            assert "item_id" in item
            assert "name" in item
            assert "buy_price" in item
            assert "category" in item
            assert "sell_value" in item
            assert isinstance(item["buy_price"], int)
            assert item["buy_price"] > 0

    def test_stock_includes_consumables(self):
        resp = self.client.get("/api/town/merchant/stock")
        data = resp.json()
        item_ids = [i["item_id"] for i in data["stock"]]
        assert "health_potion" in item_ids
        assert "portal_scroll" in item_ids

    def test_stock_includes_equipment(self):
        resp = self.client.get("/api/town/merchant/stock")
        data = resp.json()
        item_ids = [i["item_id"] for i in data["stock"]]
        assert "common_sword" in item_ids
        assert "common_chain_armor" in item_ids
        assert "common_ring" in item_ids

    def test_stock_buy_prices_match_config(self):
        resp = self.client.get("/api/town/merchant/stock")
        data = resp.json()
        # Health potion should be 25g
        potion = next(i for i in data["stock"] if i["item_id"] == "health_potion")
        assert potion["buy_price"] == 25
        # Portal scroll should be 75g
        scroll = next(i for i in data["stock"] if i["item_id"] == "portal_scroll")
        assert scroll["buy_price"] == 75


# ============================================================
# 2. Merchant Buy Endpoint
# ============================================================

class TestMerchantBuy:
    """Test POST /api/town/merchant/buy endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self, temp_data_dir):
        from fastapi.testclient import TestClient
        from app.main import app
        import app.routes.town as town_module
        town_module._merchant_cache = None
        self.client = TestClient(app)

    def test_buy_item_success(self, test_profile):
        resp = self.client.post("/api/town/merchant/buy", json={
            "username": "merchant_tester",
            "hero_id": "hero-merchant-test",
            "item_id": "health_potion",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["gold"] == 500 - 25  # 25g for health potion
        assert data["item"]["item_id"] == "health_potion"
        assert data["hero_id"] == "hero-merchant-test"

    def test_buy_deducts_gold(self, test_profile):
        self.client.post("/api/town/merchant/buy", json={
            "username": "merchant_tester",
            "hero_id": "hero-merchant-test",
            "item_id": "health_potion",
        })
        # Verify gold persisted
        profile = load_or_create_profile("merchant_tester")
        assert profile.gold == 500 - 25

    def test_buy_adds_to_inventory(self, test_profile):
        self.client.post("/api/town/merchant/buy", json={
            "username": "merchant_tester",
            "hero_id": "hero-merchant-test",
            "item_id": "common_sword",
        })
        profile = load_or_create_profile("merchant_tester")
        hero = profile.heroes[0]
        assert len(hero.inventory) == 1
        assert hero.inventory[0]["item_id"] == "common_sword"

    def test_buy_multiple_items(self, rich_profile):
        for _ in range(3):
            resp = self.client.post("/api/town/merchant/buy", json={
                "username": "rich_merchant",
                "hero_id": "hero-rich",
                "item_id": "health_potion",
            })
            assert resp.status_code == 200

        profile = load_or_create_profile("rich_merchant")
        hero = profile.heroes[0]
        assert len(hero.inventory) == 3
        assert profile.gold == 10000 - (25 * 3)

    def test_buy_insufficient_gold(self, temp_data_dir):
        hero = Hero(
            hero_id="hero-poor",
            name="Broke Hero",
            class_id="crusader",
            stats=HeroStats(),
            is_alive=True,
        )
        profile = PlayerProfile(username="poor_tester", gold=5, heroes=[hero])
        save_profile(profile)

        resp = self.client.post("/api/town/merchant/buy", json={
            "username": "poor_tester",
            "hero_id": "hero-poor",
            "item_id": "health_potion",  # costs 25g
        })
        assert resp.status_code == 400
        assert "Insufficient gold" in resp.json()["detail"]

    def test_buy_inventory_full(self, full_inventory_profile):
        resp = self.client.post("/api/town/merchant/buy", json={
            "username": "full_bag_tester",
            "hero_id": "hero-full",
            "item_id": "health_potion",
        })
        assert resp.status_code == 400
        assert "full" in resp.json()["detail"].lower()

    def test_buy_dead_hero(self, temp_data_dir):
        hero = Hero(
            hero_id="hero-dead",
            name="Dead Hero",
            class_id="crusader",
            stats=HeroStats(),
            is_alive=False,
        )
        profile = PlayerProfile(username="dead_hero_tester", gold=500, heroes=[hero])
        save_profile(profile)

        resp = self.client.post("/api/town/merchant/buy", json={
            "username": "dead_hero_tester",
            "hero_id": "hero-dead",
            "item_id": "health_potion",
        })
        assert resp.status_code == 404
        assert "dead" in resp.json()["detail"].lower() or "not found" in resp.json()["detail"].lower()

    def test_buy_invalid_item(self, test_profile):
        resp = self.client.post("/api/town/merchant/buy", json={
            "username": "merchant_tester",
            "hero_id": "hero-merchant-test",
            "item_id": "legendary_dragon_sword",
        })
        assert resp.status_code == 404
        assert "not available" in resp.json()["detail"].lower()

    def test_buy_invalid_hero(self, test_profile):
        resp = self.client.post("/api/town/merchant/buy", json={
            "username": "merchant_tester",
            "hero_id": "nonexistent-hero",
            "item_id": "health_potion",
        })
        assert resp.status_code == 404

    def test_buy_missing_username(self):
        resp = self.client.post("/api/town/merchant/buy", json={
            "username": "",
            "hero_id": "hero-test",
            "item_id": "health_potion",
        })
        assert resp.status_code == 400

    def test_buy_equipment_item(self, test_profile):
        resp = self.client.post("/api/town/merchant/buy", json={
            "username": "merchant_tester",
            "hero_id": "hero-merchant-test",
            "item_id": "common_plate_armor",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["item"]["item_id"] == "common_plate_armor"
        assert data["item"]["equip_slot"] == "armor"

    def test_buy_portal_scroll(self, test_profile):
        resp = self.client.post("/api/town/merchant/buy", json={
            "username": "merchant_tester",
            "hero_id": "hero-merchant-test",
            "item_id": "portal_scroll",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["gold"] == 500 - 75
        assert data["item"]["item_id"] == "portal_scroll"


# ============================================================
# 3. Merchant Sell Endpoint
# ============================================================

class TestMerchantSell:
    """Test POST /api/town/merchant/sell endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self, temp_data_dir):
        from fastapi.testclient import TestClient
        from app.main import app
        import app.routes.town as town_module
        town_module._merchant_cache = None
        self.client = TestClient(app)

    def test_sell_item_success(self, profile_with_items):
        resp = self.client.post("/api/town/merchant/sell", json={
            "username": "seller_tester",
            "hero_id": "hero-seller",
            "item_index": 0,  # Rusty Sword, sell_value=10
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["sell_price"] == 10
        assert data["gold"] == 200 + 10
        assert data["sold_item"]["item_id"] == "common_sword"

    def test_sell_credits_gold(self, profile_with_items):
        self.client.post("/api/town/merchant/sell", json={
            "username": "seller_tester",
            "hero_id": "hero-seller",
            "item_index": 0,
        })
        profile = load_or_create_profile("seller_tester")
        assert profile.gold == 210

    def test_sell_removes_from_inventory(self, profile_with_items):
        self.client.post("/api/town/merchant/sell", json={
            "username": "seller_tester",
            "hero_id": "hero-seller",
            "item_index": 0,
        })
        profile = load_or_create_profile("seller_tester")
        hero = profile.heroes[0]
        assert len(hero.inventory) == 2  # Was 3, now 2
        # First item (common_sword) removed, uncommon_greatsword is now index 0
        assert hero.inventory[0]["item_id"] == "uncommon_greatsword"

    def test_sell_uncommon_item(self, profile_with_items):
        resp = self.client.post("/api/town/merchant/sell", json={
            "username": "seller_tester",
            "hero_id": "hero-seller",
            "item_index": 1,  # Tempered Greatsword, sell_value=35
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["sell_price"] == 35
        assert data["gold"] == 200 + 35

    def test_sell_consumable(self, profile_with_items):
        resp = self.client.post("/api/town/merchant/sell", json={
            "username": "seller_tester",
            "hero_id": "hero-seller",
            "item_index": 2,  # Health Potion, sell_value=15
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["sell_price"] == 15

    def test_sell_invalid_index_negative(self, profile_with_items):
        resp = self.client.post("/api/town/merchant/sell", json={
            "username": "seller_tester",
            "hero_id": "hero-seller",
            "item_index": -1,
        })
        assert resp.status_code == 400

    def test_sell_invalid_index_too_high(self, profile_with_items):
        resp = self.client.post("/api/town/merchant/sell", json={
            "username": "seller_tester",
            "hero_id": "hero-seller",
            "item_index": 99,
        })
        assert resp.status_code == 400

    def test_sell_dead_hero(self, temp_data_dir):
        hero = Hero(
            hero_id="hero-dead-seller",
            name="Dead Seller",
            class_id="crusader",
            stats=HeroStats(),
            inventory=[{"item_id": "common_sword", "name": "Sword", "sell_value": 10}],
            is_alive=False,
        )
        profile = PlayerProfile(username="dead_seller", gold=100, heroes=[hero])
        save_profile(profile)

        resp = self.client.post("/api/town/merchant/sell", json={
            "username": "dead_seller",
            "hero_id": "hero-dead-seller",
            "item_index": 0,
        })
        assert resp.status_code == 404

    def test_sell_empty_inventory(self, temp_data_dir):
        hero = Hero(
            hero_id="hero-empty",
            name="Empty Hero",
            class_id="ranger",
            stats=HeroStats(),
            inventory=[],
            is_alive=True,
        )
        profile = PlayerProfile(username="empty_seller", gold=100, heroes=[hero])
        save_profile(profile)

        resp = self.client.post("/api/town/merchant/sell", json={
            "username": "empty_seller",
            "hero_id": "hero-empty",
            "item_index": 0,
        })
        assert resp.status_code == 400

    def test_sell_missing_username(self):
        resp = self.client.post("/api/town/merchant/sell", json={
            "username": "",
            "hero_id": "hero-test",
            "item_index": 0,
        })
        assert resp.status_code == 400


# ============================================================
# 4. End-to-End Flow
# ============================================================

class TestMerchantFlow:
    """Test complete buy → sell round-trip flows."""

    @pytest.fixture(autouse=True)
    def setup_client(self, temp_data_dir):
        from fastapi.testclient import TestClient
        from app.main import app
        import app.routes.town as town_module
        town_module._merchant_cache = None
        self.client = TestClient(app)

    def test_buy_then_sell(self, test_profile):
        """Buy an item, then sell it back. Gold should decrease by the margin."""
        # Buy health potion for 25g
        buy_resp = self.client.post("/api/town/merchant/buy", json={
            "username": "merchant_tester",
            "hero_id": "hero-merchant-test",
            "item_id": "health_potion",
        })
        assert buy_resp.status_code == 200
        assert buy_resp.json()["gold"] == 475

        # Sell it back for 15g (sell_value)
        sell_resp = self.client.post("/api/town/merchant/sell", json={
            "username": "merchant_tester",
            "hero_id": "hero-merchant-test",
            "item_index": 0,
        })
        assert sell_resp.status_code == 200
        assert sell_resp.json()["gold"] == 490  # 475 + 15

        # Verify profile persisted
        profile = load_or_create_profile("merchant_tester")
        assert profile.gold == 490
        assert len(profile.heroes[0].inventory) == 0

    def test_buy_multiple_sell_some(self, rich_profile):
        """Buy several items, sell some, keep others."""
        # Buy 3 health potions and a sword
        for _ in range(3):
            self.client.post("/api/town/merchant/buy", json={
                "username": "rich_merchant",
                "hero_id": "hero-rich",
                "item_id": "health_potion",
            })
        self.client.post("/api/town/merchant/buy", json={
            "username": "rich_merchant",
            "hero_id": "hero-rich",
            "item_id": "common_sword",
        })

        profile = load_or_create_profile("rich_merchant")
        assert len(profile.heroes[0].inventory) == 4
        assert profile.gold == 10000 - (25 * 3) - 50  # 9875

        # Sell the sword (index 3)
        resp = self.client.post("/api/town/merchant/sell", json={
            "username": "rich_merchant",
            "hero_id": "hero-rich",
            "item_index": 3,
        })
        assert resp.status_code == 200

        profile = load_or_create_profile("rich_merchant")
        assert len(profile.heroes[0].inventory) == 3
        assert profile.gold == 9875 + 10  # sword sell_value=10

    def test_gold_economy_consistency(self, test_profile):
        """Verify gold is always consistent after multiple transactions."""
        expected_gold = 500

        # Buy common_sword (50g buy, 10g sell)
        resp = self.client.post("/api/town/merchant/buy", json={
            "username": "merchant_tester",
            "hero_id": "hero-merchant-test",
            "item_id": "common_sword",
        })
        expected_gold -= 50
        assert resp.json()["gold"] == expected_gold

        # Buy health_potion (25g buy, 15g sell)
        resp = self.client.post("/api/town/merchant/buy", json={
            "username": "merchant_tester",
            "hero_id": "hero-merchant-test",
            "item_id": "health_potion",
        })
        expected_gold -= 25
        assert resp.json()["gold"] == expected_gold

        # Sell sword (index 0, 10g)
        resp = self.client.post("/api/town/merchant/sell", json={
            "username": "merchant_tester",
            "hero_id": "hero-merchant-test",
            "item_index": 0,
        })
        expected_gold += 10
        assert resp.json()["gold"] == expected_gold

        # Final check
        profile = load_or_create_profile("merchant_tester")
        assert profile.gold == expected_gold
        assert len(profile.heroes[0].inventory) == 1  # Only potion remains
