# Phase 21: Dungeon Visual Variety — Design & Implementation Plan

## Overview

**Goal:** Dramatically increase dungeon visual variety through new tile styles, procedural floor props, additional themes, new room archetypes, and wall-edge transition tiles — all within the existing procedural Canvas 2D pipeline (no sprite files required).

**Theme:** Grimdark fantasy — Dark Souls / Bloodborne — oppressive, decayed, distinctive per biome.

**Status:** Phase 21A Complete, Phase 21B Complete, Phase 21C Complete, Phase 21D Complete  
**Prerequisites:** All 8 existing themes functional in Theme Designer + ThemeEngine  
**Test Target:** Visual verification via Theme Designer tool after each phase

---

## Problem Statement

Currently 8 themes share only **5 wall styles** and **5 floor styles**, meaning 3 themes are visual recolors of others. Room archetypes (6 total) only apply translucent overlays — no structural or prop-based differentiation. Corridors look nearly identical across all themes. There are no environmental props, transition tiles, or sub-room structural variation.

### Current Coverage Matrix

| Theme | Wall Style | Floor Style | Unique? |
|-------|-----------|-------------|---------|
| Bleeding Catacombs | `cracked_stone` | `flagstone` | ✅ Unique pair |
| Ashen Undercroft | `scorched_brick` | `ash_covered` | ✅ Unique pair |
| Drowned Sanctum | `mossy_stone` | `flooded` | ✅ Unique pair |
| Hollowed Cathedral | `carved_stone` | `cracked_marble` | ✅ Unique pair |
| Iron Depths | `iron_plate` | `metal_grate` | ✅ Unique pair |
| Forgotten Cellar | `cracked_stone` ❌ | `flagstone` ❌ | ❌ Reuses Catacombs |
| Pale Ossuary | `carved_stone` ❌ | `cracked_marble` ❌ | ❌ Reuses Cathedral |
| Silent Vault | `mossy_stone` ❌ | `flooded` ❌ | ❌ Reuses Drowned |

---

## Phase Breakdown

### Phase 21A — Unique Wall & Floor Styles for Existing Themes
### Phase 21B — Procedural Floor Props System
### Phase 21C — New Room Archetypes
### Phase 21D — Wall-Edge Transition Tiles
### Phase 21E — New Dungeon Themes (3 new biomes)
### Phase 21F — Client ThemeEngine Sync + Server Config Export

---

## Phase 21A — Unique Wall & Floor Styles (Eliminate reuse)

**Goal:** Give Forgotten Cellar, Pale Ossuary, and Silent Vault their own unique drawing algorithms so every theme is visually distinct.

### New Drawing Functions

#### 1. `drawWall_roughHewn` — Forgotten Cellar
Irregular rough-cut stone with chisel marks and uneven block sizes. Simple, utilitarian quarry stone.

- Randomized block widths (not uniform grid) — 2-4 blocks per row with varied widths
- Chisel mark strokes: short angled 2-3px lines (2-3 per block, seeded)
- No mortar bleed, no vignette — plain and bare
- Top-edge highlight, bottom-edge shadow per block (existing pattern)

#### 2. `drawFloor_packedEarth` — Forgotten Cellar
Compacted dirt with tiny pebble dots. No grid pattern — organic texture.

- Base fill with `palette.floor`
- No slab grid — single solid fill
- 4-8 tiny pebble dots (1-2px circles) scattered deterministically
- 1-2 faint scratch lines (0.5px, very subtle directional grain)
- No stains, no debris

#### 3. `drawWall_boneStack` — Pale Ossuary
Horizontal rows of bone-like rounded segments, densely packed, with thin dark seams.

- 4 horizontal rows of rounded-rectangle "bones" (oblong segments)
- Each bone: rounded corners (2px radius), slight color variation
- Thin dark seam lines between rows (1px)
- No mortar bleed, no cracks — pristine and unsettling
- Every bone subtly different width (seeded)

#### 4. `drawFloor_polishedSlab` — Pale Ossuary
Smooth, large tiles with barely visible seam lines. Austere, clean.

- 2×2 large slabs with very faint seam (palette.grout, 1px, 0.3 alpha)
- Each slab nearly identical color — only ±1 RGB variation
- Optional single faint reflection highlight (1px lighter bar at 30% height)
- No texture dots, no stains — the emptiness is the horror

#### 5. `drawWall_ashlarBlock` — Silent Vault
Tight-fit ashlar masonry — perfectly uniform rectangular blocks, minimal mortar, architectural precision.

- 3×2 uniform blocks with hair-thin mortar (1px, very dark)
- Each block face: gradient simulation (1px lighter stripe at top, 1px darker at bottom)
- Perfectly aligned — no row offset (unlike brick patterns)
- Optional: faint incised line border 2px inside each block (geometric precision)
- No cracks, no vignette — sealed and orderly

#### 6. `drawFloor_dustyTile` — Silent Vault  
Geometric tile pattern with a faint dust film overlay.

- 3×3 smaller tile grid (more grid lines = archival/library feel)
- Tiles drawn with palette.floor, very faint grout
- Thin dust film: semi-transparent grey overlay (rgba 40,40,50, 0.04) over entire tile
- 1 seeded "dust mote" per tile (1px, slightly lighter) for subtle life
- No debris, no stains

### Files Modified

| File | Changes |
|------|---------|
| `tools/theme-designer/src/engine/tilePatterns.js` | Add 3 new wall functions + 3 new floor functions |
| `tools/theme-designer/src/engine/themes.js` | Update Forgotten Cellar, Pale Ossuary, Silent Vault to use new styles |
| `client/src/canvas/ThemeEngine.js` | Add new wall/floor draw functions + wire into style dispatcher |
| `server/configs/themes/forgotten_cellar.json` | Update wall.style + floor.style + params |
| `server/configs/themes/pale_ossuary.json` | Update wall.style + floor.style + params |
| `server/configs/themes/silent_vault.json` | Update wall.style + floor.style + params |

### Implementation Steps

1. **Add 3 wall drawing functions** to `tilePatterns.js`:
   - `drawWall_roughHewn(ctx, x, y, size, seed, palette, params)`
   - `drawWall_boneStack(ctx, x, y, size, seed, palette, params)`
   - `drawWall_ashlarBlock(ctx, x, y, size, seed, palette, params)`

2. **Add 3 floor drawing functions** to `tilePatterns.js`:
   - `drawFloor_packedEarth(ctx, x, y, size, seed, palette, params)`
   - `drawFloor_polishedSlab(ctx, x, y, size, seed, palette, params)`
   - `drawFloor_dustyTile(ctx, x, y, size, seed, palette, params)`

3. **Update `themeRenderer.js`** — add new styles to the wall/floor dispatcher switch statements

4. **Update 3 theme definitions** in `themes.js`:
   - `forgotten_cellar.wall.style` → `'rough_hewn'`
   - `forgotten_cellar.floor.style` → `'packed_earth'`
   - `pale_ossuary.wall.style` → `'bone_stack'`
   - `pale_ossuary.floor.style` → `'polished_slab'`
   - `silent_vault.wall.style` → `'ashlar_block'`
   - `silent_vault.floor.style` → `'dusty_tile'`

5. **Mirror all changes** into `client/src/canvas/ThemeEngine.js` (copy drawing functions + update BUILT_IN_THEMES + update dispatchers)

6. **Update 3 server config JSONs** with new style names + appropriate params

### Verification

- [ ] Launch Theme Designer (`start-theme-designer.bat`), select each updated theme
- [ ] Confirm Forgotten Cellar walls look uniquely rough/irregular (not cracked_stone)
- [ ] Confirm Pale Ossuary walls show horizontal bone-segment pattern
- [ ] Confirm Silent Vault walls show precise ashlar grid
- [ ] Confirm all 3 floors are visually distinct from their previous shared style
- [ ] Verify no visual artifacts at tile boundaries (seams, color bleeding)
- [ ] All 8 themes render without console errors

### Phase 21A — Implementation Log

**Completed:** 2025-03-16  

**Files Modified (6 files):**

1. **`tools/theme-designer/src/engine/tilePatterns.js`**
   - Added `drawWall_roughHewn()` — irregular block widths (2-4 per row), chisel mark strokes, no vignette
   - Added `drawWall_boneStack()` — 4 rows of rounded-rectangle bone segments, thin dark seams
   - Added `drawWall_ashlarBlock()` — 3x2 uniform blocks, hair-thin mortar, incised line borders
   - Added `drawFloor_packedEarth()` — solid fill, 4-8 seeded pebble dots, 1-2 faint scratch lines
   - Added `drawFloor_polishedSlab()` — 2x2 slabs, ±1 RGB variation, faint reflection highlight, 0.3 alpha grout
   - Added `drawFloor_dustyTile()` — 3x3 tile grid, 1 dust mote per tile, rgba(40,40,50,0.04) dust film
   - Updated `WALL_DRAW_MAP` — added `rough_hewn`, `bone_stack`, `ashlar_block`
   - Updated `FLOOR_DRAW_MAP` — added `packed_earth`, `polished_slab`, `dusty_tile`

2. **`tools/theme-designer/src/engine/themes.js`**
   - `forgotten_cellar.wall.style` → `'rough_hewn'` (was `'cracked_stone'`)
   - `forgotten_cellar.floor.style` → `'packed_earth'` (was `'flagstone'`)
   - `pale_ossuary.wall.style` → `'bone_stack'` (was `'carved_stone'`)
   - `pale_ossuary.floor.style` → `'polished_slab'` (was `'cracked_marble'`)
   - `silent_vault.wall.style` → `'ashlar_block'` (was `'mossy_stone'`)
   - `silent_vault.floor.style` → `'dusty_tile'` (was `'flooded'`)

3. **`client/src/canvas/ThemeEngine.js`**
   - Mirrored all 6 new drawing functions (compact client-side format)
   - Updated `WALL_FN` dispatch map with 3 new entries
   - Updated `FLOOR_FN` dispatch map with 3 new entries
   - Updated `BUILT_IN_THEMES` for all 3 themes with new style names + params

4. **`server/configs/themes/forgotten_cellar.json`** — wall→`rough_hewn`, floor→`packed_earth`
5. **`server/configs/themes/pale_ossuary.json`** — wall→`bone_stack`, floor→`polished_slab`
6. **`server/configs/themes/silent_vault.json`** — wall→`ashlar_block`, floor→`dusty_tile`

