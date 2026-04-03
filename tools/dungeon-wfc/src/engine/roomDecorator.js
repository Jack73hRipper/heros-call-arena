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
    const roomTiles = room.variant.tiles || [];

    const placements = [];
    // Sort slots by priority for the assigned role (A) with door-distance (D)
    const availableSlots = sortSlotsForRole(room.slots, role, roomTiles, rng);

    switch (role) {
      case 'boss': {
        // Boss: sort boss-eligible slots with boss priority
        const bossSlots = sortSlotsForRole(
          availableSlots.filter(s => s.types?.includes('boss')),
          'boss', roomTiles, rng,
        );
        if (bossSlots.length > 0) {
          const bs = bossSlots[0];
          placeTile(decoratedMap, startR + bs.y, startC + bs.x, 'B');
          placements.push({ x: startC + bs.x, y: startR + bs.y, type: 'B' });
          // Guard enemies — sorted by enemy priority (near doors)
          const guardCandidates = sortSlotsForRole(
            availableSlots.filter(s => s !== bs && s.types?.includes('enemy')),
            'enemy', roomTiles, rng,
          );
          const guardCount = Math.min(2, guardCandidates.length);
          for (let i = 0; i < guardCount; i++) {
            placeTile(decoratedMap, startR + guardCandidates[i].y, startC + guardCandidates[i].x, 'E');
            placements.push({ x: startC + guardCandidates[i].x, y: startR + guardCandidates[i].y, type: 'E' });
          }
        }
        break;
      }

      case 'spawn': {
        // Spawn markers — sorted by spawn priority (corners first)
        const spawnSlots = sortSlotsForRole(
          availableSlots.filter(s => s.types?.includes('spawn')),
          'spawn', roomTiles, rng,
        );
        const count = Math.min(4, spawnSlots.length);
        for (let i = 0; i < count; i++) {
          placeTile(decoratedMap, startR + spawnSlots[i].y, startC + spawnSlots[i].x, 'S');
          placements.push({ x: startC + spawnSlots[i].x, y: startR + spawnSlots[i].y, type: 'S' });
        }
        break;
      }

      case 'enemy': {
        // Enemies sorted by enemy priority (center/interior, near doors)
        const enemySlots = sortSlotsForRole(
          availableSlots.filter(s => s.types?.includes('enemy')),
          'enemy', roomTiles, rng,
        );
        const count = Math.min(room.maxEnemies, enemySlots.length);
        const actualCount = Math.max(1, Math.floor(rng() * count) + 1);
        for (let i = 0; i < Math.min(actualCount, enemySlots.length); i++) {
          placeTile(decoratedMap, startR + enemySlots[i].y, startC + enemySlots[i].x, 'E');
          placements.push({ x: startC + enemySlots[i].x, y: startR + enemySlots[i].y, type: 'E' });
        }
        // Scatter bonus chest — placed far from enemies (loot priority)
        if (config.scatterChests && rng() < 0.3) {
          const placedPositions = new Set(placements.map(p => `${p.x},${p.y}`));
          const chestCandidates = sortSlotsForRole(
            availableSlots.filter(s =>
              s.types?.includes('loot') && !placedPositions.has(`${startC + s.x},${startR + s.y}`)
            ),
            'loot', roomTiles, rng,
          );
          if (chestCandidates.length > 0) {
            placeTile(decoratedMap, startR + chestCandidates[0].y, startC + chestCandidates[0].x, 'X');
            placements.push({ x: startC + chestCandidates[0].x, y: startR + chestCandidates[0].y, type: 'X' });
          }
        }
        break;
      }

      case 'loot': {
        // (B) Chest clustering: group chests near a wall away from doors
        const lootEligible = availableSlots.filter(s => s.types?.includes('loot'));
        const lootSlots = clusterLootSlots(lootEligible, roomTiles, rng);
        const count = Math.min(room.maxChests, lootSlots.length);
        const actualCount = Math.max(1, Math.floor(rng() * count) + 1);
        for (let i = 0; i < Math.min(actualCount, lootSlots.length); i++) {
          placeTile(decoratedMap, startR + lootSlots[i].y, startC + lootSlots[i].x, 'X');
          placements.push({ x: startC + lootSlots[i].x, y: startR + lootSlots[i].y, type: 'X' });
        }
        // Scatter guard enemy — placed near door (enemy priority)
        if (config.scatterEnemies && rng() < 0.35) {
          const placedPositions = new Set(placements.map(p => `${p.x},${p.y}`));
          const guardCandidates = sortSlotsForRole(
            availableSlots.filter(s =>
              s.types?.includes('enemy') && !placedPositions.has(`${startC + s.x},${startR + s.y}`)
            ),
            'enemy', roomTiles, rng,
          );
          if (guardCandidates.length > 0) {
            placeTile(decoratedMap, startR + guardCandidates[0].y, startC + guardCandidates[0].x, 'E');
            placements.push({ x: startC + guardCandidates[0].x, y: startR + guardCandidates[0].y, type: 'E' });
          }
        }
        break;
      }

      case 'empty':
      default: {
        // Atmospheric — scatter enemy sorted by enemy priority
        if (config.scatterEnemies && rng() < 0.15) {
          const enemySlots = sortSlotsForRole(
            availableSlots.filter(s => s.types?.includes('enemy')),
            'enemy', roomTiles, rng,
          );
          if (enemySlots.length > 0) {
            placeTile(decoratedMap, startR + enemySlots[0].y, startC + enemySlots[0].x, 'E');
            placements.push({ x: startC + enemySlots[0].x, y: startR + enemySlots[0].y, type: 'E' });
          }
        } else if (config.scatterChests && rng() < 0.1) {
          // Empty room scatter chest — placed in corner (loot priority)
          const lootSlots = sortSlotsForRole(
            availableSlots.filter(s => s.types?.includes('loot')),
            'loot', roomTiles, rng,
          );
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

// ─── Slot Classification & Priority Sorting ───────────────────────────

/**
 * Classify a slot position as 'center', 'corner', 'wall', or 'interior'.
 */
function classifySlot(x, y, tiles) {
  const h = tiles.length;
  const w = (tiles[0] || []).length;
  let adjWall = 0;
  for (const [dx, dy] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
    const nx = x + dx, ny = y + dy;
    if (nx < 0 || nx >= w || ny < 0 || ny >= h) adjWall++;
    else if (tiles[ny][nx] === 'W') adjWall++;
  }
  const isCorner = (x <= 2 && y <= 2) || (x >= 5 && y <= 2) || (x <= 2 && y >= 5) || (x >= 5 && y >= 5);
  const isCenter = x >= 3 && x <= 4 && y >= 3 && y <= 4;
  if (isCenter) return 'center';
  if (isCorner && adjWall >= 1) return 'corner';
  if (adjWall >= 1 && !isCorner) return 'wall';
  if (isCorner) return 'corner';
  return 'interior';
}

/** Default priority values for each hint type per role. */
const HINT_PRIORITIES = {
  center:   { loot: 0.3, enemy: 0.9, boss: 1.0, spawn: 0.3 },
  corner:   { loot: 0.8, enemy: 0.5, boss: 0.7, spawn: 0.9 },
  wall:     { loot: 1.0, enemy: 0.6, boss: 0.6, spawn: 0.7 },
  interior: { loot: 0.5, enemy: 0.8, boss: 0.5, spawn: 0.5 },
};

/**
 * Return the priority score for a slot when used for a given role.
 */
function getSlotPriority(slot, role) {
  if (slot.priority && slot.priority[role] != null) return slot.priority[role];
  const hint = slot.placement_hint || 'interior';
  return (HINT_PRIORITIES[hint] || HINT_PRIORITIES.interior)[role] ?? 0.5;
}

/**
 * Find door tiles and edge openings in a module's tile grid.
 */
function findDoorPositions(tiles) {
  const doors = [];
  const h = tiles.length;
  const w = (tiles[0] || []).length;
  for (let r = 0; r < h; r++) {
    for (let c = 0; c < w; c++) {
      const t = tiles[r][c];
      if (t === 'D') {
        doors.push([c, r]);
      } else if ((t === 'F' || t === 'C') && (r === 0 || r === h - 1 || c === 0 || c === w - 1)) {
        doors.push([c, r]);
      }
    }
  }
  return doors;
}

/**
 * Manhattan distance from a slot to the nearest door/opening.
 */
function slotDoorDistance(slot, doorPositions) {
  if (!doorPositions.length) return 0;
  let min = Infinity;
  for (const [dx, dy] of doorPositions) {
    const d = Math.abs(slot.x - dx) + Math.abs(slot.y - dy);
    if (d < min) min = d;
  }
  return min;
}

/**
 * Sort slots by priority for a given role, with door-distance as tiebreaker.
 * Loot/boss prefer far from doors; enemies prefer near doors.
 */
function sortSlotsForRole(slots, role, tiles, rng, reverse = false) {
  const doorPositions = findDoorPositions(tiles);
  const sorted = [...slots];
  const doorSign = role === 'enemy' ? -1.0 : 1.0;

  sorted.sort((a, b) => {
    const pa = getSlotPriority(a, role);
    const pb = getSlotPriority(b, role);
    const da = slotDoorDistance(a, doorPositions) / 14.0;
    const db = slotDoorDistance(b, doorPositions) / 14.0;
    const ja = rng() * 0.15;
    const jb = rng() * 0.15;
    const ka = -(pa + doorSign * da * 0.3 + ja);
    const kb = -(pb + doorSign * db * 0.3 + jb);
    return ka - kb;
  });
  if (reverse) sorted.reverse();
  return sorted;
}

/**
 * Sort loot slots to cluster chests near a chosen wall region ("treasure nook").
 * Picks a focal wall away from doors, then sorts by proximity to that wall.
 */
function clusterLootSlots(slots, tiles, rng) {
  if (slots.length <= 1) return slots;
  const h = tiles.length;
  const w = (tiles[0] || []).length;

  const doorPositions = findDoorPositions(tiles);
  const wallHasOpening = { top: false, bottom: false, left: false, right: false };
  for (const [dx, dy] of doorPositions) {
    if (dy === 0) wallHasOpening.top = true;
    if (dy === h - 1) wallHasOpening.bottom = true;
    if (dx === 0) wallHasOpening.left = true;
    if (dx === w - 1) wallHasOpening.right = true;
  }

  let closedWalls = Object.keys(wallHasOpening).filter(k => !wallHasOpening[k]);
  if (!closedWalls.length) closedWalls = Object.keys(wallHasOpening);

  const focalWall = closedWalls[Math.floor(rng() * closedWalls.length) % closedWalls.length];

  function wallDistance(s) {
    if (focalWall === 'top') return s.y;
    if (focalWall === 'bottom') return (h - 1) - s.y;
    if (focalWall === 'left') return s.x;
    return (w - 1) - s.x; // right
  }

  const result = [...slots];
  result.sort((a, b) => {
    const da = wallDistance(a);
    const db = wallDistance(b);
    if (da !== db) return da - db;
    const ca = Math.abs(a.x - Math.floor(w / 2)) + Math.abs(a.y - Math.floor(h / 2));
    const cb = Math.abs(b.x - Math.floor(w / 2)) + Math.abs(b.y - Math.floor(h / 2));
    return ca - cb;
  });
  return result;
}

/**
 * Derive floor slots from a tile grid (fallback when spawnSlots is empty).
 * Includes placement_hint and priority for each derived slot.
 */
function deriveFloorSlots(tiles) {
  const slots = [];
  if (!tiles) return slots;
  const h = tiles.length;
  const w = tiles[0]?.length || 0;
  for (let r = 1; r < h - 1; r++) {
    for (let c = 1; c < w - 1; c++) {
      if (tiles[r][c] === 'F') {
        const hint = classifySlot(c, r, tiles);
        const priority = { ...(HINT_PRIORITIES[hint] || HINT_PRIORITIES.interior) };
        slots.push({ x: c, y: r, types: ['enemy', 'loot', 'spawn', 'boss'], placement_hint: hint, priority });
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
