# Minimap System

Roguelike-style minimap rendered on a dedicated DOM canvas in the right panel.

## Overview

The minimap provides a compact bird's-eye view of the entire dungeon or arena map, positioned as an **absolute overlay in the top-right corner of the canvas area**. It respects fog of war, shows friendly and enemy unit positions, and highlights the player's current viewport on larger maps.

**Two modes:**
- **Normal** (default, always visible) — compact 7px/tile overview
- **Expanded** (press **M**) — enlarged 14px+/tile, detailed view

The minimap is always visible during a match. Press **M** to toggle between normal and expanded views. Toggling does **not** shift the viewport or any other panels — the minimap simply grows in place as an overlay.

## Visual Design

| Element | Color | Notes |
|---------|-------|-------|
| Walls | `#2a2a3a` | Solid dark |
| Floors | `#1a1a2e` | Subtle dark blue |
| Corridors | `#151528` | Slightly darker than floors |
| Doors (closed) | `#8B4513` | Brown |
| Doors (open) | `#A0764B` | Lighter brown |
| Chests (unopened) | `#DAA520` | Gold |
| Chests (opened) | `#8B7355` | Dimmed gold |
| Stairs | `#88CC88` | Green |
| Portal | `#9933ff` | Pulsing purple |
| Unexplored tiles | `#000000` | Solid black |
| Revealed (not in FOV) | Dimmed terrain | `rgba(0,0,0,0.55)` overlay |
| **Player (self)** | **White (blinking)** | Alternates at ~500ms |
| Friendly units | `#4a9ff5` (blue) | Only if in FOV |
| Enemy units | `#f54a4a` (red) | Only if in FOV |
| Boss enemies | `#ff2222` (larger blip) | 1px larger in each direction |
| Viewport rectangle | Cyan `rgba(0,230,255,0.7)` | Only shown when map exceeds viewport |
| Arena obstacles | `#3a3a4a` | For arena (non-dungeon) maps |

### Sizing

| Mode | Tile Size | 25×25 map | 20×20 map | Notes |
|------|-----------|-----------|-----------|-------|
| Normal | 7px/tile | 175×175px | 140×140px | Compact, always visible |
| Expanded | 14–18px/tile | 350–450px | 280–360px | Larger detailed view |

- **Panel padding:** 4px inside border
- **Background:** `var(--bg-panel)` normal / `var(--bg-surface)` expanded (matches other panels)
- **Border:** `var(--border-subtle)` normal / `var(--border-medium)` expanded
- **No header/title** — clean canvas-only presentation

## Architecture

### Files Modified

| File | Change |
|------|--------|
| `client/src/canvas/minimapRenderer.js` | Refactored — `drawMinimap()` now accepts `tileSize` param, draws at (0,0) on its own canvas. Exports `getMinimapSize()` and tile size constants. |
| `client/src/components/MinimapPanel/MinimapPanel.jsx` | Dedicated React component with its own `<canvas>`, absolute-positioned overlay |
| `client/src/canvas/ArenaRenderer.js` | Removed minimap drawing from `renderFrame()` — minimap is now a separate DOM element |
| `client/src/hooks/useKeyboardShortcuts.js` | M key now toggles `minimapMode` ('normal'/'expanded') instead of show/hide |
| `client/src/components/Arena/Arena.jsx` | Wires `minimapMode` + game state to `<MinimapPanel>` inside the canvas area |
| `client/src/styles/main.css` | 3-column grid layout (`260px 1fr 280px`), `.minimap-wrap` absolute overlay styles |

### Data Flow

```
useKeyboardShortcuts  →  minimapMode ('normal' | 'expanded')
        ↓
   Arena.jsx          →  passes minimapMode + all game state to <MinimapPanel>
                          (rendered as absolute overlay inside the canvas area)
        ↓
   MinimapPanel.jsx   →  owns a dedicated <canvas>, calls drawMinimap() on every render
        ↓
   minimapRenderer.js →  draws map, FOV, blips, viewport rect onto minimap canvas
```

### Render Approach

The minimap is now a **separate DOM canvas** in the right panel, not drawn on the main game canvas. This means:
- No overlap with game content
- CSS controls positioning and sizing
- The minimap canvas re-renders independently via React effects
- Smooth CSS transitions between normal/expanded modes

### FOV Behavior

The minimap fully respects the fog of war system:

- **Unexplored tiles** — solid black, no information revealed
- **Revealed tiles** (explored but not currently in FOV) — terrain visible but dimmed
- **Visible tiles** (currently in FOV) — full-color terrain
- **Enemies** — only shown on tiles that are currently in `visibleTiles` (no cheating)
- **Self** — always shown regardless of FOV
- **Allies** — only shown when in FOV
- **Arena mode** (no `revealedTiles`) — standard behavior, no dim overlay

### Keyboard Shortcut

Registered in `useKeyboardShortcuts.js` following the same pattern as other shortcuts:

- **Key:** M (case-insensitive)
- **Action:** Toggles between `'normal'` and `'expanded'` minimap modes
- **Guard:** Only active during `matchStatus === 'in_progress'`
- **Ignored:** When focus is on `INPUT`/`TEXTAREA` elements
- **Ignored:** When modifier keys (Ctrl, Meta, Alt) are held
- **Default:** `minimapMode = 'normal'` (compact, always visible)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Render target | Dedicated DOM canvas in right panel | No overlap with game content, CSS controls layout, uses empty right-panel real estate |
| Normal tile size | 7px per tile | Readable on all map sizes (12×12 to 25×25) — larger default for better visibility |
| Expanded tile size | 14–18px per tile | Large detailed view for dungeon exploration |
| Position | Absolute overlay, top-right of canvas area | Doesn't affect grid layout, toggling M never shifts viewport or panels |
| FOV respect | Full | Prevents minimap from being a "cheat map" — matches server FOV rules |
| Self indicator | Blinking white | Instantly findable among other blips |
| Boss indicator | Larger red blip | Matches main canvas treatment (larger radius for bosses) |
| M key behavior | Toggle normal ↔ expanded | Always visible — M enlarges for detail instead of hiding |
| Viewport rectangle | Cyan outline (thicker in expanded) | Matches the game's primary UI accent color |
| Theme matching | Uses `--bg-panel`, `--border-subtle` CSS vars | Consistent with Party Panel, Enemy Panel, and other HUD elements |
| No header/title | Canvas only, no "MAP" label or "M" badge | Cleaner, less cluttered presentation |
