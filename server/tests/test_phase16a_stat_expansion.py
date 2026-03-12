"""
Tests for Phase 16A: Stat Expansion.

Covers every new combat stat introduced in 16A and its integration into the
damage pipeline, skill system, loot, gold, and equipment manager.

Sections:
 1. Crit chance / crit damage (deterministic seeds)
 2. Dodge chance (0%, 100%, capped)
 3. Damage Reduction (%) after flat armor
 4. Armor Penetration (floor at 0)
 5. HP Regen (ticks per turn, caps at max_hp)
 6. Life on Hit (caps at max_hp)
 7. Thorns (reflects damage, can kill attacker)
 8. Cooldown Reduction (CDR) — minimum 1 turn
 9. Skill Damage % bonus
10. Heal Power % bonus
11. DoT / HoT multipliers
12. Holy Damage %
13. Move Speed (field present, ≥ 0)
14. Gold Find %
15. Magic Find %
16. Equipment aggregation / caps
17. Backward compatibility (_simple wrappers)
"""

from __future__ import annotations

import random
import pytest

from app.models.player import PlayerState, Position
from app.models.items import StatBonuses, Item, Equipment, EquipSlot, ItemType, Rarity
from app.core.combat import (
    load_combat_config,
    calculate_damage,
    calculate_ranged_damage,
    calculate_damage_simple,
    calculate_ranged_damage_simple,
    _get_equipment_bonuses,
)
from app.core.skills import (
    load_skills_config,
    clear_skills_cache,
    _apply_skill_cooldown,
)
from app.core.loot import _try_rarity_upgrade, clear_caches as clear_loot_caches


# ---------- Module-level setup ----------

def setup_module():
    load_combat_config()
    load_skills_config()
    # Pre-load match_manager to break circular import chain
    # (equipment_manager ↔ match_manager)
    import app.core.match_manager  # noqa: F401


def teardown_module():
    clear_skills_cache()
    clear_loot_caches()


# ---------- Helpers ----------

def _make(
    pid="p1",
    username="TestUser",
    x=0,
    y=0,
    hp=100,
    max_hp=100,
    attack_damage=15,
    ranged_damage=10,
    armor=0,
    equipment=None,
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
        **kwargs,
    )


class _FixedRng:
    """Deterministic fake RNG for testing — always returns a fixed value.

    Usage:
        _FixedRng(0.0)   → always triggers (random() < any positive threshold)
        _FixedRng(0.99)  → never triggers (random() > any capped threshold)
    """
    def __init__(self, value: float):
        self._value = value

    def random(self) -> float:
        return self._value


# ============================================================
# 1. Crit Chance / Crit Damage
# ============================================================


class TestCritDamage:
    """Crit is checked in the full pipeline with deterministic RNG."""

    def test_guaranteed_crit(self):
        """Force crit with _FixedRng(0.0) — always triggers."""
        attacker = _make(crit_chance=0.50, crit_damage=2.0, dodge_chance=0.0)
        defender = _make(pid="p2", armor=0, dodge_chance=0.0)
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.0))
        assert info["is_crit"] is True
        # 15 base * 2.0 crit = 30
        assert dmg == 30

    def test_no_crit_at_zero_chance(self):
        """0% crit chance never crits regardless of RNG."""
        attacker = _make(crit_chance=0.0, crit_damage=2.0)
        defender = _make(pid="p2", armor=0, dodge_chance=0.0)
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.0))
        assert info["is_crit"] is False
        assert dmg == 15

    def test_no_crit_when_rng_exceeds_cap(self):
        """Even with high crit_chance, _FixedRng(0.99) never triggers."""
        attacker = _make(crit_chance=0.50, crit_damage=2.0)
        defender = _make(pid="p2", armor=0, dodge_chance=0.0)
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.99))
        assert info["is_crit"] is False
        assert dmg == 15

    def test_crit_damage_cap(self):
        """Crit damage is capped at crit_damage_cap (default 3.0)."""
        attacker = _make(crit_chance=0.50, crit_damage=5.0)
        defender = _make(pid="p2", armor=0, dodge_chance=0.0)
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.0))
        assert info["is_crit"] is True
        # capped at 3.0 → 15 * 3.0 = 45
        assert dmg == 45

    def test_crit_applies_to_ranged(self):
        attacker = _make(crit_chance=0.50, crit_damage=2.0)
        defender = _make(pid="p2", armor=0, dodge_chance=0.0)
        dmg, info = calculate_ranged_damage(attacker, defender, rng=_FixedRng(0.0))
        assert info["is_crit"] is True
        # 10 base * 2.0 crit = 20
        assert dmg == 20


