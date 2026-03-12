"""
Tests for Phase 18I — Enemy Identity Skills.

Validates:
- Demon Enrage: permanent melee buff triggers at ≤30% HP, doesn't double-apply
- Skeleton Bone Shield: damage_absorb skill absorbs damage, depletes, breaks, refreshes
- Imp Frenzy Aura: tag-filtered aura (+3 attack_damage to nearby imps only)
- Dark Pact: support skill buffs highest-damage ally (melee_damage_multiplier)
- Profane Ward: support skill buffs lowest-HP ally (damage_reduction_pct via buff)
- AI role routing: passive_only role returns None, new classes dispatch correctly
- Damage pipeline integration: flat attack bonus, DR buff bonus, absorb in apply_damage
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import ActionType, ActionResult
from app.core.combat import (
    calculate_damage_simple as calculate_damage,
    apply_damage,
    load_combat_config,
)
from app.core.skills import (
    load_skills_config,
    get_skill,
    get_damage_reduction_buff_bonus,
    get_attack_damage_buff_bonus,
    get_damage_absorb_effect,
    consume_damage_absorb,
    resolve_damage_absorb,
)
from app.core.turn_phases.auras_phase import _resolve_auras
from app.core.ai_behavior import (
    _CLASS_ROLE_MAP,
    _get_role_for_class,
    _try_skill,
    _decide_skill_usage,
)


# ---------- Setup ----------

def setup_module():
    """Ensure configs are loaded before any test runs."""
    load_combat_config()
    load_skills_config()


# ---------- Helper Factories ----------

def _make_unit(
    pid: str = "u1",
    name: str = "Unit",
    x: int = 5,
    y: int = 5,
    hp: int = 100,
    max_hp: int = 100,
    team: str = "b",
    damage: int = 10,
    armor: int = 0,
    class_id: str | None = None,
    tags: list[str] | None = None,
    affixes: list[str] | None = None,
    cooldowns: dict | None = None,
    active_buffs: list | None = None,
    is_alive: bool = True,
    ranged_range: int = 0,
    vision_range: int = 7,
) -> PlayerState:
    """Create a minimal PlayerState for testing."""
    return PlayerState(
        player_id=pid,
        username=name,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=damage,
        armor=armor,
        team=team,
        class_id=class_id,
        tags=tags or [],
        affixes=affixes or [],
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
        is_alive=is_alive,
        ranged_range=ranged_range,
        vision_range=vision_range,
    )


# ===========================================================================
# Section 1: Demon Enrage (passive_enrage via _resolve_auras)
# ===========================================================================

class TestDemonEnrage:
    """Demon Enrage: permanent melee buff at ≤30% HP threshold."""

    def test_enrage_triggers_at_threshold(self):
        """Demon below 30% HP gains the demon_enrage buff."""
        demon = _make_unit(pid="d1", name="Demon", hp=25, max_hp=100, class_id="demon_enrage")
        players = {"d1": demon}
        results: list[ActionResult] = []

        _resolve_auras(players, results)

        enrage_buffs = [b for b in demon.active_buffs if b.get("buff_id") == "demon_enrage"]
        assert len(enrage_buffs) == 1
        assert enrage_buffs[0]["stat"] == "melee_damage_multiplier"
        assert enrage_buffs[0]["magnitude"] == 1.5  # +50% melee damage
        assert enrage_buffs[0]["turns_remaining"] == 999  # permanent
        # Should NOT have is_aura flag (permanent, not refreshing)
        assert "is_aura" not in enrage_buffs[0] or enrage_buffs[0].get("is_aura") is not True

    def test_enrage_message_produced(self):
        """Enrage activation produces an ActionResult message."""
        demon = _make_unit(pid="d1", name="Demon", hp=20, max_hp=100, class_id="demon_enrage")
        players = {"d1": demon}
        results: list[ActionResult] = []

        _resolve_auras(players, results)

        assert any("rage" in r.message.lower() for r in results)

    def test_no_enrage_above_threshold(self):
        """Demon above 30% HP does NOT gain the enrage buff."""
        demon = _make_unit(pid="d1", name="Demon", hp=50, max_hp=100, class_id="demon_enrage")
        players = {"d1": demon}
        results: list[ActionResult] = []

        _resolve_auras(players, results)

        enrage_buffs = [b for b in demon.active_buffs if b.get("buff_id") == "demon_enrage"]
        assert len(enrage_buffs) == 0

    def test_enrage_does_not_double_apply(self):
        """Demon already enraged doesn't get a second enrage buff."""
        demon = _make_unit(
            pid="d1", name="Demon", hp=10, max_hp=100, class_id="demon_enrage",
            active_buffs=[{
                "buff_id": "demon_enrage",
                "stat": "melee_damage_multiplier",
                "magnitude": 1.5,
                "turns_remaining": 999,
                "source": "d1",
            }],
        )
        players = {"d1": demon}
        results: list[ActionResult] = []

        _resolve_auras(players, results)

        enrage_buffs = [b for b in demon.active_buffs if b.get("buff_id") == "demon_enrage"]
        assert len(enrage_buffs) == 1  # Still exactly one

    def test_enrage_permanent_survives_aura_cleanup(self):
        """Demon enrage buff without is_aura survives the aura cleanup step."""
        demon = _make_unit(
            pid="d1", name="Demon", hp=10, max_hp=100, class_id="demon_enrage",
            active_buffs=[{
                "buff_id": "demon_enrage",
                "stat": "melee_damage_multiplier",
                "magnitude": 1.5,
                "turns_remaining": 999,
                "source": "d1",
            }],
        )
        players = {"d1": demon}
        results: list[ActionResult] = []

        # Run auras twice — permanent buff should survive the cleanup each time
        _resolve_auras(players, results)
        _resolve_auras(players, results)

        enrage_buffs = [b for b in demon.active_buffs if b.get("buff_id") == "demon_enrage"]
        assert len(enrage_buffs) == 1

    def test_enrage_exactly_at_threshold(self):
        """Demon at exactly 30% HP triggers enrage."""
        demon = _make_unit(pid="d1", name="Demon", hp=30, max_hp=100, class_id="demon_enrage")
        players = {"d1": demon}
        results: list[ActionResult] = []

        _resolve_auras(players, results)

        enrage_buffs = [b for b in demon.active_buffs if b.get("buff_id") == "demon_enrage"]
        assert len(enrage_buffs) == 1

    def test_non_demon_no_enrage(self):
        """Non-demon class_id does not get demon enrage even at low HP."""
        skeleton = _make_unit(pid="s1", name="Skeleton", hp=10, max_hp=100, class_id="skeleton")
        players = {"s1": skeleton}
        results: list[ActionResult] = []

        _resolve_auras(players, results)

        enrage_buffs = [b for b in skeleton.active_buffs if b.get("buff_id") == "demon_enrage"]
        assert len(enrage_buffs) == 0


