"""
Hero Manager — Handles hero persistence, selection, spawning, and permadeath.

Extracted from match_manager.py during P2 refactoring.
Manages hero selection for dungeons, hero ally spawning, kill tracking,
post-match persistence, permadeath, and match end payloads.
"""

from __future__ import annotations

import logging
import uuid

from app.models.player import PlayerState, Position, get_all_classes

logger = logging.getLogger(__name__)
from app.models.match import MatchType, MatchStatus
from app.core.map_loader import get_spawn_points, is_dungeon_map
from app.core.combat import get_combat_config

# Shared state dicts — imported from match_manager
from app.core.match_manager import (
    _active_matches,
    _player_states,
    _hero_selections,
    _hero_ally_map,
    _username_map,
    _kill_tracker,
    _combat_stats,
    _match_timeline,
)


MAX_PARTY_SIZE = 4  # Maximum heroes a single player can bring
MAX_DUNGEON_PARTY = 5  # Total cap for humans + hero allies in a dungeon


def get_dungeon_slots_available(match_id: str) -> int:
    """Return how many hero ally slots remain in a dungeon lobby (total cap = 5).

    Counts all human players + all existing hero allies. Returns remaining slots.
    For non-dungeon matches, returns MAX_PARTY_SIZE (no global cap).
    """
    match = _active_matches.get(match_id)
    if not match:
        return 0
    is_dungeon = (
        match.config.match_type in (MatchType.DUNGEON, MatchType.PVPVE)
        or is_dungeon_map(match.config.map_id)
    )
    if not is_dungeon:
        return MAX_PARTY_SIZE

    players = _player_states.get(match_id, {})
    # Count all units currently in the match (humans + hero allies)
    total_units = len([p for p in players.values() if p.unit_type in ("human", "ai")])
    return max(0, MAX_DUNGEON_PARTY - total_units)


def select_heroes(match_id: str, player_id: str, hero_ids: list[str]) -> list[dict] | None:
    """Select heroes for dungeon — spawns each as an AI ally on the player's team.

    Enforces per-player cap (4) AND total dungeon party cap (5 = humans + hero allies).
    Validates that each hero exists, is alive, and belongs to the player.
    For dungeon matches, each hero is spawned as an AI-controlled party member
    with the hero's stats, class, equipment, and inventory.
    Returns list of hero info dicts on success, or None on failure.
    """
    match = _active_matches.get(match_id)
    if not match or match.status != MatchStatus.WAITING:
        logger.warning("[select_heroes] FAIL: match not found or not WAITING "
                       f"(match_id={match_id}, found={match is not None}, "
                       f"status={match.status if match else 'N/A'})")
        return None

    players = _player_states.get(match_id, {})
    player = players.get(player_id)
    if not player:
        logger.warning(f"[select_heroes] FAIL: player {player_id} not found in match {match_id}. "
                       f"Known player_ids: {list(players.keys())}")
        return None

    if not hero_ids or len(hero_ids) == 0:
        logger.warning(f"[select_heroes] FAIL: empty hero_ids for player {player_id}")
        return None

    logger.info(f"[select_heroes] player={player_id} username={player.username!r} "
                f"hero_ids={hero_ids}")

    # Enforce per-player max party size
    if len(hero_ids) > MAX_PARTY_SIZE:
        hero_ids = hero_ids[:MAX_PARTY_SIZE]

    # Enforce total dungeon party cap (humans + all hero allies)
    # First remove this player's existing hero allies to get accurate count
    _remove_hero_ally(match_id, player_id)
    slots_available = get_dungeon_slots_available(match_id)
    if len(hero_ids) > slots_available:
        hero_ids = hero_ids[:slots_available]
    if len(hero_ids) == 0:
        logger.warning(f"[select_heroes] FAIL: no slots available (slots={slots_available})")
        return None

    # Deduplicate while preserving order
    seen = set()
    unique_ids = []
    for hid in hero_ids:
        if hid not in seen:
            seen.add(hid)
            unique_ids.append(hid)
    hero_ids = unique_ids

    # Load player profile to validate hero ownership
    from app.services.persistence import load_profile
    profile = load_profile(player.username)

    if profile is None:
        logger.warning(f"[select_heroes] FAIL: profile not found for {player.username!r}. "
                       "Retrying once after brief delay...")
        # Retry once — file may be temporarily locked (OneDrive sync, antivirus, etc.)
        import time
        time.sleep(0.15)
        profile = load_profile(player.username)

    if profile is None:
        logger.error(f"[select_heroes] FAIL: profile still not found for {player.username!r} "
                     "after retry. NOT creating a default profile (would erase heroes).")
        return None

    profile_hero_ids = [h.hero_id for h in profile.heroes]
    logger.info(f"[select_heroes] profile loaded: {len(profile.heroes)} heroes, "
                f"ids={profile_hero_ids}")

    # Validate all heroes
    validated_heroes = []
    for hero_id in hero_ids:
        hero = None
        for h in profile.heroes:
            if h.hero_id == hero_id:
                hero = h
                break
        if hero is None:
            logger.warning(f"[select_heroes] FAIL: hero {hero_id!r} not found in profile. "
                           f"Profile hero_ids: {profile_hero_ids}")
            return None  # Hero not found in roster
        if not hero.is_alive:
            logger.warning(f"[select_heroes] FAIL: hero {hero_id!r} ({hero.name}) is dead")
            return None  # Dead heroes cannot be selected
        validated_heroes.append(hero)

    # Store hero selection for tracking (list of hero_ids)
    if match_id not in _hero_selections:
        _hero_selections[match_id] = {}
    _hero_selections[match_id][player_id] = hero_ids

    # Hero allies were already removed above (before slot counting) — no need to remove again

    # Spawn each hero as an AI ally on the player's team
    is_dungeon = match.config.match_type in (MatchType.DUNGEON, MatchType.PVPVE) or is_dungeon_map(match.config.map_id)
    results = []
    if is_dungeon:
        for hero in validated_heroes:
            _spawn_hero_ally(match_id, player_id, player.username, hero)
            results.append({
                "hero_id": hero.hero_id,
                "hero_name": hero.name,
                "class_id": hero.class_id,
                "stats": hero.stats.model_dump(),
                "equipment": hero.equipment,
                "inventory": hero.inventory,
            })
    else:
        for hero in validated_heroes:
            results.append({
                "hero_id": hero.hero_id,
                "hero_name": hero.name,
                "class_id": hero.class_id,
                "stats": hero.stats.model_dump(),
                "equipment": hero.equipment,
                "inventory": hero.inventory,
            })

    return results


