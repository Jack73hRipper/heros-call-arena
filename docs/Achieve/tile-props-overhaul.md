# Tile Props System Overhaul

**Date:** June 2025  
**Files Modified:** `client/src/canvas/TileProps.js`, `client/src/canvas/RoomOverlays.js`, `client/src/canvas/ThemeEngine.js`

---

## Problem Summary

The tile prop placement system had six root causes making dungeon rooms look broken:

1. **Overlay/prop duplication** — Room overlays (RoomOverlays.js) hardcoded the same decorative objects that the prop system (TileProps.js) also drew. Torches, pillars, altars, chains, and rubble rendered twice at different positions, causing the "torch stick in one place, flame elsewhere" bug.
2. **13 missing draw functions** — The client TileProps.js only had 10 of the 23 prop draw functions from the theme-designer. Missing props failed silently, leaving rooms bare.
3. **Incomplete propAffinities** — ThemeEngine.js only defined affinities for 10 props. The 13 new props had `undefined` affinity, so `_pickFocal()` and accent placement filtered them out — boss rooms never got thrones, ritual circles, or statues.
4. **Empty doorPositions** — Always `[]`. Left as-is per decision (no elegant door system yet).
5. **No spatial grouping** — Addressed via improved archetype configs with intentional position assignments.
6. **Single-tile wall positions** — Addressed via expanded accent lists with varied wall/corner positions.

---

## Changes Made

### 1. TileProps.js — 13 New Prop Draw Functions

Added self-contained Canvas 2D draw functions ported from `tools/theme-designer/src/engine/tileProps.js`:

| Prop | Visual Description |
|---|---|
| `statue` | Stone figure on plinth with optional chip weathering |
| `throne` | High-backed chair with accent cushion and metal studs |
| `cage` | Hanging cage with vertical bars and chain |
| `weapon_rack` | Wooden rack with 2-3 swords and cross-guard details |
| `torch_sconce` | Wall-mounted bracket with flame, glow gradient, and fire core |
| `skull_pile` | Stacked skulls with bone debris and eye sockets |
| `mushroom_cluster` | 2-4 bioluminescent mushrooms with glow halo |
| `web` | Corner spider web with spoke lines and concentric arcs |
| `fountain` | Octagonal stone basin with water fill and ripple rings |
| `candelabra` | Standing candelabra with 3-5 arms, candles, and warm glow |
| `ritual_circle` | Outer/inner rings with pentagram, runes, and center glow |
| `iron_maiden` | Upright sarcophagus with open spiked door and rivets |
| `tombstone` | Tilted gravestone with 3 shape variants and cross carving |

**PROP_DRAW_MAP** expanded from 10 → 23 entries.

### 2. TileProps.js — ARCHETYPE_PROP_SLOTS Rewrite

Completely rewrote the archetype configurations to:

- **Fix duplication**: Props now own all discrete objects; overlays own ambient effects only
- **Add focal systems**: Boss rooms pick from altar/throne/ritual_circle; prison rooms pick from cage/iron_maiden
- **Use appropriate wall props**: Enemy rooms use `torch_sconce` (unified wall torch) instead of `brazier` (floor bowl), eliminating the split-torch bug
- **Add 7 extended archetypes**: `cathedral`, `ritual`, `torture`, `graveyard`, `armory`, `ossuary`, `fungal_grotto` for theme-designer parity

| Archetype | maxProps | Focal | Key Accents |
|---|---|---|---|
| boss | 6 | altar/throne/ritual_circle | pillars at corners, braziers flanking, banners, statues |
| enemy | 4 | — | torch_sconces on walls, weapon_rack, rubble, barrels |
| loot | 4 | — | barrels at corners+floor, torch_sconces, webs |
| spawn | 3 | — | banners, torch_sconces |
| empty | 3 | — | rubble at corners+floor, webs, skull_piles, tombstones |
| stairs | 3 | — | pillars on sides, torch_sconce on top |
| shrine | 5 | — | altar at center (100%), braziers, banners, statues, candelabra |
| library | 2 | — | torch_sconces only (overlay owns bookshelves) |
| prison | 5 | cage/iron_maiden | chains on L/R walls, torch_sconce, skull_piles |
| flooded | 4 | — | puddles, mushroom_clusters |

