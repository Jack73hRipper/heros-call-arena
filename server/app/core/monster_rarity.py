"""
Phase 18A+18B+18G — Monster Rarity Data Model, Config Loader, Affix Engine & Super Uniques.

Phase 18A provides:
- load_monster_rarity_config() — cached config loader for monster_rarity_config.json
- validate_monster_rarity_config() — startup validation for config integrity
- Helper accessors: get_rarity_tier(), get_champion_type(), get_affix(), get_affix_rules(), get_spawn_chances()

Phase 18B adds:
- roll_monster_rarity() — roll whether a spawn becomes normal/champion/rare
- roll_champion_type() — pick a random champion type
- roll_affixes() — roll N random affixes respecting compatibility rules
- generate_rare_name() — generate D2-style rare name from affix pools
- apply_rarity_to_player() — apply tier scaling + champion + affix stat modifiers
- create_minions() — create Normal-tier minions for a Rare leader

Phase 18G adds:
- load_super_uniques_config() — cached config loader for super_uniques_config.json
- validate_super_uniques_config() — validation for super unique config integrity
- get_super_unique() — get a single super unique definition
- get_eligible_super_uniques() — find super uniques eligible for a floor
- roll_super_unique_spawn() — roll whether a boss room gets a super unique
- create_super_unique_player() — build a super unique PlayerState with fixed stats/affixes
- create_super_unique_retinue() — create the fixed retinue spawn dicts
"""

from __future__ import annotations

import json
import math
import random
import uuid
from pathlib import Path
from typing import Any


# ---------- Config Path & Cache ----------

_config_path = Path(__file__).resolve().parent.parent.parent / "configs" / "monster_rarity_config.json"
_config_cache: dict[str, Any] | None = None

_su_config_path = Path(__file__).resolve().parent.parent.parent / "configs" / "super_uniques_config.json"
_su_config_cache: dict[str, Any] | None = None

VALID_RARITY_TIERS = {"normal", "champion", "rare", "super_unique"}
VALID_CHAMPION_TYPES = {"berserker", "fanatic", "ghostly", "resilient", "possessed"}


def load_monster_rarity_config(path: Path | None = None) -> dict[str, Any]:
    """Load and cache monster_rarity_config.json.

    Returns the full config dict with keys:
    - rarity_tiers, champion_types, affixes, affix_rules, spawn_chances
    """
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    config_file = path or _config_path
    if not config_file.exists():
        raise FileNotFoundError(f"Monster rarity config not found: {config_file}")

    with open(config_file, "r") as f:
        _config_cache = json.load(f)

    return _config_cache


def clear_monster_rarity_cache() -> None:
    """Clear the cached config (useful for tests)."""
    global _config_cache, _su_config_cache
    _config_cache = None
    _su_config_cache = None


# ---------- Super Uniques Config Loader ----------

def load_super_uniques_config(path: Path | None = None) -> dict[str, Any]:
    """Load and cache super_uniques_config.json.

    Returns the full config dict with keys:
    - super_uniques, spawn_rules
    """
    global _su_config_cache
    if _su_config_cache is not None:
        return _su_config_cache

    config_file = path or _su_config_path
    if not config_file.exists():
        # Return empty defaults if no super uniques config exists yet
        _su_config_cache = {"super_uniques": {}, "spawn_rules": {}}
        return _su_config_cache

    with open(config_file, "r") as f:
        _su_config_cache = json.load(f)

    return _su_config_cache


def get_super_unique(su_id: str) -> dict[str, Any] | None:
    """Get a super unique definition by ID."""
    config = load_super_uniques_config()
    return config.get("super_uniques", {}).get(su_id)


def get_all_super_unique_ids() -> list[str]:
    """Get all super unique IDs from config."""
    config = load_super_uniques_config()
    return list(config.get("super_uniques", {}).keys())


def get_super_unique_spawn_rules() -> dict[str, Any]:
    """Get the spawn rules for super uniques."""
    config = load_super_uniques_config()
    return config.get("spawn_rules", {})


# ---------- Accessors ----------

def get_rarity_tier(tier_id: str) -> dict[str, Any] | None:
    """Get a rarity tier config by ID (normal, champion, rare, super_unique)."""
    config = load_monster_rarity_config()
    return config.get("rarity_tiers", {}).get(tier_id)


