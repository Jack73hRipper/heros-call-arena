"""
Tests for Phase 18A & 18B — Monster Rarity Data Model, Config & Affix Engine.

Phase 18A validates:
- monster_rarity_config.json loads correctly
- Config validation catches structural errors
- All rarity tiers present with correct fields
- All champion types present with correct fields
- All 15 affixes present with required fields (prefixes, suffixes, effects)
- Affix rules reference real affix IDs
- Forbidden combinations reference real affixes
- PlayerState serializes new monster rarity fields correctly
- EnemyDefinition serializes new excluded_affixes / allow_rarity_upgrade fields
- enemies_config.json loads with new fields (backward compat)
- Bosses and training_dummy have allow_rarity_upgrade = false
- Enemies with skill overlap have correct excluded_affixes
- Config cache works (multiple loads return same object)
- Validation rejects bad affix IDs in forbidden combos
- Validation rejects bad affix IDs in ranged_only
- Validation rejects missing required fields

Phase 18B validates:
- roll_monster_rarity() distribution at various floor levels
- roll_monster_rarity() respects min floor requirements
- roll_champion_type() returns valid champion types
- roll_affixes() respects max count, no duplicates
- roll_affixes() respects max aura limit (1 aura max)
- roll_affixes() respects max on-death limit
- roll_affixes() respects forbidden combinations
- roll_affixes() respects enemy excluded_affixes
- roll_affixes() respects ranged_only restrictions
- roll_affixes() respects excludes_class_skills
- generate_rare_name() produces correct format
- generate_rare_name() handles single affix
- generate_rare_name() handles empty affixes
- apply_rarity_to_player() tier HP/damage/armor scaling
- apply_rarity_to_player() champion type stat bonuses
- apply_rarity_to_player() affix stat modifiers (extra_strong, stone_skin, thorns, etc.)
- apply_rarity_to_player() sets metadata fields
- apply_rarity_to_player() recalculates HP to full
- apply_rarity_to_player() handles ward affix buff
- apply_rarity_to_player() handles regenerating affix
- create_minions() produces correct count
- create_minions() links to rare leader
- create_minions() minions are Normal rarity
"""

from __future__ import annotations

import copy
import json
import random
import pytest
from pathlib import Path

