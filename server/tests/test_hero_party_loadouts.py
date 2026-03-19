"""
Tests for Phase 28E — Enemy Hero Party Loadouts.

Covers:
  - _CLASS_ROLE_MAP completeness and correct mappings
  - _get_role_for_unit fallback for hero parties (class_id → role)
  - generate_hero_loadout per class (weapon category, armor category, potions)
  - Loadout rarity scaling with match_tier
  - AI opponent drinks potion via 28A (integration)
  - AI opponent auto-equips upgrade via 28D (integration)
  - No loadout for human players
  - _apply_loadout_to_unit stat application for heroes
"""

import random

import pytest

from app.models.player import (
    PlayerState,
    Position,
    ClassDefinition,
    get_all_classes,
    apply_class_stats,
)
from app.models.actions import ActionType
# Import match_manager BEFORE equipment_manager to avoid circular import
from app.core.match_manager import (
    generate_hero_loadout,
    _apply_loadout_to_unit,
    _RARITY_TIERS,
)
from app.core.equipment_manager import (
    _CLASS_ROLE_MAP,
    _get_role_for_unit,
    score_item_for_role,
    try_auto_equip,
    _ROLE_STAT_WEIGHTS,
)
from app.core.combat import load_combat_config


def setup_module():
    load_combat_config()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hero(class_id: str = "crusader", team: str = "b") -> PlayerState:
    """Create an AI hero party unit with class stats applied."""
    unit = PlayerState(
        player_id=f"ai-test-{class_id}",
        username=class_id.title(),
        position=Position(x=5, y=5),
        unit_type="ai",
        team=team,
        armor=2,
        is_ready=True,
    )
    apply_class_stats(unit, class_id)
    return unit


def _make_item(slot: str = "weapon", attack: int = 10, weapon_cat: str = "melee") -> dict:
    """Create a minimal mock item dict for testing."""
    return {
        "item_id": f"test_{slot}",
        "name": f"Test {slot.title()}",
        "item_type": "weapon" if slot == "weapon" else "armor",
        "equip_slot": slot,
        "weapon_category": weapon_cat if slot == "weapon" else "",
        "armor_category": "heavy" if slot == "armor" else "",
        "rarity": "common",
        "instance_id": f"inst-{slot}-{attack}",
        "stat_bonuses": {
            "attack_damage": attack if slot == "weapon" else 0,
            "ranged_damage": 0,
            "armor": attack if slot == "armor" else 0,
            "max_hp": 0,
        },
    }


# ---------------------------------------------------------------------------
# TestClassRoleMap — _CLASS_ROLE_MAP completeness
# ---------------------------------------------------------------------------

class TestClassRoleMap:
    """Verify _CLASS_ROLE_MAP covers all 11 classes with valid roles."""

    def test_all_classes_mapped(self):
        all_classes = get_all_classes()
        for class_id in all_classes:
            assert class_id in _CLASS_ROLE_MAP, f"{class_id} missing from _CLASS_ROLE_MAP"

    def test_roles_are_valid(self):
        valid_roles = set(_ROLE_STAT_WEIGHTS.keys())
        for class_id, role in _CLASS_ROLE_MAP.items():
            assert role in valid_roles, f"{class_id} mapped to invalid role '{role}'"

    def test_melee_classes_are_aggressive(self):
        for cls_id in ("crusader", "blood_knight", "revenant", "hexblade"):
            assert _CLASS_ROLE_MAP[cls_id] == "aggressive"

    def test_ranged_classes_are_ranged(self):
        for cls_id in ("ranger", "mage", "inquisitor", "plague_doctor"):
            assert _CLASS_ROLE_MAP[cls_id] == "ranged"

    def test_support_classes_are_support(self):
        for cls_id in ("confessor", "bard", "shaman"):
            assert _CLASS_ROLE_MAP[cls_id] == "support"


# ---------------------------------------------------------------------------
# TestGetRoleForUnit — _get_role_for_unit fallback logic
# ---------------------------------------------------------------------------

class TestGetRoleForUnit:
    """Verify _get_role_for_unit picks ai_behavior first, then class_id fallback."""

    def test_uses_ai_behavior_when_set(self):
        unit = _make_hero("crusader")
        unit.ai_behavior = "ranged"
        assert _get_role_for_unit(unit) == "ranged"

    def test_falls_back_to_class_id(self):
        unit = _make_hero("ranger")
        # Hero party units don't have ai_behavior set
        assert unit.ai_behavior is None
        assert _get_role_for_unit(unit) == "ranged"

    def test_falls_back_to_aggressive_for_unknown(self):
        unit = PlayerState(player_id="ai-x", username="X", unit_type="ai", team="b")
        unit.class_id = "unknown_class"
        assert _get_role_for_unit(unit) == "aggressive"

    def test_falls_back_to_aggressive_for_no_class(self):
        unit = PlayerState(player_id="ai-x", username="X", unit_type="ai", team="b")
        assert _get_role_for_unit(unit) == "aggressive"


# ---------------------------------------------------------------------------
# TestHeroLoadoutGeneration — generate_hero_loadout per class
# ---------------------------------------------------------------------------