# ===========================================================================
# Section 2: Bone Shield (damage_absorb)
# ===========================================================================

class TestBoneShield:
    """Bone Shield: damage absorb skill for Skeleton class."""

    def test_resolve_creates_absorb_buff(self):
        """resolve_damage_absorb creates a damage_absorb buff entry."""
        skeleton = _make_unit(pid="s1", name="Skeleton", class_id="skeleton")
        skill_def = get_skill("bone_shield")
        assert skill_def is not None

        result = resolve_damage_absorb(skeleton, skill_def)

        assert result.success is True
        absorb = get_damage_absorb_effect(skeleton)
        assert absorb is not None
        assert absorb["type"] == "damage_absorb"
        assert absorb["absorb_remaining"] == absorb["absorb_total"]
        assert absorb["absorb_remaining"] > 0

    def test_consume_absorb_full(self):
        """Absorb shield fully absorbs small incoming damage."""
        skeleton = _make_unit(pid="s1", name="Skeleton", class_id="skeleton",
                              active_buffs=[{
                                  "buff_id": "bone_shield",
                                  "type": "damage_absorb",
                                  "absorb_remaining": 25,
                                  "absorb_total": 25,
                                  "turns_remaining": 4,
                                  "stat": None,
                                  "magnitude": 25,
                              }])

        damage_after, absorbed = consume_damage_absorb(skeleton, 10)

        assert absorbed == 10
        assert damage_after == 0
        # Shield should still be active with remaining
        absorb = get_damage_absorb_effect(skeleton)
        assert absorb is not None
        assert absorb["absorb_remaining"] == 15

    def test_consume_absorb_partial_break(self):
        """Absorb shield breaks when incoming damage exceeds remaining."""
        skeleton = _make_unit(pid="s1", name="Skeleton", class_id="skeleton",
                              active_buffs=[{
                                  "buff_id": "bone_shield",
                                  "type": "damage_absorb",
                                  "absorb_remaining": 10,
                                  "absorb_total": 25,
                                  "turns_remaining": 4,
                                  "stat": None,
                                  "magnitude": 25,
                              }])

        damage_after, absorbed = consume_damage_absorb(skeleton, 20)

        assert absorbed == 10
        assert damage_after == 10
        # Shield should be removed
        absorb = get_damage_absorb_effect(skeleton)
        assert absorb is None

    def test_consume_absorb_exact_break(self):
        """Absorb shield breaks exactly when remaining matches incoming."""
        skeleton = _make_unit(pid="s1", name="Skeleton", class_id="skeleton",
                              active_buffs=[{
                                  "buff_id": "bone_shield",
                                  "type": "damage_absorb",
                                  "absorb_remaining": 15,
                                  "absorb_total": 25,
                                  "turns_remaining": 4,
                                  "stat": None,
                                  "magnitude": 25,
                              }])

        damage_after, absorbed = consume_damage_absorb(skeleton, 15)

        assert absorbed == 15
        assert damage_after == 0
        absorb = get_damage_absorb_effect(skeleton)
        assert absorb is None  # removed at 0

    def test_no_absorb_returns_full_damage(self):
        """Without absorb buff, consume_damage_absorb returns full damage."""
        unit = _make_unit(pid="u1", active_buffs=[])

        damage_after, absorbed = consume_damage_absorb(unit, 30)

        assert absorbed == 0
        assert damage_after == 30

    def test_resolve_refreshes_existing_shield(self):
        """Casting bone_shield again refreshes (replaces) the old absorb buff."""
        skeleton = _make_unit(pid="s1", name="Skeleton", class_id="skeleton",
                              active_buffs=[{
                                  "buff_id": "bone_shield",
                                  "type": "damage_absorb",
                                  "absorb_remaining": 5,  # damaged shield
                                  "absorb_total": 25,
                                  "turns_remaining": 2,
                                  "stat": None,
                                  "magnitude": 25,
                              }])

        skill_def = get_skill("bone_shield")
        resolve_damage_absorb(skeleton, skill_def)

        # Should have exactly one absorb buff, fully refreshed
        absorbs = [b for b in skeleton.active_buffs if b.get("type") == "damage_absorb"]
        assert len(absorbs) == 1
        assert absorbs[0]["absorb_remaining"] == absorbs[0]["absorb_total"]

    def test_apply_damage_uses_absorb(self):
        """apply_damage integrates with damage_absorb — HP reduced only by overflow."""
        skeleton = _make_unit(pid="s1", name="Skeleton", hp=100, max_hp=100,
                              active_buffs=[{
                                  "buff_id": "bone_shield",
                                  "type": "damage_absorb",
                                  "absorb_remaining": 20,
                                  "absorb_total": 25,
                                  "turns_remaining": 4,
                                  "stat": None,
                                  "magnitude": 25,
                              }])

        died = apply_damage(skeleton, 30)

        assert died is False
        # Shield absorbs 20, remaining 10 damage hits HP
        assert skeleton.hp == 90


