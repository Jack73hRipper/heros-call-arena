"""
Tests for Phase 26B: Shaman effect handlers.

Covers:
- Healing Totem (place_totem — healing variant): creates totem entity, validates
  placement rules (empty tile, no wall, LOS, range), max 1 per type, correct stats
- Searing Totem (place_totem — searing variant): creates totem entity, validates
  placement, max 1 per type, can coexist with healing totem
- Soul Anchor (soul_anchor): applies cheat-death buff to ally/self, range check,
  max 1 active per Shaman, correct buff fields
- Earthgrasp (aoe_root): roots enemies in radius, doesn't root allies, LOS/range
  validation, multiple enemies, correct debuff fields
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType, ActionResult
from app.models.match import MatchState
from app.core.skills import (
    load_skills_config,
    clear_skills_cache,
    get_skill,
    resolve_skill_action,
    resolve_place_totem,
    resolve_soul_anchor,
    resolve_aoe_root,
)


# ---------- Fixtures ----------


@pytest.fixture(autouse=True)
def _reset_caches():
    """Clear cached configs before each test to ensure isolation."""
    clear_skills_cache()
    import app.models.player as player_mod
    player_mod._classes_cache = None
    yield
    clear_skills_cache()
    player_mod._classes_cache = None


@pytest.fixture
def loaded_skills() -> dict:
    """Load and return the skills config dict."""
    return load_skills_config()


def _make_player(
    player_id: str = "shaman1",
    username: str = "TestShaman",
    class_id: str = "shaman",
    hp: int = 95,
    max_hp: int = 95,
    attack_damage: int = 8,
    ranged_damage: int = 10,
    armor: int = 3,
    alive: bool = True,
    cooldowns: dict | None = None,
    team: str = "team_1",
    x: int = 5,
    y: int = 5,
    buffs: list | None = None,
) -> PlayerState:
    """Helper — create a Shaman PlayerState."""
    p = PlayerState(
        player_id=player_id,
        username=username,
        position=Position(x=x, y=y),
        class_id=class_id,
        hp=hp,
        max_hp=max_hp,
        attack_damage=attack_damage,
        ranged_damage=ranged_damage,
        armor=armor,
        is_alive=alive,
        cooldowns=cooldowns or {},
        team=team,
    )
    if buffs:
        p.active_buffs = buffs
    return p


def _make_ally(
    player_id: str = "ally1",
    username: str = "TestAlly",
    class_id: str = "crusader",
    hp: int = 150,
    max_hp: int = 150,
    attack_damage: int = 20,
    armor: int = 8,
    team: str = "team_1",
    x: int = 6,
    y: int = 5,
    alive: bool = True,
) -> PlayerState:
    """Helper — create an ally PlayerState."""
    return PlayerState(
        player_id=player_id,
        username=username,
        position=Position(x=x, y=y),
        class_id=class_id,
        hp=hp,
        max_hp=max_hp,
        attack_damage=attack_damage,
        armor=armor,
        is_alive=alive,
        team=team,
    )


def _make_enemy(
    player_id: str = "enemy1",
    username: str = "TestEnemy",
    class_id: str = "ranger",
    hp: int = 80,
    max_hp: int = 80,
    attack_damage: int = 8,
    armor: int = 2,
    team: str = "team_2",
    x: int = 7,
    y: int = 5,
    alive: bool = True,
) -> PlayerState:
    """Helper — create an enemy PlayerState."""
    return PlayerState(
        player_id=player_id,
        username=username,
        position=Position(x=x, y=y),
        class_id=class_id,
        hp=hp,
        max_hp=max_hp,
        attack_damage=attack_damage,
        armor=armor,
        is_alive=alive,
        team=team,
    )


def _make_action(
    player_id: str = "shaman1",
    skill_id: str | None = None,
    target_x: int | None = None,
    target_y: int | None = None,
    target_id: str | None = None,
) -> PlayerAction:
    """Helper — create a skill action."""
    return PlayerAction(
        player_id=player_id,
        action_type=ActionType.SKILL,
        skill_id=skill_id,
        target_x=target_x,
        target_y=target_y,
        target_id=target_id,
    )


def _make_match_state() -> MatchState:
    """Helper — create a minimal MatchState with totems list."""
    return MatchState(match_id="test_match", totems=[])


# ============================================================
# 1. Healing Totem (place_totem — healing variant) Tests
# ============================================================

class TestHealingTotem:
    """Tests for resolve_place_totem() — Healing Totem variant."""

    def test_healing_totem_creates_entity(self, loaded_skills):
        """Healing Totem creates a healing totem entity at the target tile."""
        player = _make_player(x=5, y=5)
        action = _make_action(skill_id="healing_totem", target_x=7, target_y=5)
        skill_def = get_skill("healing_totem")
        players = {"shaman1": player}
        match_state = _make_match_state()

        result = resolve_place_totem(player, action, skill_def, players, set(), match_state)

        assert result.success is True
        assert "placed" in result.message
        assert "Healing Totem" in result.message
        assert len(match_state.totems) == 1

        totem = match_state.totems[0]
        assert totem["type"] == "healing_totem"
        assert totem["x"] == 7
        assert totem["y"] == 5
        assert totem["owner_id"] == "shaman1"

    def test_healing_totem_correct_stats(self, loaded_skills):
        """Healing totem has correct HP (20), effect radius (2), heal per turn (8), duration (4)."""
        player = _make_player(x=5, y=5)
        action = _make_action(skill_id="healing_totem", target_x=7, target_y=5)
        skill_def = get_skill("healing_totem")
        players = {"shaman1": player}
        match_state = _make_match_state()

        resolve_place_totem(player, action, skill_def, players, set(), match_state)

        totem = match_state.totems[0]
        assert totem["hp"] == 20
        assert totem["max_hp"] == 20
        assert totem["heal_per_turn"] == 8
        assert totem["damage_per_turn"] == 0
        assert totem["effect_radius"] == 2
        assert totem["duration_remaining"] == 4
        assert totem["team"] == "team_1"

    def test_healing_totem_fails_on_occupied_tile(self, loaded_skills):
        """Healing Totem fails when target tile has a unit on it."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=7, y=5)
        action = _make_action(skill_id="healing_totem", target_x=7, target_y=5)
        skill_def = get_skill("healing_totem")
        players = {"shaman1": player, "enemy1": enemy}
        match_state = _make_match_state()

        result = resolve_place_totem(player, action, skill_def, players, set(), match_state)

        assert result.success is False
        assert "occupied" in result.message
        assert len(match_state.totems) == 0

    def test_healing_totem_fails_on_wall_tile(self, loaded_skills):
        """Healing Totem fails when target tile is a wall/obstacle."""
        player = _make_player(x=5, y=5)
        action = _make_action(skill_id="healing_totem", target_x=7, target_y=5)
        skill_def = get_skill("healing_totem")
        players = {"shaman1": player}
        obstacles = {(7, 5)}
        match_state = _make_match_state()

        result = resolve_place_totem(player, action, skill_def, players, obstacles, match_state)

        assert result.success is False
        assert "blocked" in result.message
        assert len(match_state.totems) == 0

    def test_healing_totem_requires_los(self, loaded_skills):
        """Healing Totem fails when line of sight is blocked."""
        player = _make_player(x=5, y=5)
        action = _make_action(skill_id="healing_totem", target_x=8, target_y=5)
        skill_def = get_skill("healing_totem")
        players = {"shaman1": player}
        # Block LOS between (5,5) and (8,5)
        obstacles = {(6, 5), (7, 5)}
        match_state = _make_match_state()

        result = resolve_place_totem(player, action, skill_def, players, obstacles, match_state)

        assert result.success is False
        assert "line of sight" in result.message
        assert len(match_state.totems) == 0

    def test_healing_totem_fails_out_of_range(self, loaded_skills):
        """Healing Totem fails when target tile is beyond range 4."""
        player = _make_player(x=5, y=5)
        action = _make_action(skill_id="healing_totem", target_x=10, target_y=5)  # Distance 5
        skill_def = get_skill("healing_totem")
        players = {"shaman1": player}
        match_state = _make_match_state()

        result = resolve_place_totem(player, action, skill_def, players, set(), match_state)

        assert result.success is False
        assert "out of range" in result.message

    def test_placing_second_healing_totem_removes_first(self, loaded_skills):
        """Placing a second Healing Totem removes the first (max 1 per type)."""
        player = _make_player(x=5, y=5)
        skill_def = get_skill("healing_totem")
        players = {"shaman1": player}
        match_state = _make_match_state()

        # Place first
        action1 = _make_action(skill_id="healing_totem", target_x=7, target_y=5)
        resolve_place_totem(player, action1, skill_def, players, set(), match_state)
        assert len(match_state.totems) == 1
        first_id = match_state.totems[0]["id"]

        # Reset cooldown to allow recast
        player.cooldowns["healing_totem"] = 0

        # Place second at different position
        action2 = _make_action(skill_id="healing_totem", target_x=3, target_y=5)
        resolve_place_totem(player, action2, skill_def, players, set(), match_state)

        assert len(match_state.totems) == 1
        assert match_state.totems[0]["id"] != first_id  # New totem
        assert match_state.totems[0]["x"] == 3

    def test_healing_totem_sets_cooldown(self, loaded_skills):
        """Healing Totem sets cooldown to 6."""
        player = _make_player(x=5, y=5)
        action = _make_action(skill_id="healing_totem", target_x=7, target_y=5)
        skill_def = get_skill("healing_totem")
        players = {"shaman1": player}
        match_state = _make_match_state()

        resolve_place_totem(player, action, skill_def, players, set(), match_state)

        assert player.cooldowns.get("healing_totem", 0) == 6

    def test_healing_totem_fails_no_target(self, loaded_skills):
        """Healing Totem fails when no target coordinates are provided."""
        player = _make_player(x=5, y=5)
        action = _make_action(skill_id="healing_totem", target_x=None, target_y=None)
        skill_def = get_skill("healing_totem")
        players = {"shaman1": player}
        match_state = _make_match_state()

        result = resolve_place_totem(player, action, skill_def, players, set(), match_state)

        assert result.success is False
        assert "no target" in result.message

    def test_healing_totem_via_dispatcher(self, loaded_skills):
        """Healing Totem resolves correctly through resolve_skill_action dispatcher."""
        player = _make_player(x=5, y=5)
        action = _make_action(skill_id="healing_totem", target_x=7, target_y=5)
        skill_def = get_skill("healing_totem")
        players = {"shaman1": player}
        match_state = _make_match_state()

        result = resolve_skill_action(
            player, action, skill_def, players, set(), 20, 20,
            match_state=match_state,
        )

        assert result.success is True
        assert len(match_state.totems) == 1
        assert match_state.totems[0]["type"] == "healing_totem"


