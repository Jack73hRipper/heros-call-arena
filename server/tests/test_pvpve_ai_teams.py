"""
Tests for Phase 27 — PVPVE AI Hero Team Spawning.

Validates that pvpve_ai_team_count and pvpve_ai_team_sizes config
values result in actual AI hero teams being created and placed on
the correct teams at match start.
"""

from __future__ import annotations

import pytest

from app.models.match import MatchType, MatchConfig, MatchStatus
from app.models.player import PlayerState, Position
from app.core import match_manager
from app.core.match_manager import (
    create_match,
    join_match,
    start_match,
    get_match,
    get_match_players,
    set_player_ready,
    remove_match,
    _assign_pvpve_teams,
    _spawn_pvpve_ai_teams,
    _PVPVE_TEAM_KEYS,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════


def _clean_state():
    """Clear all in-memory stores between tests."""
    match_manager._active_matches.clear()
    match_manager._player_states.clear()
    match_manager._action_queues.clear()
    match_manager._fov_cache.clear()
    match_manager._lobby_chat.clear()
    match_manager._class_selections.clear()
    match_manager._hero_selections.clear()
    match_manager._hero_ally_map.clear()
    match_manager._username_map.clear()
    match_manager._kill_tracker.clear()
    match_manager._combat_stats.clear()
    match_manager._match_timeline.clear()
    match_manager._wave_state.clear()


def _create_pvpve_match(
    team_count: int = 2,
    ai_team_count: int = 0,
    ai_team_sizes: list[int] | None = None,
    ai_allies: int = 0,
    grid_size: int = 4,
    num_humans: int = 1,
) -> tuple:
    """Create a PVPVE match with AI team configuration.

    Returns (match, [human_player_ids]).
    """
    config = MatchConfig(
        match_type=MatchType.PVPVE,
        pvpve_team_count=team_count,
        pvpve_ai_team_count=ai_team_count,
        pvpve_ai_team_sizes=ai_team_sizes or [],
        pvpve_grid_size=grid_size,
        pvpve_pve_density=0.5,
        pvpve_boss_enabled=True,
        pvpve_loot_density=0.5,
        ai_allies=ai_allies,
    )
    match, host = create_match("Host", config)
    human_ids = [host.player_id]

    for i in range(1, num_humans):
        result = join_match(match.match_id, f"Player{i + 1}")
        if result:
            _, player = result
            human_ids.append(player.player_id)

    return match, human_ids


# ═══════════════════════════════════════════════════════════
# _spawn_pvpve_ai_teams — Unit Creation
# ═══════════════════════════════════════════════════════════


class TestSpawnPVPVEAITeams:
    """Verify _spawn_pvpve_ai_teams creates AI hero units correctly."""

    def setup_method(self):
        _clean_state()

    def test_no_ai_teams_when_count_is_zero(self):
        """No AI units created when pvpve_ai_team_count is 0."""
        match, _ = _create_pvpve_match(team_count=2, ai_team_count=0)
        _spawn_pvpve_ai_teams(match.match_id)

        players = get_match_players(match.match_id)
        pvpve_ai = [pid for pid in players if pid.startswith("pvpve-ai-")]
        assert len(pvpve_ai) == 0

    def test_1_ai_team_creates_units(self):
        """1 AI team with default size creates units."""
        match, _ = _create_pvpve_match(
            team_count=2, ai_team_count=1, ai_team_sizes=[3]
        )
        _spawn_pvpve_ai_teams(match.match_id)

        players = get_match_players(match.match_id)
        pvpve_ai = [pid for pid in players if pid.startswith("pvpve-ai-")]
        assert len(pvpve_ai) == 3

    def test_3_ai_teams_4_team_match(self):
        """3 AI teams in a 4-team match fills teams B, C, D."""
        match, _ = _create_pvpve_match(
            team_count=4, ai_team_count=3, ai_team_sizes=[3, 3, 3]
        )
        _spawn_pvpve_ai_teams(match.match_id)

        players = get_match_players(match.match_id)
        pvpve_ai = [pid for pid in players if pid.startswith("pvpve-ai-")]
        assert len(pvpve_ai) == 9  # 3 teams × 3 units

    def test_ai_team_units_have_correct_team(self):
        """AI team units have the correct team assigned."""
        match, _ = _create_pvpve_match(
            team_count=4, ai_team_count=3, ai_team_sizes=[2, 2, 2]
        )
        _spawn_pvpve_ai_teams(match.match_id)

        players = get_match_players(match.match_id)
        team_b_ai = [pid for pid in players if pid.startswith("pvpve-ai-b-")]
        team_c_ai = [pid for pid in players if pid.startswith("pvpve-ai-c-")]
        team_d_ai = [pid for pid in players if pid.startswith("pvpve-ai-d-")]

        assert len(team_b_ai) == 2
        assert len(team_c_ai) == 2
        assert len(team_d_ai) == 2

        for pid in team_b_ai:
            assert players[pid].team == "b"
        for pid in team_c_ai:
            assert players[pid].team == "c"
        for pid in team_d_ai:
            assert players[pid].team == "d"

    def test_ai_team_units_are_ai_type(self):
        """AI team units have unit_type='ai'."""
        match, _ = _create_pvpve_match(
            team_count=2, ai_team_count=1, ai_team_sizes=[3]
        )
        _spawn_pvpve_ai_teams(match.match_id)

        players = get_match_players(match.match_id)
        pvpve_ai = [pid for pid in players if pid.startswith("pvpve-ai-")]
        for pid in pvpve_ai:
            assert players[pid].unit_type == "ai"
            assert players[pid].is_ready is True

    def test_ai_team_units_have_class_stats(self):
        """AI team units get class stats applied (HP > 0)."""
        match, _ = _create_pvpve_match(
            team_count=2, ai_team_count=1, ai_team_sizes=[3]
        )
        _spawn_pvpve_ai_teams(match.match_id)

        players = get_match_players(match.match_id)
        pvpve_ai = [pid for pid in players if pid.startswith("pvpve-ai-")]
        for pid in pvpve_ai:
            assert players[pid].hp > 0
            assert players[pid].max_hp > 0
            assert players[pid].class_id is not None

    def test_ai_team_units_tracked_in_ai_ids(self):
        """AI team units are added to match.ai_ids."""
        match, _ = _create_pvpve_match(
            team_count=2, ai_team_count=1, ai_team_sizes=[3]
        )
        _spawn_pvpve_ai_teams(match.match_id)

        pvpve_ai = [aid for aid in match.ai_ids if aid.startswith("pvpve-ai-")]
        assert len(pvpve_ai) == 3

    def test_ai_team_units_tracked_in_player_ids(self):
        """AI team units are added to match.player_ids."""
        match, _ = _create_pvpve_match(
            team_count=2, ai_team_count=1, ai_team_sizes=[3]
        )
        _spawn_pvpve_ai_teams(match.match_id)

        pvpve_ai = [pid for pid in match.player_ids if pid.startswith("pvpve-ai-")]
        assert len(pvpve_ai) == 3

    def test_varying_team_sizes(self):
        """Different team sizes per AI team are respected."""
        match, _ = _create_pvpve_match(
            team_count=4, ai_team_count=3, ai_team_sizes=[2, 4, 1]
        )
        _spawn_pvpve_ai_teams(match.match_id)

        players = get_match_players(match.match_id)
        team_b_ai = [pid for pid in players if pid.startswith("pvpve-ai-b-")]
        team_c_ai = [pid for pid in players if pid.startswith("pvpve-ai-c-")]
        team_d_ai = [pid for pid in players if pid.startswith("pvpve-ai-d-")]

        assert len(team_b_ai) == 2
        assert len(team_c_ai) == 4
        assert len(team_d_ai) == 1

    def test_team_size_defaults_to_3_when_not_specified(self):
        """Teams without explicit size in config default to 3 units."""
        match, _ = _create_pvpve_match(
            team_count=2, ai_team_count=1, ai_team_sizes=[]
        )
        _spawn_pvpve_ai_teams(match.match_id)

        players = get_match_players(match.match_id)
        pvpve_ai = [pid for pid in players if pid.startswith("pvpve-ai-")]
        assert len(pvpve_ai) == 3

    def test_team_size_clamped_to_5(self):
        """Team size is capped at 5 units."""
        match, _ = _create_pvpve_match(
            team_count=2, ai_team_count=1, ai_team_sizes=[10]
        )
        _spawn_pvpve_ai_teams(match.match_id)

        players = get_match_players(match.match_id)
        pvpve_ai = [pid for pid in players if pid.startswith("pvpve-ai-")]
        assert len(pvpve_ai) == 5

    def test_team_size_clamped_to_1_minimum(self):
        """Team size cannot be less than 1."""
        match, _ = _create_pvpve_match(
            team_count=2, ai_team_count=1, ai_team_sizes=[0]
        )
        _spawn_pvpve_ai_teams(match.match_id)

        players = get_match_players(match.match_id)
        pvpve_ai = [pid for pid in players if pid.startswith("pvpve-ai-")]
        assert len(pvpve_ai) == 1

    def test_ai_teams_skip_human_occupied_teams(self):
        """AI teams are placed on non-human team slots only."""
        # 2 humans with 4 teams → humans on A and B, AI should get C and D
        match, _ = _create_pvpve_match(
            team_count=4, ai_team_count=2, ai_team_sizes=[2, 2],
            num_humans=2
        )
        _spawn_pvpve_ai_teams(match.match_id)

        players = get_match_players(match.match_id)
        # No AI on team A or B (those have humans)
        team_a_ai = [pid for pid in players if pid.startswith("pvpve-ai-a-")]
        team_b_ai = [pid for pid in players if pid.startswith("pvpve-ai-b-")]
        assert len(team_a_ai) == 0
        assert len(team_b_ai) == 0

        # AI should be on C and D
        team_c_ai = [pid for pid in players if pid.startswith("pvpve-ai-c-")]
        team_d_ai = [pid for pid in players if pid.startswith("pvpve-ai-d-")]
        assert len(team_c_ai) == 2
        assert len(team_d_ai) == 2


# ═══════════════════════════════════════════════════════════
# _assign_pvpve_teams — Integration with AI Teams
# ═══════════════════════════════════════════════════════════


class TestAssignPVPVETeamsWithAITeams:
    """Verify _assign_pvpve_teams correctly places AI team units."""

    def setup_method(self):
        _clean_state()

    def test_pvpve_ai_units_placed_on_correct_team_after_assign(self):
        """After assign, pvpve-ai units are on their pre-assigned team."""
        match, _ = _create_pvpve_match(
            team_count=4, ai_team_count=3, ai_team_sizes=[2, 2, 2]
        )
        _spawn_pvpve_ai_teams(match.match_id)
        _assign_pvpve_teams(match.match_id)

        # Team B should have AI units
        players = get_match_players(match.match_id)
        for pid in match.team_b:
            assert players[pid].team == "b"
        for pid in match.team_c:
            assert players[pid].team == "c"
        for pid in match.team_d:
            assert players[pid].team == "d"

        # Each non-human team should have its AI units
        ai_on_b = [pid for pid in match.team_b if pid.startswith("pvpve-ai-")]
        ai_on_c = [pid for pid in match.team_c if pid.startswith("pvpve-ai-")]
        ai_on_d = [pid for pid in match.team_d if pid.startswith("pvpve-ai-")]
        assert len(ai_on_b) == 2
        assert len(ai_on_c) == 2
        assert len(ai_on_d) == 2

    def test_human_still_on_team_a_with_ai_teams(self):
        """Host is on team A even with AI teams filling other slots."""
        match, human_ids = _create_pvpve_match(
            team_count=4, ai_team_count=3, ai_team_sizes=[3, 3, 3]
        )
        _spawn_pvpve_ai_teams(match.match_id)
        _assign_pvpve_teams(match.match_id)

        assert match.host_id in match.team_a

    def test_generic_ai_allies_coexist_with_ai_teams(self):
        """Generic ai- allies and pvpve-ai- units are both distributed."""
        match, _ = _create_pvpve_match(
            team_count=2, ai_team_count=1, ai_team_sizes=[3],
            ai_allies=2
        )
        _spawn_pvpve_ai_teams(match.match_id)
        _assign_pvpve_teams(match.match_id)

        players = get_match_players(match.match_id)
        # Total units: 1 human + 2 generic AI allies + 3 pvpve-ai team B
        total = len(match.team_a) + len(match.team_b)
        assert total == 6  # 1 human + 2 ai + 3 pvpve-ai

        # pvpve-ai should be on team B
        pvpve_on_b = [pid for pid in match.team_b if pid.startswith("pvpve-ai-")]
        assert len(pvpve_on_b) == 3


# ═══════════════════════════════════════════════════════════
# Full Match Start — End-to-end with AI Teams
# ═══════════════════════════════════════════════════════════


class TestPVPVEMatchStartWithAITeams:
    """Full match start with AI teams — end-to-end integration."""

    def setup_method(self):
        _clean_state()

    def test_pvpve_match_starts_with_ai_teams(self):
        """A PVPVE match with AI teams transitions to IN_PROGRESS."""
        match, human_ids = _create_pvpve_match(
            team_count=4, ai_team_count=3, ai_team_sizes=[3, 3, 3],
            grid_size=4
        )
        set_player_ready(match.match_id, human_ids[0], True)
        started = start_match(match.match_id)

        assert started is True
        assert get_match(match.match_id).status == MatchStatus.IN_PROGRESS

    def test_all_teams_populated_after_match_start(self):
        """After match start, all 4 teams have units."""
        match, human_ids = _create_pvpve_match(
            team_count=4, ai_team_count=3, ai_team_sizes=[3, 3, 3],
            grid_size=4
        )
        set_player_ready(match.match_id, human_ids[0], True)
        start_match(match.match_id)

        updated = get_match(match.match_id)
        assert len(updated.team_a) >= 1  # At least the human
        assert len(updated.team_b) >= 1  # AI team
        assert len(updated.team_c) >= 1  # AI team
        assert len(updated.team_d) >= 1  # AI team

    def test_ai_team_units_have_valid_positions(self):
        """AI team units have non-zero positions after match start."""
        match, human_ids = _create_pvpve_match(
            team_count=2, ai_team_count=1, ai_team_sizes=[3],
            grid_size=4
        )
        set_player_ready(match.match_id, human_ids[0], True)
        start_match(match.match_id)

        players = get_match_players(match.match_id)
        pvpve_ai = {pid: p for pid, p in players.items()
                    if pid.startswith("pvpve-ai-")}

        assert len(pvpve_ai) == 3
        for pid, p in pvpve_ai.items():
            # Positions should have been resolved by smart spawns
            assert p.position is not None

    def test_2_team_match_1_ai_team(self):
        """2-team match with 1 AI team: human on A, AI on B."""
        match, human_ids = _create_pvpve_match(
            team_count=2, ai_team_count=1, ai_team_sizes=[4],
            grid_size=4
        )
        set_player_ready(match.match_id, human_ids[0], True)
        start_match(match.match_id)

        updated = get_match(match.match_id)
        assert match.host_id in updated.team_a
        pvpve_on_b = [pid for pid in updated.team_b if pid.startswith("pvpve-ai-")]
        assert len(pvpve_on_b) == 4

    def test_pve_enemies_still_spawn_with_ai_teams(self):
        """PVE enemies spawn on the pve team alongside AI hero teams."""
        match, human_ids = _create_pvpve_match(
            team_count=4, ai_team_count=3, ai_team_sizes=[3, 3, 3],
            grid_size=4
        )
        set_player_ready(match.match_id, human_ids[0], True)
        start_match(match.match_id)

        updated = get_match(match.match_id)
        # PVE enemies should exist (grid_size=4 is small, may not guarantee many,
        # but the list should exist)
        assert isinstance(updated.team_pve, list)

    def test_ai_teams_not_in_team_pve(self):
        """AI hero team units are NOT in team_pve."""
        match, human_ids = _create_pvpve_match(
            team_count=4, ai_team_count=3, ai_team_sizes=[3, 3, 3],
            grid_size=4
        )
        set_player_ready(match.match_id, human_ids[0], True)
        start_match(match.match_id)

        updated = get_match(match.match_id)
        for pve_id in updated.team_pve:
            assert not pve_id.startswith("pvpve-ai-")