def select_hero(match_id: str, player_id: str, hero_id: str) -> dict | None:
    """Select a single hero for dungeon — backward-compatible wrapper around select_heroes()."""
    results = select_heroes(match_id, player_id, [hero_id])
    if results and len(results) > 0:
        return results[0]
    return None


def _spawn_hero_ally(match_id: str, owner_player_id: str, owner_username: str, hero) -> str:
    """Spawn a persistent hero as an AI ally unit on the owner's team.

    The hero ally gets the hero's name, class, stats, equipment, and inventory.
    Returns the AI ally's player_id.
    """
    match = _active_matches.get(match_id)
    players = _player_states.get(match_id, {})

    # Find a spawn point near the owner
    # For procedural dungeons the map doesn't exist yet, so get_spawn_points
    # returns [] — use fallback positions (real spawns assigned at match start).
    spawn_points = get_spawn_points(match.config.map_id)
    if not spawn_points:
        spawn_points = [(1, 1), (13, 1), (1, 13), (13, 13),
                        (7, 1), (7, 13), (1, 7), (13, 7)]

    # Use next available spawn point (after existing players)
    taken_positions = {(p.position.x, p.position.y) for p in players.values()}
    spawn_pos = spawn_points[0]  # fallback
    for sp in spawn_points:
        if sp not in taken_positions:
            spawn_pos = sp
            break

    ai_id = f"hero-{str(uuid.uuid4())[:6]}"

    # Create AI unit with hero's stats
    ally = PlayerState(
        player_id=ai_id,
        username=hero.name,  # Display the hero's name
        position=Position(x=spawn_pos[0], y=spawn_pos[1]),
        unit_type="ai",
        team="a",  # Same team as the human player
        is_ready=True,
        # Hero stats
        hp=hero.stats.hp,
        max_hp=hero.stats.max_hp,
        attack_damage=hero.stats.attack_damage,
        ranged_damage=hero.stats.ranged_damage,
        armor=hero.stats.armor,
        vision_range=hero.stats.vision_range,
        ranged_range=hero.stats.ranged_range,
        # Class & hero tracking
        class_id=hero.class_id,
        hero_id=hero.hero_id,
        sprite_variant=getattr(hero, 'sprite_variant', 1),
        # Equipment & inventory
        equipment=dict(hero.equipment) if hero.equipment else {},
        inventory=list(hero.inventory) if hero.inventory else [],
    )

    # Apply class colors/shape (for rendering)
    all_classes = get_all_classes()
    if hero.class_id in all_classes:
        cls = all_classes[hero.class_id]
        ally.class_id = hero.class_id

    # Apply equipment stat bonuses
    _apply_hero_equipment_bonuses(ally)

    # Register the ally in the match
    players[ai_id] = ally
    match.player_ids.append(ai_id)
    match.ai_ids.append(ai_id)
    match.team_a.append(ai_id)

    # Track the hero ally for persistence (owner username needed for save/permadeath)
    if match_id not in _hero_ally_map:
        _hero_ally_map[match_id] = {}
    _hero_ally_map[match_id][ai_id] = owner_username

    return ai_id


