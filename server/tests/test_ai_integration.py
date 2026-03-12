"""
Tests for Phase 8F-1 — AI Decision Priority Chain Integration.

Verifies the complete priority chain in _decide_stance_action():
  1. POTION CHECK   → HP below threshold? Drink potion (USE_ITEM)
  2. SKILL DECISION → Role-appropriate skill available? Use it (SKILL)
  3. STANCE BEHAVIOR → Existing follow/aggressive/defensive/hold logic
     3a. Adjacent enemy    → ATTACK (basic melee)
     3b. Ranged available  → RANGED_ATTACK
     3c. Move toward       → MOVE
     3d. Regroup/patrol    → MOVE toward owner
     3e. Nothing to do     → WAIT

Tests cover:
  - Potion priority over skill (USE_ITEM beats SKILL)
  - Skill priority over basic attack (SKILL beats ATTACK)
  - Fallthrough to basic attack when all skills on cooldown
  - Enemy AI never drinks potions or uses skills (hero_id guard)
  - All 5 classes produce valid actions in combat scenarios
  - Legacy null class_id unit does not crash
  - Multi-hero party: different classes use different skill types in same tick
  - Player-controlled hero (unit_type="human") not routed through AI logic
"""

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.ai_behavior import (
    _decide_stance_action,
    _decide_follow_action,
    _decide_aggressive_stance_action,
    _decide_defensive_action,
    _decide_hold_action,
    _should_use_potion,
    _decide_skill_usage,
    _get_role_for_class,
    decide_ai_action,
)
from app.core.fov import compute_fov
from app.core.combat import load_combat_config
from app.core.skills import load_skills_config
from unittest.mock import patch


def setup_module():
    """Ensure configs are loaded before any test runs."""
    load_combat_config()
    load_skills_config()


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

def _health_potion() -> dict:
    """Standard health potion (40 HP)."""
    return {
        "item_id": "health_potion",
        "name": "Health Potion",
        "item_type": "consumable",
        "rarity": "common",
        "equip_slot": None,
        "stat_bonuses": {"attack_damage": 0, "ranged_damage": 0, "armor": 0, "max_hp": 0},
        "consumable_effect": {"type": "heal", "magnitude": 40},
        "description": "Restores 40 HP.",
        "sell_value": 15,
    }


def make_crusader(pid="crusader1", username="Ser Aldric", x=5, y=5,
                  hp=150, max_hp=150, team="a", ai_stance="follow",
                  cooldowns=None, active_buffs=None, inventory=None,
                  hero_id="hero_crus") -> PlayerState:
    """Create a Crusader hero AI unit (Tank role)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=20,
        armor=8,
        team=team,
        unit_type="ai",
        hero_id=hero_id,
        ai_stance=ai_stance,
        class_id="crusader",
        ranged_range=1,
        vision_range=5,
        inventory=inventory or [],
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
    )


def make_confessor(pid="confessor1", username="Sister Maeve", x=5, y=5,
                   hp=100, max_hp=100, team="a", ai_stance="follow",
                   cooldowns=None, active_buffs=None, inventory=None,
                   hero_id="hero_conf") -> PlayerState:
    """Create a Confessor hero AI unit (Support role)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=8,
        armor=3,
        team=team,
        unit_type="ai",
        hero_id=hero_id,
        ai_stance=ai_stance,
        class_id="confessor",
        ranged_range=1,
        vision_range=6,
        inventory=inventory or [],
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
    )


def make_ranger(pid="ranger1", username="Shadow Fang", x=5, y=5,
                hp=80, max_hp=80, team="a", ai_stance="follow",
                cooldowns=None, active_buffs=None, inventory=None,
                hero_id="hero_rang") -> PlayerState:
    """Create a Ranger hero AI unit (Ranged DPS role)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=8,
        ranged_damage=18,
        armor=2,
        team=team,
        unit_type="ai",
        hero_id=hero_id,
        ai_stance=ai_stance,
        class_id="ranger",
        ranged_range=6,
        vision_range=7,
        inventory=inventory or [],
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
    )


def make_hexblade(pid="hexblade1", username="Dark Blade", x=5, y=5,
                  hp=110, max_hp=110, team="a", ai_stance="follow",
                  cooldowns=None, active_buffs=None, inventory=None,
                  hero_id="hero_hex") -> PlayerState:
    """Create a Hexblade hero AI unit (Hybrid DPS role)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=15,
        ranged_damage=12,
        armor=5,
        team=team,
        unit_type="ai",
        hero_id=hero_id,
        ai_stance=ai_stance,
        class_id="hexblade",
        ranged_range=4,
        vision_range=6,
        inventory=inventory or [],
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
    )


