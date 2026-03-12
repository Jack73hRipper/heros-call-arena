# Project Audit — February 24, 2026

Full architecture audit, file size analysis, and project health review.

## Project Size Snapshot

| Category | Lines | Files |
|----------|------:|------:|
| Server app (Python) | 16,316 | 49 |
| Server tests (Python) | 22,487 | 45 |
| Client JS/JSX | 13,890 | 56 |
| Client CSS | 8,347 | 2 |
| **Total** | **61,040** | **152** |
| Test count | 1,641 tests | 45 test files |

---

## Part 1: README.md Accuracy Audit

The README is well-structured and mostly accurate. The following discrepancies were found:

### 1A — Stale / Incorrect Numbers

| README Claim | Actual | Fix Needed |
|---|---|---|
| Header: "1629+ tests passing" | **1,641 tests** | Update |
| Body: "42 test files, 1428+ tests" | **45 test files, 1,641 tests** | Update |
| Theme configs: "5 biomes" | **8 theme JSONs** | Update to "8 biomes" |
| Phase status: "Phase 10G complete" | Phase 12 (12A–12C complete, 12D+ planned) | Update status line |

### 1B — Missing from README Structure Tree

| What's Missing | Location | Notes |
|---|---|---|
| `server/app/core/wfc/` subdirectory | 7 Python modules (wfc_engine, dungeon_generator, room_decorator, connectivity, map_exporter, module_utils, presets) | Entire WFC engine directory is absent from README |
| `server/app/core/spawn.py` description | Listed in tree but no description annotation | Minor — add `# Spawn point logic` |

### 1C — Missing Phase Docs (exist on disk, not in README)

| File | Topic |
|---|---|
| `enemy-hp-rebalance-and-identity.md` | Enemy HP rebalance design |
| `enemy-roster-system.md` | Enemy roster system design |
| `phase12-feature5-procedural-dungeon.md` | Phase 12 procedural dungeon feature |

### 1D — Missing Systems Docs (exist on disk, not in README)

| File | Topic |
|---|---|
| `action-intent-system.md` | Action/intent system design |
| `combat-meter.md` | Combat meter system doc |

### 1E — Achieve Folder Mismatch

The README claims `docs/Achieve/` contains:
- `phase2-arena-plus.md`
- `refactoring-plan.md`

**Reality:** The Achieve folder is **empty**. These files were either deleted or never committed. The README listing should be removed or the files restored.

### 1F — Minor Omissions

- `tools/generate_atlas.py` exists at tools root but isn't listed in README
- Component sub-files (BottomBar: 4 files, CombatMeter: 9 files, TownHub: 7 files) are not individually listed — acceptable at README level but worth noting

---

## Part 2: File Size Analysis — Refactoring Candidates

### Severity Tiers

**CRITICAL (1000+ lines, multiple concerns):**

| File | Lines | Functions | Issue |
|---|---:|---:|---|
| `server/app/core/match_manager.py` | 1,388 | 51 | **God Module** — 7+ distinct responsibilities: match lifecycle, AI spawning, class/hero selection, action queues, FOV cache, payload serialization, lobby features, dungeon management. Uses 8 module-level dict stores as a poor man's database. |
| `server/app/core/skills.py` | 1,447 | 39 | 4 separate concerns packed in one file: config loading, skill lookups, buff state queries, and 17 different skill effect resolvers (~1,100 lines of resolve_* functions alone). |
| `client/src/styles/main.css` | 6,199 | — | **Monolithic stylesheet.** Every component's styles in one file with 32+ major sections. The single largest file in the project by far. |

**HIGH (700–1000 lines):**

| File | Lines | Functions | Issue |
|---|---:|---:|---|
| `server/app/core/turn_resolver.py` | 1,388 | 19 | Large but well-structured pipeline. Each function handles one phase. Lower priority because the design pattern is clean — but nearing the threshold where navigation becomes painful. |
| `server/app/core/ai_stances.py` | 935 | 12 | Already refactored. Good module focus. Main issue is individual function length (150–220 lines of branching logic). |
| `server/app/core/ai_behavior.py` | 916 | 13 | Already refactored. Cohesive (all enemy AI). Same function-length concern. |
| `server/app/core/ai_skills.py` | 908 | 16 | Focused on AI skill decisions per role. Functions are long but domain-coherent. |
| `server/app/services/message_handlers.py` | 730 | ~24 | 24 individual WS handlers + dispatch router. Could split into handler groups but it's manageable. |
| `server/app/routes/town.py` | 733 | — | All town REST endpoints in one file. Could split merchant/hiring/bank into separate route files. |
| `client/src/canvas/pathfinding.js` | 717 | 8 | All pathfinding-related. Acceptable cohesion. |

**MODERATE (500–700 lines):**

