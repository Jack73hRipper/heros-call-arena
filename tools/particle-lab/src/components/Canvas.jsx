// ─────────────────────────────────────────────────────────
// Canvas.jsx — Particle preview canvas with grid, auto-emit, stats
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect, useCallback } from 'react';

const TILE_SIZE = 40;
const BG_DARK = '#0d0d1a';
const BG_GREY = '#2a2a2a';
const GRID_COLOR = 'rgba(255,255,255,0.06)';

export default function Canvas({ engine, preset, showGrid, autoEmit, timeScale, bgMode, onStatsUpdate }) {
  const canvasRef = useRef(null);
  const emitterRef = useRef(null);
  const rafRef = useRef(null);
  const lastTimeRef = useRef(0);
  const autoEmitTimerRef = useRef(0);
  const fpsFrames = useRef([]);

  // Compute background color
  const getBgColor = () => {
    switch (bgMode) {
      case 'grey': return BG_GREY;
      case 'grid': return '#111118';
      default: return BG_DARK;
    }
  };

  // ── Emitter management ──
  const restartEmitter = useCallback(() => {
    engine.clear();
    const canvas = canvasRef.current;
    if (!canvas) return;
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const emitter = engine.createEmitter(preset, cx, cy, true);
    emitterRef.current = emitter;
  }, [engine, preset]);

  // Restart emitter when preset changes
  useEffect(() => {
    restartEmitter();
  }, [preset, restartEmitter]);

  // Set time scale
  useEffect(() => {
    engine.timeScale = timeScale;
  }, [engine, timeScale]);

  // ── Click to emit ──
  const handleClick = useCallback((e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) * (canvas.width / rect.width);
    const y = (e.clientY - rect.top) * (canvas.height / rect.height);
    engine.createEmitter(preset, x, y, true);
  }, [engine, preset]);

  // ── Animation loop ──
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    // Size canvas to container
    const resize = () => {
      const container = canvas.parentElement;
      const dpr = window.devicePixelRatio || 1;
      const w = container.clientWidth;
      const h = container.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = w + 'px';
      canvas.style.height = h + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    lastTimeRef.current = performance.now();
    autoEmitTimerRef.current = 0;

    const frame = (now) => {
      const rawDt = (now - lastTimeRef.current) / 1000;
      const dt = Math.min(rawDt, 0.1); // cap to prevent spiral
      lastTimeRef.current = now;

      // FPS tracking
      fpsFrames.current.push(now);
      while (fpsFrames.current.length > 0 && fpsFrames.current[0] < now - 1000) {
        fpsFrames.current.shift();
      }
      const currentFps = fpsFrames.current.length;

      // Auto-emit: restart when effect finishes
      if (autoEmit) {
        const emitter = emitterRef.current;
        if (emitter && emitter.isDead) {
          autoEmitTimerRef.current += dt;
          if (autoEmitTimerRef.current >= 0.3) {
            autoEmitTimerRef.current = 0;
            restartEmitter();
          }
        }
      }

      // Update
      engine.update(dt);

      // Draw
      const w = canvas.width / (window.devicePixelRatio || 1);
      const h = canvas.height / (window.devicePixelRatio || 1);

      // Background
      ctx.fillStyle = getBgColor();
      ctx.fillRect(0, 0, w, h);

      // Grid overlay
      if (showGrid) {
        ctx.strokeStyle = GRID_COLOR;
        ctx.lineWidth = 1;
        for (let x = 0; x < w; x += TILE_SIZE) {
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, h);
          ctx.stroke();
        }
        for (let y = 0; y < h; y += TILE_SIZE) {
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(w, y);
          ctx.stroke();
        }

        // Center crosshair
        const cx = Math.floor(w / 2);
        const cy = Math.floor(h / 2);
        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(cx, 0);
        ctx.lineTo(cx, h);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(0, cy);
        ctx.lineTo(w, cy);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // Render particles
      engine.render(ctx);

      // Stats
      onStatsUpdate(engine.totalParticles, currentFps);

      rafRef.current = requestAnimationFrame(frame);
    };

    rafRef.current = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener('resize', resize);
    };
  }, [engine, preset, showGrid, autoEmit, timeScale, bgMode, onStatsUpdate, restartEmitter]);

  return (
    <div className="canvas-container">
      <canvas
        ref={canvasRef}
        className="preview-canvas"
        onClick={handleClick}
        title="Click anywhere to emit particles"
      />
    </div>
  );
}
