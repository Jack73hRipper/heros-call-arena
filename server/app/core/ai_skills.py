"""
AI Skill Decision Framework — Role-specific skill handlers for AI combatants.

Extracted from ai_behavior.py (P1 refactoring — pure mechanical move).

Implements:
  - Role mapping (class_id → AI behavior role)
  - Support healing logic (Phase 8C)
  - Tank buff/double-strike logic (Phase 8D)
  - Ranged DPS power shot logic (Phase 8E-1)
  - Scout power shot + shadow step logic (Phase 8E-2)
  - Hybrid DPS gap-close logic (Phase 8E-3)
  - Skill dispatch (_decide_skill_usage)
"""

from __future__ import annotations

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.fov import has_line_of_sight
from app.core.combat import is_adjacent, is_in_range, get_combat_config
from app.core.skills import can_use_skill, get_skill


# ---------------------------------------------------------------------------
# Phase 8C: Support AI — Heal thresholds
# ---------------------------------------------------------------------------
_HEAL_SELF_THRESHOLD = 0.50    # Support heals self below 50% HP
_HEAL_ALLY_THRESHOLD = 0.60    # Support heals allies below 60% HP

# Out-of-combat thresholds — when no enemies are visible, healers top off
_HEAL_SELF_OOC_THRESHOLD = 0.95   # Self-heal when below 95% HP out of combat
_HEAL_ALLY_OOC_THRESHOLD = 0.95   # Heal allies below 95% HP out of combat

# Reposition threshold — support repositions toward out-of-range allies above
# this HP%.  Higher than _HEAL_ALLY_THRESHOLD so the support starts moving
# BEFORE the ally drops into critical territory.
_REPOSITION_ALLY_THRESHOLD = 0.80

# Tank role set — classes the support should proactively stay near
_TANK_ROLES: set[str] = {"tank", "retaliation_tank", "sustain_dps"}
_SUPPORT_HEAL_RANGE = 3   # heal skill range — used for tank-proximity checks

# Support role set — used to prevent supports from targeting each other as
# movement anchors, which causes clumping and tile-swap oscillation when
# multiple supports are in the same party.
_SUPPORT_ROLES: set[str] = {"support", "offensive_support", "totemic_support"}

# ---------------------------------------------------------------------------
# Phase 8E-2: Scout AI — Shadow Step thresholds
# ---------------------------------------------------------------------------
_SHADOW_STEP_ESCAPE_HP_THRESHOLD = 0.40   # Below 40% HP, scouts escape with Shadow Step
_SHADOW_STEP_OFFENSIVE_MIN_DISTANCE = 4   # Enemies this far trigger offensive Shadow Step

# ---------------------------------------------------------------------------
# Phase 8E-3: Hybrid DPS gap-close distance threshold
# ---------------------------------------------------------------------------
_SHADOW_STEP_GAPCLOSER_MIN_DISTANCE = 2  # Enemies this far trigger gap-close Shadow Step


# ---------------------------------------------------------------------------
# Phase 8B: AI Skill Decision Framework — Role mapping & helpers
# ---------------------------------------------------------------------------
# Map class_id → AI behavior role. New classes just need an entry here;
# role handlers are reusable across any class that shares the same role.
_CLASS_ROLE_MAP: dict[str, str] = {
    "crusader": "tank",
    "confessor": "support",
    "inquisitor": "scout",
    "ranger": "ranged_dps",
    "hexblade": "hybrid_dps",
    # Enemy classes — map to existing role handlers that match their skill sets
    "wraith": "hybrid_dps",          # wither + shadow_step (same kit as hexblade)
    "medusa": "ranged_dps",          # venom_gaze (dot) + power_shot
    "acolyte": "support",            # heal + profane_ward (Phase 18I: defensive sustain)
    "werewolf": "tank",              # war_cry + double_strike (same kit as crusader)
    "reaper": "hybrid_dps",          # wither + soul_reap (ranged damage)
    "construct": "tank",             # ward (durable self-buffer)
    # Phase 13 — Enemy Skill Expansion (11 new entries)
    "necromancer": "hybrid_dps",     # wither + soul_reap (death mage boss)
    "demon_lord": "tank",            # war_cry + double_strike (overlord boss)
    "construct_guardian": "tank",    # ward + bulwark (arcane tank boss)
    "undead_knight": "tank",         # shield_bash + bulwark (room guardian boss)
    "demon_knight": "tank",          # war_cry (armored demon elite)
    "imp_lord": "tank",              # war_cry (imp commander elite)
    "horror": "hybrid_dps",          # shadow_step + wither (aberration elite)
    "ghoul": "tank",                 # double_strike (fast undead melee)
    "skeleton": "ranged_dps",        # evasion + bone_shield (Phase 18I: ranged sniper with absorb shield)
    "undead_caster": "hybrid_dps",   # wither (skeleton mage)
    "shade": "hybrid_dps",           # shadow_step (shadow creature)
    # Phase 17: Mage class
    "mage": "caster_dps",              # fireball, frost_nova, arcane_barrage, blink
    # Phase 18I: New enemy identity classes
    "demon_enrage": "passive_only",    # enrage (passive — no active skill needed)
    "imp_frenzy": "passive_only",      # frenzy_aura (passive — no active skill needed)
    "dark_priest": "support",          # heal + dark_pact (offensive enabler)
    # Phase 21: Bard class
    "bard": "offensive_support",       # ballad_of_might, dirge_of_weakness, verse_of_haste, cacophony
    # Phase 22: Blood Knight class
    "blood_knight": "sustain_dps",     # blood_strike, crimson_veil, sanguine_burst, blood_frenzy
    # Phase 23: Plague Doctor class
    "plague_doctor": "controller",      # miasma, plague_flask, enfeeble, inoculate
    # Phase 25: Revenant class
    "revenant": "retaliation_tank",      # grave_thorns, grave_chains, undying_will, soul_rend
    # Phase 26: Shaman class
    "shaman": "totemic_support",           # healing_totem, searing_totem, soul_anchor, earthgrasp
}


def _get_role_for_class(class_id: str) -> str | None:
    """Get the AI behavior role for a class. None = no special skill logic."""
    return _CLASS_ROLE_MAP.get(class_id)


def _try_skill(
    ai: PlayerState,
    skill_id: str,
    target_x: int | None = None,
    target_y: int | None = None,
    target_id: str | None = None,
) -> PlayerAction | None:
    """Attempt to build a SKILL action if the skill is usable.

    Wraps the existing can_use_skill() validation from skills.py.
    Returns PlayerAction(SKILL) if the skill passes validation, else None.
    """
    can_use, _reason = can_use_skill(ai, skill_id)
    if not can_use:
        return None
    return PlayerAction(
        player_id=ai.player_id,
        action_type=ActionType.SKILL,
        skill_id=skill_id,
        target_x=target_x,
        target_y=target_y,
        target_id=target_id,
    )


def _chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Chebyshev distance between two points."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


# ---------------------------------------------------------------------------
# Phase 8B: Role-Specific Skill Handlers
# ---------------------------------------------------------------------------

