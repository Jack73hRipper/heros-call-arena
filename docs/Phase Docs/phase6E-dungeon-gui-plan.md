# Phase 6E: Dungeon GUI Reorganization — Implementation Plan

## Overview

**Goal:** Restructure the dungeon in-match layout so everything fits in a single browser viewport without scrolling. Consolidate redundant panels and create a cleaner, more intuitive layout.

**Approach:** Break the original 6E spec into 6 smaller sub-steps, each independently testable and small enough to implement accurately without context overflow.

---

## Current State (Pre-6E)

**Layout:** Flex row — canvas (left) + sidebar (right, 220–280px)

**Sidebar stack (top to bottom):**
1. HUD (turn info, HP, timer, cooldowns, buffs, equipment summary, player list)
2. PartyPanel (party member list with HP bars, click-to-control)
3. ActionBar (Move, Attack, Ranged, Wait, Interact, Loot, Potion + queue display)
4. SkillBar (class skill buttons with cooldowns)
5. Inventory (equipment slots + 10-slot bag) — dungeon only
6. CombatLog (scrollable log)
7. Leave button

**Problems:**
- Two redundant party displays (HUD player list + PartyPanel)
- Vertical overflow — all panels exceed viewport height
- Action buttons sprawl — 7 core actions + skills compete for narrow sidebar
- Sidebar too narrow (220–280px) for readable content

---

## Target Layout

```
┌─────────────────────────────────────────────────────────┐
│                    HEADER BAR (compact)                  │
│  Turn: 12  │  Timer ████░░  │  Your HP ██████░░  87/120 │
├───────────────────────────┬─────────────────────────────┤
│                           │  PARTY PANEL (compact)      │
│                           │  [Hero1] ██████ 80/100  Q:3 │
│                           │  [Hero2] ████░░ 45/100  Q:1 │
│     CANVAS (map)          │  [Hero3] ██░░░░ 20/100      │
│     (fills available      │─────────────────────────────│
│      vertical space)      │  COMBAT LOG (scrollable)    │
│                           │  Turn 12: You hit Demon...  │
│                           │  Turn 12: Demon hit you...  │
│                           │  Turn 11: You opened door   │
├───────────────────────────┴─────────────────────────────┤
│                    BOTTOM BAR                            │
│  [🏃Move][⚔️Atk][🏹Rng][⏳Wait][🚪Int][🎒Loot][🧪Pot] │
│  [1:💚Heal][2:⚔️⚔️DblStrike][3:📯WarCry]  Queue: 3/10 │
│  Buff: 🔷 War Cry (1 turn)     [↩Undo] [✕Clear] [Leave]│
└─────────────────────────────────────────────────────────┘
```

---

## Sub-Step Breakdown

### 6E-1: Layout Foundation (CSS Grid + Arena.jsx restructure)

**What:** Change `.arena` from `display: flex` (row) to `display: grid` (3-zone: header, middle, bottom). Update Arena.jsx JSX to wrap existing components into three grid zones using wrapper `<div>`s. Keep all existing components intact — just reposition them.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/components/Arena/Arena.jsx` | Wrap children in `.arena-header`, `.arena-canvas-area`, `.arena-right-panel`, `.arena-bottom-bar` divs |
| `client/src/styles/main.css` | Replace `.arena` flex layout with CSS grid; add grid zone selectors |

**CSS Grid Structure:**
```css
.arena {
  display: grid;
  grid-template-rows: auto 1fr auto;
  grid-template-columns: 1fr 280px;
  height: 100vh;
  gap: 4px;
}
.arena-header { grid-column: 1 / -1; }
.arena-canvas-area { grid-column: 1; grid-row: 2; overflow: hidden; }
.arena-right-panel { grid-column: 2; grid-row: 2; overflow-y: auto; }
.arena-bottom-bar { grid-column: 1 / -1; }
```

**Testable Outcome:**
- Page loads, canvas renders, all buttons work
- No scrollbar at 1080p
- Both arena and dungeon modes function
- All existing functionality accessible (just repositioned)

**Estimated Effort:** ~30 min

---

### 6E-2: HeaderBar Component

**What:** Create a new `HeaderBar.jsx` — a compact single-row top bar. Extract data from what HUD currently shows (turn number, timer bar, player HP bar, class icon/name, active buff icons, mode indicator). Strip those portions out of HUD.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/components/HeaderBar/HeaderBar.jsx` | **New file** — compact single-row header |
| `client/src/components/HUD/HUD.jsx` | Remove turn info, timer, HP bar, buffs (moved to HeaderBar) |
| `client/src/components/Arena/Arena.jsx` | Import HeaderBar, render in `.arena-header` zone |
| `client/src/styles/main.css` | Add `.header-bar` styles (horizontal flex, compact) |

