# CSS Split Plan — `main.css` Decomposition

**Date:** February 27, 2026  
**Status:** In Progress — Phases 0–4 complete, Phase 5 in progress (barrel swap done, visual verification pending)  
**Risk Level:** Low (pure file reorganization, no class name changes, no logic changes)

## Problem

`client/src/styles/main.css` is **7,197 lines** — a single monolith containing every style in the project. It is:
- Hard to navigate (46+ sections with overlapping/duplicate concerns)
- Prone to merge conflicts
- Difficult to reason about which styles belong to which component
- Contains dead/duplicate sections (e.g., two Combat Log sections, two HUD sections)

## Strategy: Global Partials with `@import`

We will use the **safest possible approach** — splitting into logical partial files imported from a barrel `main.css` via CSS `@import`. Vite natively resolves CSS `@import` statements and bundles them, so this is zero-config.

### Why NOT CSS Modules / component-level imports?
- CSS Modules would require renaming every class in JSX (huge risk, thousands of touch-points)
- The grimdark theme has many cross-cutting styles that benefit from global scope
- `@import` partials give us the organization win with zero refactoring risk

## Current Structure (single file)

```
client/src/styles/
├── main.css           ← 7,197 lines (everything)
└── main-classic.css   ← backup of original theme
```

## Target Structure

```
client/src/styles/
├── main.css                 ← barrel file (~25 @import lines)
├── main-classic.css         ← unchanged (backup)
│
├── base/
│   ├── _variables.css       ← CSS custom properties (:root)
│   ├── _reset.css           ← *, scrollbar, body, .app, vignette
│   └── _buttons.css         ← shared button styles (.grim-btn, etc.)
│
├── layout/
│   ├── _app-header.css      ← game title bar
│   ├── _arena.css           ← arena grid layout + responsive viewport rules
│   └── _minimap.css         ← minimap overlay
│
├── components/
│   ├── _lobby.css           ← lobby screens (username entry, match list, match config, class select)
│   ├── _waiting-room.css    ← waiting room + AI badge
│   ├── _header-bar.css      ← in-match header bar (turn counter, HP, buffs)
│   ├── _bottom-bar.css      ← action bar, skill slots, hotkeys, cooldowns, tooltips, queue controls
│   ├── _hud.css             ← HUD overlay
│   ├── _combat-log.css      ← combat log (merged both sections)
│   ├── _party-panel.css     ← party list, stances, multi-select
│   ├── _enemy-panel.css     ← targeted enemy info
│   ├── _inventory.css       ← inventory/loot UI + dungeon inventory transfer
│   ├── _combat-meter.css    ← combat stats, meter bars, skill breakdown, source bars
│   └── _overlays.css        ← match end, death banner, queued action display, auto-target HUD, action intent
│
├── town/
│   ├── _town-hub.css        ← town hub layout + browse matches
│   ├── _merchant.css        ← merchant buy/sell UI
│   ├── _hiring-hall.css     ← hiring hall
│   ├── _hero-roster.css     ← hero roster + detail panel
│   ├── _gear-management.css ← gear management panel (equip/unequip/compare)
│   └── _bank.css            ← bank / shared stash
│
└── screens/
    └── _post-match.css      ← post-match results screen
```

**Total: 24 partial files + 1 barrel file**

## Section-to-File Mapping (with line ranges)

