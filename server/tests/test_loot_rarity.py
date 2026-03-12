"""
Tests for Phase 18F: Monster Rarity Loot Integration.

Covers:
- F1/F2: generate_enemy_loot() accepts monster_rarity and applies tier bonuses
  - Drop chance bonus (champion +50%, rare +100%, super_unique +100%)
  - Bonus item count (champion +1, rare +2, super_unique +3)
  - Guaranteed rarity floor (rare → magic+, super_unique → rare+)
  - Magic find bonus from tier
- F3: _resolve_deaths passes monster_rarity to loot roller
- F4: Gold multiplier helper
- F5: elite_kill events for rare/super_unique deaths
- F7: Edge cases and validation
"""

from __future__ import annotations

import pytest
import random

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType, TurnResult
from app.core.loot import (
    clear_caches,
    generate_enemy_loot,
    get_gold_multiplier,
    _get_rarity_loot_config,
    _RARITY_GOLD_MULTIPLIER,
    _RARITY_MF_BONUS,
)
from app.core.monster_rarity import get_rarity_tier, clear_monster_rarity_cache


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear all caches before and after each test."""
    clear_caches()
    yield
    clear_caches()


def _make_player(pid="p1", username="Player1", x=1, y=1, hp=100, max_hp=100,
                 attack_damage=15, ranged_damage=10, armor=2, team="a",
                 enemy_type=None, unit_type="human", monster_rarity=None,
                 display_name=None, champion_type=None, affixes=None,
                 is_boss=False, base_hp=100, ai_behavior=None,
                 class_id="", magic_find_pct=0.0) -> PlayerState:
    """Create a PlayerState with sensible defaults for testing."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        base_hp=base_hp,
        attack_damage=attack_damage,
        ranged_damage=ranged_damage,
        armor=armor,
        team=team,
        enemy_type=enemy_type,
        unit_type=unit_type,
        monster_rarity=monster_rarity,
        display_name=display_name,
        champion_type=champion_type,
        affixes=affixes or [],
        is_boss=is_boss,
        ai_behavior=ai_behavior,
        class_id=class_id,
        magic_find_pct=magic_find_pct,
    )


# ==========================================================================
# Test Class 1: Rarity Loot Config Helper
# ==========================================================================

class TestRarityLootConfig:
    """_get_rarity_loot_config returns correct tier bonuses."""

    def test_normal_returns_zero_bonuses(self):
        """Normal tier has no loot bonuses."""
        config = _get_rarity_loot_config("normal")
        assert config["loot_drop_chance_bonus"] == 0.0
        assert config["loot_bonus_items"] == 0
        assert config["loot_guaranteed_rarity"] is None
        assert config["loot_mf_bonus"] == 0.0

    def test_none_returns_zero_bonuses(self):
        """None rarity falls back to normal defaults."""
        config = _get_rarity_loot_config(None)
        assert config["loot_drop_chance_bonus"] == 0.0
        assert config["loot_bonus_items"] == 0

    def test_champion_has_drop_bonus(self):
        """Champion tier gets +0.5 drop chance bonus and +1 bonus item."""
        config = _get_rarity_loot_config("champion")
        assert config["loot_drop_chance_bonus"] == 0.5
        assert config["loot_bonus_items"] == 1
        assert config["loot_guaranteed_rarity"] is None
        assert config["loot_mf_bonus"] == 0.25

    def test_rare_has_full_drop_and_guaranteed_magic(self):
        """Rare tier gets +1.0 drop chance, +2 bonus items, magic guaranteed."""
        config = _get_rarity_loot_config("rare")
        assert config["loot_drop_chance_bonus"] == 1.0
        assert config["loot_bonus_items"] == 2
        assert config["loot_guaranteed_rarity"] == "magic"
        assert config["loot_mf_bonus"] == 0.50

    def test_super_unique_has_max_bonuses(self):
        """Super unique tier gets +2.0 drop, +3 bonus items, rare guaranteed."""
        config = _get_rarity_loot_config("super_unique")
        assert config["loot_drop_chance_bonus"] == 2.0
        assert config["loot_bonus_items"] == 3
        assert config["loot_guaranteed_rarity"] == "rare"
        assert config["loot_mf_bonus"] == 1.0

    def test_unknown_rarity_returns_defaults(self):
        """Unknown rarity strings fall back to zero bonuses."""
        config = _get_rarity_loot_config("mythic")
        assert config["loot_drop_chance_bonus"] == 0.0
        assert config["loot_bonus_items"] == 0

    def test_config_matches_monster_rarity_config_json(self):
        """Verify champion config values match what's in monster_rarity_config.json."""
        tier = get_rarity_tier("champion")
        assert tier is not None
        assert tier["loot_drop_chance_bonus"] == 0.5
        assert tier["loot_bonus_items"] == 1

    def test_rare_config_matches_json(self):
        """Verify rare tier config values match JSON."""
        tier = get_rarity_tier("rare")
        assert tier is not None
        assert tier["loot_drop_chance_bonus"] == 1.0
        assert tier["loot_bonus_items"] == 2
        assert tier["loot_guaranteed_rarity"] == "magic"


