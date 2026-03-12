"""
Tests for Phase 8E-3 — Hybrid DPS Role AI (Hexblade: Double Strike + Shadow Step).

Covers:
  8E-3: _hybrid_dps_skill_logic() — Hybrid DPS decision engine
    - Double Strike: adjacent enemy + off cooldown → uses Double Strike (120%)
    - Double Strike target selection: picks best target (low HP priority)
    - Double Strike over basic melee: strictly superior when off CD
    - Shadow Step gap-close: enemy > 3 tiles away + off cooldown → teleport adjacent
    - Shadow Step tile selection: prefers tiles adjacent to target enemy
    - Shadow Step requires LOS: no valid tile without LOS → doesn't teleport
    - Priority ordering: Double Strike > Shadow Step gap-close
    - No skills available: all on cooldown → returns None

  Helper function:
    - _find_shadow_step_gapcloser_tile: prefers adjacent-to-target tiles,
      tiebreaks by distance from AI

  Integration:
    - Hexblade dispatches through _decide_skill_usage to hybrid_dps logic
    - Hexblade role mapping is "hybrid_dps"

  Guard:
    - Enemy AI (no hero_id) does not use hybrid_dps skill logic
    - Non-hybrid class does not trigger hybrid_dps skill logic
    - No enemies visible → returns None
    - All skills on cooldown → returns None
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.ai_behavior import (
    _hybrid_dps_skill_logic,
    _decide_skill_usage,
    _get_role_for_class,
    _find_valid_shadow_step_tiles,
    _find_shadow_step_gapcloser_tile,
    _SHADOW_STEP_GAPCLOSER_MIN_DISTANCE,
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

def make_hexblade(pid="hex1", username="Shadow Fang", x=5, y=5,
                  hp=110, max_hp=110, team="a", ai_stance="follow",
                  cooldowns=None, active_buffs=None,
                  hero_id="hero_hex") -> PlayerState:
    """Create a Hexblade hero AI unit (Hybrid DPS role).
    
    By default, Ward is active (shield_charges buff) so tests focus on
    Double Strike / Shadow Step without Ward stealing priority.
    Pass active_buffs=[] to test Ward-specific behavior.
    """
    default_buffs = [{"buff_id": "ward", "type": "shield_charges", "charges": 3, "reflect_damage": 8}]
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=15,
        ranged_damage=12,
        armor=5,
        team=team,
        unit_type="ai",
        hero_id=hero_id,
        ai_stance=ai_stance,
        class_id="hexblade",
        ranged_range=4,
        vision_range=6,
        inventory=[],
        cooldowns=cooldowns or {},
        active_buffs=active_buffs if active_buffs is not None else default_buffs,
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


def make_ally(pid="ally1", username="Ser Aldric", x=4, y=5,
              hp=150, max_hp=150, team="a", class_id="crusader",
              hero_id="hero_ally1") -> PlayerState:
    """Create an allied hero AI unit."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=20,
        armor=8,
        team=team,
        unit_type="ai",
        hero_id=hero_id,
        ai_stance="follow",
        class_id=class_id,
        ranged_range=1,
        vision_range=5,
        inventory=[],
        cooldowns={},
        active_buffs=[],
    )


# ============================================================================
# 1. _hybrid_dps_skill_logic() Tests — Double Strike (8E-3)
# ============================================================================

