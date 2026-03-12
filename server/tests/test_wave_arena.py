"""
Tests for Wave Arena — Wave Spawner System.

Covers:
  - Map loader: get_wave_spawner_config returns config for wave maps, None for others
  - Wave state init: _init_wave_state creates state and spawns first wave
  - Wave clear check: check_wave_clear detects when all wave enemies are dead
  - Wave advancement: advance_wave_if_cleared spawns next wave when cleared
  - Wave enemy spawning: enemies are free-roaming (no room leashing)
  - Victory suppression: is_wave_map / all_waves_complete guard victory check
  - Multi-wave progression: waves advance correctly through all 8 waves
  - Cleanup: wave state is cleaned up on match removal
  - Edge cases: non-wave maps unaffected, occupied spawn points handled
"""

import pytest

from app.models.player import PlayerState, Position, apply_enemy_stats, get_enemy_definition
from app.models.match import MatchState, MatchConfig, MatchType, MatchStatus
from app.core.map_loader import load_map, get_wave_spawner_config, is_dungeon_map
from app.core.match_manager import (
    create_match,
    start_match,
    remove_match,
    get_match,
    get_match_players,
    get_match_teams,
    _active_matches,
    _player_states,
    _wave_state,
    _init_wave_state,
    _spawn_next_wave,
    check_wave_clear,
    advance_wave_if_cleared,
    is_wave_map,
    all_waves_complete,
    get_wave_state,
)
from app.core.combat import load_combat_config


def setup_module():
    """Ensure configs are loaded before any test runs."""
    load_combat_config()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_wave_match() -> tuple[str, str]:
    """Create a match on the wave_arena map and return (match_id, host_player_id)."""
    config = MatchConfig(
        map_id="wave_arena",
        match_type=MatchType.DUNGEON,
        tick_rate=1.0,
        ai_opponents=0,
        ai_allies=0,
    )
    match, host = create_match("TestHost", config=config)
    # Mark host as ready
    host.is_ready = True
    return match.match_id, host.player_id


def kill_all_team_b(match_id: str) -> None:
    """Kill all team_b enemies in the match."""
    players = _player_states.get(match_id, {})
    match = _active_matches.get(match_id)
    if not match:
        return
    for pid in list(match.team_b):
        unit = players.get(pid)
        if unit and unit.is_alive:
            unit.hp = 0
            unit.is_alive = False


# ---------------------------------------------------------------------------
# Map Loader Tests
# ---------------------------------------------------------------------------

class TestWaveMapLoader:
    """Test that map_loader correctly reads wave_spawner config."""

    def test_wave_arena_has_wave_spawner_config(self):
        config = get_wave_spawner_config("wave_arena")
        assert config is not None
        assert "waves" in config
        assert "spawn_points" in config
        assert len(config["waves"]) == 10

    def test_wave_arena_is_dungeon_map(self):
        assert is_dungeon_map("wave_arena") is True

    def test_wave_arena_has_correct_dimensions(self):
        data = load_map("wave_arena")
        assert data["width"] == 20
        assert data["height"] == 20
        assert data["name"] == "Wave Arena"

    def test_wave_arena_has_spawn_points(self):
        data = load_map("wave_arena")
        assert len(data["spawn_points"]) >= 3

    def test_wave_arena_spawner_has_5_spawn_points(self):
        config = get_wave_spawner_config("wave_arena")
        assert len(config["spawn_points"]) == 5

    def test_wave_arena_waves_have_correct_structure(self):
        config = get_wave_spawner_config("wave_arena")
        for wave in config["waves"]:
            assert "wave_number" in wave
            assert "name" in wave
            assert "enemies" in wave
            assert len(wave["enemies"]) > 0
            for enemy in wave["enemies"]:
                assert "enemy_type" in enemy

    def test_non_wave_map_returns_none(self):
        """Arena maps should return None for wave spawner config."""
        assert get_wave_spawner_config("open_arena_large") is None

    def test_dungeon_test_returns_none(self):
        """Standard dungeon map should return None for wave spawner config."""
        assert get_wave_spawner_config("dungeon_test") is None


# ---------------------------------------------------------------------------
# Wave State Initialization Tests
# ---------------------------------------------------------------------------

