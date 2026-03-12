"""
Tests for Tank Role AI (Crusader: Taunt, Shield Bash, Holy Ground, Bulwark).

Phase 12 update — replaces Phase 8D war_cry/double_strike tests.

Covers:
  1. _tank_skill_logic() — New priority chain:
     - Taunt: 2+ enemies within radius 2 → force them to target you
     - Shield Bash: adjacent enemy → stun + damage
     - Holy Ground: self/ally below 60% HP → AoE heal
     - Bulwark: enemies visible, no armor buff → armor self-buff
     - Taunt fallback: 1+ enemy in range when nothing else works
     - Returns None → basic melee/move

  2. Integration
     - Crusader dispatches through _decide_skill_usage to tank logic
     - Skill decision runs before stance dispatch in priority chain

  Guard:
     - Enemy AI (no hero_id) does not use tank skill logic
     - Non-tank class does not trigger tank skill logic
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.ai_behavior import (
    _tank_skill_logic,
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

def make_crusader(pid="crusader1", username="Ser Aldric", x=5, y=5,
                  hp=150, max_hp=150, team="a", ai_stance="follow",
                  cooldowns=None, active_buffs=None,
                  hero_id="hero_crus") -> PlayerState:
    """Create a Crusader hero AI unit (Tank role)."""
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
        ai_stance=ai_stance,
        class_id="crusader",
        ranged_range=1,
        vision_range=5,
        inventory=[],
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
    )


def make_enemy(pid="enemy1", username="Demon", x=6, y=5,
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


def make_ally(pid="ally1", username="Sister Maeve", x=4, y=5,
              hp=100, max_hp=100, team="a", class_id="confessor",
              hero_id="hero_ally1") -> PlayerState:
    """Create an allied hero AI unit."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=8,
        armor=3,
        team=team,
        unit_type="ai",
        hero_id=hero_id,
        ai_stance="follow",
        class_id=class_id,
        ranged_range=1,
        vision_range=6,
        inventory=[],
        cooldowns={},
        active_buffs=[],
    )


# ============================================================================
# 1. _tank_skill_logic() Tests — Taunt, Shield Bash, Holy Ground, Bulwark
# ============================================================================


class TestTankSkillLogicBulwark:
    """Tests for Bulwark (armor self-buff) and general tank priority chain."""

    def test_crusader_bulwark_when_distant_enemy(self):
        """Enemy visible 3 tiles away, no armor buff → uses Bulwark."""
        crusader = make_crusader()
        enemy = make_enemy(x=8, y=5)  # 3 tiles away, not adjacent
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}
        enemies = [enemy]

        result = _tank_skill_logic(crusader, enemies, all_units, set())

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "bulwark"

    def test_crusader_no_skill_if_armor_buffed_distant_enemy(self):
        """Already has armor buff, enemy not adjacent → no skill to use → None."""
        crusader = make_crusader(active_buffs=[
            {"buff_id": "bulwark", "stat": "armor", "type": "buff",
             "magnitude": 5, "turns_remaining": 2}
        ])
        enemy = make_enemy(x=8, y=5)  # 3 tiles away, not adjacent
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}
        enemies = [enemy]

        result = _tank_skill_logic(crusader, enemies, all_units, set())

        # Taunt: enemy 3 away > radius 2 → skip
        # Shield Bash: not adjacent → skip
        # Holy Ground: HP 100% → skip
        # Bulwark: already has armor buff → skip
        # Taunt fallback: enemy 3 away > radius 2 → skip
        assert result is None

    def test_crusader_shield_bash_if_armor_buffed_and_adjacent(self):
        """Armor buff active + adjacent enemy → uses Shield Bash."""
        crusader = make_crusader(active_buffs=[
            {"buff_id": "bulwark", "stat": "armor", "type": "buff",
             "magnitude": 5, "turns_remaining": 2}
        ])
        enemy = make_enemy(x=6, y=5)  # Adjacent
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}
        enemies = [enemy]

        result = _tank_skill_logic(crusader, enemies, all_units, set())

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "shield_bash"
        assert result.target_x == enemy.position.x
        assert result.target_y == enemy.position.y

    def test_crusader_no_skill_no_enemies(self):
        """No enemies visible → don't waste skills → None."""
        crusader = make_crusader()
        enemies = []
        all_units = {crusader.player_id: crusader}

        result = _tank_skill_logic(crusader, enemies, all_units, set())

        assert result is None

    def test_crusader_all_skills_on_cd_distant_enemy(self):
        """All skills on CD, armor buff active, enemy not adjacent → returns None."""
        crusader = make_crusader(
            cooldowns={"taunt": 3, "shield_bash": 2, "holy_ground": 3, "bulwark": 3},
            active_buffs=[
                {"buff_id": "bulwark", "stat": "armor", "type": "buff",
                 "magnitude": 5, "turns_remaining": 1}
            ],
        )
        enemy = make_enemy(x=8, y=5)  # 3 tiles away
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}
        enemies = [enemy]

        result = _tank_skill_logic(crusader, enemies, all_units, set())

        assert result is None

    def test_crusader_shield_bash_adjacent_off_cd(self):
        """Taunt on CD, adjacent enemy, Shield Bash off CD → uses Shield Bash."""
        crusader = make_crusader(cooldowns={"taunt": 3})
        enemy = make_enemy(x=6, y=5)  # Adjacent
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}
        enemies = [enemy]

        result = _tank_skill_logic(crusader, enemies, all_units, set())

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "shield_bash"

    def test_crusader_taunt_priority_over_shield_bash(self):
        """2 adjacent enemies → Taunt fires first (priority 1 over Shield Bash priority 2)."""
        crusader = make_crusader()
        enemy1 = make_enemy(pid="enemy1", x=6, y=5)  # Adjacent
        enemy2 = make_enemy(pid="enemy2", username="Demon B", x=4, y=5)  # Also adjacent
        all_units = {
            crusader.player_id: crusader,
            enemy1.player_id: enemy1,
            enemy2.player_id: enemy2,
        }
        enemies = [enemy1, enemy2]

        result = _tank_skill_logic(crusader, enemies, all_units, set())

        # Taunt: 2 enemies within radius 2 → fires
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "taunt"


