"""
Smart Spawn System — Team-aware and FFA spawn placement.

Provides intelligent spawn position calculations based on match type:
- Team matches: teammates spawn in compact formations within designated zones
- FFA matches: players spawn maximally distant from each other
- All spawns validated against obstacles and overlaps
"""

from __future__ import annotations

from collections import deque


# Minimum Chebyshev distance between any two FFA players (target, not hard fail)
MIN_FFA_DISTANCE = 5


def assign_spawns(
    team_rosters: dict[str, list[str]],
    map_data: dict,
    is_ffa: bool = False,
) -> dict[str, tuple[int, int]]:
    """Top-level spawn orchestrator.

    Args:
        team_rosters: {"a": [pid1, pid2], "b": [pid3], ...}
        map_data: Full map JSON data (width, height, obstacles, spawn_zones, ffa_points)
        is_ffa: True for free-for-all, False for team-based

    Returns:
        {player_id: (x, y)} mapping for all players
    """
    width = map_data.get("width", 15)
    height = map_data.get("height", 15)
    obstacles = _parse_obstacles(map_data)

    if is_ffa:
        # Collect all player IDs in roster order
        all_players = []
        for team_ids in team_rosters.values():
            all_players.extend(team_ids)
        ffa_points = _parse_ffa_points(map_data)
        return compute_ffa_spawns(all_players, ffa_points, obstacles, width, height)
    else:
        spawn_zones = _parse_spawn_zones(map_data)
        return compute_team_spawns(team_rosters, spawn_zones, obstacles, width, height)


# ---------- Team-Based Spawning ----------


def compute_team_spawns(
    team_rosters: dict[str, list[str]],
    spawn_zones: dict[str, dict],
    obstacles: set[tuple[int, int]],
    width: int,
    height: int,
) -> dict[str, tuple[int, int]]:
    """Place teammates in compact formations within their team zones.

    Each team gets a rectangular zone. Teammates are placed adjacent
    to each other in a compact formation (BFS growth from zone center).
    """
    result: dict[str, tuple[int, int]] = {}
    occupied: set[tuple[int, int]] = set()

    for team_key, player_ids in team_rosters.items():
        if not player_ids:
            continue

        zone = spawn_zones.get(team_key)
        if not zone:
            zone = _fallback_zone(team_key, width, height)

        # Get walkable tiles within zone
        walkable = _get_walkable_in_zone(zone, obstacles, occupied, width, height)

        if not walkable:
            # Zone is fully blocked — BFS outward from zone center
            cx = (zone["x_min"] + zone["x_max"]) // 2
            cy = (zone["y_min"] + zone["y_max"]) // 2
            for pid in player_ids:
                pos = find_nearest_valid(cx, cy, obstacles, occupied, width, height)
                if pos:
                    result[pid] = pos
                    occupied.add(pos)
            continue

        # Find compact formation for this team
        formation = _find_compact_formation(len(player_ids), walkable)

        for i, pid in enumerate(player_ids):
            if i < len(formation):
                pos = formation[i]
            else:
                # More players than formation slots — find nearest valid
                ref = formation[0] if formation else (
                    (zone["x_min"] + zone["x_max"]) // 2,
                    (zone["y_min"] + zone["y_max"]) // 2,
                )
                pos = find_nearest_valid(ref[0], ref[1], obstacles, occupied, width, height)

            if pos:
                result[pid] = pos
                occupied.add(pos)

    return result


# ---------- Free-For-All Spawning ----------


def compute_ffa_spawns(
    player_ids: list[str],
    ffa_points: list[tuple[int, int]],
    obstacles: set[tuple[int, int]],
    width: int,
    height: int,
) -> dict[str, tuple[int, int]]:
    """Place FFA players maximally distant from each other.

    Greedy algorithm: each successive player is placed at the candidate point
    furthest from all already-placed players.
    """
    result: dict[str, tuple[int, int]] = {}
    occupied: set[tuple[int, int]] = set()

    # Filter FFA points to only walkable, in-bounds ones
    valid_points = [
        p for p in ffa_points
        if p not in obstacles and 0 <= p[0] < width and 0 <= p[1] < height
    ]

    if not valid_points:
        # Fallback: generate distributed points
        valid_points = _generate_distributed_points(width, height, obstacles, len(player_ids))

    placed: list[tuple[int, int]] = []

    for pid in player_ids:
        if not placed:
            # First player: pick the first valid point
            pos = valid_points[0] if valid_points else (1, 1)
            pos = _validate_or_fallback(pos, obstacles, occupied, width, height)
        else:
            # Find the valid point with maximum minimum distance to all placed
            best_pos = None
            best_min_dist = -1

            for candidate in valid_points:
                if candidate in occupied:
                    continue
                min_dist = min(_chebyshev_distance(candidate, p) for p in placed)
                if min_dist > best_min_dist:
                    best_min_dist = min_dist
                    best_pos = candidate

            if best_pos:
                pos = best_pos
            else:
                # All FFA points taken — find any walkable tile far from others
                pos = _find_distant_tile(placed, obstacles, occupied, width, height)

            pos = _validate_or_fallback(pos, obstacles, occupied, width, height)

        if pos:
            result[pid] = pos
            occupied.add(pos)
            placed.append(pos)

    return result


