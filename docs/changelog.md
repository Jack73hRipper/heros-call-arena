# Arena — Changelog

All notable changes to this project will be documented in this file.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

---

## [v0.1.7f] - 2026-03-16 - Party HP Panel Centering & Instant Population Fix

### Fixed
- **Party HP panels biased to the left** — `.party-vitals` had `flex: 1` which stretched the container to fill all remaining space in the vitals row, overriding the `justify-content: center` on the parent. Removed `flex: 1` and `overflow-x: auto` so the party vitals container is content-sized and the vitals row correctly centers all HP panels (player + party) over the viewport.
- **Party HP bars missing on first frame** — only the player's own HP panel appeared at match start; party member HP panels didn't populate until after the first tick. The `MATCH_START` handler in `combatReducer` reset `partyMembers` to `[]`, and party data was only sent via the `queue_updated` message after the first turn resolved. Added `party` data to the server's `match_start` payload (`get_match_start_payload_for_player`) and updated the client's `MATCH_START` handler to use `action.payload.party` if present, so all party HP bars render immediately when the match begins.

### Files Changed
- `client/src/styles/components/_player-vitals.css` — removed `flex: 1` and `overflow-x: auto` from `.party-vitals`
- `server/app/core/match_manager.py` — `get_match_start_payload_for_player()` now includes `party` array via `get_party_members()`
- `client/src/context/reducers/combatReducer.js` — `MATCH_START` handler uses `action.payload.party || []` instead of hardcoded `[]`

---

## [v0.1.7e] - 2026-03-16 - Dungeon HUD Layout Overhaul

### Changed
- **Minimap relocated to right panel** — moved from an absolute overlay in the top-right of the game viewport to the right sidebar, positioned above the target bar (HUD). The minimap now fills the full panel width (~270px) as a squared-off panel matching the width of the HUD, Party, and Enemy panels below it. Tile size auto-scales to fill the panel based on map dimensions.
- **Player HP bar relocated above viewport** — the PlayerVitals frame (gradient HP bar with class identity row) moved from an absolute overlay at the bottom-left of the canvas to a dedicated vitals row between the action bar and the game viewport. It now sits outside the viewport area entirely rather than hovering over it.
- **Combat Meter button labeled** — the "⚔" combat meter toggle button in the action bar now displays a "Meter" text label below the icon, making its purpose clearer to players
- **Arena grid layout expanded** — grid changed from 3-row to 4-row layout (`auto auto auto 1fr`) to accommodate the new vitals row; left panel and right panel span rows 3–4 so they remain full-height

### Added
- **PartyVitals component** — new component that displays HP bars for all party members side by side using the same gradient bar style as the player's own PlayerVitals. Each party member gets a class-colored top accent border, class icon + name, player name, and a 20px gradient HP bar with HP text centered inside. Includes the same color-coded HP states (green >50%, amber 25–50%, red ≤25%, grey dead), danger pulse animation at low HP, and dead state desaturation.
- **Vitals row** (`arena-vitals-row`) — new grid row in the arena layout that contains the player's HP bar on the left and party HP bars side by side next to it, all between the action bar and the game canvas

### Files Changed
- `client/src/components/Arena/Arena.jsx` — moved MinimapPanel from canvas overlays to right panel (above HUD); moved PlayerVitals from canvas overlay to vitals row; added PartyVitals import and render
- `client/src/components/PlayerVitals/PartyVitals.jsx` — new component
- `client/src/components/PlayerVitals/PlayerVitals.jsx` — unchanged (styles updated in CSS)
- `client/src/components/MinimapPanel/MinimapPanel.jsx` — updated tile size calculation to fill panel width (~270px)
- `client/src/components/BottomBar/BottomBar.jsx` — added "Meter" label text to combat meter toggle button
- `client/src/styles/layout/_arena.css` — 4-row grid, vitals row styles, updated row spans for left/right/canvas
- `client/src/styles/layout/_minimap.css` — changed from absolute overlay to flow element with aspect-ratio 1/1 and full width
- `client/src/styles/components/_player-vitals.css` — removed absolute positioning; added PartyVitals/party-vital styles
- `client/src/styles/components/_combat-meter.css` — flex-direction column on btn-meter, added meter-label styles

---

## [v0.1.7d] - 2026-03-16 - Inventory Panel Width & Overflow Fix

### Fixed
- **Inventory overlay panel too narrow** — text (item names, buff pills, stat rows, context strip) was overflowing to the right and creating a horizontal scrollbar
  - Widened base panel from 340–440px to 420–560px (`width: max-content` up to max-width)
  - Widened large-screen breakpoint (1201px+) from 360–480px to 440–600px
  - Widened medium breakpoint (769–1200px) from 340–440px to 420–560px
  - Widened small-medium breakpoint (501–768px) from 320px min to 400px min
  - Added `overflow-x: hidden` to prevent horizontal scrollbar
  - Added `max-width: 100%` to equipment slot item names for proper ellipsis truncation
  - Added `overflow: hidden` and `max-width: 100%` to buff list and bag slot item info
  - Added `flex-wrap: wrap` and `overflow: hidden` to dungeon context strip

### Files Changed
- `client/src/styles/components/_inventory.css` — panel width increases, overflow protection

---

## [v0.1.7c] - 2026-03-16 - Player Vitals HP Bar Overhaul

### Added
- **PlayerVitals component** — new dedicated HP frame overlay anchored to the bottom-left of the game canvas, replacing the tiny inline HP bar that was buried in the header
  - **20px tall gradient HP bar** with HP text centered inside (white text with dark shadow for readability)
  - **Class identity row** — class-colored top accent border, class icon + class name + player name
  - **Color-coded HP states** — green gradient (>50%), amber gradient (25–50%), red gradient (<25%), grey (dead)
  - **Low-HP danger pulse** — red glow animation on the frame border when HP ≤ 25%
  - **Dead state** — desaturated and dimmed frame with "💀 DEAD" text
  - **Responsive scaling** — shrinks bar and frame on smaller viewports (<800px height)
- **`_player-vitals.css`** — full stylesheet with gradients, inner shadows, pulse animation, and responsive rules

### Changed
- **HeaderBar** — removed inline HP bar section (label, bar, value) to reduce top-bar clutter; turn/timer/mode/class/buffs remain
- **Arena layout** — PlayerVitals renders as an overlay inside the canvas area (bottom-left corner), near the player's natural focus area beside the action bar

### Removed
- **Header HP CSS** — removed `.header-hp`, `.header-hp-label`, `.header-hp-bar-bg`, `.header-hp-bar-fill`, `.header-hp-value` styles (no longer needed)

### Files Changed
- `client/src/components/PlayerVitals/PlayerVitals.jsx` — new component
- `client/src/styles/components/_player-vitals.css` — new stylesheet
- `client/src/components/HeaderBar/HeaderBar.jsx` — removed HP bar section
- `client/src/styles/components/_header-bar.css` — removed HP styles
- `client/src/components/Arena/Arena.jsx` — import and render PlayerVitals in canvas area
- `client/src/styles/main.css` — added `_player-vitals.css` import

---

## [v0.1.7b] - 2026-03-16 - Missing Particle Effects Pass

