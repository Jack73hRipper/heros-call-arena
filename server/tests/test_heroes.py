"""
Tests for Phase 4E-1: Hero models, persistence, and Town REST API.

Covers:
- PlayerProfile and Hero model creation and validation
- HeroStats with stat variation
- Hero generation (stat variation within bounds, unique names)
- Tavern generation (correct count, class distribution)
- JSON file persistence (save, load, round-trip, corrupt/missing handling)
- Hiring flow (gold deduction, roster add, duplicate rejection, insufficient gold)
- Town REST endpoint integration tests (profile, tavern, hire, roster, refresh)
- Backward compatibility (existing 446+ tests unaffected)
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from app.models.profile import (
    BASE_HIRE_COST,
    HERO_ROSTER_MAX,
    STARTING_GOLD,
    STAT_VARIATION_PERCENT,
    Hero,
    HeroStats,
    PlayerProfile,
    generate_hero,
    generate_tavern_heroes,
    get_tavern_pool_size,
    _vary_stat,
    _pick_unique_name,
)
from app.models.player import load_classes_config, ClassDefinition
from app.services.persistence import (
    save_profile,
    load_profile,
    create_default_profile,
    load_or_create_profile,
    delete_profile,
    list_profiles,
    get_data_dir,
    _profile_path,
)


# ---------- Fixtures ----------

@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Redirect persistence to a temp directory for test isolation."""
    players_dir = tmp_path / "players"
    players_dir.mkdir()
    monkeypatch.setattr(
        "app.services.persistence._data_dir", players_dir
    )
    return players_dir


@pytest.fixture
def sample_profile():
    """Create a basic test profile."""
    return PlayerProfile(
        username="testplayer",
        gold=STARTING_GOLD,
    )


@pytest.fixture
def sample_hero():
    """Create a basic test hero."""
    return Hero(
        name="Aldric the Unyielding",
        class_id="crusader",
        stats=HeroStats(
            hp=150, max_hp=150, attack_damage=20,
            ranged_damage=0, armor=8, vision_range=5, ranged_range=1,
        ),
        hire_cost=50,
    )


@pytest.fixture
def classes_dict():
    """Get classes config as raw dicts for hero generation tests."""
    classes = load_classes_config()
    return {
        cid: {
            "base_hp": c.base_hp,
            "base_melee_damage": c.base_melee_damage,
            "base_ranged_damage": c.base_ranged_damage,
            "base_armor": c.base_armor,
            "base_vision_range": c.base_vision_range,
            "ranged_range": c.ranged_range,
        }
        for cid, c in classes.items()
    }


@pytest.fixture
def names_config():
    """Load the names config for testing."""
    names_path = Path(__file__).resolve().parent.parent / "configs" / "names_config.json"
    with open(names_path, "r") as f:
        return json.load(f)


# Clear class config cache between tests to avoid stale state
@pytest.fixture(autouse=True)
def _clear_class_cache():
    """Clear class config cache before each test."""
    import app.models.player as player_module
    player_module._classes_cache = None
    yield
    player_module._classes_cache = None


# ============================================================
# 1. Model Tests — HeroStats
# ============================================================

class TestHeroStats:
    """Test HeroStats model creation and defaults."""

    def test_default_hero_stats(self):
        stats = HeroStats()
        assert stats.hp == 100
        assert stats.max_hp == 100
        assert stats.attack_damage == 15
        assert stats.ranged_damage == 10
        assert stats.armor == 2
        assert stats.vision_range == 7
        assert stats.ranged_range == 5

    def test_custom_hero_stats(self):
        stats = HeroStats(hp=150, max_hp=150, attack_damage=25, armor=10)
        assert stats.hp == 150
        assert stats.attack_damage == 25
        assert stats.armor == 10

    def test_hero_stats_serialization(self):
        stats = HeroStats(hp=120, max_hp=120, attack_damage=18)
        data = stats.model_dump()
        restored = HeroStats(**data)
        assert restored.hp == 120
        assert restored.attack_damage == 18


