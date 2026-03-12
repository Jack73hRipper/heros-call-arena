# Arena Prototype

Turn-based multiplayer combat arena & grimdark dungeon crawler — MMO Project.

**Current status:** Launcher Phase L7 complete (Polish & Hardening — settings panel with install dir/browse/auto-check/minimize-to-tray/repair, system tray icon, window position persistence, loading spinner, smooth animated progress bar, file logging with rotation, keyboard shortcuts Enter/Esc, tray update notifications) · Launcher Phase L6 complete (Launcher Self-Update — electron-updater integration, auto-download background install, GitHub Releases publish config, notification bar with Restart Now, dev-mode skip, separate launcher v1.x / game v0.x versioning) · Launcher Phase L5 complete (Publish Pipeline — host-agnostic publish-config.json supporting R2/GitHub/local, publish-update.bat full build+hash+manifest+upload pipeline, write-patch-notes.bat template generator, bump-version.bat semver helper, start-publish.bat convenience wrapper) · Launcher Phase L4 complete (Download & Install — Downloader with progress/cancellation, SHA-256 Verifier, Extractor with atomic update swap, GameLauncher with auto-detect exe/minimize/foreground-on-exit, full UI progress bar with status pipeline, disk space check, installed.json write-back) · Launcher Phase L3 complete (Manifest & Version Check — VersionChecker module fetches remote latest.json, compares with local installed.json, UI state machine for not-installed/up-to-date/update-available/check-failed, patch notes markdown rendering, test manifest server) · Launcher Phase L2 complete (Game Packaging — PyInstaller spec for server bundling, Electron main.cjs spawns/kills bundled server in PROD mode with /health polling, electron-builder extraResources config, 5-step build-game-package.bat pipeline) · Launcher Phase L1 complete (Launcher Shell — frameless Electron window, grimdark theme, custom title bar, PLAY button) · Arena Analyst Phase D complete (Advanced Views — Composition Analysis with ranked comps + filterable table, Timeline Replay with SVG damage curves + turn event scrubber, Trend Charts with match volume/damage creep/win distribution) · Arena Analyst Phase C complete (Core Views — MatchList with filters, MatchDetail scoreboard/team comparison/MVP/kill feed, ClassBalance with sortable win rates/stat charts/class matrix) · Arena Analyst Phase B complete (Tool Scaffold — React+Vite app, Express API server, match history endpoints) · WFC Integration Phase C complete (Shared Module Format — canonical library.json, tool→server export pipeline, JSON loading with builtin fallback, round-trip import/export, 38 tests) · WFC Integration Phase B complete (Batch Generation — Best-of-N candidate selection, quality scoring, 33 tests) · WFC Integration Phase A complete (Dungeon Style Templates — 5 styles, auto-selection, floor-scaled weight/decorator overrides — 51 tests) · Phase 20 complete (Turn Resolver File Split — 2,240→267 line orchestrator, 10 sub-modules in turn_phases/, 61 smoke tests, 19 test imports migrated) · Phase 19 complete (Inventory/Stats Panel Overhaul — bag sort, set bonus badges, responsive width, class portrait, party quick-switch tabs) · Phase 18F complete (Loot Integration — rarity-scaled drops, bonus items, guaranteed rarity, gold multiplier, elite kill broadcast + client notifications — 38 tests) · Phase 18E complete (Client Visual Feedback — name colors, glow, tints, ghostly, minimap, combat log, enemy panel, affix ambient particles, death explosions, death celebrations) · Phase 18I complete (Enemy Identity Skills — 42 tests) · Phase 18G complete (Super Uniques — 63 tests) · Phase 18H complete (Enemy Forge Tool) · Phase 18D complete (Combat Integration — auras, on-hit effects, on-death explosions, ghostly phase-through, teleporter auto-cast, minion unlinking, 33 tests) · Phase 18C complete (Spawn Integration — 28 tests) · Phase 18B complete (Affix Engine — 150 tests) · Phase 18A complete (Monster Rarity Data Model) · Phase 16G complete (Client UI & Loot Presentation) · CSS split complete · 2933 tests passing

## Project Structure