### Added
- **Seal of Judgment particles** — gold/holy branded star burst on target with diamond rune extras and a golden projectile trail (Inquisitor)
- **Blink particles** — arcane blue star burst at destination + fading departure trail at origin, visually distinct from Shadow Step's dark-bolt (Mage)
- **Bone Shield particles** — bone-colored triangle fragments orbit the caster on cast + persistent bone-shard aura while active (Skeleton enemy)
- **Dark Pact particles** — purple dark-magic burst on target with diamond-trail link wisps at caster + persistent purple aura while buffed (Dark Priest enemy)
- **Profane Ward particles** — expanding lavender circles on target + persistent lavender aura while damage reduction is active (Acolyte enemy)
- **Enrage particles** — dramatic fire ignition burst (white→gold→red→crimson) when HP drops below 30% + persistent flame aura while enraged (Demon Enrage enemy)
- **Frenzy Aura particles** — orange/red ring pulse on activation + persistent smoldering aura while the imp buff aura is active (Imp Lord enemy)
- **6 new buff auras** — `buff-aura-bone-shield`, `buff-aura-dark-pact`, `buff-aura-profane-ward`, `buff-aura-enrage`, `buff-aura-frenzy` persistent looping effects; `dark_pact` and `profane_ward` buff_id overrides added
- **3 new buff_status types** — `damage_absorb`, `passive_enrage`, `passive_aura_ally_buff` now have persistent aura visuals

### Changed
- **`particle-effects.json`** — added skill mappings for `seal_of_judgment`, `blink`, `bone_shield`, `dark_pact`, `profane_ward`, `enrage`, `frenzy_aura`; added `buff_id_overrides` for `dark_pact` and `profane_ward`; added `buff_status` entries for `damage_absorb`, `passive_enrage`, `passive_aura_ally_buff`

### Files Changed
- `client/public/particle-effects.json` — 7 new skill mappings, 3 new buff_status types, 2 new buff_id overrides
- `client/public/particle-presets/skills.json` — 12 new presets (seal-judgment-brand, seal-judgment-runes, seal-judgment-trail, blink-arrival, blink-departure, bone-shield-cast, dark-pact-cast, dark-pact-link, profane-ward-cast, enrage-ignite, frenzy-aura-pulse)
- `client/public/particle-presets/buffs.json` — 6 new aura presets (buff-aura-bone-shield, buff-aura-dark-pact, buff-aura-profane-ward, buff-aura-enrage, buff-aura-frenzy)

---

## [v0.1.7a] - 2026-03-16 - PVPVE Chest Tier Overhaul

### Added
- **PVPVE location-based chest tiers** — PVPVE mode now uses a centrality-based tier system instead of floor-depth gating. Chests closer to the map center (boss room area) roll higher tiers, creating a risk/reward dynamic where better loot requires venturing into contested territory.
  - **Edge zone** (team spawn corners): ~57% Wooden, ~28% Iron, ~11% Gold, ~3% Obsidian
  - **Mid zone** (midfield rooms): ~31% Wooden, ~37% Iron, ~22% Gold, ~11% Obsidian
  - **Center zone** (boss area): ~11% Wooden, ~25% Iron, ~40% Gold, ~24% Obsidian
- **`pvpve_tier_weights` config** — new section in `chest_tier_config` defines per-zone (edge/mid/center) spawn weights for PVPVE mode, independent of floor-range gating
- **`roll_chest_tier_pvpve()`** — new loot function that accepts a `centrality` value (0.0 = map edge, 1.0 = map center) and selects the appropriate zone weight table

### Fixed
- **PVPVE chests no longer all Wooden** — previously, PVPVE mode was always floor 1, so the floor-range gating meant only Wooden chests (floor 1+) were eligible. Iron (floor 2+), Gold (floor 4+), and Obsidian (floor 7+) could never spawn. The new centrality system bypasses floor gating entirely.

### Changed
- **`_init_dungeon_state()`** — now detects PVPVE match type and computes Euclidean centrality for each chest position relative to the map center. PVPVE chests use `roll_chest_tier_pvpve()` while standard dungeon chests continue using the floor-based `roll_chest_tier()`.

### Files Changed
- `server/configs/loot_tables.json` — added `pvpve_tier_weights` section with edge/mid/center weight tables
- `server/app/core/loot.py` — added `roll_chest_tier_pvpve()` function
- `server/app/core/match_manager.py` — updated `_init_dungeon_state()` with PVPVE centrality logic, added `get_map_dimensions` import

---

## [v0.1.7] - 2026-03-15 - Chest Tier System & Visual Redesign

### Added
- **Chest tier system** — 5 distinct chest tiers replace the single generic chest:
  - **Wooden Chest** (floors 1+, weight 50) — 1-2 common-leaning items
  - **Iron Chest** (floors 2+, weight 30) — 1-3 items, better uncommon drop rates
  - **Gold Chest** (floors 4+, weight 15) — 2-3 items, guaranteed magic+ rarity
  - **Obsidian Chest** (floors 7+, weight 5) — 2-4 items, guaranteed rare+ rarity
  - **Boss Chest** (boss rooms only) — unchanged from previous boss_chest behavior
- **Chest tier config** in `loot_tables.json` — new `chest_tier_config` section defines tier spawn weights, floor ranges, and loot table mappings
- **4 new chest loot tables** — `wooden`, `iron`, `gold`, `obsidian` with progressively better weighted pools
- **Chest tier visual redesign** — all chests now render as detailed barrel-lidded treasure chests with:
  - 3D shading (dark right edge, highlight left edge)
  - Visible lid with overhang and border
  - 2 horizontal metal band straps
  - Center latch/lock with keyhole detail
  - Opened state shows interior cavity, tilted-back lid, and hinge dots
  - Tier-specific glow effects (gold glow for Gold, purple glow for Obsidian, red glow for Boss)
- **Tier-specific color palettes** — each tier has unique body, band, latch, and lid colors
- **Tier-aware minimap** — minimap chest dots now use tier-specific colors instead of a single gold dot
- **Client utility modules**:
  - `chestUtils.js` — chest state parsing, tier config lookup, minimap color helper
  - `chestRenderer.js` — shared detailed chest drawing function used by ThemeEngine and dungeonRenderer

### Changed
- **Chest state format** — `chest_states` values changed from `"unopened"/"opened"` to `"unopened:tier"/"opened:tier"` (e.g. `"unopened:iron"`, `"opened:gold"`). Full backward compatibility with plain `"unopened"`/`"opened"` maintained.
- **`_init_dungeon_state`** — now rolls a chest tier for each chest based on floor number and boss room context using `roll_chest_tier()`
- **`generate_chest_loot`** — now falls back to the `"default"` loot table when an unknown chest type is passed, instead of returning empty
- **`_resolve_loot` (interaction_phase)** — extracts chest tier from state and passes it to `generate_chest_loot` for tier-appropriate drops
- **ThemeEngine** — chest case now delegates to shared `drawChestIcon()` with tier info passed via `extra.chestTier`
- **dungeonRenderer** — flat-color fallback chest replaced with tier-aware `drawChestIcon()`
- **Theme Designer tool** — `tilePatterns.js` `drawChest()` updated with detailed rendering matching the game
- **Pathfinding & keyboard shortcuts** — updated to recognize `"unopened:tier"` format via `startsWith` checks

### Files Changed
- `server/configs/loot_tables.json` — added `chest_tier_config`, 4 new chest loot tables (wooden, iron, gold, obsidian)
- `server/app/core/loot.py` — added `roll_chest_tier()`, updated `generate_chest_loot()` fallback
- `server/app/core/match_manager.py` — `_init_dungeon_state()` now rolls chest tiers
- `server/app/core/turn_phases/interaction_phase.py` — `_resolve_loot()` parses tier from chest state
- `client/src/utils/chestUtils.js` — new (chest tier config, state parsing)
- `client/src/canvas/chestRenderer.js` — new (detailed chest icon drawing)
- `client/src/canvas/dungeonRenderer.js` — updated chest drawing + imports
- `client/src/canvas/ThemeEngine.js` — updated chest drawing to use `drawChestIcon`
- `client/src/canvas/minimapRenderer.js` — tier-aware chest minimap colors
- `client/src/canvas/renderConstants.js` — updated default chest colors
- `client/src/canvas/pathfinding.js` — updated `startsWith` checks for new state format
- `client/src/hooks/useKeyboardShortcuts.js` — updated `startsWith` check for E key chest detection
- `tools/theme-designer/src/engine/tilePatterns.js` — updated `drawChest()` with detailed rendering
- `server/tests/test_dungeon_map.py` — updated assertion for new chest state format
- `server/tests/test_phase16b_affix_system.py` — updated test for fallback behavior