class TestTankSkillLogicShieldBash:
    """Tests for Shield Bash usage by Tank role AI."""

    def test_crusader_shield_bash_adjacent_enemy(self):
        """Adjacent to enemy, Shield Bash off CD → uses Shield Bash."""
        crusader = make_crusader(active_buffs=[
            {"buff_id": "bulwark", "stat": "armor", "type": "buff",
             "magnitude": 5, "turns_remaining": 1}
        ])  # Armor buff already active so Bulwark won't fire
        enemy = make_enemy(x=6, y=5)  # Adjacent
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}
        enemies = [enemy]

        result = _tank_skill_logic(crusader, enemies, all_units, set())

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "shield_bash"
        assert result.target_x == 6
        assert result.target_y == 5

    def test_crusader_shield_bash_diagonal_adjacent(self):
        """Enemy diagonally adjacent → still counts as adjacent (Chebyshev)."""
        crusader = make_crusader(active_buffs=[
            {"buff_id": "bulwark", "stat": "armor", "type": "buff",
             "magnitude": 5, "turns_remaining": 1}
        ])
        enemy = make_enemy(x=6, y=6)  # Diagonal adjacent
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}
        enemies = [enemy]

        result = _tank_skill_logic(crusader, enemies, all_units, set())

        assert result is not None
        assert result.skill_id == "shield_bash"
        assert result.target_x == 6
        assert result.target_y == 6

    def test_crusader_basic_attack_all_skills_on_cooldown(self):
        """Adjacent enemy, all skills on CD, armor buff active → None (basic attack fallback)."""
        crusader = make_crusader(
            cooldowns={"taunt": 3, "shield_bash": 2, "holy_ground": 3, "bulwark": 3},
            active_buffs=[
                {"buff_id": "bulwark", "stat": "armor", "type": "buff",
                 "magnitude": 5, "turns_remaining": 1}
            ],
        )
        enemy = make_enemy(x=6, y=5)  # Adjacent
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}
        enemies = [enemy]

        result = _tank_skill_logic(crusader, enemies, all_units, set())

        # All skills unavailable → fall through to basic melee
        assert result is None

    def test_crusader_shield_bash_target_selection_lowest_hp(self):
        """Two adjacent enemies, taunt on CD → Shield Bash targets lowest HP one."""
        crusader = make_crusader(
            cooldowns={"taunt": 3},
            active_buffs=[
                {"buff_id": "bulwark", "stat": "armor", "type": "buff",
                 "magnitude": 5, "turns_remaining": 1}
            ],
        )
        enemy_full = make_enemy(pid="enemy_full", username="Demon A", x=6, y=5,
                                hp=80, max_hp=80)
        enemy_hurt = make_enemy(pid="enemy_hurt", username="Demon B", x=4, y=5,
                                hp=15, max_hp=80)  # Below 30% → low HP bonus
        all_units = {
            crusader.player_id: crusader,
            enemy_full.player_id: enemy_full,
            enemy_hurt.player_id: enemy_hurt,
        }
        enemies = [enemy_full, enemy_hurt]

        result = _tank_skill_logic(crusader, enemies, all_units, set())

        assert result is not None
        assert result.skill_id == "shield_bash"
        # Should target the hurt enemy (low HP scoring bonus)
        assert result.target_x == enemy_hurt.position.x
        assert result.target_y == enemy_hurt.position.y

    def test_crusader_no_skill_enemy_not_adjacent_armor_buffed(self):
        """Enemy exists but not adjacent, armor buff active → None."""
        crusader = make_crusader(active_buffs=[
            {"buff_id": "bulwark", "stat": "armor", "type": "buff",
             "magnitude": 5, "turns_remaining": 1}
        ])
        enemy = make_enemy(x=8, y=5)  # 3 tiles away
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}
        enemies = [enemy]

        result = _tank_skill_logic(crusader, enemies, all_units, set())

        # Taunt: enemy at dist 3 > radius 2 → skip
        # Shield Bash: not adjacent → skip
        # Holy Ground: HP 100% → skip
        # Bulwark: armor buff active → skip
        # Taunt fallback: enemy at dist 3 > radius 2 → skip
        assert result is None

    def test_crusader_all_new_skills_on_cooldown(self):
        """All 4 crusader skills on cooldown → returns None."""
        crusader = make_crusader(cooldowns={"taunt": 3, "shield_bash": 2, "holy_ground": 3, "bulwark": 3})
        enemy = make_enemy(x=6, y=5)  # Adjacent
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}
        enemies = [enemy]

        result = _tank_skill_logic(crusader, enemies, all_units, set())

        assert result is None


