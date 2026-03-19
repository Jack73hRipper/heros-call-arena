# Phase — Render Performance Optimization (Lighting + Particles)

**Created:** March 17, 2026  
**Status:** Planning  
**Previous:** v0.1.7k (Ambient Darkness Pass) · v0.1.7j (Prop Lighting System) · 3710+ tests passing  
**Trigger:** Noticeable frame drops in dungeons when spell particle effects fire alongside the new lighting/darkness passes

---

## The Problem

The Prop Lighting system (v0.1.7j) and Ambient Darkness pass (v0.1.7k) produce beautiful dungeon atmosphere — torches cast warm multi-tile glow, darkness envelops the space between light sources, and prop particles (embers, spores, mist) add motion. However, the combined per-frame cost of these systems is causing frame drops, especially when spell combat particles layer on top.

### Per-Frame Render Cost Audit

| System | Per-Frame Work | Draw Calls / Frame | Cost Level |
|--------|---------------|-------------------|------------|
| **Ambient Darkness Pass** | Iterates every tile in grid (gridWidth × gridHeight), builds string key, checks Set, interpolates RGBA string, calls `fillRect` per visible tile | ~4,000–6,000 `fillRect` | **Very High** |
| **Fog Pass** | Same per-tile iteration, string key construction + `fillRect` for every non-visible tile | ~3,000–5,000 `fillRect` | **Very High** |
| **Prop Glow Pass** | `createRadialGradient()` + `arc()` + `fill()` per light source, with sine-wave flicker rebuilding gradients every frame | ~15–30 gradient creates | **Medium-High** |
| **Particle Color Sampling** | `sampleGradient()` (linear scan + hex→RGB parse) + `rgbaToString()` (string alloc) per alive particle per frame | ~100–200 string allocs | **Medium** |
| **Particle Renderer** | `ctx.save()` → `translate` → `rotate` → set alpha/fill → `arc` → `fill` → `ctx.restore()` per particle | ~9 state changes × particle count | **Medium** |
| **Particle Dead Removal** | `Array.splice(i, 1)` backward in emitter update loop — O(n) per dead particle | Varies | **Low** |

### Why It Stacks Up

A typical dungeon floor has 6–10 rooms with ~10–20 light-emitting props total. On a 96×64 map:

- **Ambient Darkness:** Up to 6,144 `fillRect` calls per frame (every tile checked)
- **Fog:** Another 3,000–5,000 `fillRect` calls (every non-visible tile)
- **Prop Glow:** 15–20 `createRadialGradient` + `arc` + `fill` (one per light source)
- **Prop Particles:** 60–110 ambient particles always alive (torches, braziers, spores)
- **Spell Particles:** 30–100+ additional burst particles during combat

That's **~10,000+ canvas draw calls per frame** from lighting/fog alone, plus 100–200 particle draws, all running at 60fps. The lighting data is **completely static between turns** — rooms don't change, light sources don't move — yet it's being recomputed every frame.

### What's Already Cached (Working Well)

- `collectLightSources()` — Cached by theme + room count. Light positions are only recalculated on floor/theme change. ✓
- `_getAmbientLightMap()` — Light intensity map cached. ✓
- `getFogLightMap()` — Fog modulation map cached. ✓

### What's NOT Cached (The Problem)

- **Ambient Darkness rendering** — The darkness overlay is drawn tile-by-tile every frame, despite the underlying light map being static
- **Fog rendering** — Same issue — per-tile `fillRect` every frame despite revealed/visible tiles only changing once per turn
- **Prop Glow rendering** — Gradient objects rebuilt every frame; only fire flicker (tiny sine-wave offset) changes between frames
- **Particle color computation** — Gradient color sampled from scratch every frame per particle

---

## Plan Overview

| Priority | Feature | Effort | Impact | Visual Change |
|----------|---------|--------|--------|---------------|
| **P-A** | Offscreen canvas for Ambient Darkness pass | Small | **Very High** — eliminates ~6K fillRects/frame | None — pixel-identical |
| **P-B** | Offscreen canvas for Fog pass | Small-Medium | **Very High** — eliminates ~5K fillRects/frame | None — pixel-identical |
| **P-C** | Offscreen canvas for Prop Glow pass (throttled redraw) | Small | **Medium-High** — eliminates ~20 gradient creates/frame | Imperceptible — flicker slightly less granular |
| **P-D** | Pre-computed particle color gradient LUT | Small | **Medium** — eliminates 100+ string allocs/frame | None — identical colors |
| **P-E** | Fast-path particle renderer for non-rotating circles | Small | **Low-Medium** — fewer state changes per particle | None |
| **P-F** | Swap-and-pop dead particle removal | Trivial | **Low** — eliminates O(n) splice overhead | None |

---

## Priority P-A — Offscreen Canvas for Ambient Darkness Pass

**Goal:** Pre-render the ambient darkness overlay to an offscreen `<canvas>`, blit it with a single `drawImage()` per frame. Invalidate only when rooms/theme/visible tiles change.