---

## [v0.1.6b] - 2026-03-15 - Hero Permadeath Bug Fix

### Fixed
- **Hero permadeath now applies to all heroes** — AI hero allies (party members) were not triggering permadeath when killed in dungeon runs. Only the human-controlled hero was checked (`unit_type == "human"`), but party allies spawn as `unit_type == "ai"` with a valid `hero_id`. Changed the condition to check for `hero_id` presence regardless of unit type, so all roster heroes are properly marked dead and removed from the active roster on death.

### Files Changed
- `server/app/core/turn_phases/deaths_phase.py` — permadeath condition changed from `unit_type == "human" and hero_id` to just `hero_id`

---

## [v0.1.6a] - 2026-03-15 - Custom Cursor & Game Icon

### Added
- **Custom game cursor** — `MouseFinal.png` resized to 32×32 and applied as the in-game cursor site-wide via CSS (`cursor.png` in `client/public/`). Replaces default browser cursor on all elements including buttons and interactive controls.
- **Game icon** — `icon 1.ico` / `icon 1.png` set as the official app icon:
  - Electron game window icon (`client/public/favicon.ico`)
  - Browser favicon (`<link>` tags in `index.html` for `.ico` and `.png`)
  - Electron builder icon for Windows/Mac/Linux builds
  - Launcher window icon + system tray icon (`launcher/assets/icon.ico`)
  - Launcher electron-builder config updated

### Files Changed
- `client/public/cursor.png` — new (32×32 resized from `Assets/Sprites/MouseFinal.png`)
- `client/public/favicon.ico` — new (from `Assets/Sprites/icon 1.ico`)
- `client/public/favicon.png` — new (from `Assets/Sprites/icon 1.png`)
- `launcher/assets/icon.ico` — new (from `Assets/Sprites/icon 1.ico`)
- `client/src/styles/base/_reset.css` — added custom cursor rules
- `client/index.html` — added favicon `<link>` tags
- `launcher/main.js` — added `icon` property to BrowserWindow
- `launcher/package.json` — added `icon` to electron-builder win config

---

## [v0.1.6] - 2026-03-14 - AI & Team Fixes

**Summary:** Six bug fixes and AI improvements targeting PVPVE team assignment, totem targeting, Confessor AI, and multi-support positioning. Rolls up v0.1.5–v0.1.5f changes into a published release.

### Bug Fixes
- **PVPVE lobby team ignored** — `_assign_pvpve_teams()` no longer force-distributes players round-robin; respects lobby-chosen team (v0.1.5)
- **PVPVE index-based team detection** — `_spawn_pvpve_ai_teams()` now reads actual `player.team` instead of using list index (v0.1.5b)
- **Hero ally hardcoded to Team A** — `_spawn_hero_ally()` now reads owner's team field (v0.1.5b)
- **Ground-placement skills hijacked by auto-target** — Added `isPlacementSkill()` check to bypass auto-select for totem skills (v0.1.5c)
- **Shield of Faith self-cast** — Excluded caster from SoF candidate loop; moved SoF to Priority 4.7 after reposition check (v0.1.5e)
- **Multi-support clumping** — Support roles now exclude other supports from nearest-ally movement fallback (v0.1.5f)

### AI Improvements
- **Confessor tank-aware positioning** — Proactively moves toward tank-role allies when outside heal range (v0.1.5d)
- **Reposition threshold raised 60% → 80%** — Confessor starts closing distance earlier (v0.1.5d)
- **Check B tank drift threshold** — Introduced `_TANK_REPOSITION_THRESHOLD = 5` so Exorcism fires at medium range (v0.1.5e)
- **Support anti-clump anchoring** — `_support_move_preference()` and `_totemic_support_move_preference()` prefer non-support allies as anchors (v0.1.5f)

---

## [v0.1.5f] - 2026-03-14 - Multi-Support Anti-Clumping Fix

### Improvement — `server/app/core/ai_skills.py`

- **Support-role nearest-ally filtering** — `_support_move_preference()` (Confessor) and `_totemic_support_move_preference()` (Shaman) now exclude other support-role allies from their "nearest ally" movement fallback. Previously, when no allies were injured and the tank was within heal range, each support would pick the **nearest ally** as its movement anchor — which was often the other support. This caused Confessor + Shaman (and similar double-support comps) to gravitate toward each other, clump away from the frontline, and oscillate tiles as the batch movement resolver repeatedly blocked their identical move targets. Both functions now prefer non-support allies (tanks, DPS) as movement anchors, only falling back to support allies if no other teammates are alive. Added `_SUPPORT_ROLES` constant (`support`, `offensive_support`, `totemic_support`) for the filter.

---

## [v0.1.5e] - 2026-03-14 - Confessor AI Healing & Targeting Fixes

### Bug Fix — `server/app/core/ai_skills.py`

- **Shield of Faith self-cast bug** — `_support_skill_logic()` SoF candidate loop included the caster itself. Confessor has the lowest base HP (100) so it always had the lowest HP% and self-cast SoF ~56% of the time, wasting the buff on a backline unit. Added `if unit.player_id == ai.player_id: continue` to match the existing Dark Pact self-exclusion pattern. SoF now always targets an ally (typically the tank).

- **SoF priority blocks repositioning** — Shield of Faith was at Priority 4, firing BEFORE the Priority 4.5 reposition check. When the tank drifted out of heal range and needed healing, the Confessor would cast SoF (often on itself) instead of repositioning toward the hurt tank. Moved SoF to Priority 4.7 so the reposition check runs first. If the tank is far and hurt, the Confessor walks toward them instead of buffing.

- **Check B too aggressive** — The v0.1.5d "suppress Exorcism when tank is far" check used `_SUPPORT_HEAL_RANGE` (3 tiles) as its threshold, forcing reposition whenever the tank was >3 tiles away. This caused 64% of turns to be wasted on repositioning. Introduced `_TANK_REPOSITION_THRESHOLD = 5` so Exorcism can fire at medium range (4–5 tiles) while still triggering reposition when the tank is truly far (>5 tiles).

### Tests — `server/tests/test_confessor_diagnostic.py`

- 14 diagnostic tests verifying the three fixes: SoF never self-casts, reposition no longer blocks Exorcism at medium range, and SoF no longer prevents repositioning toward hurt tanks. Includes a 200-turn simulation asserting 0% SoF self-cast rate and <50% reposition rate.

---

## [v0.1.5d] - 2026-03-14 - Confessor AI Positioning Overhaul

### Improvement — `server/app/core/ai_skills.py`

- **Tank-aware support positioning** — `_support_move_preference()` now identifies tank-role allies (Crusader `tank`, Revenant `retaliation_tank`, Blood Knight `sustain_dps`) and proactively moves toward them when the Confessor is outside heal range (3 tiles). Previously the Confessor only moved toward **most injured** or **nearest** ally, causing it to drift behind the party while the tank advanced into combat. New priority order: (1) most injured ally below 60% HP, (2) tank-role ally outside heal range, (3) nearest ally.

- **Raised reposition threshold from 60% → 80%** — The "Priority 4.5" reposition check in `_support_skill_logic()` now uses a dedicated `_REPOSITION_ALLY_THRESHOLD` of 0.80 instead of the heal threshold (0.60). The Confessor will start closing distance toward out-of-range allies much earlier, before they become critical. This prevents the pattern where the Confessor spams Exorcism from range 5 while the tank slowly drops from 70% → 30% HP out of heal range.

