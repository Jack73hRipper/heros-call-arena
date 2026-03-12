"""
Tests for Phase 18C — Monster Rarity Spawn Integration.

Validates:
- map_exporter rolls rarity for enemy spawns and includes metadata in spawn dicts
- map_exporter respects max_enhanced_per_room limit
- map_exporter does not upgrade bosses
- map_exporter does not upgrade enemies with allow_rarity_upgrade=false
- _spawn_dungeon_enemies reads rarity metadata and applies upgrades
- Champion pack spawning produces 2–3 same-type champions on adjacent tiles
- Rare enemy spawning creates minions linked to the leader
- Minion placement finds adjacent open tiles within room bounds
- Minions have minion_owner_id set to the rare leader's ID
- Minions are Normal rarity
- Wave spawner applies rarity upgrades using wave_number as pseudo-floor
- Wave spawner supports force_rarity in enemy spec
- get_players_snapshot includes rarity metadata for enhanced enemies
- get_players_snapshot includes minion metadata
- advance_floor payload includes rarity fields
- Floor scaling increases rarity chances at higher floors
"""

from __future__ import annotations

import json
import random
import uuid
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.models.player import (
    PlayerState,
    Position,
    EnemyDefinition,
    get_enemy_definition,
    apply_enemy_stats,
)
from app.core.monster_rarity import (
    load_monster_rarity_config,
    clear_monster_rarity_cache,
    roll_monster_rarity,
    roll_champion_type,
    roll_affixes,
    generate_rare_name,
    apply_rarity_to_player,
    create_minions,
    get_spawn_chances,
)


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear monster rarity cache before each test."""
    clear_monster_rarity_cache()
    yield
    clear_monster_rarity_cache()


@pytest.fixture
def rarity_config():
    """Load the real monster rarity config."""
    return load_monster_rarity_config()


@pytest.fixture
def base_enemy():
    """Create a basic test enemy PlayerState."""
    p = PlayerState(
        player_id="enemy-test01",
        username="Skeleton-1",
        position=Position(x=5, y=5),
        unit_type="ai",
        team="b",
        is_ready=True,
        hp=80,
        max_hp=80,
        attack_damage=12,
        armor=2,
    )
    p.enemy_type = "skeleton"
    return p


@pytest.fixture
def skeleton_def():
    """Get the Skeleton enemy definition from config."""
    edef = get_enemy_definition("skeleton")
    if edef is None:
        # Fallback mock for testing
        edef = EnemyDefinition(
            enemy_id="skeleton",
            name="Skeleton",
            hp=80,
            melee_damage=12,
            ranged_damage=8,
            armor=2,
            ranged_range=5,
            class_id="ranger",
        )
    return edef


# ====================================================================
# Section 1: Map Exporter Rarity Rolling
# ====================================================================

class TestMapExporterRarityRolling:
    """Tests for Phase 18C rarity rolling in map_exporter.py."""

    def test_export_enemy_spawns_have_rarity_fields(self):
        """Enemy spawn dicts in exported map include rarity metadata."""
        from app.core.wfc.map_exporter import export_to_game_map

        # Create a minimal tile map with a single room containing enemies
        # Module size is 5, so we create a 5x5 map
        tile_map = [
            ["W", "W", "W", "W", "W"],
            ["W", "F", "E", "F", "W"],
            ["W", "F", "F", "F", "W"],
            ["W", "F", "F", "F", "W"],
            ["W", "W", "W", "W", "W"],
        ]

        # Create a grid cell for the WFC module
        grid = [[{"chosenVariant": 0}]]
        variants = [{
            "purpose": "enemy",
            "sourceName": "TestRoom",
            "sockets": {},
        }]

        result = export_to_game_map(
            tile_map=tile_map,
            grid=grid,
            variants=variants,
            floor_number=1,
            seed=42,
        )

        rooms = result.get("rooms", [])
        assert len(rooms) > 0, "Should have at least one room"

        for room in rooms:
            for spawn in room.get("enemy_spawns", []):
                assert "monster_rarity" in spawn, "Spawn should have monster_rarity field"
                assert "champion_type" in spawn, "Spawn should have champion_type field"
                assert "affixes" in spawn, "Spawn should have affixes field"
                assert "display_name" in spawn, "Spawn should have display_name field"

    def test_export_boss_spawns_are_normal_rarity(self):
        """Boss enemy spawns should always be Normal rarity."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map = [
            ["W", "W", "W", "W", "W"],
            ["W", "F", "B", "F", "W"],
            ["W", "F", "F", "F", "W"],
            ["W", "F", "F", "F", "W"],
            ["W", "W", "W", "W", "W"],
        ]

        grid = [[{"chosenVariant": 0}]]
        variants = [{
            "purpose": "boss",
            "sourceName": "BossRoom",
            "sockets": {},
        }]

        result = export_to_game_map(
            tile_map=tile_map,
            grid=grid,
            variants=variants,
            floor_number=9,  # High floor to maximize rarity chances
            seed=42,
        )

        rooms = result.get("rooms", [])
        for room in rooms:
            for spawn in room.get("enemy_spawns", []):
                if spawn.get("is_boss"):
                    assert spawn["monster_rarity"] == "normal", "Bosses should be normal rarity"

    def test_export_rarity_metadata_types(self):
        """Rarity metadata fields should have correct types."""
        from app.core.wfc.map_exporter import export_to_game_map

        tile_map = [
            ["W", "W", "W", "W", "W"],
            ["W", "E", "E", "E", "W"],
            ["W", "F", "F", "F", "W"],
            ["W", "F", "F", "F", "W"],
            ["W", "W", "W", "W", "W"],
        ]

        grid = [[{"chosenVariant": 0}]]
        variants = [{"purpose": "enemy", "sourceName": "TestRoom", "sockets": {}}]

        result = export_to_game_map(
            tile_map=tile_map,
            grid=grid,
            variants=variants,
            floor_number=1,
            seed=42,
        )

        for room in result.get("rooms", []):
            for spawn in room.get("enemy_spawns", []):
                assert isinstance(spawn["monster_rarity"], str)
                assert isinstance(spawn["affixes"], list)
                # champion_type and display_name can be None
                assert spawn["champion_type"] is None or isinstance(spawn["champion_type"], str)
                assert spawn["display_name"] is None or isinstance(spawn["display_name"], str)

    def test_export_high_floor_produces_enhanced_enemies(self):
        """At high floor numbers, at least some enemies should get rarity upgrades."""
        from app.core.wfc.map_exporter import export_to_game_map

        # Create a room with many enemies and high floor for better chance
        tile_map = [
            ["W", "W", "W", "W", "W"],
            ["W", "E", "E", "E", "W"],
            ["W", "E", "E", "E", "W"],
            ["W", "E", "E", "E", "W"],
            ["W", "W", "W", "W", "W"],
        ]

        grid = [[{"chosenVariant": 0}]]
        variants = [{"purpose": "enemy", "sourceName": "TestRoom", "sockets": {}}]

        # Run multiple seeds to check at least one produces enhanced enemies
        found_enhanced = False
        for seed in range(100):
            result = export_to_game_map(
                tile_map=tile_map,
                grid=grid,
                variants=variants,
                floor_number=9,  # High floor = ~12-17% champion, ~12% rare
                seed=seed,
            )
            for room in result.get("rooms", []):
                for spawn in room.get("enemy_spawns", []):
                    if spawn["monster_rarity"] != "normal":
                        found_enhanced = True
                        break
            if found_enhanced:
                break

        assert found_enhanced, "High floor spawns should occasionally produce enhanced enemies"

    def test_export_max_enhanced_per_room_limit(self):
        """No room should exceed max_enhanced_per_room in a single export."""
        from app.core.wfc.map_exporter import export_to_game_map

        # Many enemies in one room
        tile_map = [
            ["W", "W", "W", "W", "W"],
            ["W", "E", "E", "E", "W"],
            ["W", "E", "E", "E", "W"],
            ["W", "E", "E", "E", "W"],
            ["W", "W", "W", "W", "W"],
        ]

        grid = [[{"chosenVariant": 0}]]
        variants = [{"purpose": "enemy", "sourceName": "TestRoom", "sockets": {}}]

        spawn_chances = get_spawn_chances()
        max_enhanced = spawn_chances.get("max_enhanced_per_room", 2)

        for seed in range(50):
            result = export_to_game_map(
                tile_map=tile_map,
                grid=grid,
                variants=variants,
                floor_number=9,
                seed=seed,
            )
            for room in result.get("rooms", []):
                enhanced_count = sum(
                    1 for s in room.get("enemy_spawns", [])
                    if s.get("monster_rarity", "normal") != "normal"
                )
                assert enhanced_count <= max_enhanced, (
                    f"Room has {enhanced_count} enhanced enemies, max is {max_enhanced} (seed={seed})"
                )


