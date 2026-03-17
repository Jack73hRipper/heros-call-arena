// ─────────────────────────────────────────────────────────
// tileProps.js — Procedural floor prop drawing system
//
// Renders small decorative objects on floor tiles, driven
// by room archetype and theme. All props are Canvas 2D
// drawn — no sprite files.
//
// Props are drawn ON TOP OF base floor tiles, BEFORE room
// archetype overlays. Each prop is a self-contained drawing
// function: (ctx, x, y, tileSize, seed, palette)
//
// Placement is deterministic via cellHash() — same grid
// position always gets the same prop.
// ─────────────────────────────────────────────────────────

import { cellHash, hexAlpha, shiftColor, lerpColor, hexToRgb, rgbToCSS } from './noiseUtils.js';

// ═══════════════════════════════════════════════════════════
//  PROP DRAWING FUNCTIONS (10 props)
// ═══════════════════════════════════════════════════════════

/**
 * Pillar — Full tile circle with shadow ring + highlight arc.
 * Used in boss rooms, corridors. Blocks top 60% of tile.
 */
function drawProp_pillar(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size / 2;
  const r = size * 0.28;

  // Shadow ring
  ctx.fillStyle = 'rgba(0,0,0,0.25)';
  ctx.beginPath();
  ctx.arc(cx + 1, cy + 1, r + 2, 0, Math.PI * 2);
  ctx.fill();

  // Pillar body
  ctx.fillStyle = lerpColor(palette.metal || palette.secondary, palette.highlight, 0.25);
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fill();

  // Highlight arc (top-left quarter)
  ctx.strokeStyle = hexAlpha(palette.highlight, 0.35);
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(cx, cy, r - 2, Math.PI * 1.1, Math.PI * 1.6);
  ctx.stroke();
}

/**
 * Rubble Pile — ~40% tile, 4-6 small overlapping rectangles.
 * Used in empty/abandoned rooms.
 */
function drawProp_rubble(ctx, x, y, size, seed, palette) {
  const h = cellHash;
  const rubbleColor = shiftColor(palette.secondary, -8);
  const count = 4 + Math.floor(h(seed, 0, 50) * 3); // 4-6 pieces

  // Shadow underneath
  ctx.fillStyle = 'rgba(0,0,0,0.12)';
  ctx.fillRect(x + size * 0.25, y + size * 0.6, size * 0.5, size * 0.15);

  for (let i = 0; i < count; i++) {
    const rx = x + size * 0.2 + h(seed, i, 51) * size * 0.4;
    const ry = y + size * 0.35 + h(seed, i, 52) * size * 0.3;
    const rw = 3 + h(seed, i, 53) * 6;
    const rh = 2 + h(seed, i, 54) * 4;
    ctx.fillStyle = shiftColor(rubbleColor, Math.floor((h(seed, i, 55) - 0.5) * 10));
    ctx.fillRect(rx, ry, rw, rh);
  }
}

/**
 * Brazier — ~30% tile, circle base + orange glow halo.
 * Used in enemy and boss rooms.
 */
function drawProp_brazier(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size * 0.45;

  // Glow halo (radial gradient)
  const grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, size * 0.4);
  grad.addColorStop(0, 'rgba(255, 160, 40, 0.15)');
  grad.addColorStop(1, 'rgba(255, 100, 20, 0)');
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.4, 0, Math.PI * 2);
  ctx.fill();

  // Base bowl
  ctx.fillStyle = shiftColor(palette.metal || palette.secondary, 5);
  ctx.beginPath();
  ctx.ellipse(cx, cy + 4, size * 0.1, size * 0.06, 0, 0, Math.PI * 2);
  ctx.fill();

  // Flame core
  ctx.fillStyle = 'rgba(255, 180, 50, 0.7)';
  ctx.beginPath();
  ctx.arc(cx, cy, 3, 0, Math.PI * 2);
  ctx.fill();

  // Flame outer
  ctx.fillStyle = 'rgba(255, 120, 30, 0.35)';
  ctx.beginPath();
  ctx.arc(cx, cy - 1, 5, 0, Math.PI * 2);
  ctx.fill();
}

/**
 * Coffin — ~70% tile, oblong rectangle with lid line.
 * Theme affinity: Catacombs, Ossuary.
 */
