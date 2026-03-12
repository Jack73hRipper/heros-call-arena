"""
Tests for Phase 22D: Blood Knight AI Behavior (sustain_dps role).

Covers:
- Role mapping: blood_knight maps to "sustain_dps"
- _sustain_dps_skill_logic() — full priority chain
  - Blood Frenzy: uses when HP < 40%, skips when HP >= 40%
  - Crimson Veil: uses when enemies within 2 tiles, skips when no enemies nearby
  - Sanguine Burst: uses when 2+ enemies adjacent, skips when fewer
  - Blood Strike: uses on lowest-HP adjacent enemy, skips when none adjacent
  - Fallback: returns None when all skills on cooldown
- _decide_skill_usage() dispatches blood_knight to sustain_dps handler
- Priority ordering: Blood Frenzy > Crimson Veil > Sanguine Burst > Blood Strike
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import ActionType, PlayerAction
from app.core.ai_skills import (
    _CLASS_ROLE_MAP,
    _get_role_for_class,
    _try_skill,
    _sustain_dps_skill_logic,
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

def _make_blood_knight(
    player_id: str = "bk1",
    x: int = 5,
    y: int = 5,
    hp: int = 100,
    max_hp: int = 100,
    team: str = "team_1",
    cooldowns: dict | None = None,
    active_buffs: list | None = None,
) -> PlayerState:
    """Create a Blood Knight AI unit."""
    return PlayerState(
        player_id=player_id,
        username="BloodKnight",
        position=Position(x=x, y=y),
        class_id="blood_knight",
        hp=hp,
        max_hp=max_hp,
        is_alive=True,
        team=team,
        unit_type="ai",
        hero_id="bk_hero_001",
        ai_stance="follow",
        ranged_range=0,
        vision_range=6,
        attack_damage=16,
        armor=4,
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
    active_buffs: list | None = None,
) -> PlayerState:
    """Create an enemy unit on the opposing team."""
    return PlayerState(
        player_id=player_id,
        username="Enemy",
        position=Position(x=x, y=y),
        class_id=None,
        hp=hp,
        max_hp=max_hp,
        is_alive=True,
        team=team,
        unit_type="ai",
        hero_id=None,
        ranged_range=0,
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

class TestBloodKnightRoleMapping:
    """Blood Knight class maps to sustain_dps role."""

    def test_blood_knight_maps_to_sustain_dps(self):
        """blood_knight → sustain_dps in _CLASS_ROLE_MAP."""
        assert _get_role_for_class("blood_knight") == "sustain_dps"

    def test_sustain_dps_in_role_map(self):
        """_CLASS_ROLE_MAP contains blood_knight entry."""
        assert "blood_knight" in _CLASS_ROLE_MAP
        assert _CLASS_ROLE_MAP["blood_knight"] == "sustain_dps"

    def test_role_map_count_updated(self):
        """_CLASS_ROLE_MAP has correct entry count (29 = 28 previous + plague_doctor)."""
        assert len(_CLASS_ROLE_MAP) == 31


# ===========================================================================
# 2. Blood Frenzy — Emergency Low-HP Burst
# ===========================================================================

class TestBloodFrenzyAI:
    """Blood Knight AI uses Blood Frenzy when HP < 40%."""

    def test_uses_blood_frenzy_when_low_hp(self):
        """Blood Frenzy fires when HP is below 40% threshold."""
        bk = _make_blood_knight(hp=35, max_hp=100)  # 35% HP
        enemy = _make_enemy(x=6, y=5)  # adjacent
        all_units = _build_units(bk, enemy)

        result = _sustain_dps_skill_logic(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "blood_frenzy"

    def test_skips_blood_frenzy_when_hp_above_threshold(self):
        """Blood Frenzy does NOT fire when HP >= 40%."""
        bk = _make_blood_knight(hp=50, max_hp=100)  # 50% HP — above threshold
        enemy = _make_enemy(x=6, y=5)
        all_units = _build_units(bk, enemy)

        result = _sustain_dps_skill_logic(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should NOT be blood_frenzy — may be crimson_veil, blood_strike, or None
        if result is not None:
            assert result.skill_id != "blood_frenzy"

    def test_skips_blood_frenzy_on_cooldown(self):
        """Blood Frenzy on cooldown → skipped even at low HP."""
        bk = _make_blood_knight(hp=30, max_hp=100, cooldowns={"blood_frenzy": 5})
        enemy = _make_enemy(x=6, y=5)
        all_units = _build_units(bk, enemy)

        result = _sustain_dps_skill_logic(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "blood_frenzy"

    def test_blood_frenzy_prioritized_over_other_skills(self):
        """Blood Frenzy takes priority over Crimson Veil, Sanguine Burst, and Blood Strike."""
        bk = _make_blood_knight(hp=30, max_hp=100)  # 30% HP — all skills available
        enemy1 = _make_enemy(player_id="enemy1", x=6, y=5)  # adjacent
        enemy2 = _make_enemy(player_id="enemy2", x=5, y=6)  # adjacent
        all_units = _build_units(bk, enemy1, enemy2)

        result = _sustain_dps_skill_logic(
            bk, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "blood_frenzy"


# ===========================================================================
# 3. Crimson Veil — Pre-Engage Damage Buff + HoT
# ===========================================================================

class TestCrimsonVeilAI:
    """Blood Knight AI uses Crimson Veil as an in-combat buff (enemies adjacent or nearby)."""

    def test_uses_crimson_veil_when_adjacent(self):
        """Crimson Veil fires when enemy is adjacent — it amplifies Blood Strike
        and auto-attack damage, so buffing in melee is high value."""
        bk = _make_blood_knight(hp=100, max_hp=100, cooldowns={"blood_frenzy": 5})
        enemy = _make_enemy(x=6, y=5)  # adjacent
        all_units = _build_units(bk, enemy)

        result = _sustain_dps_skill_logic(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        # Crimson Veil is priority 2 (above Blood Strike at priority 4) when off cooldown
        assert result.skill_id == "crimson_veil"

    def test_uses_crimson_veil_with_nearby_enemy(self):
        """Crimson Veil fires when enemy is within 2 tiles (not yet adjacent)."""
        bk = _make_blood_knight(hp=100, max_hp=100, cooldowns={"blood_frenzy": 5})
        enemy = _make_enemy(x=7, y=5)  # distance 2 — within engage range
        all_units = _build_units(bk, enemy)

        result = _sustain_dps_skill_logic(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "crimson_veil"

    def test_blood_strike_used_when_veil_on_cooldown(self):
        """When Crimson Veil is on cooldown and enemy is adjacent, Blood Strike fires."""
        bk = _make_blood_knight(hp=90, max_hp=100, cooldowns={"blood_frenzy": 5, "crimson_veil": 3})
        enemy = _make_enemy(x=6, y=5)  # adjacent
        all_units = _build_units(bk, enemy)

        result = _sustain_dps_skill_logic(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "blood_strike"

    def test_skips_crimson_veil_no_enemies_nearby(self):
        """Crimson Veil does NOT fire when all enemies are far away (> 2 tiles)."""
        bk = _make_blood_knight(hp=100, max_hp=100, cooldowns={"blood_frenzy": 5})
        enemy = _make_enemy(x=15, y=15)  # far away
        all_units = _build_units(bk, enemy)

        result = _sustain_dps_skill_logic(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should NOT be crimson_veil — enemy is too far
        if result is not None:
            assert result.skill_id != "crimson_veil"

    def test_skips_crimson_veil_on_cooldown(self):
        """Crimson Veil on cooldown → skipped, falls through to next priority."""
        bk = _make_blood_knight(
            hp=100, max_hp=100,
            cooldowns={"blood_frenzy": 5, "crimson_veil": 3},
        )
        enemy = _make_enemy(x=6, y=5)  # adjacent
        all_units = _build_units(bk, enemy)

        result = _sustain_dps_skill_logic(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "crimson_veil"


# ===========================================================================
# 4. Sanguine Burst — AoE Lifesteal When Surrounded
# ===========================================================================

class TestSanguineBurstAI:
    """Blood Knight AI uses Sanguine Burst when 2+ enemies adjacent."""

    def test_uses_sanguine_burst_with_two_adjacent_enemies(self):
        """Sanguine Burst fires when 2+ enemies are adjacent."""
        bk = _make_blood_knight(
            hp=100, max_hp=100,
            cooldowns={"blood_frenzy": 5, "crimson_veil": 3},
        )
        enemy1 = _make_enemy(player_id="enemy1", x=6, y=5)  # adjacent
        enemy2 = _make_enemy(player_id="enemy2", x=5, y=6)  # adjacent
        all_units = _build_units(bk, enemy1, enemy2)

        result = _sustain_dps_skill_logic(
            bk, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "sanguine_burst"

    def test_skips_sanguine_burst_with_one_adjacent_enemy(self):
        """Sanguine Burst does NOT fire with only 1 adjacent enemy (below threshold)."""
        bk = _make_blood_knight(
            hp=100, max_hp=100,
            cooldowns={"blood_frenzy": 5, "crimson_veil": 3},
        )
        enemy1 = _make_enemy(player_id="enemy1", x=6, y=5)  # adjacent
        enemy2 = _make_enemy(player_id="enemy2", x=15, y=15)  # far away — not adjacent
        all_units = _build_units(bk, enemy1, enemy2)

        result = _sustain_dps_skill_logic(
            bk, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "sanguine_burst"

    def test_skips_sanguine_burst_on_cooldown(self):
        """Sanguine Burst on cooldown → skipped."""
        bk = _make_blood_knight(
            hp=100, max_hp=100,
            cooldowns={"blood_frenzy": 5, "crimson_veil": 3, "sanguine_burst": 4},
        )
        enemy1 = _make_enemy(player_id="enemy1", x=6, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=5, y=6)
        all_units = _build_units(bk, enemy1, enemy2)

        result = _sustain_dps_skill_logic(
            bk, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "sanguine_burst"


# ===========================================================================
# 5. Blood Strike — Single-Target Lifesteal
# ===========================================================================

class TestBloodStrikeAI:
    """Blood Knight AI uses Blood Strike on lowest-HP adjacent enemy."""

    def test_uses_blood_strike_on_adjacent_enemy(self):
        """Blood Strike fires when an enemy is adjacent and higher-priority skills exhausted."""
        bk = _make_blood_knight(
            hp=90, max_hp=100,
            cooldowns={"blood_frenzy": 5, "crimson_veil": 3, "sanguine_burst": 4},
        )
        enemy = _make_enemy(x=6, y=5)  # adjacent
        all_units = _build_units(bk, enemy)

        result = _sustain_dps_skill_logic(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "blood_strike"

    def test_blood_strike_targets_lowest_hp_enemy(self):
        """Blood Strike targets the adjacent enemy with the lowest HP."""
        bk = _make_blood_knight(
            hp=90, max_hp=100,
            cooldowns={"blood_frenzy": 5, "crimson_veil": 3, "sanguine_burst": 4},
        )
        enemy_high = _make_enemy(player_id="enemy_high", x=6, y=5, hp=80)
        enemy_low = _make_enemy(player_id="enemy_low", x=4, y=5, hp=20)
        all_units = _build_units(bk, enemy_high, enemy_low)

        result = _sustain_dps_skill_logic(
            bk, [enemy_high, enemy_low], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "blood_strike"
        assert result.target_id == "enemy_low"

    def test_skips_blood_strike_no_adjacent_enemy(self):
        """Blood Strike does NOT fire when no enemies are adjacent."""
        bk = _make_blood_knight(
            hp=100, max_hp=100,
            cooldowns={"blood_frenzy": 5, "crimson_veil": 3, "sanguine_burst": 4},
        )
        enemy = _make_enemy(x=15, y=15)  # far away
        all_units = _build_units(bk, enemy)

        result = _sustain_dps_skill_logic(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None  # No skill usable → fall through to basic attack

    def test_skips_blood_strike_on_cooldown(self):
        """Blood Strike on cooldown → returns None (all skills exhausted)."""
        bk = _make_blood_knight(
            hp=90, max_hp=100,
            cooldowns={
                "blood_frenzy": 5,
                "crimson_veil": 3,
                "sanguine_burst": 4,
                "blood_strike": 2,
            },
        )
        enemy = _make_enemy(x=6, y=5)
        all_units = _build_units(bk, enemy)

        result = _sustain_dps_skill_logic(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None


# ===========================================================================
# 6. Fallback / Edge Cases
# ===========================================================================

class TestSustainDpsFallback:
    """Edge cases and fallback behavior for Blood Knight AI."""

    def test_returns_none_all_skills_on_cooldown(self):
        """All skills on cooldown → returns None for fallback to basic attack."""
        bk = _make_blood_knight(
            hp=30, max_hp=100,
            cooldowns={
                "blood_frenzy": 5,
                "crimson_veil": 3,
                "sanguine_burst": 4,
                "blood_strike": 2,
            },
        )
        enemy = _make_enemy(x=6, y=5)
        all_units = _build_units(bk, enemy)

        result = _sustain_dps_skill_logic(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None

    def test_returns_none_no_enemies(self):
        """No enemies visible → returns None immediately."""
        bk = _make_blood_knight()

        result = _sustain_dps_skill_logic(
            bk, [], {bk.player_id: bk}, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None

    def test_skips_blood_strike_at_full_hp(self):
        """Blood Strike skipped at full HP — lifesteal heal wasted as overheal.
        AI should fall through to auto-attack to save the cooldown."""
        bk = _make_blood_knight(
            hp=100, max_hp=100,
            cooldowns={"blood_frenzy": 5, "crimson_veil": 3, "sanguine_burst": 4},
        )
        enemy = _make_enemy(x=6, y=5)  # adjacent
        all_units = _build_units(bk, enemy)

        result = _sustain_dps_skill_logic(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # At full HP, Blood Strike is skipped → no skill fires
        assert result is None

    def test_blood_strike_fires_when_wounded(self):
        """Blood Strike fires when HP < max — lifesteal is meaningful."""
        bk = _make_blood_knight(
            hp=85, max_hp=100,
            cooldowns={"blood_frenzy": 5, "crimson_veil": 3, "sanguine_burst": 4},
        )
        enemy = _make_enemy(x=6, y=5)  # adjacent
        all_units = _build_units(bk, enemy)

        result = _sustain_dps_skill_logic(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "blood_strike"

    def test_skips_crimson_veil_when_already_active(self):
        """Crimson Veil skipped when the buff is already running —
        prevents wasting a turn re-buffing."""
        bk = _make_blood_knight(
            hp=80, max_hp=100,
            cooldowns={"blood_frenzy": 5},
            active_buffs=[{"buff_id": "crimson_veil", "stat": "melee_damage_multiplier", "magnitude": 1.3, "turns_remaining": 2}],
        )
        enemy = _make_enemy(x=6, y=5)  # adjacent
        all_units = _build_units(bk, enemy)

        result = _sustain_dps_skill_logic(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Crimson Veil should be skipped; should use Blood Strike instead
        assert result is not None
        assert result.skill_id != "crimson_veil"
        assert result.skill_id == "blood_strike"


# ===========================================================================
# 7. Dispatcher Integration
# ===========================================================================

class TestSustainDpsDispatcher:
    """_decide_skill_usage dispatches blood_knight to sustain_dps handler."""

    def test_decide_skill_dispatches_blood_knight(self):
        """_decide_skill_usage routes blood_knight to _sustain_dps_skill_logic."""
        bk = _make_blood_knight(hp=100, max_hp=100)
        enemy = _make_enemy(x=6, y=5)  # adjacent
        all_units = _build_units(bk, enemy)

        result = _decide_skill_usage(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should return a skill action (crimson_veil — priority 2 when adjacent + off cooldown)
        assert result is not None
        assert result.action_type == ActionType.SKILL

    def test_decide_skill_blood_knight_frenzy_at_low_hp(self):
        """Dispatcher correctly routes blood_knight Blood Frenzy at low HP."""
        bk = _make_blood_knight(hp=30, max_hp=100)
        enemy = _make_enemy(x=6, y=5)
        all_units = _build_units(bk, enemy)

        result = _decide_skill_usage(
            bk, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "blood_frenzy"
