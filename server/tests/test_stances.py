"""
Tests for Phase 7C — AI Behavior Stances.

Covers:
  - ai_stance field on PlayerState model (default, validation)
  - Follow stance: follows owner, regroups after combat, fights nearby
  - Aggressive stance: pursues enemies freely, returns to owner when far
  - Defensive stance: stays close to owner, only attacks nearby enemies
  - Hold Position stance: never moves, attacks in range only
  - Stance management in match_manager (set_unit_stance, set_all_stances)
  - Stance persistence across turns
  - Stance included in party snapshot and players snapshot
  - Phase 7C-2: Stance in match_start payload, WS protocol state flow
  - Backward compatibility: enemy AI ignores stances, arena AI unaffected
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.ai_behavior import (
    decide_ai_action,
    VALID_STANCES,
    _decide_follow_action,
    _decide_aggressive_stance_action,
    _decide_defensive_action,
    _decide_hold_action,
    _find_owner,
    _chebyshev,
)
from app.core.combat import load_combat_config
from app.core.match_manager import (
    create_match,
    start_match,
    set_unit_stance,
    set_all_stances,
    get_party_members,
    get_players_snapshot,
    get_match_start_payload,
    is_party_member,
    _player_states,
    _active_matches,
    _hero_ally_map,
    _action_queues,
)
from app.models.match import MatchConfig, MatchType


def setup_module():
    load_combat_config()


def make_player(pid, username, x, y, hp=100, team="a", unit_type="human",
                hero_id=None, ai_stance="follow", class_id=None,
                ranged_range=5, ai_behavior=None, enemy_type=None) -> PlayerState:
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=100,
        attack_damage=15,
        ranged_damage=10,
        armor=0,
        team=team,
        unit_type=unit_type,
        hero_id=hero_id,
        ai_stance=ai_stance,
        class_id=class_id,
        ranged_range=ranged_range,
        ai_behavior=ai_behavior,
        enemy_type=enemy_type,
    )


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

class TestStanceModel:
    """Tests for ai_stance field on PlayerState."""

    def test_default_stance_is_follow(self):
        p = PlayerState(player_id="p1", username="Test")
        assert p.ai_stance == "follow"

    def test_stance_can_be_set(self):
        p = PlayerState(player_id="p1", username="Test", ai_stance="aggressive")
        assert p.ai_stance == "aggressive"

    def test_all_valid_stances_accepted(self):
        for stance in VALID_STANCES:
            p = PlayerState(player_id="p1", username="Test", ai_stance=stance)
            assert p.ai_stance == stance

    def test_valid_stances_set(self):
        assert VALID_STANCES == {"follow", "aggressive", "defensive", "hold"}


# ---------------------------------------------------------------------------
# Helper Tests
# ---------------------------------------------------------------------------

class TestHelpers:
    """Tests for stance helper functions."""

    def test_find_owner_by_controlled_by(self):
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 7, 7, unit_type="ai", hero_id="h1")
        ally.controlled_by = "owner"
        all_units = {"owner": owner, "ally": ally}
        found = _find_owner(ally, all_units)
        assert found is not None
        assert found.player_id == "owner"

    def test_find_owner_fallback_same_team(self):
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 7, 7, unit_type="ai", hero_id="h1")
        all_units = {"owner": owner, "ally": ally}
        found = _find_owner(ally, all_units)
        assert found is not None
        assert found.player_id == "owner"

    def test_find_owner_no_human_returns_none(self):
        ally = make_player("ally", "Ally", 7, 7, unit_type="ai", hero_id="h1")
        all_units = {"ally": ally}
        found = _find_owner(ally, all_units)
        assert found is None

    def test_find_owner_dead_controlled_by_fallback(self):
        """If the controlled_by owner is dead, fallback to another human."""
        dead_owner = make_player("dead", "Dead", 5, 5, unit_type="human", hp=0)
        dead_owner.is_alive = False
        live_human = make_player("live", "Live", 3, 3, unit_type="human")
        ally = make_player("ally", "Ally", 7, 7, unit_type="ai", hero_id="h1")
        ally.controlled_by = "dead"
        all_units = {"dead": dead_owner, "live": live_human, "ally": ally}
        found = _find_owner(ally, all_units)
        assert found is not None
        assert found.player_id == "live"

    def test_chebyshev_distance(self):
        assert _chebyshev((0, 0), (3, 4)) == 4
        assert _chebyshev((5, 5), (5, 5)) == 0
        assert _chebyshev((0, 0), (3, 3)) == 3
        assert _chebyshev((2, 5), (7, 3)) == 5


# ---------------------------------------------------------------------------
# Follow Stance Tests
# ---------------------------------------------------------------------------

class TestFollowStance:
    """Tests for follow stance AI behavior."""

    def test_follow_moves_toward_owner_when_far(self):
        """Ally > 2 tiles from owner with no enemies: moves toward owner."""
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 10, 5, unit_type="ai", hero_id="h1",
                           ai_stance="follow")
        all_units = {"owner": owner, "ally": ally}
        action = _decide_follow_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should move toward owner (x decreasing)
        assert action.target_x < 10

    def test_follow_waits_when_close_no_enemies(self):
        """Ally within 2 tiles of owner with no enemies: waits."""
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 6, 5, unit_type="ai", hero_id="h1",
                           ai_stance="follow")
        all_units = {"owner": owner, "ally": ally}
        action = _decide_follow_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.WAIT

    def test_follow_regroups_when_very_far(self):
        """Ally > 4 tiles from owner: regroups even during combat."""
        owner = make_player("owner", "Owner", 2, 2, unit_type="human")
        ally = make_player("ally", "Ally", 10, 10, unit_type="ai", hero_id="h1",
                           ai_stance="follow")
        # Place an enemy near the ally
        enemy = make_player("e1", "Enemy", 11, 10, team="b", unit_type="ai")
        all_units = {"owner": owner, "ally": ally, "e1": enemy}
        action = _decide_follow_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should move toward owner (both x and y decreasing toward 2,2)
        dx = action.target_x - ally.position.x
        dy = action.target_y - ally.position.y
        assert dx <= 0 or dy <= 0  # Moving generally toward owner

    def test_follow_attacks_adjacent_enemy(self):
        """Ally in follow stance attacks adjacent enemy when close to owner."""
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 6, 5, unit_type="ai", hero_id="h1",
                           ai_stance="follow")
        enemy = make_player("e1", "Enemy", 7, 5, team="b", unit_type="ai")
        all_units = {"owner": owner, "ally": ally, "e1": enemy}
        action = _decide_follow_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.ATTACK
        assert action.target_x == 7
        assert action.target_y == 5

    def test_follow_uses_ranged_when_available(self):
        """Ally can use ranged attack in follow stance."""
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 6, 5, unit_type="ai", hero_id="h1",
                           ai_stance="follow", ranged_range=5)
        enemy = make_player("e1", "Enemy", 10, 5, team="b", unit_type="ai")
        all_units = {"owner": owner, "ally": ally, "e1": enemy}
        action = _decide_follow_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type in (ActionType.RANGED_ATTACK, ActionType.MOVE)

    def test_follow_no_owner_waits(self):
        """Ally with no owner found waits."""
        ally = make_player("ally", "Ally", 5, 5, unit_type="ai", hero_id="h1",
                           ai_stance="follow")
        all_units = {"ally": ally}
        action = _decide_follow_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.WAIT


# ---------------------------------------------------------------------------
# Aggressive Stance Tests
# ---------------------------------------------------------------------------

class TestAggressiveStance:
    """Tests for aggressive stance AI behavior."""

    def test_aggressive_attacks_enemy(self):
        """Aggressive stance engages enemies freely."""
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 6, 5, unit_type="ai", hero_id="h1",
                           ai_stance="aggressive")
        enemy = make_player("e1", "Enemy", 7, 5, team="b", unit_type="ai")
        all_units = {"owner": owner, "ally": ally, "e1": enemy}
        action = _decide_aggressive_stance_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.ATTACK
        assert action.target_x == 7

    def test_aggressive_returns_to_owner_when_far(self):
        """Aggressive stance returns to owner when > 5 tiles away and no enemies."""
        owner = make_player("owner", "Owner", 2, 2, unit_type="human")
        ally = make_player("ally", "Ally", 12, 12, unit_type="ai", hero_id="h1",
                           ai_stance="aggressive")
        all_units = {"owner": owner, "ally": ally}
        action = _decide_aggressive_stance_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Should move toward owner
        assert action.target_x < 12 or action.target_y < 12

    def test_aggressive_waits_near_owner_no_enemies(self):
        """Aggressive stance waits when near owner and no enemies or memory."""
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 6, 5, unit_type="ai", hero_id="h1",
                           ai_stance="aggressive")
        all_units = {"owner": owner, "ally": ally}
        action = _decide_aggressive_stance_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.WAIT

    def test_aggressive_pursues_distant_enemy(self):
        """Aggressive stance moves toward distant enemies."""
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 6, 5, unit_type="ai", hero_id="h1",
                           ai_stance="aggressive")
        enemy = make_player("e1", "Enemy", 10, 5, team="b", unit_type="ai")
        all_units = {"owner": owner, "ally": ally, "e1": enemy}
        action = _decide_aggressive_stance_action(ally, all_units, 15, 15, set())
        assert action is not None
        # Either attack/ranged or move toward
        assert action.action_type in (ActionType.ATTACK, ActionType.RANGED_ATTACK, ActionType.MOVE)


# ---------------------------------------------------------------------------
# Defensive Stance Tests
# ---------------------------------------------------------------------------

class TestDefensiveStance:
    """Tests for defensive stance AI behavior."""

    def test_defensive_stays_near_owner(self):
        """Defensive ally moves back toward owner when > 2 tiles away."""
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 10, 5, unit_type="ai", hero_id="h1",
                           ai_stance="defensive")
        all_units = {"owner": owner, "ally": ally}
        action = _decide_defensive_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.MOVE
        # Moving toward owner
        assert action.target_x < 10

    def test_defensive_attacks_adjacent_enemy(self):
        """Defensive ally attacks adjacent enemy when close to owner."""
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 6, 5, unit_type="ai", hero_id="h1",
                           ai_stance="defensive")
        enemy = make_player("e1", "Enemy", 7, 5, team="b", unit_type="ai")
        all_units = {"owner": owner, "ally": ally, "e1": enemy}
        action = _decide_defensive_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.ATTACK
        assert action.target_x == 7

    def test_defensive_ignores_distant_enemy(self):
        """Defensive ally ignores enemies > 2 tiles away."""
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 6, 5, unit_type="ai", hero_id="h1",
                           ai_stance="defensive")
        enemy = make_player("e1", "Enemy", 12, 5, team="b", unit_type="ai")
        all_units = {"owner": owner, "ally": ally, "e1": enemy}
        action = _decide_defensive_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.WAIT

    def test_defensive_waits_near_owner_no_enemies(self):
        """Defensive ally waits when close to owner and no nearby threats."""
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 6, 5, unit_type="ai", hero_id="h1",
                           ai_stance="defensive")
        all_units = {"owner": owner, "ally": ally}
        action = _decide_defensive_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.WAIT

    def test_defensive_no_owner_waits(self):
        """Defensive ally with no owner waits."""
        ally = make_player("ally", "Ally", 5, 5, unit_type="ai", hero_id="h1",
                           ai_stance="defensive")
        all_units = {"ally": ally}
        action = _decide_defensive_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.WAIT

    def test_defensive_ranged_nearby_enemy(self):
        """Defensive ally uses ranged on enemy within 2 tiles if not adjacent."""
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 6, 5, unit_type="ai", hero_id="h1",
                           ai_stance="defensive", ranged_range=5)
        enemy = make_player("e1", "Enemy", 8, 5, team="b", unit_type="ai")
        all_units = {"owner": owner, "ally": ally, "e1": enemy}
        action = _decide_defensive_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type in (ActionType.RANGED_ATTACK, ActionType.MOVE, ActionType.WAIT)


# ---------------------------------------------------------------------------
# Hold Position Stance Tests
# ---------------------------------------------------------------------------

class TestHoldStance:
    """Tests for hold position stance AI behavior."""

    def test_hold_never_moves(self):
        """Hold stance never generates MOVE actions."""
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 10, 10, unit_type="ai", hero_id="h1",
                           ai_stance="hold")
        all_units = {"owner": owner, "ally": ally}
        action = _decide_hold_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.WAIT

    def test_hold_attacks_adjacent_enemy(self):
        """Hold stance attacks adjacent enemies (melee)."""
        ally = make_player("ally", "Ally", 5, 5, unit_type="ai", hero_id="h1",
                           ai_stance="hold")
        enemy = make_player("e1", "Enemy", 6, 5, team="b", unit_type="ai")
        all_units = {"ally": ally, "e1": enemy}
        action = _decide_hold_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.ATTACK
        assert action.target_x == 6
        assert action.target_y == 5

    def test_hold_ranged_attack_in_range(self):
        """Hold stance uses ranged on enemies in range."""
        ally = make_player("ally", "Ally", 5, 5, unit_type="ai", hero_id="h1",
                           ai_stance="hold", ranged_range=5)
        enemy = make_player("e1", "Enemy", 9, 5, team="b", unit_type="ai")
        all_units = {"ally": ally, "e1": enemy}
        action = _decide_hold_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.RANGED_ATTACK

    def test_hold_no_attack_out_of_range(self):
        """Hold stance waits if enemy out of range."""
        ally = make_player("ally", "Ally", 5, 5, unit_type="ai", hero_id="h1",
                           ai_stance="hold", ranged_range=3)
        enemy = make_player("e1", "Enemy", 12, 5, team="b", unit_type="ai")
        all_units = {"ally": ally, "e1": enemy}
        action = _decide_hold_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.WAIT

    def test_hold_ranged_on_cooldown_waits(self):
        """Hold stance waits if ranged is on cooldown and no adjacent enemy."""
        ally = make_player("ally", "Ally", 5, 5, unit_type="ai", hero_id="h1",
                           ai_stance="hold", ranged_range=5)
        ally.cooldowns["ranged_attack"] = 2
        enemy = make_player("e1", "Enemy", 9, 5, team="b", unit_type="ai")
        all_units = {"ally": ally, "e1": enemy}
        action = _decide_hold_action(ally, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.WAIT

    def test_hold_ranged_blocked_by_obstacle(self):
        """Hold stance doesn't ranged attack through obstacles."""
        ally = make_player("ally", "Ally", 5, 5, unit_type="ai", hero_id="h1",
                           ai_stance="hold", ranged_range=5)
        enemy = make_player("e1", "Enemy", 9, 5, team="b", unit_type="ai")
        # Wall blocking LOS
        obstacles = {(7, 5)}
        all_units = {"ally": ally, "e1": enemy}
        action = _decide_hold_action(ally, all_units, 15, 15, obstacles)
        assert action is not None
        assert action.action_type == ActionType.WAIT


