"""
Tests for Target Desync Bug — "Failed - No valid target"

Root Cause Diagnosis:
=====================
The turn resolution order is:
  Phase 1:   Movement
  Phase 1.9: Skills
  Phase 2:   Ranged attacks
  Phase 3:   Melee attacks

ALL targeting (skills, ranged, melee) works by checking the TARGET TILE
(`target_x`, `target_y`) for an occupant. Actions store the target's
POSITION at the time the action was QUEUED (AI decision time / player click).

The problem: Movement resolves FIRST (Phase 1). By the time skills (1.9),
ranged (2), or melee (3) resolve, the target may have MOVED OFF the tile
that was targeted. The attack/skill checks `p.position == target_tile`
and finds nobody there → "no valid target" / "no enemy at target".

Melee attacks (Phase 3) have a partial fix: `pre_move_occupants` tracks
who was on each tile before movement, so if the target moved but is still
adjacent, the attack can track them. But:
  - Skills (Phase 1.9) have NO such tracking at all
  - Ranged attacks (Phase 2) have NO such tracking
  - Even melee tracking only works if the target moved to an adjacent tile

This is especially brutal against kiting enemies (skeleton archers) who
move AWAY every turn. By the time the attack resolves, the skeleton is
on a different tile, and the attack always whiffs.

These tests demonstrate the bug definitively.
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.turn_resolver import resolve_turn
from app.core.combat import load_combat_config
from app.core.skills import load_skills_config, clear_skills_cache, get_skill


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

def make_unit(
    pid="p1", username="Hero", x=5, y=5, hp=100, max_hp=100,
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
# 1. Core Bug Reproduction — Movement Causes Target Desync
# ============================================================

class TestRangedTargetDesync:
    """Ranged attacks fail when the target moves away from the targeted tile."""

    def test_ranged_attack_fails_when_target_moves(self):
        """
        BUG REPRODUCTION: Attacker targets skeleton at (8,5). Skeleton
        moves from (8,5) to (9,5) in Phase 1 (movement). Ranged attack
        resolves in Phase 2 — checks tile (8,5) — finds nobody → FAIL.

        This is the skeleton archer kiting scenario.
        """
        hero = make_unit(pid="hero", username="Hero", x=3, y=5, team="a")
        skeleton = make_unit(
            pid="skel", username="Skeleton Archer", x=8, y=5,
            team="b", class_id="ranger",
        )
        players = {"hero": hero, "skel": skeleton}
        obstacles = set()

        # Hero targets skeleton's CURRENT tile (8,5)
        # Skeleton moves away from hero (kiting) to (9,5)
        actions = [
            PlayerAction(
                player_id="hero",
                action_type=ActionType.RANGED_ATTACK,
                target_x=8, target_y=5,
            ),
            PlayerAction(
                player_id="skel",
                action_type=ActionType.MOVE,
                target_x=9, target_y=5,
            ),
        ]

        result = resolve_turn(
            "test_match", 1, players, actions,
            grid_width=20, grid_height=20, obstacles=obstacles,
        )

        # Find the ranged attack result
        ranged_results = [
            r for r in result.actions
            if r.player_id == "hero" and r.action_type == ActionType.RANGED_ATTACK
        ]
        assert len(ranged_results) == 1
        ranged_result = ranged_results[0]

        # THIS DEMONSTRATES THE BUG:
        # The attack SHOULD hit (target was in range when action queued),
        # but it FAILS because the target moved before resolution.
        assert ranged_result.success is False, (
            "Expected ranged attack to FAIL due to target desync bug. "
            "If this passes (success=True), the bug has been fixed!"
        )
        assert "no enemy at target" in ranged_result.message

    def test_ranged_attack_succeeds_when_target_stationary(self):
        """Control test: ranged attack hits when target doesn't move."""
        hero = make_unit(pid="hero", username="Hero", x=3, y=5, team="a")
        skeleton = make_unit(
            pid="skel", username="Skeleton", x=8, y=5,
            team="b", class_id="ranger",
        )
        players = {"hero": hero, "skel": skeleton}
        obstacles = set()

        actions = [
            PlayerAction(
                player_id="hero",
                action_type=ActionType.RANGED_ATTACK,
                target_x=8, target_y=5,
            ),
        ]

        result = resolve_turn(
            "test_match", 1, players, actions,
            grid_width=20, grid_height=20, obstacles=obstacles,
        )

        ranged_results = [
            r for r in result.actions
            if r.player_id == "hero" and r.action_type == ActionType.RANGED_ATTACK
        ]
        assert len(ranged_results) == 1
        assert ranged_results[0].success is True


