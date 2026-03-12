# WFC Dungeon Lab — Design & Implementation Document

## Overview

**Tool:** Wave Function Collapse dungeon map generation lab  
**Location:** `tools/dungeon-wfc/`  
**Port:** 5185  
**Stack:** React 18 + Vite (same pattern as particle-lab and sprite-cataloger)  
**Launch:** `start-dungeon-wfc.bat` or `cd tools/dungeon-wfc && npm run dev`

---

## Architecture

### Module-Level WFC

The lab uses **module-level** WFC rather than raw tile-level. Each "module" is a fixed 6×6 tile grid representing a room, corridor section, or structural element. WFC assembles these modules into a dungeon by matching **socket patterns** on adjacent edges.

**Why module-level:**
- Rooms retain semantic meaning (spawn, enemy, loot, boss)
- Corridors naturally form between rooms
- Dungeon "feel" is controllable via module weights
- Output is directly compatible with the Arena game's room-based JSON map format

### Socket System

Sockets are **auto-derived** from edge tiles. Each module edge (N/S/E/W) is read as a 6-character string where each tile becomes `W` (wall) or `O` (open/passable). Two modules can be placed adjacent if their facing edge sockets are identical.

**Standard socket patterns:**
- `WWWWWW` — solid wall (no connection)
- `WWOOWW` — centered 2-wide corridor opening (standard passageway)

This means all corridor/room exits use the same standard opening pattern, ensuring universal compatibility.

### Rotation Variants

Modules with `allowRotation: true` are expanded into up to 4 variants (0°, 90°, 180°, 270°). Rotation is deduped — symmetric modules don't duplicate. This means a single L-turn module produces 4 directional variants automatically.

---

## File Structure

```
tools/dungeon-wfc/
├── index.html              # Entry point
├── package.json            # Dependencies (react, react-dom, vite)
├── vite.config.js          # Vite config (port 5185)
├── src/
│   ├── main.jsx            # React root mount
│   ├── App.jsx             # Root component, layout, state management
│   ├── styles/
│   │   └── App.css         # Full application styles (grimdark theme)
│   ├── engine/
│   │   ├── wfc.js          # WFC algorithm (collapse, propagation, assembly)
│   │   ├── connectivity.js # Flood-fill reachability, corridor stitching
│   │   ├── moduleUtils.js  # Module data structures, rotation, socket derivation, content roles
│   │   ├── presets.js      # 29 built-in preset modules (16 standard + 13 multi-module grand rooms) + size presets
│   │   └── roomDecorator.js # Post-generation room content decorator engine
│   ├── components/
│   │   ├── ModuleEditor.jsx    # Canvas tile painter with undo/redo, fill tool, rotation preview
│   │   ├── ModuleLibrary.jsx   # Sidebar module list with thumbnails, CRUD, category filter, socket compat
│   │   ├── GeneratorPanel.jsx  # WFC config, templates, batch gen, difficulty scoring, decorator controls, stats
│   │   ├── PreviewCanvas.jsx   # Full dungeon preview with zoom/pan, decorator role overlays
│   │   └── ExportPanel.jsx     # Export to game JSON, import existing maps
│   └── utils/
│       ├── tileColors.js   # Tile type → color mapping, socket helpers
│       └── exportMap.js    # Convert WFC output → Arena game map JSON (decorator-aware)
```

---

## Core Components

### WFC Engine (`engine/wfc.js`)

- **Seeded RNG** — Deterministic generation via mulberry32 PRNG. Same seed = same dungeon.
- **Entropy-based collapse** — Picks the cell with fewest remaining possibilities, weighted random selection among valid modules.
- **Constraint propagation** — BFS from collapsed cells, intersecting neighbor possibilities with compatibility tables.
- **Auto-retry** — On contradiction, retries with incremented seed (configurable max retries).
- **Precomputed adjacency** — Compatibility tables built once before generation for fast lookups.
- **Border wall constraint** — Forces outer-edge modules to have solid wall sockets on their outward-facing sides, preventing corridors from leading off the map edge.
- **Connectivity enforcement** — Post-generation flood-fill validates all walkable areas are reachable; corridor stitching carves minimal tunnels to connect isolated regions.

### Connectivity Engine (`engine/connectivity.js`)

