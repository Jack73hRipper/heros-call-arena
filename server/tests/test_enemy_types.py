"""
Tests for Phase 4C — Enemy Types & Enhanced AI.

Validates:
- Enemy config loads correctly (3 types with distinct stats)
- EnemyDefinition model works
- apply_enemy_stats applies correct stats to PlayerState
- Dungeon enemies spawn in correct rooms at correct positions
- Enemy naming: "Demon-1", "Skeleton-2", "Undead Knight"
- Enemies have correct enemy_type, ai_behavior, is_boss, room_id
- AI behavior dispatch works (aggressive, ranged, boss)
- Ranged AI retreats when enemies get close
- Boss AI stays in room (room leashing)
- Boss AI returns to room center when idle
- Existing arena AI unaffected (backward compat)
- Server payloads include enemy_type fields
- Room bounds caching and cleanup
"""

from __future__ import annotations

import pytest

from app.models.player import (
    PlayerState,
    Position,
    EnemyDefinition,
    load_enemies_config,
    get_enemy_definition,
    get_all_enemies,
    apply_enemy_stats,
    apply_class_stats,
    get_all_classes,
)
from app.models.actions import PlayerAction, ActionType
from app.core.ai_behavior import (
    decide_ai_action,
    run_ai_decisions,
    _decide_aggressive_action,
    _decide_ranged_action,
    _decide_boss_action,
    _add_room_leash_obstacles,
    _find_retreat_tile,
    set_room_bounds,
    clear_room_bounds,
    _get_room_bounds,
    clear_ai_patrol_state,
)
from app.core.match_manager import (
    create_match,
    start_match,
    get_match,
    get_match_players,
    get_players_snapshot,
    get_match_start_payload,
    remove_match,
    set_player_ready,
    _spawn_ai_units,
)
from app.core.map_loader import get_room_definitions
from app.models.match import MatchConfig, MatchType

# Force fresh enemy config load for each test module
import app.models.player as player_module
player_module._enemies_cache = None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_enemies_cache():
    """Reset enemies config cache before each test."""
    player_module._enemies_cache = None
    yield
    player_module._enemies_cache = None


def _make_dungeon_match():
    """Helper: create a dungeon match, return (match_id, host_player_id)."""
    config = MatchConfig(
        map_id="dungeon_test",
        match_type=MatchType.DUNGEON,
        max_players=5,
        ai_opponents=0,
        ai_allies=0,
    )
    match, host = create_match("TestHost", config=config)
    set_player_ready(match.match_id, host.player_id, True)
    return match.match_id, host.player_id


@pytest.fixture
def dungeon_match():
    """Create a dungeon match, start it, and clean up after."""
    match_id, host_pid = _make_dungeon_match()
    start_match(match_id)
    yield match_id
    remove_match(match_id)


@pytest.fixture
def arena_match():
    """Create an arena match and clean up after."""
    config = MatchConfig(
        map_id="arena_classic",
        match_type=MatchType.SOLO_PVE,
        ai_opponents=2,
    )
    match, host = create_match("TestHost", config=config)
    set_player_ready(match.match_id, host.player_id, True)
    yield match.match_id, host.player_id
    remove_match(match.match_id)


# ===========================================================================
# 1. Enemy Config Loading
# ===========================================================================