# ---------- Validation ----------


def validate_spawn(
    x: int, y: int,
    obstacles: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    width: int,
    height: int,
) -> bool:
    """Check if a position is a valid spawn point."""
    if x < 0 or x >= width or y < 0 or y >= height:
        return False
    if (x, y) in obstacles:
        return False
    if (x, y) in occupied:
        return False
    return True


def find_nearest_valid(
    target_x: int, target_y: int,
    obstacles: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    width: int, height: int,
) -> tuple[int, int] | None:
    """BFS outward from target to find nearest walkable, unoccupied tile."""
    if validate_spawn(target_x, target_y, obstacles, occupied, width, height):
        return (target_x, target_y)

    visited: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    queue.append((target_x, target_y))
    visited.add((target_x, target_y))

    while queue:
        cx, cy = queue.popleft()
        # Check all 8 neighbors (cardinal first, then diagonal)
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0),
                       (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            nx, ny = cx + dx, cy + dy
            if (nx, ny) in visited:
                continue
            visited.add((nx, ny))
            if validate_spawn(nx, ny, obstacles, occupied, width, height):
                return (nx, ny)
            if 0 <= nx < width and 0 <= ny < height:
                queue.append((nx, ny))

    return None  # No valid tile found (shouldn't happen on any real map)


# ---------- Internal Helpers ----------


def _parse_obstacles(map_data: dict) -> set[tuple[int, int]]:
    """Extract obstacle positions from map data.

    Supports both legacy arena maps (obstacles array) and dungeon/WFC maps
    (tiles grid with tile_legend). For tile-grid maps, walls and closed doors
    are treated as obstacles.
    """
    obstacles: set[tuple[int, int]] = set()

    # Dungeon / WFC maps: derive obstacles from tile grid
    tiles = map_data.get("tiles")
    if tiles:
        legend = map_data.get("tile_legend", {})
        wall_chars = {ch for ch, ttype in legend.items() if ttype == "wall"}
        door_chars = {ch for ch, ttype in legend.items() if ttype == "door"}
        blocking = wall_chars | door_chars
        for y, row in enumerate(tiles):
            for x, ch in enumerate(row):
                if ch in blocking:
                    obstacles.add((x, y))
        return obstacles

    # Legacy arena maps: obstacles array
    for obs in map_data.get("obstacles", []):
        obstacles.add((obs["x"], obs["y"]))
    return obstacles


def _parse_spawn_zones(map_data: dict) -> dict[str, dict]:
    """Extract team spawn zones from map data, with fallback defaults."""
    zones = map_data.get("spawn_zones", {})
    if not zones:
        return _default_spawn_zones(
            map_data.get("width", 15), map_data.get("height", 15)
        )
    return zones


def _parse_ffa_points(map_data: dict) -> list[tuple[int, int]]:
    """Extract FFA spawn points from map data, falling back to legacy points."""
    points = map_data.get("ffa_points", [])
    if not points:
        points = map_data.get("spawn_points", [])
    return [(p["x"], p["y"]) for p in points]


def _default_spawn_zones(width: int, height: int) -> dict[str, dict]:
    """Generate default spawn zones for maps that lack explicit zones.

    Places 4 zones in corners. Zone size scales with map (~20% of dimension).
    """
    zone_size = max(3, width // 5)
    max_x = width - 1
    max_y = height - 1

    return {
        "a": {"x_min": 0, "y_min": 0,
              "x_max": zone_size - 1, "y_max": zone_size - 1},
        "b": {"x_min": max_x - zone_size + 1, "y_min": max_y - zone_size + 1,
              "x_max": max_x, "y_max": max_y},
        "c": {"x_min": max_x - zone_size + 1, "y_min": 0,
              "x_max": max_x, "y_max": zone_size - 1},
        "d": {"x_min": 0, "y_min": max_y - zone_size + 1,
              "x_max": zone_size - 1, "y_max": max_y},
    }


def _fallback_zone(team_key: str, width: int, height: int) -> dict:
    """Generate a fallback zone when a team's zone is missing."""
    zones = _default_spawn_zones(width, height)
    return zones.get(team_key, zones["a"])


def _get_walkable_in_zone(
    zone: dict,
    obstacles: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    width: int,
    height: int,
) -> list[tuple[int, int]]:
    """Get all walkable, unoccupied tiles within a zone (sorted by distance to center)."""
    walkable = []
    cx = (zone["x_min"] + zone["x_max"]) / 2.0
    cy = (zone["y_min"] + zone["y_max"]) / 2.0

    for x in range(max(0, zone["x_min"]), min(width, zone["x_max"] + 1)):
        for y in range(max(0, zone["y_min"]), min(height, zone["y_max"] + 1)):
            if (x, y) not in obstacles and (x, y) not in occupied:
                walkable.append((x, y))

    # Sort by distance to zone center so formations start near middle
    walkable.sort(key=lambda t: abs(t[0] - cx) + abs(t[1] - cy))
    return walkable


def _find_compact_formation(
    count: int,
    walkable: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Find a compact cluster of `count` tiles from walkable list.

    Tries every walkable tile as an anchor and grows a BFS formation
    from it. Returns the most compact (smallest total pairwise distance).
    """
    if count <= 0 or not walkable:
        return []
    if count == 1:
        return [walkable[0]]  # Already sorted by center proximity

    walkable_set = set(walkable)
    best_formation: list[tuple[int, int]] = []
    best_score = float("inf")

    # Try each walkable tile as anchor
    for anchor in walkable:
        formation = _grow_formation(anchor, count, walkable_set)
        if len(formation) >= count:
            formation = formation[:count]
            score = _formation_compactness(formation)
            if score < best_score:
                best_score = score
                best_formation = formation

    if best_formation:
        return best_formation

    # Fallback: return first N walkable tiles
    return walkable[:count]


def _grow_formation(
    anchor: tuple[int, int],
    count: int,
    walkable_set: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Grow a formation outward from anchor via BFS on walkable tiles."""
    formation = [anchor]
    visited = {anchor}
    queue = deque([anchor])

    while queue and len(formation) < count:
        cx, cy = queue.popleft()
        # Cardinal first, then diagonals — gives natural grid formations
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0),
                       (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            nx, ny = cx + dx, cy + dy
            if (nx, ny) in visited:
                continue
            visited.add((nx, ny))
            if (nx, ny) in walkable_set:
                formation.append((nx, ny))
                queue.append((nx, ny))
                if len(formation) >= count:
                    break

    return formation


def _formation_compactness(tiles: list[tuple[int, int]]) -> float:
    """Score a formation's compactness (lower = more compact)."""
    if len(tiles) <= 1:
        return 0
    total = 0
    for i in range(len(tiles)):
        for j in range(i + 1, len(tiles)):
            total += _chebyshev_distance(tiles[i], tiles[j])
    return total


def _chebyshev_distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Chebyshev (king's-move) distance between two tiles."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _validate_or_fallback(
    pos: tuple[int, int],
    obstacles: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    width: int,
    height: int,
) -> tuple[int, int] | None:
    """Return pos if valid, otherwise BFS to nearest valid tile."""
    if validate_spawn(pos[0], pos[1], obstacles, occupied, width, height):
        return pos
    return find_nearest_valid(pos[0], pos[1], obstacles, occupied, width, height)


def _find_distant_tile(
    placed: list[tuple[int, int]],
    obstacles: set[tuple[int, int]],
    occupied: set[tuple[int, int]],
    width: int,
    height: int,
) -> tuple[int, int]:
    """Find the walkable tile furthest from all already-placed positions."""
    best_pos = (1, 1)
    best_min_dist = -1

    # Sample on a coarse grid for performance on large maps
    step = max(1, min(width, height) // 10)
    for x in range(0, width, step):
        for y in range(0, height, step):
            if (x, y) in obstacles or (x, y) in occupied:
                continue
            if not (0 <= x < width and 0 <= y < height):
                continue
            min_dist = (
                min(_chebyshev_distance((x, y), p) for p in placed)
                if placed else width + height
            )
            if min_dist > best_min_dist:
                best_min_dist = min_dist
                best_pos = (x, y)

    return best_pos


def _generate_distributed_points(
    width: int,
    height: int,
    obstacles: set[tuple[int, int]],
    count: int,
) -> list[tuple[int, int]]:
    """Generate evenly distributed spawn points across the map."""
    points: list[tuple[int, int]] = []
    cols = max(2, int(count ** 0.5) + 1)
    rows = max(2, (count + cols - 1) // cols)

    x_step = max(1, (width - 2) // (cols + 1))
    y_step = max(1, (height - 2) // (rows + 1))

    for r in range(rows):
        for c in range(cols):
            x = 1 + c * x_step
            y = 1 + r * y_step
            if (x, y) not in obstacles and 0 <= x < width and 0 <= y < height:
                points.append((x, y))
            if len(points) >= count * 2:
                break

    return points if points else [(1, 1)]
