// ─────────────────────────────────────────────────────────
// tilePatterns.js — Procedural tile drawing algorithms
//
// Each function draws a single tile onto an offscreen canvas
// using only Canvas 2D API calls. No sprites required.
//
// Five wall styles + five floor styles, one per dungeon biome.
// Shared drawing helpers for doors, chests, stairs, corridors.
//
// All drawing is deterministic given a seed value, so the
// same grid position always produces the same tile appearance.
// ─────────────────────────────────────────────────────────

import { cellHash, varyColor, shiftColor, hexAlpha, lerpColor, hexToRgb, rgbToCSS } from './noiseUtils.js';

// ═══════════════════════════════════════════════════════════
//  WALL STYLES
// ═══════════════════════════════════════════════════════════

/**
 * Bleeding Catacombs wall — cracked stone blocks with red mortar
 * bleeding through joints. Deep underground crypt aesthetic.
 */
export function drawWall_crackedStone(ctx, x, y, size, seed, palette, params) {
  const { brickRows = 3, brickCols = 2, mortarWidth = 2, crackDensity = 0.08, bleedChance = 0.05 } = params;
  const h = cellHash;

  // Base fill
  ctx.fillStyle = palette.primary;
  ctx.fillRect(x, y, size, size);

  const brickH = size / brickRows;
  const brickW = size / brickCols;

  // Draw stone blocks
  for (let r = 0; r < brickRows; r++) {
    const rowOffset = (r % 2 === 0) ? 0 : brickW * 0.5;
    for (let c = -1; c <= brickCols; c++) {
      const bx = x + rowOffset + c * brickW;
      const by = y + r * brickH;

      // Clip to tile bounds
      const drawX = Math.max(x + mortarWidth, bx + mortarWidth);
      const drawY = by + mortarWidth;
      const drawR = Math.min(x + size - mortarWidth, bx + brickW - mortarWidth);
      const drawB = by + brickH - mortarWidth;
      const drawW = drawR - drawX;
      const drawH = drawB - drawY;

      if (drawW <= 2 || drawH <= 2) continue;

      // Stone face with color variation
      const v = h(r * 10 + c, seed, 1);
      ctx.fillStyle = varyColor(palette.secondary, 12, v);
      ctx.fillRect(drawX, drawY, drawW, drawH);

      // Top edge highlight (ambient light from above)
      ctx.fillStyle = shiftColor(palette.secondary, 8);
      ctx.fillRect(drawX, drawY, drawW, 1);

      // Bottom edge shadow
      ctx.fillStyle = shiftColor(palette.primary, -5);
      ctx.fillRect(drawX, drawY + drawH - 1, drawW, 1);

      // Left edge slight highlight
      ctx.fillStyle = shiftColor(palette.secondary, 4);
      ctx.fillRect(drawX, drawY + 1, 1, drawH - 2);
    }
  }

  // Mortar lines — some bleed red
  ctx.fillStyle = palette.mortar;
  for (let r = 1; r < brickRows; r++) {
    const my = y + r * brickH - 1;
    ctx.fillRect(x, my, size, mortarWidth);

    // Random mortar bleed
    if (h(r, seed, 20) < bleedChance) {
      ctx.fillStyle = hexAlpha(palette.accent, 0.4);
      const bleedX = x + h(r, seed, 21) * (size - 12);
      ctx.fillRect(bleedX, my, 8 + h(r, seed, 22) * 6, mortarWidth);
      ctx.fillStyle = palette.mortar;
    }
  }

  // Cracks
  if (h(0, seed, 30) < crackDensity) {
    ctx.strokeStyle = hexAlpha(palette.accent, 0.5);
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    const cx = x + size * (0.2 + h(0, seed, 31) * 0.6);
    const cy = y + size * (0.2 + h(0, seed, 32) * 0.6);
    ctx.moveTo(cx, cy);
    const segments = 2 + Math.floor(h(0, seed, 33) * 3);
    for (let s = 0; s < segments; s++) {
      const nx = cx + (h(s, seed, 34) - 0.5) * size * 0.5;
      const ny = cy + h(s, seed, 35) * size * 0.4;
      ctx.lineTo(nx, ny);
    }
    ctx.stroke();
  }

  // Edge vignette
  if (params.edgeVignette) {
    _drawEdgeVignette(ctx, x, y, size, 'rgba(0,0,0,0.15)');
  }
}

/**
 * Ashen Undercroft wall — scorched bricks with ember glow
 * in mortar cracks. Charred, burnt aesthetic.
 */
