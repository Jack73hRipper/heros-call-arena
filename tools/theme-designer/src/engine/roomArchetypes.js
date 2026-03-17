// ─────────────────────────────────────────────────────────
// roomArchetypes.js — Room-level visual overlay system
//
// Defines visual archetypes for dungeon rooms based on their
// purpose. Each archetype draws deliberate, symmetrical,
// purpose-driven decorations on top of base tiles.
//
// Design principles:
//   1. Symmetry — pillars in all 4 corners, torches in pairs
//   2. Room-coherent — entire room shares palette shift
//   3. Purpose-driven — boss room looks different from loot room
//   4. Positional logic — decorations go where they make sense
//   5. Sparing — most tiles unchanged; 5-8 touches per room
//
// Usage:
//   drawRoomOverlay(ctx, {
//     archetype: 'boss',
//     theme, tileSize, roomOffsetX, roomOffsetY,
//     roomWidth, roomHeight, bounds, doorPositions, seed
//   });
// ─────────────────────────────────────────────────────────

import { cellHash, hexAlpha, shiftColor, lerpColor, hexToRgb, rgbToCSS } from './noiseUtils.js';
import { drawRoomProps } from './tileProps.js';

// ═══════════════════════════════════════════════════════════
//  ARCHETYPE DEFINITIONS
// ═══════════════════════════════════════════════════════════

export const ROOM_ARCHETYPES = {
  boss: {
    label: 'Sanctum (Boss)',
    description: 'Corner pillars, center sigil, grander palette. Signals a powerful guardian.',
  },
  enemy: {
    label: 'Barracks (Enemy)',
    description: 'Wall brackets, paired torches, worn floor path between doors.',
  },
  loot: {
    label: 'Vault (Loot)',
    description: 'Wall alcoves, polished floor, corner ornaments. A maintained treasury.',
  },
  spawn: {
    label: 'Entry Hall (Spawn)',
    description: 'Archway highlights, arrival circle, warmer palette. The safe room.',
  },
  empty: {
    label: 'Abandoned (Empty)',
    description: 'Dimmer palette, corner rubble, wider grout. A neglected passage.',
  },
  stairs: {
    label: 'Stairwell (Stairs)',
    description: 'Concentric floor borders, vertical wall streaks. Descent ahead.',
  },
  shrine: {
    label: 'Sacred Shrine',
    description: 'Central altar, flanking braziers, accent floor border. A consecrated space.',
  },
  library: {
    label: 'Archive (Library)',
    description: 'Wall-hugging bookshelves, lighter maintained floor. Scholarly and orderly.',
  },
  prison: {
    label: 'Prison / Cage',
    description: 'Iron bars across doorways, chain props, dark oppressive floor.',
  },
  flooded: {
    label: 'Flooded Chamber',
    description: 'Water tint, scattered puddles, reflective edges. Eerie and inhospitable.',
  },
};

// ═══════════════════════════════════════════════════════════
//  MAIN OVERLAY DISPATCHER
// ═══════════════════════════════════════════════════════════

/**
 * Draw a room archetype overlay on top of already-rendered base tiles.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {Object} opts
 * @param {string} opts.archetype - 'boss'|'enemy'|'loot'|'spawn'|'empty'|'stairs'
 * @param {Object} opts.theme - Full theme config object
 * @param {number} opts.tileSize
 * @param {number} opts.roomOffsetX - Pixel offset of room's top-left
 * @param {number} opts.roomOffsetY - Pixel offset of room's top-left
 * @param {number} opts.roomWidth - Room width in tiles (including walls)
 * @param {number} opts.roomHeight - Room height in tiles (including walls)
 * @param {Object} opts.bounds - { x_min, y_min, x_max, y_max } inner floor area
 * @param {Array}  opts.doorPositions - [{ x, y }] door tile coords (room-local)
 * @param {number} opts.seed
 */
export function drawRoomOverlay(ctx, opts) {
  const { archetype } = opts;

  // Draw procedural floor props BEFORE archetype overlay
  drawRoomProps(ctx, opts);

  switch (archetype) {
    case 'boss':    return _drawBossOverlay(ctx, opts);
    case 'enemy':   return _drawEnemyOverlay(ctx, opts);
    case 'loot':    return _drawLootOverlay(ctx, opts);
    case 'spawn':   return _drawSpawnOverlay(ctx, opts);
    case 'empty':   return _drawEmptyOverlay(ctx, opts);
    case 'stairs':  return _drawStairsOverlay(ctx, opts);
    case 'shrine':  return _drawShrineOverlay(ctx, opts);
    case 'library': return _drawLibraryOverlay(ctx, opts);
    case 'prison':  return _drawPrisonOverlay(ctx, opts);
    case 'flooded': return _drawFloodedOverlay(ctx, opts);
  }
}