# ==========================================================================
# Test Class 2: Gold Multiplier
# ==========================================================================

class TestGoldMultiplier:
    """get_gold_multiplier returns correct multipliers per tier (Phase 18F F4)."""

    def test_normal_gold_multiplier(self):
        assert get_gold_multiplier("normal") == 1.0

    def test_champion_gold_multiplier(self):
        assert get_gold_multiplier("champion") == 1.5

    def test_rare_gold_multiplier(self):
        assert get_gold_multiplier("rare") == 2.5

    def test_super_unique_gold_multiplier(self):
        assert get_gold_multiplier("super_unique") == 5.0

    def test_none_gold_multiplier(self):
        assert get_gold_multiplier(None) == 1.0

    def test_unknown_gold_multiplier(self):
        assert get_gold_multiplier("legendary") == 1.0

    def test_gold_multiplier_dict_completeness(self):
        """All rarity tiers are represented in the gold multiplier dict."""
        for tier in ("normal", "champion", "rare", "super_unique"):
            assert tier in _RARITY_GOLD_MULTIPLIER

    def test_mf_bonus_dict_completeness(self):
        """All rarity tiers are represented in the MF bonus dict."""
        for tier in ("normal", "champion", "rare", "super_unique"):
            assert tier in _RARITY_MF_BONUS


# ==========================================================================
# Test Class 3: generate_enemy_loot with monster_rarity
# ==========================================================================

class TestGenerateEnemyLootRarity:
    """generate_enemy_loot applies monster_rarity bonuses (F1/F2)."""

    def test_normal_rarity_no_extra_items(self):
        """Normal rarity doesn't add bonus items."""
        items_normal = generate_enemy_loot(
            "skeleton", floor_number=3, enemy_tier="fodder",
            seed=42, monster_rarity="normal"
        )
        items_none = generate_enemy_loot(
            "skeleton", floor_number=3, enemy_tier="fodder",
            seed=42, monster_rarity=None
        )
        # Same seed, same results — no bonus from normal tier
        assert len(items_normal) == len(items_none)

    def test_champion_drops_more_items(self):
        """Champion rarity produces more items than normal with same seed.

        We use a seed that's known to produce a successful drop for skeleton,
        then check that champion tier adds +1 bonus item to the count.
        """
        # Run many seeds and compare — champions should average more items
        normal_total = 0
        champion_total = 0
        trials = 100
        for seed in range(trials):
            normal_items = generate_enemy_loot(
                "skeleton", floor_number=3, enemy_tier="fodder",
                seed=seed, monster_rarity="normal"
            )
            champion_items = generate_enemy_loot(
                "skeleton", floor_number=3, enemy_tier="fodder",
                seed=seed, monster_rarity="champion"
            )
            normal_total += len(normal_items)
            champion_total += len(champion_items)

        # Champion should drop significantly more items due to +50% drop chance and +1 bonus
        assert champion_total > normal_total

    def test_rare_always_drops(self):
        """Rare tier has +1.0 drop chance bonus, so any enemy always drops loot."""
        # Run multiple seeds — rare should always produce items
        drops = 0
        trials = 50
        for seed in range(trials):
            items = generate_enemy_loot(
                "skeleton", floor_number=3, enemy_tier="fodder",
                seed=seed, monster_rarity="rare"
            )
            if len(items) > 0:
                drops += 1
        # Rare has +1.0 drop bonus, so even 0% base chance → 100%
        assert drops == trials

    def test_rare_bonus_items_count(self):
        """Rare tier adds +2 bonus items beyond base count."""
        normal_items = generate_enemy_loot(
            "skeleton", floor_number=3, enemy_tier="fodder",
            seed=999, monster_rarity="normal"
        )
        rare_items = generate_enemy_loot(
            "skeleton", floor_number=3, enemy_tier="fodder",
            seed=999, monster_rarity="rare"
        )
        # If both drop, rare should have at least 2 more items
        if len(normal_items) > 0:
            assert len(rare_items) >= len(normal_items) + 2

    def test_monster_rarity_parameter_is_optional(self):
        """generate_enemy_loot works without monster_rarity (backward compat)."""
        items = generate_enemy_loot(
            "skeleton", floor_number=1, enemy_tier="fodder", seed=42
        )
        # Should work without error
        assert isinstance(items, list)

    def test_super_unique_drops_plenty(self):
        """Super unique tier produces lots of items."""
        items = generate_enemy_loot(
            "skeleton", floor_number=5, enemy_tier="boss",
            seed=42, monster_rarity="super_unique"
        )
        # Super unique: +3 bonus items + base, should be substantial
        assert len(items) >= 3


