"""
Field of View — Recursive shadowcasting algorithm (pure Python).

Computes visible tiles from a position given a vision radius and obstacle set.
Also provides line-of-sight (LOS) checks for ranged attacks.
"""

from __future__ import annotations


# Eight octants used by recursive shadowcasting.
# Each tuple is (xx, xy, yx, yy) that maps (row, col) to (dx, dy).
_OCTANTS = [
    (1, 0, 0, 1),
    (0, 1, 1, 0),
    (0, -1, 1, 0),
    (-1, 0, 0, 1),
    (-1, 0, 0, -1),
    (0, -1, -1, 0),
    (0, 1, -1, 0),
    (1, 0, 0, -1),
]


def compute_fov(
    origin_x: int,
    origin_y: int,
    radius: int,
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    """Return the set of (x, y) tiles visible from (origin_x, origin_y).

    Uses recursive shadowcasting for O(n) performance where n is the
    number of tiles in the vision radius.

    Args:
        origin_x: Viewer X position.
        origin_y: Viewer Y position.
        radius: Vision range in tiles.
        grid_width: Map width.
        grid_height: Map height.
        obstacles: Set of (x, y) positions that block vision.

    Returns:
        Set of visible (x, y) coordinates (always includes origin).
    """
    visible: set[tuple[int, int]] = {(origin_x, origin_y)}

    for octant in _OCTANTS:
        _cast_light(
            visible, obstacles,
            origin_x, origin_y,
            radius, grid_width, grid_height,
            1,         # starting row
            1.0,       # start slope
            0.0,       # end slope
            octant[0], octant[1], octant[2], octant[3],
        )

    return visible


def _cast_light(
    visible: set[tuple[int, int]],
    obstacles: set[tuple[int, int]],
    ox: int, oy: int,
    radius: int,
    grid_width: int, grid_height: int,
    row: int,
    start_slope: float,
    end_slope: float,
    xx: int, xy: int, yx: int, yy: int,
) -> None:
    """Recursive shadowcasting for one octant."""
    if start_slope < end_slope:
        return

    radius_sq = radius * radius
    next_start_slope = start_slope

    for j in range(row, radius + 1):
        blocked = False
        dx, dy = -j - 1, -j

        while dx <= 0:
            dx += 1
            # Map (dx, dy) through octant transform
            map_x = ox + dx * xx + dy * xy
            map_y = oy + dx * yx + dy * yy

            # Slopes for this cell (dy is negative, giving correct slope signs)
            l_slope = (dx - 0.5) / (dy + 0.5)
            r_slope = (dx + 0.5) / (dy - 0.5)

            if start_slope < r_slope:
                continue
            if end_slope > l_slope:
                break

            # Within radius?
            if dx * dx + dy * dy <= radius_sq:
                if 0 <= map_x < grid_width and 0 <= map_y < grid_height:
                    visible.add((map_x, map_y))

            # Check if this cell blocks light
            if blocked:
                if (map_x, map_y) in obstacles:
                    next_start_slope = r_slope
                else:
                    blocked = False
                    start_slope = next_start_slope
            elif (map_x, map_y) in obstacles:
                blocked = True
                # Recurse with narrowed beam before the wall
                _cast_light(
                    visible, obstacles,
                    ox, oy,
                    radius, grid_width, grid_height,
                    j + 1,
                    start_slope,
                    l_slope,
                    xx, xy, yx, yy,
                )
                next_start_slope = r_slope

        if blocked:
            return


def has_line_of_sight(
    x0: int, y0: int,
    x1: int, y1: int,
    obstacles: set[tuple[int, int]],
) -> bool:
    """Check if there is a clear line of sight between two points.

    Uses Bresenham's line algorithm. Returns True if no obstacle blocks
    the path (endpoints are not considered obstacles).
    """
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    cx, cy = x0, y0

    while True:
        # Skip start and end points for obstacle check
        if (cx, cy) != (x0, y0) and (cx, cy) != (x1, y1):
            if (cx, cy) in obstacles:
                return False

        if cx == x1 and cy == y1:
            break

        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            cx += sx
        if e2 < dx:
            err += dx
            cy += sy

    return True


def tiles_in_range(
    origin_x: int,
    origin_y: int,
    attack_range: int,
    grid_width: int,
    grid_height: int,
    obstacles: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    """Return tiles within attack range that also have line of sight.

    Used for highlighting valid ranged attack targets on the client.
    """
    targets: set[tuple[int, int]] = set()
    range_sq = attack_range * attack_range

    for dx in range(-attack_range, attack_range + 1):
        for dy in range(-attack_range, attack_range + 1):
            if dx * dx + dy * dy > range_sq:
                continue
            tx, ty = origin_x + dx, origin_y + dy
            if tx < 0 or tx >= grid_width or ty < 0 or ty >= grid_height:
                continue
            if (tx, ty) == (origin_x, origin_y):
                continue
            if has_line_of_sight(origin_x, origin_y, tx, ty, obstacles):
                targets.add((tx, ty))

    return targets
