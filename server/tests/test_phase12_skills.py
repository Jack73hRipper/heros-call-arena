"""
Tests for Phase 12 Feature 1: Crusader & Ranger Skill Kits.

Covers:
- Shield Bash: melee damage + stun debuff, cooldown, adjacency requirement
- Taunt: AoE debuff on nearby enemies, radius check, duration
- Holy Ground: AoE heal centered on self, radius, heal capping
- Bulwark: armor buff application, duration
- Volley: AoE ranged damage at ground target, radius, multi-hit
- Evasion: charge-based dodge self-buff, charge consumption
- Crippling Shot: ranged damage + slow debuff, range/LOS checks
- CC helpers: is_stunned, is_slowed, is_taunted, trigger_evasion_dodge
- tick_buffs: stun/slow/taunt/evasion tick & expiry
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType, ActionResult
from app.core.combat import load_combat_config
from app.core.skills import (
    load_skills_config,
    clear_skills_cache,
    get_skill,
    can_use_skill,
    tick_buffs,
    is_stunned,
    is_slowed,
    is_taunted,
    get_evasion_effect,
    trigger_evasion_dodge,
    resolve_stun_damage,
    resolve_taunt,
    resolve_aoe_damage,
    resolve_aoe_heal,
    resolve_evasion,
    resolve_ranged_damage_slow,
    resolve_buff,
)


# ---------- Setup ----------

@pytest.fixture(autouse=True)
def _reset_caches():
    """Reset caches before each test."""
    clear_skills_cache()
    load_skills_config()
    load_combat_config()
    yield
    clear_skills_cache()


# ---------- Helpers ----------

def make_player(
    pid="p1", username="Alice", x=5, y=5, hp=100, max_hp=100,
    damage=15, ranged_damage=10, armor=2, team="a",
    class_id="crusader", ranged_range=5,
    cooldowns=None, active_buffs=None,
) -> PlayerState:
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=damage,
        ranged_damage=ranged_damage,
        armor=armor,
        team=team,
        class_id=class_id,
        ranged_range=ranged_range,
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
    )


# ============================================================
# 1. CC Helper Functions
# ============================================================

class TestCCHelpers:
    """Tests for the crowd-control helper functions."""

    def test_is_stunned_true(self):
        p = make_player(active_buffs=[{"type": "stun", "turns_remaining": 1}])
        assert is_stunned(p) is True

    def test_is_stunned_false(self):
        p = make_player()
        assert is_stunned(p) is False

    def test_is_slowed_true(self):
        p = make_player(active_buffs=[{"type": "slow", "turns_remaining": 2}])
        assert is_slowed(p) is True

    def test_is_slowed_false(self):
        p = make_player()
        assert is_slowed(p) is False

    def test_is_taunted_true(self):
        p = make_player(active_buffs=[{"type": "taunt", "source_id": "tank1", "turns_remaining": 2}])
        taunted, source = is_taunted(p)
        assert taunted is True
        assert source == "tank1"

    def test_is_taunted_false(self):
        p = make_player()
        taunted, source = is_taunted(p)
        assert taunted is False
        assert source is None

    def test_get_evasion_effect_exists(self):
        eff = {"type": "evasion", "charges": 2, "turns_remaining": 4}
        p = make_player(active_buffs=[eff])
        result = get_evasion_effect(p)
        assert result is not None
        assert result["charges"] == 2
        assert result["type"] == "evasion"

    def test_get_evasion_effect_none_when_no_charges(self):
        eff = {"type": "evasion", "charges": 0, "turns_remaining": 4}
        p = make_player(active_buffs=[eff])
        assert get_evasion_effect(p) is None

    def test_trigger_evasion_dodge_consumes_charge(self):
        eff = {"type": "evasion", "charges": 2, "turns_remaining": 4, "buff_id": "evasion"}
        p = make_player(active_buffs=[eff])
        assert trigger_evasion_dodge(p) is True
        evasion_buff = get_evasion_effect(p)
        assert evasion_buff is not None
        assert evasion_buff["charges"] == 1
        assert len(p.active_buffs) == 1  # Still present

    def test_trigger_evasion_dodge_removes_at_zero(self):
        eff = {"type": "evasion", "charges": 1, "turns_remaining": 4, "buff_id": "evasion"}
        p = make_player(active_buffs=[eff])
        assert trigger_evasion_dodge(p) is True
        assert len(p.active_buffs) == 0  # Removed

    def test_trigger_evasion_dodge_false_when_no_buff(self):
        p = make_player()
        assert trigger_evasion_dodge(p) is False


# ============================================================
# 2. Shield Bash (stun_damage)
# ============================================================

class TestShieldBash:
    """Tests for the Shield Bash skill (Crusader)."""

    def test_shield_bash_deals_damage_and_stuns(self):
        attacker = make_player(pid="p1", x=5, y=5, damage=20, armor=0, team="a", class_id="crusader")
        defender = make_player(pid="p2", username="Enemy", x=6, y=5, hp=100, armor=0, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("shield_bash")
        result = resolve_stun_damage(attacker, 6, 5, skill_def, players, set())
        assert result.success is True
        assert result.damage_dealt > 0
        assert defender.hp < 100
        # Stun should be applied
        assert is_stunned(defender) is True
        stun_buff = next(b for b in defender.active_buffs if b["type"] == "stun")
        assert stun_buff["turns_remaining"] == 1

    def test_shield_bash_applies_cooldown(self):
        attacker = make_player(pid="p1", x=5, y=5, damage=15, team="a", class_id="crusader")
        defender = make_player(pid="p2", username="Enemy", x=6, y=5, hp=100, armor=0, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("shield_bash")
        resolve_stun_damage(attacker, 6, 5, skill_def, players, set())
        assert attacker.cooldowns.get("shield_bash", 0) > 0

    def test_shield_bash_fails_when_not_adjacent(self):
        attacker = make_player(pid="p1", x=5, y=5, team="a", class_id="crusader")
        defender = make_player(pid="p2", username="Enemy", x=8, y=5, hp=100, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("shield_bash")
        result = resolve_stun_damage(attacker, 8, 5, skill_def, players, set())
        assert result.success is False
        assert defender.hp == 100

    def test_shield_bash_kill_no_stun(self):
        """If target is killed, stun should NOT be applied."""
        attacker = make_player(pid="p1", x=5, y=5, damage=200, team="a", class_id="crusader")
        defender = make_player(pid="p2", username="Enemy", x=6, y=5, hp=5, armor=0, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("shield_bash")
        result = resolve_stun_damage(attacker, 6, 5, skill_def, players, set())
        assert result.success is True
        assert result.killed is True
        assert not defender.is_alive
        # No stun buff on dead target
        assert not is_stunned(defender)


# ============================================================
# 3. Taunt
# ============================================================

class TestTaunt:
    """Tests for the Taunt skill (Crusader)."""

    def test_taunt_affects_nearby_enemies(self):
        tank = make_player(pid="tank", x=5, y=5, team="a", class_id="crusader")
        enemy1 = make_player(pid="e1", username="E1", x=6, y=5, team="b")
        enemy2 = make_player(pid="e2", username="E2", x=5, y=6, team="b")
        ally = make_player(pid="a1", username="Ally", x=4, y=5, team="a")
        players = {"tank": tank, "e1": enemy1, "e2": enemy2, "a1": ally}
        skill_def = get_skill("taunt")
        result = resolve_taunt(tank, skill_def, players)
        assert result.success is True
        # Both enemies should have taunt debuff
        assert is_taunted(enemy1) == (True, "tank")
        assert is_taunted(enemy2) == (True, "tank")
        # Ally should NOT have taunt
        assert is_taunted(ally) == (False, None)

    def test_taunt_ignores_out_of_range_enemies(self):
        tank = make_player(pid="tank", x=5, y=5, team="a", class_id="crusader")
        far_enemy = make_player(pid="e1", username="FarE", x=10, y=10, team="b")
        players = {"tank": tank, "e1": far_enemy}
        skill_def = get_skill("taunt")
        result = resolve_taunt(tank, skill_def, players)
        assert result.success is True
        assert is_taunted(far_enemy) == (False, None)

    def test_taunt_applies_cooldown(self):
        tank = make_player(pid="tank", x=5, y=5, team="a", class_id="crusader")
        enemy = make_player(pid="e1", username="E1", x=6, y=5, team="b")
        players = {"tank": tank, "e1": enemy}
        skill_def = get_skill("taunt")
        resolve_taunt(tank, skill_def, players)
        assert tank.cooldowns.get("taunt", 0) > 0

    def test_taunt_refreshes_not_stacks(self):
        """Re-taunting same enemy refreshes duration, doesn't add second buff."""
        tank = make_player(pid="tank", x=5, y=5, team="a", class_id="crusader")
        enemy = make_player(pid="e1", username="E1", x=6, y=5, team="b",
                            active_buffs=[{"type": "taunt", "source_id": "tank", "turns_remaining": 1}])
        players = {"tank": tank, "e1": enemy}
        skill_def = get_skill("taunt")
        tank.cooldowns = {}  # force no cooldown
        resolve_taunt(tank, skill_def, players)
        taunt_buffs = [b for b in enemy.active_buffs if b["type"] == "taunt"]
        assert len(taunt_buffs) == 1
        assert taunt_buffs[0]["turns_remaining"] == 2  # Refreshed to full duration


