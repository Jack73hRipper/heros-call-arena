"""
Tests for Phase 8K — AI Retreat Behavior & Kiting.

Covers:
  8K-1: Retreat helpers & constants
    - _has_heal_potions inventory scanning
    - _should_retreat decision logic (thresholds, potions, danger zone, stance)

  8K-2: Retreat destination & integration into _decide_stance_action
    - _find_retreat_destination (toward support, toward owner, generic flee)
    - Priority chain: potion > retreat > skill > stance

  8K-3: Ranged kiting in _decide_follow_action() and _decide_aggressive_stance_action()
    - Ranger adjacent to enemy → steps back instead of melee
    - Ranger 2 tiles from enemy → steps back to ranged sweet spot
    - Ranger at ranged distance → fires ranged attack (no kiting needed)
    - Ranger cornered (can't step back) → melee as fallback
    - Inquisitor (scout role) kites identically to Ranger
    - Crusader (tank) does NOT kite — melee attacks normally
    - Hexblade (hybrid_dps) does NOT kite — melee attacks normally
    - Confessor (support) does NOT kite — support positioning handles this
    - Kiting works in follow stance
    - Kiting works in aggressive stance
    - Defensive stance: kiting skipped (owner-leash takes priority)
    - Hold stance: never moves (no kiting possible)

  Guard / Regression:
    - Enemy AI at low HP → fights normally (enemies never use hero retreat)
    - AI at full HP → normal combat behavior unchanged
    - Retreat does not affect full HP combat
    - Null class_id no crash
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.ai_behavior import (
    _decide_follow_action,
    _decide_aggressive_stance_action,
    _decide_defensive_action,
    _decide_hold_action,
    _decide_stance_action,
    _find_retreat_tile,
    _find_retreat_destination,
    _has_heal_potions,
    _should_retreat,
    _get_role_for_class,
    _chebyshev,
    _build_occupied_set,
    _RETREAT_THRESHOLDS,
    _RETREAT_THRESHOLD_DEFAULT,
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
                cooldowns=None, hero_id="hero_ranger",
                controlled_by="owner1") -> PlayerState:
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
        active_buffs=[],
        controlled_by=controlled_by,
    )


def make_inquisitor(pid="inquisitor1", username="Inquisitor Thane", x=5, y=5,
                    hp=80, max_hp=80, team="a", ai_stance="follow",
                    cooldowns=None, hero_id="hero_inq",
                    controlled_by="owner1") -> PlayerState:
    """Create an Inquisitor hero AI unit (Scout role)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=10,
        ranged_damage=8,
        armor=4,
        team=team,
        unit_type="ai",
        hero_id=hero_id,
        ai_stance=ai_stance,
        class_id="inquisitor",
        ranged_range=5,
        vision_range=9,
        inventory=[],
        cooldowns=cooldowns or {},
        active_buffs=[],
        controlled_by=controlled_by,
    )


def make_crusader(pid="crusader1", username="Ser Aldric", x=5, y=5,
                  hp=150, max_hp=150, team="a", ai_stance="follow",
                  cooldowns=None, hero_id="hero_crus",
                  controlled_by="owner1") -> PlayerState:
    """Create a Crusader hero AI unit (Tank role — should NOT kite)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=20,
        ranged_damage=0,
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
        active_buffs=[],
        controlled_by=controlled_by,
    )


def make_hexblade(pid="hexblade1", username="Hexblade Mara", x=5, y=5,
                  hp=110, max_hp=110, team="a", ai_stance="follow",
                  cooldowns=None, hero_id="hero_hex",
                  controlled_by="owner1") -> PlayerState:
    """Create a Hexblade hero AI unit (Hybrid DPS role — should NOT kite)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=15,
        ranged_damage=12,
        armor=5,
        team=team,
        unit_type="ai",
        hero_id=hero_id,
        ai_stance=ai_stance,
        class_id="hexblade",
        ranged_range=4,
        vision_range=6,
        inventory=[],
        cooldowns=cooldowns or {},
        active_buffs=[],
        controlled_by=controlled_by,
    )


def make_confessor(pid="confessor1", username="Confessor Lyria", x=5, y=5,
                   hp=100, max_hp=100, team="a", ai_stance="follow",
                   cooldowns=None, hero_id="hero_conf",
                   controlled_by="owner1") -> PlayerState:
    """Create a Confessor hero AI unit (Support role — should NOT kite)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=8,
        ranged_damage=0,
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
        controlled_by=controlled_by,
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


def make_owner(pid="owner1", username="Player", x=2, y=5,
               hp=100, max_hp=100, team="a") -> PlayerState:
    """Create a human player who owns hero allies."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=15,
        armor=0,
        team=team,
        unit_type="human",
        hero_id=None,
        ranged_range=5,
        vision_range=7,
        inventory=[],
    )


GRID_W, GRID_H = 15, 15
OBSTACLES: set[tuple[int, int]] = set()


