"""
Loadout Generator — Equipment generation for enemies and AI heroes.

Extracted from match_manager.py (Phase 6 of match-manager-split-plan).
Handles rarity-scaled item rolling for enemy and hero loadouts.
"""

from __future__ import annotations

import random

from app.models.player import PlayerState


# ---------- Phase 28B: Enemy Spawn Loadouts ----------

# Rarity tier names in ascending order for rarity offset clamping
_RARITY_TIERS = ["common", "magic", "rare", "epic"]

# Rarity bonus by monster rarity tier
_MONSTER_RARITY_BONUS: dict[str, int] = {
    "normal": 0,
    "champion": 1,
    "rare": 2,
}


def generate_enemy_loadout(
    enemy_def,
    floor_number: int = 1,
    monster_rarity: str | None = None,
    rng: random.Random | None = None,
) -> tuple[dict, list]:
    """Generate equipment dict and inventory list for an enemy.

    Args:
        enemy_def: EnemyDefinition with optional loadout config.
        floor_number: Dungeon floor (scales item_level and rarity).
        monster_rarity: champion/rare → boosts item rarity tier.
        rng: Optional seeded RNG for deterministic generation.

    Returns:
        (equipment_dict, inventory_list) ready to assign to PlayerState.
    """
    from app.core.item_generator import generate_item, roll_rarity
    from app.core.loot import load_items_config

    loadout_cfg = getattr(enemy_def, "loadout", None)
    if not loadout_cfg:
        return {}, []

    if rng is None:
        rng = random.Random()

    items_config = load_items_config()
    equipment: dict = {}
    inventory: list = []

    rarity_bonus = _MONSTER_RARITY_BONUS.get(monster_rarity or "normal", 0)

    # Generate equipment for each slot
    for slot_name in ("weapon", "armor", "accessory"):
        slot_cfg = loadout_cfg.get(slot_name)
        if not slot_cfg:
            continue

        pool = slot_cfg.get("pool", [])
        if not pool:
            continue

        slot_rarity_offset = slot_cfg.get("rarity_offset", 0)

        # Find matching base_type_ids from items_config
        category_key = "weapon_category" if slot_name == "weapon" else "armor_category" if slot_name == "armor" else None
        candidates = []
        for item_id, item_data in items_config.items():
            if item_data.get("equip_slot") != slot_name:
                continue
            if item_data.get("item_type") == "consumable":
                continue
            if category_key:
                if item_data.get(category_key) in pool:
                    candidates.append(item_id)
            else:
                # Accessory: pool contains base_type_ids directly
                if item_id in pool or not pool:
                    candidates.append(item_id)

        if not candidates:
            continue

        base_type_id = rng.choice(candidates)

        # Roll rarity with floor scaling + monster rarity bonus
        rolled_rarity = roll_rarity(floor_number=floor_number, enemy_tier="mid", rng=rng)

        # Apply rarity offset + monster rarity bonus
        rarity_idx = _RARITY_TIERS.index(rolled_rarity) if rolled_rarity in _RARITY_TIERS else 0
        final_idx = max(0, min(len(_RARITY_TIERS) - 1, rarity_idx + slot_rarity_offset + rarity_bonus))
        final_rarity = _RARITY_TIERS[final_idx]

        item = generate_item(
            base_type_id=base_type_id,
            rarity=final_rarity,
            item_level=floor_number,
            seed=rng.randint(0, 2**31),
        )
        if item:
            equipment[slot_name] = item.model_dump()

    # Generate potions
    potion_cfg = loadout_cfg.get("potions")
    if potion_cfg:
        potion_type = potion_cfg.get("type", "health_potion")
        count_range = potion_cfg.get("count", [0, 0])
        if isinstance(count_range, list) and len(count_range) == 2:
            potion_count = rng.randint(count_range[0], count_range[1])
        else:
            potion_count = 0

        for _ in range(potion_count):
            potion = generate_item(base_type_id=potion_type, rarity="common", item_level=1)
            if potion:
                inventory.append(potion.model_dump())

    return equipment, inventory


def _apply_loadout_to_unit(unit: PlayerState, equipment: dict, inventory: list) -> None:
    """Directly assign equipment and inventory to a unit, then recalculate stats.

    Bypasses equip_item() match lookup since unit may not be in match dict yet.
    """
    from app.core.equipment_manager import _recalculate_effective_stats
    from app.models.items import StatBonuses

    unit.equipment = equipment
    unit.inventory = inventory

    # Apply core stat bonuses from equipment (attack_damage, ranged_damage, armor, max_hp)
    for slot_name, item_data in equipment.items():
        if not item_data:
            continue
        bonuses = StatBonuses(**item_data.get("stat_bonuses", {}))
        unit.attack_damage += bonuses.attack_damage
        unit.ranged_damage += bonuses.ranged_damage
        unit.armor += bonuses.armor
        if bonuses.max_hp > 0:
            unit.max_hp += bonuses.max_hp
            unit.hp += bonuses.max_hp

    # Recalculate derived stats (crit, dodge, etc.) from full equipment set
    _recalculate_effective_stats(unit)


