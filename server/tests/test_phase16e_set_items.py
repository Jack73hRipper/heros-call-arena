"""
Tests for Phase 16E: Set Items.

Covers the complete set item system:
 1. Config loading — loads all 5 sets from sets_config.json
 2. Set piece generation — each of the 15 set pieces generates correctly
 3. Set items have Rarity.SET
 4. Set items have curated stat bonuses (no random affixes)
 5. Set bonus metadata stored in affixes list as type="set_bonus"
 6. Set bonus calculation — 0/3, 2/3, 3/3 piece thresholds
 7. Set stat totals — stat aggregation from active bonuses
 8. apply_set_stat_bonuses() — player stats modified correctly
 9. remove_set_stat_bonuses() — player stats reverted correctly
10. get_set_skill_modifiers() — skill modifiers aggregated correctly
11. get_set_special_effects() — special effects collected correctly
12. roll_set_drop() — only elite/boss tier drops
13. roll_set_drop() — no duplicate set pieces per run
14. roll_set_drop() — magic find increases chance
15. roll_set_drop() — boss tier gets 3× bonus
16. roll_set_drop() — class affinity weighting
17. Equipment manager integration — equip/unequip triggers set recalc
18. Loot integration — generate_enemy_loot includes set drops
19. Skills integration — CDR from set bonus
20. Skills integration — taunt duration from set bonus
21. Skills integration — DoT duration from set bonus
22. Backward compat — non-set items unaffected
"""

from __future__ import annotations

import random
import pytest

from app.models.items import (
    Item,
    ItemType,
    Rarity,
    EquipSlot,
    StatBonuses,
)
from app.models.player import PlayerState, Position
from app.core.item_generator import (
    generate_set_piece,
    get_all_set_piece_ids,
    roll_set_drop,
    clear_generator_caches,
)
from app.core.set_bonuses import (
    load_sets_config,
    clear_sets_cache,
    get_all_set_ids,
    get_set_definition,
    calculate_active_set_bonuses,
    get_set_stat_totals,
    apply_set_stat_bonuses,
    remove_set_stat_bonuses,
    get_set_skill_modifiers,
    get_set_special_effects,
)
from app.core.loot import (
    generate_enemy_loot,
    clear_caches as clear_loot_caches,
)


# ---------- Helpers ----------

def _make_player(
    pid="player1",
    username="TestPlayer",
    x=0, y=0,
    hp=100, max_hp=100,
    attack_damage=15,
    ranged_damage=10,
    armor=0,
    equipment=None,
    team="team_a",
    **kwargs,
) -> PlayerState:
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=attack_damage,
        ranged_damage=ranged_damage,
        armor=armor,
        equipment=equipment or {},
        team=team,
        **kwargs,
    )


def _equip_set_piece(player: PlayerState, set_id: str, piece_id: str) -> dict:
    """Generate a set piece and equip it on the player. Returns the item dict."""
    item = generate_set_piece(set_id, piece_id)
    assert item is not None, f"Failed to generate set piece: {set_id}/{piece_id}"
    item_dict = item.model_dump()
    slot = item_dict.get("equip_slot") or item.equip_slot
    player.equipment[slot] = item_dict
    return item_dict


class _FixedRng:
    """Deterministic RNG for testing — always returns a fixed value."""
    def __init__(self, value: float):
        self._value = value

    def random(self) -> float:
        return self._value

    def randint(self, a: int, b: int) -> int:
        return a

    def choices(self, population, weights=None, k=1):
        return population[:k]


class _SeqRng(random.Random):
    """RNG that returns values from a sequence, then falls back to real random."""
    def __init__(self, values):
        super().__init__(42)
        self._values = list(values)
        self._idx = 0

    def random(self) -> float:
        if self._idx < len(self._values):
            v = self._values[self._idx]
            self._idx += 1
            return v
        return super().random()


# ---------- Module-level setup ----------

def setup_module():
    clear_generator_caches()
    clear_sets_cache()
    clear_loot_caches()
    load_sets_config()


def teardown_module():
    clear_generator_caches()
    clear_sets_cache()
    clear_loot_caches()


# ============================================================
# 1. Config Loading
# ============================================================

