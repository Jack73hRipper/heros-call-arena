"""
Tests for Phase 28A — Enemy AI Potion Usage.

Covers per-behavior potion thresholds and integration with decide_ai_action:
  - Aggressive enemy drinks at 30% HP threshold
  - Aggressive enemy does NOT drink above threshold
  - Ranged enemy drinks at 40% HP threshold
  - Boss enemy drinks at 25% HP threshold
  - Support enemy drinks at 50% HP threshold
  - Enemy with empty inventory returns normal combat action
  - Enemy prefers greater_health_potion over health_potion
  - Threshold constants are correct for all behaviors
"""

from app.models.player import PlayerState, Position
from app.models.actions import ActionType
from app.core.ai_behavior import (
    _should_use_potion,
    _ENEMY_POTION_THRESHOLDS,
    _decide_aggressive_action,
    _decide_ranged_action,
    _decide_boss_action,
    _decide_support_behavior,
    decide_ai_action,
)
from app.core.combat import load_combat_config


def setup_module():
    load_combat_config()


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

def _health_potion() -> dict:
    """Standard health potion (40 HP)."""
    return {
        "item_id": "health_potion",
        "name": "Health Potion",
        "item_type": "consumable",
        "rarity": "common",
        "equip_slot": None,
        "stat_bonuses": {"attack_damage": 0, "ranged_damage": 0, "armor": 0, "max_hp": 0},
        "consumable_effect": {"type": "heal", "magnitude": 40},
        "description": "Restores 40 HP.",
        "sell_value": 15,
    }


def _greater_health_potion() -> dict:
    """Greater health potion (75 HP)."""
    return {
        "item_id": "greater_health_potion",
        "name": "Greater Health Potion",
        "item_type": "consumable",
        "rarity": "uncommon",
        "equip_slot": None,
        "stat_bonuses": {"attack_damage": 0, "ranged_damage": 0, "armor": 0, "max_hp": 0},
        "consumable_effect": {"type": "heal", "magnitude": 75},
        "description": "Restores 75 HP.",
        "sell_value": 35,
    }


def _make_enemy(ai_behavior="aggressive", hp=80, max_hp=200, inventory=None,
                x=5, y=5, pid="enemy1", enemy_type=None) -> PlayerState:
    """Create an AI hero party unit with given behavior and HP.

    Phase 28-FIX: enemy_type=None means this is a hero party AI (not a dungeon
    monster). Potion usage is guarded behind enemy_type is None.
    """
    return PlayerState(
        player_id=pid,
        username=f"Test {ai_behavior.title()}",
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=15,
        ranged_damage=10,
        armor=2,
        team="b",
        unit_type="ai",
        hero_id=None,
        ai_behavior=ai_behavior,
        enemy_type=enemy_type,
        ranged_range=5,
        vision_range=7,
        inventory=inventory or [],
    )


# ---------------------------------------------------------------------------
# 1. Threshold Constants
# ---------------------------------------------------------------------------

class TestEnemyPotionThresholds:
    """Verify per-behavior enemy potion threshold values."""

    def test_aggressive_threshold(self):
        assert _ENEMY_POTION_THRESHOLDS["aggressive"] == 0.30

    def test_ranged_threshold(self):
        assert _ENEMY_POTION_THRESHOLDS["ranged"] == 0.40

    def test_boss_threshold(self):
        assert _ENEMY_POTION_THRESHOLDS["boss"] == 0.25

    def test_support_threshold(self):
        assert _ENEMY_POTION_THRESHOLDS["support"] == 0.50

    def test_all_behaviors_present(self):
        assert set(_ENEMY_POTION_THRESHOLDS.keys()) == {
            "aggressive", "ranged", "boss", "support",
        }


# ---------------------------------------------------------------------------
# 2. Aggressive Behavior Potion Tests
# ---------------------------------------------------------------------------