class TestMeleeTargetDesync:
    """Melee attacks have pre_move_occupants tracking, but still fail in some cases."""

    def test_melee_attack_fails_when_target_moves_out_of_range(self):
        """
        BUG REPRODUCTION: Hero is at (5,5), targets enemy at (6,5) (adjacent).
        Enemy moves to (7,5) in Phase 1. Melee resolves in Phase 3.
        pre_move_occupants finds the enemy WAS at (6,5), checks if still
        adjacent — enemy is now at (7,5), distance=2 → NOT adjacent → FAIL.
        """
        hero = make_unit(pid="hero", username="Hero", x=5, y=5, team="a")
        enemy = make_unit(
            pid="enemy", username="Enemy", x=6, y=5,
            team="b",
        )
        players = {"hero": hero, "enemy": enemy}
        obstacles = set()

        actions = [
            PlayerAction(
                player_id="hero",
                action_type=ActionType.ATTACK,
                target_x=6, target_y=5,
            ),
            PlayerAction(
                player_id="enemy",
                action_type=ActionType.MOVE,
                target_x=7, target_y=5,
            ),
        ]

        result = resolve_turn(
            "test_match", 1, players, actions,
            grid_width=20, grid_height=20, obstacles=obstacles,
        )

        melee_results = [
            r for r in result.actions
            if r.player_id == "hero" and r.action_type == ActionType.ATTACK
        ]
        assert len(melee_results) == 1
        melee_result = melee_results[0]

        # Demonstrates the bug: target moved 2 tiles away, melee fails
        assert melee_result.success is False

    def test_melee_tracks_target_that_moved_but_still_adjacent(self):
        """
        Control: Melee CAN track targets that moved but remain adjacent.
        This is the partial fix already in place via pre_move_occupants.
        """
        hero = make_unit(pid="hero", username="Hero", x=5, y=5, team="a")
        enemy = make_unit(
            pid="enemy", username="Enemy", x=6, y=5,
            team="b",
        )
        players = {"hero": hero, "enemy": enemy}
        obstacles = set()

        # Enemy moves from (6,5) to (6,6) — still adjacent to hero at (5,5)
        actions = [
            PlayerAction(
                player_id="hero",
                action_type=ActionType.ATTACK,
                target_x=6, target_y=5,
            ),
            PlayerAction(
                player_id="enemy",
                action_type=ActionType.MOVE,
                target_x=6, target_y=6,
            ),
        ]

        result = resolve_turn(
            "test_match", 1, players, actions,
            grid_width=20, grid_height=20, obstacles=obstacles,
        )

        melee_results = [
            r for r in result.actions
            if r.player_id == "hero" and r.action_type == ActionType.ATTACK
        ]
        assert len(melee_results) == 1
        # pre_move_occupants tracking should make this succeed
        assert melee_results[0].success is True