def _remove_hero_ally(match_id: str, owner_player_id: str) -> None:
    """Remove any existing hero ally spawned for this player (for re-selection)."""
    match = _active_matches.get(match_id)
    players = _player_states.get(match_id, {})
    ally_map = _hero_ally_map.get(match_id, {})

    if not match:
        return

    # Find the owner's username
    owner = players.get(owner_player_id)
    if not owner:
        return

    # Find and remove hero allies belonging to this owner
    to_remove = [aid for aid, uname in ally_map.items() if uname == owner.username]
    for ai_id in to_remove:
        players.pop(ai_id, None)
        ally_map.pop(ai_id, None)
        if ai_id in match.player_ids:
            match.player_ids.remove(ai_id)
        if ai_id in match.ai_ids:
            match.ai_ids.remove(ai_id)
        if ai_id in match.team_a:
            match.team_a.remove(ai_id)


def get_hero_selection(match_id: str, player_id: str) -> list[str] | None:
    """Get a player's selected hero_ids in lobby (list of hero_id strings)."""
    return _hero_selections.get(match_id, {}).get(player_id)


def _load_heroes_at_match_start(match_id: str) -> None:
    """Load persistent heroes into PlayerState at match start.

    For dungeon matches where heroes are spawned as AI allies (via select_hero),
    this is a no-op since the hero stats are already on the AI unit.

    For arena matches (or any match without hero allies), loads hero stats
    onto the human player's PlayerState as before.

    Players without a hero selection keep default/class stats.
    """
    from app.services.persistence import load_or_create_profile

    hero_selections = _hero_selections.get(match_id, {})
    if not hero_selections:
        return  # No hero selections — arena mode

    # If hero allies were already spawned (dungeon flow), skip loading onto humans
    hero_allies = _hero_ally_map.get(match_id, {})
    if hero_allies:
        return  # Heroes are AI allies — stats already applied at spawn time

    players = _player_states.get(match_id, {})
    username_map = _username_map.get(match_id, {})

    for pid, hero_ids in hero_selections.items():
        player = players.get(pid)
        if not player or player.unit_type != "human":
            continue

        # For arena mode (no hero allies), apply the first hero's stats to the human player
        # (multi-hero is only meaningful in dungeon mode where heroes are AI allies)
        first_hero_id = hero_ids[0] if isinstance(hero_ids, list) else hero_ids

        # Load the profile and find the hero
        profile = load_or_create_profile(player.username)
        hero = None
        for h in profile.heroes:
            if h.hero_id == first_hero_id and h.is_alive:
                hero = h
                break

        if not hero:
            continue  # Hero not found or dead — keep default stats

        # Apply hero stats to PlayerState
        player.hero_id = first_hero_id
        player.class_id = hero.class_id
        player.sprite_variant = getattr(hero, 'sprite_variant', 1)
        player.hp = hero.stats.hp
        player.max_hp = hero.stats.max_hp
        player.attack_damage = hero.stats.attack_damage
        player.ranged_damage = hero.stats.ranged_damage
        player.armor = hero.stats.armor
        player.vision_range = hero.stats.vision_range
        player.ranged_range = hero.stats.ranged_range

        # Load hero equipment and inventory
        player.equipment = dict(hero.equipment) if hero.equipment else {}
        player.inventory = list(hero.inventory) if hero.inventory else []

        # Apply equipment stat bonuses
        _apply_hero_equipment_bonuses(player)


def _apply_hero_equipment_bonuses(player: PlayerState) -> None:
    """Apply stat bonuses from all equipped items to a player's stats.

    Called at match start when loading a persistent hero.
    """
    from app.models.items import StatBonuses

    for slot_name, item_data in player.equipment.items():
        if not item_data:
            continue
        bonuses = StatBonuses(**item_data.get("stat_bonuses", {}))
        if bonuses.max_hp > 0:
            player.max_hp += bonuses.max_hp
            player.hp += bonuses.max_hp  # Grant bonus HP immediately