from app.models.player import (
    PlayerState,
    Position,
    EnemyDefinition,
    load_enemies_config,
    get_enemy_definition,
    apply_enemy_stats,
)
from app.core.monster_rarity import (
    load_monster_rarity_config,
    clear_monster_rarity_cache,
    validate_monster_rarity_config,
    get_rarity_tier,
    get_champion_type,
    get_champion_type_name,
    get_affix,
    get_all_affix_ids,
    get_affix_rules,
    get_spawn_chances,
    VALID_RARITY_TIERS,
    VALID_CHAMPION_TYPES,
    # Phase 18B
    roll_monster_rarity,
    roll_champion_type,
    roll_affixes,
    generate_rare_name,
    apply_rarity_to_player,
    create_minions,
)


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear monster rarity cache before each test."""
    clear_monster_rarity_cache()
    yield
    clear_monster_rarity_cache()


@pytest.fixture
def config():
    """Load the real monster rarity config."""
    return load_monster_rarity_config()


# ==========================================================
# Section 1: Config Loading
# ==========================================================

class TestConfigLoading:
    """Test that monster_rarity_config.json loads and has expected structure."""

    def test_config_loads_successfully(self, config):
        assert config is not None
        assert isinstance(config, dict)

    def test_config_has_required_top_level_keys(self, config):
        for key in ("rarity_tiers", "champion_types", "affixes", "affix_rules", "spawn_chances"):
            assert key in config, f"Missing top-level key: {key}"

    def test_config_caching(self):
        """Multiple loads return the same cached object."""
        config1 = load_monster_rarity_config()
        config2 = load_monster_rarity_config()
        assert config1 is config2

    def test_cache_clear_forces_reload(self):
        """Clearing cache forces a fresh load."""
        config1 = load_monster_rarity_config()
        clear_monster_rarity_cache()
        config2 = load_monster_rarity_config()
        # Same content but different object after cache clear
        assert config1 is not config2
        assert config1 == config2

    def test_missing_config_raises_error(self, tmp_path):
        """Loading from a non-existent path raises FileNotFoundError."""
        clear_monster_rarity_cache()
        with pytest.raises(FileNotFoundError):
            load_monster_rarity_config(tmp_path / "nonexistent.json")


# ==========================================================
# Section 2: Rarity Tiers
# ==========================================================

class TestRarityTiers:
    """Test rarity tier definitions."""

    def test_all_tiers_present(self, config):
        tiers = config["rarity_tiers"]
        for tier_id in VALID_RARITY_TIERS:
            assert tier_id in tiers, f"Missing rarity tier: {tier_id}"

    def test_normal_tier_values(self):
        tier = get_rarity_tier("normal")
        assert tier is not None
        assert tier["hp_multiplier"] == 1.0
        assert tier["damage_multiplier"] == 1.0
        assert tier["armor_bonus"] == 0
        assert tier["affix_count"] == 0
        assert tier["loot_drop_chance_bonus"] == 0.0
        assert tier["xp_multiplier"] == 1.0

    def test_champion_tier_values(self):
        tier = get_rarity_tier("champion")
        assert tier is not None
        assert tier["hp_multiplier"] == 1.4
        assert tier["damage_multiplier"] == 1.2
        assert tier["armor_bonus"] == 3
        assert tier["name_color"] == "#6688ff"
        assert tier["champion_type_count"] == 1
        assert tier["pack_size"] == [2, 3]
        assert tier["xp_multiplier"] == 1.5

    def test_rare_tier_values(self):
        tier = get_rarity_tier("rare")
        assert tier is not None
        assert tier["hp_multiplier"] == 1.7
        assert tier["damage_multiplier"] == 1.3
        assert tier["armor_bonus"] == 5
        assert tier["name_color"] == "#ffcc00"
        assert tier["affix_count"] == [2, 3]
        assert tier["minion_count"] == [2, 3]
        assert tier["loot_guaranteed_rarity"] == "magic"
        assert tier["xp_multiplier"] == 2.0

    def test_super_unique_tier_values(self):
        tier = get_rarity_tier("super_unique")
        assert tier is not None
        # Super unique has hand-tuned stats (null multipliers)
        assert tier["hp_multiplier"] is None
        assert tier["damage_multiplier"] is None
        assert tier["armor_bonus"] is None
        assert tier["name_color"] == "#cc66ff"
        assert tier["loot_guaranteed_rarity"] == "rare"
        assert tier["xp_multiplier"] == 3.0

    def test_nonexistent_tier_returns_none(self):
        assert get_rarity_tier("legendary") is None

    def test_each_tier_has_name_color(self, config):
        for tier_id, tier_data in config["rarity_tiers"].items():
            assert "name_color" in tier_data, f"Tier {tier_id} missing name_color"
            assert tier_data["name_color"].startswith("#"), f"Tier {tier_id} name_color not hex"


# ==========================================================
# Section 3: Champion Types
# ==========================================================

class TestChampionTypes:
    """Test champion type definitions."""

    def test_all_champion_types_present(self, config):
        types = config["champion_types"]
        for ct_id in VALID_CHAMPION_TYPES:
            assert ct_id in types, f"Missing champion type: {ct_id}"

    def test_berserker_type(self):
        ct = get_champion_type("berserker")
        assert ct is not None
        assert ct["damage_bonus"] == 0.30
        assert ct["enrage_threshold"] == 0.30
        assert ct["enrage_damage_bonus"] == 0.50
        assert ct["visual_tint"] == "#ff4444"

    def test_fanatic_type(self):
        ct = get_champion_type("fanatic")
        assert ct is not None
        assert ct["cooldown_reduction"] == 1

    def test_ghostly_type(self):
        ct = get_champion_type("ghostly")
        assert ct is not None
        assert ct["dodge_chance"] == 0.25
        assert ct["phase_through_units"] is True

    def test_resilient_type(self):
        ct = get_champion_type("resilient")
        assert ct is not None
        assert ct["hp_multiplier"] == 1.5
        assert ct["armor_bonus"] == 5

    def test_possessed_type(self):
        ct = get_champion_type("possessed")
        assert ct is not None
        assert ct["death_explosion_damage"] == 15
        assert ct["death_explosion_radius"] == 1

    def test_nonexistent_champion_type_returns_none(self):
        assert get_champion_type("vampiric") is None

    def test_each_type_has_visual_tint(self, config):
        for ct_id, ct_data in config["champion_types"].items():
            assert "visual_tint" in ct_data, f"Champion type {ct_id} missing visual_tint"


# ==========================================================
# Section 4: Affixes
# ==========================================================

class TestAffixes:
    """Test affix definitions."""

    EXPECTED_AFFIXES = [
        "extra_strong", "extra_fast", "might_aura", "cursed",
        "stone_skin", "spectral_hit", "shielded", "teleporter",
        "fire_enchanted", "cold_enchanted", "thorns", "mana_burn",
        "conviction_aura", "multishot", "regenerating",
    ]

    def test_all_15_affixes_present(self, config):
        affixes = config["affixes"]
        assert len(affixes) == 15
        for affix_id in self.EXPECTED_AFFIXES:
            assert affix_id in affixes, f"Missing affix: {affix_id}"

    def test_get_all_affix_ids(self):
        ids = get_all_affix_ids()
        assert len(ids) == 15
        assert set(ids) == set(self.EXPECTED_AFFIXES)

    def test_each_affix_has_required_fields(self, config):
        for affix_id, affix_data in config["affixes"].items():
            assert affix_data["affix_id"] == affix_id
            assert "name" in affix_data
            assert "category" in affix_data
            assert isinstance(affix_data.get("effects", []), list)
            assert len(affix_data["effects"]) >= 1
            assert isinstance(affix_data.get("prefixes", []), list)
            assert len(affix_data["prefixes"]) >= 1
            assert isinstance(affix_data.get("suffixes", []), list)
            assert len(affix_data["suffixes"]) >= 1

    def test_extra_strong_affix(self):
        affix = get_affix("extra_strong")
        assert affix is not None
        assert affix["category"] == "offensive"
        effect = affix["effects"][0]
        assert effect["type"] == "stat_multiplier"
        assert effect["stat"] == "attack_damage"
        assert effect["value"] == 1.3

    def test_fire_enchanted_is_on_death(self):
        affix = get_affix("fire_enchanted")
        assert affix is not None
        assert affix["category"] == "on_death"
        effect = affix["effects"][0]
        assert effect["type"] == "on_death_explosion"
        assert effect["damage"] == 20
        assert effect["radius"] == 2

    def test_might_aura_is_aura(self):
        affix = get_affix("might_aura")
        assert affix is not None
        assert affix.get("is_aura") is True

    def test_conviction_aura_is_aura(self):
        affix = get_affix("conviction_aura")
        assert affix is not None
        assert affix.get("is_aura") is True

    def test_teleporter_excludes_shadow_step(self):
        affix = get_affix("teleporter")
        assert affix is not None
        assert "shadow_step" in affix.get("excludes_class_skills", [])

    def test_multishot_is_ranged_only(self):
        affix = get_affix("multishot")
        assert affix is not None
        assert affix.get("applies_to") == "ranged_only"

    def test_nonexistent_affix_returns_none(self):
        assert get_affix("lightning_enchanted") is None

    def test_aura_affixes_identified(self, config):
        """Exactly 2 aura affixes: might_aura and conviction_aura."""
        aura_ids = [
            aid for aid, adata in config["affixes"].items()
            if adata.get("is_aura")
        ]
        assert set(aura_ids) == {"might_aura", "conviction_aura"}

    def test_on_death_affixes_identified(self, config):
        """Exactly 1 on_death category affix: fire_enchanted."""
        on_death_ids = [
            aid for aid, adata in config["affixes"].items()
            if adata["category"] == "on_death"
        ]
        assert set(on_death_ids) == {"fire_enchanted"}


# ==========================================================
# Section 5: Affix Rules
# ==========================================================

class TestAffixRules:
    """Test affix compatibility rules."""

    def test_rules_exist(self):
        rules = get_affix_rules()
        assert rules is not None
        assert isinstance(rules, dict)

    def test_max_affixes_is_3(self):
        rules = get_affix_rules()
        assert rules["max_affixes"] == 3

    def test_max_auras_is_1(self):
        rules = get_affix_rules()
        assert rules["max_auras"] == 1

    def test_max_on_death_is_1(self):
        rules = get_affix_rules()
        assert rules["max_on_death"] == 1

    def test_forbidden_combinations(self):
        rules = get_affix_rules()
        combos = rules["forbidden_combinations"]
        assert len(combos) >= 1
        # Might aura + conviction aura is forbidden
        assert ["might_aura", "conviction_aura"] in combos

    def test_ranged_only_affixes(self):
        rules = get_affix_rules()
        assert "multishot" in rules["ranged_only_affixes"]

    def test_all_forbidden_combo_ids_exist(self, config):
        all_ids = set(config["affixes"].keys())
        rules = config["affix_rules"]
        for combo in rules["forbidden_combinations"]:
            for affix_id in combo:
                assert affix_id in all_ids, f"Forbidden combo has unknown affix: {affix_id}"

    def test_all_ranged_only_ids_exist(self, config):
        all_ids = set(config["affixes"].keys())
        for affix_id in config["affix_rules"]["ranged_only_affixes"]:
            assert affix_id in all_ids, f"ranged_only_affixes has unknown: {affix_id}"


# ==========================================================
# Section 6: Spawn Chances
# ==========================================================

class TestSpawnChances:
    """Test spawn chance configuration."""

    def test_spawn_chances_exist(self):
        chances = get_spawn_chances()
        assert chances is not None

    def test_base_champion_chance(self):
        chances = get_spawn_chances()
        assert chances["champion_base_chance"] == 0.04

    def test_base_rare_chance(self):
        chances = get_spawn_chances()
        assert chances["rare_base_chance"] == 0.02

    def test_floor_bonus(self):
        chances = get_spawn_chances()
        assert chances["floor_bonus_per_level"] == 0.01

    def test_max_enhanced_per_room(self):
        chances = get_spawn_chances()
        assert chances["max_enhanced_per_room"] == 2

    def test_min_floor_for_champions(self):
        chances = get_spawn_chances()
        assert chances["min_floor_for_champions"] == 2

    def test_min_floor_for_rares(self):
        chances = get_spawn_chances()
        assert chances["min_floor_for_rares"] == 4


# ==========================================================
# Section 7: PlayerState Model Fields
# ==========================================================

class TestPlayerStateFields:
    """Test new Phase 18A fields on PlayerState."""

    def test_default_values(self):
        p = PlayerState(player_id="test-1", username="Tester")
        assert p.monster_rarity is None
        assert p.champion_type is None
        assert p.affixes == []
        assert p.display_name is None
        assert p.minion_owner_id is None
        assert p.is_minion is False

    def test_set_monster_rarity_fields(self):
        p = PlayerState(
            player_id="test-1",
            username="Tester",
            monster_rarity="rare",
            champion_type=None,
            affixes=["extra_strong", "fire_enchanted"],
            display_name="Brutal Skeleton the Pyreborn",
            minion_owner_id=None,
            is_minion=False,
        )
        assert p.monster_rarity == "rare"
        assert p.affixes == ["extra_strong", "fire_enchanted"]
        assert p.display_name == "Brutal Skeleton the Pyreborn"

    def test_set_champion_fields(self):
        p = PlayerState(
            player_id="champ-1",
            username="Berserker Demon",
            monster_rarity="champion",
            champion_type="berserker",
            display_name="Berserker Demon",
        )
        assert p.monster_rarity == "champion"
        assert p.champion_type == "berserker"
        assert p.display_name == "Berserker Demon"

    def test_set_minion_fields(self):
        p = PlayerState(
            player_id="minion-1",
            username="Skeleton",
            monster_rarity="normal",
            is_minion=True,
            minion_owner_id="rare-leader-1",
        )
        assert p.is_minion is True
        assert p.minion_owner_id == "rare-leader-1"

    def test_serialization_includes_rarity_fields(self):
        p = PlayerState(
            player_id="test-1",
            username="Tester",
            monster_rarity="champion",
            champion_type="ghostly",
            affixes=[],
            display_name="Ghostly Skeleton",
        )
        data = p.model_dump()
        assert data["monster_rarity"] == "champion"
        assert data["champion_type"] == "ghostly"
        assert data["affixes"] == []
        assert data["display_name"] == "Ghostly Skeleton"
        assert data["minion_owner_id"] is None
        assert data["is_minion"] is False

    def test_json_roundtrip(self):
        p = PlayerState(
            player_id="test-1",
            username="Tester",
            monster_rarity="rare",
            affixes=["stone_skin", "thorns", "cold_enchanted"],
            display_name="Iron Skeleton the Chilling",
        )
        json_str = p.model_dump_json()
        p2 = PlayerState.model_validate_json(json_str)
        assert p2.monster_rarity == "rare"
        assert p2.affixes == ["stone_skin", "thorns", "cold_enchanted"]
        assert p2.display_name == "Iron Skeleton the Chilling"


# ==========================================================
# Section 8: EnemyDefinition Model Fields
# ==========================================================

class TestEnemyDefinitionFields:
    """Test new Phase 18A fields on EnemyDefinition."""

    def test_default_values(self):
        e = EnemyDefinition(enemy_id="test", name="Test", role="Test")
        assert e.excluded_affixes == []
        assert e.allow_rarity_upgrade is True

    def test_set_excluded_affixes(self):
        e = EnemyDefinition(
            enemy_id="construct",
            name="Construct",
            role="Tank",
            excluded_affixes=["shielded"],
            allow_rarity_upgrade=True,
        )
        assert e.excluded_affixes == ["shielded"]

    def test_set_allow_rarity_upgrade_false(self):
        e = EnemyDefinition(
            enemy_id="training_dummy",
            name="Training Dummy",
            role="Target Dummy",
            allow_rarity_upgrade=False,
        )
        assert e.allow_rarity_upgrade is False


# ==========================================================
# Section 9: enemies_config.json Integration
# ==========================================================

class TestEnemiesConfigIntegration:
    """Test that enemies_config.json loads with new Phase 18A fields."""

    def test_training_dummy_no_rarity_upgrade(self):
        enemy = get_enemy_definition("training_dummy")
        assert enemy is not None
        assert enemy.allow_rarity_upgrade is False

    def test_bosses_no_rarity_upgrade(self):
        """All is_boss enemies should have allow_rarity_upgrade=false."""
        boss_ids = ["undead_knight", "reaper", "demon_boss", "construct_boss", "necromancer"]
        for boss_id in boss_ids:
            enemy = get_enemy_definition(boss_id)
            assert enemy is not None, f"Boss {boss_id} not found"
            assert enemy.is_boss is True, f"{boss_id} should be is_boss=True"
            assert enemy.allow_rarity_upgrade is False, f"{boss_id} should not allow rarity upgrade"

    def test_construct_excludes_shielded(self):
        enemy = get_enemy_definition("construct")
        assert enemy is not None
        assert "shielded" in enemy.excluded_affixes

    def test_construct_boss_excludes_shielded(self):
        enemy = get_enemy_definition("construct_boss")
        assert enemy is not None
        assert "shielded" in enemy.excluded_affixes

    def test_wraith_excludes_teleporter(self):
        enemy = get_enemy_definition("wraith")
        assert enemy is not None
        assert "teleporter" in enemy.excluded_affixes

    def test_horror_excludes_teleporter(self):
        enemy = get_enemy_definition("horror")
        assert enemy is not None
        assert "teleporter" in enemy.excluded_affixes

    def test_shade_excludes_teleporter(self):
        enemy = get_enemy_definition("shade")
        assert enemy is not None
        assert "teleporter" in enemy.excluded_affixes

    def test_normal_enemies_default_allow_upgrade(self):
        """Regular enemies (not bosses/dummies) should allow rarity upgrade."""
        normal_ids = ["demon", "skeleton", "imp", "ghoul", "goblin_spearman"]
        for enemy_id in normal_ids:
            enemy = get_enemy_definition(enemy_id)
            assert enemy is not None, f"Enemy {enemy_id} not found"
            assert enemy.allow_rarity_upgrade is True, f"{enemy_id} should allow rarity upgrade"

    def test_all_existing_enemies_still_load(self):
        """Backward compat — all 24 enemies still load with new fields."""
        enemies = load_enemies_config()
        assert len(enemies) >= 24, f"Expected at least 24 enemies, got {len(enemies)}"
        for eid, edef in enemies.items():
            assert isinstance(edef.excluded_affixes, list)
            assert isinstance(edef.allow_rarity_upgrade, bool)

    def test_apply_enemy_stats_still_works(self):
        """Applying enemy stats to a PlayerState still works with new fields."""
        p = PlayerState(player_id="test-1", username="Test")
        result = apply_enemy_stats(p, "skeleton")
        assert result is True
        assert p.enemy_type == "skeleton"
        assert p.hp == 125
        assert p.ranged_range == 5
        # New fields should still be default (not set by apply_enemy_stats)
        assert p.monster_rarity is None
        assert p.affixes == []


# ==========================================================
# Section 10: Config Validation
# ==========================================================

class TestConfigValidation:
    """Test validate_monster_rarity_config catches errors."""

    def test_valid_config_has_no_errors(self, config):
        errors = validate_monster_rarity_config(config)
        assert errors == [], f"Unexpected validation errors: {errors}"

    def test_missing_rarity_tiers(self):
        bad_config = {"champion_types": {}, "affixes": {}, "affix_rules": {}, "spawn_chances": {}}
        errors = validate_monster_rarity_config(bad_config)
        assert any("No rarity_tiers" in e for e in errors)

    def test_unknown_rarity_tier(self, config):
        bad = copy.deepcopy(config)
        bad["rarity_tiers"]["legendary"] = {"tier_id": "legendary", "name": "Legendary", "name_color": "#ff0000"}
        errors = validate_monster_rarity_config(bad)
        assert any("Unknown rarity tier: 'legendary'" in e for e in errors)

    def test_mismatched_tier_id(self, config):
        bad = copy.deepcopy(config)
        bad["rarity_tiers"]["normal"]["tier_id"] = "wrong"
        errors = validate_monster_rarity_config(bad)
        assert any("mismatched tier_id" in e for e in errors)

    def test_unknown_champion_type(self, config):
        bad = copy.deepcopy(config)
        bad["champion_types"]["vampiric"] = {"type_id": "vampiric", "name": "Vampiric", "visual_tint": "#ff0000"}
        errors = validate_monster_rarity_config(bad)
        assert any("Unknown champion type: 'vampiric'" in e for e in errors)

    def test_mismatched_affix_id(self, config):
        bad = copy.deepcopy(config)
        bad["affixes"]["extra_strong"]["affix_id"] = "wrong_id"
        errors = validate_monster_rarity_config(bad)
        assert any("mismatched affix_id" in e for e in errors)

    def test_missing_affix_effects(self, config):
        bad = copy.deepcopy(config)
        bad["affixes"]["extra_strong"]["effects"] = []
        errors = validate_monster_rarity_config(bad)
        assert any("at least one effect" in e for e in errors)

    def test_missing_affix_prefixes(self, config):
        bad = copy.deepcopy(config)
        bad["affixes"]["extra_strong"]["prefixes"] = []
        errors = validate_monster_rarity_config(bad)
        assert any("at least one prefix" in e for e in errors)

    def test_missing_affix_suffixes(self, config):
        bad = copy.deepcopy(config)
        bad["affixes"]["extra_strong"]["suffixes"] = []
        errors = validate_monster_rarity_config(bad)
        assert any("at least one suffix" in e for e in errors)

    def test_forbidden_combo_bad_affix(self, config):
        bad = copy.deepcopy(config)
        bad["affix_rules"]["forbidden_combinations"].append(["extra_strong", "nonexistent_affix"])
        errors = validate_monster_rarity_config(bad)
        assert any("nonexistent_affix" in e for e in errors)

    def test_ranged_only_bad_affix(self, config):
        bad = copy.deepcopy(config)
        bad["affix_rules"]["ranged_only_affixes"].append("fake_affix")
        errors = validate_monster_rarity_config(bad)
        assert any("fake_affix" in e for e in errors)

    def test_missing_spawn_chances(self):
        bad_config = {
            "rarity_tiers": {"normal": {"tier_id": "normal", "name": "Normal", "name_color": "#fff"}},
            "champion_types": {"berserker": {"type_id": "berserker", "name": "Berserker", "visual_tint": "#f00"}},
            "affixes": {"extra_strong": {
                "affix_id": "extra_strong", "name": "Extra Strong", "category": "offensive",
                "effects": [{"type": "stat_multiplier"}], "prefixes": ["Mighty"], "suffixes": ["of Ruin"]
            }},
            "affix_rules": {},
            "spawn_chances": {},
        }
        errors = validate_monster_rarity_config(bad_config)
        assert any("No spawn_chances" in e or "spawn_chances missing" in e for e in errors)

    def test_missing_required_spawn_fields(self, config):
        bad = copy.deepcopy(config)
        del bad["spawn_chances"]["champion_base_chance"]
        errors = validate_monster_rarity_config(bad)
        assert any("champion_base_chance" in e for e in errors)


# ==========================================================
# Section 7: Phase 18B — Roll Monster Rarity
# ==========================================================

class TestRollMonsterRarity:
    """Test the rarity rolling function with floor scaling."""

    def test_floor_0_always_normal(self):
        """Floor 0 is below min_floor for both champion and rare."""
        rng = random.Random(42)
        results = [roll_monster_rarity(0, rng) for _ in range(200)]
        assert all(r == "normal" for r in results)

    def test_floor_1_always_normal(self):
        """Floor 1 is below min_floor_for_champions (2), so always normal."""
        rng = random.Random(12345)
        results = [roll_monster_rarity(1, rng) for _ in range(1000)]
        assert all(r == "normal" for r in results)

    def test_floor_2_can_roll_champion(self):
        """Floor 2 meets min_floor_for_champions, so champions are possible."""
        rng = random.Random(12345)
        results = [roll_monster_rarity(2, rng) for _ in range(1000)]
        assert "champion" in results
        assert "rare" not in results  # Floor 2 < min_floor_for_rares (4)

    def test_floor_3_no_rare(self):
        """Floor 3 is below min_floor_for_rares (4)."""
        rng = random.Random(99)
        results = [roll_monster_rarity(3, rng) for _ in range(1000)]
        assert "rare" not in results

    def test_floor_4_can_roll_rare(self):
        """Floor 4 meets min_floor_for_rares."""
        rng = random.Random(42)
        results = [roll_monster_rarity(4, rng) for _ in range(1000)]
        assert "rare" in results

    def test_high_floor_higher_rates(self):
        """Higher floors should produce more enhanced enemies."""
        low_floor = [roll_monster_rarity(3, random.Random(i)) for i in range(2000)]
        high_floor = [roll_monster_rarity(9, random.Random(i + 10000)) for i in range(2000)]
        low_enhanced = sum(1 for r in low_floor if r != "normal")
        high_enhanced = sum(1 for r in high_floor if r != "normal")
        assert high_enhanced > low_enhanced

    def test_returns_valid_strings(self):
        """All returned values are valid rarity strings."""
        rng = random.Random(42)
        for floor in range(0, 15):
            result = roll_monster_rarity(floor, rng)
            assert result in ("normal", "champion", "rare")

    def test_deterministic_with_same_seed(self):
        """Same seed produces same results."""
        results1 = [roll_monster_rarity(5, random.Random(42)) for _ in range(10)]
        results2 = [roll_monster_rarity(5, random.Random(42)) for _ in range(10)]
        assert results1 == results2

    def test_distribution_floor_5(self):
        """Floor 5 should have roughly expected rates (statistical, loose bounds)."""
        # Base rates: champion=0.08, rare=0.03, floor_bonus=0.05
        # Expected: rare ~8%, champion ~13%, normal ~79%
        results = [roll_monster_rarity(5, random.Random(i)) for i in range(5000)]
        normal_pct = results.count("normal") / len(results)
        champion_pct = results.count("champion") / len(results)
        rare_pct = results.count("rare") / len(results)
        # Loose bounds to avoid flaky tests
        assert 0.60 < normal_pct < 0.95, f"Normal: {normal_pct:.2%}"
        assert 0.02 < champion_pct < 0.30, f"Champion: {champion_pct:.2%}"
        assert 0.01 < rare_pct < 0.20, f"Rare: {rare_pct:.2%}"


# ==========================================================
# Section 8: Phase 18B — Roll Champion Type
# ==========================================================

class TestRollChampionType:
    """Test champion type random selection."""

    def test_returns_valid_type(self):
        rng = random.Random(42)
        for _ in range(50):
            ct = roll_champion_type(rng)
            assert ct in VALID_CHAMPION_TYPES

    def test_all_types_appear_over_many_rolls(self):
        """With enough rolls, all 5 champion types should appear."""
        rng = random.Random(42)
        results = set(roll_champion_type(rng) for _ in range(200))
        assert results == VALID_CHAMPION_TYPES

    def test_deterministic_with_same_seed(self):
        assert roll_champion_type(random.Random(42)) == roll_champion_type(random.Random(42))


# ==========================================================
# Section 9: Phase 18B — Roll Affixes
# ==========================================================

class TestRollAffixes:
    """Test affix rolling with compatibility rules."""

    def _make_enemy_def(self, **overrides):
        """Helper to create a minimal EnemyDefinition for testing."""
        defaults = {
            "enemy_id": "test_enemy",
            "name": "Test Enemy",
            "role": "melee",
            "excluded_affixes": [],
            "ranged_range": 1,
            "class_id": None,
        }
        defaults.update(overrides)
        return EnemyDefinition(**defaults)

    def test_returns_requested_count(self):
        enemy = self._make_enemy_def()
        rng = random.Random(42)
        result = roll_affixes(enemy, 2, rng)
        assert len(result) == 2

    def test_returns_max_3(self):
        """Even if requesting more than max_affixes (3), caps at 3."""
        enemy = self._make_enemy_def()
        rng = random.Random(42)
        result = roll_affixes(enemy, 5, rng)
        assert len(result) <= 3

    def test_no_duplicates(self):
        enemy = self._make_enemy_def()
        rng = random.Random(42)
        result = roll_affixes(enemy, 3, rng)
        assert len(result) == len(set(result))

    def test_respects_excluded_affixes(self):
        """Enemy with excluded_affixes should never get those."""
        enemy = self._make_enemy_def(excluded_affixes=["extra_strong", "stone_skin", "thorns"])
        rng = random.Random(42)
        for _ in range(50):
            result = roll_affixes(enemy, 3, random.Random(rng.randint(0, 99999)))
            assert "extra_strong" not in result
            assert "stone_skin" not in result
            assert "thorns" not in result

    def test_ranged_only_excluded_for_melee(self):
        """Melee enemies (ranged_range=1) should not get multishot."""
        enemy = self._make_enemy_def(ranged_range=1)
        rng = random.Random(42)
        for _ in range(100):
            result = roll_affixes(enemy, 3, random.Random(rng.randint(0, 99999)))
            assert "multishot" not in result

    def test_ranged_can_get_multishot(self):
        """Ranged enemies (ranged_range>1) can get multishot."""
        enemy = self._make_enemy_def(ranged_range=5)
        all_affixes = []
        for i in range(200):
            result = roll_affixes(enemy, 3, random.Random(i))
            all_affixes.extend(result)
        assert "multishot" in all_affixes

    def test_max_one_aura(self):
        """Should never have both might_aura and conviction_aura."""
        enemy = self._make_enemy_def()
        config = load_monster_rarity_config()
        aura_ids = [aid for aid, a in config["affixes"].items() if a.get("is_aura")]
        for i in range(500):
            result = roll_affixes(enemy, 3, random.Random(i))
            auras_in_result = [r for r in result if r in aura_ids]
            assert len(auras_in_result) <= 1, f"Multiple auras: {auras_in_result}"

    def test_max_one_on_death(self):
        """Should never have more than 1 on_death affix."""
        enemy = self._make_enemy_def()
        config = load_monster_rarity_config()
        on_death_ids = [aid for aid, a in config["affixes"].items() if a.get("category") == "on_death"]
        for i in range(500):
            result = roll_affixes(enemy, 3, random.Random(i))
            on_death_in_result = [r for r in result if r in on_death_ids]
            assert len(on_death_in_result) <= 1, f"Multiple on_death: {on_death_in_result}"

    def test_forbidden_combinations(self):
        """might_aura and conviction_aura should never appear together."""
        enemy = self._make_enemy_def()
        for i in range(500):
            result = roll_affixes(enemy, 3, random.Random(i))
            assert not ("might_aura" in result and "conviction_aura" in result), \
                f"Forbidden combo found: {result}"

    def test_excludes_class_skills_teleporter(self):
        """Wraith (has shadow_step) should not get teleporter affix."""
        # Wraith's class skills include shadow_step
        enemy = self._make_enemy_def(
            enemy_id="wraith",
            class_id="wraith",
            excluded_affixes=["teleporter"],  # Also in config
        )
        for i in range(200):
            result = roll_affixes(enemy, 3, random.Random(i))
            assert "teleporter" not in result

    def test_handles_none_enemy_def(self):
        """Should work (with defaults) even with None enemy_def."""
        rng = random.Random(42)
        result = roll_affixes(None, 2, rng)
        assert isinstance(result, list)
        assert len(result) <= 2

    def test_zero_count_returns_empty(self):
        enemy = self._make_enemy_def()
        result = roll_affixes(enemy, 0, random.Random(42))
        assert result == []

    def test_all_affixes_can_appear(self):
        """Over many rolls, every non-excluded affix should appear at least once."""
        enemy = self._make_enemy_def(ranged_range=5)  # Ranged so multishot eligible
        seen = set()
        for i in range(2000):
            result = roll_affixes(enemy, 3, random.Random(i))
            seen.update(result)
        all_ids = set(get_all_affix_ids())
        # All affixes should eventually appear for this unrestricted enemy
        assert seen == all_ids, f"Missing affixes: {all_ids - seen}"


# ==========================================================
# Section 10: Phase 18B — Generate Rare Name
# ==========================================================

class TestGenerateRareName:
    """Test D2-style rare name generation."""

    def test_basic_format(self):
        """Name should contain prefix, base name, and suffix."""
        rng = random.Random(42)
        name = generate_rare_name("Skeleton", ["extra_strong", "fire_enchanted"], rng)
        assert "Skeleton" in name
        # Should have a prefix before base name
        parts = name.split("Skeleton")
        assert len(parts[0].strip()) > 0  # Prefix exists
        assert len(parts[1].strip()) > 0  # Suffix exists

    def test_single_affix(self):
        """With one affix, both prefix and suffix come from that affix."""
        rng = random.Random(42)
        name = generate_rare_name("Demon", ["stone_skin"], rng)
        assert "Demon" in name
        # Prefix should be from stone_skin prefixes
        config = load_monster_rarity_config()
        prefixes = config["affixes"]["stone_skin"]["prefixes"]
        prefix_found = any(name.startswith(p) for p in prefixes)
        assert prefix_found, f"No stone_skin prefix found in '{name}'"

    def test_empty_affixes_returns_base(self):
        rng = random.Random(42)
        assert generate_rare_name("Goblin", [], rng) == "Goblin"

    def test_prefix_from_first_affix(self):
        """Prefix should come from the first affix's prefix pool."""
        config = load_monster_rarity_config()
        first_prefixes = config["affixes"]["extra_strong"]["prefixes"]
        rng = random.Random(42)
        name = generate_rare_name("Imp", ["extra_strong", "cold_enchanted"], rng)
        assert any(name.startswith(p) for p in first_prefixes), \
            f"Name '{name}' doesn't start with any of {first_prefixes}"

    def test_suffix_from_second_affix(self):
        """Suffix should come from the second affix's suffix pool."""
        config = load_monster_rarity_config()
        second_suffixes = config["affixes"]["cold_enchanted"]["suffixes"]
        rng = random.Random(42)
        name = generate_rare_name("Imp", ["extra_strong", "cold_enchanted"], rng)
        assert any(s in name for s in second_suffixes), \
            f"Name '{name}' doesn't contain any of {second_suffixes}"

    def test_deterministic(self):
        name1 = generate_rare_name("Demon", ["thorns", "cursed"], random.Random(42))
        name2 = generate_rare_name("Demon", ["thorns", "cursed"], random.Random(42))
        assert name1 == name2

    def test_various_enemies(self):
        """Test name generation for several enemy types."""
        for base in ("Skeleton", "Demon", "Imp", "Ghoul", "Wraith"):
            name = generate_rare_name(base, ["extra_strong", "fire_enchanted"], random.Random(42))
            assert base in name
            assert len(name) > len(base)