class TestSkillTargetDesync:
    """Skills have NO pre_move_occupants tracking — always fail on moved targets."""

    def test_heal_fails_when_ally_moves_away(self):
        """
        BUG REPRODUCTION: Confessor targets ally at (6,5) for heal.
        Ally moves to (7,5) in Phase 1. Heal resolves in Phase 1.9.
        Checks tile (6,5) — nobody there → "no valid target".
        """
        healer = make_unit(
            pid="healer", username="Healer", x=5, y=5,
            team="a", class_id="confessor",
        )
        ally = make_unit(
            pid="ally", username="Ally", x=6, y=5, hp=50,
            team="a", class_id="crusader",
        )
        players = {"healer": healer, "ally": ally}
        obstacles = set()

        actions = [
            PlayerAction(
                player_id="healer",
                action_type=ActionType.SKILL,
                skill_id="heal",
                target_x=6, target_y=5,
            ),
            PlayerAction(
                player_id="ally",
                action_type=ActionType.MOVE,
                target_x=7, target_y=5,
            ),
        ]

        result = resolve_turn(
            "test_match", 1, players, actions,
            grid_width=20, grid_height=20, obstacles=obstacles,
        )

        heal_results = [
            r for r in result.actions
            if r.player_id == "healer" and r.action_type == ActionType.SKILL
        ]
        assert len(heal_results) == 1
        heal_result = heal_results[0]

        # Demonstrates: heal FAILS because ally moved away from targeted tile
        assert heal_result.success is False
        assert "no valid target" in heal_result.message

    def test_ranged_skill_fails_when_enemy_moves(self):
        """
        BUG REPRODUCTION: Ranger uses Power Shot targeting enemy at (8,5).
        Enemy moves to (9,5) in Phase 1. Skill resolves in Phase 1.9.
        Nobody at (8,5) → "no enemy at target".
        """
        ranger = make_unit(
            pid="ranger", username="Ranger", x=3, y=5,
            team="a", class_id="ranger",
        )
        enemy = make_unit(
            pid="enemy", username="Enemy", x=8, y=5,
            team="b",
        )
        players = {"ranger": ranger, "enemy": enemy}
        obstacles = set()

        actions = [
            PlayerAction(
                player_id="ranger",
                action_type=ActionType.SKILL,
                skill_id="power_shot",
                target_x=8, target_y=5,
            ),
            PlayerAction(
                player_id="enemy",
                action_type=ActionType.MOVE,
                target_x=9, target_y=5,
            ),
        ]

        result = resolve_turn(
            "test_match", 1, players, actions,
            grid_width=20, grid_height=20, obstacles=obstacles,
        )

        skill_results = [
            r for r in result.actions
            if r.player_id == "ranger" and r.action_type == ActionType.SKILL
        ]
        assert len(skill_results) == 1
        skill_result = skill_results[0]

        # Demonstrates: skill FAILS because enemy moved
        assert skill_result.success is False
        assert "no enemy at target" in skill_result.message

    def test_multi_hit_skill_fails_when_enemy_moves(self):
        """
        BUG REPRODUCTION: Crusader uses Double Strike on enemy at (6,5).
        Enemy moves to (7,5). Skill resolves → nobody at (6,5) → FAIL.
        """
        hexblade = make_unit(
            pid="hexblade", username="Hexblade", x=5, y=5,
            team="a", class_id="hexblade",
        )
        enemy = make_unit(
            pid="enemy", username="Enemy", x=6, y=5,
            team="b",
        )
        players = {"hexblade": hexblade, "enemy": enemy}
        obstacles = set()

        actions = [
            PlayerAction(
                player_id="hexblade",
                action_type=ActionType.SKILL,
                skill_id="double_strike",
                target_x=6, target_y=5,
            ),
            PlayerAction(
                player_id="enemy",
                action_type=ActionType.MOVE,
                target_x=7, target_y=5,
            ),
        ]

        result = resolve_turn(
            "test_match", 1, players, actions,
            grid_width=20, grid_height=20, obstacles=obstacles,
        )

        skill_results = [
            r for r in result.actions
            if r.player_id == "hexblade" and r.action_type == ActionType.SKILL
        ]
        assert len(skill_results) == 1
        skill_result = skill_results[0]

        # Demonstrates: double strike FAILS because enemy moved
        assert skill_result.success is False
        assert "no enemy at target" in skill_result.message


