# Sprite Sheet Cataloger — Tool Documentation

> **Location:** `tools/sprite-cataloger/`
> **Stack:** React 18 + Vite 5 (matches game client stack)
> **Port:** http://localhost:5174
> **Start:** `start-sprite-cataloger.bat` (project root) or `cd tools/sprite-cataloger && npm run dev`

---

## Purpose

A standalone web-based tool for cataloging, organizing, and exporting sprites from sprite sheet images. Built specifically for the Arena MMO project so that hand-made sprite sheets (which may not have perfectly uniform grid alignment) can be precisely sliced, named, categorized, and exported as a JSON atlas that the game client's Canvas renderer can consume directly.

---

## Architecture

```
tools/sprite-cataloger/
├── index.html                         # Entry HTML
├── package.json                       # Dependencies (React 18, Vite 5)
├── vite.config.js                     # Dev server on port 5174
└── src/
    ├── main.jsx                       # React root + AtlasProvider
    ├── App.jsx                        # Main layout (toolbar + canvas + sidebar)
    ├── App.css                        # Full dark-theme stylesheet
    ├── context/
    │   └── AtlasContext.jsx           # Global state (useReducer) — sprites, categories, grid, animations
    ├── components/
    │   ├── Toolbar.jsx                # Top bar — import/export, auto-detect, clear
    │   ├── SheetCanvas.jsx            # Main canvas — image display, grid overlay, selection
    │   ├── GridControls.jsx           # Grid cell size, offset, spacing controls
    │   ├── CategoryManager.jsx        # Create/rename/delete categories
    │   ├── SpriteProperties.jsx       # Per-sprite name, category, coordinate editing
    │   ├── SpriteList.jsx             # Filterable/searchable list of all sprites
    │   ├── PreviewPanel.jsx           # Game-scale (40px) + zoomed (4×) sprite preview
    │   └── AnimationEditor.jsx        # Animation sequence builder with playback
    └── utils/
        ├── gridDetector.js            # Transparency-based grid auto-detection
        └── exporters.js               # JSON atlas export/import, PNG cropping
```

---

## Features

### Sheet Import
- **File picker** — click "Import Sheet" to browse for a PNG
- **Drag & drop** — drop an image directly onto the canvas area
- Supports any PNG sprite sheet (the combined sheets from `Assets/`)

### Grid Overlay System
- **Cell Width / Height** — adjustable via slider, number input, or ±1px nudge buttons
- **Offset X / Y** — shift the grid to align with sheets that have margins
- **Spacing X / Y** — account for padding/gutters between cells
- **Live preview** — grid lines update in real-time over the sheet as you adjust
- **Row × Column count** — displayed below the controls so you can see how many cells the current settings produce

### Auto-Detect Grid
- **Auto-Detect** — analyzes the image's transparency patterns using autocorrelation to find the most likely cell dimensions, offset, and spacing. Reports a confidence percentage.
- **Suggest Sizes** — tries all common sprite sizes (8, 16, 24, 32, 48, 64, 96, 128, 256) and ranks them by how evenly they divide the sheet. Shows top 5 suggestions.

### Sprite Cataloging
- **Click a grid cell** to catalog it — automatically creates a sprite entry with coordinates derived from the grid
- **Smart auto-naming** — new sprites auto-name based on the active category (e.g., if you last assigned `Wall_Face`, the next sprite is `Wall_Face_4`). Falls back to `sprite_N` if no category context.
- **Category assignment** — assign each sprite to a category from the dropdown. Changing a sprite's category also sets it as the "active" category for future auto-naming.
- **Coordinate fine-tuning** — per-sprite X, Y, W, H fields with ±1px nudge buttons for precise alignment on imperfect sheets
- **Delete individual sprites** from the catalog

### Multi-Select & Batch Operations
- **Shift+click** cells to multi-select sprites
- **Batch assign category** — apply one category to all selected sprites at once
- **Batch name prefix** — rename all selected sprites with a prefix + sequential number (e.g., `Floor_Cobble_1`, `Floor_Cobble_2`, …)
- **Batch assign tags** — type comma-separated tags and press Enter to apply to all selected sprites
- **Batch assign group** — type a group name and press Enter; parts are auto-assigned (`top`/`bot` for 2 tiles, `top`/`mid`/`bot` for 3 tiles)
- Quick tag suggestion buttons for common multi-tile tags (`tall-2`, `tall-3`, `wide-2`, `stone`, `brick`, `wood`)
- **Clear selection** button to deselect all

