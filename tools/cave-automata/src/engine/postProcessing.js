// ─────────────────────────────────────────────────────────
// postProcessing.js — Post-generation processing passes
//
// Smoothing: Reduces jagged single-cell protrusions
// Erosion: Widens passages by removing wall cells with few wall neighbors
// Dilation: Thickens walls by adding walls to floor cells near walls
// ─────────────────────────────────────────────────────────

import { WALL, FLOOR } from './cellularAutomata.js';

/**
 * Count wall neighbors in Moore neighborhood (8-connected).
 * Out-of-bounds counts as wall.
 */
function countNeighborWalls(grid, x, y) {
  const height = grid.length;
  const width = grid[0].length;
  let count = 0;
  for (let dy = -1; dy <= 1; dy++) {
    for (let dx = -1; dx <= 1; dx++) {
      if (dx === 0 && dy === 0) continue;
      const nx = x + dx;
      const ny = y + dy;
      if (nx < 0 || ny < 0 || nx >= width || ny >= height) {
        count++;
      } else if (grid[ny][nx] === WALL) {
        count++;
      }
    }
  }
  return count;
}

/**
 * Deep copy a grid.
 */
function cloneGrid(grid) {
  return grid.map(row => [...row]);
}

/**
 * Smoothing pass — removes single-cell wall protrusions and fills single-cell holes.
 * A wall with fewer than 2 wall neighbors becomes floor.
 * A floor with more than 6 wall neighbors becomes wall.
 *
 * @param {number[][]} grid
 * @param {boolean} preserveBorder
 * @returns {number[][]} Smoothed grid
 */
export function smooth(grid, preserveBorder = true) {
  const height = grid.length;
  const width = grid[0].length;
  const result = cloneGrid(grid);

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (preserveBorder && (x === 0 || y === 0 || x === width - 1 || y === height - 1)) continue;
      const walls = countNeighborWalls(grid, x, y);
      if (grid[y][x] === WALL && walls < 2) {
        result[y][x] = FLOOR;
      } else if (grid[y][x] === FLOOR && walls > 6) {
        result[y][x] = WALL;
      }
    }
  }

  return result;
}

/**
 * Erosion pass — widens passages by converting wall cells with few wall neighbors to floor.
 * A wall cell with fewer than `threshold` wall neighbors becomes floor.
 *
 * @param {number[][]} grid
 * @param {number} threshold - Wall neighbor count below which walls erode (default 4)
 * @param {boolean} preserveBorder
 * @returns {number[][]} Eroded grid
 */
export function erode(grid, threshold = 4, preserveBorder = true) {
  const height = grid.length;
  const width = grid[0].length;
  const result = cloneGrid(grid);

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (preserveBorder && (x === 0 || y === 0 || x === width - 1 || y === height - 1)) continue;
      if (grid[y][x] === WALL) {
        const walls = countNeighborWalls(grid, x, y);
        if (walls < threshold) {
          result[y][x] = FLOOR;
        }
      }
    }
  }

  return result;
}

/**
 * Dilation pass — thickens walls by converting floor cells near walls.
 * A floor cell with at least `threshold` wall neighbors becomes wall.
 *
 * @param {number[][]} grid
 * @param {number} threshold - Wall neighbor count above which floors become wall (default 5)
 * @param {boolean} preserveBorder
 * @returns {number[][]} Dilated grid
 */
export function dilate(grid, threshold = 5, preserveBorder = true) {
  const height = grid.length;
  const width = grid[0].length;
  const result = cloneGrid(grid);

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (preserveBorder && (x === 0 || y === 0 || x === width - 1 || y === height - 1)) continue;
      if (grid[y][x] === FLOOR) {
        const walls = countNeighborWalls(grid, x, y);
        if (walls >= threshold) {
          result[y][x] = WALL;
        }
      }
    }
  }

  return result;
}