# ============================================================
# 4. Holy Ground (aoe_heal)
# ============================================================

class TestHolyGround:
    """Tests for the Holy Ground skill (Crusader)."""

    def test_holy_ground_heals_self_and_allies(self):
        caster = make_player(pid="p1", x=5, y=5, hp=80, team="a", class_id="crusader")
        ally = make_player(pid="p2", username="Ally", x=6, y=5, hp=70, team="a")
        enemy = make_player(pid="e1", username="E", x=5, y=6, hp=60, team="b")
        players = {"p1": caster, "p2": ally, "e1": enemy}
        skill_def = get_skill("holy_ground")
        result = resolve_aoe_heal(caster, skill_def, players)
        assert result.success is True
        assert result.heal_amount > 0
        # Caster should be healed
        assert caster.hp > 80
        # Ally within radius 1 should be healed
        assert ally.hp > 70
        # Enemy should NOT be healed
        assert enemy.hp == 60

    def test_holy_ground_caps_at_max_hp(self):
        caster = make_player(pid="p1", x=5, y=5, hp=95, max_hp=100, team="a", class_id="crusader")
        players = {"p1": caster}
        skill_def = get_skill("holy_ground")
        result = resolve_aoe_heal(caster, skill_def, players)
        assert caster.hp == 100  # Capped at max

    def test_holy_ground_no_allies_in_range(self):
        caster = make_player(pid="p1", x=5, y=5, hp=100, team="a", class_id="crusader")
        far_ally = make_player(pid="p2", username="Far", x=10, y=10, hp=50, team="a")
        players = {"p1": caster, "p2": far_ally}
        skill_def = get_skill("holy_ground")
        result = resolve_aoe_heal(caster, skill_def, players)
        # Caster already at max HP, far ally out of range
        assert far_ally.hp == 50


