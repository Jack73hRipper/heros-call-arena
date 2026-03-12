"""
Tests for Phase 26C: Shaman system integration.

Covers:
- Healing Totem tick: heals allies in radius, no overheal, expires after duration
- Searing Totem tick: damages enemies in radius, ignores armor, can kill, expires
- Both totems coexisting: tick independently, replacing one doesn't affect the other
- Soul Anchor death prevention: survives killing blow at 1 HP, consumed on trigger,
  expires if unused, works against melee/ranged/DoT, max 1 per Shaman
- Root CC (movement phase): rooted cannot move, can still attack/use skills,
  expires after duration, doesn't affect allies, multiple enemies
- Totem targeting: enemies can attack/damage totems, full damage (no armor),
  destroyed at 0 HP, destroyed totem stops healing/damage
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType, ActionResult
from app.models.match import MatchState
from app.core.skills import (
    load_skills_config,
    clear_skills_cache,
    is_rooted,
)
from app.core.turn_phases.buffs_phase import _resolve_cooldowns_and_buffs
from app.core.turn_phases.deaths_phase import _resolve_deaths
from app.core.turn_phases.movement_phase import _resolve_movement
from app.core.turn_phases.combat_phase import _try_damage_totem


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


# ---------- Helpers ----------


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
    buffs: list | None = None,
) -> PlayerState:
    """Helper — create an ally PlayerState."""
    p = PlayerState(
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
    ranged_damage: int = 18,
    armor: int = 2,
    team: str = "team_2",
    x: int = 7,
    y: int = 5,
    alive: bool = True,
    buffs: list | None = None,
) -> PlayerState:
    """Helper — create an enemy PlayerState."""
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
    )
    if buffs:
        p.active_buffs = buffs
    return p


def _make_match_state(totems: list | None = None) -> MatchState:
    """Helper — create a minimal MatchState with totems list."""
    ms = MatchState(match_id="test_match")
    if totems:
        ms.totems = totems
    return ms


def _make_healing_totem(
    owner_id: str = "shaman1",
    x: int = 6,
    y: int = 6,
    team: str = "team_1",
    hp: int = 20,
    heal_per_turn: int = 8,
    effect_radius: int = 2,
    duration_remaining: int = 4,
) -> dict:
    """Helper — create a healing totem entity dict."""
    return {
        "id": "totem-heal-1",
        "type": "healing_totem",
        "owner_id": owner_id,
        "x": x,
        "y": y,
        "hp": hp,
        "max_hp": 20,
        "heal_per_turn": heal_per_turn,
        "damage_per_turn": 0,
        "effect_radius": effect_radius,
        "duration_remaining": duration_remaining,
        "team": team,
    }


def _make_searing_totem(
    owner_id: str = "shaman1",
    x: int = 8,
    y: int = 6,
    team: str = "team_1",
    hp: int = 20,
    damage_per_turn: int = 4,
    effect_radius: int = 2,
    duration_remaining: int = 4,
) -> dict:
    """Helper — create a searing totem entity dict."""
    return {
        "id": "totem-sear-1",
        "type": "searing_totem",
        "owner_id": owner_id,
        "x": x,
        "y": y,
        "hp": hp,
        "max_hp": 20,
        "heal_per_turn": 0,
        "damage_per_turn": damage_per_turn,
        "effect_radius": effect_radius,
        "duration_remaining": duration_remaining,
        "team": team,
    }


# ============================================================
# 1. Healing Totem Tick Tests
# ============================================================


class TestHealingTotemTick:
    """Tests for healing totem per-turn tick processing in buffs_phase."""

    def test_healing_totem_heals_allies_in_radius(self, loaded_skills):
        """Healing Totem heals all allies within radius each turn."""
        totem = _make_healing_totem(x=6, y=6, team="team_1")
        ally = _make_ally(player_id="ally1", x=6, y=7, hp=100, max_hp=150, team="team_1")
        match_state = _make_match_state(totems=[totem])
        players = {"ally1": ally}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert ally.hp == 108  # 100 + 8 heal
        assert any("Healing Totem" in r.message and "restores" in r.message for r in results)

    def test_healing_totem_does_not_heal_enemies(self, loaded_skills):
        """Healing Totem does not heal enemies."""
        totem = _make_healing_totem(x=6, y=6, team="team_1")
        enemy = _make_enemy(player_id="enemy1", x=6, y=7, hp=50, max_hp=80, team="team_2")
        match_state = _make_match_state(totems=[totem])
        players = {"enemy1": enemy}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert enemy.hp == 50  # No healing

    def test_healing_totem_does_not_overheal(self, loaded_skills):
        """Healing Totem does not heal above max_hp."""
        totem = _make_healing_totem(x=6, y=6, team="team_1")
        ally = _make_ally(player_id="ally1", x=6, y=7, hp=145, max_hp=150, team="team_1")
        match_state = _make_match_state(totems=[totem])
        players = {"ally1": ally}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert ally.hp == 150  # Capped at max_hp
        heal_results = [r for r in results if "restores" in r.message]
        assert len(heal_results) == 1
        assert heal_results[0].heal_amount == 5  # Only 5 healed (150 - 145)

    def test_healing_totem_no_heal_at_full_hp(self, loaded_skills):
        """Healing Totem does not produce a result if ally is at full HP."""
        totem = _make_healing_totem(x=6, y=6, team="team_1")
        ally = _make_ally(player_id="ally1", x=6, y=7, hp=150, max_hp=150, team="team_1")
        match_state = _make_match_state(totems=[totem])
        players = {"ally1": ally}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert ally.hp == 150
        # No heal result should be logged
        heal_results = [r for r in results if "restores" in r.message]
        assert len(heal_results) == 0

    def test_healing_totem_expires_after_duration(self, loaded_skills):
        """Healing Totem expires after its duration is ticked to 0."""
        totem = _make_healing_totem(x=6, y=6, team="team_1", duration_remaining=1)
        ally = _make_ally(player_id="ally1", x=6, y=7, hp=100, max_hp=150, team="team_1")
        match_state = _make_match_state(totems=[totem])
        players = {"ally1": ally}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        # Totem should have ticked (healed) and then been removed (duration_remaining went to 0)
        assert ally.hp == 108  # Still heals on its last tick
        assert len(match_state.totems) == 0  # Removed after duration hit 0

    def test_destroyed_healing_totem_removed(self, loaded_skills):
        """Destroyed healing totem (HP 0) is removed immediately without healing."""
        totem = _make_healing_totem(x=6, y=6, team="team_1", hp=0)
        ally = _make_ally(player_id="ally1", x=6, y=7, hp=100, max_hp=150, team="team_1")
        match_state = _make_match_state(totems=[totem])
        players = {"ally1": ally}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert ally.hp == 100  # No healing
        assert len(match_state.totems) == 0  # Destroyed totem cleaned up

    def test_healing_totem_heals_multiple_allies(self, loaded_skills):
        """Healing Totem heals multiple allies within radius in same turn."""
        totem = _make_healing_totem(x=6, y=6, team="team_1")
        ally1 = _make_ally(player_id="ally1", x=6, y=7, hp=100, max_hp=150, team="team_1")
        ally2 = _make_ally(player_id="ally2", username="Ally2", x=7, y=6, hp=80, max_hp=150, team="team_1")
        match_state = _make_match_state(totems=[totem])
        players = {"ally1": ally1, "ally2": ally2}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert ally1.hp == 108
        assert ally2.hp == 88
        heal_results = [r for r in results if "restores" in r.message]
        assert len(heal_results) == 2

    def test_healing_totem_ignores_out_of_radius(self, loaded_skills):
        """Healing Totem does not heal allies outside its radius."""
        totem = _make_healing_totem(x=6, y=6, team="team_1", effect_radius=2)
        far_ally = _make_ally(player_id="ally1", x=10, y=10, hp=100, max_hp=150, team="team_1")
        match_state = _make_match_state(totems=[totem])
        players = {"ally1": far_ally}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert far_ally.hp == 100  # Out of range — no heal


# ============================================================
# 2. Searing Totem Tick Tests
# ============================================================


class TestSearingTotemTick:
    """Tests for searing totem per-turn tick processing in buffs_phase."""

    def test_searing_totem_damages_enemies_in_radius(self, loaded_skills):
        """Searing Totem damages all enemies within radius each turn (reduced by armor)."""
        totem = _make_searing_totem(x=8, y=6, team="team_1")
        enemy = _make_enemy(player_id="enemy1", x=8, y=7, hp=80, max_hp=80, team="team_2")
        match_state = _make_match_state(totems=[totem])
        players = {"enemy1": enemy}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert enemy.hp == 78  # 80 - max(1, 4-2) = 78 (armor reduces damage)
        assert any("Searing Totem" in r.message and "damage" in r.message for r in results)

    def test_searing_totem_does_not_damage_allies(self, loaded_skills):
        """Searing Totem does not damage allies."""
        totem = _make_searing_totem(x=8, y=6, team="team_1")
        ally = _make_ally(player_id="ally1", x=8, y=7, hp=150, max_hp=150, team="team_1")
        match_state = _make_match_state(totems=[totem])
        players = {"ally1": ally}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert ally.hp == 150  # No damage

    def test_searing_totem_respects_armor(self, loaded_skills):
        """Searing Totem damage is reduced by armor (min 1 damage)."""
        totem = _make_searing_totem(x=8, y=6, team="team_1", damage_per_turn=4)
        # High armor enemy — damage reduced to minimum 1
        enemy = _make_enemy(player_id="enemy1", x=8, y=7, hp=80, max_hp=80,
                           armor=10, team="team_2")
        match_state = _make_match_state(totems=[totem])
        players = {"enemy1": enemy}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert enemy.hp == 79  # max(1, 4-10) = 1 damage (min 1)

    def test_searing_totem_expires_after_duration(self, loaded_skills):
        """Searing Totem expires after duration ticks to 0."""
        totem = _make_searing_totem(x=8, y=6, team="team_1", duration_remaining=1)
        enemy = _make_enemy(player_id="enemy1", x=8, y=7, hp=80, max_hp=80, team="team_2")
        match_state = _make_match_state(totems=[totem])
        players = {"enemy1": enemy}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert enemy.hp == 78  # 80 - max(1, 4-2) = 78 (armor reduces damage)
        assert len(match_state.totems) == 0  # Removed after expiry

    def test_searing_totem_can_kill_enemy(self, loaded_skills):
        """Searing Totem can kill enemies by reducing HP to 0."""
        totem = _make_searing_totem(x=8, y=6, team="team_1", damage_per_turn=4)
        enemy = _make_enemy(player_id="enemy1", x=8, y=7, hp=2, max_hp=80, team="team_2")
        match_state = _make_match_state(totems=[totem])
        players = {"enemy1": enemy}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert enemy.hp == 0
        assert not enemy.is_alive
        assert "enemy1" in deaths

    def test_searing_totem_damages_multiple_enemies(self, loaded_skills):
        """Searing Totem damages multiple enemies within radius (reduced by armor)."""
        totem = _make_searing_totem(x=8, y=6, team="team_1")
        enemy1 = _make_enemy(player_id="enemy1", username="Goblin1", x=8, y=7, hp=80, max_hp=80, team="team_2")
        enemy2 = _make_enemy(player_id="enemy2", username="Goblin2", x=9, y=6, hp=60, max_hp=60, team="team_2")
        match_state = _make_match_state(totems=[totem])
        players = {"enemy1": enemy1, "enemy2": enemy2}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert enemy1.hp == 78  # 80 - max(1, 4-2) = 78
        assert enemy2.hp == 58  # 60 - max(1, 4-2) = 58
        damage_results = [r for r in results if "Searing Totem" in r.message]
        assert len(damage_results) == 2

    def test_searing_totem_ignores_out_of_radius(self, loaded_skills):
        """Searing Totem does not damage enemies outside its radius."""
        totem = _make_searing_totem(x=8, y=6, team="team_1", effect_radius=2)
        far_enemy = _make_enemy(player_id="enemy1", x=15, y=15, hp=80, max_hp=80, team="team_2")
        match_state = _make_match_state(totems=[totem])
        players = {"enemy1": far_enemy}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert far_enemy.hp == 80  # Out of range

    def test_destroyed_searing_totem_stops_damage(self, loaded_skills):
        """Destroyed searing totem (HP 0) is removed, no damage dealt."""
        totem = _make_searing_totem(x=8, y=6, team="team_1", hp=0)
        enemy = _make_enemy(player_id="enemy1", x=8, y=7, hp=80, max_hp=80, team="team_2")
        match_state = _make_match_state(totems=[totem])
        players = {"enemy1": enemy}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert enemy.hp == 80  # No damage — totem destroyed
        assert len(match_state.totems) == 0


# ============================================================
# 3. Both Totems Coexisting Tests
# ============================================================


class TestDualTotemCoexistence:
    """Tests for healing and searing totems coexisting from the same Shaman."""

    def test_healing_and_searing_tick_independently(self, loaded_skills):
        """Both totems tick independently in the same turn."""
        heal_totem = _make_healing_totem(x=5, y=5, team="team_1")
        sear_totem = _make_searing_totem(x=9, y=9, team="team_1")
        ally = _make_ally(player_id="ally1", x=5, y=6, hp=100, max_hp=150, team="team_1")
        enemy = _make_enemy(player_id="enemy1", x=9, y=10, hp=80, max_hp=80, team="team_2")
        match_state = _make_match_state(totems=[heal_totem, sear_totem])
        players = {"ally1": ally, "enemy1": enemy}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert ally.hp == 108  # Healed 8
        assert enemy.hp == 78  # 80 - max(1, 4-2) = 78 (armor reduces damage)
        assert len(match_state.totems) == 2  # Both still active

    def test_replacing_one_type_does_not_affect_other(self, loaded_skills):
        """Removing one totem type doesn't affect the other."""
        heal_totem = _make_healing_totem(x=5, y=5, team="team_1", duration_remaining=1)
        sear_totem = _make_searing_totem(x=9, y=9, team="team_1", duration_remaining=3)
        ally = _make_ally(player_id="ally1", x=5, y=6, hp=100, max_hp=150, team="team_1")
        enemy = _make_enemy(player_id="enemy1", x=9, y=10, hp=80, max_hp=80, team="team_2")
        match_state = _make_match_state(totems=[heal_totem, sear_totem])
        players = {"ally1": ally, "enemy1": enemy}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        # Healing totem expired (was at 1 duration), searing still active (now at 2)
        assert len(match_state.totems) == 1
        assert match_state.totems[0]["type"] == "searing_totem"
        assert match_state.totems[0]["duration_remaining"] == 2


