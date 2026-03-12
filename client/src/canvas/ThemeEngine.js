// ─────────────────────────────────────────────────────────
// ThemeEngine.js — Game-side procedural theme renderer
//
// Self-contained Canvas 2D procedural tile drawing engine
// for use in dungeonRenderer.js. Loads theme configs and
// renders tiles using pure canvas operations — no sprites.
//
// Architecture:
//   1. On theme load → pre-render tile variants to offscreen cache
//   2. On draw → blit from cache (fast)
//   3. Special tiles (doors, chests) drawn directly (state-dependent)
//
// Usage in dungeonRenderer.js:
//   import { themeEngine } from './ThemeEngine.js';
//   themeEngine.setTheme('bleeding_catacombs');
//   themeEngine.drawTile(ctx, 'wall', px, py, gridX, gridY);
// ─────────────────────────────────────────────────────────

// ═══════════════════════════════════════════════════════════
//  NOISE / COLOR UTILITIES
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
  return {
    r: parseInt(h2.slice(0, 2), 16),
    g: parseInt(h2.slice(2, 4), 16),
    b: parseInt(h2.slice(4, 6), 16),
  };
}

function rgbToCSS(r, g, b, a = 1) {
  if (a < 1) return `rgba(${r}, ${g}, ${b}, ${a})`;
  return `rgb(${r}, ${g}, ${b})`;
}

