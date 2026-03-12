// ─────────────────────────────────────────────────────────
// App.jsx — Root component for the WFC Dungeon Lab
//
// Layout: Left sidebar (module library) | Center (editor/preview) | Right sidebar (generator/export)
// Two modes: "editor" (edit modules) and "preview" (view generated dungeon)
// ─────────────────────────────────────────────────────────

import React, { useState, useCallback, useEffect } from 'react';
import { PRESET_MODULES } from './engine/presets.js';
import { cloneModule, MODULE_SIZE } from './engine/moduleUtils.js';
import ModuleEditor from './components/ModuleEditor.jsx';
import ModuleLibrary from './components/ModuleLibrary.jsx';
import GeneratorPanel from './components/GeneratorPanel.jsx';
import PreviewCanvas from './components/PreviewCanvas.jsx';
import ExportPanel from './components/ExportPanel.jsx';
import './styles/App.css';

/** LocalStorage key for persisting the module library */
const STORAGE_KEY = 'wfc-dungeon-lab-modules';

/** Decorator fields that must exist on every module for the decorator to work */
const DECORATOR_FIELDS = ['contentRole', 'spawnSlots', 'maxEnemies', 'maxChests', 'canBeBoss', 'canBeSpawn'];

/**
 * Load modules from localStorage, auto-merging any new built-in presets.
 * On every load, we check if any PRESET_MODULES ids are missing from the
 * saved library. Missing presets are appended so new built-in modules
 * always appear without requiring a cache clear.
 *
 * Also back-fills decorator metadata (contentRole, spawnSlots, etc.) onto
 * existing preset modules if the stored copy is missing those fields.
 * This handles the case where modules were saved before decorator support
 * was added — without this, all modules default to 'structural' and the
 * decorator has zero flexible rooms to work with.
 */
/**
 * Resize a module's tile grid to match MODULE_SIZE.
 * Pads with walls if smaller, trims if larger.
 */
function resizeTiles(tiles, targetSize) {
  const result = [];
  for (let r = 0; r < targetSize; r++) {
    const row = [];
    for (let c = 0; c < targetSize; c++) {
      row.push(tiles[r]?.[c] ?? 'W');
    }
    result.push(row);
  }
  return result;
}

function loadModules() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed) && parsed.length > 0) {
        // Build a lookup for preset modules by ID
        const presetLookup = new Map(PRESET_MODULES.map(m => [m.id, m]));

        // ── Tile-size migration ────────────────────────────────
        // If any stored module has tiles sized differently from MODULE_SIZE
        // (e.g. old 6×6 modules after upgrading to 8×8), we need to fix them.
        // Preset modules: replace entirely with the current built-in version.
        // Custom modules: resize tiles (pad/trim with walls).
        let migrated = false;
        const updated = parsed.map(m => {
          const tileRows = m.tiles?.length || 0;
          const tileCols = m.tiles?.[0]?.length || 0;
          const sizeOk = tileRows === MODULE_SIZE && tileCols === MODULE_SIZE;

          const preset = presetLookup.get(m.id);

          if (preset) {
            // Preset module — always sync tiles + decorator fields from latest built-in
            const needsTileUpdate = !sizeOk;
            const needsFieldPatch = DECORATOR_FIELDS.some(f => m[f] === undefined);
            if (needsTileUpdate) {
              // Full replacement with current preset (tiles changed entirely)
              migrated = true;
              console.log(`[WFC Lab] Migrating preset "${m.name}" tiles to ${MODULE_SIZE}×${MODULE_SIZE}`);
              return cloneModule(preset);
            }
            if (needsFieldPatch) {
              migrated = true;
              const merged = { ...m };
              for (const field of DECORATOR_FIELDS) {
                if (merged[field] === undefined) {
                  merged[field] = JSON.parse(JSON.stringify(preset[field]));
                }
              }
              return merged;
            }
            return m;
          }

          // Custom module — resize tiles if needed
          if (!sizeOk && tileRows > 0) {
            migrated = true;
            console.log(`[WFC Lab] Resizing custom module "${m.name}" from ${tileCols}×${tileRows} to ${MODULE_SIZE}×${MODULE_SIZE}`);
            return {
              ...m,
              width: MODULE_SIZE,
              height: MODULE_SIZE,
              tiles: resizeTiles(m.tiles, MODULE_SIZE),
            };
          }
          return m;
        });

        if (migrated) {
          console.log('[WFC Lab] Module tile-size migration complete');
        }

        // Append any entirely new presets
        const existingIds = new Set(updated.map(m => m.id));
        const missing = PRESET_MODULES.filter(m => !existingIds.has(m.id));
        if (missing.length > 0) {
          console.log(`[WFC Lab] Adding ${missing.length} new preset module(s):`, missing.map(m => m.name).join(', '));
          updated.push(...missing.map(m => cloneModule(m)));
        }

        if (migrated || missing.length > 0) {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        }
        return updated;
      }
    }
  } catch (e) {
    console.warn('Failed to load saved modules, using presets:', e);
  }
  return PRESET_MODULES.map(m => cloneModule(m));
}

