"""
Tests for Phase 29A — AI Chest Seeking (Hero Allies).

Covers:
  - _find_nearest_unopened_chest: finds nearest, skips opened, skips if inv full
  - _try_loot_adjacent_chest: loots adjacent unopened, skips opened, skips far
  - Follow stance: seeks chest when idle, loots when adjacent
  - Aggressive stance: seeks chest when idle (after memory/reinforce)
  - Defensive stance: seeks chest within tether, respects 2-tile owner leash
  - Hold stance: loots adjacent chest (no movement)
  - All stances: combat takes priority over chest seeking
  - chest_states=None: no crash, normal behavior
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.models.items import INVENTORY_MAX_CAPACITY
from app.core.ai_stances import (
    _find_nearest_unopened_chest,
    _try_loot_adjacent_chest,
    _decide_stance_action,
    _decide_follow_action,
    _decide_aggressive_stance_action,
    _decide_defensive_action,
    _decide_hold_action,
)
from app.core.ai_behavior import decide_ai_action, run_ai_decisions
from app.core.combat import load_combat_config


def setup_module():
    load_combat_config()


def _make_hero(pid, x, y, team="a", stance="follow", class_id=None,
               controlled_by=None, inventory=None) -> PlayerState:
    p = PlayerState(
        player_id=pid,
        username=pid,
        position=Position(x=x, y=y),
        hp=100,
        max_hp=100,
        attack_damage=15,
        armor=0,
        team=team,
        unit_type="ai",
        hero_id=f"hero_{pid}",
        ai_stance=stance,
        class_id=class_id or "warrior",
        ranged_range=5,
        vision_range=7,
        controlled_by=controlled_by,
    )
    if inventory is not None:
        p.inventory = inventory
    return p


def _make_human(pid, x, y, team="a") -> PlayerState:
    return PlayerState(
        player_id=pid,
        username=pid,
        position=Position(x=x, y=y),
        hp=100,
        max_hp=100,
        attack_damage=15,
        armor=0,
        team=team,
        unit_type="human",
        vision_range=7,
    )


def _make_enemy(pid, x, y, team="b") -> PlayerState:
    return PlayerState(
        player_id=pid,
        username=pid,
        position=Position(x=x, y=y),
        hp=100,
        max_hp=100,
        attack_damage=15,
        armor=0,
        team=team,
        unit_type="ai",
        ai_behavior="aggressive",
        enemy_type="skeleton",
        vision_range=7,
    )


# ---------------------------------------------------------------------------
# _find_nearest_unopened_chest tests
# ---------------------------------------------------------------------------

class TestFindNearestUnopenedChest:
    def test_finds_nearest_chest(self):
        hero = _make_hero("h1", 5, 5)
        chest_states = {"3,5": "unopened", "8,5": "unopened"}
        result = _find_nearest_unopened_chest(hero, chest_states, max_range=5)
        assert result == (3, 5)  # closer

    def test_finds_chest_with_tier(self):
        hero = _make_hero("h1", 5, 5)
        chest_states = {"6,5": "unopened:gold"}
        result = _find_nearest_unopened_chest(hero, chest_states, max_range=5)
        assert result == (6, 5)

    def test_skips_opened_chests(self):
        hero = _make_hero("h1", 5, 5)
        chest_states = {"6,5": "opened", "4,5": "opened:gold"}
        result = _find_nearest_unopened_chest(hero, chest_states, max_range=5)
        assert result is None

    def test_skips_out_of_range(self):
        hero = _make_hero("h1", 5, 5)
        chest_states = {"15,15": "unopened"}
        result = _find_nearest_unopened_chest(hero, chest_states, max_range=5)
        assert result is None

    def test_returns_none_for_empty(self):
        hero = _make_hero("h1", 5, 5)
        result = _find_nearest_unopened_chest(hero, {}, max_range=5)
        assert result is None

    def test_returns_none_for_none(self):
        hero = _make_hero("h1", 5, 5)
        result = _find_nearest_unopened_chest(hero, None, max_range=5)
        assert result is None

    def test_skips_if_inventory_full(self):
        hero = _make_hero("h1", 5, 5, inventory=[{"id": f"item_{i}"} for i in range(INVENTORY_MAX_CAPACITY)])
        chest_states = {"6,5": "unopened"}
        result = _find_nearest_unopened_chest(hero, chest_states, max_range=5)
        assert result is None


# ---------------------------------------------------------------------------
# _try_loot_adjacent_chest tests
# ---------------------------------------------------------------------------

class TestTryLootAdjacentChest:
    def test_loots_adjacent_chest(self):
        hero = _make_hero("h1", 5, 5)
        chest_states = {"6,5": "unopened"}
        action = _try_loot_adjacent_chest(hero, chest_states)
        assert action is not None
        assert action.action_type == ActionType.LOOT
        assert action.target_x == 6
        assert action.target_y == 5

    def test_loots_diagonal_adjacent(self):
        hero = _make_hero("h1", 5, 5)
        chest_states = {"6,6": "unopened"}
        action = _try_loot_adjacent_chest(hero, chest_states)
        assert action is not None
        assert action.action_type == ActionType.LOOT
        assert action.target_x == 6
        assert action.target_y == 6

    def test_loots_tiered_chest(self):
        hero = _make_hero("h1", 5, 5)
        chest_states = {"4,5": "unopened:gold"}
        action = _try_loot_adjacent_chest(hero, chest_states)
        assert action is not None
        assert action.action_type == ActionType.LOOT

    def test_skips_opened_chest(self):
        hero = _make_hero("h1", 5, 5)
        chest_states = {"6,5": "opened"}
        action = _try_loot_adjacent_chest(hero, chest_states)
        assert action is None

    def test_skips_far_chest(self):
        hero = _make_hero("h1", 5, 5)
        chest_states = {"8,5": "unopened"}
        action = _try_loot_adjacent_chest(hero, chest_states)
        assert action is None


# ---------------------------------------------------------------------------
# Follow stance chest seeking
# ---------------------------------------------------------------------------

class TestFollowStanceChestSeeking:
    def test_seeks_chest_when_idle_near_owner(self):
        """Follow hero near owner with no enemies should path toward chest."""
        owner = _make_human("owner", 5, 5)
        hero = _make_hero("h1", 5, 6, controlled_by="owner")
        all_units = {owner.player_id: owner, hero.player_id: hero}
        chest_states = {"5,8": "unopened"}
        obstacles = set()

        action = _decide_follow_action(
            hero, all_units, 15, 15, obstacles,
            chest_states=chest_states,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should be stepping toward the chest at (5, 8)
        assert action.target_y > 6  # moving south toward chest

    def test_loots_chest_when_adjacent(self):
        """Follow hero adjacent to chest with no enemies should loot."""
        owner = _make_human("owner", 5, 5)
        hero = _make_hero("h1", 5, 6, controlled_by="owner")
        all_units = {owner.player_id: owner, hero.player_id: hero}
        chest_states = {"5,7": "unopened"}
        obstacles = set()

        action = _decide_follow_action(
            hero, all_units, 15, 15, obstacles,
            chest_states=chest_states,
        )
        assert action is not None
        assert action.action_type == ActionType.LOOT
        assert action.target_x == 5
        assert action.target_y == 7

    def test_combat_takes_priority(self):
        """Follow hero with visible enemy should fight, not seek chest."""
        owner = _make_human("owner", 5, 5)
        hero = _make_hero("h1", 5, 6, controlled_by="owner")
        enemy = _make_enemy("e1", 5, 7)
        all_units = {owner.player_id: owner, hero.player_id: hero, enemy.player_id: enemy}
        chest_states = {"3,6": "unopened"}
        obstacles = set()

        action = _decide_follow_action(
            hero, all_units, 15, 15, obstacles,
            chest_states=chest_states,
        )
        assert action is not None
        assert action.action_type in (ActionType.ATTACK, ActionType.RANGED_ATTACK, ActionType.MOVE)
        # Should NOT be looting chest
        assert action.action_type != ActionType.LOOT

    def test_no_crash_with_no_chest_states(self):
        """Follow hero with chest_states=None should still work normally."""
        owner = _make_human("owner", 5, 5)
        hero = _make_hero("h1", 5, 6, controlled_by="owner")
        all_units = {owner.player_id: owner, hero.player_id: hero}
        obstacles = set()

        action = _decide_follow_action(
            hero, all_units, 15, 15, obstacles,
            chest_states=None,
        )
        assert action is not None
        assert action.action_type == ActionType.WAIT


# ---------------------------------------------------------------------------
# Aggressive stance chest seeking
# ---------------------------------------------------------------------------

class TestAggressiveStanceChestSeeking:
    def test_seeks_chest_when_idle(self):
        """Aggressive hero with no enemies should seek chest."""
        owner = _make_human("owner", 5, 5)
        hero = _make_hero("h1", 6, 5, stance="aggressive", controlled_by="owner")
        all_units = {owner.player_id: owner, hero.player_id: hero}
        chest_states = {"8,5": "unopened"}
        obstacles = set()

        action = _decide_aggressive_stance_action(
            hero, all_units, 15, 15, obstacles,
            chest_states=chest_states,
        )
        assert action is not None
        # Should move toward chest or loot if adjacent
        assert action.action_type in (ActionType.MOVE, ActionType.LOOT)

    def test_loots_adjacent_chest(self):
        """Aggressive hero adjacent to chest should loot."""
        owner = _make_human("owner", 5, 5)
        hero = _make_hero("h1", 7, 5, stance="aggressive", controlled_by="owner")
        all_units = {owner.player_id: owner, hero.player_id: hero}
        chest_states = {"8,5": "unopened"}
        obstacles = set()

        action = _decide_aggressive_stance_action(
            hero, all_units, 15, 15, obstacles,
            chest_states=chest_states,
        )
        assert action is not None
        assert action.action_type == ActionType.LOOT
        assert action.target_x == 8
        assert action.target_y == 5


# ---------------------------------------------------------------------------
# Defensive stance chest seeking
# ---------------------------------------------------------------------------

class TestDefensiveStanceChestSeeking:
    def test_loots_adjacent_chest_near_owner(self):
        """Defensive hero adjacent to chest and near owner should loot."""
        owner = _make_human("owner", 5, 5)
        hero = _make_hero("h1", 5, 6, stance="defensive", controlled_by="owner")
        all_units = {owner.player_id: owner, hero.player_id: hero}
        chest_states = {"5,7": "unopened"}
        obstacles = set()

        action = _decide_defensive_action(
            hero, all_units, 15, 15, obstacles,
            chest_states=chest_states,
        )
        assert action is not None
        assert action.action_type == ActionType.LOOT

    def test_no_chest_seeking_when_it_would_break_tether(self):
        """Defensive hero should not move toward chest if it breaks 2-tile tether."""
        owner = _make_human("owner", 5, 5)
        # Hero is already at tether limit (2 tiles from owner)
        hero = _make_hero("h1", 5, 7, stance="defensive", controlled_by="owner")
        all_units = {owner.player_id: owner, hero.player_id: hero}
        # Chest is far from owner, moving toward it would break tether
        chest_states = {"5,10": "unopened"}
        obstacles = set()

        action = _decide_defensive_action(
            hero, all_units, 15, 15, obstacles,
            chest_states=chest_states,
        )
        assert action is not None
        # Should wait, not move toward chest (would break tether)
        assert action.action_type == ActionType.WAIT


# ---------------------------------------------------------------------------
# Hold stance chest seeking
# ---------------------------------------------------------------------------

class TestHoldStanceChestSeeking:
    def test_loots_adjacent_chest(self):
        """Hold hero adjacent to chest should loot it."""
        hero = _make_hero("h1", 5, 5, stance="hold")
        all_units = {hero.player_id: hero}
        chest_states = {"5,6": "unopened"}

        action = _decide_hold_action(
            hero, all_units, 15, 15, set(),
            chest_states=chest_states,
        )
        assert action is not None
        assert action.action_type == ActionType.LOOT
        assert action.target_x == 5
        assert action.target_y == 6

    def test_does_not_move_toward_chest(self):
        """Hold hero should never move toward chest, only loot if adjacent."""
        hero = _make_hero("h1", 5, 5, stance="hold")
        all_units = {hero.player_id: hero}
        chest_states = {"5,8": "unopened"}

        action = _decide_hold_action(
            hero, all_units, 15, 15, set(),
            chest_states=chest_states,
        )
        assert action is not None
        assert action.action_type == ActionType.WAIT

    def test_combat_priority_over_chest(self):
        """Hold hero with adjacent enemy should attack, not loot chest."""
        hero = _make_hero("h1", 5, 5, stance="hold")
        enemy = _make_enemy("e1", 5, 6)
        all_units = {hero.player_id: hero, enemy.player_id: enemy}
        chest_states = {"6,5": "unopened"}

        action = _decide_hold_action(
            hero, all_units, 15, 15, set(),
            chest_states=chest_states,
        )
        assert action is not None
        assert action.action_type == ActionType.ATTACK


# ---------------------------------------------------------------------------
# Integration: decide_ai_action + run_ai_decisions thread chest_states
# ---------------------------------------------------------------------------

class TestChestStatesIntegration:
    def test_decide_ai_action_passes_chest_states(self):
        """chest_states flows from decide_ai_action to stance handler."""
        owner = _make_human("owner", 5, 5)
        hero = _make_hero("h1", 5, 6, controlled_by="owner")
        all_units = {owner.player_id: owner, hero.player_id: hero}
        chest_states = {"5,7": "unopened"}

        action = decide_ai_action(
            hero, all_units, 15, 15, set(),
            chest_states=chest_states,
        )
        assert action is not None
        assert action.action_type == ActionType.LOOT

    def test_run_ai_decisions_passes_chest_states(self):
        """chest_states flows from run_ai_decisions to individual AI."""
        owner = _make_human("owner", 5, 5)
        hero = _make_hero("h1", 5, 6, controlled_by="owner")
        all_units = {owner.player_id: owner, hero.player_id: hero}
        chest_states = {"5,7": "unopened"}

        actions = run_ai_decisions(
            [hero.player_id], all_units, 15, 15, set(),
            chest_states=chest_states,
        )
        assert len(actions) == 1
        assert actions[0].action_type == ActionType.LOOT

    def test_no_crash_without_chest_states(self):
        """run_ai_decisions works fine without chest_states (arena maps)."""
        owner = _make_human("owner", 5, 5)
        hero = _make_hero("h1", 5, 6, controlled_by="owner")
        all_units = {owner.player_id: owner, hero.player_id: hero}

        actions = run_ai_decisions(
            [hero.player_id], all_units, 15, 15, set(),
        )
        assert len(actions) == 1
        assert actions[0].action_type == ActionType.WAIT


# ---------------------------------------------------------------------------
# Phase 29B — PVPVE Team Leader Chest Seeking
# ---------------------------------------------------------------------------

def _make_pvpve_leader(pid, x, y, team="b", class_id=None) -> PlayerState:
    """Create a PVPVE team leader: no hero_id, no ai_stance, no enemy_type."""
    return PlayerState(
        player_id=pid,
        username=pid,
        position=Position(x=x, y=y),
        hp=100,
        max_hp=100,
        attack_damage=15,
        armor=0,
        team=team,
        unit_type="ai",
        ai_behavior="aggressive",
        class_id=class_id or "crusader",
        ranged_range=5,
        vision_range=7,
    )


def _make_pvpve_follower(pid, x, y, team="b", leader_id="leader1",
                         class_id=None) -> PlayerState:
    """Create a PVPVE follower: hero_id set, ai_stance='follow', no enemy_type."""
    p = PlayerState(
        player_id=pid,
        username=pid,
        position=Position(x=x, y=y),
        hp=100,
        max_hp=100,
        attack_damage=15,
        armor=0,
        team=team,
        unit_type="ai",
        hero_id=f"pvpve-team-{leader_id}",
        ai_stance="follow",
        class_id=class_id or "confessor",
        ranged_range=5,
        vision_range=7,
    )
    return p


class TestPvpveLeaderChestSeeking:
    """Phase 29B — PVPVE team leaders (no hero_id, no ai_stance) should seek
    and loot chests via _decide_aggressive_action when idle."""

    def test_leader_loots_adjacent_chest(self):
        """Leader adjacent to an unopened chest should emit LOOT."""
        leader = _make_pvpve_leader("leader1", 5, 5)
        all_units = {leader.player_id: leader}
        chest_states = {"5,6": "unopened"}

        action = decide_ai_action(
            leader, all_units, 15, 15, set(),
            chest_states=chest_states,
        )
        assert action is not None
        assert action.action_type == ActionType.LOOT
        assert action.target_x == 5
        assert action.target_y == 6

    def test_leader_moves_toward_chest(self):
        """Leader should pathfind toward a nearby unopened chest when idle."""
        leader = _make_pvpve_leader("leader1", 5, 5)
        all_units = {leader.player_id: leader}
        chest_states = {"5,9": "unopened"}  # 4 tiles away

        action = decide_ai_action(
            leader, all_units, 15, 15, set(),
            chest_states=chest_states,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should move toward y=9. Exact step depends on A*, but y should increase.
        assert action.target_y > 5

    def test_leader_ignores_opened_chests(self):
        """Leader should NOT seek already-opened chests."""
        leader = _make_pvpve_leader("leader1", 5, 5)
        all_units = {leader.player_id: leader}
        chest_states = {"5,6": "opened"}

        action = decide_ai_action(
            leader, all_units, 15, 15, set(),
            chest_states=chest_states,
        )
        assert action is not None
        # No chest to seek — should patrol or wait, not LOOT
        assert action.action_type != ActionType.LOOT

    def test_leader_combat_takes_priority(self):
        """If enemies are visible, leader should fight, not seek chests."""
        leader = _make_pvpve_leader("leader1", 5, 5, team="b")
        enemy = _make_human("p1", 6, 5, team="a")
        all_units = {leader.player_id: leader, enemy.player_id: enemy}
        chest_states = {"5,6": "unopened"}

        action = decide_ai_action(
            leader, all_units, 15, 15, set(),
            chest_states=chest_states,
        )
        assert action is not None
        # Should attack or use skill on enemy, not loot
        assert action.action_type in (ActionType.ATTACK, ActionType.MOVE, ActionType.SKILL)

    def test_leader_no_chest_seeking_for_dungeon_enemies(self):
        """Dungeon enemies (enemy_type set) should NOT seek chests."""
        enemy = _make_enemy("skel1", 5, 5, team="b")
        all_units = {enemy.player_id: enemy}
        chest_states = {"5,6": "unopened"}

        action = decide_ai_action(
            enemy, all_units, 15, 15, set(),
            chest_states=chest_states,
        )
        assert action is not None
        # Should patrol, NOT loot
        assert action.action_type != ActionType.LOOT

    def test_leader_no_crash_without_chest_states(self):
        """Leader works fine when chest_states is None."""
        leader = _make_pvpve_leader("leader1", 5, 5)
        all_units = {leader.player_id: leader}

        action = decide_ai_action(
            leader, all_units, 15, 15, set(),
        )
        assert action is not None