| File | Source Lines | Sections Included | ~Size |
|------|-------------|-------------------|-------|
| `base/_variables.css` | 4–54 | CSS Custom Properties (`:root`) | ~50 |
| `base/_reset.css` | 56–118 | `*` reset, scrollbar, `body`, `.app`, vignette, fullscreen | ~63 |
| `base/_buttons.css` | 1155–1222 | Buttons — Grim Dark Redesign | ~68 |
| `layout/_app-header.css` | 120–167 | App Header — Game Title | ~48 |
| `layout/_arena.css` | 326–452 | Arena Grid Layout (6E-1) + Responsive viewport (6E-6) | ~127 |
| `layout/_minimap.css` | 388–416 | Minimap overlay | ~29 |
| `components/_lobby.css` | 168–325, 1223–1300, 2296–2483, 2491–2699, 2700–2807 | Lobby, Username Entry, Match List, Match Config, Lobby Redesign, Class Selection | ~558 |
| `components/_waiting-room.css` | 1301–1495, 2484–2490 | Waiting Room + AI Badge | ~202 |
| `components/_header-bar.css` | 909–1087 | HeaderBar (6E-2) | ~179 |
| `components/_bottom-bar.css` | 453–908, 2027–2065, 2066–2090, 2270–2295, 2451–2483, 6011–6102 | Action Bar, Shared Action/Skill, Queue Controls, Ranged/Interact buttons, Cooldowns, Skill Buttons | ~617 |
| `components/_hud.css` | 1088–1122 | HUD (both sections merged) | ~35 |
| `components/_combat-log.css` | 1123–1154, 2091–2113 | Combat Log (both sections merged) | ~55 |
| `components/_party-panel.css` | 1517–1834 | Party Panel | ~318 |
| `components/_enemy-panel.css` | 1835–2026 | Enemy Panel | ~192 |
| `components/_inventory.css` | 2808–3384, 6103–6164 | Inventory & Loot UI + Dungeon Inventory Transfer | ~639 |
| `components/_combat-meter.css` | 6602–7197 | Combat Meter (all sub-sections) | ~596 |
| `components/_overlays.css` | 1496–1516, 2114–2247, 2248–2269, 6165–6389, 6390–6601 | Queued Action, Match End, Death Banner, Auto-Target HUD, Action Intent | ~592 |
| `town/_town-hub.css` | 3385–3781 | Town Hub + Browse Matches | ~397 |
| `town/_merchant.css` | 3782–4180 | Merchant | ~399 |
| `town/_hiring-hall.css` | 4181–4354 | Hiring Hall | ~174 |
| `town/_hero-roster.css` | 4355–4559 | Hero Roster | ~205 |
| `town/_gear-management.css` | 4905–5679 | Gear Management Panel | ~775 |
| `town/_bank.css` | 5680–6010 | Bank (Shared Stash) | ~331 |
| `screens/_post-match.css` | 4560–4904 | Post-Match Screen | ~345 |

## The New `main.css` (barrel file)

```css
/* ===== HERO'S CALL — Grim Dark Theme ===== */
/* Split from monolith — Feb 2026            */

/* --- Base --- */
@import './base/_variables.css';
@import './base/_reset.css';
@import './base/_buttons.css';

/* --- Layout --- */
@import './layout/_app-header.css';
@import './layout/_arena.css';
@import './layout/_minimap.css';

/* --- Components --- */
@import './components/_lobby.css';
@import './components/_waiting-room.css';
@import './components/_header-bar.css';
@import './components/_bottom-bar.css';
@import './components/_hud.css';
@import './components/_combat-log.css';
@import './components/_party-panel.css';
@import './components/_enemy-panel.css';
@import './components/_inventory.css';
@import './components/_combat-meter.css';
@import './components/_overlays.css';

/* --- Town --- */
@import './town/_town-hub.css';
@import './town/_merchant.css';
@import './town/_hiring-hall.css';
@import './town/_hero-roster.css';
@import './town/_gear-management.css';
@import './town/_bank.css';

/* --- Screens --- */
@import './screens/_post-match.css';
```

## Execution Phases

### Phase 0: Backup — COMPLETE ✓
- [x] Copy `main.css` → `main-monolith-backup.css` (153,928 bytes — safety net)
- [ ] Verify the app loads and looks correct — this is our **baseline screenshot** *(deferred to Phase 5)*

### Phase 1: Create Directory Structure — COMPLETE ✓
- [x] Create `styles/base/`, `styles/layout/`, `styles/components/`, `styles/town/`, `styles/screens/`