# ============================================================
# 2. Dodge Chance
# ============================================================


class TestDodge:
    """Dodge is checked first in the pipeline."""

    def test_guaranteed_dodge_returns_zero(self):
        attacker = _make()
        defender = _make(pid="p2", dodge_chance=0.40)
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.0))
        assert info["is_dodged"] is True
        assert dmg == 0

    def test_zero_dodge_never_dodges(self):
        attacker = _make()
        defender = _make(pid="p2", dodge_chance=0.0)
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.99))
        assert info["is_dodged"] is False
        assert dmg > 0

    def test_dodge_cap_enforced(self):
        """Dodge above 40% cap is still capped — _FixedRng(0.45) does NOT dodge."""
        attacker = _make()
        defender = _make(pid="p2", dodge_chance=0.99)
        # 0.45 > 0.40 cap → no dodge
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.45))
        assert info["is_dodged"] is False
        assert dmg > 0

    def test_dodge_works_for_ranged(self):
        attacker = _make()
        defender = _make(pid="p2", dodge_chance=0.40)
        dmg, info = calculate_ranged_damage(attacker, defender, rng=_FixedRng(0.0))
        assert info["is_dodged"] is True
        assert dmg == 0


# ============================================================
# 3. Damage Reduction (%)
# ============================================================


class TestDamageReduction:
    """Percentage-based damage reduction applied after armor."""

    def test_50pct_dr_halves_post_armor_damage(self):
        attacker = _make(attack_damage=20, crit_chance=0.0)
        defender = _make(pid="p2", armor=0, damage_reduction_pct=0.50, dodge_chance=0.0)
        dmg, _ = calculate_damage(attacker, defender, rng=_FixedRng(0.99))
        # 20 raw, 0 armor, 50% DR → 10
        assert dmg == 10

    def test_dr_cap_respected(self):
        """DR above 50% cap is still clamped."""
        attacker = _make(attack_damage=20, crit_chance=0.0)
        defender = _make(pid="p2", armor=0, damage_reduction_pct=0.90, dodge_chance=0.0)
        dmg, _ = calculate_damage(attacker, defender, rng=_FixedRng(0.99))
        # Capped at 0.50 → 20 * 0.50 = 10
        assert dmg == 10

    def test_dr_after_armor(self):
        """DR is applied AFTER flat armor reduction."""
        attacker = _make(attack_damage=20, crit_chance=0.0)
        # 5 armor removes 5 first → 15, then 50% DR → 7 (int)
        defender = _make(pid="p2", armor=5, damage_reduction_pct=0.50, dodge_chance=0.0)
        dmg, _ = calculate_damage(attacker, defender, rng=_FixedRng(0.99))
        assert dmg == 7


# ============================================================
# 4. Armor Penetration
# ============================================================