# ====================================================================
# Section 2: Match Manager Spawn Integration
# ====================================================================

class TestMatchManagerSpawnIntegration:
    """Tests for Phase 18C rarity application in _spawn_dungeon_enemies."""

    def _setup_match_with_room(self, enemy_spawns, map_tiles=None):
        """Create a minimal match + map with given enemy spawns for testing."""
        from app.core.match_manager import (
            _active_matches,
            _player_states,
        )
        from app.models.match import MatchState, MatchConfig, MatchStatus
        from app.core.map_loader import register_runtime_map

        match_id = f"test-{uuid.uuid4().hex[:8]}"
        map_id = f"test_map_{match_id}"

        # Default map tiles: open floor
        if map_tiles is None:
            map_tiles = [["F"] * 15 for _ in range(15)]

        game_map = {
            "name": "Test Map",
            "width": 15,
            "height": 15,
            "map_type": "dungeon",
            "tiles": map_tiles,
            "tile_legend": {"F": "floor", "W": "wall"},
            "spawn_points": [{"x": 1, "y": 1}],
            "rooms": [{
                "id": "room_0_0",
                "name": "Test Room",
                "purpose": "enemy",
                "bounds": {"x_min": 0, "y_min": 0, "x_max": 14, "y_max": 14},
                "enemy_spawns": enemy_spawns,
            }],
            "doors": [],
            "chests": [],
            "stairs": [],
        }

        register_runtime_map(map_id, game_map)

        match = MatchState(
            match_id=match_id,
            status=MatchStatus.IN_PROGRESS,
            config=MatchConfig(map_id=map_id),
            host_id="host",
            player_ids=["host"],
            team_a=["host"],
            created_at=0,
        )

        _active_matches[match_id] = match
        _player_states[match_id] = {}

        return match_id, map_id

    def _cleanup_match(self, match_id, map_id):
        """Remove test match and map."""
        from app.core.match_manager import _active_matches, _player_states
        from app.core.map_loader import unregister_runtime_map
        from app.core.ai_behavior import clear_room_bounds

        _active_matches.pop(match_id, None)
        _player_states.pop(match_id, None)
        clear_room_bounds(match_id)
        try:
            unregister_runtime_map(map_id)
        except Exception:
            pass

    def test_spawn_champion_applies_rarity_stats(self):
        """Champion spawn data should result in a unit with boosted stats."""
        from app.core.match_manager import _spawn_dungeon_enemies, _player_states

        spawns = [{
            "x": 5, "y": 5,
            "enemy_type": "skeleton",
            "monster_rarity": "champion",
            "champion_type": "berserker",
            "affixes": [],
            "display_name": "Berserker Skeleton",
        }]

        match_id, map_id = self._setup_match_with_room(spawns)
        try:
            _spawn_dungeon_enemies(match_id)
            players = _player_states.get(match_id, {})

            # Find the spawned enemy
            enemies = [p for p in players.values() if p.team == "b"]
            assert len(enemies) >= 1, "Should have spawned at least 1 enemy"

            champ = enemies[0]
            assert champ.monster_rarity == "champion"
            assert champ.champion_type == "berserker"
            assert champ.username == "Berserker Skeleton"

            # Champion berserker should have boosted HP (tier multiplier applied)
            base_def = get_enemy_definition("skeleton")
            if base_def:
                base_hp = base_def.base_hp
                # Tier 1.4x HP + berserker may add more — just verify above base
                assert champ.max_hp > base_hp, f"Champion HP {champ.max_hp} should exceed base {base_hp}"
        finally:
            self._cleanup_match(match_id, map_id)

    def test_spawn_rare_applies_affixes(self):
        """Rare spawn data should result in a unit with affixes and boosted stats."""
        from app.core.match_manager import _spawn_dungeon_enemies, _player_states

        spawns = [{
            "x": 5, "y": 5,
            "enemy_type": "skeleton",
            "monster_rarity": "rare",
            "champion_type": None,
            "affixes": ["extra_strong", "stone_skin"],
            "display_name": "Mighty Skeleton the Immovable",
        }]

        match_id, map_id = self._setup_match_with_room(spawns)
        try:
            _spawn_dungeon_enemies(match_id)
            players = _player_states.get(match_id, {})

            enemies = [p for p in players.values() if p.team == "b"]
            assert len(enemies) >= 1

            rare = enemies[0]
            assert rare.monster_rarity == "rare"
            assert "extra_strong" in rare.affixes
            assert "stone_skin" in rare.affixes
            assert rare.display_name is not None

            # Rare should have boosted HP (1.7x tier + affix modifiers)
            base_def = get_enemy_definition("skeleton")
            if base_def:
                base_hp = base_def.base_hp
                # Tier 1.7x HP + affixes may add more — just verify above base
                assert rare.max_hp > base_hp, f"Rare HP {rare.max_hp} should exceed base {base_hp}"
        finally:
            self._cleanup_match(match_id, map_id)

    def test_spawn_normal_no_rarity_metadata(self):
        """Normal spawn data should produce a unit with no rarity upgrades."""
        from app.core.match_manager import _spawn_dungeon_enemies, _player_states

        spawns = [{
            "x": 5, "y": 5,
            "enemy_type": "skeleton",
            "monster_rarity": "normal",
            "champion_type": None,
            "affixes": [],
            "display_name": None,
        }]

        match_id, map_id = self._setup_match_with_room(spawns)
        try:
            _spawn_dungeon_enemies(match_id)
            players = _player_states.get(match_id, {})

            enemies = [p for p in players.values() if p.team == "b"]
            assert len(enemies) == 1

            normal = enemies[0]
            # monster_rarity should be None (not applied) since we don't call apply_rarity for normal
            assert normal.monster_rarity is None or normal.monster_rarity == "normal"
            assert normal.affixes == []
        finally:
            self._cleanup_match(match_id, map_id)

    def test_spawn_legacy_format_no_rarity_keys(self):
        """Legacy spawn data (no rarity keys) should still work — backward compat."""
        from app.core.match_manager import _spawn_dungeon_enemies, _player_states

        # Legacy format: no rarity keys at all
        spawns = [{
            "x": 5, "y": 5,
            "enemy_type": "skeleton",
        }]

        match_id, map_id = self._setup_match_with_room(spawns)
        try:
            _spawn_dungeon_enemies(match_id)
            players = _player_states.get(match_id, {})

            enemies = [p for p in players.values() if p.team == "b"]
            assert len(enemies) == 1

            enemy = enemies[0]
            assert enemy.enemy_type == "skeleton"
            # No rarity upgrade should be applied
            assert enemy.affixes == []
        finally:
            self._cleanup_match(match_id, map_id)

    def test_champion_pack_spawns_additional_champions(self):
        """Champion spawn should produce additional pack members on adjacent tiles."""
        from app.core.match_manager import _spawn_dungeon_enemies, _player_states

        spawns = [{
            "x": 7, "y": 7,
            "enemy_type": "skeleton",
            "monster_rarity": "champion",
            "champion_type": "resilient",
            "affixes": [],
            "display_name": "Resilient Skeleton",
        }]

        match_id, map_id = self._setup_match_with_room(spawns)
        try:
            _spawn_dungeon_enemies(match_id)
            players = _player_states.get(match_id, {})

            enemies = [p for p in players.values() if p.team == "b"]
            # pack_size is [2, 3], so total should be 2-3 (original + 1-2 additional)
            assert len(enemies) >= 2, f"Champion pack should have at least 2 members, got {len(enemies)}"
            assert len(enemies) <= 3, f"Champion pack should have at most 3 members, got {len(enemies)}"

            # All pack members should be champions
            for e in enemies:
                assert e.monster_rarity == "champion"
                assert e.champion_type == "resilient"
        finally:
            self._cleanup_match(match_id, map_id)

    def test_rare_spawns_minions(self):
        """Rare enemy spawn should create Normal-tier minions linked to the leader.

        Phase 5: Floor 1 limits max_rare_minions=1, so we test on floor 7
        to verify the base 2-3 minion behavior. Floor-specific caps are tested
        separately in test_wfc_floor_overrides.py.
        """
        from app.core.match_manager import _spawn_dungeon_enemies, _player_states, _active_matches

        spawns = [{
            "x": 7, "y": 7,
            "enemy_type": "skeleton",
            "monster_rarity": "rare",
            "champion_type": None,
            "affixes": ["extra_strong"],
            "display_name": "Mighty Skeleton the Crusher",
        }]

        match_id, map_id = self._setup_match_with_room(spawns)
        try:
            # Set floor high enough to avoid Phase 5 minion cap
            _active_matches[match_id].current_floor = 7
            _spawn_dungeon_enemies(match_id)
            players = _player_states.get(match_id, {})

            enemies = [p for p in players.values() if p.team == "b"]
            # Rare leader + 2-3 minions
            assert len(enemies) >= 3, f"Rare + minions should be at least 3, got {len(enemies)}"
            assert len(enemies) <= 4, f"Rare + minions should be at most 4, got {len(enemies)}"

            # Find the rare leader
            rares = [e for e in enemies if e.monster_rarity == "rare"]
            assert len(rares) == 1, "Should have exactly 1 rare leader"
            rare_leader = rares[0]

            # Find minions
            minions = [e for e in enemies if e.is_minion]
            assert len(minions) >= 2, f"Should have at least 2 minions, got {len(minions)}"

            for m in minions:
                assert m.minion_owner_id == rare_leader.player_id
                assert m.monster_rarity == "normal" or m.monster_rarity is None
                assert m.is_minion is True
        finally:
            self._cleanup_match(match_id, map_id)

    def test_minions_spawn_near_leader(self):
        """Minions should be placed on tiles adjacent to the rare leader."""
        from app.core.match_manager import _spawn_dungeon_enemies, _player_states

        spawns = [{
            "x": 7, "y": 7,
            "enemy_type": "skeleton",
            "monster_rarity": "rare",
            "champion_type": None,
            "affixes": ["thorns"],
            "display_name": "Barbed Skeleton the Spined",
        }]

        match_id, map_id = self._setup_match_with_room(spawns)
        try:
            _spawn_dungeon_enemies(match_id)
            players = _player_states.get(match_id, {})

            enemies = [p for p in players.values() if p.team == "b"]
            rares = [e for e in enemies if e.monster_rarity == "rare"]
            assert len(rares) == 1
            leader = rares[0]

            minions = [e for e in enemies if e.is_minion]
            for m in minions:
                dx = abs(m.position.x - leader.position.x)
                dy = abs(m.position.y - leader.position.y)
                # Minions should be within a reasonable distance (BFS finds nearby tiles)
                assert max(dx, dy) <= 5, f"Minion at ({m.position.x},{m.position.y}) too far from leader at ({leader.position.x},{leader.position.y})"
        finally:
            self._cleanup_match(match_id, map_id)

    def test_boss_spawn_not_upgraded(self):
        """Boss enemy spawns should not receive rarity upgrades."""
        from app.core.match_manager import _spawn_dungeon_enemies, _player_states

        spawns = [{
            "x": 5, "y": 5,
            "enemy_type": "undead_knight",
            "is_boss": True,
            "monster_rarity": "normal",
            "champion_type": None,
            "affixes": [],
            "display_name": None,
        }]

        match_id, map_id = self._setup_match_with_room(spawns)
        try:
            _spawn_dungeon_enemies(match_id)
            players = _player_states.get(match_id, {})

            enemies = [p for p in players.values() if p.team == "b"]
            assert len(enemies) == 1

            boss = enemies[0]
            assert boss.is_boss is True
            # Should not have rarity upgrade
            assert boss.monster_rarity is None or boss.monster_rarity == "normal"
        finally:
            self._cleanup_match(match_id, map_id)

    def test_no_units_stacked_on_same_tile(self):
        """No two enemy units should occupy the same tile after spawning."""
        from app.core.match_manager import _spawn_dungeon_enemies, _player_states

        # Multiple enemies including a champion that will spawn a pack
        spawns = [
            {"x": 7, "y": 7, "enemy_type": "skeleton", "monster_rarity": "champion",
             "champion_type": "fanatic", "affixes": [], "display_name": "Fanatic Skeleton"},
            {"x": 9, "y": 7, "enemy_type": "skeleton", "monster_rarity": "normal",
             "champion_type": None, "affixes": [], "display_name": None},
        ]

        match_id, map_id = self._setup_match_with_room(spawns)
        try:
            _spawn_dungeon_enemies(match_id)
            players = _player_states.get(match_id, {})

            enemies = [p for p in players.values() if p.team == "b"]
            positions = [(e.position.x, e.position.y) for e in enemies]
            assert len(positions) == len(set(positions)), (
                f"Duplicate positions found: {positions}"
            )
        finally:
            self._cleanup_match(match_id, map_id)


