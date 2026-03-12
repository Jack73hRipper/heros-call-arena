"""Item Generator -- Phase 16B/16D Affix System & Item Generation.

Transforms static config-lookup items into a Diablo-style RNG loot engine.
Items gain a base type with fixed stats, then random affixes are rolled on top.
Each affix adds a random stat bonus within a defined range, scaled by item level.

Phase 16D adds Unique item generation from curated configs.

Key functions:
  - generate_item(): Create a fully-formed Item with random affixes and UUID
  - generate_unique(): Create a Unique item from uniques_config.json
  - roll_unique_drop(): Check if a unique should drop from an enemy kill
  - roll_rarity(): Determine item rarity with floor depth + magic find
  - roll_affix_value(): Roll a stat value for an affix, scaled by item level
  - has_unique_equipped(): Check if a player has a specific unique item equipped
"""

from __future__ import annotations

import json
import random
import uuid
from pathlib import Path

from app.models.items import (
    ConsumableEffect,
    EquipSlot,
    Item,
    ItemType,
    Rarity,
    StatBonuses,
)

# ---------- Config Paths ----------

_configs_dir = Path(__file__).resolve().parent.parent.parent / "configs"
_affixes_config_path = _configs_dir / "affixes_config.json"
_item_names_config_path = _configs_dir / "item_names_config.json"
_items_config_path = _configs_dir / "items_config.json"
_uniques_config_path = _configs_dir / "uniques_config.json"

# ---------- Caches ----------

_affixes_cache: dict | None = None
_item_names_cache: dict | None = None
_uniques_cache: dict | None = None


# ---------- Config Loaders ----------

def load_affixes_config(path: Path | None = None) -> dict:
    """Load affix definitions from JSON config. Caches after first load.

    Returns dict with 'prefixes' and 'suffixes' keys.
    """
    global _affixes_cache
    if _affixes_cache is not None:
        return _affixes_cache

    config_file = path or _affixes_config_path
    if config_file.exists():
        with open(config_file, "r") as f:
            _affixes_cache = json.load(f)
    else:
        _affixes_cache = {"prefixes": {}, "suffixes": {}}
    return _affixes_cache


def load_item_names_config(path: Path | None = None) -> dict:
    """Load grimdark item name pools from JSON config. Caches after first load."""
    global _item_names_cache
    if _item_names_cache is not None:
        return _item_names_cache

    config_file = path or _item_names_config_path
    if config_file.exists():
        with open(config_file, "r") as f:
            _item_names_cache = json.load(f)
    else:
        _item_names_cache = {"weapon_names": [], "armor_names": [], "accessory_names": []}
    return _item_names_cache


def load_uniques_config(path: Path | None = None) -> dict:
    """Load unique item definitions from JSON config. Caches after first load.

    Returns dict with 'uniques', 'drop_rules', and 'enemy_type_weights' keys.
    """
    global _uniques_cache
    if _uniques_cache is not None:
        return _uniques_cache

    config_file = path or _uniques_config_path
    if config_file.exists():
        with open(config_file, "r") as f:
            _uniques_cache = json.load(f)
    else:
        _uniques_cache = {"uniques": {}, "drop_rules": {}, "enemy_type_weights": {}}
    return _uniques_cache


def clear_generator_caches() -> None:
    """Clear all generator config caches. Useful for testing."""
    global _affixes_cache, _item_names_cache, _uniques_cache
    _affixes_cache = None
    _item_names_cache = None
    _uniques_cache = None
    # Also clear sets cache from set_bonuses module
    from app.core.set_bonuses import clear_sets_cache
    clear_sets_cache()


# ---------- Affix Rolling ----------

# Rarity → (min_prefixes, max_prefixes, min_suffixes, max_suffixes, min_total)
RARITY_AFFIX_COUNTS: dict[str, tuple[int, int, int, int, int]] = {
    "common":   (0, 0, 0, 0, 0),
    "uncommon":  (0, 0, 0, 0, 0),   # Legacy tier — no affixes
    "magic":    (0, 1, 0, 1, 1),     # 1–2 affixes, at least 1
    "rare":     (1, 2, 1, 2, 3),     # 3–4 affixes, at least 3
    "epic":     (2, 3, 2, 3, 4),     # 4–5 affixes
    "unique":   (0, 0, 0, 0, 0),     # Fixed curated stats
    "set":      (0, 0, 0, 0, 0),     # Fixed curated stats
}


def roll_affix_value(affix: dict, item_level: int, rng: random.Random) -> float | int:
    """Roll a stat value for an affix, scaled by item level.

    value = uniform(min_value, min_value + ilvl_scaling × item_level)
    capped at max_value.
    """
    min_val = affix["min_value"]
    max_val = affix["max_value"]
    ilvl_scaling = affix.get("ilvl_scaling", 0)

    scaled_max = min(max_val, min_val + ilvl_scaling * item_level)
    # Ensure scaled_max >= min_val
    scaled_max = max(min_val, scaled_max)

    raw = rng.uniform(min_val, scaled_max)

    # Round to int for int stats, 2 decimal places for float stats
    if isinstance(min_val, int):
        return max(1, round(raw))
    return round(raw, 2)


