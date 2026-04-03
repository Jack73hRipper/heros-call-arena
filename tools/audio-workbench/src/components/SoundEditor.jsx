// ─────────────────────────────────────────────────────────
// SoundEditor.jsx — Parameterized sound editing panel
// ─────────────────────────────────────────────────────────
// Opens when clicking "Edit" on a synth sound. Shows sliders
// for all template params, live preview, save preset, reset.

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import Waveform from './Waveform.jsx';

const API = 'http://localhost:5211';

/**
 * Group param labels for section headers
 */
const GROUP_LABELS = {
  sound: '🎛️ Sound Parameters',
  post:  '🔊 Post-Processing',
};

/**
 * Render a single parameter control.
 */
function ParamControl({ param, value, onChange }) {
  const id = `param-${param.key}`;

  // Option-based (dropdown or checkbox)
  if (param.options) {
    // Boolean toggle
    if (typeof param.options[0] === 'boolean') {
      return (
        <div className="wb-editor__param">
          <label className="wb-editor__param-label" htmlFor={id}>{param.label}</label>
          <div className="wb-editor__param-toggle">
            <input
              id={id}
              type="checkbox"
              checked={!!value}
              onChange={e => onChange(param.key, e.target.checked)}
            />
            <span className="wb-editor__param-val">{value ? 'On' : 'Off'}</span>
          </div>
        </div>
      );
    }
    // String options (dropdown)
    return (
      <div className="wb-editor__param">
        <label className="wb-editor__param-label" htmlFor={id}>{param.label}</label>
        <select
          id={id}
          className="wb-select wb-select--sm"
          value={value}
          onChange={e => onChange(param.key, e.target.value)}
        >
          {param.options.map(opt => (
            <option key={String(opt)} value={opt}>{String(opt)}</option>
          ))}
        </select>
      </div>
    );
  }

  // Numeric slider
  const min = param.min ?? 0;
  const max = param.max ?? 1;
  const step = param.step ?? 0.01;
  // Format display value
  const displayVal = typeof value === 'number'
    ? (step >= 1 ? value.toFixed(0) : value.toFixed(step < 0.01 ? 3 : 2))
    : String(value);
  const isCustomized = param.customized || value !== param.default;

  return (
    <div className={`wb-editor__param ${isCustomized ? 'wb-editor__param--changed' : ''}`}>
      <label className="wb-editor__param-label" htmlFor={id}>
        {param.label}
        {isCustomized && <span className="wb-editor__param-dot" title="Modified">●</span>}
      </label>
      <div className="wb-editor__param-slider">
        <input
          id={id}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={e => onChange(param.key, parseFloat(e.target.value))}
        />
        <span className="wb-editor__param-val">{displayVal}</span>
        {isCustomized && (
          <button
            className="wb-editor__param-reset"
            title={`Reset to ${param.default}`}
            onClick={() => onChange(param.key, param.default)}
          >↩</button>
        )}
      </div>
    </div>
  );
}

