"""
Tests for Phase 25A: Revenant class config & data model.

Covers:
- Revenant class loads correctly from classes_config.json
- Revenant base stats match design spec (HP=130, melee=14, ranged=0, armor=5, vision=5, range=0)
- Revenant color is #708090 and shape is coffin
- All 4 Revenant skills load from skills_config.json
- Revenant skill definitions have correct fields and values
- class_skills["revenant"] maps correctly (5 skills)
- can_use_skill() validates Revenant skills for revenant class
- can_use_skill() rejects Revenant skills for non-revenant classes
- Revenant names exist in names_config.json
- apply_class_stats() works for Revenant
- Revenant allowed_weapon_categories is ["melee", "hybrid"]
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
    class_id: str = "revenant",
    hp: int = 130,
    alive: bool = True,
    cooldowns: dict | None = None,
    team: str = "team_1",
) -> PlayerState:
    """Helper — create a PlayerState with the given class and state."""
    return PlayerState(
        player_id="rev1",
        username="TestRevenant",
        position=Position(x=5, y=5),
        class_id=class_id,
        hp=hp,
        max_hp=hp,
        is_alive=alive,
        cooldowns=cooldowns or {},
        team=team,
    )


# ============================================================
# 1. Revenant Class Config
# ============================================================

class TestRevenantClassConfig:
    """Tests for Revenant class definition in classes_config.json."""

    def test_revenant_class_exists(self, loaded_classes):
        assert "revenant" in loaded_classes

    def test_revenant_class_definition_type(self, loaded_classes):
        rev = loaded_classes["revenant"]
        assert isinstance(rev, ClassDefinition)

    def test_revenant_base_hp(self, loaded_classes):
        assert loaded_classes["revenant"].base_hp == 130

    def test_revenant_base_melee_damage(self, loaded_classes):
        assert loaded_classes["revenant"].base_melee_damage == 16

    def test_revenant_base_ranged_damage(self, loaded_classes):
        assert loaded_classes["revenant"].base_ranged_damage == 0

    def test_revenant_base_armor(self, loaded_classes):
        assert loaded_classes["revenant"].base_armor == 6

    def test_revenant_base_vision_range(self, loaded_classes):
        assert loaded_classes["revenant"].base_vision_range == 5

    def test_revenant_ranged_range(self, loaded_classes):
        assert loaded_classes["revenant"].ranged_range == 0

    def test_revenant_allowed_weapons(self, loaded_classes):
        assert loaded_classes["revenant"].allowed_weapon_categories == ["melee", "hybrid"]

    def test_revenant_color(self, loaded_classes):
        assert loaded_classes["revenant"].color == "#708090"

    def test_revenant_shape(self, loaded_classes):
        assert loaded_classes["revenant"].shape == "coffin"

    def test_revenant_role(self, loaded_classes):
        assert loaded_classes["revenant"].role == "Retaliation Tank"

    def test_revenant_name(self, loaded_classes):
        assert loaded_classes["revenant"].name == "Revenant"

    def test_get_class_definition_revenant(self, loaded_classes):
        rev = get_class_definition("revenant")
        assert rev is not None
        assert rev.class_id == "revenant"

    def test_apply_class_stats_revenant(self, loaded_classes):
        player = PlayerState(player_id="p1", username="Test")
        result = apply_class_stats(player, "revenant")
        assert result is True
        assert player.class_id == "revenant"
        assert player.hp == 130
        assert player.max_hp == 130
        assert player.attack_damage == 16
        assert player.ranged_damage == 0
        assert player.armor == 6
        assert player.vision_range == 5
        assert player.ranged_range == 0

    def test_total_class_count(self, loaded_classes):
        """Should now have 11 playable classes (Shaman added in Phase 26)."""
        assert len(loaded_classes) == 11

    def test_revenant_is_pure_melee(self, loaded_classes):
        """Revenant has zero ranged capability — pure melee class."""
        rev = loaded_classes["revenant"]
        assert rev.base_ranged_damage == 0
        assert rev.ranged_range == 0


# ============================================================
# 2. Revenant Skills Config
# ============================================================

class TestRevenantSkillsConfig:
    """Tests for Revenant skill definitions in skills_config.json."""

    # -- Grave Thorns --

    def test_grave_thorns_exists(self, loaded_skills):
        skill = get_skill("grave_thorns")
        assert skill is not None

    def test_grave_thorns_definition(self, loaded_skills):
        s = get_skill("grave_thorns")
        assert s["skill_id"] == "grave_thorns"
        assert s["name"] == "Grave Thorns"
        assert s["targeting"] == "self"
        assert s["range"] == 0
        assert s["cooldown_turns"] == 5
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is False
        assert s["allowed_classes"] == ["revenant"]

    def test_grave_thorns_effect(self, loaded_skills):
        s = get_skill("grave_thorns")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "thorns_buff"
        assert effect["thorns_damage"] == 12
        assert effect["duration_turns"] == 4

    # -- Grave Chains --

    def test_grave_chains_exists(self, loaded_skills):
        skill = get_skill("grave_chains")
        assert skill is not None

    def test_grave_chains_definition(self, loaded_skills):
        s = get_skill("grave_chains")
        assert s["skill_id"] == "grave_chains"
        assert s["name"] == "Grave Chains"
        assert s["targeting"] == "enemy_ranged"
        assert s["range"] == 4
        assert s["cooldown_turns"] == 5
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is True
        assert s["allowed_classes"] == ["revenant"]

    def test_grave_chains_effect(self, loaded_skills):
        s = get_skill("grave_chains")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "ranged_taunt"
        assert effect["taunt_duration"] == 3

    # -- Undying Will --

    def test_undying_will_exists(self, loaded_skills):
        skill = get_skill("undying_will")
        assert skill is not None

    def test_undying_will_definition(self, loaded_skills):
        s = get_skill("undying_will")
        assert s["skill_id"] == "undying_will"
        assert s["name"] == "Undying Will"
        assert s["targeting"] == "self"
        assert s["range"] == 0
        assert s["cooldown_turns"] == 8
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is False
        assert s["allowed_classes"] == ["revenant"]

    def test_undying_will_effect(self, loaded_skills):
        s = get_skill("undying_will")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "cheat_death"
        assert effect["revive_hp_pct"] == 0.30
        assert effect["duration_turns"] == 5

    def test_undying_will_longest_cooldown(self, loaded_skills):
        """Undying Will has the longest cooldown (8) of any Revenant skill."""
        s = get_skill("undying_will")
        assert s["cooldown_turns"] == 8

    # -- Soul Rend --

    def test_soul_rend_exists(self, loaded_skills):
        skill = get_skill("soul_rend")
        assert skill is not None

    def test_soul_rend_definition(self, loaded_skills):
        s = get_skill("soul_rend")
        assert s["skill_id"] == "soul_rend"
        assert s["name"] == "Soul Rend"
        assert s["targeting"] == "enemy_adjacent"
        assert s["range"] == 1
        assert s["cooldown_turns"] == 4
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is False
        assert s["allowed_classes"] == ["revenant"]

    def test_soul_rend_effect(self, loaded_skills):
        s = get_skill("soul_rend")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "melee_damage_slow"
        assert effect["damage_multiplier"] == 1.5
        assert effect["slow_duration"] == 2


# ============================================================
# 3. Class-Skills Mapping
# ============================================================

class TestRevenantClassSkillsMapping:
    """Tests for the class_skills.revenant mapping in skills_config.json."""

    def test_revenant_class_skills_exist(self, loaded_skills):
        skills = get_class_skills("revenant")
        assert skills is not None
        assert len(skills) > 0

    def test_revenant_has_five_skills(self, loaded_skills):
        skills = get_class_skills("revenant")
        assert len(skills) == 5

    def test_revenant_skill_order(self, loaded_skills):
        skills = get_class_skills("revenant")
        assert skills == [
            "auto_attack_melee",
            "grave_thorns",
            "grave_chains",
            "undying_will",
            "soul_rend",
        ]

    def test_revenant_auto_attack_is_melee(self, loaded_skills):
        """Revenant uses melee auto-attack (slot 0)."""
        skills = get_class_skills("revenant")
        assert skills[0] == "auto_attack_melee"

    def test_all_revenant_skills_exist_in_config(self, loaded_skills):
        """Every skill in the revenant mapping must exist in the skills registry."""
        for skill_id in get_class_skills("revenant"):
            skill = get_skill(skill_id)
            assert skill is not None, f"Revenant skill '{skill_id}' not found in skills config"


# ============================================================
# 4. can_use_skill() Validation for Revenant
# ============================================================

class TestRevenantCanUseSkill:
    """Tests for can_use_skill() with Revenant class and skills."""

    def test_revenant_can_use_grave_thorns(self, loaded_skills):
        player = _make_player(class_id="revenant")
        ok, msg = can_use_skill(player, "grave_thorns")
        assert ok is True
        assert msg == ""

    def test_revenant_can_use_grave_chains(self, loaded_skills):
        player = _make_player(class_id="revenant")
        ok, msg = can_use_skill(player, "grave_chains")
        assert ok is True

    def test_revenant_can_use_undying_will(self, loaded_skills):
        player = _make_player(class_id="revenant")
        ok, msg = can_use_skill(player, "undying_will")
        assert ok is True

    def test_revenant_can_use_soul_rend(self, loaded_skills):
        player = _make_player(class_id="revenant")
        ok, msg = can_use_skill(player, "soul_rend")
        assert ok is True

    def test_revenant_can_use_melee_auto_attack(self, loaded_skills):
        """Revenant should be in auto_attack_melee allowed_classes."""
        player = _make_player(class_id="revenant")
        ok, msg = can_use_skill(player, "auto_attack_melee")
        assert ok is True

    def test_non_revenant_cannot_use_grave_thorns(self, loaded_skills):
        player = _make_player(class_id="crusader")
        ok, msg = can_use_skill(player, "grave_thorns")
        assert ok is False
        assert "class" in msg.lower()

    def test_non_revenant_cannot_use_grave_chains(self, loaded_skills):
        player = _make_player(class_id="ranger")
        ok, msg = can_use_skill(player, "grave_chains")
        assert ok is False

    def test_non_revenant_cannot_use_undying_will(self, loaded_skills):
        player = _make_player(class_id="mage")
        ok, msg = can_use_skill(player, "undying_will")
        assert ok is False

    def test_non_revenant_cannot_use_soul_rend(self, loaded_skills):
        player = _make_player(class_id="hexblade")
        ok, msg = can_use_skill(player, "soul_rend")
        assert ok is False

    def test_dead_revenant_cannot_use_skills(self, loaded_skills):
        player = _make_player(class_id="revenant", alive=False)
        ok, msg = can_use_skill(player, "grave_thorns")
        assert ok is False
        assert "dead" in msg

    def test_revenant_skill_on_cooldown_rejected(self, loaded_skills):
        player = _make_player(class_id="revenant", cooldowns={"grave_thorns": 3})
        ok, msg = can_use_skill(player, "grave_thorns")
        assert ok is False
        assert "cooldown" in msg.lower()
        assert "3" in msg

    def test_revenant_skill_zero_cooldown_allowed(self, loaded_skills):
        player = _make_player(class_id="revenant", cooldowns={"grave_thorns": 0})
        ok, msg = can_use_skill(player, "grave_thorns")
        assert ok is True


# ============================================================
# 5. Revenant Names Config
# ============================================================

class TestRevenantNamesConfig:
    """Tests for Revenant names in names_config.json."""

    @pytest.fixture
    def names_config(self) -> dict:
        path = Path(__file__).resolve().parent.parent / "configs" / "names_config.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_revenant_names_exist(self, names_config):
        assert "revenant" in names_config

    def test_revenant_has_enough_names(self, names_config):
        assert len(names_config["revenant"]) >= 10

    def test_revenant_names_are_unique(self, names_config):
        names = names_config["revenant"]
        assert len(names) == len(set(names)), "Duplicate revenant names found"

    def test_revenant_names_are_strings(self, names_config):
        for name in names_config["revenant"]:
            assert isinstance(name, str)
            assert len(name) > 0


# ============================================================
# 6. Regression — Existing Classes Still Work
# ============================================================

class TestRegressionExistingClasses:
    """Verify existing class definitions/skills are not broken by Revenant addition."""

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

    def test_plague_doctor_still_exists(self, loaded_classes):
        assert "plague_doctor" in loaded_classes
        assert loaded_classes["plague_doctor"].base_hp == 95

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
        assert get_class_skills("plague_doctor") == [
            "auto_attack_ranged", "miasma", "plague_flask",
            "enfeeble", "inoculate"
        ]
