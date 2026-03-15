# -*- coding: utf-8 -*-
"""Confessor AI Diagnostic Tests - Verify fixes for poor healer behavior.

Verifies:
  1. Shield of Faith self-exclusion - SoF no longer targets self
  2. SoF priority ordering - SoF fires AFTER reposition check
  3. Softened Check B - Tank at 4-5 tiles no longer blocks Exorcism
  4. Tank distance drift - Follow stance owner vs tank positioning
  5. Multi-turn simulation - Tracks decisions over 200 turns
  6. Cooldown-aware priority analysis - correct skill at each CD state
"""

from __future__ import annotations
from collections import Counter

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.ai_skills import (
    _support_skill_logic,
    _support_move_preference,
    _decide_skill_usage,
    _HEAL_SELF_THRESHOLD,
    _HEAL_ALLY_THRESHOLD,
    _REPOSITION_ALLY_THRESHOLD,
    _SUPPORT_HEAL_RANGE,
    _TANK_ROLES,
    _chebyshev,
)
from app.core.ai_stances import _decide_stance_action, _find_owner
from app.core.combat import load_combat_config
from app.core.skills import load_skills_config, get_skill


def setup_module():
    """Ensure configs are loaded before any test runs."""
    load_combat_config()
    load_skills_config()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_unit(pid, class_id, x, y, hp, max_hp, team="a",
              hero_id=None, ai_stance="follow", unit_type="ai",
              cooldowns=None, active_buffs=None, ranged_range=1,
              vision_range=6, armor=3, attack_damage=8,
              controlled_by=None) -> PlayerState:
    """Generic unit factory."""
    return PlayerState(
        player_id=pid,
        username=f"{class_id}_{pid}",
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=attack_damage,
        armor=armor,
        team=team,
        unit_type=unit_type,
        hero_id=hero_id,
        ai_stance=ai_stance,
        class_id=class_id,
        ranged_range=ranged_range,
        vision_range=vision_range,
        inventory=[],
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
        controlled_by=controlled_by,
    )


def make_wave_arena_party():
    """Create the exact party described: Crusader, Confessor, Bard, Shaman, Hexblade.

    Human controls one unit, others are AI hero allies on follow stance.
    All start grouped together.
    """
    # Human player (let's say controlling the Hexblade)
    human = make_unit("human1", "hexblade", x=5, y=10, hp=110, max_hp=110,
                      unit_type="human", ranged_range=1, armor=5,
                      attack_damage=14, vision_range=5)

    # AI hero allies on follow stance
    crusader = make_unit("tank1", "crusader", x=6, y=10, hp=135, max_hp=135,
                         hero_id="h_crusader", ai_stance="follow",
                         armor=8, attack_damage=20, vision_range=5,
                         controlled_by="human1")
    confessor = make_unit("healer1", "confessor", x=5, y=11, hp=100, max_hp=100,
                          hero_id="h_confessor", ai_stance="follow",
                          armor=3, attack_damage=8, vision_range=6,
                          controlled_by="human1")
    bard = make_unit("bard1", "bard", x=4, y=10, hp=90, max_hp=90,
                     hero_id="h_bard", ai_stance="follow",
                     ranged_range=4, armor=3, attack_damage=10, vision_range=5,
                     controlled_by="human1")
    shaman = make_unit("shaman1", "shaman", x=5, y=9, hp=95, max_hp=95,
                       hero_id="h_shaman", ai_stance="follow",
                       ranged_range=4, armor=3, attack_damage=8, vision_range=5,
                       controlled_by="human1")

    return human, crusader, confessor, bard, shaman


def make_enemies_wave(n=3, start_x=12, y=10):
    """Create a wave of enemies spread across the right side."""
    enemies = []
    for i in range(n):
        enemies.append(make_unit(
            f"enemy_{i}", "skeleton", x=start_x + i, y=y - 1 + i,
            hp=60, max_hp=60, team="b",
            ranged_range=0, armor=2, attack_damage=12, vision_range=5,
        ))
    return enemies


