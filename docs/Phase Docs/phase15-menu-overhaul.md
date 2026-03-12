# Phase 15 — Menu & UI Overhaul: From Website to Roguelike

**Goal:** Transform every pre-game screen (Login, Town Hub, Waiting Room, Post-Match) from a website-style interface into something that feels like a proper roguelike game menu — think Darkest Dungeon, Diablo II, Path of Exile character select.

**Guiding Principles:**
- **Keep all existing functionality** — nothing breaks, nothing gets removed
- **Preserve the color palette** — ember gold, crimson, deep purples/blacks are perfect
- **Preserve the font stack** — Cinzel, Crimson Text, Fira Code all stay
- **CSS-first approach** — most changes are styling/layout, minimal JSX restructuring
- **Incremental phases** — each chunk is independently shippable and testable

---

## Current Problems (Why It Feels Like a Website)

| Problem | Where | Why It Feels Wrong |
|---------|-------|--------------------|
| Horizontal tab bar | TownHub | Looks like a SaaS dashboard or browser tabs |
| Narrow centered containers | Lobby (560px), WaitingRoom (640px) | Feels like a web signup form, not a game |
| Flat bordered panels | Everywhere | Plain `border: 1px solid` boxes with no depth or character |
| No ornate framing | All panels | Game menus have frames, bevels, corner ornaments |
| Simple list patterns | Match list, hero grid | Look like data tables, not quest boards or game rosters |
| Plain form inputs | Login, config selects | Standard web form elements, not themed game inputs |
| No decorative separators | Section breaks | Just `border-bottom: 1px` lines everywhere |
| No visual hierarchy | Between screens | Every screen is "dark box on dark background" |
| Buttons are functional but flat | All buttons | Need more game-button personality (bevels, glows, weight) |
| No atmospheric elements in menus | All pre-game screens | In-game has particles; menus feel static and lifeless |

---

## Overhaul Plan — 8 Chunks

### Chunk 1: Global Frame System & Decorative CSS Utilities
**Files:** `_variables.css`, new `_frames.css`, `_buttons.css`
**Scope:** Pure CSS additions — no JSX changes

Create a reusable panel/frame system that replaces the flat bordered boxes everywhere. This is the foundation everything else builds on.

**New CSS custom properties:**
```css
/* Frame borders — ornate double-line with corner accents */
--frame-border-outer: 1px solid var(--border-medium);
--frame-border-inner: 1px solid var(--border-dark);
--frame-corner-size: 12px;
--frame-corner-color: var(--accent-ember-dim);

/* Decorative separator */
--separator-ornament: '⬥';  /* or ◆, ◇, ✦ */
```

**New `.grim-frame` class** (reusable ornate panel):
- Double-border effect using `box-shadow` + `border` (outer dark, inner subtle)
- `::before` / `::after` pseudo-elements for corner accents (all 4 corners via nested element or extra wrapper)
- Subtle inner gradient (top-down from slightly lighter to panel color)
- Optional header slot with centered ornamental divider line

**New `.grim-separator` class:**
- Horizontal rule with centered ornament symbol (like the existing `— ◆ —` pattern)
- Variants: `--ember`, `--crimson`, `--subtle`

**New `.grim-header` class:**
- Section header with ornamental underline
- Small decorative elements flanking the text
- Uses Cinzel font with tracked uppercase

**Button overhaul — `.grim-btn` variants:**
- Add `box-shadow: inset 0 1px 0 rgba(255,255,255,0.05)` for top-edge highlight (beveled look)
- Add `border-image` or multi-layered border for a hammered-metal feel
- Active state pushes down with darker inset shadow
- Hover state adds ember glow pulse (subtle `@keyframes` animation)
- Sizes: `--sm`, `--md`, `--lg`
- Colors: `--ember` (primary), `--crimson` (danger/pvp), `--verdant` (confirm/dungeon), `--steel` (neutral)