def get_champion_type(type_id: str) -> dict[str, Any] | None:
    """Get a champion type config by ID (berserker, fanatic, ghostly, resilient, possessed)."""
    config = load_monster_rarity_config()
    return config.get("champion_types", {}).get(type_id)


def get_affix(affix_id: str) -> dict[str, Any] | None:
    """Get an affix config by ID (extra_strong, fire_enchanted, etc.)."""
    config = load_monster_rarity_config()
    return config.get("affixes", {}).get(affix_id)


def get_all_affix_ids() -> list[str]:
    """Get all affix IDs from config."""
    config = load_monster_rarity_config()
    return list(config.get("affixes", {}).keys())


def get_affix_rules() -> dict[str, Any]:
    """Get the affix compatibility rules."""
    config = load_monster_rarity_config()
    return config.get("affix_rules", {})


def get_spawn_chances() -> dict[str, Any]:
    """Get the spawn chance config for rarity upgrades."""
    config = load_monster_rarity_config()
    return config.get("spawn_chances", {})


def get_floor_override(floor_number: int) -> dict[str, Any]:
    """Get floor-tier-specific overrides for rarity spawning (Phase 5).

    Looks up the first entry in ``spawn_chances.floor_overrides`` whose
    ``max_floor`` is ≥ *floor_number*.  Returns an empty dict if no
    matching entry exists or if the ``floor_overrides`` key is absent
    (backward-compatible — floors 6+ use base config values).

    Possible override keys:
    - ``max_enhanced_per_room`` (int): caps enhanced enemies per room
    - ``max_rare_minions`` (int): caps minion count for rare spawns
    - ``rare_affix_count`` ([int, int]): overrides affix count range for rares
    """
    spawn_chances = get_spawn_chances()
    floor_overrides = spawn_chances.get("floor_overrides", [])

    for entry in floor_overrides:
        if floor_number <= entry.get("max_floor", 99):
            return entry

    return {}


# ---------- Difficulty Budget (Phase 3 — Spawn Distribution Overhaul) ----------

def get_difficulty_budget_config() -> dict[str, Any]:
    """Get the difficulty_budget section from monster_rarity_config.json.

    Returns an empty dict if the section is absent (backward-compatible).
    """
    config = load_monster_rarity_config()
    return config.get("difficulty_budget", {})


def get_rarity_cost(rarity: str) -> int:
    """Return the difficulty point cost for a rarity tier.

    Costs are loaded from config ``difficulty_budget.rarity_costs``.
    Falls back to sensible defaults when the config section is absent.
    """
    budget_cfg = get_difficulty_budget_config()
    costs = budget_cfg.get("rarity_costs", {})
    defaults = {"normal": 1, "champion": 3, "rare": 5, "super_unique": 8}
    cost = costs.get(rarity)
    if cost is not None:
        return int(cost)
    return defaults.get(rarity, 1)


def get_room_budget(floor_number: int, enemy_count: int) -> int:
    """Compute the difficulty point budget for a room.

    ``budget = base + per_enemy × enemy_count``

    The *base* and *per_enemy* values are looked up from the
    ``difficulty_budget.floor_budgets`` table by matching the first entry
    whose ``max_floor`` is ≥ *floor_number*.  If no entry matches (or the
    config section is absent) sensible defaults are used.
    """
    budget_cfg = get_difficulty_budget_config()
    floor_budgets = budget_cfg.get("floor_budgets", [])

    # Default fallback (generous — effectively uncapped)
    base = 15
    per_enemy = 2.5

    for entry in floor_budgets:
        if floor_number <= entry.get("max_floor", 99):
            base = entry.get("base", base)
            per_enemy = entry.get("per_enemy", per_enemy)
            break

    return int(base + per_enemy * enemy_count)


# ---------- Validation ----------