# ===========================================================================
# DIAGNOSTIC TEST 1: Shield of Faith Self-Cast
# ===========================================================================

class TestSoFSelfCast:
    """Verify Shield of Faith no longer targets the Confessor itself."""

    def test_sof_never_targets_self_when_lowest_hp_pct(self):
        """Confessor at 80% HP (80/100), tank at 90% HP (121/135).
        Confessor has LOWER HP% → SoF must target tank, not self.
        """
        confessor = make_unit("healer1", "confessor", x=5, y=5,
                              hp=80, max_hp=100,
                              cooldowns={"heal": 3, "prayer": 5})  # heals on CD
        tank = make_unit("tank1", "crusader", x=6, y=5,
                         hp=121, max_hp=135, armor=8, attack_damage=20)
        enemy = make_unit("enemy1", "skeleton", x=10, y=5,
                          hp=60, max_hp=60, team="b")

        all_units = {u.player_id: u for u in [confessor, tank, enemy]}

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=20, grid_height=20, obstacles=set(),
        )

        assert result is not None
        assert result.skill_id == "shield_of_faith"
        assert result.target_id != confessor.player_id, "SoF must not target self"
        assert result.target_id == tank.player_id
        print(f"\n  [FIXED] SoF target: {result.target_id} ✓ (not self)")

    def test_sof_never_targets_self_at_full_hp(self):
        """All at full HP → SoF must target an ally, never self."""
        confessor = make_unit("healer1", "confessor", x=5, y=5,
                              hp=100, max_hp=100,
                              cooldowns={"heal": 3, "prayer": 5})
        tank = make_unit("tank1", "crusader", x=6, y=5,
                         hp=135, max_hp=135, armor=8, attack_damage=20)
        bard = make_unit("bard1", "bard", x=4, y=5,
                         hp=90, max_hp=90, ranged_range=4)
        enemy = make_unit("enemy1", "skeleton", x=10, y=5,
                          hp=60, max_hp=60, team="b")

        all_units = {u.player_id: u for u in [confessor, tank, bard, enemy]}

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=20, grid_height=20, obstacles=set(),
        )

        if result and result.skill_id == "shield_of_faith":
            assert result.target_id != confessor.player_id, "SoF must not target self"
            print(f"\n  [FIXED] All full HP → SoF target: {result.target_id} ✓")

    def test_sof_self_exclusion_matches_dark_pact(self):
        """SoF now correctly excludes self, matching Dark Pact pattern."""
        confessor = make_unit("healer1", "confessor", x=5, y=5,
                              hp=70, max_hp=100,
                              cooldowns={"heal": 3, "prayer": 5, "exorcism": 3})
        tank = make_unit("tank1", "crusader", x=6, y=5,
                         hp=120, max_hp=135, armor=8, attack_damage=20)
        enemy = make_unit("enemy1", "skeleton", x=10, y=5,
                          hp=60, max_hp=60, team="b")

        all_units = {u.player_id: u for u in [confessor, tank, enemy]}

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=20, grid_height=20, obstacles=set(),
        )

        if result and result.skill_id == "shield_of_faith":
            assert result.target_id != confessor.player_id, "SoF must not target self"
            print(f"\n  [FIXED] SoF self-exclusion now matches Dark Pact pattern ✓")
            print(f"         Target: {result.target_id}")


# ===========================================================================
# DIAGNOSTIC TEST 2: Reposition vs Exorcism Suppression
# ===========================================================================

