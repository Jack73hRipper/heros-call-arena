# PVPVE Dungeon Preview — Implementation Plan

> Add a live WFC-generated PVPVE dungeon preview to the Theme Designer tool
> so designers can see exactly how props, rooms, modules, and archetypes
> compose in a real PVPVE layout with the selected theme applied.

---

## Implementation Progress

| Step | Status | Date | Notes |
|------|--------|------|-------|
| 1 — Vite Alias | **DONE** | 2026-03-28 | Added `@wfc` and `@wfc-utils` aliases to `tools/theme-designer/vite.config.js`. Also added `import path from 'path'`. Aliases resolve to `../dungeon-wfc/src/engine` and `../dungeon-wfc/src/utils`. Relative imports inside WFC engine files (e.g. `../utils/tileColors.js`) resolve correctly via Vite's file-based resolution. |
| 2 — PVPVE Decorator | **DONE** | 2026-03-28 | Created `tools/theme-designer/src/engine/pvpveDecorator.js` (880 lines). Full port of Python PVPVE logic from `server/app/core/wfc/room_decorator.py` (corner spawns, center boss, difficulty tiers, proximity ramp, quota deck dealing, cluster smoothing, archetype carve-outs) AND `server/app/core/wfc/door_placer.py` (boundary scanning, door chance rules, wall+door insertion). Single export: `applyPvpveLayout()`. |
| 3 — PVPVE Generator | **DONE** | 2026-03-28 | Created `tools/theme-designer/src/engine/pvpveGenerator.js` (~140 lines). Single export `generatePvpveDungeon({ seed, gridRows, gridCols, teamCount })`. Pipeline: WFC → decorateRooms (PVPVE-tuned settings) → applyPvpveLayout → computeStats. Input clamping (rows/cols 3-8, teams 2-4, seed 0-999999). Returns `{ success, tileMap, rooms, doors, spawnZones, bossRoom, difficultyTiers, stats, gridRows, gridCols }`. Also exports `GRID_SIZE_PRESETS` and `TEAM_COUNT_OPTIONS` for toolbar use. Vite build verified — all imports resolve through `@wfc` alias. |
| 4 — PvpvePreview Component | **DONE** | 2026-03-28 | Created `tools/theme-designer/src/components/PvpvePreview.jsx` (~340 lines). Canvas-based preview modeled on `DungeonPreview.jsx`. Props: `{ themeId, gridRows, gridCols, teamCount, seed }`. Generates dungeon via `generatePvpveDungeon()` (memoized on config change). 8 render layers: (1) base tiles via `ThemeRenderer` with extended `PVPVE_TILE_LEGEND` mapping E/B→floor, (2) room archetype overlays via `drawRoomOverlay()`, (3) module grid dashed lines at `MODULE_SIZE` intervals (toggleable), (4) team spawn zone highlights with colored fills/strokes and team labels (toggleable), (5) boss room gold glow border + ★ BOSS ★ label (toggleable), (6) difficulty tier color tinting per room (toggleable), (7) room labels with role+archetype in background pills (toggleable, visible at zoom ≥ 0.8), (8) hover highlight. Enemy markers drawn as red diamonds, boss markers as gold diamonds with crown points. Overlay toggle panel with 5 checkboxes (Module Grid, Spawn Zones, Boss Highlight on by default; Difficulty Tiers, Room Labels off). Extended hover info shows grid position, tile type, module cell, room role/archetype/tier/team/enemy count. Stats bar shows room/door/spawn counts. Error state displays fallback message when WFC fails. Zoom range 0.3×–2.0× (default 0.6× for large maps). Room lookup built via useMemo for O(1) hover resolution. Added CSS: `.pvpve-overlay-toggles`, `.pvpve-stats`, `.pvpve-error` classes in `theme-designer.css`. Vite build verified — 45 modules, 0 errors. |
| 5 — Toolbar Controls | **DONE** | 2026-03-28 | Added PVPVE Dungeon view mode button + PVPVE-specific controls to `Toolbar.jsx`. New props: `pvpveConfig`, `onPvpveConfigChange`. Controls: Grid Size dropdown (3×3 through 8×8, imported from `GRID_SIZE_PRESETS`), Team Count dropdown (2/3/4, imported from `TEAM_COUNT_OPTIONS`), Seed text input (0-999999, numeric only), 🎲 Randomize button (generates random seed), ⟳ Regenerate button (bumps `_regen` counter to force re-render, shows "Generating..." for 300ms). Sample Map dropdown now only visible in `viewMode === 'dungeon'` (was previously shown for all non-archetype/non-object modes). Added `.toolbar-pvpve-controls`, `.toolbar-input`, `.regenerate-btn` CSS classes. Vite build verified — 53 modules, 0 errors. |
| 6 — App.jsx Integration | **DONE** | 2026-03-28 | Added `pvpveConfig` state with `_regen` counter, imported `PvpvePreview`, wired `pvpveConfig`/`onPvpveConfigChange` props to Toolbar, added `'pvpve'` branch to conditional render. Passes `_regen` as prop to force re-generation. Vite build verified — 54 modules, 0 errors. |
| 7 — Tile Legend Extension | **DONE** | 2026-03-28 | Added `'E': 'floor'` and `'B': 'floor'` to `TILE_LEGEND` in `sampleMaps.js`. Updated JSDoc comment to document both new tile chars. Enemy/boss tiles render as floor; overlay markers handle visual distinction. Vite build verified — 54 modules, 0 errors. |