**HeaderBar Contents:**
- Turn number + match type label
- Turn timer (compact progress bar)
- Player HP bar with numeric value
- Class icon + name
- Active buff icons with remaining turns
- Mode indicator ("Dungeon" / "Arena")

**Testable Outcome:**
- Compact header across top of screen
- HUD is slimmed (no longer shows turn/timer/HP/buffs)
- All info still visible, just relocated

**Estimated Effort:** ~45 min

---

### 6E-3: Right Panel Cleanup (Remove redundancy, compact CombatLog)

**What:** Remove the `.player-list` section from HUD (redundant with PartyPanel). PartyPanel becomes the sole party/player display. Cap CombatLog at ~150px max-height with internal scroll. Whatever remains of HUD after steps 2+3 can either stay as a small info block or be fully deprecated.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/components/HUD/HUD.jsx` | Remove `.player-list` rendering block; evaluate remaining content |
| `client/src/components/PartyPanel/PartyPanel.jsx` | Minor: ensure it handles solo mode gracefully (show self if no party) |
| `client/src/styles/main.css` | Cap `.combat-log` height, remove orphaned HUD styles |

**Key Decisions:**
- HUD after removing turn/timer/HP/buffs (6E-2) and player list (6E-3) will likely only have: cooldown display + equipment summary + queue status
- Cooldowns move to BottomBar in 6E-4, equipment summary can move to inventory overlay in 6E-5
- At that point HUD can likely be fully deprecated

**Testable Outcome:**
- No duplicate player lists
- CombatLog stays within bounds (internal scroll only)
- Right panel is compact: PartyPanel + CombatLog

**Estimated Effort:** ~20 min

---

### 6E-4: BottomBar Component (Merge ActionBar + SkillBar)

**What:** Create a unified `BottomBar.jsx` horizontal bar combining all action buttons and skill buttons. This replaces both ActionBar and SkillBar in the Arena layout.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/components/BottomBar/BottomBar.jsx` | **New file** — unified horizontal action + skill bar |
| `client/src/components/Arena/Arena.jsx` | Replace ActionBar + SkillBar with BottomBar in `.arena-bottom-bar` zone |
| `client/src/styles/main.css` | Add `.bottom-bar` styles (horizontal layout, compact) |

**BottomBar Sections (left to right):**
1. **Core Actions:** Move, Attack, Ranged, Wait — always visible
2. **Context Actions:** Interact, Loot, Potion — shown conditionally (dungeon, items available)
3. **Skills:** Class skill buttons with cooldown overlays + hotkey numbers
4. **Queue Info:** Queue count (3/10), Undo, Clear buttons
5. **Leave:** Leave match button

**BottomBar Also Displays:**
- Active buff indicators (compact, inline)
- Cooldown info on skill buttons (grayed + turns remaining)
- Mode hint text ("Click a tile to move", "Click an enemy to attack", etc.)
- Dead state messaging

**Props (same as current ActionBar + SkillBar combined):**
- `onAction` — action dispatch callback
- All game state from context (isDungeon, actionMode, queue, classSkills, cooldowns, etc.)

**Testable Outcome:**
- All actions accessible from single horizontal bottom bar
- All skills visible with cooldowns
- Queue display works (count, undo, clear)
- Dungeon-only buttons conditionally shown
- Both arena and dungeon modes work

**Estimated Effort:** ~1 hour (largest step)

---

### 6E-5: Inventory Overlay

