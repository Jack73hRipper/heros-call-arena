"""
Tests for Phase 27 — PVPVE AI Team Cohesion.

Validates that AI hero teams in PVPVE mode stick together:
- First unit per team is the leader (is_team_leader=True)
- Non-leaders have hero_id + follow stance so they follow the leader
- _find_owner() returns the team leader for PVPVE AI followers
- When a leader dies, the next alive teammate is promoted
"""

from __future__ import annotations

import pytest

from app.models.match import MatchType, MatchConfig
from app.models.player import PlayerState, Position
from app.core import match_manager
from app.core.match_manager import (
    create_match,
    get_match_players,
    _spawn_pvpve_ai_teams,
)
from app.core.ai_stances import _find_owner


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
) -> tuple:
    """Create a PVPVE match with AI team configuration."""
    config = MatchConfig(
        match_type=MatchType.PVPVE,
        pvpve_team_count=team_count,
        pvpve_ai_team_count=ai_team_count,
        pvpve_ai_team_sizes=ai_team_sizes or [],
        pvpve_grid_size=4,
        pvpve_pve_density=0.5,
        pvpve_boss_enabled=True,
        pvpve_loot_density=0.5,
    )
    match, host = create_match("Host", config)
    return match, [host.player_id]


# ═══════════════════════════════════════════════════════════
# Leader Assignment
# ═══════════════════════════════════════════════════════════


class TestPVPVETeamLeaderAssignment:
    """Verify first unit per team is designated leader."""

    def setup_method(self):
        _clean_state()

    def test_first_unit_per_team_is_leader(self):
        """The first spawned unit per AI team has is_team_leader=True."""
        match, _ = _create_pvpve_match(
            team_count=4, ai_team_count=3, ai_team_sizes=[3, 3, 3]
        )
        _spawn_pvpve_ai_teams(match.match_id)
        players = get_match_players(match.match_id)

        for team_key in ["b", "c", "d"]:
            team_units = [
                players[pid] for pid in players
                if pid.startswith(f"pvpve-ai-{team_key}-")
            ]
            leaders = [u for u in team_units if u.is_team_leader]
            assert len(leaders) == 1, f"Team {team_key} should have exactly 1 leader"

    def test_non_leaders_have_follow_stance(self):
        """Non-leader units have hero_id set and ai_stance='follow'."""
        match, _ = _create_pvpve_match(
            team_count=2, ai_team_count=1, ai_team_sizes=[4]
        )
        _spawn_pvpve_ai_teams(match.match_id)
        players = get_match_players(match.match_id)

        team_b = [
            players[pid] for pid in players
            if pid.startswith("pvpve-ai-b-")
        ]
        followers = [u for u in team_b if not u.is_team_leader]
        assert len(followers) == 3  # 4 total - 1 leader

        for follower in followers:
            assert follower.hero_id is not None, "Follower should have hero_id"
            assert follower.ai_stance == "follow", "Follower should have follow stance"

    def test_leader_has_no_hero_id(self):
        """Leader has no hero_id so it uses aggressive AI behavior."""
        match, _ = _create_pvpve_match(
            team_count=2, ai_team_count=1, ai_team_sizes=[3]
        )
        _spawn_pvpve_ai_teams(match.match_id)
        players = get_match_players(match.match_id)

        team_b = [
            players[pid] for pid in players
            if pid.startswith("pvpve-ai-b-")
        ]
        leader = [u for u in team_b if u.is_team_leader][0]
        assert leader.hero_id is None, "Leader should not have hero_id"

    def test_single_unit_team_is_leader(self):
        """A team with only 1 unit has that unit as leader (no followers)."""
        match, _ = _create_pvpve_match(
            team_count=2, ai_team_count=1, ai_team_sizes=[1]
        )
        _spawn_pvpve_ai_teams(match.match_id)
        players = get_match_players(match.match_id)

        team_b = [
            players[pid] for pid in players
            if pid.startswith("pvpve-ai-b-")
        ]
        assert len(team_b) == 1
        assert team_b[0].is_team_leader is True


# ═══════════════════════════════════════════════════════════
# _find_owner — Team Leader Fallback
# ═══════════════════════════════════════════════════════════