export function drawWall_scorchedBrick(ctx, x, y, size, seed, palette, params) {
  const { brickRows = 3, brickCols = 2, mortarWidth = 2, emberChance = 0.06, scorchChance = 0.10 } = params;
  const h = cellHash;

  // Base fill — charcoal
  ctx.fillStyle = palette.primary;
  ctx.fillRect(x, y, size, size);

  const brickH = size / brickRows;
  const brickW = size / brickCols;

  // Draw scorched bricks
  for (let r = 0; r < brickRows; r++) {
    const rowOffset = (r % 2 === 0) ? 0 : brickW * 0.45;
    for (let c = -1; c <= brickCols; c++) {
      const bx = x + rowOffset + c * brickW;
      const by = y + r * brickH;

      const drawX = Math.max(x + mortarWidth, bx + mortarWidth);
      const drawY = by + mortarWidth;
      const drawR = Math.min(x + size - mortarWidth, bx + brickW - mortarWidth);
      const drawB = by + brickH - mortarWidth;
      const drawW = drawR - drawX;
      const drawH = drawB - drawY;

      if (drawW <= 2 || drawH <= 2) continue;

      // Brick face
      const v = h(r * 10 + c, seed, 1);
      ctx.fillStyle = varyColor(palette.secondary, 10, v);
      ctx.fillRect(drawX, drawY, drawW, drawH);

      // Scorch darkening on some bricks
      if (h(r * 10 + c, seed, 5) < scorchChance) {
        ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
        ctx.fillRect(drawX, drawY, drawW, drawH);
      }

      // Top highlight
      ctx.fillStyle = shiftColor(palette.secondary, 6);
      ctx.fillRect(drawX, drawY, drawW, 1);
    }
  }

  // Mortar with ember glow
  for (let r = 1; r < brickRows; r++) {
    const my = y + r * brickH - 1;
    ctx.fillStyle = palette.mortar;
    ctx.fillRect(x, my, size, mortarWidth);

    if (h(r, seed, 20) < emberChance) {
      // Ember glow in mortar
      const glowX = x + h(r, seed, 21) * (size - 10);
      const glowW = 6 + h(r, seed, 22) * 8;
      ctx.fillStyle = hexAlpha(palette.accent, 0.6);
      ctx.fillRect(glowX, my, glowW, mortarWidth);
      // Brighter center
      ctx.fillStyle = hexAlpha(palette.highlight, 0.3);
      ctx.fillRect(glowX + 2, my, glowW - 4, mortarWidth);
    }
  }

  // Vertical mortar ember hints
  for (let r = 0; r < brickRows; r++) {
    const rowOffset = (r % 2 === 0) ? 0 : brickW * 0.45;
    for (let c = 0; c <= brickCols; c++) {
      const mx = x + rowOffset + c * brickW;
      if (mx > x + 2 && mx < x + size - 2 && h(r + c * 7, seed, 25) < emberChance * 0.5) {
        ctx.fillStyle = hexAlpha(palette.accent, 0.4);
        ctx.fillRect(mx - 1, y + r * brickH, mortarWidth, brickH);
      }
    }
  }

  if (params.edgeVignette) {
    _drawEdgeVignette(ctx, x, y, size, 'rgba(0,0,0,0.12)');
  }
}

/**
 * Drowned Sanctum wall — mossy wet stone with bioluminescent
 * veins and vertical water stain streaks.
 */