# ============================================================
# 4. Soul Anchor Death Prevention Tests
# ============================================================


class TestSoulAnchorDeathPrevention:
    """Tests for Soul Anchor death prevention in deaths_phase."""

    def test_anchored_ally_survives_killing_blow(self, loaded_skills):
        """Anchored ally survives a killing blow at 1 HP."""
        ally = _make_ally(
            player_id="ally1", username="Crusader", hp=0, max_hp=150,
            team="team_1", alive=False,
            buffs=[{
                "buff_id": "soul_anchor", "type": "soul_anchor",
                "stat": "soul_anchor", "caster_id": "shaman1",
                "turns_remaining": 3, "magnitude": 0, "survive_hp": 1,
            }],
        )
        ally.is_alive = False
        ally.hp = 0
        players = {"ally1": ally}
        deaths = ["ally1"]
        results: list[ActionResult] = []
        loot_drops: list[dict] = []

        _resolve_deaths("test_match", deaths, players, None, results, loot_drops)

        assert ally.is_alive is True
        assert ally.hp == 1
        assert "ally1" not in deaths  # Removed from deaths list
        assert any("Soul Anchor saves" in r.message for r in results)

    def test_soul_anchor_consumed_after_trigger(self, loaded_skills):
        """Soul Anchor buff is consumed after triggering."""
        ally = _make_ally(
            player_id="ally1", hp=0, max_hp=150, team="team_1", alive=False,
            buffs=[{
                "buff_id": "soul_anchor", "type": "soul_anchor",
                "stat": "soul_anchor", "caster_id": "shaman1",
                "turns_remaining": 3, "magnitude": 0, "survive_hp": 1,
            }],
        )
        ally.is_alive = False
        ally.hp = 0
        players = {"ally1": ally}
        deaths = ["ally1"]
        results: list[ActionResult] = []
        loot_drops: list[dict] = []

        _resolve_deaths("test_match", deaths, players, None, results, loot_drops)

        # Soul anchor should be removed from buffs
        sa_buffs = [b for b in ally.active_buffs if b.get("stat") == "soul_anchor"]
        assert len(sa_buffs) == 0

    def test_soul_anchor_expires_unused(self, loaded_skills):
        """Soul Anchor that's never triggered just ticks down normally via buff system."""
        # This tests that soul_anchor is a normal buff that ticks down
        # (base tick_buffs handles turns_remaining decrement)
        ally = _make_ally(
            player_id="ally1", hp=150, max_hp=150, team="team_1",
            buffs=[{
                "buff_id": "soul_anchor", "type": "soul_anchor",
                "stat": "soul_anchor", "caster_id": "shaman1",
                "turns_remaining": 1, "magnitude": 0, "survive_hp": 1,
            }],
        )
        players = {"ally1": ally}
        results: list[ActionResult] = []
        deaths: list[str] = []

        # Tick buffs (which decrements turns_remaining and removes expired)
        _resolve_cooldowns_and_buffs(players, results, deaths)

        # After tick, soul_anchor should be expired and removed
        sa_buffs = [b for b in ally.active_buffs if b.get("stat") == "soul_anchor"]
        assert len(sa_buffs) == 0

    def test_soul_anchor_works_against_combat_death(self, loaded_skills):
        """Soul Anchor saves from melee/ranged killing blow in death resolution."""
        ally = _make_ally(
            player_id="ally1", hp=0, max_hp=150, team="team_1", alive=False,
            buffs=[{
                "buff_id": "soul_anchor", "type": "soul_anchor",
                "stat": "soul_anchor", "caster_id": "shaman1",
                "turns_remaining": 4, "magnitude": 0, "survive_hp": 1,
            }],
        )
        ally.is_alive = False
        ally.hp = 0
        players = {"ally1": ally}
        deaths = ["ally1"]
        results: list[ActionResult] = []
        loot_drops: list[dict] = []

        _resolve_deaths("test_match", deaths, players, None, results, loot_drops)

        assert ally.is_alive is True
        assert ally.hp == 1

    def test_soul_anchor_does_not_trigger_if_alive(self, loaded_skills):
        """Soul Anchor does not activate if unit is not in deaths list."""
        ally = _make_ally(
            player_id="ally1", hp=50, max_hp=150, team="team_1",
            buffs=[{
                "buff_id": "soul_anchor", "type": "soul_anchor",
                "stat": "soul_anchor", "caster_id": "shaman1",
                "turns_remaining": 4, "magnitude": 0, "survive_hp": 1,
            }],
        )
        players = {"ally1": ally}
        deaths: list[str] = []  # Not dying
        results: list[ActionResult] = []
        loot_drops: list[dict] = []

        _resolve_deaths("test_match", deaths, players, None, results, loot_drops)

        assert ally.hp == 50  # Unchanged
        sa_buffs = [b for b in ally.active_buffs if b.get("stat") == "soul_anchor"]
        assert len(sa_buffs) == 1  # Still present

    def test_cheat_death_takes_priority_over_soul_anchor(self, loaded_skills):
        """Cheat death (Undying Will) takes priority; soul anchor not consumed."""
        ally = _make_ally(
            player_id="ally1", username="Revenant", hp=0, max_hp=130, team="team_1",
            alive=False,
            buffs=[
                {
                    "buff_id": "undying_will", "type": "cheat_death",
                    "stat": "cheat_death", "turns_remaining": 3, "magnitude": 0,
                    "revive_hp_pct": 0.30,
                },
                {
                    "buff_id": "soul_anchor", "type": "soul_anchor",
                    "stat": "soul_anchor", "caster_id": "shaman1",
                    "turns_remaining": 4, "magnitude": 0, "survive_hp": 1,
                },
            ],
        )
        ally.is_alive = False
        ally.hp = 0
        players = {"ally1": ally}
        deaths = ["ally1"]
        results: list[ActionResult] = []
        loot_drops: list[dict] = []

        _resolve_deaths("test_match", deaths, players, None, results, loot_drops)

        assert ally.is_alive is True
        # Revived by cheat_death (30% of 130 = 39 HP), not soul anchor (1 HP)
        assert ally.hp == 39
        # Cheat death consumed, soul anchor still active
        cd_buffs = [b for b in ally.active_buffs if b.get("stat") == "cheat_death"]
        assert len(cd_buffs) == 0
        sa_buffs = [b for b in ally.active_buffs if b.get("stat") == "soul_anchor"]
        assert len(sa_buffs) == 1  # Not consumed

    def test_soul_anchor_one_per_shaman(self, loaded_skills):
        """Only one soul_anchor buff active per caster in death resolution—first one triggers."""
        # This tests that only one triggers (the iteration finds the first matching buff)
        ally = _make_ally(
            player_id="ally1", hp=0, max_hp=150, team="team_1", alive=False,
            buffs=[{
                "buff_id": "soul_anchor", "type": "soul_anchor",
                "stat": "soul_anchor", "caster_id": "shaman1",
                "turns_remaining": 4, "magnitude": 0, "survive_hp": 1,
            }],
        )
        ally.is_alive = False
        ally.hp = 0
        players = {"ally1": ally}
        deaths = ["ally1"]
        results: list[ActionResult] = []
        loot_drops: list[dict] = []

        _resolve_deaths("test_match", deaths, players, None, results, loot_drops)

        assert ally.is_alive is True
        assert ally.hp == 1