**Architecture Notes:**
- `themeRenderer.js` required NO changes — it reads from `WALL_DRAW_MAP`/`FLOOR_DRAW_MAP` dynamically
- All new functions follow existing signature: `(ctx, x, y, size, seed, palette, params)`
- All drawing is deterministic via `cellHash()` seeding
- No new dependencies or imports added

### Post-21A Coverage Matrix

| Theme | Wall Style | Floor Style | Unique? |
|-------|-----------|-------------|---------|
| Bleeding Catacombs | `cracked_stone` | `flagstone` | ✅ |
| Ashen Undercroft | `scorched_brick` | `ash_covered` | ✅ |
| Drowned Sanctum | `mossy_stone` | `flooded` | ✅ |
| Hollowed Cathedral | `carved_stone` | `cracked_marble` | ✅ |
| Iron Depths | `iron_plate` | `metal_grate` | ✅ |
| Forgotten Cellar | `rough_hewn` | `packed_earth` | ✅ NEW |
| Pale Ossuary | `bone_stack` | `polished_slab` | ✅ NEW |
| Silent Vault | `ashlar_block` | `dusty_tile` | ✅ NEW |

---

## Phase 21B — Procedural Floor Props System

**Goal:** Add a system for rendering small procedural decorative objects on floor tiles, driven by room archetype and theme. All props are Canvas 2D drawn — no sprite files.

### Architecture

New file: `tools/theme-designer/src/engine/tileProps.js`  
Mirrored to: `client/src/canvas/TileProps.js`

Props are drawn **on top of** base floor tiles, **before** room archetype overlays. Each prop is a small self-contained drawing function that takes `(ctx, x, y, tileSize, seed, palette)`.

Props are placed deterministically using `cellHash(gridX, gridY, propSalt)` — same position always gets the same prop.

### Prop Definitions (10 props)

| # | Prop | Size | Drawing Description | Theme Affinity |
|---|------|------|-------------------|----------------|
| 1 | **Pillar** | Full tile | Circle with shadow ring + highlight arc. Blocks top 60% of tile. | All (boss, corridor) |
| 2 | **Rubble Pile** | ~40% tile | 4-6 small overlapping rectangles in stone color, shadow underneath | All (empty rooms) |
| 3 | **Brazier** | ~30% tile | Small circle base + orange glow halo (radial gradient), centered | All (enemy, boss) |
| 4 | **Coffin** | ~70% tile | Oblong rectangle with lid line, darker fill, stone-colored | Catacombs, Ossuary |
| 5 | **Bookshelf** | Wall-adjacent | Tall rectangle with 3-4 horizontal lines (shelves), wall-hugging | Vault, Cathedral |
| 6 | **Altar** | ~50% tile | Rectangle base, accent-colored top surface, center gemstone dot | Boss rooms |
| 7 | **Puddle** | ~40% tile | Irregular semi-transparent blue ellipse with highlight edge | Drowned Sanctum |
| 8 | **Barrel** | ~25% tile | Small circle with cross-line top, brown tones | Cellar, Loot rooms |
| 9 | **Chains** | Wall-adjacent | 2-3 thin vertical lines dangling from top edge of tile, metal color | Iron Depths, Catacombs |
| 10 | **Banner** | Wall-adjacent | Narrow rectangle hanging from top, tattered bottom (zigzag), accent color | Cathedral, Boss rooms |

### Prop Placement Rules

```
Props placement is controlled by two systems:

1. Theme → propAffinities: { propName: weight }
   Each theme defines which props "belong" to its biome.
   
2. Archetype → propSlots: [{ prop, position, chance }]
   Each room archetype defines where props go within the room.
   
Placement flow:
  For each room:
    archetype = room.archetype (boss, enemy, loot, etc.)
    theme = active dungeon theme
    slots = ARCHETYPE_PROP_SLOTS[archetype]
    for each slot:
      if theme.propAffinities[slot.prop] > 0:
        if cellHash(roomSeed, slotIndex) < slot.chance:
          drawProp(slot.prop, position)
```

### Theme Prop Affinity Map

```javascript
// Added to each theme definition in themes.js
propAffinities: {
  // Theme: Bleeding Catacombs
  pillar: 0.6, rubble: 0.4, brazier: 0.8, coffin: 1.0,
  bookshelf: 0.0, altar: 0.7, puddle: 0.0, barrel: 0.2,
  chains: 0.8, banner: 0.3,
}
```

| Theme | High-affinity Props |
|-------|-------------------|
| Bleeding Catacombs | coffin, chains, brazier |
| Ashen Undercroft | brazier, rubble, barrel |
| Drowned Sanctum | puddle, pillar, chains |
| Hollowed Cathedral | banner, bookshelf, altar |
| Iron Depths | chains, barrel, pillar |
| Forgotten Cellar | barrel, rubble, brazier |
| Pale Ossuary | coffin, pillar, altar |
| Silent Vault | bookshelf, pillar, banner |

### Files Modified / Created

| File | Changes |
|------|---------|
| `tools/theme-designer/src/engine/tileProps.js` | **NEW** — 10 prop drawing functions + placement logic |
| `tools/theme-designer/src/engine/themes.js` | Add `propAffinities` to each theme |
| `tools/theme-designer/src/engine/roomArchetypes.js` | Import props, call placement during overlay |
| `tools/theme-designer/src/engine/themeRenderer.js` | Wire prop rendering into tile cache or draw pass |
| `client/src/canvas/TileProps.js` | **NEW** — Mirror of tileProps.js for game client |
| `client/src/canvas/ThemeEngine.js` | Import and call TileProps in draw pass |

### Implementation Steps

1. **Create `tileProps.js`** with 10 `drawProp_*` functions
2. **Add `propAffinities`** to all 8 theme definitions
3. **Define `ARCHETYPE_PROP_SLOTS`** — map from archetype → list of prop placement rules
4. **Add prop dispatch function** `drawTileProp(ctx, propName, x, y, tileSize, seed, palette)`
5. **Integrate into `roomArchetypes.js`** — call prop placement after base overlay
6. **Mirror to client** — create `TileProps.js`, wire into ThemeEngine

### Verification

- [ ] Launch Theme Designer, toggle Archetypes view
- [ ] Boss rooms show altar + pillar + brazier (theme-appropriate)
- [ ] Enemy rooms show brazier + wall props
- [ ] Loot rooms show barrels/chests
- [ ] Empty rooms show rubble + dim atmosphere
- [ ] Catacombs show coffins, Iron Depths shows chains
- [ ] Props never overlap or extend beyond tile bounds
- [ ] Props look appropriate at 48px tile size (not too detailed)

### Phase 21B — Implementation Log

**Completed:** 2026-03-16

**Files Created (2 files):**

1. **`tools/theme-designer/src/engine/tileProps.js`** (NEW)
   - 10 prop drawing functions: `drawProp_pillar`, `drawProp_rubble`, `drawProp_brazier`, `drawProp_coffin`, `drawProp_bookshelf`, `drawProp_altar`, `drawProp_puddle`, `drawProp_barrel`, `drawProp_chains`, `drawProp_banner`
   - All follow signature: `(ctx, x, y, size, seed, palette)`
   - `PROP_DRAW_MAP` — dispatch map for all 10 props
   - `ARCHETYPE_PROP_SLOTS` — per-archetype prop placement rules (boss, enemy, loot, spawn, empty, stairs)
   - `drawTileProp()` — draws a single prop by name at a tile position
   - `drawRoomProps()` — orchestrates all prop drawing for a room (archetype × theme affinity × chance)
   - `_resolvePosition()` — converts position keywords (center, corners, flanking_center, wall_left/right/top/bottom, random_floor) to tile coordinates
   - Placement uses `cellHash()` for deterministic seeding — same room always gets same props
   - Effective chance = slot.chance × theme.propAffinities[prop] — zero affinity = never placed

2. **`client/src/canvas/TileProps.js`** (NEW)
   - Self-contained mirror of tileProps.js with inlined utilities (cellHash, hexToRgb, rgbToCSS, shiftColor, hexAlpha, lerpColor)
   - All 10 prop functions, ARCHETYPE_PROP_SLOTS, drawTileProp, drawRoomProps exported
   - Compact client-side format matching ThemeEngine.js conventions

**Files Modified (4 files):**

3. **`tools/theme-designer/src/engine/themes.js`**
   - Added `propAffinities` object to all 8 theme definitions
   - Each contains weights for all 10 props (0.0 = never, 1.0 = always when slot allows)
   - Theme-specific high-affinity props:
     - Bleeding Catacombs → coffin (1.0), chains (0.8), brazier (0.8)
     - Ashen Undercroft → brazier (0.8), rubble (0.6), barrel (0.6)
     - Drowned Sanctum → puddle (1.0), pillar (0.7), chains (0.6)
     - Hollowed Cathedral → banner (1.0), bookshelf (0.8), altar (0.8)
     - Iron Depths → chains (0.9), barrel (0.7), pillar (0.7)
     - Forgotten Cellar → barrel (0.9), rubble (0.7), brazier (0.7)
     - Pale Ossuary → coffin (0.9), altar (0.8), pillar (0.6)
     - Silent Vault → bookshelf (0.9), pillar (0.8), banner (0.7)

4. **`tools/theme-designer/src/engine/roomArchetypes.js`**
   - Added import: `import { drawRoomProps } from './tileProps.js'`
   - Added `drawRoomProps(ctx, opts)` call inside `drawRoomOverlay()` BEFORE archetype switch
   - Props render on floor tiles before room-specific overlays (pillar/sigil/torches/etc.)

5. **`client/src/canvas/ThemeEngine.js`**
   - Added `propAffinities` to all 8 `BUILT_IN_THEMES` entries — values match themes.js exactly

6. **`tools/theme-designer/src/engine/themeRenderer.js`** — NO CHANGES NEEDED
   - themeRenderer caches individual tile variants; props are room-level via `drawRoomOverlay`
   - RoomArchetypePreview.jsx already calls `drawRoomOverlay` which now includes props

