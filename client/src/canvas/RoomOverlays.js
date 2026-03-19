// ─────────────────────────────────────────────────────────
// RoomOverlays.js — Client-side room archetype overlay system
//
// Mirror of tools/theme-designer/src/engine/roomArchetypes.js
// Self-contained — inlines needed utilities.
//
// Draws archetype-specific visual overlays (boss sigils,
// torches, alcoves, water tints, etc.) on top of base tiles.
// Called AFTER drawRoomProps() so props render first.
// ─────────────────────────────────────────────────────────

import { drawRoomProps } from './TileProps.js';

// ═══════════════════════════════════════════════════════════
//  UTILITIES (inlined for self-containment)
// ═══════════════════════════════════════════════════════════

function cellHash(gridX, gridY, salt = 0) {
  let h = ((gridX * 7919) + (gridY * 6271) + (salt * 3571)) | 0;
  h = ((h >> 16) ^ h) * 0x45d9f3b;
  h = ((h >> 16) ^ h) * 0x45d9f3b;
  h = (h >> 16) ^ h;
  return ((h & 0x7FFFFFFF) >>> 0) / 0x7FFFFFFF;
}

function hexToRgb(hex) {
  const h2 = hex.replace('#', '');
  return { r: parseInt(h2.slice(0, 2), 16), g: parseInt(h2.slice(2, 4), 16), b: parseInt(h2.slice(4, 6), 16) };
}

function rgbToCSS(r, g, b, a = 1) {
  if (a < 1) return `rgba(${r}, ${g}, ${b}, ${a})`;
  return `rgb(${r}, ${g}, ${b})`;
}

function shiftColor(baseHex, amount) {
  const { r, g, b } = hexToRgb(baseHex);
  const clamp = v => Math.max(0, Math.min(255, v + amount));
  return rgbToCSS(clamp(r), clamp(g), clamp(b));
}

