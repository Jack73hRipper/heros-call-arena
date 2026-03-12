"""
Tests for Phase 22A: Blood Knight class config & data model.

Covers:
- Blood Knight class loads correctly from classes_config.json
- Blood Knight base stats match design spec (HP=100, melee=16, ranged=0, armor=4, vision=6, range=0)
- Blood Knight color is #8B0000 and shape is shield
- All 4 Blood Knight skills load from skills_config.json
- Blood Knight skill definitions have correct fields and values
- class_skills["blood_knight"] maps correctly (5 skills)
- can_use_skill() validates Blood Knight skills for blood_knight class
- can_use_skill() rejects Blood Knight skills for non-blood_knight classes
- Blood Knight names exist in names_config.json
- apply_class_stats() works for Blood Knight
- Existing class tests still pass (regression check)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.player import (
    PlayerState,
    Position,
    ClassDefinition,
    load_classes_config,
    get_class_definition,
    get_all_classes,
    apply_class_stats,
)
from app.core.skills import (
    load_skills_config,
    clear_skills_cache,
    get_skill,
    get_class_skills,
    can_use_skill,
)


# ---------- Fixtures ----------

_classes_cache_attr = "_classes_cache"


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


@pytest.fixture
def loaded_classes() -> dict[str, ClassDefinition]:
    """Load and return the classes config dict."""
    return load_classes_config()


def _make_player(
    class_id: str = "blood_knight",
    hp: int = 100,
    alive: bool = True,
    cooldowns: dict | None = None,
    team: str = "team_1",
) -> PlayerState:
    """Helper — create a PlayerState with the given class and state."""
    return PlayerState(
        player_id="bk1",
        username="TestBloodKnight",
        position=Position(x=5, y=5),
        class_id=class_id,
        hp=hp,
        max_hp=hp,
        is_alive=alive,
        cooldowns=cooldowns or {},
        team=team,
    )


# ============================================================
# 1. Blood Knight Class Config
# ============================================================

class TestBloodKnightClassConfig:
    """Tests for Blood Knight class definition in classes_config.json."""

    def test_blood_knight_class_exists(self, loaded_classes):
        assert "blood_knight" in loaded_classes

    def test_blood_knight_class_definition_type(self, loaded_classes):
        bk = loaded_classes["blood_knight"]
        assert isinstance(bk, ClassDefinition)

    def test_blood_knight_base_hp(self, loaded_classes):
        assert loaded_classes["blood_knight"].base_hp == 100

    def test_blood_knight_base_melee_damage(self, loaded_classes):
        assert loaded_classes["blood_knight"].base_melee_damage == 16

    def test_blood_knight_base_ranged_damage(self, loaded_classes):
        assert loaded_classes["blood_knight"].base_ranged_damage == 0

    def test_blood_knight_base_armor(self, loaded_classes):
        assert loaded_classes["blood_knight"].base_armor == 4

    def test_blood_knight_base_vision_range(self, loaded_classes):
        assert loaded_classes["blood_knight"].base_vision_range == 6

    def test_blood_knight_ranged_range(self, loaded_classes):
        assert loaded_classes["blood_knight"].ranged_range == 0

    def test_blood_knight_allowed_weapons(self, loaded_classes):
        assert loaded_classes["blood_knight"].allowed_weapon_categories == ["melee", "hybrid"]

    def test_blood_knight_color(self, loaded_classes):
        assert loaded_classes["blood_knight"].color == "#8B0000"

    def test_blood_knight_shape(self, loaded_classes):
        assert loaded_classes["blood_knight"].shape == "shield"

    def test_blood_knight_role(self, loaded_classes):
        assert loaded_classes["blood_knight"].role == "Sustain Melee DPS"

    def test_blood_knight_name(self, loaded_classes):
        assert loaded_classes["blood_knight"].name == "Blood Knight"

    def test_get_class_definition_blood_knight(self, loaded_classes):
        bk = get_class_definition("blood_knight")
        assert bk is not None
        assert bk.class_id == "blood_knight"

    def test_apply_class_stats_blood_knight(self, loaded_classes):
        player = PlayerState(player_id="p1", username="Test")
        result = apply_class_stats(player, "blood_knight")
        assert result is True
        assert player.class_id == "blood_knight"
        assert player.hp == 100
        assert player.max_hp == 100
        assert player.attack_damage == 16
        assert player.ranged_damage == 0
        assert player.armor == 4
        assert player.vision_range == 6
        assert player.ranged_range == 0

    def test_total_class_count(self, loaded_classes):
        """Should now have 11 playable classes (Shaman added in Phase 26)."""
        assert len(loaded_classes) == 11

    def test_blood_knight_is_pure_melee(self, loaded_classes):
        """Blood Knight has zero ranged capability — pure melee class."""
        bk = loaded_classes["blood_knight"]
        assert bk.base_ranged_damage == 0
        assert bk.ranged_range == 0


# ============================================================
# 2. Blood Knight Skills Config
# ============================================================

class TestBloodKnightSkillsConfig:
    """Tests for Blood Knight skill definitions in skills_config.json."""

    # -- Blood Strike --

    def test_blood_strike_exists(self, loaded_skills):
        skill = get_skill("blood_strike")
        assert skill is not None

    def test_blood_strike_definition(self, loaded_skills):
        s = get_skill("blood_strike")
        assert s["skill_id"] == "blood_strike"
        assert s["name"] == "Blood Strike"
        assert s["targeting"] == "entity"
        assert s["range"] == 1
        assert s["cooldown_turns"] == 4
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is False
        assert s["allowed_classes"] == ["blood_knight"]

    def test_blood_strike_effect(self, loaded_skills):
        s = get_skill("blood_strike")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "lifesteal_damage"
        assert effect["damage_multiplier"] == 1.4
        assert effect["heal_pct"] == 0.40

    # -- Crimson Veil --

    def test_crimson_veil_exists(self, loaded_skills):
        skill = get_skill("crimson_veil")
        assert skill is not None

    def test_crimson_veil_definition(self, loaded_skills):
        s = get_skill("crimson_veil")
        assert s["skill_id"] == "crimson_veil"
        assert s["name"] == "Crimson Veil"
        assert s["targeting"] == "self"
        assert s["range"] == 0
        assert s["cooldown_turns"] == 6
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is False
        assert s["allowed_classes"] == ["blood_knight"]

    def test_crimson_veil_has_two_effects(self, loaded_skills):
        """Crimson Veil is a multi-effect skill: buff + hot."""
        s = get_skill("crimson_veil")
        assert len(s["effects"]) == 2

    def test_crimson_veil_buff_effect(self, loaded_skills):
        s = get_skill("crimson_veil")
        buff_effect = s["effects"][0]
        assert buff_effect["type"] == "buff"
        assert buff_effect["stat"] == "melee_damage_multiplier"
        assert buff_effect["magnitude"] == 1.3
        assert buff_effect["duration_turns"] == 3

    def test_crimson_veil_hot_effect(self, loaded_skills):
        s = get_skill("crimson_veil")
        hot_effect = s["effects"][1]
        assert hot_effect["type"] == "hot"
        assert hot_effect["heal_per_turn"] == 6
        assert hot_effect["duration_turns"] == 3

    # -- Sanguine Burst --

    def test_sanguine_burst_exists(self, loaded_skills):
        skill = get_skill("sanguine_burst")
        assert skill is not None

    def test_sanguine_burst_definition(self, loaded_skills):
        s = get_skill("sanguine_burst")
        assert s["skill_id"] == "sanguine_burst"
        assert s["name"] == "Sanguine Burst"
        assert s["targeting"] == "self"
        assert s["range"] == 0
        assert s["cooldown_turns"] == 7
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is False
        assert s["allowed_classes"] == ["blood_knight"]

    def test_sanguine_burst_effect(self, loaded_skills):
        s = get_skill("sanguine_burst")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "lifesteal_aoe"
        assert effect["radius"] == 1
        assert effect["damage_multiplier"] == 0.7
        assert effect["heal_pct"] == 0.50

    # -- Blood Frenzy --

    def test_blood_frenzy_exists(self, loaded_skills):
        skill = get_skill("blood_frenzy")
        assert skill is not None

    def test_blood_frenzy_definition(self, loaded_skills):
        s = get_skill("blood_frenzy")
        assert s["skill_id"] == "blood_frenzy"
        assert s["name"] == "Blood Frenzy"
        assert s["targeting"] == "self"
        assert s["range"] == 0
        assert s["cooldown_turns"] == 8
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is False
        assert s["allowed_classes"] == ["blood_knight"]

    def test_blood_frenzy_effect(self, loaded_skills):
        s = get_skill("blood_frenzy")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "conditional_buff"
        assert effect["hp_threshold"] == 0.40
        assert effect["instant_heal"] == 15
        assert effect["stat"] == "melee_damage_multiplier"
        assert effect["magnitude"] == 1.5
        assert effect["duration_turns"] == 3


# ============================================================
# 3. Class-Skills Mapping
# ============================================================

class TestBloodKnightClassSkillsMapping:
    """Tests for the class_skills.blood_knight mapping in skills_config.json."""

    def test_blood_knight_class_skills_exist(self, loaded_skills):
        skills = get_class_skills("blood_knight")
        assert skills is not None
        assert len(skills) > 0

    def test_blood_knight_has_five_skills(self, loaded_skills):
        skills = get_class_skills("blood_knight")
        assert len(skills) == 5

    def test_blood_knight_skill_order(self, loaded_skills):
        skills = get_class_skills("blood_knight")
        assert skills == [
            "auto_attack_melee",
            "blood_strike",
            "crimson_veil",
            "sanguine_burst",
            "blood_frenzy",
        ]

    def test_blood_knight_auto_attack_is_melee(self, loaded_skills):
        """Blood Knight uses melee auto-attack (slot 0)."""
        skills = get_class_skills("blood_knight")
        assert skills[0] == "auto_attack_melee"

    def test_all_blood_knight_skills_exist_in_config(self, loaded_skills):
        """Every skill in the blood_knight mapping must exist in the skills registry."""
        for skill_id in get_class_skills("blood_knight"):
            skill = get_skill(skill_id)
            assert skill is not None, f"Blood Knight skill '{skill_id}' not found in skills config"


# ============================================================
# 4. can_use_skill() Validation for Blood Knight
# ============================================================

class TestBloodKnightCanUseSkill:
    """Tests for can_use_skill() with Blood Knight class and skills."""

    def test_blood_knight_can_use_blood_strike(self, loaded_skills):
        player = _make_player(class_id="blood_knight")
        ok, msg = can_use_skill(player, "blood_strike")
        assert ok is True
        assert msg == ""

    def test_blood_knight_can_use_crimson_veil(self, loaded_skills):
        player = _make_player(class_id="blood_knight")
        ok, msg = can_use_skill(player, "crimson_veil")
        assert ok is True

    def test_blood_knight_can_use_sanguine_burst(self, loaded_skills):
        player = _make_player(class_id="blood_knight")
        ok, msg = can_use_skill(player, "sanguine_burst")
        assert ok is True

    def test_blood_knight_can_use_blood_frenzy(self, loaded_skills):
        player = _make_player(class_id="blood_knight")
        ok, msg = can_use_skill(player, "blood_frenzy")
        assert ok is True

    def test_blood_knight_can_use_melee_auto_attack(self, loaded_skills):
        """Blood Knight should be in auto_attack_melee allowed_classes."""
        player = _make_player(class_id="blood_knight")
        ok, msg = can_use_skill(player, "auto_attack_melee")
        assert ok is True

    def test_non_blood_knight_cannot_use_blood_strike(self, loaded_skills):
        player = _make_player(class_id="crusader")
        ok, msg = can_use_skill(player, "blood_strike")
        assert ok is False
        assert "class" in msg.lower()

    def test_non_blood_knight_cannot_use_crimson_veil(self, loaded_skills):
        player = _make_player(class_id="ranger")
        ok, msg = can_use_skill(player, "crimson_veil")
        assert ok is False

    def test_non_blood_knight_cannot_use_sanguine_burst(self, loaded_skills):
        player = _make_player(class_id="mage")
        ok, msg = can_use_skill(player, "sanguine_burst")
        assert ok is False

    def test_non_blood_knight_cannot_use_blood_frenzy(self, loaded_skills):
        player = _make_player(class_id="hexblade")
        ok, msg = can_use_skill(player, "blood_frenzy")
        assert ok is False

    def test_dead_blood_knight_cannot_use_skills(self, loaded_skills):
        player = _make_player(class_id="blood_knight", alive=False)
        ok, msg = can_use_skill(player, "blood_strike")
        assert ok is False
        assert "dead" in msg

    def test_blood_knight_skill_on_cooldown_rejected(self, loaded_skills):
        player = _make_player(class_id="blood_knight", cooldowns={"blood_strike": 3})
        ok, msg = can_use_skill(player, "blood_strike")
        assert ok is False
        assert "cooldown" in msg.lower()
        assert "3" in msg

    def test_blood_knight_skill_zero_cooldown_allowed(self, loaded_skills):
        player = _make_player(class_id="blood_knight", cooldowns={"blood_strike": 0})
        ok, msg = can_use_skill(player, "blood_strike")
        assert ok is True


# ============================================================
# 5. Blood Knight Names Config
# ============================================================

class TestBloodKnightNamesConfig:
    """Tests for Blood Knight names in names_config.json."""

    @pytest.fixture
    def names_config(self) -> dict:
        path = Path(__file__).resolve().parent.parent / "configs" / "names_config.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_blood_knight_names_exist(self, names_config):
        assert "blood_knight" in names_config

    def test_blood_knight_has_enough_names(self, names_config):
        assert len(names_config["blood_knight"]) >= 10

    def test_blood_knight_names_are_unique(self, names_config):
        names = names_config["blood_knight"]
        assert len(names) == len(set(names)), "Duplicate blood_knight names found"

    def test_blood_knight_names_are_strings(self, names_config):
        for name in names_config["blood_knight"]:
            assert isinstance(name, str)
            assert len(name) > 0


# ============================================================
# 6. Regression — Existing Classes Still Work
# ============================================================

class TestRegressionExistingClasses:
    """Verify existing class definitions/skills are not broken by Blood Knight addition."""

    def test_crusader_still_exists(self, loaded_classes):
        assert "crusader" in loaded_classes
        assert loaded_classes["crusader"].base_hp == 135

    def test_confessor_still_exists(self, loaded_classes):
        assert "confessor" in loaded_classes
        assert loaded_classes["confessor"].base_hp == 100

    def test_inquisitor_still_exists(self, loaded_classes):
        assert "inquisitor" in loaded_classes
        assert loaded_classes["inquisitor"].base_hp == 90

    def test_ranger_still_exists(self, loaded_classes):
        assert "ranger" in loaded_classes
        assert loaded_classes["ranger"].base_hp == 80

    def test_hexblade_still_exists(self, loaded_classes):
        assert "hexblade" in loaded_classes
        assert loaded_classes["hexblade"].base_hp == 110

    def test_mage_still_exists(self, loaded_classes):
        assert "mage" in loaded_classes
        assert loaded_classes["mage"].base_hp == 80

    def test_bard_still_exists(self, loaded_classes):
        assert "bard" in loaded_classes
        assert loaded_classes["bard"].base_hp == 110

    def test_all_existing_class_skills_unchanged(self, loaded_skills):
        """Spot-check that existing class_skills mappings are unmodified."""
        assert get_class_skills("crusader") == [
            "auto_attack_melee", "taunt", "shield_bash", "holy_ground", "bulwark"
        ]
        assert get_class_skills("bard") == [
            "auto_attack_ranged", "ballad_of_might", "dirge_of_weakness",
            "verse_of_haste", "cacophony"
        ]
