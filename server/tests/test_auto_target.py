"""
Tests for Phase 10A, 10B & 10G — Auto-Target State Management, Chase Action
Generation & Skill Auto-Target Pursuit.

Phase 10A coverage:
  - Setting auto-target on a valid enemy succeeds
  - Setting auto-target clears any existing action queue
  - Cannot auto-target a same-team ally
  - Cannot auto-target a dead unit
  - Cannot auto-target yourself
  - Clearing auto-target sets it to None
  - Clearing when not set is a no-op (no crash)
  - get_auto_target returns current target_id or None

Phase 10B coverage:
  - generate_auto_target_action produces ATTACK when adjacent
  - generate_auto_target_action produces MOVE when distant
  - generate_auto_target_action produces INTERACT for closed doors
  - Auto-target clears on target death
  - Auto-target clears on unreachable target
  - Auto-target does not override queued actions
  - Auto-target fires when queue is empty
  - queue_action() clears auto-target for MOVE actions
  - queue_action() preserves auto-target for SKILL actions (balance-pass)
  - queue_action() preserves auto-target for ATTACK / RANGED_ATTACK / USE_ITEM
  - queue_action() clears auto-target for INTERACT / LOOT
  - Auto-target works for controlled party members
  - Auto-target uses live target position (not stale)

Phase 10G coverage:
  - set_auto_target with skill_id stores both fields
  - set_auto_target rejects skills the class can't use
  - set_auto_target rejects heal on enemy (wrong targeting)
  - set_auto_target allows heal on ally (same team)
  - set_auto_target rejects offensive skill on ally
  - clear_auto_target clears auto_skill_id too
  - generate_auto_target_action produces SKILL when in range + off cooldown
  - generate_auto_target_action produces MOVE when out of skill range
  - generate_auto_target_action produces WAIT when in range + on cooldown
  - generate_auto_target_action produces MOVE when out of range + on cooldown
  - generate_auto_target_action repositions when LOS blocked (ranged skill)
  - generate_auto_target_action produces SKILL for heal on ally
  - Power Shot range=0 uses player.ranged_range
  - Skill auto-target persists after cast (enables repeated casting)
  - No skill_id → melee ATTACK behavior unchanged (fallback)
  - Target death clears both auto_target_id and auto_skill_id

Phase 10G-8 edge case coverage:
  - Switch skills on same target (overwrite auto_skill_id cleanly)
  - Switch from melee to skill and back on same target
  - Skill becomes unavailable mid-pursuit (class restriction) → cancels auto-target
  - Skill on cooldown mid-pursuit → keeps approaching (NOT cancelled)
  - Heal on full HP target persists (overheal is graceful)
  - Party member skill auto-target (controlled ally uses skill pursuit)
  - Party member heal auto-target on player
  - Multi-cycle persistence (cast → cooldown → chase → cast again)
  - Offensive skill target becomes ally (team change) → cancelled
  - Heal target becomes enemy (team change) → cancelled
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.match_manager import (
    set_auto_target,
    clear_auto_target,
    get_auto_target,
    generate_auto_target_action,
    queue_action,
    get_player_queue,
    clear_player_queue,
    _player_states,
    _action_queues,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MATCH_ID = "test_auto"


def _setup_match(units: dict[str, PlayerState]) -> None:
    """Register units directly in the in-memory stores for testing."""
    _player_states[MATCH_ID] = {u.player_id: u for u in units.values()}
    _action_queues[MATCH_ID] = {}


def _make_unit(
    pid: str,
    team: str = "a",
    alive: bool = True,
    x: int = 0,
    y: int = 0,
) -> PlayerState:
    return PlayerState(
        player_id=pid,
        username=pid,
        position=Position(x=x, y=y),
        team=team,
        is_alive=alive,
        unit_type="human",
    )


def _teardown():
    _player_states.pop(MATCH_ID, None)
    _action_queues.pop(MATCH_ID, None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSetAutoTarget:
    """Tests for set_auto_target()."""

    def setup_method(self):
        self.player = _make_unit("p1", team="a", x=1, y=1)
        self.enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": self.player, "e1": self.enemy})

    def teardown_method(self):
        _teardown()

    def test_set_auto_target_valid(self):
        """Player targets alive enemy → auto_target_id is set."""
        result = set_auto_target(MATCH_ID, "p1", "e1")
        assert result is True
        assert self.player.auto_target_id == "e1"

    def test_set_auto_target_clears_queue(self):
        """Setting auto-target preserves existing action queue (QoL-A)."""
        # Pre-fill the queue with some actions
        action = PlayerAction(
            player_id="p1",
            action_type=ActionType.MOVE,
            target_x=2,
            target_y=1,
        )
        queue_action(MATCH_ID, "p1", action)
        queue_action(MATCH_ID, "p1", action)
        assert len(get_player_queue(MATCH_ID, "p1")) == 2

        result = set_auto_target(MATCH_ID, "p1", "e1")
        assert result is True
        # QoL-A: queue is preserved — batch path drains first, then auto-target takes over
        assert len(get_player_queue(MATCH_ID, "p1")) == 2

    def test_set_auto_target_invalid_ally(self):
        """Cannot auto-target a same-team unit → error string."""
        ally = _make_unit("a1", team="a", x=3, y=3)
        _player_states[MATCH_ID]["a1"] = ally

        result = set_auto_target(MATCH_ID, "p1", "a1")
        assert isinstance(result, str)
        assert "ally" in result.lower() or "same team" in result.lower()
        assert self.player.auto_target_id is None

    def test_set_auto_target_invalid_dead(self):
        """Cannot auto-target a dead unit → error string."""
        self.enemy.is_alive = False

        result = set_auto_target(MATCH_ID, "p1", "e1")
        assert isinstance(result, str)
        assert "dead" in result.lower() or "not found" in result.lower()
        assert self.player.auto_target_id is None

    def test_set_auto_target_invalid_self(self):
        """Cannot auto-target yourself → error string."""
        result = set_auto_target(MATCH_ID, "p1", "p1")
        assert isinstance(result, str)
        assert "yourself" in result.lower()
        assert self.player.auto_target_id is None

    def test_set_auto_target_invalid_nonexistent_target(self):
        """Cannot auto-target a nonexistent unit → error string."""
        result = set_auto_target(MATCH_ID, "p1", "ghost")
        assert isinstance(result, str)
        assert self.player.auto_target_id is None

    def test_set_auto_target_dead_player(self):
        """Dead player cannot set auto-target."""
        self.player.is_alive = False
        result = set_auto_target(MATCH_ID, "p1", "e1")
        assert isinstance(result, str)
        assert "dead" in result.lower() or "not found" in result.lower()

    def test_set_auto_target_replaces_existing(self):
        """Setting a new auto-target replaces the existing one."""
        enemy2 = _make_unit("e2", team="b", x=7, y=7)
        _player_states[MATCH_ID]["e2"] = enemy2

        set_auto_target(MATCH_ID, "p1", "e1")
        assert self.player.auto_target_id == "e1"

        result = set_auto_target(MATCH_ID, "p1", "e2")
        assert result is True
        assert self.player.auto_target_id == "e2"


class TestClearAutoTarget:
    """Tests for clear_auto_target()."""

    def setup_method(self):
        self.player = _make_unit("p1", team="a", x=1, y=1)
        self.enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": self.player, "e1": self.enemy})

    def teardown_method(self):
        _teardown()

    def test_clear_auto_target(self):
        """Clearing sets auto_target_id to None."""
        set_auto_target(MATCH_ID, "p1", "e1")
        assert self.player.auto_target_id == "e1"

        clear_auto_target(MATCH_ID, "p1")
        assert self.player.auto_target_id is None

    def test_clear_auto_target_noop(self):
        """Clearing when not set is a no-op — no crash."""
        assert self.player.auto_target_id is None
        clear_auto_target(MATCH_ID, "p1")  # Should not raise
        assert self.player.auto_target_id is None

    def test_clear_auto_target_nonexistent_player(self):
        """Clearing for a nonexistent player is a no-op."""
        clear_auto_target(MATCH_ID, "ghost")  # Should not raise


class TestGetAutoTarget:
    """Tests for get_auto_target()."""

    def setup_method(self):
        self.player = _make_unit("p1", team="a", x=1, y=1)
        self.enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": self.player, "e1": self.enemy})

    def teardown_method(self):
        _teardown()

    def test_get_auto_target_set(self):
        """Returns current target_id when set."""
        set_auto_target(MATCH_ID, "p1", "e1")
        assert get_auto_target(MATCH_ID, "p1") == "e1"

    def test_get_auto_target_none(self):
        """Returns None when not set."""
        assert get_auto_target(MATCH_ID, "p1") is None

    def test_get_auto_target_nonexistent_player(self):
        """Returns None for a nonexistent player."""
        assert get_auto_target(MATCH_ID, "ghost") is None

    def test_get_auto_target_after_clear(self):
        """Returns None after clearing."""
        set_auto_target(MATCH_ID, "p1", "e1")
        clear_auto_target(MATCH_ID, "p1")
        assert get_auto_target(MATCH_ID, "p1") is None


# ---------------------------------------------------------------------------
# Phase 10B — Chase Action Generation Tests
# ---------------------------------------------------------------------------

# Small test grid: 10×10, no obstacles by default
GRID_W = 10
GRID_H = 10
NO_OBSTACLES: set[tuple[int, int]] = set()


class TestGenerateAutoTargetAction:
    """Tests for generate_auto_target_action() — the core Phase 10B function."""

    def setup_method(self):
        self.player = _make_unit("p1", team="a", x=3, y=3)
        self.enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": self.player, "e1": self.enemy})
        # Set auto-target so generate function has something to act on
        set_auto_target(MATCH_ID, "p1", "e1")

    def teardown_method(self):
        _teardown()

    def _all_units(self) -> dict[str, PlayerState]:
        return _player_states[MATCH_ID]

    def test_attack_when_adjacent(self):
        """Unit adjacent to target → generates ATTACK at target's current coords."""
        # Move player next to enemy
        self.player.position = Position(x=4, y=5)
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.ATTACK
        assert action.target_x == 5
        assert action.target_y == 5
        assert action.player_id == "p1"

    def test_attack_diagonal_adjacent(self):
        """Unit diagonally adjacent to target → generates ATTACK."""
        self.player.position = Position(x=4, y=4)
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.ATTACK
        assert action.target_x == 5
        assert action.target_y == 5

    def test_chase_when_distant(self):
        """Unit 3+ tiles away → generates MOVE toward target."""
        self.player.position = Position(x=1, y=1)
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should move closer to enemy at (5,5) — next step is (2,2)
        assert action.target_x is not None
        assert action.target_y is not None
        # Verify we moved closer
        from app.core.ai_behavior import _heuristic
        old_dist = _heuristic((1, 1), (5, 5))
        new_dist = _heuristic((action.target_x, action.target_y), (5, 5))
        assert new_dist < old_dist

    def test_clears_on_target_death(self):
        """Target dies → auto-target cleared, returns None."""
        self.enemy.is_alive = False
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is None
        assert self.player.auto_target_id is None

    def test_clears_on_unreachable(self):
        """A* returns no path → auto-target cleared, returns None."""
        # Surround the enemy with obstacles so no path exists
        obstacles = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                obstacles.add((5 + dx, 5 + dy))

        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, obstacles,
        )
        assert action is None
        assert self.player.auto_target_id is None

    def test_no_action_without_auto_target(self):
        """Player without auto-target → returns None (no action generated)."""
        clear_auto_target(MATCH_ID, "p1")
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is None

    def test_clears_on_same_team(self):
        """If target somehow on same team → auto-target cleared."""
        self.enemy.team = "a"  # Switch to same team
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is None
        assert self.player.auto_target_id is None

    def test_uses_live_position(self):
        """Target moves between ticks → attack at new position, not stale one."""
        # Player adjacent to enemy at original position
        self.player.position = Position(x=4, y=5)
        # Enemy "moves" to a new position (simulating it moved last tick)
        self.enemy.position = Position(x=7, y=7)
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        # Not adjacent anymore → should MOVE, not attack old position
        assert action.action_type == ActionType.MOVE

    def test_dead_player_clears_auto_target(self):
        """Dead player → auto-target cleared, returns None."""
        self.player.is_alive = False
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is None
        assert self.player.auto_target_id is None


