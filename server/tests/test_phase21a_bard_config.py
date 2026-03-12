"""
Tests for Phase 21A: Bard class config & data model.

Covers:
- Bard class loads correctly from classes_config.json
- Bard base stats match design spec
- All 4 Bard skills load from skills_config.json
- Bard skill definitions have correct fields and values
- class_skills["bard"] maps correctly (5 skills)
- can_use_skill() validates Bard skills for bard class
- can_use_skill() rejects Bard skills for non-bard classes
- Bard names exist in names_config.json
- apply_class_stats() works for Bard
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

# Reset classes cache between tests
_classes_cache_attr = "_classes_cache"

@pytest.fixture(autouse=True)
def _reset_caches():
    """Clear cached configs before each test to ensure isolation."""
    clear_skills_cache()
    # Reset classes cache
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
    class_id: str = "bard",
    hp: int = 90,
    alive: bool = True,
    cooldowns: dict | None = None,
    team: str = "team_1",
) -> PlayerState:
    """Helper — create a PlayerState with the given class and state."""
    return PlayerState(
        player_id="bard1",
        username="TestBard",
        position=Position(x=5, y=5),
        class_id=class_id,
        hp=hp,
        max_hp=hp,
        is_alive=alive,
        cooldowns=cooldowns or {},
        team=team,
    )


# ============================================================
# 1. Bard Class Config
# ============================================================

class TestBardClassConfig:
    """Tests for Bard class definition in classes_config.json."""

    def test_bard_class_exists(self, loaded_classes):
        assert "bard" in loaded_classes

    def test_bard_class_definition_type(self, loaded_classes):
        bard = loaded_classes["bard"]
        assert isinstance(bard, ClassDefinition)

    def test_bard_base_hp(self, loaded_classes):
        assert loaded_classes["bard"].base_hp == 110

    def test_bard_base_melee_damage(self, loaded_classes):
        assert loaded_classes["bard"].base_melee_damage == 10

    def test_bard_base_ranged_damage(self, loaded_classes):
        assert loaded_classes["bard"].base_ranged_damage == 12

    def test_bard_base_armor(self, loaded_classes):
        assert loaded_classes["bard"].base_armor == 4

    def test_bard_base_vision_range(self, loaded_classes):
        assert loaded_classes["bard"].base_vision_range == 7

    def test_bard_ranged_range(self, loaded_classes):
        assert loaded_classes["bard"].ranged_range == 4

    def test_bard_allowed_weapons(self, loaded_classes):
        assert loaded_classes["bard"].allowed_weapon_categories == ["caster", "hybrid"]

    def test_bard_color(self, loaded_classes):
        assert loaded_classes["bard"].color == "#d4a017"

    def test_bard_shape(self, loaded_classes):
        assert loaded_classes["bard"].shape == "crescent"

    def test_bard_role(self, loaded_classes):
        assert loaded_classes["bard"].role == "Offensive Support"

    def test_bard_name(self, loaded_classes):
        assert loaded_classes["bard"].name == "Bard"

    def test_get_class_definition_bard(self, loaded_classes):
        bard = get_class_definition("bard")
        assert bard is not None
        assert bard.class_id == "bard"

    def test_apply_class_stats_bard(self, loaded_classes):
        player = PlayerState(player_id="p1", username="Test")
        result = apply_class_stats(player, "bard")
        assert result is True
        assert player.class_id == "bard"
        assert player.hp == 110
        assert player.max_hp == 110
        assert player.attack_damage == 10
        assert player.ranged_damage == 12
        assert player.armor == 4
        assert player.vision_range == 7
        assert player.ranged_range == 4

    def test_total_class_count(self, loaded_classes):
        """Should now have 11 playable classes (Shaman added in Phase 26)."""
        assert len(loaded_classes) == 11


# ============================================================
# 2. Bard Skills Config
# ============================================================

class TestBardSkillsConfig:
    """Tests for Bard skill definitions in skills_config.json."""

    # -- Ballad of Might --

    def test_ballad_of_might_exists(self, loaded_skills):
        skill = get_skill("ballad_of_might")
        assert skill is not None

    def test_ballad_of_might_definition(self, loaded_skills):
        s = get_skill("ballad_of_might")
        assert s["skill_id"] == "ballad_of_might"
        assert s["name"] == "Ballad of Might"
        assert s["targeting"] == "self"
        assert s["range"] == 0
        assert s["cooldown_turns"] == 5
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is False
        assert s["allowed_classes"] == ["bard"]

    def test_ballad_of_might_effect(self, loaded_skills):
        s = get_skill("ballad_of_might")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "aoe_buff"
        assert effect["radius"] == 3
        assert effect["stat"] == "all_damage_multiplier"
        assert effect["magnitude"] == 1.4
        assert effect["duration_turns"] == 3

    # -- Dirge of Weakness --

    def test_dirge_of_weakness_exists(self, loaded_skills):
        skill = get_skill("dirge_of_weakness")
        assert skill is not None

    def test_dirge_of_weakness_definition(self, loaded_skills):
        s = get_skill("dirge_of_weakness")
        assert s["skill_id"] == "dirge_of_weakness"
        assert s["name"] == "Dirge of Weakness"
        assert s["targeting"] == "ground_aoe"
        assert s["range"] == 4
        assert s["cooldown_turns"] == 5
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is True
        assert s["allowed_classes"] == ["bard"]

    def test_dirge_of_weakness_effect(self, loaded_skills):
        s = get_skill("dirge_of_weakness")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "aoe_debuff"
        assert effect["radius"] == 2
        assert effect["stat"] == "damage_taken_multiplier"
        assert effect["magnitude"] == 1.30
        assert effect["duration_turns"] == 3

    # -- Verse of Haste --

    def test_verse_of_haste_exists(self, loaded_skills):
        skill = get_skill("verse_of_haste")
        assert skill is not None

    def test_verse_of_haste_definition(self, loaded_skills):
        s = get_skill("verse_of_haste")
        assert s["skill_id"] == "verse_of_haste"
        assert s["name"] == "Verse of Haste"
        assert s["targeting"] == "ally_or_self"
        assert s["range"] == 4
        assert s["cooldown_turns"] == 5
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is False
        assert s["allowed_classes"] == ["bard"]

    def test_verse_of_haste_effect(self, loaded_skills):
        s = get_skill("verse_of_haste")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "cooldown_reduction"
        assert effect["reduction"] == 2

    # -- Cacophony --

    def test_cacophony_exists(self, loaded_skills):
        skill = get_skill("cacophony")
        assert skill is not None

    def test_cacophony_definition(self, loaded_skills):
        s = get_skill("cacophony")
        assert s["skill_id"] == "cacophony"
        assert s["name"] == "Cacophony"
        assert s["targeting"] == "self"
        assert s["range"] == 0
        assert s["cooldown_turns"] == 5
        assert s["mana_cost"] == 0
        assert s["requires_line_of_sight"] is False
        assert s["allowed_classes"] == ["bard"]

    def test_cacophony_effect(self, loaded_skills):
        s = get_skill("cacophony")
        assert len(s["effects"]) == 1
        effect = s["effects"][0]
        assert effect["type"] == "aoe_damage_slow"
        assert effect["radius"] == 2
        assert effect["base_damage"] == 11
        assert effect["slow_duration"] == 2

    def test_cacophony_uses_existing_effect_type(self, loaded_skills):
        """Cacophony reuses the same aoe_damage_slow type as Frost Nova."""
        cacophony = get_skill("cacophony")
        frost_nova = get_skill("frost_nova")
        assert cacophony["effects"][0]["type"] == frost_nova["effects"][0]["type"]

    def test_cacophony_weaker_than_frost_nova(self, loaded_skills):
        """Bard's Cacophony should deal less damage than Mage's Frost Nova."""
        cacophony = get_skill("cacophony")
        frost_nova = get_skill("frost_nova")
        assert cacophony["effects"][0]["base_damage"] < frost_nova["effects"][0]["base_damage"]


# ============================================================
# 3. Class-Skills Mapping
# ============================================================

class TestBardClassSkillsMapping:
    """Tests for the class_skills.bard mapping in skills_config.json."""

    def test_bard_class_skills_exist(self, loaded_skills):
        skills = get_class_skills("bard")
        assert skills is not None
        assert len(skills) > 0

    def test_bard_has_five_skills(self, loaded_skills):
        skills = get_class_skills("bard")
        assert len(skills) == 5

    def test_bard_skill_order(self, loaded_skills):
        skills = get_class_skills("bard")
        assert skills == [
            "auto_attack_ranged",
            "ballad_of_might",
            "dirge_of_weakness",
            "verse_of_haste",
            "cacophony",
        ]

    def test_bard_auto_attack_is_ranged(self, loaded_skills):
        """Bard uses ranged auto-attack (slot 0)."""
        skills = get_class_skills("bard")
        assert skills[0] == "auto_attack_ranged"

    def test_all_bard_skills_exist_in_config(self, loaded_skills):
        """Every skill in the bard mapping must exist in the skills registry."""
        for skill_id in get_class_skills("bard"):
            skill = get_skill(skill_id)
            assert skill is not None, f"Bard skill '{skill_id}' not found in skills config"


# ============================================================
# 4. can_use_skill() Validation for Bard
# ============================================================

class TestBardCanUseSkill:
    """Tests for can_use_skill() with Bard class and skills."""

    def test_bard_can_use_ballad_of_might(self, loaded_skills):
        player = _make_player(class_id="bard")
        ok, msg = can_use_skill(player, "ballad_of_might")
        assert ok is True
        assert msg == ""

    def test_bard_can_use_dirge_of_weakness(self, loaded_skills):
        player = _make_player(class_id="bard")
        ok, msg = can_use_skill(player, "dirge_of_weakness")
        assert ok is True

    def test_bard_can_use_verse_of_haste(self, loaded_skills):
        player = _make_player(class_id="bard")
        ok, msg = can_use_skill(player, "verse_of_haste")
        assert ok is True

    def test_bard_can_use_cacophony(self, loaded_skills):
        player = _make_player(class_id="bard")
        ok, msg = can_use_skill(player, "cacophony")
        assert ok is True

    def test_bard_can_use_ranged_auto_attack(self, loaded_skills):
        """Bard is in auto_attack_ranged allowed_classes."""
        player = _make_player(class_id="bard")
        ok, msg = can_use_skill(player, "auto_attack_ranged")
        assert ok is True

    def test_non_bard_cannot_use_ballad(self, loaded_skills):
        player = _make_player(class_id="crusader")
        ok, msg = can_use_skill(player, "ballad_of_might")
        assert ok is False
        assert "class" in msg.lower()

    def test_non_bard_cannot_use_dirge(self, loaded_skills):
        player = _make_player(class_id="ranger")
        ok, msg = can_use_skill(player, "dirge_of_weakness")
        assert ok is False

    def test_non_bard_cannot_use_verse(self, loaded_skills):
        player = _make_player(class_id="mage")
        ok, msg = can_use_skill(player, "verse_of_haste")
        assert ok is False

    def test_non_bard_cannot_use_cacophony(self, loaded_skills):
        player = _make_player(class_id="hexblade")
        ok, msg = can_use_skill(player, "cacophony")
        assert ok is False

    def test_dead_bard_cannot_use_skills(self, loaded_skills):
        player = _make_player(class_id="bard", alive=False)
        ok, msg = can_use_skill(player, "ballad_of_might")
        assert ok is False
        assert "dead" in msg

    def test_bard_skill_on_cooldown_rejected(self, loaded_skills):
        player = _make_player(class_id="bard", cooldowns={"ballad_of_might": 4})
        ok, msg = can_use_skill(player, "ballad_of_might")
        assert ok is False
        assert "cooldown" in msg.lower()
        assert "4" in msg

    def test_bard_skill_zero_cooldown_allowed(self, loaded_skills):
        player = _make_player(class_id="bard", cooldowns={"ballad_of_might": 0})
        ok, msg = can_use_skill(player, "ballad_of_might")
        assert ok is True


# ============================================================
# 5. Bard Names Config
# ============================================================

class TestBardNamesConfig:
    """Tests for Bard names in names_config.json."""

    @pytest.fixture
    def names_config(self) -> dict:
        path = Path(__file__).resolve().parent.parent / "configs" / "names_config.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_bard_names_exist(self, names_config):
        assert "bard" in names_config

    def test_bard_has_enough_names(self, names_config):
        assert len(names_config["bard"]) >= 10

    def test_bard_names_are_unique(self, names_config):
        names = names_config["bard"]
        assert len(names) == len(set(names)), "Duplicate bard names found"

    def test_bard_names_are_strings(self, names_config):
        for name in names_config["bard"]:
            assert isinstance(name, str)
            assert len(name) > 0