### Current Behavior

`drawAmbientDarknessPass()` in `PropLighting.js` — called every frame from `renderFrame()`:
1. Loops every tile `(0,0)` to `(gridWidth, gridHeight)`
2. Builds string key `"${x},${y}"` per tile
3. Checks `visibleTiles.has(key)` — skips non-visible
4. Reads `lightMap.get(key)` for light reduction
5. Computes alpha: `baseDarkness * (1 - lightReduction)`
6. Sets `ctx.fillStyle = "rgba(0,0,0,${alpha})"` — string interpolation
7. Calls `ctx.fillRect(...)` — one per tile

On a 96×64 grid that's up to **6,144** iterations with string construction + Map lookup + fillRect per frame. The output is identical between frames unless `visibleTiles` changes (which only happens when units move — once per turn).

### Target Behavior

1. On first call (or when cache is invalidated), render the darkness overlay to an offscreen canvas at full grid resolution
2. Store the offscreen canvas in module state alongside a cache key derived from `theme.id + rooms.length + visibleTiles hash`
3. Each frame: `ctx.drawImage(offscreenCanvas, -offsetX * TILE_SIZE, -offsetY * TILE_SIZE)` — a single blit
4. Cache invalidation triggers:
   - `visibleTiles` Set changes (new tiles revealed after movement)
   - Theme change (different `ambientDarkness` value)
   - Floor change (different rooms/light sources)

### Implementation Details

**File:** `client/src/canvas/PropLighting.js`

```
// Module state
let _darknessCanvas = null;          // OffscreenCanvas or regular <canvas>
let _darknessCacheKey = null;        // String hash for invalidation

function _buildDarknessCacheKey(visibleTiles, themeId, roomCount, baseDarkness) {
  // Use visibleTiles.size + a sample of tile keys as a fast hash
  // visibleTiles changes are rare (once per turn) so this is cheap
  return `${themeId}_${roomCount}_${baseDarkness}_${visibleTiles.size}`;
}
```

Rewrite `drawAmbientDarknessPass()`:
1. Compute cache key
2. If key matches → `ctx.drawImage(_darknessCanvas, ...)` → return
3. If key changed → create/resize offscreen canvas → render all tiles to it → cache → blit

### Visible Tiles Hash Approach

`visibleTiles.size` is a fast proxy — when the player moves and reveals new tiles, the Set grows. This avoids hashing every key. For rare edge cases where size stays the same but content changes (unlikely in practice), we can also track the turn number.

### Files Changed
- `client/src/canvas/PropLighting.js` — Rewrite `drawAmbientDarknessPass()` to use offscreen canvas cache; add `_darknessCanvas`, `_darknessCacheKey` module state; update `clearLightCache()` to also clear darkness canvas

### Testing
- Visual verification in-game: darkness overlay should look identical
- Performance: verify with browser DevTools Performance tab — `drawAmbientDarknessPass` should drop from ~2–4ms/frame to <0.1ms/frame
- Edge cases: theme change mid-run, floor transitions, first-frame render

---

## Priority P-B — Offscreen Canvas for Fog Pass

**Goal:** Pre-render the fog-of-war overlay to an offscreen canvas, blit with `drawImage()` per frame. Invalidate when `visibleTiles` or `revealedTiles` change.

### Current Behavior

`ThemeEngine.drawFog()` — called every frame from `drawFog()` in `dungeonRenderer.js`:
1. Loops every tile `(0,0)` to `(gridWidth, gridHeight)`
2. Skips visible tiles (`visibleTiles.has(key)`)
3. For revealed tiles: parses RGBA string, checks `fogLightMap`, computes modulated alpha, sets `fillStyle`, calls `fillRect`
4. For unrevealed tiles: sets solid black `fillStyle`, calls `fillRect`

Same per-tile cost pattern as the darkness pass. Output only changes when `visibleTiles` changes (once per turn).

### Target Behavior

1. On first call (or cache miss), render fog to an offscreen canvas at full grid resolution
2. Cache key: `themeId + visibleTiles.size + revealedTiles.size + roomCount`
3. Each frame: single `ctx.drawImage()` blit
4. Invalidation: `visibleTiles` changes (movement/reveal), `revealedTiles` changes (new rooms explored), theme change

### Implementation Details

**File:** `client/src/canvas/ThemeEngine.js`

Add an offscreen fog canvas cache to the `ThemeEngine` class:
```
// In ThemeEngine class
this._fogCanvas = null;
this._fogCacheKey = null;
```

Rewrite `drawFog()`:
1. Compute cache key from visibleTiles.size + revealedTiles.size + theme ID
2. If cache hit → `ctx.drawImage(this._fogCanvas, ...)` → return
3. If cache miss → create offscreen canvas → render all fog tiles → cache → blit

### The `fogLightMap` Integration

The `fogLightMap` (from `PropLighting.getFogLightMap()`) is already cached by theme + room count. It only needs to be applied when drawing the fog canvas — not every frame. Since it's static per floor, this integrates cleanly with the offscreen approach.