function varyColor(baseHex, amount, hashVal) {
  const { r, g, b } = hexToRgb(baseHex);
  const shift = Math.floor((hashVal - 0.5) * 2 * amount);
  const clamp = v => Math.max(0, Math.min(255, v + shift));
  return rgbToCSS(clamp(r), clamp(g), clamp(b));
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
//  BUILT-IN THEME DEFINITIONS
// ═══════════════════════════════════════════════════════════

const BUILT_IN_THEMES = {
  bleeding_catacombs: {
    id: 'bleeding_catacombs', name: 'Bleeding Catacombs',
    palette: { primary: '#1a1015', secondary: '#2a1520', accent: '#8a2030', mortar: '#4a1525', highlight: '#cc3040', floor: '#3e2d3d', floorAlt: '#413040', grout: '#120a10' },
    wall: { style: 'cracked_stone', brickRows: 3, brickCols: 2, mortarWidth: 2, crackDensity: 0.08, bleedChance: 0.05, edgeVignette: true },
    floor: { style: 'flagstone', slabGrid: 2, groutWidth: 1, stainChance: 0.0, stainColor: 'rgba(120, 20, 20, 0.18)', debrisChance: 0.0, debrisColor: '#4a4040', textureDots: 1 },
    corridor: { style: 'worn_stone', streakChance: 0.0 },
    fog: { exploredTint: 'rgba(30, 10, 15, 0.6)', unexploredColor: '#0a0508' },
    ambient: { vignetteStrength: 0.15, vignetteColor: 'rgba(80, 10, 20, 0.10)' },
  },
  ashen_undercroft: {
    id: 'ashen_undercroft', name: 'Ashen Undercroft',
    palette: { primary: '#1a1612', secondary: '#2a2218', accent: '#cc6a20', mortar: '#3a2a18', highlight: '#ff8830', floor: '#443a2c', floorAlt: '#473d2f', grout: '#121010' },
    wall: { style: 'scorched_brick', brickRows: 3, brickCols: 2, mortarWidth: 2, crackDensity: 0.05, emberChance: 0.06, scorchChance: 0.10, edgeVignette: true },
    floor: { style: 'ash_covered', slabGrid: 2, groutWidth: 1, ashDensity: 0.08, emberChance: 0.0, stainChance: 0.0, stainColor: 'rgba(60, 40, 20, 0.15)', debrisChance: 0.0, debrisColor: '#3a3025' },
    corridor: { style: 'ash_trail', ashDensity: 0.15 },
    fog: { exploredTint: 'rgba(25, 18, 10, 0.6)', unexploredColor: '#0a0805' },
    ambient: { vignetteStrength: 0.14, vignetteColor: 'rgba(80, 50, 10, 0.08)' },
  },
  drowned_sanctum: {
    id: 'drowned_sanctum', name: 'Drowned Sanctum',
    palette: { primary: '#0a1520', secondary: '#152535', accent: '#2a8a7a', mortar: '#0e1a25', highlight: '#40ccbb', floor: '#24394f', floorAlt: '#273c52', grout: '#080e14' },
    wall: { style: 'mossy_stone', brickRows: 2, brickCols: 2, mortarWidth: 2, crackDensity: 0.04, mossChance: 0.0, waterStainChance: 0.0, veinChance: 0.0, edgeVignette: true },
    floor: { style: 'flooded', slabGrid: 2, groutWidth: 1, waterDepth: 0.08, rippleChance: 0.0, stainChance: 0.0, stainColor: 'rgba(20, 80, 60, 0.12)', debrisChance: 0.0, debrisColor: '#1a3a30' },
    corridor: { style: 'shallow_water', waterDepth: 0.15 },
    fog: { exploredTint: 'rgba(8, 20, 30, 0.6)', unexploredColor: '#040a10' },
    ambient: { vignetteStrength: 0.12, vignetteColor: 'rgba(10, 60, 60, 0.07)' },
  },
  hollowed_cathedral: {
    id: 'hollowed_cathedral', name: 'Hollowed Cathedral',
    palette: { primary: '#1a1525', secondary: '#2a2035', accent: '#6a4a7a', mortar: '#1e1528', highlight: '#aa7a55', floor: '#3d3555', floorAlt: '#403858', grout: '#100e18' },
    wall: { style: 'carved_stone', brickRows: 2, brickCols: 2, mortarWidth: 3, crackDensity: 0.05, iconChance: 0.0, crumbleChance: 0.05, goldTrimChance: 0.04, edgeVignette: true },
    floor: { style: 'cracked_marble', slabGrid: 3, groutWidth: 1, crackChance: 0.0, veinChance: 0.0, rootChance: 0.0, stainChance: 0.0, stainColor: 'rgba(60, 40, 70, 0.12)', debrisChance: 0.0, debrisColor: '#3a3045' },
    corridor: { style: 'worn_carpet', carpetColor: 'rgba(80, 40, 50, 0.12)' },
    fog: { exploredTint: 'rgba(20, 15, 30, 0.6)', unexploredColor: '#08050e' },
    ambient: { vignetteStrength: 0.15, vignetteColor: 'rgba(50, 30, 60, 0.08)' },
  },
  iron_depths: {
    id: 'iron_depths', name: 'Iron Depths',
    palette: { primary: '#151518', secondary: '#2a2a30', accent: '#7a5a3a', mortar: '#1a1a20', highlight: '#aa7a4a', floor: '#3e3e48', floorAlt: '#41414b', grout: '#0a0a10' },
    wall: { style: 'iron_plate', brickRows: 2, brickCols: 2, mortarWidth: 1, crackDensity: 0.03, rivetChance: 0.40, rustChance: 0.08, pipeChance: 0.0, edgeVignette: true },
    floor: { style: 'metal_grate', slabGrid: 2, groutWidth: 2, grateLineSpacing: 10, oilChance: 0.0, stainChance: 0.0, stainColor: 'rgba(90, 60, 30, 0.15)', debrisChance: 0.0, debrisColor: '#3a3530' },
    corridor: { style: 'walkway', railHint: true },
    fog: { exploredTint: 'rgba(15, 15, 20, 0.6)', unexploredColor: '#050508' },
    ambient: { vignetteStrength: 0.14, vignetteColor: 'rgba(40, 40, 50, 0.08)' },
  },
  forgotten_cellar: {
    id: 'forgotten_cellar', name: 'Forgotten Cellar',
    palette: { primary: '#18160f', secondary: '#2c2820', accent: '#4a4035', mortar: '#1e1c15', highlight: '#6a6050', floor: '#443c30', floorAlt: '#473f33', grout: '#100e0a' },
    wall: { style: 'cracked_stone', brickRows: 3, brickCols: 2, mortarWidth: 2, crackDensity: 0.03, bleedChance: 0.0, edgeVignette: false },
    floor: { style: 'flagstone', slabGrid: 2, groutWidth: 1, stainChance: 0.0, stainColor: 'rgba(60, 50, 40, 0.12)', debrisChance: 0.0, debrisColor: '#3a3530' },
    corridor: { style: 'worn_stone', streakChance: 0.0 },
    fog: { exploredTint: 'rgba(20, 18, 12, 0.55)', unexploredColor: '#0a0908' },
    ambient: { vignetteStrength: 0.08, vignetteColor: 'rgba(30, 25, 15, 0.05)' },
  },
  pale_ossuary: {
    id: 'pale_ossuary', name: 'Pale Ossuary',
    palette: { primary: '#1c1a1e', secondary: '#35323a', accent: '#504a55', mortar: '#28262c', highlight: '#807580', floor: '#4d4856', floorAlt: '#504b59', grout: '#141218' },
    wall: { style: 'carved_stone', brickRows: 2, brickCols: 2, mortarWidth: 2, crackDensity: 0.02, iconChance: 0.0, crumbleChance: 0.01, goldTrimChance: 0.0, edgeVignette: false },
    floor: { style: 'cracked_marble', slabGrid: 2, groutWidth: 1, crackChance: 0.0, veinChance: 0.0, rootChance: 0.0, stainChance: 0.0, stainColor: 'rgba(40, 35, 45, 0.10)', debrisChance: 0.0, debrisColor: '#302830' },
    corridor: { style: 'worn_carpet', carpetColor: 'rgba(60, 55, 65, 0.08)' },
    fog: { exploredTint: 'rgba(20, 18, 24, 0.55)', unexploredColor: '#08060c' },
    ambient: { vignetteStrength: 0.06, vignetteColor: 'rgba(40, 35, 50, 0.04)' },
  },
  silent_vault: {
    id: 'silent_vault', name: 'Silent Vault',
    palette: { primary: '#101520', secondary: '#1e2535', accent: '#3a4a5a', mortar: '#151a28', highlight: '#5a6a80', floor: '#2e3c50', floorAlt: '#313f53', grout: '#0a0e15' },
    wall: { style: 'mossy_stone', brickRows: 2, brickCols: 2, mortarWidth: 2, crackDensity: 0.02, mossChance: 0.0, waterStainChance: 0.0, veinChance: 0.0, edgeVignette: false },
    floor: { style: 'flooded', slabGrid: 2, groutWidth: 1, waterDepth: 0.04, rippleChance: 0.0, stainChance: 0.0, stainColor: 'rgba(30, 40, 55, 0.10)', debrisChance: 0.0, debrisColor: '#1a2530' },
    corridor: { style: 'shallow_water', waterDepth: 0.04 },
    fog: { exploredTint: 'rgba(10, 15, 25, 0.55)', unexploredColor: '#060810' },
    ambient: { vignetteStrength: 0.06, vignetteColor: 'rgba(20, 30, 50, 0.04)' },
  },
};

// ═══════════════════════════════════════════════════════════
//  WALL DRAWING FUNCTIONS
// ═══════════════════════════════════════════════════════════

function drawWall_crackedStone(ctx, x, y, size, seed, pal, p) {
  const h = cellHash;
  ctx.fillStyle = pal.primary;
  ctx.fillRect(x, y, size, size);
  const bH = size / (p.brickRows || 3), bW = size / (p.brickCols || 2), mw = p.mortarWidth || 2;
  for (let r = 0; r < (p.brickRows || 3); r++) {
    const off = (r % 2 === 0) ? 0 : bW * 0.5;
    for (let c = -1; c <= (p.brickCols || 2); c++) {
      const bx = x + off + c * bW, by = y + r * bH;
      const dX = Math.max(x + mw, bx + mw), dY = by + mw;
      const dR = Math.min(x + size - mw, bx + bW - mw), dB = by + bH - mw;
      const dW = dR - dX, dH = dB - dY;
      if (dW <= 2 || dH <= 2) continue;
      const v = h(r * 10 + c, seed, 1);
      ctx.fillStyle = varyColor(pal.secondary, 12, v);
      ctx.fillRect(dX, dY, dW, dH);
      ctx.fillStyle = shiftColor(pal.secondary, 8); ctx.fillRect(dX, dY, dW, 1);
      ctx.fillStyle = shiftColor(pal.primary, -5); ctx.fillRect(dX, dY + dH - 1, dW, 1);
      ctx.fillStyle = shiftColor(pal.secondary, 4); ctx.fillRect(dX, dY + 1, 1, dH - 2);
    }
  }
  ctx.fillStyle = pal.mortar;
  for (let r = 1; r < (p.brickRows || 3); r++) {
    ctx.fillRect(x, y + r * bH - 1, size, mw);
    if (h(r, seed, 20) < (p.bleedChance || 0.05)) {
      ctx.fillStyle = hexAlpha(pal.accent, 0.4);
      ctx.fillRect(x + h(r, seed, 21) * (size - 12), y + r * bH - 1, 8 + h(r, seed, 22) * 6, mw);
      ctx.fillStyle = pal.mortar;
    }
  }
  if (h(0, seed, 30) < (p.crackDensity || 0.08)) {
    ctx.strokeStyle = hexAlpha(pal.accent, 0.5); ctx.lineWidth = 0.8; ctx.beginPath();
    const cx2 = x + size * (0.2 + h(0, seed, 31) * 0.6), cy2 = y + size * (0.2 + h(0, seed, 32) * 0.6);
    ctx.moveTo(cx2, cy2);
    for (let s = 0; s < 2 + Math.floor(h(0, seed, 33) * 3); s++) ctx.lineTo(cx2 + (h(s, seed, 34) - 0.5) * size * 0.5, cy2 + h(s, seed, 35) * size * 0.4);
    ctx.stroke();
  }
  if (p.edgeVignette) _edgeVig(ctx, x, y, size);
}

function drawWall_scorchedBrick(ctx, x, y, size, seed, pal, p) {
  const h = cellHash;
  ctx.fillStyle = pal.primary; ctx.fillRect(x, y, size, size);
  const bH = size / (p.brickRows || 3), bW = size / (p.brickCols || 2), mw = p.mortarWidth || 2;
  for (let r = 0; r < (p.brickRows || 3); r++) {
    const off = (r % 2 === 0) ? 0 : bW * 0.45;
    for (let c = -1; c <= (p.brickCols || 2); c++) {
      const bx = x + off + c * bW, by = y + r * bH;
      const dX = Math.max(x + mw, bx + mw), dY = by + mw, dR = Math.min(x + size - mw, bx + bW - mw), dB = by + bH - mw;
      const dW = dR - dX, dH = dB - dY;
      if (dW <= 2 || dH <= 2) continue;
      ctx.fillStyle = varyColor(pal.secondary, 10, h(r * 10 + c, seed, 1)); ctx.fillRect(dX, dY, dW, dH);
      if (h(r * 10 + c, seed, 5) < (p.scorchChance || 0.10)) { ctx.fillStyle = 'rgba(0,0,0,0.3)'; ctx.fillRect(dX, dY, dW, dH); }
      ctx.fillStyle = shiftColor(pal.secondary, 6); ctx.fillRect(dX, dY, dW, 1);
    }
  }
  for (let r = 1; r < (p.brickRows || 3); r++) {
    ctx.fillStyle = pal.mortar; ctx.fillRect(x, y + r * bH - 1, size, mw);
    if (h(r, seed, 20) < (p.emberChance || 0.06)) {
      const gx = x + h(r, seed, 21) * (size - 10), gw = 6 + h(r, seed, 22) * 8;
      ctx.fillStyle = hexAlpha(pal.accent, 0.6); ctx.fillRect(gx, y + r * bH - 1, gw, mw);
      ctx.fillStyle = hexAlpha(pal.highlight, 0.3); ctx.fillRect(gx + 2, y + r * bH - 1, gw - 4, mw);
    }
  }
  if (p.edgeVignette) _edgeVig(ctx, x, y, size);
}

function drawWall_mossyStone(ctx, x, y, size, seed, pal, p) {
  const h = cellHash;
  ctx.fillStyle = pal.primary; ctx.fillRect(x, y, size, size);
  const bH = size / (p.brickRows || 2), bW = size / (p.brickCols || 2), mw = p.mortarWidth || 2;
  for (let r = 0; r < (p.brickRows || 2); r++) {
    const off = (r % 2 === 0) ? 0 : bW * 0.35;
    for (let c = -1; c <= (p.brickCols || 2); c++) {
      const bx = x + off + c * bW, by = y + r * bH;
      const dX = Math.max(x + mw, bx + mw), dY = by + mw, dR = Math.min(x + size - mw, bx + bW - mw), dB = by + bH - mw;
      const dW = dR - dX, dH = dB - dY;
      if (dW <= 2 || dH <= 2) continue;
      ctx.fillStyle = varyColor(pal.secondary, 8, h(r * 10 + c, seed, 1)); ctx.fillRect(dX, dY, dW, dH);
      ctx.fillStyle = shiftColor(pal.secondary, 5); ctx.fillRect(dX, dY, dW, 2);
      if (h(r * 10 + c, seed, 10) < (p.mossChance || 0.0)) {
        ctx.fillStyle = hexAlpha(pal.accent, 0.4); ctx.beginPath();
        ctx.arc(dX + h(r * 10 + c, seed, 11) * (dW - 8) + 4, dY + h(r * 10 + c, seed, 12) * (dH - 6) + 3, 3 + h(r + c, seed, 13) * 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }
  if (h(0, seed, 40) < (p.waterStainChance || 0.0)) {
    const sx = x + 4 + h(0, seed, 41) * (size - 8);
    ctx.fillStyle = shiftColor(pal.primary, -8); ctx.fillRect(sx, y, 2, size);
  }
  if (h(0, seed, 50) < (p.veinChance || 0.0)) {
    ctx.strokeStyle = hexAlpha(pal.highlight, 0.35); ctx.lineWidth = 1; ctx.beginPath();
    const vx = x + h(0, seed, 51) * size * 0.6 + size * 0.2;
    ctx.moveTo(vx, y + 2);
    ctx.bezierCurveTo(vx + (h(0, seed, 52) - 0.5) * 10, y + size * 0.3, vx + (h(0, seed, 53) - 0.5) * 12, y + size * 0.7, vx + (h(0, seed, 54) - 0.5) * 8, y + size - 2);
    ctx.stroke(); ctx.strokeStyle = hexAlpha(pal.accent, 0.12); ctx.lineWidth = 3; ctx.stroke();
  }
  ctx.fillStyle = pal.mortar;
  for (let r = 1; r < (p.brickRows || 2); r++) ctx.fillRect(x, y + r * bH - 1, size, mw);
  if (p.edgeVignette) _edgeVig(ctx, x, y, size);
}

function drawWall_carvedStone(ctx, x, y, size, seed, pal, p) {
  const h = cellHash;
  ctx.fillStyle = pal.primary; ctx.fillRect(x, y, size, size);
  const bH = size / (p.brickRows || 2), bW = size / (p.brickCols || 2), mw = p.mortarWidth || 3;
  for (let r = 0; r < (p.brickRows || 2); r++) {
    for (let c = 0; c < (p.brickCols || 2); c++) {
      const bx = x + c * bW + mw, by = y + r * bH + mw, bw = bW - mw * 2, bh = bH - mw * 2;
      if (bw <= 2 || bh <= 2) continue;
      ctx.fillStyle = varyColor(pal.secondary, 10, h(r * 10 + c, seed, 1)); ctx.fillRect(bx, by, bw, bh);
      ctx.strokeStyle = shiftColor(pal.secondary, 12); ctx.lineWidth = 0.8; ctx.strokeRect(bx + 3, by + 3, bw - 6, bh - 6);
      if (h(r * 10 + c, seed, 15) < (p.crumbleChance || 0.05)) {
        const cn = Math.floor(h(r * 10 + c, seed, 16) * 4);
        ctx.fillStyle = pal.primary; ctx.fillRect(cn < 2 ? bx : bx + bw - 6, cn % 2 === 0 ? by : by + bh - 5, 5 + h(r + c, seed, 17) * 3, 4 + h(r + c, seed, 18) * 3);
      }
      if (h(r * 10 + c, seed, 20) < (p.iconChance || 0.0)) {
        ctx.strokeStyle = hexAlpha(pal.accent, 0.25); ctx.lineWidth = 1;
        const icx = bx + bw / 2, icy = by + bh / 2, it = Math.floor(h(r * 10 + c, seed, 21) * 3);
        ctx.beginPath();
        if (it === 0) { ctx.moveTo(icx, icy - 5); ctx.lineTo(icx, icy + 5); ctx.moveTo(icx - 4, icy - 1); ctx.lineTo(icx + 4, icy - 1); }
        else if (it === 1) { ctx.arc(icx, icy, 4, 0, Math.PI * 2); }
        else { ctx.moveTo(icx, icy - 5); ctx.lineTo(icx - 4, icy + 4); ctx.lineTo(icx + 4, icy + 4); ctx.closePath(); }
        ctx.stroke();
      }
    }
  }
  if (h(0, seed, 30) < (p.goldTrimChance || 0.04)) { ctx.fillStyle = hexAlpha(pal.highlight, 0.25); ctx.fillRect(x + 4, y + bH - 1, size - 8, 1); }
  ctx.fillStyle = pal.mortar;
  for (let r = 1; r < (p.brickRows || 2); r++) ctx.fillRect(x, y + r * bH - 1, size, mw);
  for (let c = 1; c < (p.brickCols || 2); c++) ctx.fillRect(x + c * bW - 1, y, mw, size);
  if (p.edgeVignette) _edgeVig(ctx, x, y, size);
}

function drawWall_ironPlate(ctx, x, y, size, seed, pal, p) {
  const h = cellHash;
  ctx.fillStyle = pal.primary; ctx.fillRect(x, y, size, size);
  const pH = size / (p.brickRows || 2), pW = size / (p.brickCols || 2), mw = p.mortarWidth || 1;
  for (let r = 0; r < (p.brickRows || 2); r++) {
    for (let c = 0; c < (p.brickCols || 2); c++) {
      const px2 = x + c * pW + mw, py2 = y + r * pH + mw, pw = pW - mw * 2, ph = pH - mw * 2;
      if (pw <= 2 || ph <= 2) continue;
      ctx.fillStyle = varyColor(pal.secondary, 8, h(r * 10 + c, seed, 1)); ctx.fillRect(px2, py2, pw, ph);
      ctx.fillStyle = shiftColor(pal.secondary, 5); ctx.fillRect(px2 + 2, py2 + ph * 0.3, pw - 4, ph * 0.15);
      ctx.fillStyle = shiftColor(pal.secondary, 10); ctx.fillRect(px2, py2, pw, 1);
      ctx.fillStyle = shiftColor(pal.primary, -5); ctx.fillRect(px2, py2 + ph - 1, pw, 1);
      if (h(r * 10 + c, seed, 10) < (p.rivetChance || 0.40)) {
        _rivet(ctx, px2 + 3, py2 + 3, pal); _rivet(ctx, px2 + pw - 4, py2 + 3, pal);
        _rivet(ctx, px2 + 3, py2 + ph - 4, pal); _rivet(ctx, px2 + pw - 4, py2 + ph - 4, pal);
      }
      if (h(r * 10 + c, seed, 20) < (p.rustChance || 0.08)) {
        ctx.fillStyle = hexAlpha(pal.accent, 0.35);
        const rx = px2 + h(r + c, seed, 21) * (pw - 6), rw = 3 + h(r + c, seed, 22) * 4, rh = ph * (0.4 + h(r + c, seed, 23) * 0.5);
        ctx.fillRect(rx, py2 + 2, rw, rh);
      }
    }
  }
  if (h(0, seed, 40) < (p.pipeChance || 0.0)) {
    const pipeY = y + size * 0.4 + h(0, seed, 41) * size * 0.2;
    ctx.fillStyle = shiftColor(pal.secondary, 15); ctx.fillRect(x, pipeY, size, 4);
    ctx.fillStyle = shiftColor(pal.secondary, 8); ctx.fillRect(x, pipeY + 1, size, 2);
  }
  ctx.fillStyle = pal.mortar;
  for (let r = 1; r < (p.brickRows || 2); r++) ctx.fillRect(x, y + r * pH, size, mw);
  for (let c = 1; c < (p.brickCols || 2); c++) ctx.fillRect(x + c * pW, y, mw, size);
  if (p.edgeVignette) _edgeVig(ctx, x, y, size);
}

function _edgeVig(ctx, x, y, s) {
  ctx.fillStyle = 'rgba(0,0,0,0.12)';
  ctx.fillRect(x, y, s, 2); ctx.fillRect(x, y + s - 2, s, 2);
  ctx.fillRect(x, y, 2, s); ctx.fillRect(x + s - 2, y, 2, s);
}

function _rivet(ctx, cx, cy, pal) {
  ctx.fillStyle = shiftColor(pal.secondary, 15); ctx.beginPath(); ctx.arc(cx, cy, 1.5, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = shiftColor(pal.secondary, -5); ctx.beginPath(); ctx.arc(cx + 0.5, cy + 0.5, 0.8, 0, Math.PI * 2); ctx.fill();
}

// ═══════════════════════════════════════════════════════════
//  FLOOR DRAWING FUNCTIONS
// ═══════════════════════════════════════════════════════════

function drawFloor_flagstone(ctx, x, y, size, seed, pal, p) {
  const h = cellHash, sg = p.slabGrid || 2, gw = p.groutWidth || 1, sW = size / sg;
  const texDots = p.textureDots != null ? p.textureDots : 1;
  ctx.fillStyle = pal.floor; ctx.fillRect(x, y, size, size);
  for (let r = 0; r < sg; r++) for (let c = 0; c < sg; c++) {
    const v = h(r * 3 + c, seed, 100);
    ctx.fillStyle = varyColor(pal.floor, 3, v);
    ctx.fillRect(x + c * sW + gw, y + r * sW + gw, sW - gw * 2, sW - gw * 2);
    for (let d = 0; d < texDots; d++) {
      ctx.fillStyle = shiftColor(pal.floor, h(d, seed, 107) < 0.5 ? 3 : -3);
      ctx.fillRect(x + c * sW + gw + h(r * 3 + c + d, seed, 105) * (sW - gw * 2), y + r * sW + gw + h(r * 3 + c + d, seed, 106) * (sW - gw * 2), 1, 1);
    }
  }
  if (h(0, seed, 110) < (p.stainChance || 0.0)) {
    ctx.fillStyle = p.stainColor || 'rgba(120,20,20,0.35)';
    ctx.beginPath(); ctx.arc(x + h(0, seed, 111) * (size - 10) + 7, y + h(0, seed, 112) * (size - 10) + 7, 3 + h(0, seed, 113) * 4, 0, Math.PI * 2); ctx.fill();
  }
  if (h(0, seed, 120) < (p.debrisChance || 0.0)) {
    ctx.fillStyle = p.debrisColor || '#4a4040';
    ctx.fillRect(x + h(0, seed, 121) * (size - 6) + 2, y + h(0, seed, 122) * (size - 6) + 2, 2, 1);
  }
}

function drawFloor_ashCovered(ctx, x, y, size, seed, pal, p) {
  const h = cellHash, sg = p.slabGrid || 2, gw = p.groutWidth || 1, sW = size / sg;
  ctx.fillStyle = pal.floor; ctx.fillRect(x, y, size, size);
  for (let r = 0; r < sg; r++) for (let c = 0; c < sg; c++) {
    ctx.fillStyle = varyColor(pal.floor, 3, h(r * 3 + c, seed, 100));
    ctx.fillRect(x + c * sW + gw, y + r * sW + gw, sW - gw * 2, sW - gw * 2);
  }
  const ac = Math.floor((p.ashDensity || 0.08) * 20);
  for (let i = 0; i < ac; i++) {
    ctx.fillStyle = `rgba(60,55,50,${0.2 + h(i, seed, 133) * 0.3})`;
    ctx.fillRect(x + h(i, seed, 130) * size, y + h(i, seed, 131) * size, 1 + h(i, seed, 132) * 2, 1 + h(i, seed, 132) * 1);
  }
  if (h(0, seed, 140) < (p.emberChance || 0.0)) {
    const ex = x + h(0, seed, 141) * (size - 4) + 2, ey = y + h(0, seed, 142) * (size - 4) + 2;
    ctx.fillStyle = hexAlpha(pal.highlight, 0.5); ctx.fillRect(ex, ey, 2, 2);
    ctx.fillStyle = hexAlpha(pal.accent, 0.15); ctx.beginPath(); ctx.arc(ex + 1, ey + 1, 3, 0, Math.PI * 2); ctx.fill();
  }
}

function drawFloor_flooded(ctx, x, y, size, seed, pal, p) {
  const h = cellHash, sg = p.slabGrid || 2, gw = p.groutWidth || 1, sW = size / sg;
  ctx.fillStyle = pal.floor; ctx.fillRect(x, y, size, size);
  for (let r = 0; r < sg; r++) for (let c = 0; c < sg; c++) {
    ctx.fillStyle = varyColor(pal.floor, 3, h(r * 3 + c, seed, 100));
    ctx.fillRect(x + c * sW + gw, y + r * sW + gw, sW - gw * 2, sW - gw * 2);
  }
  ctx.fillStyle = `rgba(10,30,50,${p.waterDepth || 0.08})`; ctx.fillRect(x, y, size, size);
  if (h(0, seed, 150) < (p.rippleChance || 0.0)) {
    const rx = x + size * 0.3 + h(0, seed, 151) * size * 0.4, ry = y + size * 0.3 + h(0, seed, 152) * size * 0.4;
    ctx.strokeStyle = hexAlpha(pal.accent, 0.10); ctx.lineWidth = 0.5;
    ctx.beginPath(); ctx.arc(rx, ry, 4 + h(0, seed, 153) * 5, 0, Math.PI * 2); ctx.stroke();
  }
}

function drawFloor_crackedMarble(ctx, x, y, size, seed, pal, p) {
  const h = cellHash, sg = p.slabGrid || 3, gw = p.groutWidth || 1, sW = size / sg;
  ctx.fillStyle = pal.floor; ctx.fillRect(x, y, size, size);
  for (let r = 0; r < sg; r++) for (let c = 0; c < sg; c++) {
    ctx.fillStyle = varyColor(pal.floor, 3, h(r * 3 + c, seed, 100));
    ctx.fillRect(x + c * sW + gw, y + r * sW + gw, sW - gw * 2, sW - gw * 2);
    if (h(r * 3 + c, seed, 105) < (p.veinChance || 0.0)) {
      ctx.strokeStyle = shiftColor(pal.floor, 6); ctx.lineWidth = 0.5; ctx.beginPath();
      ctx.moveTo(x + c * sW + gw + h(r + c, seed, 106) * (sW - gw * 2), y + r * sW + gw);
      ctx.lineTo(x + c * sW + sW - gw - h(r + c, seed, 107) * (sW - gw * 2) * 0.5, y + r * sW + sW - gw);
      ctx.stroke();
    }
  }
  if (h(0, seed, 170) < (p.crackChance || 0.0)) {
    ctx.strokeStyle = shiftColor(pal.grout, 5); ctx.lineWidth = 0.8; ctx.beginPath();
    ctx.moveTo(x + h(0, seed, 171) * size, y); ctx.lineTo(x + h(0, seed, 172) * size, y + size); ctx.stroke();
  }
  if (h(0, seed, 190) < (p.debrisChance || 0.0)) {
    ctx.fillStyle = p.debrisColor || '#3a3045';
    ctx.fillRect(x + h(0, seed, 191) * (size - 6) + 2, y + h(0, seed, 192) * (size - 6) + 2, 3, 2);
  }
}

function drawFloor_metalGrate(ctx, x, y, size, seed, pal, p) {
  const h = cellHash, gw = p.groutWidth || 2, sp = p.grateLineSpacing || 6;
  ctx.fillStyle = pal.grout; ctx.fillRect(x, y, size, size);
  ctx.fillStyle = pal.floor; ctx.fillRect(x + gw, y + gw, size - gw * 2, size - gw * 2);
  ctx.strokeStyle = shiftColor(pal.floor, -10); ctx.lineWidth = 1;
  for (let i = sp; i < size; i += sp) {
    ctx.beginPath(); ctx.moveTo(x + gw, y + i); ctx.lineTo(x + size - gw, y + i); ctx.stroke();
  }
  for (let i = sp; i < size; i += sp) {
    ctx.beginPath(); ctx.moveTo(x + i, y + gw); ctx.lineTo(x + i, y + size - gw); ctx.stroke();
  }
  ctx.strokeStyle = shiftColor(pal.floor, 5); ctx.lineWidth = 0.5;
  for (let i = sp; i < size; i += sp) { ctx.beginPath(); ctx.moveTo(x + gw, y + i - 1); ctx.lineTo(x + size - gw, y + i - 1); ctx.stroke(); }
  ctx.strokeStyle = shiftColor(pal.secondary, 5); ctx.lineWidth = 1; ctx.strokeRect(x + gw, y + gw, size - gw * 2, size - gw * 2);
  if (h(0, seed, 200) < (p.oilChance || 0.0)) {
    ctx.fillStyle = p.stainColor || 'rgba(90,60,30,0.30)'; ctx.beginPath();
    ctx.ellipse(x + h(0, seed, 201) * (size - 10) + 8, y + h(0, seed, 202) * (size - 10) + 7, 4 + h(0, seed, 203) * 3, 2 + h(0, seed, 204) * 2, 0, 0, Math.PI * 2);
    ctx.fill();
  }
}

// ═══════════════════════════════════════════════════════════
//  CORRIDOR + SPECIAL TILES
// ═══════════════════════════════════════════════════════════

function drawCorridor(ctx, x, y, size, seed, pal, theme) {
  const cs = theme.corridor?.style || 'worn_stone', h = cellHash, sW = size / 2;
  ctx.fillStyle = shiftColor(pal.floor, -3); ctx.fillRect(x, y, size, size);
  for (let r = 0; r < 2; r++) for (let c = 0; c < 2; c++) {
    ctx.fillStyle = varyColor(pal.floor, 3, h(r * 3 + c, seed, 200));
    ctx.fillRect(x + c * sW + 1, y + r * sW + 1, sW - 2, sW - 2);
  }
  switch (cs) {
    case 'worn_stone':
      if (h(0, seed, 210) < (theme.corridor.streakChance || 0.0)) {
        ctx.fillStyle = hexAlpha(pal.accent, 0.2); ctx.fillRect(x + size * 0.3 + h(0, seed, 211) * size * 0.3, y, 2, size);
      } break;
    case 'ash_trail': {
      const ac2 = Math.floor((theme.corridor.ashDensity || 0.15) * 25);
      for (let i = 0; i < ac2; i++) { ctx.fillStyle = `rgba(60,55,50,${0.15 + h(i, seed, 222) * 0.25})`; ctx.fillRect(x + h(i, seed, 220) * size, y + h(i, seed, 221) * size, 1 + h(i, seed, 223), 1); }
    } break;
    case 'shallow_water':
      ctx.fillStyle = `rgba(10,30,50,${theme.corridor.waterDepth || 0.15})`; ctx.fillRect(x, y, size, size); break;
    case 'worn_carpet': {
      const cW = size * 0.4; ctx.fillStyle = theme.corridor.carpetColor || 'rgba(80,40,50,0.20)';
      ctx.fillRect(x + (size - cW) / 2, y, cW, size);
      ctx.fillStyle = shiftColor(pal.floor, 3);
      ctx.fillRect(x + (size - cW) / 2 - 1, y, 1, size); ctx.fillRect(x + (size + cW) / 2, y, 1, size);
    } break;
    case 'walkway':
      if (theme.corridor.railHint) {
        ctx.fillStyle = shiftColor(pal.secondary, 8); ctx.fillRect(x, y, 2, size); ctx.fillRect(x + size - 2, y, 2, size);
        ctx.fillStyle = shiftColor(pal.secondary, 3); ctx.fillRect(x + 2, y, 1, size); ctx.fillRect(x + size - 3, y, 1, size);
      } break;
  }
}

function drawSpawn(ctx, x, y, size, seed, pal, theme) {
  drawCorridor(ctx, x, y, size, seed, pal, theme);
  ctx.strokeStyle = hexAlpha(pal.accent, 0.15); ctx.lineWidth = 1;
  ctx.beginPath(); ctx.arc(x + size / 2, y + size / 2, size * 0.3, 0, Math.PI * 2); ctx.stroke();
}

// ═══════════════════════════════════════════════════════════
//  DISPATCH MAPS
// ═══════════════════════════════════════════════════════════

const WALL_FN = { cracked_stone: drawWall_crackedStone, scorched_brick: drawWall_scorchedBrick, mossy_stone: drawWall_mossyStone, carved_stone: drawWall_carvedStone, iron_plate: drawWall_ironPlate };
const FLOOR_FN = { flagstone: drawFloor_flagstone, ash_covered: drawFloor_ashCovered, flooded: drawFloor_flooded, cracked_marble: drawFloor_crackedMarble, metal_grate: drawFloor_metalGrate };

// ═══════════════════════════════════════════════════════════
//  THEME ENGINE CLASS
// ═══════════════════════════════════════════════════════════

const VARIANTS = 8;

export class ThemeEngine {
  constructor() {
    this.theme = null;
    this.tileSize = 48;
    this.cache = new Map();
    this._ready = false;
  }

  /** Load a theme by ID or config object. Rebuilds tile cache. */
  setTheme(themeOrId, tileSize = 48) {
    this.theme = typeof themeOrId === 'string' ? (BUILT_IN_THEMES[themeOrId] || BUILT_IN_THEMES.bleeding_catacombs) : themeOrId;
    this.tileSize = tileSize;
    this._buildCache();
    this._ready = true;
  }

  isReady() { return this._ready && this.theme !== null; }
  getTheme() { return this.theme; }
  getThemeId() { return this.theme?.id || null; }

  /** Get all available built-in theme IDs. */
  static getThemeIds() { return Object.keys(BUILT_IN_THEMES); }
  static getThemes() { return BUILT_IN_THEMES; }

  /**
   * Draw a themed tile. Returns true if drawn.
   * @param {CanvasRenderingContext2D} ctx
   * @param {string} tileType - wall/floor/corridor/spawn/door/chest/stairs
   * @param {number} px - Pixel X
   * @param {number} py - Pixel Y
   * @param {number} gridX - Grid coordinate X
   * @param {number} gridY - Grid coordinate Y
   * @param {Object} extra - { doorOpen, chestOpened }
   */
  drawTile(ctx, tileType, px, py, gridX, gridY, extra = {}) {
    if (!this._ready) return false;

    // Cached tile types
    if (tileType === 'wall' || tileType === 'floor' || tileType === 'corridor' || tileType === 'spawn') {
      const key = `${tileType}_${this._variant(gridX, gridY)}`;
      const cached = this.cache.get(key);
      if (cached) { ctx.drawImage(cached, px, py); return true; }
    }

    // State-dependent tiles drawn directly
    const s = this.tileSize, seed = this._seed(gridX, gridY), pal = this.theme.palette;
    switch (tileType) {
      case 'door': {
        drawCorridor(ctx, px, py, s, seed, pal, this.theme);
        const isOpen = extra.doorOpen === true;
        if (isOpen) {
          const dc = lerpColor(pal.accent, '#8B4513', 0.5);
          ctx.strokeStyle = dc; ctx.lineWidth = 2; ctx.strokeRect(px + 4, py + 4, s - 8, s - 8);
          ctx.fillStyle = dc; ctx.font = `${s * 0.22}px sans-serif`; ctx.textAlign = 'center';
          ctx.fillText('○', px + s / 2, py + s / 2 + s * 0.08);
        } else {
          const wd = lerpColor(pal.secondary, '#5C3310', 0.6), wl = lerpColor(pal.secondary, '#8B4513', 0.5);
          ctx.fillStyle = wd; ctx.fillRect(px + 4, py + 4, s - 8, s - 8);
          ctx.strokeStyle = wl; ctx.lineWidth = 0.5;
          for (let i = 0; i < 3; i++) { const ly = py + 8 + i * (s - 16) / 3; ctx.beginPath(); ctx.moveTo(px + 6, ly); ctx.lineTo(px + s - 6, ly); ctx.stroke(); }
          ctx.strokeStyle = shiftColor(wd, -10); ctx.lineWidth = 1; ctx.strokeRect(px + 4, py + 4, s - 8, s - 8);
          ctx.fillStyle = pal.highlight || '#DAA520'; ctx.beginPath(); ctx.arc(px + s / 2 + 6, py + s / 2, 2, 0, Math.PI * 2); ctx.fill();
        }
        return true;
      }
      case 'chest': {
        const floorFn = FLOOR_FN[this.theme.floor.style] || drawFloor_flagstone;
        floorFn(ctx, px, py, s, seed, pal, this.theme.floor);
        const isOpened = extra.chestOpened === true;
        const cc = isOpened ? shiftColor(pal.accent, -20) : (pal.highlight || '#DAA520');
        const cw = s * 0.5, ch = s * 0.4, cx2 = px + (s - cw) / 2, cy2 = py + (s - ch) / 2;
        ctx.fillStyle = cc; ctx.fillRect(cx2, cy2, cw, ch);
        ctx.strokeStyle = shiftColor(pal.primary, 10); ctx.lineWidth = 1; ctx.strokeRect(cx2, cy2, cw, ch);
        if (!isOpened) { ctx.fillStyle = pal.highlight || '#FFD700'; ctx.fillRect(cx2 + cw / 2 - 3, cy2 + ch / 2 - 2, 6, 4); }
        else { ctx.strokeStyle = shiftColor(cc, 10); ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(cx2, cy2); ctx.lineTo(cx2 + cw, cy2); ctx.stroke(); }
        return true;
      }
      case 'stairs': {
        drawCorridor(ctx, px, py, s, seed, pal, this.theme);
        const sc = lerpColor(pal.accent, '#88CC88', 0.3), bc = shiftColor(sc, -15);
        const stW = s * 0.55, stH = s * 0.12, stX = px + (s - stW) / 2;
        for (let i = 0; i < 3; i++) {
          const sy = py + s * 0.22 + i * (stH + 2), sw = stW - i * 4, sx = stX + i * 2;
          ctx.fillStyle = sc; ctx.fillRect(sx, sy, sw, stH);
          ctx.strokeStyle = bc; ctx.lineWidth = 1; ctx.strokeRect(sx, sy, sw, stH);
        }
        ctx.fillStyle = sc; ctx.font = `${s * 0.3}px sans-serif`; ctx.textAlign = 'center'; ctx.fillText('▼', px + s / 2, py + s - 3);
        return true;
      }
      default: {
        // Fall back to wall
        const key = `wall_${this._variant(gridX, gridY)}`;
        const cached = this.cache.get(key);
        if (cached) { ctx.drawImage(cached, px, py); return true; }
        return false;
      }
    }
  }

  /**
   * Draw themed fog of war.
   */
  drawFog(ctx, gridWidth, gridHeight, visibleTiles, offsetX, offsetY, revealedTiles) {
    if (!visibleTiles) return;
    const fog = this.theme?.fog || {};
    const eTint = fog.exploredTint || 'rgba(0,0,0,0.6)';
    const uColor = fog.unexploredColor || 'rgba(0,0,0,1.0)';
    for (let x = 0; x < gridWidth; x++) {
      for (let y = 0; y < gridHeight; y++) {
        if (visibleTiles.has(`${x},${y}`)) continue;
        ctx.fillStyle = (revealedTiles && revealedTiles.has(`${x},${y}`)) ? eTint : (revealedTiles ? uColor : 'rgba(0,0,0,0.7)');
        ctx.fillRect((x - offsetX) * this.tileSize, (y - offsetY) * this.tileSize, this.tileSize, this.tileSize);
      }
    }
  }

  // ── Internal ──

  _buildCache() {
    this.cache.clear();
    if (!this.theme) return;
    const s = this.tileSize, pal = this.theme.palette;
    const wFn = WALL_FN[this.theme.wall?.style] || drawWall_crackedStone;
    const fFn = FLOOR_FN[this.theme.floor?.style] || drawFloor_flagstone;
    for (let v = 0; v < VARIANTS; v++) {
      let c = this._mkCanvas(s); wFn(c.getContext('2d'), 0, 0, s, v * 137, pal, this.theme.wall); this.cache.set(`wall_${v}`, c);
      c = this._mkCanvas(s); fFn(c.getContext('2d'), 0, 0, s, v * 251, pal, this.theme.floor); this.cache.set(`floor_${v}`, c);
      c = this._mkCanvas(s); drawCorridor(c.getContext('2d'), 0, 0, s, v * 349, pal, this.theme); this.cache.set(`corridor_${v}`, c);
      c = this._mkCanvas(s); drawSpawn(c.getContext('2d'), 0, 0, s, v * 503, pal, this.theme); this.cache.set(`spawn_${v}`, c);
    }
  }

  _mkCanvas(s) {
    if (typeof OffscreenCanvas !== 'undefined') return new OffscreenCanvas(s, s);
    const c = document.createElement('canvas'); c.width = s; c.height = s; return c;
  }

  _variant(gx, gy) { return Math.floor(cellHash(gx, gy, 0) * VARIANTS); }
  _seed(gx, gy) { return ((gx * 7919) + (gy * 6271)) & 0x7FFFFFFF; }
}

/**
 * Singleton instance for game use.
 * Import in dungeonRenderer.js: import { themeEngine } from './ThemeEngine.js';
 */
export const themeEngine = new ThemeEngine();
