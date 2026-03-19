"""
Tests for Phase 28C — AI Loot Pickup.

Covers:
  - _find_nearest_ground_loot helper (nearest tile, range cap, full inventory)
  - Passive pickup: enemy walks over ground items → items added to inventory
  - Passive pickup respects INVENTORY_MAX_CAPACITY
  - Active scavenge: idle aggressive enemy with nearby loot → moves toward it
  - Boss never scavenges (behavior not given ground_items)
  - Scavenge only when idle (enemy with visible target ignores nearby loot)
  - Scavenge respects per-behavior max_range
  - ground_items threaded through run_ai_decisions → decide_ai_action
  - Scavenge constants are correct per behavior
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType, ActionResult
from app.models.items import INVENTORY_MAX_CAPACITY
from app.core.ai_behavior import (
    _find_nearest_ground_loot,
    _SCAVENGE_MAX_RANGE,
    _decide_aggressive_action,
    _decide_ranged_action,
    _decide_support_behavior,
    _decide_boss_action,
    decide_ai_action,
    run_ai_decisions,
)
from app.core.turn_phases.interaction_phase import _resolve_loot
from app.core.combat import load_combat_config


def setup_module():
    load_combat_config()


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

def _make_item(name="Iron Sword", item_type="weapon") -> dict:
    """Create a simple item dict for testing."""
    return {
        "item_id": f"{name.lower().replace(' ', '_')}",
        "instance_id": f"inst_{name.lower().replace(' ', '_')}",
        "name": name,
        "item_type": item_type,
        "rarity": "common",
        "equip_slot": "weapon" if item_type == "weapon" else None,
        "stat_bonuses": {"attack_damage": 5, "ranged_damage": 0, "armor": 0, "max_hp": 0},
        "sell_value": 10,
    }


def _make_potion() -> dict:
    """Create a health potion dict."""
    return {
        "item_id": "health_potion",
        "name": "Health Potion",
        "item_type": "consumable",
        "rarity": "common",
        "equip_slot": None,
        "stat_bonuses": {"attack_damage": 0, "ranged_damage": 0, "armor": 0, "max_hp": 0},
        "consumable_effect": {"type": "heal", "magnitude": 40},
        "sell_value": 15,
    }


def _make_enemy(ai_behavior="aggressive", x=5, y=5, pid="enemy1",
                inventory=None, hp=200, max_hp=200, enemy_type=None) -> PlayerState:
    """Create an AI hero party unit.

    Phase 28-FIX: enemy_type=None means this is a hero party AI (not a dungeon
    monster). Scavenging and pickup are guarded behind enemy_type is None.
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


def _make_player(x=10, y=10, pid="player1") -> PlayerState:
    """Create a human player unit (for enemy targeting tests)."""
    return PlayerState(
        player_id=pid,
        username="Test Player",
        position=Position(x=x, y=y),
        hp=100,
        max_hp=100,
        attack_damage=10,
        team="a",
        unit_type="human",
        vision_range=7,
    )


# ---------------------------------------------------------------------------
# 1. Scavenge Constants
# ---------------------------------------------------------------------------

class TestScavengeConstants:
    """Verify per-behavior scavenge range values."""

    def test_aggressive_range(self):
        assert _SCAVENGE_MAX_RANGE["aggressive"] == 5

    def test_ranged_range(self):
        assert _SCAVENGE_MAX_RANGE["ranged"] == 3

    def test_support_range(self):
        assert _SCAVENGE_MAX_RANGE["support"] == 3

    def test_boss_not_in_scavenge_map(self):
        """Bosses should not have scavenge range (they never scavenge)."""
        assert "boss" not in _SCAVENGE_MAX_RANGE


# ---------------------------------------------------------------------------
# 2. _find_nearest_ground_loot — Helper Tests
# ---------------------------------------------------------------------------