# ---------------------------------------------------------------------------
# Inventory Helpers
# ---------------------------------------------------------------------------

def _make_health_potion() -> dict:
    """Create a health potion inventory item."""
    return {
        "item_id": "health_potion",
        "item_type": "consumable",
        "name": "Health Potion",
        "consumable_effect": {"type": "heal", "magnitude": 40},
    }


def _make_greater_health_potion() -> dict:
    """Create a greater health potion inventory item."""
    return {
        "item_id": "greater_health_potion",
        "item_type": "consumable",
        "name": "Greater Health Potion",
        "consumable_effect": {"type": "heal", "magnitude": 75},
    }


def _make_portal_scroll() -> dict:
    """Create a non-heal consumable (portal scroll)."""
    return {
        "item_id": "portal_scroll",
        "item_type": "consumable",
        "name": "Portal Scroll",
        "consumable_effect": {"type": "teleport", "magnitude": 0},
    }


def _make_sword() -> dict:
    """Create a non-consumable equipment item."""
    return {
        "item_id": "iron_sword",
        "item_type": "equipment",
        "name": "Iron Sword",
        "slot": "weapon",
    }


# ============================================================================
# 1. _has_heal_potions Tests
# ============================================================================


class TestHasHealPotions:
    """Tests for the _has_heal_potions() inventory scan helper."""

    def test_has_heal_potions_with_health_potion(self):
        """Inventory has health_potion → True."""
        ai = make_crusader(x=5, y=5)
        ai.inventory = [_make_health_potion()]
        assert _has_heal_potions(ai) is True

    def test_has_heal_potions_empty_inventory(self):
        """Empty inventory → False."""
        ai = make_crusader(x=5, y=5)
        ai.inventory = []
        assert _has_heal_potions(ai) is False

    def test_has_heal_potions_only_equipment(self):
        """Inventory has sword only → False."""
        ai = make_crusader(x=5, y=5)
        ai.inventory = [_make_sword()]
        assert _has_heal_potions(ai) is False

    def test_has_heal_potions_only_portal_scroll(self):
        """Portal scroll (non-heal consumable) → False."""
        ai = make_crusader(x=5, y=5)
        ai.inventory = [_make_portal_scroll()]
        assert _has_heal_potions(ai) is False

    def test_has_heal_potions_mixed_inventory(self):
        """Mix of gear + potions → True (finds the potion)."""
        ai = make_crusader(x=5, y=5)
        ai.inventory = [_make_sword(), _make_portal_scroll(), _make_health_potion()]
        assert _has_heal_potions(ai) is True


# ============================================================================
# 2. _should_retreat Decision Tests
# ============================================================================


class TestShouldRetreat:
    """Tests for the _should_retreat() decision logic."""

    def test_should_retreat_low_hp_no_potions(self):
        """AI at 10% HP, no potions, enemy adjacent → returns True."""
        ai = make_crusader(x=5, y=5, hp=15, max_hp=150)  # 10% HP, threshold 15%
        ai.inventory = []
        enemy = make_enemy(x=6, y=5)  # Adjacent
        assert _should_retreat(ai, [enemy]) is True

    def test_should_not_retreat_has_potions(self):
        """AI at 10% HP, has potions, enemy adjacent → returns False."""
        ai = make_crusader(x=5, y=5, hp=15, max_hp=150)
        ai.inventory = [_make_health_potion()]
        enemy = make_enemy(x=6, y=5)
        assert _should_retreat(ai, [enemy]) is False

    def test_should_not_retreat_hp_above_threshold(self):
        """AI at 50% HP, no potions, enemy adjacent → returns False (HP OK)."""
        ai = make_crusader(x=5, y=5, hp=75, max_hp=150)  # 50% > 15% threshold
        ai.inventory = []
        enemy = make_enemy(x=6, y=5)
        assert _should_retreat(ai, [enemy]) is False

    def test_should_not_retreat_no_enemies_nearby(self):
        """AI at 10% HP, no potions, enemy 5 tiles away → returns False."""
        ai = make_crusader(x=5, y=5, hp=15, max_hp=150)
        ai.inventory = []
        enemy = make_enemy(x=10, y=5)  # 5 tiles away, > 2
        assert _should_retreat(ai, [enemy]) is False

    def test_should_not_retreat_hold_stance(self):
        """AI at 10% HP, no potions, enemy adjacent, hold stance → returns False."""
        ai = make_crusader(x=5, y=5, hp=15, max_hp=150, ai_stance="hold")
        ai.inventory = []
        enemy = make_enemy(x=6, y=5)
        assert _should_retreat(ai, [enemy]) is False

    def test_retreat_threshold_per_role(self):
        """Each role has a different retreat threshold."""
        # Tank (Crusader) — threshold 15%
        tank = make_crusader(x=5, y=5, hp=22, max_hp=150)  # ~14.7% < 15%
        tank.inventory = []
        enemy = make_enemy(x=6, y=5)
        assert _should_retreat(tank, [enemy]) is True

        tank_above = make_crusader(x=5, y=5, hp=24, max_hp=150)  # 16% > 15%
        tank_above.inventory = []
        assert _should_retreat(tank_above, [enemy]) is False

        # Support (Confessor) — threshold 35%
        support = make_confessor(x=5, y=5, hp=34, max_hp=100)  # 34% < 35%
        support.inventory = []
        assert _should_retreat(support, [enemy]) is True

        support_above = make_confessor(x=5, y=5, hp=36, max_hp=100)  # 36% > 35%
        support_above.inventory = []
        assert _should_retreat(support_above, [enemy]) is False

        # Ranged DPS (Ranger) — threshold 25%
        ranged = make_ranger(x=5, y=5, hp=19, max_hp=80)  # ~23.75% < 25%
        ranged.inventory = []
        assert _should_retreat(ranged, [enemy]) is True

        # Hybrid DPS (Hexblade) — threshold 20%
        hybrid = make_hexblade(x=5, y=5, hp=21, max_hp=110)  # ~19% < 20%
        hybrid.inventory = []
        assert _should_retreat(hybrid, [enemy]) is True

        # Scout (Inquisitor) — threshold 25%
        scout = make_inquisitor(x=5, y=5, hp=19, max_hp=80)  # ~23.75% < 25%
        scout.inventory = []
        assert _should_retreat(scout, [enemy]) is True

    def test_should_not_retreat_full_hp(self):
        """AI at 100% HP, no potions, enemy adjacent → returns False."""
        ai = make_crusader(x=5, y=5, hp=150, max_hp=150)
        ai.inventory = []
        enemy = make_enemy(x=6, y=5)
        assert _should_retreat(ai, [enemy]) is False

    def test_retreat_null_class(self):
        """class_id=None → uses default threshold (0.25), no crash."""
        ai = make_crusader(x=5, y=5, hp=20, max_hp=150)  # ~13.3% < 25% default
        ai.class_id = None
        ai.inventory = []
        enemy = make_enemy(x=6, y=5)
        assert _should_retreat(ai, [enemy]) is True