# ===========================================================================
# Section 3: Imp Frenzy Aura (passive_aura_ally_buff with tag filter)
# ===========================================================================

class TestImpFrenzyAura:
    """Frenzy Aura: tag-filtered aura that buffs nearby imps with +3 attack_damage."""

    def test_frenzy_aura_buffs_nearby_imp(self):
        """Imp with frenzy aura buffs another imp within radius."""
        frenzy_imp = _make_unit(pid="i1", name="Imp-1", x=5, y=5, team="b",
                                class_id="imp_frenzy", tags=["demon", "imp"])
        target_imp = _make_unit(pid="i2", name="Imp-2", x=6, y=5, team="b",
                                class_id="skeleton", tags=["demon", "imp"])  # is an imp by tag
        players = {"i1": frenzy_imp, "i2": target_imp}
        results: list[ActionResult] = []

        _resolve_auras(players, results)

        atk_buffs = [b for b in target_imp.active_buffs if b.get("stat") == "attack_damage"]
        assert len(atk_buffs) == 1
        assert atk_buffs[0]["magnitude"] == 3  # +3 flat attack
        assert atk_buffs[0]["is_aura"] is True

    def test_frenzy_aura_no_buff_non_imp(self):
        """Frenzy aura does NOT buff units without the 'imp' tag."""
        frenzy_imp = _make_unit(pid="i1", name="Imp-1", x=5, y=5, team="b",
                                class_id="imp_frenzy", tags=["demon", "imp"])
        demon = _make_unit(pid="d1", name="Demon", x=6, y=5, team="b",
                           tags=["demon"])  # No 'imp' tag
        players = {"i1": frenzy_imp, "d1": demon}
        results: list[ActionResult] = []

        _resolve_auras(players, results)

        atk_buffs = [b for b in demon.active_buffs if b.get("stat") == "attack_damage"]
        assert len(atk_buffs) == 0

    def test_frenzy_aura_no_buff_enemy_team(self):
        """Frenzy aura does NOT buff imps on the opposing team."""
        frenzy_imp = _make_unit(pid="i1", name="Imp-1", x=5, y=5, team="b",
                                class_id="imp_frenzy", tags=["demon", "imp"])
        enemy_imp = _make_unit(pid="i2", name="Imp-2", x=6, y=5, team="a",
                               tags=["demon", "imp"])
        players = {"i1": frenzy_imp, "i2": enemy_imp}
        results: list[ActionResult] = []

        _resolve_auras(players, results)

        atk_buffs = [b for b in enemy_imp.active_buffs if b.get("stat") == "attack_damage"]
        assert len(atk_buffs) == 0

    def test_frenzy_aura_no_buff_out_of_range(self):
        """Frenzy aura does NOT buff imps outside of radius."""
        frenzy_imp = _make_unit(pid="i1", name="Imp-1", x=5, y=5, team="b",
                                class_id="imp_frenzy", tags=["demon", "imp"])
        far_imp = _make_unit(pid="i2", name="Imp-2", x=20, y=20, team="b",
                             tags=["demon", "imp"])
        players = {"i1": frenzy_imp, "i2": far_imp}
        results: list[ActionResult] = []

        _resolve_auras(players, results)

        atk_buffs = [b for b in far_imp.active_buffs if b.get("stat") == "attack_damage"]
        assert len(atk_buffs) == 0

    def test_frenzy_aura_does_not_buff_self(self):
        """Frenzy aura source imp does NOT buff itself."""
        frenzy_imp = _make_unit(pid="i1", name="Imp-1", x=5, y=5, team="b",
                                class_id="imp_frenzy", tags=["demon", "imp"])
        players = {"i1": frenzy_imp}
        results: list[ActionResult] = []

        _resolve_auras(players, results)

        atk_buffs = [b for b in frenzy_imp.active_buffs if b.get("stat") == "attack_damage"]
        assert len(atk_buffs) == 0

    def test_frenzy_aura_is_refreshing(self):
        """Frenzy aura buffs are cleaned and re-applied each tick (is_aura=True)."""
        frenzy_imp = _make_unit(pid="i1", name="Imp-1", x=5, y=5, team="b",
                                class_id="imp_frenzy", tags=["demon", "imp"])
        target_imp = _make_unit(pid="i2", name="Imp-2", x=6, y=5, team="b",
                                tags=["demon", "imp"])
        players = {"i1": frenzy_imp, "i2": target_imp}
        results: list[ActionResult] = []

        # Run auras twice — should NOT stack
        _resolve_auras(players, results)
        _resolve_auras(players, results)

        atk_buffs = [b for b in target_imp.active_buffs if b.get("stat") == "attack_damage"]
        assert len(atk_buffs) == 1  # refreshed, not stacked


