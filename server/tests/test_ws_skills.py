"""
Tests for Phase 6C: WebSocket Protocol Extensions for Skills.

Covers:
- WS accepts action_type "skill" with valid skill_id
- WS rejects action_type "skill" without skill_id
- WS rejects action_type "skill" with invalid/unknown skill_id
- match_start payload includes class_skills data for all classes in match
- class_skills contain expected fields (skill_id, name, icon, etc.)
- turn_result payload includes cooldowns with skill cooldowns
- turn_result payload includes active_buffs
- get_players_snapshot includes active_buffs for all players
- Queue responses include skill_id for skill actions
- Queue updated after tick includes skill_id
- Batch actions include skill_id in queue response
- Remove_last preserves skill_id in remaining queue
- Party member selection includes skill_id in unit_queue
- Backward compat — existing WS tests pass, non-skill actions unaffected
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.websocket import ws_manager
from app.core.match_manager import (
    create_match,
    get_match,
    get_match_start_payload,
    get_match_start_payload_for_player,
    get_players_snapshot,
    queue_action,
    get_player_queue,
    _active_matches,
    _player_states,
    _action_queues,
    _class_selections,
)
from app.models.actions import PlayerAction, ActionType
from app.models.player import PlayerState, Position
from app.core.skills import load_skills_config, clear_skills_cache, get_class_skills, get_skill


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def _reset_state():
    """Reset all WS + match state between tests."""
    ws_manager._connections.clear()
    _active_matches.clear()
    _player_states.clear()
    _action_queues.clear()
    _class_selections.clear()
    clear_skills_cache()
    load_skills_config()
    yield
    ws_manager._connections.clear()
    _active_matches.clear()
    _player_states.clear()
    _action_queues.clear()
    _class_selections.clear()
    clear_skills_cache()


def _create_match_with_class(username="TestPlayer", class_id="crusader"):
    """Create a match and assign a class to the host player."""
    match, player = create_match(username)
    player.class_id = class_id
    match.status = "in_progress"
    return match, player


# ============================================================
# 1. WS Skill Action Acceptance & Validation
# ============================================================

class TestWSSkillActionValidation:
    """Tests for WS handler accepting/rejecting skill actions."""

    def test_skill_action_queued_with_valid_skill_id(self):
        """WS accepts action_type 'skill' with a valid skill_id."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            ws.send_json({
                "type": "action",
                "action_type": "skill",
                "skill_id": "double_strike",
                "target_x": 6,
                "target_y": 5,
            })
            msg = ws.receive_json()
            assert msg["type"] == "action_queued"
            assert msg["action_type"] == "skill"
            assert msg["skill_id"] == "double_strike"

    def test_skill_action_rejected_without_skill_id(self):
        """WS rejects action_type 'skill' when skill_id is missing."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            ws.send_json({
                "type": "action",
                "action_type": "skill",
                "target_x": 6,
                "target_y": 5,
            })
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "skill_id" in msg["message"].lower()

    def test_skill_action_rejected_with_unknown_skill_id(self):
        """WS rejects action_type 'skill' with an unknown skill_id."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            ws.send_json({
                "type": "action",
                "action_type": "skill",
                "skill_id": "fireball_9000",
                "target_x": 6,
                "target_y": 5,
            })
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "fireball_9000" in msg["message"]

    def test_skill_action_rejected_with_empty_skill_id(self):
        """WS rejects action_type 'skill' when skill_id is empty string."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            ws.send_json({
                "type": "action",
                "action_type": "skill",
                "skill_id": "",
                "target_x": 6,
                "target_y": 5,
            })
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_non_skill_action_still_works_without_skill_id(self):
        """Non-skill actions (move, attack, etc.) still work without skill_id."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            ws.send_json({
                "type": "action",
                "action_type": "move",
                "target_x": 6,
                "target_y": 5,
            })
            msg = ws.receive_json()
            assert msg["type"] == "action_queued"
            assert msg["action_type"] == "move"

    def test_wait_action_still_works(self):
        """Wait action still works (backward compat)."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            ws.send_json({
                "type": "action",
                "action_type": "wait",
            })
            msg = ws.receive_json()
            assert msg["type"] == "action_queued"
            assert msg["action_type"] == "wait"


# ============================================================
# 2. match_start Payload — class_skills
# ============================================================

class TestMatchStartClassSkills:
    """Tests for class_skills inclusion in match_start payload."""

    def test_match_start_includes_class_skills(self):
        """match_start payload includes class_skills for classes in the match."""
        match, player = _create_match_with_class("Alice", "crusader")
        payload = get_match_start_payload(match.match_id)
        assert payload is not None
        assert "class_skills" in payload
        assert "crusader" in payload["class_skills"]

    def test_class_skills_contain_correct_skill_ids(self):
        """Crusader class_skills should contain taunt and shield_bash (Phase 12 rework)."""
        match, player = _create_match_with_class("Alice", "crusader")
        payload = get_match_start_payload(match.match_id)
        crusader_skills = payload["class_skills"]["crusader"]
        skill_ids = [s["skill_id"] for s in crusader_skills]
        assert "taunt" in skill_ids
        assert "shield_bash" in skill_ids

    def test_class_skills_have_required_fields(self):
        """Each skill in class_skills should have expected fields."""
        match, player = _create_match_with_class("Alice", "crusader")
        payload = get_match_start_payload(match.match_id)
        for skill in payload["class_skills"]["crusader"]:
            assert "skill_id" in skill
            assert "name" in skill
            assert "icon" in skill
            assert "cooldown_turns" in skill
            assert "targeting" in skill
            assert "range" in skill
            assert "description" in skill
            assert "requires_line_of_sight" in skill

    def test_class_skills_multiple_classes(self):
        """match_start includes skills for all classes present."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid = match.match_id
        # Add a second player with a different class
        p2 = PlayerState(
            player_id="p2",
            username="Bob",
            position=Position(x=10, y=10),
            unit_type="human",
            team="b",
            class_id="confessor",
        )
        _player_states[mid]["p2"] = p2

        payload = get_match_start_payload(mid)
        assert "crusader" in payload["class_skills"]
        assert "confessor" in payload["class_skills"]
        # Confessor should have heal
        confessor_skill_ids = [s["skill_id"] for s in payload["class_skills"]["confessor"]]
        assert "heal" in confessor_skill_ids

    def test_class_skills_for_all_five_classes(self):
        """Verify all 5 class skill mappings are correct."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid = match.match_id
        # Add players of each class
        for i, cid in enumerate(["confessor", "inquisitor", "ranger", "hexblade"]):
            p = PlayerState(
                player_id=f"p{i+2}",
                username=f"Player{i+2}",
                position=Position(x=1+i, y=1+i),
                unit_type="human",
                team="a",
                class_id=cid,
            )
            _player_states[mid][f"p{i+2}"] = p

        payload = get_match_start_payload(mid)
        cs = payload["class_skills"]
        assert set(cs.keys()) == {"crusader", "confessor", "inquisitor", "ranger", "hexblade"}

        # Verify expected skill lists by ID
        assert {s["skill_id"] for s in cs["crusader"]} == {"auto_attack_melee", "taunt", "shield_bash", "holy_ground", "bulwark"}
        assert {s["skill_id"] for s in cs["confessor"]} == {"auto_attack_melee", "heal", "shield_of_faith", "exorcism", "prayer"}
        assert {s["skill_id"] for s in cs["inquisitor"]} == {"auto_attack_ranged", "power_shot", "shadow_step", "seal_of_judgment", "rebuke"}
        assert {s["skill_id"] for s in cs["ranger"]} == {"auto_attack_ranged", "power_shot", "volley", "evasion", "crippling_shot"}
        assert {s["skill_id"] for s in cs["hexblade"]} == {"auto_attack_melee", "double_strike", "shadow_step", "wither", "ward"}

    def test_class_skills_not_included_when_no_class(self):
        """If player has no class_id, class_skills is empty or absent."""
        match, player = create_match("Alice")
        player.class_id = None
        payload = get_match_start_payload(match.match_id)
        # class_skills either absent or empty
        cs = payload.get("class_skills", {})
        assert len(cs) == 0

    def test_per_player_payload_includes_class_skills(self):
        """get_match_start_payload_for_player also includes class_skills."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        # Need to set FOV for per-player payload
        from app.core.match_manager import set_fov_cache
        set_fov_cache(mid, pid, {(1, 1), (2, 2)})
        payload = get_match_start_payload_for_player(mid, pid)
        assert payload is not None
        assert "class_skills" in payload
        assert "crusader" in payload["class_skills"]