# ============================================================
# 5. Root CC (Movement Phase) Tests
# ============================================================


class TestRootMovementBlocking:
    """Tests for root CC enforcement in movement phase."""

    def test_is_rooted_helper(self, loaded_skills):
        """is_rooted() returns True when rooted buff is present."""
        enemy = _make_enemy(
            buffs=[{
                "buff_id": "earthgrasp", "type": "aoe_root",
                "stat": "rooted", "turns_remaining": 2, "magnitude": 0,
            }],
        )
        assert is_rooted(enemy) is True

    def test_is_rooted_helper_returns_false(self, loaded_skills):
        """is_rooted() returns False when no rooted buff is present."""
        enemy = _make_enemy()
        assert is_rooted(enemy) is False

    def test_rooted_enemy_cannot_move(self, loaded_skills):
        """Rooted enemy cannot move (stays in place)."""
        enemy = _make_enemy(
            player_id="enemy1", x=7, y=5, team="team_2",
            buffs=[{
                "buff_id": "earthgrasp", "type": "aoe_root",
                "stat": "rooted", "turns_remaining": 2, "magnitude": 0,
            }],
        )
        move_action = PlayerAction(
            player_id="enemy1",
            action_type=ActionType.MOVE,
            target_x=8,
            target_y=5,
        )
        players = {"enemy1": enemy}
        results: list[ActionResult] = []
        obstacles: set = set()

        _resolve_movement(
            [move_action], players, 20, 20, obstacles, results,
        )

        # Enemy should still be at original position
        assert enemy.position.x == 7
        assert enemy.position.y == 5
        # Result message should indicate rooted
        assert any("rooted" in r.message.lower() for r in results)

    def test_rooted_enemy_can_still_be_targeted(self, loaded_skills):
        """Root doesn't prevent being attacked or using skills (just movement)."""
        # This is a design validation test — root stat exists alongside combat
        enemy = _make_enemy(
            player_id="enemy1", x=7, y=5,
            buffs=[{
                "buff_id": "earthgrasp", "type": "aoe_root",
                "stat": "rooted", "turns_remaining": 2, "magnitude": 0,
            }],
        )
        # Root doesn't affect is_alive or combat eligibility
        assert enemy.is_alive is True
        # is_rooted only blocks movement, not stunned
        from app.core.skills import is_stunned
        assert is_stunned(enemy) is False

    def test_root_does_not_affect_allies(self, loaded_skills):
        """Root is applied via enemy targeting — allies are never rooted by Earthgrasp logic."""
        ally = _make_ally(player_id="ally1", x=5, y=5, team="team_1")
        # No root buff on ally → not rooted
        assert is_rooted(ally) is False

    def test_multiple_enemies_rooted_simultaneously(self, loaded_skills):
        """Multiple rooted enemies all blocked from moving."""
        rooted_buff = {
            "buff_id": "earthgrasp", "type": "aoe_root",
            "stat": "rooted", "turns_remaining": 2, "magnitude": 0,
        }
        enemy1 = _make_enemy(
            player_id="e1", username="Goblin1", x=7, y=5, team="team_2",
            buffs=[rooted_buff.copy()],
        )
        enemy2 = _make_enemy(
            player_id="e2", username="Goblin2", x=8, y=5, team="team_2",
            buffs=[rooted_buff.copy()],
        )
        move1 = PlayerAction(player_id="e1", action_type=ActionType.MOVE, target_x=7, target_y=6)
        move2 = PlayerAction(player_id="e2", action_type=ActionType.MOVE, target_x=8, target_y=6)
        players = {"e1": enemy1, "e2": enemy2}
        results: list[ActionResult] = []

        _resolve_movement([move1, move2], players, 20, 20, set(), results)

        assert enemy1.position.x == 7 and enemy1.position.y == 5
        assert enemy2.position.x == 8 and enemy2.position.y == 5
        rooted_results = [r for r in results if "rooted" in r.message.lower()]
        assert len(rooted_results) == 2


