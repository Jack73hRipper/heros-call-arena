"""
Tests for Phase 25C: Revenant buff system integration.

Covers:
- Thorns damage reflection in melee combat (calculate_damage)
- Thorns damage reflection in ranged combat (calculate_ranged_damage)
- Thorns ignores attacker's armor (flat retaliation)
- Thorns can kill attacker (HP → 0)
- Thorns does not trigger when buff expired
- Multiple attackers each take thorns damage independently
- Thorns does not apply to skill damage (only auto-attacks)
- Cheat death revives player at 30% max HP instead of dying
- Cheat death buff is consumed after triggering
- Cheat death does not trigger if buff expired
- Cheat death HP calculation correct (floor of 30% × max_hp)
- Player without cheat_death dies normally (regression)
- Cheat death only triggers once (buff consumed)
- Cheat death revived player can act on following turns
- Buff tick-down works for thorns_damage and cheat_death
"""

from __future__ import annotations

import math

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType, ActionResult
from app.core.combat import (
    calculate_damage,
    calculate_ranged_damage,
    apply_damage,
    load_combat_config,
)
from app.core.turn_phases.deaths_phase import _resolve_deaths
from app.core.skills import (
    load_skills_config,
    clear_skills_cache,
    tick_buffs,
    resolve_thorns_buff,
    resolve_cheat_death,
    get_skill,
)


# ---------- Fixtures ----------


@pytest.fixture(autouse=True)
def _reset_caches():
    """Clear cached configs before each test to ensure isolation."""
    clear_skills_cache()
    load_combat_config()
    import app.models.player as player_mod
    player_mod._classes_cache = None
    yield
    clear_skills_cache()
    import app.models.player as player_mod2
    player_mod2._classes_cache = None


@pytest.fixture
def loaded_skills() -> dict:
    """Load and return the skills config dict."""
    return load_skills_config()


# ---------- Helpers ----------


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
    team: str = "team_1",
    x: int = 5,
    y: int = 5,
    buffs: list | None = None,
    thorns: int = 0,
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
        team=team,
        thorns=thorns,
    )
    if buffs:
        p.active_buffs = list(buffs)
    return p


def _make_attacker(
    player_id: str = "atk1",
    username: str = "TestAttacker",
    class_id: str = "ranger",
    hp: int = 80,
    max_hp: int = 80,
    attack_damage: int = 15,
    ranged_damage: int = 18,
    armor: int = 2,
    team: str = "team_2",
    x: int = 6,
    y: int = 5,
) -> PlayerState:
    """Helper — create an attacker PlayerState."""
    return PlayerState(
        player_id=player_id,
        username=username,
        position=Position(x=x, y=y),
        class_id=class_id,
        hp=hp,
        max_hp=max_hp,
        attack_damage=attack_damage,
        ranged_damage=ranged_damage,
        armor=armor,
        is_alive=True,
        team=team,
    )


def _apply_thorns_buff(player: PlayerState, magnitude: int = 12, duration: int = 4):
    """Apply a thorns_damage buff to a player (simulating Grave Thorns)."""
    thorns_entry = {
        "buff_id": "grave_thorns",
        "type": "thorns_buff",
        "stat": "thorns_damage",
        "magnitude": magnitude,
        "turns_remaining": duration,
    }
    player.active_buffs = [b for b in player.active_buffs if b.get("stat") != "thorns_damage"]
    player.active_buffs.append(thorns_entry)


def _apply_cheat_death_buff(player: PlayerState, revive_hp_pct: float = 0.30, duration: int = 5):
    """Apply a cheat_death buff to a player (simulating Undying Will)."""
    cheat_death_entry = {
        "buff_id": "undying_will",
        "type": "cheat_death",
        "stat": "cheat_death",
        "revive_hp_pct": revive_hp_pct,
        "turns_remaining": duration,
        "magnitude": 0,
    }
    player.active_buffs = [b for b in player.active_buffs if b.get("stat") != "cheat_death"]
    player.active_buffs.append(cheat_death_entry)


# ============================================================
# 1. Thorns Damage Reflection — Melee Combat
# ============================================================


