// ─────────────────────────────────────────────────────────
// CreateSound.jsx — Create a new sound from a template
// ─────────────────────────────────────────────────────────
// Modal dialog that lets user pick a template, name a new
// sound key, assign a category, then opens the editor.

import React, { useState, useEffect, useCallback } from 'react';

const API = 'http://localhost:5211';

const CATEGORIES = [
  { value: 'combat',   label: '⚔️ Combat' },
  { value: 'skills',   label: '✨ Skills' },
  { value: 'buffs',    label: '🛡️ Buffs & Debuffs' },
  { value: 'items',    label: '🧪 Items' },
  { value: 'events',   label: '🎯 Events' },
  { value: 'ui',       label: '🖱️ UI' },
  { value: 'movement', label: '👣 Movement' },
];

export default function CreateSound({ onClose, onCreated }) {
  const [templates, setTemplates] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Form fields
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [soundKey, setSoundKey] = useState('');
  const [category, setCategory] = useState('combat');
  const [description, setDescription] = useState('');

  // ── Load templates on mount ────────────────────────
  useEffect(() => {
    fetch(`${API}/api/synth/templates`)
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          setError(data.error);
        } else {
          setTemplates(data.templates || data);
          // Default to first template
          const tNames = Object.keys(data.templates || data);
          if (tNames.length > 0) setSelectedTemplate(tNames[0]);
        }
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  // ── Validate key format ────────────────────────────
  const keyError = (() => {
    if (!soundKey) return null;
    if (!/^[a-z][a-z0-9_]*$/.test(soundKey)) {
      return 'Key must be lowercase letters, numbers, underscores. Start with a letter.';
    }
    if (soundKey.length < 3) return 'Key must be at least 3 characters.';
    return null;
  })();

  const canCreate = soundKey.length >= 3 && !keyError && selectedTemplate && category;

  // ── Create handler ─────────────────────────────────
  const handleCreate = useCallback(() => {
    if (!canCreate) return;
    onCreated({
      key: soundKey,
      template: selectedTemplate,
      category,
      description: description || `Custom ${selectedTemplate} sound`,
      filename: `${soundKey}.wav`,
    });
  }, [canCreate, soundKey, selectedTemplate, category, description, onCreated]);

  // ── Render ─────────────────────────────────────────

  const selectedInfo = templates ? (templates[selectedTemplate] || null) : null;

  return (
    <div className="wb-editor wb-editor--create">
      <div className="wb-editor__header">
        <div className="wb-editor__header-info">
          <h3 className="wb-editor__title">
            <span className="wb-editor__title-icon">✨</span>
            Create New Sound
          </h3>
          <p className="wb-editor__desc">
            Pick a synthesis template, name your sound, and fine-tune in the editor.
          </p>
        </div>
        <button className="wb-btn wb-btn--ghost" onClick={onClose} title="Cancel">✕</button>
      </div>

      {loading && (
        <div className="wb-editor__loading">
          <div className="wb-spinner" />
          <span>Loading templates…</span>
        </div>
      )}

      {error && (
        <div className="wb-editor__error">
          <p>Failed to load templates: {error}</p>
        </div>
      )}

      {!loading && templates && (
        <div className="wb-editor__params">
          {/* ── Template picker ──────────────────────── */}
          <div className="wb-editor__group">
            <h4 className="wb-editor__group-title">🎹 Template</h4>
            <div className="wb-create__templates">
              {Object.entries(templates).map(([name, info]) => (
                <button
                  key={name}
                  className={`wb-create__tmpl ${selectedTemplate === name ? 'wb-create__tmpl--active' : ''}`}
                  onClick={() => setSelectedTemplate(name)}
                >
                  <span className="wb-create__tmpl-name">{info.label || name}</span>
                  <span className="wb-create__tmpl-desc">
                    {info.description || `${Object.keys(info.params || {}).length} params`}
                  </span>
                </button>
              ))}
            </div>
            {selectedInfo && selectedInfo.params && (
              <p className="wb-text-dim" style={{ fontSize: '11px', marginTop: '6px' }}>
                Parameters: {Object.keys(selectedInfo.params).map(k =>
                  selectedInfo.params[k].label || k
                ).join(', ')}
              </p>
            )}
          </div>

          {/* ── Sound key ────────────────────────────── */}
          <div className="wb-editor__group">
            <h4 className="wb-editor__group-title">🏷️ Sound Details</h4>
            <div className="wb-editor__param">
              <label className="wb-editor__param-label" htmlFor="create-key">Sound Key</label>
              <div className="wb-editor__param-slider">
                <input
                  id="create-key"
                  className="wb-input"
                  type="text"
                  placeholder="e.g. custom_explosion"
                  value={soundKey}
                  onChange={e => setSoundKey(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                  style={{ flex: 1 }}
                />
              </div>
              {keyError && <span className="wb-editor__error-inline">⚠ {keyError}</span>}
            </div>

            <div className="wb-editor__param">
              <label className="wb-editor__param-label" htmlFor="create-cat">Category</label>
              <select
                id="create-cat"
                className="wb-select"
                value={category}
                onChange={e => setCategory(e.target.value)}
              >
                {CATEGORIES.map(c => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>

            <div className="wb-editor__param">
              <label className="wb-editor__param-label" htmlFor="create-desc">Description</label>
              <div className="wb-editor__param-slider">
                <input
                  id="create-desc"
                  className="wb-input"
                  type="text"
                  placeholder="Optional description"
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  style={{ flex: 1 }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Footer ────────────────────────────────── */}
      <div className="wb-editor__footer">
        <button className="wb-btn wb-btn--ghost" onClick={onClose}>Cancel</button>
        <button
          className="wb-btn wb-btn--primary"
          onClick={handleCreate}
          disabled={!canCreate}
        >
          🎛️ Create &amp; Open Editor
        </button>
      </div>
    </div>
  );
}