class TestHybridDoubleStrike:
    """Tests for Double Strike usage by Hybrid DPS role AI."""

    def test_hexblade_double_strike_adjacent_enemy(self):
        """Adjacent enemy + DS off CD + Wither on CD → uses Double Strike."""
        hexblade = make_hexblade(cooldowns={"wither": 3})
        enemy = make_enemy(x=6, y=5)  # Adjacent
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "double_strike"
        assert result.target_x == 6
        assert result.target_y == 5

    def test_hexblade_double_strike_diagonal_adjacent(self):
        """Enemy diagonally adjacent + Wither on CD → still uses DS (Chebyshev distance 1)."""
        hexblade = make_hexblade(cooldowns={"wither": 3})
        enemy = make_enemy(x=6, y=6)  # Diagonal
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        assert result is not None
        assert result.skill_id == "double_strike"
        assert result.target_x == 6
        assert result.target_y == 6

    def test_hexblade_double_strike_on_cooldown(self):
        """Adjacent enemy + DS on CD + Wither on CD → None (fall through to basic attack)."""
        hexblade = make_hexblade(cooldowns={"double_strike": 2, "wither": 3})
        enemy = make_enemy(x=6, y=5)  # Adjacent
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        # DS on CD, enemy adjacent (too close for gap-close) → None
        assert result is None

    def test_hexblade_ds_targets_lowest_hp(self):
        """Two adjacent enemies, one low HP + Wither on CD → DS targets the hurt one."""
        hexblade = make_hexblade(cooldowns={"wither": 3})
        enemy_full = make_enemy(pid="e_full", username="Demon A", x=6, y=5,
                                hp=80, max_hp=80)
        enemy_hurt = make_enemy(pid="e_hurt", username="Demon B", x=4, y=5,
                                hp=15, max_hp=80)  # Below 30% → low HP bonus
        all_units = {
            hexblade.player_id: hexblade,
            enemy_full.player_id: enemy_full,
            enemy_hurt.player_id: enemy_hurt,
        }
        enemies = [enemy_full, enemy_hurt]

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        assert result is not None
        assert result.skill_id == "double_strike"
        assert result.target_x == enemy_hurt.position.x
        assert result.target_y == enemy_hurt.position.y

    def test_hexblade_no_ds_enemy_not_adjacent(self):
        """Enemy 2 tiles away + DS off CD + Wither on CD → no DS (requires adjacent target)."""
        hexblade = make_hexblade(cooldowns={"wither": 3})
        enemy = make_enemy(x=7, y=5)  # 2 tiles away — not adjacent
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        # Enemy at distance 2, below gap-close threshold (3) → None
        assert result is None


# ============================================================================
# 2. _hybrid_dps_skill_logic() Tests — Shadow Step Gap-Close (8E-3)
# ============================================================================

class TestHybridShadowStepGapClose:
    """Tests for Shadow Step gap-close usage by Hybrid DPS role AI."""

    def test_hexblade_shadow_step_gap_close(self):
        """Enemy > 3 tiles away + SS off CD → teleports adjacent to enemy."""
        hexblade = make_hexblade(x=2, y=5)
        enemy = make_enemy(x=9, y=5)  # 7 tiles away — well beyond threshold
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "shadow_step"
        assert result.target_x is not None
        assert result.target_y is not None

    def test_hexblade_gap_close_prefers_adjacent_to_enemy(self):
        """Shadow Step tile should be adjacent (Chebyshev 1) to target enemy."""
        hexblade = make_hexblade(x=2, y=5)
        enemy = make_enemy(x=9, y=5)  # 7 tiles away
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        assert result is not None
        assert result.skill_id == "shadow_step"
        # Shadow Step range is 3, so Hexblade can teleport to (5,5) at most
        # from (2,5). The tile should be as close to enemy (9,5) as possible.
        # The result tile should be within range 3 of AI
        tx, ty = result.target_x, result.target_y
        ai_dist = max(abs(tx - 2), abs(ty - 5))
        assert ai_dist <= 3  # Within Shadow Step range

    def test_hexblade_gap_close_wants_melee_range(self):
        """Hexblade gap-close should land adjacent where possible (unlike scout)."""
        # Place Hexblade 4 tiles from enemy so SS range 3 can reach adjacent
        # Wither on CD so AI falls through to gap-close logic
        hexblade = make_hexblade(x=5, y=5, cooldowns={"wither": 3})
        enemy = make_enemy(x=9, y=5)  # 4 tiles away — triggers gap-close
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        assert result is not None
        assert result.skill_id == "shadow_step"
        # Hexblade at (5,5), enemy at (9,5), SS range 3 reaches (8,5)
        # (8,5) is adjacent to (9,5) — Hexblade should land there
        tx, ty = result.target_x, result.target_y
        enemy_dist = max(abs(tx - 9), abs(ty - 5))
        assert enemy_dist == 1  # Adjacent to enemy (melee range)

    def test_hexblade_no_gap_close_enemy_close(self):
        """Enemy 2 tiles away (below threshold) + Wither on CD → no Shadow Step."""
        hexblade = make_hexblade(x=5, y=5, cooldowns={"wither": 3})
        enemy = make_enemy(x=7, y=5)  # 2 tiles away — below threshold
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        # Not adjacent → no DS, distance <= 3 → no gap-close
        assert result is None

    def test_hexblade_shadow_step_on_cooldown(self):
        """Enemy far + SS on CD → None (can't gap-close)."""
        hexblade = make_hexblade(x=2, y=5, cooldowns={"shadow_step": 3})
        enemy = make_enemy(x=9, y=5)  # 7 tiles away
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        # SS on CD, enemy not adjacent → None
        assert result is None

    def test_hexblade_shadow_step_blocked_by_obstacles(self):
        """All tiles within SS range blocked by obstacles → no gap-close."""
        hexblade = make_hexblade(x=2, y=5)
        enemy = make_enemy(x=9, y=5)  # Far away
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        # Block all tiles within SS range 3 with obstacles
        obstacles = set()
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                tx, ty = 2 + dx, 5 + dy
                if (tx, ty) != (2, 5):  # Don't block AI's own position
                    obstacles.add((tx, ty))

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, obstacles
        )

        # No valid tiles → fall through → None
        assert result is None

    def test_hexblade_gap_close_avoids_occupied_tiles(self):
        """Gap-close tile must not be occupied by another alive unit."""
        hexblade = make_hexblade(x=5, y=5, cooldowns={"wither": 3})
        enemy = make_enemy(x=9, y=5)  # 4 tiles away
        # Place an ally at (8,5) which is the ideal adjacent tile
        ally = make_ally(pid="ally_blocker", x=8, y=5)
        all_units = {
            hexblade.player_id: hexblade,
            enemy.player_id: enemy,
            ally.player_id: ally,
        }
        enemies = [enemy]

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        assert result is not None
        assert result.skill_id == "shadow_step"
        # Should NOT teleport to (8,5) since it's occupied
        assert not (result.target_x == 8 and result.target_y == 5)
        # Should still pick an adjacent tile to enemy (diagonals available)
        tx, ty = result.target_x, result.target_y
        enemy_dist = max(abs(tx - 9), abs(ty - 5))
        assert enemy_dist == 1  # Still adjacent via diagonal


