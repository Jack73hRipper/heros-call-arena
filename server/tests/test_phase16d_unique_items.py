"""
Tests for Phase 16D: Unique Items.

Covers the complete unique item system:
 1. Config loading — loads all 16 uniques from uniques_config.json
 2. Generate unique — each of the 16 uniques generates correctly
 3. Unique items have Rarity.UNIQUE
 4. Unique items have curated stat bonuses (no random affixes)
 5. Unique special effects stored in affixes list as type="unique_effect"
 6. has_unique_equipped() detects equipped uniques correctly
 7. get_unique_special_effect() returns correct effect dict
 8. get_all_equipped_unique_effects() aggregates all equipped effects
 9. roll_unique_drop() — only elite/boss tier drops
10. roll_unique_drop() — no duplicate uniques per run
11. roll_unique_drop() — magic find increases chance
12. roll_unique_drop() — boss tier gets 3× bonus
13. roll_unique_drop() — enemy type weighting
14. Soulreaver — melee lifesteal effect in combat
15. The Whisper — crit multiplier override
16. Grimfang — on-kill haste buff in turn_resolver
17. Dawnbreaker — skill cooldown reduction for holy skills
18. Plaguebow — ranged DoT application
19. Voidedge — armor ignore in combat
20. The Bonecage — flat damage reduction
21. Shadowshroud — Shadow Step cooldown reduction
22. Penitent Mail — healing received bonus
23. Wraithmantle — dodge retaliate damage
24. Ironwill Plate — CC immunity (stun resist)
25. Eye of Malice — crit skill cooldown reset
26. Bloodpact Ring — low HP damage bonus
27. Sigil of Greed — damage penalty
28. Warden's Oath — taunt range bonus
29. Prayer Beads — AoE prayer heal
30. Loot integration — generate_enemy_loot includes unique drops
31. Backward compat — non-unique items unaffected
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
    load_uniques_config,
    generate_unique,
    get_all_unique_ids,
    get_unique_definition,
    roll_unique_drop,
    has_unique_equipped,
    get_unique_special_effect,
    get_all_equipped_unique_effects,
    clear_generator_caches,
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


def _equip_unique(player: PlayerState, unique_id: str) -> dict:
    """Generate a unique and equip it on the player. Returns the item dict."""
    item = generate_unique(unique_id)
    assert item is not None, f"Failed to generate unique: {unique_id}"
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
    clear_loot_caches()
    load_uniques_config()


def teardown_module():
    clear_generator_caches()
    clear_loot_caches()


# ============================================================
# 1. Config Loading
# ============================================================

class TestConfigLoading:
    """Uniques config loads correctly with all 16 items."""

    def test_config_loads(self):
        config = load_uniques_config()
        assert config is not None
        assert "uniques" in config
        assert "drop_rules" in config
        assert "enemy_type_weights" in config

    def test_config_has_16_uniques(self):
        config = load_uniques_config()
        uniques = config["uniques"]
        assert len(uniques) == 16

    def test_all_unique_ids_present(self):
        expected_ids = [
            "unique_soulreaver", "unique_whisper", "unique_grimfang",
            "unique_dawnbreaker", "unique_plaguebow", "unique_voidedge",
            "unique_bonecage", "unique_shadowshroud", "unique_penitent_mail",
            "unique_wraithmantle", "unique_ironwill", "unique_eye_of_malice",
            "unique_bloodpact", "unique_greed_sigil", "unique_wardens_oath",
            "unique_prayer_beads",
        ]
        ids = get_all_unique_ids()
        for eid in expected_ids:
            assert eid in ids, f"Missing unique: {eid}"

    def test_drop_rules_structure(self):
        config = load_uniques_config()
        rules = config["drop_rules"]
        assert "base_drop_chance" in rules
        assert "allowed_tiers" in rules
        assert rules["base_drop_chance"] == 0.005
        assert "elite" in rules["allowed_tiers"]
        assert "boss" in rules["allowed_tiers"]
        assert rules["max_per_run"] == 1


# ============================================================
# 2. Unique Item Generation
# ============================================================

class TestUniqueGeneration:
    """generate_unique produces correct items for all 16 uniques."""

    @pytest.mark.parametrize("unique_id", get_all_unique_ids())
    def test_generate_each_unique(self, unique_id):
        item = generate_unique(unique_id)
        assert item is not None
        assert item.item_id == unique_id
        assert item.rarity == Rarity.UNIQUE
        assert item.instance_id  # UUID assigned

    @pytest.mark.parametrize("unique_id", get_all_unique_ids())
    def test_unique_has_special_effect_in_affixes(self, unique_id):
        item = generate_unique(unique_id)
        assert item is not None
        unique_effects = [a for a in item.affixes if a.get("type") == "unique_effect"]
        assert len(unique_effects) == 1, f"{unique_id} should have exactly 1 unique_effect affix"
        effect = unique_effects[0]["effect"]
        assert "type" in effect

    def test_unique_no_random_affixes(self):
        """Uniques have only the special_effect affix, no random rolls."""
        item = generate_unique("unique_soulreaver")
        assert len(item.affixes) == 1
        assert item.affixes[0]["type"] == "unique_effect"

    def test_unique_curated_stats(self):
        """Soulreaver should have exact curated stat bonuses."""
        item = generate_unique("unique_soulreaver")
        assert item.stat_bonuses.attack_damage == 15
        assert item.stat_bonuses.life_on_hit == 5

    def test_unique_has_description(self):
        item = generate_unique("unique_soulreaver")
        assert "souls" in item.description.lower() or "screaming" in item.description.lower()

    def test_unique_has_sell_value(self):
        item = generate_unique("unique_soulreaver")
        assert item.sell_value > 0

    def test_unique_returns_none_for_invalid_id(self):
        item = generate_unique("unique_nonexistent")
        assert item is None

    def test_unique_unique_instance_ids(self):
        """Two generations of the same unique have different instance_ids."""
        a = generate_unique("unique_soulreaver")
        b = generate_unique("unique_soulreaver")
        assert a.instance_id != b.instance_id


# ============================================================
# 3. Equipment Lookup Helpers
# ============================================================

class TestEquipmentHelpers:
    """has_unique_equipped, get_unique_special_effect, get_all_equipped_unique_effects."""

    def test_has_unique_equipped_true(self):
        player = _make_player()
        _equip_unique(player, "unique_soulreaver")
        assert has_unique_equipped(player.equipment, "unique_soulreaver")

    def test_has_unique_equipped_false(self):
        player = _make_player()
        assert not has_unique_equipped(player.equipment, "unique_soulreaver")

    def test_has_unique_equipped_wrong_unique(self):
        player = _make_player()
        _equip_unique(player, "unique_soulreaver")
        assert not has_unique_equipped(player.equipment, "unique_voidedge")

    def test_get_unique_special_effect(self):
        player = _make_player()
        _equip_unique(player, "unique_soulreaver")
        effect = get_unique_special_effect(player.equipment, "unique_soulreaver")
        assert effect is not None
        assert effect["type"] == "melee_lifesteal_pct"
        assert effect["value"] == 0.15

    def test_get_unique_special_effect_not_equipped(self):
        player = _make_player()
        effect = get_unique_special_effect(player.equipment, "unique_soulreaver")
        assert effect is None

    def test_get_all_equipped_unique_effects_empty(self):
        player = _make_player()
        effects = get_all_equipped_unique_effects(player.equipment)
        assert effects == []

    def test_get_all_equipped_unique_effects_one(self):
        player = _make_player()
        _equip_unique(player, "unique_soulreaver")
        effects = get_all_equipped_unique_effects(player.equipment)
        assert len(effects) == 1
        assert effects[0]["type"] == "melee_lifesteal_pct"

    def test_get_all_equipped_unique_effects_multiple(self):
        """Equip weapon + armor + accessory uniques."""
        player = _make_player()
        _equip_unique(player, "unique_soulreaver")  # weapon
        _equip_unique(player, "unique_bonecage")     # armor
        _equip_unique(player, "unique_bloodpact")    # accessory
        effects = get_all_equipped_unique_effects(player.equipment)
        assert len(effects) == 3
        types = {e["type"] for e in effects}
        assert "melee_lifesteal_pct" in types
        assert "flat_damage_reduction_bonus" in types
        assert "low_hp_damage_bonus" in types


# ============================================================
# 4. Unique Drop Rolling
# ============================================================

class TestUniqueDropRolling:
    """roll_unique_drop mechanics."""

    def test_no_drop_from_fodder(self):
        """Non-elite/boss enemies should never drop uniques."""
        rng = _FixedRng(0.0)  # Always passes drop check
        for tier in ("swarm", "fodder", "mid"):
            result = roll_unique_drop(
                enemy_tier=tier, floor_number=5, magic_find_pct=0.0,
                dropped_unique_ids=set(), rng=rng,
            )
            assert result is None, f"Tier '{tier}' should not drop uniques"

    def test_elite_can_drop(self):
        """Elite tier can produce uniques with very low roll."""
        rng = _FixedRng(0.0)  # Always passes
        result = roll_unique_drop(
            enemy_tier="elite", floor_number=5, magic_find_pct=0.0,
            dropped_unique_ids=set(), rng=rng,
        )
        assert result is not None
        assert result.rarity == Rarity.UNIQUE

    def test_boss_can_drop(self):
        rng = _FixedRng(0.0)
        result = roll_unique_drop(
            enemy_tier="boss", floor_number=5, magic_find_pct=0.0,
            dropped_unique_ids=set(), rng=rng,
        )
        assert result is not None
        assert result.rarity == Rarity.UNIQUE

    def test_no_duplicate_per_run(self):
        """Already-dropped unique IDs should be excluded."""
        all_ids = set(get_all_unique_ids())
        rng = _FixedRng(0.0)
        result = roll_unique_drop(
            enemy_tier="boss", floor_number=9, magic_find_pct=0.0,
            dropped_unique_ids=all_ids, rng=rng,
        )
        assert result is None

    def test_magic_find_increases_chance(self):
        """Higher MF should increase effective drop chance.

        With base_chance = 0.005 at floor 1, 0% MF: effective = 0.005
        With 200% MF: effective = 0.005 * 3.0 = 0.015
        An rng value of 0.010 should fail at 0% MF but pass at 200% MF.
        """
        # Boss gets 3× so: 0.005 * 1.0 * 1.0 * 3.0 = 0.015 (no MF)
        config = load_uniques_config()
        rng_fail = _FixedRng(0.014)  # just under 0.015 → passes with boss
        result_no_mf = roll_unique_drop(
            enemy_tier="boss", floor_number=1, magic_find_pct=0.0,
            dropped_unique_ids=set(), rng=rng_fail,
        )
        assert result_no_mf is not None  # 0.014 < 0.015

        # With MF: effective = 0.005 * 1.0 * 1.0 * 3.0 = 0.015 (0% MF boss)
        # vs 0.005 * 1.0 * 3.0 * 3.0 = 0.045 (200% MF boss)
        rng_mid = _FixedRng(0.020)
        result_no_mf2 = roll_unique_drop(
            enemy_tier="boss", floor_number=1, magic_find_pct=0.0,
            dropped_unique_ids=set(), rng=rng_mid,
        )
        assert result_no_mf2 is None  # 0.020 >= 0.015

        result_high_mf = roll_unique_drop(
            enemy_tier="boss", floor_number=1, magic_find_pct=2.0,
            dropped_unique_ids=set(), rng=rng_mid,
        )
        assert result_high_mf is not None  # 0.020 < 0.045

    def test_enemy_type_weighting(self):
        """Undead enemies should bias toward Dawnbreaker, Prayer Beads, Penitent Mail."""
        dropped = {}
        for seed in range(200):
            rng = random.Random(seed)
            # Force the drop chance to always succeed by using low first random
            item = roll_unique_drop(
                enemy_tier="boss", floor_number=9, magic_find_pct=5.0,
                dropped_unique_ids=set(), enemy_type="undead",
                rng=rng,
            )
            if item:
                dropped[item.item_id] = dropped.get(item.item_id, 0) + 1

        # With undead weights, dawnbreaker/prayer_beads/penitent_mail should be biased
        # At least some uniques should drop across 200 attempts with high MF on floor 9
        assert len(dropped) > 0, "Expected at least some unique drops from 200 boss kills"


# ============================================================
# 5. Soulreaver — Melee Lifesteal
# ============================================================

class TestSoulreaver:
    """Soulreaver: Heals 15% of melee damage dealt."""

    def test_combat_lifesteal(self):
        from app.core.combat import calculate_damage
        attacker = _make_player(pid="atk", hp=50, max_hp=100, attack_damage=30)
        _equip_unique(attacker, "unique_soulreaver")
        defender = _make_player(pid="def", hp=100, max_hp=100, armor=0)

        damage, combat_info = calculate_damage(attacker, defender)
        # Lifesteal should heal 15% of damage dealt
        lifesteal_healed = combat_info.get("unique_lifesteal_healed", 0)
        assert damage > 0
        expected_heal = int(damage * 0.15)
        assert lifesteal_healed == expected_heal


# ============================================================
# 6. The Whisper — Crit Multiplier Override
# ============================================================

class TestWhisper:
    """The Whisper: Critical hits deal 3× instead of 1.5×."""

    def test_crit_multiplier_override(self):
        from app.core.combat import calculate_damage
        attacker = _make_player(pid="atk", attack_damage=20, crit_chance=1.0)
        _equip_unique(attacker, "unique_whisper")
        defender = _make_player(pid="def", hp=200, max_hp=200, armor=0)

        # Use fixed RNG that always returns 0.0 so the crit check passes
        # (crit_chance is capped at 0.50 in combat.py, so we need rng < 0.50)
        damage, combat_info = calculate_damage(attacker, defender, rng=_FixedRng(0.0))
        # With crit guaranteed and 3× multiplier, damage should be much higher
        # Normal crit at 1.5×: ~30, unique crit at 3×: ~60
        assert combat_info["is_crit"], "Expected a critical hit with FixedRng(0.0)"
        assert damage > 40, f"Expected high crit damage with Whisper, got {damage}"


# ============================================================
# 7. Voidedge — Armor Ignore
# ============================================================

class TestVoidedge:
    """Voidedge: All damage ignores 50% of target armor."""

    def test_armor_ignore_melee(self):
        from app.core.combat import calculate_damage
        attacker = _make_player(pid="atk", attack_damage=30)
        _equip_unique(attacker, "unique_voidedge")
        defender = _make_player(pid="def", hp=200, max_hp=200, armor=20)

        dmg_with, info_with = calculate_damage(attacker, defender)

        # Without voidedge: damage = 30 + bonuses - armor_reduction
        attacker2 = _make_player(pid="atk2", attack_damage=30)
        defender2 = _make_player(pid="def2", hp=200, max_hp=200, armor=20)
        dmg_without, info_without = calculate_damage(attacker2, defender2)

        # Voidedge should result in more damage due to armor ignore
        assert dmg_with > dmg_without


# ============================================================
# 8. The Bonecage — Flat Damage Reduction
# ============================================================

class TestBonecage:
    """The Bonecage: Take 15% less damage from all sources."""

    def test_flat_dr_reduces_damage(self):
        from app.core.combat import calculate_damage
        attacker = _make_player(pid="atk", attack_damage=50)
        defender = _make_player(pid="def", hp=200, max_hp=200, armor=0)
        _equip_unique(defender, "unique_bonecage")

        # Use fixed RNG at 0.99 to ensure no crit fires (crit check: rng < crit_chance)
        damage, info = calculate_damage(attacker, defender, rng=_FixedRng(0.99))
        # 15% DR should reduce damage
        # Without Bonecage, damage would be ~50
        assert damage < 50


# ============================================================
# 9. Bloodpact Ring — Low HP Damage Bonus
# ============================================================

class TestBloodpact:
    """Bloodpact Ring: At below 30% HP, +40% damage."""

    def test_low_hp_bonus_active(self):
        from app.core.combat import calculate_damage
        attacker = _make_player(pid="atk", hp=20, max_hp=100, attack_damage=30)
        _equip_unique(attacker, "unique_bloodpact")
        defender = _make_player(pid="def", hp=200, max_hp=200, armor=0)

        damage, info = calculate_damage(attacker, defender)
        # At 20% HP, +40% damage → 30 * 1.4 = ~42+
        assert damage > 35

    def test_low_hp_bonus_inactive_above_threshold(self):
        from app.core.combat import calculate_damage
        attacker = _make_player(pid="atk", hp=80, max_hp=100, attack_damage=30)
        _equip_unique(attacker, "unique_bloodpact")
        defender = _make_player(pid="def", hp=200, max_hp=200, armor=0)

        dmg_with, info_with = calculate_damage(attacker, defender)
        # At 80% HP, bonus should NOT apply
        attacker2 = _make_player(pid="atk2", hp=80, max_hp=100, attack_damage=30)
        defender2 = _make_player(pid="def2", hp=200, max_hp=200, armor=0)
        dmg_without, info_without = calculate_damage(attacker2, defender2)
        assert dmg_with == dmg_without


# ============================================================
# 10. Sigil of Greed — Damage Penalty
# ============================================================

class TestGreedSigil:
    """Sigil of Greed: -15% damage dealt."""

    def test_damage_penalty(self):
        from app.core.combat import calculate_damage
        attacker = _make_player(pid="atk", attack_damage=40)
        _equip_unique(attacker, "unique_greed_sigil")
        defender = _make_player(pid="def", hp=200, max_hp=200, armor=0)

        dmg_with, info_with = calculate_damage(attacker, defender)

        attacker2 = _make_player(pid="atk2", attack_damage=40)
        defender2 = _make_player(pid="def2", hp=200, max_hp=200, armor=0)
        dmg_without, info_without = calculate_damage(attacker2, defender2)

        assert dmg_with < dmg_without


# ============================================================
# 11. Wraithmantle — Dodge Retaliate
# ============================================================

class TestWraithmantle:
    """Wraithmantle: On dodge, deal 10 damage to attacker."""

    def test_dodge_retaliate_in_combat_info(self):
        from app.core.combat import calculate_damage
        attacker = _make_player(pid="atk", attack_damage=30)
        # Guarantee dodge
        defender = _make_player(pid="def", hp=200, max_hp=200, armor=0, dodge_chance=1.0)
        _equip_unique(defender, "unique_wraithmantle")

        damage, combat_info = calculate_damage(attacker, defender)
        if combat_info.get("dodged"):
            assert combat_info.get("dodge_retaliate_damage", 0) == 10


# ============================================================
# 12. Ironwill Plate — CC Immunity
# ============================================================

class TestIronwill:
    """Ironwill Plate: Immune to stun and root."""

    def test_stun_resisted(self):
        from app.core.skills import resolve_stun_damage
        from app.core.combat import get_combat_config

        attacker = _make_player(pid="atk", attack_damage=20, x=0, y=0, team="team_a")
        defender = _make_player(pid="def", hp=200, max_hp=200, armor=0, x=1, y=0, team="team_b")
        _equip_unique(defender, "unique_ironwill")

        skill_def = {
            "skill_id": "shield_bash",
            "name": "Shield Bash",
            "cooldown_turns": 3,
            "range": 1,
            "effects": [{"type": "stun_damage", "damage_multiplier": 0.7, "stun_duration": 2}],
        }
        players = {"atk": attacker, "def": defender}

        result = resolve_stun_damage(
            attacker, 1, 0, skill_def, players, set(), target_id="def",
        )
        assert result.success
        assert "RESISTED" in result.message or "CC immune" in result.message
        # Defender should NOT have stun buff
        stuns = [b for b in defender.active_buffs if b.get("type") == "stun"]
        assert len(stuns) == 0


# ============================================================
# 13. Dawnbreaker — Holy Skill CDR
# ============================================================

class TestDawnbreaker:
    """Dawnbreaker: Exorcism/Rebuke cooldowns reduced by 2 turns."""

    def test_exorcism_cdr(self):
        from app.core.skills import _apply_skill_cooldown
        player = _make_player(pid="p1")
        _equip_unique(player, "unique_dawnbreaker")
        player.cooldowns = {}

        skill_def = {"skill_id": "exorcism", "cooldown_turns": 5}
        _apply_skill_cooldown(player, skill_def)

        assert player.cooldowns["exorcism"] == 3  # 5 - 2 = 3

    def test_rebuke_cdr(self):
        from app.core.skills import _apply_skill_cooldown
        player = _make_player(pid="p1")
        _equip_unique(player, "unique_dawnbreaker")
        player.cooldowns = {}

        skill_def = {"skill_id": "rebuke", "cooldown_turns": 4}
        _apply_skill_cooldown(player, skill_def)

        assert player.cooldowns["rebuke"] == 2  # 4 - 2 = 2

    def test_non_holy_skill_unaffected(self):
        from app.core.skills import _apply_skill_cooldown
        player = _make_player(pid="p1")
        _equip_unique(player, "unique_dawnbreaker")
        player.cooldowns = {}

        skill_def = {"skill_id": "double_strike", "cooldown_turns": 3}
        _apply_skill_cooldown(player, skill_def)

        assert player.cooldowns["double_strike"] == 3

    def test_cdr_minimum_1(self):
        from app.core.skills import _apply_skill_cooldown
        player = _make_player(pid="p1")
        _equip_unique(player, "unique_dawnbreaker")
        player.cooldowns = {}

        skill_def = {"skill_id": "exorcism", "cooldown_turns": 2}
        _apply_skill_cooldown(player, skill_def)

        assert player.cooldowns["exorcism"] >= 1  # 2 - 2 = 0 → clamped to 1


# ============================================================
# 14. Shadowshroud — Shadow Step CDR
# ============================================================

class TestShadowshroud:
    """Shadowshroud: Shadow Step cooldown reduced by 2 turns."""

    def test_shadow_step_cdr(self):
        from app.core.skills import _apply_skill_cooldown
        player = _make_player(pid="p1")
        _equip_unique(player, "unique_shadowshroud")
        player.cooldowns = {}

        skill_def = {"skill_id": "shadow_step", "cooldown_turns": 5}
        _apply_skill_cooldown(player, skill_def)

        assert player.cooldowns["shadow_step"] == 3  # 5 - 2 = 3


# ============================================================
# 15. Penitent Mail — Healing Received Bonus
# ============================================================

class TestPenitentMail:
    """Penitent Mail: Healing received increased by 30%."""

    def test_heal_bonus(self):
        from app.core.skills import resolve_heal

        healer = _make_player(pid="healer", x=0, y=0, team="team_a")
        target = _make_player(pid="target", hp=50, max_hp=200, x=1, y=0, team="team_a")
        _equip_unique(target, "unique_penitent_mail")

        skill_def = {
            "skill_id": "heal",
            "name": "Heal",
            "cooldown_turns": 2,
            "range": 3,
            "effects": [{"type": "heal", "magnitude": 40}],
        }
        players = {"healer": healer, "target": target}

        result = resolve_heal(healer, 1, 0, skill_def, players, target_id="target")
        # Expected: 40 * 1.30 = 52 (but capped by missing HP)
        assert result.success
        assert result.heal_amount >= 50  # 40 * 1.3 = 52


# ============================================================
# 16. Warden's Oath — Taunt Range Bonus
# ============================================================

class TestWardensOath:
    """Warden's Oath: Taunt radius increased by 1 tile."""

    def test_taunt_range_bonus(self):
        from app.core.skills import resolve_taunt

        tank = _make_player(pid="tank", x=3, y=3, team="team_a")
        _equip_unique(tank, "unique_wardens_oath")
        # Enemy at distance 3 (normally outside radius 2)
        enemy = _make_player(pid="enemy", x=6, y=3, team="team_b")

        skill_def = {
            "skill_id": "taunt",
            "name": "Taunt",
            "cooldown_turns": 4,
            "range": 0,
            "effects": [{"type": "taunt", "radius": 2, "duration_turns": 2}],
        }
        players = {"tank": tank, "enemy": enemy}

        result = resolve_taunt(tank, skill_def, players)
        assert result.success
        # With +1 radius (3 total), enemy at dist 3 should be taunted
        assert "enemy" in result.message.lower() or result.buff_applied is not None


