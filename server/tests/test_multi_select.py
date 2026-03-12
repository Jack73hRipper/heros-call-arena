"""
Tests for Phase 7B-1 — Server-Side Multi-Control.

Covers:
  - Multi-select: controlling multiple units simultaneously (no release-previous)
  - select_all_party: selects all alive party members
  - release_all_party: releases all controlled units
  - group_action: queues same action for multiple units
  - group_batch_actions: queues per-unit paths for multiple units
  - get_controlled_unit_ids: returns all controlled units with queued actions
  - Validation: only valid party members can be selected
  - Edge cases: dead units, enemy units, non-party members
"""

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.match_manager import (
    create_match,
    set_party_control,
    release_party_control,
    get_controlled_unit_ids,
    get_party_members,
    select_all_party,
    release_all_party,
    queue_group_action,
    queue_group_batch_actions,
    queue_action,
    get_player_queue,
    clear_player_queue,
    _player_states,
    _action_queues,
    _hero_ally_map,
    _active_matches,
)
from app.core.combat import load_combat_config


def setup_module():
    load_combat_config()


def _setup_party_match():
    """Create a match with a player and 3 hero ally AI units on the same team."""
    match, host = create_match("TestPlayer")
    mid = match.match_id
    pid = host.player_id

    # Create hero ally AI units
    ally1 = PlayerState(
        player_id="ally1",
        username="Hero_Alice",
        position=Position(x=2, y=2),
        hp=100, max_hp=100,
        unit_type="ai", team="a",
        class_id="crusader",
        hero_id="hero_alice_id",
    )
    ally2 = PlayerState(
        player_id="ally2",
        username="Hero_Bob",
        position=Position(x=3, y=2),
        hp=100, max_hp=100,
        unit_type="ai", team="a",
        class_id="ranger",
        hero_id="hero_bob_id",
    )
    ally3 = PlayerState(
        player_id="ally3",
        username="Hero_Carol",
        position=Position(x=4, y=2),
        hp=100, max_hp=100,
        unit_type="ai", team="a",
        class_id="confessor",
        hero_id="hero_carol_id",
    )

    _player_states[mid]["ally1"] = ally1
    _player_states[mid]["ally2"] = ally2
    _player_states[mid]["ally3"] = ally3

    # Register hero ownership
    _hero_ally_map[mid] = {
        "ally1": "TestPlayer",
        "ally2": "TestPlayer",
        "ally3": "TestPlayer",
    }

    return mid, pid


# ---------------------------------------------------------------------------
# Multi-Select (set_party_control no longer releases previous)
# ---------------------------------------------------------------------------

class TestMultiSelect:
    """Verify that set_party_control is additive — multiple units stay controlled."""

    def test_select_first_unit(self):
        mid, pid = _setup_party_match()
        assert set_party_control(mid, pid, "ally1") is True
        players = _player_states[mid]
        assert players["ally1"].controlled_by == pid

    def test_select_second_unit_keeps_first(self):
        """Selecting a second unit should NOT release the first (7B-1 change)."""
        mid, pid = _setup_party_match()
        set_party_control(mid, pid, "ally1")
        set_party_control(mid, pid, "ally2")
        players = _player_states[mid]
        assert players["ally1"].controlled_by == pid
        assert players["ally2"].controlled_by == pid

    def test_select_three_units_simultaneously(self):
        mid, pid = _setup_party_match()
        set_party_control(mid, pid, "ally1")
        set_party_control(mid, pid, "ally2")
        set_party_control(mid, pid, "ally3")
        players = _player_states[mid]
        assert players["ally1"].controlled_by == pid
        assert players["ally2"].controlled_by == pid
        assert players["ally3"].controlled_by == pid

    def test_release_one_keeps_others(self):
        mid, pid = _setup_party_match()
        set_party_control(mid, pid, "ally1")
        set_party_control(mid, pid, "ally2")
        set_party_control(mid, pid, "ally3")
        release_party_control(mid, pid, "ally2")
        players = _player_states[mid]
        assert players["ally1"].controlled_by == pid
        assert players["ally2"].controlled_by is None
        assert players["ally3"].controlled_by == pid

    def test_release_all_via_none(self):
        mid, pid = _setup_party_match()
        set_party_control(mid, pid, "ally1")
        set_party_control(mid, pid, "ally2")
        release_party_control(mid, pid, None)
        players = _player_states[mid]
        assert players["ally1"].controlled_by is None
        assert players["ally2"].controlled_by is None

    def test_select_dead_unit_fails(self):
        mid, pid = _setup_party_match()
        _player_states[mid]["ally1"].is_alive = False
        assert set_party_control(mid, pid, "ally1") is False

    def test_select_enemy_fails(self):
        """Cannot select enemy AI units."""
        mid, pid = _setup_party_match()
        enemy = PlayerState(
            player_id="enemy1",
            username="Demon",
            position=Position(x=10, y=10),
            unit_type="ai", team="b",
            enemy_type="demon",
        )
        _player_states[mid]["enemy1"] = enemy
        assert set_party_control(mid, pid, "enemy1") is False