- **Suppress Exorcism when tank is drifting out of range** — Added a second reposition check (Check B) that returns `None` when any tank-role ally is beyond heal range (3 tiles), regardless of their HP%. This forces the stance handler to move the Confessor toward the tank instead of casting Exorcism from the back line. Exorcism (range 5) greatly exceeds Heal (range 3), which previously created a positioning trap where the Confessor could DPS comfortably but couldn't heal.

- **New constants** — Added `_REPOSITION_ALLY_THRESHOLD` (0.80), `_TANK_ROLES` set (`{"tank", "retaliation_tank", "sustain_dps"}`), and `_SUPPORT_HEAL_RANGE` (3) for tank-proximity calculations.

---

## [v0.1.5c] - 2026-03-13 - Ground Placement Skill Targeting Fix

### Bug Fix — `client/src/components/BottomBar/BottomBar.jsx`

- **Ground-placement skills (totems) hijacked by auto-target system** — Skills with `targeting: "ground_aoe"` and a `place_totem` effect (Healing Totem, Searing Totem, Earthgrasp Totem) were treated as enemy-targeting skills by the auto-target system. When enemies were in FoV, pressing a totem skill button would auto-select the nearest enemy and initiate pursuit instead of entering tile-selection mode for placement. Fixed by adding an `isPlacementSkill()` check that detects `place_totem` effects and bypasses both the target-first casting path (Phase 10G-6) and the `findNearestTarget()` auto-select. Totem skills now always enter tile-selection mode regardless of nearby enemies. Affects all classes with ground-placement skills.

---

## [v0.1.5b] - 2026-03-13 - PVPVE Team Assignment Fix (Upstream)

### Bug Fix — `server/app/core/match_manager.py`

- **`_spawn_pvpve_ai_teams()` used index-based team detection** — When determining which teams were occupied by humans, the function used player list index (`active_teams[i % team_count]`) instead of each player's actual `player.team` value. With 2 humans both on Team A in a 4-team match, it incorrectly computed `human_teams = {"a", "b"}` instead of `{"a"}`. This meant enemy AI teams would only fill C and D, leaving Team B empty — and the cascading mismatch caused Player 2 to appear on the wrong team. Fixed to read actual `player.team` from lobby selections.

### Bug Fix — `server/app/core/hero_manager.py`

- **`_spawn_hero_ally()` hardcoded `team="a"`** — Hero allies were always spawned with `team="a"` and appended to `match.team_a`, ignoring the owner's actual team. Fixed to read the owner player's `team` field and append to the correct team list. This ensures hero allies follow their owner to whichever team they've selected in the lobby.

### Tests — `server/tests/test_pvpve_ai_teams.py`

- Updated `test_ai_teams_skip_human_occupied_teams` to explicitly place humans on separate teams (A and B) before asserting AI skips those teams.
- Added `test_ai_teams_fill_all_non_human_slots_when_same_team` — verifies that when 2 humans are both on Team A, AI enemy teams correctly fill all remaining slots (B, C, D).

---

## [v0.1.5] - 2026-03-13 - PVPVE Team Assignment Fix

### Bug Fix — `server/app/core/match_manager.py`

- **PVPVE lobby team ignored** — `_assign_pvpve_teams()` was force-distributing human players round-robin across teams, overriding whatever team they chose in the War Room lobby. If two players both picked Team A, Player 2 would be silently moved to Team B at match start and spawn in a different corner alone. Fixed to respect each player's lobby-chosen team when it's a valid active team for the match. Round-robin fallback only applies if a player's team isn't one of the active PVPVE teams (e.g., on Team D in a 2-team match).

---

## [v0.1.4] - 2026-03-13 - Stance System Overhaul, Destroy Item & Audio Fixes

**Summary:** Major AI stance overhaul making all 4 stances (Follow, Aggressive, Defensive, Hold) role-aware so class identity is preserved regardless of stance choice. New inventory destroy-item feature. Audio polish fixes.

### Stance System Overhaul (Phases S1–S3) — `server/app/core/ai_stances.py`, `server/tests/test_stances.py`

- **S1-A: Bard Aggressive kiting fix** — Added `offensive_support` to `is_ranged_role` set in `_decide_aggressive_stance_action()` so Bards kite in Aggressive (was already working in Follow). Added `ally_positions` calculation for Bard kiting direction to stay near ally centroid.
- **S1-B: Hold stance smart targeting** — Replaced naive `for enemy in enemies` iteration with `_pick_best_target()` for both melee (adjacent enemies) and ranged (in-range + LOS enemies) target selection in `_decide_hold_action()`.
- **S2-A: Defensive match_state** — Added `match_state=None` parameter to `_decide_defensive_action()` for totem awareness.
- **S2-B: Defensive ranged kiting** — Ranged classes (Mage, Ranger, Inquisitor, Plague Doctor, Bard, Shaman) now kite in Defensive stance with role-specific thresholds (controller ≤ 3, totemic_support ≤ 1, others ≤ 2). Kite moves tethered within 2 tiles of owner.
- **S2-C: Defensive ranged engagement** — Ranged roles now engage enemies at their full attack range instead of hardcoded 2-tile limit. Melee classes unchanged.
- **S2-D: Defensive support positioning** — Support classes (Confessor, Bard, Shaman) on Defensive now position near allies using role-specific move preference functions instead of charging enemies.
- **S2-E: Defensive totem-biased movement** — Added `_totem_biased_step` to Defensive movement paths and controller hold-position logic. Re-checks tether after totem bias.
- **S3-A: Aggressive support positioning** — Support classes on Aggressive now use ally positioning instead of charging enemies. Added `is_support` detection, excluded support from melee rush block.
- **S3-B: Bard ally-proximity kiting** — Already handled by S1-A.

### Audio Fixes — `client/public/audio-effects.json`, `client/src/audio/AudioManager.js`

- Wither cast sound → `shadow-step_teleport-downer.wav` (softer dark tone, vol 0.55)
- Wither DoT tick → `debuff_speed-debuff.wav` (subtler pulse, vol 0.25)
- Healing Totem pulse → `heal-alt_healing-gusts.wav` (gentle nature sound, vol 0.25)
- Registered `heal_alt` in `_soundFiles` for preloading

### 3747 tests passing, 0 regressions.

---

## [Feature] - 2026-03-13 - Destroy Item from Inventory

**Summary:** Players can now permanently destroy unwanted items from their bag during dungeon runs. Previously, once a player's 10-slot inventory filled up, there was no way to discard items to make room for better loot. Each bag slot now has a destroy button (🗑) with a two-click confirmation to prevent accidents.

### Added — `server/app/core/equipment_manager.py`

- **`destroy_item()`** — New function that removes an item from a player's inventory by instance_id or item_id. Returns the updated inventory list. Validates player exists and is alive.

### Changed — `server/app/core/match_manager.py`

- **Re-export block** — Added `destroy_item` to the equipment_manager re-exports so existing importers can access it via match_manager

### Changed — `server/app/services/message_handlers.py`

- **`handle_destroy_item()`** — New async WS handler accepting `{ type: "destroy_item", item_id, unit_id? }`. Calls `destroy_item()` and responds with `item_destroyed` message containing the updated inventory
- **`MESSAGE_HANDLERS`** — Added `"destroy_item": handle_destroy_item` entry
- **Imports** — Added `destroy_item` to the match_manager import block

### Changed — `client/src/App.jsx`

- **WS message dispatch** — Added `case 'item_destroyed'` that dispatches `ITEM_DESTROYED` action to the reducer

### Changed — `client/src/context/GameStateContext.jsx`

