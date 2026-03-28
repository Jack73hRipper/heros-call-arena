"""
Movement Phase — Phase 1: Cooperative batch movement resolution.

Handles stunned/slowed/channeling/rooted checks, then delegates to resolve_movement_batch.
Phase 2 (Friendly Swap): AI anti-oscillation cooldown prevents AI heroes from
swapping back-and-forth on alternating ticks.
Phase 26C: Root CC — rooted units cannot move but can still attack/use skills.
Phase 32E: Directional swap cooldown — only blocks a swap if the same A↔B pair
would reverse their previous swap (true oscillation detection).
"""

from __future__ import annotations

from app.models.player import PlayerState
from app.models.actions import PlayerAction, ActionType, ActionResult
from app.core.combat import resolve_movement_batch
from app.core.skills import is_stunned, is_slowed, is_rooted
from app.core.turn_phases.portal_phase import _is_channeling

# ---------------------------------------------------------------------------
# Phase 32E: Directional Swap Cooldown (replaces Phase 2E blanket cooldown)
# ---------------------------------------------------------------------------
# Tracks {frozenset(pid_a, pid_b): last_turn_swapped} — records the specific
# *pair* that swapped.  A different follower swapping through the same ally
# on the next turn is allowed — only the exact same pair reversing is blocked.
_last_swap_pair: dict[frozenset, int] = {}
_SWAP_COOLDOWN = 2  # Same pair cannot swap again for 2 turns


def reset_swap_cooldowns() -> None:
    """Reset swap cooldown tracking (for test isolation)."""
    _last_swap_pair.clear()


