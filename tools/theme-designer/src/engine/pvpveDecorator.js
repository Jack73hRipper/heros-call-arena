// ─────────────────────────────────────────────────────────
// pvpveDecorator.js — PVPVE-specific room assignment & door placement
//
// Ports the PVPVE logic from:
//   server/app/core/wfc/room_decorator.py  (corner spawns, center boss,
//     difficulty tiers, proximity ramp)
//   server/app/core/wfc/door_placer.py     (module-boundary door insertion)
//
// Used by pvpveGenerator.js to overlay PVPVE layout rules on top of
// the base room decoration from @wfc/roomDecorator.js.
// ─────────────────────────────────────────────────────────

import { MODULE_SIZE } from '@wfc/moduleUtils.js';

// ─── Constants ───────────────────────────────────────────

/** PVPVE team corner targets: team_key → (target_row, target_col) functions */
const TEAM_CORNERS = {
  a: (maxRow, _maxCol) => [0, 0],           // Top-left
  b: (maxRow, maxCol) => [maxRow, maxCol],   // Bottom-right
  c: (_maxRow, maxCol) => [0, maxCol],       // Top-right
  d: (maxRow, _maxCol) => [maxRow, 0],       // Bottom-left
};

/** Team activation order based on team count */
const TEAM_ORDER = ['a', 'b', 'c', 'd'];

/**
 * Difficulty tiers by Manhattan distance to grid center.
 * [maxDistance, tierName, maxEnemies, rarityBias]
 */
const DIFFICULTY_TIERS = [
  [0, 'boss',  5, 'super_unique'],
  [1, 'elite', 5, 'champion'],
  [2, 'hard',  4, 'rare'],
  // Anything farther → "normal"
];

/** Default door placement settings (ported from door_placer.py) */
const DEFAULT_DOOR_SETTINGS = {
  doorChance: 0.45,
  bossRoomDoorChance: 0.70,
  spawnRoomDoorChance: 0.0,
  narrowDoorChance: 0.55,
  interiorDoorChance: 0.0,
  corridorOnlyDoorChance: 0.15,
  minOpeningsForDoor: 1,
};

// ─── RNG ─────────────────────────────────────────────────

function createRNG(seed) {
  let s = seed | 0;
  return function () {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffle(arr, rng) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

// ─── Tile helpers ────────────────────────────────────────

function placeTile(tileMap, row, col, tile) {
  if (row >= 0 && row < tileMap.length && col >= 0 && col < tileMap[0].length) {
    if (tileMap[row][col] === 'F') {
      tileMap[row][col] = tile;
    }
  }
}

function inferContentRole(variant) {
  const purpose = variant.purpose || 'empty';
  if (['enemy', 'boss', 'loot', 'spawn'].includes(purpose)) return 'fixed';
  if (purpose === 'corridor') return 'structural';
  const hasFloor = variant.tiles?.flat().some(t => t === 'F');
  if (!hasFloor) return 'structural';
  const sockets = variant.sockets || {};
  const joinCount = ['north', 'south', 'east', 'west']
    .filter(d => sockets[d] === 'WOOOOW').length;
  if (joinCount >= 3) return 'structural';
  return 'flexible';
}

function deriveFloorSlots(tiles) {
  const slots = [];
  if (!tiles || !tiles.length) return slots;
  const h = tiles.length;
  const w = tiles[0].length;
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

// ─── Slot Classification & Priority Sorting ───────────────────────────

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

const HINT_PRIORITIES = {
  center:   { loot: 0.3, enemy: 0.9, boss: 1.0, spawn: 0.3 },
  corner:   { loot: 0.8, enemy: 0.5, boss: 0.7, spawn: 0.9 },
  wall:     { loot: 1.0, enemy: 0.6, boss: 0.6, spawn: 0.7 },
  interior: { loot: 0.5, enemy: 0.8, boss: 0.5, spawn: 0.5 },
};

function getSlotPriority(slot, role) {
  if (slot.priority && slot.priority[role] != null) return slot.priority[role];
  const hint = slot.placement_hint || 'interior';
  return (HINT_PRIORITIES[hint] || HINT_PRIORITIES.interior)[role] ?? 0.5;
}

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

function slotDoorDistance(slot, doorPositions) {
  if (!doorPositions.length) return 0;
  let min = Infinity;
  for (const [dx, dy] of doorPositions) {
    const d = Math.abs(slot.x - dx) + Math.abs(slot.y - dy);
    if (d < min) min = d;
  }
  return min;
}

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
    return -(pa + doorSign * da * 0.3 + ja) - (-(pb + doorSign * db * 0.3 + jb));
  });
  if (reverse) sorted.reverse();
  return sorted;
}

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
    return (w - 1) - s.x;
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

