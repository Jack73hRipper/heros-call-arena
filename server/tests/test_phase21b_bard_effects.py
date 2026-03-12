"""
Tests for Phase 21B: Bard Effect Handlers (Core Mechanics).

Covers:
- resolve_aoe_buff() — Ballad of Might (AoE ally damage buff)
- resolve_aoe_debuff() — Dirge of Weakness (AoE enemy debuff)
- resolve_cooldown_reduction() — Verse of Haste (ally cooldown reduction)
- resolve_skill_action() dispatcher — routes new effect types correctly
- Cacophony — Bard's aoe_damage_slow deals 10 damage (not 12 like Frost Nova)
"""

from __future__ import annotations

import pytest

from app.models.player import PlayerState, Position
from app.models.actions import ActionType, PlayerAction
from app.core.skills import (
    load_skills_config,
    clear_skills_cache,
    get_skill,
    resolve_aoe_buff,
    resolve_aoe_debuff,
    resolve_cooldown_reduction,
    resolve_skill_action,
    resolve_aoe_damage_slow,
)


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def _reset_skills_cache():
    """Clear cached config before each test to ensure isolation."""
    clear_skills_cache()
    yield
    clear_skills_cache()


@pytest.fixture
def loaded_skills() -> dict:
    """Load and return the skills config dict."""
    return load_skills_config()


def _make_player(
    player_id: str = "bard1",
    username: str = "TestBard",
    class_id: str = "bard",
    hp: int = 90,
    max_hp: int = 90,
    alive: bool = True,
    cooldowns: dict | None = None,
    team: str = "team_1",
    x: int = 5,
    y: int = 5,
    active_buffs: list | None = None,
) -> PlayerState:
    """Helper — create a PlayerState with the given class and state."""
    p = PlayerState(
        player_id=player_id,
        username=username,
        position=Position(x=x, y=y),
        class_id=class_id,
        hp=hp,
        max_hp=max_hp,
        is_alive=alive,
        cooldowns=cooldowns or {},
        team=team,
    )
    if active_buffs:
        p.active_buffs = active_buffs
    return p


def _make_action(target_x=None, target_y=None, target_id=None):
    """Helper — create a mock action object with target fields."""
    class MockAction:
        pass
    a = MockAction()
    a.target_x = target_x
    a.target_y = target_y
    a.target_id = target_id
    return a


# ============================================================
# 1. Ballad of Might — resolve_aoe_buff()
# ============================================================

