// ─────────────────────────────────────────────────────────
// connectivity.js — Cave connectivity analysis and corridor carving
//
// Ensures all detected cave chambers are reachable by carving
// corridors between disconnected regions. Uses nearest-wall
// tunneling between the closest pair of unconnected rooms.
// ─────────────────────────────────────────────────────────

import { WALL, FLOOR } from './cellularAutomata.js';
import { detectRooms } from './roomDetection.js';

/**
 * Check if the cave is fully connected (only one floor region).
 *
 * @param {number[][]} grid
 * @returns {{ connected: boolean, regionCount: number, rooms: Object[] }}
 */
export function checkConnectivity(grid) {
  const rooms = detectRooms(grid);
  return {
    connected: rooms.length <= 1,
    regionCount: rooms.length,
    rooms,
  };
}

/**
 * Ensure all cave regions are connected by carving corridors.
 * Iteratively connects the closest pair of unconnected rooms
 * until only one floor region remains.
 *
 * @param {number[][]} grid - Binary grid (modified in place)
 * @param {number} [corridorWidth=1] - Width of carved corridors (1, 2, or 3)
 * @returns {{ grid: number[][], corridorsCarved: number }}
 */
export function ensureConnectivity(grid, corridorWidth = 1) {
  let corridorsCarved = 0;
  let maxIterations = 100; // Safety limit

  while (maxIterations-- > 0) {
    const rooms = detectRooms(grid);
    if (rooms.length <= 1) break;

    // Find the two closest rooms by comparing cell edges
    const { roomA, roomB, cellA, cellB } = findClosestRoomPair(rooms);
    if (!cellA || !cellB) break;

    // Carve a corridor between them
    carveCorridor(grid, cellA, cellB, corridorWidth);
    corridorsCarved++;
  }

  return { grid, corridorsCarved };
}

/**
 * Find the closest pair of cells between two different rooms.
 * Returns the two rooms and the two cells that are closest.
 */
function findClosestRoomPair(rooms) {
  let bestDist = Infinity;
  let roomA = null, roomB = null;
  let cellA = null, cellB = null;

  // Compare room 0 (the largest) with all others
  // This ensures we always connect to the main cave
  const main = rooms[0];

  for (let i = 1; i < rooms.length; i++) {
    const other = rooms[i];
    const { dist, a, b } = closestCellsBetweenRooms(main, other);
    if (dist < bestDist) {
      bestDist = dist;
      roomA = main;
      roomB = other;
      cellA = a;
      cellB = b;
    }
  }

  return { roomA, roomB, cellA, cellB };
}

/**
 * Find the closest pair of cells between two rooms.
 * Uses a sampling approach for large rooms to avoid O(n*m) blowup.
 */
function closestCellsBetweenRooms(roomA, roomB) {
  let bestDist = Infinity;
  let bestA = null, bestB = null;

  // Sample cells for large rooms (every nth cell)
  const sampleA = sampleCells(roomA.cells, 50);
  const sampleB = sampleCells(roomB.cells, 50);

  for (const a of sampleA) {
    for (const b of sampleB) {
      const dist = Math.abs(a.x - b.x) + Math.abs(a.y - b.y); // Manhattan distance
      if (dist < bestDist) {
        bestDist = dist;
        bestA = a;
        bestB = b;
      }
    }
  }

  return { dist: bestDist, a: bestA, b: bestB };
}

/**
 * Sample up to maxSamples cells from a cell array, evenly spaced.
 */
function sampleCells(cells, maxSamples) {
  if (cells.length <= maxSamples) return cells;
  const step = Math.floor(cells.length / maxSamples);
  const sampled = [];
  for (let i = 0; i < cells.length; i += step) {
    sampled.push(cells[i]);
  }
  return sampled;
}

/**
 * Carve a corridor between two points using L-shaped pathways.
 * Randomly chooses horizontal-first or vertical-first.
 *
 * @param {number[][]} grid - Binary grid (modified in place)
 * @param {{ x: number, y: number }} from
 * @param {{ x: number, y: number }} to
 * @param {number} width - Corridor width (1-3)
 */
function carveCorridor(grid, from, to, width) {
  const height = grid.length;
  const gridWidth = grid[0].length;

  // Carve horizontal then vertical
  let x = from.x;
  let y = from.y;

  // Horizontal segment
  const dx = to.x > x ? 1 : -1;
  while (x !== to.x) {
    carveCell(grid, x, y, width, gridWidth, height);
    x += dx;
  }

  // Vertical segment
  const dy = to.y > y ? 1 : -1;
  while (y !== to.y) {
    carveCell(grid, x, y, width, gridWidth, height);
    y += dy;
  }

  // Carve the final cell
  carveCell(grid, x, y, width, gridWidth, height);
}

/**
 * Carve a cell and surrounding cells based on corridor width.
 */
function carveCell(grid, cx, cy, width, gridWidth, gridHeight) {
  const radius = Math.floor(width / 2);
  for (let dy = -radius; dy <= radius; dy++) {
    for (let dx = -radius; dx <= radius; dx++) {
      const nx = cx + dx;
      const ny = cy + dy;
      // Don't carve border cells
      if (nx > 0 && ny > 0 && nx < gridWidth - 1 && ny < gridHeight - 1) {
        grid[ny][nx] = FLOOR;
      }
    }
  }
}