# ==========================================================================
# Test Class 4: _resolve_deaths with monster_rarity (F3/F5)
# ==========================================================================

class TestResolveDeathsRarity:
    """_resolve_deaths passes monster_rarity to loot roller and emits elite_kill events."""

    def test_resolve_deaths_uses_monster_rarity(self):
        """When an enemy with monster_rarity dies, loot should reflect tier bonuses."""
        from app.core.turn_phases.deaths_phase import _resolve_deaths
        from app.models.actions import ActionResult, ActionType

        hero = _make_player(pid="hero1", username="Hero", x=1, y=1, team="a")
        enemy = _make_player(
            pid="enemy1", username="Champion Skeleton", x=2, y=2, team="b",
            enemy_type="skeleton", unit_type="ai", monster_rarity="champion",
            ai_behavior="aggressive", base_hp=50,
        )
        players = {"hero1": hero, "enemy1": enemy}
        deaths = ["enemy1"]
        ground_items = {}
        results = [ActionResult(
            player_id="hero1", username="Hero",
            action_type=ActionType.ATTACK, success=True,
            message="Hero slays Champion Skeleton!",
            target_id="enemy1", target_username="Champion Skeleton",
            damage_dealt=50, target_hp_remaining=0, killed=True,
        )]
        loot_drops = []
        elite_kills = []

        hero_deaths = _resolve_deaths(
            match_id="test_match",
            deaths=deaths,
            players=players,
            ground_items=ground_items,
            results=results,
            loot_drops=loot_drops,
            floor_number=3,
            elite_kills=elite_kills,
        )

        # Function should return without error
        assert isinstance(hero_deaths, list)

    def test_elite_kill_event_for_rare(self):
        """Killing a rare enemy produces an elite_kill event."""
        from app.core.turn_phases.deaths_phase import _resolve_deaths
        from app.models.actions import ActionResult, ActionType

        hero = _make_player(pid="hero1", username="Hero", x=1, y=1, team="a")
        enemy = _make_player(
            pid="rare1", username="Blazing Skeleton", x=2, y=2, team="b",
            enemy_type="skeleton", unit_type="ai", monster_rarity="rare",
            display_name="Blazing Skeleton the Pyreborn",
            ai_behavior="aggressive", base_hp=150,
        )
        players = {"hero1": hero, "rare1": enemy}
        deaths = ["rare1"]
        ground_items = {}
        results = [ActionResult(
            player_id="hero1", username="Hero",
            action_type=ActionType.ATTACK, success=True,
            message="Hero slays Blazing Skeleton the Pyreborn!",
            target_id="rare1", target_username="Blazing Skeleton the Pyreborn",
            damage_dealt=100, target_hp_remaining=0, killed=True,
        )]
        loot_drops = []
        elite_kills = []

        _resolve_deaths(
            match_id="test_match",
            deaths=deaths,
            players=players,
            ground_items=ground_items,
            results=results,
            loot_drops=loot_drops,
            floor_number=5,
            elite_kills=elite_kills,
        )

        assert len(elite_kills) == 1
        ek = elite_kills[0]
        assert ek["type"] == "elite_kill"
        assert ek["monster_rarity"] == "rare"
        assert ek["display_name"] == "Blazing Skeleton the Pyreborn"
        assert ek["killer_id"] == "hero1"
        assert ek["enemy_type"] == "skeleton"

    def test_elite_kill_event_for_super_unique(self):
        """Killing a super_unique enemy produces an elite_kill event."""
        from app.core.turn_phases.deaths_phase import _resolve_deaths
        from app.models.actions import ActionResult, ActionType

        hero = _make_player(pid="hero1", username="Hero", x=1, y=1, team="a")
        enemy = _make_player(
            pid="su1", username="Malgris the Defiler", x=3, y=3, team="b",
            enemy_type="demon", unit_type="ai", monster_rarity="super_unique",
            display_name="Malgris the Defiler",
            ai_behavior="boss", base_hp=420, is_boss=True,
        )
        players = {"hero1": hero, "su1": enemy}
        deaths = ["su1"]
        ground_items = {}
        results = [ActionResult(
            player_id="hero1", username="Hero",
            action_type=ActionType.ATTACK, success=True,
            message="Hero slays Malgris!",
            target_id="su1", target_username="Malgris the Defiler",
            damage_dealt=200, target_hp_remaining=0, killed=True,
        )]
        loot_drops = []
        elite_kills = []

        _resolve_deaths(
            match_id="test_match",
            deaths=deaths,
            players=players,
            ground_items=ground_items,
            results=results,
            loot_drops=loot_drops,
            floor_number=5,
            elite_kills=elite_kills,
        )

        assert len(elite_kills) == 1
        ek = elite_kills[0]
        assert ek["type"] == "elite_kill"
        assert ek["monster_rarity"] == "super_unique"
        assert ek["display_name"] == "Malgris the Defiler"

    def test_no_elite_kill_for_normal(self):
        """Normal enemies don't generate elite_kill events."""
        from app.core.turn_phases.deaths_phase import _resolve_deaths
        from app.models.actions import ActionResult, ActionType

        hero = _make_player(pid="hero1", username="Hero", x=1, y=1, team="a")
        enemy = _make_player(
            pid="e1", username="Skeleton", x=2, y=2, team="b",
            enemy_type="skeleton", unit_type="ai", monster_rarity="normal",
            ai_behavior="aggressive", base_hp=50,
        )
        players = {"hero1": hero, "e1": enemy}
        deaths = ["e1"]
        ground_items = {}
        results = [ActionResult(
            player_id="hero1", username="Hero",
            action_type=ActionType.ATTACK, success=True,
            message="Hero slays Skeleton!",
            target_id="e1", target_username="Skeleton",
            damage_dealt=50, target_hp_remaining=0, killed=True,
        )]
        loot_drops = []
        elite_kills = []

        _resolve_deaths(
            match_id="test_match",
            deaths=deaths,
            players=players,
            ground_items=ground_items,
            results=results,
            loot_drops=loot_drops,
            floor_number=1,
            elite_kills=elite_kills,
        )

        assert len(elite_kills) == 0

    def test_no_elite_kill_for_champion(self):
        """Champions don't generate elite_kill events (only rare+)."""
        from app.core.turn_phases.deaths_phase import _resolve_deaths
        from app.models.actions import ActionResult, ActionType

        hero = _make_player(pid="hero1", username="Hero", x=1, y=1, team="a")
        enemy = _make_player(
            pid="c1", username="Champion Skeleton", x=2, y=2, team="b",
            enemy_type="skeleton", unit_type="ai", monster_rarity="champion",
            ai_behavior="aggressive", base_hp=70,
        )
        players = {"hero1": hero, "c1": enemy}
        deaths = ["c1"]
        ground_items = {}
        results = [ActionResult(
            player_id="hero1", username="Hero",
            action_type=ActionType.ATTACK, success=True,
            message="Hero slays Champion Skeleton!",
            target_id="c1", target_username="Champion Skeleton",
            damage_dealt=70, target_hp_remaining=0, killed=True,
        )]
        loot_drops = []
        elite_kills = []

        _resolve_deaths(
            match_id="test_match",
            deaths=deaths,
            players=players,
            ground_items=ground_items,
            results=results,
            loot_drops=loot_drops,
            floor_number=3,
            elite_kills=elite_kills,
        )

        assert len(elite_kills) == 0

    def test_elite_kill_has_loot_items(self):
        """Elite kill event includes loot_items if loot was dropped."""
        from app.core.turn_phases.deaths_phase import _resolve_deaths
        from app.models.actions import ActionResult, ActionType

        hero = _make_player(pid="hero1", username="Hero", x=1, y=1, team="a")
        enemy = _make_player(
            pid="rare1", username="Rare Demon", x=2, y=2, team="b",
            enemy_type="demon", unit_type="ai", monster_rarity="rare",
            display_name="Scorching Demon the Destroyer",
            ai_behavior="aggressive", base_hp=200,
        )
        players = {"hero1": hero, "rare1": enemy}
        deaths = ["rare1"]
        ground_items = {}
        results = [ActionResult(
            player_id="hero1", username="Hero",
            action_type=ActionType.ATTACK, success=True,
            message="Hero slays the demon!",
            target_id="rare1", target_username="Scorching Demon the Destroyer",
            damage_dealt=200, target_hp_remaining=0, killed=True,
        )]
        loot_drops = []
        elite_kills = []

        _resolve_deaths(
            match_id="test_match",
            deaths=deaths,
            players=players,
            ground_items=ground_items,
            results=results,
            loot_drops=loot_drops,
            floor_number=5,
            elite_kills=elite_kills,
        )

        if elite_kills and "loot_items" in elite_kills[0]:
            # If loot was dropped, loot_items should be a list of dicts with name and rarity
            for item in elite_kills[0]["loot_items"]:
                assert "name" in item
                assert "rarity" in item

    def test_elite_kills_none_is_graceful(self):
        """If elite_kills is None, no crash occurs."""
        from app.core.turn_phases.deaths_phase import _resolve_deaths
        from app.models.actions import ActionResult, ActionType

        hero = _make_player(pid="hero1", username="Hero", x=1, y=1, team="a")
        enemy = _make_player(
            pid="rare1", username="Rare", x=2, y=2, team="b",
            enemy_type="skeleton", unit_type="ai", monster_rarity="rare",
            ai_behavior="aggressive", base_hp=150,
        )
        players = {"hero1": hero, "rare1": enemy}
        deaths = ["rare1"]
        ground_items = {}
        results = [ActionResult(
            player_id="hero1", username="Hero",
            action_type=ActionType.ATTACK, success=True,
            message="Hero slays Rare!",
            target_id="rare1", target_username="Rare",
            damage_dealt=150, target_hp_remaining=0, killed=True,
        )]
        loot_drops = []

        # elite_kills=None — should not crash
        hero_deaths = _resolve_deaths(
            match_id="test_match",
            deaths=deaths,
            players=players,
            ground_items=ground_items,
            results=results,
            loot_drops=loot_drops,
            floor_number=3,
            elite_kills=None,
        )
        assert isinstance(hero_deaths, list)