def validate_monster_rarity_config(config: dict[str, Any] | None = None) -> list[str]:
    """Validate the monster rarity config for internal consistency.

    Checks:
    - All rarity tier IDs are valid
    - All champion type IDs are valid  
    - All affix IDs in affix_rules reference existing affixes
    - Forbidden combinations reference real affix IDs
    - ranged_only/melee_only affixes reference real affix IDs
    - All affixes have required fields (affix_id, name, category, effects, prefixes, suffixes)
    - Champion types have required fields (type_id, name, visual_tint)
    - Rarity tiers have required fields (tier_id, name, name_color)
    - Spawn chances has required fields

    Returns a list of error strings (empty = valid).
    """
    if config is None:
        config = load_monster_rarity_config()

    errors: list[str] = []

    # --- Rarity tiers ---
    tiers = config.get("rarity_tiers", {})
    if not tiers:
        errors.append("No rarity_tiers defined")
    for tier_id, tier_data in tiers.items():
        if tier_id not in VALID_RARITY_TIERS:
            errors.append(f"Unknown rarity tier: '{tier_id}'")
        if tier_data.get("tier_id") != tier_id:
            errors.append(f"Tier '{tier_id}' has mismatched tier_id: '{tier_data.get('tier_id')}'")
        for required in ("name", "name_color"):
            if required not in tier_data:
                errors.append(f"Tier '{tier_id}' missing required field: '{required}'")

    # --- Champion types ---
    champion_types = config.get("champion_types", {})
    if not champion_types:
        errors.append("No champion_types defined")
    for ct_id, ct_data in champion_types.items():
        if ct_id not in VALID_CHAMPION_TYPES:
            errors.append(f"Unknown champion type: '{ct_id}'")
        if ct_data.get("type_id") != ct_id:
            errors.append(f"Champion type '{ct_id}' has mismatched type_id: '{ct_data.get('type_id')}'")
        for required in ("name", "visual_tint"):
            if required not in ct_data:
                errors.append(f"Champion type '{ct_id}' missing required field: '{required}'")

    # --- Affixes ---
    affixes = config.get("affixes", {})
    if not affixes:
        errors.append("No affixes defined")
    all_affix_ids = set(affixes.keys())
    for affix_id, affix_data in affixes.items():
        if affix_data.get("affix_id") != affix_id:
            errors.append(f"Affix '{affix_id}' has mismatched affix_id: '{affix_data.get('affix_id')}'")
        for required in ("name", "category", "effects", "prefixes", "suffixes"):
            if required not in affix_data:
                errors.append(f"Affix '{affix_id}' missing required field: '{required}'")
        # Effects must be a non-empty list
        effects = affix_data.get("effects", [])
        if not isinstance(effects, list) or len(effects) == 0:
            errors.append(f"Affix '{affix_id}' must have at least one effect")
        # Prefixes and suffixes must be non-empty lists
        for pool_name in ("prefixes", "suffixes"):
            pool = affix_data.get(pool_name, [])
            if not isinstance(pool, list) or len(pool) == 0:
                errors.append(f"Affix '{affix_id}' must have at least one {pool_name[:-2]}x")

    # --- Affix rules ---
    rules = config.get("affix_rules", {})
    if not rules:
        errors.append("No affix_rules defined")
    else:
        # Forbidden combinations must reference real affixes
        for combo in rules.get("forbidden_combinations", []):
            for affix_id in combo:
                if affix_id not in all_affix_ids:
                    errors.append(f"Forbidden combination references unknown affix: '{affix_id}'")
        # ranged_only / melee_only must reference real affixes
        for list_key in ("ranged_only_affixes", "melee_only_affixes"):
            for affix_id in rules.get(list_key, []):
                if affix_id not in all_affix_ids:
                    errors.append(f"affix_rules.{list_key} references unknown affix: '{affix_id}'")

    # --- Spawn chances ---
    spawn = config.get("spawn_chances", {})
    if not spawn:
        errors.append("No spawn_chances defined")
    else:
        for required in ("champion_base_chance", "rare_base_chance", "floor_bonus_per_level"):
            if required not in spawn:
                errors.append(f"spawn_chances missing required field: '{required}'")

    return errors


# ==========================================================
# Phase 18B — Affix Engine
# ==========================================================

def roll_monster_rarity(floor_number: int, rng: random.Random) -> str:
    """Roll whether a spawn becomes normal/champion/rare.

    Uses spawn_chances from config + floor bonus.
    Rare is checked first (higher value), then champion.
    Returns: "normal", "champion", or "rare"
    """
    config = load_monster_rarity_config()
    chances = config.get("spawn_chances", {})

    floor_bonus = chances.get("floor_bonus_per_level", 0.01) * floor_number
    min_floor_champ = chances.get("min_floor_for_champions", 1)
    min_floor_rare = chances.get("min_floor_for_rares", 3)

    # Roll rare first (more valuable, lower chance)
    if floor_number >= min_floor_rare:
        rare_chance = chances.get("rare_base_chance", 0.03) + floor_bonus
        if rng.random() < rare_chance:
            return "rare"

    # Then champion
    if floor_number >= min_floor_champ:
        champ_chance = chances.get("champion_base_chance", 0.08) + floor_bonus
        if rng.random() < champ_chance:
            return "champion"

    return "normal"


