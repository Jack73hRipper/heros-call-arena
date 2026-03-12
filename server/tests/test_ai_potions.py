"""
Tests for Phase 8A-1 — AI Potion Usage.

Covers:
  - AI drinks potion when HP is below threshold
  - AI does NOT drink when healthy (above threshold)
  - AI does NOT drink with empty inventory
  - AI prefers greater_health_potion over health_potion (higher magnitude first)
  - AI respects per-stance thresholds (aggressive = 25%, defensive = 50%)
  - AI does NOT drink at full HP even if below threshold edge case
  - AI ignores non-heal consumables (portal scrolls)
  - Returned USE_ITEM action has correct target_x (inventory index)
  - Enemy AI units never drink potions (hero_id guard)
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.ai_behavior import (
    _should_use_potion,
    _decide_stance_action,
    _POTION_THRESHOLDS,
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


def _portal_scroll() -> dict:
    """Portal scroll — NOT a heal consumable."""
    return {
        "item_id": "portal_scroll",
        "name": "Portal Scroll",
        "item_type": "consumable",
        "rarity": "uncommon",
        "equip_slot": None,
        "stat_bonuses": {"attack_damage": 0, "ranged_damage": 0, "armor": 0, "max_hp": 0},
        "consumable_effect": {"type": "portal", "magnitude": 0},
        "description": "Tears open a portal.",
        "sell_value": 50,
    }


def _sword_item() -> dict:
    """A weapon item — not consumable."""
    return {
        "item_id": "common_sword",
        "name": "Rusty Sword",
        "item_type": "weapon",
        "rarity": "common",
        "equip_slot": "weapon",
        "stat_bonuses": {"attack_damage": 5, "ranged_damage": 0, "armor": 0, "max_hp": 0},
        "description": "A battered blade.",
        "sell_value": 10,
    }


def make_hero(pid="hero1", username="Ser Aldric", x=5, y=5, hp=100, max_hp=100,
              team="a", ai_stance="follow", class_id="crusader",
              inventory=None, hero_id="hero_001") -> PlayerState:
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
    )


def make_enemy(pid="enemy1", username="Demon", x=8, y=5, hp=80, max_hp=80,
               team="b", ai_behavior="aggressive", enemy_type="demon",
               inventory=None) -> PlayerState:
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
        ai_behavior=ai_behavior,
        enemy_type=enemy_type,
        ranged_range=0,
        vision_range=5,
        inventory=inventory or [],
    )


# ---------------------------------------------------------------------------
# 1. Core _should_use_potion() Tests
# ---------------------------------------------------------------------------

class TestShouldUsePotion:
    """Tests for the _should_use_potion() helper function."""

    def test_ai_drinks_potion_when_low_hp(self):
        """AI at 30% HP with health potion → returns USE_ITEM."""
        hero = make_hero(hp=30, max_hp=100, inventory=[_health_potion()])
        action = _should_use_potion(hero, hp_threshold=0.40)

        assert action is not None
        assert action.action_type == ActionType.USE_ITEM
        assert action.player_id == hero.player_id
        assert action.target_x == 0  # first inventory slot

    def test_ai_no_potion_when_healthy(self):
        """AI at 80% HP with potions → returns None (too healthy)."""
        hero = make_hero(hp=80, max_hp=100, inventory=[_health_potion()])
        action = _should_use_potion(hero, hp_threshold=0.40)

        assert action is None

    def test_ai_no_potion_when_inventory_empty(self):
        """AI at 20% HP with empty inventory → returns None."""
        hero = make_hero(hp=20, max_hp=100, inventory=[])
        action = _should_use_potion(hero, hp_threshold=0.40)

        assert action is None

    def test_ai_prefers_greater_potion(self):
        """AI has both potion types → uses greater_health_potion first (higher magnitude)."""
        hero = make_hero(
            hp=30, max_hp=100,
            inventory=[_health_potion(), _greater_health_potion()],
        )
        action = _should_use_potion(hero, hp_threshold=0.40)

        assert action is not None
        assert action.action_type == ActionType.USE_ITEM
        # Greater potion is at index 1, but since we sort by magnitude descending,
        # the function should pick the greater potion (index 1)
        assert action.target_x == 1

    def test_ai_prefers_greater_potion_reversed_order(self):
        """Greater potion at index 0, regular at index 1 → picks index 0."""
        hero = make_hero(
            hp=30, max_hp=100,
            inventory=[_greater_health_potion(), _health_potion()],
        )
        action = _should_use_potion(hero, hp_threshold=0.40)

        assert action is not None
        assert action.target_x == 0  # greater potion is first

    def test_ai_potion_full_hp(self):
        """AI at max HP → doesn't drink even if threshold would normally trigger."""
        hero = make_hero(hp=100, max_hp=100, inventory=[_health_potion()])
        # Even with threshold=1.0 (always drink), full HP should NOT drink
        action = _should_use_potion(hero, hp_threshold=1.0)

        assert action is None

    def test_ai_potion_only_heal_consumables(self):
        """Portal scroll in inventory doesn't trigger potion logic."""
        hero = make_hero(hp=20, max_hp=100, inventory=[_portal_scroll()])
        action = _should_use_potion(hero, hp_threshold=0.40)

        assert action is None

    def test_ai_potion_ignores_equipment_items(self):
        """Weapon item in inventory doesn't trigger potion logic."""
        hero = make_hero(hp=20, max_hp=100, inventory=[_sword_item()])
        action = _should_use_potion(hero, hp_threshold=0.40)

        assert action is None

    def test_ai_potion_mixed_inventory(self):
        """Inventory with sword, portal scroll, and health potion → finds potion."""
        hero = make_hero(
            hp=25, max_hp=100,
            inventory=[_sword_item(), _portal_scroll(), _health_potion()],
        )
        action = _should_use_potion(hero, hp_threshold=0.40)

        assert action is not None
        assert action.action_type == ActionType.USE_ITEM
        assert action.target_x == 2  # health potion is at index 2

    def test_ai_potion_action_format(self):
        """Returned USE_ITEM has correct fields: player_id, action_type, target_x."""
        hero = make_hero(
            pid="hero_test", hp=30, max_hp=100,
            inventory=[_health_potion()],
        )
        action = _should_use_potion(hero, hp_threshold=0.40)

        assert action is not None
        assert action.player_id == "hero_test"
        assert action.action_type == ActionType.USE_ITEM
        assert action.target_x == 0
        assert action.target_y is None
        assert action.skill_id is None

    def test_ai_dead_no_potion(self):
        """Dead AI → returns None."""
        hero = make_hero(hp=0, max_hp=100, inventory=[_health_potion()])
        hero.is_alive = False
        action = _should_use_potion(hero, hp_threshold=0.40)

        assert action is None

    def test_ai_exact_threshold(self):
        """AI at exactly threshold (40%) → should drink (at or below)."""
        hero = make_hero(hp=40, max_hp=100, inventory=[_health_potion()])
        action = _should_use_potion(hero, hp_threshold=0.40)

        assert action is not None
        assert action.action_type == ActionType.USE_ITEM

    def test_ai_just_above_threshold(self):
        """AI at 41% HP with 40% threshold → should NOT drink."""
        hero = make_hero(hp=41, max_hp=100, inventory=[_health_potion()])
        action = _should_use_potion(hero, hp_threshold=0.40)

        assert action is None


