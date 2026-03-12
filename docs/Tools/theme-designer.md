# Dungeon Theme Designer — Documentation

> Procedural grimdark dungeon tile rendering system for the Arena MMO project.
> Created as a replacement for placeholder sprite-based tiles with fully procedural
> Canvas 2D rendering inspired by Dark Souls / Bloodborne aesthetics.

---

## Overview

The Theme system replaces TileLoader sprite-based dungeon tiles with procedural
canvas-drawn tiles. Every wall, floor, corridor, door, chest, and staircase is
rendered with pure Canvas 2D API calls — no sprite sheets required.

**Key features:**
- 8 built-in grimdark dungeon biomes (themes)
- Deterministic per-cell tile variants (same position always produces same look)
- Offscreen canvas tile cache for 60 fps game rendering
- Standalone Theme Designer preview tool (Vite + React)
- Complete fallback chain: ThemeEngine → TileSheet → DUNGEON_COLORS
- JSON theme configs for runtime loading / server-side dungeon theming

---

## Architecture

### Rendering Priority (in drawDungeonTiles)

```
1. ThemeEngine.isReady()  →  procedural themed tiles  (grimdark)
2. isTileSheetLoaded()    →  sprite-based tiles        (TileLoader)
3. DUNGEON_COLORS         →  flat color rectangles      (fallback)
```

### Performance Strategy

On theme load, the ThemeEngine pre-renders **8 variants** of each cacheable tile
type (wall, floor, corridor, spawn = 32 tiles total) to offscreen canvases.
During game rendering, `drawTile()` blits from the cache using `drawImage()`.

Special tiles (door, chest, stairs) are drawn directly since they have
interactive state (open/closed, looted/unlooted).

### Variant Selection

Each grid cell gets a deterministic variant index via:
```
cellHash(gridX, gridY, salt) = hash(x * 7919 + y * 6271 + salt * 3571)
variantIndex = floor(hash * 8)  // 0-7
```

This matches the TileLoader's `tileVariantIndex()` approach — same position
always shows the same tile appearance.

---

## Built-in Themes

> All 8 themes have been tuned for clean tile rendering — random overlay
> circles, ovals, stain pools, bezier veins, and pass-through lines have been
> removed. Floor palettes are pushed significantly lighter than wall palettes
> (50-70% brighter) for clear, natural floor/wall differentiation at gameplay
> resolution. Floor and floorAlt colors are kept within 3 values per channel
> to eliminate checkerboard artifacts — floor tiles read as a single uniform
> surface with only the faintest per-slab variation (varyColor amount: 3).

### 1. Bleeding Catacombs (`bleeding_catacombs`)
Ancient burial halls where crimson mortar bleeds through cracked stone.
- **Walls:** Dark stone blocks with subtle red mortar bleed
- **Floors:** Lighter purple-stone flagstones — clean, no stain pools
- **Palette:** Deep purples, dark reds, crimson accents; floors at #3e/#41 range
- **Mood:** Oppressive, bloody, ancient

### 2. Ashen Undercroft (`ashen_undercroft`)
Scorched ruins where fire once raged through underground chambers.
- **Walls:** Charred brickwork with sparse ember-glow mortar lines
- **Floors:** Warm brown ash-dusted stone — clean, no ember circles
- **Palette:** Charcoal, burnt umber, amber/orange accents; floors at #44/#47 range
- **Mood:** Devastated, smoldering, desolate

### 3. Drowned Sanctum (`drowned_sanctum`)
Submerged temple ruins with subtle water tint.
- **Walls:** Slick stone blocks — no random moss circles, drip lines, or vein curves
- **Floors:** Lighter blue-green water-logged tiles — clean, no ripple circles
- **Palette:** Deep sea blues, teal; floors at #24/#27 range for contrast
- **Mood:** Eerie, submerged, alien

### 4. Hollowed Cathedral (`hollowed_cathedral`)
Grand ruined church with crumbling carved stone.
- **Walls:** Carved stone blocks with subtle crumble — no random icons or gold trim lines
- **Floors:** Lighter purple-grey marble slabs — clean, no crack lines or root curves
- **Palette:** Dark purple-grey, muted gold; floors at #3d/#40 range
- **Mood:** Sacred and fallen, grandeur decayed

