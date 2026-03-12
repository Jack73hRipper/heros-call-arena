# Module Sprite Decorator

**Visual tile painting tool for WFC dungeon modules in the Arena MMO project.**

Standalone dev tool for assigning specific atlas sprites to each cell of a WFC dungeon module. When modules are assembled into dungeons at runtime, the decorated sprites render in-game instead of the generic hash-based tile variants — making generated dungeons look hand-crafted.

## Quick Start

```bash
# From project root:
start-module-decorator.bat

# Or manually:
cd tools/module-decorator
npm install
npm run dev
```

Opens at **http://localhost:5195**

## Architecture

```
tools/module-decorator/
├── index.html              # Minimal HTML shell (dark theme)
├── package.json            # React 18 + Vite 5
├── vite.config.js          # Port 5195, auto-open
├── public/
│   └── mainlevbuild.png    # Atlas spritesheet (copied from Assets/)
└── src/
    ├── main.jsx            # React entry point
    ├── App.jsx             # Root component — all state management
    ├── components/
    │   ├── Toolbar.jsx         # Top bar: tabs, undo/redo, decoration stats
    │   ├── AtlasPalette.jsx    # Right sidebar: atlas browser, category filter, search, sprite picker
    │   ├── ModuleSelector.jsx  # Left sidebar: module list, purpose filter, thumbnails
    │   ├── ModuleCanvas.jsx    # Main canvas: 6×6 grid, paint/erase, layer compositing, hover preview
    │   ├── LayerPanel.jsx      # Layer controls: visibility, opacity, auto-decorate
    │   ├── PreviewPanel.jsx    # Dungeon preview: module grid assembly with zoom/pan
    │   └── ExportPanel.jsx     # Export/import sprite library, atlas info
    ├── engine/
    │   ├── atlasLoader.js      # Parse atlas JSON, build full grid index, filter/search
    │   ├── spriteMap.js        # Sprite map data model (create, set, clone, rotate, serialize)
    │   ├── autoDecorator.js    # Rule-based auto-decoration (wall/floor/overlay assignment)
    │   └── modulePresets.js    # Built-in WFC module tile grids (16 standard modules)
    ├── utils/
    │   └── tileColors.js       # Tile type → color mapping, purpose badge colors
    └── styles/
        └── module-decorator.css # Full CSS (grimdark dark theme)
```

### Tech Stack

Identical to all other Arena dev tools:

| Layer | Technology |
|-------|-----------|
| UI | React 18 (JSX) |
| Bundler | Vite 5 + @vitejs/plugin-react |
| State | React useState/useRef/useCallback in App.jsx |
| Persistence | localStorage for sprite library |
| Rendering | Canvas API |

## Core Concepts

### Sprite Map

A sprite map is a per-module, per-cell assignment of atlas sprite regions. Each cell in a 6×6 module grid has two layers:

- **Base Layer** — The primary tile art (floor texture, wall texture)
- **Overlay Layer** — A decorative element drawn on top (torch, cobweb, banner, blood splatter)

Both layers reference a rectangular region `{ x, y, w, h }` within the atlas spritesheet.

### Layer System

The editor renders three compositable layers:

1. **Base Sprite Layer** — Floor/wall art from the atlas
2. **Overlay Sprite Layer** — Decorative overlays from the atlas
3. **Gameplay Ghost Layer** — Transparent color overlay showing the functional tile type (W/F/D/C/S/X/E/B)

Each layer has independent visibility toggle and opacity slider. The gameplay ghost lets you see what each tile *does* while painting what it *looks like*.

### Auto-Decoration

One-click rule-based decoration assigns sprites based on tile types:

- `W` (wall) tiles → wall sprite variants (brick, cobble, stone)
- `F` (floor) tiles → cobble floor variants
- `C` (corridor) tiles → smooth floor variants
- `S` (spawn) tiles → smooth floor variants
- All other passable tiles → cobble floor variants

