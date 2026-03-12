"""
Tests for Phase 6A: Skills config, server models, class-skill mapping.

Covers:
- skills_config.json loading and parsing (all 5 skills)
- get_skill() returns correct skill definitions
- get_class_skills() returns correct skill lists per class
- get_all_skills() returns full registry
- get_max_skill_slots() returns config value
- can_use_skill() validates cooldown, class restriction, alive status
- ActionType.SKILL serializes/deserializes correctly
- PlayerAction with skill_id field works
- ActionResult with skill_id, buff_applied, heal_amount fields
- TurnResult with buff_changes field
- PlayerState.active_buffs field (default empty, can be populated)
- Backward compat — SKILL enum doesn't break existing model behavior
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.actions import ActionType, PlayerAction, ActionResult, TurnResult
from app.models.player import PlayerState, Position
from app.core.skills import (
    load_skills_config,
    clear_skills_cache,
    get_skill,
    get_all_skills,
    get_class_skills,
    get_max_skill_slots,
    can_use_skill,
)


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def _reset_skills_cache():
    """Clear cached config before each test to ensure isolation."""
    clear_skills_cache()
    yield
    clear_skills_cache()


@pytest.fixture
def skills_config_path() -> Path:
    """Path to the real skills_config.json."""
    return Path(__file__).resolve().parent.parent / "configs" / "skills_config.json"


@pytest.fixture
def loaded_config(skills_config_path: Path) -> dict:
    """Load and return the skills config dict."""
    return load_skills_config(skills_config_path)


def _make_player(class_id: str = "crusader", hp: int = 100, alive: bool = True, cooldowns: dict | None = None) -> PlayerState:
    """Helper — create a PlayerState with the given class and state."""
    return PlayerState(
        player_id="p1",
        username="TestPlayer",
        position=Position(x=5, y=5),
        class_id=class_id,
        hp=hp,
        max_hp=100,
        is_alive=alive,
        cooldowns=cooldowns or {},
    )


# ============================================================
# 1. Config Loading & Parsing
# ============================================================

class TestSkillsConfigLoading:
    """Tests for skills_config.json loading and structure."""

    def test_config_loads_successfully(self, loaded_config: dict):
        assert loaded_config is not None
        assert "skills" in loaded_config
        assert "class_skills" in loaded_config
        assert "max_skill_slots" in loaded_config

    def test_config_has_five_skills(self, loaded_config: dict):
        skills = loaded_config["skills"]
        assert len(skills) == 52

    def test_all_skill_ids_present(self, loaded_config: dict):
        expected = {
            "auto_attack_melee", "auto_attack_ranged",
            "heal", "double_strike", "power_shot", "war_cry", "shadow_step",
            "wither", "ward", "shield_of_faith", "exorcism", "prayer",
            "rebuke", "seal_of_judgment", "venom_gaze", "soul_reap",
            "taunt", "shield_bash", "holy_ground", "bulwark",
            "volley", "evasion", "crippling_shot",
            "fireball", "frost_nova", "arcane_barrage", "blink",
            # Phase 18I — enemy identity skills
            "enrage", "bone_shield", "frenzy_aura", "dark_pact", "profane_ward",
            # Phase 21 — Bard skills
            "ballad_of_might", "dirge_of_weakness", "verse_of_haste", "cacophony",
            # Phase 22 — Blood Knight skills
            "blood_strike", "crimson_veil", "sanguine_burst", "blood_frenzy",
            # Phase 23 — Plague Doctor skills
            "miasma", "plague_flask", "enfeeble", "inoculate",
            # Phase 25 — Revenant skills
            "grave_thorns", "grave_chains", "undying_will", "soul_rend",
            # Phase 26 — Shaman skills
            "healing_totem", "searing_totem", "soul_anchor", "earthgrasp",
        }
        assert set(loaded_config["skills"].keys()) == expected

    def test_skill_has_required_fields(self, loaded_config: dict):
        required_fields = [
            "skill_id", "name", "description", "icon", "targeting",
            "range", "cooldown_turns", "mana_cost", "effects",
            "allowed_classes", "requires_line_of_sight",
        ]
        for skill_id, skill_def in loaded_config["skills"].items():
            for field in required_fields:
                assert field in skill_def, f"Skill '{skill_id}' missing field '{field}'"

    def test_heal_skill_definition(self, loaded_config: dict):
        heal = loaded_config["skills"]["heal"]
        assert heal["skill_id"] == "heal"
        assert heal["targeting"] == "ally_or_self"
        assert heal["range"] == 3
        assert heal["cooldown_turns"] == 4
        assert heal["allowed_classes"] == ["confessor", "acolyte", "dark_priest"]
        assert len(heal["effects"]) == 1
        assert heal["effects"][0]["type"] == "heal"
        assert heal["effects"][0]["magnitude"] == 30

    def test_double_strike_skill_definition(self, loaded_config: dict):
        ds = loaded_config["skills"]["double_strike"]
        assert ds["targeting"] == "enemy_adjacent"
        assert ds["range"] == 1
        assert ds["cooldown_turns"] == 3
        assert "hexblade" in ds["allowed_classes"]
        assert "werewolf" in ds["allowed_classes"]
        assert ds["effects"][0]["type"] == "melee_damage"
        assert ds["effects"][0]["hits"] == 2
        assert ds["effects"][0]["damage_multiplier"] == 0.7

    def test_power_shot_skill_definition(self, loaded_config: dict):
        ps = loaded_config["skills"]["power_shot"]
        assert ps["targeting"] == "enemy_ranged"
        assert ps["range"] == 0  # uses unit's own ranged_range
        assert ps["cooldown_turns"] == 7
        assert ps["allowed_classes"] == ["inquisitor", "ranger", "medusa"]
        assert ps["requires_line_of_sight"] is True
        assert ps["effects"][0]["damage_multiplier"] == 1.8

    def test_war_cry_skill_definition(self, loaded_config: dict):
        wc = loaded_config["skills"]["war_cry"]
        assert wc["targeting"] == "self"
        assert wc["cooldown_turns"] == 5
        assert "werewolf" in wc["allowed_classes"]
        effect = wc["effects"][0]
        assert effect["type"] == "buff"
        assert effect["stat"] == "melee_damage_multiplier"
        assert effect["magnitude"] == 2.0
        assert effect["duration_turns"] == 2

    def test_shadow_step_skill_definition(self, loaded_config: dict):
        ss = loaded_config["skills"]["shadow_step"]
        assert ss["targeting"] == "empty_tile"
        assert ss["range"] == 3
        assert ss["cooldown_turns"] == 4
        assert "hexblade" in ss["allowed_classes"]
        assert "inquisitor" in ss["allowed_classes"]
        assert "wraith" in ss["allowed_classes"]
        assert ss["requires_line_of_sight"] is True
        assert ss["effects"][0]["type"] == "teleport"

    def test_max_skill_slots(self, loaded_config: dict):
        assert loaded_config["max_skill_slots"] == 6

    def test_all_skills_have_mana_cost_zero(self, loaded_config: dict):
        """Mana is reserved for future — all current skills cost 0."""
        for skill_id, skill_def in loaded_config["skills"].items():
            assert skill_def["mana_cost"] == 0, f"Skill '{skill_id}' has non-zero mana_cost"

    def test_config_caching(self, skills_config_path: Path):
        """Loading twice returns the same cached dict."""
        config1 = load_skills_config(skills_config_path)
        config2 = load_skills_config(skills_config_path)
        assert config1 is config2

    def test_missing_config_returns_defaults(self, tmp_path: Path):
        """If config file doesn't exist, return safe defaults."""
        fake_path = tmp_path / "nonexistent.json"
        config = load_skills_config(fake_path)
        assert config["skills"] == {}
        assert config["class_skills"] == {}
        assert config["max_skill_slots"] == 4