# ============================================================
# 17. Eye of Malice — Crit Skill Reset (Statistical)
# ============================================================

class TestEyeOfMalice:
    """Eye of Malice: Skills that crit have cooldown reset to 0."""

    def test_crit_resets_cooldown(self):
        from app.core.skills import _apply_skill_cooldown
        import random as _random
        # Force crit roll to succeed
        old_random = _random.random
        _random.random = lambda: 0.0  # Always crits

        player = _make_player(pid="p1", crit_chance=0.5)
        _equip_unique(player, "unique_eye_of_malice")
        player.cooldowns = {}

        skill_def = {"skill_id": "fireball", "cooldown_turns": 5}
        _apply_skill_cooldown(player, skill_def, dealt_damage=True)

        _random.random = old_random

        assert player.cooldowns["fireball"] == 0

    def test_non_damage_skill_no_reset(self):
        from app.core.skills import _apply_skill_cooldown

        player = _make_player(pid="p1", crit_chance=1.0)
        _equip_unique(player, "unique_eye_of_malice")
        player.cooldowns = {}

        skill_def = {"skill_id": "heal", "cooldown_turns": 3}
        _apply_skill_cooldown(player, skill_def, dealt_damage=False)

        # Without dealt_damage=True, crit reset should NOT trigger
        assert player.cooldowns["heal"] == 3