### 5. Iron Depths (`iron_depths`)
Abandoned industrial undercity with metal panels and grated floors.
- **Walls:** Riveted metal plates with subtle rust — no random pipe lines
- **Floors:** Lighter steel grate with clean crosshatch — no oil stain ellipses
- **Palette:** Steel blue-grey, rust; floors at #3e/#41 range
- **Mood:** Industrial horror, mechanical, claustrophobic

### 6. Forgotten Cellar (`forgotten_cellar`) — *NEW*
A plain stone basement, long abandoned. The simplest, cleanest dungeon.
- **Walls:** Plain stone blocks with almost no cracks or mortar bleed
- **Floors:** Warmer brown flagstones — clean, distinct from walls
- **Palette:** Muted earth browns and warm grays; floors at #44/#47 range
- **Mood:** Quiet, bare, abandoned — minimal detail

### 7. Pale Ossuary (`pale_ossuary`) — *NEW*
Bone-white stone chambers. Austere, sterile, unsettling.
- **Walls:** Clean carved stone — no icons, no gold trim, no crumble
- **Floors:** Lighter violet-grey marble — clean, no cracks or veins
- **Palette:** Cool grey-violet, pale bone-white; floors at #4d/#50 range
- **Mood:** Empty, silent, sterile — the absence IS the horror

### 8. Silent Vault (`silent_vault`) — *NEW*
Deep slate-blue stone archive. Cold, orderly, vast.
- **Walls:** Smooth stone blocks — no moss, no veins, no detail
- **Floors:** Lighter cool blue slabs with faintest moisture sheen
- **Palette:** Deep slate blue-black, steel blue; floors at #2e/#31 range
- **Mood:** Monastic, sealed, utterly still

---

## File Structure

### Game-Side Integration
```
client/src/canvas/
├── ThemeEngine.js         — Self-contained procedural renderer + tile cache
├── dungeonRenderer.js     — Updated: ThemeEngine → TileSheet → Color fallback
├── ArenaRenderer.js       — Updated: imports + initializes ThemeEngine
└── renderConstants.js     — Unchanged: DUNGEON_COLORS kept as fallback
```

### Theme Designer Tool
```
tools/theme-designer/
├── index.html              — Entry HTML
├── package.json            — React 18 + Vite 5 deps
├── vite.config.js          — Dev server on port 5200
└── src/
    ├── main.jsx            — React entry point
    ├── App.jsx             — Root layout (3-panel)
    ├── engine/
    │   ├── noiseUtils.js   — Hash, PRNG, color manipulation utilities
    │   ├── themes.js       — 8 built-in theme definitions
    │   ├── tilePatterns.js — All procedural drawing algorithms
    │   ├── themeRenderer.js— ThemeRenderer class with tile cache
    │   └── sampleMaps.js   — 4 sample dungeon layouts for preview
    ├── components/
    │   ├── ThemeSelector.jsx — Left sidebar: theme cards with thumbnails
    │   ├── DungeonPreview.jsx— Center: live dungeon canvas with zoom
    │   ├── PaletteEditor.jsx — Right sidebar: palette + param display
    │   └── Toolbar.jsx       — Top bar: map selector, export button
    └── styles/
        └── theme-designer.css — Dark grimdark UI theme
```

### Server Theme Configs
```
server/configs/themes/
├── bleeding_catacombs.json
├── ashen_undercroft.json
├── drowned_sanctum.json
├── hollowed_cathedral.json
├── iron_depths.json
├── forgotten_cellar.json
├── pale_ossuary.json
└── silent_vault.json
```

### Launcher
```
start-theme-designer.bat   — npm install + npm run dev
```

---

## Usage

### Running the Theme Designer

```bash
# Option A: Use the batch launcher
start-theme-designer.bat

# Option B: Manual
cd tools/theme-designer
npm install
npm run dev
# Opens at http://localhost:5200
```

The tool shows a 3-panel layout:
- **Left:** Theme selector with mini canvas thumbnails
- **Center:** Full dungeon preview with zoom slider and hover info
- **Right:** Palette swatches and parameter details
- **Top:** Sample map selector and JSON export button

### Changing the Active Theme In-Game