**Architecture Notes:**
- Props are drawn at room level, not tile level — they flow through `drawRoomOverlay()` in roomArchetypes.js
- Two-layer filtering: archetype slots define WHERE props go, theme affinities define WHICH props appear
- All prop drawing is deterministic — `cellHash(seed, slotIndex, 100)` controls placement rolls
- Props stay within tile bounds — sizes specified as fractions of tileSize (e.g., 0.28, 0.4, 0.7)
- No new dependencies or external imports added

---

## Phase 21C — New Room Archetypes (4 additions)

**Goal:** Add 4 new room archetypes that utilize the prop system from 21B to create visually differentiated room types.

### New Archetypes

#### 1. `shrine` — Sacred Shrine
**Description:** A consecrated space with a central altar, symmetrical candle-spots, and an accent-colored floor border. Feels maintained and purposeful.

**Visual elements:**
- Center altar prop (always placed)
- 2 brazier props flanking the altar (left/right of center)
- Accent-colored thin floor border (1px inset rectangle)
- Subtle floor shine (highlight 0.03 alpha over inner area)
- Wall-adjacent banner props (if Cathedral or Vault theme)

**Used for:** Special encounter rooms, quest objectives, floor transition rooms.

#### 2. `library` — Archive / Library
**Description:** Wall-hugging bookshelf rectangles on all sides, slightly lighter maintained floor. Scholarly and orderly.

**Visual elements:**
- Bookshelf props along all 4 walls (every other wall tile)
- Floor slightly lighter (highlight 0.02 alpha)
- No center decorations — open reading space
- Faint dust motes (2-3 tiny 1px dots near center)

**Used for:** Non-combat discovery rooms, lore rooms, potential puzzle rooms.

#### 3. `prison` — Prison / Cage Room
**Description:** Iron bar lines across doorways, darker oppressive floor, chain props hanging from walls.

**Visual elements:**
- Chains props on left/right wall tiles
- Doorway iron bar overlay: 3 thin vertical lines across door tile
- Darker floor wash (rgba 0,0,0,0.10)
- Corner shadow vignette (heavier than empty — 0.15)
- No floor decorations — bare stone

**Used for:** Enemy-heavy rooms, trapped rooms, pre-boss gauntlets.

#### 4. `flooded` — Flooded Chamber
**Description:** Water tint over entire room, puddle props scattered, no wall decorations. Eerie and inhospitable.

**Visual elements:**
- Blue-tinted floor overlay (rgba 10,30,50,0.08)
- 2-4 puddle props on random floor tiles
- Slightly reflective floor edge highlights near walls
- No wall decorations — water has corroded everything
- Very subtle ripple lines (1-2 concentric arcs near center)

**Used for:** Environmental hazard rooms (future slow effect?), atmosphere variety.

### Files Modified

| File | Changes |
|------|---------|
| `tools/theme-designer/src/engine/roomArchetypes.js` | Add 4 new overlay functions + ROOM_ARCHETYPES entries |
| `tools/theme-designer/src/components/RoomArchetypePreview.jsx` | Include new archetypes in preview grid |
| `server/app/core/wfc/room_decorator.py` | Add new archetypes to room assignment pool |
| `server/app/core/wfc/dungeon_styles.py` | Add archetype weight overrides per style |

### Implementation Steps

1. **Add 4 entries to `ROOM_ARCHETYPES`** object (label + description)
2. **Implement `_drawShrineOverlay`** — altar, braziers, floor border, banners
3. **Implement `_drawLibraryOverlay`** — wall bookshelves, light floor, dust motes
4. **Implement `_drawPrisonOverlay`** — chains, iron bars, dark floor, corner vignette
5. **Implement `_drawFloodedOverlay`** — water tint, puddles, ripple arcs
6. **Update `drawRoomOverlay` switch** to include new archetypes
7. **Update `RoomArchetypePreview.jsx`** to show all 10 archetypes in preview grid
8. **Update server `room_decorator.py`** to assign new archetypes to eligible rooms
9. **Update `dungeon_styles.py`** with archetype affinity per style

### Archetype Assignment Rules (Server)

```python
# In room_decorator.py — extended assignment logic:
# shrine:  5% of flexible rooms, always if room has "sacred" tag
# library: 5% of flexible rooms, weight doubled in treasure_vault style
# prison:  10% of enemy rooms (override from 'enemy' when room has ≥3 enemies)
# flooded: 5% of flexible rooms, weight 3× in drowned_sanctum theme
```

### Verification

- [ ] Theme Designer Archetypes view shows all 10 room types
- [ ] Shrine has visible altar + braziers + border
- [ ] Library has wall bookshelves all around perimeter
- [ ] Prison has chains + iron bar doorway overlay
- [ ] Flooded has blue tint + puddle props
- [ ] New archetypes work with all 8 themes (props adapt to theme palette)
- [ ] No visual overlap between props from archetype and props from 21B

### Phase 21C — Implementation Log

**Completed:** 2026-03-16

**Files Modified (6 files):**

1. **`tools/theme-designer/src/engine/roomArchetypes.js`**
   - Added 4 entries to `ROOM_ARCHETYPES`: `shrine`, `library`, `prison`, `flooded`
   - Implemented `_drawShrineOverlay()` — central altar with accent top + gemstone, 2 flanking braziers (radial glow halos), accent-colored 1px inset floor border, wall-adjacent banners on top wall (every other tile), subtle floor shine (0.03 alpha)
   - Implemented `_drawLibraryOverlay()` — bookshelves on all 4 walls (every other tile) via helper `_drawWallBookshelf()`, slightly lighter floor (0.02 highlight), 3 dust mote dots near center
   - Implemented `_drawPrisonOverlay()` — dark floor wash (rgba 0,0,0,0.10), heavy corner shadow vignette (0.15), chains on left/right walls (extra pair on larger rooms), iron bar doorway overlay (3 vertical lines + 1 horizontal cross bar per door)
   - Implemented `_drawFloodedOverlay()` — blue-tinted floor overlay (rgba 10,30,50,0.08), 2-4 deterministic puddle ellipses with highlight edges, reflective 0.04 alpha edge strips near all 4 walls, 2 ripple arc pairs near center
   - Updated `drawRoomOverlay()` switch — added cases for `shrine`, `library`, `prison`, `flooded`
   - Added `_drawWallBookshelf()` helper — shelf frame, 4 shelf lines, seeded book spines per shelf

2. **`tools/theme-designer/src/engine/tileProps.js`**
   - Added `ARCHETYPE_PROP_SLOTS` entries for 4 new archetypes:
     - `shrine`: altar (center 1.0), brazier (flanking_center 0.9), banner (wall_top 0.6)
     - `library`: bookshelf on all 4 walls (wall_top/bottom 0.8, wall_left/right 0.6)
     - `prison`: chains on 3 wall positions (wall_left 0.8, wall_right 0.8, wall_top 0.4)
     - `flooded`: puddle (random_floor 0.9, center 0.7, corners 0.3)

3. **`tools/theme-designer/src/components/RoomArchetypePreview.jsx`**
   - Extended DUNGEON_MAP from 18 to 27 rows (20×27) — added 4 new rooms in 2 row groups
   - Added 4 DUNGEON_ROOMS entries: shrine (1-6, 19-21), library (12-17, 19-21), prison (1-6, 23-25), flooded (12-17, 23-25)
   - Shrine and prison rooms have door tiles for visual demo; library and flooded have no doors
   - Isolated side-by-side view auto-updates via `Object.keys(ROOM_ARCHETYPES)` — now shows all 10 archetypes

4. **`server/app/core/wfc/room_decorator.py`**
   - Added Pass C-pre: specialty archetype carving before deck dealing
     - `shrine_chance` (default 5%), `library_chance` (5%), `flooded_chance` (5%) — rolled per remaining room
     - Specialty rooms removed from remaining pool before enemy/loot/empty deck is built
   - Added Pass C1.5: prison override — enemy rooms with `maxEnemies ≥ 3` get `prison_enemy_chance` (default 10%) to become prison
   - Added content placement for 4 new roles:
     - `shrine`: non-combat, optional scatter chest (40% chance)
     - `library`: non-combat discovery, optional scatter chest (50% chance)
     - `prison`: heavy enemy room, minimum 2 enemies placed
     - `flooded`: environmental atmosphere, occasional enemy (30% chance)
   - Updated `role_count` dict with 4 new role keys for stats tracking
   - All archetype chances configurable via `config.get("archetype_overrides", {})`

5. **`server/app/core/wfc/dungeon_styles.py`**
   - Added `archetype_overrides` field to all 5 dungeon styles:
     - `balanced`: empty (default chances apply)
     - `dense_catacomb`: prison ×2.5 (0.25), flooded reduced (0.02)
     - `open_ruins`: shrine +60% (0.08), flooded +60% (0.08), library low (0.03)
     - `boss_rush`: shrine slightly up (0.06), prison +50% (0.15)
     - `treasure_vault`: library doubled (0.10), shrine standard (0.05)
   - Added `get_archetype_overrides()` function — returns copy of style's archetype overrides dict

6. **`server/app/core/wfc/dungeon_generator.py`**
   - Added import: `get_archetype_overrides`
   - Merges `archetype_overrides` into `decorator_settings` as nested dict after style decorator overrides, before PVPVE injection

**Architecture Notes:**
- Overlay functions follow identical signature pattern: `(ctx, opts)` with destructured `{ theme, tileSize: s, roomOffsetX: ox, roomOffsetY: oy, bounds, ... }`
- Props flow through existing `drawRoomProps(ctx, opts)` call in `drawRoomOverlay()` — new archetype slots use existing prop draw functions
- Server-side archetype assignment cascades: `dungeon_styles.archetype_overrides` → `dungeon_generator` merges into `decorator_settings` → `room_decorator` reads via `config.get("archetype_overrides", {})`
- Prison is unique — it's a post-deck override that promotes "enemy" rooms, not a pre-deck carve-out like shrine/library/flooded
- No new dependencies or imports added beyond existing utility functions
- All 51 dungeon_styles tests + 15 decorator tests pass clean

---

## Phase 21D — Wall-Edge Transition Tiles

**Goal:** Add visual transition rendering at wall→floor boundaries so rooms feel organic instead of having hard pixel cutoffs.

### Concept

When drawing floor tiles that are **adjacent to a wall tile**, add a small decorative overlay on the floor-side of the edge. This creates a crumbled/worn/debris border effect.

### Edge Types (Per Theme)

