"""
Town Routes - Profile management, tavern (hero hiring), roster, merchant,
and gear management (equip/unequip/transfer), and bank (account-wide item storage).

Phase 4E-1: REST API for the Town Hub. All endpoints are stateless
and operate on JSON-persisted player profiles.
Phase 5 Feature 6: Merchant buy/sell system added.
Phase 5 Feature 7: Town gear management (equip/unequip/transfer between heroes).
Phase 5 Feature 8: Shared bank / stash system (deposit/withdraw items).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.profile import (
    HERO_ROSTER_MAX,
    BANK_MAX_CAPACITY,
    PlayerProfile,
    generate_tavern_heroes,
    get_tavern_pool_size,
)
from app.models.player import load_classes_config
from app.models.items import INVENTORY_MAX_CAPACITY, Equipment, Inventory, Item, EquipSlot
from app.core.loot import create_item, load_items_config
from app.services.persistence import load_or_create_profile, save_profile

router = APIRouter()

# ---------- Merchant Config ----------

_merchant_config_path = Path(__file__).resolve().parent.parent.parent / "configs" / "merchant_config.json"
_merchant_cache: dict | None = None


def _load_merchant_config() -> dict:
    """Load merchant stock config. Caches after first load."""
    global _merchant_cache
    if _merchant_cache is not None:
        return _merchant_cache

    if _merchant_config_path.exists():
        with open(_merchant_config_path, "r") as f:
            _merchant_cache = json.load(f)
    else:
        _merchant_cache = {"merchant_stock": [], "sell_multiplier": 1.0}
    return _merchant_cache


def clear_merchant_cache() -> None:
    """Clear the merchant config cache. Useful for testing."""
    global _merchant_cache
    _merchant_cache = None

# ---------- Config Loaders ----------

_names_config_path = Path(__file__).resolve().parent.parent.parent / "configs" / "names_config.json"
_names_cache: dict | None = None


def _load_names_config() -> dict:
    """Load name lists from names_config.json. Caches after first load."""
    global _names_cache
    if _names_cache is not None:
        return _names_cache

    if _names_config_path.exists():
        with open(_names_config_path, "r") as f:
            _names_cache = json.load(f)
    else:
        _names_cache = {}
    return _names_cache


def _get_classes_dict() -> dict:
    """Get classes config as raw dicts for hero generation."""
    classes = load_classes_config()
    return {
        cid: {
            "base_hp": c.base_hp,
            "base_melee_damage": c.base_melee_damage,
            "base_ranged_damage": c.base_ranged_damage,
            "base_armor": c.base_armor,
            "base_vision_range": c.base_vision_range,
            "ranged_range": c.ranged_range,
        }
        for cid, c in classes.items()
    }


def _hero_to_dict(hero) -> dict:
    """Convert a Hero model to a JSON-safe dict for API responses."""
    return hero.model_dump(mode="json")


def _profile_summary(profile: PlayerProfile) -> dict:
    """Return a lightweight profile summary for the client."""
    return {
        "username": profile.username,
        "gold": profile.gold,
        "hero_count": len([h for h in profile.heroes if h.is_alive]),
        "total_heroes": len(profile.heroes),
    }


# ---------- Profile ----------

@router.get("/profile")
async def get_profile(username: str):
    """Load or create a player profile. Auto-creates on first access.

    Query params:
        username: Player's username
    """
    if not username or not username.strip():
        raise HTTPException(status_code=400, detail="Username is required")

    profile = load_or_create_profile(username.strip())
    return {
        "profile": _profile_summary(profile),
        "heroes": [_hero_to_dict(h) for h in profile.heroes],
        "bank": profile.bank or [],
    }


# ---------- Tavern ----------

@router.get("/tavern")
async def get_tavern(username: str):
    """Get the tavern's available heroes. Generates a pool if empty.

    Query params:
        username: Player's username
    """
    if not username or not username.strip():
        raise HTTPException(status_code=400, detail="Username is required")

    profile = load_or_create_profile(username.strip())

    classes_dict = _get_classes_dict()
    current_class_count = len(classes_dict)

    # Regenerate tavern pool if empty or stale (new classes added since pool was generated)
    if not profile.tavern_pool or profile.tavern_class_count < current_class_count:
        existing_names = {h.name for h in profile.heroes}
        names_config = _load_names_config()
        pool_size = get_tavern_pool_size(classes_dict)
        profile.tavern_pool = generate_tavern_heroes(
            classes_dict, names_config, pool_size, existing_names
        )
        profile.tavern_class_count = current_class_count
        save_profile(profile)

    return {
        "gold": profile.gold,
        "heroes": [_hero_to_dict(h) for h in profile.tavern_pool],
    }


class HireRequest(BaseModel):
    username: str
    hero_id: str


@router.post("/hire")
async def hire_hero(request: HireRequest):
    """Hire a hero from the tavern. Deducts gold, adds to roster.

    Body:
        username: Player's username
        hero_id: ID of the hero to hire (from tavern pool)
    """
    if not request.username or not request.username.strip():
        raise HTTPException(status_code=400, detail="Username is required")

    profile = load_or_create_profile(request.username.strip())

    # Find hero in tavern pool
    hero = None
    hero_index = -1
    for i, h in enumerate(profile.tavern_pool):
        if h.hero_id == request.hero_id:
            hero = h
            hero_index = i
            break

    if hero is None:
        raise HTTPException(status_code=404, detail="Hero not found in tavern")

    # Check roster capacity
    alive_heroes = [h for h in profile.heroes if h.is_alive]
    if len(alive_heroes) >= HERO_ROSTER_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Hero roster is full (max {HERO_ROSTER_MAX})"
        )

    # Check gold
    if profile.gold < hero.hire_cost:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient gold. Need {hero.hire_cost}, have {profile.gold}"
        )

    # Hire: deduct gold, move from tavern to roster
    profile.gold -= hero.hire_cost
    profile.heroes.append(hero)
    profile.tavern_pool.pop(hero_index)
    save_profile(profile)

    return {
        "status": "ok",
        "gold": profile.gold,
        "hero": _hero_to_dict(hero),
        "message": f"Hired {hero.name} for {hero.hire_cost} gold",
    }


# ---------- Roster ----------

@router.get("/roster")
async def get_roster(username: str):
    """Get all owned heroes with stats and gear.

    Query params:
        username: Player's username
    """
    if not username or not username.strip():
        raise HTTPException(status_code=400, detail="Username is required")

    profile = load_or_create_profile(username.strip())
    return {
        "gold": profile.gold,
        "heroes": [_hero_to_dict(h) for h in profile.heroes],
    }


# ---------- Dismiss Hero ----------

class DismissRequest(BaseModel):
    username: str
    hero_id: str


@router.post("/dismiss")
async def dismiss_hero(request: DismissRequest):
    """Permanently dismiss (remove) a hero from the player's roster.

    Any equipped items and inventory are lost. This action cannot be undone.

    Body:
        username: Player's username
        hero_id: ID of the hero to dismiss
    """
    if not request.username or not request.username.strip():
        raise HTTPException(status_code=400, detail="Username is required")
    if not request.hero_id:
        raise HTTPException(status_code=400, detail="Hero ID is required")

    profile = load_or_create_profile(request.username.strip())

    hero = None
    for h in profile.heroes:
        if h.hero_id == request.hero_id:
            hero = h
            break

    if not hero:
        raise HTTPException(status_code=404, detail="Hero not found")

    profile.heroes = [h for h in profile.heroes if h.hero_id != request.hero_id]
    save_profile(profile)

    return {
        "message": f"{hero.name} has been dismissed.",
        "hero_id": request.hero_id,
        "heroes": [_hero_to_dict(h) for h in profile.heroes],
    }


# ---------- Tavern Refresh ----------

class RefreshRequest(BaseModel):
    username: str


@router.post("/tavern/refresh")
async def refresh_tavern(request: RefreshRequest):
    """Refresh the tavern pool with new heroes.

    Body:
        username: Player's username
    """
    if not request.username or not request.username.strip():
        raise HTTPException(status_code=400, detail="Username is required")

    profile = load_or_create_profile(request.username.strip())

    # Generate new tavern pool
    existing_names = {h.name for h in profile.heroes}
    classes_dict = _get_classes_dict()
    names_config = _load_names_config()
    pool_size = get_tavern_pool_size(classes_dict)
    profile.tavern_pool = generate_tavern_heroes(
        classes_dict, names_config, pool_size, existing_names
    )
    profile.tavern_class_count = len(classes_dict)
    save_profile(profile)

    return {
        "gold": profile.gold,
        "heroes": [_hero_to_dict(h) for h in profile.tavern_pool],
    }


# ---------- Merchant ----------

@router.get("/merchant/stock")
async def get_merchant_stock():
    """Get the merchant's available stock with buy prices.

    Each stock entry includes the full item definition (from items_config)
    plus the buy_price and category from merchant_config.
    """
    merchant_config = _load_merchant_config()
    items_config = load_items_config()
    stock = []

    for entry in merchant_config.get("merchant_stock", []):
        item_id = entry["item_id"]
        item_def = items_config.get(item_id)
        if item_def is None:
            continue  # Skip items not in items_config

        stock.append({
            "item_id": item_id,
            "name": item_def.get("name", item_id),
            "item_type": item_def.get("item_type", "consumable"),
            "rarity": item_def.get("rarity", "common"),
            "equip_slot": item_def.get("equip_slot"),
            "stat_bonuses": item_def.get("stat_bonuses", {}),
            "consumable_effect": item_def.get("consumable_effect"),
            "description": item_def.get("description", ""),
            "sell_value": item_def.get("sell_value", 0),
            "buy_price": entry["buy_price"],
            "category": entry.get("category", "misc"),
        })

    return {"stock": stock}


class BuyRequest(BaseModel):
    username: str
    hero_id: str
    item_id: str


@router.post("/merchant/buy")
async def merchant_buy(request: BuyRequest):
    """Buy an item from the merchant and add it to a hero's inventory.

    Validates:
    - Username and hero exist
    - Hero is alive
    - Item is in merchant stock
    - Player has enough gold
    - Hero inventory is not full

    Body:
        username: Player's username
        hero_id: ID of the hero to receive the item
        item_id: ID of the item to buy
    """
    if not request.username or not request.username.strip():
        raise HTTPException(status_code=400, detail="Username is required")

    profile = load_or_create_profile(request.username.strip())

    # Find the hero
    hero = None
    for h in profile.heroes:
        if h.hero_id == request.hero_id and h.is_alive:
            hero = h
            break

    if hero is None:
        raise HTTPException(status_code=404, detail="Hero not found or is dead")

    # Check hero inventory capacity
    current_inv_count = len(hero.inventory) if hero.inventory else 0
    if current_inv_count >= INVENTORY_MAX_CAPACITY:
        raise HTTPException(
            status_code=400,
            detail=f"Hero inventory is full ({INVENTORY_MAX_CAPACITY}/{INVENTORY_MAX_CAPACITY})"
        )

    # Find item in merchant stock
    merchant_config = _load_merchant_config()
    stock_entry = None
    for entry in merchant_config.get("merchant_stock", []):
        if entry["item_id"] == request.item_id:
            stock_entry = entry
            break

    if stock_entry is None:
        raise HTTPException(status_code=404, detail="Item not available from merchant")

    buy_price = stock_entry["buy_price"]

    # Check gold
    if profile.gold < buy_price:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient gold. Need {buy_price}g, have {profile.gold}g"
        )

    # Create the item instance
    item = create_item(request.item_id)
    if item is None:
        raise HTTPException(status_code=500, detail="Failed to create item from config")

    # Transaction: deduct gold, add item to hero inventory
    profile.gold -= buy_price
    item_dict = item.model_dump(mode="json")
    if hero.inventory is None:
        hero.inventory = []
    hero.inventory.append(item_dict)
    save_profile(profile)

    return {
        "status": "ok",
        "gold": profile.gold,
        "item": item_dict,
        "hero_id": hero.hero_id,
        "message": f"Bought {item.name} for {buy_price}g",
    }


class SellRequest(BaseModel):
    username: str
    hero_id: str
    item_index: int  # Index in the hero's inventory list


@router.post("/merchant/sell")
async def merchant_sell(request: SellRequest):
    """Sell an item from a hero's inventory to the merchant.

    Uses the item's sell_value from items_config.json (modified by
    the merchant's sell_multiplier). Equipment items cannot be sold
    while equipped — must be in inventory.

    Validates:
    - Username and hero exist
    - Hero is alive
    - Item index is valid
    - Item is in inventory (not equipped)

    Body:
        username: Player's username
        hero_id: ID of the hero selling the item
        item_index: Index of the item in the hero's inventory
    """
    if not request.username or not request.username.strip():
        raise HTTPException(status_code=400, detail="Username is required")

    profile = load_or_create_profile(request.username.strip())

    # Find the hero
    hero = None
    for h in profile.heroes:
        if h.hero_id == request.hero_id and h.is_alive:
            hero = h
            break

    if hero is None:
        raise HTTPException(status_code=404, detail="Hero not found or is dead")

    # Validate item index
    inv = hero.inventory or []
    if request.item_index < 0 or request.item_index >= len(inv):
        raise HTTPException(status_code=400, detail="Invalid item index")

    # Get the item data
    item_data = inv[request.item_index]
    sell_value = item_data.get("sell_value", 0)

    # Apply sell multiplier
    merchant_config = _load_merchant_config()
    multiplier = merchant_config.get("sell_multiplier", 1.0)
    sell_price = max(1, int(sell_value * multiplier))  # Minimum 1g

    # Transaction: remove item, add gold
    hero.inventory.pop(request.item_index)
    profile.gold += sell_price
    save_profile(profile)

    return {
        "status": "ok",
        "gold": profile.gold,
        "sold_item": item_data,
        "sell_price": sell_price,
        "hero_id": hero.hero_id,
        "message": f"Sold {item_data.get('name', 'item')} for {sell_price}g",
    }


# ---------- Gear Management Helpers ----------

def _hydrate_equipment(raw: dict) -> Equipment:
    """Convert a hero's raw equipment dict into a typed Equipment model."""
    equip = Equipment()
    for slot_name in ("weapon", "armor", "accessory"):
        item_data = raw.get(slot_name)
        if item_data and isinstance(item_data, dict) and item_data.get("item_id"):
            equip.set_slot(EquipSlot(slot_name), Item(**item_data))
    return equip


