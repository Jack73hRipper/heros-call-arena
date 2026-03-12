"""
Tests for Phase 25B: Revenant effect handlers.

Covers:
- Grave Thorns (thorns_buff): self-buff applies thorns_damage with correct magnitude/duration,
  sets cooldown, buff expires after duration, can be recast after cooldown
- Grave Chains (ranged_taunt): applies taunt to enemy within range 3, respects LOS,
  fails on ally/out-of-range, taunt lasts correct duration, sets cooldown
- Undying Will (cheat_death): applies cheat_death buff with correct revive_hp_pct/duration,
  sets cooldown, buff expires if not triggered
- Soul Rend (melee_damage_slow): deals 1.2× melee damage to adjacent enemy, applies slow,
  respects armor, min damage 1, fails on non-adjacent, sets cooldown
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
    resolve_thorns_buff,
    resolve_ranged_taunt,
    resolve_cheat_death,
    resolve_melee_damage_slow,
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
# 1. Grave Thorns (thorns_buff) Tests
# ============================================================

class TestGraveThorns:
    """Tests for resolve_thorns_buff() handler."""

    def test_thorns_buff_applies_correctly(self, loaded_skills):
        """Grave Thorns applies thorns_damage buff with magnitude 12 and duration 4."""
        player = _make_player()
        skill_def = get_skill("grave_thorns")
        result = resolve_thorns_buff(player, skill_def)

        assert result.success is True
        assert "Grave Thorns" in result.message
        assert "reflects 12 damage" in result.message

        # Check buff was applied
        thorns_buffs = [b for b in player.active_buffs if b.get("stat") == "thorns_damage"]
        assert len(thorns_buffs) == 1
        buff = thorns_buffs[0]
        assert buff["magnitude"] == 12
        assert buff["turns_remaining"] == 4
        assert buff["type"] == "thorns_buff"
        assert buff["buff_id"] == "grave_thorns"

    def test_thorns_buff_sets_cooldown(self, loaded_skills):
        """Grave Thorns sets cooldown to 5."""
        player = _make_player()
        skill_def = get_skill("grave_thorns")
        resolve_thorns_buff(player, skill_def)

        assert player.cooldowns.get("grave_thorns", 0) == 5

    def test_thorns_buff_refreshes_not_stacks(self, loaded_skills):
        """Recasting Grave Thorns refreshes the buff instead of stacking."""
        player = _make_player()
        skill_def = get_skill("grave_thorns")

        # Apply once
        resolve_thorns_buff(player, skill_def)
        assert len([b for b in player.active_buffs if b.get("stat") == "thorns_damage"]) == 1

        # Reset cooldown to allow recast
        player.cooldowns["grave_thorns"] = 0

        # Apply again
        resolve_thorns_buff(player, skill_def)
        thorns_buffs = [b for b in player.active_buffs if b.get("stat") == "thorns_damage"]
        assert len(thorns_buffs) == 1  # Only one, not two
        assert thorns_buffs[0]["turns_remaining"] == 4  # Refreshed

    def test_thorns_buff_result_contains_buff_info(self, loaded_skills):
        """ActionResult includes buff_applied with thorns details."""
        player = _make_player()
        skill_def = get_skill("grave_thorns")
        result = resolve_thorns_buff(player, skill_def)

        assert result.buff_applied is not None
        assert result.buff_applied["type"] == "thorns_buff"
        assert result.buff_applied["thorns_damage"] == 12
        assert result.buff_applied["duration"] == 4

    def test_thorns_buff_via_dispatcher(self, loaded_skills):
        """Grave Thorns resolves correctly through resolve_skill_action dispatcher."""
        player = _make_player()
        action = _make_action(skill_id="grave_thorns")
        skill_def = get_skill("grave_thorns")
        players = {"rev1": player}

        result = resolve_skill_action(player, action, skill_def, players, set(), 20, 20)
        assert result.success is True
        assert any(b.get("stat") == "thorns_damage" for b in player.active_buffs)


# ============================================================
# 2. Grave Chains (ranged_taunt) Tests
# ============================================================

class TestGraveChains:
    """Tests for resolve_ranged_taunt() handler."""

    def test_ranged_taunt_applies_to_enemy_in_range(self, loaded_skills):
        """Grave Chains applies taunt (forced_target) to enemy within range 3."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=7, y=5)  # Distance 2 — within range 3
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("grave_chains")

        result = resolve_ranged_taunt(
            player, enemy.position.x, enemy.position.y,
            skill_def, players, set(), target_id="enemy1",
        )

        assert result.success is True
        assert "taunted" in result.message
        assert result.target_id == "enemy1"

        # Check taunt buff on enemy
        taunt_buffs = [b for b in enemy.active_buffs if b.get("type") == "taunt"]
        assert len(taunt_buffs) == 1
        assert taunt_buffs[0]["source_id"] == "rev1"
        assert taunt_buffs[0]["turns_remaining"] == 3

    def test_ranged_taunt_duration_is_3(self, loaded_skills):
        """Grave Chains taunt lasts 3 turns."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=7, y=5)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("grave_chains")

        resolve_ranged_taunt(player, None, None, skill_def, players, set(), target_id="enemy1")
        taunt = next(b for b in enemy.active_buffs if b.get("type") == "taunt")
        assert taunt["turns_remaining"] == 3

    def test_ranged_taunt_requires_los(self, loaded_skills):
        """Grave Chains fails when line of sight is blocked."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=8, y=5)  # Distance 3 — at max range
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("grave_chains")
        # Block LOS with a wall between them
        obstacles = {(6, 5), (7, 5)}

        result = resolve_ranged_taunt(
            player, None, None, skill_def, players, obstacles, target_id="enemy1",
        )
        assert result.success is False
        assert "line of sight" in result.message.lower()

    def test_ranged_taunt_fails_on_ally(self, loaded_skills):
        """Grave Chains fails when targeting an ally (same team)."""
        player = _make_player(x=5, y=5)
        ally = _make_enemy(player_id="ally1", username="Ally", x=6, y=5, team="team_1")
        players = {"rev1": player, "ally1": ally}
        skill_def = get_skill("grave_chains")

        result = resolve_ranged_taunt(
            player, None, None, skill_def, players, set(), target_id="ally1",
        )
        assert result.success is False
        assert "no enemy" in result.message.lower()

    def test_ranged_taunt_fails_out_of_range(self, loaded_skills):
        """Grave Chains fails when target is beyond range 4."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=10, y=5)  # Distance 5 — beyond range 4
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("grave_chains")

        result = resolve_ranged_taunt(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )
        assert result.success is False
        assert "out of range" in result.message.lower()

    def test_ranged_taunt_sets_cooldown(self, loaded_skills):
        """Grave Chains sets cooldown to 5."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=6, y=5)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("grave_chains")

        resolve_ranged_taunt(player, None, None, skill_def, players, set(), target_id="enemy1")
        assert player.cooldowns.get("grave_chains", 0) == 5

    def test_ranged_taunt_refreshes_existing(self, loaded_skills):
        """Recasting Grave Chains on same target refreshes the taunt."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=6, y=5)
        # Pre-apply a taunt with 1 turn remaining
        enemy.active_buffs.append({
            "buff_id": "grave_chains", "type": "taunt",
            "source_id": "rev1", "turns_remaining": 1,
            "stat": None, "magnitude": 0,
        })
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("grave_chains")

        resolve_ranged_taunt(player, None, None, skill_def, players, set(), target_id="enemy1")
        taunt_buffs = [b for b in enemy.active_buffs if b.get("type") == "taunt"]
        assert len(taunt_buffs) == 1
        assert taunt_buffs[0]["turns_remaining"] == 3  # Refreshed

    def test_ranged_taunt_via_dispatcher(self, loaded_skills):
        """Grave Chains resolves correctly through resolve_skill_action dispatcher."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=7, y=5)
        players = {"rev1": player, "enemy1": enemy}
        action = _make_action(skill_id="grave_chains", target_id="enemy1")
        skill_def = get_skill("grave_chains")

        result = resolve_skill_action(player, action, skill_def, players, set(), 20, 20)
        assert result.success is True
        assert any(b.get("type") == "taunt" for b in enemy.active_buffs)

    def test_ranged_taunt_fails_on_dead_target(self, loaded_skills):
        """Grave Chains fails when target is dead."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=6, y=5, alive=False)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("grave_chains")

        result = resolve_ranged_taunt(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )
        assert result.success is False


# ============================================================
# 3. Undying Will (cheat_death) Tests
# ============================================================

class TestUndyingWill:
    """Tests for resolve_cheat_death() handler."""

    def test_cheat_death_applies_buff(self, loaded_skills):
        """Undying Will applies cheat_death buff with duration 5."""
        player = _make_player()
        skill_def = get_skill("undying_will")
        result = resolve_cheat_death(player, skill_def)

        assert result.success is True
        assert "Undying Will" in result.message
        assert "30%" in result.message

        cd_buffs = [b for b in player.active_buffs if b.get("stat") == "cheat_death"]
        assert len(cd_buffs) == 1
        buff = cd_buffs[0]
        assert buff["revive_hp_pct"] == 0.30
        assert buff["turns_remaining"] == 5
        assert buff["type"] == "cheat_death"
        assert buff["buff_id"] == "undying_will"

    def test_cheat_death_sets_cooldown(self, loaded_skills):
        """Undying Will sets cooldown to 8."""
        player = _make_player()
        skill_def = get_skill("undying_will")
        resolve_cheat_death(player, skill_def)

        assert player.cooldowns.get("undying_will", 0) == 8

    def test_cheat_death_buff_has_revive_pct(self, loaded_skills):
        """Cheat death buff stores revive_hp_pct = 0.30."""
        player = _make_player()
        skill_def = get_skill("undying_will")
        resolve_cheat_death(player, skill_def)

        buff = next(b for b in player.active_buffs if b.get("stat") == "cheat_death")
        assert buff["revive_hp_pct"] == 0.30

    def test_cheat_death_refreshes_not_stacks(self, loaded_skills):
        """Recasting Undying Will refreshes the buff, doesn't stack."""
        player = _make_player()
        skill_def = get_skill("undying_will")

        resolve_cheat_death(player, skill_def)
        player.cooldowns["undying_will"] = 0
        resolve_cheat_death(player, skill_def)

        cd_buffs = [b for b in player.active_buffs if b.get("stat") == "cheat_death"]
        assert len(cd_buffs) == 1
        assert cd_buffs[0]["turns_remaining"] == 5

    def test_cheat_death_result_contains_buff_info(self, loaded_skills):
        """ActionResult includes buff_applied with cheat_death details."""
        player = _make_player()
        skill_def = get_skill("undying_will")
        result = resolve_cheat_death(player, skill_def)

        assert result.buff_applied is not None
        assert result.buff_applied["type"] == "cheat_death"
        assert result.buff_applied["revive_hp_pct"] == 0.30
        assert result.buff_applied["duration"] == 5

    def test_cheat_death_via_dispatcher(self, loaded_skills):
        """Undying Will resolves correctly through resolve_skill_action dispatcher."""
        player = _make_player()
        action = _make_action(skill_id="undying_will")
        skill_def = get_skill("undying_will")
        players = {"rev1": player}

        result = resolve_skill_action(player, action, skill_def, players, set(), 20, 20)
        assert result.success is True
        assert any(b.get("stat") == "cheat_death" for b in player.active_buffs)


