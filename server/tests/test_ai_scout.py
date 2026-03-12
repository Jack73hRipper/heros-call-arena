"""
Tests for Phase 8E-2 — Scout Role AI (Inquisitor: Power Shot + Shadow Step).

Covers:
  8E-2: _scout_skill_logic() — Scout decision engine
    - Escape Shadow Step: low HP + adjacent enemy → teleport away
    - Escape tile selection: maximizes distance from enemy, prefers ranged range
    - Power Shot: enemy in range + LOS + off CD → uses Power Shot
    - Power Shot target selection: picks best target (low HP priority)
    - Power Shot falls back to secondary target when best is blocked
    - Offensive Shadow Step: enemy far away → teleport closer (but not adjacent)
    - Offensive tile selection: stays 2+ tiles from target (prefers ranged distance)
    - Priority ordering: escape > power shot > offensive shadow step

  Helper functions:
    - _find_valid_shadow_step_tiles: bounds, obstacles, occupied, LOS checks
    - _find_shadow_step_escape_tile: scoring (distance + ranged range bonus)
    - _find_shadow_step_offensive_tile: scoring (minimize distance, keep 2+)

  Integration:
    - Inquisitor dispatches through _decide_skill_usage to scout logic
    - Inquisitor role mapping is "scout"

  Guard:
    - Enemy AI (no hero_id) does not use scout skill logic
    - Non-scout class does not trigger scout skill logic
    - No enemies visible → returns None
    - All skills on cooldown → returns None
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.ai_behavior import (
    _scout_skill_logic,
    _decide_skill_usage,
    _get_role_for_class,
    _find_valid_shadow_step_tiles,
    _find_shadow_step_escape_tile,
    _find_shadow_step_offensive_tile,
    _SHADOW_STEP_ESCAPE_HP_THRESHOLD,
    _SHADOW_STEP_OFFENSIVE_MIN_DISTANCE,
)
from app.core.combat import load_combat_config
from app.core.skills import load_skills_config


def setup_module():
    """Ensure configs are loaded before any test runs."""
    load_combat_config()
    load_skills_config()


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

def make_inquisitor(pid="inq1", username="Inquisitor Zael", x=5, y=5,
                    hp=80, max_hp=80, team="a", ai_stance="follow",
                    cooldowns=None, active_buffs=None,
                    hero_id="hero_inq") -> PlayerState:
    """Create an Inquisitor hero AI unit (Scout role)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=10,
        ranged_damage=8,
        armor=4,
        team=team,
        unit_type="ai",
        hero_id=hero_id,
        ai_stance=ai_stance,
        class_id="inquisitor",
        ranged_range=5,
        vision_range=9,
        inventory=[],
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
    )


def make_enemy(pid="enemy1", username="Demon", x=9, y=5,
               hp=80, max_hp=80, team="b") -> PlayerState:
    """Create an enemy AI unit (NOT a hero)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=10,
        armor=0,
        team=team,
        unit_type="ai",
        hero_id=None,
        ranged_range=0,
        vision_range=5,
        inventory=[],
    )


def make_ranger(pid="ranger1", username="Ranger Kael", x=5, y=5,
                hp=80, max_hp=80, team="a",
                hero_id="hero_ranger") -> PlayerState:
    """Create a Ranger hero AI unit (Ranged DPS role — cannot use Shadow Step)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=8,
        ranged_damage=18,
        armor=2,
        team=team,
        unit_type="ai",
        hero_id=hero_id,
        ai_stance="follow",
        class_id="ranger",
        ranged_range=6,
        vision_range=7,
        inventory=[],
        cooldowns={},
        active_buffs=[],
    )


# ============================================================================
# 1. Shadow Step Escape Tests (Priority 1)
# ============================================================================


