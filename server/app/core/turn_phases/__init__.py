"""
turn_phases — Sub-package barrel exports for the turn resolution pipeline.

All public symbols are re-exported here for convenience. Production code and
tests can import directly from the sub-modules or from this package.
"""

from app.core.turn_phases.helpers import (
    _is_cardinal_adjacent,
    _is_chebyshev_adjacent,
)

from app.core.turn_phases.items_phase import _resolve_items

from app.core.turn_phases.portal_phase import (
    PORTAL_CHANNEL_TURNS,
    PORTAL_DURATION_TURNS,
    _resolve_channeling,
    _resolve_portal_tick,
    _resolve_extractions,
    _resolve_stairs,
    _is_channeling,
)

from app.core.turn_phases.buffs_phase import _resolve_cooldowns_and_buffs

from app.core.turn_phases.auras_phase import _resolve_auras

from app.core.turn_phases.movement_phase import _resolve_movement

from app.core.turn_phases.interaction_phase import _resolve_doors, _resolve_loot

from app.core.turn_phases.skills_phase import _resolve_skills

from app.core.turn_phases.combat_phase import (
    _resolve_entity_target,
    _resolve_ranged,
    _resolve_melee,
)

from app.core.turn_phases.deaths_phase import _resolve_deaths, _resolve_victory

__all__ = [
    # helpers
    "_is_cardinal_adjacent",
    "_is_chebyshev_adjacent",
    # items
    "_resolve_items",
    # portal
    "PORTAL_CHANNEL_TURNS",
    "PORTAL_DURATION_TURNS",
    "_resolve_channeling",
    "_resolve_portal_tick",
    "_resolve_extractions",
    "_resolve_stairs",
    "_is_channeling",
    # buffs
    "_resolve_cooldowns_and_buffs",
    # auras
    "_resolve_auras",
    # movement
    "_resolve_movement",
    # interaction
    "_resolve_doors",
    "_resolve_loot",
    # skills
    "_resolve_skills",
    # combat
    "_resolve_entity_target",
    "_resolve_ranged",
    "_resolve_melee",
    # deaths
    "_resolve_deaths",
    "_resolve_victory",
]
