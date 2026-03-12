# Ranged Projectile Travel System

> **Last updated:** February 28, 2026  
> **Phase:** 14G — Visual Feedback & Combat Clarity  
> **Status:** Core system implemented, pending visual testing & tuning

---

## Table of Contents

1. [Overview](#1-overview)
2. [The Problem](#2-the-problem)
3. [Architecture](#3-architecture)
4. [Flight Path Mechanics](#4-flight-path-mechanics)
5. [Trail Presets](#5-trail-presets)
6. [Skill Configuration Reference](#6-skill-configuration-reference)
7. [Integration with ParticleManager](#7-integration-with-particlemanager)
8. [Edge Cases & Fallbacks](#8-edge-cases--fallbacks)
9. [File Map](#9-file-map)
10. [Future Improvements](#10-future-improvements)

---

## 1. Overview

The Ranged Projectile Travel system adds visible projectiles that fly from the caster to the victim for ranged attacks and spells. Before this system, all particle effects spawned instantly at the target — a Ranger's arrow and a Confessor's holy bolt both appeared as an impact on the victim with no visual connection to the attacker.

Now, ranged actions produce a traveling particle trail from caster → victim in pixel-space, followed by the impact effect on arrival. Each skill has its own trail preset, speed, and arc configuration — arrows lob through the air, divine bolts fly nearly flat, dark magic streaks straight to the target.

**Key principles:**
- All interpolation happens in **pixel-space**, never tile-space — no grid-snapping jitter
- Fully **data-driven** via `particle-effects.json` — tune speeds, arcs, and trails without code changes
- **Zero server changes** — entirely client-side rendering
- Impact effects (and extras, follow tracking, loop duration) fire identically to pre-projectile behavior, just delayed until arrival

---

## 2. The Problem

| Before | After |
|--------|-------|
| Ranger fires Power Shot → particles appear on victim instantly | Ranger fires Power Shot → arrow-trail arcs from Ranger to victim, impact fires on arrival |
| Confessor casts Rebuke → holy-smite appears on victim with no source | Confessor casts Rebuke → golden bolt streaks from Confessor to victim |
| All ranged skills look the same — instant impact at target | Each skill has a unique flight silhouette (arc, speed, trail color) |

With 8+ units acting simultaneously, instant-appearing effects make it difficult to understand *who attacked whom*. The projectile trail creates a visual line connecting attacker to target.

---

## 3. Architecture

```
ParticleManager._fireEffect(mapping, act, players)
    │
    ├── mapping has `projectile`?
    │     YES → _launchProjectile(mapping, act, players, targetPos)
    │             │
    │             ├── Resolve caster pixel position
    │             ├── Create ParticleProjectile(engine, config)
    │             │     ├── Creates looping trail emitter at caster position
    │             │     ├── Creates looping head emitter at caster position (if configured)
    │             │     └── Stores onArrive callback
    │             └── Push to _projectiles[] array
    │
    │             Each rAF frame:
    │             _updateProjectiles(dt)
    │               ├── projectile.update(dt)
    │               │     ├── Advance progress 0→1
    │               │     ├── Lerp X linearly
    │               │     ├── Lerp Y linearly + parabolic arc offset
    │               │     ├── Move trail emitter to (x, y)
    │               │     ├── Move head emitter to (x, y)
    │               │     └── On arrival: stop trail + head, fire onArrive()
    │               └── Remove dead projectiles (arrived + all emitters faded)
    │
    │             onArrive callback:
    │             _fireImpact(mapping, act, players, pos)
    │               ├── Emit impact preset at destination
    │               ├── Apply loop duration / follow tracking
    │               └── Fire extras (ice-shard, block, etc.)
    │
    └── NO projectile → _fireImpact() immediately (original behavior)
```

### Class: `ParticleProjectile`

**File:** `client/src/canvas/particles/ParticleProjectile.js`

A lightweight projectile that owns a trail emitter and an optional head emitter, interpolating between two world-pixel positions over time.

| Property | Type | Description |
|----------|------|-------------|
| `fromX`, `fromY` | number | Caster pixel position at launch |
| `toX`, `toY` | number | Target pixel position |
| `speed` | number | Travel speed in pixels/second |
| `arc` | number | Parabolic arc fraction (0 = flat, 0.2 = gentle lob) |
| `duration` | number | Derived: `distance / speed`, min 0.06s |
| `progress` | number | 0 → 1 interpolation progress |
| `trailEmitter` | Emitter | Continuous looping emitter — the ribbon behind the projectile |
| `headEmitter` | Emitter | Continuous looping emitter — tight bright point at the projectile tip |
| `onArrive` | Function | Callback to fire impact effect at destination |

**Methods:**
- `update(dt)` — advance progress, interpolate position, move trail emitter
- `isDead` — true when arrived AND trail particles have all died
- `forceComplete()` — immediate completion for cleanup scenarios

---

## 4. Flight Path Mechanics

### Linear Interpolation (X-axis)

```
x = fromX + (toX - fromX) * progress
```

Always a straight line in the horizontal axis. No grid involvement.

### Parabolic Arc (Y-axis)

```
baseY = fromY + (toY - fromY) * progress
arcOffset = -arc * totalDistance * sin(progress * π)
y = baseY + arcOffset
```

- `arc = 0` → perfectly straight line (magic bolts, eye beams)
- `arc = 0.05–0.08` → barely perceptible rise (holy bolts, curses)
- `arc = 0.15–0.2` → visible lob (physical arrows)
- The arc peaks at `progress = 0.5` (midpoint of flight)
- Negative offset = upward on screen (canvas Y increases downward)
- Arc magnitude scales with distance — long-range shots arc more, short-range less

### Travel Time

```
duration = max(totalDistance / speed, 0.06)
```

At TILE_SIZE = 48px:
- **Adjacent tile (1 tile, ~48px):** 0.12–0.14s at 350 px/s
- **Mid range (3 tiles, ~144px):** 0.36–0.41s
- **Max range (7 tiles, ~336px):** 0.75–0.96s depending on speed
- **Same tile (0px):** floors to 0.06s minimum (3–4 frames)

---

## 5. Trail & Head Presets

Each projectile now has two visual layers:
1. **Trail emitter** — continuous ribbon of particles behind the projectile
2. **Head emitter** — tight bright point locked to the projectile tip, giving it a visible "head" you can track with your eyes

### Trail Presets (per-skill)

| Preset | Rate | Lifetime | Shape | Colors | Gravity | Blend | Used By |
|--------|------|----------|-------|--------|---------|-------|---------|
| `arrow-trail` | 30/s | 0.08–0.18s | circle | White → brown → dark brown | Downward (15) | source-over | `ranged_attack` |
| `power-shot-trail` | 40/s | 0.1–0.22s | circle | White → gold → warm brown | Downward (12) | source-over | `power_shot` |
| `crip-shot-trail` | 35/s | 0.08–0.2s | circle | White → ice blue → deep blue | Downward (10) | lighter | `crippling_shot` |
| `rebuke-trail` | 40/s | 0.06–0.14s | circle | White → bright gold → amber | Upward (-3) | lighter | `rebuke` |
| `exorcism-trail` | 45/s | 0.12–0.25s | star | White → gold → amber | Upward (-4) | lighter | `exorcism` |
| `soul-reap-trail` | 35/s | 0.1–0.22s | line | Green → dark green → black | Upward (-4) | lighter | `soul_reap` |
| `wither-trail` | 25/s | 0.15–0.3s | square | Purple → dark purple → black | Upward (-6) | lighter | `wither` |
| `venom-trail` | 30/s | 0.1–0.22s | circle | Bright green → yellow-green → dark | Downward (5) | lighter | `venom_gaze` |

### Head Presets

| Preset | Rate | Lifetime | Shape | Colors | Size | Used By |
|--------|------|----------|-------|--------|------|---------|
| `arrow-head` | 45/s | 0.03–0.06s | circle | White → warm gold | 1.5–2.5 | `ranged_attack` |
| `power-shot-head` | 50/s | 0.04–0.08s | circle | White → bright gold | 2–3 | `power_shot` |
| `ice-arrow-head` | 45/s | 0.03–0.07s | circle | White → ice blue | 2–3 | `crippling_shot` |
| `holy-head` | 50/s | 0.04–0.08s | star | White → divine gold | 1.5–2.5 | `rebuke`, `exorcism` |
| `dark-head` | 40/s | 0.05–0.09s | circle | Bright purple → deep purple | 2–3 | `soul_reap`, `wither` |
| `venom-head` | 40/s | 0.04–0.08s | circle | Bright green → toxic green | 2–2.5 | `venom_gaze` |

### Legacy Presets (retained for backward compatibility)

| Preset | Status |
|--------|--------|
| `holy-bolt-trail` | Still in presets file, no longer referenced by default mappings |
| `dark-bolt-trail` | Still in presets file, no longer referenced by default mappings |

**Design notes:**
- All trails are continuous emitters (`burstMode: false`) with `loop: true` — they emit particles steadily while the projectile is in flight
- Very short particle lifetimes (0.03–0.3s) create a tight fading ribbon behind the projectile rather than a lingering cloud
- Physical arrow trails use `source-over` blend for an opaque feel; magic trails use `lighter` for a glowing ethereal look
- Trail gravity matches the skill fantasy: arrows droop, holy rises, dark/venom varies by personality
- Head presets have extremely short lifetimes (0.03–0.09s) and zero gravity — they create a tight bright point, not a cloud
- Shapes vary per skill category: `line` for scythe energy, `square` for curse fragments, `star` for divine sparkle

---

## 6. Skill Configuration Reference

Projectile config lives in `particle-effects.json` under each skill mapping:

```json
"power_shot": {
  "effect": "power-shot-impact",
  "target": "victim",
  "projectile": {
    "trail": "power-shot-trail",
    "head": "power-shot-head",
    "speed": 400,
    "arc": 0.2
  }
}
```

### Full Mapping Table

| Skill | Section | Trail | Head | Speed (px/s) | Arc | Impact Preset | Visual Feel |
|-------|---------|-------|------|-------------|-----|---------------|-------------|
| `ranged_attack` | combat | `arrow-trail` | `arrow-head` | 350 | 0.15 | `ranged-hit` | Gentle arrow lob, opaque warm tip |
| `power_shot` | skills | `power-shot-trail` | `power-shot-head` | 400 | 0.20 | `power-shot-impact` | Brighter, denser golden trail + glowing head |
| `crippling_shot` | skills | `crip-shot-trail` | `ice-arrow-head` | 350 | 0.15 | `crippling-shot-impact` + `ice-shard` | Icy blue trail + frosty head |
| `rebuke` | skills | `rebuke-trail` | `holy-head` | 450 | 0.05 | `holy-smite` | Compact fast-fading gold + divine star head |
| `exorcism` | skills | `exorcism-trail` | `holy-head` | 400 | 0.00 | `exorcism-flare` (2s loop) | Wide star-shaped holy beam + divine head |
| `soul_reap` | skills | `soul-reap-trail` | `dark-head` | 350 | 0.00 | `soul-reap-rend` | Green-black line-shaped slashes + purple head |
| `wither` | skills | `wither-trail` | `dark-head` | 300 | 0.08 | `wither-curse` (follow) | Sparse lingering square fragments + purple head |
| `venom_gaze` | skills | `venom-trail` | `venom-head` | 300 | 0.00 | `venom-gaze-bolt` (follow) | Green toxic dripping stream + green head |

### Speed Design Rationale

- **Faster (400–450 px/s):** High-impact or urgent skills — Power Shot, Rebuke. Quick flight sells power.
- **Medium (350 px/s):** Standard ranged attacks, soul reap. Smooth readable flight.
- **Slower (300 px/s):** Curses and debuffs — Wither, Venom Gaze. Languid flight sells dark magic menace.

### Arc Design Rationale

- **0.15–0.2:** Physical projectiles (arrows). Arcs feel natural for objects with mass and gravity.
- **0.05–0.08:** Semi-physical magic — Rebuke has a slight holy bolt rise, Wither droops ominously.
- **0:** Pure energy — exorcism beam, soul reap, venom gaze. Magic doesn't obey physics.

---

## 7. Integration with ParticleManager

### How Projectiles Enter the System

1. Server sends `TURN_RESULT` with action results
2. `Arena.jsx` passes actions to `particleManager.processActions(actions, players)`
3. `processActions()` dispatches to `_fireSkillEffect()` or `_fireCombatEffect()`
4. Both call `_fireEffect(mapping, act, players)`
5. `_fireEffect()` checks `mapping.projectile` — if present, calls `_launchProjectile()` instead of `_fireImpact()`

### Lifecycle

1. **Launch:** `_launchProjectile()` resolves caster position, creates `ParticleProjectile`, pushes to `_projectiles[]`
2. **Flight:** `_tick()` rAF loop calls `_updateProjectiles(dt)` every frame — updates positions, moves trail emitters
3. **Arrival:** Projectile reaches progress = 1.0, stops trail emitter, fires `onArrive` callback
4. **Impact:** `_fireImpact()` runs — same logic as the pre-projectile `_fireEffect()`: emit impact preset, handle loop duration, follow tracking, fire extras
5. **Cleanup:** `_updateProjectiles()` removes projectiles where `isDead` is true (arrived + trail particles all died)

### Non-Projectile Effects Unchanged

Effects without a `projectile` field in their mapping go through `_fireImpact()` directly — melee hits, heals, self-buffs, AoE, all work exactly as before.

---

## 8. Edge Cases & Fallbacks

| Scenario | Behavior |
|----------|----------|
| **Caster position unavailable** (died before render, out of FOV) | Falls back to immediate `_fireImpact()` at target — no projectile, but impact still plays |
| **Same-tile projectile** (caster and victim on same tile) | Minimum duration floor of 0.06s (~3–4 frames) — brief flash from center to center |
| **Caster dies mid-flight** | Projectile continues to destination — it owns its own position state, independent of caster |
| **Target dies before arrival** | Impact fires at the resolved position from launch time — particles appear at the original target location |
| **Multiple simultaneous projectiles** | All tracked independently in `_projectiles[]` array — no limit |
| **Match end / cleanup** | `destroy()` calls `forceComplete()` on all in-flight projectiles, triggering arrivals and cleaning up |
| **No trail preset configured** | Projectile still travels (invisible head only or fully invisible), impact fires on arrival timing |
| **No head preset configured** | Projectile travels with trail only — original behavior, backward compatible |

---

## 9. File Map

| File | Role |
|------|------|
| `client/src/canvas/particles/ParticleProjectile.js` | **New** — Projectile class (interpolation, arc, trail, arrival callback) |
| `client/src/canvas/particles/ParticleManager.js` | Modified — `_fireEffect()` projectile branch, `_launchProjectile()`, `_fireImpact()`, `_updateProjectiles()`, cleanup |
| `client/public/particle-presets.json` | Modified — 8 per-skill trail presets + 6 head presets (+ 3 legacy base trails retained) |
| `client/public/particle-effects.json` | Modified — `projectile` config with per-skill `trail` + `head` for 8 skill/combat mappings |

**No server-side changes.** The projectile system is purely a client-side rendering enhancement.

---

## 10. Future Improvements

### Short-Term (Tuning & Polish)

| Improvement | Description | Effort |
|-------------|-------------|--------|
| **Visual tuning pass** | Play-test each skill's speed/arc in-game and adjust values in JSON. Current numbers are theoretical — real feel may need tweaks. | Trivial (JSON only) |
| **Volley projectile barrage** | Volley is currently impact-only. Could spawn 4–6 rapid projectiles from above the target area raining down, each with `arrow-trail` and high downward arc (~0.8). Would make Volley visually distinct from single-target shots. | Small |
| **Trail particle count scaling** | At max range (7 tiles), the trail ribbon is long and spawns many particles. Could scale `rate` based on distance to keep particle count manageable on low-end machines. | Small |
| ~~**Projectile head sprite**~~ | **Done.** Head emitter system implemented — each projectile now has a tight bright continuous emitter locked to the tip, using per-skill head presets (`arrow-head`, `power-shot-head`, `ice-arrow-head`, `holy-head`, `dark-head`, `venom-head`). | ~~Small–Medium~~ |
| ~~**Per-skill trail presets**~~ | **Done.** 8 unique trail presets replace the original 3 shared trails. Each skill now has its own trail shape, color, gravity, and density. | ~~Small~~ |

### Medium-Term (New Capabilities)

| Improvement | Description | Effort |
|-------------|-------------|--------|
| **Bezier curve paths** | Replace `arc` with full quadratic/cubic bezier control points for per-skill flight personalities. Serpentine curves for Venom Gaze, spiraling for Soul Reap, rising-then-diving for Rebuke. | Medium |
| **Multi-projectile skills** | Some skills could fire 2–3 projectiles in a spread pattern (e.g., a Ranger volley skill, a bouncing lightning bolt). `ParticleManager` would create an array of `ParticleProjectile` with offset start positions or staggered timing. | Medium |
| **Projectile collision with terrain** | Currently projectiles fly straight through walls (the server already validated LOS). For visual fidelity, could check tile walkability along the path and terminate the projectile at the wall with a spark/ricochet effect. Only cosmetic — not gameplay-affecting. | Medium |
| **Chain projectiles** | For future bouncing/chaining skills: projectile arrives at target A, then a second projectile launches from A to B. The `onArrive` callback already supports this — just launch a new `ParticleProjectile` inside the callback. | Medium |
| **Projectile dodge interaction** | When a target dodges, the projectile could veer off to one side (overshoot) instead of hitting the target position. Would require `ParticleProjectile` to support a "miss" destination offset. | Small–Medium |

### Long-Term (System Extensions)

| Improvement | Description | Effort |
|-------------|-------------|--------|
| **Projectile speed easing** | Instead of constant speed, support easing curves (ease-in for arrows that accelerate, ease-out for bolts that decelerate near target). Would replace the constant `progress += dt / duration` with an eased value. | Small |
| **Camera follow for dramatic shots** | On high-damage ranged kills, briefly pan the viewport to follow the projectile travel. Cinematic kill-cam feel. Requires viewport control hook into the projectile system. | Large |
| **Sound effect sync** | Play a launch sound at caster position and an impact sound on arrival. The `onArrive` callback is the natural sync point. Requires audio system integration (separate phase). | Medium |
| **Homing projectiles** | Projectile that curves toward the target's *current* position each frame instead of a fixed destination. Less relevant for turn-based (targets don't move mid-flight) but would enable real-time mode in the future. | Medium |
| **Projectile interception** | A future "shield wall" or "deflect" ability could intercept incoming projectiles mid-flight, destroying them and playing a block effect. Would require projectiles to be queryable by position for intersection tests. | Large |
| **Particle Lab integration** | Add a "Projectile Preview" mode to the Particle Lab tool — define start/end points, trail preset, speed, and arc, then preview the full flight animation in isolation before wiring to game events. | Medium |