// ─── PVPVE Layout Helpers ────────────────────────────────

function getActiveTeams(teamCount) {
  return TEAM_ORDER.slice(0, Math.max(2, Math.min(4, teamCount)));
}

function findNearestFlexible(targetRow, targetCol, flexibleRooms, assignedKeys, maxRadius = 99) {
  let bestRoom = null;
  let bestDist = maxRadius + 1;
  for (const room of flexibleRooms) {
    const key = `${room.gridRow},${room.gridCol}`;
    if (assignedKeys.has(key)) continue;
    const dist = Math.abs(room.gridRow - targetRow) + Math.abs(room.gridCol - targetCol);
    if (dist < bestDist) {
      bestDist = dist;
      bestRoom = room;
    }
  }
  return bestDist <= maxRadius ? bestRoom : null;
}

function assignCornerSpawns(flexibleRooms, gridRows, gridCols, teamCount, assignments) {
  const activeTeams = getActiveTeams(teamCount);
  const maxRow = gridRows - 1;
  const maxCol = gridCols - 1;
  const assignedKeys = new Set(assignments.keys());
  const spawnRooms = {};

  for (const teamKey of activeTeams) {
    const [targetR, targetC] = TEAM_CORNERS[teamKey](maxRow, maxCol);
    const room = findNearestFlexible(targetR, targetC, flexibleRooms, assignedKeys);
    if (room) {
      const key = `${room.gridRow},${room.gridCol}`;
      assignments.set(key, `spawn_${teamKey}`);
      assignedKeys.add(key);
      spawnRooms[teamKey] = room;
    }
  }
  return spawnRooms;
}

function assignCenterBoss(flexibleRooms, gridRows, gridCols, assignments) {
  const centerRow = Math.floor(gridRows / 2);
  const centerCol = Math.floor(gridCols / 2);
  const assignedKeys = new Set(assignments.keys());

  // Prefer boss-capable rooms
  const bossRooms = flexibleRooms.filter(r => r.canBeBoss);
  let room = findNearestFlexible(centerRow, centerCol, bossRooms, assignedKeys);
  if (!room) {
    room = findNearestFlexible(centerRow, centerCol, flexibleRooms, assignedKeys);
  }
  if (room) {
    const key = `${room.gridRow},${room.gridCol}`;
    assignments.set(key, 'boss');
  }
  return room;
}

function computeProximityRamp(flexibleRooms, spawnRooms) {
  const roomDistances = {};
  const proximityOverrides = {};
  const spawnPositions = Object.values(spawnRooms).map(r => [r.gridRow, r.gridCol]);

  for (const room of flexibleRooms) {
    const key = `${room.gridRow},${room.gridCol}`;
    let dist = 99;
    if (spawnPositions.length > 0) {
      dist = Math.min(...spawnPositions.map(([sr, sc]) =>
        Math.abs(room.gridRow - sr) + Math.abs(room.gridCol - sc)
      ));
    }
    roomDistances[key] = dist;
    if (dist <= 1) proximityOverrides[key] = 'safe';
    else if (dist === 2) proximityOverrides[key] = 'softened';
  }
  return { roomDistances, proximityOverrides };
}

function computeDifficultyTier(room, gridRows, gridCols) {
  const centerRow = gridRows / 2;
  const centerCol = gridCols / 2;
  const dist = Math.abs(room.gridRow - centerRow) + Math.abs(room.gridCol - centerCol);
  const intDist = Math.round(dist);
  for (const [maxDist, tierName] of DIFFICULTY_TIERS) {
    if (intDist <= maxDist) return { tier: tierName, distance: intDist };
  }
  return { tier: 'normal', distance: intDist };
}

function getMaxEnemiesForTier(tier, baseMax) {
  for (const [, tierName, maxEnemies] of DIFFICULTY_TIERS) {
    if (tier === tierName) return maxEnemies;
  }
  return Math.min(baseMax, 3); // normal tier
}

// ─── Door Placement (ported from door_placer.py) ─────────

function classifyModule(variant) {
  if (!variant) return 'structural';
  const purpose = variant.purpose || 'empty';
  const contentRole = variant.contentRole || 'structural';
  if (purpose === 'spawn') return 'spawn';
  if (purpose === 'boss') return 'boss';
  if (purpose === 'corridor') return 'corridor';
  if (contentRole === 'flexible' || contentRole === 'fixed') return 'room';
  return 'structural';
}