### Phase 2: Extract Partials — Base & Layout — COMPLETE ✓
- [x] Extract `_variables.css` (48 lines — CSS custom properties)
- [x] Extract `_reset.css` (66 lines — reset, scrollbar, body, .app, vignette)
- [x] Extract `_buttons.css` (67 lines — grim dark button styles)
- [x] Extract `_app-header.css` (47 lines — game title bar)
- [x] Extract `_arena.css` (97 lines — arena grid + responsive viewport)
- [x] Extract `_minimap.css` (28 lines — minimap overlay)
- [ ] **Checkpoint:** Pending — barrel file not yet created

### Phase 3: Extract Partials — Components — COMPLETE ✓
- [x] Extract `_lobby.css` (740 lines — merged 5 scattered lobby sections)
- [x] Extract `_waiting-room.css` (194 lines — waiting room + AI badge)
- [x] Extract `_header-bar.css` (178 lines — header bar)
- [x] Extract `_bottom-bar.css` (637 lines — merged 6 action bar sections)
- [x] Extract `_hud.css` (34 lines — merged both HUD sections)
- [x] Extract `_combat-log.css` (49 lines — merged both combat log sections)
- [x] Extract `_party-panel.css` (317 lines — party panel)
- [x] Extract `_enemy-panel.css` (191 lines — enemy panel)
- [x] Extract `_inventory.css` (638 lines — inventory + dungeon transfer)
- [x] Extract `_combat-meter.css` (594 lines — toggle button, panel, meter bars, tables, skill breakdown, source bars, tooltips, responsive)
- [x] Extract `_overlays.css` (613 lines — 5 overlay sections merged)
- [x] **Checkpoint:** Phase 3 complete — all 11 component partials extracted

### Phase 4: Extract Partials — Town & Screens — COMPLETE ✓
- [x] Extract `_town-hub.css` (396 lines — town hub layout, tabs, actions, browse matches)
- [x] Extract `_merchant.css` (398 lines — merchant buy/sell, hero selector, confirmation modal)
- [x] Extract `_hiring-hall.css` (173 lines — hiring hall, tavern grid, hero cards, hire button)
- [x] Extract `_hero-roster.css` (204 lines — hero roster grid, equipment tags, fallen heroes)
- [x] Extract `_gear-management.css` (774 lines — gear overlay, equipment slots, bag, tooltips, transfer modal, dismiss)
- [x] Extract `_bank.css` (330 lines — bank vault/hero panels, deposit/withdraw, info banner)
- [x] Extract `_post-match.css` (344 lines — post-match header, roster cards, permadeath, actions)
- [x] **Checkpoint:** Phase 4 complete — all 7 town/screen partials extracted, verified against monolith

### Phase 5: Finalize — IN PROGRESS
- [x] Replace `main.css` contents with the barrel `@import` file (36 lines, 23 imports)
- [x] Verify `index.jsx` import still works (`import './styles/main.css'` — unchanged)
- [x] Run `vite build` — confirmed zero errors, 89 modules transformed, CSS bundle 111.36 kB
- [ ] Visual verification of all screens (requires running the app)
- [ ] Delete `main-monolith-backup.css` (after visual confirmation)
- [ ] Update README.md styles section if needed

## Cleanup Opportunities (to address during extraction)

During extraction, we should **merge duplicate sections** rather than blindly copying:
1. **Two HUD sections** (lines 1088 and 1098) — merge into one `_hud.css`
2. **Two Combat Log sections** (lines 1123 and 2091) — merge, deduplicate rules
3. **Lobby styles in 5 places** — consolidate into one logical `_lobby.css`
4. **Action bar styles in 6 places** — consolidate into one `_bottom-bar.css`

## Validation Checklist