def roll_champion_type(rng: random.Random) -> str:
    """Pick a random champion type from the pool.

    Returns: e.g. "berserker", "fanatic", etc.
    """
    config = load_monster_rarity_config()
    champion_types = list(config.get("champion_types", {}).keys())
    if not champion_types:
        return "berserker"  # Fallback
    return rng.choice(champion_types)


def get_champion_type_name(champion_type_id: str) -> str:
    """Get the human-readable name for a champion type ID.

    Returns the config 'name' field (e.g. "Ghostly", "Berserker").
    Falls back to title-cased ID if not found.
    """
    ct = get_champion_type(champion_type_id)
    if ct:
        return ct.get("name", champion_type_id.title())
    return champion_type_id.title()


def roll_affixes(
    enemy_def: Any,
    count: int,
    rng: random.Random,
) -> list[str]:
    """Roll N random affixes respecting compatibility rules.

    - No duplicates
    - Max 1 aura affix (Might OR Conviction — not both)
    - Max 1 on-death affix
    - Respects enemy excluded_affixes
    - Respects ranged_only / melee_only restrictions
    - Checks forbidden_combinations
    - Excludes affixes whose excludes_class_skills overlap with enemy class skills

    Args:
        enemy_def: EnemyDefinition (or object with excluded_affixes, ranged_range, class_id)
        count: Number of affixes to roll (capped by max_affixes rule and pool size)
        rng: Random instance for deterministic rolling

    Returns: list of affix_id strings
    """
    config = load_monster_rarity_config()
    all_affixes = config.get("affixes", {})
    rules = config.get("affix_rules", {})

    max_affixes = rules.get("max_affixes", 3)
    max_auras = rules.get("max_auras", 1)
    max_on_death = rules.get("max_on_death", 1)
    ranged_only = set(rules.get("ranged_only_affixes", []))
    melee_only = set(rules.get("melee_only_affixes", []))
    forbidden_combos = rules.get("forbidden_combinations", [])

    # Determine enemy properties
    excluded = set(getattr(enemy_def, "excluded_affixes", []) if enemy_def else [])
    is_ranged = (getattr(enemy_def, "ranged_range", 1) if enemy_def else 1) > 1
    enemy_class_id = getattr(enemy_def, "class_id", None) if enemy_def else None

    # Load class skills to check excludes_class_skills
    enemy_class_skills = set()
    if enemy_class_id:
        from app.core.skills import load_skills_config
        try:
            skills_config = load_skills_config()
            class_skills = skills_config.get("class_skills", {})
            enemy_class_skills = set(class_skills.get(enemy_class_id, []))
        except Exception:
            pass

    # Effective count capped by max_affixes
    target_count = min(count, max_affixes)

    # Build candidate pool
    candidate_ids = []
    for affix_id, affix_data in all_affixes.items():
        # Skip excluded affixes for this enemy
        if affix_id in excluded:
            continue
        # Skip ranged_only affixes for melee enemies
        if affix_id in ranged_only and not is_ranged:
            continue
        # Skip melee_only affixes for ranged enemies
        if affix_id in melee_only and is_ranged:
            continue
        # Skip affixes whose excludes_class_skills overlap with enemy's class skills
        excludes_skills = set(affix_data.get("excludes_class_skills", []))
        if excludes_skills & enemy_class_skills:
            continue
        candidate_ids.append(affix_id)

    selected: list[str] = []
    aura_count = 0
    on_death_count = 0

    # Shuffle candidates for random selection
    shuffled = list(candidate_ids)
    rng.shuffle(shuffled)

    for affix_id in shuffled:
        if len(selected) >= target_count:
            break

        affix_data = all_affixes[affix_id]

        # Check aura limit
        if affix_data.get("is_aura", False):
            if aura_count >= max_auras:
                continue
        # Check on-death limit
        if affix_data.get("category") == "on_death":
            if on_death_count >= max_on_death:
                continue

        # Check forbidden combinations with already selected affixes
        forbidden = False
        for combo in forbidden_combos:
            if affix_id in combo:
                for other in combo:
                    if other != affix_id and other in selected:
                        forbidden = True
                        break
            if forbidden:
                break
        if forbidden:
            continue

        # Add affix
        selected.append(affix_id)
        if affix_data.get("is_aura", False):
            aura_count += 1
        if affix_data.get("category") == "on_death":
            on_death_count += 1

    return selected