# ============================================================
# 2. Skill Lookup Functions
# ============================================================

class TestSkillLookups:
    """Tests for get_skill, get_all_skills, get_class_skills, get_max_skill_slots."""

    def test_get_skill_returns_definition(self, loaded_config: dict):
        skill = get_skill("heal")
        assert skill is not None
        assert skill["skill_id"] == "heal"
        assert skill["name"] == "Heal"

    def test_get_skill_returns_none_for_unknown(self, loaded_config: dict):
        result = get_skill("nonexistent_skill")
        assert result is None

    def test_get_all_skills_returns_all(self, loaded_config: dict):
        all_skills = get_all_skills()
        assert len(all_skills) == 52
        assert "heal" in all_skills
        assert "double_strike" in all_skills
        assert "auto_attack_melee" in all_skills
        assert "auto_attack_ranged" in all_skills
        assert "fireball" in all_skills
        assert "miasma" in all_skills
        assert "ballad_of_might" in all_skills
        assert "blood_strike" in all_skills

    def test_get_class_skills_crusader(self, loaded_config: dict):
        skills = get_class_skills("crusader")
        assert skills == ["auto_attack_melee", "taunt", "shield_bash", "holy_ground", "bulwark"]

    def test_get_class_skills_confessor(self, loaded_config: dict):
        skills = get_class_skills("confessor")
        assert skills == ["auto_attack_melee", "heal", "shield_of_faith", "exorcism", "prayer"]

    def test_get_class_skills_inquisitor(self, loaded_config: dict):
        skills = get_class_skills("inquisitor")
        assert skills == ["auto_attack_ranged", "power_shot", "shadow_step", "seal_of_judgment", "rebuke"]

    def test_get_class_skills_ranger(self, loaded_config: dict):
        skills = get_class_skills("ranger")
        assert skills == ["auto_attack_ranged", "power_shot", "volley", "evasion", "crippling_shot"]

    def test_get_class_skills_hexblade(self, loaded_config: dict):
        skills = get_class_skills("hexblade")
        assert skills == ["auto_attack_melee", "double_strike", "shadow_step", "wither", "ward"]

    def test_get_class_skills_unknown_class(self, loaded_config: dict):
        skills = get_class_skills("warlock")
        assert skills == []

    def test_get_max_skill_slots(self, loaded_config: dict):
        assert get_max_skill_slots() == 6


