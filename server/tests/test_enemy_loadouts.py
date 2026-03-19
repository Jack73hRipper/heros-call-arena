"""
Tests for Phase 28B — Enemy Spawn Loadouts.

Covers:
  - Basic loadout generation (demon with melee + heavy config)
  - Rarity scaling by floor number
  - Champion monster rarity bonus (+1 tier)
  - Backwards compatibility (no loadout = empty equipment)
  - Equipment stats applied to unit
  - Potion count within min/max range
  - Equipped items drop on death
  - Integration: enemy spawns with potion, takes damage, drinks it (28A+28B)
"""

import random

import pytest

from app.models.player import PlayerState, Position, EnemyDefinition
from app.models.actions import ActionType, ActionResult
from app.core.match_manager import generate_enemy_loadout, _apply_loadout_to_unit
from app.core.turn_phases.deaths_phase import _resolve_deaths
from app.core.combat import load_combat_config


def setup_module():
    load_combat_config()


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

def _demon_def() -> EnemyDefinition:
    """Demon enemy definition with loadout config."""
    return EnemyDefinition(
        enemy_id="demon",
        name="Demon",
        role="Melee Bruiser",
        base_hp=240,
        base_melee_damage=18,
        base_armor=5,
        ai_behavior="aggressive",
        class_id="demon_enrage",
        tags=["demon"],
        loadout={
            "weapon": {"pool": ["melee"], "rarity_offset": 0},
            "armor": {"pool": ["heavy", "light"], "rarity_offset": 0},
            "accessory": None,
            "potions": {"type": "health_potion", "count": [1, 2]},
        },
    )


def _skeleton_def() -> EnemyDefinition:
    """Skeleton enemy definition with loadout config."""
    return EnemyDefinition(
        enemy_id="skeleton",
        name="Skeleton",
        role="Ranged Sniper",
        base_hp=125,
        base_melee_damage=6,
        base_ranged_damage=14,
        base_armor=2,
        ai_behavior="ranged",
        tags=["undead"],
        loadout={
            "weapon": {"pool": ["ranged"], "rarity_offset": 0},
            "armor": {"pool": ["light"], "rarity_offset": 0},
            "accessory": None,
            "potions": {"type": "health_potion", "count": [0, 1]},
        },
    )


def _bare_imp_def() -> EnemyDefinition:
    """Imp enemy definition without loadout (no config)."""
    return EnemyDefinition(
        enemy_id="imp",
        name="Imp",
        role="Swarm",
        base_hp=70,
        base_melee_damage=8,
        base_armor=1,
        ai_behavior="aggressive",
        tags=["demon", "imp"],
    )


def _make_enemy_unit(enemy_def: EnemyDefinition, pid: str = "enemy-001") -> PlayerState:
    """Build a PlayerState from an EnemyDefinition."""
    return PlayerState(
        player_id=pid,
        username=enemy_def.name,
        position=Position(x=5, y=5),
        hp=enemy_def.base_hp,
        max_hp=enemy_def.base_hp,
        attack_damage=enemy_def.base_melee_damage,
        ranged_damage=enemy_def.base_ranged_damage,
        armor=enemy_def.base_armor,
        team="b",
        unit_type="ai",
        ai_behavior=enemy_def.ai_behavior,
        enemy_type=enemy_def.enemy_id,
    )


# ---------------------------------------------------------------------------
# Tests: Basic Loadout Generation (28B-2)
# ---------------------------------------------------------------------------

