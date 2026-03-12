# Phase 9 — Particle Effects Lab

> **Goal:** Build a standalone particle effects designer tool that lets us create, preview, tweak, and export visual effects for the Arena game. All effects use Canvas 2D to match the game's renderer. Effects are saved as JSON presets that can be imported directly into the game client.

> **Status:** Phase 9A + 9B + 9C complete. Lab is functional and running at `http://localhost:5180`.

---

## 1. Why a Particle Lab?

The game currently has minimal visual feedback — damage floaters and sine-wave glows. A particle system adds:

- **Combat juice** — hit sparks, blood splashes, spell impacts, projectile trails
- **Environmental atmosphere** — torch flicker, dust motes, fog wisps
- **Player feedback** — level-up bursts, healing auras, loot pickup effects, death explosions
- **Status clarity** — poison drips, fire embers, ice crystals, buff/debuff auras

Building a lab-first approach means we can design and iterate on effects visually before wiring them into the game.

---

## 2. Architecture Overview

```
tools/
└── particle-lab/
    ├── index.html                  # Entry point (dark base styles)
    ├── package.json                # React 18 + Vite 5 (mirrors client stack)
    ├── vite.config.js              # Dev server on port 5180
    └── src/
        ├── App.jsx                 # Root layout, undo/redo, import/export, shortcuts
        ├── main.jsx                # React entry
        ├── presets.js              # 15 built-in preset configs
        ├── engine/
        │   ├── MathUtils.js        # Lerp, easing (12 curves), gradient sampling, spawn shapes
        │   ├── Particle.js         # Single particle data + per-frame update (physics, color, trail)
        │   ├── Emitter.js          # Emitter with object pooling, burst/continuous, spawn shapes
        │   ├── ParticleEngine.js   # Multi-emitter manager, preset registry, time scale
        │   └── ParticleRenderer.js # Canvas 2D draw (5 shapes + trail rendering)
        ├── components/
        │   ├── Canvas.jsx          # Preview canvas (grid, click-to-emit, auto-emit, FPS)
        │   ├── Toolbar.jsx         # Action buttons + live particle/FPS stats
        │   ├── ControlPanel.jsx    # 4-tab master panel (Emitter, Particle, Colors, Physics)
        │   ├── Controls.jsx        # Shared slider/range/select/toggle primitives
        │   ├── EmitterControls.jsx # Burst/continuous, spawn shape, direction, speed
        │   ├── ParticleControls.jsx# Shape, size, lifetime, rotation, trails
        │   ├── ColorControls.jsx   # Multi-stop gradient editor, alpha, blend modes
        │   ├── PhysicsControls.jsx # Gravity, friction, wind, max particles
        │   └── PresetLibrary.jsx   # Categorized browser with search + tag filter
        └── styles/
            └── lab.css             # Full dark theme matching game aesthetic
```

### Relationship to Game Client

The particle engine (`engine/` folder) is **zero-dependency pure JS** — copy-paste portable into `client/src/canvas/`. When we integrate:

1. Copy `engine/` → `client/src/canvas/particles/`
2. Load preset JSON files at runtime
3. Call `particleEngine.emit(presetName, x, y)` from `ArenaRenderer.js`
4. Engine updates + draws each frame inside `renderFrame()`

---

## 3. Particle Engine Design

### 3A — Particle Properties (Implemented ✅)

Each particle has these runtime properties:

| Property | Type | Description |
|----------|------|-------------|
| `x`, `y` | float | Position (pixels) |
| `vx`, `vy` | float | Velocity (px/sec) |
| `life` | float | Remaining life (1→0, normalized) |
| `age` | float | Elapsed seconds |
| `maxLife` | float | Total lifespan in seconds |
| `size` | float | Current radius/width |
| `rotation` | float | Current angle (radians) |
| `rotationSpeed` | float | Rotation velocity (rad/sec) |
| `color` | string | Current RGBA CSS color string |
| `alpha` | float | Current opacity (0–1) |
| `shape` | enum | `circle`, `square`, `triangle`, `star`, `line` |
| `trail` | array | Position history for trail rendering |

### 3B — Emitter Configuration (the JSON preset, Implemented ✅)

