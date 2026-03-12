// ─────────────────────────────────────────────────────────
// PaletteEditor.jsx — Right sidebar: palette display
//
// Shows the current theme's color palette, style parameters,
// and per-tile-type detail breakdown. Read-only for now;
// future: editable palette with live preview updates.
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect } from 'react';
import { getTheme } from '../engine/themes.js';
import { ThemeRenderer } from '../engine/themeRenderer.js';

const TILE_PREVIEW_SIZE = 64;

/**
 * Renders a single tile type at large size for inspection.
 */
function TilePreview({ themeId, tileType, label }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const renderer = new ThemeRenderer();
    renderer.setTheme(themeId, TILE_PREVIEW_SIZE);
    ctx.fillStyle = '#0a0a12';
    ctx.fillRect(0, 0, TILE_PREVIEW_SIZE, TILE_PREVIEW_SIZE);
    renderer.drawTile(ctx, tileType, 0, 0, 3, 5);
  }, [themeId, tileType]);

  return (
    <div className="tile-preview">
      <canvas
        ref={canvasRef}
        width={TILE_PREVIEW_SIZE}
        height={TILE_PREVIEW_SIZE}
        style={{ width: TILE_PREVIEW_SIZE, height: TILE_PREVIEW_SIZE, imageRendering: 'pixelated', borderRadius: 3 }}
      />
      <span className="tile-label">{label}</span>
    </div>
  );
}

export default function PaletteEditor({ themeId }) {
  const theme = getTheme(themeId);
  if (!theme) return null;

  const paletteEntries = Object.entries(theme.palette);
  const wallParams = Object.entries(theme.wall || {}).filter(([k]) => k !== 'style');
  const floorParams = Object.entries(theme.floor || {}).filter(([k]) => k !== 'style');

  return (
    <div className="palette-editor">
      <h3 className="panel-title">Theme Details</h3>

      {/* Theme name & description */}
      <div className="theme-header">
        <div className="theme-full-name">{theme.name}</div>
        <div className="theme-full-desc">{theme.description}</div>
      </div>

      {/* Tile type previews at larger size */}
      <div className="section-label">Tile Previews</div>
      <div className="tile-previews-grid">
        <TilePreview themeId={themeId} tileType="wall" label="Wall" />
        <TilePreview themeId={themeId} tileType="floor" label="Floor" />
        <TilePreview themeId={themeId} tileType="corridor" label="Corridor" />
        <TilePreview themeId={themeId} tileType="spawn" label="Spawn" />
      </div>

      {/* Color palette */}
      <div className="section-label">Color Palette</div>
      <div className="palette-grid">
        {paletteEntries.map(([name, color]) => (
          <div key={name} className="palette-entry">
            <div className="palette-swatch" style={{ backgroundColor: color }} />
            <div className="palette-info">
              <span className="palette-name">{name}</span>
              <span className="palette-hex">{color}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Wall parameters */}
      <div className="section-label">Wall: {theme.wall?.style}</div>
      <div className="params-list">
        {wallParams.map(([key, val]) => (
          <div key={key} className="param-row">
            <span className="param-key">{key}</span>
            <span className="param-val">{typeof val === 'boolean' ? (val ? '✓' : '✗') : String(val)}</span>
          </div>
        ))}
      </div>

      {/* Floor parameters */}
      <div className="section-label">Floor: {theme.floor?.style}</div>
      <div className="params-list">
        {floorParams.map(([key, val]) => (
          <div key={key} className="param-row">
            <span className="param-key">{key}</span>
            <span className="param-val">{typeof val === 'boolean' ? (val ? '✓' : '✗') : String(val)}</span>
          </div>
        ))}
      </div>

      {/* Fog settings */}
      <div className="section-label">Fog of War</div>
      <div className="params-list">
        {Object.entries(theme.fog || {}).map(([key, val]) => (
          <div key={key} className="param-row">
            <span className="param-key">{key}</span>
            <span className="param-val">{val}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
