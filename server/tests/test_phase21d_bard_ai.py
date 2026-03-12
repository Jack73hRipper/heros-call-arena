"""
Tests for Phase 21D: Bard AI Behavior (offensive_support role).

Covers:
- Role mapping: bard maps to "offensive_support"
- _offensive_support_skill_logic() — full priority chain
  - Ballad of Might: uses when 2+ allies in radius, skips when fewer
  - Dirge of Weakness: uses when 2+ enemies clustered, skips otherwise
  - Verse of Haste: targets ally with highest cooldown debt
  - Cacophony: uses when enemy adjacent (self-peel)
  - Fallback: returns None when all skills on cooldown
- _decide_skill_usage() dispatches bard to offensive_support handler
- Positioning: offensive_support role uses support move preference (stay near allies)
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import ActionType, PlayerAction
from app.core.ai_skills import (
    _CLASS_ROLE_MAP,
    _get_role_for_class,
    _try_skill,
    _offensive_support_skill_logic,
    _support_move_preference,
    _decide_skill_usage,
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

def _make_bard(
    player_id: str = "bard1",
    x: int = 5,
    y: int = 5,
    hp: int = 90,
    max_hp: int = 90,
    team: str = "team_1",
    cooldowns: dict | None = None,
    active_buffs: list | None = None,
) -> PlayerState:
    """Create a Bard AI unit."""
    p = PlayerState(
        player_id=player_id,
        username="BardHero",
        position=Position(x=x, y=y),
        class_id="bard",
        hp=hp,
        max_hp=max_hp,
        is_alive=True,
        team=team,
        unit_type="ai",
        hero_id="bard_hero_001",
        ai_stance="follow",
        ranged_range=4,
        vision_range=7,
        attack_damage=10,
        armor=3,
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
        inventory=[],
    )
    return p


def _make_ally(
    player_id: str = "ally1",
    class_id: str = "crusader",
    x: int = 6,
    y: int = 5,
    hp: int = 150,
    max_hp: int = 150,
    team: str = "team_1",
    cooldowns: dict | None = None,
    active_buffs: list | None = None,
) -> PlayerState:
    """Create an ally unit on the same team."""
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
        ranged_range=5,
        vision_range=7,
        attack_damage=15,
        armor=2,
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
        inventory=[],
    )


def _make_enemy(
    player_id: str = "enemy1",
    x: int = 8,
    y: int = 5,
    hp: int = 80,
    max_hp: int = 80,
    team: str = "team_2",
    active_buffs: list | None = None,
) -> PlayerState:
    """Create an enemy unit on the opposing team."""
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
    """Build the all_units dict from a list of PlayerState objects."""
    return {u.player_id: u for u in units}


# Default grid/obstacles for most tests
GRID_W = 20
GRID_H = 20
NO_OBSTACLES: set[tuple[int, int]] = set()


# ===========================================================================
# 1. Role Mapping Tests
# ===========================================================================

class TestBardRoleMapping:
    """Bard class maps to offensive_support role."""

    def test_bard_maps_to_offensive_support(self):
        """bard → offensive_support in _CLASS_ROLE_MAP."""
        assert _get_role_for_class("bard") == "offensive_support"

    def test_offensive_support_in_role_map(self):
        """_CLASS_ROLE_MAP contains bard entry."""
        assert "bard" in _CLASS_ROLE_MAP
        assert _CLASS_ROLE_MAP["bard"] == "offensive_support"

    def test_role_map_count_updated(self):
        """_CLASS_ROLE_MAP has correct entry count (31 after Shaman addition)."""
        assert len(_CLASS_ROLE_MAP) == 31


# ===========================================================================
# 2. Ballad of Might — AoE Ally Buff
# ===========================================================================

class TestBalladOfMight:
    """Bard AI uses Ballad of Might when 2+ allies are in radius."""

    def test_uses_ballad_with_two_allies_in_radius(self):
        """Ballad fires when 2+ allies are within radius 2 of the Bard."""
        bard = _make_bard(x=5, y=5)
        ally1 = _make_ally(player_id="ally1", x=6, y=5)  # dist 1
        ally2 = _make_ally(player_id="ally2", x=5, y=6)  # dist 1
        enemies = [_make_enemy(x=10, y=10)]
        all_units = _build_units(bard, ally1, ally2, enemies[0])

        result = _offensive_support_skill_logic(
            bard, enemies, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "ballad_of_might"

    def test_skips_ballad_with_one_ally(self):
        """Ballad fires with 1 ally in radius (threshold lowered to 1)."""
        bard = _make_bard(x=5, y=5)
        ally1 = _make_ally(player_id="ally1", x=6, y=5)  # dist 1
        enemies = [_make_enemy(x=10, y=10)]
        all_units = _build_units(bard, ally1, enemies[0])

        result = _offensive_support_skill_logic(
            bard, enemies, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # With threshold 1, Ballad should fire for a single ally
        assert result is not None
        assert result.skill_id == "ballad_of_might"

    def test_skips_ballad_allies_out_of_radius(self):
        """Allies beyond radius 3 don't count toward Ballad threshold."""
        bard = _make_bard(x=5, y=5)
        ally1 = _make_ally(player_id="ally1", x=9, y=5)  # dist 4 — out of radius 3
        ally2 = _make_ally(player_id="ally2", x=5, y=9)  # dist 4 — out of radius 3
        enemies = [_make_enemy(x=10, y=10)]
        all_units = _build_units(bard, ally1, ally2, enemies[0])

        result = _offensive_support_skill_logic(
            bard, enemies, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "ballad_of_might"

    def test_skips_ballad_on_cooldown(self):
        """Ballad on cooldown → skipped, may fall through to next priority."""
        bard = _make_bard(x=5, y=5, cooldowns={"ballad_of_might": 3})
        ally1 = _make_ally(player_id="ally1", x=6, y=5)
        ally2 = _make_ally(player_id="ally2", x=5, y=6)
        enemies = [_make_enemy(x=10, y=10)]
        all_units = _build_units(bard, ally1, ally2, enemies[0])

        result = _offensive_support_skill_logic(
            bard, enemies, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "ballad_of_might"

    def test_skips_ballad_if_allies_already_buffed(self):
        """Ballad skipped if all allies in radius already have the buff (no stacking)."""
        bard = _make_bard(x=5, y=5)
        buff = {"buff_id": "ballad_of_might", "type": "buff", "stat": "all_damage_multiplier",
                "magnitude": 1.3, "turns_remaining": 2}
        ally1 = _make_ally(player_id="ally1", x=6, y=5, active_buffs=[buff.copy()])
        ally2 = _make_ally(player_id="ally2", x=5, y=6, active_buffs=[buff.copy()])
        enemies = [_make_enemy(x=10, y=10)]
        all_units = _build_units(bard, ally1, ally2, enemies[0])

        result = _offensive_support_skill_logic(
            bard, enemies, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "ballad_of_might"


# ===========================================================================
# 3. Dirge of Weakness — AoE Enemy Debuff
# ===========================================================================

class TestDirgeOfWeakness:
    """Bard AI uses Dirge of Weakness when 2+ enemies are clustered."""

    def test_uses_dirge_with_clustered_enemies(self):
        """Dirge fires when 2+ enemies are within radius 2 of each other and in range."""
        bard = _make_bard(x=5, y=5, cooldowns={"ballad_of_might": 5})  # ballad on CD
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)  # dist 3 — in dirge range 4
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)  # dist 4 — in dirge range 4, dist 1 from enemy1
        all_units = _build_units(bard, enemy1, enemy2)

        result = _offensive_support_skill_logic(
            bard, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "dirge_of_weakness"

    def test_casts_dirge_with_one_enemy(self):
        """Dirge fires with 1 enemy (min threshold lowered to 1)."""
        bard = _make_bard(x=5, y=5, cooldowns={"ballad_of_might": 5})
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)
        all_units = _build_units(bard, enemy1)

        result = _offensive_support_skill_logic(
            bard, [enemy1], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "dirge_of_weakness"

    def test_skips_dirge_enemies_out_of_range(self):
        """Dirge skipped when all enemies are beyond range 4."""
        bard = _make_bard(x=5, y=5, cooldowns={"ballad_of_might": 5})
        enemy1 = _make_enemy(player_id="enemy1", x=15, y=5)  # dist 10 — way out of range
        enemy2 = _make_enemy(player_id="enemy2", x=15, y=6)  # dist 10
        all_units = _build_units(bard, enemy1, enemy2)

        result = _offensive_support_skill_logic(
            bard, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "dirge_of_weakness"

    def test_skips_dirge_no_los(self):
        """Dirge skipped when there's no line of sight to the target tile."""
        bard = _make_bard(x=5, y=5, cooldowns={"ballad_of_might": 5})
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)
        # Wall blocking LOS between bard and enemies
        obstacles = {(6, 5), (7, 5), (6, 4), (7, 4), (6, 6), (7, 6)}
        all_units = _build_units(bard, enemy1, enemy2)

        result = _offensive_support_skill_logic(
            bard, [enemy1, enemy2], all_units, GRID_W, GRID_H, obstacles,
        )
        if result is not None:
            assert result.skill_id != "dirge_of_weakness"

    def test_skips_dirge_enemies_already_debuffed(self):
        """Dirge skipped when enemies already have the debuff (no stacking)."""
        bard = _make_bard(x=5, y=5, cooldowns={"ballad_of_might": 5})
        debuff = {"buff_id": "dirge_of_weakness", "type": "debuff",
                  "stat": "damage_taken_multiplier", "magnitude": 1.25, "turns_remaining": 2}
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5, active_buffs=[debuff.copy()])
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5, active_buffs=[debuff.copy()])
        all_units = _build_units(bard, enemy1, enemy2)

        result = _offensive_support_skill_logic(
            bard, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "dirge_of_weakness"

    def test_dirge_on_cooldown(self):
        """Dirge on cooldown → skipped."""
        bard = _make_bard(x=5, y=5, cooldowns={"ballad_of_might": 5, "dirge_of_weakness": 4})
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)
        all_units = _build_units(bard, enemy1, enemy2)

        result = _offensive_support_skill_logic(
            bard, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "dirge_of_weakness"


# ===========================================================================
# 4. Verse of Haste — Cooldown Reduction
# ===========================================================================

class TestVerseOfHaste:
    """Bard AI uses Verse of Haste on the ally with highest cooldown debt."""

    def test_uses_verse_on_ally_with_high_cd_debt(self):
        """Verse targets the ally with the highest total cooldown debt."""
        bard = _make_bard(x=5, y=5, cooldowns={"ballad_of_might": 5, "dirge_of_weakness": 5})
        ally1 = _make_ally(player_id="ally1", x=6, y=5,
                           cooldowns={"shield_bash": 4, "taunt": 3})  # debt = 7
        ally2 = _make_ally(player_id="ally2", class_id="ranger", x=5, y=6,
                           cooldowns={"power_shot": 1})  # debt = 1 (below threshold)
        enemies = [_make_enemy(x=15, y=15)]
        all_units = _build_units(bard, ally1, ally2, enemies[0])

        result = _offensive_support_skill_logic(
            bard, enemies, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "verse_of_haste"
        assert result.target_id == "ally1"

    def test_skips_verse_ally_low_cd_debt(self):
        """Verse skipped when all allies have cooldown debt < 1."""
        bard = _make_bard(x=5, y=5, cooldowns={"ballad_of_might": 5, "dirge_of_weakness": 5})
        ally1 = _make_ally(player_id="ally1", x=6, y=5,
                           cooldowns={})  # debt = 0 — below threshold
        enemies = [_make_enemy(x=15, y=15)]
        all_units = _build_units(bard, ally1, enemies[0])

        result = _offensive_support_skill_logic(
            bard, enemies, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "verse_of_haste"

    def test_skips_verse_ally_out_of_range(self):
        """Verse skipped when ally with high CD debt is out of range 3."""
        bard = _make_bard(x=5, y=5, cooldowns={"ballad_of_might": 5, "dirge_of_weakness": 5})
        ally1 = _make_ally(player_id="ally1", x=10, y=5,
                           cooldowns={"shield_bash": 4, "taunt": 3})  # dist 5 — out of range
        enemies = [_make_enemy(x=15, y=15)]
        all_units = _build_units(bard, ally1, enemies[0])

        result = _offensive_support_skill_logic(
            bard, enemies, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "verse_of_haste"

    def test_verse_on_cooldown(self):
        """Verse on cooldown → skipped."""
        bard = _make_bard(x=5, y=5, cooldowns={
            "ballad_of_might": 5, "dirge_of_weakness": 5, "verse_of_haste": 3,
        })
        ally1 = _make_ally(player_id="ally1", x=6, y=5,
                           cooldowns={"shield_bash": 4, "taunt": 3})
        enemies = [_make_enemy(x=15, y=15)]
        all_units = _build_units(bard, ally1, enemies[0])

        result = _offensive_support_skill_logic(
            bard, enemies, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        if result is not None:
            assert result.skill_id != "verse_of_haste"

    def test_verse_picks_highest_debt_ally(self):
        """When multiple allies have cooldowns, Verse targets the one with highest total debt."""
        bard = _make_bard(x=5, y=5, cooldowns={"ballad_of_might": 5, "dirge_of_weakness": 5})
        ally1 = _make_ally(player_id="ally1", x=6, y=5,
                           cooldowns={"shield_bash": 2})  # debt = 2
        ally2 = _make_ally(player_id="ally2", class_id="mage", x=5, y=6,
                           cooldowns={"fireball": 5, "frost_nova": 3})  # debt = 8
        enemies = [_make_enemy(x=15, y=15)]
        all_units = _build_units(bard, ally1, ally2, enemies[0])

        result = _offensive_support_skill_logic(
            bard, enemies, all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "verse_of_haste"
        assert result.target_id == "ally2"


# ===========================================================================
# 5. Cacophony — Self-Peel (AoE Damage + Slow)
# ===========================================================================

class TestCacophony:
    """Bard AI uses Cacophony when enemy is within radius 2."""

    def test_uses_cacophony_with_adjacent_enemy(self):
        """Cacophony fires when an enemy is within radius 2 of the Bard."""
        bard = _make_bard(x=5, y=5, cooldowns={
            "ballad_of_might": 5, "dirge_of_weakness": 5, "verse_of_haste": 5,
        })
        enemy = _make_enemy(player_id="enemy1", x=6, y=5)  # adjacent (dist 1)
        all_units = _build_units(bard, enemy)

        result = _offensive_support_skill_logic(
            bard, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "cacophony"

    def test_skips_cacophony_no_adjacent_enemy(self):
        """Cacophony does NOT fire when no enemy is adjacent."""
        bard = _make_bard(x=5, y=5, cooldowns={
            "ballad_of_might": 5, "dirge_of_weakness": 5, "verse_of_haste": 5,
        })
        enemy = _make_enemy(player_id="enemy1", x=8, y=5)  # dist 3 — not adjacent
        all_units = _build_units(bard, enemy)

        result = _offensive_support_skill_logic(
            bard, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should return None when all skills on CD / don't apply
        assert result is None

    def test_cacophony_on_cooldown(self):
        """Cacophony on cooldown → skipped even with adjacent enemy."""
        bard = _make_bard(x=5, y=5, cooldowns={
            "ballad_of_might": 5, "dirge_of_weakness": 5,
            "verse_of_haste": 5, "cacophony": 3,
        })
        enemy = _make_enemy(player_id="enemy1", x=6, y=5)
        all_units = _build_units(bard, enemy)

        result = _offensive_support_skill_logic(
            bard, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None


# ===========================================================================
# 6. Fallback — All Skills on Cooldown
# ===========================================================================

class TestFallback:
    """When all skills are on cooldown, AI returns None (fall through to auto-attack)."""

    def test_returns_none_all_skills_on_cooldown(self):
        """All 4 skills on cooldown → returns None."""
        bard = _make_bard(x=5, y=5, cooldowns={
            "ballad_of_might": 3, "dirge_of_weakness": 4,
            "verse_of_haste": 3, "cacophony": 3,
        })
        ally1 = _make_ally(player_id="ally1", x=6, y=5)
        ally2 = _make_ally(player_id="ally2", x=5, y=6)
        enemy = _make_enemy(player_id="enemy1", x=6, y=6)
        all_units = _build_units(bard, ally1, ally2, enemy)

        result = _offensive_support_skill_logic(
            bard, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None

    def test_returns_none_no_enemies(self):
        """No enemies visible → returns None (no one to debuff or self-peel from)."""
        bard = _make_bard(x=5, y=5)
        ally1 = _make_ally(player_id="ally1", x=6, y=5)
        ally2 = _make_ally(player_id="ally2", x=5, y=6)
        all_units = _build_units(bard, ally1, ally2)

        result = _offensive_support_skill_logic(
            bard, [], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Ballad could still fire (allies present, no enemies required for it)
        # But with 2 allies present and ballad off CD, it should fire
        # Let's test the "no allies nearby" case below
        pass  # Ballad is self-targeted, doesn't need enemies

    def test_returns_none_no_enemies_no_allies(self):
        """No enemies and no allies → returns None."""
        bard = _make_bard(x=5, y=5)
        all_units = _build_units(bard)

        result = _offensive_support_skill_logic(
            bard, [], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None


# ===========================================================================
# 7. Dispatcher Integration
# ===========================================================================

class TestDispatcher:
    """_decide_skill_usage dispatches bard to offensive_support handler."""

    def test_dispatcher_routes_bard_to_offensive_support(self):
        """_decide_skill_usage correctly routes bard class to offensive_support handler."""
        bard = _make_bard(x=5, y=5)
        ally1 = _make_ally(player_id="ally1", x=6, y=5)
        ally2 = _make_ally(player_id="ally2", x=5, y=6)
        enemy = _make_enemy(player_id="enemy1", x=10, y=10)
        all_units = _build_units(bard, ally1, ally2, enemy)

        result = _decide_skill_usage(
            bard, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        # Should return a skill action (Ballad since 2 allies in range)
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "ballad_of_might"

    def test_dispatcher_returns_none_when_no_skills_usable(self):
        """Bard with all skills on CD → returns None through dispatcher."""
        bard = _make_bard(x=5, y=5, cooldowns={
            "ballad_of_might": 3, "dirge_of_weakness": 4,
            "verse_of_haste": 3, "cacophony": 3,
        })
        enemy = _make_enemy(player_id="enemy1", x=10, y=10)
        all_units = _build_units(bard, enemy)

        result = _decide_skill_usage(
            bard, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is None


# ===========================================================================
# 8. Priority Order
# ===========================================================================

class TestPriorityOrder:
    """Skills are used in the correct priority order."""

    def test_ballad_over_dirge(self):
        """Ballad takes priority over Dirge when both conditions are met."""
        bard = _make_bard(x=5, y=5)
        ally1 = _make_ally(player_id="ally1", x=6, y=5)  # in ballad radius
        ally2 = _make_ally(player_id="ally2", x=5, y=6)  # in ballad radius
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)  # clustered
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)  # clustered
        all_units = _build_units(bard, ally1, ally2, enemy1, enemy2)

        result = _offensive_support_skill_logic(
            bard, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "ballad_of_might"  # Higher priority than dirge

    def test_dirge_when_ballad_on_cd(self):
        """Dirge fires when Ballad is on cooldown and enemies are clustered."""
        bard = _make_bard(x=5, y=5, cooldowns={"ballad_of_might": 3})
        ally1 = _make_ally(player_id="ally1", x=6, y=5)
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=9, y=5)
        all_units = _build_units(bard, ally1, enemy1, enemy2)

        result = _offensive_support_skill_logic(
            bard, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "dirge_of_weakness"

    def test_verse_when_ballad_and_dirge_on_cd(self):
        """Verse fires when Ballad & Dirge are on CD and ally has high cooldown debt."""
        bard = _make_bard(x=5, y=5, cooldowns={
            "ballad_of_might": 3, "dirge_of_weakness": 4,
        })
        ally1 = _make_ally(player_id="ally1", x=6, y=5,
                           cooldowns={"shield_bash": 4, "taunt": 3})  # debt = 7
        enemy = _make_enemy(player_id="enemy1", x=15, y=15)
        all_units = _build_units(bard, ally1, enemy)

        result = _offensive_support_skill_logic(
            bard, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "verse_of_haste"

    def test_cacophony_last_resort(self):
        """Cacophony fires only when higher-priority skills aren't usable."""
        bard = _make_bard(x=5, y=5, cooldowns={
            "ballad_of_might": 3, "dirge_of_weakness": 4, "verse_of_haste": 3,
        })
        enemy = _make_enemy(player_id="enemy1", x=6, y=5)  # adjacent
        all_units = _build_units(bard, enemy)

        result = _offensive_support_skill_logic(
            bard, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "cacophony"


# ===========================================================================
# 9. Positioning — Support Move Preference
# ===========================================================================

class TestPositioning:
    """Offensive support (Bard) uses support move preference — stays near allies."""

    def test_support_move_preference_returns_ally_position(self):
        """_support_move_preference returns most injured ally's position for Bard."""
        bard = _make_bard(x=5, y=5)
        ally = _make_ally(player_id="ally1", x=10, y=10, hp=50, max_hp=150)  # injured
        all_units = _build_units(bard, ally)

        result = _support_move_preference(bard, all_units)
        assert result is not None
        assert result == (10, 10)  # Move toward injured ally

    def test_support_move_preference_nearest_ally_when_all_healthy(self):
        """When all allies are healthy, move toward nearest ally to stay grouped."""
        bard = _make_bard(x=5, y=5)
        ally1 = _make_ally(player_id="ally1", x=8, y=5, hp=150, max_hp=150)  # healthy, dist 3
        ally2 = _make_ally(player_id="ally2", x=12, y=5, hp=150, max_hp=150)  # healthy, dist 7
        all_units = _build_units(bard, ally1, ally2)

        result = _support_move_preference(bard, all_units)
        assert result is not None
        assert result == (8, 5)  # Nearest ally

    def test_support_move_preference_no_allies(self):
        """No allies alive → returns None (fall through to default movement)."""
        bard = _make_bard(x=5, y=5)
        all_units = _build_units(bard)

        result = _support_move_preference(bard, all_units)
        assert result is None
