# WFC In-Game Integration Plan

> **Goal**: Make in-game procedural dungeons match the quality and variety of the WFC Dungeon Tool output.

## Current State (as of March 2026)

Both systems now share identical foundations:

| Component | Tool (JS) | Server (Python) | Synced? |
|---|---|---|---|
| Module size | 8×8 | 8×8 | ✅ |
| Preset modules | 49 modules | 49 modules | ✅ |
| WFC engine | `wfc.js` | `wfc_engine.py` (port of JS) | ✅ |
| Socket types | 4 patterns (Wall/Standard/Narrow/Interior) | Same 4 patterns | ✅ |
| RNG | mulberry32 | mulberry32 | ✅ |
| Connectivity | flood-fill + A* stitching | flood-fill + A* stitching | ✅ |
| Room decorator | `roomDecorator.js` | `room_decorator.py` (port of JS) | ✅ |
| Map exporter | `exportMap.js` | `map_exporter.py` (richer — rarity, rosters, super uniques) | ✅ |

**The core algorithms are identical.** Given the same seed + grid size, both systems produce the same structural layout. The gap is in **pre-generation tuning** — the tool has features that make its dungeons dramatically more varied and interesting.

---

## Phase A: Dungeon Style Templates (Weight Overrides)

**Priority**: HIGH — biggest visual impact, lowest effort  
**Estimated effort**: Small  
**Files**: `server/app/core/wfc/dungeon_styles.py` (new), `server/app/core/wfc/dungeon_generator.py`

### What the tool does that the server doesn't

The tool has 5 **Dungeon Style Templates** that multiply module weights by purpose before running WFC:

| Style | Corridor | Empty | Enemy | Boss | Loot | Spawn | Feel |
|---|---|---|---|---|---|---|---|
| Balanced | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | Default |
| Dense Catacomb | 2.5 | 0.4 | 2.0 | 0.3 | 0.3 | 1.0 | Tight, enemy-heavy |
| Open Ruins | 0.6 | 2.5 | 0.8 | 0.5 | 1.5 | 1.0 | Spacious, exploration |
| Boss Rush | 1.8 | 0.5 | 1.5 | 2.0 | 0.3 | 1.0 | Direct, lethal |
| Treasure Vault | 1.0 | 1.0 | 1.2 | 0.2 | 3.0 | 1.0 | Loot-heavy, guarded |

Each style also sets **decorator defaults** (enemy density, loot density, empty room chance, etc.) that change how rooms get populated after WFC.

### Implementation plan

1. **Create `dungeon_styles.py`** with a `DUNGEON_STYLES` dict matching the tool's 5 templates. Each entry has:
   - `weight_overrides`: dict of `purpose → multiplier`
   - `decorator_overrides`: dict of decorator setting overrides
   - `description`: human-readable description

2. **Add `dungeon_style` field to `FloorConfig`** (default: `"balanced"`).

3. **In `generate_dungeon_floor()`**, before passing modules to `run_wfc()`:
   - Look up the style's `weight_overrides`
   - Multiply each module's `weight` by the override for its `purpose`
   - Merge the style's `decorator_overrides` into the decorator settings

4. **Auto-select style based on floor depth + seed**:
   - Early floors (1-2): weighted toward Balanced or Open Ruins (introductory)
   - Mid floors (3-5): mix of all styles
   - Deep floors (6-8): weighted toward Dense Catacomb or Boss Rush
   - Can also be influenced by `match.theme_id` for thematic consistency

5. **Allow manual override** via `FloorConfig.dungeon_style` for testing or future UI selection.

### Acceptance criteria
- [x] Server generates visibly different dungeon layouts depending on style
- [x] Same seed + same style = identical output (deterministic)
- [x] Floor progression naturally varies dungeon feel
- [x] Decorator settings adjust with style (e.g. Dense Catacomb has 70% enemy density vs 40% default)

---

## Phase B: Batch Generation (Best-of-N)