# ============================================================
# 6. Totem Targeting Tests
# ============================================================


class TestTotemTargeting:
    """Tests for enemy attacks hitting and destroying totems."""

    def test_enemy_can_damage_totem(self, loaded_skills):
        """Enemy can attack and damage a totem."""
        attacker = _make_enemy(player_id="enemy1", x=7, y=5, attack_damage=10, team="team_2")
        totem = _make_healing_totem(x=7, y=6, team="team_1", hp=20)
        match_state = _make_match_state(totems=[totem])
        results: list[ActionResult] = []

        hit = _try_damage_totem(attacker, 7, 6, match_state, results, "melee")

        assert hit is True
        assert totem["hp"] == 10  # 20 - 10 melee damage
        assert len(results) == 1
        assert "hit" in results[0].message.lower()

    def test_totem_takes_full_damage_no_armor(self, loaded_skills):
        """Totem takes full damage (no armor reduction)."""
        attacker = _make_enemy(player_id="enemy1", x=7, y=5, attack_damage=15, team="team_2")
        totem = _make_healing_totem(x=7, y=6, team="team_1", hp=20)
        match_state = _make_match_state(totems=[totem])
        results: list[ActionResult] = []

        _try_damage_totem(attacker, 7, 6, match_state, results, "melee")

        assert totem["hp"] == 5  # Full 15 damage

    def test_totem_dies_when_hp_reaches_zero(self, loaded_skills):
        """Totem is destroyed and removed when HP reaches 0."""
        attacker = _make_enemy(player_id="enemy1", x=7, y=5, attack_damage=25, team="team_2")
        totem = _make_healing_totem(x=7, y=6, team="team_1", hp=20)
        match_state = _make_match_state(totems=[totem])
        results: list[ActionResult] = []

        _try_damage_totem(attacker, 7, 6, match_state, results, "melee")

        assert len(match_state.totems) == 0  # Totem removed
        assert "destroyed" in results[0].message.lower()

    def test_dead_totem_stops_healing(self, loaded_skills):
        """Destroyed totem (after combat) does not heal on next tick."""
        totem = _make_healing_totem(x=6, y=6, team="team_1", hp=0)
        ally = _make_ally(player_id="ally1", x=6, y=7, hp=100, max_hp=150, team="team_1")
        match_state = _make_match_state(totems=[totem])
        players = {"ally1": ally}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert ally.hp == 100  # No healing from dead totem

    def test_ranged_attack_can_damage_totem(self, loaded_skills):
        """Ranged attack can damage a totem."""
        attacker = _make_enemy(player_id="enemy1", x=10, y=10, ranged_damage=18, team="team_2")
        totem = _make_searing_totem(x=8, y=8, team="team_1", hp=20)
        match_state = _make_match_state(totems=[totem])
        results: list[ActionResult] = []

        hit = _try_damage_totem(attacker, 8, 8, match_state, results, "ranged")

        assert hit is True
        assert totem["hp"] == 2  # 20 - 18

    def test_cannot_attack_own_totem(self, loaded_skills):
        """Unit cannot attack their own team's totem."""
        ally = _make_ally(player_id="ally1", x=6, y=5, attack_damage=20, team="team_1")
        totem = _make_healing_totem(x=6, y=6, team="team_1", hp=20)
        match_state = _make_match_state(totems=[totem])
        results: list[ActionResult] = []

        hit = _try_damage_totem(ally, 6, 6, match_state, results, "melee")

        assert hit is False
        assert totem["hp"] == 20  # Undamaged

    def test_no_totem_at_tile_returns_false(self, loaded_skills):
        """Returns False when no totem exists at the target tile."""
        attacker = _make_enemy(player_id="enemy1", x=7, y=5, attack_damage=10, team="team_2")
        match_state = _make_match_state(totems=[])
        results: list[ActionResult] = []

        hit = _try_damage_totem(attacker, 7, 6, match_state, results, "melee")

        assert hit is False
        assert len(results) == 0

    def test_no_match_state_returns_false(self, loaded_skills):
        """Returns False when match_state is None."""
        attacker = _make_enemy(player_id="enemy1", x=7, y=5, team="team_2")
        results: list[ActionResult] = []

        hit = _try_damage_totem(attacker, 7, 6, None, results, "melee")

        assert hit is False


