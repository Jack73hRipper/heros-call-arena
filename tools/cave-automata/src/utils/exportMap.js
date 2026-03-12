// ─────────────────────────────────────────────────────────
// exportMap.js — Convert cave grid to Arena game map JSON
//
// Matches the JSON format used by server/configs/maps/
// (dungeon_test.json, wfc_dungeon.json, etc.)
// ─────────────────────────────────────────────────────────

import { WALL } from '../engine/cellularAutomata.js';

/**
 * Convert a cave tile map (2D array of tile characters) + metadata
 * into a game-compatible map JSON for the Arena server.
 *
 * @param {string[][]} tileMap - 2D array of tile characters ('W','F','S','E', etc.)
 * @param {Object[]} rooms - Detected rooms with purpose assignments
 * @param {string} mapName - Name for the exported map
 * @returns {Object} Game-compatible map JSON
 */
export function exportToGameJSON(tileMap, rooms = [], mapName = 'Cave Generated Map') {
  const height = tileMap.length;
  const width = tileMap[0]?.length || 0;

  // Normalize tiles for export (E → F, B → F; enemies go in rooms[].enemy_spawns)
  const tiles = tileMap.map(row =>
    row.map(t => normalizeForExport(t))
  );

  // Collect spawn points from 'S' tiles
  const spawnPoints = [];
  const spawnBounds = { x_min: Infinity, y_min: Infinity, x_max: -Infinity, y_max: -Infinity };

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (tileMap[y][x] === 'S') {
        spawnPoints.push({ x, y });
        spawnBounds.x_min = Math.min(spawnBounds.x_min, x);
        spawnBounds.y_min = Math.min(spawnBounds.y_min, y);
        spawnBounds.x_max = Math.max(spawnBounds.x_max, x);
        spawnBounds.y_max = Math.max(spawnBounds.y_max, y);
      }
    }
  }

  // Fallback: if no spawn points, use first floor tiles
  if (spawnPoints.length === 0) {
    for (let y = 0; y < height && spawnPoints.length < 5; y++) {
      for (let x = 0; x < width && spawnPoints.length < 5; x++) {
        if (tileMap[y][x] === 'F' || tileMap[y][x] === 'C') {
          spawnPoints.push({ x, y });
          spawnBounds.x_min = Math.min(spawnBounds.x_min, x);
          spawnBounds.y_min = Math.min(spawnBounds.y_min, y);
          spawnBounds.x_max = Math.max(spawnBounds.x_max, x);
          spawnBounds.y_max = Math.max(spawnBounds.y_max, y);
        }
      }
    }
  }

  // Collect doors
  const doors = [];
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (tileMap[y][x] === 'D') {
        doors.push({ x, y, state: 'closed' });
      }
    }
  }

  // Collect chests
  const chests = [];
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (tileMap[y][x] === 'X') {
        chests.push({ x, y });
      }
    }
  }

  // Build exported rooms from detected rooms with purpose assignments
  const exportedRooms = rooms.map((room, i) => {
    const exportRoom = {
      id: `cave_${i}`,
      name: room.name || `Cave Chamber ${i + 1}`,
      purpose: room.purpose || 'empty',
      bounds: room.bounds,
    };

    // Scan for enemy/boss markers in this room's bounds
    const enemySpawns = [];
    for (let y = room.bounds.y_min; y <= room.bounds.y_max; y++) {
      for (let x = room.bounds.x_min; x <= room.bounds.x_max; x++) {
        if (x >= 0 && x < width && y >= 0 && y < height) {
          if (tileMap[y][x] === 'E') {
            enemySpawns.push({ x, y, enemy_type: 'demon' });
          } else if (tileMap[y][x] === 'B') {
            enemySpawns.push({ x, y, enemy_type: 'undead_knight', is_boss: true });
          }
        }
      }
    }

    if (enemySpawns.length > 0) {
      exportRoom.enemy_spawns = enemySpawns;
    }

    return exportRoom;
  });

  // Build spawn zone
  const spawnZones = {};
  if (spawnPoints.length > 0 && spawnBounds.x_min !== Infinity) {
    spawnZones.a = spawnBounds;
  }

  return {
    name: mapName,
    width,
    height,
    map_type: 'dungeon',
    spawn_points: spawnPoints.slice(0, 8),
    spawn_zones: spawnZones,
    ffa_points: spawnPoints.slice(0, 8),
    rooms: exportedRooms,
    doors,
    chests,
    tiles,
    tile_legend: {
      W: 'wall',
      F: 'floor',
      D: 'door',
      C: 'corridor',
      S: 'spawn',
      X: 'chest',
    },
  };
}

/**
 * Normalize tile types for export.
 * E and B markers become F (floor) — enemies are placed via rooms[].enemy_spawns.
 */
function normalizeForExport(tile) {
  switch (tile) {
    case 'E': return 'F';
    case 'B': return 'F';
    default: return tile;
  }
}

/**
 * Import an existing game map JSON.
 * Returns tile map and metadata for loading into the editor.
 *
 * @param {Object} json - Game map JSON
 * @returns {Object} { tileMap, name, width, height, rooms, doors, chests }
 */
export function importFromGameJSON(json) {
  return {
    tileMap: json.tiles || [],
    name: json.name || 'Imported Map',
    width: json.width,
    height: json.height,
    mapType: json.map_type || 'dungeon',
    rooms: json.rooms || [],
    doors: json.doors || [],
    chests: json.chests || [],
    spawnPoints: json.spawn_points || [],
  };
}

/**
 * Convert a binary CA grid (0/1) to a tile character map.
 *
 * @param {number[][]} grid - Binary grid (WALL=1, FLOOR=0)
 * @returns {string[][]} 2D array of tile characters
 */
export function gridToTileMap(grid) {
  return grid.map(row => row.map(cell => cell === WALL ? 'W' : 'F'));
}