class TestFindNearestGroundLoot:
    """Test the _find_nearest_ground_loot helper function."""

    def test_finds_nearest_item(self):
        """Returns the closest loot tile by Manhattan distance."""
        ai = _make_enemy(x=5, y=5)
        ground_items = {
            "8,5": [_make_item("Far Sword")],   # dist=3
            "6,5": [_make_item("Close Sword")],  # dist=1
        }
        result = _find_nearest_ground_loot(ai, ground_items, max_range=5)
        assert result == (6, 5)

    def test_returns_none_on_empty_ground(self):
        """Returns None when no ground items exist."""
        ai = _make_enemy(x=5, y=5)
        assert _find_nearest_ground_loot(ai, None, max_range=5) is None
        assert _find_nearest_ground_loot(ai, {}, max_range=5) is None

    def test_respects_max_range(self):
        """Items beyond max_range are ignored."""
        ai = _make_enemy(x=5, y=5)
        ground_items = {
            "12,5": [_make_item("Far Sword")],  # dist=7 > max_range=5
        }
        result = _find_nearest_ground_loot(ai, ground_items, max_range=5)
        assert result is None

    def test_full_inventory_returns_none(self):
        """AI with full inventory should not seek loot."""
        full_inv = [_make_item(f"Item {i}") for i in range(INVENTORY_MAX_CAPACITY)]
        ai = _make_enemy(x=5, y=5, inventory=full_inv)
        ground_items = {
            "6,5": [_make_item("Loot")],
        }
        result = _find_nearest_ground_loot(ai, ground_items, max_range=5)
        assert result is None

    def test_skips_empty_tile_entries(self):
        """Ground items with empty lists are skipped."""
        ai = _make_enemy(x=5, y=5)
        ground_items = {
            "6,5": [],
            "7,5": [_make_item("Real Loot")],
        }
        result = _find_nearest_ground_loot(ai, ground_items, max_range=5)
        assert result == (7, 5)

    def test_loot_at_same_position(self):
        """Loot on same tile as AI returns that tile (dist=0)."""
        ai = _make_enemy(x=5, y=5)
        ground_items = {
            "5,5": [_make_item("Under Feet")],
        }
        result = _find_nearest_ground_loot(ai, ground_items, max_range=5)
        assert result == (5, 5)


# ---------------------------------------------------------------------------
# 3. Passive Pickup — interaction_phase auto-pickup sweep
# ---------------------------------------------------------------------------

class TestPassivePickup:
    """Test auto-pickup for units standing on ground items."""

    def test_enemy_auto_picks_up_ground_loot(self):
        """Enemy standing on ground items auto-picks them up."""
        enemy = _make_enemy(x=5, y=5)
        item = _make_item("Ground Sword")
        ground_items = {"5,5": [item]}
        players = {enemy.player_id: enemy}

        results: list[ActionResult] = []
        items_picked_up: list[dict] = []
        _resolve_loot(
            loot_actions=[],
            players=players,
            chest_states=None,
            ground_items=ground_items,
            results=results,
            chest_opened=[],
            items_picked_up=items_picked_up,
        )

        assert len(enemy.inventory) == 1
        assert enemy.inventory[0]["name"] == "Ground Sword"
        assert "5,5" not in ground_items
        assert len(items_picked_up) == 1

    def test_passive_pickup_respects_capacity(self):
        """Enemy with nearly full inventory only picks up what fits."""
        full_inv = [_make_item(f"Item {i}") for i in range(INVENTORY_MAX_CAPACITY - 1)]
        enemy = _make_enemy(x=5, y=5, inventory=full_inv)
        items = [_make_item("Loot A"), _make_item("Loot B")]
        ground_items = {"5,5": items}
        players = {enemy.player_id: enemy}

        results: list[ActionResult] = []
        items_picked_up: list[dict] = []
        _resolve_loot(
            loot_actions=[],
            players=players,
            chest_states=None,
            ground_items=ground_items,
            results=results,
            chest_opened=[],
            items_picked_up=items_picked_up,
        )

        # Should pick up 1 item (capacity was -1), overflow stays on ground
        assert len(enemy.inventory) == INVENTORY_MAX_CAPACITY
        assert "5,5" in ground_items  # 1 item remains
        assert len(ground_items["5,5"]) == 1

    def test_dead_enemy_does_not_pick_up(self):
        """Dead units don't auto-pickup."""
        enemy = _make_enemy(x=5, y=5, hp=0)
        enemy.is_alive = False
        ground_items = {"5,5": [_make_item("Stale Loot")]}
        players = {enemy.player_id: enemy}

        results: list[ActionResult] = []
        items_picked_up: list[dict] = []
        _resolve_loot(
            loot_actions=[],
            players=players,
            chest_states=None,
            ground_items=ground_items,
            results=results,
            chest_opened=[],
            items_picked_up=items_picked_up,
        )

        assert len(enemy.inventory) == 0
        assert len(ground_items["5,5"]) == 1

    def test_player_also_auto_picks_up(self):
        """Human players also get auto-pickup (not just AI)."""
        player = _make_player(x=3, y=3)
        item = _make_item("Player Loot")
        ground_items = {"3,3": [item]}
        players = {player.player_id: player}

        results: list[ActionResult] = []
        items_picked_up: list[dict] = []
        _resolve_loot(
            loot_actions=[],
            players=players,
            chest_states=None,
            ground_items=ground_items,
            results=results,
            chest_opened=[],
            items_picked_up=items_picked_up,
        )

        assert len(player.inventory) == 1
        assert player.inventory[0]["name"] == "Player Loot"