| Theme | Edge Style | Visual |
|-------|-----------|--------|
| Bleeding Catacombs | `crumble` | 2-3 small stone-colored rectangles along the wall edge |
| Ashen Undercroft | `scorch` | Gradient darkening toward the wall edge (4px fade) |
| Drowned Sanctum | `moss_creep` | Thin green-tinted semi-transparent irregular line |
| Hollowed Cathedral | `rubble_strip` | Fine debris dots in a 4px strip along wall |
| Iron Depths | `rust_drip` | Thin orange-brown drip line on floor near wall |
| Forgotten Cellar | `dust_drift` | Very faint grey gradient (2px) at wall base |
| Pale Ossuary | `clean_edge` | Almost nothing — just a 1px darker seam line |
| Silent Vault | `seam_line` | Precise 1px geometric inset line matching wall grid |

### Architecture

New field in each theme definition:
```javascript
edge: {
  style: 'crumble',    // drawing algorithm
  intensity: 0.6,      // strength multiplier
  width: 4,            // px extent from wall edge onto floor
}
```

### Detection Logic

```
For each floor tile at (x, y):
  Check 4 cardinal neighbors (x±1, y±1)
  For each neighbor that is a wall:
    Draw edge effect on the corresponding side of the floor tile
    e.g., wall at (x, y-1) → draw edge on TOP of floor tile at (x, y)
```

### Files Modified

| File | Changes |
|------|---------|
| `tools/theme-designer/src/engine/tilePatterns.js` | Add `drawWallEdge(ctx, x, y, size, side, seed, palette, params)` + per-theme edge style functions |
| `tools/theme-designer/src/engine/themes.js` | Add `edge` config to all 8 themes |
| `tools/theme-designer/src/engine/themeRenderer.js` | Call edge drawing after floor tiles, passing neighbor info |
| `client/src/canvas/ThemeEngine.js` | Mirror edge drawing logic + add neighbor-aware draw pass |

### Implementation Steps

1. **Add `edge` config** to all 8 theme definitions in `themes.js`
2. **Implement 8 edge-drawing functions** in `tilePatterns.js`:
   - `drawEdge_crumble`, `drawEdge_scorch`, `drawEdge_mossCreep`, `drawEdge_rubbleStrip`
   - `drawEdge_rustDrip`, `drawEdge_dustDrift`, `drawEdge_cleanEdge`, `drawEdge_seamLine`
3. **Add edge dispatcher** `drawWallEdge(ctx, x, y, size, side, seed, palette, edgeConfig)`
4. **Update `themeRenderer.js`** — after floor render pass, do edge render pass with neighbor lookup
5. **Mirror to `ThemeEngine.js`** — add neighbor-aware edge drawing in `drawTile()` when tile is floor

### Verification

- [ ] All 8 themes show edge effects at wall→floor boundaries
- [ ] Edges only appear on the floor side (not on wall tiles)
- [ ] Edges render on correct sides (top/bottom/left/right based on wall position)
- [ ] Corner tiles (2+ adjacent walls) show edges on all relevant sides
- [ ] Effects are subtle — not distracting at 48px
- [ ] Performance acceptable (edge drawing is cheap — simple fills/strokes)

### Phase 21D — Implementation Log

**Completed:** 2026-03-16

**Files Modified (12 files):**

1. **`tools/theme-designer/src/engine/tilePatterns.js`**
   - Added 8 edge drawing functions:
     - `drawEdge_crumble()` — 2-3 small stone-colored rectangles along wall edge (Bleeding Catacombs)
     - `drawEdge_scorch()` — gradient darkening toward wall edge, 4px fade (Ashen Undercroft)
     - `drawEdge_mossCreep()` — thin green-tinted irregular line + moss dots (Drowned Sanctum)
     - `drawEdge_rubbleStrip()` — 5-8 fine debris dots in 4px strip along wall (Hollowed Cathedral)
     - `drawEdge_rustDrip()` — 1-2 thin orange-brown drip lines near wall (Iron Depths)
     - `drawEdge_dustDrift()` — very faint grey gradient, 2px at wall base (Forgotten Cellar)
     - `drawEdge_cleanEdge()` — single 1px darker seam line (Pale Ossuary)
     - `drawEdge_seamLine()` — precise 1px geometric inset line (Silent Vault)
   - Added `EDGE_DRAW_MAP` — dispatch map for all 8 edge styles
   - Added `drawWallEdge()` — dispatcher function: `(ctx, x, y, size, side, seed, palette, edgeConfig)`
   - All edge functions follow unified signature: `(ctx, x, y, size, side, seed, palette, edgeConfig)` where `side` is 'top'|'bottom'|'left'|'right'

2. **`tools/theme-designer/src/engine/themes.js`**
   - Added `edge` config to all 8 theme definitions:
     - `bleeding_catacombs.edge` → `{ style: 'crumble', intensity: 0.6, width: 4 }`
     - `ashen_undercroft.edge` → `{ style: 'scorch', intensity: 0.7, width: 4 }`
     - `drowned_sanctum.edge` → `{ style: 'moss_creep', intensity: 0.5, width: 3 }`
     - `hollowed_cathedral.edge` → `{ style: 'rubble_strip', intensity: 0.5, width: 4 }`
     - `iron_depths.edge` → `{ style: 'rust_drip', intensity: 0.6, width: 3 }`
     - `forgotten_cellar.edge` → `{ style: 'dust_drift', intensity: 0.4, width: 2 }`
     - `pale_ossuary.edge` → `{ style: 'clean_edge', intensity: 0.3, width: 1 }`
     - `silent_vault.edge` → `{ style: 'seam_line', intensity: 0.4, width: 1 }`

3. **`tools/theme-designer/src/engine/themeRenderer.js`**
   - Added import: `drawWallEdge` from tilePatterns.js
   - Added `drawEdge(ctx, px, py, gridX, gridY, neighbors)` method to ThemeRenderer class
   - Takes `neighbors` object `{ top, bottom, left, right }` — true if neighbor is a wall
   - Calls `drawWallEdge()` for each side where a wall neighbor exists

4. **`client/src/canvas/ThemeEngine.js`**
   - Added 8 edge drawing functions (compact client-side format) matching tilePatterns.js
   - Added `EDGE_FN` dispatch map with all 8 edge styles
   - Added `edge` config to all 8 `BUILT_IN_THEMES` entries — values match themes.js exactly
   - Added `drawEdge(ctx, px, py, gridX, gridY, neighbors)` method to ThemeEngine class

5-12. **Server config JSONs** (8 files) — added `edge` config to all:
   - `server/configs/themes/bleeding_catacombs.json` → `crumble`
   - `server/configs/themes/ashen_undercroft.json` → `scorch`
   - `server/configs/themes/drowned_sanctum.json` → `moss_creep`
   - `server/configs/themes/hollowed_cathedral.json` → `rubble_strip`
   - `server/configs/themes/iron_depths.json` → `rust_drip`
   - `server/configs/themes/forgotten_cellar.json` → `dust_drift`
   - `server/configs/themes/pale_ossuary.json` → `clean_edge`
   - `server/configs/themes/silent_vault.json` → `seam_line`

**Architecture Notes:**
- Edge effects are drawn on **floor tiles**, not wall tiles — they overlay the floor side adjacent to walls
- Each edge function handles all 4 cardinal sides independently (top/bottom/left/right)
- Corner tiles (2+ adjacent walls) correctly receive edges on all relevant sides
- Edge drawing is deterministic via `cellHash()` seeding — same position always produces same effect
- Edge intensity and width are configurable per-theme via `edgeConfig.intensity` and `edgeConfig.width`
- No new dependencies or imports added beyond existing utility functions
- `themeRenderer.js` and `ThemeEngine.js` both expose identical `drawEdge()` API for callers to use
- Callers must pass neighbor wall info; actual dungeon renderer integration deferred to Phase 21F

---

## Phase 21E — New Dungeon Themes (3 new biomes)

**Goal:** Add 3 new themes with unique palettes, unique wall/floor styles, and unique edge styles. Expands the palette from 8 to 11 themes.

### Theme 9: Fungal Grotto

**Mood:** Alien, bioluminescent, organic cave. Mushroom spores, glowing fungal veins, wet organic walls.  
**Inspiration:** Deepnest/Fungal Wastes (Hollow Knight), Blackreach (Skyrim)

```javascript
fungal_grotto: {
  palette: {
    primary:    '#121a10',   // Deep forest black-green
    secondary:  '#1e2a18',   // Dark organic green
    accent:     '#5aaa40',   // Bioluminescent green
    mortar:     '#0e1a0c',   // Organic seam
    highlight:  '#80ee60',   // Bright fungal glow
    floor:      '#2a3822',   // Mossy cave floor
    floorAlt:   '#2d3b25',   // Floor variation
    grout:      '#0a100a',   // Dark organic gap
  },
  wall: { style: 'fungal_growth', ... },
  floor: { style: 'mycelium_mat', ... },
  edge: { style: 'spore_creep', intensity: 0.7, width: 5 },
}
```

**New wall style `drawWall_fungalGrowth`:**
- Irregular bulging organic masses (overlapping circles/ellipses)
- 2-3 bioluminescent dots (accent color, small glow)
- No mortar lines — organic seamless shapes
- Thin tendril lines from top/bottom

**New floor style `drawFloor_myceliumMat`:**
- Dark green-brown base
- Thin branching lines (mycelium network) — 2-3 per tile, seeded
- Very faint spore dots (highlight, 0.2 alpha, 1px)

### Theme 10: Frozen Crypt

**Mood:** Ice-blue, crystalline, pristine but deadly. Cracked ice over ancient stone, frost everywhere.  
**Inspiration:** Irithyll Dungeon (DS3), Frozen Path (ARPG trope)

```javascript
frozen_crypt: {
  palette: {
    primary:    '#0a1020',   // Deep ice-blue black
    secondary:  '#182838',   // Frozen stone
    accent:     '#4488cc',   // Ice blue
    mortar:     '#101828',   // Frost-sealed seam
    highlight:  '#88ccff',   // Bright ice crystal
    floor:      '#253a4e',   // Frost-covered floor
    floorAlt:   '#283d51',   // Floor variation
    grout:      '#080e18',   // Deep frozen gap
  },
  wall: { style: 'ice_crystal', ... },
  floor: { style: 'frozen_stone', ... },
  edge: { style: 'frost_creep', intensity: 0.8, width: 6 },
}
```