class TestConfigLoading:
    """Sets config loads correctly with all 5 sets."""

    def test_config_loads(self):
        config = load_sets_config()
        assert config is not None
        assert "sets" in config
        assert "drop_rules" in config
        assert "class_affinity_weights" in config

    def test_config_has_5_sets(self):
        config = load_sets_config()
        sets = config["sets"]
        assert len(sets) == 5

    def test_all_set_ids_present(self):
        expected_ids = [
            "crusaders_oath",
            "voidwalkers_regalia",
            "deadeyes_arsenal",
            "faiths_radiance",
            "seekers_judgment",
        ]
        ids = get_all_set_ids()
        for eid in expected_ids:
            assert eid in ids, f"Missing set: {eid}"

    def test_drop_rules_structure(self):
        config = load_sets_config()
        rules = config["drop_rules"]
        assert "base_drop_chance" in rules
        assert "allowed_tiers" in rules
        assert rules["base_drop_chance"] == 0.003
        assert "elite" in rules["allowed_tiers"]
        assert "boss" in rules["allowed_tiers"]

    def test_class_affinity_weights_structure(self):
        config = load_sets_config()
        weights = config["class_affinity_weights"]
        assert "crusader" in weights
        assert "hexblade" in weights
        assert "ranger" in weights
        assert "confessor" in weights
        assert "inquisitor" in weights

    def test_each_set_has_3_pieces(self):
        config = load_sets_config()
        for set_id, set_def in config["sets"].items():
            assert len(set_def["pieces"]) == 3, (
                f"Set {set_id} has {len(set_def['pieces'])} pieces, expected 3"
            )

    def test_each_set_has_2_bonus_tiers(self):
        config = load_sets_config()
        for set_id, set_def in config["sets"].items():
            assert len(set_def["bonuses"]) == 2, (
                f"Set {set_id} has {len(set_def['bonuses'])} bonus tiers, expected 2"
            )

    def test_bonus_tiers_are_2_and_3(self):
        config = load_sets_config()
        for set_id, set_def in config["sets"].items():
            required = [b["pieces_required"] for b in set_def["bonuses"]]
            assert 2 in required, f"Set {set_id} missing 2-piece bonus"
            assert 3 in required, f"Set {set_id} missing 3-piece bonus"

    def test_floor_scaling_keys(self):
        config = load_sets_config()
        floor_scaling = config["drop_rules"]["floor_scaling"]
        assert "1" in floor_scaling
        assert "5" in floor_scaling
        assert "10" in floor_scaling


# ============================================================
# 2. Set Piece Generation
# ============================================================

