# File Splitting Playbook

**Date:** March 1, 2026  
**Purpose:** Step-by-step phases for splitting oversized files. Each phase is **self-contained** — an AI agent only needs to read the single phase it is executing, not the entire document.

---

## Overview & Phase Map

| Phase | Target File | Action | Effort | Status |
|-------|-------------|--------|--------|--------|
| **Phase 1** | `client/public/particle-presets.json` (94.6 KB, 75 presets) | Split into 7 category files + index loader | Medium | **Complete** (March 1, 2026) |
| **Phase 2** | `server/app/core/skills.py` (65.2 KB, 1,451 lines) | Extract effect handlers → `skill_effects.py` | Medium | Not started |
| **Phase 3** | `server/app/services/message_handlers.py` (32.4 KB, 732 lines) | Split into domain-specific handler modules | Low-Medium | Not started |

**Watch-list (no action now):**
- `turn_resolver.py` (60.4 KB) — split if it exceeds ~1,800 lines
- `match_manager.py` (59.9 KB) — split if it exceeds ~1,600 lines
- `ParticleManager.js` (32.4 KB) — extract projectile travel if >1,000 lines

**Files excluded from analysis:** `package-lock.json` (auto-generated), atlas JSONs (asset data), generated map JSONs, test files (mirror their modules), documentation `.md` files.

---
---

## PHASE 1 — Split Particle Presets

> **Goal:** Break the monolithic `client/public/particle-presets.json` (94.6 KB, 5,122 lines, 75 presets) into 7 category files and update the loader.

### Phase 1 Context

- The file is a flat JSON array of preset objects. Each preset has a `name` (string) and `tags` (array of strings).
- `ParticleManager.init()` in `client/src/canvas/particles/ParticleManager.js` (~line 93) does `fetch('/particle-presets.json')`, parses the JSON array, and calls `this.engine.loadPresets(presets)`.
- `particle-effects.json` (separate file, 6 KB) is the **effect mapping** — it references preset names but is NOT being split.
- The Particle Lab tool (`tools/particle-lab/`) can export to `particle-presets.json` — that export will need awareness of the new structure in a future update, but is **not** in scope for this phase.

### Phase 1, Step 1 — Create category files

Create the folder `client/public/particle-presets/` and create 7 JSON files. Each file is a **JSON array** of preset objects (same schema as the original).

Sort each preset from the current `particle-presets.json` into a category file by matching preset names:

| File | Preset names to include |
|------|------------------------|
| `combat.json` | `melee-hit`, `ranged-hit`, `critical-hit`, `death-burst`, `blood-splatter`, `block` |
| `skills.json` | `fire-blast`, `ice-shard`, `poison-cloud`, `dark-bolt`, `holy-smite`, `heal-pulse`, `power-shot-impact`, `double-slash`, `ward-barrier`, `divine-pulse`, `shield-of-faith-aura`, `prayer-motes`, `wither-curse`, `exorcism-flare`, `taunt-shockwave`, `shield-bash-impact`, `holy-ground-ring`, `bulwark-fortify`, `volley-rain`, `evasion-blur`, `crippling-shot-impact`, `soul-reap-rend`, `venom-gaze-bolt` |
| `buffs.json` | `buff-aura`, `buff-aura-war-cry`, `buff-aura-armor`, `buff-aura-ward`, `buff-aura-evasion`, `buff-aura-hot`, `buff-aura-taunt`, `buff-aura-bulwark`, `stun-stars`, `slow-frost` |
| `projectiles.json` | `arrow-trail`, `holy-bolt-trail`, `dark-bolt-trail`, `power-shot-trail`, `crip-shot-trail`, `rebuke-trail`, `exorcism-trail`, `soul-reap-trail`, `wither-trail`, `venom-trail`, `arrow-head`, `power-shot-head`, `ice-arrow-head`, `holy-head`, `dark-head`, `venom-head` |
| `portal.json` | `portal-swirl`, `portal-ground-ring`, `portal-core-glow`, `portal-rising-sparks`, `portal-channel-swirl`, `portal-open-flash` |
| `ambient.json` | `torch-flame`, `dust-motes`, `loot-sparkle`, `level-up`, `Random Effect` |
| `compound.json` | `war-cry-blast`, `war-cry-shockwave`, `faith-descend`, `faith-flash`, `bulwark-slam`, `bulwark-dust`, `evasion-streak`, `prayer-blessing`, `prayer-ground-glow` |

**Important:** If any preset name from the original file is not listed above, place it in the category that best matches its `tags`. Every single preset must end up in exactly one file. **No preset may be lost.**

### Phase 1, Step 2 — Replace the root file with an index

Replace `client/public/particle-presets.json` with a small index object:

```json
{
  "version": 1,
  "files": [
    "particle-presets/combat.json",
    "particle-presets/skills.json",
    "particle-presets/buffs.json",
    "particle-presets/projectiles.json",
    "particle-presets/portal.json",
    "particle-presets/ambient.json",
    "particle-presets/compound.json"
  ]
}
```