def handle_hero_permadeath(match_id: str, dead_player_id: str) -> dict | None:
    """Handle permadeath for a hero that died in a match.

    Works for both human-controlled heroes and AI hero allies.
    For AI hero allies, looks up the owner's username via _hero_ally_map.

    Marks the hero as dead on the owner's profile, clears their equipment
    and inventory, and saves the profile to disk.

    Returns a hero_death event dict, or None if the player has no hero_id.
    """
    from app.services.persistence import load_or_create_profile, save_profile

    players = _player_states.get(match_id, {})
    player = players.get(dead_player_id)
    if not player or not player.hero_id:
        return None  # No persistent hero — arena mode, no permadeath

    hero_id = player.hero_id

    # Determine the owner's username for loading the profile
    # For AI hero allies, the owner is tracked in _hero_ally_map
    ally_map = _hero_ally_map.get(match_id, {})
    owner_username = ally_map.get(dead_player_id, player.username)

    # Load profile
    profile = load_or_create_profile(owner_username)
    hero = None
    for h in profile.heroes:
        if h.hero_id == hero_id:
            hero = h
            break

    if not hero:
        return None  # Hero not found on profile (shouldn't happen)

    # Build lost items list before clearing
    lost_items = []
    for slot_name, item_data in hero.equipment.items():
        if item_data:
            lost_items.append(item_data)
    lost_items.extend(hero.inventory)

    # Mark hero as dead and clear gear
    hero.is_alive = False
    hero.equipment = {}
    hero.inventory = []

    # Save immediately
    save_profile(profile)

    return {
        "hero_id": hero_id,
        "hero_name": hero.name,
        "class_id": hero.class_id,
        "player_id": dead_player_id,
        "username": owner_username,
        "lost_items": lost_items,
    }


def track_kill(match_id: str, killer_id: str, victim_is_boss: bool = False) -> None:
    """Track a kill for gold reward calculation.

    Called by the turn resolver when an enemy dies.
    """
    if match_id not in _kill_tracker:
        _kill_tracker[match_id] = {}
    if killer_id not in _kill_tracker[match_id]:
        _kill_tracker[match_id][killer_id] = {"enemy_kills": 0, "boss_kills": 0}

    if victim_is_boss:
        _kill_tracker[match_id][killer_id]["boss_kills"] += 1
    else:
        _kill_tracker[match_id][killer_id]["enemy_kills"] += 1


def get_kill_tracker(match_id: str) -> dict[str, dict[str, int]]:
    """Get the kill tracker for a match."""
    return dict(_kill_tracker.get(match_id, {}))


# ---------------------------------------------------------------------------
# Combat Stats Tracker — Per-player match statistics for post-match summary
# ---------------------------------------------------------------------------

def _ensure_combat_stats(match_id: str, player_id: str) -> dict[str, int]:
    """Ensure the combat stats entry exists for a player and return it."""
    if match_id not in _combat_stats:
        _combat_stats[match_id] = {}
    if player_id not in _combat_stats[match_id]:
        _combat_stats[match_id][player_id] = {
            "damage_dealt": 0,
            "damage_taken": 0,
            "healing_done": 0,
            "items_looted": 0,
            "turns_survived": 0,
        }
    return _combat_stats[match_id][player_id]


def track_damage_dealt(match_id: str, player_id: str, amount: int) -> None:
    """Track damage dealt by a player."""
    stats = _ensure_combat_stats(match_id, player_id)
    stats["damage_dealt"] += amount


def track_damage_taken(match_id: str, player_id: str, amount: int) -> None:
    """Track damage taken by a player."""
    stats = _ensure_combat_stats(match_id, player_id)
    stats["damage_taken"] += amount


def track_healing_done(match_id: str, player_id: str, amount: int) -> None:
    """Track healing done by a player (potions, skills, HoTs)."""
    stats = _ensure_combat_stats(match_id, player_id)
    stats["healing_done"] += amount


def track_items_looted(match_id: str, player_id: str, count: int = 1) -> None:
    """Track items looted by a player."""
    stats = _ensure_combat_stats(match_id, player_id)
    stats["items_looted"] += count


def track_turn_survived(match_id: str, player_id: str, turn_number: int) -> None:
    """Track the last turn a player was alive."""
    stats = _ensure_combat_stats(match_id, player_id)
    stats["turns_survived"] = max(stats["turns_survived"], turn_number)


def get_combat_stats(match_id: str) -> dict[str, dict[str, int]]:
    """Get all combat stats for a match."""
    return dict(_combat_stats.get(match_id, {}))


# ---------------------------------------------------------------------------
# Arena Analyst — Per-turn timeline buffer & match report writer
# ---------------------------------------------------------------------------

