"""
Tests for Phase 8E-1 — Ranged DPS Role AI (Ranger: Power Shot).

Covers:
  8E-1: _ranged_dps_skill_logic() — Power Shot decision
    - Ranger uses Power Shot when enemy in range + LOS + off cooldown
    - Ranger falls through to basic ranged when Power Shot on cooldown
    - Ranger Power Shot requires line of sight (blocked by obstacles)
    - Ranger Power Shot picks best target among multiple enemies in range
    - Ranger Power Shot falls back to secondary target when best is out of range
    - Ranger with no enemies visible returns None
    - Ranger Power Shot uses class ranged_range (6 tiles for Ranger)

  Integration:
    - Ranger dispatches through _decide_skill_usage to ranged_dps logic
    - Inquisitor also gets ranged_dps dispatch (shared Power Shot skill)

  Guard:
    - Enemy AI (no hero_id) does not use ranged DPS skill logic
    - Non-ranged-DPS class does not trigger ranged DPS skill logic
    - Melee-only class (Crusader) does not use Power Shot
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.ai_behavior import (
    _ranged_dps_skill_logic,
    _decide_skill_usage,
    _get_role_for_class,
)
from app.core.combat import load_combat_config
from app.core.skills import load_skills_config


def setup_module():
    """Ensure configs are loaded before any test runs."""
    load_combat_config()
    load_skills_config()


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

def make_ranger(pid="ranger1", username="Ranger Kael", x=5, y=5,
                hp=80, max_hp=80, team="a", ai_stance="follow",
                cooldowns=None, active_buffs=None,
                hero_id="hero_ranger") -> PlayerState:
    """Create a Ranger hero AI unit (Ranged DPS role)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=8,
        ranged_damage=18,
        armor=2,
        team=team,
        unit_type="ai",
        hero_id=hero_id,
        ai_stance=ai_stance,
        class_id="ranger",
        ranged_range=6,
        vision_range=7,
        inventory=[],
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
    )


def make_enemy(pid="enemy1", username="Demon", x=9, y=5,
               hp=80, max_hp=80, team="b") -> PlayerState:
    """Create an enemy AI unit (NOT a hero)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=10,
        armor=0,
        team=team,
        unit_type="ai",
        hero_id=None,
        ranged_range=0,
        vision_range=5,
        inventory=[],
    )


def make_crusader(pid="crusader1", username="Ser Aldric", x=5, y=5,
                  hp=150, max_hp=150, team="a",
                  hero_id="hero_crus") -> PlayerState:
    """Create a Crusader hero AI unit (Tank role — cannot use Power Shot)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=20,
        armor=8,
        team=team,
        unit_type="ai",
        hero_id=hero_id,
        ai_stance="follow",
        class_id="crusader",
        ranged_range=1,
        vision_range=5,
        inventory=[],
        cooldowns={},
        active_buffs=[],
    )


# ============================================================================
# 1. _ranged_dps_skill_logic() Tests — Power Shot (8E-1)
# ============================================================================


