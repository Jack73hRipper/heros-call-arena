"""
Tests for Phase 7A-3 — Movement Prediction for Queued Paths.

Covers:
  - _build_occupied_set correctly excludes vacating positions
  - _build_occupied_set correctly includes claimed positions
  - _build_occupied_set with no pending_moves (backward compat)
  - decide_ai_action with pending_moves does not block on vacating ally
  - run_ai_decisions tracks pending moves across sequential AI decisions
  - Multiple AI allies in a hallway pathfind without blocking each other
  - Non-moving units still block (pending_moves doesn't over-remove)
  - Backward compat: existing AI behavior unchanged without pending_moves
"""

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.ai_behavior import (
    _build_occupied_set,
    decide_ai_action,
    run_ai_decisions,
    clear_ai_patrol_state,
    clear_room_bounds,
)
from app.core.combat import load_combat_config


def setup_module():
    load_combat_config()


def teardown_function():
    clear_ai_patrol_state()
    clear_room_bounds()


def make_player(pid, username, x, y, hp=100, team="a", unit_type="human",
                ai_behavior=None, hero_id=None, vision_range=7) -> PlayerState:
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=100,
        attack_damage=15,
        armor=0,
        team=team,
        unit_type=unit_type,
        ai_behavior=ai_behavior,
        hero_id=hero_id,
        vision_range=vision_range,
    )


# ---------------------------------------------------------------------------
# _build_occupied_set tests
# ---------------------------------------------------------------------------

class TestBuildOccupiedSet:
    """Tests for the _build_occupied_set helper with movement prediction."""

    def test_basic_no_pending_moves(self):
        """Without pending_moves, behaves like the old occupied set."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5),
            "p2": make_player("p2", "Bob", 4, 5),
            "p3": make_player("p3", "Carol", 5, 5),
        }
        occupied = _build_occupied_set(players, "p1")
        assert (4, 5) in occupied  # Bob
        assert (5, 5) in occupied  # Carol
        assert (3, 5) not in occupied  # Alice excluded (self)

    def test_pending_moves_vacate(self):
        """A unit with a pending MOVE should have its current position excluded."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5),
            "p2": make_player("p2", "Bob", 4, 5),
        }
        pending = {"p2": ((4, 5), (5, 5))}
        occupied = _build_occupied_set(players, "p1", pending)
        assert (4, 5) not in occupied, "Bob's current position should be vacated"
        # Target is NOT claimed — batch resolver handles conflicts
        assert (5, 5) not in occupied, "No claimed positions added"

    def test_pending_moves_no_claim(self):
        """Claimed target positions are NOT added — batch resolver handles."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5),
            "p2": make_player("p2", "Bob", 4, 5),
        }
        pending = {"p2": ((4, 5), (6, 5))}
        occupied = _build_occupied_set(players, "p1", pending)
        assert (6, 5) not in occupied, "Claimed targets not added"
        assert (4, 5) not in occupied, "Bob's position vacated"

    def test_pending_moves_multiple(self):
        """Multiple pending moves should all be respected — vacating only."""
        players = {
            "p1": make_player("p1", "Alice", 1, 5),
            "p2": make_player("p2", "Bob", 2, 5),
            "p3": make_player("p3", "Carol", 3, 5),
        }
        pending = {
            "p2": ((2, 5), (3, 5)),
            "p3": ((3, 5), (4, 5)),
        }
        occupied = _build_occupied_set(players, "p1", pending)
        assert (2, 5) not in occupied, "Bob vacating"
        assert (3, 5) not in occupied, "Carol vacating"
        # Claimed targets are NOT added — batch resolver handles conflicts
        assert (4, 5) not in occupied, "No claimed positions added"

    def test_pending_moves_none_backward_compat(self):
        """Passing None for pending_moves should work identically to no arg."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5),
            "p2": make_player("p2", "Bob", 4, 5),
        }
        occ_no_arg = _build_occupied_set(players, "p1")
        occ_none = _build_occupied_set(players, "p1", None)
        assert occ_no_arg == occ_none

    def test_dead_unit_not_in_occupied(self):
        """Dead units should not appear in occupied regardless of pending_moves."""
        p2 = make_player("p2", "Bob", 4, 5)
        p2.is_alive = False
        players = {
            "p1": make_player("p1", "Alice", 3, 5),
            "p2": p2,
        }
        occupied = _build_occupied_set(players, "p1")
        assert (4, 5) not in occupied

    def test_self_not_in_occupied(self):
        """The unit building its own occupied set should never include itself."""
        players = {
            "p1": make_player("p1", "Alice", 3, 5),
            "p2": make_player("p2", "Bob", 4, 5),
        }
        occupied = _build_occupied_set(players, "p1")
        assert (3, 5) not in occupied

    def test_non_pending_unit_on_vacating_tile_still_blocks(self):
        """If a non-pending unit is on a vacating tile, it should still block.
        Only the pending mover's own position is excluded."""
        players = {
            "p1": make_player("p1", "Alice", 1, 5),
            "p2": make_player("p2", "Bob", 4, 5),
            "p3": make_player("p3", "Carol", 4, 5),  # same tile as Bob (shouldn't happen, but edge case)
        }
        # Only p2 has a pending move from (4,5)
        pending = {"p2": ((4, 5), (5, 5))}
        occupied = _build_occupied_set(players, "p1", pending)
        # Carol is also at (4,5) but NOT in pending_moves — she should still block
        assert (4, 5) in occupied, "Carol (non-pending) still blocks the tile"