```
Arena/
├── start-game.bat          # Launch backend + frontend together
├── start-backend.bat       # Launch Python backend only
├── start-frontend.bat      # Launch Vite dev server only
├── start-electron.bat      # Launch Electron desktop app
├── start-dungeon-wfc.bat   # Launch WFC Dungeon Lab tool
├── start-particle-lab.bat  # Launch Particle Effects Lab tool
├── start-sprite-cataloger.bat # Launch Sprite Cataloger tool
├── start-cave-automata.bat # Launch Cave Automata Lab tool
├── start-module-decorator.bat # Launch Module Sprite Decorator tool
├── start-theme-designer.bat# Launch Dungeon Theme Designer tool
├── start-audio-workbench.bat # Launch Audio Workbench tool
├── start-item-forge.bat    # Launch Item Forge tool
├── start-enemy-forge.bat   # Launch Enemy Forge tool
├── start-arena-analyst.bat # Launch Arena Analyst tool
├── start-launcher.bat      # Launch game launcher (dev mode)
├── start-publish.bat       # Build + publish game update
│
├── docs/                   # Project documentation
│   ├── Current Phase.md            # Phase tracker — all milestones & test counts
│   ├── bug-log.md                  # Bug tracking log
│   ├── websocket-protocol.md       # All WS message types and data shapes
│   ├── project-audit-feb-2026.md   # Feb 2026 project audit
│   ├── project-audit-file-splitting.md # File splitting audit
│   ├── Phase Docs/                 # Design specs per phase
│   │   ├── phase1-design-document-updated.md
│   │   ├── phase2-arena-plus-v2.md
│   │   ├── phase3-arena-refined.md
│   │   ├── phase4-grimdark-dungeon.md
│   │   ├── phase4-implementation-plan.md
│   │   ├── phase5-qol-and-completion.md
│   │   ├── phase5-feature7-gear-management.md
│   │   ├── phase6-skills-and-ui-overhaul.md
│   │   ├── phase6E-dungeon-gui-plan.md
│   │   ├── phase7-party-movement-overhaul.md
│   │   ├── phase8-party-ai-combat-intelligence.md
│   │   ├── phase8K-ai-retreat-and-kiting.md
│   │   ├── phase9-particle-effects-lab.md
│   │   ├── phase10-auto-target-pursuit.md
│   │   ├── phase10G-skill-auto-target.md
│   │   ├── phase11-class-identity.md
│   │   ├── phase11-implementation-log.md
│   │   ├── phase12-dungeon-run.md
│   │   ├── phase12-feature5-procedural-dungeon.md
│   │   ├── phase13-path-forward.md
│   │   ├── phase14-visual-feedback.md
│   │   ├── phase15-complete-experience.md
│   │   ├── phase15-menu-overhaul.md
│   │   ├── phase16-item-equipment-overhaul.md
│   │   ├── phase17-mage-class.md
│   │   ├── phase18-monster-rarity-core.md
│   │   ├── phase18-monster-rarity-content.md
│   │   ├── phase18J-enemy-forge-skill-integration.md
│   │   ├── phase19-inventory-panel-overhaul.md
│   │   ├── phase20-turn-resolver-split.md
│   │   ├── enemy-hp-rebalance-and-identity.md
│   │   ├── enemy-roster-system.md
│   │   ├── loot-system-overhaul.md
│   │   ├── party-control-system.md
│   │   └── wfc-in-game-integration-plan.md
│   ├── Systems/                    # System design docs
│   │   ├── action-intent-system.md
│   │   ├── affix-system.md
│   │   ├── audio-system.md
│   │   ├── audio-workbench.md
│   │   ├── buff-particle-overhaul.md
│   │   ├── combat-meter.md
│   │   ├── combat-system-overview.md
│   │   ├── electron-desktop-app.md
│   │   ├── enemy-forge.md
│   │   ├── input-targeting-systems.md
│   │   ├── minimap.md
│   │   ├── monster-rarity-visual-improvements.md
│   │   ├── particle-visibility-lifecycle.md
│   │   ├── projectile-travel-system.md
│   │   └── weapon-class-lock-system.md
│   ├── Tools/                      # Tool documentation
│   │   ├── wfc-dungeon-lab.md
│   │   ├── sprite-cataloger.md
│   │   ├── cave-automata-lab.md
│   │   ├── module-sprite-decorator.md
│   │   ├── theme-designer.md
│   │   ├── audio-workbench.md
│   │   ├── item-forge.md
│   │   ├── enemy-forge.md
│   │   └── arena-analyst.md
│   ├── Game stats references/
│   │   └── game-balance-reference.md
│   └── Achieve/                    # Archived docs (currently empty)
│
├── server/                 # Python backend (FastAPI)
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py             # Entry point
│   │   ├── config.py           # Settings
│   │   ├── models/             # Pydantic schemas
│   │   │   ├── actions.py          # ActionType enum, PlayerAction
│   │   │   ├── items.py            # Item, StatBonuses, Equipment, Inventory
│   │   │   ├── match.py            # MatchState, MatchConfig
│   │   │   ├── player.py           # PlayerState, ClassDefinition, EnemyDefinition
│   │   │   └── profile.py          # PlayerProfile, Hero
│   │   ├── core/               # Pure game logic (no framework deps)
│   │   │   ├── combat.py              # Melee + ranged damage, LOS, cooldowns, team victory, affix on-hit effects
│   │   │   ├── turn_resolver.py       # Thin orchestrator → delegates to turn_phases/ sub-modules
│   │   │   ├── turn_phases/           # Resolution phase sub-modules (split from turn_resolver.py)
│   │   │   │   ├── helpers.py             # Adjacency utilities
│   │   │   │   ├── items_phase.py         # Phase 0: Item use
│   │   │   │   ├── portal_phase.py        # Phase 0.25–0.9: Portal, extraction, stairs
│   │   │   │   ├── buffs_phase.py         # Phase 0.5–0.75: Cooldowns, buffs, DoT/HoT
│   │   │   │   ├── auras_phase.py         # Phase 18D: Monster rarity auras
│   │   │   │   ├── movement_phase.py      # Phase 1: Batch movement
│   │   │   │   ├── interaction_phase.py   # Phase 1.5–1.75: Doors, loot
│   │   │   │   ├── skills_phase.py        # Phase 1.9: Skill resolution
│   │   │   │   ├── combat_phase.py        # Phase 2–3: Ranged + melee
│   │   │   │   └── deaths_phase.py        # Phase 3.5–4: Deaths, victory
│   │   │   ├── match_manager.py       # Match lifecycle, AI spawning, FOV cache, rarity spawn integration
│   │   │   ├── map_loader.py          # JSON map loading + spawn points
│   │   │   ├── fov.py                 # Recursive shadowcasting + LOS
│   │   │   ├── skills.py              # Skills config loader + validation
│   │   │   ├── loot.py                # Loot generation (roll_enemy_loot, roll_chest_loot, rarity-scaled drops)
│   │   │   ├── spawn.py               # Spawn point logic
│   │   │   ├── ai_behavior.py         # AI decision hub (dispatches to modules below) + teleporter auto-cast
│   │   │   ├── ai_pathfinding.py      # A* pathfinding, neighbor/heuristic helpers, ghostly phase-through
│   │   │   ├── ai_skills.py           # Skill decision logic for all AI skill types
│   │   │   ├── ai_stances.py          # Stance-based AI (follow, aggressive, defensive, hold)
│   │   │   ├── ai_memory.py           # Enemy memory, target tracking, ally reinforcement
│   │   │   ├── ai_patrol.py           # Patrol waypoints & random movement
│   │   │   ├── wave_spawner.py        # Wave state, spawn logic, wave-clear checks, rarity support
│   │   │   ├── equipment_manager.py   # Equip/unequip items, stat bonuses, inventory transfer
│   │   │   ├── item_generator.py      # Procedural item generation (affixes, uniques, sets)
│   │   │   ├── set_bonuses.py         # Set bonus definitions & activation logic
│   │   │   ├── auto_target.py         # Auto-target pursuit, skill range helpers
│   │   │   ├── party_manager.py       # Party control, group actions, stances
│   │   │   ├── hero_manager.py        # Hero selection, spawn, permadeath, kill tracking
│   │   │   ├── monster_rarity.py       # Phase 18A–18D, 18G: Monster rarity config, affix engine, name gen, spawn integration, super uniques
│   │   │   └── wfc/                   # Wave Function Collapse dungeon engine
│   │   │       ├── wfc_engine.py          # Core WFC solver (propagation, collapse, backtracking)
│   │   │       ├── dungeon_generator.py   # High-level dungeon assembly from WFC output + style integration
│   │   │       ├── dungeon_styles.py      # 5 dungeon style templates (weight overrides + decorator defaults)
│   │   │       ├── room_decorator.py      # Room content placement (enemies, chests, doors)
│   │   │       ├── connectivity.py        # Graph connectivity validation for generated layouts
│   │   │       ├── map_exporter.py        # Export WFC result to game map JSON format + rarity rolling
│   │   │       ├── module_utils.py        # Module loading, rotation, socket helpers
│   │   │       └── presets.py             # 49 preset modules (5 socket types, 163 rotation variants)
│   │   ├── services/           # Infrastructure (Redis, scheduler, WS)
│   │   │   ├── websocket.py           # ConnectionManager, ws_manager, WS endpoint dispatcher
│   │   │   ├── tick_loop.py           # match_tick() — game loop (FOV, AI, auras, resolve, broadcast)
│   │   │   ├── message_handlers.py    # 24 WS message handlers + dispatch_message() router
│   │   │   ├── persistence.py         # JSON file persistence (hero/profile save/load)
│   │   │   ├── redis_client.py        # Redis client wrapper
│   │   │   └── scheduler.py           # APScheduler task scheduler
│   │   └── routes/             # REST + WS endpoints
│   │       ├── lobby.py               # Lobby/match creation
│   │       ├── maps.py                # Map list endpoint
│   │       ├── match.py               # Match REST routes
│   │       └── town.py                # Town hub REST (profile, tavern, hire, merchant, gear)
│   ├── configs/
│   │   ├── themes/                     # Dungeon theme configs (8 biomes)
│   │   ├── combat_config.json
│   │   ├── classes_config.json
│   │   ├── enemies_config.json
│   │   ├── skills_config.json
│   │   ├── items_config.json
│   │   ├── affixes_config.json         # Item affix definitions
│   │   ├── item_names_config.json      # Procedural item name parts
│   │   ├── sets_config.json            # Equipment set definitions & bonuses
│   │   ├── uniques_config.json         # Unique item definitions
│   │   ├── super_uniques_config.json   # Super unique monster definitions
│   │   ├── loot_tables.json
│   │   ├── merchant_config.json
│   │   ├── monster_rarity_config.json  # Monster rarity tiers, champion types, 15 affixes, spawn rules
│   │   ├── names_config.json
│   │   ├── maps/                      # 15 map definitions
│   │   │   ├── arena_classic.json
│   │   │   ├── open_arena.json
│   │   │   ├── open_arena_small.json
│   │   │   ├── open_arena_large.json
│   │   │   ├── maze.json
│   │   │   ├── maze_large.json
│   │   │   ├── islands.json
│   │   │   ├── islands_large.json
│   │   │   ├── dungeon_test.json
│   │   │   ├── open_catacombs.json
│   │   │   ├── training_room.json
│   │   │   ├── wave_arena.json
│   │   │   ├── test_xl.json
│   │   │   ├── wfc_dungeon.json
│   │   │   └── wfc_dungeon_6x6_test.json
│   │   ├── wfc-modules/               # WFC module library
│   │   │   └── library.json           # Canonical shared module library (49 modules, v2 format)
│   │   └── wfc-rulesets/              # WFC generation rulesets
│   ├── data/
│   │   └── players/                   # Persisted player profiles (JSON)
│   └── tests/                         # 60 test files, 2933 tests
│
├── client/                 # React frontend (Vite)
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   ├── electron/                  # Electron desktop wrapper
│   │   ├── main.cjs
│   │   └── preload.cjs
│   ├── public/
│   │   ├── spritesheet.png
│   │   ├── tilesheet.png
│   │   ├── skill-icons.png
│   │   ├── particle-effects.json
│   │   ├── particle-presets.json      # Index file → points to category files below
│   │   ├── audio-effects.json         # Audio effect trigger definitions
│   │   ├── audio/                     # Audio asset files
│   │   │   ├── buffs/
│   │   │   ├── combat/
│   │   │   ├── events/
│   │   │   ├── items/
│   │   │   ├── movement/
│   │   │   ├── music/
│   │   │   ├── skills/
│   │   │   └── ui/
│   │   └── particle-presets/          # Particle presets split into 8 category files
│   │       ├── combat.json            #   Combat presets (melee-hit, ranged-hit, etc.)
│   │       ├── skills.json            #   Skill presets (fire-blast, heal-pulse, etc.)
│   │       ├── buffs.json             #   Buff presets (buff-aura-*, stun-stars, etc.)
│   │       ├── projectiles.json       #   Projectile presets (arrow-trail, holy-head, etc.)
│   │       ├── portal.json            #   Portal presets (portal-swirl, portal-core-glow, etc.)
│   │       ├── ambient.json           #   Ambient presets (torch-flame, dust-motes, etc.)
│   │       ├── compound.json          #   Compound presets (war-cry-blast, faith-descend, etc.)
│   │       └── affixes.json           #   Monster affix presets
│   └── src/
│       ├── App.jsx                # Screen router (lobby → town → arena → postmatch)
│       ├── index.jsx
│       ├── components/            # UI components (organized by feature)
│       │   ├── Arena/             # Main game canvas container
│       │   ├── BottomBar/         # Skill bar, action buttons, tooltips
│       │   ├── CombatLog/         # Scrollable combat event log
│       │   ├── CombatMeter/       # Live combat stats panel + per-skill breakdown
│       │   ├── EnemyPanel/        # Targeted enemy info display
│       │   ├── HeaderBar/         # Turn counter, timer, HP, buffs
│       │   ├── HUD/               # Heads-up display overlay
│       │   ├── Inventory/         # Equipment slots + bag grid
│       │   ├── Lobby/             # Match creation & joining
│       │   ├── MinimapPanel/      # Minimap overlay panel
│       │   ├── PartyPanel/        # Party list, stances, multi-select
│       │   ├── PostMatch/         # Post-match results screen
│       │   ├── TownHub/           # Town hub (merchant, hiring hall, hero roster, bank)
│       │   ├── EscapeMenu/        # In-game escape/pause menu
│       │   ├── VolumeSettings/    # Audio volume controls
│       │   └── WaitingRoom/       # Pre-match waiting room
│       ├── canvas/                # Canvas rendering pipeline
│       │   ├── ArenaRenderer.js       # Hub — canvas setup, viewport, renderFrame()
│       │   ├── renderConstants.js     # TILE_SIZE, color tables, shape/name maps
│       │   ├── ThemeEngine.js          # Procedural grimdark theme renderer + tile cache
│       │   ├── minimapRenderer.js     # Minimap rendering
│       │   ├── PositionInterpolator.js # Smooth unit position interpolation
│       │   ├── dungeonRenderer.js     # Dungeon tiles (walls, doors, chests) + fog of war
│       │   ├── unitRenderer.js        # Unit drawing (sprites/shapes, stances, targets)
│       │   ├── overlayRenderer.js     # Highlights, hover paths, loot, damage floaters
│       │   ├── SpriteLoader.js        # Sprite sheet loading + drawing
│       │   ├── TileLoader.js          # Tile sheet loading + drawing
│       │   ├── pathfinding.js         # Client-side A* pathfinding
│       │   └── particles/             # Particle effects engine
│       │       ├── ParticleEngine.js
│       │       ├── ParticleManager.js
│       │       ├── ParticleRenderer.js
│       │       ├── Emitter.js
│       │       ├── Particle.js
│       │       ├── ParticleProjectile.js
│       │       └── MathUtils.js
│       ├── hooks/                 # Custom React hooks
│       │   ├── useWebSocket.js            # WebSocket connection management
│       │   ├── useHighlights.js           # Tile highlight computations
│       │   ├── useCanvasInput.js          # Canvas click, right-click, hover handlers
│       │   ├── useKeyboardShortcuts.js    # Keyboard shortcuts (Ctrl+A, F1-F4, etc.)
│       │   └── useWASDMovement.js         # WASD movement input
│       ├── audio/                 # Audio system
│       │   ├── AudioContext.jsx        # React audio context provider
│       │   ├── AudioManager.js         # Audio playback manager (SFX, music, categories)
│       │   ├── useAudio.js             # Audio hook for components
│       │   ├── soundMap.js             # Sound effect → asset mapping
│       │   └── index.js                # Audio module barrel export
│       ├── context/               # GameStateContext + domain sub-reducers
│       │   ├── GameStateContext.jsx    # Provider, hooks, initialState, combiner dispatch
│       │   └── reducers/
│       │       ├── lobbyReducer.js        # Lobby/pre-match actions
│       │       ├── combatReducer.js       # Match lifecycle, turns, queues
│       │       ├── partyReducer.js        # Party selection, stances, auto-target
│       │       ├── combatStatsReducer.js   # Combat meter stats accumulation
│       │       ├── townReducer.js         # Town hub, heroes, merchant, bank
│       │       └── inventoryReducer.js    # In-match inventory & equipment
│       ├── utils/                 # Shared utility functions
│       │   ├── skillUtils.js          # isInSkillRange() — shared skill range helper
│       │   └── itemUtils.js           # formatStatBonuses() — shared item display helper
│       └── styles/                # CSS (split from 7,197-line monolith → 29 partials)
│           ├── main.css               # Barrel file (29 @import statements)
│           ├── base/
│           │   ├── _variables.css     # CSS custom properties (:root)
│           │   ├── _reset.css         # Reset, scrollbar, body, .app, vignette
│           │   ├── _buttons.css       # Shared button styles (.grim-btn, etc.)
│           │   ├── _frames.css        # Decorative frame styles
│           │   ├── _forms.css         # Form element styles
│           │   └── _animations.css    # Keyframe animations
│           ├── layout/
│           │   ├── _app-header.css    # Game title bar
│           │   ├── _arena.css         # Arena grid + responsive viewport
│           │   └── _minimap.css       # Minimap overlay
│           ├── components/
│           │   ├── _lobby.css         # Lobby screens (username, match list, config, class select)
│           │   ├── _waiting-room.css  # Waiting room + AI badge
│           │   ├── _header-bar.css    # In-match header (turn counter, HP, buffs)
│           │   ├── _bottom-bar.css    # Action bar, skill slots, hotkeys, cooldowns
│           │   ├── _hud.css           # HUD overlay
│           │   ├── _combat-log.css    # Combat log
│           │   ├── _party-panel.css   # Party list, stances, multi-select
│           │   ├── _enemy-panel.css   # Targeted enemy info
│           │   ├── _inventory.css     # Inventory/loot UI + dungeon transfer
│           │   ├── _combat-meter.css  # Combat stats, meter bars, skill breakdown
│           │   ├── _overlays.css      # Match end, death banner, auto-target, action intent
│           │   ├── _volume-settings.css # Volume settings panel
│           │   └── _escape-menu.css   # Escape menu overlay
│           ├── town/
│           │   ├── _town-hub.css      # Town hub layout + browse matches
│           │   ├── _merchant.css      # Merchant buy/sell UI
│           │   ├── _hiring-hall.css   # Hiring hall
│           │   ├── _hero-roster.css   # Hero roster + detail panel
│           │   ├── _gear-management.css # Gear management (equip/unequip/compare)
│           │   └── _bank.css          # Bank / shared stash
│           └── screens/
│               └── _post-match.css    # Post-match results screen
│
├── tools/                  # Standalone dev tools
│   ├── generate_atlas.py   # Sprite atlas generation utility
│   ├── dungeon-wfc/        # WFC Dungeon Lab — procedural dungeon generator
│   ├── cave-automata/      # Cave Automata Lab — cellular automata cave generator
│   ├── module-decorator/   # Module Sprite Decorator — visual tile painting for WFC modules
│   ├── particle-lab/       # Particle Effects Lab — visual effect testing
│   ├── sprite-cataloger/   # Sprite Cataloger — sprite sheet browser
│   ├── theme-designer/     # Dungeon Theme Designer — procedural grimdark tile preview
│   ├── audio-workbench/    # Audio Workbench — sound testing, categorization & config editor
│   ├── item-forge/         # Item Forge — item/equipment creation, balancing & simulation
│   ├── enemy-forge/        # Enemy Forge — monster rarity, affixes, champion types, TTK simulation
│   ├── arena-analyst/      # Arena Analyst — match tracker, balance analysis & trend visualization
│   └── Thought-Mapper/     # Thought Mapper — planning tool
│
├── Assets/                 # Art assets (XCF source files, sprite sheets, maps, audio)
│   ├── Audio/
│   ├── Character Sheet/
│   ├── Maps/
│   ├── Sprites/
│   └── Walls and Objects/
│
└── README.md
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+

### One-Click Launch
```bash
# Start everything (backend + frontend)
start-game.bat
```

### Manual Setup

**Backend:**
```bash
cd server
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd client
npm install
npm run dev
```

The client runs at `http://localhost:5173` and proxies API/WS requests to the backend.