def _get_eligible_affixes(
    affix_pool: dict[str, dict],
    equip_slot: str,
    exclude_ids: set[str],
    exclude_stats: set[str],
) -> list[dict]:
    """Filter affixes by slot eligibility and exclusions.

    Args:
        affix_pool: Dict of affix_id -> affix definition (prefixes or suffixes).
        equip_slot: The equipment slot of the item ("weapon", "armor", "accessory").
        exclude_ids: Set of affix IDs already rolled (prevent duplicates).
        exclude_stats: Set of stat keys already present (prevent same-stat stacking).

    Returns:
        List of eligible affix definitions.
    """
    eligible = []
    for affix_id, affix in affix_pool.items():
        if affix_id in exclude_ids:
            continue
        if affix.get("stat") in exclude_stats:
            continue
        allowed_slots = affix.get("allowed_slots", [])
        if equip_slot in allowed_slots:
            eligible.append(affix)
    return eligible


def _weighted_pick(affixes: list[dict], rng: random.Random) -> dict | None:
    """Pick one affix from a list using weighted random selection."""
    if not affixes:
        return None
    weights = [a.get("weight", 100) for a in affixes]
    return rng.choices(affixes, weights=weights, k=1)[0]


def roll_affixes(
    rarity: str,
    equip_slot: str,
    item_level: int,
    rng: random.Random,
    affixes_config: dict | None = None,
) -> list[dict]:
    """Roll random affixes for an item based on rarity and slot.

    Returns a list of affix result dicts:
      [{affix_id, type: "prefix"|"suffix", name, stat, value}, ...]
    """
    config = affixes_config or load_affixes_config()
    counts = RARITY_AFFIX_COUNTS.get(rarity)
    if not counts or counts == (0, 0, 0, 0, 0):
        return []

    min_pre, max_pre, min_suf, max_suf, min_total = counts
    prefixes_pool = config.get("prefixes", {})
    suffixes_pool = config.get("suffixes", {})

    rolled: list[dict] = []
    used_ids: set[str] = set()
    used_stats: set[str] = set()

    # Roll prefixes
    num_prefixes = rng.randint(min_pre, max_pre)
    for _ in range(num_prefixes):
        eligible = _get_eligible_affixes(prefixes_pool, equip_slot, used_ids, used_stats)
        picked = _weighted_pick(eligible, rng)
        if picked is None:
            break
        value = roll_affix_value(picked, item_level, rng)
        rolled.append({
            "affix_id": picked["affix_id"],
            "type": "prefix",
            "name": picked["name"],
            "stat": picked["stat"],
            "value": value,
        })
        used_ids.add(picked["affix_id"])
        used_stats.add(picked["stat"])

    # Roll suffixes
    num_suffixes = rng.randint(min_suf, max_suf)
    for _ in range(num_suffixes):
        eligible = _get_eligible_affixes(suffixes_pool, equip_slot, used_ids, used_stats)
        picked = _weighted_pick(eligible, rng)
        if picked is None:
            break
        value = roll_affix_value(picked, item_level, rng)
        rolled.append({
            "affix_id": picked["affix_id"],
            "type": "suffix",
            "name": picked["name"],
            "stat": picked["stat"],
            "value": value,
        })
        used_ids.add(picked["affix_id"])
        used_stats.add(picked["stat"])

    # Ensure minimum total affix count is met
    # If we're under min_total, try to roll more from either pool
    attempts = 0
    while len(rolled) < min_total and attempts < 10:
        attempts += 1
        # Alternate between prefix and suffix pools to fill
        if rng.random() < 0.5:
            eligible = _get_eligible_affixes(prefixes_pool, equip_slot, used_ids, used_stats)
        else:
            eligible = _get_eligible_affixes(suffixes_pool, equip_slot, used_ids, used_stats)

        if not eligible:
            # Try the other pool
            eligible = _get_eligible_affixes(prefixes_pool, equip_slot, used_ids, used_stats)
            if not eligible:
                eligible = _get_eligible_affixes(suffixes_pool, equip_slot, used_ids, used_stats)
            if not eligible:
                break  # No more affixes available

        picked = _weighted_pick(eligible, rng)
        if picked is None:
            break

        affix_type = "prefix" if picked["affix_id"] in prefixes_pool else "suffix"
        value = roll_affix_value(picked, item_level, rng)
        rolled.append({
            "affix_id": picked["affix_id"],
            "type": affix_type,
            "name": picked["name"],
            "stat": picked["stat"],
            "value": value,
        })
        used_ids.add(picked["affix_id"])
        used_stats.add(picked["stat"])

    return rolled


# ---------- Name Generation ----------


def _pick_best_affix(affixes: list[dict], affix_type: str) -> dict | None:
    """Pick the highest-weight affix of a given type from a rolled affix list.

    Uses the affix 'weight' field (from config) as a proxy for importance.
    Falls back to the first affix of that type if weights are absent.
    """
    typed = [a for a in affixes if a["type"] == affix_type]
    if not typed:
        return None
    # Higher weight = more common, but we want the *most impactful* which
    # correlates with rarer (lower weight) affixes.  Pick lowest weight.
    return min(typed, key=lambda a: a.get("weight", 100))


