// ─────────────────────────────────────────────────────────
// ProjectileCanvas.jsx — Projectile preview canvas
// Shows a projectile traveling from point A → B with trail,
// optional head emitter, and impact effect on arrival.
// Endpoints are draggable for testing different distances/angles.
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect, useCallback, useState } from 'react';
import { ParticleProjectile } from '../engine/ParticleProjectile.js';

const TILE_SIZE = 40;
const BG_DARK = '#0d0d1a';
const BG_GREY = '#2a2a2a';
const GRID_COLOR = 'rgba(255,255,255,0.06)';
const HANDLE_RADIUS = 10;

export default function ProjectileCanvas({
  engine,
  projectileConfig,
  showGrid,
  autoEmit,
  timeScale,
  bgMode,
  onStatsUpdate,
  endpoints,
  onEndpointsChange,
  launchTrigger,
}) {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);
  const lastTimeRef = useRef(0);
  const autoEmitTimerRef = useRef(0);
  const fpsFrames = useRef([]);
  const projectileRef = useRef(null);
  const draggingRef = useRef(null); // 'start' | 'end' | null

  const getBgColor = () => {
    switch (bgMode) {
      case 'grey': return BG_GREY;
      case 'grid': return '#111118';
      default: return BG_DARK;
    }
  };

  // ── Launch a projectile ──
  const launchProjectile = useCallback(() => {
    // Clean up old projectile
    if (projectileRef.current && !projectileRef.current.isDead) {
      projectileRef.current.forceComplete();
    }
    engine.clear();

    const { trailPreset, headPreset, impactPreset, impactExtras, speed, arc } = projectileConfig;

    // Register presets with the engine if not already
    // (presets are loaded externally via engine.loadPresets or addPreset)

    const proj = new ParticleProjectile(engine, {
      trailPreset: trailPreset || null,
      headPreset: headPreset || null,
      fromX: endpoints.startX,
      fromY: endpoints.startY,
      toX: endpoints.endX,
      toY: endpoints.endY,
      speed: speed || 350,
      arc: arc || 0,
      onArrive: () => {
        // Fire impact effect at destination
        if (impactPreset) {
          engine.emit(impactPreset, endpoints.endX, endpoints.endY);
        }
        // Fire extras
        if (impactExtras && impactExtras.length > 0) {
          for (const extra of impactExtras) {
            if (extra) engine.emit(extra, endpoints.endX, endpoints.endY);
          }
        }
      },
    });

    projectileRef.current = proj;
  }, [engine, projectileConfig, endpoints]);

  // Set time scale
  useEffect(() => {
    engine.timeScale = timeScale;
  }, [engine, timeScale]);

  // Launch on external trigger (button press)
  useEffect(() => {
    if (launchTrigger > 0) {
      launchProjectile();
    }
  }, [launchTrigger]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Mouse interaction for draggable endpoints ──
  const getCanvasCoords = useCallback((e) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    return {
      x: (e.clientX - rect.left) * (canvas.width / rect.width) / dpr,
      y: (e.clientY - rect.top) * (canvas.height / rect.height) / dpr,
    };
  }, []);

  const handleMouseDown = useCallback((e) => {
    const { x, y } = getCanvasCoords(e);
    const dStart = Math.hypot(x - endpoints.startX, y - endpoints.startY);
    const dEnd = Math.hypot(x - endpoints.endX, y - endpoints.endY);

    if (dStart < HANDLE_RADIUS + 4) {
      draggingRef.current = 'start';
    } else if (dEnd < HANDLE_RADIUS + 4) {
      draggingRef.current = 'end';
    } else {
      draggingRef.current = null;
      // Click elsewhere: launch projectile
      launchProjectile();
    }
  }, [endpoints, getCanvasCoords, launchProjectile]);

  const handleMouseMove = useCallback((e) => {
    if (!draggingRef.current) return;
    const { x, y } = getCanvasCoords(e);
    const clamped = {
      x: Math.max(HANDLE_RADIUS, Math.min(x, (canvasRef.current?.width || 600) / (window.devicePixelRatio || 1) - HANDLE_RADIUS)),
      y: Math.max(HANDLE_RADIUS, Math.min(y, (canvasRef.current?.height || 400) / (window.devicePixelRatio || 1) - HANDLE_RADIUS)),
    };
    if (draggingRef.current === 'start') {
      onEndpointsChange({ ...endpoints, startX: clamped.x, startY: clamped.y });
    } else if (draggingRef.current === 'end') {
      onEndpointsChange({ ...endpoints, endX: clamped.x, endY: clamped.y });
    }
  }, [endpoints, getCanvasCoords, onEndpointsChange]);

  const handleMouseUp = useCallback(() => {
    draggingRef.current = null;
  }, []);

  // ── Draw endpoint handles and flight path ──
  const drawOverlays = useCallback((ctx, w, h) => {
    const { startX, startY, endX, endY } = endpoints;
    const { arc } = projectileConfig;

    // Dashed line showing flight path
    ctx.save();
    ctx.strokeStyle = 'rgba(255,255,255,0.12)';
    ctx.lineWidth = 1;
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    ctx.moveTo(startX, startY);

    // If arc > 0, draw parabolic path preview
    if (arc > 0) {
      const dist = Math.hypot(endX - startX, endY - startY);
      const steps = 30;
      for (let i = 1; i <= steps; i++) {
        const t = i / steps;
        const px = startX + (endX - startX) * t;
        const baseY = startY + (endY - startY) * t;
        const arcOff = -arc * dist * Math.sin(t * Math.PI);
        ctx.lineTo(px, baseY + arcOff);
      }
    } else {
      ctx.lineTo(endX, endY);
    }
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();

    // Distance label
    const dist = Math.hypot(endX - startX, endY - startY);
    const midX = (startX + endX) / 2;
    const midY = (startY + endY) / 2 - 12;
    ctx.save();
    ctx.font = '11px monospace';
    ctx.textAlign = 'center';
    ctx.fillStyle = 'rgba(255,255,255,0.35)';
    ctx.fillText(`${Math.round(dist)}px · ${(dist / TILE_SIZE).toFixed(1)} tiles`, midX, midY);
    // Travel time
    const speed = projectileConfig.speed || 350;
    const travelTime = Math.max(dist / speed, 0.06);
    ctx.fillText(`${(travelTime * 1000).toFixed(0)}ms`, midX, midY + 14);
    ctx.restore();

    // Start handle (green circle with ▶)
    ctx.save();
    ctx.beginPath();
    ctx.arc(startX, startY, HANDLE_RADIUS, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(68,170,102,0.25)';
    ctx.fill();
    ctx.strokeStyle = '#44aa66';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.font = 'bold 10px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#44aa66';
    ctx.fillText('A', startX, startY);
    ctx.restore();

    // End handle (red circle with ⬤)
    ctx.save();
    ctx.beginPath();
    ctx.arc(endX, endY, HANDLE_RADIUS, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(204,68,68,0.25)';
    ctx.fill();
    ctx.strokeStyle = '#cc4444';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.font = 'bold 10px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#cc4444';
    ctx.fillText('B', endX, endY);
    ctx.restore();

    // Active projectile progress indicator
    const proj = projectileRef.current;
    if (proj && !proj.complete) {
      const pct = Math.round(proj.progress * 100);
      ctx.save();
      ctx.font = '10px monospace';
      ctx.textAlign = 'left';
      ctx.fillStyle = 'rgba(255,255,255,0.4)';
      ctx.fillText(`Flight: ${pct}%`, 8, h - 8);
      ctx.restore();
    }
  }, [endpoints, projectileConfig]);

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

      // Update active projectile
      const proj = projectileRef.current;
      if (proj && !proj.complete) {
        proj.update(dt);
      }

      // Auto-emit: re-launch when projectile is done and all particles faded
      if (autoEmit) {
        const isDead = !proj || proj.isDead;
        const engineDead = engine.emitters.length === 0 || engine.emitters.every(e => e.isDead);
        if (isDead && engineDead) {
          autoEmitTimerRef.current += dt;
          if (autoEmitTimerRef.current >= 0.5) {
            autoEmitTimerRef.current = 0;
            launchProjectile();
          }
        }
      }

      // Update engine
      engine.update(dt);

      // Draw
      const w = canvas.width / (window.devicePixelRatio || 1);
      const h = canvas.height / (window.devicePixelRatio || 1);

      ctx.fillStyle = getBgColor();
      ctx.fillRect(0, 0, w, h);

      // Grid
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
      }

      // Overlays (path/handles)
      drawOverlays(ctx, w, h);

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
  }, [engine, projectileConfig, endpoints, showGrid, autoEmit, timeScale, bgMode, onStatsUpdate, launchProjectile, drawOverlays]);

  return (
    <div className="canvas-container">
      <canvas
        ref={canvasRef}
        className="preview-canvas"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        title="Drag A/B handles to reposition · Click anywhere to launch"
      />
    </div>
  );
}