### Step 2 — Implementation Details

The `pvpveDecorator.js` module contains the complete PVPVE pipeline in a single file:

**Ported from `room_decorator.py` (PVPVE path):**
- `assignCornerSpawns()` — Manhattan-distance nearest-flexible-room to each team corner
- `assignCenterBoss()` — Boss-capable room nearest grid center, with fallback
- `computeProximityRamp()` — Multi-spawn min-distance safety zones (safe ≤1, softened =2)
- `computeDifficultyTier()` — Distance-to-center tier mapping (boss/elite/hard/normal)
- `getMaxEnemiesForTier()` — Per-tier enemy caps
- Quota deck system with proximity-aware swap (enemy tokens moved from safe → far zones)
- Cluster smoothing (BFS to find adjacent enemy room clusters, downgrade closest-to-spawn)
- Archetype carve-outs (shrine 5%, library 5%)
- Prison override (enemy rooms with ≥3 max enemies, 10% chance)
- Full content tile placement for all roles (boss, spawn, enemy, loot, shrine, library, prison, empty)

**Ported from `door_placer.py`:**
- `scanBoundaries()` — Horizontal + vertical module edge scanning
- `findOpenRuns()` — Contiguous non-wall tile runs
- `getDoorChance()` — Priority rules (spawn=0%, interior=0%, boss=70%, corridor=15%, narrow=55%, default=45%)
- `placeDoorAtOpening()` — Wall separator with centered 1-tile door gap
- `insertRoomDoors()` — Main door pass with seeded RNG

**Output shape matches the plan spec:**
```js
{ tileMap, rooms, doors, spawnZones, bossRoom, difficultyTiers, stats }
```

Each room in `rooms[]` includes: `id, gridRow, gridCol, role, archetype, bounds, team, difficultyTier, enemyCount, chestCount, placements, sourceName, clusterSmoothed, proximityOverride`.

### Step 3 — Implementation Details

The `pvpveGenerator.js` module is the single-entry-point orchestrator (~140 lines):

**Pipeline:**
1. `runWFC()` — Collapses `PRESET_MODULES` onto the requested grid with border walls and connectivity enforcement
2. `decorateRooms()` — Base room decoration with PVPVE-tuned settings (`enemyDensity: 0.50`, `lootDensity: 0.50`, `emptyRoomChance: 0.15`, no stairs)
3. `applyPvpveLayout()` — PVPVE overlay from Step 2 (corner spawns, center boss, difficulty tiers, doors)
4. `computeStats()` — Final tile-level statistics

**Imports:**
- `runWFC`, `computeStats` from `@wfc/wfc.js`
- `PRESET_MODULES` from `@wfc/presets.js`
- `decorateRooms` from `@wfc/roomDecorator.js`
- `applyPvpveLayout` from `./pvpveDecorator.js`

**Exports:**
- `generatePvpveDungeon({ seed, gridRows, gridCols, teamCount })` — main generator
- `GRID_SIZE_PRESETS` — `[{label, rows, cols}]` array for toolbar dropdown (`3×3` through `8×8`)
- `TEAM_COUNT_OPTIONS` — `[2, 3, 4]`

**Input validation:** All inputs are clamped to safe ranges (rows/cols 3-8, teams 2-4, seed 0-999999). On WFC failure, returns `{ success: false, error }` with empty arrays for all collection fields.

**Stats merge:** Final `stats` object includes pvpveDecorator stats + tile census from `computeStats` + `wfcRetries` and `wfcConnectivity` from the WFC run.

**Verified:** Vite build succeeds — all 45 modules transform and bundle without errors.

### Step 4 — Implementation Details

The `PvpvePreview.jsx` component is a canvas-based PVPVE dungeon preview (~340 lines):

**Architecture:**
- Modeled on `DungeonPreview.jsx` pattern (canvas ref, ThemeRenderer, zoom, hover)
- Props: `{ themeId, gridRows, gridCols, teamCount, seed }`
- Dungeon generation memoized via `useMemo` on config change
- Room lookup map built via `useMemo` for O(1) hover resolution