class TestBalladOfMight:
    """Tests for the AoE buff handler (Ballad of Might)."""

    @pytest.fixture
    def ballad_skill(self, loaded_skills):
        return get_skill("ballad_of_might")

    def test_buff_applies_to_allies_in_radius(self, ballad_skill):
        """All alive allies within radius 2 should receive the buff."""
        bard = _make_player(player_id="bard1", username="Bard", x=5, y=5)
        ally1 = _make_player(player_id="ally1", username="Crusader", class_id="crusader",
                             hp=150, max_hp=150, x=6, y=5)
        ally2 = _make_player(player_id="ally2", username="Ranger", class_id="ranger",
                             hp=80, max_hp=80, x=5, y=6)
        players = {p.player_id: p for p in [bard, ally1, ally2]}

        result = resolve_aoe_buff(bard, ballad_skill, players)

        assert result.success is True
        # All 3 units (bard + 2 allies) should have the buff
        for p in [bard, ally1, ally2]:
            buffs = [b for b in p.active_buffs if b["buff_id"] == "ballad_of_might"]
            assert len(buffs) == 1, f"{p.username} should have exactly 1 ballad buff"
            assert buffs[0]["stat"] == "all_damage_multiplier"
            assert buffs[0]["magnitude"] == 1.4
            assert buffs[0]["turns_remaining"] == 3

    def test_buff_does_not_apply_to_enemies(self, ballad_skill):
        """Enemies (different team) should NOT receive the buff."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        enemy = _make_player(player_id="enemy1", username="Skeleton", class_id="crusader",
                             hp=100, max_hp=100, x=6, y=5, team="team_2")
        players = {p.player_id: p for p in [bard, enemy]}

        resolve_aoe_buff(bard, ballad_skill, players)

        assert len(enemy.active_buffs) == 0

    def test_buff_does_not_apply_to_dead_allies(self, ballad_skill):
        """Dead allies should NOT receive the buff."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        dead_ally = _make_player(player_id="ally1", username="DeadGuy", class_id="crusader",
                                 hp=0, alive=False, x=6, y=5)
        players = {p.player_id: p for p in [bard, dead_ally]}

        resolve_aoe_buff(bard, ballad_skill, players)

        assert len(dead_ally.active_buffs) == 0

    def test_buff_does_not_apply_outside_radius(self, ballad_skill):
        """Allies at distance 4+ should NOT receive the buff (radius is 3)."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        far_ally = _make_player(player_id="ally1", username="FarAlly", class_id="ranger",
                                hp=80, max_hp=80, x=9, y=5)  # distance 4
        players = {p.player_id: p for p in [bard, far_ally]}

        resolve_aoe_buff(bard, ballad_skill, players)

        assert len(far_ally.active_buffs) == 0

    def test_bard_receives_own_buff(self, ballad_skill):
        """The Bard should receive their own buff (self is an ally)."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        players = {"bard1": bard}

        resolve_aoe_buff(bard, ballad_skill, players)

        buffs = [b for b in bard.active_buffs if b["buff_id"] == "ballad_of_might"]
        assert len(buffs) == 1

    def test_buff_has_correct_fields(self, ballad_skill):
        """Buff entry should have all required fields."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        players = {"bard1": bard}

        resolve_aoe_buff(bard, ballad_skill, players)

        buff = bard.active_buffs[0]
        assert buff["buff_id"] == "ballad_of_might"
        assert buff["type"] == "buff"
        assert buff["stat"] == "all_damage_multiplier"
        assert buff["magnitude"] == 1.4
        assert buff["turns_remaining"] == 3

    def test_cooldown_applied_after_use(self, ballad_skill):
        """Bard's cooldowns should be updated after using Ballad."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        players = {"bard1": bard}

        resolve_aoe_buff(bard, ballad_skill, players)

        assert bard.cooldowns.get("ballad_of_might", 0) > 0

    def test_refresh_does_not_stack(self, ballad_skill):
        """Using Ballad again should refresh, not stack the buff."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        ally = _make_player(player_id="ally1", username="Ally", class_id="crusader",
                            hp=150, max_hp=150, x=6, y=5)
        players = {p.player_id: p for p in [bard, ally]}

        # Simulate first cast
        resolve_aoe_buff(bard, ballad_skill, players)
        # Reset cooldown for second cast
        bard.cooldowns["ballad_of_might"] = 0

        # Manually age the buff to 1 turn remaining
        for p in [bard, ally]:
            for b in p.active_buffs:
                if b["buff_id"] == "ballad_of_might":
                    b["turns_remaining"] = 1

        # Second cast — should refresh to 3, not add a second buff
        resolve_aoe_buff(bard, ballad_skill, players)

        for p in [bard, ally]:
            buffs = [b for b in p.active_buffs if b["buff_id"] == "ballad_of_might"]
            assert len(buffs) == 1, f"{p.username} should have exactly 1 ballad buff after refresh"
            assert buffs[0]["turns_remaining"] == 3

    def test_result_message_lists_buffed_allies(self, ballad_skill):
        """Result message should name the buffed allies."""
        bard = _make_player(player_id="bard1", username="Bard", x=5, y=5)
        ally = _make_player(player_id="ally1", username="Crusader", class_id="crusader",
                            hp=150, max_hp=150, x=6, y=5)
        players = {p.player_id: p for p in [bard, ally]}

        result = resolve_aoe_buff(bard, ballad_skill, players)

        assert result.success is True
        assert "Bard" in result.message
        assert "Ballad of Might" in result.message
        assert "Crusader" in result.message or "self" in result.message

    def test_no_allies_in_range_still_succeeds(self, ballad_skill):
        """If no allies are in range (only enemies), still succeeds but buffs nobody."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        # Only enemy nearby
        enemy = _make_player(player_id="enemy1", username="Goblin", class_id="crusader",
                             hp=100, max_hp=100, x=6, y=5, team="team_2")
        players = {p.player_id: p for p in [bard, enemy]}

        result = resolve_aoe_buff(bard, ballad_skill, players)

        # Bard buffs self (they're always in their own radius)
        assert result.success is True
        assert len(bard.active_buffs) == 1

    def test_ally_at_exact_radius_boundary(self, ballad_skill):
        """Ally at exactly radius 3 (Chebyshev) should receive the buff."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        edge_ally = _make_player(player_id="ally1", username="EdgeAlly", class_id="ranger",
                                 hp=80, max_hp=80, x=8, y=8)  # distance 3 (Chebyshev)
        players = {p.player_id: p for p in [bard, edge_ally]}

        resolve_aoe_buff(bard, ballad_skill, players)

        assert len(edge_ally.active_buffs) == 1


# ============================================================
# 2. Dirge of Weakness — resolve_aoe_debuff()
# ============================================================

class TestDirgeOfWeakness:
    """Tests for the AoE debuff handler (Dirge of Weakness)."""

    @pytest.fixture
    def dirge_skill(self, loaded_skills):
        return get_skill("dirge_of_weakness")

    def test_debuff_applies_to_enemies_in_radius(self, dirge_skill):
        """All alive enemies within radius 2 of target tile should receive the debuff."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        enemy1 = _make_player(player_id="e1", username="Goblin", class_id="crusader",
                              hp=100, max_hp=100, x=8, y=5, team="team_2")
        enemy2 = _make_player(player_id="e2", username="Orc", class_id="crusader",
                              hp=100, max_hp=100, x=9, y=5, team="team_2")
        players = {p.player_id: p for p in [bard, enemy1, enemy2]}

        result = resolve_aoe_debuff(bard, 8, 5, dirge_skill, players, set())

        assert result.success is True
        for e in [enemy1, enemy2]:
            debuffs = [b for b in e.active_buffs if b["buff_id"] == "dirge_of_weakness"]
            assert len(debuffs) == 1
            assert debuffs[0]["stat"] == "damage_taken_multiplier"
            assert debuffs[0]["magnitude"] == 1.30
            assert debuffs[0]["turns_remaining"] == 3

    def test_debuff_does_not_apply_to_allies(self, dirge_skill):
        """Allies should NOT receive the debuff."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        ally = _make_player(player_id="ally1", username="Ally", class_id="crusader",
                            hp=150, max_hp=150, x=8, y=5)
        players = {p.player_id: p for p in [bard, ally]}

        resolve_aoe_debuff(bard, 8, 5, dirge_skill, players, set())

        assert len(ally.active_buffs) == 0

    def test_debuff_does_not_apply_outside_radius(self, dirge_skill):
        """Enemies outside radius 2 of the target tile should NOT be debuffed."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        far_enemy = _make_player(player_id="e1", username="FarGoblin", class_id="crusader",
                                 hp=100, max_hp=100, x=12, y=5, team="team_2")
        players = {p.player_id: p for p in [bard, far_enemy]}

        resolve_aoe_debuff(bard, 8, 5, dirge_skill, players, set())

        assert len(far_enemy.active_buffs) == 0

    def test_fails_if_target_out_of_range(self, dirge_skill):
        """Should fail if the target tile is out of range (Chebyshev > 4)."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        enemy = _make_player(player_id="e1", username="Goblin", class_id="crusader",
                             hp=100, max_hp=100, x=15, y=5, team="team_2")
        players = {p.player_id: p for p in [bard, enemy]}

        result = resolve_aoe_debuff(bard, 15, 5, dirge_skill, players, set())

        assert result.success is False
        assert "range" in result.message.lower()

    def test_fails_if_no_los_to_target_tile(self, dirge_skill):
        """Should fail if there's no LOS to the target tile (obstacle blocking)."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        enemy = _make_player(player_id="e1", username="Goblin", class_id="crusader",
                             hp=100, max_hp=100, x=8, y=5, team="team_2")
        players = {p.player_id: p for p in [bard, enemy]}
        # Wall blocking LOS between bard (5,5) and target (8,5)
        obstacles = {(6, 5), (7, 5)}

        result = resolve_aoe_debuff(bard, 8, 5, dirge_skill, players, obstacles)

        assert result.success is False
        assert "line of sight" in result.message.lower()

    def test_debuff_has_correct_type_field(self, dirge_skill):
        """Debuff entry type should be 'debuff', not 'buff'."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        enemy = _make_player(player_id="e1", username="Goblin", class_id="crusader",
                             hp=100, max_hp=100, x=8, y=5, team="team_2")
        players = {p.player_id: p for p in [bard, enemy]}

        resolve_aoe_debuff(bard, 8, 5, dirge_skill, players, set())

        debuff = enemy.active_buffs[0]
        assert debuff["type"] == "debuff"

    def test_cooldown_applied_after_use(self, dirge_skill):
        """Bard's cooldowns should be updated after using Dirge."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        enemy = _make_player(player_id="e1", username="Goblin", class_id="crusader",
                             hp=100, max_hp=100, x=8, y=5, team="team_2")
        players = {p.player_id: p for p in [bard, enemy]}

        resolve_aoe_debuff(bard, 8, 5, dirge_skill, players, set())

        assert bard.cooldowns.get("dirge_of_weakness", 0) > 0

    def test_refresh_does_not_stack(self, dirge_skill):
        """Using Dirge again should refresh, not stack the debuff."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        enemy = _make_player(player_id="e1", username="Goblin", class_id="crusader",
                             hp=100, max_hp=100, x=8, y=5, team="team_2")
        players = {p.player_id: p for p in [bard, enemy]}

        resolve_aoe_debuff(bard, 8, 5, dirge_skill, players, set())
        bard.cooldowns["dirge_of_weakness"] = 0

        # Age existing debuff
        for b in enemy.active_buffs:
            if b["buff_id"] == "dirge_of_weakness":
                b["turns_remaining"] = 1

        resolve_aoe_debuff(bard, 8, 5, dirge_skill, players, set())

        debuffs = [b for b in enemy.active_buffs if b["buff_id"] == "dirge_of_weakness"]
        assert len(debuffs) == 1
        assert debuffs[0]["turns_remaining"] == 3

    def test_fails_if_no_target_specified(self, dirge_skill):
        """Should fail if no target tile is specified."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        players = {"bard1": bard}

        result = resolve_aoe_debuff(bard, None, None, dirge_skill, players, set())

        assert result.success is False
        assert "no target" in result.message.lower()

    def test_no_enemies_in_radius_still_succeeds(self, dirge_skill):
        """If no enemies are in the debuff radius, still succeeds with 0 debuffs."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        players = {"bard1": bard}

        result = resolve_aoe_debuff(bard, 8, 5, dirge_skill, players, set())

        assert result.success is True
        assert "no enemies" in result.message.lower()

    def test_enemy_at_exact_radius_boundary(self, dirge_skill):
        """Enemy at exactly radius 2 (Chebyshev) from target tile should be debuffed."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        # Target tile at (8,5), enemy at (10,7) = distance 2 from target
        edge_enemy = _make_player(player_id="e1", username="EdgeGoblin", class_id="crusader",
                                  hp=100, max_hp=100, x=10, y=7, team="team_2")
        players = {p.player_id: p for p in [bard, edge_enemy]}

        resolve_aoe_debuff(bard, 8, 5, dirge_skill, players, set())

        assert len(edge_enemy.active_buffs) == 1

    def test_dead_enemies_not_debuffed(self, dirge_skill):
        """Dead enemies should NOT receive the debuff."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        dead_enemy = _make_player(player_id="e1", username="DeadGoblin", class_id="crusader",
                                  hp=0, alive=False, x=8, y=5, team="team_2")
        players = {p.player_id: p for p in [bard, dead_enemy]}

        resolve_aoe_debuff(bard, 8, 5, dirge_skill, players, set())

        assert len(dead_enemy.active_buffs) == 0


# ============================================================
# 3. Verse of Haste — resolve_cooldown_reduction()
# ============================================================

class TestVerseOfHaste:
    """Tests for the cooldown reduction handler (Verse of Haste)."""

    @pytest.fixture
    def verse_skill(self, loaded_skills):
        return get_skill("verse_of_haste")

    def test_reduces_all_active_cooldowns_on_target(self, verse_skill):
        """Should reduce all active cooldowns on the target ally by 2."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        ally = _make_player(player_id="ally1", username="Mage", class_id="mage",
                            hp=70, max_hp=70, x=7, y=5,
                            cooldowns={"fireball": 5, "frost_nova": 3, "blink": 0})
        players = {p.player_id: p for p in [bard, ally]}

        result = resolve_cooldown_reduction(bard, verse_skill, players,
                                            target_x=7, target_y=5, target_id="ally1")

        assert result.success is True
        assert ally.cooldowns["fireball"] == 3   # 5 - 2
        assert ally.cooldowns["frost_nova"] == 1  # 3 - 2
        assert ally.cooldowns["blink"] == 0       # was 0, stays 0

    def test_cooldowns_dont_go_below_zero(self, verse_skill):
        """Cooldown reduction should never go below 0."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        ally = _make_player(player_id="ally1", username="Ally", class_id="ranger",
                            hp=80, max_hp=80, x=7, y=5,
                            cooldowns={"power_shot": 1})
        players = {p.player_id: p for p in [bard, ally]}

        resolve_cooldown_reduction(bard, verse_skill, players,
                                   target_x=7, target_y=5, target_id="ally1")

        assert ally.cooldowns["power_shot"] == 0  # 1 - 2 = 0, clamped

    def test_works_on_self(self, verse_skill):
        """Bard should be able to reduce their own cooldowns."""
        bard = _make_player(player_id="bard1", x=5, y=5,
                            cooldowns={"ballad_of_might": 4, "cacophony": 2})
        players = {"bard1": bard}

        result = resolve_cooldown_reduction(bard, verse_skill, players,
                                            target_x=5, target_y=5, target_id="bard1")

        assert result.success is True
        assert bard.cooldowns["ballad_of_might"] == 2   # 4 - 2
        assert bard.cooldowns["cacophony"] == 0          # 2 - 2

    def test_works_on_ally_within_range(self, verse_skill):
        """Should work on an ally within range 3."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        ally = _make_player(player_id="ally1", username="Confessor", class_id="confessor",
                            hp=100, max_hp=100, x=8, y=5,  # distance 3
                            cooldowns={"heal": 4})
        players = {p.player_id: p for p in [bard, ally]}

        result = resolve_cooldown_reduction(bard, verse_skill, players,
                                            target_x=8, target_y=5, target_id="ally1")

        assert result.success is True
        assert ally.cooldowns["heal"] == 2

    def test_fails_if_target_out_of_range(self, verse_skill):
        """Should fail if target ally is beyond range 4."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        far_ally = _make_player(player_id="ally1", username="FarAlly", class_id="ranger",
                                hp=80, max_hp=80, x=10, y=5,  # distance 5
                                cooldowns={"power_shot": 5})
        players = {p.player_id: p for p in [bard, far_ally]}

        result = resolve_cooldown_reduction(bard, verse_skill, players,
                                            target_x=10, target_y=5, target_id="ally1")

        assert result.success is False
        assert "range" in result.message.lower()
        assert far_ally.cooldowns["power_shot"] == 5  # unchanged

    def test_no_active_cooldowns_still_succeeds(self, verse_skill):
        """If the target has no active cooldowns, the skill still succeeds."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        ally = _make_player(player_id="ally1", username="Ally", class_id="crusader",
                            hp=150, max_hp=150, x=6, y=5, cooldowns={})
        players = {p.player_id: p for p in [bard, ally]}

        result = resolve_cooldown_reduction(bard, verse_skill, players,
                                            target_x=6, target_y=5, target_id="ally1")

        assert result.success is True
        assert "0 cooldown" in result.message

    def test_cooldown_applied_to_caster(self, verse_skill):
        """Bard should go on cooldown after using Verse of Haste."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        ally = _make_player(player_id="ally1", username="Ally", class_id="crusader",
                            hp=150, max_hp=150, x=6, y=5, cooldowns={"taunt": 4})
        players = {p.player_id: p for p in [bard, ally]}

        resolve_cooldown_reduction(bard, verse_skill, players,
                                   target_x=6, target_y=5, target_id="ally1")

        assert bard.cooldowns.get("verse_of_haste", 0) > 0

    def test_result_reports_reduced_count(self, verse_skill):
        """Result message should include how many cooldowns were reduced."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        ally = _make_player(player_id="ally1", username="Mage", class_id="mage",
                            hp=70, max_hp=70, x=6, y=5,
                            cooldowns={"fireball": 5, "frost_nova": 3})
        players = {p.player_id: p for p in [bard, ally]}

        result = resolve_cooldown_reduction(bard, verse_skill, players,
                                            target_x=6, target_y=5, target_id="ally1")

        assert result.success is True
        assert "2 cooldown" in result.message

    def test_tile_based_targeting_fallback(self, verse_skill):
        """Should work with tile-based targeting when target_id is not provided."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        ally = _make_player(player_id="ally1", username="Ally", class_id="crusader",
                            hp=150, max_hp=150, x=6, y=5, cooldowns={"taunt": 4})
        players = {p.player_id: p for p in [bard, ally]}

        result = resolve_cooldown_reduction(bard, verse_skill, players,
                                            target_x=6, target_y=5)

        assert result.success is True
        assert ally.cooldowns["taunt"] == 2

    def test_only_reduces_positive_cooldowns(self, verse_skill):
        """Only cooldowns that are > 0 should be counted as reduced."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        ally = _make_player(player_id="ally1", username="Ally", class_id="crusader",
                            hp=150, max_hp=150, x=6, y=5,
                            cooldowns={"taunt": 4, "shield_bash": 0, "war_cry": 0})
        players = {p.player_id: p for p in [bard, ally]}

        result = resolve_cooldown_reduction(bard, verse_skill, players,
                                            target_x=6, target_y=5, target_id="ally1")

        assert "1 cooldown" in result.message  # only taunt was reduced