# ============================================================
# 3. Skill Validation (can_use_skill)
# ============================================================

class TestCanUseSkill:
    """Tests for can_use_skill validation logic."""

    def test_valid_skill_usage(self, loaded_config: dict):
        player = _make_player(class_id="crusader")
        ok, msg = can_use_skill(player, "shield_bash")
        assert ok is True
        assert msg == ""

    def test_unknown_skill_rejected(self, loaded_config: dict):
        player = _make_player(class_id="crusader")
        ok, msg = can_use_skill(player, "totally_fake_skill")
        assert ok is False
        assert "Unknown skill" in msg

    def test_dead_player_rejected(self, loaded_config: dict):
        player = _make_player(class_id="crusader", alive=False)
        ok, msg = can_use_skill(player, "shield_bash")
        assert ok is False
        assert "dead" in msg

    def test_wrong_class_rejected(self, loaded_config: dict):
        player = _make_player(class_id="ranger")
        ok, msg = can_use_skill(player, "heal")
        assert ok is False
        assert "class" in msg.lower()

    def test_cooldown_blocks_skill(self, loaded_config: dict):
        player = _make_player(class_id="crusader", cooldowns={"shield_bash": 2})
        ok, msg = can_use_skill(player, "shield_bash")
        assert ok is False
        assert "cooldown" in msg.lower()
        assert "2" in msg

    def test_zero_cooldown_allows_skill(self, loaded_config: dict):
        player = _make_player(class_id="crusader", cooldowns={"shield_bash": 0})
        ok, msg = can_use_skill(player, "shield_bash")
        assert ok is True

    def test_confessor_can_heal(self, loaded_config: dict):
        player = _make_player(class_id="confessor")
        ok, msg = can_use_skill(player, "heal")
        assert ok is True

    def test_hexblade_can_shadow_step(self, loaded_config: dict):
        player = _make_player(class_id="hexblade")
        ok, msg = can_use_skill(player, "shadow_step")
        assert ok is True

    def test_ranger_cannot_double_strike(self, loaded_config: dict):
        player = _make_player(class_id="ranger")
        ok, msg = can_use_skill(player, "double_strike")
        assert ok is False

    def test_crusader_can_war_cry(self, loaded_config: dict):
        """Crusader no longer has war_cry (Phase 12 rework)."""
        player = _make_player(class_id="crusader")
        ok, msg = can_use_skill(player, "war_cry")
        assert ok is False

    def test_inquisitor_can_power_shot(self, loaded_config: dict):
        player = _make_player(class_id="inquisitor")
        ok, msg = can_use_skill(player, "power_shot")
        assert ok is True

    def test_null_class_rejected_for_class_restricted_skill(self, loaded_config: dict):
        """Legacy players (class_id=None) can't use class-restricted skills."""
        player = _make_player(class_id=None)
        ok, msg = can_use_skill(player, "heal")
        assert ok is False


# ============================================================
# 4. ActionType.SKILL Enum
# ============================================================