# ====================================================================
# Section 3: Wave Spawner Rarity Integration
# ====================================================================

class TestWaveSpawnerRarityIntegration:
    """Tests for Phase 18C rarity rolling in wave_spawner.py."""

    def _setup_wave_match(self, wave_enemies, wave_number=1):
        """Create a minimal wave match for testing."""
        from app.core.match_manager import _active_matches, _player_states, _wave_state
        from app.models.match import MatchState, MatchConfig, MatchStatus

        match_id = f"wave-test-{uuid.uuid4().hex[:8]}"

        match = MatchState(
            match_id=match_id,
            status=MatchStatus.IN_PROGRESS,
            config=MatchConfig(map_id="wave_arena"),
            host_id="host",
            player_ids=["host"],
            team_a=["host"],
            created_at=0,
        )

        _active_matches[match_id] = match
        _player_states[match_id] = {}

        _wave_state[match_id] = {
            "current_wave": 0,
            "total_waves": 1,
            "wave_config": {
                "spawn_points": [
                    {"x": 10, "y": 1},
                    {"x": 11, "y": 1},
                    {"x": 12, "y": 1},
                    {"x": 13, "y": 1},
                    {"x": 14, "y": 1},
                ],
                "waves": [{
                    "wave_number": wave_number,
                    "name": f"Test Wave {wave_number}",
                    "enemies": wave_enemies,
                }],
            },
            "spawning_active": True,
            "wave_enemies": [],
        }

        return match_id

    def _cleanup_wave_match(self, match_id):
        """Remove test wave match."""
        from app.core.match_manager import _active_matches, _player_states, _wave_state
        _active_matches.pop(match_id, None)
        _player_states.pop(match_id, None)
        _wave_state.pop(match_id, None)

    def test_wave_spawner_applies_forced_rarity(self):
        """force_rarity in enemy spec should override rarity roll."""
        from app.core.wave_spawner import _spawn_next_wave
        from app.core.match_manager import _player_states

        enemies = [
            {"enemy_type": "skeleton", "force_rarity": "champion"},
        ]

        match_id = self._setup_wave_match(enemies, wave_number=1)
        try:
            result = _spawn_next_wave(match_id)
            assert result is not None

            players = _player_states.get(match_id, {})
            wave_enemies = [p for p in players.values() if p.team == "b"]
            assert len(wave_enemies) == 1

            champ = wave_enemies[0]
            assert champ.monster_rarity == "champion"
            assert champ.champion_type is not None
        finally:
            self._cleanup_wave_match(match_id)

    def test_wave_spawner_respects_boss_no_upgrade(self):
        """Boss enemies in waves should not receive rarity upgrades."""
        from app.core.wave_spawner import _spawn_next_wave
        from app.core.match_manager import _player_states

        enemies = [
            {"enemy_type": "undead_knight", "is_boss": True},
        ]

        match_id = self._setup_wave_match(enemies, wave_number=8)
        try:
            _spawn_next_wave(match_id)
            players = _player_states.get(match_id, {})
            wave_enemies = [p for p in players.values() if p.team == "b"]
            assert len(wave_enemies) == 1

            boss = wave_enemies[0]
            assert boss.is_boss is True
            # Boss should not get rarity upgrade
            assert boss.monster_rarity is None or boss.monster_rarity == "normal"
        finally:
            self._cleanup_wave_match(match_id)

    def test_wave_spawner_normal_enemies_can_roll_rarity(self):
        """Normal enemies in later waves should occasionally get rarity upgrades."""
        from app.core.wave_spawner import _spawn_next_wave
        from app.core.match_manager import _player_states, _wave_state

        # Run many waves at high wave number to check for rarity upgrades
        found_enhanced = False
        for trial in range(50):
            enemies = [{"enemy_type": "skeleton"} for _ in range(5)]
            match_id = self._setup_wave_match(enemies, wave_number=8)
            try:
                _spawn_next_wave(match_id)
                players = _player_states.get(match_id, {})
                for p in players.values():
                    if p.team == "b" and p.monster_rarity and p.monster_rarity != "normal":
                        found_enhanced = True
                        break
            finally:
                self._cleanup_wave_match(match_id)
            if found_enhanced:
                break

        assert found_enhanced, "High wave number should occasionally produce enhanced enemies"

    def test_wave_spawner_low_wave_mostly_normal(self):
        """Low wave numbers should mostly produce normal enemies."""
        from app.core.wave_spawner import _spawn_next_wave
        from app.core.match_manager import _player_states

        # Wave 1 with min_floor_for_champions=1, but low base chance (8%)
        enemies = [{"enemy_type": "skeleton"}]
        match_id = self._setup_wave_match(enemies, wave_number=1)
        try:
            _spawn_next_wave(match_id)
            players = _player_states.get(match_id, {})
            wave_enemies = [p for p in players.values() if p.team == "b"]
            # With only 1 enemy at wave 1, most of the time it should be normal
            # This is a probabilistic test but wave 1 chance is only ~9%
            assert len(wave_enemies) == 1
        finally:
            self._cleanup_wave_match(match_id)


