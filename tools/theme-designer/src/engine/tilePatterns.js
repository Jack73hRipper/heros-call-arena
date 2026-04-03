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

/**
 * Forgotten Cellar wall — rough-hewn quarry stone with chisel
 * marks and irregular block sizes. Plain, utilitarian.
 */
export function drawWall_roughHewn(ctx, x, y, size, seed, palette, params) {
  const { brickRows = 3, mortarWidth = 2 } = params;
  const h = cellHash;

  // Base fill
  ctx.fillStyle = palette.primary;
  ctx.fillRect(x, y, size, size);

  const brickH = size / brickRows;

  // Irregular rough-cut blocks — 2-4 per row with varied widths
  for (let r = 0; r < brickRows; r++) {
    const numBlocks = 2 + Math.floor(h(r, seed, 1) * 3); // 2-4 blocks
    let cx = x;
    for (let c = 0; c < numBlocks; c++) {
      // Distribute width unevenly
      const fraction = (1 / numBlocks) + (h(r * 10 + c, seed, 2) - 0.5) * 0.3;
      const brickW = Math.max(8, size * fraction);
      const drawX = cx + mortarWidth;
      const drawY = y + r * brickH + mortarWidth;
      const drawW = Math.min(brickW - mortarWidth * 2, x + size - mortarWidth - drawX);
      const drawH = brickH - mortarWidth * 2;

      if (drawW <= 2 || drawH <= 2 || drawX >= x + size - mortarWidth) break;

      // Stone face with color variation
      const v = h(r * 10 + c, seed, 3);
      ctx.fillStyle = varyColor(palette.secondary, 10, v);
      ctx.fillRect(drawX, drawY, drawW, drawH);

      // Top-edge highlight
      ctx.fillStyle = shiftColor(palette.secondary, 8);
      ctx.fillRect(drawX, drawY, drawW, 1);

      // Bottom-edge shadow
      ctx.fillStyle = shiftColor(palette.primary, -5);
      ctx.fillRect(drawX, drawY + drawH - 1, drawW, 1);

      // Chisel marks: 2-3 short angled lines per block
      const chiselCount = 2 + Math.floor(h(r * 10 + c, seed, 4) * 2);
      ctx.strokeStyle = shiftColor(palette.secondary, -8);
      ctx.lineWidth = 0.8;
      for (let m = 0; m < chiselCount; m++) {
        const mx = drawX + h(r * 10 + c + m, seed, 5) * (drawW - 4) + 2;
        const my = drawY + h(r * 10 + c + m, seed, 6) * (drawH - 4) + 2;
        ctx.beginPath();
        ctx.moveTo(mx, my);
        ctx.lineTo(mx + 2 + h(m, seed, 7) * 2, my + 1 + h(m, seed, 8));
        ctx.stroke();
      }

      cx += brickW;
    }
  }

  // Horizontal mortar lines
  ctx.fillStyle = palette.mortar;
  for (let r = 1; r < brickRows; r++) {
    ctx.fillRect(x, y + r * brickH - 1, size, mortarWidth);
  }
}

/**
 * Pale Ossuary wall — horizontal rows of bone-like rounded
 * segments, densely packed, with thin dark seams.
 */
export function drawWall_boneStack(ctx, x, y, size, seed, palette, params) {
  const { boneRows = 4, seamWidth = 1 } = params;
  const h = cellHash;

  // Base fill
  ctx.fillStyle = palette.primary;
  ctx.fillRect(x, y, size, size);

  const rowH = size / boneRows;

  // Rows of bone segments
  for (let r = 0; r < boneRows; r++) {
    const numBones = 3 + Math.floor(h(r, seed, 1) * 3); // 3-5 bones per row
    let cx = x;

    for (let b = 0; b < numBones; b++) {
      const boneW = (size / numBones) + (h(r * 10 + b, seed, 2) - 0.5) * 6;
      const drawX = cx + 1;
      const drawY = y + r * rowH + seamWidth;
      const drawW = Math.min(boneW - 2, x + size - 1 - drawX);
      const drawH = rowH - seamWidth * 2;

      if (drawW <= 4 || drawH <= 2 || drawX >= x + size - 1) break;

      // Bone color with slight variation
      const v = h(r * 10 + b, seed, 3);
      ctx.fillStyle = varyColor(palette.secondary, 4, v);

      // Rounded rectangle bone segment
      const radius = Math.min(2, drawW / 4, drawH / 4);
      ctx.beginPath();
      ctx.moveTo(drawX + radius, drawY);
      ctx.lineTo(drawX + drawW - radius, drawY);
      ctx.arcTo(drawX + drawW, drawY, drawX + drawW, drawY + radius, radius);
      ctx.lineTo(drawX + drawW, drawY + drawH - radius);
      ctx.arcTo(drawX + drawW, drawY + drawH, drawX + drawW - radius, drawY + drawH, radius);
      ctx.lineTo(drawX + radius, drawY + drawH);
      ctx.arcTo(drawX, drawY + drawH, drawX, drawY + drawH - radius, radius);
      ctx.lineTo(drawX, drawY + radius);
      ctx.arcTo(drawX, drawY, drawX + radius, drawY, radius);
      ctx.closePath();
      ctx.fill();

      // Top highlight on bone
      ctx.fillStyle = shiftColor(palette.secondary, 6);
      ctx.fillRect(drawX + radius, drawY + 1, drawW - radius * 2, 1);

      cx += boneW;
    }

    // Dark seam line between rows
    if (r < boneRows - 1) {
      ctx.fillStyle = palette.mortar;
      ctx.fillRect(x, y + (r + 1) * rowH - 1, size, seamWidth);
    }
  }
}

/**
 * Silent Vault wall — tight-fit ashlar masonry with perfectly
 * uniform blocks, hair-thin mortar, and geometric precision.
 */
export function drawWall_ashlarBlock(ctx, x, y, size, seed, palette, params) {
  const { blockRows = 3, blockCols = 2, mortarWidth = 1 } = params;
  const h = cellHash;

  // Base fill
  ctx.fillStyle = palette.primary;
  ctx.fillRect(x, y, size, size);

  const blockH = size / blockRows;
  const blockW = size / blockCols;

  // Perfectly aligned ashlar blocks — no row offset
  for (let r = 0; r < blockRows; r++) {
    for (let c = 0; c < blockCols; c++) {
      const bx = x + c * blockW + mortarWidth;
      const by = y + r * blockH + mortarWidth;
      const bw = blockW - mortarWidth * 2;
      const bh = blockH - mortarWidth * 2;

      if (bw <= 2 || bh <= 2) continue;

      // Block face
      const v = h(r * 10 + c, seed, 1);
      ctx.fillStyle = varyColor(palette.secondary, 5, v);
      ctx.fillRect(bx, by, bw, bh);

      // Gradient simulation: 1px lighter stripe at top
      ctx.fillStyle = shiftColor(palette.secondary, 6);
      ctx.fillRect(bx, by, bw, 1);

      // 1px darker at bottom
      ctx.fillStyle = shiftColor(palette.primary, -3);
      ctx.fillRect(bx, by + bh - 1, bw, 1);

      // Faint incised line border 2px inside each block
      ctx.strokeStyle = shiftColor(palette.secondary, -4);
      ctx.lineWidth = 0.5;
      ctx.strokeRect(bx + 2, by + 2, bw - 4, bh - 4);
    }
  }

  // Hair-thin mortar lines
  ctx.fillStyle = palette.mortar;
  for (let r = 1; r < blockRows; r++) {
    ctx.fillRect(x, y + r * blockH - 1, size, mortarWidth);
  }
  for (let c = 1; c < blockCols; c++) {
    ctx.fillRect(x + c * blockW - 1, y, mortarWidth, size);
  }
}

/**
 * Fungal Grotto wall — organic bulging masses with bioluminescent dots.
 * Irregular overlapping ellipses, no mortar lines, thin tendrils.
 */
export function drawWall_fungalGrowth(ctx, x, y, size, seed, palette, params) {
  const h = cellHash;

  // Base fill — deep forest black-green
  ctx.fillStyle = palette.primary;
  ctx.fillRect(x, y, size, size);

  // 4-6 irregular organic masses (overlapping ellipses)
  const massCount = 4 + Math.floor(h(0, seed, 1) * 3);
  for (let i = 0; i < massCount; i++) {
    const cx = x + h(i, seed, 2) * size;
    const cy = y + h(i, seed, 3) * size;
    const rx = size * 0.15 + h(i, seed, 4) * size * 0.2;
    const ry = size * 0.12 + h(i, seed, 5) * size * 0.18;
    ctx.fillStyle = varyColor(palette.secondary, 6, h(i, seed, 6));
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx, ry, h(i, seed, 7) * Math.PI, 0, Math.PI * 2);
    ctx.fill();
  }

  // 2-3 bioluminescent dots (accent color, small glow)
  const dotCount = 2 + Math.floor(h(0, seed, 10) * 2);
  for (let i = 0; i < dotCount; i++) {
    const dx = x + h(i, seed, 11) * (size - 6) + 3;
    const dy = y + h(i, seed, 12) * (size - 6) + 3;
    const grad = ctx.createRadialGradient(dx, dy, 0, dx, dy, 4);
    grad.addColorStop(0, hexAlpha(palette.highlight, 0.6));
    grad.addColorStop(1, hexAlpha(palette.highlight, 0));
    ctx.fillStyle = grad;
    ctx.fillRect(dx - 4, dy - 4, 8, 8);
    ctx.fillStyle = palette.accent;
    ctx.fillRect(dx, dy, 1, 1);
  }

  // Thin tendril lines from top and bottom
  ctx.strokeStyle = hexAlpha(palette.accent, 0.25);
  ctx.lineWidth = 0.8;
  for (let i = 0; i < 2; i++) {
    const tx = x + h(i, seed, 20) * (size - 4) + 2;
    ctx.beginPath();
    ctx.moveTo(tx, y);
    ctx.quadraticCurveTo(tx + (h(i, seed, 21) - 0.5) * 8, y + size * 0.3, tx + (h(i, seed, 22) - 0.5) * 6, y + size * 0.5);
    ctx.stroke();
    const bx = x + h(i + 2, seed, 20) * (size - 4) + 2;
    ctx.beginPath();
    ctx.moveTo(bx, y + size);
    ctx.quadraticCurveTo(bx + (h(i + 2, seed, 21) - 0.5) * 8, y + size * 0.7, bx + (h(i + 2, seed, 22) - 0.5) * 6, y + size * 0.5);
    ctx.stroke();
  }
}