**8 Render Layers (drawn in order):**
1. **Base tiles** — `ThemeRenderer.drawTile()` with extended `PVPVE_TILE_LEGEND` (E→floor, B→floor)
2. **Room archetype overlays** — `drawRoomOverlay()` from `roomArchetypes.js` for each room with archetype
3. **Module grid** — Dashed lines at `MODULE_SIZE` (8-tile) intervals (toggleable, on by default)
4. **Team spawn zones** — Semi-transparent colored rectangles + team labels: A=blue, B=red, C=green, D=yellow (toggleable, on by default)
5. **Boss room highlight** — Gold glow border with `shadowBlur` + ★ BOSS ★ label (toggleable, on by default)
6. **Difficulty tiers** — Color-coded room fills: boss=gold, elite=red, hard=orange, normal=none (toggleable, off by default)
7. **Room labels** — Role + archetype text in background pills, visible at zoom ≥ 0.8 (toggleable, off by default)
8. **Hover highlight** — White stroke on hovered tile

**Tile Markers:**
- `E` tiles → red diamond marker (enemy spawn point)
- `B` tiles → gold diamond with crown points (boss spawn point)

**Overlay Toggle Panel:**
5 checkboxes in a horizontal bar below the zoom controls: Module Grid ☑, Spawn Zones ☑, Boss Highlight ☑, Difficulty Tiers ☐, Room Labels ☐

**Hover Info (extended):**
- Grid position `[x, y]` and tile type/char
- Module cell `[row, col]`
- Room role, archetype, difficulty tier, team assignment, enemy count

**Stats Bar:**
Room count, door count, spawn count, enemy count (from `dungeon.stats`)

**Error State:**
When WFC generation fails, shows centered error message with ⚠ icon, suggestion to try a different seed, and the error message from the generator.

**Zoom:**
Range 0.3× to 2.0×, default 0.6× (appropriate for large WFC maps).

**CSS Added:**
- `.pvpve-overlay-toggles` — Horizontal checkbox strip
- `.pvpve-stats` — Monospace stats display
- `.pvpve-error`, `.pvpve-error-icon`, `.pvpve-error-detail` — Error state styling

**Imports:**
- `ThemeRenderer` from `../engine/themeRenderer.js`
- `TILE_LEGEND` from `../engine/sampleMaps.js`
- `drawRoomOverlay` from `../engine/roomArchetypes.js`
- `getTheme` from `../engine/themes.js`
- `generatePvpveDungeon` from `../engine/pvpveGenerator.js`

**Verified:** Vite build succeeds — 45 modules, 0 errors (component fully bundled).

### Step 5 — Implementation Details

The `Toolbar.jsx` component was updated to include a 4th view mode and PVPVE-specific controls (~80 lines added):

**New Props:**
- `pvpveConfig` — `{ gridRows, gridCols, teamCount, seed, _regen }` state object from App.jsx
- `onPvpveConfigChange` — Callback to update PVPVE config state

**New Imports:**
- `useState` from React (for `generating` state)
- `GRID_SIZE_PRESETS`, `TEAM_COUNT_OPTIONS` from `../engine/pvpveGenerator.js`

**View Mode Button:**
4th button added to the `.toolbar-view-toggle` group: "PVPVE Dungeon" (`viewMode === 'pvpve'`), matching existing button styling.

**Conditional Control Display:**
- Sample Map dropdown now only shows when `viewMode === 'dungeon'` (previously showed for all modes except archetypes/objects)
- PVPVE controls only render when `viewMode === 'pvpve'` and `pvpveConfig` exists

**PVPVE Controls (`.toolbar-pvpve-controls` container):**
1. **Grid Size dropdown** — Populated from `GRID_SIZE_PRESETS` (3×3 through 8×8). Changes update `gridRows`/`gridCols` together.
2. **Team Count dropdown** — Populated from `TEAM_COUNT_OPTIONS` (2, 3, 4). Changes update `teamCount`.
3. **Seed text input** — Numeric-only (non-digit chars stripped), clamped 0-999999, `maxLength={6}`, monospace font, 70px width.
4. **🎲 Randomize button** — Generates `Math.floor(Math.random() * 1000000)` and updates seed.
5. **⟳ Regenerate button** — Bumps `pvpveConfig._regen` counter (triggers useMemo re-evaluation in PvpvePreview). Shows "Generating..." for 300ms with `disabled` state.

**CSS Added (in `theme-designer.css`):**
- `.toolbar-pvpve-controls` — Flex row, `gap: 8px`, `margin-left: 12px`
- `.toolbar-input` — Matches `.toolbar-select` styling (bg, border, padding, font-size) with monospace font
- `.toolbar-input:hover`, `.toolbar-input:focus` — Active border color, no outline
- `.regenerate-btn` — Accent color border/text (matches export button style), `white-space: nowrap`
- `.regenerate-btn:hover` — Accent glow background
- `.regenerate-btn:disabled` — `opacity: 0.6`, `cursor: not-allowed`