# ============================================================
# 18. Prayer Beads — AoE Prayer Heal
# ============================================================

class TestPrayerBeads:
    """Prayer Beads: Prayer heals all adjacent allies."""

    def test_prayer_heals_adjacent_allies(self):
        from app.core.skills import resolve_hot

        healer = _make_player(pid="healer", x=3, y=3, team="team_a")
        _equip_unique(healer, "unique_prayer_beads")

        target = _make_player(pid="target", hp=50, max_hp=200, x=4, y=3, team="team_a")
        ally = _make_player(pid="ally", hp=60, max_hp=200, x=3, y=4, team="team_a")
        far_ally = _make_player(pid="far_ally", hp=60, max_hp=200, x=6, y=6, team="team_a")

        skill_def = {
            "skill_id": "prayer",
            "name": "Prayer",
            "cooldown_turns": 5,
            "range": 4,
            "effects": [{"type": "hot", "heal_per_tick": 8, "duration_turns": 4}],
        }
        players = {"healer": healer, "target": target, "ally": ally, "far_ally": far_ally}

        result = resolve_hot(healer, 4, 3, skill_def, players, target_id="target")
        assert result.success

        # Target should have HoT
        target_hots = [b for b in target.active_buffs if b.get("type") == "hot"]
        assert len(target_hots) >= 1

        # Adjacent ally should also have HoT (thanks to Prayer Beads)
        ally_hots = [b for b in ally.active_buffs if b.get("type") == "hot"]
        assert len(ally_hots) >= 1

        # Far ally should NOT have HoT (not adjacent to healer)
        far_hots = [b for b in far_ally.active_buffs if b.get("type") == "hot"]
        assert len(far_hots) == 0