- **`INVENTORY_ACTIONS`** — Added `'ITEM_DESTROYED'` to the action routing set so it reaches the inventory reducer

### Changed — `client/src/context/reducers/inventoryReducer.js`

- **`case 'ITEM_DESTROYED'`** — New reducer case that updates `state.inventory` (or `partyInventories` for party members) with the server-provided updated inventory array

### Changed — `client/src/components/Inventory/Inventory.jsx`

- **`confirmDestroyId` state** — New state variable tracking which item is awaiting destruction confirmation
- **`handleDestroyItem()`** — New callback implementing two-click confirm: first click sets confirm state (button turns red), second click sends the `destroy_item` WS message
- **Bag slot actions** — Wrapped transfer and new destroy buttons in a `.bag-slot-actions` container. Destroy button (🗑/✕) shown on all items when alive, not just when transfer is available

### Changed — `client/src/styles/components/_inventory.css`

- **`.bag-slot-actions`** — Flex container for the action button group
- **`.bag-destroy-btn`** — Styled to match the existing transfer button aesthetic with red hover state
- **`.bag-destroy-btn.destroy-confirm`** — Red filled background with pulse animation for the confirmation state
- **`@keyframes pulse-destroy`** — Subtle pulsing animation to draw attention to the confirm state

---

## [Feature] - 2026-03-12 - Launcher Install Progress Bar (Launcher v1.1.0)

**Summary:** Added a real-time progress bar during the game extraction/install phase. Previously the launcher showed "INSTALLING..." with no visual feedback, making it look frozen. Now reuses the same smooth animated progress bar from the download phase, showing file-by-file extraction progress.

### Changed - `launcher/lib/extractor.js`

- **`extract()`** - Added `onProgress` callback option
- **`extractWithProgress()`** - New helper that extracts entries one at a time via `extractEntryTo()` instead of `extractAllTo()`, calling `onProgress(extracted, total)` after each file

### Changed - `launcher/main.js`

- **start-install handler** - Extract step now passes `onProgress` callback that sends `extract-progress` IPC events to the renderer with `{extracted, total}` counts

### Changed - `launcher/preload.js`

- **`onExtractProgress`** - New IPC bridge method exposing the `extract-progress` event to the renderer

### Changed - `launcher/renderer.js`

- **`applyState('installing')`** - Now shows the progress bar (reset to 0%) instead of hiding it
- **`onExtractProgress` listener** - Updates progress bar with smooth animation showing file count (e.g. "45% - 230 / 512 files")
- **Progress bar visibility** - Now stays visible during both `downloading` and `installing` states

---

## [Bugfix] - 2026-03-12 - Town Hub Hero Portraits Missing (v0.1.3)

**Summary:** Fixed hero portraits not displaying in Town Hub screens (Hero Roster, Hiring Hall, Merchant). Same root cause as v0.1.2 — absolute asset path under Electron's `file://` protocol.

### Changed — `client/src/components/TownHub/HeroSprite.jsx`

- **CSS `backgroundImage`** — Changed from `url(/spritesheet.png)` to `` url(${import.meta.env.BASE_URL}spritesheet.png) `` so the spritesheet resolves correctly in deployed Electron builds

---

## [Bugfix] — 2026-03-12 — Missing Sprites, Audio & Particles in Deployed Build

**Summary:** Fixed all static asset paths that broke when the game was loaded via Electron's `file://` protocol in deployed (installed) builds. Sprites, tiles, skill icons, audio, and particle effects were all missing for testers despite being correctly included in the build zip. Dev mode via `start-game.bat` was unaffected because Vite's dev server resolves `/` paths to the project root.

**Root cause:** All static asset paths in the codebase used absolute root-relative paths (e.g. `/spritesheet.png`, `/audio/combat/swing.wav`). In development, Vite's dev server maps `/` to the project's `public/` folder, so these work. In production Electron builds, the app loads via `file://` protocol from `dist/index.html`. Under `file://`, a leading `/` resolves to the **filesystem root** (e.g. `C:\spritesheet.png`), not the app's `dist/` folder. The Vite config already sets `base: './'` for Electron builds, which fixes JS/CSS bundle paths, but hardcoded asset constants in source code are not affected by Vite's `base` setting.

**Impact:** This was the cause of missing sprites and sounds reported during the first online test. All game logic, UI components, API calls, and WebSocket connections were unaffected (those use full HTTP URLs from `serverUrl.js`).

### Changed — `client/src/canvas/SpriteLoader.js`

- **`SPRITESHEET_PATH`** — Changed from `'/spritesheet.png'` to `` `${import.meta.env.BASE_URL}spritesheet.png` `` — resolves to `./spritesheet.png` in Electron builds, `/spritesheet.png` in dev

### Changed — `client/src/canvas/TileLoader.js`

- **`TILESHEET_PATH`** — Changed from `'/tilesheet.png'` to `` `${import.meta.env.BASE_URL}tilesheet.png` ``

### Changed — `client/src/components/BottomBar/SkillIconMap.js`

- **`SKILL_ICON_SHEET`** — Changed from `'/skill-icons.png'` to `` `${import.meta.env.BASE_URL}skill-icons.png` ``

### Changed — `client/src/audio/AudioManager.js`

- **`init()`** — Audio effects JSON fetch now uses `${baseUrl}audio-effects.json` instead of `/audio-effects.json`
- **`_preloadBuffer()`** — Sound file URLs from `audio-effects.json` (e.g. `/audio/combat/swing.wav`) are now normalized: leading `/` is replaced with `import.meta.env.BASE_URL`
- **`_playTrack()`** — Music track paths from `audio-effects.json` receive the same normalization

### Changed — `client/src/canvas/particles/ParticleManager.js`

- **`init()`** — Particle presets and effects JSON fetches now use `${baseUrl}particle-presets.json` and `${baseUrl}particle-effects.json` instead of absolute paths
- **Category file fetches** — Individual preset category files (e.g. `particle-presets/combat.json`) now use `${baseUrl}${file}` instead of `/${file}`

---

## [Bugfix] — 2026-03-12 — Batch PVP Team A Frozen AI

**Summary:** Fixed a bug where Team A units in batch PVP matches would return WAIT every turn instead of fighting, causing most matches to hit the max turn limit (200) and end as draws. Skills, attacks, and movement were all working correctly — the root cause was an AI ownership lookup failure.

**Root cause:** Team A units are spawned as `ai_allies` with `hero_id` and `ai_stance="follow"`, which routes them into the stance-based AI system (`_decide_stance_action`). The stance system calls `_find_owner()` to locate the human player they should follow. In batch PVP mode, the only "human" is a dummy host that gets removed from `all_units` after match creation. With no owner found, `_find_owner()` returns `None` and the follow stance falls back to WAIT. Team B (`ai_opponents`) was unaffected because those units have `hero_id=None` and fall through to independent aggressive AI.

**Note:** This bug was not caused by the Refactor 1A skills split. PVPVE mode is also unaffected — it handles leaderless AI teams correctly by designating one unit per team as `is_team_leader=True`, which `_find_owner()` uses as a fallback.

### Changed — `server/batch_pvp.py`

- **`run_headless_match()`** — After removing the dummy host, Team A units now have their `hero_id` cleared, `ai_stance` set to `None`, and `ai_behavior` set to `"aggressive"`. This converts them from stance-based hero allies (which need a human owner) into independent AI combatants — identical behavior to Team B. Both teams now use the same AI decision engine for fair simulation.

---

## [Balance] — 2026-03-11 — Monster Rarity & Wave Arena Balance Pass

**Summary:** Addressed oppressive damage spikes from rarity-upgraded (champion/rare) monsters in the wave arena and dungeons. The wave spawner was missing the difficulty budget and enhanced-per-room cap systems that dungeons use, allowing uncapped rarity stacking. Additionally, several affix multipliers were tuned down to reduce multiplicative damage escalation that could one-shot tanks.

