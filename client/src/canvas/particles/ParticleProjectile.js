// ─────────────────────────────────────────────────────────────────────────────
// ParticleProjectile.js — Lightweight ranged projectile that travels from
// caster to victim in pixel-space, emitting a trail of particles along the way.
//
// Phase 14G: Ranged Projectile Travel
//
// The projectile uses direct linear interpolation in pixel coordinates —
// it never snaps to the tile grid — so flight paths look smooth and natural.
// An optional `arc` parameter adds a parabolic vertical offset for physical
// projectiles (arrows lob, magic bolts fly flat).
//
// On arrival the projectile fires a callback so ParticleManager can trigger
// the impact effect at the destination.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * @typedef {Object} ProjectileConfig
 * @property {string}  trailPreset  — name of the continuous-emit trail preset
 * @property {string}  [headPreset] — name of a tight-burst preset rendered at the projectile tip
 * @property {number}  fromX        — start X in world pixels
 * @property {number}  fromY        — start Y in world pixels
 * @property {number}  toX          — end X in world pixels
 * @property {number}  toY          — end Y in world pixels
 * @property {number}  speed        — travel speed in pixels per second
 * @property {number}  [arc=0]      — parabolic arc height as a fraction of distance (0 = flat, 0.2 = gentle lob)
 * @property {Function} onArrive    — callback fired when projectile reaches destination
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

    // ── Derived values ──
    const dx = this.toX - this.fromX;
    const dy = this.toY - this.fromY;
    this.totalDistance = Math.hypot(dx, dy);

    // Guard against zero-distance projectiles (caster == victim same tile)
    const speed = config.speed || 400;
    const MIN_DURATION = 0.06; // ~3–4 frames at 60 fps
    this.duration = Math.max(this.totalDistance / speed, MIN_DURATION);

    // ── State ──
    this.elapsed = 0;
    this.progress = 0; // 0 → 1
    this.complete = false;

    // Current pixel position (updated each frame)
    this.x = this.fromX;
    this.y = this.fromY;

    // ── Heading angle ──
    // Compute the flight direction so trail/head emitters can orient along it.
    this.heading = Math.atan2(dy, dx); // radians, Math.atan2 convention

    // ── Trail emitter ──
    // Create a continuous looping emitter that follows the projectile.
    // It will be stopped when the projectile arrives.
    this.trailEmitter = null;
    if (config.trailPreset) {
      this.trailEmitter = engine.emit(config.trailPreset, this.fromX, this.fromY);
      // Ensure the trail stays alive for the full flight
      if (this.trailEmitter) {
        this.trailEmitter.loop = true;
        this.trailEmitter.setHeading(this.heading);
      }
    }

    // ── Head emitter ──
    // A tight, bright point emitter that stays locked to the projectile tip.
    // Gives the projectile a visible "head" — the trail is the ribbon behind it.
    this.headEmitter = null;
    if (config.headPreset) {
      this.headEmitter = engine.emit(config.headPreset, this.fromX, this.fromY);
      if (this.headEmitter) {
        this.headEmitter.loop = true;
        this.headEmitter.setHeading(this.heading);
      }
    }
  }

  /**
   * Advance the projectile by dt seconds.
   * @param {number} dt — delta time in seconds
   * @returns {boolean} true if still in flight, false if complete
   */
  update(dt) {
    if (this.complete) return false;

    this.elapsed += dt;
    this.progress = Math.min(this.elapsed / this.duration, 1);

    // ── Linear interpolation in pixel space ──
    this.x = this.fromX + (this.toX - this.fromX) * this.progress;

    // Base Y is linear
    const baseY = this.fromY + (this.toY - this.fromY) * this.progress;

    // Parabolic arc: peaks at progress = 0.5, returns to 0 at progress = 0 and 1
    // Negative offset = upward on screen (canvas Y increases downward)
    const arcOffset = this.arc > 0
      ? -this.arc * this.totalDistance * Math.sin(this.progress * Math.PI)
      : 0;

    this.y = baseY + arcOffset;

    // Move the trail emitter to follow the projectile
    if (this.trailEmitter) {
      this.trailEmitter.moveTo(this.x, this.y);
    }

    // Move the head emitter to the projectile tip
    if (this.headEmitter) {
      this.headEmitter.moveTo(this.x, this.y);
    }

    // ── Arrival ──
    if (this.progress >= 1) {
      this.complete = true;

      // Immediately stop the trail emitter from spawning new particles.
      // Setting loop=false alone would let the current duration cycle (up to 5s)
      // keep spawning — instead we fully stop so only existing particles fade out.
      if (this.trailEmitter) {
        this.trailEmitter.loop = false;
        this.trailEmitter.active = false;
        this.trailEmitter.finished = true;
      }

      // Immediately stop the head emitter
      if (this.headEmitter) {
        this.headEmitter.loop = false;
        this.headEmitter.active = false;
        this.headEmitter.finished = true;
      }

      // Fire the arrival callback (triggers impact effect)
      if (this.onArrive) {
        this.onArrive();
      }
    }

    return !this.complete;
  }

  /**
   * True when the projectile has arrived and its trail particles have all died.
   * Used by ParticleManager to clean up the projectile from its active list.
   */
  get isDead() {
    const trailDone = !this.trailEmitter || this.trailEmitter.isDead;
    const headDone = !this.headEmitter || this.headEmitter.isDead;
    return this.complete && trailDone && headDone;
  }

  /**
   * Force-complete the projectile immediately (e.g., on cleanup/destroy).
   */
  forceComplete() {
    if (this.complete) return;
    this.complete = true;
    if (this.trailEmitter) {
      this.trailEmitter.loop = false;
      this.trailEmitter.active = false;
      this.trailEmitter.finished = true;
    }
    if (this.headEmitter) {
      this.headEmitter.loop = false;
      this.headEmitter.active = false;
      this.headEmitter.finished = true;
    }
    if (this.onArrive) {
      this.onArrive();
    }
  }
}
