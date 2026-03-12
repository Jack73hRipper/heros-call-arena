"""
Interaction Phase — Phase 1.5 + 1.75: Doors and loot/chest interaction.

Phase 4B-2: Door toggle (open/close).
Phase 4D-2: Chest interaction + ground item pickup.
Phase 16B: Affix-based chest loot generation.
"""

from __future__ import annotations

from app.models.player import PlayerState
from app.models.actions import PlayerAction, ActionType, ActionResult
from app.models.items import INVENTORY_MAX_CAPACITY
from app.core.loot import generate_chest_loot
from app.core.turn_phases.helpers import _is_chebyshev_adjacent


def _resolve_doors(
    interact_actions: list[PlayerAction],
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    door_states: dict[str, str] | None,
    results: list[ActionResult],
    door_changes: list[dict],
) -> None:
    """Phase 1.5 — Toggle doors open/closed via INTERACT actions."""
    if door_states is None:
        return

    for action in interact_actions:
        player = players.get(action.player_id)
        if not player or not player.is_alive:
            continue
        if action.target_x is None or action.target_y is None:
            continue

        door_key = f"{action.target_x},{action.target_y}"

        # Must be adjacent (8-directional / Chebyshev distance 1)
        if not _is_chebyshev_adjacent(player.position, action.target_x, action.target_y):
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.INTERACT,
                success=False,
                message=f"{player.username} cannot interact — not adjacent",
            ))
            continue

        current_state = door_states.get(door_key)

        # Must be a door (either open or closed)
        if current_state not in ("closed", "open"):
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.INTERACT,
                success=False,
                message=f"{player.username} nothing to interact with here",
            ))
            continue

        if current_state == "closed":
            # Open the door
            door_states[door_key] = "open"
            obstacles.discard((action.target_x, action.target_y))
            door_changes.append({
                "x": action.target_x,
                "y": action.target_y,
                "state": "open",
            })
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.INTERACT,
                success=True,
                message=f"{player.username} opened a door",
                to_x=action.target_x,
                to_y=action.target_y,
            ))
        else:
            # Close the door (current_state == "open")
            door_states[door_key] = "closed"
            obstacles.add((action.target_x, action.target_y))
            door_changes.append({
                "x": action.target_x,
                "y": action.target_y,
                "state": "closed",
            })
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.INTERACT,
                success=True,
                message=f"{player.username} closed a door",
                to_x=action.target_x,
                to_y=action.target_y,
            ))


def _resolve_loot(
    loot_actions: list[PlayerAction],
    players: dict[str, PlayerState],
    chest_states: dict[str, str] | None,
    ground_items: dict[str, list] | None,
    results: list[ActionResult],
    chest_opened: list[dict],
    items_picked_up: list[dict],
    floor_number: int = 1,
) -> None:
    """Phase 1.75 — Chest interaction + ground item pickup."""
    for action in loot_actions:
        player = players.get(action.player_id)
        if not player or not player.is_alive:
            continue

        # Case 1: Chest interaction — target is an unopened chest tile
        if action.target_x is not None and action.target_y is not None and chest_states is not None:
            chest_key = f"{action.target_x},{action.target_y}"
            if chest_states.get(chest_key) == "unopened":
                # Must be adjacent (8-directional / Chebyshev)
                if not _is_chebyshev_adjacent(player.position, action.target_x, action.target_y):
                    results.append(ActionResult(
                        player_id=player.player_id,
                        username=player.username,
                        action_type=ActionType.LOOT,
                        success=False,
                        message=f"{player.username} cannot loot chest — not adjacent",
                    ))
                    continue

                # Generate chest loot — Phase 16B: use affix generator
                # Get best magic_find_pct from the looting player
                player_mf = getattr(player, 'magic_find_pct', 0.0)
                chest_items = generate_chest_loot(
                    "default",
                    floor_number=floor_number,
                    magic_find_pct=player_mf,
                )
                chest_states[chest_key] = "opened"

                # Add to player inventory, overflow to ground
                added_items = []
                overflow_items = []
                for item in chest_items:
                    item_dict = item.model_dump()
                    if len(player.inventory) < INVENTORY_MAX_CAPACITY:
                        player.inventory.append(item_dict)
                        added_items.append(item_dict)
                    else:
                        overflow_items.append(item_dict)

                # Place overflow on ground at chest tile
                if overflow_items and ground_items is not None:
                    if chest_key not in ground_items:
                        ground_items[chest_key] = []
                    ground_items[chest_key].extend(overflow_items)

                chest_opened.append({
                    "x": action.target_x,
                    "y": action.target_y,
                    "items": [i.model_dump() for i in chest_items],
                    "player_id": player.player_id,
                    "added_to_inventory": added_items,
                    "overflow_to_ground": overflow_items,
                })
                results.append(ActionResult(
                    player_id=player.player_id,
                    username=player.username,
                    action_type=ActionType.LOOT,
                    success=True,
                    message=f"{player.username} opened a chest and found {len(chest_items)} item(s)",
                    to_x=action.target_x,
                    to_y=action.target_y,
                ))
                continue

        # Case 2: Ground pickup — player is standing on tile with ground items
        if ground_items is not None:
            player_key = f"{player.position.x},{player.position.y}"
            tile_items = ground_items.get(player_key, [])

            if tile_items:
                picked_up = []
                remaining = []
                for item_dict in tile_items:
                    if len(player.inventory) < INVENTORY_MAX_CAPACITY:
                        player.inventory.append(item_dict)
                        picked_up.append(item_dict)
                    else:
                        remaining.append(item_dict)

                if picked_up:
                    if remaining:
                        ground_items[player_key] = remaining
                    else:
                        ground_items.pop(player_key, None)

                    items_picked_up.append({
                        "player_id": player.player_id,
                        "items": picked_up,
                    })
                    results.append(ActionResult(
                        player_id=player.player_id,
                        username=player.username,
                        action_type=ActionType.LOOT,
                        success=True,
                        message=f"{player.username} picked up {len(picked_up)} item(s)",
                    ))
                    continue

        # No valid loot target
        results.append(ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.LOOT,
            success=False,
            message=f"{player.username} nothing to loot here",
        ))