function findOpenRuns(edgeTiles) {
  const runs = [];
  let i = 0;
  const n = edgeTiles.length;
  while (i < n) {
    if (edgeTiles[i] !== 'W') {
      const start = i;
      while (i < n && edgeTiles[i] !== 'W') i++;
      runs.push([start, i - start]);
    } else {
      i++;
    }
  }
  return runs;
}

function scanBoundaries(tileMap, grid, variants, decorationLookup) {
  const gridRows = grid.length;
  const gridCols = grid[0]?.length || 0;
  const height = tileMap.length;
  const width = tileMap[0]?.length || 0;
  const boundaries = [];

  function getVariant(gr, gc) {
    const vi = grid[gr][gc].chosenVariant;
    if (vi == null || vi >= variants.length) return null;
    return variants[vi];
  }

  function getRole(gr, gc, variant) {
    const key = `${gr},${gc}`;
    const decRole = decorationLookup[key];
    if (decRole === 'spawn' || decRole?.startsWith('spawn_')) return 'spawn';
    if (decRole === 'boss') return 'boss';
    if (!variant) return 'structural';
    return classifyModule(variant);
  }

  // Horizontal boundaries (between vertically adjacent modules)
  for (let gr = 0; gr < gridRows - 1; gr++) {
    for (let gc = 0; gc < gridCols; gc++) {
      const varA = getVariant(gr, gc);
      const varB = getVariant(gr + 1, gc);
      const roleA = getRole(gr, gc, varA);
      const roleB = getRole(gr + 1, gc, varB);

      const boundaryYA = gr * MODULE_SIZE + (MODULE_SIZE - 1);
      const startX = gc * MODULE_SIZE;
      if (boundaryYA >= height || (gr + 1) * MODULE_SIZE >= height) continue;

      const edgeTiles = [];
      for (let dx = 0; dx < MODULE_SIZE; dx++) {
        const tx = startX + dx;
        edgeTiles.push(tx < width ? tileMap[boundaryYA][tx] : 'W');
      }

      const runs = findOpenRuns(edgeTiles);
      if (!runs.length) continue;

      const openings = runs.map(([runStart, runLen]) => {
        const tiles = [];
        for (let dx = 0; dx < runLen; dx++) {
          tiles.push([startX + runStart + dx, boundaryYA]);
        }
        return { start: runStart, length: runLen, tiles };
      });

      boundaries.push({
        direction: 'horizontal',
        cellA: [gr, gc],
        cellB: [gr + 1, gc],
        roleA, roleB,
        openings,
        socketWidth: runs.reduce((s, [, len]) => s + len, 0),
      });
    }
  }

  // Vertical boundaries (between horizontally adjacent modules)
  for (let gr = 0; gr < gridRows; gr++) {
    for (let gc = 0; gc < gridCols - 1; gc++) {
      const varA = getVariant(gr, gc);
      const varB = getVariant(gr, gc + 1);
      const roleA = getRole(gr, gc, varA);
      const roleB = getRole(gr, gc + 1, varB);

      const boundaryXA = gc * MODULE_SIZE + (MODULE_SIZE - 1);
      const startY = gr * MODULE_SIZE;
      if (boundaryXA >= width || (gc + 1) * MODULE_SIZE >= width) continue;

      const edgeTiles = [];
      for (let dy = 0; dy < MODULE_SIZE; dy++) {
        const ty = startY + dy;
        edgeTiles.push(ty < height ? tileMap[ty][boundaryXA] : 'W');
      }

      const runs = findOpenRuns(edgeTiles);
      if (!runs.length) continue;

      const openings = runs.map(([runStart, runLen]) => {
        const tiles = [];
        for (let dy = 0; dy < runLen; dy++) {
          tiles.push([boundaryXA, startY + runStart + dy]);
        }
        return { start: runStart, length: runLen, tiles };
      });

      boundaries.push({
        direction: 'vertical',
        cellA: [gr, gc],
        cellB: [gr, gc + 1],
        roleA, roleB,
        openings,
        socketWidth: runs.reduce((s, [, len]) => s + len, 0),
      });
    }
  }

  return boundaries;
}

function getDoorChance(boundary, settings) {
  const { roleA, roleB, socketWidth: sw } = boundary;

  if (roleA === 'spawn' || roleB === 'spawn')
    return settings.spawnRoomDoorChance ?? 0;
  if (roleA === 'structural' || roleB === 'structural')
    return 0;
  if (sw >= 6)
    return settings.interiorDoorChance ?? 0;
  if (roleA === 'boss' || roleB === 'boss')
    return settings.bossRoomDoorChance ?? 0.70;
  if (roleA === 'corridor' && roleB === 'corridor')
    return settings.corridorOnlyDoorChance ?? 0.15;
  if (sw <= 2)
    return settings.narrowDoorChance ?? 0.55;
  return settings.doorChance ?? 0.45;
}

