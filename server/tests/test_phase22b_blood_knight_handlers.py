"""
Tests for Phase 22B: Blood Knight Effect Handlers.

Covers:
- resolve_lifesteal_damage() — Blood Strike (single-target melee + lifesteal)
- resolve_lifesteal_aoe() — Sanguine Burst (AoE melee + lifesteal)
- resolve_conditional_buff() — Blood Frenzy (HP threshold + instant heal + buff)
- resolve_buff() multi-effect — Crimson Veil (buff + HoT)
- resolve_skill_action() dispatcher routing for new effect types
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import ActionResult, ActionType
from app.core.skills import (
    load_skills_config,
    clear_skills_cache,
    get_skill,
    resolve_lifesteal_damage,
    resolve_lifesteal_aoe,
    resolve_conditional_buff,
    resolve_buff,
    resolve_skill_action,
    get_melee_buff_multiplier,
    tick_buffs,
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
    player_id: str = "bk1",
    username: str = "BloodKnight",
    class_id: str = "blood_knight",
    hp: int = 100,
    max_hp: int = 100,
    attack_damage: int = 16,
    ranged_damage: int = 0,
    armor: int = 4,
    team: str = "team_1",
    x: int = 5,
    y: int = 5,
    alive: bool = True,
    cooldowns: dict | None = None,
    active_buffs: list | None = None,
) -> PlayerState:
    """Helper — create a PlayerState for Blood Knight testing."""
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
        active_buffs=active_buffs or [],
    )
    return p


def _make_enemy(
    player_id: str = "enemy1",
    username: str = "Skeleton",
    hp: int = 50,
    max_hp: int = 50,
    armor: int = 4,
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
        class_id="crusader",
        hp=hp,
        max_hp=max_hp,
        attack_damage=10,
        armor=armor,
        is_alive=alive,
        cooldowns={},
        team=team,
        active_buffs=[],
    )


def _make_players(*units: PlayerState) -> dict[str, PlayerState]:
    """Build a players dict from a list of units."""
    return {u.player_id: u for u in units}


# ============================================================
# 1. Blood Strike (lifesteal_damage)
# ============================================================

class TestBloodStrikeLifestealDamage:
    """Tests for resolve_lifesteal_damage() — Blood Strike handler."""

    def test_blood_strike_deals_damage(self, loaded_skills):
        """Blood Strike deals 1.4x melee damage to adjacent enemy."""
        bk = _make_player(hp=80, max_hp=100)
        enemy = _make_enemy(hp=50, armor=0)
        players = _make_players(bk, enemy)
        skill = get_skill("blood_strike")

        result = resolve_lifesteal_damage(bk, 6, 5, skill, players, set(), target_id="enemy1")

        assert result.success is True
        # 16 * 1.4 = 22 damage (0 armor)
        assert result.damage_dealt == 22
        assert enemy.hp == 50 - 22

    def test_blood_strike_heals_caster(self, loaded_skills):
        """Blood Strike heals caster for 40% of damage dealt."""
        bk = _make_player(hp=80, max_hp=100)
        enemy = _make_enemy(hp=50, armor=0)
        players = _make_players(bk, enemy)
        skill = get_skill("blood_strike")

        resolve_lifesteal_damage(bk, 6, 5, skill, players, set(), target_id="enemy1")

        # Damage = 22, heal = floor(22 * 0.4) = 8
        assert bk.hp == 80 + 8

    def test_blood_strike_respects_armor(self, loaded_skills):
        """Blood Strike damage is reduced by target armor (min 1 damage)."""
        bk = _make_player(hp=80, max_hp=100)
        enemy = _make_enemy(hp=50, armor=4)
        players = _make_players(bk, enemy)
        skill = get_skill("blood_strike")

        result = resolve_lifesteal_damage(bk, 6, 5, skill, players, set(), target_id="enemy1")

        # 16 * 1.4 = 22 - 4 armor = 18 damage
        assert result.damage_dealt == 18
        assert enemy.hp == 50 - 18

    def test_blood_strike_heal_respects_armor(self, loaded_skills):
        """Lifesteal heal is based on post-armor damage."""
        bk = _make_player(hp=80, max_hp=100)
        enemy = _make_enemy(hp=50, armor=4)
        players = _make_players(bk, enemy)
        skill = get_skill("blood_strike")

        resolve_lifesteal_damage(bk, 6, 5, skill, players, set(), target_id="enemy1")

        # Damage = 18, heal = floor(18 * 0.4) = 7
        assert bk.hp == 80 + 7

    def test_blood_strike_heal_capped_at_max_hp(self, loaded_skills):
        """Lifesteal heal does not exceed max HP."""
        bk = _make_player(hp=98, max_hp=100)
        enemy = _make_enemy(hp=50, armor=0)
        players = _make_players(bk, enemy)
        skill = get_skill("blood_strike")

        resolve_lifesteal_damage(bk, 6, 5, skill, players, set(), target_id="enemy1")

        # heal would be 8 but capped at 100
        assert bk.hp == 100

    def test_blood_strike_fails_non_adjacent(self, loaded_skills):
        """Blood Strike fails when target is not adjacent."""
        bk = _make_player(x=5, y=5)
        enemy = _make_enemy(x=8, y=5)  # 3 tiles away
        players = _make_players(bk, enemy)
        skill = get_skill("blood_strike")

        result = resolve_lifesteal_damage(bk, 8, 5, skill, players, set(), target_id="enemy1")

        assert result.success is False
        assert "not adjacent" in result.message

    def test_blood_strike_fails_dead_target(self, loaded_skills):
        """Blood Strike fails against a dead target."""
        bk = _make_player()
        enemy = _make_enemy(alive=False)
        players = _make_players(bk, enemy)
        skill = get_skill("blood_strike")

        result = resolve_lifesteal_damage(bk, 6, 5, skill, players, set(), target_id="enemy1")

        assert result.success is False

    def test_blood_strike_fails_against_ally(self, loaded_skills):
        """Blood Strike fails against a same-team ally."""
        bk = _make_player(team="team_1")
        ally = _make_enemy(player_id="ally1", team="team_1", x=6, y=5)
        players = _make_players(bk, ally)
        skill = get_skill("blood_strike")

        result = resolve_lifesteal_damage(bk, 6, 5, skill, players, set(), target_id="ally1")

        assert result.success is False

    def test_blood_strike_sets_cooldown(self, loaded_skills):
        """Blood Strike sets cooldown to 4 after use."""
        bk = _make_player(hp=80, max_hp=100)
        enemy = _make_enemy(hp=50, armor=0)
        players = _make_players(bk, enemy)
        skill = get_skill("blood_strike")

        resolve_lifesteal_damage(bk, 6, 5, skill, players, set(), target_id="enemy1")

        assert bk.cooldowns.get("blood_strike", 0) == 4

    def test_blood_strike_with_buff_multiplier(self, loaded_skills):
        """Blood Strike applies melee buff multiplier (e.g., Crimson Veil combo)."""
        bk = _make_player(hp=80, max_hp=100, active_buffs=[
            {"buff_id": "crimson_veil", "type": "buff", "stat": "melee_damage_multiplier",
             "magnitude": 1.3, "turns_remaining": 3}
        ])
        enemy = _make_enemy(hp=80, armor=0)
        players = _make_players(bk, enemy)
        skill = get_skill("blood_strike")

        result = resolve_lifesteal_damage(bk, 6, 5, skill, players, set(), target_id="enemy1")

        # 16 * 1.3 (buff) * 1.4 (skill) = 29.12 → int = 29
        assert result.damage_dealt == 29
        # heal = floor(29 * 0.4) = 11
        assert bk.hp == 80 + 11

    def test_blood_strike_target_killed(self, loaded_skills):
        """Blood Strike can kill the target."""
        bk = _make_player(hp=80, max_hp=100)
        enemy = _make_enemy(hp=5, armor=0)
        players = _make_players(bk, enemy)
        skill = get_skill("blood_strike")

        result = resolve_lifesteal_damage(bk, 6, 5, skill, players, set(), target_id="enemy1")

        assert result.killed is True
        assert enemy.is_alive is False
        assert enemy.hp == 0

    def test_blood_strike_fails_no_target_specified(self, loaded_skills):
        """Blood Strike fails when no target is specified."""
        bk = _make_player()
        players = _make_players(bk)
        skill = get_skill("blood_strike")

        result = resolve_lifesteal_damage(bk, None, None, skill, players, set())

        assert result.success is False
        assert "no target" in result.message.lower()

    def test_blood_strike_min_1_damage(self, loaded_skills):
        """Blood Strike always deals at least 1 damage even with high armor."""
        bk = _make_player(hp=80, max_hp=100)
        enemy = _make_enemy(hp=50, armor=100)  # absurdly high armor
        players = _make_players(bk, enemy)
        skill = get_skill("blood_strike")

        result = resolve_lifesteal_damage(bk, 6, 5, skill, players, set(), target_id="enemy1")

        assert result.damage_dealt >= 1
        assert enemy.hp == 49


# ============================================================
# 2. Crimson Veil (buff + HoT multi-effect)
# ============================================================

class TestCrimsonVeilMultiEffect:
    """Tests for Crimson Veil: resolve_buff() with multi-effect HoT extension."""

    def test_crimson_veil_applies_melee_buff(self, loaded_skills):
        """Crimson Veil applies melee_damage_multiplier 1.3 for 3 turns."""
        bk = _make_player()
        skill = get_skill("crimson_veil")

        result = resolve_buff(bk, skill)

        assert result.success is True
        # Find the primary buff
        melee_buffs = [b for b in bk.active_buffs if b.get("stat") == "melee_damage_multiplier"]
        assert len(melee_buffs) == 1
        assert melee_buffs[0]["magnitude"] == 1.3
        assert melee_buffs[0]["turns_remaining"] == 3

    def test_crimson_veil_applies_hot(self, loaded_skills):
        """Crimson Veil applies HoT that heals 6 HP/turn for 3 turns."""
        bk = _make_player()
        skill = get_skill("crimson_veil")

        resolve_buff(bk, skill)

        # Find the HoT buff
        hot_buffs = [b for b in bk.active_buffs if b.get("type") == "hot"]
        assert len(hot_buffs) == 1
        assert hot_buffs[0]["heal_per_tick"] == 6
        assert hot_buffs[0]["turns_remaining"] == 3

    def test_crimson_veil_hot_heals_on_tick(self, loaded_skills):
        """Crimson Veil HoT heals 6 HP when tick_buffs() is called."""
        bk = _make_player(hp=80, max_hp=100)
        skill = get_skill("crimson_veil")

        resolve_buff(bk, skill)
        tick_buffs(bk)

        # Should heal 6 HP from HoT tick
        assert bk.hp == 86

    def test_crimson_veil_buff_affects_melee_multiplier(self, loaded_skills):
        """Crimson Veil's buff multiplier shows in get_melee_buff_multiplier()."""
        bk = _make_player()
        skill = get_skill("crimson_veil")

        assert get_melee_buff_multiplier(bk) == 1.0  # before
        resolve_buff(bk, skill)
        assert get_melee_buff_multiplier(bk) == pytest.approx(1.3)

    def test_crimson_veil_buff_affects_blood_strike(self, loaded_skills):
        """Crimson Veil buff multiplier increases Blood Strike damage."""
        bk = _make_player(hp=80, max_hp=100)
        enemy = _make_enemy(hp=80, armor=0)
        players = _make_players(bk, enemy)

        # Apply Crimson Veil first
        veil = get_skill("crimson_veil")
        resolve_buff(bk, veil)

        # Then use Blood Strike
        strike = get_skill("blood_strike")
        result = resolve_lifesteal_damage(bk, 6, 5, strike, players, set(), target_id="enemy1")

        # 16 * 1.3 * 1.4 = 29.12 → 29
        assert result.damage_dealt == 29

    def test_crimson_veil_sets_cooldown(self, loaded_skills):
        """Crimson Veil sets cooldown to 6."""
        bk = _make_player()
        skill = get_skill("crimson_veil")

        resolve_buff(bk, skill)

        assert bk.cooldowns.get("crimson_veil", 0) == 6