def _get_name_pool(equip_slot: str | None, config: dict) -> list[str]:
    """Return the grimdark name pool for a given equipment slot."""
    if equip_slot == "weapon":
        return config.get("weapon_names", [])
    elif equip_slot == "armor":
        return config.get("armor_names", [])
    elif equip_slot == "accessory":
        return config.get("accessory_names", [])
    return config.get("weapon_names", [])


def generate_item_name(
    base_name: str,
    rarity: str,
    affixes: list[dict],
    equip_slot: str | None,
    rng: random.Random,
    names_config: dict | None = None,
) -> str:
    """Generate a display name for an item based on rarity and affixes.

    Naming tiers (max ~3 words in every case):
      Common/Uncommon : "{BaseName}"
      Magic (1-2 aff) : "{Prefix} {BaseName}" / "{BaseName} {Suffix}"
                        / "{Prefix} {BaseName} {Suffix}"
      Rare  (3-4 aff) : Best prefix + base + best suffix picked by rarity
                        (remaining affixes visible in tooltip only)
      Epic  (4-5 aff) : Grimdark title from curated name pool
    """
    if rarity in ("common", "uncommon"):
        return base_name

    if rarity == "magic":
        # Magic items have at most 1 prefix + 1 suffix — simple concatenation
        prefix_names = [a["name"] for a in affixes if a["type"] == "prefix"]
        suffix_names = [a["name"] for a in affixes if a["type"] == "suffix"]

        parts = []
        if prefix_names:
            parts.append(prefix_names[0])
        parts.append(base_name)
        if suffix_names:
            parts.append(suffix_names[0])
        return " ".join(parts)

    if rarity == "rare":
        # Rare: pick the single most interesting prefix & suffix for the name.
        # This keeps names to ≤3 words even with 3-4 rolled affixes.
        best_pre = _pick_best_affix(affixes, "prefix")
        best_suf = _pick_best_affix(affixes, "suffix")

        parts = []
        if best_pre:
            parts.append(best_pre["name"])
        parts.append(base_name)
        if best_suf:
            parts.append(best_suf["name"])
        return " ".join(parts)

    if rarity == "epic":
        # Epic: prestigious grimdark title replaces affixes in display name
        config = names_config or load_item_names_config()
        pool = _get_name_pool(equip_slot, config)
        if pool:
            return rng.choice(pool)
        return base_name

    # Unique/Set — name comes from curated config, not generated here
    return base_name


# ---------- Sell Value ----------

RARITY_SELL_MULTIPLIERS: dict[str, float] = {
    "common":   1.0,
    "uncommon":  1.0,
    "magic":    1.5,
    "rare":     3.0,
    "epic":     6.0,
    "unique":   8.0,
    "set":      8.0,
}


def calculate_sell_value(base_sell_value: int, rarity: str, affixes: list[dict]) -> int:
    """Calculate sell value based on base value, rarity, and affix quality.

    sell_value = base_sell_value × rarity_multiplier + sum(affix_value_bonuses)
    Each affix adds: affix_value / affix_max_value × 10 gold (scales with roll quality)
    """
    multiplier = RARITY_SELL_MULTIPLIERS.get(rarity, 1.0)
    base = int(base_sell_value * multiplier)

    affix_bonus = 0
    affixes_config = load_affixes_config()
    all_affixes = {**affixes_config.get("prefixes", {}), **affixes_config.get("suffixes", {})}

    for affix in affixes:
        affix_def = all_affixes.get(affix.get("affix_id", ""), {})
        max_val = affix_def.get("max_value", 1)
        value = affix.get("value", 0)
        if max_val > 0:
            # Scale bonus by how good the roll was (0-10 gold per affix)
            quality_ratio = abs(value) / abs(max_val) if max_val != 0 else 0
            affix_bonus += int(quality_ratio * 10)

    return max(1, base + affix_bonus)


# ---------- Stat Combining ----------

def _combine_stats(base_stats: StatBonuses, affixes: list[dict]) -> StatBonuses:
    """Combine base stats with affix stat bonuses into final stat_bonuses.

    Creates a new StatBonuses with base values + all affix additions.
    """
    combined = base_stats.model_copy()

    for affix in affixes:
        stat_key = affix.get("stat", "")
        value = affix.get("value", 0)
        if hasattr(combined, stat_key):
            current = getattr(combined, stat_key)
            setattr(combined, stat_key, current + value)

    return combined


# ---------- Rarity Rolling ----------

# Base drop rates (applied when using roll_rarity for generated items)
_BASE_RARITY_WEIGHTS: dict[str, float] = {
    "common":  60.0,
    "magic":   25.0,
    "rare":    12.0,
    "epic":     2.5,
    "unique":   0.5,
}

# Floor bonus multipliers for rarity chances
_FLOOR_BONUS: dict[tuple[int, int], float] = {
    (1, 2):   0.0,
    (3, 4):   0.15,
    (5, 6):   0.35,
    (7, 8):   0.60,
    (9, 99):  1.00,
}