In `ArenaRenderer.js`, the theme is initialized on module import:
```javascript
themeEngine.setTheme('bleeding_catacombs', TILE_SIZE);
```

To change at runtime (e.g., per dungeon floor):
```javascript
import { themeEngine } from './ThemeEngine.js';
themeEngine.setTheme('drowned_sanctum');
```

### Loading a Custom Theme

Pass a theme config object directly:
```javascript
const custom = {
  id: 'custom_theme',
  palette: { primary: '#1a1018', secondary: '#2a2028', ... },
  wall: { style: 'cracked_stone', brickRows: 3, ... },
  floor: { style: 'flagstone', slabGrid: 2, ... },
  corridor: { style: 'worn_stone' },
  fog: { exploredTint: 'rgba(0,0,0,0.6)', unexploredColor: '#000' },
  ambient: { vignetteStrength: 0.2 }
};
themeEngine.setTheme(custom, 48);
```

### Disabling Procedural Themes

To revert to sprite/color fallback, simply remove the `themeEngine.setTheme()`
call in ArenaRenderer.js. The `themeEngine.isReady()` check will return false
and the rendering will fall through to the existing TileSheet → Color chain.

---

## Theme Config Format

```json
{
  "id": "string — unique identifier",
  "name": "string — display name",
  "description": "string — flavor text",
  "palette": {
    "primary": "#hex — wall base / dark background",
    "secondary": "#hex — wall block face color",
    "accent": "#hex — theme accent (blood, fire, moss, etc.)",
    "mortar": "#hex — mortar line color",
    "highlight": "#hex — bright accent (glows, trim)",
    "floor": "#hex — floor base color",
    "floorAlt": "#hex — floor slab variation",
    "grout": "#hex — floor grout lines"
  },
  "wall": {
    "style": "cracked_stone | scorched_brick | mossy_stone | carved_stone | iron_plate",
    "brickRows": "number — rows of blocks (2-4)",
    "brickCols": "number — columns of blocks (2-3)",
    "mortarWidth": "number — mortar gap in pixels",
    "crackDensity": "0-1 — chance of cracks per tile",
    "edgeVignette": "boolean — darken tile edges",
    "... style-specific params"
  },
  "floor": {
    "style": "flagstone | ash_covered | flooded | cracked_marble | metal_grate",
    "slabGrid": "number — NxN slab grid (2-3)",
    "groutWidth": "number — grout line width",
    "stainChance": "0-1 — chance of stain overlay",
    "debrisChance": "0-1 — chance of tiny debris",
    "... style-specific params"
  },
  "corridor": {
    "style": "worn_stone | ash_trail | shallow_water | worn_carpet | walkway"
  },
  "fog": {
    "exploredTint": "rgba string — fog for revealed tiles",
    "unexploredColor": "#hex or rgba — fog for unseen tiles"
  },
  "ambient": {
    "vignetteStrength": "0-1 — edge darkening intensity",
    "vignetteColor": "rgba string — vignette tint"
  }
}
```

---

## Procedural Drawing Algorithms

### Wall Styles

| Style | Algorithm |
|-------|-----------|
| `cracked_stone` | Base fill → brick grid (3×2 offset) → mortar with red bleed → random bezier cracks → edge vignette |
| `scorched_brick` | Base fill → brick grid → selective scorch overlay (30% blackened) → ember-glow mortar lines → edge vignette |
| `mossy_stone` | Base fill → large blocks (2×2) → moss arc patches → water stain streaks → bioluminescent bezier veins → mortar |
| `carved_stone` | Base fill → grand blocks → inner border carving → random corner crumble → faded icon symbols → gold trim accent |
| `iron_plate` | Base fill → metal panels → gradient highlight strip → corner rivets → diagonal rust streaks → pipe conduit → seam lines |

### Floor Styles

| Style | Algorithm |
|-------|-----------|
| `flagstone` | Base fill → NxN slab grid with color variation → grout lines → blood/stain pools → tiny debris → outline |
| `ash_covered` | Slab base → grout → ash particle scatter (20+ dots, varied alpha) → dying ember glow spots |
| `flooded` | Slab base → semi-transparent water overlay → concentric ripple rings → faint grout through water |
| `cracked_marble` | Fine 3×3 slab grid → diagonal vein lines → crossing cracks → debris chips → faded grout |
| `metal_grate` | Border frame → horizontal + vertical grate lines (6px spacing) → highlight pass → oil stain ellipses → frame border |

