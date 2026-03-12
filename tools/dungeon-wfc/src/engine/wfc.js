// ─────────────────────────────────────────────────────────
// wfc.js — Wave Function Collapse engine
//
// Module-level WFC: each cell in a grid holds one module.
// Sockets on adjacent edges must match for modules to be neighbors.
// Uses entropy-based collapse with weighted random selection.
// ─────────────────────────────────────────────────────────

import { expandModules, MODULE_SIZE } from './moduleUtils.js';
import { ensureConnectivity, validateConnectivity } from './connectivity.js';

// Re-export connectivity for convenience
export { validateConnectivity } from './connectivity.js';

/**
 * Seeded pseudo-random number generator (mulberry32).
 * Deterministic results for a given seed.
 */
function createRNG(seed) {
  let s = seed | 0;
  return function () {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Opposite direction map for socket matching */
const OPPOSITE = {
  north: 'south',
  south: 'north',
  east: 'west',
  west: 'east',
};

/** Direction → neighbor offset */
const OFFSETS = {
  north: { dr: -1, dc: 0 },
  south: { dr: 1, dc: 0 },
  east: { dr: 0, dc: 1 },
  west: { dr: 0, dc: -1 },
};

/**
 * Run WFC generation.
 *
 * @param {Object} params
 * @param {Array} params.modules - Raw module library (before expansion)
 * @param {number} params.gridRows - Number of module cells vertically
 * @param {number} params.gridCols - Number of module cells horizontally
 * @param {number} params.seed - RNG seed
 * @param {Object} params.pinned - Map of "row,col" → module variant index to pin
 * @param {number} params.maxRetries - Max restart attempts on contradiction
 * @param {boolean} params.forceBorderWalls - Force wall sockets on map edges
 * @param {boolean} params.ensureConnected - Carve corridors to connect isolated regions
 * @returns {{ success: boolean, grid: Array, tileMap: Array, steps: Array, retries: number, connectivity: Object }}
 */
export function runWFC({ modules, gridRows, gridCols, seed, pinned = {}, maxRetries = 50, forceBorderWalls = true, ensureConnected = true }) {
  const variants = expandModules(modules);

  if (variants.length === 0) {
    return { success: false, grid: null, tileMap: null, steps: [], retries: 0, error: 'No modules in library' };
  }

  // Precompute adjacency compatibility table
  // compatible[dir][variantIndex] = Set of variant indices that can be placed in that direction
  const compatible = {};
  for (const dir of ['north', 'south', 'east', 'west']) {
    compatible[dir] = [];
    const opp = OPPOSITE[dir];
    for (let i = 0; i < variants.length; i++) {
      const mySocket = variants[i].sockets[dir];
      const compat = new Set();
      for (let j = 0; j < variants.length; j++) {
        if (variants[j].sockets[opp] === mySocket) {
          compat.add(j);
        }
      }
      compatible[dir][i] = compat;
    }
  }

  // Precompute border-compatible variant sets (variants with all-wall sockets on a given side)
  const wallSocket = 'W'.repeat(MODULE_SIZE);
  const borderVariants = {};
  for (const dir of ['north', 'south', 'east', 'west']) {
    borderVariants[dir] = new Set();
    for (let i = 0; i < variants.length; i++) {
      if (variants[i].sockets[dir] === wallSocket) {
        borderVariants[dir].add(i);
      }
    }
  }

  let retries = 0;

  while (retries <= maxRetries) {
    const rng = createRNG(seed + retries);
    const result = attemptWFC(variants, compatible, gridRows, gridCols, rng, pinned, forceBorderWalls, borderVariants);

    if (result.success) {
      const tileMap = assembleToTileMap(result.grid, variants, gridRows, gridCols);

      // Connectivity enforcement
      let connectivity = null;
      if (ensureConnected) {
        connectivity = ensureConnectivity(tileMap);
      } else {
        const validation = validateConnectivity(tileMap);
        connectivity = {
          connected: validation.isConnected,
          regionsFound: validation.regionCount,
          corridorsCarved: 0,
          regionSizes: validation.regionSizes,
        };
      }

      return {
        success: true,
        grid: result.grid,
        tileMap,
        steps: result.steps,
        retries,
        variants,
        connectivity,
      };
    }

    retries++;
  }

  return { success: false, grid: null, tileMap: null, steps: [], retries, error: 'Max retries exceeded — contradiction' };
}

/**
 * Single WFC attempt. Returns { success, grid, steps } or { success: false }.
 */
function attemptWFC(variants, compatible, rows, cols, rng, pinned, forceBorderWalls, borderVariants) {
  const numVariants = variants.length;

  // Initialize grid: each cell has a Set of possible variant indices
  const grid = [];
  for (let r = 0; r < rows; r++) {
    const row = [];
    for (let c = 0; c < cols; c++) {
      row.push({
        possible: new Set(Array.from({ length: numVariants }, (_, i) => i)),
        collapsed: false,
        chosenVariant: null,
      });
    }
    grid.push(row);
  }

  // Apply border wall constraints — restrict edge cells to modules with wall sockets on their outward-facing edges
  if (forceBorderWalls && borderVariants) {
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const cell = grid[r][c];
        if (r === 0) {
          // Top edge: must have wall socket on north
          cell.possible = new Set([...cell.possible].filter(v => borderVariants.north.has(v)));
        }
        if (r === rows - 1) {
          // Bottom edge: must have wall socket on south
          cell.possible = new Set([...cell.possible].filter(v => borderVariants.south.has(v)));
        }
        if (c === 0) {
          // Left edge: must have wall socket on west
          cell.possible = new Set([...cell.possible].filter(v => borderVariants.west.has(v)));
        }
        if (c === cols - 1) {
          // Right edge: must have wall socket on east
          cell.possible = new Set([...cell.possible].filter(v => borderVariants.east.has(v)));
        }
        if (cell.possible.size === 0) {
          return { success: false }; // Cannot satisfy border constraints
        }
      }
    }
  }

  // Apply pinned constraints
  for (const [key, variantIdx] of Object.entries(pinned)) {
    const [r, c] = key.split(',').map(Number);
    if (r >= 0 && r < rows && c >= 0 && c < cols && variantIdx >= 0 && variantIdx < numVariants) {
      grid[r][c].possible = new Set([variantIdx]);
    }
  }

  // Initial constraint propagation from pinned cells
  for (const key of Object.keys(pinned)) {
    const [r, c] = key.split(',').map(Number);
    if (!propagate(grid, r, c, compatible, rows, cols, variants)) {
      return { success: false };
    }
  }

  const steps = [];
  const totalCells = rows * cols;
  let collapsedCount = 0;

  // Count already-collapsed cells (single possibility from pinning)
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (grid[r][c].possible.size === 1 && !grid[r][c].collapsed) {
        grid[r][c].collapsed = true;
        grid[r][c].chosenVariant = [...grid[r][c].possible][0];
        collapsedCount++;
      }
    }
  }

  while (collapsedCount < totalCells) {
    // Find cell with minimum entropy (fewest possibilities, > 1)
    let minEntropy = Infinity;
    let candidates = [];

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const cell = grid[r][c];
        if (cell.collapsed) continue;
        const entropy = cell.possible.size;
        if (entropy === 0) {
          // Contradiction
          return { success: false };
        }
        if (entropy < minEntropy) {
          minEntropy = entropy;
          candidates = [{ r, c }];
        } else if (entropy === minEntropy) {
          candidates.push({ r, c });
        }
      }
    }

    if (candidates.length === 0) break;

    // Pick random cell among minimum-entropy candidates
    const chosen = candidates[Math.floor(rng() * candidates.length)];
    const cell = grid[chosen.r][chosen.c];

    // Weighted collapse
    const variantIdx = weightedPick([...cell.possible], variants, rng);
    cell.possible = new Set([variantIdx]);
    cell.collapsed = true;
    cell.chosenVariant = variantIdx;
    collapsedCount++;

    steps.push({
      row: chosen.r,
      col: chosen.c,
      variantIdx,
      name: variants[variantIdx].sourceName,
      rotation: variants[variantIdx].rotation,
    });

    // Propagate constraints
    if (!propagate(grid, chosen.r, chosen.c, compatible, rows, cols, variants)) {
      return { success: false };
    }

    // Check for newly-determined cells
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (!grid[r][c].collapsed && grid[r][c].possible.size === 1) {
          grid[r][c].collapsed = true;
          grid[r][c].chosenVariant = [...grid[r][c].possible][0];
          collapsedCount++;
        }
      }
    }
  }

  return { success: true, grid, steps };
}