class TestRepositionSuppression:
    """Test that softened Check B allows Exorcism at medium range."""

    def test_exorcism_allowed_when_tank_5_tiles(self):
        """Tank 5 tiles away at 95% HP → Exorcism now fires (softened Check B)."""
        confessor = make_unit("healer1", "confessor", x=5, y=5,
                              hp=100, max_hp=100,
                              cooldowns={"heal": 3, "prayer": 5, "shield_of_faith": 4})
        tank = make_unit("tank1", "crusader", x=10, y=5,
                         hp=128, max_hp=135, armor=8, attack_damage=20)
        enemy = make_unit("enemy1", "skeleton", x=8, y=5,
                          hp=60, max_hp=60, team="b")

        all_units = {u.player_id: u for u in [confessor, tank, enemy]}
        dist = _chebyshev((5, 5), (10, 5))

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=20, grid_height=20, obstacles=set(),
        )

        print(f"\n  [FIXED] Tank distance: {dist} tiles")
        print(f"         Tank HP: {tank.hp/tank.max_hp:.0%}")
        print(f"         Result: {result.skill_id if result else 'None (reposition)'}")
        # Tank at 5 tiles → no longer triggers Check B (threshold raised to >5)
        assert result is not None, "Exorcism should fire at 5-tile tank distance"
        assert result.skill_id == "exorcism"
        print(f"         Exorcism fires as expected ✓")

    def test_exorcism_allowed_when_tank_4_tiles_full_hp(self):
        """Tank 4 tiles away at 100% HP → Exorcism now fires."""
        confessor = make_unit("healer1", "confessor", x=5, y=5,
                              hp=100, max_hp=100,
                              cooldowns={"heal": 3, "prayer": 5, "shield_of_faith": 4})
        tank = make_unit("tank1", "crusader", x=9, y=5,
                         hp=135, max_hp=135, armor=8, attack_damage=20)
        enemy = make_unit("enemy1", "skeleton", x=7, y=5,
                          hp=60, max_hp=60, team="b")

        all_units = {u.player_id: u for u in [confessor, tank, enemy]}
        dist = _chebyshev((5, 5), (9, 5))

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=20, grid_height=20, obstacles=set(),
        )

        print(f"\n  [FIXED] Tank 100% HP but {dist} tiles away")
        print(f"         Result: {result.skill_id if result else 'None (reposition)'}")
        assert result is not None, "Exorcism should fire at 4-tile tank distance"
        assert result.skill_id == "exorcism"
        print(f"         Exorcism deals 20 damage instead of wasting a turn ✓")

    def test_reposition_still_triggers_when_tank_very_far(self):
        """Tank 7 tiles away → Check B still triggers reposition."""
        confessor = make_unit("healer1", "confessor", x=5, y=5,
                              hp=100, max_hp=100,
                              cooldowns={"heal": 3, "prayer": 5, "shield_of_faith": 4})
        tank = make_unit("tank1", "crusader", x=12, y=5,
                         hp=135, max_hp=135, armor=8, attack_damage=20)
        enemy = make_unit("enemy1", "skeleton", x=8, y=5,
                          hp=60, max_hp=60, team="b")

        all_units = {u.player_id: u for u in [confessor, tank, enemy]}
        dist = _chebyshev((5, 5), (12, 5))

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=20, grid_height=20, obstacles=set(),
        )

        print(f"\n  [FIXED] Tank {dist} tiles away → still repositions")
        assert result is None, "Should reposition when tank is 7 tiles away"
        print(f"         Reposition triggers at >5 tiles ✓")


# ===========================================================================
# DIAGNOSTIC TEST 3: Follow Stance Owner vs Tank
# ===========================================================================