# ---------------------------------------------------------------------------
# decide_ai_action with pending_moves
# ---------------------------------------------------------------------------

class TestDecideWithPendingMoves:
    """AI decisions should use pending_moves to avoid blocking allies."""

    def test_ai_paths_through_vacating_ally(self):
        """AI should be able to path toward a tile being vacated by an ally."""
        # Set up: 1-wide hallway at y=5, AI at (1,5), Bob at (2,5) moving to (3,5),
        # enemy at (5,5). Walls at y=4 and y=6 to force horizontal movement.
        # Put ranged on cooldown so AI must MOVE.
        ai = make_player("ai1", "AI-1", 1, 5, team="b", unit_type="ai", ai_behavior="aggressive")
        ai.cooldowns["ranged_attack"] = 3  # ranged on cooldown → must move
        bob = make_player("p2", "Bob", 2, 5, team="b", unit_type="ai", ai_behavior="aggressive")
        enemy = make_player("e1", "Enemy", 5, 5, team="a")
        all_units = {"ai1": ai, "p2": bob, "e1": enemy}

        obstacles = set()
        for x in range(10):
            obstacles.add((x, 4))
            obstacles.add((x, 6))

        # Without pending_moves, AI is blocked by Bob at (2,5)
        action_no_pending = decide_ai_action(
            ai, all_units, 10, 10, obstacles,
        )
        # AI can't path through Bob in hallway — it should WAIT (stuck)
        assert action_no_pending is not None
        assert action_no_pending.action_type == ActionType.WAIT

        # With pending_moves showing Bob vacating (2,5) → (3,5)
        pending = {"p2": ((2, 5), (3, 5))}
        action_with_pending = decide_ai_action(
            ai, all_units, 10, 10, obstacles,
            pending_moves=pending,
        )

        # With prediction, AI should move to (2,5) since Bob is vacating
        assert action_with_pending is not None
        assert action_with_pending.action_type == ActionType.MOVE
        assert action_with_pending.target_x == 2
        assert action_with_pending.target_y == 5

    def test_ai_backward_compat_no_pending(self):
        """Without pending_moves, AI behavior should be unchanged."""
        # 1-wide hallway to force deterministic movement direction
        ai = make_player("ai1", "AI-1", 5, 5, team="b", unit_type="ai", ai_behavior="aggressive")
        enemy = make_player("e1", "Enemy", 7, 5, team="a")
        all_units = {"ai1": ai, "e1": enemy}

        obstacles = set()
        for x in range(15):
            obstacles.add((x, 4))
            obstacles.add((x, 6))

        action = decide_ai_action(ai, all_units, 15, 15, obstacles)
        assert action is not None
        assert action.action_type == ActionType.MOVE
        assert action.target_x == 6
        assert action.target_y == 5


