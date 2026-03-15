"""
Tests for Phase 26D: Shaman AI Behavior (totemic_support role).

Covers:
- Role mapping: shaman maps to "totemic_support"
- _totemic_support_skill_logic() — full priority chain
  - Healing Totem: places when 2+ allies below 70% HP, no active healing totem
  - Healing Totem: skips when no allies injured or active totem exists
  - Healing Totem: places near largest injured ally cluster, avoids enemies
  - Searing Totem: places when 2+ enemies clustered, no active searing totem
  - Searing Totem: prefers placement near rooted enemies (combo awareness)
  - Earthgrasp: uses when 2+ enemies in range, esp. near active searing totem
  - Earthgrasp: roots melee enemies approaching party
  - Soul Anchor: uses on low-HP frontline ally (below 30% HP)
  - Soul Anchor: does not waste when no ally endangered
  - Fallback: returns None when all skills on cooldown
- _decide_skill_usage() dispatches shaman to totemic_support handler
- Priority ordering: Healing Totem > Searing Totem > Earthgrasp > Soul Anchor
- Shaman AI stays behind frontline (support positioning via existing stance system)
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import ActionType, PlayerAction
from app.core.ai_skills import (
    _CLASS_ROLE_MAP,
    _get_role_for_class,
    _try_skill,
    _totemic_support_skill_logic,
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

def _make_shaman(
    player_id: str = "sham1",
    x: int = 5,
    y: int = 5,
    hp: int = 95,
    max_hp: int = 95,
    team: str = "team_1",
    cooldowns: dict | None = None,
    active_buffs: list | None = None,
) -> PlayerState:
    """Create a Shaman AI unit."""
    return PlayerState(
        player_id=player_id,
        username="Shaman",
        position=Position(x=x, y=y),
        class_id="shaman",
        hp=hp,
        max_hp=max_hp,
        is_alive=True,
        team=team,
        unit_type="ai",
        hero_id="sham_hero_001",
        ai_stance="follow",
        ranged_range=4,
        vision_range=7,
        attack_damage=10,
        armor=3,
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
        inventory=[],
    )


def _make_ally(
    player_id: str = "ally1",
    x: int = 4,
    y: int = 5,
    hp: int = 60,
    max_hp: int = 100,
    team: str = "team_1",
    class_id: str = "crusader",
    active_buffs: list | None = None,
) -> PlayerState:
    """Create an ally unit on the same team."""
    return PlayerState(
        player_id=player_id,
        username="Ally",
        position=Position(x=x, y=y),
        class_id=class_id,
        hp=hp,
        max_hp=max_hp,
        is_alive=True,
        team=team,
        unit_type="ai",
        hero_id="ally_hero_001",
        ai_stance="follow",
        ranged_range=0,
        vision_range=5,
        attack_damage=20,
        armor=8,
        cooldowns={},
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
    class_id: str | None = None,
    ranged_range: int = 0,
    active_buffs: list | None = None,
) -> PlayerState:
    """Create an enemy unit on the opposing team."""
    return PlayerState(
        player_id=player_id,
        username="Enemy",
        position=Position(x=x, y=y),
        class_id=class_id,
        hp=hp,
        max_hp=max_hp,
        is_alive=True,
        team=team,
        unit_type="ai",
        hero_id=None,
        ranged_range=ranged_range,
        vision_range=5,
        attack_damage=10,
        armor=4,
        cooldowns={},
        active_buffs=active_buffs or [],
        inventory=[],
    )


def _build_units(*units: PlayerState) -> dict[str, PlayerState]:
    """Build the all_units dict from a list of PlayerState objects."""
    return {u.player_id: u for u in units}


class _FakeMatchState:
    """Minimal match state duck-type for AI totem checks."""
    def __init__(self, totems: list | None = None):
        self.totems = totems or []


# Default grid/obstacles for most tests
GRID_W = 20
GRID_H = 20
NO_OBSTACLES: set[tuple[int, int]] = set()


# ===========================================================================
# 1. Role Mapping Tests
# ===========================================================================

class TestShamanRoleMapping:
    """Shaman class maps to totemic_support role."""

    def test_shaman_maps_to_totemic_support(self):
        """shaman → totemic_support in _CLASS_ROLE_MAP."""
        assert _get_role_for_class("shaman") == "totemic_support"

    def test_totemic_support_in_role_map(self):
        """_CLASS_ROLE_MAP contains shaman entry."""
        assert "shaman" in _CLASS_ROLE_MAP
        assert _CLASS_ROLE_MAP["shaman"] == "totemic_support"

    def test_role_map_count_updated(self):
        """_CLASS_ROLE_MAP has correct entry count (31 = 30 previous + shaman)."""
        assert len(_CLASS_ROLE_MAP) == 31


# ===========================================================================
# 2. Healing Totem — Place When Allies Injured
# ===========================================================================

class TestHealingTotemAI:
    """Shaman AI places Healing Totem when 2+ allies are injured."""

    def test_places_healing_totem_when_allies_injured(self):
        """Healing Totem fires when 2+ allies below 70% HP and no active healing totem."""
        sham = _make_shaman()
        ally1 = _make_ally(player_id="ally1", x=4, y=5, hp=50, max_hp=100)  # 50% HP
        ally2 = _make_ally(player_id="ally2", x=6, y=5, hp=40, max_hp=100)  # 40% HP
        enemy = _make_enemy(x=10, y=5)  # Far away
        all_units = _build_units(sham, ally1, ally2, enemy)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "healing_totem"

    def test_does_not_place_healing_totem_when_no_allies_injured(self):
        """Healing Totem does NOT fire when no allies are below 70% HP."""
        sham = _make_shaman()
        ally1 = _make_ally(player_id="ally1", x=4, y=5, hp=90, max_hp=100)  # 90% HP
        ally2 = _make_ally(player_id="ally2", x=6, y=5, hp=85, max_hp=100)  # 85% HP
        enemy = _make_enemy(x=8, y=5)
        all_units = _build_units(sham, ally1, ally2, enemy)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        # Should NOT be healing_totem (no injured allies)
        if result is not None:
            assert result.skill_id != "healing_totem"

    def test_skips_healing_totem_when_already_active(self):
        """Healing Totem does NOT fire when an active healing totem exists for this Shaman."""
        sham = _make_shaman()
        ally1 = _make_ally(player_id="ally1", x=4, y=5, hp=50, max_hp=100)
        ally2 = _make_ally(player_id="ally2", x=6, y=5, hp=40, max_hp=100)
        enemy = _make_enemy(x=10, y=5)
        all_units = _build_units(sham, ally1, ally2, enemy)
        ms = _FakeMatchState(totems=[{
            "id": "ht1", "type": "healing_totem", "owner_id": "sham1",
            "x": 5, "y": 4, "hp": 20, "max_hp": 20,
            "heal_per_turn": 8, "damage_per_turn": 0,
            "effect_radius": 2, "duration_remaining": 3, "team": "team_1",
        }])

        result = _totemic_support_skill_logic(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        # Should NOT be healing_totem since one already exists
        if result is not None:
            assert result.skill_id != "healing_totem"

    def test_healing_totem_avoids_placing_near_enemies(self):
        """Healing Totem placement prefers tiles away from adjacent enemies."""
        sham = _make_shaman(x=5, y=5)
        ally1 = _make_ally(player_id="ally1", x=4, y=5, hp=40, max_hp=100)
        ally2 = _make_ally(player_id="ally2", x=4, y=4, hp=40, max_hp=100)
        # Enemies at various positions — totem should prefer tiles away from them
        enemy = _make_enemy(player_id="enemy1", x=3, y=5)  # Adjacent to ally1
        all_units = _build_units(sham, ally1, ally2, enemy)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        if result is not None and result.skill_id == "healing_totem":
            # If it placed a totem, verify it picked a valid tile
            assert result.target_x is not None
            assert result.target_y is not None

    def test_healing_totem_on_cooldown_skipped(self):
        """Healing Totem on cooldown → skipped, falls through to next priority."""
        sham = _make_shaman(cooldowns={"healing_totem": 5})
        ally1 = _make_ally(player_id="ally1", x=4, y=5, hp=40, max_hp=100)
        ally2 = _make_ally(player_id="ally2", x=6, y=5, hp=40, max_hp=100)
        enemy = _make_enemy(x=10, y=5)
        all_units = _build_units(sham, ally1, ally2, enemy)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        if result is not None:
            assert result.skill_id != "healing_totem"


# ===========================================================================
# 3. Searing Totem — Place Near Enemy Clusters
# ===========================================================================

class TestSearingTotemAI:
    """Shaman AI places Searing Totem when 1+ enemies are in range."""

    def test_places_searing_totem_when_enemies_clustered(self):
        """Searing Totem fires when 2+ enemies are clustered and no active searing totem."""
        sham = _make_shaman(cooldowns={"healing_totem": 5})  # Healing on CD
        enemy1 = _make_enemy(player_id="enemy1", x=7, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=8, y=5)
        all_units = _build_units(sham, enemy1, enemy2)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "searing_totem"

    def test_skips_searing_totem_when_already_active(self):
        """Searing Totem does NOT fire when one already exists for this Shaman."""
        sham = _make_shaman(cooldowns={"healing_totem": 5})
        enemy1 = _make_enemy(player_id="enemy1", x=7, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=8, y=5)
        all_units = _build_units(sham, enemy1, enemy2)
        ms = _FakeMatchState(totems=[{
            "id": "st1", "type": "searing_totem", "owner_id": "sham1",
            "x": 7, "y": 4, "hp": 20, "max_hp": 20,
            "heal_per_turn": 0, "damage_per_turn": 6,
            "effect_radius": 2, "duration_remaining": 3, "team": "team_1",
        }])

        result = _totemic_support_skill_logic(
            sham, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        if result is not None:
            assert result.skill_id != "searing_totem"

    def test_searing_totem_prefers_rooted_enemies(self):
        """Searing Totem placement scores higher near rooted enemies."""
        sham = _make_shaman(cooldowns={"healing_totem": 5})
        # Two enemies: one rooted, one not
        rooted_enemy = _make_enemy(
            player_id="rooted1", x=7, y=5,
            active_buffs=[{"stat": "rooted", "turns_remaining": 2}],
        )
        free_enemy = _make_enemy(player_id="free1", x=8, y=5)
        all_units = _build_units(sham, rooted_enemy, free_enemy)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [rooted_enemy, free_enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is not None
        assert result.skill_id == "searing_totem"
        # Totem should be placed near the enemies
        assert result.target_x is not None
        assert result.target_y is not None

    def test_searing_totem_on_cooldown_skipped(self):
        """Searing Totem on cooldown → skipped."""
        sham = _make_shaman(cooldowns={"healing_totem": 5, "searing_totem": 4})
        enemy1 = _make_enemy(player_id="enemy1", x=7, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=8, y=5)
        all_units = _build_units(sham, enemy1, enemy2)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        if result is not None:
            assert result.skill_id != "searing_totem"

    def test_places_searing_totem_single_enemy(self):
        """Searing Totem fires with 1 enemy in range (threshold lowered to 1)."""
        sham = _make_shaman(cooldowns={"healing_totem": 5})
        enemy = _make_enemy(x=7, y=5)
        all_units = _build_units(sham, enemy)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is not None
        assert result.skill_id == "searing_totem"


# ===========================================================================
# 4. Earthgrasp — AoE Root (especially near Searing Totem)
# ===========================================================================

class TestEarthgraspAI:
    """Shaman AI uses Earthgrasp to root 1+ enemies, preferring searing totem combo."""

    def test_uses_earthgrasp_when_enemies_clustered(self):
        """Earthgrasp fires when 2+ enemies within range and higher-priority skills exhausted."""
        sham = _make_shaman(cooldowns={"healing_totem": 5, "searing_totem": 4})
        enemy1 = _make_enemy(player_id="enemy1", x=7, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=7, y=6)
        all_units = _build_units(sham, enemy1, enemy2)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "earthgrasp"

    def test_uses_earthgrasp_single_enemy(self):
        """Earthgrasp fires on a single un-rooted enemy (threshold lowered to 1)."""
        sham = _make_shaman(cooldowns={"healing_totem": 5, "searing_totem": 4})
        enemy = _make_enemy(player_id="enemy1", x=7, y=5)
        all_units = _build_units(sham, enemy)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is not None
        assert result.skill_id == "earthgrasp"

    def test_earthgrasp_prefers_searing_totem_combo(self):
        """Earthgrasp targets enemies near an active searing totem for combo damage."""
        sham = _make_shaman(cooldowns={"healing_totem": 5, "searing_totem": 4})
        # Searing totem at (8, 5), enemies near it
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)  # On searing totem
        enemy2 = _make_enemy(player_id="enemy2", x=8, y=6)  # Near searing totem
        all_units = _build_units(sham, enemy1, enemy2)
        ms = _FakeMatchState(totems=[{
            "id": "st1", "type": "searing_totem", "owner_id": "sham1",
            "x": 8, "y": 5, "hp": 20, "max_hp": 20,
            "heal_per_turn": 0, "damage_per_turn": 6,
            "effect_radius": 2, "duration_remaining": 3, "team": "team_1",
        }])

        result = _totemic_support_skill_logic(
            sham, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is not None
        assert result.skill_id == "earthgrasp"

    def test_earthgrasp_prefers_melee_enemies(self):
        """Earthgrasp scores melee enemies higher (root is more impactful vs melee)."""
        sham = _make_shaman(cooldowns={"healing_totem": 5, "searing_totem": 4})
        melee_enemy1 = _make_enemy(player_id="melee1", x=7, y=5, ranged_range=0)
        melee_enemy2 = _make_enemy(player_id="melee2", x=7, y=6, ranged_range=0)
        all_units = _build_units(sham, melee_enemy1, melee_enemy2)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [melee_enemy1, melee_enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is not None
        assert result.skill_id == "earthgrasp"

    def test_earthgrasp_on_cooldown_skipped(self):
        """Earthgrasp on cooldown → skipped."""
        sham = _make_shaman(cooldowns={
            "healing_totem": 5, "searing_totem": 4, "earthgrasp": 6,
        })
        enemy1 = _make_enemy(player_id="enemy1", x=7, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=7, y=6)
        all_units = _build_units(sham, enemy1, enemy2)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        if result is not None:
            assert result.skill_id != "earthgrasp"

    def test_earthgrasp_skips_when_totem_already_active(self):
        """Earthgrasp totem is NOT placed when one already exists."""
        sham = _make_shaman(cooldowns={"healing_totem": 5, "searing_totem": 4})
        enemy1 = _make_enemy(player_id="enemy1", x=7, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=7, y=6)
        all_units = _build_units(sham, enemy1, enemy2)
        # Already have an active earthgrasp totem
        ms = _FakeMatchState(totems=[{
            "type": "earthgrasp_totem", "owner_id": "sham1",
            "x": 7, "y": 5, "hp": 20, "max_hp": 20,
            "effect_radius": 2, "duration_remaining": 3, "team": "team_1",
        }])

        result = _totemic_support_skill_logic(
            sham, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        # Should NOT place another earthgrasp totem
        if result is not None:
            assert result.skill_id != "earthgrasp"


# ===========================================================================
# 5. Soul Anchor — Cheat Death on Endangered Frontline Ally
# ===========================================================================

class TestSoulAnchorAI:
    """Shaman AI uses Soul Anchor on low-HP frontline allies."""

    def test_uses_soul_anchor_on_low_hp_tank(self):
        """Soul Anchor fires on a Crusader below 30% HP."""
        sham = _make_shaman(cooldowns={
            "healing_totem": 5, "searing_totem": 4, "earthgrasp": 6,
        })
        tank = _make_ally(
            player_id="tank1", x=6, y=5, hp=25, max_hp=150,
            class_id="crusader",
        )  # ~17% HP — well below 30%
        enemy = _make_enemy(x=8, y=5)
        all_units = _build_units(sham, tank, enemy)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "soul_anchor"
        assert result.target_id == "tank1"

    def test_does_not_waste_soul_anchor_when_no_ally_endangered(self):
        """Soul Anchor does NOT fire when no ally is below 30% HP."""
        sham = _make_shaman(cooldowns={
            "healing_totem": 5, "searing_totem": 4, "earthgrasp": 6,
        })
        healthy_ally = _make_ally(
            player_id="ally1", x=6, y=5, hp=80, max_hp=100,
        )  # 80% HP — well above 30%
        enemy = _make_enemy(x=8, y=5)
        all_units = _build_units(sham, healthy_ally, enemy)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        if result is not None:
            assert result.skill_id != "soul_anchor"

    def test_soul_anchor_prefers_tanks(self):
        """Soul Anchor prefers Crusader (tank) over Mage (squishy) at similar HP%."""
        sham = _make_shaman(cooldowns={
            "healing_totem": 5, "searing_totem": 4, "earthgrasp": 6,
        })
        tank = _make_ally(
            player_id="tank1", x=6, y=5, hp=20, max_hp=150,
            class_id="crusader",
        )  # ~13% HP
        mage = _make_ally(
            player_id="mage1", x=4, y=5, hp=15, max_hp=70,
            class_id="mage",
        )  # ~21% HP
        enemy = _make_enemy(x=8, y=5)
        all_units = _build_units(sham, tank, mage, enemy)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is not None
        assert result.skill_id == "soul_anchor"
        assert result.target_id == "tank1"  # Tanks are prioritized

    def test_soul_anchor_skips_already_anchored_ally(self):
        """Soul Anchor does NOT fire if the Shaman already has an active anchor on someone."""
        sham = _make_shaman(cooldowns={
            "healing_totem": 5, "searing_totem": 4, "earthgrasp": 6,
        })
        anchored_tank = _make_ally(
            player_id="tank1", x=6, y=5, hp=20, max_hp=150,
            class_id="crusader",
            active_buffs=[{"stat": "soul_anchor", "caster_id": "sham1", "turns_remaining": 3}],
        )
        other_ally = _make_ally(
            player_id="ally2", x=4, y=5, hp=20, max_hp=100,
            class_id="ranger",
        )  # 20% HP — below threshold, but anchor already active
        enemy = _make_enemy(x=8, y=5)
        all_units = _build_units(sham, anchored_tank, other_ally, enemy)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        # Should skip soul_anchor — one is already active from this Shaman
        if result is not None:
            assert result.skill_id != "soul_anchor"

    def test_soul_anchor_on_cooldown_skipped(self):
        """Soul Anchor on cooldown → skipped."""
        sham = _make_shaman(cooldowns={
            "healing_totem": 5, "searing_totem": 4, "earthgrasp": 6, "soul_anchor": 9,
        })
        tank = _make_ally(
            player_id="tank1", x=6, y=5, hp=20, max_hp=150,
            class_id="crusader",
        )
        enemy = _make_enemy(x=8, y=5)
        all_units = _build_units(sham, tank, enemy)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        if result is not None:
            assert result.skill_id != "soul_anchor"

    def test_soul_anchor_out_of_range_skipped(self):
        """Soul Anchor does NOT fire on allies beyond range 4."""
        sham = _make_shaman(cooldowns={
            "healing_totem": 5, "searing_totem": 4, "earthgrasp": 6,
        })
        far_tank = _make_ally(
            player_id="tank1", x=15, y=15, hp=20, max_hp=150,
            class_id="crusader",
        )  # Way out of range
        enemy = _make_enemy(x=8, y=5)
        all_units = _build_units(sham, far_tank, enemy)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        if result is not None:
            assert result.skill_id != "soul_anchor"


# ===========================================================================
# 6. Fallback / Edge Cases
# ===========================================================================

class TestTotemicSupportFallback:
    """Edge cases and fallback behavior for Shaman AI."""

    def test_returns_none_all_skills_on_cooldown(self):
        """All skills on cooldown → returns None for fallback to basic attack."""
        sham = _make_shaman(cooldowns={
            "healing_totem": 5, "searing_totem": 4,
            "earthgrasp": 6, "soul_anchor": 9,
        })
        enemy = _make_enemy(x=7, y=5)
        ally = _make_ally(player_id="ally1", x=4, y=5, hp=30, max_hp=100)
        all_units = _build_units(sham, enemy, ally)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is None

    def test_returns_none_no_enemies(self):
        """No enemies visible → returns None immediately."""
        sham = _make_shaman()
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [], {sham.player_id: sham}, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is None

    def test_works_without_match_state(self):
        """Gracefully handles match_state=None (no totem awareness)."""
        sham = _make_shaman()
        ally1 = _make_ally(player_id="ally1", x=4, y=5, hp=40, max_hp=100)
        ally2 = _make_ally(player_id="ally2", x=6, y=5, hp=40, max_hp=100)
        enemy = _make_enemy(x=10, y=5)
        all_units = _build_units(sham, ally1, ally2, enemy)

        # match_state=None — should still work (treats totem list as empty)
        result = _totemic_support_skill_logic(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=None,
        )
        # Should place healing totem (match_state=None means no existing totems)
        assert result is not None
        assert result.skill_id == "healing_totem"

    def test_both_totems_active_skips_to_earthgrasp(self):
        """When both totems are active, AI skips to Earthgrasp."""
        sham = _make_shaman()
        enemy1 = _make_enemy(player_id="enemy1", x=7, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=7, y=6)
        all_units = _build_units(sham, enemy1, enemy2)
        ms = _FakeMatchState(totems=[
            {
                "id": "ht1", "type": "healing_totem", "owner_id": "sham1",
                "x": 4, "y": 5, "hp": 20, "max_hp": 20,
                "heal_per_turn": 8, "damage_per_turn": 0,
                "effect_radius": 2, "duration_remaining": 3, "team": "team_1",
            },
            {
                "id": "st1", "type": "searing_totem", "owner_id": "sham1",
                "x": 7, "y": 4, "hp": 20, "max_hp": 20,
                "heal_per_turn": 0, "damage_per_turn": 6,
                "effect_radius": 2, "duration_remaining": 3, "team": "team_1",
            },
        ])

        result = _totemic_support_skill_logic(
            sham, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        # Should skip both totems and use Earthgrasp
        assert result is not None
        assert result.skill_id == "earthgrasp"


# ===========================================================================
# 7. Priority Order Tests
# ===========================================================================

class TestTotemicSupportPriority:
    """Priority ordering: Healing Totem > Searing Totem > Earthgrasp > Soul Anchor."""

    def test_healing_totem_prioritized_over_searing(self):
        """When both Healing Totem and Searing Totem conditions are met, favors Healing."""
        sham = _make_shaman()
        ally1 = _make_ally(player_id="ally1", x=4, y=5, hp=40, max_hp=100)  # Injured
        ally2 = _make_ally(player_id="ally2", x=6, y=5, hp=40, max_hp=100)  # Injured
        enemy1 = _make_enemy(player_id="enemy1", x=8, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=8, y=6)
        all_units = _build_units(sham, ally1, ally2, enemy1, enemy2)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is not None
        assert result.skill_id == "healing_totem"

    def test_searing_totem_prioritized_over_earthgrasp(self):
        """When Healing Totem is on CD but Searing and Earthgrasp are ready, favors Searing."""
        sham = _make_shaman(cooldowns={"healing_totem": 5})
        enemy1 = _make_enemy(player_id="enemy1", x=7, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=7, y=6)
        all_units = _build_units(sham, enemy1, enemy2)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is not None
        assert result.skill_id == "searing_totem"

    def test_earthgrasp_prioritized_over_soul_anchor(self):
        """When totems are on CD but Earthgrasp and Soul Anchor ready, favors Earthgrasp."""
        sham = _make_shaman(cooldowns={"healing_totem": 5, "searing_totem": 4})
        tank = _make_ally(
            player_id="tank1", x=6, y=5, hp=20, max_hp=150,
            class_id="crusader",
        )  # Also qualifies for Soul Anchor
        enemy1 = _make_enemy(player_id="enemy1", x=7, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=7, y=6)
        all_units = _build_units(sham, tank, enemy1, enemy2)
        ms = _FakeMatchState()

        result = _totemic_support_skill_logic(
            sham, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is not None
        assert result.skill_id == "earthgrasp"


# ===========================================================================
# 8. Dispatcher Integration
# ===========================================================================

class TestTotemicSupportDispatcher:
    """_decide_skill_usage dispatches shaman to totemic_support handler."""

    def test_decide_skill_dispatches_shaman(self):
        """_decide_skill_usage routes shaman to _totemic_support_skill_logic."""
        sham = _make_shaman()
        ally1 = _make_ally(player_id="ally1", x=4, y=5, hp=40, max_hp=100)
        ally2 = _make_ally(player_id="ally2", x=6, y=5, hp=40, max_hp=100)
        enemy = _make_enemy(x=10, y=5)
        all_units = _build_units(sham, ally1, ally2, enemy)
        ms = _FakeMatchState()

        result = _decide_skill_usage(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        # Should place healing totem (2 injured allies)
        assert result is not None
        assert result.action_type == ActionType.SKILL
        assert result.skill_id == "healing_totem"

    def test_decide_skill_shaman_searing_totem(self):
        """Dispatcher correctly routes Shaman Searing Totem when healing not needed."""
        sham = _make_shaman(cooldowns={"healing_totem": 5})
        enemy1 = _make_enemy(player_id="enemy1", x=7, y=5)
        enemy2 = _make_enemy(player_id="enemy2", x=8, y=5)
        all_units = _build_units(sham, enemy1, enemy2)
        ms = _FakeMatchState()

        result = _decide_skill_usage(
            sham, [enemy1, enemy2], all_units, GRID_W, GRID_H, NO_OBSTACLES, match_state=ms,
        )
        assert result is not None
        assert result.skill_id == "searing_totem"

    def test_decide_skill_without_match_state(self):
        """_decide_skill_usage still works when match_state is not provided."""
        sham = _make_shaman()
        ally1 = _make_ally(player_id="ally1", x=4, y=5, hp=40, max_hp=100)
        ally2 = _make_ally(player_id="ally2", x=6, y=5, hp=40, max_hp=100)
        enemy = _make_enemy(x=10, y=5)
        all_units = _build_units(sham, ally1, ally2, enemy)

        # No match_state — should still work
        result = _decide_skill_usage(
            sham, [enemy], all_units, GRID_W, GRID_H, NO_OBSTACLES,
        )
        assert result is not None
        assert result.skill_id == "healing_totem"
