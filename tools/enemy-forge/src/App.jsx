// ─────────────────────────────────────────────────────────
// App.jsx — Root component for Enemy Forge
// ─────────────────────────────────────────────────────────

import React, { useState, useEffect, useCallback } from 'react';
import EnemyBrowser from './components/EnemyBrowser.jsx';
import EnemyEditor from './components/EnemyEditor.jsx';
import AffixEditor from './components/AffixEditor.jsx';
import ChampionTypeEditor from './components/ChampionTypeEditor.jsx';
import RosterEditor from './components/RosterEditor.jsx';
import Simulator from './components/Simulator.jsx';
import SpawnPreview from './components/SpawnPreview.jsx';
import SuperUniqueEditor from './components/SuperUniqueEditor.jsx';
import ExportPanel from './components/ExportPanel.jsx';
import './styles/main.css';

const API = 'http://localhost:5231';

/** Fetch all config files at once */
async function fetchConfigs() {
  const res = await fetch(`${API}/api/configs`);
  if (!res.ok) throw new Error('Failed to load configs');
  return res.json();
}

/** Fetch enemy metadata */
async function fetchMeta() {
  const res = await fetch(`${API}/api/enemy-meta`);
  if (!res.ok) throw new Error('Failed to load enemy metadata');
  return res.json();
}

/** Fetch floor roster data */
async function fetchRoster() {
  const res = await fetch(`${API}/api/roster`);
  if (!res.ok) throw new Error('Failed to load roster');
  return res.json();
}

/** Fetch sprite atlas data */
async function fetchSprites() {
  const res = await fetch(`${API}/api/sprites`);
  if (!res.ok) throw new Error('Failed to load sprite atlas');
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
  { id: 'enemies',    label: 'Enemies',      icon: '👹' },
  { id: 'affixes',    label: 'Affixes',       icon: '⚡' },
  { id: 'champions',  label: 'Champion Types', icon: '🛡️' },
  { id: 'roster',     label: 'Floor Roster',  icon: '📋' },
  { id: 'simulator',  label: 'TTK Simulator', icon: '⚔️' },
  { id: 'spawns',     label: 'Spawn Preview', icon: '🎲' },
  { id: 'uniques',    label: 'Super Uniques', icon: '💀' },
  { id: 'export',     label: 'Export',        icon: '💾' },
];

export default function App() {
  const [configs, setConfigs] = useState(null);
  const [meta, setMeta] = useState(null);
  const [roster, setRoster] = useState(null);
  const [spriteAtlas, setSpriteAtlas] = useState(null);
  const [activeTab, setActiveTab] = useState('enemies');
  const [selectedEnemy, setSelectedEnemy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saveStatus, setSaveStatus] = useState(null);
  const [dirty, setDirty] = useState(new Set());

  // ── Load all data ───────────────────────────────────
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cfgs, metaData, rosterData, spriteData] = await Promise.all([
        fetchConfigs(), fetchMeta(), fetchRoster(), fetchSprites()
      ]);
      setConfigs(cfgs);
      setMeta(metaData);
      setRoster(rosterData);
      setSpriteAtlas(spriteData);
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
      case 'enemies':
        return configs.enemies ? Object.keys(configs.enemies.enemies || {}).length : 0;
      case 'affixes':
        return configs.rarity ? Object.keys(configs.rarity.affixes || {}).length : 0;
      case 'champions':
        return configs.rarity ? Object.keys(configs.rarity.champion_types || {}).length : 0;
      case 'uniques':
        return configs.super_uniques ? Object.keys(configs.super_uniques.super_uniques || {}).length : 0;
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
        <h1>👹 Enemy Forge <span>Monster Workbench</span></h1>
        <div className="header-actions">
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
        {activeTab === 'enemies' && (
          <div className="enemy-layout">
            <EnemyBrowser
              enemies={configs.enemies?.enemies || {}}
              meta={meta}
              selectedEnemy={selectedEnemy}
              onSelect={setSelectedEnemy}
              spriteAtlas={spriteAtlas}
              skills={configs.skills}
            />
            <EnemyEditor
              enemy={selectedEnemy ? (configs.enemies?.enemies || {})[selectedEnemy] : null}
              enemyId={selectedEnemy}
              allEnemies={configs.enemies?.enemies || {}}
              skills={configs.skills}
              classes={configs.classes}
              meta={meta}
              spriteAtlas={spriteAtlas}
              onUpdate={(id, data) => {
                const updated = { ...configs.enemies, enemies: { ...configs.enemies.enemies, [id]: data } };
                updateConfig('enemies', updated);
              }}
              onCreate={(id, data) => {
                const updated = { ...configs.enemies, enemies: { ...configs.enemies.enemies, [id]: data } };
                updateConfig('enemies', updated);
                setSelectedEnemy(id);
              }}
              onDelete={(id) => {
                const enemies = { ...configs.enemies.enemies };
                delete enemies[id];
                updateConfig('enemies', { ...configs.enemies, enemies });
                if (selectedEnemy === id) setSelectedEnemy(null);
              }}
            />
          </div>
        )}
        {activeTab === 'affixes' && (
          <AffixEditor
            config={configs.rarity}
            meta={meta}
            onUpdate={(data) => updateConfig('rarity', data)}
          />
        )}
        {activeTab === 'champions' && (
          <ChampionTypeEditor
            config={configs.rarity}
            meta={meta}
            onUpdate={(data) => updateConfig('rarity', data)}
          />
        )}
        {activeTab === 'roster' && (
          <RosterEditor
            roster={roster}
            enemies={configs.enemies?.enemies || {}}
            meta={meta}
          />
        )}
        {activeTab === 'simulator' && (
          <Simulator
            enemies={configs.enemies?.enemies || {}}
            rarity={configs.rarity}
            classes={configs.classes}
            combat={configs.combat}
            skills={configs.skills}
            meta={meta}
          />
        )}
        {activeTab === 'spawns' && (
          <SpawnPreview
            rarity={configs.rarity}
            enemies={configs.enemies?.enemies || {}}
            meta={meta}
          />
        )}
        {activeTab === 'uniques' && (
          <SuperUniqueEditor
            config={configs.super_uniques}
            enemies={configs.enemies?.enemies || {}}
            rarity={configs.rarity}
            skills={configs.skills}
            meta={meta}
            onUpdate={(data) => updateConfig('super_uniques', data)}
          />
        )}
        {activeTab === 'export' && (
          <ExportPanel
            configs={configs}
            dirty={dirty}
            onSave={handleSave}
            onReload={loadData}
          />
        )}
      </div>
    </div>
  );
}