### Desktop App (Electron)
```bash
# Option 1: Use the batch file (starts everything)
start-electron.bat

# Option 2: Manual (backend must be running first)
cd client
npm run electron:dev
```

See [docs/Systems/electron-desktop-app.md](docs/Systems/electron-desktop-app.md) for full details, build instructions, and packaging.

### Dev Tools
```bash
start-dungeon-wfc.bat       # WFC Dungeon Lab
start-cave-automata.bat     # Cave Automata Lab
start-particle-lab.bat      # Particle Effects Lab
start-sprite-cataloger.bat  # Sprite Cataloger
start-module-decorator.bat  # Module Sprite Decorator
start-theme-designer.bat    # Dungeon Theme Designer
start-audio-workbench.bat   # Audio Workbench
start-item-forge.bat        # Item Forge
start-enemy-forge.bat       # Enemy Forge
```

## Features

| Feature | Description |
|---------|-------------|
| **FOV / Fog of War** | Server-side recursive shadowcasting; shared team vision (7-tile range) |
| **Combat System** | Melee + ranged attacks, LOS checks, cooldowns, armor, per-class stats |
| **6 Playable Classes** | Crusader, Confessor, Inquisitor, Ranger, Hexblade, Mage — unique stats, shapes, skills |
| **Skills & Spells** | 5 class skills (Heal, Double Strike, Power Shot, War Cry, Shadow Step) with buff system |
| **AI System** | A* pathfinding, stance-based behavior (follow/aggressive/defensive/hold), potion usage, retreat/kiting |
| **Dungeon Crawler** | Grimdark dungeons with rooms, doors, chests, enemy types, loot drops |
| **Loot & Items** | Equipment (weapon/armor/accessory), consumables, ground items, rarity system |
| **Hero System** | Persistent heroes, permadeath, name generation, stat variation |
| **Town Hub** | Merchant (buy/sell), Hiring Hall, Hero Roster, Bank, gear management |
| **Party Control** | Multi-select, group movement, formation pathfinding, stance control |
| **Auto-Target Pursuit** | Right-click to persistently chase + attack/skill enemies across turns |
| **Combat Meter** | Live damage/healing/kill stats with click-to-inspect per-skill breakdown, source type bars, and keyboard nav |
| **Match Types** | PvP Only, Solo PvE, Mixed (humans + AI) |
| **Team System** | Up to 4 teams (A, B, C, D), no friendly fire, shared team FOV |
| **Wave Arena** | 8 waves of escalating enemies for AI testing |
| **Particle Effects** | Damage, heal, buff, teleport, and death visual effects |
| **WFC Dungeons** | Procedural dungeon generation via Wave Function Collapse |
| **Module Decorator** | Visual sprite painting tool for WFC dungeon modules |
| **Cave Automata** | Organic cave/cavern generation via Cellular Automata |
| **Theme Designer** | Procedural grimdark dungeon tile preview tool (8 biomes) |
| **Audio Workbench** | Sound preview, A/B comparison, category management & config editor |
| **Item Forge** | Item/equipment creation, affix editing, set design, balance simulation & drop rate calculator |
| **Enemy Forge** | Monster rarity editing, affix tuning, champion types, floor roster viewer, TTK simulator, spawn preview, super uniques |
| **Monster Rarity** | D2-inspired Normal/Champion/Rare/Super Unique tiers, 5 champion types, 15 affixes, pack spawning, combat effects (auras, on-hit, on-death) |
| **Electron App** | Desktop wrapper with native window chrome |