# ============================================================
# 4. Dispatcher — resolve_skill_action() routes new types
# ============================================================

class TestSkillActionDispatcher:
    """Tests for resolve_skill_action() dispatching the 3 new effect types."""

    def test_aoe_buff_dispatched_correctly(self, loaded_skills):
        """aoe_buff effect type should be routed to resolve_aoe_buff."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        ally = _make_player(player_id="ally1", username="Ally", class_id="crusader",
                            hp=150, max_hp=150, x=6, y=5)
        players = {p.player_id: p for p in [bard, ally]}
        action = _make_action(target_x=5, target_y=5)
        skill = get_skill("ballad_of_might")

        result = resolve_skill_action(bard, action, skill, players, set())

        assert result.success is True
        assert len(bard.active_buffs) > 0

    def test_aoe_debuff_dispatched_correctly(self, loaded_skills):
        """aoe_debuff effect type should be routed to resolve_aoe_debuff."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        enemy = _make_player(player_id="e1", username="Goblin", class_id="crusader",
                             hp=100, max_hp=100, x=8, y=5, team="team_2")
        players = {p.player_id: p for p in [bard, enemy]}
        action = _make_action(target_x=8, target_y=5)
        skill = get_skill("dirge_of_weakness")

        result = resolve_skill_action(bard, action, skill, players, set())

        assert result.success is True
        assert len(enemy.active_buffs) > 0

    def test_cooldown_reduction_dispatched_correctly(self, loaded_skills):
        """cooldown_reduction effect type should be routed to resolve_cooldown_reduction."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        ally = _make_player(player_id="ally1", username="Mage", class_id="mage",
                            hp=70, max_hp=70, x=6, y=5,
                            cooldowns={"fireball": 5})
        players = {p.player_id: p for p in [bard, ally]}
        action = _make_action(target_x=6, target_y=5, target_id="ally1")
        skill = get_skill("verse_of_haste")

        result = resolve_skill_action(bard, action, skill, players, set())

        assert result.success is True
        assert ally.cooldowns["fireball"] == 3

    def test_cacophony_dispatches_to_aoe_damage_slow(self, loaded_skills):
        """Cacophony (aoe_damage_slow) should reuse the existing Frost Nova handler."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        enemy = _make_player(player_id="e1", username="Goblin", class_id="crusader",
                             hp=100, max_hp=100, x=6, y=5, team="team_2")
        players = {p.player_id: p for p in [bard, enemy]}
        action = _make_action()
        skill = get_skill("cacophony")

        result = resolve_skill_action(bard, action, skill, players, set())

        assert result.success is True
        # Should have dealt damage
        assert enemy.hp < 100