class TestLoadoutGenerationBasic:
    """Test generate_enemy_loadout produces correct equipment for demons."""

    def test_demon_generates_weapon_and_armor(self):
        """Demon with melee+heavy config → generates weapon + armor."""
        demon = _demon_def()
        rng = random.Random(42)
        equipment, inventory = generate_enemy_loadout(demon, floor_number=1, rng=rng)

        assert "weapon" in equipment, "Demon should spawn with a weapon"
        assert "armor" in equipment, "Demon should spawn with armor"
        # Weapon should be melee category
        weapon = equipment["weapon"]
        assert weapon.get("weapon_category") == "melee", f"Expected melee, got {weapon.get('weapon_category')}"

    def test_demon_generates_potions(self):
        """Demon generates 1-2 health potions in inventory."""
        demon = _demon_def()
        rng = random.Random(42)
        equipment, inventory = generate_enemy_loadout(demon, floor_number=1, rng=rng)

        assert len(inventory) >= 1, "Demon should have at least 1 potion"
        assert len(inventory) <= 2, "Demon should have at most 2 potions"
        for item in inventory:
            assert item.get("item_id") == "health_potion"

    def test_skeleton_generates_ranged_weapon(self):
        """Skeleton with ranged pool → generates ranged weapon."""
        skeleton = _skeleton_def()
        rng = random.Random(42)
        equipment, inventory = generate_enemy_loadout(skeleton, floor_number=1, rng=rng)

        assert "weapon" in equipment
        weapon = equipment["weapon"]
        assert weapon.get("weapon_category") == "ranged"

    def test_no_accessory_when_null(self):
        """Demon loadout has accessory=null → no accessory generated."""
        demon = _demon_def()
        rng = random.Random(42)
        equipment, inventory = generate_enemy_loadout(demon, floor_number=1, rng=rng)

        assert "accessory" not in equipment or equipment.get("accessory") is None


class TestLoadoutNoConfig:
    """Test backwards compatibility for enemies without loadout."""

    def test_no_loadout_returns_empty(self):
        """Enemy without loadout field → empty equipment, no crash."""
        imp = _bare_imp_def()
        equipment, inventory = generate_enemy_loadout(imp, floor_number=1)

        assert equipment == {}
        assert inventory == []

    def test_none_loadout_returns_empty(self):
        """Enemy with loadout=None → empty equipment."""
        imp = EnemyDefinition(
            enemy_id="imp",
            name="Imp",
            role="Swarm",
            base_hp=70,
            base_melee_damage=8,
            base_armor=1,
            ai_behavior="aggressive",
            loadout=None,
        )
        equipment, inventory = generate_enemy_loadout(imp, floor_number=1)

        assert equipment == {}
        assert inventory == []


# ---------------------------------------------------------------------------
# Tests: Rarity Scaling (28B-2)
# ---------------------------------------------------------------------------

class TestLoadoutRarityScaling:
    """Test that floor depth and monster rarity affect item quality."""

    def test_floor5_higher_chance_of_magic(self):
        """Floor 5 generation should produce more non-common items than floor 1."""
        demon = _demon_def()
        floor1_magic = 0
        floor5_magic = 0
        trials = 100

        for seed in range(trials):
            eq1, _ = generate_enemy_loadout(demon, floor_number=1, rng=random.Random(seed))
            eq5, _ = generate_enemy_loadout(demon, floor_number=5, rng=random.Random(seed))
            if eq1.get("weapon", {}).get("rarity") != "common":
                floor1_magic += 1
            if eq5.get("weapon", {}).get("rarity") != "common":
                floor5_magic += 1

        assert floor5_magic >= floor1_magic, (
            f"Floor 5 should produce >= non-common items as floor 1: "
            f"floor1={floor1_magic}, floor5={floor5_magic}"
        )

    def test_champion_bonus_boosts_rarity(self):
        """Champion enemy → item rarity should be boosted by +1 tier over normal."""
        demon = _demon_def()
        normal_magic = 0
        champ_magic = 0
        trials = 100

        for seed in range(trials):
            eq_n, _ = generate_enemy_loadout(demon, floor_number=1, monster_rarity="normal", rng=random.Random(seed))
            eq_c, _ = generate_enemy_loadout(demon, floor_number=1, monster_rarity="champion", rng=random.Random(seed))
            if eq_n.get("weapon", {}).get("rarity") != "common":
                normal_magic += 1
            if eq_c.get("weapon", {}).get("rarity") != "common":
                champ_magic += 1

        assert champ_magic >= normal_magic, (
            f"Champion rarity bonus should produce >= non-common items as normal: "
            f"normal={normal_magic}, champion={champ_magic}"
        )