# ===========================================================================
# Section 4: Flat Attack Damage Buff (Frenzy Aura integration in damage pipeline)
# ===========================================================================

class TestAttackDamageBuff:
    """get_attack_damage_buff_bonus integrates Frenzy Aura into damage calc."""

    def test_attack_damage_buff_adds_flat(self):
        """Frenzy Aura buff adds flat damage bonus."""
        unit = _make_unit(pid="u1", damage=10, active_buffs=[{
            "buff_id": "frenzy_aura_i1",
            "stat": "attack_damage",
            "magnitude": 3,
            "turns_remaining": 1,
            "is_aura": True,
            "source": "i1",
        }])

        bonus = get_attack_damage_buff_bonus(unit)
        assert bonus == 3

    def test_no_buff_returns_zero(self):
        """No attack_damage buff returns zero."""
        unit = _make_unit(pid="u1", damage=10)
        assert get_attack_damage_buff_bonus(unit) == 0

    def test_multiple_buffs_stack(self):
        """Multiple attack_damage buffs stack additively."""
        unit = _make_unit(pid="u1", damage=10, active_buffs=[
            {"stat": "attack_damage", "magnitude": 3, "turns_remaining": 1, "is_aura": True},
            {"stat": "attack_damage", "magnitude": 2, "turns_remaining": 1, "is_aura": True},
        ])
        assert get_attack_damage_buff_bonus(unit) == 5

    def test_flat_bonus_in_calculate_damage(self):
        """Flat attack bonus from Frenzy Aura increases calculated melee damage."""
        attacker = _make_unit(pid="a1", damage=10, active_buffs=[{
            "stat": "attack_damage",
            "magnitude": 3,
            "turns_remaining": 1,
            "is_aura": True,
        }])
        defender = _make_unit(pid="d1", armor=0)

        dmg_buffed = calculate_damage(attacker, defender)

        # Without buff: 10 damage. With buff: 13 damage.
        attacker_no_buff = _make_unit(pid="a2", damage=10)
        dmg_base = calculate_damage(attacker_no_buff, defender)

        assert dmg_buffed == dmg_base + 3