# ============================================================
# 3. Players Snapshot — active_buffs & cooldowns
# ============================================================

class TestPlayersSnapshotSkillState:
    """Tests for active_buffs and skill cooldowns in player snapshots."""

    def test_snapshot_includes_active_buffs(self):
        """get_players_snapshot includes active_buffs for each player."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid = match.match_id
        snapshot = get_players_snapshot(mid)
        pid = player.player_id
        assert "active_buffs" in snapshot[pid]
        assert snapshot[pid]["active_buffs"] == []

    def test_snapshot_with_active_buff(self):
        """Snapshot reflects active buffs when present."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid = match.match_id
        player.active_buffs = [
            {"buff_id": "war_cry", "stat": "melee_damage_multiplier",
             "magnitude": 2.0, "turns_remaining": 2}
        ]
        snapshot = get_players_snapshot(mid)
        pid = player.player_id
        assert len(snapshot[pid]["active_buffs"]) == 1
        assert snapshot[pid]["active_buffs"][0]["buff_id"] == "war_cry"
        assert snapshot[pid]["active_buffs"][0]["turns_remaining"] == 2

    def test_snapshot_includes_skill_cooldowns(self):
        """Snapshot cooldowns dict includes per-skill cooldowns."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid = match.match_id
        player.cooldowns = {"ranged_attack": 2, "double_strike": 3, "war_cry": 5}
        snapshot = get_players_snapshot(mid)
        pid = player.player_id
        assert snapshot[pid]["cooldowns"]["double_strike"] == 3
        assert snapshot[pid]["cooldowns"]["war_cry"] == 5
        assert snapshot[pid]["cooldowns"]["ranged_attack"] == 2

    def test_snapshot_empty_buffs_and_cooldowns(self):
        """Snapshot defaults: empty buffs, empty cooldowns."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid = match.match_id
        snapshot = get_players_snapshot(mid)
        pid = player.player_id
        assert snapshot[pid]["active_buffs"] == []
        assert snapshot[pid]["cooldowns"] == {}