def _hydrate_inventory(raw: list) -> Inventory:
    """Convert a hero's raw inventory list into a typed Inventory model."""
    inv = Inventory()
    for item_data in (raw or []):
        if isinstance(item_data, dict) and item_data.get("item_id"):
            inv.items.append(Item(**item_data))
    return inv


def _serialize_equipment(equip: Equipment) -> dict:
    """Serialize an Equipment model back to a raw dict for persistence."""
    result = {}
    for slot_name in ("weapon", "armor", "accessory"):
        item = equip.get_slot(EquipSlot(slot_name))
        result[slot_name] = item.model_dump(mode="json") if item else None
    return result


def _serialize_inventory(inv: Inventory) -> list:
    """Serialize an Inventory model back to a raw list for persistence."""
    return [item.model_dump(mode="json") for item in inv.items]


# ---------- Gear Management Endpoints ----------

class EquipRequest(BaseModel):
    username: str
    hero_id: str
    item_index: int  # Index in the hero's inventory list


@router.post("/equip")
async def equip_item(request: EquipRequest):
    """Equip an item from a hero's inventory to the appropriate equipment slot.

    If the target slot already has an item, the old item is swapped back
    into the inventory. Only equippable items (weapon/armor/accessory) can
    be equipped — consumables are rejected.

    Validates:
    - Username and hero exist
    - Hero is alive
    - Item index is valid
    - Item is equippable (has equip_slot)

    Body:
        username: Player's username
        hero_id: ID of the hero
        item_index: Index of the item in the hero's inventory to equip
    """
    if not request.username or not request.username.strip():
        raise HTTPException(status_code=400, detail="Username is required")

    profile = load_or_create_profile(request.username.strip())

    # Find the hero
    hero = None
    for h in profile.heroes:
        if h.hero_id == request.hero_id and h.is_alive:
            hero = h
            break

    if hero is None:
        raise HTTPException(status_code=404, detail="Hero not found or is dead")

    # Validate item index
    inv_raw = hero.inventory or []
    if request.item_index < 0 or request.item_index >= len(inv_raw):
        raise HTTPException(status_code=400, detail="Invalid item index")

    # Check that the item is equippable
    item_data = inv_raw[request.item_index]
    if not item_data.get("equip_slot"):
        raise HTTPException(status_code=400, detail="Item cannot be equipped (no equip slot)")

    # Phase 16: Weapon class-lock — reject weapons incompatible with hero's class
    if item_data.get("equip_slot") == "weapon" and hero.class_id:
        weapon_cat = item_data.get("weapon_category", "")
        if weapon_cat:
            from app.models.player import get_class_definition
            class_def = get_class_definition(hero.class_id)
            if class_def and class_def.allowed_weapon_categories:
                if weapon_cat not in class_def.allowed_weapon_categories:
                    raise HTTPException(
                        status_code=400,
                        detail=f"This class cannot equip {weapon_cat} weapons"
                    )

    # Hydrate into typed models
    equipment = _hydrate_equipment(hero.equipment or {})
    inventory = _hydrate_inventory(inv_raw)

    # Remove the item from inventory
    item_to_equip = inventory.items.pop(request.item_index)

    # Equip it (returns previously equipped item, if any)
    previous = equipment.equip(item_to_equip)

    # If there was a previously equipped item, put it back in inventory
    if previous is not None:
        inventory.items.insert(request.item_index, previous)

    # Serialize back to raw dicts and save
    hero.equipment = _serialize_equipment(equipment)
    hero.inventory = _serialize_inventory(inventory)
    save_profile(profile)

    return {
        "status": "ok",
        "hero_id": hero.hero_id,
        "equipment": hero.equipment,
        "inventory": hero.inventory,
        "message": f"Equipped {item_to_equip.name}",
    }


