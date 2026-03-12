"""
Tests for Phase 23A: Plague Doctor class config & data model.

Covers:
- Plague Doctor class loads correctly from classes_config.json
- Plague Doctor base stats match design spec (HP=85, melee=8, ranged=12, armor=2, vision=7, range=5)
- Plague Doctor color is #50C878 and shape is flask
- All 4 Plague Doctor skills load from skills_config.json
- Plague Doctor skill definitions have correct fields and values
- class_skills["plague_doctor"] maps correctly (5 skills)
- can_use_skill() validates Plague Doctor skills for plague_doctor class
- can_use_skill() rejects Plague Doctor skills for non-plague_doctor classes
- Plague Doctor names exist in names_config.json
- apply_class_stats() works for Plague Doctor
- auto_attack_ranged allowed_classes includes plague_doctor
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
    class_id: str = "plague_doctor",
    hp: int = 85,
    alive: bool = True,
    cooldowns: dict | None = None,
    team: str = "team_1",
) -> PlayerState:
    """Helper — create a PlayerState with the given class and state."""
    return PlayerState(
        player_id="pd1",
        username="TestPlagueDoctor",
        position=Position(x=5, y=5),
        class_id=class_id,
        hp=hp,
        max_hp=hp,
        is_alive=alive,
        cooldowns=cooldowns or {},
        team=team,
    )


# ============================================================
# 1. Plague Doctor Class Config
# ============================================================

class TestPlagueDoctorClassConfig:
    """Tests for Plague Doctor class definition in classes_config.json."""

    def test_plague_doctor_class_exists(self, loaded_classes):
        assert "plague_doctor" in loaded_classes

    def test_plague_doctor_class_definition_type(self, loaded_classes):
        pd = loaded_classes["plague_doctor"]
        assert isinstance(pd, ClassDefinition)

    def test_plague_doctor_base_hp(self, loaded_classes):
        assert loaded_classes["plague_doctor"].base_hp == 95

    def test_plague_doctor_base_melee_damage(self, loaded_classes):
        assert loaded_classes["plague_doctor"].base_melee_damage == 8

    def test_plague_doctor_base_ranged_damage(self, loaded_classes):
        assert loaded_classes["plague_doctor"].base_ranged_damage == 12

    def test_plague_doctor_base_armor(self, loaded_classes):
        assert loaded_classes["plague_doctor"].base_armor == 3

    def test_plague_doctor_base_vision_range(self, loaded_classes):
        assert loaded_classes["plague_doctor"].base_vision_range == 7

    def test_plague_doctor_ranged_range(self, loaded_classes):
        assert loaded_classes["plague_doctor"].ranged_range == 5

    def test_plague_doctor_allowed_weapons(self, loaded_classes):
        assert loaded_classes["plague_doctor"].allowed_weapon_categories == ["caster", "hybrid"]

    def test_plague_doctor_color(self, loaded_classes):
        assert loaded_classes["plague_doctor"].color == "#50C878"

    def test_plague_doctor_shape(self, loaded_classes):
        assert loaded_classes["plague_doctor"].shape == "flask"

    def test_plague_doctor_role(self, loaded_classes):
        assert loaded_classes["plague_doctor"].role == "Controller"

    def test_plague_doctor_name(self, loaded_classes):
        assert loaded_classes["plague_doctor"].name == "Plague Doctor"

    def test_get_class_definition_plague_doctor(self, loaded_classes):
        pd = get_class_definition("plague_doctor")
        assert pd is not None
        assert pd.class_id == "plague_doctor"

    def test_apply_class_stats_plague_doctor(self, loaded_classes):
        player = PlayerState(player_id="p1", username="Test")
        result = apply_class_stats(player, "plague_doctor")
        assert result is True
        assert player.class_id == "plague_doctor"
        assert player.hp == 95
        assert player.max_hp == 95
        assert player.attack_damage == 8
        assert player.ranged_damage == 12
        assert player.armor == 3
        assert player.vision_range == 7
        assert player.ranged_range == 5

    def test_total_class_count(self, loaded_classes):
        """Should now have 11 playable classes (Shaman added in Phase 26)."""
        assert len(loaded_classes) == 11

    def test_plague_doctor_is_ranged(self, loaded_classes):
        """Plague Doctor has ranged capability — midline controller."""
        pd = loaded_classes["plague_doctor"]
        assert pd.base_ranged_damage == 12
        assert pd.ranged_range == 5


# ============================================================
# 2. Plague Doctor Skills Config
# ============================================================

class TestPlagueDoctorSkillsConfig:
    """Tests for Plague Doctor skill definitions in skills_config.json."""

    # -- Miasma --

    def test_miasma_exists(self, loaded_skills):
        skill = get_skill("miasma")
        assert skill is not None

    def test_miasma_definition(self, loaded_skills):
        s = get_skill("miasma")
        assert s["skill_id"] == "miasma"
        assert s["name"] == "Miasma"
        assert s["targeting"] == "ground_aoe"
        assert s["range"] == 5
        assert s["cooldown_turns"] == 6
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is True
        assert s["allowed_classes"] == ["plague_doctor"]

    def test_miasma_effect(self, loaded_skills):
        s = get_skill("miasma")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "aoe_damage_slow_targeted"
        assert effect["radius"] == 2
        assert effect["base_damage"] == 10
        assert effect["slow_duration"] == 2

    # -- Plague Flask --

    def test_plague_flask_exists(self, loaded_skills):
        skill = get_skill("plague_flask")
        assert skill is not None

    def test_plague_flask_definition(self, loaded_skills):
        s = get_skill("plague_flask")
        assert s["skill_id"] == "plague_flask"
        assert s["name"] == "Plague Flask"
        assert s["targeting"] == "enemy_ranged"
        assert s["range"] == 5
        assert s["cooldown_turns"] == 4
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is True
        assert s["allowed_classes"] == ["plague_doctor"]

    def test_plague_flask_effect(self, loaded_skills):
        s = get_skill("plague_flask")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "dot"
        assert effect["damage_per_tick"] == 8
        assert effect["duration_turns"] == 4

    # -- Enfeeble --

    def test_enfeeble_exists(self, loaded_skills):
        skill = get_skill("enfeeble")
        assert skill is not None

    def test_enfeeble_definition(self, loaded_skills):
        s = get_skill("enfeeble")
        assert s["skill_id"] == "enfeeble"
        assert s["name"] == "Enfeeble"
        assert s["targeting"] == "ground_aoe"
        assert s["range"] == 4
        assert s["cooldown_turns"] == 5
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is True
        assert s["allowed_classes"] == ["plague_doctor"]

    def test_enfeeble_effect(self, loaded_skills):
        s = get_skill("enfeeble")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "aoe_debuff"
        assert effect["radius"] == 2
        assert effect["stat"] == "damage_dealt_multiplier"
        assert effect["magnitude"] == 0.75
        assert effect["duration_turns"] == 4

    # -- Inoculate --

    def test_inoculate_exists(self, loaded_skills):
        skill = get_skill("inoculate")
        assert skill is not None

    def test_inoculate_definition(self, loaded_skills):
        s = get_skill("inoculate")
        assert s["skill_id"] == "inoculate"
        assert s["name"] == "Inoculate"
        assert s["targeting"] == "ally_or_self"
        assert s["range"] == 4
        assert s["cooldown_turns"] == 5
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is False
        assert s["allowed_classes"] == ["plague_doctor"]

    def test_inoculate_effect(self, loaded_skills):
        s = get_skill("inoculate")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "buff_cleanse"
        assert effect["stat"] == "armor"
        assert effect["magnitude"] == 3
        assert effect["duration_turns"] == 3
        assert effect["cleanse_dots"] is True


# ============================================================
# 3. Auto Attack Ranged — Plague Doctor allowed
# ============================================================

class TestAutoAttackRangedPlagueDoctor:
    """Tests that auto_attack_ranged includes plague_doctor in allowed_classes."""

    def test_auto_attack_ranged_allows_plague_doctor(self, loaded_skills):
        s = get_skill("auto_attack_ranged")
        assert "plague_doctor" in s["allowed_classes"]
        # Also verify other ranged classes are still allowed
        assert "ranger" in s["allowed_classes"]
        assert "mage" in s["allowed_classes"]
        assert "bard" in s["allowed_classes"]

    def test_plague_doctor_can_use_auto_attack_ranged(self, loaded_skills):
        player = _make_player(class_id="plague_doctor")
        ok, msg = can_use_skill(player, "auto_attack_ranged")
        assert ok is True


# ============================================================
# 4. Class-Skills Mapping
# ============================================================

class TestPlagueDoctorClassSkillsMapping:
    """Tests for the class_skills.plague_doctor mapping in skills_config.json."""

    def test_plague_doctor_class_skills_exist(self, loaded_skills):
        skills = get_class_skills("plague_doctor")
        assert skills is not None
        assert len(skills) > 0

    def test_plague_doctor_has_five_skills(self, loaded_skills):
        skills = get_class_skills("plague_doctor")
        assert len(skills) == 5

    def test_plague_doctor_skill_order(self, loaded_skills):
        skills = get_class_skills("plague_doctor")
        assert skills == [
            "auto_attack_ranged",
            "miasma",
            "plague_flask",
            "enfeeble",
            "inoculate",
        ]

    def test_plague_doctor_auto_attack_is_ranged(self, loaded_skills):
        """Plague Doctor uses ranged auto-attack (slot 0)."""
        skills = get_class_skills("plague_doctor")
        assert skills[0] == "auto_attack_ranged"

    def test_all_plague_doctor_skills_exist_in_config(self, loaded_skills):
        """Every skill in the plague_doctor mapping must exist in the skills registry."""
        for skill_id in get_class_skills("plague_doctor"):
            skill = get_skill(skill_id)
            assert skill is not None, f"Plague Doctor skill '{skill_id}' not found in skills config"


# ============================================================
# 5. can_use_skill() Validation for Plague Doctor
# ============================================================

class TestPlagueDoctorCanUseSkill:
    """Tests for can_use_skill() with Plague Doctor class and skills."""

    def test_plague_doctor_can_use_miasma(self, loaded_skills):
        player = _make_player(class_id="plague_doctor")
        ok, msg = can_use_skill(player, "miasma")
        assert ok is True
        assert msg == ""

    def test_plague_doctor_can_use_plague_flask(self, loaded_skills):
        player = _make_player(class_id="plague_doctor")
        ok, msg = can_use_skill(player, "plague_flask")
        assert ok is True

    def test_plague_doctor_can_use_enfeeble(self, loaded_skills):
        player = _make_player(class_id="plague_doctor")
        ok, msg = can_use_skill(player, "enfeeble")
        assert ok is True

    def test_plague_doctor_can_use_inoculate(self, loaded_skills):
        player = _make_player(class_id="plague_doctor")
        ok, msg = can_use_skill(player, "inoculate")
        assert ok is True

    def test_plague_doctor_can_use_ranged_auto_attack(self, loaded_skills):
        """Plague Doctor should be in auto_attack_ranged allowed_classes."""
        player = _make_player(class_id="plague_doctor")
        ok, msg = can_use_skill(player, "auto_attack_ranged")
        assert ok is True

    def test_non_plague_doctor_cannot_use_miasma(self, loaded_skills):
        player = _make_player(class_id="crusader")
        ok, msg = can_use_skill(player, "miasma")
        assert ok is False
        assert "class" in msg.lower()

    def test_non_plague_doctor_cannot_use_plague_flask(self, loaded_skills):
        player = _make_player(class_id="ranger")
        ok, msg = can_use_skill(player, "plague_flask")
        assert ok is False

    def test_non_plague_doctor_cannot_use_enfeeble(self, loaded_skills):
        player = _make_player(class_id="mage")
        ok, msg = can_use_skill(player, "enfeeble")
        assert ok is False

    def test_non_plague_doctor_cannot_use_inoculate(self, loaded_skills):
        player = _make_player(class_id="hexblade")
        ok, msg = can_use_skill(player, "inoculate")
        assert ok is False

    def test_dead_plague_doctor_cannot_use_skills(self, loaded_skills):
        player = _make_player(class_id="plague_doctor", alive=False)
        ok, msg = can_use_skill(player, "miasma")
        assert ok is False
        assert "dead" in msg

    def test_plague_doctor_skill_on_cooldown_rejected(self, loaded_skills):
        player = _make_player(class_id="plague_doctor", cooldowns={"miasma": 4})
        ok, msg = can_use_skill(player, "miasma")
        assert ok is False
        assert "cooldown" in msg.lower()
        assert "4" in msg

    def test_plague_doctor_skill_zero_cooldown_allowed(self, loaded_skills):
        player = _make_player(class_id="plague_doctor", cooldowns={"miasma": 0})
        ok, msg = can_use_skill(player, "miasma")
        assert ok is True


# ============================================================
# 6. Plague Doctor Names Config
# ============================================================

class TestPlagueDoctorNamesConfig:
    """Tests for Plague Doctor names in names_config.json."""

    @pytest.fixture
    def names_config(self) -> dict:
        path = Path(__file__).resolve().parent.parent / "configs" / "names_config.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_plague_doctor_names_exist(self, names_config):
        assert "plague_doctor" in names_config

    def test_plague_doctor_has_enough_names(self, names_config):
        assert len(names_config["plague_doctor"]) >= 10

    def test_plague_doctor_names_are_unique(self, names_config):
        names = names_config["plague_doctor"]
        assert len(names) == len(set(names)), "Duplicate plague_doctor names found"

    def test_plague_doctor_names_are_strings(self, names_config):
        for name in names_config["plague_doctor"]:
            assert isinstance(name, str)
            assert len(name) > 0


# ============================================================
# 7. Regression — Existing Classes Still Work
# ============================================================

class TestRegressionExistingClasses:
    """Verify existing class definitions/skills are not broken by Plague Doctor addition."""

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

    def test_blood_knight_still_exists(self, loaded_classes):
        assert "blood_knight" in loaded_classes
        assert loaded_classes["blood_knight"].base_hp == 100

    def test_all_existing_class_skills_unchanged(self, loaded_skills):
        """Spot-check that existing class_skills mappings are unmodified."""
        assert get_class_skills("crusader") == [
            "auto_attack_melee", "taunt", "shield_bash", "holy_ground", "bulwark"
        ]
        assert get_class_skills("bard") == [
            "auto_attack_ranged", "ballad_of_might", "dirge_of_weakness",
            "verse_of_haste", "cacophony"
        ]
        assert get_class_skills("blood_knight") == [
            "auto_attack_melee", "blood_strike", "crimson_veil",
            "sanguine_burst", "blood_frenzy"
        ]
