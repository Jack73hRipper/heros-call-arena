// ─────────────────────────────────────────────────────────
// Toolbar.jsx — Top toolbar: map selector, export, info
// ─────────────────────────────────────────────────────────

import React, { useState } from 'react';
import { getSampleMapIds, getSampleMap } from '../engine/sampleMaps.js';
import { getTheme } from '../engine/themes.js';
import { GRID_SIZE_PRESETS, TEAM_COUNT_OPTIONS } from '../engine/pvpveGenerator.js';

export default function Toolbar({
  activeThemeId, sampleMapId, onSelectMap, onExportTheme,
  viewMode, onViewModeChange,
  pvpveConfig, onPvpveConfigChange,
}) {
  const mapIds = getSampleMapIds();
  const theme = getTheme(activeThemeId);
  const [generating, setGenerating] = useState(false);

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

  const handleGridSizeChange = (e) => {
    const preset = GRID_SIZE_PRESETS.find(p => p.label === e.target.value);
    if (preset && onPvpveConfigChange) {
      onPvpveConfigChange({ ...pvpveConfig, gridRows: preset.rows, gridCols: preset.cols });
    }
  };

  const handleTeamCountChange = (e) => {
    if (onPvpveConfigChange) {
      onPvpveConfigChange({ ...pvpveConfig, teamCount: Number(e.target.value) });
    }
  };

  const handleSeedChange = (e) => {
    const val = e.target.value.replace(/\D/g, '');
    const seed = Math.min(999999, Math.max(0, Number(val) || 0));
    if (onPvpveConfigChange) {
      onPvpveConfigChange({ ...pvpveConfig, seed });
    }
  };

  const handleRandomize = () => {
    const seed = Math.floor(Math.random() * 1000000);
    if (onPvpveConfigChange) {
      onPvpveConfigChange({ ...pvpveConfig, seed });
    }
  };

  const handleRegenerate = () => {
    setGenerating(true);
    // Trigger regeneration by bumping a regeneration counter
    if (onPvpveConfigChange) {
      onPvpveConfigChange({ ...pvpveConfig, _regen: (pvpveConfig._regen || 0) + 1 });
    }
    setTimeout(() => setGenerating(false), 300);
  };

  // Find current grid size label for dropdown
  const currentGridLabel = GRID_SIZE_PRESETS.find(
    p => p.rows === pvpveConfig?.gridRows && p.cols === pvpveConfig?.gridCols
  )?.label || '6×6';

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
          <button
            className={`toolbar-btn view-btn ${viewMode === 'pvpve' ? 'active' : ''}`}
            onClick={() => onViewModeChange('pvpve')}
          >
            PVPVE Dungeon
          </button>
        </div>

        {/* Sample map dropdown — only for dungeon preview mode */}
        {viewMode === 'dungeon' && (
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

        {/* PVPVE controls — only for pvpve mode */}
        {viewMode === 'pvpve' && pvpveConfig && (
          <div className="toolbar-pvpve-controls">
            <label className="toolbar-label">Grid:</label>
            <select
              value={currentGridLabel}
              onChange={handleGridSizeChange}
              className="toolbar-select"
            >
              {GRID_SIZE_PRESETS.map(p => (
                <option key={p.label} value={p.label}>{p.label}</option>
              ))}
            </select>

            <label className="toolbar-label">Teams:</label>
            <select
              value={pvpveConfig.teamCount}
              onChange={handleTeamCountChange}
              className="toolbar-select"
            >
              {TEAM_COUNT_OPTIONS.map(n => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>

            <label className="toolbar-label">Seed:</label>
            <input
              type="text"
              value={pvpveConfig.seed}
              onChange={handleSeedChange}
              className="toolbar-input"
              style={{ width: '70px' }}
              maxLength={6}
            />

            <button className="toolbar-btn" onClick={handleRandomize} title="Random seed">
              🎲
            </button>
            <button
              className="toolbar-btn regenerate-btn"
              onClick={handleRegenerate}
              disabled={generating}
              title="Regenerate dungeon"
            >
              {generating ? 'Generating...' : '⟳ Regenerate'}
            </button>
          </div>
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
