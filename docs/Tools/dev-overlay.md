# Dev Overlay — Dungeon Observation Tool

**Phase:** Dev Tooling  
**Date:** March 2026  
**Status:** Complete

## Overview

The Dev Overlay is a client-side observation tool for debugging and monitoring dungeon instances (PVPVE). It provides god-view capabilities — clear fog of war, free camera movement, unit inspection, room boundary visualization, and more — so developers can observe what is happening across the entire dungeon in real time.

The overlay is toggled with the **backtick (`)** key during any active match. All features are purely client-side and do not affect server state or gameplay.

---

## Features

### 1. Dev Mode Toggle — `` ` `` key
- Press **backtick** during a match to open/close the dev overlay panel
- A subtle "DEV MODE" banner appears at the top-center of the screen when active
- All dev features deactivate automatically when dev mode is closed or the match ends

### 2. Clear Fog of War — `Fog OFF` button
- **Removes all fog rendering** — the entire dungeon map is fully visible
- Revealed/unexplored tile states are bypassed; every tile renders at full brightness
- When fog is cleared, all units are also visible (no FOV filtering on tiles)
- Toggle on/off independently; re-enabling restores normal fog behavior

### 3. Free Camera — `Free Cam` button
- **Detaches the viewport** from the player character
- Use **arrow keys** to pan the camera across the map (2 tiles per press)
- WASD movement still works for your character while free camera is active
- Arrow keys are intercepted in the capture phase, so they don't trigger character movement
- **Reset Cam** button snaps the viewport back to the player and disables free camera
- Camera starts at the current viewport position when first enabled

### 4. Show All Units — `All Units` button
- **Renders all units** on the map regardless of fog of war
- Works independently from the fog toggle — fog can still be visible while all units are shown
- Adds type labels above each unit (BOSS, RARE, CHAMP, MOB, ALLY, YOU)
- Useful for tracking enemy positions, patrol routes, and spawn behavior through fog

### 5. Grid Coordinates — `Coords ON` button
- **Displays (x,y) tile coordinates** on every visible tile
- Rendered as small monospace labels at the bottom of each tile with a dark background pill
- Essential for debugging position-related issues, spawn points, and pathfinding

### 6. Room Boundaries — `Rooms ON` button
- **Highlights dungeon room boundaries** with colored rectangles and dashed borders
- Each room gets a unique color from a cycling palette (8 colors)
- Room archetype labels (e.g., "R0: combat", "R3: treasure") are displayed in the top-left corner
- Useful for verifying WFC dungeon generation, room placement, and decorator assignments

### 7. Spawn Points — `Spawns ON` button
- **Highlights spawn point tiles** with a golden overlay and "S" marker
- Detects all tile types mapped to `spawn`, `player_spawn`, or `enemy_spawn` in the tile legend
- Useful for verifying spawn placement and density

### 8. Unit Inspector — `Inspect ON` toggle + click
- Toggle the **🔍 Inspect ON/OFF** button in the dev panel to enter inspect mode
- When inspect mode is active, **left-click** any visible unit to inspect detailed stats in the panel
- Gameplay clicks are suspended while inspect mode is on — clicks only inspect, they don't move or target
- Cursor changes to a help/magnifying icon while inspect mode is active for clear visual feedback
- Displays: ID, class, HP, position, team, unit type, enemy type, rarity, champion type, stance, buffs, affixes, attack power, defense
- Inspector auto-updates every tick as the unit's stats change
- Uses the pre-computed `occupiedMap` for O(1) tile→unit lookup
- Click the **✕** button to close the inspector, or toggle inspect mode off to resume gameplay

### 9. Live Stats Dashboard
- Always visible at the top of the dev panel
- Shows: total alive units, ally/enemy breakdown
- Boss and elite counts (when present)
- Room count from dungeon generation
- Current cursor tile position
- Camera offset (when free camera is active)

---

## File Summary

### New Files

| File | Purpose |
|------|---------|
| `client/src/hooks/useDevOverlay.js` | React hook managing all dev overlay state, keyboard shortcuts, viewport overrides |
| `client/src/components/DevOverlay/DevOverlayPanel.jsx` | Floating UI panel with toggle buttons, stats, and unit inspector |
| `client/src/canvas/devRenderer.js` | Canvas rendering functions: grid coords, room bounds, spawn markers, unit labels |
| `client/src/styles/components/_dev-overlay.css` | Grimdark-themed CSS for the dev panel, toggles, inspector, and banner |

### Modified Files

| File | Change |
|------|--------|
| `client/src/components/Arena/Arena.jsx` | Integrated `useDevOverlay` hook, effective viewport/fog overrides, dev rendering in rAF loop, `DevOverlayPanel` component, inspect-mode click handler with `occupiedMap` lookup, inspect cursor feedback |
| `client/src/canvas/ArenaRenderer.js` | Added `showAllUnits` parameter to `renderFrame()`, bypasses FOV unit check when active |
| `client/src/styles/main.css` | Added `_dev-overlay.css` import |

---

## Architecture

```
Arena.jsx
├── useDevOverlay()           ← hook manages all dev state
│   ├── devMode toggle        ← backtick key listener
│   ├── effectiveViewport     ← overrides viewport when free cam active
│   ├── effectiveVisibleTiles ← null when fog disabled
│   └── free cam arrow keys   ← capture-phase keydown handler
│
├── renderParamsRef           ← injects dev state into render loop
│   ├── visibleTiles          ← uses effectiveVisibleTiles
│   ├── viewport              ← uses effectiveViewport
│   └── showAllUnits          ← passed to renderFrame()
│
├── rAF render loop
│   ├── renderFrame()         ← normal game rendering (with showAllUnits param)
│   └── Dev canvas rendering  ← drawDevRoomBounds, drawDevSpawnMarkers, etc.
│
├── handleDevCanvasClick()    ← Inspect-mode click handler (occupiedMap lookup)
│
└── <DevOverlayPanel />       ← floating UI panel
```

### Viewport Override Flow

```
useHighlights() → viewport (centered on player)
                      ↓
useDevOverlay()  → effectiveViewport (free cam offset OR normal viewport)
                      ↓
Used by: renderParamsRef, particleManager, useCanvasInput, MinimapPanel
```

### Fog Override Flow

```
Game state → visibleTiles (server-sent FOV)
                  ↓
useDevOverlay() → effectiveVisibleTiles (null when fog disabled, normal otherwise)
                  ↓
Used by: renderParamsRef → renderFrame() → drawFog() returns early if null
```

---

## Keyboard Shortcuts

| Key | Action | Context |
|-----|--------|---------|
| `` ` `` (backtick) | Toggle dev mode on/off | During any active match |
| **Arrow keys** | Pan free camera (2 tiles/press) | Only when free cam is active |
| **Left-click** | Inspect unit on clicked tile | When inspect mode is toggled ON |
| **WASD** | Still moves character | Works normally alongside free cam |

---

## UI Layout

The dev panel appears as a floating overlay in the **top-right corner** of the screen (z-index: 9999). It does not interfere with the minimap, party panel, or other UI elements which are positioned within the arena layout grid.

The "DEV MODE" banner appears centered at the **top edge** of the screen as a subtle, non-interactive indicator.

---

## Design Decisions

1. **Client-side only** — No server modifications required. All dev features are pure client-side rendering overrides. This means the overlay works with existing server code without any protocol changes.

2. **Capture-phase arrow key interception** — When free camera is active, arrow keys are handled with `{ capture: true }` event listeners that fire before the `useWASDMovement` bubble-phase listeners. This prevents arrow keys from triggering character movement while allowing WASD to continue working.

3. **Dedicated inspect mode toggle** — Instead of Shift+Click (which conflicted with party multi-select), inspect mode is a dedicated toggle button in the panel. When active, all left-clicks on the canvas inspect units; when off, clicks pass through to normal gameplay. This eliminates modifier-key conflicts and matches the existing toggle-button UI pattern.

4. **Additive canvas rendering** — Dev overlays (grid coords, room bounds, spawn markers, unit labels) are drawn AFTER `renderFrame()` completes in the rAF loop, so they layer on top without modifying the core rendering pipeline.

5. **Single `showAllUnits` param** — Rather than creating a synthetic full-map `visibleTiles` Set, a boolean flag was added to `renderFrame()` that simply bypasses the FOV check in the unit rendering loop. This is a minimal, surgical change to the renderer.

---

## Test Impact

No existing tests affected. The dev overlay is a purely additive client-side feature with:
- No server protocol changes
- No game state mutations
- No modifications to existing rendering logic (only an additive `showAllUnits` bypass)
- Auto-disables when match ends (cleanup in `useDevOverlay`)