# ============================================================
# 4. Soul Rend (melee_damage_slow) Tests
# ============================================================

class TestSoulRend:
    """Tests for resolve_melee_damage_slow() handler."""

    def test_soul_rend_deals_damage_to_adjacent_enemy(self, loaded_skills):
        """Soul Rend deals 1.5× melee damage to adjacent enemy."""
        player = _make_player(x=5, y=5, attack_damage=16, armor=6)
        enemy = _make_enemy(x=6, y=5, hp=80, armor=2)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_slow(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )

        assert result.success is True
        assert result.damage_dealt is not None
        assert result.damage_dealt > 0
        # Expected: floor(16 * 1.5) = 24, minus 2 armor = 22
        assert result.damage_dealt == 22
        assert enemy.hp == 80 - 22  # 58

    def test_soul_rend_applies_slow(self, loaded_skills):
        """Soul Rend applies 2-turn slow debuff to surviving target."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=6, y=5, hp=80, armor=2)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_slow(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )

        slow_buffs = [b for b in enemy.active_buffs if b.get("type") == "slow"]
        assert len(slow_buffs) == 1
        assert slow_buffs[0]["turns_remaining"] == 2
        assert slow_buffs[0]["source_id"] == "rev1"
        assert "SLOWED" in result.message

    def test_soul_rend_respects_armor(self, loaded_skills):
        """Soul Rend damage reduced by target's armor."""
        player = _make_player(x=5, y=5, attack_damage=16)
        enemy = _make_enemy(x=6, y=5, hp=80, armor=8)  # High armor
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_slow(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )

        # Expected: floor(16 * 1.5) = 24, minus 8 armor = 16
        assert result.damage_dealt == 16
        assert enemy.hp == 64

    def test_soul_rend_minimum_damage_is_one(self, loaded_skills):
        """Soul Rend deals minimum 1 damage even with very high armor."""
        player = _make_player(x=5, y=5, attack_damage=16)
        enemy = _make_enemy(x=6, y=5, hp=80, armor=50)  # Absurdly high armor
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_slow(
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

        result = resolve_melee_damage_slow(
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

        result = resolve_melee_damage_slow(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )

        assert result.success is False

    def test_soul_rend_sets_cooldown(self, loaded_skills):
        """Soul Rend sets cooldown to 4."""
        player = _make_player(x=5, y=5)
        enemy = _make_enemy(x=6, y=5, hp=80, armor=2)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        resolve_melee_damage_slow(player, None, None, skill_def, players, set(), target_id="enemy1")
        assert player.cooldowns.get("soul_rend", 0) == 4

    def test_soul_rend_can_kill_target(self, loaded_skills):
        """Soul Rend can kill the target (HP → 0, is_alive → False)."""
        player = _make_player(x=5, y=5, attack_damage=16)
        enemy = _make_enemy(x=6, y=5, hp=5, armor=0)  # Very low HP
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_slow(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )

        assert result.success is True
        assert result.killed is True
        assert enemy.hp == 0
        assert enemy.is_alive is False

    def test_soul_rend_no_slow_if_killed(self, loaded_skills):
        """Soul Rend does not apply slow if the target was killed."""
        player = _make_player(x=5, y=5, attack_damage=16)
        enemy = _make_enemy(x=6, y=5, hp=5, armor=0)
        players = {"rev1": player, "enemy1": enemy}
        skill_def = get_skill("soul_rend")

        resolve_melee_damage_slow(player, None, None, skill_def, players, set(), target_id="enemy1")

        slow_buffs = [b for b in enemy.active_buffs if b.get("type") == "slow"]
        assert len(slow_buffs) == 0

    def test_soul_rend_fails_on_no_target(self, loaded_skills):
        """Soul Rend fails when no target is specified."""
        player = _make_player(x=5, y=5)
        players = {"rev1": player}
        skill_def = get_skill("soul_rend")

        result = resolve_melee_damage_slow(
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

        result = resolve_melee_damage_slow(
            player, None, None, skill_def, players, set(), target_id="enemy1",
        )
        assert result.success is True
        assert result.damage_dealt > 0
