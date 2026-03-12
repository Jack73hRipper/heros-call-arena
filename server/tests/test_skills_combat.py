"""
Tests for Phase 6B: Turn Resolver Skill Phase & Combat Logic.

Covers:
- Heal skill: self-heal, ally heal, can't heal enemy, cooldown block, cap at max_hp
- Double Strike: 2 hits, armor per-hit, kill on second hit, not adjacent = fail
- Power Shot: 1.8x ranged damage, requires LOS, blocked by obstacles, own cooldown
- War Cry: buff applied, melee does 2x, buff decays, buff in combat.py
- Shadow Step: teleport valid tile, blocked by obstacle/occupied/out-of-range/no-LOS
- Buff tick: buffs decrement each turn, expired buffs removed
- Skill phase ordering: skills resolve before ranged and melee
- Backward compat: all skill types integrate cleanly in turn resolver
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType, ActionResult
from app.core.turn_resolver import resolve_turn
from app.core.combat import (
    load_combat_config,
    calculate_damage_simple as calculate_damage,
    calculate_ranged_damage_simple as calculate_ranged_damage,
)
from app.core.skills import (
    load_skills_config,
    clear_skills_cache,
    get_skill,
    can_use_skill,
    tick_buffs,
    get_melee_buff_multiplier,
    get_ranged_buff_multiplier,
    resolve_heal,
    resolve_multi_hit,
    resolve_ranged_skill,
    resolve_buff,
    resolve_teleport,
    resolve_skill_action,
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
    crit_chance=0.0, crit_damage=1.5,
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
        crit_chance=crit_chance,
        crit_damage=crit_damage,
    )


def make_skill_action(pid, skill_id, target_x=None, target_y=None):
    return PlayerAction(
        player_id=pid,
        action_type=ActionType.SKILL,
        target_x=target_x,
        target_y=target_y,
        skill_id=skill_id,
    )


# ============================================================
# 1. Heal Skill
# ============================================================

class TestHealSkill:
    """Tests for the Heal skill (Confessor)."""

    def test_heal_self(self):
        player = make_player(class_id="confessor", hp=60)
        players = {"p1": player}
        skill_def = get_skill("heal")
        result = resolve_heal(player, player.position.x, player.position.y, skill_def, players)
        assert result.success is True
        assert result.heal_amount == 30
        assert player.hp == 90
        assert result.skill_id == "heal"

    def test_heal_self_no_target(self):
        """When no target specified, heal defaults to self."""
        player = make_player(class_id="confessor", hp=70)
        players = {"p1": player}
        skill_def = get_skill("heal")
        result = resolve_heal(player, None, None, skill_def, players)
        assert result.success is True
        assert result.heal_amount == 30
        assert player.hp == 100

    def test_heal_adjacent_ally(self):
        healer = make_player(pid="p1", class_id="confessor", x=5, y=5, team="a")
        ally = make_player(pid="p2", username="Bob", x=6, y=5, hp=50, team="a")
        players = {"p1": healer, "p2": ally}
        skill_def = get_skill("heal")
        result = resolve_heal(healer, 6, 5, skill_def, players)
        assert result.success is True
        assert result.heal_amount == 30
        assert ally.hp == 80

    def test_heal_cannot_heal_enemy(self):
        healer = make_player(pid="p1", class_id="confessor", x=5, y=5, team="a")
        enemy = make_player(pid="p2", username="Enemy", x=6, y=5, hp=50, team="b")
        players = {"p1": healer, "p2": enemy}
        skill_def = get_skill("heal")
        result = resolve_heal(healer, 6, 5, skill_def, players)
        assert result.success is False
        assert enemy.hp == 50  # Unchanged

    def test_heal_caps_at_max_hp(self):
        player = make_player(class_id="confessor", hp=90, max_hp=100)
        players = {"p1": player}
        skill_def = get_skill("heal")
        result = resolve_heal(player, player.position.x, player.position.y, skill_def, players)
        assert result.success is True
        assert result.heal_amount == 10  # Only healed 10, not 30
        assert player.hp == 100

    def test_heal_applies_cooldown(self):
        player = make_player(class_id="confessor", hp=60)
        players = {"p1": player}
        skill_def = get_skill("heal")
        resolve_heal(player, player.position.x, player.position.y, skill_def, players)
        assert player.cooldowns.get("heal") == 4

    def test_heal_blocked_by_cooldown(self):
        player = make_player(class_id="confessor", hp=60, cooldowns={"heal": 3})
        can_use, reason = can_use_skill(player, "heal")
        assert can_use is False
        assert "cooldown" in reason.lower()

    def test_heal_out_of_range(self):
        healer = make_player(pid="p1", class_id="confessor", x=5, y=5, team="a")
        ally = make_player(pid="p2", username="Bob", x=9, y=5, hp=50, team="a")
        players = {"p1": healer, "p2": ally}
        skill_def = get_skill("heal")
        result = resolve_heal(healer, 9, 5, skill_def, players)
        assert result.success is False

    def test_heal_no_valid_target_at_position(self):
        healer = make_player(pid="p1", class_id="confessor", x=5, y=5, team="a")
        players = {"p1": healer}
        skill_def = get_skill("heal")
        result = resolve_heal(healer, 6, 5, skill_def, players)
        assert result.success is False


# ============================================================
# 2. Double Strike Skill
# ============================================================

class TestDoubleStrikeSkill:
    """Tests for the Double Strike skill (Crusader, Hexblade)."""

    def test_double_strike_two_hits(self):
        attacker = make_player(pid="p1", class_id="crusader", x=5, y=5, damage=15, team="a")
        defender = make_player(pid="p2", username="Enemy", x=6, y=5, hp=100, armor=0, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("double_strike")
        result = resolve_multi_hit(attacker, 6, 5, skill_def, players, set())
        assert result.success is True
        assert result.skill_id == "double_strike"
        assert result.damage_dealt > 0
        # Each hit = floor(15 * 0.7) = 10 damage, 2 hits = 20 (with 0 armor)
        assert result.damage_dealt == 20
        assert defender.hp == 80

    def test_double_strike_armor_per_hit(self):
        """Armor reduction applies per-hit, not total."""
        attacker = make_player(pid="p1", class_id="crusader", x=5, y=5, damage=15, team="a")
        defender = make_player(pid="p2", username="Enemy", x=6, y=5, hp=100, armor=5, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("double_strike")
        result = resolve_multi_hit(attacker, 6, 5, skill_def, players, set())
        assert result.success is True
        # Each hit raw = floor(15 * 0.7) = 10, minus 5 armor = 5, 2 hits = 10
        assert result.damage_dealt == 10

    def test_double_strike_kill_on_second_hit(self):
        attacker = make_player(pid="p1", class_id="crusader", x=5, y=5, damage=15, team="a")
        defender = make_player(pid="p2", username="Enemy", x=6, y=5, hp=15, armor=0, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("double_strike")
        result = resolve_multi_hit(attacker, 6, 5, skill_def, players, set())
        assert result.success is True
        assert result.killed is True
        assert defender.is_alive is False

    def test_double_strike_not_adjacent_fails(self):
        attacker = make_player(pid="p1", class_id="crusader", x=5, y=5, team="a")
        defender = make_player(pid="p2", username="Enemy", x=8, y=5, hp=100, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("double_strike")
        result = resolve_multi_hit(attacker, 8, 5, skill_def, players, set())
        assert result.success is False

    def test_double_strike_no_enemy_at_target(self):
        attacker = make_player(pid="p1", class_id="crusader", x=5, y=5, team="a")
        players = {"p1": attacker}
        skill_def = get_skill("double_strike")
        result = resolve_multi_hit(attacker, 6, 5, skill_def, players, set())
        assert result.success is False

    def test_double_strike_applies_cooldown(self):
        attacker = make_player(pid="p1", class_id="crusader", x=5, y=5, damage=15, team="a")
        defender = make_player(pid="p2", username="Enemy", x=6, y=5, hp=100, armor=0, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("double_strike")
        resolve_multi_hit(attacker, 6, 5, skill_def, players, set())
        assert attacker.cooldowns.get("double_strike") == 3

    def test_double_strike_cant_target_self(self):
        attacker = make_player(pid="p1", class_id="crusader", x=5, y=5, team="a")
        players = {"p1": attacker}
        skill_def = get_skill("double_strike")
        result = resolve_multi_hit(attacker, 5, 5, skill_def, players, set())
        assert result.success is False

    def test_double_strike_no_target_specified(self):
        attacker = make_player(pid="p1", class_id="crusader", x=5, y=5, team="a")
        players = {"p1": attacker}
        skill_def = get_skill("double_strike")
        result = resolve_multi_hit(attacker, None, None, skill_def, players, set())
        assert result.success is False

    def test_double_strike_hexblade_can_use(self):
        can, _ = can_use_skill(make_player(class_id="hexblade"), "double_strike")
        assert can is True

    def test_double_strike_ranger_cannot_use(self):
        can, reason = can_use_skill(make_player(class_id="ranger"), "double_strike")
        assert can is False
        assert "class" in reason.lower()


# ============================================================
# 3. Power Shot Skill
# ============================================================

class TestPowerShotSkill:
    """Tests for the Power Shot skill (Ranger, Inquisitor)."""

    def test_power_shot_deals_boosted_damage(self):
        attacker = make_player(pid="p1", class_id="ranger", x=5, y=5, ranged_damage=10, team="a")
        defender = make_player(pid="p2", username="Enemy", x=8, y=5, hp=100, armor=0, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("power_shot")
        result = resolve_ranged_skill(attacker, 8, 5, skill_def, players, set())
        assert result.success is True
        assert result.skill_id == "power_shot"
        # 10 * 1.8 = 18 damage (0 armor)
        assert result.damage_dealt == 18

    def test_power_shot_requires_los(self):
        attacker = make_player(pid="p1", class_id="ranger", x=5, y=5, team="a")
        defender = make_player(pid="p2", username="Enemy", x=8, y=5, hp=100, team="b")
        # Obstacle blocks LOS at (6,5)
        obstacles = {(6, 5), (7, 5)}
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("power_shot")
        result = resolve_ranged_skill(attacker, 8, 5, skill_def, players, obstacles)
        assert result.success is False
        assert "line of sight" in result.message.lower()

    def test_power_shot_out_of_range(self):
        attacker = make_player(pid="p1", class_id="ranger", x=0, y=0, ranged_range=5, team="a")
        defender = make_player(pid="p2", username="Enemy", x=10, y=0, hp=100, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("power_shot")
        result = resolve_ranged_skill(attacker, 10, 0, skill_def, players, set())
        assert result.success is False
        assert "range" in result.message.lower()

    def test_power_shot_applies_own_cooldown(self):
        """Power Shot has its own cooldown, separate from ranged_attack."""
        attacker = make_player(pid="p1", class_id="ranger", x=5, y=5, team="a")
        defender = make_player(pid="p2", username="Enemy", x=8, y=5, hp=100, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("power_shot")
        resolve_ranged_skill(attacker, 8, 5, skill_def, players, set())
        assert attacker.cooldowns.get("power_shot") == 7
        assert attacker.cooldowns.get("ranged_attack", 0) == 0  # Separate cooldown

    def test_power_shot_kills_low_hp_target(self):
        attacker = make_player(pid="p1", class_id="ranger", x=5, y=5, ranged_damage=10, team="a")
        defender = make_player(pid="p2", username="Enemy", x=8, y=5, hp=10, armor=0, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("power_shot")
        result = resolve_ranged_skill(attacker, 8, 5, skill_def, players, set())
        assert result.killed is True
        assert defender.is_alive is False

    def test_power_shot_inquisitor_can_use(self):
        can, _ = can_use_skill(make_player(class_id="inquisitor"), "power_shot")
        assert can is True

    def test_power_shot_crusader_cannot_use(self):
        can, reason = can_use_skill(make_player(class_id="crusader"), "power_shot")
        assert can is False

    def test_power_shot_no_enemy_at_target(self):
        attacker = make_player(pid="p1", class_id="ranger", x=5, y=5, team="a")
        players = {"p1": attacker}
        skill_def = get_skill("power_shot")
        result = resolve_ranged_skill(attacker, 8, 5, skill_def, players, set())
        assert result.success is False


# ============================================================
# 4. War Cry Skill
# ============================================================

class TestWarCrySkill:
    """Tests for the War Cry skill (Crusader)."""

    def test_war_cry_applies_buff(self):
        player = make_player(class_id="crusader")
        skill_def = get_skill("war_cry")
        result = resolve_buff(player, skill_def)
        assert result.success is True
        assert result.skill_id == "war_cry"
        assert result.buff_applied is not None
        assert result.buff_applied["stat"] == "melee_damage_multiplier"
        assert result.buff_applied["magnitude"] == 2.0
        assert result.buff_applied["duration"] == 2

    def test_war_cry_buff_in_active_buffs(self):
        player = make_player(class_id="crusader")
        skill_def = get_skill("war_cry")
        resolve_buff(player, skill_def)
        assert len(player.active_buffs) == 1
        buff = player.active_buffs[0]
        assert buff["buff_id"] == "war_cry"
        assert buff["stat"] == "melee_damage_multiplier"
        assert buff["magnitude"] == 2.0
        assert buff["turns_remaining"] == 2

    def test_war_cry_melee_does_double_damage(self):
        """When War Cry buff is active, melee attack deals 2x damage."""
        attacker = make_player(damage=15, active_buffs=[
            {"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 2}
        ])
        defender = make_player(pid="p2", armor=0)
        damage = calculate_damage(attacker, defender)
        # 15 * 2.0 = 30
        assert damage == 30

    def test_war_cry_does_not_affect_ranged(self):
        """War Cry buff is melee only — ranged stays normal."""
        attacker = make_player(ranged_damage=10, active_buffs=[
            {"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 2}
        ])
        defender = make_player(pid="p2", armor=0)
        damage = calculate_ranged_damage(attacker, defender)
        assert damage == 10  # Unaffected

    def test_war_cry_applies_cooldown(self):
        player = make_player(class_id="crusader")
        skill_def = get_skill("war_cry")
        resolve_buff(player, skill_def)
        assert player.cooldowns.get("war_cry") == 5

    def test_war_cry_only_werewolf_can_use(self):
        can, _ = can_use_skill(make_player(class_id="werewolf"), "war_cry")
        assert can is True
        can, _ = can_use_skill(make_player(class_id="crusader"), "war_cry")
        assert can is False
        can, reason = can_use_skill(make_player(class_id="ranger"), "war_cry")
        assert can is False


# ============================================================
# 5. Shadow Step Skill
# ============================================================

class TestShadowStepSkill:
    """Tests for the Shadow Step skill (Hexblade, Inquisitor)."""

    def test_shadow_step_teleports(self):
        player = make_player(pid="p1", class_id="hexblade", x=5, y=5)
        players = {"p1": player}
        skill_def = get_skill("shadow_step")
        result = resolve_teleport(player, 7, 5, skill_def, players, set(), 20, 20)
        assert result.success is True
        assert result.skill_id == "shadow_step"
        assert player.position.x == 7
        assert player.position.y == 5
        assert result.from_x == 5
        assert result.to_x == 7

    def test_shadow_step_blocked_by_obstacle(self):
        player = make_player(pid="p1", class_id="hexblade", x=5, y=5)
        players = {"p1": player}
        skill_def = get_skill("shadow_step")
        result = resolve_teleport(player, 7, 5, skill_def, players, {(7, 5)}, 20, 20)
        assert result.success is False
        assert player.position.x == 5  # Didn't move

    def test_shadow_step_blocked_by_occupied(self):
        player = make_player(pid="p1", class_id="hexblade", x=5, y=5, team="a")
        other = make_player(pid="p2", username="Other", x=7, y=5, team="a")
        players = {"p1": player, "p2": other}
        skill_def = get_skill("shadow_step")
        result = resolve_teleport(player, 7, 5, skill_def, players, set(), 20, 20)
        assert result.success is False

    def test_shadow_step_out_of_range(self):
        player = make_player(pid="p1", class_id="hexblade", x=5, y=5)
        players = {"p1": player}
        skill_def = get_skill("shadow_step")
        # Range is 3 — (5,5) to (10,5) = 5 tiles away
        result = resolve_teleport(player, 10, 5, skill_def, players, set(), 20, 20)
        assert result.success is False

    def test_shadow_step_no_los(self):
        player = make_player(pid="p1", class_id="hexblade", x=5, y=5)
        players = {"p1": player}
        # Block LOS with obstacle between player and target
        obstacles = {(6, 5)}
        skill_def = get_skill("shadow_step")
        result = resolve_teleport(player, 7, 5, skill_def, players, obstacles, 20, 20)
        assert result.success is False
        assert "line of sight" in result.message.lower()

    def test_shadow_step_applies_cooldown(self):
        player = make_player(pid="p1", class_id="hexblade", x=5, y=5)
        players = {"p1": player}
        skill_def = get_skill("shadow_step")
        resolve_teleport(player, 7, 5, skill_def, players, set(), 20, 20)
        assert player.cooldowns.get("shadow_step") == 4

    def test_shadow_step_out_of_bounds(self):
        player = make_player(pid="p1", class_id="hexblade", x=0, y=0)
        players = {"p1": player}
        skill_def = get_skill("shadow_step")
        result = resolve_teleport(player, -1, 0, skill_def, players, set(), 20, 20)
        assert result.success is False

    def test_shadow_step_cant_teleport_to_self(self):
        player = make_player(pid="p1", class_id="hexblade", x=5, y=5)
        players = {"p1": player}
        skill_def = get_skill("shadow_step")
        result = resolve_teleport(player, 5, 5, skill_def, players, set(), 20, 20)
        assert result.success is False

    def test_shadow_step_inquisitor_can_use(self):
        can, _ = can_use_skill(make_player(class_id="inquisitor"), "shadow_step")
        assert can is True

    def test_shadow_step_ranger_cannot_use(self):
        can, reason = can_use_skill(make_player(class_id="ranger"), "shadow_step")
        assert can is False


# ============================================================
# 6. Buff Tick System
# ============================================================

class TestBuffTick:
    """Tests for buff duration tracking and expiry."""

    def test_buff_decrements_each_tick(self):
        player = make_player(active_buffs=[
            {"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 2}
        ])
        expired = tick_buffs(player)
        assert len(player.active_buffs) == 1
        assert player.active_buffs[0]["turns_remaining"] == 1
        assert len(expired) == 0

    def test_buff_removed_when_expired(self):
        player = make_player(active_buffs=[
            {"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 1}
        ])
        expired = tick_buffs(player)
        assert len(player.active_buffs) == 0
        assert len(expired) == 1
        assert expired[0]["buff_id"] == "war_cry"

    def test_multiple_buffs_tick_independently(self):
        player = make_player(active_buffs=[
            {"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 3},
            {"buff_id": "other", "stat": "ranged_damage_multiplier", "magnitude": 1.5, "turns_remaining": 1},
        ])
        expired = tick_buffs(player)
        assert len(player.active_buffs) == 1
        assert player.active_buffs[0]["buff_id"] == "war_cry"
        assert player.active_buffs[0]["turns_remaining"] == 2
        assert len(expired) == 1
        assert expired[0]["buff_id"] == "other"

    def test_no_buffs_no_error(self):
        player = make_player()
        expired = tick_buffs(player)
        assert len(expired) == 0
        assert len(player.active_buffs) == 0

    def test_buff_multiplier_helper(self):
        player = make_player(active_buffs=[
            {"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 2}
        ])
        assert get_melee_buff_multiplier(player) == 2.0
        assert get_ranged_buff_multiplier(player) == 1.0  # No ranged buffs

    def test_no_buff_multiplier_is_one(self):
        player = make_player()
        assert get_melee_buff_multiplier(player) == 1.0
        assert get_ranged_buff_multiplier(player) == 1.0


# ============================================================
# 7. Buff Effects in Combat (combat.py integration)
# ============================================================

class TestBuffsInCombat:
    """Tests for buff effects modifying damage calculations."""

    def test_melee_damage_with_buff(self):
        attacker = make_player(damage=15, armor=0, active_buffs=[
            {"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 1}
        ])
        defender = make_player(pid="p2", armor=0)
        dmg = calculate_damage(attacker, defender)
        assert dmg == 30  # 15 * 2.0

    def test_melee_damage_without_buff(self):
        attacker = make_player(damage=15, armor=0)
        defender = make_player(pid="p2", armor=0)
        dmg = calculate_damage(attacker, defender)
        assert dmg == 15

    def test_ranged_damage_no_melee_buff_effect(self):
        """Melee buff should not affect ranged damage."""
        attacker = make_player(ranged_damage=10, active_buffs=[
            {"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 1}
        ])
        defender = make_player(pid="p2", armor=0)
        dmg = calculate_ranged_damage(attacker, defender)
        assert dmg == 10


# ============================================================
# 8. Skill Dispatch (resolve_skill_action)
# ============================================================

class TestSkillDispatch:
    """Tests for the resolve_skill_action dispatcher."""

    def test_dispatch_heal(self):
        player = make_player(class_id="confessor", hp=60)
        players = {"p1": player}
        skill_def = get_skill("heal")
        action = make_skill_action("p1", "heal", player.position.x, player.position.y)
        result = resolve_skill_action(player, action, skill_def, players, set())
        assert result.success is True
        assert result.heal_amount == 30

    def test_dispatch_double_strike(self):
        attacker = make_player(pid="p1", class_id="crusader", x=5, y=5, damage=15, team="a")
        defender = make_player(pid="p2", username="Enemy", x=6, y=5, hp=100, armor=0, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("double_strike")
        action = make_skill_action("p1", "double_strike", 6, 5)
        result = resolve_skill_action(attacker, action, skill_def, players, set())
        assert result.success is True
        assert result.damage_dealt == 20

    def test_dispatch_power_shot(self):
        attacker = make_player(pid="p1", class_id="ranger", x=5, y=5, ranged_damage=10, team="a")
        defender = make_player(pid="p2", username="Enemy", x=8, y=5, hp=100, armor=0, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("power_shot")
        action = make_skill_action("p1", "power_shot", 8, 5)
        result = resolve_skill_action(attacker, action, skill_def, players, set())
        assert result.success is True
        assert result.damage_dealt == 18

    def test_dispatch_war_cry(self):
        player = make_player(class_id="crusader")
        players = {"p1": player}
        skill_def = get_skill("war_cry")
        action = make_skill_action("p1", "war_cry")
        result = resolve_skill_action(player, action, skill_def, players, set())
        assert result.success is True
        assert result.buff_applied is not None

    def test_dispatch_shadow_step(self):
        player = make_player(pid="p1", class_id="hexblade", x=5, y=5)
        players = {"p1": player}
        skill_def = get_skill("shadow_step")
        action = make_skill_action("p1", "shadow_step", 7, 5)
        result = resolve_skill_action(player, action, skill_def, players, set())
        assert result.success is True
        assert player.position.x == 7

    def test_dispatch_unknown_effect_type(self):
        player = make_player()
        players = {"p1": player}
        fake_def = {
            "skill_id": "fake",
            "name": "Fake",
            "effects": [{"type": "unknown_effect"}],
            "cooldown_turns": 3,
        }
        action = make_skill_action("p1", "fake")
        result = resolve_skill_action(player, action, fake_def, players, set())
        assert result.success is False
        assert "unknown effect type" in result.message.lower()


# ============================================================
# 9. Turn Resolver Integration
# ============================================================

class TestSkillPhaseInTurnResolver:
    """Integration tests: skills resolve correctly in the turn resolver."""

    def test_heal_in_turn_resolver(self):
        player = make_player(pid="p1", class_id="confessor", hp=60)
        players = {"p1": player}
        actions = [make_skill_action("p1", "heal", 5, 5)]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        skill_results = [r for r in result.actions if r.action_type == ActionType.SKILL]
        assert len(skill_results) == 1
        assert skill_results[0].success is True
        assert player.hp == 90

    def test_double_strike_in_turn_resolver(self):
        attacker = make_player(pid="p1", class_id="hexblade", x=5, y=5, damage=15, team="a")
        defender = make_player(pid="p2", username="Enemy", x=6, y=5, hp=100, armor=0, team="b")
        players = {"p1": attacker, "p2": defender}
        actions = [make_skill_action("p1", "double_strike", 6, 5)]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set(),
                              team_a=["p1"], team_b=["p2"])
        skill_results = [r for r in result.actions if r.action_type == ActionType.SKILL]
        assert len(skill_results) == 1
        assert skill_results[0].success is True
        assert defender.hp == 80

    def test_war_cry_then_melee_same_turn(self):
        """War Cry resolves before melee phase — so melee gets 2x buff."""
        attacker = make_player(pid="p1", class_id="werewolf", x=5, y=5, damage=15, team="a")
        defender = make_player(pid="p2", username="Enemy", x=6, y=5, hp=100, armor=0, team="b")
        players = {"p1": attacker, "p2": defender}
        actions = [
            make_skill_action("p1", "war_cry"),
            PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=6, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set(),
                              team_a=["p1"], team_b=["p2"])

        # Skill phase first
        skill_results = [r for r in result.actions if r.action_type == ActionType.SKILL]
        melee_results = [r for r in result.actions if r.action_type == ActionType.ATTACK]
        assert len(skill_results) == 1
        assert skill_results[0].success is True
        assert len(melee_results) == 1
        assert melee_results[0].success is True
        # Melee should be 15 * 2.0 = 30
        assert melee_results[0].damage_dealt == 30

    def test_shadow_step_then_avoid_melee(self):
        """Shadow Step resolves before melee — teleported away, attacker misses."""
        stepper = make_player(pid="p1", class_id="hexblade", x=5, y=5, team="a")
        attacker = make_player(pid="p2", username="Attacker", x=6, y=5, damage=15, team="b")
        players = {"p1": stepper, "p2": attacker}
        actions = [
            make_skill_action("p1", "shadow_step", 8, 5),  # Teleport away
            PlayerAction(player_id="p2", action_type=ActionType.ATTACK, target_x=5, target_y=5),
        ]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set(),
                              team_a=["p1"], team_b=["p2"])
        # Shadow step succeeds
        skill_results = [r for r in result.actions if r.action_type == ActionType.SKILL]
        assert skill_results[0].success is True
        assert stepper.position.x == 8
        # Melee should miss — stepper no longer at (5,5)
        melee_results = [r for r in result.actions if r.action_type == ActionType.ATTACK]
        assert melee_results[0].success is False

    def test_skill_without_skill_id_fails(self):
        player = make_player(pid="p1", class_id="crusader")
        players = {"p1": player}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.SKILL)]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        skill_results = [r for r in result.actions if r.action_type == ActionType.SKILL]
        assert len(skill_results) == 1
        assert skill_results[0].success is False

    def test_skill_wrong_class_fails(self):
        player = make_player(pid="p1", class_id="ranger")  # Ranger can't use heal
        players = {"p1": player}
        actions = [make_skill_action("p1", "heal", 5, 5)]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        skill_results = [r for r in result.actions if r.action_type == ActionType.SKILL]
        assert len(skill_results) == 1
        assert skill_results[0].success is False

    def test_skill_on_cooldown_fails(self):
        player = make_player(pid="p1", class_id="confessor", hp=60, cooldowns={"heal": 3})
        players = {"p1": player}
        actions = [make_skill_action("p1", "heal", 5, 5)]
        # Cooldowns tick first (phase 0.5), so heal goes from 3 -> 2, still blocked
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        skill_results = [r for r in result.actions if r.action_type == ActionType.SKILL]
        assert len(skill_results) == 1
        assert skill_results[0].success is False

    def test_skill_kill_registers_death(self):
        """Kill via skill should appear in deaths list."""
        attacker = make_player(pid="p1", class_id="hexblade", x=5, y=5, damage=15, team="a")
        defender = make_player(pid="p2", username="Enemy", x=6, y=5, hp=5, armor=0, team="b")
        players = {"p1": attacker, "p2": defender}
        actions = [make_skill_action("p1", "double_strike", 6, 5)]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set(),
                              team_a=["p1"], team_b=["p2"])
        assert "p2" in result.deaths
        assert defender.is_alive is False

    def test_buff_ticks_in_turn_resolver(self):
        """Active buffs decrement each turn via buff tick phase."""
        player = make_player(pid="p1", active_buffs=[
            {"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 2}
        ])
        players = {"p1": player}
        actions = []
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        # Buff should have decremented to 1
        assert len(player.active_buffs) == 1
        assert player.active_buffs[0]["turns_remaining"] == 1
        assert len(result.buff_changes) == 1

    def test_buff_expires_in_turn_resolver(self):
        player = make_player(pid="p1", active_buffs=[
            {"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 1}
        ])
        players = {"p1": player}
        actions = []
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        assert len(player.active_buffs) == 0
        assert len(result.buff_changes) == 1
        assert len(result.buff_changes[0]["expired"]) == 1

    def test_dead_player_skill_ignored(self):
        player = make_player(pid="p1", class_id="crusader", hp=0)
        player.is_alive = False
        players = {"p1": player}
        actions = [make_skill_action("p1", "double_strike", 6, 5)]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        skill_results = [r for r in result.actions if r.action_type == ActionType.SKILL]
        assert len(skill_results) == 0

    def test_power_shot_in_turn_resolver(self):
        attacker = make_player(pid="p1", class_id="ranger", x=5, y=5, ranged_damage=10, team="a")
        defender = make_player(pid="p2", username="Enemy", x=8, y=5, hp=100, armor=0, team="b")
        players = {"p1": attacker, "p2": defender}
        actions = [make_skill_action("p1", "power_shot", 8, 5)]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set(),
                              team_a=["p1"], team_b=["p2"])
        skill_results = [r for r in result.actions if r.action_type == ActionType.SKILL]
        assert len(skill_results) == 1
        assert skill_results[0].success is True
        assert skill_results[0].damage_dealt == 18


# ============================================================
# 10. Backward Compatibility
# ============================================================

class TestBackwardCompat:
    """Ensure skill additions don't break existing turn resolver behavior."""

    def test_no_skill_actions_works(self):
        p1 = make_player(pid="p1", x=5, y=5, team="a")
        p2 = make_player(pid="p2", x=6, y=5, team="b")
        players = {"p1": p1, "p2": p2}
        actions = [
            PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=6, target_y=5)
        ]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set(),
                              team_a=["p1"], team_b=["p2"])
        assert result.actions[0].success is True
        assert result.buff_changes == []

    def test_move_still_works(self):
        p1 = make_player(pid="p1", x=5, y=5)
        players = {"p1": p1}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.MOVE, target_x=6, target_y=5)]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        assert result.actions[0].success is True
        assert p1.position.x == 6

    def test_ranged_still_works(self):
        p1 = make_player(pid="p1", x=5, y=5, team="a", ranged_damage=10)
        p2 = make_player(pid="p2", x=8, y=5, team="b", hp=100, armor=0)
        players = {"p1": p1, "p2": p2}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.RANGED_ATTACK,
                                target_x=8, target_y=5)]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set(),
                              team_a=["p1"], team_b=["p2"])
        ranged_results = [r for r in result.actions if r.action_type == ActionType.RANGED_ATTACK]
        assert len(ranged_results) == 1
        assert ranged_results[0].success is True

    def test_empty_turn_with_buffs_field(self):
        p1 = make_player(pid="p1")
        players = {"p1": p1}
        result = resolve_turn("m1", 1, players, [], 20, 20, set())
        assert result.buff_changes == []