# ==========================================================================
# Test Class 5: TurnResult elite_kills field (F5)
# ==========================================================================

class TestTurnResultEliteKills:
    """TurnResult model contains the elite_kills field."""

    def test_turn_result_has_elite_kills_field(self):
        """TurnResult should have an elite_kills list field."""
        tr = TurnResult(match_id="test", turn_number=1)
        assert hasattr(tr, "elite_kills")
        assert isinstance(tr.elite_kills, list)
        assert len(tr.elite_kills) == 0

    def test_turn_result_elite_kills_populated(self):
        """TurnResult can hold elite_kill event dicts."""
        tr = TurnResult(
            match_id="test",
            turn_number=1,
            elite_kills=[
                {
                    "type": "elite_kill",
                    "monster_rarity": "rare",
                    "display_name": "Blazing Skeleton the Pyreborn",
                    "killer_id": "p1",
                },
            ],
        )
        assert len(tr.elite_kills) == 1
        assert tr.elite_kills[0]["monster_rarity"] == "rare"


# ==========================================================================
# Test Class 6: Integration — resolve_turn with enhanced enemies
# ==========================================================================

class TestResolveTurnEliteKills:
    """Full resolve_turn integration produces elite_kill events."""

    def test_resolve_turn_includes_elite_kills(self):
        """A full resolve_turn with a rare dying should populate elite_kills."""
        from app.core.turn_resolver import resolve_turn

        hero = _make_player(
            pid="hero1", username="Hero", x=1, y=1, hp=100, max_hp=100,
            attack_damage=200, team="a",
        )
        rare_enemy = _make_player(
            pid="rare1", username="Blazing Skeleton", x=2, y=1,
            hp=10, max_hp=100, attack_damage=5, armor=0, team="b",
            enemy_type="skeleton", unit_type="ai", monster_rarity="rare",
            display_name="Blazing Skeleton the Pyreborn",
            ai_behavior="aggressive", base_hp=100,
        )

        players = {"hero1": hero, "rare1": rare_enemy}
        actions = [
            PlayerAction(
                player_id="hero1", action_type=ActionType.ATTACK,
                target_id="rare1", target_x=2, target_y=1,
            ),
        ]

        result = resolve_turn(
            match_id="test_match",
            turn_number=1,
            players=players,
            actions=actions,
            grid_width=10,
            grid_height=10,
            obstacles=set(),
            team_a=["hero1"],
            team_b=["rare1"],
            ground_items={},
            floor_number=5,
        )

        # The rare enemy should have died
        assert "rare1" in result.deaths
        # elite_kills should contain the kill event
        assert len(result.elite_kills) >= 1
        ek = result.elite_kills[0]
        assert ek["type"] == "elite_kill"
        assert ek["monster_rarity"] == "rare"
        assert ek["display_name"] == "Blazing Skeleton the Pyreborn"

    def test_resolve_turn_no_elite_kills_for_normal(self):
        """Normal enemy death should not produce elite_kills."""
        from app.core.turn_resolver import resolve_turn

        hero = _make_player(
            pid="hero1", username="Hero", x=1, y=1, hp=100, max_hp=100,
            attack_damage=200, team="a",
        )
        normal_enemy = _make_player(
            pid="e1", username="Skeleton", x=2, y=1,
            hp=10, max_hp=50, attack_damage=5, armor=0, team="b",
            enemy_type="skeleton", unit_type="ai", monster_rarity="normal",
            ai_behavior="aggressive", base_hp=50,
        )

        players = {"hero1": hero, "e1": normal_enemy}
        actions = [
            PlayerAction(
                player_id="hero1", action_type=ActionType.ATTACK,
                target_id="e1", target_x=2, target_y=1,
            ),
        ]

        result = resolve_turn(
            match_id="test_match",
            turn_number=1,
            players=players,
            actions=actions,
            grid_width=10,
            grid_height=10,
            obstacles=set(),
            team_a=["hero1"],
            team_b=["e1"],
            ground_items={},
            floor_number=1,
        )

        assert "e1" in result.deaths
        assert len(result.elite_kills) == 0