class TestThornsMelee:
    """Tests for buff-based thorns damage in melee (calculate_damage)."""

    def test_attacker_takes_thorns_on_melee_hit(self):
        """Attacker takes 10 thorns damage when hitting a thorns-buffed target (melee)."""
        import random as _r
        rng = _r.Random(42)

        defender = _make_player(buffs=[])
        _apply_thorns_buff(defender, magnitude=10)
        attacker = _make_attacker(hp=80)

        damage, info = calculate_damage(attacker, defender, rng=rng)

        # Thorns should have triggered
        assert info["thorns_damage"] >= 10  # At least buff thorns
        # Attacker should have lost HP
        assert attacker.hp <= 80 - 10

    def test_thorns_ignores_attacker_armor(self):
        """Thorns damage ignores the attacker's armor — flat retaliation."""
        import random as _r
        rng = _r.Random(42)

        defender = _make_player(buffs=[])
        _apply_thorns_buff(defender, magnitude=10)
        # Attacker has high armor — shouldn't reduce thorns
        attacker = _make_attacker(hp=80, armor=20)

        initial_hp = attacker.hp
        damage, info = calculate_damage(attacker, defender, rng=rng)

        # Thorns damage should still be 10 regardless of attacker's armor
        assert info["thorns_damage"] >= 10
        hp_lost = initial_hp - attacker.hp
        assert hp_lost >= 10  # Thorns are flat, not reduced by armor

    def test_thorns_can_kill_attacker(self):
        """Thorns damage can kill the attacker (HP → 0)."""
        import random as _r
        rng = _r.Random(42)

        defender = _make_player(buffs=[])
        _apply_thorns_buff(defender, magnitude=15)
        attacker = _make_attacker(hp=5)  # Low HP — thorns will kill

        damage, info = calculate_damage(attacker, defender, rng=rng)

        assert attacker.hp == 0
        assert attacker.is_alive is False
        assert info["thorns_damage"] >= 15

    def test_thorns_does_not_trigger_without_buff(self):
        """No extra thorns damage if the defender has no thorns_damage buff."""
        import random as _r
        rng = _r.Random(42)

        defender = _make_player(buffs=[])  # No thorns buff
        attacker = _make_attacker(hp=80)

        initial_hp = attacker.hp
        damage, info = calculate_damage(attacker, defender, rng=rng)

        # Only equipment thorns (0 in this case) should apply
        assert info["thorns_damage"] == 0
        assert attacker.hp == initial_hp  # No thorns damage

    def test_thorns_stacks_with_equipment_thorns(self):
        """Buff thorns adds on top of equipment-based thorns."""
        import random as _r
        rng = _r.Random(42)

        defender = _make_player(buffs=[], thorns=5)  # 5 equipment thorns
        _apply_thorns_buff(defender, magnitude=10)
        attacker = _make_attacker(hp=80)

        initial_hp = attacker.hp
        damage, info = calculate_damage(attacker, defender, rng=rng)

        # Total thorns = 5 (equipment) + 10 (buff) = 15
        assert info["thorns_damage"] == 15
        assert attacker.hp == initial_hp - 15


# ============================================================
# 2. Thorns Damage Reflection — Ranged Combat
# ============================================================


class TestThornsRanged:
    """Tests for buff-based thorns damage in ranged (calculate_ranged_damage)."""

    def test_attacker_takes_thorns_on_ranged_hit(self):
        """Attacker takes 10 thorns damage when hitting a thorns-buffed target (ranged)."""
        import random as _r
        rng = _r.Random(42)

        defender = _make_player(buffs=[])
        _apply_thorns_buff(defender, magnitude=10)
        attacker = _make_attacker(hp=80, ranged_damage=18)

        initial_hp = attacker.hp
        damage, info = calculate_ranged_damage(attacker, defender, rng=rng)

        assert info["thorns_damage"] >= 10
        assert attacker.hp <= initial_hp - 10

    def test_ranged_thorns_can_kill_attacker(self):
        """Ranged thorns damage can kill the attacker."""
        import random as _r
        rng = _r.Random(42)

        defender = _make_player(buffs=[])
        _apply_thorns_buff(defender, magnitude=20)
        attacker = _make_attacker(hp=8, ranged_damage=18)

        damage, info = calculate_ranged_damage(attacker, defender, rng=rng)

        assert attacker.hp == 0
        assert attacker.is_alive is False

    def test_ranged_thorns_stacks_with_equipment(self):
        """Ranged buff thorns stacks with equipment thorns."""
        import random as _r
        rng = _r.Random(42)

        defender = _make_player(buffs=[], thorns=3)
        _apply_thorns_buff(defender, magnitude=10)
        attacker = _make_attacker(hp=80, ranged_damage=18)

        initial_hp = attacker.hp
        damage, info = calculate_ranged_damage(attacker, defender, rng=rng)

        assert info["thorns_damage"] == 13  # 3 + 10
        assert attacker.hp == initial_hp - 13