### Category Management
- **21 dungeon tileset categories** (pre-loaded, purpose-driven taxonomy):

| Category | What Belongs | Examples |
|---|---|---|
| `Floor_Stone` | Stone/cobble/smooth floor tiles | Cobble variants, smooth stone, cracked flagstone |
| `Floor_Dirt` | Earth, dirt, sand floor tiles | Dirt paths, sandy ground, packed earth |
| `Floor_Special` | Functional floor tiles | Spawn markers, trap plates, floor grates, rugs |
| `Wall_Face` | Front-facing wall surface (player-visible) | Brick face, cobble face, stone face |
| `Wall_Top` | Top-of-wall cap tiles (row above face) | Brick parapet, stone crenellation |
| `Wall_Edge` | Wall-to-floor transitions, edges, corners | Left/right edges, inner/outer corners |
| `Wall_Accent` | Wall detail tiles | Cracked brick, mossy stone, archway segments |
| `Door` | Door tiles in all states | Wood door closed/open, iron gate, portcullis |
| `Stair` | Stairs, ladders, ramps | Stone staircase top/bottom tiles |
| `Deco_Wall` | Decorations mounted on walls (overlays) | Torches, banners, sconces, chains, shields |
| `Deco_Floor` | Decorations on floors (overlays) | Blood splatter, cracks, debris, puddles, runes |
| `Furniture` | Dungeon furniture | Tables, chairs, beds, bookshelves, weapon racks |
| `Container` | Lootable/interactive objects | Chests, barrels, crates, urns, pots |
| `Column` | Pillars, columns, supports | Stone pillar top/mid/base |
| `Water` | Water, lava, liquid tiles | Water surface, lava, puddle |
| `Vegetation` | Organic growth | Mushrooms, vines, moss patches |
| `Character` | Heroes, NPCs | Player sprites, townfolk |
| `Monster` | Enemy sprites | Skeletons, goblins, etc. |
| `Effect` | VFX tiles | Flame sprites, sparkles, magic glows |
| `UI` | Interface elements in the sheet | Cursor, icons, buttons |
| `Uncategorized` | Default / not yet sorted | Anything unidentified (protected, can't delete) |

- **Add** new categories with text input
- **Rename** categories by double-clicking (all assigned sprites update automatically)
- **Delete** categories (sprites reassigned to "Uncategorized"; the Uncategorized category is protected)
- **Sprite counts** shown next to each category

### Sprite List
- **Full searchable list** of all cataloged sprites
- **Filter by category** dropdown
- **Text search** by sprite name
- **Sorted** by category, then alphabetically by name
- **Click to select / Shift+click to multi-select** directly from the list
- Shows name, category, and coordinate info per entry

### Preview Panel
- **Game-scale preview** — renders the selected sprite at the game's 40px tile size (matching `TILE_SIZE` in `ArenaRenderer.js`)
- **Zoomed 4× preview** — pixel-level view with per-pixel grid lines for checking alignment accuracy
- **Checkerboard background** — makes transparency visible

### Animation Sequencing
- **Create named animations** (e.g., `warrior_idle`, `goblin_walk`)
- **Add frames** by selecting a sprite and clicking "+ Add Selected"
- **Remove frames** individually
- **FPS control** (1–30)
- **Loop toggle**
- **Live playback** — play/pause button animates the frames on a small canvas
- **Frame counter** displayed during playback

### Canvas Navigation
- **Zoom** — mouse wheel zooms toward cursor position (0.1× to 10×)
- **Pan** — middle-click-drag or Alt+left-click-drag to pan the view
- **Hover highlighting** — grid cell under the cursor gets a white outline
- **Color-coded overlays** — each category gets a unique color tint on the canvas
- **Selected sprite** shown with a white border; multi-selected sprites shown with yellow borders
- **Sprite name labels** drawn on each cataloged cell

### Export (JSON Atlas)
Exports a `sprite-atlas.json` with this structure:
```json
{
  "version": 1,
  "sheetFile": "mainlevbuild.png",
  "sheetWidth": 1024,
  "sheetHeight": 640,
  "gridDefaults": {
    "cellW": 16, "cellH": 16,
    "offsetX": 0, "offsetY": 0,
    "spacingX": 0, "spacingY": 0
  },
  "categories": ["Floor_Stone", "Floor_Dirt", "Wall_Face", "...", "Uncategorized"],
  "sprites": {
    "Floor_Cobble_1": {
      "x": 736, "y": 272, "w": 16, "h": 16,
      "category": "Floor_Stone", "row": 17, "col": 46,
      "tags": ["stone", "cobble"],
      "group": null
    },
    "Bookcase_1_Top": {
      "x": 160, "y": 96, "w": 16, "h": 16,
      "category": "Furniture", "row": 6, "col": 10,
      "tags": ["tall-2", "wood", "furniture"],
      "group": "Bookcase_1", "groupPart": "top"
    },
    "Bookcase_1_Bot": {
      "x": 160, "y": 112, "w": 16, "h": 16,
      "category": "Furniture", "row": 7, "col": 10,
      "tags": ["tall-2", "wood", "furniture"],
      "group": "Bookcase_1", "groupPart": "bot"
    }
  },
  "animations": {
    "torch_flicker": {
      "frames": ["Deco_Torch_1", "Deco_Torch_2", "Deco_Torch_3"],
      "fps": 4,
      "loop": true
    }
  }
}
```

New fields (backward compatible — absent fields default to `[]` / `null`):
- **`tags`** — array of string tags for flexible cross-category filtering
- **`group`** — name linking multi-tile sprites that form one visual object
- **`groupPart`** — position within the group (`top`, `mid`, `bot`, `tl`, `tr`, `bl`, `br`)

### Import Atlas
- Re-import a previously saved atlas JSON to continue editing
- Restores all sprites, categories, animations, and grid settings
- Sheet image must be re-loaded separately (the atlas stores the filename for reference)

### Clear All
- Bulk-delete all cataloged sprites with a confirmation prompt

---

## Naming Convention

Use a consistent pattern: **`{Type}_{Material}_{Variant}`** with optional **`_{Part}`** for multi-tile sprites.

### Single-tile examples:
```
Floor_Cobble_1          Floor_Cobble_2          Floor_Cobble_3
Floor_Smooth_1          Floor_Smooth_2          Floor_Smooth_3
Wall_Brick_1            Wall_Cobble_1           Wall_Stone_1
Deco_Torch_1            Deco_Torch_2
Deco_Blood_Splat_1      Deco_Cobweb_1
Door_Wood_Closed        Door_Wood_Open
Door_Iron_Closed        Door_Iron_Open
Chest_Wood_Closed       Chest_Wood_Open
Barrel_1                Barrel_2
Column_Stone_1
```

### Multi-tile examples (2–3 tiles tall/wide):
```
Wall_Brick_Tall_1_Top       Wall_Brick_Tall_1_Bot
Column_Stone_1_Top          Column_Stone_1_Mid          Column_Stone_1_Bot
Bookcase_1_Top              Bookcase_1_Bot
Statue_Stone_1_Top          Statue_Stone_1_Mid          Statue_Stone_1_Bot
Door_Iron_Tall_Top          Door_Iron_Tall_Bot
Banner_Red_Top              Banner_Red_Bot
```

The batch group-assign workflow auto-labels parts: select 2 tiles top-to-bottom → `top`, `bot`. Select 3 → `top`, `mid`, `bot`. For 2×2 objects use `tl`, `tr`, `bl`, `br`.

---

## Tag System

Tags provide a second axis of organization beyond categories. A sprite can have any number of tags.

### Built-in tag suggestions:

| Tag Family | Tags | Purpose |
|---|---|---|
| **Material** | `stone`, `brick`, `cobble`, `wood`, `iron`, `moss` | Filter by material type |
| **Size** | `tall-2`, `tall-3`, `wide-2`, `wide-3` | Find multi-tile sprites |
| **Behavior** | `animated` | Sprites with animation frames |
| **Decoration** | `torch`, `banner`, `blood`, `crack`, `debris`, `puddle`, `cobweb` | Overlay content type |
| **Lighting** | `dark`, `light`, `glow`, `shadow` | Light/mood context |
| **Position** | `top`, `mid`, `bot`, `left`, `right` | Part position hints |
| **Edge** | `corner-tl`, `corner-tr`, `corner-bl`, `corner-br`, `edge-n`, `edge-s`, `edge-e`, `edge-w` | Wall/floor edge context |
| **Variant** | `variant-a`, `variant-b`, `variant-c` | Alternate visual options |

Custom tags can be typed freely — just enter any text and press Enter.

---

## Multi-Tile Sprite Workflow

For sprite sheets with tiles that are 2–3 tiles tall (e.g., bookcases, columns, tall doors), each 16×16 tile must be cataloged individually. The **group** system links them together.

### Step-by-step:
1. **Catalog each tile** — click the top tile, then the bottom tile (each becomes its own sprite entry)
2. **Shift+click** both tiles to multi-select them (order matters: top first, then bottom)
3. **Batch assign category** — set both to `Furniture`, `Column`, etc.
4. **Batch name prefix** — type `Bookcase_1` to name them `Bookcase_1_1`, `Bookcase_1_2`
5. **Rename** to `Bookcase_1_Top` and `Bookcase_1_Bot` (or just use part suffixes)
6. **Batch assign group** — type `Bookcase_1` and press Enter. Parts auto-assign:
   - 2 selected → `top`, `bot`
   - 3 selected → `top`, `mid`, `bot`
7. **Add tags** — add `tall-2` (or `tall-3`) and `wood` to both

### How the Module Decorator uses groups:
The Module Decorator reads `group` and `groupPart` fields and shows them in the sprite info panel. This lets you quickly identify which tiles belong together when painting multi-tile regions in a dungeon module.

---

## Integration Path

The exported JSON atlas is designed to be consumed by the game client. The integration would involve:

1. Place the exported `sprite-atlas.json` and the PNG sheet(s) into `client/public/sprites/`
2. Add a `SpriteLoader` utility to `client/src/canvas/` that:
   - Loads the atlas JSON at game start
   - Pre-loads the sprite sheet image
   - Provides a `drawSprite(ctx, spriteName, x, y)` function
3. Update `ArenaRenderer.js` to call `drawSprite()` instead of drawing colored circles/diamonds

---

## Future Development Ideas

### High Priority
| Feature | Description |
|---------|-------------|
| **Undo / Redo** | Ctrl+Z / Ctrl+Y with a state history stack (the reducer architecture already supports this) |
| **Grid Snapping** | When manually adjusting sprite coordinates, snap to the nearest grid line |
| **Export Individual PNGs** | Crop and download individual sprites or entire category batches as separate PNG files |
| **SpriteLoader Integration** | Build the client-side loader so the game actually renders cataloged sprites |
| **LocalStorage Persistence** | Auto-save the current atlas state to localStorage so work isn't lost on refresh |

### Medium Priority
| Feature | Description |
|---------|-------------|
| **Multi-Sheet Support** | Handle multiple sprite sheet files in one atlas (character sheets 1–12) |
| **Sprite Thumbnails in List** | Show a tiny cropped preview next to each sprite in the list panel |
| **Drag-to-Reorder Frames** | Drag animation frames to reorder instead of remove-and-re-add |
| **Tilemap Preview** | Place cataloged sprites on a mock tile grid to preview how they look at game scale |
| **Keyboard Shortcuts** | Arrow keys to move selection, Delete to remove, Ctrl+A to select all visible |
| **Stamp Preview** | Show grouped multi-tile sprites assembled together as a preview |

### Lower Priority / Nice-to-Have
| Feature | Description |
|---------|-------------|
| **Multiple Spritesheets Atlas** | Combine multiple sheets into one atlas with sheet references per sprite |
| **Auto-Slice All** | One-click button to catalog every grid cell as a sprite (with auto-naming) |
| **Duplicate Detection** | Flag visually identical sprites across the sheet |
| **Export to Pixi.js Format** | Generate Pixi.js-compatible texture atlas JSON (for future renderer upgrade) |
| **9-Slice Support** | Mark sprites as 9-slice for UI panels and borders |
| **Collision Box Editor** | Define per-sprite collision rectangles for physics/hit detection |
| **Origin/Anchor Point** | Set per-sprite anchor points for rotation and positioning |
| **Color Palette Extraction** | Auto-detect dominant colors per sprite for tinting or palette-swap features |
| **Dark/Light Theme Toggle** | Currently dark-only; add a light theme option |
| **Export to CSS Sprite Classes** | Generate CSS classes for each sprite (useful if any UI uses HTML sprites) |

---

## Running

```bash
# From project root
start-sprite-cataloger.bat

# Or manually
cd tools/sprite-cataloger
npm install
npm run dev
# Opens at http://localhost:5174
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| react | ^18.2.0 | UI framework |
| react-dom | ^18.2.0 | DOM rendering |
| vite | ^5.4.0 | Dev server & bundler |
| @vitejs/plugin-react | ^4.2.1 | JSX/React support in Vite |

No additional dependencies — the tool is built entirely with React + Canvas API, keeping it lightweight and matching the game client's tech stack.