# ============================================================
# 4. Queue Responses — skill_id in queue payloads
# ============================================================

class TestQueueSkillId:
    """Tests for skill_id inclusion in queue-related WS responses."""

    def test_action_queued_response_includes_skill_id(self):
        """action_queued response includes skill_id when action is a skill."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            ws.send_json({
                "type": "action",
                "action_type": "skill",
                "skill_id": "war_cry",
            })
            msg = ws.receive_json()
            assert msg["type"] == "action_queued"
            assert msg["skill_id"] == "war_cry"
            # Queue should also include skill_id
            assert len(msg["queue"]) == 1
            assert msg["queue"][0]["skill_id"] == "war_cry"
            assert msg["queue"][0]["action_type"] == "skill"

    def test_queue_contains_skill_id_for_mixed_actions(self):
        """Queue with both regular and skill actions includes skill_id correctly."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            # Queue a move first
            ws.send_json({"type": "action", "action_type": "move", "target_x": 2, "target_y": 3})
            ws.receive_json()  # consume response

            # Queue a skill
            ws.send_json({
                "type": "action",
                "action_type": "skill",
                "skill_id": "double_strike",
                "target_x": 3,
                "target_y": 3,
            })
            msg = ws.receive_json()
            assert msg["type"] == "action_queued"
            assert len(msg["queue"]) == 2
            # First action is move — skill_id should be None
            assert msg["queue"][0]["action_type"] == "move"
            assert msg["queue"][0]["skill_id"] is None
            # Second action is skill
            assert msg["queue"][1]["action_type"] == "skill"
            assert msg["queue"][1]["skill_id"] == "double_strike"

    def test_batch_actions_include_skill_id(self):
        """Batch queue response includes skill_id for skill actions."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            ws.send_json({
                "type": "batch_actions",
                "actions": [
                    {"action_type": "move", "target_x": 3, "target_y": 3},
                    {"action_type": "skill", "skill_id": "war_cry"},
                ],
            })
            msg = ws.receive_json()
            assert msg["type"] == "queue_updated"
            assert len(msg["queue"]) == 2
            assert msg["queue"][0]["action_type"] == "move"
            assert msg["queue"][0]["skill_id"] is None
            assert msg["queue"][1]["action_type"] == "skill"
            assert msg["queue"][1]["skill_id"] == "war_cry"

    def test_remove_last_preserves_skill_id(self):
        """After remove_last, remaining queue items still include skill_id."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            # Queue skill + move
            ws.send_json({
                "type": "action", "action_type": "skill",
                "skill_id": "double_strike", "target_x": 6, "target_y": 5,
            })
            ws.receive_json()  # consume
            ws.send_json({"type": "action", "action_type": "move", "target_x": 3, "target_y": 3})
            ws.receive_json()  # consume

            # Remove last (the move)
            ws.send_json({"type": "remove_last"})
            msg = ws.receive_json()
            assert msg["type"] == "queue_updated"
            assert len(msg["queue"]) == 1
            assert msg["queue"][0]["action_type"] == "skill"
            assert msg["queue"][0]["skill_id"] == "double_strike"


# ============================================================
# 5. Backward Compatibility
# ============================================================