**Note for Step 6:** App.jsx must pass `pvpveConfig` and `onPvpveConfigChange` props to Toolbar. The `pvpveConfig` state shape expected:
```js
{ gridRows: 6, gridCols: 6, teamCount: 4, seed: 42, _regen: 0 }
```

**Verified:** Vite build succeeds — 53 modules, 0 errors.

### Step 6 — Implementation Details

The `App.jsx` root component was updated to integrate the PVPVE preview mode (~15 lines added):

**New Import:**
- `PvpvePreview` from `./components/PvpvePreview.jsx`

**New State:**
- `pvpveConfig` — `{ gridRows: 6, gridCols: 6, teamCount: 4, seed: 42, _regen: 0 }` via `useState`
- `viewMode` comment updated to include `'pvpve'` as valid mode

**Toolbar Props Added:**
- `pvpveConfig={pvpveConfig}` — Passes config state for PVPVE controls
- `onPvpveConfigChange={setPvpveConfig}` — Toolbar calls this to update grid size, team count, seed, and `_regen` counter

**Conditional Render (4-way):**
1. `viewMode === 'pvpve'` → `<PvpvePreview>` with `themeId`, `gridRows`, `gridCols`, `teamCount`, `seed`, `_regen` props
2. `viewMode === 'archetypes'` → `<RoomArchetypePreview>` (unchanged)
3. `viewMode === 'objects'` → `<ObjectBrowser>` (unchanged)
4. Default (`'dungeon'`) → `<DungeonPreview>` (unchanged)

The `_regen` prop is passed to `PvpvePreview` so the Toolbar's "Regenerate" button (which bumps `_regen`) triggers a `useMemo` re-evaluation even when all other config values remain the same.

**Verified:** Vite build succeeds — 54 modules, 0 errors.

### Step 7 — Implementation Details

The `sampleMaps.js` TILE_LEGEND was extended with two new entries (~4 lines added):

**New Entries:**
- `'E': 'floor'` — Enemy spawn point. Rendered as a floor tile by `ThemeRenderer`; the red diamond enemy marker is drawn by `PvpvePreview`'s overlay layer.
- `'B': 'floor'` — Boss spawn point. Rendered as a floor tile by `ThemeRenderer`; the gold diamond+crown boss marker is drawn by `PvpvePreview`'s overlay layer.

**JSDoc Updated:**
Added `E = enemy spawn` and `B = boss spawn` entries with notes that overlays handle visual markers.

**Design Rationale:**
Mapping E/B → `'floor'` means the base `ThemeRenderer` draws normal floor tiles at these positions, which is correct — the enemy/boss entities don't change the terrain. The `PvpvePreview` component's overlay layer (layer 8 — tile markers) draws distinctive diamond markers on top: red for enemies, gold with crown points for bosses. This separation keeps the theme renderer generic and the PVPVE-specific visuals in the preview component.

**Verified:** Vite build succeeds — 54 modules, 0 errors.

---

## Problem Statement

The Theme Designer's Dungeon Preview currently uses **4 hand-drawn sample maps**
(12-15 tiles wide) defined in `sampleMaps.js`. These bear no resemblance to
actual PVPVE dungeons, which are:

| Aspect | Current Preview | Actual PVPVE Dungeon |
|--------|----------------|---------------------|
| Size | 12-15 tiles | 32-64 tiles (4×4 to 8×8 module grid) |
| Layout | Hand-drawn, arbitrary | WFC-generated from 30+ modular 8×8 tiles |
| Rooms | No real room structure | Distinct 8×8 module rooms with assigned purposes |
| Spawns | Scattered `S` tiles | 2-4 corner team spawn zones |
| Boss | None or single chest | Center boss arena with guards + chests |
| Doors | A few placed manually | Auto-placed at module boundaries |
| Difficulty | None | Tiered by distance from center |
| Corridors | Simple 1-wide paths | Standard / narrow / interior socket corridors |
| Archetypes | Not data-driven | Shrine, library, prison, armory, ossuary, etc. |

The preview gives no sense of how props, rooms, and modules actually compose.

---

## Solution Overview

Import the existing **JS-side WFC engine** from `tools/dungeon-wfc/src/engine/`
into the Theme Designer, add a PVPVE room decoration + door placement pass,
and wire it into a new "PVPVE Dungeon" preview mode alongside the existing
sample maps.

### Key Advantage

The `tools/dungeon-wfc/` JS engine is the **original source** that the Python
server was ported from. Same algorithm, same modules, same sockets = identical
layout structure to what the game produces.

---

## Architecture

### Existing Code We Reuse (No Changes)

