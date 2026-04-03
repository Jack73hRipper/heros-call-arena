"""
Pydantic models for persistent player profiles and heroes.

Phase 4E-1: Data models for the Town system — hero hiring, roster management,
and JSON-based persistence. No match integration (that's 4E-2).
Phase 4E-4: Hiring Hall overhaul — removed stat variation, heroes now come with
random starting gear that increases hire cost. Class identity shown on cards.
"""

from __future__ import annotations

import random
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.items import Equipment, Inventory


# ---------- Constants ----------

STARTING_GOLD = 500
BASE_HIRE_COST = 30          # Base hiring cost (naked hero)
GEAR_CHANCE_WEAPON = 0.55    # 55% chance hero comes with a weapon
GEAR_CHANCE_ARMOR = 0.40     # 40% chance hero comes with armor
GEAR_CHANCE_ACCESSORY = 0.20 # 20% chance hero comes with an accessory
TAVERN_POOL_SIZE = None      # Dynamically set to class count (see get_tavern_pool_size())
HERO_ROSTER_MAX = 20         # Maximum heroes a player can own at once
BANK_MAX_CAPACITY = 20       # Maximum items in account-wide bank storage
HERO_SPRITE_VARIANTS = {       # Number of sprite variants per hero class
    "crusader": 6,
    "confessor": 6,
    "inquisitor": 7,
    "ranger": 4,
    "hexblade": 9,
    "mage": 7,
    "bard": 1,
    "blood_knight": 4,
    "plague_doctor": 3,
    "revenant": 1,
    "shaman": 1,
}
HERO_SPRITE_VARIANTS_DEFAULT = 3  # Fallback for unknown classes


# ---------- Hero Stats (with variation) ----------

class HeroStats(BaseModel):
    """Hero stats — derived from class base stats with random variation."""
    hp: int = 100
    max_hp: int = 100
    attack_damage: int = 15
    ranged_damage: int = 10
    armor: int = 2
    vision_range: int = 7
    ranged_range: int = 5


# ---------- Hero Model ----------

class Hero(BaseModel):
    """A persistent hero that belongs to a player's roster.

    Heroes are generated in the tavern, hired with gold, and sent into
    dungeon matches. On death (permadeath), is_alive is set to False.
    """
    hero_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Unknown Hero"
    class_id: str = "crusader"
    sprite_variant: int = 1     # Sprite variant (1-3), assigned randomly on creation
    stats: HeroStats = Field(default_factory=HeroStats)
    equipment: dict = Field(default_factory=dict)    # Serialized Equipment slots
    inventory: list = Field(default_factory=list)     # Serialized Item list
    is_alive: bool = True
    hire_cost: int = BASE_HIRE_COST
    # Tracking
    matches_survived: int = 0
    enemies_killed: int = 0


# ---------- Player Profile ----------

class PlayerProfile(BaseModel):
    """Persistent player profile saved to disk as JSON.

    Created automatically on first access (no registration).
    Survives server restarts via JSON file persistence.
    """
    player_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    username: str
    gold: int = STARTING_GOLD
    heroes: list[Hero] = Field(default_factory=list)
    # Tavern: pool of heroes available for hire (regenerated on refresh)
    tavern_pool: list[Hero] = Field(default_factory=list)
    tavern_class_count: int = 0  # Class count when pool was generated (for stale detection)
    # Bank: account-wide item storage (20 slots, persists across hero deaths)
    bank: list = Field(default_factory=list)


# ---------- Hero Generation ----------

def generate_hero(class_id: str, name: str, class_def: dict) -> Hero:
    """Generate a hero with flat base stats and random starting gear.

    Heroes use exact class base stats (no variation). The tavern hire cost
    is BASE_HIRE_COST + the sell value of any gear they come with.
    Gear is rolled from the item generator using the class's allowed
    weapon categories and preferred armor type.

    Args:
        class_id: The class identifier (e.g. "crusader")
        name: The hero's display name
        class_def: Raw class definition dict from classes_config.json

    Returns:
        A Hero instance with base stats and optional random starting gear.
    """
    hp = class_def.get("base_hp", 100)
    stats = HeroStats(
        hp=hp,
        max_hp=hp,
        attack_damage=class_def.get("base_melee_damage", 15),
        ranged_damage=class_def.get("base_ranged_damage", 10),
        armor=class_def.get("base_armor", 2),
        vision_range=class_def.get("base_vision_range", 7),
        ranged_range=class_def.get("ranged_range", 5),
    )

    # Roll random starting gear
    equipment, gear_value = _roll_starting_gear(class_id, class_def)
    hire_cost = BASE_HIRE_COST + gear_value

    return Hero(
        name=name,
        class_id=class_id,
        sprite_variant=random.randint(1, HERO_SPRITE_VARIANTS.get(class_id, HERO_SPRITE_VARIANTS_DEFAULT)),
        stats=stats,
        equipment=equipment,
        hire_cost=hire_cost,
    )