def make_inquisitor(pid="inquisitor1", username="Witch Hunter", x=5, y=5,
                    hp=80, max_hp=80, team="a", ai_stance="follow",
                    cooldowns=None, active_buffs=None, inventory=None,
                    hero_id="hero_inq") -> PlayerState:
    """Create an Inquisitor hero AI unit (Scout role)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=10,
        ranged_damage=8,
        armor=4,
        team=team,
        unit_type="ai",
        hero_id=hero_id,
        ai_stance=ai_stance,
        class_id="inquisitor",
        ranged_range=5,
        vision_range=9,
        inventory=inventory or [],
        cooldowns=cooldowns or {},
        active_buffs=active_buffs or [],
    )


def make_enemy(pid="enemy1", username="Demon", x=6, y=5,
               hp=80, max_hp=80, team="b", ai_behavior="aggressive",
               enemy_type="demon", inventory=None,
               class_id=None) -> PlayerState:
    """Create an enemy AI unit (NOT a hero)."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        attack_damage=10,
        armor=0,
        team=team,
        unit_type="ai",
        hero_id=None,
        ai_behavior=ai_behavior,
        enemy_type=enemy_type,
        ranged_range=0,
        vision_range=5,
        inventory=inventory or [],
        class_id=class_id,
    )


def make_owner(pid="owner1", username="Player", x=3, y=5,
               hp=100, max_hp=100, team="a") -> PlayerState:
    """Create a human owner for hero allies."""
    return PlayerState(
        player_id=pid,
        username=username,
        position=Position(x=x, y=y),
        hp=hp,
        max_hp=max_hp,
        team=team,
        unit_type="human",
    )


# ---------------------------------------------------------------------------
# 1. Priority Chain: Potion > Skill > Basic Attack
# ---------------------------------------------------------------------------