# ============================================================
# 11. Double Strike with War Cry Buff
# ============================================================

class TestDoubleStrikeWithBuff:
    """Double Strike damage should also be boosted by War Cry buff."""

    def test_double_strike_with_war_cry(self):
        attacker = make_player(
            pid="p1", class_id="crusader", x=5, y=5, damage=15, team="a",
            active_buffs=[
                {"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 2}
            ]
        )
        defender = make_player(pid="p2", username="Enemy", x=6, y=5, hp=100, armor=0, team="b")
        players = {"p1": attacker, "p2": defender}
        skill_def = get_skill("double_strike")
        result = resolve_multi_hit(attacker, 6, 5, skill_def, players, set())
        assert result.success is True
        # raw_damage = 15 * 2.0 = 30, per-hit = floor(30 * 0.7) = 21, 2 hits = 42
        assert result.damage_dealt == 42


# ============================================================
# 12. Phase 14C — DoT/HoT Tick is_tick Flag
# ============================================================

class TestTickFloaterFlag:
    """Verify that DoT and HoT tick ActionResults carry is_tick=True,
    while direct skill casts do NOT have is_tick set."""

    def test_dot_tick_has_is_tick_flag(self):
        """Wither DoT tick result should have is_tick=True."""
        victim = make_player(
            pid="p1", hp=80, max_hp=100,
            active_buffs=[
                {"buff_id": "wither", "type": "dot", "damage_per_tick": 6, "turns_remaining": 3}
            ]
        )
        players = {"p1": victim}
        result = resolve_turn("m1", 1, players, [], 20, 20, set())
        dot_results = [r for r in result.actions
                       if r.action_type == ActionType.SKILL and r.damage_dealt and r.is_tick]
        assert len(dot_results) == 1
        assert dot_results[0].skill_id == "wither"
        assert dot_results[0].damage_dealt == 6
        assert dot_results[0].is_tick is True

    def test_hot_tick_has_is_tick_flag(self):
        """Prayer HoT tick result should have is_tick=True."""
        target = make_player(
            pid="p1", hp=70, max_hp=100,
            active_buffs=[
                {"buff_id": "prayer", "type": "hot", "heal_per_tick": 4, "turns_remaining": 3}
            ]
        )
        players = {"p1": target}
        result = resolve_turn("m1", 1, players, [], 20, 20, set())
        hot_results = [r for r in result.actions
                       if r.action_type == ActionType.SKILL and r.heal_amount and r.is_tick]
        assert len(hot_results) == 1
        assert hot_results[0].skill_id == "prayer"
        assert hot_results[0].heal_amount > 0
        assert hot_results[0].is_tick is True

    def test_direct_skill_does_not_have_is_tick(self):
        """Direct skill cast (e.g. Heal) should have is_tick=False (default)."""
        healer = make_player(pid="p1", class_id="confessor", x=5, y=5, hp=60, team="a")
        players = {"p1": healer}
        actions = [make_skill_action("p1", "heal", 5, 5)]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        heal_results = [r for r in result.actions
                        if r.action_type == ActionType.SKILL and r.heal_amount]
        assert len(heal_results) == 1
        assert heal_results[0].is_tick is False

    def test_dot_and_hot_ticks_same_turn(self):
        """Unit with both DoT and HoT should generate two tick results, both is_tick=True."""
        unit = make_player(
            pid="p1", hp=60, max_hp=100,
            active_buffs=[
                {"buff_id": "wither", "type": "dot", "damage_per_tick": 6, "turns_remaining": 2},
                {"buff_id": "prayer", "type": "hot", "heal_per_tick": 4, "turns_remaining": 2},
            ]
        )
        players = {"p1": unit}
        result = resolve_turn("m1", 1, players, [], 20, 20, set())
        tick_results = [r for r in result.actions if r.is_tick]
        assert len(tick_results) == 2
        dot_tick = [r for r in tick_results if r.damage_dealt]
        hot_tick = [r for r in tick_results if r.heal_amount]
        assert len(dot_tick) == 1
        assert len(hot_tick) == 1

    def test_dot_kill_does_not_have_is_tick_on_death_result(self):
        """The death notification from DoT shouldn't have is_tick (it's not a tick, it's a death event)."""
        victim = make_player(
            pid="p1", hp=3, max_hp=100,
            active_buffs=[
                {"buff_id": "wither", "type": "dot", "damage_per_tick": 6, "turns_remaining": 2}
            ]
        )
        players = {"p1": victim}
        result = resolve_turn("m1", 1, players, [], 20, 20, set())
        death_results = [r for r in result.actions if r.killed]
        assert len(death_results) >= 1
        # The death announcement itself should NOT be a tick
        for dr in death_results:
            if "killed" in dr.message:
                assert dr.is_tick is False


# ============================================================
# 13. Phase 14D — Miss / Dodge / Stunned / Slowed Action Results
# ============================================================

class TestMissDodgeStunnedFloaterData:
    """Verify that failed attack/skill ActionResults contain the data needed
    by the client-side 14D floater logic: success=False, descriptive message,
    and target_id where applicable."""

    def test_melee_dodge_has_target_id_and_dodged_message(self):
        """When melee attack is dodged via evasion, result has target_id and 'DODGED' in message."""
        attacker = make_player(pid="atk", x=5, y=5, team="a")
        defender = make_player(
            pid="def", x=6, y=5, team="b", username="Dodger",
            active_buffs=[{"type": "evasion", "charges": 1, "turns_remaining": 3, "buff_id": "evasion"}],
        )
        players = {"atk": attacker, "def": defender}
        actions = [PlayerAction(player_id="atk", action_type=ActionType.ATTACK, target_x=6, target_y=5, target_id="def")]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        dodge_results = [r for r in result.actions
                         if r.action_type == ActionType.ATTACK and not r.success
                         and "DODGED" in (r.message or "")]
        assert len(dodge_results) == 1
        assert dodge_results[0].target_id == "def"
        assert dodge_results[0].player_id == "atk"

    def test_ranged_dodge_has_target_id_and_dodged_message(self):
        """When ranged attack is dodged via evasion, result has target_id and 'DODGED' in message."""
        attacker = make_player(pid="atk", x=5, y=5, team="a", ranged_range=5)
        defender = make_player(
            pid="def", x=8, y=5, team="b", username="Dodger",
            active_buffs=[{"type": "evasion", "charges": 1, "turns_remaining": 3, "buff_id": "evasion"}],
        )
        players = {"atk": attacker, "def": defender}
        actions = [PlayerAction(player_id="atk", action_type=ActionType.RANGED_ATTACK, target_x=8, target_y=5, target_id="def")]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        dodge_results = [r for r in result.actions
                         if r.action_type == ActionType.RANGED_ATTACK and not r.success
                         and "DODGED" in (r.message or "")]
        assert len(dodge_results) == 1
        assert dodge_results[0].target_id == "def"

    def test_stunned_melee_has_stunned_message(self):
        """Stunned unit trying to melee should get success=False with 'stunned' in message."""
        stunned_unit = make_player(
            pid="p1", x=5, y=5, team="a",
            active_buffs=[{"type": "stun", "turns_remaining": 2, "buff_id": "shield_bash_stun"}],
        )
        target = make_player(pid="p2", x=6, y=5, team="b")
        players = {"p1": stunned_unit, "p2": target}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=6, target_y=5, target_id="p2")]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        stun_results = [r for r in result.actions
                        if r.player_id == "p1" and not r.success
                        and "stunned" in (r.message or "").lower()]
        assert len(stun_results) >= 1

    def test_stunned_ranged_has_stunned_message(self):
        """Stunned unit trying to shoot should get success=False with 'stunned' in message."""
        stunned_unit = make_player(
            pid="p1", x=5, y=5, team="a",
            active_buffs=[{"type": "stun", "turns_remaining": 2, "buff_id": "shield_bash_stun"}],
        )
        target = make_player(pid="p2", x=8, y=5, team="b")
        players = {"p1": stunned_unit, "p2": target}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.RANGED_ATTACK, target_x=8, target_y=5, target_id="p2")]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        stun_results = [r for r in result.actions
                        if r.player_id == "p1" and not r.success
                        and "stunned" in (r.message or "").lower()]
        assert len(stun_results) >= 1

    def test_melee_miss_out_of_range(self):
        """Melee attack against non-adjacent target should fail with 'out of range' message."""
        attacker = make_player(pid="atk", x=5, y=5, team="a")
        target = make_player(pid="def", x=8, y=5, team="b")
        players = {"atk": attacker, "def": target}
        actions = [PlayerAction(player_id="atk", action_type=ActionType.ATTACK, target_x=8, target_y=5)]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        miss_results = [r for r in result.actions
                        if r.action_type == ActionType.ATTACK and not r.success
                        and "out of range" in (r.message or "").lower()]
        assert len(miss_results) == 1

    def test_ward_reflect_generates_reflect_result(self):
        """Ward reflect should generate a successful skill action with 'reflects' in message."""
        attacker = make_player(pid="atk", x=5, y=5, team="a", damage=20)
        defender = make_player(
            pid="def", x=6, y=5, team="b",
            active_buffs=[{"type": "shield_charges", "charges": 1, "reflect_damage": 10,
                           "turns_remaining": 5, "buff_id": "ward"}],
        )
        players = {"atk": attacker, "def": defender}
        actions = [PlayerAction(player_id="atk", action_type=ActionType.ATTACK, target_x=6, target_y=5, target_id="def")]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        reflect_results = [r for r in result.actions
                           if r.skill_id == "ward" and r.success
                           and "reflects" in (r.message or "").lower()]
        assert len(reflect_results) == 1
        assert reflect_results[0].target_id == "atk"
        assert reflect_results[0].damage_dealt > 0