class TestKitingScenario:
    """
    Full kiting scenario: skeleton archer alternates between moving and
    shooting while the hero's attacks consistently miss.
    """

    def test_skeleton_kites_indefinitely(self):
        """
        Simulates multiple turns of a skeleton archer kiting a melee hero.
        The hero can never land a hit because the skeleton always moves first.
        """
        hero = make_unit(pid="hero", username="Hero", x=5, y=5, team="a", ranged_range=0)
        skeleton = make_unit(
            pid="skel", username="Skeleton Archer", x=7, y=5,
            team="b", class_id="ranger", ranged_range=5,
        )
        players = {"hero": hero, "skel": skeleton}
        obstacles = set()

        hero_hits = 0
        hero_misses = 0

        # Simulate 6 turns of kiting
        for turn in range(1, 7):
            # Hero always tries to move toward skeleton, then attack
            skel_x = skeleton.position.x
            skel_y = skeleton.position.y

            # Hero moves toward skeleton
            hero_dx = 1 if skel_x > hero.position.x else (-1 if skel_x < hero.position.x else 0)
            hero_target_x = hero.position.x + hero_dx

            # Skeleton kites away (moves +1 x)
            skel_new_x = min(skel_x + 1, 18)

            turn_actions = [
                # Hero moves toward
                PlayerAction(
                    player_id="hero",
                    action_type=ActionType.MOVE,
                    target_x=hero_target_x, target_y=5,
                ),
                # Skeleton kites away
                PlayerAction(
                    player_id="skel",
                    action_type=ActionType.MOVE,
                    target_x=skel_new_x, target_y=5,
                ),
            ]

            result = resolve_turn(
                "test_match", turn, players, turn_actions,
                grid_width=20, grid_height=20, obstacles=obstacles,
            )

            # Next turn: hero tries to attack skeleton's PRE-MOVE position
            if abs(hero.position.x - skel_x) <= 1:
                # Hero was close enough to try melee
                attack_actions = [
                    PlayerAction(
                        player_id="hero",
                        action_type=ActionType.ATTACK,
                        target_x=skel_x, target_y=5,  # targets OLD position
                    ),
                    PlayerAction(
                        player_id="skel",
                        action_type=ActionType.MOVE,
                        target_x=min(skeleton.position.x + 1, 18), target_y=5,
                    ),
                ]

                result2 = resolve_turn(
                    "test_match", turn * 10, players, attack_actions,
                    grid_width=20, grid_height=20, obstacles=obstacles,
                )

                for r in result2.actions:
                    if r.player_id == "hero" and r.action_type == ActionType.ATTACK:
                        if r.success:
                            hero_hits += 1
                        else:
                            hero_misses += 1

        # The hero should have missed most/all attacks due to kiting
        # This demonstrates the frustrating gameplay loop
        print(f"\n  Kiting scenario: Hero hits={hero_hits}, misses={hero_misses}")
        assert hero_misses >= hero_hits, (
            f"Expected more misses than hits due to kiting. "
            f"Hits={hero_hits}, Misses={hero_misses}"
        )


class TestBothUnitsMoveThenAttack:
    """
    Common scenario: Both units move AND attack in the same turn.
    The attacker targets where the enemy WAS, not where they'll BE.
    """

    def test_mutual_move_and_ranged_desync(self):
        """
        Both units move and try to ranged attack each other.
        Both target the OTHER's pre-move position.
        Both attacks should fail because both targets moved.
        """
        unit_a = make_unit(pid="a", username="UnitA", x=3, y=5, team="a", ranged_range=5)
        unit_b = make_unit(pid="b", username="UnitB", x=8, y=5, team="b", ranged_range=5)
        players = {"a": unit_a, "b": unit_b}
        obstacles = set()

        actions = [
            # Both move
            PlayerAction(player_id="a", action_type=ActionType.MOVE, target_x=4, target_y=5),
            PlayerAction(player_id="b", action_type=ActionType.MOVE, target_x=9, target_y=5),
            # Both attack the OTHER's old position
            PlayerAction(player_id="a", action_type=ActionType.RANGED_ATTACK, target_x=8, target_y=5),
            PlayerAction(player_id="b", action_type=ActionType.RANGED_ATTACK, target_x=3, target_y=5),
        ]

        result = resolve_turn(
            "test_match", 1, players, actions,
            grid_width=20, grid_height=20, obstacles=obstacles,
        )

        ranged_results = [
            r for r in result.actions
            if r.action_type == ActionType.RANGED_ATTACK
        ]

        # Both attacks should fail — both targets moved
        failed = [r for r in ranged_results if not r.success]
        assert len(failed) == 2, (
            f"Expected both ranged attacks to fail. Results: "
            f"{[(r.player_id, r.success, r.message) for r in ranged_results]}"
        )


# ============================================================
# 6. Entity-Based Targeting Fix Verification
# ============================================================

