# Project Health Audit — March 11, 2026

**Overall Verdict: Strong (8/10)**

Codebase is well-organized, well-tested, and well-documented after 20+ phases of aggressive feature development. Issues found are typical of fast-iteration game dev and are all addressable.

---

## What's Working Well

- **Documentation** — README is comprehensive (full project tree, phase history, feature table, decision log). Phase docs provide traceability for every feature.
- **Test suite** — 2,933 tests across 88 files, 0 failures, consistent naming, parametrized edge cases, multi-seed validation. No xfails, only 2 justified skips.
- **Dependencies** — 2 production client deps (React, React-DOM). 10 server deps, all current. No bloat or vulnerabilities.
- **Architecture** — Server cleanly separates models/core/services/routes. Client separates context/reducers/hooks/canvas/components. Turn_phases/ split in Phase 20 was excellent.
- **Config files** — 14 JSON configs, none oversized, all well-structured. `.gitignore` comprehensive. No `.pyc` committed. Archive directory empty.
- **Code hygiene** — Zero TODO/FIXME/HACK comments across the entire codebase.

---

## Priority 1 — Server File Splits (High Impact)

Apply the same proven pattern from the Phase 20 turn_resolver split: extract sub-modules, keep backward-compatible re-exports, verify all tests pass.

### 1A. Split `skills.py` (~2,907 lines) — CRITICAL

**Problem:** 30+ skill effect handlers in one massive dispatch function. Largest file in the project.

**Action:** Create `server/app/core/skill_effects/` directory:
- `__init__.py` — re-exports for backward compat
- `heal.py` — healing skill effects
- `damage.py` — direct damage effects
- `buff.py` — buff application effects
- `debuff.py` — debuff/CC effects
- `movement.py` — teleport/dash/movement skills
- `summon.py` — minion/totem/zone summoning
- `utility.py` — misc utility effects
- Keep config loading + validation in root `skills.py`

**Tests to verify:** All test_skills*.py, test_ws_skills.py, test_phase*.py

### 1B. Split `match_manager.py` (~1,287 lines) — HIGH

**Problem:** 13 global state dicts + 40+ functions = god-object pattern.

**Action:**
- Extract `match_state.py` — global state dict management (_active_matches, _player_states, _action_queues, _fov_cache, etc.) with getter/setter functions
- Extract `dungeon_orchestrator.py` — dungeon-specific logic (_generate_procedural_dungeon, _spawn_dungeon_enemies, advance_floor)
- Keep match lifecycle orchestration in `match_manager.py`

**Tests to verify:** Broad — most test files import from match_manager

### 1C. Split `ai_behavior.py` (~1,184 lines) — MEDIUM

**Problem:** 4 decision functions (aggressive/ranged/boss/support) at 200-350 lines each.

**Action:** Extract `ai_strategies.py` — move the 4 large decision functions there. Keep dispatch hub in ai_behavior.py.

**Tests to verify:** test_ai_*.py files

### 1D. Split `monster_rarity.py` (~1,080 lines) — MEDIUM

**Problem:** Combines rarity scaling + affix engine + super uniques in one file.

**Action:**
- Extract `affix_engine.py` — affix rolling, application, combat effects
- Extract `super_uniques.py` — super unique definitions, spawn logic
- Keep rarity tier config + scaling in `monster_rarity.py`

**Tests to verify:** test_monster_rarity*.py, test_affix*.py, test_super_unique*.py

### 1E. Extract movement from `combat.py` (~834 lines) — MEDIUM

**Problem:** `resolve_movement_batch()` is ~350 lines embedded in combat.

**Action:** Extract `movement_resolver.py` — move batch movement resolution. Keep damage/attack logic in combat.py.

**Tests to verify:** test_combat.py, test_movement*.py

---

## Priority 2 — Client Renderer Splits (Medium Impact)

Same pattern — extract by domain, keep re-exports for backward compat.

### 2A. Split `overlayRenderer.js` (~900+ lines) — HIGH

**Problem:** 5 separate rendering systems jammed into one file.

**Action:**
- `highlightRenderer.js` — drawHighlights, drawSkillHighlights
- `pathPreviewRenderer.js` — drawQueuePreview, drawHoverPathPreviews
- `environmentRenderer.js` — drawGroundItems, drawLootHighlight, drawGroundItemLabels, drawDamageFloaters, drawGroundZones, drawTotems, drawRootEffects, drawSoulAnchorEffects, drawSpawnMarker

### 2B. Split `unitRenderer.js` (~800+ lines) — HIGH

**Problem:** Sprites + nameplates + buffs + CC indicators all in one file.