class TestAggressiveEnemyPotions:
    """Aggressive enemy AI potion behavior (threshold = 30%)."""

    def test_enemy_drinks_potion_at_threshold(self):
        """Aggressive enemy at 30% HP with potion → returns USE_ITEM."""
        enemy = _make_enemy(hp=60, max_hp=200, inventory=[_health_potion()])
        action = _decide_aggressive_action(
            enemy, {enemy.player_id: enemy},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is not None
        assert action.action_type == ActionType.USE_ITEM
        assert action.target_x == 0

    def test_enemy_no_potion_above_threshold(self):
        """Aggressive enemy at 50% HP → does NOT drink (above 30%)."""
        enemy = _make_enemy(hp=100, max_hp=200, inventory=[_health_potion()])
        action = _decide_aggressive_action(
            enemy, {enemy.player_id: enemy},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is None or action.action_type != ActionType.USE_ITEM

    def test_enemy_no_potion_empty_inventory(self):
        """Aggressive enemy at 10% HP with empty inventory → normal action."""
        enemy = _make_enemy(hp=20, max_hp=200, inventory=[])
        action = _decide_aggressive_action(
            enemy, {enemy.player_id: enemy},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is None or action.action_type != ActionType.USE_ITEM

    def test_enemy_prefers_greater_potion(self):
        """Aggressive enemy with both potions → picks greater_health_potion."""
        enemy = _make_enemy(
            hp=40, max_hp=200,
            inventory=[_health_potion(), _greater_health_potion()],
        )
        action = _decide_aggressive_action(
            enemy, {enemy.player_id: enemy},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is not None
        assert action.action_type == ActionType.USE_ITEM
        assert action.target_x == 1  # greater potion at index 1

    def test_via_decide_ai_action(self):
        """Integration: decide_ai_action routes aggressive enemy to potion."""
        enemy = _make_enemy(hp=40, max_hp=200, inventory=[_health_potion()])
        action = decide_ai_action(
            enemy, {enemy.player_id: enemy},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is not None
        assert action.action_type == ActionType.USE_ITEM


# ---------------------------------------------------------------------------
# 3. Ranged Behavior Potion Tests
# ---------------------------------------------------------------------------

class TestRangedEnemyPotions:
    """Ranged enemy AI potion behavior (threshold = 40%)."""

    def test_ranged_drinks_at_threshold(self):
        """Ranged enemy at 35% HP → drinks potion (below 40%)."""
        enemy = _make_enemy(ai_behavior="ranged", hp=70, max_hp=200,
                            inventory=[_health_potion()])
        action = _decide_ranged_action(
            enemy, {enemy.player_id: enemy},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is not None
        assert action.action_type == ActionType.USE_ITEM

    def test_ranged_no_drink_above_threshold(self):
        """Ranged enemy at 50% HP → does NOT drink (above 40%)."""
        enemy = _make_enemy(ai_behavior="ranged", hp=100, max_hp=200,
                            inventory=[_health_potion()])
        action = _decide_ranged_action(
            enemy, {enemy.player_id: enemy},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is None or action.action_type != ActionType.USE_ITEM

    def test_via_decide_ai_action(self):
        """Integration: decide_ai_action routes ranged enemy to potion."""
        enemy = _make_enemy(ai_behavior="ranged", hp=60, max_hp=200,
                            inventory=[_health_potion()])
        action = decide_ai_action(
            enemy, {enemy.player_id: enemy},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is not None
        assert action.action_type == ActionType.USE_ITEM


# ---------------------------------------------------------------------------
# 4. Boss Behavior Potion Tests
# ---------------------------------------------------------------------------

class TestBossEnemyPotions:
    """Boss enemy AI potion behavior (threshold = 25%)."""

    def test_boss_drinks_at_threshold(self):
        """Boss at 20% HP → drinks potion (below 25%)."""
        enemy = _make_enemy(ai_behavior="boss", hp=40, max_hp=200,
                            inventory=[_health_potion()])
        action = _decide_boss_action(
            enemy, {enemy.player_id: enemy},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is not None
        assert action.action_type == ActionType.USE_ITEM

    def test_boss_no_drink_above_threshold(self):
        """Boss at 30% HP → does NOT drink (above 25% threshold)."""
        enemy = _make_enemy(ai_behavior="boss", hp=60, max_hp=200,
                            inventory=[_health_potion()])
        action = _decide_boss_action(
            enemy, {enemy.player_id: enemy},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is None or action.action_type != ActionType.USE_ITEM

    def test_boss_lower_threshold_than_aggressive(self):
        """Boss at 28% HP still attacks (threshold is 25%, not 30%)."""
        enemy = _make_enemy(ai_behavior="boss", hp=56, max_hp=200,
                            inventory=[_health_potion()])
        action = _decide_boss_action(
            enemy, {enemy.player_id: enemy},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is None or action.action_type != ActionType.USE_ITEM


# ---------------------------------------------------------------------------
# 5. Support Behavior Potion Tests
# ---------------------------------------------------------------------------

class TestSupportEnemyPotions:
    """Support enemy AI potion behavior (threshold = 50%)."""

    def test_support_drinks_at_45_percent(self):
        """Support at 45% HP → drinks potion (below 50% threshold)."""
        enemy = _make_enemy(ai_behavior="support", hp=90, max_hp=200,
                            inventory=[_health_potion()])
        action = _decide_support_behavior(
            enemy, {enemy.player_id: enemy},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is not None
        assert action.action_type == ActionType.USE_ITEM

    def test_support_no_drink_above_threshold(self):
        """Support at 60% HP → does NOT drink (above 50%)."""
        enemy = _make_enemy(ai_behavior="support", hp=120, max_hp=200,
                            inventory=[_health_potion()])
        action = _decide_support_behavior(
            enemy, {enemy.player_id: enemy},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is None or action.action_type != ActionType.USE_ITEM

    def test_support_higher_threshold_than_others(self):
        """Support threshold (50%) is highest — drinks before other behaviors would."""
        # 45% HP: support drinks, aggressive would not (30%), boss would not (25%)
        enemy = _make_enemy(ai_behavior="support", hp=90, max_hp=200,
                            inventory=[_health_potion()])
        support_action = _should_use_potion(enemy, hp_threshold=0.50)
        aggressive_action = _should_use_potion(enemy, hp_threshold=0.30)
        boss_action = _should_use_potion(enemy, hp_threshold=0.25)

        assert support_action is not None
        assert aggressive_action is None
        assert boss_action is None


# ---------------------------------------------------------------------------
# 6. Phase 28-FIX: Monster Exclusion Tests
# ---------------------------------------------------------------------------

class TestMonsterPotionExclusion:
    """Phase 28-FIX: Dungeon monsters (enemy_type set) must NOT drink potions."""

    def test_monster_aggressive_skips_potion(self):
        """Monster with enemy_type='demon' at low HP → does NOT drink potion."""
        monster = _make_enemy(ai_behavior="aggressive", hp=30, max_hp=200,
                              inventory=[_health_potion()], enemy_type="demon")
        action = _decide_aggressive_action(
            monster, {monster.player_id: monster},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is None or action.action_type != ActionType.USE_ITEM

    def test_monster_boss_skips_potion(self):
        """Boss monster at critically low HP → does NOT drink."""
        monster = _make_enemy(ai_behavior="boss", hp=20, max_hp=200,
                              inventory=[_health_potion()], enemy_type="undead_knight")
        action = _decide_boss_action(
            monster, {monster.player_id: monster},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is None or action.action_type != ActionType.USE_ITEM

    def test_monster_support_skips_potion(self):
        """Support monster at low HP → does NOT drink."""
        monster = _make_enemy(ai_behavior="support", hp=50, max_hp=200,
                              inventory=[_health_potion()], enemy_type="dark_priest")
        action = _decide_support_behavior(
            monster, {monster.player_id: monster},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is None or action.action_type != ActionType.USE_ITEM

    def test_monster_ranged_skips_potion(self):
        """Ranged monster at low HP → does NOT drink."""
        monster = _make_enemy(ai_behavior="ranged", hp=40, max_hp=200,
                              inventory=[_health_potion()], enemy_type="skeleton")
        action = _decide_ranged_action(
            monster, {monster.player_id: monster},
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert action is None or action.action_type != ActionType.USE_ITEM
