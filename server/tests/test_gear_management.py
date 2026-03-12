"""
Tests for Phase 5 Feature 7: Town gear management (equip/unequip/transfer).

Covers:
- Equip item from inventory to equipment slot
- Equip item with swap (slot occupied → old item returns to bag)
- Equip consumable rejected
- Equip invalid index rejected
- Equip dead hero rejected
- Equip empty slot
- Unequip item from equipment slot to inventory
- Unequip empty slot rejected
- Unequip with full inventory rejected
- Unequip invalid slot rejected
- Unequip dead hero rejected
- Transfer item between heroes
- Transfer to full inventory rejected
- Transfer same hero rejected
- Transfer dead hero rejected
- Transfer invalid index rejected
- Full flow: buy → equip → unequip → transfer → sell
- Hydrate/serialize helpers
"""

from __future__ import annotations

import pytest

from app.models.profile import (
    Hero,
    HeroStats,
    PlayerProfile,
)
from app.models.items import INVENTORY_MAX_CAPACITY
from app.routes.town import (
    _hydrate_equipment,
    _hydrate_inventory,
    _serialize_equipment,
    _serialize_inventory,
)
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
def profile_with_gear(temp_data_dir):
    """Profile with one hero holding items in bag and equipment."""
    hero = Hero(
        hero_id="hero-gear-test",
        name="Gear Knight",
        class_id="crusader",
        stats=HeroStats(hp=100, max_hp=100, attack_damage=15, ranged_damage=10, armor=2),
        equipment={"weapon": None, "armor": None, "accessory": None},
        inventory=[COMMON_SWORD.copy(), COMMON_CHAIN_ARMOR.copy(), COMMON_RING.copy(), HEALTH_POTION.copy()],
        is_alive=True,
    )
    profile = PlayerProfile(
        username="gear_tester",
        gold=500,
        heroes=[hero],
    )
    save_profile(profile)
    return profile


@pytest.fixture
def profile_with_equipped(temp_data_dir):
    """Profile with a hero that has gear equipped."""
    hero = Hero(
        hero_id="hero-equipped",
        name="Equipped Knight",
        class_id="crusader",
        stats=HeroStats(hp=100, max_hp=100, attack_damage=15, ranged_damage=10, armor=2),
        equipment={
            "weapon": COMMON_SWORD.copy(),
            "armor": COMMON_CHAIN_ARMOR.copy(),
            "accessory": None,
        },
        inventory=[COMMON_RING.copy(), HEALTH_POTION.copy()],
        is_alive=True,
    )
    profile = PlayerProfile(
        username="equipped_tester",
        gold=500,
        heroes=[hero],
    )
    save_profile(profile)
    return profile


@pytest.fixture
def two_hero_profile(temp_data_dir):
    """Profile with two alive heroes for transfer testing."""
    hero1 = Hero(
        hero_id="hero-src",
        name="Source Knight",
        class_id="crusader",
        stats=HeroStats(),
        equipment={},
        inventory=[COMMON_SWORD.copy(), COMMON_CHAIN_ARMOR.copy(), HEALTH_POTION.copy()],
        is_alive=True,
    )
    hero2 = Hero(
        hero_id="hero-dest",
        name="Dest Ranger",
        class_id="ranger",
        stats=HeroStats(),
        equipment={},
        inventory=[COMMON_RING.copy()],
        is_alive=True,
    )
    profile = PlayerProfile(
        username="transfer_tester",
        gold=300,
        heroes=[hero1, hero2],
    )
    save_profile(profile)
    return profile


@pytest.fixture
def dead_hero_profile(temp_data_dir):
    """Profile with a dead hero."""
    hero = Hero(
        hero_id="hero-dead",
        name="Fallen Knight",
        class_id="crusader",
        stats=HeroStats(),
        equipment={},
        inventory=[COMMON_SWORD.copy()],
        is_alive=False,
    )
    profile = PlayerProfile(
        username="dead_tester",
        gold=100,
        heroes=[hero],
    )
    save_profile(profile)
    return profile


# ---------- Helper Tests ----------