function placeDoorAtOpening(tileMap, opening, rng) {
  const { tiles, length } = opening;
  if (length < 1) return null;

  if (length === 1) {
    const [dx, dy] = tiles[0];
    tileMap[dy][dx] = 'D';
    return { x: dx, y: dy };
  }

  const center = Math.floor(length / 2);
  let doorIdx;
  if (length >= 3) {
    const offset = rng() < 0.5 ? -1 : 0;
    doorIdx = Math.max(0, Math.min(length - 1, center + offset));
  } else {
    doorIdx = rng() < 0.5 ? 0 : 1;
  }

  let doorX = null, doorY = null;
  for (let i = 0; i < tiles.length; i++) {
    const [tx, ty] = tiles[i];
    if (i === doorIdx) {
      tileMap[ty][tx] = 'D';
      doorX = tx;
      doorY = ty;
    } else {
      tileMap[ty][tx] = 'W';
    }
  }

  return doorX != null ? { x: doorX, y: doorY } : null;
}

function insertRoomDoors(tileMap, grid, variants, seed, settings, decorationLookup) {
  const config = { ...DEFAULT_DOOR_SETTINGS, ...(settings || {}) };
  const rng = createRNG(seed + 99991);

  const boundaries = scanBoundaries(tileMap, grid, variants, decorationLookup);
  const doorsPlaced = [];
  let openingsSkipped = 0;

  for (const boundary of boundaries) {
    const chance = getDoorChance(boundary, config);
    if (chance <= 0) {
      openingsSkipped += boundary.openings.length;
      continue;
    }
    if (rng() >= chance) {
      openingsSkipped += boundary.openings.length;
      continue;
    }
    for (const opening of boundary.openings) {
      const result = placeDoorAtOpening(tileMap, opening, rng);
      if (result) doorsPlaced.push(result);
    }
  }

  return {
    doors: doorsPlaced,
    stats: {
      boundariesScanned: boundaries.length,
      doorsPlaced: doorsPlaced.length,
      openingsSkipped,
    },
  };
}

// ─── Main Export ─────────────────────────────────────────

/**
 * Apply PVPVE room assignments on top of base-decorated rooms.
 *
 * This is the full PVPVE decorator: it collects flexible rooms from the
 * WFC grid, assigns corner spawns, center boss, difficulty tiers,
 * proximity ramp, deals remaining rooms via quota deck, places content
 * tiles, and inserts doors at module boundaries.
 *
 * @param {Object} opts
 * @param {string[][]} opts.tileMap       - Tile map (deep-cloned internally)
 * @param {Object[][]} opts.grid          - WFC grid (rows x cols)
 * @param {Object[]}   opts.variants      - Expanded WFC variants
 * @param {number}     opts.seed          - RNG seed
 * @param {number}     opts.teamCount     - 2-4 player teams
 * @param {number}     opts.gridRows      - Module grid row count
 * @param {number}     opts.gridCols      - Module grid col count
 * @returns {{ tileMap, rooms, doors, spawnZones, bossRoom, difficultyTiers, stats }}
 */