# ---------------------------------------------------------------------------
# 2. Stance Threshold Tests
# ---------------------------------------------------------------------------

class TestPotionThresholdPerStance:
    """Tests for per-stance potion thresholds."""

    def test_threshold_constants_exist(self):
        """All four stances have defined thresholds."""
        assert "follow" in _POTION_THRESHOLDS
        assert "aggressive" in _POTION_THRESHOLDS
        assert "defensive" in _POTION_THRESHOLDS
        assert "hold" in _POTION_THRESHOLDS

    def test_aggressive_threshold_lower(self):
        """Aggressive stance has lowest threshold (25%)."""
        assert _POTION_THRESHOLDS["aggressive"] == 0.25

    def test_defensive_threshold_higher(self):
        """Defensive stance has highest threshold (50%)."""
        assert _POTION_THRESHOLDS["defensive"] == 0.50

    def test_aggressive_no_drink_at_30_percent(self):
        """Aggressive stance at 30% HP → does NOT drink (threshold is 25%)."""
        hero = make_hero(hp=30, max_hp=100, ai_stance="aggressive",
                         inventory=[_health_potion()])
        action = _should_use_potion(hero, hp_threshold=_POTION_THRESHOLDS["aggressive"])

        assert action is None

    def test_aggressive_drinks_at_25_percent(self):
        """Aggressive stance at 25% HP → drinks (at threshold)."""
        hero = make_hero(hp=25, max_hp=100, ai_stance="aggressive",
                         inventory=[_health_potion()])
        action = _should_use_potion(hero, hp_threshold=_POTION_THRESHOLDS["aggressive"])

        assert action is not None
        assert action.action_type == ActionType.USE_ITEM

    def test_defensive_drinks_at_50_percent(self):
        """Defensive stance at 50% HP → drinks (at threshold)."""
        hero = make_hero(hp=50, max_hp=100, ai_stance="defensive",
                         inventory=[_health_potion()])
        action = _should_use_potion(hero, hp_threshold=_POTION_THRESHOLDS["defensive"])

        assert action is not None
        assert action.action_type == ActionType.USE_ITEM

    def test_follow_drinks_at_40_percent(self):
        """Follow stance at 40% HP → drinks (at threshold)."""
        hero = make_hero(hp=40, max_hp=100, ai_stance="follow",
                         inventory=[_health_potion()])
        action = _should_use_potion(hero, hp_threshold=_POTION_THRESHOLDS["follow"])

        assert action is not None
        assert action.action_type == ActionType.USE_ITEM