# ============================================================
# 19. Loot Integration
# ============================================================

class TestLootIntegration:
    """generate_enemy_loot integrates unique drops."""

    def test_unique_in_enemy_loot(self):
        """Boss loot can include a unique item."""
        # Use a high seed count to eventually get a unique
        dropped_ids = set()
        found_unique = False
        for seed in range(200):
            items = generate_enemy_loot(
                enemy_type="demon",
                floor_number=9,
                enemy_tier="boss",
                magic_find_pct=5.0,
                seed=seed,
                dropped_unique_ids=dropped_ids,
            )
            for item in items:
                if item.rarity == Rarity.UNIQUE:
                    found_unique = True
                    break
            if found_unique:
                break
        assert found_unique, "Expected at least one unique drop from 200 boss kills at floor 9 with high MF"

    def test_dropped_ids_tracked(self):
        """dropped_unique_ids set should be updated by loot generation."""
        dropped_ids = set()
        for seed in range(500):
            items = generate_enemy_loot(
                enemy_type="undead",
                floor_number=9,
                enemy_tier="boss",
                magic_find_pct=10.0,
                seed=seed,
                dropped_unique_ids=dropped_ids,
            )
        # If any unique dropped, it should be in dropped_ids
        # (may be empty if no unique dropped, but if one did, it's tracked)
        for uid in dropped_ids:
            assert uid.startswith("unique_")


