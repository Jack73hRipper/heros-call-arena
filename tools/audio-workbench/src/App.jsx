// ─────────────────────────────────────────────────────────
// App.jsx — Root component for the Audio Workbench
// ─────────────────────────────────────────────────────────

import React, { useState, useEffect, useCallback, useRef } from 'react';
import SoundBrowser from './components/SoundBrowser.jsx';
import MappingEditor from './components/MappingEditor.jsx';
import ComparePanel from './components/ComparePanel.jsx';
import AssetLibrary from './components/AssetLibrary.jsx';
import './styles/workbench.css';

const API = 'http://localhost:5211';

/** Fetch audio-effects.json from the API */
async function fetchConfig() {
  const res = await fetch(`${API}/api/config`);
  if (!res.ok) throw new Error('Failed to load config');
  return res.json();
}

/** Fetch all sound files on disk */
async function fetchSounds() {
  const res = await fetch(`${API}/api/sounds`);
  if (!res.ok) throw new Error('Failed to load sounds');
  return res.json();
}

/** Save updated config back to disk */
async function saveConfig(config) {
  const res = await fetch(`${API}/api/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error('Failed to save config');
  return res.json();
}

export default function App() {
  // ── State ──────────────────────────────────────────────
  const [config, setConfig] = useState(null);
  const [diskFiles, setDiskFiles] = useState([]);
  const [activeTab, setActiveTab] = useState('browser');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saveStatus, setSaveStatus] = useState(null); // null | 'saving' | 'saved' | 'error'
  const [dirty, setDirty] = useState(false);
  const [compareList, setCompareList] = useState([]);

  // Web Audio context (shared)
  const audioCtxRef = useRef(null);

  function getAudioCtx() {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume();
    }
    return audioCtxRef.current;
  }

  // ── Load data on mount ──────────────────────────────────
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cfg, sounds] = await Promise.all([fetchConfig(), fetchSounds()]);
      setConfig(cfg);
      setDiskFiles(sounds.files || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Refresh disk files (after importing from library) ──
  const refreshDiskFiles = useCallback(async () => {
    try {
      const sounds = await fetchSounds();
      setDiskFiles(sounds.files || []);
    } catch (err) {
      console.error('Failed to refresh disk files:', err);
    }
  }, []);

  // ── Config updater (marks dirty) ───────────────────────
  const updateConfig = useCallback((updater) => {
    setConfig(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      return next;
    });
    setDirty(true);
    setSaveStatus(null);
  }, []);

  // ── Save handler ───────────────────────────────────────
  const handleSave = useCallback(async () => {
    if (!config) return;
    setSaveStatus('saving');
    try {
      await saveConfig(config);
      setSaveStatus('saved');
      setDirty(false);
      setTimeout(() => setSaveStatus(null), 2500);
    } catch (err) {
      setSaveStatus('error');
      console.error('Save failed:', err);
    }
  }, [config]);

  // ── Compare list helpers ───────────────────────────────
  const addToCompare = useCallback((soundPath, label) => {
    setCompareList(prev => {
      if (prev.length >= 6) return prev;
      if (prev.some(s => s.path === soundPath)) return prev;
      return [...prev, { path: soundPath, label: label || soundPath.split('/').pop() }];
    });
    setActiveTab('compare');
  }, []);

  const removeFromCompare = useCallback((soundPath) => {
    setCompareList(prev => prev.filter(s => s.path !== soundPath));
  }, []);

  const clearCompare = useCallback(() => setCompareList([]), []);

  // ── Validation helpers ─────────────────────────────────
  const validation = React.useMemo(() => {
    if (!config || !diskFiles.length) return { orphaned: [], broken: [] };

    const mappedPaths = new Set(Object.values(config._soundFiles || {}));
    const diskPaths = new Set(diskFiles.map(f => f.path));

    // Files on disk not referenced in _soundFiles
    const orphaned = diskFiles.filter(f => !mappedPaths.has(f.path));
    // Keys in _soundFiles whose path doesn't exist on disk
    const broken = Object.entries(config._soundFiles || {})
      .filter(([, filePath]) => !diskPaths.has(filePath))
      .map(([key, filePath]) => ({ key, path: filePath }));

    return { orphaned, broken };
  }, [config, diskFiles]);

  // ── Render ─────────────────────────────────────────────
  if (loading) {
    return (
      <div className="wb-loading">
        <div className="wb-spinner" />
        <p>Loading Audio Workbench...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="wb-error">
        <h2>Connection Error</h2>
        <p>{error}</p>
        <p className="wb-error-hint">Make sure the API server is running on port 5211.</p>
        <button className="wb-btn wb-btn--primary" onClick={loadData}>Retry</button>
      </div>
    );
  }

  return (
    <div className="wb-app">
      {/* ── Header ─────────────────────────────────── */}
      <header className="wb-header">
        <div className="wb-header__left">
          <h1 className="wb-header__title">
            <span className="wb-header__icon">♫</span>
            Audio Workbench
          </h1>
          <span className="wb-header__stats">
            {diskFiles.length} files · {Object.keys(config?._soundFiles || {}).length} mapped
            {validation.orphaned.length > 0 && (
              <span className="wb-badge wb-badge--warn">{validation.orphaned.length} unmapped</span>
            )}
            {validation.broken.length > 0 && (
              <span className="wb-badge wb-badge--error">{validation.broken.length} broken</span>
            )}
          </span>
        </div>
        <div className="wb-header__right">
          {dirty && <span className="wb-dirty-indicator">● Unsaved changes</span>}
          <button
            className={`wb-btn wb-btn--save ${saveStatus === 'saving' ? 'wb-btn--saving' : ''}`}
            onClick={handleSave}
            disabled={!dirty || saveStatus === 'saving'}
          >
            {saveStatus === 'saving' ? 'Saving...'
              : saveStatus === 'saved' ? '✓ Saved!'
              : saveStatus === 'error' ? '✗ Error'
              : '💾 Save'}
          </button>
          <button className="wb-btn wb-btn--secondary" onClick={loadData}>⟳ Reload</button>
        </div>
      </header>

      {/* ── Tab Bar ────────────────────────────────── */}
      <nav className="wb-tabs">
        <button
          className={`wb-tab ${activeTab === 'browser' ? 'wb-tab--active' : ''}`}
          onClick={() => setActiveTab('browser')}
        >
          📁 Sound Browser
        </button>
        <button
          className={`wb-tab ${activeTab === 'editor' ? 'wb-tab--active' : ''}`}
          onClick={() => setActiveTab('editor')}
        >
          🎛️ Mapping Editor
        </button>
        <button
          className={`wb-tab ${activeTab === 'compare' ? 'wb-tab--active' : ''}`}
          onClick={() => setActiveTab('compare')}
        >
          ⚖️ Compare {compareList.length > 0 && `(${compareList.length})`}
        </button>
        <button
          className={`wb-tab ${activeTab === 'library' ? 'wb-tab--active' : ''}`}
          onClick={() => setActiveTab('library')}
        >
          📦 Asset Library
        </button>
      </nav>

      {/* ── Panel Content ──────────────────────────── */}
      <main className="wb-main">
        {activeTab === 'browser' && (
          <SoundBrowser
            diskFiles={diskFiles}
            config={config}
            validation={validation}
            getAudioCtx={getAudioCtx}
            onAddToCompare={addToCompare}
            onUpdateConfig={updateConfig}
          />
        )}
        {activeTab === 'editor' && (
          <MappingEditor
            config={config}
            diskFiles={diskFiles}
            getAudioCtx={getAudioCtx}
            onUpdateConfig={updateConfig}
            onAddToCompare={addToCompare}
          />
        )}
        {activeTab === 'compare' && (
          <ComparePanel
            compareList={compareList}
            getAudioCtx={getAudioCtx}
            onRemove={removeFromCompare}
            onClear={clearCompare}
          />
        )}
        {activeTab === 'library' && (
          <AssetLibrary
            config={config}
            diskFiles={diskFiles}
            getAudioCtx={getAudioCtx}
            onUpdateConfig={updateConfig}
            onAddToCompare={addToCompare}
            onRefreshDiskFiles={refreshDiskFiles}
          />
        )}
      </main>
    </div>
  );
}
