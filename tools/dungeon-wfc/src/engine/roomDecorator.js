// ─────────────────────────────────────────────────────────
// roomDecorator.js — Post-generation room content decorator
//
// After WFC assembles the structural dungeon, this pass assigns
// gameplay content (enemies, loot, bosses, spawn points) to
// "flexible" rooms based on configurable density settings.
//
// Fixed rooms (with baked-in E/X/S/B tiles) are left untouched.
// Structural rooms (corridors, filler, grand interiors) are skipped.
// ─────────────────────────────────────────────────────────

import { MODULE_SIZE } from './moduleUtils.js';

/**
 * Default decorator settings. These can be overridden from the UI.
 */
export const DEFAULT_DECORATOR_SETTINGS = {
  enemyDensity: 0.4,      // 0–1: fraction of flexible rooms that get enemies
  lootDensity: 0.25,       // 0–1: fraction of flexible rooms that get loot
  guaranteeBoss: true,     // If true, at least 1 flexible room becomes a boss room
  guaranteeSpawn: true,    // If true, at least 1 flexible room becomes a spawn room
  emptyRoomChance: 0.2,   // 0–1: chance a room stays completely empty (atmosphere/pacing)
  scatterEnemies: true,    // If true, some "loot" and "empty" rooms get 1 random enemy
  scatterChests: true,     // If true, some "enemy" rooms get 1 bonus chest
};

/**
 * Decorator result for a single room.
 * @typedef {Object} DecoratedRoom
 * @property {number} gridRow - Module grid row
 * @property {number} gridCol - Module grid col
 * @property {string} assignedRole - 'enemy' | 'loot' | 'boss' | 'spawn' | 'empty'
 * @property {Array<{x:number, y:number, type:string}>} placements - Tile placements (E/X/S/B)
 * @property {string} sourceName - Original module name
 */

/**
 * Create a seeded RNG (mulberry32) for deterministic decoration.
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

/**
 * Shuffle an array in-place using Fisher-Yates with provided RNG.
 */
function shuffle(arr, rng) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

/**
 * Run the room decorator on a completed WFC result.
 *
 * @param {Object} params
 * @param {Object[][]} params.grid - WFC grid (rows × cols of cells with chosenVariant)
 * @param {Object[]} params.variants - Expanded variant list from WFC
 * @param {string[][]} params.tileMap - 2D tile map from assembleToTileMap
 * @param {number} params.seed - RNG seed for deterministic results
 * @param {Object} params.settings - Decorator settings (merged with defaults)
 * @returns {{ decoratedRooms: DecoratedRoom[], tileMap: string[][], stats: Object }}
 */