# ---------------------------------------------------------------------------
# Tests: Apply Loadout Stats (28B-3)
# ---------------------------------------------------------------------------

class TestApplyLoadoutStats:
    """Test that _apply_loadout_to_unit correctly modifies unit stats."""

    def test_weapon_stats_applied(self):
        """Enemy with loadout → attack_damage includes weapon bonus."""
        demon = _demon_def()
        unit = _make_enemy_unit(demon)
        base_attack = unit.attack_damage

        rng = random.Random(42)
        equipment, inventory = generate_enemy_loadout(demon, floor_number=1, rng=rng)
        _apply_loadout_to_unit(unit, equipment, inventory)

        weapon_bonus = equipment.get("weapon", {}).get("stat_bonuses", {}).get("attack_damage", 0)
        assert unit.attack_damage >= base_attack + weapon_bonus, (
            f"Expected attack_damage >= {base_attack + weapon_bonus}, got {unit.attack_damage}"
        )

    def test_armor_stats_applied(self):
        """Enemy with armor → armor stat includes equipment bonus."""
        demon = _demon_def()
        unit = _make_enemy_unit(demon)
        base_armor = unit.armor

        rng = random.Random(42)
        equipment, inventory = generate_enemy_loadout(demon, floor_number=1, rng=rng)
        _apply_loadout_to_unit(unit, equipment, inventory)

        armor_bonus = equipment.get("armor", {}).get("stat_bonuses", {}).get("armor", 0)
        assert unit.armor >= base_armor + armor_bonus

    def test_inventory_populated(self):
        """Enemy with potion loadout → inventory contains potions."""
        demon = _demon_def()
        unit = _make_enemy_unit(demon)

        rng = random.Random(42)
        equipment, inventory = generate_enemy_loadout(demon, floor_number=1, rng=rng)
        _apply_loadout_to_unit(unit, equipment, inventory)

        assert len(unit.inventory) >= 1
        assert any(item.get("item_id") == "health_potion" for item in unit.inventory)


# ---------------------------------------------------------------------------
# Tests: Equipped Items Drop on Death (28B-4)
# ---------------------------------------------------------------------------

class TestEquippedItemsDropOnDeath:
    """Test that equipped items appear in ground loot when enemy dies."""

    def test_equipped_weapon_drops(self):
        """Enemy with weapon + armor dies → both items appear in ground loot."""
        demon = _demon_def()
        unit = _make_enemy_unit(demon, pid="enemy-dead")
        unit.hp = 0
        unit.is_alive = False

        # Give the unit equipment
        rng = random.Random(42)
        equipment, inventory = generate_enemy_loadout(demon, floor_number=1, rng=rng)
        _apply_loadout_to_unit(unit, equipment, inventory)

        weapon_name = unit.equipment.get("weapon", {}).get("name")
        armor_name = unit.equipment.get("armor", {}).get("name")

        # Set up death resolution context
        killer = PlayerState(
            player_id="player1",
            username="Hero",
            position=Position(x=3, y=3),
            hp=100, max_hp=100,
            team="a", unit_type="human",
        )
        players = {"enemy-dead": unit, "player1": killer}
        ground_items: dict[str, list] = {}
        results = [ActionResult(
            player_id="player1",
            username="Hero",
            action_type=ActionType.ATTACK,
            success=True,
            message="",
            killed=True,
            target_id="enemy-dead",
            target_username="Demon",
        )]
        loot_drops: list[dict] = []

        _resolve_deaths(
            match_id="test-match",
            deaths=["enemy-dead"],
            players=players,
            ground_items=ground_items,
            results=results,
            loot_drops=loot_drops,
            floor_number=1,
        )

        # Check ground items at death position
        death_key = f"{unit.position.x},{unit.position.y}"
        all_ground = ground_items.get(death_key, [])
        ground_names = [item.get("name") for item in all_ground]

        if weapon_name:
            assert weapon_name in ground_names, (
                f"Weapon '{weapon_name}' should drop on death. Ground: {ground_names}"
            )
        if armor_name:
            assert armor_name in ground_names, (
                f"Armor '{armor_name}' should drop on death. Ground: {ground_names}"
            )

    def test_no_equipment_no_extra_drops(self):
        """Enemy without equipment → only normal loot drops (no crash)."""
        imp = _bare_imp_def()
        unit = _make_enemy_unit(imp, pid="enemy-bare")
        unit.hp = 0
        unit.is_alive = False
        unit.enemy_type = "imp"

        killer = PlayerState(
            player_id="player1",
            username="Hero",
            position=Position(x=3, y=3),
            hp=100, max_hp=100,
            team="a", unit_type="human",
        )
        players = {"enemy-bare": unit, "player1": killer}
        ground_items: dict[str, list] = {}
        results = [ActionResult(
            player_id="player1",
            username="Hero",
            action_type=ActionType.ATTACK,
            success=True,
            message="",
            killed=True,
            target_id="enemy-bare",
            target_username="Imp",
        )]
        loot_drops: list[dict] = []

        # Should not crash even with no equipment
        _resolve_deaths(
            match_id="test-match",
            deaths=["enemy-bare"],
            players=players,
            ground_items=ground_items,
            results=results,
            loot_drops=loot_drops,
            floor_number=1,
        )
        # If imp has loot table, items may drop. No crash = pass.


