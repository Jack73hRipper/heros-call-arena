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
    match_id: str = "",
) -> None:
    """Phase 1.75 — Chest interaction + ground item pickup."""
    for action in loot_actions:
        player = players.get(action.player_id)
        if not player or not player.is_alive:
            continue

        # Case 1: Chest interaction — target is an unopened chest tile
        if action.target_x is not None and action.target_y is not None and chest_states is not None:
            chest_key = f"{action.target_x},{action.target_y}"
            chest_state = chest_states.get(chest_key, "")
            # Parse tier from state format "unopened:tier" (backward compat: plain "unopened")
            is_unopened = chest_state == "unopened" or chest_state.startswith("unopened:")
            if is_unopened:
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

                # Extract chest tier for loot generation
                chest_tier = "default"
                if ":" in chest_state:
                    chest_tier = chest_state.split(":", 1)[1]

                # Generate chest loot — Phase 16B: use affix generator
                # Get best magic_find_pct from the looting player
                player_mf = getattr(player, 'magic_find_pct', 0.0)
                chest_items = generate_chest_loot(
                    chest_tier,
                    floor_number=floor_number,
                    magic_find_pct=player_mf,
                )
                # Mark opened, preserving the tier for client rendering
                chest_states[chest_key] = f"opened:{chest_tier}" if chest_tier != "default" else "opened"

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

    # ------------------------------------------------------------------
    # Phase 28C: Passive auto-pickup — sweep alive units standing on
    # ground items.  HERO PARTIES ONLY — dungeon monsters (enemy_type set)
    # do not auto-pickup ground loot.  Human players + AI hero parties only.
    # ------------------------------------------------------------------
    if ground_items:
        # Build set of player_ids already handled above to avoid double pickup
        handled_ids = {a.player_id for a in loot_actions}
        for player in players.values():
            if not player.is_alive:
                continue
            if player.player_id in handled_ids:
                continue
            # Skip dungeon monsters — they should not auto-pickup loot
            if getattr(player, 'enemy_type', None) is not None:
                continue
            player_key = f"{player.position.x},{player.position.y}"
            tile_items = ground_items.get(player_key)
            if not tile_items:
                continue
            if len(player.inventory) >= INVENTORY_MAX_CAPACITY:
                continue

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

                # Phase 28F: Distribute equippable items to best party member
                trade_recipients = set()
                is_ai_hero = player.unit_type == "ai" and getattr(player, 'enemy_type', None) is None
                if is_ai_hero:
                    from app.core.equipment_manager import find_best_party_recipient
                    team_members = [
                        p for p in players.values()
                        if p.team == player.team and p.is_alive and p.player_id != player.player_id
                        and getattr(p, 'enemy_type', None) is None
                    ]
                    if team_members:
                        items_to_trade = []
                        for item in list(picked_up):
                            if item.get("item_type") == "consumable":
                                continue
                            best = find_best_party_recipient(item, team_members + [player])
                            if best and best.player_id != player.player_id:
                                items_to_trade.append((item, best))
                        for item, recipient in items_to_trade:
                            if item in player.inventory:
                                player.inventory.remove(item)
                                recipient.inventory.append(item)
                                trade_recipients.add(recipient.player_id)
                                results.append(ActionResult(
                                    player_id=recipient.player_id,
                                    username=recipient.username,
                                    action_type=ActionType.LOOT,
                                    success=True,
                                    message=f"{recipient.username} received {item.get('name', 'item')} from {player.username}",
                                ))

                # Phase 28E: Auto-equip for AI hero party units after pickup/trade
                if is_ai_hero and match_id:
                    from app.core.equipment_manager import try_auto_equip
                    equip_results = try_auto_equip(player, match_id)
                    for er in equip_results:
                        equipped_item = er.get("equipped", {})
                        item_name = equipped_item.get("name", "item") if isinstance(equipped_item, dict) else "item"
                        results.append(ActionResult(
                            player_id=player.player_id,
                            username=player.username,
                            action_type=ActionType.LOOT,
                            success=True,
                            message=f"{player.username} equipped {item_name}",
                        ))
                    # Phase 28F: Auto-equip for recipients who received traded items
                    for rid in trade_recipients:
                        recipient = players.get(rid)
                        if recipient and recipient.is_alive:
                            re_results = try_auto_equip(recipient, match_id)
                            for er in re_results:
                                equipped_item = er.get("equipped", {})
                                item_name = equipped_item.get("name", "item") if isinstance(equipped_item, dict) else "item"
                                results.append(ActionResult(
                                    player_id=recipient.player_id,
                                    username=recipient.username,
                                    action_type=ActionType.LOOT,
                                    success=True,
                                    message=f"{recipient.username} equipped {item_name}",
                                ))

                    # Phase 28I: Redistribute displaced equipment across team
                    # After auto-equip, old items land in inventory. Re-scan ALL
                    # team members' inventories and transfer items that would be
                    # an upgrade for a teammate, then auto-equip + repeat until
                    # no more transfers happen (max 3 passes to avoid loops).
                    all_team = [
                        p for p in players.values()
                        if p.team == player.team and p.is_alive
                        and getattr(p, 'enemy_type', None) is None
                    ]
                    for _redist_pass in range(3):
                        transfers_this_pass = 0
                        for member in list(all_team):
                            if not member.is_alive:
                                continue
                            # Scan inventory for equippable non-consumable items
                            for idx in range(len(member.inventory) - 1, -1, -1):
                                if idx >= len(member.inventory):
                                    continue
                                item = member.inventory[idx]
                                if not isinstance(item, dict):
                                    continue
                                if item.get("item_type") == "consumable":
                                    continue
                                slot = item.get("equip_slot")
                                if not slot:
                                    continue
                                # Find the best recipient across the whole team
                                best = find_best_party_recipient(item, all_team)
                                if best and best.player_id != member.player_id:
                                    if len(best.inventory) >= INVENTORY_MAX_CAPACITY:
                                        continue
                                    member.inventory.pop(idx)
                                    best.inventory.append(item)
                                    transfers_this_pass += 1
                                    results.append(ActionResult(
                                        player_id=best.player_id,
                                        username=best.username,
                                        action_type=ActionType.LOOT,
                                        success=True,
                                        message=f"{best.username} received {item.get('name', 'item')} from {member.username}",
                                    ))
                        # Auto-equip everyone who might have received items
                        if transfers_this_pass > 0:
                            for member in all_team:
                                if member.is_alive:
                                    eq_res = try_auto_equip(member, match_id)
                                    for er in eq_res:
                                        equipped_item = er.get("equipped", {})
                                        item_name = equipped_item.get("name", "item") if isinstance(equipped_item, dict) else "item"
                                        results.append(ActionResult(
                                            player_id=member.player_id,
                                            username=member.username,
                                            action_type=ActionType.LOOT,
                                            success=True,
                                            message=f"{member.username} equipped {item_name}",
                                        ))
                        else:
                            break  # No transfers needed — done

                    # Phase 28G: Purge items no team member wants — free inventory space
                    from app.core.equipment_manager import purge_unwanted_items
                    all_team = [
                        p for p in players.values()
                        if p.team == player.team and p.is_alive
                        and getattr(p, 'enemy_type', None) is None
                    ]
                    purge_ids = {m.player_id for m in all_team}
                    for pid in purge_ids:
                        purge_unit = players.get(pid)
                        if purge_unit and purge_unit.is_alive:
                            destroyed = purge_unwanted_items(purge_unit, all_team)
                            for d in destroyed:
                                results.append(ActionResult(
                                    player_id=purge_unit.player_id,
                                    username=purge_unit.username,
                                    action_type=ActionType.LOOT,
                                    success=True,
                                    message=f"{purge_unit.username} destroyed {d['item_name']} (no upgrade)",
                                ))

                    # Phase 28H: Balance potions across team members
                    from app.core.equipment_manager import balance_team_potions
                    potion_transfers = balance_team_potions(all_team)
                    for pt in potion_transfers:
                        results.append(ActionResult(
                            player_id=pt["to_id"],
                            username=pt["to_name"],
                            action_type=ActionType.LOOT,
                            success=True,
                            message=f"{pt['to_name']} received {pt['item_name']} from {pt['from_name']}",
                        ))
