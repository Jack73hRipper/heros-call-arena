// ─────────────────────────────────────────────────────────
// ModuleEditor.jsx — Canvas-based tile painter for editing modules
//
// Paint tiles on an 8×8 grid. Left-click to paint, right-click to erase (wall).
// Shows socket patterns derived from edges.
// Features: undo/redo, fill tool, drag-to-paint, rotation preview panel.
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect, useCallback, useState } from 'react';
import { MODULE_SIZE, deriveSockets, generateRotationVariants } from '../engine/moduleUtils.js';
import { TILE_COLORS, TILE_BORDERS, PAINT_TILES, TILE_LABELS } from '../utils/tileColors.js';

const CELL_PX = 56;     // pixels per cell in editor
const PAD = 40;          // padding around grid for socket labels
const GRID_PX = MODULE_SIZE * CELL_PX;

const MAX_UNDO = 50;

export default function ModuleEditor({ module, onModuleChange }) {
  const canvasRef = useRef(null);
  const [activeTile, setActiveTile] = useState('F');
  const [isPainting, setIsPainting] = useState(false);
  const [activeTool, setActiveTool] = useState('paint'); // 'paint' | 'fill'
  const [showRotations, setShowRotations] = useState(false);

  // Undo/Redo stacks — store tile state snapshots
  const undoStackRef = useRef([]);
  const redoStackRef = useRef([]);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  // Track current module id so we reset undo stacks on module switch
  const lastModuleIdRef = useRef(null);
  if (module && module.id !== lastModuleIdRef.current) {
    lastModuleIdRef.current = module.id;
    undoStackRef.current = [];
    redoStackRef.current = [];
  }

  const sockets = module ? deriveSockets(module.tiles) : null;

  // Push current state to undo stack before a change
  const pushUndo = useCallback(() => {
    if (!module) return;
    undoStackRef.current.push(module.tiles.map(row => [...row]));
    if (undoStackRef.current.length > MAX_UNDO) undoStackRef.current.shift();
    redoStackRef.current = []; // Clear redo on new action
    setCanUndo(true);
    setCanRedo(false);
  }, [module]);

  const handleUndo = useCallback(() => {
    if (!module || undoStackRef.current.length === 0) return;
    redoStackRef.current.push(module.tiles.map(row => [...row]));
    const prevTiles = undoStackRef.current.pop();
    onModuleChange({ ...module, tiles: prevTiles });
    setCanUndo(undoStackRef.current.length > 0);
    setCanRedo(true);
  }, [module, onModuleChange]);

  const handleRedo = useCallback(() => {
    if (!module || redoStackRef.current.length === 0) return;
    undoStackRef.current.push(module.tiles.map(row => [...row]));
    const nextTiles = redoStackRef.current.pop();
    onModuleChange({ ...module, tiles: nextTiles });
    setCanRedo(redoStackRef.current.length > 0);
    setCanUndo(true);
  }, [module, onModuleChange]);

  // Keyboard shortcuts for undo/redo
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        handleUndo();
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
        e.preventDefault();
        handleRedo();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleUndo, handleRedo]);

  // ── Draw the module grid ──
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !module) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;

    ctx.fillStyle = '#16162a';
    ctx.fillRect(0, 0, w, h);

    // Draw tiles
    for (let r = 0; r < MODULE_SIZE; r++) {
      for (let c = 0; c < MODULE_SIZE; c++) {
        const tile = module.tiles[r][c];
        const x = PAD + c * CELL_PX;
        const y = PAD + r * CELL_PX;

        // Fill
        ctx.fillStyle = TILE_COLORS[tile] || '#444';
        ctx.fillRect(x, y, CELL_PX, CELL_PX);

        // Border
        ctx.strokeStyle = TILE_BORDERS[tile] || '#333';
        ctx.lineWidth = 1;
        ctx.strokeRect(x + 0.5, y + 0.5, CELL_PX - 1, CELL_PX - 1);

        // Label
        ctx.fillStyle = '#ddd';
        ctx.font = 'bold 14px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(tile, x + CELL_PX / 2, y + CELL_PX / 2);
      }
    }

    // Draw grid lines
    ctx.strokeStyle = '#555';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= MODULE_SIZE; i++) {
      ctx.beginPath();
      ctx.moveTo(PAD + i * CELL_PX, PAD);
      ctx.lineTo(PAD + i * CELL_PX, PAD + GRID_PX);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(PAD, PAD + i * CELL_PX);
      ctx.lineTo(PAD + GRID_PX, PAD + i * CELL_PX);
      ctx.stroke();
    }

    // Draw socket labels
    if (sockets) {
      ctx.font = '11px monospace';
      ctx.fillStyle = '#aaa';
      ctx.textAlign = 'center';

      // North
      ctx.textBaseline = 'bottom';
      ctx.fillText(`N: ${sockets.north}`, PAD + GRID_PX / 2, PAD - 6);

      // South
      ctx.textBaseline = 'top';
      ctx.fillText(`S: ${sockets.south}`, PAD + GRID_PX / 2, PAD + GRID_PX + 6);

      // West
      ctx.save();
      ctx.translate(PAD - 8, PAD + GRID_PX / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.textBaseline = 'bottom';
      ctx.fillText(`W: ${sockets.west}`, 0, 0);
      ctx.restore();

      // East
      ctx.save();
      ctx.translate(PAD + GRID_PX + 8, PAD + GRID_PX / 2);
      ctx.rotate(Math.PI / 2);
      ctx.textBaseline = 'bottom';
      ctx.fillText(`E: ${sockets.east}`, 0, 0);
      ctx.restore();
    }
  }, [module, sockets]);

  useEffect(() => { draw(); }, [draw]);

  // ── Painting handlers ──
  const getTileCoords = useCallback((e) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const c = Math.floor((mx - PAD) / CELL_PX);
    const r = Math.floor((my - PAD) / CELL_PX);
    if (r >= 0 && r < MODULE_SIZE && c >= 0 && c < MODULE_SIZE) {
      return { r, c };
    }
    return null;
  }, []);

  const paintAt = useCallback((r, c, tileType) => {
    if (!module) return;

    if (activeTool === 'fill') {
      // Flood fill mode
      const target = module.tiles[r][c];
      if (target === tileType) return;
      const newTiles = module.tiles.map(row => [...row]);
      const queue = [{ r, c }];
      const visited = new Set();
      visited.add(`${r},${c}`);
      while (queue.length > 0) {
        const { r: cr, c: cc } = queue.shift();
        newTiles[cr][cc] = tileType;
        const neighbors = [
          { r: cr - 1, c: cc }, { r: cr + 1, c: cc },
          { r: cr, c: cc - 1 }, { r: cr, c: cc + 1 },
        ];
        for (const n of neighbors) {
          if (n.r < 0 || n.r >= MODULE_SIZE || n.c < 0 || n.c >= MODULE_SIZE) continue;
          const key = `${n.r},${n.c}`;
          if (visited.has(key)) continue;
          if (newTiles[n.r][n.c] !== target) continue;
          visited.add(key);
          queue.push(n);
        }
      }
      onModuleChange({ ...module, tiles: newTiles });
      return;
    }

    // Normal paint mode
    const newTiles = module.tiles.map(row => [...row]);
    if (newTiles[r][c] !== tileType) {
      newTiles[r][c] = tileType;
      onModuleChange({ ...module, tiles: newTiles });
    }
  }, [module, activeTool, onModuleChange]);

  // Track if we've pushed undo for current stroke
  const strokePushedRef = useRef(false);

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    const coords = getTileCoords(e);
    if (!coords) return;

    // Push undo at start of stroke (not per-tile)
    pushUndo();
    strokePushedRef.current = true;

    if (activeTool === 'fill') {
      const tileType = e.button === 2 ? 'W' : activeTile;
      paintAt(coords.r, coords.c, tileType);
      return;
    }

    setIsPainting(true);
    const tileType = e.button === 2 ? 'W' : activeTile;
    paintAt(coords.r, coords.c, tileType);
  }, [getTileCoords, activeTile, activeTool, paintAt, pushUndo]);

  const handleMouseMove = useCallback((e) => {
    if (!isPainting || activeTool === 'fill') return;
    const coords = getTileCoords(e);
    if (!coords) return;
    const tileType = e.buttons === 2 ? 'W' : activeTile;
    paintAt(coords.r, coords.c, tileType);
  }, [isPainting, activeTool, getTileCoords, activeTile, paintAt]);

  const handleMouseUp = useCallback(() => {
    setIsPainting(false);
    strokePushedRef.current = false;
  }, []);

  const handleContextMenu = useCallback((e) => {
    e.preventDefault();
  }, []);

  if (!module) {
    return (
      <div className="module-editor empty-editor">
        <p>Select a module from the library to edit, or create a new one.</p>
      </div>
    );
  }

  // Generate rotation variants for preview
  const rotationVariants = showRotations && module.allowRotation
    ? generateRotationVariants(module)
    : [];

  return (
    <div className="module-editor">
      <div className="editor-header">
        <h3>Module Editor</h3>
        <div className="module-meta">
          <label>
            Name:
            <input
              type="text"
              value={module.name}
              onChange={(e) => onModuleChange({ ...module, name: e.target.value })}
            />
          </label>
          <label>
            Purpose:
            <select
              value={module.purpose}
              onChange={(e) => onModuleChange({ ...module, purpose: e.target.value })}
            >
              <option value="empty">Empty</option>
              <option value="corridor">Corridor</option>
              <option value="spawn">Spawn</option>
              <option value="enemy">Enemy</option>
              <option value="loot">Loot</option>
              <option value="boss">Boss</option>
            </select>
          </label>
          <label>
            Weight:
            <input
              type="number"
              min="0.1"
              max="10"
              step="0.1"
              value={module.weight}
              onChange={(e) => onModuleChange({ ...module, weight: parseFloat(e.target.value) || 1.0 })}
            />
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={module.allowRotation}
              onChange={(e) => onModuleChange({ ...module, allowRotation: e.target.checked })}
            />
            Allow Rotation
          </label>
        </div>
      </div>

      {/* Tool bar: tile palette + tools */}
      <div className="tile-palette">
        {PAINT_TILES.map((t) => (
          <button
            key={t}
            className={`palette-btn ${activeTile === t ? 'active' : ''}`}
            style={{ backgroundColor: TILE_COLORS[t], borderColor: activeTile === t ? '#fff' : TILE_BORDERS[t] }}
            onClick={() => setActiveTile(t)}
            title={TILE_LABELS[t]}
          >
            {t}
          </button>
        ))}
        <span className="palette-divider">|</span>
        <button
          className={`tool-btn ${activeTool === 'paint' ? 'active' : ''}`}
          onClick={() => setActiveTool('paint')}
          title="Paint tool — click/drag to paint tiles"
        >
          ✏️
        </button>
        <button
          className={`tool-btn ${activeTool === 'fill' ? 'active' : ''}`}
          onClick={() => setActiveTool('fill')}
          title="Fill tool — click to flood-fill a region"
        >
          🪣
        </button>
        <span className="palette-divider">|</span>
        <button
          className="tool-btn"
          onClick={handleUndo}
          disabled={!canUndo}
          title="Undo (Ctrl+Z)"
        >
          ↩
        </button>
        <button
          className="tool-btn"
          onClick={handleRedo}
          disabled={!canRedo}
          title="Redo (Ctrl+Y)"
        >
          ↪
        </button>
        <span className="palette-hint">
          {activeTool === 'fill' ? 'Click to flood-fill region' : 'Left: paint | Right: erase'}
        </span>
      </div>

      {/* Canvas */}
      <canvas
        ref={canvasRef}
        width={GRID_PX + PAD * 2}
        height={GRID_PX + PAD * 2}
        className="editor-canvas"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onContextMenu={handleContextMenu}
      />

      {/* Rotation Preview Toggle */}
      {module.allowRotation && (
        <div className="rotation-section">
          <button
            className={`btn-rotation-toggle ${showRotations ? 'active' : ''}`}
            onClick={() => setShowRotations(prev => !prev)}
          >
            {showRotations ? 'Hide' : 'Show'} Rotation Variants ({rotationVariants.length || '...'})
          </button>
          {showRotations && rotationVariants.length > 0 && (
            <div className="rotation-previews">
              {rotationVariants.map((variant, i) => (
                <RotationPreview key={i} variant={variant} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Small canvas preview for a rotation variant */
function RotationPreview({ variant }) {
  const canvasRef = useRef(null);
  const THUMB_CELL = 12;
  const THUMB_SIZE = MODULE_SIZE * THUMB_CELL;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    for (let r = 0; r < MODULE_SIZE; r++) {
      for (let c = 0; c < MODULE_SIZE; c++) {
        const tile = variant.tiles[r]?.[c] || 'W';
        ctx.fillStyle = TILE_COLORS[tile] || '#444';
        ctx.fillRect(c * THUMB_CELL, r * THUMB_CELL, THUMB_CELL, THUMB_CELL);
        ctx.strokeStyle = TILE_BORDERS[tile] || '#333';
        ctx.lineWidth = 0.5;
        ctx.strokeRect(c * THUMB_CELL + 0.5, r * THUMB_CELL + 0.5, THUMB_CELL - 1, THUMB_CELL - 1);
      }
    }
  }, [variant]);

  const sockets = variant.sockets;

  return (
    <div className="rotation-preview-card">
      <canvas
        ref={canvasRef}
        width={THUMB_SIZE}
        height={THUMB_SIZE}
        className="rotation-thumb"
      />
      <div className="rotation-info">
        <span className="rotation-angle">{variant.rotation}°</span>
        <div className="rotation-sockets">
          <span title="North">N:{sockets.north}</span>
          <span title="South">S:{sockets.south}</span>
          <span title="East">E:{sockets.east}</span>
          <span title="West">W:{sockets.west}</span>
        </div>
      </div>
    </div>
  );
}
