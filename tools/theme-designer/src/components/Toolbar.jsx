// ─────────────────────────────────────────────────────────
// Toolbar.jsx — Top toolbar: map selector, export, info
// ─────────────────────────────────────────────────────────

import React from 'react';
import { getSampleMapIds, getSampleMap } from '../engine/sampleMaps.js';
import { getTheme } from '../engine/themes.js';

export default function Toolbar({ activeThemeId, sampleMapId, onSelectMap, onExportTheme, viewMode, onViewModeChange }) {
  const mapIds = getSampleMapIds();
  const theme = getTheme(activeThemeId);

  const handleExport = () => {
    if (!theme) return;
    const json = JSON.stringify(theme, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${theme.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
    if (onExportTheme) onExportTheme(theme.id);
  };

  return (
    <div className="toolbar">
      <div className="toolbar-left">
        <span className="toolbar-title">Dungeon Theme Designer</span>
        <span className="toolbar-subtitle">Arena MMO</span>
      </div>

      <div className="toolbar-center">
        <div className="toolbar-view-toggle">
          <button
            className={`toolbar-btn view-btn ${viewMode === 'dungeon' ? 'active' : ''}`}
            onClick={() => onViewModeChange('dungeon')}
          >
            Dungeon Preview
          </button>
          <button
            className={`toolbar-btn view-btn ${viewMode === 'archetypes' ? 'active' : ''}`}
            onClick={() => onViewModeChange('archetypes')}
          >
            Room Archetypes
          </button>
          <button
            className={`toolbar-btn view-btn ${viewMode === 'objects' ? 'active' : ''}`}
            onClick={() => onViewModeChange('objects')}
          >
            Object Browser
          </button>
        </div>
        {viewMode !== 'archetypes' && viewMode !== 'objects' && (
          <>
            <label className="toolbar-label">Sample Map:</label>
            <select
              value={sampleMapId}
              onChange={e => onSelectMap(e.target.value)}
              className="toolbar-select"
            >
              {mapIds.map(id => {
                const m = getSampleMap(id);
                return (
                  <option key={id} value={id}>
                    {m.name} ({m.width}×{m.height})
                  </option>
                );
              })}
            </select>
          </>
        )}
      </div>

      <div className="toolbar-right">
        <button className="toolbar-btn export-btn" onClick={handleExport}>
          Export Theme JSON
        </button>
      </div>
    </div>
  );
}