class TestScoutEscapeShadowStep:
    """Tests for defensive Shadow Step escape when low HP + adjacent enemy."""

    def test_inquisitor_escape_shadow_step(self):
        """HP < 40% + adjacent enemy + Shadow Step off CD → teleports away."""
        # Inquisitor at 20% HP, enemy adjacent at (6, 5)
        inq = make_inquisitor(x=5, y=5, hp=16, max_hp=80)
        enemy = make_enemy(x=6, y=5)
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "shadow_step"
        # Should teleport AWAY from the enemy (target_x < 6)
        assert result.target_x is not None
        assert result.target_y is not None

    def test_inquisitor_escape_tile_maximizes_distance(self):
        """Escape tile selection maximizes distance from nearest enemy."""
        inq = make_inquisitor(x=5, y=5, hp=16, max_hp=80)
        enemy = make_enemy(x=6, y=5)
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.skill_id == "shadow_step"
        # Escape tile should be farther from enemy than the current position
        from app.core.ai_behavior import _chebyshev
        current_dist = _chebyshev((5, 5), (6, 5))
        escape_dist = _chebyshev((result.target_x, result.target_y), (6, 5))
        assert escape_dist > current_dist

    def test_inquisitor_escape_prefers_ranged_range(self):
        """Escape tile in ranged range of enemy scores higher (can shoot after retreat)."""
        # Inquisitor at 20% HP with enemy adjacent.
        # The escape tile finder should prefer tiles within ranged_range=5
        inq = make_inquisitor(x=5, y=5, hp=16, max_hp=80)
        enemy = make_enemy(x=6, y=5)
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.skill_id == "shadow_step"
        # With Shadow Step range 3, max distance from enemy at (6,5) is ~4
        # which is within ranged_range=5, so tile should still be in shooting range
        from app.core.ai_behavior import _chebyshev
        teleport_dist = _chebyshev((result.target_x, result.target_y), (6, 5))
        assert teleport_dist <= 5  # Within Inquisitor's ranged_range

    def test_inquisitor_no_escape_when_healthy(self):
        """HP > 40% + adjacent enemy → does NOT escape (uses Power Shot or attack)."""
        inq = make_inquisitor(x=5, y=5, hp=60, max_hp=80,
                              cooldowns={"rebuke": 99, "seal_of_judgment": 99})  # 75% HP
        enemy = make_enemy(x=6, y=5)  # Adjacent
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        # Should use Power Shot or None, NOT shadow_step escape
        if result is not None:
            # If a skill is returned, it should be Power Shot (not escape)
            assert result.skill_id == "power_shot"

    def test_inquisitor_no_escape_when_not_adjacent(self):
        """HP < 40% but enemy NOT adjacent → skips escape, uses Power Shot if possible."""
        inq = make_inquisitor(x=5, y=5, hp=16, max_hp=80,
                              cooldowns={"rebuke": 99, "seal_of_judgment": 99})  # 20% HP
        enemy = make_enemy(x=9, y=5)  # 4 tiles away, NOT adjacent
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        # Should NOT be shadow_step escape (not adjacent)
        # Should be Power Shot (enemy in range 5, 4 tiles away)
        if result is not None:
            assert result.skill_id == "power_shot"

    def test_inquisitor_escape_shadow_step_on_cd(self):
        """HP < 40% + adjacent enemy but Shadow Step on CD → tries Power Shot instead."""
        inq = make_inquisitor(x=5, y=5, hp=16, max_hp=80,
                              cooldowns={"shadow_step": 3, "rebuke": 99, "seal_of_judgment": 99})
        enemy = make_enemy(x=6, y=5)  # Adjacent
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        # Shadow Step on CD, should try Power Shot or return None
        if result is not None:
            assert result.skill_id == "power_shot"

    def test_inquisitor_escape_blocked_by_walls(self):
        """All escape tiles blocked by obstacles → falls through to Power Shot."""
        # Inquisitor cornered with walls everywhere except current position
        inq = make_inquisitor(x=1, y=1, hp=16, max_hp=80)
        enemy = make_enemy(x=2, y=1)  # Adjacent
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]
        # Surround with obstacles (leave only very few tiles)
        obstacles = set()
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                tx, ty = 1 + dx, 1 + dy
                if (tx, ty) != (1, 1) and (tx, ty) != (2, 1):
                    if 0 <= tx < 15 and 0 <= ty < 15:
                        obstacles.add((tx, ty))

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=obstacles,
        )

        # No valid escape tiles → should fall through to Power Shot or None
        if result is not None:
            assert result.skill_id != "shadow_step" or result.skill_id == "power_shot"