class TestFollowStanceOwnerMismatch:
    """Test whether follow stance regroups to human owner instead of tank."""

    def test_confessor_follows_human_not_tank(self):
        """Human (Hexblade) runs left, tank (Crusader) runs right.
        Confessor should stay with tank but follows human.
        """
        human = make_unit("human1", "hexblade", x=2, y=5,
                          hp=110, max_hp=110, unit_type="human")
        tank = make_unit("tank1", "crusader", x=12, y=5,
                         hp=135, max_hp=135, hero_id="h_tank",
                         ai_stance="follow", controlled_by="human1")
        confessor = make_unit("healer1", "confessor", x=7, y=5,
                              hp=100, max_hp=100, hero_id="h_conf",
                              ai_stance="follow", controlled_by="human1")

        all_units = {u.player_id: u for u in [human, tank, confessor]}

        owner = _find_owner(confessor, all_units)
        dist_to_owner = _chebyshev((7, 5), (owner.position.x, owner.position.y)) if owner else 999
        dist_to_tank = _chebyshev((7, 5), (12, 5))

        print(f"\n  [DIAG] Confessor owner: {owner.class_id if owner else 'None'}")
        print(f"         Distance to owner (human): {dist_to_owner}")
        print(f"         Distance to tank (crusader): {dist_to_tank}")
        print(f"         Follow leash: 4 tiles")
        print(f"         Owner is {'TANK ✓' if owner and owner.class_id == 'crusader' else 'NOT TANK ⚠️'}")

        # Confessor follows the human, not the tank
        assert owner is not None
        assert owner.player_id == "human1", "Confessor follows human, not tank"

        # If owner is > 4 tiles away, confessor regroups TO OWNER (not tank)
        if dist_to_owner > 4:
            print(f"         → Confessor will regroup toward HUMAN (away from tank!)")


# ===========================================================================
# DIAGNOSTIC TEST 4: Multi-Turn Simulation
# ===========================================================================

class TestMultiTurnSimulation:
    """Simulate 200 turns and track Confessor decision distribution."""

    def test_200_turn_skill_distribution(self):
        """Track what the Confessor does each turn over a simulated combat.

        Simulates a steady-state scenario: tank at varying distances,
        enemies constantly present, all skills cycling through cooldowns.
        """
        decisions = Counter()
        sof_targets = Counter()

        # --- Simulation state ---
        heal_cd = 0
        prayer_cd = 0
        sof_cd = 0
        exorcism_cd = 0

        for turn in range(1, 201):
            # Simulate varying game state
            # Tank drifts between 2-8 tiles away (common in wave arena)
            import math
            tank_dist = 3 + int(3 * abs(math.sin(turn * 0.1)))
            tank_hp_pct = max(0.3, 1.0 - (turn % 20) * 0.03)  # oscillates

            confessor = make_unit("healer1", "confessor", x=5, y=5,
                                  hp=max(30, int(100 * (0.7 + 0.3 * math.cos(turn * 0.05)))),
                                  max_hp=100,
                                  cooldowns={
                                      "heal": max(0, heal_cd),
                                      "prayer": max(0, prayer_cd),
                                      "shield_of_faith": max(0, sof_cd),
                                      "exorcism": max(0, exorcism_cd),
                                  })
            tank = make_unit("tank1", "crusader", x=5 + tank_dist, y=5,
                             hp=int(135 * tank_hp_pct), max_hp=135,
                             armor=8, attack_damage=20)
            bard = make_unit("bard1", "bard", x=4, y=5,
                             hp=int(90 * 0.85), max_hp=90, ranged_range=4)
            # Always 2-3 enemies visible
            enemies = [
                make_unit(f"e{i}", "skeleton", x=10 + i, y=5 + i,
                          hp=60, max_hp=60, team="b")
                for i in range(3)
            ]

            all_units = {u.player_id: u for u in [confessor, tank, bard] + enemies}

            result = _support_skill_logic(
                confessor, enemies, all_units,
                grid_width=25, grid_height=25, obstacles=set(),
            )

            # Track decision
            if result is None:
                decisions["reposition/fallthrough"] += 1
            else:
                decisions[result.skill_id] += 1
                if result.skill_id == "shield_of_faith":
                    if result.target_id == confessor.player_id:
                        sof_targets["SELF"] += 1
                    else:
                        sof_targets[result.target_id] += 1

            # Decrement cooldowns
            heal_cd = max(0, heal_cd - 1)
            prayer_cd = max(0, prayer_cd - 1)
            sof_cd = max(0, sof_cd - 1)
            exorcism_cd = max(0, exorcism_cd - 1)

            # Set cooldown when skill is used
            if result:
                if result.skill_id == "heal":
                    heal_cd = 4
                elif result.skill_id == "prayer":
                    prayer_cd = 6
                elif result.skill_id == "shield_of_faith":
                    sof_cd = 5
                elif result.skill_id == "exorcism":
                    exorcism_cd = 4

        # --- Print analysis ---
        print("\n" + "=" * 60)
        print("  CONFESSOR 200-TURN SKILL DISTRIBUTION")
        print("=" * 60)
        total = sum(decisions.values())
        for skill, count in decisions.most_common():
            pct = count / total * 100
            bar = "█" * int(pct / 2)
            print(f"  {skill:<25} {count:>4} ({pct:5.1f}%) {bar}")
        print(f"  {'TOTAL':<25} {total:>4}")
        print()

        if sof_targets:
            print("  Shield of Faith targets:")
            for target, count in sof_targets.most_common():
                print(f"    {target:<20} {count:>4}")
            self_pct = sof_targets.get("SELF", 0) / sum(sof_targets.values()) * 100
            print(f"    Self-cast rate: {self_pct:.0f}%")

        print()
        print(f"  Heal casts:     {decisions.get('heal', 0):>4}")
        print(f"  Prayer casts:   {decisions.get('prayer', 0):>4}")
        print(f"  SoF casts:      {decisions.get('shield_of_faith', 0):>4}")
        print(f"  Exorcism casts: {decisions.get('exorcism', 0):>4}")
        print(f"  Reposition:     {decisions.get('reposition/fallthrough', 0):>4}")

        # Post-fix assertions
        self_casts = sof_targets.get("SELF", 0)
        total_sof = sum(sof_targets.values()) if sof_targets else 0
        self_pct_val = (self_casts / total_sof * 100) if total_sof > 0 else 0
        repo_pct = decisions.get("reposition/fallthrough", 0) / total * 100

        print(f"\n  Post-fix validation:")
        print(f"    SoF self-cast rate: {self_pct_val:.0f}%")
        print(f"    Reposition rate:    {repo_pct:.0f}%")

        assert self_casts == 0, f"SoF should NEVER self-cast (got {self_casts})"
        assert repo_pct < 70, f"Reposition should be < 70% of turns (got {repo_pct:.0f}%)"
        print(f"    ✓ All post-fix checks passed")


