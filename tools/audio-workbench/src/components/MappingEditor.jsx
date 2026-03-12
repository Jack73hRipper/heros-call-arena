// ─────────────────────────────────────────────────────────
// MappingEditor.jsx — Edit audio-effects.json mappings
// ─────────────────────────────────────────────────────────

import React, { useState, useRef, useCallback, useMemo } from 'react';
import Waveform from './Waveform.jsx';

const API_BASE = 'http://localhost:5211';

// Sections in audio-effects.json that contain event→sound mappings
const SECTIONS = [
  { id: 'combat', label: '⚔️ Combat', description: 'Melee, ranged, death, block, miss, etc.' },
  { id: 'skills', label: '✨ Skills', description: 'Per-skill sound overrides' },
  { id: 'environment', label: '🏰 Environment', description: 'Doors, chests, world interactions' },
  { id: 'events', label: '🎯 Events', description: 'Match start/end, portal, wave clear, floor' },
  { id: 'ui', label: '🖱️ UI', description: 'Button clicks, confirm, cancel' },
  { id: 'music', label: '🎵 Music', description: 'Music playlist tracks' },
];

/** All sound keys from _soundFiles for dropdown selection */
function getSoundKeyOptions(config) {
  return Object.keys(config?._soundFiles || {}).sort();
}

