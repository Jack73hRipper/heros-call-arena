"""
Tests for Phase 23B: Plague Doctor Effect Handlers.

Covers:
- resolve_aoe_damage_slow_targeted() — Miasma (ground-targeted AoE damage + slow)
- resolve_dot() — Plague Flask (single-target DoT via existing handler)
- resolve_aoe_debuff() — Enfeeble (AoE damage_dealt_multiplier debuff via existing handler)
- resolve_buff_cleanse() — Inoculate (ally buff + DoT cleanse)
- resolve_skill_action() dispatcher routing for new effect types
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import ActionResult, ActionType, PlayerAction
from app.core.skills import (
    load_skills_config,
    clear_skills_cache,
    get_skill,
    resolve_aoe_damage_slow_targeted,
    resolve_buff_cleanse,
    resolve_dot,
    resolve_aoe_debuff,
    resolve_skill_action,
)


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def _reset_caches():
    """Clear cached configs before each test to ensure isolation."""
    clear_skills_cache()
    import app.models.player as player_mod
    player_mod._classes_cache = None
    yield
    clear_skills_cache()
    player_mod._classes_cache = None


@pytest.fixture
def loaded_skills() -> dict:
    """Load and return the skills config dict."""
    return load_skills_config()


def _make_player(
    player_id: str = "pd1",
    username: str = "PlagueDoc",
    class_id: str = "plague_doctor",
    hp: int = 85,
    max_hp: int = 85,
    attack_damage: int = 8,
    ranged_damage: int = 12,
    armor: int = 2,
    team: str = "team_1",
    x: int = 5,
    y: int = 5,
    alive: bool = True,
    cooldowns: dict | None = None,
    active_buffs: list | None = None,
) -> PlayerState:
    """Helper — create a Plague Doctor PlayerState."""
    p = PlayerState(
        player_id=player_id,
        username=username,
        position=Position(x=x, y=y),
        class_id=class_id,
        hp=hp,
        max_hp=max_hp,
        attack_damage=attack_damage,
        ranged_damage=ranged_damage,
        armor=armor,
        is_alive=alive,
        cooldowns=cooldowns or {},
        team=team,
        active_buffs=active_buffs or [],
    )
    return p


def _make_enemy(
    player_id: str = "enemy1",
    username: str = "Skeleton",
    hp: int = 50,
    max_hp: int = 50,
    armor: int = 4,
    team: str = "team_2",
    x: int = 7,
    y: int = 5,
    alive: bool = True,
    active_buffs: list | None = None,
) -> PlayerState:
    """Helper — create an enemy PlayerState."""
    return PlayerState(
        player_id=player_id,
        username=username,
        position=Position(x=x, y=y),
        class_id="crusader",
        hp=hp,
        max_hp=max_hp,
        attack_damage=10,
        armor=armor,
        is_alive=alive,
        cooldowns={},
        team=team,
        active_buffs=active_buffs or [],
    )


def _make_ally(
    player_id: str = "ally1",
    username: str = "Crusader",
    hp: int = 100,
    max_hp: int = 150,
    armor: int = 8,
    team: str = "team_1",
    x: int = 4,
    y: int = 5,
    alive: bool = True,
    active_buffs: list | None = None,
) -> PlayerState:
    """Helper — create an allied PlayerState."""
    return PlayerState(
        player_id=player_id,
        username=username,
        position=Position(x=x, y=y),
        class_id="crusader",
        hp=hp,
        max_hp=max_hp,
        attack_damage=20,
        armor=armor,
        is_alive=alive,
        cooldowns={},
        team=team,
        active_buffs=active_buffs or [],
    )


def _make_players(*units: PlayerState) -> dict[str, PlayerState]:
    """Build a players dict from a list of units."""
    return {u.player_id: u for u in units}


# ============================================================
# 1. Miasma (aoe_damage_slow_targeted)
# ============================================================

class TestMiasmaAoeDamageSlowTargeted:
    """Tests for resolve_aoe_damage_slow_targeted() — Miasma handler."""

    def test_miasma_deals_damage_to_enemies_in_radius(self, loaded_skills):
        """Miasma deals magic damage to enemies within radius of target tile."""
        pd = _make_player()
        enemy1 = _make_enemy(player_id="e1", username="Skel1", x=8, y=5, armor=0)
        enemy2 = _make_enemy(player_id="e2", username="Skel2", x=8, y=6, armor=0)
        players = _make_players(pd, enemy1, enemy2)
        skill = get_skill("miasma")

        # Target tile (8, 5) — both enemies within radius 2
        result = resolve_aoe_damage_slow_targeted(pd, 8, 5, skill, players, set())

        assert result.success is True
        assert result.damage_dealt > 0
        assert enemy1.hp < 50
        assert enemy2.hp < 50

    def test_miasma_does_not_damage_allies(self, loaded_skills):
        """Miasma only hits enemies, not allies in radius."""
        pd = _make_player(x=5, y=5)
        ally = _make_ally(player_id="a1", x=7, y=5)
        enemy = _make_enemy(player_id="e1", x=8, y=5, armor=0)
        players = _make_players(pd, ally, enemy)
        skill = get_skill("miasma")

        # Target tile (8, 5) — ally is within radius but should not be hit
        result = resolve_aoe_damage_slow_targeted(pd, 8, 5, skill, players, set())

        assert ally.hp == 100  # unchanged
        assert enemy.hp < 50  # took damage

    def test_miasma_applies_slow_to_survivors(self, loaded_skills):
        """Miasma applies slow debuff to enemies that survive the damage."""
        pd = _make_player()
        enemy = _make_enemy(player_id="e1", x=7, y=5, hp=50, armor=0)
        players = _make_players(pd, enemy)
        skill = get_skill("miasma")

        resolve_aoe_damage_slow_targeted(pd, 7, 5, skill, players, set())

        slow_buffs = [b for b in enemy.active_buffs if b.get("type") == "slow"]
        assert len(slow_buffs) == 1
        assert slow_buffs[0]["turns_remaining"] == 2

    def test_miasma_does_not_slow_killed_enemies(self, loaded_skills):
        """Enemies killed by Miasma do not receive slow debuff."""
        pd = _make_player()
        enemy = _make_enemy(player_id="e1", x=7, y=5, hp=1, armor=0)  # Will die
        players = _make_players(pd, enemy)
        skill = get_skill("miasma")

        result = resolve_aoe_damage_slow_targeted(pd, 7, 5, skill, players, set())

        assert enemy.is_alive is False
        slow_buffs = [b for b in enemy.active_buffs if b.get("type") == "slow"]
        assert len(slow_buffs) == 0

    def test_miasma_fails_out_of_range(self, loaded_skills):
        """Miasma fails when target tile is beyond range 5."""
        pd = _make_player(x=0, y=0)
        enemy = _make_enemy(player_id="e1", x=12, y=12)
        players = _make_players(pd, enemy)
        skill = get_skill("miasma")

        result = resolve_aoe_damage_slow_targeted(pd, 12, 12, skill, players, set())

        assert result.success is False
        assert "out of range" in result.message

    def test_miasma_fails_no_los(self, loaded_skills):
        """Miasma fails when there's no line of sight to target tile."""
        pd = _make_player(x=0, y=0)
        enemy = _make_enemy(player_id="e1", x=3, y=0)
        # Wall at (1, 0) blocks LOS
        obstacles = {(1, 0)}
        players = _make_players(pd, enemy)
        skill = get_skill("miasma")

        result = resolve_aoe_damage_slow_targeted(pd, 3, 0, skill, players, obstacles)

        assert result.success is False
        assert "no line of sight" in result.message

    def test_miasma_applies_cooldown(self, loaded_skills):
        """Miasma sets cooldown after use."""
        pd = _make_player()
        enemy = _make_enemy(player_id="e1", x=7, y=5, armor=0)
        players = _make_players(pd, enemy)
        skill = get_skill("miasma")

        resolve_aoe_damage_slow_targeted(pd, 7, 5, skill, players, set())

        assert pd.cooldowns.get("miasma", 0) == 6

    def test_miasma_no_enemies_in_radius(self, loaded_skills):
        """Miasma succeeds but reports empty radius when no enemies are nearby."""
        pd = _make_player(x=5, y=5)
        enemy = _make_enemy(player_id="e1", x=15, y=15)  # far away
        players = _make_players(pd, enemy)
        skill = get_skill("miasma")

        # Target tile (7, 5) has no enemies within radius 2
        result = resolve_aoe_damage_slow_targeted(pd, 7, 5, skill, players, set())

        assert result.success is True
        assert "no enemies" in result.message.lower()

    def test_miasma_magic_armor_50_percent(self, loaded_skills):
        """Miasma uses 50% armor effectiveness (magic damage)."""
        pd = _make_player()
        # Enemy with 4 armor → magic armor = 4 * 0.5 = 2 → damage = max(1, 10-2) = 8
        enemy = _make_enemy(player_id="e1", x=7, y=5, hp=50, armor=4)
        players = _make_players(pd, enemy)
        skill = get_skill("miasma")

        resolve_aoe_damage_slow_targeted(pd, 7, 5, skill, players, set())

        assert enemy.hp == 50 - 8

    def test_miasma_respects_skill_damage_pct_bonus(self, loaded_skills):
        """Miasma applies skill_damage_pct and magic_damage_pct bonuses."""
        pd = _make_player()
        pd.skill_damage_pct = 0.20  # +20%
        pd.magic_damage_pct = 0.10  # +10%
        # Base 10 * (1.0 + 0.20 + 0.10) = 10 * 1.3 = 13
        enemy = _make_enemy(player_id="e1", x=7, y=5, hp=50, armor=0)
        players = _make_players(pd, enemy)
        skill = get_skill("miasma")

        resolve_aoe_damage_slow_targeted(pd, 7, 5, skill, players, set())

        assert enemy.hp == 50 - 13

    def test_miasma_fails_no_target_specified(self, loaded_skills):
        """Miasma fails when target_x/target_y is None."""
        pd = _make_player()
        players = _make_players(pd)
        skill = get_skill("miasma")

        result = resolve_aoe_damage_slow_targeted(pd, None, None, skill, players, set())

        assert result.success is False
        assert "no target" in result.message.lower()


