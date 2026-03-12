// ─────────────────────────────────────────────────────────
// App.jsx — Root component for Item Forge
// ─────────────────────────────────────────────────────────

import React, { useState, useEffect, useCallback } from 'react';
import AffixEditor from './components/AffixEditor.jsx';
import BaseItemEditor from './components/BaseItemEditor.jsx';
import UniqueEditor from './components/UniqueEditor.jsx';
import SetEditor from './components/SetEditor.jsx';
import ItemSimulator from './components/ItemSimulator.jsx';
import './styles/forge.css';

const API = 'http://localhost:5221';

/** Fetch all config files at once */
async function fetchConfigs() {
  const res = await fetch(`${API}/api/configs`);
  if (!res.ok) throw new Error('Failed to load configs');
  return res.json();
}

/** Fetch stat metadata */
async function fetchStatsMeta() {
  const res = await fetch(`${API}/api/stats-meta`);
  if (!res.ok) throw new Error('Failed to load stats metadata');
  return res.json();
}

/** Save a single config back to disk */
async function saveConfig(key, data) {
  const res = await fetch(`${API}/api/config/${key}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to save ${key}`);
  return res.json();
}

const TABS = [
  { id: 'affixes',   label: 'Affixes',    icon: '⚡' },
  { id: 'items',     label: 'Base Items',  icon: '🗡️' },
  { id: 'uniques',   label: 'Uniques',     icon: '⭐' },
  { id: 'sets',      label: 'Sets',        icon: '🛡️' },
  { id: 'simulator', label: 'Simulator',   icon: '🎲' },
];

export default function App() {
  const [configs, setConfigs] = useState(null);
  const [statsMeta, setStatsMeta] = useState(null);
  const [activeTab, setActiveTab] = useState('affixes');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saveStatus, setSaveStatus] = useState(null);
  const [dirty, setDirty] = useState(new Set());

  // ── Load all data ───────────────────────────────────
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cfgs, meta] = await Promise.all([fetchConfigs(), fetchStatsMeta()]);
      setConfigs(cfgs);
      setStatsMeta(meta);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Update a config locally (marks dirty) ───────────
  const updateConfig = useCallback((key, data) => {
    setConfigs(prev => ({ ...prev, [key]: data }));
    setDirty(prev => new Set([...prev, key]));
    setSaveStatus(null);
  }, []);

  // ── Save all dirty configs ──────────────────────────
  const handleSave = useCallback(async () => {
    if (dirty.size === 0) return;
    setSaveStatus('saving');
    try {
      for (const key of dirty) {
        await saveConfig(key, configs[key]);
      }
      setDirty(new Set());
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus(null), 2000);
    } catch (err) {
      setSaveStatus('error');
      console.error('Save failed:', err);
    }
  }, [configs, dirty]);

  // ── Keyboard shortcut: Ctrl+S ───────────────────────
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleSave]);

  // ── Count helpers ───────────────────────────────────
  function getTabCount(tabId) {
    if (!configs) return 0;
    switch (tabId) {
      case 'affixes': {
        const a = configs.affixes;
        if (!a) return 0;
        return Object.keys(a.prefixes || {}).length + Object.keys(a.suffixes || {}).length;
      }
      case 'items':
        return configs.items ? Object.keys(configs.items.items || {}).length : 0;
      case 'uniques':
        return configs.uniques ? Object.keys(configs.uniques.uniques || {}).length : 0;
      case 'sets':
        return configs.sets ? Object.keys(configs.sets.sets || {}).length : 0;
      default: return null;
    }
  }

  // ── Loading / Error states ──────────────────────────
  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner" />
        <div>Loading configs...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="loading-screen">
        <div style={{ color: 'var(--danger)', marginBottom: 12 }}>Error: {error}</div>
        <button className="btn btn-primary" onClick={loadData}>Retry</button>
      </div>
    );
  }

  // ── Render ──────────────────────────────────────────
  return (
    <div className="app">
      {/* Header */}
      <div className="app-header">
        <h1>⚒️ Item Forge <span>Equipment Workbench</span></h1>
        {dirty.size > 0 && (
          <button className="btn btn-primary" onClick={handleSave}>
            💾 Save Changes ({dirty.size})
          </button>
        )}
        {saveStatus && (
          <span className={`save-indicator ${saveStatus}`}>
            {saveStatus === 'saving' && '⏳ Saving...'}
            {saveStatus === 'saved' && '✅ Saved!'}
            {saveStatus === 'error' && '❌ Save failed'}
          </span>
        )}
      </div>

      {/* Tab Bar */}
      <div className="tab-bar">
        {TABS.map(tab => {
          const count = getTabCount(tab.id);
          return (
            <button
              key={tab.id}
              className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.icon} {tab.label}
              {count !== null && <span className="tab-count">({count})</span>}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="tab-content">
        {activeTab === 'affixes' && (
          <AffixEditor
            config={configs.affixes}
            statsMeta={statsMeta}
            onUpdate={(data) => updateConfig('affixes', data)}
          />
        )}
        {activeTab === 'items' && (
          <BaseItemEditor
            config={configs.items}
            statsMeta={statsMeta}
            onUpdate={(data) => updateConfig('items', data)}
          />
        )}
        {activeTab === 'uniques' && (
          <UniqueEditor
            config={configs.uniques}
            statsMeta={statsMeta}
            onUpdate={(data) => updateConfig('uniques', data)}
          />
        )}
        {activeTab === 'sets' && (
          <SetEditor
            config={configs.sets}
            statsMeta={statsMeta}
            onUpdate={(data) => updateConfig('sets', data)}
          />
        )}
        {activeTab === 'simulator' && (
          <ItemSimulator
            configs={configs}
            statsMeta={statsMeta}
          />
        )}
      </div>
    </div>
  );
}