// ═══════════════════════════════════════════════════════════
//  BOSS — Sanctum / Throne Room
// ═══════════════════════════════════════════════════════════

function _drawBossOverlay(ctx, opts) {
  const { theme, tileSize: s, roomOffsetX: ox, roomOffsetY: oy, bounds, seed } = opts;
  const pal = theme.palette;

  // 1. Palette shift — slightly grander (lighter walls)
  const innerX = bounds.x_min * s + ox;
  const innerY = bounds.y_min * s + oy;
  const innerW = (bounds.x_max - bounds.x_min + 1) * s;
  const innerH = (bounds.y_max - bounds.y_min + 1) * s;
  ctx.fillStyle = hexAlpha(pal.highlight, 0.04);
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2. Four corner pillars — identical, symmetrical
  const corners = [
    { x: bounds.x_min, y: bounds.y_min },
    { x: bounds.x_max, y: bounds.y_min },
    { x: bounds.x_min, y: bounds.y_max },
    { x: bounds.x_max, y: bounds.y_max },
  ];
  const pillarColor = lerpColor(pal.metal || pal.secondary, pal.highlight, 0.3);
  const pillarShadow = shiftColor(pal.primary, -10);
  for (const c of corners) {
    const px = ox + c.x * s;
    const py = oy + c.y * s;
    const r = s * 0.28;
    // Shadow
    ctx.fillStyle = pillarShadow;
    ctx.beginPath();
    ctx.arc(px + s / 2 + 1, py + s / 2 + 1, r + 1, 0, Math.PI * 2);
    ctx.fill();
    // Pillar body
    ctx.fillStyle = pillarColor;
    ctx.beginPath();
    ctx.arc(px + s / 2, py + s / 2, r, 0, Math.PI * 2);
    ctx.fill();
    // Highlight ring
    ctx.strokeStyle = hexAlpha(pal.highlight, 0.35);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(px + s / 2, py + s / 2, r - 2, 0, Math.PI * 2);
    ctx.stroke();
  }

  // 3. Center floor sigil — geometric pattern
  const cx = ox + ((bounds.x_min + bounds.x_max + 1) / 2) * s;
  const cy = oy + ((bounds.y_min + bounds.y_max + 1) / 2) * s;
  const sigilR = s * 1.2;

  // Outer circle
  ctx.strokeStyle = hexAlpha(pal.accent, 0.25);
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(cx, cy, sigilR, 0, Math.PI * 2);
  ctx.stroke();

  // Inner diamond
  ctx.strokeStyle = hexAlpha(pal.highlight, 0.20);
  ctx.lineWidth = 1;
  ctx.beginPath();
  const dr = sigilR * 0.65;
  ctx.moveTo(cx, cy - dr);
  ctx.lineTo(cx + dr, cy);
  ctx.lineTo(cx, cy + dr);
  ctx.lineTo(cx - dr, cy);
  ctx.closePath();
  ctx.stroke();

  // Center dot
  ctx.fillStyle = hexAlpha(pal.highlight, 0.30);
  ctx.beginPath();
  ctx.arc(cx, cy, 3, 0, Math.PI * 2);
  ctx.fill();

  // 4. Wall trim line along bottom of wall tiles (top/bottom inner edges)
  ctx.fillStyle = hexAlpha(pal.highlight, 0.15);
  // Top wall trim
  ctx.fillRect(innerX + s * 0.5, innerY - 2, innerW - s, 2);
  // Bottom wall trim
  ctx.fillRect(innerX + s * 0.5, innerY + innerH, innerW - s, 2);
}

// ═══════════════════════════════════════════════════════════
//  ENEMY — Barracks / Garrison
// ═══════════════════════════════════════════════════════════