class TestEnemyConfigLoading:
    """Tests for enemies_config.json loading and EnemyDefinition model."""

    def test_load_enemies_config_returns_dict(self):
        enemies = load_enemies_config()
        assert isinstance(enemies, dict)
        assert len(enemies) == 25  # 12 original + 13 new enemy types

    def test_all_three_enemy_types_present(self):
        enemies = get_all_enemies()
        assert "demon" in enemies
        assert "skeleton" in enemies
        assert "undead_knight" in enemies

    def test_demon_definition(self):
        demon = get_enemy_definition("demon")
        assert demon is not None
        assert isinstance(demon, EnemyDefinition)
        assert demon.enemy_id == "demon"
        assert demon.name == "Demon"
        assert demon.base_hp == 240
        assert demon.base_melee_damage == 18
        assert demon.base_ranged_damage == 0
        assert demon.base_armor == 5
        assert demon.ai_behavior == "aggressive"
        assert demon.is_boss is False

    def test_skeleton_definition(self):
        skeleton = get_enemy_definition("skeleton")
        assert skeleton is not None
        assert skeleton.enemy_id == "skeleton"
        assert skeleton.name == "Skeleton"
        assert skeleton.base_hp == 125
        assert skeleton.base_ranged_damage == 14
        assert skeleton.ai_behavior == "ranged"
        assert skeleton.ranged_range == 5
        assert skeleton.is_boss is False

    def test_undead_knight_definition(self):
        uk = get_enemy_definition("undead_knight")
        assert uk is not None
        assert uk.enemy_id == "undead_knight"
        assert uk.name == "Undead Knight"
        assert uk.base_hp == 425
        assert uk.base_melee_damage == 25
        assert uk.base_armor == 12
        assert uk.ai_behavior == "boss"
        assert uk.is_boss is True

    def test_nonexistent_enemy_returns_none(self):
        assert get_enemy_definition("dragon") is None

    def test_enemy_definitions_have_colors_and_shapes(self):
        for eid in ["demon", "skeleton", "undead_knight"]:
            edef = get_enemy_definition(eid)
            assert edef.color, f"{eid} should have a color"
            assert edef.shape, f"{eid} should have a shape"


# ===========================================================================
# 2. apply_enemy_stats
# ===========================================================================

class TestApplyEnemyStats:
    """Tests for applying enemy type stats to PlayerState."""

    def test_apply_demon_stats(self):
        unit = PlayerState(player_id="e-1", username="Demon-1", unit_type="ai", team="b")
        result = apply_enemy_stats(unit, "demon", room_id="enemy_room_1")
        assert result is True
        assert unit.enemy_type == "demon"
        assert unit.hp == 240
        assert unit.max_hp == 240
        assert unit.attack_damage == 18
        assert unit.ranged_damage == 0
        assert unit.armor == 5
        assert unit.ai_behavior == "aggressive"
        assert unit.room_id == "enemy_room_1"
        assert unit.is_boss is False

    def test_apply_skeleton_stats(self):
        unit = PlayerState(player_id="e-2", username="Skeleton-1", unit_type="ai", team="b")
        result = apply_enemy_stats(unit, "skeleton", room_id="enemy_room_2")
        assert result is True
        assert unit.enemy_type == "skeleton"
        assert unit.hp == 125
        assert unit.ranged_damage == 14
        assert unit.ai_behavior == "ranged"

    def test_apply_undead_knight_stats(self):
        unit = PlayerState(player_id="e-3", username="Undead Knight", unit_type="ai", team="b")
        result = apply_enemy_stats(unit, "undead_knight", room_id="boss_room")
        assert result is True
        assert unit.enemy_type == "undead_knight"
        assert unit.hp == 425
        assert unit.attack_damage == 25
        assert unit.armor == 12
        assert unit.ai_behavior == "boss"
        assert unit.is_boss is True
        assert unit.room_id == "boss_room"

    def test_apply_nonexistent_enemy_returns_false(self):
        unit = PlayerState(player_id="e-4", username="Unknown", unit_type="ai", team="b")
        result = apply_enemy_stats(unit, "dragon")
        assert result is False
        assert unit.enemy_type is None

    def test_apply_enemy_stats_no_room(self):
        unit = PlayerState(player_id="e-5", username="Demon-1", unit_type="ai", team="b")
        apply_enemy_stats(unit, "demon")
        assert unit.room_id is None


# ===========================================================================
# 3. PlayerState New Fields
# ===========================================================================

class TestPlayerStateFields:
    """Tests for new Phase 4C fields on PlayerState."""

    def test_default_enemy_fields(self):
        p = PlayerState(player_id="p1", username="Player")
        assert p.enemy_type is None
        assert p.ai_behavior is None
        assert p.room_id is None
        assert p.is_boss is False

    def test_enemy_fields_set(self):
        p = PlayerState(
            player_id="e1", username="Boss",
            enemy_type="undead_knight", ai_behavior="boss",
            room_id="boss_room", is_boss=True,
        )
        assert p.enemy_type == "undead_knight"
        assert p.ai_behavior == "boss"
        assert p.room_id == "boss_room"
        assert p.is_boss is True

    def test_human_player_has_no_enemy_type(self):
        p = PlayerState(player_id="h1", username="Human", unit_type="human")
        assert p.enemy_type is None
        assert p.is_boss is False


