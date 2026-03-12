"""
Tests for Phase 5 Feature 8: Shared Bank / Stash system.

Covers:
- Deposit item from hero inventory to bank
- Deposit preserves item data
- Deposit to full bank rejected (20/20)
- Deposit invalid item index rejected
- Deposit negative item index rejected
- Deposit dead hero rejected
- Deposit hero not found rejected
- Withdraw item from bank to hero inventory
- Withdraw preserves item data
- Withdraw to full hero inventory rejected (10/10)
- Withdraw invalid bank index rejected
- Withdraw negative bank index rejected
- Withdraw dead hero rejected
- Withdraw hero not found rejected
- Bank data persists across profile loads
- Get bank endpoint returns correct data
- Deposit → withdraw roundtrip
- Full flow: deposit multiple items → withdraw to different hero
- Bank survives hero death (items remain in bank)
"""

from __future__ import annotations

import pytest

from app.models.profile import (
    BANK_MAX_CAPACITY,
    Hero,
    HeroStats,
    PlayerProfile,
)
from app.models.items import INVENTORY_MAX_CAPACITY
from app.services.persistence import save_profile, load_or_create_profile


# ---------- Item Fixtures ----------

COMMON_SWORD = {
    "item_id": "common_sword",
    "name": "Rusty Sword",
    "item_type": "weapon",
    "rarity": "common",
    "equip_slot": "weapon",
    "stat_bonuses": {"attack_damage": 5, "ranged_damage": 0, "armor": 0, "max_hp": 0},
    "description": "A battered blade.",
    "sell_value": 10,
}

UNCOMMON_GREATSWORD = {
    "item_id": "uncommon_greatsword",
    "name": "Tempered Greatsword",
    "item_type": "weapon",
    "rarity": "uncommon",
    "equip_slot": "weapon",
    "stat_bonuses": {"attack_damage": 12, "ranged_damage": 0, "armor": 0, "max_hp": 0},
    "description": "Well-forged steel.",
    "sell_value": 35,
}

COMMON_CHAIN_ARMOR = {
    "item_id": "common_chain_armor",
    "name": "Chain Mail",
    "item_type": "armor",
    "rarity": "common",
    "equip_slot": "armor",
    "stat_bonuses": {"attack_damage": 0, "ranged_damage": 0, "armor": 3, "max_hp": 0},
    "description": "Basic chain armor.",
    "sell_value": 12,
}

COMMON_RING = {
    "item_id": "common_ring",
    "name": "Iron Ring",
    "item_type": "accessory",
    "rarity": "common",
    "equip_slot": "accessory",
    "stat_bonuses": {"attack_damage": 0, "ranged_damage": 0, "armor": 0, "max_hp": 5},
    "description": "A simple ring.",
    "sell_value": 8,
}

HEALTH_POTION = {
    "item_id": "health_potion",
    "name": "Health Potion",
    "item_type": "consumable",
    "rarity": "common",
    "equip_slot": None,
    "stat_bonuses": {"attack_damage": 0, "ranged_damage": 0, "armor": 0, "max_hp": 0},
    "consumable_effect": {"type": "heal", "magnitude": 25},
    "description": "Restores 25 HP.",
    "sell_value": 5,
}


# ---------- Fixtures ----------

