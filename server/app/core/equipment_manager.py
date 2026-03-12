"""
Equipment Manager — Handles in-match equipment operations.

Extracted from match_manager.py during P2 refactoring.
Manages equipping/unequipping items, stat bonuses, item transfers,
and party member inventory access.
"""

from __future__ import annotations

from app.models.player import PlayerState

# Shared state dicts — imported from match_manager
from app.core.match_manager import (
    _player_states,
)


def equip_item(match_id: str, player_id: str, item_id: str) -> dict | None:
    """Equip an item from inventory to the appropriate equipment slot.

    Returns a dict with result info on success, or None on failure.
    Handles swap: if the slot is already occupied, the old item goes back to inventory.
    Applies stat bonuses (max_hp increase also raises current hp).

    Phase 16B: Supports instance_id lookup for generated items with affixes.
    Falls back to item_id match for legacy/static items.
    """
    from app.models.items import Item, Equipment, EquipSlot, StatBonuses

    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player or not player.is_alive:
        return None

    # Find the item in inventory — try instance_id first, then item_id
    inv_index = None
    item_data = None

    # Phase 16B: First try instance_id match (for generated items with UUID)
    for idx, it in enumerate(player.inventory):
        if it.get("instance_id") and it.get("instance_id") == item_id:
            inv_index = idx
            item_data = it
            break

    # Fallback: item_id match (for legacy/static items)
    if item_data is None:
        for idx, it in enumerate(player.inventory):
            if it.get("item_id") == item_id:
                inv_index = idx
                item_data = it
                break

    if item_data is None:
        return None

    # Parse item to check equip slot
    try:
        item = Item(**item_data)
    except Exception:
        return None

    if item.equip_slot is None:
        return None  # Consumables can't be equipped

    # Phase 16: Weapon class-lock — reject weapons incompatible with class
    if item.equip_slot == EquipSlot.WEAPON and player.class_id:
        weapon_cat = item_data.get("weapon_category", "")
        if weapon_cat:
            from app.models.player import get_class_definition
            class_def = get_class_definition(player.class_id)
            if class_def and class_def.allowed_weapon_categories:
                if weapon_cat not in class_def.allowed_weapon_categories:
                    return None  # Class cannot equip this weapon category

    slot_name = item.equip_slot.value  # "weapon", "armor", or "accessory"

    # Remove from inventory
    player.inventory.pop(inv_index)

    # Get previously equipped item (if any) and put it back in inventory
    previously_equipped = player.equipment.get(slot_name)
    if previously_equipped:
        player.inventory.append(previously_equipped)

    # Place new item in equipment slot
    player.equipment[slot_name] = item_data

    # Apply stat bonuses — recalculate effective stats
    _apply_equipment_stats(player, previously_equipped, item_data)

    return {
        "player_id": player_id,
        "slot": slot_name,
        "equipped": item_data,
        "unequipped": previously_equipped,
        "inventory": list(player.inventory),
        "equipment": dict(player.equipment),
        "player_stats": {
            "hp": player.hp,
            "max_hp": player.max_hp,
            "attack_damage": player.attack_damage,
            "ranged_damage": player.ranged_damage,
            "armor": player.armor,
            "crit_chance": player.crit_chance,
            "crit_damage": player.crit_damage,
            "dodge_chance": player.dodge_chance,
            "damage_reduction_pct": player.damage_reduction_pct,
            "hp_regen": player.hp_regen,
            "move_speed": player.move_speed,
            "life_on_hit": player.life_on_hit,
            "cooldown_reduction_pct": player.cooldown_reduction_pct,
            "skill_damage_pct": player.skill_damage_pct,
            "thorns": player.thorns,
            "gold_find_pct": player.gold_find_pct,
            "magic_find_pct": player.magic_find_pct,
            "holy_damage_pct": player.holy_damage_pct,
            "dot_damage_pct": player.dot_damage_pct,
            "heal_power_pct": player.heal_power_pct,
            "armor_pen": player.armor_pen,
        },
        "active_set_bonuses": player.active_set_bonuses,
    }