# ============================================================
# 2. Model Tests — Hero
# ============================================================

class TestHero:
    """Test Hero model creation, defaults, and serialization."""

    def test_default_hero(self):
        hero = Hero(name="Test Hero", class_id="crusader")
        assert hero.name == "Test Hero"
        assert hero.class_id == "crusader"
        assert hero.is_alive is True
        assert hero.hero_id  # Auto-generated
        assert len(hero.hero_id) == 8
        assert hero.hire_cost == BASE_HIRE_COST
        assert hero.equipment == {}
        assert hero.inventory == []
        assert hero.matches_survived == 0
        assert hero.enemies_killed == 0

    def test_hero_with_custom_stats(self, sample_hero):
        assert sample_hero.name == "Aldric the Unyielding"
        assert sample_hero.class_id == "crusader"
        assert sample_hero.stats.hp == 150
        assert sample_hero.stats.attack_damage == 20
        assert sample_hero.hire_cost == 50

    def test_hero_unique_ids(self):
        h1 = Hero(name="A", class_id="crusader")
        h2 = Hero(name="B", class_id="crusader")
        assert h1.hero_id != h2.hero_id

    def test_hero_serialization_roundtrip(self, sample_hero):
        data = sample_hero.model_dump(mode="json")
        restored = Hero(**data)
        assert restored.name == sample_hero.name
        assert restored.class_id == sample_hero.class_id
        assert restored.stats.hp == sample_hero.stats.hp
        assert restored.hero_id == sample_hero.hero_id
        assert restored.is_alive == sample_hero.is_alive

    def test_hero_dead_state(self, sample_hero):
        sample_hero.is_alive = False
        assert sample_hero.is_alive is False
        data = sample_hero.model_dump(mode="json")
        restored = Hero(**data)
        assert restored.is_alive is False


# ============================================================
# 3. Model Tests — PlayerProfile
# ============================================================

class TestPlayerProfile:
    """Test PlayerProfile model creation, defaults, and serialization."""

    def test_default_profile(self):
        profile = PlayerProfile(username="newplayer")
        assert profile.username == "newplayer"
        assert profile.gold == STARTING_GOLD
        assert profile.heroes == []
        assert profile.tavern_pool == []
        assert profile.bank == []
        assert profile.player_id  # Auto-generated

    def test_profile_with_heroes(self, sample_hero):
        profile = PlayerProfile(username="veteran", gold=500, heroes=[sample_hero])
        assert len(profile.heroes) == 1
        assert profile.heroes[0].name == "Aldric the Unyielding"
        assert profile.gold == 500

    def test_profile_serialization_roundtrip(self, sample_hero):
        profile = PlayerProfile(
            username="testuser",
            gold=200,
            heroes=[sample_hero],
            tavern_pool=[Hero(name="Tavern Guy", class_id="ranger")],
        )
        data = profile.model_dump(mode="json")
        restored = PlayerProfile(**data)
        assert restored.username == "testuser"
        assert restored.gold == 200
        assert len(restored.heroes) == 1
        assert restored.heroes[0].name == "Aldric the Unyielding"
        assert len(restored.tavern_pool) == 1
        assert restored.tavern_pool[0].name == "Tavern Guy"

    def test_profile_json_serialization(self, sample_hero):
        """Test that profile can be serialized to/from JSON string."""
        profile = PlayerProfile(username="jsontest", heroes=[sample_hero])
        json_str = json.dumps(profile.model_dump(mode="json"))
        data = json.loads(json_str)
        restored = PlayerProfile(**data)
        assert restored.username == "jsontest"
        assert len(restored.heroes) == 1


# ============================================================
# 4. Stat Variation Tests
# ============================================================