# ============================================================
# 5. Cacophony — Bard aoe_damage_slow specific tests
# ============================================================

class TestCacophony:
    """Tests specific to Bard's Cacophony (aoe_damage_slow)."""

    def test_cacophony_deals_11_damage(self, loaded_skills):
        """Cacophony should deal 11 base damage, below Frost Nova's 12."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        # Use an enemy with 0 armor so we see exact damage
        enemy = _make_player(player_id="e1", username="Goblin", class_id="crusader",
                             hp=100, max_hp=100, x=6, y=5, team="team_2")
        enemy.armor = 0
        players = {p.player_id: p for p in [bard, enemy]}
        skill = get_skill("cacophony")

        resolve_aoe_damage_slow(bard, skill, players, set())

        assert enemy.hp == 89  # 100 - 11 = 89

    def test_cacophony_applies_slow(self, loaded_skills):
        """Cacophony should apply a 2-turn slow to enemies in radius."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        enemy = _make_player(player_id="e1", username="Goblin", class_id="crusader",
                             hp=100, max_hp=100, x=6, y=5, team="team_2")
        enemy.armor = 0
        players = {p.player_id: p for p in [bard, enemy]}
        skill = get_skill("cacophony")

        resolve_aoe_damage_slow(bard, skill, players, set())

        slow_buffs = [b for b in enemy.active_buffs if b["type"] == "slow"]
        assert len(slow_buffs) == 1
        assert slow_buffs[0]["turns_remaining"] == 2

    def test_cacophony_weaker_than_frost_nova(self, loaded_skills):
        """Verify Cacophony deals less raw damage than Frost Nova."""
        bard = _make_player(player_id="bard1", x=5, y=5)
        mage = _make_player(player_id="mage1", username="Mage", class_id="mage",
                            hp=70, max_hp=70, x=5, y=5)

        enemy1 = _make_player(player_id="e1", username="G1", class_id="crusader",
                              hp=200, max_hp=200, x=6, y=5, team="team_2")
        enemy1.armor = 0
        enemy2 = _make_player(player_id="e2", username="G2", class_id="crusader",
                              hp=200, max_hp=200, x=6, y=5, team="team_2")
        enemy2.armor = 0

        cacophony = get_skill("cacophony")
        frost_nova = get_skill("frost_nova")

        players1 = {"bard1": bard, "e1": enemy1}
        resolve_aoe_damage_slow(bard, cacophony, players1, set())
        caco_dmg = 200 - enemy1.hp

        players2 = {"mage1": mage, "e2": enemy2}
        resolve_aoe_damage_slow(mage, frost_nova, players2, set())
        nova_dmg = 200 - enemy2.hp

        assert caco_dmg < nova_dmg
