"""
Portal Phase — Phase 0.25–0.9: Channeling, portal entity, extraction, stairs.

Phase 12C: Portal scroll channeling system.
Phase 12-5: Stairs floor transition.
"""

from __future__ import annotations

from app.models.player import PlayerState
from app.models.actions import PlayerAction, ActionType, ActionResult


# ---------------------------------------------------------------------------
# Phase 12C: Portal Scroll — Channeling, Portal Entity, Extraction
# ---------------------------------------------------------------------------

PORTAL_CHANNEL_TURNS = 3
PORTAL_DURATION_TURNS = 20


def _resolve_channeling(
    players: dict[str, PlayerState],
    results: list[ActionResult],
    portal_context: dict,
    match_channeling: dict | None,
    match_portal: dict | None,
) -> tuple[dict | None, dict | None]:
    """Phase 0.25 — Tick channeling timer and spawn portal when complete.

    If a new channeling was started this turn via portal scroll, it overrides
    any existing channeling (shouldn't happen — only one scroll at a time).

    Returns:
        (updated_channeling, updated_portal): new channeling/portal state dicts.
    """
    channeling = match_channeling
    portal = match_portal

    # If a new channeling started this turn (from _resolve_items), set it up
    new_chan = portal_context.get("channeling_started")
    if new_chan:
        channeling = dict(new_chan)
        channeling["action"] = "portal"
        portal_context["channeling_active"] = True

    if not channeling:
        return channeling, portal

    caster_id = channeling["player_id"]
    caster = players.get(caster_id)

    # If caster died during this turn (e.g., DoT), cancel channeling
    if not caster or not caster.is_alive:
        results.append(ActionResult(
            player_id=caster_id,
            username=caster.username if caster else "Unknown",
            action_type=ActionType.USE_ITEM,
            success=False,
            message=f"Portal channeling interrupted — caster died!",
        ))
        portal_context["channeling_active"] = False
        return None, portal

    # Decrement channeling timer
    channeling["turns_remaining"] -= 1
    portal_context["channeling_active"] = True

    if channeling["turns_remaining"] <= 0:
        # Channel complete — spawn portal entity on caster's tile
        portal = {
            "active": True,
            "x": channeling["tile_x"],
            "y": channeling["tile_y"],
            "turns_remaining": PORTAL_DURATION_TURNS,
            "owner_id": caster_id,
        }
        results.append(ActionResult(
            player_id=caster_id,
            username=caster.username,
            action_type=ActionType.USE_ITEM,
            success=True,
            message=f"{caster.username}'s portal tears open! A shimmering gateway appears.",
        ))
        portal_context["portal_spawned"] = {
            "x": portal["x"],
            "y": portal["y"],
            "turns_remaining": portal["turns_remaining"],
            "owner_id": caster_id,
        }
        portal_context["channeling_active"] = False
        return None, portal  # channeling done, portal now active
    else:
        # Still channeling
        portal_context["channeling_tick"] = {
            "player_id": caster_id,
            "turns_remaining": channeling["turns_remaining"],
        }
        results.append(ActionResult(
            player_id=caster_id,
            username=caster.username,
            action_type=ActionType.USE_ITEM,
            success=True,
            message=f"{caster.username} is channeling a portal... ({channeling['turns_remaining']} turns remaining)",
        ))
        return channeling, portal


def _resolve_portal_tick(
    portal: dict | None,
    portal_context: dict,
    results: list[ActionResult],
) -> dict | None:
    """Phase 0.8 — Tick portal entity timer. Returns updated portal or None if expired."""
    if not portal or not portal.get("active"):
        return portal

    portal["turns_remaining"] -= 1

    if portal["turns_remaining"] <= 0:
        # Portal expired
        portal_context["portal_expired"] = True
        results.append(ActionResult(
            player_id=portal["owner_id"],
            username="",
            action_type=ActionType.INTERACT,
            success=False,
            message="The portal flickers and fades away...",
        ))
        return None

    portal_context["portal_tick"] = {
        "x": portal["x"],
        "y": portal["y"],
        "turns_remaining": portal["turns_remaining"],
    }
    return portal