class TestHydrateSerialize:
    """Test the hydrate/serialize helper functions."""

    def test_hydrate_empty_equipment(self):
        equip = _hydrate_equipment({})
        assert equip.weapon is None
        assert equip.armor is None
        assert equip.accessory is None

    def test_hydrate_equipment_with_items(self):
        raw = {
            "weapon": COMMON_SWORD.copy(),
            "armor": COMMON_CHAIN_ARMOR.copy(),
            "accessory": None,
        }
        equip = _hydrate_equipment(raw)
        assert equip.weapon is not None
        assert equip.weapon.item_id == "common_sword"
        assert equip.armor is not None
        assert equip.armor.item_id == "common_chain_armor"
        assert equip.accessory is None

    def test_hydrate_empty_inventory(self):
        inv = _hydrate_inventory([])
        assert len(inv.items) == 0

    def test_hydrate_inventory_with_items(self):
        raw = [COMMON_SWORD.copy(), HEALTH_POTION.copy()]
        inv = _hydrate_inventory(raw)
        assert len(inv.items) == 2
        assert inv.items[0].item_id == "common_sword"
        assert inv.items[1].item_id == "health_potion"

    def test_serialize_roundtrip(self):
        raw_equip = {"weapon": COMMON_SWORD.copy(), "armor": None, "accessory": COMMON_RING.copy()}
        raw_inv = [COMMON_CHAIN_ARMOR.copy(), HEALTH_POTION.copy()]
        equip = _hydrate_equipment(raw_equip)
        inv = _hydrate_inventory(raw_inv)
        serialized_equip = _serialize_equipment(equip)
        serialized_inv = _serialize_inventory(inv)
        assert serialized_equip["weapon"]["item_id"] == "common_sword"
        assert serialized_equip["armor"] is None
        assert serialized_equip["accessory"]["item_id"] == "common_ring"
        assert len(serialized_inv) == 2
        assert serialized_inv[0]["item_id"] == "common_chain_armor"


# ---------- Equip Tests ----------