def _support_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Support role AI: prioritize healing, then buffing, then offense.

    Phase 8C + Phase 11 implementation.
    Out-of-combat top-off: when no enemies are visible, uses relaxed
    thresholds (95%) so the healer tops party members off between fights.

    Priority:
    1. Heal self if below threshold (50% in combat, 95% out of combat)
    2. Heal ally with lowest HP% within heal range if below threshold
    3. Prayer (HoT) on most injured ally if Heal is on cooldown and ally below threshold
    4. Shield of Faith on most injured frontline ally (tank/melee)
    5. Exorcism on Undead/Demon enemy in range (holy bonus damage)
    6. Exorcism on any enemy in range (standard damage)
    7. Return None → fall through to basic attack logic
    """
    ai_pos = (ai.position.x, ai.position.y)

    # Determine thresholds: relaxed when out of combat (no visible enemies)
    in_combat = len(enemies) > 0
    self_threshold = _HEAL_SELF_THRESHOLD if in_combat else _HEAL_SELF_OOC_THRESHOLD
    ally_threshold = _HEAL_ALLY_THRESHOLD if in_combat else _HEAL_ALLY_OOC_THRESHOLD

    # --- Priority 1 & 2: Instant Heal (self then allies) ---
    heal_action_base = _try_skill(ai, "heal")
    if heal_action_base is not None:
        heal_def = get_skill("heal")
        heal_range = heal_def["range"] if heal_def else 3

        # Self-heal if below threshold
        if ai.hp / ai.max_hp < self_threshold and ai.hp < ai.max_hp:
            return _try_skill(ai, "heal", target_x=ai.position.x, target_y=ai.position.y, target_id=ai.player_id)

        # Heal most injured ally
        heal_candidates = _find_heal_candidates(ai, all_units, heal_range, threshold=ally_threshold)
        if heal_candidates:
            target = heal_candidates[0]
            return _try_skill(ai, "heal", target_x=target.position.x, target_y=target.position.y, target_id=target.player_id)

    # --- Priority 3: Prayer (HoT) if Heal is on cooldown ---
    prayer_action = _try_skill(ai, "prayer")
    if prayer_action is not None:
        prayer_def = get_skill("prayer")
        prayer_range = prayer_def["range"] if prayer_def else 4

        # Self-prayer if below threshold
        if ai.hp / ai.max_hp < self_threshold and ai.hp < ai.max_hp:
            # Don't stack — check for existing HoT
            has_hot = any(b.get("buff_id") == "prayer" for b in ai.active_buffs)
            if not has_hot:
                return _try_skill(ai, "prayer", target_x=ai.position.x, target_y=ai.position.y, target_id=ai.player_id)

        # Prayer on most injured ally
        prayer_candidates = _find_heal_candidates(ai, all_units, prayer_range, threshold=ally_threshold)
        for c in prayer_candidates:
            has_hot = any(b.get("buff_id") == "prayer" for b in c.active_buffs)
            if not has_hot:
                return _try_skill(ai, "prayer", target_x=c.position.x, target_y=c.position.y, target_id=c.player_id)

    # --- Priority 4: Dark Pact / Profane Ward on ally ---
    # NOTE: Shield of Faith moved AFTER reposition check (Priority 4.7)
    # so it doesn't block repositioning when the tank needs healing.

    # Phase 18I: Dark Pact — buff highest-damage ally with +25% melee damage
    dp_action = _try_skill(ai, "dark_pact")
    if dp_action is not None:
        dp_def = get_skill("dark_pact")
        dp_range = dp_def["range"] if dp_def else 4
        dp_candidates: list[PlayerState] = []
        for unit in all_units.values():
            if not unit.is_alive or unit.team != ai.team:
                continue
            if unit.player_id == ai.player_id:
                continue  # Don't buff self — buff an ally
            # Don't stack — check for existing dark_pact buff
            has_dp = any(b.get("buff_id") == "dark_pact" for b in unit.active_buffs)
            if has_dp:
                continue
            dist = _chebyshev(ai_pos, (unit.position.x, unit.position.y))
            if dist <= dp_range:
                dp_candidates.append(unit)
        if dp_candidates:
            # Prefer highest attack_damage (offensive enabler)
            dp_candidates.sort(key=lambda u: u.attack_damage, reverse=True)
            target = dp_candidates[0]
            return _try_skill(ai, "dark_pact", target_x=target.position.x, target_y=target.position.y, target_id=target.player_id)

    # Phase 18I: Profane Ward — buff lowest-HP ally with 30% damage reduction
    pw_action = _try_skill(ai, "profane_ward")
    if pw_action is not None:
        pw_def = get_skill("profane_ward")
        pw_range = pw_def["range"] if pw_def else 3
        pw_candidates: list[PlayerState] = []
        for unit in all_units.values():
            if not unit.is_alive or unit.team != ai.team:
                continue
            # Don't stack — check for existing profane_ward buff
            has_pw = any(b.get("buff_id") == "profane_ward" for b in unit.active_buffs)
            if has_pw:
                continue
            dist = _chebyshev(ai_pos, (unit.position.x, unit.position.y))
            if dist <= pw_range:
                pw_candidates.append(unit)
        if pw_candidates:
            # Prefer lowest HP% (most at-risk)
            pw_candidates.sort(key=lambda u: u.hp / u.max_hp if u.max_hp > 0 else 1.0)
            target = pw_candidates[0]
            return _try_skill(ai, "profane_ward", target_x=target.position.x, target_y=target.position.y, target_id=target.player_id)

    # --- Priority 4.5: Reposition check — skip offense if ally needs healing ---
    # If an ally is injured (below reposition threshold) but out of heal/prayer
    # range, return None so the stance handler can move the support toward them.
    # Uses the higher _REPOSITION_ALLY_THRESHOLD (80%) so the support starts
    # closing distance BEFORE allies become critical.
    # Additionally, if the nearest tank-role ally is outside heal range,
    # reposition proactively even if they're healthy — staying near the tank
    # is more valuable than casting Exorcism from the back line.
    if in_combat:
        max_heal_range = 3  # heal range
        prayer_def_check = get_skill("prayer")
        if prayer_def_check:
            max_heal_range = max(max_heal_range, prayer_def_check.get("range", 4))

        # Check A: any ally below reposition threshold and out of heal range
        for unit in all_units.values():
            if not unit.is_alive or unit.player_id == ai.player_id or unit.team != ai.team:
                continue
            if unit.max_hp <= 0 or unit.hp / unit.max_hp >= _REPOSITION_ALLY_THRESHOLD:
                continue
            dist = _chebyshev(ai_pos, (unit.position.x, unit.position.y))
            if dist > max_heal_range:
                return None  # Ally below 80% and out of range — reposition

        # Check B: tank-role ally far out of heal range — close distance proactively
        # Softened: only suppress DPS when tank is well beyond heal range (> 5 tiles).
        # At 4-5 tiles the support can still DPS while being close enough to
        # reach healing range within 1-2 movement turns.  Previously this used
        # _SUPPORT_HEAL_RANGE (3), which forced repositioning at 4+ tiles and
        # caused the support to waste 64% of turns walking instead of casting.
        _TANK_REPOSITION_THRESHOLD = 5  # only reposition when tank is > 5 tiles away
        for unit in all_units.values():
            if not unit.is_alive or unit.player_id == ai.player_id or unit.team != ai.team:
                continue
            unit_role = _get_role_for_class(unit.class_id) if unit.class_id else None
            if unit_role not in _TANK_ROLES:
                continue
            dist = _chebyshev(ai_pos, (unit.position.x, unit.position.y))
            if dist > _TANK_REPOSITION_THRESHOLD:
                return None  # Tank far away — reposition instead of DPS

    # --- Priority 4.7: Shield of Faith on ally (AFTER reposition check) ---
    # Moved here from Priority 4 so SoF doesn't block repositioning when
    # the tank is out of heal range and needs the Confessor to close distance.
    sof_action = _try_skill(ai, "shield_of_faith")
    if sof_action is not None:
        sof_def = get_skill("shield_of_faith")
        sof_range = sof_def["range"] if sof_def else 3
        sof_candidates: list[PlayerState] = []
        for unit in all_units.values():
            if not unit.is_alive or unit.team != ai.team:
                continue
            if unit.player_id == ai.player_id:
                continue  # Don't buff self — buff allies who are taking damage
            # Don't stack — check for existing armor buff
            has_sof = any(b.get("buff_id") == "shield_of_faith" for b in unit.active_buffs)
            if has_sof:
                continue
            dist = _chebyshev(ai_pos, (unit.position.x, unit.position.y))
            if dist <= sof_range:
                sof_candidates.append(unit)
        if sof_candidates:
            # Prefer lowest HP% (most at-risk)
            sof_candidates.sort(key=lambda u: u.hp / u.max_hp if u.max_hp > 0 else 1.0)
            target = sof_candidates[0]
            return _try_skill(ai, "shield_of_faith", target_x=target.position.x, target_y=target.position.y, target_id=target.player_id)

    # --- Priority 5 & 6: Exorcism (holy damage) ---
    exo_action = _try_skill(ai, "exorcism")
    if exo_action is not None and enemies:
        exo_def = get_skill("exorcism")
        exo_range = exo_def["range"] if exo_def else 5

        # Prioritize tagged enemies (undead/demon)
        for enemy in enemies:
            enemy_tags = getattr(enemy, 'tags', [])
            if any(t in enemy_tags for t in ["undead", "demon"]):
                dist = _chebyshev(ai_pos, (enemy.position.x, enemy.position.y))
                if dist <= exo_range:
                    if has_line_of_sight(ai.position.x, ai.position.y,
                                        enemy.position.x, enemy.position.y, obstacles):
                        return _try_skill(ai, "exorcism",
                                         target_x=enemy.position.x, target_y=enemy.position.y,
                                         target_id=enemy.player_id)

        # Fallback: any enemy in range
        for enemy in enemies:
            dist = _chebyshev(ai_pos, (enemy.position.x, enemy.position.y))
            if dist <= exo_range:
                if has_line_of_sight(ai.position.x, ai.position.y,
                                    enemy.position.x, enemy.position.y, obstacles):
                    return _try_skill(ai, "exorcism",
                                     target_x=enemy.position.x, target_y=enemy.position.y,
                                     target_id=enemy.player_id)

    return None


def _find_heal_candidates(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    heal_range: int,
    threshold: float | None = None,
) -> list[PlayerState]:
    """Find allies below heal threshold within range, sorted by HP% ascending.

    Args:
        threshold: HP% threshold — allies at or above this are skipped.
                   Defaults to _HEAL_ALLY_THRESHOLD (0.60) for combat triage.
                   Pass _HEAL_ALLY_OOC_THRESHOLD (0.95) for out-of-combat top-off.
    """
    if threshold is None:
        threshold = _HEAL_ALLY_THRESHOLD
    ai_pos = (ai.position.x, ai.position.y)
    candidates: list[PlayerState] = []
    for unit in all_units.values():
        if not unit.is_alive:
            continue
        if unit.player_id == ai.player_id:
            continue
        if unit.team != ai.team:
            continue
        if unit.hp >= unit.max_hp or unit.max_hp <= 0:
            continue
        if unit.hp / unit.max_hp >= threshold:
            continue
        dist = _chebyshev(ai_pos, (unit.position.x, unit.position.y))
        if dist <= heal_range:
            candidates.append(unit)
    candidates.sort(key=lambda u: u.hp / u.max_hp)
    return candidates


def _support_move_preference(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
) -> tuple[int, int] | None:
    """Return a preferred move target for support-role units (8C-2).

    Support units prefer to stay near allies rather than charging at enemies.
    Priority:
      1. Most injured ally (below 60% HP) — move toward them to heal next turn
      2. Tank-role ally outside heal range — close distance proactively
      3. Nearest ally — stay grouped, don't solo charge
      4. None — no allies alive, fall through to default behavior

    Returns (x, y) position of the preferred move target, or None.
    """
    ai_pos = (ai.position.x, ai.position.y)
    injured_allies: list[tuple[float, int, PlayerState]] = []
    all_allies: list[tuple[int, PlayerState]] = []
    tank_allies: list[tuple[int, PlayerState]] = []

    for unit in all_units.values():
        if not unit.is_alive:
            continue
        if unit.player_id == ai.player_id:
            continue
        if unit.team != ai.team:
            continue
        dist = _chebyshev(ai_pos, (unit.position.x, unit.position.y))
        all_allies.append((dist, unit))

        # Track tank-role allies separately
        unit_role = _get_role_for_class(unit.class_id) if unit.class_id else None
        if unit_role in _TANK_ROLES:
            tank_allies.append((dist, unit))

        if unit.max_hp > 0 and (unit.hp / unit.max_hp) < _HEAL_ALLY_THRESHOLD:
            injured_allies.append((unit.hp / unit.max_hp, dist, unit))

    # Priority 1: move toward most injured ally
    if injured_allies:
        injured_allies.sort(key=lambda t: (t[0], t[1]))  # lowest HP%, then closest
        target = injured_allies[0][2]
        return (target.position.x, target.position.y)

    # Priority 2: stay within heal range of the tank
    # If a tank-role ally is beyond heal range, close distance toward them
    # even when nobody is injured yet — proactive positioning.
    if tank_allies:
        tank_allies.sort(key=lambda t: t[0])  # nearest tank first
        nearest_tank_dist, nearest_tank = tank_allies[0]
        if nearest_tank_dist > _SUPPORT_HEAL_RANGE:
            return (nearest_tank.position.x, nearest_tank.position.y)

    # Priority 3: move toward nearest non-support ally (stay grouped)
    # Filter out other support-role allies to prevent two supports from
    # gravitating toward each other and clumping away from the frontline.
    non_support_allies = [
        (d, u) for d, u in all_allies
        if _get_role_for_class(u.class_id) not in _SUPPORT_ROLES
    ] if all_allies else []
    preferred = non_support_allies if non_support_allies else all_allies
    if preferred:
        preferred.sort(key=lambda t: t[0])
        target = preferred[0][1]
        return (target.position.x, target.position.y)

    return None


def _offensive_support_move_preference(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
) -> tuple[int, int] | None:
    """Return a preferred move target for the Bard (offensive_support role).

    Unlike generic _support_move_preference which chases the nearest or most
    injured ally (designed for the healer), the Bard targets the **centroid**
    of all living allies.  This positions the Bard in the center of the team
    so Ballad of Might (radius 3) covers the maximum number of teammates.

    Returns (x, y) of the ally centroid, or None if no allies alive.
    """
    allies: list[PlayerState] = []
    for unit in all_units.values():
        if not unit.is_alive:
            continue
        if unit.player_id == ai.player_id:
            continue
        if unit.team != ai.team:
            continue
        allies.append(unit)

    if not allies:
        return None

    cx = sum(a.position.x for a in allies) // len(allies)
    cy = sum(a.position.y for a in allies) // len(allies)
    return (cx, cy)


def _totemic_support_move_preference(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    match_state=None,
) -> tuple[int, int] | None:
    """Return a preferred move target for the Shaman (totemic_support role).

    Unlike generic _support_move_preference which chases the most injured ally,
    the Shaman prioritizes staying near the frontline tank so healing totems
    cover the unit absorbing the most damage.

    Priority:
      1. If a healing totem is active: move toward the totem (stay in own heal zone)
      2. Injured tank (below 70% HP): move toward the frontline tank taking damage
      3. Nearest tank: stay within placement range of the tank even if healthy
      4. Most injured ally: fallback to generic support behavior
      5. Nearest ally: stay grouped

    Returns (x, y) position of the preferred move target, or None.
    """
    ai_pos = (ai.position.x, ai.position.y)

    # If we have an active healing totem, drift toward it (stay in our own heal zone)
    if match_state is not None and hasattr(match_state, "totems"):
        for t in match_state.totems:
            if t.get("owner_id") == ai.player_id and t["type"] == "healing_totem":
                return (t["x"], t["y"])

    tanks: list[tuple[float, int, PlayerState]] = []
    injured_allies: list[tuple[float, int, PlayerState]] = []
    all_allies: list[tuple[int, PlayerState]] = []

    for unit in all_units.values():
        if not unit.is_alive or unit.player_id == ai.player_id or unit.team != ai.team:
            continue
        dist = _chebyshev(ai_pos, (unit.position.x, unit.position.y))
        all_allies.append((dist, unit))
        is_tank = (getattr(unit, "class_id", "") or "") in _HEALING_TOTEM_TANK_CLASSES
        if is_tank:
            hp_pct = unit.hp / unit.max_hp if unit.max_hp > 0 else 1.0
            tanks.append((hp_pct, dist, unit))
        if unit.max_hp > 0 and (unit.hp / unit.max_hp) < _HEAL_ALLY_THRESHOLD:
            injured_allies.append((unit.hp / unit.max_hp, dist, unit))

    # Prefer injured tanks first (lowest HP%, then closest)
    if tanks:
        tanks.sort(key=lambda t: (t[0], t[1]))
        # Move toward the most injured tank (or nearest tank if all healthy)
        target = tanks[0][2]
        return (target.position.x, target.position.y)

    # No tanks — fall back to most injured ally
    if injured_allies:
        injured_allies.sort(key=lambda t: (t[0], t[1]))
        target = injured_allies[0][2]
        return (target.position.x, target.position.y)

    # Otherwise nearest non-support ally — avoid clumping with other supports
    non_support_allies = [
        (d, u) for d, u in all_allies
        if _get_role_for_class(u.class_id) not in _SUPPORT_ROLES
    ] if all_allies else []
    preferred = non_support_allies if non_support_allies else all_allies
    if preferred:
        preferred.sort(key=lambda t: t[0])
        target = preferred[0][1]
        return (target.position.x, target.position.y)

    return None


def _tank_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Tank role AI: taunt, shield bash (stun), holy ground (AoE heal), bulwark, then melee.

    Phase 12 implementation — replaces Phase 8D crusader-specific logic.

    Priority:
      1. Taunt: if 2+ enemies visible AND off cooldown → force nearby enemies to target you.
      2. Shield Bash (stun): if adjacent to enemy AND off cooldown → stun + damage.
      3. Holy Ground (AoE heal): if self or adjacent ally below 60% HP AND off cooldown.
      4. Bulwark (armor buff): if enemies visible AND no armor buff active AND off cooldown.
      5. War Cry: if enemies visible AND off cooldown AND no melee_damage_multiplier buff.
      6. Double Strike: if adjacent to an enemy AND off cooldown.
      7. Return None → fall through to basic melee/move logic.
    """
    if not enemies:
        return None  # No enemies visible → don't waste skills

    ai_pos = (ai.position.x, ai.position.y)
    ai_pos_obj = Position(x=ai.position.x, y=ai.position.y)

    # --- Priority 1: Taunt (AoE threat pull) ---
    # Use when 2+ enemies are within taunt radius (2 tiles)
    taunt_action = _try_skill(ai, "taunt")
    if taunt_action is not None:
        taunt_def = get_skill("taunt")
        taunt_radius = taunt_def["effects"][0].get("radius", 2) if taunt_def else 2
        enemies_in_range = [
            e for e in enemies
            if _chebyshev(ai_pos, (e.position.x, e.position.y)) <= taunt_radius
        ]
        if len(enemies_in_range) >= 2:
            return _try_skill(ai, "taunt", target_x=ai.position.x, target_y=ai.position.y)

    # --- Priority 2: Shield Bash (stun adjacent enemy) ---
    adjacent_enemies = [
        e for e in enemies
        if is_adjacent(ai_pos_obj, Position(x=e.position.x, y=e.position.y))
    ]
    if adjacent_enemies:
        sb_action = _try_skill(ai, "shield_bash")
        if sb_action is not None:
            from app.core.ai_memory import _pick_best_target
            target = _pick_best_target(ai, adjacent_enemies, all_units)
            return _try_skill(
                ai, "shield_bash",
                target_x=target.position.x,
                target_y=target.position.y,
                target_id=target.player_id,
            )

    # --- Priority 3: Holy Ground (AoE heal) ---
    # Use when self or adjacent ally is below 60% HP
    hg_action = _try_skill(ai, "holy_ground")
    if hg_action is not None:
        needs_heal = False
        if ai.hp / ai.max_hp < 0.6:
            needs_heal = True
        else:
            for unit in all_units.values():
                if not unit.is_alive or unit.team != ai.team or unit.player_id == ai.player_id:
                    continue
                dist = _chebyshev(ai_pos, (unit.position.x, unit.position.y))
                if dist <= 1 and unit.max_hp > 0 and unit.hp / unit.max_hp < 0.6:
                    needs_heal = True
                    break
        if needs_heal:
            return _try_skill(ai, "holy_ground", target_x=ai.position.x, target_y=ai.position.y)

    # --- Priority 4: Bulwark (armor self-buff) ---
    has_armor_buff = any(
        buff.get("stat") == "armor" and buff.get("type") == "buff"
        for buff in ai.active_buffs
    )
    if not has_armor_buff:
        bulwark_action = _try_skill(ai, "bulwark")
        if bulwark_action:
            return bulwark_action

    # --- Priority 5: War Cry (melee damage self-buff) — legacy fallback ---
    has_melee_buff = any(
        buff.get("stat") == "melee_damage_multiplier"
        for buff in ai.active_buffs
    )
    if not has_melee_buff:
        war_cry_action = _try_skill(ai, "war_cry")
        if war_cry_action:
            return war_cry_action

    # --- Priority 6: Double Strike (adjacent enemy) — legacy fallback ---
    if adjacent_enemies:
        from app.core.ai_memory import _pick_best_target
        target = _pick_best_target(ai, adjacent_enemies, all_units)
        ds_action = _try_skill(
            ai, "double_strike",
            target_x=target.position.x,
            target_y=target.position.y,
            target_id=target.player_id,
        )
        if ds_action:
            return ds_action

    # Use taunt even with 1 enemy if nothing else available
    if taunt_action is not None:
        enemies_in_range = [
            e for e in enemies
            if _chebyshev(ai_pos, (e.position.x, e.position.y)) <= 2
        ]
        if enemies_in_range:
            return _try_skill(ai, "taunt", target_x=ai.position.x, target_y=ai.position.y)

    # --- No skill to use → fall through to basic attack/move ---
    return None


