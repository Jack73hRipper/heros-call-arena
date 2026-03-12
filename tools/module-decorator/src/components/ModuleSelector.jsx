// ─────────────────────────────────────────────────────────
// ModuleSelector.jsx — Left sidebar module list
//
// Displays all WFC modules with mini thumbnails showing
// their tile layout. Decorated modules show a green indicator.
// Supports filtering by purpose and importing custom modules.
// ─────────────────────────────────────────────────────────

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { TILE_COLORS } from '../utils/tileColors.js';
import { PURPOSE_COLORS } from '../utils/tileColors.js';
import { hasAnySprites, createEmptySpriteMap } from '../engine/spriteMap.js';

const THUMB_SIZE = 48;
const THUMB_CELL = THUMB_SIZE / 6; // 8px per cell for 6x6 modules

export default function ModuleSelector({
  modules,
  selectedModuleId,
  onSelectModule,
  spriteMaps,
  onImportModule,
}) {
  const [purposeFilter, setPurposeFilter] = useState('All');

  const purposes = ['All', ...new Set(modules.map(m => m.purpose))];

  const filtered = purposeFilter === 'All'
    ? modules
    : modules.filter(m => m.purpose === purposeFilter);

  // Import module from JSON file
  const handleImport = useCallback(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        try {
          const data = JSON.parse(ev.target.result);
          if (data.tiles && data.id) {
            onImportModule(data);
          } else {
            alert('Invalid module JSON — must have "id" and "tiles" fields.');
          }
        } catch (err) {
          alert('Failed to parse JSON: ' + err.message);
        }
      };
      reader.readAsText(file);
    };
    input.click();
  }, [onImportModule]);

  return (
    <div className="module-selector">
      <div className="selector-header">
        <h3>Modules</h3>
        <button className="small-btn" onClick={handleImport} title="Import module JSON">
          + Import
        </button>
      </div>

      <div className="purpose-filter">
        {purposes.map(p => (
          <button
            key={p}
            className={`purpose-btn ${purposeFilter === p ? 'active' : ''}`}
            onClick={() => setPurposeFilter(p)}
            style={p !== 'All' ? { borderColor: PURPOSE_COLORS[p] || '#666' } : {}}
          >
            {p.charAt(0).toUpperCase() + p.slice(1)}
            <span className="purpose-count">
              {p === 'All' ? modules.length : modules.filter(m => m.purpose === p).length}
            </span>
          </button>
        ))}
      </div>

      <div className="module-list">
        {filtered.map(mod => {
          const isDecorated = hasAnySprites(spriteMaps[mod.id] || createEmptySpriteMap(6, 6));
          const isSelected = mod.id === selectedModuleId;

          return (
            <div
              key={mod.id}
              className={`module-item ${isSelected ? 'selected' : ''} ${isDecorated ? 'decorated' : ''}`}
              onClick={() => onSelectModule(mod.id)}
            >
              <ModuleThumbnail tiles={mod.tiles} />
              <div className="module-info">
                <div className="module-name">{mod.name}</div>
                <div className="module-purpose" style={{ color: PURPOSE_COLORS[mod.purpose] || '#666' }}>
                  {mod.purpose}
                </div>
              </div>
              {isDecorated && <span className="decorated-badge" title="Has sprite assignments">✓</span>}
              {mod.allowRotation && <span className="rotation-badge" title="Allows rotation">↻</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Mini module thumbnail using tile colors
function ModuleThumbnail({ tiles }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !tiles) return;
    canvas.width = THUMB_SIZE;
    canvas.height = THUMB_SIZE;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, THUMB_SIZE, THUMB_SIZE);

    for (let row = 0; row < tiles.length; row++) {
      for (let col = 0; col < tiles[row].length; col++) {
        const tile = tiles[row][col];
        ctx.fillStyle = TILE_COLORS[tile] || '#333';
        ctx.fillRect(col * THUMB_CELL, row * THUMB_CELL, THUMB_CELL, THUMB_CELL);
      }
    }
  }, [tiles]);

  return <canvas ref={canvasRef} className="module-thumb" />;
}