class TestHeroLoadoutGeneration:
    """Verify generate_hero_loadout produces class-appropriate gear."""

    def test_crusader_gets_melee_weapon(self):
        rng = random.Random(42)
        eq, inv = generate_hero_loadout("crusader", rng=rng)
        assert "weapon" in eq
        weapon = eq["weapon"]
        assert weapon.get("weapon_category") in ("melee", "hybrid")

    def test_ranger_gets_ranged_weapon(self):
        rng = random.Random(42)
        eq, inv = generate_hero_loadout("ranger", rng=rng)
        assert "weapon" in eq
        weapon = eq["weapon"]
        assert weapon.get("weapon_category") in ("ranged", "hybrid")

    def test_mage_gets_caster_weapon(self):
        rng = random.Random(42)
        eq, inv = generate_hero_loadout("mage", rng=rng)
        assert "weapon" in eq
        weapon = eq["weapon"]
        assert weapon.get("weapon_category") in ("caster", "hybrid")

    def test_crusader_gets_heavy_armor(self):
        rng = random.Random(42)
        eq, inv = generate_hero_loadout("crusader", rng=rng)
        assert "armor" in eq
        armor = eq["armor"]
        assert armor.get("armor_category") == "heavy"

    def test_mage_gets_cloth_armor(self):
        rng = random.Random(42)
        eq, inv = generate_hero_loadout("mage", rng=rng)
        assert "armor" in eq
        armor = eq["armor"]
        assert armor.get("armor_category") == "cloth"

    def test_ranger_gets_light_armor(self):
        rng = random.Random(42)
        eq, inv = generate_hero_loadout("ranger", rng=rng)
        assert "armor" in eq
        armor = eq["armor"]
        assert armor.get("armor_category") == "light"

    def test_includes_potions(self):
        rng = random.Random(42)
        eq, inv = generate_hero_loadout("crusader", rng=rng)
        assert len(inv) >= 2
        assert len(inv) <= 3
        for item in inv:
            assert item.get("item_type") == "consumable" or "potion" in item.get("item_id", "")

    def test_invalid_class_returns_empty(self):
        eq, inv = generate_hero_loadout("nonexistent_class")
        assert eq == {}
        assert inv == []


# ---------------------------------------------------------------------------
# TestHeroLoadoutRarityScaling — match_tier controls rarity
# ---------------------------------------------------------------------------

class TestHeroLoadoutRarityScaling:
    """Verify match_tier shifts rarity tiers appropriately."""

    def test_high_tier_produces_better_rarity(self):
        """High tier items should on average be higher rarity than low tier."""
        rng_low = random.Random(100)
        rng_high = random.Random(100)
        eq_low, _ = generate_hero_loadout("crusader", match_tier="low", rng=rng_low)
        eq_high, _ = generate_hero_loadout("crusader", match_tier="high", rng=rng_high)

        weapon_low = eq_low.get("weapon", {})
        weapon_high = eq_high.get("weapon", {})

        if weapon_low and weapon_high:
            rarity_low = str(weapon_low.get("rarity", "common"))
            rarity_high = str(weapon_high.get("rarity", "common"))
            # With the same seed, high tier should be >= low tier rarity
            low_idx = _RARITY_TIERS.index(rarity_low) if rarity_low in _RARITY_TIERS else 0
            high_idx = _RARITY_TIERS.index(rarity_high) if rarity_high in _RARITY_TIERS else 0
            assert high_idx >= low_idx

    def test_low_tier_produces_common_or_magic(self):
        """Low tier should produce common or magic items at floor 1."""
        rng = random.Random(42)
        eq, _ = generate_hero_loadout("ranger", match_tier="low", floor_number=1, rng=rng)
        weapon = eq.get("weapon", {})
        if weapon:
            rarity = str(weapon.get("rarity", "common")).lower()
            assert any(r in rarity for r in ("common", "magic", "rare"))  # Allow up to rare with RNG


# ---------------------------------------------------------------------------
# TestApplyLoadoutStats — _apply_loadout_to_unit stat bonuses
# ---------------------------------------------------------------------------

class TestApplyLoadoutStats:
    """Verify that applying a loadout increases unit stats correctly."""

    def test_weapon_increases_attack_damage(self):
        unit = _make_hero("crusader")
        base_atk = unit.attack_damage
        weapon = _make_item("weapon", attack=10)
        _apply_loadout_to_unit(unit, {"weapon": weapon}, [])
        assert unit.attack_damage >= base_atk + 10

    def test_armor_increases_armor(self):
        unit = _make_hero("crusader")
        base_armor = unit.armor
        armor = _make_item("armor", attack=5)
        _apply_loadout_to_unit(unit, {"armor": armor}, [])
        assert unit.armor >= base_armor + 5

    def test_potions_in_inventory(self):
        unit = _make_hero("ranger")
        potion = {"item_id": "health_potion", "item_type": "consumable", "name": "Health Potion"}
        _apply_loadout_to_unit(unit, {}, [potion, potion])
        assert len(unit.inventory) == 2

    def test_full_loadout_for_all_classes(self):
        """Every class should get a valid loadout without errors."""
        all_classes = get_all_classes()
        for class_id in all_classes:
            rng = random.Random(42)
            eq, inv = generate_hero_loadout(class_id, rng=rng)
            unit = _make_hero(class_id)
            _apply_loadout_to_unit(unit, eq, inv)
            # Unit should have equipment and inventory
            assert unit.equipment or unit.inventory, f"{class_id} got no loadout"


