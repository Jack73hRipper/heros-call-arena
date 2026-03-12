# Loot System Overhaul

> **Status**: Design Phase  
> **Created**: 2025-02-17  
> **Goal**: Transform the loot system from a barely-functional afterthought into a satisfying, keyboard-friendly, Diablo 2-inspired experience.

---

## Table of Contents

1. [Current System Overview](#1-current-system-overview)
2. [Known Issues](#2-known-issues)
3. [Recommended Changes](#3-recommended-changes)
4. [Implementation Checklist](#4-implementation-checklist)

---

## 1. Current System Overview

### 1.1 Server Architecture

**Core Files:**
- `server/app/core/loot.py` (324 lines) — Loot engine: item creation, pool rolling, enemy/chest loot generation
- `server/app/core/turn_resolver.py` — `_resolve_loot()` at Phase 1.75, `_resolve_deaths()` at Phase 3.5
- `server/app/core/match_manager.py` — Initializes `chest_states` and `ground_items` at match start
- `server/app/core/equipment_manager.py` — Equip/unequip/transfer items between slots and inventory

**Config Files:**
- `server/configs/items_config.json` — 18 items (weapons, armor, accessories, consumables) across 2 rarity tiers (common, uncommon)
- `server/configs/loot_tables.json` — 11 enemy loot tables + 2 chest tables with weighted pools
- `server/configs/merchant_config.json` — Merchant sells common items only; uncommon is loot-exclusive

### 1.2 How Loot Drops Work

**Enemy Death (Phase 3.5 — `_resolve_deaths`):**
1. Dead enemy's `enemy_type` is looked up in `enemy_loot_tables`
2. Roll against `drop_chance` (e.g., demon 60%, undead_knight 100%)
3. Pick `randint(min_items, max_items)` items from weighted pools
4. If `guaranteed_rarity: "uncommon"`, first item forced to uncommon tier
5. Items serialized and placed into `ground_items["x,y"]` at death position
6. `loot_drops` event appended to turn results (FOV-filtered for broadcast)

**Chest Opening (Phase 1.75 — `_resolve_loot`):**
1. Player sends `loot` action targeting a chest tile
2. Must be cardinally adjacent to an `"unopened"` chest
3. `roll_chest_loot("default")` generates 1-2 items
4. Items go directly into player inventory; overflow goes to ground at chest tile
5. Chest state changes to `"opened"`

**Ground Pickup (Phase 1.75 — `_resolve_loot`):**
1. Player sends `loot` action (no chest target)
2. Server checks `ground_items` at the player's **current position**
3. Picks up ALL items on tile (up to inventory capacity of 10)
4. No item selection — grabs everything, first-in-list priority

### 1.3 Data Structures

```
MatchState.ground_items: dict[str, list]
  Key:   "x,y" string (e.g., "5,3")
  Value: list of serialized Item dicts [{item_id, name, type, rarity, ...}, ...]

PlayerState.inventory: list (max 10 slots)
PlayerState.equipment: dict {weapon, armor, accessory}
```

### 1.4 Client Architecture

**State Management:**
- `GameStateContext.jsx` — `groundItems: {}` in initial state
- `combatReducer.js` — `TURN_RESULT` handler updates `groundItems` from server's `ground_items`
- `inventoryReducer.js` — Handles equip/unequip/transfer (not pickup)

**Rendering:**
- `overlayRenderer.js` → `drawGroundItems()` — Pulsing sparkle icons on loot tiles, color-coded by rarity, count badges
- `overlayRenderer.js` → `drawLootHighlight()` — Dashed gold border when active unit stands on items
- Only rendered in dungeon maps (`isDungeon` gate in Arena.jsx)

**Pickup Trigger:**
- Smart right-click only (via `pathfinding.js` → `generateSmartActions()`)
- Right-click loot tile → generates path-to-tile + loot action as batch
- No keyboard shortcut exists
- Old loot button was removed; prompt text still references it

**Broadcast (tick_loop.py):**

| Field | Frequency | Content |
|-------|-----------|---------|
| `ground_items` | Every tick | Full ground items dict (NOT FOV-filtered) |
| `loot_drops` | On enemy death | FOV-filtered `{x, y, enemy_type, items}` |
| `chest_opened` | On chest open | `{x, y, items, added_to_inventory, overflow}` |
| `items_picked_up` | On pickup | `{player_id, items}` |
| `my_inventory` | Every tick | Player's current inventory (private) |
| `my_equipment` | Every tick | Player's current equipment (private) |

### 1.5 Current Keyboard Shortcuts (for reference)

| Key | Action |
|-----|--------|
| Ctrl+A | Select all alive party members |
| F1–F4 | Select individual party member |
| Ctrl+1–4 | Set stance (follow/aggressive/defensive/hold) |
| Escape | Clear queue, auto-target, action mode |
| Tab / Shift+Tab | Cycle through visible enemies |
| *(none)* | Loot pickup |
| *(none)* | Show ground item labels |

---

## 2. Known Issues

### 2.1 Critical / Gameplay-Breaking

| # | Issue | Location | Details |
|---|-------|----------|---------|
| C1 | **Loot prompt references removed button** | `Arena.jsx:443` | Says "Press 🎒 Loot to pick up" but no loot button exists. Players see the prompt but have no obvious way to act on it. |
| C2 | **No keyboard shortcut for loot pickup** | `useKeyboardShortcuts.js` | Zero loot bindings. Standing on items with no keyboard path to pick them up. |
| C3 | **Right-click own tile is unintuitive** | `useCanvasInput.js` | The only way to pick up loot is smart right-click, which requires right-clicking your own tile — not discoverable. |
| C4 | **No item selection on pickup** | `turn_resolver.py:405` | Server grabs ALL items on tile. Players can't choose what to take. Full inventory? First-in-list wins. |

### 2.2 Bugs

| # | Issue | Location | Details |
|---|-------|----------|---------|
| B1 | **`ground_items` not FOV-filtered** | `tick_loop.py:302` | All ground items sent to all players every tick — loot visible through unexplored fog (wall-hack). |
| B2 | **`boss_chest` loot table is dead code** | `turn_resolver.py:436` | `_resolve_loot()` always calls `roll_chest_loot("default")`. No chest-type distinction exists in `chest_states`. |
| B3 | **`validate_loot_tables()` never called** | `loot.py:298` | Validation function exists but isn't invoked at startup. Misconfigured tables silently produce `None` items. |
| B4 | **Orphaned CSS for removed loot button** | `main.css`, `main-classic.css` | `.btn-loot` / `.btn-loot.active` / `.btn-loot:disabled` styles are unused dead code. |

### 2.3 Missing Features / Polish

| # | Issue | Details |
|---|-------|---------|
| M1 | No way to preview ground items | Players see a sparkle + count but not item names, types, or stats. |
| M2 | No ALT-to-show-labels | No Diablo 2 style label overlay for ground loot. |
| M3 | No pickup visual feedback | Items silently vanish. No floater text or animation. |
| M4 | No drop animation | Loot appears instantly on death — no spawn effect. |
| M5 | No gold drops from enemies | Gold only awarded post-match by kill count. |
| M6 | Ground loot persists forever | No decay/despawn — unbounded growth in long matches. |
| M7 | Hero death drops nothing | Permadeath heroes lose all gear — items aren't dropped on ground. |
| M8 | Loot only in dungeons | Arena/PvP maps skip loot entirely even when enemies die. |
| M9 | No inventory-full warning | No feedback when pickup fails due to full inventory. |

---

## 3. Recommended Changes

### 3.1 `E` — Unified Interact Key

**Concept:** Press `E` to interact with whatever is on/adjacent to the active unit's tile. This replaces the removed loot button and provides a keyboard-first experience.

**Behavior Priority:**
1. Standing on ground items → open loot pickup (see 3.2)
2. Adjacent to unopened chest → open loot and pick up items
3. Adjacent to closed door → open door
4. Nothing to interact with → brief "Nothing here" feedback

**Implementation:**
- Client: Add `E` binding in `useKeyboardShortcuts.js`
- Client: Determine context (ground items? chest? door?) and send appropriate action
- Server: No changes needed — `loot` and `interact` action types already exist

**Status:** ✅ COMPLETE

**Changes Made:**
- `client/src/hooks/useKeyboardShortcuts.js` — Added new `useEffect` block for `E` key with context-sensitive priority chain:
  1. Ground items on player's tile → sends `loot` action
  2. Adjacent unopened chest (cardinal) → sends `loot` action targeting chest
  3. Adjacent closed door (8-directional Chebyshev) → sends `interact` action
  4. Nothing found → combat log feedback "Nothing to interact with here."
- `client/src/hooks/useKeyboardShortcuts.js` — Added `groundItems`, `doorStates`, `chestStates`, `isDungeon` to hook params
- `client/src/components/Arena/Arena.jsx` — Passes new dungeon state props to `useKeyboardShortcuts`
- `client/src/components/Arena/Arena.jsx` — Fixed loot prompt text from "Press 🎒 Loot" to "Press E to pick up" (3.9)
- Supports ally control: when controlling a party member (`isControllingAlly`), `E` uses the ally's position and sends `unit_id`
- Chest adjacency uses cardinal directions (matching server's `_is_cardinal_adjacent`); door adjacency uses 8-directional (matching server's `_is_chebyshev_adjacent`)

---

### 3.2 Item Selection Popup

**Concept:** When pressing `E` on a tile with multiple items, show a small pickup list instead of grabbing everything blindly.

**Behavior:**
- Single item on tile → pick up immediately (no popup)
- Multiple items → show popup list with item names, rarity colors, and a "Take All" option
- Player clicks an item or presses number key (1-9) to pick up specific items
- `Shift+E` or "Take All" button picks up everything (up to inventory capacity)
- Popup auto-closes when all items are taken or player moves/presses Escape

**Implementation:**
- Client: New `LootPopup` component (overlay near the tile or bottom of screen)
- Client: New state: `lootPopupItems`, `lootPopupOpen`
- Server: New action variant — `loot` with optional `item_index` or `item_id` param for single-item pickup
- Server: Modify `_resolve_loot()` to support picking specific items, not just "take all"

---

### 3.3 ALT-to-Show-Labels (Diablo 2 Style)

**Concept:** Hold `ALT` to reveal floating item name labels above all visible ground loot tiles.

**Behavior:**
- Labels appear above each loot tile showing item names (one per line if stacked)
- Color-coded by rarity: white = common, green = uncommon (future: blue/purple/gold)
- Labels are FOV-filtered — only show on visible tiles
- Labels disappear when ALT is released
- Optional: labels are clickable while visible — clicking a label queues a path-to + pickup action

**Implementation:**
- Client: Track `altHeld` state in `useKeyboardShortcuts.js` (keydown/keyup)
- Client: New `drawGroundItemLabels()` function in `overlayRenderer.js`
- Client: Pass `altHeld` into `renderFrame()` and draw labels when true
- Server: No changes needed

**Status:** ✅ COMPLETE

**Changes Made:**
- `client/src/hooks/useKeyboardShortcuts.js` — Added `altHeld` state via `useState`. New `useEffect` listens for `keydown`/`keyup`/`blur` events on the `Alt` key. Prevents default to avoid browser menu bar activation. Returns `{ altHeld }` from the hook.
- `client/src/canvas/overlayRenderer.js` — New `drawGroundItemLabels()` function renders floating Diablo 2-style item name labels above all visible ground loot tiles. Features:
  - Rarity-colored text (white=common, green=uncommon, blue=rare, purple=epic, orange=legendary)
  - Semi-transparent dark background with rounded corners and rarity-colored border
  - Multiple items on one tile stack vertically upward with a slight rightward stagger (6px per item) for clear visual separation
  - FOV-filtered — only labels on visible tiles are rendered
- `client/src/canvas/ArenaRenderer.js` — Added `drawGroundItemLabels` to imports and re-exports. Added `altHeld` param to `renderFrame()`. Labels render after fog overlay but before damage floaters so they stay readable.
- `client/src/components/Arena/Arena.jsx` — Destructures `{ altHeld }` from `useKeyboardShortcuts` return value. Passes `altHeld` to `renderFrame()` and includes it in the render `useEffect` dependency array.

**Label Rendering Details:**
- Rendered above the tile (offset upward so they don't overlap the sparkle icon)
- Semi-transparent dark background behind text for readability
- If multiple items on one tile, stack labels vertically or show "Item Name (+N more)"
- Use the same rarity color scheme as the existing sparkle system

---

### 3.4 Pickup Floater Text

**Concept:** When items are picked up, show floating text (like damage numbers) rising from the tile.

**Behavior:**
- Gold-colored text: "+Item Name" floats upward and fades
- Multiple items picked up → stagger the floaters vertically
- Rarity color applied to item name

**Implementation:**
- Client: Extend existing damage floater system in `overlayRenderer.js`
- Client: On `items_picked_up` in `TURN_RESULT`, create floater entries
- Server: No changes needed

---

### 3.5 Loot Drop Animation

**Concept:** Brief visual effect when loot first hits the ground (enemy death / chest overflow).

**Behavior:**
- Small sparkle burst or "pop" effect on the tile when items appear
- Fade into the existing pulsing sparkle indicator after ~0.5s

**Implementation:**
- Client: Track `newLootTiles` from `loot_drops` in turn results
- Client: Render a brief particle/flash effect at those positions
- Client: Clear after animation completes

---

### 3.6 FOV-Filter Ground Items

**Concept:** Fix the wall-hack bug where all ground items are visible to all players regardless of fog of war.

**Implementation:**
- Server: In `tick_loop.py`, filter `ground_items` against the player's `visible_tiles` set before including in payload (same approach used for `loot_drops`)
- Alternative: Client-side filter using existing `visibleTiles` set (less secure but simpler)
- Recommended: Server-side for security, client already handles FOV gate for rendering

---

### 3.7 Ground Item Hover Tooltip

**Concept:** Hovering over a loot tile shows item details in the existing tile tooltip.

**Behavior:**
- Current tooltip already shows "✦ N item(s) on ground" — enhance with actual item names
- Show: item name, rarity, type (weapon/armor/etc)
- If many items, show first 3-4 + "and N more..."

**Implementation:**
- Client: Extend tooltip logic in `Arena.jsx` tile tooltip section
- Client: Look up items from `groundItems[key]` and format names with rarity colors
- Server: No changes needed (ground items already include full item data)

---

### 3.8 Inventory Full Warning

**Concept:** Clear visual feedback when player tries to pick up items but inventory is full.

**Behavior:**
- Red floater text: "Inventory Full!" above the player's tile
- Optional: brief red flash on inventory panel
- Still show what items are on the ground so player knows what they're missing

**Implementation:**
- Client: Check `inventory.length >= 10` before sending loot action, show warning
- Server: Already returns failure message, but client doesn't surface it visually
- Could also add server-side `inventory_full` flag in turn results

---

### 3.9 Fix Loot Prompt Text

**Concept:** Update the misleading prompt that references the removed loot button.

**Current:** `"✦ Items here! Press 🎒 Loot to pick up"`  
**New:** `"✦ Items here! Press E to pick up"` (or `"Press E to loot"`)

**Implementation:**
- Client: Single text change in `Arena.jsx:443`

**Status:** ✅ COMPLETE — Prompt now says "Press E to pick up".

---

### 3.10 Boss Chest Support

**Concept:** Make the existing `boss_chest` loot table actually work.

**Implementation:**
- Server: Add chest type to `chest_states` (e.g., `"unopened:boss"` or a richer data structure)
- Server: Map files need a way to designate boss chests vs regular chests
- Server: `_resolve_loot()` reads chest type and calls `roll_chest_loot("boss_chest")` accordingly
- Client: Optional visual distinction (different sparkle color or icon for boss chests)

---

### 3.11 Loot Table Validation at Startup

**Concept:** Call `validate_loot_tables()` during server initialization to catch config errors early.

**Implementation:**
- Server: Call `validate_loot_tables()` in `main.py` app startup or in `_init_dungeon_state()`
- Log warnings for invalid item references instead of silently producing `None`

---

### 3.12 Clean Up Dead Code

**Concept:** Remove orphaned loot button CSS and any other remnants.

**Implementation:**
- Client: Remove `.btn-loot` / `.btn-loot.active` / `.btn-loot:disabled` from `main.css` and `main-classic.css`
- Client: Remove any other references to the old loot button

---

## 4. Implementation Checklist

Priority tiers:
- **P0** — Fix broken things / core functionality
- **P1** — Key experience improvements
- **P2** — Polish and nice-to-haves

### P0 — Critical Fixes

- [x] **3.9** — Fix loot prompt text (references removed button)
- [x] **3.1** — Add `E` as unified interact key (loot pickup + chest + door)
- [ ] **C4/3.2** — Item selection on pickup (popup for multi-item tiles, immediate for single)
- [ ] **3.6** — FOV-filter `ground_items` in tick broadcast

### P1 — Core Experience

- [x] **3.3** — ALT-to-show-labels (Diablo 2 style floating item names)
- [ ] **3.7** — Ground item hover tooltip (item names + rarity in tile tooltip)
- [ ] **3.4** — Pickup floater text (gold "+Item Name" rising animation)
- [ ] **3.8** — Inventory full warning (red floater + feedback)
- [ ] **3.11** — Call `validate_loot_tables()` at server startup

### P2 — Polish

- [ ] **3.5** — Loot drop animation (sparkle burst on new drops)
- [ ] **3.10** — Boss chest support (use existing `boss_chest` loot table)
- [ ] **3.12** — Clean up dead CSS and old loot button remnants
- [ ] **M5** — Gold drops from enemies (future — ties into economy design)
- [ ] **M6** — Ground loot decay timer (despawn after N turns)
- [ ] **M7** — Hero death drops gear on ground (permadeath loot recovery)

---

## Future Considerations (Not In Scope)

These ideas were discussed but deferred to later phases:

- **More rarity tiers** — Only common/uncommon exist. Rare/epic/legendary would need new items, colors, and drop weight tuning.
- **Loot filters** — Player-configurable filters to auto-hide low-rarity items (Diablo 2 / Path of Exile style). Only relevant when item pool grows significantly.
- **Sound effects** — Loot drop and pickup audio cues. Architecture should be ready but audio system doesn't exist yet.
- **Arena/PvP loot** — Currently loot only works in dungeon maps. Enabling it for arena modes requires design decisions about PvP item economy.
