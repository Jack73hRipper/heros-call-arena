// ─────────────────────────────────────────────────────────
// TileProps.js — Client-side procedural floor prop system
//
// Mirror of tools/theme-designer/src/engine/tileProps.js
// Self-contained — inlines needed utilities.
//
// Renders decorative objects on floor tiles based on room
// archetype and theme. All Canvas 2D drawn, no sprites.
// ─────────────────────────────────────────────────────────

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
//  PROP DRAWING FUNCTIONS (10 props)
// ═══════════════════════════════════════════════════════════

function drawProp_pillar(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2, cy = y + size / 2, r = size * 0.28;
  ctx.fillStyle = 'rgba(0,0,0,0.25)'; ctx.beginPath(); ctx.arc(cx + 1, cy + 1, r + 2, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = lerpColor(palette.metal || palette.secondary, palette.highlight, 0.25); ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = hexAlpha(palette.highlight, 0.35); ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(cx, cy, r - 2, Math.PI * 1.1, Math.PI * 1.6); ctx.stroke();
}

function drawProp_rubble(ctx, x, y, size, seed, palette) {
  const h = cellHash;
  const rubbleColor = shiftColor(palette.secondary, -8);
  const count = 4 + Math.floor(h(seed, 0, 50) * 3);
  ctx.fillStyle = 'rgba(0,0,0,0.12)'; ctx.fillRect(x + size * 0.25, y + size * 0.6, size * 0.5, size * 0.15);
  for (let i = 0; i < count; i++) {
    const rx = x + size * 0.2 + h(seed, i, 51) * size * 0.4;
    const ry = y + size * 0.35 + h(seed, i, 52) * size * 0.3;
    const rw = 3 + h(seed, i, 53) * 6, rh = 2 + h(seed, i, 54) * 4;
    ctx.fillStyle = shiftColor(rubbleColor, Math.floor((h(seed, i, 55) - 0.5) * 10));
    ctx.fillRect(rx, ry, rw, rh);
  }
}

function drawProp_brazier(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2, cy = y + size * 0.45;
  const grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, size * 0.4);
  grad.addColorStop(0, 'rgba(255, 160, 40, 0.15)'); grad.addColorStop(1, 'rgba(255, 100, 20, 0)');
  ctx.fillStyle = grad; ctx.beginPath(); ctx.arc(cx, cy, size * 0.4, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = shiftColor(palette.metal || palette.secondary, 5); ctx.beginPath(); ctx.ellipse(cx, cy + 4, size * 0.1, size * 0.06, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = 'rgba(255, 180, 50, 0.7)'; ctx.beginPath(); ctx.arc(cx, cy, 3, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = 'rgba(255, 120, 30, 0.35)'; ctx.beginPath(); ctx.arc(cx, cy - 1, 5, 0, Math.PI * 2); ctx.fill();
}

function drawProp_coffin(ctx, x, y, size, seed, palette) {
  const cx = x + size * 0.15, cy = y + size * 0.2, cw = size * 0.7, ch = size * 0.6;
  ctx.fillStyle = 'rgba(0,0,0,0.15)'; ctx.fillRect(cx + 2, cy + 2, cw, ch);
  ctx.fillStyle = palette.furniture || shiftColor(palette.secondary, -5); ctx.fillRect(cx, cy, cw, ch);
  ctx.strokeStyle = shiftColor(palette.furniture || palette.secondary, -8); ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(cx, cy + ch * 0.45); ctx.lineTo(cx + cw, cy + ch * 0.45); ctx.stroke();
  ctx.strokeStyle = shiftColor(palette.furniture || palette.secondary, -12); ctx.lineWidth = 0.8; ctx.strokeRect(cx, cy, cw, ch);
  ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, -5); ctx.beginPath(); ctx.moveTo(cx + 2, cy); ctx.lineTo(cx + cw - 2, cy); ctx.lineTo(cx + cw, cy + ch * 0.15); ctx.lineTo(cx, cy + ch * 0.15); ctx.closePath(); ctx.fill();
}

function drawProp_bookshelf(ctx, x, y, size, seed, palette) {
  const bx = x + size * 0.1, by = y + size * 0.05, bw = size * 0.8, bh = size * 0.85;
  ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, 5); ctx.fillRect(bx, by, bw, bh);
  ctx.strokeStyle = shiftColor(palette.furniture || palette.secondary, -8); ctx.lineWidth = 1; ctx.strokeRect(bx, by, bw, bh);
  const shelves = 4, shelfH = bh / shelves;
  for (let i = 1; i < shelves; i++) { ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, -4); ctx.fillRect(bx + 1, by + i * shelfH, bw - 2, 1); }
  const h = cellHash;
  for (let shelf = 0; shelf < shelves; shelf++) {
    const sy = by + shelf * shelfH + 2;
    const bookCount = 3 + Math.floor(h(seed, shelf, 60) * 3);
    for (let b = 0; b < bookCount; b++) {
      const bookX = bx + 3 + b * ((bw - 6) / bookCount);
      const bookW = 2 + h(seed, shelf * 10 + b, 61) * 3, bookH = shelfH - 4;
      ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, Math.floor((h(seed, shelf * 10 + b, 62) - 0.5) * 20));
      ctx.fillRect(bookX, sy, bookW, bookH);
    }
  }
}