---

## What's Complete

- [x] Full procedural rendering engine (ThemeEngine.js — game side)
- [x] 8 grimdark biome themes with distinct wall/floor/corridor styles
- [x] Offscreen canvas tile cache (8 variants × 4 tile types = 32 cached)
- [x] Game integration (dungeonRenderer.js, ArenaRenderer.js)
- [x] Complete fallback chain preserving existing sprite/color rendering
- [x] Standalone Theme Designer tool (React + Vite, port 5200)
- [x] 4 sample dungeon maps for preview (classic, corridors, open hall, boss)
- [x] JSON theme configs in server/configs/themes/
- [x] Launcher batch file (start-theme-designer.bat)
- [x] Theme-aware fog of war colors

---

## Future Development Ideas

### Near-Term Enhancements
1. **Live Theme Editing** — Color picker + parameter sliders in the Theme Designer
   with real-time canvas re-rendering. Currently the tool displays themes but
   doesn't support live editing.
2. **Wall-Connectivity Awareness** — Pass neighbor tile info to wall draw functions
   so walls can render differently at corners, edges, and T-junctions (seamless
   brick patterns, connected mortar lines).
3. **Server-Driven Theme Assignment** — Have the dungeon generator assign themes
   per floor/zone by loading from `server/configs/themes/*.json` and sending the
   theme ID to clients in the dungeon state message.
4. **Animated Details** — Add frame-dependent parameters for things like flickering
   ember glow, water ripple animation, bioluminescent pulse. Would require the
   cache to include multiple animation frames per variant.
5. **Transition Tiles** — Blended tiles for adjacent biome zones (e.g., catacombs
   transitioning into drowned sanctum at a water boundary).

### Medium-Term Goals
6. **Custom Theme Creator** — Full editor in the Theme Designer tool with palette
   picker, style dropdowns, and parameter sliders. Export as JSON, import into game.
7. **Per-Room Theming** — Different themes within the same dungeon (e.g., boss room
   uses a different palette than corridors). The ThemeEngine already supports
   runtime `setTheme()` calls — would need per-tile theme assignment.
8. **Ambient Particle Layer** — Floating ash particles, dripping water, drifting
   embers rendered as a separate overlay layer tied to the active theme.
9. **Theme-Aware Lighting** — Dynamic point lights that interact with theme palette
   (torch = warm, bioluminescence = cool). Would affect tile color via a lighting
   pass after tile rendering.
10. **Mini-Map Theming** — Apply simplified theme colors to the dungeon mini-map
    for consistent aesthetic.

### Long-Term Vision
11. **Procedural Detail Objects** — Barrels, crates, bookshelves, altars drawn
    procedurally and placed by the dungeon generator with theme-appropriate variants.
12. **Tile Sheet Export** — Render theme variants to a sprite sheet PNG for use
    in non-canvas contexts (WebGL, mobile, map editor).
13. **Community Themes** — Theme JSON import/export with sharing. Players could
    select preferred visual themes for their dungeon runs.
14. **WFC Integration** — Feed theme tile patterns into the Wave Function Collapse
    dungeon-wfc tool for constraint-based dungeon layout generation with theme-aware
    adjacency rules.

---

## Known Limitations

- The Theme Designer tool requires `npm install` on first run (React + Vite deps)
- Procedural tiles at 48px resolution have limited detail — this is intentional
  for the pixel-art ARPG aesthetic
- Door/chest/stairs are drawn directly each frame (not cached) since they have
  interactive open/closed states
- No animated tile support yet — tiles are static after cache build
- Theme configs are embedded in ThemeEngine.js (built-in) — server JSON configs
  exist but aren't loaded dynamically yet (require a fetch + setTheme call)
- Wall styles don't account for neighbor context (no seamless brick patterns
  across adjacent wall tiles)

---

*Last updated: Phase — Grimdark Theme System*
*Tool port: 5200 | Themes: 8 built-in | Tile cache: 32 offscreen canvases*