def generate_rare_name(base_name: str, affixes: list[str], rng: random.Random) -> str:
    """Generate a D2-style rare name from affix prefix/suffix pools.

    Format: '{prefix} {base_name} the {suffix}'
    Prefix drawn from first affix's prefix pool.
    Suffix drawn from second affix's suffix pool (or first if only one affix).

    If no affixes, returns base_name unchanged.
    """
    if not affixes:
        return base_name

    config = load_monster_rarity_config()
    all_affixes = config.get("affixes", {})

    # Get prefix from first affix
    first_affix = all_affixes.get(affixes[0], {})
    prefixes = first_affix.get("prefixes", [])
    prefix = rng.choice(prefixes) if prefixes else "Cursed"

    # Get suffix from second affix (or first if only one)
    suffix_affix_id = affixes[1] if len(affixes) > 1 else affixes[0]
    suffix_affix = all_affixes.get(suffix_affix_id, {})
    suffixes = suffix_affix.get("suffixes", [])
    suffix = rng.choice(suffixes) if suffixes else "the Damned"

    # Format: suffix may already start with "the " or "of "
    # If suffix starts with "the " or "of ", use directly
    if suffix.startswith("the ") or suffix.startswith("of "):
        return f"{prefix} {base_name} {suffix}"
    else:
        return f"{prefix} {base_name} the {suffix}"


def apply_rarity_to_player(
    player: Any,
    rarity: str,
    champion_type: str | None = None,
    affixes: list[str] | None = None,
    display_name: str | None = None,
) -> None:
    """Apply rarity tier stat scaling + champion type bonuses + affix stat modifiers.

    This mutates the PlayerState in-place following the application order:
    1. Tier multipliers — HP x hp_multiplier, damage x damage_multiplier, armor + armor_bonus
    2. Champion type — Additional multipliers/bonuses (Resilient HP x1.5, Ghostly dodge, etc.)
    3. Affix stat modifiers — stat_multiplier, set_stat, life_steal_pct, hp_regen_pct, grant_ward, cooldown_reduction
    4. Recalculate max_hp — Set hp = max_hp after all HP modifications

    Args:
        player: PlayerState to modify in-place
        rarity: "normal", "champion", "rare", or "super_unique"
        champion_type: champion type ID (for champions only)
        affixes: list of affix IDs (for rare enemies)
        display_name: Generated display name
    """
    if affixes is None:
        affixes = []

    config = load_monster_rarity_config()

    # --- Set metadata fields ---
    player.monster_rarity = rarity
    player.champion_type = champion_type
    player.affixes = list(affixes)
    player.display_name = display_name

    # --- Step 1: Tier stat scaling ---
    tier = config.get("rarity_tiers", {}).get(rarity, {})
    hp_mult = tier.get("hp_multiplier")
    dmg_mult = tier.get("damage_multiplier")
    armor_bonus = tier.get("armor_bonus")

    if hp_mult is not None:
        player.max_hp = int(player.max_hp * hp_mult)
    if dmg_mult is not None:
        player.attack_damage = int(player.attack_damage * dmg_mult)
        if player.ranged_damage > 0:
            player.ranged_damage = int(player.ranged_damage * dmg_mult)
    if armor_bonus is not None:
        player.armor += armor_bonus

    # --- Step 2: Champion type bonuses ---
    if champion_type:
        ct = config.get("champion_types", {}).get(champion_type, {})

        # Berserker: +30% damage (enrage is a combat-time effect handled in 18D)
        if ct.get("damage_bonus"):
            bonus = ct["damage_bonus"]
            player.attack_damage = int(player.attack_damage * (1.0 + bonus))
            if player.ranged_damage > 0:
                player.ranged_damage = int(player.ranged_damage * (1.0 + bonus))

        # Fanatic: cooldown reduction
        if ct.get("cooldown_reduction"):
            # Applied as flat reduction to all cooldowns when they are set
            # Store as a flag that the combat system will check
            pass  # Handled at combat time in 18D

        # Ghostly: dodge chance + phase through
        if ct.get("dodge_chance"):
            player.dodge_chance = ct["dodge_chance"]

        # Resilient: extra HP multiplier + armor
        if ct.get("hp_multiplier"):
            player.max_hp = int(player.max_hp * ct["hp_multiplier"])
        if ct.get("armor_bonus"):
            player.armor += ct["armor_bonus"]

        # Possessed: on-death explosion (handled at combat time in 18D)
        # No stat changes needed at spawn

    # --- Step 3: Affix stat modifiers ---
    all_affixes = config.get("affixes", {})
    for affix_id in affixes:
        affix_data = all_affixes.get(affix_id, {})
        for effect in affix_data.get("effects", []):
            _apply_affix_effect(player, effect)

    # --- Step 4: Recalculate HP to full ---
    player.hp = player.max_hp