export default function SoundEditor({
  soundKey,
  soundInfo,
  getAudioCtx,
  onClose,
  onAddToCompare,
  onSoundUpdated,
}) {
  const [editorData, setEditorData] = useState(null);
  const [params, setParams] = useState({});
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [playingPreview, setPlayingPreview] = useState(false);
  const [error, setError] = useState(null);
  const [saveMsg, setSaveMsg] = useState(null);

  const sourceRef = useRef(null);
  const gainRef = useRef(null);

  // ── Load editor info on mount / key change ─────────
  useEffect(() => {
    if (!soundKey) return;
    setLoading(true);
    setError(null);
    setPreviewUrl(null);
    const tmplParam = soundInfo?.template ? `?template=${encodeURIComponent(soundInfo.template)}` : '';
    fetch(`${API}/api/synth/editor/${encodeURIComponent(soundKey)}${tmplParam}`)
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          setError(data.error);
        } else {
          setEditorData(data);
          // Init params from editor data
          const p = {};
          for (const param of data.params || []) {
            p[param.key] = param.value;
          }
          setParams(p);
        }
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [soundKey]);

  // ── Cleanup audio on unmount ───────────────────────
  useEffect(() => {
    return () => {
      if (sourceRef.current) {
        try { sourceRef.current.stop(); } catch (_) {}
      }
    };
  }, []);

  // ── Param change handler ──────────────────────────
  const handleParamChange = useCallback((key, value) => {
    setParams(prev => ({ ...prev, [key]: value }));
  }, []);

  // ── Reset all to defaults ─────────────────────────
  const handleResetAll = useCallback(() => {
    if (!editorData) return;
    const p = {};
    for (const param of editorData.params || []) {
      p[param.key] = param.default;
    }
    setParams(p);
    setPreviewUrl(null);
  }, [editorData]);

  // ── Check if any param is modified ─────────────────
  const hasChanges = useMemo(() => {
    if (!editorData) return false;
    return editorData.params.some(p => params[p.key] !== p.default);
  }, [editorData, params]);

  // ── Generate preview ───────────────────────────────
  const handlePreview = useCallback(async () => {
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/synth/generate-one`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key: soundKey,
          params: params,
          template: editorData?.template,
        }),
      });
      const data = await res.json();
      if (data.success) {
        // Add cache-buster to force reload
        setPreviewUrl(`${API}${data.path}?t=${Date.now()}`);
      } else {
        setError(data.error || 'Generation failed');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  }, [soundKey, params, editorData]);

  // ── Playback ───────────────────────────────────────
  const stopPreview = useCallback(() => {
    if (sourceRef.current) {
      try { sourceRef.current.stop(); } catch (_) {}
      sourceRef.current = null;
    }
    setPlayingPreview(false);
  }, []);

  const playPreview = useCallback(async () => {
    if (!previewUrl) return;
    stopPreview();
    try {
      const ctx = getAudioCtx();
      const response = await fetch(previewUrl);
      const arrayBuf = await response.arrayBuffer();
      const audioBuf = await ctx.decodeAudioData(arrayBuf);
      const source = ctx.createBufferSource();
      source.buffer = audioBuf;
      const gain = ctx.createGain();
      gain.gain.value = 0.8;
      source.connect(gain);
      gain.connect(ctx.destination);
      source.onended = () => setPlayingPreview(false);
      source.start();
      sourceRef.current = source;
      gainRef.current = gain;
      setPlayingPreview(true);
    } catch (err) {
      console.error('Preview playback error:', err);
    }
  }, [previewUrl, getAudioCtx, stopPreview]);

  // ── Save preset ────────────────────────────────────
  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaveMsg(null);
    try {
      const res = await fetch(`${API}/api/synth/presets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key: soundKey,
          template: editorData?.template,
          params: params,
          category: soundInfo?.category,
          filename: soundInfo?.filename,
          description: soundInfo?.description,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setSaveMsg('Preset saved!');
        setTimeout(() => setSaveMsg(null), 2000);
        if (onSoundUpdated) onSoundUpdated(soundKey);
      } else {
        setSaveMsg(`Save failed: ${data.error}`);
      }
    } catch (err) {
      setSaveMsg(`Save failed: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }, [soundKey, editorData, params, soundInfo, onSoundUpdated]);

  // ── Group params by section ────────────────────────
  const groupedParams = useMemo(() => {
    if (!editorData) return {};
    const groups = {};
    for (const p of editorData.params || []) {
      const g = p.group || 'sound';
      if (!groups[g]) groups[g] = [];
      groups[g].push(p);
    }
    return groups;
  }, [editorData]);

  // ── Render ─────────────────────────────────────────

  if (loading) {
    return (
      <div className="wb-editor">
        <div className="wb-editor__loading">
          <div className="wb-spinner" />
          <span>Loading editor…</span>
        </div>
      </div>
    );
  }

  if (error && !editorData) {
    return (
      <div className="wb-editor">
        <div className="wb-editor__header">
          <h3>Sound Editor</h3>
          <button className="wb-btn wb-btn--ghost" onClick={onClose}>✕</button>
        </div>
        <div className="wb-editor__error">
          <p>Could not load editor for <code>{soundKey}</code></p>
          <p className="wb-text-dim">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="wb-editor">
      {/* ── Header ─────────────────────────────────── */}
      <div className="wb-editor__header">
        <div className="wb-editor__header-info">
          <h3 className="wb-editor__title">
            <span className="wb-editor__title-icon">🎛️</span>
            {soundKey}
          </h3>
          <span className="wb-editor__template-badge">
            {editorData?.templateLabel || editorData?.template}
          </span>
          {soundInfo?.description && (
            <p className="wb-editor__desc">{soundInfo.description}</p>
          )}
        </div>
        <button className="wb-btn wb-btn--ghost" onClick={onClose} title="Close editor">✕</button>
      </div>

      {/* ── Preview bar ─────────────────────────────── */}
      <div className="wb-editor__preview-bar">
        <button
          className={`wb-btn wb-btn--primary ${generating ? 'wb-btn--saving' : ''}`}
          onClick={handlePreview}
          disabled={generating}
        >
          {generating ? '⏳ Generating…' : '🔄 Preview'}
        </button>
        {previewUrl && (
          <>
            <button
              className={`wb-play-btn ${playingPreview ? 'wb-play-btn--active' : ''}`}
              onClick={playingPreview ? stopPreview : playPreview}
              title={playingPreview ? 'Stop' : 'Play preview'}
            >
              {playingPreview ? '⏹' : '▶'}
            </button>
            <div className="wb-editor__preview-waveform">
              <Waveform
                src={previewUrl}
                getAudioCtx={getAudioCtx}
                isPlaying={playingPreview}
                compact
              />
            </div>
            {onAddToCompare && (
              <button
                className="wb-btn wb-btn--ghost wb-btn--sm"
                onClick={() => onAddToCompare(previewUrl, `[edit] ${soundKey}`)}
                title="Add preview to compare"
              >⚖️</button>
            )}
          </>
        )}
        {error && <span className="wb-editor__error-inline">⚠ {error}</span>}
      </div>

      {/* ── Param sections ──────────────────────────── */}
      <div className="wb-editor__params">
        {Object.entries(groupedParams).map(([group, paramList]) => (
          <div key={group} className="wb-editor__group">
            <h4 className="wb-editor__group-title">
              {GROUP_LABELS[group] || group}
            </h4>
            {paramList.map(p => (
              <ParamControl
                key={p.key}
                param={p}
                value={params[p.key] ?? p.value}
                onChange={handleParamChange}
              />
            ))}
          </div>
        ))}
      </div>

      {/* ── Footer actions ──────────────────────────── */}
      <div className="wb-editor__footer">
        <button
          className="wb-btn wb-btn--ghost"
          onClick={handleResetAll}
          disabled={!hasChanges}
        >
          ↩ Reset All
        </button>
        <div className="wb-editor__footer-right">
          {saveMsg && (
            <span className={`wb-editor__save-msg ${saveMsg.startsWith('Save failed') ? 'wb-editor__save-msg--err' : ''}`}>
              {saveMsg}
            </span>
          )}
          <button
            className={`wb-btn wb-btn--primary ${saving ? 'wb-btn--saving' : ''}`}
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? '⏳ Saving…' : '💾 Save Preset'}
          </button>
        </div>
      </div>
    </div>
  );
}
