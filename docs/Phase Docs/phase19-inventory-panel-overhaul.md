# Phase 19 — Inventory / Stats Panel Overhaul

**Status:** Batch 3 Complete  
**Date Started:** March 4, 2026

## Goal

Overhaul the in-dungeon Inventory/Stats panel for better visual presentation and QoL. Surface existing server data that wasn't being shown, improve readability, and make the panel feel more like a proper RPG character sheet.

---

## Batch 1 — Completed ✓

### 1. Expanded Advanced Stats Section
**Files:** `Inventory.jsx`, `_inventory.css`

- Added collapsible "Advanced Stats" button below the 4 core stats
- Surfaces 12 stats from the server `PlayerState` model that were previously invisible to players:
  - Crit Chance, Crit Damage, Dodge, Damage Reduction, Armor Pen
  - HP Regen, Life on Hit, Cooldown Reduction, Skill Damage
  - Thorns, Gold Find, Magic Find
- Only shows non-default stats when expanded (Crit Chance/Damage always show as baseline)
- Ember dot indicator appears when any advanced stat is above its default value
- Imported `useCombatStats` context for kill tracking

### 2. Dungeon Context Strip
**Files:** `Inventory.jsx`, `_inventory.css`

- New horizontal strip below the header when `isDungeon` is true
- Shows: **Floor** number, **Gold** amount, **Kills** this run
- Uses `currentFloor` and `gold` from game state, `kills` from combat stats reducer
- Styled with themed icons and color-coded labels (ember gold, crimson kills)

### 3. Active Buffs Display
**Files:** `Inventory.jsx`, `_inventory.css`

- New "Buffs" section at the bottom of the character stats area
- Shows all active buffs as color-coded pills with duration text
- Buff types: DoT (red), HoT (green), Shield (blue), Detection (amber), Armor (steel), Default
- Hover tooltip shows full buff name and effect description
- Reused `formatBuffName()` and `formatBuffEffect()` helpers (same as HeaderBar)

### 4. HP Bar Polish
**Files:** `_inventory.css`

- HP bar height increased from 10px → 16px
- HP value text now rendered **inside** the bar (centered, white with text-shadow)
- Old external `character-hp-text` element removed from JSX render
- Better readability at a glance — looks more game-like

### 5. Visual Equipment Slot Restyle
**Files:** `Inventory.jsx`, `_inventory.css`

- Replaced horizontal 3-column layout → vertical list with icon + info layout
- Each slot now has a 28×28 icon area with a slot-type symbol (⚔ Weapon, ⊛ Armor, ◇ Accessory)
- Icon colors match item rarity when equipped
- Rarity-colored inner glow on the slot row (subtle `box-shadow: inset`)
- "x" unequip hint appears on hover (top-right corner)
- Item name now in heading font with text ellipsis for long names
- Empty slots show italic "Empty" in flavor font

### 6. Bag Slot Visual Improvements
**Files:** `Inventory.jsx`, `_inventory.css`

- Grid changed from 5 columns → 2 columns for much better item name readability
- Each item now shows a colored **type badge** (W/A/R/P) with type-specific background colors:
  - Weapon: warm orange, Armor: steel gray, Accessory: amber, Consumable: purple
- Consumable slots use dashed borders to visually distinguish them
- Item names now use heading font at 0.65rem (up from 0.55rem), left-aligned
- Slot height reduced since items are now horizontal instead of stacked vertical

### 7. Enhanced Comparison Visuals
**Files:** `_inventory.css`

- Comparison rows now have tinted background strips matching their direction (green for upgrade, red for downgrade)
- Delta values increased to 0.7rem bold mono font for at-a-glance readability
- Labels now use heading font with subtle letter-spacing
- Rows have proper padding and border-radius

---

## Batch 2 — Completed ✓

### 8. Tooltip Position Edge-Clamping
**Files:** `ItemTooltip.jsx`

- Tooltip now measures itself after render using `useLayoutEffect` + `useRef`
- Computes clamped position: if tooltip would go above the viewport, flips below the hovered slot
- Horizontal clamping: prevents overlap with left/right viewport edges (8px padding)
- Bottom clamping: prevents overflow below the viewport
- Falls back to original center-above positioning on first frame (no visible flash)

### 9. Equipment Slot Hover Glow Animation
**Files:** `_inventory.css`

- Equipped items now pulse with a subtle rarity-colored glow on hover
- Each rarity tier has its own `@keyframes` animation:
  - Magic/Uncommon: blue glow pulse (`equipGlowMagic`)
  - Rare: gold glow pulse (`equipGlowRare`)
  - Epic: purple glow pulse (`equipGlowEpic`)
  - Unique: orange glow pulse (`equipGlowUnique`)
  - Set: green glow pulse (`equipGlowSet`)
- Animation is 1.6s ease-in-out infinite; combines inset + outer box-shadow
- Common items have no glow (intentional — only special items feel special)

### 10. Gold Earned This Run
**Files:** `Inventory.jsx`, `GameStateContext.jsx`, `combatReducer.js`, `_inventory.css`