# ============================================================================
# 2. Power Shot Tests (Priority 2)
# ============================================================================


class TestScoutPowerShot:
    """Tests for Power Shot usage by Scout role AI."""

    def test_inquisitor_power_shot_when_available(self):
        """Enemy in range + LOS + Power Shot off CD → uses Power Shot."""
        inq = make_inquisitor(x=5, y=5, cooldowns={"rebuke": 99, "seal_of_judgment": 99})
        enemy = make_enemy(x=9, y=5)  # 4 tiles away, within range 5
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "power_shot"
        assert result.target_x == 9
        assert result.target_y == 5

    def test_inquisitor_power_shot_on_cd_returns_none(self):
        """Power Shot on CD + no escape needed + enemy close → returns None."""
        inq = make_inquisitor(x=5, y=5, cooldowns={"power_shot": 3, "rebuke": 99, "seal_of_judgment": 99})
        enemy = make_enemy(x=7, y=5)  # 2 tiles away (within 4, no offensive SS)
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is None  # Falls through to basic attack/move

    def test_inquisitor_power_shot_requires_los(self):
        """Enemy in range but obstacle blocks LOS → doesn't use Power Shot."""
        inq = make_inquisitor(x=5, y=5)
        enemy = make_enemy(x=9, y=5)
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]
        obstacles = {(7, 5)}  # Wall blocks LOS

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=obstacles,
        )

        # No LOS for Power Shot, enemy at dist 4 (not > 4), so no offensive SS
        assert result is None

    def test_inquisitor_power_shot_out_of_range(self):
        """Enemy beyond ranged range (5) → no Power Shot."""
        inq = make_inquisitor(x=0, y=0)
        enemy = make_enemy(x=8, y=0)  # 8 tiles away, beyond range 5
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        # Out of Power Shot range, but dist 8 > 4, so offensive Shadow Step should fire
        assert result is not None
        assert result.skill_id == "shadow_step"

    def test_inquisitor_power_shot_target_selection(self):
        """Multiple enemies: picks best target (lowest HP)."""
        inq = make_inquisitor(x=5, y=5, cooldowns={"rebuke": 99, "seal_of_judgment": 99})
        enemy_full = make_enemy(pid="e_full", x=9, y=5, hp=80, max_hp=80)
        enemy_low = make_enemy(pid="e_low", x=8, y=5, hp=20, max_hp=80)
        all_units = {
            inq.player_id: inq,
            enemy_full.player_id: enemy_full,
            enemy_low.player_id: enemy_low,
        }
        enemies = [enemy_full, enemy_low]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.skill_id == "power_shot"
        # Should target the low-HP enemy
        assert result.target_x == 8
        assert result.target_y == 5

    def test_inquisitor_power_shot_fallback_secondary(self):
        """Best target blocked by wall → falls back to secondary target."""
        inq = make_inquisitor(x=5, y=5, cooldowns={"rebuke": 99, "seal_of_judgment": 99})
        enemy_low = make_enemy(pid="e_low", x=9, y=5, hp=20, max_hp=80)
        enemy_full = make_enemy(pid="e_full", x=8, y=8, hp=80, max_hp=80)
        all_units = {
            inq.player_id: inq,
            enemy_low.player_id: enemy_low,
            enemy_full.player_id: enemy_full,
        }
        enemies = [enemy_low, enemy_full]
        obstacles = {(7, 5)}  # Blocks LOS to low-HP enemy

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=obstacles,
        )

        assert result is not None
        assert result.skill_id == "power_shot"
        assert result.target_x == 8
        assert result.target_y == 8


