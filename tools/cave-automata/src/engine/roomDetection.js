// ─────────────────────────────────────────────────────────
// roomDetection.js — Flood-fill room/cave chamber detection
//
// Scans a CA grid to identify distinct connected regions of floor.
// Each region becomes a "room" (cave chamber) with ID, bounds,
// cell count, and center position.
// ─────────────────────────────────────────────────────────

import { WALL, FLOOR } from './cellularAutomata.js';

/**
 * Detect all connected floor regions in a grid using flood-fill.
 *
 * @param {number[][]} grid - Binary grid (WALL/FLOOR)
 * @returns {Object[]} Array of room objects:
 *   { id, cells: [{x,y}], bounds: {x_min, y_min, x_max, y_max}, size, center: {x,y} }
 */
export function detectRooms(grid) {
  const height = grid.length;
  const width = grid[0]?.length || 0;
  const visited = Array.from({ length: height }, () => new Array(width).fill(false));
  const rooms = [];
  let roomId = 0;

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (grid[y][x] === FLOOR && !visited[y][x]) {
        const cells = floodFill(grid, visited, x, y, width, height);
        if (cells.length > 0) {
          const bounds = computeBounds(cells);
          const center = {
            x: Math.round(cells.reduce((s, c) => s + c.x, 0) / cells.length),
            y: Math.round(cells.reduce((s, c) => s + c.y, 0) / cells.length),
          };
          rooms.push({
            id: roomId++,
            cells,
            bounds,
            size: cells.length,
            center,
          });
        }
      }
    }
  }

  // Sort by size descending (largest chamber first)
  rooms.sort((a, b) => b.size - a.size);

  // Re-assign IDs after sort
  rooms.forEach((room, i) => { room.id = i; });

  return rooms;
}

/**
 * Flood-fill from a starting cell, collecting all connected floor cells.
 * Uses an iterative BFS approach for safety (no recursion stack overflow).
 */
function floodFill(grid, visited, startX, startY, width, height) {
  const cells = [];
  const queue = [{ x: startX, y: startY }];
  visited[startY][startX] = true;

  while (queue.length > 0) {
    const { x, y } = queue.shift();
    cells.push({ x, y });

    // 4-connected neighbors (cardinal directions only for room detection)
    const neighbors = [
      { x: x + 1, y },
      { x: x - 1, y },
      { x, y: y + 1 },
      { x, y: y - 1 },
    ];

    for (const n of neighbors) {
      if (n.x >= 0 && n.x < width && n.y >= 0 && n.y < height &&
          !visited[n.y][n.x] && grid[n.y][n.x] === FLOOR) {
        visited[n.y][n.x] = true;
        queue.push(n);
      }
    }
  }

  return cells;
}

/**
 * Compute the bounding box of a set of cells.
 */
function computeBounds(cells) {
  let x_min = Infinity, y_min = Infinity, x_max = -Infinity, y_max = -Infinity;
  for (const c of cells) {
    x_min = Math.min(x_min, c.x);
    y_min = Math.min(y_min, c.y);
    x_max = Math.max(x_max, c.x);
    y_max = Math.max(y_max, c.y);
  }
  return { x_min, y_min, x_max, y_max };
}

/**
 * Build a room-assignment map: grid[y][x] → room ID (or -1 for walls / unassigned).
 *
 * @param {number[][]} grid - Binary grid
 * @param {Object[]} rooms - Detected rooms from detectRooms()
 * @returns {number[][]} Room assignment grid
 */
export function buildRoomMap(grid, rooms) {
  const height = grid.length;
  const width = grid[0]?.length || 0;
  const map = Array.from({ length: height }, () => new Array(width).fill(-1));

  for (const room of rooms) {
    for (const cell of room.cells) {
      map[cell.y][cell.x] = room.id;
    }
  }

  return map;
}

/**
 * Remove tiny rooms (below minSize) by filling them with walls.
 *
 * @param {number[][]} grid - Binary grid (modified in place)
 * @param {Object[]} rooms - Detected rooms
 * @param {number} minSize - Minimum room size to keep
 * @returns {{ grid: number[][], rooms: Object[], removed: number }}
 */
export function removeSmallRooms(grid, rooms, minSize) {
  let removed = 0;
  const kept = [];

  for (const room of rooms) {
    if (room.size < minSize) {
      // Fill small room with walls
      for (const cell of room.cells) {
        grid[cell.y][cell.x] = WALL;
      }
      removed++;
    } else {
      kept.push(room);
    }
  }

  // Re-index kept rooms
  kept.forEach((r, i) => { r.id = i; });

  return { grid, rooms: kept, removed };
}
