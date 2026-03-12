// ─────────────────────────────────────────────────────────
// ModuleCanvas.jsx — Main 6×6 grid canvas for painting sprites
//
// Renders the module with three composited layers:
// 1. Base sprite layer (floor/wall art)
// 2. Overlay sprite layer (torches, decorations)
// 3. Gameplay layer (ghost tile type colors)
//
// Supports click-to-paint, drag-to-paint, and right-click-to-erase.
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect, useCallback, useState } from 'react';
import { TILE_COLORS, TILE_LABELS } from '../utils/tileColors.js';
import { getCellSprite } from '../engine/spriteMap.js';

const CANVAS_CELL_SIZE = 64; // Pixel size per cell on the editor canvas
const GRID_SIZE = 6;
const CANVAS_SIZE = CANVAS_CELL_SIZE * GRID_SIZE; // 384px

export default function ModuleCanvas({
  module,
  spriteMap,
  atlasImage,
  atlasLoaded,
  selectedSprite,
  activeLayer,
  showGameplayLayer,
  showBaseLayer,
  showOverlayLayer,
  baseOpacity,
  overlayOpacity,
  gameplayOpacity,
  onPaintCell,
  onEraseCell,
}) {
  const canvasRef = useRef(null);
  const [hoveredCell, setHoveredCell] = useState(null);
  const [isPainting, setIsPainting] = useState(false);
  const lastPaintedRef = useRef(null);

  // ─── Render the canvas ─────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !module) return;

    canvas.width = CANVAS_SIZE;
    canvas.height = CANVAS_SIZE;
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

    const tiles = module.tiles;

    for (let row = 0; row < GRID_SIZE; row++) {
      for (let col = 0; col < GRID_SIZE; col++) {
        const px = col * CANVAS_CELL_SIZE;
        const py = row * CANVAS_CELL_SIZE;
        const tile = tiles[row]?.[col] || 'W';
        const cell = spriteMap ? getCellSprite(spriteMap, row, col) : { base: null, overlay: null };

        // 1. Dark background
        ctx.fillStyle = '#111';
        ctx.fillRect(px, py, CANVAS_CELL_SIZE, CANVAS_CELL_SIZE);

        // 2. Base sprite layer
        if (showBaseLayer && cell.base && atlasLoaded && atlasImage) {
          ctx.globalAlpha = baseOpacity;
          ctx.drawImage(
            atlasImage,
            cell.base.x, cell.base.y, cell.base.w, cell.base.h,
            px, py, CANVAS_CELL_SIZE, CANVAS_CELL_SIZE
          );
          ctx.globalAlpha = 1.0;
        }

        // 3. Overlay sprite layer
        if (showOverlayLayer && cell.overlay && atlasLoaded && atlasImage) {
          ctx.globalAlpha = overlayOpacity;
          ctx.drawImage(
            atlasImage,
            cell.overlay.x, cell.overlay.y, cell.overlay.w, cell.overlay.h,
            px, py, CANVAS_CELL_SIZE, CANVAS_CELL_SIZE
          );
          ctx.globalAlpha = 1.0;
        }

        // 4. Gameplay type overlay (ghost)
        if (showGameplayLayer) {
          ctx.globalAlpha = gameplayOpacity;
          ctx.fillStyle = TILE_COLORS[tile] || '#333';
          ctx.fillRect(px, py, CANVAS_CELL_SIZE, CANVAS_CELL_SIZE);
          ctx.globalAlpha = 1.0;

          // Tile type label
          ctx.fillStyle = 'rgba(255,255,255,0.6)';
          ctx.font = 'bold 10px monospace';
          ctx.textAlign = 'center';
          ctx.fillText(tile, px + CANVAS_CELL_SIZE / 2, py + CANVAS_CELL_SIZE - 4);
        }

        // 5. Grid lines
        ctx.strokeStyle = 'rgba(255,255,255,0.1)';
        ctx.lineWidth = 1;
        ctx.strokeRect(px, py, CANVAS_CELL_SIZE, CANVAS_CELL_SIZE);
      }
    }

    // Hovered cell highlight
    if (hoveredCell) {
      const hx = hoveredCell.col * CANVAS_CELL_SIZE;
      const hy = hoveredCell.row * CANVAS_CELL_SIZE;
      ctx.strokeStyle = activeLayer === 'base' ? '#44aaff' : '#ff44aa';
      ctx.lineWidth = 2;
      ctx.strokeRect(hx + 1, hy + 1, CANVAS_CELL_SIZE - 2, CANVAS_CELL_SIZE - 2);

      // Show selected sprite preview in hovered cell
      if (selectedSprite && atlasLoaded && atlasImage) {
        ctx.globalAlpha = 0.5;
        ctx.drawImage(
          atlasImage,
          selectedSprite.x, selectedSprite.y, selectedSprite.w, selectedSprite.h,
          hx, hy, CANVAS_CELL_SIZE, CANVAS_CELL_SIZE
        );
        ctx.globalAlpha = 1.0;
      }
    }

    // Active layer indicator border
    ctx.strokeStyle = activeLayer === 'base' ? '#44aaff' : '#ff44aa';
    ctx.lineWidth = 3;
    ctx.strokeRect(1, 1, CANVAS_SIZE - 2, CANVAS_SIZE - 2);

  }, [module, spriteMap, atlasImage, atlasLoaded, hoveredCell, selectedSprite,
      activeLayer, showGameplayLayer, showBaseLayer, showOverlayLayer,
      baseOpacity, overlayOpacity, gameplayOpacity]);

  // ─── Mouse position → grid cell ────────────────────────
  const getCellFromEvent = useCallback((e) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const scaleX = CANVAS_SIZE / rect.width;
    const scaleY = CANVAS_SIZE / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;
    const col = Math.floor(x / CANVAS_CELL_SIZE);
    const row = Math.floor(y / CANVAS_CELL_SIZE);
    if (row >= 0 && row < GRID_SIZE && col >= 0 && col < GRID_SIZE) {
      return { row, col };
    }
    return null;
  }, []);

  // ─── Mouse handlers ────────────────────────────────────
  const handleMouseMove = useCallback((e) => {
    const cell = getCellFromEvent(e);
    setHoveredCell(cell);

    if (isPainting && cell) {
      const key = `${cell.row},${cell.col}`;
      if (lastPaintedRef.current !== key) {
        lastPaintedRef.current = key;
        if (e.buttons === 1) {
          onPaintCell(cell.row, cell.col);
        } else if (e.buttons === 2) {
          onEraseCell(cell.row, cell.col);
        }
      }
    }
  }, [getCellFromEvent, isPainting, onPaintCell, onEraseCell]);

  const handleMouseDown = useCallback((e) => {
    const cell = getCellFromEvent(e);
    if (!cell) return;

    setIsPainting(true);
    lastPaintedRef.current = `${cell.row},${cell.col}`;

    if (e.button === 0) {
      onPaintCell(cell.row, cell.col);
    } else if (e.button === 2) {
      onEraseCell(cell.row, cell.col);
    }
  }, [getCellFromEvent, onPaintCell, onEraseCell]);

  const handleMouseUp = useCallback(() => {
    setIsPainting(false);
    lastPaintedRef.current = null;
  }, []);

  const handleMouseLeave = useCallback(() => {
    setHoveredCell(null);
    setIsPainting(false);
    lastPaintedRef.current = null;
  }, []);

  const handleContextMenu = useCallback((e) => {
    e.preventDefault();
  }, []);

  if (!module) {
    return (
      <div className="module-canvas-empty">
        <p>Select a module from the left panel to begin decorating.</p>
      </div>
    );
  }

  return (
    <div className="module-canvas-container">
      <div className="canvas-header">
        <h3>{module.name}</h3>
        <span className="canvas-layer-label">
          Painting: <strong>{activeLayer === 'base' ? '🎨 Base Layer' : '✨ Overlay Layer'}</strong>
        </span>
      </div>
      <canvas
        ref={canvasRef}
        className="module-canvas"
        onMouseMove={handleMouseMove}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onContextMenu={handleContextMenu}
      />
      <div className="canvas-instructions">
        <span>Left-click: Paint</span>
        <span>Right-click: Erase</span>
        <span>Drag: Multi-paint</span>
      </div>
    </div>
  );
}