# ==========================================================
# Section 11: Phase 18B — Apply Rarity to Player
# ==========================================================

class TestApplyRarityToPlayer:
    """Test stat application for each rarity tier and modifier type."""

    def _make_player(self, **overrides):
        """Helper to create a test PlayerState."""
        defaults = {
            "player_id": "test_enemy_1",
            "username": "enemy_ai",
            "hp": 100,
            "max_hp": 100,
            "attack_damage": 20,
            "ranged_damage": 0,
            "armor": 5,
        }
        defaults.update(overrides)
        return PlayerState(**defaults)

    # --- Tier scaling ---

    def test_normal_no_stat_changes(self):
        """Normal rarity should not change any stats."""
        p = self._make_player()
        apply_rarity_to_player(p, "normal")
        assert p.max_hp == 100
        assert p.hp == 100
        assert p.attack_damage == 20
        assert p.armor == 5
        assert p.monster_rarity == "normal"

    def test_champion_tier_scaling(self):
        """Champion: HP x1.4, damage x1.2, armor +3."""
        p = self._make_player()
        apply_rarity_to_player(p, "champion")
        assert p.max_hp == 140  # 100 * 1.4
        assert p.hp == 140
        assert p.attack_damage == 24  # 20 * 1.2
        assert p.armor == 8  # 5 + 3
        assert p.monster_rarity == "champion"

    def test_rare_tier_scaling(self):
        """Rare: HP x1.7, damage x1.3, armor +5."""
        p = self._make_player()
        apply_rarity_to_player(p, "rare")
        assert p.max_hp == 170  # 100 * 1.7
        assert p.hp == 170
        assert p.attack_damage == 26  # 20 * 1.3
        assert p.armor == 10  # 5 + 5
        assert p.monster_rarity == "rare"

    def test_rare_with_ranged_damage(self):
        """Rare tier should also scale ranged_damage if > 0."""
        p = self._make_player(ranged_damage=10)
        apply_rarity_to_player(p, "rare")
        assert p.ranged_damage == 13  # 10 * 1.3

    def test_super_unique_null_multipliers(self):
        """Super unique has null multipliers — no stat changes from tier alone."""
        p = self._make_player()
        apply_rarity_to_player(p, "super_unique")
        assert p.max_hp == 100  # null multiplier -> no change
        assert p.attack_damage == 20
        assert p.armor == 5
        assert p.monster_rarity == "super_unique"

    # --- Champion type bonuses ---

    def test_berserker_champion_damage(self):
        """Berserker champion: +30% damage on top of tier scaling."""
        p = self._make_player()
        apply_rarity_to_player(p, "champion", champion_type="berserker")
        # Tier: damage 20*1.2=24, then berserker +30%: 24*1.3=31.2->31
        assert p.attack_damage == 31
        assert p.champion_type == "berserker"

    def test_resilient_champion_extra_hp_and_armor(self):
        """Resilient: HP x1.5 extra, +5 armor extra."""
        p = self._make_player()
        apply_rarity_to_player(p, "champion", champion_type="resilient")
        # Tier HP: 100*1.4=140, then resilient x1.5: 140*1.5=210
        assert p.max_hp == 210
        assert p.hp == 210
        # Tier armor: 5+3=8, then resilient +5: 13
        assert p.armor == 13

    def test_ghostly_champion_dodge(self):
        """Ghostly: 25% dodge chance."""
        p = self._make_player()
        apply_rarity_to_player(p, "champion", champion_type="ghostly")
        assert p.dodge_chance == 0.25

    def test_fanatic_champion_no_stat_changes(self):
        """Fanatic: cooldown reduction is combat-time, no stat changes at spawn beyond tier."""
        p = self._make_player()
        apply_rarity_to_player(p, "champion", champion_type="fanatic")
        # Only tier scaling, no extra stat bonuses
        assert p.max_hp == 140
        assert p.attack_damage == 24

    def test_possessed_champion_no_stat_changes(self):
        """Possessed: on-death explosion is combat-time, no stat changes at spawn beyond tier."""
        p = self._make_player()
        apply_rarity_to_player(p, "champion", champion_type="possessed")
        assert p.max_hp == 140
        assert p.attack_damage == 24

    # --- Affix stat modifiers ---

    def test_extra_strong_affix(self):
        """Extra Strong: attack_damage x1.3."""
        p = self._make_player()
        apply_rarity_to_player(p, "rare", affixes=["extra_strong"])
        # Tier: 20*1.3=26, then extra_strong x1.3: 26*1.3=33.8->33
        assert p.attack_damage == 33

    def test_extra_strong_scales_ranged_too(self):
        """Extra Strong should scale ranged_damage if > 0."""
        p = self._make_player(ranged_damage=10)
        apply_rarity_to_player(p, "rare", affixes=["extra_strong"])
        # Tier: 10*1.3=13, then extra_strong x1.3: 13*1.3=16.9->16
        assert p.ranged_damage == 16

    def test_stone_skin_affix(self):
        """Stone Skin: armor x1.5."""
        p = self._make_player()
        apply_rarity_to_player(p, "rare", affixes=["stone_skin"])
        # Tier: 5+5=10, then stone_skin x1.5: 10*1.5=15
        assert p.armor == 15

    def test_thorns_affix(self):
        """Thorns: set thorns stat to 8."""
        p = self._make_player()
        apply_rarity_to_player(p, "rare", affixes=["thorns"])
        assert p.thorns == 8

    def test_regenerating_affix(self):
        """Regenerating: 3% max HP as hp_regen per turn."""
        p = self._make_player()
        apply_rarity_to_player(p, "rare", affixes=["regenerating"])
        # Tier HP: 100*1.7=170, 3% of 170 = 5.1 -> 5
        assert p.hp_regen == 5

    def test_spectral_hit_affix(self):
        """Spectral Hit: 20% life steal stored as life_on_hit."""
        p = self._make_player()
        apply_rarity_to_player(p, "rare", affixes=["spectral_hit"])
        assert p.life_on_hit == 20  # 0.20 * 100

    def test_shielded_affix_ward_buff(self):
        """Shielded: should add a ward buff to active_buffs."""
        p = self._make_player()
        apply_rarity_to_player(p, "rare", affixes=["shielded"])
        ward_buffs = [b for b in p.active_buffs if b.get("source") == "affix_shielded"]
        assert len(ward_buffs) == 1
        ward = ward_buffs[0]
        assert ward["magnitude"] == 3  # 3 charges
        assert ward["reflect_damage"] == 10
        assert ward["turns_remaining"] == -1  # Permanent

    def test_multiple_affixes_stack(self):
        """Multiple affixes should stack correctly."""
        p = self._make_player()
        apply_rarity_to_player(p, "rare", affixes=["extra_strong", "stone_skin", "thorns"])
        # Damage: 20*1.3=26 (tier), 26*1.3=33.8->33 (extra_strong)
        assert p.attack_damage == 33
        # Armor: 5+5=10 (tier), 10*1.5=15 (stone_skin)
        assert p.armor == 15
        # Thorns: 8
        assert p.thorns == 8

    # --- Metadata fields ---

    def test_sets_metadata_fields(self):
        p = self._make_player()
        apply_rarity_to_player(
            p, "rare",
            champion_type=None,
            affixes=["extra_strong", "fire_enchanted"],
            display_name="Mighty Skeleton the Pyreborn",
        )
        assert p.monster_rarity == "rare"
        assert p.champion_type is None
        assert p.affixes == ["extra_strong", "fire_enchanted"]
        assert p.display_name == "Mighty Skeleton the Pyreborn"

    def test_champion_metadata(self):
        p = self._make_player()
        apply_rarity_to_player(p, "champion", champion_type="berserker", display_name="Berserker Demon")
        assert p.monster_rarity == "champion"
        assert p.champion_type == "berserker"
        assert p.affixes == []
        assert p.display_name == "Berserker Demon"

    # --- HP recalculation ---

    def test_hp_set_to_max_after_apply(self):
        """HP should be set to max_hp after all modifications."""
        p = self._make_player(hp=50, max_hp=100)  # Start at half HP
        apply_rarity_to_player(p, "champion", champion_type="resilient")
        assert p.hp == p.max_hp

    # --- Edge cases ---

    def test_empty_affixes_list(self):
        p = self._make_player()
        apply_rarity_to_player(p, "rare", affixes=[])
        # Only tier scaling
        assert p.max_hp == 170
        assert p.attack_damage == 26

    def test_unknown_affix_ignored(self):
        """Unknown affix IDs should be silently ignored."""
        p = self._make_player()
        apply_rarity_to_player(p, "rare", affixes=["nonexistent_affix"])
        # Only tier scaling
        assert p.max_hp == 170

    def test_champion_with_realistic_enemy(self):
        """Test with a realistic enemy (Demon: 240 HP, 24 damage, 8 armor)."""
        p = self._make_player(hp=240, max_hp=240, attack_damage=24, armor=8)
        apply_rarity_to_player(p, "champion", champion_type="berserker")
        # Tier: 240*1.4=336 HP, 24*1.2=28.8->28 damage, 8+3=11 armor
        # Berserker: 28*1.3=36.4->36 damage
        assert p.max_hp == 336
        assert p.attack_damage == 36
        assert p.armor == 11

    def test_rare_with_realistic_enemy(self):
        """Test with a realistic enemy (Skeleton: 70 HP, 14 ranged, 3 armor)."""
        p = self._make_player(hp=70, max_hp=70, attack_damage=10, ranged_damage=14, armor=3)
        apply_rarity_to_player(
            p, "rare",
            affixes=["extra_strong", "cold_enchanted", "regenerating"],
            display_name="Brutal Skeleton of Frost",
        )
        # Tier: 70*1.7=119 HP, 10*1.3=13 melee, 14*1.3=18.2->18 ranged, 3+5=8 armor
        # Extra Strong: 13*1.3=16.9->16 melee, 18*1.3=23.4->23 ranged
        # Cold Enchanted: on-hit -> no stat changes at spawn
        # Regenerating: 3% of 119 = 3.57 -> 3
        assert p.max_hp == 119
        assert p.hp == 119
        assert p.attack_damage == 16
        assert p.ranged_damage == 23
        assert p.armor == 8
        assert p.hp_regen == 3
        assert p.display_name == "Brutal Skeleton of Frost"