def unequip_item(match_id: str, player_id: str, slot_name: str) -> dict | None:
    """Unequip an item from an equipment slot back to inventory.

    Returns a dict with result info on success, or None on failure.
    """
    from app.models.items import Item, EquipSlot, INVENTORY_MAX_CAPACITY

    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player or not player.is_alive:
        return None

    # Check that the slot is valid and occupied
    if slot_name not in ("weapon", "armor", "accessory"):
        return None

    item_data = player.equipment.get(slot_name)
    if not item_data:
        return None  # Slot is empty

    # Check inventory space
    if len(player.inventory) >= INVENTORY_MAX_CAPACITY:
        return None  # Inventory full — can't unequip

    # Remove from equipment, add to inventory
    player.equipment[slot_name] = None

    # Remove stat bonuses
    _remove_equipment_stats(player, item_data)

    player.inventory.append(item_data)

    return {
        "player_id": player_id,
        "slot": slot_name,
        "unequipped": item_data,
        "inventory": list(player.inventory),
        "equipment": dict(player.equipment),
        "player_stats": {
            "hp": player.hp,
            "max_hp": player.max_hp,
            "attack_damage": player.attack_damage,
            "ranged_damage": player.ranged_damage,
            "armor": player.armor,            "crit_chance": player.crit_chance,
            "crit_damage": player.crit_damage,
            "dodge_chance": player.dodge_chance,
            "damage_reduction_pct": player.damage_reduction_pct,
            "hp_regen": player.hp_regen,
            "move_speed": player.move_speed,
            "life_on_hit": player.life_on_hit,
            "cooldown_reduction_pct": player.cooldown_reduction_pct,
            "skill_damage_pct": player.skill_damage_pct,
            "thorns": player.thorns,
            "gold_find_pct": player.gold_find_pct,
            "magic_find_pct": player.magic_find_pct,
            "holy_damage_pct": player.holy_damage_pct,
            "dot_damage_pct": player.dot_damage_pct,
            "heal_power_pct": player.heal_power_pct,
            "armor_pen": player.armor_pen,        },
        "active_set_bonuses": player.active_set_bonuses,
    }


def _apply_equipment_stats(player: PlayerState, old_item_data: dict | None, new_item_data: dict) -> None:
    """Apply stat changes when equipping a new item (and removing the old one).

    For max_hp bonuses: increases max_hp and current hp proportionally.
    Phase 16A: Recalculates all effective stats from full equipment set.
    """
    from app.models.items import StatBonuses

    # Remove old item bonuses
    if old_item_data:
        old_bonuses = StatBonuses(**old_item_data.get("stat_bonuses", {}))
        if old_bonuses.max_hp > 0:
            player.max_hp -= old_bonuses.max_hp
            player.hp = min(player.hp, player.max_hp)

    # Apply new item bonuses
    new_bonuses = StatBonuses(**new_item_data.get("stat_bonuses", {}))
    if new_bonuses.max_hp > 0:
        player.max_hp += new_bonuses.max_hp
        player.hp += new_bonuses.max_hp  # Grant bonus HP immediately

    # Phase 16A: Recalculate all effective stats from full equipment
    _recalculate_effective_stats(player)

    # Phase 16E: Recalculate set bonuses
    _recalculate_set_bonuses(player)


def _remove_equipment_stats(player: PlayerState, item_data: dict) -> None:
    """Remove stat bonuses when unequipping an item."""
    from app.models.items import StatBonuses

    bonuses = StatBonuses(**item_data.get("stat_bonuses", {}))
    if bonuses.max_hp > 0:
        player.max_hp -= bonuses.max_hp
        player.hp = min(player.hp, player.max_hp)

    # Phase 16A: Recalculate all effective stats from remaining equipment
    _recalculate_effective_stats(player)

    # Phase 16E: Recalculate set bonuses
    _recalculate_set_bonuses(player)


def _recalculate_effective_stats(player: PlayerState) -> None:
    """Recalculate Phase 16A effective stats from the player's full equipment set.

    Aggregates all new stats from equipment and applies configurable caps.
    Called after every equip/unequip operation.
    """
    from app.models.items import Item, Equipment, EquipSlot, StatBonuses
    from app.core.combat import get_combat_config

    config = get_combat_config()
    dodge_cap = config.get("dodge_cap", 0.40)
    crit_damage_cap = config.get("crit_damage_cap", 3.0)
    dr_cap = config.get("damage_reduction_cap", 0.50)
    cdr_cap = config.get("cooldown_reduction_cap", 0.30)
    base_crit_chance = config.get("base_crit_chance", 0.05)
    base_crit_damage = config.get("base_crit_damage", 1.5)

    # Sum all equipment bonuses
    totals = StatBonuses()
    for slot_name, item_data in player.equipment.items():
        if item_data:
            bonuses = StatBonuses(**item_data.get("stat_bonuses", {}))
            totals.crit_chance += bonuses.crit_chance
            totals.crit_damage += bonuses.crit_damage
            totals.dodge_chance += bonuses.dodge_chance
            totals.damage_reduction_pct += bonuses.damage_reduction_pct
            totals.hp_regen += bonuses.hp_regen
            totals.move_speed += bonuses.move_speed
            totals.life_on_hit += bonuses.life_on_hit
            totals.cooldown_reduction_pct += bonuses.cooldown_reduction_pct
            totals.skill_damage_pct += bonuses.skill_damage_pct
            totals.thorns += bonuses.thorns
            totals.gold_find_pct += bonuses.gold_find_pct
            totals.magic_find_pct += bonuses.magic_find_pct
            totals.holy_damage_pct += bonuses.holy_damage_pct
            totals.dot_damage_pct += bonuses.dot_damage_pct
            totals.heal_power_pct += bonuses.heal_power_pct
            totals.armor_pen += bonuses.armor_pen

    # Apply to PlayerState with caps
    player.crit_chance = min(0.50, base_crit_chance + totals.crit_chance)
    player.crit_damage = min(crit_damage_cap, base_crit_damage + totals.crit_damage)
    player.dodge_chance = min(dodge_cap, totals.dodge_chance)
    player.damage_reduction_pct = min(dr_cap, totals.damage_reduction_pct)
    player.hp_regen = totals.hp_regen
    player.move_speed = totals.move_speed
    player.life_on_hit = totals.life_on_hit
    player.cooldown_reduction_pct = min(cdr_cap, totals.cooldown_reduction_pct)
    player.skill_damage_pct = totals.skill_damage_pct
    player.thorns = totals.thorns
    player.gold_find_pct = totals.gold_find_pct
    player.magic_find_pct = totals.magic_find_pct
    player.holy_damage_pct = totals.holy_damage_pct
    player.dot_damage_pct = totals.dot_damage_pct
    player.heal_power_pct = totals.heal_power_pct
    player.armor_pen = totals.armor_pen


