# Particle Visibility Lifecycle

**Date:** 2026-03-01  
**Status:** Implemented  
**File changed:** `client/src/canvas/particles/ParticleManager.js`

---

## Problem

When the user alt-tabs away from the game (or switches browser tabs), particle effects from every turn that occurred while the tab was hidden would all fire simultaneously upon return, producing a visual burst of stale effects.

### Root Cause

Two systems operate independently:

1. **`requestAnimationFrame` (rAF) loop** — The browser pauses rAF callbacks when a tab is hidden. The particle engine's `_tick()` method stops executing, so no particles are updated, rendered, or cleaned up.

2. **WebSocket → React → ParticleManager pipeline** — The server's tick loop continues sending `turn_result` messages at 1 Hz. React processes them normally, and each turn triggers `processActions()`, `updateCCStatus()`, and `updateBuffStatus()` on the ParticleManager. These methods create `Emitter` objects in the particle engine regardless of whether the rAF loop is running.

The result: emitters accumulate silently in the engine while the tab is hidden. When the user returns, rAF resumes and every queued emitter renders on the same frame — a burst of all combat effects that happened during the absence.

Additionally, the large time gap between the last rAF tick and the first post-return tick could cause a giant `dt` spike, making existing particles jump or behave erratically.

---

## Solution — Option C (Prevent + Resync)

All changes are encapsulated inside `ParticleManager.js`. No React component changes required.

### 1. Hidden Flag (`_hidden`)

A `_hidden` boolean tracks `document.hidden` state. It is initialized in the constructor and updated by a `visibilitychange` event listener.

```js
this._hidden = document.hidden;
document.addEventListener('visibilitychange', this._onVisibilityChange);
```

### 2. Guard All Public Trigger Methods

Four methods that create emitters are guarded with an early-return:

| Method | Purpose |
|--------|---------|
| `processActions()` | One-shot combat/skill/item effects from turn results |
| `processEnvironment()` | Door open / chest open effects |
| `updateCCStatus()` | Persistent CC aura emitters (stun, slow) |
| `updateBuffStatus()` | Persistent buff aura emitters (war cry, armor, evasion, etc.) |

Each now starts with:
```js
if (this._hidden) return;
```

This prevents **all** emitter creation while the tab is hidden — zero memory waste, zero CPU overhead for throwaway objects.

### 3. Resync on Tab Return (`_onVisibilityChange`)

When the tab becomes visible again:

1. **Reset `_lastTime`** — Sets `performance.now()` so the first `_tick()` after return computes a tiny `dt` instead of a multi-second spike.

2. **Clear the engine** — Wipes all emitters and projectiles as a safety net (there should be none thanks to the guards, but this protects against edge cases).

3. **Tear down persistent aura maps** — Clears `_ccEmitters` and `_buffEmitters` since they referenced emitters that were just removed from the engine.

4. **Rebuild persistent auras** — Immediately calls `updateCCStatus()` and `updateBuffStatus()` with the latest player state so looping auras (stun stars, buff glows) appear correctly on the very first rendered frame after return.

### 4. Cleanup on Destroy

The `destroy()` method now removes the `visibilitychange` event listener and clears the cached `_lastVisibleTiles` reference to prevent leaks.

---

## What This Does NOT Change

- **Game state processing** — WebSocket messages continue to be processed normally while hidden. Player positions, HP, buffs, combat log, etc. all stay current. Only the visual particle layer is paused.
- **The rAF loop itself** — The browser already pauses rAF for hidden tabs. This change works *with* that behavior rather than fighting it.
- **Arena.jsx** — No changes to the React component. The ParticleManager encapsulates all visibility awareness internally.

---

## Performance Impact

| State | Before | After |
|-------|--------|-------|
| Tab hidden, 30 turns pass | 30+ emitters created, hundreds of particles pooled | 0 emitters created, 0 particles allocated |
| Tab return | All 30+ emitters render simultaneously (visual burst + CPU spike) | Clean slate, only active auras rebuilt from current state |
| Normal gameplay (tab visible) | No change | No change (guard is a single boolean check) |

---

## Files Modified

| File | Changes |
|------|---------|
| `client/src/canvas/particles/ParticleManager.js` | Added `_hidden` flag, `_onVisibilityChange` handler, `_lastVisibleTiles` cache, guards on 4 trigger methods, cleanup in `destroy()` |

---

## Testing

Manual verification:  
1. Start a match with AI enemies  
2. Let combat begin (particle effects visible)  
3. Alt-tab away for 10+ seconds  
4. Alt-tab back  
5. **Expected:** No burst of stale effects. Active buff/CC auras appear immediately and correctly. New combat effects fire normally from the next turn onward.