**Root cause:** The wave spawner (`_spawn_next_wave`) called `roll_monster_rarity()` per enemy with zero guardrails — no `max_enhanced_per_room` cap, no `difficulty_budget` downgrade, and no `floor_overrides` for affix count limits. A single wave could produce multiple rares with full 2-3 affixes each. Combined with multiplicative damage stacking (tier × champion × affix × aura), a rare Extra Strong ghoul with Might Aura nearby could deal 27+ damage/hit vs a crusader's 135 HP.

### Changed — `server/app/core/wave_spawner.py`

- **`_spawn_next_wave()`** — Ported difficulty budget and cap enforcement from dungeon `map_exporter.py`:
  - Tracks `wave_enhanced_count` per wave, capped by `max_enhanced_per_room` from config (respects `floor_overrides`)
  - Computes per-wave `difficulty_budget` via `get_room_budget(wave_number, enemy_count)` — deducts `get_rarity_cost()` per enemy, downgrades rare→champion→normal if over budget
  - Reads `floor_overrides` via `get_floor_override(wave_number)` to apply early-wave affix count caps (e.g. 1-2 affixes on waves 1-3 instead of 2-3)
  - Supports per-wave `max_rarity` field from wave config — downgrades rolled rarity if it exceeds the wave's declared cap

### Changed — `server/configs/maps/wave_arena.json`

- **Waves 1-3** — Added `"max_rarity": "normal"` — no rarity upgrades allowed on introductory waves
- **Waves 4-5** — Added `"max_rarity": "champion"` — champions allowed but rares blocked
- **Waves 6-10** — Unchanged (full rarity range, constrained by budget system)

### Changed — `server/configs/monster_rarity_config.json`

- **`extra_strong` affix** — Damage multiplier reduced from 1.5× to **1.3×** (was the single largest damage spike source)
- **`might_aura` affix** — Ally damage multiplier reduced from 1.25× to **1.15×** (was amplifying entire packs multiplicatively)
- **`conviction_aura` affix** — Enemy armor reduction reduced from -3 to **-2** (was devastating low-armor classes: -3 from 2 armor = near-zero)
- **`floor_bonus_per_level`** — Rarity chance scaling reduced from 0.015 to **0.01** per wave/floor (softens the rarity ramp on later waves)

### Before/After — Damage Comparison (Rare Extra Strong Ghoul vs Crusader)

| Scenario | Before | After |
|---|---|---|
| Raw hit (no aura) | 21 dmg (7 hits to kill) | 17 dmg (8 hits to kill) |
| With Might Aura nearby | 27 dmg (5 hits to kill) | 19 dmg (8 hits to kill) |
| + Conviction Aura debuff | 30 dmg (5 hits to kill) | 20 dmg (7 hits to kill) |

### Tests — 3,775 passing

- Updated 5 test assertions in `test_monster_rarity.py` to match new `extra_strong` (1.3×) and `floor_bonus_per_level` (0.01) values

---

## [Refactor 1A] — 2026-06-21 — Split skills.py into skill_effects/ sub-package

**Summary:** Extracted all 30 `resolve_*` skill-effect handler functions from the monolithic `skills.py` (3,818 lines) into a new `server/app/core/skill_effects/` sub-package with 7 domain-specific modules. `skills.py` retains config loading, validation, buff/CC/ward helpers, and the central `resolve_skill_action` dispatcher. All 3,774 tests pass; all existing import paths remain backward-compatible via re-exports.

### Added — `server/app/core/skill_effects/` (new sub-package)

- **`_helpers.py`** — Shared helpers: `_apply_skill_cooldown`, `_resolve_skill_entity_target`
- **`heal.py`** — 3 handlers: `resolve_heal`, `resolve_hot`, `resolve_aoe_heal`
- **`damage.py`** — 13 handlers: `resolve_multi_hit`, `resolve_ranged_skill`, `resolve_holy_damage`, `resolve_stun_damage`, `resolve_aoe_damage`, `resolve_aoe_magic_damage`, `resolve_ranged_damage_slow`, `resolve_magic_damage`, `resolve_aoe_damage_slow`, `resolve_lifesteal_damage`, `resolve_lifesteal_aoe`, `resolve_aoe_damage_slow_targeted`, `resolve_melee_damage_slow`
- **`buff.py`** — 9 handlers: `resolve_buff`, `resolve_aoe_buff`, `resolve_damage_absorb`, `resolve_shield_charges`, `resolve_evasion`, `resolve_conditional_buff`, `resolve_thorns_buff`, `resolve_cheat_death`, `resolve_buff_cleanse`
- **`debuff.py`** — 6 handlers: `resolve_dot`, `resolve_taunt`, `resolve_aoe_debuff`, `resolve_targeted_debuff`, `resolve_ranged_taunt`, `resolve_aoe_root`
- **`movement.py`** — 1 handler: `resolve_teleport`
- **`summon.py`** — 2 handlers: `resolve_place_totem`, `resolve_soul_anchor`
- **`utility.py`** — 2 handlers: `resolve_detection`, `resolve_cooldown_reduction`
- **`__init__.py`** — Re-exports all 36 public symbols for `from app.core.skill_effects import ...`

### Changed — `server/app/core/skills.py`

- Reduced from ~3,818 lines to ~580 lines
- Retains: config loading (`load_skills_config`, `get_skill`, `get_all_skills`, etc.), validation (`can_use_skill`), buff helpers (`tick_buffs`, `get_melee_buff_multiplier`, etc.), CC helpers (`is_stunned`, `is_slowed`, etc.), ward/absorb helpers, and the `resolve_skill_action` dispatcher
- Dispatcher now calls handlers imported from `skill_effects` sub-modules
- Bottom-of-file re-exports ensure `from app.core.skills import resolve_heal` continues to work across all 43 consumer files (13 app + 30 test files)

### Architecture — Circular Import Avoidance

- `_helpers.py` imports only from `app.models` (no circular risk)
- Sub-modules that need skills helpers (e.g., `get_effective_armor`) use **lazy imports** inside function bodies: `from app.core.skills import get_effective_armor`
- `skills.py` imports from `skill_effects` at the bottom of the file, after all local functions are defined

---

## [Phase 27D] — 2026-03-09 — PVPVE Victory Conditions & PVE Team

**Summary:** Implements PVPVE victory logic so that the match correctly ends when only one player team survives, regardless of how many PVE enemies remain alive. PVE enemies on the `"pve"` team are excluded from the victory calculation. Player teams are hostile to each other and to PVE enemies. PVE enemies target all player teams equally. 21 new Phase D tests, 37 total PVPVE tests passing.

### Changed — `server/app/core/combat.py`

- **`check_team_victory()`** — Added optional `excluded_teams: set[str] | None` parameter. When provided (e.g. `{"pve"}`), units on excluded teams are filtered out before counting survivors. PVE enemies being alive no longer blocks PVPVE victory.

### Changed — `server/app/core/turn_phases/deaths_phase.py`

- **`_resolve_victory()`** — Added optional `match_type: str | None` parameter. When `match_type == "pvpve"`, passes `excluded_teams={"pve"}` to `check_team_victory()`.

### Changed — `server/app/core/turn_resolver.py`

- **`resolve_turn()`** — Derives `match_type` from `match_state.config.match_type` and passes it to `_resolve_victory()` for PVPVE exclusion logic.

### Changed — `server/app/services/tick_loop.py`

- **`match_tick()`** — Added PVE team FOV computation: when `match.team_pve` is populated, adds a `"pve"` entry to `ai_team_fov_map` so PVE enemies share vision with nearby PVE allies.