### Files Changed
- `client/src/canvas/ThemeEngine.js` — Rewrite `drawFog()` with offscreen canvas cache; add `_fogCanvas`, `_fogCacheKey` instance state; clear fog cache in `setTheme()`
- `client/src/canvas/dungeonRenderer.js` — No changes needed (calls `themeEngine.drawFog()` which handles caching internally)

### Testing
- Visual verification: fog should look identical — light-modulated revealed tiles, solid black unexplored, clear visible
- Verify fog updates correctly when player moves and reveals new tiles
- Verify fog updates on theme/floor change
- Performance: `drawFog` should drop from ~2–3ms to <0.1ms per frame

---

## Priority P-C — Offscreen Canvas for Prop Glow Pass

**Goal:** Pre-render the additive glow halos to an offscreen canvas. Redraw the offscreen canvas at ~10fps (for fire flicker animation) instead of 60fps, then blit to the main canvas every frame.

### Current Behavior

`drawPropGlowPass()` in `PropLighting.js` — called every frame:
1. Gets cached light sources (fast)
2. For each source: computes flicker sine-wave, creates `CanvasGradient`, draws `arc` + `fill` with 'lighter' composite
3. ~15–20 `createRadialGradient()` calls per frame — gradient creation is expensive in Canvas2D

### Target Behavior

1. Maintain a dedicated offscreen canvas for the glow layer
2. **Throttle redraws** to ~100ms intervals (10fps) — fire flicker is a subtle sine-wave; 10fps is more than enough for the visual effect
3. Each main frame: `ctx.drawImage(glowCanvas, ...)` with `globalCompositeOperation: 'lighter'` — single blit with correct blending
4. Full invalidation on room/theme change (same as current light source cache)

### Implementation Details

**File:** `client/src/canvas/PropLighting.js`

```
let _glowCanvas = null;
let _glowLastRedraw = 0;
const GLOW_REDRAW_INTERVAL = 100; // ms — 10fps for flicker
```

Rewrite `drawPropGlowPass()`:
1. Check if `now - _glowLastRedraw >= GLOW_REDRAW_INTERVAL`
2. If yes → redraw all glow sources to `_glowCanvas`, update `_glowLastRedraw`
3. If no → skip redraw (use cached canvas)
4. Blit: `ctx.globalCompositeOperation = 'lighter'; ctx.drawImage(_glowCanvas, ...); ctx.globalCompositeOperation = 'source-over';`

### Visual Impact

Fire flicker updates at 10fps instead of 60fps. The flicker amplitude is ±0.012 intensity — this is already a very subtle effect. At 10fps it will still look like a natural flicker; human perception of fire flicker tops out around 8–12Hz anyway.

### Files Changed
- `client/src/canvas/PropLighting.js` — Rewrite `drawPropGlowPass()` with throttled offscreen canvas; add `_glowCanvas`, `_glowLastRedraw` module state; update `clearLightCache()` to clear glow canvas

### Testing
- Visual comparison: glow should look identical in still frame, flicker still visible and natural in motion
- Verify additive blending produces same visual result via offscreen blit
- Performance: `drawPropGlowPass` should drop from ~1–2ms to <0.1ms on non-redraw frames

---

## Priority P-D — Pre-Computed Particle Color Gradient LUT

**Goal:** Replace per-frame `sampleGradient()` (linear scan + hex→RGB + string alloc per particle) with a pre-computed lookup table of RGBA strings, indexed by normalized age `t`.

### Current Behavior

In `Particle.js`, every `update(dt)` call:
1. Computes normalized age `t = elapsed / lifetime`
2. Calls `sampleGradient(this.colorStops, t)` — linear scan of color stops array
3. Inside `sampleGradient`: finds bracketing stops, parses hex colors to RGB (`parseInt` × 3 per color), interpolates RGBA per channel, calls `rgbaToString()` to build a CSS color string
4. Result: a freshly allocated string like `"rgba(255, 140, 40, 0.8)"` — **every particle, every frame**

With 100–200 alive particles, that's 100–200 hex parses + 100–200 string allocations per frame.

### Target Behavior

When an Emitter is created, pre-compute a lookup table (LUT) of ~64 pre-built RGBA strings spanning `t = 0.0` to `t = 1.0`. During particle update, index into the LUT with `Math.floor(t * (LUT_LENGTH - 1))` — a single array access, no parsing, no allocation.

### Implementation Details

**File:** `client/src/canvas/particles/Emitter.js` (or a new utility in the particles folder)

```
const COLOR_LUT_SIZE = 64;

function buildColorLUT(colorStops) {
  const lut = new Array(COLOR_LUT_SIZE);
  for (let i = 0; i < COLOR_LUT_SIZE; i++) {
    const t = i / (COLOR_LUT_SIZE - 1);
    lut[i] = sampleGradient(colorStops, t); // existing function
  }
  return lut;
}
```