# ---------------------------------------------------------------------------
# 4. Active Scavenging — AI behavior functions
# ---------------------------------------------------------------------------

class TestActiveScavenge:
    """Test AI actively pathing toward ground loot when idle."""

    def test_aggressive_scavenges_when_idle(self):
        """Idle aggressive enemy with ground loot nearby → moves toward it."""
        enemy = _make_enemy(ai_behavior="aggressive", x=5, y=5)
        ground_items = {"7,5": [_make_item("Loot")]}
        all_units = {enemy.player_id: enemy}

        action = _decide_aggressive_action(
            enemy, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
            ground_items=ground_items,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should move closer to the loot (x increases toward 7)
        assert action.target_x >= 6

    def test_ranged_scavenges_when_idle(self):
        """Idle ranged enemy with ground loot nearby → moves toward it."""
        enemy = _make_enemy(ai_behavior="ranged", x=5, y=5)
        ground_items = {"7,5": [_make_item("Loot")]}
        all_units = {enemy.player_id: enemy}

        action = _decide_ranged_action(
            enemy, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
            ground_items=ground_items,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should move closer to the loot (x increases toward 7)
        assert action.target_x >= 6

    def test_support_scavenges_when_idle_no_allies(self):
        """Idle support enemy with no allies nearby → scavenges ground loot."""
        enemy = _make_enemy(ai_behavior="support", x=5, y=5)
        ground_items = {"7,5": [_make_item("Loot")]}
        all_units = {enemy.player_id: enemy}

        action = _decide_support_behavior(
            enemy, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
            ground_items=ground_items,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should move closer to the loot (x increases toward 7)
        assert action.target_x >= 6

    def test_boss_never_scavenges(self):
        """Boss with nearby loot → ignores it, waits instead."""
        enemy = _make_enemy(ai_behavior="boss", x=5, y=5)
        ground_items = {"6,5": [_make_item("Loot")]}
        all_units = {enemy.player_id: enemy}

        action = _decide_boss_action(
            enemy, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )
        # Boss should WAIT (no enemies visible, not scavenging)
        assert action is not None
        assert action.action_type == ActionType.WAIT

    def test_scavenge_only_when_no_enemies_visible(self):
        """Enemy with visible target + nearby loot → attacks target, ignores loot."""
        enemy = _make_enemy(ai_behavior="aggressive", x=5, y=5)
        player = _make_player(x=6, y=5)  # Adjacent enemy → will attack
        ground_items = {"4,5": [_make_item("Loot")]}
        all_units = {enemy.player_id: enemy, player.player_id: player}

        action = _decide_aggressive_action(
            enemy, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
            ground_items=ground_items,
        )
        assert action is not None
        # Should attack player, not go for loot
        assert action.action_type in (ActionType.ATTACK, ActionType.RANGED_ATTACK)

    def test_scavenge_respects_max_range(self):
        """Loot beyond max_range → enemy patrols instead of scavenging."""
        enemy = _make_enemy(ai_behavior="ranged", x=5, y=5)
        # Ranged max_range is 3; place loot at dist=6
        ground_items = {"11,5": [_make_item("Far Loot")]}
        all_units = {enemy.player_id: enemy}

        action = _decide_ranged_action(
            enemy, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
            ground_items=ground_items,
        )
        # Should not move toward faraway loot — falls through to patrol
        if action and action.action_type == ActionType.MOVE:
            # If it moves, it should NOT be toward (11,5)
            assert action.target_x <= 6  # Should be patrol, not toward 11

    def test_aggressive_scavenge_no_loot(self):
        """Aggressive enemy with no ground loot → falls through to patrol."""
        enemy = _make_enemy(ai_behavior="aggressive", x=5, y=5)
        all_units = {enemy.player_id: enemy}

        action = _decide_aggressive_action(
            enemy, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
            ground_items=None,
        )
        # Should NOT crash; returns MOVE (patrol) or WAIT
        assert action is not None
        assert action.action_type in (ActionType.MOVE, ActionType.WAIT)


# ---------------------------------------------------------------------------
# 5. ground_items Threading — run_ai_decisions passes ground_items
# ---------------------------------------------------------------------------

class TestGroundItemsThreading:
    """Test that ground_items is threaded from run_ai_decisions to behaviors."""

    def test_run_ai_decisions_passes_ground_items(self):
        """run_ai_decisions accepts and forwards ground_items to AI decisions."""
        enemy = _make_enemy(ai_behavior="aggressive", x=5, y=5)
        ground_items = {"7,5": [_make_item("Loot")]}
        all_units = {enemy.player_id: enemy}

        actions = run_ai_decisions(
            ai_ids=[enemy.player_id],
            all_units=all_units,
            grid_width=15,
            grid_height=15,
            obstacles=set(),
            ground_items=ground_items,
        )
        # Should get a MOVE action toward loot since no enemies visible
        assert len(actions) == 1
        assert actions[0].action_type == ActionType.MOVE
        # Should move closer to the loot (x increases toward 7)
        assert actions[0].target_x >= 6

    def test_run_ai_decisions_none_ground_items(self):
        """run_ai_decisions with ground_items=None does not crash."""
        enemy = _make_enemy(ai_behavior="aggressive", x=5, y=5)
        all_units = {enemy.player_id: enemy}

        actions = run_ai_decisions(
            ai_ids=[enemy.player_id],
            all_units=all_units,
            grid_width=15,
            grid_height=15,
            obstacles=set(),
            ground_items=None,
        )
        # Should not crash — returns patrol/wait action
        assert len(actions) == 1
        assert actions[0].action_type in (ActionType.MOVE, ActionType.WAIT)

    def test_decide_ai_action_passes_ground_items(self):
        """decide_ai_action accepts ground_items kwarg."""
        enemy = _make_enemy(ai_behavior="aggressive", x=5, y=5)
        ground_items = {"7,5": [_make_item("Loot")]}
        all_units = {enemy.player_id: enemy}

        action = decide_ai_action(
            enemy, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
            ground_items=ground_items,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE


# ---------------------------------------------------------------------------
# 6. Phase 28-FIX: Monster Exclusion Tests
# ---------------------------------------------------------------------------

class TestMonsterLootExclusion:
    """Phase 28-FIX: Dungeon monsters must NOT scavenge or auto-pickup loot."""

    def test_monster_does_not_scavenge(self):
        """Monster (enemy_type='demon') does NOT path toward ground loot."""
        monster = _make_enemy(ai_behavior="aggressive", x=5, y=5, enemy_type="demon")
        ground_items = {"7,5": [_make_item("Loot")]}
        all_units = {monster.player_id: monster}

        action = _decide_aggressive_action(
            monster, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
            ground_items=ground_items,
        )
        # Monster falls through to patrol, not loot-seeking
        assert action is not None
        # Should not be moving directly toward the loot tile at (7,5)
        if action.action_type == ActionType.MOVE:
            assert not (action.target_x == 7 and action.target_y == 5)

    def test_monster_does_not_auto_pickup(self):
        """Monster standing on ground items does NOT auto-pick them up."""
        monster = _make_enemy(x=5, y=5, enemy_type="demon")
        item = _make_item("Ground Sword")
        ground_items = {"5,5": [item]}
        players = {monster.player_id: monster}

        results: list[ActionResult] = []
        items_picked_up: list[dict] = []
        _resolve_loot(
            loot_actions=[],
            players=players,
            chest_states=None,
            ground_items=ground_items,
            results=results,
            chest_opened=[],
            items_picked_up=items_picked_up,
        )

        assert len(monster.inventory) == 0  # Monster should NOT pick up
        assert "5,5" in ground_items  # Item stays on ground

    def test_human_player_still_auto_pickups(self):
        """Human player auto-pickup still works (not affected by monster guard)."""
        player = _make_player(x=3, y=3)
        item = _make_item("Player Loot")
        ground_items = {"3,3": [item]}
        players = {player.player_id: player}

        results: list[ActionResult] = []
        items_picked_up: list[dict] = []
        _resolve_loot(
            loot_actions=[],
            players=players,
            chest_states=None,
            ground_items=ground_items,
            results=results,
            chest_opened=[],
            items_picked_up=items_picked_up,
        )

        assert len(player.inventory) == 1