def _ranged_dps_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Ranged DPS role: evasion, bone shield, DoT debuffs, volley AoE, crippling shot, power shot.

    Phase 12 implementation — extends Phase 8E-1 with new Ranger skills.
    Phase 18I: Added Bone Shield support for Skeletons.

    Priority:
      1. Evasion: if adjacent to enemy AND HP < 50% AND off cooldown → dodge charges
      1b. Bone Shield: if enemies visible AND no absorb active → cast absorb shield
      2. Venom Gaze / DoT: if enemy in range + LOS + not already cursed → apply DoT
      3. Volley (AoE): if 2+ enemies clustered within 2 tiles of each other → rain arrows
      4. Crippling Shot: if enemy in range + LOS + off CD → damage + slow
      5. Power Shot: if enemy in ranged range + LOS + Power Shot off CD → heavy ranged hit
      6. Return None → fall through to basic ranged/melee logic.
    """
    if not enemies:
        return None

    ai_pos = (ai.position.x, ai.position.y)
    ai_pos_obj = Position(x=ai.position.x, y=ai.position.y)
    config = get_combat_config()
    ranged_range = getattr(ai, 'ranged_range', config.get("ranged_range", 5))

    # --- Priority 1: Evasion (self-buff when in danger) ---
    adjacent_enemies = [
        e for e in enemies
        if is_adjacent(ai_pos_obj, Position(x=e.position.x, y=e.position.y))
    ]
    has_evasion = any(
        buff.get("type") == "evasion" and buff.get("charges", 0) > 0
        for buff in ai.active_buffs
    )
    if adjacent_enemies and not has_evasion and ai.max_hp > 0 and ai.hp / ai.max_hp < 0.5:
        ev_action = _try_skill(ai, "evasion")
        if ev_action:
            return ev_action

    # --- Priority 1b: Bone Shield (Skeleton) ---
    # Cast when enemies are visible and skeleton has no active absorb shield
    has_absorb = any(
        buff.get("type") == "damage_absorb" and buff.get("absorb_remaining", 0) > 0
        for buff in ai.active_buffs
    )
    if enemies and not has_absorb:
        bs_action = _try_skill(ai, "bone_shield")
        if bs_action:
            return bs_action

    # --- Priority 2: Venom Gaze (DoT — Medusa) ---
    vg_action = _try_skill(ai, "venom_gaze")
    if vg_action is not None:
        vg_def = get_skill("venom_gaze")
        vg_range = vg_def["range"] if vg_def else 4

        candidates = []
        for enemy in enemies:
            dist = _chebyshev(ai_pos, (enemy.position.x, enemy.position.y))
            if dist > vg_range:
                continue
            has_venom = any(
                b.get("buff_id") == "venom_gaze" and b.get("type") == "dot"
                for b in enemy.active_buffs
            )
            if has_venom:
                continue
            if has_line_of_sight(ai.position.x, ai.position.y,
                                enemy.position.x, enemy.position.y, obstacles):
                candidates.append(enemy)

        if candidates:
            candidates.sort(key=lambda e: e.hp, reverse=True)
            target = candidates[0]
            return _try_skill(ai, "venom_gaze",
                             target_x=target.position.x, target_y=target.position.y,
                             target_id=target.player_id)

    # --- Priority 3: Volley (AoE) — if 2+ enemies clustered ---
    volley_action = _try_skill(ai, "volley")
    if volley_action is not None:
        volley_def = get_skill("volley")
        volley_range = volley_def["range"] if volley_def else 5
        volley_radius = volley_def["effects"][0].get("radius", 2) if volley_def else 2

        # Find the best target tile that hits the most enemies
        best_tile = None
        best_count = 0
        for enemy in enemies:
            ex, ey = enemy.position.x, enemy.position.y
            # Check if we can target this tile (range + LOS to center)
            dist_to_tile = _chebyshev(ai_pos, (ex, ey))
            if dist_to_tile > volley_range:
                continue
            if not has_line_of_sight(ai.position.x, ai.position.y, ex, ey, obstacles):
                continue
            # Count enemies within radius of this tile
            count = sum(
                1 for e in enemies
                if max(abs(e.position.x - ex), abs(e.position.y - ey)) <= volley_radius
            )
            if count > best_count:
                best_count = count
                best_tile = (ex, ey)

        if best_tile and best_count >= 2:
            return _try_skill(ai, "volley", target_x=best_tile[0], target_y=best_tile[1])

    # --- Priority 4: Crippling Shot (damage + slow) ---
    cs_action = _try_skill(ai, "crippling_shot")
    if cs_action is not None:
        # Prefer enemies that are closing distance (melee threats)
        for enemy in enemies:
            dist = _chebyshev(ai_pos, (enemy.position.x, enemy.position.y))
            if dist > ranged_range:
                continue
            # Prefer enemies not already slowed
            has_slow = any(b.get("type") == "slow" for b in enemy.active_buffs)
            if has_slow:
                continue
            if has_line_of_sight(ai.position.x, ai.position.y,
                                enemy.position.x, enemy.position.y, obstacles):
                return _try_skill(ai, "crippling_shot",
                                 target_x=enemy.position.x, target_y=enemy.position.y,
                                 target_id=enemy.player_id)
        # Fallback: any enemy in range even if slowed
        for enemy in enemies:
            dist = _chebyshev(ai_pos, (enemy.position.x, enemy.position.y))
            if dist > ranged_range:
                continue
            if has_line_of_sight(ai.position.x, ai.position.y,
                                enemy.position.x, enemy.position.y, obstacles):
                return _try_skill(ai, "crippling_shot",
                                 target_x=enemy.position.x, target_y=enemy.position.y,
                                 target_id=enemy.player_id)

    # --- Priority 5: Power Shot ---
    ps_base = _try_skill(ai, "power_shot")
    if ps_base is not None:
        config = get_combat_config()
        ranged_range = getattr(ai, 'ranged_range', config.get("ranged_range", 5))

        from app.core.ai_memory import _pick_best_target
        target = _pick_best_target(ai, enemies, all_units)
        target_pos = Position(x=target.position.x, y=target.position.y)

        if is_in_range(ai.position, target_pos, ranged_range):
            if has_line_of_sight(
                ai.position.x, ai.position.y,
                target.position.x, target.position.y,
                obstacles,
            ):
                return _try_skill(
                    ai, "power_shot",
                    target_x=target.position.x,
                    target_y=target.position.y,
                    target_id=target.player_id,
                )

        for enemy in enemies:
            if enemy.player_id == target.player_id:
                continue
            e_pos = Position(x=enemy.position.x, y=enemy.position.y)
            if is_in_range(ai.position, e_pos, ranged_range):
                if has_line_of_sight(
                    ai.position.x, ai.position.y,
                    enemy.position.x, enemy.position.y,
                    obstacles,
                ):
                    return _try_skill(
                        ai, "power_shot",
                        target_x=enemy.position.x,
                        target_y=enemy.position.y,
                        target_id=enemy.player_id,
                    )

    # No enemy in range + LOS → fall through to basic attack/move
    return None


def _find_shadow_step_gapcloser_tile(
    ai: PlayerState,
    target_enemy: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> tuple[int, int] | None:
    """Find the best Shadow Step gap-close tile for a hybrid DPS (Hexblade).

    Hexblades want to land ADJACENT to the target enemy for immediate melee.
    Scoring:
      - Primary: prefer tiles adjacent (Chebyshev distance 1) to the target
      - Tiebreak: minimize distance from AI's current position (preserve momentum)

    If no adjacent tiles are available, fall back to the closest valid tile.

    Returns (x, y) of best tile, or None if no valid tiles.
    """
    valid_tiles = _find_valid_shadow_step_tiles(
        ai, all_units, grid_width, grid_height, obstacles,
    )
    if not valid_tiles:
        return None

    target_pos = (target_enemy.position.x, target_enemy.position.y)
    ai_pos = (ai.position.x, ai.position.y)

    # Prefer tiles adjacent to target enemy (Chebyshev distance 1)
    adjacent_tiles = [
        t for t in valid_tiles
        if _chebyshev(t, target_pos) == 1
    ]

    if adjacent_tiles:
        # Among adjacent tiles, pick the one closest to AI (least wasted movement)
        return min(adjacent_tiles, key=lambda t: _chebyshev(t, ai_pos))

    # No adjacent tiles — fall back to closest valid tile to target
    return min(valid_tiles, key=lambda t: _chebyshev(t, target_pos))


def _hybrid_dps_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Hybrid DPS role: Wither for DoT, Ward for reflection, gap-close + Double Strike.

    Phase 8E-3 + Phase 11 + Hexblade balance pass (March 2026).

    Priority:
      1. Wither: if enemy in range + LOS + not already cursed → apply DoT (immediate value)
      2. Ward: if not active AND enemies visible → activate reflective shield
      3. Double Strike: if adjacent to enemy AND off cooldown
      4. Shadow Step gap-close: if closest enemy > 2 tiles away AND off cooldown
      5. Return None → fall through to basic attack/move logic.

    Design:
      - Hexblade opens with Wither at range for immediate DoT pressure, then pops Ward.
      - Ward is activated before committing to melee — Hexblade expects to take hits.
      - Wither applied to high-HP targets for efficient armor-bypassing damage.
    """
    if not enemies:
        return None

    ai_pos = (ai.position.x, ai.position.y)
    ai_pos_obj = Position(x=ai.position.x, y=ai.position.y)

    # --- Priority 1: Wither (DoT curse — immediate value opener) ---
    wither_action = _try_skill(ai, "wither")
    if wither_action is not None:
        wither_def = get_skill("wither")
        wither_range = wither_def["range"] if wither_def else 3

        # Prefer highest-HP target without existing Wither
        candidates = []
        for enemy in enemies:
            dist = _chebyshev(ai_pos, (enemy.position.x, enemy.position.y))
            if dist > wither_range:
                continue
            # Check if already affected by Wither
            has_wither = any(
                b.get("buff_id") == "wither" and b.get("type") == "dot"
                for b in enemy.active_buffs
            )
            if has_wither:
                continue
            if has_line_of_sight(ai.position.x, ai.position.y,
                                enemy.position.x, enemy.position.y, obstacles):
                candidates.append(enemy)

        if candidates:
            # Target highest HP (Wither is most efficient on tanky targets)
            candidates.sort(key=lambda e: e.hp, reverse=True)
            target = candidates[0]
            return _try_skill(ai, "wither",
                             target_x=target.position.x, target_y=target.position.y,
                             target_id=target.player_id)

    # --- Priority 2: Ward (reflective shield) ---
    has_ward = any(
        buff.get("buff_id") == "ward" and buff.get("type") == "shield_charges"
        for buff in ai.active_buffs
    )
    if not has_ward:
        ward_action = _try_skill(ai, "ward")
        if ward_action:
            return ward_action

    # --- Priority 2b: Soul Reap (ranged nuke — Reaper) ---
    sr_action = _try_skill(ai, "soul_reap")
    if sr_action is not None:
        sr_def = get_skill("soul_reap")
        sr_range = sr_def["range"] if sr_def else 4

        from app.core.ai_memory import _pick_best_target as _pick_sr_target
        sr_target = _pick_sr_target(ai, enemies, all_units)
        sr_target_pos = Position(x=sr_target.position.x, y=sr_target.position.y)
        sr_dist = _chebyshev(ai_pos, (sr_target.position.x, sr_target.position.y))
        if sr_dist <= sr_range and has_line_of_sight(
            ai.position.x, ai.position.y,
            sr_target.position.x, sr_target.position.y, obstacles
        ):
            return _try_skill(ai, "soul_reap",
                             target_x=sr_target.position.x, target_y=sr_target.position.y,
                             target_id=sr_target.player_id)

    # --- Priority 3: Double Strike (adjacent enemy) ---
    adjacent_enemies = [
        e for e in enemies
        if is_adjacent(ai_pos_obj, Position(x=e.position.x, y=e.position.y))
    ]
    if adjacent_enemies:
        from app.core.ai_memory import _pick_best_target
        target = _pick_best_target(ai, adjacent_enemies, all_units)
        ds_action = _try_skill(
            ai, "double_strike",
            target_x=target.position.x,
            target_y=target.position.y,
            target_id=target.player_id,
        )
        if ds_action:
            return ds_action

    # --- Priority 4: Shadow Step gap-close (offensive) ---
    closest_enemy = min(
        enemies,
        key=lambda e: _chebyshev(ai_pos, (e.position.x, e.position.y)),
    )
    closest_dist = _chebyshev(ai_pos, (closest_enemy.position.x, closest_enemy.position.y))

    if closest_dist > _SHADOW_STEP_GAPCLOSER_MIN_DISTANCE:
        ss_action = _try_skill(ai, "shadow_step")
        if ss_action is not None:
            gapcloser_tile = _find_shadow_step_gapcloser_tile(
                ai, closest_enemy, all_units, grid_width, grid_height,
                obstacles,
            )
            if gapcloser_tile:
                return _try_skill(
                    ai, "shadow_step",
                    target_x=gapcloser_tile[0],
                    target_y=gapcloser_tile[1],
                )

    # --- No skill to use → fall through to basic attack/move ---
    return None