## Maps

| Map | Size | Type | Description |
|-----|------|------|-------------|
| Open Arena Small | 12×12 | Arena | Compact open arena for 2-4 players |
| Arena Classic | 15×15 | Arena | Balanced mix with center cross |
| Open Arena | 15×15 | Arena | Wide open with scattered pillars |
| Maze | 15×15 | Arena | Tight corridors and dead ends |
| Islands | 15×15 | Arena | Clustered obstacle zones |
| Open Arena Large | 20×20 | Arena | Spacious open arena for 6-8 players |
| Maze Large | 20×20 | Arena | Brick-wall corridor maze, large scale |
| Islands Large | 20×20 | Arena | Scaled island clusters for large groups |
| Wave Arena | 20×20 | Arena | AI testing — 8 waves of escalating enemies |
| Test Map XL | 25×25 | Arena | Fortress theme — scalability testing |
| Dungeon Test | 20×20 | Dungeon | 5 rooms, doors, chests, enemy spawns |
| Open Catacombs | — | Dungeon | Catacomb-themed dungeon |
| Training Room | — | Dungeon | Practice environment |
| WFC Dungeon | — | Dungeon | Procedurally generated via WFC |

## Decisions Locked In

| Decision | Choice |
|----------|--------|
| Turn tick rate | 1 second (configurable) |
| Rendering | Canvas API |
| Map sizes | 12×12, 15×15, 20×20, 25×25 |
| FOV algorithm | Recursive shadowcasting (pure Python, server-side) |
| AI pathfinding | A* with Chebyshev heuristic |
| Auth | Username only |
| Bundler | Vite |
| Persistence | JSON file-based (server/data/players/) |
| Desktop | Electron |