function drawProp_coffin(ctx, x, y, size, seed, palette) {
  const cx = x + size * 0.15;
  const cy = y + size * 0.2;
  const cw = size * 0.7;
  const ch = size * 0.6;

  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.15)';
  ctx.fillRect(cx + 2, cy + 2, cw, ch);

  // Coffin body
  ctx.fillStyle = palette.furniture || shiftColor(palette.secondary, -5);
  ctx.fillRect(cx, cy, cw, ch);

  // Lid line (horizontal midline)
  ctx.strokeStyle = shiftColor(palette.furniture || palette.secondary, -8);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(cx, cy + ch * 0.45);
  ctx.lineTo(cx + cw, cy + ch * 0.45);
  ctx.stroke();

  // Edge border
  ctx.strokeStyle = shiftColor(palette.furniture || palette.secondary, -12);
  ctx.lineWidth = 0.8;
  ctx.strokeRect(cx, cy, cw, ch);

  // Top taper (coffin narrows at head)
  ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, -5);
  ctx.beginPath();
  ctx.moveTo(cx + 2, cy);
  ctx.lineTo(cx + cw - 2, cy);
  ctx.lineTo(cx + cw, cy + ch * 0.15);
  ctx.lineTo(cx, cy + ch * 0.15);
  ctx.closePath();
  ctx.fill();
}

/**
 * Bookshelf — Wall-adjacent tall rectangle with shelf lines.
 * Theme affinity: Vault, Cathedral.
 */
function drawProp_bookshelf(ctx, x, y, size, seed, palette) {
  const bx = x + size * 0.1;
  const by = y + size * 0.05;
  const bw = size * 0.8;
  const bh = size * 0.85;

  // Shelf frame
  ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, 5);
  ctx.fillRect(bx, by, bw, bh);

  // Border
  ctx.strokeStyle = shiftColor(palette.furniture || palette.secondary, -8);
  ctx.lineWidth = 1;
  ctx.strokeRect(bx, by, bw, bh);

  // 3-4 horizontal shelf lines
  const shelves = 4;
  const shelfH = bh / shelves;
  for (let i = 1; i < shelves; i++) {
    const sy = by + i * shelfH;
    ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, -4);
    ctx.fillRect(bx + 1, sy, bw - 2, 1);
  }

  // Book spines (tiny vertical rects on each shelf)
  const h = cellHash;
  for (let shelf = 0; shelf < shelves; shelf++) {
    const sy = by + shelf * shelfH + 2;
    const bookCount = 3 + Math.floor(h(seed, shelf, 60) * 3);
    for (let b = 0; b < bookCount; b++) {
      const bookX = bx + 3 + b * ((bw - 6) / bookCount);
      const bookW = 2 + h(seed, shelf * 10 + b, 61) * 3;
      const bookH = shelfH - 4;
      const variant = h(seed, shelf * 10 + b, 62);
      ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, Math.floor((variant - 0.5) * 20));
      ctx.fillRect(bookX, sy, bookW, bookH);
    }
  }
}

/**
 * Altar — ~50% tile, rectangle base with accent top + center gem.
 * Theme affinity: Boss rooms.
 */
function drawProp_altar(ctx, x, y, size, seed, palette) {
  const ax = x + size * 0.2;
  const ay = y + size * 0.3;
  const aw = size * 0.6;
  const ah = size * 0.4;

  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.15)';
  ctx.fillRect(ax + 2, ay + 2, aw, ah);

  // Base stone
  ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, 5);
  ctx.fillRect(ax, ay, aw, ah);

  // Accent-colored top surface
  ctx.fillStyle = hexAlpha(palette.accent, 0.5);
  ctx.fillRect(ax + 2, ay + 2, aw - 4, ah * 0.3);

  // Border
  ctx.strokeStyle = shiftColor(palette.furniture || palette.secondary, -10);
  ctx.lineWidth = 1;
  ctx.strokeRect(ax, ay, aw, ah);

  // Center gemstone dot
  ctx.fillStyle = hexAlpha(palette.highlight, 0.7);
  ctx.beginPath();
  ctx.arc(ax + aw / 2, ay + ah * 0.5, 2.5, 0, Math.PI * 2);
  ctx.fill();

  // Gem glow
  ctx.fillStyle = hexAlpha(palette.highlight, 0.15);
  ctx.beginPath();
  ctx.arc(ax + aw / 2, ay + ah * 0.5, 6, 0, Math.PI * 2);
  ctx.fill();
}

/**
 * Puddle — ~40% tile, irregular semi-transparent blue ellipse.
 * Theme affinity: Drowned Sanctum.
 */