```json
{
  "name": "Combat Hit",
  "version": 1,
  "duration": 0.4,
  "loop": false,
  "tags": ["combat", "impact", "melee"],
  "emitter": {
    "spawnRate": 30,
    "burstCount": 15,
    "burstMode": true,
    "spawnShape": "point",
    "spawnRadius": 0,
    "angle": { "min": 0, "max": 360 },
    "speed": { "min": 40, "max": 120 },
    "gravity": { "x": 0, "y": 50 },
    "friction": 0.02,
    "wind": { "x": 0 }
  },
  "particle": {
    "lifetime": { "min": 0.2, "max": 0.6 },
    "shape": "circle",
    "size": {
      "start": { "min": 3, "max": 6 },
      "end": { "min": 0, "max": 1 },
      "easing": "easeOutQuad"
    },
    "color": {
      "gradient": [
        { "stop": 0.0, "color": "#ffffff" },
        { "stop": 0.3, "color": "#ffaa00" },
        { "stop": 1.0, "color": "#ff2200" }
      ]
    },
    "alpha": {
      "start": 1.0,
      "end": 0.0,
      "easing": "easeOutCubic"
    },
    "rotation": {
      "speed": { "min": -2, "max": 2 }
    },
    "trail": { "length": 0 },
    "blendMode": "lighter"
  }
}
```

### 3C — Spawn Shapes (Implemented ✅)

| Shape | Description |
|-------|-------------|
| `point` | All particles emit from a single point |
| `circle` | Random position within a circle radius (sqrt for uniform dist) |
| `ring` | Random position on the edge of a circle |
| `line` | Random position along a line segment |
| `rect` | Random position within a rectangle |

### 3D — Easing Functions (Implemented ✅)

12 easing curves available for size, alpha, and color transitions:

- `linear`
- `easeInQuad`, `easeOutQuad`, `easeInOutQuad`
- `easeInCubic`, `easeOutCubic`, `easeInOutCubic`
- `easeOutElastic`, `easeOutBounce`
- `easeInExpo`, `easeOutExpo`

### 3E — Blend Modes (Implemented ✅)

Canvas 2D `globalCompositeOperation` options:

| Mode | Use Case |
|------|----------|
| `source-over` | Default — standard layering |
| `lighter` | Additive — fire, magic, glow effects |
| `multiply` | Shadows, dark smoke |
| `screen` | Soft glow |

### 3F — Object Pooling (Implemented ✅)

The Emitter pre-allocates a pool of Particle objects (default 500). Dead particles are returned to the pool and recycled via `init()` rather than creating new objects, minimizing garbage collection pressure.

---

## 4. Lab UI Design

### 4A — Layout (Implemented ✅)

```
┌──────────────────────────────────────────────────────────────┐
│  Toolbar: [New] [Save] [Duplicate] [Undo] [Redo]            │
│           [Import] [Export] [Export All] [Copy] [Paste]      │
│           [🎲 Random]                        ● 18  60 FPS   │
├──────────────────────────────┬───────────────────────────────┤
│                              │  Preset Name: [_____________] │
│   Preview Canvas             │  Tags: [___________________]  │
│                              │                               │
│   - Dark background (#0d0d1a)│  Tab Bar:                     │
│   - 40px grid overlay        │  [Emitter] [Particle]         │
│   - Click anywhere to emit   │  [Colors]  [Physics]          │
│   - Auto-emit loop toggle    │                               │
│                              │  ┌───────────────────────┐    │
│                              │  │  Sliders, dropdowns,  │    │
│  ┌────────────────────────┐  │  │  color pickers,       │    │
│  │ [✓] Grid  [✓] Auto    │  │  │  range controls,      │    │
│  │ BG: [Dark ▾]          │  │  │  toggles              │    │
│  │ Speed: [1x ▾]         │  │  │                       │    │
│  └────────────────────────┘  │  └───────────────────────┘    │
│                              │                               │
│  Preset Library              │                               │
│  [Search...] [Tag filter ▾]  │                               │
│  ┌─ combat ──────────────┐   │                               │
│  │ ● melee-hit  [built-in]│  │                               │
│  │   ranged-hit [built-in]│  │                               │
│  │   critical-hit ...     │  │                               │
│  ├─ magic ───────────────┤   │                               │
│  │   heal-pulse ...       │  │                               │
│  └───────────────────────┘   │                               │
└──────────────────────────────┴───────────────────────────────┘
```