# ==========================================================
# Section 12: Phase 18B — Create Minions
# ==========================================================

class TestCreateMinions:
    """Test Normal-tier minion creation for Rare leaders."""

    def _make_rare_player(self):
        return PlayerState(
            player_id="rare_leader_001",
            username="rare_ai",
            enemy_type="skeleton",
            monster_rarity="rare",
        )

    def _make_enemy_def(self):
        return EnemyDefinition(
            enemy_id="skeleton",
            name="Skeleton",
            role="ranged",
        )

    def test_correct_count(self):
        leader = self._make_rare_player()
        enemy_def = self._make_enemy_def()
        minions = create_minions(leader, enemy_def, 3)
        assert len(minions) == 3

    def test_zero_count(self):
        leader = self._make_rare_player()
        enemy_def = self._make_enemy_def()
        minions = create_minions(leader, enemy_def, 0)
        assert minions == []

    def test_minions_are_normal_rarity(self):
        leader = self._make_rare_player()
        enemy_def = self._make_enemy_def()
        minions = create_minions(leader, enemy_def, 2)
        for m in minions:
            assert m["monster_rarity"] == "normal"

    def test_minions_linked_to_leader(self):
        leader = self._make_rare_player()
        enemy_def = self._make_enemy_def()
        minions = create_minions(leader, enemy_def, 2)
        for m in minions:
            assert m["minion_owner_id"] == "rare_leader_001"
            assert m["is_minion"] is True

    def test_minions_have_same_enemy_type(self):
        leader = self._make_rare_player()
        enemy_def = self._make_enemy_def()
        minions = create_minions(leader, enemy_def, 2)
        for m in minions:
            assert m["enemy_type"] == "skeleton"

    def test_minions_have_no_affixes(self):
        leader = self._make_rare_player()
        enemy_def = self._make_enemy_def()
        minions = create_minions(leader, enemy_def, 2)
        for m in minions:
            assert m["affixes"] == []
            assert m["champion_type"] is None

    def test_minion_ids_are_unique(self):
        leader = self._make_rare_player()
        enemy_def = self._make_enemy_def()
        minions = create_minions(leader, enemy_def, 3)
        ids = [m["player_id"] for m in minions]
        assert len(ids) == len(set(ids))

    def test_minion_ids_contain_leader_id(self):
        leader = self._make_rare_player()
        enemy_def = self._make_enemy_def()
        minions = create_minions(leader, enemy_def, 2)
        for m in minions:
            assert "rare_leader_001" in m["player_id"]

    def test_room_id_passed_through(self):
        leader = self._make_rare_player()
        enemy_def = self._make_enemy_def()
        minions = create_minions(leader, enemy_def, 2, room_id="room_3")
        for m in minions:
            assert m["room_id"] == "room_3"

    def test_room_id_none_default(self):
        leader = self._make_rare_player()
        enemy_def = self._make_enemy_def()
        minions = create_minions(leader, enemy_def, 2)
        for m in minions:
            assert m["room_id"] is None

    def test_deterministic_with_rng(self):
        leader = self._make_rare_player()
        enemy_def = self._make_enemy_def()
        m1 = create_minions(leader, enemy_def, 2, rng=random.Random(42))
        m2 = create_minions(leader, enemy_def, 2, rng=random.Random(42))
        # IDs will differ (uuid), but structure should be same
        assert len(m1) == len(m2)
        for a, b in zip(m1, m2):
            assert a["enemy_type"] == b["enemy_type"]
            assert a["monster_rarity"] == b["monster_rarity"]