class TestAutoTargetDoorInteraction:
    """Tests for auto-target chase through doors (Phase 10B-1 door handling)."""

    def setup_method(self):
        self.player = _make_unit("p1", team="a", x=3, y=3)
        self.enemy = _make_unit("e1", team="b", x=5, y=3)
        _setup_match({"p1": self.player, "e1": self.enemy})
        set_auto_target(MATCH_ID, "p1", "e1")

    def teardown_method(self):
        _teardown()

    def _all_units(self) -> dict[str, PlayerState]:
        return _player_states[MATCH_ID]

    def test_door_interaction(self):
        """Path crosses closed door → generates INTERACT action."""
        # Put a wall across the path, with a door at (4,3)
        obstacles = set()
        for y in range(0, GRID_H):
            if y != 3:
                obstacles.add((4, y))
        # (4,3) is a closed door — included in obstacles but also in door_tiles
        obstacles.add((4, 3))
        door_tiles = {(4, 3)}

        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, obstacles,
            door_tiles=door_tiles,
        )
        assert action is not None
        assert action.action_type == ActionType.INTERACT
        assert action.target_x == 4
        assert action.target_y == 3


class TestAutoTargetInvalidation:
    """Tests for auto-target being cleared by new commands (Phase 10B-3)."""

    def setup_method(self):
        self.player = _make_unit("p1", team="a", x=1, y=1)
        self.enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": self.player, "e1": self.enemy})

    def teardown_method(self):
        _teardown()

    def test_queue_move_clears_auto_target(self):
        """Queueing a MOVE action clears auto-target (repositioning intent)."""
        set_auto_target(MATCH_ID, "p1", "e1")
        assert self.player.auto_target_id == "e1"

        action = PlayerAction(
            player_id="p1",
            action_type=ActionType.MOVE,
            target_x=2,
            target_y=1,
        )
        queue_action(MATCH_ID, "p1", action)
        assert self.player.auto_target_id is None

    def test_queue_skill_preserves_auto_target(self):
        """Queueing a SKILL action preserves auto-target (skill weaving)."""
        set_auto_target(MATCH_ID, "p1", "e1")
        assert self.player.auto_target_id == "e1"

        action = PlayerAction(
            player_id="p1",
            action_type=ActionType.SKILL,
            skill_id="double_strike",
            target_x=5,
            target_y=5,
            target_id="e1",
        )
        queue_action(MATCH_ID, "p1", action)
        assert self.player.auto_target_id == "e1"

    def test_queue_attack_preserves_auto_target(self):
        """Queueing an ATTACK action preserves auto-target (same combat intent)."""
        set_auto_target(MATCH_ID, "p1", "e1")
        assert self.player.auto_target_id == "e1"

        action = PlayerAction(
            player_id="p1",
            action_type=ActionType.ATTACK,
            target_x=5,
            target_y=5,
            target_id="e1",
        )
        queue_action(MATCH_ID, "p1", action)
        assert self.player.auto_target_id == "e1"

    def test_queue_ranged_attack_preserves_auto_target(self):
        """Queueing a RANGED_ATTACK action preserves auto-target."""
        set_auto_target(MATCH_ID, "p1", "e1")
        assert self.player.auto_target_id == "e1"

        action = PlayerAction(
            player_id="p1",
            action_type=ActionType.RANGED_ATTACK,
            target_x=5,
            target_y=5,
            target_id="e1",
        )
        queue_action(MATCH_ID, "p1", action)
        assert self.player.auto_target_id == "e1"

    def test_queue_use_item_preserves_auto_target(self):
        """Queueing a USE_ITEM action preserves auto-target (potion mid-fight)."""
        set_auto_target(MATCH_ID, "p1", "e1")
        assert self.player.auto_target_id == "e1"

        action = PlayerAction(
            player_id="p1",
            action_type=ActionType.USE_ITEM,
            target_x=1,
            target_y=1,
        )
        queue_action(MATCH_ID, "p1", action)
        assert self.player.auto_target_id == "e1"

    def test_queue_interact_clears_auto_target(self):
        """Queueing an INTERACT action clears auto-target (door/object intent)."""
        set_auto_target(MATCH_ID, "p1", "e1")
        assert self.player.auto_target_id == "e1"

        action = PlayerAction(
            player_id="p1",
            action_type=ActionType.INTERACT,
            target_x=2,
            target_y=1,
        )
        queue_action(MATCH_ID, "p1", action)
        assert self.player.auto_target_id is None

    def test_queue_loot_clears_auto_target(self):
        """Queueing a LOOT action clears auto-target (looting intent)."""
        set_auto_target(MATCH_ID, "p1", "e1")
        assert self.player.auto_target_id == "e1"

        action = PlayerAction(
            player_id="p1",
            action_type=ActionType.LOOT,
            target_x=2,
            target_y=1,
        )
        queue_action(MATCH_ID, "p1", action)
        assert self.player.auto_target_id is None

    def test_auto_target_no_override_queued_actions(self):
        """Player with queued MOVE → auto-target cleared but queue intact.

        The test verifies the design: generate_auto_target_action is only
        called when the queue is empty (the tick loop skips players with
        queued actions).  MOVE clears auto-target on queue insertion.
        """
        set_auto_target(MATCH_ID, "p1", "e1")
        # Queue a MOVE — repositioning clears auto-target
        action = PlayerAction(
            player_id="p1",
            action_type=ActionType.MOVE,
            target_x=2,
            target_y=1,
        )
        queue_action(MATCH_ID, "p1", action)
        assert self.player.auto_target_id is None

    def test_auto_target_survives_queued_skill(self):
        """Player with queued SKILL → auto-target preserved, resumes after drain."""
        set_auto_target(MATCH_ID, "p1", "e1")
        action = PlayerAction(
            player_id="p1",
            action_type=ActionType.SKILL,
            skill_id="war_cry",
            target_x=1,
            target_y=1,
        )
        queue_action(MATCH_ID, "p1", action)
        # Auto-target should survive — when queue drains, pursuit resumes
        assert self.player.auto_target_id == "e1"