export function drawWall_mossyStone(ctx, x, y, size, seed, palette, params) {
  const { brickRows = 2, brickCols = 2, mortarWidth = 2, mossChance = 0.0, waterStainChance = 0.0, veinChance = 0.0 } = params;
  const h = cellHash;

  // Base fill — deep ocean
  ctx.fillStyle = palette.primary;
  ctx.fillRect(x, y, size, size);

  const brickH = size / brickRows;
  const brickW = size / brickCols;

  // Draw large stone blocks
  for (let r = 0; r < brickRows; r++) {
    const rowOffset = (r % 2 === 0) ? 0 : brickW * 0.35;
    for (let c = -1; c <= brickCols; c++) {
      const bx = x + rowOffset + c * brickW;
      const by = y + r * brickH;

      const drawX = Math.max(x + mortarWidth, bx + mortarWidth);
      const drawY = by + mortarWidth;
      const drawR = Math.min(x + size - mortarWidth, bx + brickW - mortarWidth);
      const drawB = by + brickH - mortarWidth;
      const drawW = drawR - drawX;
      const drawH = drawB - drawY;

      if (drawW <= 2 || drawH <= 2) continue;

      // Wet stone face
      const v = h(r * 10 + c, seed, 1);
      ctx.fillStyle = varyColor(palette.secondary, 8, v);
      ctx.fillRect(drawX, drawY, drawW, drawH);

      // Wet sheen — subtle lighter bar near top
      ctx.fillStyle = shiftColor(palette.secondary, 5);
      ctx.fillRect(drawX, drawY, drawW, 2);

      // Moss patches
      if (h(r * 10 + c, seed, 10) < mossChance) {
        const mossX = drawX + h(r * 10 + c, seed, 11) * (drawW - 8);
        const mossY = drawY + h(r * 10 + c, seed, 12) * (drawH - 6);
        ctx.fillStyle = hexAlpha(palette.accent, 0.4);
        ctx.beginPath();
        ctx.arc(mossX + 4, mossY + 3, 3 + h(r + c, seed, 13) * 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  // Water drip stains
  if (h(0, seed, 40) < waterStainChance) {
    const sx = x + 4 + h(0, seed, 41) * (size - 8);
    ctx.fillStyle = shiftColor(palette.primary, -8);
    ctx.fillRect(sx, y, 2, size);
    ctx.fillStyle = shiftColor(palette.primary, -4);
    ctx.fillRect(sx + 2, y + 4, 1, size - 8);
  }

  // Bioluminescent vein
  if (h(0, seed, 50) < veinChance) {
    ctx.strokeStyle = hexAlpha(palette.highlight, 0.35);
    ctx.lineWidth = 1;
    ctx.beginPath();
    const vx = x + h(0, seed, 51) * size * 0.6 + size * 0.2;
    ctx.moveTo(vx, y + 2);
    ctx.bezierCurveTo(
      vx + (h(0, seed, 52) - 0.5) * 10, y + size * 0.3,
      vx + (h(0, seed, 53) - 0.5) * 12, y + size * 0.7,
      vx + (h(0, seed, 54) - 0.5) * 8, y + size - 2
    );
    ctx.stroke();
    // Glow around vein
    ctx.strokeStyle = hexAlpha(palette.accent, 0.12);
    ctx.lineWidth = 3;
    ctx.stroke();
  }

  // Mortar
  ctx.fillStyle = palette.mortar;
  for (let r = 1; r < brickRows; r++) {
    ctx.fillRect(x, y + r * brickH - 1, size, mortarWidth);
  }

  if (params.edgeVignette) {
    _drawEdgeVignette(ctx, x, y, size, 'rgba(0,0,0,0.12)');
  }
}

/**
 * Hollowed Cathedral wall — grand carved stone with faded
 * icons, crumbling edges, and gold trim remnants.
 */
export function drawWall_carvedStone(ctx, x, y, size, seed, palette, params) {
  const { brickRows = 2, brickCols = 2, mortarWidth = 3, iconChance = 0.0, crumbleChance = 0.05, goldTrimChance = 0.04 } = params;
  const h = cellHash;

  // Base fill
  ctx.fillStyle = palette.primary;
  ctx.fillRect(x, y, size, size);

  const brickH = size / brickRows;
  const brickW = size / brickCols;

  // Large carved blocks
  for (let r = 0; r < brickRows; r++) {
    for (let c = 0; c < brickCols; c++) {
      const bx = x + c * brickW + mortarWidth;
      const by = y + r * brickH + mortarWidth;
      const bw = brickW - mortarWidth * 2;
      const bh = brickH - mortarWidth * 2;

      if (bw <= 2 || bh <= 2) continue;

      // Carved stone face
      const v = h(r * 10 + c, seed, 1);
      ctx.fillStyle = varyColor(palette.secondary, 10, v);
      ctx.fillRect(bx, by, bw, bh);

      // Carved inset border (1px inset lighter line)
      ctx.strokeStyle = shiftColor(palette.secondary, 12);
      ctx.lineWidth = 0.8;
      ctx.strokeRect(bx + 3, by + 3, bw - 6, bh - 6);

      // Crumbling corner
      if (h(r * 10 + c, seed, 15) < crumbleChance) {
        const corner = Math.floor(h(r * 10 + c, seed, 16) * 4);
        const cx2 = corner < 2 ? bx : bx + bw - 6;
        const cy2 = corner % 2 === 0 ? by : by + bh - 5;
        ctx.fillStyle = palette.primary;
        ctx.fillRect(cx2, cy2, 5 + h(r + c, seed, 17) * 3, 4 + h(r + c, seed, 18) * 3);
      }

      // Faded icon
      if (h(r * 10 + c, seed, 20) < iconChance) {
        ctx.strokeStyle = hexAlpha(palette.accent, 0.25);
        ctx.lineWidth = 1;
        const icx = bx + bw / 2;
        const icy = by + bh / 2;
        const iconType = Math.floor(h(r * 10 + c, seed, 21) * 3);
        if (iconType === 0) {
          // Cross
          ctx.beginPath();
          ctx.moveTo(icx, icy - 5); ctx.lineTo(icx, icy + 5);
          ctx.moveTo(icx - 4, icy - 1); ctx.lineTo(icx + 4, icy - 1);
          ctx.stroke();
        } else if (iconType === 1) {
          // Circle
          ctx.beginPath();
          ctx.arc(icx, icy, 4, 0, Math.PI * 2);
          ctx.stroke();
        } else {
          // Triangle
          ctx.beginPath();
          ctx.moveTo(icx, icy - 5);
          ctx.lineTo(icx - 4, icy + 4);
          ctx.lineTo(icx + 4, icy + 4);
          ctx.closePath();
          ctx.stroke();
        }
      }
    }
  }

  // Gold trim in mortar
  if (h(0, seed, 30) < goldTrimChance) {
    ctx.fillStyle = hexAlpha(palette.highlight, 0.25);
    const trimY = y + brickH - 1;
    ctx.fillRect(x + 4, trimY, size - 8, 1);
  }

  // Mortar
  ctx.fillStyle = palette.mortar;
  for (let r = 1; r < brickRows; r++) {
    ctx.fillRect(x, y + r * brickH - 1, size, mortarWidth);
  }
  for (let c = 1; c < brickCols; c++) {
    ctx.fillRect(x + c * brickW - 1, y, mortarWidth, size);
  }

  if (params.edgeVignette) {
    _drawEdgeVignette(ctx, x, y, size, 'rgba(0,0,0,0.10)');
  }
}

/**
 * Iron Depths wall — riveted metal panels with rust streaks.
 * Industrial, mechanical aesthetic.
 */
export function drawWall_ironPlate(ctx, x, y, size, seed, palette, params) {
  const { brickRows = 2, brickCols = 2, mortarWidth = 1, rivetChance = 0.40, rustChance = 0.08, pipeChance = 0.0 } = params;
  const h = cellHash;

  // Base fill — dark steel
  ctx.fillStyle = palette.primary;
  ctx.fillRect(x, y, size, size);

  const panelH = size / brickRows;
  const panelW = size / brickCols;

  // Metal panels
  for (let r = 0; r < brickRows; r++) {
    for (let c = 0; c < brickCols; c++) {
      const px2 = x + c * panelW + mortarWidth;
      const py2 = y + r * panelH + mortarWidth;
      const pw = panelW - mortarWidth * 2;
      const ph = panelH - mortarWidth * 2;

      if (pw <= 2 || ph <= 2) continue;

      // Metal face with slight vertical gradient (lighter center)
      const v = h(r * 10 + c, seed, 1);
      ctx.fillStyle = varyColor(palette.secondary, 8, v);
      ctx.fillRect(px2, py2, pw, ph);

      // Subtle center lighter stripe
      ctx.fillStyle = shiftColor(palette.secondary, 5);
      ctx.fillRect(px2 + 2, py2 + ph * 0.3, pw - 4, ph * 0.15);

      // Panel seam highlight (top)
      ctx.fillStyle = shiftColor(palette.secondary, 10);
      ctx.fillRect(px2, py2, pw, 1);

      // Panel seam shadow (bottom)
      ctx.fillStyle = shiftColor(palette.primary, -5);
      ctx.fillRect(px2, py2 + ph - 1, pw, 1);

      // Rivets at corners
      if (h(r * 10 + c, seed, 10) < rivetChance) {
        _drawRivet(ctx, px2 + 3, py2 + 3, palette);
        _drawRivet(ctx, px2 + pw - 4, py2 + 3, palette);
        _drawRivet(ctx, px2 + 3, py2 + ph - 4, palette);
        _drawRivet(ctx, px2 + pw - 4, py2 + ph - 4, palette);
      }

      // Rust streak
      if (h(r * 10 + c, seed, 20) < rustChance) {
        ctx.fillStyle = hexAlpha(palette.accent, 0.35);
        const rx = px2 + h(r + c, seed, 21) * (pw - 6);
        const ry = py2 + 2;
        const rw = 3 + h(r + c, seed, 22) * 4;
        const rh = ph * (0.4 + h(r + c, seed, 23) * 0.5);
        ctx.fillRect(rx, ry, rw, rh);
        // Darker rust center
        ctx.fillStyle = hexAlpha(palette.accent, 0.2);
        ctx.fillRect(rx + 1, ry + 2, rw - 2, rh - 4);
      }
    }
  }

  // Pipe segment hint
  if (h(0, seed, 40) < pipeChance) {
    const pipeY = y + size * 0.4 + h(0, seed, 41) * size * 0.2;
    ctx.fillStyle = shiftColor(palette.secondary, 15);
    ctx.fillRect(x, pipeY, size, 4);
    ctx.fillStyle = shiftColor(palette.secondary, 8);
    ctx.fillRect(x, pipeY + 1, size, 2);
    ctx.fillStyle = shiftColor(palette.primary, -3);
    ctx.fillRect(x, pipeY + 4, size, 1);
  }

  // Seam lines
  ctx.fillStyle = palette.mortar;
  for (let r = 1; r < brickRows; r++) {
    ctx.fillRect(x, y + r * panelH, size, mortarWidth);
  }
  for (let c = 1; c < brickCols; c++) {
    ctx.fillRect(x + c * panelW, y, mortarWidth, size);
  }

  if (params.edgeVignette) {
    _drawEdgeVignette(ctx, x, y, size, 'rgba(0,0,0,0.10)');
  }
}

// ═══════════════════════════════════════════════════════════
//  FLOOR STYLES
// ═══════════════════════════════════════════════════════════

/**
 * Bleeding Catacombs floor — worn flagstone with blood stains
 * and scattered bone debris.
 */
export function drawFloor_flagstone(ctx, x, y, size, seed, palette, params) {
  const { slabGrid = 2, groutWidth = 1, stainChance = 0.0, debrisChance = 0.0, textureDots = 1 } = params;
  const h = cellHash;

  // Base floor fill
  ctx.fillStyle = palette.floor;
  ctx.fillRect(x, y, size, size);

  const slabW = size / slabGrid;
  const slabH = size / slabGrid;

  // Flagstone slabs
  for (let r = 0; r < slabGrid; r++) {
    for (let c = 0; c < slabGrid; c++) {
      const sx = x + c * slabW + groutWidth;
      const sy = y + r * slabH + groutWidth;
      const sw = slabW - groutWidth * 2;
      const sh = slabH - groutWidth * 2;

      const v = h(r * 3 + c, seed, 100);
      ctx.fillStyle = varyColor(palette.floor, 3, v);
      ctx.fillRect(sx, sy, sw, sh);

      // Subtle surface texture — tiny dots (controllable via textureDots param)
      const dotCount = Math.min(textureDots, 3);
      for (let d = 0; d < dotCount; d++) {
        const dx = sx + h(r * 3 + c + d, seed, 105) * sw;
        const dy = sy + h(r * 3 + c + d, seed, 106) * sh;
        ctx.fillStyle = shiftColor(palette.floor, h(d, seed, 107) < 0.5 ? 3 : -3);
        ctx.fillRect(dx, dy, 1, 1);
      }
    }
  }

  // Blood stain
  if (h(0, seed, 110) < stainChance) {
    ctx.fillStyle = params.stainColor || 'rgba(120, 20, 20, 0.35)';
    const stainX = x + h(0, seed, 111) * (size - 10) + 3;
    const stainY = y + h(0, seed, 112) * (size - 10) + 3;
    ctx.beginPath();
    ctx.arc(stainX + 4, stainY + 4, 3 + h(0, seed, 113) * 4, 0, Math.PI * 2);
    ctx.fill();
  }

  // Debris
  if (h(0, seed, 120) < debrisChance) {
    ctx.fillStyle = params.debrisColor || '#4a4040';
    const debX = x + h(0, seed, 121) * (size - 6) + 2;
    const debY = y + h(0, seed, 122) * (size - 6) + 2;
    ctx.fillRect(debX, debY, 2, 1);
    ctx.fillRect(debX + 3, debY + 1, 1, 2);
  }
}

/**
 * Ashen Undercroft floor — ash-dusted stone with ember dots
 * and subtle tile pattern visible underneath ash.
 */
export function drawFloor_ashCovered(ctx, x, y, size, seed, palette, params) {
  const { slabGrid = 2, groutWidth = 1, ashDensity = 0.08, emberChance = 0.0 } = params;
  const h = cellHash;

  // Base floor
  ctx.fillStyle = palette.floor;
  ctx.fillRect(x, y, size, size);

  const slabW = size / slabGrid;
  const slabH = size / slabGrid;

  // Underlying tile pattern (barely visible under ash)
  for (let r = 0; r < slabGrid; r++) {
    for (let c = 0; c < slabGrid; c++) {
      const sx = x + c * slabW + groutWidth;
      const sy = y + r * slabH + groutWidth;
      const sw = slabW - groutWidth * 2;
      const sh = slabH - groutWidth * 2;

      const v = h(r * 3 + c, seed, 100);
      ctx.fillStyle = varyColor(palette.floor, 3, v);
      ctx.fillRect(sx, sy, sw, sh);
    }
  }

  // Ash layer — scattered semi-transparent grey dots
  const ashCount = Math.floor(ashDensity * 20);
  for (let i = 0; i < ashCount; i++) {
    const ax = x + h(i, seed, 130) * size;
    const ay = y + h(i, seed, 131) * size;
    const asize = 1 + h(i, seed, 132) * 2;
    ctx.fillStyle = `rgba(60, 55, 50, ${0.2 + h(i, seed, 133) * 0.3})`;
    ctx.fillRect(ax, ay, asize, asize);
  }

  // Ember dots
  if (h(0, seed, 140) < emberChance) {
    const ex = x + h(0, seed, 141) * (size - 4) + 2;
    const ey = y + h(0, seed, 142) * (size - 4) + 2;
    ctx.fillStyle = hexAlpha(palette.highlight, 0.5);
    ctx.fillRect(ex, ey, 2, 2);
    // Glow
    ctx.fillStyle = hexAlpha(palette.accent, 0.15);
    ctx.beginPath();
    ctx.arc(ex + 1, ey + 1, 3, 0, Math.PI * 2);
    ctx.fill();
  }
}

/**
 * Drowned Sanctum floor — water-logged dark stone with
 * blue tint and subtle ripple marks.
 */
export function drawFloor_flooded(ctx, x, y, size, seed, palette, params) {
  const { slabGrid = 2, groutWidth = 1, waterDepth = 0.08, rippleChance = 0.0 } = params;
  const h = cellHash;

  // Base floor (dark)
  ctx.fillStyle = palette.floor;
  ctx.fillRect(x, y, size, size);

  const slabW = size / slabGrid;
  const slabH = size / slabGrid;

  // Stone underneath water
  for (let r = 0; r < slabGrid; r++) {
    for (let c = 0; c < slabGrid; c++) {
      const sx = x + c * slabW + groutWidth;
      const sy = y + r * slabH + groutWidth;
      const sw = slabW - groutWidth * 2;
      const sh = slabH - groutWidth * 2;

      const v = h(r * 3 + c, seed, 100);
      ctx.fillStyle = varyColor(palette.floor, 3, v);
      ctx.fillRect(sx, sy, sw, sh);
    }
  }

  // Water overlay
  ctx.fillStyle = `rgba(10, 30, 50, ${waterDepth})`;
  ctx.fillRect(x, y, size, size);

  // Ripple circles
  if (h(0, seed, 150) < rippleChance) {
    const rx = x + size * 0.3 + h(0, seed, 151) * size * 0.4;
    const ry = y + size * 0.3 + h(0, seed, 152) * size * 0.4;
    ctx.strokeStyle = hexAlpha(palette.accent, 0.10);
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.arc(rx, ry, 4 + h(0, seed, 153) * 5, 0, Math.PI * 2);
    ctx.stroke();
  }
}

/**
 * Hollowed Cathedral floor — cracked marble with root
 * intrusions and scattered stone debris.
 */
export function drawFloor_crackedMarble(ctx, x, y, size, seed, palette, params) {
  const { slabGrid = 3, groutWidth = 1, crackChance = 0.0, rootChance = 0.0, debrisChance = 0.0 } = params;
  const h = cellHash;

  // Base floor
  ctx.fillStyle = palette.floor;
  ctx.fillRect(x, y, size, size);

  const slabW = size / slabGrid;
  const slabH = size / slabGrid;

  // Marble slabs (lighter than other themes)
  for (let r = 0; r < slabGrid; r++) {
    for (let c = 0; c < slabGrid; c++) {
      const sx = x + c * slabW + groutWidth;
      const sy = y + r * slabH + groutWidth;
      const sw = slabW - groutWidth * 2;
      const sh = slabH - groutWidth * 2;

      const v = h(r * 3 + c, seed, 100);
      ctx.fillStyle = varyColor(palette.floor, 3, v);
      ctx.fillRect(sx, sy, sw, sh);

      // Marble veining — thin diagonal line (controlled by veinChance param)
      if (h(r * 3 + c, seed, 105) < (params.veinChance || 0.12)) {
        ctx.strokeStyle = shiftColor(palette.floor, 6);
        ctx.lineWidth = 0.5;
        ctx.beginPath();
        ctx.moveTo(sx + h(r + c, seed, 106) * sw, sy);
        ctx.lineTo(sx + sw - h(r + c, seed, 107) * sw * 0.5, sy + sh);
        ctx.stroke();
      }
    }
  }

  // Crack across marble
  if (h(0, seed, 170) < crackChance) {
    ctx.strokeStyle = shiftColor(palette.grout, 5);
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.moveTo(x + h(0, seed, 171) * size, y);
    ctx.lineTo(x + h(0, seed, 172) * size, y + size);
    ctx.stroke();
  }

  // Root intrusion
  if (h(0, seed, 180) < rootChance) {
    ctx.strokeStyle = 'rgba(40, 55, 30, 0.4)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    const rx = x + h(0, seed, 181) * size * 0.3;
    ctx.moveTo(rx, y + size);
    ctx.bezierCurveTo(rx + 5, y + size * 0.5, rx + 10, y + size * 0.3, rx + 8, y);
    ctx.stroke();
  }

  // Debris
  if (h(0, seed, 190) < debrisChance) {
    ctx.fillStyle = params.debrisColor || '#3a3045';
    const dx = x + h(0, seed, 191) * (size - 6) + 2;
    const dy = y + h(0, seed, 192) * (size - 6) + 2;
    ctx.fillRect(dx, dy, 3, 2);
    ctx.fillRect(dx + 2, dy + 2, 2, 1);
  }
}

/**
 * Iron Depths floor — metal grate with crosshatch pattern
 * and darkness visible below. Oil stains.
 */
export function drawFloor_metalGrate(ctx, x, y, size, seed, palette, params) {
  const { groutWidth = 2, grateLineSpacing = 10, oilChance = 0.0 } = params;
  const h = cellHash;

  // Void below (very dark)
  ctx.fillStyle = palette.grout;
  ctx.fillRect(x, y, size, size);

  // Metal grate surface
  ctx.fillStyle = palette.floor;
  ctx.fillRect(x + groutWidth, y + groutWidth, size - groutWidth * 2, size - groutWidth * 2);

  // Crosshatch grate lines
  ctx.strokeStyle = shiftColor(palette.floor, -10);
  ctx.lineWidth = 1;
  for (let i = grateLineSpacing; i < size; i += grateLineSpacing) {
    // Horizontal bars
    ctx.beginPath();
    ctx.moveTo(x + groutWidth, y + i);
    ctx.lineTo(x + size - groutWidth, y + i);
    ctx.stroke();
  }
  for (let i = grateLineSpacing; i < size; i += grateLineSpacing) {
    // Vertical bars
    ctx.beginPath();
    ctx.moveTo(x + i, y + groutWidth);
    ctx.lineTo(x + i, y + size - groutWidth);
    ctx.stroke();
  }

  // Bar highlight on top of crosshatch
  ctx.strokeStyle = shiftColor(palette.floor, 5);
  ctx.lineWidth = 0.5;
  for (let i = grateLineSpacing; i < size; i += grateLineSpacing) {
    ctx.beginPath();
    ctx.moveTo(x + groutWidth, y + i - 1);
    ctx.lineTo(x + size - groutWidth, y + i - 1);
    ctx.stroke();
  }

  // Outer frame
  ctx.strokeStyle = shiftColor(palette.secondary, 5);
  ctx.lineWidth = 1;
  ctx.strokeRect(x + groutWidth, y + groutWidth, size - groutWidth * 2, size - groutWidth * 2);

  // Oil stain
  if (h(0, seed, 200) < oilChance) {
    ctx.fillStyle = params.stainColor || 'rgba(90, 60, 30, 0.30)';
    const ox = x + h(0, seed, 201) * (size - 10) + 4;
    const oy = y + h(0, seed, 202) * (size - 10) + 4;
    ctx.beginPath();
    ctx.ellipse(ox + 4, oy + 3, 4 + h(0, seed, 203) * 3, 2 + h(0, seed, 204) * 2, 0, 0, Math.PI * 2);
    ctx.fill();
  }
}


// ═══════════════════════════════════════════════════════════
//  CORRIDOR STYLES
// ═══════════════════════════════════════════════════════════

/**
 * Draw a themed corridor tile. Corridors are narrower/more worn
 * versions of the floor with style-specific enhancements.
 */
export function drawCorridor(ctx, x, y, size, seed, palette, theme) {
  const corridorStyle = theme.corridor?.style || 'worn_stone';
  const h = cellHash;

  // Start with a floor base (slightly different shade)
  ctx.fillStyle = shiftColor(palette.floor, -3);
  ctx.fillRect(x, y, size, size);

  // Simple worn stone pattern (2x2 grid)
  const slabW = size / 2;
  for (let r = 0; r < 2; r++) {
    for (let c = 0; c < 2; c++) {
      const sx = x + c * slabW + 1;
      const sy = y + r * slabW + 1;
      const v = h(r * 3 + c, seed, 200);
      ctx.fillStyle = varyColor(palette.floor, 3, v);
      ctx.fillRect(sx, sy, slabW - 2, slabW - 2);
    }
  }

  // Style-specific corridor effects
  switch (corridorStyle) {
    case 'worn_stone': {
      // Blood trail streaks
      if (h(0, seed, 210) < (theme.corridor.streakChance || 0.15)) {
        ctx.fillStyle = hexAlpha(palette.accent, 0.2);
        const sx2 = x + size * 0.3 + h(0, seed, 211) * size * 0.3;
        ctx.fillRect(sx2, y, 2, size);
      }
      break;
    }
    case 'ash_trail': {
      // Heavy ash
      const ashCount = Math.floor((theme.corridor.ashDensity || 0.5) * 25);
      for (let i = 0; i < ashCount; i++) {
        const ax = x + h(i, seed, 220) * size;
        const ay = y + h(i, seed, 221) * size;
        ctx.fillStyle = `rgba(60, 55, 50, ${0.15 + h(i, seed, 222) * 0.25})`;
        ctx.fillRect(ax, ay, 1 + h(i, seed, 223), 1);
      }
      break;
    }
    case 'shallow_water': {
      // Water overlay
      ctx.fillStyle = `rgba(10, 30, 50, ${theme.corridor.waterDepth || 0.3})`;
      ctx.fillRect(x, y, size, size);
      break;
    }
    case 'worn_carpet': {
      // Faded carpet strip down the center
      const carpetW = size * 0.4;
      ctx.fillStyle = theme.corridor.carpetColor || 'rgba(80, 40, 50, 0.20)';
      ctx.fillRect(x + (size - carpetW) / 2, y, carpetW, size);
      // Frayed edge
      ctx.fillStyle = shiftColor(palette.floor, 3);
      ctx.fillRect(x + (size - carpetW) / 2 - 1, y, 1, size);
      ctx.fillRect(x + (size + carpetW) / 2, y, 1, size);
      break;
    }
    case 'walkway': {
      // Edge rail hints
      if (theme.corridor.railHint) {
        ctx.fillStyle = shiftColor(palette.secondary, 8);
        ctx.fillRect(x, y, 2, size);
        ctx.fillRect(x + size - 2, y, 2, size);
        ctx.fillStyle = shiftColor(palette.secondary, 3);
        ctx.fillRect(x + 2, y, 1, size);
        ctx.fillRect(x + size - 3, y, 1, size);
      }
      break;
    }
  }
}


// ═══════════════════════════════════════════════════════════
//  SPECIAL TILES (doors, chests, stairs, spawn)
//  These use the theme palette but share common structure.
// ═══════════════════════════════════════════════════════════

/**
 * Draw a door tile (open or closed) using theme palette.
 */
export function drawDoor(ctx, x, y, size, seed, palette, theme, isOpen) {
  // Floor underneath
  drawCorridor(ctx, x, y, size, seed, palette, theme);

  if (isOpen) {
    // Open door — brown/accent outline
    const doorColor = lerpColor(palette.accent, '#8B4513', 0.5);
    ctx.strokeStyle = doorColor;
    ctx.lineWidth = 2;
    ctx.strokeRect(x + 4, y + 4, size - 8, size - 8);
    ctx.fillStyle = doorColor;
    ctx.font = `${size * 0.22}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText('○', x + size / 2, y + size / 2 + size * 0.08);
  } else {
    // Closed door — solid with handle
    const woodDark = lerpColor(palette.secondary, '#5C3310', 0.6);
    const woodLight = lerpColor(palette.secondary, '#8B4513', 0.5);
    ctx.fillStyle = woodDark;
    ctx.fillRect(x + 4, y + 4, size - 8, size - 8);
    // Wood grain lines
    ctx.strokeStyle = woodLight;
    ctx.lineWidth = 0.5;
    for (let i = 0; i < 3; i++) {
      const ly = y + 8 + i * (size - 16) / 3;
      ctx.beginPath();
      ctx.moveTo(x + 6, ly);
      ctx.lineTo(x + size - 6, ly);
      ctx.stroke();
    }
    // Frame
    ctx.strokeStyle = shiftColor(woodDark, -10);
    ctx.lineWidth = 1;
    ctx.strokeRect(x + 4, y + 4, size - 8, size - 8);
    // Door handle
    ctx.fillStyle = palette.highlight || '#DAA520';
    ctx.beginPath();
    ctx.arc(x + size / 2 + 6, y + size / 2, 2, 0, Math.PI * 2);
    ctx.fill();
  }
}

/**
 * Draw a chest tile using theme palette.
 */
export function drawChest(ctx, x, y, size, seed, palette, theme, isOpened) {
  // Floor underneath
  const h = cellHash;
  // Use the floor style from the theme
  const floorFn = FLOOR_DRAW_MAP[theme.floor.style] || drawFloor_flagstone;
  floorFn(ctx, x, y, size, seed, palette, theme.floor);

  // Chest icon
  const chestColor = isOpened
    ? shiftColor(palette.accent, -20)
    : palette.highlight || '#DAA520';
  const cw = size * 0.5;
  const ch = size * 0.4;
  const cx = x + (size - cw) / 2;
  const cy = y + (size - ch) / 2;

  ctx.fillStyle = chestColor;
  ctx.fillRect(cx, cy, cw, ch);
  ctx.strokeStyle = shiftColor(palette.primary, 10);
  ctx.lineWidth = 1;
  ctx.strokeRect(cx, cy, cw, ch);

  if (!isOpened) {
    // Latch
    ctx.fillStyle = palette.highlight || '#FFD700';
    ctx.fillRect(cx + cw / 2 - 3, cy + ch / 2 - 2, 6, 4);
  } else {
    // Open lid line
    ctx.strokeStyle = shiftColor(chestColor, 10);
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + cw, cy);
    ctx.stroke();
  }
}

/**
 * Draw a stairs tile using theme palette.
 */
export function drawStairs(ctx, x, y, size, seed, palette, theme) {
  // Floor underneath
  drawCorridor(ctx, x, y, size, seed, palette, theme);

  // Stairs icon — descending steps
  const stairColor = lerpColor(palette.accent, '#88CC88', 0.3);
  const borderColor = shiftColor(stairColor, -15);
  const stepW = size * 0.55;
  const stepH = size * 0.12;
  const stairX = x + (size - stepW) / 2;

  for (let s = 0; s < 3; s++) {
    const sy = y + size * 0.22 + s * (stepH + 2);
    const sw = stepW - s * 4;
    const sx = stairX + s * 2;
    ctx.fillStyle = stairColor;
    ctx.fillRect(sx, sy, sw, stepH);
    ctx.strokeStyle = borderColor;
    ctx.lineWidth = 1;
    ctx.strokeRect(sx, sy, sw, stepH);
  }

  ctx.fillStyle = stairColor;
  ctx.font = `${size * 0.3}px sans-serif`;
  ctx.textAlign = 'center';
  ctx.fillText('▼', x + size / 2, y + size - 3);
}

/**
 * Draw a spawn point tile — floor with subtle spawn marker.
 */
export function drawSpawn(ctx, x, y, size, seed, palette, theme) {
  // Use corridor style (smooth floor)
  drawCorridor(ctx, x, y, size, seed, palette, theme);

  // Subtle spawn indicator (faint ring)
  ctx.strokeStyle = hexAlpha(palette.accent, 0.15);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(x + size / 2, y + size / 2, size * 0.3, 0, Math.PI * 2);
  ctx.stroke();
}


// ═══════════════════════════════════════════════════════════
//  DISPATCH MAPS
// ═══════════════════════════════════════════════════════════

/** Maps wall style string → drawing function */
export const WALL_DRAW_MAP = {
  cracked_stone:  drawWall_crackedStone,
  scorched_brick: drawWall_scorchedBrick,
  mossy_stone:    drawWall_mossyStone,
  carved_stone:   drawWall_carvedStone,
  iron_plate:     drawWall_ironPlate,
};

/** Maps floor style string → drawing function */
export const FLOOR_DRAW_MAP = {
  flagstone:      drawFloor_flagstone,
  ash_covered:    drawFloor_ashCovered,
  flooded:        drawFloor_flooded,
  cracked_marble: drawFloor_crackedMarble,
  metal_grate:    drawFloor_metalGrate,
};


// ═══════════════════════════════════════════════════════════
//  INTERNAL HELPERS
// ═══════════════════════════════════════════════════════════

/** Draw subtle edge vignette (darken tile edges). */
function _drawEdgeVignette(ctx, x, y, size, color) {
  ctx.fillStyle = color;
  ctx.fillRect(x, y, size, 2);           // top
  ctx.fillRect(x, y + size - 2, size, 2); // bottom
  ctx.fillRect(x, y, 2, size);           // left
  ctx.fillRect(x + size - 2, y, 2, size); // right
}

/** Draw a small rivet circle (Iron Depths). */
function _drawRivet(ctx, cx, cy, palette) {
  ctx.fillStyle = shiftColor(palette.secondary, 15);
  ctx.beginPath();
  ctx.arc(cx, cy, 1.5, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = shiftColor(palette.secondary, -5);
  ctx.beginPath();
  ctx.arc(cx + 0.5, cy + 0.5, 0.8, 0, Math.PI * 2);
  ctx.fill();
}