class TestActionTypeSKILL:
    """Tests for the new SKILL enum value."""

    def test_skill_enum_exists(self):
        assert ActionType.SKILL == "skill"

    def test_skill_enum_value(self):
        assert ActionType.SKILL.value == "skill"

    def test_skill_enum_from_string(self):
        assert ActionType("skill") == ActionType.SKILL

    def test_all_existing_enums_still_work(self):
        """Backward compat: existing action types unaffected."""
        assert ActionType("move") == ActionType.MOVE
        assert ActionType("attack") == ActionType.ATTACK
        assert ActionType("ranged_attack") == ActionType.RANGED_ATTACK
        assert ActionType("wait") == ActionType.WAIT
        assert ActionType("interact") == ActionType.INTERACT
        assert ActionType("loot") == ActionType.LOOT
        assert ActionType("use_item") == ActionType.USE_ITEM

    def test_skill_serializes_to_json(self):
        action = PlayerAction(
            player_id="p1",
            action_type=ActionType.SKILL,
            skill_id="heal",
        )
        data = action.model_dump()
        assert data["action_type"] == "skill"
        assert data["skill_id"] == "heal"


# ============================================================
# 5. PlayerAction with skill_id
# ============================================================

class TestPlayerActionSkillId:
    """Tests for the optional skill_id field on PlayerAction."""

    def test_skill_id_default_none(self):
        action = PlayerAction(player_id="p1", action_type=ActionType.MOVE, target_x=3, target_y=4)
        assert action.skill_id is None

    def test_skill_id_set_for_skill_action(self):
        action = PlayerAction(
            player_id="p1",
            action_type=ActionType.SKILL,
            target_x=5,
            target_y=5,
            skill_id="double_strike",
        )
        assert action.skill_id == "double_strike"
        assert action.action_type == ActionType.SKILL

    def test_skill_id_ignored_for_non_skill_action(self):
        """skill_id can technically be set on any action, but it's only meaningful for SKILL."""
        action = PlayerAction(
            player_id="p1",
            action_type=ActionType.MOVE,
            skill_id="heal",
        )
        assert action.skill_id == "heal"  # field exists, just ignored by resolver

    def test_backward_compat_existing_actions(self):
        """Existing actions work without skill_id."""
        action = PlayerAction(player_id="p1", action_type=ActionType.ATTACK, target_x=3, target_y=4)
        assert action.skill_id is None
        assert action.target_x == 3


# ============================================================
# 6. ActionResult Skill Fields
# ============================================================

class TestActionResultSkillFields:
    """Tests for skill_id, buff_applied, heal_amount on ActionResult."""

    def test_default_skill_fields_none(self):
        result = ActionResult(
            player_id="p1",
            username="Test",
            action_type=ActionType.ATTACK,
        )
        assert result.skill_id is None
        assert result.buff_applied is None
        assert result.heal_amount is None

    def test_skill_result_with_heal_amount(self):
        result = ActionResult(
            player_id="p1",
            username="Confessor",
            action_type=ActionType.SKILL,
            skill_id="heal",
            heal_amount=30,
        )
        assert result.skill_id == "heal"
        assert result.heal_amount == 30

    def test_skill_result_with_buff(self):
        result = ActionResult(
            player_id="p1",
            username="Crusader",
            action_type=ActionType.SKILL,
            skill_id="war_cry",
            buff_applied={"stat": "melee_damage_multiplier", "magnitude": 2.0, "duration": 2},
        )
        assert result.buff_applied["stat"] == "melee_damage_multiplier"
        assert result.buff_applied["magnitude"] == 2.0

    def test_backward_compat_action_result(self):
        """Old-style ActionResult (without skill fields) still works."""
        result = ActionResult(
            player_id="p1",
            username="Player1",
            action_type=ActionType.ATTACK,
            damage_dealt=15,
            killed=True,
        )
        assert result.damage_dealt == 15
        assert result.killed is True
        assert result.skill_id is None


# ============================================================
# 7. TurnResult buff_changes
# ============================================================