function drawProp_altar(ctx, x, y, size, seed, palette) {
  const ax = x + size * 0.2, ay = y + size * 0.3, aw = size * 0.6, ah = size * 0.4;
  ctx.fillStyle = 'rgba(0,0,0,0.15)'; ctx.fillRect(ax + 2, ay + 2, aw, ah);
  ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, 5); ctx.fillRect(ax, ay, aw, ah);
  ctx.fillStyle = hexAlpha(palette.accent, 0.5); ctx.fillRect(ax + 2, ay + 2, aw - 4, ah * 0.3);
  ctx.strokeStyle = shiftColor(palette.furniture || palette.secondary, -10); ctx.lineWidth = 1; ctx.strokeRect(ax, ay, aw, ah);
  ctx.fillStyle = hexAlpha(palette.highlight, 0.7); ctx.beginPath(); ctx.arc(ax + aw / 2, ay + ah * 0.5, 2.5, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = hexAlpha(palette.highlight, 0.15); ctx.beginPath(); ctx.arc(ax + aw / 2, ay + ah * 0.5, 6, 0, Math.PI * 2); ctx.fill();
}

function drawProp_puddle(ctx, x, y, size, seed, palette) {
  const cx = x + size * 0.45 + cellHash(seed, 0, 70) * size * 0.1;
  const cy = y + size * 0.5 + cellHash(seed, 0, 71) * size * 0.1;
  const rx = size * 0.18 + cellHash(seed, 0, 72) * size * 0.08;
  const ry = size * 0.12 + cellHash(seed, 0, 73) * size * 0.06;
  ctx.fillStyle = 'rgba(20, 60, 80, 0.15)'; ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = 'rgba(100, 180, 220, 0.12)'; ctx.lineWidth = 0.8; ctx.beginPath(); ctx.ellipse(cx - 1, cy - 1, rx * 0.7, ry * 0.7, 0, Math.PI * 0.8, Math.PI * 1.4); ctx.stroke();
}