# ============================================================
# 3. Multiple Attackers Take Thorns Damage Independently
# ============================================================


class TestThornsMultipleAttackers:
    """Tests for independent thorns damage across multiple attackers."""

    def test_multiple_attackers_each_take_thorns(self):
        """Each attacker takes thorns damage independently from the same thorns buff."""
        import random as _r

        defender = _make_player(buffs=[])
        _apply_thorns_buff(defender, magnitude=10)

        attacker1 = _make_attacker(player_id="atk1", hp=80, x=6, y=5)
        attacker2 = _make_attacker(player_id="atk2", hp=60, x=4, y=5)
        attacker3 = _make_attacker(player_id="atk3", hp=50, x=5, y=6)

        rng1 = _r.Random(42)
        rng2 = _r.Random(43)
        rng3 = _r.Random(44)

        d1, info1 = calculate_damage(attacker1, defender, rng=rng1)
        d2, info2 = calculate_damage(attacker2, defender, rng=rng2)
        d3, info3 = calculate_damage(attacker3, defender, rng=rng3)

        # Each attacker should have taken thorns damage independently
        assert info1["thorns_damage"] >= 10
        assert info2["thorns_damage"] >= 10
        assert info3["thorns_damage"] >= 10
        assert attacker1.hp <= 80 - 10
        assert attacker2.hp <= 60 - 10
        assert attacker3.hp <= 50 - 10


# ============================================================
# 4. Thorns Does Not Apply to Skill Damage
# ============================================================


class TestThornsSkillDamage:
    """Tests that thorns does not trigger from skill damage (only auto-attacks)."""

    def test_soul_rend_does_not_trigger_thorns(self, loaded_skills):
        """Soul Rend (melee_damage_slow skill) does not trigger buff-based thorns.

        Buff thorns only trigger in calculate_damage/calculate_ranged_damage
        (auto-attacks), not in skill handler damage calculations.
        """
        from app.core.skills import resolve_melee_damage_slow

        defender = _make_player(
            player_id="enemy1", username="ThornsDefender",
            class_id="crusader", hp=100, max_hp=100,
            attack_damage=15, armor=5, team="team_2", x=6, y=5,
            buffs=[],
        )
        _apply_thorns_buff(defender, magnitude=10)

        attacker = _make_attacker(player_id="atk1", hp=80, x=5, y=5)
        skill_def = get_skill("soul_rend")

        players = {"atk1": attacker, "enemy1": defender}

        result = resolve_melee_damage_slow(
            attacker, 6, 5, skill_def, players, set(),
            target_id="enemy1",
        )

        # Attacker should NOT have taken thorns damage from the skill
        assert attacker.hp == 80  # No thorns reflection from skill damage


# ============================================================
# 5. Cheat Death — deaths_phase.py Integration
# ============================================================


