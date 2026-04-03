"""Tests for Phase 25B: Revenant effect handlers (Phase 25R rework).

Covers:
- Death's Embrace (deaths_embrace_buff): self-buff applies thorns_damage (8) + armor (+2) +
  heal_on_hit_taken (3), sets cooldown (5), buff expires after duration (4), refreshes on recast
- Grasp of the Grave (ranged_root): roots enemy within range 4, respects LOS,
  fails on ally/out-of-range, root lasts 1 turn (2 empowered below 50% HP), sets cooldown (4)
- Undying Fury (undying_fury): applies cheat_death buff with revive_hp_pct 0.25,
  activation window 5, fury duration 3, sets cooldown (12), buff expires if not triggered
- Soul Rend (melee_damage_conditional_bleed): deals 1.3× melee damage to adjacent enemy
  (1.8× + bleed below 50% HP), respects armor, min damage 1, sets cooldown (3)
"""

from __future__ import annotations

import math

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType, ActionResult
from app.core.skills import (
    load_skills_config,
    clear_skills_cache,
    get_skill,
    resolve_skill_action,
    resolve_deaths_embrace,
    resolve_ranged_root,
    resolve_undying_fury,
    resolve_melee_damage_conditional_bleed,
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
    player_id: str = "rev1",
    username: str = "TestRevenant",
    class_id: str = "revenant",
    hp: int = 130,
    max_hp: int = 130,
    attack_damage: int = 14,
    ranged_damage: int = 0,
    armor: int = 5,
    alive: bool = True,
    cooldowns: dict | None = None,
    team: str = "team_1",
    x: int = 5,
    y: int = 5,
    buffs: list | None = None,
) -> PlayerState:
    """Helper — create a PlayerState with the given attributes."""
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