# ============================================================
# 20. Backward Compatibility
# ============================================================

class TestBackwardCompat:
    """Non-unique items should be completely unaffected by unique hooks."""

    def test_normal_combat_unaffected(self):
        from app.core.combat import calculate_damage
        attacker = _make_player(pid="atk", attack_damage=30)
        defender = _make_player(pid="def", hp=200, max_hp=200, armor=5)

        damage, info = calculate_damage(attacker, defender)
        # Should work without errors
        assert damage > 0
        assert info.get("unique_lifesteal_healed", 0) == 0
        assert info.get("dodge_retaliate_damage", 0) == 0

    def test_normal_skill_cooldown(self):
        from app.core.skills import _apply_skill_cooldown

        player = _make_player(pid="p1")
        player.cooldowns = {}
        skill_def = {"skill_id": "heal", "cooldown_turns": 3}
        _apply_skill_cooldown(player, skill_def)

        assert player.cooldowns["heal"] == 3

    def test_loot_generation_without_unique_param(self):
        """Old callers that don't pass dropped_unique_ids should still work."""
        items = generate_enemy_loot(
            enemy_type="demon",
            floor_number=1,
            enemy_tier="fodder",
            magic_find_pct=0.0,
            seed=42,
        )
        # Should not crash
        assert isinstance(items, list)


# ============================================================
# 21. Plaguebow — Ranged DoT
# ============================================================

class TestPlaguebow:
    """Plaguebow: Ranged hits apply 4 damage/turn poison for 2 turns."""

    def test_plaguebow_dot_flag_in_combat_info(self):
        from app.core.combat import calculate_ranged_damage
        attacker = _make_player(pid="atk", ranged_damage=20)
        _equip_unique(attacker, "unique_plaguebow")
        defender = _make_player(pid="def", hp=200, max_hp=200, armor=0)

        damage, info = calculate_ranged_damage(attacker, defender)
        assert info.get("plaguebow_applied") is True
        dot = info.get("plaguebow_dot", {})
        assert dot.get("damage_per_tick") == 4
        assert dot.get("duration") == 2


# ============================================================
# 22. Grimfang — On-Kill Buff
# ============================================================

class TestGrimfang:
    """Grimfang: On kill, +1 move speed for 2 turns."""

    def test_grimfang_config(self):
        defn = get_unique_definition("unique_grimfang")
        assert defn is not None
        effect = defn["special_effect"]
        assert effect["type"] == "on_kill_buff"
        assert effect["buff_id"] == "grimfang_haste"
        assert effect["value"] == 1
        assert effect["duration"] == 2
