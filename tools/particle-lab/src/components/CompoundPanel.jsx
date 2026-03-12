// ─────────────────────────────────────────────────────────
// CompoundPanel.jsx — Multi-layer compound effect editor
// Stack multiple presets to preview as a single compound effect.
// ─────────────────────────────────────────────────────────

import React, { useState, useCallback } from 'react';

/**
 * @param {Object} props
 * @param {Array} props.layers - Array of { id, presetName, visible, preset }
 * @param {Function} props.onLayersChange - (newLayers) => void
 * @param {Array} props.presetLibrary - All available presets
 * @param {number|null} props.activeLayerIndex - Currently selected layer for editing
 * @param {Function} props.onSelectLayer - (index) => void
 */
export default function CompoundPanel({
  layers,
  onLayersChange,
  presetLibrary,
  activeLayerIndex,
  onSelectLayer,
}) {
  const [showAddDropdown, setShowAddDropdown] = useState(false);
  const [addSearch, setAddSearch] = useState('');

  // ── Add layer ──
  const addLayer = useCallback((presetName) => {
    const preset = presetLibrary.find(p => p.name === presetName);
    if (!preset) return;
    const newLayer = {
      id: Date.now() + Math.random(),
      presetName: preset.name,
      visible: true,
      preset: JSON.parse(JSON.stringify(preset)),
      offsetX: 0,
      offsetY: 0,
    };
    onLayersChange([...layers, newLayer]);
    setShowAddDropdown(false);
    setAddSearch('');
  }, [layers, onLayersChange, presetLibrary]);

  // ── Remove layer ──
  const removeLayer = useCallback((index) => {
    const next = layers.filter((_, i) => i !== index);
    onLayersChange(next);
    if (activeLayerIndex === index) {
      onSelectLayer(next.length > 0 ? Math.min(index, next.length - 1) : null);
    } else if (activeLayerIndex > index) {
      onSelectLayer(activeLayerIndex - 1);
    }
  }, [layers, onLayersChange, activeLayerIndex, onSelectLayer]);

  // ── Toggle visibility ──
  const toggleVisibility = useCallback((index) => {
    const next = layers.map((l, i) =>
      i === index ? { ...l, visible: !l.visible } : l
    );
    onLayersChange(next);
  }, [layers, onLayersChange]);

  // ── Reorder ──
  const moveLayer = useCallback((index, direction) => {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= layers.length) return;
    const next = [...layers];
    [next[index], next[newIndex]] = [next[newIndex], next[index]];
    onLayersChange(next);
    if (activeLayerIndex === index) onSelectLayer(newIndex);
    else if (activeLayerIndex === newIndex) onSelectLayer(index);
  }, [layers, onLayersChange, activeLayerIndex, onSelectLayer]);

  // ── Duplicate layer ──
  const duplicateLayer = useCallback((index) => {
    const source = layers[index];
    const copy = {
      ...source,
      id: Date.now() + Math.random(),
      presetName: source.presetName + ' (copy)',
      preset: JSON.parse(JSON.stringify(source.preset)),
    };
    const next = [...layers];
    next.splice(index + 1, 0, copy);
    onLayersChange(next);
  }, [layers, onLayersChange]);

  // ── Update layer offset ──
  const updateOffset = useCallback((index, axis, value) => {
    const next = layers.map((l, i) =>
      i === index ? { ...l, [axis]: value } : l
    );
    onLayersChange(next);
  }, [layers, onLayersChange]);

  // ── Export as effect-map entry ──
  const exportEffectMapEntry = useCallback(() => {
    if (layers.length === 0) return;
    const primary = layers[0];
    const extras = layers.slice(1).filter(l => l.visible).map(l => l.presetName);
    const entry = {
      effect: primary.presetName,
      target: 'caster',
    };
    if (extras.length > 0) {
      entry.extras = extras;
      entry.extrasTarget = 'caster';
    }
    const json = JSON.stringify(entry, null, 2);
    navigator.clipboard.writeText(json).then(() => {
      alert('Effect map entry copied to clipboard!\n\n' + json);
    });
  }, [layers]);

  // ── Filtered presets for add dropdown ──
  const filteredPresets = presetLibrary.filter(p =>
    !addSearch || p.name.toLowerCase().includes(addSearch.toLowerCase())
  );

  return (
    <div className="compound-panel">
      <div className="compound-header">
        <h3>Compound Layers</h3>
        <span className="compound-count">{layers.length}</span>
      </div>

      {/* Layer list */}
      <div className="compound-layers">
        {layers.length === 0 && (
          <div className="compound-empty">
            No layers yet. Add presets to build a compound effect.
          </div>
        )}
        {layers.map((layer, index) => (
          <div
            key={layer.id}
            className={`compound-layer ${activeLayerIndex === index ? 'active' : ''}`}
            onClick={() => onSelectLayer(index)}
          >
            <div className="layer-main">
              <button
                className={`layer-visibility ${layer.visible ? 'visible' : 'hidden'}`}
                onClick={(e) => { e.stopPropagation(); toggleVisibility(index); }}
                title={layer.visible ? 'Hide layer' : 'Show layer'}
              >
                {layer.visible ? '👁' : '👁‍🗨'}
              </button>
              <span className="layer-index">{index + 1}</span>
              <span className="layer-name">{layer.presetName}</span>
              {index === 0 && <span className="badge badge-primary">primary</span>}
              {index > 0 && <span className="badge badge-extra">extra</span>}
            </div>
            <div className="layer-actions">
              <button
                className="layer-btn"
                onClick={(e) => { e.stopPropagation(); moveLayer(index, -1); }}
                disabled={index === 0}
                title="Move up"
              >▲</button>
              <button
                className="layer-btn"
                onClick={(e) => { e.stopPropagation(); moveLayer(index, 1); }}
                disabled={index === layers.length - 1}
                title="Move down"
              >▼</button>
              <button
                className="layer-btn"
                onClick={(e) => { e.stopPropagation(); duplicateLayer(index); }}
                title="Duplicate layer"
              >⧉</button>
              <button
                className="layer-btn layer-btn-delete"
                onClick={(e) => { e.stopPropagation(); removeLayer(index); }}
                title="Remove layer"
              >×</button>
            </div>
          </div>
        ))}
      </div>

      {/* Active layer offset controls */}
      {activeLayerIndex !== null && activeLayerIndex < layers.length && (
        <div className="layer-offset-controls">
          <span className="offset-label">Offset:</span>
          <label className="offset-field">
            X
            <input
              type="number"
              className="offset-input"
              value={layers[activeLayerIndex].offsetX}
              onChange={(e) => updateOffset(activeLayerIndex, 'offsetX', Number(e.target.value))}
            />
          </label>
          <label className="offset-field">
            Y
            <input
              type="number"
              className="offset-input"
              value={layers[activeLayerIndex].offsetY}
              onChange={(e) => updateOffset(activeLayerIndex, 'offsetY', Number(e.target.value))}
            />
          </label>
        </div>
      )}

      {/* Add layer button + dropdown */}
      <div className="compound-add-section">
        <button
          className="btn-add-layer"
          onClick={() => setShowAddDropdown(!showAddDropdown)}
        >
          + Add Layer
        </button>
        {layers.length > 0 && (
          <button
            className="btn-export-compound"
            onClick={exportEffectMapEntry}
            title="Copy effect-map JSON entry to clipboard"
          >
            📋 Export Map Entry
          </button>
        )}
      </div>

      {showAddDropdown && (
        <div className="add-layer-dropdown">
          <input
            type="text"
            className="add-layer-search"
            placeholder="Search presets..."
            value={addSearch}
            onChange={(e) => setAddSearch(e.target.value)}
            autoFocus
          />
          <div className="add-layer-list">
            {filteredPresets.map(p => (
              <div
                key={p.name}
                className="add-layer-item"
                onClick={() => addLayer(p.name)}
              >
                <span>{p.name}</span>
                {p.loop && <span className="badge badge-loop">loop</span>}
              </div>
            ))}
            {filteredPresets.length === 0 && (
              <div className="add-layer-empty">No matching presets.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
