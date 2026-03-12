// ─────────────────────────────────────────────────────────
// connectivity.js — Dungeon connectivity validation & corridor stitching
//
// After WFC generation, ensures all walkable regions are connected.
// Uses flood-fill to detect isolated regions, then carves minimal
// corridors between them using A* pathfinding through walls.
// ─────────────────────────────────────────────────────────

import { OPEN_TILES } from '../utils/tileColors.js';

/**
 * Check if a tile is walkable (open).
 */
function isOpen(tile) {
  return OPEN_TILES.has(tile);
}

/**
 * Flood-fill from a starting position, returning all connected open tile coords.
 * @param {string[][]} tileMap - 2D tile array
 * @param {number} startR - start row
 * @param {number} startC - start column
 * @param {Set<string>} visited - already-visited coords set ("r,c" strings)
 * @returns {Array<{r: number, c: number}>} all tiles in this connected region
 */
function floodFill(tileMap, startR, startC, visited) {
  const height = tileMap.length;
  const width = tileMap[0].length;
  const region = [];
  const queue = [{ r: startR, c: startC }];
  const key = `${startR},${startC}`;
  visited.add(key);

  while (queue.length > 0) {
    const { r, c } = queue.shift();
    region.push({ r, c });

    const neighbors = [
      { r: r - 1, c },
      { r: r + 1, c },
      { r, c: c - 1 },
      { r, c: c + 1 },
    ];

    for (const n of neighbors) {
      if (n.r < 0 || n.r >= height || n.c < 0 || n.c >= width) continue;
      const nKey = `${n.r},${n.c}`;
      if (visited.has(nKey)) continue;
      if (!isOpen(tileMap[n.r][n.c])) continue;
      visited.add(nKey);
      queue.push(n);
    }
  }

  return region;
}

/**
 * Find all disconnected regions in the tile map.
 * @param {string[][]} tileMap
 * @returns {Array<Array<{r: number, c: number}>>} array of regions (each is array of coords)
 */
export function findRegions(tileMap) {
  const height = tileMap.length;
  const width = tileMap[0]?.length || 0;
  const visited = new Set();
  const regions = [];

  for (let r = 0; r < height; r++) {
    for (let c = 0; c < width; c++) {
      if (!isOpen(tileMap[r][c])) continue;
      const key = `${r},${c}`;
      if (visited.has(key)) continue;
      const region = floodFill(tileMap, r, c, visited);
      if (region.length > 0) {
        regions.push(region);
      }
    }
  }

  return regions;
}

/**
 * A* pathfinding through walls to find the shortest tunnel between two points.
 * Cost: 1 for open tiles, 3 for wall tiles (prefer going through open space).
 */
function findTunnelPath(tileMap, from, to) {
  const height = tileMap.length;
  const width = tileMap[0].length;

  const openSet = new Map(); // key → { r, c, g, f, parent }
  const closedSet = new Set();

  const startKey = `${from.r},${from.c}`;
  const endKey = `${to.r},${to.c}`;

  const heuristic = (r, c) => Math.abs(r - to.r) + Math.abs(c - to.c);

  openSet.set(startKey, {
    r: from.r,
    c: from.c,
    g: 0,
    f: heuristic(from.r, from.c),
    parent: null,
  });

  while (openSet.size > 0) {
    // Find node with lowest f score
    let bestKey = null;
    let bestF = Infinity;
    for (const [key, node] of openSet) {
      if (node.f < bestF) {
        bestF = node.f;
        bestKey = key;
      }
    }

    const current = openSet.get(bestKey);
    openSet.delete(bestKey);
    closedSet.add(bestKey);

    if (bestKey === endKey) {
      // Reconstruct path
      const path = [];
      let node = current;
      while (node) {
        path.unshift({ r: node.r, c: node.c });
        node = node.parent;
      }
      return path;
    }

    const neighbors = [
      { r: current.r - 1, c: current.c },
      { r: current.r + 1, c: current.c },
      { r: current.r, c: current.c - 1 },
      { r: current.r, c: current.c + 1 },
    ];

    for (const n of neighbors) {
      if (n.r < 0 || n.r >= height || n.c < 0 || n.c >= width) continue;
      const nKey = `${n.r},${n.c}`;
      if (closedSet.has(nKey)) continue;

      // Wall tiles cost more to tunnel through
      const moveCost = isOpen(tileMap[n.r][n.c]) ? 1 : 3;
      const tentativeG = current.g + moveCost;

      const existing = openSet.get(nKey);
      if (existing && tentativeG >= existing.g) continue;

      openSet.set(nKey, {
        r: n.r,
        c: n.c,
        g: tentativeG,
        f: tentativeG + heuristic(n.r, n.c),
        parent: current,
      });
    }
  }

  return null; // No path found (shouldn't happen on a valid grid)
}