### 4B — Preview Canvas Features (Implemented ✅)

| Feature | Status |
|---------|--------|
| Dark background matching game's `#0d0d1a` | ✅ |
| 40px grid overlay (toggle with `G` key) | ✅ |
| Click-to-emit at any position | ✅ |
| Auto-emit loop with 0.3s cooldown (toggle with `L` key) | ✅ |
| Background options: Dark, Grid Only, Grey | ✅ |
| Speed control: 0.25x, 0.5x, 1x, 2x, 4x | ✅ |
| Live particle counter in toolbar | ✅ |
| Live FPS display (warns when < 30) | ✅ |
| Center crosshair (dashed lines) | ✅ |
| HiDPI / devicePixelRatio support | ✅ |
| Auto-resize to container | ✅ |

### 4C — Control Panel Tabs (Implemented ✅)

#### Tab: Emitter
| Control | Type | Status |
|---------|------|--------|
| Burst Mode toggle | Toggle | ✅ |
| Burst Count (1–200) | Slider | ✅ |
| Spawn Rate (1–500/sec) | Slider | ✅ |
| Duration (0.1–10s) | Slider | ✅ |
| Loop toggle | Toggle | ✅ |
| Spawn Shape (point/circle/ring/line/rect) | Dropdown | ✅ |
| Spawn Radius (0–100) | Slider | ✅ (contextual: circle/ring) |
| Spawn Width (0–200) | Slider | ✅ (contextual: line/rect) |
| Spawn Height (0–200) | Slider | ✅ (contextual: rect) |
| Emit Angle (0–360) | Range slider | ✅ |
| Speed range | Min/Max slider | ✅ |

#### Tab: Particle
| Control | Type | Status |
|---------|------|--------|
| Shape (circle/square/triangle/star/line) | Dropdown | ✅ |
| Lifetime range | Min/Max slider | ✅ |
| Start Size range | Min/Max slider | ✅ |
| End Size range | Min/Max slider | ✅ |
| Size Easing (12 curves) | Dropdown | ✅ |
| Rotation Speed range | Min/Max slider | ✅ |
| Trail Length (0–20) | Slider | ✅ |

#### Tab: Colors
| Control | Type | Status |
|---------|------|--------|
| Multi-stop color gradient | Gradient editor | ✅ |
| Add/remove color stops | Buttons | ✅ |
| Gradient preview bar | CSS preview | ✅ |
| Color pickers per stop | Native color input | ✅ |
| Stop position sliders | Slider per stop | ✅ |
| Blend Mode (lighter/source-over/screen/multiply) | Dropdown | ✅ |
| Alpha Start (0–1) | Slider | ✅ |
| Alpha End (0–1) | Slider | ✅ |
| Alpha Easing (9 curves) | Dropdown | ✅ |

#### Tab: Physics
| Control | Type | Status |
|---------|------|--------|
| Gravity X (-200–200) | Slider | ✅ |
| Gravity Y (-200–200) | Slider | ✅ |
| Friction (0–0.2) | Slider | ✅ |
| Wind X (-100–100) | Slider | ✅ |
| Max Particles (10–2000) | Slider | ✅ |

---

## 5. Preset Library

### 5A — Built-in Presets (15 shipped ✅)

#### Combat (6 presets)
| Preset | Description | Status |
|--------|-------------|--------|
| `melee-hit` | Orange-white sparks burst on impact | ✅ |
| `ranged-hit` | Smaller directional blue spark shower | ✅ |
| `critical-hit` | Oversized gold star burst | ✅ |
| `block` | Blue-grey shield squares + small debris | ✅ |
| `death-burst` | Red particles explode outward, fade to dark | ✅ |
| `blood-splatter` | Dark red drops with heavy gravity | ✅ |

#### Magic / Skills (7 presets)
| Preset | Description | Status |
|--------|-------------|--------|
| `heal-pulse` | Green particles rise upward, gentle glow | ✅ |
| `fire-blast` | Expanding orange-red burst + ember trail | ✅ |
| `ice-shard` | Blue-white spinning triangles scatter | ✅ |
| `poison-cloud` | Green fog particles, slow expanding drift | ✅ |
| `dark-bolt` | Purple-black streaking particles with trails | ✅ |
| `holy-smite` | Bright white-gold downward line rays | ✅ |
| `buff-aura` | Soft golden halo rising from ring spawn | ✅ |