# ===========================================================================
# 4. Dungeon Enemy Spawning
# ===========================================================================

class TestDungeonEnemySpawning:
    """Tests for _spawn_dungeon_enemies integration (via start_match)."""

    def test_dungeon_match_spawns_enemies(self, dungeon_match):
        all_players = get_match_players(dungeon_match)
        enemies = {pid: p for pid, p in all_players.items()
                   if p.unit_type == "ai" and p.enemy_type is not None}
        assert len(enemies) == 5

    def test_demon_enemies_in_demon_den(self, dungeon_match):
        all_players = get_match_players(dungeon_match)
        demons = [p for p in all_players.values() if p.enemy_type == "demon"]
        assert len(demons) == 2
        for d in demons:
            assert d.ai_behavior == "aggressive"
            assert d.room_id == "enemy_room_1"
            assert d.hp == 240
            assert d.attack_damage == 18
            assert d.team == "b"

    def test_skeleton_enemies_in_skeleton_hall(self, dungeon_match):
        all_players = get_match_players(dungeon_match)
        skeletons = [p for p in all_players.values() if p.enemy_type == "skeleton"]
        assert len(skeletons) == 2
        for s in skeletons:
            assert s.ai_behavior == "ranged"
            assert s.room_id == "enemy_room_2"
            assert s.hp == 125
            assert s.ranged_damage == 14

    def test_boss_in_boss_room(self, dungeon_match):
        all_players = get_match_players(dungeon_match)
        bosses = [p for p in all_players.values() if p.is_boss]
        assert len(bosses) == 1
        boss = bosses[0]
        assert boss.enemy_type == "undead_knight"
        assert boss.ai_behavior == "boss"
        assert boss.room_id == "boss_room"
        assert boss.hp == 425
        assert boss.username == "Undead Knight"

    def test_enemy_naming_convention(self, dungeon_match):
        all_players = get_match_players(dungeon_match)
        demons = [p for p in all_players.values() if p.enemy_type == "demon"]
        demon_names = sorted([d.username for d in demons])
        assert "Demon-1" in demon_names
        assert "Demon-2" in demon_names

        skeletons = [p for p in all_players.values() if p.enemy_type == "skeleton"]
        skel_names = sorted([s.username for s in skeletons])
        assert "Skeleton-1" in skel_names
        assert "Skeleton-2" in skel_names

    def test_enemies_on_team_b(self, dungeon_match):
        all_players = get_match_players(dungeon_match)
        enemies = [p for p in all_players.values() if p.enemy_type is not None]
        for e in enemies:
            assert e.team == "b"
            assert e.unit_type == "ai"

    def test_enemy_spawn_positions_correct(self, dungeon_match):
        all_players = get_match_players(dungeon_match)
        # Demon Den spawns at (12,3) and (13,2)
        demons = [p for p in all_players.values() if p.enemy_type == "demon"]
        demon_positions = {(d.position.x, d.position.y) for d in demons}
        assert (12, 3) in demon_positions
        assert (13, 2) in demon_positions

        # Boss at (16,17)
        bosses = [p for p in all_players.values() if p.is_boss]
        assert bosses[0].position.x == 16
        assert bosses[0].position.y == 17


# ===========================================================================
# 5. AI Behavior Dispatch
# ===========================================================================

