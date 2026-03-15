"""
Tests for Phase 26A: Shaman class config & data model.

Covers:
- Shaman class loads correctly from classes_config.json
- Shaman base stats match design spec (HP=95, melee=8, ranged=10, armor=3, vision=7, range=4)
- Shaman color is #8B6914 and shape is totem
- All 4 Shaman skills load from skills_config.json with correct effect types
- Healing Totem and Searing Totem both have place_totem effect with correct totem_type
- Soul Anchor has soul_anchor effect type with correct survive_hp and duration
- Earthgrasp has aoe_root effect type with correct radius and root_duration
- class_skills["shaman"] maps correctly (5 skills including auto_attack_ranged)
- can_use_skill() validates Shaman skills for shaman class
- can_use_skill() rejects Shaman skills for non-shaman classes
- Shaman allowed_weapon_categories is ["caster", "hybrid"]
- MatchState.totems field exists and defaults to empty list
- Shaman names exist in names_config.json
- apply_class_stats() works for Shaman
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
from app.models.match import MatchState


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
    class_id: str = "shaman",
    hp: int = 95,
    alive: bool = True,
    cooldowns: dict | None = None,
    team: str = "team_1",
) -> PlayerState:
    """Helper — create a PlayerState with the given class and state."""
    return PlayerState(
        player_id="shaman1",
        username="TestShaman",
        position=Position(x=5, y=5),
        class_id=class_id,
        hp=hp,
        max_hp=hp,
        is_alive=alive,
        cooldowns=cooldowns or {},
        team=team,
    )


# ============================================================
# 1. Shaman Class Config
# ============================================================

class TestShamanClassConfig:
    """Tests for Shaman class definition in classes_config.json."""

    def test_shaman_class_exists(self, loaded_classes):
        assert "shaman" in loaded_classes

    def test_shaman_class_definition_type(self, loaded_classes):
        shaman = loaded_classes["shaman"]
        assert isinstance(shaman, ClassDefinition)

    def test_shaman_base_hp(self, loaded_classes):
        assert loaded_classes["shaman"].base_hp == 95

    def test_shaman_base_melee_damage(self, loaded_classes):
        assert loaded_classes["shaman"].base_melee_damage == 8

    def test_shaman_base_ranged_damage(self, loaded_classes):
        assert loaded_classes["shaman"].base_ranged_damage == 10

    def test_shaman_base_armor(self, loaded_classes):
        assert loaded_classes["shaman"].base_armor == 3

    def test_shaman_base_vision_range(self, loaded_classes):
        assert loaded_classes["shaman"].base_vision_range == 7

    def test_shaman_ranged_range(self, loaded_classes):
        assert loaded_classes["shaman"].ranged_range == 4

    def test_shaman_allowed_weapons(self, loaded_classes):
        assert loaded_classes["shaman"].allowed_weapon_categories == ["caster", "hybrid"]

    def test_shaman_color(self, loaded_classes):
        assert loaded_classes["shaman"].color == "#8B6914"

    def test_shaman_shape(self, loaded_classes):
        assert loaded_classes["shaman"].shape == "totem"

    def test_shaman_role(self, loaded_classes):
        assert loaded_classes["shaman"].role == "Totemic Healer"

    def test_shaman_name(self, loaded_classes):
        assert loaded_classes["shaman"].name == "Shaman"

    def test_get_class_definition_shaman(self, loaded_classes):
        shaman = get_class_definition("shaman")
        assert shaman is not None
        assert shaman.class_id == "shaman"

    def test_apply_class_stats_shaman(self, loaded_classes):
        player = PlayerState(player_id="p1", username="Test")
        result = apply_class_stats(player, "shaman")
        assert result is True
        assert player.class_id == "shaman"
        assert player.hp == 95
        assert player.max_hp == 95
        assert player.attack_damage == 8
        assert player.ranged_damage == 10
        assert player.armor == 3
        assert player.vision_range == 7
        assert player.ranged_range == 4

    def test_total_class_count(self, loaded_classes):
        """Should now have 11 playable classes (Shaman added in Phase 26)."""
        assert len(loaded_classes) == 11

    def test_shaman_is_ranged_support(self, loaded_classes):
        """Shaman has ranged capability (range 4) and moderate ranged damage."""
        shaman = loaded_classes["shaman"]
        assert shaman.base_ranged_damage == 10
        assert shaman.ranged_range == 4


# ============================================================
# 2. Shaman Skills Config
# ============================================================

class TestShamanSkillsConfig:
    """Tests for Shaman skill definitions in skills_config.json."""

    # -- Healing Totem --

    def test_healing_totem_exists(self, loaded_skills):
        skill = get_skill("healing_totem")
        assert skill is not None

    def test_healing_totem_definition(self, loaded_skills):
        s = get_skill("healing_totem")
        assert s["skill_id"] == "healing_totem"
        assert s["name"] == "Healing Totem"
        assert s["targeting"] == "ground_aoe"
        assert s["range"] == 4
        assert s["cooldown_turns"] == 6
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is True
        assert s["allowed_classes"] == ["shaman"]

    def test_healing_totem_effect(self, loaded_skills):
        s = get_skill("healing_totem")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "place_totem"
        assert effect["totem_type"] == "healing"
        assert effect["totem_hp"] == 20
        assert effect["heal_per_turn"] == 8
        assert effect["effect_radius"] == 2
        assert effect["duration_turns"] == 4

    # -- Searing Totem --

    def test_searing_totem_exists(self, loaded_skills):
        skill = get_skill("searing_totem")
        assert skill is not None

    def test_searing_totem_definition(self, loaded_skills):
        s = get_skill("searing_totem")
        assert s["skill_id"] == "searing_totem"
        assert s["name"] == "Searing Totem"
        assert s["targeting"] == "ground_aoe"
        assert s["range"] == 4
        assert s["cooldown_turns"] == 6
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is True
        assert s["allowed_classes"] == ["shaman"]

    def test_searing_totem_effect(self, loaded_skills):
        s = get_skill("searing_totem")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "place_totem"
        assert effect["totem_type"] == "searing"
        assert effect["totem_hp"] == 20
        assert effect["damage_per_turn"] == 4
        assert effect["effect_radius"] == 2
        assert effect["duration_turns"] == 4

    def test_both_totems_use_place_totem_effect(self, loaded_skills):
        """Healing and Searing totems share the same effect type but differ by totem_type."""
        healing = get_skill("healing_totem")
        searing = get_skill("searing_totem")
        assert healing["effects"][0]["type"] == "place_totem"
        assert searing["effects"][0]["type"] == "place_totem"
        assert healing["effects"][0]["totem_type"] == "healing"
        assert searing["effects"][0]["totem_type"] == "searing"

    # -- Soul Anchor --

    def test_soul_anchor_exists(self, loaded_skills):
        skill = get_skill("soul_anchor")
        assert skill is not None

    def test_soul_anchor_definition(self, loaded_skills):
        s = get_skill("soul_anchor")
        assert s["skill_id"] == "soul_anchor"
        assert s["name"] == "Soul Anchor"
        assert s["targeting"] == "ally_or_self"
        assert s["range"] == 4
        assert s["cooldown_turns"] == 10
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is False
        assert s["allowed_classes"] == ["shaman"]

    def test_soul_anchor_effect(self, loaded_skills):
        s = get_skill("soul_anchor")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "soul_anchor"
        assert effect["survive_hp"] == 1
        assert effect["duration_turns"] == 4

    def test_soul_anchor_longest_cooldown(self, loaded_skills):
        """Soul Anchor has the longest cooldown (10) of any Shaman skill."""
        s = get_skill("soul_anchor")
        assert s["cooldown_turns"] == 10

    # -- Earthgrasp --

    def test_earthgrasp_exists(self, loaded_skills):
        skill = get_skill("earthgrasp")
        assert skill is not None

    def test_earthgrasp_definition(self, loaded_skills):
        s = get_skill("earthgrasp")
        assert s["skill_id"] == "earthgrasp"
        assert s["name"] == "Earthgrasp Totem"
        assert s["targeting"] == "ground_aoe"
        assert s["range"] == 4
        assert s["cooldown_turns"] == 7
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is True
        assert s["allowed_classes"] == ["shaman"]

    def test_earthgrasp_effect(self, loaded_skills):
        s = get_skill("earthgrasp")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "place_totem"
        assert effect["totem_type"] == "earthgrasp"
        assert effect["totem_hp"] == 20
        assert effect["effect_radius"] == 2
        assert effect["duration_turns"] == 4
        assert effect["root_duration"] == 1


# ============================================================
# 3. Class-Skills Mapping
# ============================================================

class TestShamanClassSkillsMapping:
    """Tests for the class_skills.shaman mapping in skills_config.json."""

    def test_shaman_class_skills_exist(self, loaded_skills):
        skills = get_class_skills("shaman")
        assert skills is not None
        assert len(skills) > 0

    def test_shaman_has_five_skills(self, loaded_skills):
        skills = get_class_skills("shaman")
        assert len(skills) == 5

    def test_shaman_skill_order(self, loaded_skills):
        skills = get_class_skills("shaman")
        assert skills == [
            "auto_attack_ranged",
            "healing_totem",
            "searing_totem",
            "soul_anchor",
            "earthgrasp",
        ]

    def test_shaman_auto_attack_is_ranged(self, loaded_skills):
        """Shaman uses ranged auto-attack (slot 0)."""
        skills = get_class_skills("shaman")
        assert skills[0] == "auto_attack_ranged"

    def test_all_shaman_skills_exist_in_config(self, loaded_skills):
        """Every skill in the shaman mapping must exist in the skills registry."""
        for skill_id in get_class_skills("shaman"):
            skill = get_skill(skill_id)
            assert skill is not None, f"Shaman skill '{skill_id}' not found in skills config"


# ============================================================
# 4. can_use_skill() Validation for Shaman
# ============================================================

class TestShamanCanUseSkill:
    """Tests for can_use_skill() with Shaman class and skills."""

    def test_shaman_can_use_healing_totem(self, loaded_skills):
        player = _make_player(class_id="shaman")
        ok, msg = can_use_skill(player, "healing_totem")
        assert ok is True
        assert msg == ""

    def test_shaman_can_use_searing_totem(self, loaded_skills):
        player = _make_player(class_id="shaman")
        ok, msg = can_use_skill(player, "searing_totem")
        assert ok is True

    def test_shaman_can_use_soul_anchor(self, loaded_skills):
        player = _make_player(class_id="shaman")
        ok, msg = can_use_skill(player, "soul_anchor")
        assert ok is True

    def test_shaman_can_use_earthgrasp(self, loaded_skills):
        player = _make_player(class_id="shaman")
        ok, msg = can_use_skill(player, "earthgrasp")
        assert ok is True

    def test_shaman_can_use_ranged_auto_attack(self, loaded_skills):
        """Shaman should be in auto_attack_ranged allowed_classes."""
        player = _make_player(class_id="shaman")
        ok, msg = can_use_skill(player, "auto_attack_ranged")
        assert ok is True

    def test_non_shaman_cannot_use_healing_totem(self, loaded_skills):
        player = _make_player(class_id="crusader")
        ok, msg = can_use_skill(player, "healing_totem")
        assert ok is False
        assert "class" in msg.lower()

    def test_non_shaman_cannot_use_searing_totem(self, loaded_skills):
        player = _make_player(class_id="ranger")
        ok, msg = can_use_skill(player, "searing_totem")
        assert ok is False

    def test_non_shaman_cannot_use_soul_anchor(self, loaded_skills):
        player = _make_player(class_id="mage")
        ok, msg = can_use_skill(player, "soul_anchor")
        assert ok is False

    def test_non_shaman_cannot_use_earthgrasp(self, loaded_skills):
        player = _make_player(class_id="hexblade")
        ok, msg = can_use_skill(player, "earthgrasp")
        assert ok is False

    def test_dead_shaman_cannot_use_skills(self, loaded_skills):
        player = _make_player(class_id="shaman", alive=False)
        ok, msg = can_use_skill(player, "healing_totem")
        assert ok is False
        assert "dead" in msg

    def test_shaman_skill_on_cooldown_rejected(self, loaded_skills):
        player = _make_player(class_id="shaman", cooldowns={"healing_totem": 4})
        ok, msg = can_use_skill(player, "healing_totem")
        assert ok is False
        assert "cooldown" in msg.lower()
        assert "4" in msg

    def test_shaman_skill_zero_cooldown_allowed(self, loaded_skills):
        player = _make_player(class_id="shaman", cooldowns={"healing_totem": 0})
        ok, msg = can_use_skill(player, "healing_totem")
        assert ok is True


# ============================================================
# 5. MatchState Totems Field
# ============================================================

class TestMatchStateTotems:
    """Tests for the totems field on MatchState model."""

    def test_totems_field_exists(self):
        ms = MatchState(match_id="test_match")
        assert hasattr(ms, "totems")

    def test_totems_default_empty_list(self):
        ms = MatchState(match_id="test_match")
        assert ms.totems == []
        assert isinstance(ms.totems, list)

    def test_totems_accepts_totem_dicts(self):
        healing_totem = {
            "id": "totem_1",
            "type": "healing_totem",
            "owner_id": "shaman1",
            "x": 5, "y": 5,
            "hp": 20, "max_hp": 20,
            "heal_per_turn": 8,
            "damage_per_turn": 0,
            "effect_radius": 2,
            "duration_remaining": 4,
            "team": "team_1",
        }
        ms = MatchState(match_id="test_match", totems=[healing_totem])
        assert len(ms.totems) == 1
        assert ms.totems[0]["type"] == "healing_totem"

    def test_totems_supports_dual_totems(self):
        """A Shaman can have both a healing and searing totem active."""
        healing = {
            "id": "totem_1", "type": "healing_totem", "owner_id": "shaman1",
            "x": 5, "y": 5, "hp": 20, "max_hp": 20,
            "heal_per_turn": 8, "damage_per_turn": 0,
            "effect_radius": 2, "duration_remaining": 4, "team": "team_1",
        }
        searing = {
            "id": "totem_2", "type": "searing_totem", "owner_id": "shaman1",
            "x": 7, "y": 7, "hp": 20, "max_hp": 20,
            "heal_per_turn": 0, "damage_per_turn": 6,
            "effect_radius": 2, "duration_remaining": 4, "team": "team_1",
        }
        ms = MatchState(match_id="test_match", totems=[healing, searing])
        assert len(ms.totems) == 2
        types = {t["type"] for t in ms.totems}
        assert types == {"healing_totem", "searing_totem"}


# ============================================================
# 6. Shaman Names Config
# ============================================================

class TestShamanNamesConfig:
    """Tests for Shaman names in names_config.json."""

    @pytest.fixture
    def names_config(self) -> dict:
        path = Path(__file__).resolve().parent.parent / "configs" / "names_config.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_shaman_names_exist(self, names_config):
        assert "shaman" in names_config

    def test_shaman_has_enough_names(self, names_config):
        assert len(names_config["shaman"]) >= 10

    def test_shaman_names_are_unique(self, names_config):
        names = names_config["shaman"]
        assert len(names) == len(set(names)), "Duplicate shaman names found"

    def test_shaman_names_are_strings(self, names_config):
        for name in names_config["shaman"]:
            assert isinstance(name, str)
            assert len(name) > 0


# ============================================================
# 7. Regression — Existing Classes Still Work
# ============================================================

class TestRegressionExistingClasses:
    """Verify existing class definitions/skills are not broken by Shaman addition."""

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

    def test_revenant_still_exists(self, loaded_classes):
        assert "revenant" in loaded_classes
        assert loaded_classes["revenant"].base_hp == 130

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
        assert get_class_skills("revenant") == [
            "auto_attack_melee", "grave_thorns", "grave_chains",
            "undying_will", "soul_rend"
        ]

    def test_revenant_auto_attack_unchanged(self, loaded_skills):
        """Revenant still uses melee auto-attack — verify no contamination."""
        skill = get_skill("auto_attack_melee")
        assert "revenant" in skill["allowed_classes"]

    def test_auto_attack_ranged_includes_shaman(self, loaded_skills):
        """Shaman was added to auto_attack_ranged allowed_classes."""
        skill = get_skill("auto_attack_ranged")
        assert "shaman" in skill["allowed_classes"]

    def test_auto_attack_ranged_still_includes_originals(self, loaded_skills):
        """Original ranged auto-attack classes are still present."""
        skill = get_skill("auto_attack_ranged")
        for cls in ["ranger", "mage", "bard", "plague_doctor"]:
            assert cls in skill["allowed_classes"], f"{cls} missing from auto_attack_ranged"