export function applyPvpveLayout({
  tileMap,
  grid,
  variants,
  seed = 42,
  teamCount = 4,
  gridRows,
  gridCols,
}) {
  const rng = createRNG(seed + 77777);
  const decoratedMap = tileMap.map(row => [...row]);

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
        const slots = (variant.spawnSlots?.length > 0)
          ? variant.spawnSlots
          : deriveFloorSlots(variant.tiles);
        flexibleRooms.push({
          gridRow: gr,
          gridCol: gc,
          variant,
          slots,
          maxEnemies: variant.maxEnemies || Math.min(5, Math.floor(slots.length / 2)),
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
    }
  }

  // ── Phase 2: PVPVE role assignments ──
  shuffle(flexibleRooms, rng);

  const assignments = new Map();
  const hasFixedBoss = fixedRooms.some(r => r.purpose === 'boss');

  // Pass A: Corner spawn rooms
  const spawnRooms = assignCornerSpawns(flexibleRooms, gridRows, gridCols, teamCount, assignments);

  // Pass B: Center boss room
  let bossRoom = null;
  if (!hasFixedBoss) {
    bossRoom = assignCenterBoss(flexibleRooms, gridRows, gridCols, assignments);
  }

  // Pass B3: Proximity ramp + difficulty tiers
  const { roomDistances, proximityOverrides } = computeProximityRamp(flexibleRooms, spawnRooms);
  const difficultyTiers = {};
  for (const room of flexibleRooms) {
    const key = `${room.gridRow},${room.gridCol}`;
    const { tier } = computeDifficultyTier(room, gridRows, gridCols);
    difficultyTiers[key] = tier;
  }

  // ── Pass C: Assign remaining rooms via quota deck ──
  const config = {
    enemyDensity: 0.50,
    lootDensity: 0.15,
    emptyRoomChance: 0.15,
    scatterEnemies: true,
    scatterChests: true,
  };

  // Archetype carve-out
  const shrineChance = 0.05;
  const libraryChance = 0.05;
  const floodedChance = 0.05;
  const prisonEnemyChance = 0.10;
  const specialtyAssigned = new Set();

  let remaining = flexibleRooms.filter(r => !assignments.has(`${r.gridRow},${r.gridCol}`));
  shuffle(remaining, rng);

  for (const room of remaining) {
    const key = `${room.gridRow},${room.gridCol}`;
    if (specialtyAssigned.has(key)) continue;
    const roll = rng();
    if (roll < shrineChance) {
      assignments.set(key, 'shrine');
      specialtyAssigned.add(key);
    } else if (roll < shrineChance + libraryChance) {
      assignments.set(key, 'library');
      specialtyAssigned.add(key);
    } else if (roll < shrineChance + libraryChance + floodedChance) {
      assignments.set(key, 'flooded');
      specialtyAssigned.add(key);
    }
  }

  remaining = remaining.filter(r => !specialtyAssigned.has(`${r.gridRow},${r.gridCol}`));
  const n = remaining.length;

  if (n > 0) {
    let nEnemy = Math.round(n * config.enemyDensity);
    let nLoot = Math.round(n * config.lootDensity);
    let nEmpty = Math.max(1, n - nEnemy - nLoot);

    if (nEnemy + nLoot > n) {
      const totalWant = nEnemy + nLoot;
      const scale = totalWant > 0 ? (n - 1) / totalWant : 0;
      nEnemy = Math.max(1, Math.round(nEnemy * scale));
      nLoot = Math.max(0, Math.round(nLoot * scale));
      nEmpty = n - nEnemy - nLoot;
    }

    let deck = [
      ...Array(nEnemy).fill('enemy'),
      ...Array(nLoot).fill('loot'),
      ...Array(nEmpty).fill('empty'),
    ];
    while (deck.length < n) deck.push('empty');
    deck = deck.slice(0, n);
    shuffle(deck, rng);

    // Proximity-aware swap: move enemy tokens out of safe zones
    const safeEnemyIndices = [];
    const farNonEnemyIndices = [];
    const remainingSorted = remaining.map((room, i) => [i, room])
      .sort((a, b) => {
        const dA = roomDistances[`${a[1].gridRow},${a[1].gridCol}`] || 99;
        const dB = roomDistances[`${b[1].gridRow},${b[1].gridCol}`] || 99;
        return dA - dB;
      });

    for (const [origIdx, room] of remainingSorted) {
      const key = `${room.gridRow},${room.gridCol}`;
      const override = proximityOverrides[key];
      if (override === 'safe' && deck[origIdx] === 'enemy') {
        safeEnemyIndices.push(origIdx);
      } else if (!override && deck[origIdx] !== 'enemy') {
        farNonEnemyIndices.push(origIdx);
      }
    }

    for (const safeIdx of safeEnemyIndices) {
      if (farNonEnemyIndices.length === 0) {
        deck[safeIdx] = 'loot';
      } else {
        const farIdx = farNonEnemyIndices.shift();
        [deck[safeIdx], deck[farIdx]] = [deck[farIdx], deck[safeIdx]];
      }
    }

    // Deal roles
    for (let i = 0; i < remaining.length; i++) {
      const key = `${remaining[i].gridRow},${remaining[i].gridCol}`;
      assignments.set(key, deck[i]);
    }
  }

  // Prison override
  for (const room of flexibleRooms) {
    const key = `${room.gridRow},${room.gridCol}`;
    if (assignments.get(key) === 'enemy' && room.maxEnemies >= 3) {
      if (rng() < prisonEnemyChance) assignments.set(key, 'prison');
    }
  }

  // ── Pass C2: Cluster smoothing ──
  const roomByKey = new Map();
  for (const room of flexibleRooms) {
    roomByKey.set(`${room.gridRow},${room.gridCol}`, room);
  }

  const smoothedKeys = new Set();
  const getAdjacentKeys = (gr, gc) => [
    `${gr - 1},${gc}`, `${gr + 1},${gc}`, `${gr},${gc - 1}`, `${gr},${gc + 1}`,
  ];

  for (let iter = 0; iter < flexibleRooms.length; iter++) {
    const visited = new Set();
    const clusters = [];

    for (const room of flexibleRooms) {
      const rk = `${room.gridRow},${room.gridCol}`;
      if (visited.has(rk) || assignments.get(rk) !== 'enemy') continue;

      const cluster = [];
      const queue = [room];
      while (queue.length) {
        const current = queue.shift();
        const ck = `${current.gridRow},${current.gridCol}`;
        if (visited.has(ck)) continue;
        visited.add(ck);
        if (assignments.get(ck) === 'enemy') {
          cluster.push(current);
          for (const adjKey of getAdjacentKeys(current.gridRow, current.gridCol)) {
            if (!visited.has(adjKey) && roomByKey.has(adjKey)) {
              queue.push(roomByKey.get(adjKey));
            }
          }
        }
      }
      if (cluster.length >= 2) clusters.push(cluster);
    }

    if (!clusters.length) break;

    for (const cluster of clusters) {
      cluster.sort((a, b) =>
        (roomDistances[`${a.gridRow},${a.gridCol}`] || 0) -
        (roomDistances[`${b.gridRow},${b.gridCol}`] || 0)
      );
      const target = cluster[0];
      const targetKey = `${target.gridRow},${target.gridCol}`;
      assignments.set(targetKey, 'loot');
      smoothedKeys.add(targetKey);
    }
  }

  // ── Phase 3: Place content tiles ──
  const decoratedRooms = [];

  for (const room of flexibleRooms) {
    const key = `${room.gridRow},${room.gridCol}`;
    const role = assignments.get(key) || 'empty';
    const startR = room.gridRow * MODULE_SIZE;
    const startC = room.gridCol * MODULE_SIZE;
    const placements = [];
    const roomTiles = room.variant.tiles || [];
    const availableSlots = sortSlotsForRole(room.slots, role, roomTiles, rng);

    if (role === 'boss') {
      const bossSlots = sortSlotsForRole(
        availableSlots.filter(s => s.types?.includes('boss')),
        'boss', roomTiles, rng,
      );
      if (bossSlots.length > 0) {
        const bs = bossSlots[0];
        placeTile(decoratedMap, startR + bs.y, startC + bs.x, 'B');
        placements.push({ x: startC + bs.x, y: startR + bs.y, type: 'B' });

        // PVPVE: 3 guards + 2 chests — sorted by priority
        const guardCandidates = sortSlotsForRole(
          availableSlots.filter(s => s !== bs && s.types?.includes('enemy')),
          'enemy', roomTiles, rng,
        );
        for (let i = 0; i < Math.min(3, guardCandidates.length); i++) {
          placeTile(decoratedMap, startR + guardCandidates[i].y, startC + guardCandidates[i].x, 'E');
          placements.push({ x: startC + guardCandidates[i].x, y: startR + guardCandidates[i].y, type: 'E' });
        }
        const placedPos = new Set(placements.map(p => `${p.x},${p.y}`));
        const chestSlots = sortSlotsForRole(
          availableSlots.filter(s =>
            s.types?.includes('loot') && !placedPos.has(`${startC + s.x},${startR + s.y}`)),
          'loot', roomTiles, rng,
        );
        for (let i = 0; i < Math.min(2, chestSlots.length); i++) {
          placeTile(decoratedMap, startR + chestSlots[i].y, startC + chestSlots[i].x, 'X');
          placements.push({ x: startC + chestSlots[i].x, y: startR + chestSlots[i].y, type: 'X' });
        }
      }
    } else if (role === 'spawn' || role.startsWith('spawn_')) {
      const spawnSlots = sortSlotsForRole(
        availableSlots.filter(s => s.types?.includes('spawn')),
        'spawn', roomTiles, rng,
      );
      for (let i = 0; i < Math.min(4, spawnSlots.length); i++) {
        placeTile(decoratedMap, startR + spawnSlots[i].y, startC + spawnSlots[i].x, 'S');
        placements.push({ x: startC + spawnSlots[i].x, y: startR + spawnSlots[i].y, type: 'S' });
      }
    } else if (role === 'enemy') {
      let effectiveMax = room.maxEnemies;
      if (proximityOverrides[key] === 'softened') {
        effectiveMax = Math.max(1, Math.floor(effectiveMax / 2));
      }
      const tier = difficultyTiers[key] || 'normal';
      const tierMax = getMaxEnemiesForTier(tier, room.maxEnemies);
      effectiveMax = proximityOverrides[key] === 'softened'
        ? Math.min(effectiveMax, tierMax)
        : tierMax;

      const enemySlots = sortSlotsForRole(
        availableSlots.filter(s => s.types?.includes('enemy')),
        'enemy', roomTiles, rng,
      );
      const count = Math.min(effectiveMax, enemySlots.length);
      const actualCount = count <= 2
        ? Math.max(1, Math.floor(rng() * count) + 1)
        : Math.max(2, Math.floor(rng() * count) + 1);
      for (let i = 0; i < Math.min(actualCount, enemySlots.length); i++) {
        placeTile(decoratedMap, startR + enemySlots[i].y, startC + enemySlots[i].x, 'E');
        placements.push({ x: startC + enemySlots[i].x, y: startR + enemySlots[i].y, type: 'E' });
      }
      if (config.scatterChests && rng() < 0.15) {
        const placedPos = new Set(placements.map(p => `${p.x},${p.y}`));
        const chestCandidates = sortSlotsForRole(
          availableSlots.filter(s =>
            s.types?.includes('loot') && !placedPos.has(`${startC + s.x},${startR + s.y}`)),
          'loot', roomTiles, rng,
        );
        if (chestCandidates.length > 0) {
          placeTile(decoratedMap, startR + chestCandidates[0].y, startC + chestCandidates[0].x, 'X');
          placements.push({ x: startC + chestCandidates[0].x, y: startR + chestCandidates[0].y, type: 'X' });
        }
      }
    } else if (role === 'loot') {
      const lootEligible = availableSlots.filter(s => s.types?.includes('loot'));
      const lootSlots = clusterLootSlots(lootEligible, roomTiles, rng);
      // PVPVE: cap to 1 chest per loot room for scarcity
      const count = Math.min(1, lootSlots.length);
      const actualCount = Math.max(1, count);
      for (let i = 0; i < Math.min(actualCount, lootSlots.length); i++) {
        placeTile(decoratedMap, startR + lootSlots[i].y, startC + lootSlots[i].x, 'X');
        placements.push({ x: startC + lootSlots[i].x, y: startR + lootSlots[i].y, type: 'X' });
      }
      if (config.scatterEnemies && rng() < 0.45) {
        const placedPos = new Set(placements.map(p => `${p.x},${p.y}`));
        const guardCandidates = sortSlotsForRole(
          availableSlots.filter(s =>
            s.types?.includes('enemy') && !placedPos.has(`${startC + s.x},${startR + s.y}`)),
          'enemy', roomTiles, rng,
        );
        if (guardCandidates.length > 0) {
          placeTile(decoratedMap, startR + guardCandidates[0].y, startC + guardCandidates[0].x, 'E');
          placements.push({ x: startC + guardCandidates[0].x, y: startR + guardCandidates[0].y, type: 'E' });
        }
      }
    } else if (role === 'shrine') {
      if (config.scatterChests && rng() < 0.2) {
        const lootSlots = sortSlotsForRole(
          availableSlots.filter(s => s.types?.includes('loot')),
          'loot', roomTiles, rng,
        );
        if (lootSlots.length > 0) {
          placeTile(decoratedMap, startR + lootSlots[0].y, startC + lootSlots[0].x, 'X');
          placements.push({ x: startC + lootSlots[0].x, y: startR + lootSlots[0].y, type: 'X' });
        }
      }
    } else if (role === 'library') {
      if (config.scatterChests && rng() < 0.25) {
        const lootSlots = sortSlotsForRole(
          availableSlots.filter(s => s.types?.includes('loot')),
          'loot', roomTiles, rng,
        );
        if (lootSlots.length > 0) {
          placeTile(decoratedMap, startR + lootSlots[0].y, startC + lootSlots[0].x, 'X');
          placements.push({ x: startC + lootSlots[0].x, y: startR + lootSlots[0].y, type: 'X' });
        }
      }
    } else if (role === 'prison') {
      const enemySlots = sortSlotsForRole(
        availableSlots.filter(s => s.types?.includes('enemy')),
        'enemy', roomTiles, rng,
      );
      const count = Math.min(room.maxEnemies, enemySlots.length);
      const actualCount = count > 0 ? Math.max(2, Math.floor(rng() * count) + 1) : 0;
      for (let i = 0; i < Math.min(actualCount, enemySlots.length); i++) {
        placeTile(decoratedMap, startR + enemySlots[i].y, startC + enemySlots[i].x, 'E');
        placements.push({ x: startC + enemySlots[i].x, y: startR + enemySlots[i].y, type: 'E' });
      }
    } else if (role === 'flooded') {
      if (config.scatterEnemies && rng() < 0.3) {
        const enemySlots = sortSlotsForRole(
          availableSlots.filter(s => s.types?.includes('enemy')),
          'enemy', roomTiles, rng,
        );
        if (enemySlots.length > 0) {
          placeTile(decoratedMap, startR + enemySlots[0].y, startC + enemySlots[0].x, 'E');
          placements.push({ x: startC + enemySlots[0].x, y: startR + enemySlots[0].y, type: 'E' });
        }
      }
    } else {
      // empty
      if (config.scatterEnemies && rng() < 0.25) {
        const enemySlots = sortSlotsForRole(
          availableSlots.filter(s => s.types?.includes('enemy')),
          'enemy', roomTiles, rng,
        );
        if (enemySlots.length > 0) {
          placeTile(decoratedMap, startR + enemySlots[0].y, startC + enemySlots[0].x, 'E');
          placements.push({ x: startC + enemySlots[0].x, y: startR + enemySlots[0].y, type: 'E' });
        }
      } else if (config.scatterChests && rng() < 0.05) {
        const lootSlots = availableSlots.filter(s => s.types?.includes('loot'));
        if (lootSlots.length > 0) {
          placeTile(decoratedMap, startR + lootSlots[0].y, startC + lootSlots[0].x, 'X');
          placements.push({ x: startC + lootSlots[0].x, y: startR + lootSlots[0].y, type: 'X' });
        }
      }
    }

    // Determine team from spawn role
    let team = null;
    if (role.startsWith('spawn_')) team = role.split('_')[1];

    decoratedRooms.push({
      id: `room_${room.gridRow}_${room.gridCol}`,
      gridRow: room.gridRow,
      gridCol: room.gridCol,
      role: role.startsWith('spawn_') ? 'spawn' : role,
      archetype: ['shrine', 'library', 'prison', 'flooded'].includes(role) ? role : null,
      bounds: {
        x_min: room.gridCol * MODULE_SIZE,
        y_min: room.gridRow * MODULE_SIZE,
        x_max: room.gridCol * MODULE_SIZE + MODULE_SIZE - 1,
        y_max: room.gridRow * MODULE_SIZE + MODULE_SIZE - 1,
      },
      team,
      difficultyTier: difficultyTiers[key] || 'normal',
      enemyCount: placements.filter(p => p.type === 'E').length,
      chestCount: placements.filter(p => p.type === 'X').length,
      placements,
      sourceName: room.variant.sourceName || room.variant.name || 'Unknown',
      clusterSmoothed: smoothedKeys.has(key),
      proximityOverride: proximityOverrides[key] || null,
    });
  }

  // ── Phase 4: Insert doors at module boundaries ──
  const decorationLookup = {};
  for (const room of decoratedRooms) {
    const key = `${room.gridRow},${room.gridCol}`;
    decorationLookup[key] = room.team ? `spawn_${room.team}` : room.role;
  }

  const doorResult = insertRoomDoors(decoratedMap, grid, variants, seed, null, decorationLookup);

  // ── Phase 5: Build spawn zone bounds ──
  const spawnZones = {};
  for (const [teamKey, room] of Object.entries(spawnRooms)) {
    spawnZones[teamKey] = {
      x_min: room.gridCol * MODULE_SIZE,
      y_min: room.gridRow * MODULE_SIZE,
      x_max: room.gridCol * MODULE_SIZE + MODULE_SIZE - 1,
      y_max: room.gridRow * MODULE_SIZE + MODULE_SIZE - 1,
    };
  }

  // ── Phase 6: Compute stats ──
  const roleCount = {};
  let enemiesPlaced = 0, chestsPlaced = 0, bossesPlaced = 0, spawnsPlaced = 0;
  for (const room of decoratedRooms) {
    const statRole = room.role;
    roleCount[statRole] = (roleCount[statRole] || 0) + 1;
    for (const p of room.placements) {
      if (p.type === 'E') enemiesPlaced++;
      else if (p.type === 'X') chestsPlaced++;
      else if (p.type === 'B') bossesPlaced++;
      else if (p.type === 'S') spawnsPlaced++;
    }
  }

  return {
    tileMap: decoratedMap,
    rooms: decoratedRooms,
    doors: doorResult.doors,
    spawnZones,
    bossRoom: bossRoom ? decoratedRooms.find(r =>
      r.gridRow === bossRoom.gridRow && r.gridCol === bossRoom.gridCol
    ) : null,
    difficultyTiers,
    stats: {
      flexibleRooms: flexibleRooms.length,
      fixedRooms: fixedRooms.length,
      roleCount,
      enemiesPlaced,
      chestsPlaced,
      bossesPlaced,
      spawnsPlaced,
      clustersSmoothed: smoothedKeys.size,
      ...doorResult.stats,
    },
  };
}