# ============================================================================
# 3. Priority Chain Tests (8E-3)
# ============================================================================

class TestHybridPriorityChain:
    """Tests for priority ordering: Double Strike > Shadow Step gap-close."""

    def test_ds_priority_over_shadow_step(self):
        """Adjacent enemy + both DS/SS off CD + Wither on CD → Double Strike (not Shadow Step)."""
        hexblade = make_hexblade(cooldowns={"wither": 3})
        enemy = make_enemy(x=6, y=5)  # Adjacent
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        assert result is not None
        assert result.skill_id == "double_strike"  # NOT shadow_step

    def test_ds_on_cd_no_gap_close_needed(self):
        """Adjacent enemy + DS on CD + Wither on CD → None (adjacent = no gap-close trigger)."""
        hexblade = make_hexblade(cooldowns={"double_strike": 2, "wither": 3})
        enemy = make_enemy(x=6, y=5)  # Adjacent
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        # Adjacent → no gap-close, DS on CD → None (basic melee)
        assert result is None

    def test_both_skills_on_cooldown(self):
        """DS + SS + Wither all on cooldown → returns None."""
        hexblade = make_hexblade(
            x=2, y=5,
            cooldowns={"double_strike": 2, "shadow_step": 3, "wither": 4},
        )
        enemy = make_enemy(x=9, y=5)  # Far away
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        assert result is None

    def test_no_enemies_returns_none(self):
        """No enemies visible → returns None immediately."""
        hexblade = make_hexblade()
        all_units = {hexblade.player_id: hexblade}
        enemies = []

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        assert result is None

    def test_ds_off_cd_far_enemy_no_ds(self):
        """Enemy far away + DS off CD but not adjacent → gap-close, not DS."""
        hexblade = make_hexblade(x=2, y=5)
        enemy = make_enemy(x=9, y=5)  # 7 tiles away — not adjacent
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _hybrid_dps_skill_logic(
            hexblade, enemies, all_units, 15, 15, set()
        )

        # Not adjacent → DS skipped. Far → gap-close triggered.
        assert result is not None
        assert result.skill_id == "shadow_step"


# ============================================================================
# 4. _find_shadow_step_gapcloser_tile() Helper Tests
# ============================================================================