export default function App() {
  // ── State ──
  const [modules, setModules] = useState(loadModules);
  const [selectedModuleId, setSelectedModuleId] = useState(modules[0]?.id || null);
  const [mode, setMode] = useState('editor'); // 'editor' | 'preview'
  const [wfcResult, setWfcResult] = useState(null);
  const [importedMap, setImportedMap] = useState(null);

  const selectedModule = modules.find(m => m.id === selectedModuleId) || null;

  // ── Persist modules to localStorage ──
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(modules));
    } catch (e) {
      console.warn('Failed to save modules:', e);
    }
  }, [modules]);

  // ── Module editing ──
  const handleModuleChange = useCallback((updatedModule) => {
    setModules(prev =>
      prev.map(m => m.id === updatedModule.id ? updatedModule : m)
    );
  }, []);

  const handleModulesChange = useCallback((newModules) => {
    setModules(newModules);
  }, []);

  // ── Generation ──
  const handleGenerate = useCallback((result) => {
    setWfcResult(result);
    setImportedMap(null);
    if (result.success) {
      setMode('preview');
    }
  }, []);

  // ── Import ──
  const handleImportMap = useCallback((imported) => {
    setImportedMap(imported);
    setWfcResult(null);
    setMode('preview');
  }, []);

  // ── Swap a module in the generated dungeon (click-to-swap) ──
  const handleSwapModule = useCallback((row, col, variant) => {
    if (!wfcResult || !wfcResult.grid || !wfcResult.tileMap) return;

    // Deep clone the grid and tile map
    const newGrid = wfcResult.grid.map(r => r.map(c => ({ ...c })));
    const newTileMap = wfcResult.tileMap.map(r => [...r]);

    // Update the grid cell — store variant info directly since it may not be in the original variants array
    const cell = newGrid[row][col];
    cell.chosenVariant = cell.chosenVariant; // keep index for compat, but we need to track the new variant
    cell.swappedVariant = variant; // mark as swapped

    // Stamp the new module's tiles into the tile map
    const startR = row * MODULE_SIZE;
    const startC = col * MODULE_SIZE;
    for (let lr = 0; lr < MODULE_SIZE; lr++) {
      for (let lc = 0; lc < MODULE_SIZE; lc++) {
        if (variant.tiles[lr] && variant.tiles[lr][lc] !== undefined) {
          newTileMap[startR + lr][startC + lc] = variant.tiles[lr][lc];
        }
      }
    }

    // Build a new variants array that includes any swapped variants
    const newVariants = [...(wfcResult.variants || [])];
    // Find or add this variant to the array, update the cell's chosenVariant index
    let varIdx = newVariants.findIndex(v =>
      v.sourceId === variant.sourceId && v.rotation === variant.rotation
    );
    if (varIdx === -1) {
      varIdx = newVariants.length;
      newVariants.push(variant);
    }
    newGrid[row][col].chosenVariant = varIdx;

    setWfcResult(prev => ({
      ...prev,
      grid: newGrid,
      tileMap: newTileMap,
      variants: newVariants,
    }));
  }, [wfcResult]);

  // ── Reset to presets ──
  const handleResetLibrary = useCallback(() => {
    if (confirm('Reset module library to built-in presets? This will lose all custom modules.')) {
      const fresh = PRESET_MODULES.map(m => cloneModule(m));
      setModules(fresh);
      setSelectedModuleId(fresh[0]?.id || null);
    }
  }, []);

  // Determine what to show in the preview
  const previewTileMap = wfcResult?.tileMap || importedMap?.tileMap || null;
  const previewGrid = wfcResult?.grid || null;
  const previewVariants = wfcResult?.variants || null;

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="app-header">
        <h1>WFC Dungeon Lab</h1>
        <nav className="mode-tabs">
          <button
            className={mode === 'editor' ? 'active' : ''}
            onClick={() => setMode('editor')}
          >
            Module Editor
          </button>
          <button
            className={mode === 'preview' ? 'active' : ''}
            onClick={() => setMode('preview')}
          >
            Dungeon Preview
          </button>
        </nav>
        <div className="header-actions">
          <button className="btn-reset" onClick={handleResetLibrary} title="Reset to built-in presets">
            Reset Library
          </button>
        </div>
      </header>

      {/* ── Main Layout ── */}
      <div className="app-body">
        {/* Left Sidebar — Module Library */}
        <aside className="sidebar-left">
          <ModuleLibrary
            modules={modules}
            selectedId={selectedModuleId}
            onSelect={(id) => {
              setSelectedModuleId(id);
              if (id) setMode('editor');
            }}
            onModulesChange={handleModulesChange}
          />
        </aside>

        {/* Center — Editor or Preview */}
        <main className="center-panel">
          {mode === 'editor' ? (
            <ModuleEditor
              module={selectedModule}
              onModuleChange={handleModuleChange}
            />
          ) : (
            <PreviewCanvas
              tileMap={previewTileMap}
              wfcGrid={previewGrid}
              variants={previewVariants}
              modules={modules}
              onSwapModule={wfcResult ? handleSwapModule : null}
              decoratedRooms={wfcResult?.decoratedRooms}
            />
          )}
        </main>

        {/* Right Sidebar — Generator + Export */}
        <aside className="sidebar-right">
          <GeneratorPanel
            modules={modules}
            onGenerate={handleGenerate}
            lastResult={wfcResult}
          />
          <ExportPanel
            tileMap={previewTileMap}
            wfcGrid={previewGrid}
            variants={previewVariants}
            modules={modules}
            onImportMap={handleImportMap}
            onModulesChange={handleModulesChange}
          />
        </aside>
      </div>
    </div>
  );
}