## Documentation

### Phase Specs
- [Phase 1](docs/Phase%20Docs/phase1-design-document-updated.md) — Original scope & timeline
- [Phase 2](docs/Phase%20Docs/phase2-arena-plus-v2.md) — Arena Plus features, design & bug fix tracking
- [Phase 3](docs/Phase%20Docs/phase3-arena-refined.md) — Larger maps, spawn system, performance monitoring
- [Phase 4](docs/Phase%20Docs/phase4-grimdark-dungeon.md) — Grimdark dungeon crawler design
- [Phase 4 Implementation](docs/Phase%20Docs/phase4-implementation-plan.md) — Sub-phase breakdown (4A–4G)
- [Phase 5](docs/Phase%20Docs/phase5-qol-and-completion.md) — QoL improvements, merchant, portal scrolls, AI parties
- [Phase 5 Feature 7](docs/Phase%20Docs/phase5-feature7-gear-management.md) — Town gear management
- [Phase 6](docs/Phase%20Docs/phase6-skills-and-ui-overhaul.md) — Skills/spells system & dungeon UI overhaul
- [Phase 6E](docs/Phase%20Docs/phase6E-dungeon-gui-plan.md) — Dungeon GUI reorganization
- [Phase 7](docs/Phase%20Docs/phase7-party-movement-overhaul.md) — Party movement & AI overhaul
- [Phase 8](docs/Phase%20Docs/phase8-party-ai-combat-intelligence.md) — Party AI combat intelligence
- [Phase 8K](docs/Phase%20Docs/phase8K-ai-retreat-and-kiting.md) — AI retreat behavior & ranged kiting
- [Phase 9](docs/Phase%20Docs/phase9-particle-effects-lab.md) — Particle effects system
- [Phase 10](docs/Phase%20Docs/phase10-auto-target-pursuit.md) — Auto-target pursuit
- [Phase 10G](docs/Phase%20Docs/phase10G-skill-auto-target.md) — Skill & ability auto-target pursuit
- [Phase 11](docs/Phase%20Docs/phase11-class-identity.md) — Class identity design
- [Phase 11 Log](docs/Phase%20Docs/phase11-implementation-log.md) — Phase 11 implementation log
- [Phase 12](docs/Phase%20Docs/phase12-dungeon-run.md) — The Dungeon Run (multi-floor, extraction, CC, loot, audio)
- [Phase 12 Procedural](docs/Phase%20Docs/phase12-feature5-procedural-dungeon.md) — Procedural dungeon generation feature
- [Phase 13](docs/Phase%20Docs/phase13-path-forward.md) — Path Forward (cleanup, content depth, polish)
- [Phase 14](docs/Phase%20Docs/phase14-visual-feedback.md) — Visual Feedback & Combat Clarity
- [Phase 15](docs/Phase%20Docs/phase15-complete-experience.md) — Complete Experience
- [Phase 15 Menu](docs/Phase%20Docs/phase15-menu-overhaul.md) — Menu overhaul
- [Phase 16](docs/Phase%20Docs/phase16-item-equipment-overhaul.md) — Item & Equipment Overhaul (16A–16E complete)
- [Phase 17](docs/Phase%20Docs/phase17-mage-class.md) — Mage Class
- [Phase 18 Core](docs/Phase%20Docs/phase18-monster-rarity-core.md) — Monster Rarity & Affix System (18A–18D complete)
- [Phase 18 Content](docs/Phase%20Docs/phase18-monster-rarity-content.md) — Monster Rarity Content & Visuals (18F complete, 18G complete, 18I complete, 18E complete, 18H complete)
- [Phase 18J](docs/Phase%20Docs/phase18J-enemy-forge-skill-integration.md) — Enemy Forge Skill Integration
- [Phase 19](docs/Phase%20Docs/phase19-inventory-panel-overhaul.md) — Inventory/Stats Panel Overhaul (Batch 3 complete)
- [Phase 20](docs/Phase%20Docs/phase20-turn-resolver-split.md) — Turn Resolver File Split (all 6 phases complete)
- [Enemy HP Rebalance](docs/Phase%20Docs/enemy-hp-rebalance-and-identity.md) — Enemy HP rebalance & identity
- [Enemy Roster](docs/Phase%20Docs/enemy-roster-system.md) — Enemy roster system
- [Loot System](docs/Phase%20Docs/loot-system-overhaul.md) — Loot system overhaul
- [Party Control](docs/Phase%20Docs/party-control-system.md) — Party control system design
- [WFC Integration](docs/Phase%20Docs/wfc-in-game-integration-plan.md) — WFC in-game integration plan (Phase A complete — dungeon style templates, 51 tests; Phase B complete — batch generation, 33 tests; Phase C complete — shared module format, 38 tests)