def _apply_affix_effect(player: Any, effect: dict) -> None:
    """Apply a single affix effect to a PlayerState.

    Handles effect types:
    - stat_multiplier: multiply a stat by value
    - set_stat: set a stat to a fixed value
    - life_steal_pct: set life steal (as damage_reduction_pct proxy or custom field)
    - hp_regen_pct: set HP regen as percentage of max_hp per turn
    - grant_ward: sets up ward charges (stored as buff, applied in 18D)
    - cooldown_reduction_flat: reduce all existing cooldowns by N (min 1)
    - on_hit_*, on_death_*, aura_*, auto_*, extra_*: behavioral — no stat changes at spawn
    """
    effect_type = effect.get("type", "")

    if effect_type == "stat_multiplier":
        stat = effect.get("stat", "")
        value = effect.get("value", 1.0)
        if stat == "attack_damage":
            player.attack_damage = int(player.attack_damage * value)
            if player.ranged_damage > 0:
                player.ranged_damage = int(player.ranged_damage * value)
        elif stat == "armor":
            player.armor = int(player.armor * value)

    elif effect_type == "set_stat":
        stat = effect.get("stat", "")
        value = effect.get("value", 0)
        if hasattr(player, stat):
            setattr(player, stat, value)

    elif effect_type == "life_steal_pct":
        # Store life steal percentage — combat integration reads this in 18D
        # Use life_on_hit as percentage indicator (will be refined in 18D)
        # For now, store the percentage value on the player so combat can check
        player.life_on_hit = int(effect.get("value", 0.0) * 100)  # Store as integer pct

    elif effect_type == "hp_regen_pct":
        # Convert percentage to flat HP regen based on current max_hp
        pct = effect.get("value", 0.0)
        player.hp_regen = max(1, int(player.max_hp * pct))

    elif effect_type == "cooldown_reduction_flat":
        # Reduces all active cooldowns by N (min 1 remaining)
        # At spawn time there may be no active cooldowns, so this is also
        # stored as cooldown_reduction_pct for the combat system to use
        reduction = effect.get("value", 0)
        player.cooldown_reduction_pct = min(1.0, reduction * 0.15)  # Approximate CDR

    elif effect_type == "grant_ward":
        # Store ward info as a buff — combat integration handles actual ward mechanics in 18D
        charges = effect.get("charges", 3)
        reflect = effect.get("reflect_damage", 10)
        player.active_buffs.append({
            "buff_id": "affix_ward",
            "stat": "shield_charges",
            "magnitude": charges,
            "turns_remaining": -1,  # Permanent until charges depleted
            "reflect_damage": reflect,
            "source": "affix_shielded",
        })

    # Behavioral effects (on_hit, on_death, aura, auto_shadow_step, extra_ranged_target)
    # These are handled at combat time in Phase 18D — no stat changes needed at spawn.


def create_minions(
    rare_player: Any,
    enemy_def: Any,
    count: int,
    room_id: str | None = None,
    rng: random.Random | None = None,
) -> list[dict]:
    """Create Normal-tier minion data for a Rare leader.

    Minions are the same base enemy type as the rare, with Normal rarity,
    and minion_owner_id set to the rare's player_id.

    This returns a list of dicts with the info needed to spawn minions
    (the actual PlayerState construction happens in match_manager when
    positions are known).

    Args:
        rare_player: The Rare leader PlayerState
        enemy_def: EnemyDefinition of the base enemy type
        count: Number of minions to create
        room_id: Room ID for leashing
        rng: Random instance

    Returns:
        List of minion spawn dicts with keys:
        - player_id, enemy_type, monster_rarity, minion_owner_id, is_minion, room_id
    """
    if rng is None:
        rng = random.Random()

    minions = []
    enemy_type = getattr(enemy_def, "enemy_id", None) or getattr(rare_player, "enemy_type", "skeleton")

    for i in range(count):
        minion_id = f"minion_{rare_player.player_id}_{i}_{uuid.uuid4().hex[:6]}"
        minions.append({
            "player_id": minion_id,
            "enemy_type": enemy_type,
            "monster_rarity": "normal",
            "champion_type": None,
            "affixes": [],
            "display_name": None,
            "minion_owner_id": rare_player.player_id,
            "is_minion": True,
            "room_id": room_id,
        })

    return minions


