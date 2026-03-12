// ─────────────────────────────────────────────────────────
// ModuleLibrary.jsx — Sidebar panel for browsing/managing modules
//
// Lists all modules with mini preview thumbnails.
// CRUD: create, duplicate, delete modules. Import/export library.
// Category filter, socket compatibility viewer.
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect, useCallback, useState, useMemo } from 'react';
import { MODULE_SIZE, createBlankModule, cloneModule, generateId, deriveSockets, expandModules } from '../engine/moduleUtils.js';
import { TILE_COLORS } from '../utils/tileColors.js';

const THUMB_CELL = 8;  // pixels per cell in thumbnail
const THUMB_SIZE = MODULE_SIZE * THUMB_CELL;

/** Tiny canvas thumbnail for a module */
function ModuleThumb({ tiles }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !tiles) return;
    const ctx = canvas.getContext('2d');

    for (let r = 0; r < MODULE_SIZE; r++) {
      for (let c = 0; c < MODULE_SIZE; c++) {
        const tile = tiles[r]?.[c] || 'W';
        ctx.fillStyle = TILE_COLORS[tile] || '#444';
        ctx.fillRect(c * THUMB_CELL, r * THUMB_CELL, THUMB_CELL, THUMB_CELL);
      }
    }
  }, [tiles]);

  return (
    <canvas
      ref={canvasRef}
      width={THUMB_SIZE}
      height={THUMB_SIZE}
      className="module-thumb"
    />
  );
}

/** Purpose tag badge */
function PurposeBadge({ purpose }) {
  const colors = {
    empty: '#555',
    corridor: '#7a7a6e',
    spawn: '#4a7a4a',
    enemy: '#8a3a3a',
    loot: '#c9a02c',
    boss: '#9a2a6a',
  };

  return (
    <span
      className="purpose-badge"
      style={{ backgroundColor: colors[purpose] || '#555' }}
    >
      {purpose}
    </span>
  );
}