- **Flood-fill region detection** — Identifies all disconnected walkable regions in the tile map.
- **A\* tunnel pathfinding** — Finds the shortest path between disconnected regions, tunneling through walls with higher cost to prefer existing open space.
- **Corridor stitching** — Carves 2-wide corridors along tunnel paths to connect isolated rooms to the main dungeon body.
- **Validation mode** — `validateConnectivity()` checks connectivity without modifying the map.
- **Region metrics** — Reports region count, sizes, and how many corridors were carved.

### Module Editor (`components/ModuleEditor.jsx`)

- Canvas-based 6×6 grid painter
- **Left-click** to paint the selected tile type, **right-click** to erase (paint wall)
- **Drag-to-paint** — hold and drag across tiles to paint continuously
- 8 tile types: Wall, Floor, Door, Corridor, Spawn, Chest, Enemy, Boss
- Live socket pattern display on all 4 edges
- Editable metadata: name, purpose, weight, allowRotation
- **Undo/Redo** — Ctrl+Z / Ctrl+Y (or Ctrl+Shift+Z) with per-stroke history (up to 50 levels)
- **Fill tool** — flood-fill a region of same-type tiles with the selected tile type
- **Rotation preview panel** — toggle to see all rotation variants (0°/90°/180°/270°) with their socket patterns, helping confirm module compatibility before generation

### Module Library (`components/ModuleLibrary.jsx`)

- Scrollable list with mini canvas thumbnails
- **CRUD:** New, Duplicate, Delete
- **Import/Export:** Save/load entire library as JSON
- Purpose badges (color-coded), rotation indicator, weight display
- **Auto-persisted** to localStorage
- **Category filter** — filter modules by purpose (All, Empty, Corridor, Spawn, Enemy, Loot, Boss) with count badges
- **Socket compatibility viewer** — for the selected module, shows which other modules can attach to each edge (N/S/E/W) based on matching socket patterns

### Generator Panel (`components/GeneratorPanel.jsx`)

- **Dungeon style templates:** Balanced, Dense Catacomb, Open Ruins, Boss Rush, Treasure Vault — each applies weight multipliers to modules by purpose to shape dungeon personality
- **Size presets:** Tiny (2×2 = 12×12), Small (3×3 = 18×18), Medium (4×4 = 24×24), Large (5×5 = 30×30)
- Seed input + randomize button
- **Constraint toggles:** Border Walls (force solid edges), Ensure Connected (auto-stitch)
- Max retries control
- **Batch generation:** Generate 1–50 dungeons at once, auto-ranked by quality (floor ratio, connectivity, spawn presence), pick the best result
- **Generate** and **Quick Random** (randomize seed + generate in one click)
- Status indicator (success/fail, retry count, step count, connectivity info)
- **Dungeon Stats:** floor ratio, tile counts by type, room counts
- **Difficulty scoring:** 0–100 score (Trivial → Nightmare) based on enemy density, boss presence, reward ratio, floor openness, door chokepoints, spawn scarcity

### Preview Canvas (`components/PreviewCanvas.jsx`)

- Full tile map rendering with zoom (scroll wheel) and pan (drag)
- **Module grid overlay** — dashed yellow lines showing module boundaries
- **Module labels** — variant name + rotation displayed per cell
- Toggle: grid overlay, tile labels
- Reset view button

### Export (`utils/exportMap.js` + `components/ExportPanel.jsx`)

- **Export Map JSON** — Downloads game-compatible JSON matching the `server/configs/maps/` format
  - Tile grid, rooms with bounds and purpose, doors, chests, spawn points/zones, enemy spawns
  - Enemy/Boss markers (E/B tiles) become floor tiles in the grid; enemies placed in `rooms[].enemy_spawns`
  - **Decorator-aware:** Scans the actual tileMap (including decorator placements) to detect room purpose dynamically, so flexible rooms that received content via the decorator export correctly
- **Copy to Clipboard** — JSON text copied directly
- **Import Existing Map** — Load any map JSON from `server/configs/maps/` to preview it

### Room Decorator Engine (`engine/roomDecorator.js`)