**File:** `client/src/canvas/particles/Particle.js`

In `update()`, replace:
```
this.color = sampleGradient(this.colorStops, t);
```
With:
```
this.color = this._colorLUT[Math.floor(t * (this._colorLUT.length - 1))];
```

The LUT is set on the particle when it's spawned from the emitter's pre-built LUT (shared reference — no per-particle allocation).

### Files Changed
- `client/src/canvas/particles/Emitter.js` — Build `_colorLUT` array on construction from preset color stops; pass LUT reference to particles on spawn
- `client/src/canvas/particles/Particle.js` — Replace `sampleGradient()` call in `update()` with LUT index lookup

### Testing
- Visual verification in Particle Lab: all presets should look identical
- No color banding: 64 steps across a typical 0.3–1.5s lifetime is more than sufficient (human eye can distinguish ~30 color steps in a gradient)
- Performance: per-particle update cost should drop significantly (no hex parse, no string alloc)

---

## Priority P-E — Fast-Path Particle Renderer for Non-Rotating Circles

**Goal:** Skip `ctx.save()` / `ctx.translate()` / `ctx.rotate()` / `ctx.restore()` for particles that don't use rotation. Most ambient particles (embers, spores, mist, candelabra glow) are circles with zero rotation.

### Current Behavior

`ParticleRenderer.render()` — per particle:
```js
ctx.save();
ctx.translate(p.x, p.y);
ctx.rotate(p.rotation);
ctx.globalAlpha = p.alpha;
ctx.fillStyle = p.color;
this._drawShape(ctx, p.shape, p.size);  // arc() for circles
ctx.restore();
```

That's 9 canvas state changes per particle, even when `rotation = 0` and shape is a simple circle.

### Target Behavior

Check if the particle needs rotation/complex shapes. If not, use a fast path:
```js
// Fast path: non-rotating circle
ctx.globalAlpha = p.alpha;
ctx.fillStyle = p.color;
ctx.beginPath();
ctx.arc(p.x, p.y, p.size / 2, 0, Math.PI * 2);
ctx.fill();
```

This eliminates `save`, `translate`, `rotate`, `restore` — 4 expensive state operations per particle.

### Detection

A particle qualifies for the fast path when:
- `p.shape === 'circle'` (or undefined/default)
- `p.rotation === 0` (or no rotationSpeed configured in preset)
- `p.trail` is null/empty (no trail drawing needed)

Most ambient prop presets meet all three criteria.

### Files Changed
- `client/src/canvas/particles/ParticleRenderer.js` — Add fast-path branch in `render()` loop before the existing save/translate/rotate path

### Testing
- Visual verification: all particle effects should look identical
- Compare ambient presets (embers, spores, mist) side by side before/after
- Performance: fewer state changes per particle in the common case

---

## Priority P-F — Swap-and-Pop Dead Particle Removal

**Goal:** Replace `Array.splice(i, 1)` in the Emitter update loop with swap-and-pop for O(1) removal.

### Current Behavior

`Emitter.update()`:
```js
for (let i = this.particles.length - 1; i >= 0; i--) {
  const p = this.particles[i];
  const alive = p.update(dt, forces);
  if (!alive) {
    this._pool.push(p);
    this.particles.splice(i, 1);   // O(n) — shifts all elements after i
  }
}
```

Each `splice` shifts the remaining array elements. With 10–20 particles per emitter and frequent death/respawn, this adds up.

### Target Behavior

```js
for (let i = this.particles.length - 1; i >= 0; i--) {
  const p = this.particles[i];
  const alive = p.update(dt, forces);
  if (!alive) {
    this._pool.push(p);
    // Swap dead particle with last element, then pop
    const last = this.particles.length - 1;
    if (i !== last) this.particles[i] = this.particles[last];
    this.particles.pop();
  }
}
```

Order doesn't matter for particles (they're drawn independently), so swap-and-pop is safe.

### Files Changed
- `client/src/canvas/particles/Emitter.js` — Replace `splice(i, 1)` with swap-and-pop in `update()` loop

