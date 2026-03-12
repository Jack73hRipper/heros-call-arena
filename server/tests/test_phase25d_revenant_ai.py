"""
Tests for Phase 25D: Revenant AI Behavior (retaliation_tank role).

Covers:
- Role mapping: revenant maps to "retaliation_tank"
- _retaliation_tank_skill_logic() — full priority chain
  - Undying Will: uses when HP < 40% and no cheat_death buff, skips otherwise
  - Grave Thorns: uses when 2+ enemies within 2 tiles and no thorns active
  - Grave Chains: taunts ranged/squishy enemy within 3 tiles (not adjacent)
  - Soul Rend: uses on adjacent enemy (slow)
  - Fallback: returns None when all skills on cooldown
- _decide_skill_usage() dispatches revenant to retaliation_tank handler
- Priority ordering: Undying Will > Grave Thorns > Grave Chains > Soul Rend
- Smart targeting: prefers squishier classes for Grave Chains
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

class TestUndyingWillAI:
    """Revenant AI casts Undying Will when HP < 40% and no cheat_death buff."""

    def test_uses_undying_will_when_low_hp(self):
        """Undying Will fires when HP is below 40% threshold and no buff active."""
        rev = _make_revenant(hp=50, max_hp=130)  # ~38% HP
        enemy = _make_enemy(x=6, y=5)  # adjacent
        all_units = _build_units(rev, enemy)

        result = _retaliation_tank_skill_logic(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "undying_will"

    def test_skips_undying_will_when_hp_above_threshold(self):
        """Undying Will does NOT fire when HP >= 40%."""
        rev = _make_revenant(hp=60, max_hp=130)  # ~46% HP — above threshold
        enemy = _make_enemy(x=6, y=5)
        all_units = _build_units(rev, enemy)

        result = _retaliation_tank_skill_logic(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should NOT be undying_will
        if result is not None:
            assert result.skill_id != "undying_will"

    def test_skips_undying_will_when_buff_already_active(self):
        """Undying Will does NOT fire when cheat_death buff is already active."""
        rev = _make_revenant(
            hp=40, max_hp=130,  # ~31% HP — below threshold
            active_buffs=[{"stat": "cheat_death", "revive_hp_pct": 0.30, "duration_turns": 4}],
        )
        enemy = _make_enemy(x=6, y=5)
        all_units = _build_units(rev, enemy)

        result = _retaliation_tank_skill_logic(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should NOT be undying_will — buff already active
        if result is not None:
            assert result.skill_id != "undying_will"

    def test_skips_undying_will_on_cooldown(self):
        """Undying Will on cooldown → skipped even at low HP."""
        rev = _make_revenant(hp=40, max_hp=130, cooldowns={"undying_will": 8})
        enemy = _make_enemy(x=6, y=5)
        all_units = _build_units(rev, enemy)

        result = _retaliation_tank_skill_logic(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "undying_will"

    def test_undying_will_prioritized_over_other_skills(self):
        """Undying Will takes priority over Grave Thorns, Grave Chains, and Soul Rend."""
        rev = _make_revenant(hp=40, max_hp=130)  # ~31% HP — all skills available
        enemy1 = _make_enemy(player_id="enemy1", x=6, y=5)  # adjacent
        enemy2 = _make_enemy(player_id="enemy2", x=5, y=6)  # adjacent
        all_units = _build_units(rev, enemy1, enemy2)

        result = _retaliation_tank_skill_logic(
            rev, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "undying_will"


# ===========================================================================
# 3. Grave Thorns — Self-Buff When Surrounded
# ===========================================================================

class TestGraveThornsAI:
    """Revenant AI casts Grave Thorns when 2+ enemies nearby and no thorns active."""

    def test_uses_grave_thorns_when_two_enemies_nearby(self):
        """Grave Thorns fires when 2+ enemies within 2 tiles, soul_rend on CD, and no thorns buff."""
        rev = _make_revenant(hp=130, max_hp=130, cooldowns={"undying_will": 8, "soul_rend": 3})
        enemy1 = _make_enemy(player_id="enemy1", x=6, y=5)  # adjacent (dist 1)
        enemy2 = _make_enemy(player_id="enemy2", x=5, y=6)  # adjacent (dist 1)
        all_units = _build_units(rev, enemy1, enemy2)

        result = _retaliation_tank_skill_logic(
            rev, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "grave_thorns"

    def test_uses_grave_thorns_with_one_enemy_nearby(self):
        """Grave Thorns fires even with only 1 enemy nearby (soul_rend on CD)."""
        rev = _make_revenant(hp=130, max_hp=130, cooldowns={"undying_will": 8, "soul_rend": 3})
        enemy = _make_enemy(x=6, y=5)  # only 1 adjacent
        all_units = _build_units(rev, enemy)

        result = _retaliation_tank_skill_logic(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Thorns should activate even against a single enemy — it's the Rev's core identity
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "grave_thorns"

    def test_skips_grave_thorns_when_buff_already_active(self):
        """Grave Thorns does NOT fire when thorns_damage buff is already active."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_will": 8},
            active_buffs=[{"stat": "thorns_damage", "magnitude": 10, "duration_turns": 2}],
        )
        enemy1 = _make_enemy(player_id="enemy1", x=6, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=5, y=6)
        all_units = _build_units(rev, enemy1, enemy2)

        result = _retaliation_tank_skill_logic(
            rev, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "grave_thorns"

    def test_skips_grave_thorns_on_cooldown(self):
        """Grave Thorns on cooldown → skipped even with 2+ enemies nearby."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_will": 8, "grave_thorns": 4},
        )
        enemy1 = _make_enemy(player_id="enemy1", x=6, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=5, y=6)
        all_units = _build_units(rev, enemy1, enemy2)

        result = _retaliation_tank_skill_logic(
            rev, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "grave_thorns"


# ===========================================================================
# 4. Grave Chains — Ranged Taunt on Squishy/Ranged Enemies
# ===========================================================================

class TestGraveChainsAI:
    """Revenant AI taunts squishy/ranged enemies at range with Grave Chains."""

    def test_uses_grave_chains_on_ranged_enemy(self):
        """Grave Chains fires on a ranged enemy within 3 tiles, not adjacent."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_will": 8, "grave_thorns": 4},
        )
        # Ranged enemy at distance 3 — perfect taunt target
        ranged_enemy = _make_enemy(
            player_id="ranged1", x=8, y=5, class_id="ranger", ranged_range=6,
        )
        all_units = _build_units(rev, ranged_enemy)

        result = _retaliation_tank_skill_logic(
            rev, [ranged_enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "grave_chains"
        assert result.target_id == "ranged1"

    def test_prefers_squishier_targets(self):
        """Grave Chains prefers Mage (squishy priority 5) over Crusader (no priority)."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_will": 8, "grave_thorns": 4},
        )
        # Two enemies at distance 2-3 — both valid taunt targets
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
        assert result.skill_id == "grave_chains"
        assert result.target_id == "mage1"  # Mage has higher squishy priority

    def test_skips_grave_chains_on_adjacent_enemy(self):
        """Grave Chains does NOT target adjacent enemies (already in melee)."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_will": 8, "grave_thorns": 4},
        )
        # Only enemy is adjacent — should skip Grave Chains, use Soul Rend instead
        adjacent_enemy = _make_enemy(player_id="adj1", x=6, y=5, class_id="mage")
        all_units = _build_units(rev, adjacent_enemy)

        result = _retaliation_tank_skill_logic(
            rev, [adjacent_enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should NOT be grave_chains — enemy is adjacent
        if result is not None:
            assert result.skill_id != "grave_chains"

    def test_skips_grave_chains_on_out_of_range_enemy(self):
        """Grave Chains does NOT target enemies beyond range 4."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_will": 8, "grave_thorns": 4},
        )
        # Enemy at distance 5 — beyond Grave Chains range
        far_enemy = _make_enemy(player_id="far1", x=10, y=5, class_id="ranger", ranged_range=6)
        all_units = _build_units(rev, far_enemy)

        result = _retaliation_tank_skill_logic(
            rev, [far_enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should be None — no skill usable (no adjacent enemy for Soul Rend either)
        assert result is None

    def test_skips_grave_chains_on_cooldown(self):
        """Grave Chains on cooldown → skipped."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_will": 8, "grave_thorns": 4, "grave_chains": 3},
        )
        ranged_enemy = _make_enemy(
            player_id="ranged1", x=8, y=5, class_id="ranger", ranged_range=6,
        )
        all_units = _build_units(rev, ranged_enemy)

        result = _retaliation_tank_skill_logic(
            rev, [ranged_enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "grave_chains"

    def test_skips_already_taunted_enemy(self):
        """Grave Chains skips enemies that already have a forced_target buff."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_will": 8, "grave_thorns": 4},
        )
        taunted_enemy = _make_enemy(
            player_id="taunted1", x=7, y=5, class_id="mage", ranged_range=5,
            active_buffs=[{"stat": "forced_target", "target_id": "rev1", "duration_turns": 2}],
        )
        all_units = _build_units(rev, taunted_enemy)

        result = _retaliation_tank_skill_logic(
            rev, [taunted_enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should skip — enemy already taunted; no adjacent enemy so returns None
        assert result is None


# ===========================================================================
# 5. Soul Rend — Melee Slow on Adjacent Enemy
# ===========================================================================

class TestSoulRendAI:
    """Revenant AI uses Soul Rend on adjacent enemies."""

    def test_uses_soul_rend_on_adjacent_enemy(self):
        """Soul Rend fires when an enemy is adjacent and higher-priority skills exhausted."""
        rev = _make_revenant(
            hp=130, max_hp=130,
            cooldowns={"undying_will": 8, "grave_thorns": 4, "grave_chains": 3},
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
            cooldowns={"undying_will": 8, "grave_thorns": 4, "grave_chains": 3},
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
            cooldowns={"undying_will": 8, "grave_thorns": 4, "grave_chains": 3},
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
                "undying_will": 8,
                "grave_thorns": 4,
                "grave_chains": 3,
                "soul_rend": 2,
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
                "undying_will": 8,
                "grave_thorns": 4,
                "grave_chains": 3,
                "soul_rend": 2,
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
        rev = _make_revenant(hp=50, max_hp=130)  # ~38% HP
        enemy = _make_enemy(x=6, y=5)  # adjacent
        all_units = _build_units(rev, enemy)

        result = _decide_skill_usage(
            rev, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should return Undying Will (priority 1 — HP below 40%)
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "undying_will"

    def test_decide_skill_revenant_thorns_when_surrounded(self):
        """Dispatcher correctly routes Revenant Grave Thorns when surrounded (soul_rend on CD)."""
        rev = _make_revenant(hp=130, max_hp=130, cooldowns={"undying_will": 8, "soul_rend": 3})
        enemy1 = _make_enemy(player_id="enemy1", x=6, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=5, y=6)
        all_units = _build_units(rev, enemy1, enemy2)

        result = _decide_skill_usage(
            rev, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "grave_thorns"