### Architecture
- [CSS Split Plan](docs/css-split-plan.md) — Monolith CSS decomposition into 24 partials

### Systems & References
- [WebSocket Protocol](docs/websocket-protocol.md) — All message types and data shapes
- [Action & Intent System](docs/Systems/action-intent-system.md) — Action and intent system design
- [Combat System](docs/Systems/combat-system-overview.md) — Combat mechanics overview
- [Combat Meter](docs/Systems/combat-meter.md) — Live combat statistics panel with per-skill breakdown drill-in
- [Input & Targeting](docs/Systems/input-targeting-systems.md) — Input and targeting system design
- [Projectile Travel](docs/Systems/projectile-travel-system.md) — Ranged projectile travel system (Phase 14G)
- [Electron Desktop App](docs/Systems/electron-desktop-app.md) — Desktop app setup & packaging
- [Minimap System](docs/Systems/minimap.md) — Minimap panel with normal/expanded modes
- [Buff Particle Overhaul](docs/Systems/buff-particle-overhaul.md) — Buff particle effect redesign
- [Particle Visibility Lifecycle](docs/Systems/particle-visibility-lifecycle.md) — Particle visibility & lifecycle system
- [Audio Workbench](docs/Systems/audio-workbench.md) — Sound testing, categorization & config editor system
- [Enemy Forge](docs/Systems/enemy-forge.md) — Monster rarity editing, affix tuning, TTK simulation & spawn preview system
- [Affix System](docs/Systems/affix-system.md) — Item affix system design
- [Audio System](docs/Systems/audio-system.md) — Audio system architecture
- [Monster Rarity Visuals](docs/Systems/monster-rarity-visual-improvements.md) — Monster rarity visual improvements
- [Weapon Class Lock](docs/Systems/weapon-class-lock-system.md) — Weapon class lock system
- [Game Balance](docs/Game%20stats%20references/game-balance-reference.md) — Balance reference data
- [Current Phase](docs/Current%20Phase.md) — Full milestone tracker with test counts

