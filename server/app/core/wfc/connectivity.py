"""
connectivity.py — Dungeon connectivity validation & corridor stitching.

Port of tools/dungeon-wfc/src/engine/connectivity.js to Python.
After WFC generation, ensures all walkable regions are connected.
Uses flood-fill to detect isolated regions, then carves minimal
corridors between them using A* pathfinding through walls.
"""

from __future__ import annotations

import heapq
from typing import Any

from app.core.wfc.module_utils import OPEN_TILES


def is_open(tile: str) -> bool:
    """Check if a tile is walkable (open)."""
    return tile in OPEN_TILES


def _flood_fill(
    tile_map: list[list[str]],
    start_r: int,
    start_c: int,
    visited: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Flood-fill from a starting position, returning all connected open tile coords."""
    height = len(tile_map)
    width = len(tile_map[0]) if height > 0 else 0
    region: list[tuple[int, int]] = []
    queue = [(start_r, start_c)]
    visited.add((start_r, start_c))

    while queue:
        r, c = queue.pop(0)
        region.append((r, c))

        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= nr < height and 0 <= nc < width:
                if (nr, nc) not in visited and is_open(tile_map[nr][nc]):
                    visited.add((nr, nc))
                    queue.append((nr, nc))

    return region


def find_regions(tile_map: list[list[str]]) -> list[list[tuple[int, int]]]:
    """Find all disconnected walkable regions in the tile map."""
    height = len(tile_map)
    width = len(tile_map[0]) if height > 0 else 0
    visited: set[tuple[int, int]] = set()
    regions: list[list[tuple[int, int]]] = []

    for r in range(height):
        for c in range(width):
            if is_open(tile_map[r][c]) and (r, c) not in visited:
                region = _flood_fill(tile_map, r, c, visited)
                if region:
                    regions.append(region)

    return regions


def _find_tunnel_path(
    tile_map: list[list[str]],
    from_pos: tuple[int, int],
    to_pos: tuple[int, int],
) -> list[tuple[int, int]] | None:
    """A* pathfinding through walls to find the shortest tunnel between two points.

    Cost: 1 for open tiles, 3 for wall tiles (prefer going through open space).
    """
    height = len(tile_map)
    width = len(tile_map[0])

    def heuristic(r: int, c: int) -> int:
        return abs(r - to_pos[0]) + abs(c - to_pos[1])

    # (f_score, counter, r, c, parent_key)
    counter = 0
    start_key = from_pos
    open_set: list[tuple[int, int, int, int, tuple[int, int] | None]] = [
        (heuristic(from_pos[0], from_pos[1]), counter, from_pos[0], from_pos[1], None)
    ]
    g_scores: dict[tuple[int, int], int] = {start_key: 0}
    parents: dict[tuple[int, int], tuple[int, int] | None] = {start_key: None}
    closed_set: set[tuple[int, int]] = set()

    while open_set:
        f, _, r, c, parent = heapq.heappop(open_set)
        pos = (r, c)

        if pos in closed_set:
            continue
        closed_set.add(pos)

        if pos == to_pos:
            # Reconstruct path
            path = []
            current: tuple[int, int] | None = pos
            while current is not None:
                path.append(current)
                current = parents.get(current)
            path.reverse()
            return path

        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= nr < height and 0 <= nc < width:
                n_pos = (nr, nc)
                if n_pos in closed_set:
                    continue

                move_cost = 1 if is_open(tile_map[nr][nc]) else 3
                tentative_g = g_scores[pos] + move_cost

                if tentative_g < g_scores.get(n_pos, float("inf")):
                    g_scores[n_pos] = tentative_g
                    parents[n_pos] = pos
                    counter += 1
                    heapq.heappush(
                        open_set,
                        (tentative_g + heuristic(nr, nc), counter, nr, nc, pos),
                    )

    return None


def _find_closest_pair(
    region_a: list[tuple[int, int]],
    region_b: list[tuple[int, int]],
) -> tuple[tuple[int, int], tuple[int, int], int] | None:
    """Find the closest pair of tiles between two regions.

    Returns (from_pos, to_pos, distance) or None.
    Samples for performance on large regions.
    """
    def sample(arr: list, n: int) -> list:
        if len(arr) <= n:
            return arr
        step = max(1, len(arr) // n)
        return arr[::step][:n]

    sample_a = sample(region_a, 100)
    sample_b = sample(region_b, 100)

    best_dist = float("inf")
    best_pair = None

    for a in sample_a:
        for b in sample_b:
            dist = abs(a[0] - b[0]) + abs(a[1] - b[1])
            if dist < best_dist:
                best_dist = dist
                best_pair = (a, b, dist)

    return best_pair


def _carve_corridor(tile_map: list[list[str]], path: list[tuple[int, int]]) -> None:
    """Carve a 2-wide corridor along a path by setting wall tiles to corridor.

    Modifies tile_map in place.
    """
    height = len(tile_map)
    width = len(tile_map[0])

    for r, c in path:
        # Only carve walls (don't overwrite existing content)
        if tile_map[r][c] == "W":
            tile_map[r][c] = "C"
        # Try to make it 2-wide
        for nr, nc in ((r, c + 1), (r + 1, c)):
            if 0 <= nr < height and 0 <= nc < width:
                if tile_map[nr][nc] == "W":
                    tile_map[nr][nc] = "C"
                    break  # Only widen by 1


def ensure_connectivity(tile_map: list[list[str]]) -> dict:
    """Ensure the dungeon is fully connected.

    Detects disconnected regions and carves corridors between them.
    Modifies tile_map in place.

    Returns dict with: connected, regionsFound, corridorsCarved.
    """
    regions = find_regions(tile_map)

    if len(regions) <= 1:
        return {
            "connected": True,
            "regionsFound": len(regions),
            "corridorsCarved": 0,
        }

    # Sort regions by size (largest first) — main region is the biggest
    regions.sort(key=lambda r: len(r), reverse=True)

    corridors_carved = 0
    main_region = list(regions[0])

    for i in range(1, len(regions)):
        small_region = regions[i]
        # Skip tiny regions (1-2 tiles, likely artifacts)
        if len(small_region) < 2:
            continue

        pair = _find_closest_pair(main_region, small_region)
        if pair is None:
            continue

        from_pos, to_pos, _ = pair
        path = _find_tunnel_path(tile_map, from_pos, to_pos)
        if path:
            _carve_corridor(tile_map, path)
            corridors_carved += 1
            main_region.extend(small_region)

    return {
        "connected": True,
        "regionsFound": len(regions),
        "corridorsCarved": corridors_carved,
    }


def validate_connectivity(tile_map: list[list[str]]) -> dict:
    """Validate connectivity without modifying the tile map.

    Returns dict with: isConnected, regionCount, regionSizes.
    """
    regions = find_regions(tile_map)
    return {
        "isConnected": len(regions) <= 1,
        "regionCount": len(regions),
        "regionSizes": sorted([len(r) for r in regions], reverse=True),
    }