**Priority**: MEDIUM — quality improvement, small effort  
**Estimated effort**: Small  
**Files**: `server/app/core/wfc/dungeon_generator.py`

### What the tool does

The tool can generate N dungeons with different seeds and **rank them** by quality metrics:
- Floor ratio (more open space = better)
- Spawn point coverage
- Connectivity (0 corridors carved = naturally connected = better)

Then it picks the best one.

### Implementation plan

1. **Add `batch_size` to `FloorConfig`** (default: `3`).

2. **In `generate_dungeon_floor()`**, when `batch_size > 1`:
   - Run WFC `batch_size` times with seeds `floor_seed + i * 7919`
   - Score each result:
     - Floor ratio (% open tiles) — higher is better
     - Has spawn points? (+20 bonus)
     - Corridors carved == 0? (+10 bonus, means naturally connected)
   - Pick the highest-scoring result
   - Continue with decoration + export on the winner

3. **Performance budget**: WFC on a 4×4 grid takes ~10-30ms. Batch of 5 = ~50-150ms. Well within acceptable server latency.

### Acceptance criteria
- [x] Batch generation produces measurably better dungeons (higher floor ratio, fewer carved corridors)
- [x] `batch_size=1` behaves identically to current behavior (no regression)
- [x] Generation time stays under 500ms for batch_size=5 on a 5×5 grid

---

## Phase C: Shared Module Format (Tool → Server Pipeline)

**Priority**: LOW — architectural improvement for long-term  
**Estimated effort**: Medium  
**Files**: `server/app/core/wfc/presets.py`, `tools/dungeon-wfc/` (export feature)

### The problem

Currently, modules are defined **twice** — once in `presets.js` (tool) and once in `presets.py` (server). When modules change, both files must be updated manually. This is error-prone and was the root cause of the 6×6 vs 8×8 mismatch.

### Implementation plan

1. **Define a canonical JSON module format**:
   ```json
   {
     "version": 2,
     "module_size": 8,
     "modules": [
       {
         "id": "preset_solid",
         "name": "Solid Wall",
         "purpose": "empty",
         "contentRole": "structural",
         "width": 8,
         "height": 8,
         "weight": 3.0,
         "allowRotation": false,
         "tiles": [["W","W",...], ...],
         "spawnSlots": [],
         "maxEnemies": 0,
         "maxChests": 0,
         "canBeBoss": false,
         "canBeSpawn": false
       }
     ]
   }
   ```

2. **Add "Export Library to Server" button** in the WFC tool that writes to `server/configs/wfc-modules/library.json`.

3. **Refactor `presets.py`** to load from `library.json` instead of hardcoded Python dicts. Keep a Python fallback for when the JSON file doesn't exist.

4. **Refactor `presets.js`** to load from the same JSON at tool startup (or bundle it as a static import).

5. **Single source of truth**: edit modules visually in the tool → export → server picks them up automatically.

### Acceptance criteria
- [x] One JSON file defines all modules (`server/configs/wfc-modules/library.json`)
- [x] Tool can export its library to the server config directory ("Export Library to Server" button + API endpoint)
- [x] Server loads modules from JSON and generates identical dungeons (38 tests)
- [x] Fallback to hardcoded presets if JSON is missing
- [x] Tool can import the JSON back (round-trip — import/download buttons in ExportPanel)

---

## Phase D: Per-Theme Module Sets

**Priority**: LOW — content expansion, depends on Phase C  
**Estimated effort**: Medium-Large (mostly content authoring)  
**Files**: `server/configs/wfc-modules/`, `server/app/core/wfc/presets.py`, `server/app/core/wfc/dungeon_generator.py`

### The vision

Different dungeon themes use **different module libraries** to create visually and structurally distinct experiences:

| Theme | Module Character | Example |
|---|---|---|
| `bleeding_catacombs` | Narrow corridors, cramped rooms, many dead ends | More narrow-socket modules, smaller rooms |
| `hollowed_cathedral` | Grand open spaces, pillared halls, few corridors | More grand/interior modules, fewer narrow modules |
| `iron_depths` | Industrial, symmetric, grid-like | More cross/T-junction modules, regular layouts |
| `drowned_sanctum` | Organic, winding, asymmetric | More L-turns, alcoves, irregular rooms |