# ============================================================
# Phase 14E: CC Visual Overlay Data Tests
# ============================================================

class TestCCVisualOverlayData:
    """Verify that CC buff state is correctly preserved in turn results
    and player snapshots so the client can render visual overlays.

    Phase 14E requires:
    - Stun buffs appear in player active_buffs with type='stun'
    - Slow buffs appear in player active_buffs with type='slow'
    - Taunt buffs appear in player active_buffs with type='taunt'
    - CC buffs decrement turns_remaining each turn
    - Expired CC buffs are removed
    """

    def test_stun_buff_present_in_active_buffs(self):
        """Unit with stun buff has type='stun' entry in active_buffs for client rendering."""
        from app.core.skills import is_stunned
        stunned = make_player(
            pid="p1", x=5, y=5,
            active_buffs=[{"type": "stun", "turns_remaining": 2, "buff_id": "shield_bash_stun"}],
        )
        assert is_stunned(stunned)
        stun_buffs = [b for b in stunned.active_buffs if b.get("type") == "stun"]
        assert len(stun_buffs) == 1
        assert stun_buffs[0]["turns_remaining"] == 2

    def test_slow_buff_present_in_active_buffs(self):
        """Unit with slow buff has type='slow' entry in active_buffs for client rendering."""
        from app.core.skills import is_slowed
        slowed = make_player(
            pid="p1", x=5, y=5,
            active_buffs=[{"type": "slow", "turns_remaining": 3, "buff_id": "crippling_shot_slow"}],
        )
        assert is_slowed(slowed)
        slow_buffs = [b for b in slowed.active_buffs if b.get("type") == "slow"]
        assert len(slow_buffs) == 1
        assert slow_buffs[0]["turns_remaining"] == 3

    def test_taunt_buff_present_in_active_buffs(self):
        """Unit with taunt buff has type='taunt' entry with source_id for client rendering."""
        from app.core.skills import is_taunted
        taunted = make_player(
            pid="p1", x=5, y=5,
            active_buffs=[{"type": "taunt", "turns_remaining": 2, "buff_id": "taunt", "source_id": "taunter1"}],
        )
        is_t, source = is_taunted(taunted)
        assert is_t is True
        assert source == "taunter1"
        taunt_buffs = [b for b in taunted.active_buffs if b.get("type") == "taunt"]
        assert len(taunt_buffs) == 1
        assert taunt_buffs[0]["source_id"] == "taunter1"

    def test_stun_buff_decrements_on_tick(self):
        """Stun buff turns_remaining decrements after resolve_turn tick."""
        stunned = make_player(
            pid="p1", x=5, y=5, team="a",
            active_buffs=[{"type": "stun", "turns_remaining": 2, "buff_id": "shield_bash_stun"}],
        )
        idle = make_player(pid="p2", x=10, y=10, team="b")
        players = {"p1": stunned, "p2": idle}
        result = resolve_turn("m1", 1, players, [], 20, 20, set())
        # After one turn, remaining should be 1
        remaining_stun = [b for b in stunned.active_buffs if b.get("type") == "stun"]
        assert len(remaining_stun) == 1
        assert remaining_stun[0]["turns_remaining"] == 1

    def test_stun_buff_expires_after_final_tick(self):
        """Stun buff with turns_remaining=1 should be removed after one tick."""
        stunned = make_player(
            pid="p1", x=5, y=5, team="a",
            active_buffs=[{"type": "stun", "turns_remaining": 1, "buff_id": "shield_bash_stun"}],
        )
        idle = make_player(pid="p2", x=10, y=10, team="b")
        players = {"p1": stunned, "p2": idle}
        result = resolve_turn("m1", 1, players, [], 20, 20, set())
        # Stun should be expired and removed
        remaining_stun = [b for b in stunned.active_buffs if b.get("type") == "stun"]
        assert len(remaining_stun) == 0

    def test_slow_buff_decrements_on_tick(self):
        """Slow buff turns_remaining decrements after resolve_turn tick."""
        slowed = make_player(
            pid="p1", x=5, y=5, team="a",
            active_buffs=[{"type": "slow", "turns_remaining": 3, "buff_id": "crippling_shot_slow"}],
        )
        idle = make_player(pid="p2", x=10, y=10, team="b")
        players = {"p1": slowed, "p2": idle}
        result = resolve_turn("m1", 1, players, [], 20, 20, set())
        remaining_slow = [b for b in slowed.active_buffs if b.get("type") == "slow"]
        assert len(remaining_slow) == 1
        assert remaining_slow[0]["turns_remaining"] == 2

    def test_stunned_unit_action_blocked_with_buffs_intact(self):
        """Stunned unit's melee is blocked but stun buff remains in active_buffs for rendering."""
        stunned = make_player(
            pid="p1", x=5, y=5, team="a",
            active_buffs=[{"type": "stun", "turns_remaining": 2, "buff_id": "shield_bash_stun"}],
        )
        target = make_player(pid="p2", x=6, y=5, team="b")
        players = {"p1": stunned, "p2": target}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=6, target_y=5, target_id="p2")]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        # Attack should have been blocked
        blocked = [r for r in result.actions if r.player_id == "p1" and not r.success]
        assert len(blocked) >= 1
        # But stun buff should still be in active_buffs (decremented to 1)
        stun_buffs = [b for b in stunned.active_buffs if b.get("type") == "stun"]
        assert len(stun_buffs) == 1
        assert stun_buffs[0]["turns_remaining"] == 1