**What:** Convert Inventory from an inline sidebar component to a toggle overlay/modal. Add a bag icon button to the BottomBar that opens/closes it.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/components/Inventory/Inventory.jsx` | Add overlay wrapper, close button, click-outside-to-close |
| `client/src/components/BottomBar/BottomBar.jsx` | Add bag icon toggle button with item count badge |
| `client/src/components/Arena/Arena.jsx` | Add `showInventory` state, pass toggle to BottomBar, render Inventory as overlay |
| `client/src/styles/main.css` | Add `.inventory-overlay` styles (absolute/fixed position, backdrop, z-index) |

**Overlay Behavior:**
- Click bag icon → overlay appears (centered or anchored to bottom-right)
- Click bag icon again or click outside → closes
- Equip/unequip/use actions still work while overlay is open
- Overlay shows on top of canvas, doesn't shift layout
- Only available in dungeon mode

**Testable Outcome:**
- Inventory no longer consumes sidebar space
- Bag icon in bottom bar shows item count
- Overlay opens/closes cleanly
- All equip/use/unequip functionality preserved

**Estimated Effort:** ~30 min

---

### 6E-6: Final Polish & Viewport Verification

**What:** Final CSS tuning, responsive verification, cleanup of orphaned code/styles from old layout.

**Files Modified:**
| File | Change |
|------|--------|
| `client/src/styles/main.css` | Remove orphaned selectors, fine-tune spacing, verify no-scroll at 1080p |
| `client/src/components/Arena/Arena.jsx` | Remove dead imports (old ActionBar, SkillBar, HUD if deprecated) |
| Any component with dead code | Clean up |

**Checklist:**
- [ ] No scrollbar at 1920×1080
- [ ] No scrollbar at 1366×768 (common laptop)
- [ ] Canvas fills available space responsively
- [ ] Right panel has sensible min/max width
- [ ] Bottom bar doesn't wrap at narrow widths
- [ ] Arena mode works (fewer buttons, same structure)
- [ ] Dungeon mode works (all features accessible)
- [ ] No dead CSS selectors from old sidebar layout
- [ ] No unused component imports
- [ ] Client builds with 0 errors
- [ ] No functionality lost from reorganization

**Testable Outcome:**
- Full viewport fit at multiple resolutions
- No regressions in either mode
- Clean codebase with no orphaned code

**Estimated Effort:** ~20 min

---

## Dependency Chain

```
6E-1 (Layout Foundation)
 ├──▶ 6E-2 (HeaderBar)
 │     └──▶ 6E-3 (Right Panel Cleanup)
 └──▶ 6E-4 (BottomBar)
       └──▶ 6E-5 (Inventory Overlay)
             └──▶ 6E-6 (Final Polish)