| File | Lines | Notes |
|---|---:|---|
| `client/src/components/BottomBar/BottomBar.jsx` | 667 | Single 694-line React component with inline skill targeting, range checking, potion, and hotkey logic. |
| `client/src/canvas/ThemeEngine.js` | 594 | Procedural tile rendering. Focused. |
| `client/src/App.jsx` | 587 | `PostMatchScreen` (215 lines) and `handleMessage` (~150 lines switch/case) are inline. |
| `client/src/components/TownHub/HeroDetailPanel.jsx` | 587 | Stats, equipment, bag grid, transfer modal — all one component. |
| `server/app/core/hero_manager.py` | 556 | Hero lifecycle. Moderately large but focused. |
| `server/app/services/tick_loop.py` | 540 | Game loop. Critical path, focused. |
| `client/src/canvas/unitRenderer.js` | 533 | Unit drawing. Focused. |
| `client/src/components/Arena/Arena.jsx` | 512 | Main game canvas container. |

### Recommended Refactoring Plan (Priority Order)

#### Priority 1: `match_manager.py` → Split into 4 modules
This is the most dangerous file in the codebase. 51 functions, 7+ concerns, and growing.

| New Module | Extract From | Est. Lines |
|---|---|---|
| `dungeon_manager.py` | Floor progression, stair logic, procedural generation, dungeon state, enemy spawning | ~500 |
| `match_payloads.py` | `get_match_start_payload`, `get_players_snapshot`, `get_lobby_players_payload`, etc. | ~250 |
| `match_actions.py` | `queue_action`, `pop_next_actions`, `get_and_clear_actions`, queue management | ~120 |
| `lobby_manager.py` | Chat, config updates, AI spawn, class selection | ~200 |
| `match_manager.py` (remaining) | Match lifecycle, FOV cache, core orchestration | ~300 |

#### Priority 2: `skills.py` → Split into 3 modules

| New Module | Extract From | Est. Lines |
|---|---|---|
| `skills_config.py` | `load_skills_config`, `get_skill`, `get_all_skills`, `get_class_skills`, `can_use_skill` | ~100 |
| `skills_buffs.py` | `tick_buffs`, `get_melee_buff_multiplier`, `is_stunned`, `is_slowed`, `get_effective_armor`, etc. | ~200 |
| `skills_effects.py` | All 17 `resolve_*` functions | ~1,100 |

#### Priority 3: `main.css` → Split into component stylesheets

| New File | Sections to Extract |
|---|---|
| `styles/variables.css` | CSS custom properties (L4–55) |
| `styles/lobby.css` | Lobby + waiting room styles |
| `styles/arena.css` | Arena, canvas, viewport styles |
| `styles/action-bar.css` | Bottom bar, skill bar, tooltips |
| `styles/town-hub.css` | Town hub, merchant, hiring hall, hero roster |
| `styles/combat-meter.css` | Combat meter panel and views |
| `styles/inventory.css` | Equipment slots, bag grid |
| `styles/party-panel.css` | Party list, stances |
| `styles/common.css` | Buttons, scrollbars, animations, shared utilities |

#### Priority 4: Client component extractions

| Action | From | Extract |
|---|---|---|
| PostMatchScreen → own file | `App.jsx` | `components/PostMatch/PostMatchScreen.jsx` |
| useMessageHandler hook | `App.jsx` | `hooks/useMessageHandler.js` |
| Skill targeting logic | `BottomBar.jsx` | `hooks/useSkillTargeting.js` or sub-components |
| Transfer modal | `HeroDetailPanel.jsx` | `components/TownHub/TransferModal.jsx` |

---

## Part 3: Other Project Health Observations

### 3A — Stale / Orphan Files (Cleanup Targets)

| File | Issue |
|---|---|
| `server/test_full_output.txt` (163 KB) | Stale test output dump |
| `server/test_output.txt` (5 KB) | Stale test output dump |
| `server/test_output2.txt` (76 KB) | Stale test output dump |
| `server/package-lock.json` | Empty Node lockfile in the Python server directory — clearly stale |
| `client/public/desktop.ini` | Windows system file, should be in .gitignore |

### 3B — .gitignore Gaps

Current .gitignore is reasonable but missing:
- `desktop.ini` (Windows shell metadata)
- `test_output*.txt` or `server/test_*.txt` patterns
- `*.bak` files (the _archive folders handle this, but worth a catch-all)

### 3C — Archive Strategy

The `_archive/` folders (client/src, server/app/core, server/app/services) contain `.bak` snapshots from the previous refactoring. These serve as rollback references.

The `docs/Achieve/` folder is empty despite the README listing 2 files. Either:
- The files were lost/deleted and should be restored from version control
- The README entry should be removed

### 3D — Current Phase.md is Outdated