class TestFindOwnerTeamLeaderFallback:
    """Verify _find_owner returns the team leader for PVPVE AI followers."""

    def test_find_owner_returns_team_leader(self):
        """_find_owner returns the alive team leader for a follower."""
        leader = PlayerState(
            player_id="pvpve-ai-b-leader",
            username="Leader",
            team="b",
            unit_type="ai",
            is_team_leader=True,
        )
        follower = PlayerState(
            player_id="pvpve-ai-b-f1",
            username="Follower",
            team="b",
            unit_type="ai",
            hero_id="pvpve-team-f1",
            ai_stance="follow",
        )
        all_units = {
            leader.player_id: leader,
            follower.player_id: follower,
        }

        owner = _find_owner(follower, all_units)
        assert owner is not None
        assert owner.player_id == leader.player_id

    def test_find_owner_prefers_human_over_leader(self):
        """If a human exists on the same team, prefer them over leader."""
        human = PlayerState(
            player_id="human-1",
            username="Human",
            team="a",
            unit_type="human",
        )
        leader = PlayerState(
            player_id="pvpve-ai-a-leader",
            username="Leader",
            team="a",
            unit_type="ai",
            is_team_leader=True,
        )
        follower = PlayerState(
            player_id="ai-f1",
            username="Follower",
            team="a",
            unit_type="ai",
            hero_id="generic-f1",
            ai_stance="follow",
        )
        all_units = {
            human.player_id: human,
            leader.player_id: leader,
            follower.player_id: follower,
        }

        owner = _find_owner(follower, all_units)
        assert owner is not None
        assert owner.player_id == human.player_id

    def test_find_owner_returns_none_when_leader_dead(self):
        """If the team leader is dead and no human exists, return None."""
        leader = PlayerState(
            player_id="pvpve-ai-b-leader",
            username="Leader",
            team="b",
            unit_type="ai",
            is_team_leader=True,
            is_alive=False,
        )
        follower = PlayerState(
            player_id="pvpve-ai-b-f1",
            username="Follower",
            team="b",
            unit_type="ai",
            hero_id="pvpve-team-f1",
            ai_stance="follow",
        )
        all_units = {
            leader.player_id: leader,
            follower.player_id: follower,
        }

        owner = _find_owner(follower, all_units)
        assert owner is None

    def test_find_owner_ignores_leader_on_other_team(self):
        """Team leader on a different team is not returned."""
        leader_c = PlayerState(
            player_id="pvpve-ai-c-leader",
            username="Leader C",
            team="c",
            unit_type="ai",
            is_team_leader=True,
        )
        follower_b = PlayerState(
            player_id="pvpve-ai-b-f1",
            username="Follower B",
            team="b",
            unit_type="ai",
            hero_id="pvpve-team-f1",
            ai_stance="follow",
        )
        all_units = {
            leader_c.player_id: leader_c,
            follower_b.player_id: follower_b,
        }

        owner = _find_owner(follower_b, all_units)
        assert owner is None  # No leader on team B


# ═══════════════════════════════════════════════════════════
# Leader Promotion on Death
# ═══════════════════════════════════════════════════════════