class TestStatVariation:
    """Test the _vary_stat helper and stat variation bounds."""

    def test_vary_stat_returns_int(self):
        result = _vary_stat(100)
        assert isinstance(result, int)

    def test_vary_stat_within_bounds(self):
        """Run many iterations to verify stats stay within ±10% bounds."""
        base = 100
        results = [_vary_stat(base) for _ in range(500)]
        assert all(90 <= r <= 110 for r in results), f"Out of bounds: {min(results)}-{max(results)}"

    def test_vary_stat_zero_base(self):
        """Zero base stat should return 0 (not negative)."""
        assert _vary_stat(0) == 0

    def test_vary_stat_small_base(self):
        """Small base stats should still have variation but stay >= 1."""
        results = [_vary_stat(2) for _ in range(100)]
        assert all(r >= 1 for r in results), f"Got value below 1: {min(results)}"

    def test_vary_stat_produces_variation(self):
        """Over many rolls, we should see different values (not always the base)."""
        results = set(_vary_stat(100) for _ in range(100))
        assert len(results) > 1, "No variation detected"

    def test_vary_stat_large_base(self):
        """Large base stats should have proportional variation."""
        base = 200
        results = [_vary_stat(base) for _ in range(200)]
        assert all(180 <= r <= 220 for r in results)


# ============================================================
# 5. Hero Generation Tests
# ============================================================

class TestHeroGeneration:
    """Test generate_hero and generate_tavern_heroes."""

    def test_generate_hero_basic(self, classes_dict):
        hero = generate_hero("crusader", "Test Knight", classes_dict["crusader"])
        assert hero.name == "Test Knight"
        assert hero.class_id == "crusader"
        assert hero.stats.hp > 0
        assert hero.stats.max_hp == hero.stats.hp
        assert hero.hire_cost >= BASE_HIRE_COST

    def test_generate_hero_stats_vary_from_base(self, classes_dict):
        """Generated hero stats should be close to but not always equal to base."""
        base_hp = classes_dict["crusader"]["base_hp"]  # 150
        hps = set()
        for _ in range(50):
            hero = generate_hero("crusader", "Knight", classes_dict["crusader"])
            hps.add(hero.stats.hp)
        # Should see variation (not always 150)
        assert len(hps) > 1, f"No HP variation detected, always {hps}"

    def test_generate_hero_ranged_range_no_variation(self, classes_dict):
        """ranged_range should NOT vary (exact copy from class config)."""
        ranges = set()
        for _ in range(50):
            hero = generate_hero("ranger", "Archer", classes_dict["ranger"])
            ranges.add(hero.stats.ranged_range)
        assert len(ranges) == 1, f"ranged_range should not vary, got {ranges}"
        assert classes_dict["ranger"]["ranged_range"] in ranges

    def test_generate_hero_hire_cost_scales(self, classes_dict):
        """Crusader (tank, high HP+armor) should cost more than Confessor (low stats)."""
        crusader_costs = [
            generate_hero("crusader", "C", classes_dict["crusader"]).hire_cost
            for _ in range(20)
        ]
        confessor_costs = [
            generate_hero("confessor", "F", classes_dict["confessor"]).hire_cost
            for _ in range(20)
        ]
        # Average cost should generally be higher for crusader
        avg_c = sum(crusader_costs) / len(crusader_costs)
        avg_f = sum(confessor_costs) / len(confessor_costs)
        assert avg_c > avg_f, f"Crusader avg {avg_c} should cost more than Confessor avg {avg_f}"

    def test_generate_tavern_heroes_count(self, classes_dict, names_config):
        heroes = generate_tavern_heroes(classes_dict, names_config, count=5)
        assert len(heroes) == 5

    def test_generate_tavern_heroes_class_distribution(self, classes_dict, names_config):
        """Heroes should be distributed across classes."""
        heroes = generate_tavern_heroes(classes_dict, names_config, count=5)
        class_ids = {h.class_id for h in heroes}
        assert len(class_ids) == 5  # 5 heroes, 5 classes → 1 each

    def test_generate_tavern_heroes_unique_names(self, classes_dict, names_config):
        heroes = generate_tavern_heroes(classes_dict, names_config, count=5)
        names = [h.name for h in heroes]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"

    def test_generate_tavern_avoids_existing_names(self, classes_dict, names_config):
        """Should not reuse names that are already hired."""
        existing = {"Aldric the Unyielding", "Bors Ironwall"}
        heroes = generate_tavern_heroes(classes_dict, names_config, count=5, existing_names=existing)
        for hero in heroes:
            assert hero.name not in existing, f"Reused existing name: {hero.name}"

    def test_generate_tavern_large_pool(self, classes_dict, names_config):
        """Can generate more heroes than default pool size."""
        heroes = generate_tavern_heroes(classes_dict, names_config, count=10)
        assert len(heroes) == 10
        names = [h.name for h in heroes]
        assert len(names) == len(set(names))

    def test_generate_hero_all_classes(self, classes_dict):
        """Every class should produce a valid hero."""
        for class_id, class_def in classes_dict.items():
            hero = generate_hero(class_id, f"Test {class_id}", class_def)
            assert hero.class_id == class_id
            assert hero.stats.hp > 0
            assert hero.is_alive is True