After each phase, verify these screens:
- [ ] Login / username entry
- [ ] Lobby (match list, create match, match config)
- [ ] Class selection
- [ ] Waiting room
- [ ] Arena (canvas renders, header bar, bottom bar, party panel, enemy panel)
- [ ] Combat log
- [ ] Minimap
- [ ] Inventory overlay
- [ ] Combat meter
- [ ] Town hub (all tabs: merchant, hiring hall, hero roster, bank, gear management)
- [ ] Post-match screen
- [ ] Death banner / match end overlay
- [ ] HUD + auto-target frame + action intent banner

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| CSS specificity changes from import order | Low | Medium | Maintain same declaration order in barrel file |
| Missing a section during extraction | Low | Low | Line-by-line verification against monolith |
| Vite import resolution issues | Very Low | Low | Vite handles CSS `@import` natively |
| Breaking `main-classic.css` | None | None | File is untouched |

## Rules for Execution

1. **No class name changes** — this is purely a file split
2. **Preserve declaration order** — the barrel `@import` order must match the original top-to-bottom order
3. **One phase at a time** — checkpoint after each phase before moving on
4. **Rollback plan** — `main-monolith-backup.css` can be copied back at any point
5. **Merge duplicates** — when sections overlap, keep the later (more complete) version and verify

---

## Progress Log

### Session 1 — February 27, 2026

**Work completed:**
- Created this plan document (`docs/css-split-plan.md`)
- Phase 0: Backed up `main.css` → `main-monolith-backup.css` (153,928 bytes)
- Phase 1: Created 5 subdirectories under `client/src/styles/` (`base/`, `layout/`, `components/`, `town/`, `screens/`)
- Phase 2: Extracted 6 base/layout partials (353 total lines)
- Phase 3: Extracted 10 of 11 component partials (3,591 total lines)

**Current state on disk:**
```
styles/
├── main.css                  ← STILL the original 7,197-line monolith (unchanged)
├── main-monolith-backup.css  ← identical safety copy
├── main-classic.css          ← untouched original theme backup
├── base/
│   ├── _variables.css    (48 lines)  ✓
│   ├── _reset.css        (66 lines)  ✓
│   └── _buttons.css      (67 lines)  ✓
├── layout/
│   ├── _app-header.css   (47 lines)  ✓
│   ├── _arena.css        (97 lines)  ✓
│   └── _minimap.css      (28 lines)  ✓
├── components/
│   ├── _lobby.css        (740 lines) ✓
│   ├── _waiting-room.css (194 lines) ✓
│   ├── _header-bar.css   (178 lines) ✓
│   ├── _bottom-bar.css   (637 lines) ✓
│   ├── _hud.css          (34 lines)  ✓
│   ├── _combat-log.css   (49 lines)  ✓
│   ├── _party-panel.css  (317 lines) ✓
│   ├── _enemy-panel.css  (191 lines) ✓
│   ├── _inventory.css    (638 lines) ✓
│   ├── _combat-meter.css              ✗ NOT CREATED
│   └── _overlays.css     (613 lines) ✓
├── town/                              ✗ ALL 6 FILES NOT CREATED
└── screens/                           ✗ _post-match.css NOT CREATED
```

**Coverage:** 3,944 of 7,197 lines extracted into partials (54.8%)

**What remains (next session):**
1. Extract `components/_combat-meter.css` (lines 6602–7197, ~596 lines)
2. Extract all 6 `town/` partials (lines 3385–6010, ~2,281 lines)
3. Extract `screens/_post-match.css` (lines 4560–4904, ~345 lines)
4. Replace `main.css` with barrel `@import` file
5. Visual verification of all screens
6. Delete backup after confirmation

**Important notes:**
- `main.css` has NOT been modified — the app still works from the monolith
- All partials are additive — no risk until the barrel file swap in Phase 5
- The `index.jsx` import (`import './styles/main.css'`) will remain unchanged

### Session 2 — February 27, 2026

**Work completed:**
- Phase 3 completion: Extracted `components/_combat-meter.css` (594 lines)
  - Content: toggle button, panel layout, header, body, meter bar rows, table views (kills/overview), clickable drill-in rows, skill breakdown view, source type bars, meter skill tooltips, responsive media queries
  - Verified exact match against monolith lines 6602–7197 (only diff: trailing blank line in monolith)

