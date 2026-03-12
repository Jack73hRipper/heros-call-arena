"""
AI Memory & Target Selection — Enemy tracking and ally reinforcement.

Extracted from ai_behavior.py (P1 refactoring — pure mechanical move).

Implements:
  - Last-known enemy position memory (_enemy_memory)
  - Memory pursuit (path toward remembered enemy positions)
  - Ally reinforcement (move to help teammates in combat)
  - Weighted target selection (prioritize low-HP and threatening enemies)
"""

from __future__ import annotations

from app.models.player import PlayerState, Position
from app.models.actions import PlayerAction, ActionType
from app.core.combat import is_adjacent
from app.core.ai_pathfinding import _build_occupied_set, get_next_step_toward


# ---------------------------------------------------------------------------
# Last-Known Enemy Memory (module-level, keyed by AI player_id)
# ---------------------------------------------------------------------------
# {ai_id: {enemy_id: (x, y, turns_since_seen)}}
_enemy_memory: dict[str, dict[str, tuple[int, int, int]]] = {}

# How many turns AI will pursue a last-known position before giving up
_MEMORY_EXPIRY_TURNS = 3


# ---------------------------------------------------------------------------
# Enemy Memory Helpers
# ---------------------------------------------------------------------------

def _update_enemy_memory(
    ai_id: str,
    visible_enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
) -> None:
    """Update the last-known position memory for enemies.

    - Enemies currently visible: store/refresh their position (age = 0)
    - Enemies not visible: increment age by 1
    - Enemies dead or expired: remove from memory
    """
    if ai_id not in _enemy_memory:
        _enemy_memory[ai_id] = {}

    mem = _enemy_memory[ai_id]

    # Refresh positions of currently visible enemies
    visible_ids = {e.player_id for e in visible_enemies}
    for enemy in visible_enemies:
        mem[enemy.player_id] = (enemy.position.x, enemy.position.y, 0)

    # Age and prune entries for enemies we can't see
    for eid in list(mem.keys()):
        if eid in visible_ids:
            continue
        # Check if enemy is dead — remove immediately
        enemy_unit = all_units.get(eid)
        if not enemy_unit or not enemy_unit.is_alive:
            del mem[eid]
            continue
        # Age the memory
        x, y, age = mem[eid]
        if age + 1 > _MEMORY_EXPIRY_TURNS:
            del mem[eid]
        else:
            mem[eid] = (x, y, age + 1)


def _pursue_memory_target(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
) -> PlayerAction | None:
    """If AI remembers where an enemy was last seen, path toward that spot.

    Returns a MOVE action toward the freshest memory target, or None if
    memory is empty or all targets are expired.
    """
    ai_id = ai.player_id
    mem = _enemy_memory.get(ai_id, {})
    if not mem:
        return None

    ai_pos = (ai.position.x, ai.position.y)
    # Phase 7A-3: Use _build_occupied_set with pending_moves prediction
    occupied = _build_occupied_set(all_units, ai_id, pending_moves)

    # Pick the freshest (lowest age) memory target, break ties by distance
    best_eid = min(
        mem.keys(),
        key=lambda eid: (mem[eid][2], abs(mem[eid][0] - ai_pos[0]) + abs(mem[eid][1] - ai_pos[1])),
    )
    tx, ty, _age = mem[best_eid]

    # If we've reached the last-known position and enemy isn't there, clear it
    if ai_pos == (tx, ty):
        del mem[best_eid]
        return None

    next_step = get_next_step_toward(
        ai_pos, (tx, ty), grid_width, grid_height, obstacles, occupied
    )
    if next_step:
        return PlayerAction(
            player_id=ai_id,
            action_type=ActionType.MOVE,
            target_x=next_step[0],
            target_y=next_step[1],
        )

    # Can't path there — clear this memory entry
    del mem[best_eid]
    return None


# ---------------------------------------------------------------------------
# Ally Reinforcement
# ---------------------------------------------------------------------------