def _get_floor_bonus(floor_number: int) -> float:
    """Get the floor bonus multiplier for rarity scaling."""
    for (low, high), bonus in _FLOOR_BONUS.items():
        if low <= floor_number <= high:
            return bonus
    return 0.0


def roll_rarity(
    floor_number: int = 1,
    enemy_tier: str = "fodder",
    magic_find_bonus: float = 0.0,
    rng: random.Random | None = None,
) -> Rarity:
    """Determine item rarity with floor depth and magic find factored in.

    Base rates adjusted by floor_number (deeper = rarer).
    magic_find_bonus adds % chance to upgrade each roll one tier higher.
    enemy_tier can shift weights for tougher enemies.
    """
    if rng is None:
        rng = random.Random()

    floor_bonus = _get_floor_bonus(floor_number)

    # Enemy tier bonuses — tougher enemies shift the curve
    tier_bonus = {
        "swarm": -0.1,
        "fodder": 0.0,
        "mid": 0.15,
        "elite": 0.35,
        "boss": 0.60,
    }.get(enemy_tier, 0.0)

    # Calculate effective weights
    # Higher rarities get boosted by floor + MF, lower rarities get reduced
    weights = {}
    for rarity_name, base_weight in _BASE_RARITY_WEIGHTS.items():
        if rarity_name == "common":
            # Common weight decreases as bonuses increase
            effective = base_weight * max(0.2, 1.0 - (floor_bonus + tier_bonus) * 0.3)
        else:
            # Rarer tiers get boosted
            effective = base_weight * (1.0 + floor_bonus + tier_bonus) * (1.0 + magic_find_bonus)
        weights[rarity_name] = max(0.01, effective)

    # Weighted random selection
    rarity_names = list(weights.keys())
    rarity_weights = [weights[r] for r in rarity_names]
    chosen = rng.choices(rarity_names, weights=rarity_weights, k=1)[0]

    # Map string to Rarity enum — Phase 16C proper enum mapping
    rarity_map = {
        "common": Rarity.COMMON,
        "magic": Rarity.MAGIC,
        "rare": Rarity.RARE,
        "epic": Rarity.EPIC,
        "unique": Rarity.UNIQUE,
    }

    return chosen  # type: ignore  — returns rarity string for generate_item()


# ---------- Main Generator ----------

def generate_item(
    base_type_id: str,
    rarity: str = "common",
    item_level: int = 1,
    seed: int | None = None,
    magic_find_bonus: float = 0.0,
    items_config: dict[str, dict] | None = None,
    affixes_config: dict | None = None,
    names_config: dict | None = None,
) -> Item | None:
    """Generate a complete item instance with random affixes.

    1. Load base type from items_config
    2. Determine affix count based on rarity
    3. Roll prefix/suffix affixes from allowed pools (filtered by equip_slot)
    4. Roll affix values scaled by item_level
    5. Combine base stats + affix stats
    6. Generate name
    7. Calculate sell value (base × rarity multiplier × affix count bonus)
    8. Return fully-formed Item with unique instance_id

    Args:
        base_type_id: Item ID from items_config.json (e.g., "uncommon_greatsword").
        rarity: Target rarity string ("common", "magic", "rare", "epic").
        item_level: Determines affix value scaling (higher = stronger rolls).
        seed: Optional deterministic seed for reproducible results.
        magic_find_bonus: Not used directly in generation (MF affects rarity selection).
        items_config: Override items config (for testing).
        affixes_config: Override affixes config (for testing).
        names_config: Override names config (for testing).

    Returns:
        Fully-formed Item with unique instance_id and random affixes,
        or None if the base_type_id is not found.
    """
    from app.core.loot import load_items_config

    config = items_config or load_items_config()
    raw = config.get(base_type_id)
    if raw is None:
        return None

    rng = random.Random(seed) if seed is not None else random.Random()

    # Parse base type info
    base_name = raw.get("name", base_type_id)
    item_type = raw.get("item_type", "weapon")
    equip_slot = raw.get("equip_slot")
    weapon_category = raw.get("weapon_category", "")  # Phase 16: class-lock category
    raw_bonuses = raw.get("stat_bonuses", {})
    base_stats = StatBonuses(**raw_bonuses)
    base_sell_value = raw.get("sell_value", 0)
    description = raw.get("description", "")

    # Build consumable effect (if present) — consumables don't get affixes
    consumable_effect = None
    raw_effect = raw.get("consumable_effect")
    if raw_effect is not None:
        consumable_effect = ConsumableEffect(**raw_effect)
        # Consumables are returned as-is, no affixes
        return Item(
            item_id=base_type_id,
            name=base_name,
            item_type=item_type,
            rarity=raw.get("rarity", "common"),
            equip_slot=equip_slot,
            stat_bonuses=base_stats,
            consumable_effect=consumable_effect,
            description=description,
            sell_value=base_sell_value,
            instance_id=str(uuid.uuid4()),
            base_type_id=base_type_id,
            display_name=base_name,
            base_stats=base_stats.model_copy(),
            affixes=[],
            item_level=item_level,
            weapon_category=weapon_category,
        )

    # Roll affixes (only for equippable items)
    aff_config = affixes_config or load_affixes_config()
    slot_str = equip_slot or item_type  # Use item_type as fallback for slot filtering
    affixes = roll_affixes(rarity, slot_str, item_level, rng, aff_config)

    # Combine base stats + affix stats
    final_stats = _combine_stats(base_stats, affixes)

    # Generate name
    n_config = names_config or load_item_names_config()
    generated_name = generate_item_name(
        base_name, rarity, affixes, equip_slot, rng, n_config
    )

    # Calculate sell value
    sell_value = calculate_sell_value(base_sell_value, rarity, affixes)

    # Map rarity string to Rarity enum — Phase 16C adds proper enums
    rarity_enum_map = {
        "common": Rarity.COMMON,
        "uncommon": Rarity.UNCOMMON,
        "magic": Rarity.MAGIC,
        "rare": Rarity.RARE,
        "epic": Rarity.EPIC,
        "unique": Rarity.UNIQUE,
        "set": Rarity.SET,
    }
    rarity_enum = rarity_enum_map.get(rarity, Rarity.COMMON)

    instance_id = str(uuid.uuid4())

    return Item(
        item_id=base_type_id,
        name=generated_name,
        item_type=item_type,
        rarity=rarity_enum,
        equip_slot=equip_slot,
        stat_bonuses=final_stats,
        consumable_effect=None,
        description=description,
        sell_value=sell_value,
        instance_id=instance_id,
        base_type_id=base_type_id,
        display_name=base_name,
        base_stats=base_stats.model_copy(),
        affixes=affixes,
        item_level=item_level,
        weapon_category=weapon_category,
    )


