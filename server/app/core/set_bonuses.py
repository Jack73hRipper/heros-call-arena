"""
Set Bonuses — Phase 16E set item bonus calculation and application.

Manages the detection of equipped set pieces, calculation of active set bonuses,
and application of stat/skill modifiers from set bonuses.

Key functions:
  - load_sets_config(): Load set definitions from sets_config.json
  - calculate_active_set_bonuses(): Determine which set bonuses are active
  - apply_set_stat_bonuses(): Apply stat bonuses from active sets to effective stats
  - get_set_skill_modifiers(): Get skill-specific modifiers from active set bonuses
  - get_set_special_effects(): Get special combat effects from active set bonuses
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models.items import StatBonuses

# ---------- Config Paths ----------

_configs_dir = Path(__file__).resolve().parent.parent.parent / "configs"
_sets_config_path = _configs_dir / "sets_config.json"

# ---------- Cache ----------

_sets_cache: dict | None = None


# ---------- Config Loader ----------

def load_sets_config(path: Path | None = None) -> dict:
    """Load set definitions from JSON config. Caches after first load.

    Returns dict with 'sets', 'drop_rules', and 'class_affinity_weights' keys.
    """
    global _sets_cache
    if _sets_cache is not None:
        return _sets_cache

    config_file = path or _sets_config_path
    if config_file.exists():
        with open(config_file, "r") as f:
            _sets_cache = json.load(f)
    else:
        _sets_cache = {"sets": {}, "drop_rules": {}, "class_affinity_weights": {}}
    return _sets_cache


def clear_sets_cache() -> None:
    """Clear the cached config. Useful for testing."""
    global _sets_cache
    _sets_cache = None


# ---------- Set Detection ----------

def get_all_set_ids(sets_config: dict | None = None) -> list[str]:
    """Return all set IDs from the sets config."""
    config = sets_config or load_sets_config()
    return list(config.get("sets", {}).keys())


def get_set_definition(set_id: str, sets_config: dict | None = None) -> dict | None:
    """Return the raw set definition dict, or None if not found."""
    config = sets_config or load_sets_config()
    return config.get("sets", {}).get(set_id)


def _count_equipped_set_pieces(equipment: dict, set_def: dict) -> int:
    """Count how many pieces of a given set are equipped.

    Args:
        equipment: Player's equipment dict (slot_name -> item_data dict or None).
        set_def: The set definition from sets_config.json.

    Returns:
        Number of equipped pieces belonging to this set.
    """
    if not equipment:
        return 0

    set_piece_ids = {p["piece_id"] for p in set_def.get("pieces", [])}
    count = 0

    for slot_name, item_data in equipment.items():
        if not item_data:
            continue
        # Check by item_id matching set piece_id
        item_id = item_data.get("item_id", "")
        if item_id in set_piece_ids:
            count += 1

    return count


def calculate_active_set_bonuses(equipment: dict, sets_config: dict | None = None) -> list[dict]:
    """Given a hero's equipment, determine which set bonuses are active.

    Scans all known sets for equipped pieces, and returns active bonus dicts
    for any set with enough pieces to trigger a bonus tier.

    Args:
        equipment: Player's equipment dict (slot_name -> item_data dict or None).
        sets_config: Override config (for testing).

    Returns:
        List of active bonus dicts:
        [
            {
                "set_id": "crusaders_oath",
                "set_name": "Crusader's Oath",
                "pieces_equipped": 2,
                "pieces_total": 3,
                "bonuses": [
                    {
                        "pieces_required": 2,
                        "stat_bonuses": {...},
                        "skill_modifiers": {...},
                        "description": "..."
                    }
                ]
            },
            ...
        ]
    """
    config = sets_config or load_sets_config()
    sets = config.get("sets", {})
    active: list[dict] = []

    for set_id, set_def in sets.items():
        pieces_equipped = _count_equipped_set_pieces(equipment, set_def)
        if pieces_equipped < 2:
            continue  # Need at least 2 pieces for any set bonus

        pieces_total = len(set_def.get("pieces", []))

        # Collect all bonus tiers that are met
        active_bonuses = []
        for bonus in set_def.get("bonuses", []):
            if pieces_equipped >= bonus.get("pieces_required", 99):
                active_bonuses.append(bonus)

        if active_bonuses:
            active.append({
                "set_id": set_id,
                "set_name": set_def.get("name", set_id),
                "pieces_equipped": pieces_equipped,
                "pieces_total": pieces_total,
                "bonuses": active_bonuses,
            })

    return active


# ---------- Stat Application ----------

def get_set_stat_totals(active_sets: list[dict]) -> StatBonuses:
    """Sum up all stat bonuses from active set bonuses.

    For sets with multiple active tiers (e.g., both 2/3 and 3/3),
    only the HIGHEST tier's stat bonuses are applied (not cumulative).
    This matches Diablo convention — the highest tier replaces lower tier stats.

    Args:
        active_sets: List of active set bonus dicts from calculate_active_set_bonuses().

    Returns:
        Aggregated StatBonuses from all active set bonuses.
    """
    totals = StatBonuses()

    for active_set in active_sets:
        bonuses = active_set.get("bonuses", [])
        if not bonuses:
            continue

        # Use the highest tier (last in the sorted list)
        highest_bonus = max(bonuses, key=lambda b: b.get("pieces_required", 0))
        stat_dict = highest_bonus.get("stat_bonuses", {})

        for stat_key, value in stat_dict.items():
            if hasattr(totals, stat_key):
                current = getattr(totals, stat_key)
                setattr(totals, stat_key, current + value)

    return totals


def apply_set_stat_bonuses(player, active_sets: list[dict]) -> None:
    """Apply stat bonuses from active sets to the player's effective stats.

    This is called after equipment stat recalculation to layer set bonuses
    on top of equipment stats. Modifies player in-place.

    Args:
        player: PlayerState instance.
        active_sets: List of active set bonus dicts.
    """
    from app.core.combat import get_combat_config

    config = get_combat_config()
    dodge_cap = config.get("dodge_cap", 0.40)
    crit_damage_cap = config.get("crit_damage_cap", 3.0)
    dr_cap = config.get("damage_reduction_cap", 0.50)
    cdr_cap = config.get("cooldown_reduction_cap", 0.30)

    set_totals = get_set_stat_totals(active_sets)

    # Apply stat bonuses with caps
    player.crit_chance = min(0.50, player.crit_chance + set_totals.crit_chance)
    player.crit_damage = min(crit_damage_cap, player.crit_damage + set_totals.crit_damage)
    player.dodge_chance = min(dodge_cap, player.dodge_chance + set_totals.dodge_chance)
    player.damage_reduction_pct = min(dr_cap, player.damage_reduction_pct + set_totals.damage_reduction_pct)
    player.hp_regen += set_totals.hp_regen
    player.move_speed += set_totals.move_speed
    player.life_on_hit += set_totals.life_on_hit
    player.cooldown_reduction_pct = min(cdr_cap, player.cooldown_reduction_pct + set_totals.cooldown_reduction_pct)
    player.skill_damage_pct += set_totals.skill_damage_pct
    player.thorns += set_totals.thorns
    player.gold_find_pct += set_totals.gold_find_pct
    player.magic_find_pct += set_totals.magic_find_pct
    player.holy_damage_pct += set_totals.holy_damage_pct
    player.dot_damage_pct += set_totals.dot_damage_pct
    player.heal_power_pct += set_totals.heal_power_pct
    player.armor_pen += set_totals.armor_pen

    # Apply flat stat bonuses (armor, max_hp, attack_damage, ranged_damage)
    player.armor += set_totals.armor
    player.attack_damage += set_totals.attack_damage
    player.ranged_damage += set_totals.ranged_damage

    # max_hp bonus also increases current hp
    if set_totals.max_hp > 0:
        player.max_hp += set_totals.max_hp
        player.hp += set_totals.max_hp


def remove_set_stat_bonuses(player, active_sets: list[dict]) -> None:
    """Remove stat bonuses from previously active sets.

    Called before recalculating set bonuses to avoid double-counting.
    Modifies player in-place.

    Args:
        player: PlayerState instance.
        active_sets: List of previously active set bonus dicts.
    """
    set_totals = get_set_stat_totals(active_sets)

    player.crit_chance = max(0.0, player.crit_chance - set_totals.crit_chance)
    player.crit_damage = max(0.0, player.crit_damage - set_totals.crit_damage)
    player.dodge_chance = max(0.0, player.dodge_chance - set_totals.dodge_chance)
    player.damage_reduction_pct = max(0.0, player.damage_reduction_pct - set_totals.damage_reduction_pct)
    player.hp_regen = max(0, player.hp_regen - set_totals.hp_regen)
    player.move_speed = max(0, player.move_speed - set_totals.move_speed)
    player.life_on_hit = max(0, player.life_on_hit - set_totals.life_on_hit)
    player.cooldown_reduction_pct = max(0.0, player.cooldown_reduction_pct - set_totals.cooldown_reduction_pct)
    player.skill_damage_pct = max(0.0, player.skill_damage_pct - set_totals.skill_damage_pct)
    player.thorns = max(0, player.thorns - set_totals.thorns)
    player.gold_find_pct = max(0.0, player.gold_find_pct - set_totals.gold_find_pct)
    player.magic_find_pct = max(0.0, player.magic_find_pct - set_totals.magic_find_pct)
    player.holy_damage_pct = max(0.0, player.holy_damage_pct - set_totals.holy_damage_pct)
    player.dot_damage_pct = max(0.0, player.dot_damage_pct - set_totals.dot_damage_pct)
    player.heal_power_pct = max(0.0, player.heal_power_pct - set_totals.heal_power_pct)
    player.armor_pen = max(0, player.armor_pen - set_totals.armor_pen)

    player.armor = max(0, player.armor - set_totals.armor)
    player.attack_damage = max(0, player.attack_damage - set_totals.attack_damage)
    player.ranged_damage = max(0, player.ranged_damage - set_totals.ranged_damage)

    if set_totals.max_hp > 0:
        player.max_hp = max(1, player.max_hp - set_totals.max_hp)
        player.hp = min(player.hp, player.max_hp)


# ---------- Skill Modifiers ----------

def get_set_skill_modifiers(active_sets: list[dict]) -> dict:
    """Return skill-specific modifiers from active set bonuses.

    Aggregates skill modifiers from all active set bonus tiers.
    For sets with multiple tiers, uses the highest tier only.

    Returns:
        Dict mapping skill_id -> modifier dict.
        e.g., {"taunt": {"duration_bonus": 1}, "heal": {"cooldown_reduction": 1}}
    """
    modifiers: dict = {}

    for active_set in active_sets:
        bonuses = active_set.get("bonuses", [])
        if not bonuses:
            continue

        # Use the highest tier's skill modifiers
        highest_bonus = max(bonuses, key=lambda b: b.get("pieces_required", 0))
        skill_mods = highest_bonus.get("skill_modifiers", {})

        for skill_id, mod in skill_mods.items():
            if skill_id not in modifiers:
                modifiers[skill_id] = {}
            # Merge modifiers (if same skill appears in multiple sets, sum values)
            for key, value in mod.items():
                if isinstance(value, (int, float)):
                    modifiers[skill_id][key] = modifiers[skill_id].get(key, 0) + value
                else:
                    modifiers[skill_id][key] = value

    return modifiers


def get_set_special_effects(active_sets: list[dict]) -> list[dict]:
    """Return special combat effects from active set bonuses.

    These are non-stat, non-skill effects like 'ranged_crit_pierce'.

    Returns:
        List of special effect dicts with set_id and effect data.
    """
    effects: list[dict] = []

    for active_set in active_sets:
        bonuses = active_set.get("bonuses", [])
        if not bonuses:
            continue

        highest_bonus = max(bonuses, key=lambda b: b.get("pieces_required", 0))
        specials = highest_bonus.get("special_effects", {})

        for effect_id, effect_data in specials.items():
            effects.append({
                "set_id": active_set["set_id"],
                "effect_id": effect_id,
                **effect_data,
            })

    return effects
