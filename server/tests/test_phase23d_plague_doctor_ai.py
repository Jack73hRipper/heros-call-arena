"""
Tests for Phase 23D: Plague Doctor AI Behavior (controller role).

Covers:
- Role mapping: plague_doctor maps to "controller"
- _controller_skill_logic() — full priority chain
  - Enfeeble: uses when 2+ un-enfeebled enemies in AoE radius, skips otherwise
  - Miasma: uses when 2+ enemies clustered, skips when fewer
  - Plague Flask: targets highest-HP enemy without active DoT
  - Inoculate: cures ally with DoT, or buffs injured ally
  - Fallback: returns None when all skills on cooldown
- _decide_skill_usage() dispatches plague_doctor to controller handler
- Priority ordering: Enfeeble > Miasma > Plague Flask > Inoculate
- Positioning: controller role uses support move preference (stay near allies)
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import ActionType, PlayerAction
from app.core.ai_skills import (
    _CLASS_ROLE_MAP,
    _get_role_for_class,
    _try_skill,
    _controller_skill_logic,
    _support_move_preference,
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

def _make_plague_doctor(
    player_id: str = "pd1",
    x: int = 5,
    y: int = 5,
    hp: int = 85,
    max_hp: int = 85,
    team: str = "team_1",
    cooldowns: dict | None = None,
    active_buffs: list | None = None,
) -> PlayerState:
    """Create a Plague Doctor AI unit."""
    return PlayerState(
        player_id=player_id,
        username="PlagueDoc",
        position=Position(x=x, y=y),
        class_id="plague_doctor",
        hp=hp,
        max_hp=max_hp,
        is_alive=True,
        team=team,
        unit_type="ai",
        hero_id="pd_hero_001",
        ai_stance="follow",
        ranged_range=5,
        vision_range=7,
        attack_damage=12,
        armor=2,
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
        inventory=[],
    )


def _make_ally(
    player_id: str = "ally1",
    class_id: str = "crusader",
    x: int = 6,
    y: int = 5,
    hp: int = 150,
    max_hp: int = 150,
    team: str = "team_1",
    cooldowns: dict | None = None,
    active_buffs: list | None = None,
) -> PlayerState:
    """Create an ally unit on the same team."""
    return PlayerState(
        player_id=player_id,
        username=f"Ally_{class_id}",
        position=Position(x=x, y=y),
        class_id=class_id,
        hp=hp,
        max_hp=max_hp,
        is_alive=True,
        team=team,
        unit_type="ai",
        hero_id=f"hero_{player_id}",
        ai_stance="follow",
        ranged_range=5,
        vision_range=7,
        attack_damage=15,
        armor=2,
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
        inventory=[],
    )


def _make_enemy(
    player_id: str = "enemy1",
    x: int = 8,
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
        armor=0,
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

class TestPlagueDocRoleMapping:
    """Plague Doctor class maps to controller role."""

    def test_plague_doctor_maps_to_controller(self):
        """plague_doctor → controller in _CLASS_ROLE_MAP."""
        assert _get_role_for_class("plague_doctor") == "controller"

    def test_controller_in_role_map(self):
        """_CLASS_ROLE_MAP contains plague_doctor entry."""
        assert "plague_doctor" in _CLASS_ROLE_MAP
        assert _CLASS_ROLE_MAP["plague_doctor"] == "controller"

    def test_role_map_count_updated(self):
        """_CLASS_ROLE_MAP has correct entry count (29 = 28 previous + plague_doctor)."""
        assert len(_CLASS_ROLE_MAP) == 31


# ===========================================================================
# 2. Enfeeble — AoE Damage Reduction Debuff
# ===========================================================================

class TestEnfeeble:
    """Plague Doctor AI uses Enfeeble when 2+ un-enfeebled enemies in AoE."""

    def test_uses_enfeeble_with_clustered_enemies(self):
        """Enfeeble fires when 2+ enemies are within radius 2 of each other and plague_flask is on CD."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"plague_flask": 3})
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)  # dist 3 — in enfeeble range 4
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)  # dist 4 — in enfeeble range 4
        all_units = _build_units(pd, enemy1, enemy2)

        result = _controller_skill_logic(
            pd, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "enfeeble"

    def test_skips_enfeeble_with_one_enemy(self):
        """Enfeeble does NOT fire with only 1 enemy (below threshold)."""
        pd = _make_plague_doctor(x=5, y=5)
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)
        all_units = _build_units(pd, enemy1)

        result = _controller_skill_logic(
            pd, [enemy1], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "enfeeble"

    def test_skips_enfeeble_enemies_out_of_range(self):
        """Enfeeble skipped when all enemies are beyond range 4."""
        pd = _make_plague_doctor(x=5, y=5)
        enemy1 = _make_enemy(player_id="enemy1", x=15, y=5)  # dist 10
        enemy2 = _make_enemy(player_id="enemy2", x=15, y=6)  # dist 10
        all_units = _build_units(pd, enemy1, enemy2)

        result = _controller_skill_logic(
            pd, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "enfeeble"

    def test_skips_enfeeble_no_los(self):
        """Enfeeble skipped when there's no line of sight to the target tile."""
        pd = _make_plague_doctor(x=5, y=5)
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)
        # Wall blocking LOS between PD and enemies
        obstacles = {(6, 5), (7, 5), (6, 4), (7, 4), (6, 6), (7, 6)}
        all_units = _build_units(pd, enemy1, enemy2)

        result = _controller_skill_logic(
            pd, [enemy1, enemy2], all_units, GRID_W, GRID_H, obstacles,
        )
        if result is not None:
            assert result.skill_id != "enfeeble"

    def test_skips_enfeeble_enemies_already_debuffed(self):
        """Enfeeble skipped when all enemies already have the enfeeble debuff."""
        pd = _make_plague_doctor(x=5, y=5)
        debuff = {"buff_id": "enfeeble", "type": "debuff",
                  "stat": "damage_dealt_multiplier", "magnitude": 0.75, "turns_remaining": 2}
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5, active_buffs=[debuff.copy()])
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5, active_buffs=[debuff.copy()])
        all_units = _build_units(pd, enemy1, enemy2)

        result = _controller_skill_logic(
            pd, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "enfeeble"

    def test_enfeeble_on_cooldown(self):
        """Enfeeble on cooldown → skipped."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 4})
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)
        all_units = _build_units(pd, enemy1, enemy2)

        result = _controller_skill_logic(
            pd, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "enfeeble"


# ===========================================================================
# 3. Miasma — AoE Damage + Slow
# ===========================================================================

class TestMiasma:
    """Plague Doctor AI uses Miasma when 2+ enemies clustered in range."""

    def test_uses_miasma_with_clustered_enemies(self):
        """Miasma fires when 2+ enemies are clustered and plague_flask + enfeeble are on CD."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 5, "plague_flask": 3})
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)  # dist 3 — in miasma range 5
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)  # dist 4 — in miasma range 5
        all_units = _build_units(pd, enemy1, enemy2)

        result = _controller_skill_logic(
            pd, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "miasma"

    def test_miasma_fires_with_one_enemy_in_range(self):
        """Miasma fires on 1 enemy when plague_flask and enfeeble are on CD (cluster threshold = 1)."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 5, "plague_flask": 3})
        enemy1 = _make_enemy(player_id="enemy1", x=10, y=5)  # dist 5 — in miasma range 5
        all_units = _build_units(pd, enemy1)

        result = _controller_skill_logic(
            pd, [enemy1], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "miasma"

    def test_skips_miasma_enemies_out_of_range(self):
        """Miasma skipped when all enemies are beyond range 5."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 5})
        enemy1 = _make_enemy(player_id="enemy1", x=15, y=5)  # dist 10
        enemy2 = _make_enemy(player_id="enemy2", x=15, y=6)  # dist 10
        all_units = _build_units(pd, enemy1, enemy2)

        result = _controller_skill_logic(
            pd, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "miasma"

    def test_skips_miasma_no_los(self):
        """Miasma skipped when no line of sight to target tile."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 5})
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)
        obstacles = {(6, 5), (7, 5), (6, 4), (7, 4), (6, 6), (7, 6)}
        all_units = _build_units(pd, enemy1, enemy2)

        result = _controller_skill_logic(
            pd, [enemy1, enemy2], all_units, GRID_W, GRID_H, obstacles,
        )
        if result is not None:
            assert result.skill_id != "miasma"

    def test_miasma_on_cooldown(self):
        """Miasma on cooldown → skipped."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 5, "miasma": 3})
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)
        all_units = _build_units(pd, enemy1, enemy2)

        result = _controller_skill_logic(
            pd, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "miasma"


# ===========================================================================
# 4. Plague Flask — Single-Target DoT
# ===========================================================================

class TestPlagueFlask:
    """Plague Doctor AI uses Plague Flask on highest-HP enemy without active DoT."""

    def test_uses_plague_flask_on_unpoisoned_enemy(self):
        """Plague Flask fires when enemy in range has no active DoT."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 5, "miasma": 5})
        enemy = _make_enemy(player_id="enemy1", x=8, y=5, hp=80)  # dist 3
        all_units = _build_units(pd, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "plague_flask"
        assert result.target_id == "enemy1"

    def test_prefers_highest_hp_enemy(self):
        """Plague Flask targets the highest-HP enemy without DoT."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 5, "miasma": 5})
        enemy_low = _make_enemy(player_id="enemy_low", x=8, y=5, hp=30, max_hp=80)
        enemy_high = _make_enemy(player_id="enemy_high", x=9, y=5, hp=80, max_hp=80)
        all_units = _build_units(pd, enemy_low, enemy_high)

        result = _controller_skill_logic(
            pd, [enemy_low, enemy_high], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "plague_flask"
        assert result.target_id == "enemy_high"

    def test_skips_enemy_with_active_dot(self):
        """Plague Flask skips enemies that already have an active DoT."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 5, "miasma": 5})
        dot = {"buff_id": "plague_flask", "type": "dot", "damage_per_tick": 7, "turns_remaining": 3}
        enemy = _make_enemy(player_id="enemy1", x=8, y=5, active_buffs=[dot])
        all_units = _build_units(pd, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "plague_flask"

    def test_skips_plague_flask_enemy_out_of_range(self):
        """Plague Flask skipped when enemy is beyond range 5."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 5, "miasma": 5})
        enemy = _make_enemy(player_id="enemy1", x=15, y=5)  # dist 10
        all_units = _build_units(pd, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "plague_flask"

    def test_skips_plague_flask_no_los(self):
        """Plague Flask skipped when no LOS to enemy."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 5, "miasma": 5})
        enemy = _make_enemy(player_id="enemy1", x=8, y=5)
        obstacles = {(6, 5), (7, 5), (6, 4), (7, 4), (6, 6), (7, 6)}
        all_units = _build_units(pd, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, obstacles,
        )
        if result is not None:
            assert result.skill_id != "plague_flask"

    def test_plague_flask_on_cooldown(self):
        """Plague Flask on cooldown → skipped."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={
            "enfeeble": 5, "miasma": 5, "plague_flask": 3,
        })
        enemy = _make_enemy(player_id="enemy1", x=8, y=5)
        all_units = _build_units(pd, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "plague_flask"


# ===========================================================================
# 5. Inoculate — Buff + DoT Cleanse
# ===========================================================================

class TestInoculate:
    """Plague Doctor AI uses Inoculate on ally with DoT or injured ally."""

    def test_uses_inoculate_on_ally_with_dot(self):
        """Inoculate fires when an ally within range has an active DoT."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={
            "enfeeble": 5, "miasma": 5, "plague_flask": 5,
        })
        dot = {"buff_id": "wither", "type": "dot", "damage_per_tick": 8, "turns_remaining": 3}
        ally = _make_ally(player_id="ally1", x=6, y=5, active_buffs=[dot])
        enemy = _make_enemy(player_id="enemy1", x=15, y=15)
        all_units = _build_units(pd, ally, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "inoculate"
        assert result.target_id == "ally1"

    def test_uses_inoculate_on_self_with_dot(self):
        """Inoculate targets self when PD has an active DoT."""
        dot = {"buff_id": "wither", "type": "dot", "damage_per_tick": 8, "turns_remaining": 3}
        pd = _make_plague_doctor(x=5, y=5, cooldowns={
            "enfeeble": 5, "miasma": 5, "plague_flask": 5,
        }, active_buffs=[dot])
        enemy = _make_enemy(player_id="enemy1", x=15, y=15)
        all_units = _build_units(pd, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "inoculate"
        assert result.target_id == "pd1"

    def test_uses_inoculate_on_injured_ally(self):
        """Inoculate fires on ally below 50% HP (no DoTs present) for armor buff."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={
            "enfeeble": 5, "miasma": 5, "plague_flask": 5,
        })
        ally = _make_ally(player_id="ally1", x=6, y=5, hp=60, max_hp=150)  # 40% HP
        enemy = _make_enemy(player_id="enemy1", x=15, y=15)
        all_units = _build_units(pd, ally, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "inoculate"
        assert result.target_id == "ally1"

    def test_skips_inoculate_ally_out_of_range(self):
        """Inoculate skipped when ally with DoT is beyond range 3."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={
            "enfeeble": 5, "miasma": 5, "plague_flask": 5,
        })
        dot = {"buff_id": "wither", "type": "dot", "damage_per_tick": 8, "turns_remaining": 3}
        ally = _make_ally(player_id="ally1", x=10, y=5, active_buffs=[dot])  # dist 5
        enemy = _make_enemy(player_id="enemy1", x=15, y=15)
        all_units = _build_units(pd, ally, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "inoculate"

    def test_skips_inoculate_ally_healthy(self):
        """Inoculate skipped when all allies are healthy and have no DoTs."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={
            "enfeeble": 5, "miasma": 5, "plague_flask": 5,
        })
        ally = _make_ally(player_id="ally1", x=6, y=5, hp=150, max_hp=150)
        enemy = _make_enemy(player_id="enemy1", x=15, y=15)
        all_units = _build_units(pd, ally, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # No ally with DoT, no injured ally → inoculate should not fire
        assert result is None

    def test_inoculate_on_cooldown(self):
        """Inoculate on cooldown → skipped."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={
            "enfeeble": 5, "miasma": 5, "plague_flask": 5, "inoculate": 3,
        })
        dot = {"buff_id": "wither", "type": "dot", "damage_per_tick": 8, "turns_remaining": 3}
        ally = _make_ally(player_id="ally1", x=6, y=5, active_buffs=[dot])
        enemy = _make_enemy(player_id="enemy1", x=15, y=15)
        all_units = _build_units(pd, ally, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None

    def test_inoculate_prefers_dot_over_injured(self):
        """Ally with DoT takes priority over injured ally without DoT."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={
            "enfeeble": 5, "miasma": 5, "plague_flask": 5,
        })
        dot = {"buff_id": "wither", "type": "dot", "damage_per_tick": 8, "turns_remaining": 3}
        ally_with_dot = _make_ally(player_id="ally_dot", x=6, y=5, hp=100, max_hp=150,
                                    active_buffs=[dot])  # Has DoT, 67% HP
        ally_injured = _make_ally(player_id="ally_hurt", x=5, y=6, hp=40, max_hp=150)  # 27% HP, no DoT
        enemy = _make_enemy(player_id="enemy1", x=15, y=15)
        all_units = _build_units(pd, ally_with_dot, ally_injured, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "inoculate"
        assert result.target_id == "ally_dot"


# ===========================================================================
# 6. Fallback — All Skills on Cooldown
# ===========================================================================

class TestFallback:
    """When all skills are on cooldown, AI returns None (fall through to auto-attack)."""

    def test_returns_none_all_skills_on_cooldown(self):
        """All 4 skills on cooldown → returns None."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={
            "enfeeble": 4, "miasma": 3, "plague_flask": 3, "inoculate": 3,
        })
        ally = _make_ally(player_id="ally1", x=6, y=5)
        enemy = _make_enemy(player_id="enemy1", x=8, y=5)
        all_units = _build_units(pd, ally, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None

    def test_returns_none_no_enemies_no_allies(self):
        """No enemies and no allies → returns None."""
        pd = _make_plague_doctor(x=5, y=5)
        all_units = _build_units(pd)

        result = _controller_skill_logic(
            pd, [], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None


# ===========================================================================
# 7. Dispatcher Integration
# ===========================================================================

class TestDispatcher:
    """_decide_skill_usage dispatches plague_doctor to controller handler."""

    def test_dispatcher_routes_plague_doctor_to_controller(self):
        """_decide_skill_usage correctly routes plague_doctor class to controller handler."""
        pd = _make_plague_doctor(x=5, y=5)
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)
        all_units = _build_units(pd, enemy1, enemy2)

        result = _decide_skill_usage(
            pd, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should return a skill action (Plague Flask as highest priority)
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "plague_flask"

    def test_dispatcher_returns_none_when_no_skills_usable(self):
        """Plague Doctor with all skills on CD → returns None through dispatcher."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={
            "enfeeble": 4, "miasma": 3, "plague_flask": 3, "inoculate": 3,
        })
        enemy = _make_enemy(player_id="enemy1", x=8, y=5)
        all_units = _build_units(pd, enemy)

        result = _decide_skill_usage(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None


# ===========================================================================
# 8. Priority Order
# ===========================================================================

class TestPriorityOrder:
    """Skills are used in the correct priority order."""

    def test_plague_flask_over_enfeeble(self):
        """Plague Flask takes priority over Enfeeble when both conditions are met."""
        pd = _make_plague_doctor(x=5, y=5)
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)
        all_units = _build_units(pd, enemy1, enemy2)

        result = _controller_skill_logic(
            pd, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "plague_flask"  # Highest priority

    def test_enfeeble_over_miasma(self):
        """Enfeeble takes priority over Miasma when plague_flask is on CD."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"plague_flask": 3})
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)
        all_units = _build_units(pd, enemy1, enemy2)

        result = _controller_skill_logic(
            pd, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "enfeeble"  # Higher priority than miasma

    def test_miasma_when_enfeeble_on_cd(self):
        """Miasma fires when Plague Flask + Enfeeble are on cooldown and enemies are clustered."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 5, "plague_flask": 3})
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)
        all_units = _build_units(pd, enemy1, enemy2)

        result = _controller_skill_logic(
            pd, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "miasma"

    def test_plague_flask_when_enfeeble_and_miasma_on_cd(self):
        """Plague Flask fires when Enfeeble & Miasma are on CD (but flask is off CD)."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 5, "miasma": 5})
        enemy = _make_enemy(player_id="enemy1", x=8, y=5)
        all_units = _build_units(pd, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "plague_flask"

    def test_inoculate_last_resort(self):
        """Inoculate fires only when higher-priority skills aren't usable."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={
            "enfeeble": 5, "miasma": 5, "plague_flask": 5,
        })
        dot = {"buff_id": "wither", "type": "dot", "damage_per_tick": 8, "turns_remaining": 3}
        ally = _make_ally(player_id="ally1", x=6, y=5, active_buffs=[dot])
        enemy = _make_enemy(player_id="enemy1", x=15, y=15)
        all_units = _build_units(pd, ally, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "inoculate"


# ===========================================================================
# 9. Positioning — Support Move Preference
# ===========================================================================

class TestPositioning:
    """Controller (Plague Doctor) uses support move preference — stays near allies."""

    def test_support_move_preference_returns_injured_ally(self):
        """_support_move_preference returns most injured ally's position for PD."""
        pd = _make_plague_doctor(x=5, y=5)
        ally = _make_ally(player_id="ally1", x=10, y=10, hp=50, max_hp=150)  # injured
        all_units = _build_units(pd, ally)

        result = _support_move_preference(pd, all_units)
        assert result is not None
        assert result == (10, 10)  # Move toward injured ally

    def test_support_move_preference_nearest_ally_when_healthy(self):
        """When all allies are healthy, move toward nearest ally to stay grouped."""
        pd = _make_plague_doctor(x=5, y=5)
        ally1 = _make_ally(player_id="ally1", x=8, y=5, hp=150, max_hp=150)  # dist 3
        ally2 = _make_ally(player_id="ally2", x=12, y=5, hp=150, max_hp=150)  # dist 7
        all_units = _build_units(pd, ally1, ally2)

        result = _support_move_preference(pd, all_units)
        assert result is not None
        assert result == (8, 5)  # Nearest ally

    def test_support_move_preference_no_allies(self):
        """No allies alive → returns None (fall through to default movement)."""
        pd = _make_plague_doctor(x=5, y=5)
        all_units = _build_units(pd)

        result = _support_move_preference(pd, all_units)
        assert result is None