**New wall style `drawWall_iceCrystal`:**
- Angular fracture pattern — 3-4 irregular polygons (crystal facets)
- Each facet: slightly different shade of blue-grey
- Bright highlight edge on 1 facet face (simulating light refraction)
- Thin white frost lines at polygon seams

**New floor style `drawFloor_frozenStone`:**
- 2×2 slab grid barely visible under frost
- Light frost film overlay (rgba white, 0.04)
- 1-2 tiny crystal glint dots (highlight color, 1px)
- Optional thin crack line (ice crack, 0.8px, very faint)

### Theme 11: Cursed Shrine

**Mood:** Deep red-gold, corrupted sacred space. Blood rituals, defiled iconography, oppressive crimson atmosphere.  
**Inspiration:** Nightmare of Mensis, Corrupted Monastery

```javascript
cursed_shrine: {
  palette: {
    primary:    '#1a0a10',   // Deep crimson-black
    secondary:  '#2a1520',   // Dark blood-stone
    accent:     '#cc4430',   // Corrupted red
    mortar:     '#200a12',   // Blood-dark seam
    highlight:  '#ffaa30',   // Cursed gold glow
    floor:      '#3a2028',   // Blood-stained stone
    floorAlt:   '#3d232b',   // Floor variation
    grout:      '#100810',   // Deep ritual gap
  },
  wall: { style: 'blood_stone', ... },
  floor: { style: 'ritual_tile', ... },
  edge: { style: 'blood_seep', intensity: 0.6, width: 4 },
}
```

**New wall style `drawWall_bloodStone`:**
- Dark marble blocks (2×2 grid, similar to carved_stone)
- Red vein lines (1-2 per tile, bezier curves, accent color 0.35 alpha)
- Occasional gold symbol remnant (simple geometric mark in highlight color)
- Deep mortar with faint red glow

**New floor style `drawFloor_ritualTile`:**
- Geometric pentagonal/hexagonal tile pattern (5-sided tiles)
- Thin accent-colored lines at tile borders (ritualistic geometry)
- Center of some tiles: tiny dot (gold highlight, seeded)
- Faint overall dark red wash

### Files Modified / Created

| File | Changes |
|------|---------|
| `tools/theme-designer/src/engine/tilePatterns.js` | Add 6 new draw functions (3 wall + 3 floor) + 3 edge functions |
| `tools/theme-designer/src/engine/themes.js` | Add 3 new theme definitions |
| `tools/theme-designer/src/components/ThemeSelector.jsx` | Handle 11 themes in selector list |
| `client/src/canvas/ThemeEngine.js` | Add all 3 themes + draw functions to BUILT_IN_THEMES |
| `server/configs/themes/fungal_grotto.json` | **NEW** |
| `server/configs/themes/frozen_crypt.json` | **NEW** |
| `server/configs/themes/cursed_shrine.json` | **NEW** |
| `server/app/core/wfc/dungeon_styles.py` | Add theme-to-style affinities for new themes |

### Implementation Steps

1. **Add 3 wall drawing functions** to `tilePatterns.js`
2. **Add 3 floor drawing functions** to `tilePatterns.js`
3. **Add 3 edge drawing functions** to `tilePatterns.js`
4. **Add 3 theme definitions** to `themes.js` (full palette + wall + floor + edge + corridor + fog + ambient + propAffinities)
5. **Add corridor styles** for new themes (reuse closest existing or add new)
6. **Update ThemeSelector** if needed (may auto-pick up new entries)
7. **Mirror to client ThemeEngine** — add themes, draw functions
8. **Create 3 server config JSONs** in `server/configs/themes/`
9. **Update `dungeon_styles.py`** with new theme affinities for floor selection

### Verification

- [ ] All 11 themes visible in Theme Designer selector
- [ ] Fungal Grotto: organic green walls, mycelium floor, spore edges
- [ ] Frozen Crypt: crystalline blue walls, frosted floor, ice edges
- [ ] Cursed Shrine: blood-marble walls, ritual geometry floor, blood seep edges
- [ ] New themes work with all room archetypes
- [ ] Props adapt palette correctly for new themes
- [ ] Each new theme is instantly distinguishable from all others

### Phase 21E — Implementation Log

**Completed:** 2026-03-17

**Files Created (3 files):**

1. **`server/configs/themes/fungal_grotto.json`** — Full theme config: palette (deep green/bioluminescent), wall `fungal_growth`, floor `mycelium_mat`, corridor `shallow_water` (waterDepth 0.06), edge `spore_creep`, fog `#0a120a`, ambient `#151f12`
2. **`server/configs/themes/frozen_crypt.json`** — Full theme config: palette (ice-blue), wall `ice_crystal`, floor `frozen_stone`, corridor `shallow_water` (waterDepth 0.08), edge `frost_creep`, fog `#08101a`, ambient `#121e2e`
3. **`server/configs/themes/cursed_shrine.json`** — Full theme config: palette (crimson/gold), wall `blood_stone`, floor `ritual_tile`, corridor `worn_carpet` (carpetColor `#3a1520`), edge `blood_seep`, fog `#140a0e`, ambient `#1e1218`

**Files Modified (4 files):**

1. **`tools/theme-designer/src/engine/tilePatterns.js`**
   - Added 3 wall drawing functions:
     - `drawWall_fungalGrowth()` — organic overlapping ellipses, 2-3 bioluminescent dots (accent glow), thin tendril lines from top/bottom
     - `drawWall_iceCrystal()` — 3-4 angular polygon crystal facets in varied blue-grey shades, bright highlight refraction on 1 facet, white frost seam lines
     - `drawWall_bloodStone()` — 2×2 marble blocks, 1-2 red bezier vein lines (accent 0.35 alpha), gold diamond symbol remnants (highlight), red-glow mortar
   - Added 3 floor drawing functions:
     - `drawFloor_myceliumMat()` — dark green-brown base, 2-3 branching quadratic mycelium lines with forks, faint spore dots (1px, 0.2 alpha)
     - `drawFloor_frozenStone()` — 2×2 slab grid, frost film overlay (rgba 200,220,255,0.04), 1-2 crystal glint dots, thin ice crack lines
     - `drawFloor_ritualTile()` — 3×3 geometric grid with diagonal alternating line pattern, gold center dots (seeded), accent border lines at tile edges
   - Added 3 edge drawing functions:
     - `drawEdge_sporeCreep()` — quadratic tendril curves growing from wall edge, spore dots scattered along edge
     - `drawEdge_frostCreep()` — white-blue gradient fade from wall, crystal dots, frost boundary line
     - `drawEdge_bloodSeep()` — red gradient bleeding from wall edge, thin drip lines
   - Updated `WALL_DRAW_MAP` — added `fungal_growth`, `ice_crystal`, `blood_stone` (now 11 entries)
   - Updated `FLOOR_DRAW_MAP` — added `mycelium_mat`, `frozen_stone`, `ritual_tile` (now 11 entries)
   - Updated `EDGE_DRAW_MAP` — added `spore_creep`, `frost_creep`, `blood_seep` (now 11 entries)

2. **`tools/theme-designer/src/engine/themes.js`**
   - Added 3 new theme definitions (full palette + wall + floor + corridor + fog + ambient + details + edge + propAffinities):
     - `fungal_grotto` — edge: `{ style: 'spore_creep', intensity: 0.7, width: 5 }`, corridor: `shallow_water` (waterDepth 0.06), propAffinities: puddle 0.8, rubble 0.5 high
     - `frozen_crypt` — edge: `{ style: 'frost_creep', intensity: 0.8, width: 6 }`, corridor: `shallow_water` (waterDepth 0.08), propAffinities: pillar 0.7, chains 0.6 high
     - `cursed_shrine` — edge: `{ style: 'blood_seep', intensity: 0.6, width: 4 }`, corridor: `worn_carpet` (carpetColor red), propAffinities: altar 1.0, banner 0.9, brazier 0.8 high
   - `getTheme()`, `getThemeIds()`, `getThemeSummaries()` are dynamic — auto-include new themes, no manual updates needed

3. **`client/src/canvas/ThemeEngine.js`**
   - Added 3 new entries to `BUILT_IN_THEMES` (compact inline format matching existing entries)
   - Added 3 wall drawing functions: `drawWall_fungalGrowth`, `drawWall_iceCrystal`, `drawWall_bloodStone` (compact client format)
   - Added 3 floor drawing functions: `drawFloor_myceliumMat`, `drawFloor_frozenStone`, `drawFloor_ritualTile`
   - Added 3 edge drawing functions: `drawEdge_sporeCreep`, `drawEdge_frostCreep`, `drawEdge_bloodSeep`
   - Updated `WALL_FN` dispatch map — added `fungal_growth`, `ice_crystal`, `blood_stone` (now 11 entries)
   - Updated `FLOOR_FN` dispatch map — added `mycelium_mat`, `frozen_stone`, `ritual_tile` (now 11 entries)
   - Updated `EDGE_FN` dispatch map — added `spore_creep`, `frost_creep`, `blood_seep` (now 11 entries)

4. **`server/app/core/match_manager.py`**
   - Updated all 4 `DUNGEON_THEMES` lists to include `'fungal_grotto'`, `'frozen_crypt'`, `'cursed_shrine'`:
     - `valid_themes` in config update validation (~line 1294)
     - PVPVE theme selection list (~line 1696)
     - Standard dungeon theme selection list (~line 2045)
     - Static dungeon fallback theme list (~line 2171)

**Files Verified (no changes needed):**
- `tools/theme-designer/src/components/ThemeSelector.jsx` — uses `getThemeSummaries()` dynamically, auto-picks up new themes
- `server/app/core/wfc/dungeon_styles.py` — contains room layout styles only, no theme ID references; no changes needed

**Architecture Notes:**
- All 9 new drawing functions follow the established signatures: wall/floor `(ctx, x, y, size, seed, palette, params)`, edge `(ctx, x, y, size, side, seed, palette, edgeConfig)`
- All functions use `cellHash()` for deterministic seeding — same position always produces same visual
- No new dependencies or utility functions were added — all existing utilities (cellHash, varyColor, shiftColor, hexAlpha, lerpColor, hexToRgb, rgbToCSS) were sufficient
- Client ThemeEngine mirrors use compact/minified format consistent with existing inline functions
- Corridor styles reuse existing patterns: `shallow_water` for Fungal Grotto and Frozen Crypt, `worn_carpet` for Cursed Shrine
- Theme assignment in match_manager.py uses `random.Random(seed).choice()` — new themes added to all 4 selection pools for even distribution
- All 265 server tests pass with 0 failures after changes