#### Environment (2 presets)
| Preset | Description | Status |
|--------|-------------|--------|
| `torch-flame` | Continuous upward fire flicker (looping) | ✅ |
| `dust-motes` | Slow floating specks with wind (looping) | ✅ |

#### UI / Feedback (3 presets)
| Preset | Description | Status |
|--------|-------------|--------|
| `level-up` | Gold star burst rising upward | ✅ |
| `loot-sparkle` | Twinkling star particles (looping) | ✅ |
| `portal-swirl` | Circular vortex of blue-purple particles (looping) | ✅ |

### 5B — Preset Management (Implemented ✅)

| Feature | Status |
|---------|--------|
| Save to browser `localStorage` | ✅ |
| Load from library (click to select) | ✅ |
| Duplicate preset (fork with "(copy)" suffix) | ✅ |
| Delete user-created presets (built-ins are read-only) | ✅ |
| Tag-based filtering (dropdown) | ✅ |
| Name search (text input) | ✅ |
| Category grouping (combat, magic, environment, ui) | ✅ |
| Built-in badge + loop badge display | ✅ |
| Preset count indicator | ✅ |

---

## 6. Import / Export (Implemented ✅)

### 6A — Export Formats

| Format | Status |
|--------|--------|
| **Single JSON** — Export current preset as `{name}.json` | ✅ |
| **Export All** — All presets as `particle-presets.json` (game-ready bundle) | ✅ |
| **Clipboard** — Copy preset JSON to clipboard | ✅ |

### 6B — Import Methods

| Method | Status |
|--------|--------|
| **File picker** — Load `.json` file(s) from disk (single or array) | ✅ |
| **Clipboard paste** — Paste JSON from clipboard | ✅ |
| **Drag & drop** — Drag `.json` files onto the lab window | ✅ |
| **Conflict resolution** — Matching names overwrite user presets, skip built-ins | ✅ |

### 6C — Preset JSON Schema

A versioned schema (`"version": 1`) ensures forward compatibility. When we add features, we bump the version and add migration logic for older presets.

---

## 7. QoL Features

| Feature | Status | Notes |
|---------|--------|-------|
| **Undo / Redo** | ✅ | Full history stack (50 entries), Ctrl+Z / Ctrl+Y |
| **Real-time preview** | ✅ | All changes reflect instantly via requestAnimationFrame loop |
| **Randomize** | ✅ | 🎲 button generates random shapes, colors, physics, trails |
| **Parameter reset** | ✅ | Double-click any slider to reset to default value |
| **Keyboard shortcuts** | ✅ | G=grid, L=auto-emit, Ctrl+S=save, Ctrl+E=export, Ctrl+Z/Y=undo/redo |
| **Performance monitor** | ✅ | Live particle count + FPS in toolbar (red warning < 30 FPS) |
| **Dark theme** | ✅ | Matches game aesthetic (`#0d0d1a` background, muted UI) |
| **Tooltips** | ✅ | Title attributes on all controls with descriptions |
| **Background options** | ✅ | Dark / Grid Only / Grey selector |
| **Speed control** | ✅ | 0.25x–4x time scale via dropdown |
| **Frame-rate independence** | ✅ | All animation uses `deltaTime`, capped at 100ms to prevent spiral |

---

## 8. Integration Path (Future)

Once presets are designed, integrating into the game:

### Step 1: Copy Engine
```
client/src/canvas/particles/
├── ParticleEngine.js
├── Particle.js
├── Emitter.js
├── ParticleRenderer.js
└── MathUtils.js
```

### Step 2: Load Presets
```js
// In ArenaRenderer.js or a new ParticleManager
import { ParticleEngine } from './particles/ParticleEngine.js';

const particles = new ParticleEngine();
await particles.loadPresets('/particle-presets.json');
```

### Step 3: Trigger Effects
```js
// On melee hit
particles.emit('melee-hit', targetX * TILE_SIZE + 20, targetY * TILE_SIZE + 20);

// On heal
particles.emit('heal-pulse', casterX * TILE_SIZE + 20, casterY * TILE_SIZE + 20);

// Continuous torch
particles.emitContinuous('torch-flame', torchX * TILE_SIZE + 20, torchY * TILE_SIZE);
```

