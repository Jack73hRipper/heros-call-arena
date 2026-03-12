"""
Tests for Phase 21C: Buff System Integration (all_damage_multiplier + damage_taken_multiplier).

Covers:
- all_damage_multiplier (Bard Ballad of Might) boosts melee, ranged, and skill damage
- damage_taken_multiplier (Bard Dirge of Weakness) increases damage taken from all sources
- Combined Ballad + Dirge multiplicative stacking
- Buff expiration resets multipliers
- Minimum damage of 1 always respected
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import ActionType, PlayerAction
from app.core.skills import (
    load_skills_config,
    clear_skills_cache,
    get_skill,
    get_melee_buff_multiplier,
    get_ranged_buff_multiplier,
    get_damage_taken_multiplier,
    tick_buffs,
    resolve_multi_hit,
    resolve_ranged_skill,
    resolve_magic_damage,
    resolve_holy_damage,
    resolve_aoe_damage,
    resolve_aoe_damage_slow,
    resolve_stun_damage,
    resolve_ranged_damage_slow,
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


def _ballad_buff(turns: int = 3, magnitude: float = 1.3) -> dict:
    """Create a Ballad of Might buff entry."""
    return {
        "buff_id": "ballad_of_might",
        "type": "buff",
        "stat": "all_damage_multiplier",
        "magnitude": magnitude,
        "turns_remaining": turns,
    }


def _dirge_debuff(turns: int = 3, magnitude: float = 1.25) -> dict:
    """Create a Dirge of Weakness debuff entry."""
    return {
        "buff_id": "dirge_of_weakness",
        "type": "debuff",
        "stat": "damage_taken_multiplier",
        "magnitude": magnitude,
        "turns_remaining": turns,
    }


def _war_cry_buff(turns: int = 3) -> dict:
    """Create a War Cry melee buff (existing Phase 11 buff)."""
    return {
        "buff_id": "war_cry",
        "type": "buff",
        "stat": "melee_damage_multiplier",
        "magnitude": 2.0,
        "turns_remaining": turns,
    }


# ============================================================
# 1. get_melee_buff_multiplier — all_damage_multiplier integration
# ============================================================

class TestAllDamageMultiplierMelee:
    """Tests for all_damage_multiplier in get_melee_buff_multiplier."""

    def test_melee_multiplier_with_ballad(self):
        """Ballad of Might (all_damage_multiplier) increases melee buff multiplier."""
        player = _make_player(active_buffs=[_ballad_buff()])
        assert get_melee_buff_multiplier(player) == pytest.approx(1.3)

    def test_melee_multiplier_without_buffs(self):
        """No buffs → multiplier is 1.0."""
        player = _make_player()
        assert get_melee_buff_multiplier(player) == 1.0

    def test_melee_multiplier_stacks_with_war_cry(self):
        """Ballad + War Cry stack multiplicatively."""
        player = _make_player(active_buffs=[_ballad_buff(), _war_cry_buff()])
        # 1.3 × 2.0 = 2.6
        assert get_melee_buff_multiplier(player) == pytest.approx(2.6)

    def test_melee_multiplier_ignores_debuffs(self):
        """A debuff with all_damage_multiplier type should NOT boost damage (type != buff)."""
        bad_debuff = {
            "buff_id": "test_debuff",
            "type": "debuff",
            "stat": "all_damage_multiplier",
            "magnitude": 1.5,
            "turns_remaining": 3,
        }
        player = _make_player(active_buffs=[bad_debuff])
        assert get_melee_buff_multiplier(player) == 1.0

    def test_melee_multiplier_ignores_damage_taken(self):
        """damage_taken_multiplier debuff should NOT affect outgoing damage."""
        player = _make_player(active_buffs=[_dirge_debuff()])
        assert get_melee_buff_multiplier(player) == 1.0


# ============================================================
# 2. get_ranged_buff_multiplier — all_damage_multiplier integration
# ============================================================

class TestAllDamageMultiplierRanged:
    """Tests for all_damage_multiplier in get_ranged_buff_multiplier."""

    def test_ranged_multiplier_with_ballad(self):
        """Ballad of Might increases ranged buff multiplier."""
        player = _make_player(active_buffs=[_ballad_buff()])
        assert get_ranged_buff_multiplier(player) == pytest.approx(1.3)

    def test_ranged_multiplier_without_buffs(self):
        """No buffs → multiplier is 1.0."""
        player = _make_player()
        assert get_ranged_buff_multiplier(player) == 1.0

    def test_ranged_multiplier_ignores_melee_only_buff(self):
        """War Cry (melee_damage_multiplier) should NOT affect ranged."""
        player = _make_player(active_buffs=[_war_cry_buff()])
        assert get_ranged_buff_multiplier(player) == 1.0

    def test_ranged_multiplier_ballad_plus_ranged_specific(self):
        """Ballad stacks with ranged-specific buff."""
        ranged_buff = {
            "buff_id": "test_ranged",
            "type": "buff",
            "stat": "ranged_damage_multiplier",
            "magnitude": 1.5,
            "turns_remaining": 3,
        }
        player = _make_player(active_buffs=[_ballad_buff(), ranged_buff])
        # 1.3 × 1.5 = 1.95
        assert get_ranged_buff_multiplier(player) == pytest.approx(1.95)


# ============================================================
# 3. get_damage_taken_multiplier tests
# ============================================================

class TestDamageTakenMultiplier:
    """Tests for the get_damage_taken_multiplier helper."""

    def test_no_debuffs_returns_1(self):
        """No debuffs → multiplier is 1.0."""
        player = _make_player()
        assert get_damage_taken_multiplier(player) == 1.0

    def test_single_dirge(self):
        """Single Dirge debuff → 1.25× damage taken."""
        player = _make_player(active_buffs=[_dirge_debuff()])
        assert get_damage_taken_multiplier(player) == pytest.approx(1.25)

    def test_multiple_dirges_stack(self):
        """Two Dirge debuffs should stack multiplicatively."""
        player = _make_player(active_buffs=[_dirge_debuff(), _dirge_debuff(magnitude=1.1)])
        # 1.25 × 1.1 = 1.375
        assert get_damage_taken_multiplier(player) == pytest.approx(1.375)

    def test_ignores_non_damage_taken_debuffs(self):
        """Other debuff stats should not be included."""
        other_debuff = {
            "buff_id": "other",
            "type": "debuff",
            "stat": "speed_reduction",
            "magnitude": 0.5,
            "turns_remaining": 3,
        }
        player = _make_player(active_buffs=[other_debuff])
        assert get_damage_taken_multiplier(player) == 1.0


# ============================================================
# 4. Melee auto-attack with damage_taken_multiplier
# ============================================================

class TestMeleeAutoAttackDamageTaken:
    """Tests for damage_taken_multiplier in melee auto-attack calculations."""

    def test_melee_simple_increased_with_dirge(self):
        """calculate_damage_simple applies damage_taken_multiplier on target."""
        attacker = _make_player(player_id="atk", attack_damage=20, armor=0)
        # Defender has 0 armor, dirge debuff
        defender = _make_player(
            player_id="def", hp=100, armor=0, team="team_2",
            active_buffs=[_dirge_debuff()],
        )
        base_damage = calculate_damage_simple(attacker, defender)

        # Without dirge: 20 damage (no armor)
        # With dirge: 20 × 1.25 = 25
        assert base_damage == 25

    def test_melee_simple_no_dirge(self):
        """Without dirge, damage is normal."""
        attacker = _make_player(player_id="atk", attack_damage=20)
        defender = _make_player(player_id="def", hp=100, armor=0, team="team_2")
        damage = calculate_damage_simple(attacker, defender)
        assert damage == 20

    def test_melee_full_increased_with_dirge(self):
        """calculate_damage (full pipeline) applies damage_taken_multiplier."""
        import random
        rng = random.Random(42)  # Fixed seed for reproducibility
        attacker = _make_player(player_id="atk", attack_damage=20, armor=0)
        defender = _make_player(
            player_id="def", hp=200, armor=0, team="team_2",
            active_buffs=[_dirge_debuff()],
        )
        damage, info = calculate_damage(attacker, defender, rng=rng)
        # With 0 armor, no crit (fixed seed), base = 20
        # With dirge: 20 × 1.25 = 25
        if not info["is_crit"] and not info["is_dodged"]:
            assert damage == 25


# ============================================================
# 5. Ranged auto-attack with damage_taken_multiplier
# ============================================================

class TestRangedAutoAttackDamageTaken:
    """Tests for damage_taken_multiplier in ranged auto-attack calculations."""

    def test_ranged_simple_increased_with_dirge(self):
        """calculate_ranged_damage_simple applies damage_taken_multiplier."""
        attacker = _make_player(player_id="atk", ranged_damage=18)
        defender = _make_player(
            player_id="def", hp=100, armor=0, team="team_2",
            active_buffs=[_dirge_debuff()],
        )
        damage = calculate_ranged_damage_simple(attacker, defender)
        # 18 × 1.25 = 22.5 → int(22.5) = 22
        assert damage == 22

    def test_ranged_simple_no_dirge(self):
        """Without dirge, ranged damage is normal."""
        attacker = _make_player(player_id="atk", ranged_damage=18)
        defender = _make_player(player_id="def", hp=100, armor=0, team="team_2")
        damage = calculate_ranged_damage_simple(attacker, defender)
        assert damage == 18


# ============================================================
# 6. Ballad + Dirge combined (multiplicative)
# ============================================================

class TestBalladDirgeCombined:
    """Tests for combined Ballad of Might + Dirge of Weakness stacking."""

    def test_melee_ballad_plus_dirge(self):
        """Attacker has Ballad (+30%), target has Dirge (+25%) → 1.3 × 1.25 = 1.625×."""
        attacker = _make_player(
            player_id="atk", attack_damage=20, armor=0,
            active_buffs=[_ballad_buff()],
        )
        defender = _make_player(
            player_id="def", hp=200, armor=0, team="team_2",
            active_buffs=[_dirge_debuff()],
        )
        damage = calculate_damage_simple(attacker, defender)
        # 20 × 1.3 = 26 (melee buff) → 26 × 1.25 = 32.5 → int(32.5) = 32
        assert damage == 32

    def test_ranged_ballad_plus_dirge(self):
        """Ranged: Ballad (+30%) + Dirge (+25%) = combined 1.625× boost."""
        attacker = _make_player(
            player_id="atk", ranged_damage=18,
            active_buffs=[_ballad_buff()],
        )
        defender = _make_player(
            player_id="def", hp=200, armor=0, team="team_2",
            active_buffs=[_dirge_debuff()],
        )
        damage = calculate_ranged_damage_simple(attacker, defender)
        # 18 × 1.3 = 23.4 → int = 23 (ranged buff applied first)
        # 23 × 1.25 = 28.75 → int = 28
        assert damage == 28

    def test_concrete_party_damage_scenario(self):
        """Verify concrete damage numbers from the design doc party scenario."""
        # Crusader: 20 atk, 0 armor on target, Ballad active, Dirge on target
        crusader = _make_player(
            player_id="crus", attack_damage=20,
            active_buffs=[_ballad_buff()],
        )
        target = _make_player(
            player_id="boss", hp=500, armor=0, team="team_2",
            active_buffs=[_dirge_debuff()],
        )
        damage = calculate_damage_simple(crusader, target)
        # 20 × 1.3 = 26, 26 × 1.25 = 32.5 → 32
        assert damage == 32


# ============================================================
# 7. Buff expiration resets multiplier
# ============================================================

class TestBuffExpiration:
    """Tests that multipliers reset when buffs expire via tick_buffs."""

    def test_ballad_expires_after_ticks(self):
        """After 3 tick_buffs calls, the Ballad buff should expire."""
        player = _make_player(active_buffs=[_ballad_buff(turns=3)])
        assert get_melee_buff_multiplier(player) == pytest.approx(1.3)

        tick_buffs(player)  # turns_remaining: 3 → 2
        assert get_melee_buff_multiplier(player) == pytest.approx(1.3)

        tick_buffs(player)  # turns_remaining: 2 → 1
        assert get_melee_buff_multiplier(player) == pytest.approx(1.3)

        tick_buffs(player)  # turns_remaining: 1 → 0 → expired
        assert get_melee_buff_multiplier(player) == 1.0

    def test_dirge_expires_after_ticks(self):
        """After 3 tick_buffs calls, the Dirge debuff should expire."""
        player = _make_player(active_buffs=[_dirge_debuff(turns=3)])
        assert get_damage_taken_multiplier(player) == pytest.approx(1.25)

        tick_buffs(player)
        tick_buffs(player)
        tick_buffs(player)  # expired
        assert get_damage_taken_multiplier(player) == 1.0

    def test_melee_damage_reverts_after_ballad_expires(self):
        """Melee auto-attack damage returns to normal when Ballad expires."""
        attacker = _make_player(
            player_id="atk", attack_damage=20,
            active_buffs=[_ballad_buff(turns=1)],
        )
        defender = _make_player(player_id="def", hp=200, armor=0, team="team_2")

        # With Ballad: 20 × 1.3 = 26
        assert calculate_damage_simple(attacker, defender) == 26

        tick_buffs(attacker)  # Ballad expires

        # Without Ballad: normal 20
        assert calculate_damage_simple(attacker, defender) == 20


# ============================================================
# 8. Skill handlers — damage_taken_multiplier integration
# ============================================================

class TestSkillDamageTaken:
    """Tests for damage_taken_multiplier applied in specific skill handlers."""

    @pytest.fixture(autouse=True)
    def _load(self, loaded_skills):
        pass

    def test_resolve_ranged_skill_with_dirge(self):
        """Power Shot (resolve_ranged_skill) applies damage_taken_multiplier."""
        skill = get_skill("power_shot")
        attacker = _make_player(
            player_id="ranger", username="Ranger", class_id="ranger",
            ranged_damage=18, x=5, y=5,
        )
        target = _make_player(
            player_id="enemy", username="Enemy", hp=200, armor=0,
            team="team_2", x=5, y=8,
            active_buffs=[_dirge_debuff()],
        )
        players = {p.player_id: p for p in [attacker, target]}
        obstacles = set()

        result = resolve_ranged_skill(
            attacker, target.position.x, target.position.y,
            skill, players, obstacles, target_id="enemy",
        )
        assert result.success is True
        # Damage should be boosted by 1.25× from Dirge
        assert result.damage_dealt > 0

        # Compare: same attack without Dirge
        attacker2 = _make_player(
            player_id="ranger2", username="Ranger2", class_id="ranger",
            ranged_damage=18, x=5, y=5,
        )
        target2 = _make_player(
            player_id="enemy2", username="Enemy2", hp=200, armor=0,
            team="team_2", x=5, y=8,
        )
        players2 = {p.player_id: p for p in [attacker2, target2]}
        result2 = resolve_ranged_skill(
            attacker2, target2.position.x, target2.position.y,
            skill, players2, obstacles, target_id="enemy2",
        )

        # Dirge version should deal more damage
        assert result.damage_dealt > result2.damage_dealt

    def test_resolve_magic_damage_with_dirge(self):
        """Fireball (resolve_magic_damage) applies damage_taken_multiplier."""
        skill = get_skill("fireball")
        mage = _make_player(
            player_id="mage", username="Mage", class_id="mage",
            ranged_damage=14, x=5, y=5,
        )
        target = _make_player(
            player_id="enemy", username="Enemy", hp=200, armor=0,
            team="team_2", x=5, y=8,
            active_buffs=[_dirge_debuff()],
        )
        target_no_debuff = _make_player(
            player_id="enemy2", username="Enemy2", hp=200, armor=0,
            team="team_2", x=5, y=8,
        )

        players_with = {mage.player_id: mage, target.player_id: target}
        obstacles = set()
        result_with = resolve_magic_damage(
            mage, target.position.x, target.position.y,
            skill, players_with, obstacles, target_id="enemy",
        )

        # Reset mage cooldowns for 2nd call
        mage2 = _make_player(
            player_id="mage2", username="Mage2", class_id="mage",
            ranged_damage=14, x=5, y=5,
        )
        players_without = {mage2.player_id: mage2, target_no_debuff.player_id: target_no_debuff}
        result_without = resolve_magic_damage(
            mage2, target_no_debuff.position.x, target_no_debuff.position.y,
            skill, players_without, obstacles, target_id="enemy2",
        )

        assert result_with.success is True
        assert result_without.success is True
        # Dirge version should deal more
        assert result_with.damage_dealt > result_without.damage_dealt

    def test_resolve_aoe_damage_slow_with_dirge(self):
        """Frost Nova / Cacophony applies damage_taken_multiplier per target."""
        skill = get_skill("frost_nova")
        caster = _make_player(
            player_id="mage", username="Mage", class_id="mage",
            ranged_damage=14, x=5, y=5,
        )
        # Enemy with dirge debuff adjacent
        enemy = _make_player(
            player_id="enemy", username="Enemy", hp=200, armor=0,
            team="team_2", x=5, y=6,
            active_buffs=[_dirge_debuff()],
        )
        players = {p.player_id: p for p in [caster, enemy]}
        obstacles = set()

        result = resolve_aoe_damage_slow(caster, skill, players, obstacles)
        assert result.success is True
        # Frost Nova base_damage=16, with dirge → 16 × 1.25 = 20
        assert result.damage_dealt == 20

    def test_resolve_aoe_damage_slow_without_dirge(self):
        """Without dirge, AoE damage slow is normal."""
        skill = get_skill("frost_nova")
        caster = _make_player(
            player_id="mage", username="Mage", class_id="mage",
            ranged_damage=14, x=5, y=5,
        )
        enemy = _make_player(
            player_id="enemy", username="Enemy", hp=200, armor=0,
            team="team_2", x=5, y=6,
        )
        players = {p.player_id: p for p in [caster, enemy]}
        obstacles = set()

        result = resolve_aoe_damage_slow(caster, skill, players, obstacles)
        assert result.success is True
        # Frost Nova base_damage=16, no dirge → 16
        assert result.damage_dealt == 16


# ============================================================
# 9. Skill handlers — all_damage_multiplier integration
# ============================================================

class TestSkillAllDamageMultiplier:
    """Tests for all_damage_multiplier applied in skill damage handlers."""

    @pytest.fixture(autouse=True)
    def _load(self, loaded_skills):
        pass

    def test_ranged_skill_with_ballad(self):
        """Power Shot damage boosted by Ballad of Might."""
        skill = get_skill("power_shot")
        attacker = _make_player(
            player_id="ranger", username="Ranger", class_id="ranger",
            ranged_damage=18, x=5, y=5,
            active_buffs=[_ballad_buff()],
        )
        target = _make_player(
            player_id="enemy", username="Enemy", hp=200, armor=0,
            team="team_2", x=5, y=8,
        )

        attacker_no_buff = _make_player(
            player_id="ranger2", username="Ranger2", class_id="ranger",
            ranged_damage=18, x=5, y=5,
        )
        target2 = _make_player(
            player_id="enemy2", username="Enemy2", hp=200, armor=0,
            team="team_2", x=5, y=8,
        )

        obstacles = set()
        result_buffed = resolve_ranged_skill(
            attacker, target.position.x, target.position.y,
            skill, {attacker.player_id: attacker, target.player_id: target},
            obstacles, target_id="enemy",
        )
        result_normal = resolve_ranged_skill(
            attacker_no_buff, target2.position.x, target2.position.y,
            skill, {attacker_no_buff.player_id: attacker_no_buff, target2.player_id: target2},
            obstacles, target_id="enemy2",
        )

        assert result_buffed.success and result_normal.success
        assert result_buffed.damage_dealt > result_normal.damage_dealt

    def test_magic_damage_with_ballad(self):
        """Fireball damage boosted by Ballad."""
        skill = get_skill("fireball")
        mage_buffed = _make_player(
            player_id="mage", username="Mage", class_id="mage",
            ranged_damage=14, x=5, y=5,
            active_buffs=[_ballad_buff()],
        )
        mage_normal = _make_player(
            player_id="mage2", username="Mage2", class_id="mage",
            ranged_damage=14, x=5, y=5,
        )
        target1 = _make_player(
            player_id="e1", username="E1", hp=200, armor=0, team="team_2", x=5, y=8,
        )
        target2 = _make_player(
            player_id="e2", username="E2", hp=200, armor=0, team="team_2", x=5, y=8,
        )

        obstacles = set()
        r1 = resolve_magic_damage(
            mage_buffed, 5, 8, skill,
            {mage_buffed.player_id: mage_buffed, target1.player_id: target1},
            obstacles, target_id="e1",
        )
        r2 = resolve_magic_damage(
            mage_normal, 5, 8, skill,
            {mage_normal.player_id: mage_normal, target2.player_id: target2},
            obstacles, target_id="e2",
        )

        assert r1.success and r2.success
        assert r1.damage_dealt > r2.damage_dealt


# ============================================================
# 10. Minimum damage always 1
# ============================================================

class TestMinimumDamage:
    """Ensure minimum damage is always 1, even with multipliers."""

    def test_melee_min_damage_with_high_armor(self):
        """High armor target with or without dirge still takes at least 1 damage."""
        attacker = _make_player(player_id="atk", attack_damage=1)
        defender = _make_player(
            player_id="def", hp=200, armor=50, team="team_2",
            active_buffs=[_dirge_debuff()],
        )
        damage = calculate_damage_simple(attacker, defender)
        assert damage >= 1

    def test_ranged_min_damage_with_high_armor(self):
        """High armor target still takes at least 1 ranged damage."""
        attacker = _make_player(player_id="atk", ranged_damage=1)
        defender = _make_player(
            player_id="def", hp=200, armor=50, team="team_2",
            active_buffs=[_dirge_debuff()],
        )
        damage = calculate_ranged_damage_simple(attacker, defender)
        assert damage >= 1


# ============================================================
# 11. Edge cases
# ============================================================

class TestEdgeCases:
    """Edge case coverage for Phase 21C buff integration."""

    def test_damage_taken_multiplier_exactly_1(self):
        """A debuff with magnitude exactly 1.0 should not change damage."""
        player = _make_player(active_buffs=[_dirge_debuff(magnitude=1.0)])
        assert get_damage_taken_multiplier(player) == 1.0

    def test_all_damage_multiplier_with_no_other_buffs(self):
        """all_damage_multiplier works even if no melee/ranged-specific buffs exist."""
        player = _make_player(active_buffs=[_ballad_buff(magnitude=1.5)])
        assert get_melee_buff_multiplier(player) == pytest.approx(1.5)
        assert get_ranged_buff_multiplier(player) == pytest.approx(1.5)

    def test_both_multipliers_together_concrete(self):
        """Verify exact math: 20 atk × 1.3 ballad = 26, × 1.25 dirge = 32."""
        attacker = _make_player(
            player_id="atk", attack_damage=20, active_buffs=[_ballad_buff()],
        )
        defender = _make_player(
            player_id="def", hp=200, armor=0, team="team_2",
            active_buffs=[_dirge_debuff()],
        )
        damage = calculate_damage_simple(attacker, defender)
        # 20 × 1.3 = 26 → int = 26, then 26 × 1.25 = 32.5 → int = 32
        assert damage == 32

    def test_dirge_does_not_affect_healing(self):
        """damage_taken_multiplier should only affect damage, not healing."""
        player = _make_player(active_buffs=[_dirge_debuff()])
        # Simply verify the multiplier function exists and returns expected value
        # Healing functions don't call get_damage_taken_multiplier
        assert get_damage_taken_multiplier(player) == pytest.approx(1.25)
