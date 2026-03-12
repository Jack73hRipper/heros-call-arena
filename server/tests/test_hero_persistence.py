"""
Tests for Phase 4E-2: Match Integration & Permadeath.

Covers:
- Hero loads into PlayerState with correct stats/equipment
- Equipment bonuses applied at match start
- Permadeath: hero marked dead on profile after death in match
- Dead hero's gear cleared on profile
- Post-match save: surviving hero inventory/equipment updated
- Gold earned from kills persisted to profile
- Cannot join match with dead hero
- Cannot start dungeon match without hero selection
- Arena mode unaffected (no hero required)
- match_end payload includes per-hero outcomes
- Kill tracking for gold rewards
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.models.profile import (
    Hero,
    HeroStats,
    PlayerProfile,
    STARTING_GOLD,
    generate_hero,
)
from app.models.player import PlayerState, Position, load_classes_config
from app.models.match import MatchConfig, MatchType
from app.models.actions import TurnResult, PlayerAction, ActionType
from app.services.persistence import (
    save_profile,
    load_profile,
    load_or_create_profile,
    delete_profile,
)
from app.core.match_manager import (
    create_match,
    join_match,
    start_match,
    end_match,
    get_match,
    get_match_players,
    select_hero,
    select_heroes,
    get_hero_selection,
    _load_heroes_at_match_start,
    _apply_hero_equipment_bonuses,
    handle_hero_permadeath,
    track_kill,
    get_kill_tracker,
    _persist_post_match,
    get_match_end_payload,
    validate_dungeon_hero_selections,
    select_class,
    get_lobby_players_payload,
    remove_match,
    _hero_selections,
    _username_map,
    _kill_tracker,
)


# ---------- Fixtures ----------


@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Redirect persistence to a temp directory for test isolation."""
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    monkeypatch.setattr("app.services.persistence._data_dir", players_dir)
    return players_dir


@pytest.fixture
def sample_hero():
    """Create a test hero with known stats."""
    return Hero(
        hero_id="hero-test1",
        name="Aldric the Brave",
        class_id="crusader",
        stats=HeroStats(
            hp=150, max_hp=150,
            attack_damage=20, ranged_damage=0,
            armor=8, vision_range=5, ranged_range=1,
        ),
        equipment={},
        inventory=[],
        is_alive=True,
        hire_cost=50,
    )


@pytest.fixture
def equipped_hero():
    """Create a test hero with equipment."""
    weapon = {
        "item_id": "wpn-001",
        "name": "Iron Sword",
        "item_type": "weapon",
        "rarity": "common",
        "equip_slot": "weapon",
        "stat_bonuses": {"max_hp": 0, "attack_damage": 0, "ranged_damage": 0, "armor": 0},
        "sell_value": 5,
    }
    armor = {
        "item_id": "arm-001",
        "name": "Steel Plate",
        "item_type": "armor",
        "rarity": "uncommon",
        "equip_slot": "armor",
        "stat_bonuses": {"max_hp": 20, "attack_damage": 0, "ranged_damage": 0, "armor": 0},
        "sell_value": 10,
    }
    potion = {
        "item_id": "pot-001",
        "name": "Health Potion",
        "item_type": "consumable",
        "rarity": "common",
        "consumable_effect": {"type": "heal", "magnitude": 30},
        "sell_value": 3,
    }
    return Hero(
        hero_id="hero-equip1",
        name="Gareth the Armed",
        class_id="crusader",
        stats=HeroStats(
            hp=150, max_hp=150,
            attack_damage=20, ranged_damage=0,
            armor=8, vision_range=5, ranged_range=1,
        ),
        equipment={"weapon": weapon, "armor": armor},
        inventory=[potion],
        is_alive=True,
        hire_cost=60,
    )


@pytest.fixture
def profile_with_hero(temp_data_dir, sample_hero):
    """Create and save a profile with one hero."""
    profile = PlayerProfile(
        username="testhero_player",
        gold=200,
        heroes=[sample_hero],
    )
    save_profile(profile)
    return profile


@pytest.fixture
def profile_with_equipped_hero(temp_data_dir, equipped_hero):
    """Create and save a profile with an equipped hero."""
    profile = PlayerProfile(
        username="equipped_player",
        gold=200,
        heroes=[equipped_hero],
    )
    save_profile(profile)
    return profile