/**
 * Weighted random pick from a set of variant indices.
 */
function weightedPick(indices, variants, rng) {
  let totalWeight = 0;
  for (const idx of indices) {
    totalWeight += variants[idx].weight;
  }
  let r = rng() * totalWeight;
  for (const idx of indices) {
    r -= variants[idx].weight;
    if (r <= 0) return idx;
  }
  return indices[indices.length - 1];
}

/**
 * Propagate constraints from a collapsed/changed cell outward (BFS).
 * Returns false if a contradiction is found.
 */
function propagate(grid, startR, startC, compatible, rows, cols, variants) {
  const queue = [{ r: startR, c: startC }];
  const visited = new Set();
  visited.add(`${startR},${startC}`);

  while (queue.length > 0) {
    const { r, c } = queue.shift();
    const cell = grid[r][c];

    for (const [dir, { dr, dc }] of Object.entries(OFFSETS)) {
      const nr = r + dr;
      const nc = c + dc;
      if (nr < 0 || nr >= rows || nc < 0 || nc >= cols) continue;

      const neighbor = grid[nr][nc];
      if (neighbor.collapsed) continue;

      // Compute the set of variants allowed in the neighbor based on this cell
      const allowedInNeighbor = new Set();
      for (const myVar of cell.possible) {
        const compatSet = compatible[dir][myVar];
        for (const nVar of compatSet) {
          allowedInNeighbor.add(nVar);
        }
      }

      // Intersect with neighbor's current possibilities
      const before = neighbor.possible.size;
      const newPossible = new Set();
      for (const p of neighbor.possible) {
        if (allowedInNeighbor.has(p)) {
          newPossible.add(p);
        }
      }
      neighbor.possible = newPossible;

      if (newPossible.size === 0) {
        return false; // Contradiction
      }

      // If possibilities were reduced, propagate from this neighbor too
      if (newPossible.size < before) {
        const key = `${nr},${nc}`;
        if (!visited.has(key)) {
          visited.add(key);
          queue.push({ r: nr, c: nc });
        }
      }
    }
  }

  return true;
}