### Phase 1, Step 3 — Update `ParticleManager.init()`

Edit `client/src/canvas/particles/ParticleManager.js`. In the `init()` method:

1. Fetch `/particle-presets.json` as before.
2. Detect the new format: if the response is an **object** with a `files` array (instead of a raw array), treat it as the index.
3. Fetch all files listed in `files` in parallel using `Promise.all`.
4. Concatenate the resulting arrays into one flat preset array.
5. Pass the merged array to `this.engine.loadPresets(presets)` — same as before.
6. **Backward compat:** If the fetched JSON is already a plain array (old format), load it directly as before.

**Pseudocode:**
```js
const presetsRes = await fetch(`/particle-presets.json${cacheBust}`);
if (presetsRes.ok) {
  const data = await presetsRes.json();
  let presets;
  if (Array.isArray(data)) {
    // Legacy: single flat array
    presets = data;
  } else if (data.files) {
    // New: index file pointing to category files
    const fetches = data.files.map(f => fetch(`/${f}${cacheBust}`).then(r => r.json()));
    const arrays = await Promise.all(fetches);
    presets = arrays.flat();
  }
  this.engine.loadPresets(presets);
}
```

### Phase 1, Step 4 — Validate

1. Count total presets loaded — must equal 75 (the original count).
2. Run the game and open the browser console — confirm `[ParticleManager] Loaded 75 presets:` message appears.
3. Confirm `[ParticleManager] ✓ All N mapped effects verified` message (no missing presets).
4. Trigger a few particle effects in-game (melee hit, spell cast, buff aura) to visually verify.

### Phase 1 — Done Criteria

- [x] 7 category files exist in `client/public/particle-presets/`
- [x] `particle-presets.json` is now the small index file
- [x] `ParticleManager.init()` loads and merges all category files
- [ ] Console shows 75 presets loaded, zero missing effects
- [ ] Visual particle effects work in-game

> **Completed:** March 1, 2026 — All 75 presets split into 7 category files (combat: 6, skills: 23, buffs: 10, projectiles: 16, portal: 6, ambient: 5, compound: 9). Index loader added with backward-compatible detection (Array = legacy, object with `files` = new format). Remaining checkboxes require a live game launch to visually verify.

---
---

## PHASE 2 — Split `skills.py` Effect Handlers

> **Goal:** Extract all skill effect handler functions from `server/app/core/skills.py` (65.2 KB, 1,451 lines) into a new `server/app/core/skill_effects.py`.

### Phase 2 Context

- `skills.py` contains two distinct sections:
  1. **Config & lookups** (~lines 1–250): `load_skills_config()`, `get_skill()`, `get_all_skills()`, `get_class_skills()`, `get_max_skill_slots()`, `can_use_skill()`, cooldown helpers.
  2. **Effect handlers** (~lines 250–1451): `apply_skill_effect()` dispatcher plus individual handlers like `_apply_heal()`, `_apply_buff()`, `_apply_multi_hit()`, `_apply_teleport()`, `_apply_ranged_attack()`, `_apply_aoe()`, plus `tick_buffs()` and buff expiration logic.
- The effect handlers are called by `turn_resolver.py` via `apply_skill_effect()`.
- Effect handlers import from `app.models.player`, `app.models.actions`, `app.core.fov`, and call `get_skill()` from the same file.
- **27 test files** import from `skills.py` — all existing imports must continue to work.

### Phase 2, Step 1 — Read and identify the split boundary

1. Open `server/app/core/skills.py`.
2. Identify the last "config/lookup" function and the first "effect handler" function.
3. The split boundary is between these two sections.

### Phase 2, Step 2 — Create `skill_effects.py`

1. Create `server/app/core/skill_effects.py`.
2. Move all `apply_*` functions, `tick_buffs()`, and any private helpers used exclusively by effect handlers into this new file.
3. Add necessary imports at the top (models, fov, and `from app.core.skills import get_skill` for lookups).

### Phase 2, Step 3 — Update `skills.py`

1. Remove the moved functions from `skills.py`.
2. Add re-exports so existing imports don't break:
   ```python
   # Re-export effect handlers for backward compatibility
   from app.core.skill_effects import apply_skill_effect, tick_buffs  # noqa: F401
   ```
3. This ensures that any file doing `from app.core.skills import apply_skill_effect` still works.

### Phase 2, Step 4 — Validate

1. Run the full test suite: `cd server && python -m pytest tests/ -x -q`
2. All 1641+ tests must pass — zero import errors, zero regressions.
3. Verify `skills.py` is now ~250 lines (config/lookup only).
4. Verify `skill_effects.py` is ~1,200 lines (all effect handlers).

### Phase 2 — Done Criteria

- [ ] `skill_effects.py` exists with all `apply_*` handlers and `tick_buffs()`
- [ ] `skills.py` re-exports `apply_skill_effect` and `tick_buffs` for backward compat
- [ ] `skills.py` is now ≤300 lines
- [ ] Full test suite passes with zero failures

---
---

## PHASE 3 — Split `message_handlers.py` by Domain