def generate_loot_item(
    base_type_id: str,
    floor_number: int = 1,
    enemy_tier: str = "fodder",
    magic_find_bonus: float = 0.0,
    seed: int | None = None,
    items_config: dict[str, dict] | None = None,
) -> Item | None:
    """High-level loot generation: rolls rarity then generates a full item.

    Convenience wrapper that combines roll_rarity() + generate_item().

    Args:
        base_type_id: Item ID from items_config.json.
        floor_number: Dungeon floor (affects rarity chances).
        enemy_tier: Enemy difficulty tier (affects rarity chances).
        magic_find_bonus: Player's magic find stat (decimal, e.g. 0.20 = 20%).
        seed: Optional deterministic seed.
        items_config: Override items config (for testing).

    Returns:
        Fully-formed Item with random rarity and affixes, or None.
    """
    rng = random.Random(seed) if seed is not None else random.Random()

    # Determine item level based on enemy tier and floor
    item_level = _calculate_item_level(floor_number, enemy_tier, rng)

    # Roll rarity
    rarity = roll_rarity(
        floor_number=floor_number,
        enemy_tier=enemy_tier,
        magic_find_bonus=magic_find_bonus,
        rng=rng,
    )

    return generate_item(
        base_type_id=base_type_id,
        rarity=rarity,
        item_level=item_level,
        seed=None,  # Already using rng above; pass None so generate_item creates its own
        items_config=items_config,
    )


def _calculate_item_level(floor_number: int, enemy_tier: str, rng: random.Random) -> int:
    """Calculate item level based on floor and enemy tier.

    | Source                | Item Level |
    |Swarm enemy drops      | 1–3        |
    |Fodder enemy drops     | 3–6        |
    |Mid-tier enemy drops   | 5–9        |
    |Elite enemy drops      | 8–13       |
    |Boss enemy drops       | 12–18      |
    """
    tier_ranges = {
        "swarm":  (1, 3),
        "fodder": (3, 6),
        "mid":    (5, 9),
        "elite":  (8, 13),
        "boss":   (12, 18),
    }
    low, high = tier_ranges.get(enemy_tier, (3, 6))
    # Floor adds a small bonus
    floor_bonus = min(floor_number, 5)
    return rng.randint(low, min(high, low + floor_bonus))


# ---------- Phase 16C: Rarity Colors & Boss Drop Logic ----------

# Rarity tier ordering for comparisons and upgrades
RARITY_TIER_ORDER: list[str] = ["common", "magic", "rare", "epic", "unique"]

# Canonical rarity colors (hex) — matches client overlayRenderer + CSS
RARITY_COLORS: dict[str, str] = {
    "common":   "#9d9d9d",
    "uncommon": "#9d9d9d",  # Legacy alias → gray (same as common)
    "magic":    "#4488ff",
    "rare":     "#ffcc00",
    "epic":     "#b040ff",
    "unique":   "#ff8800",
    "set":      "#00cc44",
}


def get_rarity_color(rarity: str) -> str:
    """Return the hex color for a rarity tier."""
    return RARITY_COLORS.get(rarity, RARITY_COLORS["common"])


def get_rarity_display_name(rarity: str) -> str:
    """Return a human-readable display name for a rarity tier."""
    names = {
        "common": "Common",
        "uncommon": "Common",  # Legacy mapping
        "magic": "Magic",
        "rare": "Rare",
        "epic": "Epic",
        "unique": "Unique",
        "set": "Set",
    }
    return names.get(rarity, "Common")