# ============================================================
# 5. Bulwark (armor buff)
# ============================================================

class TestBulwark:
    """Tests for the Bulwark skill (Crusader)."""

    def test_bulwark_applies_armor_buff(self):
        tank = make_player(pid="p1", x=5, y=5, team="a", class_id="crusader")
        players = {"p1": tank}
        skill_def = get_skill("bulwark")
        result = resolve_buff(tank, skill_def)
        assert result.success is True
        # Should have an armor buff in active_buffs
        armor_buff = [b for b in tank.active_buffs if b.get("stat") == "armor"]
        assert len(armor_buff) == 1
        assert armor_buff[0]["magnitude"] == 8
        assert armor_buff[0]["turns_remaining"] == 4

    def test_bulwark_applies_cooldown(self):
        tank = make_player(pid="p1", x=5, y=5, team="a", class_id="crusader")
        skill_def = get_skill("bulwark")
        resolve_buff(tank, skill_def)
        assert tank.cooldowns.get("bulwark", 0) > 0


# ============================================================
# 6. Volley (aoe_damage)
# ============================================================

class TestVolley:
    """Tests for the Volley skill (Ranger)."""

    def test_volley_hits_multiple_enemies(self):
        archer = make_player(pid="p1", x=0, y=0, ranged_damage=20, team="a", class_id="ranger")
        enemy1 = make_player(pid="e1", username="E1", x=3, y=3, hp=100, armor=0, team="b")
        enemy2 = make_player(pid="e2", username="E2", x=3, y=4, hp=100, armor=0, team="b")
        players = {"p1": archer, "e1": enemy1, "e2": enemy2}
        skill_def = get_skill("volley")
        result = resolve_aoe_damage(archer, 3, 3, skill_def, players, set())
        assert result.success is True
        assert result.damage_dealt > 0
        # Both enemies should have taken damage
        assert enemy1.hp < 100
        assert enemy2.hp < 100

    def test_volley_no_friendly_fire(self):
        archer = make_player(pid="p1", x=0, y=0, ranged_damage=20, team="a", class_id="ranger")
        ally = make_player(pid="a1", username="Ally", x=3, y=3, hp=100, team="a")
        enemy = make_player(pid="e1", username="E1", x=3, y=4, hp=100, armor=0, team="b")
        players = {"p1": archer, "a1": ally, "e1": enemy}
        skill_def = get_skill("volley")
        result = resolve_aoe_damage(archer, 3, 3, skill_def, players, set())
        assert ally.hp == 100  # No friendly fire
        assert enemy.hp < 100

    def test_volley_fails_out_of_range(self):
        archer = make_player(pid="p1", x=0, y=0, ranged_damage=20, team="a", class_id="ranger")
        enemy = make_player(pid="e1", username="E1", x=15, y=15, hp=100, team="b")
        players = {"p1": archer, "e1": enemy}
        skill_def = get_skill("volley")
        result = resolve_aoe_damage(archer, 15, 15, skill_def, players, set())
        assert result.success is False

    def test_volley_no_target_specified(self):
        archer = make_player(pid="p1", x=0, y=0, team="a", class_id="ranger")
        players = {"p1": archer}
        skill_def = get_skill("volley")
        result = resolve_aoe_damage(archer, None, None, skill_def, players, set())
        assert result.success is False

    def test_volley_can_kill_multiple(self):
        archer = make_player(pid="p1", x=0, y=0, ranged_damage=200, team="a", class_id="ranger")
        enemy1 = make_player(pid="e1", username="E1", x=3, y=3, hp=10, armor=0, team="b")
        enemy2 = make_player(pid="e2", username="E2", x=3, y=4, hp=10, armor=0, team="b")
        players = {"p1": archer, "e1": enemy1, "e2": enemy2}
        skill_def = get_skill("volley")
        result = resolve_aoe_damage(archer, 3, 3, skill_def, players, set())
        assert result.killed is True
        killed_ids = result.buff_applied.get("killed_ids", [])
        assert "e1" in killed_ids
        assert "e2" in killed_ids