class UnequipRequest(BaseModel):
    username: str
    hero_id: str
    slot: str  # "weapon", "armor", or "accessory"


@router.post("/unequip")
async def unequip_item(request: UnequipRequest):
    """Unequip an item from a hero's equipment slot and place it in their inventory.

    Fails if the hero's inventory is full (10/10).

    Validates:
    - Username and hero exist
    - Hero is alive
    - Slot is valid
    - Slot has an item equipped
    - Inventory is not full

    Body:
        username: Player's username
        hero_id: ID of the hero
        slot: Equipment slot to unequip ("weapon", "armor", or "accessory")
    """
    if not request.username or not request.username.strip():
        raise HTTPException(status_code=400, detail="Username is required")

    # Validate slot name
    valid_slots = ("weapon", "armor", "accessory")
    if request.slot not in valid_slots:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid slot. Must be one of: {', '.join(valid_slots)}"
        )

    profile = load_or_create_profile(request.username.strip())

    # Find the hero
    hero = None
    for h in profile.heroes:
        if h.hero_id == request.hero_id and h.is_alive:
            hero = h
            break

    if hero is None:
        raise HTTPException(status_code=404, detail="Hero not found or is dead")

    # Check inventory capacity
    inv_raw = hero.inventory or []
    if len(inv_raw) >= INVENTORY_MAX_CAPACITY:
        raise HTTPException(
            status_code=400,
            detail=f"Inventory is full ({INVENTORY_MAX_CAPACITY}/{INVENTORY_MAX_CAPACITY}). "
                   "Sell or transfer items first."
        )

    # Hydrate models
    equipment = _hydrate_equipment(hero.equipment or {})
    inventory = _hydrate_inventory(inv_raw)

    # Unequip
    slot_enum = EquipSlot(request.slot)
    removed = equipment.unequip(slot_enum)
    if removed is None:
        raise HTTPException(status_code=400, detail=f"No item equipped in {request.slot} slot")

    # Add to inventory
    inventory.items.append(removed)

    # Serialize and save
    hero.equipment = _serialize_equipment(equipment)
    hero.inventory = _serialize_inventory(inventory)
    save_profile(profile)

    return {
        "status": "ok",
        "hero_id": hero.hero_id,
        "equipment": hero.equipment,
        "inventory": hero.inventory,
        "message": f"Unequipped {removed.name}",
    }