def record_turn_events(match_id: str, turn_number: int, turn_result, all_units: dict) -> None:
    """Append a compact event summary for this turn to the match timeline.

    Called from tick_loop.py after resolve_turn() and combat stats tracking.
    Converts TurnResult actions into lightweight event dicts for later analysis.
    """
    if match_id not in _match_timeline:
        _match_timeline[match_id] = []

    events: list[dict] = []

    for act in turn_result.actions:
        # Movement events
        if act.action_type == "move" and act.success and act.to_x is not None:
            events.append({
                "type": "move",
                "unit": act.player_id,
                "to": [act.to_x, act.to_y],
            })

        # Damage events (melee, ranged, skill damage)
        if act.damage_dealt and act.damage_dealt > 0:
            events.append({
                "type": "damage",
                "src": act.player_id,
                "tgt": act.target_id,
                "dmg": act.damage_dealt,
                "skill": act.skill_id or act.action_type,
                "crit": act.is_crit,
            })

        # Heal events
        if act.heal_amount and act.heal_amount > 0:
            events.append({
                "type": "heal",
                "src": act.player_id,
                "tgt": act.target_id or act.player_id,
                "amt": act.heal_amount,
                "skill": act.skill_id or "heal",
            })

        # Buff events
        if act.buff_applied:
            events.append({
                "type": "buff",
                "src": act.player_id,
                "tgt": act.target_id or act.player_id,
                "buff": act.skill_id or "buff",
            })

    # Death events
    for death_id in turn_result.deaths:
        # Try to identify the killer from damage actions this turn
        killer_id = None
        for act in turn_result.actions:
            if act.killed and act.target_id == death_id:
                killer_id = act.player_id
                break
        event = {"type": "death", "unit": death_id}
        if killer_id:
            event["killer"] = killer_id
        events.append(event)

    # Elite kill events
    for ek in turn_result.elite_kills:
        events.append({
            "type": "elite_kill",
            "monster": ek.get("display_name", "unknown"),
            "rarity": ek.get("monster_rarity", "normal"),
            "killer": ek.get("killer_id"),
        })

    _match_timeline[match_id].append({
        "turn": turn_number,
        "events": events,
    })