@pytest.fixture
def dungeon_match(profile_with_hero):
    """Create a dungeon match with the test profile's user as host."""
    config = MatchConfig(
        map_id="dungeon_test",
        match_type=MatchType.DUNGEON,
        max_players=4,
    )
    match, host = create_match("testhero_player", config)
    yield match, host
    # Cleanup
    remove_match(match.match_id)


@pytest.fixture
def arena_match():
    """Create an arena (PvP) match for backward compat tests."""
    config = MatchConfig(
        map_id="arena_classic",
        match_type=MatchType.PVP,
        max_players=4,
    )
    match, host = create_match("arena_player", config)
    yield match, host
    remove_match(match.match_id)


# ---------- Test: Hero Selection ----------


class TestHeroSelection:
    """Tests for hero selection in lobby."""

    def test_select_hero_success(self, dungeon_match, profile_with_hero):
        match, host = dungeon_match
        result = select_hero(match.match_id, host.player_id, "hero-test1")
        assert result is not None
        assert result["hero_id"] == "hero-test1"
        assert result["hero_name"] == "Aldric the Brave"
        assert result["class_id"] == "crusader"

    def test_select_hero_stores_selection(self, dungeon_match, profile_with_hero):
        match, host = dungeon_match
        select_hero(match.match_id, host.player_id, "hero-test1")
        assert get_hero_selection(match.match_id, host.player_id) == ["hero-test1"]

    def test_select_nonexistent_hero(self, dungeon_match, profile_with_hero):
        match, host = dungeon_match
        result = select_hero(match.match_id, host.player_id, "nonexistent")
        assert result is None

    def test_select_dead_hero(self, dungeon_match, temp_data_dir):
        match, host = dungeon_match
        # Create a dead hero on the profile
        profile = load_or_create_profile("testhero_player")
        dead_hero = Hero(
            hero_id="hero-dead1",
            name="Fallen One",
            class_id="ranger",
            is_alive=False,
        )
        profile.heroes.append(dead_hero)
        save_profile(profile)

        result = select_hero(match.match_id, host.player_id, "hero-dead1")
        assert result is None

    def test_hero_in_lobby_payload(self, dungeon_match, profile_with_hero):
        match, host = dungeon_match
        select_hero(match.match_id, host.player_id, "hero-test1")
        payload = get_lobby_players_payload(match.match_id)
        assert payload[host.player_id].get("hero_id") == "hero-test1"
        assert payload[host.player_id].get("hero_ids") == ["hero-test1"]

    def test_no_hero_in_arena_lobby_payload(self, arena_match):
        match, host = arena_match
        payload = get_lobby_players_payload(match.match_id)
        assert "hero_id" not in payload[host.player_id]


# ---------- Test: Multi-Hero Selection (up to 4) ----------