# ============================================================
# 7. Evasion
# ============================================================

class TestEvasion:
    """Tests for the Evasion skill (Ranger)."""

    def test_evasion_grants_charges(self):
        ranger = make_player(pid="p1", x=5, y=5, team="a", class_id="ranger")
        skill_def = get_skill("evasion")
        result = resolve_evasion(ranger, skill_def)
        assert result.success is True
        evasion_buff = get_evasion_effect(ranger)
        assert evasion_buff is not None
        assert evasion_buff["charges"] == 2
        assert evasion_buff["turns_remaining"] == 4

    def test_evasion_dodge_works(self):
        """Evasion should dodge an incoming attack and consume a charge."""
        ranger = make_player(pid="p1", x=5, y=5, team="a", class_id="ranger")
        skill_def = get_skill("evasion")
        resolve_evasion(ranger, skill_def)
        # First dodge
        assert trigger_evasion_dodge(ranger) is True
        evasion_buff = get_evasion_effect(ranger)
        assert evasion_buff is not None
        assert evasion_buff["charges"] == 1
        # Second dodge — consumes last charge
        assert trigger_evasion_dodge(ranger) is True
        assert get_evasion_effect(ranger) is None
        # Third dodge — no more charges
        assert trigger_evasion_dodge(ranger) is False

    def test_evasion_refresh_doesnt_stack(self):
        ranger = make_player(pid="p1", x=5, y=5, team="a", class_id="ranger")
        skill_def = get_skill("evasion")
        resolve_evasion(ranger, skill_def)
        # Consume a charge
        trigger_evasion_dodge(ranger)
        # Re-cast (clear cooldown first for test)
        ranger.cooldowns = {}
        resolve_evasion(ranger, skill_def)
        # Should have fresh 2 charges, not 3
        evasion_buffs = [b for b in ranger.active_buffs if b.get("type") == "evasion"]
        assert len(evasion_buffs) == 1
        assert evasion_buffs[0]["charges"] == 2

    def test_evasion_applies_cooldown(self):
        ranger = make_player(pid="p1", x=5, y=5, team="a", class_id="ranger")
        skill_def = get_skill("evasion")
        resolve_evasion(ranger, skill_def)
        assert ranger.cooldowns.get("evasion", 0) > 0


