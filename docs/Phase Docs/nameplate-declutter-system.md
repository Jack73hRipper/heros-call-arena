# Nameplate Declutter System — Hybrid Tiered Nameplates

**Goal:** Reduce visual clutter when many units are clumped together by showing compact HP-only bars for low-priority units and full nameplates for important ones, with hover/ALT expansion.

**Status:** Phase A Complete · Phase B Complete

---

## Phase A — Implementation Log

**Completed:** March 7, 2026

### Files Changed

| File | What Changed |
|------|-------------|
| `client/src/canvas/unitRenderer.js` | Added compact plate constants (`COMPACT_PLATE_WIDTH` 44px, `COMPACT_PLATE_HEIGHT` 10px, `COMPACT_BAR_HEIGHT` 5px), `_getCompactPlateRect()` helper, `nameplateMode` param on `drawPlayer()` with full compact branch (HP-bar-only, slim background, single 50% notch, thinner rarity border), `nameplateMode` param on `drawBuffIcons()` and `drawNameplateGlow()` for correct plate rect selection |
| `client/src/canvas/ArenaRenderer.js` | Added per-unit `nameplateMode` computation in `renderFrame()` loop — checks `isMyHero`, `isPrimary`, `isSecondary`, `isSelectedTarget`, `hasAutoTarget`, `is_boss`, `monster_rarity` (rare/super_unique), and `isHovered` (mouse on tile). Passes mode to `drawPlayer`, `drawBuffIcons`, `drawNameplateGlow` |

### Nameplate Mode Rules (Phase A)

| Condition | Mode |
|-----------|------|
| Your hero (`myPlayerId` or in `partyMembers`) | Full |
| Active/selected/secondary unit | Full |
| Selected target or auto-target | Full |
| Boss (`is_boss`) | Full |
| Rare (`monster_rarity === 'rare'`) | Full |
| Super Unique (`monster_rarity === 'super_unique'`) | Full |
| Mouse hovering unit's tile | Full |
| Everything else (normal enemies, champions) | Compact |

### Compact Plate Specs

- Width: 44px (56px boss) — fits inside `TILE_SIZE` (48px), no horizontal overflow
- Height: 10px — vs 26px for full plates
- HP bar: 5px with same gradient colors and flash animation
- Single 50% notch mark (too slim for 25/75)
- Thinner rarity border when applicable
- No name text, no accent stripe

---

## Phase B — Implementation Log

**Completed:** March 7, 2026

### Files Changed

| File | What Changed |
|------|-------------|
| `client/src/canvas/ArenaRenderer.js` | Added `altHeld` and `isNearCursor` (2-tile Chebyshev proximity) to nameplate mode computation — `nameplateMode = (isImportant \|\| isHovered \|\| isNearCursor \|\| altHeld) ? 'full' : 'compact'` |
| `client/src/canvas/unitRenderer.js` | Added `_plateExpandCache` Map + `_getExpandProgress(unitId, targetMode)` lerp function (0.2 lerp factor, ~150ms at 60fps). Replaced branched compact/full nameplate drawing with unified interpolated path — all plate dimensions (width, height, bar height, border radius, insets) smoothly lerp between compact and full values. Name text fades in at p0 > 0.3, accent stripe fades at p0 > 0.1, boss/rarity ornamental borders fade at p0 > 0.3, inner bar border fades at p0 > 0.5, notch marks switch from 1 (50%) to 3 (25/50/75%) at p0 ≥ 0.5 |

### Phase B Features

| Feature | Details |
|---------|---------|
| **B1: ALT-to-Expand** | Holding ALT expands all compact nameplates to full — same key as ground item labels. Single line change to mode check. |
| **B2: Mouse Proximity** | Units within 2 tiles of cursor (Chebyshev distance) get full nameplates — "flashlight" reveal effect when sweeping the mouse. Constant `NAMEPLATE_PROXIMITY_RADIUS = 2`. |
| **B3: Smooth Animation** | Per-unit `_plateExpandCache` lerps between compact (0) and full (1) dimensions over ~150ms. All plate properties interpolate: background opacity (0.65→0.72), border thickness (0.75→1.0), bar height (5→6px), plate width (44→72px), plate height (10→26px). Name text, accent stripe, ornamental borders, and inner bar border all have staggered fade-in thresholds for a natural expand feel. |

---

## Problem Statement