def _find_valid_shadow_step_tiles(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Find all valid Shadow Step destination tiles.

    Valid tiles must be:
      - Within range 3 (Chebyshev) of the AI
      - Within grid bounds
      - Not the AI's current position
      - Not an obstacle
      - Not occupied by another alive unit
      - Have LOS from the AI's current position
    """
    ai_pos = (ai.position.x, ai.position.y)
    ss_range = 3  # Shadow Step range from skills_config

    # Build occupied set
    occupied = set()
    for unit in all_units.values():
        if unit.is_alive and unit.player_id != ai.player_id:
            occupied.add((unit.position.x, unit.position.y))

    valid_tiles: list[tuple[int, int]] = []
    for dx in range(-ss_range, ss_range + 1):
        for dy in range(-ss_range, ss_range + 1):
            tx, ty = ai_pos[0] + dx, ai_pos[1] + dy

            if tx == ai_pos[0] and ty == ai_pos[1]:
                continue  # Can't teleport to own position
            if max(abs(dx), abs(dy)) > ss_range:
                continue  # Out of Chebyshev range
            if tx < 0 or tx >= grid_width or ty < 0 or ty >= grid_height:
                continue  # Out of bounds
            if (tx, ty) in obstacles:
                continue  # Obstacle
            if (tx, ty) in occupied:
                continue  # Occupied
            if not has_line_of_sight(ai_pos[0], ai_pos[1], tx, ty, obstacles):
                continue  # No LOS

            valid_tiles.append((tx, ty))

    return valid_tiles


def _find_shadow_step_escape_tile(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    ranged_range: int,
) -> tuple[int, int] | None:
    """Find the best Shadow Step escape tile for a scout.

    Scoring:
      - Primary: maximize distance from nearest enemy (survival)
      - Bonus: tile is still within ranged_range of an enemy (retreat to shoot)

    Returns (x, y) of best tile, or None if no valid tiles.
    """
    valid_tiles = _find_valid_shadow_step_tiles(
        ai, all_units, grid_width, grid_height, obstacles,
    )
    if not valid_tiles:
        return None

    def escape_score(tile: tuple[int, int]) -> float:
        tx, ty = tile
        # Minimum distance from any enemy (maximize this)
        min_enemy_dist = min(
            _chebyshev((tx, ty), (e.position.x, e.position.y))
            for e in enemies
        )
        score = float(min_enemy_dist) * 10.0  # Heavy weight on distance

        # Bonus: tile is within ranged range of at least one enemy (can still shoot)
        for e in enemies:
            if _chebyshev((tx, ty), (e.position.x, e.position.y)) <= ranged_range:
                score += 5.0  # Can still shoot from this position
                break

        return score

    best_tile = max(valid_tiles, key=escape_score)
    return best_tile


def _find_shadow_step_offensive_tile(
    ai: PlayerState,
    target_enemy: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> tuple[int, int] | None:
    """Find the best Shadow Step offensive tile for a scout.

    Scouts prefer ranged distance — teleport closer but NOT adjacent.
    Scoring:
      - Minimize distance to target (get closer)
      - Prefer tiles at least 2 tiles away (Inquisitor prefers range, not melee)

    Returns (x, y) of best tile, or None if no valid tiles.
    """
    valid_tiles = _find_valid_shadow_step_tiles(
        ai, all_units, grid_width, grid_height, obstacles,
    )
    if not valid_tiles:
        return None

    target_pos = (target_enemy.position.x, target_enemy.position.y)

    # Filter: prefer tiles at least 2 tiles from target (keep ranged distance)
    ranged_tiles = [
        t for t in valid_tiles
        if _chebyshev(t, target_pos) >= 2
    ]

    # If no tiles at 2+ distance, allow adjacent as fallback
    candidates = ranged_tiles if ranged_tiles else valid_tiles

    # Score: minimize distance to target enemy
    best_tile = min(candidates, key=lambda t: _chebyshev(t, target_pos))
    return best_tile


def _caster_dps_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Caster DPS role (Mage): Frost Nova panic, Blink escape, Fireball nuke, Arcane Barrage AoE.

    Phase 17 implementation — ranger-style kiting with spell focus.

    Priority:
      1. Frost Nova: if 2+ enemies within radius 2 → AoE damage + slow (panic button)
      2. Blink: if adjacent to enemy AND HP < 40% → teleport to safety
      3. Fireball: if enemy in range + LOS + off CD → single-target magic nuke
      4. Arcane Barrage: if 2+ enemies clustered within 1 tile of each other → AoE
      5. Blink: offensive gap-close to get into range if no enemies reachable
      6. Return None → fall through to basic ranged attack/kiting logic.

    Design:
      - Mage plays like a glass cannon: stays at max range, Frost Nova + Blink if caught.
      - Fireball is the primary damage dealer (2.0× ranged), spammed on cooldown.
      - Arcane Barrage for AoE when enemies cluster.
      - Uses ranger-style kiting: flee if enemies get adjacent.
    """
    if not enemies:
        return None

    ai_pos = (ai.position.x, ai.position.y)
    ai_pos_obj = Position(x=ai.position.x, y=ai.position.y)
    config = get_combat_config()
    ranged_range = getattr(ai, 'ranged_range', config.get("ranged_range", 5))

    # Check adjacency to any enemy
    adjacent_enemies = [
        e for e in enemies
        if is_adjacent(ai_pos_obj, Position(x=e.position.x, y=e.position.y))
    ]

    # --- Priority 1: Frost Nova (AoE damage + slow — panic button) ---
    fn_action = _try_skill(ai, "frost_nova")
    if fn_action is not None:
        frost_def = get_skill("frost_nova")
        frost_radius = frost_def["effects"][0].get("radius", 2) if frost_def else 2
        enemies_in_radius = [
            e for e in enemies
            if max(abs(e.position.x - ai.position.x), abs(e.position.y - ai.position.y)) <= frost_radius
        ]
        if len(enemies_in_radius) >= 2:
            return _try_skill(ai, "frost_nova", target_x=ai.position.x, target_y=ai.position.y)
        # Also use Frost Nova with just 1 adjacent enemy if HP is critical
        if adjacent_enemies and ai.max_hp > 0 and ai.hp / ai.max_hp < 0.40:
            return _try_skill(ai, "frost_nova", target_x=ai.position.x, target_y=ai.position.y)

    # --- Priority 2: Blink escape (defensive) ---
    if adjacent_enemies and ai.max_hp > 0 and ai.hp / ai.max_hp < 0.40:
        blink_action = _try_skill(ai, "blink")
        if blink_action is not None:
            escape_tile = _find_shadow_step_escape_tile(
                ai, enemies, all_units, grid_width, grid_height,
                obstacles, ranged_range,
            )
            if escape_tile:
                return _try_skill(ai, "blink", target_x=escape_tile[0], target_y=escape_tile[1])

    # --- Priority 3: Fireball (single-target magic nuke) ---
    fb_action = _try_skill(ai, "fireball")
    if fb_action is not None:
        fireball_def = get_skill("fireball")
        fb_range = fireball_def["range"] if fireball_def else 5

        # Target highest-HP enemy in range + LOS
        candidates = []
        for enemy in enemies:
            dist = _chebyshev(ai_pos, (enemy.position.x, enemy.position.y))
            if dist > fb_range:
                continue
            if has_line_of_sight(ai.position.x, ai.position.y,
                                enemy.position.x, enemy.position.y, obstacles):
                candidates.append(enemy)
        if candidates:
            candidates.sort(key=lambda e: e.hp, reverse=True)
            target = candidates[0]
            return _try_skill(ai, "fireball",
                             target_x=target.position.x, target_y=target.position.y,
                             target_id=target.player_id)

    # --- Priority 4: Arcane Barrage (AoE — if 2+ enemies clustered) ---
    ab_action = _try_skill(ai, "arcane_barrage")
    if ab_action is not None:
        ab_def = get_skill("arcane_barrage")
        ab_range = ab_def["range"] if ab_def else 5
        ab_radius = ab_def["effects"][0].get("radius", 1) if ab_def else 1

        best_tile = None
        best_count = 0
        for enemy in enemies:
            ex, ey = enemy.position.x, enemy.position.y
            dist_to_tile = _chebyshev(ai_pos, (ex, ey))
            if dist_to_tile > ab_range:
                continue
            if not has_line_of_sight(ai.position.x, ai.position.y, ex, ey, obstacles):
                continue
            count = sum(
                1 for e in enemies
                if max(abs(e.position.x - ex), abs(e.position.y - ey)) <= ab_radius
            )
            if count > best_count:
                best_count = count
                best_tile = (ex, ey)
        if best_tile and best_count >= 2:
            return _try_skill(ai, "arcane_barrage", target_x=best_tile[0], target_y=best_tile[1])

    # --- Priority 5: Blink offensive (close gap to get into cast range) ---
    closest_enemy = min(
        enemies,
        key=lambda e: _chebyshev(ai_pos, (e.position.x, e.position.y)),
    )
    closest_dist = _chebyshev(ai_pos, (closest_enemy.position.x, closest_enemy.position.y))

    if closest_dist > ranged_range:
        blink_action = _try_skill(ai, "blink")
        if blink_action is not None:
            offensive_tile = _find_shadow_step_offensive_tile(
                ai, closest_enemy, all_units, grid_width, grid_height,
                obstacles,
            )
            if offensive_tile:
                return _try_skill(ai, "blink", target_x=offensive_tile[0], target_y=offensive_tile[1])

    # --- No skill to use → fall through to basic ranged attack/kiting ---
    return None


def _scout_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Scout role: Seal of Judgment debuff, Rebuke holy burst, Power Shot + Shadow Step.

    Phase 8E-2 + Phase 11 + Seal of Judgment rework.

    Priority:
      1. Shadow Step escape: HP < 30% AND adjacent to enemy AND Shadow Step off CD
      2. Seal of Judgment: mark highest-HP enemy for +25% damage taken (team amplifier)
      3. Rebuke the Wicked: prioritize Undead/Demon enemies in range (42 dmg!)
      4. Power Shot: enemy in range + LOS + off CD
      5. Shadow Step offense: closest enemy > 4 tiles away
      6. Return None → fall through to basic attack/move logic.
    """
    if not enemies:
        return None

    ai_pos = (ai.position.x, ai.position.y)

    # Get class ranged range for positioning decisions
    config = get_combat_config()
    ranged_range = getattr(ai, 'ranged_range', config.get("ranged_range", 5))

    # Check adjacency to any enemy (needed for escape check)
    ai_pos_obj = Position(x=ai.position.x, y=ai.position.y)
    adjacent_enemies = [
        e for e in enemies
        if is_adjacent(ai_pos_obj, Position(x=e.position.x, y=e.position.y))
    ]

    # --- Priority 1: Shadow Step escape (defensive) ---
    if (ai.max_hp > 0
            and ai.hp / ai.max_hp < _SHADOW_STEP_ESCAPE_HP_THRESHOLD
            and adjacent_enemies):
        ss_action = _try_skill(ai, "shadow_step")
        if ss_action is not None:
            escape_tile = _find_shadow_step_escape_tile(
                ai, enemies, all_units, grid_width, grid_height,
                obstacles, ranged_range,
            )
            if escape_tile:
                return _try_skill(
                    ai, "shadow_step",
                    target_x=escape_tile[0],
                    target_y=escape_tile[1],
                )

    # --- Priority 2: Seal of Judgment (mark enemy for +25% damage taken) ---
    soj_action = _try_skill(ai, "seal_of_judgment")
    if soj_action is not None:
        soj_def = get_skill("seal_of_judgment")
        soj_range = soj_def["range"] if soj_def else 6

        # Pick highest-HP enemy in range+LOS (mark the tankiest threat)
        best_target = None
        best_hp = -1
        for enemy in enemies:
            # Skip enemies already marked with seal_of_judgment
            already_marked = any(
                b.get("buff_id") == "seal_of_judgment" for b in enemy.active_buffs
            )
            if already_marked:
                continue
            if is_in_range(ai.position, Position(x=enemy.position.x, y=enemy.position.y), soj_range):
                if has_line_of_sight(ai.position.x, ai.position.y,
                                    enemy.position.x, enemy.position.y, obstacles):
                    if enemy.hp > best_hp:
                        best_hp = enemy.hp
                        best_target = enemy
        if best_target is not None:
            return _try_skill(ai, "seal_of_judgment",
                             target_x=best_target.position.x, target_y=best_target.position.y,
                             target_id=best_target.player_id)

    # --- Priority 3: Rebuke the Wicked (holy burst — prefer tagged enemies) ---
    rebuke_action = _try_skill(ai, "rebuke")
    if rebuke_action is not None:
        rebuke_def = get_skill("rebuke")
        rebuke_range = rebuke_def["range"] if rebuke_def else 6

        # Prioritize Undead/Demon targets for bonus damage
        tagged_targets = [
            e for e in enemies
            if any(t in getattr(e, 'tags', []) for t in ["undead", "demon"])
        ]
        for target_list in [tagged_targets, enemies]:
            for enemy in target_list:
                if is_in_range(ai.position, Position(x=enemy.position.x, y=enemy.position.y), rebuke_range):
                    if has_line_of_sight(ai.position.x, ai.position.y,
                                        enemy.position.x, enemy.position.y, obstacles):
                        return _try_skill(ai, "rebuke",
                                         target_x=enemy.position.x, target_y=enemy.position.y,
                                         target_id=enemy.player_id)

    # --- Priority 4: Power Shot (offensive ranged) ---
    ps_base = _try_skill(ai, "power_shot")
    if ps_base is not None:
        from app.core.ai_memory import _pick_best_target
        target = _pick_best_target(ai, enemies, all_units)
        target_pos = Position(x=target.position.x, y=target.position.y)

        if is_in_range(ai.position, target_pos, ranged_range):
            if has_line_of_sight(
                ai.position.x, ai.position.y,
                target.position.x, target.position.y,
                obstacles,
            ):
                return _try_skill(
                    ai, "power_shot",
                    target_x=target.position.x,
                    target_y=target.position.y,
                    target_id=target.player_id,
                )

        # Check secondary targets
        for enemy in enemies:
            if enemy.player_id == target.player_id:
                continue
            e_pos = Position(x=enemy.position.x, y=enemy.position.y)
            if is_in_range(ai.position, e_pos, ranged_range):
                if has_line_of_sight(
                    ai.position.x, ai.position.y,
                    enemy.position.x, enemy.position.y,
                    obstacles,
                ):
                    return _try_skill(
                        ai, "power_shot",
                        target_x=enemy.position.x,
                        target_y=enemy.position.y,
                        target_id=enemy.player_id,
                    )

    # --- Priority 5: Shadow Step offense (close the gap to ranged distance) ---
    closest_enemy = min(
        enemies,
        key=lambda e: _chebyshev(ai_pos, (e.position.x, e.position.y)),
    )
    closest_dist = _chebyshev(ai_pos, (closest_enemy.position.x, closest_enemy.position.y))

    if closest_dist > _SHADOW_STEP_OFFENSIVE_MIN_DISTANCE:
        ss_action = _try_skill(ai, "shadow_step")
        if ss_action is not None:
            offensive_tile = _find_shadow_step_offensive_tile(
                ai, closest_enemy, all_units, grid_width, grid_height,
                obstacles,
            )
            if offensive_tile:
                return _try_skill(
                    ai, "shadow_step",
                    target_x=offensive_tile[0],
                    target_y=offensive_tile[1],
                )

    # --- No skill to use → fall through to basic attack/move ---
    return None


# ---------------------------------------------------------------------------
# Phase 21D: Offensive Support (Bard) — buff allies, debuff enemies, CDR
# ---------------------------------------------------------------------------

# Minimum ally count thresholds for AoE buffs/debuffs
_BALLAD_MIN_ALLIES = 1       # Need 1+ ally in radius to justify Ballad (single DPS buff still high-value)
_DIRGE_MIN_ENEMIES = 1       # Need 1+ enemy to justify Dirge (was 2 — too restrictive, Bard lost a key tool in spread fights)
_VERSE_MIN_COOLDOWN_DEBT = 1 # Ally must have 1+ total cooldown turns to merit Verse (lowered from 2 — lets Bard use CDR more aggressively)
_CACOPHONY_EMERGENCY_HP_PCT = 0.50  # Bard promotes Cacophony to priority 1 when HP below this AND enemy adjacent


def _offensive_support_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Offensive support (Bard): buff allies → debuff enemies → reduce cooldowns → self-peel.

    Phase 21D implementation.

    Priority:
      1. Ballad of Might:  if 2+ allies within radius 2, off cooldown
      2. Dirge of Weakness: if 2+ enemies clustered (within radius 2 of a tile), off cooldown
      3. Verse of Haste:   on the ally with the highest cooldown debt, off cooldown
      4. Cacophony:        if enemy adjacent (self-peel emergency)
      5. Return None →     fall through to basic attack logic
    """
    ai_pos = (ai.position.x, ai.position.y)

    # Gather living allies (same team, not self)
    allies = [
        u for u in all_units.values()
        if u.is_alive and u.team == ai.team and u.player_id != ai.player_id
    ]

    # --- Emergency Priority 0: Cacophony self-peel when low HP + enemy adjacent ---
    # If the Bard is being dived and wounded, slow the attacker FIRST to enable kiting.
    if ai.max_hp > 0 and (ai.hp / ai.max_hp) < _CACOPHONY_EMERGENCY_HP_PCT:
        cacophony_def = get_skill("cacophony")
        cacophony_radius = cacophony_def["effects"][0].get("radius", 2) if cacophony_def else 2
        nearby_enemies = [
            e for e in enemies
            if _chebyshev(ai_pos, (e.position.x, e.position.y)) <= cacophony_radius
        ]
        if nearby_enemies:
            emergency_cacophony = _try_skill(ai, "cacophony")
            if emergency_cacophony is not None:
                return _try_skill(ai, "cacophony",
                                 target_x=ai.position.x, target_y=ai.position.y)

    # --- Priority 1: Ballad of Might (AoE ally damage buff) ---
    ballad_action = _try_skill(ai, "ballad_of_might")
    if ballad_action is not None:
        ballad_def = get_skill("ballad_of_might")
        ballad_radius = ballad_def["effects"][0].get("radius", 2) if ballad_def else 2

        allies_in_radius = [
            a for a in allies
            if _chebyshev(ai_pos, (a.position.x, a.position.y)) <= ballad_radius
        ]
        # Don't stack — skip if most allies already have the buff
        unbuffed_allies = [
            a for a in allies_in_radius
            if not any(b.get("buff_id") == "ballad_of_might" for b in a.active_buffs)
        ]
        if len(allies_in_radius) >= _BALLAD_MIN_ALLIES and unbuffed_allies:
            return _try_skill(ai, "ballad_of_might",
                             target_x=ai.position.x, target_y=ai.position.y)

    # --- Priority 2: Dirge of Weakness (AoE enemy debuff) ---
    dirge_action = _try_skill(ai, "dirge_of_weakness")
    if dirge_action is not None and enemies:
        dirge_def = get_skill("dirge_of_weakness")
        dirge_range = dirge_def["range"] if dirge_def else 4
        dirge_radius = dirge_def["effects"][0].get("radius", 2) if dirge_def else 2

        # Find best AoE tile that hits the most enemies
        best_tile = None
        best_count = 0
        for enemy in enemies:
            ex, ey = enemy.position.x, enemy.position.y
            dist_to_tile = _chebyshev(ai_pos, (ex, ey))
            if dist_to_tile > dirge_range:
                continue
            if not has_line_of_sight(ai.position.x, ai.position.y, ex, ey, obstacles):
                continue
            # Count enemies within AoE radius of this tile
            count = sum(
                1 for e in enemies
                if _chebyshev((e.position.x, e.position.y), (ex, ey)) <= dirge_radius
                and not any(b.get("buff_id") == "dirge_of_weakness" for b in e.active_buffs)
            )
            if count > best_count:
                best_count = count
                best_tile = (ex, ey)

        if best_tile and best_count >= _DIRGE_MIN_ENEMIES:
            return _try_skill(ai, "dirge_of_weakness",
                             target_x=best_tile[0], target_y=best_tile[1])

    # --- Priority 3: Verse of Haste (cooldown reduction on ally) ---
    verse_action = _try_skill(ai, "verse_of_haste")
    if verse_action is not None:
        verse_def = get_skill("verse_of_haste")
        verse_range = verse_def["range"] if verse_def else 3

        # Score each ally by total cooldown debt (sum of remaining CDs > 0)
        verse_candidates: list[tuple[int, PlayerState]] = []
        for ally in allies:
            dist = _chebyshev(ai_pos, (ally.position.x, ally.position.y))
            if dist > verse_range:
                continue
            cd_debt = sum(
                cd for cd in ally.cooldowns.values() if cd > 0
            )
            if cd_debt >= _VERSE_MIN_COOLDOWN_DEBT:
                verse_candidates.append((cd_debt, ally))

        if verse_candidates:
            # Pick ally with highest cooldown debt
            verse_candidates.sort(key=lambda t: t[0], reverse=True)
            target = verse_candidates[0][1]
            return _try_skill(ai, "verse_of_haste",
                             target_x=target.position.x, target_y=target.position.y,
                             target_id=target.player_id)

    # --- Priority 4: Cacophony (AoE damage + slow when enemies within radius 2) ---
    cacophony_action = _try_skill(ai, "cacophony")
    if cacophony_action is not None:
        cacophony_def = get_skill("cacophony")
        cacophony_radius = cacophony_def["effects"][0].get("radius", 2) if cacophony_def else 2
        enemies_in_radius = [
            e for e in enemies
            if _chebyshev(ai_pos, (e.position.x, e.position.y)) <= cacophony_radius
        ]
        if enemies_in_radius:
            return _try_skill(ai, "cacophony",
                             target_x=ai.position.x, target_y=ai.position.y)

    # --- No skill to use → fall through to basic attack/move ---
    return None


# ---------------------------------------------------------------------------
# Phase 23D: Controller AI — Plague Doctor
# ---------------------------------------------------------------------------
# Enfeeble: minimum un-enfeebled enemies in AoE to justify casting
# Note: 1 is fine — -25% damage dealt on a single high-damage enemy (Blood Knight,
# Ranger) is extremely valuable, especially in 5v5 where focus fire is common.
_ENFEEBLE_MIN_ENEMIES = 1
# Miasma: minimum enemies in AoE to justify casting
_MIASMA_MIN_ENEMIES = 1
# Inoculate: ally HP ratio below which Inoculate is considered (when no DoTs)
_INOCULATE_HP_THRESHOLD = 0.50


def _controller_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Controller role (Plague Doctor): debuff enemies, apply DoTs, support allies.

    Phase 23D implementation.

    Priority:
      1. Plague Flask:  enemy in range without active DoT (prefer highest HP)
      2. Enfeeble:     1+ non-enfeebled enemies in AoE, off cooldown
      3. Miasma:       1+ enemies in range, off cooldown (slow value)
      4. Inoculate:    ally with active DoT OR ally below 50% HP
      5. Return None → fall through to basic attack logic

    Design:
      - Plague Doctor is the anti-Bard: debuffs enemies rather than buffing allies.
      - Plague Flask is the priority — consistent DoT damage on high-value targets.
      - Enfeeble is the crown jewel — AoE damage reduction on enemy clusters.
      - Miasma provides area denial via AoE damage + slow.
      - Inoculate is reactive support — cleanse ally DoTs or grant armor to wounded allies.
      - Midline positioning — stays near allies, doesn't charge.
    """
    ai_pos = (ai.position.x, ai.position.y)

    # Gather living allies (same team, not self)
    allies = [
        u for u in all_units.values()
        if u.is_alive and u.team == ai.team and u.player_id != ai.player_id
    ]

    # --- Priority 1: Plague Flask (single-target DoT on highest-HP un-poisoned enemy) ---
    flask_action = _try_skill(ai, "plague_flask")
    if flask_action is not None and enemies:
        flask_def = get_skill("plague_flask")
        flask_range = flask_def["range"] if flask_def else 5

        # Filter: in range, LOS, no active DoT (or DoT about to expire)
        candidates = []
        for enemy in enemies:
            dist = _chebyshev(ai_pos, (enemy.position.x, enemy.position.y))
            if dist > flask_range:
                continue
            # Check if enemy already has a healthy DoT (2+ turns remaining).
            # Allow refreshing DoTs with only 1 turn left to maintain uptime.
            has_healthy_dot = any(
                b.get("type") == "dot" and b.get("turns_remaining", 0) >= 2
                for b in enemy.active_buffs
            )
            if has_healthy_dot:
                continue
            if has_line_of_sight(ai.position.x, ai.position.y,
                                enemy.position.x, enemy.position.y, obstacles):
                candidates.append(enemy)

        if candidates:
            # Target highest HP to maximize DoT value
            candidates.sort(key=lambda e: e.hp, reverse=True)
            target = candidates[0]
            return _try_skill(ai, "plague_flask",
                             target_x=target.position.x, target_y=target.position.y,
                             target_id=target.player_id)

    # --- Priority 2: Enfeeble (AoE damage-dealt debuff on enemy clusters) ---
    enfeeble_action = _try_skill(ai, "enfeeble")
    if enfeeble_action is not None and enemies:
        enfeeble_def = get_skill("enfeeble")
        enfeeble_range = enfeeble_def["range"] if enfeeble_def else 4
        enfeeble_radius = enfeeble_def["effects"][0].get("radius", 2) if enfeeble_def else 2

        # Find best AoE tile that hits the most un-enfeebled enemies
        best_tile = None
        best_count = 0
        for enemy in enemies:
            ex, ey = enemy.position.x, enemy.position.y
            dist_to_tile = _chebyshev(ai_pos, (ex, ey))
            if dist_to_tile > enfeeble_range:
                continue
            if not has_line_of_sight(ai.position.x, ai.position.y, ex, ey, obstacles):
                continue
            # Count enemies within AoE radius of this tile that lack enfeeble
            count = sum(
                1 for e in enemies
                if _chebyshev((e.position.x, e.position.y), (ex, ey)) <= enfeeble_radius
                and not any(b.get("buff_id") == "enfeeble" for b in e.active_buffs)
            )
            if count > best_count:
                best_count = count
                best_tile = (ex, ey)

        if best_tile and best_count >= _ENFEEBLE_MIN_ENEMIES:
            return _try_skill(ai, "enfeeble",
                             target_x=best_tile[0], target_y=best_tile[1])

    # --- Priority 3: Miasma (AoE damage + slow) ---
    miasma_action = _try_skill(ai, "miasma")
    if miasma_action is not None and enemies:
        miasma_def = get_skill("miasma")
        miasma_range = miasma_def["range"] if miasma_def else 5
        miasma_radius = miasma_def["effects"][0].get("radius", 2) if miasma_def else 2

        # Find best AoE tile that hits the most enemies
        best_tile = None
        best_count = 0
        for enemy in enemies:
            ex, ey = enemy.position.x, enemy.position.y
            dist_to_tile = _chebyshev(ai_pos, (ex, ey))
            if dist_to_tile > miasma_range:
                continue
            if not has_line_of_sight(ai.position.x, ai.position.y, ex, ey, obstacles):
                continue
            # Count enemies within AoE radius of this tile
            count = sum(
                1 for e in enemies
                if _chebyshev((e.position.x, e.position.y), (ex, ey)) <= miasma_radius
            )
            if count > best_count:
                best_count = count
                best_tile = (ex, ey)

        if best_tile and best_count >= _MIASMA_MIN_ENEMIES:
            return _try_skill(ai, "miasma",
                             target_x=best_tile[0], target_y=best_tile[1])

    # --- Priority 4: Inoculate (buff+cleanse ally with DoT, or injured ally) ---
    inoc_action = _try_skill(ai, "inoculate")
    if inoc_action is not None:
        inoc_def = get_skill("inoculate")
        inoc_range = inoc_def["range"] if inoc_def else 3

        # Priority 4a: ally (or self) with active DoT
        dot_targets = []
        # Check self first
        self_has_dot = any(b.get("type") == "dot" for b in ai.active_buffs)
        if self_has_dot:
            dot_targets.append(ai)
        # Then allies
        for ally in allies:
            dist = _chebyshev(ai_pos, (ally.position.x, ally.position.y))
            if dist > inoc_range:
                continue
            ally_has_dot = any(b.get("type") == "dot" for b in ally.active_buffs)
            if ally_has_dot:
                dot_targets.append(ally)

        if dot_targets:
            target = dot_targets[0]
            return _try_skill(ai, "inoculate",
                             target_x=target.position.x, target_y=target.position.y,
                             target_id=target.player_id)

        # Priority 4b: ally below HP threshold (no DoT, but injured)
        injured_allies = []
        for ally in allies:
            dist = _chebyshev(ai_pos, (ally.position.x, ally.position.y))
            if dist > inoc_range:
                continue
            if ally.max_hp > 0 and (ally.hp / ally.max_hp) < _INOCULATE_HP_THRESHOLD:
                injured_allies.append(ally)

        if injured_allies:
            # Pick most injured
            injured_allies.sort(key=lambda a: a.hp / a.max_hp if a.max_hp > 0 else 1.0)
            target = injured_allies[0]
            return _try_skill(ai, "inoculate",
                             target_x=target.position.x, target_y=target.position.y,
                             target_id=target.player_id)

    # --- No skill to use → fall through to basic attack/move ---
    return None


# ---------------------------------------------------------------------------
# Phase 22D: Sustain DPS AI — Blood Knight
# ---------------------------------------------------------------------------
# Blood Frenzy HP threshold — must be below this ratio to activate
_BLOOD_FRENZY_HP_THRESHOLD = 0.40
# Sanguine Burst minimum adjacent enemies to justify AoE
_SANGUINE_BURST_MIN_ADJACENT = 2
# Crimson Veil: how close enemies need to be to justify pre-engage buff
_CRIMSON_VEIL_ENGAGE_RANGE = 2


# ---------------------------------------------------------------------------
# Phase 26D: Totemic Support AI — Shaman
# ---------------------------------------------------------------------------
# Healing Totem: place when allies below this HP% are within placement range
_HEALING_TOTEM_ALLY_HP_THRESHOLD = 0.70
# Healing Totem: minimum injured allies to justify placement
_HEALING_TOTEM_MIN_INJURED_ALLIES = 1
# Healing Totem: if any ally is below this HP%, bypass the min-injured check entirely
_HEALING_TOTEM_SEVERE_HP_THRESHOLD = 0.40
# Healing Totem: out-of-combat threshold (top-off between fights, like Confessor)
_HEALING_TOTEM_OOC_HP_THRESHOLD = 0.90
# Searing Totem: minimum enemies clustered to justify placement
# (Lowered from 2→1 so Shaman uses searing totem in single-target fights;
#  tile scoring still naturally prefers placements that catch multiple enemies)
_SEARING_TOTEM_MIN_ENEMIES = 1
# Soul Anchor: ally HP% below which we consider anchoring
_SOUL_ANCHOR_HP_THRESHOLD = 0.30
# Earthgrasp Totem: minimum enemies in radius to justify placement
_EARTHGRASP_MIN_ENEMIES = 1
# Earthgrasp Totem radius (matches skill config)
_EARTHGRASP_RADIUS = 2
# Totem placement range (matches skill config)
_TOTEM_PLACEMENT_RANGE = 4
# Totem effect radius (matches skill config)
_TOTEM_EFFECT_RADIUS = 2
# Frontline classes that Soul Anchor prefers to protect
_SOUL_ANCHOR_TANK_CLASSES = {"crusader", "revenant", "blood_knight", "hexblade"}
# Frontline/tank classes that Healing Totem placement prioritizes
_HEALING_TOTEM_TANK_CLASSES = {"crusader", "revenant", "blood_knight"}

# ---------------------------------------------------------------------------
# Phase 25D: Retaliation Tank AI — Revenant
# ---------------------------------------------------------------------------
# Undying Will HP threshold — cast preemptively when below this ratio
_UNDYING_WILL_HP_THRESHOLD = 0.40
# Grave Thorns minimum nearby enemies to trigger proactive thorns
# (Lowered from 2→1 so Revenant activates thorns in single-target fights too)
_GRAVE_THORNS_MIN_NEARBY = 1
# Grave Thorns nearby range check (enemies within this Chebyshev distance)
_GRAVE_THORNS_NEARBY_RANGE = 2
# Grave Chains max range (matches skill config)
_GRAVE_CHAINS_RANGE = 4
# Squishy class priority for Grave Chains targeting (higher = taunt first)
_GRAVE_CHAINS_SQUISHY_PRIORITY: dict[str, int] = {
    "mage": 5,
    "ranger": 4,
    "bard": 3,
    "confessor": 3,
    "plague_doctor": 3,
    "inquisitor": 2,
}


# ---------------------------------------------------------------------------
# Phase 26D: Totemic Support AI — Shaman
# ---------------------------------------------------------------------------

def _totemic_support_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    match_state=None,
) -> PlayerAction | None:
    """Totemic Support role (Shaman): triple totem placement, earthgrasp combos, soul anchor.

    Phase 26D implementation.

    Priority:
      1. Healing Totem:    1+ allies below 70% HP (or any below 40%) within range, no active healing totem → place near injured cluster
      2. Searing Totem:    2+ enemies clustered, no active searing totem → place near enemy cluster (combo with root)
      3. Earthgrasp Totem: 1+ enemies within range, no active earthgrasp totem → place root zone near enemies
      4. Soul Anchor:      frontline ally (or self) below 30% HP, no active anchor → cheat-death insurance
      5. Return None →     fall through to basic ranged attack/move logic

    Design:
      - Shaman is a backline support — places totems strategically, never charges.
      - Healing Totem is prioritized when allies are hurt (sustain the party).
      - Searing Totem is placed near enemy clusters for passive damage.
      - Earthgrasp Totem combos with Searing Totem — root enemies in the damage zone.
      - Soul Anchor is saved for frontline allies in real danger (below 30% HP).
      - Match state is needed to check for existing active totems.
    """
    ai_pos = (ai.position.x, ai.position.y)

    # Gather active totems for this Shaman from match_state
    my_totems: list[dict] = []
    if match_state is not None and hasattr(match_state, "totems"):
        my_totems = [t for t in match_state.totems if t.get("owner_id") == ai.player_id]

    has_healing_totem = any(t["type"] == "healing_totem" for t in my_totems)
    has_searing_totem = any(t["type"] == "searing_totem" for t in my_totems)
    has_earthgrasp_totem = any(t["type"] == "earthgrasp_totem" for t in my_totems)

    # Gather living allies (same team, not self)
    allies = [
        u for u in all_units.values()
        if u.is_alive and u.team == ai.team and u.player_id != ai.player_id
    ]

    if not enemies:
        # --- Out-of-combat: place Healing Totem to top off injured allies ---
        if not has_healing_totem:
            ht_action = _try_skill(ai, "healing_totem")
            if ht_action is not None:
                ooc_injured = [
                    a for a in allies + [ai]
                    if a.is_alive and a.max_hp > 0
                    and (a.hp / a.max_hp) < _HEALING_TOTEM_OOC_HP_THRESHOLD
                    and _chebyshev(ai_pos, (a.position.x, a.position.y)) <= _TOTEM_PLACEMENT_RANGE + _TOTEM_EFFECT_RADIUS
                ]
                if ooc_injured:
                    best_tile = _find_best_totem_tile(
                        ai, allies + [ai], [], obstacles, all_units,
                        _TOTEM_PLACEMENT_RANGE, _TOTEM_EFFECT_RADIUS,
                        totem_mode="healing",
                        match_state=match_state,
                        grid_width=grid_width, grid_height=grid_height,
                    )
                    if best_tile:
                        return _try_skill(
                            ai, "healing_totem",
                            target_x=best_tile[0], target_y=best_tile[1],
                        )
        return None

    # --- Priority 1: Healing Totem (place near injured ally cluster) ---
    if not has_healing_totem:
        ht_action = _try_skill(ai, "healing_totem")
        if ht_action is not None:
            # Count injured allies within placement range (including self)
            injured_nearby = [
                a for a in allies + [ai]
                if a.is_alive and a.max_hp > 0
                and (a.hp / a.max_hp) < _HEALING_TOTEM_ALLY_HP_THRESHOLD
                and _chebyshev(ai_pos, (a.position.x, a.position.y)) <= _TOTEM_PLACEMENT_RANGE + _TOTEM_EFFECT_RADIUS
            ]
            total_injured = len(injured_nearby)

            # Severe injury override: if ANY nearby ally is critically low, bypass min count
            has_severe_injury = any(
                a.max_hp > 0 and (a.hp / a.max_hp) < _HEALING_TOTEM_SEVERE_HP_THRESHOLD
                for a in injured_nearby
            )

            if total_injured >= _HEALING_TOTEM_MIN_INJURED_ALLIES or has_severe_injury:
                # Find best placement tile: maximize injured allies in heal radius, avoid enemies
                best_tile = _find_best_totem_tile(
                    ai, allies + [ai], enemies, obstacles, all_units,
                    _TOTEM_PLACEMENT_RANGE, _TOTEM_EFFECT_RADIUS,
                    totem_mode="healing",
                    match_state=match_state,
                    grid_width=grid_width, grid_height=grid_height,
                )
                if best_tile:
                    return _try_skill(
                        ai, "healing_totem",
                        target_x=best_tile[0], target_y=best_tile[1],
                    )

    # --- Priority 2: Searing Totem (place near enemy cluster) ---
    if not has_searing_totem:
        st_action = _try_skill(ai, "searing_totem")
        if st_action is not None:
            # Count enemies within placement range
            reachable_enemies = [
                e for e in enemies
                if _chebyshev(ai_pos, (e.position.x, e.position.y)) <= _TOTEM_PLACEMENT_RANGE + _TOTEM_EFFECT_RADIUS
            ]
            if len(reachable_enemies) >= _SEARING_TOTEM_MIN_ENEMIES:
                best_tile = _find_best_totem_tile(
                    ai, allies + [ai], enemies, obstacles, all_units,
                    _TOTEM_PLACEMENT_RANGE, _TOTEM_EFFECT_RADIUS,
                    totem_mode="searing",
                    match_state=match_state,
                    grid_width=grid_width, grid_height=grid_height,
                )
                if best_tile:
                    return _try_skill(
                        ai, "searing_totem",
                        target_x=best_tile[0], target_y=best_tile[1],
                    )

    # --- Priority 3: Earthgrasp Totem (place root totem near enemy cluster) ---
    if not has_earthgrasp_totem:
        eg_action = _try_skill(ai, "earthgrasp")
        if eg_action is not None:
            eg_def = get_skill("earthgrasp")
            eg_radius = eg_def["effects"][0].get("effect_radius", _EARTHGRASP_RADIUS) if eg_def else _EARTHGRASP_RADIUS

            # Count enemies within placement range
            reachable_enemies = [
                e for e in enemies
                if _chebyshev(ai_pos, (e.position.x, e.position.y)) <= _TOTEM_PLACEMENT_RANGE + _TOTEM_EFFECT_RADIUS
            ]
            if len(reachable_enemies) >= _EARTHGRASP_MIN_ENEMIES:
                best_tile = _find_best_totem_tile(
                    ai, allies + [ai], enemies, obstacles, all_units,
                    _TOTEM_PLACEMENT_RANGE, _TOTEM_EFFECT_RADIUS,
                    totem_mode="searing",  # Score based on enemy proximity (same logic)
                    match_state=match_state,
                    grid_width=grid_width, grid_height=grid_height,
                )
                if best_tile:
                    return _try_skill(
                        ai, "earthgrasp",
                        target_x=best_tile[0], target_y=best_tile[1],
                    )

    # --- Priority 4: Soul Anchor (cheat-death on endangered frontline ally) ---
    sa_action = _try_skill(ai, "soul_anchor")
    if sa_action is not None:
        # Check if we already have an active Soul Anchor on someone
        has_active_anchor = False
        for unit in all_units.values():
            if any(
                b.get("stat") == "soul_anchor" and b.get("caster_id") == ai.player_id
                for b in unit.active_buffs
            ):
                has_active_anchor = True
                break

        if not has_active_anchor:
            sa_def = get_skill("soul_anchor")
            sa_range = sa_def["range"] if sa_def else 4

            # Find endangered allies (or self) — below HP threshold
            anchor_candidates = []
            for candidate in allies + [ai]:
                if not candidate.is_alive or candidate.max_hp <= 0:
                    continue
                if candidate.hp / candidate.max_hp >= _SOUL_ANCHOR_HP_THRESHOLD:
                    continue
                dist = _chebyshev(ai_pos, (candidate.position.x, candidate.position.y))
                if dist > sa_range:
                    continue
                # Already has soul_anchor?
                has_anchor = any(b.get("stat") == "soul_anchor" for b in candidate.active_buffs)
                if has_anchor:
                    continue
                anchor_candidates.append(candidate)

            if anchor_candidates:
                # Prefer tanks/frontliners, then lowest HP%
                def _anchor_priority(u: PlayerState) -> tuple[int, float]:
                    is_tank = 0 if (u.class_id or "") in _SOUL_ANCHOR_TANK_CLASSES else 1
                    hp_pct = u.hp / u.max_hp if u.max_hp > 0 else 1.0
                    return (is_tank, hp_pct)

                anchor_candidates.sort(key=_anchor_priority)
                target = anchor_candidates[0]
                return _try_skill(
                    ai, "soul_anchor",
                    target_x=target.position.x, target_y=target.position.y,
                    target_id=target.player_id,
                )

    # --- No skill to use → fall through to basic ranged attack/move ---
    return None


def _find_best_totem_tile(
    ai: PlayerState,
    allies: list[PlayerState],
    enemies: list[PlayerState],
    obstacles: set[tuple[int, int]],
    all_units: dict[str, PlayerState],
    placement_range: int,
    effect_radius: int,
    totem_mode: str = "healing",
    match_state=None,
    grid_width: int = 20,
    grid_height: int = 20,
) -> tuple[int, int] | None:
    """Score empty tiles within placement range to find the best totem location.

    For healing totems: maximize injured allies within effect radius, penalize enemy proximity.
    For searing totems: maximize enemies within effect radius, bonus for rooted enemies.

    Returns the best (x, y) tile, or None if no valid tile found.
    """
    ai_pos = (ai.position.x, ai.position.y)
    best_tile = None
    best_score = -1

    # Occupied tiles (units)
    occupied_tiles = set()
    for u in all_units.values():
        if u.is_alive:
            occupied_tiles.add((u.position.x, u.position.y))

    # Existing totem tiles
    totem_tiles = set()
    if match_state is not None and hasattr(match_state, "totems"):
        for t in match_state.totems:
            totem_tiles.add((t["x"], t["y"]))

    # Evaluate candidate tiles: use enemy/ally positions as candidates
    # (rather than scanning all grid tiles, which would be expensive)
    candidate_tiles: set[tuple[int, int]] = set()

    if totem_mode == "healing":
        # Candidate tiles: near allies (wider ±2 search around each ally)
        for ally in allies:
            if not ally.is_alive:
                continue
            ax, ay = ally.position.x, ally.position.y
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    candidate_tiles.add((ax + dx, ay + dy))
        # Also add tiles around the Shaman's own position (totem near self)
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                candidate_tiles.add((ai.position.x + dx, ai.position.y + dy))
        # Add centroid of injured allies as a candidate area
        injured_allies = [
            a for a in allies if a.is_alive and a.max_hp > 0
            and (a.hp / a.max_hp) < _HEALING_TOTEM_ALLY_HP_THRESHOLD
        ]
        if injured_allies:
            cx = sum(a.position.x for a in injured_allies) // len(injured_allies)
            cy = sum(a.position.y for a in injured_allies) // len(injured_allies)
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    candidate_tiles.add((cx + dx, cy + dy))
    else:
        # Candidate tiles: near enemy positions
        for enemy in enemies:
            ex, ey = enemy.position.x, enemy.position.y
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    tx, ty = ex + dx, ey + dy
                    candidate_tiles.add((tx, ty))

    for tx, ty in candidate_tiles:
        # Must be within grid bounds
        if tx < 0 or ty < 0 or tx >= grid_width or ty >= grid_height:
            continue
        # Must be within placement range from caster (Chebyshev)
        if _chebyshev(ai_pos, (tx, ty)) > placement_range:
            continue
        # Must not be obstacle, occupied, or existing totem
        if (tx, ty) in obstacles or (tx, ty) in occupied_tiles or (tx, ty) in totem_tiles:
            continue
        # Must have LOS from caster
        if not has_line_of_sight(ai.position.x, ai.position.y, tx, ty, obstacles):
            continue

        score = 0
        if totem_mode == "healing":
            for ally in allies:
                if not ally.is_alive:
                    continue
                dist = _chebyshev((ally.position.x, ally.position.y), (tx, ty))
                if dist <= effect_radius:
                    is_tank = (getattr(ally, "class_id", "") or "") in _HEALING_TOTEM_TANK_CLASSES
                    if ally.max_hp > 0 and (ally.hp / ally.max_hp) < _HEALING_TOTEM_ALLY_HP_THRESHOLD:
                        score += 5 if is_tank else 3  # Injured tank +5, injured ally +3
                    else:
                        score += 2 if is_tank else 1  # Healthy tank +2, healthy ally +1
            # Penalize if enemies are very close to the totem (it'll get destroyed)
            for enemy in enemies:
                e_dist = _chebyshev((enemy.position.x, enemy.position.y), (tx, ty))
                if e_dist <= 1:
                    score -= 2  # Adjacent enemy — totem will be destroyed quickly
        else:
            # Searing mode
            for enemy in enemies:
                dist = _chebyshev((enemy.position.x, enemy.position.y), (tx, ty))
                if dist <= effect_radius:
                    score += 3  # Enemy in damage radius
                    # Bonus for rooted enemies (can't escape the damage zone)
                    is_rooted = any(b.get("stat") == "rooted" for b in enemy.active_buffs)
                    if is_rooted:
                        score += 2
            # Slight penalty if ally is very close (offensive positioning)
            for ally in allies:
                if not ally.is_alive:
                    continue
                a_dist = _chebyshev((ally.position.x, ally.position.y), (tx, ty))
                if a_dist <= 1:
                    score -= 1

        if score > best_score:
            best_score = score
            best_tile = (tx, ty)

    return best_tile if best_score > 0 else None


def _retaliation_tank_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Retaliation Tank role (Revenant): aggressive punishment tank.

    Phase 25D implementation.  Balance-pass revision: Soul Rend promoted to
    priority 2 so the Revenant leads with damage instead of spending opening
    turns on self-buffs.

    Priority:
      1. Undying Will:  HP < 40% AND no cheat_death buff active → preemptive safety net
      2. Soul Rend:     adjacent enemy exists → damage + slow (lead with damage)
      3. Grave Thorns:  enemies within 2 tiles AND no thorns buff active → retaliation aura
      4. Grave Chains:  ranged/squishy enemy within 4 tiles, not adjacent → taunt into melee
      5. Return None →  fall through to basic melee attack/move logic

    Design:
      - Revenant plays aggressively — charges into enemy groups and punishes focus fire.
      - Undying Will is the panic button: cast preemptively when wounded, not reactively.
      - Soul Rend opens combat with real damage + a slow, establishing threat immediately.
      - Grave Thorns goes up turn 2 — still near-permanent uptime (4/5 = 80%).
      - Grave Chains pulls ranged enemies into melee where thorns + auto-attacks punish them.
      - No retreat when Undying Will is available — the safety net emboldens aggression.
    """
    if not enemies:
        return None

    ai_pos = (ai.position.x, ai.position.y)
    ai_pos_obj = Position(x=ai.position.x, y=ai.position.y)

    # Pre-compute adjacent enemies (used by multiple priorities)
    adjacent_enemies = [
        e for e in enemies
        if is_adjacent(ai_pos_obj, Position(x=e.position.x, y=e.position.y))
    ]

    # --- Priority 1: Undying Will (cheat death when HP < 40%) ---
    has_cheat_death = any(
        b.get("stat") == "cheat_death" for b in ai.active_buffs
    )
    if not has_cheat_death and ai.max_hp > 0 and (ai.hp / ai.max_hp) < _UNDYING_WILL_HP_THRESHOLD:
        uw_action = _try_skill(ai, "undying_will")
        if uw_action is not None:
            return _try_skill(
                ai, "undying_will",
                target_x=ai.position.x, target_y=ai.position.y,
            )

    # --- Priority 2: Soul Rend (melee slow on adjacent enemy — lead with damage) ---
    if adjacent_enemies:
        sr_action = _try_skill(ai, "soul_rend")
        if sr_action is not None:
            # Target lowest-HP adjacent enemy (focus fire to secure kills)
            target = min(adjacent_enemies, key=lambda e: e.hp)
            return _try_skill(
                ai, "soul_rend",
                target_x=target.position.x, target_y=target.position.y,
                target_id=target.player_id,
            )

    # --- Priority 3: Grave Thorns (self-buff when enemies nearby) ---
    has_thorns = any(
        b.get("stat") == "thorns_damage" for b in ai.active_buffs
    )
    if not has_thorns:
        nearby_enemies = [
            e for e in enemies
            if _chebyshev(ai_pos, (e.position.x, e.position.y)) <= _GRAVE_THORNS_NEARBY_RANGE
        ]
        if len(nearby_enemies) >= _GRAVE_THORNS_MIN_NEARBY:
            gt_action = _try_skill(ai, "grave_thorns")
            if gt_action is not None:
                return _try_skill(
                    ai, "grave_thorns",
                    target_x=ai.position.x, target_y=ai.position.y,
                )

    # --- Priority 4: Grave Chains (ranged taunt on squishy/ranged enemy) ---
    gc_action = _try_skill(ai, "grave_chains")
    if gc_action is not None:
        # Find non-adjacent enemies within Grave Chains range (4 tiles) with LOS
        taunt_candidates = []
        for enemy in enemies:
            dist = _chebyshev(ai_pos, (enemy.position.x, enemy.position.y))
            if dist < 2 or dist > _GRAVE_CHAINS_RANGE:
                continue  # Skip adjacent (already in melee) and out-of-range
            # Check for existing taunt (forced_target) — don't re-taunt
            already_taunted = any(
                b.get("stat") == "forced_target" for b in enemy.active_buffs
            )
            if already_taunted:
                continue
            if has_line_of_sight(ai.position.x, ai.position.y,
                                enemy.position.x, enemy.position.y, obstacles):
                taunt_candidates.append(enemy)

        if taunt_candidates:
            # Score each candidate: squishy class priority + ranged bonus
            def _taunt_score(e: PlayerState) -> int:
                score = _GRAVE_CHAINS_SQUISHY_PRIORITY.get(e.class_id or "", 0)
                # Bonus for ranged enemies (ranged_range > 0)
                if getattr(e, "ranged_range", 0) > 0:
                    score += 3
                return score

            taunt_candidates.sort(key=_taunt_score, reverse=True)
            target = taunt_candidates[0]
            return _try_skill(
                ai, "grave_chains",
                target_x=target.position.x, target_y=target.position.y,
                target_id=target.player_id,
            )

    # --- No skill to use → fall through to basic melee attack/move ---
    return None


def _sustain_dps_skill_logic(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> PlayerAction | None:
    """Sustain DPS role (Blood Knight): aggressive melee lifesteal with self-sustain.

    Phase 22D implementation.

    Priority:
      1. Blood Frenzy:   if HP < 40% AND off cooldown → emergency heal + damage buff
      2. Crimson Veil:   if off cooldown AND enemies adjacent or within 2 tiles → damage buff + HoT
      3. Sanguine Burst: if 2+ enemies adjacent AND off cooldown → AoE lifesteal
      4. Blood Strike:   if 1+ enemy adjacent AND off cooldown → single-target lifesteal
      5. Return None →   fall through to basic melee attack/move logic

    Design:
      - Blood Knight plays aggressively — charges into melee and sustains through lifesteal.
      - Blood Frenzy is the panic button: only activates when wounded, heals + damage spike.
      - Crimson Veil is the "turn on" buff: damage + HoT when in or entering melee.
      - Sanguine Burst is the pack-clearing AoE: scales with enemies hit.
      - Blood Strike is the bread-and-butter sustain on a single adjacent target.
      - No retreat logic — Blood Knight fights to the death (sustain or die).
    """
    if not enemies:
        return None

    ai_pos = (ai.position.x, ai.position.y)
    ai_pos_obj = Position(x=ai.position.x, y=ai.position.y)

    # Pre-compute adjacent enemies (used by multiple priorities)
    adjacent_enemies = [
        e for e in enemies
        if is_adjacent(ai_pos_obj, Position(x=e.position.x, y=e.position.y))
    ]

    # --- Priority 1: Blood Frenzy (emergency heal + damage when low HP) ---
    if ai.max_hp > 0 and (ai.hp / ai.max_hp) < _BLOOD_FRENZY_HP_THRESHOLD:
        frenzy_action = _try_skill(ai, "blood_frenzy")
        if frenzy_action is not None:
            return _try_skill(
                ai, "blood_frenzy",
                target_x=ai.position.x, target_y=ai.position.y,
            )

    # --- Priority 2: Crimson Veil (in-combat damage buff + HoT) ---
    # Cast when enemies are adjacent OR within engage range (2 tiles).
    # The buff amplifies Blood Strike and auto-attack damage, so it's
    # most valuable when already in melee or about to be. Previously this
    # was a pre-engage-only buff (NOT adjacent), but that caused the BK to
    # waste a turn buffing at range 2 instead of closing to melee — leading
    # to back-and-forth movement without ever auto-attacking.
    # Skip if Crimson Veil buff is already active — don't waste a turn
    # re-buffing when the damage multiplier + HoT are still running.
    has_crimson_veil = any(
        b.get("buff_id") == "crimson_veil" for b in ai.active_buffs
    )
    if not has_crimson_veil:
        veil_action = _try_skill(ai, "crimson_veil")
        if veil_action is not None:
            nearby_enemies = [
                e for e in enemies
                if _chebyshev(ai_pos, (e.position.x, e.position.y)) <= _CRIMSON_VEIL_ENGAGE_RANGE
            ]
            if adjacent_enemies or nearby_enemies:
                return _try_skill(
                    ai, "crimson_veil",
                    target_x=ai.position.x, target_y=ai.position.y,
                )

    # --- Priority 3: Sanguine Burst (AoE lifesteal when 2+ adjacent) ---
    if len(adjacent_enemies) >= _SANGUINE_BURST_MIN_ADJACENT:
        burst_action = _try_skill(ai, "sanguine_burst")
        if burst_action is not None:
            return _try_skill(
                ai, "sanguine_burst",
                target_x=ai.position.x, target_y=ai.position.y,
            )

    # --- Priority 4: Blood Strike (single-target lifesteal on adjacent enemy) ---
    # Skip Blood Strike when at full HP — the lifesteal heal is entirely
    # wasted as overheal. Save the cooldown for when sustain actually
    # matters; auto-attack deals comparable damage without burning the CD.
    if adjacent_enemies and (ai.max_hp <= 0 or ai.hp < ai.max_hp):
        strike_action = _try_skill(ai, "blood_strike")
        if strike_action is not None:
            # Target lowest-HP adjacent enemy (focus fire to secure kills)
            target = min(adjacent_enemies, key=lambda e: e.hp)
            return _try_skill(
                ai, "blood_strike",
                target_x=target.position.x,
                target_y=target.position.y,
                target_id=target.player_id,
            )

    # --- No skill to use → fall through to basic melee attack/move ---
    return None


def _decide_skill_usage(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    match_state=None,
) -> PlayerAction | None:
    """Evaluate whether the AI should use a skill instead of basic attack.

    Dispatches to role-specific handlers based on class_id.
    Returns SKILL action or None (fall through to basic attack logic).

    Future-proof: New classes map to existing role handlers via _CLASS_ROLE_MAP.

    Args:
        match_state: Phase 26D — optional MatchState for totem-aware AI
                     (Shaman totemic_support needs match_state.totems).
    """
    class_id = ai.class_id
    if not class_id:
        return None

    role = _get_role_for_class(class_id)
    if role is None:
        return None

    if role == "support":
        return _support_skill_logic(ai, enemies, all_units, grid_width, grid_height, obstacles)
    elif role == "tank":
        return _tank_skill_logic(ai, enemies, all_units, obstacles)
    elif role == "ranged_dps":
        return _ranged_dps_skill_logic(ai, enemies, all_units, obstacles)
    elif role == "hybrid_dps":
        return _hybrid_dps_skill_logic(ai, enemies, all_units, grid_width, grid_height, obstacles)
    elif role == "scout":
        return _scout_skill_logic(ai, enemies, all_units, grid_width, grid_height, obstacles)
    elif role == "caster_dps":
        return _caster_dps_skill_logic(ai, enemies, all_units, grid_width, grid_height, obstacles)
    elif role == "offensive_support":
        # Phase 21D: Bard — buff allies, debuff enemies, cooldown reduction, self-peel
        return _offensive_support_skill_logic(ai, enemies, all_units, grid_width, grid_height, obstacles)
    elif role == "sustain_dps":
        # Phase 22D: Blood Knight — aggressive melee lifesteal, self-sustain
        return _sustain_dps_skill_logic(ai, enemies, all_units, grid_width, grid_height, obstacles)
    elif role == "controller":
        # Phase 23D: Plague Doctor — AoE debuffs, DoTs, ally cleanse
        return _controller_skill_logic(ai, enemies, all_units, grid_width, grid_height, obstacles)
    elif role == "retaliation_tank":
        # Phase 25D: Revenant — thorns, taunt, cheat death, melee slow
        return _retaliation_tank_skill_logic(ai, enemies, all_units, grid_width, grid_height, obstacles)
    elif role == "totemic_support":
        # Phase 26D: Shaman — dual totems, soul anchor, earthgrasp root
        return _totemic_support_skill_logic(ai, enemies, all_units, grid_width, grid_height, obstacles, match_state=match_state)
    elif role == "passive_only":
        # Phase 18I: Passive-only units (Demon Enrage, Imp Frenzy)
        # Their skills are resolved in _resolve_auras, not here.
        return None

    return None