| File | Location | What It Provides |
|------|----------|-----------------|
| `wfc.js` | `tools/dungeon-wfc/src/engine/` | `runWFC({ modules, gridRows, gridCols, seed, ... })` → `{ tileMap, grid, variants }` |
| `presets.js` | `tools/dungeon-wfc/src/engine/` | `PRESET_MODULES` array (30+ modules, 8×8 tiles each) |
| `moduleUtils.js` | `tools/dungeon-wfc/src/engine/` | `expandModules()`, `MODULE_SIZE = 8`, rotation helpers |
| `connectivity.js` | `tools/dungeon-wfc/src/engine/` | `ensureConnectivity(tileMap)` — corridor carving |
| `roomDecorator.js` | `tools/dungeon-wfc/src/engine/` | `decorateRooms({ grid, variants, tileMap, seed, settings })` → rooms with roles |

### New Code We Write

| File | Location | Purpose |
|------|----------|---------|
| `pvpveDecorator.js` | `tools/theme-designer/src/engine/` | PVPVE-specific room assignment (corner spawns, center boss, difficulty tiers, door placement) |
| `pvpveGenerator.js` | `tools/theme-designer/src/engine/` | Orchestrator: WFC → decorate → doors → export to preview format |
| `PvpvePreview.jsx` | `tools/theme-designer/src/components/` | New center panel component for PVPVE preview with overlays |

### Modified Files

| File | Change |
|------|--------|
| `App.jsx` | Add `'pvpve'` view mode, render `PvpvePreview` |
| `Toolbar.jsx` | Add PVPVE controls (grid size, team count, seed, regenerate) |
| `sampleMaps.js` | Add `TILE_LEGEND` export for `'E'` (enemy) and `'B'` (boss) chars |
| `vite.config.js` | Add alias to resolve `dungeon-wfc` engine imports |

---

## Implementation Steps

### Step 1 — Vite Alias for WFC Engine Imports

**File:** `tools/theme-designer/vite.config.js`

Add a path alias so theme-designer can import from the dungeon-wfc engine
without copying files:

```js
resolve: {
  alias: {
    '@wfc': path.resolve(__dirname, '../dungeon-wfc/src/engine'),
    '@wfc-utils': path.resolve(__dirname, '../dungeon-wfc/src/utils'),
  }
}
```

This lets us write `import { runWFC } from '@wfc/wfc.js'` cleanly.

**Verify:** The dungeon-wfc engine files import from `'../utils/tileColors.js'`.
The `@wfc-utils` alias resolves this. If the relative imports inside wfc.js
reference `../utils/`, we may need a second alias or a wrapper.

> **Alternative:** If aliasing proves tricky with the relative imports inside
> the WFC engine files, we can instead create thin re-export wrappers in a
> `tools/shared/wfc-engine/` directory.

---

### Step 2 — PVPVE Decorator Module

**File:** `tools/theme-designer/src/engine/pvpveDecorator.js`

Port the PVPVE-specific logic from `server/app/core/wfc/room_decorator.py`
(the Python PVPVE decorator path) and `server/app/core/wfc/door_placer.py`
into a single JS module.

#### Exports

```js
/**
 * Apply PVPVE room assignments on top of base-decorated rooms.
 *
 * @param {Object} opts
 * @param {string[][]} opts.tileMap       - Decorated tile map (mutated)
 * @param {Object[][]} opts.grid          - WFC grid (rows x cols)
 * @param {Object[]}   opts.variants      - Expanded WFC variants
 * @param {Object[]}   opts.decoratedRooms - Output from decorateRooms()
 * @param {number}     opts.seed          - RNG seed
 * @param {number}     opts.teamCount     - 2-4 player teams
 * @param {number}     opts.gridRows      - Module grid row count
 * @param {number}     opts.gridCols      - Module grid col count
 * @returns {{ rooms, doors, spawnZones, bossRoom, difficultyTiers }}
 */
export function applyPvpveLayout(opts) { ... }
```

#### Core Logic (ported from Python)

1. **Corner spawn assignment** — For each active team (2-4), find the
   flexible room nearest the team's corner via Manhattan distance to
   `(targetRow, targetCol)`. Assign `role = "spawn"`, place 4 `S` tiles,
   record spawn zone bounds.

   ```
   Team corners:
     "a" → (0, 0)               top-left
     "b" → (maxRow, maxCol)     bottom-right
     "c" → (0, maxCol)          top-right
     "d" → (maxRow, 0)          bottom-left
   ```

2. **Center boss placement** — Find the flexible room closest to
   `(gridRows/2, gridCols/2)`. Assign `role = "boss"`, place 1 `B` tile +
   3 `E` guard tiles + 2 `X` chest tiles on available floor slots.

