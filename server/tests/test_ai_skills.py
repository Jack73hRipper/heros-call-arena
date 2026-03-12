"""
Tests for Phase 8B — AI Skill Decision Framework.

Covers:
  - Role mapping: all 5 classes map to a valid role
  - Role mapping: unknown class_id returns None
  - Skill dispatch: each class dispatches to the correct role handler
  - _try_skill: skill on cooldown returns None
  - _try_skill: wrong class for skill returns None
  - _try_skill: valid skill + off cooldown returns SKILL action
  - Null class_id: returns None, no crash
"""

from unittest.mock import patch

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.ai_behavior import (
    _CLASS_ROLE_MAP,
    _get_role_for_class,
    _try_skill,
    _decide_skill_usage,
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

def make_hero(pid="hero1", username="Ser Aldric", x=5, y=5, hp=100, max_hp=100,
              team="a", ai_stance="follow", class_id="crusader",
              inventory=None, hero_id="hero_001",
              cooldowns=None, active_buffs=None) -> PlayerState:
    """Create a hero ally AI unit."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=15,
        armor=2,
        team=team,
        unit_type="ai",
        hero_id=hero_id,
        ai_stance=ai_stance,
        class_id=class_id,
        ranged_range=5,
        vision_range=7,
        inventory=inventory or [],
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
    )


def make_enemy(pid="enemy1", username="Demon", x=8, y=5, hp=80, max_hp=80,
               team="b") -> PlayerState:
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


# ---------------------------------------------------------------------------
# 1. Role Mapping Tests (_CLASS_ROLE_MAP, _get_role_for_class)
# ---------------------------------------------------------------------------

class TestRoleMapping:
    """Tests for the class → role mapping registry (8B-2)."""

    def test_role_mapping_all_classes(self):
        """All 5 classes map to a valid role."""
        expected = {
            "crusader": "tank",
            "confessor": "support",
            "inquisitor": "scout",
            "ranger": "ranged_dps",
            "hexblade": "hybrid_dps",
        }
        for class_id, expected_role in expected.items():
            role = _get_role_for_class(class_id)
            assert role == expected_role, f"{class_id} should map to {expected_role}, got {role}"

    def test_role_mapping_unknown_class(self):
        """Unknown class_id returns None — no crash, no skill logic."""
        assert _get_role_for_class("paladin") is None
        assert _get_role_for_class("druid") is None
        assert _get_role_for_class("") is None

    def test_role_map_is_complete(self):
        """_CLASS_ROLE_MAP has entries for all hero and enemy classes."""
        assert len(_CLASS_ROLE_MAP) == 31  # 11 hero + 17 enemy + 3 Phase-18I identity classes

    def test_all_roles_are_recognized_strings(self):
        """Every role value in the map is a known role string."""
        known_roles = {"tank", "support", "scout", "ranged_dps", "hybrid_dps", "caster_dps", "passive_only", "offensive_support", "sustain_dps", "controller", "retaliation_tank", "totemic_support"}
        for class_id, role in _CLASS_ROLE_MAP.items():
            assert role in known_roles, f"Unknown role '{role}' for class '{class_id}'"


# ---------------------------------------------------------------------------
# 2. _try_skill() Tests (Core Validation Helper — 8B-3)
# ---------------------------------------------------------------------------

class TestTrySkill:
    """Tests for the _try_skill() convenience helper."""

    def test_try_skill_success(self):
        """Valid skill + off cooldown → returns SKILL action with correct fields."""
        hero = make_hero(class_id="crusader", cooldowns={})
        action = _try_skill(hero, "shield_bash", target_x=6, target_y=5)

        assert action is not None
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "shield_bash"
        assert action.player_id == hero.player_id
        assert action.target_x == 6
        assert action.target_y == 5

    def test_try_skill_on_cooldown(self):
        """Skill on cooldown → returns None."""
        hero = make_hero(class_id="crusader", cooldowns={"double_strike": 2})
        action = _try_skill(hero, "double_strike", target_x=6, target_y=5)

        assert action is None

    def test_try_skill_wrong_class(self):
        """Wrong class for skill → returns None (Ranger can't use Heal)."""
        hero = make_hero(class_id="ranger", cooldowns={})
        action = _try_skill(hero, "heal", target_x=5, target_y=5)

        assert action is None

    def test_try_skill_unknown_skill(self):
        """Unknown skill_id → returns None."""
        hero = make_hero(class_id="crusader", cooldowns={})
        action = _try_skill(hero, "nonexistent_fireball")

        assert action is None

    def test_try_skill_dead_unit(self):
        """Dead unit → returns None (can_use_skill checks is_alive)."""
        hero = make_hero(class_id="crusader", hp=0, cooldowns={})
        hero.is_alive = False
        action = _try_skill(hero, "double_strike", target_x=6, target_y=5)

        assert action is None

    def test_try_skill_no_target_coords(self):
        """Self-targeting skill (Taunt) → no target_x/y needed."""
        hero = make_hero(class_id="crusader", cooldowns={})
        action = _try_skill(hero, "taunt")

        assert action is not None
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "taunt"
        assert action.target_x is None
        assert action.target_y is None


# ---------------------------------------------------------------------------
# 3. _decide_skill_usage() Dispatch Tests (8B-1)
# ---------------------------------------------------------------------------

class TestDecideSkillUsage:
    """Tests for the role-based skill dispatch framework."""

    def test_no_skills_for_null_class(self):
        """class_id=None (legacy) → returns None, no crash."""
        hero = make_hero(class_id=None, cooldowns={})
        enemies = [make_enemy()]

        result = _decide_skill_usage(
            hero, enemies, {hero.player_id: hero},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert result is None

    def test_no_skills_for_unknown_class(self):
        """Unknown class_id → returns None, no crash."""
        hero = make_hero(class_id="unknown_class_xyz", cooldowns={})
        enemies = [make_enemy()]

        result = _decide_skill_usage(
            hero, enemies, {hero.player_id: hero},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert result is None

    def test_decide_skill_dispatches_to_support(self):
        """Confessor dispatches to _support_skill_logic."""
        hero = make_hero(class_id="confessor")
        enemies = [make_enemy()]

        with patch("app.core.ai_skills._support_skill_logic", return_value=None) as mock_fn:
            _decide_skill_usage(
                hero, enemies, {hero.player_id: hero},
                grid_width=15, grid_height=15, obstacles=set(),
            )
            mock_fn.assert_called_once()
            # Verify hero was passed as first arg
            call_args = mock_fn.call_args
            assert call_args[0][0].player_id == hero.player_id

    def test_decide_skill_dispatches_to_tank(self):
        """Crusader dispatches to _tank_skill_logic."""
        hero = make_hero(class_id="crusader")
        enemies = [make_enemy()]

        with patch("app.core.ai_skills._tank_skill_logic", return_value=None) as mock_fn:
            _decide_skill_usage(
                hero, enemies, {hero.player_id: hero},
                grid_width=15, grid_height=15, obstacles=set(),
            )
            mock_fn.assert_called_once()

    def test_decide_skill_dispatches_to_ranged_dps(self):
        """Ranger dispatches to _ranged_dps_skill_logic."""
        hero = make_hero(class_id="ranger")
        enemies = [make_enemy()]

        with patch("app.core.ai_skills._ranged_dps_skill_logic", return_value=None) as mock_fn:
            _decide_skill_usage(
                hero, enemies, {hero.player_id: hero},
                grid_width=15, grid_height=15, obstacles=set(),
            )
            mock_fn.assert_called_once()

    def test_decide_skill_dispatches_to_hybrid_dps(self):
        """Hexblade dispatches to _hybrid_dps_skill_logic."""
        hero = make_hero(class_id="hexblade")
        enemies = [make_enemy()]

        with patch("app.core.ai_skills._hybrid_dps_skill_logic", return_value=None) as mock_fn:
            _decide_skill_usage(
                hero, enemies, {hero.player_id: hero},
                grid_width=15, grid_height=15, obstacles=set(),
            )
            mock_fn.assert_called_once()

    def test_decide_skill_dispatches_to_scout(self):
        """Inquisitor dispatches to _scout_skill_logic."""
        hero = make_hero(class_id="inquisitor")
        enemies = [make_enemy()]

        with patch("app.core.ai_skills._scout_skill_logic", return_value=None) as mock_fn:
            _decide_skill_usage(
                hero, enemies, {hero.player_id: hero},
                grid_width=15, grid_height=15, obstacles=set(),
            )
            mock_fn.assert_called_once()

    def test_dispatch_returns_skill_action_from_handler(self):
        """When a role handler returns a SKILL action, _decide_skill_usage passes it through."""
        hero = make_hero(class_id="crusader")
        enemies = [make_enemy()]
        fake_action = PlayerAction(
            player_id=hero.player_id,
            action_type=ActionType.SKILL,
            skill_id="double_strike",
            target_x=8, target_y=5,
        )

        with patch("app.core.ai_skills._tank_skill_logic", return_value=fake_action):
            result = _decide_skill_usage(
                hero, enemies, {hero.player_id: hero},
                grid_width=15, grid_height=15, obstacles=set(),
            )
            assert result is not None
            assert result.action_type == ActionType.SKILL
            assert result.skill_id == "double_strike"

    def test_dispatch_returns_none_when_handler_returns_none(self):
        """When role handler returns None, _decide_skill_usage returns None (fall through)."""
        hero = make_hero(class_id="crusader")
        # Put all 4 crusader skills on cooldown and add armor buff so tank handler returns None
        hero.cooldowns = {"taunt": 3, "shield_bash": 2, "holy_ground": 3, "bulwark": 3}
        hero.active_buffs = [
            {"buff_id": "bulwark", "stat": "armor", "type": "buff",
             "magnitude": 5, "turns_remaining": 1}
        ]
        enemies = [make_enemy()]

        result = _decide_skill_usage(
            hero, enemies, {hero.player_id: hero},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert result is None
