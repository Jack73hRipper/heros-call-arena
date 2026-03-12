// ─────────────────────────────────────────────────────────
// ParticleProjectile.js — Lightweight ranged projectile (lab-local copy)
//
// Travels from point A → B emitting a trail, with optional parabolic arc.
// Fires a callback on arrival so the canvas can trigger the impact effect.
//
// This is a standalone copy for the particle-lab tool — the game client
// has its own copy in client/src/canvas/particles/ParticleProjectile.js.
// ─────────────────────────────────────────────────────────

/**
 * @typedef {Object} ProjectileConfig
 * @property {string}  trailPreset  — name of the continuous-emit trail preset
 * @property {string}  [headPreset] — name of a tight-burst preset for the projectile tip
 * @property {number}  fromX        — start X in pixels
 * @property {number}  fromY        — start Y in pixels
 * @property {number}  toX          — end X in pixels
 * @property {number}  toY          — end Y in pixels
 * @property {number}  speed        — travel speed in pixels per second
 * @property {number}  [arc=0]      — parabolic arc as fraction of distance (0 = flat)
 * @property {Function} onArrive    — callback fired on arrival
 */

export class ParticleProjectile {
  /**
   * @param {import('./ParticleEngine.js').ParticleEngine} engine
   * @param {ProjectileConfig} config
   */
  constructor(engine, config) {
    this.engine = engine;

    this.fromX = config.fromX;
    this.fromY = config.fromY;
    this.toX = config.toX;
    this.toY = config.toY;
    this.arc = config.arc ?? 0;
    this.onArrive = config.onArrive || null;

    const dx = this.toX - this.fromX;
    const dy = this.toY - this.fromY;
    this.totalDistance = Math.hypot(dx, dy);

    const speed = config.speed || 400;
    const MIN_DURATION = 0.06;
    this.duration = Math.max(this.totalDistance / speed, MIN_DURATION);

    this.elapsed = 0;
    this.progress = 0;
    this.complete = false;

    this.x = this.fromX;
    this.y = this.fromY;

    // Trail emitter
    this.trailEmitter = null;
    if (config.trailPreset) {
      this.trailEmitter = engine.emit(config.trailPreset, this.fromX, this.fromY);
      if (this.trailEmitter) {
        this.trailEmitter.loop = true;
      }
    }

    // Head emitter
    this.headEmitter = null;
    if (config.headPreset) {
      this.headEmitter = engine.emit(config.headPreset, this.fromX, this.fromY);
      if (this.headEmitter) {
        this.headEmitter.loop = true;
      }
    }
  }

  update(dt) {
    if (this.complete) return false;

    this.elapsed += dt;
    this.progress = Math.min(this.elapsed / this.duration, 1);

    this.x = this.fromX + (this.toX - this.fromX) * this.progress;

    const baseY = this.fromY + (this.toY - this.fromY) * this.progress;
    const arcOffset = this.arc > 0
      ? -this.arc * this.totalDistance * Math.sin(this.progress * Math.PI)
      : 0;
    this.y = baseY + arcOffset;

    if (this.trailEmitter) {
      this.trailEmitter.moveTo(this.x, this.y);
    }
    if (this.headEmitter) {
      this.headEmitter.moveTo(this.x, this.y);
    }

    if (this.progress >= 1) {
      this.complete = true;
      if (this.trailEmitter) this.trailEmitter.loop = false;
      if (this.headEmitter) this.headEmitter.loop = false;
      if (this.onArrive) this.onArrive();
    }

    return !this.complete;
  }

  get isDead() {
    const trailDone = !this.trailEmitter || this.trailEmitter.isDead;
    const headDone = !this.headEmitter || this.headEmitter.isDead;
    return this.complete && trailDone && headDone;
  }

  forceComplete() {
    if (this.complete) return;
    this.complete = true;
    if (this.trailEmitter) this.trailEmitter.loop = false;
    if (this.headEmitter) this.headEmitter.loop = false;
    if (this.onArrive) this.onArrive();
  }
}