3. **Difficulty tiers** — Assign tiers based on Manhattan distance from
   grid center:

   | Distance | Tier | Max Enemies |
   |----------|------|------------|
   | 0 | boss | 5 |
   | 1 | elite | 5 |
   | 2 | hard | 4 |
   | 3+ | normal | 3 |

4. **Proximity safety ramp** — Rooms within Manhattan distance 1 of ANY
   team spawn become "safe" (enemy tiles removed). Distance 2 = "softened"
   (halve enemy tiles). This mirrors the Python `_PVPVE_PROXIMITY_SAFE`
   behavior.

5. **Door placement** — Scan all module boundaries, find open tile runs
   at the edge between adjacent modules, and probabilistically insert wall
   separators with a 1-tile door gap. Port directly from `door_placer.py`:

   | Condition | Door Chance |
   |-----------|------------|
   | Spawn room on either side | 0% |
   | Interior join (6+ tiles wide) | 0% |
   | Boss room | 70% |
   | Corridor ↔ corridor | 15% |
   | Narrow (2-wide) opening | 55% |
   | Default | 45% |

6. **Room metadata output** — For each room, export:
   ```js
   {
     id: "room_R_C",
     gridRow, gridCol,
     role,           // "spawn" | "boss" | "enemy" | "loot" | "empty" | "stairs"
     archetype,      // "shrine" | "library" | "prison" | null
     bounds: { x_min, y_min, x_max, y_max },
     team,           // "a"/"b"/"c"/"d" for spawn rooms, null otherwise
     difficultyTier, // "boss" | "elite" | "hard" | "normal"
     enemyCount,
     chestCount,
   }
   ```

---

### Step 3 — PVPVE Generator Orchestrator

**File:** `tools/theme-designer/src/engine/pvpveGenerator.js`

Single entry point that runs the full pipeline:

```js
/**
 * Generate a complete PVPVE dungeon for preview.
 *
 * @param {Object} opts
 * @param {number} opts.seed        - RNG seed (default 42)
 * @param {number} opts.gridRows    - Module grid rows (default 6)
 * @param {number} opts.gridCols    - Module grid cols (default 6)
 * @param {number} opts.teamCount   - 2-4 player teams (default 4)
 * @returns {PvpveResult}
 */
export function generatePvpveDungeon({ seed, gridRows, gridCols, teamCount }) {
  // 1. Load preset modules
  //    → PRESET_MODULES from '@wfc/presets.js'

  // 2. Run WFC
  //    → runWFC({ modules: PRESET_MODULES, gridRows, gridCols, seed,
  //              forceBorderWalls: true, ensureConnected: true })

  // 3. Base room decoration
  //    → decorateRooms({ grid, variants, tileMap, seed,
  //        settings: {
  //          enemyDensity: 0.50,
  //          lootDensity: 0.50,
  //          emptyRoomChance: 0.15,
  //          guaranteeBoss: true,
  //          guaranteeSpawn: true,
  //          guaranteeStairs: false,
  //        }
  //      })

  // 4. PVPVE overlay (corner spawns, center boss, doors)
  //    → applyPvpveLayout({ tileMap, grid, variants, decoratedRooms,
  //        seed, teamCount, gridRows, gridCols })

  // 5. Return result
  //    → { success, tileMap, rooms, doors, spawnZones, bossRoom,
  //        difficultyTiers, stats, gridRows, gridCols }
}
```

**Return shape:**
```js
{
  success: boolean,
  tileMap: string[][],        // 2D tile chars (gridRows*8 × gridCols*8)
  rooms: PvpveRoom[],         // Room metadata with roles, archetypes, bounds
  doors: { x, y }[],          // Door positions
  spawnZones: {               // Per-team spawn bounds
    a?: { x_min, y_min, x_max, y_max },
    b?: { ... }, c?: { ... }, d?: { ... }
  },
  bossRoom: PvpveRoom | null, // Center boss room
  difficultyTiers: Map<string, string>,  // "row,col" → tier name
  stats: { ... },
  gridRows: number,
  gridCols: number,
  error?: string,
}
```

---

### Step 4 — PvpvePreview Component

**File:** `tools/theme-designer/src/components/PvpvePreview.jsx`

New center panel component, modeled on the existing `DungeonPreview.jsx` but
with PVPVE-specific rendering layers.

#### Props

```jsx
<PvpvePreview
  themeId="bleeding_catacombs"
  gridRows={6}
  gridCols={6}
  teamCount={4}
  seed={42}
/>
```

#### Render Layers (drawn in order)

1. **Base tiles** — Use the existing `ThemeRenderer` from the theme designer
   to draw every tile in the `tileMap` with the selected theme applied. This
   is the same as `DungeonPreview.jsx` but on a WFC-generated map.