# ==========================================================
# Section 13: Phase 18B — Integration: End-to-End Rarity Flow
# ==========================================================

class TestEndToEndRarityFlow:
    """Test the complete flow: roll -> select affixes -> name -> apply -> verify."""

    def test_champion_flow(self):
        """Roll champion, apply type, verify stats."""
        rng = random.Random(42)
        ct = roll_champion_type(rng)
        assert ct in VALID_CHAMPION_TYPES

        p = PlayerState(
            player_id="e2e_champ",
            username="ai",
            hp=100, max_hp=100,
            attack_damage=20, armor=5,
        )
        ct_name = get_champion_type_name(ct)
        display_name = f"{ct_name} Skeleton"
        apply_rarity_to_player(p, "champion", champion_type=ct, display_name=display_name)

        assert p.monster_rarity == "champion"
        assert p.champion_type == ct
        assert p.display_name == display_name
        assert p.max_hp >= 140  # At least tier scaling
        assert p.hp == p.max_hp

    def test_rare_flow(self):
        """Roll rare, select affixes, generate name, apply, verify."""
        rng = random.Random(42)
        enemy_def = EnemyDefinition(
            enemy_id="demon",
            name="Demon",
            role="bruiser",
            base_hp=240,
            base_melee_damage=24,
            base_armor=8,
            ranged_range=1,
        )

        affixes = roll_affixes(enemy_def, 3, rng)
        assert 1 <= len(affixes) <= 3

        name = generate_rare_name("Demon", affixes, rng)
        assert "Demon" in name

        p = PlayerState(
            player_id="e2e_rare",
            username="ai",
            hp=240, max_hp=240,
            attack_damage=24, armor=8,
        )
        apply_rarity_to_player(p, "rare", affixes=affixes, display_name=name)

        assert p.monster_rarity == "rare"
        assert p.affixes == affixes
        assert p.display_name == name
        assert p.max_hp >= 240 * 1.7 - 1  # At least tier scaling (int rounding)
        assert p.hp == p.max_hp

    def test_rare_with_minions_flow(self):
        """Full rare flow including minion creation."""
        rng = random.Random(42)
        enemy_def = EnemyDefinition(
            enemy_id="skeleton",
            name="Skeleton",
            role="ranged",
            ranged_range=5,
        )

        affixes = roll_affixes(enemy_def, 2, rng)
        name = generate_rare_name("Skeleton", affixes, rng)

        leader = PlayerState(
            player_id="rare_skel_001",
            username="ai",
            hp=70, max_hp=70,
            attack_damage=10, ranged_damage=14, armor=3,
            enemy_type="skeleton",
        )
        apply_rarity_to_player(leader, "rare", affixes=affixes, display_name=name)

        # Config says minion_count is [2, 3]
        minion_count = rng.randint(2, 3)
        minions = create_minions(leader, enemy_def, minion_count, room_id="room_5", rng=rng)

        assert len(minions) == minion_count
        for m in minions:
            assert m["minion_owner_id"] == "rare_skel_001"
            assert m["monster_rarity"] == "normal"
            assert m["enemy_type"] == "skeleton"

    def test_normal_flow_no_changes(self):
        """Normal rarity should pass through cleanly."""
        p = PlayerState(
            player_id="e2e_normal",
            username="ai",
            hp=100, max_hp=100,
            attack_damage=20, armor=5,
        )
        apply_rarity_to_player(p, "normal")
        assert p.monster_rarity == "normal"
        assert p.max_hp == 100
        assert p.attack_damage == 20
        assert p.armor == 5
