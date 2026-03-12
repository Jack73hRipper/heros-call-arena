"""
Auras Phase — Phase 18D: Monster rarity aura effects.
Phase 18I: Skill-based passive auras (Enrage, Frenzy Aura).

Auras apply at the start of each turn tick before combat:
- Might Aura: allies within radius get +25% damage (1-turn refreshing buff)
- Conviction Aura: enemies within radius lose armor (1-turn refreshing debuff)
- Berserker enrage: champions below 30% HP get +50% damage buff
- Demon enrage (18I): demons below 30% HP get permanent +50% damage buff
- Frenzy Aura (18I): imps buff nearby imps with +3 attack damage
"""

from __future__ import annotations

from app.models.player import PlayerState
from app.models.actions import ActionType, ActionResult


def _resolve_auras(
    players: dict[str, PlayerState],
    results: list[ActionResult],
) -> None:
    """Phase 18D — Resolve monster rarity aura effects.
    Phase 18I — Resolve skill-based passive auras (Enrage, Frenzy Aura).

    Auras apply at the start of each turn tick before combat:
    - Might Aura: allies within radius get +25% damage (1-turn refreshing buff)
    - Conviction Aura: enemies within radius lose armor (1-turn refreshing debuff)
    - Berserker enrage: champions below 30% HP get +50% damage buff
    - Demon enrage (18I): demons below 30% HP get permanent +50% damage buff
    - Frenzy Aura (18I): imps buff nearby imps with +3 attack damage

    Aura buffs have is_aura=True to prevent stacking display and are
    refreshed each tick (1-turn duration).
    """
    from app.core.monster_rarity import get_affix, get_champion_type
    from app.core.skills import get_skill

    # First: remove all expired aura buffs from previous tick
    # Note: demon_enrage is permanent (not is_aura), so it survives this cleanup
    for p in players.values():
        if p.active_buffs:
            p.active_buffs = [
                b for b in p.active_buffs
                if not b.get("is_aura")
            ]

    for uid, unit in players.items():
        if not unit.is_alive:
            continue

        unit_pos = (unit.position.x, unit.position.y)

        # --- Berserker enrage check (champion type) ---
        if unit.champion_type == "berserker" and unit.max_hp > 0:
            ct_config = get_champion_type("berserker")
            if ct_config:
                threshold = ct_config.get("enrage_threshold", 0.30)
                enrage_bonus = ct_config.get("enrage_damage_bonus", 0.50)
                if (unit.hp / unit.max_hp) <= threshold:
                    # Apply enrage buff
                    enrage_buff = {
                        "buff_id": "berserker_enrage",
                        "stat": "melee_damage_multiplier",
                        "magnitude": 1.0 + enrage_bonus,
                        "turns_remaining": 1,
                        "is_aura": True,
                        "source": uid,
                    }
                    unit.active_buffs.append(enrage_buff)
                    results.append(ActionResult(
                        player_id=uid,
                        username=unit.username,
                        action_type=ActionType.SKILL,
                        skill_id="berserker_enrage",
                        success=True,
                        message=f"{unit.username} is ENRAGED! (+{int(enrage_bonus * 100)}% damage)",
                        target_id=uid,
                        target_username=unit.username,
                        is_tick=True,
                    ))

        # --- Phase 18I: Demon Enrage (passive skill) ---
        # Permanent buff — check if unit has the enrage passive and is below threshold
        if unit.class_id == "demon_enrage" and unit.max_hp > 0:
            # Check if already has the permanent enrage buff
            has_enrage = any(b.get("buff_id") == "demon_enrage" for b in unit.active_buffs)
            if not has_enrage:
                enrage_skill = get_skill("enrage")
                if enrage_skill:
                    effect = enrage_skill["effects"][0]
                    threshold = effect.get("hp_threshold", 0.30)
                    damage_multiplier = effect.get("damage_multiplier", 1.5)
                    if (unit.hp / unit.max_hp) <= threshold:
                        # Apply permanent enrage buff (very long duration, NOT is_aura so it persists)
                        enrage_buff = {
                            "buff_id": "demon_enrage",
                            "stat": "melee_damage_multiplier",
                            "magnitude": damage_multiplier,
                            "turns_remaining": 999,
                            "source": uid,
                        }
                        unit.active_buffs.append(enrage_buff)
                        results.append(ActionResult(
                            player_id=uid,
                            username=unit.username,
                            action_type=ActionType.SKILL,
                            skill_id="enrage",
                            success=True,
                            message=f"{unit.username} flies into a rage! +{int((damage_multiplier - 1.0) * 100)}% melee damage!",
                            target_id=uid,
                            target_username=unit.username,
                            is_tick=True,
                        ))

        # --- Phase 18I: Frenzy Aura (imp passive skill) ---
        if unit.class_id == "imp_frenzy":
            frenzy_skill = get_skill("frenzy_aura")
            if frenzy_skill:
                effect = frenzy_skill["effects"][0]
                radius = effect.get("radius", 2)
                value = effect.get("value", 3)
                requires_tag = effect.get("requires_tag", "imp")
                for other_id, other in players.items():
                    if other_id == uid or not other.is_alive:
                        continue
                    if other.team != unit.team:
                        continue
                    # Tag filter: only buff units with matching tag
                    if requires_tag and requires_tag not in getattr(other, 'tags', []):
                        continue
                    dist = max(
                        abs(other.position.x - unit.position.x),
                        abs(other.position.y - unit.position.y),
                    )
                    if dist <= radius:
                        frenzy_buff = {
                            "buff_id": f"frenzy_aura_{uid}",
                            "stat": "attack_damage",
                            "magnitude": value,
                            "turns_remaining": 1,
                            "is_aura": True,
                            "source": uid,
                        }
                        other.active_buffs.append(frenzy_buff)

        # --- Process affix auras ---
        if not unit.affixes:
            continue

        for affix_id in unit.affixes:
            affix_data = get_affix(affix_id)
            if not affix_data or not affix_data.get("is_aura"):
                continue

            for effect in affix_data.get("effects", []):
                effect_type = effect.get("type", "")
                radius = effect.get("radius", 2)

                if effect_type == "aura_ally_buff":
                    # Might Aura: buff allies within radius
                    stat = effect.get("stat", "attack_damage")
                    multiplier = effect.get("multiplier", 1.25)
                    for other_id, other in players.items():
                        if other_id == uid or not other.is_alive:
                            continue
                        if other.team != unit.team:
                            continue
                        dist = max(
                            abs(other.position.x - unit.position.x),
                            abs(other.position.y - unit.position.y),
                        )
                        if dist <= radius:
                            aura_buff = {
                                "buff_id": f"aura_{affix_id}_{uid}",
                                "stat": "melee_damage_multiplier",
                                "magnitude": multiplier,
                                "turns_remaining": 1,
                                "is_aura": True,
                                "source": uid,
                            }
                            other.active_buffs.append(aura_buff)

                elif effect_type == "aura_enemy_debuff":
                    # Conviction Aura: debuff enemies within radius
                    stat = effect.get("stat", "armor")
                    value = effect.get("value", -3)
                    for other_id, other in players.items():
                        if other_id == uid or not other.is_alive:
                            continue
                        if other.team == unit.team:
                            continue  # Skip allies
                        dist = max(
                            abs(other.position.x - unit.position.x),
                            abs(other.position.y - unit.position.y),
                        )
                        if dist <= radius:
                            aura_debuff = {
                                "buff_id": f"aura_{affix_id}_{uid}",
                                "stat": stat,
                                "magnitude": value,  # Negative for debuff
                                "turns_remaining": 1,
                                "is_aura": True,
                                "source": uid,
                            }
                            other.active_buffs.append(aura_debuff)
                            # Apply the armor reduction immediately this tick
                            if stat == "armor":
                                other.armor = max(0, other.armor + value)