# ============================================================
# 8. Crippling Shot (ranged_damage_slow)
# ============================================================

class TestCripplingShot:
    """Tests for the Crippling Shot skill (Ranger)."""

    def test_crippling_shot_deals_damage_and_slows(self):
        ranger = make_player(pid="p1", x=0, y=0, ranged_damage=20, team="a", class_id="ranger")
        enemy = make_player(pid="e1", username="E1", x=3, y=0, hp=100, armor=0, team="b")
        players = {"p1": ranger, "e1": enemy}
        skill_def = get_skill("crippling_shot")
        result = resolve_ranged_damage_slow(ranger, 3, 0, skill_def, players, set())
        assert result.success is True
        assert result.damage_dealt > 0
        assert enemy.hp < 100
        assert is_slowed(enemy) is True
        slow_buff = next(b for b in enemy.active_buffs if b["type"] == "slow")
        assert slow_buff["turns_remaining"] == 2

    def test_crippling_shot_out_of_range(self):
        ranger = make_player(pid="p1", x=0, y=0, ranged_damage=20, team="a", class_id="ranger")
        enemy = make_player(pid="e1", username="E1", x=15, y=0, hp=100, team="b")
        players = {"p1": ranger, "e1": enemy}
        skill_def = get_skill("crippling_shot")
        result = resolve_ranged_damage_slow(ranger, 15, 0, skill_def, players, set())
        assert result.success is False

    def test_crippling_shot_no_los(self):
        ranger = make_player(pid="p1", x=0, y=0, ranged_damage=20, team="a", class_id="ranger")
        enemy = make_player(pid="e1", username="E1", x=3, y=0, hp=100, team="b")
        obstacles = {(1, 0), (2, 0)}  # Wall between them
        players = {"p1": ranger, "e1": enemy}
        skill_def = get_skill("crippling_shot")
        result = resolve_ranged_damage_slow(ranger, 3, 0, skill_def, players, obstacles)
        assert result.success is False

    def test_crippling_shot_kill_no_slow(self):
        """If target killed, slow should NOT be applied."""
        ranger = make_player(pid="p1", x=0, y=0, ranged_damage=200, team="a", class_id="ranger")
        enemy = make_player(pid="e1", username="E1", x=3, y=0, hp=5, armor=0, team="b")
        players = {"p1": ranger, "e1": enemy}
        skill_def = get_skill("crippling_shot")
        result = resolve_ranged_damage_slow(ranger, 3, 0, skill_def, players, set())
        assert result.killed is True
        assert not is_slowed(enemy)

    def test_crippling_shot_applies_cooldown(self):
        ranger = make_player(pid="p1", x=0, y=0, ranged_damage=20, team="a", class_id="ranger")
        enemy = make_player(pid="e1", username="E1", x=3, y=0, hp=100, armor=0, team="b")
        players = {"p1": ranger, "e1": enemy}
        skill_def = get_skill("crippling_shot")
        resolve_ranged_damage_slow(ranger, 3, 0, skill_def, players, set())
        assert ranger.cooldowns.get("crippling_shot", 0) > 0


# ============================================================
# 9. Buff Tick & Expiry for New CC Types
# ============================================================

class TestCCBuffTick:
    """Tests that stun, slow, taunt, evasion buffs tick and expire correctly."""

    def test_stun_expires_after_tick(self):
        p = make_player(active_buffs=[
            {"buff_id": "shield_bash", "type": "stun", "turns_remaining": 1, "stat": None, "magnitude": 0}
        ])
        tick_buffs(p)
        assert is_stunned(p) is False
        assert len(p.active_buffs) == 0

    def test_stun_decrements(self):
        """A 2-turn stun should become 1-turn after one tick."""
        p = make_player(active_buffs=[
            {"buff_id": "shield_bash", "type": "stun", "turns_remaining": 2, "stat": None, "magnitude": 0}
        ])
        tick_buffs(p)
        assert is_stunned(p) is True
        stun = next(b for b in p.active_buffs if b["type"] == "stun")
        assert stun["turns_remaining"] == 1

    def test_slow_expires_after_tick(self):
        p = make_player(active_buffs=[
            {"buff_id": "crippling_shot", "type": "slow", "turns_remaining": 1, "stat": None, "magnitude": 0}
        ])
        tick_buffs(p)
        assert is_slowed(p) is False

    def test_taunt_expires_after_ticks(self):
        p = make_player(active_buffs=[
            {"buff_id": "taunt", "type": "taunt", "source_id": "tank1", "turns_remaining": 1, "stat": None, "magnitude": 0}
        ])
        tick_buffs(p)
        assert is_taunted(p) == (False, None)

    def test_evasion_expires_by_duration(self):
        """Evasion should expire when turns_remaining reaches 0 even with charges left."""
        p = make_player(active_buffs=[
            {"buff_id": "evasion", "type": "evasion", "charges": 2, "turns_remaining": 1, "stat": None, "magnitude": 0}
        ])
        tick_buffs(p)
        assert get_evasion_effect(p) is None