# ---------------------------------------------------------------------------
# run_ai_decisions — sequential pending move tracking
# ---------------------------------------------------------------------------

class TestRunAIDecisionsPendingMoves:
    """run_ai_decisions should track pending moves across sequential AI calls."""

    def test_two_allies_hallway_sequential(self):
        """Two AI allies in a 1-wide hallway.  First decides to move,
        second should see the first's position as vacating and also move."""
        # Hallway: y=5, x from 1 to 10, enemy at (5,5)
        # Put ranged on cooldown so all AI must MOVE (not ranged attack)
        ai1 = make_player("ai1", "AI-1", 2, 5, team="a", unit_type="ai", ai_behavior="aggressive")
        ai1.cooldowns["ranged_attack"] = 3
        ai2 = make_player("ai2", "AI-2", 1, 5, team="a", unit_type="ai", ai_behavior="aggressive")
        ai2.cooldowns["ranged_attack"] = 3
        enemy = make_player("e1", "Enemy", 5, 5, team="b")
        all_units = {"ai1": ai1, "ai2": ai2, "e1": enemy}

        # Wall off the top and bottom so it's truly a 1-wide hallway
        obstacles = set()
        for x in range(10):
            obstacles.add((x, 4))
            obstacles.add((x, 6))

        actions = run_ai_decisions(
            ["ai1", "ai2"], all_units, 10, 10, obstacles,
        )

        # Both should produce MOVE actions (not WAIT)
        move_actions = [a for a in actions if a.action_type == ActionType.MOVE]
        assert len(move_actions) == 2, f"Expected 2 moves, got {len(move_actions)}: {actions}"

        # AI1 (at 2,5) should move to (3,5)
        ai1_action = next(a for a in actions if a.player_id == "ai1")
        assert ai1_action.target_x == 3
        assert ai1_action.target_y == 5

        # AI2 (at 1,5) should move to (2,5) — possible because AI1 is vacating it
        ai2_action = next(a for a in actions if a.player_id == "ai2")
        assert ai2_action.target_x == 2
        assert ai2_action.target_y == 5

    def test_three_allies_chain_prediction(self):
        """Three AI allies in a line: each should predict the previous vacating."""
        # Put ranged on cooldown so all AI must MOVE
        ai1 = make_player("ai1", "AI-1", 3, 5, team="a", unit_type="ai", ai_behavior="aggressive")
        ai1.cooldowns["ranged_attack"] = 3
        ai2 = make_player("ai2", "AI-2", 2, 5, team="a", unit_type="ai", ai_behavior="aggressive")
        ai2.cooldowns["ranged_attack"] = 3
        ai3 = make_player("ai3", "AI-3", 1, 5, team="a", unit_type="ai", ai_behavior="aggressive")
        ai3.cooldowns["ranged_attack"] = 3
        enemy = make_player("e1", "Enemy", 6, 5, team="b")
        all_units = {"ai1": ai1, "ai2": ai2, "ai3": ai3, "e1": enemy}

        obstacles = set()
        for x in range(10):
            obstacles.add((x, 4))
            obstacles.add((x, 6))

        actions = run_ai_decisions(
            ["ai1", "ai2", "ai3"], all_units, 10, 10, obstacles,
        )

        move_actions = [a for a in actions if a.action_type == ActionType.MOVE]
        assert len(move_actions) == 3, f"All 3 should move, got {len(move_actions)}: {actions}"

    def test_controlled_units_skipped(self):
        """Player-controlled AI units should be skipped (backward compat)."""
        ai1 = make_player("ai1", "AI-1", 3, 5, team="a", unit_type="ai", ai_behavior="aggressive")
        enemy = make_player("e1", "Enemy", 6, 5, team="b")
        all_units = {"ai1": ai1, "e1": enemy}

        actions = run_ai_decisions(
            ["ai1"], all_units, 15, 15, set(),
            controlled_ids={"ai1"},
        )
        assert len(actions) == 0, "Controlled AI should be skipped"

    def test_non_move_actions_not_tracked(self):
        """Only MOVE actions should be added to pending_moves, not attacks."""
        # AI adjacent to enemy should ATTACK, which shouldn't be tracked
        ai1 = make_player("ai1", "AI-1", 4, 5, team="a", unit_type="ai", ai_behavior="aggressive")
        ai2 = make_player("ai2", "AI-2", 3, 5, team="a", unit_type="ai", ai_behavior="aggressive")
        enemy = make_player("e1", "Enemy", 5, 5, team="b")
        all_units = {"ai1": ai1, "ai2": ai2, "e1": enemy}

        actions = run_ai_decisions(
            ["ai1", "ai2"], all_units, 15, 15, set(),
        )

        ai1_action = next(a for a in actions if a.player_id == "ai1")
        assert ai1_action.action_type == ActionType.ATTACK, "AI1 should attack adjacent enemy"

        # AI2 should still be able to move toward enemy
        ai2_action = next(a for a in actions if a.player_id == "ai2")
        assert ai2_action.action_type == ActionType.MOVE

    def test_backward_compat_single_ai(self):
        """Single AI unit should behave identically with or without prediction."""
        # 1-wide hallway for deterministic movement
        ai = make_player("ai1", "AI-1", 3, 5, team="a", unit_type="ai", ai_behavior="aggressive")
        enemy = make_player("e1", "Enemy", 6, 5, team="b")
        all_units = {"ai1": ai, "e1": enemy}

        obstacles = set()
        for x in range(15):
            obstacles.add((x, 4))
            obstacles.add((x, 6))

        actions = run_ai_decisions(
            ["ai1"], all_units, 15, 15, obstacles,
        )
        assert len(actions) == 1
        assert actions[0].action_type == ActionType.MOVE
        assert actions[0].target_x == 4
        assert actions[0].target_y == 5


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestMovementPredictionEdgeCases:
    """Edge cases for the movement prediction system."""

    def test_dead_ai_skipped_and_cleaned(self):
        """Dead AI units should be skipped and have state cleaned."""
        ai = make_player("ai1", "AI-1", 3, 5, team="a", unit_type="ai")
        ai.is_alive = False
        all_units = {"ai1": ai}

        actions = run_ai_decisions(["ai1"], all_units, 15, 15, set())
        assert len(actions) == 0

    def test_empty_ai_list(self):
        """Empty AI list should return empty actions."""
        all_units = {"p1": make_player("p1", "Alice", 3, 5)}
        actions = run_ai_decisions([], all_units, 15, 15, set())
        assert actions == []

    def test_pending_moves_dont_remove_stationary_enemies(self):
        """Pending moves should only affect the pending mover, not other
        units that happen to be on non-pending tiles."""
        ai = make_player("ai1", "AI-1", 1, 5, team="a", unit_type="ai", ai_behavior="aggressive")
        enemy = make_player("e1", "Enemy", 3, 5, team="b")
        all_units = {"ai1": ai, "e1": enemy}

        # No pending moves for the enemy — it should still block
        pending = {}
        action = decide_ai_action(ai, all_units, 15, 15, set(), pending_moves=pending)
        assert action is not None
        assert action.action_type == ActionType.MOVE
        assert action.target_x == 2  # Move toward enemy, not through it
