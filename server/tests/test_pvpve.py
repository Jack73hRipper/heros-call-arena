"""
Tests for Phase 27 — PVPVE Dungeon Map.

Phase A: Data model & match type validation.
Phase D: Victory conditions & PVE team.
"""

from __future__ import annotations

import pytest

from app.models.match import MatchType, MatchConfig, MatchState
from app.models.player import PlayerState, Position
from app.core.combat import check_team_victory, are_allies


# ═══════════════════════════════════════════════════════════
# Phase A — Data Model & Match Type
# ═══════════════════════════════════════════════════════════


class TestMatchTypePVPVE:
    """A-1: MatchType.PVPVE enum value."""

    def test_pvpve_enum_exists(self):
        assert MatchType.PVPVE == "pvpve"

    def test_pvpve_serializes_to_string(self):
        assert MatchType.PVPVE.value == "pvpve"

    def test_pvpve_deserializes_from_string(self):
        assert MatchType("pvpve") == MatchType.PVPVE

    def test_pvpve_in_match_config(self):
        cfg = MatchConfig(match_type=MatchType.PVPVE)
        assert cfg.match_type == MatchType.PVPVE

    def test_pvpve_round_trip_json(self):
        cfg = MatchConfig(match_type=MatchType.PVPVE)
        data = cfg.model_dump()
        restored = MatchConfig(**data)
        assert restored.match_type == MatchType.PVPVE


class TestMatchConfigPVPVEFields:
    """A-2: PVPVE-specific MatchConfig fields."""

    def test_default_team_count(self):
        cfg = MatchConfig()
        assert cfg.pvpve_team_count == 2

    def test_default_pve_density(self):
        cfg = MatchConfig()
        assert cfg.pvpve_pve_density == 0.5

    def test_default_boss_enabled(self):
        cfg = MatchConfig()
        assert cfg.pvpve_boss_enabled is True

    def test_default_loot_density(self):
        cfg = MatchConfig()
        assert cfg.pvpve_loot_density == 0.5

    def test_default_grid_size(self):
        cfg = MatchConfig()
        assert cfg.pvpve_grid_size == 8

    def test_custom_pvpve_fields(self):
        cfg = MatchConfig(
            match_type=MatchType.PVPVE,
            pvpve_team_count=4,
            pvpve_pve_density=0.8,
            pvpve_boss_enabled=False,
            pvpve_loot_density=0.3,
            pvpve_grid_size=10,
        )
        assert cfg.pvpve_team_count == 4
        assert cfg.pvpve_pve_density == 0.8
        assert cfg.pvpve_boss_enabled is False
        assert cfg.pvpve_loot_density == 0.3
        assert cfg.pvpve_grid_size == 10

    def test_pvpve_config_round_trip(self):
        """All PVPVE fields survive JSON serialization round-trip."""
        cfg = MatchConfig(
            match_type=MatchType.PVPVE,
            pvpve_team_count=3,
            pvpve_pve_density=0.7,
            pvpve_boss_enabled=False,
            pvpve_loot_density=0.9,
            pvpve_grid_size=6,
        )
        data = cfg.model_dump()
        restored = MatchConfig(**data)
        assert restored.pvpve_team_count == 3
        assert restored.pvpve_pve_density == 0.7
        assert restored.pvpve_boss_enabled is False
        assert restored.pvpve_loot_density == 0.9
        assert restored.pvpve_grid_size == 6
        assert restored.match_type == MatchType.PVPVE


class TestMatchStatePVPVE:
    """A-3/A-4: MatchState team_pve field."""

    def test_team_pve_defaults_empty(self):
        state = MatchState(match_id="test1")
        assert state.team_pve == []

    def test_team_pve_stores_ids(self):
        state = MatchState(match_id="test2", team_pve=["pve_1", "pve_2", "pve_3"])
        assert len(state.team_pve) == 3
        assert "pve_1" in state.team_pve

    def test_team_pve_round_trip(self):
        state = MatchState(match_id="test3", team_pve=["pve_boss", "pve_guard"])
        data = state.model_dump()
        restored = MatchState(**data)
        assert restored.team_pve == ["pve_boss", "pve_guard"]

    def test_pvpve_full_state(self):
        """A PVPVE match state with all teams populated."""
        state = MatchState(
            match_id="pvpve_match_1",
            config=MatchConfig(match_type=MatchType.PVPVE, pvpve_team_count=4),
            team_a=["player1", "ally1"],
            team_b=["player2", "ally2"],
            team_c=["player3", "ally3"],
            team_d=["player4", "ally4"],
            team_pve=["pve_1", "pve_2", "pve_boss"],
        )
        assert state.config.match_type == MatchType.PVPVE
        assert len(state.team_a) == 2
        assert len(state.team_b) == 2
        assert len(state.team_c) == 2
        assert len(state.team_d) == 2
        assert len(state.team_pve) == 3
        # PVE IDs should not be in any player team
        all_player_ids = state.team_a + state.team_b + state.team_c + state.team_d
        for pve_id in state.team_pve:
            assert pve_id not in all_player_ids