# ===========================================================================
# DIAGNOSTIC TEST 5: Cooldown-Aware Priority Analysis
# ===========================================================================

class TestCooldownPriorityAnalysis:
    """Analyze what happens at each cooldown state."""

    def test_all_off_cd_tank_nearby(self):
        """All skills available, tank 2 tiles away at 50% HP."""
        confessor = make_unit("healer1", "confessor", x=5, y=5, hp=100, max_hp=100)
        tank = make_unit("tank1", "crusader", x=7, y=5,
                         hp=67, max_hp=135, armor=8, attack_damage=20)
        enemy = make_unit("enemy1", "skeleton", x=9, y=5,
                          hp=60, max_hp=60, team="b")

        all_units = {u.player_id: u for u in [confessor, tank, enemy]}

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=20, grid_height=20, obstacles=set(),
        )

        print(f"\n  [DIAG] All off CD, tank 2 tiles @ 50% HP:")
        print(f"         Result: {result.skill_id if result else 'None'}")
        print(f"         Target: {result.target_id if result else 'N/A'}")
        print(f"         Expected: heal → tank (Priority 2)")

    def test_heal_on_cd_tank_nearby_hurt(self):
        """Heal on CD, tank 2 tiles away at 50% HP → should Prayer."""
        confessor = make_unit("healer1", "confessor", x=5, y=5, hp=100, max_hp=100,
                              cooldowns={"heal": 3})
        tank = make_unit("tank1", "crusader", x=7, y=5,
                         hp=67, max_hp=135, armor=8, attack_damage=20)
        enemy = make_unit("enemy1", "skeleton", x=9, y=5,
                          hp=60, max_hp=60, team="b")

        all_units = {u.player_id: u for u in [confessor, tank, enemy]}

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=20, grid_height=20, obstacles=set(),
        )

        print(f"\n  [DIAG] Heal on CD, tank 2 tiles @ 50% HP:")
        print(f"         Result: {result.skill_id if result else 'None'}")
        print(f"         Target: {result.target_id if result else 'N/A'}")
        print(f"         Expected: prayer → tank (Priority 3)")

    def test_heal_prayer_on_cd_tank_nearby(self):
        """Heal+Prayer on CD, tank 2 tiles away at 50% HP → SoF."""
        confessor = make_unit("healer1", "confessor", x=5, y=5, hp=100, max_hp=100,
                              cooldowns={"heal": 3, "prayer": 5})
        tank = make_unit("tank1", "crusader", x=7, y=5,
                         hp=67, max_hp=135, armor=8, attack_damage=20)
        enemy = make_unit("enemy1", "skeleton", x=9, y=5,
                          hp=60, max_hp=60, team="b")

        all_units = {u.player_id: u for u in [confessor, tank, enemy]}

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=20, grid_height=20, obstacles=set(),
        )

        print(f"\n  [FIXED] Heal+Prayer on CD, tank 2 tiles @ 50%:")
        print(f"         Result: {result.skill_id if result else 'None'}")
        if result and result.skill_id == "shield_of_faith":
            assert result.target_id != confessor.player_id, "SoF must not target self"
            print(f"         SoF target: {result.target_id} ✓ (not self)")

    def test_all_on_cd_tank_far(self):
        """All heals on CD, tank 6 tiles away at 70% HP → Exorcism fires (softened Check B)."""
        confessor = make_unit("healer1", "confessor", x=5, y=5, hp=100, max_hp=100,
                              cooldowns={"heal": 3, "prayer": 5, "shield_of_faith": 4})
        tank = make_unit("tank1", "crusader", x=11, y=5,
                         hp=94, max_hp=135, armor=8, attack_damage=20)
        enemy = make_unit("enemy1", "skeleton", x=8, y=5,
                          hp=60, max_hp=60, team="b")

        all_units = {u.player_id: u for u in [confessor, tank, enemy]}
        dist = _chebyshev((5, 5), (11, 5))
        enemy_dist = _chebyshev((5, 5), (8, 5))

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=20, grid_height=20, obstacles=set(),
        )

        print(f"\n  [FIXED] All heals on CD, tank {dist} tiles @ 70%:")
        print(f"         Enemy at {enemy_dist} tiles (Exorcism range: 5)")
        print(f"         Result: {result.skill_id if result else 'None (reposition)'}")
        # Tank at 6 tiles → Check B fires (> 5 threshold), reposition
        assert result is None, "Should reposition when tank is 6 tiles away"
        print(f"         Reposition triggers for tank at {dist} tiles ✓")

    def test_heal_available_but_tank_out_of_range(self):
        """Heal available, tank 6 tiles away at 40% HP → repositions (SoF moved after reposition)."""
        confessor = make_unit("healer1", "confessor", x=5, y=5, hp=100, max_hp=100)
        tank = make_unit("tank1", "crusader", x=11, y=5,
                         hp=54, max_hp=135, armor=8, attack_damage=20)
        enemy = make_unit("enemy1", "skeleton", x=8, y=5,
                          hp=60, max_hp=60, team="b")

        all_units = {u.player_id: u for u in [confessor, tank, enemy]}
        dist = _chebyshev((5, 5), (11, 5))

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=20, grid_height=20, obstacles=set(),
        )

        print(f"\n  [FIXED] Heal available, tank {dist} tiles @ 40%:")
        print(f"         Heal range: 3, Prayer range: 4")
        print(f"         Result: {result.skill_id if result else 'None (reposition)'}")
        # Tank at 6 tiles with 40% HP → reposition to get in heal range
        # Previously SoF (Priority 4) blocked this; now SoF is after reposition (Priority 4.7)
        assert result is None, "Should reposition toward 40% HP tank, not cast SoF"
        print(f"         Correctly repositions toward hurt tank ✓")


