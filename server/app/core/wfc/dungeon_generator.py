"""
dungeon_generator.py — High-level API for procedural dungeon generation.

Orchestrates the full WFC pipeline:
    get_preset_modules → expand_modules → run_wfc → ensure_connectivity →
    decorate_rooms → export_to_game_map

Supports multi-floor generation with per-floor scaling of difficulty,
size, and loot quality. Deterministic via seed + floor_number.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.wfc.module_utils import expand_modules, MODULE_SIZE
from app.core.wfc.wfc_engine import run_wfc
from app.core.wfc.connectivity import ensure_connectivity
from app.core.wfc.room_decorator import decorate_rooms
from app.core.wfc.map_exporter import export_to_game_map
from app.core.wfc.presets import get_preset_modules, SIZE_PRESETS
from app.core.wfc.dungeon_styles import (
    apply_weight_overrides,
    get_decorator_overrides,
    select_style_for_floor,
    VALID_STYLES,
)

logger = logging.getLogger(__name__)


# ─── Floor scaling constants ──────────────────────────────────────────────

# Grid sizes scale with floor depth
_FLOOR_SIZE_PROGRESSION = [
    # (max_floor, grid_rows, grid_cols)
    (2,  3, 3),   # Floors 1-2: 3×3 (24×24 tiles) — Small
    (5,  4, 4),   # Floors 3-5: 4×4 (32×32 tiles) — Medium
    (8,  5, 5),   # Floors 6-8: 5×5 (40×40 tiles) — Large
    (99, 6, 6),   # Floors 9+:  6×6 (48×48 tiles) — Huge
]

# Enemy scaling per floor
_ENEMY_DENSITY_BASE = 0.45        # Base room enemy density (rooms are 36 tiles now)
_ENEMY_DENSITY_PER_FLOOR = 0.06   # +6% per floor
_ENEMY_DENSITY_CAP = 0.85

# Empty room chance scaling — more breather rooms on early floors
_EMPTY_ROOM_BASE = 0.20           # 20% empty on floor 1 (reduced for 8×8 rooms)
_EMPTY_ROOM_PER_FLOOR = -0.02     # −2% per floor
_EMPTY_ROOM_MIN = 0.08            # Never below 8%

# Max enemies per room scaling — prevents overwhelming packs on early floors
# (scaled for 8×8 modules: rooms now have 36+ floor tiles, ~2.25× old area)
_MAX_ENEMIES_PER_ROOM_PROGRESSION = [
    # (max_floor, max_enemies_per_room)
    (2,  4),   # Floors 1-2: max 4 enemies per room
    (5,  5),   # Floors 3-5: max 5
    (8,  6),   # Floors 6-8: max 6
    (99, 7),   # Floors 9+:  max 7 (uncapped feel)
]

# Loot scaling per floor
_LOOT_DENSITY_BASE = 0.3
_LOOT_DENSITY_PER_FLOOR = 0.02
_LOOT_DENSITY_CAP = 0.7

# ─── Enemy Roster System ──────────────────────────────────────────────
#
# Each floor tier has a weighted roster of enemies for three roles:
#   regular  — standard "E" tile enemies, drawn with weighted randomness
#   boss     — "B" tile bosses/elites
#   support  — healer/support enemies; when a room has 2+ enemies,
#              there's a chance one "E" slot becomes a support unit
#
# Format: (max_floor, {"regular": [(id, weight), ...], "boss": [...], "support": [...]})
# Weights are relative (don't need to sum to 1.0).
#
# Uses enemy IDs from configs/enemies_config.json.

_FLOOR_ENEMY_ROSTER: list[tuple[int, dict[str, list[tuple[str, float]]]]] = [
    (2, {  # Floors 1-2 (Early) — swarm + fodder intro, lots of variety
        "regular": [
            ("skeleton", 0.20), ("imp", 0.15), ("goblin_spearman", 0.15),
            ("ghoul", 0.12), ("insectoid", 0.10), ("evil_snail", 0.08),
            ("caster", 0.10), ("acolyte", 0.10),
        ],
        "boss":    [("demon", 1.0)],
        "support": [("dark_priest", 0.5), ("acolyte", 0.5)],
    }),
    (4, {  # Floors 3-4 (Mid-early) — demons step up, shades & ranged threats appear
        "regular": [
            ("demon", 0.15), ("shade", 0.14), ("skeleton", 0.12),
            ("undead_caster", 0.12), ("imp_lord", 0.12), ("medusa", 0.10),
            ("ghoul", 0.10), ("goblin_spearman", 0.08), ("insectoid", 0.07),
        ],
        "boss":    [("undead_knight", 0.5), ("necromancer", 0.5)],
        "support": [("dark_priest", 0.5), ("acolyte", 0.3), ("medusa", 0.2)],
    }),
    (6, {  # Floors 5-6 (Mid) — casters, elites, aberrations
        "regular": [
            ("wraith", 0.15), ("demon_knight", 0.12), ("medusa", 0.12),
            ("shade", 0.12), ("horror", 0.10), ("undead_caster", 0.10),
            ("werewolf", 0.10), ("imp_lord", 0.10), ("insectoid", 0.09),
        ],
        "boss":    [("undead_knight", 0.25), ("reaper", 0.25), ("necromancer", 0.25), ("demon_boss", 0.25)],
        "support": [("dark_priest", 0.35), ("acolyte", 0.30), ("medusa", 0.35)],
    }),
    (8, {  # Floors 7-8 (Late) — elite melee + tanky horrors
        "regular": [
            ("werewolf", 0.16), ("demon_knight", 0.14), ("construct", 0.14),
            ("horror", 0.13), ("wraith", 0.12), ("shade", 0.11),
            ("medusa", 0.10), ("undead_caster", 0.10),
        ],
        "boss":    [("reaper", 0.30), ("demon_boss", 0.30), ("construct_boss", 0.25), ("necromancer", 0.15)],
        "support": [("dark_priest", 0.45), ("acolyte", 0.25), ("medusa", 0.30)],
    }),
    (99, {  # Floors 9+ (Deep) — everything dangerous, maximum variety
        "regular": [
            ("construct", 0.15), ("werewolf", 0.13), ("horror", 0.13),
            ("demon_knight", 0.13), ("wraith", 0.12), ("demon", 0.10),
            ("medusa", 0.10), ("shade", 0.08), ("undead_caster", 0.06),
        ],
        "boss":    [("reaper", 0.25), ("construct_boss", 0.25), ("demon_boss", 0.25), ("necromancer", 0.15), ("undead_knight", 0.10)],
        "support": [("dark_priest", 0.35), ("acolyte", 0.30), ("medusa", 0.35)],
    }),
]

# Chance that a room with 2+ regular enemies swaps one for a support unit
_SUPPORT_SWAP_CHANCE = 0.30

# Legacy compatibility: derive simple {"E": str, "B": str} from roster
# Uses the highest-weighted entry for each role.
_FLOOR_ENEMY_TYPES: list[tuple[int, dict[str, str]]] = [
    (
        max_f,
        {
            "E": max(roster["regular"], key=lambda t: t[1])[0],
            "B": max(roster["boss"], key=lambda t: t[1])[0],
        },
    )
    for max_f, roster in _FLOOR_ENEMY_ROSTER
]

# Valid enemy type IDs that must exist in enemies_config.json
# Used for startup validation — includes every ID referenced in any roster
_KNOWN_ENEMY_TYPES = {
    "skeleton", "demon", "undead_knight", "imp", "dark_priest",
    "wraith", "medusa", "acolyte", "werewolf", "reaper", "construct",
    "imp_lord", "demon_boss", "demon_knight", "construct_boss",
    "ghoul", "necromancer", "undead_caster", "horror", "insectoid",
    "caster", "evil_snail", "goblin_spearman", "shade",
}


def _pick_weighted(pool: list[tuple[str, float]], rng_func) -> str:
    """Pick an entry from a weighted pool using a [0,1) RNG function.

    Args:
        pool: List of (enemy_id, weight) tuples.
        rng_func: Callable returning a float in [0, 1) — e.g. ``random.random``.

    Returns:
        The selected enemy_id string.
    """
    total = sum(w for _, w in pool)
    roll = rng_func() * total
    cumulative = 0.0
    for enemy_id, weight in pool:
        cumulative += weight
        if roll < cumulative:
            return enemy_id
    # Fallback (float rounding): return last entry
    return pool[-1][0]


def resolve_enemy_for_tile(
    tile: str,
    roster: dict[str, list[tuple[str, float]]],
    rng_func,
    is_support_swap: bool = False,
) -> str:
    """Resolve an enemy ID for a given tile character using the roster.

    Args:
        tile: Tile character — 'E' (regular) or 'B' (boss).
        roster: The floor's enemy roster dict.
        rng_func: Callable returning float in [0, 1).
        is_support_swap: If True and tile is 'E', draw from support pool instead.

    Returns:
        An enemy_id string from enemies_config.json.
    """
    if tile == "B":
        return _pick_weighted(roster.get("boss", [("undead_knight", 1.0)]), rng_func)

    if is_support_swap and roster.get("support"):
        return _pick_weighted(roster["support"], rng_func)

    return _pick_weighted(roster.get("regular", [("demon", 1.0)]), rng_func)


def validate_enemy_types() -> list[str]:
    """Validate that all enemy types used in floor rosters exist in enemies_config.json.

    Returns a list of missing enemy type IDs (empty if all valid).
    Should be called at startup or in tests to catch config mismatches early.
    """
    try:
        from app.models.player import get_enemy_definition
    except ImportError:
        logger.warning("Cannot import get_enemy_definition — skipping enemy validation")
        return []

    missing = []
    seen: set[str] = set()
    for _, roster in _FLOOR_ENEMY_ROSTER:
        for role_pool in roster.values():
            for enemy_id, _weight in role_pool:
                if enemy_id not in seen:
                    seen.add(enemy_id)
                    if get_enemy_definition(enemy_id) is None:
                        missing.append(enemy_id)
                        logger.warning(
                            "Enemy type '%s' used in floor roster but not in enemies_config.json",
                            enemy_id,
                        )
    return missing


def get_floor_roster(floor_number: int) -> dict[str, list[tuple[str, float]]]:
    """Return the enemy roster for a given floor number.

    Returns:
        Dict with 'regular', 'boss', and 'support' weighted pools.
    """
    for max_f, roster in _FLOOR_ENEMY_ROSTER:
        if floor_number <= max_f:
            return roster
    return _FLOOR_ENEMY_ROSTER[-1][1]


@dataclass
class FloorConfig:
    """Configuration for generating a single dungeon floor.

    Use ``from_floor_number()`` for automatic scaling, or set fields
    manually for full control.
    """
    seed: int = 42
    floor_number: int = 1
    grid_rows: int = 4
    grid_cols: int = 4
    max_attempts: int = 20
    enemy_density: float = 0.30
    loot_density: float = 0.3
    empty_room_chance: float = 0.35
    max_enemies_per_room: int = 3
    enemy_types: dict[str, str] = field(default_factory=lambda: {"E": "demon", "B": "undead_knight"})
    enemy_roster: dict[str, list[tuple[str, float]]] | None = field(default=None)
    dungeon_style: str | None = None  # None = auto-select based on floor + seed
    batch_size: int = 3  # Best-of-N: generate N candidates, pick the best
    map_name: str = "WFC Dungeon"
    pvpve_mode: bool = False       # Enable PVPVE layout (4 corner spawns, center boss)
    pvpve_team_count: int = 2      # Number of player teams (2–4)

    @classmethod
    def for_pvpve(cls, seed: int, team_count: int = 2,
                  grid_size: int = 8, pve_density: float = 0.5,
                  loot_density: float = 0.5, boss_enabled: bool = True) -> FloorConfig:
        """Create a FloorConfig optimized for PVPVE matches."""
        return cls(
            seed=seed,
            floor_number=1,              # PVPVE is single-floor
            grid_rows=grid_size,
            grid_cols=grid_size,
            enemy_density=pve_density,
            loot_density=loot_density,
            empty_room_chance=0.15,       # Fewer empties — more content to fight over
            max_enemies_per_room=4,
            enemy_roster=get_floor_roster(3),  # Mid-tier roster as baseline
            dungeon_style="balanced",
            batch_size=5,                 # More candidates for better layout
            map_name="PVPVE Dungeon",
            pvpve_mode=True,
            pvpve_team_count=max(2, min(4, team_count)),
        )

    @classmethod
    def from_floor_number(cls, seed: int, floor_number: int = 1) -> FloorConfig:
        """Create a FloorConfig with auto-scaled parameters based on floor depth."""
        # Grid size
        grid_rows, grid_cols = 4, 4  # default medium
        for max_floor, rows, cols in _FLOOR_SIZE_PROGRESSION:
            if floor_number <= max_floor:
                grid_rows, grid_cols = rows, cols
                break

        # Enemy density
        enemy_density = min(
            _ENEMY_DENSITY_BASE + (floor_number - 1) * _ENEMY_DENSITY_PER_FLOOR,
            _ENEMY_DENSITY_CAP,
        )

        # Loot density
        loot_density = min(
            _LOOT_DENSITY_BASE + (floor_number - 1) * _LOOT_DENSITY_PER_FLOOR,
            _LOOT_DENSITY_CAP,
        )

        # Empty room chance — more breather rooms on early floors
        empty_room_chance = max(
            _EMPTY_ROOM_BASE + (floor_number - 1) * _EMPTY_ROOM_PER_FLOOR,
            _EMPTY_ROOM_MIN,
        )

        # Max enemies per room — scales with floor depth
        max_enemies_per_room = 3  # default
        for max_f, cap in _MAX_ENEMIES_PER_ROOM_PROGRESSION:
            if floor_number <= max_f:
                max_enemies_per_room = cap
                break

        # Enemy types (legacy) + roster
        enemy_types = {"E": "demon", "B": "undead_knight"}
        enemy_roster = None
        for max_f, types in _FLOOR_ENEMY_TYPES:
            if floor_number <= max_f:
                enemy_types = types
                break
        enemy_roster = get_floor_roster(floor_number)

        return cls(
            seed=seed,
            floor_number=floor_number,
            grid_rows=grid_rows,
            grid_cols=grid_cols,
            enemy_density=enemy_density,
            loot_density=loot_density,
            empty_room_chance=empty_room_chance,
            max_enemies_per_room=max_enemies_per_room,
            enemy_types=enemy_types,
            enemy_roster=enemy_roster,
            dungeon_style=None,  # Auto-select in generate_dungeon_floor()
            batch_size=3,        # Best-of-3 by default
            map_name=f"Dungeon Floor {floor_number}",
        )


@dataclass
class GenerationResult:
    """Result of a dungeon floor generation attempt."""
    success: bool
    game_map: dict | None = None
    stats: dict = field(default_factory=dict)
    wfc_grid: list[list[dict]] | None = None
    tile_map: list[list[str]] | None = None
    variants: list[dict] | None = None
    error: str | None = None
    generation_time_ms: float = 0.0

    @property
    def map_data(self) -> dict:
        """Convenience accessor - raises if generation failed."""
        if not self.success or self.game_map is None:
            raise RuntimeError(f"Generation failed: {self.error}")
        return self.game_map


def score_dungeon_candidate(
    tile_map: list[list[str]],
    connectivity_result: dict | None = None,
) -> float:
    """Score a WFC candidate by quality metrics (higher = better).

    Mirrors the tool's batch-ranking logic:
      - Floor ratio (% open tiles) — primary quality signal
      - Has spawn points in the raw tile map? (+20 bonus)
      - Naturally connected (0 corridors carved)? (+10 bonus)

    Args:
        tile_map: The raw WFC tile map (before decoration).
        connectivity_result: Connectivity dict from ``run_wfc()``.

    Returns:
        A numeric quality score (higher is better).
    """
    total_tiles = 0
    open_tiles = 0
    has_spawns = False

    for row in tile_map:
        for tile in row:
            total_tiles += 1
            if tile != "W":
                open_tiles += 1
            if tile == "S":
                has_spawns = True

    # Floor ratio as percentage (primary metric)
    floor_ratio = (open_tiles / max(1, total_tiles)) * 100.0
    score = floor_ratio

    # Bonus: has at least one spawn point in the raw layout
    if has_spawns:
        score += 20.0

    # Bonus: naturally connected (no corridors carved = cleaner layout)
    if connectivity_result:
        corridors_carved = connectivity_result.get("corridorsCarved", 0)
        if corridors_carved == 0:
            score += 10.0

    return score


def _run_single_candidate(
    modules: list[dict],
    config: FloorConfig,
    candidate_seed: int,
    active_style: str,
) -> dict | None:
    """Run a single WFC + connectivity pass and return raw candidate data.

    Returns None if WFC fails, otherwise a dict with grid/tileMap/variants/
    connectivity/score for ranking.
    """
    wfc_result = run_wfc(
        modules=modules,
        grid_rows=config.grid_rows,
        grid_cols=config.grid_cols,
        seed=candidate_seed,
        max_retries=config.max_attempts,
        ensure_connected=True,
    )

    if not wfc_result["success"]:
        return None

    tile_map = wfc_result["tileMap"]
    connectivity = wfc_result.get("connectivity", {}) or {}

    score = score_dungeon_candidate(tile_map, connectivity)

    return {
        "grid": wfc_result["grid"],
        "tileMap": tile_map,
        "variants": wfc_result["variants"],
        "connectivity": connectivity,
        "retries": wfc_result.get("retries", 0),
        "seed": candidate_seed,
        "score": score,
    }


def generate_dungeon_floor(
    config: FloorConfig | None = None,
    seed: int | None = None,
    floor_number: int = 1,
) -> GenerationResult:
    """Generate a single dungeon floor.

    This is the main entry point for procedural dungeon generation.
    Can be called with a ``FloorConfig`` for full control, or with
    just ``seed`` and ``floor_number`` for auto-scaled defaults.

    When ``batch_size > 1``, generates multiple candidates with different
    seeds and picks the highest-scoring one (Best-of-N selection).
    Scoring favours higher floor ratio, natural connectivity, and spawn
    point presence — matching the tool's batch-generation logic.

    Args:
        config: Full generation config. If None, auto-created from seed/floor_number.
        seed: Random seed. Used only if config is None.
        floor_number: Floor depth. Used only if config is None.

    Returns:
        GenerationResult with the game map dict and metadata.
    """
    t0 = time.perf_counter()

    # Build config if not provided
    if config is None:
        if seed is None:
            seed = int(time.time() * 1000) & 0xFFFFFFFF
        config = FloorConfig.from_floor_number(seed, floor_number)

    # Use floor_number to offset the seed deterministically  
    floor_seed = (config.seed + config.floor_number * 7919) & 0xFFFFFFFF

    # ── Resolve dungeon style ──
    if config.dungeon_style and config.dungeon_style in VALID_STYLES:
        active_style = config.dungeon_style
    elif config.dungeon_style is None:
        active_style = select_style_for_floor(config.floor_number, floor_seed)
    else:
        logger.warning(
            "Unknown dungeon_style '%s', falling back to 'balanced'",
            config.dungeon_style,
        )
        active_style = "balanced"

    batch_size = max(1, config.batch_size)

    logger.info(
        "WFC Generate: floor=%d seed=%d grid=%dx%d style=%s batch=%d",
        config.floor_number, floor_seed,
        config.grid_rows, config.grid_cols, active_style, batch_size,
    )

    try:
        # 1. Get preset modules and apply style weight overrides
        modules = get_preset_modules()
        modules = apply_weight_overrides(modules, active_style)

        # 2. Run WFC — batch generation (Best-of-N)
        #    Generate N candidates with spaced seeds, pick the best.
        #    Use a different prime (104729) than the floor offset (7919)
        #    so batch candidates don't collide with neighboring floors.
        candidates: list[dict] = []
        for i in range(batch_size):
            candidate_seed = (floor_seed + i * 104729) & 0xFFFFFFFF
            candidate = _run_single_candidate(
                modules, config, candidate_seed, active_style,
            )
            if candidate is not None:
                candidates.append(candidate)

        if not candidates:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(
                "WFC failed: all %d batch candidates failed (%.1fms)",
                batch_size, elapsed,
            )
            return GenerationResult(
                success=False,
                error=f"WFC failed: all {batch_size} batch candidates failed",
                generation_time_ms=elapsed,
            )

        # Pick the highest-scoring candidate
        best = max(candidates, key=lambda c: c["score"])

        if batch_size > 1:
            scores = [c["score"] for c in candidates]
            logger.info(
                "Batch selection: %d/%d succeeded, scores=[%s], best=%.1f (seed=%d)",
                len(candidates), batch_size,
                ", ".join(f"{s:.1f}" for s in scores),
                best["score"], best["seed"],
            )

        grid = best["grid"]
        tile_map = best["tileMap"]
        variants = best["variants"]
        winning_seed = best["seed"]

        # Connectivity info from the winning candidate
        connectivity_result = best["connectivity"]
        corridors_carved = connectivity_result.get("corridorsCarved", 0)
        if corridors_carved > 0:
            logger.info("Connectivity: carved %d corridors", corridors_carved)

        # 3. Decorate rooms (assign enemies, loot, boss, spawn to flexible rooms)
        #    Start with floor-scaled defaults, then layer style overrides on top.
        decorator_settings = {
            "enemyDensity": config.enemy_density,
            "lootDensity": config.loot_density,
            "emptyRoomChance": config.empty_room_chance,
            "maxEnemiesPerRoom": config.max_enemies_per_room,
            "guaranteeBoss": True,
            "guaranteeSpawn": True,
        }
        # Merge style decorator overrides first (base layer)
        style_decorator = get_decorator_overrides(active_style)
        if style_decorator:
            decorator_settings.update(style_decorator)
        # PVPVE mode: inject decorator settings AFTER style overrides so they
        # can't be clobbered (corner spawns, center boss, no stairs are mandatory)
        if config.pvpve_mode:
            decorator_settings.update({
                "pvpve_mode": True,
                "pvpve_team_count": config.pvpve_team_count,
                "guaranteeStairs": False,  # No stairs in PVPVE (single floor)
                "guaranteeBoss": True,     # Boss is always required in PVPVE
                "guaranteeSpawn": True,    # Corner spawns are always required
            })
        decoration_result = decorate_rooms(
            grid=grid,
            variants=variants,
            tile_map=tile_map,
            seed=winning_seed,
            settings=decorator_settings,
        )

        # Use the DECORATED tile map for export (has E/B/S/X placed)
        decorated_tile_map = decoration_result.get("tileMap", tile_map)

        # 4. Export to game map dict
        game_map = export_to_game_map(
            tile_map=decorated_tile_map,
            grid=grid,
            variants=variants,
            map_name=config.map_name,
            floor_number=config.floor_number,
            enemy_types=config.enemy_types,
            enemy_roster=config.enemy_roster,
            seed=winning_seed,
            pvpve_mode=config.pvpve_mode,
            pvpve_team_count=config.pvpve_team_count,
            decoration_result=decoration_result,
        )

        elapsed = (time.perf_counter() - t0) * 1000

        # Collect combined stats
        batch_stats = {}
        if batch_size > 1:
            batch_stats = {
                "batch_size": batch_size,
                "candidates_succeeded": len(candidates),
                "candidate_scores": [round(c["score"], 1) for c in candidates],
                "winning_score": round(best["score"], 1),
                "winning_seed": winning_seed,
            }

        stats = {
            "wfc_attempts": best.get("retries", 0) + 1,
            "grid_size": f"{config.grid_rows}x{config.grid_cols}",
            "tile_size": f"{game_map['width']}x{game_map['height']}",
            "rooms": len(game_map.get("rooms", [])),
            "doors": len(game_map.get("doors", [])),
            "chests": len(game_map.get("chests", [])),
            "spawn_points": len(game_map.get("spawn_points", [])),
            "corridors_carved": corridors_carved,
            "decoration": decoration_result.get("stats", {}),
            "floor_number": config.floor_number,
            "seed": winning_seed,
            "dungeon_style": active_style,
            "generation_time_ms": round(elapsed, 1),
            **batch_stats,
        }

        logger.info(
            "WFC Success: floor=%d %s %d rooms %.1fms",
            config.floor_number, stats["tile_size"],
            stats["rooms"], elapsed,
        )

        return GenerationResult(
            success=True,
            game_map=game_map,
            stats=stats,
            wfc_grid=grid,
            tile_map=tile_map,
            variants=variants,
            generation_time_ms=elapsed,
        )

    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        logger.exception("WFC generation error: %s", e)
        return GenerationResult(
            success=False,
            error=str(e),
            generation_time_ms=elapsed,
        )