class TestCheatDeath:
    """Tests for cheat death buff integration in the deaths phase."""

    def test_cheat_death_revives_at_30_pct(self):
        """Player with cheat_death buff revives at 30% max HP instead of dying."""
        player = _make_player(hp=0, max_hp=130, alive=False)
        _apply_cheat_death_buff(player)
        
        players = {"rev1": player}
        deaths = ["rev1"]
        results: list[ActionResult] = []
        loot_drops: list[dict] = []

        _resolve_deaths("test_match", deaths, players, None, results, loot_drops)

        # Player should be alive
        assert player.is_alive is True
        # HP = floor(130 * 0.30) = 39
        expected_hp = math.floor(130 * 0.30)
        assert player.hp == expected_hp
        # Should be removed from deaths list
        assert "rev1" not in deaths
        # Should have a revive message in results
        revive_msgs = [r for r in results if "defies death" in r.message]
        assert len(revive_msgs) == 1
        assert revive_msgs[0].heal_amount == expected_hp

    def test_cheat_death_buff_consumed(self):
        """Cheat death buff is removed after triggering."""
        player = _make_player(hp=0, max_hp=130, alive=False)
        _apply_cheat_death_buff(player)
        assert any(b.get("stat") == "cheat_death" for b in player.active_buffs)

        players = {"rev1": player}
        deaths = ["rev1"]
        results: list[ActionResult] = []
        loot_drops: list[dict] = []

        _resolve_deaths("test_match", deaths, players, None, results, loot_drops)

        # Buff should be gone
        assert not any(b.get("stat") == "cheat_death" for b in player.active_buffs)

    def test_cheat_death_only_triggers_once(self):
        """Cheat death only triggers once — after consumption, second death is real."""
        player = _make_player(hp=0, max_hp=130, alive=False)
        _apply_cheat_death_buff(player)

        players = {"rev1": player}
        deaths = ["rev1"]
        results: list[ActionResult] = []
        loot_drops: list[dict] = []

        # First death: revived
        _resolve_deaths("test_match", deaths, players, None, results, loot_drops)
        assert player.is_alive is True
        assert not any(b.get("stat") == "cheat_death" for b in player.active_buffs)

        # Simulate second death
        player.hp = 0
        player.is_alive = False
        deaths2 = ["rev1"]
        results2: list[ActionResult] = []
        loot_drops2: list[dict] = []

        _resolve_deaths("test_match", deaths2, players, None, results2, loot_drops2)

        # Second death: NOT revived (no buff)
        assert player.is_alive is False
        assert player.hp == 0
        assert "rev1" in deaths2

    def test_cheat_death_hp_correct_for_various_max_hp(self):
        """Cheat death HP calculation uses floor(max_hp * revive_hp_pct)."""
        # Test with max_hp=100 → floor(100 * 0.30) = 30
        player = _make_player(hp=0, max_hp=100, alive=False)
        _apply_cheat_death_buff(player, revive_hp_pct=0.30)

        players = {"rev1": player}
        deaths = ["rev1"]
        results: list[ActionResult] = []
        _resolve_deaths("test_match", deaths, players, None, results, [])

        assert player.hp == 30

    def test_cheat_death_hp_rounds_down(self):
        """Cheat death uses floor — e.g. 133 * 0.30 = 39.9 → 39."""
        player = _make_player(hp=0, max_hp=133, alive=False)
        _apply_cheat_death_buff(player, revive_hp_pct=0.30)

        players = {"rev1": player}
        deaths = ["rev1"]
        results: list[ActionResult] = []
        _resolve_deaths("test_match", deaths, players, None, results, [])

        assert player.hp == math.floor(133 * 0.30)  # 39

    def test_player_without_cheat_death_dies_normally(self):
        """Player without cheat_death buff dies normally (regression check)."""
        player = _make_player(hp=0, max_hp=130, alive=False, buffs=[])

        players = {"rev1": player}
        deaths = ["rev1"]
        results: list[ActionResult] = []
        loot_drops: list[dict] = []

        _resolve_deaths("test_match", deaths, players, None, results, loot_drops)

        # Should remain dead
        assert player.is_alive is False
        assert player.hp == 0
        assert "rev1" in deaths

    def test_cheat_death_revived_player_is_actionable(self):
        """Revived player has is_alive=True and positive HP — can act on next turn."""
        player = _make_player(hp=0, max_hp=130, alive=False)
        _apply_cheat_death_buff(player)

        players = {"rev1": player}
        deaths = ["rev1"]
        results: list[ActionResult] = []
        _resolve_deaths("test_match", deaths, players, None, results, [])

        # Player should be actionable
        assert player.is_alive is True
        assert player.hp > 0
        # Verify they're removed from the deaths list (so they don't get loot-dropped/permadeath'd)
        assert "rev1" not in deaths

    def test_cheat_death_preserves_other_buffs(self):
        """Cheat death only removes the cheat_death buff, not other active buffs."""
        player = _make_player(hp=0, max_hp=130, alive=False, buffs=[])
        _apply_thorns_buff(player, magnitude=10, duration=2)  # Add another buff
        _apply_cheat_death_buff(player)
        assert len(player.active_buffs) == 2  # thorns + cheat_death

        players = {"rev1": player}
        deaths = ["rev1"]
        results: list[ActionResult] = []
        _resolve_deaths("test_match", deaths, players, None, results, [])

        # Cheat death consumed, thorns remains
        assert len(player.active_buffs) == 1
        assert player.active_buffs[0]["stat"] == "thorns_damage"


# ============================================================
# 6. Buff Tick-Down — thorns_damage and cheat_death
# ============================================================