The "Test Suite" section at the bottom of `Current Phase.md` claims **"1428+ tests passing"** — this hasn't been updated since the Wave Arena phase. The actual count is **1,641**. The detailed per-phase compatibility notes are thorough and valuable but stop at the Combat Meter phase.

### 3E — Phase Status Progression

The README header says Phase 10G is the latest complete phase, but the project has progressed significantly:
- Phase 11 (Class Identity) — design doc exists, status unclear from Current Phase.md
- Phase 12A (Complete Crusader & Ranger Skill Kits) — ✅ Complete
- Phase 12B (CC / Status Effects: Stun, Slow, Taunt, Evasion) — ✅ Complete
- Phase 12C (Portal Scroll — Extraction Mechanic) — ✅ Complete
- Phase 12D–12H — Planned

### 3F — Test File Growth

The largest test files are also getting big:
| File | Lines |
|---|---:|
| test_auto_target.py | 1,258 |
| test_ai_retreat.py | 1,193 |
| test_ai_integration.py | 1,059 |
| test_hero_persistence.py | 813 |

Not urgent, but worth watching. Test files over 1,000 lines become hard to navigate.

### 3G — Architecture Strengths (What's Working Well)

- **Clean separation of AI modules**: `ai_behavior`, `ai_stances`, `ai_skills`, `ai_memory`, `ai_patrol`, `ai_pathfinding` — this decomposition from the previous refactor is holding up well
- **WFC engine** (`server/app/core/wfc/`): 7 focused modules with clear responsibilities
- **Canvas rendering pipeline**: Well-organized (ArenaRenderer hub, separate dungeon/unit/overlay renderers)
- **Particle system**: Clean separation (Engine, Manager, Renderer, Emitter, Particle, MathUtils)
- **React state management**: GameStateContext + 6 domain-specific reducers is a solid pattern
- **Test discipline**: 1,641 tests with 0 failures, backward compat verified at every phase

---

## Summary — Action Items

| # | Priority | Action | Effort | Status |
|---|---|---|---|---|
| 1 | **Now** | Update README (numbers, missing docs, wfc/ directory, phase status, Achieve fix) | Small | ✅ **Done** |
| 2 | **Now** | Delete stale files (test outputs, server/package-lock.json) | Trivial | 🔲 Pending |
| 3 | **Now** | Update .gitignore (desktop.ini, test outputs, *.bak) | Trivial | 🔲 Pending |
| 4 | **Now** | Update Current Phase.md test count to 1,641 | Trivial | 🔲 Pending |
| 5 | **Next** | Refactor `match_manager.py` — extract dungeon_manager, match_payloads, match_actions, lobby_manager | Medium | 🔲 Pending |
| 6 | **Next** | Refactor `skills.py` — extract skills_config, skills_buffs, skills_effects | Medium | 🔲 Pending |
| 7 | **Next** | Split `main.css` into per-component stylesheets | Medium | 🔲 Pending |
| 8 | **Later** | Extract PostMatchScreen from App.jsx | Small | 🔲 Pending |
| 9 | **Later** | Split BottomBar.jsx into sub-components | Small | 🔲 Pending |
| 10 | **Later** | Consider splitting town.py routes | Small | 🔲 Pending |

---

## Change Log

### Session 1 — February 24, 2026

**README.md updated** — 13 edits applied in a single pass:

1. **Header status line**: "Phase 10G complete · 1629+ tests" → "Phase 12C complete (Portal Scroll — Extraction Mechanic) · 1641+ tests passing"
2. **Structure tree — Phase Docs**: Added 3 missing entries: `phase12-feature5-procedural-dungeon.md`, `enemy-hp-rebalance-and-identity.md`, `enemy-roster-system.md`
3. **Structure tree — Systems docs**: Added 2 missing entries: `action-intent-system.md`, `combat-meter.md`
4. **Structure tree — Achieve folder**: Removed phantom file listings (`phase2-arena-plus.md`, `refactoring-plan.md`), marked as "currently empty"
5. **Structure tree — server/app/core/wfc/**: Added entire WFC engine subdirectory with all 7 modules and descriptions
6. **Structure tree — themes count**: "5 biomes" → "8 biomes"
7. **Structure tree — test count**: "42 test files, 1428+ tests" → "45 test files, 1641+ tests"
8. **Structure tree — tools**: Added `generate_atlas.py` entry
9. **Features table**: Theme Designer description updated from "5 biomes" → "8 biomes"
10. **Documentation — Phase Specs links**: Added 4 missing links (Phase 11 Log, Phase 12 Procedural, Enemy HP Rebalance, Enemy Roster)
11. **Documentation — Systems links**: Added Action & Intent System link
12. **Test Suite section**: Updated count from "1629+ across 42 files" → "1641+ across 45 files"; added portal scroll, crowd control, Phase 12 skills to coverage list