# ---------------------------------------------------------------------------
# 3. Integration with _decide_stance_action Tests
# ---------------------------------------------------------------------------

class TestPotionIntegrationWithStance:
    """Tests for potion check integration into _decide_stance_action."""

    def test_stance_action_returns_potion_when_low_hp(self):
        """_decide_stance_action returns USE_ITEM when hero is low HP with potions."""
        hero = make_hero(hp=30, max_hp=100, ai_stance="follow",
                         inventory=[_health_potion()])
        owner = PlayerState(
            player_id="owner1", username="Player",
            position=Position(x=3, y=5), hp=100, max_hp=100,
            team="a", unit_type="human",
        )
        hero.controlled_by = "owner1"
        all_units = {hero.player_id: hero, owner.player_id: owner}
        obstacles = set()

        action = _decide_stance_action(
            hero, all_units, grid_width=15, grid_height=15,
            obstacles=obstacles,
        )

        assert action is not None
        assert action.action_type == ActionType.USE_ITEM

    def test_stance_action_no_potion_when_healthy(self):
        """_decide_stance_action does NOT return USE_ITEM when hero is healthy."""
        hero = make_hero(hp=90, max_hp=100, ai_stance="follow",
                         inventory=[_health_potion()])
        owner = PlayerState(
            player_id="owner1", username="Player",
            position=Position(x=3, y=5), hp=100, max_hp=100,
            team="a", unit_type="human",
        )
        hero.controlled_by = "owner1"
        all_units = {hero.player_id: hero, owner.player_id: owner}
        obstacles = set()

        action = _decide_stance_action(
            hero, all_units, grid_width=15, grid_height=15,
            obstacles=obstacles,
        )

        # Should NOT be USE_ITEM — should be a normal stance action (MOVE/WAIT/etc.)
        assert action is None or action.action_type != ActionType.USE_ITEM

    def test_aggressive_stance_potion_integration(self):
        """Aggressive hero at 20% drinks potion via _decide_stance_action."""
        hero = make_hero(hp=20, max_hp=100, ai_stance="aggressive",
                         inventory=[_health_potion()])
        owner = PlayerState(
            player_id="owner1", username="Player",
            position=Position(x=3, y=5), hp=100, max_hp=100,
            team="a", unit_type="human",
        )
        hero.controlled_by = "owner1"
        all_units = {hero.player_id: hero, owner.player_id: owner}
        obstacles = set()

        action = _decide_stance_action(
            hero, all_units, grid_width=15, grid_height=15,
            obstacles=obstacles,
        )

        assert action is not None
        assert action.action_type == ActionType.USE_ITEM

    def test_defensive_stance_potion_integration(self):
        """Defensive hero at 45% drinks potion (defensive threshold is 50%)."""
        hero = make_hero(hp=45, max_hp=100, ai_stance="defensive",
                         inventory=[_health_potion()])
        owner = PlayerState(
            player_id="owner1", username="Player",
            position=Position(x=3, y=5), hp=100, max_hp=100,
            team="a", unit_type="human",
        )
        hero.controlled_by = "owner1"
        all_units = {hero.player_id: hero, owner.player_id: owner}
        obstacles = set()

        action = _decide_stance_action(
            hero, all_units, grid_width=15, grid_height=15,
            obstacles=obstacles,
        )

        assert action is not None
        assert action.action_type == ActionType.USE_ITEM

    def test_hold_stance_potion_integration(self):
        """Hold hero at 30% drinks potion (hold threshold is 40%)."""
        hero = make_hero(hp=30, max_hp=100, ai_stance="hold",
                         inventory=[_health_potion()])
        all_units = {hero.player_id: hero}
        obstacles = set()

        action = _decide_stance_action(
            hero, all_units, grid_width=15, grid_height=15,
            obstacles=obstacles,
        )

        assert action is not None
        assert action.action_type == ActionType.USE_ITEM