def _recalculate_set_bonuses(player: PlayerState) -> None:
    """Recalculate Phase 16E set bonuses from the player's equipped items.

    1. Remove old set stat bonuses
    2. Calculate new active set bonuses
    3. Apply new set stat bonuses
    4. Update active_set_bonuses on PlayerState
    """
    from app.core.set_bonuses import (
        calculate_active_set_bonuses,
        apply_set_stat_bonuses,
        remove_set_stat_bonuses,
    )

    # Remove old set bonuses (if any were active)
    old_sets = player.active_set_bonuses
    if old_sets:
        remove_set_stat_bonuses(player, old_sets)

    # Calculate new active set bonuses from current equipment
    new_sets = calculate_active_set_bonuses(player.equipment)

    # Apply new set stat bonuses
    if new_sets:
        apply_set_stat_bonuses(player, new_sets)

    # Store active set bonuses on player for client display and skill checks
    player.active_set_bonuses = new_sets


def transfer_item_in_match(
    match_id: str, player_id: str, from_unit_id: str, to_unit_id: str, item_index: int
) -> dict | None:
    """Transfer an item between two party members' inventories during a match.

    The player must own/control both units (or one can be themselves).
    Returns a result dict on success, None on failure.
    """
    from app.models.items import INVENTORY_MAX_CAPACITY
    from app.core.match_manager import is_party_member

    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player:
        return None

    from_unit = players.get(from_unit_id)
    to_unit = players.get(to_unit_id)
    if not from_unit or not to_unit:
        return None

    # Both units must be alive
    if not from_unit.is_alive or not to_unit.is_alive:
        return None

    # Validate ownership: each unit must be the player themselves or a party member
    if from_unit_id != player_id and not is_party_member(match_id, player_id, from_unit_id):
        return None
    if to_unit_id != player_id and not is_party_member(match_id, player_id, to_unit_id):
        return None

    # Can't transfer to self
    if from_unit_id == to_unit_id:
        return None

    # Validate item index
    if item_index < 0 or item_index >= len(from_unit.inventory):
        return None

    # Check destination capacity
    if len(to_unit.inventory) >= INVENTORY_MAX_CAPACITY:
        return None

    # Perform transfer
    item = from_unit.inventory.pop(item_index)
    to_unit.inventory.append(item)

    return {
        "from_unit_id": from_unit_id,
        "to_unit_id": to_unit_id,
        "item": item,
        "from_inventory": list(from_unit.inventory),
        "to_inventory": list(to_unit.inventory),
        "from_equipment": dict(from_unit.equipment),
        "to_equipment": dict(to_unit.equipment),
    }


def get_party_member_inventory(match_id: str, player_id: str, unit_id: str) -> dict | None:
    """Get inventory and equipment for a party member (or self).

    Returns dict with inventory/equipment, or None if not authorized.
    """
    from app.core.match_manager import is_party_member

    players = _player_states.get(match_id, {})
    if unit_id == player_id:
        unit = players.get(player_id)
        if not unit:
            return None
        return {
            "unit_id": unit_id,
            "inventory": list(unit.inventory),
            "equipment": dict(unit.equipment),
        }

    if not is_party_member(match_id, player_id, unit_id):
        return None

    unit = players.get(unit_id)
    if not unit:
        return None

    return {
        "unit_id": unit_id,
        "inventory": list(unit.inventory),
        "equipment": dict(unit.equipment),
    }
