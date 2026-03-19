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
//  ADDITIONAL PROP DRAWING FUNCTIONS (13 props)
// ═══════════════════════════════════════════════════════════

function drawProp_statue(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2, baseY = y + size * 0.85, h = cellHash;
  ctx.fillStyle = 'rgba(0,0,0,0.12)'; ctx.beginPath(); ctx.ellipse(cx + 3, baseY - 2, size * 0.18, size * 0.06, 0, 0, Math.PI * 2); ctx.fill();
  const pw = size * 0.34, ph = size * 0.12;
  ctx.fillStyle = shiftColor(palette.secondary, 8); ctx.fillRect(cx - pw / 2, baseY - ph, pw, ph);
  ctx.strokeStyle = shiftColor(palette.secondary, -6); ctx.lineWidth = 0.6; ctx.strokeRect(cx - pw / 2, baseY - ph, pw, ph);
  const torsoTop = baseY - ph - size * 0.35, torsoBot = baseY - ph;
  ctx.fillStyle = lerpColor(palette.secondary, palette.metal || palette.secondary, 0.3);
  ctx.beginPath(); ctx.moveTo(cx - size * 0.1, torsoBot); ctx.lineTo(cx + size * 0.1, torsoBot); ctx.lineTo(cx + size * 0.08, torsoTop); ctx.lineTo(cx - size * 0.08, torsoTop); ctx.closePath(); ctx.fill();
  ctx.fillStyle = lerpColor(palette.secondary, palette.metal || palette.secondary, 0.25);
  ctx.beginPath(); ctx.arc(cx, torsoTop - size * 0.06, size * 0.055, 0, Math.PI * 2); ctx.fill();
  if (h(seed, 0, 100) > 0.4) { ctx.fillStyle = palette.floor || palette.primary; ctx.fillRect(cx + size * 0.04, torsoTop - size * 0.1, size * 0.04, size * 0.04); }
  ctx.strokeStyle = hexAlpha(palette.highlight, 0.15); ctx.lineWidth = 0.8;
  ctx.beginPath(); ctx.moveTo(cx - size * 0.08, torsoTop); ctx.lineTo(cx - size * 0.1, torsoBot); ctx.stroke();
}

function drawProp_throne(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2, baseY = y + size * 0.82;
  ctx.fillStyle = 'rgba(0,0,0,0.18)'; ctx.beginPath(); ctx.ellipse(cx + 1, baseY + 1, size * 0.16, size * 0.06, 0, 0, Math.PI * 2); ctx.fill();
  const bw = size * 0.28, bh = size * 0.55, bx = cx - bw / 2, by = baseY - bh;
  ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, 3); ctx.fillRect(bx, by, bw, bh);
  ctx.strokeStyle = shiftColor(palette.furniture || palette.secondary, -10); ctx.lineWidth = 0.8; ctx.strokeRect(bx, by, bw, bh);
  ctx.fillStyle = palette.metal || palette.secondary;
  ctx.beginPath(); ctx.moveTo(cx, by - size * 0.06); ctx.lineTo(cx - size * 0.06, by); ctx.lineTo(cx + size * 0.06, by); ctx.closePath(); ctx.fill();
  ctx.fillStyle = hexAlpha(palette.accent, 0.55); ctx.fillRect(cx - size * 0.16, baseY - size * 0.15, size * 0.32, size * 0.1);
  ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, -2);
  ctx.fillRect(cx - size * 0.2, baseY - size * 0.2, size * 0.08, size * 0.04);
  ctx.fillRect(cx + size * 0.12, baseY - size * 0.2, size * 0.08, size * 0.04);
  ctx.fillStyle = hexAlpha(palette.highlight, 0.4);
  ctx.beginPath(); ctx.arc(bx + 3, by + 3, 1.2, 0, Math.PI * 2); ctx.arc(bx + bw - 3, by + 3, 1.2, 0, Math.PI * 2); ctx.fill();
}

function drawProp_cage(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2, cageTop = y + size * 0.2, cageBot = y + size * 0.75;
  const cageW = size * 0.32, cageH = cageBot - cageTop, metalColor = palette.metal || palette.secondary;
  ctx.strokeStyle = shiftColor(metalColor, 5); ctx.lineWidth = 1;
  for (let ly = y; ly < cageTop; ly += 3) {
    const off = ((ly / 3) | 0) % 2 === 0 ? -0.5 : 0.5;
    ctx.beginPath(); ctx.moveTo(cx + off, ly); ctx.lineTo(cx + off, Math.min(ly + 2, cageTop)); ctx.stroke();
  }
  ctx.strokeStyle = shiftColor(metalColor, 3); ctx.lineWidth = 1.2; ctx.strokeRect(cx - cageW / 2, cageTop, cageW, cageH);
  const barCount = 3 + Math.floor(cellHash(seed, 0, 105) * 2);
  ctx.strokeStyle = shiftColor(metalColor, 0); ctx.lineWidth = 0.8;
  for (let b = 1; b < barCount; b++) { const bx = cx - cageW / 2 + (b / barCount) * cageW; ctx.beginPath(); ctx.moveTo(bx, cageTop); ctx.lineTo(bx, cageBot); ctx.stroke(); }
  ctx.beginPath(); ctx.moveTo(cx - cageW / 2, cageTop + cageH * 0.5); ctx.lineTo(cx + cageW / 2, cageTop + cageH * 0.5); ctx.stroke();
  ctx.fillStyle = 'rgba(0,0,0,0.08)'; ctx.beginPath(); ctx.ellipse(cx, cageBot + 4, cageW * 0.4, 3, 0, 0, Math.PI * 2); ctx.fill();
}