# ═══════════════════════════════════════════════════════════
# Phase D — Victory Conditions & PVE Team
# ═══════════════════════════════════════════════════════════

def _make_player(pid: str, team: str, alive: bool = True) -> PlayerState:
    """Helper to create a minimal PlayerState for victory tests."""
    p = PlayerState(
        player_id=pid,
        username=pid,
        position=Position(x=0, y=0),
        team=team,
    )
    p.is_alive = alive
    return p


class TestCheckTeamVictoryExcludedTeams:
    """D-1: check_team_victory with excluded_teams parameter."""

    def test_pve_alive_does_not_block_victory(self):
        """Victory triggers when 1 player team survives, even if PVE alive."""
        players = [
            _make_player("p1", "a", alive=True),
            _make_player("p2", "b", alive=False),
            _make_player("pve1", "pve", alive=True),
            _make_player("pve2", "pve", alive=True),
        ]
        result = check_team_victory(
            players,
            team_a=["p1"],
            team_b=["p2"],
            excluded_teams={"pve"},
        )
        assert result == "team_a"

    def test_pve_dead_does_not_trigger_draw(self):
        """PVE deaths don't factor into draw detection."""
        players = [
            _make_player("p1", "a", alive=True),
            _make_player("p2", "b", alive=True),
            _make_player("pve1", "pve", alive=False),
        ]
        result = check_team_victory(
            players,
            team_a=["p1"],
            team_b=["p2"],
            excluded_teams={"pve"},
        )
        assert result is None  # Match continues

    def test_all_player_teams_dead_is_draw(self):
        """All player teams eliminated → draw, even if PVE alive."""
        players = [
            _make_player("p1", "a", alive=False),
            _make_player("p2", "b", alive=False),
            _make_player("pve1", "pve", alive=True),
        ]
        result = check_team_victory(
            players,
            team_a=["p1"],
            team_b=["p2"],
            excluded_teams={"pve"},
        )
        assert result == "draw"

    def test_four_teams_one_survives(self):
        """4-team PVPVE: team_c survives, others eliminated."""
        players = [
            _make_player("p1", "a", alive=False),
            _make_player("p2", "b", alive=False),
            _make_player("p3", "c", alive=True),
            _make_player("p4", "d", alive=False),
            _make_player("pve1", "pve", alive=True),
            _make_player("pve2", "pve", alive=True),
        ]
        result = check_team_victory(
            players,
            team_a=["p1"],
            team_b=["p2"],
            team_c=["p3"],
            team_d=["p4"],
            excluded_teams={"pve"},
        )
        assert result == "team_c"

    def test_match_continues_two_teams_alive(self):
        """Match continues when 2+ player teams have living members."""
        players = [
            _make_player("p1", "a", alive=True),
            _make_player("p2", "b", alive=True),
            _make_player("pve1", "pve", alive=True),
        ]
        result = check_team_victory(
            players,
            team_a=["p1"],
            team_b=["p2"],
            excluded_teams={"pve"},
        )
        assert result is None

    def test_no_excluded_teams_backward_compat(self):
        """Without excluded_teams, behavior is unchanged (backward compat)."""
        players = [
            _make_player("p1", "a", alive=True),
            _make_player("p2", "b", alive=False),
        ]
        result = check_team_victory(
            players,
            team_a=["p1"],
            team_b=["p2"],
        )
        assert result == "team_a"

    def test_pve_not_in_team_lists_already_excluded(self):
        """PVE enemies not in any team list are inherently excluded."""
        players = [
            _make_player("p1", "a", alive=True),
            _make_player("p2", "b", alive=False),
            _make_player("pve1", "pve", alive=True),
        ]
        # Even without excluded_teams, PVE enemies aren't in team_a or team_b
        result = check_team_victory(
            players,
            team_a=["p1"],
            team_b=["p2"],
        )
        assert result == "team_a"