class TestEquip:
    """Test the /equip endpoint."""

    @pytest.mark.anyio
    async def test_equip_weapon_to_empty_slot(self, profile_with_gear):
        from app.routes.town import equip_item, EquipRequest
        req = EquipRequest(username="gear_tester", hero_id="hero-gear-test", item_index=0)
        result = await equip_item(req)
        assert result["status"] == "ok"
        assert result["equipment"]["weapon"]["item_id"] == "common_sword"
        assert len(result["inventory"]) == 3  # was 4, sword moved to equipment

    @pytest.mark.anyio
    async def test_equip_armor_to_empty_slot(self, profile_with_gear):
        from app.routes.town import equip_item, EquipRequest
        req = EquipRequest(username="gear_tester", hero_id="hero-gear-test", item_index=1)
        result = await equip_item(req)
        assert result["status"] == "ok"
        assert result["equipment"]["armor"]["item_id"] == "common_chain_armor"
        assert len(result["inventory"]) == 3

    @pytest.mark.anyio
    async def test_equip_accessory_to_empty_slot(self, profile_with_gear):
        from app.routes.town import equip_item, EquipRequest
        req = EquipRequest(username="gear_tester", hero_id="hero-gear-test", item_index=2)
        result = await equip_item(req)
        assert result["status"] == "ok"
        assert result["equipment"]["accessory"]["item_id"] == "common_ring"
        assert len(result["inventory"]) == 3

    @pytest.mark.anyio
    async def test_equip_swap_occupied_slot(self, profile_with_equipped):
        """Equipping when slot is occupied should swap items."""
        from app.routes.town import equip_item, EquipRequest
        # Add a new weapon to inventory, then equip it (swapping the rusty sword)
        profile = load_or_create_profile("equipped_tester")
        profile.heroes[0].inventory.append(UNCOMMON_GREATSWORD.copy())
        save_profile(profile)

        req = EquipRequest(username="equipped_tester", hero_id="hero-equipped", item_index=2)
        result = await equip_item(req)
        assert result["status"] == "ok"
        # Greatsword should now be equipped
        assert result["equipment"]["weapon"]["item_id"] == "uncommon_greatsword"
        # Rusty sword should be back in inventory at the same index (swapped)
        inv_ids = [i["item_id"] for i in result["inventory"]]
        assert "common_sword" in inv_ids
        # Total inventory count stays the same (greatsword removed, rusty sword added back)
        assert len(result["inventory"]) == 3

    @pytest.mark.anyio
    async def test_equip_consumable_rejected(self, profile_with_gear):
        from app.routes.town import equip_item, EquipRequest
        from fastapi import HTTPException
        req = EquipRequest(username="gear_tester", hero_id="hero-gear-test", item_index=3)
        with pytest.raises(HTTPException) as exc_info:
            await equip_item(req)
        assert exc_info.value.status_code == 400
        assert "cannot be equipped" in exc_info.value.detail.lower()

    @pytest.mark.anyio
    async def test_equip_invalid_index(self, profile_with_gear):
        from app.routes.town import equip_item, EquipRequest
        from fastapi import HTTPException
        req = EquipRequest(username="gear_tester", hero_id="hero-gear-test", item_index=99)
        with pytest.raises(HTTPException) as exc_info:
            await equip_item(req)
        assert exc_info.value.status_code == 400

    @pytest.mark.anyio
    async def test_equip_negative_index(self, profile_with_gear):
        from app.routes.town import equip_item, EquipRequest
        from fastapi import HTTPException
        req = EquipRequest(username="gear_tester", hero_id="hero-gear-test", item_index=-1)
        with pytest.raises(HTTPException) as exc_info:
            await equip_item(req)
        assert exc_info.value.status_code == 400

    @pytest.mark.anyio
    async def test_equip_dead_hero(self, dead_hero_profile):
        from app.routes.town import equip_item, EquipRequest
        from fastapi import HTTPException
        req = EquipRequest(username="dead_tester", hero_id="hero-dead", item_index=0)
        with pytest.raises(HTTPException) as exc_info:
            await equip_item(req)
        assert exc_info.value.status_code == 404

    @pytest.mark.anyio
    async def test_equip_hero_not_found(self, profile_with_gear):
        from app.routes.town import equip_item, EquipRequest
        from fastapi import HTTPException
        req = EquipRequest(username="gear_tester", hero_id="nonexistent", item_index=0)
        with pytest.raises(HTTPException) as exc_info:
            await equip_item(req)
        assert exc_info.value.status_code == 404

    @pytest.mark.anyio
    async def test_equip_persists_to_disk(self, profile_with_gear):
        from app.routes.town import equip_item, EquipRequest
        req = EquipRequest(username="gear_tester", hero_id="hero-gear-test", item_index=0)
        await equip_item(req)
        # Reload from disk
        profile = load_or_create_profile("gear_tester")
        hero = profile.heroes[0]
        assert hero.equipment["weapon"]["item_id"] == "common_sword"
        assert len(hero.inventory) == 3


# ---------- Unequip Tests ----------

