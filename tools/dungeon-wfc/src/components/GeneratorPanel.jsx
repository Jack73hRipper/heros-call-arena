// ─────────────────────────────────────────────────────────
// GeneratorPanel.jsx — WFC generation controls
//
// Configure grid size, seed, constraints; run generation.
// Dungeon templates, batch generation, difficulty scoring.
// Shows dungeon statistics and connectivity info after generation.
// ─────────────────────────────────────────────────────────

import React, { useState, useCallback } from 'react';
import { SIZE_PRESETS } from '../engine/presets.js';
import { MODULE_SIZE } from '../engine/moduleUtils.js';
import { runWFC, computeStats } from '../engine/wfc.js';
import { decorateRooms, DEFAULT_DECORATOR_SETTINGS } from '../engine/roomDecorator.js';

/** Dungeon template presets — modify module weights AND decorator defaults */
const DUNGEON_TEMPLATES = [
  {
    name: 'Balanced',
    description: 'Default balanced dungeon',
    icon: '⚖️',
    weightOverrides: {}, // No overrides — uses module defaults
    decoratorDefaults: {}, // Use default decorator settings
  },
  {
    name: 'Dense Catacomb',
    description: 'Tight corridors, many enemies, claustrophobic',
    icon: '🪦',
    weightOverrides: {
      corridor: 2.5,   // Boost corridor weight multiplier
      empty: 0.4,      // Fewer open rooms
      enemy: 2.0,      // More enemies
      boss: 0.3,
      loot: 0.3,
      spawn: 1.0,
    },
    decoratorDefaults: {
      enemyDensity: 0.7,
      lootDensity: 0.1,
      emptyRoomChance: 0.1,
      guaranteeBoss: false,
      scatterEnemies: true,
      scatterChests: false,
    },
  },
  {
    name: 'Open Ruins',
    description: 'Spacious rooms, fewer walls, exploration-focused',
    icon: '🏛️',
    weightOverrides: {
      corridor: 0.6,
      empty: 2.5,      // More rooms
      enemy: 0.8,
      boss: 0.5,
      loot: 1.5,
      spawn: 1.0,
    },
    decoratorDefaults: {
      enemyDensity: 0.25,
      lootDensity: 0.3,
      emptyRoomChance: 0.35,
      guaranteeBoss: true,
      scatterEnemies: true,
      scatterChests: true,
    },
  },
  {
    name: 'Boss Rush',
    description: 'Direct paths to boss, minimal detours',
    icon: '💀',
    weightOverrides: {
      corridor: 1.8,
      empty: 0.5,
      enemy: 1.5,
      boss: 2.0,       // Boss rooms more likely
      loot: 0.3,
      spawn: 1.0,
    },
    decoratorDefaults: {
      enemyDensity: 0.6,
      lootDensity: 0.05,
      emptyRoomChance: 0.1,
      guaranteeBoss: true,
      scatterEnemies: true,
      scatterChests: false,
    },
  },
  {
    name: 'Treasure Vault',
    description: 'Loot-heavy, dead-ends with chests, guarded rooms',
    icon: '💰',
    weightOverrides: {
      corridor: 1.0,
      empty: 1.0,
      enemy: 1.2,
      boss: 0.2,
      loot: 3.0,       // Lots of treasure
      spawn: 1.0,
    },
    decoratorDefaults: {
      enemyDensity: 0.3,
      lootDensity: 0.5,
      emptyRoomChance: 0.1,
      guaranteeBoss: false,
      guaranteeSpawn: true,
      scatterEnemies: true,
      scatterChests: true,
    },
  },
];

/**
 * Score dungeon difficulty from 0-100 based on tile composition
 * and (optionally) decorator room assignments for enhanced accuracy.
 */