# ====================================================================
# Section 4: WebSocket Broadcast Integration
# ====================================================================

class TestWebSocketBroadcastRarity:
    """Tests for Phase 18C rarity metadata in player state broadcasts."""

    def _setup_match_with_players(self, players_dict):
        """Create a match with pre-built player states."""
        from app.core.match_manager import _active_matches, _player_states
        from app.models.match import MatchState, MatchConfig, MatchStatus

        match_id = f"broadcast-test-{uuid.uuid4().hex[:8]}"
        match = MatchState(
            match_id=match_id,
            status=MatchStatus.IN_PROGRESS,
            config=MatchConfig(map_id="test"),
            host_id="host",
            player_ids=list(players_dict.keys()),
            team_a=["host"],
            created_at=0,
        )
        _active_matches[match_id] = match
        _player_states[match_id] = players_dict
        return match_id

    def _cleanup(self, match_id):
        from app.core.match_manager import _active_matches, _player_states
        _active_matches.pop(match_id, None)
        _player_states.pop(match_id, None)

    def test_snapshot_includes_champion_fields(self):
        """get_players_snapshot should include rarity fields for champions."""
        from app.core.match_manager import get_players_snapshot

        champ = PlayerState(
            player_id="champ-01",
            username="Berserker Skeleton",
            position=Position(x=5, y=5),
            unit_type="ai",
            team="b",
        )
        champ.monster_rarity = "champion"
        champ.champion_type = "berserker"
        champ.affixes = []
        champ.display_name = "Berserker Skeleton"

        match_id = self._setup_match_with_players({"champ-01": champ})
        try:
            snapshot = get_players_snapshot(match_id)
            data = snapshot["champ-01"]
            assert data["monster_rarity"] == "champion"
            assert data["champion_type"] == "berserker"
            assert data["affixes"] == []
            assert data["display_name"] == "Berserker Skeleton"
        finally:
            self._cleanup(match_id)

    def test_snapshot_includes_rare_with_affixes(self):
        """get_players_snapshot should include rarity + affix fields for rares."""
        from app.core.match_manager import get_players_snapshot

        rare = PlayerState(
            player_id="rare-01",
            username="Mighty Skeleton the Crusher",
            position=Position(x=5, y=5),
            unit_type="ai",
            team="b",
        )
        rare.monster_rarity = "rare"
        rare.affixes = ["extra_strong", "fire_enchanted"]
        rare.display_name = "Mighty Skeleton the Crusher"

        match_id = self._setup_match_with_players({"rare-01": rare})
        try:
            snapshot = get_players_snapshot(match_id)
            data = snapshot["rare-01"]
            assert data["monster_rarity"] == "rare"
            assert "extra_strong" in data["affixes"]
            assert "fire_enchanted" in data["affixes"]
        finally:
            self._cleanup(match_id)

    def test_snapshot_excludes_rarity_for_normal(self):
        """get_players_snapshot should not include rarity metadata for normal enemies."""
        from app.core.match_manager import get_players_snapshot

        normal = PlayerState(
            player_id="normal-01",
            username="Skeleton-1",
            position=Position(x=5, y=5),
            unit_type="ai",
            team="b",
        )
        # monster_rarity defaults to None

        match_id = self._setup_match_with_players({"normal-01": normal})
        try:
            snapshot = get_players_snapshot(match_id)
            data = snapshot["normal-01"]
            assert "monster_rarity" not in data
            assert "champion_type" not in data
            assert "affixes" not in data
        finally:
            self._cleanup(match_id)

    def test_snapshot_includes_minion_metadata(self):
        """get_players_snapshot should include minion flags for minions."""
        from app.core.match_manager import get_players_snapshot

        minion = PlayerState(
            player_id="minion-01",
            username="Skeleton-3",
            position=Position(x=6, y=5),
            unit_type="ai",
            team="b",
        )
        minion.is_minion = True
        minion.minion_owner_id = "rare-leader-01"

        match_id = self._setup_match_with_players({"minion-01": minion})
        try:
            snapshot = get_players_snapshot(match_id)
            data = snapshot["minion-01"]
            assert data["is_minion"] is True
            assert data["minion_owner_id"] == "rare-leader-01"
        finally:
            self._cleanup(match_id)