# ---------------------------------------------------------------------------
# decide_ai_action Dispatch Tests
# ---------------------------------------------------------------------------

class TestStanceDispatch:
    """Tests that decide_ai_action dispatches to stance-based behavior for hero allies."""

    def test_hero_ally_uses_stance_dispatch(self):
        """Hero ally with ai_stance dispatches to stance behavior, not enemy aggressive."""
        owner = make_player("owner", "Owner", 5, 5, unit_type="human")
        ally = make_player("ally", "Ally", 6, 5, unit_type="ai", hero_id="h1",
                           ai_stance="hold")
        # Far enemy — hold stance should WAIT, aggressive would MOVE
        enemy = make_player("e1", "Enemy", 12, 5, team="b", unit_type="ai")
        all_units = {"owner": owner, "ally": ally, "e1": enemy}
        action = decide_ai_action(ally, all_units, 15, 15, set())
        assert action is not None
        # Hold stance should NOT move, it should wait (enemy out of range)
        assert action.action_type == ActionType.WAIT

    def test_enemy_ai_ignores_stance(self):
        """Enemy AI (with enemy_type) ignores ai_stance field."""
        enemy = make_player("e1", "Enemy", 5, 5, team="b", unit_type="ai",
                            ai_behavior="aggressive", enemy_type="demon")
        enemy.ai_stance = "hold"  # Should be ignored
        target = make_player("p1", "Player", 7, 5, team="a", unit_type="human")
        all_units = {"e1": enemy, "p1": target}
        action = decide_ai_action(enemy, all_units, 15, 15, set())
        assert action is not None
        # Aggressive enemy should MOVE toward player, not WAIT (ignoring hold)
        assert action.action_type in (ActionType.MOVE, ActionType.ATTACK)

    def test_non_hero_ai_ignores_stance(self):
        """Arena AI (no hero_id) uses standard aggressive behavior."""
        ai = make_player("ai1", "Bot", 5, 5, team="b", unit_type="ai")
        ai.ai_stance = "hold"  # Should be ignored — no hero_id
        target = make_player("p1", "Player", 7, 5, team="a", unit_type="human")
        all_units = {"ai1": ai, "p1": target}
        action = decide_ai_action(ai, all_units, 15, 15, set())
        assert action is not None
        # Standard aggressive AI should engage, not hold
        assert action.action_type in (ActionType.MOVE, ActionType.ATTACK)

    def test_dead_ally_no_action(self):
        """Dead hero ally returns None."""
        ally = make_player("ally", "Ally", 5, 5, unit_type="ai", hero_id="h1",
                           ai_stance="follow", hp=0)
        ally.is_alive = False
        all_units = {"ally": ally}
        action = decide_ai_action(ally, all_units, 15, 15, set())
        assert action is None