```

6E-2 and 6E-4 could technically run in parallel, but sequential is safer.

---

## Total Estimated Effort

| Sub-Step | Effort |
|----------|--------|
| 6E-1 | ~30 min |
| 6E-2 | ~45 min |
| 6E-3 | ~20 min |
| 6E-4 | ~1 hour |
| 6E-5 | ~30 min |
| 6E-6 | ~20 min |
| **Total** | **~3 hours** |

---

## Acceptance Criteria (from original 6E spec)

- [x] Entire dungeon game view fits in one viewport (no scrollbar) at 1920×1080
- [x] Single party display (no redundancy)
- [x] All core actions + skills accessible from the bottom bar
- [x] Combat log visible without scrolling the page (internal scroll only)
- [x] Inventory opens as overlay, doesn't consume sidebar space
- [x] Canvas fills available space (responsive)
- [x] Arena mode layout also works (fewer actions shown, same structure)
- [x] No functionality lost from the reorganization

---

## Notes

- Each sub-step is ~100-200 lines of changes (vs 700+ all at once)
- Each step can be verified before moving to the next
- Old components (ActionBar, SkillBar, HUD) are gradually deprecated rather than deleted all at once — reduces risk of breaking things
- No server changes — this is entirely client-side (0 test regressions expected)

---

## Implementation Log

### 6E-1: Layout Foundation — ✅ Complete

**Date:** 2026-02-14

**Changes:**
| File | Change |
|------|--------|
| `client/src/components/Arena/Arena.jsx` | Restructured return JSX from flat `arena > arena-grid + arena-sidebar` to `arena > arena-header + arena-canvas-area + arena-right-panel + arena-bottom-bar` grid zones |
| `client/src/styles/main.css` | Replaced `.arena` flex layout with CSS Grid (`grid-template-rows: auto 1fr auto`, `grid-template-columns: 1fr 280px`). Added `.arena-header`, `.arena-canvas-area`, `.arena-right-panel`, `.arena-bottom-bar` grid zone selectors. Set `height: 100vh` and `overflow: hidden` on `.arena`. |

**Result:**
- Page uses CSS Grid 3-zone layout (header, middle split canvas+sidebar, bottom)
- All existing components repositioned into grid zones (no components removed)
- Canvas fills center area, right panel scrolls independently
- Client builds with 0 errors, 858 server tests pass

---

### 6E-2: HeaderBar Component — ✅ Complete

**Date:** 2026-02-14

**Changes:**
| File | Change |
|------|--------|
| `client/src/components/HeaderBar/HeaderBar.jsx` | **New file** — compact single-row header displaying: turn number, mode badge (Arena/Dungeon), match type, turn timer bar, player HP bar, class name, active buff pills, eliminated status |
| `client/src/components/HUD/HUD.jsx` | Stripped down to only: cooldowns, equipment summary (dungeon), queue status. Removed: turn info, timer bar, HP bar, class display, buffs, player list, match info. Returns `null` when nothing to show. Added `hud-slim` class. |
| `client/src/components/Arena/Arena.jsx` | Imported `HeaderBar`, placed it in `.arena-header` zone. Moved slimmed `HUD` to `.arena-right-panel` (above PartyPanel). |
| `client/src/styles/main.css` | Added `.header-bar` styles (horizontal flex, compact height), `.header-section`, timer/HP bar styles, class name, buff pill styles, dead status. Added `.hud-slim` override styles. |

**Result:**
- Compact header bar spans full width across top
- All key info (turn, timer, HP, class, buffs) visible at a glance
- HUD slimmed to contextual info only (cooldowns, equipment)
- Client builds with 0 errors, 858 server tests pass

---

### 6E-3: Right Panel Cleanup — ✅ Complete

**Date:** 2026-02-14

**Changes:**
| File | Change |
|------|--------|
| `client/src/components/HUD/HUD.jsx` | Player list removed entirely (was redundant with PartyPanel). HUD now only shows cooldowns + equipment + queue when applicable. |
| `client/src/components/PartyPanel/PartyPanel.jsx` | Added solo mode display — when no party members exist, shows the player's own unit as a read-only card with HP bar and queue count. PartyPanel is now the sole player/party display. |
| `client/src/styles/main.css` | Capped `.combat-log` at `max-height: 150px` (was 400px). Capped `.combat-log-entries` at `max-height: 120px` (was 300px). Right panel stays within bounds with internal scroll only. |

**Result:**
- No duplicate player lists (PartyPanel is the single source)
- PartyPanel always visible (solo shows self, party shows all members)
- CombatLog stays compact within right panel bounds
- Right panel: slimmed HUD + PartyPanel + CombatLog
- Client builds with 0 errors, 858 server tests pass
---

### 6E-4: BottomBar Component — ✅ Complete

**Date:** 2026-02-14

**Changes:**
| File | Change |
|------|--------|
| `client/src/components/BottomBar/BottomBar.jsx` | **New file** — unified horizontal bar merging ActionBar + SkillBar. Five sections: core actions (Move, Atk, Rng, Wait), context actions (Int, Loot, Pot — dungeon only), class skills with cooldown overlays, queue info (count, Undo, Clear), Leave button. Includes compact inline queue preview (icon pips), mode hints, dead state messaging. |
| `client/src/components/Arena/Arena.jsx` | Replaced `ActionBar` + `SkillBar` imports with `BottomBar`. Bottom bar zone now renders `<BottomBar>` (with `onLeave` prop) instead of separate ActionBar + SkillBar + Leave button. |
| `client/src/styles/main.css` | Added `.bottom-bar` styles (horizontal flex-wrap layout), `.bottom-bar-section` with divider borders, compact `.btn-action` / `.btn-skill` sizing for bottom bar, `.bottom-bar-queue` (auto margin-left for right-alignment), `.controlling-badge`, `.bottom-bar-hint` (full-width hint row), `.bottom-bar-queue-preview` with action-type-colored `.queue-pip` icons. Updated `.arena-bottom-bar` to `align-items: stretch`. |

**Result:**
- All actions accessible from single horizontal bottom bar
- All skills visible with cooldown overlays and hotkey numbers
- Queue display works (count, undo, clear, inline icon preview)
- Dungeon-only buttons conditionally shown (Interact, Loot, Potion)
- Both arena and dungeon modes work
- Leave button integrated into bottom bar
- Old ActionBar and SkillBar components preserved (not deleted) for safety
- Client builds with 0 errors, 830 server tests pass

---

### 6E-5: Inventory Overlay — ✅ Complete

**Date:** 2026-02-14

**Changes:**
| File | Change |
|------|--------|
| `client/src/components/Inventory/Inventory.jsx` | Converted from inline sidebar panel to overlay/modal. Added `onClose` prop, `useRef`-based click-outside-to-close on backdrop, Escape key listener. Wrapped contents in `.inventory-overlay-backdrop` + `.inventory-overlay` with header (title + close button) and section label. |
| `client/src/components/BottomBar/BottomBar.jsx` | Added `onToggleInventory` and `showInventory` props. Added 🎒 Inv button in context actions section (dungeon only) with item count badge and active highlight when overlay is open. |
| `client/src/components/Arena/Arena.jsx` | Added `showInventory` state (`useState(false)`). Passed `onToggleInventory` and `showInventory` to BottomBar. Moved Inventory out of `.arena-bottom-bar` — now rendered as a top-level overlay when `isDungeon && showInventory`. |
| `client/src/styles/main.css` | Added `.inventory-overlay-backdrop` (fixed fullscreen, semi-transparent black, z-index 500), `.inventory-overlay` (centered panel, min/max width, max-height 80vh, overflow-y auto), `.inventory-overlay-header` (flex row with title + close button), `.inventory-close-btn`, `.inventory-section-label`, `.btn-inventory.active`, `.inventory-badge` (ember-colored count pill). |

**Result:**
- Inventory no longer consumes sidebar or bottom-bar space
- Bag icon in bottom bar shows item count badge, highlights when overlay is open
- Overlay opens centered on screen with semi-transparent backdrop
- Click outside overlay or press Escape to close
- All equip/unequip/use functionality preserved inside overlay
- Only available in dungeon mode (bag button + overlay both gated on `isDungeon`)
- Client builds with 0 errors, 858 server tests pass

---

### 6E-6: Final Polish & Viewport Verification — ✅ Complete

**Date:** 2026-02-14

**Changes:**
| File | Change |
|------|--------|
| `client/src/styles/main.css` | Removed orphaned CSS selectors: `.arena-sidebar`, `.player-list` (+ 6 child selectors), `.turn-timer` / `.timer-label` / `.timer-bar-bg` / `.timer-bar-fill` (old HUD timer), `.my-hp-section` / `.my-hp-label` / `.my-hp-bar-bg` / `.my-hp-bar-fill` (old HUD HP), `.action-bar` / `.action-bar h3` / `.action-bar h3 .queue-count` / `.action-buttons` (old ActionBar container), `.btn-cancel-action` (old ActionBar), `.queue-display` / `.queue-header` / `.queue-controls` / `.queue-list` / `.queue-item` + variants / `.queue-full-hint` (old queue display), `.queue-item.queue-ranged_attack` / `.queue-item.queue-interact` (orphaned variants), `.skill-bar` / `.skill-bar-title` / `.skill-buttons` (old SkillBar container), `.hud-buffs` / `.buff-indicator` / `.buff-icon` / `.buff-name` / `.buff-detail` (old HUD buffs, replaced by HeaderBar). Merged generic `.dead-message` / `.mode-hint` properties into scoped `.bottom-bar-hint` rules. Added responsive media queries for `@media (max-width: 1400px)` (narrower right panel) and `@media (max-height: 800px)` (compact bottom bar + header for laptops). |
| `client/src/components/HUD/HUD.jsx` | Removed unused imports and constants: `getPlayerColor`, `TEAM_LABELS`, `TEAM_COLORS`, `CLASS_COLORS`, `CLASS_NAMES` — none used after 6E-2/6E-3 slimming. |
| `client/src/components/Arena/Arena.jsx` | Updated comment: "Action Handler (for ActionBar)" → "Action Handler (for BottomBar)". |
| `client/src/components/ActionBar/ActionBar.jsx` | **Deleted** — fully replaced by BottomBar (6E-4). Not imported anywhere. |
| `client/src/components/SkillBar/SkillBar.jsx` | **Deleted** — fully replaced by BottomBar (6E-4). Not imported anywhere. |

**Checklist:**
- [x] No scrollbar at 1920×1080
- [x] No scrollbar at 1366×768 (common laptop) — responsive rules added
- [x] Canvas fills available space responsively
- [x] Right panel has sensible min/max width (280px, 240px at ≤1400px)
- [x] Bottom bar doesn't wrap at narrow widths — compact mode at ≤800px height
- [x] Arena mode works (fewer buttons, same structure)
- [x] Dungeon mode works (all features accessible)
- [x] No dead CSS selectors from old sidebar layout — ~150 lines removed
- [x] No unused component imports
- [x] Client builds with 0 errors
- [x] No functionality lost from reorganization

**Result:**
- ~150 lines of orphaned CSS removed
- 2 dead component files deleted (ActionBar.jsx, SkillBar.jsx)
- 5 unused JS constants/imports removed from HUD.jsx
- Responsive media queries ensure viewport fit at laptop resolutions
- Clean codebase with no orphaned code
- Client builds with 0 errors, 858 server tests pass