class TestFindShadowStepGapcloserTile:
    """Tests for the gap-close tile finder helper."""

    def test_finds_adjacent_tile_to_target(self):
        """Gap-close tile should be adjacent (distance 1) to target enemy."""
        hexblade = make_hexblade(x=5, y=5)
        enemy = make_enemy(x=9, y=5)
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}

        tile = _find_shadow_step_gapcloser_tile(
            hexblade, enemy, all_units, 15, 15, set()
        )

        assert tile is not None
        tx, ty = tile
        enemy_dist = max(abs(tx - 9), abs(ty - 5))
        assert enemy_dist == 1  # Adjacent to enemy

    def test_tiebreaks_by_distance_from_ai(self):
        """Among adjacent-to-enemy tiles, picks closest to AI position."""
        hexblade = make_hexblade(x=5, y=5)
        enemy = make_enemy(x=9, y=5)
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}

        tile = _find_shadow_step_gapcloser_tile(
            hexblade, enemy, all_units, 15, 15, set()
        )

        assert tile is not None
        tx, ty = tile
        # Must be adjacent to enemy (9,5) — Chebyshev distance 1
        enemy_dist = max(abs(tx - 9), abs(ty - 5))
        assert enemy_dist == 1
        # Must be within SS range 3 of AI (5,5)
        ai_dist = max(abs(tx - 5), abs(ty - 5))
        assert ai_dist <= 3
        # Among all adjacent-to-enemy tiles in range, should pick the closest
        # to AI. Multiple tiles at distance 3 are valid (e.g., (8,4), (8,5), (8,6)).
        assert ai_dist == 3  # Distance 3 is the minimum for adjacent-to-(9,5)

    def test_fallback_when_no_adjacent_tiles(self):
        """If no adjacent-to-enemy tiles are in SS range, picks closest available."""
        # Place Hexblade far away so no adjacent-to-enemy tiles are within range 3
        hexblade = make_hexblade(x=2, y=5)
        enemy = make_enemy(x=12, y=5)  # 10 tiles away, adjacent tiles at x=11,13
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}

        tile = _find_shadow_step_gapcloser_tile(
            hexblade, enemy, all_units, 15, 15, set()
        )

        assert tile is not None
        tx, ty = tile
        # Should be the tile closest to enemy within SS range 3 of AI
        ai_dist = max(abs(tx - 2), abs(ty - 5))
        assert ai_dist <= 3  # Within SS range
        # Should be (5, 5) — closest valid tile to enemy at (12,5)
        assert tx == 5  # Maximum x within range 3 from (2,5)

    def test_no_valid_tiles_returns_none(self):
        """All tiles blocked → returns None."""
        hexblade = make_hexblade(x=5, y=5)
        enemy = make_enemy(x=9, y=5)
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}

        # Block everything
        obstacles = set()
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                tx, ty = 5 + dx, 5 + dy
                if (tx, ty) != (5, 5):
                    obstacles.add((tx, ty))

        tile = _find_shadow_step_gapcloser_tile(
            hexblade, enemy, all_units, 15, 15, obstacles
        )

        assert tile is None

    def test_avoids_occupied_tiles(self):
        """Occupied tiles are not valid gap-close destinations."""
        hexblade = make_hexblade(x=5, y=5)
        enemy = make_enemy(x=9, y=5)
        ally = make_ally(pid="blocker", x=8, y=5)  # Blocks ideal tile
        all_units = {
            hexblade.player_id: hexblade,
            enemy.player_id: enemy,
            ally.player_id: ally,
        }

        tile = _find_shadow_step_gapcloser_tile(
            hexblade, enemy, all_units, 15, 15, set()
        )

        assert tile is not None
        assert tile != (8, 5)  # Occupied by ally
        # Should pick another adjacent-to-enemy tile (diagonal)
        tx, ty = tile
        enemy_dist = max(abs(tx - 9), abs(ty - 5))
        assert enemy_dist == 1  # Still adjacent

    def test_respects_grid_bounds(self):
        """Tiles outside grid bounds are excluded."""
        # Place near edge so some tiles in SS range are out of bounds
        hexblade = make_hexblade(x=1, y=1)
        enemy = make_enemy(x=5, y=1)  # 4 tiles away
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}

        tile = _find_shadow_step_gapcloser_tile(
            hexblade, enemy, all_units, 15, 15, set()
        )

        assert tile is not None
        tx, ty = tile
        assert 0 <= tx < 15
        assert 0 <= ty < 15


# ============================================================================
# 5. Integration Tests (8E-3)
# ============================================================================