class TestAutoTargetPartyMember:
    """Tests for auto-target on controlled party members (Phase 10B-4)."""

    def setup_method(self):
        self.player = _make_unit("p1", team="a", x=0, y=0)
        self.ally = PlayerState(
            player_id="ally1",
            username="Paladin Dave",
            position=Position(x=3, y=3),
            team="a",
            is_alive=True,
            unit_type="ai",
            controlled_by="p1",  # Controlled by player p1
        )
        self.enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": self.player, "ally1": self.ally, "e1": self.enemy})

    def teardown_method(self):
        _teardown()

    def _all_units(self) -> dict[str, PlayerState]:
        return _player_states[MATCH_ID]

    def test_party_member_auto_target(self):
        """Party member with auto-target generates chase action."""
        set_auto_target(MATCH_ID, "ally1", "e1")
        assert self.ally.auto_target_id == "e1"

        action = generate_auto_target_action(
            MATCH_ID, "ally1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.player_id == "ally1"
        # Ally at (3,3), enemy at (5,5) → should MOVE closer
        assert action.action_type == ActionType.MOVE

    def test_party_member_adjacent_attack(self):
        """Party member adjacent to target → ATTACK."""
        self.ally.position = Position(x=4, y=5)
        set_auto_target(MATCH_ID, "ally1", "e1")

        action = generate_auto_target_action(
            MATCH_ID, "ally1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.ATTACK
        assert action.target_x == 5
        assert action.target_y == 5


class TestAutoTargetPersistence:
    """Tests that auto-target persists across multiple ticks."""

    def setup_method(self):
        self.player = _make_unit("p1", team="a", x=1, y=1)
        self.enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": self.player, "e1": self.enemy})
        set_auto_target(MATCH_ID, "p1", "e1")

    def teardown_method(self):
        _teardown()

    def _all_units(self) -> dict[str, PlayerState]:
        return _player_states[MATCH_ID]

    def test_persists_across_ticks(self):
        """Auto-target stays set across multiple action generations (simulating ticks)."""
        for i in range(3):
            action = generate_auto_target_action(
                MATCH_ID, "p1", self._all_units(),
                GRID_W, GRID_H, NO_OBSTACLES,
            )
            assert action is not None, f"Failed on iteration {i}"
            assert action.action_type == ActionType.MOVE
            # Simulate moving closer
            self.player.position = Position(x=action.target_x, y=action.target_y)
            # Auto-target should still be set
            assert self.player.auto_target_id == "e1"

    def test_attack_every_tick_when_adjacent(self):
        """Adjacent to target → ATTACK generated every call until target changes."""
        self.player.position = Position(x=4, y=5)
        for i in range(3):
            action = generate_auto_target_action(
                MATCH_ID, "p1", self._all_units(),
                GRID_W, GRID_H, NO_OBSTACLES,
            )
            assert action is not None
            assert action.action_type == ActionType.ATTACK
            assert action.target_x == 5
            assert action.target_y == 5
            # Auto-target stays set
            assert self.player.auto_target_id == "e1"


class TestAutoTargetMultipleAttackers:
    """Tests for multiple units targeting the same enemy (Phase 10B/10F)."""

    def setup_method(self):
        self.p1 = _make_unit("p1", team="a", x=4, y=5)
        self.p2 = _make_unit("p2", team="a", x=6, y=5)
        self.enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": self.p1, "p2": self.p2, "e1": self.enemy})
        set_auto_target(MATCH_ID, "p1", "e1")
        set_auto_target(MATCH_ID, "p2", "e1")

    def teardown_method(self):
        _teardown()

    def _all_units(self) -> dict[str, PlayerState]:
        return _player_states[MATCH_ID]

    def test_multiple_attackers_both_get_actions(self):
        """Multiple units targeting same enemy → both get actions."""
        a1 = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        a2 = generate_auto_target_action(
            MATCH_ID, "p2", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert a1 is not None
        assert a2 is not None
        assert a1.action_type == ActionType.ATTACK
        assert a2.action_type == ActionType.ATTACK

    def test_multiple_attackers_all_clear_on_death(self):
        """Enemy dies → all auto-targets pointing to it should be cleared."""
        self.enemy.is_alive = False
        # Both should clear
        a1 = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        a2 = generate_auto_target_action(
            MATCH_ID, "p2", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert a1 is None
        assert a2 is None
        assert self.p1.auto_target_id is None
        assert self.p2.auto_target_id is None


# ---------------------------------------------------------------------------
# Phase 10G — Skill Auto-Target Tests
# ---------------------------------------------------------------------------


def _make_confessor(
    pid: str, team: str = "a", x: int = 0, y: int = 0,
) -> PlayerState:
    """Create a Confessor unit (has Heal skill)."""
    return PlayerState(
        player_id=pid,
        username=pid,
        position=Position(x=x, y=y),
        team=team,
        is_alive=True,
        unit_type="human",
        class_id="confessor",
    )


def _make_crusader(
    pid: str, team: str = "a", x: int = 0, y: int = 0,
) -> PlayerState:
    """Create a Crusader unit (has Shield Bash, Taunt, Holy Ground, Bulwark)."""
    return PlayerState(
        player_id=pid,
        username=pid,
        position=Position(x=x, y=y),
        team=team,
        is_alive=True,
        unit_type="human",
        class_id="crusader",
    )


def _make_ranger(
    pid: str, team: str = "a", x: int = 0, y: int = 0,
    ranged_range: int = 5,
) -> PlayerState:
    """Create a Ranger unit (has Power Shot)."""
    return PlayerState(
        player_id=pid,
        username=pid,
        position=Position(x=x, y=y),
        team=team,
        is_alive=True,
        unit_type="human",
        class_id="ranger",
        ranged_range=ranged_range,
    )


class TestSetAutoTargetWithSkill:
    """Tests for set_auto_target() with skill_id parameter (Phase 10G-1)."""

    def setup_method(self):
        self.player = _make_crusader("p1", team="a", x=1, y=1)
        self.enemy = _make_unit("e1", team="b", x=5, y=5)
        self.ally = _make_unit("a1", team="a", x=3, y=3)
        _setup_match({"p1": self.player, "e1": self.enemy, "a1": self.ally})

    def teardown_method(self):
        _teardown()

    def test_set_auto_target_with_skill(self):
        """Set auto-target with skill_id → both fields stored."""
        result = set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")
        assert result is True
        assert self.player.auto_target_id == "e1"
        assert self.player.auto_skill_id == "shield_bash"

    def test_set_auto_target_skill_wrong_class(self):
        """Player can't use the skill (wrong class) → error string."""
        # Crusader can't use "heal" (Confessor-only)
        result = set_auto_target(MATCH_ID, "p1", "e1", skill_id="heal")
        assert isinstance(result, str)
        assert self.player.auto_target_id is None
        assert self.player.auto_skill_id is None

    def test_set_auto_target_heal_on_enemy(self):
        """Heal skill on enemy → error (wrong targeting type)."""
        confessor = _make_confessor("c1", team="a", x=2, y=2)
        _player_states[MATCH_ID]["c1"] = confessor

        result = set_auto_target(MATCH_ID, "c1", "e1", skill_id="heal")
        assert isinstance(result, str)
        assert "enemy" in result.lower()
        assert confessor.auto_target_id is None

    def test_set_auto_target_heal_on_ally(self):
        """Heal skill on ally → success (same team allowed)."""
        confessor = _make_confessor("c1", team="a", x=2, y=2)
        _player_states[MATCH_ID]["c1"] = confessor

        result = set_auto_target(MATCH_ID, "c1", "a1", skill_id="heal")
        assert result is True
        assert confessor.auto_target_id == "a1"
        assert confessor.auto_skill_id == "heal"

    def test_set_auto_target_offensive_on_ally(self):
        """Offensive skill on ally → error."""
        result = set_auto_target(MATCH_ID, "p1", "a1", skill_id="shield_bash")
        assert isinstance(result, str)
        assert "ally" in result.lower() or "offensive" in result.lower()
        assert self.player.auto_target_id is None

    def test_set_auto_target_self_skill_rejected(self):
        """Self-targeting skill (Taunt) → error (doesn't support auto-targeting)."""
        result = set_auto_target(MATCH_ID, "p1", "e1", skill_id="taunt")
        assert isinstance(result, str)
        assert "auto-targeting" in result.lower() or "support" in result.lower()
        assert self.player.auto_target_id is None

    def test_set_auto_target_unknown_skill(self):
        """Unknown skill_id → error string."""
        result = set_auto_target(MATCH_ID, "p1", "e1", skill_id="fireball_9000")
        assert isinstance(result, str)
        assert "unknown" in result.lower() or "fireball" in result.lower()

    def test_clear_auto_target_clears_skill(self):
        """Clearing auto-target also clears auto_skill_id."""
        set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")
        assert self.player.auto_skill_id == "shield_bash"

        clear_auto_target(MATCH_ID, "p1")
        assert self.player.auto_target_id is None
        assert self.player.auto_skill_id is None

    def test_queue_move_clears_skill(self):
        """Queueing a MOVE action clears both auto_target_id and auto_skill_id."""
        set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")
        assert self.player.auto_skill_id == "shield_bash"

        action = PlayerAction(
            player_id="p1",
            action_type=ActionType.MOVE,
            target_x=2,
            target_y=1,
        )
        queue_action(MATCH_ID, "p1", action)
        assert self.player.auto_target_id is None
        assert self.player.auto_skill_id is None

    def test_queue_skill_preserves_auto_skill(self):
        """Queueing a SKILL preserves both auto_target_id and auto_skill_id."""
        set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")
        assert self.player.auto_skill_id == "shield_bash"

        action = PlayerAction(
            player_id="p1",
            action_type=ActionType.SKILL,
            skill_id="shield_bash",
            target_x=5,
            target_y=5,
            target_id="e1",
        )
        queue_action(MATCH_ID, "p1", action)
        assert self.player.auto_target_id == "e1"
        assert self.player.auto_skill_id == "shield_bash"


class TestGenerateSkillAutoTargetAction:
    """Tests for generate_auto_target_action() with skill awareness (Phase 10G-2)."""

    def setup_method(self):
        pass  # Each test sets up its own scenario

    def teardown_method(self):
        _teardown()

    def _all_units(self) -> dict[str, PlayerState]:
        return _player_states[MATCH_ID]

    def test_generate_skill_action_in_range(self):
        """In skill range + off cooldown → SKILL action generated."""
        # Crusader with Shield Bash (enemy_adjacent, range=1)
        player = _make_crusader("p1", team="a", x=4, y=5)
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "e1": enemy})

        set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "shield_bash"
        assert action.target_x == 5
        assert action.target_y == 5

    def test_generate_skill_action_out_of_range(self):
        """Out of skill range → MOVE toward target."""
        player = _make_crusader("p1", team="a", x=1, y=1)
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "e1": enemy})

        set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should move closer
        from app.core.ai_behavior import _heuristic
        old_dist = _heuristic((1, 1), (5, 5))
        new_dist = _heuristic((action.target_x, action.target_y), (5, 5))
        assert new_dist < old_dist

    def test_generate_skill_action_cooldown_in_range(self):
        """In skill range + on cooldown → fall back to class auto-attack."""
        player = _make_crusader("p1", team="a", x=4, y=5)
        player.cooldowns["shield_bash"] = 3
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "e1": enemy})

        set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        # Non-auto-attack skill on cooldown → falls back to class auto-attack
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "auto_attack_melee"
        # Auto-target should still be set (spell pursuit preserved)
        assert player.auto_target_id == "e1"
        assert player.auto_skill_id == "shield_bash"

    def test_generate_skill_action_cooldown_out_of_range(self):
        """Out of range + on cooldown → MOVE toward target (close gap while cooling)."""
        player = _make_crusader("p1", team="a", x=1, y=1)
        player.cooldowns["shield_bash"] = 2
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "e1": enemy})

        set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE

    def test_generate_skill_action_los_blocked(self):
        """In ranged skill range but LOS blocked → MOVE to reposition."""
        # Ranger with Power Shot (enemy_ranged, requires LOS)
        player = _make_ranger("p1", team="a", x=1, y=3, ranged_range=5)
        enemy = _make_unit("e1", team="b", x=5, y=3)
        _setup_match({"p1": player, "e1": enemy})

        # Wall blocking LOS between player and enemy
        obstacles = {(3, 3)}

        set_auto_target(MATCH_ID, "p1", "e1", skill_id="power_shot")
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, obstacles,
        )
        assert action is not None
        # In range (dist=4, ranged_range=5) but LOS blocked → MOVE to reposition
        assert action.action_type == ActionType.MOVE

    def test_generate_skill_action_los_clear(self):
        """In ranged skill range with clear LOS → SKILL action."""
        player = _make_ranger("p1", team="a", x=1, y=3, ranged_range=5)
        enemy = _make_unit("e1", team="b", x=5, y=3)
        _setup_match({"p1": player, "e1": enemy})

        set_auto_target(MATCH_ID, "p1", "e1", skill_id="power_shot")
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "power_shot"
        assert action.target_x == 5
        assert action.target_y == 3

    def test_generate_skill_action_heal_ally(self):
        """Heal auto-target on ally → SKILL action when in range."""
        confessor = _make_confessor("c1", team="a", x=3, y=3)
        ally = _make_unit("a1", team="a", x=4, y=3)
        ally.hp = 50  # Damaged so heal is useful
        _setup_match({"c1": confessor, "a1": ally})

        set_auto_target(MATCH_ID, "c1", "a1", skill_id="heal")
        action = generate_auto_target_action(
            MATCH_ID, "c1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "heal"
        assert action.target_x == 4
        assert action.target_y == 3

    def test_generate_skill_action_heal_out_of_range(self):
        """Heal auto-target on ally → MOVE when out of range."""
        confessor = _make_confessor("c1", team="a", x=0, y=0)
        ally = _make_unit("a1", team="a", x=8, y=8)
        _setup_match({"c1": confessor, "a1": ally})

        set_auto_target(MATCH_ID, "c1", "a1", skill_id="heal")
        action = generate_auto_target_action(
            MATCH_ID, "c1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE

    def test_generate_skill_action_uses_ranged_range(self):
        """Power Shot range=0 → uses player's ranged_range for effective range."""
        # Player at distance 4 from enemy, ranged_range=5 → in range
        player = _make_ranger("p1", team="a", x=1, y=3, ranged_range=5)
        enemy = _make_unit("e1", team="b", x=5, y=3)
        _setup_match({"p1": player, "e1": enemy})

        set_auto_target(MATCH_ID, "p1", "e1", skill_id="power_shot")
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.SKILL  # In range (dist 4 ≤ 5)

        # Now move player far away — out of range
        player.position = Position(x=0, y=0)
        player.auto_target_id = "e1"  # Re-set since clear may have happened
        player.auto_skill_id = "power_shot"

        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE  # Out of range (dist ~5.8 > 5)

    def test_generate_skill_action_persists_after_cast(self):
        """Skill cast → cooldown → auto-target persists → can cast again later."""
        player = _make_crusader("p1", team="a", x=4, y=5)
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "e1": enemy})

        set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")

        # Tick 1: In range, off cooldown → SKILL
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.SKILL
        # Auto-target persists
        assert player.auto_target_id == "e1"
        assert player.auto_skill_id == "shield_bash"

        # Simulate cooldown being applied after cast
        player.cooldowns["shield_bash"] = 3

        # Tick 2: In range, on cooldown → falls back to class auto-attack
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "auto_attack_melee"
        assert player.auto_target_id == "e1"

        # Simulate cooldown expiring
        player.cooldowns["shield_bash"] = 0

        # Tick 3: In range, off cooldown → SKILL again!
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "shield_bash"

    def test_generate_skill_melee_fallback(self):
        """No explicit skill_id → class auto-attack skill used."""
        player = _make_crusader("p1", team="a", x=4, y=5)
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "e1": enemy})

        # Set auto-target WITHOUT explicit skill — auto-attack resolved from class
        set_auto_target(MATCH_ID, "p1", "e1")
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "auto_attack_melee"

    def test_skill_auto_target_death_cleanup(self):
        """Target dies → both auto_target_id and auto_skill_id cleared."""
        player = _make_crusader("p1", team="a", x=1, y=1)
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "e1": enemy})

        set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")
        assert player.auto_target_id == "e1"
        assert player.auto_skill_id == "shield_bash"

        # Target dies
        enemy.is_alive = False
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is None
        assert player.auto_target_id is None
        assert player.auto_skill_id is None

    def test_skill_auto_target_unreachable(self):
        """Target unreachable with skill → auto-target cleared."""
        player = _make_crusader("p1", team="a", x=1, y=1)
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "e1": enemy})

        # Surround enemy with obstacles
        obstacles = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                obstacles.add((5 + dx, 5 + dy))

        set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, obstacles,
        )
        assert action is None
        assert player.auto_target_id is None
        assert player.auto_skill_id is None