# ---------------------------------------------------------------------------
# select_all_party
# ---------------------------------------------------------------------------

class TestSelectAllParty:
    """Verify select_all_party selects all alive hero allies."""

    def test_selects_all_alive_allies(self):
        mid, pid = _setup_party_match()
        selected = select_all_party(mid, pid)
        assert sorted(selected) == ["ally1", "ally2", "ally3"]
        players = _player_states[mid]
        assert all(players[uid].controlled_by == pid for uid in selected)

    def test_skips_dead_allies(self):
        mid, pid = _setup_party_match()
        _player_states[mid]["ally2"].is_alive = False
        selected = select_all_party(mid, pid)
        assert sorted(selected) == ["ally1", "ally3"]
        assert _player_states[mid]["ally2"].controlled_by is None

    def test_skips_enemy_units(self):
        mid, pid = _setup_party_match()
        enemy = PlayerState(
            player_id="enemy1",
            username="Demon",
            position=Position(x=10, y=10),
            unit_type="ai", team="b",
            enemy_type="demon",
        )
        _player_states[mid]["enemy1"] = enemy
        selected = select_all_party(mid, pid)
        assert "enemy1" not in selected
        assert sorted(selected) == ["ally1", "ally2", "ally3"]

    def test_skips_same_team_enemies(self):
        """Enemy types on the same team should not be selectable."""
        mid, pid = _setup_party_match()
        enemy = PlayerState(
            player_id="friendly_enemy",
            username="Skeleton",
            position=Position(x=10, y=10),
            unit_type="ai", team="a",
            enemy_type="skeleton",
        )
        _player_states[mid]["friendly_enemy"] = enemy
        selected = select_all_party(mid, pid)
        assert "friendly_enemy" not in selected

    def test_empty_party(self):
        match, host = create_match("Solo")
        selected = select_all_party(match.match_id, host.player_id)
        assert selected == []

    def test_party_state_includes_controlled_by(self):
        """get_party_members should reflect controlled_by for all selected units."""
        mid, pid = _setup_party_match()
        select_all_party(mid, pid)
        party = get_party_members(mid, pid)
        for member in party:
            assert member["controlled_by"] == pid


# ---------------------------------------------------------------------------
# release_all_party
# ---------------------------------------------------------------------------

class TestReleaseAllParty:
    """Verify release_all_party releases all controlled units."""

    def test_releases_all_controlled(self):
        mid, pid = _setup_party_match()
        select_all_party(mid, pid)
        released = release_all_party(mid, pid)
        assert sorted(released) == ["ally1", "ally2", "ally3"]
        players = _player_states[mid]
        assert all(players[uid].controlled_by is None for uid in released)

    def test_releases_only_own_units(self):
        """Should not release units controlled by OTHER players."""
        mid, pid = _setup_party_match()
        # Manually set ally1 as controlled by someone else
        _player_states[mid]["ally1"].controlled_by = "other_player"
        set_party_control(mid, pid, "ally2")
        set_party_control(mid, pid, "ally3")
        released = release_all_party(mid, pid)
        assert sorted(released) == ["ally2", "ally3"]
        assert _player_states[mid]["ally1"].controlled_by == "other_player"

    def test_release_when_none_controlled(self):
        mid, pid = _setup_party_match()
        released = release_all_party(mid, pid)
        assert released == []

    def test_party_state_after_release(self):
        mid, pid = _setup_party_match()
        select_all_party(mid, pid)
        release_all_party(mid, pid)
        party = get_party_members(mid, pid)
        for member in party:
            assert member["controlled_by"] is None


# ---------------------------------------------------------------------------
# get_controlled_unit_ids (existing, verify multi works)
# ---------------------------------------------------------------------------