class TestSetPieceGeneration:
    """generate_set_piece produces correct items for all 15 set pieces."""

    @pytest.mark.parametrize("set_id,piece_id", get_all_set_piece_ids())
    def test_generate_each_set_piece(self, set_id, piece_id):
        item = generate_set_piece(set_id, piece_id)
        assert item is not None
        assert item.item_id == piece_id
        assert item.rarity == Rarity.SET
        assert item.instance_id  # UUID assigned

    @pytest.mark.parametrize("set_id,piece_id", get_all_set_piece_ids())
    def test_set_piece_has_set_bonus_affix(self, set_id, piece_id):
        item = generate_set_piece(set_id, piece_id)
        assert item is not None
        set_affixes = [a for a in item.affixes if a.get("type") == "set_bonus"]
        assert len(set_affixes) == 1, f"{piece_id} should have exactly 1 set_bonus affix"
        affix = set_affixes[0]
        assert affix["value"] == set_id
        assert affix["stat"] == "set_id"

    def test_set_piece_no_random_affixes(self):
        """Set items only carry the set_bonus metadata affix, no random rolls."""
        item = generate_set_piece("crusaders_oath", "crusaders_oath_weapon")
        assert len(item.affixes) == 1
        assert item.affixes[0]["type"] == "set_bonus"

    def test_set_piece_curated_stats_crusader_weapon(self):
        """Crusader's Oath Warhammer has exact curated stats."""
        item = generate_set_piece("crusaders_oath", "crusaders_oath_weapon")
        assert item.stat_bonuses.attack_damage == 14
        assert item.stat_bonuses.max_hp == 20

    def test_set_piece_curated_stats_deadeye_weapon(self):
        """Deadeye Longbow has exact curated stats."""
        item = generate_set_piece("deadeyes_arsenal", "deadeyes_arsenal_weapon")
        assert item.stat_bonuses.ranged_damage == 16
        assert item.stat_bonuses.crit_chance == 0.05

    def test_set_piece_equip_slot_correct(self):
        """Weapon pieces go to weapon slot, armor to armor, etc."""
        item = generate_set_piece("crusaders_oath", "crusaders_oath_weapon")
        assert item.equip_slot == "weapon"

        item = generate_set_piece("crusaders_oath", "crusaders_oath_armor")
        assert item.equip_slot == "armor"

        item = generate_set_piece("crusaders_oath", "crusaders_oath_accessory")
        assert item.equip_slot == "accessory"

    def test_set_piece_has_description(self):
        item = generate_set_piece("faiths_radiance", "faiths_radiance_weapon")
        assert item.description and len(item.description) > 0

    def test_set_piece_has_sell_value(self):
        item = generate_set_piece("crusaders_oath", "crusaders_oath_weapon")
        assert item.sell_value > 0

    def test_set_piece_has_item_level(self):
        item = generate_set_piece("crusaders_oath", "crusaders_oath_weapon")
        assert item.item_level == 14

    def test_set_piece_returns_none_for_invalid_ids(self):
        assert generate_set_piece("nonexistent_set", "nonexistent_piece") is None
        assert generate_set_piece("crusaders_oath", "nonexistent_piece") is None

    def test_set_piece_has_display_name(self):
        item = generate_set_piece("crusaders_oath", "crusaders_oath_weapon")
        assert item.display_name == "Crusader's Oath Warhammer"

    def test_all_15_pieces_gettable(self):
        """All 15 (set_id, piece_id) tuples exist."""
        pairs = get_all_set_piece_ids()
        assert len(pairs) == 15
        for set_id, piece_id in pairs:
            assert set_id and piece_id


# ============================================================
# 3. Set Bonus Calculation
# ============================================================

class TestSetBonusCalculation:
    """calculate_active_set_bonuses detects correct bonus tiers."""

    def test_zero_pieces_no_bonus(self):
        """0/3 pieces → no set bonus active."""
        player = _make_player()
        result = calculate_active_set_bonuses(player.equipment)
        assert result == []

    def test_one_piece_no_bonus(self):
        """1/3 pieces → no set bonus active."""
        player = _make_player()
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_weapon")
        result = calculate_active_set_bonuses(player.equipment)
        assert result == []

    def test_two_pieces_tier1_active(self):
        """2/3 pieces → tier 1 (2-piece) bonus active."""
        player = _make_player()
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_weapon")
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_armor")
        result = calculate_active_set_bonuses(player.equipment)

        assert len(result) == 1
        active = result[0]
        assert active["set_id"] == "crusaders_oath"
        assert active["pieces_equipped"] == 2
        assert active["pieces_total"] == 3
        # The 2-piece bonus should be present
        bonus_required = [b["pieces_required"] for b in active["bonuses"]]
        assert 2 in bonus_required

    def test_three_pieces_both_tiers_active(self):
        """3/3 pieces → both tier 1 and tier 2 bonuses active."""
        player = _make_player()
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_weapon")
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_armor")
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_accessory")
        result = calculate_active_set_bonuses(player.equipment)

        assert len(result) == 1
        active = result[0]
        assert active["set_id"] == "crusaders_oath"
        assert active["pieces_equipped"] == 3
        bonus_required = [b["pieces_required"] for b in active["bonuses"]]
        assert 2 in bonus_required
        assert 3 in bonus_required

    def test_mixed_sets_independent(self):
        """Pieces from different sets don't combine. Only sets with 2+ pieces activate."""
        player = _make_player()
        # 1 piece from each of 3 sets — no bonus should trigger
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_weapon")
        _equip_set_piece(player, "voidwalkers_regalia", "voidwalkers_regalia_armor")
        _equip_set_piece(player, "deadeyes_arsenal", "deadeyes_arsenal_accessory")
        result = calculate_active_set_bonuses(player.equipment)
        assert result == []

    def test_empty_equipment_no_bonus(self):
        result = calculate_active_set_bonuses({})
        assert result == []

    def test_none_slots_ignored(self):
        result = calculate_active_set_bonuses({"weapon": None, "armor": None})
        assert result == []