class TestLeaderPromotionOnDeath:
    """Verify that when a team leader dies, the next alive unit is promoted."""

    def test_leader_death_promotes_next_unit(self):
        """When a PVPVE team leader dies, the next alive teammate becomes leader."""
        from app.core.turn_phases.deaths_phase import _resolve_deaths
        from app.models.actions import ActionResult

        leader = PlayerState(
            player_id="pvpve-ai-b-leader",
            username="Leader",
            team="b",
            unit_type="ai",
            is_team_leader=True,
            is_alive=False,
            hp=0,
        )
        follower1 = PlayerState(
            player_id="pvpve-ai-b-f1",
            username="Follower1",
            team="b",
            unit_type="ai",
            hero_id="pvpve-team-f1",
            ai_stance="follow",
        )
        follower2 = PlayerState(
            player_id="pvpve-ai-b-f2",
            username="Follower2",
            team="b",
            unit_type="ai",
            hero_id="pvpve-team-f2",
            ai_stance="follow",
        )
        players = {
            leader.player_id: leader,
            follower1.player_id: follower1,
            follower2.player_id: follower2,
        }

        results: list[ActionResult] = []
        loot_drops: list[dict] = []

        _resolve_deaths(
            match_id="test-match",
            deaths=[leader.player_id],
            players=players,
            ground_items={},
            results=results,
            loot_drops=loot_drops,
        )

        # One of the followers should now be promoted to leader
        new_leaders = [u for u in players.values() if u.is_team_leader and u.is_alive]
        assert len(new_leaders) == 1
        assert new_leaders[0].player_id in [follower1.player_id, follower2.player_id]
        # The new leader should have hero_id cleared (aggressive AI)
        assert new_leaders[0].hero_id is None

    def test_leader_death_no_promotion_if_no_alive_teammates(self):
        """If all teammates are dead, no promotion occurs."""
        from app.core.turn_phases.deaths_phase import _resolve_deaths
        from app.models.actions import ActionResult

        leader = PlayerState(
            player_id="pvpve-ai-b-leader",
            username="Leader",
            team="b",
            unit_type="ai",
            is_team_leader=True,
            is_alive=False,
            hp=0,
        )
        follower = PlayerState(
            player_id="pvpve-ai-b-f1",
            username="Follower",
            team="b",
            unit_type="ai",
            is_alive=False,
            hp=0,
        )
        players = {
            leader.player_id: leader,
            follower.player_id: follower,
        }

        results: list[ActionResult] = []
        loot_drops: list[dict] = []

        _resolve_deaths(
            match_id="test-match",
            deaths=[leader.player_id],
            players=players,
            ground_items={},
            results=results,
            loot_drops=loot_drops,
        )

        # No alive units to promote — no new leaders
        alive_leaders = [u for u in players.values() if u.is_team_leader and u.is_alive]
        assert len(alive_leaders) == 0

    def test_non_leader_death_no_promotion(self):
        """When a non-leader dies, no promotion occurs."""
        from app.core.turn_phases.deaths_phase import _resolve_deaths
        from app.models.actions import ActionResult

        leader = PlayerState(
            player_id="pvpve-ai-b-leader",
            username="Leader",
            team="b",
            unit_type="ai",
            is_team_leader=True,
        )
        follower = PlayerState(
            player_id="pvpve-ai-b-f1",
            username="Follower",
            team="b",
            unit_type="ai",
            hero_id="pvpve-team-f1",
            ai_stance="follow",
            is_alive=False,
            hp=0,
        )
        players = {
            leader.player_id: leader,
            follower.player_id: follower,
        }

        results: list[ActionResult] = []
        loot_drops: list[dict] = []

        _resolve_deaths(
            match_id="test-match",
            deaths=[follower.player_id],
            players=players,
            ground_items={},
            results=results,
            loot_drops=loot_drops,
        )

        # Leader should still be the same — no promotion
        assert leader.is_team_leader is True
        assert follower.is_team_leader is False


# ═══════════════════════════════════════════════════════════
# Integration — Full Spawn Produces Cohesive Teams
# ═══════════════════════════════════════════════════════════


class TestPVPVETeamCohesionIntegration:
    """End-to-end: spawned AI teams have leader/follower structure."""

    def setup_method(self):
        _clean_state()

    def test_spawned_teams_have_one_leader_and_followers(self):
        """Each spawned AI team has exactly 1 leader, rest are followers."""
        match, _ = _create_pvpve_match(
            team_count=4, ai_team_count=3, ai_team_sizes=[4, 3, 5]
        )
        _spawn_pvpve_ai_teams(match.match_id)
        players = get_match_players(match.match_id)

        for team_key, expected_size in [("b", 4), ("c", 3), ("d", 5)]:
            team_units = [
                players[pid] for pid in players
                if pid.startswith(f"pvpve-ai-{team_key}-")
            ]
            assert len(team_units) == expected_size

            leaders = [u for u in team_units if u.is_team_leader]
            followers = [u for u in team_units if not u.is_team_leader]

            assert len(leaders) == 1
            assert len(followers) == expected_size - 1

            # Leader: no hero_id (aggressive AI)
            assert leaders[0].hero_id is None

            # Followers: hero_id + follow stance
            for f in followers:
                assert f.hero_id is not None
                assert f.ai_stance == "follow"

    def test_find_owner_works_for_spawned_teams(self):
        """_find_owner resolves the leader for spawned follower units."""
        match, _ = _create_pvpve_match(
            team_count=2, ai_team_count=1, ai_team_sizes=[3]
        )
        _spawn_pvpve_ai_teams(match.match_id)
        players = get_match_players(match.match_id)

        team_b = {
            pid: players[pid] for pid in players
            if pid.startswith("pvpve-ai-b-")
        }
        leader = [u for u in team_b.values() if u.is_team_leader][0]
        followers = [u for u in team_b.values() if not u.is_team_leader]

        for follower in followers:
            owner = _find_owner(follower, players)
            assert owner is not None
            assert owner.player_id == leader.player_id
