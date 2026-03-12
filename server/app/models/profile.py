"""
Pydantic models for persistent player profiles and heroes.

Phase 4E-1: Data models for the Town system — hero hiring, roster management,
and JSON-based persistence. No match integration (that's 4E-2).
"""

from __future__ import annotations

import random
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.items import Equipment, Inventory


# ---------- Constants ----------

STARTING_GOLD = 100
STAT_VARIATION_PERCENT = 10  # ±10% stat variation on hire
BASE_HIRE_COST = 30          # Minimum hiring cost
HIRE_COST_PER_STAT_POINT = 0.15  # Gold per total stat point above minimum
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

def _vary_stat(base: int, variation_pct: int = STAT_VARIATION_PERCENT) -> int:
    """Apply random ±variation_pct% to a base stat. Minimum 1."""
    if base <= 0:
        return 0
    delta = max(1, int(base * variation_pct / 100))
    return max(1, base + random.randint(-delta, delta))


def generate_hero(class_id: str, name: str, class_def: dict) -> Hero:
    """Generate a hero with stat variation from class base stats.

    Args:
        class_id: The class identifier (e.g. "crusader")
        name: The hero's display name
        class_def: Raw class definition dict from classes_config.json

    Returns:
        A Hero instance with randomized stats and calculated hire cost.
    """
    # Generate varied stats
    hp = _vary_stat(class_def.get("base_hp", 100))
    stats = HeroStats(
        hp=hp,
        max_hp=hp,
        attack_damage=_vary_stat(class_def.get("base_melee_damage", 15)),
        ranged_damage=_vary_stat(class_def.get("base_ranged_damage", 10)),
        armor=_vary_stat(class_def.get("base_armor", 2)),
        vision_range=_vary_stat(class_def.get("base_vision_range", 7)),
        ranged_range=class_def.get("ranged_range", 5),  # No variation on range
    )

    # Calculate hire cost based on total stat power
    total_stat_points = (
        stats.max_hp + stats.attack_damage * 3 + stats.ranged_damage * 3
        + stats.armor * 5 + stats.vision_range * 2
    )
    hire_cost = max(BASE_HIRE_COST, int(BASE_HIRE_COST + total_stat_points * HIRE_COST_PER_STAT_POINT))

    return Hero(
        name=name,
        class_id=class_id,
        sprite_variant=random.randint(1, HERO_SPRITE_VARIANTS.get(class_id, HERO_SPRITE_VARIANTS_DEFAULT)),
        stats=stats,
        hire_cost=hire_cost,
    )


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