# ============================================================
# 10. Config Integration
# ============================================================

class TestPhase12SkillConfig:
    """Tests that new skills are properly registered in skills_config.json."""

    def test_new_skills_exist(self):
        for skill_id in ["taunt", "shield_bash", "holy_ground", "bulwark", "volley", "evasion", "crippling_shot"]:
            skill = get_skill(skill_id)
            assert skill is not None, f"Skill '{skill_id}' not found in config"
            assert skill["skill_id"] == skill_id

    def test_crusader_class_skills(self):
        from app.core.skills import get_class_skills
        crusader_skills = get_class_skills("crusader")
        expected = {"auto_attack_melee", "taunt", "shield_bash", "holy_ground", "bulwark"}
        assert set(crusader_skills) == expected

    def test_ranger_class_skills(self):
        from app.core.skills import get_class_skills
        ranger_skills = get_class_skills("ranger")
        expected = {"auto_attack_ranged", "power_shot", "volley", "evasion", "crippling_shot"}
        assert set(ranger_skills) == expected

    def test_shield_bash_config(self):
        skill = get_skill("shield_bash")
        assert skill["targeting"] == "enemy_adjacent"
        assert skill["range"] == 1
        assert skill["cooldown_turns"] == 4
        assert skill["effects"][0]["type"] == "stun_damage"
        assert skill["effects"][0]["damage_multiplier"] == 0.7
        assert skill["effects"][0]["stun_duration"] == 1

    def test_taunt_config(self):
        skill = get_skill("taunt")
        assert skill["targeting"] == "self"
        assert skill["cooldown_turns"] == 5
        assert skill["effects"][0]["type"] == "taunt"
        assert skill["effects"][0]["radius"] == 2
        assert skill["effects"][0]["duration_turns"] == 2

    def test_holy_ground_config(self):
        skill = get_skill("holy_ground")
        assert skill["targeting"] == "self"
        assert skill["cooldown_turns"] == 5
        assert skill["effects"][0]["type"] == "aoe_heal"
        assert skill["effects"][0]["magnitude"] == 15
        assert skill["effects"][0]["radius"] == 1

    def test_bulwark_config(self):
        skill = get_skill("bulwark")
        assert skill["targeting"] == "self"
        assert skill["cooldown_turns"] == 5
        assert skill["effects"][0]["type"] == "buff"
        assert skill["effects"][0]["stat"] == "armor"
        assert skill["effects"][0]["magnitude"] == 8
        assert skill["effects"][0]["duration_turns"] == 4

    def test_volley_config(self):
        skill = get_skill("volley")
        assert skill["targeting"] == "ground_aoe"
        assert skill["range"] == 5
        assert skill["cooldown_turns"] == 7
        assert skill["effects"][0]["type"] == "aoe_damage"
        assert skill["effects"][0]["damage_multiplier"] == 0.5
        assert skill["effects"][0]["radius"] == 2

    def test_evasion_config(self):
        skill = get_skill("evasion")
        assert skill["targeting"] == "self"
        assert skill["cooldown_turns"] == 6
        assert skill["effects"][0]["type"] == "evasion"
        assert skill["effects"][0]["charges"] == 2
        assert skill["effects"][0]["duration_turns"] == 4

    def test_crippling_shot_config(self):
        skill = get_skill("crippling_shot")
        assert skill["targeting"] == "enemy_ranged"
        assert skill["cooldown_turns"] == 5
        assert skill["effects"][0]["type"] == "ranged_damage_slow"
        assert skill["effects"][0]["damage_multiplier"] == 0.8
        assert skill["effects"][0]["slow_duration"] == 2