- `TILE_SIZE` = 48px, but full nameplates are 72px wide (84 for bosses) and 26px tall
- Adjacent units' nameplates **always overlap** horizontally (72 > 48)
- No collision avoidance exists — every alive unit gets a full plate at a fixed offset
- Buff icons, CC indicators, and rarity glows stack even more visual noise
- In 4+ unit clusters the nameplates become an unreadable mess

---

## Solution: Two-Phase Hybrid Tiered Nameplate System

### Nameplate Display Tiers

| Tier | What Shows | When |
|------|-----------|------|
| **Full** | Name text + HP bar + accent stripe + rarity border (current look) | Important units (see rules below) |
| **Compact** | HP bar only — smaller plate, no name text | Default for normal enemies |
| **Expanded** | Compact → Full transition | Mouse proximity or ALT held |

### "Important" Unit Rules (always get Full plate)

1. **Your own heroes** — `pid === myPlayerId` OR unit is in `partyMembers`
2. **Selected/targeted unit** — `pid === selectedTargetId`
3. **Active unit** — `pid === activeUnitId`
4. **Auto-targeted unit** — in `allAutoTargets` set
5. **Boss monsters** — `p.is_boss === true`
6. **Rare tier monsters** — `p.monster_rarity === 'rare'`
7. **Super Unique monsters** — `p.monster_rarity === 'super_unique'`
8. **Hovered unit** — unit is on the `hoveredTile` (selectedTile in renderFrame)

Champions (`monster_rarity === 'champion'`) and normal enemies get **Compact** by default.

---

## Phase A — Compact Nameplate Mode

### A1. New `nameplateMode` param on `drawPlayer()`

**File:** `client/src/canvas/unitRenderer.js`

Add a new parameter `nameplateMode = 'full'` to the `drawPlayer` function signature (after `championType`). Values: `'full'` | `'compact'`.

### A2. Compact plate constants

Add new constants alongside existing plate constants:

```js
// Compact plate: HP-bar-only, fits within one tile width
const COMPACT_PLATE_WIDTH = 44;      // narrower than TILE_SIZE (48) — no overflow
const COMPACT_PLATE_HEIGHT = 8;      // just the bar + tiny border
const COMPACT_BAR_HEIGHT = 5;        // slightly smaller bar
```

### A3. New `_getCompactPlateRect()` helper

```js
function _getCompactPlateRect(cx, ey, isBoss) {
  const radius = isBoss ? TILE_SIZE * 0.42 : TILE_SIZE * 0.35;
  const plateWidth = isBoss ? 56 : COMPACT_PLATE_WIDTH;
  const plateX = cx - plateWidth / 2;
  const plateY = ey - radius - COMPACT_PLATE_HEIGHT - 2;
  return { plateX, plateY, plateWidth, plateHeight: COMPACT_PLATE_HEIGHT };
}
```

### A4. Branch nameplate drawing in `drawPlayer()`

Inside `drawPlayer()`, after the sprite/shape rendering and tint overlay section (~line 485), branch on `nameplateMode`:

- **`'full'`** → existing nameplate code (unchanged)
- **`'compact'`** → draw only:
  - Slim dark background rect (COMPACT_PLATE_HEIGHT tall)
  - HP fill bar (COMPACT_BAR_HEIGHT, same gradient logic)
  - Flash overlay on HP change
  - Notch marks at 25/50/75%
  - Rarity border (if applicable) — but thinner
  - **No** name text, **no** accent stripe

### A5. Update `_getPlateRect` usage for buff icons / glow

The shared `_getPlateRect` function is used by `drawBuffIcons` and `drawNameplateGlow` to position above the plate. These need to also accept the mode so they position correctly above the compact plate when applicable:

- Add optional `nameplateMode` param to `drawBuffIcons` and `drawNameplateGlow`
- When `nameplateMode === 'compact'`, use `_getCompactPlateRect` instead
- **Buff icons** — still draw above the compact bar (just at a lower Y)
- **Nameplate glow** — glow wraps the compact bar instead

### A6. Determine `nameplateMode` in `renderFrame()`

**File:** `client/src/canvas/ArenaRenderer.js`

In the `playerEntries.forEach` loop (~line 318), compute the mode before calling `drawPlayer`:

```js
// --- Determine nameplate display mode ---
const isMyHero = pid === myPlayerId || partyMembers.some(m => m.unit_id === pid);
const isImportant = isMyHero
  || isPrimary || isSecondary || isSelectedTarget || hasAutoTarget
  || (p.is_boss)
  || (p.monster_rarity === 'rare')
  || (p.monster_rarity === 'super_unique');

// Hovered tile check: unit on the tile the mouse is pointing at
const isHovered = selectedTile
  && p.position.x === selectedTile.x
  && p.position.y === selectedTile.y;

const nameplateMode = (isImportant || isHovered) ? 'full' : 'compact';
```