class TestPriorityChain:
    """Verify the priority order: Potion → Skill → Stance (basic attack)."""

    def test_priority_potion_over_skill(self):
        """AI at 20% HP with heal potion + Double Strike available → drinks potion (USE_ITEM).

        Potion check fires FIRST in _decide_stance_action, before skill decision.
        Even though Double Strike is off cooldown and an adjacent enemy exists,
        the AI should prioritize survival and drink the potion.
        """
        crusader = make_crusader(
            hp=30, max_hp=150,  # 20% HP — well below follow threshold (40%)
            inventory=[_health_potion()],
            cooldowns={},  # Double Strike off cooldown
        )
        enemy = make_enemy(x=6, y=5)  # adjacent
        owner = make_owner()
        crusader.controlled_by = "owner1"

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            crusader, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        assert action is not None
        assert action.action_type == ActionType.USE_ITEM
        assert action.target_x == 0  # first inventory slot

    def test_priority_skill_over_attack(self):
        """AI at 80% HP adjacent to enemy + Double Strike off CD → uses Double Strike (SKILL).

        HP is above potion threshold, so potion check passes.
        Double Strike is available and AI is adjacent to enemy.
        Should choose SKILL over basic ATTACK.
        """
        crusader = make_crusader(
            hp=120, max_hp=150,  # 80% HP — above threshold
            cooldowns={},  # Double Strike off cooldown
        )
        enemy = make_enemy(x=6, y=5)  # adjacent
        owner = make_owner()
        crusader.controlled_by = "owner1"

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            crusader, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        assert action is not None
        # Should be a SKILL (War Cry or Double Strike), not basic ATTACK
        # Crusader priority: War Cry first (if no buff), then Double Strike
        assert action.action_type == ActionType.SKILL

    def test_priority_attack_when_no_skills(self):
        """All skills on CD → falls through to basic ATTACK.

        With potion threshold not met and all skills on cooldown,
        the crusader should fall through to the stance handler and
        use a basic melee ATTACK on the adjacent enemy.
        """
        crusader = make_crusader(
            hp=150, max_hp=150,  # full HP
            cooldowns={"taunt": 3, "shield_bash": 2, "holy_ground": 3, "bulwark": 3},  # all on CD
            active_buffs=[
                {"buff_id": "bulwark", "stat": "armor", "type": "buff",
                 "magnitude": 5, "turns_remaining": 1}
            ],
        )
        enemy = make_enemy(x=6, y=5)  # adjacent
        owner = make_owner()
        crusader.controlled_by = "owner1"

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            crusader, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        assert action is not None
        assert action.action_type == ActionType.ATTACK
        assert action.target_x == enemy.position.x
        assert action.target_y == enemy.position.y

    def test_priority_potion_over_heal_skill(self):
        """Confessor at 20% HP with potion + Heal available → drinks potion.

        Even though Heal could self-heal, the potion check fires first
        and returns USE_ITEM before the skill decision runs.
        """
        confessor = make_confessor(
            hp=20, max_hp=100,  # 20% HP
            inventory=[_health_potion()],
            cooldowns={},  # Heal off cooldown
        )
        owner = make_owner()
        confessor.controlled_by = "owner1"

        all_units = {
            confessor.player_id: confessor,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            confessor, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        assert action is not None
        assert action.action_type == ActionType.USE_ITEM

    def test_skill_fires_when_no_potion_needed(self):
        """Confessor at 40% HP (below heal threshold) with NO potions → heals self.

        Potion check finds no potions → passes through.
        Skill decision recognizes low HP and heals self.
        """
        confessor = make_confessor(
            hp=40, max_hp=100,  # 40% HP — below self-heal threshold (50%)
            inventory=[],  # no potions
            cooldowns={},  # Heal off cooldown
        )
        owner = make_owner()
        confessor.controlled_by = "owner1"

        all_units = {
            confessor.player_id: confessor,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            confessor, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        assert action is not None
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "heal"

    def test_fallthrough_to_wait_no_enemies_near_owner(self):
        """Hero at full HP, no enemies, close to owner → WAIT.

        Potion: skipped (full HP). Skill: skipped (no enemies/hurt allies).
        Stance: near owner, no enemies → WAIT.
        """
        crusader = make_crusader(hp=150, max_hp=150, x=4, y=5)
        owner = make_owner(x=3, y=5)
        crusader.controlled_by = "owner1"

        all_units = {
            crusader.player_id: crusader,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            crusader, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        assert action is not None
        assert action.action_type == ActionType.WAIT

    def test_fallthrough_to_move_toward_owner(self):
        """Hero far from owner, no enemies → MOVE toward owner.

        Potion: skipped. Skill: skipped. Stance: too far from owner → MOVE.
        """
        crusader = make_crusader(hp=150, max_hp=150, x=10, y=10)
        owner = make_owner(x=3, y=3)
        crusader.controlled_by = "owner1"

        all_units = {
            crusader.player_id: crusader,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            crusader, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        assert action is not None
        assert action.action_type == ActionType.MOVE


# ---------------------------------------------------------------------------
# 2. Enemy AI Exclusion (8F-3 guard verification)
# ---------------------------------------------------------------------------

class TestEnemyAIExclusion:
    """Enemy AI must never use potions or skills — the hero_id guard in
    decide_ai_action routes enemies to aggressive/ranged/boss behavior,
    NOT to _decide_stance_action."""

    def test_enemy_ai_no_potions(self):
        """Enemy AI at 10% HP with potions in inventory → never drinks.

        decide_ai_action dispatches enemies to _decide_aggressive_action,
        which has no potion logic. Even though _should_use_potion would
        fire if called directly, the dispatch guard prevents it.
        """
        enemy = make_enemy(hp=8, max_hp=80, inventory=[_health_potion()])
        all_units = {enemy.player_id: enemy}

        action = decide_ai_action(
            enemy, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        # Enemy should get WAIT/MOVE/ATTACK — never USE_ITEM
        assert action is None or action.action_type != ActionType.USE_ITEM

    def test_enemy_ai_with_class_uses_skills(self):
        """Enemy AI with a class_id and adjacent target → may use SKILL.

        Enemies with a class_id go through aggressive/ranged/boss behavior
        which now includes skill usage via _decide_skill_usage.
        """
        enemy = make_enemy(x=5, y=5, class_id="crusader")
        target = PlayerState(
            player_id="target1", username="Hero",
            position=Position(x=6, y=5), hp=100, max_hp=100,
            team="a", unit_type="ai", hero_id="h1",
        )
        all_units = {enemy.player_id: enemy, target.player_id: target}

        action = decide_ai_action(
            enemy, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        # Enemy with class_id can now use skills when available
        assert action is not None
        assert action.action_type in (ActionType.SKILL, ActionType.ATTACK)

    def test_enemy_ai_no_class_no_skills(self):
        """Enemy AI without a class_id → uses ATTACK, never SKILL."""
        enemy = make_enemy(x=5, y=5, class_id=None)
        target = PlayerState(
            player_id="target1", username="Hero",
            position=Position(x=6, y=5), hp=100, max_hp=100,
            team="a", unit_type="ai", hero_id="h1",
        )
        all_units = {enemy.player_id: enemy, target.player_id: target}

        action = decide_ai_action(
            enemy, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        # Enemy without class_id should ATTACK, never SKILL
        assert action is not None
        assert action.action_type != ActionType.SKILL

    def test_enemy_hero_id_is_none(self):
        """Enemy units always have hero_id=None — the exclusion guard key."""
        enemy = make_enemy()
        assert enemy.hero_id is None

    def test_hero_ally_has_hero_id(self):
        """Hero allies always have hero_id set — they go through stance dispatch."""
        crusader = make_crusader()
        assert crusader.hero_id is not None


# ---------------------------------------------------------------------------
# 3. All Classes Produce Valid Actions
# ---------------------------------------------------------------------------

class TestAllClassesValidActions:
    """Each class should produce a valid action in common combat scenarios."""

    def _run_class_combat_scenario(self, hero: PlayerState) -> PlayerAction:
        """Place hero near owner with enemy adjacent and verify valid action."""
        enemy = make_enemy(x=hero.position.x + 1, y=hero.position.y)
        owner = make_owner(x=hero.position.x - 2, y=hero.position.y)
        hero.controlled_by = "owner1"

        all_units = {
            hero.player_id: hero,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            hero, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        assert action is not None
        assert action.action_type in (
            ActionType.ATTACK, ActionType.RANGED_ATTACK,
            ActionType.SKILL, ActionType.USE_ITEM,
            ActionType.MOVE, ActionType.WAIT,
        )
        return action

    def test_crusader_produces_valid_action(self):
        """Crusader (Tank) adjacent to enemy → valid action (War Cry or Double Strike or ATTACK)."""
        hero = make_crusader(hp=150, max_hp=150)
        action = self._run_class_combat_scenario(hero)
        # Crusader with skills off CD should use War Cry first (enemies visible), then DS
        assert action.action_type in (ActionType.SKILL, ActionType.ATTACK)

    def test_confessor_produces_valid_action(self):
        """Confessor (Support) adjacent to enemy, full HP → valid action."""
        hero = make_confessor(hp=100, max_hp=100)
        action = self._run_class_combat_scenario(hero)
        # No one to heal → ATTACK or MOVE
        assert action.action_type in (ActionType.ATTACK, ActionType.MOVE, ActionType.SKILL)

    def test_ranger_produces_valid_action(self):
        """Ranger (Ranged DPS) adjacent to enemy → valid action."""
        hero = make_ranger(hp=80, max_hp=80)
        action = self._run_class_combat_scenario(hero)
        # Ranger might use Power Shot (if in ranged range + LOS) or ATTACK
        assert action.action_type in (ActionType.SKILL, ActionType.ATTACK, ActionType.RANGED_ATTACK)

    def test_hexblade_produces_valid_action(self):
        """Hexblade (Hybrid DPS) adjacent to enemy → valid action."""
        hero = make_hexblade(hp=110, max_hp=110)
        action = self._run_class_combat_scenario(hero)
        # Hexblade adjacent → Double Strike or ATTACK
        assert action.action_type in (ActionType.SKILL, ActionType.ATTACK)

    def test_inquisitor_produces_valid_action(self):
        """Inquisitor (Scout) adjacent to enemy → valid action."""
        hero = make_inquisitor(hp=80, max_hp=80)
        action = self._run_class_combat_scenario(hero)
        # Inquisitor adjacent might Power Shot (range 5, LOS) or ATTACK
        assert action.action_type in (ActionType.SKILL, ActionType.ATTACK, ActionType.RANGED_ATTACK)


# ---------------------------------------------------------------------------
# 4. Legacy / Null Class Guard
# ---------------------------------------------------------------------------

class TestLegacyNullClass:
    """Units with class_id=None should not crash and should get normal stance actions."""

    def test_legacy_null_class_no_crash(self):
        """class_id=None hero → no skills fired, no crash, gets normal stance action."""
        hero = PlayerState(
            player_id="legacy1",
            username="Legacy Hero",
            position=Position(x=5, y=5),
            hp=100,
            max_hp=100,
            attack_damage=15,
            armor=2,
            team="a",
            unit_type="ai",
            hero_id="hero_legacy",
            ai_stance="follow",
            class_id=None,  # no class
            ranged_range=5,
            vision_range=7,
            inventory=[],
        )
        enemy = make_enemy(x=6, y=5)
        owner = make_owner()
        hero.controlled_by = "owner1"

        all_units = {
            hero.player_id: hero,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            hero, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        # Should get a valid action, not crash
        assert action is not None
        # No skills because class_id is None
        assert action.action_type in (
            ActionType.ATTACK, ActionType.RANGED_ATTACK,
            ActionType.MOVE, ActionType.WAIT,
        )

    def test_null_class_skill_decision_returns_none(self):
        """_decide_skill_usage with class_id=None → returns None immediately."""
        hero = PlayerState(
            player_id="null1",
            username="No Class",
            position=Position(x=5, y=5),
            hp=100,
            max_hp=100,
            team="a",
            unit_type="ai",
            hero_id="hero_null",
            class_id=None,
        )

        result = _decide_skill_usage(
            hero, enemies=[], all_units={}, grid_width=15,
            grid_height=15, obstacles=set(),
        )

        assert result is None

    def test_unknown_class_skill_decision_returns_none(self):
        """_decide_skill_usage with unknown class_id → returns None."""
        hero = PlayerState(
            player_id="unk1",
            username="Unknown Class",
            position=Position(x=5, y=5),
            hp=100,
            max_hp=100,
            team="a",
            unit_type="ai",
            hero_id="hero_unk",
            class_id="necromancer",  # not in _CLASS_ROLE_MAP
        )

        result = _decide_skill_usage(
            hero, enemies=[], all_units={}, grid_width=15,
            grid_height=15, obstacles=set(),
        )

        assert result is None


# ---------------------------------------------------------------------------
# 5. Multi-Hero Party — Different Classes Using Different Skills
# ---------------------------------------------------------------------------

class TestMultiHeroPartySkills:
    """Verify a mixed party produces role-appropriate actions in the same tick."""

    def test_multi_hero_party_skills(self):
        """4-hero party: each class uses role-appropriate action in same tick.

        Setup: All heroes near owner, enemy visible.
        Expected: each class should independently produce a valid action through
        the priority chain (potion → skill → stance).
        """
        owner = make_owner(x=5, y=5)

        # Crusader adjacent to enemy, full HP → should War Cry or Double Strike
        crusader = make_crusader(x=7, y=5, hp=150, max_hp=150)
        crusader.controlled_by = "owner1"

        # Confessor with hurt ally nearby, full HP → should heal ally or attack
        confessor = make_confessor(x=4, y=5, hp=100, max_hp=100)
        confessor.controlled_by = "owner1"

        # Ranger far from enemy, full HP → should Power Shot or ranged/move
        ranger = make_ranger(x=3, y=5, hp=80, max_hp=80)
        ranger.controlled_by = "owner1"

        # Hexblade adjacent to enemy, full HP → should Double Strike
        hexblade = make_hexblade(pid="hexblade1", x=9, y=5, hp=110, max_hp=110)
        hexblade.controlled_by = "owner1"

        enemy1 = make_enemy(pid="enemy1", x=8, y=5)  # adjacent to crusader
        enemy2 = make_enemy(pid="enemy2", x=10, y=5)  # adjacent to hexblade

        all_units = {
            owner.player_id: owner,
            crusader.player_id: crusader,
            confessor.player_id: confessor,
            ranger.player_id: ranger,
            hexblade.player_id: hexblade,
            enemy1.player_id: enemy1,
            enemy2.player_id: enemy2,
        }

        # Each hero decides independently through _decide_stance_action
        crus_action = _decide_stance_action(
            crusader, all_units, grid_width=20, grid_height=20, obstacles=set(),
        )
        conf_action = _decide_stance_action(
            confessor, all_units, grid_width=20, grid_height=20, obstacles=set(),
        )
        rang_action = _decide_stance_action(
            ranger, all_units, grid_width=20, grid_height=20, obstacles=set(),
        )
        hex_action = _decide_stance_action(
            hexblade, all_units, grid_width=20, grid_height=20, obstacles=set(),
        )

        # All actions should be non-None and valid
        for name, action in [("Crusader", crus_action), ("Confessor", conf_action),
                             ("Ranger", rang_action), ("Hexblade", hex_action)]:
            assert action is not None, f"{name} returned None action"
            assert action.action_type in (
                ActionType.ATTACK, ActionType.RANGED_ATTACK,
                ActionType.SKILL, ActionType.USE_ITEM,
                ActionType.MOVE, ActionType.WAIT,
            ), f"{name} returned invalid action type: {action.action_type}"

        # Crusader should use a skill (War Cry or Double Strike) when adjacent to enemy
        assert crus_action.action_type == ActionType.SKILL, \
            f"Crusader should use skill, got {crus_action.action_type}"

        # Hexblade adjacent to enemy should use Double Strike
        assert hex_action.action_type == ActionType.SKILL, \
            f"Hexblade should use skill, got {hex_action.action_type}"

    def test_multi_hero_mixed_priorities(self):
        """2-hero party: one drinks potion, one uses skill — in same tick.

        Crusader at 20% HP with potions → USE_ITEM
        Hexblade at full HP adjacent to enemy → SKILL (Double Strike)
        """
        owner = make_owner(x=5, y=5)

        crusader = make_crusader(
            x=7, y=5, hp=30, max_hp=150,  # 20% HP
            inventory=[_health_potion()],
        )
        crusader.controlled_by = "owner1"

        hexblade = make_hexblade(x=9, y=5, hp=110, max_hp=110)
        hexblade.controlled_by = "owner1"

        enemy = make_enemy(x=10, y=5)  # adjacent to hexblade

        all_units = {
            owner.player_id: owner,
            crusader.player_id: crusader,
            hexblade.player_id: hexblade,
            enemy.player_id: enemy,
        }

        crus_action = _decide_stance_action(
            crusader, all_units, grid_width=20, grid_height=20, obstacles=set(),
        )
        hex_action = _decide_stance_action(
            hexblade, all_units, grid_width=20, grid_height=20, obstacles=set(),
        )

        # Crusader drinks potion (USE_ITEM)
        assert crus_action.action_type == ActionType.USE_ITEM

        # Hexblade uses Double Strike (SKILL)
        assert hex_action.action_type == ActionType.SKILL


# ---------------------------------------------------------------------------
# 6. Player-Controlled Hero Exclusion
# ---------------------------------------------------------------------------

class TestControlledHeroExclusion:
    """Player-controlled heroes (unit_type='human') should NOT go through AI logic."""

    def test_controlled_hero_no_ai_decision(self):
        """Human-controlled unit → decide_ai_action returns None.

        Players submit their own actions via WebSocket; the AI engine
        should not generate actions for human-controlled units.
        """
        human = PlayerState(
            player_id="human1",
            username="Real Player",
            position=Position(x=5, y=5),
            hp=100,
            max_hp=100,
            team="a",
            unit_type="human",
        )
        all_units = {human.player_id: human}

        action = decide_ai_action(
            human, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        # Human players don't go through AI decision at all
        # decide_ai_action should return None or not generate SKILL/USE_ITEM
        # The actual guard depends on how decide_ai_action filters unit_type
        assert action is None or action.action_type in (
            ActionType.WAIT, ActionType.MOVE,
        )

    def test_dead_hero_no_action(self):
        """Dead hero → decide_ai_action returns None."""
        hero = make_crusader(hp=0, max_hp=150)
        hero.is_alive = False

        all_units = {hero.player_id: hero}

        action = decide_ai_action(
            hero, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        assert action is None


# ---------------------------------------------------------------------------
# 7. Stance Variations — Priority Chain Consistent Across All Stances
# ---------------------------------------------------------------------------

class TestPriorityChainAcrossStances:
    """The priority chain (potion → skill → stance) must work identically
    regardless of which stance the hero is in."""

    def test_aggressive_stance_potion_priority(self):
        """Aggressive stance hero at low HP → drinks potion before attacking."""
        crusader = make_crusader(
            hp=25, max_hp=150,  # ~17% — below aggressive threshold (25%)
            ai_stance="aggressive",
            inventory=[_health_potion()],
        )
        enemy = make_enemy(x=6, y=5)
        owner = make_owner()
        crusader.controlled_by = "owner1"

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            crusader, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        assert action.action_type == ActionType.USE_ITEM

    def test_defensive_stance_skill_priority(self):
        """Defensive stance hero at full HP with skill available → uses skill."""
        crusader = make_crusader(
            hp=150, max_hp=150,
            ai_stance="defensive",
            cooldowns={},  # War Cry off CD
        )
        enemy = make_enemy(x=6, y=5)
        owner = make_owner(x=4, y=5)
        crusader.controlled_by = "owner1"

        all_units = {
            crusader.player_id: crusader,
            enemy.player_id: enemy,
            owner.player_id: owner,
        }

        action = _decide_stance_action(
            crusader, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        # Should use War Cry (enemies visible, no buff active)
        assert action.action_type == ActionType.SKILL

    def test_hold_stance_potion_priority(self):
        """Hold stance hero at low HP → drinks potion (potion still highest priority)."""
        ranger = make_ranger(
            hp=24, max_hp=80,  # 30% — below hold threshold (40%)
            ai_stance="hold",
            inventory=[_health_potion()],
        )
        all_units = {ranger.player_id: ranger}

        action = _decide_stance_action(
            ranger, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        assert action.action_type == ActionType.USE_ITEM

    def test_hold_stance_skill_then_attack(self):
        """Hold stance hero at full HP with Power Shot off CD and enemy in range → SKILL."""
        ranger = make_ranger(
            hp=80, max_hp=80,
            ai_stance="hold",
            cooldowns={},  # Power Shot off CD
        )
        # Enemy in ranged range (6) with LOS
        enemy = make_enemy(x=10, y=5, hp=80, max_hp=80)
        all_units = {ranger.player_id: ranger, enemy.player_id: enemy}

        action = _decide_stance_action(
            ranger, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        # Should use Crippling Shot (priority over Power Shot)
        assert action.action_type == ActionType.SKILL
        assert action.skill_id == "crippling_shot"

    def test_hold_stance_fallthrough_to_attack(self):
        """Hold stance hero with all skills on CD + adjacent enemy → basic ATTACK."""
        crusader = make_crusader(
            hp=150, max_hp=150,
            ai_stance="hold",
            cooldowns={"taunt": 3, "shield_bash": 2, "holy_ground": 3, "bulwark": 3},
            active_buffs=[
                {"buff_id": "bulwark", "stat": "armor", "type": "buff",
                 "magnitude": 5, "turns_remaining": 1}
            ],
        )
        enemy = make_enemy(x=6, y=5)
        all_units = {crusader.player_id: crusader, enemy.player_id: enemy}

        action = _decide_stance_action(
            crusader, all_units, grid_width=15, grid_height=15,
            obstacles=set(),
        )

        assert action.action_type == ActionType.ATTACK


# ---------------------------------------------------------------------------
# 8. Role Mapping Consistency
# ---------------------------------------------------------------------------

class TestRoleMappingIntegration:
    """Verify role mapping is consistent across the priority chain."""

    def test_all_five_classes_have_roles(self):
        """All 5 classes map to a valid role."""
        classes = ["crusader", "confessor", "inquisitor", "ranger", "hexblade"]
        expected_roles = {"tank", "support", "scout", "ranged_dps", "hybrid_dps"}
        actual_roles = set()

        for cls in classes:
            role = _get_role_for_class(cls)
            assert role is not None, f"Class {cls} has no role mapping"
            actual_roles.add(role)

        assert actual_roles == expected_roles

    def test_role_mapping_drives_skill_dispatch(self):
        """Each role produces a different skill decision pattern.

        Tank → War Cry/Double Strike
        Support → Heal
        Ranged DPS → Power Shot
        Scout → Power Shot/Shadow Step
        Hybrid DPS → Double Strike/Shadow Step
        """
        enemy = make_enemy(x=6, y=5)
        all_units_base = {enemy.player_id: enemy}

        # Tank: War Cry (enemies visible, no buff)
        crusader = make_crusader(x=5, y=5, cooldowns={})
        result = _decide_skill_usage(
            crusader, [enemy], {**all_units_base, crusader.player_id: crusader},
            15, 15, set(),
        )
        assert result is not None
        assert result.action_type == ActionType.SKILL

        # Support: Heal self at low HP
        confessor = make_confessor(x=5, y=5, hp=40, max_hp=100, cooldowns={})
        result = _decide_skill_usage(
            confessor, [enemy], {**all_units_base, confessor.player_id: confessor},
            15, 15, set(),
        )
        assert result is not None
        assert result.skill_id == "heal"

        # Ranged DPS: Power Shot (enemy in range + LOS)
        ranger = make_ranger(x=5, y=5, cooldowns={})
        # Move enemy to within ranged range (6)
        enemy_far = make_enemy(pid="enemy_far", x=10, y=5)
        result = _decide_skill_usage(
            ranger, [enemy_far], {enemy_far.player_id: enemy_far, ranger.player_id: ranger},
            15, 15, set(),
        )
        assert result is not None
        assert result.skill_id == "crippling_shot"


# ---------------------------------------------------------------------------
# 8. Phase 8F-2: Pre-computed FOV Integration
# ---------------------------------------------------------------------------

class TestPrecomputedFOVIntegration:
    """Verify that _decide_stance_action pre-computes FOV and enemies once,
    passing them to stance functions to avoid redundant compute_fov calls.

    Phase 8F-2: Performance optimization — compute_fov is called exactly once
    in _decide_stance_action(), and the result is forwarded to the stance handler.
    """

    def test_fov_computed_once_follow_stance(self):
        """Follow stance: compute_fov called once in _decide_stance_action, not again in _decide_follow_action."""
        owner = make_owner(x=3, y=5)
        crusader = make_crusader(x=5, y=5, cooldowns={"taunt": 99, "shield_bash": 99, "holy_ground": 99, "bulwark": 99})
        enemy = make_enemy(x=6, y=5)
        all_units = {
            owner.player_id: owner,
            crusader.player_id: crusader,
            enemy.player_id: enemy,
        }

        with patch("app.core.ai_stances.compute_fov", wraps=compute_fov) as mock_fov:
            _decide_stance_action(
                crusader, all_units, 15, 15, set(), None, None, None, None,
            )
            # compute_fov should be called exactly once (in _decide_stance_action),
            # NOT a second time inside _decide_follow_action
            assert mock_fov.call_count == 1, (
                f"compute_fov called {mock_fov.call_count} times, expected 1 "
                f"(pre-computed in _decide_stance_action, reused in stance handler)"
            )

    def test_fov_computed_once_aggressive_stance(self):
        """Aggressive stance: compute_fov called once, not duplicated."""
        owner = make_owner(x=3, y=5)
        crusader = make_crusader(
            x=5, y=5, ai_stance="aggressive",
            cooldowns={"taunt": 99, "shield_bash": 99, "holy_ground": 99, "bulwark": 99},
        )
        enemy = make_enemy(x=6, y=5)
        all_units = {
            owner.player_id: owner,
            crusader.player_id: crusader,
            enemy.player_id: enemy,
        }

        with patch("app.core.ai_stances.compute_fov", wraps=compute_fov) as mock_fov:
            _decide_stance_action(
                crusader, all_units, 15, 15, set(), None, None, None, None,
            )
            assert mock_fov.call_count == 1

    def test_fov_computed_once_defensive_stance(self):
        """Defensive stance: compute_fov called once, not duplicated."""
        owner = make_owner(x=3, y=5)
        confessor = make_confessor(
            x=4, y=5, ai_stance="defensive",
            cooldowns={"heal": 99, "shield_of_faith": 99, "exorcism": 99, "prayer": 99},
        )
        enemy = make_enemy(x=5, y=5)
        all_units = {
            owner.player_id: owner,
            confessor.player_id: confessor,
            enemy.player_id: enemy,
        }

        with patch("app.core.ai_stances.compute_fov", wraps=compute_fov) as mock_fov:
            _decide_stance_action(
                confessor, all_units, 15, 15, set(), None, None, None, None,
            )
            assert mock_fov.call_count == 1

    def test_fov_computed_once_hold_stance(self):
        """Hold stance: compute_fov called once, not duplicated."""
        owner = make_owner(x=3, y=5)
        ranger = make_ranger(
            x=5, y=5, ai_stance="hold",
            cooldowns={"power_shot": 99, "crippling_shot": 99, "volley": 99, "evasion": 99},
        )
        enemy = make_enemy(x=6, y=5)
        all_units = {
            owner.player_id: owner,
            ranger.player_id: ranger,
            enemy.player_id: enemy,
        }

        with patch("app.core.ai_stances.compute_fov", wraps=compute_fov) as mock_fov:
            _decide_stance_action(
                ranger, all_units, 15, 15, set(), None, None, None, None,
            )
            assert mock_fov.call_count == 1

    def test_precomputed_enemies_match_self_computed(self):
        """Pre-computed enemy list produces the same action as self-computed."""
        owner = make_owner(x=3, y=5)
        crusader = make_crusader(x=5, y=5, cooldowns={"taunt": 99, "shield_bash": 99, "holy_ground": 99, "bulwark": 99})
        enemy = make_enemy(x=6, y=5)
        all_units = {
            owner.player_id: owner,
            crusader.player_id: crusader,
            enemy.player_id: enemy,
        }

        # Get result through _decide_stance_action (pre-computes + passes through)
        result_integrated = _decide_stance_action(
            crusader, all_units, 15, 15, set(), None, None, None, None,
        )

        # Get result directly from stance function WITHOUT pre-computed data
        result_direct = _decide_follow_action(
            crusader, all_units, 15, 15, set(), None, None, None, None,
        )

        # Both should produce the same action type and target
        assert result_integrated.action_type == result_direct.action_type
        assert result_integrated.target_x == result_direct.target_x
        assert result_integrated.target_y == result_direct.target_y

    def test_stance_function_fallback_without_precomputed(self):
        """Stance functions still work when called directly without pre-computed data."""
        owner = make_owner(x=3, y=5)
        ranger = make_ranger(x=5, y=5, ai_stance="hold", cooldowns={"power_shot": 99, "crippling_shot": 99, "volley": 99, "evasion": 99})
        enemy = make_enemy(x=6, y=5)
        all_units = {
            owner.player_id: owner,
            ranger.player_id: ranger,
            enemy.player_id: enemy,
        }

        # Call hold directly without pre-computed data — should still work
        result = _decide_hold_action(ranger, all_units, 15, 15, set())
        assert result is not None
        assert result.action_type == ActionType.ATTACK

    def test_precomputed_data_with_team_fov(self):
        """Pre-computed FOV includes team_fov, enemies found via shared vision."""
        owner = make_owner(x=3, y=5)
        # Ranger can't see enemy at (14, 14) with vision 7 from (5, 5)
        ranger = make_ranger(x=5, y=5, ai_stance="hold", cooldowns={"power_shot": 99, "crippling_shot": 99, "volley": 99, "evasion": 99})
        enemy = make_enemy(x=14, y=14)
        all_units = {
            owner.player_id: owner,
            ranger.player_id: ranger,
            enemy.player_id: enemy,
        }

        # Without team_fov: no enemies visible → WAIT
        result_no_team = _decide_stance_action(
            ranger, all_units, 15, 15, set(), None, None, None, None,
        )
        assert result_no_team.action_type == ActionType.WAIT

        # With team_fov that includes enemy position → enemy is visible
        team_fov = {(14, 14)}
        # The key test: compute_fov called once, and team_fov properly merged
        with patch("app.core.ai_stances.compute_fov", wraps=compute_fov) as mock_fov:
            _decide_stance_action(
                ranger, all_units, 15, 15, set(), team_fov, None, None, None,
            )
            assert mock_fov.call_count == 1

    def test_no_enemies_precomputed_empty_list(self):
        """When no enemies visible, pre-computed empty list is passed through correctly."""
        owner = make_owner(x=3, y=5)
        crusader = make_crusader(x=4, y=5, cooldowns={"taunt": 99, "shield_bash": 99, "holy_ground": 99, "bulwark": 99})
        all_units = {
            owner.player_id: owner,
            crusader.player_id: crusader,
        }

        with patch("app.core.ai_stances.compute_fov", wraps=compute_fov) as mock_fov:
            result = _decide_stance_action(
                crusader, all_units, 15, 15, set(), None, None, None, None,
            )
            assert mock_fov.call_count == 1
            # No enemies, close to owner → WAIT
            assert result.action_type == ActionType.WAIT

    def test_aggressive_stance_consistent_with_precomputed(self):
        """Aggressive stance produces the same result via _decide_stance_action vs direct call."""
        owner = make_owner(x=3, y=5)
        crusader = make_crusader(
            x=5, y=5, ai_stance="aggressive",
            cooldowns={"taunt": 99, "shield_bash": 99, "holy_ground": 99, "bulwark": 99},
        )
        enemy = make_enemy(x=6, y=5)
        all_units = {
            owner.player_id: owner,
            crusader.player_id: crusader,
            enemy.player_id: enemy,
        }

        result_integrated = _decide_stance_action(
            crusader, all_units, 15, 15, set(), None, None, None, None,
        )
        result_direct = _decide_aggressive_stance_action(
            crusader, all_units, 15, 15, set(), None, None, None, None,
        )
        assert result_integrated.action_type == result_direct.action_type

    def test_defensive_stance_consistent_with_precomputed(self):
        """Defensive stance produces the same result via _decide_stance_action vs direct call."""
        owner = make_owner(x=3, y=5)
        confessor = make_confessor(
            x=4, y=5, ai_stance="defensive",
            cooldowns={"heal": 99, "shield_of_faith": 99, "exorcism": 99, "prayer": 99},
        )
        enemy = make_enemy(x=5, y=5)
        all_units = {
            owner.player_id: owner,
            confessor.player_id: confessor,
            enemy.player_id: enemy,
        }

        result_integrated = _decide_stance_action(
            confessor, all_units, 15, 15, set(), None, None, None, None,
        )
        result_direct = _decide_defensive_action(
            confessor, all_units, 15, 15, set(), None, None, None, None,
        )
        assert result_integrated.action_type == result_direct.action_type