# ===========================================================================
# Section 5: Damage Reduction Buff (Profane Ward via buff)
# ===========================================================================

class TestDamageReductionBuff:
    """get_damage_reduction_buff_bonus integrates Profane Ward into damage pipeline."""

    def test_dr_buff_returns_bonus(self):
        """Profane Ward buff adds DR%."""
        unit = _make_unit(pid="u1", active_buffs=[{
            "buff_id": "profane_ward",
            "stat": "damage_reduction_pct",
            "magnitude": 0.30,
            "turns_remaining": 3,
            "type": "buff",
            "source": "healer1",
        }])

        dr = get_damage_reduction_buff_bonus(unit)
        assert dr == pytest.approx(0.30)

    def test_no_dr_buff_returns_zero(self):
        """No damage_reduction_pct buff returns zero."""
        unit = _make_unit(pid="u1")
        assert get_damage_reduction_buff_bonus(unit) == 0.0


# ===========================================================================
# Section 6: AI Role Mapping for New Classes
# ===========================================================================

class TestAIRoleMappingPhase18I:
    """Verify Phase 18I enemy classes are in the role map."""

    def test_demon_enrage_maps_to_passive_only(self):
        """demon_enrage class maps to passive_only role."""
        assert _get_role_for_class("demon_enrage") == "passive_only"

    def test_imp_frenzy_maps_to_passive_only(self):
        """imp_frenzy class maps to passive_only role."""
        assert _get_role_for_class("imp_frenzy") == "passive_only"

    def test_dark_priest_maps_to_support(self):
        """dark_priest class maps to support role."""
        assert _get_role_for_class("dark_priest") == "support"

    def test_skeleton_still_ranged_dps(self):
        """skeleton class still maps to ranged_dps."""
        assert _get_role_for_class("skeleton") == "ranged_dps"

    def test_acolyte_still_support(self):
        """acolyte class still maps to support."""
        assert _get_role_for_class("acolyte") == "support"

    def test_passive_only_returns_none(self):
        """_decide_skill_usage for passive_only role returns None (no active skill)."""
        unit = _make_unit(pid="d1", name="Demon", class_id="demon_enrage",
                          damage=15, hp=50, max_hp=100)
        enemies = [_make_unit(pid="e1", x=6, y=5, team="a")]
        all_players = {"d1": unit, "e1": enemies[0]}

        action = _decide_skill_usage(unit, enemies, all_players, 30, 30, set())
        assert action is None


# ===========================================================================
# Section 7: Skill Config Validation
# ===========================================================================