class TestArmorPen:
    """Armor pen reduces effective armor, floored at 0."""

    def test_armor_pen_reduces_armor(self):
        attacker = _make(attack_damage=20, armor_pen=3, crit_chance=0.0)
        # Defender has 5 armor; 5-3 = 2 effective → 20-2 = 18
        defender = _make(pid="p2", armor=5, dodge_chance=0.0)
        dmg, _ = calculate_damage(attacker, defender, rng=_FixedRng(0.99))
        assert dmg == 18

    def test_armor_pen_cannot_go_negative(self):
        """Armor pen exceeding armor → effective armor = 0, not negative bonus."""
        attacker = _make(attack_damage=10, armor_pen=100, crit_chance=0.0)
        defender = _make(pid="p2", armor=5, dodge_chance=0.0)
        dmg, _ = calculate_damage(attacker, defender, rng=_FixedRng(0.99))
        # 10 raw, 0 effective armor, 0 DR → 10
        assert dmg == 10

    def test_armor_pen_in_ranged(self):
        attacker = _make(ranged_damage=20, armor_pen=4, crit_chance=0.0)
        defender = _make(pid="p2", armor=6, dodge_chance=0.0)
        dmg, _ = calculate_ranged_damage(attacker, defender, rng=_FixedRng(0.99))
        # 6-4=2 armor, 20-2 = 18
        assert dmg == 18


# ============================================================
# 5. HP Regen
# ============================================================


class TestHPRegen:
    """HP regen is a field on PlayerState; ticking is tested via turn_resolver
    integration. Here we verify the field defaults and caps."""

    def test_hp_regen_default_is_zero(self):
        player = _make()
        assert player.hp_regen == 0

    def test_hp_regen_stored_on_player(self):
        player = _make(hp_regen=5)
        assert player.hp_regen == 5


# ============================================================
# 6. Life on Hit
# ============================================================


class TestLifeOnHit:
    """Life on hit heals attacker on successful damage, capped at max HP."""

    def test_life_on_hit_heals(self):
        attacker = _make(hp=80, max_hp=100, life_on_hit=5, crit_chance=0.0)
        defender = _make(pid="p2", armor=0, dodge_chance=0.0)
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.99))
        assert dmg > 0
        assert info["life_on_hit_healed"] == 5
        assert attacker.hp == 85

    def test_life_on_hit_caps_at_max_hp(self):
        attacker = _make(hp=98, max_hp=100, life_on_hit=10, crit_chance=0.0)
        defender = _make(pid="p2", armor=0, dodge_chance=0.0)
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.99))
        assert attacker.hp == 100
        assert info["life_on_hit_healed"] == 2  # Only healed 2 to cap

    def test_life_on_hit_no_heal_on_dodge(self):
        attacker = _make(hp=80, life_on_hit=5, crit_chance=0.0)
        defender = _make(pid="p2", dodge_chance=0.40)
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.0))
        assert dmg == 0
        assert info["life_on_hit_healed"] == 0
        assert attacker.hp == 80  # Unchanged


# ============================================================
# 7. Thorns
# ============================================================


class TestThorns:
    """Thorns reflects flat damage back to the attacker."""

    def test_thorns_damages_attacker(self):
        attacker = _make(hp=100, crit_chance=0.0)
        defender = _make(pid="p2", armor=0, dodge_chance=0.0, thorns=8)
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.99))
        assert dmg > 0
        assert info["thorns_damage"] == 8
        assert attacker.hp == 92

    def test_thorns_can_kill_attacker(self):
        attacker = _make(hp=5, crit_chance=0.0)
        defender = _make(pid="p2", armor=0, dodge_chance=0.0, thorns=20)
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.99))
        assert info["thorns_damage"] == 20
        assert attacker.hp == 0
        assert attacker.is_alive is False

    def test_thorns_no_damage_on_dodge(self):
        attacker = _make(hp=100, crit_chance=0.0)
        defender = _make(pid="p2", dodge_chance=0.40, thorns=10)
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.0))
        assert dmg == 0
        assert info["thorns_damage"] == 0
        assert attacker.hp == 100


# ============================================================
# 8. Cooldown Reduction (CDR)
# ============================================================