/**
 * Assemble the collapsed WFC grid into a full tile map.
 * Each module occupies MODULE_SIZE x MODULE_SIZE tiles.
 */
function assembleToTileMap(grid, variants, gridRows, gridCols) {
  const tileH = gridRows * MODULE_SIZE;
  const tileW = gridCols * MODULE_SIZE;
  const tileMap = [];

  for (let r = 0; r < tileH; r++) {
    tileMap.push(new Array(tileW).fill('W'));
  }

  for (let gr = 0; gr < gridRows; gr++) {
    for (let gc = 0; gc < gridCols; gc++) {
      const cell = grid[gr][gc];
      if (cell.chosenVariant == null) continue;

      const variant = variants[cell.chosenVariant];
      const startR = gr * MODULE_SIZE;
      const startC = gc * MODULE_SIZE;

      for (let lr = 0; lr < MODULE_SIZE; lr++) {
        for (let lc = 0; lc < MODULE_SIZE; lc++) {
          tileMap[startR + lr][startC + lc] = variant.tiles[lr][lc];
        }
      }
    }
  }

  return tileMap;
}

/**
 * Compute dungeon statistics from a tile map.
 */
export function computeStats(tileMap) {
  if (!tileMap) return null;

  const stats = {
    width: tileMap[0]?.length || 0,
    height: tileMap.length,
    totalTiles: 0,
    walls: 0,
    floors: 0,
    doors: 0,
    corridors: 0,
    spawns: 0,
    chests: 0,
    enemySpawns: 0,
    bossSpawns: 0,
    floorRatio: 0,
  };

  for (const row of tileMap) {
    for (const tile of row) {
      stats.totalTiles++;
      switch (tile) {
        case 'W': stats.walls++; break;
        case 'F': stats.floors++; break;
        case 'D': stats.doors++; break;
        case 'C': stats.corridors++; break;
        case 'S': stats.spawns++; break;
        case 'X': stats.chests++; break;
        case 'E': stats.enemySpawns++; break;
        case 'B': stats.bossSpawns++; break;
      }
    }
  }

  const openTiles = stats.floors + stats.doors + stats.corridors + stats.spawns + stats.chests + stats.enemySpawns + stats.bossSpawns;
  stats.floorRatio = stats.totalTiles > 0 ? (openTiles / stats.totalTiles * 100).toFixed(1) : 0;

  return stats;
}