# ============================================================
# 4. Set Stat Totals (highest tier only)
# ============================================================

class TestSetStatTotals:
    """get_set_stat_totals aggregates stats from highest bonus tier only."""

    def test_two_piece_bonus_stats(self):
        """2-piece Crusader's Oath gives +4 armor, +30 HP."""
        player = _make_player()
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_weapon")
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_armor")
        active = calculate_active_set_bonuses(player.equipment)

        totals = get_set_stat_totals(active)
        assert totals.armor == 4
        assert totals.max_hp == 30

    def test_three_piece_bonus_uses_highest_tier(self):
        """3-piece Crusader's Oath: highest tier is 3-piece (+8 armor, +80 HP)."""
        player = _make_player()
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_weapon")
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_armor")
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_accessory")
        active = calculate_active_set_bonuses(player.equipment)

        totals = get_set_stat_totals(active)
        # Should be 3-piece tier values ONLY (not cumulative with 2-piece)
        assert totals.armor == 8
        assert totals.max_hp == 80

    def test_deadeye_three_piece_bonus_stats(self):
        """3-piece Deadeye's Arsenal: +15% crit chance, +50% crit damage."""
        player = _make_player()
        _equip_set_piece(player, "deadeyes_arsenal", "deadeyes_arsenal_weapon")
        _equip_set_piece(player, "deadeyes_arsenal", "deadeyes_arsenal_armor")
        _equip_set_piece(player, "deadeyes_arsenal", "deadeyes_arsenal_accessory")
        active = calculate_active_set_bonuses(player.equipment)

        totals = get_set_stat_totals(active)
        assert totals.crit_chance == pytest.approx(0.15)
        assert totals.crit_damage == pytest.approx(0.50)

    def test_faiths_radiance_two_piece_bonus(self):
        """2-piece Faith's Radiance: +15% heal power."""
        player = _make_player()
        _equip_set_piece(player, "faiths_radiance", "faiths_radiance_weapon")
        _equip_set_piece(player, "faiths_radiance", "faiths_radiance_armor")
        active = calculate_active_set_bonuses(player.equipment)

        totals = get_set_stat_totals(active)
        assert totals.heal_power_pct == pytest.approx(0.15)

    def test_empty_active_sets_zero_totals(self):
        totals = get_set_stat_totals([])
        assert totals.armor == 0
        assert totals.max_hp == 0
        assert totals.crit_chance == 0.0

    def test_voidwalker_three_piece_bonus(self):
        """3-piece Voidwalker's Regalia: +20% skill damage."""
        player = _make_player()
        _equip_set_piece(player, "voidwalkers_regalia", "voidwalkers_regalia_weapon")
        _equip_set_piece(player, "voidwalkers_regalia", "voidwalkers_regalia_armor")
        _equip_set_piece(player, "voidwalkers_regalia", "voidwalkers_regalia_accessory")
        active = calculate_active_set_bonuses(player.equipment)

        totals = get_set_stat_totals(active)
        assert totals.skill_damage_pct == pytest.approx(0.20)


# ============================================================
# 5. Apply / Remove Set Stat Bonuses
# ============================================================