class TestWSBackwardCompat:
    """Ensure existing non-skill WS flows are unaffected."""

    def test_move_action_unchanged(self):
        """Move action still works exactly as before."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            ws.send_json({"type": "action", "action_type": "move", "target_x": 5, "target_y": 3})
            msg = ws.receive_json()
            assert msg["type"] == "action_queued"
            assert msg["action_type"] == "move"
            assert msg["target_x"] == 5
            assert msg["target_y"] == 3

    def test_attack_action_unchanged(self):
        """Attack action still works exactly as before."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            ws.send_json({"type": "action", "action_type": "attack", "target_x": 6, "target_y": 5})
            msg = ws.receive_json()
            assert msg["type"] == "action_queued"
            assert msg["action_type"] == "attack"

    def test_ranged_attack_action_unchanged(self):
        """Ranged attack action still works."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            ws.send_json({
                "type": "action", "action_type": "ranged_attack",
                "target_x": 8, "target_y": 5
            })
            msg = ws.receive_json()
            assert msg["type"] == "action_queued"
            assert msg["action_type"] == "ranged_attack"

    def test_unknown_action_type_still_rejected(self):
        """Unknown action types still return error."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            ws.send_json({"type": "action", "action_type": "fly"})
            msg = ws.receive_json()
            assert msg["type"] == "error"

    def test_clear_queue_unchanged(self):
        """Clear queue still works."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        client = TestClient(app)
        with client.websocket_connect(f"/ws/{mid}/{pid}") as ws:
            ws.send_json({"type": "action", "action_type": "wait"})
            ws.receive_json()
            ws.send_json({"type": "clear_queue"})
            msg = ws.receive_json()
            assert msg["type"] == "queue_cleared"
            assert msg["queue"] == []


# ============================================================
# 6. Skill-specific Integration — Skill in Queue Serialization
# ============================================================

class TestSkillQueueSerialization:
    """Test that skill actions serialize correctly through the queue system."""

    def test_skill_action_persists_in_queue(self):
        """A skill action queued via WS survives in the internal queue."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        action = PlayerAction(
            player_id=pid,
            action_type=ActionType.SKILL,
            target_x=6,
            target_y=5,
            skill_id="double_strike",
        )
        result = queue_action(mid, pid, action)
        assert result is True

        queue = get_player_queue(mid, pid)
        assert len(queue) == 1
        assert queue[0].action_type == ActionType.SKILL
        assert queue[0].skill_id == "double_strike"
        assert queue[0].target_x == 6
        assert queue[0].target_y == 5

    def test_multiple_skills_in_queue(self):
        """Multiple skill actions can be queued."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id
        for sid in ["double_strike", "war_cry"]:
            action = PlayerAction(
                player_id=pid,
                action_type=ActionType.SKILL,
                skill_id=sid,
            )
            queue_action(mid, pid, action)

        queue = get_player_queue(mid, pid)
        assert len(queue) == 2
        assert queue[0].skill_id == "double_strike"
        assert queue[1].skill_id == "war_cry"

    def test_skill_action_wait_interleaved(self):
        """Skills and regular actions can be interleaved in queue."""
        match, player = _create_match_with_class("Alice", "crusader")
        mid, pid = match.match_id, player.player_id

        queue_action(mid, pid, PlayerAction(
            player_id=pid, action_type=ActionType.MOVE, target_x=3, target_y=3,
        ))
        queue_action(mid, pid, PlayerAction(
            player_id=pid, action_type=ActionType.SKILL, skill_id="war_cry",
        ))
        queue_action(mid, pid, PlayerAction(
            player_id=pid, action_type=ActionType.ATTACK, target_x=4, target_y=3,
        ))

        queue = get_player_queue(mid, pid)
        assert len(queue) == 3
        assert queue[0].action_type == ActionType.MOVE
        assert queue[0].skill_id is None
        assert queue[1].action_type == ActionType.SKILL
        assert queue[1].skill_id == "war_cry"
        assert queue[2].action_type == ActionType.ATTACK
        assert queue[2].skill_id is None


# ============================================================
# 7. Skill Definition Cross-Reference
# ============================================================

class TestSkillDefinitionCrossRef:
    """Verify that class_skills in payload match skills_config.json exactly."""

    def test_skill_definitions_match_config(self):
        """Skill definitions in payload should match the config file."""
        match, player = _create_match_with_class("Alice", "crusader")
        payload = get_match_start_payload(match.match_id)

        for skill_info in payload["class_skills"]["crusader"]:
            config_skill = get_skill(skill_info["skill_id"])
            assert config_skill is not None
            assert skill_info["name"] == config_skill["name"]
            assert skill_info["icon"] == config_skill["icon"]
            assert skill_info["cooldown_turns"] == config_skill["cooldown_turns"]
            assert skill_info["targeting"] == config_skill["targeting"]
            assert skill_info["range"] == config_skill["range"]
            assert skill_info["description"] == config_skill["description"]

    def test_class_skills_order_matches_config(self):
        """The order of skills in payload matches the class_skills order in config."""
        match, player = _create_match_with_class("Alice", "crusader")
        payload = get_match_start_payload(match.match_id)
        payload_order = [s["skill_id"] for s in payload["class_skills"]["crusader"]]
        config_order = get_class_skills("crusader")
        assert payload_order == config_order