function drawProp_puddle(ctx, x, y, size, seed, palette) {
  const cx = x + size * 0.45 + cellHash(seed, 0, 70) * size * 0.1;
  const cy = y + size * 0.5 + cellHash(seed, 0, 71) * size * 0.1;
  const rx = size * 0.18 + cellHash(seed, 0, 72) * size * 0.08;
  const ry = size * 0.12 + cellHash(seed, 0, 73) * size * 0.06;

  // Water body
  ctx.fillStyle = 'rgba(20, 60, 80, 0.15)';
  ctx.beginPath();
  ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  ctx.fill();

  // Highlight edge (reflection)
  ctx.strokeStyle = 'rgba(100, 180, 220, 0.12)';
  ctx.lineWidth = 0.8;
  ctx.beginPath();
  ctx.ellipse(cx - 1, cy - 1, rx * 0.7, ry * 0.7, 0, Math.PI * 0.8, Math.PI * 1.4);
  ctx.stroke();
}

/**
 * Barrel — ~25% tile, small circle with cross-line top.
 * Theme affinity: Cellar, Loot rooms.
 */
function drawProp_barrel(ctx, x, y, size, seed, palette) {
  const cx = x + size * 0.5;
  const cy = y + size * 0.5;
  const r = size * 0.12;

  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.15)';
  ctx.beginPath();
  ctx.ellipse(cx + 1, cy + 2, r + 1, r * 0.7 + 1, 0, 0, Math.PI * 2);
  ctx.fill();

  // Barrel body (brown circle)
  ctx.fillStyle = lerpColor(palette.furniture || palette.secondary, '#5C3310', 0.5);
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fill();

  // Barrel rim
  ctx.strokeStyle = lerpColor(palette.furniture || palette.secondary, '#3A1F08', 0.5);
  ctx.lineWidth = 0.8;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.stroke();

  // Cross-line top
  ctx.strokeStyle = shiftColor(palette.metal || palette.secondary, -5);
  ctx.lineWidth = 0.6;
  ctx.beginPath();
  ctx.moveTo(cx - r * 0.7, cy);
  ctx.lineTo(cx + r * 0.7, cy);
  ctx.moveTo(cx, cy - r * 0.7);
  ctx.lineTo(cx, cy + r * 0.7);
  ctx.stroke();
}

/**
 * Chains — Wall-adjacent, 2-3 thin vertical lines dangling from top.
 * Theme affinity: Iron Depths, Catacombs.
 */
function drawProp_chains(ctx, x, y, size, seed, palette) {
  const h = cellHash;
  const chainColor = shiftColor(palette.metal || palette.secondary, 5);
  const count = 2 + Math.floor(h(seed, 0, 80) * 2); // 2-3 chains

  for (let i = 0; i < count; i++) {
    const cx = x + size * 0.2 + (i / (count - 1 || 1)) * size * 0.6;
    const chainLen = size * 0.4 + h(seed, i, 81) * size * 0.3;

    ctx.strokeStyle = chainColor;
    ctx.lineWidth = 1;

    // Chain links (alternating small segments)
    for (let ly = 0; ly < chainLen; ly += 4) {
      const linkX = cx + ((ly / 4) % 2 === 0 ? -0.5 : 0.5);
      ctx.beginPath();
      ctx.moveTo(linkX, y + ly);
      ctx.lineTo(linkX, y + Math.min(ly + 3, chainLen));
      ctx.stroke();
    }
  }
}

/**
 * Banner — Wall-adjacent, narrow rectangle hanging from top, tattered bottom.
 * Theme affinity: Cathedral, Boss rooms.
 */
function drawProp_banner(ctx, x, y, size, seed, palette) {
  const bx = x + size * 0.35;
  const by = y + 2;
  const bw = size * 0.3;
  const bh = size * 0.6;

  // Banner rod at top
  ctx.fillStyle = shiftColor(palette.metal || palette.secondary, 5);
  ctx.fillRect(bx - 2, by, bw + 4, 2);

  // Banner fabric
  ctx.fillStyle = hexAlpha(palette.accent, 0.6);
  ctx.fillRect(bx, by + 2, bw, bh - 8);

  // Tattered bottom (zigzag)
  ctx.fillStyle = hexAlpha(palette.accent, 0.6);
  ctx.beginPath();
  ctx.moveTo(bx, by + bh - 8);
  const teeth = 3;
  const toothW = bw / teeth;
  for (let t = 0; t < teeth; t++) {
    ctx.lineTo(bx + t * toothW + toothW / 2, by + bh);
    ctx.lineTo(bx + (t + 1) * toothW, by + bh - 8);
  }
  ctx.closePath();
  ctx.fill();

  // Center stripe
  ctx.fillStyle = hexAlpha(palette.highlight, 0.2);
  ctx.fillRect(bx + bw * 0.35, by + 4, bw * 0.3, bh - 14);
}