class TestRangedDpsSkillLogicPowerShot:
    """Tests for Power Shot usage by Ranged DPS role AI."""

    def test_ranger_power_shot_when_available(self):
        """Enemy in range + LOS + off CD → uses Crippling Shot (higher priority than Power Shot)."""
        ranger = make_ranger()
        enemy = make_enemy(x=9, y=5)  # 4 tiles away, within range 6
        all_units = {ranger.player_id: ranger, enemy.player_id: enemy}
        enemies = [enemy]

        result = _ranged_dps_skill_logic(ranger, enemies, all_units, set())

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "crippling_shot"
        assert result.target_x == 9
        assert result.target_y == 5

    def test_ranger_basic_ranged_when_all_skills_on_cd(self):
        """Enemy in range + all ranged skills on CD → returns None (falls through)."""
        ranger = make_ranger(cooldowns={"power_shot": 3, "crippling_shot": 3, "volley": 3, "evasion": 3})
        enemy = make_enemy(x=9, y=5)
        all_units = {ranger.player_id: ranger, enemy.player_id: enemy}
        enemies = [enemy]

        result = _ranged_dps_skill_logic(ranger, enemies, all_units, set())

        assert result is None  # Falls through to basic ranged attack logic

    def test_ranger_power_shot_requires_los(self):
        """Enemy in range but obstacle blocks LOS → doesn't use Power Shot."""
        ranger = make_ranger()
        enemy = make_enemy(x=9, y=5)
        all_units = {ranger.player_id: ranger, enemy.player_id: enemy}
        enemies = [enemy]
        # Wall between ranger (5,5) and enemy (9,5) at (7,5)
        obstacles = {(7, 5)}

        result = _ranged_dps_skill_logic(ranger, enemies, all_units, obstacles)

        assert result is None  # No LOS → can't use Power Shot

    def test_ranger_power_shot_target_selection(self):
        """Multiple enemies in range, volley+crippling on CD → Power Shot picks lowest HP."""
        ranger = make_ranger(cooldowns={"volley": 3, "crippling_shot": 3})
        enemy_full = make_enemy(pid="enemy_full", x=9, y=5, hp=80, max_hp=80)
        enemy_low = make_enemy(pid="enemy_low", x=8, y=5, hp=20, max_hp=80)
        all_units = {
            ranger.player_id: ranger,
            enemy_full.player_id: enemy_full,
            enemy_low.player_id: enemy_low,
        }
        enemies = [enemy_full, enemy_low]

        result = _ranged_dps_skill_logic(ranger, enemies, all_units, set())

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "power_shot"
        # Should target the low-HP enemy
        assert result.target_x == 8
        assert result.target_y == 5

    def test_ranger_power_shot_out_of_range(self):
        """Enemy beyond ranged range (6) → doesn't use Power Shot."""
        ranger = make_ranger()
        # Enemy at (12, 5): distance = 7, beyond ranged_range=6
        enemy = make_enemy(x=12, y=5)
        all_units = {ranger.player_id: ranger, enemy.player_id: enemy}
        enemies = [enemy]

        result = _ranged_dps_skill_logic(ranger, enemies, all_units, set())

        assert result is None

    def test_ranger_no_enemies_returns_none(self):
        """No enemies visible → returns None."""
        ranger = make_ranger()
        all_units = {ranger.player_id: ranger}
        enemies = []

        result = _ranged_dps_skill_logic(ranger, enemies, all_units, set())

        assert result is None

    def test_ranger_crippling_shot_adjacent_enemy(self):
        """Crippling Shot works even on adjacent enemies (range includes adjacent)."""
        ranger = make_ranger()
        enemy = make_enemy(x=6, y=5)  # Adjacent (1 tile away)
        all_units = {ranger.player_id: ranger, enemy.player_id: enemy}
        enemies = [enemy]

        result = _ranged_dps_skill_logic(ranger, enemies, all_units, set())

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "crippling_shot"
        assert result.target_x == 6
        assert result.target_y == 5

    def test_ranger_crippling_shot_max_range(self):
        """Enemy at exactly max range (6 tiles) → uses Crippling Shot (priority over PS)."""
        ranger = make_ranger(x=0, y=0)
        enemy = make_enemy(x=6, y=0)  # Exactly 6 tiles away
        all_units = {ranger.player_id: ranger, enemy.player_id: enemy}
        enemies = [enemy]

        result = _ranged_dps_skill_logic(ranger, enemies, all_units, set())

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "crippling_shot"

    def test_ranger_fallback_to_secondary_target(self):
        """Best target out of LOS, but secondary target has LOS → uses Crippling Shot on secondary."""
        ranger = make_ranger()
        # Best target (low HP) blocked by wall
        enemy_low = make_enemy(pid="enemy_low", x=9, y=5, hp=20, max_hp=80)
        # Secondary target (full HP) has clear LOS
        enemy_full = make_enemy(pid="enemy_full", x=8, y=8, hp=80, max_hp=80)
        all_units = {
            ranger.player_id: ranger,
            enemy_low.player_id: enemy_low,
            enemy_full.player_id: enemy_full,
        }
        enemies = [enemy_low, enemy_full]
        # Wall blocks LOS to low-HP enemy
        obstacles = {(7, 5)}

        result = _ranged_dps_skill_logic(ranger, enemies, all_units, obstacles)

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "crippling_shot"
        # Should target the secondary enemy (has LOS)
        assert result.target_x == 8
        assert result.target_y == 8

    def test_ranger_all_enemies_blocked(self):
        """All enemies blocked by obstacles → returns None."""
        ranger = make_ranger()
        enemy1 = make_enemy(pid="e1", x=9, y=5, hp=80, max_hp=80)
        enemy2 = make_enemy(pid="e2", x=5, y=9, hp=80, max_hp=80)
        all_units = {
            ranger.player_id: ranger,
            enemy1.player_id: enemy1,
            enemy2.player_id: enemy2,
        }
        enemies = [enemy1, enemy2]
        # Walls block both enemies
        obstacles = {(7, 5), (5, 7)}

        result = _ranged_dps_skill_logic(ranger, enemies, all_units, obstacles)

        assert result is None