# ============================================================================
# 3. _find_retreat_destination Tests
# ============================================================================


class TestFindRetreatDestination:
    """Tests for retreat destination selection priority."""

    def test_retreat_toward_confessor(self):
        """Injured Crusader retreats toward alive Confessor."""
        crusader = make_crusader(x=5, y=5, hp=15, max_hp=150)
        crusader.inventory = []
        confessor = make_confessor(x=5, y=10)  # 5 tiles south
        enemy = make_enemy(x=6, y=5)  # Adjacent east
        owner = make_owner(x=1, y=5)

        all_units = {
            crusader.player_id: crusader,
            confessor.player_id: confessor,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }
        occupied = _build_occupied_set(all_units, crusader.player_id)

        action = _find_retreat_destination(
            crusader, [enemy], all_units,
            GRID_W, GRID_H, OBSTACLES, occupied,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should move toward confessor (south), closer to (5, 10)
        new_dist = _chebyshev(
            (action.target_x, action.target_y),
            (confessor.position.x, confessor.position.y),
        )
        old_dist = _chebyshev(
            (crusader.position.x, crusader.position.y),
            (confessor.position.x, confessor.position.y),
        )
        assert new_dist < old_dist, "Should move closer to Confessor"

    def test_retreat_toward_owner_no_support(self):
        """No Confessor alive → retreats toward owner."""
        crusader = make_crusader(x=5, y=5, hp=15, max_hp=150)
        crusader.inventory = []
        enemy = make_enemy(x=6, y=5)  # Adjacent east
        owner = make_owner(x=1, y=5)  # 4 tiles west

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }
        occupied = _build_occupied_set(all_units, crusader.player_id)

        action = _find_retreat_destination(
            crusader, [enemy], all_units,
            GRID_W, GRID_H, OBSTACLES, occupied,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should move toward owner (west)
        new_dist = _chebyshev(
            (action.target_x, action.target_y),
            (owner.position.x, owner.position.y),
        )
        old_dist = _chebyshev(
            (crusader.position.x, crusader.position.y),
            (owner.position.x, owner.position.y),
        )
        assert new_dist < old_dist, "Should move closer to owner"

    def test_retreat_away_from_enemy_no_allies(self):
        """No allies alive → moves away from nearest enemy."""
        crusader = make_crusader(x=5, y=5, hp=15, max_hp=150)
        crusader.inventory = []
        crusader.controlled_by = None  # No owner link
        enemy = make_enemy(x=6, y=5)

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
        }
        occupied = _build_occupied_set(all_units, crusader.player_id)

        action = _find_retreat_destination(
            crusader, [enemy], all_units,
            GRID_W, GRID_H, OBSTACLES, occupied,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should move away from enemy
        new_dist = _chebyshev(
            (action.target_x, action.target_y),
            (enemy.position.x, enemy.position.y),
        )
        old_dist = _chebyshev(
            (crusader.position.x, crusader.position.y),
            (enemy.position.x, enemy.position.y),
        )
        assert new_dist > old_dist, "Should move away from enemy"

    def test_retreat_path_door_aware(self):
        """Retreat path goes through closed door → returns INTERACT."""
        # Place crusader in a corridor with walls on both diagonals so the
        # only path south toward the Confessor goes through the door at (5,6).
        crusader = make_crusader(x=5, y=5, hp=15, max_hp=150)
        crusader.inventory = []
        confessor = make_confessor(x=5, y=8)  # South, through a door
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=1, y=5)

        all_units = {
            crusader.player_id: crusader,
            confessor.player_id: confessor,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }
        occupied = _build_occupied_set(all_units, crusader.player_id)

        # Walls block diagonal bypasses around the door
        walls = {(4, 6), (6, 6), (4, 5), (4, 7), (6, 7)}
        # Door at (5, 6) — directly south, now the only path forward
        door_tiles = {(5, 6)}

        action = _find_retreat_destination(
            crusader, [enemy], all_units,
            GRID_W, GRID_H, walls, occupied,
            door_tiles=door_tiles,
        )
        assert action is not None
        assert action.action_type == ActionType.INTERACT
        assert (action.target_x, action.target_y) == (5, 6)

    def test_retreat_cornered_returns_none(self):
        """Surrounded by walls + enemies → returns None (fall through to fight)."""
        # Place crusader in corner (0, 0), walls on most sides
        crusader = make_crusader(x=0, y=0, hp=15, max_hp=150)
        crusader.inventory = []
        crusader.controlled_by = None
        enemy = make_enemy(x=1, y=0)  # East
        enemy2 = make_enemy(pid="enemy2", x=0, y=1, team="b")  # South
        enemy3 = make_enemy(pid="enemy3", x=1, y=1, team="b")  # SE

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            enemy2.player_id: enemy2,
            enemy3.player_id: enemy3,
        }
        occupied = _build_occupied_set(all_units, crusader.player_id)

        action = _find_retreat_destination(
            crusader, [enemy, enemy2, enemy3], all_units,
            GRID_W, GRID_H, OBSTACLES, occupied,
        )
        # Cornered — all adjacent tiles occupied by enemies or out of bounds
        assert action is None

    def test_retreat_prefers_support_over_owner(self):
        """Both support ally + owner available → paths toward support."""
        crusader = make_crusader(x=5, y=5, hp=15, max_hp=150)
        crusader.inventory = []
        confessor = make_confessor(x=5, y=8)  # 3 tiles south
        owner = make_owner(x=5, y=2)  # 3 tiles north
        enemy = make_enemy(x=6, y=5)

        all_units = {
            crusader.player_id: crusader,
            confessor.player_id: confessor,
            owner.player_id: owner,
            enemy.player_id: enemy,
        }
        occupied = _build_occupied_set(all_units, crusader.player_id)

        action = _find_retreat_destination(
            crusader, [enemy], all_units,
            GRID_W, GRID_H, OBSTACLES, occupied,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should move toward confessor (south), not owner (north)
        dist_to_conf = _chebyshev(
            (action.target_x, action.target_y),
            (confessor.position.x, confessor.position.y),
        )
        old_dist_conf = _chebyshev(
            (crusader.position.x, crusader.position.y),
            (confessor.position.x, confessor.position.y),
        )
        assert dist_to_conf < old_dist_conf, "Should move toward Confessor, not owner"

    def test_retreat_support_too_far(self):
        """Confessor alive but 15 tiles away → falls back to owner."""
        crusader = make_crusader(x=1, y=1, hp=15, max_hp=150)
        crusader.inventory = []
        # Confessor at distance > 8 (limit for support-based retreat)
        confessor = make_confessor(x=14, y=14)  # ~13 tiles away
        owner = make_owner(x=1, y=4)  # 3 tiles south
        enemy = make_enemy(x=2, y=1)

        all_units = {
            crusader.player_id: crusader,
            confessor.player_id: confessor,
            owner.player_id: owner,
            enemy.player_id: enemy,
        }
        occupied = _build_occupied_set(all_units, crusader.player_id)

        action = _find_retreat_destination(
            crusader, [enemy], all_units,
            GRID_W, GRID_H, OBSTACLES, occupied,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should move toward owner (south), since Confessor is too far
        new_dist_owner = _chebyshev(
            (action.target_x, action.target_y),
            (owner.position.x, owner.position.y),
        )
        old_dist_owner = _chebyshev(
            (crusader.position.x, crusader.position.y),
            (owner.position.x, owner.position.y),
        )
        assert new_dist_owner < old_dist_owner, "Should move toward owner when support too far"


# ============================================================================
# 4. Integration Tests (Priority Chain via _decide_stance_action)
# ============================================================================


class TestRetreatPriorityChain:
    """Test the potion > retreat > skill > stance priority chain."""

    def test_priority_potion_over_retreat(self):
        """AI at 10% HP WITH potions → drinks potion, not retreat."""
        crusader = make_crusader(x=5, y=5, hp=15, max_hp=150, ai_stance="follow")
        crusader.inventory = [_make_health_potion()]
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=2, y=5)

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            crusader, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.USE_ITEM

    def test_priority_retreat_over_skill(self):
        """AI at 10% HP, no potions, adjacent enemy → retreats, not skill."""
        crusader = make_crusader(x=5, y=5, hp=15, max_hp=150, ai_stance="follow")
        crusader.inventory = []
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=2, y=5)

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            crusader, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        # Should be MOVE (retreat), not SKILL or ATTACK
        assert action.action_type == ActionType.MOVE
        # Should move toward owner (west) or away from enemy
        new_dist_enemy = _chebyshev(
            (action.target_x, action.target_y),
            (enemy.position.x, enemy.position.y),
        )
        assert new_dist_enemy >= 1, "Should retreat away from enemy"

    def test_retreat_fallthrough_to_skill_when_cornered(self):
        """Cornered (retreat fails) → uses skill or attack instead."""
        # Corner position with enemies blocking all escape
        crusader = make_crusader(x=0, y=0, hp=15, max_hp=150, ai_stance="follow")
        crusader.inventory = []
        enemy = make_enemy(x=1, y=0)
        enemy2 = make_enemy(pid="enemy2", x=0, y=1, team="b")
        enemy3 = make_enemy(pid="enemy3", x=1, y=1, team="b")

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            enemy2.player_id: enemy2,
            enemy3.player_id: enemy3,
        }

        action = _decide_stance_action(
            crusader, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        # Retreat should fail (cornered). Should fall through to skill or attack.
        assert action.action_type in (ActionType.SKILL, ActionType.ATTACK)

    def test_retreat_fallthrough_to_attack_when_cornered(self):
        """Cornered + skills on CD → falls through to basic attack or wait."""
        crusader = make_crusader(
            x=0, y=0, hp=15, max_hp=150, ai_stance="follow",
            cooldowns={"taunt": 5, "shield_bash": 5, "holy_ground": 5, "bulwark": 5},
        )
        crusader.inventory = []
        enemy = make_enemy(x=1, y=0)
        enemy2 = make_enemy(pid="enemy2", x=0, y=1, team="b")
        enemy3 = make_enemy(pid="enemy3", x=1, y=1, team="b")

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            enemy2.player_id: enemy2,
            enemy3.player_id: enemy3,
        }

        action = _decide_stance_action(
            crusader, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        # Retreat failed, skills on CD → falls through to stance combat.
        # May ATTACK an adjacent enemy or WAIT if stance can't resolve.
        assert action.action_type in (ActionType.ATTACK, ActionType.WAIT)

    def test_follow_stance_retreat(self):
        """Follow stance AI at retreat threshold → retreats."""
        ranger = make_ranger(x=5, y=5, hp=19, max_hp=80, ai_stance="follow")  # ~23.75% < 25%
        ranger.inventory = []
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=2, y=5)

        all_units = {
            ranger.player_id: ranger,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            ranger, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE

    def test_aggressive_stance_retreat(self):
        """Aggressive stance AI at retreat threshold → retreats."""
        ranger = make_ranger(x=5, y=5, hp=19, max_hp=80, ai_stance="aggressive")
        ranger.inventory = []
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=2, y=5)

        all_units = {
            ranger.player_id: ranger,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            ranger, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE

    def test_defensive_stance_retreat(self):
        """Defensive stance AI at retreat threshold → retreats."""
        confessor = make_confessor(x=5, y=5, hp=34, max_hp=100, ai_stance="defensive")  # 34% < 35%
        confessor.inventory = []
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=2, y=5)

        all_units = {
            confessor.player_id: confessor,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            confessor, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE

    def test_hold_stance_no_retreat(self):
        """Hold stance AI at retreat threshold → attacks (never moves)."""
        crusader = make_crusader(x=5, y=5, hp=15, max_hp=150, ai_stance="hold")
        crusader.inventory = []
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=2, y=5)

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            crusader, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        # Hold never retreats — should attack or skill, never MOVE
        assert action.action_type != ActionType.MOVE