/**
 * Find the closest pair of tiles between two regions.
 * @returns {{ from: {r,c}, to: {r,c}, distance: number }}
 */
function findClosestPair(regionA, regionB) {
  let best = null;
  let bestDist = Infinity;

  // Sample for performance: if regions are large, sample random subset
  const sampleA = regionA.length > 100 ? sampleArray(regionA, 100) : regionA;
  const sampleB = regionB.length > 100 ? sampleArray(regionB, 100) : regionB;

  for (const a of sampleA) {
    for (const b of sampleB) {
      const dist = Math.abs(a.r - b.r) + Math.abs(a.c - b.c);
      if (dist < bestDist) {
        bestDist = dist;
        best = { from: a, to: b, distance: dist };
      }
    }
  }

  return best;
}

function sampleArray(arr, n) {
  const result = [];
  const step = Math.max(1, Math.floor(arr.length / n));
  for (let i = 0; i < arr.length && result.length < n; i += step) {
    result.push(arr[i]);
  }
  return result;
}

/**
 * Carve a 2-wide corridor along a path by setting wall tiles to corridor.
 * Tries to carve 2-wide to match the standard corridor width.
 */
function carveCorridor(tileMap, path) {
  const height = tileMap.length;
  const width = tileMap[0].length;

  for (const { r, c } of path) {
    // Only carve walls (don't overwrite existing content)
    if (tileMap[r][c] === 'W') {
      tileMap[r][c] = 'C';
    }
    // Try to make it 2-wide (expand horizontally or vertically based on direction)
    // Check which neighbor is best for widening
    const wideNeighbors = [
      { r: r, c: c + 1 },
      { r: r + 1, c: c },
    ];
    for (const n of wideNeighbors) {
      if (n.r >= 0 && n.r < height && n.c >= 0 && n.c < width) {
        if (tileMap[n.r][n.c] === 'W') {
          tileMap[n.r][n.c] = 'C';
          break; // Only widen by 1
        }
      }
    }
  }
}

/**
 * Ensure the dungeon is fully connected.
 * Detects disconnected regions and carves corridors between them.
 *
 * @param {string[][]} tileMap - Mutable 2D tile array (will be modified in place)
 * @returns {{ connected: boolean, regionsFound: number, corridorsCarved: number, tileMap: string[][] }}
 */
export function ensureConnectivity(tileMap) {
  const regions = findRegions(tileMap);

  if (regions.length <= 1) {
    return {
      connected: true,
      regionsFound: regions.length,
      corridorsCarved: 0,
      tileMap,
    };
  }

  // Sort regions by size (largest first) — main region is the biggest
  regions.sort((a, b) => b.length - a.length);

  let corridorsCarved = 0;

  // Connect each smaller region to the main region
  // Use union approach: merge regions as we connect them
  let mainRegion = regions[0];

  for (let i = 1; i < regions.length; i++) {
    const smallRegion = regions[i];

    // Skip tiny regions (1-2 tiles, likely artifacts)
    if (smallRegion.length < 2) continue;

    const pair = findClosestPair(mainRegion, smallRegion);
    if (!pair) continue;

    const path = findTunnelPath(tileMap, pair.from, pair.to);
    if (path) {
      carveCorridor(tileMap, path);
      corridorsCarved++;
      // Merge the small region into main
      mainRegion = [...mainRegion, ...smallRegion];
    }
  }

  return {
    connected: true,
    regionsFound: regions.length,
    corridorsCarved,
    tileMap,
  };
}

/**
 * Validate connectivity without modifying the tile map.
 * @param {string[][]} tileMap
 * @returns {{ isConnected: boolean, regionCount: number, regionSizes: number[] }}
 */
export function validateConnectivity(tileMap) {
  const regions = findRegions(tileMap);
  return {
    isConnected: regions.length <= 1,
    regionCount: regions.length,
    regionSizes: regions.map(r => r.length).sort((a, b) => b - a),
  };
}