@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Redirect persistence to a temp directory for test isolation."""
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    monkeypatch.setattr("app.services.persistence._data_dir", players_dir)
    return players_dir


@pytest.fixture
def profile_with_items(temp_data_dir):
    """Profile with one hero holding items in bag, empty bank."""
    hero = Hero(
        hero_id="hero-bank-test",
        name="Bank Knight",
        class_id="crusader",
        stats=HeroStats(hp=100, max_hp=100, attack_damage=15, ranged_damage=10, armor=2),
        equipment={"weapon": None, "armor": None, "accessory": None},
        inventory=[
            COMMON_SWORD.copy(),
            COMMON_CHAIN_ARMOR.copy(),
            COMMON_RING.copy(),
            HEALTH_POTION.copy(),
        ],
        is_alive=True,
    )
    profile = PlayerProfile(
        username="bank_tester",
        gold=500,
        heroes=[hero],
        bank=[],
    )
    save_profile(profile)
    return profile


@pytest.fixture
def profile_with_bank_items(temp_data_dir):
    """Profile with items already in the bank."""
    hero = Hero(
        hero_id="hero-withdraw-test",
        name="Withdraw Knight",
        class_id="crusader",
        stats=HeroStats(hp=100, max_hp=100, attack_damage=15, ranged_damage=10, armor=2),
        equipment={"weapon": None, "armor": None, "accessory": None},
        inventory=[HEALTH_POTION.copy()],
        is_alive=True,
    )
    profile = PlayerProfile(
        username="bank_withdraw_tester",
        gold=500,
        heroes=[hero],
        bank=[COMMON_SWORD.copy(), UNCOMMON_GREATSWORD.copy(), COMMON_CHAIN_ARMOR.copy()],
    )
    save_profile(profile)
    return profile


@pytest.fixture
def profile_two_heroes(temp_data_dir):
    """Profile with two heroes for cross-hero bank operations."""
    hero1 = Hero(
        hero_id="hero-bank-a",
        name="Depositor",
        class_id="crusader",
        stats=HeroStats(hp=100, max_hp=100, attack_damage=15, ranged_damage=10, armor=2),
        equipment={"weapon": None, "armor": None, "accessory": None},
        inventory=[COMMON_SWORD.copy(), UNCOMMON_GREATSWORD.copy()],
        is_alive=True,
    )
    hero2 = Hero(
        hero_id="hero-bank-b",
        name="Receiver",
        class_id="ranger",
        stats=HeroStats(hp=80, max_hp=80, attack_damage=10, ranged_damage=15, armor=1),
        equipment={"weapon": None, "armor": None, "accessory": None},
        inventory=[],
        is_alive=True,
    )
    profile = PlayerProfile(
        username="bank_two_heroes",
        gold=500,
        heroes=[hero1, hero2],
        bank=[],
    )
    save_profile(profile)
    return profile


# ---------- Constant Tests ----------

class TestBankConstants:
    """Verify bank capacity constant."""

    def test_bank_max_capacity_is_20(self):
        assert BANK_MAX_CAPACITY == 20


# ---------- Deposit Tests ----------

class TestBankDeposit:
    """Test depositing items from hero inventory to bank."""

    @pytest.mark.asyncio
    async def test_deposit_basic(self, profile_with_items):
        """Deposit moves item from hero bag to bank."""
        from app.routes.town import bank_deposit, DepositRequest

        req = DepositRequest(username="bank_tester", hero_id="hero-bank-test", item_index=0)
        result = await bank_deposit(req)

        assert result["status"] == "ok"
        assert len(result["bank"]) == 1
        assert result["bank"][0]["item_id"] == "common_sword"
        assert len(result["inventory"]) == 3  # was 4, now 3

    @pytest.mark.asyncio
    async def test_deposit_preserves_item_data(self, profile_with_items):
        """Deposited item retains all fields (stats, rarity, description)."""
        from app.routes.town import bank_deposit, DepositRequest

        req = DepositRequest(username="bank_tester", hero_id="hero-bank-test", item_index=0)
        result = await bank_deposit(req)

        banked = result["bank"][0]
        assert banked["name"] == "Rusty Sword"
        assert banked["rarity"] == "common"
        assert banked["stat_bonuses"]["attack_damage"] == 5
        assert banked["description"] == "A battered blade."
        assert banked["sell_value"] == 10

    @pytest.mark.asyncio
    async def test_deposit_consumable(self, profile_with_items):
        """Consumables can also be deposited."""
        from app.routes.town import bank_deposit, DepositRequest

        req = DepositRequest(username="bank_tester", hero_id="hero-bank-test", item_index=3)
        result = await bank_deposit(req)

        assert result["status"] == "ok"
        assert result["bank"][0]["item_id"] == "health_potion"

    @pytest.mark.asyncio
    async def test_deposit_full_bank_rejected(self, temp_data_dir):
        """Deposit fails when bank is at max capacity (20)."""
        from app.routes.town import bank_deposit, DepositRequest
        from fastapi import HTTPException

        # Create profile with full bank
        filler_items = [COMMON_SWORD.copy() for _ in range(BANK_MAX_CAPACITY)]
        hero = Hero(
            hero_id="hero-full-bank",
            name="Full Bank Hero",
            class_id="crusader",
            inventory=[COMMON_RING.copy()],
            is_alive=True,
        )
        profile = PlayerProfile(
            username="full_bank_user",
            heroes=[hero],
            bank=filler_items,
        )
        save_profile(profile)

        req = DepositRequest(username="full_bank_user", hero_id="hero-full-bank", item_index=0)
        with pytest.raises(HTTPException) as exc_info:
            await bank_deposit(req)
        assert exc_info.value.status_code == 400
        assert "full" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_deposit_invalid_index(self, profile_with_items):
        """Deposit with out-of-range index fails."""
        from app.routes.town import bank_deposit, DepositRequest
        from fastapi import HTTPException

        req = DepositRequest(username="bank_tester", hero_id="hero-bank-test", item_index=99)
        with pytest.raises(HTTPException) as exc_info:
            await bank_deposit(req)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_deposit_negative_index(self, profile_with_items):
        """Deposit with negative index fails."""
        from app.routes.town import bank_deposit, DepositRequest
        from fastapi import HTTPException

        req = DepositRequest(username="bank_tester", hero_id="hero-bank-test", item_index=-1)
        with pytest.raises(HTTPException) as exc_info:
            await bank_deposit(req)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_deposit_dead_hero_rejected(self, temp_data_dir):
        """Depositing from a dead hero fails."""
        from app.routes.town import bank_deposit, DepositRequest
        from fastapi import HTTPException

        hero = Hero(
            hero_id="hero-dead-deposit",
            name="Dead Knight",
            class_id="crusader",
            inventory=[COMMON_SWORD.copy()],
            is_alive=False,
        )
        profile = PlayerProfile(username="dead_deposit_user", heroes=[hero])
        save_profile(profile)

        req = DepositRequest(username="dead_deposit_user", hero_id="hero-dead-deposit", item_index=0)
        with pytest.raises(HTTPException) as exc_info:
            await bank_deposit(req)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_deposit_hero_not_found(self, profile_with_items):
        """Deposit with nonexistent hero ID fails."""
        from app.routes.town import bank_deposit, DepositRequest
        from fastapi import HTTPException

        req = DepositRequest(username="bank_tester", hero_id="nonexistent", item_index=0)
        with pytest.raises(HTTPException) as exc_info:
            await bank_deposit(req)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_deposit_persists(self, profile_with_items):
        """Deposited items persist after profile reload."""
        from app.routes.town import bank_deposit, DepositRequest

        req = DepositRequest(username="bank_tester", hero_id="hero-bank-test", item_index=0)
        await bank_deposit(req)

        # Reload from disk
        reloaded = load_or_create_profile("bank_tester")
        assert len(reloaded.bank) == 1
        assert reloaded.bank[0]["item_id"] == "common_sword"
        assert len(reloaded.heroes[0].inventory) == 3


# ---------- Withdraw Tests ----------

class TestBankWithdraw:
    """Test withdrawing items from bank to hero inventory."""

    @pytest.mark.asyncio
    async def test_withdraw_basic(self, profile_with_bank_items):
        """Withdraw moves item from bank to hero bag."""
        from app.routes.town import bank_withdraw, WithdrawRequest

        req = WithdrawRequest(username="bank_withdraw_tester", hero_id="hero-withdraw-test", bank_index=0)
        result = await bank_withdraw(req)

        assert result["status"] == "ok"
        assert len(result["bank"]) == 2  # was 3, now 2
        assert len(result["inventory"]) == 2  # was 1, now 2
        assert result["item"]["item_id"] == "common_sword"

    @pytest.mark.asyncio
    async def test_withdraw_preserves_item_data(self, profile_with_bank_items):
        """Withdrawn item retains all original data."""
        from app.routes.town import bank_withdraw, WithdrawRequest

        req = WithdrawRequest(username="bank_withdraw_tester", hero_id="hero-withdraw-test", bank_index=1)
        result = await bank_withdraw(req)

        withdrawn = result["item"]
        assert withdrawn["name"] == "Tempered Greatsword"
        assert withdrawn["rarity"] == "uncommon"
        assert withdrawn["stat_bonuses"]["attack_damage"] == 12

    @pytest.mark.asyncio
    async def test_withdraw_full_inventory_rejected(self, temp_data_dir):
        """Withdraw fails when hero inventory is full (10/10)."""
        from app.routes.town import bank_withdraw, WithdrawRequest
        from fastapi import HTTPException

        # Create hero with full inventory
        full_inv = [COMMON_SWORD.copy() for _ in range(INVENTORY_MAX_CAPACITY)]
        hero = Hero(
            hero_id="hero-full-inv",
            name="Full Inv Hero",
            class_id="crusader",
            inventory=full_inv,
            is_alive=True,
        )
        profile = PlayerProfile(
            username="full_inv_withdraw",
            heroes=[hero],
            bank=[COMMON_RING.copy()],
        )
        save_profile(profile)

        req = WithdrawRequest(username="full_inv_withdraw", hero_id="hero-full-inv", bank_index=0)
        with pytest.raises(HTTPException) as exc_info:
            await bank_withdraw(req)
        assert exc_info.value.status_code == 400
        assert "full" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_withdraw_invalid_index(self, profile_with_bank_items):
        """Withdraw with out-of-range bank index fails."""
        from app.routes.town import bank_withdraw, WithdrawRequest
        from fastapi import HTTPException

        req = WithdrawRequest(username="bank_withdraw_tester", hero_id="hero-withdraw-test", bank_index=99)
        with pytest.raises(HTTPException) as exc_info:
            await bank_withdraw(req)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_withdraw_negative_index(self, profile_with_bank_items):
        """Withdraw with negative bank index fails."""
        from app.routes.town import bank_withdraw, WithdrawRequest
        from fastapi import HTTPException

        req = WithdrawRequest(username="bank_withdraw_tester", hero_id="hero-withdraw-test", bank_index=-1)
        with pytest.raises(HTTPException) as exc_info:
            await bank_withdraw(req)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_withdraw_dead_hero_rejected(self, temp_data_dir):
        """Withdrawing to a dead hero fails."""
        from app.routes.town import bank_withdraw, WithdrawRequest
        from fastapi import HTTPException

        hero = Hero(
            hero_id="hero-dead-withdraw",
            name="Dead Knight",
            class_id="crusader",
            inventory=[],
            is_alive=False,
        )
        profile = PlayerProfile(
            username="dead_withdraw_user",
            heroes=[hero],
            bank=[COMMON_SWORD.copy()],
        )
        save_profile(profile)

        req = WithdrawRequest(username="dead_withdraw_user", hero_id="hero-dead-withdraw", bank_index=0)
        with pytest.raises(HTTPException) as exc_info:
            await bank_withdraw(req)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_withdraw_hero_not_found(self, profile_with_bank_items):
        """Withdraw with nonexistent hero ID fails."""
        from app.routes.town import bank_withdraw, WithdrawRequest
        from fastapi import HTTPException

        req = WithdrawRequest(username="bank_withdraw_tester", hero_id="nonexistent", bank_index=0)
        with pytest.raises(HTTPException) as exc_info:
            await bank_withdraw(req)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_withdraw_empty_bank(self, temp_data_dir):
        """Withdraw from empty bank fails."""
        from app.routes.town import bank_withdraw, WithdrawRequest
        from fastapi import HTTPException

        hero = Hero(
            hero_id="hero-empty-bank",
            name="Empty Bank Hero",
            class_id="crusader",
            inventory=[],
            is_alive=True,
        )
        profile = PlayerProfile(username="empty_bank_user", heroes=[hero], bank=[])
        save_profile(profile)

        req = WithdrawRequest(username="empty_bank_user", hero_id="hero-empty-bank", bank_index=0)
        with pytest.raises(HTTPException) as exc_info:
            await bank_withdraw(req)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_withdraw_persists(self, profile_with_bank_items):
        """Withdrawn items persist after profile reload."""
        from app.routes.town import bank_withdraw, WithdrawRequest

        req = WithdrawRequest(username="bank_withdraw_tester", hero_id="hero-withdraw-test", bank_index=0)
        await bank_withdraw(req)

        # Reload from disk
        reloaded = load_or_create_profile("bank_withdraw_tester")
        assert len(reloaded.bank) == 2
        assert len(reloaded.heroes[0].inventory) == 2
        assert reloaded.heroes[0].inventory[1]["item_id"] == "common_sword"


# ---------- Get Bank Tests ----------

class TestGetBank:
    """Test the GET /bank endpoint."""

    @pytest.mark.asyncio
    async def test_get_bank_empty(self, profile_with_items):
        """Get bank returns empty list for new profile."""
        from app.routes.town import get_bank

        result = await get_bank(username="bank_tester")
        assert result["bank"] == []
        assert result["capacity"] == 20
        assert result["used"] == 0

    @pytest.mark.asyncio
    async def test_get_bank_with_items(self, profile_with_bank_items):
        """Get bank returns stored items."""
        from app.routes.town import get_bank

        result = await get_bank(username="bank_withdraw_tester")
        assert len(result["bank"]) == 3
        assert result["capacity"] == 20
        assert result["used"] == 3


# ---------- Integration Tests ----------

class TestBankIntegration:
    """End-to-end bank workflows."""

    @pytest.mark.asyncio
    async def test_deposit_withdraw_roundtrip(self, profile_with_items):
        """Deposit then withdraw returns item to hero with all data intact."""
        from app.routes.town import bank_deposit, bank_withdraw, DepositRequest, WithdrawRequest

        # Deposit the sword
        dep_req = DepositRequest(username="bank_tester", hero_id="hero-bank-test", item_index=0)
        dep_result = await bank_deposit(dep_req)
        assert len(dep_result["bank"]) == 1
        assert len(dep_result["inventory"]) == 3

        # Withdraw it back
        with_req = WithdrawRequest(username="bank_tester", hero_id="hero-bank-test", bank_index=0)
        with_result = await bank_withdraw(with_req)
        assert len(with_result["bank"]) == 0
        assert len(with_result["inventory"]) == 4
        # Item should be appended at end
        assert with_result["inventory"][3]["item_id"] == "common_sword"
        assert with_result["inventory"][3]["name"] == "Rusty Sword"

    @pytest.mark.asyncio
    async def test_deposit_multiple_then_withdraw_to_different_hero(self, profile_two_heroes):
        """Deposit from hero A, withdraw to hero B."""
        from app.routes.town import bank_deposit, bank_withdraw, DepositRequest, WithdrawRequest

        # Deposit both items from hero A
        dep1 = DepositRequest(username="bank_two_heroes", hero_id="hero-bank-a", item_index=0)
        await bank_deposit(dep1)
        dep2 = DepositRequest(username="bank_two_heroes", hero_id="hero-bank-a", item_index=0)
        result2 = await bank_deposit(dep2)

        assert len(result2["bank"]) == 2
        assert len(result2["inventory"]) == 0  # hero A's bag is now empty

        # Withdraw first item to hero B
        with_req = WithdrawRequest(username="bank_two_heroes", hero_id="hero-bank-b", bank_index=0)
        with_result = await bank_withdraw(with_req)

        assert len(with_result["bank"]) == 1
        assert len(with_result["inventory"]) == 1
        assert with_result["inventory"][0]["item_id"] == "common_sword"

    @pytest.mark.asyncio
    async def test_bank_survives_hero_death(self, profile_with_items):
        """Bank items remain even if the depositing hero dies."""
        from app.routes.town import bank_deposit, DepositRequest

        # Deposit an item
        dep_req = DepositRequest(username="bank_tester", hero_id="hero-bank-test", item_index=0)
        await bank_deposit(dep_req)

        # Simulate hero death
        profile = load_or_create_profile("bank_tester")
        profile.heroes[0].is_alive = False
        profile.heroes[0].inventory = []
        profile.heroes[0].equipment = {}
        save_profile(profile)

        # Bank still has the item
        reloaded = load_or_create_profile("bank_tester")
        assert len(reloaded.bank) == 1
        assert reloaded.bank[0]["item_id"] == "common_sword"
        assert reloaded.heroes[0].is_alive is False

    @pytest.mark.asyncio
    async def test_deposit_all_item_types(self, profile_with_items):
        """All item types (weapon, armor, accessory, consumable) can be deposited."""
        from app.routes.town import bank_deposit, DepositRequest

        # Deposit all 4 items one by one (always index 0 since list shrinks)
        for _ in range(4):
            req = DepositRequest(username="bank_tester", hero_id="hero-bank-test", item_index=0)
            await bank_deposit(req)

        profile = load_or_create_profile("bank_tester")
        assert len(profile.bank) == 4
        assert len(profile.heroes[0].inventory) == 0
        item_ids = [i["item_id"] for i in profile.bank]
        assert "common_sword" in item_ids
        assert "common_chain_armor" in item_ids
        assert "common_ring" in item_ids
        assert "health_potion" in item_ids

    @pytest.mark.asyncio
    async def test_fill_bank_to_capacity(self, temp_data_dir):
        """Can deposit exactly BANK_MAX_CAPACITY items, then the next is rejected."""
        from app.routes.town import bank_deposit, DepositRequest
        from fastapi import HTTPException

        # Create hero with exactly 20 items (we'll deposit in batches)
        items = [COMMON_SWORD.copy() for _ in range(10)]
        hero = Hero(
            hero_id="hero-fill-bank",
            name="Fill Bank Hero",
            class_id="crusader",
            inventory=items,
            is_alive=True,
        )
        profile = PlayerProfile(
            username="fill_bank_user",
            heroes=[hero],
            bank=[COMMON_RING.copy() for _ in range(BANK_MAX_CAPACITY - 10)],  # 10 already in bank
        )
        save_profile(profile)

        # Deposit 10 more to fill bank to 20
        for i in range(10):
            req = DepositRequest(username="fill_bank_user", hero_id="hero-fill-bank", item_index=0)
            await bank_deposit(req)

        # Bank should be full now
        profile = load_or_create_profile("fill_bank_user")
        assert len(profile.bank) == BANK_MAX_CAPACITY

        # Add one more item to hero inventory for the rejection test
        profile.heroes[0].inventory = [HEALTH_POTION.copy()]
        save_profile(profile)

        # Next deposit should fail
        req = DepositRequest(username="fill_bank_user", hero_id="hero-fill-bank", item_index=0)
        with pytest.raises(HTTPException) as exc_info:
            await bank_deposit(req)
        assert exc_info.value.status_code == 400
        assert "full" in exc_info.value.detail.lower()