# ---------------------------------------------------------------------------
# Tests: Potion Count Range (28B-2)
# ---------------------------------------------------------------------------

class TestPotionCountRange:
    """Test that potion generation respects min/max count config."""

    def test_potions_within_range(self):
        """Potions generated are within [min, max] for all seeds."""
        demon = _demon_def()
        for seed in range(50):
            _, inventory = generate_enemy_loadout(demon, floor_number=1, rng=random.Random(seed))
            potion_count = sum(1 for i in inventory if i.get("item_id") == "health_potion")
            assert 1 <= potion_count <= 2, (
                f"Seed {seed}: expected 1-2 potions, got {potion_count}"
            )

    def test_skeleton_zero_potions_possible(self):
        """Skeleton with count=[0,1] can have 0 potions."""
        skeleton = _skeleton_def()
        found_zero = False
        for seed in range(100):
            _, inventory = generate_enemy_loadout(skeleton, floor_number=1, rng=random.Random(seed))
            potion_count = sum(1 for i in inventory if i.get("item_id") == "health_potion")
            assert 0 <= potion_count <= 1
            if potion_count == 0:
                found_zero = True
        assert found_zero, "Skeleton should be able to have 0 potions with count=[0,1]"


# ---------------------------------------------------------------------------
# Tests: 28A+28B Integration — Enemy Drinks Spawned Potion
# ---------------------------------------------------------------------------

class TestLoadoutPotionIntegration:
    """Integration test: enemy spawns with potion, AI should drink it."""

    def test_enemy_uses_spawned_potion(self):
        """Enemy spawns with potion via loadout, takes damage → drinks it."""
        from app.core.ai_behavior import _should_use_potion, _ENEMY_POTION_THRESHOLDS

        demon = _demon_def()
        unit = _make_enemy_unit(demon)

        # Apply loadout
        rng = random.Random(42)
        equipment, inventory = generate_enemy_loadout(demon, floor_number=1, rng=rng)
        _apply_loadout_to_unit(unit, equipment, inventory)

        # Set HP below aggressive threshold (30%)
        unit.hp = int(unit.max_hp * 0.20)  # 20% HP

        threshold = _ENEMY_POTION_THRESHOLDS.get("aggressive", 0.30)
        action = _should_use_potion(unit, hp_threshold=threshold)

        assert action is not None, "Enemy with potion below threshold should drink"
        assert action.action_type == ActionType.USE_ITEM
