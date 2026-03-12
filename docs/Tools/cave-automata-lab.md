# Cave Automata Lab

**Cellular Automata cave & natural environment generator for the Arena MMO project.**

Standalone dev tool for procedurally generating organic cave maps using Cellular Automata (CA), with full export to the game's dungeon JSON map format. Complementary to the WFC Dungeon Lab — WFC excels at structured room-based dungeons, while Cave Automata produces organic, natural environments (caves, caverns, underground networks).

## Quick Start

```bash
# From project root:
start-cave-automata.bat

# Or manually:
cd tools/cave-automata
npm install
npm run dev
```

Opens at **http://localhost:5190**

## Architecture

```
tools/cave-automata/
├── index.html              # Minimal HTML shell (dark theme)
├── package.json            # React 18 + Vite 5
├── vite.config.js          # Port 5190, auto-open
└── src/
    ├── main.jsx            # React entry point
    ├── App.jsx             # Root component — all state management
    ├── components/
    │   ├── Toolbar.jsx         # Top bar: name, size, preset, generate/clear
    │   ├── ParameterPanel.jsx  # CA params: seed, density, B/S thresholds, iterations
    │   ├── CaveCanvas.jsx      # Main canvas: render, pan, zoom, paint, hover
    │   ├── EntityPanel.jsx     # Paint palette + display toggles
    │   ├── RoomPanel.jsx       # Detected rooms list, purpose editor
    │   ├── StatsPanel.jsx      # Map statistics readout
    │   ├── ExportPanel.jsx     # Export/import, gallery, batch gen, undo/redo
    │   └── BatchModal.jsx      # Batch generation results with mini-previews
    ├── engine/
    │   ├── cellularAutomata.js # Core CA algorithm (init, step, generate)
    │   ├── roomDetection.js    # Flood-fill room finder + bounds + small room removal
    │   ├── connectivity.js     # Connectivity check + corridor carving
    │   ├── postProcessing.js   # Smooth, erode, dilate passes
    │   ├── presets.js          # Rule presets + size presets
    │   └── prng.js             # Seeded PRNG (mulberry32)
    ├── utils/
    │   ├── exportMap.js        # Convert to/from game JSON map format
    │   └── tileColors.js       # Tile type colors, labels, room overlay colors
    └── styles/
        └── cave-automata.css   # Full CSS (grimdark dark theme)
```

### Tech Stack

Identical to all other Arena dev tools:

| Layer | Technology |
|-------|-----------|
| UI | React 18 (JSX) |
| Bundler | Vite 5 + @vitejs/plugin-react |
| State | React useState/useRef/useCallback in App.jsx |
| Persistence | localStorage for gallery |
| Rendering | Canvas API |

## How Cellular Automata Works

The classic cave generation algorithm:

1. **Initialize** a grid randomly — each cell is WALL or FLOOR based on a fill density percentage
2. **Iterate** the automaton — for each cell, count its 8 neighbors (Moore neighborhood):
   - If a FLOOR cell has ≥ `birthThreshold` wall neighbors → becomes WALL
   - If a WALL cell has < `survivalThreshold` wall neighbors → becomes FLOOR
3. **Repeat** for N iterations — caves emerge organically from the noise

The algorithm is fully deterministic given the same seed, width, height, and parameters.

### Rule Parameters

| Parameter | Default | Range | Effect |
|-----------|---------|-------|--------|
| **Fill Density** | 48% | 20–80% | Initial percentage of cells that start as walls |
| **Birth Threshold** | 5 | 1–8 | Min wall neighbors to create a new wall |
| **Survival Threshold** | 4 | 1–8 | Min wall neighbors for a wall to survive |
| **Iterations** | 5 | 1–20 | Number of CA steps to run |
| **Solid Border** | true | bool | Keep map edges as solid walls |

## Features

### Generation

- **One-click generate** — Press "Generate" or hit Enter
- **Rule presets** — 8 built-in presets for different cave styles
- **Seeded PRNG** — Every map is reproducible via seed number
- **Step-by-step** — Advance one CA iteration at a time to observe evolution
- **Custom map sizes** — Presets (12×12 to 50×50) or custom width/height

### Rule Presets

| Preset | Fill% | Birth | Survival | Iters | Style |
|--------|-------|-------|----------|-------|-------|
| Natural Caves | 48 | 5 | 4 | 5 | Classic smooth organic chambers |
| Cavern Network | 42 | 5 | 4 | 7 | Large connected caverns |
| Winding Tunnels | 55 | 5 | 4 | 4 | Narrow winding passages |
| Island Archipelago | 58 | 5 | 3 | 6 | Scattered floor islands |
| Open Clearing | 35 | 5 | 4 | 6 | Mostly open with scattered pillars |
| Dense Labyrinth | 52 | 5 | 5 | 3 | Maze-like passages |
| Crystal Caverns | 45 | 6 | 4 | 4 | Angular geometric caves |
| Flooded Depths | 38 | 6 | 5 | 8 | Open floors with thick columns |

### Post-Processing

- **Smooth** — Remove single-cell wall protrusions and fill single-cell holes
- **Erode** — Widen passages by removing wall cells with few wall neighbors
- **Dilate** — Thicken walls by converting floor cells near walls

### Connectivity

- **Auto-detect** — Finds all disconnected cave regions via flood-fill
- **Status indicator** — Shows "Connected" (green) or "Disconnected: N regions" (red)
- **Connect All Regions** — Carves L-shaped corridors between the closest disconnected rooms

### Room Detection

