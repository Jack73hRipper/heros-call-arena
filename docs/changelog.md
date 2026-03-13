# Arena — Changelog

All notable changes to this project will be documented in this file.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

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