# ---------------------------------------------------------------------------
# 4. Enemy AI Exclusion Tests
# ---------------------------------------------------------------------------

class TestEnemyAIPotionExclusion:
    """Enemy AI units must NEVER drink potions — only hero allies."""

    def test_enemy_ai_never_drinks_potion(self):
        """Enemy AI at 10% HP with potions → never calls _should_use_potion.

        The guard is in decide_ai_action: enemies go to aggressive/ranged/boss
        behavior, which never calls _should_use_potion. This test verifies
        _should_use_potion CAN return an action for the state, but
        decide_ai_action does NOT route enemies through _decide_stance_action.
        """
        enemy = make_enemy(hp=8, max_hp=80, inventory=[_health_potion()])
        # The helper itself would fire, but the dispatch in decide_ai_action
        # only calls _decide_stance_action for hero allies (hero_id is not None)
        assert enemy.hero_id is None

        # If we DID call _should_use_potion directly, it would return an action
        direct_action = _should_use_potion(enemy, hp_threshold=0.40)
        assert direct_action is not None  # helper has no hero_id guard itself

        # But decide_ai_action routes enemies to aggressive behavior, not stance
        all_units = {enemy.player_id: enemy}
        action = decide_ai_action(
            enemy, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )
        # Enemy should get a patrol/wait action, NOT USE_ITEM
        assert action is None or action.action_type != ActionType.USE_ITEM

    def test_enemy_ai_no_hero_id(self):
        """Verify enemy AI has hero_id=None (exclusion guard)."""
        enemy = make_enemy()
        assert enemy.hero_id is None
        assert enemy.ai_stance == "follow"  # default, but not used for enemies

    def test_hero_ally_has_hero_id(self):
        """Verify hero ally has hero_id set (inclusion guard)."""
        hero = make_hero()
        assert hero.hero_id is not None
        assert hero.hero_id == "hero_001"