- New `startGold` field in game state, captured at MATCH_START from current `gold`
- Dungeon context strip now shows `(+N)` in green next to the gold total when earned > 0
- Uses mono font and green color (#6aaa40) to match stat-bonus styling
- Delta is `gold - startGold`, so it accurate reflects net gold changes from the match
- No visual noise when nothing earned (hidden when delta ≤ 0)

---

## Batch 3 — Completed ✓

### 11. Bag Sort Button
**Files:** `Inventory.jsx`, `_inventory.css`

- Three sort mode buttons (Type, Rarity, Name) added to the bag header row
- Click a sort button to sort all bag items; click again to return to natural order
- **Type** sort: groups weapons → armor → accessories → consumables, secondary sort by rarity descending
- **Rarity** sort: orders set → unique → epic → rare → magic → common, secondary sort by type
- **Name** sort: alphabetical A-Z by item name
- Active sort button highlighted with ember accent color
- Sort uses original inventory indices for equip/use/transfer actions (sorted view only, no server mutation)
- Memoized with `useMemo` — only recalculates when inventory or sort mode changes

### 12. Set Bonus Indicator on Equipment
**Files:** `Inventory.jsx`, `_inventory.css`

- Small `◈ N` badge displayed on equipment slots that are part of an item set
- Badge shows the set icon and count of equipped pieces from that set
- Uses `getItemSetInfo()` from `itemUtils.js` to detect set membership
- Counts are computed across all 3 equipment slots via `useMemo`
- Badge styled with set-green color, subtle green background, and border
- Hover tooltip shows set name and equipped piece count

### 13. Responsive Panel Width
**Files:** `_inventory.css`

- Four responsive breakpoints for the inventory overlay:
  - **≤500px** (mobile): Full width (98vw), reduced padding, single-column bag/stat grids
  - **501–768px** (small): 320px min, 95vw max
  - **769–1200px** (medium): 340–440px (original)
  - **≥1201px** (large): 360–480px (slightly wider)
- Bag grid, stat grid, and advanced stats grid all collapse to single-column on small screens
- Max-height increased to 90vh on mobile for better vertical usage

### 14. Character Portrait / Class Icon
**Files:** `Inventory.jsx`, `_inventory.css`

- SVG class shape icon rendered in the header next to the character name
- Uses `CLASS_SHAPES` and `CLASS_COLORS` from `renderConstants.js` — same shapes as canvas units
- 6 shape paths defined: square (Crusader), circle (Confessor), triangle (Inquisitor), diamond (Ranger), star (Hexblade), hexagon (Mage)
- 28×28px portrait container with dark background and subtle border
- Dead units rendered at 40% opacity with red stroke
- Alive units rendered with a subtle white stroke

### 15. Party Member Quick-Switch Tabs
**Files:** `Inventory.jsx`, `_inventory.css`

- Tab bar rendered above the header when player has party members (2+ controllable units)
- Each tab shows class shape icon (14×14 SVG) + character name
- Clicking a tab dispatches `SELECT_ACTIVE_UNIT` to switch which unit's inventory is displayed
- Active tab highlighted with ember accent bottom border
- Dead party member tabs rendered at 45% opacity
- Tabs scroll horizontally on overflow
- State resets (clears hovered item and transfer modal) on tab switch
- Uses existing `useGameDispatch` for state management — no new reducer actions needed

---

## Files Modified

| File | Changes |
|------|---------|
| `client/src/components/Inventory/Inventory.jsx` | Added `useCombatStats` import, `formatBuffName`/`formatBuffEffect` helpers, `SLOT_ICONS` constant, `showAdvancedStats` state, dungeon context strip, advanced stats section, buffs section, restyled equipment slots, bag type badges, gold earned delta display, `startGold` from context, `useMemo`/`useGameDispatch` imports, `getItemSetInfo` import, `CLASS_SHAPES`/`CLASS_COLORS` imports, bag sort logic (`RARITY_ORDER`, `TYPE_ORDER`, `SORT_MODES`, `sortBagItems`), `CLASS_SHAPE_PATHS` SVG definitions, `bagSortMode` state, `sortedBag` memoized computation, `equipmentSetInfo` memoized set detection, `partyTabs` memoized party tab list, `handlePartyTabClick` dispatch, party quick-switch tab bar JSX, character portrait SVG in header, set badge `◈` on equipment slots, bag sort buttons in bag header, sorted bag rendering with `origIndex` |
| `client/src/components/Inventory/ItemTooltip.jsx` | Added `useRef`/`useLayoutEffect`/`useState` imports, tooltip edge-clamping logic with viewport measurement and flip-below fallback |
| `client/src/styles/components/_inventory.css` | New CSS for dungeon context strip, HP bar text overlay, advanced stats toggle/grid, buff pills, equipment slots v2, bag type badges, consumable slot styling, enhanced comparison rows, equipment hover glow keyframes (5 rarity tiers), gold-earned delta styling, responsive panel width (4 breakpoints with media queries), party quick-switch tabs, character portrait container, set bonus badge, bag sort buttons |
| `client/src/context/GameStateContext.jsx` | Added `startGold: 0` to initial state |
| `client/src/context/reducers/combatReducer.js` | MATCH_START now stores `startGold: state.gold` for gold delta tracking |