**Deliverable:** A utility CSS toolkit. Zero visual change yet (classes exist but aren't applied). Tested by adding classes to a single element temporarily.

#### Chunk 1 — Implementation Log (March 1, 2026)

**Status: COMPLETE** — All CSS utilities built, zero visual regressions, Vite build passes.

**Files modified:**
| File | Change |
|------|--------|
| `client/src/styles/base/_variables.css` | Added 9 new custom properties: `--frame-border-outer`, `--frame-border-inner`, `--frame-corner-size`, `--frame-corner-color`, `--separator-ornament`, `--frame-shadow`, `--frame-glow-ember/crimson/verdant`, `--btn-bevel-highlight`, `--btn-bevel-pressed` |
| `client/src/styles/base/_frames.css` | **NEW** — 260-line frame system with `.grim-frame`, `.grim-separator`, `.grim-header` + variants |
| `client/src/styles/base/_buttons.css` | Added `.grim-btn` system (~200 lines) with size (`--sm/--md/--lg`) and color (`--ember/--crimson/--verdant/--steel`) variants, keyframe glow animations, full-width & icon modifiers |
| `client/src/styles/main.css` | Added `@import './base/_frames.css'` after `_buttons.css` |

**New CSS classes available:**
- `.grim-frame` — Ornate double-border panel with corner accents, inner gradient, and layered shadow
  - Modifiers: `--ember`, `--crimson`, `--verdant` (glow), `--recessed` (sunken), `--elevated` (raised)
- `.grim-separator` — Ornamental horizontal rule (use as `<div class="grim-separator">◆</div>`)
  - Modifiers: `--ember`, `--crimson`, `--subtle`
- `.grim-header` — Cinzel uppercase section header with ornamental underline and flanking dots
  - Modifiers: `--sm`, `--lg`, `--left`, `--crimson`
- `.grim-btn` — Beveled hammered-metal game button with hover glow animations
  - Sizes: `--sm`, `--md`, `--lg`
  - Colors: `--ember` (primary), `--crimson` (danger), `--verdant` (confirm), `--steel` (neutral)
  - Modifiers: `--full` (width:100%), `--icon` (square icon button)

**Verification:**
- Vite production build: ✓ (120.37 KB CSS, 0 errors)
- No lint errors or warnings
- Zero visual changes — all classes are additive, no existing styles modified
- Existing `.btn-primary`, `.btn-leave`, base `button` styles fully preserved

---

### Chunk 2: Login / Title Screen Overhaul
**Files:** `Lobby.jsx` (landing section only), `_lobby.css`
**Scope:** CSS overhaul + minor JSX additions (decorative elements)

Transform the login card from a simple centered form into an immersive game title screen.

**Changes:**
- **Full-viewport layout** — login screen becomes a full centered splash, not a small card
- **Game title prominent** — Large "HERO'S CALL" (or game name) rendered in Cinzel with text-shadow glow, stacked above the login card
- **Ornate login frame** — Apply `.grim-frame` to the login card, expand corner accents to all 4 corners
- **Username input styling** — Wider input with ornate left/right border accents, subtle background pattern
- **"Enter" button** — Full-width below input, larger, with glow animation on hover
- **Flavor text** — Styled as parchment-scroll text (slightly warmer background strip behind it)
- **Decorative dividers** — `.grim-separator` above and below the form
- **Subtle background enhancement** — Add a faint repeating tile pattern (CSS-only, radial/conic gradients) or a low-opacity noise texture to body background behind the login only
- **Version/credits line** at bottom: `Phase 15 · Arena Prototype` in dim text

**Visual Target:** Think Darkest Dungeon's "click to start" screen meets Diablo II's login — dark, atmospheric, the game title is the star.

#### Chunk 2 — Implementation Log (March 1, 2026)

**Status: COMPLETE** — Login screen transformed into immersive title screen, zero visual regressions, Vite build passes.

**Files modified:**
| File | Change |
|------|--------|
| `client/src/components/Lobby/Lobby.jsx` | Restructured login JSX: added `.lobby-landing-inner` wrapper, game title block (`.lobby-title` with `<h1>` "Hero's Call" + subtitle), `.grim-separator--ember` dividers, applied `.grim-frame.grim-frame--ember` to login card, replaced `btn-enter-name` with `.grim-btn--lg.grim-btn--ember.grim-btn--full`, added `grim-header` to heading, `.grim-separator--subtle` ornaments, version/credits line |
| `client/src/styles/components/_lobby.css` | Major overhaul of login/landing section (~120 new lines). Preserved all post-login lobby styles intact |

**CSS changes in `_lobby.css`:**
- `.lobby-landing` — Full-viewport centered splash (`min-height: calc(100vh - 2rem)`), no `max-width` constraint
- `.lobby-landing::before` — Atmospheric fixed background: repeating-conic-gradient crosshatch texture, radial ember glow behind title area, deep vignette overlay
- `.lobby-landing-inner` — Flex column wrapper, `max-width: 480px`, centers content with proper z-index above background
- `.lobby-title-text` — `clamp(2.2rem, 5vw, 3.2rem)` Cinzel title with layered text-shadow glow + `@keyframes title-glow` subtle pulsing animation
- `.lobby-title-sub` — Smaller tracked subtitle ("Arena & Dungeon")
- `.lobby-landing-card` — Wider card (`max-width: 440px`), uses `.grim-frame` for ornate double-border with all 4 corner accents
- `.lobby-landing-flavor` — Parchment-scroll treatment: warm semi-transparent gradient background strip
- `.lobby-landing .username-form` — Stacked layout (`flex-direction: column`), full-width input with centered text, ornate left/right ember border accents on focus
- `.lobby-version` — Dim monospace version line at bottom (`opacity: 0.6`)
- Responsive breakpoint at 480px for mobile

**JSX structure (login screen):**
```
lobby lobby-landing
  └── lobby-landing-inner
      ├── lobby-title
      │   ├── h1.lobby-title-text — "Hero's Call"
      │   └── p.lobby-title-sub — "Arena & Dungeon"
      ├── grim-separator--ember — ◆
      ├── lobby-landing-card.grim-frame.grim-frame--ember
      │   ├── h2.grim-header — "Enter the Arena"
      │   ├── p.lobby-landing-flavor — flavor text
      │   ├── grim-separator--subtle — ⬥
      │   ├── form.username-form
      │   │   ├── input — username
      │   │   └── button.grim-btn--lg.grim-btn--ember.grim-btn--full — "Enter Arena"
      │   └── grim-separator--subtle — ⬥
      └── p.lobby-version — "Phase 15 · Arena Prototype"
```

**What changed visually:**
- Login is now a full-viewport immersive title screen (was a small centered card)
- Large dramatic "HERO'S CALL" title with animated ember glow dominates the top
- Login card uses the grim-frame ornate panel system (double border, 4 corner accents, ember glow shadow)
- Username input is full-width, centered text, with ornate ember border accents on focus
- "Enter Arena" button is full-width, large, with the `.grim-btn` hammered-metal system + ember hover pulse
- Flavor text has warm parchment-scroll background treatment
- Decorative ◆ and ⬥ separators frame the form sections
- Atmospheric background: subtle crosshatch texture + radial ember glow + vignette
- Version/credits line anchors the bottom

**Verification:**
- Vite production build: ✓ (122.59 KB CSS, 0 errors)
- No lint errors or warnings
- All post-login lobby styles preserved (match list, buttons, chat, class selection, config)
- `.btn-primary`/`.btn-enter-name` base styles preserved in `_buttons.css` (backward compat)
- Zero functionality changes — form submit, username validation, dispatch all identical

---

### Chunk 3: Town Hub — Navigation Overhaul
**Files:** `TownHub.jsx`, `_town-hub.css`
**Scope:** JSX restructuring of tab navigation + CSS overhaul

This is the biggest single change. Replace the horizontal tab bar with a **sidebar navigation panel** that feels like navigating locations in a town.

**Layout Change:**
```
BEFORE (website):
┌─────────────────────────────────┐
│ Town Hub          Welcome, user │
│ [Roster][Hiring][Merchant][Bank]│
│ ┌─────────────────────────────┐ │
│ │     Tab Content Area        │ │
│ └─────────────────────────────┘ │
│ [Enter Dungeon] [Enter Arena]   │
└─────────────────────────────────┘

AFTER (roguelike):
┌───────────────┬─────────────────┐
│  ◆ TOWN HUB  │                 │
│  ─────────── │  Content Area   │
│               │  (framed panel) │
│  ⚔ Roster    │                 │
│  🏛 Hiring    │                 │
│  🪙 Merchant  │                 │
│  🏦 Bank      │                 │
│  📜 Quests    │                 │
│               │                 │
│  ─────────── │                 │
│  Gold: 450g  │                 │
│               ├─────────────────┤
│  [Dungeon]   │  Status / Info  │
│  [Arena]     │  (optional)     │
└───────────────┴─────────────────┘
```

**Sidebar details:**
- Fixed-width left panel (~220px) with `.grim-frame` styling
- Navigation items are stacked vertically — each is a location "button" with:
  - Icon (text/emoji initially, sprite later)
  - Location name in Cinzel
  - Optional count badge (hero count, bank items)
  - Active state: ember-highlighted left border + glow background
  - Hover: subtle slide-in highlight
- Ornamental separator between nav sections
- Gold display integrated into sidebar bottom
- Action buttons (Enter Dungeon, Enter Arena) in sidebar below nav, styled as major CTA buttons

**Content area:**
- Takes remaining width
- Wrapped in `.grim-frame`
- Content header with location name + ornamental underline
- Scrollable content below

**Responsive consideration:** Below 900px, sidebar collapses to a top bar (but styled as icon buttons, not web tabs)

#### Chunk 3 — Implementation Log (March 1, 2026)

**Status: COMPLETE** — Town Hub restructured from horizontal tab bar to sidebar navigation, zero functionality regressions, Vite build passes.

**Files modified:**
| File | Change |
|------|--------|
| `client/src/components/TownHub/TownHub.jsx` | Major restructure: replaced horizontal tab bar with sidebar `<aside>` navigation + `<main>` content area. Added `NAV_ITEMS` / `CONTENT_TITLES` constants, sidebar nav with icons/badges, gold display in sidebar, action buttons (Enter Dungeon/Arena) moved to sidebar using `.grim-btn` system. Content area wrapped in `.grim-frame` with `.grim-header--left` section titles. |
| `client/src/styles/town/_town-hub.css` | Complete CSS overhaul (~310 new/rewritten lines). Replaced column flex layout with row flex (sidebar + content). Added responsive collapse at 900px breakpoint. Preserved all legacy button styles and browse matches panel styles. |

**Layout change:**
```
BEFORE:                             AFTER:
┌────────────────────────┐         ┌──────────┬──────────────┐
│ Town Hub    Welcome  g │         │ TOWN HUB │              │
│ [Roster][Hiring][...]  │         │ Welcome  │ Content Area │
│ ┌────────────────────┐ │         │ ◆─────── │ (grim-frame) │
│ │   Tab Content      │ │         │ ⚔ Roster │              │
│ └────────────────────┘ │  →      │ 🏛 Hiring │              │
│ [Enter Dungeon] [Arena]│         │ 🪙 Merch  │              │
└────────────────────────┘         │ 🏦 Bank   │              │
                                   │ 📜 Notice │              │
                                   │ ⬥─────── │              │
                                   │ Gold: Xg  │              │
                                   │ ⬥─────── │              │
                                   │ [Dungeon] │              │
                                   │ [Arena]   │              │
                                   └──────────┴──────────────┘
```

**New CSS classes:**
- `.town-hub` — Row flex layout (sidebar | content), `max-width: 1400px`
- `.town-hub-sidebar` — 230px fixed-width sidebar, `.grim-frame` styled, flex column
- `.town-sidebar-header` — Centered title + welcome text with torch-flicker text-shadow
- `.town-sidebar-nav` — Vertical stacked nav container
- `.town-nav-item` — Location button with icon + label + optional count badge
  - Hover: slide-in highlight with left border color
  - Active (`--active`): ember gradient background, glowing left border accent, bold label
- `.town-nav-icon` — Fixed-width emoji icon column
- `.town-nav-label` — Cinzel uppercase location name
- `.town-nav-count` — Mono badge for item/hero counts
- `.town-sidebar-gold` — Gold label + value row
- `.town-sidebar-actions` — Stacked Enter Dungeon / Enter Arena buttons using `.grim-btn--verdant` / `.grim-btn--crimson`
- `.town-hub-content` — Flex-grow content area, `.grim-frame` styled, with scrollable body
- `.town-content-header` — Section title using `.grim-header--left`
- `.town-content-body` — Scrollable content area with thin scrollbar

**JSX structure:**
```
town-hub (row flex)
  ├── aside.town-hub-sidebar.grim-frame
  │   ├── town-sidebar-header
  │   │   ├── h2.town-sidebar-title — "Town Hub"
  │   │   └── span.town-welcome — "Welcome, {username}"
  │   ├── grim-separator--ember — ◆
  │   ├── nav.town-sidebar-nav
  │   │   └── button.town-nav-item (×5: Roster, Hiring, Merchant, Bank, Notice Board)
  │   │       ├── span.town-nav-icon
  │   │       ├── span.town-nav-label
  │   │       └── span.town-nav-count (conditional)
  │   ├── grim-separator--subtle — ⬥
  │   ├── town-sidebar-gold
  │   │   ├── span.town-gold-label — "Gold"
  │   │   └── span.gold-display — "{gold}g"
  │   ├── grim-separator--subtle — ⬥
  │   └── town-sidebar-actions
  │       ├── button.grim-btn--verdant — "Enter Dungeon"
  │       └── button.grim-btn--crimson — "Enter Arena"
  └── main.town-hub-content.grim-frame
      ├── town-content-header
      │   └── h3.grim-header.grim-header--left — "{active tab title}"
      ├── p.town-error (conditional)
      └── town-content-body
          └── {HeroRoster | HiringHall | Merchant | Bank | BrowseMatches}
```

**Responsive behavior (≤900px):**
- Layout flips from row to column
- Sidebar becomes a horizontal top bar: header hidden, nav items become horizontal icon+label buttons
- Active state uses bottom border instead of left border
- Gold display becomes inline compact badge
- Action buttons become a horizontal row (flex: 1 each)
- Content area gets `min-height: 400px`

**What changed visually:**
- Town Hub is now a two-panel layout: sidebar (locations) + content (framed panel)
- Navigation feels like moving through locations in a town, not clicking website tabs
- Each nav item has an icon, Cinzel label, and optional count badge
- Active location has an ember-highlighted left border with gradient glow background
- Gold display integrated into sidebar with label
- Enter Dungeon/Enter Arena are major CTA buttons in the sidebar using the `.grim-btn` system
- All panels use `.grim-frame` for ornate double-border with corner accents
- Content area has a `.grim-header--left` section title with ornamental underline
- Decorative ◆ and ⬥ separators divide sidebar sections

**What was preserved:**
- All existing functionality — tab switching, hero selection, match joining, dungeon entry, arena entry
- All sub-components render identically (HeroRoster, HiringHall, Merchant, Bank, browse matches)
- Browse matches panel CSS fully preserved
- Legacy button styles preserved for backward compatibility
- Procedural dungeon badge styles preserved (used in WaitingRoom)
- All event handlers, state management, API calls identical

**Verification:**
- Vite production build: ✓ (124.47 KB CSS, 0 errors)
- No lint errors or warnings
- Zero functionality changes — all form submits, fetch calls, dispatches identical
- Sub-components (HeroRoster, HiringHall, Merchant, Bank) render unchanged
- Responsive breakpoint at 900px properly collapses sidebar to top bar

---

### Chunk 4: Panel & Card Styling (Hero Cards, Match Lists, Merchant)
**Files:** `_hero-roster.css`, `_hiring-hall.css`, `_merchant.css`, `_bank.css`, `_town-hub.css` (browse matches section)
**Scope:** Pure CSS — apply frame system to all cards and panels

**Hero Cards (Roster + Hiring Hall):**
- Apply `.grim-frame` to each card
- Add class-color left border accent (Crusader=ember, Confessor=blue, etc.)
- Hero name styled larger in Cinzel with slight text-shadow
- Stats section styled as a "stat block" — uses dotted leaders between label and value (like a D&D character sheet)
- Equipment tags get rarity-colored ornate borders
- "Select for Dungeon" button → full-width bottom bar on card, styled like a banner/ribbon
- Selected state: full ember glow border + corner accents brighten

**Match List (Lobby + Town Browse):**
- Restyle as a "Notice Board" / "Quest Board"
  - Each match entry styled like a pinned notice with slight rotation variance (CSS `transform: rotate`)
  - Match type tag gets a wax-seal look (circular badge)
  - "Join" button styled as a crimson action button
- Section header "Available Matches" → "The Notice Board" with `.grim-header`

**Merchant Panel:**
- Two-column layout already exists — add `.grim-frame` to buy/sell panels
- Item rows get rarity-colored left border
- Buy/sell buttons get coin icon treatment
- "No items" placeholder styled with atmospheric flavor text

**Bank Panel:**
- Vault/chest thematic styling
- Item grid with dark recessed backgrounds (like slots in a container)

#### Chunk 4 — Implementation Log (March 1, 2026)

**Status: COMPLETE** — All panels and cards restyled with grim-frame system, zero visual regressions, Vite build passes.

**Files modified:**
| File | Change |
|------|--------|
| `client/src/styles/town/_hero-roster.css` | Complete card overhaul: grim-frame double-border with corner accents, selected ember glow, ribbon-style select button, ornate rarity equipment tags |
| `client/src/styles/town/_hiring-hall.css` | Grim-frame tavern cards, hero name enlarged with text-shadow, stat-block dotted leaders, hammered-metal hire button with active press state |
| `client/src/styles/town/_merchant.css` | Grim-framed buy/sell panels with inner border + corner accents, rarity left-border items, coin icon (🪙) on buy/sell buttons, atmospheric empty states, grim-framed confirm modal |
| `client/src/styles/town/_bank.css` | Vault/chest themed panels (ember vault, blue-steel hero bag), dark recessed item slots with inset shadow, rarity left-border items, hammered-metal deposit/withdraw buttons, atmospheric empty states |
| `client/src/styles/town/_town-hub.css` | Notice Board restyle: pinned-notice rotation variance, wax-seal match type badges, ornamental header underline, pin accent left-border on hover, enhanced join buttons |

**Hero Cards (Roster) — what changed:**
- `.roster-hero-card` now has full grim-frame treatment: double-border (`::before` inner border), 4 corner accents (`::after` gradient lines), layered depth shadow, inner gradient
- Class-color left border accent via `border-left: 3px solid` (color set by inline style when selected)
- `.roster-hero-selected` gets amplified ember glow (`0 0 40px`) + brighter 14px corner accents
- Equipment tags (`.hero-equip-tag`) have rarity-colored left-border accents: `--common` (steel), `--uncommon` (sickly-green), `--rare` (blue-steel) with glow shadows
- `.btn-select-hero` is now a full-width ribbon banner: extends to card edges (`width: calc(100% + 1.7rem)`, negative margin), border-top separator, hammered-metal bevel, verdant selected state
- `.selected-badge` enhanced with subtle glow shadow

**Hero Cards (Hiring Hall) — what changed:**
- `.tavern-hero-card` gets the same grim-frame treatment as roster cards (double-border, corners, depth)
- `.hero-name` enlarged to 1.05rem with `text-bright` color and text-shadow glow
- `.hero-card-stats` now a D&D stat-block: recessed (`inset box-shadow`), with dotted leader lines between label and value via `::after` on `.hero-stat-label`
- `.hero-stat-value` uses `margin-left: auto` for proper right-alignment
- `.btn-hire` gets hammered-metal bevel (`inset highlight`) + active press state + hover glow
- `.hero-hire-cost` gets text-shadow glow
- `.btn-refresh-tavern` styled with Cinzel uppercase + subtle ember gradient

**Match List (Notice Board) — what changed:**
- `.town-browse-matches h3` gets ornamental gradient underline (ember → dim → transparent)
- `.town-match-item` restyled as pinned notices: grim-frame depth shadow, inner gradient, slight CSS rotation variance (odd/even/3n selectors), pin accent left border (`::before`)
- Hover: rotation resets to 0°, slight translateY lift, ember glow
- `.match-type-tag` in town context: wax-seal circular badge (border-radius: 10px, box-shadow)
- `.btn-join-town` enhanced: hammered-metal bevel, active press state, stronger hover glow
- `.town-match-map` gets italic Crimson Text flavor font

**Merchant Panel — what changed:**
- `.merchant-buy-panel` / `.merchant-sell-panel` get full grim-frame treatment: `::before` inner border, `::after` corner accents, layered depth shadow
- `.merchant-item` gets rarity-colored left border (`border-left: 3px solid`)
- `.btn-merchant-buy` / `.btn-merchant-sell` get 🪙 coin icon via `::before` pseudo-element, hammered-metal bevel, active press state
- `.merchant-empty` gets warm parchment gradient background, more padding
- `.merchant-confirm-modal` gets grim-frame depth shadow + corner accents + inner gradient
- `.merchant-gold` gets text-shadow glow
- Scrollbar styling added (thin, themed)

**Bank Panel — what changed:**
- `.bank-vault-panel` gets ember-themed grim-frame: warm corner accents (12px ember), ember gradient top
- `.bank-hero-panel` gets blue-steel themed grim-frame: cool corner accents, blue gradient top
- `.bank-item` restyled as dark recessed slots: `background: var(--bg-deep)`, `inset box-shadow`, rarity left-border, gap instead of margin-bottom
- `.btn-bank-withdraw` / `.btn-bank-deposit` get hammered-metal bevel + active press state
- `.bank-empty` gets atmospheric warm gradient background
- `.bank-info-banner` gets parchment-scroll gradient + inset shadow
- `.bank-capacity` gets subtle slot counter badge styling
- Scrollbar styling added (thin, themed)

**What was preserved:**
- All existing functionality — zero JSX changes, all event handlers, API calls, state management identical
- All existing class names retained — no breaking changes to markup
- Hero gear management overlay (HeroDetailPanel) unaffected
- Tooltip systems (roster gear tooltip, bank item tooltip) unaffected
- Responsive breakpoints preserved
- All legacy button styles in `_gear-management.css` preserved
- Match type tag styles in `_lobby.css` preserved (town context gets overrides)

**Verification:**
- Vite production build: ✓ (138.46 KB CSS, 0 errors)
- No lint errors or warnings
- Zero JSX changes — pure CSS enhancement
- All sub-components render with same HTML structure
- All interactive functionality identical (select, hire, buy, sell, deposit, withdraw, join)

---

### Chunk 5: Waiting Room / War Room Overhaul
**Files:** `WaitingRoom.jsx`, `_waiting-room.css`, `_lobby.css` (shared styles)
**Scope:** CSS overhaul + minor JSX for decorative elements

**Rename conceptually:** "Waiting Room" → feels like a "War Room" or "Staging Ground"

**Changes:**
- Expand from 640px max-width to full available width (match town hub proportions)
- **Two-column layout:**
  - Left: Player roster + config → framed panel
  - Right: Chat window → framed panel
- **Player list redesign:**
  - Each player rendered as a "unit card" with class icon, name, team badge
  - Ready status shown as a glowing checkmark or crossed-swords icon
  - Host gets a crown icon
- **Config panel:**
  - Styled as a "battle orders" document
  - Map selector → styled dropdown with map preview name in Cinzel
  - Mode buttons → toggle group with ornate active state
- **Chat window:**
  - Header: "War Room Communications" with `.grim-header`
  - Messages area: recessed dark panel with scrollbar
  - Input: styled with ornate borders, send button with icon
- **Action buttons:**
  - "Ready" → large green banner button centered below
  - "Leave" → smaller crimson button in corner
  - "Start Match" (host) → massive ember-glow CTA

#### Chunk 5 — Implementation Log (March 1, 2026)

**Status: COMPLETE** — Waiting Room transformed into War Room / Staging Ground with two-column layout, zero functionality regressions, Vite build passes.

**Files modified:**
| File | Change |
|------|--------|
| `client/src/components/WaitingRoom/WaitingRoom.jsx` | Major restructure: replaced narrow stacked layout with two-column war room. Added `.war-room` wrapper, `.war-room-header` with title/subtitle/meta, `.war-room-columns` (left: orders+roster, right: chat). Replaced flat player list with unit cards (`.war-unit-card`). Config styled as "Battle Orders" with `.grim-header`. Chat renamed "War Room Communications". All buttons use `.grim-btn` system. Host gets `⚜ Commander` badge and `⚔ Start Match` CTA. |
| `client/src/styles/components/_waiting-room.css` | Complete CSS rewrite (~480 lines). Replaced 640px centered box with full-width 1200px two-column layout. Added war room header, unit card system, styled config controls, chat panel, responsive breakpoints at 900px and 600px. |

**Layout change:**
```
BEFORE:                             AFTER:
┌────────────────────────┐         ┌───────────────────────────────────┐
│ Lobby                  │         │ WAR ROOM           Match: xyz    │
│ Match ID: xyz  HOST    │         │ Staging Ground     ⚜ Commander   │
│ ┌────────────────────┐ │         ├──────────────────┬────────────────┤
│ │ Match Settings     │ │         │ BATTLE ORDERS    │ WAR ROOM       │
│ │ Map: xxx           │ │         │ Map: xxx         │ COMMUNICATIONS │
│ │ Mode: [PvP][PvE]   │ │         │ Mode: [toggle]   │                │
│ └────────────────────┘ │         │ AI: ▬▬▬▬         │ [chat msgs]    │
│ ┌────────────────────┐ │  →      │ ⬥────────────⬥  │                │
│ │ Players & Units    │ │         │ DEPLOYED UNITS   │                │
│ │ Player1 TeamA ✓    │ │         │ 👑 Player1 A ⚔  │                │
│ │ 🤖 Bot1  TeamB ✓   │ │         │ ⚔ Player2 B ○  │                │
│ └────────────────────┘ │         │ 🤖 Bot1   B ⚔   │                │
│ ┌────────────────────┐ │         │                  │ [Issue orders] │
│ │ Chat               │ │         ├──────────────────┴────────────────┤
│ │ [messages]         │ │         │ [⚔ Start Match]        [Retreat] │
│ └────────────────────┘ │         └───────────────────────────────────┘
│ [Ready Up] [Leave]     │
└────────────────────────┘
```

**New CSS classes:**
- `.war-room` — Full-width container, `max-width: 1200px`
- `.war-room-header` — Flex row header with title block + meta info, ornamental ember gradient underline
- `.war-room-title` — Cinzel 1.5rem title with ember text-shadow glow
- `.war-room-subtitle` — Crimson Text italic "Staging Ground" subtitle
- `.war-room-host-badge` — `⚜ Commander` gradient badge (replaces `.host-badge`)
- `.war-room-headcount` — Monospace unit count display
- `.war-room-procedural-banner` — Procedural dungeon info strip with ember left border
- `.war-room-columns` — Row flex container for two-column layout
- `.war-room-left` — Flex-grow left panel (orders + class selection + roster), `.grim-frame` styled, scrollable
- `.war-room-right` — Fixed 320px right panel (chat), `.grim-frame` styled
- `.war-room-orders` — Battle Orders section with styled config rows
- `.war-room-select` — Themed select dropdowns (Cinzel font, inset shadow, ember focus glow)
- `.war-room-mode-btns` / `.war-room-mode-btn` — Ornate toggle buttons with hammered-metal bevel, active ember glow
- `.war-room-class-selection` — Class selection wrapper with thin scrollbar
- `.war-room-roster` — Deployed Units section
- `.war-room-unit-list` — Flex column of unit cards
- `.war-unit-card` — Unit card: recessed dark slot with inner border, icon + info + team + status
  - `--you`: ember highlight left border + warm background
  - `--ready`: verdant left border + status glow
  - `--ai`: dimmer opacity treatment
- `.war-unit-icon` — 1.15rem icon column (crown 👑 for host, class shape, or ⚔)
- `.war-unit-info` — Two-line name + class display
- `.war-unit-name` — Cinzel name with ellipsis overflow
- `.war-unit-class` — Italic Crimson Text class name (color-coded)
- `.war-unit-status` — Ready/waiting indicator with green glow text-shadow
- `.war-room-chat-messages` — Recessed dark chat area with inset shadow, thin scrollbar
- `.war-room-chat-placeholder` — Italic flavor text ("The war room is quiet... for now.")
- `.war-room-chat-form` — Flex row: input + grim-btn send button
- `.war-room-chat-input` — Themed input with ember focus glow
- `.war-room-actions` — Full-width action bar below columns
- `.war-room-btn-start` — Host CTA: massive ember glow on hover (25px + 50px shadow)
- `.war-room-btn-ready` — Non-host verdant ready button with active dimming
- `.war-room-btn-leave` — Compact crimson retreat button

**JSX structure:**
```
war-room
  ├── war-room-header
  │   ├── war-room-title-block
  │   │   ├── h2.war-room-title — "War Room"
  │   │   └── p.war-room-subtitle — "Staging Ground"
  │   └── war-room-meta
  │       ├── span.war-room-match-id — "Match: {id}"
  │       ├── span.war-room-host-badge — "⚜ Commander" (host only)
  │       └── span.war-room-headcount — "2 humans, 1 AI — 3 total"
  ├── war-room-procedural-banner (conditional)
  ├── lobby-error-banner (conditional)
  ├── war-room-columns
  │   ├── war-room-left.grim-frame
  │   │   ├── war-room-orders
  │   │   │   ├── h3.grim-header.grim-header--left.grim-header--sm — "Battle Orders"
  │   │   │   └── config-grid
  │   │   │       ├── config-row — Map (war-room-select)
  │   │   │       ├── config-row — Mode (war-room-mode-btns)
  │   │   │       ├── config-row — AI Opponents (range slider)
  │   │   │       ├── config-row — AI Allies (range slider)
  │   │   │       └── config-row — Dungeon Theme (war-room-select)
  │   │   ├── grim-separator--subtle — ⬥
  │   │   ├── war-room-class-selection (conditional)
  │   │   │   ├── h3.grim-header.grim-header--left.grim-header--sm — "Choose Your Class"
  │   │   │   └── class-cards (reused from _lobby.css)
  │   │   ├── grim-separator--subtle — ⬥ (conditional)
  │   │   └── war-room-roster
  │   │       ├── h3.grim-header.grim-header--left.grim-header--sm — "Deployed Units"
  │   │       └── war-room-unit-list
  │   │           └── war-unit-card (per player/AI)
  │   │               ├── span.war-unit-icon — 👑/■/▲/◆/★/●/⚔/🤖
  │   │               ├── div.war-unit-info
  │   │               │   ├── span.war-unit-name
  │   │               │   └── span.war-unit-class (color-coded)
  │   │               ├── span.war-unit-team — team-select or team-badge
  │   │               └── span.war-unit-status — "⚔ Ready" / "○ Waiting"
  │   └── war-room-right.grim-frame
  │       ├── h3.grim-header.grim-header--left.grim-header--sm — "War Room Communications"
  │       ├── war-room-chat-messages (recessed)
  │       │   └── chat-msg (reused from _lobby.css)
  │       └── war-room-chat-form
  │           ├── war-room-chat-input
  │           └── grim-btn.grim-btn--sm.grim-btn--ember — "Send"
  └── war-room-actions
      ├── grim-btn--lg.grim-btn--ember.war-room-btn-start (host) OR
      │   grim-btn--lg.grim-btn--verdant.war-room-btn-ready (non-host)
      └── grim-btn--sm.grim-btn--crimson.war-room-btn-leave — "Retreat"
```

**Responsive behavior:**
- **≤900px:** Columns flip from row to column; left panel loses max-height; right panel (chat) goes full-width with 200px max-height
- **≤600px:** Header stacks vertically; config rows stack (label above control); mode buttons full-width; action buttons stack vertically; unit cards wrap

**What changed visually:**
- Waiting room is now "War Room" — a full-width two-column staging ground (was a narrow 640px centered form)
- Header is a dramatic Cinzel title ("War Room") with ember glow + italic subtitle ("Staging Ground")
- Host gets an ember gradient `⚜ Commander` badge (was simple "HOST" tag)
- Config panel is now "Battle Orders" with `.grim-header` section title and styled selects/mode toggles
- Mode buttons have hammered-metal bevel treatment with ember glow active state
- Select dropdowns use Cinzel font with inset shadow and ember focus glow
- Player list redesigned as "Deployed Units" — unit cards with icon, name, class, team badge, status
- Host player shows 👑 crown icon; class-selected players show their class shape icon
- Ready state has verdant left border + ⚔ icon; "you" card has ember highlight
- AI units dimmed with 🤖 icon and Ally/Opponent label
- Chat is now "War Room Communications" in a dedicated right-column `.grim-frame` panel
- Chat area is a recessed dark panel with inset shadow and thin styled scrollbar
- Chat placeholder reads "The war room is quiet... for now."
- Send button uses `.grim-btn--ember` system
- Host sees massive `⚔ Start Match` ember CTA button (25px + 50px glow on hover)
- Non-host sees `⚔ Ready Up` verdant button
- Leave is now "Retreat" — small crimson button in the corner
- All panels use `.grim-frame` for ornate double-border with corner accents
- Decorative `⬥` separators divide sections in the left panel

**What was preserved:**
- All existing functionality — ready, leave, team select, class select, config changes, chat, hero_select
- All event handlers, state management, API calls identical
- Class selection cards render identically (reusing `class-card` CSS from `_lobby.css`)
- Chat message rendering reuses `chat-msg`, `chat-sender`, `chat-text` from `_lobby.css`
- Error banner reuses `lobby-error-banner` from `_lobby.css`
- Team badge styles reused (scoped via `.war-room .team-badge`)
- Procedural dungeon badge preserved
- wsReady dependency, hero auto-select, ready state reset all preserved

**Verification:**
- Vite production build: ✓ (145.69 KB CSS, 0 errors)
- No lint errors or warnings
- Zero functionality changes — all form submits, fetch calls, dispatches identical
- All shared styles from `_lobby.css` (chat messages, class cards, error banner) work without modification
- Responsive breakpoints at 900px and 600px properly reorganize layout

---

### Chunk 6: Post-Match Screen Enhancement  
**Files:** `PostMatchScreen.jsx` (minor additions), `_post-match.css`
**Scope:** CSS enhancements + minor JSX for decorative elements

The post-match screen already has good thematic styling (outcome-based colors, stats). Enhance it:

- **Victory/defeat banner** — larger, more dramatic with animated glow
- **Hero outcomes** framed in ornate cards (survived = ember glow, fallen = crimson + desaturated)
- **Stats table** → styled as a combat ledger with ornamental column headers
- **"Return to Town" button** — large, prominent, centered, with ember glow
- **Decorative separators** between sections
- **Loot summary** panel framed like a treasure chest inventory

#### Chunk 6 — Implementation Log (March 1, 2026)

**Status: COMPLETE** — Post-match screen enhanced with dramatic banners, ornate hero cards, combat ledger stats, treasure-chest loot panel, grim-frame system, and grim-btn action buttons. Zero functionality regressions, Vite build passes.

**Files modified:**
| File | Change |
|------|--------|
| `client/src/components/PostMatch/PostMatchScreen.jsx` | Added animated `.post-match-banner-line` element in header, `hasLootSummary` memo, "Combat Ledger" `.grim-header` above roster, "Spoils of War" loot summary panel with totals (gold/kills/bosses/damage/healing), `.grim-separator` dividers between all sections (ember ◆, subtle ⬥, crimson ☠), action buttons switched to `.grim-btn` system (`--lg --ember` for Return to Town, `--sm --steel` for Leave), permadeath section wrapped in Fragment with crimson separator |
| `client/src/styles/screens/_post-match.css` | Complete CSS rewrite (~600+ lines). Replaced flat bordered panels with grim-frame ornate system throughout. Added banner pulse animations, treasure chest loot panel, combat ledger stat block, responsive breakpoint at 700px |

**Victory/Defeat Banner — what changed:**
- `.post-match-header` now uses full grim-frame treatment: double-border (`::before` inner border), corner accents (`::after` gradient lines), layered depth shadow
- New `.post-match-banner-line` element: 3px animated gradient line at top of banner with `@keyframes` glow pulse
- Three pulse animations: `banner-pulse-ember` (victory/cleared), `banner-pulse-crimson` (defeat/wipe), `banner-pulse-steel` (escaped)
- Each outcome type gets its own corner accent color (16px corners) and outer glow shadow
- Title enlarged to `clamp(1.4rem, 3vw, 1.8rem)` with stronger layered text-shadow (20px + 40px spread)
- Subtext upgraded to `--font-flavor` (Crimson Text) at 1rem
- Meta stats now styled as mono badges with dark background + dark border

**Hero Outcome Cards — what changed:**
- `.roster-card` now has full grim-frame treatment: double-border, 4 corner accents, inner gradient, layered depth shadow
- Survived cards: verdant left accent border + subtle verdant glow shadow
- Fallen cards: crimson left accent border + crimson glow shadow + `filter: saturate(0.7)` desaturation
- "You" card (`.roster-self`): bright ember corner accents (14px), amplified ember glow (25px)
- `.roster-name` enlarged to 1.05rem with `--text-bright` color + text-shadow
- `.status-survived` / `.status-fallen` now have colored text-shadow glow

**Combat Ledger Stats — what changed:**
- `.roster-card-stats` now has recessed stat-block treatment: dark background, inset box-shadow, border
- `.stat-row` gets dotted leader lines (via `::after` pseudo-element `border-bottom: dotted`)
- `.stat-label` and `.stat-value` have background patches to sit above the dotted leaders (z-index layering)
- `.stat-value` now uses `--font-mono` (Fira Code) for tabular alignment
- Boss/heal/gold stat values get colored text-shadow glow effects

**Loot Summary (NEW) — "Spoils of War" panel:**
- New `.post-match-loot-section` with `.grim-header--sm` section title
- `.post-match-loot-panel` styled as treasure chest: recessed dark background (`--bg-deep`), inner shadow, ember gradient top, full grim-frame corners in ember-dim
- `.loot-totals` flex row with icon + label + value items:
  - 🪙 Gold (ember-bright with text-shadow)
  - ⚔ Enemies Slain (crimson-bright)
  - 💀 Bosses Felled (crimson-bright, conditional)
  - 🗡 Total Damage (text-primary)
  - ✦ Total Healing (verdant, conditional)
- Values use `--font-mono` with `tabular-nums`

**Permadeath Section — what changed:**
- Now uses full grim-frame treatment: double-border, crimson corner accents (14px), crimson glow shadow
- Inner gradient with subtle crimson tint at top
- `.permadeath-header` gets text-shadow glow + bottom border separator
- `.permadeath-card` gets crimson left border accent (3px) + inset shadow (dark recessed slots)
- `.lost-item` loses border-radius, gets left-border rarity accent
- `.rarity-rare` styling added (blue-steel)
- `.permadeath-lost-items` gets top border separator

**Action Buttons — what changed:**
- "Return to Town" now uses `.grim-btn--lg.grim-btn--ember` (hammered-metal bevel, ember hover glow pulse)
- "Leave" now uses `.grim-btn--sm.grim-btn--steel` (neutral, compact)
- Legacy `.btn-back-town` / `.btn-leave-post` styles preserved in CSS for backward compatibility

**Decorative Separators added:**
- `grim-separator--ember ◆` between header banner and hero roster
- `grim-separator--subtle ⬥` between hero roster and loot summary
- `grim-separator--crimson ☠` before permadeath section
- `grim-separator--subtle ⬥` above action buttons
- `.grim-header--sm` "Combat Ledger" above hero roster cards
- `.grim-header--sm` "Spoils of War" above loot summary panel

**JSX structure:**
```
post-match-screen
  ├── post-match-header.outcome-{type}
  │   ├── div.post-match-banner-line (animated glow)
  │   ├── h2.post-match-title — outcome message
  │   ├── p.post-match-subtext — flavor text
  │   └── post-match-meta
  │       ├── span.meta-turns — "Turn X"
  │       ├── span.meta-stat — "X enemies slain"
  │       └── span.meta-stat — "Xg earned"
  ├── grim-separator--ember — ◆
  ├── post-match-roster-section
  │   ├── h3.grim-header.grim-header--sm — "Combat Ledger"
  │   └── post-match-roster (grid)
  │       └── roster-card (per hero)
  │           ├── roster-card-header
  │           │   ├── HeroSprite (48px, grayscale if dead)
  │           │   └── roster-card-identity
  │           │       ├── span.roster-name
  │           │       ├── span.roster-class
  │           │       └── span.roster-status
  │           └── roster-card-stats (recessed ledger)
  │               └── stat-row (×N, dotted leaders)
  ├── post-match-loot-section (conditional)
  │   ├── grim-separator--subtle — ⬥
  │   ├── h3.grim-header.grim-header--sm — "Spoils of War"
  │   └── post-match-loot-panel (treasure-chest frame)
  │       └── loot-totals (flex row)
  │           └── loot-total-item (×N: gold, kills, bosses, damage, healing)
  ├── grim-separator--crimson — ☠ (conditional, before permadeath)
  ├── permadeath-section (conditional, grim-frame + crimson corners)
  │   ├── h3.permadeath-header — "Fallen Heroes — Lost Forever"
  │   └── permadeath-card (per death)
  │       ├── permadeath-name (HeroSprite + info)
  │       └── permadeath-lost-items (conditional)
  ├── grim-separator--subtle — ⬥
  └── post-match-actions
      ├── button.grim-btn--lg.grim-btn--ember — "Return to Town"
      └── button.grim-btn--sm.grim-btn--steel — "Leave"
```

**Responsive behavior (≤700px):**
- Screen padding reduced, header padding tightened
- Title shrinks via `clamp()` to 1.2rem minimum
- Hero roster grid collapses to single column
- Meta stats and loot totals wrap with tighter gaps
- Action buttons stack vertically

**What was preserved:**
- All existing functionality — zero logic changes, all event handlers, state management, memos identical
- `onBackToTown` and `onLeave` callbacks preserved on action buttons
- Hero roster filtering, sorting, outcome calculation all identical
- Permadeath rendering (heroDeaths, lost items) all identical
- HeroSprite component usage unchanged
- Legacy `.btn-back-town` / `.btn-leave-post` CSS preserved for backward compatibility

**Verification:**
- Vite production build: ✓ (160.24 KB CSS, 0 errors)
- No lint errors or warnings
- Zero functionality changes — all memos, dispatches, callbacks identical
- All outcome types render correctly (6 variants)
- Responsive breakpoint at 700px properly reorganizes layout

---

### Chunk 7: Input & Form Element Theming
**Files:** `_variables.css`, `_reset.css`, potentially new `_forms.css`
**Scope:** Pure CSS

Theme all remaining form elements to match the game aesthetic:

**Text inputs:**
- Recessed dark background with inner shadow  
- Ornate left/right border accents on focus  
- Cursor color set to ember
- Placeholder text in dim italic Crimson Text

**Select dropdowns:**
- Custom styled (or at minimum themed with `appearance: none`)
- Dark background, ember highlight for selected option
- Border treatment matching `.grim-frame`

**Range sliders:**
- Custom track (dark recessed bar)
- Custom thumb (ember-colored, circular, with glow)

**Checkboxes / Toggles (if any):**
- Custom styled with ember accent

#### Chunk 7 — Implementation Log (March 1, 2026)

**Status: COMPLETE** — All form elements globally themed with grim-dark aesthetic. Zero JSX changes, zero visual regressions, Vite build passes.

**Files modified:**
| File | Change |
|------|--------|
| `client/src/styles/base/_variables.css` | Added 14 new custom properties for form theming: `--input-bg`, `--input-border`, `--input-border-focus`, `--input-text`, `--input-placeholder`, `--input-shadow`, `--input-focus-glow`, `--input-focus-accent`, `--range-track-bg`, `--range-track-border`, `--range-thumb-bg`, `--range-thumb-glow`, `--checkbox-bg`, `--checkbox-border`, `--checkbox-checked-bg` |
| `client/src/styles/base/_reset.css` | Added form element resets: `font: inherit` + `color: inherit` on input/select/textarea, removed search decoration (Webkit), removed number spinners (Webkit + Firefox) |
| `client/src/styles/base/_forms.css` | **NEW** — ~310-line form element theming system with global styles for text inputs, selects, ranges, checkboxes, labels, fieldsets, plus `.grim-input` / `.grim-select` opt-in utility classes |
| `client/src/styles/main.css` | Added `@import './base/_forms.css'` after `_frames.css` |

**Text Inputs — what changed globally:**
- All text-type inputs (`text`, `email`, `password`, `search`, `url`, `number`, untyped, `textarea`) get:
  - Recessed dark background (`--input-bg` = `--bg-deep`) with inner shadow (`--input-shadow`)
  - `caret-color: var(--accent-ember)` — ember-colored cursor
  - Consistent `2px` border-radius, `0.55rem 0.75rem` padding, `0.9rem` font size
  - Smooth `0.2s` transitions on border-color and box-shadow
- **Placeholder**: dim italic Crimson Text (`--font-flavor`) via `font-style: italic; font-family: var(--font-flavor)`
- **Focus**: ornate left/right ember border accents (`border-left-color` / `border-right-color` = `--accent-ember`), top/bottom border dims to `--accent-ember-dim`, ember glow shadow + inner ring
- **Disabled**: `opacity: 0.45`, `grayscale(30%)`, `cursor: not-allowed`
- **Textarea**: `resize: vertical`, `min-height: 4rem`, `line-height: 1.5`

**Select Dropdowns — what changed globally:**
- All `<select>` elements get:
  - `appearance: none` (removes native browser styling)
  - Custom SVG dropdown arrow in ember color (chevron, 12×8px), positioned at `right 0.6rem center`
  - Cinzel heading font with `0.03em` letter-spacing
  - Recessed dark background with inner shadow (matches text inputs)
  - Right padding (`2rem`) accommodates the custom arrow
- **Focus**: ember glow shadow + arrow color brightens from `--accent-ember-dim` to `--accent-ember`
- **Hover**: border color shifts to `--accent-ember-dim`
- **Options**: dark panel background, primary text color; `:checked` gets ember gradient background + bright text (Chromium)
- **Disabled**: `opacity: 0.45`, `grayscale(30%)`, `cursor: not-allowed`

**Range Sliders — what changed globally:**
- All `<input type="range">` elements get full custom styling (replaces browser defaults):
- **Track** (Webkit + Firefox):
  - 6px height, recessed dark bar (`--range-track-bg`)
  - 1px border (`--range-track-border`), 3px border-radius
  - `inset box-shadow` for depth
- **Thumb** (Webkit + Firefox):
  - 16px circular thumb with radial gradient (ember-bright → ember → ember-dim)
  - 2px ember-dim border, 8px ember glow shadow
  - **Hover**: glow intensifies (14px), `scale(1.1)` size increase
  - **Active/dragging**: brighter gradient, 18px glow, `scale(1.15)` for satisfying feedback
- **Focus-visible**: 2px ember outline with 2px offset (keyboard accessibility)
- **Disabled**: muted gray thumb, no glow, `opacity: 0.4`

**Checkboxes — what changed globally:**
- All `<input type="checkbox">` elements get full custom styling:
  - 18×18px dark recessed box with `inset box-shadow`
  - `appearance: none` removes native checkbox
  - **Checkmark**: `::after` pseudo-element rotated 45° border trick (hidden by default)
  - **Checked**: ember background + ember border + checkmark appears (dark color against ember bg) + outer glow shadow
  - **Hover**: ember-dim border + subtle outer glow
  - **Focus-visible**: 2px ember outline for accessibility
  - **Disabled**: `opacity: 0.4`, `cursor: not-allowed`

**Opt-in utility classes:**
- `.grim-input` — Enhanced text input with larger padding, double-border inner line effect (like `.grim-frame`), stronger focus glow
- `.grim-select` — Enhanced select with larger padding, double-border inner line, stronger focus glow

**Reset additions (`_reset.css`):**
- `input, select, textarea` — `font: inherit; color: inherit; line-height: normal` (ensures form elements inherit app fonts)
- `input[type="search"]` — Removed Webkit search decoration and cancel button
- `input[type="number"]` — Removed Webkit spinner buttons and Firefox spinners (`appearance: textfield`)

**Fieldset & Legend styling:**
- `fieldset` — Subtle border, 2px radius, dark background overlay
- `legend` — Cinzel uppercase, ember-dim color, 0.08em letter-spacing

**What was preserved:**
- All existing component-specific input styles preserved — `.lobby-landing .username-form input`, `.war-room-chat-input`, `.war-room-select`, `.team-select`, `.chat-input`, `.combat-meter-select` all override global base styles via higher CSS specificity
- All existing functionality — zero JSX changes
- All event handlers, form submits, dispatches identical
- Range slider `accent-color` overrides in component CSS still work (now superseded by full custom styling)

**Specificity note:**
Global form styles use element selectors (`input[type="text"]`, `select`, etc.) which have lower specificity than existing component class selectors (`.war-room-select`, `.lobby-landing .username-form input`). This ensures zero visual regressions in already-styled components while providing consistent theming for any unstyled or future form elements.

**Verification:**
- Vite production build: ✓ (168.86 KB CSS, 0 errors)
- No lint errors or warnings
- Zero JSX changes — pure CSS enhancement
- All existing component form styles preserved via specificity
- All interactive functionality identical

---

### Chunk 8: Polish, Animation & Ambient Details
**Files:** Various CSS files, potentially `App.jsx` for ambient wrapper
**Scope:** CSS animations + minor JSX

Final polish pass:

**Micro-animations:**
- Screen transitions: subtle fade-in when switching between lobby → town → waiting room
- Panel hover: slight border-color brighten (already exists in some places — standardize)
- Button press: satisfying downward push + inset shadow
- Glow pulse on important CTA buttons (slow, subtle `@keyframes`)
- Gold counter: brief flash animation when gold value changes
- New match appearing in list: fade-in slide-down

**Ambient details:**
- Login screen: subtle ember particle effect floating upward (reuse existing `ParticleEngine` if feasible, or CSS-only floating dots)
- Town hub sidebar: very subtle animated torch-flicker glow at top (CSS `@keyframes` on a pseudo-element's `box-shadow`)
- Low-opacity noise/grain texture overlay on panels (CSS `background-image` with tiny repeated SVG data URI)

**Screen transition framework:**
- Add a `.screen-enter` / `.screen-exit` CSS class system
- Fade + slight vertical shift (opacity 0→1, translateY 8px→0) over 200ms

#### Chunk 8 — Implementation Log (March 1, 2026)

**Status: COMPLETE** — Polish, animation & ambient details applied across all pre-game screens. Zero functionality regressions, Vite build passes.

**Files modified:**
| File | Change |
|------|--------|
| `client/src/styles/base/_animations.css` | **NEW** — ~370-line animation system: screen transitions, panel hover standardisation, CTA glow pulses (ember/verdant/crimson), gold flash animation, match list stagger entrance, ember particle float (login), torch flicker (town sidebar), noise/grain texture (panels), nav item slide-in, war room unit card entrance, post-match roster card reveal, hero card hover lift, `prefers-reduced-motion` accessibility fallback |
| `client/src/styles/main.css` | Added `@import './base/_animations.css'` after `_forms.css` |
| `client/src/styles/town/_town-hub.css` | Added `position: relative` to `.town-sidebar-header` (required for torch flicker pseudo-element positioning) |
| `client/src/App.jsx` | Added `useRef` import. Wrapped `setScreen` in a callback that increments `screenKeyRef` counter. Wrapped each non-arena screen in `<div key={…} className="screen-enter">` for fade-in transition on mount |
| `client/src/components/TownHub/TownHub.jsx` | Added `useRef` import. Added gold flash detection via `prevGoldRef` + `useEffect` that toggles `.gold-flash` class on gold value change. Added `.grim-btn-pulse--verdant` to Enter Dungeon button. Added `.grim-btn-pulse--crimson` to Enter Arena button |
| `client/src/components/WaitingRoom/WaitingRoom.jsx` | Added `.grim-btn-pulse` to Start Match button. Added `.grim-btn-pulse--verdant` to Ready Up button |
| `client/src/components/PostMatch/PostMatchScreen.jsx` | Added `.grim-btn-pulse` to Return to Town button |

**New CSS file: `_animations.css` — what it contains:**

**1. Screen Transition Framework (`.screen-enter` / `.screen-exit`):**
- `screen-fade-in`: opacity 0→1, translateY 8px→0 over 250ms ease-out
- `screen-fade-out`: opacity 1→0, translateY 0→-6px over 200ms ease-in
- Applied via `<div className="screen-enter">` wrappers in App.jsx for lobby, town, waiting, postmatch screens
- Arena excluded (no transition — immediate fullscreen switch)

**2. Panel Hover Standardisation (`.grim-frame`):**
- Added `transition: border-color 0.25s, box-shadow 0.3s` to all `.grim-frame` elements
- `.grim-frame--interactive:hover` — stronger border-color + ember glow for interactive panels

**3. CTA Glow Pulse (`.grim-btn-pulse` / `--verdant` / `--crimson`):**
- Slow 3-second `ease-in-out infinite` pulse cycle
- Ember variant: 12px→20px+40px ember glow
- Verdant variant: 12px→20px+40px verdant glow
- Crimson variant: 12px→20px+40px crimson glow
- Applied to: Enter Dungeon, Enter Arena, Start Match, Ready Up, Return to Town

**4. Gold Counter Flash (`.gold-flash`):**
- 0.6s `ease-out` animation triggered by JS when gold value changes
- Flash: scale 1.15→1.05→1, bright text + 14px ember glow → normal
- JS implementation: `prevGoldRef` tracks previous value, `useEffect` toggles class for 650ms
- Applies to `.gold-display` element in TownHub sidebar

**5. Match List Stagger Entrance:**
- `.town-match-item` gets `match-slide-in` animation: opacity 0→1, translateY -8px→0 over 350ms
- Staggered via `animation-delay`: child 1=0s, child 2=40ms, ..., child 7+=240ms

**6. Ambient — Login Ember Particles (`.lobby-landing::after`):**
- CSS-only floating dots using multiple `radial-gradient` backgrounds (12 ember dots)
- Background sizes from 4px to 8px at varied positions across viewport
- Animated via `ember-float` keyframes: translateY 0 → -100vh over 12s linear infinite
- Results in slow-rising ember particle effect behind login screen

**7. Ambient — Town Sidebar Torch Flicker:**
- `.town-sidebar-header::before` — 3px wide radial gradient "ember line" above header
- `.town-sidebar-header::after` — 20px tall radial gradient "halo" below header
- Both animated with `torch-flicker` keyframes: irregular opacity/scaleX fluctuation (0.5→0.9) over 4s
- Staggered by 1.5s delay between line and halo for organic feel
- Required `position: relative` added to `.town-sidebar-header` in `_town-hub.css`

**8. Ambient — Noise/Grain Texture (`.grim-frame::before`):**
- Layered onto existing inner-border pseudo-element via `background-image`
- Tiny 4×4px SVG data-URI with 3 semi-transparent white pixels at different positions
- Creates subtle film-grain texture on all panels at near-invisible opacity (0.6%–1.2%)

**9. Nav Item Slide-In (`.town-nav-item`):**
- `nav-item-slide-in`: opacity 0→1, translateX -12px→0 over 300ms
- Staggered: child 1=50ms, child 2=100ms, ..., child 5=250ms
- Plays once on sidebar mount (town hub load)

**10. War Room Unit Cards (`.war-unit-card`):**
- `unit-card-enter`: opacity 0→1, translateY 6px→0 over 300ms
- Staggered: child 1=0ms, child 2=60ms, ..., child 6+=300ms

**11. Post-Match Roster Cards (`.post-match-roster .roster-card`):**
- `roster-card-reveal`: opacity 0→1, translateY 12px→0, scale 0.97→1 over 400ms
- Staggered: child 1=100ms, child 2=200ms, ..., child 4=400ms

**12. Hero Card Hover Lift:**
- `.roster-hero-card` / `.tavern-hero-card` — `transition: transform 0.2s, box-shadow 0.3s, border-color 0.25s`
- Hover: `translateY(-2px)` lift effect

**13. Reduced Motion Accessibility (`prefers-reduced-motion: reduce`):**
- Disables all non-essential animations: screen transitions, ember particles, torch flicker, CTA pulses, gold flash, stagger entrances, hover lifts
- Ember particles reduced to static `opacity: 0.3`

**App.jsx screen transition mechanism:**
- `setScreenRaw` + `screenKeyRef` pattern: every `setScreen()` call increments a counter
- Each screen wrapper uses `key={screenName-${counter}}` which forces React re-mount
- Re-mount triggers the `.screen-enter` CSS animation (fade-in + slide-up)
- Arena screen excluded from transition wrapper (needs immediate fullscreen switch)

**What was preserved:**
- All existing functionality — zero logic changes in any component
- All existing event handlers, state management, API calls, dispatches identical
- All existing CSS animations preserved (title-glow, banner-pulse-*, fadeIn, slideUp, etc.)
- All existing button styles and grim-btn system fully preserved
- All responsive breakpoints preserved
- Arena screen has no transition wrapper (intentional — combat should feel instant)

**Performance notes:**
- All animations use only `transform` and `opacity` (GPU-composited properties)
- Ember particles are pure CSS — no JS, no canvas, no requestAnimationFrame
- Noise texture is a 4×4px SVG — minimal memory impact
- CTA pulses use `box-shadow` (composited) not `filter` or `background`
- Stagger delays are small (40–100ms) to avoid perceived lag
- `prefers-reduced-motion` respects accessibility preferences

**Verification:**
- Vite production build: ✓ (175.77 KB CSS, 0 errors, 0 warnings)
- No lint errors or warnings
- Zero functionality changes — all form submits, fetch calls, dispatches identical
- All existing animations coexist without conflicts
- Responsive behavior preserved at all breakpoints

---

## Implementation Order & Dependencies

```
Chunk 1: Frame System ─────────────────┐
    (CSS utilities, zero breakage)      │
                                        ▼
Chunk 2: Login Screen ──────── Chunk 7: Form Theming
    (uses frame system)            (uses frame system)
                                        │
Chunk 3: Town Hub Navigation ◄──────────┘
    (biggest layout change)
         │
         ▼
Chunk 4: Panel & Card Styling
    (applies frames to all content panels)
         │
         ▼
Chunk 5: Waiting Room Overhaul
    (uses frame system + panel patterns from Chunk 4)
         │
         ▼
Chunk 6: Post-Match Enhancement
    (uses frame system + card patterns)
         │
         ▼
Chunk 8: Polish & Animation
    (final pass across everything)
```

**Recommended order:** 1 → 2 → 7 → 3 → 4 → 5 → 6 → 8

Chunks 2 and 7 can be done in parallel after Chunk 1.  
Chunks 4, 5, 6 can be done in any order after Chunk 3.

---

## Files Touched Per Chunk

| Chunk | CSS Files | JSX Files | New Files |
|-------|-----------|-----------|-----------|
| 1 | `_variables.css`, `_buttons.css` | — | `_frames.css` |
| 2 | `_lobby.css` | `Lobby.jsx` (minor) | — |
| 3 | `_town-hub.css` | `TownHub.jsx` | — |
| 4 | `_hero-roster.css`, `_hiring-hall.css`, `_merchant.css`, `_bank.css`, `_town-hub.css` | — | — |
| 5 | `_waiting-room.css`, `_lobby.css` | `WaitingRoom.jsx` (minor) | — |
| 6 | `_post-match.css` | `PostMatchScreen.jsx` (minor) | — |
| 7 | `_reset.css`, `_variables.css` | — | `_forms.css` |
| 8 | Various | `App.jsx` (minor) | `_animations.css` |

**New CSS partials to add to `main.css`:**
- `base/_frames.css`
- `base/_forms.css`  
- `base/_animations.css`

---

## What This Does NOT Change

- **No backend changes** — this is 100% client-side
- **No functionality changes** — every button, form, and interaction works identically
- **No component restructuring** beyond TownHub layout (Chunk 3) and minor decorative JSX additions
- **No font changes** — we keep Cinzel, Crimson Text, Inter, Fira Code
- **No color palette changes** — ember, crimson, sickly-green, blue-steel all stay
- **No in-game UI changes** — Arena, HUD, combat panels, inventory are untouched (separate effort)

---

## Visual Reference Points

The aesthetic we're targeting sits between:

- **Darkest Dungeon** — ornate frames, parchment textures, heavy use of decorative borders, sidebar navigation, atmospheric darkness
- **Diablo II Resurrected** — dark stone/metal frames, character-centric layout, stat blocks, dramatic lighting
- **Path of Exile** — dense but organized panels, ornate header treatments, metal-frame UI elements
- **Slay the Spire** — clean but clearly "game", framed panels, card-focused layouts

Key visual elements we're borrowing:
1. **Double-line ornate borders** with corner accents (Darkest Dungeon)
2. **Sidebar town navigation** (Darkest Dungeon hamlet / DD2 inn)
3. **Stat-block character sheets** (D&D / roguelike tradition)
4. **Notice board match list** (tavern quest board trope)
5. **War room staging area** (replaces "waiting room")
6. **Dramatic post-match banners** (Slay the Spire victory/defeat)

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Chunk 3 (town layout) is a significant restructure | Keep old tab system as fallback behind a CSS class toggle |
| Custom form styling breaks on some browsers | Use progressive enhancement — base styles work everywhere |
| Performance impact of animations | All animations use `transform`/`opacity` only (GPU-composited) |
| Scope creep into in-game UI | Strict boundary: only pre-game screens in this phase |
| Responsive behavior regression | Test at 1920px, 1440px, 1024px, 768px after each chunk |

---

## Success Criteria

After all 8 chunks:
- [ ] A new player launching the game sees a dramatic title screen, not a web form
- [ ] Navigating the town feels like moving through locations in a game, not clicking tabs on a website
- [ ] Every panel has ornate framing that says "this is a game UI"
- [ ] Buttons feel hefty and satisfying (visual weight, hover glow, press feedback)
- [ ] The waiting room feels like a war room where you prepare for battle
- [ ] Post-match screens feel dramatic and impactful
- [ ] All existing functionality works identically
- [ ] 0 test regressions