# ---------------------------------------------------------------------------
# Phase 10G-8 — Edge Cases & Robustness Tests
# ---------------------------------------------------------------------------


class TestSkillAutoTargetEdgeCases:
    """Tests for Phase 10G-8 edge cases — robustness and defensive behaviour."""

    def teardown_method(self):
        _teardown()

    def _all_units(self) -> dict[str, PlayerState]:
        return _player_states[MATCH_ID]

    # --- Edge Case: Switch skills on same target ---

    def test_switch_skill_on_same_target(self):
        """Switching skills on the same target updates auto_skill_id cleanly."""
        player = _make_crusader("p1", team="a", x=1, y=1)
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "e1": enemy})

        # First set auto-target with Shield Bash
        result = set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")
        assert result is True
        assert player.auto_target_id == "e1"
        assert player.auto_skill_id == "shield_bash"

        # Switch to Taunt — should fail (self-targeting skill)
        result = set_auto_target(MATCH_ID, "p1", "e1", skill_id="taunt")
        assert isinstance(result, str)
        # Original auto-target should be cleared since set_auto_target clears queue on attempt
        # Actually, set_auto_target only clears queue on SUCCESS — on failure, state is unchanged
        # So auto_target_id should still be "e1" from the previous successful call
        assert player.auto_target_id == "e1"
        assert player.auto_skill_id == "shield_bash"

    def test_switch_from_melee_to_skill_on_same_target(self):
        """Switch from melee auto-target to skill auto-target on same enemy."""
        player = _make_crusader("p1", team="a", x=1, y=1)
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "e1": enemy})

        # Melee auto-target (no skill)
        result = set_auto_target(MATCH_ID, "p1", "e1")
        assert result is True
        assert player.auto_target_id == "e1"
        assert player.auto_skill_id is None

        # Switch to Shield Bash on same target
        result = set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")
        assert result is True
        assert player.auto_target_id == "e1"
        assert player.auto_skill_id == "shield_bash"

    def test_switch_from_skill_to_melee_on_same_target(self):
        """Switch from skill auto-target back to melee on same enemy."""
        player = _make_crusader("p1", team="a", x=1, y=1)
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "e1": enemy})

        # Skill auto-target
        result = set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")
        assert result is True
        assert player.auto_skill_id == "shield_bash"

        # Switch back to melee (no skill)
        result = set_auto_target(MATCH_ID, "p1", "e1")
        assert result is True
        assert player.auto_target_id == "e1"
        assert player.auto_skill_id is None

    # --- Edge Case: Skill becomes unavailable mid-pursuit ---

    def test_skill_unavailable_mid_pursuit_class_restriction(self):
        """Skill becomes unusable mid-pursuit (non-cooldown reason) → auto-target cancelled.

        Simulates a scenario where can_use_skill fails for a reason other than
        cooldown (e.g., the skill config changes or a future class-change mechanic).
        We achieve this by changing the player's class_id mid-pursuit.
        """
        player = _make_crusader("p1", team="a", x=4, y=5)
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "e1": enemy})

        set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")
        assert player.auto_skill_id == "shield_bash"

        # Tick 1: In range, correct class → should produce SKILL
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.SKILL

        # Now simulate class becoming incompatible (hypothetical future mechanic)
        player.class_id = "ranger"  # Rangers can't use Shield Bash
        player.auto_target_id = "e1"  # Re-set since we might need to
        player.auto_skill_id = "shield_bash"

        # Tick 2: can_use_skill should fail (class restriction), auto-target cleared
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is None
        assert player.auto_target_id is None
        assert player.auto_skill_id is None

    def test_skill_on_cooldown_mid_pursuit_keeps_going(self):
        """Skill on cooldown mid-pursuit is NOT a cancel reason — keep approaching."""
        player = _make_crusader("p1", team="a", x=1, y=1)
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "e1": enemy})

        set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")
        player.cooldowns["shield_bash"] = 5

        # Out of range + on cooldown → should MOVE (not cancel)
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE
        assert player.auto_target_id == "e1"
        assert player.auto_skill_id == "shield_bash"

    # --- Edge Case: Target healed to full (Heal-specific) ---

    def test_heal_on_full_hp_target_persists(self):
        """Heal auto-target on an ally at full HP still casts (overheal is graceful).

        The auto-target should NOT clear — the player may want to keep healing
        as the ally takes future damage.
        """
        confessor = _make_confessor("c1", team="a", x=3, y=3)
        ally = _make_unit("a1", team="a", x=4, y=3)
        ally.hp = ally.max_hp  # Full HP
        _setup_match({"c1": confessor, "a1": ally})

        set_auto_target(MATCH_ID, "c1", "a1", skill_id="heal")

        # In range, off cooldown → should still produce SKILL (server handles overheal)
        action = generate_auto_target_action(
            MATCH_ID, "c1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "heal"
        # Auto-target persists (player wants to keep healing)
        assert confessor.auto_target_id == "a1"
        assert confessor.auto_skill_id == "heal"

    # --- Edge Case: Party member skill auto-target ---

    def test_party_member_skill_auto_target(self):
        """Controlled party member can use skill auto-target."""
        # Player's controlled party member (a Crusader AI)
        party_member = PlayerState(
            player_id="ally1",
            username="Paladin Dave",
            position=Position(x=4, y=5),
            team="a",
            is_alive=True,
            unit_type="ai",
            controlled_by="p1",
            class_id="crusader",
        )
        player = _make_unit("p1", team="a", x=0, y=0)
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "ally1": party_member, "e1": enemy})

        # Set skill auto-target for the party member
        result = set_auto_target(MATCH_ID, "ally1", "e1", skill_id="shield_bash")
        assert result is True
        assert party_member.auto_target_id == "e1"
        assert party_member.auto_skill_id == "shield_bash"

        # Generate action — party member is adjacent, should produce SKILL
        action = generate_auto_target_action(
            MATCH_ID, "ally1", _player_states[MATCH_ID],
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "shield_bash"
        assert action.player_id == "ally1"

    def test_party_member_heal_skill_auto_target(self):
        """Controlled Confessor party member can heal-auto-target an ally."""
        confessor_party = PlayerState(
            player_id="healer1",
            username="Sister Mercy",
            position=Position(x=3, y=3),
            team="a",
            is_alive=True,
            unit_type="ai",
            controlled_by="p1",
            class_id="confessor",
        )
        player = _make_unit("p1", team="a", x=2, y=3)
        player.hp = 50  # Damaged
        enemy = _make_unit("e1", team="b", x=8, y=8)
        _setup_match({"p1": player, "healer1": confessor_party, "e1": enemy})

        # Set heal auto-target on the player
        result = set_auto_target(MATCH_ID, "healer1", "p1", skill_id="heal")
        assert result is True

        # In range → should produce SKILL
        action = generate_auto_target_action(
            MATCH_ID, "healer1", _player_states[MATCH_ID],
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "heal"
        assert action.player_id == "healer1"
        assert action.target_x == player.position.x
        assert action.target_y == player.position.y

    # --- Edge Case: Auto-target persists through multiple cast cycles ---

    def test_skill_auto_target_multi_cycle_persistence(self):
        """Auto-target persists through complete cast → cooldown → cast cycle.

        Validates the full lifecycle described in 10G-8: cast, wait through
        cooldown, cast again, target moves away, chase, cast again.
        """
        player = _make_crusader("p1", team="a", x=4, y=5)
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "e1": enemy})

        set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")

        # Cycle 1 — Cast
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action.action_type == ActionType.SKILL
        assert player.auto_target_id == "e1"

        # Simulate cooldown applied
        player.cooldowns["shield_bash"] = 3

        # Cycle 1 — Wait through cooldown → now falls back to auto-attack
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "auto_attack_melee"
        assert player.auto_target_id == "e1"

        # Simulate target fleeing while on cooldown
        enemy.position = Position(x=8, y=8)

        # Now out of range: should MOVE even on cooldown (close gap while cooling)
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action.action_type == ActionType.MOVE
        assert player.auto_target_id == "e1"

        # Cooldown expires, move player adjacent to new position
        player.cooldowns["shield_bash"] = 0
        player.position = Position(x=7, y=8)

        # Cycle 2 — Cast again
        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "shield_bash"
        assert player.auto_target_id == "e1"
        assert player.auto_skill_id == "shield_bash"

    # --- Edge Case: Target team changes (defensive) ---

    def test_offensive_skill_target_becomes_ally(self):
        """If target somehow becomes same-team, skill auto-target is cancelled.

        Defensive test — validates the team check inside generate_auto_target_action.
        """
        player = _make_crusader("p1", team="a", x=4, y=5)
        enemy = _make_unit("e1", team="b", x=5, y=5)
        _setup_match({"p1": player, "e1": enemy})

        set_auto_target(MATCH_ID, "p1", "e1", skill_id="shield_bash")

        # Target switches teams (hypothetical future mechanic)
        enemy.team = "a"

        action = generate_auto_target_action(
            MATCH_ID, "p1", self._all_units(),
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is None
        assert player.auto_target_id is None
        assert player.auto_skill_id is None

    def test_heal_target_becomes_enemy(self):
        """If heal target switches to enemy team, heal auto-target is cancelled."""
        confessor = _make_confessor("c1", team="a", x=3, y=3)
        ally = _make_unit("a1", team="a", x=4, y=3)
        _setup_match({"c1": confessor, "a1": ally})

        set_auto_target(MATCH_ID, "c1", "a1", skill_id="heal")

        # Ally switches teams (hypothetical)
        ally.team = "b"

        action = generate_auto_target_action(
            MATCH_ID, "c1", _player_states[MATCH_ID],
            GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is None
        assert confessor.auto_target_id is None
        assert confessor.auto_skill_id is None