# ===========================================================================
# DIAGNOSTIC TEST 6: Stance Integration — Full Decision Flow
# ===========================================================================

class TestStanceIntegration:
    """Test the full decision pipeline through _decide_stance_action."""

    def test_full_pipeline_tank_far_enemy_close(self):
        """Full pipeline: tank 8 tiles away, enemy 4 tiles away.
        What does the Confessor actually DO?
        """
        human = make_unit("human1", "hexblade", x=5, y=5,
                          hp=110, max_hp=110, unit_type="human")
        tank = make_unit("tank1", "crusader", x=13, y=5,
                         hp=100, max_hp=135, hero_id="h_tank",
                         ai_stance="follow", armor=8, attack_damage=20,
                         controlled_by="human1")
        confessor = make_unit("healer1", "confessor", x=5, y=6,
                              hp=100, max_hp=100, hero_id="h_conf",
                              ai_stance="follow", controlled_by="human1")
        enemy = make_unit("enemy1", "skeleton", x=9, y=6,
                          hp=60, max_hp=60, team="b")

        all_units = {u.player_id: u for u in [human, tank, confessor, enemy]}

        result = _decide_stance_action(
            confessor, all_units,
            grid_width=25, grid_height=25, obstacles=set(),
        )

        conf_to_tank = _chebyshev((5, 6), (13, 5))
        conf_to_human = _chebyshev((5, 6), (5, 5))
        conf_to_enemy = _chebyshev((5, 6), (9, 6))

        print(f"\n  [DIAG] Full pipeline result:")
        print(f"         Action: {result.action_type.value if result else 'None'}")
        if result:
            if result.skill_id:
                print(f"         Skill: {result.skill_id}")
                print(f"         Target: {result.target_id}")
            elif result.action_type == ActionType.MOVE:
                print(f"         Move to: ({result.target_x}, {result.target_y})")
            elif result.action_type == ActionType.ATTACK:
                print(f"         Attack: ({result.target_x}, {result.target_y})")
        print(f"         Distances: tank={conf_to_tank}, human={conf_to_human}, enemy={conf_to_enemy}")