**Action:**
- `spriteRenderer.js` — drawUnitShadow, drawPlayer (sprite/shape logic)
- `nameplateRenderer.js` — Diablo-style nameplate rendering (plate rect, HP bar, name layout)
- `buffRenderer.js` — drawBuffIcons (grid layout, sprite mapping, turn badges)
- `ccRenderer.js` — drawCrowdControlIndicators, stun stars, slow frost, taunt, roots, souls

### 2C. Extract message dispatch from `App.jsx` (~587 lines) — LOW

**Problem:** ~150 lines of nested type-checking in handleMessage().

**Action:** Create `messageHandlers.js` dispatch map so new message types don't bloat App.jsx.

---

## Priority 3 — Logging Infrastructure (Low Effort, High Value)

### 3A. Replace `print()` with Python `logging` — HIGH

**Problem:** Server uses print statements instead of structured logging. Errors are invisible in production scenarios.

**Action:**
- Add `logging.basicConfig()` in main.py
- Replace print() calls with appropriate log levels:
  - `logging.debug()` — tick details, AI decisions
  - `logging.info()` — match events, connections
  - `logging.warning()` — connection issues, stale state
  - `logging.error()` — failures, exceptions
- Estimate: ~2-3 hours of mechanical replacement

### 3B. Fix bare `except Exception: pass` — MEDIUM

**Problem:** WebSocket broadcast and other I/O paths silently swallow all errors. Masks bugs.

**Action:** Replace with specific exception types (ConnectionClosedError, JSONDecodeError, etc.) and log at warning/error level.

---

## Priority 4 — Test Infrastructure (Low Effort)

### 4A. Create shared `conftest.py` — MEDIUM

**Problem:** Every test file defines its own cache-clearing and state-reset fixtures. Repeated boilerplate.

**Action:** Create `server/tests/conftest.py` with common fixtures:
- Cache clearing (monster rarity, skills, config)
- Match state reset (_active_matches, _player_states, etc.)
- Match builder helpers
- WebSocket test client factory

**Benefit:** Every new test file gets cleaner, less boilerplate.

### 4B. Add `pytest-cov` for coverage reporting — LOW

**Action:** Add `pytest-cov` to requirements.txt and configure in pyproject.toml:
```toml
[tool.pytest.ini_options]
addopts = "--cov=app --cov-report=term-missing"
```

---

## Priority 5 — Security Hardening (When Production-Bound)

Not urgent for local dev, but must be addressed before any multiplayer testing beyond localhost.

### 5A. WebSocket Authentication — HIGH (for prod)

**Problem:** `/ws/{match_id}/{player_id}` accepts any connection with no identity verification. Anyone could connect as any player.

**Action:** Add JWT or session token validation in `websocket_endpoint` before accepting connection.

### 5B. WebSocket Rate Limiting — MEDIUM (for prod)

**Problem:** WebSocket accepts unlimited messages. Potential DoS vector.

**Action:** Add per-connection message rate limiting (e.g., max 60 messages/second).

### 5C. Production CORS Config — LOW (for prod)

**Problem:** CORS currently allows all origins (fine for dev).

**Action:** Restrict to production domain(s) when deploying.

---

## What NOT To Do

- **Don't over-abstract.** Code is pleasantly direct. Don't add service layers or design patterns "just in case."
- **Don't chase coverage metrics.** 2,933 tests cover the right things. Quality over quantity.
- **Don't refactor everything at once.** Pick one file split per sprint, verify tests, move on.
- **Don't add comments to working code.** Zero TODO/FIXME is a strength — keep it that way.

---

## Quick Reference — File Sizes

### Server (files > 500 lines)
| File | Lines | Priority |
|------|-------|----------|
| skills.py | ~2,907 | P1A (Critical) |
| match_manager.py | ~1,287 | P1B (High) |
| ai_behavior.py | ~1,184 | P1C (Medium) |
| monster_rarity.py | ~1,080 | P1D (Medium) |
| combat.py | ~834 | P1E (Medium) |

### Client (files > 400 lines)
| File | Lines | Priority |
|------|-------|----------|
| overlayRenderer.js | ~900+ | P2A (High) |
| unitRenderer.js | ~800+ | P2B (High) |
| pathfinding.js | ~717 | Acceptable (domain-cohesive) |
| Arena.jsx | ~710 | Acceptable (well-decomposed via hooks) |
| BottomBar.jsx | ~667 | Acceptable (cohesive) |
| ThemeEngine.js | ~594 | Acceptable (8 themes, focused) |
| App.jsx | ~587 | P2C (Low) |
| HeroDetailPanel.jsx | ~587 | Borderline |