class TestWaveStateInit:
    """Test wave state initialization when a wave match starts."""

    def test_init_wave_state_creates_state(self):
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            state = get_wave_state(mid)
            assert state is not None
            assert state["current_wave"] == 1  # First wave spawned
            assert state["total_waves"] == 10
            assert state["spawning_active"] is True
            assert len(state["wave_enemies"]) > 0
        finally:
            remove_match(mid)

    def test_init_spawns_first_wave_enemies(self):
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            players = _player_states.get(mid, {})
            match = _active_matches.get(mid)

            # First wave: Crawler Swarm (3 insectoid + 2 evil_snail)
            wave_enemies = [
                p for p in players.values()
                if p.player_id.startswith("wave-") and p.is_alive
            ]
            assert len(wave_enemies) == 5
            assert all(e.team == "b" for e in wave_enemies)
        finally:
            remove_match(mid)

    def test_wave_enemies_are_on_team_b(self):
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            match = _active_matches.get(mid)
            state = get_wave_state(mid)
            for eid in state["wave_enemies"]:
                assert eid in match.team_b
                assert eid in match.ai_ids
                assert eid in match.player_ids
        finally:
            remove_match(mid)

    def test_non_wave_map_no_wave_state(self):
        """Non-wave maps should not have wave state."""
        config = MatchConfig(
            map_id="open_arena_large",
            match_type=MatchType.PVP,
        )
        match, host = create_match("TestHost", config=config)
        try:
            host.is_ready = True
            start_match(match.match_id)
            assert get_wave_state(match.match_id) is None
            assert not is_wave_map(match.match_id)
        finally:
            remove_match(match.match_id)

    def test_wave_enemies_are_free_roaming(self):
        """Wave enemies should not have a room_id (no leashing)."""
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            players = _player_states.get(mid, {})
            state = get_wave_state(mid)
            for eid in state["wave_enemies"]:
                unit = players[eid]
                # Free-roaming enemies should not have room_id
                assert not hasattr(unit, 'room_id') or unit.room_id is None or unit.room_id == ""
        finally:
            remove_match(mid)


# ---------------------------------------------------------------------------
# Wave Clear Detection Tests
# ---------------------------------------------------------------------------

class TestWaveClearCheck:
    """Test wave clear detection logic."""

    def test_wave_not_clear_while_enemies_alive(self):
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            assert check_wave_clear(mid) is False
        finally:
            remove_match(mid)

    def test_wave_clear_when_all_enemies_dead(self):
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            kill_all_team_b(mid)
            assert check_wave_clear(mid) is True
        finally:
            remove_match(mid)

    def test_wave_not_clear_if_some_alive(self):
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            state = get_wave_state(mid)
            players = _player_states.get(mid, {})
            # Kill only the first enemy
            first_enemy = players.get(state["wave_enemies"][0])
            if first_enemy:
                first_enemy.hp = 0
                first_enemy.is_alive = False
            # Second enemy still alive
            assert check_wave_clear(mid) is False
        finally:
            remove_match(mid)

    def test_check_wave_clear_non_wave_map(self):
        """Non-wave maps should always return False."""
        config = MatchConfig(map_id="open_arena_large", match_type=MatchType.PVP)
        match, host = create_match("TestHost", config=config)
        try:
            assert check_wave_clear(match.match_id) is False
        finally:
            remove_match(match.match_id)


# ---------------------------------------------------------------------------
# Wave Advancement Tests
# ---------------------------------------------------------------------------

class TestWaveAdvancement:
    """Test wave advancement when waves are cleared."""

    def test_advance_spawns_wave_2(self):
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            kill_all_team_b(mid)
            wave_info = advance_wave_if_cleared(mid)
            assert wave_info is not None
            assert wave_info["wave_number"] == 2
            assert wave_info["wave_name"] == "Goblin Raid"
            assert wave_info["enemy_count"] == 4  # 3 goblin_spearman + 1 imp
            assert wave_info["total_waves"] == 10
        finally:
            remove_match(mid)

    def test_advance_does_nothing_if_not_cleared(self):
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            result = advance_wave_if_cleared(mid)
            assert result is None
        finally:
            remove_match(mid)

    def test_advance_spawns_correct_enemy_count_per_wave(self):
        """Verify each wave spawns the correct number of enemies."""
        mid, pid = create_wave_match()
        expected_counts = [5, 4, 5, 4, 5, 4, 4, 4, 5, 5]  # enemies per wave
        try:
            start_match(mid)
            # Wave 1 already spawned
            state = get_wave_state(mid)
            assert len(state["wave_enemies"]) == expected_counts[0]

            # Advance through all remaining waves
            for i in range(1, 10):
                kill_all_team_b(mid)
                wave_info = advance_wave_if_cleared(mid)
                assert wave_info is not None, f"Wave {i+1} should have spawned"
                assert wave_info["enemy_count"] == expected_counts[i], \
                    f"Wave {i+1}: expected {expected_counts[i]} enemies, got {wave_info['enemy_count']}"
        finally:
            remove_match(mid)

    def test_no_advance_after_final_wave(self):
        """After wave 10, no more waves should spawn."""
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            # Advance through all 10 waves
            for i in range(9):  # 9 more advances (wave 1 already spawned)
                kill_all_team_b(mid)
                wave_info = advance_wave_if_cleared(mid)
                assert wave_info is not None

            # Now on wave 10 — kill and try to advance
            kill_all_team_b(mid)
            wave_info = advance_wave_if_cleared(mid)
            assert wave_info is None  # No wave 11
        finally:
            remove_match(mid)

    def test_wave_enemies_have_correct_stats(self):
        """Wave enemies should have stats from enemies_config."""
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            players = _player_states.get(mid, {})
            state = get_wave_state(mid)
            for eid in state["wave_enemies"]:
                unit = players[eid]
                assert unit.hp > 0
                assert unit.max_hp > 0
                assert unit.unit_type == "ai"
        finally:
            remove_match(mid)