Pass `nameplateMode` to `drawPlayer`, `drawBuffIcons`, and `drawNameplateGlow`.

### A7. Files Changed (Phase A)

| File | Changes |
|------|---------|
| `client/src/canvas/unitRenderer.js` | New constants, `_getCompactPlateRect()`, `drawPlayer` gets `nameplateMode` param + compact branch, `drawBuffIcons` + `drawNameplateGlow` get optional `nameplateMode` param |
| `client/src/canvas/ArenaRenderer.js` | Compute `nameplateMode` per unit in render loop, pass to draw calls |

### A8. Visual Result

- Normal enemies / champions in a clump: thin HP bars only (~44px wide), no overlap on adjacent tiles
- Bosses / rares / super uniques / your heroes: full beautiful Diablo-style nameplate (unchanged)
- Selected/targeted enemy: full nameplate pops out of the clump
- Mousing over any unit: its plate expands to full

---

## Phase B — ALT-to-Expand & Mouse Proximity Expansion

### B1. ALT-to-Expand All Nameplates

**File:** `client/src/canvas/ArenaRenderer.js`

`altHeld` is already passed into `renderFrame()` and wired from `useKeyboardShortcuts`. Simply add it to the mode computation:

```js
const nameplateMode = (isImportant || isHovered || altHeld) ? 'full' : 'compact';
```

That's it — holding ALT shows all ground item labels AND all full nameplates. Clean, consistent keybind.

### B2. Mouse Proximity Expansion (within N tiles)

Expand nameplates for units near the cursor, not just on the exact hovered tile. This gives a "flashlight" effect where nearby units reveal their names as you sweep the mouse.

**In `renderFrame()`**, before the unit loop, compute proximity:

```js
// Phase B: Proximity expansion radius (in tiles)
const NAMEPLATE_PROXIMITY_RADIUS = 2;
```

In the per-unit mode check, add distance calculation:

```js
const isNearCursor = selectedTile && Math.abs(p.position.x - selectedTile.x) <= NAMEPLATE_PROXIMITY_RADIUS
  && Math.abs(p.position.y - selectedTile.y) <= NAMEPLATE_PROXIMITY_RADIUS;

const nameplateMode = (isImportant || isHovered || isNearCursor || altHeld) ? 'full' : 'compact';
```

### B3. Smooth Expand/Collapse Animation (Optional Polish)

Add a per-unit animation cache (like `_hpAnimCache`) that lerps between compact and full dimensions over ~150ms. This prevents jarring pop-in when mousing over groups.

```js
// In unitRenderer.js
const _plateExpandCache = new Map();

function _getExpandProgress(unitId, targetMode) {
  const target = targetMode === 'full' ? 1 : 0;
  if (!_plateExpandCache.has(unitId)) {
    _plateExpandCache.set(unitId, { progress: target });
    return target;
  }
  const entry = _plateExpandCache.get(unitId);
  entry.progress += (target - entry.progress) * 0.2; // lerp factor
  if (Math.abs(entry.progress - target) < 0.02) entry.progress = target;
  return entry.progress;
}
```

Use this to interpolate between compact and full plate dimensions, creating a smooth transition.

### B4. Files Changed (Phase B)

| File | Changes |
|------|---------|
| `client/src/canvas/ArenaRenderer.js` | Add `altHeld` and proximity to mode computation |
| `client/src/canvas/unitRenderer.js` | (Optional) `_plateExpandCache` + lerp for smooth transitions |

---

## Implementation Order

1. **Phase A1–A3**: Add compact constants + `_getCompactPlateRect()`
2. **Phase A4**: Branch `drawPlayer()` for compact mode
3. **Phase A5**: Update `drawBuffIcons` + `drawNameplateGlow` for mode awareness
4. **Phase A6**: Compute + pass `nameplateMode` in `renderFrame()`
5. **Test Phase A** — verify compact bars on normal enemies, full plates on heroes/bosses/targets
6. **Phase B1**: Wire `altHeld` into mode check
7. **Phase B2**: Add proximity expansion
8. **Phase B3**: (Optional) Smooth animation
9. **Test Phase B** — verify ALT expand, mouse proximity, smooth transitions

---

## Revert Plan

All changes are additive. The `nameplateMode` defaults to `'full'`, so removing the mode computation in `ArenaRenderer.js` (or hardcoding `'full'`) reverts to current behavior instantly. No data model or server changes required.