# ============================================================
# 3. Sanguine Burst (lifesteal_aoe)
# ============================================================

class TestSanguineBurstLifestealAoE:
    """Tests for resolve_lifesteal_aoe() — Sanguine Burst handler."""

    def test_sanguine_burst_hits_adjacent_enemies(self, loaded_skills):
        """Sanguine Burst hits all enemies within 1 tile of caster."""
        bk = _make_player(hp=80, max_hp=100)
        e1 = _make_enemy(player_id="e1", username="Skel1", hp=50, armor=0, x=6, y=5)
        e2 = _make_enemy(player_id="e2", username="Skel2", hp=50, armor=0, x=4, y=5)
        e3 = _make_enemy(player_id="e3", username="Skel3", hp=50, armor=0, x=5, y=6)
        players = _make_players(bk, e1, e2, e3)
        skill = get_skill("sanguine_burst")

        result = resolve_lifesteal_aoe(bk, skill, players, set())

        assert result.success is True
        # Should hit all 3 enemies
        assert result.buff_applied["hits"] == 3

    def test_sanguine_burst_does_not_hit_allies(self, loaded_skills):
        """Sanguine Burst does not damage same-team allies."""
        bk = _make_player(hp=80, max_hp=100)
        ally = _make_enemy(player_id="ally1", username="Ally", team="team_1", x=6, y=5, hp=50)
        enemy = _make_enemy(player_id="e1", username="Enemy", team="team_2", x=4, y=5, hp=50, armor=0)
        players = _make_players(bk, ally, enemy)
        skill = get_skill("sanguine_burst")

        result = resolve_lifesteal_aoe(bk, skill, players, set())

        assert result.buff_applied["hits"] == 1
        assert ally.hp == 50  # Ally not damaged

    def test_sanguine_burst_deals_correct_damage(self, loaded_skills):
        """Sanguine Burst deals 0.7x melee damage per target."""
        bk = _make_player(hp=80, max_hp=100)
        enemy = _make_enemy(hp=50, armor=0, x=6, y=5)
        players = _make_players(bk, enemy)
        skill = get_skill("sanguine_burst")

        result = resolve_lifesteal_aoe(bk, skill, players, set())

        # 16 * 0.7 = 11.2 → 11 damage (0 armor)
        assert result.damage_dealt == 11
        assert enemy.hp == 50 - 11

    def test_sanguine_burst_heals_percentage_of_total(self, loaded_skills):
        """Sanguine Burst heals for 50% of TOTAL damage dealt."""
        bk = _make_player(hp=70, max_hp=100)
        e1 = _make_enemy(player_id="e1", hp=50, armor=0, x=6, y=5)
        e2 = _make_enemy(player_id="e2", hp=50, armor=0, x=4, y=5)
        e3 = _make_enemy(player_id="e3", hp=50, armor=0, x=5, y=6)
        players = _make_players(bk, e1, e2, e3)
        skill = get_skill("sanguine_burst")

        result = resolve_lifesteal_aoe(bk, skill, players, set())

        # 3 × 11 = 33 total damage, heal = floor(33 * 0.5) = 16
        total_dmg = result.damage_dealt
        expected_heal = int(total_dmg * 0.5)
        assert bk.hp == 70 + expected_heal

    def test_sanguine_burst_heal_scales_with_enemy_count(self, loaded_skills):
        """More enemies hit = more healing (core design intent)."""
        # 1 enemy
        bk1 = _make_player(player_id="bk1", hp=70, max_hp=100)
        e1 = _make_enemy(player_id="e1", hp=50, armor=0, x=6, y=5)
        skill = get_skill("sanguine_burst")
        resolve_lifesteal_aoe(bk1, skill, _make_players(bk1, e1), set())
        heal_1 = bk1.hp - 70

        # 3 enemies
        bk3 = _make_player(player_id="bk3", hp=70, max_hp=100)
        e1 = _make_enemy(player_id="e1", hp=50, armor=0, x=6, y=5)
        e2 = _make_enemy(player_id="e2", hp=50, armor=0, x=4, y=5)
        e3 = _make_enemy(player_id="e3", hp=50, armor=0, x=5, y=6)
        resolve_lifesteal_aoe(bk3, skill, _make_players(bk3, e1, e2, e3), set())
        heal_3 = bk3.hp - 70

        assert heal_3 > heal_1

    def test_sanguine_burst_respects_armor(self, loaded_skills):
        """Sanguine Burst damage is reduced by each target's armor (min 1)."""
        bk = _make_player(hp=80, max_hp=100)
        enemy = _make_enemy(hp=50, armor=4, x=6, y=5)
        players = _make_players(bk, enemy)
        skill = get_skill("sanguine_burst")

        result = resolve_lifesteal_aoe(bk, skill, players, set())

        # 16 * 0.7 = 11 - 4 armor = 7
        assert result.damage_dealt == 7

    def test_sanguine_burst_no_enemies_in_range(self, loaded_skills):
        """Sanguine Burst with no enemies returns success but no damage."""
        bk = _make_player(hp=80, max_hp=100)
        enemy = _make_enemy(hp=50, x=10, y=10)  # far away
        players = _make_players(bk, enemy)
        skill = get_skill("sanguine_burst")

        result = resolve_lifesteal_aoe(bk, skill, players, set())

        assert result.success is True
        assert "no enemies" in result.message.lower()

    def test_sanguine_burst_sets_cooldown(self, loaded_skills):
        """Sanguine Burst sets cooldown to 7."""
        bk = _make_player(hp=80, max_hp=100)
        enemy = _make_enemy(hp=50, armor=0, x=6, y=5)
        players = _make_players(bk, enemy)
        skill = get_skill("sanguine_burst")

        resolve_lifesteal_aoe(bk, skill, players, set())

        assert bk.cooldowns.get("sanguine_burst", 0) == 7

    def test_sanguine_burst_kills_register(self, loaded_skills):
        """Sanguine Burst correctly reports kills."""
        bk = _make_player(hp=80, max_hp=100)
        e1 = _make_enemy(player_id="e1", hp=3, armor=0, x=6, y=5)  # Will die
        e2 = _make_enemy(player_id="e2", hp=50, armor=0, x=4, y=5)  # Survives
        players = _make_players(bk, e1, e2)
        skill = get_skill("sanguine_burst")

        result = resolve_lifesteal_aoe(bk, skill, players, set())

        assert result.killed is True
        assert e1.is_alive is False
        assert e2.is_alive is True
        assert result.buff_applied["kills"] == 1

    def test_sanguine_burst_does_not_hit_self(self, loaded_skills):
        """Sanguine Burst does not damage the caster (dist > 0 check)."""
        bk = _make_player(hp=80, max_hp=100)
        enemy = _make_enemy(hp=50, armor=0, x=6, y=5)
        players = _make_players(bk, enemy)
        skill = get_skill("sanguine_burst")

        old_hp = bk.hp
        resolve_lifesteal_aoe(bk, skill, players, set())

        # Caster HP should only go UP (from heal), not down
        assert bk.hp >= old_hp

    def test_sanguine_burst_does_not_hit_distant_enemies(self, loaded_skills):
        """Sanguine Burst only hits enemies within radius 1 (Chebyshev)."""
        bk = _make_player(hp=80, max_hp=100)
        close = _make_enemy(player_id="close", hp=50, armor=0, x=6, y=5)  # dist 1, hit
        far = _make_enemy(player_id="far", hp=50, armor=0, x=8, y=5)   # dist 3, miss
        players = _make_players(bk, close, far)
        skill = get_skill("sanguine_burst")

        result = resolve_lifesteal_aoe(bk, skill, players, set())

        assert result.buff_applied["hits"] == 1
        assert far.hp == 50  # Not hit