### 3. RoomOverlays.js — Removed Hardcoded Prop Elements

Removed discrete object drawings from 6 overlays. Each overlay retains its ambient effects (washes, tints, gradients, floor patterns).

| Overlay | Removed | Kept |
|---|---|---|
| Boss | Corner pillars, center sigil | Palette shift wash, wall trim |
| Enemy | Paired wall torches, weapon rack lines | Worn path between doors |
| Empty | Corner rubble clumps | Dark wash, darkened wall edges |
| Shrine | Center altar, flanking braziers, top banners | Floor shine, accent floor border |
| Prison | Chain drawings on walls | Dark wash, corner vignette, doorway iron bars |
| Flooded | Puddle ellipses | Water tint, reflective edge highlights, ripple arcs |

**Design rule**: Props own all discrete objects. Overlays own ambient mood effects. Exception: Library bookshelves remain in the overlay since they constitute the room's core wall identity and the prop system uses torch_sconces for library rooms instead.

### 4. ThemeEngine.js — Extended propAffinities (11 themes × 13 new props)

Every theme now defines affinities for all 23 props. Values are theme-appropriate:

| Theme | High-affinity new props | Zero/near-zero new props |
|---|---|---|
| Bleeding Catacombs | skull_pile (0.8), iron_maiden (0.7), torch_sconce (0.7) | mushroom_cluster (0.1), fountain (0.1) |
| Ashen Undercroft | torch_sconce (0.8), weapon_rack (0.5) | mushroom_cluster (0), fountain (0) |
| Drowned Sanctum | fountain (0.8), mushroom_cluster (0.7), statue (0.5) | weapon_rack (0.1), iron_maiden (0.1) |
| Hollowed Cathedral | candelabra (0.9), statue (0.8), throne (0.7) | cage (0.1), iron_maiden (0.1), mushroom_cluster (0) |
| Iron Depths | cage (0.8), iron_maiden (0.8), weapon_rack (0.7) | mushroom_cluster (0), ritual_circle (0.1), fountain (0.1) |
| Forgotten Cellar | torch_sconce (0.7), web (0.6), weapon_rack (0.4) | throne (0), ritual_circle (0), fountain (0) |
| Pale Ossuary | skull_pile (1.0), tombstone (0.8), candelabra (0.7) | mushroom_cluster (0), weapon_rack (0.1) |
| Silent Vault | candelabra (0.7), statue (0.6), throne (0.5) | mushroom_cluster (0), iron_maiden (0) |
| Fungal Grotto | mushroom_cluster (1.0), web (0.7) | throne (0), iron_maiden (0) |
| Frozen Crypt | tombstone (0.6), statue (0.5) | mushroom_cluster (0) |
| Cursed Shrine | ritual_circle (1.0), candelabra (0.8), torch_sconce (0.7) | mushroom_cluster (0) |

---

## Architecture After Changes

```
Server (room_decorator.py)
  └─ assigns archetype string + bounds per room
  └─ map_exporter.py sends via WebSocket

Client (dungeonRenderer.js line 242)
  └─ drawRoomOverlay(ctx, archetype, ...)   ← ambient mood (RoomOverlays.js)
  └─ drawRoomProps(ctx, { archetype, theme, bounds, seed, ... })
       ├─ _pickFocal()        ← weighted selection filtered by propAffinities
       ├─ accent sorting      ← by position priority (center→corners→walls→floor)
       ├─ _resolvePosition()  ← maps keyword → tile coordinates
       └─ drawTileProp()      ← dispatches to PROP_DRAW_MAP[propName]
```

**Rendering order**: Overlays draw first (ambient washes), then props draw on top (discrete objects). This ensures props are always visible and not hidden under ambient effects.

---

## Not Changed

- **doorPositions** — Still passed as `[]`. No door-aware placement yet.
- **tools/theme-designer/src/engine/tileProps.js** — Untouched (source of truth reference).
- **server/app/room_decorator.py** — Untouched (archetype assignment logic).
- **Library overlay bookshelves** — Intentionally kept in overlay; prop system adds torch_sconces only.