# ---------------------------------------------------------------------------
# Stance Persistence Tests
# ---------------------------------------------------------------------------

class TestStancePersistence:
    """Tests that stance persists across turns and survives state changes."""

    def test_stance_persists_on_model(self):
        """ai_stance value persists on the PlayerState object."""
        ally = make_player("ally", "Ally", 5, 5, unit_type="ai", hero_id="h1")
        assert ally.ai_stance == "follow"
        ally.ai_stance = "aggressive"
        assert ally.ai_stance == "aggressive"
        # Simulate multiple turns — stance should remain
        ally.hp -= 10
        assert ally.ai_stance == "aggressive"

    def test_stance_survives_serialization(self):
        """ai_stance roundtrips through dict serialization."""
        ally = make_player("ally", "Ally", 5, 5, unit_type="ai", hero_id="h1",
                           ai_stance="defensive")
        d = ally.model_dump()
        assert d["ai_stance"] == "defensive"
        restored = PlayerState(**d)
        assert restored.ai_stance == "defensive"


# ---------------------------------------------------------------------------
# Match Manager Stance Management Tests
# ---------------------------------------------------------------------------

class TestMatchManagerStance:
    """Tests for set_unit_stance and set_all_stances in match_manager."""

    def _setup_match_with_allies(self):
        """Create a match with a human player and two hero allies."""
        config = MatchConfig(map_id="arena_classic", match_type=MatchType.SOLO_PVE)
        match, player = create_match("TestPlayer", config)
        match_id = match.match_id
        players = _player_states[match_id]

        # Create two hero allies
        ally1 = PlayerState(
            player_id="hero-a1",
            username="Ally1",
            position=Position(x=3, y=3),
            unit_type="ai",
            team="a",
            hero_id="h1",
            is_alive=True,
            ai_stance="follow",
        )
        ally2 = PlayerState(
            player_id="hero-a2",
            username="Ally2",
            position=Position(x=4, y=3),
            unit_type="ai",
            team="a",
            hero_id="h2",
            is_alive=True,
            ai_stance="follow",
        )
        players["hero-a1"] = ally1
        players["hero-a2"] = ally2
        match.player_ids.extend(["hero-a1", "hero-a2"])
        match.ai_ids.extend(["hero-a1", "hero-a2"])
        match.team_a.extend(["hero-a1", "hero-a2"])

        # Register in hero ally map
        if match_id not in _hero_ally_map:
            _hero_ally_map[match_id] = {}
        _hero_ally_map[match_id]["hero-a1"] = "TestPlayer"
        _hero_ally_map[match_id]["hero-a2"] = "TestPlayer"

        return match_id, player.player_id

    def test_set_unit_stance_valid(self):
        match_id, pid = self._setup_match_with_allies()
        result = set_unit_stance(match_id, pid, "hero-a1", "aggressive")
        assert result is True
        players = _player_states[match_id]
        assert players["hero-a1"].ai_stance == "aggressive"

    def test_set_unit_stance_invalid_stance(self):
        match_id, pid = self._setup_match_with_allies()
        result = set_unit_stance(match_id, pid, "hero-a1", "invalid_stance")
        assert result is False
        players = _player_states[match_id]
        assert players["hero-a1"].ai_stance == "follow"  # unchanged

    def test_set_unit_stance_not_party_member(self):
        match_id, pid = self._setup_match_with_allies()
        result = set_unit_stance(match_id, pid, "nonexistent", "aggressive")
        assert result is False

    def test_set_all_stances(self):
        match_id, pid = self._setup_match_with_allies()
        updated = set_all_stances(match_id, pid, "hold")
        assert len(updated) == 2
        assert "hero-a1" in updated
        assert "hero-a2" in updated
        players = _player_states[match_id]
        assert players["hero-a1"].ai_stance == "hold"
        assert players["hero-a2"].ai_stance == "hold"

    def test_set_all_stances_invalid(self):
        match_id, pid = self._setup_match_with_allies()
        updated = set_all_stances(match_id, pid, "invalid")
        assert len(updated) == 0

    def test_set_unit_stance_all_valid_stances(self):
        """Each valid stance can be set via match_manager."""
        match_id, pid = self._setup_match_with_allies()
        for stance in VALID_STANCES:
            result = set_unit_stance(match_id, pid, "hero-a1", stance)
            assert result is True
            players = _player_states[match_id]
            assert players["hero-a1"].ai_stance == stance

    def test_set_unit_stance_dead_ally_fails(self):
        match_id, pid = self._setup_match_with_allies()
        players = _player_states[match_id]
        players["hero-a1"].is_alive = False
        result = set_unit_stance(match_id, pid, "hero-a1", "aggressive")
        assert result is False