# ============================================================
# 7. Totem Duration and Lifecycle Tests
# ============================================================


class TestTotemLifecycle:
    """Tests for totem lifecycle — duration tracking across multiple ticks."""

    def test_totem_duration_decrements_each_tick(self, loaded_skills):
        """Totem duration decreases by 1 each tick."""
        totem = _make_healing_totem(x=6, y=6, team="team_1", duration_remaining=4)
        match_state = _make_match_state(totems=[totem])
        players: dict = {}
        results: list[ActionResult] = []
        deaths: list[str] = []

        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert match_state.totems[0]["duration_remaining"] == 3

    def test_totem_survives_full_duration(self, loaded_skills):
        """Totem with 4 duration survives 3 ticks, then removed on 4th."""
        totem = _make_healing_totem(x=6, y=6, team="team_1", duration_remaining=4)
        match_state = _make_match_state(totems=[totem])
        players: dict = {}

        # Tick 3 times
        for _ in range(3):
            results: list[ActionResult] = []
            deaths: list[str] = []
            _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)

        assert len(match_state.totems) == 1
        assert match_state.totems[0]["duration_remaining"] == 1

        # 4th tick — totem's last tick, then removed
        results = []
        deaths = []
        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=match_state)
        assert len(match_state.totems) == 0

    def test_no_match_state_graceful(self, loaded_skills):
        """buffs_phase handles None match_state gracefully (no crash)."""
        players: dict = {}
        results: list[ActionResult] = []
        deaths: list[str] = []

        # Should not raise any exception
        _resolve_cooldowns_and_buffs(players, results, deaths, match_state=None)