class TestBuffTickDown:
    """Tests that thorns_damage and cheat_death buffs tick down correctly via tick_buffs."""

    def test_thorns_buff_ticks_down(self):
        """Thorns buff duration decrements by 1 each tick."""
        player = _make_player(buffs=[])
        _apply_thorns_buff(player, magnitude=10, duration=3)

        assert player.active_buffs[0]["turns_remaining"] == 3

        tick_buffs(player)
        assert player.active_buffs[0]["turns_remaining"] == 2

        tick_buffs(player)
        assert player.active_buffs[0]["turns_remaining"] == 1

    def test_thorns_buff_expires_after_duration(self):
        """Thorns buff is removed after its duration expires."""
        player = _make_player(buffs=[])
        _apply_thorns_buff(player, magnitude=10, duration=2)

        tick_buffs(player)  # 2 → 1
        assert len([b for b in player.active_buffs if b.get("stat") == "thorns_damage"]) == 1

        tick_buffs(player)  # 1 → 0 → removed
        assert len([b for b in player.active_buffs if b.get("stat") == "thorns_damage"]) == 0

    def test_cheat_death_buff_ticks_down(self):
        """Cheat death buff duration decrements by 1 each tick."""
        player = _make_player(buffs=[])
        _apply_cheat_death_buff(player, duration=5)

        assert player.active_buffs[0]["turns_remaining"] == 5

        tick_buffs(player)
        assert player.active_buffs[0]["turns_remaining"] == 4

        tick_buffs(player)
        assert player.active_buffs[0]["turns_remaining"] == 3

    def test_cheat_death_buff_expires_after_duration(self):
        """Cheat death buff is removed when its duration expires (unused)."""
        player = _make_player(buffs=[])
        _apply_cheat_death_buff(player, duration=2)

        tick_buffs(player)  # 2 → 1
        assert len([b for b in player.active_buffs if b.get("stat") == "cheat_death"]) == 1

        tick_buffs(player)  # 1 → 0 → removed
        assert len([b for b in player.active_buffs if b.get("stat") == "cheat_death"]) == 0

    def test_expired_thorns_does_not_reflect(self):
        """No thorns damage after the buff has expired."""
        import random as _r
        rng = _r.Random(42)

        defender = _make_player(buffs=[])
        _apply_thorns_buff(defender, magnitude=10, duration=1)

        # Expire the buff
        tick_buffs(defender)
        assert len([b for b in defender.active_buffs if b.get("stat") == "thorns_damage"]) == 0

        attacker = _make_attacker(hp=80)
        initial_hp = attacker.hp
        damage, info = calculate_damage(attacker, defender, rng=rng)

        # No thorns damage — buff expired
        assert info["thorns_damage"] == 0
        assert attacker.hp == initial_hp

    def test_expired_cheat_death_does_not_revive(self):
        """Cheat death does not trigger after the buff has expired."""
        player = _make_player(buffs=[])
        _apply_cheat_death_buff(player, duration=1)

        # Expire the buff
        tick_buffs(player)
        assert len([b for b in player.active_buffs if b.get("stat") == "cheat_death"]) == 0

        # Now kill the player
        player.hp = 0
        player.is_alive = False

        players = {"rev1": player}
        deaths = ["rev1"]
        results: list[ActionResult] = []
        _resolve_deaths("test_match", deaths, players, None, results, [])

        # Should NOT be revived
        assert player.is_alive is False
        assert player.hp == 0
        assert "rev1" in deaths


# ============================================================
# 7. Integration — Thorns + Cheat Death combo
# ============================================================


class TestThornsCheatDeathCombo:
    """Tests for interactions between thorns and cheat death mechanics."""

    def test_cheat_death_works_with_thorns_active(self):
        """Revenant with both thorns and cheat death: thorns reflects, cheat death revives."""
        player = _make_player(hp=0, max_hp=130, alive=False, buffs=[])
        _apply_thorns_buff(player, magnitude=10)
        _apply_cheat_death_buff(player)

        players = {"rev1": player}
        deaths = ["rev1"]
        results: list[ActionResult] = []
        _resolve_deaths("test_match", deaths, players, None, results, [])

        # Should be revived
        assert player.is_alive is True
        assert player.hp == math.floor(130 * 0.30)
        # Cheat death consumed, thorns remains
        assert not any(b.get("stat") == "cheat_death" for b in player.active_buffs)
        assert any(b.get("stat") == "thorns_damage" for b in player.active_buffs)

    def test_cheat_death_minimum_hp_is_1(self):
        """Cheat death always revives with at least 1 HP (even with very low max_hp)."""
        player = _make_player(hp=0, max_hp=2, alive=False, buffs=[])
        _apply_cheat_death_buff(player, revive_hp_pct=0.30)

        players = {"rev1": player}
        deaths = ["rev1"]
        results: list[ActionResult] = []
        _resolve_deaths("test_match", deaths, players, None, results, [])

        # floor(2 * 0.30) = 0, but max(1, 0) = 1
        assert player.hp >= 1
        assert player.is_alive is True