# ==========================================================
# Phase 18G — Super Uniques
# ==========================================================

def validate_super_uniques_config(config: dict[str, Any] | None = None) -> list[str]:
    """Validate the super uniques config for internal consistency.

    Checks:
    - All super unique entries have required fields
    - base_enemy references a valid enemy type in enemies_config
    - affixes reference real affix IDs in monster_rarity_config
    - retinue enemy_types reference valid enemy types
    - loot table pools reference real item IDs
    - floor_range is a valid [min, max] pair
    - spawn_rules has required fields

    Returns a list of error strings (empty = valid).
    """
    if config is None:
        config = load_super_uniques_config()

    errors: list[str] = []

    # Validate super unique entries
    su_entries = config.get("super_uniques", {})
    if not isinstance(su_entries, dict):
        errors.append("super_uniques must be a dict")
        return errors

    # Load reference data for cross-validation
    from app.models.player import get_enemy_definition
    rarity_config = load_monster_rarity_config()
    all_affix_ids = set(rarity_config.get("affixes", {}).keys())

    required_fields = ("id", "base_enemy", "name", "floor_range", "affixes")

    for su_id, su_data in su_entries.items():
        if not isinstance(su_data, dict):
            errors.append(f"Super unique '{su_id}' must be a dict")
            continue

        # Check required fields
        for field in required_fields:
            if field not in su_data:
                errors.append(f"Super unique '{su_id}' missing required field: '{field}'")

        # Check ID consistency
        if su_data.get("id") != su_id:
            errors.append(f"Super unique '{su_id}' has mismatched id: '{su_data.get('id')}'")

        # Check base_enemy references a real enemy
        base_enemy = su_data.get("base_enemy", "")
        if base_enemy and get_enemy_definition(base_enemy) is None:
            errors.append(f"Super unique '{su_id}' references unknown base_enemy: '{base_enemy}'")

        # Check affixes reference real affix IDs
        for affix_id in su_data.get("affixes", []):
            if affix_id not in all_affix_ids:
                errors.append(f"Super unique '{su_id}' references unknown affix: '{affix_id}'")

        # Check floor_range is valid
        floor_range = su_data.get("floor_range", [])
        if isinstance(floor_range, list):
            if len(floor_range) != 2:
                errors.append(f"Super unique '{su_id}' floor_range must have exactly 2 elements")
            elif floor_range[0] > floor_range[1]:
                errors.append(f"Super unique '{su_id}' floor_range min > max: {floor_range}")

        # Check retinue enemy types
        for ret in su_data.get("retinue", []):
            ret_type = ret.get("enemy_type", "")
            if ret_type and get_enemy_definition(ret_type) is None:
                errors.append(f"Super unique '{su_id}' retinue references unknown enemy_type: '{ret_type}'")

        # Check loot table pool items exist
        loot_table = su_data.get("loot_table", {})
        if loot_table:
            from app.core.loot import load_items_config
            items_config = load_items_config()
            for pool_idx, pool in enumerate(loot_table.get("pools", [])):
                for item_id in pool.get("items", []):
                    if item_id not in items_config:
                        errors.append(
                            f"Super unique '{su_id}' loot pool[{pool_idx}]: "
                            f"item_id '{item_id}' not found in items_config"
                        )

    # Validate spawn rules
    rules = config.get("spawn_rules", {})
    for required in ("per_floor_chance", "max_per_run", "min_floor"):
        if required not in rules:
            errors.append(f"spawn_rules missing required field: '{required}'")

    return errors


def get_eligible_super_uniques(floor_number: int) -> list[dict[str, Any]]:
    """Get all super uniques eligible to spawn on a given floor.

    A super unique is eligible if floor_number falls within its floor_range [min, max].

    Args:
        floor_number: Current dungeon floor number.

    Returns:
        List of super unique config dicts eligible for this floor.
    """
    config = load_super_uniques_config()
    su_entries = config.get("super_uniques", {})
    eligible = []

    for su_id, su_data in su_entries.items():
        floor_range = su_data.get("floor_range", [0, 0])
        if isinstance(floor_range, list) and len(floor_range) == 2:
            if floor_range[0] <= floor_number <= floor_range[1]:
                eligible.append(su_data)

    return eligible