# ============================================================
# 6. Name Generation Tests
# ============================================================

class TestNameGeneration:
    """Test the _pick_unique_name helper."""

    def test_pick_name_from_class_pool(self, names_config):
        name = _pick_unique_name("crusader", names_config, set())
        crusader_names = names_config["crusader"]
        assert name in crusader_names

    def test_pick_name_avoids_used(self, names_config):
        used = set(names_config["crusader"][:5])
        name = _pick_unique_name("crusader", names_config, used)
        assert name not in used

    def test_pick_name_falls_back_to_generic(self, names_config):
        """When all class names are used, falls back to generic."""
        used = set(names_config["crusader"])  # All crusader names exhausted
        name = _pick_unique_name("crusader", names_config, used)
        # Should be from generic pool
        generic = names_config.get("generic", [])
        assert name in generic or "#" in name  # Either generic or numbered fallback

    def test_pick_name_numbered_fallback(self, names_config):
        """When all names exhausted, generates numbered fallback."""
        all_names = set()
        for key, names in names_config.items():
            all_names.update(names)
        name = _pick_unique_name("crusader", names_config, all_names)
        assert "Crusader #" in name

    def test_names_config_has_all_classes(self, names_config):
        """names_config.json should have entries for all 5 classes."""
        expected = {"crusader", "confessor", "inquisitor", "ranger", "hexblade"}
        assert expected.issubset(set(names_config.keys()))

    def test_names_config_has_generic(self, names_config):
        assert "generic" in names_config
        assert len(names_config["generic"]) >= 5

    def test_each_class_has_names(self, names_config):
        for class_id in ["crusader", "confessor", "inquisitor", "ranger", "hexblade"]:
            assert len(names_config[class_id]) >= 10, f"{class_id} needs at least 10 names"


# ============================================================
# 7. Persistence Tests
# ============================================================