class TestMultiHeroSelection:
    """Tests for selecting multiple heroes for dungeon runs."""

    @pytest.fixture
    def profile_with_multiple_heroes(self, temp_data_dir):
        """Create a profile with 5 heroes (to test max party size of 4)."""
        heroes = []
        for i in range(1, 6):
            heroes.append(Hero(
                hero_id=f"hero-multi{i}",
                name=f"Hero {i}",
                class_id="crusader",
                stats=HeroStats(
                    hp=100 + i * 10, max_hp=100 + i * 10,
                    attack_damage=15 + i, ranged_damage=0,
                    armor=5, vision_range=5, ranged_range=1,
                ),
                equipment={},
                inventory=[],
                is_alive=True,
                hire_cost=50,
            ))
        profile = PlayerProfile(
            username="multi_hero_player",
            gold=500,
            heroes=heroes,
        )
        save_profile(profile)
        return profile

    @pytest.fixture
    def multi_dungeon_match(self, profile_with_multiple_heroes):
        """Create a dungeon match for the multi-hero player."""
        config = MatchConfig(
            map_id="dungeon_test",
            match_type=MatchType.DUNGEON,
            max_players=4,
        )
        match, host = create_match("multi_hero_player", config)
        yield match, host
        remove_match(match.match_id)

    def test_select_multiple_heroes(self, multi_dungeon_match, profile_with_multiple_heroes):
        """Can select up to 4 heroes at once."""
        match, host = multi_dungeon_match
        hero_ids = ["hero-multi1", "hero-multi2", "hero-multi3", "hero-multi4"]
        results = select_heroes(match.match_id, host.player_id, hero_ids)
        assert results is not None
        assert len(results) == 4
        assert [r["hero_id"] for r in results] == hero_ids

    def test_multi_hero_stores_all_selections(self, multi_dungeon_match, profile_with_multiple_heroes):
        """All selected hero IDs are stored."""
        match, host = multi_dungeon_match
        hero_ids = ["hero-multi1", "hero-multi2", "hero-multi3"]
        select_heroes(match.match_id, host.player_id, hero_ids)
        stored = get_hero_selection(match.match_id, host.player_id)
        assert stored == hero_ids

    def test_multi_hero_spawns_all_allies(self, multi_dungeon_match, profile_with_multiple_heroes):
        """Each selected hero is spawned as an AI ally."""
        match, host = multi_dungeon_match
        hero_ids = ["hero-multi1", "hero-multi2", "hero-multi3"]
        select_heroes(match.match_id, host.player_id, hero_ids)
        players = get_match_players(match.match_id)
        hero_allies = [p for p in players.values() if p.hero_id and p.unit_type == "ai"]
        assert len(hero_allies) == 3
        hero_ally_ids = {p.hero_id for p in hero_allies}
        assert hero_ally_ids == set(hero_ids)

    def test_max_party_size_enforced(self, multi_dungeon_match, profile_with_multiple_heroes):
        """Selecting more than 4 heroes truncates to 4."""
        match, host = multi_dungeon_match
        hero_ids = ["hero-multi1", "hero-multi2", "hero-multi3", "hero-multi4", "hero-multi5"]
        results = select_heroes(match.match_id, host.player_id, hero_ids)
        assert results is not None
        assert len(results) == 4
        stored = get_hero_selection(match.match_id, host.player_id)
        assert len(stored) == 4

    def test_reselect_removes_old_allies(self, multi_dungeon_match, profile_with_multiple_heroes):
        """Re-selecting heroes removes all previously spawned allies."""
        match, host = multi_dungeon_match
        # First selection: 2 heroes
        select_heroes(match.match_id, host.player_id, ["hero-multi1", "hero-multi2"])
        players_before = get_match_players(match.match_id)
        allies_before = [p for p in players_before.values() if p.hero_id and p.unit_type == "ai"]
        assert len(allies_before) == 2

        # Re-select: 3 different heroes
        select_heroes(match.match_id, host.player_id, ["hero-multi3", "hero-multi4", "hero-multi5"])
        players_after = get_match_players(match.match_id)
        allies_after = [p for p in players_after.values() if p.hero_id and p.unit_type == "ai"]
        assert len(allies_after) == 3
        ally_hero_ids = {p.hero_id for p in allies_after}
        assert ally_hero_ids == {"hero-multi3", "hero-multi4", "hero-multi5"}

    def test_multi_hero_lobby_payload(self, multi_dungeon_match, profile_with_multiple_heroes):
        """Lobby payload includes hero_ids list."""
        match, host = multi_dungeon_match
        select_heroes(match.match_id, host.player_id, ["hero-multi1", "hero-multi2"])
        payload = get_lobby_players_payload(match.match_id)
        assert payload[host.player_id].get("hero_ids") == ["hero-multi1", "hero-multi2"]
        # Backward compat: hero_id is first hero
        assert payload[host.player_id].get("hero_id") == "hero-multi1"

    def test_duplicate_hero_ids_deduplicated(self, multi_dungeon_match, profile_with_multiple_heroes):
        """Duplicate hero IDs in the list are deduplicated."""
        match, host = multi_dungeon_match
        results = select_heroes(match.match_id, host.player_id, ["hero-multi1", "hero-multi1", "hero-multi2"])
        assert results is not None
        assert len(results) == 2

    def test_select_heroes_validates_all(self, multi_dungeon_match, profile_with_multiple_heroes):
        """If any hero in the list is invalid, entire selection fails."""
        match, host = multi_dungeon_match
        results = select_heroes(match.match_id, host.player_id, ["hero-multi1", "nonexistent"])
        assert results is None

    def test_dungeon_validation_with_multi_heroes(self, multi_dungeon_match, profile_with_multiple_heroes):
        """Dungeon validation passes with multi-hero selection."""
        match, host = multi_dungeon_match
        select_heroes(match.match_id, host.player_id, ["hero-multi1", "hero-multi2", "hero-multi3"])
        valid, error, offending_pid = validate_dungeon_hero_selections(match.match_id)
        assert valid is True

    def test_single_hero_backward_compat(self, multi_dungeon_match, profile_with_multiple_heroes):
        """select_hero() wrapper still works for single hero selection."""
        match, host = multi_dungeon_match
        result = select_hero(match.match_id, host.player_id, "hero-multi1")
        assert result is not None
        assert result["hero_id"] == "hero-multi1"
        stored = get_hero_selection(match.match_id, host.player_id)
        assert stored == ["hero-multi1"]


