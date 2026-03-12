// ─────────────────────────────────────────────────────────
// Toolbar.jsx — Top toolbar: map selector, export, info
// ─────────────────────────────────────────────────────────

import React from 'react';
import { getSampleMapIds, getSampleMap } from '../engine/sampleMaps.js';
import { getTheme } from '../engine/themes.js';

export default function Toolbar({ activeThemeId, sampleMapId, onSelectMap, onExportTheme }) {
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
      </div>

      <div className="toolbar-right">
        <button className="toolbar-btn export-btn" onClick={handleExport}>
          Export Theme JSON
        </button>
      </div>
    </div>
  );
}