class TestEntityTargetingFix:
    """Verify that target_id (entity-based targeting) resolves the desync bug."""

    def test_ranged_attack_hits_when_target_moves_with_entity_id(self):
        """
        FIX VERIFICATION: Attacker targets skeleton at (7,5). Skeleton moves
        to (8,5) in Phase 1 (still in range 5 from hero at (3,5), distance=5).
        Without entity targeting → attack checks tile (7,5) → nobody → FAIL.
        With target_id='skel' → looks up skeleton's CURRENT position (8,5),
        validates range (5 ≤ 5) + LOS → HIT.
        """
        hero = make_unit(pid="hero", username="Hero", x=3, y=5, team="a", ranged_range=5)
        skeleton = make_unit(
            pid="skel", username="Skeleton Archer", x=7, y=5,
            team="b", class_id="ranger",
        )
        players = {"hero": hero, "skel": skeleton}
        obstacles = set()

        actions = [
            PlayerAction(
                player_id="hero",
                action_type=ActionType.RANGED_ATTACK,
                target_x=7, target_y=5,
                target_id="skel",  # Entity-based targeting!
            ),
            PlayerAction(
                player_id="skel",
                action_type=ActionType.MOVE,
                target_x=8, target_y=5,
            ),
        ]

        result = resolve_turn(
            "test_match", 1, players, actions,
            grid_width=20, grid_height=20, obstacles=obstacles,
        )

        ranged_results = [
            r for r in result.actions
            if r.player_id == "hero" and r.action_type == ActionType.RANGED_ATTACK
        ]
        assert len(ranged_results) == 1
        assert ranged_results[0].success is True, (
            f"Entity-based ranged attack should HIT moving target. "
            f"Got: {ranged_results[0].message}"
        )

    def test_melee_attack_hits_when_target_moves_nearby_with_entity_id(self):
        """
        FIX VERIFICATION: Hero at (5,5), enemy at (6,5). Enemy moves to (6,6)
        (still adjacent). With target_id, melee should find enemy at (6,6)
        and succeed since it's still adjacent to hero.
        """
        hero = make_unit(pid="hero", username="Hero", x=5, y=5, team="a")
        enemy = make_unit(
            pid="enemy", username="Enemy", x=6, y=5, team="b",
        )
        players = {"hero": hero, "enemy": enemy}
        obstacles = set()

        actions = [
            PlayerAction(
                player_id="hero",
                action_type=ActionType.ATTACK,
                target_x=6, target_y=5,
                target_id="enemy",
            ),
            PlayerAction(
                player_id="enemy",
                action_type=ActionType.MOVE,
                target_x=6, target_y=6,
            ),
        ]

        result = resolve_turn(
            "test_match", 1, players, actions,
            grid_width=20, grid_height=20, obstacles=obstacles,
        )

        melee_results = [
            r for r in result.actions
            if r.player_id == "hero" and r.action_type == ActionType.ATTACK
        ]
        assert len(melee_results) == 1
        assert melee_results[0].success is True

    def test_heal_hits_when_ally_moves_with_entity_id(self):
        """
        FIX VERIFICATION: Healer targets ally at (6,5). Ally moves to (7,5).
        With target_id, heal finds ally at (7,5), validates range → SUCCESS.
        """
        healer = make_unit(
            pid="healer", username="Healer", x=5, y=5,
            team="a", class_id="confessor",
        )
        ally = make_unit(
            pid="ally", username="Ally", x=6, y=5, hp=50,
            team="a", class_id="crusader",
        )
        players = {"healer": healer, "ally": ally}
        obstacles = set()

        actions = [
            PlayerAction(
                player_id="healer",
                action_type=ActionType.SKILL,
                skill_id="heal",
                target_x=6, target_y=5,
                target_id="ally",
            ),
            PlayerAction(
                player_id="ally",
                action_type=ActionType.MOVE,
                target_x=7, target_y=5,
            ),
        ]

        result = resolve_turn(
            "test_match", 1, players, actions,
            grid_width=20, grid_height=20, obstacles=obstacles,
        )

        heal_results = [
            r for r in result.actions
            if r.player_id == "healer" and r.action_type == ActionType.SKILL
        ]
        assert len(heal_results) == 1
        assert heal_results[0].success is True, (
            f"Entity-based heal should hit moving ally. "
            f"Got: {heal_results[0].message}"
        )

    def test_ranged_skill_hits_when_enemy_moves_with_entity_id(self):
        """
        FIX VERIFICATION: Ranger Power Shot targets enemy at (7,5).
        Enemy moves to (8,5) (still in range 5 from (3,5), distance=5).
        Without entity targeting → checks tile (7,5) → nobody → FAIL.
        With target_id → finds enemy at (8,5) → validates range → SUCCESS.
        """
        ranger = make_unit(
            pid="ranger", username="Ranger", x=3, y=5,
            team="a", class_id="ranger", ranged_range=5,
        )
        enemy = make_unit(
            pid="enemy", username="Enemy", x=7, y=5, team="b",
        )
        players = {"ranger": ranger, "enemy": enemy}
        obstacles = set()

        actions = [
            PlayerAction(
                player_id="ranger",
                action_type=ActionType.SKILL,
                skill_id="power_shot",
                target_x=7, target_y=5,
                target_id="enemy",
            ),
            PlayerAction(
                player_id="enemy",
                action_type=ActionType.MOVE,
                target_x=8, target_y=5,
            ),
        ]

        result = resolve_turn(
            "test_match", 1, players, actions,
            grid_width=20, grid_height=20, obstacles=obstacles,
        )

        skill_results = [
            r for r in result.actions
            if r.player_id == "ranger" and r.action_type == ActionType.SKILL
        ]
        assert len(skill_results) == 1
        assert skill_results[0].success is True, (
            f"Entity-based Power Shot should hit moving target. "
            f"Got: {skill_results[0].message}"
        )

    def test_multi_hit_hits_when_enemy_moves_with_entity_id(self):
        """
        FIX VERIFICATION: Double Strike targets enemy at (6,5).
        Enemy moves to (6,6) (still adjacent). With target_id → SUCCESS.
        """
        hexblade = make_unit(
            pid="hexblade", username="Hexblade", x=5, y=5,
            team="a", class_id="hexblade",
        )
        enemy = make_unit(
            pid="enemy", username="Enemy", x=6, y=5, team="b",
        )
        players = {"hexblade": hexblade, "enemy": enemy}
        obstacles = set()

        actions = [
            PlayerAction(
                player_id="hexblade",
                action_type=ActionType.SKILL,
                skill_id="double_strike",
                target_x=6, target_y=5,
                target_id="enemy",
            ),
            PlayerAction(
                player_id="enemy",
                action_type=ActionType.MOVE,
                target_x=6, target_y=6,
            ),
        ]

        result = resolve_turn(
            "test_match", 1, players, actions,
            grid_width=20, grid_height=20, obstacles=obstacles,
        )

        skill_results = [
            r for r in result.actions
            if r.player_id == "hexblade" and r.action_type == ActionType.SKILL
        ]
        assert len(skill_results) == 1
        assert skill_results[0].success is True, (
            f"Entity-based Double Strike should hit moving target. "
            f"Got: {skill_results[0].message}"
        )

    def test_entity_targeting_fails_when_out_of_range(self):
        """
        Entity targeting should still fail if the target moved OUT of range.
        Ranged hero at (3,5) with range 5. Enemy at (8,5) moves to (9,5).
        Distance becomes 6 (> range 5) → FAIL even with entity targeting.
        """
        hero = make_unit(pid="hero", username="Hero", x=3, y=5, team="a", ranged_range=5)
        enemy = make_unit(
            pid="enemy", username="Enemy", x=8, y=5, team="b",
        )
        players = {"hero": hero, "enemy": enemy}
        obstacles = set()

        actions = [
            PlayerAction(
                player_id="hero",
                action_type=ActionType.RANGED_ATTACK,
                target_x=8, target_y=5,
                target_id="enemy",
            ),
            PlayerAction(
                player_id="enemy",
                action_type=ActionType.MOVE,
                target_x=9, target_y=5,
            ),
        ]

        result = resolve_turn(
            "test_match", 1, players, actions,
            grid_width=20, grid_height=20, obstacles=obstacles,
        )

        ranged_results = [
            r for r in result.actions
            if r.player_id == "hero" and r.action_type == ActionType.RANGED_ATTACK
        ]
        assert len(ranged_results) == 1
        # Should fail — target moved out of range even with entity targeting
        assert ranged_results[0].success is False
