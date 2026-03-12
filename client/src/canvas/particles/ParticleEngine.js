// ─────────────────────────────────────────────────────────
// ParticleEngine.js — Top-level manager for emitters & rendering
// Zero dependencies. Portable into game client.
// ─────────────────────────────────────────────────────────

import { Emitter } from './Emitter.js';
import { ParticleRenderer } from './ParticleRenderer.js';

/**
 * ParticleEngine manages multiple concurrent emitters, updates them each
 * frame, and renders them all to a Canvas 2D context.
 *
 * Game integration usage:
 *   const engine = new ParticleEngine();
 *   engine.loadPresets(presetsJson);
 *   engine.emit('melee-hit', x, y);
 *   // in render loop:
 *   engine.update(dt);
 *   engine.render(ctx);
 *
 * Lab usage (single emitter, live editing):
 *   const engine = new ParticleEngine();
 *   const emitter = engine.createEmitter(preset, x, y);
 *   emitter.start();
 */
export class ParticleEngine {
  constructor() {
    /** @type {Map<string, object>} Preset library keyed by name */
    this.presets = new Map();

    /** @type {Emitter[]} Active emitters */
    this.emitters = [];

    /** @type {ParticleRenderer} */
    this.renderer = new ParticleRenderer();

    /** @type {number} Total alive particles across all emitters */
    this.totalParticles = 0;

    /** Speed multiplier for the entire engine (0.25x–4x) */
    this.timeScale = 1;

    /** Pause state */
    this.paused = false;
  }

  // ─── Preset Management ───

  /**
   * Load presets from a JSON array or object.
   * @param {Array|Object} data - Array of preset objects, or {name: preset} map
   */
  loadPresets(data) {
    if (Array.isArray(data)) {
      for (const preset of data) {
        if (preset.name) {
          this.presets.set(preset.name, preset);
        }
      }
    } else if (typeof data === 'object') {
      for (const [name, preset] of Object.entries(data)) {
        preset.name = preset.name || name;
        this.presets.set(name, preset);
      }
    }
  }

  /**
   * Register a single preset.
   * @param {object} preset - Preset config with a `name` field
   */
  addPreset(preset) {
    if (preset.name) {
      this.presets.set(preset.name, preset);
    }
  }

  /**
   * Get a preset by name.
   * @param {string} name
   * @returns {object|undefined}
   */
  getPreset(name) {
    return this.presets.get(name);
  }

  // ─── Emitter Lifecycle ───

  /**
   * Create and start an emitter from a named preset.
   * @param {string} presetName
   * @param {number} x - World X
   * @param {number} y - World Y
   * @returns {Emitter|null}
   */
  emit(presetName, x, y) {
    const preset = this.presets.get(presetName);
    if (!preset) {
      console.warn(`ParticleEngine: unknown preset "${presetName}"`);
      return null;
    }
    return this.createEmitter(preset, x, y, true);
  }

  /**
   * Create an emitter from a raw preset config.
   * @param {object} preset - Preset config object
   * @param {number} x
   * @param {number} y
   * @param {boolean} autoStart - Start immediately (default true)
   * @returns {Emitter}
   */
  createEmitter(preset, x = 0, y = 0, autoStart = true) {
    const emitter = new Emitter(preset, x, y);
    this.emitters.push(emitter);
    if (autoStart) emitter.start();
    return emitter;
  }

  /**
   * Remove a specific emitter immediately.
   * @param {Emitter} emitter
   */
  removeEmitter(emitter) {
    const idx = this.emitters.indexOf(emitter);
    if (idx !== -1) this.emitters.splice(idx, 1);
  }

  /** Remove all emitters and particles. */
  clear() {
    this.emitters = [];
    this.totalParticles = 0;
  }

  // ─── Frame Loop ───

  /**
   * Update all emitters and their particles.
   * @param {number} dt - Raw delta time in seconds
   */
  update(dt) {
    if (this.paused) return;

    const scaledDt = dt * this.timeScale;
    let total = 0;

    for (let i = this.emitters.length - 1; i >= 0; i--) {
      const emitter = this.emitters[i];
      emitter.update(scaledDt);
      total += emitter.aliveCount;

      // Auto-cleanup dead emitters (one-shot effects)
      if (emitter.isDead) {
        this.emitters.splice(i, 1);
      }
    }

    this.totalParticles = total;
  }

  /**
   * Render all emitters' particles to a canvas context.
   * @param {CanvasRenderingContext2D} ctx
   */
  render(ctx) {
    for (const emitter of this.emitters) {
      const blendMode = emitter.preset?.particle?.blendMode || 'lighter';
      this.renderer.render(ctx, emitter.particles, blendMode);
    }
  }
}