def _roll_starting_gear(class_id: str, class_def: dict) -> tuple[dict, int]:
    """Roll random starting equipment for a tavern hero.

    Each slot has an independent chance to have gear. Gear rarity is weighted
    toward common/magic with a small chance of rare.

    Args:
        class_id: Class identifier for weapon/armor filtering.
        class_def: Class definition dict with allowed_weapon_categories and preferred_armor.

    Returns:
        (equipment_dict, total_gear_sell_value) — serialized equipment and gold value.
    """
    from app.core.item_generator import generate_item, roll_rarity
    from app.core.loot import load_items_config

    items_config_raw = load_items_config()
    equipment: dict = {}
    total_value = 0
    rng = random.Random()
    allowed_weapons = class_def.get("allowed_weapon_categories", [])
    preferred_armor = class_def.get("preferred_armor", "cloth")

    # --- Weapon ---
    if rng.random() < GEAR_CHANCE_WEAPON and allowed_weapons:
        candidates = [
            item_id for item_id, data in items_config_raw.items()
            if data.get("equip_slot") == "weapon"
            and data.get("item_type") != "consumable"
            and data.get("weapon_category") in allowed_weapons
        ]
        if candidates:
            base_id = rng.choice(candidates)
            rarity = _tavern_rarity(rng)
            item = generate_item(base_type_id=base_id, rarity=rarity, item_level=1, seed=rng.randint(0, 2**31))
            if item:
                equipment["weapon"] = item.model_dump(mode="json")
                total_value += item.sell_value

    # --- Armor ---
    if rng.random() < GEAR_CHANCE_ARMOR:
        # Prefer the class's preferred armor type, but allow any
        armor_candidates = [
            item_id for item_id, data in items_config_raw.items()
            if data.get("equip_slot") == "armor"
            and data.get("item_type") != "consumable"
            and data.get("armor_category") == preferred_armor
        ]
        if not armor_candidates:
            armor_candidates = [
                item_id for item_id, data in items_config_raw.items()
                if data.get("equip_slot") == "armor"
                and data.get("item_type") != "consumable"
            ]
        if armor_candidates:
            base_id = rng.choice(armor_candidates)
            rarity = _tavern_rarity(rng)
            item = generate_item(base_type_id=base_id, rarity=rarity, item_level=1, seed=rng.randint(0, 2**31))
            if item:
                equipment["armor"] = item.model_dump(mode="json")
                total_value += item.sell_value

    # --- Accessory ---
    if rng.random() < GEAR_CHANCE_ACCESSORY:
        acc_candidates = [
            item_id for item_id, data in items_config_raw.items()
            if data.get("equip_slot") == "accessory"
            and data.get("item_type") != "consumable"
        ]
        if acc_candidates:
            base_id = rng.choice(acc_candidates)
            rarity = _tavern_rarity(rng)
            item = generate_item(base_type_id=base_id, rarity=rarity, item_level=1, seed=rng.randint(0, 2**31))
            if item:
                equipment["accessory"] = item.model_dump(mode="json")
                total_value += item.sell_value

    return equipment, total_value


def _tavern_rarity(rng: random.Random) -> str:
    """Roll a rarity for tavern starting gear — weighted toward common/magic."""
    return rng.choices(
        ["common", "magic", "rare"],
        weights=[60, 30, 10],
        k=1,
    )[0]


def get_tavern_pool_size(classes_config: dict) -> int:
    """Return the tavern pool size — one hero per available class."""
    return max(len(classes_config), 1)


def generate_tavern_heroes(
    classes_config: dict,
    names_config: dict,
    count: int | None = None,
    existing_names: set[str] | None = None,
) -> list[Hero]:
    """Generate a pool of heroes for the tavern.

    Distributes heroes across all available classes as evenly as possible.
    Names are drawn from the names_config and guaranteed unique within the pool.

    Args:
        classes_config: Dict of class_id -> class definition (from classes_config.json "classes" key)
        names_config: Dict from names_config.json (class_id -> list of names + "generic" fallback)
        count: Number of heroes to generate
        existing_names: Set of names already in use (hired heroes) to avoid duplicates

    Returns:
        List of Hero instances ready for display in the tavern.
    """
    if existing_names is None:
        existing_names = set()

    class_ids = list(classes_config.keys())
    if not class_ids:
        return []

    # Default count = one hero per class (covers all classes)
    if count is None:
        count = len(class_ids)

    heroes: list[Hero] = []
    used_names: set[str] = set(existing_names)

    for i in range(count):
        # Rotate through classes evenly
        class_id = class_ids[i % len(class_ids)]
        class_def = classes_config[class_id]

        # Pick a unique name
        name = _pick_unique_name(class_id, names_config, used_names)
        used_names.add(name)

        hero = generate_hero(class_id, name, class_def)
        heroes.append(hero)

    return heroes


def _pick_unique_name(
    class_id: str,
    names_config: dict,
    used_names: set[str],
) -> str:
    """Pick a unique name for a hero from the names config.

    Tries class-specific names first, then generic fallback, then generates
    a numbered fallback if all names are exhausted.
    """
    # Try class-specific names
    class_names = names_config.get(class_id, [])
    available = [n for n in class_names if n not in used_names]
    if available:
        return random.choice(available)

    # Try generic fallback names
    generic_names = names_config.get("generic", [])
    available = [n for n in generic_names if n not in used_names]
    if available:
        return random.choice(available)

    # All names exhausted — generate a numbered fallback
    class_name = class_id.capitalize()
    counter = 1
    while True:
        fallback = f"{class_name} #{counter}"
        if fallback not in used_names:
            return fallback
        counter += 1
