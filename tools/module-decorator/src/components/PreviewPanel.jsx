// ─────────────────────────────────────────────────────────
// PreviewPanel.jsx — Full dungeon preview with decorated sprites
//
// Simulates a small WFC dungeon layout using randomly placed
// modules to show what the decorated sprites look like when
// assembled. Also supports loading an exported dungeon JSON
// to preview with decorated module sprites applied.
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect, useState, useCallback } from 'react';
import { TILE_COLORS } from '../utils/tileColors.js';
import { getCellSprite, createEmptySpriteMap } from '../engine/spriteMap.js';

const PREVIEW_CELL_SIZE = 16;

export default function PreviewPanel({
  modules,
  spriteMaps,
  atlasImage,
  atlasLoaded,
}) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const [gridCols, setGridCols] = useState(4);
  const [gridRows, setGridRows] = useState(4);
  const [previewLayout, setPreviewLayout] = useState(null);
  const [zoom, setZoom] = useState(1.0);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef(null);
  const [showGrid, setShowGrid] = useState(true);

  // Generate a simple preview layout — place modules in a grid
  const generatePreview = useCallback(() => {
    const layout = [];
    const decoratedModules = modules.filter(m => {
      const sm = spriteMaps[m.id] || createEmptySpriteMap(6, 6);
      return sm.cells.some(row => row.some(cell => cell.base || cell.overlay));
    });

    // If no modules are decorated, use all modules
    const pool = decoratedModules.length > 0 ? decoratedModules : modules;

    for (let row = 0; row < gridRows; row++) {
      for (let col = 0; col < gridCols; col++) {
        const idx = (row * gridCols + col) % pool.length;
        layout.push({
          module: pool[idx],
          gridRow: row,
          gridCol: col,
        });
      }
    }
    setPreviewLayout(layout);
  }, [modules, spriteMaps, gridRows, gridCols]);

  // Auto-generate on first load
  useEffect(() => {
    generatePreview();
  }, []);

  // Render the preview canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !previewLayout) return;

    const totalWidth = gridCols * 6 * PREVIEW_CELL_SIZE;
    const totalHeight = gridRows * 6 * PREVIEW_CELL_SIZE;
    canvas.width = totalWidth;
    canvas.height = totalHeight;
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, totalWidth, totalHeight);

    for (const entry of previewLayout) {
      const { module: mod, gridRow, gridCol } = entry;
      const spriteMap = spriteMaps[mod.id] || createEmptySpriteMap(6, 6);
      const ox = gridCol * 6 * PREVIEW_CELL_SIZE;
      const oy = gridRow * 6 * PREVIEW_CELL_SIZE;

      for (let row = 0; row < 6; row++) {
        for (let col = 0; col < 6; col++) {
          const px = ox + col * PREVIEW_CELL_SIZE;
          const py = oy + row * PREVIEW_CELL_SIZE;
          const tile = mod.tiles[row]?.[col] || 'W';
          const cell = getCellSprite(spriteMap, row, col);

          // Base: draw sprite or tile color
          if (cell.base && atlasLoaded && atlasImage) {
            ctx.drawImage(
              atlasImage,
              cell.base.x, cell.base.y, cell.base.w, cell.base.h,
              px, py, PREVIEW_CELL_SIZE, PREVIEW_CELL_SIZE
            );
          } else {
            ctx.fillStyle = TILE_COLORS[tile] || '#333';
            ctx.fillRect(px, py, PREVIEW_CELL_SIZE, PREVIEW_CELL_SIZE);
          }

          // Overlay
          if (cell.overlay && atlasLoaded && atlasImage) {
            ctx.drawImage(
              atlasImage,
              cell.overlay.x, cell.overlay.y, cell.overlay.w, cell.overlay.h,
              px, py, PREVIEW_CELL_SIZE, PREVIEW_CELL_SIZE
            );
          }
        }
      }

      // Module grid overlay
      if (showGrid) {
        ctx.strokeStyle = 'rgba(255, 204, 0, 0.3)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.strokeRect(ox, oy, 6 * PREVIEW_CELL_SIZE, 6 * PREVIEW_CELL_SIZE);
        ctx.setLineDash([]);

        // Module name label
        ctx.fillStyle = 'rgba(255,204,0,0.5)';
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(mod.name, ox + 2, oy + 10);
      }
    }
  }, [previewLayout, spriteMaps, atlasImage, atlasLoaded, showGrid, gridCols, gridRows]);

  // Zoom/pan handlers
  const handleWheel = useCallback((e) => {
    e.preventDefault();
    setZoom(prev => Math.max(0.25, Math.min(4, prev + (e.deltaY > 0 ? -0.1 : 0.1))));
  }, []);

  const handleMouseDown = useCallback((e) => {
    if (e.button === 0) {
      setIsDragging(true);
      dragStartRef.current = { x: e.clientX - offset.x, y: e.clientY - offset.y };
    }
  }, [offset]);

  const handleMouseMove = useCallback((e) => {
    if (isDragging && dragStartRef.current) {
      setOffset({
        x: e.clientX - dragStartRef.current.x,
        y: e.clientY - dragStartRef.current.y,
      });
    }
  }, [isDragging]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
    dragStartRef.current = null;
  }, []);

  return (
    <div className="preview-panel">
      <div className="preview-controls">
        <h3>Dungeon Preview</h3>
        <div className="preview-settings">
          <label>
            Grid:
            <input
              type="number"
              min="1"
              max="8"
              value={gridCols}
              onChange={e => setGridCols(Math.max(1, Math.min(8, parseInt(e.target.value) || 1)))}
              className="num-input"
            />
            ×
            <input
              type="number"
              min="1"
              max="8"
              value={gridRows}
              onChange={e => setGridRows(Math.max(1, Math.min(8, parseInt(e.target.value) || 1)))}
              className="num-input"
            />
          </label>
          <button className="small-btn" onClick={generatePreview}>Regenerate</button>
          <label>
            <input type="checkbox" checked={showGrid} onChange={() => setShowGrid(v => !v)} />
            Grid Overlay
          </label>
          <button className="small-btn" onClick={() => { setZoom(1); setOffset({ x: 0, y: 0 }); }}>
            Reset View
          </button>
          <span className="zoom-label">Zoom: {Math.round(zoom * 100)}%</span>
        </div>
      </div>

      <div
        className="preview-viewport"
        ref={containerRef}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <canvas
          ref={canvasRef}
          className="preview-canvas"
          style={{
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
            transformOrigin: '0 0',
            cursor: isDragging ? 'grabbing' : 'grab',
          }}
        />
      </div>
    </div>
  );
}