function drawProp_barrel(ctx, x, y, size, seed, palette) {
  const cx = x + size * 0.5, cy = y + size * 0.5, r = size * 0.12;
  ctx.fillStyle = 'rgba(0,0,0,0.15)'; ctx.beginPath(); ctx.ellipse(cx + 1, cy + 2, r + 1, r * 0.7 + 1, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = lerpColor(palette.furniture || palette.secondary, '#5C3310', 0.5); ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = lerpColor(palette.furniture || palette.secondary, '#3A1F08', 0.5); ctx.lineWidth = 0.8; ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
  ctx.strokeStyle = shiftColor(palette.metal || palette.secondary, -5); ctx.lineWidth = 0.6; ctx.beginPath(); ctx.moveTo(cx - r * 0.7, cy); ctx.lineTo(cx + r * 0.7, cy); ctx.moveTo(cx, cy - r * 0.7); ctx.lineTo(cx, cy + r * 0.7); ctx.stroke();
}

function drawProp_chains(ctx, x, y, size, seed, palette) {
  const h = cellHash;
  const chainColor = shiftColor(palette.metal || palette.secondary, 5);
  const count = 2 + Math.floor(h(seed, 0, 80) * 2);
  for (let i = 0; i < count; i++) {
    const cx = x + size * 0.2 + (i / (count - 1 || 1)) * size * 0.6;
    const chainLen = size * 0.4 + h(seed, i, 81) * size * 0.3;
    ctx.strokeStyle = chainColor; ctx.lineWidth = 1;
    for (let ly = 0; ly < chainLen; ly += 4) {
      const linkX = cx + ((ly / 4) % 2 === 0 ? -0.5 : 0.5);
      ctx.beginPath(); ctx.moveTo(linkX, y + ly); ctx.lineTo(linkX, y + Math.min(ly + 3, chainLen)); ctx.stroke();
    }
  }
}

function drawProp_banner(ctx, x, y, size, seed, palette) {
  const bx = x + size * 0.35, by = y + 2, bw = size * 0.3, bh = size * 0.6;
  ctx.fillStyle = shiftColor(palette.metal || palette.secondary, 5); ctx.fillRect(bx - 2, by, bw + 4, 2);
  ctx.fillStyle = hexAlpha(palette.accent, 0.6); ctx.fillRect(bx, by + 2, bw, bh - 8);
  ctx.fillStyle = hexAlpha(palette.accent, 0.6); ctx.beginPath(); ctx.moveTo(bx, by + bh - 8);
  const teeth = 3, toothW = bw / teeth;
  for (let t = 0; t < teeth; t++) { ctx.lineTo(bx + t * toothW + toothW / 2, by + bh); ctx.lineTo(bx + (t + 1) * toothW, by + bh - 8); }
  ctx.closePath(); ctx.fill();
  ctx.fillStyle = hexAlpha(palette.highlight, 0.2); ctx.fillRect(bx + bw * 0.35, by + 4, bw * 0.3, bh - 14);
}

// ═══════════════════════════════════════════════════════════
//  DISPATCH + PLACEMENT
// ═══════════════════════════════════════════════════════════

const PROP_DRAW_MAP = {
  pillar: drawProp_pillar, rubble: drawProp_rubble, brazier: drawProp_brazier,
  coffin: drawProp_coffin, bookshelf: drawProp_bookshelf, altar: drawProp_altar,
  puddle: drawProp_puddle, barrel: drawProp_barrel, chains: drawProp_chains, banner: drawProp_banner,
};

export function drawTileProp(ctx, propName, x, y, tileSize, seed, palette) {
  const fn = PROP_DRAW_MAP[propName];
  if (fn) fn(ctx, x, y, tileSize, seed, palette);
}

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

function _resolvePosition(position, bounds, seed) {
  const { x_min, y_min, x_max, y_max } = bounds;
  const floorW = x_max - x_min + 1, floorH = y_max - y_min + 1;
  const midX = Math.floor((x_min + x_max) / 2), midY = Math.floor((y_min + y_max) / 2);
  switch (position) {
    case 'center': return [{ x: midX, y: midY }];
    case 'corners': return [{ x: x_min, y: y_min }, { x: x_max, y: y_min }, { x: x_min, y: y_max }, { x: x_max, y: y_max }];
    case 'flanking_center': return [{ x: midX - 1, y: midY }, { x: midX + 1, y: midY }];
    case 'wall_left': return [{ x: x_min, y: midY }];
    case 'wall_right': return [{ x: x_max, y: midY }];
    case 'wall_top': { const tiles = []; for (let tx = x_min + 1; tx < x_max; tx += 2) tiles.push({ x: tx, y: y_min }); return tiles; }
    case 'wall_bottom': { const tiles = []; for (let tx = x_min + 1; tx < x_max; tx += 2) tiles.push({ x: tx, y: y_max }); return tiles; }
    case 'random_floor': {
      const count = 1 + Math.floor(cellHash(seed, 0, 90) * 2);
      const tiles = [];
      for (let i = 0; i < count; i++) tiles.push({ x: x_min + Math.floor(cellHash(seed, i, 91) * floorW), y: y_min + Math.floor(cellHash(seed, i, 92) * floorH) });
      return tiles;
    }
    default: return [];
  }
}

export function drawRoomProps(ctx, opts) {
  const { archetype, theme, tileSize, roomOffsetX, roomOffsetY, bounds, seed } = opts;
  const slots = ARCHETYPE_PROP_SLOTS[archetype];
  if (!slots) return;
  const affinities = theme.propAffinities || {};
  for (let i = 0; i < slots.length; i++) {
    const slot = slots[i];
    const affinity = affinities[slot.prop];
    if (affinity === undefined || affinity <= 0) continue;
    const effectiveChance = slot.chance * affinity;
    if (cellHash(seed, i, 100) >= effectiveChance) continue;
    const positions = _resolvePosition(slot.position, bounds, seed + i * 13);
    for (const pos of positions) {
      const px = roomOffsetX + pos.x * tileSize;
      const py = roomOffsetY + pos.y * tileSize;
      drawTileProp(ctx, slot.prop, px, py, tileSize, cellHash(pos.x, pos.y, seed), theme.palette);
    }
  }
}
