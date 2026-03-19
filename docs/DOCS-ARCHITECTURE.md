# Documentation Architecture

> **Purpose:** Master index of all project documentation. Agents and contributors should start here to find any document quickly.

## Quick Navigation

| Need to find... | Go to |
|-----------------|-------|
| What phase are we on? | [Current Phase.md](Current%20Phase.md) |
| How a system works | [Systems/](#systems--technical-references) |
| How to use a dev tool | [Tools/](#tools--development-tool-guides) |
| Design spec for a feature | [Phase Docs/](#phase-docs--design-specs) |
| Class stats & skills | [class-overview.md](class-overview.md) |
| WebSocket message types | [websocket-protocol.md](websocket-protocol.md) |
| Balance data | [Game stats references/](#game-stats-references) |
| Bug history | [bug-log.md](bug-log.md) |
| Recent changes | [changelog.md](changelog.md) / [pending-changes.md](pending-changes.md) |
| Project health | [project-audit-march-2026.md](project-audit-march-2026.md) |
| Publishing / launcher | [publish-workflow.md](publish-workflow.md) / [launcher-pipeline.md](launcher-pipeline.md) |
| Adding a new class | [new-class-implementation-template.md](new-class-implementation-template.md) |

---

## Folder Structure

```
docs/
├── DOCS-ARCHITECTURE.md          ← You are here
│
├── Current Phase.md               # Real-time phase tracker (all milestones & test counts)
├── changelog.md                   # Permanent versioned changelog
├── pending-changes.md             # WIP changes staged before changelog publish
├── bug-log.md                     # Bug tracking with root causes & fixes
├── class-overview.md              # Source of truth: all 11 playable classes
├── websocket-protocol.md          # All WS message types and data shapes
├── project-audit-march-2026.md    # Current project health audit
├── new-class-implementation-template.md  # Protocol for adding new classes
├── publish-workflow.md            # Agent reference: publishing pipeline
├── launcher-pipeline.md           # Launcher versioning & update flow
│
├── Phase Docs/                    # Design specs per feature phase (57 files)
│   ├── phase1–phase27*.md         #   Numbered phase design documents
│   ├── *-balance-changelog.md     #   Per-class balance changelogs
│   └── *-system-overhaul.md       #   System redesign specs
│
├── Systems/                       # Technical reference docs (16 files)
│   ├── combat-system-overview.md  #   Master combat reference
│   ├── action-intent-system.md    #   Action queueing pipeline
│   ├── audio-system.md            #   Audio engine architecture
│   └── ...                        #   (see detailed listing below)
│
├── Tools/                         # Dev tool user guides (9 files)
│   ├── wfc-dungeon-lab.md         #   WFC Dungeon Lab
│   ├── item-forge.md              #   Item Forge
│   └── ...                        #   (see detailed listing below)
│
├── Game stats references/         # Balance & stat data
│   └── game-balance-reference.md  #   Class tuning & balance history
│
└── Achieve/                       # Archived docs (completed/superseded)
    ├── project-audit-feb-2026.md
    ├── project-audit-file-splitting.md
    ├── css-split-plan.md
    └── tile-props-overhaul.md
```

---

## Top-Level Docs (10 files)

| File | Purpose | Status |
|------|---------|--------|
| [Current Phase.md](Current%20Phase.md) | Real-time status of all active/completed phases | Active |
| [changelog.md](changelog.md) | Permanent versioned changelog | Active |
| [pending-changes.md](pending-changes.md) | WIP staging area before changelog publish | Active |
| [bug-log.md](bug-log.md) | Bug tracking with root causes & fixes | Reference |
| [class-overview.md](class-overview.md) | **Source of truth** for all 11 playable classes (stats, roles, skills) | Reference |
| [websocket-protocol.md](websocket-protocol.md) | All WebSocket message types and data shapes | Reference |
| [project-audit-march-2026.md](project-audit-march-2026.md) | Current project health audit (8/10 score) | Snapshot |
| [new-class-implementation-template.md](new-class-implementation-template.md) | Step-by-step protocol for implementing new classes | Template |
| [publish-workflow.md](publish-workflow.md) | Publishing steps, versioning, build pipeline | Reference |
| [launcher-pipeline.md](launcher-pipeline.md) | Launcher versioning, GitHub infrastructure, update manifest | Reference |

---

## Phase Docs — Design Specs

57 files organized by feature phase. Each phase doc contains the design spec, implementation plan, and completion status for a major feature.

### Foundation & Core (Phases 1–5)

| Phase | File | Scope |
|-------|------|-------|
| 1 | [phase1-design-document-updated.md](Phase%20Docs/phase1-design-document-updated.md) | Original 10-section build plan |
| 2 | [phase2-arena-plus-v2.md](Phase%20Docs/phase2-arena-plus-v2.md) | Arena Plus features & bug fixes |
| 3 | [phase3-arena-refined.md](Phase%20Docs/phase3-arena-refined.md) | Larger maps, spawn system, performance |
| 4 | [phase4-grimdark-dungeon.md](Phase%20Docs/phase4-grimdark-dungeon.md) | Grimdark dungeon crawler design |
| 4 | [phase4-implementation-plan.md](Phase%20Docs/phase4-implementation-plan.md) | Sub-phase breakdown (4A–4G) |
| 5 | [phase5-qol-and-completion.md](Phase%20Docs/phase5-qol-and-completion.md) | QoL, merchant, portal scrolls, AI parties |
| 5.7 | [phase5-feature7-gear-management.md](Phase%20Docs/phase5-feature7-gear-management.md) | Town gear management |

### Combat & Mechanics (Phases 6–11)

| Phase | File | Scope |
|-------|------|-------|
| 6 | [phase6-skills-and-ui-overhaul.md](Phase%20Docs/phase6-skills-and-ui-overhaul.md) | Skills/spells system & dungeon UI |
| 6E | [phase6E-dungeon-gui-plan.md](Phase%20Docs/phase6E-dungeon-gui-plan.md) | Dungeon GUI reorganization |
| 7 | [phase7-party-movement-overhaul.md](Phase%20Docs/phase7-party-movement-overhaul.md) | Party movement & AI overhaul |
| 8 | [phase8-party-ai-combat-intelligence.md](Phase%20Docs/phase8-party-ai-combat-intelligence.md) | Party AI combat intelligence |
| 8K | [phase8K-ai-retreat-and-kiting.md](Phase%20Docs/phase8K-ai-retreat-and-kiting.md) | AI retreat & ranged kiting |
| 9 | [phase9-particle-effects-lab.md](Phase%20Docs/phase9-particle-effects-lab.md) | Particle effects system |
| 10 | [phase10-auto-target-pursuit.md](Phase%20Docs/phase10-auto-target-pursuit.md) | Auto-target pursuit |
| 10G | [phase10G-skill-auto-target.md](Phase%20Docs/phase10G-skill-auto-target.md) | Skill auto-target |
| 11 | [phase11-class-identity.md](Phase%20Docs/phase11-class-identity.md) | Class identity design |
| 11 | [phase11-implementation-log.md](Phase%20Docs/phase11-implementation-log.md) | Implementation log |

### Dungeon & Content (Phases 12–15)

| Phase | File | Scope |
|-------|------|-------|
| 12 | [phase12-dungeon-run.md](Phase%20Docs/phase12-dungeon-run.md) | Multi-floor dungeon run, extraction, CC, loot, audio |
| 12.5 | [phase12-feature5-procedural-dungeon.md](Phase%20Docs/phase12-feature5-procedural-dungeon.md) | Procedural dungeon generation feature |
| 13 | [phase13-path-forward.md](Phase%20Docs/phase13-path-forward.md) | Cleanup, content depth, polish |
| 14 | [phase14-visual-feedback.md](Phase%20Docs/phase14-visual-feedback.md) | Visual feedback & combat clarity |
| 15 | [phase15-complete-experience.md](Phase%20Docs/phase15-complete-experience.md) | Complete experience design |
| 15 | [phase15-menu-overhaul.md](Phase%20Docs/phase15-menu-overhaul.md) | Menu overhaul |

### Items & Monsters (Phases 16–20)

| Phase | File | Scope |
|-------|------|-------|
| 16 | [phase16-item-equipment-overhaul.md](Phase%20Docs/phase16-item-equipment-overhaul.md) | Item & equipment overhaul (16A–16E) |
| 17 | [phase17-mage-class.md](Phase%20Docs/phase17-mage-class.md) | Mage class |
| 18 | [phase18-monster-rarity-core.md](Phase%20Docs/phase18-monster-rarity-core.md) | Monster rarity & affix system (18A–18D) |
| 18 | [phase18-monster-rarity-content.md](Phase%20Docs/phase18-monster-rarity-content.md) | Monster rarity content & visuals |
| 18J | [phase18J-enemy-forge-skill-integration.md](Phase%20Docs/phase18J-enemy-forge-skill-integration.md) | Enemy Forge skill integration |
| 19 | [phase19-inventory-panel-overhaul.md](Phase%20Docs/phase19-inventory-panel-overhaul.md) | Inventory/stats panel overhaul |
| 20 | [phase20-turn-resolver-split.md](Phase%20Docs/phase20-turn-resolver-split.md) | Turn resolver file split |

### New Classes (Phases 21–26)

| Phase | File | Scope |
|-------|------|-------|
| 21 | [phase21-bard-class.md](Phase%20Docs/phase21-bard-class.md) | Bard class |
| 21 | [phase21-dungeon-visual-variety.md](Phase%20Docs/phase21-dungeon-visual-variety.md) | Dungeon visual variety |
| 22 | [phase22-blood-knight-class.md](Phase%20Docs/phase22-blood-knight-class.md) | Blood Knight class |
| 23 | [phase23-plague-doctor-class.md](Phase%20Docs/phase23-plague-doctor-class.md) | Plague Doctor class |
| 24 | [phase24-tooltip-revamp.md](Phase%20Docs/phase24-tooltip-revamp.md) | Tooltip revamp |
| 25 | [phase25-revenant-class.md](Phase%20Docs/phase25-revenant-class.md) | Revenant class |
| 26 | [phase26-shaman-class.md](Phase%20Docs/phase26-shaman-class.md) | Shaman class |

### Late-Stage Features (Phase 27+)

| Phase | File | Scope |
|-------|------|-------|
| 27 | [phase27-pvpve-ai-team-spawn-log.md](Phase%20Docs/phase27-pvpve-ai-team-spawn-log.md) | PvPvE AI team spawn log |
| 27 | [phase27-pvpve-dungeon-map.md](Phase%20Docs/phase27-pvpve-dungeon-map.md) | PvPvE dungeon map |

### Supporting Phase Docs

These are system-level design specs and feature plans that emerged alongside numbered phases:

| File | Scope |
|------|-------|
| [enemy-hp-rebalance-and-identity.md](Phase%20Docs/enemy-hp-rebalance-and-identity.md) | Enemy HP rebalance & identity |
| [enemy-roster-system.md](Phase%20Docs/enemy-roster-system.md) | Enemy roster system |
| [loot-system-overhaul.md](Phase%20Docs/loot-system-overhaul.md) | Loot system overhaul |
| [party-control-system.md](Phase%20Docs/party-control-system.md) | Party control system |
| [stance-system-overhaul.md](Phase%20Docs/stance-system-overhaul.md) | Stance system overhaul |
| [spawn-distribution-overhaul.md](Phase%20Docs/spawn-distribution-overhaul.md) | Spawn distribution overhaul |
| [friendly-swap-movement.md](Phase%20Docs/friendly-swap-movement.md) | Friendly swap movement |
| [match-lobby-redesign.md](Phase%20Docs/match-lobby-redesign.md) | Match lobby redesign |
| [nameplate-declutter-system.md](Phase%20Docs/nameplate-declutter-system.md) | Nameplate declutter system |
| [playtest-distribution-system.md](Phase%20Docs/playtest-distribution-system.md) | Playtest distribution system |
| [project-cleanup-plan.md](Phase%20Docs/project-cleanup-plan.md) | Project cleanup plan |
| [launcher-implementation-plan.md](Phase%20Docs/launcher-implementation-plan.md) | Launcher implementation plan |
| [wfc-in-game-integration-plan.md](Phase%20Docs/wfc-in-game-integration-plan.md) | WFC in-game integration plan |
| [wfc-dungeon-tile-size-update.md](Phase%20Docs/wfc-dungeon-tile-size-update.md) | WFC dungeon tile size update |

### Balance Changelogs

Per-class balance tuning history, stored alongside phase docs:

| File | Class |
|------|-------|
| [bard-balance-changelog.md](Phase%20Docs/bard-balance-changelog.md) | Bard |
| [hexblade-balance-changelog.md](Phase%20Docs/hexblade-balance-changelog.md) | Hexblade |
| [inquisitor-balance-changelog.md](Phase%20Docs/inquisitor-balance-changelog.md) | Inquisitor |
| [shaman-balance-changelog.md](Phase%20Docs/shaman-balance-changelog.md) | Shaman |

---

## Systems — Technical References

16 files documenting how core game systems work. These are the **current-state architecture docs** — use Phase Docs for historical design context.

### Combat & Gameplay

| File | System |
|------|--------|
| [combat-system-overview.md](Systems/combat-system-overview.md) | **Master reference** — game loop, turn resolution, auto-target, skills |
| [action-intent-system.md](Systems/action-intent-system.md) | Player action queueing pipeline |
| [input-targeting-systems.md](Systems/input-targeting-systems.md) | Click targeting & pathfinding |
| [projectile-travel-system.md](Systems/projectile-travel-system.md) | Ranged projectile arc/travel animations |
| [combat-meter.md](Systems/combat-meter.md) | Live damage/healing/kill stats panel |

### Items & Monsters

| File | System |
|------|--------|
| [affix-system.md](Systems/affix-system.md) | Item prefix & suffix attribute system |
| [weapon-class-lock-system.md](Systems/weapon-class-lock-system.md) | Weapon category restrictions per class |
| [monster-rarity-visual-improvements.md](Systems/monster-rarity-visual-improvements.md) | Rarity glow/tint/prefix visual system |
| [enemy-forge.md](Systems/enemy-forge.md) | Enemy Forge system architecture |

### Visual & Audio

| File | System |
|------|--------|
| [particle-visibility-lifecycle.md](Systems/particle-visibility-lifecycle.md) | Particle emission, culling, lifecycle |
| [buff-particle-overhaul.md](Systems/buff-particle-overhaul.md) | Buff/debuff particle attachment system |
| [minimap.md](Systems/minimap.md) | Minimap rendering & room state visualization |
| [audio-system.md](Systems/audio-system.md) | Audio engine architecture (BGM, SFX, spatial) |
| [audio-workbench.md](Systems/audio-workbench.md) | Audio Workbench system design |

### Infrastructure

| File | System |
|------|--------|
| [electron-desktop-app.md](Systems/electron-desktop-app.md) | Electron desktop client setup & packaging |
| [batch-pvp-simulator.md](Systems/batch-pvp-simulator.md) | CLI tool for running N PvP matches for balance testing |

---

## Tools — Development Tool Guides

9 files documenting standalone dev tools (source code lives in `/tools/`). These explain **how to use** each tool.

| File | Tool | Launch |
|------|------|--------|
| [wfc-dungeon-lab.md](Tools/wfc-dungeon-lab.md) | WFC Dungeon Lab — procedural dungeon generator | `start-dungeon-wfc.bat` |
| [cave-automata-lab.md](Tools/cave-automata-lab.md) | Cave Automata Lab — cellular automata caves | `start-cave-automata.bat` |
| [sprite-cataloger.md](Tools/sprite-cataloger.md) | Sprite Cataloger — sprite sheet browser | `start-sprite-cataloger.bat` |
| [module-sprite-decorator.md](Tools/module-sprite-decorator.md) | Module Sprite Decorator — visual tile painting | `start-module-decorator.bat` |
| [theme-designer.md](Tools/theme-designer.md) | Theme Designer — grimdark tile preview | `start-theme-designer.bat` |
| [audio-workbench.md](Tools/audio-workbench.md) | Audio Workbench — sound testing & config editor | `start-audio-workbench.bat` |
| [item-forge.md](Tools/item-forge.md) | Item Forge — item creation & balance simulation | `start-item-forge.bat` |
| [enemy-forge.md](Tools/enemy-forge.md) | Enemy Forge — monster rarity & affix tuning | `start-enemy-forge.bat` |
| [arena-analyst.md](Tools/arena-analyst.md) | Arena Analyst — match tracker & balance analysis | `start-arena-analyst.bat` |

---

## Game Stats References

| File | Purpose |
|------|---------|
| [game-balance-reference.md](Game%20stats%20references/game-balance-reference.md) | Class tuning data, DPS benchmarks, balance history |

---

## Archive (Achieve/)

Completed or superseded documents moved here for historical reference:

| File | Original Purpose |
|------|-----------------|
| [project-audit-feb-2026.md](Achieve/project-audit-feb-2026.md) | Feb 2026 architecture audit snapshot |
| [project-audit-file-splitting.md](Achieve/project-audit-file-splitting.md) | File splitting playbook (Phase 1 complete) |
| [css-split-plan.md](Achieve/css-split-plan.md) | CSS monolith decomposition (completed) |
| [tile-props-overhaul.md](Achieve/tile-props-overhaul.md) | Tile prop placement redesign (completed) |

---

## Conventions

- **Phase docs** are named `phaseN-description.md` (e.g., `phase21-bard-class.md`)
- **Sub-phase docs** use a letter suffix (e.g., `phase8K-ai-retreat-and-kiting.md`)
- **Balance changelogs** are named `classname-balance-changelog.md`
- **System docs** describe current-state architecture; phase docs describe the design/implementation plan
- **Tool docs** match the tool folder name in `/tools/`
- **Completed/superseded docs** go in `Achieve/`
- **Current Phase.md** is the single source of truth for project status
- **class-overview.md** is the single source of truth for class definitions

## For Agents

When searching for documentation:
1. **Start here** — this file maps the entire docs tree
2. **Current status** → [Current Phase.md](Current%20Phase.md)
3. **How something works** → check [Systems/](#systems--technical-references) first, then [Phase Docs/](#phase-docs--design-specs) for historical context
4. **Adding a feature** → find the relevant phase doc for design context, then the system doc for current architecture
5. **Balance/tuning** → [class-overview.md](class-overview.md) for stats, [Game stats references/](Game%20stats%20references/) for history
6. **Tool usage** → [Tools/](#tools--development-tool-guides) for how-to, `/tools/` directory for source code