class TestPersistence:
    """Test JSON file-based save/load/create operations."""

    def test_save_and_load_roundtrip(self, temp_data_dir, sample_profile):
        assert save_profile(sample_profile) is True
        loaded = load_profile("testplayer")
        assert loaded is not None
        assert loaded.username == "testplayer"
        assert loaded.gold == STARTING_GOLD

    def test_save_with_heroes(self, temp_data_dir, sample_profile, sample_hero):
        sample_profile.heroes.append(sample_hero)
        save_profile(sample_profile)
        loaded = load_profile("testplayer")
        assert len(loaded.heroes) == 1
        assert loaded.heroes[0].name == "Aldric the Unyielding"
        assert loaded.heroes[0].stats.hp == 150

    def test_load_missing_file_returns_none(self, temp_data_dir):
        result = load_profile("nonexistent_player")
        assert result is None

    def test_load_corrupt_file_returns_none(self, temp_data_dir):
        """Corrupt JSON should return None (graceful handling)."""
        filepath = temp_data_dir / "corrupt.json"
        filepath.write_text("{invalid json!!!}")
        # The function maps username to filename, so we look up "corrupt"
        result = load_profile("corrupt")
        assert result is None

    def test_create_default_profile(self, temp_data_dir):
        profile = create_default_profile("newbie")
        assert profile.username == "newbie"
        assert profile.gold == STARTING_GOLD
        assert profile.heroes == []
        # Should also be saved to disk
        loaded = load_profile("newbie")
        assert loaded is not None
        assert loaded.username == "newbie"

    def test_load_or_create_new(self, temp_data_dir):
        profile = load_or_create_profile("freshplayer")
        assert profile.username == "freshplayer"
        assert profile.gold == STARTING_GOLD
        # Verify it's saved
        loaded = load_profile("freshplayer")
        assert loaded is not None

    def test_load_or_create_existing(self, temp_data_dir, sample_profile):
        sample_profile.gold = 999
        save_profile(sample_profile)
        loaded = load_or_create_profile("testplayer")
        assert loaded.gold == 999  # Should load existing, not create new

    def test_delete_profile(self, temp_data_dir, sample_profile):
        save_profile(sample_profile)
        assert load_profile("testplayer") is not None
        assert delete_profile("testplayer") is True
        assert load_profile("testplayer") is None

    def test_delete_nonexistent(self, temp_data_dir):
        assert delete_profile("ghost") is False

    def test_list_profiles(self, temp_data_dir):
        create_default_profile("alice")
        create_default_profile("bob")
        create_default_profile("charlie")
        profiles = list_profiles()
        assert set(profiles) == {"alice", "bob", "charlie"}

    def test_list_profiles_empty(self, temp_data_dir):
        profiles = list_profiles()
        assert profiles == []

    def test_profile_persists_gold_change(self, temp_data_dir, sample_profile):
        save_profile(sample_profile)
        loaded = load_or_create_profile("testplayer")
        loaded.gold = 50
        save_profile(loaded)
        reloaded = load_profile("testplayer")
        assert reloaded.gold == 50

    def test_profile_persists_hero_roster(self, temp_data_dir, sample_hero):
        profile = create_default_profile("warrior")
        profile.heroes.append(sample_hero)
        save_profile(profile)
        loaded = load_profile("warrior")
        assert len(loaded.heroes) == 1
        assert loaded.heroes[0].hero_id == sample_hero.hero_id

    def test_sanitized_filename(self, temp_data_dir):
        """Usernames with special characters should be sanitized."""
        profile = PlayerProfile(username="player@#$123")
        save_profile(profile)
        # Should create file with sanitized name
        files = list(temp_data_dir.glob("*.json"))
        assert len(files) == 1
        assert "@" not in files[0].name

    def test_profile_with_tavern_pool_roundtrip(self, temp_data_dir):
        profile = PlayerProfile(username="taverntest")
        profile.tavern_pool = [
            Hero(name="Tavern Hero 1", class_id="ranger"),
            Hero(name="Tavern Hero 2", class_id="hexblade"),
        ]
        save_profile(profile)
        loaded = load_profile("taverntest")
        assert len(loaded.tavern_pool) == 2
        assert loaded.tavern_pool[0].name == "Tavern Hero 1"


# ============================================================
# 8. Hiring Flow Tests (Pure Model Logic)
# ============================================================

class TestHiringFlow:
    """Test the hiring logic at the model level (gold deduction, roster add)."""

    def test_hire_hero_deducts_gold(self, sample_profile, sample_hero):
        sample_hero.hire_cost = 40
        sample_profile.tavern_pool.append(sample_hero)
        initial_gold = sample_profile.gold  # 100

        # Simulate hire
        sample_profile.gold -= sample_hero.hire_cost
        sample_profile.heroes.append(sample_hero)
        sample_profile.tavern_pool.remove(sample_hero)

        assert sample_profile.gold == initial_gold - 40
        assert len(sample_profile.heroes) == 1
        assert len(sample_profile.tavern_pool) == 0

    def test_insufficient_gold_check(self, sample_profile, sample_hero):
        sample_hero.hire_cost = 999
        assert sample_profile.gold < sample_hero.hire_cost

    def test_roster_max_capacity(self):
        profile = PlayerProfile(username="fullroster")
        for i in range(HERO_ROSTER_MAX):
            profile.heroes.append(Hero(name=f"Hero {i}", class_id="crusader"))
        alive = [h for h in profile.heroes if h.is_alive]
        assert len(alive) == HERO_ROSTER_MAX

    def test_dead_heroes_dont_count_toward_cap(self):
        profile = PlayerProfile(username="deads")
        for i in range(HERO_ROSTER_MAX):
            hero = Hero(name=f"Hero {i}", class_id="crusader")
            hero.is_alive = False
            profile.heroes.append(hero)
        alive = [h for h in profile.heroes if h.is_alive]
        assert len(alive) == 0  # All dead, roster "empty" for hiring


