"""Skill effect handler sub-modules.

All resolve_* functions are re-exported here for convenience.
Canonical import path: ``from app.core.skill_effects import resolve_heal``
Backward-compat path:  ``from app.core.skills import resolve_heal``
"""
from app.core.skill_effects._helpers import (
    _apply_skill_cooldown,
    _resolve_skill_entity_target,
)
from app.core.skill_effects.heal import (
    resolve_aoe_heal,
    resolve_heal,
    resolve_hot,
)
from app.core.skill_effects.damage import (
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
from app.core.skill_effects.buff import (
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
from app.core.skill_effects.debuff import (
    resolve_aoe_debuff,
    resolve_aoe_root,
    resolve_dot,
    resolve_ranged_taunt,
    resolve_targeted_debuff,
    resolve_taunt,
)
from app.core.skill_effects.movement import resolve_teleport
from app.core.skill_effects.summon import resolve_place_totem, resolve_soul_anchor
from app.core.skill_effects.utility import resolve_cooldown_reduction, resolve_detection

__all__ = [
    # helpers
    "_apply_skill_cooldown",
    "_resolve_skill_entity_target",
    # heal
    "resolve_heal",
    "resolve_hot",
    "resolve_aoe_heal",
    # damage
    "resolve_multi_hit",
    "resolve_ranged_skill",
    "resolve_holy_damage",
    "resolve_stun_damage",
    "resolve_aoe_damage",
    "resolve_aoe_magic_damage",
    "resolve_ranged_damage_slow",
    "resolve_magic_damage",
    "resolve_aoe_damage_slow",
    "resolve_lifesteal_damage",
    "resolve_lifesteal_aoe",
    "resolve_aoe_damage_slow_targeted",
    "resolve_melee_damage_slow",
    # buff
    "resolve_buff",
    "resolve_aoe_buff",
    "resolve_damage_absorb",
    "resolve_shield_charges",
    "resolve_evasion",
    "resolve_conditional_buff",
    "resolve_thorns_buff",
    "resolve_cheat_death",
    "resolve_buff_cleanse",
    # debuff
    "resolve_dot",
    "resolve_taunt",
    "resolve_aoe_debuff",
    "resolve_targeted_debuff",
    "resolve_ranged_taunt",
    "resolve_aoe_root",
    # movement
    "resolve_teleport",
    # summon
    "resolve_place_totem",
    "resolve_soul_anchor",
    # utility
    "resolve_detection",
    "resolve_cooldown_reduction",
]