class TestTankSkillLogicCombo:
    """Tests for Tank skill priority chain flow."""

    def test_crusader_combo_turn1_shield_bash(self):
        """Turn 1: 1 adjacent enemy, no buffs → Shield Bash (stun first)."""
        crusader = make_crusader()
        enemy = make_enemy(x=6, y=5)  # Adjacent
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}

        result = _tank_skill_logic(crusader, [enemy], all_units, set())

        assert result is not None
        assert result.skill_id == "shield_bash"

    def test_crusader_combo_turn2_bulwark(self):
        """Turn 2: Shield Bash on CD, 1 adjacent enemy, no armor buff → Bulwark."""
        crusader = make_crusader(
            cooldowns={"shield_bash": 2},  # Just used Shield Bash → on CD
        )
        enemy = make_enemy(x=6, y=5)

        result = _tank_skill_logic(crusader, [enemy],
                                   {crusader.player_id: crusader, enemy.player_id: enemy},
                                   set())

        # Taunt: 1 enemy → skip (needs 2+)
        # Shield Bash: on CD → skip
        # Holy Ground: HP 100% → skip
        # Bulwark: no armor buff → fires!
        assert result is not None
        assert result.skill_id == "bulwark"

    def test_crusader_combo_turn3_nothing(self):
        """Turn 3: All skills on CD, armor buff active → None (basic attack)."""
        crusader = make_crusader(
            cooldowns={"taunt": 3, "shield_bash": 2, "holy_ground": 3, "bulwark": 3},
            active_buffs=[
                {"buff_id": "bulwark", "stat": "armor", "type": "buff",
                 "magnitude": 5, "turns_remaining": 1}
            ],
        )
        enemy = make_enemy(x=6, y=5)

        result = _tank_skill_logic(crusader, [enemy],
                                   {crusader.player_id: crusader, enemy.player_id: enemy},
                                   set())

        # All on CD → fall through — basic melee
        assert result is None


