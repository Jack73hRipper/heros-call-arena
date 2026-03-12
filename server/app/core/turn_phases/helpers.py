"""
Turn Phase Helpers — Pure utility functions for adjacency checks.

No external dependencies. Used by interaction_phase and other sub-modules.
"""

from __future__ import annotations

from app.models.player import Position


def _is_cardinal_adjacent(pos: Position, tx: int, ty: int) -> bool:
    """Check if (tx, ty) is cardinally adjacent (up/down/left/right) to pos."""
    dx = abs(pos.x - tx)
    dy = abs(pos.y - ty)
    return (dx + dy) == 1


def _is_chebyshev_adjacent(pos: Position, tx: int, ty: int) -> bool:
    """Check if (tx, ty) is adjacent in any of 8 directions (Chebyshev distance 1)."""
    dx = abs(pos.x - tx)
    dy = abs(pos.y - ty)
    return max(dx, dy) == 1