Five style presets control the wall/floor combination:

| Preset | Walls | Floors | Best For |
|--------|-------|--------|----------|
| Grimdark Brick | Brick | Cobble | Standard dungeon rooms |
| Ancient Stone | Stone | Smooth | Temple / ancient ruins |
| Cobble Dungeon | Cobble | Cobble | Natural underground |
| Mixed Ruins | Random mix | Random mix | Varied / decayed areas |
| Clean Halls | Brick | Smooth | Maintained interiors |

### Rotation Awareness

WFC modules can rotate (0°, 90°, 180°, 270°). The sprite map system supports automatic rotation — when exporting, the tool can generate all 4 rotation variants of sprite assignments so the game renderer always has the correct mapping regardless of which rotation the WFC engine placed.

## Features

### Module Selector (Left Sidebar)
- Scrollable list of all 16 built-in WFC modules with mini tile-color thumbnails
- **Purpose filter** — filter by All, Empty, Corridor, Spawn, Enemy, Loot, Boss (with count badges)
- **Decorated indicator** — green left border + checkmark on modules with sprite assignments
- **Rotation badge** — ↻ icon shows which modules allow rotation
- **Import custom** — Load additional module JSON files from the WFC Dungeon Lab

### Sprite Atlas Palette (Right Sidebar)
- Visual grid of all tiles from the `mainlevbuild.png` atlas
- **Two view modes:**
  - *Named* — only cataloged sprites from the atlas JSON (Floor_Cobble_1, Wall_Brick_1, etc.)
  - *All Tiles* — every 16×16 cell in the entire 1024×640 sheet (2,560 tiles)
- **Category filter** — 21 dungeon tileset categories (Floor_Stone, Wall_Face, Deco_Wall, Furniture, etc.)
- **Tag filter** — toggle tags to narrow results (e.g., `stone`, `torch`, `tall-2`); AND logic when multiple active
- **Search** — filter by sprite name
- **Selected sprite preview** — shows the selected tile at 48px with name, coordinates, category, tags, and group info
- Click any tile to select it as the paint brush

### Module Canvas (Center)
- **Large 384×384px canvas** showing the 6×6 module at 64px per cell
- Three composited layers: base sprites, overlay sprites, gameplay ghost
- **Left-click** to paint the selected atlas sprite onto a cell
- **Right-click** to erase (clear the active layer for that cell)
- **Drag-to-paint** — hold and sweep across cells for rapid painting
- **Hover preview** — shows a ghost of the selected sprite in the hovered cell before painting
- **Active layer indicator** — blue border for base layer, pink border for overlay layer
- **Tile type labels** — small letter on each cell showing the gameplay tile type
- Grid overlay for clear cell boundaries

### Layer Panel
- **Paint Target toggle** — switch between painting on Base or Overlay layer
- **Layer visibility toggles** — independently show/hide each of the three layers
- **Opacity sliders** — adjust each layer's opacity (0–100%)
- **Current module stats** — base sprite count / overlay sprite count out of 36 cells
- **Auto-Decorate presets** — 5 one-click style presets for instant rule-based decoration
- **Clear Module** — reset all sprites for the current module
- **Auto-Decorate All** — apply auto-decoration to all undecorated modules at once

### Export Panel
- **Export module-sprites.json** — download the full sprite library as a JSON file
- **Copy to Clipboard** — JSON text copied directly
- **Import Sprite Library** — load a previously exported sprite library JSON
- **Import Atlas JSON** — load a different atlas metadata file
- **Atlas Info** — displays current atlas sheet name, dimensions, tile size, named sprite count

### Dungeon Preview Tab
- Simulates a module grid layout using decorated modules
- **Configurable grid** — 1×1 to 8×8 module grid
- **Zoom** — scroll wheel (25%–400%)
- **Pan** — click and drag
- **Module grid overlay** — dashed yellow borders with module name labels
- **Reset View** — recenter and reset zoom
- **Regenerate** — re-assemble the preview with a new random module arrangement