export function decorateRooms({ grid, variants, tileMap, seed = 42, settings = {} }) {
  const config = { ...DEFAULT_DECORATOR_SETTINGS, ...settings };
  const rng = createRNG(seed + 77777); // Offset seed from WFC seed for independent randomization

  // Deep-clone the tile map so we don't mutate the original
  const decoratedMap = tileMap.map(row => [...row]);

  const gridRows = grid.length;
  const gridCols = grid[0]?.length || 0;

  // ── Phase 1: Collect flexible rooms ──
  const flexibleRooms = [];
  const fixedRooms = [];

  for (let gr = 0; gr < gridRows; gr++) {
    for (let gc = 0; gc < gridCols; gc++) {
      const cell = grid[gr][gc];
      if (cell.chosenVariant == null) continue;

      const variant = variants[cell.chosenVariant];
      if (!variant) continue;

      const role = variant.contentRole || inferContentRole(variant);

      if (role === 'flexible') {
        // Derive spawnSlots from tile data if not provided
        const slots = (variant.spawnSlots && variant.spawnSlots.length > 0)
          ? variant.spawnSlots
          : deriveFloorSlots(variant.tiles);

        flexibleRooms.push({
          gridRow: gr,
          gridCol: gc,
          variant,
          slots,
          maxEnemies: variant.maxEnemies || Math.min(3, Math.floor(slots.length / 2)),
          maxChests: variant.maxChests || Math.min(2, Math.floor(slots.length / 3)),
          canBeBoss: variant.canBeBoss !== false && slots.some(s => s.types?.includes('boss')),
          canBeSpawn: variant.canBeSpawn !== false && slots.some(s => s.types?.includes('spawn')),
        });
      } else if (role === 'fixed') {
        fixedRooms.push({
          gridRow: gr,
          gridCol: gc,
          variant,
          purpose: variant.purpose,
        });
      }
      // 'structural' rooms are fully skipped
    }
  }

  // ── Phase 2: Check what fixed rooms already provide ──
  const hasFixedBoss = fixedRooms.some(r => r.purpose === 'boss');
  const hasFixedSpawn = fixedRooms.some(r => r.purpose === 'spawn');

  // ── Phase 3: Assign roles to flexible rooms ──
  shuffle(flexibleRooms, rng);

  const decoratedRooms = [];
  const assignments = new Map(); // key = "gr,gc" → assigned role

  let bossAssigned = hasFixedBoss;
  let spawnAssigned = hasFixedSpawn;

  // Pass A: Guarantee boss room
  if (config.guaranteeBoss && !bossAssigned) {
    const bossCandidate = flexibleRooms.find(r => r.canBeBoss);
    if (bossCandidate) {
      const key = `${bossCandidate.gridRow},${bossCandidate.gridCol}`;
      assignments.set(key, 'boss');
      bossAssigned = true;
    }
  }

  // Pass B: Guarantee spawn room
  if (config.guaranteeSpawn && !spawnAssigned) {
    const spawnCandidate = flexibleRooms.find(r =>
      r.canBeSpawn && !assignments.has(`${r.gridRow},${r.gridCol}`)
    );
    if (spawnCandidate) {
      const key = `${spawnCandidate.gridRow},${spawnCandidate.gridCol}`;
      assignments.set(key, 'spawn');
      spawnAssigned = true;
    }
  }

  // Pass C: Assign remaining flexible rooms
  for (const room of flexibleRooms) {
    const key = `${room.gridRow},${room.gridCol}`;
    if (assignments.has(key)) continue;

    const roll = rng();

    // Chance to stay empty (atmospheric pacing)
    if (roll < config.emptyRoomChance) {
      assignments.set(key, 'empty');
      continue;
    }

    // Weighted random between 'enemy' and 'loot'
    const enemyThreshold = config.emptyRoomChance + config.enemyDensity * (1 - config.emptyRoomChance);
    const lootThreshold = enemyThreshold + config.lootDensity * (1 - config.emptyRoomChance);

    if (roll < enemyThreshold) {
      assignments.set(key, 'enemy');
    } else if (roll < lootThreshold) {
      assignments.set(key, 'loot');
    } else {
      assignments.set(key, 'empty');
    }
  }

  // ── Phase 4: Place content based on assignments ──
  for (const room of flexibleRooms) {
    const key = `${room.gridRow},${room.gridCol}`;
    const role = assignments.get(key) || 'empty';

    const startR = room.gridRow * MODULE_SIZE;
    const startC = room.gridCol * MODULE_SIZE;

    const placements = [];
    const availableSlots = shuffle([...room.slots], rng);

    switch (role) {
      case 'boss': {
        // Place boss marker(s) at boss-eligible slots
        const bossSlots = availableSlots.filter(s => s.types?.includes('boss'));
        if (bossSlots.length > 0) {
          // Place 1 boss marker (B) at first boss slot
          const bs = bossSlots[0];
          placeTile(decoratedMap, startR + bs.y, startC + bs.x, 'B');
          placements.push({ x: startC + bs.x, y: startR + bs.y, type: 'B' });
          // Also place 1-2 enemy guards
          const guardSlots = availableSlots.filter(s =>
            s !== bs && s.types?.includes('enemy')
          );
          const guardCount = Math.min(2, guardSlots.length);
          for (let i = 0; i < guardCount; i++) {
            placeTile(decoratedMap, startR + guardSlots[i].y, startC + guardSlots[i].x, 'E');
            placements.push({ x: startC + guardSlots[i].x, y: startR + guardSlots[i].y, type: 'E' });
          }
        }
        break;
      }

      case 'spawn': {
        // Place spawn markers at spawn-eligible slots
        const spawnSlots = availableSlots.filter(s => s.types?.includes('spawn'));
        const count = Math.min(4, spawnSlots.length);
        for (let i = 0; i < count; i++) {
          placeTile(decoratedMap, startR + spawnSlots[i].y, startC + spawnSlots[i].x, 'S');
          placements.push({ x: startC + spawnSlots[i].x, y: startR + spawnSlots[i].y, type: 'S' });
        }
        break;
      }

      case 'enemy': {
        // Place enemies at enemy-eligible slots (up to maxEnemies)
        const enemySlots = availableSlots.filter(s => s.types?.includes('enemy'));
        const count = Math.min(room.maxEnemies, enemySlots.length);
        // Randomize how many (at least 1)
        const actualCount = Math.max(1, Math.floor(rng() * count) + 1);
        for (let i = 0; i < Math.min(actualCount, enemySlots.length); i++) {
          placeTile(decoratedMap, startR + enemySlots[i].y, startC + enemySlots[i].x, 'E');
          placements.push({ x: startC + enemySlots[i].x, y: startR + enemySlots[i].y, type: 'E' });
        }
        // Scatter bonus chest
        if (config.scatterChests && rng() < 0.3) {
          const chestSlots = availableSlots.filter(s =>
            s.types?.includes('loot') && !placements.some(p => p.x === startC + s.x && p.y === startR + s.y)
          );
          if (chestSlots.length > 0) {
            placeTile(decoratedMap, startR + chestSlots[0].y, startC + chestSlots[0].x, 'X');
            placements.push({ x: startC + chestSlots[0].x, y: startR + chestSlots[0].y, type: 'X' });
          }
        }
        break;
      }

      case 'loot': {
        // Place chests at loot-eligible slots (up to maxChests)
        const lootSlots = availableSlots.filter(s => s.types?.includes('loot'));
        const count = Math.min(room.maxChests, lootSlots.length);
        const actualCount = Math.max(1, Math.floor(rng() * count) + 1);
        for (let i = 0; i < Math.min(actualCount, lootSlots.length); i++) {
          placeTile(decoratedMap, startR + lootSlots[i].y, startC + lootSlots[i].x, 'X');
          placements.push({ x: startC + lootSlots[i].x, y: startR + lootSlots[i].y, type: 'X' });
        }
        // Scatter a guard enemy
        if (config.scatterEnemies && rng() < 0.35) {
          const enemySlots = availableSlots.filter(s =>
            s.types?.includes('enemy') && !placements.some(p => p.x === startC + s.x && p.y === startR + s.y)
          );
          if (enemySlots.length > 0) {
            placeTile(decoratedMap, startR + enemySlots[0].y, startC + enemySlots[0].x, 'E');
            placements.push({ x: startC + enemySlots[0].x, y: startR + enemySlots[0].y, type: 'E' });
          }
        }
        break;
      }

      case 'empty':
      default: {
        // Atmospheric — maybe scatter a lone enemy or chest
        if (config.scatterEnemies && rng() < 0.15) {
          const enemySlots = availableSlots.filter(s => s.types?.includes('enemy'));
          if (enemySlots.length > 0) {
            placeTile(decoratedMap, startR + enemySlots[0].y, startC + enemySlots[0].x, 'E');
            placements.push({ x: startC + enemySlots[0].x, y: startR + enemySlots[0].y, type: 'E' });
          }
        } else if (config.scatterChests && rng() < 0.1) {
          const lootSlots = availableSlots.filter(s => s.types?.includes('loot'));
          if (lootSlots.length > 0) {
            placeTile(decoratedMap, startR + lootSlots[0].y, startC + lootSlots[0].x, 'X');
            placements.push({ x: startC + lootSlots[0].x, y: startR + lootSlots[0].y, type: 'X' });
          }
        }
        break;
      }
    }

    decoratedRooms.push({
      gridRow: room.gridRow,
      gridCol: room.gridCol,
      assignedRole: role,
      placements,
      sourceName: room.variant.sourceName || room.variant.name || 'Unknown',
    });
  }

  // ── Phase 5: Compute decoration stats ──
  const stats = computeDecorationStats(decoratedRooms, fixedRooms);

  return {
    decoratedRooms,
    tileMap: decoratedMap,
    stats,
  };
}