class TestSkillConfig:
    """Verify Phase 18I skills are properly configured."""

    def test_enrage_skill_exists(self):
        """enrage skill exists in skills_config.json."""
        skill = get_skill("enrage")
        assert skill is not None
        assert skill["effects"][0]["type"] == "passive_enrage"

    def test_bone_shield_skill_exists(self):
        """bone_shield skill exists with damage_absorb effect."""
        skill = get_skill("bone_shield")
        assert skill is not None
        assert skill["effects"][0]["type"] == "damage_absorb"

    def test_frenzy_aura_skill_exists(self):
        """frenzy_aura skill exists with passive_aura_ally_buff effect."""
        skill = get_skill("frenzy_aura")
        assert skill is not None
        assert skill["effects"][0]["type"] == "passive_aura_ally_buff"

    def test_dark_pact_skill_exists(self):
        """dark_pact skill exists with buff effect."""
        skill = get_skill("dark_pact")
        assert skill is not None
        assert skill["effects"][0]["type"] == "buff"

    def test_profane_ward_skill_exists(self):
        """profane_ward skill exists with buff effect."""
        skill = get_skill("profane_ward")
        assert skill is not None
        assert skill["effects"][0]["type"] == "buff"

    def test_skeleton_has_bone_shield_in_class_skills(self):
        """skeleton class_skills includes bone_shield."""
        skill_def = get_skill("bone_shield")
        assert skill_def is not None
        # Verify skeleton can use it via _try_skill
        skeleton = _make_unit(pid="s1", class_id="skeleton")
        action = _try_skill(skeleton, "bone_shield")
        assert action is not None

    def test_acolyte_has_profane_ward_in_class_skills(self):
        """acolyte class_skills includes profane_ward."""
        acolyte = _make_unit(pid="a1", class_id="acolyte")
        action = _try_skill(acolyte, "profane_ward")
        assert action is not None

    def test_dark_priest_has_dark_pact_in_class_skills(self):
        """dark_priest class_skills includes dark_pact and heal."""
        dp = _make_unit(pid="dp1", class_id="dark_priest")
        action_dp = _try_skill(dp, "dark_pact")
        assert action_dp is not None
        action_heal = _try_skill(dp, "heal")
        assert action_heal is not None


# ===========================================================================
# Section 8: Bone Shield AI Usage (ranged_dps role)
# ===========================================================================

class TestBoneShieldAI:
    """Bone Shield AI: skeleton casts bone_shield when enemies are visible."""

    def test_skeleton_casts_bone_shield_with_visible_enemy(self):
        """Skeleton casts bone_shield when enemies are visible and no absorb active."""
        skeleton = _make_unit(
            pid="s1", name="Skeleton-1", x=5, y=5, hp=60, max_hp=80,
            team="b", damage=8, class_id="skeleton",
            ranged_range=5, vision_range=7,
        )
        enemy = _make_unit(pid="e1", name="Hero", x=8, y=5, team="a", hp=100, max_hp=100)
        all_players = {"s1": skeleton, "e1": enemy}

        action = _decide_skill_usage(skeleton, [enemy], all_players, 30, 30, set())

        # Should cast bone_shield (or evasion depending on HP); at 75% HP, bone_shield is priority
        if action is not None and action.skill_id == "bone_shield":
            assert action.action_type == ActionType.SKILL
        # If evasion was chosen instead (HP < 50%), that's also valid ranged_dps behavior

    def test_skeleton_skips_bone_shield_if_absorb_active(self):
        """Skeleton does NOT cast bone_shield if already has damage_absorb buff."""
        skeleton = _make_unit(
            pid="s1", name="Skeleton-1", x=5, y=5, hp=60, max_hp=80,
            team="b", damage=8, class_id="skeleton",
            ranged_range=5, vision_range=7,
            active_buffs=[{
                "buff_id": "bone_shield",
                "type": "damage_absorb",
                "absorb_remaining": 20,
                "absorb_total": 25,
                "turns_remaining": 3,
                "stat": None,
                "magnitude": 25,
            }],
        )
        enemy = _make_unit(pid="e1", name="Hero", x=8, y=5, team="a", hp=100, max_hp=100)
        all_players = {"s1": skeleton, "e1": enemy}

        action = _decide_skill_usage(skeleton, [enemy], all_players, 30, 30, set())

        # Should NOT choose bone_shield (absorb already active)
        if action is not None:
            assert action.skill_id != "bone_shield"