2. **Room archetype overlays** — Use the existing `drawRoomOverlay()` from
   `roomArchetypes.js` for each room that has an archetype (shrine, library,
   etc.). Driven by the room metadata from the generator.

3. **Module grid overlay** (toggleable) — Faint grid lines at MODULE_SIZE
   (8-tile) intervals showing module boundaries. Helps visualize how WFC
   modules compose.

4. **Team spawn zone highlights** (toggleable) — Semi-transparent colored
   rectangles over each team's spawn zone:
   - Team A: Blue
   - Team B: Red
   - Team C: Green
   - Team D: Yellow

5. **Boss room highlight** (toggleable) — Gold/amber border + subtle glow
   on the center boss room.

6. **Difficulty tier overlay** (toggleable) — Color-coded room tinting:
   - Boss (center): Gold
   - Elite (dist 1): Red
   - Hard (dist 2): Orange
   - Normal (dist 3+): No tint

7. **Room labels** (toggleable, visible at zoom ≥ 0.8) — Small text labels
   on each room showing role + archetype (e.g. "Enemy / Prison", "Loot",
   "Spawn A").

8. **Hover info** — Extended from DungeonPreview to show:
   - Grid position `[x, y]` and tile type
   - Module cell `[row, col]` and module name
   - Room role, archetype, difficulty tier
   - Enemy count if enemy room

#### Overlay Toggle Panel

Small floating panel (top-right of preview) with checkboxes:
- ☑ Module Grid
- ☑ Spawn Zones
- ☑ Boss Highlight
- ☐ Difficulty Tiers
- ☐ Room Labels

---

### Step 5 — Toolbar Controls

**File:** `tools/theme-designer/src/components/Toolbar.jsx`

Add a 4th view mode button: **PVPVE Dungeon** (alongside existing Dungeon
Preview, Room Archetypes, Object Browser).

When `viewMode === 'pvpve'`, show PVPVE-specific controls:

| Control | Type | Default | Range |
|---------|------|---------|-------|
| Grid Size | dropdown | `6×6` | `3×3`, `4×4`, `5×5`, `6×6`, `8×8` |
| Team Count | dropdown | `4` | `2`, `3`, `4` |
| Seed | text input | `42` | 0-999999 |
| Randomize | button | — | Generates random seed |
| Regenerate | button | — | Re-runs WFC with current settings |

The Regenerate button should show a brief "Generating..." state while WFC
runs (typically < 200ms for 6×6 grids in JS).

---

### Step 6 — App.jsx Integration

**File:** `tools/theme-designer/src/App.jsx`

Add state for PVPVE controls and wire up the new view mode:

```jsx
const [pvpveConfig, setPvpveConfig] = useState({
  gridRows: 6, gridCols: 6, teamCount: 4, seed: 42,
});
const [viewMode, setViewMode] = useState('dungeon');

// In render:
{viewMode === 'pvpve' ? (
  <PvpvePreview
    themeId={activeThemeId}
    gridRows={pvpveConfig.gridRows}
    gridCols={pvpveConfig.gridCols}
    teamCount={pvpveConfig.teamCount}
    seed={pvpveConfig.seed}
  />
) : viewMode === 'archetypes' ? (
  <RoomArchetypePreview themeId={activeThemeId} />
) : viewMode === 'objects' ? (
  <ObjectBrowser themeId={activeThemeId} />
) : (
  <DungeonPreview themeId={activeThemeId} sampleMapId={sampleMapId} />
)}
```

---

### Step 7 — Tile Legend Extension

**File:** `tools/theme-designer/src/engine/sampleMaps.js`

Add enemy and boss tile types to the legend so the ThemeRenderer can handle
them (rendered as floor tiles with overlay markers):

```js
export const TILE_LEGEND = {
  'W': 'wall',
  'F': 'floor',
  'C': 'corridor',
  'D': 'door',
  'S': 'spawn',
  'X': 'chest',
  'T': 'stairs',
  'E': 'floor',   // Enemy spawn → render as floor (overlay handles marker)
  'B': 'floor',   // Boss spawn  → render as floor (overlay handles marker)
};
```

---

## File Dependency Graph

```
Toolbar.jsx ──────────────────────────┐
    (PVPVE controls: grid, teams,     │
     seed, regenerate button)         │
                                      ▼
App.jsx ─────────────────────► PvpvePreview.jsx
    (viewMode='pvpve',                │
     pvpveConfig state)               │ calls on mount / config change
                                      ▼
                              pvpveGenerator.js
                                      │
                    ┌─────────────────┼──────────────────┐
                    ▼                 ▼                  ▼
              @wfc/wfc.js    @wfc/roomDecorator.js   pvpveDecorator.js
                    │                 │                  │
                    ▼                 │        (corner spawns, center boss,
           @wfc/presets.js            │         difficulty tiers, doors)
           @wfc/moduleUtils.js        │
           @wfc/connectivity.js       │
                                      │
                    ┌─────────────────┘
                    ▼
            ThemeRenderer ◄── themes.js
            roomArchetypes.js ◄── tileProps.js
            (existing theme designer rendering)
```

