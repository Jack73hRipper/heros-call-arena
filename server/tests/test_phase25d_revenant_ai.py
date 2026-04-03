"""
Tests for Phase 25D: Revenant AI Behavior (retaliation_tank role).

Covers:
- Role mapping: revenant maps to "retaliation_tank"
- _retaliation_tank_skill_logic() — full priority chain (Phase 25R rework)
  - Undying Fury: uses when HP < 35% and no undying_fury/fury_state buff, skips otherwise
  - Soul Rend: uses on adjacent enemy (empowered below 50% HP: 1.8× + bleed)
  - Death's Embrace: thorns + armor + heal-on-hit aura when enemies within 2 tiles
  - Grasp of the Grave: roots ranged/kiting enemy within 4 tiles (not adjacent)
  - Fallback: returns None when all skills on cooldown
- _decide_skill_usage() dispatches revenant to retaliation_tank handler
- Priority ordering: Undying Fury > Soul Rend > Death's Embrace > Grasp of the Grave
- Smart targeting: prefers squishier/ranged classes for Grasp of the Grave
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import ActionType, PlayerAction
from app.core.ai_skills import (
    _CLASS_ROLE_MAP,
    _get_role_for_class,
    _try_skill,
    _retaliation_tank_skill_logic,
    _decide_skill_usage,
)
from app.core.combat import load_combat_config
from app.core.skills import load_skills_config, clear_skills_cache


# ---------- Setup ----------

def setup_module():
    """Ensure configs are loaded before any test runs."""
    load_combat_config()
    load_skills_config()


@pytest.fixture(autouse=True)
def _reset_skills_cache():
    """Clear cached config before each test to ensure isolation."""
    clear_skills_cache()
    load_skills_config()
    yield
    clear_skills_cache()


# ---------- Helpers ----------

def _make_revenant(
    player_id: str = "rev1",
    x: int = 5,
    y: int = 5,
    hp: int = 130,
    max_hp: int = 130,
    team: str = "team_1",
    cooldowns: dict | None = None,
    active_buffs: list | None = None,
) -> PlayerState:
    """Create a Revenant AI unit."""
    return PlayerState(
        player_id=player_id,
        username="Revenant",
        position=Position(x=x, y=y),
        class_id="revenant",
        hp=hp,
        max_hp=max_hp,
        is_alive=True,
        team=team,
        unit_type="ai",
        hero_id="rev_hero_001",
        ai_stance="follow",
        ranged_range=0,
        vision_range=5,
        attack_damage=14,
        armor=5,
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
        inventory=[],
    )


def _make_enemy(
    player_id: str = "enemy1",
    x: int = 6,
    y: int = 5,
    hp: int = 80,
    max_hp: int = 80,
    team: str = "team_2",
    class_id: str | None = None,
    ranged_range: int = 0,
    active_buffs: list | None = None,
) -> PlayerState:
    """Create an enemy unit on the opposing team."""
    return PlayerState(
        player_id=player_id,
        username="Enemy",
        position=Position(x=x, y=y),
        class_id=class_id,
        hp=hp,
        max_hp=max_hp,
        is_alive=True,
        team=team,
        unit_type="ai",
        hero_id=None,
        ranged_range=ranged_range,
        vision_range=5,
        attack_damage=10,
        armor=4,
        cooldowns={},
        active_buffs=active_buffs or [],
        inventory=[],
    )


def _build_units(*units: PlayerState) -> dict[str, PlayerState]:
    """Build the all_units dict from a list of PlayerState objects."""
    return {u.player_id: u for u in units}


# Default grid/obstacles for most tests
GRID_W = 20
GRID_H = 20
NO_OBSTACLES: set[tuple[int, int]] = set()


# ===========================================================================
# 1. Role Mapping Tests
# ===========================================================================

class TestRevenantRoleMapping:
    """Revenant class maps to retaliation_tank role."""

    def test_revenant_maps_to_retaliation_tank(self):
        """revenant → retaliation_tank in _CLASS_ROLE_MAP."""
        assert _get_role_for_class("revenant") == "retaliation_tank"

    def test_retaliation_tank_in_role_map(self):
        """_CLASS_ROLE_MAP contains revenant entry."""
        assert "revenant" in _CLASS_ROLE_MAP
        assert _CLASS_ROLE_MAP["revenant"] == "retaliation_tank"

    def test_role_map_count_updated(self):
        """_CLASS_ROLE_MAP has correct entry count (30 = 29 previous + revenant)."""
        assert len(_CLASS_ROLE_MAP) == 31


# ===========================================================================
# 2. Undying Will — Cheat Death When Low HP
# ===========================================================================

class TestUndyingFuryAI:
    """Revenant AI casts Undying Fury when HP < 35% and no undying_fury/fury_state buff."""

    def test_uses_undying_fury_when_low_hp(self):
        """Undying Fury fires when HP is below 35% threshold and no buff active."""
        rev = _make_revenant(hp=44, max_hp=130)  # ~33.8% HP — below 35%
        enemy = _make_enemy(x=6, y=5)  # adjacent
        all_units = _build_units(rev, enemy)

        result = _retaliation_tank_skill_logic(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "undying_fury"

    def test_skips_undying_fury_when_hp_above_threshold(self):
        """Undying Fury does NOT fire when HP >= 35%."""
        rev = _make_revenant(hp=60, max_hp=130)  # ~46% HP — above threshold
        enemy = _make_enemy(x=6, y=5)
        all_units = _build_units(rev, enemy)

        result = _retaliation_tank_skill_logic(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should NOT be undying_fury
        if result is not None:
            assert result.skill_id != "undying_fury"

    def test_skips_undying_fury_when_buff_already_active(self):
        """Undying Fury does NOT fire when undying_fury/cheat_death buff is already active."""
        rev = _make_revenant(
            hp=40, max_hp=130,  # ~31% HP — below threshold
            active_buffs=[{"type": "undying_fury", "stat": "cheat_death", "revive_hp_pct": 0.25, "duration_turns": 4}],
        )
        enemy = _make_enemy(x=6, y=5)
        all_units = _build_units(rev, enemy)

        result = _retaliation_tank_skill_logic(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should NOT be undying_fury — buff already active
        if result is not None:
            assert result.skill_id != "undying_fury"

    def test_skips_undying_fury_on_cooldown(self):
        """Undying Fury on cooldown → skipped even at low HP."""
        rev = _make_revenant(hp=40, max_hp=130, cooldowns={"undying_fury": 12})
        enemy = _make_enemy(x=6, y=5)
        all_units = _build_units(rev, enemy)

        result = _retaliation_tank_skill_logic(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "undying_fury"

    def test_undying_fury_prioritized_over_other_skills(self):
        """Undying Fury takes priority over Soul Rend, Death's Embrace, and Grasp of the Grave."""
        rev = _make_revenant(hp=40, max_hp=130)  # ~31% HP — all skills available
        enemy1 = _make_enemy(player_id="enemy1", x=6, y=5)  # adjacent
        enemy2 = _make_enemy(player_id="enemy2", x=5, y=6)  # adjacent
        all_units = _build_units(rev, enemy1, enemy2)

        result = _retaliation_tank_skill_logic(
            rev, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "undying_fury"


# ===========================================================================
# 3. Grave Thorns — Self-Buff When Surrounded
# ===========================================================================

class TestDeathsEmbraceAI:
    """Revenant AI casts Death's Embrace when enemies nearby and no embrace buff active."""

    def test_uses_deaths_embrace_when_two_enemies_nearby(self):
        """Death's Embrace fires when 2+ enemies within 2 tiles, soul_rend on CD, and no embrace buff."""
        rev = _make_revenant(hp=130, max_hp=130, cooldowns={"undying_fury": 12, "soul_rend": 3})
        enemy1 = _make_enemy(player_id="enemy1", x=6, y=5)  # adjacent (dist 1)
        enemy2 = _make_enemy(player_id="enemy2", x=5, y=6)  # adjacent (dist 1)
        all_units = _build_units(rev, enemy1, enemy2)

        result = _retaliation_tank_skill_logic(
            rev, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "deaths_embrace"

    def test_uses_deaths_embrace_with_one_enemy_nearby(self):
        """Death's Embrace fires even with only 1 enemy within 2 tiles (soul_rend on CD)."""
        rev = _make_revenant(hp=130, max_hp=130, cooldowns={"undying_fury": 12, "soul_rend": 3})
        enemy = _make_enemy(x=6, y=5)  # only 1 adjacent
        all_units = _build_units(rev, enemy)

        result = _retaliation_tank_skill_logic(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "deaths_embrace"

    def test_skips_deaths_embrace_when_buff_already_active(self):
        """Death's Embrace does NOT fire when embrace buff is already active."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_fury": 12, "soul_rend": 3},
            active_buffs=[{"type": "deaths_embrace_buff", "buff_id": "deaths_embrace", "magnitude": 8, "duration_turns": 2}],
        )
        enemy1 = _make_enemy(player_id="enemy1", x=6, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=5, y=6)
        all_units = _build_units(rev, enemy1, enemy2)

        result = _retaliation_tank_skill_logic(
            rev, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "deaths_embrace"

    def test_skips_deaths_embrace_on_cooldown(self):
        """Death's Embrace on cooldown → skipped even with 2+ enemies nearby."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_fury": 12, "soul_rend": 3, "deaths_embrace": 5},
        )
        enemy1 = _make_enemy(player_id="enemy1", x=6, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=5, y=6)
        all_units = _build_units(rev, enemy1, enemy2)

        result = _retaliation_tank_skill_logic(
            rev, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "deaths_embrace"


# ===========================================================================
# 4. Grave Chains — Ranged Taunt on Squishy/Ranged Enemies
# ===========================================================================

class TestGraspOfTheGraveAI:
    """Revenant AI roots ranged/kiting enemies at range with Grasp of the Grave."""

    def test_uses_grasp_of_the_grave_on_ranged_enemy(self):
        """Grasp of the Grave fires on a ranged enemy within 4 tiles, not adjacent."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_fury": 12, "deaths_embrace": 5},
        )
        # Ranged enemy at distance 3 — perfect root target
        ranged_enemy = _make_enemy(
            player_id="ranged1", x=8, y=5, class_id="ranger", ranged_range=6,
        )
        all_units = _build_units(rev, ranged_enemy)

        result = _retaliation_tank_skill_logic(
            rev, [ranged_enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "grasp_of_the_grave"
        assert result.target_id == "ranged1"

    def test_prefers_squishier_targets(self):
        """Grasp of the Grave prefers Mage (squishy priority + ranged bonus) over Crusader."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_fury": 12, "deaths_embrace": 5},
        )
        # Two enemies at distance 2 — both valid root targets (not adjacent)
        mage_enemy = _make_enemy(
            player_id="mage1", x=7, y=5, class_id="mage", ranged_range=5,
        )
        crusader_enemy = _make_enemy(
            player_id="crus1", x=5, y=7, class_id="crusader", ranged_range=0,
        )
        all_units = _build_units(rev, mage_enemy, crusader_enemy)

        result = _retaliation_tank_skill_logic(
            rev, [mage_enemy, crusader_enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "grasp_of_the_grave"
        assert result.target_id == "mage1"  # Mage has higher squishy + ranged priority

    def test_skips_grasp_on_adjacent_enemy(self):
        """Grasp of the Grave does NOT target adjacent enemies (already in melee)."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_fury": 12, "deaths_embrace": 5},
        )
        # Only enemy is adjacent — should skip Grasp, use Soul Rend instead
        adjacent_enemy = _make_enemy(player_id="adj1", x=6, y=5, class_id="mage")
        all_units = _build_units(rev, adjacent_enemy)

        result = _retaliation_tank_skill_logic(
            rev, [adjacent_enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should NOT be grasp_of_the_grave — enemy is adjacent
        if result is not None:
            assert result.skill_id != "grasp_of_the_grave"

    def test_skips_grasp_on_out_of_range_enemy(self):
        """Grasp of the Grave does NOT target enemies beyond range 4."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_fury": 12, "deaths_embrace": 5},
        )
        # Enemy at distance 5 — beyond Grasp range
        far_enemy = _make_enemy(player_id="far1", x=10, y=5, class_id="ranger", ranged_range=6)
        all_units = _build_units(rev, far_enemy)

        result = _retaliation_tank_skill_logic(
            rev, [far_enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should be None — no skill usable (no adjacent enemy for Soul Rend either)
        assert result is None

    def test_skips_grasp_on_cooldown(self):
        """Grasp of the Grave on cooldown → skipped."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_fury": 12, "deaths_embrace": 5, "grasp_of_the_grave": 4},
        )
        ranged_enemy = _make_enemy(
            player_id="ranged1", x=8, y=5, class_id="ranger", ranged_range=6,
        )
        all_units = _build_units(rev, ranged_enemy)

        result = _retaliation_tank_skill_logic(
            rev, [ranged_enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "grasp_of_the_grave"

    def test_skips_already_rooted_enemy(self):
        """Grasp of the Grave skips enemies that already have a rooted debuff."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_fury": 12, "deaths_embrace": 5},
        )
        rooted_enemy = _make_enemy(
            player_id="rooted1", x=7, y=5, class_id="mage", ranged_range=5,
            active_buffs=[{"stat": "rooted", "source_id": "rev1", "turns_remaining": 2}],
        )
        all_units = _build_units(rev, rooted_enemy)

        result = _retaliation_tank_skill_logic(
            rev, [rooted_enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should skip — enemy already rooted; no adjacent enemy so returns None
        assert result is None


# ===========================================================================
# 5. Soul Rend — Melee Slow on Adjacent Enemy
# ===========================================================================

class TestSoulRendAI:
    """Revenant AI uses Soul Rend on adjacent enemies."""

    def test_uses_soul_rend_on_adjacent_enemy(self):
        """Soul Rend fires when an enemy is adjacent (priority 2 after Undying Fury)."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_fury": 12},
        )
        enemy = _make_enemy(x=6, y=5)  # adjacent
        all_units = _build_units(rev, enemy)

        result = _retaliation_tank_skill_logic(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "soul_rend"

    def test_soul_rend_targets_lowest_hp_enemy(self):
        """Soul Rend targets the adjacent enemy with the lowest HP."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_fury": 12},
        )
        enemy_high = _make_enemy(player_id="enemy_high", x=6, y=5, hp=80)
        enemy_low = _make_enemy(player_id="enemy_low", x=4, y=5, hp=20)
        all_units = _build_units(rev, enemy_high, enemy_low)

        result = _retaliation_tank_skill_logic(
            rev, [enemy_high, enemy_low], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "soul_rend"
        assert result.target_id == "enemy_low"

    def test_skips_soul_rend_no_adjacent_enemy(self):
        """Soul Rend does NOT fire when no enemies are adjacent."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_fury": 12, "deaths_embrace": 5, "grasp_of_the_grave": 4},
        )
        enemy = _make_enemy(x=15, y=15)  # far away
        all_units = _build_units(rev, enemy)

        result = _retaliation_tank_skill_logic(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None  # No skill usable → fall through

    def test_skips_soul_rend_on_cooldown(self):
        """Soul Rend on cooldown → returns None (all skills exhausted)."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={
                "undying_fury": 12,
                "soul_rend": 3,
                "deaths_embrace": 5,
                "grasp_of_the_grave": 4,
            },
        )
        enemy = _make_enemy(x=6, y=5)
        all_units = _build_units(rev, enemy)

        result = _retaliation_tank_skill_logic(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None


# ===========================================================================
# 6. Fallback / Edge Cases
# ===========================================================================

class TestRetalTankFallback:
    """Edge cases and fallback behavior for Revenant AI."""

    def test_returns_none_all_skills_on_cooldown(self):
        """All skills on cooldown → returns None for fallback to basic attack."""
        rev = _make_revenant(
            hp=40, max_hp=130,
            cooldowns={
                "undying_fury": 12,
                "soul_rend": 3,
                "deaths_embrace": 5,
                "grasp_of_the_grave": 4,
            },
        )
        enemy = _make_enemy(x=6, y=5)
        all_units = _build_units(rev, enemy)

        result = _retaliation_tank_skill_logic(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None

    def test_returns_none_no_enemies(self):
        """No enemies visible → returns None immediately."""
        rev = _make_revenant()

        result = _retaliation_tank_skill_logic(
            rev, [], {rev.player_id: rev}, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None


# ===========================================================================
# 7. Dispatcher Integration
# ===========================================================================

class TestRetalTankDispatcher:
    """_decide_skill_usage dispatches revenant to retaliation_tank handler."""

    def test_decide_skill_dispatches_revenant(self):
        """_decide_skill_usage routes revenant to _retaliation_tank_skill_logic."""
        rev = _make_revenant(hp=44, max_hp=130)  # ~33.8% HP — below 35%
        enemy = _make_enemy(x=6, y=5)  # adjacent
        all_units = _build_units(rev, enemy)

        result = _decide_skill_usage(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should return Undying Fury (priority 1 — HP below 35%)
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "undying_fury"

    def test_decide_skill_revenant_embrace_when_surrounded(self):
        """Dispatcher correctly routes Revenant Death's Embrace when surrounded (soul_rend on CD)."""
        rev = _make_revenant(hp=130, max_hp=130, cooldowns={"undying_fury": 12, "soul_rend": 3})
        enemy1 = _make_enemy(player_id="enemy1", x=6, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=5, y=6)
        all_units = _build_units(rev, enemy1, enemy2)

        result = _decide_skill_usage(
            rev, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "deaths_embrace"