# ---------- Test: Hero Loading at Match Start ----------


class TestHeroLoadingAtMatchStart:
    """Tests for hero loading as AI ally (hero-as-ally system)."""

    @staticmethod
    def _find_hero_ally(match_id, hero_id):
        """Find the AI ally unit that represents a hero."""
        players = get_match_players(match_id)
        for pid, p in players.items():
            if p.hero_id == hero_id and p.unit_type == "ai":
                return pid, p
        return None, None

    def test_hero_spawned_as_ally(self, dungeon_match, profile_with_hero):
        match, host = dungeon_match
        select_hero(match.match_id, host.player_id, "hero-test1")

        # Hero should be spawned as AI ally immediately on select
        ally_id, ally = self._find_hero_ally(match.match_id, "hero-test1")
        assert ally is not None
        assert ally.hero_id == "hero-test1"
        assert ally.class_id == "crusader"
        assert ally.hp == 150
        assert ally.max_hp == 150
        assert ally.attack_damage == 20
        assert ally.armor == 8
        assert ally.unit_type == "ai"
        assert ally.team == "a"
        assert ally.username == "Aldric the Brave"

    def test_hero_ally_in_match_ids(self, dungeon_match, profile_with_hero):
        match, host = dungeon_match
        select_hero(match.match_id, host.player_id, "hero-test1")

        ally_id, ally = self._find_hero_ally(match.match_id, "hero-test1")
        assert ally_id in match.player_ids
        assert ally_id in match.ai_ids
        assert ally_id in match.team_a

    def test_hero_equipment_loaded(self, temp_data_dir, equipped_hero):
        profile = PlayerProfile(
            username="equip_loader",
            gold=200,
            heroes=[equipped_hero],
        )
        save_profile(profile)

        config = MatchConfig(map_id="dungeon_test", match_type=MatchType.DUNGEON)
        match, host = create_match("equip_loader", config)
        try:
            select_hero(match.match_id, host.player_id, equipped_hero.hero_id)

            ally_id, ally = self._find_hero_ally(match.match_id, equipped_hero.hero_id)
            assert ally is not None
            assert "weapon" in ally.equipment
            assert ally.equipment["weapon"]["item_id"] == "wpn-001"
            assert "armor" in ally.equipment
            assert len(ally.inventory) == 1
            assert ally.inventory[0]["item_id"] == "pot-001"
        finally:
            remove_match(match.match_id)

    def test_equipment_bonuses_applied(self, temp_data_dir, equipped_hero):
        profile = PlayerProfile(
            username="bonus_loader",
            gold=200,
            heroes=[equipped_hero],
        )
        save_profile(profile)

        config = MatchConfig(map_id="dungeon_test", match_type=MatchType.DUNGEON)
        match, host = create_match("bonus_loader", config)
        try:
            select_hero(match.match_id, host.player_id, equipped_hero.hero_id)

            ally_id, ally = self._find_hero_ally(match.match_id, equipped_hero.hero_id)
            assert ally is not None
            # Armor has +20 max_hp bonus
            assert ally.max_hp == 150 + 20
            assert ally.hp == 150 + 20
        finally:
            remove_match(match.match_id)

    def test_human_player_keeps_defaults(self, dungeon_match, profile_with_hero):
        match, host = dungeon_match
        select_hero(match.match_id, host.player_id, "hero-test1")
        _load_heroes_at_match_start(match.match_id)

        # Human player should NOT have hero stats (hero is AI ally)
        players = get_match_players(match.match_id)
        player = players[host.player_id]
        assert player.hero_id is None
        assert player.hp == 100  # Default HP

    def test_no_hero_keeps_defaults(self, arena_match):
        match, host = arena_match
        # No hero selected — should keep default stats
        _load_heroes_at_match_start(match.match_id)

        players = get_match_players(match.match_id)
        player = players[host.player_id]
        assert player.hero_id is None
        assert player.hp == 100  # Default HP

    def test_reselect_hero_removes_old_ally(self, temp_data_dir):
        """Selecting a different hero removes the previous ally."""
        profile = load_or_create_profile("reselect_player")
        hero1 = Hero(hero_id="hero-r1", name="First Hero", class_id="crusader",
                     stats=HeroStats(hp=150, max_hp=150, attack_damage=20, armor=8))
        hero2 = Hero(hero_id="hero-r2", name="Second Hero", class_id="ranger",
                     stats=HeroStats(hp=80, max_hp=80, ranged_damage=18, armor=2))
        profile.heroes.extend([hero1, hero2])
        save_profile(profile)

        config = MatchConfig(map_id="dungeon_test", match_type=MatchType.DUNGEON)
        match, host = create_match("reselect_player", config)
        try:
            # Select first hero
            select_hero(match.match_id, host.player_id, "hero-r1")
            ally1_id, ally1 = self._find_hero_ally(match.match_id, "hero-r1")
            assert ally1 is not None

            # Select second hero — first should be removed
            select_hero(match.match_id, host.player_id, "hero-r2")
            _, old_ally = self._find_hero_ally(match.match_id, "hero-r1")
            assert old_ally is None  # First hero ally removed

            ally2_id, ally2 = self._find_hero_ally(match.match_id, "hero-r2")
            assert ally2 is not None
            assert ally2.username == "Second Hero"
        finally:
            remove_match(match.match_id)


