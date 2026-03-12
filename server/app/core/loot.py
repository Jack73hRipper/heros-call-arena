"""
Loot generation utility — config-driven item rolling.

Phase 4D-1: Pure functions. No match/combat integration.
Loads items_config.json and loot_tables.json, provides roll_loot_table()
to generate Item instances from configured probability pools.

Phase 16B: Added generate_enemy_loot() and generate_chest_loot() that
produce affix-bearing items via the item_generator module. The original
create_item() / roll_enemy_loot() / roll_chest_loot() remain for backward compat.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from app.models.items import (
    ConsumableEffect,
    Item,
    Rarity,
    StatBonuses,
)

# ---------- Config Paths ----------

_configs_dir = Path(__file__).resolve().parent.parent.parent / "configs"
_items_config_path = _configs_dir / "items_config.json"
_loot_tables_path = _configs_dir / "loot_tables.json"

# ---------- Caches ----------

_items_cache: dict[str, dict] | None = None
_loot_tables_cache: dict | None = None


# ---------- Config Loaders ----------

def load_items_config(path: Path | None = None) -> dict[str, dict]:
    """Load item definitions from JSON config. Caches after first load.

    Returns a dict mapping item_id -> raw item dict from config.
    """
    global _items_cache
    if _items_cache is not None:
        return _items_cache

    config_file = path or _items_config_path
    if config_file.exists():
        with open(config_file, "r") as f:
            raw = json.load(f)
        _items_cache = raw.get("items", {})
    else:
        _items_cache = {}
    return _items_cache


def load_loot_tables(path: Path | None = None) -> dict:
    """Load loot table definitions from JSON config. Caches after first load.

    Returns the full loot tables dict with 'enemy_loot_tables' and 'chest_loot_tables'.
    """
    global _loot_tables_cache
    if _loot_tables_cache is not None:
        return _loot_tables_cache

    config_file = path or _loot_tables_path
    if config_file.exists():
        with open(config_file, "r") as f:
            _loot_tables_cache = json.load(f)
    else:
        _loot_tables_cache = {"enemy_loot_tables": {}, "chest_loot_tables": {}}
    return _loot_tables_cache


def clear_caches() -> None:
    """Clear all config caches. Useful for testing with different config files."""
    global _items_cache, _loot_tables_cache
    _items_cache = None
    _loot_tables_cache = None


# ---------- Phase 18F: Monster Rarity Loot Helpers ----------

# MF bonus per monster rarity tier (on top of killer's magic find)
_RARITY_MF_BONUS = {
    "normal": 0.0,
    "champion": 0.25,
    "rare": 0.50,
    "super_unique": 1.00,
}

# Gold multiplier per monster rarity tier
_RARITY_GOLD_MULTIPLIER = {
    "normal": 1.0,
    "champion": 1.5,
    "rare": 2.5,
    "super_unique": 5.0,
}


def _get_rarity_loot_config(monster_rarity: str | None) -> dict:
    """Get loot-related config fields for a monster rarity tier.

    Returns a dict with loot_drop_chance_bonus, loot_bonus_items,
    loot_guaranteed_rarity, and loot_mf_bonus. Falls back to normal-tier
    defaults if the rarity is unknown or None.
    """
    if not monster_rarity or monster_rarity == "normal":
        return {
            "loot_drop_chance_bonus": 0.0,
            "loot_bonus_items": 0,
            "loot_guaranteed_rarity": None,
            "loot_mf_bonus": 0.0,
        }

    from app.core.monster_rarity import get_rarity_tier

    tier = get_rarity_tier(monster_rarity)
    if not tier:
        return {
            "loot_drop_chance_bonus": 0.0,
            "loot_bonus_items": 0,
            "loot_guaranteed_rarity": None,
            "loot_mf_bonus": 0.0,
        }

    return {
        "loot_drop_chance_bonus": tier.get("loot_drop_chance_bonus", 0.0),
        "loot_bonus_items": tier.get("loot_bonus_items", 0),
        "loot_guaranteed_rarity": tier.get("loot_guaranteed_rarity"),
        "loot_mf_bonus": _RARITY_MF_BONUS.get(monster_rarity, 0.0),
    }


def get_gold_multiplier(monster_rarity: str | None) -> float:
    """Phase 18F: Get the gold drop multiplier for a monster rarity tier.

    Returns:
        Multiplier for gold drops (1.0× for normal, up to 5.0× for super uniques).
        Used when gold drops are implemented in the future.
    """
    if not monster_rarity:
        return 1.0
    return _RARITY_GOLD_MULTIPLIER.get(monster_rarity, 1.0)


# ---------- Item Factory ----------

def create_item(item_id: str, items_config: dict[str, dict] | None = None) -> Item | None:
    """Create an Item instance from config by item_id.

    Returns None if the item_id is not found in config.
    """
    config = items_config or load_items_config()
    raw = config.get(item_id)
    if raw is None:
        return None

    # Build stat bonuses
    raw_bonuses = raw.get("stat_bonuses", {})
    stat_bonuses = StatBonuses(**raw_bonuses)

    # Build consumable effect (if present)
    consumable_effect = None
    raw_effect = raw.get("consumable_effect")
    if raw_effect is not None:
        consumable_effect = ConsumableEffect(**raw_effect)

    return Item(
        item_id=raw["item_id"],
        name=raw["name"],
        item_type=raw["item_type"],
        rarity=raw.get("rarity", "common"),
        equip_slot=raw.get("equip_slot"),
        stat_bonuses=stat_bonuses,
        consumable_effect=consumable_effect,
        description=raw.get("description", ""),
        sell_value=raw.get("sell_value", 0),
    )


def get_all_item_ids() -> list[str]:
    """Return all item IDs from the items config."""
    return list(load_items_config().keys())


def get_items_by_rarity(rarity: str) -> list[str]:
    """Return item IDs of a specific rarity."""
    config = load_items_config()
    return [
        item_id for item_id, data in config.items()
        if data.get("rarity", "common") == rarity
    ]


# ---------- Loot Rolling ----------

def _pick_from_pool(pools: list[dict], rng: random.Random, items_config: dict[str, dict]) -> Item | None:
    """Pick a single item from weighted pools.

    Each pool has a 'weight' and an 'items' list. First we pick a pool
    (weighted random), then pick a random item from that pool's items list.
    Returns None if the chosen item_id is invalid.
    """
    if not pools:
        return None

    weights = [pool["weight"] for pool in pools]
    chosen_pool = rng.choices(pools, weights=weights, k=1)[0]
    pool_items = chosen_pool.get("items", [])
    if not pool_items:
        return None

    chosen_id = rng.choice(pool_items)
    return create_item(chosen_id, items_config)


def _try_rarity_upgrade(item: Item, magic_find_pct: float, rng: random.Random) -> Item:
    """Phase 16A/16C: Attempt to upgrade an item's rarity based on magic_find_pct.

    magic_find_pct is a decimal (e.g., 0.20 = 20% bonus chance).
    If the upgrade roll succeeds, the item's rarity is bumped up one tier.
    Phase 16C: Full tier chain: common → magic → rare → epic.
    """
    if magic_find_pct <= 0:
        return item

    # Upgrade chain — each tier can upgrade to the next
    upgrade_chain = {
        Rarity.COMMON: Rarity.MAGIC,
        Rarity.UNCOMMON: Rarity.MAGIC,  # Legacy: uncommon → magic
        Rarity.MAGIC: Rarity.RARE,
        Rarity.RARE: Rarity.EPIC,
    }

    if item.rarity in upgrade_chain and rng.random() < magic_find_pct:
        item.rarity = upgrade_chain[item.rarity]

    return item


def _pick_guaranteed_rarity_from_pool(
    pools: list[dict],
    rng: random.Random,
    items_config: dict[str, dict],
    target_rarity: str = "uncommon",
) -> Item | None:
    """Pick a guaranteed item of at least the target rarity from pools.

    Phase 16C: Generalized from _pick_uncommon_from_pool to support
    any rarity target ('magic', 'rare', 'epic', etc.).
    Filters pool items to matching rarity, falls back to any pool item.
    """
    # Map target rarity to config-level rarity strings that qualify
    # (e.g., "magic" also matches legacy "uncommon")
    qualifying = {target_rarity}
    if target_rarity == "magic":
        qualifying.add("uncommon")  # Legacy items marked "uncommon" qualify as magic

    matching_ids = []
    for pool in pools:
        for item_id in pool.get("items", []):
            raw = items_config.get(item_id, {})
            if raw.get("rarity", "common") in qualifying:
                matching_ids.append(item_id)

    if matching_ids:
        chosen_id = rng.choice(matching_ids)
        return create_item(chosen_id, items_config)

    # Fallback: pick from any pool normally
    return _pick_from_pool(pools, rng, items_config)


def _pick_uncommon_from_pool(pools: list[dict], rng: random.Random, items_config: dict[str, dict]) -> Item | None:
    """Pick a guaranteed uncommon item from the pools.

    Filters pool items to only uncommon-rarity items, then picks randomly.
    Falls back to any pool item if no uncommon items exist.
    Legacy wrapper — delegates to _pick_guaranteed_rarity_from_pool.
    """
    return _pick_guaranteed_rarity_from_pool(pools, rng, items_config, "uncommon")


def roll_enemy_loot(
    enemy_type: str,
    seed: int | None = None,
    magic_find_pct: float = 0.0,
) -> list[Item]:
    """Roll loot for a defeated enemy.

    Args:
        enemy_type: Enemy type ID (e.g. "demon", "skeleton", "undead_knight").
        seed: Optional deterministic seed for reproducible results.
        magic_find_pct: Phase 16A — bonus chance for drops to upgrade rarity tier.

    Returns:
        List of Item objects dropped. May be empty if drop chance fails.
    """
    rng = random.Random(seed) if seed is not None else random.Random()
    items_config = load_items_config()
    loot_tables = load_loot_tables()

    table = loot_tables.get("enemy_loot_tables", {}).get(enemy_type)
    if table is None:
        return []

    # Check drop chance
    drop_chance = table.get("drop_chance", 0.0)
    if rng.random() > drop_chance:
        return []

    # Determine number of items to drop
    min_items = table.get("min_items", 1)
    max_items = table.get("max_items", 1)
    num_items = rng.randint(min_items, max_items)
    if num_items <= 0:
        return []

    pools = table.get("pools", [])
    if not pools:
        return []

    items: list[Item] = []

    # Guaranteed items always drop (e.g. boss always drops a portal scroll)
    guaranteed_items = table.get("guaranteed_items", [])
    for gitem_id in guaranteed_items:
        gitem = create_item(gitem_id, items_config)
        if gitem is not None:
            items.append(gitem)

    # If guaranteed_rarity is set, first item must be of that rarity
    guaranteed_rarity = table.get("guaranteed_rarity")
    if guaranteed_rarity:
        item = _pick_guaranteed_rarity_from_pool(pools, rng, items_config, guaranteed_rarity)
        if item is not None:
            items.append(item)
        num_items -= 1

    # Roll remaining items from pools
    for _ in range(num_items):
        item = _pick_from_pool(pools, rng, items_config)
        if item is not None:
            # Phase 16A: Magic Find rarity upgrade
            item = _try_rarity_upgrade(item, magic_find_pct, rng)
            items.append(item)

    return items


def roll_chest_loot(
    chest_type: str = "default",
    seed: int | None = None,
    magic_find_pct: float = 0.0,
) -> list[Item]:
    """Roll loot for a chest.

    Args:
        chest_type: Chest type ID (e.g. "default", "boss_chest").
        seed: Optional deterministic seed for reproducible results.
        magic_find_pct: Phase 16A — bonus chance for drops to upgrade rarity tier.

    Returns:
        List of Item objects found in the chest.
    """
    rng = random.Random(seed) if seed is not None else random.Random()
    items_config = load_items_config()
    loot_tables = load_loot_tables()

    table = loot_tables.get("chest_loot_tables", {}).get(chest_type)
    if table is None:
        return []

    min_items = table.get("min_items", 1)
    max_items = table.get("max_items", 1)
    num_items = rng.randint(min_items, max_items)
    if num_items <= 0:
        return []

    pools = table.get("pools", [])
    if not pools:
        return []

    items: list[Item] = []

    # If guaranteed_rarity is set, first item must be of that rarity
    guaranteed_rarity = table.get("guaranteed_rarity")
    if guaranteed_rarity:
        item = _pick_guaranteed_rarity_from_pool(pools, rng, items_config, guaranteed_rarity)
        if item is not None:
            items.append(item)
        num_items -= 1

    # Roll remaining items from pools
    for _ in range(num_items):
        item = _pick_from_pool(pools, rng, items_config)
        if item is not None:
            # Phase 16A: Magic Find rarity upgrade
            item = _try_rarity_upgrade(item, magic_find_pct, rng)
            items.append(item)

    return items


def roll_loot_table(
    source_type: str,
    source_category: str = "enemy",
    seed: int | None = None,
) -> list[Item]:
    """Unified loot rolling interface.

    Args:
        source_type: The specific type ID (e.g. "demon", "default", "boss_chest").
        source_category: "enemy" or "chest".
        seed: Optional deterministic seed.

    Returns:
        List of Item objects.
    """
    if source_category == "enemy":
        return roll_enemy_loot(source_type, seed=seed)
    elif source_category == "chest":
        return roll_chest_loot(source_type, seed=seed)
    else:
        return []


# ---------- Phase 18G: Super Unique Loot ----------

def roll_super_unique_loot(
    super_unique_id: str,
    seed: int | None = None,
    magic_find_pct: float = 0.0,
) -> list[Item]:
    """Roll loot for a defeated super unique using its dedicated loot table.

    Super uniques have their own loot tables embedded in super_uniques_config.json.
    They always drop (drop_chance 1.0) with guaranteed minimum rarity.

    Args:
        super_unique_id: Super unique ID (e.g. "malgris_the_defiler").
        seed: Optional deterministic seed for reproducible results.
        magic_find_pct: Player's magic find bonus (decimal, e.g. 0.20 = 20%).

    Returns:
        List of Item objects dropped. Falls back to empty if super unique
        not found or has no loot table.
    """
    from app.core.monster_rarity import get_super_unique

    su_config = get_super_unique(super_unique_id)
    if not su_config:
        return []

    table = su_config.get("loot_table", {})
    if not table:
        return []

    rng = random.Random(seed) if seed is not None else random.Random()
    items_config = load_items_config()

    # Check drop chance (usually 1.0 for super uniques)
    drop_chance = table.get("drop_chance", 1.0)
    if rng.random() > drop_chance:
        return []

    # Determine number of items
    min_items = table.get("min_items", 3)
    max_items = table.get("max_items", 4)
    num_items = rng.randint(min_items, max_items)
    if num_items <= 0:
        return []

    pools = table.get("pools", [])
    if not pools:
        return []

    items: list[Item] = []
    guaranteed_rarity = table.get("guaranteed_rarity")

    # First item: enforce guaranteed rarity
    if guaranteed_rarity and num_items > 0:
        item = _pick_guaranteed_rarity_from_pool(pools, rng, items_config, guaranteed_rarity)
        if item is not None:
            items.append(item)
        num_items -= 1

    # Roll remaining items
    for _ in range(num_items):
        item = _pick_from_pool(pools, rng, items_config)
        if item is not None:
            item = _try_rarity_upgrade(item, magic_find_pct, rng)
            items.append(item)

    return items


def validate_loot_tables() -> list[str]:
    """Validate that all item_ids referenced in loot tables exist in items config.

    Returns a list of error messages. Empty list = all valid.
    """
    errors: list[str] = []
    items_config = load_items_config()
    loot_tables = load_loot_tables()

    for category_key in ("enemy_loot_tables", "chest_loot_tables"):
        tables = loot_tables.get(category_key, {})
        for table_name, table_data in tables.items():
            pools = table_data.get("pools", [])
            for pool_idx, pool in enumerate(pools):
                for item_id in pool.get("items", []):
                    if item_id not in items_config:
                        errors.append(
                            f"{category_key}.{table_name}.pools[{pool_idx}]: "
                            f"item_id '{item_id}' not found in items_config"
                        )

    return errors


# ---------- Phase 16B: Generator-backed Loot ----------

def generate_enemy_loot(
    enemy_type: str,
    floor_number: int = 1,
    enemy_tier: str = "fodder",
    magic_find_pct: float = 0.0,
    seed: int | None = None,
    dropped_unique_ids: set[str] | None = None,
    dropped_set_piece_ids: set[str] | None = None,
    player_class: str = "",
    monster_rarity: str | None = None,
) -> list[Item]:
    """Roll loot for a defeated enemy using the Phase 16B affix generator.

    Items are generated with random affixes, rarity scaled by floor and MF.
    Falls back to static create_item() for items that can't be generated.

    Phase 16D: Elite/Boss enemies can additionally drop unique items.
    Phase 16E: Elite/Boss enemies can additionally drop set items.
    Phase 18F: Monster rarity tier bonuses — champions/rares/super uniques
    get boosted drop chances, bonus item counts, guaranteed rarity floors,
    and magic find bonuses.

    Args:
        enemy_type: Enemy type ID (e.g. "demon", "skeleton", "undead_knight").
        floor_number: Current dungeon floor (affects rarity + item level).
        enemy_tier: Enemy difficulty tier ("swarm", "fodder", "mid", "elite", "boss").
        magic_find_pct: Player's magic find bonus (decimal, e.g. 0.20 = 20%).
        seed: Optional deterministic seed for reproducible results.
        dropped_unique_ids: Set of unique IDs already dropped this run (prevents duplicates).
        monster_rarity: Phase 18F — monster rarity tier ("normal", "champion", "rare", "super_unique").

    Returns:
        List of Item objects dropped. May be empty if drop chance fails.
    """
    from app.core.item_generator import (
        generate_item, roll_rarity, _calculate_item_level,
        enforce_minimum_rarity, get_boss_guaranteed_rarity, get_boss_drop_count,
        roll_unique_drop,
    )

    rng = random.Random(seed) if seed is not None else random.Random()
    items_config = load_items_config()
    loot_tables = load_loot_tables()

    # --- Phase 18F: Load monster rarity tier bonuses ---
    rarity_config = _get_rarity_loot_config(monster_rarity)
    rarity_drop_bonus = rarity_config.get("loot_drop_chance_bonus", 0.0)
    rarity_bonus_items = rarity_config.get("loot_bonus_items", 0)
    rarity_guaranteed = rarity_config.get("loot_guaranteed_rarity")  # e.g. "magic", "rare"
    rarity_mf_bonus = rarity_config.get("loot_mf_bonus", 0.0)  # extra MF from tier

    # Apply rarity MF bonus on top of killer's magic find
    effective_mf = magic_find_pct + rarity_mf_bonus

    table = loot_tables.get("enemy_loot_tables", {}).get(enemy_type)
    if table is None:
        return []

    # Check drop chance — Phase 18F: add rarity tier drop bonus
    base_drop_chance = table.get("drop_chance", 0.0)
    effective_drop_chance = min(1.0, base_drop_chance + rarity_drop_bonus)
    if rng.random() > effective_drop_chance:
        return []

    # Phase 16C: Boss drop count override by floor bracket
    is_boss = enemy_tier == "boss"
    if is_boss:
        num_items = get_boss_drop_count(floor_number, rng)
    else:
        min_items = table.get("min_items", 1)
        max_items = table.get("max_items", 1)
        num_items = rng.randint(min_items, max_items)

    # Phase 18F: Add bonus items from monster rarity tier
    num_items += rarity_bonus_items

    if num_items <= 0:
        return []

    pools = table.get("pools", [])
    if not pools:
        return []

    items: list[Item] = []

    # Guaranteed items always drop (e.g. boss always drops a portal scroll)
    guaranteed_items = table.get("guaranteed_items", [])
    for gitem_id in guaranteed_items:
        gitem = create_item(gitem_id, items_config)
        if gitem is not None:
            items.append(gitem)

    # Phase 16C: Boss guaranteed minimum rarity
    boss_min_rarity = get_boss_guaranteed_rarity(floor_number) if is_boss else None

    # Phase 18F: Monster rarity guaranteed floor (e.g. rare → magic+, super_unique → rare+)
    # Use the higher of boss guaranteed and rarity tier guaranteed
    rarity_min_rarity = rarity_guaranteed

    # Roll items with affix generation
    first_item = True
    for _ in range(num_items):
        # Pick base type from pools
        base_type_id = _pick_base_type_from_pool(pools, rng, items_config)
        if base_type_id is None:
            continue

        # Roll rarity — Phase 18F: use effective MF (includes rarity tier bonus)
        rarity = roll_rarity(
            floor_number=floor_number,
            enemy_tier=enemy_tier,
            magic_find_bonus=effective_mf,
            rng=rng,
        )

        # Phase 16C: Enforce boss minimum rarity on at least the first item
        if boss_min_rarity and first_item:
            rarity = enforce_minimum_rarity(rarity, boss_min_rarity)

        # Phase 18F: Enforce monster rarity tier guaranteed floor on first item
        if rarity_min_rarity and first_item:
            rarity = enforce_minimum_rarity(rarity, rarity_min_rarity)

        if first_item:
            first_item = False

        # Calculate item level
        item_level = _calculate_item_level(floor_number, enemy_tier, rng)

        # Generate item with affixes
        item = generate_item(
            base_type_id=base_type_id,
            rarity=rarity,
            item_level=item_level,
            items_config=items_config,
        )
        if item is not None:
            items.append(item)

    # Phase 16D: Roll for unique item drop (elite/boss only)
    unique_item = roll_unique_drop(
        enemy_tier=enemy_tier,
        floor_number=floor_number,
        magic_find_pct=magic_find_pct,
        dropped_unique_ids=dropped_unique_ids or set(),
        enemy_type=enemy_type,
        rng=rng,
    )
    if unique_item is not None:
        items.append(unique_item)
        # Track that this unique was dropped so it won't drop again this run
        if dropped_unique_ids is not None:
            dropped_unique_ids.add(unique_item.item_id)

    # Phase 16E: Roll for set item drop (elite/boss only)
    from app.core.item_generator import roll_set_drop
    set_item = roll_set_drop(
        enemy_tier=enemy_tier,
        floor_number=floor_number,
        magic_find_pct=magic_find_pct,
        dropped_set_piece_ids=dropped_set_piece_ids or set(),
        player_class=player_class,
        rng=rng,
    )
    if set_item is not None:
        items.append(set_item)
        # Track that this set piece was dropped so it won't drop again this run
        if dropped_set_piece_ids is not None:
            dropped_set_piece_ids.add(set_item.item_id)

    return items


def generate_chest_loot(
    chest_type: str = "default",
    floor_number: int = 1,
    magic_find_pct: float = 0.0,
    seed: int | None = None,
) -> list[Item]:
    """Roll loot for a chest using the Phase 16B affix generator.

    Args:
        chest_type: Chest type ID (e.g. "default", "boss_chest").
        floor_number: Current dungeon floor (affects rarity + item level).
        magic_find_pct: Player's magic find bonus (decimal, e.g. 0.20 = 20%).
        seed: Optional deterministic seed for reproducible results.

    Returns:
        List of Item objects found in the chest.
    """
    from app.core.item_generator import generate_item, roll_rarity, _calculate_item_level

    rng = random.Random(seed) if seed is not None else random.Random()
    items_config = load_items_config()
    loot_tables = load_loot_tables()

    table = loot_tables.get("chest_loot_tables", {}).get(chest_type)
    if table is None:
        return []

    min_items = table.get("min_items", 1)
    max_items = table.get("max_items", 1)
    num_items = rng.randint(min_items, max_items)
    if num_items <= 0:
        return []

    pools = table.get("pools", [])
    if not pools:
        return []

    items: list[Item] = []

    # Chest item level = floor × 2
    base_item_level = floor_number * 2
    is_boss_chest = "boss" in chest_type.lower()
    if is_boss_chest:
        base_item_level += 4

    for _ in range(num_items):
        base_type_id = _pick_base_type_from_pool(pools, rng, items_config)
        if base_type_id is None:
            continue

        # Roll rarity (chests use "mid" tier equivalent for rarity)
        chest_tier = "elite" if is_boss_chest else "mid"
        rarity = roll_rarity(
            floor_number=floor_number,
            enemy_tier=chest_tier,
            magic_find_bonus=magic_find_pct,
            rng=rng,
        )

        item_level = base_item_level + rng.randint(0, 2)

        item = generate_item(
            base_type_id=base_type_id,
            rarity=rarity,
            item_level=item_level,
            items_config=items_config,
        )
        if item is not None:
            items.append(item)

    return items


def _pick_base_type_from_pool(
    pools: list[dict], rng: random.Random, items_config: dict[str, dict]
) -> str | None:
    """Pick a base type ID from weighted pools (without creating the item).

    Returns the item_id string, or None if pools are empty/invalid.
    """
    if not pools:
        return None

    weights = [pool["weight"] for pool in pools]
    chosen_pool = rng.choices(pools, weights=weights, k=1)[0]
    pool_items = chosen_pool.get("items", [])
    if not pool_items:
        return None

    chosen_id = rng.choice(pool_items)
    # Verify it exists in config
    if chosen_id not in items_config:
        return None
    return chosen_id
