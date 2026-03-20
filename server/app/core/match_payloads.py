"""
Match Payloads — WebSocket payload builders (pure serializers).

Extracted from match_manager.py as Phase 4 of the match-manager-split.
These functions read shared state and produce dicts. No side effects.
"""

from __future__ import annotations

from app.config import settings
from app.core.match_store import (
    _active_matches, _player_states,
    _hero_selections, _controlled_hero_map, _hero_ally_map,
)
from app.core.map_loader import load_map, get_tiles, is_dungeon_map, get_room_definitions
from app.core.fov_manager import get_team_fov, get_fov_cache
from app.core.party_manager import get_party_members


# ---------------------------------------------------------------------------
# Local helper — avoids circular import with match_manager.py
# ---------------------------------------------------------------------------

def _get_match_teams(match_id: str) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return (team_a, team_b, team_c, team_d) ID lists for a match."""
    match = _active_matches.get(match_id)
    if not match:
        return [], [], [], []
    return list(match.team_a), list(match.team_b), list(match.team_c), list(match.team_d)


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------

def get_match_start_payload(match_id: str) -> dict | None:
    """Build the match_start message payload per the WebSocket protocol spec."""
    match = _active_matches.get(match_id)
    if not match:
        return None
    players = _player_states.get(match_id, {})

    # Load map data for obstacles
    map_data = load_map(match.config.map_id)
    # For dungeon maps, derive wall-only obstacles from the tile grid.
    # Door tiles are excluded here because the client manages door blocking
    # dynamically via doorStates (closed doors get added to obstacleSet,
    # open doors are walkable). Sending doors as permanent obstacles would
    # prevent pathing through opened doors.
    if is_dungeon_map(match.config.map_id):
        tiles = map_data.get("tiles", [])
        legend = map_data.get("tile_legend", {})
        wall_chars = {ch for ch, ttype in legend.items() if ttype == "wall"}
        obstacles = []
        for y, row in enumerate(tiles):
            for x, ch in enumerate(row):
                if ch in wall_chars:
                    obstacles.append({"x": x, "y": y})
    else:
        obstacles = [{"x": o["x"], "y": o["y"]} for o in map_data.get("obstacles", [])]

    players_payload = {}
    for pid, p in players.items():
        players_payload[pid] = {
            "username": p.username,
            "position": {"x": p.position.x, "y": p.position.y},
            "hp": p.hp,
            "max_hp": p.max_hp,
            "is_alive": p.is_alive,
            "is_ready": p.is_ready,
            "unit_type": p.unit_type,
            "team": p.team,
            "class_id": p.class_id,
            "attack_damage": p.attack_damage,
            "ranged_damage": p.ranged_damage,
            "armor": p.armor,
            "vision_range": p.vision_range,
            "ranged_range": p.ranged_range,
            "enemy_type": p.enemy_type,
            "ai_behavior": p.ai_behavior,
            "is_boss": p.is_boss,
            "ai_stance": p.ai_stance,  # Phase 7C: stance for hero allies
            # Phase 19 fix: Include advanced stats at match start
            "crit_chance": p.crit_chance,
            "crit_damage": p.crit_damage,
            "dodge_chance": p.dodge_chance,
            "damage_reduction_pct": p.damage_reduction_pct,
            "hp_regen": p.hp_regen,
            "life_on_hit": p.life_on_hit,
            "cooldown_reduction_pct": p.cooldown_reduction_pct,
            "skill_damage_pct": p.skill_damage_pct,
            "thorns": p.thorns,
            "gold_find_pct": p.gold_find_pct,
            "magic_find_pct": p.magic_find_pct,
            "armor_pen": p.armor_pen,
            "sprite_variant": p.sprite_variant,
        }

    payload = {
        "type": "match_start",
        "match_id": match.match_id,
        "players": players_payload,
        "grid_width": map_data.get("width", settings.GRID_WIDTH),
        "grid_height": map_data.get("height", settings.GRID_HEIGHT),
        "obstacles": obstacles,
        "tick_rate": match.config.tick_rate,
        "match_type": match.config.match_type.value,
        "team_a": list(match.team_a),
        "team_b": list(match.team_b),
        "team_c": list(match.team_c),
        "team_d": list(match.team_d),
        "ai_ids": list(match.ai_ids),
    }

    # Phase 6C: Include class skill definitions for all classes in the match
    from app.core.skills import get_class_skills as _get_class_skills, get_skill as _get_skill
    class_ids_in_match = set()
    for p in players.values():
        if p.class_id:
            class_ids_in_match.add(p.class_id)
    class_skills_payload = {}
    for cid in class_ids_in_match:
        skill_ids = _get_class_skills(cid)
        skill_defs = []
        for sid in skill_ids:
            sdef = _get_skill(sid)
            if sdef:
                skill_defs.append({
                    "skill_id": sdef["skill_id"],
                    "name": sdef["name"],
                    "icon": sdef["icon"],
                    "cooldown_turns": sdef["cooldown_turns"],
                    "targeting": sdef["targeting"],
                    "range": sdef["range"],
                    "description": sdef["description"],
                    "requires_line_of_sight": sdef.get("requires_line_of_sight", False),
                    "is_auto_attack": sdef.get("is_auto_attack", False),
                })
        class_skills_payload[cid] = skill_defs
    if class_skills_payload:
        payload["class_skills"] = class_skills_payload

    # Dungeon-specific data for client rendering
    if is_dungeon_map(match.config.map_id):
        tiles = get_tiles(match.config.map_id)
        tile_legend = map_data.get("tile_legend", {})
        payload["tiles"] = tiles
        payload["tile_legend"] = tile_legend
        payload["door_states"] = dict(match.door_states)
        payload["chest_states"] = dict(match.chest_states)
        payload["is_dungeon"] = True
        payload["current_floor"] = match.current_floor
        payload["stairs_unlocked"] = match.stairs_unlocked
        if match.theme_id:
            payload["theme_id"] = match.theme_id
        # Phase 21F: Include room archetype + bounds for client-side room props rendering
        rooms = get_room_definitions(match.config.map_id)
        payload["dungeon_rooms"] = [
            {"archetype": r.get("archetype", r.get("purpose", "empty")), "bounds": r["bounds"]}
            for r in rooms if "bounds" in r
        ]

    return payload


def get_match_start_payload_for_player(match_id: str, player_id: str) -> dict | None:
    """Build a per-player match_start payload that includes FOV-filtered visible_tiles.

    Wraps get_match_start_payload and adds the player's initial FOV so the client
    can render fog from the very first frame (no full-map flash).
    """
    base = get_match_start_payload(match_id)
    if not base:
        return None

    match = _active_matches.get(match_id)
    if not match:
        return base

    # Get team-based FOV for this player
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player:
        return base

    player_team = player.team
    team_a, team_b, team_c, team_d = _get_match_teams(match_id)
    team_map = {"a": team_a, "b": team_b, "c": team_c, "d": team_d}
    team_members = team_map.get(player_team, [])

    # Use shared team FOV if applicable
    if team_members:
        player_fov = get_team_fov(match_id, team_members)
    else:
        player_fov = get_fov_cache(match_id, player_id)

    # Filter players: only include units visible to this player
    if player_fov:
        filtered_players = {}
        for uid, data in base["players"].items():
            if uid == player_id:
                filtered_players[uid] = data
                continue
            pos = data["position"]
            if (pos["x"], pos["y"]) in player_fov:
                filtered_players[uid] = data
            elif data.get("team") == player_team:
                # Allies always visible
                filtered_players[uid] = data
        base["players"] = filtered_players
        base["visible_tiles"] = list(player_fov)

    # Include party members so PartyVitals renders immediately
    party = get_party_members(match_id, player_id)
    if party:
        base["party"] = party

    return base


def get_player_joined_payload(match_id: str, player_id: str) -> dict | None:
    """Build the player_joined broadcast payload."""
    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player:
        return None
    return {
        "type": "player_joined",
        "player_id": player_id,
        "username": player.username,
        "position": {"x": player.position.x, "y": player.position.y},
        "team": player.team,
        "unit_type": player.unit_type,
        "class_id": player.class_id,
    }


def get_lobby_players_payload(match_id: str) -> dict:
    """Build a dict of all players for lobby state sync.

    Only includes players whose IDs are still in match.player_ids
    to prevent ghost entries from appearing.
    """
    match = _active_matches.get(match_id)
    players = _player_states.get(match_id, {})
    active_ids = set(match.player_ids) if match else set()
    hero_selections = _hero_selections.get(match_id, {})
    controlled_heroes = _controlled_hero_map.get(match_id, {})
    hero_ally_owners = _hero_ally_map.get(match_id, {})  # Phase L3: AI hero owner tracking
    result = {}
    for pid, p in players.items():
        if pid not in active_ids:
            continue  # Skip removed/ghost players
        entry = {
            "username": p.username,
            "position": {"x": p.position.x, "y": p.position.y},
            "hp": p.hp,
            "max_hp": p.max_hp,
            "is_alive": p.is_alive,
            "is_ready": p.is_ready,
            "unit_type": p.unit_type,
            "team": p.team,
            "class_id": p.class_id,
            "enemy_type": p.enemy_type,
            "is_boss": p.is_boss,
        }
        # Include hero_ids if selected (Phase 4E-2, multi-hero support)
        if pid in hero_selections:
            selection = hero_selections[pid]
            # Support both list (new) and string (legacy) formats
            if isinstance(selection, list):
                entry["hero_ids"] = selection
                entry["hero_id"] = selection[0] if selection else None  # backward compat
            else:
                entry["hero_id"] = selection
                entry["hero_ids"] = [selection]
        # Phase L2: Include controlled hero ID
        if pid in controlled_heroes:
            entry["controlled_hero_id"] = controlled_heroes[pid]
        # Phase L3: Include owner_username for hero allies (contributed AI heroes)
        if pid in hero_ally_owners:
            entry["owner_username"] = hero_ally_owners[pid]
        result[pid] = entry
    return result


def get_players_snapshot(match_id: str) -> dict:
    """Build a compact snapshot of all unit states for turn_result broadcast."""
    players = _player_states.get(match_id, {})
    result = {}
    for pid, p in players.items():
        entry = {
            "username": p.username,
            "position": {"x": p.position.x, "y": p.position.y},
            "hp": p.hp,
            "max_hp": p.max_hp,
            "is_alive": p.is_alive,
            "unit_type": p.unit_type,
            "team": p.team,
            "cooldowns": dict(p.cooldowns),
            "active_buffs": list(p.active_buffs),  # Phase 6C: include buff state
            "class_id": p.class_id,
            "enemy_type": p.enemy_type,
            "ai_behavior": p.ai_behavior,
            "is_boss": p.is_boss,
            "ai_stance": p.ai_stance,  # Phase 7C: stance for hero allies
            "extracted": p.extracted,  # Phase 12C: portal extraction
            # Phase 19 fix: Core combat stats (were missing, causing 0 display in inventory)
            "attack_damage": p.attack_damage,
            "ranged_damage": p.ranged_damage,
            "armor": p.armor,
            "vision_range": p.vision_range,
            "ranged_range": p.ranged_range,
            # Phase 19 fix: Advanced stats (Phase 16A) for inventory panel
            "crit_chance": p.crit_chance,
            "crit_damage": p.crit_damage,
            "dodge_chance": p.dodge_chance,
            "damage_reduction_pct": p.damage_reduction_pct,
            "hp_regen": p.hp_regen,
            "life_on_hit": p.life_on_hit,
            "cooldown_reduction_pct": p.cooldown_reduction_pct,
            "skill_damage_pct": p.skill_damage_pct,
            "thorns": p.thorns,
            "gold_find_pct": p.gold_find_pct,
            "magic_find_pct": p.magic_find_pct,
            "armor_pen": p.armor_pen,
            "sprite_variant": p.sprite_variant,
        }
        # Phase 18C: Include monster rarity metadata for enhanced enemies
        if p.monster_rarity and p.monster_rarity != "normal":
            entry["monster_rarity"] = p.monster_rarity
            entry["champion_type"] = p.champion_type
            entry["affixes"] = list(p.affixes) if p.affixes else []
            entry["display_name"] = p.display_name
        if p.is_minion:
            entry["is_minion"] = True
            entry["minion_owner_id"] = p.minion_owner_id
        result[pid] = entry
    return result