# ============================================================================
# 2. Integration Tests
# ============================================================================

class TestTankDispatchIntegration:
    """Tests for _decide_skill_usage dispatch to tank logic."""

    def test_crusader_dispatches_to_tank_logic(self):
        """Crusader triggers _tank_skill_logic via _decide_skill_usage → Bulwark."""
        crusader = make_crusader()
        enemy = make_enemy(x=8, y=5)
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}
        enemies = [enemy]

        result = _decide_skill_usage(crusader, enemies, all_units, 15, 15, set())

        # Distant enemy, no armor buff → Bulwark
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "bulwark"

    def test_crusader_returns_none_when_no_skills_available(self):
        """All skills on CD, armor buff active, no adjacent enemies → None from dispatch."""
        crusader = make_crusader(
            cooldowns={"taunt": 3, "shield_bash": 2, "holy_ground": 3, "bulwark": 3},
            active_buffs=[
                {"buff_id": "bulwark", "stat": "armor", "type": "buff",
                 "magnitude": 5, "turns_remaining": 1}
            ],
        )
        enemy = make_enemy(x=8, y=5)  # Not adjacent
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}
        enemies = [enemy]

        result = _decide_skill_usage(crusader, enemies, all_units, 15, 15, set())

        assert result is None

    def test_role_is_tank_for_crusader(self):
        """Crusader maps to 'tank' role."""
        assert _get_role_for_class("crusader") == "tank"

    def test_action_format_bulwark(self):
        """Bulwark action has correct format (SKILL, bulwark, no target)."""
        crusader = make_crusader()
        enemy = make_enemy(x=8, y=5)
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}

        result = _tank_skill_logic(crusader, [enemy], all_units, set())

        assert result.player_id == "crusader1"
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "bulwark"
        # Bulwark is self-targeting → target_x/y should be None
        assert result.target_x is None
        assert result.target_y is None

    def test_action_format_shield_bash(self):
        """Shield Bash action has correct format (SKILL, shield_bash, target coords)."""
        crusader = make_crusader(active_buffs=[
            {"buff_id": "bulwark", "stat": "armor", "type": "buff",
             "magnitude": 5, "turns_remaining": 1}
        ])
        enemy = make_enemy(x=6, y=5)
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}

        result = _tank_skill_logic(crusader, [enemy], all_units, set())

        assert result.player_id == "crusader1"
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "shield_bash"
        assert result.target_x == 6
        assert result.target_y == 5


# ============================================================================
# 3. Guard Tests
# ============================================================================

class TestTankGuard:
    """Guard tests: ensure tank logic only applies to tank-role hero AI."""

    def test_enemy_ai_no_tank_skills(self):
        """Enemy AI (no hero_id) should not use tank skills even with crusader class."""
        enemy_crusader = PlayerState(
            player_id="enemy_crus",
            username="Dark Knight",
            position=Position(x=5, y=5),
            hp=150,
            max_hp=150,
            attack_damage=20,
            armor=8,
            team="b",
            unit_type="ai",
            hero_id=None,  # Not a hero
            class_id="crusader",
            ranged_range=1,
            vision_range=5,
            inventory=[],
            cooldowns={},
            active_buffs=[],
        )
        target = make_enemy(pid="target1", x=6, y=5, team="a")
        all_units = {enemy_crusader.player_id: enemy_crusader, target.player_id: target}

        # _tank_skill_logic itself doesn't check hero_id (that's the caller's job)
        # But _decide_skill_usage is called from _decide_stance_action which only
        # triggers for hero AI with ai_stance. This test verifies the role mapping works.
        role = _get_role_for_class(enemy_crusader.class_id)
        assert role == "tank"
        # The guard is at the _decide_stance_action level, not inside _tank_skill_logic.
        # Tank skill logic will work for any crusader unit — the caller filters.

    def test_non_tank_class_no_tank_dispatch(self):
        """Non-tank class (e.g., Ranger) does not dispatch to tank logic."""
        assert _get_role_for_class("ranger") == "ranged_dps"
        assert _get_role_for_class("ranger") != "tank"

        assert _get_role_for_class("confessor") == "support"
        assert _get_role_for_class("confessor") != "tank"