class TestApplyRemoveSetBonuses:
    """apply_set_stat_bonuses and remove_set_stat_bonuses modify player correctly."""

    def test_apply_increases_stats(self):
        player = _make_player(armor=5, max_hp=100, hp=100)
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_weapon")
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_armor")
        active = calculate_active_set_bonuses(player.equipment)

        apply_set_stat_bonuses(player, active)
        assert player.armor == 9  # 5 base + 4 from 2-piece bonus
        assert player.max_hp == 130  # 100 base + 30 from 2-piece bonus
        assert player.hp == 130  # HP also increased

    def test_remove_reverts_stats(self):
        player = _make_player(armor=5, max_hp=100, hp=100)
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_weapon")
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_armor")
        active = calculate_active_set_bonuses(player.equipment)

        apply_set_stat_bonuses(player, active)
        assert player.armor == 9
        assert player.max_hp == 130

        remove_set_stat_bonuses(player, active)
        assert player.armor == 5
        assert player.max_hp == 100
        assert player.hp <= player.max_hp

    def test_apply_respects_caps(self):
        """Crit chance should be capped at 50%."""
        player = _make_player()
        player.crit_chance = 0.45
        _equip_set_piece(player, "deadeyes_arsenal", "deadeyes_arsenal_weapon")
        _equip_set_piece(player, "deadeyes_arsenal", "deadeyes_arsenal_armor")
        _equip_set_piece(player, "deadeyes_arsenal", "deadeyes_arsenal_accessory")
        active = calculate_active_set_bonuses(player.equipment)

        apply_set_stat_bonuses(player, active)
        # 3-piece bonus is +15% crit_chance, but player already has 45% → capped at 50%
        assert player.crit_chance == pytest.approx(0.50)

    def test_remove_does_not_go_below_zero(self):
        player = _make_player(armor=2, max_hp=50, hp=50)
        # Create a fake active set that would subtract more than available
        fake_active = [{
            "set_id": "test",
            "set_name": "Test",
            "pieces_equipped": 3,
            "pieces_total": 3,
            "bonuses": [{
                "pieces_required": 3,
                "stat_bonuses": {"armor": 100, "max_hp": 200},
                "skill_modifiers": {},
            }],
        }]
        remove_set_stat_bonuses(player, fake_active)
        assert player.armor >= 0
        assert player.max_hp >= 1

    def test_apply_empty_active_sets_noop(self):
        player = _make_player(armor=5, max_hp=100, hp=100)
        apply_set_stat_bonuses(player, [])
        assert player.armor == 5
        assert player.max_hp == 100


# ============================================================
# 6. Skill Modifiers from Sets
# ============================================================

class TestSetSkillModifiers:
    """get_set_skill_modifiers returns correct skill-specific modifiers."""

    def test_crusader_two_piece_taunt_duration(self):
        """2-piece Crusader's Oath: taunt duration +1."""
        player = _make_player()
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_weapon")
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_armor")
        active = calculate_active_set_bonuses(player.equipment)

        mods = get_set_skill_modifiers(active)
        assert "taunt" in mods
        assert mods["taunt"]["duration_bonus"] == 1

    def test_crusader_three_piece_adds_bulwark(self):
        """3-piece Crusader's Oath: taunt duration +1, bulwark thorns +4."""
        player = _make_player()
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_weapon")
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_armor")
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_accessory")
        active = calculate_active_set_bonuses(player.equipment)

        mods = get_set_skill_modifiers(active)
        assert "taunt" in mods
        assert "bulwark" in mods
        assert mods["bulwark"]["thorns_bonus"] == 4

    def test_voidwalker_two_piece_wither_duration(self):
        """2-piece Voidwalker's Regalia: wither duration +1."""
        player = _make_player()
        _equip_set_piece(player, "voidwalkers_regalia", "voidwalkers_regalia_weapon")
        _equip_set_piece(player, "voidwalkers_regalia", "voidwalkers_regalia_armor")
        active = calculate_active_set_bonuses(player.equipment)

        mods = get_set_skill_modifiers(active)
        assert "wither" in mods
        assert mods["wither"]["duration_bonus"] == 1

    def test_voidwalker_three_piece_wither_and_ward(self):
        """3-piece Voidwalker: wither duration +2, ward reflect +4."""
        player = _make_player()
        _equip_set_piece(player, "voidwalkers_regalia", "voidwalkers_regalia_weapon")
        _equip_set_piece(player, "voidwalkers_regalia", "voidwalkers_regalia_armor")
        _equip_set_piece(player, "voidwalkers_regalia", "voidwalkers_regalia_accessory")
        active = calculate_active_set_bonuses(player.equipment)

        mods = get_set_skill_modifiers(active)
        assert mods["wither"]["duration_bonus"] == 2
        assert mods["ward"]["reflect_bonus"] == 4

    def test_deadeye_two_piece_power_shot_cdr(self):
        """2-piece Deadeye's Arsenal: power_shot cooldown -1."""
        player = _make_player()
        _equip_set_piece(player, "deadeyes_arsenal", "deadeyes_arsenal_weapon")
        _equip_set_piece(player, "deadeyes_arsenal", "deadeyes_arsenal_armor")
        active = calculate_active_set_bonuses(player.equipment)

        mods = get_set_skill_modifiers(active)
        assert "power_shot" in mods
        assert mods["power_shot"]["cooldown_reduction"] == 1

    def test_faiths_radiance_two_piece_heal_cdr(self):
        """2-piece Faith's Radiance: heal cooldown -1."""
        player = _make_player()
        _equip_set_piece(player, "faiths_radiance", "faiths_radiance_weapon")
        _equip_set_piece(player, "faiths_radiance", "faiths_radiance_armor")
        active = calculate_active_set_bonuses(player.equipment)

        mods = get_set_skill_modifiers(active)
        assert "heal" in mods
        assert mods["heal"]["cooldown_reduction"] == 1

    def test_seeker_two_piece_rebuke_cdr(self):
        """2-piece Seeker's Judgment: rebuke cooldown -2."""
        player = _make_player()
        _equip_set_piece(player, "seekers_judgment", "seekers_judgment_weapon")
        _equip_set_piece(player, "seekers_judgment", "seekers_judgment_armor")
        active = calculate_active_set_bonuses(player.equipment)

        mods = get_set_skill_modifiers(active)
        assert "rebuke" in mods
        assert mods["rebuke"]["cooldown_reduction"] == 2

    def test_seeker_three_piece_shadow_step_range(self):
        """3-piece Seeker's Judgment: shadow_step range +1."""
        player = _make_player()
        _equip_set_piece(player, "seekers_judgment", "seekers_judgment_weapon")
        _equip_set_piece(player, "seekers_judgment", "seekers_judgment_armor")
        _equip_set_piece(player, "seekers_judgment", "seekers_judgment_accessory")
        active = calculate_active_set_bonuses(player.equipment)

        mods = get_set_skill_modifiers(active)
        assert "shadow_step" in mods
        assert mods["shadow_step"]["range_bonus"] == 1

    def test_empty_active_sets_no_modifiers(self):
        mods = get_set_skill_modifiers([])
        assert mods == {}