def _resolve_movement(
    move_actions: list[PlayerAction],
    players: dict[str, PlayerState],
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
    results: list[ActionResult],
    portal_context: dict | None = None,
    current_turn: int = 0,
    interacting_pids: set[str] | None = None,
) -> dict[tuple[int, int], str]:
    """Phase 1 — Cooperative batch movement resolution.

    Args:
        current_turn: The current turn number (used for AI swap cooldown).
        interacting_pids: Player IDs with pending INTERACT actions this turn
            (e.g. opening doors). These units must not be displaced by swap
            injection — doing so would move them away from the door before
            Phase 1.5 resolves their INTERACT, causing it to fail.

    Returns:
        pre_move_occupants: Snapshot of unit positions before movement,
            used by melee phase for target tracking.
    """
    # Pre-movement snapshot (for melee target tracking)
    pre_move_occupants: dict[tuple[int, int], str] = {}
    for p in players.values():
        if p.is_alive and not p.extracted:
            pre_move_occupants[(p.position.x, p.position.y)] = p.player_id

    # Build move intents for the batch resolver
    move_intents: list[dict] = []
    for action in move_actions:
        player = players.get(action.player_id)
        if not player or not player.is_alive:
            continue
        if action.target_x is None or action.target_y is None:
            continue
        # Phase 12C: Extracted heroes skip all phases
        if player.extracted:
            continue
        # Phase 12C: Channeling players cannot move
        if portal_context and _is_channeling(player.player_id, portal_context):
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.MOVE,
                success=False,
                message=f"{player.username} is channeling and cannot move!",
            ))
            continue
        # Phase 12: Stunned units cannot move
        if is_stunned(player):
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.MOVE,
                success=False,
                message=f"{player.username} is stunned and cannot move!",
            ))
            continue
        # Phase 12: Slowed units cannot move
        if is_slowed(player):
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.MOVE,
                success=False,
                message=f"{player.username} is slowed and cannot move!",
            ))
            continue
        # Phase 26C: Rooted units cannot move (can still attack/use skills)
        if is_rooted(player):
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.MOVE,
                success=False,
                message=f"{player.username} is rooted and cannot move!",
            ))
            continue
        move_intents.append({
            "player_id": action.player_id,
            "target": (action.target_x, action.target_y),
        })

    # --- Friendly Swap Injection ---
    # If a mover targets a same-team stationary ally (not in hold stance,
    # not stunned/slowed/channeling), inject a reciprocal MOVE so the
    # batch resolver handles it as a swap.
    moving_pids = {mi["player_id"] for mi in move_intents}
    swap_intents: list[dict] = []
    injected_allies: set[str] = set()  # Prevent duplicate injections

    for mi in move_intents:
        mover = players.get(mi["player_id"])
        if not mover:
            continue
        target_tile = mi["target"]
        # Find who's standing on the target tile
        for p in players.values():
            if not p.is_alive or getattr(p, 'extracted', False):
                continue
            if p.player_id == mi["player_id"]:
                continue
            if (p.position.x, p.position.y) != target_tile:
                continue
            # Found occupant on target tile
            if p.team != mover.team:
                break  # Cross-team — no swap
            if p.player_id in moving_pids:
                break  # Already moving — batch resolver handles naturally
            if p.player_id in injected_allies:
                break  # Already being swapped by another mover
            if getattr(p, 'ai_stance', None) == 'hold':
                break  # Hold stance — refuse swap
            # Don't swap stunned/slowed/channeling/rooted allies
            if is_stunned(p) or is_slowed(p) or is_rooted(p):
                break
            if portal_context and _is_channeling(p.player_id, portal_context):
                break
            # Phase 30A: Don't swap units that have a pending INTERACT action
            # (e.g. opening a door). The swap would displace them before
            # Phase 1.5 resolves the INTERACT, causing the adjacency check
            # to fail silently.
            if interacting_pids and p.player_id in interacting_pids:
                break
            # Phase 32E: Directional swap cooldown — only for AI movers.
            # Player-initiated swaps are always allowed.  Only blocks
            # the exact same A↔B pair from swapping again within the
            # cooldown window (prevents true oscillation while allowing
            # sequential filing through corridors).
            if mover.unit_type != 'human' and current_turn > 0:
                pair_key = frozenset((mover.player_id, p.player_id))
                last_tick = _last_swap_pair.get(pair_key, -_SWAP_COOLDOWN - 1)
                if current_turn - last_tick < _SWAP_COOLDOWN:
                    break  # Same pair swapped too recently — skip
            # Inject reciprocal move: ally → mover's current position
            mover_pos = (mover.position.x, mover.position.y)
            swap_intents.append({
                "player_id": p.player_id,
                "target": mover_pos,
            })
            injected_allies.add(p.player_id)
            break

    move_intents.extend(swap_intents)

    # Track which player IDs were injected for swap detection in results
    swap_injected_pids = {si["player_id"] for si in swap_intents}

    batch_results = resolve_movement_batch(
        move_intents, players, grid_width, grid_height, obstacles,
    )

    # Build a lookup of successful moves for swap message detection
    successful_moves: dict[str, dict] = {}
    for br in batch_results:
        if br["success"]:
            successful_moves[br["player_id"]] = br

    for br in batch_results:
        player = players.get(br["player_id"])
        if not player:
            continue
        if br["success"]:
            old_pos = br["from"]
            new_pos = br["to"]
            player.position.x = new_pos[0]
            player.position.y = new_pos[1]
            # Detect swap: if this was an injected ally, find who triggered it
            message = f"{player.username} moved to ({new_pos[0]}, {new_pos[1]})"
            if br["player_id"] in swap_injected_pids:
                # Phase 32E: Record swap cooldown for the specific pair
                # Find the mover who triggered this swap
                for other_pid, other_br in successful_moves.items():
                    if other_pid == br["player_id"]:
                        continue
                    if other_br["to"] == old_pos and other_br["from"] == new_pos:
                        other_player = players.get(other_pid)
                        if other_player:
                            message = f"{player.username} swapped places with {other_player.username}"
                            # Record cooldown for this specific pair
                            if current_turn > 0:
                                pair_key = frozenset((br["player_id"], other_pid))
                                _last_swap_pair[pair_key] = current_turn
                        break
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.MOVE,
                success=True,
                message=message,
                from_x=old_pos[0], from_y=old_pos[1],
                to_x=new_pos[0], to_y=new_pos[1],
            ))
        else:
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.MOVE,
                success=False,
                message=f"{player.username} failed to move",
            ))

    return pre_move_occupants