def roll_super_unique_spawn(
    floor_number: int,
    rng: random.Random | None = None,
    already_spawned_count: int = 0,
) -> dict[str, Any] | None:
    """Roll whether a boss room on this floor gets a super unique.

    1. Check if floor_number >= min_floor
    2. Check if already_spawned_count < max_per_run
    3. Find eligible super uniques for this floor
    4. Roll against per_floor_chance
    5. If triggered, pick a random eligible super unique

    Args:
        floor_number: Current dungeon floor number.
        rng: Random instance for deterministic rolling.
        already_spawned_count: How many super uniques have already spawned this run.

    Returns:
        Super unique config dict if one should spawn, None otherwise.
    """
    if rng is None:
        rng = random.Random()

    rules = get_super_unique_spawn_rules()
    min_floor = rules.get("min_floor", 3)
    max_per_run = rules.get("max_per_run", 1)
    per_floor_chance = rules.get("per_floor_chance", 0.25)

    # Check floor minimum
    if floor_number < min_floor:
        return None

    # Check max per run
    if already_spawned_count >= max_per_run:
        return None

    # Find eligible super uniques
    eligible = get_eligible_super_uniques(floor_number)
    if not eligible:
        return None

    # Roll chance
    if rng.random() >= per_floor_chance:
        return None

    # Pick a random eligible super unique
    return rng.choice(eligible)


def apply_super_unique_stats(player: Any, su_config: dict[str, Any]) -> None:
    """Apply super unique fixed stats, affixes, and metadata to a PlayerState.

    Super uniques override base enemy stats entirely with their own fixed values,
    then apply their fixed affixes on top.

    Args:
        player: PlayerState to modify in-place.
        su_config: Super unique config dict from super_uniques_config.json.
    """
    # --- Set metadata ---
    player.monster_rarity = "super_unique"
    player.champion_type = None
    player.affixes = list(su_config.get("affixes", []))
    player.display_name = su_config.get("name", "Super Unique")
    player.is_boss = True

    # --- Override base stats with fixed values ---
    if "base_hp" in su_config:
        player.max_hp = su_config["base_hp"]
    if "base_melee_damage" in su_config:
        player.attack_damage = su_config["base_melee_damage"]
    if "base_ranged_damage" in su_config:
        player.ranged_damage = su_config["base_ranged_damage"]
    if "base_armor" in su_config:
        player.armor = su_config["base_armor"]

    # --- Apply fixed affixes (stat modifiers only — behavioral handled at combat time) ---
    config = load_monster_rarity_config()
    all_affixes = config.get("affixes", {})
    for affix_id in su_config.get("affixes", []):
        affix_data = all_affixes.get(affix_id, {})
        for effect in affix_data.get("effects", []):
            _apply_affix_effect(player, effect)

    # --- Set HP to full after all stat modifications ---
    player.hp = player.max_hp


def create_super_unique_retinue(
    su_config: dict[str, Any],
    leader_id: str,
    room_id: str | None = None,
) -> list[dict]:
    """Create spawn data dicts for a super unique's fixed retinue.

    Each retinue member is a Normal-rarity enemy linked to the super unique
    as its minion_owner_id.

    Args:
        su_config: Super unique config dict with retinue array.
        leader_id: player_id of the super unique leader.
        room_id: Room ID for AI leashing.

    Returns:
        List of spawn dicts with keys:
        - player_id, enemy_type, monster_rarity, display_name,
          minion_owner_id, is_minion, room_id, count (for spawner to unpack)
    """
    retinue_spawns = []
    for entry in su_config.get("retinue", []):
        enemy_type = entry.get("enemy_type", "skeleton")
        count = entry.get("count", 1)

        for i in range(count):
            retinue_id = f"retinue_{leader_id}_{enemy_type}_{i}_{uuid.uuid4().hex[:6]}"
            retinue_spawns.append({
                "player_id": retinue_id,
                "enemy_type": enemy_type,
                "monster_rarity": "normal",
                "champion_type": None,
                "affixes": [],
                "display_name": None,
                "minion_owner_id": leader_id,
                "is_minion": True,
                "room_id": room_id,
            })

    return retinue_spawns
