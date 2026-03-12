# WFC Dungeon Tile Size Update

**Date:** March 5, 2026  
**Status:** Complete  
**Tests:** 2811 passed, 0 failures

## Summary

Increased WFC dungeon module size from 6×6 to 8×8 tiles to resolve cramped hallways and rooms. With 5 party members and 5+ enemies, the old 6×6 modules created unplayable congestion — 1-2 tile wide corridors forced conga-line movement, and 4×4 interior rooms (16 floor tiles) hit 50-60% occupancy with 8-10 units.

## Problem

| Issue | Old (6×6) | Impact |
|-------|-----------|--------|
| Corridor width | 2 tiles | Party moves single-file, no flanking |
| Room floor area | 4×4 = 16 tiles | 10 units = 62% density, no room to maneuver |
| Narrow corridors | 1 tile wide | Completely impassable for group movement |
| Boss rooms | ~5×5 = 25 tiles | No tactical positioning for boss fights |

## Solution: MODULE_SIZE 6 → 8

| Metric | Old (6×6) | New (8×8) | Improvement |
|--------|-----------|-----------|-------------|
| Standard corridor width | 2 tiles | **4 tiles** | 2× wider, party can form 2×2 |
| Narrow corridor width | 1 tile | **2 tiles** | Passable side-by-side |
| Room interior floor area | 4×4 = 16 tiles | **6×6 = 36 tiles** | +125% more space |
| Boss room floor area | ~25 tiles | **36 tiles** | Proper boss fight arena |
| 10 units in room density | 62% | **28%** | Room to breathe and position |
| Spawn slots per room | 6 | **8** | Better unit distribution |

## Socket Types (8-char edge patterns)

| Socket | Pattern | Opening Width | Use |
|--------|---------|---------------|-----|
| Wall | `WWWWWWWW` | 0 (solid) | No connection |
| Standard | `WWOOOOWW` | 4-wide | Corridors & room entrances |
| Narrow | `WWWOOWWW` | 2-wide | Tight passages & side doors |
| Interior | `WOOOOOOW` | 6-wide | Grand multi-module room joins |

## Map Size Changes

| Grid | Old Tiles | New Tiles | Feel |
|------|-----------|-----------|------|
| 2×2 (Tiny) | 12×12 | **16×16** | Quick encounter |
| 3×3 (Small) | 18×18 | **24×24** | Comfortable small dungeon |
| 4×4 (Medium) | 24×24 | **32×32** | Good medium dungeon |
| 5×5 (Large) | 30×30 | **40×40** | Spacious large dungeon |
| 6×6 (Huge) | 36×36 | **48×48** | Epic deep floors |

## Enemy Scaling Adjustments

Max enemies per room bumped by +2 across all floor tiers to properly fill the larger 8×8 rooms:

| Floor Tier | Old (6×6) Max | New (8×8) Max |
|------------|-------------|---------------|
| Floors 1-2 | 2 | **4** |
| Floors 3-5 | 3 | **5** |
| Floors 6-8 | 4 | **6** |
| Floors 9+ | 5 | **7** |

### Density Tuning (post-tile-size rebalance)

With 125% more floor area per room, density constants were retuned to maintain encounter feel:

| Parameter | Old Value | New Value | Rationale |
|-----------|-----------|-----------|----------|
| `_ENEMY_DENSITY_BASE` | 0.30 | **0.45** | More rooms become enemy rooms |
| `_EMPTY_ROOM_BASE` | 0.35 | **0.20** | Fewer empty 36-tile voids |
| `_EMPTY_ROOM_PER_FLOOR` | -0.03 | **-0.02** | Slower reduction (starts lower) |
| `_EMPTY_ROOM_MIN` | 0.10 | **0.08** | Slightly lower floor |
| Min enemies per enemy room | 1 | **2** | Single enemy in 36 tiles felt empty |
| Empty room scatter chance | 15% | **25%** | Larger rooms need ambient threats |
| Loot room guard chance | 35% | **45%** | Guards more common in spacious rooms |

## Files Changed

### `server/app/core/wfc/module_utils.py`
- `MODULE_SIZE = 6` → `MODULE_SIZE = 8`

### `server/app/core/wfc/presets.py`
- All 49 preset module tile grids rewritten from 6×6 to 8×8
- Socket patterns updated to 8-char strings
- `maxEnemies` increased (standard rooms: 4-5, grand rooms: 5-6)
- `spawnSlots` expanded to 8 per room with coordinates spread across 6×6 interior
- `SIZE_PRESETS` labels updated to reflect new tile dimensions
- Module `width`/`height` fields updated from 6 to 8

### `server/app/core/wfc/dungeon_generator.py`
- `_FLOOR_SIZE_PROGRESSION` comments updated (3×3=24×24, 4×4=32×32, etc.)
- `_MAX_ENEMIES_PER_ROOM_PROGRESSION` bumped +1 per tier

### `server/tests/test_wfc_dungeon.py`
- `test_module_size_constant`: 6 → 8
- `test_preset_modules_are_6x6` renamed to `test_preset_modules_are_8x8`, assertions updated
- `test_derive_sockets_solid_wall`: socket strings updated to 8-char
- `test_derive_sockets_corridor`: socket strings updated to 8-char (`WWOOOOWW`)
- `test_rotate_tiles_90cw`: dimension assertions updated to 8

### Files NOT changed (no changes needed)
- `wfc_engine.py` — already uses `MODULE_SIZE` dynamically
- `connectivity.py` — tile-level flood-fill, size-agnostic
- `map_exporter.py` — already uses `MODULE_SIZE` dynamically
- `room_decorator.py` — already uses `MODULE_SIZE` dynamically
- `server/configs/wfc-modules/*.json` — legacy JSON modules, not used by the Python engine
- `server/configs/wfc-rulesets/default.json` — socket compatibility rules unchanged
