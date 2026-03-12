"""
Skills Phase — Phase 1.9: Skill resolution (heal, multi-hit, ranged, buff, teleport).

Phase 6B: Skill system.
Phase 12C: Channeling/extraction skip checks.
"""

from __future__ import annotations

from app.models.player import PlayerState
from app.models.actions import PlayerAction, ActionType, ActionResult
from app.core.skills import get_skill, can_use_skill, resolve_skill_action, is_stunned
from app.core.turn_phases.portal_phase import _is_channeling


def _resolve_skills(
    skill_actions: list[PlayerAction],
    players: dict[str, PlayerState],
    obstacles: set[tuple[int, int]],
    grid_width: int,
    grid_height: int,
    results: list[ActionResult],
    deaths: list[str],
    buff_changes: list[dict],
    portal_context: dict | None = None,
    match_state=None,  # Phase 26B: MatchState for totem placement
) -> None:
    """Phase 1.9 — Resolve skill actions (heal, multi-hit, ranged, buff, teleport)."""
    for action in skill_actions:
        player = players.get(action.player_id)
        if not player or not player.is_alive:
            continue

        # Phase 12C: Extracted heroes skip all phases
        if player.extracted:
            continue
        # Phase 12C: Channeling players cannot use skills
        if portal_context and _is_channeling(player.player_id, portal_context):
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.SKILL,
                success=False,
                message=f"{player.username} is channeling and cannot use skills!",
            ))
            continue

        # Phase 12: Stunned units cannot use skills
        if is_stunned(player):
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.SKILL,
                success=False,
                message=f"{player.username} is stunned and cannot use skills!",
            ))
            continue

        skill_id = action.skill_id
        if not skill_id:
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.SKILL,
                success=False,
                message=f"{player.username} skill action missing skill_id",
            ))
            continue

        # Validate skill usage (class, cooldown, alive)
        can_use, reason = can_use_skill(player, skill_id)
        if not can_use:
            results.append(ActionResult(
                player_id=player.player_id,
                username=player.username,
                action_type=ActionType.SKILL,
                skill_id=skill_id,
                success=False,
                message=f"{player.username} cannot use skill — {reason}",
            ))
            continue

        # Get skill definition and dispatch to handler
        skill_def = get_skill(skill_id)
        result = resolve_skill_action(
            player, action, skill_def, players, obstacles,
            grid_width, grid_height,
            match_state=match_state,
        )
        results.append(result)

        # Track kills from skill actions
        if result.killed and result.target_id:
            deaths.append(result.target_id)

        # Phase 12: Track AoE kills (multiple targets killed in one skill)
        if result.buff_applied and isinstance(result.buff_applied, dict):
            killed_ids = result.buff_applied.get("killed_ids", [])
            for kid in killed_ids:
                if kid not in deaths:
                    deaths.append(kid)

        # Track buff changes from skill usage
        if result.buff_applied:
            buff_changes.append({
                "player_id": player.player_id,
                "buffs": [b.copy() for b in player.active_buffs],
                "expired": [],
            })