class TransferRequest(BaseModel):
    username: str
    from_hero_id: str
    to_hero_id: str
    item_index: int  # Index in the source hero's inventory


@router.post("/transfer")
async def transfer_item(request: TransferRequest):
    """Transfer an item from one hero's inventory to another's.

    The item must be in the source hero's bag (not equipped). The
    destination hero must have free inventory space.

    Validates:
    - Username exists
    - Both heroes exist and are alive
    - Heroes are different
    - Item index is valid
    - Destination hero has free inventory space

    Body:
        username: Player's username
        from_hero_id: ID of the hero giving the item
        to_hero_id: ID of the hero receiving the item
        item_index: Index of the item in the source hero's inventory
    """
    if not request.username or not request.username.strip():
        raise HTTPException(status_code=400, detail="Username is required")

    if request.from_hero_id == request.to_hero_id:
        raise HTTPException(status_code=400, detail="Cannot transfer to the same hero")

    profile = load_or_create_profile(request.username.strip())

    # Find both heroes
    from_hero = None
    to_hero = None
    for h in profile.heroes:
        if h.hero_id == request.from_hero_id and h.is_alive:
            from_hero = h
        if h.hero_id == request.to_hero_id and h.is_alive:
            to_hero = h

    if from_hero is None:
        raise HTTPException(status_code=404, detail="Source hero not found or is dead")
    if to_hero is None:
        raise HTTPException(status_code=404, detail="Destination hero not found or is dead")

    # Validate item index on source
    from_inv = from_hero.inventory or []
    if request.item_index < 0 or request.item_index >= len(from_inv):
        raise HTTPException(status_code=400, detail="Invalid item index")

    # Check destination capacity
    to_inv = to_hero.inventory or []
    if len(to_inv) >= INVENTORY_MAX_CAPACITY:
        raise HTTPException(
            status_code=400,
            detail=f"{to_hero.name}'s inventory is full ({INVENTORY_MAX_CAPACITY}/{INVENTORY_MAX_CAPACITY})"
        )

    # Transfer the item
    item_data = from_hero.inventory.pop(request.item_index)
    if to_hero.inventory is None:
        to_hero.inventory = []
    to_hero.inventory.append(item_data)
    save_profile(profile)

    return {
        "status": "ok",
        "from_hero_id": from_hero.hero_id,
        "to_hero_id": to_hero.hero_id,
        "from_inventory": from_hero.inventory,
        "to_inventory": to_hero.inventory,
        "item": item_data,
        "message": f"Transferred {item_data.get('name', 'item')} from {from_hero.name} to {to_hero.name}",
    }