# Boss guaranteed minimum rarity by floor bracket
_BOSS_GUARANTEED_RARITY: dict[tuple[int, int], str] = {
    (1, 4):   "magic",    # All bosses guarantee at least Magic
    (5, 7):   "rare",     # Floor 5+ bosses guarantee Rare
    (8, 99):  "epic",     # Floor 8+ bosses guarantee Epic
}

# Boss item drop counts by floor bracket
_BOSS_DROP_COUNTS: dict[tuple[int, int], tuple[int, int]] = {
    (1, 4):   (2, 3),
    (5, 7):   (2, 4),
    (8, 99):  (3, 4),
}


def get_boss_guaranteed_rarity(floor_number: int) -> str:
    """Get the minimum guaranteed rarity for boss drops on a given floor.

    Returns:
        Rarity string: "magic" (floor 1–4), "rare" (5–7), "epic" (8+).
    """
    for (low, high), rarity in _BOSS_GUARANTEED_RARITY.items():
        if low <= floor_number <= high:
            return rarity
    return "magic"


def get_boss_drop_count(floor_number: int, rng: random.Random) -> int:
    """Get the number of items a boss drops based on floor bracket."""
    for (low, high), (min_drops, max_drops) in _BOSS_DROP_COUNTS.items():
        if low <= floor_number <= high:
            return rng.randint(min_drops, max_drops)
    return rng.randint(2, 3)


def enforce_minimum_rarity(rolled_rarity: str, minimum_rarity: str) -> str:
    """Ensure rolled rarity is at least the minimum tier.

    If rolled rarity is below the minimum, upgrade it.
    Uses RARITY_TIER_ORDER for comparison.
    """
    try:
        rolled_idx = RARITY_TIER_ORDER.index(rolled_rarity)
    except ValueError:
        rolled_idx = 0
    try:
        min_idx = RARITY_TIER_ORDER.index(minimum_rarity)
    except ValueError:
        min_idx = 0

    if rolled_idx < min_idx:
        return minimum_rarity
    return rolled_rarity


def boss_has_unique_chance(floor_number: int, rng: random.Random) -> bool:
    """Floor 8+ bosses have a 10% chance to drop a Unique/Set item.

    Returns True if the roll succeeds.
    """
    if floor_number >= 8:
        return rng.random() < 0.10
    return False


# ---------- Phase 16D: Unique Item Generation ----------


def generate_unique(
    unique_id: str,
    uniques_config: dict | None = None,
) -> Item | None:
    """Generate a Unique item instance from uniques_config.json.

    Uniques have fixed, curated stats — no random affixes. They receive a
    unique instance_id (UUID) like all generated items.

    Args:
        unique_id: The unique item ID (e.g., "unique_soulreaver").
        uniques_config: Override config (for testing).

    Returns:
        Fully-formed Item with Rarity.UNIQUE and curated stats, or None if
        the unique_id is not found.
    """
    config = uniques_config or load_uniques_config()
    uniques = config.get("uniques", {})
    raw = uniques.get(unique_id)
    if raw is None:
        return None

    stat_bonuses = StatBonuses(**raw.get("stat_bonuses", {}))
    equip_slot = raw.get("equip_slot")
    weapon_category = raw.get("weapon_category", "")  # Phase 16: class-lock category

    # Build special effect metadata stored in affixes list for transport
    special_effect = raw.get("special_effect", {})
    affixes_data = []
    if special_effect:
        affixes_data.append({
            "affix_id": special_effect.get("effect_id", ""),
            "type": "unique_effect",
            "name": special_effect.get("description", ""),
            "stat": special_effect.get("type", ""),
            "value": special_effect.get("value", 0),
            "effect": special_effect,  # Full effect data for combat system lookups
        })

    instance_id = str(uuid.uuid4())

    return Item(
        item_id=unique_id,
        name=raw.get("name", unique_id),
        item_type=raw.get("item_type", "weapon"),
        rarity=Rarity.UNIQUE,
        equip_slot=equip_slot,
        stat_bonuses=stat_bonuses,
        consumable_effect=None,
        description=raw.get("description", ""),
        sell_value=raw.get("sell_value", 100),
        instance_id=instance_id,
        base_type_id=unique_id,
        display_name=raw.get("name", unique_id),
        base_stats=stat_bonuses.model_copy(),
        affixes=affixes_data,
        item_level=raw.get("item_level", 14),
        weapon_category=weapon_category,
    )


def get_all_unique_ids(uniques_config: dict | None = None) -> list[str]:
    """Return all unique item IDs from the uniques config."""
    config = uniques_config or load_uniques_config()
    return list(config.get("uniques", {}).keys())


def get_unique_definition(unique_id: str, uniques_config: dict | None = None) -> dict | None:
    """Return the raw unique definition dict, or None if not found."""
    config = uniques_config or load_uniques_config()
    return config.get("uniques", {}).get(unique_id)


