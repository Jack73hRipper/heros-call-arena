// ─────────────────────────────────────────────────────────
// exportMap.js — Convert WFC tile map to Arena game map JSON
//
// Matches the JSON format used by server/configs/maps/
// (dungeon_test.json, open_catacombs.json, etc.)
// ─────────────────────────────────────────────────────────

import { MODULE_SIZE } from '../engine/moduleUtils.js';

/**
 * Convert a WFC tile map + grid metadata into a game-compatible map JSON.
 *
 * @param {string[][]} tileMap - 2D array of tile characters
 * @param {Object[][]} grid - WFC grid with cell metadata (chosenVariant)
 * @param {Object[]} variants - Expanded variant list from WFC
 * @param {string} mapName - Name for the exported map
 * @returns {Object} Game-compatible map JSON
 */
export function exportToGameJSON(tileMap, grid, variants, mapName = 'WFC Generated Dungeon') {
  const height = tileMap.length;
  const width = tileMap[0]?.length || 0;

  // Convert tile map to game format (tile_legend mapping)
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

  // If no spawn points found, use first floor tile area as fallback
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

  // Build rooms from the WFC module grid
  // Scans the actual tileMap (which includes decorator placements) rather
  // than variant tiles, so decorated flexible rooms are exported correctly.
  const rooms = [];
  if (grid && variants) {
    const gridRows = grid.length;
    const gridCols = grid[0]?.length || 0;

    for (let gr = 0; gr < gridRows; gr++) {
      for (let gc = 0; gc < gridCols; gc++) {
        const cell = grid[gr][gc];
        if (cell.chosenVariant == null) continue;

        const variant = variants[cell.chosenVariant];
        const startR = gr * MODULE_SIZE;
        const startC = gc * MODULE_SIZE;

        // Scan the actual tileMap region for this module to detect content
        const enemySpawns = [];
        let hasContent = false;
        let detectedPurpose = variant.purpose || 'empty';

        for (let lr = 0; lr < MODULE_SIZE; lr++) {
          for (let lc = 0; lc < MODULE_SIZE; lc++) {
            const tile = tileMap[startR + lr]?.[startC + lc];
            if (tile === 'E') {
              enemySpawns.push({
                x: startC + lc,
                y: startR + lr,
                enemy_type: 'demon',
              });
              hasContent = true;
              if (detectedPurpose === 'empty') detectedPurpose = 'enemy';
            } else if (tile === 'B') {
              enemySpawns.push({
                x: startC + lc,
                y: startR + lr,
                enemy_type: 'undead_knight',
                is_boss: true,
              });
              hasContent = true;
              if (detectedPurpose === 'empty') detectedPurpose = 'boss';
            } else if (tile === 'S') {
              hasContent = true;
              if (detectedPurpose === 'empty') detectedPurpose = 'spawn';
            } else if (tile === 'X') {
              hasContent = true;
              if (detectedPurpose === 'empty') detectedPurpose = 'loot';
            }
          }
        }

        // Skip purely structural modules (corridors with no content, solid walls)
        if (!hasContent && (variant.purpose === 'empty' || variant.purpose === 'corridor')) continue;

        const room = {
          id: `room_${gr}_${gc}`,
          name: variant.sourceName,
          purpose: detectedPurpose,
          bounds: {
            x_min: startC,
            y_min: startR,
            x_max: startC + MODULE_SIZE - 1,
            y_max: startR + MODULE_SIZE - 1,
          },
        };

        if (enemySpawns.length > 0) {
          room.enemy_spawns = enemySpawns;
        }

        rooms.push(room);
      }
    }
  }

  // Build spawn zone from spawn bounds
  const spawnZones = {};
  if (spawnPoints.length > 0 && spawnBounds.x_min !== Infinity) {
    spawnZones.a = spawnBounds;
  }

  const mapJSON = {
    name: mapName,
    width,
    height,
    map_type: 'dungeon',
    spawn_points: spawnPoints.slice(0, 8), // Max 8 spawn points
    spawn_zones: spawnZones,
    ffa_points: spawnPoints.slice(0, 8),
    rooms,
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

  return mapJSON;
}

/**
 * Normalize tile types for game export.
 * E and B markers become F (floor) in the exported tile grid —
 * enemies are placed via the rooms[].enemy_spawns array instead.
 */
function normalizeForExport(tile) {
  switch (tile) {
    case 'E': return 'F';
    case 'B': return 'F';
    default: return tile;
  }
}

/**
 * Import an existing game map JSON and convert it to a tile map for preview.
 */
export function importFromGameJSON(json) {
  return {
    tileMap: json.tiles || [],
    name: json.name || 'Imported Map',
    width: json.width,
    height: json.height,
    rooms: json.rooms || [],
    doors: json.doors || [],
    chests: json.chests || [],
  };
}