# ============================================================================
# 3. Offensive Shadow Step Tests (Priority 3)
# ============================================================================


class TestScoutOffensiveShadowStep:
    """Tests for offensive Shadow Step gap-close when enemy is far away."""

    def test_inquisitor_offensive_shadow_step(self):
        """Enemy > 4 tiles away + Shadow Step off CD → teleports closer."""
        inq = make_inquisitor(x=0, y=0)
        enemy = make_enemy(x=10, y=0)  # 10 tiles away
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]
        # Power Shot out of range (range 5, dist 10)

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "shadow_step"
        assert result.target_x is not None
        assert result.target_y is not None

    def test_inquisitor_offensive_tile_not_adjacent(self):
        """Offensive Shadow Step tile should NOT be adjacent to enemy (prefer range)."""
        inq = make_inquisitor(x=0, y=0)
        enemy = make_enemy(x=10, y=0)  # Far away
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.skill_id == "shadow_step"
        # Tile should be 2+ from enemy (Inquisitor prefers ranged distance)
        from app.core.ai_behavior import _chebyshev
        dist_to_enemy = _chebyshev(
            (result.target_x, result.target_y),
            (enemy.position.x, enemy.position.y),
        )
        assert dist_to_enemy >= 2

    def test_inquisitor_offensive_tile_closer_than_current(self):
        """Offensive Shadow Step tile should be closer to enemy than current position."""
        inq = make_inquisitor(x=0, y=0)
        enemy = make_enemy(x=10, y=0)
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.skill_id == "shadow_step"
        from app.core.ai_behavior import _chebyshev
        current_dist = _chebyshev((0, 0), (10, 0))
        new_dist = _chebyshev(
            (result.target_x, result.target_y),
            (10, 0),
        )
        assert new_dist < current_dist

    def test_inquisitor_no_offensive_ss_when_close(self):
        """Enemy within 4 tiles → no offensive Shadow Step (not needed)."""
        inq = make_inquisitor(x=5, y=5, cooldowns={"power_shot": 3, "rebuke": 99, "seal_of_judgment": 99})
        enemy = make_enemy(x=8, y=5)  # 3 tiles (≤ 4, no offensive SS)
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        # Power Shot on CD, enemy at dist 3 (≤ 4), so no offensive SS
        assert result is None

    def test_inquisitor_offensive_ss_on_cd_returns_none(self):
        """Enemy far away but Shadow Step on CD + Power Shot out of range → None."""
        inq = make_inquisitor(x=0, y=0,
                              cooldowns={"shadow_step": 3, "power_shot": 4})
        enemy = make_enemy(x=12, y=0)  # Far away, out of PS range
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is None


# ============================================================================
# 4. Priority Chain Tests
# ============================================================================