### Post-21E Coverage Matrix

| Theme | Wall Style | Floor Style | Edge Style | Unique? |
|-------|-----------|-------------|------------|---------|
| Bleeding Catacombs | `cracked_stone` | `flagstone` | `crumble` | ✅ |
| Ashen Undercroft | `scorched_brick` | `ash_covered` | `scorch` | ✅ |
| Drowned Sanctum | `mossy_stone` | `flooded` | `moss_creep` | ✅ |
| Hollowed Cathedral | `carved_stone` | `cracked_marble` | `rubble_strip` | ✅ |
| Iron Depths | `iron_plate` | `metal_grate` | `rust_drip` | ✅ |
| Forgotten Cellar | `rough_hewn` | `packed_earth` | `dust_drift` | ✅ |
| Pale Ossuary | `bone_stack` | `polished_slab` | `clean_edge` | ✅ |
| Silent Vault | `ashlar_block` | `dusty_tile` | `seam_line` | ✅ |
| Fungal Grotto | `fungal_growth` | `mycelium_mat` | `spore_creep` | ✅ NEW |
| Frozen Crypt | `ice_crystal` | `frozen_stone` | `frost_creep` | ✅ NEW |
| Cursed Shrine | `blood_stone` | `ritual_tile` | `blood_seep` | ✅ NEW |

---

## Phase 21F — Client ThemeEngine Sync + Server Config Export

**Goal:** Ensure all Phase 21 additions are fully mirrored from the Theme Designer tool into the game client's `ThemeEngine.js` and server config JSONs.

### Sync Checklist

The Theme Designer tool (`tools/theme-designer/`) is the authoring environment. The game client (`client/src/canvas/ThemeEngine.js`) must have identical copies of:

| Component | Source (Tool) | Target (Client) |
|-----------|--------------|-----------------|
| Theme definitions | `themes.js` | `BUILT_IN_THEMES` in ThemeEngine.js |
| Wall drawing functions | `tilePatterns.js` | ThemeEngine.js wall section |
| Floor drawing functions | `tilePatterns.js` | ThemeEngine.js floor section |
| Edge drawing functions | `tilePatterns.js` | ThemeEngine.js edge section |
| Prop drawing functions | `tileProps.js` | `TileProps.js` (new file) |
| Noise/color utilities | `noiseUtils.js` | ThemeEngine.js utility section |

### Server Config Sync

Each theme must have a matching JSON in `server/configs/themes/`:
- Used by the server to assign themes to dungeon floors
- Must match the theme ID and contain palette + wall + floor + fog + ambient

### Integration Points in Game Client

| File | What to update |
|------|---------------|
| `client/src/canvas/ThemeEngine.js` | All new wall/floor/edge/prop draw functions + 11 theme defs |
| `client/src/canvas/TileProps.js` | **NEW** — copy of tileProps.js |
| `client/src/canvas/dungeonRenderer.js` | Pass neighbor tile info for edge rendering |
| `server/app/core/wfc/dungeon_generator.py` | Add theme assignment for new themes to floor pools |
| `server/app/core/wfc/dungeon_styles.py` | New theme affinities in floor selection pools |

### Implementation Steps

1. **Copy all new `tilePatterns.js` functions** into ThemeEngine.js (adapting imports to use local utils)
2. **Copy all BUILT_IN_THEMES** updates into ThemeEngine.js
3. **Create `client/src/canvas/TileProps.js`** mirroring `tileProps.js`
4. **Update `dungeonRenderer.js`** to pass tile neighbor data for edge rendering
5. **Update `dungeon_styles.py`** — add new themes to `FLOOR_STYLE_POOLS`
6. **Export all 11 theme JSONs** to `server/configs/themes/`
7. **Test in-game** — launch dungeon, verify all themes render correctly

### Verification

- [ ] Launch game (`start-game.bat`), enter dungeon
- [ ] Confirm themed tiles render in-game (not flat color fallback)
- [ ] Confirm edge effects visible at wall boundaries in-game
- [ ] Confirm props render in rooms in-game
- [ ] All 11 themes available for floor assignment
- [ ] No console errors from ThemeEngine
- [ ] Performance acceptable (FPS stays above 30 on typical dungeon)

### Phase 21F — Implementation Log

**Completed:** 2025-06-25

#### Audit Results

Full sync audit of all Phase 21 components between the Theme Designer tool and the game client/server:

| Component | Tool Source | Client Target | Status |
|-----------|-----------|--------------|--------|
| Wall draw functions (11) | `tilePatterns.js` | `ThemeEngine.js` WALL_FN | ✅ In sync |
| Floor draw functions (11) | `tilePatterns.js` | `ThemeEngine.js` FLOOR_FN | ✅ In sync |
| Edge draw functions (11) | `tilePatterns.js` | `ThemeEngine.js` EDGE_FN | ✅ In sync |
| Prop draw functions (10) | `tileProps.js` | `TileProps.js` | ✅ In sync |
| Theme definitions (11) | `themes.js` | `ThemeEngine.js` BUILT_IN_THEMES | ✅ In sync |
| Server config JSONs (11) | — | `server/configs/themes/` | ✅ All present |
| Room archetypes (10) | `tileProps.js` | `TileProps.js` ARCHETYPE_PROP_SLOTS | ❌ **4 missing** → Fixed |
| Edge rendering in game | `drawEdge()` ready | `dungeonRenderer.js` | ❌ **Not called** → Fixed |
| Room props rendering in game | `drawRoomProps()` ready | `dungeonRenderer.js` | ❌ **Not called** → Fixed |
| Room data pipeline (server→client) | — | match_start / floor_advance payloads | ❌ **Missing** → Created |

#### Gaps Found & Fixed

##### 1. Missing Archetypes in Client TileProps.js

**Problem:** Phase 21C added 4 new room archetypes (shrine, library, prison, flooded) to the tool's `tileProps.js` but they were never synced to the client's `TileProps.js`. The `ARCHETYPE_PROP_SLOTS` map only had 6 entries instead of 10.

**Fix:** Added the 4 missing archetype entries to `ARCHETYPE_PROP_SLOTS` in `client/src/canvas/TileProps.js`:
- `shrine` — altar(center), brazier(corners), banner(edges)
- `library` — bookshelf(edges), pillar(corners), brazier(center)
- `prison` — chains(edges), barrel(corners), pillar(center)
- `flooded` — puddle(center), rubble(corners), barrel(edges)

##### 2. Room Archetype Identity Lost in Map Exporter

**Problem:** `map_exporter.py` detected room `purpose` from tile content (B→boss, E→enemy, X→loot, T→stairs), but the room_decorator's `assignedRole` (shrine, library, prison, flooded) was not propagated. A shrine room with a chest would incorrectly export as "loot"; a prison room with enemies would export as "enemy".

**Fix:** Built an `_archetype_lookup` dict from `decoration_result["decoratedRooms"]`, mapping `(gridRow, gridCol)` → `assignedRole`. Each exported room now includes an `archetype` field that preserves the decorator's intent, falling back to the content-detected `purpose` for non-specialty rooms.

##### 3. No Room Data Sent to Client

**Problem:** The client had zero knowledge of rooms, archetypes, or room bounds. `get_dungeon_state()` only sent door/chest/ground_item states. The match_start and floor_advance payloads included tiles, tile_legend, and theme_id, but no room geometry.

**Fix:** Created the full server→client room data pipeline:
- `match_manager.py` `get_match_start_payload()`: Added `dungeon_rooms` — lightweight list with `archetype` + `bounds` per room
- `match_manager.py` `advance_floor()`: Added `dungeon_rooms` to floor advance return dict
- `tick_loop.py`: Added `dungeon_rooms` to the `floor_advance` WebSocket payload
- `combatReducer.js`: Stores `dungeonRooms` from both `MATCH_START` and `FLOOR_ADVANCE` actions
- `Arena.jsx`: Destructures `dungeonRooms` from gameState and passes through renderParamsRef
- `ArenaRenderer.js`: Accepts `dungeonRooms` parameter and forwards to `drawDungeonTiles()`

##### 4. Edge Rendering Not Integrated in Game Client

**Problem:** `ThemeEngine.drawEdge()` existed and was fully functional (all 11 edge styles), but `dungeonRenderer.js` never called it. Edge effects (moss creep, blood seep, frost, etc.) were invisible in actual gameplay.

**Fix:** Added an edge rendering pass to `drawDungeonTiles()` in `dungeonRenderer.js`. After the main tile draw loop, iterates all floor tiles, checks cardinal neighbors for walls using a `_type()` helper, and calls `themeEngine.drawEdge(ctx, px, py, TILE, seed, side)` for each floor-to-wall adjacency.

##### 5. Room Props Rendering Not Integrated in Game Client

**Problem:** `TileProps.drawRoomProps()` existed with all 10 prop draw functions and the archetype→prop affinity system, but was never called from `dungeonRenderer.js`. Procedural props (pillars, braziers, bookshelves, etc.) were invisible in gameplay.

**Fix:** Added a room props pass to `drawDungeonTiles()`. After edge rendering, iterates `dungeonRooms`, and for each room with a recognized archetype, calls `drawRoomProps()` with the archetype, theme, and room bounds (converted from tile coordinates to pixel coordinates).

##### 6. WFC Test Suite Updated for Phase 21C Archetypes

**Problem:** 5 WFC tests failed because they predated Phase 21C's specialty archetypes. Tests assumed the only non-reserved roles were `enemy`, `loot`, and `empty`, but `shrine`, `library`, `prison`, and `flooded` now exist in the role pool.

**Fix:** Updated 3 test files:
- `test_wfc_cluster_smoothing.py`: Added 4 new roles to `expected_roles` set
- `test_wfc_proximity.py`: Added non-combat specialty roles to safe-zone allowed set; subtracted specialty rooms from `remaining` in quota calculations
- `test_wfc_room_quota.py`: Subtracted specialty rooms from `remaining` in quota tolerance checks; included specialty count in total validation