# ---------------------------------------------------------------------------
# Snapshot Tests — ai_stance in broadcasts
# ---------------------------------------------------------------------------

class TestStanceInSnapshots:
    """Tests that ai_stance is included in party/player snapshots."""

    def test_party_members_include_stance(self):
        """get_party_members includes ai_stance for each ally."""
        config = MatchConfig(map_id="arena_classic", match_type=MatchType.SOLO_PVE)
        match, player = create_match("SnapshotPlayer", config)
        match_id = match.match_id
        players = _player_states[match_id]

        ally = PlayerState(
            player_id="hero-s1",
            username="SnapAlly",
            position=Position(x=3, y=3),
            unit_type="ai",
            team="a",
            hero_id="h1",
            is_alive=True,
            ai_stance="defensive",
        )
        players["hero-s1"] = ally
        match.player_ids.append("hero-s1")
        match.ai_ids.append("hero-s1")
        match.team_a.append("hero-s1")
        if match_id not in _hero_ally_map:
            _hero_ally_map[match_id] = {}
        _hero_ally_map[match_id]["hero-s1"] = "SnapshotPlayer"

        party = get_party_members(match_id, player.player_id)
        assert len(party) >= 1
        ally_info = [p for p in party if p["unit_id"] == "hero-s1"][0]
        assert ally_info["ai_stance"] == "defensive"

    def test_players_snapshot_includes_stance(self):
        """get_players_snapshot includes ai_stance for all units."""
        config = MatchConfig(map_id="arena_classic", match_type=MatchType.SOLO_PVE)
        match, player = create_match("SnapPlayer2", config)
        match_id = match.match_id

        snapshot = get_players_snapshot(match_id)
        for pid, data in snapshot.items():
            assert "ai_stance" in data