class TestAIBehaviorDispatch:
    """Tests for AI behavior profile routing."""

    def _make_unit(self, pid, x, y, team="b", enemy_type=None, ai_behavior=None, room_id=None, is_boss=False, hp=100):
        u = PlayerState(
            player_id=pid, username=pid, unit_type="ai", team=team,
            position=Position(x=x, y=y), hp=hp, max_hp=hp,
            enemy_type=enemy_type, ai_behavior=ai_behavior,
            room_id=room_id, is_boss=is_boss,
        )
        if enemy_type:
            apply_enemy_stats(u, enemy_type, room_id)
        return u

    def _make_human(self, pid, x, y, team="a", hp=100):
        return PlayerState(
            player_id=pid, username=pid, unit_type="human", team=team,
            position=Position(x=x, y=y), hp=hp, max_hp=hp,
        )

    def test_aggressive_ai_closes_distance(self):
        """Aggressive AI should move toward enemy when far away."""
        ai = self._make_unit("demon1", 5, 5, enemy_type="demon", ai_behavior="aggressive")
        target = self._make_human("h1", 10, 10)
        all_units = {"demon1": ai, "h1": target}
        obstacles = set()

        action = decide_ai_action(ai, all_units, 20, 20, obstacles)
        assert action is not None
        assert action.action_type == ActionType.MOVE

    def test_aggressive_ai_attacks_adjacent(self):
        """Aggressive AI should melee attack when adjacent."""
        ai = self._make_unit("demon1", 5, 5, enemy_type="demon", ai_behavior="aggressive")
        target = self._make_human("h1", 5, 6)
        all_units = {"demon1": ai, "h1": target}
        obstacles = set()

        action = decide_ai_action(ai, all_units, 20, 20, obstacles)
        assert action is not None
        assert action.action_type == ActionType.ATTACK

    def test_ranged_ai_retreats_when_close(self):
        """Ranged AI should retreat when enemy is within 2 tiles."""
        ai = self._make_unit("skel1", 5, 5, enemy_type="skeleton", ai_behavior="ranged")
        target = self._make_human("h1", 5, 6)  # Adjacent
        all_units = {"skel1": ai, "h1": target}
        obstacles = set()

        action = decide_ai_action(ai, all_units, 20, 20, obstacles)
        assert action is not None
        # Should retreat (MOVE away), attack as last resort, or use a defensive skill
        assert action.action_type in (ActionType.MOVE, ActionType.ATTACK, ActionType.SKILL)
        if action.action_type == ActionType.MOVE:
            # Should be moving AWAY from the target
            new_dist = max(abs(action.target_x - 5), abs(action.target_y - 6))
            orig_dist = 1  # was adjacent
            assert new_dist > orig_dist

    def test_ranged_ai_shoots_at_range(self):
        """Ranged AI should use ranged attack when at good distance."""
        ai = self._make_unit("skel1", 5, 5, enemy_type="skeleton", ai_behavior="ranged")
        target = self._make_human("h1", 5, 9)  # 4 tiles away
        all_units = {"skel1": ai, "h1": target}
        obstacles = set()

        action = decide_ai_action(ai, all_units, 20, 20, obstacles)
        assert action is not None
        # Skeleton may use a skill (bone_shield) or fire ranged attack
        assert action.action_type in (ActionType.RANGED_ATTACK, ActionType.SKILL)
        if action.action_type == ActionType.RANGED_ATTACK:
            assert action.target_x == 5
            assert action.target_y == 9

    def test_boss_ai_attacks_in_room(self):
        """Boss AI should attack or use skill on enemy that enters its room."""
        # Set up room bounds
        rooms = [{"id": "boss_room", "bounds": {"x_min": 14, "y_min": 16, "x_max": 18, "y_max": 18}}]
        set_room_bounds("test-boss-match", rooms)

        ai = self._make_unit("boss1", 16, 17, enemy_type="undead_knight", ai_behavior="boss", room_id="boss_room", is_boss=True)
        target = self._make_human("h1", 16, 18)  # Adjacent, inside room
        all_units = {"boss1": ai, "h1": target}
        obstacles = set()

        action = decide_ai_action(ai, all_units, 20, 20, obstacles, match_id="test-boss-match")
        assert action is not None
        assert action.action_type in (ActionType.ATTACK, ActionType.SKILL)

        clear_room_bounds("test-boss-match")

    def test_boss_ai_waits_when_no_enemies_in_room(self):
        """Boss AI should wait/return to center when enemies are outside room."""
        rooms = [{"id": "boss_room", "bounds": {"x_min": 14, "y_min": 16, "x_max": 18, "y_max": 18}}]
        set_room_bounds("test-boss-match2", rooms)

        ai = self._make_unit("boss1", 16, 17, enemy_type="undead_knight", ai_behavior="boss", room_id="boss_room", is_boss=True)
        # Enemy far outside room
        target = self._make_human("h1", 3, 3)
        all_units = {"boss1": ai, "h1": target}
        obstacles = set()

        action = decide_ai_action(ai, all_units, 20, 20, obstacles, match_id="test-boss-match2")
        assert action is not None
        # Should wait or move to center — never leave room
        assert action.action_type in (ActionType.WAIT, ActionType.MOVE)
        if action.action_type == ActionType.MOVE:
            # Movement must be within room bounds
            assert 14 <= action.target_x <= 18
            assert 16 <= action.target_y <= 18

        clear_room_bounds("test-boss-match2")

    def test_default_behavior_for_arena_ai(self):
        """Arena AI without ai_behavior field should use aggressive (backward compat)."""
        ai = PlayerState(
            player_id="ai-old", username="AI-1",
            unit_type="ai", team="b",
            position=Position(x=5, y=5),
        )
        target = self._make_human("h1", 5, 6)
        all_units = {"ai-old": ai, "h1": target}
        obstacles = set()

        action = decide_ai_action(ai, all_units, 20, 20, obstacles)
        assert action is not None
        assert action.action_type == ActionType.ATTACK

    def test_run_ai_decisions_passes_match_id(self):
        """run_ai_decisions should pass match_id to individual AI decisions."""
        ai = self._make_unit("demon1", 5, 5, enemy_type="demon")
        target = self._make_human("h1", 10, 10)
        all_units = {"demon1": ai, "h1": target}
        obstacles = set()

        actions = run_ai_decisions(
            ["demon1"], all_units, 20, 20, obstacles,
            match_id="test-match",
        )
        assert len(actions) == 1