function _drawEnemyOverlay(ctx, opts) {
  const { theme, tileSize: s, roomOffsetX: ox, roomOffsetY: oy, bounds, doorPositions, seed } = opts;
  const pal = theme.palette;

  const innerX = bounds.x_min * s + ox;
  const innerY = bounds.y_min * s + oy;
  const innerW = (bounds.x_max - bounds.x_min + 1) * s;
  const innerH = (bounds.y_max - bounds.y_min + 1) * s;

  // 1. Paired torches on left and right walls — symmetrical
  const midY = Math.floor((bounds.y_min + bounds.y_max) / 2);
  const torchPositions = [
    { x: bounds.x_min, y: midY },     // Left wall
    { x: bounds.x_max, y: midY },     // Right wall
  ];
  for (const t of torchPositions) {
    const px = ox + t.x * s;
    const py = oy + t.y * s;

    // Torch glow radius (on the floor side)
    const glowX = t.x === bounds.x_min ? px + s : px;
    ctx.fillStyle = hexAlpha(pal.highlight, 0.06);
    ctx.beginPath();
    ctx.arc(glowX, py + s / 2, s * 1.5, 0, Math.PI * 2);
    ctx.fill();

    // Bracket on wall
    const bx = t.x === bounds.x_min ? px + s - 6 : px + 2;
    ctx.fillStyle = shiftColor(pal.metal || pal.secondary, 10);
    ctx.fillRect(bx, py + s * 0.3, 4, s * 0.4);

    // Flame
    const fx = t.x === bounds.x_min ? px + s - 4 : px + 4;
    ctx.fillStyle = hexAlpha(pal.highlight, 0.7);
    ctx.beginPath();
    ctx.arc(fx, py + s * 0.28, 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = hexAlpha(pal.accent, 0.4);
    ctx.beginPath();
    ctx.arc(fx, py + s * 0.28, 5, 0, Math.PI * 2);
    ctx.fill();
  }

  // 2. Wall-adjacent floor trim — weapon rack lines along top and bottom walls
  const rackColor = shiftColor(pal.metal || pal.secondary, 5);
  // Top inner edge
  for (let x = bounds.x_min + 1; x < bounds.x_max; x++) {
    const px = ox + x * s;
    const py = oy + bounds.y_min * s;
    ctx.fillStyle = rackColor;
    ctx.fillRect(px + 4, py + 2, s - 8, 3);
    ctx.fillStyle = shiftColor(pal.metal || pal.secondary, 12);
    ctx.fillRect(px + 4, py + 2, s - 8, 1);
    // Vertical pegs (evenly spaced)
    for (let p = 0; p < 3; p++) {
      const pegX = px + 8 + p * ((s - 16) / 2);
      ctx.fillStyle = shiftColor(pal.metal || pal.secondary, 8);
      ctx.fillRect(pegX, py + 5, 2, 4);
    }
  }

  // 3. Worn path between doors — darker floor stripe
  if (doorPositions && doorPositions.length > 0) {
    const door = doorPositions[0];
    // Draw a path from the door straight into the room center
    const pathStartY = Math.max(bounds.y_min, door.y + 1);
    const pathEndY = Math.floor((bounds.y_min + bounds.y_max) / 2);
    const pathX = door.x;
    for (let y = pathStartY; y <= pathEndY; y++) {
      const px = ox + pathX * s;
      const py = oy + y * s;
      ctx.fillStyle = 'rgba(0,0,0,0.08)';
      ctx.fillRect(px + s * 0.15, py, s * 0.7, s);
    }
  }
}

// ═══════════════════════════════════════════════════════════
//  LOOT — Vault / Treasury
// ═══════════════════════════════════════════════════════════

function _drawLootOverlay(ctx, opts) {
  const { theme, tileSize: s, roomOffsetX: ox, roomOffsetY: oy, bounds, seed } = opts;
  const pal = theme.palette;

  const innerX = bounds.x_min * s + ox;
  const innerY = bounds.y_min * s + oy;
  const innerW = (bounds.x_max - bounds.x_min + 1) * s;
  const innerH = (bounds.y_max - bounds.y_min + 1) * s;

  // 1. Polished floor — slight reflective sheen over entire room
  ctx.fillStyle = hexAlpha(pal.highlight, 0.03);
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2. Wall alcoves — uniform recesses along left and right walls
  const alcoveColor = shiftColor(pal.primary, -5);
  const alcoveHighlight = shiftColor(pal.secondary, 8);
  for (let y = bounds.y_min + 1; y < bounds.y_max; y++) {
    // Left wall alcoves
    const lx = ox + bounds.x_min * s;
    const ly = oy + y * s;
    ctx.fillStyle = alcoveColor;
    ctx.fillRect(lx + 2, ly + 6, 6, s - 12);
    ctx.strokeStyle = alcoveHighlight;
    ctx.lineWidth = 0.5;
    ctx.strokeRect(lx + 2, ly + 6, 6, s - 12);

    // Right wall alcoves
    const rx = ox + bounds.x_max * s;
    ctx.fillStyle = alcoveColor;
    ctx.fillRect(rx + s - 8, ly + 6, 6, s - 12);
    ctx.strokeStyle = alcoveHighlight;
    ctx.strokeRect(rx + s - 8, ly + 6, 6, s - 12);
  }

  // 3. Four corner ornaments — matching filigree marks
  const corners = [
    { x: bounds.x_min, y: bounds.y_min, sx:  1, sy:  1 },
    { x: bounds.x_max, y: bounds.y_min, sx: -1, sy:  1 },
    { x: bounds.x_min, y: bounds.y_max, sx:  1, sy: -1 },
    { x: bounds.x_max, y: bounds.y_max, sx: -1, sy: -1 },
  ];
  ctx.strokeStyle = hexAlpha(pal.highlight, 0.30);
  ctx.lineWidth = 1;
  for (const c of corners) {
    const px = ox + c.x * s + s / 2;
    const py = oy + c.y * s + s / 2;
    // L-shaped corner filigree
    ctx.beginPath();
    ctx.moveTo(px, py + c.sy * 8);
    ctx.lineTo(px, py);
    ctx.lineTo(px + c.sx * 8, py);
    ctx.stroke();
    // Dot at corner
    ctx.fillStyle = hexAlpha(pal.highlight, 0.25);
    ctx.beginPath();
    ctx.arc(px, py, 2, 0, Math.PI * 2);
    ctx.fill();
  }

  // 4. Floor border — thin inset line around the room interior
  ctx.strokeStyle = hexAlpha(pal.highlight, 0.12);
  ctx.lineWidth = 1;
  ctx.strokeRect(innerX + s * 0.3, innerY + s * 0.3, innerW - s * 0.6, innerH - s * 0.6);
}

// ═══════════════════════════════════════════════════════════
//  SPAWN — Entry Hall
// ═══════════════════════════════════════════════════════════

function _drawSpawnOverlay(ctx, opts) {
  const { theme, tileSize: s, roomOffsetX: ox, roomOffsetY: oy, bounds, doorPositions, seed } = opts;
  const pal = theme.palette;

  const innerX = bounds.x_min * s + ox;
  const innerY = bounds.y_min * s + oy;
  const innerW = (bounds.x_max - bounds.x_min + 1) * s;
  const innerH = (bounds.y_max - bounds.y_min + 1) * s;

  // 1. Warmer palette — subtle warm tint over entire room
  ctx.fillStyle = 'rgba(60, 40, 20, 0.04)';
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2. Archway highlights flanking doors
  if (doorPositions && doorPositions.length > 0) {
    for (const door of doorPositions) {
      const dx = ox + door.x * s;
      const dy = oy + door.y * s;
      // Two flanking columns beside the door
      const flankL = dx - s * 0.1;
      const flankR = dx + s + s * 0.1 - 6;

      ctx.fillStyle = lerpColor(pal.secondary, pal.highlight, 0.25);
      // Left flank
      ctx.fillRect(flankL - 2, dy + 2, 6, s - 4);
      ctx.fillStyle = hexAlpha(pal.highlight, 0.15);
      ctx.fillRect(flankL - 2, dy + 2, 6, 2);
      // Right flank
      ctx.fillStyle = lerpColor(pal.secondary, pal.highlight, 0.25);
      ctx.fillRect(flankR, dy + 2, 6, s - 4);
      ctx.fillStyle = hexAlpha(pal.highlight, 0.15);
      ctx.fillRect(flankR, dy + 2, 6, 2);

      // Arch top connecting the flanks
      ctx.strokeStyle = hexAlpha(pal.highlight, 0.18);
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(flankL, dy + 4);
      ctx.quadraticCurveTo(dx + s / 2, dy - 6, flankR + 6, dy + 4);
      ctx.stroke();
    }
  }

  // 3. Arrival circle at room center
  const cx = ox + ((bounds.x_min + bounds.x_max + 1) / 2) * s;
  const cy = oy + ((bounds.y_min + bounds.y_max + 1) / 2) * s;

  // Outer glow
  ctx.fillStyle = hexAlpha(pal.highlight, 0.04);
  ctx.beginPath();
  ctx.arc(cx, cy, s * 1.5, 0, Math.PI * 2);
  ctx.fill();

  // Circle mark
  ctx.strokeStyle = hexAlpha(pal.highlight, 0.18);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(cx, cy, s * 0.8, 0, Math.PI * 2);
  ctx.stroke();

  // Inner dot
  ctx.fillStyle = hexAlpha(pal.highlight, 0.15);
  ctx.beginPath();
  ctx.arc(cx, cy, 3, 0, Math.PI * 2);
  ctx.fill();
}

// ═══════════════════════════════════════════════════════════
//  EMPTY — Abandoned / Forgotten
// ═══════════════════════════════════════════════════════════

function _drawEmptyOverlay(ctx, opts) {
  const { theme, tileSize: s, roomOffsetX: ox, roomOffsetY: oy, bounds, seed } = opts;
  const pal = theme.palette;

  const innerX = bounds.x_min * s + ox;
  const innerY = bounds.y_min * s + oy;
  const innerW = (bounds.x_max - bounds.x_min + 1) * s;
  const innerH = (bounds.y_max - bounds.y_min + 1) * s;

  // 1. Dimmer overall — dark wash
  ctx.fillStyle = 'rgba(0, 0, 0, 0.12)';
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2. Corner rubble — always in bottom-left and top-right (deliberate, not random)
  const rubbleCorners = [
    { x: bounds.x_min, y: bounds.y_max },     // Bottom-left
    { x: bounds.x_max, y: bounds.y_min },      // Top-right
  ];
  for (const c of rubbleCorners) {
    const px = ox + c.x * s;
    const py = oy + c.y * s;
    const rubbleColor = shiftColor(pal.secondary, -8);

    // Main rubble pile — a cluster of 3-4 small rects
    ctx.fillStyle = rubbleColor;
    ctx.fillRect(px + 4, py + s - 10, 10, 6);
    ctx.fillRect(px + 8, py + s - 14, 8, 5);
    ctx.fillRect(px + 2, py + s - 8, 6, 4);

    // Shadow underneath
    ctx.fillStyle = 'rgba(0,0,0,0.15)';
    ctx.fillRect(px + 3, py + s - 4, 14, 2);
  }

  // 3. Darkened wall edges — heavier vignette on walls
  ctx.fillStyle = 'rgba(0,0,0,0.08)';
  // Top edge
  ctx.fillRect(innerX, innerY, innerW, s * 0.4);
  // Bottom edge
  ctx.fillRect(innerX, innerY + innerH - s * 0.4, innerW, s * 0.4);
}

// ═══════════════════════════════════════════════════════════
//  STAIRS — Descending Stairwell
// ═══════════════════════════════════════════════════════════

function _drawStairsOverlay(ctx, opts) {
  const { theme, tileSize: s, roomOffsetX: ox, roomOffsetY: oy, bounds, seed } = opts;
  const pal = theme.palette;

  const innerX = bounds.x_min * s + ox;
  const innerY = bounds.y_min * s + oy;
  const innerW = (bounds.x_max - bounds.x_min + 1) * s;
  const innerH = (bounds.y_max - bounds.y_min + 1) * s;

  // 1. Vertical Wall streaks — on left and right walls suggesting depth
  const streakColor = hexAlpha(pal.accent, 0.10);
  ctx.fillStyle = streakColor;
  // Left wall — 3 evenly spaced streaks
  for (let i = 0; i < 3; i++) {
    const y = bounds.y_min + 1 + i * Math.floor((bounds.y_max - bounds.y_min - 1) / 3);
    const px = ox + (bounds.x_min - 1) * s;    // Wall tile (left of floor)
    const py = oy + y * s;
    ctx.fillRect(px + s * 0.4, py + 2, 2, s - 4);
    ctx.fillRect(px + s * 0.6, py + 4, 2, s - 8);
  }
  // Right wall — matching streaks
  for (let i = 0; i < 3; i++) {
    const y = bounds.y_min + 1 + i * Math.floor((bounds.y_max - bounds.y_min - 1) / 3);
    const px = ox + (bounds.x_max + 1) * s;
    const py = oy + y * s;
    ctx.fillRect(px + s * 0.3, py + 2, 2, s - 4);
    ctx.fillRect(px + s * 0.5, py + 4, 2, s - 8);
  }

  // 3. Downward gradient — bottom of room is slightly darker (depth illusion)
  const grad = ctx.createLinearGradient(innerX, innerY, innerX, innerY + innerH);
  grad.addColorStop(0, 'rgba(0,0,0,0)');
  grad.addColorStop(1, 'rgba(0,0,0,0.10)');
  ctx.fillStyle = grad;
  ctx.fillRect(innerX, innerY, innerW, innerH);
}

// ═══════════════════════════════════════════════════════════
//  SHRINE — Sacred Shrine
// ═══════════════════════════════════════════════════════════

function _drawShrineOverlay(ctx, opts) {
  const { theme, tileSize: s, roomOffsetX: ox, roomOffsetY: oy, bounds, seed } = opts;
  const pal = theme.palette;

  const innerX = bounds.x_min * s + ox;
  const innerY = bounds.y_min * s + oy;
  const innerW = (bounds.x_max - bounds.x_min + 1) * s;
  const innerH = (bounds.y_max - bounds.y_min + 1) * s;

  // 1. Subtle floor shine — highlight overlay over inner area
  ctx.fillStyle = hexAlpha(pal.highlight, 0.03);
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2. Accent-colored thin floor border (1px inset rectangle)
  ctx.strokeStyle = hexAlpha(pal.accent, 0.25);
  ctx.lineWidth = 1;
  ctx.strokeRect(innerX + s * 0.4, innerY + s * 0.4, innerW - s * 0.8, innerH - s * 0.8);

  // 3. Center altar area — stone base with accent top
  const cx = ox + ((bounds.x_min + bounds.x_max + 1) / 2) * s;
  const cy = oy + ((bounds.y_min + bounds.y_max + 1) / 2) * s;
  const aw = s * 0.6;
  const ah = s * 0.4;

  // Altar shadow
  ctx.fillStyle = 'rgba(0,0,0,0.15)';
  ctx.fillRect(cx - aw / 2 + 2, cy - ah / 2 + 2, aw, ah);

  // Altar body
  ctx.fillStyle = shiftColor(pal.furniture || pal.secondary, 5);
  ctx.fillRect(cx - aw / 2, cy - ah / 2, aw, ah);

  // Altar accent top
  ctx.fillStyle = hexAlpha(pal.accent, 0.5);
  ctx.fillRect(cx - aw / 2 + 2, cy - ah / 2 + 2, aw - 4, ah * 0.3);

  // Altar border
  ctx.strokeStyle = shiftColor(pal.furniture || pal.secondary, -10);
  ctx.lineWidth = 1;
  ctx.strokeRect(cx - aw / 2, cy - ah / 2, aw, ah);

  // Center gemstone
  ctx.fillStyle = hexAlpha(pal.highlight, 0.7);
  ctx.beginPath();
  ctx.arc(cx, cy, 2.5, 0, Math.PI * 2);
  ctx.fill();

  // 4. Two flanking braziers — left and right of center
  const flankDist = s * 1.2;
  for (const side of [-1, 1]) {
    const bx = cx + side * flankDist;
    const by = cy;

    // Glow halo
    const grad = ctx.createRadialGradient(bx, by, 2, bx, by, s * 0.35);
    grad.addColorStop(0, 'rgba(255, 160, 40, 0.12)');
    grad.addColorStop(1, 'rgba(255, 100, 20, 0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(bx, by, s * 0.35, 0, Math.PI * 2);
    ctx.fill();

    // Brazier base
    ctx.fillStyle = shiftColor(pal.metal || pal.secondary, 5);
    ctx.beginPath();
    ctx.ellipse(bx, by + 4, s * 0.08, s * 0.05, 0, 0, Math.PI * 2);
    ctx.fill();

    // Flame
    ctx.fillStyle = 'rgba(255, 180, 50, 0.6)';
    ctx.beginPath();
    ctx.arc(bx, by, 3, 0, Math.PI * 2);
    ctx.fill();
  }

  // 5. Wall-adjacent banners on top wall (every other tile)
  ctx.fillStyle = hexAlpha(pal.accent, 0.5);
  for (let tx = bounds.x_min + 1; tx < bounds.x_max; tx += 2) {
    const bx = ox + tx * s + s * 0.35;
    const by = oy + bounds.y_min * s + 2;
    const bw = s * 0.3;
    const bh = s * 0.5;

    // Rod
    ctx.fillStyle = shiftColor(pal.metal || pal.secondary, 5);
    ctx.fillRect(bx - 2, by, bw + 4, 2);

    // Fabric
    ctx.fillStyle = hexAlpha(pal.accent, 0.5);
    ctx.fillRect(bx, by + 2, bw, bh - 8);

    // Tattered bottom
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
  }
}

// ═══════════════════════════════════════════════════════════
//  LIBRARY — Archive / Library
// ═══════════════════════════════════════════════════════════

function _drawLibraryOverlay(ctx, opts) {
  const { theme, tileSize: s, roomOffsetX: ox, roomOffsetY: oy, bounds, seed } = opts;
  const pal = theme.palette;

  const innerX = bounds.x_min * s + ox;
  const innerY = bounds.y_min * s + oy;
  const innerW = (bounds.x_max - bounds.x_min + 1) * s;
  const innerH = (bounds.y_max - bounds.y_min + 1) * s;

  // 1. Floor slightly lighter — maintained and clean
  ctx.fillStyle = hexAlpha(pal.highlight, 0.02);
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2. Bookshelves along all 4 walls (every other wall tile)
  const shelfColor = shiftColor(pal.furniture || pal.secondary, 5);
  const shelfBorder = shiftColor(pal.furniture || pal.secondary, -8);
  const h = cellHash;

  // Top wall bookshelves
  for (let tx = bounds.x_min; tx <= bounds.x_max; tx += 2) {
    _drawWallBookshelf(ctx, ox + tx * s, oy + bounds.y_min * s, s, seed + tx, pal, shelfColor, shelfBorder);
  }
  // Bottom wall bookshelves
  for (let tx = bounds.x_min; tx <= bounds.x_max; tx += 2) {
    _drawWallBookshelf(ctx, ox + tx * s, oy + bounds.y_max * s, s, seed + tx + 100, pal, shelfColor, shelfBorder);
  }
  // Left wall bookshelves
  for (let ty = bounds.y_min + 1; ty < bounds.y_max; ty += 2) {
    _drawWallBookshelf(ctx, ox + bounds.x_min * s, oy + ty * s, s, seed + ty + 200, pal, shelfColor, shelfBorder);
  }
  // Right wall bookshelves
  for (let ty = bounds.y_min + 1; ty < bounds.y_max; ty += 2) {
    _drawWallBookshelf(ctx, ox + bounds.x_max * s, oy + ty * s, s, seed + ty + 300, pal, shelfColor, shelfBorder);
  }

  // 3. Faint dust motes near center (2-3 tiny 1px dots)
  ctx.fillStyle = hexAlpha(pal.highlight, 0.12);
  const cx = ox + ((bounds.x_min + bounds.x_max + 1) / 2) * s;
  const cy = oy + ((bounds.y_min + bounds.y_max + 1) / 2) * s;
  for (let i = 0; i < 3; i++) {
    const dx = cx + (h(seed, i, 40) - 0.5) * s * 1.5;
    const dy = cy + (h(seed, i, 41) - 0.5) * s * 1.5;
    ctx.beginPath();
    ctx.arc(dx, dy, 1, 0, Math.PI * 2);
    ctx.fill();
  }
}

/**
 * Helper: draw a single wall-tile bookshelf with shelf lines and book spines.
 */
function _drawWallBookshelf(ctx, x, y, size, seed, palette, shelfColor, shelfBorder) {
  const bx = x + size * 0.1;
  const by = y + size * 0.05;
  const bw = size * 0.8;
  const bh = size * 0.85;
  const h = cellHash;

  // Shelf frame
  ctx.fillStyle = shelfColor;
  ctx.fillRect(bx, by, bw, bh);

  // Border
  ctx.strokeStyle = shelfBorder;
  ctx.lineWidth = 1;
  ctx.strokeRect(bx, by, bw, bh);

  // 4 horizontal shelf lines
  const shelves = 4;
  const shelfH = bh / shelves;
  for (let i = 1; i < shelves; i++) {
    const sy = by + i * shelfH;
    ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, -4);
    ctx.fillRect(bx + 1, sy, bw - 2, 1);
  }

  // Book spines on each shelf
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

// ═══════════════════════════════════════════════════════════
//  PRISON — Prison / Cage Room
// ═══════════════════════════════════════════════════════════

function _drawPrisonOverlay(ctx, opts) {
  const { theme, tileSize: s, roomOffsetX: ox, roomOffsetY: oy, bounds, doorPositions, seed } = opts;
  const pal = theme.palette;

  const innerX = bounds.x_min * s + ox;
  const innerY = bounds.y_min * s + oy;
  const innerW = (bounds.x_max - bounds.x_min + 1) * s;
  const innerH = (bounds.y_max - bounds.y_min + 1) * s;

  // 1. Darker floor wash — oppressive atmosphere
  ctx.fillStyle = 'rgba(0,0,0,0.10)';
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2. Corner shadow vignette — heavier than empty (0.15)
  ctx.fillStyle = 'rgba(0,0,0,0.15)';
  // Top-left corner
  ctx.fillRect(innerX, innerY, s, s);
  // Top-right corner
  ctx.fillRect(innerX + innerW - s, innerY, s, s);
  // Bottom-left corner
  ctx.fillRect(innerX, innerY + innerH - s, s, s);
  // Bottom-right corner
  ctx.fillRect(innerX + innerW - s, innerY + innerH - s, s, s);

  // 3. Chains on left and right wall tiles
  const chainColor = shiftColor(pal.metal || pal.secondary, 5);
  const midY = Math.floor((bounds.y_min + bounds.y_max) / 2);
  const chainPositions = [
    { x: bounds.x_min, y: midY },
    { x: bounds.x_max, y: midY },
  ];
  if (bounds.y_max - bounds.y_min > 3) {
    chainPositions.push(
      { x: bounds.x_min, y: bounds.y_min + 1 },
      { x: bounds.x_max, y: bounds.y_min + 1 },
    );
  }
  for (const pos of chainPositions) {
    const px = ox + pos.x * s;
    const py = oy + pos.y * s;
    const count = 2 + Math.floor(cellHash(seed + pos.x, pos.y, 80) * 2);
    for (let i = 0; i < count; i++) {
      const cx = px + s * 0.2 + (i / (count - 1 || 1)) * s * 0.6;
      const chainLen = s * 0.4 + cellHash(seed, i + pos.x, 81) * s * 0.3;
      ctx.strokeStyle = chainColor;
      ctx.lineWidth = 1;
      for (let ly = 0; ly < chainLen; ly += 4) {
        const linkX = cx + ((ly / 4) % 2 === 0 ? -0.5 : 0.5);
        ctx.beginPath();
        ctx.moveTo(linkX, py + ly);
        ctx.lineTo(linkX, py + Math.min(ly + 3, chainLen));
        ctx.stroke();
      }
    }
  }

  // 4. Doorway iron bar overlay — 3 thin vertical lines across each door tile
  if (doorPositions && doorPositions.length > 0) {
    for (const door of doorPositions) {
      const dx = ox + door.x * s;
      const dy = oy + door.y * s;
      ctx.strokeStyle = shiftColor(pal.metal || pal.secondary, 10);
      ctx.lineWidth = 1.5;
      for (let bar = 0; bar < 3; bar++) {
        const barX = dx + s * 0.2 + bar * (s * 0.3);
        ctx.beginPath();
        ctx.moveTo(barX, dy + 2);
        ctx.lineTo(barX, dy + s - 2);
        ctx.stroke();
      }
      // Horizontal cross bar
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(dx + s * 0.15, dy + s * 0.35);
      ctx.lineTo(dx + s * 0.85, dy + s * 0.35);
      ctx.stroke();
    }
  }
}

// ═══════════════════════════════════════════════════════════
//  FLOODED — Flooded Chamber
// ═══════════════════════════════════════════════════════════

function _drawFloodedOverlay(ctx, opts) {
  const { theme, tileSize: s, roomOffsetX: ox, roomOffsetY: oy, bounds, seed } = opts;
  const pal = theme.palette;

  const innerX = bounds.x_min * s + ox;
  const innerY = bounds.y_min * s + oy;
  const innerW = (bounds.x_max - bounds.x_min + 1) * s;
  const innerH = (bounds.y_max - bounds.y_min + 1) * s;

  // 1. Visible water tint — use theme accent to contrast with floor
  const accentRgb = hexToRgb(pal.accent || '#4488aa');
  ctx.fillStyle = `rgba(${Math.min(accentRgb.r, 60)}, ${Math.min(accentRgb.g + 30, 120)}, ${Math.min(accentRgb.b + 60, 180)}, 0.18)`;
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2. Second tint pass — slight blue-green wash for depth
  ctx.fillStyle = 'rgba(15, 60, 90, 0.12)';
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 3. Puddle props on 3-5 random floor tiles — larger, more visible
  const h = cellHash;
  const puddleCount = 3 + Math.floor(h(seed, 0, 90) * 3);
  const floorW = bounds.x_max - bounds.x_min + 1;
  const floorH = bounds.y_max - bounds.y_min + 1;

  for (let i = 0; i < puddleCount; i++) {
    const px = bounds.x_min + Math.floor(h(seed, i, 91) * floorW);
    const py = bounds.y_min + Math.floor(h(seed, i, 92) * floorH);
    const tileX = ox + px * s;
    const tileY = oy + py * s;

    // Water body ellipse — bigger and more opaque
    const pcx = tileX + s * 0.45 + h(seed, i, 93) * s * 0.1;
    const pcy = tileY + s * 0.5 + h(seed, i, 94) * s * 0.1;
    const rx = s * 0.22 + h(seed, i, 95) * s * 0.1;
    const ry = s * 0.15 + h(seed, i, 96) * s * 0.08;

    ctx.fillStyle = 'rgba(10, 50, 70, 0.30)';
    ctx.beginPath();
    ctx.ellipse(pcx, pcy, rx, ry, 0, 0, Math.PI * 2);
    ctx.fill();

    // Bright highlight edge — shimmer
    ctx.strokeStyle = 'rgba(120, 200, 240, 0.25)';
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.ellipse(pcx - 1, pcy - 1, rx * 0.7, ry * 0.7, 0, Math.PI * 0.8, Math.PI * 1.4);
    ctx.stroke();
  }

  // 4. Reflective floor edge highlights near walls — brighter
  ctx.fillStyle = 'rgba(80, 160, 200, 0.08)';
  ctx.fillRect(innerX, innerY, innerW, s * 0.4);
  ctx.fillRect(innerX, innerY + innerH - s * 0.4, innerW, s * 0.4);
  ctx.fillRect(innerX, innerY, s * 0.4, innerH);
  ctx.fillRect(innerX + innerW - s * 0.4, innerY, s * 0.4, innerH);

  // 5. Visible ripple lines — concentric arcs near center
  const rcx = ox + ((bounds.x_min + bounds.x_max + 1) / 2) * s;
  const rcy = oy + ((bounds.y_min + bounds.y_max + 1) / 2) * s;

  ctx.strokeStyle = 'rgba(100, 190, 230, 0.18)';
  ctx.lineWidth = 0.6;
  for (let ring = 0; ring < 3; ring++) {
    const r = s * 0.3 + ring * s * 0.35;
    ctx.beginPath();
    ctx.arc(rcx, rcy, r, Math.PI * 0.1, Math.PI * 0.9);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(rcx, rcy, r, Math.PI * 1.1, Math.PI * 1.7);
    ctx.stroke();
  }
}
