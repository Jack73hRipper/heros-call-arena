// ─────────────────────────────────────────────────────────
// EntityPanel.jsx — Paint tool palette + entity placement controls
// ─────────────────────────────────────────────────────────

import React from 'react';
import { PAINT_TILES, TILE_LABELS, TILE_COLORS } from '../utils/tileColors.js';

export default function EntityPanel({
  paintTile,
  onPaintTileChange,
  brushSize,
  onBrushSizeChange,
  showGrid,
  onShowGridChange,
  showRooms,
  onShowRoomsChange,
}) {
  return (
    <div className="panel entity-panel">
      <h3 className="panel-title">Paint Tools</h3>

      <div className="paint-palette">
        <button
          className={`paint-btn ${!paintTile ? 'active' : ''}`}
          onClick={() => onPaintTileChange(null)}
          title="No paint (navigate only)"
        >
          <span className="paint-swatch" style={{ background: '#555', border: '2px dashed #999' }} />
          <span className="paint-label">None</span>
        </button>
        {PAINT_TILES.map(tile => (
          <button
            key={tile}
            className={`paint-btn ${paintTile === tile ? 'active' : ''}`}
            onClick={() => onPaintTileChange(tile)}
            title={`Paint ${TILE_LABELS[tile]} tiles`}
          >
            <span className="paint-swatch" style={{ background: TILE_COLORS[tile] }} />
            <span className="paint-label">{TILE_LABELS[tile]}</span>
          </button>
        ))}
      </div>

      <div className="param-group">
        <label className="param-label">
          Brush Size: {brushSize}
          <input
            type="range"
            min={1}
            max={5}
            value={brushSize}
            onChange={e => onBrushSizeChange(parseInt(e.target.value))}
            className="input-range"
          />
        </label>
      </div>

      <h3 className="panel-title" style={{ marginTop: 16 }}>Display</h3>

      <div className="param-group">
        <label className="param-label checkbox-label">
          <input
            type="checkbox"
            checked={showGrid}
            onChange={e => onShowGridChange(e.target.checked)}
          />
          Show Grid Lines
        </label>
      </div>

      <div className="param-group">
        <label className="param-label checkbox-label">
          <input
            type="checkbox"
            checked={showRooms}
            onChange={e => onShowRoomsChange(e.target.checked)}
          />
          Show Room Overlays
        </label>
      </div>
    </div>
  );
}