def save_match_report(match_id: str, winner: str, turn_number: int) -> str | None:
    """Serialize full match data + timeline to a JSON file for Arena Analyst.

    Writes to server/data/match_history/{timestamp}_{match_id}.json.
    Called from tick_loop.py right before end_match().
    Returns the filename on success, or None on failure.
    """
    import json
    import os
    from datetime import datetime, timezone

    match = _active_matches.get(match_id)
    if not match:
        return None

    players = _player_states.get(match_id, {})
    kill_data = _kill_tracker.get(match_id, {})
    stats_data = _combat_stats.get(match_id, {})
    timeline = _match_timeline.get(match_id, [])

    # --- Build team rosters ---
    teams: dict[str, list[dict]] = {"team_a": [], "team_b": [], "team_c": [], "team_d": []}
    team_map = {
        "a": "team_a", "b": "team_b", "c": "team_c", "d": "team_d",
    }
    for pid, player in players.items():
        team_key = team_map.get(player.team, "team_b")
        teams[team_key].append({
            "unit_id": pid,
            "username": player.username,
            "class_id": player.class_id,
            "team": player.team,
            "is_ai": player.unit_type != "human",
            "base_hp": player.max_hp,
            "base_melee_damage": getattr(player, 'melee_damage', 0),
            "base_armor": getattr(player, 'armor', 0),
        })

    # Remove empty teams
    teams = {k: v for k, v in teams.items() if v}

    # --- Build per-unit stats ---
    unit_stats: dict[str, dict] = {}
    for pid, player in players.items():
        pstats = stats_data.get(pid, {})
        kills = kill_data.get(pid, {"enemy_kills": 0, "boss_kills": 0})
        total_kills = kills.get("enemy_kills", 0) + kills.get("boss_kills", 0)
        dmg_dealt = pstats.get("damage_dealt", 0)
        dmg_taken = pstats.get("damage_taken", 0)

        # Compute highest hit from timeline
        highest_hit = 0
        overkill_damage = 0
        for turn_entry in timeline:
            for evt in turn_entry.get("events", []):
                if evt.get("type") == "damage" and evt.get("src") == pid:
                    hit = evt.get("dmg", 0)
                    if hit > highest_hit:
                        highest_hit = hit
                if evt.get("type") == "death" and evt.get("killer") == pid:
                    # Simple overkill estimation not possible without HP tracking
                    pass

        unit_stats[pid] = {
            "unit_id": pid,
            "username": player.username,
            "class_id": player.class_id,
            "team": player.team,
            "is_ai": player.unit_type != "human",
            "status": "survived" if player.is_alive else "died",
            "damage_dealt": dmg_dealt,
            "damage_taken": dmg_taken,
            "healing_done": pstats.get("healing_done", 0),
            "kills": total_kills,
            "boss_kills": kills.get("boss_kills", 0),
            "deaths": 0 if player.is_alive else 1,
            "turns_survived": pstats.get("turns_survived", 0),
            "items_looted": pstats.get("items_looted", 0),
            "highest_hit": highest_hit,
            "overkill_damage": overkill_damage,
        }

    # --- Compute summary ---
    team_totals: dict[str, dict] = {}
    for team_key in teams:
        team_letter = team_key.replace("team_", "")
        team_totals[team_key] = {
            "total_damage": 0, "total_healing": 0, "kills": 0, "deaths": 0,
        }
        for pid, us in unit_stats.items():
            if us["team"] == team_letter:
                team_totals[team_key]["total_damage"] += us["damage_dealt"]
                team_totals[team_key]["total_healing"] += us["healing_done"]
                team_totals[team_key]["kills"] += us["kills"]
                team_totals[team_key]["deaths"] += us["deaths"]

    # First blood detection
    first_blood_turn = None
    first_blood_killer = None
    first_blood_victim = None
    for turn_entry in timeline:
        for evt in turn_entry.get("events", []):
            if evt.get("type") == "death":
                first_blood_turn = turn_entry["turn"]
                first_blood_killer = evt.get("killer")
                first_blood_victim = evt.get("unit")
                break
        if first_blood_turn is not None:
            break

    # MVP: highest (damage_dealt + kills * 100) composite score
    mvp_id = None
    mvp_score = -1
    for pid, us in unit_stats.items():
        score = us["damage_dealt"] + us["kills"] * 100
        if score > mvp_score:
            mvp_score = score
            mvp_id = pid

    summary = {}
    for team_key, totals in team_totals.items():
        summary[f"{team_key}_total_damage"] = totals["total_damage"]
        summary[f"{team_key}_total_healing"] = totals["total_healing"]
        summary[f"{team_key}_kills"] = totals["kills"]
        summary[f"{team_key}_deaths"] = totals["deaths"]

    summary["first_blood_turn"] = first_blood_turn
    summary["first_blood_killer"] = first_blood_killer
    summary["first_blood_victim"] = first_blood_victim
    summary["mvp"] = mvp_id
    summary["mvp_damage"] = unit_stats[mvp_id]["damage_dealt"] if mvp_id else 0
    summary["mvp_kills"] = unit_stats[mvp_id]["kills"] if mvp_id else 0

    # --- Build config snapshot ---
    config_snapshot = {
        "max_players": match.config.max_players,
        "tick_rate": match.config.tick_rate,
        "ai_opponents": match.config.ai_opponents,
        "ai_allies": match.config.ai_allies,
        "ai_opponent_classes": list(match.config.ai_opponent_classes),
        "ai_ally_classes": list(match.config.ai_ally_classes),
    }

    # --- Determine match type string ---
    match_type_str = match.config.match_type
    if hasattr(match_type_str, "value"):
        match_type_str = match_type_str.value

    # --- Assemble full report ---
    now = datetime.now(timezone.utc)
    report = {
        "match_id": match_id,
        "timestamp": now.isoformat(),
        "duration_turns": turn_number,
        "map_id": match.config.map_id,
        "match_type": match_type_str,
        "winner": winner,
        "config": config_snapshot,
        "teams": teams,
        "unit_stats": unit_stats,
        "timeline": timeline,
        "summary": summary,
    }

    # --- Write to disk ---
    # Resolve path relative to the server package root
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    history_dir = os.path.join(base_dir, "data", "match_history")
    os.makedirs(history_dir, exist_ok=True)

    timestamp_str = now.strftime("%Y-%m-%d_%H%M%S")
    # Sanitize match_id for filename (replace non-alphanumeric with _)
    safe_id = "".join(c if c.isalnum() else "_" for c in match_id)
    filename = f"{timestamp_str}_{safe_id}.json"
    filepath = os.path.join(history_dir, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"[Analyst] Match report saved: {filename}")
        return filename
    except Exception as e:
        print(f"[Analyst] Failed to save match report: {e}")
        return None