# ============================================================
# 9. REST Endpoint Integration Tests
# ============================================================

class TestTownEndpoints:
    """Test Town REST endpoints via FastAPI TestClient."""

    @pytest.fixture(autouse=True)
    def setup_client(self, temp_data_dir):
        """Create a test client and clear names cache."""
        from fastapi.testclient import TestClient
        from app.main import app
        # Also clear the names config cache for test isolation
        import app.routes.town as town_module
        town_module._names_cache = None
        self.client = TestClient(app)

    # --- Profile ---

    def test_get_profile_new_player(self):
        resp = self.client.get("/api/town/profile?username=newbie")
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile"]["username"] == "newbie"
        assert data["profile"]["gold"] == STARTING_GOLD
        assert data["profile"]["hero_count"] == 0
        assert data["heroes"] == []

    def test_get_profile_existing_player(self):
        # Create profile first
        self.client.get("/api/town/profile?username=veteran")
        # Load again
        resp = self.client.get("/api/town/profile?username=veteran")
        assert resp.status_code == 200
        assert resp.json()["profile"]["gold"] == STARTING_GOLD

    def test_get_profile_missing_username(self):
        resp = self.client.get("/api/town/profile?username=")
        assert resp.status_code == 400

    def test_get_profile_no_username(self):
        resp = self.client.get("/api/town/profile")
        assert resp.status_code == 422  # FastAPI validation error

    # --- Tavern ---

    def test_get_tavern(self):
        resp = self.client.get("/api/town/tavern?username=taverngoer")
        assert resp.status_code == 200
        data = resp.json()
        assert "heroes" in data
        # Pool size should match class count (one hero per class)
        classes = load_classes_config()
        expected_pool = get_tavern_pool_size({
            cid: {"base_hp": c.base_hp, "base_melee_damage": c.base_melee_damage,
                  "base_ranged_damage": c.base_ranged_damage, "base_armor": c.base_armor,
                  "base_vision_range": c.base_vision_range, "ranged_range": c.ranged_range}
            for cid, c in classes.items()
        })
        assert len(data["heroes"]) == expected_pool
        assert "gold" in data

    def test_tavern_heroes_have_required_fields(self):
        resp = self.client.get("/api/town/tavern?username=fieldcheck")
        heroes = resp.json()["heroes"]
        for hero in heroes:
            assert "hero_id" in hero
            assert "name" in hero
            assert "class_id" in hero
            assert "stats" in hero
            assert "hire_cost" in hero
            assert "is_alive" in hero

    def test_tavern_persists_pool(self):
        """Same tavern pool returned on second request (not regenerated)."""
        resp1 = self.client.get("/api/town/tavern?username=persistent")
        resp2 = self.client.get("/api/town/tavern?username=persistent")
        heroes1 = [h["hero_id"] for h in resp1.json()["heroes"]]
        heroes2 = [h["hero_id"] for h in resp2.json()["heroes"]]
        assert heroes1 == heroes2

    # --- Hire ---

    def test_hire_hero_success(self):
        # Get tavern
        resp = self.client.get("/api/town/tavern?username=hirer")
        heroes = resp.json()["heroes"]
        hero_to_hire = heroes[0]

        # Hire
        resp = self.client.post("/api/town/hire", json={
            "username": "hirer",
            "hero_id": hero_to_hire["hero_id"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["gold"] == STARTING_GOLD - hero_to_hire["hire_cost"]
        assert data["hero"]["hero_id"] == hero_to_hire["hero_id"]

    def test_hire_hero_appears_in_roster(self):
        # Get tavern and hire
        resp = self.client.get("/api/town/tavern?username=rostertester")
        hero_to_hire = resp.json()["heroes"][0]
        self.client.post("/api/town/hire", json={
            "username": "rostertester",
            "hero_id": hero_to_hire["hero_id"],
        })

        # Check roster
        resp = self.client.get("/api/town/roster?username=rostertester")
        assert resp.status_code == 200
        roster = resp.json()["heroes"]
        assert len(roster) == 1
        assert roster[0]["hero_id"] == hero_to_hire["hero_id"]

    def test_hire_hero_removed_from_tavern(self):
        # Get tavern and hire
        resp = self.client.get("/api/town/tavern?username=tavernremove")
        heroes = resp.json()["heroes"]
        hero_id = heroes[0]["hero_id"]
        self.client.post("/api/town/hire", json={
            "username": "tavernremove", "hero_id": hero_id,
        })

        # Tavern should have one fewer hero
        resp = self.client.get("/api/town/tavern?username=tavernremove")
        remaining_ids = [h["hero_id"] for h in resp.json()["heroes"]]
        assert hero_id not in remaining_ids
        # Pool should be 1 less since all classes still represented (no auto-regen)
        classes = load_classes_config()
        expected_pool = get_tavern_pool_size({
            cid: {"base_hp": c.base_hp, "base_melee_damage": c.base_melee_damage,
                  "base_ranged_damage": c.base_ranged_damage, "base_armor": c.base_armor,
                  "base_vision_range": c.base_vision_range, "ranged_range": c.ranged_range}
            for cid, c in classes.items()
        })
        assert len(remaining_ids) == expected_pool - 1

    def test_hire_insufficient_gold(self):
        # Create profile with 0 gold
        profile = load_or_create_profile("broke")
        profile.gold = 0
        save_profile(profile)

        # Get tavern
        resp = self.client.get("/api/town/tavern?username=broke")
        hero = resp.json()["heroes"][0]

        # Try to hire
        resp = self.client.post("/api/town/hire", json={
            "username": "broke", "hero_id": hero["hero_id"],
        })
        assert resp.status_code == 400
        assert "Insufficient gold" in resp.json()["detail"]

    def test_hire_nonexistent_hero(self):
        resp = self.client.post("/api/town/hire", json={
            "username": "confused", "hero_id": "fake_hero_999",
        })
        assert resp.status_code == 404

    def test_hire_same_hero_twice(self):
        """Hiring the same hero twice should fail (removed from pool after first)."""
        resp = self.client.get("/api/town/tavern?username=dupe")
        hero = resp.json()["heroes"][0]

        # First hire succeeds
        resp1 = self.client.post("/api/town/hire", json={
            "username": "dupe", "hero_id": hero["hero_id"],
        })
        assert resp1.status_code == 200

        # Second hire should fail (hero no longer in pool)
        resp2 = self.client.post("/api/town/hire", json={
            "username": "dupe", "hero_id": hero["hero_id"],
        })
        assert resp2.status_code == 404

    # --- Roster ---

    def test_get_roster_empty(self):
        resp = self.client.get("/api/town/roster?username=noroster")
        assert resp.status_code == 200
        assert resp.json()["heroes"] == []

    def test_get_roster_with_hero(self):
        # Hire a hero first
        self.client.get("/api/town/tavern?username=rostercheck")
        resp = self.client.get("/api/town/tavern?username=rostercheck")
        hero = resp.json()["heroes"][0]
        self.client.post("/api/town/hire", json={
            "username": "rostercheck", "hero_id": hero["hero_id"],
        })

        resp = self.client.get("/api/town/roster?username=rostercheck")
        assert resp.status_code == 200
        assert len(resp.json()["heroes"]) == 1

    # --- Tavern Refresh ---

    def test_tavern_refresh(self):
        # Get initial tavern
        resp1 = self.client.get("/api/town/tavern?username=refresher")
        old_ids = {h["hero_id"] for h in resp1.json()["heroes"]}

        # Refresh
        resp = self.client.post("/api/town/tavern/refresh", json={
            "username": "refresher",
        })
        assert resp.status_code == 200
        new_ids = {h["hero_id"] for h in resp.json()["heroes"]}

        # IDs should be different (new heroes generated)
        assert old_ids != new_ids
        classes = load_classes_config()
        expected_pool = get_tavern_pool_size({
            cid: {"base_hp": c.base_hp, "base_melee_damage": c.base_melee_damage,
                  "base_ranged_damage": c.base_ranged_damage, "base_armor": c.base_armor,
                  "base_vision_range": c.base_vision_range, "ranged_range": c.ranged_range}
            for cid, c in classes.items()
        })
        assert len(resp.json()["heroes"]) == expected_pool

    def test_tavern_refresh_preserves_gold(self):
        self.client.get("/api/town/profile?username=goldkeeper")
        resp = self.client.post("/api/town/tavern/refresh", json={
            "username": "goldkeeper",
        })
        assert resp.json()["gold"] == STARTING_GOLD

    # --- Full Hiring Workflow ---

    def test_full_hire_workflow(self):
        """End-to-end: create profile → view tavern → hire → check roster → check gold."""
        username = "e2e_player"

        # 1. Get profile (auto-creates)
        resp = self.client.get(f"/api/town/profile?username={username}")
        assert resp.status_code == 200
        assert resp.json()["profile"]["gold"] == STARTING_GOLD

        # 2. View tavern
        resp = self.client.get(f"/api/town/tavern?username={username}")
        heroes = resp.json()["heroes"]
        classes = load_classes_config()
        expected_pool = get_tavern_pool_size({
            cid: {"base_hp": c.base_hp, "base_melee_damage": c.base_melee_damage,
                  "base_ranged_damage": c.base_ranged_damage, "base_armor": c.base_armor,
                  "base_vision_range": c.base_vision_range, "ranged_range": c.ranged_range}
            for cid, c in classes.items()
        })
        assert len(heroes) == expected_pool

        # 3. Hire first hero
        hero = heroes[0]
        resp = self.client.post("/api/town/hire", json={
            "username": username, "hero_id": hero["hero_id"],
        })
        assert resp.status_code == 200
        gold_after = resp.json()["gold"]
        assert gold_after == STARTING_GOLD - hero["hire_cost"]

        # 4. Check roster
        resp = self.client.get(f"/api/town/roster?username={username}")
        roster = resp.json()["heroes"]
        assert len(roster) == 1
        assert roster[0]["name"] == hero["name"]

        # 5. Check profile
        resp = self.client.get(f"/api/town/profile?username={username}")
        assert resp.json()["profile"]["gold"] == gold_after
        assert resp.json()["profile"]["hero_count"] == 1


# ============================================================
# 10. Backward Compatibility
# ============================================================

class TestBackwardCompatibility:
    """Ensure existing arena functionality is not affected."""

    def test_player_state_no_hero_fields(self):
        """PlayerState should work fine without any hero-related fields."""
        from app.models.player import PlayerState, Position
        player = PlayerState(player_id="p1", username="test")
        assert player.hp == 100
        assert player.class_id is None
        assert player.equipment == {}
        assert player.inventory == []

    def test_classes_config_loads(self):
        """classes_config.json still loads correctly."""
        classes = load_classes_config()
        assert len(classes) == 11
        assert "crusader" in classes
        assert "mage" in classes
        assert "bard" in classes
        assert "blood_knight" in classes
        assert "plague_doctor" in classes
        assert "revenant" in classes

    def test_match_models_unchanged(self):
        """MatchState, MatchConfig etc. still work."""
        from app.models.match import MatchState, MatchConfig, MatchType
        config = MatchConfig(map_id="arena_classic", match_type=MatchType.PVP)
        state = MatchState(match_id="test123", config=config)
        assert state.match_id == "test123"
        assert state.config.match_type == MatchType.PVP