> **Goal:** Split `server/app/services/message_handlers.py` (32.4 KB, 732 lines, 24 handlers) into domain-specific sub-modules.

### Phase 3 Context

- The file contains `dispatch_message()` (a router that maps message type strings to handler functions) and 24 individual `handle_*` functions.
- Each handler function takes `(ws, data, match, player_id)` or similar args and returns a response dict.
- `dispatch_message()` is called from `server/app/services/websocket.py`.
- The handler functions call into `app.core.*` modules for business logic.

### Phase 3, Step 1 — Read and categorize handlers

1. Open `server/app/services/message_handlers.py`.
2. List every `handle_*` function and note which game domain it belongs to.
3. Group them into these domain buckets:

| File | Purpose |
|------|---------|
| `handlers/__init__.py` | Empty — makes it a package |
| `handlers/combat_handlers.py` | Combat actions: attack, skill use, auto-target |
| `handlers/dungeon_handlers.py` | Dungeon/map: movement, door, loot, exploration |
| `handlers/lobby_handlers.py` | Match: create, join, leave, ready, config |
| `handlers/party_handlers.py` | Party: stance, formation, hire, dismiss |
| `handlers/town_handlers.py` | Town hub: merchant, tavern, profile |

> **Note:** If a handler doesn't fit neatly, prefer the closest match. The grouping doesn't need to be perfect — it needs to be better than "all 24 in one file."

### Phase 3, Step 2 — Create handler sub-modules

1. Create `server/app/services/handlers/` directory with `__init__.py`.
2. Create each domain file, moving the relevant `handle_*` functions into it.
3. Each file should have its own imports (only what that file needs).

### Phase 3, Step 3 — Update `message_handlers.py`

1. Remove the moved handler functions.
2. Import them back from sub-modules.
3. `dispatch_message()` stays in `message_handlers.py` — the router remains the single entry point.

```python
# message_handlers.py — now just the router + imports
from app.services.handlers.combat_handlers import handle_attack, handle_skill, ...
from app.services.handlers.dungeon_handlers import handle_move, handle_door, ...
from app.services.handlers.lobby_handlers import handle_create_match, ...
from app.services.handlers.party_handlers import handle_set_stance, ...
from app.services.handlers.town_handlers import handle_merchant, ...

def dispatch_message(msg_type, ws, data, match, player_id):
    # ... existing routing logic, unchanged ...
```

### Phase 3, Step 4 — Validate

1. Run the full test suite: `cd server && python -m pytest tests/ -x -q`
2. All tests must pass.
3. Start the backend and connect with the client — send a few WebSocket messages (move, attack, open door) to confirm live routing works.
4. Verify `message_handlers.py` is now ≤100 lines (just imports + router).

### Phase 3 — Done Criteria

- [ ] `handlers/` package exists with 5 domain files + `__init__.py`
- [ ] `message_handlers.py` contains only `dispatch_message()` and re-imports
- [ ] `message_handlers.py` is now ≤100 lines
- [ ] Full test suite passes with zero failures
- [ ] WebSocket message routing works end-to-end

---
---

## Appendix — Watch List (No Action Required)

These files are large but currently cohesive. Re-evaluate if they grow significantly.

| File | Current Size | Split Trigger | Potential Extraction |
|------|-------------|---------------|---------------------|
| `server/app/core/turn_resolver.py` | 60.4 KB / 1,390 lines | >1,800 lines | Extract `_resolve_movement`, `_resolve_melee`, `_resolve_ranged` into helper modules |
| `server/app/core/match_manager.py` | 59.9 KB / 1,388 lines | >1,600 lines | Extract AI spawning, FOV cache into separate modules |
| `server/app/core/ai_stances.py` | 44.9 KB / 935 lines | New stances added | One file per stance |
| `server/app/core/ai_skills.py` | 42.7 KB / 920 lines | >1,200 lines | Split by skill category |
| `server/app/core/ai_behavior.py` | 40.0 KB / 916 lines | >1,200 lines | — (dispatch hub, likely stays) |
| `client/src/canvas/particles/ParticleManager.js` | 32.4 KB / 844 lines | >1,000 lines | Extract projectile travel → `ProjectileTraveler.js` |
| `client/src/canvas/ThemeEngine.js` | 36.5 KB / 594 lines | >800 lines | — (single responsibility) |
| `client/src/canvas/unitRenderer.js` | 34.2 KB / 710 lines | >1,000 lines | — (single responsibility) |
| `client/src/canvas/pathfinding.js` | 31.6 KB / 916 lines | >1,200 lines | — (self-contained algorithm) |

---

## Files Excluded From Analysis

- **`package-lock.json`** files (237 KB, 56 KB each) — auto-generated, never split
- **`mainlevbuild-atlas.json`** (338 KB) — asset atlas, not code
- **`wfc_dungeon.json`** / `wfc_dungeon_test_12x8.json` — generated map data
- **Test files** (`test_skills_combat.py`, `test_auto_target.py`, etc.) — large test files are normal; they mirror the modules they test
- **Documentation** — `.md` files are excluded regardless of size