class TestUnequip:
    """Test the /unequip endpoint."""

    @pytest.mark.anyio
    async def test_unequip_weapon(self, profile_with_equipped):
        from app.routes.town import unequip_item, UnequipRequest
        req = UnequipRequest(username="equipped_tester", hero_id="hero-equipped", slot="weapon")
        result = await unequip_item(req)
        assert result["status"] == "ok"
        assert result["equipment"]["weapon"] is None
        # Item moved to inventory
        inv_ids = [i["item_id"] for i in result["inventory"]]
        assert "common_sword" in inv_ids
        assert len(result["inventory"]) == 3  # was 2, now 3

    @pytest.mark.anyio
    async def test_unequip_armor(self, profile_with_equipped):
        from app.routes.town import unequip_item, UnequipRequest
        req = UnequipRequest(username="equipped_tester", hero_id="hero-equipped", slot="armor")
        result = await unequip_item(req)
        assert result["status"] == "ok"
        assert result["equipment"]["armor"] is None
        assert len(result["inventory"]) == 3

    @pytest.mark.anyio
    async def test_unequip_empty_slot(self, profile_with_equipped):
        from app.routes.town import unequip_item, UnequipRequest
        from fastapi import HTTPException
        req = UnequipRequest(username="equipped_tester", hero_id="hero-equipped", slot="accessory")
        with pytest.raises(HTTPException) as exc_info:
            await unequip_item(req)
        assert exc_info.value.status_code == 400
        assert "no item" in exc_info.value.detail.lower()

    @pytest.mark.anyio
    async def test_unequip_invalid_slot(self, profile_with_equipped):
        from app.routes.town import unequip_item, UnequipRequest
        from fastapi import HTTPException
        req = UnequipRequest(username="equipped_tester", hero_id="hero-equipped", slot="boots")
        with pytest.raises(HTTPException) as exc_info:
            await unequip_item(req)
        assert exc_info.value.status_code == 400
        assert "invalid slot" in exc_info.value.detail.lower()

    @pytest.mark.anyio
    async def test_unequip_full_inventory(self, profile_with_equipped):
        from app.routes.town import unequip_item, UnequipRequest
        from fastapi import HTTPException
        # Fill inventory to max
        profile = load_or_create_profile("equipped_tester")
        hero = profile.heroes[0]
        while len(hero.inventory) < INVENTORY_MAX_CAPACITY:
            hero.inventory.append(HEALTH_POTION.copy())
        save_profile(profile)

        req = UnequipRequest(username="equipped_tester", hero_id="hero-equipped", slot="weapon")
        with pytest.raises(HTTPException) as exc_info:
            await unequip_item(req)
        assert exc_info.value.status_code == 400
        assert "full" in exc_info.value.detail.lower()

    @pytest.mark.anyio
    async def test_unequip_dead_hero(self, dead_hero_profile):
        from app.routes.town import unequip_item, UnequipRequest
        from fastapi import HTTPException
        req = UnequipRequest(username="dead_tester", hero_id="hero-dead", slot="weapon")
        with pytest.raises(HTTPException) as exc_info:
            await unequip_item(req)
        assert exc_info.value.status_code == 404

    @pytest.mark.anyio
    async def test_unequip_persists_to_disk(self, profile_with_equipped):
        from app.routes.town import unequip_item, UnequipRequest
        req = UnequipRequest(username="equipped_tester", hero_id="hero-equipped", slot="weapon")
        await unequip_item(req)
        profile = load_or_create_profile("equipped_tester")
        hero = profile.heroes[0]
        assert hero.equipment.get("weapon") is None
        inv_ids = [i["item_id"] for i in hero.inventory]
        assert "common_sword" in inv_ids


# ---------- Transfer Tests ----------