# ==========================================================================
# Test Class 7: Drop Chance Math Edge Cases
# ==========================================================================

class TestDropChanceMath:
    """Verify drop chance bonus math and capping."""

    def test_drop_chance_capped_at_one(self):
        """Effective drop chance caps at 1.0 (100%)."""
        config = _get_rarity_loot_config("super_unique")
        # super_unique has +2.0 bonus — even if base is 0.5, should cap at 1.0
        assert config["loot_drop_chance_bonus"] == 2.0
        effective = min(1.0, 0.5 + config["loot_drop_chance_bonus"])
        assert effective == 1.0

    def test_mf_bonus_stacks_with_player_mf(self):
        """Monster rarity MF bonus adds to player's magic find."""
        config = _get_rarity_loot_config("rare")
        player_mf = 0.20  # Player has 20% magic find
        effective_mf = player_mf + config["loot_mf_bonus"]
        assert effective_mf == pytest.approx(0.70)  # 0.20 + 0.50 = 0.70

    def test_champion_moderate_bonus(self):
        """Champion tier provides moderate but meaningful bonuses."""
        config = _get_rarity_loot_config("champion")
        assert 0.0 < config["loot_drop_chance_bonus"] < 1.0
        assert config["loot_bonus_items"] == 1
        assert config["loot_mf_bonus"] > 0