/**
 * Place a tile on the map (only if target is currently floor).
 */
function placeTile(tileMap, row, col, tile) {
  if (row >= 0 && row < tileMap.length && col >= 0 && col < tileMap[0].length) {
    if (tileMap[row][col] === 'F') {
      tileMap[row][col] = tile;
    }
  }
}

/**
 * Infer contentRole from a variant if the field is missing.
 * Used for backwards compatibility with modules that don't have the field.
 */
function inferContentRole(variant) {
  const purpose = variant.purpose || 'empty';

  // Fixed content: modules that have baked-in E/X/S/B tiles
  if (['enemy', 'boss', 'loot', 'spawn'].includes(purpose)) {
    return 'fixed';
  }

  // Structural: corridors, solid walls, grand interior pieces
  if (purpose === 'corridor') return 'structural';

  // Check if the module is a pure filler (all walls or interior piece)
  const hasMostlyFloor = variant.tiles?.flat().filter(t => t === 'F').length > 0;
  if (!hasMostlyFloor) return 'structural';

  // Check for grand interior pieces (center/edge — 3+ interior joins)
  const sockets = variant.sockets || {};
  const interiorJoinSocket = 'WOOOOW';
  const interiorJoinCount = ['north', 'south', 'east', 'west']
    .filter(d => sockets[d] === interiorJoinSocket).length;
  if (interiorJoinCount >= 3) return 'structural'; // Grand Center (4) and Grand Edge (3)

  // Default: flexible (empty rooms suitable for decoration)
  return 'flexible';
}