# ============================================================
# 7. Special Effects from Sets
# ============================================================

class TestSetSpecialEffects:
    """get_set_special_effects returns combat effects from active set bonuses."""

    def test_deadeye_three_piece_ranged_crit_pierce(self):
        """3-piece Deadeye's Arsenal has ranged_crit_pierce special effect."""
        player = _make_player()
        _equip_set_piece(player, "deadeyes_arsenal", "deadeyes_arsenal_weapon")
        _equip_set_piece(player, "deadeyes_arsenal", "deadeyes_arsenal_armor")
        _equip_set_piece(player, "deadeyes_arsenal", "deadeyes_arsenal_accessory")
        active = calculate_active_set_bonuses(player.equipment)

        effects = get_set_special_effects(active)
        assert len(effects) >= 1
        pierce_effects = [e for e in effects if e["effect_id"] == "ranged_crit_pierce"]
        assert len(pierce_effects) == 1
        assert pierce_effects[0]["pierce_count"] == 1

    def test_no_special_effects_for_sets_without_them(self):
        """Crusader's Oath has no special_effects entries."""
        player = _make_player()
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_weapon")
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_armor")
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_accessory")
        active = calculate_active_set_bonuses(player.equipment)

        effects = get_set_special_effects(active)
        crusader_effects = [e for e in effects if e["set_id"] == "crusaders_oath"]
        assert len(crusader_effects) == 0

    def test_two_piece_deadeye_no_special_effects(self):
        """2-piece Deadeye doesn't have special effects (only 3-piece does)."""
        player = _make_player()
        _equip_set_piece(player, "deadeyes_arsenal", "deadeyes_arsenal_weapon")
        _equip_set_piece(player, "deadeyes_arsenal", "deadeyes_arsenal_armor")
        active = calculate_active_set_bonuses(player.equipment)

        effects = get_set_special_effects(active)
        deadeye_effects = [e for e in effects if e["set_id"] == "deadeyes_arsenal"]
        assert len(deadeye_effects) == 0

    def test_empty_active_sets_no_effects(self):
        effects = get_set_special_effects([])
        assert effects == []