# ============================================================
# 2. Searing Totem (place_totem — searing variant) Tests
# ============================================================

class TestSearingTotem:
    """Tests for resolve_place_totem() — Searing Totem variant."""

    def test_searing_totem_creates_entity(self, loaded_skills):
        """Searing Totem creates a searing totem entity at the target tile."""
        player = _make_player(x=5, y=5)
        action = _make_action(skill_id="searing_totem", target_x=7, target_y=5)
        skill_def = get_skill("searing_totem")
        players = {"shaman1": player}
        match_state = _make_match_state()

        result = resolve_place_totem(player, action, skill_def, players, set(), match_state)

        assert result.success is True
        assert "placed" in result.message
        assert "Searing Totem" in result.message
        assert len(match_state.totems) == 1

        totem = match_state.totems[0]
        assert totem["type"] == "searing_totem"
        assert totem["x"] == 7
        assert totem["y"] == 5

    def test_searing_totem_correct_stats(self, loaded_skills):
        """Searing totem has correct HP (20), effect radius (2), damage per turn (4), duration (4)."""
        player = _make_player(x=5, y=5)
        action = _make_action(skill_id="searing_totem", target_x=7, target_y=5)
        skill_def = get_skill("searing_totem")
        players = {"shaman1": player}
        match_state = _make_match_state()

        resolve_place_totem(player, action, skill_def, players, set(), match_state)

        totem = match_state.totems[0]
        assert totem["hp"] == 20
        assert totem["max_hp"] == 20
        assert totem["heal_per_turn"] == 0
        assert totem["damage_per_turn"] == 4
        assert totem["effect_radius"] == 2
        assert totem["duration_remaining"] == 4

    def test_searing_totem_fails_on_occupied_tile(self, loaded_skills):
        """Searing Totem fails on occupied tile."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=7, y=5)
        action = _make_action(skill_id="searing_totem", target_x=7, target_y=5)
        skill_def = get_skill("searing_totem")
        players = {"shaman1": player, "enemy1": enemy}
        match_state = _make_match_state()

        result = resolve_place_totem(player, action, skill_def, players, set(), match_state)
        assert result.success is False
        assert "occupied" in result.message

    def test_searing_totem_fails_on_wall(self, loaded_skills):
        """Searing Totem fails on wall tile."""
        player = _make_player(x=5, y=5)
        action = _make_action(skill_id="searing_totem", target_x=7, target_y=5)
        skill_def = get_skill("searing_totem")
        players = {"shaman1": player}
        obstacles = {(7, 5)}
        match_state = _make_match_state()

        result = resolve_place_totem(player, action, skill_def, players, obstacles, match_state)
        assert result.success is False
        assert "blocked" in result.message

    def test_searing_totem_requires_los(self, loaded_skills):
        """Searing Totem fails when LOS is blocked."""
        player = _make_player(x=5, y=5)
        action = _make_action(skill_id="searing_totem", target_x=8, target_y=5)
        skill_def = get_skill("searing_totem")
        players = {"shaman1": player}
        obstacles = {(6, 5), (7, 5)}
        match_state = _make_match_state()

        result = resolve_place_totem(player, action, skill_def, players, obstacles, match_state)
        assert result.success is False
        assert "line of sight" in result.message

    def test_placing_second_searing_totem_removes_first(self, loaded_skills):
        """Placing a second Searing Totem removes the first (max 1 per type)."""
        player = _make_player(x=5, y=5)
        skill_def = get_skill("searing_totem")
        players = {"shaman1": player}
        match_state = _make_match_state()

        action1 = _make_action(skill_id="searing_totem", target_x=7, target_y=5)
        resolve_place_totem(player, action1, skill_def, players, set(), match_state)
        first_id = match_state.totems[0]["id"]

        player.cooldowns["searing_totem"] = 0
        action2 = _make_action(skill_id="searing_totem", target_x=3, target_y=5)
        resolve_place_totem(player, action2, skill_def, players, set(), match_state)

        assert len(match_state.totems) == 1
        assert match_state.totems[0]["id"] != first_id

    def test_searing_totem_sets_cooldown(self, loaded_skills):
        """Searing Totem sets cooldown to 6."""
        player = _make_player(x=5, y=5)
        action = _make_action(skill_id="searing_totem", target_x=7, target_y=5)
        skill_def = get_skill("searing_totem")
        players = {"shaman1": player}
        match_state = _make_match_state()

        resolve_place_totem(player, action, skill_def, players, set(), match_state)
        assert player.cooldowns.get("searing_totem", 0) == 6

    def test_shaman_can_have_both_totem_types(self, loaded_skills):
        """A Shaman can have 1 healing + 1 searing totem simultaneously."""
        player = _make_player(x=5, y=5)
        players = {"shaman1": player}
        match_state = _make_match_state()

        # Place healing totem
        healing_def = get_skill("healing_totem")
        action1 = _make_action(skill_id="healing_totem", target_x=7, target_y=5)
        resolve_place_totem(player, action1, healing_def, players, set(), match_state)
        assert len(match_state.totems) == 1

        # Place searing totem at different tile
        searing_def = get_skill("searing_totem")
        action2 = _make_action(skill_id="searing_totem", target_x=3, target_y=5)
        resolve_place_totem(player, action2, searing_def, players, set(), match_state)

        assert len(match_state.totems) == 2
        types = {t["type"] for t in match_state.totems}
        assert "healing_totem" in types
        assert "searing_totem" in types

    def test_searing_totem_via_dispatcher(self, loaded_skills):
        """Searing Totem resolves correctly through resolve_skill_action dispatcher."""
        player = _make_player(x=5, y=5)
        action = _make_action(skill_id="searing_totem", target_x=7, target_y=5)
        skill_def = get_skill("searing_totem")
        players = {"shaman1": player}
        match_state = _make_match_state()

        result = resolve_skill_action(
            player, action, skill_def, players, set(), 20, 20,
            match_state=match_state,
        )

        assert result.success is True
        assert len(match_state.totems) == 1
        assert match_state.totems[0]["type"] == "searing_totem"


# ============================================================
# 3. Soul Anchor Tests
# ============================================================

class TestSoulAnchor:
    """Tests for resolve_soul_anchor() handler."""

    def test_soul_anchor_applies_buff_to_ally(self, loaded_skills):
        """Soul Anchor applies soul_anchor buff to a target ally."""
        player = _make_player(x=5, y=5)
        ally = _make_ally(x=6, y=5)
        players = {"shaman1": player, "ally1": ally}
        action = _make_action(skill_id="soul_anchor", target_x=6, target_y=5, target_id="ally1")
        skill_def = get_skill("soul_anchor")

        result = resolve_soul_anchor(player, action, skill_def, players, target_id="ally1")

        assert result.success is True
        assert "anchored" in result.message
        assert result.target_id == "ally1"

        anchor_buffs = [b for b in ally.active_buffs if b.get("stat") == "soul_anchor"]
        assert len(anchor_buffs) == 1
        buff = anchor_buffs[0]
        assert buff["caster_id"] == "shaman1"
        assert buff["turns_remaining"] == 4
        assert buff["survive_hp"] == 1

    def test_soul_anchor_can_target_self(self, loaded_skills):
        """Soul Anchor can be cast on self."""
        player = _make_player(x=5, y=5)
        players = {"shaman1": player}
        action = _make_action(skill_id="soul_anchor", target_x=5, target_y=5, target_id="shaman1")
        skill_def = get_skill("soul_anchor")

        result = resolve_soul_anchor(player, action, skill_def, players, target_id="shaman1")

        assert result.success is True
        assert "self" in result.message
        anchor_buffs = [b for b in player.active_buffs if b.get("stat") == "soul_anchor"]
        assert len(anchor_buffs) == 1

    def test_soul_anchor_fails_on_enemy(self, loaded_skills):
        """Soul Anchor fails when targeting an enemy."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=6, y=5)
        players = {"shaman1": player, "enemy1": enemy}
        action = _make_action(skill_id="soul_anchor", target_x=6, target_y=5, target_id="enemy1")
        skill_def = get_skill("soul_anchor")

        result = resolve_soul_anchor(player, action, skill_def, players, target_id="enemy1")

        assert result.success is False
        assert "no valid target" in result.message

    def test_soul_anchor_fails_out_of_range(self, loaded_skills):
        """Soul Anchor fails on ally beyond range 4."""
        player = _make_player(x=5, y=5)
        ally = _make_ally(x=10, y=5)  # Distance 5 — beyond range 4
        players = {"shaman1": player, "ally1": ally}
        action = _make_action(skill_id="soul_anchor", target_x=10, target_y=5, target_id="ally1")
        skill_def = get_skill("soul_anchor")

        result = resolve_soul_anchor(player, action, skill_def, players, target_id="ally1")

        assert result.success is False
        assert "out of range" in result.message

    def test_soul_anchor_replaces_previous(self, loaded_skills):
        """A second Soul Anchor replaces the first (max 1 active per Shaman)."""
        player = _make_player(x=5, y=5)
        ally1 = _make_ally(player_id="ally1", username="Ally1", x=6, y=5)
        ally2 = _make_ally(player_id="ally2", username="Ally2", x=4, y=5)
        players = {"shaman1": player, "ally1": ally1, "ally2": ally2}
        skill_def = get_skill("soul_anchor")

        # Anchor ally1
        action1 = _make_action(skill_id="soul_anchor", target_x=6, target_y=5, target_id="ally1")
        resolve_soul_anchor(player, action1, skill_def, players, target_id="ally1")
        assert len([b for b in ally1.active_buffs if b.get("stat") == "soul_anchor"]) == 1

        # Reset cooldown
        player.cooldowns["soul_anchor"] = 0

        # Anchor ally2 — should remove from ally1
        action2 = _make_action(skill_id="soul_anchor", target_x=4, target_y=5, target_id="ally2")
        resolve_soul_anchor(player, action2, skill_def, players, target_id="ally2")

        assert len([b for b in ally1.active_buffs if b.get("stat") == "soul_anchor"]) == 0
        assert len([b for b in ally2.active_buffs if b.get("stat") == "soul_anchor"]) == 1

    def test_soul_anchor_buff_correct_fields(self, loaded_skills):
        """Soul Anchor buff stores correct caster_id and duration."""
        player = _make_player(x=5, y=5)
        ally = _make_ally(x=6, y=5)
        players = {"shaman1": player, "ally1": ally}
        action = _make_action(skill_id="soul_anchor", target_x=6, target_y=5, target_id="ally1")
        skill_def = get_skill("soul_anchor")

        resolve_soul_anchor(player, action, skill_def, players, target_id="ally1")

        buff = next(b for b in ally.active_buffs if b.get("stat") == "soul_anchor")
        assert buff["buff_id"] == "soul_anchor"
        assert buff["type"] == "soul_anchor"
        assert buff["stat"] == "soul_anchor"
        assert buff["caster_id"] == "shaman1"
        assert buff["turns_remaining"] == 4
        assert buff["survive_hp"] == 1
        assert buff["magnitude"] == 0

    def test_soul_anchor_sets_cooldown(self, loaded_skills):
        """Soul Anchor sets cooldown to 10."""
        player = _make_player(x=5, y=5)
        ally = _make_ally(x=6, y=5)
        players = {"shaman1": player, "ally1": ally}
        action = _make_action(skill_id="soul_anchor", target_x=6, target_y=5, target_id="ally1")
        skill_def = get_skill("soul_anchor")

        resolve_soul_anchor(player, action, skill_def, players, target_id="ally1")

        assert player.cooldowns.get("soul_anchor", 0) == 10

    def test_soul_anchor_result_contains_buff_info(self, loaded_skills):
        """ActionResult includes buff_applied with soul anchor details."""
        player = _make_player(x=5, y=5)
        ally = _make_ally(x=6, y=5)
        players = {"shaman1": player, "ally1": ally}
        action = _make_action(skill_id="soul_anchor", target_x=6, target_y=5, target_id="ally1")
        skill_def = get_skill("soul_anchor")

        result = resolve_soul_anchor(player, action, skill_def, players, target_id="ally1")

        assert result.buff_applied is not None
        assert result.buff_applied["type"] == "soul_anchor"
        assert result.buff_applied["survive_hp"] == 1
        assert result.buff_applied["duration"] == 4

    def test_soul_anchor_via_dispatcher(self, loaded_skills):
        """Soul Anchor resolves correctly through resolve_skill_action dispatcher."""
        player = _make_player(x=5, y=5)
        ally = _make_ally(x=6, y=5)
        players = {"shaman1": player, "ally1": ally}
        action = _make_action(skill_id="soul_anchor", target_x=6, target_y=5, target_id="ally1")
        skill_def = get_skill("soul_anchor")

        result = resolve_skill_action(
            player, action, skill_def, players, set(), 20, 20,
        )

        assert result.success is True
        assert any(b.get("stat") == "soul_anchor" for b in ally.active_buffs)