# ===========================================================================
# 6. Room Leashing
# ===========================================================================

class TestRoomLeashing:
    """Tests for room bounds caching and leash obstacles."""

    def test_set_and_get_room_bounds(self):
        rooms = [
            {"id": "room_a", "bounds": {"x_min": 1, "y_min": 1, "x_max": 5, "y_max": 5}},
            {"id": "room_b", "bounds": {"x_min": 10, "y_min": 10, "x_max": 15, "y_max": 14}},
        ]
        set_room_bounds("test-leash", rooms)

        bounds_a = _get_room_bounds("test-leash", "room_a")
        assert bounds_a is not None
        assert bounds_a["x_min"] == 1
        assert bounds_a["x_max"] == 5

        bounds_b = _get_room_bounds("test-leash", "room_b")
        assert bounds_b is not None
        assert bounds_b["x_min"] == 10

        clear_room_bounds("test-leash")

    def test_clear_room_bounds(self):
        rooms = [{"id": "rm", "bounds": {"x_min": 0, "y_min": 0, "x_max": 5, "y_max": 5}}]
        set_room_bounds("test-clear", rooms)
        clear_room_bounds("test-clear")
        assert _get_room_bounds("test-clear", "rm") is None

    def test_add_room_leash_obstacles(self):
        base_obstacles = {(0, 0)}
        bounds = {"x_min": 2, "y_min": 2, "x_max": 4, "y_max": 4}
        leashed = _add_room_leash_obstacles(base_obstacles, bounds, 6, 6)

        # Tiles inside room (2-4, 2-4) should NOT be in leashed obstacles
        # (unless they were already in base_obstacles)
        for x in range(2, 5):
            for y in range(2, 5):
                assert (x, y) not in leashed, f"({x},{y}) should be walkable inside room"

        # Tiles outside room should be obstacles
        assert (0, 0) in leashed  # Original obstacle
        assert (1, 1) in leashed  # Outside room
        assert (5, 5) in leashed  # Outside room

    def test_nonexistent_room_returns_none(self):
        assert _get_room_bounds("no-match", "no-room") is None


# ===========================================================================
# 7. Retreat Tile Finding
# ===========================================================================

class TestRetreatTile:
    """Tests for _find_retreat_tile helper."""

    def test_finds_tile_away_from_threat(self):
        ai_pos = (5, 5)
        threat_pos = (5, 6)  # South
        tile = _find_retreat_tile(ai_pos, threat_pos, 20, 20, set(), set())
        assert tile is not None
        # Should be further from threat
        new_dist = max(abs(tile[0] - threat_pos[0]), abs(tile[1] - threat_pos[1]))
        old_dist = 1
        assert new_dist > old_dist

    def test_no_retreat_when_surrounded(self):
        """When all tiles are blocked, returns None."""
        ai_pos = (1, 1)
        threat_pos = (1, 2)
        # Block everything around (1,1)
        obstacles = {(0, 0), (1, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2)}
        occupied = {(1, 2)}  # threat is there
        tile = _find_retreat_tile(ai_pos, threat_pos, 3, 3, obstacles, occupied)
        assert tile is None