### Undo/Redo
- **Ctrl+Z** — undo last paint/erase action
- **Ctrl+Y** — redo
- Up to 50 undo levels
- Undo count badge shown in toolbar

### Persistence
- Sprite library auto-saved to localStorage on every change
- Survives page reloads — pick up where you left off
- Import/export for sharing between machines or version control

## Export Format

The exported `module-sprites.json` follows this structure:

```json
{
  "version": 1,
  "atlas": "mainlevbuild.png",
  "tileSize": 16,
  "modules": {
    "preset_corridor_h": {
      "cells": [
        [
          { "base": { "x": 272, "y": 304, "w": 16, "h": 16 }, "overlay": null },
          { "base": { "x": 272, "y": 304, "w": 16, "h": 16 }, "overlay": null },
          ...
        ],
        ...
      ]
    },
    "preset_room_dead_end": { ... },
    ...
  }
}
```

Each module entry maps to a 6×6 grid of cells. Each cell has:
- `base` — atlas region for the primary tile sprite (or `null` if unassigned)
- `overlay` — atlas region for the decorative overlay sprite (or `null`)

Only modules with at least one sprite assignment are included in the export.

## Game Renderer Integration

To consume the sprite map in the game, two small changes are needed:

### 1. Load the sprite map JSON

In the game client, load `module-sprites.json` alongside the existing tilesheet:

```javascript
// In TileLoader.js or a new SpriteMapLoader.js
let spriteMapData = null;

export async function loadSpriteMap() {
  const res = await fetch('/module-sprites.json');
  spriteMapData = await res.json();
}

export function getModuleSpriteMap() { return spriteMapData; }
```

### 2. Look up sprites during rendering

In `dungeonRenderer.js`, when drawing a tile that belongs to a WFC module, check the sprite map first:

```javascript
// After determining the module ID and local (row, col) within the module:
const moduleSprites = spriteMapData?.modules?.[moduleId];
if (moduleSprites) {
  const cell = moduleSprites.cells[localRow]?.[localCol];
  if (cell?.base) {
    ctx.drawImage(atlasImage, cell.base.x, cell.base.y, cell.base.w, cell.base.h, px, py, TILE_SIZE, TILE_SIZE);
  }
  if (cell?.overlay) {
    ctx.drawImage(atlasImage, cell.overlay.x, cell.overlay.y, cell.overlay.w, cell.overlay.h, px, py, TILE_SIZE, TILE_SIZE);
  }
} else {
  // Fall back to current generic rendering
}
```

This is fully backward-compatible — undecorated modules keep using the existing hash-based variant system.

## How to Use

### Basic Workflow
1. **Launch:** Run `start-module-decorator.bat` or `cd tools/module-decorator && npm run dev`
2. **Select a module:** Click any module in the left sidebar list
3. **Pick a sprite:** Click a tile from the atlas palette on the right
4. **Paint:** Left-click cells on the 6×6 grid to assign the sprite
5. **Switch layers:** Toggle between Base and Overlay in the Layer Panel
6. **Or auto-decorate:** Click a style preset to auto-fill based on tile types
7. **Preview:** Switch to the "Dungeon Preview" tab to see modules assembled
8. **Export:** Click "Export module-sprites.json" to download the file

### Quick Start: Decorate Everything
1. Launch the tool
2. In the Layer Panel, click **"Auto-Decorate All"**
3. This fills all 16 modules with rule-based sprites using the Grimdark Brick preset
4. Browse each module and hand-refine any cells you want to customize
5. Export when satisfied

