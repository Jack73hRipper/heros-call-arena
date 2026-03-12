// ─────────────────────────────────────────────────────────
// Toolbar.jsx — Top toolbar with generate, presets, and map size controls
// ─────────────────────────────────────────────────────────

import React from 'react';
import { PRESETS, SIZE_PRESETS } from '../engine/presets.js';

export default function Toolbar({
  mapWidth,
  mapHeight,
  onSizeChange,
  selectedPreset,
  onPresetChange,
  onGenerate,
  onClear,
  mapName,
  onMapNameChange,
}) {
  return (
    <div className="toolbar">
      <div className="toolbar-group">
        <span className="toolbar-title">Cave Automata Lab</span>
      </div>

      <div className="toolbar-group">
        <label>Map Name:</label>
        <input
          type="text"
          value={mapName}
          onChange={e => onMapNameChange(e.target.value)}
          className="input-text"
          placeholder="Cave Map"
        />
      </div>

      <div className="toolbar-group">
        <label>Size:</label>
        <select
          value={`${mapWidth}x${mapHeight}`}
          onChange={e => {
            const preset = SIZE_PRESETS.find(p => `${p.width}x${p.height}` === e.target.value);
            if (preset) onSizeChange(preset.width, preset.height);
          }}
          className="input-select"
        >
          {SIZE_PRESETS.map(p => (
            <option key={`${p.width}x${p.height}`} value={`${p.width}x${p.height}`}>
              {p.label}
            </option>
          ))}
        </select>
        <label style={{ marginLeft: 8 }}>W:</label>
        <input
          type="number"
          value={mapWidth}
          onChange={e => onSizeChange(parseInt(e.target.value) || 12, mapHeight)}
          className="input-number"
          min={8}
          max={100}
        />
        <label>H:</label>
        <input
          type="number"
          value={mapHeight}
          onChange={e => onSizeChange(mapWidth, parseInt(e.target.value) || 12)}
          className="input-number"
          min={8}
          max={100}
        />
      </div>

      <div className="toolbar-group">
        <label>Preset:</label>
        <select
          value={selectedPreset}
          onChange={e => onPresetChange(e.target.value)}
          className="input-select"
        >
          <option value="">-- Custom --</option>
          {PRESETS.map(p => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
      </div>

      <div className="toolbar-group">
        <button onClick={onGenerate} className="btn btn-primary" title="Generate cave (Enter)">
          Generate
        </button>
        <button onClick={onClear} className="btn btn-secondary" title="Clear map">
          Clear
        </button>
      </div>
    </div>
  );
}
