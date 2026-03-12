/**
 * PositionInterpolator — Smooth tile-to-tile movement for units.
 *
 * Tracks previous and target positions per unit ID, providing interpolated
 * (lerped) float coordinates each animation frame. This creates smooth visual
 * sliding between tiles instead of abrupt teleporting.
 *
 * Architecture:
 *   - On each TURN_RESULT, call update(players) with the new authoritative positions
 *   - On each rAF frame, call getInterpolatedPositions() to get float {x, y} per unit
 *   - Interpolation runs over LERP_DURATION_MS (first portion of the tick)
 *   - Units that didn't move, just spawned, or teleported (>1 tile jump) snap instantly
 *
 * Purely cosmetic — does not affect game logic or authoritative state.
 */

// Duration of the smooth slide in milliseconds.
// At 1-second ticks, 300ms gives a quick glide then rest for the remaining 700ms.
const LERP_DURATION_MS = 300;

// Max tile distance for interpolation. Moves larger than this snap instantly
// (e.g. Shadow Step, teleport, respawn, multi-tile jumps from lag).
const MAX_LERP_DISTANCE = 2;

class PositionInterpolator {
  constructor() {
    /** @type {Map<string, {prevX: number, prevY: number, targetX: number, targetY: number, startTime: number, duration: number}>} */
    this._entries = new Map();
  }

  /**
   * Feed new authoritative positions from a TURN_RESULT.
   * Compares against current targets to detect movement.
   *
   * @param {Object} players — { [unitId]: { position: {x, y}, is_alive, ... } }
   */
  update(players) {
    if (!players) return;

    const now = performance.now();
    const activeIds = new Set();

    for (const [id, p] of Object.entries(players)) {
      if (!p.position) continue;
      activeIds.add(id);

      const entry = this._entries.get(id);
      const newX = p.position.x;
      const newY = p.position.y;

      if (!entry) {
        // First time seeing this unit — snap immediately (no lerp)
        this._entries.set(id, {
          prevX: newX, prevY: newY,
          targetX: newX, targetY: newY,
          startTime: now,
          duration: 0, // 0 = already at target
        });
        continue;
      }

      // Check if the target position actually changed
      if (entry.targetX === newX && entry.targetY === newY) {
        // No change — unit didn't move this tick
        continue;
      }

      // Unit moved — compute distance to decide lerp vs snap
      const dx = newX - entry.targetX;
      const dy = newY - entry.targetY;
      const dist = Math.max(Math.abs(dx), Math.abs(dy)); // Chebyshev

      if (dist > MAX_LERP_DISTANCE) {
        // Teleport / large jump — snap immediately
        this._entries.set(id, {
          prevX: newX, prevY: newY,
          targetX: newX, targetY: newY,
          startTime: now,
          duration: 0,
        });
      } else {
        // Normal 1-tile move — lerp from current visual position to new target
        // Use the unit's current interpolated position as the lerp origin,
        // so mid-animation moves chain smoothly.
        const currentVisual = this._getLerpedPos(entry, now);
        this._entries.set(id, {
          prevX: currentVisual.x,
          prevY: currentVisual.y,
          targetX: newX,
          targetY: newY,
          startTime: now,
          duration: LERP_DURATION_MS,
        });
      }
    }

    // Clean up entries for units that no longer exist
    for (const id of this._entries.keys()) {
      if (!activeIds.has(id)) {
        this._entries.delete(id);
      }
    }
  }

  /**
   * Immediately snap a unit to its target position (skip any in-progress lerp).
   * Useful for death, extraction, or other instant-transition events.
   *
   * @param {string} unitId
   */
  snap(unitId) {
    const entry = this._entries.get(unitId);
    if (entry) {
      entry.prevX = entry.targetX;
      entry.prevY = entry.targetY;
      entry.duration = 0;
    }
  }

  /**
   * Get interpolated float positions for all tracked units.
   * Call this every animation frame.
   *
   * @returns {Map<string, {x: number, y: number}>}
   */
  getInterpolatedPositions() {
    const now = performance.now();
    const result = new Map();

    for (const [id, entry] of this._entries) {
      result.set(id, this._getLerpedPos(entry, now));
    }

    return result;
  }

  /**
   * Get interpolated position for a single unit.
   * Returns null if the unit isn't tracked.
   *
   * @param {string} unitId
   * @returns {{x: number, y: number} | null}
   */
  getPosition(unitId) {
    const entry = this._entries.get(unitId);
    if (!entry) return null;
    return this._getLerpedPos(entry, performance.now());
  }

  /**
   * Compute lerped position for an entry at a given time.
   * Uses ease-out cubic for a natural deceleration feel.
   *
   * @param {Object} entry
   * @param {number} now — performance.now() timestamp
   * @returns {{x: number, y: number}}
   */
  _getLerpedPos(entry, now) {
    if (entry.duration <= 0) {
      return { x: entry.targetX, y: entry.targetY };
    }

    const elapsed = now - entry.startTime;
    if (elapsed >= entry.duration) {
      return { x: entry.targetX, y: entry.targetY };
    }

    // Normalized progress [0, 1]
    const t = elapsed / entry.duration;
    // Ease-out cubic: 1 - (1 - t)^3  — fast start, smooth deceleration
    const eased = 1 - Math.pow(1 - t, 3);

    return {
      x: entry.prevX + (entry.targetX - entry.prevX) * eased,
      y: entry.prevY + (entry.targetY - entry.prevY) * eased,
    };
  }

  /**
   * Check if any unit is currently mid-interpolation (still animating).
   * Useful for deciding whether to keep the rAF loop hot.
   *
   * @returns {boolean}
   */
  isAnimating() {
    const now = performance.now();
    for (const entry of this._entries.values()) {
      if (entry.duration > 0 && (now - entry.startTime) < entry.duration) {
        return true;
      }
    }
    return false;
  }

  /**
   * Clear all tracked positions (e.g. on match end / leave).
   */
  clear() {
    this._entries.clear();
  }
}

// Singleton instance shared across the app
export const positionInterpolator = new PositionInterpolator();
export default PositionInterpolator;