function drawProp_weapon_rack(ctx, x, y, size, seed, palette) {
  const h = cellHash, metalColor = palette.metal || palette.secondary, woodColor = palette.furniture || palette.secondary;
  const rx = x + size * 0.15, ry = y + size * 0.08, rw = size * 0.7, rh = size * 0.8;
  ctx.fillStyle = shiftColor(woodColor, 3); ctx.fillRect(rx, ry, rw, rh);
  ctx.strokeStyle = shiftColor(woodColor, -8); ctx.lineWidth = 0.6; ctx.strokeRect(rx, ry, rw, rh);
  ctx.fillStyle = shiftColor(metalColor, 5);
  ctx.fillRect(rx + 3, ry + rh * 0.28, rw - 6, 1.5); ctx.fillRect(rx + 3, ry + rh * 0.62, rw - 6, 1.5);
  const sw1X = rx + rw * 0.25;
  ctx.strokeStyle = shiftColor(metalColor, 8); ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(sw1X, ry + rh * 0.15); ctx.lineTo(sw1X, ry + rh * 0.75); ctx.stroke();
  ctx.strokeStyle = shiftColor(metalColor, 2); ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(sw1X - 4, ry + rh * 0.6); ctx.lineTo(sw1X + 4, ry + rh * 0.6); ctx.stroke();
  const sw2X = rx + rw * 0.55;
  ctx.strokeStyle = shiftColor(metalColor, 6); ctx.lineWidth = 1.2;
  ctx.beginPath(); ctx.moveTo(sw2X, ry + rh * 0.2); ctx.lineTo(sw2X, ry + rh * 0.72); ctx.stroke();
  ctx.fillStyle = shiftColor(metalColor, 10); ctx.beginPath(); ctx.arc(sw2X, ry + rh * 0.2, 3, 0, Math.PI * 2); ctx.fill();
  if (h(seed, 0, 106) > 0.35) {
    const sw3X = rx + rw * 0.8;
    ctx.strokeStyle = shiftColor(metalColor, 4); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(sw3X, ry + rh * 0.35); ctx.lineTo(sw3X, ry + rh * 0.68); ctx.stroke();
  }
}

function drawProp_torch_sconce(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2, flameY = y + size * 0.25, bracketY = y + size * 0.4;
  const grad = ctx.createRadialGradient(cx, flameY, 1, cx, flameY, size * 0.45);
  grad.addColorStop(0, 'rgba(255, 180, 60, 0.18)'); grad.addColorStop(0.5, 'rgba(255, 120, 30, 0.06)'); grad.addColorStop(1, 'rgba(255, 80, 10, 0)');
  ctx.fillStyle = grad; ctx.beginPath(); ctx.arc(cx, flameY, size * 0.45, 0, Math.PI * 2); ctx.fill();
  const metalColor = palette.metal || palette.secondary;
  ctx.strokeStyle = shiftColor(metalColor, 5); ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(cx, bracketY + size * 0.3); ctx.lineTo(cx, bracketY); ctx.lineTo(cx - size * 0.08, bracketY + size * 0.04); ctx.stroke();
  ctx.strokeStyle = shiftColor(palette.furniture || palette.secondary, 5); ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(cx, bracketY); ctx.lineTo(cx, flameY + 4); ctx.stroke();
  ctx.fillStyle = 'rgba(255, 130, 30, 0.6)';
  ctx.beginPath(); ctx.moveTo(cx, flameY - 5); ctx.quadraticCurveTo(cx + 4, flameY, cx, flameY + 3); ctx.quadraticCurveTo(cx - 4, flameY, cx, flameY - 5); ctx.fill();
  ctx.fillStyle = 'rgba(255, 220, 80, 0.75)'; ctx.beginPath(); ctx.arc(cx, flameY, 2.0, 0, Math.PI * 2); ctx.fill();
}