def _resolve_extractions(
    interact_actions: list[PlayerAction],
    players: dict[str, PlayerState],
    portal: dict | None,
    team_a: list[str] | None,
    results: list[ActionResult],
    portal_context: dict,
) -> None:
    """Phase 0.85 — Handle portal extraction for heroes on the portal tile.

    Heroes can extract by:
    1. Sending an INTERACT action with target_id='enter_portal' while on the portal tile
    2. AI-controlled party members on the portal tile auto-extract

    Extracted heroes are marked with extracted=True and skip all subsequent phases.
    """
    if not portal or not portal.get("active"):
        return

    portal_x, portal_y = portal["x"], portal["y"]

    # Process explicit extraction interact actions
    for action in interact_actions:
        if action.target_id != "enter_portal":
            continue
        player = players.get(action.player_id)
        if not player or not player.is_alive or player.extracted:
            continue
        # Must be on the portal tile
        if player.position.x != portal_x or player.position.y != portal_y:
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.INTERACT,
                success=False,
                message=f"{player.username} is not on the portal tile!",
            ))
            continue
        # Extract this hero
        player.extracted = True
        portal_context["extractions"].append({
            "player_id": player.player_id,
            "username": player.username,
            "hero_id": player.hero_id,
        })
        results.append(ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.INTERACT,
            success=True,
            message=f"{player.username} steps through the portal to safety!",
        ))

    # Auto-extract AI-controlled party members standing on the portal tile
    # (they auto-extract if they've been on the tile for 1 turn — simplified
    # to: if they're on the tile and haven't extracted yet, extract them)
    team_a_ids = set(team_a or [])
    for pid, player in players.items():
        if pid not in team_a_ids:
            continue
        if not player.is_alive or player.extracted:
            continue
        if player.unit_type != "ai" and not player.controlled_by:
            continue  # Only auto-extract AI allies, not human players
        if player.position.x == portal_x and player.position.y == portal_y:
            player.extracted = True
            portal_context["extractions"].append({
                "player_id": player.player_id,
                "username": player.username,
                "hero_id": player.hero_id,
            })
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.INTERACT,
                success=True,
                message=f"{player.username} escapes through the portal!",
            ))


# ---------------------------------------------------------------------------
# Phase 12-5: Stairs — Floor Transition
# ---------------------------------------------------------------------------

def _resolve_stairs(
    interact_actions: list[PlayerAction],
    players: dict[str, PlayerState],
    stairs_positions: list[tuple[int, int]],
    stairs_unlocked: bool,
    team_a: list[str] | None,
    results: list[ActionResult],
    stairs_context: dict,
) -> None:
    """Phase 0.9 — Handle stairs interaction to descend to next floor.

    When any team_a hero sends INTERACT with target_id='enter_stairs' while
    standing on a stairs tile and stairs are unlocked (all enemies dead),
    the entire party descends.  Sets stairs_context['floor_advance'] = True.
    """
    if not stairs_positions or not stairs_unlocked:
        # Check for interact attempts when stairs are locked
        for action in interact_actions:
            if action.target_id != "enter_stairs":
                continue
            player = players.get(action.player_id)
            if not player or not player.is_alive:
                continue
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.INTERACT,
                success=False,
                message="The stairs are sealed... defeat all enemies first!" if not stairs_unlocked
                    else "There are no stairs on this floor.",
            ))
        return

    stairs_set = set(stairs_positions)
    team_a_ids = set(team_a or [])

    for action in interact_actions:
        if action.target_id != "enter_stairs":
            continue
        player = players.get(action.player_id)
        if not player or not player.is_alive or player.extracted:
            continue

        # Must be on a stairs tile
        if (player.position.x, player.position.y) not in stairs_set:
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.INTERACT,
                success=False,
                message=f"{player.username} is not on the stairs!",
            ))
            continue

        # Must be on team_a (player party)
        if player.player_id not in team_a_ids:
            continue

        # Trigger floor advance for the entire party
        stairs_context["floor_advance"] = True
        stairs_context["triggered_by"] = player.player_id
        results.append(ActionResult(
            player_id=player.player_id,
            username=player.username,
            action_type=ActionType.INTERACT,
            success=True,
            message=f"{player.username} descends the stairs... The party follows!",
        ))
        return  # Only one floor advance per turn


def _is_channeling(player_id: str, portal_context: dict) -> bool:
    """Check if a player is currently channeling a portal scroll."""
    if portal_context.get("channeling_active", False):
        chan_started = portal_context.get("channeling_started")
        if chan_started and chan_started.get("player_id") == player_id:
            return True
    chan_tick = portal_context.get("channeling_tick")
    if chan_tick and chan_tick.get("player_id") == player_id:
        return True
    return False