def _make_enemy(
    player_id: str = "enemy1",
    username: str = "TestEnemy",
    class_id: str = "ranger",
    hp: int = 80,
    max_hp: int = 80,
    attack_damage: int = 8,
    armor: int = 2,
    team: str = "team_2",
    x: int = 6,
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
    player_id: str = "rev1",
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


# ============================================================
# 1. Death's Embrace (deaths_embrace_buff) Tests
# ============================================================

class TestDeathsEmbrace:
    """Tests for resolve_deaths_embrace() handler."""

    def test_deaths_embrace_applies_correctly(self, loaded_skills):
        """Death's Embrace applies three buff components: thorns(8), armor(+2), heal_on_hit(3) for 4 turns."""
        player = _make_player()
        skill_def = get_skill("deaths_embrace")
        result = resolve_deaths_embrace(player, skill_def)

        assert result.success is True
        assert "Death's Embrace" in result.message

        # Check 3 buff components were applied
        embrace_buffs = [b for b in player.active_buffs if b.get("buff_id") == "deaths_embrace"]
        assert len(embrace_buffs) == 3
        stats = {b["stat"]: b["magnitude"] for b in embrace_buffs}
        assert stats["thorns_damage"] == 8
        assert stats["armor"] == 2
        assert stats["heal_on_hit_taken"] == 3
        for b in embrace_buffs:
            assert b["turns_remaining"] == 4

    def test_deaths_embrace_sets_cooldown(self, loaded_skills):
        """Death's Embrace sets cooldown to 5."""
        player = _make_player()
        skill_def = get_skill("deaths_embrace")
        resolve_deaths_embrace(player, skill_def)

        assert player.cooldowns.get("deaths_embrace", 0) == 5

    def test_deaths_embrace_refreshes_not_stacks(self, loaded_skills):
        """Recasting Death's Embrace refreshes the buff instead of stacking."""
        player = _make_player()
        skill_def = get_skill("deaths_embrace")

        # Apply once
        resolve_deaths_embrace(player, skill_def)
        assert len([b for b in player.active_buffs if b.get("buff_id") == "deaths_embrace"]) == 3

        # Reset cooldown to allow recast
        player.cooldowns["deaths_embrace"] = 0

        # Apply again
        resolve_deaths_embrace(player, skill_def)
        embrace_buffs = [b for b in player.active_buffs if b.get("buff_id") == "deaths_embrace"]
        assert len(embrace_buffs) == 3  # Still 3, not 6
        for b in embrace_buffs:
            assert b["turns_remaining"] == 4  # Refreshed

    def test_deaths_embrace_result_contains_buff_info(self, loaded_skills):
        """ActionResult includes buff_applied with embrace details."""
        player = _make_player()
        skill_def = get_skill("deaths_embrace")
        result = resolve_deaths_embrace(player, skill_def)

        assert result.buff_applied is not None
        assert result.buff_applied["type"] == "deaths_embrace"
        assert result.buff_applied["thorns_damage"] == 8
        assert result.buff_applied["armor_bonus"] == 2
        assert result.buff_applied["heal_on_hit_taken"] == 3
        assert result.buff_applied["duration"] == 4

    def test_deaths_embrace_via_dispatcher(self, loaded_skills):
        """Death's Embrace resolves correctly through resolve_skill_action dispatcher."""
        player = _make_player()
        action = _make_action(skill_id="deaths_embrace")
        skill_def = get_skill("deaths_embrace")
        players = {"rev1": player}

        result = resolve_skill_action(player, action, skill_def, players, set(), 20, 20)
        assert result.success is True
        assert any(b.get("buff_id") == "deaths_embrace" for b in player.active_buffs)


# ============================================================
# 2. Grasp of the Grave (ranged_root) Tests
# ============================================================

class TestGraspOfTheGrave:
    """Tests for resolve_ranged_root() handler."""

    def test_ranged_root_applies_to_enemy_in_range(self, loaded_skills):
        """Grasp of the Grave roots enemy within range 4 for 1 turn."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=7, y=5)  # Distance 2 — within range 4
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("grasp_of_the_grave")

        result = resolve_ranged_root(
            player, enemy.position.x, enemy.position.y,
            skill_def, players, set(), target_id="enemy1",
        )

        assert result.success is True
        assert "rooted" in result.message.lower()
        assert result.target_id == "enemy1"

        # Check root debuff on enemy
        root_buffs = [b for b in enemy.active_buffs if b.get("stat") == "rooted"]
        assert len(root_buffs) == 1
        assert root_buffs[0]["source_id"] == "rev1"
        assert root_buffs[0]["turns_remaining"] == 1

    def test_ranged_root_empowered_duration(self, loaded_skills):
        """Grasp of the Grave roots for 2 turns when caster is below 50% HP."""
        player = _make_player(x=5, y=5, hp=60, max_hp=130)  # ~46% HP — below 50%
        enemy = _make_enemy(x=7, y=5)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("grasp_of_the_grave")

        resolve_ranged_root(player, None, None, skill_def, players, set(), target_id="enemy1")
        root = next(b for b in enemy.active_buffs if b.get("stat") == "rooted")
        assert root["turns_remaining"] == 2

    def test_ranged_root_requires_los(self, loaded_skills):
        """Grasp of the Grave fails when line of sight is blocked."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=8, y=5)  # Distance 3 — within range
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("grasp_of_the_grave")
        # Block LOS with walls between them
        obstacles = {(6, 5), (7, 5)}

        result = resolve_ranged_root(
            player, None, None, skill_def, players, obstacles, target_id="enemy1",
        )
        assert result.success is False
        assert "line of sight" in result.message.lower()

    def test_ranged_root_fails_on_ally(self, loaded_skills):
        """Grasp of the Grave fails when targeting an ally (same team)."""
        player = _make_player(x=5, y=5)
        ally = _make_enemy(player_id="ally1", username="Ally", x=6, y=5, team="team_1")
        players = {"rev1": player, "ally1": ally}
        skill_def = get_skill("grasp_of_the_grave")

        result = resolve_ranged_root(
            player, None, None, skill_def, players, set(), target_id="ally1",
        )
        assert result.success is False
        assert "no target specified" in result.message.lower() or "no enemy" in result.message.lower()

    def test_ranged_root_fails_out_of_range(self, loaded_skills):
        """Grasp of the Grave fails when target is beyond range 4."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=10, y=5)  # Distance 5 — beyond range 4
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("grasp_of_the_grave")

        result = resolve_ranged_root(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )
        assert result.success is False
        assert "out of range" in result.message.lower()

    def test_ranged_root_sets_cooldown(self, loaded_skills):
        """Grasp of the Grave sets cooldown to 4."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=6, y=5)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("grasp_of_the_grave")

        resolve_ranged_root(player, None, None, skill_def, players, set(), target_id="enemy1")
        assert player.cooldowns.get("grasp_of_the_grave", 0) == 4

    def test_ranged_root_refreshes_existing(self, loaded_skills):
        """Recasting Grasp of the Grave on same target refreshes the root."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=6, y=5)
        # Pre-apply a root with 0 turns remaining (about to expire)
        enemy.active_buffs.append({
            "buff_id": "grasp_of_the_grave", "type": "ranged_root",
            "source_id": "rev1", "turns_remaining": 0,
            "stat": "rooted", "magnitude": 0,
        })
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("grasp_of_the_grave")

        resolve_ranged_root(player, None, None, skill_def, players, set(), target_id="enemy1")
        root_buffs = [b for b in enemy.active_buffs if b.get("stat") == "rooted"]
        assert len(root_buffs) == 1
        assert root_buffs[0]["turns_remaining"] == 1  # Refreshed

    def test_ranged_root_via_dispatcher(self, loaded_skills):
        """Grasp of the Grave resolves correctly through resolve_skill_action dispatcher."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=7, y=5)
        players = {"rev1": player, "enemy1": enemy}
        action = _make_action(skill_id="grasp_of_the_grave", target_id="enemy1")
        skill_def = get_skill("grasp_of_the_grave")

        result = resolve_skill_action(player, action, skill_def, players, set(), 20, 20)
        assert result.success is True
        assert any(b.get("stat") == "rooted" for b in enemy.active_buffs)

    def test_ranged_root_fails_on_dead_target(self, loaded_skills):
        """Grasp of the Grave fails when target is dead."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=6, y=5, alive=False)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("grasp_of_the_grave")

        result = resolve_ranged_root(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )
        assert result.success is False


# ============================================================
# 3. Undying Fury (undying_fury) Tests
# ============================================================

class TestUndyingFury:
    """Tests for resolve_undying_fury() handler."""

    def test_undying_fury_applies_buff(self, loaded_skills):
        """Undying Fury applies undying_fury buff with activation window 5."""
        player = _make_player()
        skill_def = get_skill("undying_fury")
        result = resolve_undying_fury(player, skill_def)

        assert result.success is True
        assert "Undying Fury" in result.message
        assert "25%" in result.message

        cd_buffs = [b for b in player.active_buffs if b.get("stat") == "cheat_death"]
        assert len(cd_buffs) == 1
        buff = cd_buffs[0]
        assert buff["revive_hp_pct"] == 0.25
        assert buff["turns_remaining"] == 5
        assert buff["type"] == "undying_fury"
        assert buff["buff_id"] == "undying_fury"

    def test_undying_fury_sets_cooldown(self, loaded_skills):
        """Undying Fury sets cooldown to 12."""
        player = _make_player()
        skill_def = get_skill("undying_fury")
        resolve_undying_fury(player, skill_def)

        assert player.cooldowns.get("undying_fury", 0) == 12

    def test_undying_fury_buff_has_revive_pct(self, loaded_skills):
        """Undying fury buff stores revive_hp_pct = 0.25."""
        player = _make_player()
        skill_def = get_skill("undying_fury")
        resolve_undying_fury(player, skill_def)

        buff = next(b for b in player.active_buffs if b.get("stat") == "cheat_death")
        assert buff["revive_hp_pct"] == 0.25

    def test_undying_fury_refreshes_not_stacks(self, loaded_skills):
        """Recasting Undying Fury refreshes the buff, doesn't stack."""
        player = _make_player()
        skill_def = get_skill("undying_fury")

        resolve_undying_fury(player, skill_def)
        player.cooldowns["undying_fury"] = 0
        resolve_undying_fury(player, skill_def)

        cd_buffs = [b for b in player.active_buffs if b.get("stat") == "cheat_death"]
        assert len(cd_buffs) == 1
        assert cd_buffs[0]["turns_remaining"] == 5

    def test_undying_fury_result_contains_buff_info(self, loaded_skills):
        """ActionResult includes buff_applied with undying_fury details."""
        player = _make_player()
        skill_def = get_skill("undying_fury")
        result = resolve_undying_fury(player, skill_def)

        assert result.buff_applied is not None
        assert result.buff_applied["type"] == "undying_fury"
        assert result.buff_applied["revive_hp_pct"] == 0.25
        assert result.buff_applied["activation_window"] == 5
        assert result.buff_applied["fury_duration"] == 3

    def test_undying_fury_via_dispatcher(self, loaded_skills):
        """Undying Fury resolves correctly through resolve_skill_action dispatcher."""
        player = _make_player()
        action = _make_action(skill_id="undying_fury")
        skill_def = get_skill("undying_fury")
        players = {"rev1": player}

        result = resolve_skill_action(player, action, skill_def, players, set(), 20, 20)
        assert result.success is True
        assert any(b.get("stat") == "cheat_death" for b in player.active_buffs)


# ============================================================
# 4. Soul Rend (melee_damage_conditional_bleed) Tests
# ============================================================

class TestSoulRend:
    """Tests for resolve_melee_damage_conditional_bleed() handler."""

    def test_soul_rend_deals_damage_to_adjacent_enemy(self, loaded_skills):
        """Soul Rend deals 1.3× melee damage to adjacent enemy."""
        player = _make_player(x=5, y=5, attack_damage=16, armor=6)
        enemy = _make_enemy(x=6, y=5, hp=80, armor=2)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_conditional_bleed(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )

        assert result.success is True
        assert result.damage_dealt is not None
        assert result.damage_dealt > 0
        # Expected: floor(16 * 1.3) = 20, minus 2 armor = 18
        assert result.damage_dealt == 18
        assert enemy.hp == 80 - 18  # 62

    def test_soul_rend_applies_bleed_when_empowered(self, loaded_skills):
        """Soul Rend applies bleed (5/turn, 3 turns) when caster is below 50% HP."""
        player = _make_player(x=5, y=5, hp=60, max_hp=130)  # ~46% — empowered
        enemy = _make_enemy(x=6, y=5, hp=80, armor=2)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_conditional_bleed(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )

        bleed_buffs = [b for b in enemy.active_buffs if b.get("type") == "dot" and b.get("buff_id") == "soul_rend_bleed"]
        assert len(bleed_buffs) == 1
        assert bleed_buffs[0]["damage_per_tick"] == 5
        assert bleed_buffs[0]["turns_remaining"] == 3
        assert bleed_buffs[0]["source_id"] == "rev1"

    def test_soul_rend_no_bleed_above_50_hp(self, loaded_skills):
        """Soul Rend does NOT apply bleed when caster is above 50% HP."""
        player = _make_player(x=5, y=5, hp=100, max_hp=130)  # ~77% — NOT empowered
        enemy = _make_enemy(x=6, y=5, hp=80, armor=2)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        resolve_melee_damage_conditional_bleed(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )

        bleed_buffs = [b for b in enemy.active_buffs if b.get("type") == "dot" and b.get("buff_id") == "soul_rend_bleed"]
        assert len(bleed_buffs) == 0

    def test_soul_rend_empowered_multiplier(self, loaded_skills):
        """Soul Rend deals 1.8× damage when caster is below 50% HP."""
        player = _make_player(x=5, y=5, attack_damage=16, hp=60, max_hp=130)  # empowered
        enemy = _make_enemy(x=6, y=5, hp=80, armor=2)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_conditional_bleed(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )

        # Expected: floor(16 * 1.8) = 28, minus 2 armor = 26
        assert result.damage_dealt == 26
        assert enemy.hp == 80 - 26  # 54

    def test_soul_rend_respects_armor(self, loaded_skills):
        """Soul Rend damage reduced by target's armor."""
        player = _make_player(x=5, y=5, attack_damage=16)
        enemy = _make_enemy(x=6, y=5, hp=80, armor=8)  # High armor
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_conditional_bleed(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )

        # Expected: floor(16 * 1.3) = 20, minus 8 armor = 12
        assert result.damage_dealt == 12
        assert enemy.hp == 68

    def test_soul_rend_minimum_damage_is_one(self, loaded_skills):
        """Soul Rend deals minimum 1 damage even with very high armor."""
        player = _make_player(x=5, y=5, attack_damage=16)
        enemy = _make_enemy(x=6, y=5, hp=80, armor=50)  # Absurdly high armor
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_conditional_bleed(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )

        assert result.damage_dealt == 1
        assert enemy.hp == 79

    def test_soul_rend_fails_non_adjacent(self, loaded_skills):
        """Soul Rend fails when target is not adjacent."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=8, y=5)  # Distance 3 — not adjacent
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_conditional_bleed(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )

        assert result.success is False
        assert "not adjacent" in result.message.lower()

    def test_soul_rend_fails_on_self_position(self, loaded_skills):
        """Soul Rend fails when targeting own position (dx=0, dy=0)."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=5, y=5)  # Same position
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_conditional_bleed(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )

        assert result.success is False

    def test_soul_rend_sets_cooldown(self, loaded_skills):
        """Soul Rend sets cooldown to 3."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=6, y=5, hp=80, armor=2)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        resolve_melee_damage_conditional_bleed(player, None, None, skill_def, players, set(), target_id="enemy1")
        assert player.cooldowns.get("soul_rend", 0) == 3

    def test_soul_rend_can_kill_target(self, loaded_skills):
        """Soul Rend can kill the target (HP → 0, is_alive → False)."""
        player = _make_player(x=5, y=5, attack_damage=16)
        enemy = _make_enemy(x=6, y=5, hp=5, armor=0)  # Very low HP
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_conditional_bleed(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )

        assert result.success is True
        assert result.killed is True
        assert enemy.hp == 0
        assert enemy.is_alive is False

    def test_soul_rend_no_bleed_if_killed(self, loaded_skills):
        """Soul Rend does not apply bleed even if empowered when target was killed."""
        player = _make_player(x=5, y=5, attack_damage=16, hp=60, max_hp=130)  # empowered
        enemy = _make_enemy(x=6, y=5, hp=5, armor=0)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        resolve_melee_damage_conditional_bleed(player, None, None, skill_def, players, set(), target_id="enemy1")

        bleed_buffs = [b for b in enemy.active_buffs if b.get("type") == "dot" and b.get("buff_id") == "soul_rend_bleed"]
        assert len(bleed_buffs) == 0

    def test_soul_rend_fails_on_no_target(self, loaded_skills):
        """Soul Rend fails when no target is specified."""
        player = _make_player(x=5, y=5)
        players = {"rev1": player}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_conditional_bleed(
            player, None, None, skill_def, players, set(), target_id=None,
        )
        assert result.success is False

    def test_soul_rend_via_dispatcher(self, loaded_skills):
        """Soul Rend resolves correctly through resolve_skill_action dispatcher."""
        player = _make_player(x=5, y=5, attack_damage=16)
        enemy = _make_enemy(x=6, y=5, hp=80, armor=2)
        players = {"rev1": player, "enemy1": enemy}
        action = _make_action(skill_id="soul_rend", target_id="enemy1")
        skill_def = get_skill("soul_rend")

        result = resolve_skill_action(player, action, skill_def, players, set(), 20, 20)
        assert result.success is True
        assert result.damage_dealt > 0

    def test_soul_rend_diagonal_adjacent(self, loaded_skills):
        """Soul Rend works on diagonally adjacent targets (distance 1 Chebyshev)."""
        player = _make_player(x=5, y=5, attack_damage=16)
        enemy = _make_enemy(x=6, y=6, hp=80, armor=2)  # Diagonal
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_conditional_bleed(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )
        assert result.success is True
        assert result.damage_dealt > 0
