// ─────────────────────────────────────────────────────────
// Particle.js — Single particle data object + per-frame update
// Zero dependencies (uses MathUtils). Portable into game client.
// ─────────────────────────────────────────────────────────

import { lerp, clamp, getEasing, sampleGradient, rgbaToString } from './MathUtils.js';

/**
 * A single particle instance. Created by an Emitter, updated each frame,
 * rendered by ParticleRenderer. Uses an object-pool–friendly design:
 * call init() to reset rather than creating new objects.
 */
export class Particle {
  constructor() {
    this.alive = false;
    this.x = 0;
    this.y = 0;
    this.vx = 0;
    this.vy = 0;
    this.age = 0;       // seconds elapsed
    this.maxLife = 1;    // seconds total
    this.life = 1;       // normalized remaining life (1→0)

    // Visual properties — current values (mutated each frame)
    this.size = 4;
    this.alpha = 1;
    this.rotation = 0;
    this.rotationSpeed = 0;
    this.color = 'rgba(255,255,255,1)';
    this.shape = 'circle';  // circle | square | triangle | star | line

    // Configuration snapshot — set once at spawn by Emitter
    this._cfg = null;

    // Trail history (optional)
    this.trail = [];
    this._trailTimer = 0;
  }

  /**
   * Initialize (or recycle) this particle with the given configuration.
   * @param {number} x - Spawn X pixel position
   * @param {number} y - Spawn Y pixel position
   * @param {number} vx - Initial X velocity (px/sec)
   * @param {number} vy - Initial Y velocity (px/sec)
   * @param {object} cfg - Particle configuration from the preset
   */
  init(x, y, vx, vy, cfg) {
    this.alive = true;
    this.x = x;
    this.y = y;
    this.vx = vx;
    this.vy = vy;
    this.age = 0;
    this.maxLife = cfg.lifetime;
    this.life = 1;

    this.size = cfg.sizeStart;
    this.alpha = cfg.alphaStart;
    this.rotation = cfg.rotationStart || 0;
    this.rotationSpeed = cfg.rotationSpeed || 0;
    this.shape = cfg.shape || 'circle';

    this._cfg = cfg;

    this.trail = [];
    this._trailTimer = 0;
  }

  /**
   * Advance this particle by dt seconds.
   * @param {number} dt - Delta time in seconds
   * @param {object} forces - Global forces {gravityX, gravityY, friction, windX}
   * @returns {boolean} true if still alive
   */
  update(dt, forces = {}) {
    if (!this.alive) return false;

    // Age
    this.age += dt;
    if (this.age >= this.maxLife) {
      this.alive = false;
      return false;
    }

    const t = clamp(this.age / this.maxLife, 0, 1); // 0→1 over lifetime
    this.life = 1 - t;

    const cfg = this._cfg;

    // ── Physics ──
    const { gravityX = 0, gravityY = 0, friction = 0, windX = 0 } = forces;

    // Acceleration: gravity + wind
    this.vx += (gravityX + windX) * dt;
    this.vy += gravityY * dt;

    // Friction (velocity damping)
    if (friction > 0) {
      const damp = Math.pow(1 - friction, dt * 60); // frame-rate independent
      this.vx *= damp;
      this.vy *= damp;
    }

    // Position
    this.x += this.vx * dt;
    this.y += this.vy * dt;

    // ── Size ──
    if (cfg.sizeEasing) {
      const ease = getEasing(cfg.sizeEasing);
      this.size = lerp(cfg.sizeStart, cfg.sizeEnd, ease(t));
    } else {
      this.size = lerp(cfg.sizeStart, cfg.sizeEnd, t);
    }

    // ── Alpha ──
    if (cfg.alphaEasing) {
      const ease = getEasing(cfg.alphaEasing);
      this.alpha = lerp(cfg.alphaStart, cfg.alphaEnd, ease(t));
    } else {
      this.alpha = lerp(cfg.alphaStart, cfg.alphaEnd, t);
    }

    // ── Color gradient ──
    if (cfg.gradient && cfg.gradient.length > 0) {
      const rgba = sampleGradient(cfg.gradient, t);
      this.color = rgbaToString({ ...rgba, a: rgba.a * this.alpha });
    } else {
      // Single color mode — apply alpha
      this.color = `rgba(255, 200, 50, ${this.alpha})`;
    }

    // ── Rotation ──
    this.rotation += this.rotationSpeed * dt;

    // ── Trail ──
    if (cfg.trailLength && cfg.trailLength > 0) {
      this._trailTimer += dt;
      if (this._trailTimer >= 0.016) { // ~60fps sampling
        this._trailTimer = 0;
        this.trail.push({ x: this.x, y: this.y, alpha: this.alpha, size: this.size });
        if (this.trail.length > cfg.trailLength) {
          this.trail.shift();
        }
      }
    }

    return true;
  }
}