- Auto-detects discrete cave chambers (connected floor regions)
- Color-coded overlays to visualize room boundaries
- Room list with size (tile count) and percentage of total floor
- **Purpose editor** — Assign each room: empty, spawn, enemy, loot, boss, corridor
- **Name editor** — Custom name per room (exported to game JSON)
- **Remove Small Rooms** — Fill rooms below a configurable size threshold

### Paint / Edit Tools

- **Tile palette** — Wall, Floor, Door, Corridor, Spawn, Chest, Enemy, Boss
- **Brush sizes** 1–5
- **Keyboard shortcuts** — 1-8 for tile types, 0/Esc for no paint
- **Pan** — Ctrl+drag or middle-click drag
- **Zoom** — Scroll wheel (zooms toward cursor)
- **Grid lines** toggle

### Export / Import

- **Export JSON** — Downloads a game-compatible dungeon map JSON file
  - Includes: tiles 2D array, rooms with purposes/enemy_spawns, doors, chests, spawn_points, spawn_zones, tile_legend
  - Entity markers (E, B) are converted to floor tiles; enemies are placed via rooms[].enemy_spawns
  - Can be dropped directly into `server/configs/maps/`
- **Import JSON** — Load any existing game map JSON for editing
- **Gallery** — Save/load maps to localStorage with name, date, and parameters

### Batch Generate

- Generate 2–20 maps with varied seeds
- Auto-ranked by quality score (connectivity + floor openness balance)
- Mini-preview thumbnails for each result
- Click to load the best map into the editor

### Undo / Redo

- Full history stack (up to 50 states)
- Ctrl+Z / Ctrl+Y keyboard shortcuts
- Tracks all generation, post-processing, painting, and editing operations

### Statistics Panel

- Dimensions, total cells
- Floor % / Wall %
- Region count, connectivity status
- Largest / smallest room
- Entity counts (spawns, enemies, bosses, chests, doors)

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Enter | Generate cave |
| 1–8 | Select paint tile (Wall, Floor, Door, Corridor, Spawn, Chest, Enemy, Boss) |
| 0 / Esc | Deselect paint tool |
| [ / ] | Decrease / increase brush size |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Ctrl+Drag | Pan canvas |
| Scroll | Zoom in/out |

## Export Format

Exports match the Arena game's dungeon map JSON format (same as `dungeon_test.json`, `wfc_dungeon.json`):

```json
{
  "name": "Cave Map",
  "width": 25,
  "height": 25,
  "map_type": "dungeon",
  "spawn_points": [{ "x": 5, "y": 5 }, ...],
  "spawn_zones": { "a": { "x_min": 3, "y_min": 3, "x_max": 8, "y_max": 8 } },
  "ffa_points": [...],
  "rooms": [
    {
      "id": "cave_0",
      "name": "Main Cavern",
      "purpose": "spawn",
      "bounds": { "x_min": 1, "y_min": 1, "x_max": 15, "y_max": 12 }
    },
    {
      "id": "cave_1",
      "name": "Demon Den",
      "purpose": "enemy",
      "bounds": { "x_min": 18, "y_min": 5, "x_max": 23, "y_max": 10 },
      "enemy_spawns": [
        { "x": 20, "y": 7, "enemy_type": "demon" }
      ]
    }
  ],
  "doors": [{ "x": 10, "y": 6, "state": "closed" }],
  "chests": [{ "x": 12, "y": 8 }],
  "tiles": [["W","W","F","F",...], ...],
  "tile_legend": {
    "W": "wall", "F": "floor", "D": "door",
    "C": "corridor", "S": "spawn", "X": "chest"
  }
}
```

## Tile Types

| Char | Type | Color | Description |
|------|------|-------|-------------|
| W | Wall | Dark stone | Impassable terrain |
| F | Floor | Cobblestone | Walkable cave floor |
| D | Door | Wood brown | Placeable door |
| C | Corridor | Light stone | Carved corridor connector |
| S | Spawn | Green tint | Player spawn point |
| X | Chest | Gold | Loot chest placement |
| E | Enemy | Red | Enemy spawn (exported as floor + room enemy_spawns) |
| B | Boss | Purple-red | Boss spawn (exported as floor + room enemy_spawns) |

## Future Enhancements

Potential features for future development:

- **Multi-layer generation** — Combine multiple CA passes with different rules (large caves → small tunnels)
- **Water/lava tiles** — New tile types for environmental features
- **Biome themes** — Visual presets (ice caves, lava tubes, mushroom grotto)
- **Template zones** — Define regions that force certain content (guaranteed boss room, etc.)
- **Symmetry modes** — Mirror generation horizontally/vertically/radially
- **Noise blending** — Combine CA with Perlin noise for more natural terrain variation
- **Auto-populate** — Automatically place enemies, chests, and doors based on room purpose rules
- **Path quality analysis** — Analyze corridor bottlenecks and critical paths
- **Minimap navigator** — Click-to-pan minimap for large maps
- **PNG export** — Export map as a pixel image for documentation

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Algorithm | Cellular Automata (B/S rules) | Best for organic, natural cave shapes — complementary to WFC's structured rooms |
| State management | App.jsx props-down | Matches all existing tools — no Redux/Context needed |
| Connectivity fix | L-shaped corridors | Simple, predictable, doesn't destroy cave aesthetics |
| Room detection | 4-connected flood fill | Cardinal-only avoids diagonal-only connections that break pathfinding |
| Border handling | Solid borders by default | Ensures maps are enclosed — required by game engine |
| Export format | Identical to WFC/dungeon_test.json | Drop-in compatibility with server map loader |