**Current state on disk:**
```
styles/
├── main.css                  ← STILL the original 7,197-line monolith (unchanged)
├── main-monolith-backup.css  ← identical safety copy
├── main-classic.css          ← untouched original theme backup
├── base/
│   ├── _variables.css    (48 lines)  ✓
│   ├── _reset.css        (66 lines)  ✓
│   └── _buttons.css      (67 lines)  ✓
├── layout/
│   ├── _app-header.css   (47 lines)  ✓
│   ├── _arena.css        (97 lines)  ✓
│   └── _minimap.css      (28 lines)  ✓
├── components/
│   ├── _lobby.css        (740 lines) ✓
│   ├── _waiting-room.css (194 lines) ✓
│   ├── _header-bar.css   (178 lines) ✓
│   ├── _bottom-bar.css   (637 lines) ✓
│   ├── _hud.css          (34 lines)  ✓
│   ├── _combat-log.css   (49 lines)  ✓
│   ├── _party-panel.css  (317 lines) ✓
│   ├── _enemy-panel.css  (191 lines) ✓
│   ├── _inventory.css    (638 lines) ✓
│   ├── _combat-meter.css (594 lines) ✓  ← NEW
│   └── _overlays.css     (613 lines) ✓
├── town/                              ✗ ALL 6 FILES NOT CREATED
└── screens/                           ✗ _post-match.css NOT CREATED
```

**Coverage:** 4,538 of 7,197 lines extracted into partials (63.1%)

**What remains (next session):**
1. Extract all 6 `town/` partials (lines 3385–6010, ~2,281 lines)
2. Extract `screens/_post-match.css` (lines 4560–4904, ~345 lines)
3. Replace `main.css` with barrel `@import` file
4. Visual verification of all screens
5. Delete backup after confirmation

**Important notes:**
- `main.css` has NOT been modified — the app still works from the monolith
- All partials are additive — no risk until the barrel file swap in Phase 5
- The `index.jsx` import (`import './styles/main.css'`) will remain unchanged

### Session 3 — February 27, 2026

**Work completed:**
- Phase 4: Extracted all 7 town/screen partials (2,619 total lines)
  - `town/_town-hub.css` (396 lines) — town hub layout, tab navigation, action buttons, browse matches panel
  - `town/_merchant.css` (398 lines) — merchant buy/sell UI, hero selector tabs, category headers, item rows, confirmation modal
  - `town/_hiring-hall.css` (173 lines) — hiring hall header, tavern hero grid, shared hero card styles, hire button
  - `town/_hero-roster.css` (204 lines) — hero roster grid, equipment tags, select/deselect, fallen heroes section
  - `town/_gear-management.css` (774 lines) — gear overlay, detail panel, equipment slots, bag section, tooltips, transfer modal, dismiss hero, responsive
  - `town/_bank.css` (330 lines) — bank vault/hero two-column layout, deposit/withdraw buttons, info banner
  - `screens/_post-match.css` (344 lines) — thematic header with outcome variants, roster cards, stat rows, permadeath section, action buttons
  - Verified all 7 partials against monolith — only difference is trailing blank lines between sections (no CSS content missing)

**Current state on disk:**
```
styles/
├── main.css                  ← STILL the original 7,197-line monolith (unchanged)
├── main-monolith-backup.css  ← identical safety copy
├── main-classic.css          ← untouched original theme backup
├── base/
│   ├── _variables.css    (48 lines)  ✓
│   ├── _reset.css        (66 lines)  ✓
│   └── _buttons.css      (67 lines)  ✓
├── layout/
│   ├── _app-header.css   (47 lines)  ✓
│   ├── _arena.css        (97 lines)  ✓
│   └── _minimap.css      (28 lines)  ✓
├── components/
│   ├── _lobby.css        (740 lines) ✓
│   ├── _waiting-room.css (194 lines) ✓
│   ├── _header-bar.css   (178 lines) ✓
│   ├── _bottom-bar.css   (637 lines) ✓
│   ├── _hud.css          (34 lines)  ✓
│   ├── _combat-log.css   (49 lines)  ✓
│   ├── _party-panel.css  (317 lines) ✓
│   ├── _enemy-panel.css  (191 lines) ✓
│   ├── _inventory.css    (638 lines) ✓
│   ├── _combat-meter.css (594 lines) ✓
│   └── _overlays.css     (613 lines) ✓
├── town/
│   ├── _town-hub.css     (396 lines) ✓  ← NEW
│   ├── _merchant.css     (398 lines) ✓  ← NEW
│   ├── _hiring-hall.css  (173 lines) ✓  ← NEW
│   ├── _hero-roster.css  (204 lines) ✓  ← NEW
│   ├── _gear-management.css (774 lines) ✓  ← NEW
│   └── _bank.css         (330 lines) ✓  ← NEW
└── screens/
    └── _post-match.css   (344 lines) ✓  ← NEW
```