The decorator is a **post-generation pass** that assigns gameplay content (enemies, loot, boss, spawn) to structurally "empty" rooms. This decouples room **shape** from room **purpose**, making the 14 previously-empty modules (Dead End, Passthrough, Corner, Three-Way, Hub, and most Grand rooms) usable for any gameplay role.

**Content Roles:**
- `flexible` — Room shape only, no baked-in content tiles. The decorator can assign enemies, loot, boss, spawn, or leave empty.
- `fixed` — Has baked-in content tiles (Enemy Den, Treasury, Boss Chamber, Spawn Room, etc.). Decorator counts these but never overrides them.
- `structural` — Corridors, solid walls, and grand room interior pieces. Never receives content.

**Spawn Slots:**
Each flexible module defines `spawnSlots` — an array of `{row, col}` positions within the 6×6 grid where content tiles can be placed. These are hand-authored floor positions that make gameplay sense (open floor, not blocking doors). Example: a Dead End Room with 5 spawn slots in its interior.

**Decorator Phases:**
1. **Collect flexible rooms** — Scans the WFC grid for collapsed cells with `contentRole: 'flexible'`
2. **Count fixed rooms** — Tallies existing fixed-content rooms (enemy, loot, boss, spawn)
3. **Assign roles** — Guarantees boss/spawn rooms first (if enabled and not already present via fixed modules), then distributes remaining rooms based on density sliders:
   - `enemyDensity` (0.0–1.0) — Fraction of remaining rooms that become enemy rooms
   - `lootDensity` (0.0–1.0) — Fraction that become loot rooms
   - `emptyRoomChance` (0.0–1.0) — Probability any flexible room stays empty
4. **Place content tiles** — Writes actual tile characters (E/B/S/X) onto the tileMap at spawn slot positions, using seeded RNG to select which slots get content
5. **Compute stats** — Returns decoration summary (role counts, placement totals)

