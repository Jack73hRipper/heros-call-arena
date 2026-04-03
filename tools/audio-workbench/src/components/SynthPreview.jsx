// ─────────────────────────────────────────────────────────
// SynthPreview.jsx — Sound Synthesizer tab for Audio Workbench
// ─────────────────────────────────────────────────────────
// Generates procedural SFX via Python, previews them, and
// lets you apply individual or all sounds to the game.

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Waveform from './Waveform.jsx';
import SoundEditor from './SoundEditor.jsx';
import CreateSound from './CreateSound.jsx';

const API = 'http://localhost:5211';

/**
 * Category display info
 */
const CATEGORY_META = {
  combat:    { icon: '⚔️', label: 'Combat' },
  skills:    { icon: '✨', label: 'Skills' },
  buffs:     { icon: '🛡️', label: 'Buffs & Debuffs' },
  items:     { icon: '🧪', label: 'Items' },
  events:    { icon: '🎯', label: 'Events' },
  ui:        { icon: '🖱️', label: 'UI' },
  movement:  { icon: '👣', label: 'Movement' },
};

export default function SynthPreview({
  config,
  diskFiles,
  getAudioCtx,
  onUpdateConfig,
  onAddToCompare,
  onRefreshDiskFiles,
}) {
  // ── State ──────────────────────────────────────────────
  const [manifest, setManifest] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [genOutput, setGenOutput] = useState(null);
  const [loading, setLoading] = useState(true);
  const [playingKey, setPlayingKey] = useState(null);
  const [search, setSearch] = useState('');
  const [catFilter, setCatFilter] = useState('all');
  const [applying, setApplying] = useState(null); // key being applied
  const [applyingAll, setApplyingAll] = useState(false);
  const [expandedCats, setExpandedCats] = useState(new Set());
  const [applyResult, setApplyResult] = useState(null);
  const [editingSound, setEditingSound] = useState(null);   // {key, ...soundInfo}
  const [creatingSound, setCreatingSound] = useState(false); // show create dialog

  const sourceRef = useRef(null);
  const gainRef = useRef(null);

  // ── Load manifest on mount ─────────────────────────────
  const loadManifest = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/synth/manifest`);
      if (res.ok) {
        const data = await res.json();
        setManifest(data);
        // Auto-expand all categories on first load
        if (data.sounds && data.sounds.length > 0) {
          const cats = new Set(data.sounds.map(s => s.category));
          setExpandedCats(cats);
        }
      }
    } catch (err) {
      console.error('Failed to load synth manifest:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadManifest(); }, [loadManifest]);

  // ── Cleanup on unmount ─────────────────────────────────
  useEffect(() => {
    return () => {
      if (sourceRef.current) {
        try { sourceRef.current.stop(); } catch (_) {}
      }
    };
  }, []);

  // ── Generate all sounds ────────────────────────────────
  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setGenOutput(null);
    try {
      const res = await fetch(`${API}/api/synth/generate`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setGenOutput({ success: true, count: data.totalCount, stdout: data.stdout });
        setManifest(data);
        // Expand all categories
        if (data.sounds) {
          setExpandedCats(new Set(data.sounds.map(s => s.category)));
        }
      } else {
        setGenOutput({ success: false, error: data.error, stderr: data.stderr });
      }
    } catch (err) {
      setGenOutput({ success: false, error: err.message });
    } finally {
      setGenerating(false);
    }
  }, []);

  // ── Playback ───────────────────────────────────────────
  const stopSound = useCallback(() => {
    if (sourceRef.current) {
      try { sourceRef.current.stop(); } catch (_) {}
      sourceRef.current = null;
    }
    setPlayingKey(null);
  }, []);

  const playSound = useCallback(async (sound) => {
    stopSound();
    try {
      const ctx = getAudioCtx();
      const url = `${API}${sound.path}`;
      const response = await fetch(url);
      const arrayBuf = await response.arrayBuffer();
      const audioBuf = await ctx.decodeAudioData(arrayBuf);

      const source = ctx.createBufferSource();
      source.buffer = audioBuf;

      const gain = ctx.createGain();
      gain.gain.value = 0.8;
      source.connect(gain);
      gain.connect(ctx.destination);

      source.onended = () => {
        setPlayingKey(prev => prev === sound.key ? null : prev);
      };

      source.start();
      sourceRef.current = source;
      gainRef.current = gain;
      setPlayingKey(sound.key);
    } catch (err) {
      console.error('Playback error:', err);
    }
  }, [getAudioCtx, stopSound]);

  const togglePlay = useCallback((sound) => {
    if (playingKey === sound.key) {
      stopSound();
    } else {
      playSound(sound);
    }
  }, [playingKey, playSound, stopSound]);

  // ── Apply single sound ─────────────────────────────────
  const handleApply = useCallback(async (sound) => {
    setApplying(sound.key);
    try {
      const res = await fetch(`${API}/api/synth/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key: sound.key,
          category: sound.category,
          filename: sound.filename,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setApplyResult({ key: sound.key, success: true });
        if (onRefreshDiskFiles) onRefreshDiskFiles();
        setTimeout(() => setApplyResult(null), 2000);
      } else {
        setApplyResult({ key: sound.key, success: false, error: data.error });
      }
    } catch (err) {
      setApplyResult({ key: sound.key, success: false, error: err.message });
    } finally {
      setApplying(null);
    }
  }, [onRefreshDiskFiles]);

  // ── Apply all sounds ───────────────────────────────────
  const handleApplyAll = useCallback(async () => {
    if (!window.confirm(`This will replace ALL ${manifest?.totalCount || 0} sound files in the game. Continue?`)) {
      return;
    }
    setApplyingAll(true);
    try {
      const res = await fetch(`${API}/api/synth/apply-all`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setApplyResult({ key: '_all', success: true, count: data.applied });
        if (onRefreshDiskFiles) onRefreshDiskFiles();
        setTimeout(() => setApplyResult(null), 3000);
      } else {
        setApplyResult({ key: '_all', success: false, error: data.error });
      }
    } catch (err) {
      setApplyResult({ key: '_all', success: false, error: err.message });
    } finally {
      setApplyingAll(false);
    }
  }, [manifest, onRefreshDiskFiles]);

  // ── Category toggle ────────────────────────────────────
  const toggleCat = useCallback((cat) => {
    setExpandedCats(prev => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  }, []);

  // ── Filter & group sounds ──────────────────────────────
  const sounds = manifest?.sounds || [];
  const filtered = sounds.filter(s => {
    if (catFilter !== 'all' && s.category !== catFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return s.key.toLowerCase().includes(q) ||
             s.description.toLowerCase().includes(q) ||
             s.filename.toLowerCase().includes(q);
    }
    return true;
  });

  // Group by category
  const grouped = {};
  for (const s of filtered) {
    if (!grouped[s.category]) grouped[s.category] = [];
    grouped[s.category].push(s);
  }

  const categories = Object.keys(grouped).sort();
  const allCats = [...new Set(sounds.map(s => s.category))].sort();

  // Check which keys already exist in current config
  const existingKeys = new Set(Object.keys(config?._soundFiles || {}));

  // ── Play All in Category ───────────────────────────────
  const playAllInCategory = useCallback(async (cat) => {
    const catSounds = grouped[cat] || [];
    for (const s of catSounds) {
      await new Promise((resolve) => {
        playSound(s);
        // Wait for sound to finish + small gap
        setTimeout(resolve, Math.max((s.duration || 0.3) * 1000 + 200, 400));
      });
    }
  }, [grouped, playSound]);

  // ── Render ─────────────────────────────────────────────

  if (loading) {
    return (
      <div className="wb-synth">
        <div className="wb-loading"><div className="wb-spinner" /><p>Loading synthesizer...</p></div>
      </div>
    );
  }

  const hasSounds = sounds.length > 0;

  return (
    <div className="wb-synth">
      {/* ── Header / Controls ────────────────────── */}
      <div className="wb-synth__header">
        <div className="wb-synth__header-left">
          <h2 className="wb-synth__title">
            <span className="wb-synth__icon">🔊</span>
            Sound Synthesizer
          </h2>
          <p className="wb-synth__subtitle">
            Procedurally generated SFX — preview, compare, and apply to the game.
          </p>
        </div>
        <div className="wb-synth__header-right">
          <button
            className="wb-btn wb-btn--secondary"
            onClick={() => setCreatingSound(true)}
            disabled={generating}
          >
            ✨ New Sound
          </button>
          <button
            className={`wb-btn wb-btn--primary ${generating ? 'wb-btn--saving' : ''}`}
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? '⏳ Generating...' : '🔧 Generate All Sounds'}
          </button>
          {hasSounds && (
            <button
              className={`wb-btn wb-btn--danger ${applyingAll ? 'wb-btn--saving' : ''}`}
              onClick={handleApplyAll}
              disabled={applyingAll || generating}
            >
              {applyingAll ? '⏳ Applying...' : `🔄 Apply All (${sounds.length})`}
            </button>
          )}
        </div>
      </div>

      {/* ── Generation output ─────────────────────── */}
      {genOutput && (
        <div className={`wb-synth__output ${genOutput.success ? 'wb-synth__output--ok' : 'wb-synth__output--err'}`}>
          {genOutput.success ? (
            <span>✓ Generated {genOutput.count} sounds successfully</span>
          ) : (
            <span>✗ Generation failed: {genOutput.error}</span>
          )}
        </div>
      )}

      {/* ── Apply-all result ──────────────────────── */}
      {applyResult?.key === '_all' && (
        <div className={`wb-synth__output ${applyResult.success ? 'wb-synth__output--ok' : 'wb-synth__output--err'}`}>
          {applyResult.success ? (
            <span>✓ Applied {applyResult.count} sounds to the game audio folder</span>
          ) : (
            <span>✗ Apply failed: {applyResult.error}</span>
          )}
        </div>
      )}

      {/* ── No sounds state ───────────────────────── */}
      {!hasSounds && !generating && (
        <div className="wb-synth__empty">
          <div className="wb-synth__empty-icon">🎵</div>
          <h3>No synthesized sounds yet</h3>
          <p>Click <strong>"Generate All Sounds"</strong> to create ~{85} procedural SFX.</p>
          <p className="wb-text-dim">Synthesis takes a few seconds using numpy + scipy.</p>
        </div>
      )}

      {/* ── Filter bar ────────────────────────────── */}
      {hasSounds && (
        <div className="wb-synth__filters">
          <input
            className="wb-input"
            type="text"
            placeholder="Search sounds..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <select
            className="wb-select"
            value={catFilter}
            onChange={e => setCatFilter(e.target.value)}
          >
            <option value="all">All categories ({sounds.length})</option>
            {allCats.map(c => (
              <option key={c} value={c}>
                {CATEGORY_META[c]?.icon || '📁'} {CATEGORY_META[c]?.label || c}
                {' '}({sounds.filter(s => s.category === c).length})
              </option>
            ))}
          </select>
          <span className="wb-synth__count">
            {filtered.length} / {sounds.length} sounds
          </span>
        </div>
      )}

      {/* ── Sound list by category ────────────────── */}
      {hasSounds && (
        <div className={`wb-synth__body ${editingSound || creatingSound ? 'wb-synth__body--split' : ''}`}>
          <div className="wb-synth__list">
          {categories.map(cat => {
        const catMeta = CATEGORY_META[cat] || { icon: '📁', label: cat };
        const catSounds = grouped[cat];
        const expanded = expandedCats.has(cat);

        return (
          <div key={cat} className="wb-synth__category">
            <div
              className="wb-synth__cat-header"
              onClick={() => toggleCat(cat)}
            >
              <span className="wb-synth__cat-arrow">{expanded ? '▾' : '▸'}</span>
              <span className="wb-synth__cat-icon">{catMeta.icon}</span>
              <span className="wb-synth__cat-name">{catMeta.label}</span>
              <span className="wb-badge wb-badge--ok">{catSounds.length}</span>
              <button
                className="wb-btn wb-btn--ghost wb-btn--sm"
                onClick={(e) => { e.stopPropagation(); playAllInCategory(cat); }}
                title="Preview all in this category"
              >
                ▶ Preview All
              </button>
            </div>

            {expanded && (
              <div className="wb-synth__cat-body">
                {catSounds.map(sound => {
                  const isPlaying = playingKey === sound.key;
                  const isApplying = applying === sound.key;
                  const existsInGame = existingKeys.has(sound.key);
                  const justApplied = applyResult?.key === sound.key && applyResult?.success;

                  return (
                    <div
                      key={sound.key}
                      className={`wb-synth__sound ${isPlaying ? 'wb-synth__sound--playing' : ''}`}
                    >
                      {/* Play button */}
                      <button
                        className={`wb-play-btn ${isPlaying ? 'wb-play-btn--active' : ''}`}
                        onClick={() => togglePlay(sound)}
                        title={isPlaying ? 'Stop' : 'Play'}
                      >
                        {isPlaying ? '⏹' : '▶'}
                      </button>

                      {/* Waveform */}
                      <div className="wb-synth__waveform">
                        <Waveform
                          src={`${API}${sound.path}`}
                          getAudioCtx={getAudioCtx}
                          isPlaying={isPlaying}
                          compact
                        />
                      </div>

                      {/* Info */}
                      <div className="wb-synth__info">
                        <span className="wb-synth__key">{sound.key}</span>
                        <span className="wb-synth__desc">{sound.description}</span>
                      </div>

                      {/* Duration */}
                      <span className="wb-synth__duration">
                        {sound.duration ? `${sound.duration}s` : ''}
                      </span>

                      {/* Status badge */}
                      {existsInGame && !justApplied && (
                        <span className="wb-badge wb-badge--warn" title="Key already mapped in game">
                          exists
                        </span>
                      )}
                      {justApplied && (
                        <span className="wb-badge wb-badge--ok">✓ applied</span>
                      )}

                      {/* Actions */}
                      <div className="wb-synth__actions">
                        <button
                          className="wb-btn wb-btn--ghost wb-btn--sm"
                          onClick={() => setEditingSound(sound)}
                          title="Edit sound parameters"
                        >
                          ✏️
                        </button>
                        <button
                          className="wb-btn wb-btn--ghost wb-btn--sm"
                          onClick={() => onAddToCompare(
                            `${API}${sound.path}`,
                            `[synth] ${sound.key}`
                          )}
                          title="Add to compare panel"
                        >
                          ⚖️
                        </button>
                        <button
                          className={`wb-btn wb-btn--sm ${justApplied ? 'wb-btn--primary' : 'wb-btn--secondary'}`}
                          onClick={() => handleApply(sound)}
                          disabled={isApplying}
                          title="Copy to game audio folder and update config"
                        >
                          {isApplying ? '...' : justApplied ? '✓' : '📥 Apply'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
        </div>

          {/* ── Side panel: Editor or Create ──────────── */}
          {editingSound && (
            <div className="wb-synth__side-panel">
              <SoundEditor
                soundKey={editingSound.key}
                soundInfo={editingSound}
                getAudioCtx={getAudioCtx}
                onClose={() => setEditingSound(null)}
                onAddToCompare={onAddToCompare}
                onSoundUpdated={(key) => {
                  // Regenerate manifest to pick up changes
                  loadManifest();
                }}
              />
            </div>
          )}

          {creatingSound && !editingSound && (
            <div className="wb-synth__side-panel">
              <CreateSound
                onClose={() => setCreatingSound(false)}
                onCreated={(newSound) => {
                  // Close create dialog, open editor for the new sound
                  setCreatingSound(false);
                  setEditingSound({
                    key: newSound.key,
                    category: newSound.category,
                    description: newSound.description,
                    filename: newSound.filename,
                    template: newSound.template,
                    isNew: true,
                  });
                }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