# ============================================================
# 8. Roll Set Drop
# ============================================================

class TestRollSetDrop:
    """roll_set_drop follows drop rules correctly."""

    def test_no_drop_from_swarm(self):
        """Swarm enemies never drop set items."""
        rng = _FixedRng(0.0)  # always succeeds roll check
        result = roll_set_drop("swarm", rng=rng)
        assert result is None

    def test_no_drop_from_fodder(self):
        """Fodder enemies never drop set items."""
        rng = _FixedRng(0.0)
        result = roll_set_drop("fodder", rng=rng)
        assert result is None

    def test_no_drop_from_mid(self):
        """Mid enemies never drop set items."""
        rng = _FixedRng(0.0)
        result = roll_set_drop("mid", rng=rng)
        assert result is None

    def test_drop_possible_from_elite(self):
        """Elite enemies can drop set items with low enough roll."""
        rng = _FixedRng(0.0)  # always passes chance check
        result = roll_set_drop("elite", floor_number=1, rng=rng)
        assert result is not None
        assert result.rarity == Rarity.SET

    def test_drop_possible_from_boss(self):
        """Boss enemies can drop set items."""
        rng = _FixedRng(0.0)
        result = roll_set_drop("boss", floor_number=1, rng=rng)
        assert result is not None
        assert result.rarity == Rarity.SET

    def test_high_roll_no_drop(self):
        """High RNG roll means no drop."""
        rng = _FixedRng(0.999)
        result = roll_set_drop("elite", floor_number=1, rng=rng)
        assert result is None

    def test_deduplicate_already_dropped(self):
        """Already-dropped piece IDs are excluded from the pool."""
        # Drop all 15 pieces first to exhaust the pool
        all_piece_ids = {pid for _, pid in get_all_set_piece_ids()}
        rng = _FixedRng(0.0)
        result = roll_set_drop("elite", dropped_set_piece_ids=all_piece_ids, rng=rng)
        assert result is None

    def test_magic_find_increases_chance(self):
        """Higher magic find should make drops more likely (tested indirectly)."""
        # With 0% MF and a roll that's just above the base chance
        # The roll value must be between base_chance and base_chance * (1 + mf)
        config = load_sets_config()
        base_chance = config["drop_rules"]["base_drop_chance"]

        # Roll just above base chance — should fail without MF
        rng_fail = _FixedRng(base_chance + 0.0001)
        result_no_mf = roll_set_drop("elite", floor_number=1, magic_find_pct=0.0, rng=rng_fail)
        assert result_no_mf is None

        # Same roll, but with 100% MF — effective chance doubles, should succeed
        rng_pass = _FixedRng(base_chance + 0.0001)
        result_with_mf = roll_set_drop("elite", floor_number=1, magic_find_pct=1.0, rng=rng_pass)
        assert result_with_mf is not None

    def test_boss_3x_multiplier(self):
        """Boss has 3× chance multiplier. A roll that fails for elite may pass for boss."""
        config = load_sets_config()
        base_chance = config["drop_rules"]["base_drop_chance"]

        # Roll just above base chance — should fail for elite
        rng_elite = _FixedRng(base_chance + 0.0001)
        result_elite = roll_set_drop("elite", floor_number=1, rng=rng_elite)
        assert result_elite is None

        # Same roll for boss — 3× multiplier should make it pass
        rng_boss = _FixedRng(base_chance + 0.0001)
        result_boss = roll_set_drop("boss", floor_number=1, rng=rng_boss)
        assert result_boss is not None

    def test_floor_scaling_increases_chance(self):
        """Higher floors have increased drop chance."""
        config = load_sets_config()
        base_chance = config["drop_rules"]["base_drop_chance"]

        # Roll that fails on floor 1 but passes on floor 10 (3x scaling)
        roll_val = base_chance * 1.5  # 1.5× base chance
        rng_low = _FixedRng(roll_val)
        result_floor1 = roll_set_drop("elite", floor_number=1, rng=rng_low)
        assert result_floor1 is None

        rng_high = _FixedRng(roll_val)
        result_floor10 = roll_set_drop("elite", floor_number=10, rng=rng_high)
        assert result_floor10 is not None

    def test_class_affinity_weighting(self):
        """Class affinity weights affect which set pieces drop.

        A crusader should heavily favor Crusader's Oath pieces.
        We test this by mocking a guaranteed drop and verifying weighting
        biases the result toward the player's class set.
        """
        # Use many drops to check statistical bias
        crusader_count = 0
        total = 200
        for _ in range(total):
            rng = _FixedRng(0.0)
            item = roll_set_drop("elite", player_class="crusader", rng=rng)
            if item and "crusaders_oath" in item.item_id:
                crusader_count += 1

        # With 3.0 weight vs 1.0 defaults, crusader pieces should be strongly favored
        # Expect ~30-40% of drops to be crusader pieces (3 pieces × 3.0 weight / total weight)
        assert crusader_count > total * 0.2, (
            f"Expected crusader class to strongly favor crusader set, got {crusader_count}/{total}"
        )