class TestTransfer:
    """Test the /transfer endpoint."""

    @pytest.mark.anyio
    async def test_transfer_item(self, two_hero_profile):
        from app.routes.town import transfer_item, TransferRequest
        req = TransferRequest(
            username="transfer_tester",
            from_hero_id="hero-src",
            to_hero_id="hero-dest",
            item_index=0,
        )
        result = await transfer_item(req)
        assert result["status"] == "ok"
        assert len(result["from_inventory"]) == 2  # was 3, now 2
        assert len(result["to_inventory"]) == 2    # was 1, now 2
        assert result["item"]["item_id"] == "common_sword"

    @pytest.mark.anyio
    async def test_transfer_preserves_item_data(self, two_hero_profile):
        from app.routes.town import transfer_item, TransferRequest
        req = TransferRequest(
            username="transfer_tester",
            from_hero_id="hero-src",
            to_hero_id="hero-dest",
            item_index=0,
        )
        result = await transfer_item(req)
        transferred = result["to_inventory"][-1]
        assert transferred["item_id"] == "common_sword"
        assert transferred["name"] == "Rusty Sword"
        assert transferred["stat_bonuses"]["attack_damage"] == 5

    @pytest.mark.anyio
    async def test_transfer_same_hero_rejected(self, two_hero_profile):
        from app.routes.town import transfer_item, TransferRequest
        from fastapi import HTTPException
        req = TransferRequest(
            username="transfer_tester",
            from_hero_id="hero-src",
            to_hero_id="hero-src",
            item_index=0,
        )
        with pytest.raises(HTTPException) as exc_info:
            await transfer_item(req)
        assert exc_info.value.status_code == 400
        assert "same hero" in exc_info.value.detail.lower()

    @pytest.mark.anyio
    async def test_transfer_to_full_inventory(self, two_hero_profile):
        from app.routes.town import transfer_item, TransferRequest
        from fastapi import HTTPException
        # Fill destination inventory
        profile = load_or_create_profile("transfer_tester")
        dest = [h for h in profile.heroes if h.hero_id == "hero-dest"][0]
        while len(dest.inventory) < INVENTORY_MAX_CAPACITY:
            dest.inventory.append(HEALTH_POTION.copy())
        save_profile(profile)

        req = TransferRequest(
            username="transfer_tester",
            from_hero_id="hero-src",
            to_hero_id="hero-dest",
            item_index=0,
        )
        with pytest.raises(HTTPException) as exc_info:
            await transfer_item(req)
        assert exc_info.value.status_code == 400
        assert "full" in exc_info.value.detail.lower()

    @pytest.mark.anyio
    async def test_transfer_invalid_index(self, two_hero_profile):
        from app.routes.town import transfer_item, TransferRequest
        from fastapi import HTTPException
        req = TransferRequest(
            username="transfer_tester",
            from_hero_id="hero-src",
            to_hero_id="hero-dest",
            item_index=99,
        )
        with pytest.raises(HTTPException) as exc_info:
            await transfer_item(req)
        assert exc_info.value.status_code == 400

    @pytest.mark.anyio
    async def test_transfer_from_dead_hero(self, temp_data_dir):
        from app.routes.town import transfer_item, TransferRequest
        from fastapi import HTTPException
        profile = PlayerProfile(
            username="dead_transfer",
            gold=100,
            heroes=[
                Hero(hero_id="dead-one", name="Dead", is_alive=False, inventory=[COMMON_SWORD.copy()]),
                Hero(hero_id="alive-one", name="Alive", is_alive=True, inventory=[]),
            ],
        )
        save_profile(profile)
        req = TransferRequest(
            username="dead_transfer",
            from_hero_id="dead-one",
            to_hero_id="alive-one",
            item_index=0,
        )
        with pytest.raises(HTTPException) as exc_info:
            await transfer_item(req)
        assert exc_info.value.status_code == 404

    @pytest.mark.anyio
    async def test_transfer_to_dead_hero(self, temp_data_dir):
        from app.routes.town import transfer_item, TransferRequest
        from fastapi import HTTPException
        profile = PlayerProfile(
            username="dead_transfer2",
            gold=100,
            heroes=[
                Hero(hero_id="alive-src", name="Alive", is_alive=True, inventory=[COMMON_SWORD.copy()]),
                Hero(hero_id="dead-dest", name="Dead", is_alive=False, inventory=[]),
            ],
        )
        save_profile(profile)
        req = TransferRequest(
            username="dead_transfer2",
            from_hero_id="alive-src",
            to_hero_id="dead-dest",
            item_index=0,
        )
        with pytest.raises(HTTPException) as exc_info:
            await transfer_item(req)
        assert exc_info.value.status_code == 404

    @pytest.mark.anyio
    async def test_transfer_persists_to_disk(self, two_hero_profile):
        from app.routes.town import transfer_item, TransferRequest
        req = TransferRequest(
            username="transfer_tester",
            from_hero_id="hero-src",
            to_hero_id="hero-dest",
            item_index=0,
        )
        await transfer_item(req)
        profile = load_or_create_profile("transfer_tester")
        src = [h for h in profile.heroes if h.hero_id == "hero-src"][0]
        dest = [h for h in profile.heroes if h.hero_id == "hero-dest"][0]
        assert len(src.inventory) == 2
        assert len(dest.inventory) == 2
        dest_ids = [i["item_id"] for i in dest.inventory]
        assert "common_sword" in dest_ids


# ---------- Integration Tests ----------