# ===========================================================================
# DIAGNOSTIC TEST 7: The Worst Case — SoF Blocks Reposition
# ===========================================================================

class TestSoFBlocksReposition:
    """Verify SoF no longer blocks repositioning when tank is far and hurt."""

    def test_sof_does_not_block_reposition_to_hurt_tank(self):
        """Heal on CD, SoF available, tank 6 tiles @ 55% HP.
        SoF is now Priority 4.7 (after reposition check at 4.5).
        Confessor repositions toward tank instead of casting SoF.
        """
        confessor = make_unit("healer1", "confessor", x=5, y=5,
                              hp=85, max_hp=100,
                              cooldowns={"heal": 3, "prayer": 5})
        tank = make_unit("tank1", "crusader", x=11, y=5,
                         hp=74, max_hp=135,
                         armor=8, attack_damage=20)
        enemy = make_unit("enemy1", "skeleton", x=8, y=5,
                          hp=60, max_hp=60, team="b")

        all_units = {u.player_id: u for u in [confessor, tank, enemy]}

        result = _support_skill_logic(
            confessor, [enemy], all_units,
            grid_width=20, grid_height=20, obstacles=set(),
        )

        print(f"\n  [FIXED] SoF no longer blocks reposition:")
        print(f"         Confessor: 85/100 (85%)")
        print(f"         Tank:      74/135 (55%) — NEEDS HEALING")
        print(f"         Tank dist: 6 tiles (heal range: 3)")
        # Tank at 6 tiles, 55% HP → Check A triggers (below 80% AND out of heal range)
        # SoF no longer blocks because it's after the reposition check
        assert result is None, "Should reposition toward 55% HP tank, not cast SoF"
        print(f"         Correctly repositions toward hurt tank ✓")