class TestTurnResultBuffChanges:
    """Tests for buff_changes field on TurnResult."""

    def test_default_buff_changes_empty(self):
        tr = TurnResult(match_id="m1", turn_number=1)
        assert tr.buff_changes == []

    def test_buff_changes_populated(self):
        tr = TurnResult(
            match_id="m1",
            turn_number=1,
            buff_changes=[
                {"player_id": "p1", "buffs": [{"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 2}]},
            ],
        )
        assert len(tr.buff_changes) == 1
        assert tr.buff_changes[0]["player_id"] == "p1"

    def test_backward_compat_turn_result(self):
        """Existing TurnResult fields still work."""
        tr = TurnResult(
            match_id="m1",
            turn_number=5,
            deaths=["p2"],
            winner="p1",
        )
        assert tr.deaths == ["p2"]
        assert tr.winner == "p1"
        assert tr.buff_changes == []


# ============================================================
# 8. PlayerState.active_buffs
# ============================================================

class TestPlayerStateActiveBuffs:
    """Tests for the active_buffs field on PlayerState."""

    def test_default_active_buffs_empty(self):
        player = PlayerState(player_id="p1", username="Test")
        assert player.active_buffs == []

    def test_active_buffs_can_be_set(self):
        player = PlayerState(
            player_id="p1",
            username="Test",
            active_buffs=[
                {"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 2}
            ],
        )
        assert len(player.active_buffs) == 1
        assert player.active_buffs[0]["buff_id"] == "war_cry"

    def test_active_buffs_multiple(self):
        player = PlayerState(
            player_id="p1",
            username="Test",
            active_buffs=[
                {"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 2},
                {"buff_id": "shield", "stat": "armor", "magnitude": 5, "turns_remaining": 3},
            ],
        )
        assert len(player.active_buffs) == 2

    def test_active_buffs_mutable(self):
        player = PlayerState(player_id="p1", username="Test")
        player.active_buffs.append(
            {"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 2}
        )
        assert len(player.active_buffs) == 1

    def test_active_buffs_removal(self):
        player = PlayerState(
            player_id="p1",
            username="Test",
            active_buffs=[
                {"buff_id": "war_cry", "stat": "melee_damage_multiplier", "magnitude": 2.0, "turns_remaining": 1},
            ],
        )
        # Simulate tick: decrement and remove expired
        remaining = []
        for buff in player.active_buffs:
            buff["turns_remaining"] -= 1
            if buff["turns_remaining"] > 0:
                remaining.append(buff)
        player.active_buffs = remaining
        assert player.active_buffs == []

    def test_backward_compat_player_state(self):
        """Creating a PlayerState without active_buffs works (defaults to [])."""
        player = PlayerState(
            player_id="p1",
            username="Test",
            hp=80,
            attack_damage=20,
        )
        assert player.active_buffs == []
        assert player.hp == 80


# ============================================================
# 9. Class-Skill Mapping Cross-Validation
# ============================================================

class TestClassSkillMapping:
    """Cross-validate that class_skills entries reference valid skills."""

    def test_all_class_skill_refs_are_valid(self, loaded_config: dict):
        """Every skill_id in class_skills must exist in the skills dict."""
        valid_skills = set(loaded_config["skills"].keys())
        for class_id, skill_list in loaded_config["class_skills"].items():
            for sid in skill_list:
                assert sid in valid_skills, f"class_skills['{class_id}'] references unknown skill '{sid}'"

    def test_all_skills_are_referenced_by_at_least_one_class(self, loaded_config: dict):
        """Every defined skill should be used by at least one class."""
        all_referenced = set()
        for skill_list in loaded_config["class_skills"].values():
            all_referenced.update(skill_list)
        for skill_id in loaded_config["skills"]:
            assert skill_id in all_referenced, f"Skill '{skill_id}' is not assigned to any class"

    def test_class_skills_within_max_slots(self, loaded_config: dict):
        """No class should have more skills than max_skill_slots."""
        max_slots = loaded_config["max_skill_slots"]
        for class_id, skill_list in loaded_config["class_skills"].items():
            assert len(skill_list) <= max_slots, (
                f"Class '{class_id}' has {len(skill_list)} skills, exceeds max_skill_slots={max_slots}"
            )

    def test_allowed_classes_consistent_with_class_skills(self, loaded_config: dict):
        """If a skill lists a class in allowed_classes, that class should have the skill in class_skills."""
        for skill_id, skill_def in loaded_config["skills"].items():
            for cls in skill_def["allowed_classes"]:
                class_skills = loaded_config["class_skills"].get(cls, [])
                assert skill_id in class_skills, (
                    f"Skill '{skill_id}' allows class '{cls}', but '{cls}' doesn't list it in class_skills"
                )
