"""
AI Exploration — Room-aware strategic dungeon exploration.

Phase: Strategic Dungeon Exploration, Sub-Phase A (Foundation)

Provides:
  - Room adjacency graph construction from room definitions + door positions
  - Per-team room discovery state tracking (undiscovered / discovered / cleared)
  - Exploration target API for AI leaders to select next room to explore

Depends on:
  - map_loader: room definitions, door positions, chest positions
  - match_manager: FOV cache, match teams, match players
  - ai_pathfinding: A* for distance estimation
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum number of a team's FOV tiles that must overlap a room's bounds
# before that room transitions from undiscovered → discovered.
_ROOM_DISCOVER_OVERLAP = 1

# Whether opening all chests in a room is required for "cleared" status.
# If False, only enemy kills matter.
_ROOM_CLEAR_REQUIRES_CHESTS = True

# Priority multipliers for exploration target scoring.
# Higher = more attractive target.
_LEADER_EXPLORE_PRIORITY_LOOT = 1.5   # rooms with unopened chests
_LEADER_EXPLORE_PRIORITY_ENEMY = 1.0  # rooms with known enemies

# Door adjacency tolerance — how far a door can be from a room bound edge
# and still count as connecting that room (handles off-by-one in map data).
_DOOR_ROOM_TOLERANCE = 1


# ---------------------------------------------------------------------------
# Module-level caches (keyed by match_id, cleared on match end)
# ---------------------------------------------------------------------------

# {match_id: {room_id: set(neighbor_room_ids)}}
_room_graph: dict[str, dict[str, set[str]]] = {}

# {match_id: {"a": {room_id: "undiscovered"|"discovered"|"cleared"}, ...}}
_room_discovery: dict[str, dict[str, dict[str, str]]] = {}

# {match_id: {room_id: {"center": (x,y), "bounds": {...}, ...}}}
_room_info: dict[str, dict[str, dict]] = {}

# {match_id: {room_id: [(cx, cy), ...]}}  — chest positions per room
_room_chests: dict[str, dict[str, list[tuple[int, int]]]] = {}

# {match_id: {room_id: [(ex, ey), ...]}}  — enemy spawn positions per room
_room_enemy_spawns: dict[str, dict[str, list[tuple[int, int]]]] = {}

# {match_id: {"x,y": [room_id, ...]}}  — door → rooms it connects
_door_rooms: dict[str, dict[str, list[str]]] = {}

# {match_id: {team: {room_id: expiry_turn}}}  — temporarily skipped rooms
# When a leader repeatedly fails to path to a room, it is marked as skipped
# so get_next_exploration_target() picks the next-best candidate.  The skip
# expires after _SKIP_EXPIRY_TURNS so the room can be retried later (the
# dungeon layout may become more accessible after doors open).
_skipped_rooms: dict[str, dict[str, dict[str, int]]] = {}
_SKIP_EXPIRY_TURNS = 40


# ---------------------------------------------------------------------------
# A1: Room Adjacency Graph
# ---------------------------------------------------------------------------

def build_room_graph(
    match_id: str,
    rooms: list[dict],
    doors: list[dict],
    chests: list[dict] | None = None,
) -> dict[str, set[str]]:
    """Build a room connectivity graph from room definitions and door positions.

    For each door, determine which rooms it connects by checking if the door
    position falls on or adjacent to the edge of a room's bounds.

    Also caches room metadata (center, bounds) and chest-to-room mappings.

    Returns the adjacency dict: {room_id: set(neighbor_room_ids)}.
    """
    chests = chests or []
    graph: dict[str, set[str]] = {}
    info: dict[str, dict] = {}
    room_chests: dict[str, list[tuple[int, int]]] = {}
    room_enemy_spawns: dict[str, list[tuple[int, int]]] = {}
    door_room_map: dict[str, list[str]] = {}

    # Pre-compute room info and initialize graph nodes
    for room in rooms:
        rid = room.get("id")
        bounds = room.get("bounds", {})
        if not rid or not bounds:
            continue

        x_min = bounds.get("x_min", 0)
        y_min = bounds.get("y_min", 0)
        x_max = bounds.get("x_max", 0)
        y_max = bounds.get("y_max", 0)

        center_x = (x_min + x_max) // 2
        center_y = (y_min + y_max) // 2

        graph[rid] = set()
        info[rid] = {
            "center": (center_x, center_y),
            "bounds": bounds,
            "name": room.get("name", rid),
            "purpose": room.get("purpose", ""),
        }
        room_chests[rid] = []
        room_enemy_spawns[rid] = []

        # Cache enemy spawn positions
        for esp in room.get("enemy_spawns", []):
            room_enemy_spawns[rid].append((esp["x"], esp["y"]))

    # Map chests to rooms
    for chest in chests:
        cx, cy = chest["x"], chest["y"]
        for rid, rinfo in info.items():
            b = rinfo["bounds"]
            if (b["x_min"] <= cx <= b["x_max"]
                    and b["y_min"] <= cy <= b["y_max"]):
                room_chests[rid].append((cx, cy))
                break  # A chest belongs to at most one room

    # Map doors to rooms — a door connects rooms whose bounds it touches
    for door in doors:
        dx, dy = door["x"], door["y"]
        door_key = f"{dx},{dy}"
        touching_rooms: list[str] = []

        for rid, rinfo in info.items():
            b = rinfo["bounds"]
            # Door is "touching" a room if it's within tolerance of the room
            # bounds edge (doors typically sit on the boundary wall).
            x_near = b["x_min"] - _DOOR_ROOM_TOLERANCE <= dx <= b["x_max"] + _DOOR_ROOM_TOLERANCE
            y_near = b["y_min"] - _DOOR_ROOM_TOLERANCE <= dy <= b["y_max"] + _DOOR_ROOM_TOLERANCE
            if x_near and y_near:
                touching_rooms.append(rid)

        door_room_map[door_key] = touching_rooms

        # Create bidirectional edges between all rooms this door touches
        for i in range(len(touching_rooms)):
            for j in range(i + 1, len(touching_rooms)):
                r1, r2 = touching_rooms[i], touching_rooms[j]
                graph[r1].add(r2)
                graph[r2].add(r1)

    # Store in module cache
    _room_graph[match_id] = graph
    _room_info[match_id] = info
    _room_chests[match_id] = room_chests
    _room_enemy_spawns[match_id] = room_enemy_spawns
    _door_rooms[match_id] = door_room_map

    return graph


# ---------------------------------------------------------------------------
# A2: Room Discovery State
# ---------------------------------------------------------------------------

def init_room_discovery(match_id: str, teams: list[str]) -> None:
    """Initialize per-team room discovery state for all rooms in the match.

    All rooms start as "undiscovered" for every team.
    """
    graph = _room_graph.get(match_id, {})
    _room_discovery[match_id] = {}
    for team in teams:
        _room_discovery[match_id][team] = {
            rid: "undiscovered" for rid in graph
        }


def update_room_discovery(
    match_id: str,
    team: str,
    team_fov: set[tuple[int, int]],
) -> list[str]:
    """Update discovery state for a team based on their current shared FOV.

    Transitions undiscovered → discovered when any team FOV tile overlaps
    the room bounds (≥ _ROOM_DISCOVER_OVERLAP tiles).

    Returns list of room_ids that were newly discovered this tick.
    """
    discovery = _room_discovery.get(match_id, {}).get(team)
    if not discovery:
        return []

    info = _room_info.get(match_id, {})
    newly_discovered: list[str] = []

    for rid, state in discovery.items():
        if state != "undiscovered":
            continue

        rinfo = info.get(rid)
        if not rinfo:
            continue

        b = rinfo["bounds"]
        overlap = 0
        # Count how many FOV tiles fall inside this room's bounds
        for tx, ty in team_fov:
            if (b["x_min"] <= tx <= b["x_max"]
                    and b["y_min"] <= ty <= b["y_max"]):
                overlap += 1
                if overlap >= _ROOM_DISCOVER_OVERLAP:
                    break

        if overlap >= _ROOM_DISCOVER_OVERLAP:
            discovery[rid] = "discovered"
            newly_discovered.append(rid)

    return newly_discovered


def update_room_clearance(
    match_id: str,
    team: str,
    all_units: dict,
    chest_states: dict[str, str] | None = None,
) -> list[str]:
    """Check discovered rooms for clearance (all enemies dead, all chests opened).

    Transitions discovered → cleared when:
      - All enemy spawn positions in the room have no alive enemies on them,
        AND no alive enemies currently inside the room bounds (team "b" units)
      - All chests in the room are opened (if _ROOM_CLEAR_REQUIRES_CHESTS)

    Returns list of room_ids that were newly cleared this tick.
    """
    discovery = _room_discovery.get(match_id, {}).get(team)
    if not discovery:
        return []

    info = _room_info.get(match_id, {})
    room_chests = _room_chests.get(match_id, {})
    newly_cleared: list[str] = []

    for rid, state in discovery.items():
        if state != "discovered":
            continue

        rinfo = info.get(rid)
        if not rinfo:
            continue

        b = rinfo["bounds"]

        # Check: are there any alive enemy units inside this room?
        enemies_alive_in_room = False
        for uid, unit in all_units.items():
            if not unit.is_alive:
                continue
            if unit.team == team:
                continue  # Same team — not an enemy
            ux, uy = unit.position.x, unit.position.y
            if (b["x_min"] <= ux <= b["x_max"]
                    and b["y_min"] <= uy <= b["y_max"]):
                enemies_alive_in_room = True
                break

        if enemies_alive_in_room:
            continue

        # Check: are all chests in this room opened?
        if _ROOM_CLEAR_REQUIRES_CHESTS and chest_states:
            chests_in_room = room_chests.get(rid, [])
            all_chests_opened = True
            for cx, cy in chests_in_room:
                ckey = f"{cx},{cy}"
                cstate = chest_states.get(ckey, "")
                if cstate.startswith("unopened"):
                    all_chests_opened = False
                    break
            if not all_chests_opened:
                continue

        discovery[rid] = "cleared"
        newly_cleared.append(rid)

    return newly_cleared


# ---------------------------------------------------------------------------
# A3: Exploration Target API
# ---------------------------------------------------------------------------

def get_next_exploration_target(
    match_id: str,
    team: str,
    current_pos: tuple[int, int],
) -> dict | None:
    """Return the best next room to explore for a team leader.

    Selection priority:
      1. discovered-but-uncleared rooms (known content not yet handled)
      2. undiscovered rooms adjacent to a discovered/cleared room
      3. any remaining undiscovered room

    Within each priority tier, prefer the closest room (Manhattan distance
    to room center).

    Returns: {room_id, center: (x,y), entrance: (x,y)|None, priority: int}
             or None if all rooms are cleared.
    """
    discovery = _room_discovery.get(match_id, {}).get(team)
    if not discovery:
        return None

    graph = _room_graph.get(match_id, {})
    info = _room_info.get(match_id, {})

    # Classify rooms by priority
    # Priority 1: discovered but not cleared (we know about it, go finish it)
    # Priority 2: undiscovered but adjacent to discovered/cleared (frontier)
    # Priority 3: undiscovered, not adjacent to anything known (deep unknown)
    candidates: list[tuple[int, str, int]] = []  # (priority, room_id, distance)

    discovered_or_cleared = {
        rid for rid, st in discovery.items() if st in ("discovered", "cleared")
    }

    # Build set of currently-skipped rooms for this team
    skipped = _skipped_rooms.get(match_id, {}).get(team, {})

    for rid, state in discovery.items():
        if state == "cleared":
            continue  # Already done

        # Skip rooms that were recently marked as unreachable
        if rid in skipped:
            continue

        rinfo = info.get(rid)
        if not rinfo:
            continue

        center = rinfo["center"]
        dist = abs(current_pos[0] - center[0]) + abs(current_pos[1] - center[1])

        if state == "discovered":
            # Priority 1: discovered but uncleared
            priority = 1
        elif state == "undiscovered":
            # Check if adjacent to any discovered/cleared room
            neighbors = graph.get(rid, set())
            if neighbors & discovered_or_cleared:
                priority = 2  # Frontier — adjacent to known territory
            else:
                priority = 3  # Deep unknown
        else:
            continue

        candidates.append((priority, rid, dist))

    if not candidates:
        # All rooms are either cleared or skipped — try clearing skips
        # so the leader has something to target.
        if skipped:
            _skipped_rooms.get(match_id, {}).get(team, {}).clear()
            return get_next_exploration_target(match_id, team, current_pos)
        return None

    # Sort by priority (ascending) then distance (ascending)
    candidates.sort(key=lambda c: (c[0], c[2]))

    best_priority, best_rid, best_dist = candidates[0]
    best_info = info[best_rid]

    # Find entrance: prefer the door position that connects from a
    # discovered/cleared room to this target room
    entrance = _find_room_entrance(match_id, best_rid, discovered_or_cleared)

    return {
        "room_id": best_rid,
        "center": best_info["center"],
        "entrance": entrance or best_info["center"],
        "priority": best_priority,
    }


def _find_room_entrance(
    match_id: str,
    target_room_id: str,
    known_rooms: set[str],
) -> tuple[int, int] | None:
    """Find the door position connecting a known room to the target room.

    Returns the door (x, y) if found, else None.
    """
    door_room_map = _door_rooms.get(match_id, {})

    for door_key, rooms_touching in door_room_map.items():
        if target_room_id in rooms_touching:
            # Check if this door also touches a known room
            for rid in rooms_touching:
                if rid != target_room_id and rid in known_rooms:
                    parts = door_key.split(",")
                    return (int(parts[0]), int(parts[1]))

    return None


# ---------------------------------------------------------------------------
# Helper: Get the room a position is currently inside
# ---------------------------------------------------------------------------

def get_current_room(
    match_id: str,
    x: int,
    y: int,
) -> dict | None:
    """Return room info dict for the room containing (x, y), or None.

    Returns: {room_id, center, bounds, name, purpose} or None.
    """
    info = _room_info.get(match_id, {})
    for rid, rinfo in info.items():
        b = rinfo["bounds"]
        if (b["x_min"] <= x <= b["x_max"]
                and b["y_min"] <= y <= b["y_max"]):
            return {"room_id": rid, **rinfo}
    return None


# ---------------------------------------------------------------------------
# Helper: Exploration progress for a team
# ---------------------------------------------------------------------------

def get_exploration_progress(match_id: str, team: str) -> dict:
    """Return exploration stats for a team.

    Returns: {
        total_rooms, discovered_rooms, cleared_rooms,
        exploration_pct, clearance_pct
    }
    """
    discovery = _room_discovery.get(match_id, {}).get(team, {})
    total = len(discovery)
    if total == 0:
        return {
            "total_rooms": 0,
            "discovered_rooms": 0,
            "cleared_rooms": 0,
            "exploration_pct": 0.0,
            "clearance_pct": 0.0,
        }

    discovered = sum(1 for s in discovery.values() if s in ("discovered", "cleared"))
    cleared = sum(1 for s in discovery.values() if s == "cleared")
    return {
        "total_rooms": total,
        "discovered_rooms": discovered,
        "cleared_rooms": cleared,
        "exploration_pct": round(discovered / total * 100, 1),
        "clearance_pct": round(cleared / total * 100, 1),
    }


# ---------------------------------------------------------------------------
# Helper: Get discovery state dict (for external inspection / tests)
# ---------------------------------------------------------------------------

def get_room_discovery(match_id: str, team: str) -> dict[str, str]:
    """Return the discovery state dict for a team: {room_id: state}."""
    return dict(_room_discovery.get(match_id, {}).get(team, {}))


def get_room_graph(match_id: str) -> dict[str, set[str]]:
    """Return the room adjacency graph for a match."""
    return dict(_room_graph.get(match_id, {}))


def get_room_info(match_id: str) -> dict[str, dict]:
    """Return cached room info for a match."""
    return dict(_room_info.get(match_id, {}))


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def skip_room(
    match_id: str,
    team: str,
    room_id: str,
    current_turn: int,
) -> None:
    """Mark a room as temporarily unreachable for a team.

    The room will be excluded from ``get_next_exploration_target()`` until
    *current_turn + _SKIP_EXPIRY_TURNS*, at which point it becomes eligible
    again.
    """
    if match_id not in _skipped_rooms:
        _skipped_rooms[match_id] = {}
    if team not in _skipped_rooms[match_id]:
        _skipped_rooms[match_id][team] = {}
    _skipped_rooms[match_id][team][room_id] = current_turn + _SKIP_EXPIRY_TURNS


def expire_skipped_rooms(match_id: str, current_turn: int) -> None:
    """Remove expired skip entries so rooms become targetable again."""
    match_skips = _skipped_rooms.get(match_id)
    if not match_skips:
        return
    for team in list(match_skips):
        team_skips = match_skips[team]
        expired = [rid for rid, exp in team_skips.items() if current_turn >= exp]
        for rid in expired:
            del team_skips[rid]


def clear_exploration_state(match_id: str | None = None) -> None:
    """Clear all exploration state for a match (or all matches)."""
    if match_id:
        _room_graph.pop(match_id, None)
        _room_discovery.pop(match_id, None)
        _room_info.pop(match_id, None)
        _room_chests.pop(match_id, None)
        _room_enemy_spawns.pop(match_id, None)
        _door_rooms.pop(match_id, None)
        _skipped_rooms.pop(match_id, None)
    else:
        _room_graph.clear()
        _room_discovery.clear()
        _room_info.clear()
        _room_chests.clear()
        _room_enemy_spawns.clear()
        _door_rooms.clear()
        _skipped_rooms.clear()