# ============================================================
# 4. Blood Frenzy (conditional_buff)
# ============================================================

class TestBloodFrenzyConditionalBuff:
    """Tests for resolve_conditional_buff() — Blood Frenzy handler."""

    def test_blood_frenzy_activates_below_40_pct(self, loaded_skills):
        """Blood Frenzy activates when HP < 40% of max."""
        bk = _make_player(hp=35, max_hp=100)  # 35% HP
        skill = get_skill("blood_frenzy")

        result = resolve_conditional_buff(bk, skill)

        assert result.success is True

    def test_blood_frenzy_fails_at_40_pct(self, loaded_skills):
        """Blood Frenzy FAILS when HP is exactly 40% (must be BELOW)."""
        bk = _make_player(hp=40, max_hp=100)  # exactly 40%
        skill = get_skill("blood_frenzy")

        result = resolve_conditional_buff(bk, skill)

        assert result.success is False
        assert "not wounded enough" in result.message.lower()

    def test_blood_frenzy_fails_above_40_pct(self, loaded_skills):
        """Blood Frenzy FAILS when HP > 40%."""
        bk = _make_player(hp=60, max_hp=100)
        skill = get_skill("blood_frenzy")

        result = resolve_conditional_buff(bk, skill)

        assert result.success is False

    def test_blood_frenzy_no_cooldown_on_failure(self, loaded_skills):
        """Blood Frenzy does NOT consume cooldown when it fails."""
        bk = _make_player(hp=60, max_hp=100)
        skill = get_skill("blood_frenzy")

        resolve_conditional_buff(bk, skill)

        assert bk.cooldowns.get("blood_frenzy", 0) == 0

    def test_blood_frenzy_heals_15_hp(self, loaded_skills):
        """Blood Frenzy heals 15 HP instantly on activation."""
        bk = _make_player(hp=30, max_hp=100)
        skill = get_skill("blood_frenzy")

        resolve_conditional_buff(bk, skill)

        assert bk.hp == 30 + 15

    def test_blood_frenzy_heal_capped_at_max_hp(self, loaded_skills):
        """Blood Frenzy heal does not exceed max HP."""
        bk = _make_player(hp=39, max_hp=100)  # 39% HP — barely qualifies
        skill = get_skill("blood_frenzy")

        resolve_conditional_buff(bk, skill)

        assert bk.hp == 39 + 15  # 54, within max

        # Edge case: low max_hp where heal would exceed
        bk2 = _make_player(hp=5, max_hp=15)  # 33% HP
        resolve_conditional_buff(bk2, skill)
        assert bk2.hp == 15  # capped

    def test_blood_frenzy_applies_damage_buff(self, loaded_skills):
        """Blood Frenzy applies melee_damage_multiplier 1.5 for 3 turns."""
        bk = _make_player(hp=30, max_hp=100)
        skill = get_skill("blood_frenzy")

        resolve_conditional_buff(bk, skill)

        melee_buffs = [b for b in bk.active_buffs if b.get("stat") == "melee_damage_multiplier"]
        assert len(melee_buffs) == 1
        assert melee_buffs[0]["magnitude"] == 1.5
        assert melee_buffs[0]["turns_remaining"] == 3

    def test_blood_frenzy_sets_cooldown_on_success(self, loaded_skills):
        """Blood Frenzy sets cooldown to 8 on successful activation."""
        bk = _make_player(hp=30, max_hp=100)
        skill = get_skill("blood_frenzy")

        resolve_conditional_buff(bk, skill)

        assert bk.cooldowns.get("blood_frenzy", 0) == 8

    def test_blood_frenzy_stacks_with_crimson_veil(self, loaded_skills):
        """Blood Frenzy + Crimson Veil stack multiplicatively (1.3 × 1.5 = 1.95)."""
        bk = _make_player(hp=30, max_hp=100, active_buffs=[
            {"buff_id": "crimson_veil", "type": "buff", "stat": "melee_damage_multiplier",
             "magnitude": 1.3, "turns_remaining": 2}
        ])
        skill = get_skill("blood_frenzy")

        resolve_conditional_buff(bk, skill)

        mult = get_melee_buff_multiplier(bk)
        assert mult == pytest.approx(1.3 * 1.5)  # 1.95