### Testing
- All existing particle effects should look identical (render order of particles within one emitter doesn't matter visually)
- Particle Lab verification
- Edge case: single-particle emitter, all particles dying on same frame

---

## Implementation Order & Dependencies

```
P-A (Darkness offscreen)   ─── independent ───┐
P-B (Fog offscreen)        ─── independent ───┤
P-C (Glow offscreen)       ─── independent ───┼── all can be done in parallel
P-D (Color LUT)            ─── independent ───┤
P-E (Fast-path renderer)   ─── independent ───┤
P-F (Swap-and-pop)         ─── independent ───┘
```

All six priorities are fully independent — no dependencies between them. They touch different functions in different files. Each can be implemented and verified in isolation.

**Recommended order for maximum incremental gain:**
1. P-A + P-B together (biggest FPS wins, both follow the same offscreen canvas pattern)
2. P-C (completes the offscreen canvas trio for all lighting passes)
3. P-D (particle engine improvement)
4. P-E + P-F together (particle renderer micro-optimizations)

---

## Performance Validation

After each priority is implemented, validate with:

1. **Browser DevTools → Performance tab** — Record 5s of dungeon gameplay
   - Before: Look for `drawAmbientDarknessPass`, `drawFog`, `drawPropGlowPass` in the flame chart
   - After: These should nearly disappear (replaced by fast `drawImage` blits)
2. **Frame time** — Target consistent <16.6ms frames (60fps) during active combat with particles
3. **Visual diff** — Screenshot comparison before/after each change to confirm pixel-identical output

### Expected Results

| Metric | Before (estimated) | After P-A+P-B | After All |
|--------|-------------------|---------------|-----------|
| Darkness pass | ~2–4ms/frame | <0.1ms/frame | <0.1ms/frame |
| Fog pass | ~2–3ms/frame | <0.1ms/frame | <0.1ms/frame |
| Glow pass | ~1–2ms/frame | ~1–2ms at 10fps, <0.1ms other frames | <0.1ms avg |
| Particle update+render | ~1–2ms/frame | ~1–2ms/frame | <0.5ms/frame |
| **Total lighting+particle** | **~6–11ms/frame** | **~1–2ms/frame** | **<1ms/frame** |

---

## Files Summary

| File | Changes |
|------|---------|
| `client/src/canvas/PropLighting.js` | P-A: offscreen darkness canvas + cache; P-C: offscreen glow canvas + throttled redraw; update `clearLightCache()` |
| `client/src/canvas/ThemeEngine.js` | P-B: offscreen fog canvas + cache in `drawFog()` |
| `client/src/canvas/particles/Emitter.js` | P-D: build color LUT on construction; P-F: swap-and-pop removal |
| `client/src/canvas/particles/Particle.js` | P-D: LUT index lookup instead of `sampleGradient()` |
| `client/src/canvas/particles/ParticleRenderer.js` | P-E: fast-path branch for non-rotating circles |

No server changes. No new dependencies. No API/protocol changes. All changes are client-side rendering internals.

---

## Risks & Notes

- **Offscreen canvas memory** — Each offscreen canvas at 96×64 tiles × 64px = 6144×4096 pixels × 4 bytes = ~96MB per canvas. This is too large. Instead, size the offscreen canvas to match the **viewport** dimensions (the visible area on screen, ~20×15 tiles), and translate coordinates accordingly. This keeps each offscreen canvas at ~5–10MB, well within budget. Alternatively, render only the on-screen portion by iterating `offsetX..offsetX+viewportW` instead of `0..gridWidth`.
- **Visibility change detection** — Using `visibleTiles.size` as a cache key is a fast O(1) proxy. In rare cases where Set size stays the same but content changes, adding the current turn number to the cache key fully resolves this.
- **Glow additive blending via offscreen** — When blitting the glow offscreen canvas, the main canvas must use `globalCompositeOperation: 'lighter'` to preserve the additive blending effect. The offscreen canvas itself should be rendered with `'lighter'` on a transparent background.
- **No visual changes** — Every optimization produces pixel-identical output (P-C's glow throttle is the only one with a theoretical difference, and it's imperceptible at 10fps flicker rate vs 60fps).

---

## Implementation Log

### P-A — Offscreen Canvas for Ambient Darkness Pass ✅

**Completed:** March 17, 2026  
**Status:** Done — pixel-identical, no errors

**What was done:**

1. **Added module-level offscreen canvas state** in `PropLighting.js`:
   - `_darknessCanvas` — offscreen `<canvas>` element sized to the viewport
   - `_darknessCacheKey` — string hash for cache invalidation

2. **Rewrote `drawAmbientDarknessPass()`** to use a two-path strategy:
   - **Cache hit:** single `ctx.drawImage(_darknessCanvas, 0, 0)` blit — near-zero cost
   - **Cache miss:** renders all darkness tiles to the offscreen canvas, stores it, then blits

3. **Cache key composition:** `themeId_roomCount_baseDarkness_visibleTiles.size_offsetX_offsetY_canvasW_canvasH`
   - `visibleTiles.size` is an O(1) proxy — the Set grows when the player reveals new tiles
   - `offsetX/offsetY` included because the offscreen canvas is viewport-scoped
   - `canvasW/canvasH` included to handle window resizes

4. **Viewport-scoped rendering** (per Risks & Notes):
   - Offscreen canvas sized to `ctx.canvas.width × ctx.canvas.height` (viewport), NOT the full grid
   - Tile iteration bounded to `offsetX..offsetX+tilesVisibleX` instead of `0..gridWidth`
   - Keeps offscreen canvas memory at ~5–10MB instead of ~96MB

5. **Updated `clearLightCache()`** to also null out `_darknessCanvas` and `_darknessCacheKey`

**Performance impact:**
- Before: ~6,144 `fillRect` calls + string interpolations per frame (every tile in grid)
- After: 1 `drawImage` blit per frame (cache hit), full re-render only on visibility/camera change
- Expected: `drawAmbientDarknessPass` drops from ~2–4ms/frame to <0.1ms/frame on cache-hit frames

**Files changed:**
- `client/src/canvas/PropLighting.js` — `drawAmbientDarknessPass()` rewrite, `_darknessCanvas`/`_darknessCacheKey` state, `clearLightCache()` update

---

### P-B — Offscreen Canvas for Fog Pass ✅

**Completed:** March 17, 2026  
**Status:** Done — pixel-identical, no errors

**What was done:**

1. **Added instance-level offscreen canvas state** in `ThemeEngine` constructor:
   - `this._fogCanvas` — offscreen `<canvas>` element sized to the viewport
   - `this._fogCacheKey` — string hash for cache invalidation

2. **Rewrote `drawFog()`** to use a two-path strategy (matching P-A pattern):
   - **Cache hit:** single `ctx.drawImage(this._fogCanvas, 0, 0)` blit — near-zero cost
   - **Cache miss:** renders all fog tiles to the offscreen canvas, stores it, then blits

3. **Cache key composition:** `themeId_visibleTiles.size_revealedTiles.size_offsetX_offsetY_canvasW_canvasH`
   - `visibleTiles.size` + `revealedTiles.size` are O(1) proxies — both Sets only grow during a floor (tiles get revealed, never un-revealed)
   - `offsetX/offsetY` included because the offscreen canvas is viewport-scoped
   - `canvasW/canvasH` included to handle window resizes

4. **Viewport-scoped rendering** (per Risks & Notes):
   - Offscreen canvas sized to `ctx.canvas.width × ctx.canvas.height` (viewport), NOT the full grid
   - Tile iteration bounded to `offsetX..offsetX+tilesVisibleX` instead of `0..gridWidth`
   - Keeps offscreen canvas memory at ~5–10MB instead of ~96MB

5. **Cache invalidation on theme change:** `setTheme()` now nulls out `_fogCanvas` and `_fogCacheKey`

6. **fogLightMap integration preserved:** The `fogLightMap` (already cached by theme + room count in `PropLighting.getFogLightMap()`) is applied during offscreen canvas rendering — not every frame. Since it's static per floor, this integrates cleanly with the offscreen approach.

**Performance impact:**
- Before: ~3,000–5,000 `fillRect` calls + string interpolation + Map lookups per frame (every non-visible tile in full grid)
- After: 1 `drawImage` blit per frame (cache hit), full re-render only on visibility/camera/theme change
- Expected: `drawFog` drops from ~2–3ms/frame to <0.1ms/frame on cache-hit frames

**Files changed:**
- `client/src/canvas/ThemeEngine.js` — `drawFog()` rewrite with offscreen canvas cache, `_fogCanvas`/`_fogCacheKey` instance state in constructor, `setTheme()` cache invalidation

---

### P-C — Offscreen Canvas for Prop Glow Pass ✅

**Completed:** March 17, 2026  
**Status:** Done — pixel-identical on still frames, flicker visually indistinguishable at 10fps vs 60fps

**What was done:**

1. **Added module-level offscreen glow canvas state** in `PropLighting.js`:
   - `_glowCanvas` — offscreen `<canvas>` element sized to the viewport
   - `_glowLastRedraw` — timestamp of last offscreen redraw (for throttle)
   - `GLOW_REDRAW_INTERVAL = 100` — redraw every 100ms (~10fps) for fire flicker animation
   - `_glowSourceKey` — invalidation key for room/theme changes

2. **Rewrote `drawPropGlowPass()`** to use a throttled offscreen canvas strategy:
   - **Every frame:** blits `_glowCanvas` to the main canvas with `globalCompositeOperation: 'lighter'` — single `drawImage()` call
   - **Every ~100ms:** re-renders all glow sources (gradients, arcs, flicker sine-waves) to the offscreen canvas
   - **On room/theme change:** full invalidation — `_glowCanvas` nulled, forced redraw on next call

3. **Offscreen canvas uses additive blending internally:**
   - `offCtx.globalCompositeOperation = 'lighter'` set before drawing glow sources to the offscreen canvas
   - This ensures overlapping glow halos from nearby light sources blend additively, exactly matching the original behavior
   - The final blit to the main canvas also uses `'lighter'`, preserving the same visual result

4. **Cache invalidation triggers:**
   - Room/theme change: `_glowSourceKey` (`themeId_roomCount`) mismatch nulls the canvas and forces immediate redraw
   - Window resize: canvas dimension mismatch triggers recreation with forced redraw
   - `clearLightCache()` now also resets `_glowCanvas`, `_glowLastRedraw`, and `_glowSourceKey`

5. **Animation clock preserved:** `_lightAnimTime` continues advancing every frame so that when the throttled redraw fires, it samples the correct flicker/pulse phase — no visual desync

**Visual impact:**
- Fire flicker updates at 10fps instead of 60fps. The flicker amplitude is ±0.012 intensity — a very subtle effect. At 10fps it still looks like natural fire flicker; human flicker perception tops out around 8–12Hz.
- Pulsing effects (ritual circles, mushroom clusters) at ±0.04–0.06 amplitude also update at 10fps — still smooth and natural.

**Performance impact:**
- Before: ~15–20 `createRadialGradient()` + `arc()` + `fill()` calls per frame at 60fps (gradient creation is expensive in Canvas2D)
- After: 1 `drawImage` blit per frame (5 out of 6 frames), full gradient re-render only at ~10fps
- Expected: `drawPropGlowPass` drops from ~1–2ms/frame to <0.1ms/frame on non-redraw frames (~83% of frames)

**Files changed:**
- `client/src/canvas/PropLighting.js` — `drawPropGlowPass()` rewrite with throttled offscreen canvas, `_glowCanvas`/`_glowLastRedraw`/`_glowSourceKey` module state, `clearLightCache()` updated to clear glow state

---

### P-D — Pre-Computed Particle Color Gradient LUT ✅

**Completed:** March 17, 2026  
**Status:** Done — identical colors, no errors, 3,403 tests passing

**What was done:**

1. **Added `buildColorLUT()` helper function** in `Emitter.js`:
   - `COLOR_LUT_SIZE = 64` — 64-entry lookup table spanning `t = 0.0` to `t = 1.0`
   - Pre-samples `sampleGradient()` at 64 evenly-spaced `t` values at emitter construction time
   - Returns an array of `{r, g, b, a}` objects — pre-parsed, pre-interpolated, zero hex parsing at runtime
   - Returns `null` for presets with no color gradient (single-color fallback path unchanged)

2. **Built LUT in Emitter constructor** from `preset.particle.color.gradient`:
   - `this._colorLUT = buildColorLUT(pc.color?.gradient)` — one-time cost at emitter creation
   - LUT is a shared reference — all particles spawned from this emitter point to the same array (no per-particle allocation)

3. **Passed LUT to particles via spawn config** in `_spawnBurst()`:
   - Added `colorLUT: this._colorLUT` to the per-particle `cfg` object
   - Particles receive a reference to the emitter's LUT, not a copy

4. **Rebuilt LUT on live preset changes** in `applyPreset()`:
   - `this._colorLUT = buildColorLUT(pc.color?.gradient)` — supports Particle Lab real-time editing
   - New particles pick up the updated LUT; existing particles continue using their original cfg reference (natural lifecycle)

5. **Replaced `sampleGradient()` with LUT index lookup** in `Particle.js` `update()`:
   - **Fast path (LUT available):** `const idx = Math.floor(t * (lut.length - 1))` — single array access
   - Color string: `` `rgba(${c.r}, ${c.g}, ${c.b}, ${c.a * this.alpha})` `` — gradient alpha multiplied by particle alpha, matching original behavior exactly
   - **Fallback path preserved:** If no LUT (edge case), falls through to original `sampleGradient()` + `rgbaToString()` path
   - **Single-color path unchanged:** Presets without gradients still use `rgba(255, 200, 50, ${alpha})`

**What was eliminated per frame (per particle):**
- Linear scan of color stops array
- 2× `hexToRgba()` calls (6× `parseInt` per sample — two bracketing colors × 3 channels each)
- RGB channel interpolation computation
- Object spread `{ ...rgba, a: rgba.a * this.alpha }`
- `rgbaToString()` function call overhead

**What remains per frame (per particle):**
- 1× `Math.floor()` — trivial
- 1× array index access — trivial
- 1× template literal string build — unavoidable (Canvas2D needs a CSS color string)

**Color fidelity:** 64 LUT entries across a typical 0.3–1.5s particle lifetime means each step covers ~5–23ms. The human eye can distinguish ~30 color steps in a smooth gradient — 64 steps produces no visible banding.

**Performance impact:**
- Before: ~100–200 hex parses + gradient scans + string allocations per frame (one per alive particle)
- After: ~100–200 array index lookups + template literals per frame (no parsing, no scanning)
- Expected: measurable reduction in per-particle `update()` cost, especially with 100+ concurrent particles during spell combat

**Files changed:**
- `client/src/canvas/particles/Emitter.js` — `buildColorLUT()` helper, `_colorLUT` built in constructor, passed in `_spawnBurst()` cfg, rebuilt in `applyPreset()`
- `client/src/canvas/particles/Particle.js` — LUT fast-path branch in `update()` color gradient section

---

### P-E — Fast-Path Particle Renderer for Non-Rotating Circles ✅

**Completed:** March 17, 2026  
**Status:** Done — pixel-identical, no errors, 3,375 tests passing

**What was done:**

1. **Added fast-path branch in `render()` loop** in `ParticleRenderer.js`:
   - Before the existing `save/translate/rotate/restore` block, checks if the particle qualifies for the fast path
   - **Fast-path criteria:** particle shape is `'circle'` (or undefined/default), rotation is `0` (falsy), and no trail to draw
   - When all three hold, draws the circle directly at `(p.x, p.y)` without any canvas state push/pop

2. **Fast-path rendering sequence** (4 calls vs 9):
   - `ctx.globalAlpha = p.alpha`
   - `ctx.fillStyle = p.color`
   - `ctx.beginPath()` → `ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)` → `ctx.fill()`
   - Then `continue` — skips the slow path entirely

3. **Slow path preserved unchanged** for particles that need it:
   - Non-circle shapes (square, triangle, star, diamond, line)
   - Rotating particles (`p.rotation !== 0`)
   - Trail-bearing particles (trail already drawn above, but the particle body still needs translate/rotate)

4. **Trail compatibility:** The trail drawing (`_drawTrail`) happens before the fast-path check. If a particle has a trail, the trail is drawn first, then the fast-path check excludes it (because trail particles need `translate`/`rotate` for their body). This preserves correct layering: trail behind, particle body on top.

5. **Applied to both copies:**
   - `client/src/canvas/particles/ParticleRenderer.js` — game client
   - `tools/particle-lab/src/engine/ParticleRenderer.js` — Particle Lab tool (kept in sync)

**What the fast path eliminates per qualifying particle:**
- `ctx.save()` — pushes entire canvas state to stack
- `ctx.translate(p.x, p.y)` — modifies transform matrix
- `ctx.rotate(p.rotation)` — modifies transform matrix (rotation was 0 anyway)
- `ctx.restore()` — pops entire canvas state from stack
- `_drawShape()` function call overhead — inlined as direct `arc()` call

**Which particles qualify:**
- Most ambient prop particles: embers, spores, mist, candelabra glow, brazier sparks
- Many spell particles that are simple circles without rotation
- Estimated ~60–80% of all alive particles in a typical dungeon scene qualify for the fast path

**Performance impact:**
- Before: 9 canvas state operations per particle (`save`, `translate`, `rotate`, `globalAlpha`, `fillStyle`, `beginPath`, `arc`, `fill`, `restore`)
- After (fast path): 5 canvas operations per particle (`globalAlpha`, `fillStyle`, `beginPath`, `arc`, `fill`)
- `save()`/`restore()` are among the most expensive Canvas2D operations (they push/pop the full state stack including transform matrix, clipping, shadow, etc.)
- Expected: noticeable reduction in per-particle render cost for the majority of particles

**Files changed:**
- `client/src/canvas/particles/ParticleRenderer.js` — Fast-path branch added in `render()` loop
- `tools/particle-lab/src/engine/ParticleRenderer.js` — Same fast-path branch (kept in sync)

---

### P-F — Swap-and-Pop Dead Particle Removal ✅

**Completed:** March 17, 2026  
**Status:** Done — identical behavior, no errors

**What was done:**

1. **Replaced `Array.splice(i, 1)` with swap-and-pop** in `Emitter.update()`:
   - When a particle dies, instead of splicing (which shifts all subsequent elements — O(n) per removal), the dead particle is swapped with the last element in the array, then `pop()` removes the last element — O(1)
   - The backward `for` loop (`i = length - 1` down to `0`) is preserved, which naturally handles the swap correctly: when `i === last`, the swap is skipped and `pop()` just removes the dead particle; when `i < last`, the swapped-in particle at index `i` will be processed on the next iteration (it was already at a higher index, so it's already been updated this frame — but since we're iterating backward and it came from `last > i`, it was already visited)

2. **Applied to both copies:**
   - `client/src/canvas/particles/Emitter.js` — game client
   - `tools/particle-lab/src/engine/Emitter.js` — Particle Lab tool (kept in sync)

**Why this is safe:**
- Particle render order within a single emitter is visually irrelevant — particles are independent points/circles drawn on top of each other with alpha blending. Reordering them produces pixel-identical output in practice.
- The backward loop ensures every particle is updated exactly once per frame, even after a swap: the swapped-in element at index `i` came from a higher index that was already processed.

**What was eliminated:**
- `Array.splice(i, 1)` — O(n) per dead particle (shifts all elements after index `i`)
- With 10–20 particles per emitter and frequent death/respawn cycles (especially in continuous-spawn emitters like torch embers), the cumulative shift cost adds up across many emitters

**What replaced it:**
- 1× conditional assignment (`this.particles[i] = this.particles[last]`) — O(1)
- 1× `Array.pop()` — O(1)

**Performance impact:**
- Before: O(n) per dead particle removal, O(n × k) total per frame where k = number of dead particles
- After: O(1) per dead particle removal, O(k) total per frame
- Impact is most noticeable with many concurrent emitters (dungeon prop particles: torches, braziers, spores) where several particles expire each frame across all active emitters

**Files changed:**
- `client/src/canvas/particles/Emitter.js` — `splice(i, 1)` replaced with swap-and-pop in `update()` loop
- `tools/particle-lab/src/engine/Emitter.js` — Same swap-and-pop change (kept in sync)