# ============================================================
# 15. Phase 14F — Critical / Overkill Hit Emphasis Data
# ============================================================

class TestCriticalOverkillHitData:
    """Verify that high-damage hits and kill blows produce the data fields
    the client needs for Phase 14F critical/overkill visual emphasis:
    - damage_dealt is present and accurate for all damage actions
    - killed is True on lethal blows
    - kill + high-damage can co-occur on the same action result
    - ActionResult always includes damage_dealt for the client to scale font size
    """

    def test_melee_kill_has_killed_and_damage_dealt(self):
        """Lethal melee hit should have both killed=True and damage_dealt set."""
        attacker = make_player(pid="p1", x=5, y=5, damage=50, team="a")
        victim = make_player(pid="p2", x=6, y=5, hp=10, team="b")
        players = {"p1": attacker, "p2": victim}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.ATTACK,
                                target_x=6, target_y=5, target_id="p2")]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        kill_results = [r for r in result.actions
                        if r.player_id == "p1" and r.action_type == ActionType.ATTACK and r.killed]
        assert len(kill_results) >= 1
        kr = kill_results[0]
        assert kr.killed is True
        assert kr.damage_dealt is not None
        assert kr.damage_dealt > 0

    def test_high_damage_melee_exceeds_threshold(self):
        """A strong melee swing (high attack_damage) should produce damage_dealt >= 25
        so the client fires the critical-hit particle."""
        # War Cry 2x multiplier + high base damage to reliably exceed threshold
        attacker = make_player(pid="p1", x=5, y=5, damage=30, armor=0, team="a",
                               active_buffs=[{"type": "buff", "stat": "melee_multiplier",
                                              "multiplier": 2.0, "turns_remaining": 2,
                                              "buff_id": "war_cry_buff"}])
        victim = make_player(pid="p2", x=6, y=5, hp=200, armor=0, team="b")
        players = {"p1": attacker, "p2": victim}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.ATTACK,
                                target_x=6, target_y=5, target_id="p2")]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        hits = [r for r in result.actions
                if r.player_id == "p1" and r.action_type == ActionType.ATTACK
                and r.success and r.damage_dealt]
        assert len(hits) >= 1
        assert hits[0].damage_dealt >= 25, \
            f"Expected high damage >= 25, got {hits[0].damage_dealt}"

    def test_ranged_kill_has_killed_and_damage(self):
        """Lethal ranged attack should have killed=True and damage_dealt."""
        shooter = make_player(pid="p1", x=5, y=5, ranged_damage=20, team="a",
                              class_id="ranger", ranged_range=6)
        victim = make_player(pid="p2", x=5, y=8, hp=5, team="b")
        players = {"p1": shooter, "p2": victim}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.RANGED_ATTACK,
                                target_x=5, target_y=8, target_id="p2")]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        kills = [r for r in result.actions
                 if r.player_id == "p1" and r.killed]
        assert len(kills) >= 1
        assert kills[0].damage_dealt is not None
        assert kills[0].damage_dealt > 0

    def test_skill_damage_has_damage_dealt_field(self):
        """Skill damage (e.g. Power Shot) should carry damage_dealt for font scaling."""
        caster = make_player(pid="p1", x=5, y=5, ranged_damage=20, team="a",
                             class_id="ranger", ranged_range=6)
        victim = make_player(pid="p2", x=5, y=8, hp=200, armor=0, team="b")
        players = {"p1": caster, "p2": victim}
        actions = [make_skill_action("p1", "power_shot", 5, 8)]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        dmg_results = [r for r in result.actions
                       if r.player_id == "p1" and r.action_type == ActionType.SKILL
                       and r.damage_dealt]
        assert len(dmg_results) >= 1
        assert dmg_results[0].damage_dealt > 0

    def test_low_damage_still_has_damage_dealt(self):
        """Even low-damage attacks should carry damage_dealt for client font tier logic."""
        attacker = make_player(pid="p1", x=5, y=5, damage=5, team="a")
        victim = make_player(pid="p2", x=6, y=5, hp=200, armor=3, team="b")
        players = {"p1": attacker, "p2": victim}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.ATTACK,
                                target_x=6, target_y=5, target_id="p2")]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        hits = [r for r in result.actions
                if r.player_id == "p1" and r.action_type == ActionType.ATTACK
                and r.success and r.damage_dealt]
        assert len(hits) >= 1
        assert hits[0].damage_dealt > 0
        assert hits[0].damage_dealt <= 10, \
            f"Expected low damage <= 10 with 5 atk vs 3 armor, got {hits[0].damage_dealt}"

    def test_overkill_has_both_killed_and_high_damage(self):
        """Massive overkill (50 dmg vs 5 HP) should have killed=True AND high damage_dealt,
        allowing the client to fire both death-burst and critical-hit particles."""
        attacker = make_player(pid="p1", x=5, y=5, damage=50, team="a")
        victim = make_player(pid="p2", x=6, y=5, hp=5, armor=0, team="b")
        players = {"p1": attacker, "p2": victim}
        actions = [PlayerAction(player_id="p1", action_type=ActionType.ATTACK,
                                target_x=6, target_y=5, target_id="p2")]
        result = resolve_turn("m1", 1, players, actions, 20, 20, set())
        kills = [r for r in result.actions
                 if r.player_id == "p1" and r.action_type == ActionType.ATTACK and r.killed]
        assert len(kills) >= 1
        kr = kills[0]
        assert kr.killed is True
        assert kr.damage_dealt is not None
        assert kr.damage_dealt >= 25, \
            f"Overkill damage should be high, got {kr.damage_dealt}"