# ============================================================================
# 2. Integration — _decide_skill_usage() dispatch (8E-1)
# ============================================================================


class TestRangedDpsDispatch:
    """Tests for ranged DPS role dispatch through _decide_skill_usage."""

    def test_ranger_dispatches_to_ranged_dps(self):
        """Ranger class dispatches to ranged_dps role handler."""
        assert _get_role_for_class("ranger") == "ranged_dps"

    def test_ranger_skill_usage_crippling_shot(self):
        """Ranger dispatches through _decide_skill_usage and gets Crippling Shot."""
        ranger = make_ranger()
        enemy = make_enemy(x=9, y=5)
        all_units = {ranger.player_id: ranger, enemy.player_id: enemy}
        enemies = [enemy]

        result = _decide_skill_usage(
            ranger, enemies, all_units,
            grid_width=20, grid_height=20,
            obstacles=set(),
        )

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "crippling_shot"

    def test_ranger_skill_usage_all_on_cd_returns_none(self):
        """Ranger with all ranged skills on CD → _decide_skill_usage returns None."""
        ranger = make_ranger(cooldowns={"power_shot": 3, "crippling_shot": 3, "volley": 3, "evasion": 3})
        enemy = make_enemy(x=9, y=5)
        all_units = {ranger.player_id: ranger, enemy.player_id: enemy}
        enemies = [enemy]

        result = _decide_skill_usage(
            ranger, enemies, all_units,
            grid_width=20, grid_height=20,
            obstacles=set(),
        )

        assert result is None


# ============================================================================
# 3. Guard Tests — Exclusion & Regression (8E-1)
# ============================================================================


class TestRangedDpsGuard:
    """Guard tests ensuring non-ranged-DPS classes are unaffected."""

    def test_enemy_ai_no_ranged_dps_skills(self):
        """Enemy AI (hero_id=None) cannot use Power Shot even if class matches."""
        # Enemy AI never goes through _decide_skill_usage (hero_id check upstream)
        # But even if called directly, wrong class should block it
        enemy = make_enemy()
        enemy_target = make_enemy(pid="et", x=12, y=5, team="a")
        all_units = {enemy.player_id: enemy, enemy_target.player_id: enemy_target}
        enemies = [enemy_target]

        # Enemy has no class → _try_skill will fail (no allowed_classes match)
        result = _ranged_dps_skill_logic(enemy, enemies, all_units, set())
        assert result is None

    def test_crusader_no_power_shot(self):
        """Crusader (Tank role) does not use Power Shot."""
        crusader = make_crusader()
        enemy = make_enemy(x=9, y=5)
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}
        enemies = [enemy]

        # Direct call — Crusader is wrong class for power_shot
        result = _ranged_dps_skill_logic(crusader, enemies, all_units, set())
        assert result is None

    def test_crusader_dispatches_to_tank_not_ranged(self):
        """Crusader dispatches to tank role, not ranged_dps."""
        assert _get_role_for_class("crusader") == "tank"

    def test_null_class_no_crash(self):
        """class_id=None → _decide_skill_usage returns None, no crash."""
        unit = PlayerState(
            player_id="legacy1",
            username="Legacy",
            position=Position(x=5, y=5),
            hp=80,
            max_hp=80,
            attack_damage=10,
            armor=0,
            team="a",
            unit_type="ai",
            class_id=None,
            ranged_range=5,
            vision_range=5,
            inventory=[],
        )
        enemy = make_enemy(x=9, y=5)
        all_units = {unit.player_id: unit, enemy.player_id: enemy}
        enemies = [enemy]

        result = _decide_skill_usage(
            unit, enemies, all_units,
            grid_width=20, grid_height=20,
            obstacles=set(),
        )
        assert result is None