# ============================================================
# 2. Plague Flask (dot — existing handler)
# ============================================================

class TestPlagueFlaskDot:
    """Tests for resolve_dot() when used with Plague Flask skill definition."""

    def test_plague_flask_applies_dot(self, loaded_skills):
        """Plague Flask applies a 8 dmg/tick DoT for 4 turns."""
        pd = _make_player()
        enemy = _make_enemy(player_id="e1", x=7, y=5)
        players = _make_players(pd, enemy)
        skill = get_skill("plague_flask")

        result = resolve_dot(pd, 7, 5, skill, players, set(), target_id="e1")

        assert result.success is True
        dot_buffs = [b for b in enemy.active_buffs if b.get("type") == "dot"]
        assert len(dot_buffs) == 1
        assert dot_buffs[0]["damage_per_tick"] == 8
        assert dot_buffs[0]["turns_remaining"] == 4

    def test_plague_flask_refreshes_duration_on_recast(self, loaded_skills):
        """Recasting Plague Flask refreshes duration instead of stacking."""
        pd = _make_player()
        enemy = _make_enemy(player_id="e1", x=7, y=5, active_buffs=[
            {"buff_id": "plague_flask", "type": "dot", "source_id": "pd1",
             "damage_per_tick": 7, "turns_remaining": 1, "stat": None, "magnitude": 7}
        ])
        players = _make_players(pd, enemy)
        skill = get_skill("plague_flask")

        result = resolve_dot(pd, 7, 5, skill, players, set(), target_id="e1")

        assert result.success is True
        dot_buffs = [b for b in enemy.active_buffs if b.get("type") == "dot"]
        assert len(dot_buffs) == 1  # Not stacked
        assert dot_buffs[0]["turns_remaining"] == 4  # Refreshed

    def test_plague_flask_fails_out_of_range(self, loaded_skills):
        """Plague Flask fails when target is beyond range 5."""
        pd = _make_player(x=0, y=0)
        enemy = _make_enemy(player_id="e1", x=10, y=10)
        players = _make_players(pd, enemy)
        skill = get_skill("plague_flask")

        result = resolve_dot(pd, 10, 10, skill, players, set(), target_id="e1")

        assert result.success is False
        assert "out of range" in result.message

    def test_plague_flask_fails_no_los(self, loaded_skills):
        """Plague Flask fails when there's no line of sight to target."""
        pd = _make_player(x=0, y=0)
        enemy = _make_enemy(player_id="e1", x=3, y=0)
        obstacles = {(1, 0)}
        players = _make_players(pd, enemy)
        skill = get_skill("plague_flask")

        result = resolve_dot(pd, 3, 0, skill, players, obstacles, target_id="e1")

        assert result.success is False
        assert "no line of sight" in result.message

    def test_plague_flask_applies_cooldown(self, loaded_skills):
        """Plague Flask sets cooldown to 4 after use."""
        pd = _make_player()
        enemy = _make_enemy(player_id="e1", x=7, y=5)
        players = _make_players(pd, enemy)
        skill = get_skill("plague_flask")

        resolve_dot(pd, 7, 5, skill, players, set(), target_id="e1")

        assert pd.cooldowns.get("plague_flask", 0) == 4

    def test_plague_flask_damage_per_tick_correct(self, loaded_skills):
        """Plague Flask DoT deals 8 per tick (design: 8 × 4 = 32 total)."""
        pd = _make_player()
        enemy = _make_enemy(player_id="e1", x=7, y=5)
        players = _make_players(pd, enemy)
        skill = get_skill("plague_flask")

        resolve_dot(pd, 7, 5, skill, players, set(), target_id="e1")

        dot = [b for b in enemy.active_buffs if b.get("type") == "dot"][0]
        total_damage = dot["damage_per_tick"] * dot["turns_remaining"]
        assert total_damage == 32