### Tests — `server/tests/test_pvpve.py`

- **`TestCheckTeamVictoryExcludedTeams`** (7 tests): Victory with excluded PVE, draw when all player teams dead, 4-team scenarios, backward compatibility.
- **`TestResolveVictoryPVPVE`** (3 tests): `_resolve_victory()` integration with match_type exclusion.
- **`TestPVEAITargeting`** (5 tests): PVE enemies hostile to all player teams, PVE allies with each other.
- **`TestPlayerTeamsHostile`** (6 tests): Inter-team hostility, same-team allies, player-vs-PVE hostility.

---

## [Phase 27C] — 2026-03-09 — PVPVE Match Manager Flow

**Summary:** Implements the PVPVE match initialization pipeline in the match manager. When a PVPVE match starts, the system generates a procedural PVPVE dungeon, distributes players across 2–4 teams, spawns each team in their designated corner zone, initializes dungeon state (doors, chests), spawns all PVE enemies on the dedicated `"pve"` team, and computes initial FOV. Floor advancement and stairs are disabled for PVPVE (single-floor mode).

### Added — `match_manager.py`

- **`_PVPVE_TEAM_KEYS`** — Constant list `["a", "b", "c", "d"]` for team assignment ordering.
- **`_start_pvpve_match(match_id)`** — Top-level PVPVE initialization orchestrator. Calls team assignment → dungeon generation → smart spawns → class stats → dungeon state init → PVE enemy spawning in sequence.
- **`_assign_pvpve_teams(match_id)`** — Distributes human players + AI allies across teams. Host always goes to team A. Others round-robin across active teams. AI allies fill remaining team slots round-robin. Clears old team lists before reassignment. Updates each player's `.team` field.
- **`_generate_pvpve_dungeon(match)`** — Generates a WFC procedural dungeon using `FloorConfig.for_pvpve()`. Registers the map as `pvpve_{match_id}`. Assigns a random dungeon theme and stores the dungeon seed.
- **`_spawn_pvpve_enemies(match_id)`** — Spawns PVE enemies from room definitions. All enemies placed on `team="pve"` (read from spawn data). Enemy IDs tracked in `match.team_pve` (not in team_a/b/c/d). Full monster rarity system support: champion packs, rare minions, super unique bosses with retinue.

### Changed — `match_manager.py`

- **`start_match()`** — Added PVPVE branch that delegates to `_start_pvpve_match()` before the standard dungeon/PVP flow. Non-PVPVE matches unchanged.
- **`get_stairs_info()`** — Returns empty stairs for PVPVE matches (no stairs in single-floor mode).
- **`advance_floor()`** — Returns `None` immediately for PVPVE matches (no floor advancement).
- **`remove_match()`** — Now also cleans up `pvpve_{match_id}` runtime maps in addition to `wfc_{match_id}`.

### Tests

- 22 new tests in `test_pvpve_phase_c.py`:
  - `TestAssignPVPVETeams` (7 tests) — Host on team A, 2-team round-robin, 4-team distribution, 3-team (no team D), AI distribution, player.team field updates, old list clearing.
  - `TestPVPVEMatchStart` (5 tests) — Match starts successfully, pvpve_ map prefix, dungeon seed stored, theme assigned, dungeon state initialized.
  - `TestPVPVEEnemySpawning` (5 tests) — PVE enemies on "pve" team, team_pve populated, PVE IDs not in player teams, PVE are AI units, PVE tracked in ai_ids.
  - `TestPVPVEFOV` (1 test) — FOV computed for all alive units across all teams.
  - `TestPVPVENoFloorAdvancement` (3 tests) — No stairs info, advance_floor returns None, floor stays at 1.
  - `TestPVPVECleanup` (1 test) — remove_match unregisters PVPVE runtime map.

### Regression

- 3717 passing (+22 new) · 1 pre-existing failure (unrelated `test_turn_resolver.py` melee tracking assertion)

---

## [Phase 27B] — 2026-03-09 — PVPVE WFC Generation Pipeline

**Summary:** Extends the WFC dungeon generation engine to produce PVPVE-specific layouts. The decorator places 2–4 team spawn rooms in grid corners, a center boss room, applies a multi-spawn proximity ramp (safe → softened → normal), and computes a difficulty gradient (normal → hard → elite → boss) based on Manhattan distance to center. The map exporter tags all PVE enemies with `"team": "pve"`, collects per-team spawn zones, and emits `boss_room` metadata.

### Added — `dungeon_generator.py`

- **`FloorConfig.pvpve_mode`** (bool, default False) — Enables PVPVE layout generation.
- **`FloorConfig.pvpve_team_count`** (int, default 2) — Number of player teams (2–4).
- **`FloorConfig.for_pvpve()`** — Factory classmethod producing a FloorConfig optimized for PVPVE: 8×8 grid, floor 1, mid-tier roster, batch_size=5, balanced style, `empty_room_chance=0.15`.
- Updated `generate_dungeon_floor()` to inject `pvpve_mode`, `pvpve_team_count`, and `guaranteeStairs: False` into decorator settings when in PVPVE mode. Passes PVPVE params and decoration result to the map exporter.

### Added — `room_decorator.py`

- **`_PVPVE_DECORATOR_DEFAULTS`** — Config block for PVPVE-specific decorator settings (boss_guards, boss_chests, safe/softened enemy caps).
- **`_PVPVE_TEAM_CORNERS`** — Maps teams a–d to grid corners: a→top-left, b→bottom-right, c→top-right, d→bottom-left.
- **`_PVPVE_DIFFICULTY_TIERS`** — Distance-based difficulty tiers: boss (dist 0, 5 enemies), elite (dist 1, 5), hard (dist 2, 4), normal (3+, 3).
- **`_get_active_teams(team_count)`** — Returns active team letters based on count (clamped 2–4).
- **`_pvpve_assign_corner_spawns()`** — Places spawn rooms near target corners using `_find_nearest_flexible()`.
- **`_pvpve_assign_center_boss()`** — Places boss room at grid center, avoiding assigned rooms.
- **`_pvpve_compute_proximity_ramp()`** — Multi-spawn proximity ramp: distance 1 = "safe", distance 2 = "softened".
- **`_pvpve_compute_difficulty_tier()`** — Manhattan distance to center → tier name.
- **`_pvpve_get_max_enemies_for_tier()`** — Per-tier enemy count cap.
- Refactored `decorate_rooms()` with a PVPVE branch: corner spawns → center boss → proximity ramp → difficulty gradient. Standard dungeon path preserved unchanged.
- Phase 4 tile placement: PVPVE boss rooms get configurable extra guards + chests. Spawn-prefixed roles handled in placement and stats.
- Return value includes `pvpve_spawn_rooms` (team → {gridRow, gridCol}) and `pvpve_difficulty_tiers` when in PVPVE mode.

### Added — `map_exporter.py`

- **`export_to_game_map()`** — New params: `pvpve_mode`, `pvpve_team_count`, `decoration_result`.
- **Per-team spawn points** (`spawn_points_by_team`) — Groups S-tile spawn points by team using decorator's `pvpve_spawn_rooms` grid-cell lookup.
- **PVE team tagging** — All enemy spawns (regular E, boss B, super_unique, retinue) get `"team": "pve"` when in PVPVE mode.
- **Per-team spawn zones** — Built from grouped spawn points (expanded ±2 tiles for formation room), keyed by team letter.
- **Boss room metadata** — `boss_room` dict with id, bounds, enemy_spawns, chests.
- **Map type** — Set to `"pvpve"` instead of `"dungeon"` when in PVPVE mode.
- Top-level output includes `pvpve_team_count`, `spawn_points_by_team`, `boss_room`.

### Tests

