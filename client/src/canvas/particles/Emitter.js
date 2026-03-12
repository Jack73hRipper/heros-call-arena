// ─────────────────────────────────────────────────────────
// Emitter.js — Particle emitter: spawning rules, shapes, rates
// Zero dependencies (uses MathUtils + Particle). Portable into game client.
// ─────────────────────────────────────────────────────────

import { Particle } from './Particle.js';
import { randomRange, getSpawnOffset, getEmitVelocity } from './MathUtils.js';

/**
 * An Emitter is a source of particles. It owns a pool of Particle objects
 * and manages their lifecycle (spawn, recycle, kill).
 *
 * Usage:
 *   const emitter = new Emitter(preset, x, y);
 *   emitter.start();
 *   // each frame:
 *   emitter.update(dt);
 *   // get live particles:
 *   emitter.particles.filter(p => p.alive)
 */
export class Emitter {
  /**
   * @param {object} preset - Full preset config (see preset schema)
   * @param {number} x - World X position
   * @param {number} y - World Y position
   */
  constructor(preset, x = 0, y = 0) {
    this.preset = preset;
    this.x = x;
    this.y = y;

    // Parse emitter config with defaults
    const em = preset.emitter || {};
    this.burstMode = em.burstMode !== undefined ? em.burstMode : true;
    this.burstCount = em.burstCount || 20;
    this.spawnRate = em.spawnRate || em.rate || 30; // particles per second (continuous)
    this.duration = preset.duration || 1;           // seconds
    this.loop = preset.loop !== undefined ? preset.loop : false;
    this.spawnShape = em.spawnShape || 'point';
    this.spawnRadius = em.spawnRadius || 0;
    this.spawnWidth = em.spawnWidth || 0;
    this.spawnHeight = em.spawnHeight || 0;
    this.angleMin = em.angle?.min ?? 0;
    this.angleMax = em.angle?.max ?? 360;
    this.speedMin = em.speed?.min ?? 20;
    this.speedMax = em.speed?.max ?? 80;

    // Global forces
    this.gravity = em.gravity || { x: 0, y: 0 };
    this.friction = em.friction || 0;
    this.wind = em.wind || { x: 0 };

    // Max particle cap (performance)
    this.maxParticles = preset.maxParticles || 500;

    // Object pool
    this.particles = [];
    this._pool = [];
    for (let i = 0; i < this.maxParticles; i++) {
      this._pool.push(new Particle());
    }

    // State
    this.elapsed = 0;
    this.active = false;
    this.finished = false;
    this._spawnAccum = 0; // fractional particle accumulator for continuous mode
  }

  /** Move the emitter to a new position. */
  moveTo(x, y) {
    this.x = x;
    this.y = y;
  }

  /**
   * Set a directed heading angle (radians). When set, the emitter's angle
   * range is re-centered so that 0° in the preset maps to this heading.
   * Used by ParticleProjectile to orient trail/head particles along the
   * flight path (e.g., arrow trails stream backward from the heading).
   * @param {number} headingRad — flight heading in radians (Math.atan2 convention)
   */
  setHeading(headingRad) {
    this._headingRad = headingRad;
  }

  /** Start (or restart) the emitter. */
  start() {
    this.elapsed = 0;
    this.active = true;
    this.finished = false;
    this._spawnAccum = 0;

    // Kill all existing particles
    for (const p of this.particles) {
      p.alive = false;
      this._pool.push(p);
    }
    this.particles = [];

    // If burst mode, spawn all particles immediately
    if (this.burstMode) {
      this._spawnBurst(this.burstCount);
    }
  }

  /** Stop the emitter (existing particles continue until they die). */
  stop() {
    this.active = false;
  }