### Implementation plan

1. **Create themed module sets** using the WFC Dungeon Tool:
   - Start from the base 49 modules
   - Adjust weights and add/remove modules per theme
   - Export each as `server/configs/wfc-modules/<theme>.json`

2. **Update `presets.py`** to accept an optional `theme` parameter:
   ```python
   def get_preset_modules(theme: str | None = None) -> list[dict]:
       if theme and (path := f"configs/wfc-modules/{theme}.json") exists:
           return load_from_json(path)
       return default_presets
   ```

3. **Wire into `dungeon_generator.py`**: pass `match.theme_id` through to module selection.

4. **Fallback**: if a theme's module file doesn't exist, use the default library.

### Acceptance criteria
- [ ] At least 2 themes have distinct module sets
- [ ] Dungeons visually differ based on theme
- [ ] Missing theme files gracefully fall back to defaults
- [ ] Tool can load and edit any theme's module set

---

## Implementation Order

```
Phase A ──→ Phase B ──→ Phase C ──→ Phase D
(styles)    (batch)     (shared     (themed
                        format)     modules)
```

- **Phase A** is the immediate next step — it's the single biggest lever for dungeon variety
- **Phase B** is a quick follow-up that catches bad seeds
- **Phase C** is complete — canonical JSON library, export/import pipeline, 38 tests
- **Phase D** is the content expansion that leverages all prior phases

---

## Key Files Reference

### Tool (JS)
| File | Purpose |
|---|---|
| `tools/dungeon-wfc/src/engine/moduleUtils.js` | MODULE_SIZE, rotation, socket derivation |
| `tools/dungeon-wfc/src/engine/presets.js` | 49 builtin preset modules + SIZE_PRESETS (fallback) |
| `tools/dungeon-wfc/src/engine/wfc.js` | Core WFC solver |
| `tools/dungeon-wfc/src/engine/connectivity.js` | Region detection + corridor stitching |
| `tools/dungeon-wfc/src/engine/roomDecorator.js` | Post-gen content placement |
| `tools/dungeon-wfc/src/utils/exportMap.js` | Export to game JSON format |
| `tools/dungeon-wfc/src/utils/moduleLibrary.js` | **Phase C**: Canonical JSON library export/import helpers |
| `tools/dungeon-wfc/src/components/GeneratorPanel.jsx` | DUNGEON_TEMPLATES + UI controls |
| `tools/dungeon-wfc/src/components/ExportPanel.jsx` | **Phase C**: Export/Import Library buttons + map export |

### Server (Python)
| File | Purpose |
|---|---|
| `server/app/core/wfc/module_utils.py` | MODULE_SIZE, rotation, socket derivation |
| `server/app/core/wfc/presets.py` | **Phase C**: JSON library loader + hardcoded builtin fallback |
| `server/app/core/wfc/wfc_engine.py` | Core WFC solver |
| `server/app/core/wfc/connectivity.py` | Region detection + corridor stitching |
| `server/app/core/wfc/room_decorator.py` | Post-gen content placement |
| `server/app/core/wfc/map_exporter.py` | Export to game map dict (+ rarity, rosters) |
| `server/app/core/wfc/dungeon_generator.py` | Orchestrator: FloorConfig → full pipeline |
| `server/app/core/match_manager.py` | Triggers generation at match start (line 1271) |
| `server/app/routes/maps.py` | **Phase C**: `/api/maps/wfc-modules/library` upload/download endpoints |

### Shared Data
| File | Purpose |
|---|---|
| `server/configs/wfc-modules/library.json` | **Phase C**: Canonical module library (single source of truth, 49 modules) |

### Dead Weight (can be cleaned up)
| File | Note |
|---|---|
| `server/configs/wfc-modules/*.json` (excluding library.json) | 13 legacy 5×5 module files — unused by either system |