def roll_unique_drop(
    enemy_tier: str,
    floor_number: int = 1,
    magic_find_pct: float = 0.0,
    dropped_unique_ids: set[str] | None = None,
    enemy_type: str = "",
    rng: random.Random | None = None,
    uniques_config: dict | None = None,
) -> Item | None:
    """Attempt to roll a unique item drop from an enemy kill.

    Unique drop rules:
    - Only drop from Elite and Boss tier enemies
    - Base chance: 0.5% per item dropped (modified by magic find and floor depth)
    - Each unique can only drop once per dungeon run (tracked by dropped_unique_ids)
    - Weighted by enemy type for thematic drops

    Args:
        enemy_tier: Enemy difficulty tier ("swarm", "fodder", "mid", "elite", "boss").
        floor_number: Current dungeon floor.
        magic_find_pct: Player's magic find bonus (decimal).
        dropped_unique_ids: Set of unique IDs already dropped this run (de-dupe).
        enemy_type: Enemy type for thematic weighting (e.g., "undead", "demon").
        rng: Random instance for deterministic tests.
        uniques_config: Override config (for testing).

    Returns:
        A generated Unique Item, or None if no unique drops.
    """
    if rng is None:
        rng = random.Random()

    config = uniques_config or load_uniques_config()
    drop_rules = config.get("drop_rules", {})

    # Only Elite and Boss enemies can drop uniques
    allowed_tiers = drop_rules.get("allowed_tiers", ["elite", "boss"])
    if enemy_tier not in allowed_tiers:
        return None

    # Base drop chance (0.5% = 0.005)
    base_chance = drop_rules.get("base_drop_chance", 0.005)

    # Floor scaling
    floor_scaling = drop_rules.get("floor_scaling", {})
    floor_mult = 1.0
    for threshold_str in sorted(floor_scaling.keys(), key=int, reverse=True):
        if floor_number >= int(threshold_str):
            floor_mult = floor_scaling[threshold_str]
            break

    # Magic find bonus
    mf_mult = 1.0 + magic_find_pct

    effective_chance = base_chance * floor_mult * mf_mult

    # Boss gets a significant bonus
    if enemy_tier == "boss":
        effective_chance *= 3.0

    # Roll the drop check
    if rng.random() >= effective_chance:
        return None

    # Build weighted pool of available uniques (excluding already-dropped)
    if dropped_unique_ids is None:
        dropped_unique_ids = set()

    uniques = config.get("uniques", {})
    available = {uid: udef for uid, udef in uniques.items()
                 if uid not in dropped_unique_ids}

    if not available:
        return None

    # Build weights — enemy type weighting
    enemy_weights = config.get("enemy_type_weights", {}).get(enemy_type, {})

    weighted_ids = []
    weights = []
    for uid in available:
        base_weight = 1.0
        # Apply enemy-type thematic weighting
        if uid in enemy_weights:
            base_weight = enemy_weights[uid]
        weighted_ids.append(uid)
        weights.append(base_weight)

    if not weighted_ids:
        return None

    chosen_id = rng.choices(weighted_ids, weights=weights, k=1)[0]
    return generate_unique(chosen_id, config)


def has_unique_equipped(player_equipment: dict, unique_id: str) -> bool:
    """Check if a player has a specific unique item equipped.

    Args:
        player_equipment: The player's equipment dict (slot_name -> item_data dict).
        unique_id: The unique item ID to check for (e.g., "unique_voidedge").

    Returns:
        True if the unique is equipped in any slot.
    """
    if not player_equipment:
        return False
    for slot_name, item_data in player_equipment.items():
        if item_data and item_data.get("item_id") == unique_id:
            return True
    return False


def get_unique_special_effect(player_equipment: dict, unique_id: str) -> dict | None:
    """Return the special_effect dict for an equipped unique, or None.

    Reads the effect from the item's affixes list (unique effects are stored
    as a single affix entry with type='unique_effect').
    """
    if not player_equipment:
        return None
    for slot_name, item_data in player_equipment.items():
        if item_data and item_data.get("item_id") == unique_id:
            for affix in item_data.get("affixes", []):
                if affix.get("type") == "unique_effect":
                    return affix.get("effect", {})
    return None


def get_all_equipped_unique_effects(player_equipment: dict) -> list[dict]:
    """Return all unique special effects currently equipped on a player.

    Returns a list of effect dicts from all equipped unique items.
    """
    effects = []
    if not player_equipment:
        return effects
    for slot_name, item_data in player_equipment.items():
        if not item_data:
            continue
        if item_data.get("rarity") != "unique":
            continue
        for affix in item_data.get("affixes", []):
            if affix.get("type") == "unique_effect":
                effect = affix.get("effect", {})
                if effect:
                    effect["_source_item_id"] = item_data.get("item_id", "")
                    effects.append(effect)
    return effects


# ---------- Phase 16E: Set Item Generation ----------