# ============================================================
# 5. Dispatcher Integration (resolve_skill_action)
# ============================================================

class TestDispatcherIntegration:
    """Tests for resolve_skill_action() routing to new Blood Knight handlers."""

    def _make_action(self, skill_id, target_x=None, target_y=None, target_id=None):
        """Create a mock action object."""
        class MockAction:
            pass
        action = MockAction()
        action.skill_id = skill_id
        action.target_x = target_x
        action.target_y = target_y
        action.target_id = target_id
        return action

    def test_dispatcher_routes_lifesteal_damage(self, loaded_skills):
        """resolve_skill_action routes 'lifesteal_damage' to resolve_lifesteal_damage."""
        bk = _make_player(hp=80, max_hp=100)
        enemy = _make_enemy(hp=50, armor=0, x=6, y=5)
        players = _make_players(bk, enemy)
        skill = get_skill("blood_strike")
        action = self._make_action("blood_strike", target_x=6, target_y=5, target_id="enemy1")

        result = resolve_skill_action(bk, action, skill, players, set())

        assert result.success is True
        assert result.damage_dealt == 22  # 16 * 1.4

    def test_dispatcher_routes_lifesteal_aoe(self, loaded_skills):
        """resolve_skill_action routes 'lifesteal_aoe' to resolve_lifesteal_aoe."""
        bk = _make_player(hp=80, max_hp=100)
        enemy = _make_enemy(hp=50, armor=0, x=6, y=5)
        players = _make_players(bk, enemy)
        skill = get_skill("sanguine_burst")
        action = self._make_action("sanguine_burst")

        result = resolve_skill_action(bk, action, skill, players, set())

        assert result.success is True
        assert result.damage_dealt == 11  # 16 * 0.7

    def test_dispatcher_routes_conditional_buff(self, loaded_skills):
        """resolve_skill_action routes 'conditional_buff' to resolve_conditional_buff."""
        bk = _make_player(hp=30, max_hp=100)
        players = _make_players(bk)
        skill = get_skill("blood_frenzy")
        action = self._make_action("blood_frenzy")

        result = resolve_skill_action(bk, action, skill, players, set())

        assert result.success is True
        assert bk.hp == 45  # 30 + 15 heal

    def test_dispatcher_routes_crimson_veil_buff(self, loaded_skills):
        """resolve_skill_action routes Crimson Veil (buff type) to resolve_buff."""
        bk = _make_player()
        players = _make_players(bk)
        skill = get_skill("crimson_veil")
        action = self._make_action("crimson_veil")

        result = resolve_skill_action(bk, action, skill, players, set())

        assert result.success is True
        assert len(bk.active_buffs) == 2  # buff + hot


