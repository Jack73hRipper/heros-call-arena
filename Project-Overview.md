# Arena Prototype

Turn-based multiplayer combat arena & grimdark dungeon crawler — MMO Project.

**Current status:** 3987 tests passing

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
├── start-pvpve-analyst.bat # Launch PvPvE Analyst tool
├── start-launcher.bat      # Launch game launcher (dev mode)
├── start-publish.bat       # Build + publish game update
├── start-batch-pvp.bat     # Run batch PvP simulations
├── start-batch-pvpve.bat   # Run batch PvPvE simulations
├── start-pvpve-agent.bat   # Launch PvPvE agent
├── start-server-online.bat # Start online server
├── start-test-manifest.bat # Run test manifest
├── stop-server-online.bat  # Stop online server
├── copy-sprites.bat        # Copy sprite assets
│
├── docs/                   # Project documentation
│   ├── DOCS-ARCHITECTURE.md        # ★ Master index — start here to find any doc
│   ├── Current Phase.md            # Phase tracker — all milestones & test counts
│   ├── changelog.md                # Permanent versioned changelog
│   ├── class-overview.md           # Source of truth: all 11 playable classes
│   ├── bug-log.md                  # Bug tracking log
│   ├── websocket-protocol.md       # All WS message types and data shapes
│   ├── project-audit-march-2026.md # Current project health audit
│   ├── ai-hero-dungeon-behavior-audit.md  # AI hero behavior analysis
│   ├── ai-hero-stalling-analysis.md       # AI stalling diagnosis
│   ├── known-test-failures.md             # Known test failure tracking
│   ├── launcher-pipeline.md               # Launcher build pipeline docs
│   ├── new-class-implementation-template.md # Template for adding new classes
│   ├── pending-changes.md                 # Pending change tracking
│   ├── publish-workflow.md                # Publish workflow documentation
│   ├── pvp-batch-analysis-2026-04-02.md   # PvP batch analysis results
│   ├── Phase Docs/                 # Design specs per phase (68 files)
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
│   │   ├── phase21-armor-affinity-and-tooltip-overhaul.md
│   │   ├── phase21-bard-class.md
│   │   ├── phase21-dungeon-visual-variety.md
│   │   ├── phase21G-party-tooltip-upgrades.md
│   │   ├── phase22-blood-knight-class.md
│   │   ├── phase23-plague-doctor-class.md
│   │   ├── phase24-tooltip-revamp.md
│   │   ├── phase25-revenant-class.md
│   │   ├── phase25-revenant-rework.md
│   │   ├── phase26-shaman-class.md
│   │   ├── phase27-pvpve-ai-team-spawn-log.md
│   │   ├── phase27-pvpve-dungeon-map.md
│   │   ├── phase28-enemy-ai-equipment.md
│   │   ├── phase28-hero-equipment-qol.md
│   │   ├── phase-render-performance.md
│   │   ├── phase-strategic-exploration.md
│   │   ├── enemy-hp-rebalance-and-identity.md
│   │   ├── enemy-roster-system.md
│   │   ├── loot-system-overhaul.md
│   │   ├── party-control-system.md
│   │   ├── wfc-in-game-integration-plan.md
│   │   ├── bard-balance-changelog.md
│   │   ├── hexblade-balance-changelog.md
│   │   ├── inquisitor-balance-changelog.md
│   │   ├── shaman-balance-changelog.md
│   │   ├── friendly-swap-movement.md
│   │   ├── launcher-implementation-plan.md
│   │   ├── loot-rarity-rebalance-proposal.md
│   │   ├── match-lobby-redesign.md
│   │   ├── match-manager-split-plan.md
│   │   ├── nameplate-declutter-system.md
│   │   ├── playtest-distribution-system.md
│   │   ├── progression-systems-brainstorm.md
│   │   ├── project-cleanup-plan.md
│   │   ├── pvpve-dungeon-preview-plan.md
│   │   ├── spawn-distribution-overhaul.md
│   │   ├── stance-system-overhaul.md
│   │   └── wfc-dungeon-tile-size-update.md
│   ├── Systems/                    # System design docs
│   │   ├── action-intent-system.md
│   │   ├── affix-system.md
│   │   ├── audio-system.md
│   │   ├── audio-workbench.md
│   │   ├── batch-pvp-simulator.md
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
│   │   ├── arena-analyst.md
│   │   ├── dev-overlay.md
│   │   └── pvpve-analyst.md
│   ├── Game stats references/
│   │   └── game-balance-reference.md
│   └── Achieve/                    # Archived docs (completed/superseded)
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
│   │   │   ├── match_store.py         # Shared state dicts (single source of truth for all match data)
│   │   │   ├── action_queue.py        # Action queue CRUD (queue, pop, clear, remove)
│   │   │   ├── fov_manager.py         # FOV cache + dev mode accessors
│   │   │   ├── match_payloads.py      # WS payload builders (match_start, player_joined, snapshots)
│   │   │   ├── lobby_config.py        # Lobby chat, config updates, class selection
│   │   │   ├── loadout_generator.py   # Enemy + hero equipment generation
│   │   │   ├── dungeon_manager.py     # Dungeon lifecycle, enemy spawning, floor advancement
│   │   │   ├── pvpve_manager.py       # PVPVE match flow: team distribution, dungeon gen, PVE spawning
│   │   │   ├── map_loader.py          # JSON map loading + spawn points
│   │   │   ├── fov.py                 # Recursive shadowcasting + LOS
│   │   │   ├── skills.py              # Skills config loader + validation
│   │   │   ├── skill_effects/         # Skill effect handlers (split by category)
│   │   │   │   ├── buff.py                # Buff skill effects
│   │   │   │   ├── damage.py              # Damage skill effects
│   │   │   │   ├── debuff.py              # Debuff skill effects
│   │   │   │   ├── heal.py                # Heal skill effects
│   │   │   │   ├── movement.py            # Movement skill effects
│   │   │   │   ├── summon.py              # Summon skill effects
│   │   │   │   ├── utility.py             # Utility skill effects
│   │   │   │   └── _helpers.py            # Shared skill effect helpers
│   │   │   ├── loot.py                # Loot generation (roll_enemy_loot, roll_chest_loot, rarity-scaled drops)
│   │   │   ├── spawn.py               # Spawn point logic
│   │   │   ├── ai_behavior.py         # AI decision hub (dispatches to modules below) + teleporter auto-cast
│   │   │   ├── ai_pathfinding.py      # A* pathfinding, neighbor/heuristic helpers, ghostly phase-through
│   │   │   ├── ai_skills.py           # Skill decision logic for all AI skill types
│   │   │   ├── ai_stances.py          # Stance-based AI (follow, aggressive, defensive, hold)
│   │   │   ├── ai_memory.py           # Enemy memory, target tracking, ally reinforcement
│   │   │   ├── ai_patrol.py           # Patrol waypoints & random movement
│   │   │   ├── ai_exploration.py      # AI dungeon exploration behavior
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
│   │   │       ├── door_placer.py         # Door placement logic for room boundaries
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
│   │   ├── themes/                     # Dungeon theme configs (11 biomes)
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
│   │   ├── maps/                      # 16 map definitions
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
│   │   │   ├── the_crucible.json
│   │   │   ├── training_room.json
│   │   │   ├── wave_arena.json
│   │   │   ├── test_xl.json
│   │   │   ├── wfc_dungeon.json
│   │   │   └── wfc_dungeon_6x6_test.json
│   │   ├── wfc-modules/               # WFC module library
│   │   │   └── library.json           # Canonical shared module library (49 modules, v2 format)
│   │   └── wfc-rulesets/              # WFC generation rulesets
│   ├── data/
│   │   ├── players/                   # Persisted player profiles (JSON)
│   │   └── match_history/             # Match history records
│   └── tests/                         # 101 test files, 3987 tests
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
│       │   ├── ActionBar/         # Skill bar, action buttons, hotkeys, cooldowns
│       │   ├── Arena/             # Main game canvas container
│       │   ├── CombatLog/         # Scrollable combat event log
│       │   ├── CombatMeter/       # Live combat stats panel + per-skill breakdown
│       │   ├── DevOverlay/        # Developer debug overlay
│       │   ├── EnemyPanel/        # Targeted enemy info display
│       │   ├── EscapeMenu/        # In-game escape/pause menu
│       │   ├── HeaderBar/         # Turn counter, timer, HP, buffs
│       │   ├── HUD/               # Heads-up display overlay
│       │   ├── Intro/             # Game intro/splash screen
│       │   ├── Inventory/         # Equipment slots + bag grid
│       │   ├── Lobby/             # Match creation & joining
│       │   ├── MatchLobby/        # In-match lobby / team setup
│       │   ├── MinimapPanel/      # Minimap overlay panel
│       │   ├── PartyPanel/        # Party list, stances, multi-select
│       │   ├── PlayerVitals/      # Player vitals display
│       │   ├── PostMatch/         # Post-match results screen
│       │   ├── TownHub/           # Town hub (merchant, hiring hall, hero roster, bank)
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
│       │   ├── chestRenderer.js       # Chest rendering
│       │   ├── devRenderer.js         # Developer debug rendering
│       │   ├── PerfTracker.js         # Performance tracking overlay
│       │   ├── PropLighting.js        # Prop-based dynamic lighting (torches, braziers)
│       │   ├── RoomOverlays.js        # Room overlay rendering
│       │   ├── TileProps.js           # Tile prop placement and rendering
│       │   ├── WaterAnimation.js      # Water tile animation
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
│       │   ├── useWASDMovement.js         # WASD movement input
│       │   └── useDevOverlay.js           # Dev overlay toggle and state
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
│       │   ├── itemUtils.js           # formatStatBonuses() — shared item display helper
│       │   ├── chestUtils.js          # Chest interaction utilities
│       │   ├── combatLogBuilder.js    # Combat log message formatting
│       │   ├── fetchWithRetry.js      # HTTP fetch with retry logic
│       │   └── serverUrl.js           # Server URL configuration
│       └── styles/                # CSS (split into partials by feature)
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
│           │   ├── _action-bar.css    # Action bar, skill slots, hotkeys, cooldowns
│           │   ├── _lobby.css         # Lobby screens (username, match list, config, class select)
│           │   ├── _match-lobby.css   # Match lobby UI
│           │   ├── _waiting-room.css  # Waiting room + AI badge
│           │   ├── _header-bar.css    # In-match header (turn counter, HP, buffs)
│           │   ├── _hud.css           # HUD overlay
│           │   ├── _combat-log.css    # Combat log
│           │   ├── _party-panel.css   # Party list, stances, multi-select
│           │   ├── _enemy-panel.css   # Targeted enemy info
│           │   ├── _inventory.css     # Inventory/loot UI + dungeon transfer
│           │   ├── _combat-meter.css  # Combat stats, meter bars, skill breakdown
│           │   ├── _overlays.css      # Match end, death banner, auto-target, action intent
│           │   ├── _player-vitals.css # Player vitals display
│           │   ├── _dev-overlay.css   # Developer overlay styles
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
│               ├── _intro.css         # Intro/splash screen
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
│   ├── pvpve-analyst/      # PvPvE Analyst — PvPvE match analysis & visualization
│   └── Thought-Mapper/     # Thought Mapper — planning tool
│
├── Assets/                 # Art assets (XCF source files, sprite sheets, maps, audio)
│   ├── Audio/
│   ├── Character Sheet/
│   ├── Maps/
│   ├── Sprites/
│   └── Walls and Objects/
│
├── scripts/                # Build & publish scripts
│   ├── arena-server.spec       # PyInstaller spec for server packaging
│   ├── build-game-package.bat  # Build game distribution package
│   ├── bump-version.bat        # Version bump utility
│   ├── publish-config.json     # Publish configuration
│   ├── publish-update.bat      # Publish game update
│   └── write-patch-notes.bat   # Generate patch notes
│
├── build/                  # Build artifacts & packaging
│   ├── patch-notes.md          # Current patch notes
│   ├── electron/               # Electron build output
│   ├── gh-pages-temp/          # GitHub Pages staging
│   ├── launcher/               # Launcher build output
│   ├── publish/                # Published release artifacts
│   └── pyinstaller/            # PyInstaller build output
│
├── launcher/               # Electron game launcher
│   ├── index.html
│   ├── main.js
│   ├── package.json
│   ├── preload.js
│   ├── renderer.js
│   ├── styles.css
│   ├── assets/
│   ├── lib/
│   └── test-manifest/
│
├── GITHUB FRONT PAGE.md    # GitHub README
└── Project-Overview.md
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
start-arena-analyst.bat     # Arena Analyst
start-pvpve-analyst.bat     # PvPvE Analyst
```

## Features

| Feature | Description |
|---------|-------------|
| **FOV / Fog of War** | Server-side recursive shadowcasting; shared team vision (7-tile range) |
| **Combat System** | Melee + ranged attacks, LOS checks, cooldowns, armor, per-class stats |
| **11 Playable Classes** | Crusader, Confessor, Inquisitor, Ranger, Hexblade, Mage, Bard, Blood Knight, Plague Doctor, Revenant, Shaman — unique stats, skills, identity |
| **Skills & Spells** | 40+ skills across all classes including heals, buffs, AoE, DoTs, summons, auras, and crowd control |
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
| **Theme Designer** | Procedural grimdark dungeon tile preview tool (11 biomes) |
| **Audio Workbench** | Sound preview, A/B comparison, category management & config editor |
| **Item Forge** | Item/equipment creation, affix editing, set design, balance simulation & drop rate calculator |
| **Enemy Forge** | Monster rarity editing, affix tuning, champion types, floor roster viewer, TTK simulator, spawn preview, super uniques |
| **Monster Rarity** | D2-inspired Normal/Champion/Rare/Super Unique tiers, 5 champion types, 15 affixes, pack spawning, combat effects (auras, on-hit, on-death) |
| **Electron App** | Desktop wrapper with native window chrome |
| **PvPvE Mode** | Mixed PvP and PvE in dungeon environments with AI teams |
| **Batch PvP/PvPvE** | Automated match simulation for balance testing |

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
| The Crucible | — | Arena | Challenge arena map |

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

> **📖 Full documentation map:** [docs/DOCS-ARCHITECTURE.md](docs/DOCS-ARCHITECTURE.md) — Master index of all project documentation. Agents and contributors should start there to navigate the docs tree.

### Key References
- [Current Phase](docs/Current%20Phase.md) — Full milestone tracker with test counts
- [Class Overview](docs/class-overview.md) — Source of truth for all 11 playable classes
- [WebSocket Protocol](docs/websocket-protocol.md) — All message types and data shapes
- [Project Health Audit](docs/project-audit-march-2026.md) — Current architecture health assessment

### Phase Specs (57 docs)
Design specs per feature phase — see [DOCS-ARCHITECTURE.md § Phase Docs](docs/DOCS-ARCHITECTURE.md#phase-docs--design-specs) for the full indexed list.

Highlights:
- [Phase 1](docs/Phase%20Docs/phase1-design-document-updated.md) — Original scope & timeline
- [Phase 4](docs/Phase%20Docs/phase4-grimdark-dungeon.md) — Grimdark dungeon crawler design
- [Phase 12](docs/Phase%20Docs/phase12-dungeon-run.md) — The Dungeon Run (multi-floor, extraction, CC, loot, audio)
- [Phase 16](docs/Phase%20Docs/phase16-item-equipment-overhaul.md) — Item & Equipment Overhaul
- [Phase 18 Core](docs/Phase%20Docs/phase18-monster-rarity-core.md) — Monster Rarity & Affix System
- [Phase 20](docs/Phase%20Docs/phase20-turn-resolver-split.md) — Turn Resolver File Split
- [Phase 21–26](docs/Phase%20Docs/phase21-bard-class.md) — New classes (Bard, Blood Knight, Plague Doctor, Revenant, Shaman)
- [Phase 27](docs/Phase%20Docs/phase27-pvpve-dungeon-map.md) — PvPvE Dungeon

### Systems & References (16 docs)
Technical reference docs for current-state architecture — see [DOCS-ARCHITECTURE.md § Systems](docs/DOCS-ARCHITECTURE.md#systems--technical-references) for the full categorized list.

- [Combat System](docs/Systems/combat-system-overview.md) — Master combat reference
- [Action & Intent](docs/Systems/action-intent-system.md) — Action queueing pipeline
- [Audio System](docs/Systems/audio-system.md) — Audio engine architecture
- [Electron Desktop App](docs/Systems/electron-desktop-app.md) — Desktop app setup & packaging
- [Affix System](docs/Systems/affix-system.md) — Item affix system design
- [Game Balance](docs/Game%20stats%20references/game-balance-reference.md) — Balance reference data

### Tools (9 docs)
Dev tool user guides — see [DOCS-ARCHITECTURE.md § Tools](docs/DOCS-ARCHITECTURE.md#tools--development-tool-guides) for the full list with launch commands.

- [WFC Dungeon Lab](docs/Tools/wfc-dungeon-lab.md) — Procedural dungeon generator
- [Item Forge](docs/Tools/item-forge.md) — Item/equipment creation, balancing & simulation
- [Enemy Forge](docs/Tools/enemy-forge.md) — Monster rarity, affixes, champion types, TTK simulation
- [Arena Analyst](docs/Tools/arena-analyst.md) — Match tracker, balance analysis & trend visualization

### Workflows
- [Publish Workflow](docs/publish-workflow.md) — Publishing steps, versioning, build pipeline
- [Launcher Pipeline](docs/launcher-pipeline.md) — Launcher versioning & update manifest flow
- [New Class Template](docs/new-class-implementation-template.md) — Step-by-step protocol for implementing new classes

## Test Suite

- **2933 tests** across 60 test files (0 failures)
- Full backward compatibility verified at every phase
- Coverage spans: combat, turn resolution, AI behavior, WebSocket protocol, dungeon mechanics, items/loot, hero persistence, skills, cooperative movement, stances, door pathfinding, wave spawner, auto-target, portal scroll, crowd control, Phase 12 skills, monster rarity (affix engine, spawn integration, combat effects, super uniques, loot integration), turn phase sub-module imports, and more