// ═══════════════════════════════════════════════════════════
//  PROP DISPATCH MAP
// ═══════════════════════════════════════════════════════════

const PROP_DRAW_MAP = {
  pillar:    drawProp_pillar,
  rubble:    drawProp_rubble,
  brazier:   drawProp_brazier,
  coffin:    drawProp_coffin,
  bookshelf: drawProp_bookshelf,
  altar:     drawProp_altar,
  puddle:    drawProp_puddle,
  barrel:    drawProp_barrel,
  chains:    drawProp_chains,
  banner:    drawProp_banner,
};

/**
 * Draw a single prop by name at a tile position.
 * @param {CanvasRenderingContext2D} ctx
 * @param {string} propName - Key from PROP_DRAW_MAP
 * @param {number} x - Pixel X of tile
 * @param {number} y - Pixel Y of tile
 * @param {number} tileSize - Tile size in px
 * @param {number} seed - Deterministic seed for variation
 * @param {Object} palette - Theme palette object
 */
export function drawTileProp(ctx, propName, x, y, tileSize, seed, palette) {
  const fn = PROP_DRAW_MAP[propName];
  if (fn) fn(ctx, x, y, tileSize, seed, palette);
}

// ═══════════════════════════════════════════════════════════
//  ARCHETYPE PROP SLOTS
// ═══════════════════════════════════════════════════════════

/**
 * Defines prop placement rules per room archetype.
 * Each slot: { prop, position, chance }
 *   - prop: name from PROP_DRAW_MAP
 *   - position: 'center' | 'corners' | 'wall_left' | 'wall_right' |
 *               'wall_top' | 'wall_bottom' | 'random_floor' | 'flanking_center'
 *   - chance: 0-1 probability this slot is filled (deterministic via hash)
 */
export const ARCHETYPE_PROP_SLOTS = {
  boss: [
    { prop: 'altar',   position: 'center',          chance: 0.9 },
    { prop: 'pillar',  position: 'corners',          chance: 0.8 },
    { prop: 'brazier', position: 'flanking_center',  chance: 0.7 },
    { prop: 'banner',  position: 'wall_top',         chance: 0.5 },
  ],
  enemy: [
    { prop: 'brazier', position: 'wall_left',        chance: 0.7 },
    { prop: 'brazier', position: 'wall_right',       chance: 0.7 },
    { prop: 'chains',  position: 'wall_top',         chance: 0.4 },
    { prop: 'rubble',  position: 'random_floor',     chance: 0.3 },
  ],
  loot: [
    { prop: 'barrel',  position: 'corners',          chance: 0.6 },
    { prop: 'barrel',  position: 'random_floor',     chance: 0.4 },
    { prop: 'brazier', position: 'wall_left',        chance: 0.3 },
  ],
  spawn: [
    { prop: 'banner',  position: 'wall_top',         chance: 0.5 },
    { prop: 'brazier', position: 'flanking_center',  chance: 0.4 },
  ],
  empty: [
    { prop: 'rubble',  position: 'random_floor',     chance: 0.5 },
    { prop: 'rubble',  position: 'corners',          chance: 0.3 },
    { prop: 'chains',  position: 'wall_left',        chance: 0.2 },
  ],
  stairs: [
    { prop: 'pillar',  position: 'wall_left',        chance: 0.4 },
    { prop: 'pillar',  position: 'wall_right',       chance: 0.4 },
  ],
  shrine: [
    { prop: 'altar',   position: 'center',           chance: 1.0 },
    { prop: 'brazier', position: 'flanking_center',   chance: 0.9 },
    { prop: 'banner',  position: 'wall_top',          chance: 0.6 },
  ],
  library: [
    { prop: 'bookshelf', position: 'wall_top',        chance: 0.8 },
    { prop: 'bookshelf', position: 'wall_bottom',     chance: 0.8 },
    { prop: 'bookshelf', position: 'wall_left',       chance: 0.6 },
    { prop: 'bookshelf', position: 'wall_right',      chance: 0.6 },
  ],
  prison: [
    { prop: 'chains',  position: 'wall_left',         chance: 0.8 },
    { prop: 'chains',  position: 'wall_right',        chance: 0.8 },
    { prop: 'chains',  position: 'wall_top',          chance: 0.4 },
  ],
  flooded: [
    { prop: 'puddle',  position: 'random_floor',      chance: 0.9 },
    { prop: 'puddle',  position: 'center',            chance: 0.7 },
    { prop: 'puddle',  position: 'corners',           chance: 0.3 },
  ],
};

