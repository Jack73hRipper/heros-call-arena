// ─────────────────────────────────────────────────────────
// CompoundCanvas.jsx — Preview canvas for compound multi-layer effects
// Renders all visible layers simultaneously at the canvas center.
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect, useCallback } from 'react';

const TILE_SIZE = 40;
const BG_DARK = '#0d0d1a';
const BG_GREY = '#2a2a2a';
const GRID_COLOR = 'rgba(255,255,255,0.06)';

export default function CompoundCanvas({
  engine,
  layers,
  showGrid,
  autoEmit,
  timeScale,
  bgMode,
  onStatsUpdate,
}) {
  const canvasRef = useRef(null);
  const emittersRef = useRef([]); // Array of { layerIndex, emitter }
  const rafRef = useRef(null);
  const lastTimeRef = useRef(0);
  const autoEmitTimerRef = useRef(0);
  const fpsFrames = useRef([]);

  const getBgColor = () => {
    switch (bgMode) {
      case 'grey': return BG_GREY;
      case 'grid': return '#111118';
      default: return BG_DARK;
    }
  };

  // ── Emit all layers ──
  const emitAll = useCallback(() => {
    engine.clear();
    emittersRef.current = [];
    const canvas = canvasRef.current;
    if (!canvas) return;
    const cx = canvas.width / (window.devicePixelRatio || 1) / 2;
    const cy = canvas.height / (window.devicePixelRatio || 1) / 2;

    layers.forEach((layer, index) => {
      if (!layer.visible) return;
      const x = cx + (layer.offsetX || 0);
      const y = cy + (layer.offsetY || 0);
      const emitter = engine.createEmitter(layer.preset, x, y, true);
      emittersRef.current.push({ layerIndex: index, emitter });
    });
  }, [engine, layers]);

  // Re-emit when layers change
  useEffect(() => {
    emitAll();
  }, [layers, emitAll]);

  // Set time scale
  useEffect(() => {
    engine.timeScale = timeScale;
  }, [engine, timeScale]);

  // ── Click to emit at position ──
  const handleClick = useCallback((e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const x = (e.clientX - rect.left) * (canvas.width / rect.width) / dpr;
    const y = (e.clientY - rect.top) * (canvas.height / rect.height) / dpr;

    layers.forEach((layer) => {
      if (!layer.visible) return;
      const lx = x + (layer.offsetX || 0);
      const ly = y + (layer.offsetY || 0);
      engine.createEmitter(layer.preset, lx, ly, true);
    });
  }, [engine, layers]);

  // ── Animation loop ──
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

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
      const dt = Math.min(rawDt, 0.1);
      lastTimeRef.current = now;

      // FPS tracking
      fpsFrames.current.push(now);
      while (fpsFrames.current.length > 0 && fpsFrames.current[0] < now - 1000) {
        fpsFrames.current.shift();
      }
      const currentFps = fpsFrames.current.length;

      // Auto-emit: restart when all emitters are dead
      if (autoEmit) {
        const allDead = emittersRef.current.length === 0 ||
          emittersRef.current.every(e => e.emitter.isDead);
        if (allDead) {
          autoEmitTimerRef.current += dt;
          if (autoEmitTimerRef.current >= 0.3) {
            autoEmitTimerRef.current = 0;
            emitAll();
          }
        }
      }

      // Update engine
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
  }, [engine, layers, showGrid, autoEmit, timeScale, bgMode, onStatsUpdate, emitAll]);

  return (
    <div className="canvas-container">
      <canvas
        ref={canvasRef}
        className="preview-canvas"
        onClick={handleClick}
        title="Click anywhere to emit all layers"
      />
    </div>
  );
}
