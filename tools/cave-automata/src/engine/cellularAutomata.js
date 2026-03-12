// ─────────────────────────────────────────────────────────
// cellularAutomata.js — Core cellular automata cave generation
//
// Implements the classic B/S rule system for organic cave generation.
// Each cell is either WALL (1) or FLOOR (0). On each step, a cell's
// 8-neighbor count determines its next state via birth/survival thresholds.
// ─────────────────────────────────────────────────────────

import { mulberry32 } from './prng.js';

export const WALL = 1;
export const FLOOR = 0;

/**
 * Initialize a grid with random wall/floor based on fill density.
 *
 * @param {number} width - Grid width
 * @param {number} height - Grid height
 * @param {number} fillPercent - Percentage of cells that start as walls (0–100)
 * @param {function} rng - Seeded PRNG function returning [0,1)
 * @param {boolean} solidBorder - If true, border cells are always walls
 * @returns {number[][]} 2D grid of WALL/FLOOR values
 */
export function initializeGrid(width, height, fillPercent, rng, solidBorder = true) {
  const grid = [];
  for (let y = 0; y < height; y++) {
    const row = [];
    for (let x = 0; x < width; x++) {
      if (solidBorder && (x === 0 || y === 0 || x === width - 1 || y === height - 1)) {
        row.push(WALL);
      } else {
        row.push(rng() * 100 < fillPercent ? WALL : FLOOR);
      }
    }
    grid.push(row);
  }
  return grid;
}

/**
 * Count the number of wall neighbors in a Moore neighborhood (8-connected).
 * Out-of-bounds cells count as walls.
 *
 * @param {number[][]} grid
 * @param {number} x
 * @param {number} y
 * @returns {number} Count of wall neighbors (0–8)
 */
function countWallNeighbors(grid, x, y) {
  const height = grid.length;
  const width = grid[0].length;
  let count = 0;

  for (let dy = -1; dy <= 1; dy++) {
    for (let dx = -1; dx <= 1; dx++) {
      if (dx === 0 && dy === 0) continue;
      const nx = x + dx;
      const ny = y + dy;
      if (nx < 0 || ny < 0 || nx >= width || ny >= height) {
        count++; // Out-of-bounds = wall
      } else if (grid[ny][nx] === WALL) {
        count++;
      }
    }
  }
  return count;
}

/**
 * Run one step of the cellular automata using B/S rules.
 *
 * A dead cell (floor) becomes a wall if neighbors >= birthThreshold.
 * A living cell (wall) survives if neighbors >= survivalThreshold, else becomes floor.
 *
 * @param {number[][]} grid - Current grid state
 * @param {number} birthThreshold - Min neighbors to birth a wall (default 5)
 * @param {number} survivalThreshold - Min neighbors to keep a wall alive (default 4)
 * @param {boolean} solidBorder - Keep borders as walls
 * @returns {number[][]} New grid after one step
 */
export function stepAutomata(grid, birthThreshold = 5, survivalThreshold = 4, solidBorder = true) {
  const height = grid.length;
  const width = grid[0].length;
  const newGrid = [];

  for (let y = 0; y < height; y++) {
    const row = [];
    for (let x = 0; x < width; x++) {
      if (solidBorder && (x === 0 || y === 0 || x === width - 1 || y === height - 1)) {
        row.push(WALL);
      } else {
        const neighbors = countWallNeighbors(grid, x, y);
        if (grid[y][x] === WALL) {
          row.push(neighbors >= survivalThreshold ? WALL : FLOOR);
        } else {
          row.push(neighbors >= birthThreshold ? WALL : FLOOR);
        }
      }
    }
    newGrid.push(row);
  }
  return newGrid;
}

/**
 * Run the full cellular automata generation pipeline.
 *
 * @param {Object} params
 * @param {number} params.width
 * @param {number} params.height
 * @param {number} params.fillPercent - Initial wall fill density (0–100)
 * @param {number} params.birthThreshold - Neighbors needed to birth a wall
 * @param {number} params.survivalThreshold - Neighbors needed for wall survival
 * @param {number} params.iterations - Number of CA steps to run
 * @param {number} params.seed - PRNG seed
 * @param {boolean} [params.solidBorder=true]
 * @returns {{ grid: number[][], seed: number }}
 */
export function generateCave(params) {
  const {
    width,
    height,
    fillPercent,
    birthThreshold,
    survivalThreshold,
    iterations,
    seed,
    solidBorder = true,
  } = params;

  const rng = mulberry32(seed);
  let grid = initializeGrid(width, height, fillPercent, rng, solidBorder);

  for (let i = 0; i < iterations; i++) {
    grid = stepAutomata(grid, birthThreshold, survivalThreshold, solidBorder);
  }

  return { grid, seed };
}