# ============================================================
# 6. Edge Cases & Combo Scenarios
# ============================================================

class TestBloodKnightCombos:
    """Tests for combo scenarios and edge cases."""

    def test_crimson_veil_plus_blood_strike_combo(self, loaded_skills):
        """Full combo: Crimson Veil buff → Blood Strike = boosted damage + boosted heal."""
        bk = _make_player(hp=70, max_hp=100)
        enemy = _make_enemy(hp=80, armor=4, x=6, y=5)
        players = _make_players(bk, enemy)

        # Apply Crimson Veil
        veil = get_skill("crimson_veil")
        resolve_buff(bk, veil)

        # Blood Strike with buff
        strike = get_skill("blood_strike")
        result = resolve_lifesteal_damage(bk, 6, 5, strike, players, set(), target_id="enemy1")

        # 16 * 1.3 * 1.4 = 29.12 → 29 - 4 armor = 25
        assert result.damage_dealt == 25
        # heal = floor(25 * 0.4) = 10
        assert bk.hp == 70 + 10

    def test_full_stack_blood_frenzy_crimson_veil_blood_strike(self, loaded_skills):
        """Triple stack: Crimson Veil + Blood Frenzy → Blood Strike damage."""
        bk = _make_player(hp=30, max_hp=100)
        enemy = _make_enemy(hp=100, armor=0, x=6, y=5)
        players = _make_players(bk, enemy)

        # Apply Crimson Veil
        veil = get_skill("crimson_veil")
        resolve_buff(bk, veil)

        # Apply Blood Frenzy (hp=30 < 40%)
        frenzy = get_skill("blood_frenzy")
        resolve_conditional_buff(bk, frenzy)
        # HP is now 30 + 15 = 45

        # Blood Strike with both buffs
        strike = get_skill("blood_strike")
        result = resolve_lifesteal_damage(bk, 6, 5, strike, players, set(), target_id="enemy1")

        # 16 * 1.3 * 1.5 * 1.4 = 43.68 → int(16*1.3*1.5) = 31, then int(31*1.4) = 43
        # Actually need to trace through the code carefully:
        # melee_mult = 1.3 * 1.5 = 1.95
        # raw = int(16 * 1.95 * 1.4) = int(43.68) = 43
        assert result.damage_dealt == 43

    def test_sanguine_burst_with_crimson_veil_buff(self, loaded_skills):
        """Sanguine Burst damage is boosted by Crimson Veil melee buff."""
        bk = _make_player(hp=70, max_hp=100, active_buffs=[
            {"buff_id": "crimson_veil", "type": "buff", "stat": "melee_damage_multiplier",
             "magnitude": 1.3, "turns_remaining": 3}
        ])
        enemy = _make_enemy(hp=50, armor=0, x=6, y=5)
        players = _make_players(bk, enemy)
        skill = get_skill("sanguine_burst")

        result = resolve_lifesteal_aoe(bk, skill, players, set())

        # 16 * 1.3 (buff) * 0.7 (skill) = 14.56 → int = 14
        assert result.damage_dealt == 14

    def test_crimson_veil_hot_expires_after_3_ticks(self, loaded_skills):
        """Crimson Veil HoT expires after 3 turns of tick_buffs()."""
        bk = _make_player(hp=50, max_hp=100)
        veil = get_skill("crimson_veil")
        resolve_buff(bk, veil)

        # Tick 3 times
        tick_buffs(bk)  # turn 1: hp 56
        tick_buffs(bk)  # turn 2: hp 62
        tick_buffs(bk)  # turn 3: hp 68, buffs expire

        assert bk.hp == 68
        # Both buffs should be expired
        assert len(bk.active_buffs) == 0

    def test_blood_frenzy_at_exact_1_hp(self, loaded_skills):
        """Blood Frenzy works at critically low HP (1 HP)."""
        bk = _make_player(hp=1, max_hp=100)
        skill = get_skill("blood_frenzy")

        result = resolve_conditional_buff(bk, skill)

        assert result.success is True
        assert bk.hp == 16  # 1 + 15

    def test_sanguine_burst_heal_caps_at_max_hp(self, loaded_skills):
        """Sanguine Burst lifesteal doesn't exceed max HP."""
        bk = _make_player(hp=98, max_hp=100)
        e1 = _make_enemy(player_id="e1", hp=50, armor=0, x=6, y=5)
        e2 = _make_enemy(player_id="e2", hp=50, armor=0, x=4, y=5)
        e3 = _make_enemy(player_id="e3", hp=50, armor=0, x=5, y=6)
        players = _make_players(bk, e1, e2, e3)
        skill = get_skill("sanguine_burst")

        resolve_lifesteal_aoe(bk, skill, players, set())

        assert bk.hp == 100  # capped