# ============================================================
# 3. Enfeeble (aoe_debuff — existing handler)
# ============================================================

class TestEnfeebleAoeDebuff:
    """Tests for resolve_aoe_debuff() when used with Enfeeble skill definition."""

    def test_enfeeble_applies_debuff_to_enemies_in_radius(self, loaded_skills):
        """Enfeeble applies damage_dealt_multiplier debuff to enemies in radius."""
        pd = _make_player(x=5, y=5)
        enemy1 = _make_enemy(player_id="e1", username="Skel1", x=7, y=5)
        enemy2 = _make_enemy(player_id="e2", username="Skel2", x=8, y=5)
        players = _make_players(pd, enemy1, enemy2)
        skill = get_skill("enfeeble")

        # Target tile (7, 5) — both enemies within radius 2
        result = resolve_aoe_debuff(pd, 7, 5, skill, players, set())

        assert result.success is True
        debuffs_e1 = [b for b in enemy1.active_buffs if b.get("stat") == "damage_dealt_multiplier"]
        debuffs_e2 = [b for b in enemy2.active_buffs if b.get("stat") == "damage_dealt_multiplier"]
        assert len(debuffs_e1) == 1
        assert len(debuffs_e2) == 1
        assert debuffs_e1[0]["magnitude"] == 0.75
        assert debuffs_e1[0]["turns_remaining"] == 4

    def test_enfeeble_does_not_debuff_allies(self, loaded_skills):
        """Enfeeble only debuffs enemies, not allies."""
        pd = _make_player(x=5, y=5)
        ally = _make_ally(player_id="a1", x=7, y=5)
        enemy = _make_enemy(player_id="e1", x=8, y=5)
        players = _make_players(pd, ally, enemy)
        skill = get_skill("enfeeble")

        resolve_aoe_debuff(pd, 7, 5, skill, players, set())

        ally_debuffs = [b for b in ally.active_buffs if b.get("stat") == "damage_dealt_multiplier"]
        assert len(ally_debuffs) == 0

    def test_enfeeble_refreshes_on_recast(self, loaded_skills):
        """Recasting Enfeeble refreshes duration instead of stacking."""
        pd = _make_player(x=5, y=5)
        enemy = _make_enemy(player_id="e1", x=7, y=5, active_buffs=[
            {"buff_id": "enfeeble", "type": "debuff", "stat": "damage_dealt_multiplier",
             "magnitude": 0.75, "turns_remaining": 1}
        ])
        players = _make_players(pd, enemy)
        skill = get_skill("enfeeble")

        resolve_aoe_debuff(pd, 7, 5, skill, players, set())

        debuffs = [b for b in enemy.active_buffs if b.get("stat") == "damage_dealt_multiplier"]
        assert len(debuffs) == 1  # Not stacked
        assert debuffs[0]["turns_remaining"] == 4  # Refreshed

    def test_enfeeble_fails_out_of_range(self, loaded_skills):
        """Enfeeble fails when target tile is beyond range 4."""
        pd = _make_player(x=0, y=0)
        enemy = _make_enemy(player_id="e1", x=10, y=10)
        players = _make_players(pd, enemy)
        skill = get_skill("enfeeble")

        result = resolve_aoe_debuff(pd, 10, 10, skill, players, set())

        assert result.success is False
        assert "out of range" in result.message

    def test_enfeeble_fails_no_los(self, loaded_skills):
        """Enfeeble fails when there's no line of sight to target tile."""
        pd = _make_player(x=0, y=0)
        enemy = _make_enemy(player_id="e1", x=3, y=0)
        obstacles = {(1, 0)}
        players = _make_players(pd, enemy)
        skill = get_skill("enfeeble")

        result = resolve_aoe_debuff(pd, 3, 0, skill, players, obstacles)

        assert result.success is False
        assert "no line of sight" in result.message

    def test_enfeeble_applies_cooldown(self, loaded_skills):
        """Enfeeble sets cooldown to 5 after use."""
        pd = _make_player(x=5, y=5)
        enemy = _make_enemy(player_id="e1", x=7, y=5)
        players = _make_players(pd, enemy)
        skill = get_skill("enfeeble")

        resolve_aoe_debuff(pd, 7, 5, skill, players, set())

        assert pd.cooldowns.get("enfeeble", 0) == 5

    def test_enfeeble_no_enemies_in_radius(self, loaded_skills):
        """Enfeeble succeeds but reports no enemies when radius is empty."""
        pd = _make_player(x=5, y=5)
        enemy = _make_enemy(player_id="e1", x=15, y=15)  # far away from target
        players = _make_players(pd, enemy)
        skill = get_skill("enfeeble")

        result = resolve_aoe_debuff(pd, 7, 5, skill, players, set())

        assert result.success is True
        assert "no enemies" in result.message.lower()