/**
 * Derive floor slots from a tile grid (fallback when spawnSlots is empty).
 * Returns interior floor tiles as spawn slot candidates.
 */
function deriveFloorSlots(tiles) {
  const slots = [];
  if (!tiles) return slots;
  const h = tiles.length;
  const w = tiles[0]?.length || 0;
  for (let r = 1; r < h - 1; r++) {
    for (let c = 1; c < w - 1; c++) {
      if (tiles[r][c] === 'F') {
        slots.push({ x: c, y: r, types: ['enemy', 'loot', 'spawn', 'boss'] });
      }
    }
  }
  return slots;
}

/**
 * Compute summary stats about the decoration pass.
 */
function computeDecorationStats(decoratedRooms, fixedRooms) {
  const roleCount = { enemy: 0, loot: 0, boss: 0, spawn: 0, empty: 0 };
  let totalPlacements = 0;
  let enemiesPlaced = 0;
  let chestsPlaced = 0;
  let bossesPlaced = 0;
  let spawnsPlaced = 0;

  for (const room of decoratedRooms) {
    roleCount[room.assignedRole] = (roleCount[room.assignedRole] || 0) + 1;
    totalPlacements += room.placements.length;
    for (const p of room.placements) {
      if (p.type === 'E') enemiesPlaced++;
      else if (p.type === 'X') chestsPlaced++;
      else if (p.type === 'B') bossesPlaced++;
      else if (p.type === 'S') spawnsPlaced++;
    }
  }

  return {
    flexibleRooms: decoratedRooms.length,
    fixedRooms: fixedRooms.length,
    roleCount,
    totalPlacements,
    enemiesPlaced,
    chestsPlaced,
    bossesPlaced,
    spawnsPlaced,
  };
}