class TestGetControlledUnitIds:
    """Verify get_controlled_unit_ids works with multiple controlled units."""

    def test_multiple_controlled_with_queues(self):
        mid, pid = _setup_party_match()
        select_all_party(mid, pid)
        # Queue actions for ally1 and ally2, not ally3
        action1 = PlayerAction(player_id="ally1", action_type=ActionType.MOVE, target_x=2, target_y=3)
        action2 = PlayerAction(player_id="ally2", action_type=ActionType.MOVE, target_x=3, target_y=3)
        queue_action(mid, "ally1", action1)
        queue_action(mid, "ally2", action2)
        controlled = get_controlled_unit_ids(mid)
        # Only ally1 and ally2 — ally3 has no queued actions
        assert controlled == {"ally1", "ally2"}

    def test_no_queue_means_not_in_controlled(self):
        """Controlled unit without queued actions should NOT be in the set."""
        mid, pid = _setup_party_match()
        set_party_control(mid, pid, "ally1")
        controlled = get_controlled_unit_ids(mid)
        assert "ally1" not in controlled

    def test_all_with_queues(self):
        mid, pid = _setup_party_match()
        select_all_party(mid, pid)
        for uid in ["ally1", "ally2", "ally3"]:
            action = PlayerAction(player_id=uid, action_type=ActionType.WAIT)
            queue_action(mid, uid, action)
        controlled = get_controlled_unit_ids(mid)
        assert controlled == {"ally1", "ally2", "ally3"}


# ---------------------------------------------------------------------------
# queue_group_action
# ---------------------------------------------------------------------------

class TestGroupAction:
    """Verify queuing the same action for multiple units."""

    def test_group_wait_for_all_controlled(self):
        mid, pid = _setup_party_match()
        select_all_party(mid, pid)
        result = queue_group_action(mid, pid, "wait")
        # Should queue for player + 3 allies
        assert len(result["queued"]) == 4
        assert pid in result["queued"]
        assert "ally1" in result["queued"]
        assert len(result["failed"]) == 0

    def test_group_move_for_specific_units(self):
        mid, pid = _setup_party_match()
        result = queue_group_action(
            mid, pid, "move",
            target_x=5, target_y=5,
            unit_ids=["ally1", "ally2"],
        )
        assert sorted(result["queued"]) == ["ally1", "ally2"]
        # Check queues have the action
        q1 = get_player_queue(mid, "ally1")
        assert len(q1) == 1
        assert q1[0].action_type == ActionType.MOVE
        assert q1[0].target_x == 5

    def test_group_action_fails_for_dead_unit(self):
        mid, pid = _setup_party_match()
        _player_states[mid]["ally1"].is_alive = False
        result = queue_group_action(mid, pid, "wait", unit_ids=["ally1", "ally2"])
        # ally1 should fail (dead), ally2 should succeed
        assert "ally2" in result["queued"]
        assert any(f["unit_id"] == "ally1" for f in result["failed"])

    def test_group_action_fails_for_non_party(self):
        mid, pid = _setup_party_match()
        result = queue_group_action(mid, pid, "wait", unit_ids=["nonexistent_unit"])
        assert len(result["queued"]) == 0
        assert len(result["failed"]) == 1

    def test_group_action_includes_player(self):
        """When unit_ids is None, player's own unit should be included."""
        mid, pid = _setup_party_match()
        select_all_party(mid, pid)
        result = queue_group_action(mid, pid, "wait")
        assert pid in result["queued"]

    def test_group_action_skill(self):
        """Group action with skill_id should propagate to all units."""
        mid, pid = _setup_party_match()
        result = queue_group_action(
            mid, pid, "skill",
            skill_id="heal",
            unit_ids=[pid],
        )
        assert pid in result["queued"]
        q = get_player_queue(mid, pid)
        assert q[0].skill_id == "heal"


# ---------------------------------------------------------------------------
# queue_group_batch_actions
# ---------------------------------------------------------------------------