# ---------- Test: Permadeath ----------


class TestPermadeath:
    """Tests for hero permadeath mechanics (hero-as-ally system)."""

    @staticmethod
    def _find_hero_ally(match_id, hero_id):
        """Find the AI ally unit that represents a hero."""
        players = get_match_players(match_id)
        for pid, p in players.items():
            if p.hero_id == hero_id and p.unit_type == "ai":
                return pid, p
        return None, None

    def test_permadeath_marks_hero_dead(self, dungeon_match, profile_with_hero):
        match, host = dungeon_match
        select_hero(match.match_id, host.player_id, "hero-test1")

        # Find the hero ally and simulate death
        ally_id, ally = self._find_hero_ally(match.match_id, "hero-test1")
        assert ally is not None
        ally.is_alive = False

        result = handle_hero_permadeath(match.match_id, ally_id)
        assert result is not None
        assert result["hero_id"] == "hero-test1"
        assert result["hero_name"] == "Aldric the Brave"

        # Verify profile was updated
        profile = load_or_create_profile("testhero_player")
        hero = next(h for h in profile.heroes if h.hero_id == "hero-test1")
        assert hero.is_alive is False

    def test_permadeath_clears_equipment(self, temp_data_dir, equipped_hero):
        profile = PlayerProfile(
            username="perma_equip",
            gold=200,
            heroes=[equipped_hero],
        )
        save_profile(profile)

        config = MatchConfig(map_id="dungeon_test", match_type=MatchType.DUNGEON)
        match, host = create_match("perma_equip", config)
        try:
            select_hero(match.match_id, host.player_id, equipped_hero.hero_id)

            ally_id, ally = self._find_hero_ally(match.match_id, equipped_hero.hero_id)
            assert ally is not None
            ally.is_alive = False

            result = handle_hero_permadeath(match.match_id, ally_id)
            assert result is not None
            assert len(result["lost_items"]) == 3  # weapon + armor + potion

            # Verify profile was updated
            profile = load_or_create_profile("perma_equip")
            hero = next(h for h in profile.heroes if h.hero_id == equipped_hero.hero_id)
            assert hero.is_alive is False
            assert hero.equipment == {}
            assert hero.inventory == []
        finally:
            remove_match(match.match_id)

    def test_permadeath_no_hero_returns_none(self, arena_match):
        match, host = arena_match
        # Arena player without hero_id should not trigger permadeath
        result = handle_hero_permadeath(match.match_id, host.player_id)
        assert result is None

    def test_permadeath_lost_items_listed(self, temp_data_dir, equipped_hero):
        profile = PlayerProfile(
            username="lost_items_player",
            gold=200,
            heroes=[equipped_hero],
        )
        save_profile(profile)

        config = MatchConfig(map_id="dungeon_test", match_type=MatchType.DUNGEON)
        match, host = create_match("lost_items_player", config)
        try:
            select_hero(match.match_id, host.player_id, equipped_hero.hero_id)

            ally_id, ally = self._find_hero_ally(match.match_id, equipped_hero.hero_id)
            assert ally is not None
            ally.is_alive = False

            result = handle_hero_permadeath(match.match_id, ally_id)
            # Should list weapon, armor, and potion
            lost_ids = [i.get("item_id") for i in result["lost_items"]]
            assert "wpn-001" in lost_ids
            assert "arm-001" in lost_ids
            assert "pot-001" in lost_ids
        finally:
            remove_match(match.match_id)