function scoreDifficulty(stats, decorationStats) {
  if (!stats) return null;
  let score = 0;

  // Enemy density (more enemies = harder) — counts both fixed AND decorator-placed E tiles
  const enemyRatio = stats.enemySpawns / Math.max(1, stats.floors + stats.corridors);
  score += Math.min(30, enemyRatio * 500);

  // Boss presence — counts both fixed AND decorator-placed B tiles
  score += Math.min(20, stats.bossSpawns * 10);

  // Low chest-to-enemy ratio = harder (fewer rewards)
  const rewardRatio = stats.chests / Math.max(1, stats.enemySpawns);
  score += Math.max(0, 15 - rewardRatio * 10);

  // Low floor ratio = more walls = tighter = harder
  const floorPct = parseFloat(stats.floorRatio);
  if (floorPct < 30) score += 15;
  else if (floorPct < 45) score += 8;

  // Door density (more doors = more chokepoints)
  const doorRatio = stats.doors / Math.max(1, stats.totalTiles);
  score += Math.min(10, doorRatio * 500);

  // Spawn scarcity
  if (stats.spawns < 4) score += 10;
  else if (stats.spawns < 8) score += 5;

  // Decorator-aware bonus: if decorator stats available, factor in room-level info
  if (decorationStats) {
    const totalDecoratable = decorationStats.flexibleRooms + decorationStats.fixedRooms;
    if (totalDecoratable > 0) {
      const rc = decorationStats.roleCount || {};
      // High enemy-room ratio among all content rooms adds difficulty
      const enemyRoomRatio = (rc.enemy || 0) / Math.max(1, totalDecoratable);
      score += Math.min(5, enemyRoomRatio * 10);
      // Multiple boss rooms are extra dangerous
      if ((rc.boss || 0) >= 2) score += 5;
      // Low loot-to-enemy room ratio = under-rewarded
      const lootToEnemy = (rc.loot || 0) / Math.max(1, (rc.enemy || 0));
      if (lootToEnemy < 0.3) score += 3;
    }
  }

  return Math.min(100, Math.round(score));
}

function difficultyLabel(score) {
  if (score == null) return '';
  if (score < 20) return 'Trivial';
  if (score < 40) return 'Easy';
  if (score < 55) return 'Moderate';
  if (score < 70) return 'Hard';
  if (score < 85) return 'Brutal';
  return 'Nightmare';
}

function difficultyColor(score) {
  if (score == null) return '#888';
  if (score < 20) return '#8c8';
  if (score < 40) return '#ac8';
  if (score < 55) return '#cc8';
  if (score < 70) return '#ca8';
  if (score < 85) return '#c88';
  return '#f66';
}

/** Default weight multipliers (all 1.0 = no change) */
const DEFAULT_WEIGHTS = { corridor: 1.0, empty: 1.0, enemy: 1.0, boss: 1.0, loot: 1.0, spawn: 1.0 };