# ============================================================
# 4. Inoculate (buff_cleanse)
# ============================================================

class TestInoculateBuffCleanse:
    """Tests for resolve_buff_cleanse() — Inoculate handler."""

    def test_inoculate_grants_armor_buff(self, loaded_skills):
        """Inoculate grants +3 armor buff for 3 turns."""
        pd = _make_player()
        ally = _make_ally(player_id="a1", x=4, y=5)
        players = _make_players(pd, ally)
        skill = get_skill("inoculate")

        result = resolve_buff_cleanse(pd, skill, 4, 5, players, target_id="a1")

        assert result.success is True
        armor_buffs = [b for b in ally.active_buffs if b.get("stat") == "armor" and b.get("type") == "buff"]
        assert len(armor_buffs) == 1
        assert armor_buffs[0]["magnitude"] == 3
        assert armor_buffs[0]["turns_remaining"] == 3

    def test_inoculate_cleanses_dot_effects(self, loaded_skills):
        """Inoculate removes all active DoT effects from target."""
        pd = _make_player()
        ally = _make_ally(player_id="a1", x=4, y=5, active_buffs=[
            {"buff_id": "wither", "type": "dot", "source_id": "e1",
             "damage_per_tick": 8, "turns_remaining": 3, "stat": None, "magnitude": 8},
        ])
        players = _make_players(pd, ally)
        skill = get_skill("inoculate")

        result = resolve_buff_cleanse(pd, skill, 4, 5, players, target_id="a1")

        assert result.success is True
        dot_buffs = [b for b in ally.active_buffs if b.get("type") == "dot"]
        assert len(dot_buffs) == 0
        assert result.buff_applied["dots_cleansed"] == 1

    def test_inoculate_cleanses_multiple_dots(self, loaded_skills):
        """Inoculate removes ALL DoTs simultaneously — not just one."""
        pd = _make_player()
        ally = _make_ally(player_id="a1", x=4, y=5, active_buffs=[
            {"buff_id": "wither", "type": "dot", "source_id": "e1",
             "damage_per_tick": 8, "turns_remaining": 3, "stat": None, "magnitude": 8},
            {"buff_id": "venom_gaze", "type": "dot", "source_id": "e2",
             "damage_per_tick": 5, "turns_remaining": 2, "stat": None, "magnitude": 5},
        ])
        players = _make_players(pd, ally)
        skill = get_skill("inoculate")

        result = resolve_buff_cleanse(pd, skill, 4, 5, players, target_id="a1")

        dot_buffs = [b for b in ally.active_buffs if b.get("type") == "dot"]
        assert len(dot_buffs) == 0
        assert result.buff_applied["dots_cleansed"] == 2

    def test_inoculate_works_without_dots(self, loaded_skills):
        """Inoculate works when target has no DoTs — just applies armor buff."""
        pd = _make_player()
        ally = _make_ally(player_id="a1", x=4, y=5)
        players = _make_players(pd, ally)
        skill = get_skill("inoculate")

        result = resolve_buff_cleanse(pd, skill, 4, 5, players, target_id="a1")

        assert result.success is True
        armor_buffs = [b for b in ally.active_buffs if b.get("stat") == "armor"]
        assert len(armor_buffs) == 1
        assert result.buff_applied["dots_cleansed"] == 0

    def test_inoculate_can_target_self(self, loaded_skills):
        """Inoculate can be cast on self (plague doctor targets own tile)."""
        pd = _make_player(active_buffs=[
            {"buff_id": "wither", "type": "dot", "source_id": "e1",
             "damage_per_tick": 8, "turns_remaining": 3, "stat": None, "magnitude": 8},
        ])
        players = _make_players(pd)
        skill = get_skill("inoculate")

        result = resolve_buff_cleanse(pd, skill, 5, 5, players, target_id="pd1")

        assert result.success is True
        # DoT should be cleansed
        dot_buffs = [b for b in pd.active_buffs if b.get("type") == "dot"]
        assert len(dot_buffs) == 0
        # Armor buff should be applied
        armor_buffs = [b for b in pd.active_buffs if b.get("stat") == "armor"]
        assert len(armor_buffs) == 1

    def test_inoculate_can_target_ally_in_range(self, loaded_skills):
        """Inoculate works on an ally within range 3."""
        pd = _make_player(x=5, y=5)
        ally = _make_ally(player_id="a1", x=7, y=5)  # 2 tiles away < range 3
        players = _make_players(pd, ally)
        skill = get_skill("inoculate")

        result = resolve_buff_cleanse(pd, skill, 7, 5, players, target_id="a1")

        assert result.success is True
        assert result.target_id == "a1"

    def test_inoculate_fails_ally_out_of_range(self, loaded_skills):
        """Inoculate fails when ally is beyond range 3."""
        pd = _make_player(x=0, y=0)
        ally = _make_ally(player_id="a1", x=5, y=5)  # distance 5 > range 3
        players = _make_players(pd, ally)
        skill = get_skill("inoculate")

        result = resolve_buff_cleanse(pd, skill, 5, 5, players, target_id="a1")

        assert result.success is False
        assert "out of range" in result.message

    def test_inoculate_applies_cooldown(self, loaded_skills):
        """Inoculate sets cooldown to 5 after use."""
        pd = _make_player()
        players = _make_players(pd)
        skill = get_skill("inoculate")

        resolve_buff_cleanse(pd, skill, 5, 5, players, target_id="pd1")

        assert pd.cooldowns.get("inoculate", 0) == 5

    def test_inoculate_preserves_non_dot_buffs(self, loaded_skills):
        """Inoculate removes only DoTs — other buffs/debuffs are preserved."""
        pd = _make_player()
        ally = _make_ally(player_id="a1", x=4, y=5, active_buffs=[
            {"buff_id": "shield_of_faith", "type": "buff", "stat": "armor",
             "magnitude": 5, "turns_remaining": 3},
            {"buff_id": "wither", "type": "dot", "source_id": "e1",
             "damage_per_tick": 8, "turns_remaining": 3, "stat": None, "magnitude": 8},
            {"buff_id": "enfeeble", "type": "debuff", "stat": "damage_dealt_multiplier",
             "magnitude": 0.75, "turns_remaining": 2},
        ])
        players = _make_players(pd, ally)
        skill = get_skill("inoculate")

        resolve_buff_cleanse(pd, skill, 4, 5, players, target_id="a1")

        # DoT removed
        dot_buffs = [b for b in ally.active_buffs if b.get("type") == "dot"]
        assert len(dot_buffs) == 0
        # Old armor buff preserved
        old_armor = [b for b in ally.active_buffs if b.get("buff_id") == "shield_of_faith"]
        assert len(old_armor) == 1
        # Debuff preserved
        debuffs = [b for b in ally.active_buffs if b.get("type") == "debuff"]
        assert len(debuffs) == 1
        # New armor buff from Inoculate added
        new_armor = [b for b in ally.active_buffs if b.get("buff_id") == "inoculate"]
        assert len(new_armor) == 1