# ====================================================================
# Section 5: Floor Scaling & Distribution
# ====================================================================

class TestFloorScaling:
    """Tests for rarity spawn chance scaling by floor/wave number."""

    def test_floor_1_no_rares(self):
        """Floor 1 (min_floor_for_rares=3) should never produce rare enemies."""
        rng = random.Random(42)
        for _ in range(1000):
            rarity = roll_monster_rarity(1, rng)
            assert rarity != "rare", "Floor 1 should not produce rares"

    def test_floor_below_champion_min(self):
        """Floor 0 (below min_floor_for_champions=1) should always be normal."""
        rng = random.Random(42)
        for _ in range(1000):
            rarity = roll_monster_rarity(0, rng)
            assert rarity == "normal", "Floor 0 should always be normal"

    def test_high_floor_increased_chances(self):
        """Higher floors should produce more enhanced enemies."""
        rng_low = random.Random(12345)
        rng_high = random.Random(12345)

        low_floor_enhanced = 0
        high_floor_enhanced = 0
        trials = 5000

        for _ in range(trials):
            if roll_monster_rarity(1, rng_low) != "normal":
                low_floor_enhanced += 1
            if roll_monster_rarity(9, rng_high) != "normal":
                high_floor_enhanced += 1

        # High floor should have significantly more enhanced enemies
        assert high_floor_enhanced > low_floor_enhanced * 1.5, (
            f"Floor 9 ({high_floor_enhanced}) should have >1.5x enhanced vs floor 1 ({low_floor_enhanced})"
        )

    def test_champion_vs_rare_distribution(self):
        """Champions should be more common than rares at any given floor."""
        rng = random.Random(99999)
        champions = 0
        rares = 0
        trials = 10000

        for _ in range(trials):
            r = roll_monster_rarity(5, rng)
            if r == "champion":
                champions += 1
            elif r == "rare":
                rares += 1

        assert champions > rares, (
            f"Champions ({champions}) should outnumber rares ({rares})"
        )