class TestCooldownReduction:
    """CDR reduces skill cooldowns with a minimum of 1 turn."""

    def test_cdr_reduces_cooldown(self):
        player = _make(cooldown_reduction_pct=0.25)
        skill_def = {"skill_id": "test_skill", "cooldown_turns": 4}
        _apply_skill_cooldown(player, skill_def)
        # 4 * (1 - 0.25) = 3
        assert player.cooldowns["test_skill"] == 3

    def test_cdr_minimum_one_turn(self):
        player = _make(cooldown_reduction_pct=0.99)
        skill_def = {"skill_id": "test_skill", "cooldown_turns": 2}
        _apply_skill_cooldown(player, skill_def)
        # 2 * 0.01 → rounds to 0, but clamped to 1
        assert player.cooldowns["test_skill"] == 1

    def test_zero_cdr_is_base_cooldown(self):
        player = _make(cooldown_reduction_pct=0.0)
        skill_def = {"skill_id": "test_skill", "cooldown_turns": 5}
        _apply_skill_cooldown(player, skill_def)
        assert player.cooldowns["test_skill"] == 5


# ============================================================
# 9. Skill Damage %
# ============================================================


class TestSkillDamPct:
    """skill_damage_pct field is correctly stored and defaults to 0."""

    def test_default_is_zero(self):
        player = _make()
        assert player.skill_damage_pct == 0.0

    def test_custom_value(self):
        player = _make(skill_damage_pct=0.25)
        assert player.skill_damage_pct == 0.25


# ============================================================
# 10. Heal Power %
# ============================================================


class TestHealPowerPct:
    def test_default_is_zero(self):
        player = _make()
        assert player.heal_power_pct == 0.0

    def test_custom_value(self):
        player = _make(heal_power_pct=0.30)
        assert player.heal_power_pct == 0.30


# ============================================================
# 11. DoT / HoT multipliers
# ============================================================


class TestDotHotPct:
    def test_dot_default(self):
        p = _make()
        assert p.dot_damage_pct == 0.0

    def test_dot_custom(self):
        p = _make(dot_damage_pct=0.20)
        assert p.dot_damage_pct == 0.20

    def test_holy_damage_default(self):
        p = _make()
        assert p.holy_damage_pct == 0.0


# ============================================================
# 12. Holy Damage %
# ============================================================


class TestHolyDmgPct:
    def test_default(self):
        p = _make()
        assert p.holy_damage_pct == 0.0

    def test_set(self):
        p = _make(holy_damage_pct=0.15)
        assert p.holy_damage_pct == 0.15


# ============================================================
# 13. Move Speed
# ============================================================


class TestMoveSpeed:
    def test_default_is_zero(self):
        p = _make()
        assert p.move_speed == 0

    def test_set(self):
        p = _make(move_speed=2)
        assert p.move_speed == 2


# ============================================================
# 14. Gold Find %
# ============================================================


class TestGoldFind:
    def test_default_is_zero(self):
        p = _make()
        assert p.gold_find_pct == 0.0

    def test_set(self):
        p = _make(gold_find_pct=0.50)
        assert p.gold_find_pct == 0.50


# ============================================================
# 15. Magic Find %
# ============================================================


class TestMagicFind:
    """magic_find_pct used in loot.py to upgrade rarity."""

    def test_default_is_zero(self):
        p = _make()
        assert p.magic_find_pct == 0.0

    def test_rarity_upgrade_common_to_uncommon(self):
        """Phase 16C: common now upgrades to MAGIC instead of UNCOMMON."""
        item = Item(
            item_id="test", name="Test Sword", item_type=ItemType.WEAPON,
            rarity=Rarity.COMMON, equip_slot="weapon",
            stat_bonuses=StatBonuses(attack_damage=1),
        )
        rng = random.Random(42)
        upgraded = _try_rarity_upgrade(item, 1.0, rng)  # 100% chance
        assert upgraded.rarity == Rarity.MAGIC

    def test_no_upgrade_at_zero(self):
        item = Item(
            item_id="test", name="Test Sword", item_type=ItemType.WEAPON,
            rarity=Rarity.COMMON, equip_slot="weapon",
            stat_bonuses=StatBonuses(attack_damage=1),
        )
        rng = random.Random(42)
        upgraded = _try_rarity_upgrade(item, 0.0, rng)
        assert upgraded.rarity == Rarity.COMMON


# ============================================================
# 16. Equipment Aggregation / Caps
# ============================================================