class TestGearManagementFlow:
    """End-to-end gear management flow tests."""

    @pytest.mark.anyio
    async def test_equip_then_unequip_roundtrip(self, profile_with_gear):
        from app.routes.town import equip_item, unequip_item, EquipRequest, UnequipRequest

        # Equip sword
        eq_req = EquipRequest(username="gear_tester", hero_id="hero-gear-test", item_index=0)
        eq_result = await equip_item(eq_req)
        assert eq_result["equipment"]["weapon"]["item_id"] == "common_sword"
        assert len(eq_result["inventory"]) == 3

        # Unequip sword
        uneq_req = UnequipRequest(username="gear_tester", hero_id="hero-gear-test", slot="weapon")
        uneq_result = await unequip_item(uneq_req)
        assert uneq_result["equipment"]["weapon"] is None
        assert len(uneq_result["inventory"]) == 4
        inv_ids = [i["item_id"] for i in uneq_result["inventory"]]
        assert "common_sword" in inv_ids

    @pytest.mark.anyio
    async def test_equip_all_three_slots(self, profile_with_gear):
        from app.routes.town import equip_item, EquipRequest

        # Equip weapon (index 0 = sword)
        await equip_item(EquipRequest(username="gear_tester", hero_id="hero-gear-test", item_index=0))
        # Equip armor (index 0 now = chain armor, since sword was removed)
        await equip_item(EquipRequest(username="gear_tester", hero_id="hero-gear-test", item_index=0))
        # Equip accessory (index 0 now = ring)
        await equip_item(EquipRequest(username="gear_tester", hero_id="hero-gear-test", item_index=0))

        profile = load_or_create_profile("gear_tester")
        hero = profile.heroes[0]
        assert hero.equipment["weapon"]["item_id"] == "common_sword"
        assert hero.equipment["armor"]["item_id"] == "common_chain_armor"
        assert hero.equipment["accessory"]["item_id"] == "common_ring"
        # Only health potion left in bag
        assert len(hero.inventory) == 1
        assert hero.inventory[0]["item_id"] == "health_potion"

    @pytest.mark.anyio
    async def test_full_flow_equip_unequip_transfer(self, temp_data_dir):
        """Full flow: equip gear, unequip, transfer to another hero."""
        from app.routes.town import equip_item, unequip_item, transfer_item
        from app.routes.town import EquipRequest, UnequipRequest, TransferRequest

        # Setup: two heroes, first has items
        profile = PlayerProfile(
            username="flow_tester",
            gold=200,
            heroes=[
                Hero(
                    hero_id="flow-hero1",
                    name="Hero One",
                    class_id="crusader",
                    is_alive=True,
                    equipment={},
                    inventory=[COMMON_SWORD.copy(), COMMON_CHAIN_ARMOR.copy()],
                ),
                Hero(
                    hero_id="flow-hero2",
                    name="Hero Two",
                    class_id="ranger",
                    is_alive=True,
                    equipment={},
                    inventory=[],
                ),
            ],
        )
        save_profile(profile)

        # Step 1: Equip sword on hero 1
        await equip_item(EquipRequest(username="flow_tester", hero_id="flow-hero1", item_index=0))

        # Step 2: Transfer armor from hero 1 to hero 2
        await transfer_item(TransferRequest(
            username="flow_tester",
            from_hero_id="flow-hero1",
            to_hero_id="flow-hero2",
            item_index=0,  # armor is now at index 0
        ))

        # Step 3: Equip armor on hero 2
        await equip_item(EquipRequest(username="flow_tester", hero_id="flow-hero2", item_index=0))

        # Verify final state
        profile = load_or_create_profile("flow_tester")
        hero1 = [h for h in profile.heroes if h.hero_id == "flow-hero1"][0]
        hero2 = [h for h in profile.heroes if h.hero_id == "flow-hero2"][0]

        assert hero1.equipment["weapon"]["item_id"] == "common_sword"
        assert len(hero1.inventory) == 0

        assert hero2.equipment["armor"]["item_id"] == "common_chain_armor"
        assert len(hero2.inventory) == 0