### Tips
- Start with auto-decorate, then hand-paint specific cells for variety
- Use the Overlay layer for details — torches on walls, cracks on floors, etc.
- Toggle the Gameplay Ghost layer on/off to check alignment with tile types
- Lower gameplay opacity to 20-30% for a subtle guide while painting
- Right-click to erase mistakes on the active layer
- Use "All Tiles" mode in the atlas palette to access every 16×16 cell in the full sheet

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Module size | 6×6 fixed | Matches WFC Dungeon Lab module size |
| Layers | Base + Overlay | Simple two-layer system covers 95% of decoration needs without complexity |
| Atlas format | mainlevbuild atlas JSON | Reuses existing cataloged sprite data from the Sprite Cataloger |
| Persistence | localStorage | No backend needed, instant save/load, matches other tools |
| Export format | Flat JSON | Simple, human-readable, easy to load in the game renderer |
| Auto-decoration | Rule-based presets | Gives instant results, hand-refinement for quality |
| Rotation support | spriteMap rotation function | Engine-level rotation so you decorate once, all 4 variants derived automatically |
| Tool pattern | React 18 + Vite 5 + Canvas | Identical to all other Arena dev tools |
| Port | 5195 | Next available after cave-automata (5190) |

## Current Status

### Implemented
- [x] Full project scaffold (React 18, Vite 5, grimdark CSS theme)
- [x] Atlas loader with full grid indexing (named + unnamed sprites)
- [x] Atlas loader parses tags, groups, and groupPart fields from atlas JSON
- [x] Sprite map data model (create, set, clone, rotate, serialize, deserialize)
- [x] Auto-decoration engine with 5 style presets
- [x] 16 built-in WFC module presets with tile grids
- [x] Module selector with purpose filter, thumbnails, decorated indicators
- [x] Sprite atlas palette with dual view modes, category filter, search
- [x] Tag-based filtering in atlas palette (AND logic, toggle on/off)
- [x] Selected sprite info shows tags and group membership
- [x] 21-category dungeon tileset taxonomy (matches Sprite Cataloger)
- [x] 6×6 module canvas with three compositable layers
- [x] Click-to-paint and drag-to-paint with hover preview
- [x] Right-click to erase
- [x] Base/Overlay layer toggle
- [x] Layer visibility and opacity controls
- [x] Auto-decorate per module (5 style presets)
- [x] Auto-decorate all undecorated modules
- [x] Clear module sprites
- [x] Undo/Redo (Ctrl+Z / Ctrl+Y, 50 levels)
- [x] Export sprite library as JSON download
- [x] Copy to clipboard
- [x] Import sprite library JSON
- [x] Import atlas JSON
- [x] localStorage auto-persistence
- [x] Dungeon preview with zoom/pan and module grid overlay
- [x] Custom module JSON import
- [x] Batch file launcher (start-module-decorator.bat)

### Future Enhancements
- [ ] **Stamp tool for groups** — select a multi-tile group (e.g., `Bookcase_1`), click a cell, auto-place all parts in correct relative positions
- [ ] **Group palette view** — browse sprites by group (show each group as a single assembled thumbnail)
- [ ] **Rotation preview** — show all 4 rotation variants of the current module side-by-side with sprites
- [ ] **Fill tool** — flood-fill same-type cells with the selected sprite
- [ ] **Import dungeon JSON** — load an exported WFC dungeon and preview with decorated sprites applied per-module
- [ ] **Multi-module selection** — paint the same sprite across all modules with matching tile types
- [ ] **Overlay auto-placement** — rule-based overlay pass (torch on walls near floors, cobwebs in corners)
- [ ] **Animated tile support** — assign animation frames (torch_1-4, candle_01-04) with playback preview
- [ ] **Module biome tags** — tag modules with visual themes (crypt, sewer, cave) for theme-based auto-decoration
- [ ] **Undo per-stroke** — batch multiple cells painted in a single drag into one undo step
- [ ] **Copy/paste module sprites** — copy sprite assignments from one module to another
- [ ] **Game renderer integration** — TileLoader.js and dungeonRenderer.js patch for sprite map consumption
