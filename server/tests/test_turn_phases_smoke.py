"""
Smoke tests for the turn_phases sub-package (Phase 20, Phase 2 validation).

Verifies that every sub-module in turn_phases/ loads without import errors and
that all 17 public symbols are accessible both from the barrel (__init__) and
from each individual sub-module.
"""

import importlib
import pytest


# ── Sub-module import tests ──────────────────────────────────────────────────

SUB_MODULES = [
    "app.core.turn_phases.helpers",
    "app.core.turn_phases.items_phase",
    "app.core.turn_phases.portal_phase",
    "app.core.turn_phases.buffs_phase",
    "app.core.turn_phases.auras_phase",
    "app.core.turn_phases.movement_phase",
    "app.core.turn_phases.interaction_phase",
    "app.core.turn_phases.skills_phase",
    "app.core.turn_phases.combat_phase",
    "app.core.turn_phases.deaths_phase",
]


@pytest.mark.parametrize("module_path", SUB_MODULES)
def test_submodule_imports_cleanly(module_path):
    """Each turn_phases sub-module should import without errors."""
    mod = importlib.import_module(module_path)
    assert mod is not None


def test_barrel_imports_cleanly():
    """The turn_phases barrel (__init__) should import without errors."""
    import app.core.turn_phases as tp
    assert tp is not None


# ── Symbol availability via barrel ───────────────────────────────────────────

EXPECTED_BARREL_SYMBOLS = [
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


@pytest.mark.parametrize("symbol_name", EXPECTED_BARREL_SYMBOLS)
def test_barrel_exports_symbol(symbol_name):
    """Every expected symbol should be accessible from the barrel package."""
    import app.core.turn_phases as tp
    assert hasattr(tp, symbol_name), f"Missing barrel export: {symbol_name}"
    obj = getattr(tp, symbol_name)
    assert obj is not None


# ── Symbol availability via direct sub-module imports ────────────────────────

DIRECT_IMPORTS = [
    ("app.core.turn_phases.helpers", "_is_cardinal_adjacent"),
    ("app.core.turn_phases.helpers", "_is_chebyshev_adjacent"),
    ("app.core.turn_phases.items_phase", "_resolve_items"),
    ("app.core.turn_phases.portal_phase", "PORTAL_CHANNEL_TURNS"),
    ("app.core.turn_phases.portal_phase", "PORTAL_DURATION_TURNS"),
    ("app.core.turn_phases.portal_phase", "_resolve_channeling"),
    ("app.core.turn_phases.portal_phase", "_resolve_portal_tick"),
    ("app.core.turn_phases.portal_phase", "_resolve_extractions"),
    ("app.core.turn_phases.portal_phase", "_resolve_stairs"),
    ("app.core.turn_phases.portal_phase", "_is_channeling"),
    ("app.core.turn_phases.buffs_phase", "_resolve_cooldowns_and_buffs"),
    ("app.core.turn_phases.auras_phase", "_resolve_auras"),
    ("app.core.turn_phases.movement_phase", "_resolve_movement"),
    ("app.core.turn_phases.interaction_phase", "_resolve_doors"),
    ("app.core.turn_phases.interaction_phase", "_resolve_loot"),
    ("app.core.turn_phases.skills_phase", "_resolve_skills"),
    ("app.core.turn_phases.combat_phase", "_resolve_entity_target"),
    ("app.core.turn_phases.combat_phase", "_resolve_ranged"),
    ("app.core.turn_phases.combat_phase", "_resolve_melee"),
    ("app.core.turn_phases.deaths_phase", "_resolve_deaths"),
    ("app.core.turn_phases.deaths_phase", "_resolve_victory"),
]


@pytest.mark.parametrize("module_path,symbol_name", DIRECT_IMPORTS)
def test_direct_submodule_symbol(module_path, symbol_name):
    """Every symbol should be importable directly from its home sub-module."""
    mod = importlib.import_module(module_path)
    assert hasattr(mod, symbol_name), f"{module_path} missing: {symbol_name}"
    obj = getattr(mod, symbol_name)
    assert obj is not None


# ── Callable checks (functions vs constants) ─────────────────────────────────

def test_helpers_are_callable():
    from app.core.turn_phases.helpers import _is_cardinal_adjacent, _is_chebyshev_adjacent
    assert callable(_is_cardinal_adjacent)
    assert callable(_is_chebyshev_adjacent)


def test_portal_constants_are_integers():
    from app.core.turn_phases.portal_phase import PORTAL_CHANNEL_TURNS, PORTAL_DURATION_TURNS
    assert isinstance(PORTAL_CHANNEL_TURNS, int)
    assert isinstance(PORTAL_DURATION_TURNS, int)


def test_all_phase_functions_are_callable():
    """Every _resolve_* function should be callable."""
    import app.core.turn_phases as tp
    resolve_funcs = [
        tp._resolve_items,
        tp._resolve_channeling,
        tp._resolve_portal_tick,
        tp._resolve_extractions,
        tp._resolve_stairs,
        tp._resolve_cooldowns_and_buffs,
        tp._resolve_auras,
        tp._resolve_movement,
        tp._resolve_doors,
        tp._resolve_loot,
        tp._resolve_skills,
        tp._resolve_entity_target,
        tp._resolve_ranged,
        tp._resolve_melee,
        tp._resolve_deaths,
        tp._resolve_victory,
        tp._is_channeling,
    ]
    for fn in resolve_funcs:
        assert callable(fn), f"{fn} is not callable"


# ── Backward-compat: old turn_resolver.py still exports resolve_turn ─────────

def test_old_turn_resolver_still_exports_resolve_turn():
    """The original turn_resolver.py must continue to export resolve_turn."""
    from app.core.turn_resolver import resolve_turn
    assert callable(resolve_turn)


def test_old_turn_resolver_still_exports_private_helpers():
    """Test files import private helpers from turn_resolver — must still work."""
    from app.core.turn_resolver import _is_cardinal_adjacent, _is_chebyshev_adjacent
    assert callable(_is_cardinal_adjacent)
    assert callable(_is_chebyshev_adjacent)


def test_old_turn_resolver_still_exports_portal_constants():
    """test_portal_scroll.py imports constants from turn_resolver — must still work."""
    from app.core.turn_resolver import PORTAL_CHANNEL_TURNS, PORTAL_DURATION_TURNS
    assert isinstance(PORTAL_CHANNEL_TURNS, int)
    assert isinstance(PORTAL_DURATION_TURNS, int)


def test_old_turn_resolver_still_exports_resolve_auras():
    """test_monster_rarity_combat.py imports _resolve_auras from turn_resolver."""
    from app.core.turn_resolver import _resolve_auras
    assert callable(_resolve_auras)


def test_old_turn_resolver_still_exports_resolve_deaths():
    """test_loot_rarity.py and test_monster_rarity_combat.py import _resolve_deaths."""
    from app.core.turn_resolver import _resolve_deaths
    assert callable(_resolve_deaths)