class TestEquipmentAggregation:
    """_recalculate_effective_stats sums equipment bonuses and applies caps."""

    @staticmethod
    def _recalc(player):
        from app.core.equipment_manager import _recalculate_effective_stats
        _recalculate_effective_stats(player)

    def _make_item_data(self, **stat_kwargs) -> dict:
        """Return a minimal item dict suitable for player.equipment slot."""
        bonuses = StatBonuses(**stat_kwargs)
        return {
            "item_id": "test_item",
            "name": "Test",
            "item_type": "weapon",
            "rarity": "common",
            "equip_slot": "weapon",
            "stat_bonuses": bonuses.model_dump(),
        }

    def test_single_item_stats(self):
        player = _make(equipment={
            "weapon": self._make_item_data(crit_chance=0.10, thorns=3),
        })
        self._recalc(player)
        # base 0.05 + 0.10 = 0.15
        assert player.crit_chance == pytest.approx(0.15)
        assert player.thorns == 3

    def test_multiple_items_stack(self):
        player = _make(equipment={
            "weapon": self._make_item_data(crit_chance=0.05, life_on_hit=2),
            "armor": self._make_item_data(crit_chance=0.05, life_on_hit=3),
        })
        self._recalc(player)
        # base 0.05 + 0.05 + 0.05 = 0.15
        assert player.crit_chance == pytest.approx(0.15)
        assert player.life_on_hit == 5

    def test_dodge_cap(self):
        player = _make(equipment={
            "weapon": self._make_item_data(dodge_chance=0.30),
            "armor": self._make_item_data(dodge_chance=0.30),
        })
        self._recalc(player)
        # 0.60 would exceed cap of 0.40
        assert player.dodge_chance == pytest.approx(0.40)

    def test_cdr_cap(self):
        player = _make(equipment={
            "weapon": self._make_item_data(cooldown_reduction_pct=0.20),
            "armor": self._make_item_data(cooldown_reduction_pct=0.20),
        })
        self._recalc(player)
        # 0.40 would exceed cap of 0.30
        assert player.cooldown_reduction_pct == pytest.approx(0.30)

    def test_dr_cap(self):
        player = _make(equipment={
            "weapon": self._make_item_data(damage_reduction_pct=0.60),
        })
        self._recalc(player)
        # capped at 0.50
        assert player.damage_reduction_pct == pytest.approx(0.50)

    def test_crit_damage_cap(self):
        player = _make(equipment={
            "weapon": self._make_item_data(crit_damage=5.0),
        })
        self._recalc(player)
        # base 1.5 + 5.0 = 6.5 → capped at 3.0
        assert player.crit_damage == pytest.approx(3.0)

    def test_empty_equipment_uses_defaults(self):
        player = _make(equipment={})
        self._recalc(player)
        assert player.crit_chance == pytest.approx(0.05)  # base
        assert player.crit_damage == pytest.approx(1.5)   # base
        assert player.dodge_chance == 0.0
        assert player.damage_reduction_pct == 0.0
        assert player.thorns == 0
        assert player.life_on_hit == 0


# ============================================================
# 17. Backward Compatibility (_simple wrappers)
# ============================================================


class TestSimpleWrappers:
    """_simple variants return plain int, no crit/dodge/thorns."""

    def test_calculate_damage_simple_returns_int(self):
        attacker = _make(crit_chance=1.0, crit_damage=3.0)
        defender = _make(pid="p2", armor=0, dodge_chance=0.5)
        result = calculate_damage_simple(attacker, defender)
        # No crit, no dodge — just base formula
        assert isinstance(result, int)
        assert result == 15

    def test_calculate_ranged_damage_simple_returns_int(self):
        attacker = _make(ranged_damage=10, crit_chance=1.0)
        defender = _make(pid="p2", armor=0, dodge_chance=0.5)
        result = calculate_ranged_damage_simple(attacker, defender)
        assert isinstance(result, int)
        assert result == 10


# ============================================================
# 18. StatBonuses Model Expansion
# ============================================================