# ---------------------------------------------------------------------------
# Backward Compatibility Tests
# ---------------------------------------------------------------------------

class TestStanceBackwardCompat:
    """Ensure stances don't affect existing arena/enemy AI behavior."""

    def test_arena_ai_default_stance(self):
        """Default ai_stance is 'follow' but arena AI without hero_id ignores it."""
        ai = make_player("ai1", "Bot", 5, 5, team="b", unit_type="ai")
        assert ai.ai_stance == "follow"
        assert ai.hero_id is None
        # No hero_id → decide_ai_action uses enemy behavior, not stance
        target = make_player("p1", "Player", 7, 5, team="a", unit_type="human")
        all_units = {"ai1": ai, "p1": target}
        action = decide_ai_action(ai, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type in (ActionType.MOVE, ActionType.ATTACK)

    def test_boss_enemy_ignores_stance(self):
        """Boss enemy AI uses boss behavior regardless of ai_stance."""
        boss = make_player("boss", "UKnight", 5, 5, team="b", unit_type="ai",
                           ai_behavior="boss", enemy_type="undead_knight")
        boss.ai_stance = "follow"  # Should be completely ignored
        target = make_player("p1", "Player", 6, 5, team="a", unit_type="human")
        all_units = {"boss": boss, "p1": target}
        action = decide_ai_action(boss, all_units, 15, 15, set())
        assert action is not None
        assert action.action_type == ActionType.ATTACK  # Boss engages adjacent target

    def test_ranged_enemy_ignores_stance(self):
        """Ranged enemy AI uses ranged behavior regardless of ai_stance."""
        ranged = make_player("r1", "Skel", 5, 5, team="b", unit_type="ai",
                             ai_behavior="ranged", enemy_type="skeleton")
        ranged.ai_stance = "hold"  # Should be ignored
        target = make_player("p1", "Player", 6, 5, team="a", unit_type="human")
        all_units = {"r1": ranged, "p1": target}
        action = decide_ai_action(ranged, all_units, 15, 15, set())
        assert action is not None
        # Ranged enemy adjacent to player will retreat or melee — NOT hold
        assert action.action_type in (ActionType.MOVE, ActionType.ATTACK)

    def test_player_state_default_backward_compat(self):
        """PlayerState created without ai_stance gets default 'follow'."""
        p = PlayerState(player_id="p1", username="Legacy")
        assert p.ai_stance == "follow"
        # Doesn't break any existing constructors


# ---------------------------------------------------------------------------
# Phase 7C-2: Stance WS Protocol & State Tests
# ---------------------------------------------------------------------------

class TestStanceWSProtocol:
    """Tests for 7C-2 — stance included in match_start payload and protocol state flow."""

    def _setup_match_with_ally(self, stance="follow"):
        """Create a match with one hero ally at a specific stance."""
        config = MatchConfig(map_id="arena_classic", match_type=MatchType.SOLO_PVE)
        match, player = create_match("ProtoPlayer", config)
        match_id = match.match_id
        players = _player_states[match_id]

        ally = PlayerState(
            player_id="hero-p1",
            username="ProtoAlly",
            position=Position(x=3, y=3),
            unit_type="ai",
            team="a",
            hero_id="h1",
            is_alive=True,
            ai_stance=stance,
        )
        players["hero-p1"] = ally
        match.player_ids.append("hero-p1")
        match.ai_ids.append("hero-p1")
        match.team_a.append("hero-p1")
        if match_id not in _hero_ally_map:
            _hero_ally_map[match_id] = {}
        _hero_ally_map[match_id]["hero-p1"] = "ProtoPlayer"

        return match_id, player.player_id

    def test_match_start_payload_includes_stance(self):
        """match_start payload includes ai_stance for every unit."""
        match_id, pid = self._setup_match_with_ally("aggressive")
        payload = get_match_start_payload(match_id)
        assert payload is not None

        # Check the owner player has default stance
        assert payload["players"][pid]["ai_stance"] == "follow"
        # Check the ally has the stance we set
        assert payload["players"]["hero-p1"]["ai_stance"] == "aggressive"

    def test_match_start_default_stance(self):
        """New units in match_start default to 'follow' stance."""
        match_id, pid = self._setup_match_with_ally()
        payload = get_match_start_payload(match_id)
        assert payload["players"]["hero-p1"]["ai_stance"] == "follow"

    def test_stance_change_reflected_in_party_snapshot(self):
        """After set_unit_stance, the new stance appears in get_party_members."""
        match_id, pid = self._setup_match_with_ally("follow")

        # Change stance
        result = set_unit_stance(match_id, pid, "hero-p1", "defensive")
        assert result is True

        # Verify it's reflected in party snapshot
        party = get_party_members(match_id, pid)
        ally_info = [p for p in party if p["unit_id"] == "hero-p1"][0]
        assert ally_info["ai_stance"] == "defensive"

    def test_stance_change_reflected_in_players_snapshot(self):
        """After set_unit_stance, the new stance appears in get_players_snapshot."""
        match_id, pid = self._setup_match_with_ally("follow")

        set_unit_stance(match_id, pid, "hero-p1", "hold")

        snapshot = get_players_snapshot(match_id)
        assert snapshot["hero-p1"]["ai_stance"] == "hold"

    def test_set_all_stances_reflected_in_snapshots(self):
        """set_all_stances updates are visible in both party and players snapshots."""
        config = MatchConfig(map_id="arena_classic", match_type=MatchType.SOLO_PVE)
        match, player = create_match("AllStancePlayer", config)
        match_id = match.match_id
        pid = player.player_id
        players = _player_states[match_id]

        # Add two allies
        for i, aid in enumerate(["hero-as1", "hero-as2"]):
            ally = PlayerState(
                player_id=aid,
                username=f"Ally{i}",
                position=Position(x=3 + i, y=3),
                unit_type="ai",
                team="a",
                hero_id=f"h{i}",
                is_alive=True,
                ai_stance="follow",
            )
            players[aid] = ally
            match.player_ids.append(aid)
            match.ai_ids.append(aid)
            match.team_a.append(aid)
        if match_id not in _hero_ally_map:
            _hero_ally_map[match_id] = {}
        _hero_ally_map[match_id]["hero-as1"] = "AllStancePlayer"
        _hero_ally_map[match_id]["hero-as2"] = "AllStancePlayer"

        # Set all to aggressive
        updated = set_all_stances(match_id, pid, "aggressive")
        assert set(updated) == {"hero-as1", "hero-as2"}

        # Verify in party snapshot
        party = get_party_members(match_id, pid)
        for member in party:
            assert member["ai_stance"] == "aggressive"

        # Verify in players snapshot
        snapshot = get_players_snapshot(match_id)
        assert snapshot["hero-as1"]["ai_stance"] == "aggressive"
        assert snapshot["hero-as2"]["ai_stance"] == "aggressive"

    def test_stance_multiple_changes_persist(self):
        """Multiple successive stance changes all persist correctly."""
        match_id, pid = self._setup_match_with_ally("follow")

        for stance in ["aggressive", "defensive", "hold", "follow"]:
            result = set_unit_stance(match_id, pid, "hero-p1", stance)
            assert result is True
            party = get_party_members(match_id, pid)
            ally_info = [p for p in party if p["unit_id"] == "hero-p1"][0]
            assert ally_info["ai_stance"] == stance
