"""
Skills System — Skill config loading, validation, and effect resolution.

Phase 6A: Loads skills_config.json, provides skill lookups by ID and class,
and validates whether a player can use a given skill.

Phase 6B: Adds skill effect handlers (heal, multi-hit, ranged, buff, teleport)
and buff tick logic for the turn resolver.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models.player import PlayerState, Position
from app.models.actions import ActionResult, ActionType
from app.core.fov import has_line_of_sight


# ---------- Config Loading ----------

_config_path = Path(__file__).resolve().parent.parent.parent / "configs" / "skills_config.json"
_skills_config: dict | None = None


def load_skills_config(path: Path | None = None) -> dict:
    """Load skills configuration from JSON. Caches after first load."""
    global _skills_config
    if _skills_config is not None:
        return _skills_config

    config_file = path or _config_path
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            _skills_config = json.load(f)
    else:
        _skills_config = {"skills": {}, "class_skills": {}, "max_skill_slots": 4}
    return _skills_config


def _get_config() -> dict:
    """Internal helper — ensures config is loaded, returns cached dict."""
    if _skills_config is None:
        load_skills_config()
    return _skills_config  # type: ignore[return-value]


def clear_skills_cache() -> None:
    """Clear the cached config. Useful for tests that swap config files."""
    global _skills_config
    _skills_config = None


# ---------- Skill Lookups ----------

def get_skill(skill_id: str) -> dict | None:
    """Return the full skill definition dict for a given skill_id, or None."""
    config = _get_config()
    return config.get("skills", {}).get(skill_id)


def get_all_skills() -> dict[str, dict]:
    """Return the full skills registry dict (skill_id -> definition)."""
    config = _get_config()
    return config.get("skills", {})


def get_class_skills(class_id: str) -> list[str]:
    """Return ordered list of skill_ids available to a given class.

    Returns an empty list if the class has no skills or the class_id
    is not found in the config.
    """
    config = _get_config()
    return config.get("class_skills", {}).get(class_id, [])


def get_max_skill_slots() -> int:
    """Return the maximum number of skill slots per unit."""
    config = _get_config()
    return config.get("max_skill_slots", 4)


# ---------- Validation ----------

def can_use_skill(player: PlayerState, skill_id: str) -> tuple[bool, str]:
    """Validate whether a player can use a specific skill right now.

    Checks:
    1. Skill exists in config
    2. Player is alive
    3. Player's class is in the skill's allowed_classes
    4. Skill is not on cooldown

    Returns:
        (True, "") if valid, or (False, "reason string") if not.
    """
    skill_def = get_skill(skill_id)
    if skill_def is None:
        return False, f"Unknown skill: {skill_id}"

    if not player.is_alive:
        return False, f"{player.username} is dead and cannot use skills"

    # Class restriction
    allowed = skill_def.get("allowed_classes", [])
    if allowed and player.class_id not in allowed:
        return False, f"{player.username}'s class ({player.class_id}) cannot use {skill_def['name']}"

    # Cooldown check
    cd_remaining = player.cooldowns.get(skill_id, 0)
    if cd_remaining > 0:
        return False, f"{skill_def['name']} is on cooldown ({cd_remaining} turns remaining)"

    return True, ""


# ---------- Buff Helpers ----------

def tick_buffs(player: PlayerState) -> list[dict]:
    """Decrement all active buff durations by 1, apply per-tick effects, and remove expired ones.

    Handles:
      - Standard buffs: decrement turns_remaining, remove at 0
      - DoT effects: apply damage_per_tick each turn, remove at 0 turns
      - HoT effects: apply heal_per_tick each turn, remove at 0 turns
      - Charge-based effects: only removed when charges reach 0 (not turn-based)

    Returns list of removed buff dicts (for logging/UI) and a list of tick_events.
    """
    if not player.active_buffs:
        return []
    remaining = []
    expired = []
    for buff in player.active_buffs:
        buff_type = buff.get("type", "buff")

        # Charge-based effects don't tick down by turns — they expire by charge depletion
        if buff_type in ("shield_charges", "evasion"):
            if buff.get("charges", 0) > 0:
                # Also decrement duration if the buff has one
                if buff.get("turns_remaining", 0) > 0:
                    buff["turns_remaining"] -= 1
                    if buff["turns_remaining"] <= 0:
                        expired.append(buff)
                        continue
                remaining.append(buff)
            else:
                expired.append(buff)
            continue

        # DoT: apply damage per tick
        if buff_type == "dot":
            dmg = buff.get("damage_per_tick", 0)
            if dmg > 0 and player.is_alive:
                player.hp = max(0, player.hp - dmg)
                if player.hp <= 0:
                    player.is_alive = False

        # HoT: apply healing per tick
        if buff_type == "hot":
            heal = buff.get("heal_per_tick", 0)
            if heal > 0 and player.is_alive:
                player.hp = min(player.max_hp, player.hp + heal)

        # Standard turn decrement
        buff["turns_remaining"] -= 1
        if buff["turns_remaining"] > 0:
            remaining.append(buff)
        else:
            expired.append(buff)

    player.active_buffs = remaining
    return expired


def get_melee_buff_multiplier(player: PlayerState) -> float:
    """Return the combined melee damage multiplier from active buffs.

    Phase 21C: Also checks all_damage_multiplier (Bard Ballad of Might).
    """
    mult = 1.0
    for buff in player.active_buffs:
        if buff.get("stat") == "melee_damage_multiplier":
            mult *= buff["magnitude"]
        elif buff.get("stat") == "all_damage_multiplier" and buff.get("type") == "buff":
            mult *= buff["magnitude"]
    return mult


def get_ranged_buff_multiplier(player: PlayerState) -> float:
    """Return the combined ranged damage multiplier from active buffs.

    Phase 21C: Also checks all_damage_multiplier (Bard Ballad of Might).
    """
    mult = 1.0
    for buff in player.active_buffs:
        if buff.get("stat") == "ranged_damage_multiplier":
            mult *= buff["magnitude"]
        elif buff.get("stat") == "all_damage_multiplier" and buff.get("type") == "buff":
            mult *= buff["magnitude"]
    return mult


# ---------- Phase 21C: Damage-Taken Multiplier (Bard Dirge of Weakness) ----------

def get_damage_taken_multiplier(player: PlayerState) -> float:
    """Return the combined damage-taken multiplier from all active debuffs.

    Phase 21C: Used by Dirge of Weakness (damage_taken_multiplier debuff).
    Values > 1.0 mean the target takes MORE damage.
    Multiplicative stacking if multiple sources apply.
    """
    mult = 1.0
    for buff in player.active_buffs:
        if buff.get("stat") == "damage_taken_multiplier":
            mult *= buff["magnitude"]
    return mult


# ---------- Phase 23C: Damage-Dealt Multiplier (Plague Doctor Enfeeble) ----------

def get_damage_dealt_multiplier(player: PlayerState) -> float:
    """Return the combined damage-dealt multiplier from all active debuffs.

    Phase 23C: Used by Enfeeble (damage_dealt_multiplier debuff).
    Values < 1.0 mean the unit deals LESS damage.
    Multiplicative stacking if multiple sources apply.
    """
    mult = 1.0
    for buff in player.active_buffs:
        if buff.get("stat") == "damage_dealt_multiplier":
            mult *= buff["magnitude"]
    return mult


# ---------- Phase 18I: Flat Attack Damage Bonus ----------

def get_attack_damage_buff_bonus(player: PlayerState) -> int:
    """Return the total flat attack damage bonus from active buffs (e.g. Frenzy Aura).

    Phase 18I: Imp Frenzy Aura grants +3 flat attack_damage to nearby imps.
    """
    bonus = 0
    for buff in player.active_buffs:
        if buff.get("stat") == "attack_damage":
            bonus += int(buff["magnitude"])
    return bonus


# ---------- Phase 11: Generic Stat Pipeline ----------

def get_armor_buff_bonus(player: PlayerState) -> int:
    """Return the total armor bonus from active buffs (e.g. Shield of Faith, Bulwark)."""
    bonus = 0
    for buff in player.active_buffs:
        if buff.get("stat") == "armor" and buff.get("type", "buff") == "buff":
            bonus += int(buff["magnitude"])
    return bonus


# ---------- Phase 12: CC Status Helpers ----------

def is_stunned(player: PlayerState) -> bool:
    """Check if a player has an active stun debuff."""
    return any(buff.get("type") == "stun" for buff in player.active_buffs)


def is_slowed(player: PlayerState) -> bool:
    """Check if a player has an active slow debuff (cannot move but can act)."""
    return any(buff.get("type") == "slow" for buff in player.active_buffs)


def is_rooted(player: PlayerState) -> bool:
    """Check if a player is rooted (cannot move, can still attack/use skills).

    Phase 26C: Shaman — Earthgrasp root CC type.
    """
    return any(buff.get("stat") == "rooted" for buff in player.active_buffs)


def is_taunted(player: PlayerState) -> tuple[bool, str | None]:
    """Check if a player has an active taunt debuff.

    Returns (True, source_id) if taunted, (False, None) otherwise.
    """
    for buff in player.active_buffs:
        if buff.get("type") == "taunt":
            return True, buff.get("source_id")
    return False, None


def get_evasion_effect(player: PlayerState) -> dict | None:
    """Return the active evasion buff, or None."""
    for buff in player.active_buffs:
        if buff.get("type") == "evasion" and buff.get("charges", 0) > 0:
            return buff
    return None


def trigger_evasion_dodge(defender: PlayerState) -> bool:
    """Check if defender has an active Evasion buff. If so, consume a charge and dodge.

    Returns True if the attack was dodged, False otherwise.
    """
    evasion = get_evasion_effect(defender)
    if not evasion:
        return False

    evasion["charges"] = evasion.get("charges", 0) - 1

    # Remove evasion if charges depleted
    if evasion["charges"] <= 0:
        defender.active_buffs = [b for b in defender.active_buffs if b is not evasion]

    return True


def get_damage_reduction_buff_bonus(player: PlayerState) -> float:
    """Return the total damage reduction % bonus from active buffs (e.g. Profane Ward).

    Phase 18I: Profane Ward grants +30% damage reduction via buff.
    """
    bonus = 0.0
    for buff in player.active_buffs:
        if buff.get("stat") == "damage_reduction_pct":
            bonus += float(buff["magnitude"])
    return bonus


def get_effective_armor(player: PlayerState) -> int:
    """Return the effective armor including base, equipment, and buff bonuses."""
    from app.core.combat import _get_equipment_bonuses
    equip_bonuses = _get_equipment_bonuses(player)
    return player.armor + equip_bonuses.armor + get_armor_buff_bonus(player)


# ---------- Phase 18I: Damage Absorb (Bone Shield) Helpers ----------

def get_damage_absorb_effect(player: PlayerState) -> dict | None:
    """Return the active damage_absorb buff, or None."""
    for buff in player.active_buffs:
        if buff.get("type") == "damage_absorb" and buff.get("absorb_remaining", 0) > 0:
            return buff
    return None


def consume_damage_absorb(defender: PlayerState, incoming_damage: int) -> tuple[int, int]:
    """Check if defender has an active Bone Shield / damage absorb buff.

    Absorbs incoming damage up to the absorb_remaining amount.
    Returns (damage_after_absorb, damage_absorbed).
    """
    absorb = get_damage_absorb_effect(defender)
    if not absorb:
        return incoming_damage, 0

    remaining = absorb.get("absorb_remaining", 0)
    absorbed = min(remaining, incoming_damage)
    absorb["absorb_remaining"] = remaining - absorbed
    damage_through = incoming_damage - absorbed

    # Remove absorb buff if fully depleted
    if absorb["absorb_remaining"] <= 0:
        defender.active_buffs = [b for b in defender.active_buffs if b is not absorb]

    return damage_through, absorbed


# ---------- Phase 11: Ward (Reflective Shield) Helpers ----------

def get_ward_effect(player: PlayerState) -> dict | None:
    """Return the active ward/shield_charges buff, or None."""
    for buff in player.active_buffs:
        if buff.get("type") == "shield_charges" and buff.get("charges", 0) > 0:
            return buff
    return None


def trigger_ward_reflect(defender: PlayerState, attacker: PlayerState) -> int:
    """Check if defender has an active Ward. If so, consume a charge and reflect damage.

    Returns the reflected damage dealt to the attacker (0 if no ward).
    """
    ward = get_ward_effect(defender)
    if not ward:
        return 0

    reflect_damage = ward.get("reflect_damage", 0)
    ward["charges"] = ward.get("charges", 0) - 1

    # Remove ward if charges depleted
    if ward["charges"] <= 0:
        defender.active_buffs = [b for b in defender.active_buffs if b is not ward]

    # Apply reflected damage to attacker
    if reflect_damage > 0 and attacker.is_alive:
        attacker.hp = max(0, attacker.hp - reflect_damage)
        if attacker.hp <= 0:
            attacker.is_alive = False

    return reflect_damage


def resolve_skill_action(
    player: PlayerState,
    action,
    skill_def: dict,
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    grid_width: int = 0,
    grid_height: int = 0,
    match_state=None,
) -> ActionResult:
    """Central dispatcher — routes a skill action to the correct effect handler.

    Reads the first effect's ``type`` field from the skill definition and
    delegates to the matching ``resolve_*`` handler in the skill_effects
    sub-package.
    """
    effect_type = skill_def["effects"][0]["type"]
    target_x = getattr(action, "target_x", None)
    target_y = getattr(action, "target_y", None)
    target_id = getattr(action, "target_id", None)
    skill_id = skill_def["skill_id"]

    # --- Healing ---
    if effect_type == "heal":
        return resolve_heal(player, target_x, target_y, skill_def, players, target_id=target_id)
    elif effect_type == "hot":
        return resolve_hot(player, target_x, target_y, skill_def, players, target_id=target_id)
    elif effect_type == "aoe_heal":
        return resolve_aoe_heal(player, skill_def, players)

    # --- Melee / Ranged / Damage ---
    elif effect_type == "melee_damage":
        return resolve_multi_hit(player, target_x, target_y, skill_def, players, obstacles, target_id=target_id)
    elif effect_type == "ranged_damage":
        return resolve_ranged_skill(player, target_x, target_y, skill_def, players, obstacles, target_id=target_id)
    elif effect_type == "holy_damage":
        return resolve_holy_damage(player, target_x, target_y, skill_def, players, obstacles, target_id=target_id)
    elif effect_type == "stun_damage":
        return resolve_stun_damage(player, target_x, target_y, skill_def, players, obstacles, target_id=target_id)
    elif effect_type == "magic_damage":
        return resolve_magic_damage(player, target_x, target_y, skill_def, players, obstacles, target_id=target_id)
    elif effect_type == "aoe_damage":
        return resolve_aoe_damage(player, target_x, target_y, skill_def, players, obstacles)
    elif effect_type == "aoe_magic_damage":
        return resolve_aoe_magic_damage(player, target_x, target_y, skill_def, players, obstacles)
    elif effect_type == "ranged_damage_slow":
        return resolve_ranged_damage_slow(player, target_x, target_y, skill_def, players, obstacles, target_id=target_id)
    elif effect_type == "aoe_damage_slow":
        return resolve_aoe_damage_slow(player, skill_def, players, obstacles)
    elif effect_type == "lifesteal_damage":
        return resolve_lifesteal_damage(player, target_x, target_y, skill_def, players, obstacles, target_id=target_id)
    elif effect_type == "lifesteal_aoe":
        return resolve_lifesteal_aoe(player, skill_def, players, obstacles)
    elif effect_type == "aoe_damage_slow_targeted":
        return resolve_aoe_damage_slow_targeted(player, target_x, target_y, skill_def, players, obstacles)
    elif effect_type == "melee_damage_slow":
        return resolve_melee_damage_slow(player, target_x, target_y, skill_def, players, obstacles, target_id=target_id)

    # --- Buffs ---
    elif effect_type == "buff":
        return resolve_buff(player, skill_def, target_x=target_x, target_y=target_y, players=players, target_id=target_id)
    elif effect_type == "aoe_buff":
        return resolve_aoe_buff(player, skill_def, players)
    elif effect_type == "damage_absorb":
        return resolve_damage_absorb(player, skill_def)
    elif effect_type == "shield_charges":
        return resolve_shield_charges(player, skill_def)
    elif effect_type == "evasion":
        return resolve_evasion(player, skill_def)
    elif effect_type == "conditional_buff":
        return resolve_conditional_buff(player, skill_def)
    elif effect_type == "thorns_buff":
        return resolve_thorns_buff(player, skill_def)
    elif effect_type == "cheat_death":
        return resolve_cheat_death(player, skill_def)
    elif effect_type == "buff_cleanse":
        return resolve_buff_cleanse(player, skill_def, target_x=target_x, target_y=target_y, players=players, target_id=target_id)

    # --- Debuffs / CC ---
    elif effect_type == "dot":
        return resolve_dot(player, target_x, target_y, skill_def, players, obstacles, target_id=target_id)
    elif effect_type == "taunt":
        return resolve_taunt(player, skill_def, players)
    elif effect_type == "aoe_debuff":
        return resolve_aoe_debuff(player, target_x, target_y, skill_def, players, obstacles)
    elif effect_type == "targeted_debuff":
        return resolve_targeted_debuff(player, target_x, target_y, skill_def, players, obstacles, target_id=target_id)
    elif effect_type == "ranged_taunt":
        return resolve_ranged_taunt(player, target_x, target_y, skill_def, players, obstacles, target_id=target_id)
    elif effect_type == "aoe_root":
        return resolve_aoe_root(player, action, skill_def, players, obstacles)

    # --- Movement ---
    elif effect_type == "teleport":
        return resolve_teleport(player, target_x, target_y, skill_def, players, obstacles, grid_width, grid_height)

    # --- Detection ---
    elif effect_type == "detection":
        return resolve_detection(player, skill_def, players)

    # --- Cooldown Reduction ---
    elif effect_type == "cooldown_reduction":
        return resolve_cooldown_reduction(player, skill_def, players, target_x=target_x, target_y=target_y, target_id=target_id)

    # --- Summon / Totem ---
    elif effect_type == "place_totem":
        return resolve_place_totem(player, action, skill_def, players, obstacles, match_state=match_state)
    elif effect_type == "soul_anchor":
        return resolve_soul_anchor(player, action, skill_def, players, target_id=target_id)

    # --- Passive (no active use) ---
    elif effect_type in ("passive_aura_ally_buff", "passive_enrage"):
        return ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.SKILL,
            skill_id=skill_id,
            success=False,
            message=f"{player.username} skill '{skill_def['name']}' is passive and cannot be actively used",
        )

    # --- Unknown effect type ---
    else:
        return ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.SKILL,
            skill_id=skill_id,
            success=False,
            message=f"{player.username} skill '{skill_def['name']}' has unknown effect type: {effect_type}",
        )


# ---------- Backward-compatible re-exports from skill_effects sub-modules ----------
# These allow existing imports like rom app.core.skills import resolve_heal to keep working.
from app.core.skill_effects._helpers import (  # noqa: E402, F401
    _apply_skill_cooldown,
    _resolve_skill_entity_target,
)
from app.core.skill_effects.heal import (  # noqa: E402, F401
    resolve_aoe_heal,
    resolve_heal,
    resolve_hot,
)
from app.core.skill_effects.damage import (  # noqa: E402, F401
    resolve_aoe_damage,
    resolve_aoe_damage_slow,
    resolve_aoe_damage_slow_targeted,
    resolve_aoe_magic_damage,
    resolve_holy_damage,
    resolve_lifesteal_aoe,
    resolve_lifesteal_damage,
    resolve_magic_damage,
    resolve_melee_damage_slow,
    resolve_multi_hit,
    resolve_ranged_damage_slow,
    resolve_ranged_skill,
    resolve_stun_damage,
)
from app.core.skill_effects.buff import (  # noqa: E402, F401
    resolve_aoe_buff,
    resolve_buff,
    resolve_buff_cleanse,
    resolve_cheat_death,
    resolve_conditional_buff,
    resolve_damage_absorb,
    resolve_evasion,
    resolve_shield_charges,
    resolve_thorns_buff,
)
from app.core.skill_effects.debuff import (  # noqa: E402, F401
    resolve_aoe_debuff,
    resolve_aoe_root,
    resolve_dot,
    resolve_ranged_taunt,
    resolve_targeted_debuff,
    resolve_taunt,
)
from app.core.skill_effects.movement import resolve_teleport  # noqa: E402, F401
from app.core.skill_effects.summon import (  # noqa: E402, F401
    resolve_place_totem,
    resolve_soul_anchor,
)
from app.core.skill_effects.utility import (  # noqa: E402, F401
    resolve_cooldown_reduction,
    resolve_detection,
)