export default function GeneratorPanel({
  modules,
  onGenerate,
  lastResult,
}) {
  // Editable grid dimensions (default to Medium 4×4)
  const [gridRows, setGridRows] = useState(4);
  const [gridCols, setGridCols] = useState(4);
  const [seed, setSeed] = useState(Math.floor(Math.random() * 99999));
  const [maxRetries, setMaxRetries] = useState(50);
  const [isGenerating, setIsGenerating] = useState(false);
  const [forceBorderWalls, setForceBorderWalls] = useState(true);
  const [ensureConnected, setEnsureConnected] = useState(true);
  const [templateIdx, setTemplateIdx] = useState(0);
  const [batchCount, setBatchCount] = useState(1);
  const [batchResults, setBatchResults] = useState(null);
  // Per-category weight multipliers (exposed as sliders)
  const [styleWeights, setStyleWeights] = useState({ ...DEFAULT_WEIGHTS });

  // ── Room Decorator Settings ──
  const [enableDecorator, setEnableDecorator] = useState(true);
  const [decoratorSettings, setDecoratorSettings] = useState({ ...DEFAULT_DECORATOR_SETTINGS });

  const tileW = gridCols * MODULE_SIZE;
  const tileH = gridRows * MODULE_SIZE;
  const template = DUNGEON_TEMPLATES[templateIdx];

  const stats = lastResult?.tileMap ? computeStats(lastResult.tileMap) : null;
  const difficulty = scoreDifficulty(stats, lastResult?.decorationStats);

  /** Apply a template: snap weight sliders AND decorator settings to template values */
  const applyTemplateToSliders = useCallback((idx) => {
    setTemplateIdx(idx);
    const t = DUNGEON_TEMPLATES[idx];
    // Apply weight overrides
    if (!t.weightOverrides || Object.keys(t.weightOverrides).length === 0) {
      setStyleWeights({ ...DEFAULT_WEIGHTS });
    } else {
      setStyleWeights({ ...DEFAULT_WEIGHTS, ...t.weightOverrides });
    }
    // Apply decorator defaults (merge with base defaults so missing keys reset)
    if (t.decoratorDefaults && Object.keys(t.decoratorDefaults).length > 0) {
      setDecoratorSettings({ ...DEFAULT_DECORATOR_SETTINGS, ...t.decoratorDefaults });
    } else {
      setDecoratorSettings({ ...DEFAULT_DECORATOR_SETTINGS });
    }
  }, []);

  /** Apply a size preset: fill the row/col fields */
  const applySizePreset = useCallback((preset) => {
    setGridRows(preset.gridRows);
    setGridCols(preset.gridCols);
  }, []);

  /** Update a single weight slider */
  const updateWeight = useCallback((key, value) => {
    setStyleWeights(prev => ({ ...prev, [key]: value }));
  }, []);

  /** Update a single decorator setting */
  const updateDecoratorSetting = useCallback((key, value) => {
    setDecoratorSettings(prev => ({ ...prev, [key]: value }));
  }, []);

  const doGenerate = useCallback((seedVal, mods) => {
    return runWFC({
      modules: mods,
      gridRows,
      gridCols,
      seed: seedVal,
      maxRetries,
      forceBorderWalls,
      ensureConnected,
    });
  }, [gridRows, gridCols, maxRetries, forceBorderWalls, ensureConnected]);

  /** Apply current slider weights to the module list */
  const applySliderWeights = useCallback((mods) => {
    return mods.map(m => {
      const mult = styleWeights[m.purpose];
      if (mult !== undefined && mult !== 1.0) {
        return { ...m, weight: m.weight * mult };
      }
      return m;
    });
  }, [styleWeights]);

  /** Apply decorator to a WFC result if enabled, preserving rawTileMap */
  const applyDecorator = useCallback((result, seedVal) => {
    // Always preserve the raw (pre-decoration) tileMap for re-decoration
    const rawTileMap = result.rawTileMap || result.tileMap;

    if (!enableDecorator || !result.success || !result.grid || !rawTileMap) {
      return { ...result, rawTileMap };
    }
    // Deep-clone rawTileMap as input so decorator doesn't mutate it
    const cleanMap = rawTileMap.map(row => [...row]);
    const decorated = decorateRooms({
      grid: result.grid,
      variants: result.variants,
      tileMap: cleanMap,
      seed: seedVal,
      settings: decoratorSettings,
    });
    return {
      ...result,
      rawTileMap,
      tileMap: decorated.tileMap,
      decoratedRooms: decorated.decoratedRooms,
      decorationStats: decorated.stats,
    };
  }, [enableDecorator, decoratorSettings]);

  const handleGenerate = useCallback(() => {
    setIsGenerating(true);
    setBatchResults(null);
    setTimeout(() => {
      const templatedModules = applySliderWeights(modules);
      if (batchCount <= 1) {
        const result = doGenerate(seed, templatedModules);
        const decorated = applyDecorator(result, seed);
        onGenerate(decorated);
      } else {
        // Batch generation
        const results = [];
        for (let i = 0; i < batchCount; i++) {
          const batchSeed = seed + i * 7919; // Space seeds apart
          const result = doGenerate(batchSeed, templatedModules);
          if (result.success) {
            const dec = applyDecorator(result, batchSeed);
            const s = computeStats(dec.tileMap);
            results.push({
              ...dec,
              batchSeed,
              stats: s,
              difficulty: scoreDifficulty(s, dec.decorationStats),
              index: i,
            });
          }
        }
        // Sort by quality: highest floor ratio + connected + has spawns
        results.sort((a, b) => {
          const scoreA = parseFloat(a.stats.floorRatio) + (a.stats.spawns > 0 ? 20 : 0) + (a.connectivity?.corridorsCarved === 0 ? 10 : 0);
          const scoreB = parseFloat(b.stats.floorRatio) + (b.stats.spawns > 0 ? 20 : 0) + (b.connectivity?.corridorsCarved === 0 ? 10 : 0);
          return scoreB - scoreA;
        });
        setBatchResults(results);
        if (results.length > 0) {
          onGenerate(results[0]); // Auto-select best
        } else {
          onGenerate({ success: false, error: `All ${batchCount} batch attempts failed` });
        }
      }
      setIsGenerating(false);
    }, 50);
  }, [modules, styleWeights, seed, batchCount, doGenerate, onGenerate, applySliderWeights, applyDecorator]);

  const handleRandomSeed = useCallback(() => {
    setSeed(Math.floor(Math.random() * 99999));
  }, []);

  const handleQuickGenerate = useCallback(() => {
    const newSeed = Math.floor(Math.random() * 99999);
    setSeed(newSeed);
    setIsGenerating(true);
    setBatchResults(null);
    setTimeout(() => {
      const templatedModules = applySliderWeights(modules);
      const result = doGenerate(newSeed, templatedModules);
      const decorated = applyDecorator(result, newSeed);
      onGenerate(decorated);
      setIsGenerating(false);
    }, 50);
  }, [modules, applySliderWeights, doGenerate, onGenerate, applyDecorator]);

  const handleSelectBatch = useCallback((result) => {
    onGenerate(result);
  }, [onGenerate]);

  /** Re-run the decorator on the existing dungeon layout (no WFC re-run) */
  const handleRedecorate = useCallback(() => {
    if (!lastResult || !lastResult.success || !lastResult.rawTileMap) return;
    const redecorated = applyDecorator(lastResult, seed);
    onGenerate(redecorated);
  }, [lastResult, seed, applyDecorator, onGenerate]);

  return (
    <div className="generator-panel">
      <h3>Generator</h3>

      {/* Dungeon Style — Template quick-buttons + per-category sliders */}
      <div className="gen-section">
        <label>Dungeon Style:</label>
        <div className="template-presets">
          {DUNGEON_TEMPLATES.map((t, i) => (
            <button
              key={t.name}
              className={`template-btn ${i === templateIdx ? 'active' : ''}`}
              onClick={() => applyTemplateToSliders(i)}
              title={t.description}
            >
              <span className="template-icon">{t.icon}</span>
              <span className="template-name">{t.name}</span>
            </button>
          ))}
        </div>
        <div className="template-desc">{template.description}</div>

        {/* Per-category weight sliders */}
        <div className="weight-sliders">
          {['corridor', 'empty', 'enemy', 'boss', 'loot', 'spawn'].map(cat => (
            <div key={cat} className="weight-slider-row">
              <span className="weight-label">{cat}</span>
              <input
                type="range"
                min="0"
                max="5"
                step="0.1"
                value={styleWeights[cat]}
                onChange={(e) => updateWeight(cat, parseFloat(e.target.value))}
                className="weight-range"
              />
              <input
                type="number"
                min="0"
                max="5"
                step="0.1"
                value={styleWeights[cat]}
                onChange={(e) => updateWeight(cat, Math.max(0, Math.min(5, parseFloat(e.target.value) || 0)))}
                className="weight-num"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Dungeon Size — editable fields + preset quick-fills */}
      <div className="gen-section">
        <label>Dungeon Size:</label>
        <div className="size-presets">
          {SIZE_PRESETS.map((p) => (
            <button
              key={p.name}
              className={`size-btn ${gridRows === p.gridRows && gridCols === p.gridCols ? 'active' : ''}`}
              onClick={() => applySizePreset(p)}
              title={p.label}
            >
              {p.name}
            </button>
          ))}
        </div>
        <div className="size-inputs">
          <div className="size-field">
            <span className="size-field-label">Rows</span>
            <input
              type="number"
              min="1"
              max="12"
              value={gridRows}
              onChange={(e) => setGridRows(Math.max(1, Math.min(12, parseInt(e.target.value) || 1)))}
            />
          </div>
          <span className="size-times">×</span>
          <div className="size-field">
            <span className="size-field-label">Cols</span>
            <input
              type="number"
              min="1"
              max="12"
              value={gridCols}
              onChange={(e) => setGridCols(Math.max(1, Math.min(12, parseInt(e.target.value) || 1)))}
            />
          </div>
        </div>
        <div className="size-info">{gridRows}×{gridCols} modules — {tileW}×{tileH} tiles</div>
      </div>

      {/* Seed */}
      <div className="gen-section">
        <label>Seed:</label>
        <div className="seed-row">
          <input
            type="number"
            value={seed}
            onChange={(e) => setSeed(parseInt(e.target.value) || 0)}
          />
          <button onClick={handleRandomSeed} title="Randomize seed">🎲</button>
        </div>
      </div>

      {/* Constraints */}
      <div className="gen-section">
        <label>Constraints:</label>
        <div className="constraint-row">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={forceBorderWalls}
              onChange={(e) => setForceBorderWalls(e.target.checked)}
            />
            Border Walls
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={ensureConnected}
              onChange={(e) => setEnsureConnected(e.target.checked)}
            />
            Ensure Connected
          </label>
        </div>
      </div>

      {/* Max retries */}
      <div className="gen-section">
        <label>Max Retries:</label>
        <input
          type="number"
          min="1"
          max="500"
          value={maxRetries}
          onChange={(e) => setMaxRetries(parseInt(e.target.value) || 50)}
        />
      </div>

      {/* Batch count */}
      <div className="gen-section">
        <label>Batch Generate:</label>
        <div className="seed-row">
          <input
            type="number"
            min="1"
            max="50"
            value={batchCount}
            onChange={(e) => setBatchCount(Math.max(1, Math.min(50, parseInt(e.target.value) || 1)))}
          />
          <span className="batch-hint">{batchCount > 1 ? `Generate ${batchCount}, pick best` : 'Single'}</span>
        </div>
      </div>

      {/* ── Room Decorator ── */}
      <div className="gen-section decorator-section">
        <label>
          <input
            type="checkbox"
            checked={enableDecorator}
            onChange={(e) => setEnableDecorator(e.target.checked)}
          />
          Room Decorator
        </label>
        {enableDecorator && (
          <div className="decorator-controls">
            <div className="decorator-hint">
              Assigns enemies, loot, bosses, and spawns to flexible rooms after generation.
            </div>
            <div className="weight-slider-row">
              <span className="weight-label">Enemies</span>
              <input
                type="range" min="0" max="1" step="0.05"
                value={decoratorSettings.enemyDensity}
                onChange={(e) => updateDecoratorSetting('enemyDensity', parseFloat(e.target.value))}
                className="weight-range"
              />
              <span className="decorator-val">{Math.round(decoratorSettings.enemyDensity * 100)}%</span>
            </div>
            <div className="weight-slider-row">
              <span className="weight-label">Loot</span>
              <input
                type="range" min="0" max="1" step="0.05"
                value={decoratorSettings.lootDensity}
                onChange={(e) => updateDecoratorSetting('lootDensity', parseFloat(e.target.value))}
                className="weight-range"
              />
              <span className="decorator-val">{Math.round(decoratorSettings.lootDensity * 100)}%</span>
            </div>
            <div className="weight-slider-row">
              <span className="weight-label">Empty</span>
              <input
                type="range" min="0" max="1" step="0.05"
                value={decoratorSettings.emptyRoomChance}
                onChange={(e) => updateDecoratorSetting('emptyRoomChance', parseFloat(e.target.value))}
                className="weight-range"
              />
              <span className="decorator-val">{Math.round(decoratorSettings.emptyRoomChance * 100)}%</span>
            </div>
            <div className="constraint-row decorator-toggles">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={decoratorSettings.guaranteeBoss}
                  onChange={(e) => updateDecoratorSetting('guaranteeBoss', e.target.checked)}
                />
                Guarantee Boss
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={decoratorSettings.guaranteeSpawn}
                  onChange={(e) => updateDecoratorSetting('guaranteeSpawn', e.target.checked)}
                />
                Guarantee Spawn
              </label>
            </div>
            <div className="constraint-row decorator-toggles">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={decoratorSettings.scatterEnemies}
                  onChange={(e) => updateDecoratorSetting('scatterEnemies', e.target.checked)}
                />
                Scatter Enemies
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={decoratorSettings.scatterChests}
                  onChange={(e) => updateDecoratorSetting('scatterChests', e.target.checked)}
                />
                Scatter Chests
              </label>
            </div>
          </div>
        )}
      </div>

      {/* Generate buttons */}
      <div className="gen-buttons">
        <button
          className="btn-generate"
          onClick={handleGenerate}
          disabled={isGenerating || modules.length === 0}
        >
          {isGenerating ? 'Generating...' : batchCount > 1 ? `Generate ${batchCount}` : 'Generate'}
        </button>
        <button
          className="btn-quick"
          onClick={handleQuickGenerate}
          disabled={isGenerating || modules.length === 0}
          title="Random seed + generate"
        >
          Quick Random
        </button>
        {lastResult?.success && lastResult.rawTileMap && (
          <button
            className="btn-redecorate"
            onClick={handleRedecorate}
            disabled={isGenerating || !enableDecorator}
            title="Re-run decorator on current dungeon layout with current settings"
          >
            Re-decorate
          </button>
        )}
      </div>

      {/* Result info */}
      {lastResult && (
        <div className="gen-result">
          {lastResult.success ? (
            <div className="result-success">
              <span className="result-icon">✓</span>
              Generated in {lastResult.retries} retries, {lastResult.steps?.length || 0} steps
              {lastResult.connectivity && lastResult.connectivity.regionsFound > 1 && (
                <span className="connectivity-info">
                  {' '}— {lastResult.connectivity.regionsFound} regions found, {lastResult.connectivity.corridorsCarved} corridors carved
                </span>
              )}
              {lastResult.connectivity && lastResult.connectivity.regionsFound <= 1 && (
                <span className="connectivity-info"> — fully connected ✓</span>
              )}
            </div>
          ) : (
            <div className="result-fail">
              <span className="result-icon">✗</span>
              Failed: {lastResult.error}
            </div>
          )}
        </div>
      )}

      {/* Batch results picker */}
      {batchResults && batchResults.length > 1 && (
        <div className="batch-results">
          <h4>Batch Results ({batchResults.length} successful)</h4>
          <div className="batch-list">
            {batchResults.slice(0, 10).map((r, i) => {
              const d = r.difficulty;
              return (
                <button
                  key={i}
                  className="batch-item"
                  onClick={() => handleSelectBatch(r)}
                  title={`Seed: ${r.batchSeed}, Floor: ${r.stats.floorRatio}%, Difficulty: ${difficultyLabel(d)}`}
                >
                  <span className="batch-rank">#{i + 1}</span>
                  <span className="batch-floor">{r.stats.floorRatio}%</span>
                  <span className="batch-diff" style={{ color: difficultyColor(d) }}>{difficultyLabel(d)}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Stats */}
      {stats && (
        <div className="gen-stats">
          <h4>Dungeon Stats</h4>
          <table className="stats-table">
            <tbody>
              <tr><td>Size</td><td>{stats.width}×{stats.height}</td></tr>
              <tr><td>Floor Ratio</td><td>{stats.floorRatio}%</td></tr>
              <tr><td>Walls</td><td>{stats.walls}</td></tr>
              <tr><td>Floors</td><td>{stats.floors}</td></tr>
              <tr><td>Corridors</td><td>{stats.corridors}</td></tr>
              <tr><td>Doors</td><td>{stats.doors}</td></tr>
              <tr><td>Spawns</td><td>{stats.spawns}</td></tr>
              <tr><td>Chests</td><td>{stats.chests}</td></tr>
              <tr><td>Enemy Spawns</td><td>{stats.enemySpawns}</td></tr>
              <tr><td>Boss Spawns</td><td>{stats.bossSpawns}</td></tr>
              <tr>
                <td>Difficulty</td>
                <td style={{ color: difficultyColor(difficulty) }}>
                  {difficulty != null ? `${difficulty}/100 (${difficultyLabel(difficulty)})` : '—'}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {/* Decoration Stats */}
      {lastResult?.decorationStats && (
        <div className="gen-stats decoration-stats">
          <h4>🎭 Decoration</h4>
          <table className="stats-table">
            <tbody>
              <tr><td>Flexible Rooms</td><td>{lastResult.decorationStats.flexibleRooms}</td></tr>
              <tr><td>Fixed Rooms</td><td>{lastResult.decorationStats.fixedRooms}</td></tr>
              <tr>
                <td>Assigned</td>
                <td>
                  {lastResult.decorationStats.roleCount.enemy > 0 && <span className="role-badge role-enemy">{lastResult.decorationStats.roleCount.enemy} enemy</span>}
                  {lastResult.decorationStats.roleCount.loot > 0 && <span className="role-badge role-loot">{lastResult.decorationStats.roleCount.loot} loot</span>}
                  {lastResult.decorationStats.roleCount.boss > 0 && <span className="role-badge role-boss">{lastResult.decorationStats.roleCount.boss} boss</span>}
                  {lastResult.decorationStats.roleCount.spawn > 0 && <span className="role-badge role-spawn">{lastResult.decorationStats.roleCount.spawn} spawn</span>}
                  {lastResult.decorationStats.roleCount.empty > 0 && <span className="role-badge role-empty">{lastResult.decorationStats.roleCount.empty} empty</span>}
                </td>
              </tr>
              <tr><td>Enemies Placed</td><td>{lastResult.decorationStats.enemiesPlaced}</td></tr>
              <tr><td>Chests Placed</td><td>{lastResult.decorationStats.chestsPlaced}</td></tr>
              <tr><td>Bosses Placed</td><td>{lastResult.decorationStats.bossesPlaced}</td></tr>
              <tr><td>Spawns Placed</td><td>{lastResult.decorationStats.spawnsPlaced}</td></tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