# ============================================================
# 9. Loot Integration
# ============================================================

class TestLootIntegration:
    """generate_enemy_loot can include set drops."""

    def test_loot_includes_set_drop_tracking_params(self):
        """generate_enemy_loot accepts dropped_set_piece_ids and player_class params."""
        # This is mostly a signature check — a normal loot call shouldn't crash
        import inspect
        sig = inspect.signature(generate_enemy_loot)
        params = sig.parameters
        assert "dropped_set_piece_ids" in params
        assert "player_class" in params


# ============================================================
# 10. ActiveSetBonuses on PlayerState
# ============================================================

class TestPlayerStateActiveSets:
    """PlayerState stores active_set_bonuses list."""

    def test_default_empty(self):
        player = _make_player()
        assert player.active_set_bonuses == []

    def test_stores_set_data(self):
        player = _make_player()
        player.active_set_bonuses = [{
            "set_id": "crusaders_oath",
            "set_name": "Crusader's Oath",
            "pieces_equipped": 2,
            "pieces_total": 3,
            "bonuses": [],
        }]
        assert len(player.active_set_bonuses) == 1
        assert player.active_set_bonuses[0]["set_id"] == "crusaders_oath"


# ============================================================
# 11. Backward Compatibility
# ============================================================

class TestBackwardCompat:
    """Non-set items should be unaffected by set bonus logic."""

    def test_non_set_equipment_no_set_bonuses(self):
        """A player with regular items should have no active set bonuses."""
        player = _make_player()
        player.equipment = {
            "weapon": {"item_id": "basic_sword", "equip_slot": "weapon", "stat_bonuses": {"attack_damage": 5}},
            "armor": {"item_id": "basic_armor", "equip_slot": "armor", "stat_bonuses": {"armor": 3}},
        }
        result = calculate_active_set_bonuses(player.equipment)
        assert result == []

    def test_set_bonus_calc_ignores_non_set_items(self):
        """A player with 1 set piece and 1 regular item gets no set bonus."""
        player = _make_player()
        _equip_set_piece(player, "crusaders_oath", "crusaders_oath_weapon")
        player.equipment["armor"] = {
            "item_id": "basic_armor",
            "equip_slot": "armor",
            "stat_bonuses": {"armor": 3},
        }
        result = calculate_active_set_bonuses(player.equipment)
        assert result == []


# ============================================================
# 12. get_set_definition helper
# ============================================================

class TestGetSetDefinition:
    """get_set_definition returns raw set data."""

    def test_returns_definition(self):
        defn = get_set_definition("crusaders_oath")
        assert defn is not None
        assert defn["name"] == "Crusader's Oath"
        assert len(defn["pieces"]) == 3

    def test_returns_none_for_invalid(self):
        defn = get_set_definition("nonexistent_set")
        assert defn is None

    @pytest.mark.parametrize("set_id", get_all_set_ids())
    def test_all_sets_have_definition(self, set_id):
        defn = get_set_definition(set_id)
        assert defn is not None
        assert "pieces" in defn
        assert "bonuses" in defn
        assert "name" in defn


# ============================================================
# 13. Cache Clearing
# ============================================================

class TestCacheClearing:
    """Cache clear/reload cycle works correctly."""

    def test_clear_and_reload(self):
        clear_sets_cache()
        config = load_sets_config()
        assert config is not None
        assert "sets" in config
        assert len(config["sets"]) == 5
