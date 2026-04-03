// ─────────────────────────────────────────────────────────
// PerfTracker.js — Lightweight frame timing tracker
//
// Records frame times and computes rolling FPS/ms statistics
// for the DevOverlay performance panel. Singleton instance
// shared between the render loop (writes) and the overlay (reads).
// ─────────────────────────────────────────────────────────

const HISTORY_SIZE = 120; // frames of history for graph/stats

class PerfTracker {
  constructor() {
    this._frameTimes = new Float64Array(HISTORY_SIZE);
    this._head = 0;
    this._count = 0;
    this._lastTimestamp = 0;
    this._fps = 0;
    this._fpsFrameCount = 0;
    this._fpsLastUpdate = 0;
    this._min = Infinity;
    this._max = 0;
    this._minResetTime = 0;
  }

  /**
   * Record a frame render.
   * @param {number} renderMs - Time spent in renderFrame() (ms)
   * @param {number} timestamp - performance.now() at frame start
   */
  recordFrame(renderMs, timestamp) {
    // Store in ring buffer
    this._frameTimes[this._head] = renderMs;
    this._head = (this._head + 1) % HISTORY_SIZE;
    if (this._count < HISTORY_SIZE) this._count++;

    // FPS calculation (update once per second)
    this._fpsFrameCount++;
    if (timestamp - this._fpsLastUpdate >= 1000) {
      this._fps = this._fpsFrameCount;
      this._fpsFrameCount = 0;
      this._fpsLastUpdate = timestamp;
    }

    // Rolling min/max (reset every 5 seconds to stay responsive)
    if (timestamp - this._minResetTime > 5000) {
      this._min = renderMs;
      this._max = renderMs;
      this._minResetTime = timestamp;
    } else {
      if (renderMs < this._min) this._min = renderMs;
      if (renderMs > this._max) this._max = renderMs;
    }

    this._lastTimestamp = timestamp;
  }

  /** Get current stats snapshot for the overlay. */
  getStats() {
    // Average over recent frames
    let sum = 0;
    const count = Math.min(this._count, 60); // avg over last 60 frames
    for (let i = 0; i < count; i++) {
      const idx = (this._head - 1 - i + HISTORY_SIZE) % HISTORY_SIZE;
      sum += this._frameTimes[idx];
    }
    const avg = count > 0 ? sum / count : 0;

    // Current frame time (most recent)
    const current = this._count > 0
      ? this._frameTimes[(this._head - 1 + HISTORY_SIZE) % HISTORY_SIZE]
      : 0;

    return {
      fps: this._fps,
      frameMs: current,
      avgMs: avg,
      minMs: this._min === Infinity ? 0 : this._min,
      maxMs: this._max,
    };
  }

  /** Get the last N frame times for a sparkline graph. */
  getHistory(count = 60) {
    const result = [];
    const n = Math.min(count, this._count);
    for (let i = n - 1; i >= 0; i--) {
      const idx = (this._head - 1 - i + HISTORY_SIZE) % HISTORY_SIZE;
      result.push(this._frameTimes[idx]);
    }
    return result;
  }
}

/** Singleton instance — shared between render loop and DevOverlay. */
export const perfTracker = new PerfTracker();