function drawProp_skull_pile(ctx, x, y, size, seed, palette) {
  const h = cellHash, baseY = y + size * 0.6, cx = x + size / 2;
  const boneColor = lerpColor(palette.secondary, '#d8d0c0', 0.3);
  ctx.fillStyle = 'rgba(0,0,0,0.12)'; ctx.beginPath(); ctx.ellipse(cx, baseY + 4, size * 0.2, size * 0.06, 0, 0, Math.PI * 2); ctx.fill();
  for (let i = 0; i < 3; i++) { ctx.fillStyle = shiftColor(boneColor, -5); ctx.fillRect(cx - size * 0.12 + h(seed, i, 110) * size * 0.24, baseY + h(seed, i, 111) * 4, 3 + h(seed, i, 112) * 3, 1.5); }
  const count = 3 + Math.floor(h(seed, 0, 113) * 3);
  for (let i = count - 1; i >= 0; i--) {
    const sx = cx + (h(seed, i, 114) - 0.5) * size * 0.22, sy = baseY - size * 0.06 - i * size * 0.06 + h(seed, i, 115) * size * 0.04;
    const sr = size * 0.05 + h(seed, i, 116) * size * 0.02;
    ctx.fillStyle = shiftColor(boneColor, Math.floor((h(seed, i, 117) - 0.5) * 8)); ctx.beginPath(); ctx.arc(sx, sy, sr, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = 'rgba(0,0,0,0.5)'; ctx.beginPath(); ctx.arc(sx - sr * 0.35, sy - sr * 0.15, sr * 0.2, 0, Math.PI * 2); ctx.arc(sx + sr * 0.35, sy - sr * 0.15, sr * 0.2, 0, Math.PI * 2); ctx.fill();
  }
}

function drawProp_mushroom_cluster(ctx, x, y, size, seed, palette) {
  const h = cellHash, cx = x + size / 2, baseY = y + size * 0.75, glowColor = palette.accent;
  const grad = ctx.createRadialGradient(cx, baseY - size * 0.1, 2, cx, baseY - size * 0.1, size * 0.32);
  grad.addColorStop(0, hexAlpha(glowColor, 0.12)); grad.addColorStop(1, hexAlpha(glowColor, 0));
  ctx.fillStyle = grad; ctx.beginPath(); ctx.arc(cx, baseY - size * 0.1, size * 0.32, 0, Math.PI * 2); ctx.fill();
  const count = 2 + Math.floor(h(seed, 0, 120) * 3);
  for (let i = 0; i < count; i++) {
    const mx = cx + (h(seed, i, 121) - 0.5) * size * 0.3;
    const stemH = size * 0.12 + h(seed, i, 122) * size * 0.12, stemBot = baseY - h(seed, i, 123) * size * 0.05, stemTop = stemBot - stemH;
    const capR = size * 0.04 + h(seed, i, 124) * size * 0.03;
    ctx.strokeStyle = shiftColor(palette.secondary, 10); ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(mx, stemBot); ctx.lineTo(mx, stemTop); ctx.stroke();
    ctx.fillStyle = hexAlpha(glowColor, 0.6 + h(seed, i, 125) * 0.2); ctx.beginPath(); ctx.arc(mx, stemTop, capR, Math.PI, Math.PI * 2); ctx.fill();
    ctx.fillStyle = hexAlpha(palette.highlight, 0.3); ctx.beginPath(); ctx.arc(mx - capR * 0.3, stemTop - capR * 0.3, capR * 0.25, 0, Math.PI * 2); ctx.fill();
  }
}

function drawProp_web(ctx, x, y, size, seed, palette) {
  const originX = x + size * 0.05, originY = y + size * 0.05, reach = size * 0.55;
  const spokes = 4 + Math.floor(cellHash(seed, 0, 130) * 2);
  ctx.strokeStyle = 'rgba(180, 180, 170, 0.18)'; ctx.lineWidth = 0.5;
  for (let s = 0; s < spokes; s++) {
    const angle = (s / (spokes - 1)) * Math.PI * 0.5;
    ctx.beginPath(); ctx.moveTo(originX, originY); ctx.lineTo(originX + Math.cos(angle) * reach, originY + Math.sin(angle) * reach); ctx.stroke();
  }
  ctx.strokeStyle = 'rgba(180, 180, 170, 0.12)'; ctx.lineWidth = 0.4;
  for (let ring = 1; ring <= 3; ring++) { ctx.beginPath(); ctx.arc(originX, originY, reach * ring / 4, 0, Math.PI * 0.5); ctx.stroke(); }
}

function drawProp_fountain(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2, cy = y + size * 0.52, h = cellHash;
  const basinR = size * 0.32, stoneColor = lerpColor(palette.secondary, palette.metal || palette.secondary, 0.2);
  ctx.fillStyle = 'rgba(0,0,0,0.18)'; ctx.beginPath(); ctx.ellipse(cx + 2, cy + basinR * 0.6, (basinR + size * 0.04) * 1.1, (basinR + size * 0.04) * 0.35, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = shiftColor(stoneColor, 4); ctx.beginPath();
  for (let i = 0; i < 8; i++) { const a = (i / 8) * Math.PI * 2 - Math.PI / 8, px = cx + Math.cos(a) * basinR, py = cy + Math.sin(a) * basinR * 0.6; if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py); }
  ctx.closePath(); ctx.fill();
  ctx.fillStyle = shiftColor(stoneColor, -12); ctx.beginPath();
  for (let i = 0; i < 8; i++) { const a = (i / 8) * Math.PI * 2 - Math.PI / 8, px = cx + Math.cos(a) * (basinR - size * 0.04), py = cy + Math.sin(a) * (basinR - size * 0.04) * 0.6; if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py); }
  ctx.closePath(); ctx.fill();
  ctx.fillStyle = hexAlpha(palette.accent, 0.15); ctx.beginPath(); ctx.ellipse(cx, cy, basinR * 0.72, basinR * 0.42, 0, 0, Math.PI * 2); ctx.fill();
  const ripples = 2 + Math.floor(h(seed, 0, 200) * 2);
  for (let r = 0; r < ripples; r++) { ctx.strokeStyle = hexAlpha(palette.highlight, 0.06 + r * 0.02); ctx.lineWidth = 0.4; ctx.beginPath(); ctx.ellipse(cx, cy, basinR * (0.2 + r * 0.22), basinR * (0.2 + r * 0.22) * 0.58, 0, 0, Math.PI * 2); ctx.stroke(); }
  ctx.strokeStyle = hexAlpha(palette.highlight, 0.12); ctx.lineWidth = 1; ctx.beginPath(); ctx.ellipse(cx, cy, basinR, basinR * 0.6, 0, Math.PI * 0.6, Math.PI * 1.4); ctx.stroke();
  ctx.fillStyle = shiftColor(stoneColor, 8); ctx.beginPath(); ctx.arc(cx, cy - size * 0.06, size * 0.04, 0, Math.PI * 2); ctx.fill();
}