### Step 4: Update & Render
```js
function renderFrame() {
  // ... existing draw calls ...

  // After units, before fog
  particles.update(deltaTime);
  particles.render(ctx);
}
```

---

## 9. Implementation Phases

### Phase 9A — Core Engine + Lab UI ✅ COMPLETE
- [x] Particle, Emitter, ParticleEngine, ParticleRenderer classes
- [x] MathUtils with 12 easing curves, gradient sampling, spawn shapes
- [x] Object pooling in Emitter for particle recycling
- [x] Basic Canvas preview with click-to-emit
- [x] Emitter controls (burst/continuous, count, speed, angle, spawn shape)
- [x] Particle controls (shape, size, lifetime, rotation, trails)
- [x] Color gradient editor (multi-stop, add/remove)
- [x] Alpha start/end + easing selector
- [x] Blend mode selector (4 modes)
- [x] JSON export/import (single preset + bundle)

### Phase 9B — Presets + Physics ✅ COMPLETE
- [x] Physics tab (gravity X/Y, friction, wind, max particles)
- [x] 15 built-in presets across combat, magic, environment, UI categories
- [x] Preset library panel with search, tag filter, category grouping
- [x] Grid overlay toggle (40px game-scale)
- [x] Live particle count + FPS display in toolbar
- [x] Auto-emit loop mode
- [x] Background options (dark, grid, grey)
- [x] Speed control (0.25x–4x)

### Phase 9C — QoL ✅ COMPLETE
- [x] Undo/redo history (50-entry stack)
- [x] Keyboard shortcuts (G, L, Ctrl+S, Ctrl+E, Ctrl+Z, Ctrl+Y)
- [x] Randomize button (random shapes, colors, physics, trails)
- [x] Export All (game-ready bundle)
- [x] Drag & drop import
- [x] Clipboard copy/paste
- [x] Duplicate preset
- [x] Tooltips on all controls
- [x] Double-click slider to reset to default
- [x] localStorage persistence for user presets

### Phase 9D — Advanced Features (Future)
- [ ] Sub-emitters (spawn child effects on particle death)
- [ ] Pre-warm mode (start with particles already mid-flight)
- [ ] Noise/turbulence (per-frame random position jitter)
- [ ] Bounce off canvas floor (toggle + restitution slider)
- [ ] Cone spawn shape (directional emission for projectile trails)
- [ ] Sprite-based particles (load custom PNG textures)
- [ ] Compare mode (side-by-side canvas: original vs modified)
- [ ] Screenshot capture (export PNG snapshot of current effect)
- [ ] GIF recording (record a few seconds as animated GIF)
- [ ] Batch editing (select multiple presets, update shared parameter)
- [ ] Favorites (star presets for quick access)
- [ ] Easing curve visual preview (draw the curve shape next to dropdown)
- [ ] Import validation with field-level warnings
- [ ] Responsive/collapsible panels for smaller screens
- [ ] Thumbnail previews in preset library (mini canvas per preset)
- [ ] Preset versioning / migration logic for schema changes

### Phase 9E — Game Integration (Future)
- [ ] Copy engine into `client/src/canvas/particles/`
- [ ] ParticleManager wrapper with preset loading from `/particle-presets.json`
- [ ] Wire combat events → particle triggers in turn resolver results
- [ ] Wire skill effects → particle triggers (heal, fire, ice, etc.)
- [ ] Wire environment effects (torches, ambient dust in dungeons)
- [ ] Wire UI effects (level-up, loot sparkle replacing sine glow, portal)
- [ ] Performance profiling on large maps (25×25, many concurrent effects)
- [ ] Particle layer ordering (behind units vs in front of units vs above fog)

---

## 10. Additional Presets to Create (Future)