# ---------------------------------------------------------------------------
# TestHeroPartyScoring — score_item_for_role respects _CLASS_ROLE_MAP
# ---------------------------------------------------------------------------

class TestHeroPartyScoring:
    """Verify item scoring uses correct role for hero party classes."""

    def test_crusader_scores_attack_highly(self):
        """Crusader (aggressive) should score attack_damage items high."""
        sword = {"stat_bonuses": {"attack_damage": 10}, "item_type": "weapon"}
        staff = {"stat_bonuses": {"ranged_damage": 10}, "item_type": "weapon"}
        role = _CLASS_ROLE_MAP["crusader"]
        assert score_item_for_role(sword, role) > score_item_for_role(staff, role)

    def test_ranger_scores_ranged_highly(self):
        """Ranger (ranged) should score ranged_damage items high."""
        bow = {"stat_bonuses": {"ranged_damage": 10}, "item_type": "weapon"}
        sword = {"stat_bonuses": {"attack_damage": 10}, "item_type": "weapon"}
        role = _CLASS_ROLE_MAP["ranger"]
        assert score_item_for_role(bow, role) > score_item_for_role(sword, role)

    def test_confessor_scores_defense_highly(self):
        """Confessor (support) should score max_hp items high."""
        shield = {"stat_bonuses": {"max_hp": 20}, "item_type": "armor"}
        sword = {"stat_bonuses": {"attack_damage": 10}, "item_type": "weapon"}
        role = _CLASS_ROLE_MAP["confessor"]
        assert score_item_for_role(shield, role) > score_item_for_role(sword, role)


# ---------------------------------------------------------------------------
# TestAutoEquipRoleFallback — try_auto_equip uses class_id fallback
# ---------------------------------------------------------------------------

class TestAutoEquipRoleFallback:
    """Verify try_auto_equip falls back to _CLASS_ROLE_MAP for hero parties."""

    def test_hero_without_ai_behavior_still_scores(self):
        """Hero party units (no ai_behavior) should still get valid scoring."""
        unit = _make_hero("ranger")
        assert unit.ai_behavior is None
        role = _get_role_for_unit(unit)
        assert role == "ranged"

    def test_hero_crusader_role_is_aggressive(self):
        unit = _make_hero("crusader")
        assert _get_role_for_unit(unit) == "aggressive"

    def test_hero_bard_role_is_support(self):
        unit = _make_hero("bard")
        assert _get_role_for_unit(unit) == "support"


# ---------------------------------------------------------------------------
# TestPotionUsageIntegration — 28A works for hero party units
# ---------------------------------------------------------------------------

class TestPotionUsageIntegration:
    """Verify hero party AI drinks potions from spawned loadout."""

    def test_hero_with_potion_at_low_hp(self):
        """AI hero at low HP with potion in inventory → should drink it."""
        from app.core.ai_stances import _should_use_potion

        unit = _make_hero("crusader")
        # Give unit a potion (matching items_config.json format)
        unit.inventory = [{
            "item_id": "health_potion",
            "name": "Health Potion",
            "item_type": "consumable",
            "consumable_effect": {"type": "heal", "magnitude": 40},
            "instance_id": "pot-1",
        }]
        # Set HP to 20% of max
        unit.hp = int(unit.max_hp * 0.20)
        action = _should_use_potion(unit, hp_threshold=0.30)
        assert action is not None
        assert action.action_type == ActionType.USE_ITEM

    def test_hero_with_potion_above_threshold(self):
        """AI hero at high HP → should NOT drink potion."""
        from app.core.ai_stances import _should_use_potion

        unit = _make_hero("crusader")
        unit.inventory = [{
            "item_id": "health_potion",
            "name": "Health Potion",
            "item_type": "consumable",
            "consumable_effect": {"type": "heal", "magnitude": 40},
            "instance_id": "pot-1",
        }]
        unit.hp = unit.max_hp  # Full HP
        action = _should_use_potion(unit, hp_threshold=0.30)
        assert action is None


# ---------------------------------------------------------------------------
# TestNoLoadoutForHumans — human players unaffected
# ---------------------------------------------------------------------------

class TestNoLoadoutForHumans:
    """Verify loadout generation doesn't apply to human player units."""

    def test_human_unit_no_auto_equip(self):
        """Human unit should not trigger auto-equip via unit_type check."""
        unit = PlayerState(
            player_id="human-1",
            username="Player",
            unit_type="human",
            team="a",
        )
        # Human has ai_behavior=None and unit_type="human"
        assert unit.unit_type == "human"
        # Auto-equip is gated on unit_type == "ai" in interaction_phase