# ---------- Test: Kill Tracking ----------


class TestKillTracking:
    """Tests for kill tracking and gold reward calculation."""

    def test_track_enemy_kill(self):
        match_id = "test-kill-track"
        _kill_tracker.pop(match_id, None)
        track_kill(match_id, "player1", victim_is_boss=False)
        tracker = get_kill_tracker(match_id)
        assert tracker["player1"]["enemy_kills"] == 1
        assert tracker["player1"]["boss_kills"] == 0
        _kill_tracker.pop(match_id, None)

    def test_track_boss_kill(self):
        match_id = "test-boss-track"
        _kill_tracker.pop(match_id, None)
        track_kill(match_id, "player1", victim_is_boss=True)
        tracker = get_kill_tracker(match_id)
        assert tracker["player1"]["enemy_kills"] == 0
        assert tracker["player1"]["boss_kills"] == 1
        _kill_tracker.pop(match_id, None)

    def test_track_multiple_kills(self):
        match_id = "test-multi-kills"
        _kill_tracker.pop(match_id, None)
        track_kill(match_id, "player1", victim_is_boss=False)
        track_kill(match_id, "player1", victim_is_boss=False)
        track_kill(match_id, "player1", victim_is_boss=True)
        tracker = get_kill_tracker(match_id)
        assert tracker["player1"]["enemy_kills"] == 2
        assert tracker["player1"]["boss_kills"] == 1
        _kill_tracker.pop(match_id, None)


# ---------- Test: Post-Match Persistence ----------