# ============================================================
# 5. Dispatcher — resolve_skill_action()
# ============================================================

class TestDispatcherPlagueDoctorSkills:
    """Tests that resolve_skill_action() correctly dispatches Plague Doctor skills."""

    def test_dispatcher_routes_miasma(self, loaded_skills):
        """resolve_skill_action() routes aoe_damage_slow_targeted to the correct handler."""
        pd = _make_player()
        enemy = _make_enemy(player_id="e1", x=7, y=5, armor=0)
        players = _make_players(pd, enemy)
        skill = get_skill("miasma")
        action = PlayerAction(
            player_id="pd1", action_type=ActionType.SKILL,
            target_x=7, target_y=5, skill_id="miasma",
        )

        result = resolve_skill_action(pd, action, skill, players, set())

        assert result.success is True
        assert result.skill_id == "miasma"
        assert result.damage_dealt > 0

    def test_dispatcher_routes_plague_flask(self, loaded_skills):
        """resolve_skill_action() routes dot to the correct handler for plague_flask."""
        pd = _make_player()
        enemy = _make_enemy(player_id="e1", x=7, y=5)
        players = _make_players(pd, enemy)
        skill = get_skill("plague_flask")
        action = PlayerAction(
            player_id="pd1", action_type=ActionType.SKILL,
            target_x=7, target_y=5, skill_id="plague_flask", target_id="e1",
        )

        result = resolve_skill_action(pd, action, skill, players, set())

        assert result.success is True
        assert result.skill_id == "plague_flask"
        dot_buffs = [b for b in enemy.active_buffs if b.get("type") == "dot"]
        assert len(dot_buffs) == 1

    def test_dispatcher_routes_enfeeble(self, loaded_skills):
        """resolve_skill_action() routes aoe_debuff to the correct handler for enfeeble."""
        pd = _make_player(x=5, y=5)
        enemy = _make_enemy(player_id="e1", x=7, y=5)
        players = _make_players(pd, enemy)
        skill = get_skill("enfeeble")
        action = PlayerAction(
            player_id="pd1", action_type=ActionType.SKILL,
            target_x=7, target_y=5, skill_id="enfeeble",
        )

        result = resolve_skill_action(pd, action, skill, players, set())

        assert result.success is True
        assert result.skill_id == "enfeeble"
        debuffs = [b for b in enemy.active_buffs if b.get("stat") == "damage_dealt_multiplier"]
        assert len(debuffs) == 1

    def test_dispatcher_routes_inoculate(self, loaded_skills):
        """resolve_skill_action() routes buff_cleanse to the correct handler for inoculate."""
        pd = _make_player()
        players = _make_players(pd)
        skill = get_skill("inoculate")
        action = PlayerAction(
            player_id="pd1", action_type=ActionType.SKILL,
            target_x=5, target_y=5, skill_id="inoculate", target_id="pd1",
        )

        result = resolve_skill_action(pd, action, skill, players, set())

        assert result.success is True
        assert result.skill_id == "inoculate"
        armor_buffs = [b for b in pd.active_buffs if b.get("stat") == "armor"]
        assert len(armor_buffs) == 1

    def test_dispatcher_miasma_with_multiple_enemies(self, loaded_skills):
        """Miasma through dispatcher hits multiple enemies in cluster."""
        pd = _make_player(x=5, y=5)
        e1 = _make_enemy(player_id="e1", username="Skel1", x=8, y=5, armor=0)
        e2 = _make_enemy(player_id="e2", username="Skel2", x=9, y=5, armor=0)
        e3 = _make_enemy(player_id="e3", username="Skel3", x=8, y=6, armor=0)
        players = _make_players(pd, e1, e2, e3)
        skill = get_skill("miasma")
        action = PlayerAction(
            player_id="pd1", action_type=ActionType.SKILL,
            target_x=8, target_y=5, skill_id="miasma",
        )

        result = resolve_skill_action(pd, action, skill, players, set())

        assert result.success is True
        # All 3 enemies within radius 2 of (8,5) should be hit
        assert result.buff_applied["hits"] == 3