/**
 * Frozen Crypt wall — angular crystal facets with frost lines.
 * 3-4 irregular polygons simulating crystal faces, highlight edge, white frost seams.
 */
export function drawWall_iceCrystal(ctx, x, y, size, seed, palette, params) {
  const h = cellHash;

  // Base fill — deep ice-blue black
  ctx.fillStyle = palette.primary;
  ctx.fillRect(x, y, size, size);

  // 3-4 crystal facets as irregular polygons
  const facetCount = 3 + Math.floor(h(0, seed, 1) * 2);
  const cx = x + size / 2, cy = y + size / 2;

  for (let i = 0; i < facetCount; i++) {
    const angle = (i / facetCount) * Math.PI * 2 + h(i, seed, 2) * 0.5;
    const nextAngle = ((i + 1) / facetCount) * Math.PI * 2 + h(i + 1, seed, 2) * 0.5;
    const r1 = size * 0.3 + h(i, seed, 3) * size * 0.2;
    const r2 = size * 0.3 + h(i + 1, seed, 3) * size * 0.2;

    // Each facet: slightly different shade of blue-grey
    ctx.fillStyle = varyColor(palette.secondary, 8, h(i, seed, 4));
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(angle) * r1, cy + Math.sin(angle) * r1);
    ctx.lineTo(cx + Math.cos(nextAngle) * r2, cy + Math.sin(nextAngle) * r2);
    ctx.closePath();
    ctx.fill();

    // Frost seam line at polygon edge
    ctx.strokeStyle = hexAlpha('#ffffff', 0.15);
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(angle) * r1, cy + Math.sin(angle) * r1);
    ctx.lineTo(cx + Math.cos(nextAngle) * r2, cy + Math.sin(nextAngle) * r2);
    ctx.stroke();
  }

  // Bright highlight on 1 facet face (light refraction)
  const hlFacet = Math.floor(h(0, seed, 10) * facetCount);
  const hlAngle = (hlFacet / facetCount) * Math.PI * 2 + h(hlFacet, seed, 2) * 0.5;
  const hlR = size * 0.15 + h(hlFacet, seed, 11) * size * 0.1;
  ctx.fillStyle = hexAlpha(palette.highlight, 0.2);
  ctx.beginPath();
  ctx.arc(cx + Math.cos(hlAngle) * hlR, cy + Math.sin(hlAngle) * hlR, size * 0.08, 0, Math.PI * 2);
  ctx.fill();

  // Outer edge darkening
  ctx.fillStyle = hexAlpha(palette.primary, 0.3);
  ctx.fillRect(x, y, size, 2);
  ctx.fillRect(x, y + size - 2, size, 2);
  ctx.fillRect(x, y, 2, size);
  ctx.fillRect(x + size - 2, y, 2, size);
}

/**
 * Cursed Shrine wall — dark marble blocks with red vein lines and gold symbols.
 * 2x2 grid, bezier curve veins, occasional geometric gold mark.
 */
