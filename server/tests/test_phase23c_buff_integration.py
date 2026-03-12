"""
Tests for Phase 23C: Buff System Integration (damage_dealt_multiplier).

Covers:
- get_damage_dealt_multiplier() helper function
- damage_dealt_multiplier reduces melee damage (calculate_damage, calculate_damage_simple)
- damage_dealt_multiplier reduces ranged damage (calculate_ranged_damage, calculate_ranged_damage_simple)
- Minimum damage of 1 always respected
- Buff expiration resets damage to normal
- Multiplicative stacking of multiple Enfeeble sources
- Combined Enfeeble (damage_dealt_multiplier) + Dirge (damage_taken_multiplier) interaction
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.core.skills import (
    load_skills_config,
    clear_skills_cache,
    get_damage_dealt_multiplier,
    get_damage_taken_multiplier,
    tick_buffs,
)
from app.core.combat import (
    calculate_damage_simple,
    calculate_ranged_damage_simple,
    calculate_damage,
    calculate_ranged_damage,
)


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def _reset_skills_cache():
    """Clear cached config before each test to ensure isolation."""
    clear_skills_cache()
    yield
    clear_skills_cache()


@pytest.fixture
def loaded_skills() -> dict:
    """Load and return the skills config dict."""
    return load_skills_config()


# ---------- Helpers ----------

def _make_player(
    player_id: str = "p1",
    username: str = "TestPlayer",
    class_id: str = "crusader",
    hp: int = 100,
    max_hp: int = 100,
    attack_damage: int = 20,
    ranged_damage: int = 10,
    armor: int = 0,
    alive: bool = True,
    team: str = "team_1",
    x: int = 5,
    y: int = 5,
    active_buffs: list | None = None,
) -> PlayerState:
    """Helper — create a PlayerState with specified stats."""
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
    if active_buffs:
        p.active_buffs = active_buffs
    return p


def _enfeeble_debuff(turns: int = 3, magnitude: float = 0.75) -> dict:
    """Create an Enfeeble debuff entry (damage_dealt_multiplier)."""
    return {
        "buff_id": "enfeeble",
        "type": "debuff",
        "stat": "damage_dealt_multiplier",
        "magnitude": magnitude,
        "turns_remaining": turns,
    }


def _dirge_debuff(turns: int = 3, magnitude: float = 1.25) -> dict:
    """Create a Dirge of Weakness debuff entry (damage_taken_multiplier)."""
    return {
        "buff_id": "dirge_of_weakness",
        "type": "debuff",
        "stat": "damage_taken_multiplier",
        "magnitude": magnitude,
        "turns_remaining": turns,
    }


# ============================================================
# 1. get_damage_dealt_multiplier() helper tests
# ============================================================

class TestGetDamageDealtMultiplier:
    """Tests for the get_damage_dealt_multiplier helper."""

    def test_no_debuffs_returns_1(self):
        player = _make_player()
        assert get_damage_dealt_multiplier(player) == 1.0

    def test_single_enfeeble_returns_075(self):
        player = _make_player(active_buffs=[_enfeeble_debuff()])
        assert get_damage_dealt_multiplier(player) == pytest.approx(0.75)

    def test_double_enfeeble_stacks_multiplicatively(self):
        player = _make_player(active_buffs=[_enfeeble_debuff(), _enfeeble_debuff()])
        # 0.75 × 0.75 = 0.5625
        assert get_damage_dealt_multiplier(player) == pytest.approx(0.5625)

    def test_expired_debuff_returns_1(self):
        player = _make_player(active_buffs=[_enfeeble_debuff(turns=1)])
        # Tick once to expire
        tick_buffs(player)
        assert get_damage_dealt_multiplier(player) == 1.0

    def test_ignores_other_buff_stats(self):
        """damage_dealt_multiplier should not be affected by damage_taken_multiplier or others."""
        player = _make_player(active_buffs=[_dirge_debuff()])
        assert get_damage_dealt_multiplier(player) == 1.0


# ============================================================
# 2. damage_dealt_multiplier in melee damage
# ============================================================

class TestEnfeebleMeleeDamage:
    """Tests for damage_dealt_multiplier reducing melee damage."""

    def test_enfeebled_attacker_deals_reduced_melee_damage(self):
        """Enfeebled attacker should deal 0.75× melee damage."""
        attacker = _make_player(
            player_id="atk", attack_damage=20, armor=0,
            active_buffs=[_enfeeble_debuff()],
        )
        defender = _make_player(player_id="def", hp=100, armor=0, team="team_2")

        normal_attacker = _make_player(
            player_id="atk2", attack_damage=20, armor=0,
        )
        normal_defender = _make_player(player_id="def2", hp=100, armor=0, team="team_2")

        normal_dmg = calculate_damage_simple(normal_attacker, normal_defender)
        enfeebled_dmg = calculate_damage_simple(attacker, defender)

        assert enfeebled_dmg < normal_dmg
        assert enfeebled_dmg == max(1, int(normal_dmg * 0.75))

    def test_enfeebled_melee_minimum_damage_is_1(self):
        """Even with Enfeeble, minimum melee damage should be 1."""
        attacker = _make_player(
            player_id="atk", attack_damage=1, armor=0,
            active_buffs=[_enfeeble_debuff()],
        )
        defender = _make_player(player_id="def", hp=100, armor=10, team="team_2")

        dmg = calculate_damage_simple(attacker, defender)
        assert dmg >= 1

    def test_enfeeble_expires_melee_damage_returns_to_normal(self):
        """After Enfeeble expires, melee damage should be back to normal."""
        attacker = _make_player(
            player_id="atk", attack_damage=20, armor=0,
            active_buffs=[_enfeeble_debuff(turns=1)],
        )
        defender1 = _make_player(player_id="def1", hp=100, armor=0, team="team_2")

        enfeebled_dmg = calculate_damage_simple(attacker, defender1)

        # Tick to expire the debuff
        tick_buffs(attacker)
        assert get_damage_dealt_multiplier(attacker) == 1.0

        defender2 = _make_player(player_id="def2", hp=100, armor=0, team="team_2")
        normal_dmg = calculate_damage_simple(attacker, defender2)

        assert normal_dmg > enfeebled_dmg
        assert normal_dmg == 20  # Full damage, no armor

    def test_calculate_damage_full_applies_enfeeble(self):
        """calculate_damage() (full pipeline) should also apply damage_dealt_multiplier."""
        import random
        rng = random.Random(42)

        attacker = _make_player(
            player_id="atk", attack_damage=20, armor=0,
            active_buffs=[_enfeeble_debuff()],
        )
        defender = _make_player(player_id="def", hp=200, armor=0, team="team_2", x=6, y=5)

        dmg, info = calculate_damage(attacker, defender, rng=rng)
        # 20 * 0.75 = 15, no crit expected with no crit_chance
        assert dmg == 15


# ============================================================
# 3. damage_dealt_multiplier in ranged damage
# ============================================================

class TestEnfeebleRangedDamage:
    """Tests for damage_dealt_multiplier reducing ranged damage."""

    def test_enfeebled_attacker_deals_reduced_ranged_damage(self):
        """Enfeebled attacker should deal 0.75× ranged damage."""
        attacker = _make_player(
            player_id="atk", ranged_damage=20, armor=0,
            active_buffs=[_enfeeble_debuff()],
        )
        defender = _make_player(player_id="def", hp=100, armor=0, team="team_2")

        normal_attacker = _make_player(
            player_id="atk2", ranged_damage=20, armor=0,
        )
        normal_defender = _make_player(player_id="def2", hp=100, armor=0, team="team_2")

        normal_dmg = calculate_ranged_damage_simple(normal_attacker, normal_defender)
        enfeebled_dmg = calculate_ranged_damage_simple(attacker, defender)

        assert enfeebled_dmg < normal_dmg
        assert enfeebled_dmg == max(1, int(normal_dmg * 0.75))

    def test_enfeebled_ranged_minimum_damage_is_1(self):
        """Even with Enfeeble, minimum ranged damage should be 1."""
        attacker = _make_player(
            player_id="atk", ranged_damage=1, armor=0,
            active_buffs=[_enfeeble_debuff()],
        )
        defender = _make_player(player_id="def", hp=100, armor=10, team="team_2")

        dmg = calculate_ranged_damage_simple(attacker, defender)
        assert dmg >= 1

    def test_enfeeble_expires_ranged_damage_returns_to_normal(self):
        """After Enfeeble expires, ranged damage should be back to normal."""
        attacker = _make_player(
            player_id="atk", ranged_damage=20, armor=0,
            active_buffs=[_enfeeble_debuff(turns=1)],
        )
        defender1 = _make_player(player_id="def1", hp=100, armor=0, team="team_2")

        enfeebled_dmg = calculate_ranged_damage_simple(attacker, defender1)

        # Tick to expire
        tick_buffs(attacker)
        assert get_damage_dealt_multiplier(attacker) == 1.0

        defender2 = _make_player(player_id="def2", hp=100, armor=0, team="team_2")
        normal_dmg = calculate_ranged_damage_simple(attacker, defender2)

        assert normal_dmg > enfeebled_dmg
        assert normal_dmg == 20  # Full damage, no armor

    def test_calculate_ranged_damage_full_applies_enfeeble(self):
        """calculate_ranged_damage() (full pipeline) should also apply damage_dealt_multiplier."""
        import random
        rng = random.Random(42)

        attacker = _make_player(
            player_id="atk", ranged_damage=20, armor=0,
            active_buffs=[_enfeeble_debuff()],
        )
        defender = _make_player(player_id="def", hp=200, armor=0, team="team_2", x=8, y=5)

        dmg, info = calculate_ranged_damage(attacker, defender, rng=rng)
        # 20 * 0.75 = 15, no crit expected with no crit_chance
        assert dmg == 15


# ============================================================
# 4. Edge cases and interactions
# ============================================================

class TestEnfeebleEdgeCases:
    """Edge case tests for damage_dealt_multiplier."""

    def test_multiple_enfeeble_sources_stack_multiplicatively(self):
        """Two Enfeeble debuffs (0.75 × 0.75 = 0.5625) should stack."""
        attacker = _make_player(
            player_id="atk", attack_damage=20, armor=0,
            active_buffs=[_enfeeble_debuff(), _enfeeble_debuff()],
        )
        defender = _make_player(player_id="def", hp=100, armor=0, team="team_2")

        dmg = calculate_damage_simple(attacker, defender)
        # 20 * 0.5625 = 11.25 → int(11.25) = 11
        expected = max(1, int(20 * 0.5625))
        assert dmg == expected

    def test_enfeeble_and_dirge_both_apply(self):
        """Both Enfeeble (0.75 dmg dealt) and Dirge (1.25 dmg taken) should apply.

        Attacker has Enfeeble (deals 0.75× damage).
        Defender has Dirge (takes 1.25× damage).
        Combined: 20 * 1.25 * 0.75 = 18.75 → 18 (order: dmg_taken applied first, then dmg_dealt).
        """
        attacker = _make_player(
            player_id="atk", attack_damage=20, armor=0,
            active_buffs=[_enfeeble_debuff()],
        )
        defender = _make_player(
            player_id="def", hp=100, armor=0, team="team_2",
            active_buffs=[_dirge_debuff()],
        )

        dmg = calculate_damage_simple(attacker, defender)
        # Pipeline: base=20, dmg_taken_mult first: int(20*1.25)=25, then dmg_dealt: int(25*0.75)=18
        expected = max(1, int(int(20 * 1.25) * 0.75))
        assert dmg == expected

    def test_no_crash_when_multiplier_is_1(self):
        """No debuff → multiplier is exactly 1.0, damage should be unchanged."""
        attacker = _make_player(player_id="atk", attack_damage=20, armor=0)
        defender = _make_player(player_id="def", hp=100, armor=0, team="team_2")

        assert get_damage_dealt_multiplier(attacker) == 1.0
        dmg = calculate_damage_simple(attacker, defender)
        assert dmg == 20

    def test_enfeeble_reduces_ranged_damage_simple(self):
        """calculate_ranged_damage_simple applies damage_dealt_multiplier."""
        attacker = _make_player(
            player_id="atk", ranged_damage=16, armor=0,
            active_buffs=[_enfeeble_debuff()],
        )
        defender = _make_player(player_id="def", hp=100, armor=0, team="team_2")

        dmg = calculate_ranged_damage_simple(attacker, defender)
        # 16 * 0.75 = 12
        assert dmg == 12

    def test_enfeeble_reduces_melee_damage_simple(self):
        """calculate_damage_simple applies damage_dealt_multiplier."""
        attacker = _make_player(
            player_id="atk", attack_damage=16, armor=0,
            active_buffs=[_enfeeble_debuff()],
        )
        defender = _make_player(player_id="def", hp=100, armor=0, team="team_2")

        dmg = calculate_damage_simple(attacker, defender)
        # 16 * 0.75 = 12
        assert dmg == 12
