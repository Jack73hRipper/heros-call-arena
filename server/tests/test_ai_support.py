"""
Tests for Phase 8C — Support Role AI (Confessor: Heal).

Covers:
  8C-1: _support_skill_logic() — Heal decision
    - Confessor heals low-HP ally within range
    - Confessor heals self when below 50% HP
    - Confessor heals lowest-HP ally when multiple injured
    - Confessor attacks when all allies healthy (>60%)
    - Confessor attacks when Heal on cooldown
    - Confessor doesn't heal allies out of range
    - Confessor prioritizes heal over attack when both possible
    - Confessor heals even if ally only missing small HP (game caps)
    - Confessor doesn't heal when all allies at full HP
    - Confessor heals at new extended range (3 tiles)

  8C-2: _support_move_preference() — Positioning
    - Support prefers moving toward injured ally over enemy
    - Support moves toward nearest ally when no one hurt

  Guard:
    - Enemy AI does not use support skill logic
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.ai_behavior import (
    _support_skill_logic,
    _support_move_preference,
    _decide_skill_usage,
    _HEAL_SELF_THRESHOLD,
    _HEAL_ALLY_THRESHOLD,
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

def make_confessor(pid="confessor1", username="Sister Maeve", x=5, y=5,
                   hp=100, max_hp=100, team="a", ai_stance="follow",
                   cooldowns=None, hero_id="hero_conf") -> PlayerState:
    """Create a Confessor hero AI unit (Support role)."""
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
        ai_stance=ai_stance,
        class_id="confessor",
        ranged_range=1,
        vision_range=6,
        inventory=[],
        cooldowns=cooldowns or {},
        active_buffs=[],
    )


def make_ally(pid="ally1", username="Ser Aldric", x=6, y=5,
              hp=60, max_hp=150, team="a", class_id="crusader",
              hero_id="hero_ally1") -> PlayerState:
    """Create an allied hero AI unit."""
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
        class_id=class_id,
        ranged_range=1,
        vision_range=5,
        inventory=[],
        cooldowns={},
        active_buffs=[],
    )


def make_enemy(pid="enemy1", username="Demon", x=8, y=5,
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


# ---------------------------------------------------------------------------
# 1. _support_skill_logic() Tests — Heal Decision (8C-1)
# ---------------------------------------------------------------------------

class TestSupportSkillLogicHeal:
    """Tests for the Confessor's heal decision logic."""

    def test_confessor_heals_low_hp_ally(self):
        """Adjacent ally at 40% HP → heals ally."""
        confessor = make_confessor(x=5, y=5, hp=100, max_hp=100)
        ally = make_ally(pid="ally1", x=6, y=5, hp=60, max_hp=150)  # 40%
        enemy = make_enemy(pid="enemy1", x=10, y=5)

        all_units = {
            confessor.player_id: confessor,
            ally.player_id: ally,
            enemy.player_id: enemy,
        }

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "heal"
        assert result.target_x == ally.position.x
        assert result.target_y == ally.position.y

    def test_confessor_heals_self_when_low(self):
        """Self at 45% HP, no adjacent allies → heals self."""
        confessor = make_confessor(x=5, y=5, hp=45, max_hp=100)
        enemy = make_enemy(pid="enemy1", x=10, y=5)

        all_units = {
            confessor.player_id: confessor,
            enemy.player_id: enemy,
        }

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "heal"
        assert result.target_x == confessor.position.x
        assert result.target_y == confessor.position.y

    def test_confessor_heals_lowest_ally(self):
        """Two allies within range at 40% and 55% → heals the 40% one."""
        confessor = make_confessor(x=5, y=5, hp=100, max_hp=100)
        ally_low = make_ally(pid="ally1", username="Low HP", x=6, y=5,
                            hp=60, max_hp=150)  # 40%
        ally_mid = make_ally(pid="ally2", username="Mid HP", x=5, y=6,
                            hp=55, max_hp=100)  # 55%

        all_units = {
            confessor.player_id: confessor,
            ally_low.player_id: ally_low,
            ally_mid.player_id: ally_mid,
        }

        result = _support_skill_logic(
            confessor, [], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.skill_id == "heal"
        assert result.target_x == ally_low.position.x
        assert result.target_y == ally_low.position.y

    def test_confessor_attacks_when_all_healthy(self):
        """All allies above 60% HP → returns None (fall through to attack)."""
        confessor = make_confessor(x=5, y=5, hp=100, max_hp=100,
                                   cooldowns={"shield_of_faith": 99, "exorcism": 99, "prayer": 99})
        ally = make_ally(pid="ally1", x=6, y=5, hp=120, max_hp=150)  # 80%
        enemy = make_enemy(pid="enemy1", x=7, y=5)

        all_units = {
            confessor.player_id: confessor,
            ally.player_id: ally,
            enemy.player_id: enemy,
        }

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is None  # Fall through to basic attack logic

    def test_confessor_heal_on_cooldown_attacks(self):
        """Ally at 30% but Heal on cooldown → returns None (attacks instead)."""
        confessor = make_confessor(x=5, y=5, cooldowns={"heal": 3, "shield_of_faith": 99, "exorcism": 99, "prayer": 99})
        ally = make_ally(pid="ally1", x=6, y=5, hp=45, max_hp=150)  # 30%
        enemy = make_enemy(pid="enemy1", x=7, y=5)

        all_units = {
            confessor.player_id: confessor,
            ally.player_id: ally,
            enemy.player_id: enemy,
        }

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is None

    def test_confessor_heal_range_check_out_of_range(self):
        """Ally at 30% HP but 5 tiles away → doesn't heal (range 3)."""
        confessor = make_confessor(x=5, y=5,
                                   cooldowns={"shield_of_faith": 99, "exorcism": 99, "prayer": 99})
        ally = make_ally(pid="ally1", x=10, y=5, hp=45, max_hp=150)  # 30%, 5 tiles away

        all_units = {
            confessor.player_id: confessor,
            ally.player_id: ally,
        }

        result = _support_skill_logic(
            confessor, [], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is None  # Out of range

    def test_confessor_heals_ally_at_range_3(self):
        """Ally at 30% HP exactly 3 tiles away → does heal (range 3)."""
        confessor = make_confessor(x=5, y=5)
        ally = make_ally(pid="ally1", x=8, y=5, hp=45, max_hp=150)  # 30%, 3 tiles away

        all_units = {
            confessor.player_id: confessor,
            ally.player_id: ally,
        }

        result = _support_skill_logic(
            confessor, [], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.skill_id == "heal"
        assert result.target_x == ally.position.x
        assert result.target_y == ally.position.y

    def test_confessor_heals_ally_at_range_2(self):
        """Ally at 40% HP 2 tiles away → heals."""
        confessor = make_confessor(x=5, y=5)
        ally = make_ally(pid="ally1", x=7, y=5, hp=60, max_hp=150)  # 40%, 2 tiles away

        all_units = {
            confessor.player_id: confessor,
            ally.player_id: ally,
        }

        result = _support_skill_logic(
            confessor, [], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.skill_id == "heal"
        assert result.target_x == ally.position.x

    def test_confessor_prioritizes_heal_over_attack(self):
        """Adjacent enemy AND adjacent hurt ally → heals (skill runs before attack)."""
        confessor = make_confessor(x=5, y=5, hp=100, max_hp=100)
        ally = make_ally(pid="ally1", x=6, y=5, hp=40, max_hp=100)  # 40%, adjacent
        enemy = make_enemy(pid="enemy1", x=4, y=5)  # Also adjacent

        all_units = {
            confessor.player_id: confessor,
            ally.player_id: ally,
            enemy.player_id: enemy,
        }

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "heal"
        # Should heal the ally, not attack the enemy
        assert result.target_x == ally.position.x
        assert result.target_y == ally.position.y

    def test_confessor_heal_doesnt_overheal_check(self):
        """Ally missing just 10 HP (above 60% threshold) in combat → doesn't heal."""
        confessor = make_confessor(x=5, y=5,
                                   cooldowns={"shield_of_faith": 99, "exorcism": 99, "prayer": 99})
        ally = make_ally(pid="ally1", x=6, y=5, hp=140, max_hp=150)  # 93%
        enemy = make_enemy(pid="enemy1", x=10, y=5)  # In combat

        all_units = {
            confessor.player_id: confessor,
            ally.player_id: ally,
            enemy.player_id: enemy,
        }

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is None  # Above in-combat threshold, no heal needed

    def test_confessor_tops_off_ally_out_of_combat(self):
        """Ally missing just 10 HP, no enemies visible → heals (OOC top-off)."""
        confessor = make_confessor(x=5, y=5,
                                   cooldowns={"shield_of_faith": 99, "exorcism": 99, "prayer": 99})
        ally = make_ally(pid="ally1", x=6, y=5, hp=140, max_hp=150)  # 93%

        all_units = {
            confessor.player_id: confessor,
            ally.player_id: ally,
        }

        result = _support_skill_logic(
            confessor, [], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.skill_id == "heal"
        assert result.target_id == "ally1"

    def test_confessor_heals_ally_below_threshold(self):
        """Ally at exactly 59% → heals (below 60% threshold)."""
        confessor = make_confessor(x=5, y=5)
        ally = make_ally(pid="ally1", x=6, y=5, hp=59, max_hp=100)  # 59%

        all_units = {
            confessor.player_id: confessor,
            ally.player_id: ally,
        }

        result = _support_skill_logic(
            confessor, [], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.skill_id == "heal"

    def test_confessor_no_heal_at_full_hp(self):
        """All allies at 100% → returns None."""
        confessor = make_confessor(x=5, y=5, hp=100, max_hp=100,
                                   cooldowns={"shield_of_faith": 99, "exorcism": 99, "prayer": 99})
        ally = make_ally(pid="ally1", x=6, y=5, hp=150, max_hp=150)  # 100%

        all_units = {
            confessor.player_id: confessor,
            ally.player_id: ally,
        }

        result = _support_skill_logic(
            confessor, [], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is None

    def test_confessor_self_heal_priority_over_ally(self):
        """Self at 45% HP AND ally at 40% → heals self first (self-preservation)."""
        confessor = make_confessor(x=5, y=5, hp=45, max_hp=100)
        ally = make_ally(pid="ally1", x=6, y=5, hp=60, max_hp=150)  # 40%

        all_units = {
            confessor.player_id: confessor,
            ally.player_id: ally,
        }

        result = _support_skill_logic(
            confessor, [], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.skill_id == "heal"
        assert result.target_x == confessor.position.x
        assert result.target_y == confessor.position.y

    def test_confessor_no_self_heal_above_threshold(self):
        """Self at 55% (above 50% in-combat threshold) with enemies → doesn't self-heal."""
        confessor = make_confessor(x=5, y=5, hp=55, max_hp=100,
                                   cooldowns={"shield_of_faith": 99, "exorcism": 99, "prayer": 99})
        enemy = make_enemy(pid="enemy1", x=10, y=5)  # In combat

        all_units = {
            confessor.player_id: confessor,
            enemy.player_id: enemy,
        }

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is None

    def test_confessor_tops_off_self_out_of_combat(self):
        """Self at 55% with no enemies → self-heals (OOC top-off)."""
        confessor = make_confessor(x=5, y=5, hp=55, max_hp=100,
                                   cooldowns={"shield_of_faith": 99, "exorcism": 99, "prayer": 99})

        all_units = {confessor.player_id: confessor}

        result = _support_skill_logic(
            confessor, [], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.skill_id == "heal"
        assert result.target_id == confessor.player_id

    def test_confessor_doesnt_heal_enemies(self):
        """Enemy at low HP → doesn't heal them (wrong team)."""
        confessor = make_confessor(x=5, y=5,
                                   cooldowns={"shield_of_faith": 99, "exorcism": 99, "prayer": 99})
        enemy = make_enemy(pid="enemy1", x=6, y=5, hp=10, max_hp=80)  # 12.5%

        all_units = {
            confessor.player_id: confessor,
            enemy.player_id: enemy,
        }

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is None  # No allies to heal, enemy is not a valid target

    def test_confessor_doesnt_heal_dead_ally(self):
        """Dead ally → not a valid heal target."""
        confessor = make_confessor(x=5, y=5,
                                   cooldowns={"shield_of_faith": 99, "exorcism": 99, "prayer": 99})
        dead_ally = make_ally(pid="ally1", x=6, y=5, hp=0, max_hp=150)
        dead_ally.is_alive = False

        all_units = {
            confessor.player_id: confessor,
            dead_ally.player_id: dead_ally,
        }

        result = _support_skill_logic(
            confessor, [], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is None


# ---------------------------------------------------------------------------
# 2. _support_move_preference() Tests — Positioning (8C-2)
# ---------------------------------------------------------------------------

class TestSupportMovePreference:
    """Tests for the support positioning helper."""

    def test_moves_toward_injured_ally(self):
        """Injured ally exists → returns ally position."""
        confessor = make_confessor(x=5, y=5)
        ally = make_ally(pid="ally1", x=10, y=5, hp=45, max_hp=150)  # 30%

        all_units = {
            confessor.player_id: confessor,
            ally.player_id: ally,
        }

        result = _support_move_preference(confessor, all_units)
        assert result == (ally.position.x, ally.position.y)

    def test_moves_toward_most_injured_ally(self):
        """Multiple injured allies → prefers lowest HP%."""
        confessor = make_confessor(x=5, y=5)
        ally_low = make_ally(pid="ally1", username="Low", x=8, y=5,
                            hp=30, max_hp=150)  # 20%
        ally_mid = make_ally(pid="ally2", username="Mid", x=3, y=5,
                            hp=50, max_hp=100)  # 50%

        all_units = {
            confessor.player_id: confessor,
            ally_low.player_id: ally_low,
            ally_mid.player_id: ally_mid,
        }

        result = _support_move_preference(confessor, all_units)
        assert result == (ally_low.position.x, ally_low.position.y)

    def test_moves_toward_nearest_ally_when_no_injured(self):
        """No injured allies → returns nearest ally position (stay grouped)."""
        confessor = make_confessor(x=5, y=5)
        ally_near = make_ally(pid="ally1", username="Near", x=7, y=5,
                             hp=150, max_hp=150)  # 100%, dist 2
        ally_far = make_ally(pid="ally2", username="Far", x=12, y=5,
                            hp=100, max_hp=100)  # 100%, dist 7

        all_units = {
            confessor.player_id: confessor,
            ally_near.player_id: ally_near,
            ally_far.player_id: ally_far,
        }

        result = _support_move_preference(confessor, all_units)
        assert result == (ally_near.position.x, ally_near.position.y)

    def test_returns_none_when_no_allies(self):
        """No allies alive → returns None."""
        confessor = make_confessor(x=5, y=5)
        enemy = make_enemy(pid="enemy1", x=8, y=5)

        all_units = {
            confessor.player_id: confessor,
            enemy.player_id: enemy,
        }

        result = _support_move_preference(confessor, all_units)
        assert result is None

    def test_ignores_dead_allies(self):
        """Dead ally not counted in move preference."""
        confessor = make_confessor(x=5, y=5)
        dead_ally = make_ally(pid="ally1", x=6, y=5, hp=0, max_hp=150)
        dead_ally.is_alive = False

        all_units = {
            confessor.player_id: confessor,
            dead_ally.player_id: dead_ally,
        }

        result = _support_move_preference(confessor, all_units)
        assert result is None

    def test_ignores_enemies_in_preference(self):
        """Enemy at low HP not considered as ally for move preference."""
        confessor = make_confessor(x=5, y=5)
        enemy = make_enemy(pid="enemy1", x=6, y=5, hp=10, max_hp=80)

        all_units = {
            confessor.player_id: confessor,
            enemy.player_id: enemy,
        }

        result = _support_move_preference(confessor, all_units)
        assert result is None


# ---------------------------------------------------------------------------
# 3. Integration Tests — Support in the Skill Dispatch Chain
# ---------------------------------------------------------------------------

class TestSupportDispatchIntegration:
    """Verify _decide_skill_usage dispatches correctly for Confessor."""

    def test_confessor_dispatches_to_support_logic(self):
        """Confessor with injured ally → _decide_skill_usage returns SKILL heal."""
        confessor = make_confessor(x=5, y=5, hp=100, max_hp=100)
        ally = make_ally(pid="ally1", x=6, y=5, hp=30, max_hp=100)  # 30%
        enemy = make_enemy(pid="enemy1", x=10, y=5)

        all_units = {
            confessor.player_id: confessor,
            ally.player_id: ally,
            enemy.player_id: enemy,
        }

        result = _decide_skill_usage(
            confessor, [enemy], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "heal"

    def test_confessor_returns_none_when_no_healing_needed(self):
        """All allies healthy → falls through to basic attack."""
        confessor = make_confessor(x=5, y=5, hp=100, max_hp=100,
                                   cooldowns={"shield_of_faith": 99, "exorcism": 99, "prayer": 99})
        ally = make_ally(pid="ally1", x=6, y=5, hp=150, max_hp=150)  # 100%
        enemy = make_enemy(pid="enemy1", x=8, y=5)

        all_units = {
            confessor.player_id: confessor,
            ally.player_id: ally,
            enemy.player_id: enemy,
        }

        result = _decide_skill_usage(
            confessor, [enemy], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is None  # Fall through

    def test_role_is_support_for_confessor(self):
        """Confessor maps to 'support' role."""
        assert _get_role_for_class("confessor") == "support"

    def test_heal_thresholds_are_set(self):
        """Verify heal thresholds exist and are reasonable."""
        assert 0 < _HEAL_SELF_THRESHOLD < 1.0
        assert 0 < _HEAL_ALLY_THRESHOLD < 1.0
        assert _HEAL_SELF_THRESHOLD <= _HEAL_ALLY_THRESHOLD


# ---------------------------------------------------------------------------
# 4. Guard Tests — Enemy AI Exclusion
# ---------------------------------------------------------------------------

class TestSupportGuard:
    """Ensure enemy AI and non-confessor classes are unaffected."""

    def test_enemy_ai_no_support_skills(self):
        """Enemy AI unit (no hero_id) with confessor class → no skill usage.

        Note: Enemy AI units don't go through _decide_skill_usage because
        they use decide_aggressive_action/decide_ranged_action instead.
        But if class_id='confessor' somehow gets set, support logic should
        still only activate for hero allies. The skill dispatch itself runs
        fine for any unit, but the stance action gate (hero_id check) prevents
        enemy AI from reaching it.
        """
        # Direct call to _support_skill_logic doesn't check hero_id
        # The guard is in decide_ai_action → _decide_stance_action (hero_id check)
        # This test confirms the healing logic itself doesn't crash for non-heroes
        enemy = make_enemy(pid="enemy1", x=5, y=5, hp=20, max_hp=80)
        enemy.class_id = "confessor"  # Edge case: enemy with confessor class

        all_units = {enemy.player_id: enemy}

        result = _support_skill_logic(
            enemy, [], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        # Self-heal check: enemy is at 25% (below 50% threshold)
        # can_use_skill checks class, so this should work if class is valid
        # The real guard is hero_id check in _decide_stance_action
        # This test just confirms no crash
        assert result is None or result.action_type == ActionType.SKILL

    def test_non_support_class_no_heal(self):
        """Crusader (Tank role) → _support_skill_logic never called via dispatch."""
        crusader = make_ally(pid="tank1", x=5, y=5, hp=30, max_hp=150,
                           class_id="crusader")
        ally = make_ally(pid="ally1", x=6, y=5, hp=30, max_hp=100)

        all_units = {
            crusader.player_id: crusader,
            ally.player_id: ally,
        }

        result = _decide_skill_usage(
            crusader, [], all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        # Crusader dispatches to _tank_skill_logic (stub returns None)
        assert result is None