class TestPostMatchPersistence:
    """Tests for post-match hero persistence (hero-as-ally system)."""

    @staticmethod
    def _find_hero_ally(match_id, hero_id):
        """Find the AI ally unit that represents a hero."""
        players = get_match_players(match_id)
        for pid, p in players.items():
            if p.hero_id == hero_id and p.unit_type == "ai":
                return pid, p
        return None, None

    def test_surviving_hero_inventory_persisted(self, temp_data_dir, equipped_hero):
        profile = PlayerProfile(
            username="survivor",
            gold=100,
            heroes=[equipped_hero],
        )
        save_profile(profile)

        config = MatchConfig(map_id="dungeon_test", match_type=MatchType.DUNGEON)
        match, host = create_match("survivor", config)
        try:
            select_hero(match.match_id, host.player_id, equipped_hero.hero_id)

            # Add a new item to the hero ally's inventory during match
            ally_id, ally = self._find_hero_ally(match.match_id, equipped_hero.hero_id)
            assert ally is not None
            new_item = {
                "item_id": "loot-001",
                "name": "Goblin Dagger",
                "item_type": "weapon",
                "rarity": "common",
            }
            ally.inventory.append(new_item)

            # Run post-match persistence
            outcomes = _persist_post_match(match.match_id)

            # Verify hero inventory was updated on profile
            profile = load_or_create_profile("survivor")
            hero = next(h for h in profile.heroes if h.hero_id == equipped_hero.hero_id)
            inv_ids = [i.get("item_id") for i in hero.inventory]
            assert "pot-001" in inv_ids  # Original potion
            assert "loot-001" in inv_ids  # New loot
        finally:
            remove_match(match.match_id)

    def test_gold_earned_from_kills(self, temp_data_dir, sample_hero):
        profile = PlayerProfile(
            username="gold_earner",
            gold=100,
            heroes=[sample_hero],
        )
        save_profile(profile)

        config = MatchConfig(map_id="dungeon_test", match_type=MatchType.DUNGEON)
        match, host = create_match("gold_earner", config)
        try:
            select_hero(match.match_id, host.player_id, sample_hero.hero_id)

            # Find the hero ally and track kills against its ID
            ally_id, ally = self._find_hero_ally(match.match_id, sample_hero.hero_id)
            assert ally is not None
            track_kill(match.match_id, ally_id, victim_is_boss=False)
            track_kill(match.match_id, ally_id, victim_is_boss=False)
            track_kill(match.match_id, ally_id, victim_is_boss=True)

            outcomes = _persist_post_match(match.match_id)

            # Verify gold was earned: 2*10 + 1*50 + 25 (clear bonus) = 95
            profile = load_or_create_profile("gold_earner")
            assert profile.gold == 100 + 95
            assert outcomes[ally_id]["gold_earned"] == 95
            assert outcomes[ally_id]["status"] == "survived"
        finally:
            remove_match(match.match_id)

    def test_dead_hero_no_gold(self, temp_data_dir, sample_hero):
        profile = PlayerProfile(
            username="dead_hero_gold",
            gold=100,
            heroes=[sample_hero],
        )
        save_profile(profile)

        config = MatchConfig(map_id="dungeon_test", match_type=MatchType.DUNGEON)
        match, host = create_match("dead_hero_gold", config)
        try:
            select_hero(match.match_id, host.player_id, sample_hero.hero_id)

            # Kill the hero ally (permadeath)
            ally_id, ally = self._find_hero_ally(match.match_id, sample_hero.hero_id)
            assert ally is not None
            ally.is_alive = False
            handle_hero_permadeath(match.match_id, ally_id)

            outcomes = _persist_post_match(match.match_id)

            assert outcomes[ally_id]["status"] == "died"
            assert outcomes[ally_id]["gold_earned"] == 0
        finally:
            remove_match(match.match_id)

    def test_matches_survived_incremented(self, temp_data_dir, sample_hero):
        profile = PlayerProfile(
            username="survivor_count",
            gold=100,
            heroes=[sample_hero],
        )
        save_profile(profile)

        config = MatchConfig(map_id="dungeon_test", match_type=MatchType.DUNGEON)
        match, host = create_match("survivor_count", config)
        try:
            select_hero(match.match_id, host.player_id, sample_hero.hero_id)

            _persist_post_match(match.match_id)

            profile = load_or_create_profile("survivor_count")
            hero = next(h for h in profile.heroes if h.hero_id == sample_hero.hero_id)
            assert hero.matches_survived == 1
        finally:
            remove_match(match.match_id)


# ---------- Test: Dungeon Validation ----------


class TestDungeonValidation:
    """Tests for dungeon hero selection validation."""

    def test_dungeon_requires_hero(self, dungeon_match, profile_with_hero):
        match, host = dungeon_match
        # No hero selected — should fail
        valid, error, offending_pid = validate_dungeon_hero_selections(match.match_id)
        assert valid is False
        assert "testhero_player" in error
        assert offending_pid == host.player_id

    def test_dungeon_with_hero_passes(self, dungeon_match, profile_with_hero):
        match, host = dungeon_match
        select_hero(match.match_id, host.player_id, "hero-test1")
        valid, error, offending_pid = validate_dungeon_hero_selections(match.match_id)
        assert valid is True
        assert offending_pid is None

    def test_arena_always_passes(self, arena_match):
        match, host = arena_match
        # Arena mode — no hero required
        valid, error, offending_pid = validate_dungeon_hero_selections(match.match_id)
        assert valid is True
        assert offending_pid is None

    def test_arena_mode_unaffected(self, arena_match):
        """Full arena mode backward compat: no hero_id, no permadeath."""
        match, host = arena_match
        players = get_match_players(match.match_id)
        player = players[host.player_id]
        assert player.hero_id is None

        # Permadeath should return None for arena players
        result = handle_hero_permadeath(match.match_id, host.player_id)
        assert result is None


# ---------- Test: Match End Payload ----------