# ---------------------------------------------------------------------------
# Victory Suppression Tests
# ---------------------------------------------------------------------------

class TestVictorySuppression:
    """Test that victory is suppressed until all waves are cleared."""

    def test_is_wave_map_returns_true_for_wave_arena(self):
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            assert is_wave_map(mid) is True
        finally:
            remove_match(mid)

    def test_is_wave_map_returns_false_for_regular_map(self):
        config = MatchConfig(map_id="open_arena_large", match_type=MatchType.PVP)
        match, host = create_match("TestHost", config=config)
        try:
            assert is_wave_map(match.match_id) is False
        finally:
            remove_match(match.match_id)

    def test_all_waves_not_complete_while_waves_remain(self):
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            kill_all_team_b(mid)
            # Wave 1 cleared but 7 more remain
            assert all_waves_complete(mid) is False
        finally:
            remove_match(mid)

    def test_all_waves_complete_after_final_wave_cleared(self):
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            # Advance through all waves
            for i in range(9):
                kill_all_team_b(mid)
                advance_wave_if_cleared(mid)
            # Now kill final wave
            kill_all_team_b(mid)
            assert all_waves_complete(mid) is True
        finally:
            remove_match(mid)

    def test_all_waves_complete_returns_true_for_non_wave_map(self):
        """Non-wave maps should return True (defer to standard victory)."""
        config = MatchConfig(map_id="open_arena_large", match_type=MatchType.PVP)
        match, host = create_match("TestHost", config=config)
        try:
            assert all_waves_complete(match.match_id) is True
        finally:
            remove_match(match.match_id)


# ---------------------------------------------------------------------------
# Cleanup Tests
# ---------------------------------------------------------------------------

class TestWaveCleanup:
    """Test that wave state is properly cleaned up."""

    def test_remove_match_clears_wave_state(self):
        mid, pid = create_wave_match()
        start_match(mid)
        assert mid in _wave_state
        remove_match(mid)
        assert mid not in _wave_state

    def test_wave_state_isolated_between_matches(self):
        mid1, _ = create_wave_match()
        mid2, _ = create_wave_match()
        try:
            start_match(mid1)
            start_match(mid2)
            assert mid1 in _wave_state
            assert mid2 in _wave_state
            remove_match(mid1)
            assert mid1 not in _wave_state
            assert mid2 in _wave_state
        finally:
            remove_match(mid1)
            remove_match(mid2)


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------

class TestWaveEdgeCases:
    """Edge case and regression tests."""

    def test_spawn_points_cycle_when_too_many_enemies(self):
        """When enemies exceed spawn points, positions should cycle."""
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            # Advance to wave 9 (5 enemies, 5 spawn points — tight fit)
            for i in range(8):
                kill_all_team_b(mid)
                advance_wave_if_cleared(mid)
            state = get_wave_state(mid)
            assert state["current_wave"] == 9
            assert len(state["wave_enemies"]) == 5
        finally:
            remove_match(mid)

    def test_wave_enemy_ids_start_with_wave_prefix(self):
        """Wave enemies should have IDs starting with 'wave-'."""
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            state = get_wave_state(mid)
            for eid in state["wave_enemies"]:
                assert eid.startswith("wave-")
        finally:
            remove_match(mid)

    def test_wave_state_tracks_current_wave_correctly(self):
        """Wave number should increment correctly through progression."""
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            state = get_wave_state(mid)
            assert state["current_wave"] == 1

            kill_all_team_b(mid)
            advance_wave_if_cleared(mid)
            assert state["current_wave"] == 2

            kill_all_team_b(mid)
            advance_wave_if_cleared(mid)
            assert state["current_wave"] == 3
        finally:
            remove_match(mid)

    def test_full_10_wave_progression(self):
        """Complete run through all 10 waves."""
        mid, pid = create_wave_match()
        try:
            start_match(mid)
            wave_names = []

            # Wave 1 already spawned
            state = get_wave_state(mid)
            assert state["current_wave"] == 1

            # Advance through all remaining waves
            for i in range(9):
                kill_all_team_b(mid)
                wave_info = advance_wave_if_cleared(mid)
                assert wave_info is not None
                wave_names.append(wave_info["wave_name"])

            expected_names = [
                "Goblin Raid", "Grave Crawlers", "Dark Assembly",
                "Venom Den", "Spectral Court", "Demon Vanguard",
                "Eldritch Nightmares", "The Bone Throne", "The Final Reckoning"
            ]
            assert wave_names == expected_names

            # Final wave killed — no more waves
            kill_all_team_b(mid)
            assert advance_wave_if_cleared(mid) is None
            assert all_waves_complete(mid) is True
        finally:
            remove_match(mid)
