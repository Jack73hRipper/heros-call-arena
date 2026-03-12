// ─────────────────────────────────────────────────────────
// ControlPanel.jsx — Tabbed parameter editor for preset config
// ─────────────────────────────────────────────────────────

import React, { useState } from 'react';
import EmitterControls from './EmitterControls.jsx';
import ParticleControls from './ParticleControls.jsx';
import ColorControls from './ColorControls.jsx';
import PhysicsControls from './PhysicsControls.jsx';

const TABS = [
  { id: 'emitter', label: 'Emitter' },
  { id: 'particle', label: 'Particle' },
  { id: 'colors', label: 'Colors' },
  { id: 'physics', label: 'Physics' },
];

export default function ControlPanel({ preset, updatePreset }) {
  const [activeTab, setActiveTab] = useState('emitter');

  return (
    <div className="control-panel">
      {/* Preset name editor */}
      <div className="control-group">
        <label className="control-label">Preset Name</label>
        <input
          type="text"
          className="control-input"
          value={preset.name}
          onChange={e => updatePreset(p => { p.name = e.target.value; })}
        />
      </div>

      {/* Tags editor */}
      <div className="control-group">
        <label className="control-label">Tags</label>
        <input
          type="text"
          className="control-input"
          value={(preset.tags || []).join(', ')}
          placeholder="combat, impact, fire..."
          onChange={e => updatePreset(p => {
            p.tags = e.target.value.split(',').map(t => t.trim()).filter(Boolean);
          })}
        />
      </div>

      {/* Tabs */}
      <div className="tab-bar">
        {TABS.map(tab => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="tab-content">
        {activeTab === 'emitter' && (
          <EmitterControls preset={preset} updatePreset={updatePreset} />
        )}
        {activeTab === 'particle' && (
          <ParticleControls preset={preset} updatePreset={updatePreset} />
        )}
        {activeTab === 'colors' && (
          <ColorControls preset={preset} updatePreset={updatePreset} />
        )}
        {activeTab === 'physics' && (
          <PhysicsControls preset={preset} updatePreset={updatePreset} />
        )}
      </div>
    </div>
  );
}
