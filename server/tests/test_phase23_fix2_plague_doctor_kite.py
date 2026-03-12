"""
Tests for Phase 23 Fix 2: Plague Doctor AI kiting & positioning improvements.

Covers:
- Fix 2a: Controller kite threshold widened to dist <= 3 (from dist <= 2)
- Fix 2b: Controller holds position when skills/ranged on CD and enemies within 4 tiles
- Fix 3:  Miasma used on single target when enemy is within 4 tiles (defensive slow)
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import ActionType, PlayerAction
from app.core.ai_stances import (
    _decide_follow_action,
    _decide_aggressive_stance_action,
)
from app.core.ai_skills import (
    _controller_skill_logic,
)
from app.core.combat import load_combat_config
from app.core.skills import load_skills_config, clear_skills_cache


# ---------- Setup ----------

def setup_module():
    """Ensure configs are loaded before any test runs."""
    load_combat_config()
    load_skills_config()


@pytest.fixture(autouse=True)
def _reset_skills_cache():
    """Clear cached config before each test to ensure isolation."""
    clear_skills_cache()
    load_skills_config()
    yield
    clear_skills_cache()


# ---------- Helpers ----------

def _make_plague_doctor(
    player_id: str = "pd1",
    x: int = 5,
    y: int = 5,
    hp: int = 85,
    max_hp: int = 85,
    team: str = "team_1",
    cooldowns: dict | None = None,
    active_buffs: list | None = None,
    stance: str = "follow",
) -> PlayerState:
    """Create a Plague Doctor AI hero unit."""
    return PlayerState(
        player_id=player_id,
        username="PlagueDoc",
        position=Position(x=x, y=y),
        class_id="plague_doctor",
        hp=hp,
        max_hp=max_hp,
        is_alive=True,
        team=team,
        unit_type="ai",
        hero_id="pd_hero_001",
        ai_stance=stance,
        ranged_range=5,
        vision_range=7,
        attack_damage=12,
        armor=2,
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
        inventory=[],
    )


def _make_owner(
    player_id: str = "owner",
    x: int = 3,
    y: int = 5,
    team: str = "team_1",
) -> PlayerState:
    """Create the human owner behind the party."""
    return PlayerState(
        player_id=player_id,
        username="Player",
        position=Position(x=x, y=y),
        class_id="crusader",
        hp=150,
        max_hp=150,
        is_alive=True,
        team=team,
        unit_type="human",
        hero_id=None,
        ranged_range=0,
        vision_range=7,
        attack_damage=20,
        armor=8,
        cooldowns={},
        active_buffs=[],
        inventory=[],
    )


def _make_ally(
    player_id: str = "ally1",
    class_id: str = "crusader",
    x: int = 8,
    y: int = 5,
    hp: int = 150,
    max_hp: int = 150,
    team: str = "team_1",
) -> PlayerState:
    """Create a frontline ally (close to enemies)."""
    return PlayerState(
        player_id=player_id,
        username=f"Ally_{class_id}",
        position=Position(x=x, y=y),
        class_id=class_id,
        hp=hp,
        max_hp=max_hp,
        is_alive=True,
        team=team,
        unit_type="ai",
        hero_id=f"hero_{player_id}",
        ai_stance="follow",
        ranged_range=0,
        vision_range=7,
        attack_damage=20,
        armor=8,
        cooldowns={},
        active_buffs=[],
        inventory=[],
    )


def _make_enemy(
    player_id: str = "enemy1",
    x: int = 10,
    y: int = 5,
    hp: int = 80,
    max_hp: int = 80,
    team: str = "team_2",
    active_buffs: list | None = None,
) -> PlayerState:
    """Create an enemy unit."""
    return PlayerState(
        player_id=player_id,
        username="Enemy",
        position=Position(x=x, y=y),
        class_id=None,
        hp=hp,
        max_hp=max_hp,
        is_alive=True,
        team=team,
        unit_type="ai",
        hero_id=None,
        ranged_range=0,
        vision_range=5,
        attack_damage=10,
        armor=0,
        cooldowns={},
        active_buffs=active_buffs or [],
        inventory=[],
    )


def _build_units(*units: PlayerState) -> dict[str, PlayerState]:
    return {u.player_id: u for u in units}


GRID_W = 20
GRID_H = 20
NO_OBSTACLES: set[tuple[int, int]] = set()


# ===========================================================================
# Fix 2a: Controller kites at dist <= 3 (widened from 2)
# ===========================================================================

class TestControllerWidenedKite:
    """Plague Doctor kites when enemies are within 3 tiles (not just 2)."""

    def test_pd_kites_at_dist_3_follow_stance(self):
        """In follow stance, PD at dist 3 from enemy should kite (MOVE away)."""
        # PD at (5,5), enemy at (8,5) → Chebyshev dist = 3
        pd = _make_plague_doctor(x=5, y=5, cooldowns={
            "enfeeble": 5, "miasma": 5, "plague_flask": 5, "inoculate": 5,
            "ranged_attack": 2,
        })
        owner = _make_owner(x=3, y=5)
        enemy = _make_enemy(player_id="enemy1", x=8, y=5)
        all_units = _build_units(pd, owner, enemy)

        action = _decide_follow_action(
            pd, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        # At dist 3 the PD should kite — move AWAY from enemy (lower x)
        if action.action_type == ActionType.MOVE:
            new_dist = max(abs(action.target_x - 8), abs(action.target_y - 5))
            assert new_dist > 3, (
                f"PD moved to ({action.target_x}, {action.target_y}) which is "
                f"dist {new_dist} from enemy — should have moved further away"
            )

    def test_pd_kites_at_dist_3_aggressive_stance(self):
        """In aggressive stance, PD at dist 3 from enemy should kite (MOVE away)."""
        pd = _make_plague_doctor(x=5, y=5, stance="aggressive", cooldowns={
            "enfeeble": 5, "miasma": 5, "plague_flask": 5, "inoculate": 5,
            "ranged_attack": 2,
        })
        owner = _make_owner(x=3, y=5)
        enemy = _make_enemy(player_id="enemy1", x=8, y=5)
        all_units = _build_units(pd, owner, enemy)

        action = _decide_aggressive_stance_action(
            pd, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        if action.action_type == ActionType.MOVE:
            new_dist = max(abs(action.target_x - 8), abs(action.target_y - 5))
            assert new_dist > 3, (
                f"PD moved to ({action.target_x}, {action.target_y}) which is "
                f"dist {new_dist} from enemy — should have moved further away"
            )


# ===========================================================================
# Fix 2b: Controller holds position when idle and enemies medium-range
# ===========================================================================

class TestControllerHoldPosition:
    """When skills + ranged on CD and enemies within 4 tiles, PD WAITs."""

    def test_pd_waits_instead_of_walking_toward_frontline_follow(self):
        """In follow stance, PD with all CDs and enemy at dist 4 should WAIT."""
        # PD at (5,5), enemy at (9,5) → dist 4.
        # Ally crusader at (8,5) — close to enemy (frontline).
        # PD should NOT walk toward ally since it would bring it closer to enemy.
        pd = _make_plague_doctor(x=5, y=5, cooldowns={
            "enfeeble": 5, "miasma": 5, "plague_flask": 5, "inoculate": 5,
            "ranged_attack": 2,
        })
        owner = _make_owner(x=3, y=5)
        ally = _make_ally(x=8, y=5)  # frontline ally near enemy
        enemy = _make_enemy(player_id="enemy1", x=9, y=5)
        all_units = _build_units(pd, owner, ally, enemy)

        action = _decide_follow_action(
            pd, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.WAIT, (
            f"PD should WAIT but got {action.action_type}"
        )

    def test_pd_waits_instead_of_walking_toward_enemy_aggressive(self):
        """In aggressive stance, PD with all CDs and enemy at dist 4 should WAIT."""
        pd = _make_plague_doctor(x=5, y=5, stance="aggressive", cooldowns={
            "enfeeble": 5, "miasma": 5, "plague_flask": 5, "inoculate": 5,
            "ranged_attack": 2,
        })
        owner = _make_owner(x=3, y=5)
        enemy = _make_enemy(player_id="enemy1", x=9, y=5)
        all_units = _build_units(pd, owner, enemy)

        action = _decide_aggressive_stance_action(
            pd, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.WAIT, (
            f"PD should WAIT but got {action.action_type}"
        )

    def test_pd_advances_when_enemies_far_away(self):
        """When enemies are dist > 4 (but visible), PD should still move toward allies."""
        # PD at (5,5), enemy at (10,5) → dist 5. Visible (vision 7) but safe (> 4).
        pd = _make_plague_doctor(x=5, y=5, cooldowns={
            "enfeeble": 5, "miasma": 5, "plague_flask": 5, "inoculate": 5,
            "ranged_attack": 2,
        })
        owner = _make_owner(x=3, y=5)
        ally = _make_ally(x=8, y=5)
        enemy = _make_enemy(player_id="enemy1", x=10, y=5)
        all_units = _build_units(pd, owner, ally, enemy)

        action = _decide_follow_action(
            pd, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.MOVE, (
            f"PD should advance toward allies when enemies are far, got {action.action_type}"
        )

    def test_pd_ranged_attacks_when_ready(self):
        """When ranged is off CD, PD should ranged-attack instead of WAITing."""
        # PD at (5,5), enemy at (9,5) → dist 4, in range 5.
        pd = _make_plague_doctor(x=5, y=5, cooldowns={
            "enfeeble": 5, "miasma": 5, "plague_flask": 5, "inoculate": 5,
            # ranged_attack NOT on cooldown
        })
        owner = _make_owner(x=3, y=5)
        enemy = _make_enemy(player_id="enemy1", x=9, y=5)
        all_units = _build_units(pd, owner, enemy)

        action = _decide_follow_action(
            pd, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert action is not None
        assert action.action_type == ActionType.RANGED_ATTACK, (
            f"PD should fire ranged when off CD, got {action.action_type}"
        )


# ===========================================================================
# Fix 3: Miasma on single target when enemy is close (defensive slow)
# ===========================================================================

class TestMiasmaSingleTargetSlow:
    """Miasma fires on 1 enemy when that enemy is within 4 tiles (defensive slow)."""

    def test_miasma_single_target_enemy_close(self):
        """Miasma fires on 1 enemy at dist 4 when enfeeble and plague_flask on CD."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 5, "plague_flask": 3})
        enemy = _make_enemy(player_id="enemy1", x=9, y=5)  # dist 4 — in miasma range 5
        all_units = _build_units(pd, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "miasma", (
            f"Expected miasma as defensive slow on close single target, got {result.skill_id}"
        )

    def test_miasma_fires_single_target_enemy_far(self):
        """Miasma fires on 1 enemy at dist 5 — _MIASMA_MIN_ENEMIES=1 allows single targets."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 5, "plague_flask": 3})
        enemy = _make_enemy(player_id="enemy1", x=10, y=5)  # dist 5
        all_units = _build_units(pd, enemy)

        result = _controller_skill_logic(
            pd, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # With _MIASMA_MIN_ENEMIES=1, miasma fires on single targets in range
        assert result is not None
        assert result.skill_id == "miasma", (
            f"Expected miasma on single target in range, got {result.skill_id}"
        )

    def test_miasma_still_fires_on_two_targets_far(self):
        """Miasma still fires with 2+ enemies clustered at range (normal behavior)."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"enfeeble": 5, "plague_flask": 3})
        enemy1 = _make_enemy(player_id="enemy1", x=10, y=5)  # dist 5
        enemy2 = _make_enemy(player_id="enemy2", x=10, y=6)  # dist 5
        all_units = _build_units(pd, enemy1, enemy2)

        result = _controller_skill_logic(
            pd, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "miasma"

    def test_miasma_single_target_prefers_enfeeble_when_two_enemies(self):
        """Enfeeble still takes priority over miasma when plague_flask on CD and 2+ enemies available."""
        pd = _make_plague_doctor(x=5, y=5, cooldowns={"plague_flask": 3})
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)  # dist 3
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)  # dist 4
        all_units = _build_units(pd, enemy1, enemy2)

        result = _controller_skill_logic(
            pd, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "enfeeble"