# ============================================================
# 4. Earthgrasp (aoe_root) Tests
# ============================================================

class TestEarthgrasp:
    """Tests for resolve_aoe_root() handler."""

    def test_earthgrasp_roots_enemies_in_radius(self, loaded_skills):
        """Earthgrasp applies rooted debuff to all enemies within radius 2."""
        player = _make_player(x=5, y=5)
        enemy1 = _make_enemy(player_id="e1", username="Enemy1", x=8, y=5)  # Within radius 2 of (7,5)
        enemy2 = _make_enemy(player_id="e2", username="Enemy2", x=7, y=6)  # Within radius 2 of (7,5)
        players = {"shaman1": player, "e1": enemy1, "e2": enemy2}
        action = _make_action(skill_id="earthgrasp", target_x=7, target_y=5)
        skill_def = get_skill("earthgrasp")

        result = resolve_aoe_root(player, action, skill_def, players, set())

        assert result.success is True
        assert "rooted" in result.message
        assert "2 enemies" in result.message

        # Both enemies should have rooted debuff
        for enemy in [enemy1, enemy2]:
            rooted = [b for b in enemy.active_buffs if b.get("stat") == "rooted"]
            assert len(rooted) == 1
            assert rooted[0]["turns_remaining"] == 2

    def test_earthgrasp_does_not_root_allies(self, loaded_skills):
        """Earthgrasp does not root allies in the area."""
        player = _make_player(x=5, y=5)
        ally = _make_ally(x=7, y=5)  # At the center of the AoE
        enemy = _make_enemy(x=8, y=5)  # Within radius
        players = {"shaman1": player, "ally1": ally, "enemy1": enemy}
        action = _make_action(skill_id="earthgrasp", target_x=7, target_y=5)
        skill_def = get_skill("earthgrasp")

        result = resolve_aoe_root(player, action, skill_def, players, set())

        assert result.success is True
        # Ally should NOT be rooted
        assert not any(b.get("stat") == "rooted" for b in ally.active_buffs)
        # Enemy should be rooted
        assert any(b.get("stat") == "rooted" for b in enemy.active_buffs)

    def test_earthgrasp_requires_los(self, loaded_skills):
        """Earthgrasp fails when LOS to target tile is blocked."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=8, y=5)
        players = {"shaman1": player, "enemy1": enemy}
        obstacles = {(6, 5), (7, 5)}  # Block LOS
        action = _make_action(skill_id="earthgrasp", target_x=8, target_y=5)
        skill_def = get_skill("earthgrasp")

        result = resolve_aoe_root(player, action, skill_def, players, obstacles)

        assert result.success is False
        assert "line of sight" in result.message

    def test_earthgrasp_fails_out_of_range(self, loaded_skills):
        """Earthgrasp fails when target tile is beyond range 4."""
        player = _make_player(x=5, y=5)
        players = {"shaman1": player}
        action = _make_action(skill_id="earthgrasp", target_x=10, target_y=5)  # Distance 5
        skill_def = get_skill("earthgrasp")

        result = resolve_aoe_root(player, action, skill_def, players, set())

        assert result.success is False
        assert "out of range" in result.message

    def test_earthgrasp_rooted_debuff_correct_fields(self, loaded_skills):
        """Rooted debuff has correct duration (2 turns) and fields."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=7, y=5)
        players = {"shaman1": player, "enemy1": enemy}
        action = _make_action(skill_id="earthgrasp", target_x=7, target_y=5)
        skill_def = get_skill("earthgrasp")

        resolve_aoe_root(player, action, skill_def, players, set())

        buff = next(b for b in enemy.active_buffs if b.get("stat") == "rooted")
        assert buff["buff_id"] == "earthgrasp"
        assert buff["type"] == "aoe_root"
        assert buff["stat"] == "rooted"
        assert buff["source_id"] == "shaman1"
        assert buff["turns_remaining"] == 2
        assert buff["magnitude"] == 0

    def test_earthgrasp_sets_cooldown(self, loaded_skills):
        """Earthgrasp sets cooldown to 7."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=7, y=5)
        players = {"shaman1": player, "enemy1": enemy}
        action = _make_action(skill_id="earthgrasp", target_x=7, target_y=5)
        skill_def = get_skill("earthgrasp")

        resolve_aoe_root(player, action, skill_def, players, set())

        assert player.cooldowns.get("earthgrasp", 0) == 7

    def test_earthgrasp_multiple_enemies(self, loaded_skills):
        """Multiple enemies can be rooted in a single cast."""
        player = _make_player(x=5, y=5)
        enemy1 = _make_enemy(player_id="e1", username="Orc1", x=7, y=5)
        enemy2 = _make_enemy(player_id="e2", username="Orc2", x=8, y=5)
        enemy3 = _make_enemy(player_id="e3", username="Orc3", x=7, y=6)
        players = {"shaman1": player, "e1": enemy1, "e2": enemy2, "e3": enemy3}
        action = _make_action(skill_id="earthgrasp", target_x=7, target_y=5)
        skill_def = get_skill("earthgrasp")

        result = resolve_aoe_root(player, action, skill_def, players, set())

        assert result.success is True
        assert result.buff_applied["rooted_count"] == 3
        for e in [enemy1, enemy2, enemy3]:
            assert any(b.get("stat") == "rooted" for b in e.active_buffs)

    def test_earthgrasp_no_enemies_in_range(self, loaded_skills):
        """Earthgrasp succeeds but roots 0 enemies when none are in radius."""
        player = _make_player(x=5, y=5)
        # Enemy far from target tile (7,5) — at (15,15), well out of radius 2
        enemy = _make_enemy(x=15, y=15)
        players = {"shaman1": player, "enemy1": enemy}
        action = _make_action(skill_id="earthgrasp", target_x=7, target_y=5)
        skill_def = get_skill("earthgrasp")

        result = resolve_aoe_root(player, action, skill_def, players, set())

        assert result.success is True
        assert result.buff_applied["rooted_count"] == 0
        assert "no enemies" in result.message

    def test_earthgrasp_fails_no_target(self, loaded_skills):
        """Earthgrasp fails when no target coordinates are provided."""
        player = _make_player(x=5, y=5)
        players = {"shaman1": player}
        action = _make_action(skill_id="earthgrasp", target_x=None, target_y=None)
        skill_def = get_skill("earthgrasp")

        result = resolve_aoe_root(player, action, skill_def, players, set())

        assert result.success is False
        assert "no target" in result.message

    def test_earthgrasp_refreshes_root_not_stacks(self, loaded_skills):
        """Recasting Earthgrasp on an already-rooted enemy refreshes the root."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=7, y=5)
        players = {"shaman1": player, "enemy1": enemy}
        skill_def = get_skill("earthgrasp")

        # Root once
        action1 = _make_action(skill_id="earthgrasp", target_x=7, target_y=5)
        resolve_aoe_root(player, action1, skill_def, players, set())
        assert len([b for b in enemy.active_buffs if b.get("stat") == "rooted"]) == 1

        # Reset cooldown
        player.cooldowns["earthgrasp"] = 0

        # Root again — should still only have 1 rooted debuff (refreshed)
        action2 = _make_action(skill_id="earthgrasp", target_x=7, target_y=5)
        resolve_aoe_root(player, action2, skill_def, players, set())

        rooted_buffs = [b for b in enemy.active_buffs if b.get("stat") == "rooted"]
        assert len(rooted_buffs) == 1
        assert rooted_buffs[0]["turns_remaining"] == 2  # Refreshed to full

    def test_earthgrasp_via_dispatcher(self, loaded_skills):
        """Earthgrasp resolves correctly through resolve_skill_action dispatcher."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=7, y=5)
        players = {"shaman1": player, "enemy1": enemy}
        action = _make_action(skill_id="earthgrasp", target_x=7, target_y=5)
        skill_def = get_skill("earthgrasp")

        result = resolve_skill_action(
            player, action, skill_def, players, set(), 20, 20,
        )

        assert result.success is True
        assert any(b.get("stat") == "rooted" for b in enemy.active_buffs)

    def test_earthgrasp_enemy_outside_radius_not_rooted(self, loaded_skills):
        """Enemy just outside radius 2 is NOT rooted."""
        player = _make_player(x=5, y=5)
        # Target tile (7,5), enemy at (10, 5) — distance 3 from target, outside radius 2
        enemy = _make_enemy(x=10, y=5)
        players = {"shaman1": player, "enemy1": enemy}
        action = _make_action(skill_id="earthgrasp", target_x=7, target_y=5)
        skill_def = get_skill("earthgrasp")

        result = resolve_aoe_root(player, action, skill_def, players, set())

        assert result.success is True
        assert result.buff_applied["rooted_count"] == 0
        assert not any(b.get("stat") == "rooted" for b in enemy.active_buffs)

    def test_earthgrasp_ignores_dead_enemies(self, loaded_skills):
        """Earthgrasp does not root dead enemies."""
        player = _make_player(x=5, y=5)
        dead_enemy = _make_enemy(x=7, y=5, alive=False)
        players = {"shaman1": player, "enemy1": dead_enemy}
        action = _make_action(skill_id="earthgrasp", target_x=7, target_y=5)
        skill_def = get_skill("earthgrasp")

        result = resolve_aoe_root(player, action, skill_def, players, set())

        assert result.success is True
        assert result.buff_applied["rooted_count"] == 0