def generate_set_piece(
    set_id: str,
    piece_id: str,
    sets_config: dict | None = None,
) -> Item | None:
    """Generate a Set item instance from sets_config.json.

    Set pieces have fixed, curated stats — no random affixes. They receive a
    unique instance_id (UUID) like all generated items.

    Args:
        set_id: The set ID (e.g., "crusaders_oath").
        piece_id: The piece ID within the set (e.g., "crusaders_oath_weapon").
        sets_config: Override config (for testing).

    Returns:
        Fully-formed Item with Rarity.SET and curated stats, or None if not found.
    """
    from app.core.set_bonuses import load_sets_config

    config = sets_config or load_sets_config()
    sets = config.get("sets", {})
    set_def = sets.get(set_id)
    if set_def is None:
        return None

    # Find the specific piece
    piece_def = None
    for p in set_def.get("pieces", []):
        if p.get("piece_id") == piece_id:
            piece_def = p
            break

    if piece_def is None:
        return None

    stat_bonuses = StatBonuses(**piece_def.get("stat_bonuses", {}))
    equip_slot = piece_def.get("equip_slot")
    item_type = piece_def.get("item_type", equip_slot or "weapon")
    weapon_category = piece_def.get("weapon_category", "")  # Phase 16: class-lock category

    # Set item affixes carry set metadata for client display
    affixes_data = [{
        "affix_id": f"set_{set_id}",
        "type": "set_bonus",
        "name": set_def.get("name", set_id),
        "stat": "set_id",
        "value": set_id,
    }]

    instance_id = str(uuid.uuid4())

    return Item(
        item_id=piece_id,
        name=piece_def.get("name", piece_id),
        item_type=item_type,
        rarity=Rarity.SET,
        equip_slot=equip_slot,
        stat_bonuses=stat_bonuses,
        consumable_effect=None,
        description=piece_def.get("description", ""),
        sell_value=piece_def.get("sell_value", 80),
        instance_id=instance_id,
        base_type_id=piece_id,
        display_name=piece_def.get("name", piece_id),
        base_stats=stat_bonuses.model_copy(),
        affixes=affixes_data,
        item_level=piece_def.get("item_level", 14),
        weapon_category=weapon_category,
    )


def get_all_set_piece_ids(sets_config: dict | None = None) -> list[tuple[str, str]]:
    """Return all (set_id, piece_id) pairs from the sets config.

    Returns:
        List of (set_id, piece_id) tuples.
    """
    from app.core.set_bonuses import load_sets_config

    config = sets_config or load_sets_config()
    result = []
    for set_id, set_def in config.get("sets", {}).items():
        for piece in set_def.get("pieces", []):
            result.append((set_id, piece.get("piece_id", "")))
    return result


def roll_set_drop(
    enemy_tier: str,
    floor_number: int = 1,
    magic_find_pct: float = 0.0,
    dropped_set_piece_ids: set[str] | None = None,
    player_class: str = "",
    rng: random.Random | None = None,
    sets_config: dict | None = None,
) -> Item | None:
    """Attempt to roll a set item drop from an enemy kill.

    Set drop rules:
    - Only drop from Elite and Boss tier enemies
    - Base chance: 0.3% per item dropped (modified by magic find and floor depth)
    - Each set piece can only drop once per dungeon run (tracked by dropped_set_piece_ids)
    - Weighted by player class affinity

    Args:
        enemy_tier: Enemy difficulty tier ("swarm", "fodder", "mid", "elite", "boss").
        floor_number: Current dungeon floor.
        magic_find_pct: Player's magic find bonus (decimal).
        dropped_set_piece_ids: Set of piece IDs already dropped this run.
        player_class: Player's class for affinity weighting (e.g., "crusader").
        rng: Random instance for deterministic tests.
        sets_config: Override config (for testing).

    Returns:
        A generated Set Item, or None if no set drops.
    """
    from app.core.set_bonuses import load_sets_config

    if rng is None:
        rng = random.Random()

    config = sets_config or load_sets_config()
    drop_rules = config.get("drop_rules", {})

    # Only Elite and Boss enemies can drop set items
    allowed_tiers = drop_rules.get("allowed_tiers", ["elite", "boss"])
    if enemy_tier not in allowed_tiers:
        return None

    # Base drop chance (0.3% = 0.003)
    base_chance = drop_rules.get("base_drop_chance", 0.003)

    # Floor scaling
    floor_scaling = drop_rules.get("floor_scaling", {})
    floor_mult = 1.0
    for threshold_str in sorted(floor_scaling.keys(), key=int, reverse=True):
        if floor_number >= int(threshold_str):
            floor_mult = floor_scaling[threshold_str]
            break

    # Magic find bonus
    mf_mult = 1.0 + magic_find_pct

    effective_chance = base_chance * floor_mult * mf_mult

    # Boss gets a significant bonus
    if enemy_tier == "boss":
        effective_chance *= 3.0

    # Roll the drop check
    if rng.random() >= effective_chance:
        return None

    # Build weighted pool of available set pieces (excluding already-dropped)
    if dropped_set_piece_ids is None:
        dropped_set_piece_ids = set()

    sets = config.get("sets", {})
    class_weights = config.get("class_affinity_weights", {}).get(player_class, {})

    weighted_pieces = []
    weights = []

    for set_id, set_def in sets.items():
        base_weight = class_weights.get(set_id, 1.0)
        for piece in set_def.get("pieces", []):
            piece_id = piece.get("piece_id", "")
            if piece_id in dropped_set_piece_ids:
                continue
            weighted_pieces.append((set_id, piece_id))
            weights.append(base_weight)

    if not weighted_pieces:
        return None

    chosen = rng.choices(weighted_pieces, weights=weights, k=1)[0]
    chosen_set_id, chosen_piece_id = chosen
    return generate_set_piece(chosen_set_id, chosen_piece_id, config)
