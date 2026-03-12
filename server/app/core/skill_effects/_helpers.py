"""Shared helpers for skill effect handlers."""
from __future__ import annotations

from app.models.player import PlayerState


def _apply_skill_cooldown(player: PlayerState, skill_def: dict, dealt_damage: bool = False) -> None:
    """Set the skill's cooldown on the player.

    Phase 16A: Cooldown Reduction (CDR) reduces the effective cooldown.
    Phase 16D: Unique items can grant additional CDR for specific skills
               (Dawnbreaker → exorcism/rebuke, Shadowshroud → shadow_step).
               Eye of Malice: If a damage skill crits, cooldown resets to 0.
    Phase 16E: Set bonuses can grant additional CDR for specific skills.
    Minimum cooldown is always 1 turn.
    """
    import random
    base_cooldown = skill_def["cooldown_turns"]
    cdr = getattr(player, 'cooldown_reduction_pct', 0.0)
    if cdr > 0:
        reduced = max(1, round(base_cooldown * (1.0 - cdr)))
    else:
        reduced = base_cooldown

    # Phase 16D: Unique skill-specific CDR
    from app.core.item_generator import get_all_equipped_unique_effects
    skill_id = skill_def["skill_id"]
    unique_effects = get_all_equipped_unique_effects(player.equipment)

    for effect in unique_effects:
        if effect.get("type") == "skill_cooldown_reduction":
            if skill_id in effect.get("skills", []):
                reduced = max(1, reduced - effect.get("value", 0))

    # Phase 16E: Set bonus skill-specific CDR
    from app.core.set_bonuses import get_set_skill_modifiers
    set_modifiers = get_set_skill_modifiers(player.active_set_bonuses)
    if skill_id in set_modifiers:
        set_cdr = set_modifiers[skill_id].get("cooldown_reduction", 0)
        if set_cdr > 0:
            reduced = max(1, reduced - set_cdr)

    # Phase 16D: Eye of Malice — crit skill cooldown reset
    if dealt_damage:
        for effect in unique_effects:
            if effect.get("type") == "crit_skill_reset_cooldown":
                crit_chance = getattr(player, 'crit_chance', 0.0)
                if random.random() < crit_chance:
                    reduced = 0
                    break

    player.cooldowns[skill_def["skill_id"]] = reduced


def _resolve_skill_entity_target(
    player: PlayerState,
    target_id: str | None,
    target_x: int | None,
    target_y: int | None,
    players: dict[str, PlayerState],
    ally_target: bool = False,
) -> PlayerState | None:
    """Look up a skill target using entity ID (preferred) or tile coords (fallback).

    For enemy skills: returns an alive enemy (different team).
    For ally skills (ally_target=True): returns an alive ally (same team or self).
    """
    # --- Entity-based lookup (preferred) ---
    if target_id:
        candidate = players.get(target_id)
        if candidate and candidate.is_alive:
            if ally_target:
                if candidate.team == player.team or candidate.player_id == player.player_id:
                    return candidate
            else:
                if candidate.team != player.team:
                    return candidate
        return None

    # --- Tile-based fallback ---
    if target_x is None or target_y is None:
        return None
    for p in players.values():
        if p.is_alive and p.position.x == target_x and p.position.y == target_y:
            if ally_target:
                if p.team == player.team or p.player_id == player.player_id:
                    return p
            else:
                if p.team != player.team:
                    return p
            break
    return None
