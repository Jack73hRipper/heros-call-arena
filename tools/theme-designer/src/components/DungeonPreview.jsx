// ─────────────────────────────────────────────────────────
// DungeonPreview.jsx — Center panel: live dungeon preview
//
// Renders a sample dungeon map using the active theme.
// Supports zoom and displays tile type on hover.
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect, useState, useCallback } from 'react';
import { ThemeRenderer } from '../engine/themeRenderer.js';
import { getSampleMap, TILE_LEGEND } from '../engine/sampleMaps.js';

const BASE_TILE_SIZE = 48;

export default function DungeonPreview({ themeId, sampleMapId }) {
  const canvasRef = useRef(null);
  const rendererRef = useRef(new ThemeRenderer());
  const [zoom, setZoom] = useState(1);
  const [hoverTile, setHoverTile] = useState(null);

  const map = getSampleMap(sampleMapId);
  const tileSize = Math.round(BASE_TILE_SIZE * zoom);

  // Re-render when theme, map, or zoom changes
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const renderer = rendererRef.current;

    // Update renderer theme
    renderer.setTheme(themeId, tileSize);

    const canvasW = map.width * tileSize;
    const canvasH = map.height * tileSize;
    canvas.width = canvasW;
    canvas.height = canvasH;

    // Clear
    ctx.fillStyle = '#0a0a12';
    ctx.fillRect(0, 0, canvasW, canvasH);

    // Draw all tiles
    for (let y = 0; y < map.tiles.length; y++) {
      const row = map.tiles[y];
      for (let x = 0; x < row.length; x++) {
        const ch = row[x];
        const tileType = TILE_LEGEND[ch] || 'wall';
        const px = x * tileSize;
        const py = y * tileSize;

        const extra = {};
        // Doors default to closed, chests default to closed
        if (tileType === 'door') extra.doorOpen = false;
        if (tileType === 'chest') extra.chestOpened = false;

        renderer.drawTile(ctx, tileType, px, py, x, y, extra);
      }
    }

    // Draw hover highlight
    if (hoverTile) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
      ctx.lineWidth = 2;
      ctx.strokeRect(hoverTile.x * tileSize + 1, hoverTile.y * tileSize + 1, tileSize - 2, tileSize - 2);
    }
  }, [themeId, sampleMapId, tileSize, hoverTile]);

  const handleMouseMove = useCallback((e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const gx = Math.floor(mx / tileSize);
    const gy = Math.floor(my / tileSize);

    if (gx >= 0 && gx < map.width && gy >= 0 && gy < map.height) {
      const ch = map.tiles[gy]?.[gx];
      setHoverTile({ x: gx, y: gy, type: TILE_LEGEND[ch] || 'wall', char: ch });
    } else {
      setHoverTile(null);
    }
  }, [map, tileSize]);

  const handleMouseLeave = useCallback(() => {
    setHoverTile(null);
  }, []);

  return (
    <div className="dungeon-preview">
      <div className="preview-controls">
        <label>Zoom:</label>
        <input
          type="range"
          min="0.5"
          max="2"
          step="0.1"
          value={zoom}
          onChange={e => setZoom(parseFloat(e.target.value))}
        />
        <span>{Math.round(zoom * 100)}%</span>
        {hoverTile && (
          <span className="hover-info">
            [{hoverTile.x}, {hoverTile.y}] {hoverTile.type} ({hoverTile.char})
          </span>
        )}
      </div>
      <div className="preview-canvas-wrap">
        <canvas
          ref={canvasRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          style={{ imageRendering: 'pixelated', cursor: 'crosshair' }}
        />
      </div>
    </div>
  );
}