export default function MappingEditor({
  config,
  diskFiles,
  getAudioCtx,
  onUpdateConfig,
  onAddToCompare,
}) {
  const [activeSection, setActiveSection] = useState('combat');
  const [expandedEvent, setExpandedEvent] = useState(null);
  const [playingKey, setPlayingKey] = useState(null);
  const sourceRef = useRef(null);
  const [editingKey, setEditingKey] = useState(null);
  const [newSoundFileKey, setNewSoundFileKey] = useState('');
  const [newSoundFilePath, setNewSoundFilePath] = useState('');

  const soundKeyOptions = useMemo(() => getSoundKeyOptions(config), [config]);

  // ── Playback ───────────────────────────────────────────
  const playByKey = useCallback(async (soundKey) => {
    try {
      if (sourceRef.current) {
        try { sourceRef.current.stop(); } catch (_) {}
        sourceRef.current = null;
      }
      if (playingKey === soundKey) {
        setPlayingKey(null);
        return;
      }

      const filePath = config?._soundFiles?.[soundKey];
      if (!filePath) return;

      const ctx = getAudioCtx();
      const response = await fetch(`${API_BASE}${filePath}`);
      const arrayBuf = await response.arrayBuffer();
      const audioBuf = await ctx.decodeAudioData(arrayBuf);

      const source = ctx.createBufferSource();
      source.buffer = audioBuf;
      source.connect(ctx.destination);
      source.onended = () => {
        setPlayingKey(null);
        sourceRef.current = null;
      };
      source.start();
      sourceRef.current = source;
      setPlayingKey(soundKey);
    } catch (err) {
      console.error('Playback error:', err);
      setPlayingKey(null);
    }
  }, [playingKey, config, getAudioCtx]);

  // Play a random variant (simulates game behavior)
  const playRandomVariant = useCallback((variants) => {
    if (!variants?.length) return;
    const pick = variants[Math.floor(Math.random() * variants.length)];
    playByKey(pick);
  }, [playByKey]);

  // ── Config mutation helpers ────────────────────────────
  const updateMapping = useCallback((section, eventName, field, value) => {
    onUpdateConfig(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      if (!next[section]) next[section] = {};
      if (!next[section][eventName]) next[section][eventName] = {};
      next[section][eventName][field] = value;
      return next;
    });
  }, [onUpdateConfig]);

  const addVariant = useCallback((section, eventName, soundKey) => {
    onUpdateConfig(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      const mapping = next[section]?.[eventName];
      if (!mapping) return next;
      if (!mapping.variants) mapping.variants = [];
      if (!mapping.variants.includes(soundKey)) {
        mapping.variants.push(soundKey);
      }
      return next;
    });
  }, [onUpdateConfig]);

  const removeVariant = useCallback((section, eventName, soundKey) => {
    onUpdateConfig(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      const mapping = next[section]?.[eventName];
      if (!mapping?.variants) return next;
      mapping.variants = mapping.variants.filter(v => v !== soundKey);
      return next;
    });
  }, [onUpdateConfig]);

  const addSoundFileEntry = useCallback(() => {
    if (!newSoundFileKey.trim() || !newSoundFilePath.trim()) return;
    onUpdateConfig(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next._soundFiles[newSoundFileKey.trim()] = newSoundFilePath.trim();
      return next;
    });
    setNewSoundFileKey('');
    setNewSoundFilePath('');
  }, [newSoundFileKey, newSoundFilePath, onUpdateConfig]);

  const removeSoundFileEntry = useCallback((key) => {
    onUpdateConfig(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      delete next._soundFiles[key];
      return next;
    });
  }, [onUpdateConfig]);

  // ── Render section content ─────────────────────────────
  const sectionData = config?.[activeSection];

  const renderMusicSection = () => {
    const tracks = config?.music?.tracks || [];
    return (
      <div className="wb-editor__music">
        <h3 className="wb-editor__section-title">Music Playlist ({tracks.length} tracks)</h3>
        {tracks.map((track, i) => (
          <div key={i} className="wb-mapping-row">
            <div className="wb-mapping-row__header">
              <span className="wb-mapping-row__event">{track.title}</span>
              <span className="wb-mapping-row__path">{track.path}</span>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderSoundFilesManager = () => {
    const entries = Object.entries(config?._soundFiles || {}).sort(([a], [b]) => a.localeCompare(b));
    return (
      <div className="wb-editor__soundfiles">
        <h3 className="wb-editor__section-title">
          Sound Files Registry ({entries.length} entries)
        </h3>
        <div className="wb-editor__add-row">
          <input
            className="wb-input"
            type="text"
            placeholder="Key (e.g. melee_hit_10)"
            value={newSoundFileKey}
            onChange={e => setNewSoundFileKey(e.target.value)}
          />
          <input
            className="wb-input"
            type="text"
            placeholder="Path (e.g. /audio/combat/my-sound.wav)"
            value={newSoundFilePath}
            onChange={e => setNewSoundFilePath(e.target.value)}
          />
          <button className="wb-btn wb-btn--sm wb-btn--primary" onClick={addSoundFileEntry}>
            + Add
          </button>
        </div>
        <div className="wb-editor__file-list">
          {entries.map(([key, filePath]) => {
            const isPlaying = playingKey === key;
            return (
              <div key={key} className={`wb-sf-row ${isPlaying ? 'wb-sf-row--playing' : ''}`}>
                <button
                  className={`wb-play-btn wb-play-btn--sm ${isPlaying ? 'wb-play-btn--active' : ''}`}
                  onClick={() => playByKey(key)}
                  title="Play"
                >
                  {isPlaying ? '⏹' : '▶'}
                </button>
                <span className="wb-sf-row__key">{key}</span>
                <span className="wb-sf-row__path">{filePath}</span>
                <div className="wb-sf-row__actions">
                  <button
                    className="wb-btn wb-btn--sm wb-btn--ghost"
                    onClick={() => onAddToCompare(filePath, key)}
                    title="Add to compare"
                  >
                    ⚖️
                  </button>
                  <button
                    className="wb-btn wb-btn--sm wb-btn--danger"
                    onClick={() => removeSoundFileEntry(key)}
                    title="Remove entry"
                  >
                    ✗
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderEventMappings = () => {
    if (!sectionData || typeof sectionData !== 'object') {
      return <div className="wb-empty">No mappings in this section.</div>;
    }

    const events = Object.entries(sectionData).filter(([k]) => !k.startsWith('_'));

    return (
      <div className="wb-editor__events">
        {events.map(([eventName, mapping]) => {
          const isExpanded = expandedEvent === `${activeSection}.${eventName}`;
          const hasVariants = Array.isArray(mapping.variants);
          const soundKey = mapping.key || null;
          const volume = mapping.volume ?? 1.0;
          const pitch = mapping.pitchVariance ?? 0;

          return (
            <div key={eventName} className="wb-mapping-row">
              {/* Header */}
              <div
                className="wb-mapping-row__header"
                onClick={() => setExpandedEvent(isExpanded ? null : `${activeSection}.${eventName}`)}
              >
                <span className="wb-mapping-row__expand">{isExpanded ? '▼' : '▶'}</span>
                <span className="wb-mapping-row__event">{eventName}</span>
                {hasVariants && (
                  <span className="wb-badge wb-badge--info">{mapping.variants.length} variants</span>
                )}
                {soundKey && <span className="wb-mapping-row__single-key">→ {soundKey}</span>}
                <span className="wb-mapping-row__vol">vol: {volume}</span>
                <span className="wb-mapping-row__pitch">pitch±: {pitch}</span>

                {/* Quick play */}
                <button
                  className="wb-play-btn wb-play-btn--sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (hasVariants) {
                      playRandomVariant(mapping.variants);
                    } else if (soundKey) {
                      playByKey(soundKey);
                    }
                  }}
                  title={hasVariants ? 'Play random variant' : 'Play sound'}
                >
                  {playingKey && ((hasVariants && mapping.variants.includes(playingKey)) || playingKey === soundKey) ? '⏹' : '▶'}
                </button>
              </div>

              {/* Expanded detail */}
              {isExpanded && (
                <div className="wb-mapping-row__detail">
                  {mapping._comment && (
                    <p className="wb-mapping-row__comment">{mapping._comment}</p>
                  )}

                  {/* Volume slider */}
                  <div className="wb-mapping-row__control">
                    <label>Volume</label>
                    <input
                      type="range"
                      min="0" max="1" step="0.05"
                      value={volume}
                      onChange={e => updateMapping(activeSection, eventName, 'volume', parseFloat(e.target.value))}
                    />
                    <span className="wb-mapping-row__val">{volume.toFixed(2)}</span>
                  </div>

                  {/* Pitch variance slider */}
                  <div className="wb-mapping-row__control">
                    <label>Pitch Variance</label>
                    <input
                      type="range"
                      min="0" max="0.2" step="0.01"
                      value={pitch}
                      onChange={e => updateMapping(activeSection, eventName, 'pitchVariance', parseFloat(e.target.value))}
                    />
                    <span className="wb-mapping-row__val">±{(pitch * 100).toFixed(0)}%</span>
                  </div>

                  {/* Single key selector */}
                  {!hasVariants && soundKey && (
                    <div className="wb-mapping-row__control">
                      <label>Sound Key</label>
                      <select
                        className="wb-select"
                        value={soundKey}
                        onChange={e => updateMapping(activeSection, eventName, 'key', e.target.value)}
                      >
                        {soundKeyOptions.map(k => (
                          <option key={k} value={k}>{k}</option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* Variant list */}
                  {hasVariants && (
                    <div className="wb-mapping-row__variants">
                      <h4>Variants ({mapping.variants.length})</h4>
                      {mapping.variants.map((vKey, i) => {
                        const vPath = config?._soundFiles?.[vKey];
                        const isVPlaying = playingKey === vKey;
                        return (
                          <div key={vKey} className="wb-variant-row">
                            <span className="wb-variant-row__index">{i + 1}.</span>
                            <button
                              className={`wb-play-btn wb-play-btn--sm ${isVPlaying ? 'wb-play-btn--active' : ''}`}
                              onClick={() => playByKey(vKey)}
                            >
                              {isVPlaying ? '⏹' : '▶'}
                            </button>
                            {vPath && (
                              <Waveform
                                src={`${API_BASE}${vPath}`}
                                getAudioCtx={getAudioCtx}
                                isPlaying={isVPlaying}
                                compact
                              />
                            )}
                            <span className="wb-variant-row__key">{vKey}</span>
                            <button
                              className="wb-btn wb-btn--sm wb-btn--ghost"
                              onClick={() => onAddToCompare(vPath, vKey)}
                              title="Add to compare"
                            >
                              ⚖️
                            </button>
                            <button
                              className="wb-btn wb-btn--sm wb-btn--danger"
                              onClick={() => removeVariant(activeSection, eventName, vKey)}
                              title="Remove variant"
                            >
                              ✗
                            </button>
                          </div>
                        );
                      })}

                      {/* Add variant dropdown */}
                      <div className="wb-variant-add">
                        <select
                          className="wb-select"
                          value=""
                          onChange={e => {
                            if (e.target.value) addVariant(activeSection, eventName, e.target.value);
                          }}
                        >
                          <option value="">+ Add variant...</option>
                          {soundKeyOptions
                            .filter(k => !mapping.variants.includes(k))
                            .map(k => (
                              <option key={k} value={k}>{k}</option>
                            ))
                          }
                        </select>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  // ── Main render ────────────────────────────────────────
  return (
    <div className="wb-editor">
      {/* Section sidebar */}
      <aside className="wb-editor__sidebar">
        <button
          className={`wb-editor__section-btn ${activeSection === '_soundFiles' ? 'wb-editor__section-btn--active' : ''}`}
          onClick={() => setActiveSection('_soundFiles')}
        >
          <span className="wb-editor__section-icon">📋</span>
          <span>Sound Files</span>
          <span className="wb-editor__section-count">{Object.keys(config?._soundFiles || {}).length}</span>
        </button>

        {SECTIONS.map(sec => {
          const data = config?.[sec.id];
          let count = 0;
          if (sec.id === 'music') {
            count = config?.music?.tracks?.length || 0;
          } else if (data && typeof data === 'object') {
            count = Object.keys(data).filter(k => !k.startsWith('_')).length;
          }

          return (
            <button
              key={sec.id}
              className={`wb-editor__section-btn ${activeSection === sec.id ? 'wb-editor__section-btn--active' : ''}`}
              onClick={() => setActiveSection(sec.id)}
            >
              <span className="wb-editor__section-icon">{sec.label.split(' ')[0]}</span>
              <span>{sec.label.split(' ').slice(1).join(' ')}</span>
              <span className="wb-editor__section-count">{count}</span>
            </button>
          );
        })}
      </aside>

      {/* Main content area */}
      <div className="wb-editor__content">
        {activeSection === '_soundFiles' && renderSoundFilesManager()}
        {activeSection === 'music' && renderMusicSection()}
        {activeSection !== '_soundFiles' && activeSection !== 'music' && renderEventMappings()}
      </div>
    </div>
  );
}