# ===========================================================================
# 8. Server Payloads Include Enemy Fields
# ===========================================================================

class TestServerPayloads:
    """Tests that enemy_type, ai_behavior, is_boss appear in server payloads."""

    def test_players_snapshot_includes_enemy_fields(self, dungeon_match):
        snapshot = get_players_snapshot(dungeon_match)
        # Find a demon in the snapshot
        demon_entries = [v for v in snapshot.values() if v.get("enemy_type") == "demon"]
        assert len(demon_entries) > 0
        demon = demon_entries[0]
        assert demon["enemy_type"] == "demon"
        assert demon["ai_behavior"] == "aggressive"
        assert demon["is_boss"] is False

        # Find boss
        boss_entries = [v for v in snapshot.values() if v.get("is_boss") is True]
        assert len(boss_entries) == 1
        boss = boss_entries[0]
        assert boss["enemy_type"] == "undead_knight"
        assert boss["ai_behavior"] == "boss"

    def test_match_start_payload_includes_enemy_fields(self, dungeon_match):
        payload = get_match_start_payload(dungeon_match)
        assert payload is not None
        # Check that enemy data is in players
        enemy_players = {k: v for k, v in payload["players"].items()
                         if v.get("enemy_type") is not None}
        assert len(enemy_players) == 5  # 2 demons + 2 skeletons + 1 boss

        for pid, pdata in enemy_players.items():
            assert "enemy_type" in pdata
            assert "ai_behavior" in pdata
            assert "is_boss" in pdata


# ===========================================================================
# 9. Arena Backward Compatibility
# ===========================================================================

class TestArenaBackwardCompat:
    """Ensure arena mode AI still works without enemy_type fields."""

    def test_arena_ai_has_no_enemy_type(self, arena_match):
        from app.core.match_manager import _player_states
        match_id, host_pid = arena_match
        _spawn_ai_units(match_id)

        all_p = _player_states[match_id]
        ai_units = [p for p in all_p.values() if p.unit_type == "ai"]
        assert len(ai_units) == 2
        for ai in ai_units:
            assert ai.enemy_type is None
            assert ai.ai_behavior is None
            assert ai.is_boss is False
            assert ai.class_id is not None  # Should still get a class


# ===========================================================================
# 10. Dungeon Map Enemy Spawn Data
# ===========================================================================

class TestDungeonMapData:
    """Tests that dungeon map enemy_spawns have correct metadata."""

    def test_demon_den_has_typed_spawns(self):
        rooms = get_room_definitions("dungeon_test")
        demon_den = [r for r in rooms if r["id"] == "enemy_room_1"][0]
        spawns = demon_den.get("enemy_spawns", [])
        assert len(spawns) == 2
        for s in spawns:
            assert s.get("enemy_type") == "demon"

    def test_skeleton_hall_has_typed_spawns(self):
        rooms = get_room_definitions("dungeon_test")
        skel_hall = [r for r in rooms if r["id"] == "enemy_room_2"][0]
        spawns = skel_hall.get("enemy_spawns", [])
        assert len(spawns) == 2
        for s in spawns:
            assert s.get("enemy_type") == "skeleton"

    def test_boss_room_has_typed_boss_spawn(self):
        rooms = get_room_definitions("dungeon_test")
        boss_room = [r for r in rooms if r["id"] == "boss_room"][0]
        spawns = boss_room.get("enemy_spawns", [])
        assert len(spawns) == 1
        assert spawns[0]["enemy_type"] == "undead_knight"
        assert spawns[0].get("is_boss") is True

    def test_start_and_loot_rooms_have_no_enemy_spawns(self):
        rooms = get_room_definitions("dungeon_test")
        for room in rooms:
            if room["id"] in ("start_room", "loot_room"):
                spawns = room.get("enemy_spawns", [])
                assert len(spawns) == 0, f"{room['id']} should have no enemy_spawns"