# ---------- Bank (Shared Stash) ----------

@router.get("/bank")
async def get_bank(username: str):
    """Get the player's bank contents and capacity.

    Query params:
        username: Player's username
    """
    if not username or not username.strip():
        raise HTTPException(status_code=400, detail="Username is required")

    profile = load_or_create_profile(username.strip())
    return {
        "bank": profile.bank or [],
        "capacity": BANK_MAX_CAPACITY,
        "used": len(profile.bank or []),
    }


class DepositRequest(BaseModel):
    username: str
    hero_id: str
    item_index: int  # Index in the hero's inventory list


@router.post("/bank/deposit")
async def bank_deposit(request: DepositRequest):
    """Deposit an item from a hero's inventory into the account-wide bank.

    Items in the bank persist across hero deaths (permadeath protection).
    Heroes must unequip items before depositing — only bag items can
    be deposited.

    Validates:
    - Username exists
    - Hero exists and is alive
    - Item index is valid
    - Bank is not full (20/20)

    Body:
        username: Player's username
        hero_id: ID of the hero depositing the item
        item_index: Index of the item in the hero's inventory
    """
    if not request.username or not request.username.strip():
        raise HTTPException(status_code=400, detail="Username is required")

    profile = load_or_create_profile(request.username.strip())

    # Find the hero
    hero = None
    for h in profile.heroes:
        if h.hero_id == request.hero_id and h.is_alive:
            hero = h
            break

    if hero is None:
        raise HTTPException(status_code=404, detail="Hero not found or is dead")

    # Validate item index
    inv = hero.inventory or []
    if request.item_index < 0 or request.item_index >= len(inv):
        raise HTTPException(status_code=400, detail="Invalid item index")

    # Check bank capacity
    bank = profile.bank or []
    if len(bank) >= BANK_MAX_CAPACITY:
        raise HTTPException(
            status_code=400,
            detail=f"Bank is full ({BANK_MAX_CAPACITY}/{BANK_MAX_CAPACITY})"
        )

    # Transfer: remove from hero inventory, add to bank
    item_data = hero.inventory.pop(request.item_index)
    if profile.bank is None:
        profile.bank = []
    profile.bank.append(item_data)
    save_profile(profile)

    return {
        "status": "ok",
        "hero_id": hero.hero_id,
        "inventory": hero.inventory,
        "bank": profile.bank,
        "item": item_data,
        "message": f"Deposited {item_data.get('name', 'item')} into the bank",
    }