// ═══════════════════════════════════════════════════════════
//  PROP PLACEMENT ENGINE
// ═══════════════════════════════════════════════════════════

/**
 * Resolve a position keyword into actual tile coordinates within a room.
 * Returns an array of { x, y } in room-grid coordinates.
 *
 * @param {string} position - Position keyword
 * @param {Object} bounds - { x_min, y_min, x_max, y_max } inner floor area
 * @param {number} seed - Room seed for deterministic random placement
 * @returns {Array<{x: number, y: number}>}
 */
function _resolvePosition(position, bounds, seed) {
  const { x_min, y_min, x_max, y_max } = bounds;
  const floorW = x_max - x_min + 1;
  const floorH = y_max - y_min + 1;
  const midX = Math.floor((x_min + x_max) / 2);
  const midY = Math.floor((y_min + y_max) / 2);

  switch (position) {
    case 'center':
      return [{ x: midX, y: midY }];

    case 'corners':
      return [
        { x: x_min, y: y_min },
        { x: x_max, y: y_min },
        { x: x_min, y: y_max },
        { x: x_max, y: y_max },
      ];

    case 'flanking_center':
      return [
        { x: midX - 1, y: midY },
        { x: midX + 1, y: midY },
      ];

    case 'wall_left':
      // One tile along the left interior edge
      return [{ x: x_min, y: midY }];

    case 'wall_right':
      return [{ x: x_max, y: midY }];

    case 'wall_top': {
      // Every other tile along the top interior edge
      const tiles = [];
      for (let tx = x_min + 1; tx < x_max; tx += 2) {
        tiles.push({ x: tx, y: y_min });
      }
      return tiles;
    }

    case 'wall_bottom': {
      const tiles = [];
      for (let tx = x_min + 1; tx < x_max; tx += 2) {
        tiles.push({ x: tx, y: y_max });
      }
      return tiles;
    }

    case 'random_floor': {
      // 1-2 random floor positions (deterministic)
      const count = 1 + Math.floor(cellHash(seed, 0, 90) * 2);
      const tiles = [];
      for (let i = 0; i < count; i++) {
        const rx = x_min + Math.floor(cellHash(seed, i, 91) * floorW);
        const ry = y_min + Math.floor(cellHash(seed, i, 92) * floorH);
        tiles.push({ x: rx, y: ry });
      }
      return tiles;
    }

    default:
      return [];
  }
}

/**
 * Draw all props for a room based on its archetype and theme.
 *
 * Call this AFTER base floor tiles are drawn, BEFORE room archetype overlay.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Object} opts
 * @param {string} opts.archetype - Room archetype key
 * @param {Object} opts.theme - Full theme config (must have propAffinities)
 * @param {number} opts.tileSize
 * @param {number} opts.roomOffsetX - Pixel offset of dungeon grid origin
 * @param {number} opts.roomOffsetY - Pixel offset of dungeon grid origin
 * @param {Object} opts.bounds - { x_min, y_min, x_max, y_max } inner floor area
 * @param {number} opts.seed - Room seed
 */
export function drawRoomProps(ctx, opts) {
  const { archetype, theme, tileSize, roomOffsetX, roomOffsetY, bounds, seed } = opts;

  const slots = ARCHETYPE_PROP_SLOTS[archetype];
  if (!slots) return;

  const affinities = theme.propAffinities || {};

  for (let i = 0; i < slots.length; i++) {
    const slot = slots[i];

    // Check theme affinity — skip if theme has 0 or no affinity for this prop
    const affinity = affinities[slot.prop];
    if (affinity === undefined || affinity <= 0) continue;

    // Combined chance: slot.chance × theme affinity
    const effectiveChance = slot.chance * affinity;
    const roll = cellHash(seed, i, 100);
    if (roll >= effectiveChance) continue;

    // Resolve positions for this slot
    const positions = _resolvePosition(slot.position, bounds, seed + i * 13);

    for (const pos of positions) {
      const px = roomOffsetX + pos.x * tileSize;
      const py = roomOffsetY + pos.y * tileSize;
      const tileSeed = cellHash(pos.x, pos.y, seed);
      drawTileProp(ctx, slot.prop, px, py, tileSize, tileSeed, theme.palette);
    }
  }
}

export { PROP_DRAW_MAP };