---

## Step Execution Order

| Step | Files | Depends On | Estimated Scope |
|------|-------|-----------|-----------------|
| 1 | `vite.config.js` | None | ~5 lines changed |
| 2 | `pvpveDecorator.js` (new) | Step 1 (imports work) | ~300 lines — largest new file |
| 3 | `pvpveGenerator.js` (new) | Steps 1-2 | ~80 lines |
| 4 | `PvpvePreview.jsx` (new) | Steps 1-3 | ~250 lines |
| 5 | `Toolbar.jsx` | None (UI only) | ~40 lines added |
| 6 | `App.jsx` | Steps 4-5 | ~20 lines added |
| 7 | `sampleMaps.js` | None | ~2 lines added |

**Recommended implementation order:** 7 → 1 → 2 → 3 → 5 → 6 → 4

Start with the leaf dependencies (tile legend, vite alias), then build up
the engine layer (decorator, generator), then wire up the UI (toolbar, app,
preview component).

---

## Testing Checklist

- [ ] `npm run dev` in theme-designer starts without import errors
- [ ] PVPVE view mode button appears in toolbar
- [ ] Selecting "PVPVE Dungeon" shows a generated dungeon (not a blank canvas)
- [ ] Changing grid size (3×3 → 8×8) regenerates with correct dimensions
- [ ] Changing team count (2/3/4) places correct number of corner spawn zones
- [ ] Changing seed produces different layouts
- [ ] Randomize button generates a new seed and re-renders
- [ ] Regenerate button re-runs WFC with the same seed (same result)
- [ ] Theme selection changes the visual appearance of tiles
- [ ] Module grid overlay toggle works
- [ ] Spawn zone highlights show correct team corners
- [ ] Boss room highlighted at/near grid center
- [ ] Difficulty tier overlay shows gradient from center outward
- [ ] Room labels show correct role + archetype text
- [ ] Hover info displays tile type, module cell, room metadata
- [ ] Doors rendered at module boundaries (not on spawn rooms, yes on boss rooms)
- [ ] Room archetype overlays (shrine props, library bookshelves, etc.) render on appropriate rooms
- [ ] Zoom slider works (0.3× to 2.0× for large maps)
- [ ] No console errors during generation or rendering
- [ ] 8×8 grid (64×64 tiles) renders within 500ms

---

## PVPVE Layout Reference

```
┌────────┬────────┬────────┬────────┬────────┬────────┐
│SPAWN A │corridor│ enemy  │ enemy  │corridor│SPAWN C │  ← Teams in corners
│(safe)  │        │(normal)│(normal)│        │(safe)  │
├────────┼────────┼────────┼────────┼────────┼────────┤
│corridor│ loot   │ enemy  │ loot   │ empty  │corridor│
│        │        │(hard)  │        │        │        │
├────────┼────────┼────────┼────────┼────────┼────────┤
│ enemy  │ enemy  │ enemy  │ enemy  │ enemy  │ enemy  │
│(normal)│(hard)  │(elite) │(elite) │(hard)  │(normal)│
├────────┼────────┼────────┼────────┼────────┼────────┤
│ loot   │ empty  │ enemy  │ ★BOSS★ │ enemy  │ loot   │  ← Boss at center
│        │        │(elite) │(boss)  │(elite) │        │
├────────┼────────┼────────┼────────┼────────┼────────┤
│corridor│ loot   │ enemy  │ enemy  │ shrine │corridor│
│        │        │(hard)  │(hard)  │        │        │
├────────┼────────┼────────┼────────┼────────┼────────┤
│SPAWN D │corridor│ enemy  │ enemy  │corridor│SPAWN B │  ← Teams in corners
│(safe)  │        │(normal)│(normal)│        │(safe)  │
└────────┴────────┴────────┴────────┴────────┴────────┘

Difficulty increases toward center:
  Safe (dist ≤1 from spawn) → Normal (dist 3+) → Hard (dist 2) → Elite (dist 1) → Boss (dist 0)
```

---

## Notes

- The JS `roomDecorator.js` does **not** have PVPVE logic — that exists only in
  the Python `room_decorator.py`. Step 2 ports the Python PVPVE path to JS.
- The JS engine has **no `doorPlacer.js`** — door placement only exists in
  Python `door_placer.py`. Step 2 ports this to JS as well.
- Both tools share identical dependencies (React 18, Vite 5) so no new
  packages are needed.
- The `PRESET_MODULES` array is the single source of truth for both the JS
  tool and the Python server (Python loads from `configs/wfc-modules/library.json`).