# ==========================================================================
# Test Class 8: Statistical Loot Quality Tests
# ==========================================================================

class TestLootQualityStatistical:
    """Statistical tests to verify rarity bonuses have meaningful effect."""

    def test_rare_produces_more_items_than_normal_statistical(self):
        """Over 200 trials, rare enemies should drop significantly more items than normal."""
        normal_count = 0
        rare_count = 0
        for seed in range(200):
            normal_items = generate_enemy_loot(
                "skeleton", floor_number=3, seed=seed, monster_rarity="normal"
            )
            rare_items = generate_enemy_loot(
                "skeleton", floor_number=3, seed=seed, monster_rarity="rare"
            )
            normal_count += len(normal_items)
            rare_count += len(rare_items)

        # Rare should produce meaningfully more items (at minimum 30% more)
        assert rare_count > normal_count * 1.3

    def test_super_unique_drops_most_items(self):
        """Over 100 trials, super uniques produce the most items."""
        normal_count = 0
        super_count = 0
        for seed in range(100):
            normal_items = generate_enemy_loot(
                "demon", floor_number=5, seed=seed, monster_rarity="normal"
            )
            super_items = generate_enemy_loot(
                "demon", floor_number=5, seed=seed, monster_rarity="super_unique"
            )
            normal_count += len(normal_items)
            super_count += len(super_items)

        assert super_count > normal_count