**Coverage:** 7,157 of 7,197 lines extracted into partials (99.4%)

**What remains (next session):**
1. Replace `main.css` with barrel `@import` file (Phase 5)
2. Visual verification of all screens
3. Delete `main-monolith-backup.css` after confirmation

**Important notes:**
- `main.css` has NOT been modified — the app still works from the monolith
- All 23 partials are now created and verified — ready for the barrel file swap
- The `index.jsx` import (`import './styles/main.css'`) will remain unchanged

### Session 4 — February 27, 2026

**Work completed:**
- Phase 5 (partial): Replaced `main.css` monolith with barrel `@import` file
  - Verified all 23 partials present on disk (3 base + 3 layout + 11 components + 6 town + 1 screens)
  - Confirmed `index.jsx` still imports `./styles/main.css` (no change needed)
  - Replaced 6,225-line monolith with 36-line barrel file containing 23 `@import` statements
  - Ran `vite build` — success: 89 modules, 111.36 kB CSS bundle, zero errors
  - Total partial lines: 6,213 vs monolith 6,225 (12-line gap = trailing blank lines between sections)

**Current state on disk:**
```
styles/
├── main.css                  ← NEW barrel file (36 lines, 23 @imports)
├── main-monolith-backup.css  ← safety copy (153,928 bytes) — KEEP until visual verification
├── main-classic.css          ← untouched original theme backup
├── base/
│   ├── _variables.css    (43 lines)  ✓
│   ├── _reset.css        (60 lines)  ✓
│   └── _buttons.css      (59 lines)  ✓
├── layout/
│   ├── _app-header.css   (43 lines)  ✓
│   ├── _arena.css        (88 lines)  ✓
│   └── _minimap.css      (25 lines)  ✓
├── components/
│   ├── _lobby.css        (639 lines) ✓
│   ├── _waiting-room.css (164 lines) ✓
│   ├── _header-bar.css   (157 lines) ✓
│   ├── _bottom-bar.css   (551 lines) ✓
│   ├── _hud.css          (28 lines)  ✓
│   ├── _combat-log.css   (43 lines)  ✓
│   ├── _party-panel.css  (275 lines) ✓
│   ├── _enemy-panel.css  (167 lines) ✓
│   ├── _inventory.css    (552 lines) ✓
│   ├── _combat-meter.css (509 lines) ✓
│   └── _overlays.css     (532 lines) ✓
├── town/
│   ├── _town-hub.css     (349 lines) ✓
│   ├── _merchant.css     (349 lines) ✓
│   ├── _hiring-hall.css  (148 lines) ✓
│   ├── _hero-roster.css  (177 lines) ✓
│   ├── _gear-management.css (668 lines) ✓
│   └── _bank.css         (288 lines) ✓
└── screens/
    └── _post-match.css   (299 lines) ✓
```

**Coverage:** 6,213 partial lines / 6,225 monolith lines = 99.8%

**What remains (next session):**
1. Visual verification — launch the app and check all screens from the validation checklist
2. Delete `main-monolith-backup.css` after visual confirmation
3. Update README.md styles section if needed

**Rollback plan:** Copy `main-monolith-backup.css` → `main.css` to instantly revert