**Files Modified (11 files):**

| File | Changes |
|------|---------|
| `client/src/canvas/TileProps.js` | Added 4 missing ARCHETYPE_PROP_SLOTS entries (shrine, library, prison, flooded) |
| `client/src/canvas/dungeonRenderer.js` | Added drawRoomProps import; updated drawDungeonTiles signature for dungeonRooms; added _type() helper; added edge rendering pass; added room props pass |
| `client/src/canvas/ArenaRenderer.js` | Added dungeonRooms parameter to renderFrame(); passes to drawDungeonTiles() |
| `client/src/components/Arena/Arena.jsx` | Destructures dungeonRooms from gameState; includes in renderParamsRef |
| `client/src/context/reducers/combatReducer.js` | Stores dungeonRooms from MATCH_START and FLOOR_ADVANCE payloads |
| `server/app/core/wfc/map_exporter.py` | Builds _archetype_lookup from decoration_result; adds archetype field to exported rooms |
| `server/app/core/match_manager.py` | Adds dungeon_rooms to match_start payload and advance_floor return |
| `server/app/services/tick_loop.py` | Adds dungeon_rooms to floor_advance WebSocket broadcast |
| `server/tests/test_wfc_cluster_smoothing.py` | Added shrine/library/prison/flooded to expected_roles |
| `server/tests/test_wfc_proximity.py` | Updated safe-zone and quota tests for specialty archetypes |
| `server/tests/test_wfc_room_quota.py` | Updated quota tolerance and total validation for specialty archetypes |

**Test Results:**
- 508 WFC/dungeon-related tests: ✅ All passing
- 1780 total server tests: ✅ All passing (1 pre-existing unrelated Bloodpact failure)
- 0 client-side lint/compile errors across all modified files

**Architecture Notes:**
- Room data flows: `dungeon_generator` → `room_decorator` (assigns roles) → `map_exporter` (preserves archetype) → `match_manager` (builds payload) → WebSocket → `combatReducer` (stores state) → `Arena` → `ArenaRenderer` → `dungeonRenderer` (renders edges + props)
- `dungeon_rooms` payload is lightweight: `[{archetype, bounds}]` — no tile data, no enemy lists
- Edge rendering uses `_type()` helper for O(1) neighbor lookups via `tileLegend` inversion
- All rendering remains deterministic via `cellHash()` seeding — same dungeon always looks the same

---

## Summary: Full Phase 21 Roadmap

| Phase | Title | New Files | Modified Files | Key Additions |
|-------|-------|-----------|---------------|---------------|
| **21A** | Unique Wall & Floor Styles | 0 | 6 | 3 wall funcs + 3 floor funcs, fix 3 theme reuse |
| **21B** | Procedural Floor Props | 2 | 4 | 10 prop draw funcs, prop placement system |
| **21C** | New Room Archetypes | 0 | 4 | 4 new archetypes (shrine, library, prison, flooded) |
| **21D** | Wall-Edge Transitions | 0 | 4 | 8 edge style funcs, neighbor-aware edge pass |
| **21E** | New Themes (3 biomes) | 3 | 5 | Fungal Grotto, Frozen Crypt, Cursed Shrine |
| **21F** | Client Sync & Export | 0 | 11 | Fix 4 archetype gaps, room data pipeline, edge + prop rendering integration, 5 test fixes |

### Dependency Graph

```
21A ─────────────────────────────────→ 21F
  ↘                                   ↗
   21B → 21C ────────────────────────→
                                    ↗
21D ────────────────────────────────
  ↘                               ↗
   21E ──────────────────────────→
```

- **21A** is standalone — can be done first (fixes reuse problem)
- **21B** depends on nothing but 21A is recommended first (themes need unique styles before adding props)
- **21C** depends on **21B** (uses prop system)
- **21D** is standalone (can run in parallel with 21B/21C)
- **21E** depends on **21A** + **21D** (new themes need unique styles + edge support)
- **21F** is the final sync — depends on everything else being done

---

## Object Color Contrast Polish (Post-21E)

### Problem

All decorative dungeon objects (pillars, braziers, bookshelves, barrels, coffins, altars, chains, banners) drew their colors from `palette.secondary` — the same color used for walls. This made props visually blend into the background, reducing readability and atmosphere. Objects that should look like wood, iron, or brass appeared as the same stone as the surrounding walls.

Treasure chests were unaffected (they use a separate color source).

### Solution

Added two new palette colors to all 11 themes:

| Color | Purpose | Used By |
|-------|---------|---------|
| `furniture` | Warm wood/organic tones for wooden objects | Bookshelves, coffins, altars, barrels (body) |
| `metal` | Metallic/structural tones for metal objects | Pillars, braziers (bowl), chains, barrel bands, banner rods, weapon racks, iron bars |

All prop drawing functions include a `|| palette.secondary` fallback so any custom or legacy themes without the new colors still render correctly.

### Palette Colors Per Theme

| Theme | Furniture | Metal | Flavor |
|-------|-----------|-------|--------|
| Bleeding Catacombs | `#4a3520` | `#6a5540` | Dark rotting wood / tarnished bronze |
| Ashen Undercroft | `#3a2a1a` | `#5a5048` | Charred wood / heat-blackened iron |
| Drowned Sanctum | `#3a4a3a` | `#4a5a55` | Waterlogged wood / corroded verdigris |
| Hollowed Cathedral | `#4a3830` | `#7a6a48` | Old dark oak / old brass |
| Iron Depths | `#3a3028` | `#6a6a72` | Oil-stained wood / dull iron |
| Forgotten Cellar | `#5a4a35` | `#5a4a3a` | Rough pine / rusty iron |
| Pale Ossuary | `#4a4540` | `#6a6570` | Bleached wood / silver-grey |
| Silent Vault | `#3a3040` | `#5a6068` | Dark mahogany / cold blued steel |
| Fungal Grotto | `#3a4520` | `#4a6a45` | Fungus-covered wood / corroded copper |
| Frozen Crypt | `#4a4848` | `#6a7a88` | Frost-pale birch / frost-covered steel |
| Cursed Shrine | `#4a2520` | `#5a3a38` | Blood-stained wood / dark iron red patina |

### Files Modified

| File | Changes |
|------|---------|
| `tools/theme-designer/src/engine/themes.js` | Added `furniture` and `metal` to all 11 palette definitions |
| `tools/theme-designer/src/engine/tileProps.js` | Updated ~8 prop draw functions to use `palette.furniture` / `palette.metal` with fallback |
| `tools/theme-designer/src/engine/roomArchetypes.js` | Updated ~14 overlay color references (boss pillars, weapon racks, shrine altar, library shelves, prison chains/bars) |
| `client/src/canvas/ThemeEngine.js` | Added `furniture` and `metal` to all 11 `BUILT_IN_THEMES` palette entries |
| `client/src/canvas/TileProps.js` | Mirrored all tileProps.js prop function changes |
| `server/configs/themes/*.json` (×11) | Added `furniture` and `metal` to each theme's palette block |

### Prop Color Assignments

| Prop | Before | After |
|------|--------|-------|
| Pillar | `palette.secondary` | `palette.metal` |
| Brazier (bowl) | `palette.secondary` | `palette.metal` |
| Coffin | `palette.secondary` | `palette.furniture` |
| Bookshelf | `palette.secondary` | `palette.furniture` |
| Altar (body) | `palette.secondary` | `palette.furniture` |
| Barrel (body) | `palette.secondary` | `palette.furniture` |
| Barrel (bands) | `palette.secondary` | `palette.metal` |
| Chains | `palette.secondary` | `palette.metal` |
| Banner (rod) | `palette.secondary` | `palette.metal` |
| Rubble | `palette.secondary` | Unchanged (stone debris stays wall-colored) |
| Puddle | Hardcoded blue | Unchanged |
| Banner (fabric) | `palette.accent` | Unchanged |

### Architecture Notes

- All changes use `palette.furniture || palette.secondary` / `palette.metal || palette.secondary` pattern for backward compatibility
- Color shift amounts adjusted: furniture uses smaller shifts (wood grain subtlety), metal uses moderate shifts (structural highlight)
- Room archetype overlays (tool-only, not rendered on client) follow the same pattern
- No new utility functions added — existing `shiftColor()` handles all tinting
- Server JSON configs include the new fields for runtime theme loading

### Recommended Build Order

1. **Phase 21A** — Fix the reuse problem first (highest clarity impact)
2. **Phase 21D** — Wall-edge transitions (standalone, high visual impact)
3. **Phase 21B** — Floor props system (infrastructure for 21C)
4. **Phase 21C** — New archetypes (uses 21B props)
5. **Phase 21E** — New themes (uses 21A styles + 21D edges)
6. **Phase 21F** — Final client sync & server export

---

## Pre-21F Visual Polish Pass

**Completed:** 2026-03-16

A set of visual polish fixes applied before Phase 21F sync to address issues spotted during visual review of the Theme Designer.

### Issues Fixed

#### 1. Thick Floor Grout Lines Removed (Iron Depths, Pale Ossuary, Silent Vault, Frozen Crypt)

**Problem:** Four themes had very visible dark grout lines between floor tiles, creating an unintended checkerboard pattern.