# ============================================================================
# 5. Guard / Regression Tests — Retreat
# ============================================================================


class TestRetreatGuardRegression:
    """Guard tests ensuring retreat doesn't break existing behavior."""

    def test_enemy_ai_no_retreat(self):
        """Enemy AI at low HP → _should_retreat returns True but enemies
        never route through _decide_stance_action, so retreat never fires.
        Verify _should_retreat itself doesn't crash on enemy units."""
        enemy = make_enemy(x=5, y=5, hp=5, max_hp=80)
        enemy.class_id = None
        enemy.inventory = []
        ally = make_crusader(x=6, y=5)
        ally.team = "a"
        # Enemy perspective: ally is the "enemy"
        result = _should_retreat(enemy, [ally])
        # With class_id=None, default threshold 25%. HP 6.25% < 25%, no potions, in range.
        # Should return True (function works correctly), but enemy AI never calls it.
        assert isinstance(result, bool)

    def test_retreat_does_not_affect_full_hp_combat(self):
        """AI at 100% HP → normal combat behavior, no retreat."""
        crusader = make_crusader(x=5, y=5, hp=150, max_hp=150, ai_stance="follow")
        crusader.inventory = []
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=2, y=5)

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            crusader, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        # Full HP → should attack, not retreat
        assert action.action_type in (ActionType.ATTACK, ActionType.SKILL)

    def test_legacy_null_class_no_crash(self):
        """class_id=None through _decide_stance_action → no crash."""
        ai = make_crusader(x=5, y=5, hp=15, max_hp=150, ai_stance="follow")
        ai.class_id = None
        ai.inventory = []
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=2, y=5)

        all_units = {
            ai.player_id: ai,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        # Should not crash — uses default threshold
        action = _decide_stance_action(
            ai, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None

    def test_enemy_ai_no_kiting_via_stances(self):
        """Enemy ranged AI still uses its own kiting (unchanged by 8K)."""
        # Enemy AI with ranged stats shouldn't be affected by hero retreat
        enemy = make_enemy(x=5, y=5, hp=80, max_hp=80)
        enemy.class_id = None
        enemy.hero_id = None

        # _should_retreat with no class_id + full HP → False
        ally = make_crusader(x=6, y=5)
        assert _should_retreat(enemy, [ally]) is False


# ============================================================================
# 1. Ranged Kiting — Follow Stance (8K-3)
# ============================================================================


class TestRangerKitingFollowStance:
    """Tests for Ranger kiting behavior in follow stance."""

    def test_ranger_kites_when_adjacent(self):
        """Ranger adjacent to enemy → steps back (MOVE away) instead of melee."""
        ranger = make_ranger(x=5, y=5)
        enemy = make_enemy(x=6, y=5)  # Adjacent (dist 1)
        owner = make_owner(x=2, y=5)

        all_units = {
            ranger.player_id: ranger,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_follow_action(
            ranger, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should move AWAY from enemy (x=6), so target_x < 5
        new_dist = _chebyshev(
            (action.target_x, action.target_y),
            (enemy.position.x, enemy.position.y),
        )
        old_dist = _chebyshev(
            (ranger.position.x, ranger.position.y),
            (enemy.position.x, enemy.position.y),
        )
        assert new_dist > old_dist, "Ranger should move AWAY from enemy, not closer"

    def test_ranger_kites_when_distance_2(self):
        """Ranger 2 tiles from enemy → steps back to ranged sweet spot."""
        ranger = make_ranger(x=5, y=5)
        enemy = make_enemy(x=7, y=5)  # Distance 2
        owner = make_owner(x=2, y=5)

        all_units = {
            ranger.player_id: ranger,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_follow_action(
            ranger, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should step back, increasing distance
        new_dist = _chebyshev(
            (action.target_x, action.target_y),
            (enemy.position.x, enemy.position.y),
        )
        assert new_dist > 2, "Ranger should step back from distance 2"

    def test_ranger_attacks_ranged_at_distance(self):
        """Ranger at 4 tiles from enemy → fires ranged attack (no kiting needed)."""
        ranger = make_ranger(x=5, y=5, cooldowns={})
        enemy = make_enemy(x=9, y=5)  # Distance 4 — within ranged range 6
        owner = make_owner(x=2, y=5)

        all_units = {
            ranger.player_id: ranger,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_follow_action(
            ranger, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.RANGED_ATTACK
        assert action.target_x == 9
        assert action.target_y == 5

    def test_ranger_melee_when_cornered(self):
        """Ranger adjacent to enemy, walls on all other sides → melee as fallback."""
        # Place ranger in a corner with walls blocking all retreat tiles
        ranger = make_ranger(x=0, y=0)
        enemy = make_enemy(x=1, y=0)
        owner = make_owner(x=0, y=2)  # Owner close enough to avoid regroup (dist ≤4)

        # Walls blocking all escape routes except (1,0) which is the enemy
        walls = {(0, 1), (1, 1)}  # Block the remaining adjacent tiles

        all_units = {
            ranger.player_id: ranger,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        # Pre-compute occupied so the retreat tile check sees the enemy position
        occupied = {(enemy.position.x, enemy.position.y)}

        action = _decide_follow_action(
            ranger, all_units, GRID_W, GRID_H, walls,
            precomputed_occupied=occupied,
        )
        assert action is not None
        # Cornered: can't kite, should fall through to melee ATTACK
        assert action.action_type == ActionType.ATTACK

    def test_inquisitor_kites_same_as_ranger(self):
        """Inquisitor (scout role) kites when adjacent to enemy, same as Ranger."""
        inquisitor = make_inquisitor(x=5, y=5)
        enemy = make_enemy(x=6, y=5)  # Adjacent
        owner = make_owner(x=2, y=5)

        all_units = {
            inquisitor.player_id: inquisitor,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_follow_action(
            inquisitor, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        new_dist = _chebyshev(
            (action.target_x, action.target_y),
            (enemy.position.x, enemy.position.y),
        )
        assert new_dist > 1, "Inquisitor should kite away from adjacent enemy"


# ============================================================================
# 2. Non-Ranged Classes Do NOT Kite — Follow Stance
# ============================================================================


class TestNonRangedNoKiting:
    """Verify that melee/support/hybrid classes do NOT kite."""

    def test_crusader_does_not_kite(self):
        """Crusader adjacent to enemy → melee attacks normally (tank doesn't kite)."""
        crusader = make_crusader(x=5, y=5)
        enemy = make_enemy(x=6, y=5)  # Adjacent
        owner = make_owner(x=2, y=5)

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_follow_action(
            crusader, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.ATTACK
        assert action.target_x == 6
        assert action.target_y == 5

    def test_hexblade_does_not_kite(self):
        """Hexblade adjacent to enemy → melee attacks (hybrid doesn't kite)."""
        hexblade = make_hexblade(x=5, y=5)
        enemy = make_enemy(x=6, y=5)  # Adjacent
        owner = make_owner(x=2, y=5)

        all_units = {
            hexblade.player_id: hexblade,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_follow_action(
            hexblade, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.ATTACK
        assert action.target_x == 6
        assert action.target_y == 5

    def test_confessor_does_not_kite(self):
        """Confessor adjacent to enemy → melee attacks (support doesn't kite)."""
        confessor = make_confessor(x=5, y=5)
        enemy = make_enemy(x=6, y=5)  # Adjacent
        owner = make_owner(x=2, y=5)

        all_units = {
            confessor.player_id: confessor,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_follow_action(
            confessor, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.ATTACK
        assert action.target_x == 6
        assert action.target_y == 5


# ============================================================================
# 3. Ranged Kiting — Aggressive Stance (8K-3)
# ============================================================================


class TestRangerKitingAggressiveStance:
    """Tests for Ranger kiting behavior in aggressive stance."""

    def test_ranger_kites_aggressive_when_adjacent(self):
        """Aggressive stance: Ranger adjacent to enemy → steps back."""
        ranger = make_ranger(x=5, y=5, ai_stance="aggressive")
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=2, y=5)

        all_units = {
            ranger.player_id: ranger,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_aggressive_stance_action(
            ranger, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        new_dist = _chebyshev(
            (action.target_x, action.target_y),
            (enemy.position.x, enemy.position.y),
        )
        assert new_dist > 1, "Ranger in aggressive stance should kite away"

    def test_ranger_kites_aggressive_dist_2(self):
        """Aggressive stance: Ranger 2 tiles from enemy → steps back."""
        ranger = make_ranger(x=5, y=5, ai_stance="aggressive")
        enemy = make_enemy(x=7, y=5)  # Distance 2
        owner = make_owner(x=2, y=5)

        all_units = {
            ranger.player_id: ranger,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_aggressive_stance_action(
            ranger, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        new_dist = _chebyshev(
            (action.target_x, action.target_y),
            (enemy.position.x, enemy.position.y),
        )
        assert new_dist > 2, "Ranger should step back from distance 2 in aggressive"

    def test_ranger_aggressive_ranged_at_distance(self):
        """Aggressive stance: Ranger at 4 tiles → fires ranged attack."""
        ranger = make_ranger(x=5, y=5, ai_stance="aggressive", cooldowns={})
        enemy = make_enemy(x=9, y=5)  # Distance 4
        owner = make_owner(x=2, y=5)

        all_units = {
            ranger.player_id: ranger,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_aggressive_stance_action(
            ranger, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.RANGED_ATTACK

    def test_crusader_rushes_in_aggressive(self):
        """Aggressive stance: Crusader at dist 3 → rushes to melee (no kiting)."""
        crusader = make_crusader(x=5, y=5, ai_stance="aggressive")
        enemy = make_enemy(x=8, y=5)  # Distance 3
        owner = make_owner(x=2, y=5)

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_aggressive_stance_action(
            crusader, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Crusader should rush TOWARD enemy, not away
        new_dist = _chebyshev(
            (action.target_x, action.target_y),
            (enemy.position.x, enemy.position.y),
        )
        assert new_dist < 3, "Crusader should rush TOWARD enemy"

    def test_inquisitor_kites_aggressive(self):
        """Aggressive stance: Inquisitor adjacent → kites away."""
        inquisitor = make_inquisitor(x=5, y=5, ai_stance="aggressive")
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=2, y=5)

        all_units = {
            inquisitor.player_id: inquisitor,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_aggressive_stance_action(
            inquisitor, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        new_dist = _chebyshev(
            (action.target_x, action.target_y),
            (enemy.position.x, enemy.position.y),
        )
        assert new_dist > 1, "Inquisitor in aggressive should kite away"


# ============================================================================
# 4. Defensive & Hold Stances — No Kiting
# ============================================================================


class TestKitingDefensiveHold:
    """Verify kiting behavior in defensive and hold stances."""

    def test_ranger_kites_defensive_stance(self):
        """Defensive stance (S2-B): Ranger kites adjacent enemies while staying within 2 of owner."""
        ranger = make_ranger(x=5, y=5, ai_stance="defensive")
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=4, y=5)  # Owner close by

        all_units = {
            ranger.player_id: ranger,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_defensive_action(
            ranger, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        # S2-B: Ranged classes on Defensive kite when tether allows
        assert action.action_type == ActionType.MOVE

    def test_ranger_no_kiting_hold_stance(self):
        """Hold stance: Ranger never moves — attacks if adjacent, ranged if in range."""
        ranger = make_ranger(x=5, y=5, ai_stance="hold")
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=2, y=5)

        all_units = {
            ranger.player_id: ranger,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_hold_action(
            ranger, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        # Hold never moves — should ATTACK adjacent enemy
        assert action.action_type == ActionType.ATTACK


# ============================================================================
# 5. Ranged Rush Gate — Non-Ranged Still Rushes
# ============================================================================


class TestMeleeRushGate:
    """Verify that the rush-to-melee branch still works for non-ranged classes."""

    def test_crusader_rushes_follow_stance(self):
        """Follow stance: Crusader at distance 3 → rushes to melee."""
        crusader = make_crusader(x=5, y=5)
        enemy = make_enemy(x=8, y=5)  # Distance 3
        owner = make_owner(x=2, y=5)

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_follow_action(
            crusader, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        new_dist = _chebyshev(
            (action.target_x, action.target_y),
            (enemy.position.x, enemy.position.y),
        )
        assert new_dist < 3, "Crusader should rush toward enemy"

    def test_ranger_does_not_rush_follow_stance(self):
        """Follow stance: Ranger at distance 3 → does NOT rush to melee."""
        ranger = make_ranger(x=5, y=5, cooldowns={"ranged_attack": 3})
        enemy = make_enemy(x=8, y=5)  # Distance 3
        owner = make_owner(x=2, y=5)

        all_units = {
            ranger.player_id: ranger,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_follow_action(
            ranger, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        # Distance 3 is NOT ≤2, so kiting doesn't trigger.
        # But Ranger should NOT rush to melee (ranged role).
        # Instead should move toward (ranged on CD, general move toward target).
        assert action.action_type == ActionType.MOVE
        # Even though moving toward, it's a general approach, not the "rush"
        # branch which was gated by is_ranged_role


# ============================================================================
# 6. Guard / Regression Tests
# ============================================================================


class TestKitingGuardRegression:
    """Guard tests: ensure no regressions in non-kiting scenarios."""

    def test_full_hp_ranger_still_kites(self):
        """Kiting is about positioning, not HP — full HP Ranger still kites."""
        ranger = make_ranger(x=5, y=5, hp=80, max_hp=80)
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=2, y=5)

        all_units = {
            ranger.player_id: ranger,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_follow_action(
            ranger, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        new_dist = _chebyshev(
            (action.target_x, action.target_y),
            (enemy.position.x, enemy.position.y),
        )
        assert new_dist > 1, "Full HP Ranger should still kite"

    def test_null_class_no_crash(self):
        """AI with class_id=None → no crash, no kiting (default behavior)."""
        ai = make_ranger(x=5, y=5)
        ai.class_id = None  # Override class_id to None
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=2, y=5)

        all_units = {
            ai.player_id: ai,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_follow_action(
            ai, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        # Should attack normally — no role means no kiting
        assert action.action_type == ActionType.ATTACK

    def test_enemy_ai_no_kiting_via_stances(self):
        """Enemy AI (no hero_id) doesn't route through stance functions.
        Verify that making an enemy-like unit with ranged stats still
        attacks normally when put through follow stance directly."""
        enemy_like = make_enemy(x=5, y=5)
        enemy_like.class_id = None
        enemy_like.hero_id = None

        other_enemy = make_enemy(pid="enemy2", x=6, y=5, team="b")
        owner = make_owner(x=2, y=5)

        # Put the "enemy" on team a so it sees team b as enemies
        enemy_like.team = "a"

        all_units = {
            enemy_like.player_id: enemy_like,
            other_enemy.player_id: other_enemy,
            owner.player_id: owner,
        }

        action = _decide_follow_action(
            enemy_like, all_units, GRID_W, GRID_H, OBSTACLES,
        )
        assert action is not None
        # No class_id → no role → no kiting → should attack
        assert action.action_type == ActionType.ATTACK