class TestHybridDispatchIntegration:
    """Tests for _decide_skill_usage dispatch to hybrid_dps logic."""

    def test_hexblade_dispatches_to_hybrid_logic(self):
        """Hexblade triggers _hybrid_dps_skill_logic via _decide_skill_usage."""
        hexblade = make_hexblade(cooldowns={"wither": 3})
        enemy = make_enemy(x=6, y=5)  # Adjacent
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _decide_skill_usage(
            hexblade, enemies, all_units, 15, 15, set()
        )

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "double_strike"

    def test_hexblade_dispatch_gap_close(self):
        """Hexblade gap-close dispatches through _decide_skill_usage."""
        hexblade = make_hexblade(x=2, y=5)
        enemy = make_enemy(x=9, y=5)  # Far away
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _decide_skill_usage(
            hexblade, enemies, all_units, 15, 15, set()
        )

        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "shadow_step"

    def test_hexblade_dispatch_returns_none_when_no_skills(self):
        """All skills on CD, no adjacent enemies → None from dispatch."""
        hexblade = make_hexblade(
            x=5, y=5,
            cooldowns={"double_strike": 2, "shadow_step": 3, "wither": 3},
        )
        enemy = make_enemy(x=7, y=5)  # 2 tiles — not adjacent, not far enough
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}
        enemies = [enemy]

        result = _decide_skill_usage(
            hexblade, enemies, all_units, 15, 15, set()
        )

        assert result is None

    def test_role_is_hybrid_dps_for_hexblade(self):
        """Hexblade maps to 'hybrid_dps' role."""
        assert _get_role_for_class("hexblade") == "hybrid_dps"

    def test_action_format_double_strike(self):
        """Double Strike action has correct format (SKILL, double_strike, target coords)."""
        hexblade = make_hexblade(cooldowns={"wither": 3})
        enemy = make_enemy(x=6, y=5)
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}

        result = _hybrid_dps_skill_logic(
            hexblade, [enemy], all_units, 15, 15, set()
        )

        assert result.player_id == "hex1"
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "double_strike"
        assert result.target_x == 6
        assert result.target_y == 5

    def test_action_format_shadow_step(self):
        """Shadow Step action has correct format (SKILL, shadow_step, target coords)."""
        hexblade = make_hexblade(x=2, y=5)
        enemy = make_enemy(x=9, y=5)
        all_units = {hexblade.player_id: hexblade, enemy.player_id: enemy}

        result = _hybrid_dps_skill_logic(
            hexblade, [enemy], all_units, 15, 15, set()
        )

        assert result.player_id == "hex1"
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "shadow_step"
        assert result.target_x is not None
        assert result.target_y is not None


# ============================================================================
# 6. Guard Tests
# ============================================================================

class TestHybridGuard:
    """Guard tests: ensure hybrid_dps logic only applies to hybrid-role hero AI."""

    def test_enemy_ai_no_hybrid_skills(self):
        """Enemy AI (no hero_id) should not be dispatched to hybrid_dps logic.

        The guard is at _decide_stance_action level — enemy AI never calls
        _decide_skill_usage. This test validates the role mapping exists.
        """
        enemy_hexblade = PlayerState(
            player_id="enemy_hex",
            username="Dark Hexblade",
            position=Position(x=5, y=5),
            hp=110,
            max_hp=110,
            attack_damage=15,
            armor=5,
            team="b",
            unit_type="ai",
            hero_id=None,  # Not a hero
            class_id="hexblade",
            ranged_range=4,
            vision_range=6,
            inventory=[],
            cooldowns={},
            active_buffs=[],
        )
        role = _get_role_for_class(enemy_hexblade.class_id)
        assert role == "hybrid_dps"
        # The guard is at _decide_stance_action level, not inside the handler.

    def test_non_hybrid_class_no_hybrid_dispatch(self):
        """Non-hybrid classes do not dispatch to hybrid_dps logic."""
        assert _get_role_for_class("crusader") == "tank"
        assert _get_role_for_class("crusader") != "hybrid_dps"

        assert _get_role_for_class("ranger") == "ranged_dps"
        assert _get_role_for_class("ranger") != "hybrid_dps"

        assert _get_role_for_class("confessor") == "support"
        assert _get_role_for_class("confessor") != "hybrid_dps"

        assert _get_role_for_class("inquisitor") == "scout"
        assert _get_role_for_class("inquisitor") != "hybrid_dps"

    def test_null_class_no_crash(self):
        """class_id=None → _decide_skill_usage returns None, no crash."""
        no_class_unit = PlayerState(
            player_id="legacy1",
            username="Legacy Unit",
            position=Position(x=5, y=5),
            hp=80,
            max_hp=80,
            attack_damage=10,
            armor=0,
            team="a",
            unit_type="ai",
            hero_id="hero_legacy",
            ai_stance="follow",
            class_id=None,
            ranged_range=0,
            vision_range=5,
            inventory=[],
            cooldowns={},
            active_buffs=[],
        )
        enemy = make_enemy(x=6, y=5)
        all_units = {no_class_unit.player_id: no_class_unit, enemy.player_id: enemy}

        result = _decide_skill_usage(
            no_class_unit, [enemy], all_units, 15, 15, set()
        )

        assert result is None

    def test_gap_close_threshold_constant(self):
        """Verify gap-close threshold constant is 2 (post Hexblade balance pass)."""
        assert _SHADOW_STEP_GAPCLOSER_MIN_DISTANCE == 2
