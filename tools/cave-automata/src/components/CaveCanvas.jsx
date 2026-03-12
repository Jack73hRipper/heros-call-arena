// ─────────────────────────────────────────────────────────
// CaveCanvas.jsx — Main canvas for cave rendering + painting
//
// Supports:
// - Rendering tile map with color-coded tiles
// - Room highlighting with color overlays
// - Pan (middle-click / Ctrl+drag) and zoom (scroll wheel)
// - Paint mode (left-click to place selected tile)
// - Hover coordinate display
// - Grid lines toggle
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect, useCallback, useState } from 'react';
import { TILE_COLORS, TILE_BORDERS, ROOM_COLORS } from '../utils/tileColors.js';

const MIN_CELL_SIZE = 4;
const MAX_CELL_SIZE = 64;
const DEFAULT_CELL_SIZE = 20;

export default function CaveCanvas({
  tileMap,
  rooms,
  showRooms,
  showGrid,
  paintTile,
  onPaintCell,
  brushSize,
}) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);

  // Viewport state
  const [cellSize, setCellSize] = useState(DEFAULT_CELL_SIZE);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0 });
  const offsetStart = useRef({ x: 0, y: 0 });

  // Hover state
  const [hoverCell, setHoverCell] = useState(null);

  // Painting state
  const [isPainting, setIsPainting] = useState(false);

  const mapHeight = tileMap.length;
  const mapWidth = tileMap[0]?.length || 0;

  // Build room lookup map for efficient rendering
  const roomMap = useRef(null);
  useEffect(() => {
    if (!showRooms || !rooms || rooms.length === 0) {
      roomMap.current = null;
      return;
    }
    const map = Array.from({ length: mapHeight }, () => new Array(mapWidth).fill(-1));
    rooms.forEach((room, idx) => {
      if (room.cells) {
        room.cells.forEach(c => {
          if (c.y >= 0 && c.y < mapHeight && c.x >= 0 && c.x < mapWidth) {
            map[c.y][c.x] = idx;
          }
        });
      }
    });
    roomMap.current = map;
  }, [rooms, showRooms, mapWidth, mapHeight]);

  // Render the canvas
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || mapWidth === 0 || mapHeight === 0) return;

    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#0e0e1a';
    ctx.fillRect(0, 0, w, h);

    // Draw tiles
    for (let y = 0; y < mapHeight; y++) {
      for (let x = 0; x < mapWidth; x++) {
        const px = offset.x + x * cellSize;
        const py = offset.y + y * cellSize;

        // Skip if off-screen
        if (px + cellSize < 0 || py + cellSize < 0 || px > w || py > h) continue;

        const tile = tileMap[y][x];
        ctx.fillStyle = TILE_COLORS[tile] || '#333';
        ctx.fillRect(px, py, cellSize, cellSize);

        // Room overlay
        if (showRooms && roomMap.current && roomMap.current[y][x] >= 0) {
          const roomIdx = roomMap.current[y][x];
          ctx.fillStyle = ROOM_COLORS[roomIdx % ROOM_COLORS.length];
          ctx.fillRect(px, py, cellSize, cellSize);
        }

        // Grid lines
        if (showGrid && cellSize >= 8) {
          ctx.strokeStyle = 'rgba(255,255,255,0.08)';
          ctx.lineWidth = 0.5;
          ctx.strokeRect(px, py, cellSize, cellSize);
        }
      }
    }

    // Draw map border
    ctx.strokeStyle = 'rgba(255,255,255,0.3)';
    ctx.lineWidth = 1;
    ctx.strokeRect(offset.x, offset.y, mapWidth * cellSize, mapHeight * cellSize);

    // Hover highlight
    if (hoverCell && hoverCell.x >= 0 && hoverCell.x < mapWidth && hoverCell.y >= 0 && hoverCell.y < mapHeight) {
      const halfBrush = Math.floor(brushSize / 2);
      for (let dy = -halfBrush; dy <= halfBrush; dy++) {
        for (let dx = -halfBrush; dx <= halfBrush; dx++) {
          const bx = hoverCell.x + dx;
          const by = hoverCell.y + dy;
          if (bx >= 0 && bx < mapWidth && by >= 0 && by < mapHeight) {
            const px = offset.x + bx * cellSize;
            const py = offset.y + by * cellSize;
            ctx.strokeStyle = 'rgba(255,255,255,0.6)';
            ctx.lineWidth = 2;
            ctx.strokeRect(px + 1, py + 1, cellSize - 2, cellSize - 2);
          }
        }
      }

      // Coordinate label
      ctx.fillStyle = 'rgba(0,0,0,0.7)';
      ctx.fillRect(offset.x + hoverCell.x * cellSize, offset.y + hoverCell.y * cellSize - 16, 60, 16);
      ctx.fillStyle = '#fff';
      ctx.font = '11px monospace';
      ctx.fillText(
        `${hoverCell.x},${hoverCell.y}`,
        offset.x + hoverCell.x * cellSize + 3,
        offset.y + hoverCell.y * cellSize - 4
      );
    }
  }, [tileMap, mapWidth, mapHeight, cellSize, offset, hoverCell, showRooms, showGrid, rooms, brushSize]);

  // Resize canvas to fill container
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const resize = () => {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
      render();
    };

    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();

    return () => observer.disconnect();
  }, [render]);

  // Re-render on state changes
  useEffect(() => {
    render();
  }, [render]);

  // Auto-fit on new map
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || mapWidth === 0 || mapHeight === 0) return;

    const fitW = (canvas.width - 40) / mapWidth;
    const fitH = (canvas.height - 40) / mapHeight;
    const fit = Math.max(MIN_CELL_SIZE, Math.min(MAX_CELL_SIZE, Math.floor(Math.min(fitW, fitH))));
    setCellSize(fit);
    setOffset({
      x: Math.floor((canvas.width - mapWidth * fit) / 2),
      y: Math.floor((canvas.height - mapHeight * fit) / 2),
    });
  }, [mapWidth, mapHeight]);

  // Convert mouse position to cell coordinates
  const mouseToCell = useCallback((e) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const cx = Math.floor((mx - offset.x) / cellSize);
    const cy = Math.floor((my - offset.y) / cellSize);
    if (cx >= 0 && cx < mapWidth && cy >= 0 && cy < mapHeight) {
      return { x: cx, y: cy };
    }
    return null;
  }, [offset, cellSize, mapWidth, mapHeight]);

  // Paint at a cell position with brush
  const paintAt = useCallback((cell) => {
    if (!cell || !paintTile || !onPaintCell) return;
    const halfBrush = Math.floor(brushSize / 2);
    for (let dy = -halfBrush; dy <= halfBrush; dy++) {
      for (let dx = -halfBrush; dx <= halfBrush; dx++) {
        const bx = cell.x + dx;
        const by = cell.y + dy;
        if (bx >= 0 && bx < mapWidth && by >= 0 && by < mapHeight) {
          onPaintCell(bx, by, paintTile);
        }
      }
    }
  }, [paintTile, onPaintCell, brushSize, mapWidth, mapHeight]);

  // Mouse handlers
  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    if (e.button === 1 || (e.button === 0 && e.ctrlKey)) {
      // Middle click or Ctrl+left click = pan
      setIsPanning(true);
      panStart.current = { x: e.clientX, y: e.clientY };
      offsetStart.current = { ...offset };
    } else if (e.button === 0 && paintTile) {
      // Left click = paint
      setIsPainting(true);
      const cell = mouseToCell(e);
      paintAt(cell);
    }
  }, [offset, paintTile, mouseToCell, paintAt]);

  const handleMouseMove = useCallback((e) => {
    if (isPanning) {
      const dx = e.clientX - panStart.current.x;
      const dy = e.clientY - panStart.current.y;
      setOffset({
        x: offsetStart.current.x + dx,
        y: offsetStart.current.y + dy,
      });
    } else {
      const cell = mouseToCell(e);
      setHoverCell(cell);
      if (isPainting && paintTile) {
        paintAt(cell);
      }
    }
  }, [isPanning, isPainting, paintTile, mouseToCell, paintAt]);

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
    if (isPainting) {
      setIsPainting(false);
    }
  }, [isPainting]);

  const handleWheel = useCallback((e) => {
    e.preventDefault();
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const oldSize = cellSize;
    const delta = e.deltaY > 0 ? -1 : 1;
    const step = Math.max(1, Math.floor(oldSize * 0.15));
    const newSize = Math.max(MIN_CELL_SIZE, Math.min(MAX_CELL_SIZE, oldSize + delta * step));

    if (newSize !== oldSize) {
      // Zoom toward mouse position
      const scale = newSize / oldSize;
      setOffset({
        x: mx - (mx - offset.x) * scale,
        y: my - (my - offset.y) * scale,
      });
      setCellSize(newSize);
    }
  }, [cellSize, offset]);

  const handleMouseLeave = useCallback(() => {
    setHoverCell(null);
    setIsPanning(false);
    setIsPainting(false);
  }, []);

  return (
    <div className="cave-canvas-container" ref={containerRef}>
      <canvas
        ref={canvasRef}
        className="cave-canvas"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onWheel={handleWheel}
        onContextMenu={e => e.preventDefault()}
      />
      <div className="canvas-overlay-info">
        {hoverCell ? `(${hoverCell.x}, ${hoverCell.y}) — ${tileMap[hoverCell.y]?.[hoverCell.x] || '?'}` : ''}
        {' | '}Zoom: {cellSize}px
      </div>
    </div>
  );
}
