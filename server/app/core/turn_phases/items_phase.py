"""
Items Phase — Phase 0: Consume potions/scrolls before cooldowns or movement.

Portal scrolls start channeling via portal_context.
"""

from __future__ import annotations

from app.models.player import PlayerState
from app.models.actions import PlayerAction, ActionType, ActionResult
from app.models.items import INVENTORY_MAX_CAPACITY


def _resolve_items(
    use_item_actions: list[PlayerAction],
    players: dict[str, PlayerState],
    results: list[ActionResult],
    items_used: list[dict],
    portal_context: dict | None = None,
) -> None:
    """Phase 0 — Consume potions/scrolls before cooldowns or movement.

    portal_context: if provided, a mutable dict that will be updated with
    {'activated': True, 'user_id': player_id} when a portal scroll is used.
    """
    for action in use_item_actions:
        player = players.get(action.player_id)
        if not player or not player.is_alive:
            continue

        inv_items = player.inventory
        if not inv_items:
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.USE_ITEM,
                success=False,
                message=f"{player.username} has no items to use",
            ))
            continue

        # Find the consumable to use. target_x is used as inventory index if set.
        item_data = None
        item_index = None
        if action.target_x is not None and 0 <= action.target_x < len(inv_items):
            candidate = inv_items[action.target_x]
            if candidate.get("item_type") == "consumable":
                item_data = candidate
                item_index = action.target_x
        else:
            # Find first consumable
            for idx, it in enumerate(inv_items):
                if it.get("item_type") == "consumable":
                    item_data = it
                    item_index = idx
                    break

        if item_data is None:
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.USE_ITEM,
                success=False,
                message=f"{player.username} has no usable consumable",
            ))
            continue

        # Parse the consumable effect
        effect_data = item_data.get("consumable_effect", {})
        effect_type = effect_data.get("type")
        magnitude = effect_data.get("magnitude", 0)

        if effect_type == "portal":
            # Phase 12C: Portal scroll — start 3-turn channeling (no longer instant extract)
            # Consume the scroll immediately (committed action)
            player.inventory.pop(item_index)
            items_used.append({
                "player_id": player.player_id,
                "item_id": item_data.get("item_id"),
                "item_name": item_data.get("name"),
                "effect": {"type": "portal"},
            })
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.USE_ITEM,
                success=True,
                message=f"{player.username} begins channeling a town portal...",
            ))
            if portal_context is not None:
                portal_context["channeling_started"] = {
                    "player_id": player.player_id,
                    "turns_remaining": 3,
                    "tile_x": player.position.x,
                    "tile_y": player.position.y,
                }
            continue

        if effect_type == "heal":
            # Consume potion — remove from inventory, restore HP
            player.inventory.pop(item_index)
            old_hp = player.hp
            player.hp = min(player.max_hp, player.hp + magnitude)
            healed = player.hp - old_hp

            items_used.append({
                "player_id": player.player_id,
                "item_id": item_data.get("item_id"),
                "item_name": item_data.get("name"),
                "effect": {"type": "heal", "magnitude": magnitude, "actual_healed": healed},
            })
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.USE_ITEM,
                success=True,
                message=f"{player.username} used {item_data.get('name', 'potion')} and restored {healed} HP",
            ))
            continue

        # Unknown consumable type
        results.append(ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.USE_ITEM,
            success=False,
            message=f"{player.username} cannot use {item_data.get('name', 'item')}",
        ))