**Root cause per theme:**
- **Iron Depths (`metal_grate`):** Entire tile was pre-filled with `palette.grout` (#0a0a10, near-black), then floor color drawn inset by `groutWidth=2` — creating a 4px dark gap between adjacent tiles.
- **Pale Ossuary (`polished_slab`):** Grout lines drawn at `hexAlpha(palette.grout, 0.3)` — too visible between the 2×2 slab grid.
- **Silent Vault (`dusty_tile`):** Grout lines drawn at **full opacity** `palette.grout` — very dark 1px lines across the 3×3 grid.
- **Frozen Crypt (`frozen_stone`):** Same as Silent Vault — full opacity grout lines across the 2×2 slab grid.

**Fix applied:**
- **`metal_grate`:** Removed the dark background fill entirely. Floor now fills edge-to-edge. Crosshatch grate lines draw across the full tile (no inset). Outer frame replaced with a subtle 0.15-alpha hairline stroke instead of a 1px solid border.
- **`polished_slab`:** Reduced grout alpha from `0.3` → `0.08` and changed from `groutWidth`-thick lines to 1px hairlines at slab boundaries.
- **`dusty_tile`:** Completely removed the grout line rendering. The per-tile color variation and dust film provide sufficient visual separation.
- **`frozen_stone`:** Completely removed the grout line rendering. The frost overlay and crystal glints provide floor character without grid lines.

**Files modified (2):**
- `tools/theme-designer/src/engine/tilePatterns.js` — `drawFloor_metalGrate`, `drawFloor_polishedSlab`, `drawFloor_dustyTile`, `drawFloor_frozenStone`
- `client/src/canvas/ThemeEngine.js` — mirrored all 4 function changes

#### 2. Abandoned Room Floor Crack Removed

**Problem:** The empty/abandoned room archetype (`_drawEmptyOverlay`) drew two diagonal lines across the floor meant to represent cracks, which formed a Y-shaped black mark in the center of the room. It was off-putting and didn't read as a crack.

**Fix applied:** Removed the entire "Wider floor cracks" section (both crack lines). The abandoned room retains its dark wash, corner rubble piles, and darkened wall edges — all of which provide sufficient atmosphere without the distracting Y-line.

**Files modified (1):**
- `tools/theme-designer/src/engine/roomArchetypes.js` — `_drawEmptyOverlay` section 3 removed

#### 3. Flooded Room Visibility Improved

**Problem:** The flooded room archetype overlay was nearly invisible because the water tint (`rgba(10,30,50,0.08)`) was too close in color and opacity to the base floor tiles. Puddles were too small and faint.

**Fix applied:**
- Water tint now uses the theme's accent color (clamped to blue-green range) at 0.18 opacity, plus a second blue-green wash at 0.12 — making the water clearly visible regardless of theme.
- Puddle ellipses increased in size (rx +22%, ry +25%) and opacity (0.15 → 0.30). Count increased from 2-4 to 3-5.
- Puddle highlight shimmer increased from 0.12 to 0.25 opacity with brighter blue (120,200,240).
- Wall-edge reflections doubled in opacity (0.04 → 0.08) and widened from 0.3 to 0.4 tile units.
- Ripple arcs increased from 2 to 3 rings with higher opacity (0.08 → 0.18) and extended arc sweep.

**Files modified (1):**
- `tools/theme-designer/src/engine/roomArchetypes.js` — `_drawFloodedOverlay` completely rewritten

#### 4. Stairwell Room Rectangles Removed

**Problem:** The stairs room archetype drew 3 concentric rectangles narrowing toward the center, intended to represent a descending stairwell. In practice, it didn't read as stairs and looked like meaningless nested boxes.

**Fix applied:** Removed the entire "Concentric rectangular borders" section. The stairwell room retains its wall depth streaks and downward darkening gradient, which convey the descending feeling more effectively without the abstract rectangles.

**Files modified (1):**
- `tools/theme-designer/src/engine/roomArchetypes.js` — `_drawStairsOverlay` section 1 removed

---

## Bugfix: Room Props Spawning on Wall Tiles (2026-03-16)

### Problem

Floor props (torches, chains, braziers, coffins, pillars, etc.) were rendering on wall tiles or outside the traversable dungeon area in PVPVE dungeons. Some props appeared to be missing entirely — drawn underneath opaque wall graphics and invisible to the player. This made decoration placement look random or broken compared to the Theme Designer tool, where props rendered correctly.

### Root Cause

The server's `map_exporter.py` exports room bounds as the **full 8×8 WFC module grid** including the 1-tile wall perimeter ring:

```python
# map_exporter.py — room bounds include walls
"bounds": {
    "x_min": start_c,                     # gridCol * 8
    "y_min": start_r,                     # gridRow * 8
    "x_max": start_c + MODULE_SIZE - 1,   # gridCol * 8 + 7
    "y_max": start_r + MODULE_SIZE - 1,   # gridRow * 8 + 7
},
```

The client's `TileProps.js _resolvePosition()` computes prop coordinates directly from these bounds. With wall-inclusive bounds:

- `'corners'` → props at `(x_min, y_min)` etc. — **all 4 are wall tiles**
- `'wall_left'` / `'wall_right'` → props at `x_min` / `x_max` — **wall columns**
- `'wall_top'` / `'wall_bottom'` → props at `y_min` / `y_max` — **wall rows**
- `'random_floor'` → positions span full bounds range, **including walls**

The Theme Designer tool doesn't have this problem because its preview uses hardcoded inner bounds `{x_min: 1, y_min: 1, x_max: 6, y_max: 6}` that already exclude the wall ring.

### Fix Applied

Inset the server-provided bounds by 1 in each direction on the client side before passing to `drawRoomProps()`, so all prop positions fall on floor tiles only:

```javascript
// dungeonRenderer.js — Phase 21F room props rendering pass
const inner = {
  x_min: b.x_min + 1,
  y_min: b.y_min + 1,
  x_max: b.x_max - 1,
  y_max: b.y_max - 1,
};
drawRoomProps(ctx, {
  archetype: room.archetype || 'empty',
  theme: themeEngine.theme,
  tileSize: TILE_SIZE,
  roomOffsetX: gridOffsetX,
  roomOffsetY: gridOffsetY,
  bounds: inner,    // floor-only bounds
  seed: ((b.x_min * 7919) + (b.y_min * 6271)) & 0x7FFFFFFF,
});
```

### Additional Notes

The archetype system itself is fully functional — archetypes flow correctly from `room_decorator.py` → `map_exporter.py` → `match_start` payload → client `combatReducer` → `dungeonRenderer.js` → `drawRoomProps()`. Theme `propAffinities` correctly filter which props appear per biome. The only issue was the bounds mismatch between server (full module) and client expectations (floor-only).

**Files modified (1):**
- `client/src/canvas/dungeonRenderer.js` — inset room bounds by 1 before passing to `drawRoomProps()`

---

## Bugfix: Missing Room Archetype Overlays & Filtered Rooms (2026-03-16)

### Problem

After the bounds fix above, PVPVE dungeons still appeared nearly empty — walking through 10–12 rooms revealed only scattered pillars and single torches, with no floor decorations or the rich archetype-specific visuals (boss sigils, wall torches, weapon racks, water tints, bookshelves, prison chains, etc.) visible in the Theme Designer tool.

### Root Causes

**1. Client only called `drawRoomProps()`, not `drawRoomOverlay()`.**

The Theme Designer renders rooms in two layers:

- `drawRoomProps()` (TileProps.js) — sparse procedural floor objects (2–4 pillar/brazier/coffin per room)
- `drawRoomOverlay()` (roomArchetypes.js) — heavy archetype-specific canvas overlays providing ~90% of visual character: boss corner pillars + center sigil, enemy wall torches with glow halos + weapon racks, loot alcoves + corner filigree, shrine altar + flanking braziers + banners, library wall bookshelves + dust motes, prison chains + iron bar doorways, flooded water tint + puddles + ripple arcs, etc.

The client's `dungeonRenderer.js` only imported and called `drawRoomProps()`. The overlay functions existed solely in the Theme Designer tool and were never ported to the client.

**2. `map_exporter.py` dropped rooms with decorator-assigned specialty archetypes.**

The server filter:
```python
if not has_content and variant.get("purpose") in ("empty", "corridor"):
    continue
```
This ran BEFORE the `_archetype_lookup` check, so rooms with no enemy/boss/spawn/loot/stairs content tiles were skipped — even if `room_decorator.py` had assigned them specialty archetypes like `shrine`, `library`, `prison`, or `flooded`. These rooms' `detected_purpose` was still `"empty"` at that point, so the filter dropped them. The archetype lookup that would have promoted them to their specialty role never executed.

### Fixes Applied

**Fix 1: Port `drawRoomOverlay` to the client.**

Created `client/src/canvas/RoomOverlays.js` — a self-contained client-side mirror of the Theme Designer's `roomArchetypes.js` with all 10 archetype overlay functions:

| Archetype | Overlay visuals |
|-----------|----------------|
| `boss` | Corner pillars, center sigil (circle + diamond), highlight wash, wall trim |
| `enemy` | Paired wall torches with glow halos, weapon rack brackets, worn door paths |
| `loot` | Polished floor sheen, wall alcoves, corner filigree, floor border |
| `spawn` | Warm tint, archway columns flanking doors, arrival circle |
| `empty` | Dark wash, corner rubble piles, darkened wall edges |
| `stairs` | Vertical wall streaks, downward darkening gradient |
| `shrine` | Altar with accent, flanking braziers with glow, accent floor border, wall banners |
| `library` | Wall bookshelves on all 4 walls (via helper), dust motes |
| `prison` | Dark wash, corner vignette, wall chains, iron bar doorway overlay |
| `flooded` | Water tint (accent-based), puddle ellipses, reflective edge highlights, ripple arcs |

`drawRoomOverlay()` calls `drawRoomProps()` internally first, then applies the archetype-specific overlay on top. Updated `dungeonRenderer.js` to import `drawRoomOverlay` from `RoomOverlays.js` instead of `drawRoomProps` from `TileProps.js`.

**Fix 2: Reorder `map_exporter.py` filter to preserve decorator-assigned archetypes.**

Moved the `_archetype_lookup` check BEFORE the filter, so rooms with specialty archetypes assigned by `room_decorator.py` are preserved even when they have no content tiles:

```python
# BEFORE (broken): archetype lookup happened after filter — never reached
if not has_content and variant.get("purpose") in ("empty", "corridor"):
    continue
archetype = _archetype_lookup.get(_dec_key, detected_purpose)

# AFTER (fixed): lookup first, only skip if archetype matches raw purpose
archetype = _archetype_lookup.get(_dec_key, detected_purpose)
if not has_content and variant.get("purpose") in ("empty", "corridor"):
    if archetype == detected_purpose:
        continue
```

Rooms where the decorator assigned a specialty archetype (e.g., `shrine` instead of `empty`) now survive the filter and render with their full overlay visuals.

**Files created (1):**
- `client/src/canvas/RoomOverlays.js` — all 10 archetype overlay functions + utility helpers

**Files modified (2):**
- `client/src/canvas/dungeonRenderer.js` — import `drawRoomOverlay` from `RoomOverlays.js`, call it instead of `drawRoomProps`
- `server/app/core/wfc/map_exporter.py` — reordered filter to check `_archetype_lookup` first, preserving decorator-assigned specialty rooms