class WithdrawRequest(BaseModel):
    username: str
    hero_id: str
    bank_index: int  # Index in the bank list


@router.post("/bank/withdraw")
async def bank_withdraw(request: WithdrawRequest):
    """Withdraw an item from the bank into a hero's inventory.

    Validates:
    - Username exists
    - Hero exists and is alive
    - Bank index is valid
    - Hero's inventory is not full (10/10)

    Body:
        username: Player's username
        hero_id: ID of the hero receiving the item
        bank_index: Index of the item in the bank
    """
    if not request.username or not request.username.strip():
        raise HTTPException(status_code=400, detail="Username is required")

    profile = load_or_create_profile(request.username.strip())

    # Find the hero
    hero = None
    for h in profile.heroes:
        if h.hero_id == request.hero_id and h.is_alive:
            hero = h
            break

    if hero is None:
        raise HTTPException(status_code=404, detail="Hero not found or is dead")

    # Validate bank index
    bank = profile.bank or []
    if request.bank_index < 0 or request.bank_index >= len(bank):
        raise HTTPException(status_code=400, detail="Invalid bank index")

    # Check hero inventory capacity
    inv = hero.inventory or []
    if len(inv) >= INVENTORY_MAX_CAPACITY:
        raise HTTPException(
            status_code=400,
            detail=f"Hero inventory is full ({INVENTORY_MAX_CAPACITY}/{INVENTORY_MAX_CAPACITY}). "
                   "Sell or transfer items first."
        )

    # Transfer: remove from bank, add to hero inventory
    item_data = profile.bank.pop(request.bank_index)
    if hero.inventory is None:
        hero.inventory = []
    hero.inventory.append(item_data)
    save_profile(profile)

    return {
        "status": "ok",
        "hero_id": hero.hero_id,
        "inventory": hero.inventory,
        "bank": profile.bank,
        "item": item_data,
        "message": f"Withdrew {item_data.get('name', 'item')} from the bank",
    }