function drawProp_candelabra(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2, baseY = y + size * 0.88, h = cellHash, metalColor = palette.metal || palette.secondary;
  const glowGrad = ctx.createRadialGradient(cx, y + size * 0.3, 2, cx, y + size * 0.35, size * 0.48);
  glowGrad.addColorStop(0, 'rgba(255, 190, 80, 0.10)'); glowGrad.addColorStop(0.5, 'rgba(255, 140, 40, 0.04)'); glowGrad.addColorStop(1, 'rgba(255, 100, 20, 0)');
  ctx.fillStyle = glowGrad; ctx.beginPath(); ctx.arc(cx, y + size * 0.35, size * 0.48, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = shiftColor(metalColor, 8); ctx.beginPath(); ctx.ellipse(cx, baseY, size * 0.08, size * 0.03, 0, 0, Math.PI * 2); ctx.fill();
  const pillarTop = y + size * 0.28;
  ctx.strokeStyle = shiftColor(metalColor, 5); ctx.lineWidth = 2.5; ctx.beginPath(); ctx.moveTo(cx, baseY); ctx.lineTo(cx, pillarTop); ctx.stroke();
  ctx.strokeStyle = hexAlpha(palette.highlight, 0.15); ctx.lineWidth = 0.6; ctx.beginPath(); ctx.moveTo(cx - 1, baseY - size * 0.1); ctx.lineTo(cx - 1, pillarTop + size * 0.05); ctx.stroke();
  const armCount = 3 + Math.floor(h(seed, 0, 210) * 3), armY = pillarTop + size * 0.1;
  for (let i = 0; i < armCount; i++) {
    const t = armCount === 1 ? 0.5 : i / (armCount - 1), armEndX = cx + (t - 0.5) * size * 0.6, armEndY = armY - size * 0.02 + Math.abs(t - 0.5) * size * 0.08;
    ctx.strokeStyle = shiftColor(metalColor, 3); ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.moveTo(cx, armY); ctx.quadraticCurveTo((cx + armEndX) / 2, armY - size * 0.06, armEndX, armEndY); ctx.stroke();
    ctx.fillStyle = shiftColor(metalColor, 6); ctx.beginPath(); ctx.arc(armEndX, armEndY, size * 0.02, 0, Math.PI * 2); ctx.fill();
    const candleH = size * 0.06 + h(seed, i, 211) * size * 0.04, candleTop = armEndY - candleH;
    ctx.fillStyle = lerpColor('#e8e0d0', palette.secondary, 0.15); ctx.fillRect(armEndX - 1, candleTop, 2.5, candleH);
    ctx.fillStyle = 'rgba(255, 140, 30, 0.35)'; ctx.beginPath(); ctx.moveTo(armEndX, candleTop - 6); ctx.quadraticCurveTo(armEndX + 3, candleTop - 2, armEndX, candleTop); ctx.quadraticCurveTo(armEndX - 3, candleTop - 2, armEndX, candleTop - 6); ctx.fill();
    ctx.fillStyle = 'rgba(255, 230, 100, 0.7)'; ctx.beginPath(); ctx.arc(armEndX, candleTop - 2, 1.3, 0, Math.PI * 2); ctx.fill();
  }
}

function drawProp_ritual_circle(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2, cy = y + size / 2, h = cellHash, glowColor = palette.accent, outerR = size * 0.38;
  const ambientGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, outerR * 1.3);
  ambientGrad.addColorStop(0, hexAlpha(glowColor, 0.1)); ambientGrad.addColorStop(0.6, hexAlpha(glowColor, 0.04)); ambientGrad.addColorStop(1, hexAlpha(glowColor, 0));
  ctx.fillStyle = ambientGrad; ctx.beginPath(); ctx.arc(cx, cy, outerR * 1.3, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = hexAlpha(glowColor, 0.3); ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(cx, cy, outerR, 0, Math.PI * 2); ctx.stroke();
  const innerR = outerR * 0.65;
  ctx.strokeStyle = hexAlpha(glowColor, 0.25); ctx.lineWidth = 1.2; ctx.beginPath(); ctx.arc(cx, cy, innerR, 0, Math.PI * 2); ctx.stroke();
  ctx.strokeStyle = hexAlpha(glowColor, 0.35); ctx.lineWidth = 1; ctx.beginPath();
  for (let i = 0; i < 5; i++) { const a1 = (i * 2 % 5) / 5 * Math.PI * 2 - Math.PI / 2, a2 = ((i * 2 + 2) % 5) / 5 * Math.PI * 2 - Math.PI / 2; ctx.moveTo(cx + Math.cos(a1) * innerR, cy + Math.sin(a1) * innerR); ctx.lineTo(cx + Math.cos(a2) * innerR, cy + Math.sin(a2) * innerR); }
  ctx.stroke();
  const runeCount = 6 + Math.floor(h(seed, 0, 220) * 3), runeR = (outerR + innerR) / 2;
  for (let i = 0; i < runeCount; i++) {
    const angle = (i / runeCount) * Math.PI * 2 + h(seed, i, 221) * 0.2, rx = cx + Math.cos(angle) * runeR, ry = cy + Math.sin(angle) * runeR;
    ctx.strokeStyle = hexAlpha(glowColor, 0.3 + h(seed, i, 222) * 0.15); ctx.lineWidth = 0.7;
    const rt = Math.floor(h(seed, i, 223) * 3);
    if (rt === 0) { ctx.beginPath(); ctx.moveTo(rx, ry - 2); ctx.lineTo(rx, ry + 2); ctx.moveTo(rx - 1.5, ry); ctx.lineTo(rx + 1.5, ry); ctx.stroke(); }
    else if (rt === 1) { ctx.beginPath(); ctx.moveTo(rx, ry - 2); ctx.lineTo(rx + 1.5, ry); ctx.lineTo(rx, ry + 2); ctx.lineTo(rx - 1.5, ry); ctx.closePath(); ctx.stroke(); }
    else { ctx.fillStyle = hexAlpha(glowColor, 0.4); ctx.beginPath(); ctx.arc(rx, ry, 1.2, 0, Math.PI * 2); ctx.fill(); }
  }
  ctx.fillStyle = hexAlpha(glowColor, 0.4); ctx.beginPath(); ctx.arc(cx, cy, size * 0.03, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = hexAlpha(palette.highlight, 0.5); ctx.beginPath(); ctx.arc(cx, cy, size * 0.015, 0, Math.PI * 2); ctx.fill();
}

function drawProp_iron_maiden(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2, h = cellHash, metalColor = palette.metal || palette.secondary;
  const bx = cx - size * 0.14, by = y + size * 0.08, bw = size * 0.28, bh = size * 0.72;
  ctx.fillStyle = 'rgba(0,0,0,0.2)'; ctx.beginPath(); ctx.ellipse(cx, y + size * 0.85, size * 0.22, size * 0.06, 0, 0, Math.PI * 2); ctx.fill();
  const doorW = size * 0.18;
  ctx.fillStyle = shiftColor(metalColor, -3); ctx.beginPath();
  ctx.moveTo(bx + bw, by + bh * 0.05); ctx.lineTo(bx + bw + doorW, by + bh * 0.12); ctx.lineTo(bx + bw + doorW, by + bh * 0.88); ctx.lineTo(bx + bw, by + bh * 0.95); ctx.closePath(); ctx.fill();
  const spikeCount = 3 + Math.floor(h(seed, 0, 230) * 2);
  for (let s = 0; s < spikeCount; s++) { const sy = by + bh * 0.2 + (s / spikeCount) * bh * 0.55, sx = bx + bw + doorW * 0.3; ctx.fillStyle = shiftColor(metalColor, 15); ctx.beginPath(); ctx.moveTo(sx - 1, sy - 1.5); ctx.lineTo(sx + 3, sy); ctx.lineTo(sx - 1, sy + 1.5); ctx.closePath(); ctx.fill(); }
  ctx.fillStyle = 'rgba(0,0,0,0.35)'; ctx.fillRect(bx + bw - 2, by + bh * 0.08, 4, bh * 0.84);
  ctx.fillStyle = metalColor; ctx.beginPath();
  ctx.moveTo(bx, by + bh); ctx.lineTo(bx, by + bh * 0.15); ctx.quadraticCurveTo(bx, by, cx, by); ctx.quadraticCurveTo(bx + bw, by, bx + bw, by + bh * 0.15); ctx.lineTo(bx + bw, by + bh); ctx.closePath(); ctx.fill();
  ctx.strokeStyle = shiftColor(metalColor, -10); ctx.lineWidth = 1; ctx.beginPath();
  ctx.moveTo(bx, by + bh); ctx.lineTo(bx, by + bh * 0.15); ctx.quadraticCurveTo(bx, by, cx, by); ctx.quadraticCurveTo(bx + bw, by, bx + bw, by + bh * 0.15); ctx.lineTo(bx + bw, by + bh); ctx.stroke();
  ctx.fillStyle = 'rgba(0,0,0,0.5)'; ctx.fillRect(bx + bw * 0.2, by + bh * 0.2, bw * 0.6, size * 0.02);
  ctx.fillStyle = shiftColor(metalColor, 14);
  for (const [rx, ry] of [[bx + 3, by + bh * 0.25], [bx + 3, by + bh * 0.45], [bx + 3, by + bh * 0.65], [bx + 3, by + bh * 0.85], [bx + bw - 3, by + bh * 0.25], [bx + bw - 3, by + bh * 0.45], [bx + bw - 3, by + bh * 0.65], [bx + bw - 3, by + bh * 0.85]]) { ctx.beginPath(); ctx.arc(rx, ry, 1, 0, Math.PI * 2); ctx.fill(); }
}

function drawProp_tombstone(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2, baseY = y + size * 0.82, h = cellHash;
  const stoneColor = lerpColor(palette.secondary, '#8a8580', 0.25);
  const tilt = (h(seed, 0, 240) - 0.5) * 0.12;
  ctx.save(); ctx.translate(cx, baseY); ctx.rotate(tilt);
  const sw = size * 0.24, sh = size * 0.42, sx = -sw / 2, sy = -sh;
  ctx.fillStyle = 'rgba(0,0,0,0.15)'; ctx.beginPath(); ctx.ellipse(2, 3, sw * 0.7, size * 0.04, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = shiftColor(palette.floor || palette.primary, -3); ctx.beginPath(); ctx.ellipse(0, 0, sw * 0.6, size * 0.035, 0, 0, Math.PI * 2); ctx.fill();
  const shape = Math.floor(h(seed, 0, 241) * 3);
  ctx.fillStyle = stoneColor; ctx.beginPath();
  if (shape === 0) { ctx.moveTo(sx, 0); ctx.lineTo(sx, sy + sw / 2); ctx.arc(0, sy + sw / 2, sw / 2, Math.PI, 0); ctx.lineTo(sx + sw, 0); ctx.closePath(); }
  else if (shape === 1) { ctx.moveTo(sx, 0); ctx.lineTo(sx, sy + sh * 0.25); ctx.lineTo(0, sy - sh * 0.05); ctx.lineTo(sx + sw, sy + sh * 0.25); ctx.lineTo(sx + sw, 0); ctx.closePath(); }
  else { ctx.moveTo(sx, 0); ctx.lineTo(sx, sy + 3); ctx.lineTo(sx + 3, sy); ctx.lineTo(sx + sw - 3, sy); ctx.lineTo(sx + sw, sy + 3); ctx.lineTo(sx + sw, 0); ctx.closePath(); }
  ctx.fill();
  ctx.strokeStyle = shiftColor(stoneColor, -10); ctx.lineWidth = 0.7; ctx.stroke();
  const crossCY = sy + sh * 0.35;
  ctx.strokeStyle = shiftColor(stoneColor, -8); ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(0, crossCY - sh * 0.15); ctx.lineTo(0, crossCY + sh * 0.15); ctx.moveTo(-sw * 0.2, crossCY - sh * 0.04); ctx.lineTo(sw * 0.2, crossCY - sh * 0.04); ctx.stroke();
  if (h(seed, 0, 242) > 0.3) { ctx.strokeStyle = shiftColor(stoneColor, -14); ctx.lineWidth = 0.4; ctx.beginPath(); ctx.moveTo(-sw * 0.1, sy + sh * (0.2 + h(seed, 0, 243) * 0.4)); ctx.lineTo(sw * 0.05, sy + sh * (0.2 + h(seed, 0, 243) * 0.4) + sh * 0.2); ctx.stroke(); }
  ctx.restore();
}

// ═══════════════════════════════════════════════════════════
//  DISPATCH + PLACEMENT
// ═══════════════════════════════════════════════════════════

const PROP_DRAW_MAP = {
  pillar: drawProp_pillar, rubble: drawProp_rubble, brazier: drawProp_brazier,
  coffin: drawProp_coffin, bookshelf: drawProp_bookshelf, altar: drawProp_altar,
  puddle: drawProp_puddle, barrel: drawProp_barrel, chains: drawProp_chains, banner: drawProp_banner,
  statue: drawProp_statue, throne: drawProp_throne, cage: drawProp_cage,
  weapon_rack: drawProp_weapon_rack, torch_sconce: drawProp_torch_sconce,
  skull_pile: drawProp_skull_pile, mushroom_cluster: drawProp_mushroom_cluster,
  web: drawProp_web, fountain: drawProp_fountain, candelabra: drawProp_candelabra,
  ritual_circle: drawProp_ritual_circle, iron_maiden: drawProp_iron_maiden,
  tombstone: drawProp_tombstone,
};

export function drawTileProp(ctx, propName, x, y, tileSize, seed, palette) {
  const fn = PROP_DRAW_MAP[propName];
  if (fn) fn(ctx, x, y, tileSize, seed, palette);
}

export const ARCHETYPE_PROP_SLOTS = {
  // Boss — overlay keeps: palette wash, wall trim. Props own: pillars, focal, accents.
  boss: {
    maxProps: 6,
    focal: [
      { prop: 'altar',         weight: 0.45 },
      { prop: 'throne',        weight: 0.30 },
      { prop: 'ritual_circle', weight: 0.25 },
    ],
    accents: [
      { prop: 'pillar',       position: 'corners',          chance: 1.0  },
      { prop: 'brazier',      position: 'flanking_center',  chance: 0.7  },
      { prop: 'banner',       position: 'wall_top',         chance: 0.5  },
      { prop: 'statue',       position: 'wall_left',        chance: 0.4  },
      { prop: 'candelabra',   position: 'flanking_center',  chance: 0.35 },
      { prop: 'weapon_rack',  position: 'wall_right',       chance: 0.3  },
    ],
  },
  // Enemy — overlay keeps: worn door path. Props own: torches, weapon racks, rubble.
  enemy: {
    maxProps: 4,
    accents: [
      { prop: 'torch_sconce', position: 'wall_left',        chance: 0.6  },
      { prop: 'torch_sconce', position: 'wall_right',       chance: 0.6  },
      { prop: 'weapon_rack',  position: 'wall_top',         chance: 0.5  },
      { prop: 'rubble',       position: 'random_floor',     chance: 0.25 },
      { prop: 'barrel',       position: 'corners',          chance: 0.2  },
    ],
  },
  // Loot — overlay keeps: floor sheen, wall alcoves, corner filigree, floor border.
  loot: {
    maxProps: 4,
    accents: [
      { prop: 'barrel',       position: 'corners',          chance: 0.6  },
      { prop: 'barrel',       position: 'random_floor',     chance: 0.3  },
      { prop: 'torch_sconce', position: 'wall_left',        chance: 0.3  },
      { prop: 'torch_sconce', position: 'wall_right',       chance: 0.3  },
      { prop: 'web',          position: 'corners',          chance: 0.15 },
    ],
  },
  // Spawn — overlay keeps: warm tint, archway highlights, arrival circle.
  spawn: {
    maxProps: 3,
    accents: [
      { prop: 'banner',       position: 'wall_top',         chance: 0.5  },
      { prop: 'torch_sconce', position: 'wall_left',        chance: 0.4  },
      { prop: 'torch_sconce', position: 'wall_right',       chance: 0.4  },
    ],
  },
  // Empty — overlay keeps: dark wash, darkened wall edges. Props own: rubble, webs.
  empty: {
    maxProps: 3,
    accents: [
      { prop: 'rubble',       position: 'corners',          chance: 0.5  },
      { prop: 'rubble',       position: 'random_floor',     chance: 0.3  },
      { prop: 'web',          position: 'corners',          chance: 0.35 },
      { prop: 'skull_pile',   position: 'random_floor',     chance: 0.12 },
      { prop: 'tombstone',    position: 'random_floor',     chance: 0.12 },
    ],
  },
  // Stairs — overlay keeps: wall streaks, downward gradient.
  stairs: {
    maxProps: 3,
    accents: [
      { prop: 'pillar',       position: 'wall_left',        chance: 0.4  },
      { prop: 'pillar',       position: 'wall_right',       chance: 0.4  },
      { prop: 'torch_sconce', position: 'wall_top',         chance: 0.5  },
    ],
  },
  // Shrine — overlay keeps: floor shine, accent floor border. Props own: altar, braziers, banners.
  shrine: {
    maxProps: 5,
    accents: [
      { prop: 'altar',        position: 'center',           chance: 1.0  },
      { prop: 'brazier',      position: 'flanking_center',  chance: 0.9  },
      { prop: 'banner',       position: 'wall_top',         chance: 0.6  },
      { prop: 'statue',       position: 'corners',          chance: 0.4  },
      { prop: 'candelabra',   position: 'wall_right',       chance: 0.45 },
      { prop: 'torch_sconce', position: 'wall_left',        chance: 0.35 },
    ],
  },
  // Library — overlay keeps: lighter floor, bookshelves on walls, dust motes.
  library: {
    maxProps: 2,
    accents: [
      { prop: 'torch_sconce', position: 'wall_left',        chance: 0.4  },
      { prop: 'torch_sconce', position: 'wall_right',       chance: 0.3  },
    ],
  },
  // Prison — overlay keeps: dark wash, corner vignette, doorway iron bars. Props own: chains, focal.
  prison: {
    maxProps: 5,
    focal: [
      { prop: 'cage',         weight: 0.55 },
      { prop: 'iron_maiden',  weight: 0.45 },
    ],
    accents: [
      { prop: 'chains',       position: 'wall_left',        chance: 0.8  },
      { prop: 'chains',       position: 'wall_right',       chance: 0.8  },
      { prop: 'torch_sconce', position: 'wall_top',         chance: 0.5  },
      { prop: 'skull_pile',   position: 'random_floor',     chance: 0.2  },
    ],
  },
  // Flooded — overlay keeps: water tint, reflective edges, ripple arcs. Props own: puddles, mushrooms.
  flooded: {
    maxProps: 4,
    accents: [
      { prop: 'puddle',            position: 'random_floor',     chance: 0.9  },
      { prop: 'puddle',            position: 'center',           chance: 0.7  },
      { prop: 'mushroom_cluster',  position: 'wall_left',        chance: 0.4  },
      { prop: 'mushroom_cluster',  position: 'random_floor',     chance: 0.25 },
    ],
  },
  // ── Extended archetypes (theme-designer parity) ──
  cathedral: {
    maxProps: 5,
    focal: [
      { prop: 'fountain',     weight: 0.40 },
      { prop: 'statue',       weight: 0.35 },
      { prop: 'candelabra',   weight: 0.25 },
    ],
    accents: [
      { prop: 'candelabra',   position: 'wall_left',        chance: 0.4  },
      { prop: 'candelabra',   position: 'wall_right',       chance: 0.4  },
      { prop: 'banner',       position: 'wall_top',         chance: 0.5  },
      { prop: 'statue',       position: 'corners',          chance: 0.35 },
      { prop: 'tombstone',    position: 'random_floor',     chance: 0.15 },
    ],
  },
  ritual: {
    maxProps: 4,
    focal: [
      { prop: 'ritual_circle', weight: 1.0 },
    ],
    accents: [
      { prop: 'candelabra',   position: 'corners',          chance: 0.5  },
      { prop: 'brazier',      position: 'flanking_center',  chance: 0.4  },
      { prop: 'skull_pile',   position: 'random_floor',     chance: 0.25 },
    ],
  },
  torture: {
    maxProps: 4,
    focal: [
      { prop: 'cage',         weight: 0.40 },
      { prop: 'iron_maiden',  weight: 0.60 },
    ],
    accents: [
      { prop: 'chains',       position: 'wall_top',         chance: 0.7  },
      { prop: 'skull_pile',   position: 'corners',          chance: 0.25 },
      { prop: 'torch_sconce', position: 'wall_left',        chance: 0.35 },
    ],
  },
  graveyard: {
    maxProps: 5,
    accents: [
      { prop: 'tombstone',    position: 'random_floor',     chance: 0.75 },
      { prop: 'tombstone',    position: 'corners',          chance: 0.5  },
      { prop: 'skull_pile',   position: 'random_floor',     chance: 0.15 },
      { prop: 'web',          position: 'corners',          chance: 0.2  },
    ],
  },
  armory: {
    maxProps: 5,
    accents: [
      { prop: 'weapon_rack',  position: 'wall_top',         chance: 0.7  },
      { prop: 'weapon_rack',  position: 'wall_left',        chance: 0.5  },
      { prop: 'barrel',       position: 'corners',          chance: 0.5  },
      { prop: 'torch_sconce', position: 'wall_right',       chance: 0.45 },
      { prop: 'barrel',       position: 'random_floor',     chance: 0.25 },
    ],
  },
  ossuary: {
    maxProps: 5,
    focal: [
      { prop: 'altar',        weight: 0.35 },
      { prop: 'coffin',       weight: 0.35 },
      { prop: 'candelabra',   weight: 0.30 },
    ],
    accents: [
      { prop: 'skull_pile',   position: 'wall_left',        chance: 0.6  },
      { prop: 'skull_pile',   position: 'wall_right',       chance: 0.6  },
      { prop: 'skull_pile',   position: 'corners',          chance: 0.4  },
      { prop: 'coffin',       position: 'wall_top',         chance: 0.4  },
      { prop: 'tombstone',    position: 'random_floor',     chance: 0.25 },
    ],
  },
  fungal_grotto: {
    maxProps: 5,
    accents: [
      { prop: 'mushroom_cluster', position: 'wall_left',    chance: 0.75 },
      { prop: 'mushroom_cluster', position: 'wall_right',   chance: 0.75 },
      { prop: 'mushroom_cluster', position: 'corners',      chance: 0.5  },
      { prop: 'mushroom_cluster', position: 'random_floor', chance: 0.3  },
      { prop: 'puddle',           position: 'random_floor', chance: 0.4  },
      { prop: 'web',              position: 'corners',      chance: 0.2  },
    ],
  },
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

function _pickFocal(focalOptions, seed, affinities) {
  const valid = focalOptions.filter(f => { const aff = affinities[f.prop]; return aff !== undefined && aff > 0; });
  if (valid.length === 0) return null;
  const weighted = valid.map(f => ({ prop: f.prop, weight: f.weight * (affinities[f.prop] || 0) }));
  const totalWeight = weighted.reduce((sum, w) => sum + w.weight, 0);
  if (totalWeight <= 0) return null;
  let roll = cellHash(seed, 0, 200) * totalWeight;
  for (const w of weighted) { roll -= w.weight; if (roll <= 0) return w.prop; }
  return weighted[weighted.length - 1].prop;
}

const _POSITION_PRIORITY = { center: 0, flanking_center: 1, corners: 2, wall_top: 3, wall_bottom: 3, wall_left: 4, wall_right: 4, random_floor: 5 };

export function drawRoomProps(ctx, opts) {
  const { archetype, theme, tileSize, roomOffsetX, roomOffsetY, bounds, seed } = opts;
  const config = ARCHETYPE_PROP_SLOTS[archetype];
  if (!config) return;
  const affinities = theme.propAffinities || {};
  const maxProps = config.maxProps || 99;
  let propsPlaced = 0;
  const claimed = new Set();

  const _placeSlot = (propName, position, slotSeed) => {
    const positions = _resolvePosition(position, bounds, slotSeed);
    let placedAny = false;
    for (const pos of positions) {
      const key = `${pos.x},${pos.y}`;
      if (claimed.has(key)) continue;
      claimed.add(key);
      placedAny = true;
      const px = roomOffsetX + pos.x * tileSize;
      const py = roomOffsetY + pos.y * tileSize;
      drawTileProp(ctx, propName, px, py, tileSize, cellHash(pos.x, pos.y, seed), theme.palette);
    }
    return placedAny;
  };

  // Focal prop: pick exactly one from weighted group
  if (config.focal && config.focal.length > 0 && propsPlaced < maxProps) {
    const focalProp = _pickFocal(config.focal, seed, affinities);
    if (focalProp && _placeSlot(focalProp, 'center', seed)) propsPlaced++;
  }

  // Accent props: fill remaining budget
  if (config.accents) {
    const sortedAccents = config.accents.map((s, i) => ({ ...s, _origIdx: i }))
      .sort((a, b) => (_POSITION_PRIORITY[a.position] ?? 9) - (_POSITION_PRIORITY[b.position] ?? 9));
    for (const slot of sortedAccents) {
      if (propsPlaced >= maxProps) break;
      const i = slot._origIdx;
      const affinity = affinities[slot.prop];
      if (affinity === undefined || affinity <= 0) continue;
      const effectiveChance = slot.chance * affinity;
      if (cellHash(seed, i, 100) >= effectiveChance) continue;
      if (_placeSlot(slot.prop, slot.position, seed + i * 13)) propsPlaced++;
    }
  }
}