**Decorator Settings (UI controls):**
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enemyDensity` | slider 0–1 | 0.4 | Fraction of flexible rooms assigned as enemy rooms |
| `lootDensity` | slider 0–1 | 0.2 | Fraction assigned as loot rooms |
| `emptyRoomChance` | slider 0–1 | 0.2 | Per-room chance to skip decoration |
| `guaranteeBoss` | toggle | true | Ensure at least 1 boss room exists |
| `guaranteeSpawn` | toggle | true | Ensure at least 1 spawn room exists |
| `scatterEnemies` | toggle | true | Place E tiles at spawn slots in enemy rooms |
| `scatterChests` | toggle | true | Place X tiles at spawn slots in loot rooms |

**Module Metadata (per preset):**
| Field | Type | Description |
|-------|------|-------------|
| `contentRole` | `'flexible'` \| `'fixed'` \| `'structural'` | How the decorator treats this module |
| `spawnSlots` | `[{row, col}]` | Valid positions for content tile placement |
| `maxEnemies` | number | Max enemy tiles the decorator will place |
| `maxChests` | number | Max chest tiles the decorator will place |
| `canBeBoss` | boolean | Whether this module can be promoted to boss room |
| `canBeSpawn` | boolean | Whether this module can be used as a spawn point |

**RNG:** Uses its own mulberry32 PRNG seeded with `wfcSeed + 9999`, ensuring decorator results are deterministic and independent of WFC internals.

---

## Preset Module Library (29 modules)

| Module | Purpose | Content Role | Exits | Rotation | Weight | Description |
|--------|---------|-------------|-------|----------|--------|-------------|
| Solid Wall | empty | structural | 0 | No | 3.0 | Filler — all walls |
| Corridor Straight | corridor | structural | 2 (E+W) | Yes (→V) | 2.0 | Standard 2-wide corridor |
| Corridor L-Turn | corridor | structural | 2 (W+S) | Yes (×4) | 1.5 | L-shaped turn |
| Corridor T-Junction | corridor | structural | 3 (W+E+S) | Yes (×4) | 1.0 | T-intersection |
| Corridor Crossroads | corridor | structural | 4 | No | 0.5 | 4-way cross |
| Dead End Room | empty | **flexible** | 1 (S) | Yes (×4) | 1.0 | Small room, single exit — 5 spawn slots |
| Room Passthrough | empty | **flexible** | 2 (N+S) | Yes (→V) | 1.2 | Room with through-passage — 4 spawn slots |
| Room Corner | empty | **flexible** | 2 (S+E) | Yes (×4) | 1.0 | Corner room — 4 spawn slots |
| Room Three-Way | empty | **flexible** | 3 (W+E+S) | Yes (×4) | 0.8 | Three-exit room — 6 spawn slots |
| Room Hub | empty | **flexible** | 4 | No | 0.4 | Central hub room — 8 spawn slots |
| Spawn Room | spawn | fixed | 1 (S) | Yes (×4) | 0.3 | Starting area with S tiles |
| Enemy Den | enemy | fixed | 2 (S+E) | Yes (×4) | 1.5 | Room with E markers |
| Skeleton Hall | enemy | fixed | 2 (N+S) | Yes (→V) | 1.2 | Enemy passthrough |
| Treasury | loot | fixed | 1 (S) | Yes (×4) | 0.5 | Chest-filled dead end |
| Boss Chamber | boss | fixed | 1 (S) | Yes (×4) | 0.2 | Boss encounter room |
| Doored Corridor | corridor | structural | 2 (E+W) | Yes (→V) | 0.8 | Corridor with door tiles |
| **Grand Hall** | empty | **flexible** | 1 corridor + 1 interior | Yes (×4) | 0.5 | 2-module open room — 6 spawn slots |
| **Grand Hall Pillared** | empty | **flexible** | 1 corridor + 1 interior | Yes (×4) | 0.4 | 2-module room with pillars — 4 spawn slots |
| **Grand End** | empty | **flexible** | 0 exits + 1 interior | Yes (×4) | 0.4 | Dead-end cap — 6 spawn slots |
| **Grand Corner Closed** | empty | **flexible** | 0 exits + 2 interior | Yes (×4) | 0.3 | Sealed corner — 4 spawn slots |
| **Grand Corner Open** | empty | **flexible** | 1 corridor + 2 interior | Yes (×4) | 0.4 | Corner with exit — 4 spawn slots |
| **Grand Corner Double** | empty | **flexible** | 2 corridors + 2 interior | Yes (×4) | 0.3 | Corner with 2 exits — 4 spawn slots |
| **Grand Corner Pillared** | empty | **flexible** | 1 corridor + 2 interior | Yes (×4) | 0.35 | Pillared corner — 3 spawn slots |
| **Grand Enemy Den** | enemy | fixed | 1 corridor + 1 interior | Yes (×4) | 0.4 | 2-module enemy arena |
| **Grand Boss Arena** | boss | fixed | 0 exits + 2 interior | Yes (×4) | 0.1 | Boss encounter corner |
| **Grand Treasury** | loot | fixed | 1 corridor + 1 interior | Yes (×4) | 0.2 | 2-module treasure hall |
| **Grand Spawn Hall** | spawn | fixed | 1 corridor + 1 interior | Yes (×4) | 0.15 | Spacious starting area |
| **Grand Center** | empty | structural | 4 interior | No (symmetric) | 0.2 | Interior of 3×3+ rooms |
| **Grand Edge** | empty | structural | 1 wall + 3 interior | Yes (×4) | 0.25 | Edge of 3×3+ rooms |

### Multi-Module Room System

The 13 "Grand" modules use a special **interior join socket** (`WOOOOW`) on edges that connect to other room segments. Since no standard module has this pattern, the WFC is forced to place matching grand pieces adjacent to each other, naturally assembling large rooms.

**Room configurations possible:**
- **2-module rooms** (12×6 tiles) — Grand Hall + Grand End (dead-end), or Grand Hall + Grand Hall (through-room)
- **4-module rooms** (12×12 tiles) — 4 Grand Corner variants forming a massive chamber
- **9-module rooms** (18×18 tiles) — 4 corners + 4 Grand Edges + 1 Grand Center
- **Irregular rooms** — Mixing halls and corners creates L-shaped, T-shaped, and U-shaped rooms naturally

---

## Exported Map Format

Matches the existing Arena map format (`dungeon_test.json`, `open_catacombs.json`):

```json
{
  "name": "WFC Dungeon",
  "width": 24,
  "height": 24,
  "map_type": "dungeon",
  "spawn_points": [{ "x": 1, "y": 2 }, ...],
  "spawn_zones": { "a": { "x_min": 1, "y_min": 1, "x_max": 4, "y_max": 4 } },
  "ffa_points": [...],
  "rooms": [
    {
      "id": "room_0_1",
      "name": "Enemy Den",
      "purpose": "enemy",
      "bounds": { "x_min": 6, "y_min": 0, "x_max": 11, "y_max": 5 },
      "enemy_spawns": [{ "x": 8, "y": 1, "enemy_type": "demon" }]
    }
  ],
  "doors": [{ "x": 5, "y": 2, "state": "closed" }],
  "chests": [{ "x": 3, "y": 7 }],
  "tiles": [["W","W","F","F","W","W", ...], ...],
  "tile_legend": { "W": "wall", "F": "floor", "D": "door", "C": "corridor", "S": "spawn", "X": "chest" }
}
```

---

## Current Status

### Implemented (Core)
- [x] WFC engine with entropy-based collapse + constraint propagation
- [x] Seeded deterministic generation with auto-retry
- [x] 29 preset modules with auto-rotation expansion (including 13 multi-module grand room pieces)
- [x] Canvas-based module editor with tile painting
- [x] Module library with CRUD, thumbnails, localStorage persistence
- [x] 4 size presets (Tiny through Large, up to 30×30)
- [x] Dungeon preview with zoom/pan and module grid overlay
- [x] Export to game-compatible JSON (direct drop into server/configs/maps/)
- [x] Import existing maps for preview
- [x] Module library import/export as JSON files
- [x] Dungeon statistics panel
- [x] Quick Random generation (one-click randomize + generate)
- [x] Dark grimdark UI theme

### Implemented (Room Decorator System)
- [x] Content role system (`flexible` / `fixed` / `structural`) on all 29 modules
- [x] Spawn slot metadata on all flexible modules (hand-authored floor positions)
- [x] Post-generation room decorator engine with 5-phase content assignment
- [x] Decorator UI controls in GeneratorPanel (density sliders, guarantee toggles, scatter toggles)
- [x] Color-coded role badges on PreviewCanvas module overlay (`[ENEMY]`, `[LOOT]`, `[BOSS]`, `[SPAWN]`)
- [x] Decorator-aware export — flexible rooms with decorator content export correctly to game JSON
- [x] Decoration stats panel (role counts, placement totals)
- [x] Seeded deterministic decoration (mulberry32, offset from WFC seed)

### Implemented (QoL — February 2026)

#### Connectivity & Map Quality
- [x] Post-generation flood-fill connectivity validation
- [x] Automatic corridor stitching to connect isolated regions (A* through walls, 2-wide carved corridors)
- [x] Border wall constraint — force solid wall sockets on map edges (prevents corridors leading off-map)
- [x] Connectivity metrics displayed in generation result (regions found, corridors carved)

#### Module Editor Enhancements
- [x] Undo/Redo (Ctrl+Z / Ctrl+Y) — per-stroke history, 50-level stack
- [x] Fill tool — flood-fill a region with selected tile type
- [x] Drag-to-paint — hold and sweep across tiles to paint continuously
- [x] Paint/Fill tool toggle in toolbar
- [x] Rotation preview panel — see all rotation variants with socket patterns at a glance

#### Module Library Enhancements
- [x] Category filter — filter modules by purpose (All/Empty/Corridor/Spawn/Enemy/Loot/Boss) with count badges
- [x] Socket compatibility viewer — select a module and see which modules can attach to each edge

#### Generation Enhancements
- [x] 5 dungeon style templates (Balanced, Dense Catacomb, Open Ruins, Boss Rush, Treasure Vault) — apply weight multipliers by purpose
- [x] Batch generation — generate 1–50 dungeons at once, auto-ranked by quality metrics, pick the best
- [x] Difficulty scoring (0–100: Trivial/Easy/Moderate/Hard/Brutal/Nightmare) based on enemy density, boss presence, reward ratio, floor openness, doors, spawn scarcity

#### Decorator Polish (February 2026)
- [x] **Decorator template presets** — Dungeon templates (Balanced, Dense Catacomb, Open Ruins, Boss Rush, Treasure Vault) now also set decorator density defaults. E.g., Boss Rush → `enemyDensity: 0.6, guaranteeBoss: true`; Treasure Vault → `lootDensity: 0.5`.
- [x] **Re-decorate button** — Re-runs the decorator on an existing generation without re-running WFC. Preserves raw (pre-decoration) tileMap so users can tweak density sliders and see the effect instantly on the same dungeon layout.
- [x] **Decorator-aware difficulty scoring** — Updated difficulty formula factors in decorator room assignments (enemy-room ratio, multi-boss bonus, loot-to-enemy room ratio) alongside tile-level counts for more accurate scoring after decoration.
- [x] **Show All Modules swap** — Module picker now has a "Show All Modules" toggle that bypasses socket compatibility filtering, letting users hot-swap any module from the full library into any cell. Warning shown when socket mismatches may occur.


---

## How to Use

### Basic Workflow
1. **Launch:** Run `start-dungeon-wfc.bat` or `cd tools/dungeon-wfc && npm run dev`
2. **Browse modules:** Left sidebar shows all modules. Click to select & edit.
3. **Edit a module:** Paint tiles on the 6×6 grid. Set name, purpose, weight, rotation.
4. **Create modules:** Click "+ New" to create blank modules. "Dup" to duplicate.
5. **Generate:** In the right panel, choose a size preset, set seed, click Generate.
6. **Quick iterate:** Click "Quick Random" to randomize seed + generate in one action.
7. **Decorator:** The Room Decorator automatically runs after generation. Adjust density sliders in the "Room Decorator" section to control enemy/loot distribution.
8. **Re-decorate:** After generating, tweak decorator sliders (enemy/loot density, etc.) and click "Re-decorate" to re-apply decoration on the same dungeon layout — no WFC re-run needed.
9. **Preview:** Switch to "Dungeon Preview" tab. Scroll to zoom, drag to pan. Decorated rooms show color-coded role labels (`[ENEMY]`, `[LOOT]`, `[BOSS]`, `[SPAWN]`).
10. **Swap modules:** Click any module cell in the preview to open the swap picker. Toggle "Show All Modules" to pick from the full library (not just socket-compatible variants).
11. **Export:** Enter a map name, click "Export Map JSON" to download. Drop the file into `server/configs/maps/`.
12. **Import:** Click "Import Existing Map" to load and preview any map JSON.

### Editor Tools
- **Paint tool (✏️):** Click or drag across tiles to paint with the selected tile type. This is the default tool.
- **Fill tool (🪣):** Click a tile to flood-fill all connected tiles of the same type with the selected type.
- **Undo/Redo:** Click ↩/↪ buttons or press **Ctrl+Z** / **Ctrl+Y**. History is tracked per paint stroke (up to 50 levels).
- **Rotation Preview:** Toggle "Show Rotations" to see all generated rotation variants of the current module, including their socket patterns per edge.

### Library Features
- **Category filter:** Click purpose buttons (All / Empty / Corridor / Spawn / Enemy / Loot / Boss) to filter the module list. Count badges show how many modules exist in each category.
- **Socket compatibility:** Toggle "Show Compatibility" on a selected module to see which other modules can connect to each of its four edges.

### Generation Features
- **Dungeon Templates:** Click a template button (Balanced, Dense Catacomb, Open Ruins, Boss Rush, Treasure Vault) to auto-apply weight multipliers **and decorator density defaults** that bias generation toward a specific dungeon style.
- **Constraint toggles:**
  - *Force Border Walls* — ensures the map perimeter is solid walls (no corridors leading off-map).
  - *Ensure Connectivity* — after generation, detects disconnected regions and carves corridors to link them.
- **Batch generation:** Set a batch count (1–50) and generate multiple dungeons at once. Results are auto-ranked by floor coverage and natural connectivity. Pick the best from the ranked list.
- **Difficulty score:** After generation, a 0–100 difficulty score is displayed (Trivial → Nightmare) based on enemy density, boss presence, loot ratio, floor openness, door density, spawn scarcity, **and decorator room assignments when available**.

### Module Swap (Preview)
- **Click to swap:** Click any module cell in the dungeon preview to open the module picker.
- **Compatible mode (default):** Shows only modules whose sockets match all adjacent neighbors.
- **Show All Modules:** Toggle the "Show All Modules" checkbox to bypass socket filtering and pick **any** module from the full library. A warning is shown since socket mismatches at borders may occur.
- **Mini previews:** Each variant shows a tiny tile preview and rotation angle for quick identification.

### Room Decorator Controls
- **Enable/Disable:** Toggle the decorator on/off. When disabled, flexible rooms remain empty (purely structural).
- **Enemy Density (0–100%):** Controls what fraction of available flexible rooms become enemy rooms.
- **Loot Density (0–100%):** Controls what fraction become loot rooms.
- **Empty Room Chance (0–100%):** Per-room probability of staying empty even if selected for content.
- **Guarantee Boss:** Ensures at least one boss room exists — if no fixed boss modules are placed by WFC, promotes a flexible room.
- **Guarantee Spawn:** Ensures at least one spawn room exists.
- **Scatter Enemies / Chests:** When enabled, places actual E/X tiles at spawn slot positions in decorated rooms. When disabled, assigns the role but doesn't place tiles (useful for server-side content injection).
- **Re-decorate:** Click the "Re-decorate" button (appears after first generation) to re-run decoration with updated sliders on the same WFC layout. Uses the stored raw (pre-decoration) tileMap as a clean base.
- **Decoration Stats:** After generation, shows role assignment counts and total tile placements with color-coded badges.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Module size | 6×6 fixed | Clean math (30÷6=5), enough room interior (4×4), simple WFC |
| Socket derivation | Auto from edge tiles | No manual labeling, impossible to mismatch |
| Corridor width | 2-wide centered | Matches existing dungeon maps, comfortable for party movement |
| RNG | Seeded mulberry32 | Deterministic, reproducible dungeons |
| Persistence | localStorage | No backend needed, instant save/load |
| Export format | Existing Arena JSON | Zero integration work, drop-in compatible |
| Connectivity fix | Flood-fill + A* stitching | Detects all isolated walkable regions via BFS, then A* finds lowest-cost path through walls between closest region pairs; carves 2-wide corridors so parties can traverse naturally |
| Border constraint | Socket-level filtering | During WFC collapse, edge cells are restricted to variants with all-wall sockets on outward-facing sides — guarantees solid perimeter without post-processing |
| Difficulty scoring | Weighted 0–100 formula | 6 factors (enemy density 30pts, boss 20pts, loot ratio 15pts, floor tightness 15pts, doors 10pts, spawn scarcity 10pts) mapped to 6 named tiers for quick readability |
| Template system | Weight multipliers | Templates multiply existing module weights by purpose category, preserving relative ordering while shifting generation bias — simple, composable, no extra module authoring needed |
| Batch ranking | Quality score sort | floor_ratio + spawn_bonus + natural_connectivity_bonus; auto-sorts so best map is at top; keeps all results selectable for manual override |
| Undo granularity | Per-stroke, not per-tile | Painting 20 tiles in one drag = 1 undo step; keeps history useful and stack small |
| Content decoupling | Decorator post-pass | Separating room shape from purpose lets 14 empty modules serve any gameplay role; decorator assigns content after WFC collapse using density/guarantee settings |
| Spawn slots | Hand-authored per module | Auto-detection risks blocking doors or placing content in walls; hand-authored slots ensure every placement is on valid open floor |
| Decorator RNG | Offset seed (wfcSeed+9999) | Same WFC seed always produces the same decoration; offset prevents correlation with WFC collapse order |
| Template decorator defaults | Co-applied with weights | Selecting a dungeon template also sets matching decorator densities (e.g., Boss Rush → high enemy, guaranteed boss); keeps template selection a one-click experience |
| Re-decorate base | Stored rawTileMap | Pre-decoration tileMap is preserved in result so re-decorate always starts from a clean structural base including connectivity-carved corridors |
| Difficulty scoring | Tile + room hybrid | Tile-level counts (E/B/S/X) give granular accuracy; decorator room-level stats add context (enemy-room ratio, multi-boss penalty, loot scarcity) for more nuanced scores |
| Show All swap | Opt-in toggle | Default shows only socket-compatible modules for safety; opt-in "Show All" mode enables full creative control with a socket-mismatch warning |

---

## Remaining Implementation Steps

These are the next logical steps to fully realize the decorator system and expand the module library:

### High Priority — Decorator Polish
- [ ] **ModuleEditor spawn slot editing** — Visual UI for authoring/editing spawn slots directly in the 6×6 editor. Toggle "Slot Edit Mode" to click floor tiles and mark them as spawn slots. Display slots as overlay markers (distinct from tile paint).

### Medium Priority — New Module Variety
- [ ] **Trap Corridor** — Corridor variant with floor pressure-plates or spike tiles. Uses new `T` (trap) tile type.
- [ ] **Shrine Room** — Small room with a central shrine tile (`H` for holy/shrine). Single exit, canBeSpawn: true.
- [ ] **Guard Post** — 2-exit room with E tiles flanking the doorways. Fixed enemy content.
- [ ] **Armory** — Small room with X tiles along walls (weapon racks). Fixed loot content.
- [ ] **Prison Cells** — Passthrough room with small walled alcoves and door tiles. Flexible content.
- [ ] **Pit Room** — Room with a central impassable `P` (pit/void) tile surrounded by narrow walkable floor. Creates tactical choke.
- [ ] **Bridge Room** — Room bisected by a 2-wide `P` (void) gap with a narrow bridge. Forces single-file crossing.

### Medium Priority — Grand Room Expansion
- [ ] **Grand Throne Room** — 2-module boss variant with a raised dais area and boss spawn. Fixed boss content.
- [ ] **Grand Library** — 2-module loot variant with pillar-shelves pattern creating cover lanes. Fixed loot.
- [ ] **Grand Barracks** — 2-module enemy arena with bed/obstacle tiles and distributed E spawns. Fixed enemy.
- [ ] **Grand Ritual Chamber** — 4-module (2×2) boss arena with a central pattern and surrounding columns. canBeBoss: true.
- [ ] **Grand Trap Gauntlet** — 2-module corridor-scale run with trap tiles. Structural tension module.

### Lower Priority — New Tile Types
- [ ] **`T` — Trap tile** — Pressure plate, spike, or hazard. Exported as `trap` in the map JSON; server interprets as damage-on-step or trigger.
- [ ] **`H` — Shrine tile** — Holy/healing shrine. Exported as interactable point in room data.
- [ ] **`P` — Pit/Void tile** — Impassable gap (not a wall). Rendered distinctly from walls. Creates tactical terrain without blocking line of sight.
- [ ] **`L` — Lava/Water tile** — Hazardous terrain that is passable but applies damage or slow. Rendered with animated color.

---

## Future Feature Ideas

These are stretch goals and advanced features that could further enhance the dungeon generation system:

### Decorator Enhancements
- **Weighted content placement** — Instead of uniform random slot selection, weight spawn slots by distance from doors (enemies further from entrance, chests deeper in room).
- **Enemy type variety** — Decorator assigns enemy subtypes (skeleton, demon, wraith) based on dungeon depth/difficulty tier.
- **Loot tier scaling** — Chests near boss rooms or in harder-to-reach areas get higher loot tier tags.
- **Room theme propagation** — Adjacent decorated rooms influence each other (enemy rooms near boss room get more enemies; loot rooms near spawn get less loot).
- **Encounter budget system** — Instead of density sliders, use a total "encounter point budget" distributed across the dungeon. Boss costs 5 points, enemy room costs 2, loot costs 1.

### Generation Enhancements
- **Zone-based generation** — Define dungeon "zones" (entrance zone, mid zone, deep zone) with different decorator settings per zone. Entrance is safe, deep zone is dangerous.
- **Key/lock mechanics** — Special door tiles that require a key item. Generator places key in one room and locked door blocking access to another area.
- **Room connectivity graph** — Post-generation analysis showing room adjacency graph, critical path, dead-end depth, etc.
- **Narrative placement** — Tag certain rooms as "story rooms" for NPC placement, quest triggers, or lore items.

### Module System Enhancements
- **Module tags/biomes** — Tag modules with biomes (crypt, sewer, cave) and generate dungeons that blend or transition between biomes.
- **Asymmetric sockets** — Beyond `WWOOWW`, support wider openings, offset doors, or one-way passages.
- **Module frequency caps** — "At most 2 Boss Chambers per dungeon" enforced during WFC collapse.
- **Auto spawn-slot derivation** — Optional auto-detection of valid spawn slots from floor tiles (with manual override), to reduce authoring effort for new modules.