function hexAlpha(hex, alpha) {
  const { r, g, b } = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function lerpColor(hexA, hexB, t) {
  const a = hexToRgb(hexA);
  const b = hexToRgb(hexB);
  const mix = (va, vb) => Math.round(va + (vb - va) * t);
  return rgbToCSS(mix(a.r, b.r), mix(a.g, b.g), mix(a.b, b.b));
}

// ═══════════════════════════════════════════════════════════
//  MAIN OVERLAY DISPATCHER
// ═══════════════════════════════════════════════════════════

/**
 * Draw room archetype overlay on top of already-rendered base tiles.
 * Calls drawRoomProps() first, then the archetype-specific overlay.
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

  const innerX = bounds.x_min * s + ox;
  const innerY = bounds.y_min * s + oy;
  const innerW = (bounds.x_max - bounds.x_min + 1) * s;
  const innerH = (bounds.y_max - bounds.y_min + 1) * s;

  // 1. Palette shift — slightly grander (lighter walls)
  ctx.fillStyle = hexAlpha(pal.highlight, 0.04);
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2–3. Corner pillars + center sigil now handled by prop system

  // 4. Wall trim
  ctx.fillStyle = hexAlpha(pal.highlight, 0.15);
  ctx.fillRect(innerX + s * 0.5, innerY - 2, innerW - s, 2);
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

  // 1–2. Torches + weapon racks now handled by prop system

  // 3. Worn path between doors
  if (doorPositions && doorPositions.length > 0) {
    const door = doorPositions[0];
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

  // 1. Polished floor sheen
  ctx.fillStyle = hexAlpha(pal.highlight, 0.03);
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2. Wall alcoves along left and right walls
  const alcoveColor = shiftColor(pal.primary, -5);
  const alcoveHighlight = shiftColor(pal.secondary, 8);
  for (let y = bounds.y_min + 1; y < bounds.y_max; y++) {
    const lx = ox + bounds.x_min * s, ly = oy + y * s;
    ctx.fillStyle = alcoveColor; ctx.fillRect(lx + 2, ly + 6, 6, s - 12);
    ctx.strokeStyle = alcoveHighlight; ctx.lineWidth = 0.5; ctx.strokeRect(lx + 2, ly + 6, 6, s - 12);
    const rx = ox + bounds.x_max * s;
    ctx.fillStyle = alcoveColor; ctx.fillRect(rx + s - 8, ly + 6, 6, s - 12);
    ctx.strokeStyle = alcoveHighlight; ctx.strokeRect(rx + s - 8, ly + 6, 6, s - 12);
  }

  // 3. Corner filigree ornaments
  const fCorners = [
    { x: bounds.x_min, y: bounds.y_min, sx:  1, sy:  1 },
    { x: bounds.x_max, y: bounds.y_min, sx: -1, sy:  1 },
    { x: bounds.x_min, y: bounds.y_max, sx:  1, sy: -1 },
    { x: bounds.x_max, y: bounds.y_max, sx: -1, sy: -1 },
  ];
  ctx.strokeStyle = hexAlpha(pal.highlight, 0.30); ctx.lineWidth = 1;
  for (const c of fCorners) {
    const px = ox + c.x * s + s / 2, py = oy + c.y * s + s / 2;
    ctx.beginPath(); ctx.moveTo(px, py + c.sy * 8); ctx.lineTo(px, py); ctx.lineTo(px + c.sx * 8, py); ctx.stroke();
    ctx.fillStyle = hexAlpha(pal.highlight, 0.25);
    ctx.beginPath(); ctx.arc(px, py, 2, 0, Math.PI * 2); ctx.fill();
  }

  // 4. Floor border
  ctx.strokeStyle = hexAlpha(pal.highlight, 0.12); ctx.lineWidth = 1;
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

  // 1. Warm tint
  ctx.fillStyle = 'rgba(60, 40, 20, 0.04)';
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2. Archway highlights flanking doors
  if (doorPositions && doorPositions.length > 0) {
    for (const door of doorPositions) {
      const dx = ox + door.x * s, dy = oy + door.y * s;
      const flankL = dx - s * 0.1, flankR = dx + s + s * 0.1 - 6;
      ctx.fillStyle = lerpColor(pal.secondary, pal.highlight, 0.25);
      ctx.fillRect(flankL - 2, dy + 2, 6, s - 4);
      ctx.fillStyle = hexAlpha(pal.highlight, 0.15);
      ctx.fillRect(flankL - 2, dy + 2, 6, 2);
      ctx.fillStyle = lerpColor(pal.secondary, pal.highlight, 0.25);
      ctx.fillRect(flankR, dy + 2, 6, s - 4);
      ctx.fillStyle = hexAlpha(pal.highlight, 0.15);
      ctx.fillRect(flankR, dy + 2, 6, 2);
      ctx.strokeStyle = hexAlpha(pal.highlight, 0.18); ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(flankL, dy + 4); ctx.quadraticCurveTo(dx + s / 2, dy - 6, flankR + 6, dy + 4); ctx.stroke();
    }
  }

  // 3. Arrival circle at room center
  const cx = ox + ((bounds.x_min + bounds.x_max + 1) / 2) * s;
  const cy = oy + ((bounds.y_min + bounds.y_max + 1) / 2) * s;
  ctx.fillStyle = hexAlpha(pal.highlight, 0.04);
  ctx.beginPath(); ctx.arc(cx, cy, s * 1.5, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = hexAlpha(pal.highlight, 0.18); ctx.lineWidth = 1;
  ctx.beginPath(); ctx.arc(cx, cy, s * 0.8, 0, Math.PI * 2); ctx.stroke();
  ctx.fillStyle = hexAlpha(pal.highlight, 0.15);
  ctx.beginPath(); ctx.arc(cx, cy, 3, 0, Math.PI * 2); ctx.fill();
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

  // 1. Dark wash
  ctx.fillStyle = 'rgba(0, 0, 0, 0.12)';
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2. Corner rubble now handled by prop system

  // 3. Darkened wall edges
  ctx.fillStyle = 'rgba(0,0,0,0.08)';
  ctx.fillRect(innerX, innerY, innerW, s * 0.4);
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

  // 1. Wall streaks suggesting depth
  const streakColor = hexAlpha(pal.accent, 0.10);
  ctx.fillStyle = streakColor;
  for (let i = 0; i < 3; i++) {
    const y = bounds.y_min + 1 + i * Math.floor((bounds.y_max - bounds.y_min - 1) / 3);
    const px = ox + (bounds.x_min - 1) * s, py = oy + y * s;
    ctx.fillRect(px + s * 0.4, py + 2, 2, s - 4);
    ctx.fillRect(px + s * 0.6, py + 4, 2, s - 8);
  }
  for (let i = 0; i < 3; i++) {
    const y = bounds.y_min + 1 + i * Math.floor((bounds.y_max - bounds.y_min - 1) / 3);
    const px = ox + (bounds.x_max + 1) * s, py = oy + y * s;
    ctx.fillRect(px + s * 0.3, py + 2, 2, s - 4);
    ctx.fillRect(px + s * 0.5, py + 4, 2, s - 8);
  }

  // 2. Downward gradient
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

  // 1. Floor shine
  ctx.fillStyle = hexAlpha(pal.highlight, 0.03);
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2. Accent floor border
  ctx.strokeStyle = hexAlpha(pal.accent, 0.25); ctx.lineWidth = 1;
  ctx.strokeRect(innerX + s * 0.4, innerY + s * 0.4, innerW - s * 0.8, innerH - s * 0.8);

  // 3–5. Center altar, flanking braziers, and banners now handled by prop system
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

  // 1. Lighter maintained floor
  ctx.fillStyle = hexAlpha(pal.highlight, 0.02);
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2. Bookshelves along walls
  const shelfColor = shiftColor(pal.furniture || pal.secondary, 5);
  const shelfBorder = shiftColor(pal.furniture || pal.secondary, -8);
  for (let tx = bounds.x_min; tx <= bounds.x_max; tx += 2) {
    _drawWallBookshelf(ctx, ox + tx * s, oy + bounds.y_min * s, s, seed + tx, pal, shelfColor, shelfBorder);
  }
  for (let tx = bounds.x_min; tx <= bounds.x_max; tx += 2) {
    _drawWallBookshelf(ctx, ox + tx * s, oy + bounds.y_max * s, s, seed + tx + 100, pal, shelfColor, shelfBorder);
  }
  for (let ty = bounds.y_min + 1; ty < bounds.y_max; ty += 2) {
    _drawWallBookshelf(ctx, ox + bounds.x_min * s, oy + ty * s, s, seed + ty + 200, pal, shelfColor, shelfBorder);
  }
  for (let ty = bounds.y_min + 1; ty < bounds.y_max; ty += 2) {
    _drawWallBookshelf(ctx, ox + bounds.x_max * s, oy + ty * s, s, seed + ty + 300, pal, shelfColor, shelfBorder);
  }

  // 3. Dust motes near center
  ctx.fillStyle = hexAlpha(pal.highlight, 0.12);
  const cx = ox + ((bounds.x_min + bounds.x_max + 1) / 2) * s;
  const cy = oy + ((bounds.y_min + bounds.y_max + 1) / 2) * s;
  for (let i = 0; i < 3; i++) {
    const dx = cx + (cellHash(seed, i, 40) - 0.5) * s * 1.5;
    const dy = cy + (cellHash(seed, i, 41) - 0.5) * s * 1.5;
    ctx.beginPath(); ctx.arc(dx, dy, 1, 0, Math.PI * 2); ctx.fill();
  }
}

function _drawWallBookshelf(ctx, x, y, size, seed, palette, shelfColor, shelfBorder) {
  const bx = x + size * 0.1, by = y + size * 0.05, bw = size * 0.8, bh = size * 0.85;
  ctx.fillStyle = shelfColor; ctx.fillRect(bx, by, bw, bh);
  ctx.strokeStyle = shelfBorder; ctx.lineWidth = 1; ctx.strokeRect(bx, by, bw, bh);
  const shelves = 4, shelfH = bh / shelves;
  for (let i = 1; i < shelves; i++) {
    ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, -4);
    ctx.fillRect(bx + 1, by + i * shelfH, bw - 2, 1);
  }
  for (let shelf = 0; shelf < shelves; shelf++) {
    const sy = by + shelf * shelfH + 2;
    const bookCount = 3 + Math.floor(cellHash(seed, shelf, 60) * 3);
    for (let b = 0; b < bookCount; b++) {
      const bookX = bx + 3 + b * ((bw - 6) / bookCount);
      const bookW = 2 + cellHash(seed, shelf * 10 + b, 61) * 3;
      const bookH = shelfH - 4;
      ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, Math.floor((cellHash(seed, shelf * 10 + b, 62) - 0.5) * 20));
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

  // 1. Dark floor wash
  ctx.fillStyle = 'rgba(0,0,0,0.10)';
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2. Corner vignette
  ctx.fillStyle = 'rgba(0,0,0,0.15)';
  ctx.fillRect(innerX, innerY, s, s);
  ctx.fillRect(innerX + innerW - s, innerY, s, s);
  ctx.fillRect(innerX, innerY + innerH - s, s, s);
  ctx.fillRect(innerX + innerW - s, innerY + innerH - s, s, s);

  // 3. Chains now handled by prop system

  // 4. Doorway iron bars
  if (doorPositions && doorPositions.length > 0) {
    for (const door of doorPositions) {
      const dx = ox + door.x * s, dy = oy + door.y * s;
      ctx.strokeStyle = shiftColor(pal.metal || pal.secondary, 10); ctx.lineWidth = 1.5;
      for (let bar = 0; bar < 3; bar++) {
        const barX = dx + s * 0.2 + bar * (s * 0.3);
        ctx.beginPath(); ctx.moveTo(barX, dy + 2); ctx.lineTo(barX, dy + s - 2); ctx.stroke();
      }
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(dx + s * 0.15, dy + s * 0.35); ctx.lineTo(dx + s * 0.85, dy + s * 0.35); ctx.stroke();
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

  // 1. Visible water tint
  const accentRgb = hexToRgb(pal.accent || '#4488aa');
  ctx.fillStyle = `rgba(${Math.min(accentRgb.r, 60)}, ${Math.min(accentRgb.g + 30, 120)}, ${Math.min(accentRgb.b + 60, 180)}, 0.18)`;
  ctx.fillRect(innerX, innerY, innerW, innerH);
  ctx.fillStyle = 'rgba(15, 60, 90, 0.12)';
  ctx.fillRect(innerX, innerY, innerW, innerH);

  // 2. Puddles now handled by prop system

  // 3. Reflective edge highlights
  ctx.fillStyle = 'rgba(80, 160, 200, 0.08)';
  ctx.fillRect(innerX, innerY, innerW, s * 0.4);
  ctx.fillRect(innerX, innerY + innerH - s * 0.4, innerW, s * 0.4);
  ctx.fillRect(innerX, innerY, s * 0.4, innerH);
  ctx.fillRect(innerX + innerW - s * 0.4, innerY, s * 0.4, innerH);

  // 4. Ripple arcs near center
  const rcx = ox + ((bounds.x_min + bounds.x_max + 1) / 2) * s;
  const rcy = oy + ((bounds.y_min + bounds.y_max + 1) / 2) * s;
  ctx.strokeStyle = 'rgba(100, 190, 230, 0.18)'; ctx.lineWidth = 0.6;
  for (let ring = 0; ring < 3; ring++) {
    const r = s * 0.3 + ring * s * 0.35;
    ctx.beginPath(); ctx.arc(rcx, rcy, r, Math.PI * 0.1, Math.PI * 0.9); ctx.stroke();
    ctx.beginPath(); ctx.arc(rcx, rcy, r, Math.PI * 1.1, Math.PI * 1.7); ctx.stroke();
  }
}
