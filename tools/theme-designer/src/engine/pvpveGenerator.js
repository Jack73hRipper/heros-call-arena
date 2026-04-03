// ─────────────────────────────────────────────────────────
// pvpveGenerator.js — PVPVE Dungeon Generator Orchestrator
//
// Single entry point that runs the full pipeline:
//   1. Load preset modules
//   2. Run WFC collapse
//   3. Base room decoration
//   4. PVPVE overlay (corner spawns, center boss, doors)
//   5. Return unified result for PvpvePreview component
//
// Consumes:
//   @wfc/wfc.js          → runWFC(), computeStats()
//   @wfc/presets.js       → PRESET_MODULES
//   @wfc/roomDecorator.js → decorateRooms()
//   ./pvpveDecorator.js   → applyPvpveLayout()
// ─────────────────────────────────────────────────────────

import { runWFC, computeStats } from '@wfc/wfc.js';
import { PRESET_MODULES } from '@wfc/presets.js';
import { decorateRooms } from '@wfc/roomDecorator.js';
import { applyPvpveLayout } from './pvpveDecorator.js';

// ─── Defaults ────────────────────────────────────────────

const DEFAULT_GRID_ROWS = 8;
const DEFAULT_GRID_COLS = 8;
const DEFAULT_TEAM_COUNT = 4;
const DEFAULT_SEED = 42;
const BATCH_SIZE = 5; // Best-of-N: generate N candidates, pick the best (matches server)

/** PVPVE-tuned decorator settings (higher density than standard PvE) */
const PVPVE_DECORATOR_SETTINGS = {
  enemyDensity: 0.50,
  lootDensity: 0.15,
  emptyRoomChance: 0.15,
  guaranteeBoss: true,
  guaranteeSpawn: true,
  guaranteeStairs: false,
  scatterEnemies: true,
  scatterChests: true,
};

// ─── Public API ──────────────────────────────────────────

/**
 * Generate a complete PVPVE dungeon for preview.
 *
 * @param {Object} opts
 * @param {number} [opts.seed=42]       - RNG seed
 * @param {number} [opts.gridRows=8]    - Module grid rows
 * @param {number} [opts.gridCols=8]    - Module grid cols
 * @param {number} [opts.teamCount=4]   - Number of player teams (2-4)
 * @returns {PvpveResult}
 */
export function generatePvpveDungeon({
  seed = DEFAULT_SEED,
  gridRows = DEFAULT_GRID_ROWS,
  gridCols = DEFAULT_GRID_COLS,
  teamCount = DEFAULT_TEAM_COUNT,
} = {}) {
  // ── Validate inputs ──
  const clampedRows = Math.max(3, Math.min(8, gridRows));
  const clampedCols = Math.max(3, Math.min(8, gridCols));
  const clampedTeams = Math.max(2, Math.min(4, teamCount));
  const safeSeed = Math.max(0, Math.min(999999, Math.floor(seed)));

  // ── Step 1: Run WFC (best-of-N candidate selection, matches server) ──
  const candidates = [];
  for (let i = 0; i < BATCH_SIZE; i++) {
    const candidateSeed = (safeSeed + i * 7919) % 1000000; // Offset seeds like server
    const result = runWFC({
      modules: PRESET_MODULES,
      gridRows: clampedRows,
      gridCols: clampedCols,
      seed: candidateSeed,
      forceBorderWalls: true,
      ensureConnected: true,
    });
    if (result.success) {
      const stats = computeStats(result.tileMap);
      const floorRatio = parseFloat(stats.floorRatio) || 0;
      // Score: floor ratio + bonus for natural connectivity (no corridors carved)
      let score = floorRatio;
      if (stats.spawns > 0) score += 20.0;
      const corridorsCarved = result.connectivity?.corridorsCarved ?? 0;
      if (corridorsCarved === 0) score += 10.0;
      candidates.push({ ...result, score, candidateSeed });
    }
  }

  if (candidates.length === 0) {
    return {
      success: false,
      tileMap: null,
      rooms: [],
      doors: [],
      spawnZones: {},
      bossRoom: null,
      difficultyTiers: new Map(),
      stats: {},
      gridRows: clampedRows,
      gridCols: clampedCols,
      error: `WFC failed: all ${BATCH_SIZE} batch candidates failed`,
    };
  }

  // Pick the best candidate by score (higher = better)
  candidates.sort((a, b) => b.score - a.score);
  const wfcResult = candidates[0];

  const { grid, tileMap, variants } = wfcResult;

  // ── Step 2: Base room decoration ──
  const decorResult = decorateRooms({
    grid,
    variants,
    tileMap,
    seed: safeSeed,
    settings: PVPVE_DECORATOR_SETTINGS,
  });

  // ── Step 3: PVPVE overlay ──
  const pvpveResult = applyPvpveLayout({
    tileMap: decorResult.tileMap,
    grid,
    variants,
    seed: safeSeed,
    teamCount: clampedTeams,
    gridRows: clampedRows,
    gridCols: clampedCols,
  });

  // ── Step 4: Compute final tile stats ──
  const tileStats = computeStats(pvpveResult.tileMap);

  // ── Step 5: Merge stats and return ──
  return {
    success: true,
    tileMap: pvpveResult.tileMap,
    rooms: pvpveResult.rooms,
    doors: pvpveResult.doors,
    spawnZones: pvpveResult.spawnZones,
    bossRoom: pvpveResult.bossRoom,
    difficultyTiers: pvpveResult.difficultyTiers,
    stats: {
      ...pvpveResult.stats,
      ...tileStats,
      wfcRetries: wfcResult.retries,
      wfcConnectivity: wfcResult.connectivity,
      batchSize: BATCH_SIZE,
      batchCandidates: candidates.length,
      batchBestScore: wfcResult.score,
    },
    gridRows: clampedRows,
    gridCols: clampedCols,
  };
}

// ─── Grid Size Presets ───────────────────────────────────

/** Available grid size options for the toolbar dropdown */
export const GRID_SIZE_PRESETS = [
  { label: '3×3', rows: 3, cols: 3 },
  { label: '4×4', rows: 4, cols: 4 },
  { label: '5×5', rows: 5, cols: 5 },
  { label: '6×6', rows: 6, cols: 6 },
  { label: '8×8', rows: 8, cols: 8 },
];

/** Available team count options */
export const TEAM_COUNT_OPTIONS = [2, 3, 4];