def _persist_post_match(match_id: str) -> dict:
    """Persist surviving heroes' inventory, equipment, and gold back to profiles.

    Called when a match ends. For each unit with a hero_id (human or AI hero ally):
    - Copies current inventory/equipment from PlayerState back to Hero
    - Awards gold based on kills (configurable per enemy/boss)
    - Increments matches_survived + enemies_killed counters
    - Saves profile to disk

    Returns a dict of per-player outcomes for the match_end payload.
    """
    from app.services.persistence import load_or_create_profile, save_profile

    combat_config = get_combat_config()
    gold_per_kill = combat_config.get("gold_per_enemy_kill", 10)
    gold_per_boss = combat_config.get("gold_per_boss_kill", 50)
    gold_clear_bonus = combat_config.get("gold_dungeon_clear_bonus", 25)

    players = _player_states.get(match_id, {})
    kill_data = _kill_tracker.get(match_id, {})
    ally_map = _hero_ally_map.get(match_id, {})
    outcomes = {}

    for pid, player in players.items():
        if not player.hero_id:
            continue  # No persistent hero — skip

        # Determine owner username for loading the profile
        # AI hero allies use _hero_ally_map; human players use their own username
        if pid in ally_map:
            owner_username = ally_map[pid]
        elif player.unit_type == "human":
            owner_username = player.username
        else:
            continue  # Generic AI unit without hero — skip

        profile = load_or_create_profile(owner_username)
        hero = None
        for h in profile.heroes:
            if h.hero_id == player.hero_id:
                hero = h
                break

        if not hero:
            continue

        if player.is_alive or player.extracted:
            # Surviving/extracted hero: persist inventory and equipment back to profile
            hero.equipment = dict(player.equipment)
            hero.inventory = list(player.inventory)
            hero.matches_survived += 1

            # Calculate and award gold
            kills = kill_data.get(pid, {"enemy_kills": 0, "boss_kills": 0})
            base_gold = (
                kills["enemy_kills"] * gold_per_kill
                + kills["boss_kills"] * gold_per_boss
                + gold_clear_bonus
            )
            # Phase 16A: Gold Find % bonus from equipment
            gold_find_bonus = getattr(player, 'gold_find_pct', 0.0)
            gold_earned = int(base_gold * (1.0 + gold_find_bonus))
            profile.gold += gold_earned
            hero.enemies_killed += kills["enemy_kills"] + kills["boss_kills"]

            save_profile(profile)

            outcomes[pid] = {
                "player_id": pid,
                "username": player.username,
                "hero_id": player.hero_id,
                "hero_name": hero.name,
                "status": "extracted" if player.extracted else "survived",
                "gold_earned": gold_earned,
                "items_kept": len(hero.inventory) + len([v for v in hero.equipment.values() if v]),
            }
        else:
            # Dead hero: permadeath was already handled via handle_hero_permadeath
            # Just record the outcome
            outcomes[pid] = {
                "player_id": pid,
                "username": player.username,
                "hero_id": player.hero_id,
                "hero_name": hero.name,
                "status": "died",
                "gold_earned": 0,
                "items_kept": 0,
            }

    return outcomes