  /**
   * Update the emitter and all its particles by dt seconds.
   * @param {number} dt - Delta time in seconds
   */
  update(dt) {
    if (this.finished && this.particles.length === 0) return;

    // Advance emitter timer
    if (this.active) {
      this.elapsed += dt;

      // Continuous spawn mode: accumulate and spawn
      if (!this.burstMode && this.active) {
        this._spawnAccum += this.spawnRate * dt;
        const count = Math.floor(this._spawnAccum);
        if (count > 0) {
          this._spawnBurst(count);
          this._spawnAccum -= count;
        }
      }

      // Check duration
      if (this.elapsed >= this.duration) {
        if (this.loop) {
          this.elapsed -= this.duration;
          if (this.burstMode) {
            this._spawnBurst(this.burstCount);
          }
        } else {
          this.active = false;
          this.finished = true;
        }
      }
    }

    // Update particles
    const forces = {
      gravityX: this.gravity.x,
      gravityY: this.gravity.y,
      friction: this.friction,
      windX: this.wind.x || 0,
    };

    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i];
      const alive = p.update(dt, forces);
      if (!alive) {
        // Return to pool
        this._pool.push(p);
        this.particles.splice(i, 1);
      }
    }
  }

  /** Spawn a batch of particles. */
  _spawnBurst(count) {
    const pc = this.preset.particle || {};

    for (let i = 0; i < count; i++) {
      if (this._pool.length === 0) break; // pool exhausted

      const p = this._pool.pop();

      // Spawn position
      const offset = getSpawnOffset(this.spawnShape, {
        radius: this.spawnRadius,
        width: this.spawnWidth,
        height: this.spawnHeight,
      });

      // Initial velocity — if a heading is set, offset the angle range so
      // the preset's angular spread is relative to the flight direction.
      let aMin = this.angleMin;
      let aMax = this.angleMax;
      if (this._headingRad !== undefined) {
        const headingDeg = this._headingRad * (180 / Math.PI);
        aMin = headingDeg + this.angleMin;
        aMax = headingDeg + this.angleMax;
      }
      const vel = getEmitVelocity(
        aMin, aMax,
        this.speedMin, this.speedMax
      );

      // Build particle config
      const cfg = {
        lifetime: randomRange(pc.lifetime?.min ?? 0.3, pc.lifetime?.max ?? 1.0),
        shape: pc.shape || 'circle',
        sizeStart: randomRange(pc.size?.start?.min ?? 3, pc.size?.start?.max ?? 6),
        sizeEnd: randomRange(pc.size?.end?.min ?? 0, pc.size?.end?.max ?? 1),
        sizeEasing: pc.size?.easing || 'linear',
        alphaStart: pc.alpha?.start ?? 1,
        alphaEnd: pc.alpha?.end ?? 0,
        alphaEasing: pc.alpha?.easing || 'easeOutCubic',
        gradient: pc.color?.gradient || null,
        rotationStart: randomRange(pc.rotation?.start?.min ?? 0, pc.rotation?.start?.max ?? 0),
        rotationSpeed: randomRange(pc.rotation?.speed?.min ?? 0, pc.rotation?.speed?.max ?? 0),
        trailLength: pc.trail?.length || 0,
      };

      // If heading is set, orient particles along the flight direction
      if (this._headingRad !== undefined) {
        cfg.rotationStart = this._headingRad;
      }

      p.init(this.x + offset.dx, this.y + offset.dy, vel.vx, vel.vy, cfg);
      this.particles.push(p);
    }
  }

  /** Get the number of currently alive particles. */
  get aliveCount() {
    return this.particles.length;
  }

  /** True if the emitter and all its particles are finished. */
  get isDead() {
    return this.finished && this.particles.length === 0;
  }

  /**
   * Apply a live preset update (for real-time editing in the lab).
   * Updates the emitter config without killing existing particles.
   */
  applyPreset(preset) {
    this.preset = preset;
    const em = preset.emitter || {};
    this.burstMode = em.burstMode !== undefined ? em.burstMode : true;
    this.burstCount = em.burstCount || 20;
    this.spawnRate = em.spawnRate || em.rate || 30;
    this.duration = preset.duration || 1;
    this.loop = preset.loop !== undefined ? preset.loop : false;
    this.spawnShape = em.spawnShape || 'point';
    this.spawnRadius = em.spawnRadius || 0;
    this.spawnWidth = em.spawnWidth || 0;
    this.spawnHeight = em.spawnHeight || 0;
    this.angleMin = em.angle?.min ?? 0;
    this.angleMax = em.angle?.max ?? 360;
    this.speedMin = em.speed?.min ?? 20;
    this.speedMax = em.speed?.max ?? 80;
    this.gravity = em.gravity || { x: 0, y: 0 };
    this.friction = em.friction || 0;
    this.wind = em.wind || { x: 0 };
    this.maxParticles = preset.maxParticles || 500;
  }
}