class TestMatchEndPayload:
    """Tests for the match_end hero outcomes payload (hero-as-ally system)."""

    @staticmethod
    def _find_hero_ally(match_id, hero_id):
        """Find the AI ally unit that represents a hero."""
        players = get_match_players(match_id)
        for pid, p in players.items():
            if p.hero_id == hero_id and p.unit_type == "ai":
                return pid, p
        return None, None

    def test_match_end_includes_hero_outcomes(self, temp_data_dir, sample_hero):
        profile = PlayerProfile(
            username="end_payload",
            gold=100,
            heroes=[sample_hero],
        )
        save_profile(profile)

        config = MatchConfig(map_id="dungeon_test", match_type=MatchType.DUNGEON)
        match, host = create_match("end_payload", config)
        try:
            select_hero(match.match_id, host.player_id, sample_hero.hero_id)

            ally_id, ally = self._find_hero_ally(match.match_id, sample_hero.hero_id)
            assert ally is not None
            track_kill(match.match_id, ally_id, victim_is_boss=False)

            payload = get_match_end_payload(match.match_id)
            assert "hero_outcomes" in payload
            assert ally_id in payload["hero_outcomes"]
            outcome = payload["hero_outcomes"][ally_id]
            assert outcome["hero_id"] == sample_hero.hero_id
            assert outcome["status"] == "survived"
            assert outcome["enemy_kills"] == 1
        finally:
            remove_match(match.match_id)

    def test_arena_match_end_payload(self, arena_match):
        match, host = arena_match
        payload = get_match_end_payload(match.match_id)
        assert "hero_outcomes" in payload
        outcome = payload["hero_outcomes"][host.player_id]
        assert outcome["status"] == "survived"
        assert "hero_id" not in outcome  # No hero in arena mode


# ---------- Test: Equipment Bonus Application ----------


class TestEquipmentBonuses:
    """Tests for equipment stat bonuses at match start."""

    def test_apply_hero_equipment_bonuses_max_hp(self):
        player = PlayerState(
            player_id="test-equip",
            username="test",
            hp=100,
            max_hp=100,
        )
        player.equipment = {
            "armor": {
                "item_id": "arm-test",
                "stat_bonuses": {"max_hp": 30, "attack_damage": 0, "ranged_damage": 0, "armor": 0},
            }
        }
        _apply_hero_equipment_bonuses(player)
        assert player.max_hp == 130
        assert player.hp == 130

    def test_apply_hero_equipment_bonuses_empty(self):
        player = PlayerState(
            player_id="test-empty",
            username="test",
            hp=100,
            max_hp=100,
        )
        player.equipment = {}
        _apply_hero_equipment_bonuses(player)
        assert player.max_hp == 100
        assert player.hp == 100

    def test_apply_hero_equipment_bonuses_none_slot(self):
        player = PlayerState(
            player_id="test-none",
            username="test",
            hp=100,
            max_hp=100,
        )
        player.equipment = {"weapon": None, "armor": None}
        _apply_hero_equipment_bonuses(player)
        assert player.max_hp == 100


# ---------- Test: TurnResult hero_deaths field ----------


class TestTurnResultHeroDeaths:
    """Tests for the hero_deaths field on TurnResult."""

    def test_turn_result_has_hero_deaths_field(self):
        tr = TurnResult(match_id="test", turn_number=1)
        assert hasattr(tr, "hero_deaths")
        assert tr.hero_deaths == []

    def test_turn_result_hero_deaths_populated(self):
        tr = TurnResult(
            match_id="test",
            turn_number=1,
            hero_deaths=[{
                "hero_id": "h1",
                "hero_name": "Test Hero",
                "class_id": "crusader",
                "lost_items": [],
            }],
        )
        assert len(tr.hero_deaths) == 1
        assert tr.hero_deaths[0]["hero_id"] == "h1"


# ---------- Test: PlayerState hero_id field ----------


class TestPlayerStateHeroId:
    """Tests for the hero_id field on PlayerState."""

    def test_player_state_hero_id_default_none(self):
        ps = PlayerState(player_id="test", username="test")
        assert ps.hero_id is None

    def test_player_state_hero_id_set(self):
        ps = PlayerState(player_id="test", username="test", hero_id="hero-123")
        assert ps.hero_id == "hero-123"

    def test_player_state_backward_compat(self):
        """Existing code that creates PlayerState without hero_id should still work."""
        ps = PlayerState(
            player_id="test",
            username="test",
            hp=100,
            max_hp=100,
            attack_damage=15,
        )
        assert ps.hero_id is None
        assert ps.hp == 100