def _reinforce_ally(
    ai: PlayerState,
    all_units: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    pending_moves: dict[str, tuple[tuple[int, int], tuple[int, int]]] | None = None,
) -> PlayerAction | None:
    """If a teammate is in combat (adjacent to an enemy), path toward them.

    This makes AI feel cooperative — idle AI rush to help allies in fights
    instead of wandering aimlessly.

    Returns a MOVE action toward the embattled ally, or None if no ally
    needs help.
    """
    # Room-bound enemies should not leave their room to help distant allies.
    # This prevents cross-room aggro cascading.
    if getattr(ai, 'room_id', None):
        return None

    ai_id = ai.player_id
    ai_pos = (ai.position.x, ai.position.y)

    # Find allies that are adjacent to at least one enemy
    allies_in_combat: list[PlayerState] = []
    for unit in all_units.values():
        if not unit.is_alive:
            continue
        if unit.player_id == ai_id:
            continue
        if unit.team != ai.team:
            continue  # Not an ally
        # Check if this ally is adjacent to any enemy
        ally_pos = Position(x=unit.position.x, y=unit.position.y)
        for other in all_units.values():
            if not other.is_alive:
                continue
            if other.team == ai.team:
                continue  # Same team, skip
            if is_adjacent(ally_pos, Position(x=other.position.x, y=other.position.y)):
                allies_in_combat.append(unit)
                break  # This ally is confirmed in combat

    if not allies_in_combat:
        return None

    # Pick the nearest embattled ally
    nearest_ally = min(
        allies_in_combat,
        key=lambda a: abs(a.position.x - ai_pos[0]) + abs(a.position.y - ai_pos[1]),
    )

    occupied = _build_occupied_set(all_units, ai_id, pending_moves)

    next_step = get_next_step_toward(
        ai_pos,
        (nearest_ally.position.x, nearest_ally.position.y),
        grid_width, grid_height,
        obstacles, occupied,
    )
    if next_step:
        return PlayerAction(
            player_id=ai_id,
            action_type=ActionType.MOVE,
            target_x=next_step[0],
            target_y=next_step[1],
        )

    return None


# ---------------------------------------------------------------------------
# Weighted Target Selection
# ---------------------------------------------------------------------------

def _pick_best_target(
    ai: PlayerState,
    enemies: list[PlayerState],
    all_units: dict[str, PlayerState],
) -> PlayerState:
    """Pick the best enemy target using weighted scoring.

    Phase 12: Taunt enforcement — if the AI is taunted, it MUST target the taunter
    (if the taunter is in the enemies list and still alive).

    Scoring factors:
      - Low HP bonus: +5 if target is below 30% max HP (focus fire wounded)
      - Threat bonus: +3 if target is adjacent to a teammate (protect allies)
      - Distance penalty: -1 per Chebyshev tile of distance

    Returns the highest-scored enemy.
    """
    # Phase 12: Taunt override — forced target selection
    from app.core.skills import is_taunted
    taunted, taunt_source_id = is_taunted(ai)
    if taunted and taunt_source_id:
        for enemy in enemies:
            if enemy.player_id == taunt_source_id and enemy.is_alive:
                return enemy

    ai_pos = (ai.position.x, ai.position.y)

    def target_score(enemy: PlayerState) -> float:
        score = 0.0
        dist = max(
            abs(enemy.position.x - ai_pos[0]),
            abs(enemy.position.y - ai_pos[1]),
        )
        # Distance penalty
        score -= dist

        # Low HP bonus — focus fire on wounded targets
        if enemy.max_hp > 0 and (enemy.hp / enemy.max_hp) < 0.30:
            score += 5.0

        # Threat bonus — enemy is adjacent to one of our allies (protect them)
        enemy_pos = Position(x=enemy.position.x, y=enemy.position.y)
        for unit in all_units.values():
            if not unit.is_alive:
                continue
            if unit.player_id == ai.player_id:
                continue
            if unit.team != ai.team:
                continue  # Not an ally
            if is_adjacent(Position(x=unit.position.x, y=unit.position.y), enemy_pos):
                score += 3.0
                break  # Only count once

        return score

    return max(enemies, key=target_score)
