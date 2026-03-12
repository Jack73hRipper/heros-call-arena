"""
Combat Engine — Pure game logic, no framework dependencies.

Handles damage calculation, death checks, and combat resolution.
Supports melee and ranged attacks, cooldown tracking, and team-based victory.
Phase 16A: Expanded damage formula with crit, dodge, armor pen, % DR, life on hit, thorns.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from app.models.player import PlayerState, Position
from app.models.actions import ActionResult, ActionType
from app.core.fov import has_line_of_sight
from app.models.items import Equipment, Item, EquipSlot, StatBonuses

# Load combat config
_config_path = Path(__file__).resolve().parent.parent.parent / "configs" / "combat_config.json"
_combat_config: dict = {}


def load_combat_config(path: Path | None = None) -> dict:
    """Load combat tuning values from JSON config."""
    global _combat_config
    config_file = path or _config_path
    if config_file.exists():
        with open(config_file, "r") as f:
            _combat_config = json.load(f)
    else:
        # Sensible defaults if config missing
        _combat_config = {
            "base_health": 100,
            "base_damage": 15,
            "armor_reduction_per_point": 1,
        }
    return _combat_config


def get_combat_config() -> dict:
    if not _combat_config:
        load_combat_config()
    return _combat_config


def _get_equipment_bonuses(player: PlayerState) -> StatBonuses:
    """Extract total equipment stat bonuses from a player's equipment dict.

    PlayerState.equipment is stored as raw dicts for JSON compatibility.
    This converts them to Item models, builds an Equipment object, and
    returns the summed StatBonuses.
    """
    if not player.equipment:
        return StatBonuses()
    try:
        equip = Equipment()
        for slot_name, item_data in player.equipment.items():
            if item_data:
                item = Item(**item_data)
                slot = EquipSlot(slot_name)
                equip.set_slot(slot, item)
        return equip.total_bonuses()
    except Exception:
        return StatBonuses()


def calculate_damage(
    attacker: PlayerState,
    defender: PlayerState,
    rng: random.Random | None = None,
) -> tuple[int, dict]:
    """Calculate melee damage dealt from attacker to defender.

    Phase 16A: Full damage pipeline with crit, dodge, armor pen, % DR,
    life on hit, and thorns.
    Phase 16D: Unique item special effects integrated into damage calc.

    Returns:
        (final_damage, combat_info) where combat_info contains:
          - is_crit: bool
          - is_dodged: bool
          - life_on_hit_healed: int
          - thorns_damage: int
          - unique_lifesteal_healed: int  (Phase 16D)
          - dodge_retaliate_damage: int   (Phase 16D)
    """
    from app.core.skills import get_melee_buff_multiplier, get_effective_armor
    from app.core.item_generator import has_unique_equipped, get_all_equipped_unique_effects
    from app.core.skills import get_damage_reduction_buff_bonus, get_attack_damage_buff_bonus, get_damage_taken_multiplier, get_damage_dealt_multiplier

    if rng is None:
        rng = random.Random()

    atk_bonuses = _get_equipment_bonuses(attacker)
    melee_mult = get_melee_buff_multiplier(attacker)
    flat_atk_bonus = get_attack_damage_buff_bonus(attacker)
    config = get_combat_config()

    combat_info = {
        "is_crit": False,
        "is_dodged": False,
        "life_on_hit_healed": 0,
        "thorns_damage": 0,
        "unique_lifesteal_healed": 0,
        "dodge_retaliate_damage": 0,
    }

    # Phase 16D: Collect unique effects for attacker and defender
    atk_unique_effects = get_all_equipped_unique_effects(attacker.equipment)
    def_unique_effects = get_all_equipped_unique_effects(defender.equipment)

    # Phase 16D: Greed Sigil damage penalty (attacker)
    damage_mult = 1.0
    for effect in atk_unique_effects:
        if effect.get("type") == "damage_dealt_penalty":
            damage_mult += effect.get("value", 0)  # value is negative, e.g. -0.15

    # Phase 16D: Bloodpact low HP damage bonus (attacker)
    for effect in atk_unique_effects:
        if effect.get("type") == "low_hp_damage_bonus":
            threshold = effect.get("hp_threshold", 0.30)
            if attacker.max_hp > 0 and (attacker.hp / attacker.max_hp) < threshold:
                damage_mult += effect.get("value", 0)

    # Step 1: Dodge check
    dodge_cap = config.get("dodge_cap", 0.40)
    effective_dodge = min(dodge_cap, defender.dodge_chance)
    if effective_dodge > 0 and rng.random() < effective_dodge:
        combat_info["is_dodged"] = True
        # Phase 16D: Wraithmantle — on dodge, deal damage to attacker
        for effect in def_unique_effects:
            if effect.get("type") == "on_dodge_damage":
                retaliate_dmg = effect.get("value", 0)
                if retaliate_dmg > 0 and attacker.is_alive:
                    attacker.hp = max(0, attacker.hp - retaliate_dmg)
                    combat_info["dodge_retaliate_damage"] = retaliate_dmg
                    if attacker.hp <= 0:
                        attacker.is_alive = False
        return 0, combat_info

    # Step 2: Raw damage (with unique damage multiplier + flat attack bonus from auras)
    raw_damage = int((attacker.attack_damage + atk_bonuses.attack_damage + flat_atk_bonus) * melee_mult * max(0.01, damage_mult))

    # Step 3: Armor after penetration
    effective_armor_val = get_effective_armor(defender)
    # Phase 16D: Voidedge — ignore 50% of target armor
    for effect in atk_unique_effects:
        if effect.get("type") == "armor_ignore_pct":
            effective_armor_val = int(effective_armor_val * (1.0 - effect.get("value", 0)))
    armor_after_pen = max(0, effective_armor_val - attacker.armor_pen)
    reduction = armor_after_pen * config.get("armor_reduction_per_point", 1)
    post_armor = max(1, raw_damage - reduction)

    # Step 4: Percentage-based damage reduction
    dr_cap = config.get("damage_reduction_cap", 0.50)
    effective_dr = min(dr_cap, defender.damage_reduction_pct + get_damage_reduction_buff_bonus(defender))
    # Phase 16D: Bonecage flat DR bonus
    for effect in def_unique_effects:
        if effect.get("type") == "flat_damage_reduction_bonus":
            effective_dr = min(dr_cap, effective_dr + effect.get("value", 0))
    post_pct_dr = max(1, int(post_armor * (1.0 - effective_dr)))

    # Step 5: Crit check
    crit_chance = min(0.50, attacker.crit_chance)
    if crit_chance > 0 and rng.random() < crit_chance:
        combat_info["is_crit"] = True
        crit_damage_cap = config.get("crit_damage_cap", 3.0)
        crit_mult = min(crit_damage_cap, attacker.crit_damage)
        # Phase 16D: The Whisper — override crit multiplier to 3×
        for effect in atk_unique_effects:
            if effect.get("type") == "override_crit_multiplier":
                crit_mult = min(crit_damage_cap, effect.get("value", crit_mult))
        final_damage = max(1, int(post_pct_dr * crit_mult))
    else:
        final_damage = post_pct_dr

    # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
    dmg_taken_mult = get_damage_taken_multiplier(defender)
    if dmg_taken_mult != 1.0:
        final_damage = max(1, int(final_damage * dmg_taken_mult))

    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble)
    dmg_dealt_mult = get_damage_dealt_multiplier(attacker)
    if dmg_dealt_mult != 1.0:
        final_damage = max(1, int(final_damage * dmg_dealt_mult))

    # Step 6: Life on hit
    if final_damage > 0 and attacker.life_on_hit > 0:
        heal_amount = attacker.life_on_hit
        old_hp = attacker.hp
        attacker.hp = min(attacker.max_hp, attacker.hp + heal_amount)
        combat_info["life_on_hit_healed"] = attacker.hp - old_hp

    # Phase 16D: Soulreaver — melee lifesteal (heals 15% of damage dealt)
    if final_damage > 0:
        for effect in atk_unique_effects:
            if effect.get("type") == "melee_lifesteal_pct":
                lifesteal_pct = effect.get("value", 0)
                lifesteal_heal = max(1, int(final_damage * lifesteal_pct))
                old_hp = attacker.hp
                attacker.hp = min(attacker.max_hp, attacker.hp + lifesteal_heal)
                combat_info["unique_lifesteal_healed"] = attacker.hp - old_hp

    # Step 7: Thorns (equipment-based)
    if final_damage > 0 and defender.thorns > 0:
        thorns_dmg = defender.thorns
        attacker.hp = max(0, attacker.hp - thorns_dmg)
        combat_info["thorns_damage"] = thorns_dmg
        if attacker.hp <= 0:
            attacker.is_alive = False

    # Phase 25C: Buff-based thorns (Grave Thorns skill) — flat retaliation, ignores armor
    if final_damage > 0 and attacker.is_alive:
        thorns_buff = next((b for b in defender.active_buffs if b.get("stat") == "thorns_damage"), None)
        if thorns_buff:
            buff_thorns_dmg = thorns_buff.get("magnitude", 0)
            if buff_thorns_dmg > 0:
                attacker.hp = max(0, attacker.hp - buff_thorns_dmg)
                combat_info["thorns_damage"] = combat_info.get("thorns_damage", 0) + buff_thorns_dmg
                if attacker.hp <= 0:
                    attacker.is_alive = False

    return final_damage, combat_info


def calculate_damage_simple(attacker: PlayerState, defender: PlayerState) -> int:
    """Backward-compatible simple damage calculation (no crit/dodge/thorns).

    Used by existing callers that expect a plain int return.
    Phase 21C: Applies damage_taken_multiplier from Bard Dirge of Weakness.
    """
    from app.core.skills import get_melee_buff_multiplier, get_effective_armor, get_attack_damage_buff_bonus, get_damage_taken_multiplier, get_damage_dealt_multiplier

    atk_bonuses = _get_equipment_bonuses(attacker)
    melee_mult = get_melee_buff_multiplier(attacker)
    flat_atk_bonus = get_attack_damage_buff_bonus(attacker)
    raw_damage = int((attacker.attack_damage + atk_bonuses.attack_damage + flat_atk_bonus) * melee_mult)
    effective_armor = get_effective_armor(defender)
    reduction = effective_armor * get_combat_config().get("armor_reduction_per_point", 1)
    final_damage = max(1, raw_damage - reduction)
    # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
    dmg_taken_mult = get_damage_taken_multiplier(defender)
    if dmg_taken_mult != 1.0:
        final_damage = max(1, int(final_damage * dmg_taken_mult))
    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble)
    dmg_dealt_mult = get_damage_dealt_multiplier(attacker)
    if dmg_dealt_mult != 1.0:
        final_damage = max(1, int(final_damage * dmg_dealt_mult))
    return final_damage


def calculate_ranged_damage(
    attacker: PlayerState,
    defender: PlayerState,
    rng: random.Random | None = None,
) -> tuple[int, dict]:
    """Calculate ranged damage dealt from attacker to defender.

    Phase 16A: Full damage pipeline with crit, dodge, armor pen, % DR,
    life on hit, and thorns.
    Phase 16D: Unique item special effects integrated into ranged damage calc.

    Returns:
        (final_damage, combat_info) where combat_info is the same shape
        as calculate_damage.
    """
    from app.core.skills import get_ranged_buff_multiplier, get_effective_armor
    from app.core.item_generator import get_all_equipped_unique_effects
    from app.core.skills import get_damage_reduction_buff_bonus, get_damage_taken_multiplier, get_damage_dealt_multiplier

    if rng is None:
        rng = random.Random()

    atk_bonuses = _get_equipment_bonuses(attacker)
    ranged_mult = get_ranged_buff_multiplier(attacker)
    config = get_combat_config()

    combat_info = {
        "is_crit": False,
        "is_dodged": False,
        "life_on_hit_healed": 0,
        "thorns_damage": 0,
        "unique_lifesteal_healed": 0,
        "dodge_retaliate_damage": 0,
        "plaguebow_applied": False,
    }

    # Phase 16D: Collect unique effects
    atk_unique_effects = get_all_equipped_unique_effects(attacker.equipment)
    def_unique_effects = get_all_equipped_unique_effects(defender.equipment)

    # Phase 16D: Greed Sigil damage penalty
    damage_mult = 1.0
    for effect in atk_unique_effects:
        if effect.get("type") == "damage_dealt_penalty":
            damage_mult += effect.get("value", 0)

    # Phase 16D: Bloodpact low HP damage bonus
    for effect in atk_unique_effects:
        if effect.get("type") == "low_hp_damage_bonus":
            threshold = effect.get("hp_threshold", 0.30)
            if attacker.max_hp > 0 and (attacker.hp / attacker.max_hp) < threshold:
                damage_mult += effect.get("value", 0)

    # Step 1: Dodge check
    dodge_cap = config.get("dodge_cap", 0.40)
    effective_dodge = min(dodge_cap, defender.dodge_chance)
    if effective_dodge > 0 and rng.random() < effective_dodge:
        combat_info["is_dodged"] = True
        # Phase 16D: Wraithmantle on-dodge retaliation
        for effect in def_unique_effects:
            if effect.get("type") == "on_dodge_damage":
                retaliate_dmg = effect.get("value", 0)
                if retaliate_dmg > 0 and attacker.is_alive:
                    attacker.hp = max(0, attacker.hp - retaliate_dmg)
                    combat_info["dodge_retaliate_damage"] = retaliate_dmg
                    if attacker.hp <= 0:
                        attacker.is_alive = False
        return 0, combat_info

    # Step 2: Raw damage (with unique damage multiplier)
    raw_damage = int((attacker.ranged_damage + atk_bonuses.ranged_damage) * ranged_mult * max(0.01, damage_mult))

    # Step 3: Armor after penetration
    effective_armor_val = get_effective_armor(defender)
    # Phase 16D: Voidedge — ignore 50% of target armor
    for effect in atk_unique_effects:
        if effect.get("type") == "armor_ignore_pct":
            effective_armor_val = int(effective_armor_val * (1.0 - effect.get("value", 0)))
    armor_after_pen = max(0, effective_armor_val - attacker.armor_pen)
    reduction = armor_after_pen * config.get("armor_reduction_per_point", 1)
    post_armor = max(1, raw_damage - reduction)

    # Step 4: Percentage-based damage reduction
    dr_cap = config.get("damage_reduction_cap", 0.50)
    effective_dr = min(dr_cap, defender.damage_reduction_pct + get_damage_reduction_buff_bonus(defender))
    # Phase 16D: Bonecage flat DR bonus
    for effect in def_unique_effects:
        if effect.get("type") == "flat_damage_reduction_bonus":
            effective_dr = min(dr_cap, effective_dr + effect.get("value", 0))
    post_pct_dr = max(1, int(post_armor * (1.0 - effective_dr)))

    # Step 5: Crit check
    crit_chance = min(0.50, attacker.crit_chance)
    if crit_chance > 0 and rng.random() < crit_chance:
        combat_info["is_crit"] = True
        crit_damage_cap = config.get("crit_damage_cap", 3.0)
        crit_mult = min(crit_damage_cap, attacker.crit_damage)
        # Phase 16D: The Whisper — override crit multiplier
        for effect in atk_unique_effects:
            if effect.get("type") == "override_crit_multiplier":
                crit_mult = min(crit_damage_cap, effect.get("value", crit_mult))
        final_damage = max(1, int(post_pct_dr * crit_mult))
    else:
        final_damage = post_pct_dr

    # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
    dmg_taken_mult = get_damage_taken_multiplier(defender)
    if dmg_taken_mult != 1.0:
        final_damage = max(1, int(final_damage * dmg_taken_mult))

    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble)
    dmg_dealt_mult = get_damage_dealt_multiplier(attacker)
    if dmg_dealt_mult != 1.0:
        final_damage = max(1, int(final_damage * dmg_dealt_mult))

    # Step 6: Life on hit
    if final_damage > 0 and attacker.life_on_hit > 0:
        heal_amount = attacker.life_on_hit
        old_hp = attacker.hp
        attacker.hp = min(attacker.max_hp, attacker.hp + heal_amount)
        combat_info["life_on_hit_healed"] = attacker.hp - old_hp

    # Phase 16D: Plaguebow — ranged hits apply poison DoT (flagged for turn_resolver)
    if final_damage > 0:
        for effect in atk_unique_effects:
            if effect.get("type") == "ranged_apply_dot":
                combat_info["plaguebow_applied"] = True
                combat_info["plaguebow_dot"] = {
                    "damage_per_tick": effect.get("damage_per_tick", 4),
                    "duration": effect.get("duration", 2),
                    "dot_id": effect.get("dot_id", "plaguebow_poison"),
                }

    # Step 7: Thorns (ranged attacks also trigger equipment thorns)
    if final_damage > 0 and defender.thorns > 0:
        thorns_dmg = defender.thorns
        attacker.hp = max(0, attacker.hp - thorns_dmg)
        combat_info["thorns_damage"] = thorns_dmg
        if attacker.hp <= 0:
            attacker.is_alive = False

    # Phase 25C: Buff-based thorns (Grave Thorns skill) — flat retaliation, ignores armor
    if final_damage > 0 and attacker.is_alive:
        thorns_buff = next((b for b in defender.active_buffs if b.get("stat") == "thorns_damage"), None)
        if thorns_buff:
            buff_thorns_dmg = thorns_buff.get("magnitude", 0)
            if buff_thorns_dmg > 0:
                attacker.hp = max(0, attacker.hp - buff_thorns_dmg)
                combat_info["thorns_damage"] = combat_info.get("thorns_damage", 0) + buff_thorns_dmg
                if attacker.hp <= 0:
                    attacker.is_alive = False

    return final_damage, combat_info


def calculate_ranged_damage_simple(attacker: PlayerState, defender: PlayerState) -> int:
    """Backward-compatible simple ranged damage calculation (no crit/dodge/thorns).

    Used by existing callers that expect a plain int return.
    Phase 21C: Applies damage_taken_multiplier from Bard Dirge of Weakness.
    """
    from app.core.skills import get_ranged_buff_multiplier, get_effective_armor, get_damage_taken_multiplier, get_damage_dealt_multiplier

    atk_bonuses = _get_equipment_bonuses(attacker)
    ranged_mult = get_ranged_buff_multiplier(attacker)
    raw_damage = int((attacker.ranged_damage + atk_bonuses.ranged_damage) * ranged_mult)
    effective_armor = get_effective_armor(defender)
    reduction = effective_armor * get_combat_config().get("armor_reduction_per_point", 1)
    final_damage = max(1, raw_damage - reduction)
    # Phase 21C: Damage-taken multiplier (Bard Dirge of Weakness)
    dmg_taken_mult = get_damage_taken_multiplier(defender)
    if dmg_taken_mult != 1.0:
        final_damage = max(1, int(final_damage * dmg_taken_mult))
    # Phase 23C: Damage-dealt multiplier (Plague Doctor Enfeeble)
    dmg_dealt_mult = get_damage_dealt_multiplier(attacker)
    if dmg_dealt_mult != 1.0:
        final_damage = max(1, int(final_damage * dmg_dealt_mult))
    return final_damage


def apply_damage(defender: PlayerState, damage: int) -> bool:
    """Apply damage to defender. Returns True if defender died.

    Invulnerable units (e.g. training dummies) take damage normally so
    damage numbers appear in the combat log, but their HP resets to max
    immediately and they can never die.

    Phase 18I: Damage absorb shields (Bone Shield) reduce incoming damage
    before it hits HP. The shield depletes and then breaks.
    """
    from app.core.skills import consume_damage_absorb

    # Phase 18I: Check for damage absorb shield
    effective_damage = damage
    if damage > 0:
        effective_damage, _absorbed = consume_damage_absorb(defender, damage)

    defender.hp = max(0, defender.hp - effective_damage)
    if defender.invulnerable:
        defender.hp = defender.max_hp
        defender.is_alive = True
        return False
    if defender.hp <= 0:
        defender.is_alive = False
        return True
    return False


def is_adjacent(pos_a: Position, pos_b: Position) -> bool:
    """Check if two positions are adjacent (including diagonals)."""
    return abs(pos_a.x - pos_b.x) <= 1 and abs(pos_a.y - pos_b.y) <= 1 and pos_a != pos_b


def is_in_range(pos_a: Position, pos_b: Position, attack_range: int) -> bool:
    """Check if pos_b is within attack_range tiles of pos_a (Euclidean)."""
    dx = pos_a.x - pos_b.x
    dy = pos_a.y - pos_b.y
    return (dx * dx + dy * dy) <= attack_range * attack_range


def can_ranged_attack(
    attacker: PlayerState,
    target_x: int,
    target_y: int,
    attack_range: int,
    obstacles: set[tuple[int, int]],
) -> tuple[bool, str]:
    """Validate whether a ranged attack can be performed.

    Returns (success, reason_if_failed).
    """
    # Check cooldown
    cd = attacker.cooldowns.get("ranged_attack", 0)
    if cd > 0:
        return False, f"Ranged attack on cooldown ({cd} turns remaining)"

    target_pos = Position(x=target_x, y=target_y)

    # Check range
    if not is_in_range(attacker.position, target_pos, attack_range):
        return False, "Target out of ranged attack range"

    # Check line of sight
    if not has_line_of_sight(
        attacker.position.x, attacker.position.y,
        target_x, target_y,
        obstacles,
    ):
        return False, "No line of sight to target"

    return True, ""


def apply_ranged_cooldown(unit: PlayerState, cooldown_turns: int = 3) -> None:
    """Set the ranged attack cooldown for a unit."""
    unit.cooldowns["ranged_attack"] = cooldown_turns


def tick_cooldowns(unit: PlayerState) -> None:
    """Decrement all cooldowns by 1 at the start of each tick (min 0)."""
    for key in list(unit.cooldowns.keys()):
        unit.cooldowns[key] = max(0, unit.cooldowns[key] - 1)
        if unit.cooldowns[key] == 0:
            del unit.cooldowns[key]


def is_valid_move(position: Position, target_x: int, target_y: int,
                  grid_width: int, grid_height: int,
                  obstacles: set[tuple[int, int]],
                  occupied: set[tuple[int, int]]) -> bool:
    """Check if a move to (target_x, target_y) is valid."""
    # Must be adjacent
    if abs(position.x - target_x) > 1 or abs(position.y - target_y) > 1:
        return False
    # Must be on grid
    if target_x < 0 or target_x >= grid_width or target_y < 0 or target_y >= grid_height:
        return False
    # Must not be obstacle
    if (target_x, target_y) in obstacles:
        return False
    # Must not be occupied by another player
    if (target_x, target_y) in occupied:
        return False
    return True


def check_victory(players: list[PlayerState]) -> str | None:
    """Return winner's player_id if only one player is alive, else None.
    Used for free-for-all (PvP with no teams)."""
    alive = [p for p in players if p.is_alive]
    if len(alive) == 1:
        return alive[0].player_id
    if len(alive) == 0:
        return "draw"
    return None


def check_team_victory(
    players: list[PlayerState],
    team_a: list[str],
    team_b: list[str],
    team_c: list[str] | None = None,
    team_d: list[str] | None = None,
    excluded_teams: set[str] | None = None,
) -> str | None:
    """Check for team-based victory (last team standing).

    Supports 2-4 teams. Only teams with at least one member are considered active.

    Phase 27D: When *excluded_teams* is provided (e.g. ``{"pve"}``), any
    player whose ``team`` attribute is in the set is ignored when counting
    survivors.  This allows PVE enemies to be alive without blocking a
    PVPVE victory check.

    Returns:
        "team_a", "team_b", "team_c", or "team_d" if that team wins,
        "draw" if all active teams are eliminated simultaneously,
        None if match continues.
    """
    teams = {
        "team_a": team_a,
        "team_b": team_b,
    }
    if team_c:
        teams["team_c"] = team_c
    if team_d:
        teams["team_d"] = team_d

    # Only consider teams that actually have members (were assigned players)
    active_teams = {name: ids for name, ids in teams.items() if ids}

    # Phase 27D: filter out units on excluded teams before checking
    if excluded_teams:
        eligible = [p for p in players if p.team not in excluded_teams]
    else:
        eligible = players

    # Check which active teams still have alive members
    surviving = []
    for name, ids in active_teams.items():
        if any(p.is_alive for p in eligible if p.player_id in ids):
            surviving.append(name)

    if len(surviving) == 1:
        return surviving[0]
    if len(surviving) == 0:
        return "draw"
    return None  # Multiple teams still alive — match continues


def are_allies(unit_a: PlayerState, unit_b: PlayerState) -> bool:
    """Check if two units are on the same team."""
    return unit_a.team == unit_b.team


# ---------------------------------------------------------------------------
# Phase 7A-1: Cooperative Movement Resolution
# ---------------------------------------------------------------------------

def resolve_movement_batch(
    move_intents: list[dict],
    players: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> list[dict]:
    """Resolve all movement actions simultaneously with swap / chain detection.

    Args:
        move_intents: List of ``{"player_id": str, "target": (tx, ty)}`` dicts
                      for every MOVE action this tick.
        players:      Full player dict (needed for positions, teams, alive).
        grid_width:   Map width.
        grid_height:  Map height.
        obstacles:    Impassable tiles.

    Returns:
        List of result dicts, one per intent:
            ``{"player_id": str, "success": bool,
               "from": (x, y), "to": (x, y) | None}``

    Resolution algorithm:
      1. Build a *desired-move* map  ``unit -> target_tile``.
      2. Reject any moves that are fundamentally invalid (off-grid, obstacle,
         not adjacent).
      3. Detect **same-target conflicts** — two+ units want the same tile.
         Resolve by priority: human > AI, then lowest player_id wins. Losers
         are marked as failed.
      4. Detect **swap pairs** — A→B's position, B→A's position, both valid.
         Mark both as approved.
      5. Detect **chain moves** — A→B's pos, B→C's pos, C→empty.  Walk each
         chain from the tail (the unit whose target is empty) back to the head
         and approve all links.  Cycles (without a free tail) are rejected.
      6. Approve any remaining moves whose target is either empty or being
         vacated by an already-approved mover.
      7. Failed movers stay in place (no cascading failures).
    """

    # Quick exit
    if not move_intents:
        return []

    # -- Step 1: Build intent map -----------------------------------------------
    # unit_id -> target tile
    intent: dict[str, tuple[int, int]] = {}
    # unit_id -> current position
    cur_pos: dict[str, tuple[int, int]] = {}
    # target -> [unit_ids wanting it]
    target_claimants: dict[tuple[int, int], list[str]] = {}

    results_map: dict[str, dict] = {}  # final results keyed by player_id

    for mi in move_intents:
        pid = mi["player_id"]
        target = mi["target"]
        player = players.get(pid)
        if not player or not player.is_alive:
            results_map[pid] = {"player_id": pid, "success": False,
                                "from": None, "to": None}
            continue
        cur_pos[pid] = (player.position.x, player.position.y)

        # -- Step 2: Basic validity (adjacent, on-grid, not obstacle) -----------
        tx, ty = target
        pos = player.position
        if (abs(pos.x - tx) > 1 or abs(pos.y - ty) > 1):
            results_map[pid] = {"player_id": pid, "success": False,
                                "from": cur_pos[pid], "to": None}
            continue
        if tx < 0 or tx >= grid_width or ty < 0 or ty >= grid_height:
            results_map[pid] = {"player_id": pid, "success": False,
                                "from": cur_pos[pid], "to": None}
            continue
        if (tx, ty) in obstacles:
            results_map[pid] = {"player_id": pid, "success": False,
                                "from": cur_pos[pid], "to": None}
            continue
        if (tx, ty) == cur_pos[pid]:
            # Moving to own tile — treat as no-op success
            results_map[pid] = {"player_id": pid, "success": True,
                                "from": cur_pos[pid], "to": cur_pos[pid]}
            continue

        intent[pid] = target
        target_claimants.setdefault(target, []).append(pid)

    # -- Step 3: Same-target conflict resolution --------------------------------
    # If 2+ units want the same tile, pick a winner by priority.
    for tile, claimants in list(target_claimants.items()):
        if len(claimants) <= 1:
            continue
        # Priority: human > AI, then alphabetical player_id as tiebreaker
        def _priority(pid: str) -> tuple:
            p = players[pid]
            return (0 if p.unit_type == "human" else 1, pid)

        claimants.sort(key=_priority)
        winner = claimants[0]
        for loser in claimants[1:]:
            intent.pop(loser, None)
            results_map[loser] = {"player_id": loser, "success": False,
                                  "from": cur_pos[loser], "to": None}
        target_claimants[tile] = [winner]

    # -- Build helper lookups ---------------------------------------------------
    # Position -> unit_id currently standing there (only movers & alive units
    # that might be blocking).
    pos_to_unit: dict[tuple[int, int], str] = {}
    for p in players.values():
        if p.is_alive and not getattr(p, 'extracted', False):
            pos_to_unit[(p.position.x, p.position.y)] = p.player_id

    # For each mover, who (if anyone) is sitting on their target?
    # unit -> occupant_pid or None
    blocked_by: dict[str, str | None] = {}
    for pid, target in intent.items():
        occ = pos_to_unit.get(target)
        if occ and occ != pid:
            blocked_by[pid] = occ
        else:
            blocked_by[pid] = None

    approved: set[str] = set()
    failed: set[str] = set()

    # -- Step 4 & 5: Detect swaps and chains ------------------------------------
    # We walk each mover through its blocking chain.  If the chain ends at an
    # empty tile or circles back (cycle), we decide accordingly.

    visited_global: set[str] = set()  # units already fully resolved

    for start_pid in list(intent.keys()):
        if start_pid in visited_global:
            continue

        # Walk the chain: start_pid -> blocker -> blocker's blocker -> ...
        chain: list[str] = []
        current = start_pid
        chain_set: set[str] = set()

        while True:
            if current in chain_set:
                # We've looped back — this is a cycle
                break
            chain.append(current)
            chain_set.add(current)

            blocker = blocked_by.get(current)
            if blocker is None:
                # Target is free (or unit not in intent) — chain ends in open space
                break
            if blocker not in intent:
                # Blocker is a non-moving unit — chain is stuck
                # BUT: if blocker is same-team, treat as "will not block" 
                # only if the non-mover is NOT moving (they stay). In Phase 7A
                # we only grant pass-through when the blocker is *also* moving
                # away. A stationary ally still blocks.
                break
            current = blocker

        # Determine if chain terminates freely or in a cycle
        if current in chain_set and len(chain) > 1 and current == chain[0]:
            # Pure cycle detected (A->B->...->A). Check if it's a swap (len 2)
            # or a rotation (len 3+).  We approve ALL members of the cycle —
            # they are effectively rotating positions simultaneously.
            cycle_start_idx = chain.index(current)
            cycle_members = chain[cycle_start_idx:]
            for pid in cycle_members:
                approved.add(pid)
                visited_global.add(pid)
        elif chain:
            # Chain ending in open space — approve from tail backwards.
            # The last unit in the chain has a free target (or is blocked by
            # a non-mover).
            tail = chain[-1]
            if blocked_by.get(tail) is None:
                # Tail target is free — approve tail, then everyone before it
                # whose target is being vacated by the next in chain.
                for pid in reversed(chain):
                    if blocked_by.get(pid) is None:
                        # free target
                        approved.add(pid)
                        visited_global.add(pid)
                    elif blocked_by[pid] in approved:
                        # target vacated by approved mover
                        approved.add(pid)
                        visited_global.add(pid)
                    else:
                        # still blocked
                        failed.add(pid)
                        visited_global.add(pid)
            else:
                # Chain ends at a stationary blocker — nobody moves
                for pid in chain:
                    if pid not in visited_global:
                        failed.add(pid)
                        visited_global.add(pid)

    # -- Step 6: Build final results --------------------------------------------
    for pid in list(intent.keys()):
        if pid in results_map:
            continue  # already resolved (basic-invalid or conflict-loser)
        if pid in approved:
            results_map[pid] = {"player_id": pid, "success": True,
                                "from": cur_pos[pid], "to": intent[pid]}
        else:
            results_map[pid] = {"player_id": pid, "success": False,
                                "from": cur_pos[pid], "to": None}

    # Return in the same order as the input intents
    ordered = []
    for mi in move_intents:
        pid = mi["player_id"]
        ordered.append(results_map.get(pid, {"player_id": pid, "success": False,
                                              "from": None, "to": None}))
    return ordered


# ---------------------------------------------------------------------------
# Phase 18D: Affix On-Hit Effects
# ---------------------------------------------------------------------------

def apply_affix_on_hit_effects(
    attacker: PlayerState,
    defender: PlayerState,
    damage: int,
    combat_info: dict,
    rng: random.Random | None = None,
) -> None:
    """Apply affix-based on-hit effects after a successful attack.

    Checks the attacker's affixes list and applies:
    - Cursed: extend victim's lowest-remaining cooldown by 1 turn
    - Cold Enchanted: 30% chance to apply 1-turn slow debuff
    - Mana Burn: extend victim's highest active cooldown by 2 turns
    - Spectral Hit: heal attacker for 20% of damage dealt

    Mutates attacker/defender in place. Updates combat_info with affix effect details.

    Args:
        attacker: The attacking unit
        defender: The defending unit (damage already applied)
        damage: Amount of damage dealt
        combat_info: Combat info dict to update with affix effect details
        rng: Random instance for chance-based effects
    """
    if not getattr(attacker, 'affixes', None) or damage <= 0:
        return

    if rng is None:
        rng = random.Random()

    from app.core.monster_rarity import get_affix

    # Initialize affix results in combat_info
    combat_info["affix_on_hit"] = []

    for affix_id in attacker.affixes:
        affix_data = get_affix(affix_id)
        if not affix_data:
            continue

        for effect in affix_data.get("effects", []):
            effect_type = effect.get("type", "")

            if effect_type == "on_hit_extend_cooldowns":
                # Cursed / Mana Burn: extend victim cooldowns
                turns = effect.get("turns", 1)
                target_selection = effect.get("target", "lowest_remaining")

                if defender.cooldowns:
                    if target_selection == "highest_active":
                        # Mana Burn: extend the highest active cooldown
                        max_cd_key = max(defender.cooldowns, key=lambda k: defender.cooldowns[k])
                        defender.cooldowns[max_cd_key] = defender.cooldowns[max_cd_key] + turns
                        combat_info["affix_on_hit"].append({
                            "affix": affix_id,
                            "effect": "extend_cooldown",
                            "target_cooldown": max_cd_key,
                            "turns_added": turns,
                        })
                    else:
                        # Cursed: extend the lowest-remaining cooldown
                        min_cd_key = min(defender.cooldowns, key=lambda k: defender.cooldowns[k])
                        defender.cooldowns[min_cd_key] = defender.cooldowns[min_cd_key] + turns
                        combat_info["affix_on_hit"].append({
                            "affix": affix_id,
                            "effect": "extend_cooldown",
                            "target_cooldown": min_cd_key,
                            "turns_added": turns,
                        })

            elif effect_type == "on_hit_slow":
                # Cold Enchanted: chance to slow
                chance = effect.get("chance", 0.30)
                duration = effect.get("duration", 1)
                if rng.random() < chance and defender.is_alive:
                    slow_buff = {
                        "buff_id": "cold_enchanted_slow",
                        "type": "debuff",
                        "stat": "slow",
                        "magnitude": 1,
                        "turns_remaining": duration,
                        "is_aura": False,
                        "source": attacker.player_id,
                    }
                    # Don't stack — refresh if already present
                    defender.active_buffs = [
                        b for b in defender.active_buffs
                        if b.get("buff_id") != "cold_enchanted_slow"
                    ]
                    defender.active_buffs.append(slow_buff)
                    combat_info["affix_on_hit"].append({
                        "affix": affix_id,
                        "effect": "slow",
                        "duration": duration,
                    })

            elif effect_type == "life_steal_pct":
                # Spectral Hit: heal attacker for % of damage dealt
                pct = effect.get("value", 0.20)
                heal_amount = max(1, int(damage * pct))
                if attacker.is_alive:
                    old_hp = attacker.hp
                    attacker.hp = min(attacker.max_hp, attacker.hp + heal_amount)
                    actual_heal = attacker.hp - old_hp
                    if actual_heal > 0:
                        combat_info["affix_on_hit"].append({
                            "affix": affix_id,
                            "effect": "life_steal",
                            "healed": actual_heal,
                        })