export default function ModuleLibrary({
  modules,
  selectedId,
  onSelect,
  onModulesChange,
}) {
  const fileInputRef = useRef(null);
  const [filter, setFilter] = useState('all'); // 'all' | 'empty' | 'corridor' | 'spawn' | 'enemy' | 'loot' | 'boss'
  const [showCompat, setShowCompat] = useState(false);

  // Compute filtered modules
  const filteredModules = useMemo(() => {
    if (filter === 'all') return modules;
    return modules.filter(m => m.purpose === filter);
  }, [modules, filter]);

  // Compute purpose counts for filter badges
  const purposeCounts = useMemo(() => {
    const counts = { all: modules.length };
    for (const m of modules) {
      counts[m.purpose] = (counts[m.purpose] || 0) + 1;
    }
    return counts;
  }, [modules]);

  // Compute socket compatibility for selected module
  const compatInfo = useMemo(() => {
    if (!showCompat || !selectedId) return null;
    const selected = modules.find(m => m.id === selectedId);
    if (!selected) return null;

    const selSockets = deriveSockets(selected.tiles);
    const allVariants = expandModules(modules);

    const result = { north: [], south: [], east: [], west: [] };
    const opposite = { north: 'south', south: 'north', east: 'west', west: 'east' };

    for (const dir of ['north', 'south', 'east', 'west']) {
      const mySocket = selSockets[dir];
      const seen = new Set();
      for (const v of allVariants) {
        if (v.sockets[opposite[dir]] === mySocket && !seen.has(v.sourceName)) {
          seen.add(v.sourceName);
          result[dir].push(v.sourceName);
        }
      }
    }

    return { sockets: selSockets, compatModules: result };
  }, [showCompat, selectedId, modules]);

  const handleAdd = useCallback(() => {
    const newMod = createBlankModule('New Module', 'empty');
    onModulesChange([...modules, newMod]);
    onSelect(newMod.id);
  }, [modules, onModulesChange, onSelect]);

  const handleDuplicate = useCallback(() => {
    const source = modules.find(m => m.id === selectedId);
    if (!source) return;
    const dup = cloneModule(source);
    dup.id = generateId();
    dup.name = source.name + ' (copy)';
    onModulesChange([...modules, dup]);
    onSelect(dup.id);
  }, [modules, selectedId, onModulesChange, onSelect]);

  const handleDelete = useCallback(() => {
    if (!selectedId) return;
    const remaining = modules.filter(m => m.id !== selectedId);
    onModulesChange(remaining);
    onSelect(remaining.length > 0 ? remaining[0].id : null);
  }, [modules, selectedId, onModulesChange, onSelect]);

  const handleExportLibrary = useCallback(() => {
    const json = JSON.stringify(modules, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'wfc-module-library.json';
    a.click();
    URL.revokeObjectURL(url);
  }, [modules]);

  const handleImportLibrary = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileLoad = useCallback((e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const imported = JSON.parse(ev.target.result);
        if (Array.isArray(imported)) {
          // Assign new IDs to avoid collisions
          const withNewIds = imported.map(m => ({
            ...m,
            id: generateId(),
          }));
          onModulesChange([...modules, ...withNewIds]);
        }
      } catch (err) {
        console.error('Failed to import module library:', err);
        alert('Invalid module library JSON file.');
      }
    };
    reader.readAsText(file);
    e.target.value = ''; // reset
  }, [modules, onModulesChange]);

  return (
    <div className="module-library">
      <div className="library-header">
        <h3>Module Library</h3>
        <span className="module-count">{modules.length} modules</span>
      </div>

      <div className="library-actions">
        <button onClick={handleAdd} title="Create new blank module">+ New</button>
        <button onClick={handleDuplicate} disabled={!selectedId} title="Duplicate selected">Dup</button>
        <button onClick={handleDelete} disabled={!selectedId} title="Delete selected">Del</button>
        <button onClick={handleExportLibrary} title="Export library JSON">Export</button>
        <button onClick={handleImportLibrary} title="Import library JSON">Import</button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          style={{ display: 'none' }}
          onChange={handleFileLoad}
        />
      </div>

      {/* Category filter */}
      <div className="library-filter">
        {['all', 'empty', 'corridor', 'spawn', 'enemy', 'loot', 'boss'].map((cat) => (
          <button
            key={cat}
            className={`filter-btn ${filter === cat ? 'active' : ''}`}
            onClick={() => setFilter(cat)}
            title={`Show ${cat} modules`}
          >
            {cat === 'all' ? 'All' : cat.charAt(0).toUpperCase() + cat.slice(1)}
            {purposeCounts[cat] > 0 && <span className="filter-count">{purposeCounts[cat]}</span>}
          </button>
        ))}
      </div>

      {/* Socket compatibility toggle */}
      <div className="library-compat-toggle">
        <button
          className={`compat-toggle-btn ${showCompat ? 'active' : ''}`}
          onClick={() => setShowCompat(prev => !prev)}
          disabled={!selectedId}
          title="Show which modules are compatible with the selected module's sockets"
        >
          {showCompat ? 'Hide' : 'Show'} Socket Compat
        </button>
      </div>

      {/* Socket compatibility panel */}
      {showCompat && compatInfo && (
        <div className="compat-panel">
          {['north', 'south', 'east', 'west'].map((dir) => (
            <div key={dir} className="compat-dir">
              <span className="compat-dir-label">{dir.charAt(0).toUpperCase()}: {compatInfo.sockets[dir]}</span>
              <span className="compat-dir-list">
                {compatInfo.compatModules[dir].length > 0
                  ? compatInfo.compatModules[dir].join(', ')
                  : '(none)'}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="library-list">
        {filteredModules.map((mod) => (
          <div
            key={mod.id}
            className={`library-item ${mod.id === selectedId ? 'selected' : ''}`}
            onClick={() => onSelect(mod.id)}
          >
            <ModuleThumb tiles={mod.tiles} />
            <div className="item-info">
              <div className="item-name">{mod.name}</div>
              <div className="item-meta">
                <PurposeBadge purpose={mod.purpose} />
                {mod.allowRotation && <span className="rot-badge">↻</span>}
                <span className="weight-badge">×{mod.weight}</span>
              </div>
            </div>
          </div>
        ))}
        {filteredModules.length === 0 && (
          <div className="library-empty">No modules match this filter.</div>
        )}
      </div>
    </div>
  );
}