### Tools
- [WFC Dungeon Lab](docs/Tools/wfc-dungeon-lab.md) — Procedural dungeon generator
- [Cave Automata Lab](docs/Tools/cave-automata-lab.md) — Cellular automata cave generator
- [Sprite Cataloger](docs/Tools/sprite-cataloger.md) — Sprite sheet browser
- [Module Sprite Decorator](docs/Tools/module-sprite-decorator.md) — Visual tile painting for WFC modules
- [Dungeon Theme Designer](docs/Tools/theme-designer.md) — Procedural grimdark tile rendering + preview
- [Audio Workbench](docs/Tools/audio-workbench.md) — Sound testing, categorization & config editor
- [Item Forge](docs/Tools/item-forge.md) — Item/equipment creation, balancing & simulation tool
- [Enemy Forge](docs/Tools/enemy-forge.md) — Monster rarity, affixes, champion types, TTK simulation & spawn preview
- [Arena Analyst](docs/Tools/arena-analyst.md) — Match tracker, balance analysis & trend visualization

## Test Suite

- **2933 tests** across 60 test files (0 failures)
- Full backward compatibility verified at every phase
- Coverage spans: combat, turn resolution, AI behavior, WebSocket protocol, dungeon mechanics, items/loot, hero persistence, skills, cooperative movement, stances, door pathfinding, wave spawner, auto-target, portal scroll, crowd control, Phase 12 skills, monster rarity (affix engine, spawn integration, combat effects, super uniques, loot integration), turn phase sub-module imports, and more