def get_match_end_payload(match_id: str) -> dict:
    """Build extended match_end payload with per-hero outcomes and combat stats.

    Returns a dict suitable for adding to the match_end WS broadcast.
    Includes both human players and AI hero allies.
    """
    outcomes = {}
    players = _player_states.get(match_id, {})
    kill_data = _kill_tracker.get(match_id, {})
    stats_data = _combat_stats.get(match_id, {})
    ally_map = _hero_ally_map.get(match_id, {})
    combat_config = get_combat_config()
    gold_per_kill = combat_config.get("gold_per_enemy_kill", 10)
    gold_per_boss = combat_config.get("gold_per_boss_kill", 50)

    # Detect if boss was killed this match
    boss_killed = False
    for pid_kills in kill_data.values():
        if pid_kills.get("boss_kills", 0) > 0:
            boss_killed = True
            break

    # Detect dungeon mode
    match = _active_matches.get(match_id)
    is_dungeon = False
    if match:
        is_dungeon = (
            match.config.match_type in (MatchType.DUNGEON, MatchType.PVPVE)
            or is_dungeon_map(match.config.map_id)
        )

    for pid, player in players.items():
        # Include human players and AI hero allies
        is_hero_ally = pid in ally_map
        if player.unit_type != "human" and not is_hero_ally:
            continue
        if not player.hero_id and player.unit_type == "human":
            # Arena mode player — no hero tracking, but include combat stats
            pstats = stats_data.get(pid, {})
            outcomes[pid] = {
                "player_id": pid,
                "username": player.username,
                "class_id": player.class_id,
                "sprite_variant": getattr(player, 'sprite_variant', 1),
                "status": "survived" if player.is_alive else "died",
                "damage_dealt": pstats.get("damage_dealt", 0),
                "damage_taken": pstats.get("damage_taken", 0),
                "healing_done": pstats.get("healing_done", 0),
                "items_looted": pstats.get("items_looted", 0),
                "turns_survived": pstats.get("turns_survived", 0),
            }
            continue
        elif not player.hero_id:
            continue

        kills = kill_data.get(pid, {"enemy_kills": 0, "boss_kills": 0})
        pstats = stats_data.get(pid, {})
        base_gold = kills["enemy_kills"] * gold_per_kill + kills["boss_kills"] * gold_per_boss
        # Phase 16A: Gold Find % bonus from equipment
        gold_find_bonus = getattr(player, 'gold_find_pct', 0.0)
        gold_earned = int(base_gold * (1.0 + gold_find_bonus))

        outcomes[pid] = {
            "player_id": pid,
            "username": player.username,
            "hero_id": player.hero_id,
            "hero_name": getattr(player, '_hero_name', None) or player.username,
            "class_id": player.class_id,
            "sprite_variant": getattr(player, 'sprite_variant', 1),
            "status": "survived" if player.is_alive else "died",
            "enemy_kills": kills["enemy_kills"],
            "boss_kills": kills["boss_kills"],
            "gold_earned": gold_earned,
            "damage_dealt": pstats.get("damage_dealt", 0),
            "damage_taken": pstats.get("damage_taken", 0),
            "healing_done": pstats.get("healing_done", 0),
            "items_looted": pstats.get("items_looted", 0),
            "turns_survived": pstats.get("turns_survived", 0),
        }

    # ── Build full battle scoreboard (all units, both teams) for post-match display ──
    all_units_list = []
    team_totals: dict[str, dict] = {}  # team -> aggregate stats

    for pid, player in players.items():
        pstats = stats_data.get(pid, {})
        kills = kill_data.get(pid, {"enemy_kills": 0, "boss_kills": 0})
        team = getattr(player, 'team', 'b')
        is_ai = player.unit_type == "ai"

        unit_entry = {
            "unit_id": pid,
            "username": player.username,
            "class_id": player.class_id,
            "team": team,
            "is_ai": is_ai,
            "status": "survived" if player.is_alive else "died",
            "damage_dealt": pstats.get("damage_dealt", 0),
            "damage_taken": pstats.get("damage_taken", 0),
            "healing_done": pstats.get("healing_done", 0),
            "kills": kills.get("enemy_kills", 0),
            "turns_survived": pstats.get("turns_survived", 0),
        }
        all_units_list.append(unit_entry)

        # Accumulate team totals
        if team not in team_totals:
            team_totals[team] = {
                "team": team,
                "damage_dealt": 0,
                "damage_taken": 0,
                "healing_done": 0,
                "kills": 0,
                "survived": 0,
                "died": 0,
            }
        tt = team_totals[team]
        tt["damage_dealt"] += unit_entry["damage_dealt"]
        tt["damage_taken"] += unit_entry["damage_taken"]
        tt["healing_done"] += unit_entry["healing_done"]
        tt["kills"] += unit_entry["kills"]
        if player.is_alive:
            tt["survived"] += 1
        else:
            tt["died"] += 1

    return {
        "hero_outcomes": outcomes,
        "boss_killed": boss_killed,
        "is_dungeon": is_dungeon,
        "battle_scoreboard": all_units_list,
        "team_totals": team_totals,
    }


def validate_dungeon_hero_selections(match_id: str) -> tuple[bool, str, str | None]:
    """Validate that all human players in a dungeon match have selected a hero.

    Returns (True, "", None) if valid, or (False, error_message, offending_player_id) if not.
    Arena matches always pass.
    """
    match = _active_matches.get(match_id)
    if not match:
        return False, "Match not found", None

    # Only dungeon match type requires hero selection.
    # Non-dungeon modes (PvP, Solo PvE, Mixed, PVPVE) use class selection instead.
    # PVPVE supports optional hero selection but doesn't require it.
    is_dungeon = match.config.match_type == MatchType.DUNGEON
    if not is_dungeon:
        return True, "", None

    players = _player_states.get(match_id, {})
    hero_selections = _hero_selections.get(match_id, {})

    for pid, player in players.items():
        if player.unit_type != "human":
            continue
        if pid not in hero_selections:
            return False, f"{player.username} has not selected a hero", pid
        selection = hero_selections[pid]
        if isinstance(selection, list) and len(selection) == 0:
            return False, f"{player.username} has not selected a hero", pid

    return True, "", None