| Preset | Category | Description |
|--------|----------|-------------|
| `debuff-aura` | magic | Jagged red/dark particles orbiting a unit |
| `fog-wisps` | environment | Low horizontal drifting haze |
| `rain` | environment | Angled streaking line particles |
| `snow` | environment | Gentle floating white dots |
| `xp-gain` | ui | Small upward-floating gold trailing sparkles |
| `door-open` | environment | Dust cloud when a door opens |
| `chest-open` | ui | Sparkle burst when a chest is opened |
| `poison-tick` | combat | Small drip effect for damage-over-time |
| `fire-tick` | combat | Ember puff for burn damage |
| `teleport` | magic | Flash + dissolve scatter |
| `shield-up` | magic | Expanding ring + rising particles |
| `arrow-trail` | combat | Thin directional streak behind projectiles |
| `footstep-dust` | environment | Tiny puff when units move |
| `spawn-in` | ui | Materialization effect for spawned units |

---

## 11. Technical Constraints

| Constraint | Approach |
|------------|----------|
| **Canvas 2D only** | No WebGL — uses `globalCompositeOperation` for blend modes |
| **Performance** | Object pool capped at `maxParticles` (default 500, configurable to 2000) |
| **No new deps** | Engine is zero-dependency pure JS; lab uses React + Vite (same as game client) |
| **Tile-scale aware** | Grid overlay shows 40px tiles; effects designed at game scale |
| **Frame-rate independent** | All animation uses `deltaTime` (capped at 100ms max) |
| **Portable engine** | Engine code has no React/DOM dependency — copy-pasteable into game |
| **HiDPI support** | Canvas scales by `devicePixelRatio` for sharp rendering |

---

## 12. Startup

Run via batch file from project root:
```batch
start-particle-lab.bat
```

Or manually:
```bash
cd tools/particle-lab
npm install
npm run dev
```

Opens at `http://localhost:5180`.

---

## 13. Success Criteria

| Criteria | Status |
|----------|--------|
| Can create a new particle effect from scratch using the lab UI | ✅ |
| Can export a preset as JSON and re-import it without data loss | ✅ |
| 15 built-in presets covering combat, magic, environment, and UI | ✅ |
| Effects render on the game's dark background at 40px tile scale | ✅ |
| Engine handles 500+ simultaneous particles at 60fps | ✅ |
| Engine code designed for zero-modification drop into game client | ✅ |
| Undo/redo, keyboard shortcuts, and randomize for fast iteration | ✅ |
| Drag & drop + clipboard import/export for easy sharing | ✅ |

---

## 14. Files Created

| File | Purpose |
|------|---------|
| `tools/particle-lab/package.json` | React 18 + Vite 5 project config |
| `tools/particle-lab/vite.config.js` | Dev server on port 5180 with auto-open |
| `tools/particle-lab/index.html` | Entry point with dark base styles |
| `tools/particle-lab/src/main.jsx` | React root mount |
| `tools/particle-lab/src/App.jsx` | Root component: state, undo/redo, import/export, shortcuts |
| `tools/particle-lab/src/presets.js` | 15 built-in preset configurations |
| `tools/particle-lab/src/engine/MathUtils.js` | Lerp, easing, gradient, spawn shapes |
| `tools/particle-lab/src/engine/Particle.js` | Single particle lifecycle + physics |
| `tools/particle-lab/src/engine/Emitter.js` | Object-pooled emitter with burst/continuous |
| `tools/particle-lab/src/engine/ParticleEngine.js` | Multi-emitter manager + preset registry |
| `tools/particle-lab/src/engine/ParticleRenderer.js` | Canvas 2D drawing (5 shapes + trails) |
| `tools/particle-lab/src/components/Canvas.jsx` | Preview canvas with grid, auto-emit, stats |
| `tools/particle-lab/src/components/Toolbar.jsx` | Action buttons + live stats display |
| `tools/particle-lab/src/components/ControlPanel.jsx` | 4-tab master control panel |
| `tools/particle-lab/src/components/Controls.jsx` | Shared slider/range/select/toggle primitives |
| `tools/particle-lab/src/components/EmitterControls.jsx` | Emitter tab controls |
| `tools/particle-lab/src/components/ParticleControls.jsx` | Particle tab controls |
| `tools/particle-lab/src/components/ColorControls.jsx` | Color gradient + alpha + blend mode |
| `tools/particle-lab/src/components/PhysicsControls.jsx` | Gravity, friction, wind, max particles |
| `tools/particle-lab/src/components/PresetLibrary.jsx` | Categorized preset browser with search |
| `tools/particle-lab/src/styles/lab.css` | Full dark theme stylesheet |
| `start-particle-lab.bat` | One-click launcher from project root |