class TestStatBonusesModel:
    """All 16A fields exist on StatBonuses with correct defaults."""

    def test_all_new_fields_default_zero(self):
        sb = StatBonuses()
        for field in [
            "crit_chance", "crit_damage", "dodge_chance",
            "damage_reduction_pct", "hp_regen", "move_speed",
            "life_on_hit", "cooldown_reduction_pct", "skill_damage_pct",
            "thorns", "gold_find_pct", "magic_find_pct",
            "holy_damage_pct", "dot_damage_pct", "heal_power_pct", "armor_pen",
        ]:
            assert getattr(sb, field) == 0, f"{field} should default to 0"

    def test_original_fields_still_default_zero(self):
        sb = StatBonuses()
        assert sb.attack_damage == 0
        assert sb.ranged_damage == 0
        assert sb.armor == 0
        assert sb.max_hp == 0


# ============================================================
# 19. PlayerState Effective Stats Defaults
# ============================================================


class TestPlayerStateDefaults:
    """PlayerState has correct defaults for 16A effective stats."""

    def test_crit_defaults(self):
        p = _make()
        assert p.crit_chance == pytest.approx(0.05)
        assert p.crit_damage == pytest.approx(1.5)

    def test_defensive_defaults(self):
        p = _make()
        assert p.dodge_chance == 0.0
        assert p.damage_reduction_pct == 0.0

    def test_utility_defaults(self):
        p = _make()
        assert p.hp_regen == 0
        assert p.move_speed == 0
        assert p.life_on_hit == 0
        assert p.cooldown_reduction_pct == 0.0
        assert p.thorns == 0
        assert p.gold_find_pct == 0.0
        assert p.magic_find_pct == 0.0
        assert p.armor_pen == 0

    def test_damage_bonus_defaults(self):
        p = _make()
        assert p.skill_damage_pct == 0.0
        assert p.holy_damage_pct == 0.0
        assert p.dot_damage_pct == 0.0
        assert p.heal_power_pct == 0.0


# ============================================================
# 20. Full Pipeline Integration
# ============================================================


class TestFullPipeline:
    """End-to-end damage calculation with multiple stats at play."""

    def test_crit_after_armor_and_dr(self):
        """Crit multiplier applies to post-armor, post-DR damage."""
        attacker = _make(
            attack_damage=20,
            armor_pen=2,
            crit_chance=0.50,
            crit_damage=2.0,
        )
        defender = _make(
            pid="p2",
            armor=6,
            dodge_chance=0.0,
            damage_reduction_pct=0.20,
        )
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.0))
        # Raw: 20
        # Armor pen: 6 - 2 = 4 effective armor
        # Post armor: 20 - 4 = 16
        # DR 20%: 16 * 0.80 = 12 (int)
        # Crit 2.0x: 12 * 2.0 = 24
        assert info["is_crit"] is True
        assert dmg == 24

    def test_dodge_short_circuits_everything(self):
        """If dodge succeeds, damage is 0, no life on hit, no thorns."""
        attacker = _make(
            attack_damage=50,
            life_on_hit=10,
            hp=80,
            crit_chance=0.50,
        )
        defender = _make(
            pid="p2",
            dodge_chance=0.40,
            thorns=20,
        )
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.0))
        assert dmg == 0
        assert info["is_dodged"] is True
        assert info["life_on_hit_healed"] == 0
        assert info["thorns_damage"] == 0
        assert attacker.hp == 80  # Unchanged

    def test_life_on_hit_and_thorns_together(self):
        """Both life on hit and thorns trigger on successful hits."""
        attacker = _make(
            hp=90, max_hp=100,
            attack_damage=20,
            life_on_hit=5,
            crit_chance=0.0,
        )
        defender = _make(
            pid="p2",
            armor=0,
            dodge_chance=0.0,
            thorns=3,
        )
        dmg, info = calculate_damage(attacker, defender, rng=_FixedRng(0.99))
        # Damage: 20
        # Life on hit: 90 + 5 = 95
        # Thorns: 95 - 3 = 92
        assert dmg == 20
        assert info["life_on_hit_healed"] == 5
        assert info["thorns_damage"] == 3
        assert attacker.hp == 92