class TestResolveVictoryPVPVE:
    """D-2: _resolve_victory passes excluded_teams for PVPVE."""

    def test_pvpve_match_type_excludes_pve(self):
        """_resolve_victory with match_type='pvpve' excludes PVE team."""
        from app.core.turn_phases.deaths_phase import _resolve_victory

        players = {
            "p1": _make_player("p1", "a", alive=True),
            "p2": _make_player("p2", "b", alive=False),
            "pve1": _make_player("pve1", "pve", alive=True),
        }
        result = _resolve_victory(
            players,
            team_a=["p1"],
            team_b=["p2"],
            team_c=None,
            team_d=None,
            match_type="pvpve",
        )
        assert result == "team_a"

    def test_non_pvpve_match_type_no_exclusion(self):
        """Non-PVPVE match types do not exclude any team."""
        from app.core.turn_phases.deaths_phase import _resolve_victory

        players = {
            "p1": _make_player("p1", "a", alive=True),
            "p2": _make_player("p2", "b", alive=False),
        }
        result = _resolve_victory(
            players,
            team_a=["p1"],
            team_b=["p2"],
            team_c=None,
            team_d=None,
            match_type="pvp",
        )
        assert result == "team_a"

    def test_pvpve_all_dead_draw(self):
        """PVPVE: all player teams dead → draw."""
        from app.core.turn_phases.deaths_phase import _resolve_victory

        players = {
            "p1": _make_player("p1", "a", alive=False),
            "p2": _make_player("p2", "b", alive=False),
            "pve1": _make_player("pve1", "pve", alive=True),
        }
        result = _resolve_victory(
            players,
            team_a=["p1"],
            team_b=["p2"],
            team_c=None,
            team_d=None,
            match_type="pvpve",
        )
        assert result == "draw"


class TestPVEAITargeting:
    """D-3: PVE enemies target all player teams."""

    def test_pve_enemy_targets_team_a(self):
        """PVE enemy (team='pve') considers team 'a' units as enemies."""
        pve = _make_player("pve1", "pve")
        player_a = _make_player("p1", "a")
        assert not are_allies(pve, player_a)

    def test_pve_enemy_targets_team_b(self):
        pve = _make_player("pve1", "pve")
        player_b = _make_player("p2", "b")
        assert not are_allies(pve, player_b)

    def test_pve_enemy_targets_team_c(self):
        pve = _make_player("pve1", "pve")
        player_c = _make_player("p3", "c")
        assert not are_allies(pve, player_c)

    def test_pve_enemy_targets_team_d(self):
        pve = _make_player("pve1", "pve")
        player_d = _make_player("p4", "d")
        assert not are_allies(pve, player_d)

    def test_pve_allies_with_pve(self):
        """PVE enemies are allies with other PVE enemies."""
        pve1 = _make_player("pve1", "pve")
        pve2 = _make_player("pve2", "pve")
        assert are_allies(pve1, pve2)


class TestPlayerTeamsHostile:
    """D-4: Player teams are hostile to each other."""

    def test_team_a_hostile_to_team_b(self):
        p1 = _make_player("p1", "a")
        p2 = _make_player("p2", "b")
        assert not are_allies(p1, p2)

    def test_team_a_hostile_to_team_c(self):
        p1 = _make_player("p1", "a")
        p3 = _make_player("p3", "c")
        assert not are_allies(p1, p3)

    def test_team_a_hostile_to_team_d(self):
        p1 = _make_player("p1", "a")
        p4 = _make_player("p4", "d")
        assert not are_allies(p1, p4)

    def test_team_b_hostile_to_team_c(self):
        p2 = _make_player("p2", "b")
        p3 = _make_player("p3", "c")
        assert not are_allies(p2, p3)

    def test_same_team_are_allies(self):
        """Units on the same team are allies (friendly fire prevention)."""
        p1 = _make_player("p1", "a")
        p2 = _make_player("p2", "a")
        assert are_allies(p1, p2)

    def test_player_hostile_to_pve(self):
        """Player teams are hostile to PVE enemies."""
        p1 = _make_player("p1", "a")
        pve = _make_player("pve1", "pve")
        assert not are_allies(p1, pve)