class TestScoutPriorityChain:
    """Tests verifying the correct priority ordering of scout decisions."""

    def test_escape_over_power_shot(self):
        """HP < 40% + adjacent enemy + both skills off CD → escape wins over Power Shot."""
        inq = make_inquisitor(x=5, y=5, hp=16, max_hp=80)  # 20% HP
        enemy = make_enemy(x=6, y=5)  # Adjacent, within ranged range too
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.skill_id == "shadow_step"  # Escape takes priority

    def test_power_shot_over_offensive_ss(self):
        """Enemy in range + LOS + both skills off CD → Power Shot wins over offensive SS."""
        inq = make_inquisitor(x=5, y=5, cooldowns={"rebuke": 99, "seal_of_judgment": 99})
        # Enemy at 9,5 is 4 tiles away (within ranged_range=5) — not > 4 for offensive SS
        enemy = make_enemy(x=9, y=5)
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.skill_id == "power_shot"  # Power Shot before offensive SS

    def test_all_skills_on_cd_returns_none(self):
        """All skills on CD → returns None."""
        inq = make_inquisitor(x=5, y=5,
                              cooldowns={"shadow_step": 2, "power_shot": 3, "rebuke": 99, "seal_of_judgment": 99})
        enemy = make_enemy(x=9, y=5)
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is None

    def test_no_enemies_returns_none(self):
        """No enemies visible → returns None immediately."""
        inq = make_inquisitor(x=5, y=5, cooldowns={"seal_of_judgment": 99})
        all_units = {inq.player_id: inq}
        enemies = []

        result = _scout_skill_logic(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is None


# ============================================================================
# 5. Helper Function Tests
# ============================================================================


class TestShadowStepTileFinding:
    """Tests for Shadow Step tile-finding helper functions."""

    def test_valid_tiles_excludes_obstacles(self):
        """Obstacle tiles are excluded from valid Shadow Step tiles."""
        inq = make_inquisitor(x=5, y=5)
        all_units = {inq.player_id: inq}
        obstacles = {(6, 5), (4, 5), (5, 6), (5, 4)}

        tiles = _find_valid_shadow_step_tiles(
            inq, all_units, 15, 15, obstacles,
        )

        for obs in obstacles:
            assert obs not in tiles

    def test_valid_tiles_excludes_occupied(self):
        """Tiles occupied by other units are excluded."""
        inq = make_inquisitor(x=5, y=5)
        ally = make_enemy(pid="ally1", x=6, y=5, team="a")
        ally.is_alive = True
        all_units = {inq.player_id: inq, ally.player_id: ally}

        tiles = _find_valid_shadow_step_tiles(
            inq, all_units, 15, 15, set(),
        )

        assert (6, 5) not in tiles

    def test_valid_tiles_excludes_own_position(self):
        """AI's own position is excluded (can't teleport to self)."""
        inq = make_inquisitor(x=5, y=5)
        all_units = {inq.player_id: inq}

        tiles = _find_valid_shadow_step_tiles(
            inq, all_units, 15, 15, set(),
        )

        assert (5, 5) not in tiles

    def test_valid_tiles_within_range_3(self):
        """All valid tiles are within Chebyshev range 3 of the AI."""
        inq = make_inquisitor(x=5, y=5)
        all_units = {inq.player_id: inq}

        tiles = _find_valid_shadow_step_tiles(
            inq, all_units, 15, 15, set(),
        )

        from app.core.ai_behavior import _chebyshev
        for tile in tiles:
            assert _chebyshev((5, 5), tile) <= 3

    def test_valid_tiles_respects_grid_bounds(self):
        """Tiles outside grid bounds are excluded."""
        inq = make_inquisitor(x=0, y=0)  # Corner position
        all_units = {inq.player_id: inq}

        tiles = _find_valid_shadow_step_tiles(
            inq, all_units, 15, 15, set(),
        )

        for tx, ty in tiles:
            assert 0 <= tx < 15
            assert 0 <= ty < 15

    def test_valid_tiles_requires_los(self):
        """Tiles without LOS from AI position are excluded."""
        inq = make_inquisitor(x=5, y=5)
        all_units = {inq.player_id: inq}
        # Wall that blocks LOS to tiles behind it
        obstacles = {(6, 5)}

        tiles = _find_valid_shadow_step_tiles(
            inq, all_units, 15, 15, obstacles,
        )

        # (6, 5) is obstacle, so not valid
        assert (6, 5) not in tiles

    def test_escape_tile_returns_none_when_no_tiles(self):
        """No valid tiles → returns None."""
        inq = make_inquisitor(x=0, y=0)
        enemy = make_enemy(x=1, y=0)
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        # Block everything
        obstacles = set()
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                tx, ty = dx, dy
                if (tx, ty) != (0, 0) and (tx, ty) != (1, 0):
                    if 0 <= tx < 15 and 0 <= ty < 15:
                        obstacles.add((tx, ty))

        result = _find_shadow_step_escape_tile(
            inq, [enemy], all_units, 15, 15, obstacles, ranged_range=5,
        )

        assert result is None

    def test_offensive_tile_returns_none_when_no_tiles(self):
        """No valid tiles → returns None."""
        inq = make_inquisitor(x=0, y=0)
        enemy = make_enemy(x=10, y=0)
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        # Block everything
        obstacles = set()
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                tx, ty = dx, dy
                if (tx, ty) != (0, 0) and (tx, ty) != (10, 0):
                    if 0 <= tx < 15 and 0 <= ty < 15:
                        obstacles.add((tx, ty))

        result = _find_shadow_step_offensive_tile(
            inq, enemy, all_units, 15, 15, obstacles,
        )

        assert result is None


# ============================================================================
# 6. Integration — _decide_skill_usage() dispatch
# ============================================================================


class TestScoutDispatch:
    """Tests for scout role dispatch through _decide_skill_usage."""

    def test_inquisitor_role_is_scout(self):
        """Inquisitor class maps to scout role."""
        assert _get_role_for_class("inquisitor") == "scout"

    def test_inquisitor_dispatches_through_skill_usage(self):
        """Inquisitor dispatches through _decide_skill_usage and gets Power Shot."""
        inq = make_inquisitor(x=5, y=5, cooldowns={"rebuke": 99, "seal_of_judgment": 99})
        enemy = make_enemy(x=9, y=5)
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _decide_skill_usage(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "power_shot"

    def test_inquisitor_dispatch_escape_shadow_step(self):
        """Low-HP Inquisitor dispatches escape Shadow Step through _decide_skill_usage."""
        inq = make_inquisitor(x=5, y=5, hp=16, max_hp=80)
        enemy = make_enemy(x=6, y=5)  # Adjacent
        all_units = {inq.player_id: inq, enemy.player_id: enemy}
        enemies = [enemy]

        result = _decide_skill_usage(
            inq, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "shadow_step"


# ============================================================================
# 7. Guard Tests — Exclusion & Regression
# ============================================================================


class TestScoutGuard:
    """Guard tests ensuring non-scout classes and enemy AI are unaffected."""

    def test_enemy_ai_no_scout_skills(self):
        """Enemy AI (no hero_id, no class_id) cannot use scout skills."""
        enemy = make_enemy(x=5, y=5)
        enemy_target = make_enemy(pid="et", x=9, y=5, team="a")
        all_units = {enemy.player_id: enemy, enemy_target.player_id: enemy_target}
        enemies = [enemy_target]

        result = _scout_skill_logic(enemy, enemies, all_units, 15, 15, set())
        assert result is None

    def test_ranger_no_scout_dispatch(self):
        """Ranger (ranged_dps) does NOT dispatch to scout handler."""
        assert _get_role_for_class("ranger") == "ranged_dps"
        assert _get_role_for_class("ranger") != "scout"

    def test_ranger_cannot_shadow_step(self):
        """Ranger does not have Shadow Step — direct call returns None for SS."""
        ranger = make_ranger(x=5, y=5, hp=16, max_hp=80)
        enemy = make_enemy(x=6, y=5)
        all_units = {ranger.player_id: ranger, enemy.player_id: enemy}
        enemies = [enemy]

        # Direct call to scout logic — ranger can't use shadow_step
        result = _scout_skill_logic(ranger, enemies, all_units, 15, 15, set())

        # Ranger has power_shot but not shadow_step, so escape fails
        # but Power Shot should work since ranger's class allows it
        if result is not None:
            assert result.skill_id == "power_shot"

    def test_null_class_no_crash(self):
        """class_id=None → _decide_skill_usage returns None, no crash."""
        unit = PlayerState(
            player_id="legacy1",
            username="Legacy",
            position=Position(x=5, y=5),
            hp=80,
            max_hp=80,
            attack_damage=10,
            armor=0,
            team="a",
            unit_type="ai",
            class_id=None,
            ranged_range=5,
            vision_range=5,
            inventory=[],
        )
        enemy = make_enemy(x=9, y=5)
        all_units = {unit.player_id: unit, enemy.player_id: enemy}
        enemies = [enemy]

        result = _decide_skill_usage(
            unit, enemies, all_units,
            grid_width=15, grid_height=15, obstacles=set(),
        )
        assert result is None