export function drawWall_bloodStone(ctx, x, y, size, seed, palette, params) {
  const { blockRows = 2, blockCols = 2, mortarWidth = 2 } = params;
  const h = cellHash;

  // Base fill
  ctx.fillStyle = palette.primary;
  ctx.fillRect(x, y, size, size);

  const blockH = size / blockRows;
  const blockW = size / blockCols;

  // Dark marble blocks
  for (let r = 0; r < blockRows; r++) {
    for (let c = 0; c < blockCols; c++) {
      const bx = x + c * blockW + mortarWidth;
      const by = y + r * blockH + mortarWidth;
      const bw = blockW - mortarWidth * 2;
      const bh = blockH - mortarWidth * 2;
      if (bw <= 2 || bh <= 2) continue;

      ctx.fillStyle = varyColor(palette.secondary, 5, h(r * 10 + c, seed, 1));
      ctx.fillRect(bx, by, bw, bh);

      // Top highlight, bottom shadow
      ctx.fillStyle = shiftColor(palette.secondary, 5);
      ctx.fillRect(bx, by, bw, 1);
      ctx.fillStyle = shiftColor(palette.primary, -3);
      ctx.fillRect(bx, by + bh - 1, bw, 1);

      // Red vein lines (1-2 per block, bezier curves)
      const veinCount = 1 + Math.floor(h(r * 10 + c, seed, 5) * 2);
      ctx.strokeStyle = hexAlpha(palette.accent, 0.35);
      ctx.lineWidth = 0.8;
      for (let v = 0; v < veinCount; v++) {
        const vx1 = bx + h(r * 10 + c + v, seed, 6) * bw;
        const vy1 = by + h(r * 10 + c + v, seed, 7) * bh;
        const vx2 = bx + h(r * 10 + c + v, seed, 8) * bw;
        const vy2 = by + h(r * 10 + c + v, seed, 9) * bh;
        const cpx = bx + h(r * 10 + c + v, seed, 10) * bw;
        const cpy = by + h(r * 10 + c + v, seed, 11) * bh;
        ctx.beginPath();
        ctx.moveTo(vx1, vy1);
        ctx.quadraticCurveTo(cpx, cpy, vx2, vy2);
        ctx.stroke();
      }
    }
  }

  // Occasional gold symbol remnant (1 per tile, seeded)
  if (h(0, seed, 20) < 0.35) {
    const sx = x + size * 0.3 + h(0, seed, 21) * size * 0.4;
    const sy = y + size * 0.3 + h(0, seed, 22) * size * 0.4;
    ctx.strokeStyle = hexAlpha(palette.highlight, 0.25);
    ctx.lineWidth = 1;
    // Simple geometric mark — small diamond
    ctx.beginPath();
    ctx.moveTo(sx, sy - 3);
    ctx.lineTo(sx + 3, sy);
    ctx.lineTo(sx, sy + 3);
    ctx.lineTo(sx - 3, sy);
    ctx.closePath();
    ctx.stroke();
  }

  // Deep mortar with faint red glow
  ctx.fillStyle = palette.mortar;
  for (let r = 1; r < blockRows; r++) {
    ctx.fillRect(x, y + r * blockH - 1, size, mortarWidth);
  }
  for (let c = 1; c < blockCols; c++) {
    ctx.fillRect(x + c * blockW - 1, y, mortarWidth, size);
  }
  // Faint red glow over mortar
  ctx.fillStyle = hexAlpha(palette.accent, 0.08);
  for (let r = 1; r < blockRows; r++) {
    ctx.fillRect(x, y + r * blockH - 2, size, mortarWidth + 2);
  }
  for (let c = 1; c < blockCols; c++) {
    ctx.fillRect(x + c * blockW - 2, y, mortarWidth + 2, size);
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
  const { grateLineSpacing = 10, oilChance = 0.0 } = params;
  const h = cellHash;

  // Solid metal grate surface — no visible border gap between tiles
  ctx.fillStyle = palette.floor;
  ctx.fillRect(x, y, size, size);

  // Crosshatch grate lines
  ctx.strokeStyle = shiftColor(palette.floor, -10);
  ctx.lineWidth = 1;
  for (let i = grateLineSpacing; i < size; i += grateLineSpacing) {
    // Horizontal bars
    ctx.beginPath();
    ctx.moveTo(x, y + i);
    ctx.lineTo(x + size, y + i);
    ctx.stroke();
  }
  for (let i = grateLineSpacing; i < size; i += grateLineSpacing) {
    // Vertical bars
    ctx.beginPath();
    ctx.moveTo(x + i, y);
    ctx.lineTo(x + i, y + size);
    ctx.stroke();
  }

  // Bar highlight on top of crosshatch
  ctx.strokeStyle = shiftColor(palette.floor, 5);
  ctx.lineWidth = 0.5;
  for (let i = grateLineSpacing; i < size; i += grateLineSpacing) {
    ctx.beginPath();
    ctx.moveTo(x, y + i - 1);
    ctx.lineTo(x + size, y + i - 1);
    ctx.stroke();
  }

  // Subtle outer frame
  ctx.strokeStyle = hexAlpha(palette.secondary, 0.15);
  ctx.lineWidth = 0.5;
  ctx.strokeRect(x + 0.5, y + 0.5, size - 1, size - 1);

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

/**
 * Forgotten Cellar floor — compacted dirt with tiny pebble
 * dots. No grid pattern — organic texture.
 */
export function drawFloor_packedEarth(ctx, x, y, size, seed, palette, params) {
  const h = cellHash;

  // Base fill — single solid fill, no slab grid
  ctx.fillStyle = palette.floor;
  ctx.fillRect(x, y, size, size);

  // 4-8 tiny pebble dots scattered deterministically
  const pebbleCount = 4 + Math.floor(h(0, seed, 100) * 5);
  for (let i = 0; i < pebbleCount; i++) {
    const px = x + h(i, seed, 101) * (size - 4) + 2;
    const py = y + h(i, seed, 102) * (size - 4) + 2;
    const pSize = 1 + Math.floor(h(i, seed, 103) * 2);
    ctx.fillStyle = shiftColor(palette.floor, h(i, seed, 104) < 0.5 ? 5 : -5);
    ctx.beginPath();
    ctx.arc(px, py, pSize * 0.5, 0, Math.PI * 2);
    ctx.fill();
  }

  // 1-2 faint scratch lines (directional grain)
  const scratchCount = 1 + Math.floor(h(0, seed, 110) * 2);
  ctx.strokeStyle = shiftColor(palette.floor, -3);
  ctx.lineWidth = 0.5;
  for (let i = 0; i < scratchCount; i++) {
    const sx = x + h(i, seed, 111) * size;
    const sy = y + h(i, seed, 112) * size * 0.3;
    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.lineTo(sx + h(i, seed, 113) * size * 0.4, sy + size * 0.6 + h(i, seed, 114) * size * 0.3);
    ctx.stroke();
  }
}

/**
 * Pale Ossuary floor — smooth large tiles with barely visible
 * seam lines. Austere, clean. The emptiness is the horror.
 */
export function drawFloor_polishedSlab(ctx, x, y, size, seed, palette, params) {
  const { slabGrid = 2, groutWidth = 1 } = params;
  const h = cellHash;

  // Base floor fill
  ctx.fillStyle = palette.floor;
  ctx.fillRect(x, y, size, size);

  const slabW = size / slabGrid;

  // 2×2 large slabs with very faint seam
  for (let r = 0; r < slabGrid; r++) {
    for (let c = 0; c < slabGrid; c++) {
      const sx = x + c * slabW + groutWidth;
      const sy = y + r * slabW + groutWidth;
      const sw = slabW - groutWidth * 2;
      const sh = slabW - groutWidth * 2;

      // Nearly identical color — only ±1 RGB variation
      const v = h(r * 3 + c, seed, 100);
      ctx.fillStyle = varyColor(palette.floor, 1, v);
      ctx.fillRect(sx, sy, sw, sh);

      // Optional faint reflection highlight (1px lighter bar at 30% height)
      if (h(r * 3 + c, seed, 105) < 0.4) {
        ctx.fillStyle = shiftColor(palette.floor, 3);
        ctx.fillRect(sx + 2, sy + sh * 0.3, sw - 4, 1);
      }
    }
  }

  // Very faint grout lines — barely perceptible seams
  ctx.fillStyle = hexAlpha(palette.grout, 0.08);
  for (let r = 1; r < slabGrid; r++) {
    ctx.fillRect(x, y + r * slabW, size, 1);
  }
  for (let c = 1; c < slabGrid; c++) {
    ctx.fillRect(x + c * slabW, y, 1, size);
  }
}

/**
 * Silent Vault floor — geometric tile pattern with a faint
 * dust film overlay. Archival/library feel.
 */
export function drawFloor_dustyTile(ctx, x, y, size, seed, palette, params) {
  const { slabGrid = 3, groutWidth = 1 } = params;
  const h = cellHash;

  // Base floor fill
  ctx.fillStyle = palette.floor;
  ctx.fillRect(x, y, size, size);

  const slabW = size / slabGrid;

  // 3×3 smaller tile grid
  for (let r = 0; r < slabGrid; r++) {
    for (let c = 0; c < slabGrid; c++) {
      const sx = x + c * slabW + groutWidth;
      const sy = y + r * slabW + groutWidth;
      const sw = slabW - groutWidth * 2;
      const sh = slabW - groutWidth * 2;

      const v = h(r * 3 + c, seed, 100);
      ctx.fillStyle = varyColor(palette.floor, 3, v);
      ctx.fillRect(sx, sy, sw, sh);

      // 1 seeded "dust mote" per tile (1px, slightly lighter)
      const dx = sx + h(r * 3 + c, seed, 105) * (sw - 2) + 1;
      const dy = sy + h(r * 3 + c, seed, 106) * (sh - 2) + 1;
      ctx.fillStyle = shiftColor(palette.floor, 4);
      ctx.fillRect(dx, dy, 1, 1);
    }
  }

  // Thin dust film: semi-transparent grey overlay
  ctx.fillStyle = 'rgba(40, 40, 50, 0.04)';
  ctx.fillRect(x, y, size, size);
}

/**
 * Fungal Grotto floor — dark green-brown base with mycelium network lines.
 * Thin branching lines + faint spore dots.
 */
export function drawFloor_myceliumMat(ctx, x, y, size, seed, palette, params) {
  const h = cellHash;

  // Dark green-brown base fill
  ctx.fillStyle = palette.floor;
  ctx.fillRect(x, y, size, size);

  // Subtle floor variation
  ctx.fillStyle = varyColor(palette.floor, 3, h(0, seed, 100));
  ctx.fillRect(x + 2, y + 2, size - 4, size - 4);

  // Thin branching mycelium lines (2-3 per tile, seeded)
  const lineCount = 2 + Math.floor(h(0, seed, 1) * 2);
  ctx.strokeStyle = hexAlpha(palette.accent, 0.2);
  ctx.lineWidth = 0.6;
  for (let i = 0; i < lineCount; i++) {
    const sx = x + h(i, seed, 2) * size;
    const sy = y + h(i, seed, 3) * size;
    const ex = x + h(i, seed, 4) * size;
    const ey = y + h(i, seed, 5) * size;
    const cpx = x + h(i, seed, 6) * size;
    const cpy = y + h(i, seed, 7) * size;
    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.quadraticCurveTo(cpx, cpy, ex, ey);
    ctx.stroke();

    // Branch fork
    if (h(i, seed, 8) > 0.4) {
      const fx = (ex + cpx) / 2 + (h(i, seed, 9) - 0.5) * size * 0.3;
      const fy = (ey + cpy) / 2 + (h(i, seed, 10) - 0.5) * size * 0.3;
      ctx.beginPath();
      ctx.moveTo((sx + cpx) / 2, (sy + cpy) / 2);
      ctx.lineTo(fx, fy);
      ctx.stroke();
    }
  }

  // Very faint spore dots (highlight, 0.2 alpha, 1px)
  const sporeCount = 3 + Math.floor(h(0, seed, 20) * 3);
  ctx.fillStyle = hexAlpha(palette.highlight, 0.2);
  for (let i = 0; i < sporeCount; i++) {
    const dx = x + h(i, seed, 21) * (size - 2) + 1;
    const dy = y + h(i, seed, 22) * (size - 2) + 1;
    ctx.fillRect(dx, dy, 1, 1);
  }
}

/**
 * Frozen Crypt floor — frost-covered 2x2 slab grid with crystal glints.
 * Barely visible slabs under frost film, thin ice crack.
 */
export function drawFloor_frozenStone(ctx, x, y, size, seed, palette, params) {
  const { slabGrid = 2, groutWidth = 1 } = params;
  const h = cellHash;

  // Base floor fill
  ctx.fillStyle = palette.floor;
  ctx.fillRect(x, y, size, size);

  // 2×2 slab grid barely visible under frost
  const slabW = size / slabGrid;
  for (let r = 0; r < slabGrid; r++) {
    for (let c = 0; c < slabGrid; c++) {
      const sx = x + c * slabW + groutWidth;
      const sy = y + r * slabW + groutWidth;
      const sw = slabW - groutWidth * 2;
      const sh = slabW - groutWidth * 2;
      ctx.fillStyle = varyColor(palette.floor, 3, h(r * 3 + c, seed, 100));
      ctx.fillRect(sx, sy, sw, sh);
    }
  }

  // Light frost film overlay (rgba white, 0.04)
  ctx.fillStyle = 'rgba(200, 220, 255, 0.04)';
  ctx.fillRect(x, y, size, size);

  // 1-2 tiny crystal glint dots (highlight color, 1px)
  const glintCount = 1 + Math.floor(h(0, seed, 1) * 2);
  for (let i = 0; i < glintCount; i++) {
    const gx = x + h(i, seed, 2) * (size - 4) + 2;
    const gy = y + h(i, seed, 3) * (size - 4) + 2;
    ctx.fillStyle = hexAlpha(palette.highlight, 0.4);
    ctx.fillRect(gx, gy, 1, 1);
  }

  // Optional thin crack line (ice crack, 0.8px, very faint)
  if (h(0, seed, 10) < 0.35) {
    ctx.strokeStyle = hexAlpha(palette.highlight, 0.15);
    ctx.lineWidth = 0.8;
    const cx1 = x + h(0, seed, 11) * size;
    const cy1 = y + h(0, seed, 12) * size;
    const cx2 = x + h(0, seed, 13) * size;
    const cy2 = y + h(0, seed, 14) * size;
    ctx.beginPath();
    ctx.moveTo(cx1, cy1);
    ctx.lineTo(cx2, cy2);
    ctx.stroke();
  }
}

/**
 * Cursed Shrine floor — geometric pentagonal/hexagonal tile pattern.
 * Accent-colored ritual geometry borders, occasional gold center dots.
 */
export function drawFloor_ritualTile(ctx, x, y, size, seed, palette, params) {
  const { slabGrid = 3, groutWidth = 1 } = params;
  const h = cellHash;

  // Base floor fill
  ctx.fillStyle = palette.floor;
  ctx.fillRect(x, y, size, size);

  // Faint overall dark red wash
  ctx.fillStyle = hexAlpha(palette.accent, 0.04);
  ctx.fillRect(x, y, size, size);

  // Geometric tile pattern — pentagonal approximation via 3x3 grid with diagonal lines
  const slabW = size / slabGrid;
  for (let r = 0; r < slabGrid; r++) {
    for (let c = 0; c < slabGrid; c++) {
      const sx = x + c * slabW;
      const sy = y + r * slabW;
      const sw = slabW;
      const sh = slabW;

      ctx.fillStyle = varyColor(palette.floor, 3, h(r * slabGrid + c, seed, 100));
      ctx.fillRect(sx + groutWidth, sy + groutWidth, sw - groutWidth * 2, sh - groutWidth * 2);

      // Diagonal line across each sub-tile for pentagonal feel
      ctx.strokeStyle = hexAlpha(palette.accent, 0.12);
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      if ((r + c) % 2 === 0) {
        ctx.moveTo(sx, sy + sh);
        ctx.lineTo(sx + sw, sy);
      } else {
        ctx.moveTo(sx, sy);
        ctx.lineTo(sx + sw, sy + sh);
      }
      ctx.stroke();

      // Tiny gold dot in center of some tiles (seeded)
      if (h(r * slabGrid + c, seed, 1) < 0.3) {
        ctx.fillStyle = hexAlpha(palette.highlight, 0.35);
        ctx.fillRect(sx + sw / 2, sy + sh / 2, 1, 1);
      }
    }
  }

  // Thin accent-colored border lines at tile borders
  ctx.strokeStyle = hexAlpha(palette.accent, 0.15);
  ctx.lineWidth = 0.5;
  for (let r = 1; r < slabGrid; r++) {
    ctx.beginPath();
    ctx.moveTo(x, y + r * slabW);
    ctx.lineTo(x + size, y + r * slabW);
    ctx.stroke();
  }
  for (let c = 1; c < slabGrid; c++) {
    ctx.beginPath();
    ctx.moveTo(x + c * slabW, y);
    ctx.lineTo(x + c * slabW, y + size);
    ctx.stroke();
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
 * Legacy non-oriented version — used when neighbor context is unavailable.
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
 * Draw a door tile with faux 3/4 perspective, oriented by neighboring walls.
 *
 * @param {boolean} wallNorth - true if tile to the north is a wall
 * @param {boolean} wallSouth - true if tile to the south is a wall
 * @param {boolean} wallEast  - true if tile to the east is a wall
 * @param {boolean} wallWest  - true if tile to the west is a wall
 */
export function drawDoorPerspective(ctx, x, y, size, seed, palette, theme, isOpen, wallNorth, wallSouth, wallEast, wallWest) {
  // Floor underneath
  drawCorridor(ctx, x, y, size, seed, palette, theme);

  const woodDark  = lerpColor(palette.secondary, '#5C3310', 0.6);
  const woodMid   = lerpColor(palette.secondary, '#8B4513', 0.5);
  const woodLight = lerpColor(palette.secondary, '#A0764B', 0.4);
  const metalCol  = palette.metal || palette.secondary;
  const metalDark = shiftColor(metalCol, -8);
  const handleCol = palette.highlight || '#DAA520';
  const frameSt   = shiftColor(palette.primary, 10);

  if (wallNorth && wallSouth && !wallEast && !wallWest) {
    // ── EW passage door ──
    if (isOpen) {
      _drawDoorEW_open(ctx, x, y, size, woodMid, woodLight, metalCol, frameSt);
    } else {
      _drawDoorEW_closed(ctx, x, y, size, seed, woodDark, woodMid, woodLight, metalCol, metalDark, handleCol, frameSt);
    }
  } else {
    // ── NS passage door (default) ──
    if (isOpen) {
      _drawDoorNS_open(ctx, x, y, size, woodMid, woodLight, metalCol, frameSt);
    } else {
      _drawDoorNS_closed(ctx, x, y, size, seed, woodDark, woodMid, woodLight, metalCol, metalDark, handleCol, frameSt);
    }
  }
}

// ── NS door helpers (front-facing, top edge + face visible) ──

function _drawDoorNS_closed(ctx, px, py, s, seed, woodDark, woodMid, woodLight, metalCol, metalDark, handleCol, frameSt) {
  const inset = Math.round(s * 0.08);
  const topH = Math.round(s * 0.14);
  const faceY = py + topH;
  const faceH = s - topH - inset;
  const dw = s - inset * 2;

  // Stone door frame
  ctx.fillStyle = frameSt;
  ctx.fillRect(px + inset - 2, py + topH, 3, faceH + inset);
  ctx.fillRect(px + s - inset - 1, py + topH, 3, faceH + inset);
  ctx.fillRect(px + inset - 2, py + topH - 2, dw + 4, 3);

  // Top edge of door (looking down)
  ctx.fillStyle = woodLight;
  ctx.fillRect(px + inset, py, dw, topH);
  ctx.fillStyle = shiftColor(woodLight, 12);
  ctx.fillRect(px + inset, py, dw, 1);
  ctx.fillStyle = 'rgba(0,0,0,0.15)';
  ctx.fillRect(px + inset, py + topH - 1, dw, 1);

  // Door face
  ctx.fillStyle = woodDark;
  ctx.fillRect(px + inset, faceY, dw, faceH);

  // Vertical planks
  const plankCount = 3;
  const plankW = dw / plankCount;
  for (let i = 0; i < plankCount; i++) {
    const plX = px + inset + i * plankW;
    const colorVar = cellHash(seed, i, 55) * 6 - 3;
    ctx.fillStyle = shiftColor(woodDark, colorVar);
    ctx.fillRect(plX + 0.5, faceY + 1, plankW - 1, faceH - 2);
    ctx.fillStyle = 'rgba(0,0,0,0.12)';
    ctx.fillRect(plX, faceY + 1, 1, faceH - 2);
  }

  // Iron bands
  ctx.fillStyle = metalCol;
  const bandH = Math.max(2, Math.round(s * 0.05));
  const band1Y = faceY + Math.round(faceH * 0.28);
  const band2Y = faceY + Math.round(faceH * 0.68);
  ctx.fillRect(px + inset, band1Y, dw, bandH);
  ctx.fillRect(px + inset, band2Y, dw, bandH);
  ctx.fillStyle = shiftColor(metalCol, 10);
  ctx.fillRect(px + inset, band1Y, dw, 1);
  ctx.fillRect(px + inset, band2Y, dw, 1);
  ctx.fillStyle = metalDark;
  ctx.fillRect(px + inset, band1Y + bandH - 1, dw, 1);
  ctx.fillRect(px + inset, band2Y + bandH - 1, dw, 1);

  // Iron rivets
  ctx.fillStyle = shiftColor(metalCol, 15);
  for (let i = 0; i <= plankCount; i++) {
    const rx = px + inset + i * plankW;
    for (const ry of [band1Y + bandH / 2, band2Y + bandH / 2]) {
      ctx.beginPath();
      ctx.arc(rx, ry, 1.2, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Ring pull handle
  const ringCX = px + s / 2;
  const ringCY = faceY + faceH * 0.50;
  ctx.fillStyle = metalDark;
  ctx.fillRect(ringCX - 2, ringCY - 5, 4, 4);
  ctx.strokeStyle = handleCol;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(ringCX, ringCY + 1, 3.5, 0, Math.PI * 2);
  ctx.stroke();

  // Bottom threshold
  ctx.fillStyle = 'rgba(0,0,0,0.18)';
  ctx.fillRect(px + inset, py + s - inset - 2, dw, 2);
  ctx.fillStyle = 'rgba(0,0,0,0.08)';
  ctx.fillRect(px + inset, py + s - inset - 4, dw, 2);
}

function _drawDoorNS_open(ctx, px, py, s, woodMid, woodLight, metalCol, frameSt) {
  const inset = Math.round(s * 0.08);
  const topH = Math.round(s * 0.14);
  const faceH = s - topH - inset;
  const dw = s - inset * 2;
  const panelDepth = Math.round(s * 0.22);

  // Stone frame
  ctx.fillStyle = frameSt;
  ctx.fillRect(px + inset - 2, py + topH, 3, faceH + inset);
  ctx.fillRect(px + s - inset - 1, py + topH, 3, faceH + inset);
  ctx.fillRect(px + inset - 2, py + topH - 2, dw + 4, 3);

  // Left panel swung inward
  ctx.fillStyle = woodMid;
  ctx.beginPath();
  ctx.moveTo(px + inset, py + topH);
  ctx.lineTo(px + inset + panelDepth, py + topH + 4);
  ctx.lineTo(px + inset + panelDepth, py + s - inset - 4);
  ctx.lineTo(px + inset, py + s - inset);
  ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = woodLight; ctx.lineWidth = 0.5; ctx.stroke();
  ctx.fillStyle = metalCol;
  ctx.fillRect(px + inset, py + topH + Math.round(faceH * 0.30), panelDepth, 2);

  // Right panel swung inward
  ctx.fillStyle = woodMid;
  ctx.beginPath();
  ctx.moveTo(px + s - inset, py + topH);
  ctx.lineTo(px + s - inset - panelDepth, py + topH + 4);
  ctx.lineTo(px + s - inset - panelDepth, py + s - inset - 4);
  ctx.lineTo(px + s - inset, py + s - inset);
  ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = woodLight; ctx.lineWidth = 0.5; ctx.stroke();
  ctx.fillStyle = metalCol;
  ctx.fillRect(px + s - inset - panelDepth, py + topH + Math.round(faceH * 0.30), panelDepth, 2);

  // Dark gap
  const gapL = px + inset + panelDepth + 1;
  const gapR = px + s - inset - panelDepth - 1;
  if (gapR > gapL) {
    ctx.fillStyle = 'rgba(0,0,0,0.10)';
    ctx.fillRect(gapL, py + topH, gapR - gapL, faceH);
  }

  // Frame top edge
  ctx.fillStyle = shiftColor(frameSt, 6);
  ctx.fillRect(px + inset - 2, py, dw + 4, topH);
  ctx.fillStyle = shiftColor(frameSt, 12);
  ctx.fillRect(px + inset - 2, py, dw + 4, 1);
}

// ── EW door helpers (side-on view, narrow edge visible) ──

function _drawDoorEW_closed(ctx, px, py, s, seed, woodDark, woodMid, woodLight, metalCol, metalDark, handleCol, frameSt) {
  const inset = Math.round(s * 0.08);
  const dh = s - inset * 2;
  const faceW = Math.round(s * 0.35);
  const edgeW = Math.round(s * 0.14);
  const panelX = px + Math.round((s - faceW - edgeW) / 2);

  // Stone frame
  ctx.fillStyle = frameSt;
  ctx.fillRect(px + inset, py + inset - 2, s - inset * 2, 3);
  ctx.fillRect(px + inset, py + s - inset - 1, s - inset * 2, 3);
  ctx.fillRect(panelX - 2, py + inset, 3, dh);
  ctx.fillRect(panelX + faceW + edgeW - 1, py + inset, 3, dh);

  // Door face (wider visible portion)
  ctx.fillStyle = woodDark;
  ctx.fillRect(panelX, py + inset, faceW, dh);

  // Horizontal planks on face
  const plankCount = 3;
  const plankH = dh / plankCount;
  for (let i = 0; i < plankCount; i++) {
    const plY = py + inset + i * plankH;
    const colorVar = cellHash(seed, i, 66) * 6 - 3;
    ctx.fillStyle = shiftColor(woodDark, colorVar);
    ctx.fillRect(panelX + 1, plY + 0.5, faceW - 2, plankH - 1);
    ctx.fillStyle = 'rgba(0,0,0,0.12)';
    ctx.fillRect(panelX + 1, plY, faceW - 2, 1);
  }

  // Iron bands (vertical)
  ctx.fillStyle = metalCol;
  const bandW = Math.max(2, Math.round(s * 0.05));
  const band1X = panelX + Math.round(faceW * 0.30);
  const band2X = panelX + Math.round(faceW * 0.70);
  ctx.fillRect(band1X, py + inset, bandW, dh);
  ctx.fillRect(band2X, py + inset, bandW, dh);
  ctx.fillStyle = shiftColor(metalCol, 10);
  ctx.fillRect(band1X, py + inset, 1, dh);
  ctx.fillRect(band2X, py + inset, 1, dh);
  ctx.fillStyle = metalDark;
  ctx.fillRect(band1X + bandW - 1, py + inset, 1, dh);
  ctx.fillRect(band2X + bandW - 1, py + inset, 1, dh);

  // Rivets
  ctx.fillStyle = shiftColor(metalCol, 15);
  for (let i = 0; i <= plankCount; i++) {
    const ry = py + inset + i * plankH;
    for (const rx of [band1X + bandW / 2, band2X + bandW / 2]) {
      ctx.beginPath();
      ctx.arc(rx, ry, 1.2, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Door edge/thickness
  ctx.fillStyle = woodMid;
  ctx.fillRect(panelX + faceW, py + inset, edgeW, dh);
  ctx.fillStyle = shiftColor(woodMid, 8);
  ctx.fillRect(panelX + faceW, py + inset, edgeW, 1);
  ctx.fillStyle = 'rgba(0,0,0,0.12)';
  ctx.fillRect(panelX + faceW, py + s - inset - 2, edgeW, 2);
  ctx.fillStyle = 'rgba(0,0,0,0.20)';
  ctx.fillRect(panelX + faceW, py + inset, 1, dh);

  // Ring pull handle
  const ringCX = panelX + Math.round(faceW * 0.55);
  const ringCY = py + s / 2;
  ctx.fillStyle = metalDark;
  ctx.fillRect(ringCX - 2, ringCY - 5, 4, 4);
  ctx.strokeStyle = handleCol;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(ringCX, ringCY + 1, 3.5, 0, Math.PI * 2);
  ctx.stroke();
}

function _drawDoorEW_open(ctx, px, py, s, woodMid, woodLight, metalCol, frameSt) {
  const inset = Math.round(s * 0.08);
  const dh = s - inset * 2;
  const panelEdge = Math.round(s * 0.14);

  // Stone frame
  ctx.fillStyle = frameSt;
  ctx.fillRect(px + inset, py + inset - 2, s - inset * 2, 3);
  ctx.fillRect(px + inset, py + s - inset - 1, s - inset * 2, 3);

  // Panel flat against north wall
  ctx.fillStyle = woodMid;
  ctx.fillRect(px + inset + 2, py + inset, s - inset * 2 - 4, panelEdge);
  ctx.fillStyle = woodLight;
  ctx.fillRect(px + inset + 2, py + inset, s - inset * 2 - 4, 1);
  ctx.fillStyle = metalCol;
  ctx.fillRect(px + inset + 2, py + inset + panelEdge - 2, s - inset * 2 - 4, 2);
  ctx.fillStyle = 'rgba(0,0,0,0.12)';
  ctx.fillRect(px + inset + 2, py + inset + panelEdge, s - inset * 2 - 4, 2);
}

/**
 * Draw a chest tile using theme palette.
 * Renders a detailed barrel-lidded chest with curved dome lid, wood plank
 * texture, metal corner brackets, prominent lock plate, ground shadow,
 * and palette-driven colors. Supports opened/closed states.
 */
export function drawChest(ctx, x, y, size, seed, palette, theme, isOpened) {
  // Floor underneath
  const h = cellHash;
  const floorFn = FLOOR_DRAW_MAP[theme.floor.style] || drawFloor_flagstone;
  floorFn(ctx, x, y, size, seed, palette, theme.floor);

  // Chest colors from palette
  const bodyColor = isOpened ? shiftColor(palette.accent, -20) : (palette.highlight || '#DAA520');
  const bodyDark = shiftColor(bodyColor, -30);
  const bodyHi = shiftColor(bodyColor, 20);
  const bandColor = shiftColor(palette.primary, -10);
  const latchColor = palette.highlight || '#FFD700';
  const lidColor = shiftColor(bodyColor, 10);

  // Proportions
  const cw = size * 0.58;
  const ch = size * 0.42;
  const lidH = size * 0.18;
  const cx = x + (size - cw) / 2;
  const cy = y + (size - ch - lidH) / 2 + size * 0.08;
  const lidY = cy - lidH;
  const lidOverhang = cw * 0.06;
  const lx = cx - lidOverhang;
  const lw = cw + lidOverhang * 2;
  const domeH = lidH * 0.85;

  // ── Ground shadow ──
  ctx.save();
  ctx.fillStyle = 'rgba(0, 0, 0, 0.35)';
  ctx.beginPath();
  ctx.ellipse(cx + cw / 2, cy + ch + size * 0.02, cw * 0.52, size * 0.05, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  // ── Helper: barrel-curved lid path ──
  const _lidPath = () => {
    ctx.beginPath();
    ctx.moveTo(lx, lidY + lidH);
    ctx.lineTo(lx, lidY + lidH - domeH * 0.3);
    ctx.quadraticCurveTo(lx + lw * 0.5, lidY - domeH * 0.4, lx + lw, lidY + lidH - domeH * 0.3);
    ctx.lineTo(lx + lw, lidY + lidH);
    ctx.closePath();
  };

  // ── Helper: draw wood plank lines ──
  const _drawPlanks = (px2, py2, w, h2, color, count) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = 0.7;
    const gap = w / (count + 1);
    for (let i = 1; i <= count; i++) {
      const ppx = px2 + gap * i;
      ctx.beginPath();
      ctx.moveTo(ppx, py2 + 1);
      ctx.lineTo(ppx, py2 + h2 - 1);
      ctx.stroke();
    }
  };

  // ── Helper: corner brackets ──
  const _drawCornerBrackets = () => {
    const bLen = Math.max(3, cw * 0.14);
    const bW = Math.max(1.5, cw * 0.04);
    ctx.fillStyle = bandColor;
    ctx.fillRect(cx, cy, bLen, bW);
    ctx.fillRect(cx, cy, bW, bLen);
    ctx.fillRect(cx + cw - bLen, cy, bLen, bW);
    ctx.fillRect(cx + cw - bW, cy, bW, bLen);
    ctx.fillRect(cx, cy + ch - bW, bLen, bW);
    ctx.fillRect(cx, cy + ch - bLen, bW, bLen);
    ctx.fillRect(cx + cw - bLen, cy + ch - bW, bLen, bW);
    ctx.fillRect(cx + cw - bW, cy + ch - bLen, bW, bLen);
    // Corner rivets
    const rr = Math.max(1, bW * 0.7);
    ctx.fillStyle = bodyHi;
    for (const [rx, ry] of [
      [cx + bW, cy + bW], [cx + cw - bW, cy + bW],
      [cx + bW, cy + ch - bW], [cx + cw - bW, cy + ch - bW],
    ]) {
      ctx.beginPath();
      ctx.arc(rx, ry, rr, 0, Math.PI * 2);
      ctx.fill();
    }
  };

  // ── Helper: band rivets ──
  const _drawBandRivets = (bandY2, bandH2) => {
    const rr = Math.max(0.8, bandH2 * 0.5);
    ctx.fillStyle = bodyHi;
    for (let i = 0; i < 3; i++) {
      ctx.beginPath();
      ctx.arc(cx + cw * (0.2 + i * 0.3), bandY2 + bandH2 / 2, rr, 0, Math.PI * 2);
      ctx.fill();
    }
  };

  if (!isOpened) {
    // ── Body ──
    ctx.fillStyle = bodyColor;
    ctx.fillRect(cx, cy, cw, ch);
    // Wood plank lines
    _drawPlanks(cx, cy, cw, ch, bodyDark, 3);
    // Right-edge shadow
    ctx.fillStyle = bodyDark;
    ctx.fillRect(cx + cw - cw * 0.12, cy, cw * 0.12, ch);
    // Left-edge highlight
    ctx.fillStyle = bodyHi;
    ctx.fillRect(cx, cy, cw * 0.06, ch);
    // Body border
    ctx.strokeStyle = bodyDark;
    ctx.lineWidth = 1;
    ctx.strokeRect(cx, cy, cw, ch);

    // ── Metal bands (thicker, with highlights & shadow) ──
    const bandH = Math.max(2, size * 0.05);
    const band1Y = cy + ch * 0.22;
    const band2Y = cy + ch * 0.68;
    ctx.fillStyle = bandColor;
    ctx.fillRect(cx, band1Y, cw, bandH);
    ctx.fillRect(cx, band2Y, cw, bandH);
    ctx.fillStyle = bodyHi;
    ctx.globalAlpha = 0.3;
    ctx.fillRect(cx, band1Y, cw, 1);
    ctx.fillRect(cx, band2Y, cw, 1);
    ctx.globalAlpha = 1.0;
    ctx.fillStyle = bodyDark;
    ctx.fillRect(cx, band1Y + bandH - 1, cw, 1);
    ctx.fillRect(cx, band2Y + bandH - 1, cw, 1);
    // Band rivets
    _drawBandRivets(band1Y, bandH);
    _drawBandRivets(band2Y, bandH);

    // ── Corner brackets ──
    _drawCornerBrackets();

    // ── Curved lid ──
    ctx.fillStyle = lidColor;
    _lidPath();
    ctx.fill();
    // Lid highlight
    ctx.save();
    _lidPath();
    ctx.clip();
    ctx.fillStyle = bodyHi;
    ctx.globalAlpha = 0.35;
    ctx.fillRect(lx + 2, lidY, lw - 4, lidH * 0.35);
    ctx.globalAlpha = 1.0;
    ctx.restore();
    // Lid border
    ctx.strokeStyle = bodyDark;
    ctx.lineWidth = 1;
    _lidPath();
    ctx.stroke();
    // Lid metal band
    const lidBandY = lidY + lidH * 0.55;
    ctx.fillStyle = bandColor;
    ctx.fillRect(lx + 1, lidBandY, lw - 2, Math.max(1.5, size * 0.03));

    // ── Lock (ornate circular with keyhole) ──
    const lockCX = cx + cw / 2;
    const lockCY = cy + ch * 0.30;
    const lockR = Math.max(3.5, size * 0.06);
    ctx.fillStyle = latchColor;
    ctx.beginPath();
    ctx.arc(lockCX, lockCY + lockR, lockR, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = bandColor;
    ctx.lineWidth = Math.max(1.2, size * 0.025);
    ctx.stroke();
    ctx.strokeStyle = bodyHi;
    ctx.lineWidth = 0.6;
    ctx.beginPath();
    ctx.arc(lockCX, lockCY + lockR, lockR * 0.65, 0, Math.PI * 2);
    ctx.stroke();
    // Keyhole
    ctx.fillStyle = bodyDark;
    ctx.beginPath();
    ctx.arc(lockCX, lockCY + lockR, Math.max(1.2, size * 0.02), 0, Math.PI * 2);
    ctx.fill();
    ctx.fillRect(lockCX - size * 0.008, lockCY + lockR, size * 0.016, lockR * 0.5);

    // ── Lid-to-body seam ──
    ctx.strokeStyle = bodyDark;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(cx - lidOverhang * 0.5, cy);
    ctx.lineTo(cx + cw + lidOverhang * 0.5, cy);
    ctx.stroke();
  } else {
    // ── Opened body ──
    ctx.fillStyle = bodyColor;
    ctx.fillRect(cx, cy, cw, ch);
    // Faded plank lines
    ctx.globalAlpha = 0.5;
    _drawPlanks(cx, cy, cw, ch, bodyDark, 3);
    ctx.globalAlpha = 1.0;
    // Right-edge shadow
    ctx.fillStyle = bodyDark;
    ctx.fillRect(cx + cw - cw * 0.12, cy, cw * 0.12, ch);
    ctx.strokeStyle = bodyDark;
    ctx.lineWidth = 1;
    ctx.strokeRect(cx, cy, cw, ch);

    // Faded bands
    const bandH = Math.max(2, size * 0.05);
    ctx.fillStyle = bandColor;
    ctx.globalAlpha = 0.45;
    ctx.fillRect(cx, cy + ch * 0.22, cw, bandH);
    ctx.fillRect(cx, cy + ch * 0.68, cw, bandH);
    ctx.globalAlpha = 1.0;

    // Faded corner brackets
    ctx.globalAlpha = 0.5;
    _drawCornerBrackets();
    ctx.globalAlpha = 1.0;

    // ── Interior (dark cavity with golden rim + sparkles) ──
    const interiorH = ch * 0.40;
    ctx.fillStyle = latchColor;
    ctx.globalAlpha = 0.25;
    ctx.fillRect(cx + 1, cy, cw - 2, 2);
    ctx.globalAlpha = 1.0;
    ctx.fillStyle = '#08081A';
    ctx.fillRect(cx + 2, cy + 2, cw - 4, interiorH);
    ctx.fillStyle = 'rgba(255, 215, 0, 0.2)';
    ctx.fillRect(cx + 3, cy + 3, cw - 6, interiorH - 2);
    // Sparkle dots
    for (let i = 0; i < 2; i++) {
      const sx = cx + cw * 0.25 + cw * 0.5 * (i / 2);
      const sy2 = cy + interiorH * 0.3 + (i % 2) * interiorH * 0.3;
      const sr = Math.max(0.8, size * 0.015);
      ctx.fillStyle = '#FFE880';
      ctx.beginPath();
      ctx.arc(sx, sy2, sr, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.8)';
      ctx.beginPath();
      ctx.arc(sx, sy2, sr * 0.4, 0, Math.PI * 2);
      ctx.fill();
    }

    // ── Open lid (curved, tilted back) ──
    const openLidH = lidH * 0.5;
    const openLidY = lidY - openLidH * 0.2;
    ctx.fillStyle = bodyColor;
    ctx.beginPath();
    ctx.moveTo(lx, openLidY + openLidH);
    ctx.lineTo(lx, openLidY + openLidH * 0.4);
    ctx.quadraticCurveTo(lx + lw * 0.5, openLidY - openLidH * 0.2, lx + lw, openLidY + openLidH * 0.4);
    ctx.lineTo(lx + lw, openLidY + openLidH);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = bodyDark;
    ctx.lineWidth = 1;
    ctx.stroke();
    // Lid inside (dark underside)
    ctx.fillStyle = bodyDark;
    ctx.fillRect(lx + 2, openLidY + openLidH * 0.7, lw - 4, openLidH * 0.3);

    // Hinges
    ctx.fillStyle = bandColor;
    const hingeR = Math.max(1.2, size * 0.02);
    ctx.beginPath();
    ctx.arc(cx + 2, cy, hingeR, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(cx + cw - 2, cy, hingeR, 0, Math.PI * 2);
    ctx.fill();
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
  rough_hewn:     drawWall_roughHewn,
  bone_stack:     drawWall_boneStack,
  ashlar_block:   drawWall_ashlarBlock,
  fungal_growth:  drawWall_fungalGrowth,
  ice_crystal:    drawWall_iceCrystal,
  blood_stone:    drawWall_bloodStone,
};

/** Maps floor style string → drawing function */
export const FLOOR_DRAW_MAP = {
  flagstone:      drawFloor_flagstone,
  ash_covered:    drawFloor_ashCovered,
  flooded:        drawFloor_flooded,
  cracked_marble: drawFloor_crackedMarble,
  metal_grate:    drawFloor_metalGrate,
  packed_earth:   drawFloor_packedEarth,
  polished_slab:  drawFloor_polishedSlab,
  dusty_tile:     drawFloor_dustyTile,
  mycelium_mat:   drawFloor_myceliumMat,
  frozen_stone:   drawFloor_frozenStone,
  ritual_tile:    drawFloor_ritualTile,
};


// ═══════════════════════════════════════════════════════════
//  WALL-EDGE TRANSITION STYLES
// ═══════════════════════════════════════════════════════════

/**
 * Bleeding Catacombs edge — crumbled stone rubble along wall boundary.
 * 2-3 small stone-colored rectangles scattered along the wall edge.
 */
export function drawEdge_crumble(ctx, x, y, size, side, seed, palette, edgeConfig) {
  const h = cellHash;
  const w = edgeConfig.width || 4;
  const alpha = edgeConfig.intensity || 0.6;
  const count = 2 + Math.floor(h(seed, 0, 60) * 2); // 2-3 rubble pieces

  for (let i = 0; i < count; i++) {
    const pos = h(seed, i, 61) * (size - 6) + 2; // position along the edge
    const rw = 3 + h(seed, i, 62) * 4;            // rubble width 3-7px
    const rh = 2 + h(seed, i, 63) * (w - 1);      // rubble height within edge width

    ctx.fillStyle = hexAlpha(palette.secondary, alpha);

    if (side === 'top') {
      ctx.fillRect(x + pos, y, rw, rh);
    } else if (side === 'bottom') {
      ctx.fillRect(x + pos, y + size - rh, rw, rh);
    } else if (side === 'left') {
      ctx.fillRect(x, y + pos, rh, rw);
    } else {
      ctx.fillRect(x + size - rh, y + pos, rh, rw);
    }
  }
}

/**
 * Ashen Undercroft edge — gradient darkening toward the wall edge (scorch mark).
 * 4px fade from opaque charred to transparent.
 */
export function drawEdge_scorch(ctx, x, y, size, side, seed, palette, edgeConfig) {
  const w = edgeConfig.width || 4;
  const alpha = edgeConfig.intensity || 0.7;

  for (let i = 0; i < w; i++) {
    const a = alpha * (1 - i / w) * 0.3; // fade from wall edge outward
    ctx.fillStyle = `rgba(10, 8, 5, ${a})`;

    if (side === 'top') {
      ctx.fillRect(x, y + i, size, 1);
    } else if (side === 'bottom') {
      ctx.fillRect(x, y + size - 1 - i, size, 1);
    } else if (side === 'left') {
      ctx.fillRect(x + i, y, 1, size);
    } else {
      ctx.fillRect(x + size - 1 - i, y, 1, size);
    }
  }
}

/**
 * Drowned Sanctum edge — thin green-tinted semi-transparent irregular line (moss creep).
 */
export function drawEdge_mossCreep(ctx, x, y, size, side, seed, palette, edgeConfig) {
  const h = cellHash;
  const w = edgeConfig.width || 3;
  const alpha = edgeConfig.intensity || 0.5;

  ctx.strokeStyle = hexAlpha(palette.accent, alpha * 0.5);
  ctx.lineWidth = 1;
  ctx.beginPath();

  const segments = 4 + Math.floor(h(seed, 0, 70) * 3);
  if (side === 'top' || side === 'bottom') {
    const ey = side === 'top' ? y + 1 : y + size - 2;
    ctx.moveTo(x, ey);
    for (let i = 1; i <= segments; i++) {
      const sx = x + (i / segments) * size;
      const sy = ey + (h(seed, i, 71) - 0.5) * w;
      ctx.lineTo(sx, sy);
    }
  } else {
    const ex = side === 'left' ? x + 1 : x + size - 2;
    ctx.moveTo(ex, y);
    for (let i = 1; i <= segments; i++) {
      const sy = y + (i / segments) * size;
      const sx = ex + (h(seed, i, 72) - 0.5) * w;
      ctx.lineTo(sx, sy);
    }
  }
  ctx.stroke();

  // Tiny moss dots along edge
  const dotCount = 2 + Math.floor(h(seed, 0, 73) * 2);
  ctx.fillStyle = hexAlpha(palette.accent, alpha * 0.3);
  for (let i = 0; i < dotCount; i++) {
    const pos = h(seed, i, 74) * (size - 4) + 2;
    const offset = h(seed, i, 75) * (w - 1);
    if (side === 'top') {
      ctx.fillRect(x + pos, y + offset, 2, 2);
    } else if (side === 'bottom') {
      ctx.fillRect(x + pos, y + size - 1 - offset, 2, 2);
    } else if (side === 'left') {
      ctx.fillRect(x + offset, y + pos, 2, 2);
    } else {
      ctx.fillRect(x + size - 1 - offset, y + pos, 2, 2);
    }
  }
}

/**
 * Hollowed Cathedral edge — fine debris dots in a 4px strip along wall.
 */
export function drawEdge_rubbleStrip(ctx, x, y, size, side, seed, palette, edgeConfig) {
  const h = cellHash;
  const w = edgeConfig.width || 4;
  const alpha = edgeConfig.intensity || 0.5;
  const dotCount = 5 + Math.floor(h(seed, 0, 80) * 4); // 5-8 debris dots

  for (let i = 0; i < dotCount; i++) {
    const pos = h(seed, i, 81) * (size - 2) + 1;
    const offset = h(seed, i, 82) * w;
    const dotSize = 1 + Math.floor(h(seed, i, 83) * 1.5); // 1-2px dots

    ctx.fillStyle = hexAlpha(palette.secondary, alpha * (0.4 + h(seed, i, 84) * 0.3));

    if (side === 'top') {
      ctx.fillRect(x + pos, y + offset, dotSize, dotSize);
    } else if (side === 'bottom') {
      ctx.fillRect(x + pos, y + size - offset - dotSize, dotSize, dotSize);
    } else if (side === 'left') {
      ctx.fillRect(x + offset, y + pos, dotSize, dotSize);
    } else {
      ctx.fillRect(x + size - offset - dotSize, y + pos, dotSize, dotSize);
    }
  }
}

/**
 * Iron Depths edge — thin orange-brown drip line on floor near wall.
 */
export function drawEdge_rustDrip(ctx, x, y, size, side, seed, palette, edgeConfig) {
  const h = cellHash;
  const w = edgeConfig.width || 3;
  const alpha = edgeConfig.intensity || 0.6;

  // 1-2 thin drip lines
  const lines = 1 + Math.floor(h(seed, 0, 90) * 1.5);
  for (let l = 0; l < lines; l++) {
    const pos = 4 + h(seed, l, 91) * (size - 8); // position along edge
    ctx.strokeStyle = hexAlpha(palette.accent, alpha * 0.4);
    ctx.lineWidth = 0.8;
    ctx.beginPath();

    if (side === 'top') {
      ctx.moveTo(x + pos, y);
      ctx.lineTo(x + pos + (h(seed, l, 92) - 0.5) * 3, y + w);
    } else if (side === 'bottom') {
      ctx.moveTo(x + pos, y + size);
      ctx.lineTo(x + pos + (h(seed, l, 92) - 0.5) * 3, y + size - w);
    } else if (side === 'left') {
      ctx.moveTo(x, y + pos);
      ctx.lineTo(x + w, y + pos + (h(seed, l, 92) - 0.5) * 3);
    } else {
      ctx.moveTo(x + size, y + pos);
      ctx.lineTo(x + size - w, y + pos + (h(seed, l, 92) - 0.5) * 3);
    }
    ctx.stroke();
  }
}

/**
 * Forgotten Cellar edge — very faint grey gradient (2px) at wall base.
 */
export function drawEdge_dustDrift(ctx, x, y, size, side, seed, palette, edgeConfig) {
  const w = edgeConfig.width || 2;
  const alpha = edgeConfig.intensity || 0.4;

  for (let i = 0; i < w; i++) {
    const a = alpha * (1 - i / w) * 0.15;
    ctx.fillStyle = `rgba(60, 55, 45, ${a})`;

    if (side === 'top') {
      ctx.fillRect(x, y + i, size, 1);
    } else if (side === 'bottom') {
      ctx.fillRect(x, y + size - 1 - i, size, 1);
    } else if (side === 'left') {
      ctx.fillRect(x + i, y, 1, size);
    } else {
      ctx.fillRect(x + size - 1 - i, y, 1, size);
    }
  }
}

/**
 * Pale Ossuary edge — almost nothing, just a 1px darker seam line.
 */
export function drawEdge_cleanEdge(ctx, x, y, size, side, seed, palette, edgeConfig) {
  const alpha = edgeConfig.intensity || 0.3;
  ctx.fillStyle = hexAlpha(palette.grout, alpha);

  if (side === 'top') {
    ctx.fillRect(x, y, size, 1);
  } else if (side === 'bottom') {
    ctx.fillRect(x, y + size - 1, size, 1);
  } else if (side === 'left') {
    ctx.fillRect(x, y, 1, size);
  } else {
    ctx.fillRect(x + size - 1, y, 1, size);
  }
}

/**
 * Silent Vault edge — precise 1px geometric inset line matching wall grid.
 */
export function drawEdge_seamLine(ctx, x, y, size, side, seed, palette, edgeConfig) {
  const alpha = edgeConfig.intensity || 0.4;
  ctx.strokeStyle = hexAlpha(palette.mortar, alpha);
  ctx.lineWidth = 1;

  const inset = 2; // geometric inset from tile edge
  ctx.beginPath();
  if (side === 'top') {
    ctx.moveTo(x + inset, y + inset);
    ctx.lineTo(x + size - inset, y + inset);
  } else if (side === 'bottom') {
    ctx.moveTo(x + inset, y + size - inset);
    ctx.lineTo(x + size - inset, y + size - inset);
  } else if (side === 'left') {
    ctx.moveTo(x + inset, y + inset);
    ctx.lineTo(x + inset, y + size - inset);
  } else {
    ctx.moveTo(x + size - inset, y + inset);
    ctx.lineTo(x + size - inset, y + size - inset);
  }
  ctx.stroke();
}

/**
 * Fungal Grotto edge — spore tendrils creeping from wall onto floor.
 * Thin organic lines with tiny spore dots along the wall edge.
 */
export function drawEdge_sporeCreep(ctx, x, y, size, side, seed, palette, edgeConfig) {
  const h = cellHash;
  const w = edgeConfig.width || 5;
  const alpha = edgeConfig.intensity || 0.7;

  // Thin tendril lines creeping from wall edge
  const tendrilCount = 2 + Math.floor(h(seed, 0, 80) * 2);
  ctx.strokeStyle = hexAlpha(palette.accent, alpha * 0.35);
  ctx.lineWidth = 0.7;

  for (let i = 0; i < tendrilCount; i++) {
    const pos = h(seed, i, 81) * (size - 6) + 3;
    ctx.beginPath();
    if (side === 'top') {
      ctx.moveTo(x + pos, y);
      ctx.quadraticCurveTo(x + pos + (h(seed, i, 82) - 0.5) * 4, y + w * 0.5, x + pos + (h(seed, i, 83) - 0.5) * 6, y + w);
    } else if (side === 'bottom') {
      ctx.moveTo(x + pos, y + size);
      ctx.quadraticCurveTo(x + pos + (h(seed, i, 82) - 0.5) * 4, y + size - w * 0.5, x + pos + (h(seed, i, 83) - 0.5) * 6, y + size - w);
    } else if (side === 'left') {
      ctx.moveTo(x, y + pos);
      ctx.quadraticCurveTo(x + w * 0.5, y + pos + (h(seed, i, 82) - 0.5) * 4, x + w, y + pos + (h(seed, i, 83) - 0.5) * 6);
    } else {
      ctx.moveTo(x + size, y + pos);
      ctx.quadraticCurveTo(x + size - w * 0.5, y + pos + (h(seed, i, 82) - 0.5) * 4, x + size - w, y + pos + (h(seed, i, 83) - 0.5) * 6);
    }
    ctx.stroke();
  }

  // Tiny spore dots near edge
  const dotCount = 3 + Math.floor(h(seed, 0, 85) * 2);
  ctx.fillStyle = hexAlpha(palette.highlight, alpha * 0.3);
  for (let i = 0; i < dotCount; i++) {
    const pos = h(seed, i, 86) * (size - 4) + 2;
    const off = h(seed, i, 87) * (w - 1);
    if (side === 'top') ctx.fillRect(x + pos, y + off, 1, 1);
    else if (side === 'bottom') ctx.fillRect(x + pos, y + size - 1 - off, 1, 1);
    else if (side === 'left') ctx.fillRect(x + off, y + pos, 1, 1);
    else ctx.fillRect(x + size - 1 - off, y + pos, 1, 1);
  }
}

/**
 * Frozen Crypt edge — frost creep with ice crystal formations.
 * White-blue gradient fade from wall + tiny crystal glint dots.
 */
export function drawEdge_frostCreep(ctx, x, y, size, side, seed, palette, edgeConfig) {
  const h = cellHash;
  const w = edgeConfig.width || 6;
  const alpha = edgeConfig.intensity || 0.8;

  // Frost gradient from wall edge
  for (let i = 0; i < w; i++) {
    const a = alpha * 0.08 * (1 - i / w);
    ctx.fillStyle = `rgba(200, 220, 255, ${a})`;
    if (side === 'top') ctx.fillRect(x, y + i, size, 1);
    else if (side === 'bottom') ctx.fillRect(x, y + size - 1 - i, size, 1);
    else if (side === 'left') ctx.fillRect(x + i, y, 1, size);
    else ctx.fillRect(x + size - 1 - i, y, 1, size);
  }

  // Tiny ice crystal dots along edge
  const crystalCount = 2 + Math.floor(h(seed, 0, 90) * 3);
  for (let i = 0; i < crystalCount; i++) {
    const pos = h(seed, i, 91) * (size - 4) + 2;
    const off = h(seed, i, 92) * (w * 0.6);
    ctx.fillStyle = hexAlpha(palette.highlight, alpha * 0.4);
    if (side === 'top') ctx.fillRect(x + pos, y + off, 1, 1);
    else if (side === 'bottom') ctx.fillRect(x + pos, y + size - 1 - off, 1, 1);
    else if (side === 'left') ctx.fillRect(x + off, y + pos, 1, 1);
    else ctx.fillRect(x + size - 1 - off, y + pos, 1, 1);
  }

  // Thin frost line at edge boundary
  ctx.strokeStyle = hexAlpha('#ffffff', alpha * 0.12);
  ctx.lineWidth = 0.5;
  ctx.beginPath();
  if (side === 'top') { ctx.moveTo(x, y + 1); ctx.lineTo(x + size, y + 1); }
  else if (side === 'bottom') { ctx.moveTo(x, y + size - 2); ctx.lineTo(x + size, y + size - 2); }
  else if (side === 'left') { ctx.moveTo(x + 1, y); ctx.lineTo(x + 1, y + size); }
  else { ctx.moveTo(x + size - 2, y); ctx.lineTo(x + size - 2, y + size); }
  ctx.stroke();
}

/**
 * Cursed Shrine edge — blood seep dripping from wall onto floor.
 * Dark red gradient + thin drip lines from wall edge.
 */
export function drawEdge_bloodSeep(ctx, x, y, size, side, seed, palette, edgeConfig) {
  const h = cellHash;
  const w = edgeConfig.width || 4;
  const alpha = edgeConfig.intensity || 0.6;

  // Dark red gradient from wall edge
  for (let i = 0; i < w; i++) {
    const a = alpha * 0.06 * (1 - i / w);
    ctx.fillStyle = hexAlpha(palette.accent, a);
    if (side === 'top') ctx.fillRect(x, y + i, size, 1);
    else if (side === 'bottom') ctx.fillRect(x, y + size - 1 - i, size, 1);
    else if (side === 'left') ctx.fillRect(x + i, y, 1, size);
    else ctx.fillRect(x + size - 1 - i, y, 1, size);
  }

  // 1-2 thin drip lines (vertical for top/bottom, horizontal for left/right)
  const dripCount = 1 + Math.floor(h(seed, 0, 95) * 2);
  ctx.strokeStyle = hexAlpha(palette.accent, alpha * 0.3);
  ctx.lineWidth = 0.6;
  for (let i = 0; i < dripCount; i++) {
    const pos = h(seed, i, 96) * (size - 6) + 3;
    const len = w + h(seed, i, 97) * w * 0.5;
    ctx.beginPath();
    if (side === 'top') { ctx.moveTo(x + pos, y); ctx.lineTo(x + pos + (h(seed, i, 98) - 0.5) * 2, y + len); }
    else if (side === 'bottom') { ctx.moveTo(x + pos, y + size); ctx.lineTo(x + pos + (h(seed, i, 98) - 0.5) * 2, y + size - len); }
    else if (side === 'left') { ctx.moveTo(x, y + pos); ctx.lineTo(x + len, y + pos + (h(seed, i, 98) - 0.5) * 2); }
    else { ctx.moveTo(x + size, y + pos); ctx.lineTo(x + size - len, y + pos + (h(seed, i, 98) - 0.5) * 2); }
    ctx.stroke();
  }
}

/** Maps edge style string → drawing function */
export const EDGE_DRAW_MAP = {
  crumble:      drawEdge_crumble,
  scorch:       drawEdge_scorch,
  moss_creep:   drawEdge_mossCreep,
  rubble_strip: drawEdge_rubbleStrip,
  rust_drip:    drawEdge_rustDrip,
  dust_drift:   drawEdge_dustDrift,
  clean_edge:   drawEdge_cleanEdge,
  seam_line:    drawEdge_seamLine,
  spore_creep:  drawEdge_sporeCreep,
  frost_creep:  drawEdge_frostCreep,
  blood_seep:   drawEdge_bloodSeep,
};

/**
 * Draw a wall-edge transition on a floor tile for one side.
 * Called for each cardinal neighbor that is a wall.
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} x - Pixel X of the floor tile
 * @param {number} y - Pixel Y of the floor tile
 * @param {number} size - Tile size in pixels
 * @param {string} side - 'top', 'bottom', 'left', 'right'
 * @param {number} seed - Deterministic seed
 * @param {Object} palette - Theme palette
 * @param {Object} edgeConfig - { style, intensity, width }
 */
export function drawWallEdge(ctx, x, y, size, side, seed, palette, edgeConfig) {
  if (!edgeConfig || !edgeConfig.style) return;
  const fn = EDGE_DRAW_MAP[edgeConfig.style];
  if (fn) fn(ctx, x, y, size, side, seed, palette, edgeConfig);
}


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