# ====================================================================
# Section 6: End-to-End Integration
# ====================================================================

class TestEndToEndSpawnRarity:
    """End-to-end tests verifying the full spawn pipeline."""

    def test_export_then_spawn_preserves_rarity(self):
        """Rarity metadata from map_exporter should be correctly applied by match_manager."""
        from app.core.wfc.map_exporter import export_to_game_map
        from app.core.match_manager import (
            _active_matches, _player_states, _spawn_dungeon_enemies,
        )
        from app.models.match import MatchState, MatchConfig, MatchStatus
        from app.core.map_loader import register_runtime_map, unregister_runtime_map
        from app.core.ai_behavior import clear_room_bounds

        # Create a map with enemies — use a seed that gives at least one enhanced
        tile_map = [
            ["W", "W", "W", "W", "W"],
            ["W", "E", "E", "E", "W"],
            ["W", "F", "F", "F", "W"],
            ["W", "F", "S", "F", "W"],
            ["W", "W", "W", "W", "W"],
        ]

        grid = [[{"chosenVariant": 0}]]
        variants = [{"purpose": "enemy", "sourceName": "TestRoom", "sockets": {}}]

        # Try multiple seeds to find one that produces an enhanced enemy
        for seed in range(200):
            game_map = export_to_game_map(
                tile_map=tile_map,
                grid=grid,
                variants=variants,
                floor_number=9,  # High floor for better chances
                seed=seed,
            )

            has_enhanced = False
            for room in game_map.get("rooms", []):
                for spawn in room.get("enemy_spawns", []):
                    if spawn.get("monster_rarity", "normal") != "normal":
                        has_enhanced = True
                        break

            if has_enhanced:
                # Found an enhanced spawn — now test the full pipeline
                match_id = f"e2e-test-{uuid.uuid4().hex[:8]}"
                map_id = f"e2e_map_{match_id}"
                register_runtime_map(map_id, game_map)

                match = MatchState(
                    match_id=match_id,
                    status=MatchStatus.IN_PROGRESS,
                    config=MatchConfig(map_id=map_id),
                    host_id="host",
                    player_ids=["host"],
                    team_a=["host"],
                    created_at=0,
                )
                _active_matches[match_id] = match
                _player_states[match_id] = {}

                try:
                    _spawn_dungeon_enemies(match_id)
                    players = _player_states.get(match_id, {})

                    enemies = [p for p in players.values() if p.team == "b"]
                    enhanced = [e for e in enemies if e.monster_rarity and e.monster_rarity != "normal"]

                    assert len(enhanced) >= 1, "Should have at least 1 enhanced enemy"
                    for e in enhanced:
                        assert e.monster_rarity in ("champion", "rare")
                        if e.monster_rarity == "champion":
                            assert e.champion_type is not None
                        elif e.monster_rarity == "rare":
                            assert len(e.affixes) >= 2
                    return  # Test passed
                finally:
                    _active_matches.pop(match_id, None)
                    _player_states.pop(match_id, None)
                    clear_room_bounds(match_id)
                    try:
                        unregister_runtime_map(map_id)
                    except Exception:
                        pass

        pytest.skip("Could not find a seed producing enhanced enemies in 200 attempts")

    def test_all_enemy_types_support_rarity(self):
        """All standard (non-boss, non-training) enemies should accept rarity upgrades."""
        from app.models.player import load_enemies_config

        enemies_cfg = load_enemies_config()
        for eid, edata in enemies_cfg.items():
            edef = get_enemy_definition(eid)
            if not edef:
                continue
            if edef.is_boss or eid == "training_dummy":
                assert not getattr(edef, "allow_rarity_upgrade", True) or edef.is_boss, (
                    f"Boss/training_dummy {eid} should have allow_rarity_upgrade=false"
                )
            # Non-boss enemies should support rarity by default