class TestGroupBatchActions:
    """Verify queuing per-unit batch paths for multiple units."""

    def test_batch_two_units_different_paths(self):
        mid, pid = _setup_party_match()
        set_party_control(mid, pid, "ally1")
        set_party_control(mid, pid, "ally2")

        unit_actions = [
            {
                "unit_id": "ally1",
                "actions": [
                    {"action_type": "move", "target_x": 2, "target_y": 3},
                    {"action_type": "move", "target_x": 2, "target_y": 4},
                ],
            },
            {
                "unit_id": "ally2",
                "actions": [
                    {"action_type": "move", "target_x": 3, "target_y": 3},
                ],
            },
        ]
        result = queue_group_batch_actions(mid, pid, unit_actions)
        assert len(result["queued"]) == 2
        assert len(result["failed"]) == 0
        # Verify queue contents
        q1 = get_player_queue(mid, "ally1")
        q2 = get_player_queue(mid, "ally2")
        assert len(q1) == 2
        assert len(q2) == 1

    def test_batch_clears_existing_queue(self):
        """Batch should replace existing queued actions."""
        mid, pid = _setup_party_match()
        set_party_control(mid, pid, "ally1")
        # Queue an initial action
        action = PlayerAction(player_id="ally1", action_type=ActionType.WAIT)
        queue_action(mid, "ally1", action)
        assert len(get_player_queue(mid, "ally1")) == 1

        # Batch replace
        unit_actions = [
            {
                "unit_id": "ally1",
                "actions": [
                    {"action_type": "move", "target_x": 2, "target_y": 3},
                ],
            },
        ]
        queue_group_batch_actions(mid, pid, unit_actions)
        q = get_player_queue(mid, "ally1")
        assert len(q) == 1
        assert q[0].action_type == ActionType.MOVE

    def test_batch_rejects_non_party_member(self):
        mid, pid = _setup_party_match()
        unit_actions = [
            {
                "unit_id": "nonexistent",
                "actions": [{"action_type": "move", "target_x": 5, "target_y": 5}],
            },
        ]
        result = queue_group_batch_actions(mid, pid, unit_actions)
        assert len(result["queued"]) == 0
        assert len(result["failed"]) == 1

    def test_batch_invalid_action_type(self):
        mid, pid = _setup_party_match()
        set_party_control(mid, pid, "ally1")
        unit_actions = [
            {
                "unit_id": "ally1",
                "actions": [{"action_type": "invalid_type", "target_x": 5, "target_y": 5}],
            },
        ]
        result = queue_group_batch_actions(mid, pid, unit_actions)
        assert len(result["failed"]) == 1

    def test_batch_mixed_success_and_failure(self):
        mid, pid = _setup_party_match()
        _player_states[mid]["ally2"].is_alive = False
        unit_actions = [
            {
                "unit_id": "ally1",
                "actions": [{"action_type": "move", "target_x": 2, "target_y": 3}],
            },
            {
                "unit_id": "ally2",
                "actions": [{"action_type": "move", "target_x": 3, "target_y": 3}],
            },
        ]
        result = queue_group_batch_actions(mid, pid, unit_actions)
        assert any(e["unit_id"] == "ally1" for e in result["queued"])
        assert any(e["unit_id"] == "ally2" for e in result["failed"])

    def test_batch_player_self(self):
        """Player can include their own unit in group batch."""
        mid, pid = _setup_party_match()
        unit_actions = [
            {
                "unit_id": pid,
                "actions": [{"action_type": "wait"}],
            },
        ]
        result = queue_group_batch_actions(mid, pid, unit_actions)
        assert len(result["queued"]) == 1
        assert result["queued"][0]["unit_id"] == pid

    def test_batch_empty_actions_list(self):
        """Unit with empty actions list should not cause errors."""
        mid, pid = _setup_party_match()
        set_party_control(mid, pid, "ally1")
        unit_actions = [
            {
                "unit_id": "ally1",
                "actions": [],
            },
        ]
        result = queue_group_batch_actions(mid, pid, unit_actions)
        # No actions queued, but also no errors
        assert len(result["queued"]) == 0
        assert len(result["failed"]) == 0


# ---------------------------------------------------------------------------
# Regression: existing single-unit behavior unchanged
# ---------------------------------------------------------------------------

class TestRegression:
    """Verify that single-unit selection and action queueing still works."""

    def test_single_select_still_works(self):
        mid, pid = _setup_party_match()
        assert set_party_control(mid, pid, "ally1") is True
        party = get_party_members(mid, pid)
        a1 = next(m for m in party if m["unit_id"] == "ally1")
        assert a1["controlled_by"] == pid

    def test_single_action_queue_still_works(self):
        mid, pid = _setup_party_match()
        set_party_control(mid, pid, "ally1")
        action = PlayerAction(
            player_id="ally1",
            action_type=ActionType.MOVE,
            target_x=2, target_y=3,
        )
        result = queue_action(mid, "ally1", action)
        assert result is True
        q = get_player_queue(mid, "ally1")
        assert len(q) == 1

    def test_release_still_works(self):
        mid, pid = _setup_party_match()
        set_party_control(mid, pid, "ally1")
        assert release_party_control(mid, pid, "ally1") is True
        assert _player_states[mid]["ally1"].controlled_by is None

    def test_party_member_validation_unchanged(self):
        mid, pid = _setup_party_match()
        # Non-party unit cannot be selected
        assert set_party_control(mid, pid, "nonexistent") is False
        # Player cannot select themselves
        assert set_party_control(mid, pid, pid) is False