- 63 new tests in `test_pvpve_phase_b.py`:
  - `TestFloorConfigPVPVE` (13 tests) — factory defaults, grid size, team clamping, density, roster, map name.
  - `TestPVPVEHelpers` (13 tests) — active teams, difficulty tiers, max enemies per tier.
  - `TestPVPVECornerSpawns` (5 tests) — 4-corner placement, 2-team mode, near-top-left/bottom-right, no adjacent spawns.
  - `TestPVPVECenterBoss` (2 tests) — near-center placement, no overlap with spawns.
  - `TestPVPVEProximityRamp` (3 tests) — safe/softened/no-override at correct distances.
  - `TestPVPVEDecoratorIntegration` (9 tests) — 4-team spawns, 2-team spawns, boss placement, no stairs, safe adjacency, metadata, difficulty tiers, boss guards.
  - `TestPVPVEExporter` (11 tests) — map_type, team_count, spawn zones, spawn points, enemy PVE tags, boss metadata, standard mode unchanged.
  - `TestPVPVEFullPipeline` (7 tests) — end-to-end generation, map type, dimensions, spawn zones, PVE tags, determinism.

### Regression

- All 335 existing WFC tests pass unchanged.

---

## [Phase 27A] — 2026-03-09 — PVPVE Data Model & Match Type

**Summary:** Foundation data model for the new PVPVE competitive dungeon mode. Adds the `PVPVE` match type enum, PVPVE-specific configuration fields on `MatchConfig`, and a `team_pve` list on `MatchState` for tracking PVE enemy IDs separately from player teams.

### Added

- **`MatchType.PVPVE`** — New enum value `"pvpve"` for competitive dungeon matches where 2–4 player teams fight PVE enemies and each other.

- **`MatchConfig` PVPVE fields:**
  - `pvpve_team_count` (int, default 2) — Number of player teams (2–4).
  - `pvpve_pve_density` (float, default 0.5) — PVE enemy density multiplier (0.0–1.0).
  - `pvpve_boss_enabled` (bool, default True) — Whether to spawn a center boss.
  - `pvpve_loot_density` (float, default 0.5) — Chest/loot density multiplier.
  - `pvpve_grid_size` (int, default 8) — WFC grid size for map generation.

- **`MatchState.team_pve`** — List of PVE enemy IDs (`list[str]`, default empty). Tracks PVE enemies separately so they can be excluded from player team victory checks.

### Tests

- 16 new tests in `test_pvpve.py`:
  - `TestMatchTypePVPVE` (5 tests) — enum existence, serialization, deserialization, config assignment, JSON round-trip.
  - `TestMatchConfigPVPVEFields` (7 tests) — default values for all 5 fields, custom values, full round-trip.
  - `TestMatchStatePVPVE` (4 tests) — empty default, ID storage, round-trip, full state with all teams + PVE.

### Test count

- 3632 passing (+16 new) · 1 pre-existing failure (unrelated `test_phase16d_unique_items.py`)

---

## [Phase 26D] — 2026-03-07 — AI Totem Awareness

**Summary:** AI-controlled heroes now recognize active healing totems as safe zones. They will retreat toward totems when critically injured, prefer kiting in the direction of a totem, and gently drift toward totem heal zones during normal combat when hurt — without being hard-locked to the totem's position.

### Added

- **`_find_nearest_healing_totem()` helper** — Scans `match_state.totems` for the closest alive, same-team healing totem within a configurable distance (`_TOTEM_RETREAT_MAX_DIST = 8` tiles). Returns the totem dict or `None`. Used by retreat, kiting, and combat positioning logic.

- **`_tile_inside_totem_radius()` helper** — Quick Chebyshev check for whether a tile is within a totem's `effect_radius`.

- **`_totem_biased_step()` helper** — Soft drift function for normal combat movement. When an AI hero is below 80% HP (`_TOTEM_DRIFT_HP_THRESHOLD`) and a healing totem is nearby, nudges the planned movement step toward a tile inside the totem's radius — but only if it doesn't lose progress toward the AI's actual move target. Creates a gentle "gravity well" effect without overriding combat goals.

- **Retreat Priority 1.5: Healing Totem** — New retreat destination slotted between "path toward support ally" (Priority 1) and "path toward owner" (Priority 2) in `_find_retreat_destination()`. When a low-HP hero triggers retreat and there's an active same-team healing totem within 8 tiles, the hero paths toward the totem center. If already inside the totem's effect radius, falls through to the next priority (no unnecessary repositioning).

- **Totem-biased kiting** — In both Follow and Aggressive stance kiting (Phase 8K-3), ranged roles now score retreat tiles with a totem proximity bonus (`_TOTEM_KITE_BIAS_WEIGHT = 2`). When stepping away from a melee threat, the AI prefers tiles that are inside (or closer to) a healing totem radius, while still maximizing distance from the threat. Falls back to the original retreat tile if no totem is active.

- **Totem-biased combat movement** — In both Follow and Aggressive stance "move toward target" phases, the planned A* step is passed through `_totem_biased_step()` when the AI is hurt. This causes injured heroes to naturally drift into totem heal zones during regular fighting without changing their target priorities.

- **Constants:**
  - `_TOTEM_RETREAT_MAX_DIST = 8` — Max distance for AI to consider retreating toward a totem
  - `_TOTEM_KITE_BIAS_WEIGHT = 2` — Scoring bonus when a kite tile is inside totem radius
  - `_TOTEM_DRIFT_HP_THRESHOLD = 0.80` — HP ratio below which soft drift activates

### Changed

- **`_find_retreat_destination()` signature** — Added optional `match_state=None` parameter to access `match_state.totems` for the new Priority 1.5 totem retreat.

- **`_decide_stance_action()` retreat call** — Now forwards `match_state=match_state` to `_find_retreat_destination()`.

- **`_decide_follow_action()` signature** — Added optional `match_state=None` parameter. Stance dispatch now forwards `match_state`.

- **`_decide_aggressive_stance_action()` signature** — Added optional `match_state=None` parameter. Stance dispatch now forwards `match_state`.

- **Follow stance kiting block** — Replaced simple `_find_retreat_tile` with totem-biased tile scoring when a healing totem is active.

- **Aggressive stance kiting block** — Same totem-biased tile scoring as Follow stance.

- **Follow stance movement** — Final "Move toward target" step now passes through `_totem_biased_step()`.

- **Aggressive stance movement** — Final "Move toward target" step now passes through `_totem_biased_step()`.

### File Changed

- `server/app/core/ai_stances.py` — All changes confined to this single file (~120 lines added).

### Not Changed

- **Hold stance** — Never moves; no totem awareness needed (by design).
- **Defensive stance** — 2-tile owner leash already constrains positioning; adding totem bias would conflict with the "stay near owner" mandate. No changes.
- **Enemy AI** — Enemies have no totem awareness (intentional — they don't cooperate with player totems).
- **Shaman's own AI** — The Shaman's totem placement logic (`_totemic_support_skill_logic` in `ai_skills.py`) is unchanged. The Shaman already places totems intelligently; this change makes *other* heroes aware of those totems.

### Design Notes

- **Soft preference, not hard lock** — No AI behavior is overridden. Totem proximity is a tiebreaker / secondary factor in every case. Heroes still chase enemies, still attack, still regroup with the owner. The totem is simply an attractive "safe zone" that the AI knows about.
- **Three tiers of totem awareness:**
  1. **Retreat** (strongest) — Critical HP heroes actively path TO the totem
  2. **Kiting** (medium) — Ranged heroes prefer kite directions near the totem
  3. **Combat drift** (gentlest) — Hurt heroes nudge toward totem during normal movement
- **All 3605 tests pass** (1 pre-existing failure in `test_phase16d_unique_items.py` unrelated to this change). 675 AI-specific tests pass with zero regressions.