# ---------- Phase 28E: Hero Party Loadout Generation ----------

# Preferred armor by class — maps class preferred_armor to armor_category pool
_CLASS_ARMOR_POOL: dict[str, list[str]] = {
    "heavy": ["heavy"],
    "light": ["light"],
    "cloth": ["cloth"],
}

# Match tier → rarity tier index offset (controls baseline gear quality)
_MATCH_TIER_BONUS: dict[str, int] = {
    "low": 0,
    "mid": 1,
    "high": 2,
}


def generate_hero_loadout(
    class_id: str,
    class_def=None,
    floor_number: int = 1,
    match_tier: str = "mid",
    rng: random.Random | None = None,
) -> tuple[dict, list]:
    """Generate class-appropriate equipment + potions for an AI hero.

    Uses the class's allowed_weapon_categories and preferred_armor to
    produce a loadout that mirrors what a real player might have.

    Args:
        class_id: The hero's class (e.g., "crusader", "ranger").
        class_def: ClassDefinition (optional — loaded if not provided).
        floor_number: Scales item_level and rarity.
        match_tier: "low"/"mid"/"high" — controls baseline rarity.
        rng: Optional seeded RNG.

    Returns:
        (equipment_dict, inventory_list) — ready to assign to PlayerState.
    """
    from app.core.item_generator import generate_item, roll_rarity
    from app.core.loot import load_items_config
    from app.models.player import get_class_definition

    if class_def is None:
        class_def = get_class_definition(class_id)
    if class_def is None:
        return {}, []

    if rng is None:
        rng = random.Random()

    items_config = load_items_config()
    equipment: dict = {}
    inventory: list = []

    tier_bonus = _MATCH_TIER_BONUS.get(match_tier, 1)

    # --- Weapon ---
    weapon_cats = getattr(class_def, 'allowed_weapon_categories', None) or []
    if weapon_cats:
        weapon_candidates = []
        for item_id, item_data in items_config.items():
            if item_data.get("equip_slot") != "weapon":
                continue
            if item_data.get("item_type") == "consumable":
                continue
            if item_data.get("weapon_category") in weapon_cats:
                weapon_candidates.append(item_id)
        if weapon_candidates:
            base_type_id = rng.choice(weapon_candidates)
            rolled_rarity = roll_rarity(floor_number=floor_number, enemy_tier="mid", rng=rng)
            rarity_idx = _RARITY_TIERS.index(rolled_rarity) if rolled_rarity in _RARITY_TIERS else 0
            final_idx = max(0, min(len(_RARITY_TIERS) - 1, rarity_idx + tier_bonus))
            final_rarity = _RARITY_TIERS[final_idx]
            item = generate_item(
                base_type_id=base_type_id,
                rarity=final_rarity,
                item_level=max(1, floor_number),
                seed=rng.randint(0, 2**31),
            )
            if item:
                equipment["weapon"] = item.model_dump()

    # --- Armor ---
    preferred_armor = getattr(class_def, 'preferred_armor', '') or ''
    armor_pool = _CLASS_ARMOR_POOL.get(preferred_armor, ["light"])
    armor_candidates = []
    for item_id, item_data in items_config.items():
        if item_data.get("equip_slot") != "armor":
            continue
        if item_data.get("item_type") == "consumable":
            continue
        if item_data.get("armor_category") in armor_pool:
            armor_candidates.append(item_id)
    if armor_candidates:
        base_type_id = rng.choice(armor_candidates)
        rolled_rarity = roll_rarity(floor_number=floor_number, enemy_tier="mid", rng=rng)
        rarity_idx = _RARITY_TIERS.index(rolled_rarity) if rolled_rarity in _RARITY_TIERS else 0
        final_idx = max(0, min(len(_RARITY_TIERS) - 1, rarity_idx + tier_bonus))
        final_rarity = _RARITY_TIERS[final_idx]
        item = generate_item(
            base_type_id=base_type_id,
            rarity=final_rarity,
            item_level=max(1, floor_number),
            seed=rng.randint(0, 2**31),
        )
        if item:
            equipment["armor"] = item.model_dump()

    # --- Potions (2-3 health potions) ---
    potion_count = rng.randint(2, 3)
    for _ in range(potion_count):
        potion = generate_item(base_type_id="health_potion", rarity="common", item_level=1)
        if potion:
            inventory.append(potion.model_dump())

    return equipment, inventory
