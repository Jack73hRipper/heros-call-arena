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
//  NEW PROPS (Phase 21 — Object Browser expansion)
// ═══════════════════════════════════════════════════════════

/**
 * Statue — Crumbling stone figure on a plinth. Upper body
 * silhouette with missing arm/head chip. Casts a long shadow.
 * Theme affinity: Cathedral, Ossuary, Boss rooms.
 */
function drawProp_statue(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const baseY = y + size * 0.85;
  const h = cellHash;

  // Long cast shadow behind the figure
  ctx.fillStyle = 'rgba(0,0,0,0.12)';
  ctx.beginPath();
  ctx.ellipse(cx + 3, baseY - 2, size * 0.18, size * 0.06, 0, 0, Math.PI * 2);
  ctx.fill();

  // Plinth (rectangular stone base)
  const plinthW = size * 0.34;
  const plinthH = size * 0.12;
  ctx.fillStyle = shiftColor(palette.secondary, 8);
  ctx.fillRect(cx - plinthW / 2, baseY - plinthH, plinthW, plinthH);
  ctx.strokeStyle = shiftColor(palette.secondary, -6);
  ctx.lineWidth = 0.6;
  ctx.strokeRect(cx - plinthW / 2, baseY - plinthH, plinthW, plinthH);

  // Torso — tapered trapezoid
  const torsoTop = baseY - plinthH - size * 0.35;
  const torsoBot = baseY - plinthH;
  ctx.fillStyle = lerpColor(palette.secondary, palette.metal || palette.secondary, 0.3);
  ctx.beginPath();
  ctx.moveTo(cx - size * 0.1, torsoBot);
  ctx.lineTo(cx + size * 0.1, torsoBot);
  ctx.lineTo(cx + size * 0.08, torsoTop);
  ctx.lineTo(cx - size * 0.08, torsoTop);
  ctx.closePath();
  ctx.fill();

  // Head — small circle atop torso
  const headY = torsoTop - size * 0.06;
  ctx.fillStyle = lerpColor(palette.secondary, palette.metal || palette.secondary, 0.25);
  ctx.beginPath();
  ctx.arc(cx, headY, size * 0.055, 0, Math.PI * 2);
  ctx.fill();

  // Chipped detail — missing corner (deterministic)
  if (h(seed, 0, 100) > 0.4) {
    ctx.fillStyle = palette.floor || palette.primary;
    ctx.fillRect(cx + size * 0.04, headY - size * 0.04, size * 0.04, size * 0.04);
  }

  // Highlight edge (stone catch-light)
  ctx.strokeStyle = hexAlpha(palette.highlight, 0.15);
  ctx.lineWidth = 0.8;
  ctx.beginPath();
  ctx.moveTo(cx - size * 0.08, torsoTop);
  ctx.lineTo(cx - size * 0.1, torsoBot);
  ctx.stroke();
}

/**
 * Throne — Ornate high-backed chair with armrests.
 * Dark wood frame, accent-colored seat cushion, metal studs.
 * Theme affinity: Boss rooms, Shrines.
 */
function drawProp_throne(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const baseY = y + size * 0.82;

  // Shadow beneath
  ctx.fillStyle = 'rgba(0,0,0,0.18)';
  ctx.beginPath();
  ctx.ellipse(cx + 1, baseY + 1, size * 0.16, size * 0.06, 0, 0, Math.PI * 2);
  ctx.fill();

  // High back rest — tall narrow rectangle
  const backW = size * 0.28;
  const backH = size * 0.55;
  const backX = cx - backW / 2;
  const backY = baseY - backH;
  ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, 3);
  ctx.fillRect(backX, backY, backW, backH);

  // Back border
  ctx.strokeStyle = shiftColor(palette.furniture || palette.secondary, -10);
  ctx.lineWidth = 0.8;
  ctx.strokeRect(backX, backY, backW, backH);

  // Ornate top finial — pointed triangle
  ctx.fillStyle = palette.metal || palette.secondary;
  ctx.beginPath();
  ctx.moveTo(cx, backY - size * 0.06);
  ctx.lineTo(cx - size * 0.06, backY);
  ctx.lineTo(cx + size * 0.06, backY);
  ctx.closePath();
  ctx.fill();

  // Seat cushion — accent colored
  const seatW = size * 0.32;
  const seatH = size * 0.1;
  ctx.fillStyle = hexAlpha(palette.accent, 0.55);
  ctx.fillRect(cx - seatW / 2, baseY - seatH - size * 0.05, seatW, seatH);

  // Armrests — two short horizontal bars
  const armY = baseY - size * 0.2;
  ctx.fillStyle = shiftColor(palette.furniture || palette.secondary, -2);
  ctx.fillRect(cx - size * 0.2, armY, size * 0.08, size * 0.04);
  ctx.fillRect(cx + size * 0.12, armY, size * 0.08, size * 0.04);

  // Metal studs on backrest corners
  ctx.fillStyle = hexAlpha(palette.highlight, 0.4);
  ctx.beginPath();
  ctx.arc(backX + 3, backY + 3, 1.2, 0, Math.PI * 2);
  ctx.arc(backX + backW - 3, backY + 3, 1.2, 0, Math.PI * 2);
  ctx.fill();
}

/**
 * Cage — Hanging iron cage with vertical bars and chain.
 * Overhead attachment chain, narrow vertical rectangle.
 * Theme affinity: Prison, Catacombs, Iron Depths.
 */
function drawProp_cage(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cageTop = y + size * 0.2;
  const cageBot = y + size * 0.75;
  const cageW = size * 0.32;
  const cageH = cageBot - cageTop;
  const metalColor = palette.metal || palette.secondary;

  // Chain from ceiling to cage top
  ctx.strokeStyle = shiftColor(metalColor, 5);
  ctx.lineWidth = 1;
  for (let ly = y; ly < cageTop; ly += 3) {
    const linkOff = ((ly / 3) | 0) % 2 === 0 ? -0.5 : 0.5;
    ctx.beginPath();
    ctx.moveTo(cx + linkOff, ly);
    ctx.lineTo(cx + linkOff, Math.min(ly + 2, cageTop));
    ctx.stroke();
  }

  // Cage frame outline
  ctx.strokeStyle = shiftColor(metalColor, 3);
  ctx.lineWidth = 1.2;
  ctx.strokeRect(cx - cageW / 2, cageTop, cageW, cageH);

  // Vertical bars (3-4 bars)
  const barCount = 3 + Math.floor(cellHash(seed, 0, 105) * 2);
  ctx.strokeStyle = shiftColor(metalColor, 0);
  ctx.lineWidth = 0.8;
  for (let b = 1; b < barCount; b++) {
    const barX = cx - cageW / 2 + (b / barCount) * cageW;
    ctx.beginPath();
    ctx.moveTo(barX, cageTop);
    ctx.lineTo(barX, cageBot);
    ctx.stroke();
  }

  // Horizontal crossbar mid-height
  ctx.beginPath();
  ctx.moveTo(cx - cageW / 2, cageTop + cageH * 0.5);
  ctx.lineTo(cx + cageW / 2, cageTop + cageH * 0.5);
  ctx.stroke();

  // Bottom shadow
  ctx.fillStyle = 'rgba(0,0,0,0.08)';
  ctx.beginPath();
  ctx.ellipse(cx, cageBot + 4, cageW * 0.4, 3, 0, 0, Math.PI * 2);
  ctx.fill();
}

/**
 * Weapon Rack — Wall-mounted rack with 2-3 weapon silhouettes.
 * Sword/spear shapes rendered as simple line + triangle combos.
 * Theme affinity: Enemy rooms, Boss rooms, Armory.
 */
function drawProp_weapon_rack(ctx, x, y, size, seed, palette) {
  const h = cellHash;
  const rackX = x + size * 0.15;
  const rackY = y + size * 0.08;
  const rackW = size * 0.7;
  const rackH = size * 0.8;
  const metalColor = palette.metal || palette.secondary;
  const woodColor = palette.furniture || palette.secondary;

  // Back board (wooden plank)
  ctx.fillStyle = shiftColor(woodColor, 3);
  ctx.fillRect(rackX, rackY, rackW, rackH);
  ctx.strokeStyle = shiftColor(woodColor, -8);
  ctx.lineWidth = 0.6;
  ctx.strokeRect(rackX, rackY, rackW, rackH);

  // Horizontal mounting pegs (2 rows)
  ctx.fillStyle = shiftColor(metalColor, 5);
  ctx.fillRect(rackX + 3, rackY + rackH * 0.28, rackW - 6, 1.5);
  ctx.fillRect(rackX + 3, rackY + rackH * 0.62, rackW - 6, 1.5);

  // Weapon 1 — Sword (angled line + pommel)
  const sw1X = rackX + rackW * 0.25;
  ctx.strokeStyle = shiftColor(metalColor, 8);
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(sw1X, rackY + rackH * 0.15);
  ctx.lineTo(sw1X, rackY + rackH * 0.75);
  ctx.stroke();
  // Crossguard
  ctx.strokeStyle = shiftColor(metalColor, 2);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(sw1X - 4, rackY + rackH * 0.6);
  ctx.lineTo(sw1X + 4, rackY + rackH * 0.6);
  ctx.stroke();

  // Weapon 2 — Mace (line + circle head)
  const sw2X = rackX + rackW * 0.55;
  ctx.strokeStyle = shiftColor(metalColor, 6);
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(sw2X, rackY + rackH * 0.2);
  ctx.lineTo(sw2X, rackY + rackH * 0.72);
  ctx.stroke();
  ctx.fillStyle = shiftColor(metalColor, 10);
  ctx.beginPath();
  ctx.arc(sw2X, rackY + rackH * 0.2, 3, 0, Math.PI * 2);
  ctx.fill();

  // Weapon 3 — Dagger (short line, conditional)
  if (h(seed, 0, 106) > 0.35) {
    const sw3X = rackX + rackW * 0.8;
    ctx.strokeStyle = shiftColor(metalColor, 4);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(sw3X, rackY + rackH * 0.35);
    ctx.lineTo(sw3X, rackY + rackH * 0.68);
    ctx.stroke();
  }
}

/**
 * Torch Sconce — Wall-mounted flaming torch with warm radial
 * glow. Metal bracket + flame tip. Universal lighting prop.
 * Theme affinity: Nearly all themes.
 */
function drawProp_torch_sconce(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const flameY = y + size * 0.25;
  const bracketY = y + size * 0.4;

  // Warm radial glow (large)
  const grad = ctx.createRadialGradient(cx, flameY, 1, cx, flameY, size * 0.45);
  grad.addColorStop(0, 'rgba(255, 180, 60, 0.18)');
  grad.addColorStop(0.5, 'rgba(255, 120, 30, 0.06)');
  grad.addColorStop(1, 'rgba(255, 80, 10, 0)');
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(cx, flameY, size * 0.45, 0, Math.PI * 2);
  ctx.fill();

  // Wall bracket (L-shaped metal piece)
  const metalColor = palette.metal || palette.secondary;
  ctx.strokeStyle = shiftColor(metalColor, 5);
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(cx, bracketY + size * 0.3);
  ctx.lineTo(cx, bracketY);
  ctx.lineTo(cx - size * 0.08, bracketY + size * 0.04);
  ctx.stroke();

  // Torch handle (vertical stick)
  ctx.strokeStyle = shiftColor(palette.furniture || palette.secondary, 5);
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(cx, bracketY);
  ctx.lineTo(cx, flameY + 4);
  ctx.stroke();

  // Flame outer (orange teardrop)
  ctx.fillStyle = 'rgba(255, 130, 30, 0.6)';
  ctx.beginPath();
  ctx.moveTo(cx, flameY - 5);
  ctx.quadraticCurveTo(cx + 4, flameY, cx, flameY + 3);
  ctx.quadraticCurveTo(cx - 4, flameY, cx, flameY - 5);
  ctx.fill();

  // Flame core (bright yellow)
  ctx.fillStyle = 'rgba(255, 220, 80, 0.75)';
  ctx.beginPath();
  ctx.arc(cx, flameY, 2.0, 0, Math.PI * 2);
  ctx.fill();
}

/**
 * Skull Pile — Mound of 3-5 overlapping skull circles with
 * eye socket dots. Grim ossuary / crypt decoration.
 * Theme affinity: Catacombs, Ossuary, Cursed Shrine.
 */
function drawProp_skull_pile(ctx, x, y, size, seed, palette) {
  const h = cellHash;
  const baseY = y + size * 0.6;
  const cx = x + size / 2;
  const boneColor = lerpColor(palette.secondary, '#d8d0c0', 0.3);

  // Shadow beneath the pile
  ctx.fillStyle = 'rgba(0,0,0,0.12)';
  ctx.beginPath();
  ctx.ellipse(cx, baseY + 4, size * 0.2, size * 0.06, 0, 0, Math.PI * 2);
  ctx.fill();

  // Scattered bone fragments underneath
  for (let i = 0; i < 3; i++) {
    const bx = cx - size * 0.12 + h(seed, i, 110) * size * 0.24;
    const by = baseY + h(seed, i, 111) * 4;
    ctx.fillStyle = shiftColor(boneColor, -5);
    ctx.fillRect(bx, by, 3 + h(seed, i, 112) * 3, 1.5);
  }

  // Skulls (3-5 overlapping circles, front-to-back)
  const count = 3 + Math.floor(h(seed, 0, 113) * 3);
  for (let i = count - 1; i >= 0; i--) {
    const sx = cx + (h(seed, i, 114) - 0.5) * size * 0.22;
    const sy = baseY - size * 0.06 - i * size * 0.06 + h(seed, i, 115) * size * 0.04;
    const sr = size * 0.05 + h(seed, i, 116) * size * 0.02;

    // Skull circle
    ctx.fillStyle = shiftColor(boneColor, Math.floor((h(seed, i, 117) - 0.5) * 8));
    ctx.beginPath();
    ctx.arc(sx, sy, sr, 0, Math.PI * 2);
    ctx.fill();

    // Eye sockets (two tiny dark dots)
    ctx.fillStyle = 'rgba(0,0,0,0.5)';
    ctx.beginPath();
    ctx.arc(sx - sr * 0.35, sy - sr * 0.15, sr * 0.2, 0, Math.PI * 2);
    ctx.arc(sx + sr * 0.35, sy - sr * 0.15, sr * 0.2, 0, Math.PI * 2);
    ctx.fill();
  }
}

/**
 * Mushroom Cluster — 2-4 bioluminescent fungi with soft glow.
 * Cap + stem silhouettes, radial glow halo. Organic feel.
 * Theme affinity: Fungal Grotto, Drowned Sanctum.
 */
function drawProp_mushroom_cluster(ctx, x, y, size, seed, palette) {
  const h = cellHash;
  const cx = x + size / 2;
  const baseY = y + size * 0.75;
  const glowColor = palette.accent;

  // Soft ground-level glow
  const grad = ctx.createRadialGradient(cx, baseY - size * 0.1, 2, cx, baseY - size * 0.1, size * 0.32);
  grad.addColorStop(0, hexAlpha(glowColor, 0.12));
  grad.addColorStop(1, hexAlpha(glowColor, 0));
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(cx, baseY - size * 0.1, size * 0.32, 0, Math.PI * 2);
  ctx.fill();

  const count = 2 + Math.floor(h(seed, 0, 120) * 3); // 2-4 mushrooms
  for (let i = 0; i < count; i++) {
    const mx = cx + (h(seed, i, 121) - 0.5) * size * 0.3;
    const stemH = size * 0.12 + h(seed, i, 122) * size * 0.12;
    const stemBot = baseY - h(seed, i, 123) * size * 0.05;
    const stemTop = stemBot - stemH;
    const capR = size * 0.04 + h(seed, i, 124) * size * 0.03;

    // Stem
    ctx.strokeStyle = shiftColor(palette.secondary, 10);
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(mx, stemBot);
    ctx.lineTo(mx, stemTop);
    ctx.stroke();

    // Cap (semicircle on top of stem)
    ctx.fillStyle = hexAlpha(glowColor, 0.6 + h(seed, i, 125) * 0.2);
    ctx.beginPath();
    ctx.arc(mx, stemTop, capR, Math.PI, Math.PI * 2);
    ctx.fill();

    // Cap highlight dot
    ctx.fillStyle = hexAlpha(palette.highlight, 0.3);
    ctx.beginPath();
    ctx.arc(mx - capR * 0.3, stemTop - capR * 0.3, capR * 0.25, 0, Math.PI * 2);
    ctx.fill();
  }
}

/**
 * Web — Corner spider web radiating from top-left of tile.
 * Concentric arcs + radial lines, semi-transparent.
 * Theme affinity: Cellar, Empty rooms, Catacombs.
 */
function drawProp_web(ctx, x, y, size, seed, palette) {
  const originX = x + size * 0.05;
  const originY = y + size * 0.05;
  const reach = size * 0.55;
  const webColor = 'rgba(180, 180, 170, 0.12)';
  const webColorStrong = 'rgba(180, 180, 170, 0.18)';

  // Radial lines from corner (4-5 spokes)
  const spokes = 4 + Math.floor(cellHash(seed, 0, 130) * 2);
  ctx.strokeStyle = webColorStrong;
  ctx.lineWidth = 0.5;
  for (let s = 0; s < spokes; s++) {
    const angle = (s / (spokes - 1)) * Math.PI * 0.5; // quarter circle
    const endX = originX + Math.cos(angle) * reach;
    const endY = originY + Math.sin(angle) * reach;
    ctx.beginPath();
    ctx.moveTo(originX, originY);
    ctx.lineTo(endX, endY);
    ctx.stroke();
  }

  // Concentric arcs (3 rings)
  ctx.strokeStyle = webColor;
  ctx.lineWidth = 0.4;
  for (let ring = 1; ring <= 3; ring++) {
    const r = reach * ring / 4;
    ctx.beginPath();
    ctx.arc(originX, originY, r, 0, Math.PI * 0.5);
    ctx.stroke();
  }
}

// ═══════════════════════════════════════════════════════════
//  NEW PROPS (Object Browser Expansion — Quality Batch)
// ═══════════════════════════════════════════════════════════

/**
 * Fountain — Crumbling octagonal stone basin with still dark
 * water, concentric ripple rings, and moss-stained edges.
 * Multi-layered: shadow → basin → water → rim → ripples → moss.
 * Theme affinity: Cathedral, Drowned Sanctum, Shrine, Vault.
 */
function drawProp_fountain(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size * 0.52;
  const h = cellHash;
  const basinR = size * 0.32;
  const rimR = basinR + size * 0.04;
  const stoneColor = lerpColor(palette.secondary, palette.metal || palette.secondary, 0.2);

  // Ground shadow (elliptical, offset)
  ctx.fillStyle = 'rgba(0,0,0,0.18)';
  ctx.beginPath();
  ctx.ellipse(cx + 2, cy + basinR * 0.6, rimR * 1.1, rimR * 0.35, 0, 0, Math.PI * 2);
  ctx.fill();

  // Stone basin base (octagonal approximation — 8-sided polygon)
  ctx.fillStyle = shiftColor(stoneColor, 4);
  ctx.beginPath();
  for (let i = 0; i < 8; i++) {
    const angle = (i / 8) * Math.PI * 2 - Math.PI / 8;
    const px = cx + Math.cos(angle) * basinR;
    const py = cy + Math.sin(angle) * basinR * 0.6; // perspective squish
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
  ctx.fill();

  // Basin inner shadow (darker recessed area)
  ctx.fillStyle = shiftColor(stoneColor, -12);
  ctx.beginPath();
  for (let i = 0; i < 8; i++) {
    const angle = (i / 8) * Math.PI * 2 - Math.PI / 8;
    const px = cx + Math.cos(angle) * (basinR - size * 0.04);
    const py = cy + Math.sin(angle) * (basinR - size * 0.04) * 0.6;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.closePath();
  ctx.fill();

  // Dark water surface (slightly reflective)
  const waterColor = palette.accent;
  ctx.fillStyle = hexAlpha(waterColor, 0.15);
  ctx.beginPath();
  ctx.ellipse(cx, cy, basinR * 0.72, basinR * 0.42, 0, 0, Math.PI * 2);
  ctx.fill();

  // Concentric ripple rings (2-3 subtle rings)
  const rippleCount = 2 + Math.floor(h(seed, 0, 200) * 2);
  for (let r = 0; r < rippleCount; r++) {
    const ripR = basinR * (0.2 + r * 0.22);
    ctx.strokeStyle = hexAlpha(palette.highlight, 0.06 + r * 0.02);
    ctx.lineWidth = 0.4;
    ctx.beginPath();
    ctx.ellipse(cx, cy, ripR, ripR * 0.58, 0, 0, Math.PI * 2);
    ctx.stroke();
  }

  // Outer rim highlight (catch-light on front edge)
  ctx.strokeStyle = hexAlpha(palette.highlight, 0.12);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.ellipse(cx, cy, basinR, basinR * 0.6, 0, Math.PI * 0.6, Math.PI * 1.4);
  ctx.stroke();

  // Central pedestal column (small circle rising from center)
  const pedR = size * 0.04;
  ctx.fillStyle = shiftColor(stoneColor, 8);
  ctx.beginPath();
  ctx.arc(cx, cy - size * 0.06, pedR, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = shiftColor(stoneColor, 12);
  ctx.beginPath();
  ctx.arc(cx, cy - size * 0.1, pedR * 0.7, 0, Math.PI * 2);
  ctx.fill();

  // Water drip from pedestal (thin line + small dot)
  ctx.strokeStyle = hexAlpha(waterColor, 0.2);
  ctx.lineWidth = 0.6;
  ctx.beginPath();
  ctx.moveTo(cx + 1, cy - size * 0.06);
  ctx.lineTo(cx + 1, cy + size * 0.02);
  ctx.stroke();

  // Moss staining on rim (2-3 small patches)
  for (let m = 0; m < 3; m++) {
    if (h(seed, m, 201) > 0.5) continue;
    const mAngle = h(seed, m, 202) * Math.PI * 2;
    const mx = cx + Math.cos(mAngle) * basinR * 0.85;
    const my = cy + Math.sin(mAngle) * basinR * 0.5;
    ctx.fillStyle = 'rgba(40, 70, 35, 0.15)';
    ctx.beginPath();
    ctx.arc(mx, my, size * 0.025 + h(seed, m, 203) * size * 0.015, 0, Math.PI * 2);
    ctx.fill();
  }

  // Crumbled chip on rim (one missing section)
  if (h(seed, 0, 204) > 0.4) {
    const chipAngle = h(seed, 0, 205) * Math.PI - Math.PI * 0.5;
    const chipX = cx + Math.cos(chipAngle) * basinR;
    const chipY = cy + Math.sin(chipAngle) * basinR * 0.6;
    ctx.fillStyle = palette.floor || palette.primary;
    ctx.fillRect(chipX - 2, chipY - 1, 4, 3);
  }
}

/**
 * Candelabra — Tall ornate multi-armed candle holder with
 * individual flames, wax drips, metallic sheen, and warm
 * ambient glow. 3-5 arms radiating from a central pillar.
 * Theme affinity: Cathedral, Shrine, Vault, Boss rooms.
 */
function drawProp_candelabra(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const baseY = y + size * 0.88;
  const h = cellHash;
  const metalColor = palette.metal || palette.secondary;

  // Warm ambient glow (large radial, soft)
  const glowGrad = ctx.createRadialGradient(cx, y + size * 0.3, 2, cx, y + size * 0.35, size * 0.48);
  glowGrad.addColorStop(0, 'rgba(255, 190, 80, 0.10)');
  glowGrad.addColorStop(0.5, 'rgba(255, 140, 40, 0.04)');
  glowGrad.addColorStop(1, 'rgba(255, 100, 20, 0)');
  ctx.fillStyle = glowGrad;
  ctx.beginPath();
  ctx.arc(cx, y + size * 0.35, size * 0.48, 0, Math.PI * 2);
  ctx.fill();

  // Base plate (small circle on ground)
  ctx.fillStyle = shiftColor(metalColor, 8);
  ctx.beginPath();
  ctx.ellipse(cx, baseY, size * 0.08, size * 0.03, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = shiftColor(metalColor, -5);
  ctx.lineWidth = 0.5;
  ctx.beginPath();
  ctx.ellipse(cx, baseY, size * 0.08, size * 0.03, 0, 0, Math.PI * 2);
  ctx.stroke();

  // Central pillar (vertical line with slight taper)
  const pillarTop = y + size * 0.28;
  ctx.strokeStyle = shiftColor(metalColor, 5);
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.moveTo(cx, baseY);
  ctx.lineTo(cx, pillarTop);
  ctx.stroke();

  // Pillar highlight (thin bright line on left edge)
  ctx.strokeStyle = hexAlpha(palette.highlight, 0.15);
  ctx.lineWidth = 0.6;
  ctx.beginPath();
  ctx.moveTo(cx - 1, baseY - size * 0.1);
  ctx.lineTo(cx - 1, pillarTop + size * 0.05);
  ctx.stroke();

  // Ornamental ring at junction
  ctx.fillStyle = shiftColor(metalColor, 12);
  ctx.beginPath();
  ctx.ellipse(cx, pillarTop + size * 0.12, size * 0.035, size * 0.015, 0, 0, Math.PI * 2);
  ctx.fill();

  // Arms + candles (3-5 arms, symmetrically spread)
  const armCount = 3 + Math.floor(h(seed, 0, 210) * 3); // 3-5
  const armY = pillarTop + size * 0.1;

  for (let i = 0; i < armCount; i++) {
    // Distribute arms evenly across horizontal span
    const t = armCount === 1 ? 0.5 : i / (armCount - 1);
    const armEndX = cx + (t - 0.5) * size * 0.6;
    const armEndY = armY - size * 0.02 + Math.abs(t - 0.5) * size * 0.08;

    // Arm (curved metal bar)
    ctx.strokeStyle = shiftColor(metalColor, 3);
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(cx, armY);
    const cpY = armY - size * 0.06;
    ctx.quadraticCurveTo((cx + armEndX) / 2, cpY, armEndX, armEndY);
    ctx.stroke();

    // Candle cup (small circle at arm end)
    ctx.fillStyle = shiftColor(metalColor, 6);
    ctx.beginPath();
    ctx.arc(armEndX, armEndY, size * 0.02, 0, Math.PI * 2);
    ctx.fill();

    // Candle stick (short white/cream rect)
    const candleH = size * 0.06 + h(seed, i, 211) * size * 0.04;
    const candleTop = armEndY - candleH;
    ctx.fillStyle = lerpColor('#e8e0d0', palette.secondary, 0.15);
    ctx.fillRect(armEndX - 1, candleTop, 2.5, candleH);

    // Wax drip (tiny bulge on candle side, deterministic)
    if (h(seed, i, 212) > 0.4) {
      const dripSide = h(seed, i, 213) > 0.5 ? 1.5 : -1;
      const dripY = candleTop + candleH * 0.3 + h(seed, i, 214) * candleH * 0.4;
      ctx.fillStyle = lerpColor('#d8d0c0', palette.secondary, 0.2);
      ctx.beginPath();
      ctx.arc(armEndX + dripSide, dripY, 1, 0, Math.PI * 2);
      ctx.fill();
    }

    // Flame (teardrop shape, orange→yellow core)
    const flameX = armEndX;
    const flameY = candleTop - 2;

    // Flame outer glow
    ctx.fillStyle = 'rgba(255, 140, 30, 0.35)';
    ctx.beginPath();
    ctx.moveTo(flameX, flameY - 4);
    ctx.quadraticCurveTo(flameX + 3, flameY, flameX, flameY + 2);
    ctx.quadraticCurveTo(flameX - 3, flameY, flameX, flameY - 4);
    ctx.fill();

    // Flame bright core
    ctx.fillStyle = 'rgba(255, 230, 100, 0.7)';
    ctx.beginPath();
    ctx.arc(flameX, flameY, 1.3, 0, Math.PI * 2);
    ctx.fill();
  }
}

/**
 * Ritual Circle — Large glowing arcane sigil inscribed on the floor.
 * Concentric rings with rune marks, pulsing energy lines, and
 * a central pentagram shape. Spans multiple tiles for imposing scale.
 * Theme affinity: Boss rooms, Cursed Shrine, Shrine.
 */
function drawProp_ritual_circle(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size / 2;
  const h = cellHash;
  const glowColor = palette.accent;
  const outerR = size * 1.2;

  // Large ambient glow (ground-level radial)
  const ambientGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, outerR * 1.3);
  ambientGrad.addColorStop(0, hexAlpha(glowColor, 0.12));
  ambientGrad.addColorStop(0.5, hexAlpha(glowColor, 0.05));
  ambientGrad.addColorStop(1, hexAlpha(glowColor, 0));
  ctx.fillStyle = ambientGrad;
  ctx.beginPath();
  ctx.arc(cx, cy, outerR * 1.3, 0, Math.PI * 2);
  ctx.fill();

  // Outer ring (thick, slightly transparent)
  ctx.strokeStyle = hexAlpha(glowColor, 0.3);
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.arc(cx, cy, outerR, 0, Math.PI * 2);
  ctx.stroke();

  // Middle ring
  const midR = outerR * 0.78;
  ctx.strokeStyle = hexAlpha(glowColor, 0.2);
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(cx, cy, midR, 0, Math.PI * 2);
  ctx.stroke();

  // Inner ring
  const innerR = outerR * 0.55;
  ctx.strokeStyle = hexAlpha(glowColor, 0.25);
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(cx, cy, innerR, 0, Math.PI * 2);
  ctx.stroke();

  // Pentagram/star shape (5-pointed, connecting every other vertex)
  ctx.strokeStyle = hexAlpha(glowColor, 0.35);
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  for (let i = 0; i < 5; i++) {
    const angle = (i * 2 % 5) / 5 * Math.PI * 2 - Math.PI / 2;
    const nextAngle = ((i * 2 + 2) % 5) / 5 * Math.PI * 2 - Math.PI / 2;
    const px1 = cx + Math.cos(angle) * innerR;
    const py1 = cy + Math.sin(angle) * innerR;
    const px2 = cx + Math.cos(nextAngle) * innerR;
    const py2 = cy + Math.sin(nextAngle) * innerR;
    ctx.moveTo(px1, py1);
    ctx.lineTo(px2, py2);
  }
  ctx.stroke();

  // Rune marks between outer and middle rings (8-12 larger glyphs)
  const runeCount = 8 + Math.floor(h(seed, 0, 220) * 5);
  const runeR = (outerR + midR) / 2;
  for (let i = 0; i < runeCount; i++) {
    const angle = (i / runeCount) * Math.PI * 2 + h(seed, i, 221) * 0.15;
    const rx = cx + Math.cos(angle) * runeR;
    const ry = cy + Math.sin(angle) * runeR;

    // Each rune is a small glyph: scaled up for visibility
    ctx.strokeStyle = hexAlpha(glowColor, 0.3 + h(seed, i, 222) * 0.15);
    ctx.lineWidth = 0.9;

    const runeType = Math.floor(h(seed, i, 223) * 3);
    if (runeType === 0) {
      // Vertical line + horizontal tick
      ctx.beginPath();
      ctx.moveTo(rx, ry - 3.5);
      ctx.lineTo(rx, ry + 3.5);
      ctx.moveTo(rx - 2.5, ry);
      ctx.lineTo(rx + 2.5, ry);
      ctx.stroke();
    } else if (runeType === 1) {
      // Small diamond
      ctx.beginPath();
      ctx.moveTo(rx, ry - 3.5);
      ctx.lineTo(rx + 2.5, ry);
      ctx.lineTo(rx, ry + 3.5);
      ctx.lineTo(rx - 2.5, ry);
      ctx.closePath();
      ctx.stroke();
    } else {
      // Dot with halo
      ctx.fillStyle = hexAlpha(glowColor, 0.4);
      ctx.beginPath();
      ctx.arc(rx, ry, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = hexAlpha(glowColor, 0.1);
      ctx.beginPath();
      ctx.arc(rx, ry, 5, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Center eye / focal point
  ctx.fillStyle = hexAlpha(glowColor, 0.45);
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.06, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = hexAlpha(palette.highlight, 0.6);
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.03, 0, Math.PI * 2);
  ctx.fill();

  // Pulsing energy wisps (3-4 radial streaks from center to outer ring)
  for (let w = 0; w < 4; w++) {
    const wAngle = h(seed, w, 224) * Math.PI * 2;
    const wR1 = innerR * 0.3;
    const wR2 = outerR * 0.95;
    ctx.strokeStyle = hexAlpha(glowColor, 0.08 + h(seed, w, 225) * 0.06);
    ctx.lineWidth = 0.6;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(wAngle) * wR1, cy + Math.sin(wAngle) * wR1);
    ctx.lineTo(cx + Math.cos(wAngle) * wR2, cy + Math.sin(wAngle) * wR2);
    ctx.stroke();
  }
}

/**
 * Iron Maiden — Half-open hinged iron torture sarcophagus.
 * Front-facing view with open door showing interior spikes,
 * heavy riveted iron construction, and menacing silhouette.
 * Theme affinity: Prison, Iron Depths, Catacombs.
 */
function drawProp_iron_maiden(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const h = cellHash;
  const metalColor = palette.metal || palette.secondary;
  const darkMetal = shiftColor(metalColor, -10);

  const bodyX = cx - size * 0.14;
  const bodyY = y + size * 0.08;
  const bodyW = size * 0.28;
  const bodyH = size * 0.72;

  // Ground shadow
  ctx.fillStyle = 'rgba(0,0,0,0.2)';
  ctx.beginPath();
  ctx.ellipse(cx, y + size * 0.85, size * 0.22, size * 0.06, 0, 0, Math.PI * 2);
  ctx.fill();

  // Open door (angled rectangle to the right, perspective)
  const doorW = size * 0.18;
  ctx.fillStyle = shiftColor(metalColor, -3);
  ctx.beginPath();
  ctx.moveTo(bodyX + bodyW, bodyY + bodyH * 0.05);
  ctx.lineTo(bodyX + bodyW + doorW, bodyY + bodyH * 0.12);
  ctx.lineTo(bodyX + bodyW + doorW, bodyY + bodyH * 0.88);
  ctx.lineTo(bodyX + bodyW, bodyY + bodyH * 0.95);
  ctx.closePath();
  ctx.fill();

  // Spikes inside door (3-4 small triangles)
  const spikeCount = 3 + Math.floor(h(seed, 0, 230) * 2);
  for (let s = 0; s < spikeCount; s++) {
    const sy = bodyY + bodyH * 0.2 + (s / spikeCount) * bodyH * 0.55;
    const sx = bodyX + bodyW + doorW * 0.3;
    ctx.fillStyle = shiftColor(metalColor, 15);
    ctx.beginPath();
    ctx.moveTo(sx - 1, sy - 1.5);
    ctx.lineTo(sx + 3, sy);
    ctx.lineTo(sx - 1, sy + 1.5);
    ctx.closePath();
    ctx.fill();
  }

  // Door border
  ctx.strokeStyle = shiftColor(metalColor, -8);
  ctx.lineWidth = 0.6;
  ctx.beginPath();
  ctx.moveTo(bodyX + bodyW, bodyY + bodyH * 0.05);
  ctx.lineTo(bodyX + bodyW + doorW, bodyY + bodyH * 0.12);
  ctx.lineTo(bodyX + bodyW + doorW, bodyY + bodyH * 0.88);
  ctx.lineTo(bodyX + bodyW, bodyY + bodyH * 0.95);
  ctx.closePath();
  ctx.stroke();

  // Interior cavity (visible dark gap between body and door)
  ctx.fillStyle = 'rgba(0,0,0,0.35)';
  ctx.fillRect(bodyX + bodyW - 2, bodyY + bodyH * 0.08, 4, bodyH * 0.84);

  // Interior spikes (points facing inward)
  for (let s = 0; s < 4; s++) {
    const sy = bodyY + bodyH * 0.15 + s * bodyH * 0.18;
    ctx.fillStyle = shiftColor(metalColor, 12);
    ctx.beginPath();
    ctx.moveTo(bodyX + bodyW + 1, sy);
    ctx.lineTo(bodyX + bodyW - 3, sy + 1);
    ctx.lineTo(bodyX + bodyW + 1, sy + 2);
    ctx.closePath();
    ctx.fill();
  }

  // Main body (front-facing iron case, rounded top)
  ctx.fillStyle = metalColor;
  ctx.beginPath();
  ctx.moveTo(bodyX, bodyY + bodyH);
  ctx.lineTo(bodyX, bodyY + bodyH * 0.15);
  // Rounded top (arch)
  ctx.quadraticCurveTo(bodyX, bodyY, cx, bodyY);
  ctx.quadraticCurveTo(bodyX + bodyW, bodyY, bodyX + bodyW, bodyY + bodyH * 0.15);
  ctx.lineTo(bodyX + bodyW, bodyY + bodyH);
  ctx.closePath();
  ctx.fill();

  // Body border
  ctx.strokeStyle = darkMetal;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(bodyX, bodyY + bodyH);
  ctx.lineTo(bodyX, bodyY + bodyH * 0.15);
  ctx.quadraticCurveTo(bodyX, bodyY, cx, bodyY);
  ctx.quadraticCurveTo(bodyX + bodyW, bodyY, bodyX + bodyW, bodyY + bodyH * 0.15);
  ctx.lineTo(bodyX + bodyW, bodyY + bodyH);
  ctx.stroke();

  // Face slit (horizontal eye slot)
  ctx.fillStyle = 'rgba(0,0,0,0.5)';
  ctx.fillRect(bodyX + bodyW * 0.2, bodyY + bodyH * 0.2, bodyW * 0.6, size * 0.02);

  // Rivets (6-8 small dots along edges)
  ctx.fillStyle = shiftColor(metalColor, 14);
  const rivetPositions = [
    [bodyX + 3, bodyY + bodyH * 0.25],
    [bodyX + 3, bodyY + bodyH * 0.45],
    [bodyX + 3, bodyY + bodyH * 0.65],
    [bodyX + 3, bodyY + bodyH * 0.85],
    [bodyX + bodyW - 3, bodyY + bodyH * 0.25],
    [bodyX + bodyW - 3, bodyY + bodyH * 0.45],
    [bodyX + bodyW - 3, bodyY + bodyH * 0.65],
    [bodyX + bodyW - 3, bodyY + bodyH * 0.85],
  ];
  for (const [rx, ry] of rivetPositions) {
    ctx.beginPath();
    ctx.arc(rx, ry, 1, 0, Math.PI * 2);
    ctx.fill();
  }

  // Hinge pins (2 circles where door meets body)
  ctx.fillStyle = shiftColor(metalColor, 10);
  ctx.beginPath();
  ctx.arc(bodyX + bodyW, bodyY + bodyH * 0.2, 1.5, 0, Math.PI * 2);
  ctx.arc(bodyX + bodyW, bodyY + bodyH * 0.75, 1.5, 0, Math.PI * 2);
  ctx.fill();

  // Rust staining (subtle brown patches)
  if (h(seed, 0, 231) > 0.35) {
    ctx.fillStyle = 'rgba(120, 60, 20, 0.1)';
    ctx.beginPath();
    ctx.arc(bodyX + bodyW * 0.4, bodyY + bodyH * 0.55, size * 0.04, 0, Math.PI * 2);
    ctx.fill();
  }
}

/**
 * Tombstone — Weathered gravestone with engraved cross,
 * deterministic tilt, cracks, and base-level moss/lichen.
 * Top shape varies: rounded arch, peaked, or flat.
 * Theme affinity: Catacombs, Ossuary, Cursed Shrine.
 */
function drawProp_tombstone(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const baseY = y + size * 0.82;
  const h = cellHash;
  const stoneColor = lerpColor(palette.secondary, '#8a8580', 0.25);

  // Slight tilt (deterministic rotation)
  const tilt = (h(seed, 0, 240) - 0.5) * 0.12; // -0.06 to +0.06 radians
  ctx.save();
  ctx.translate(cx, baseY);
  ctx.rotate(tilt);

  const stoneW = size * 0.24;
  const stoneH = size * 0.42;
  const stoneX = -stoneW / 2;
  const stoneY = -stoneH;

  // Ground shadow (offset for tilt)
  ctx.fillStyle = 'rgba(0,0,0,0.15)';
  ctx.beginPath();
  ctx.ellipse(2, 3, stoneW * 0.7, size * 0.04, 0, 0, Math.PI * 2);
  ctx.fill();

  // Ground mound (small dirt rise at base)
  ctx.fillStyle = shiftColor(palette.floor || palette.primary, -3);
  ctx.beginPath();
  ctx.ellipse(0, 0, stoneW * 0.6, size * 0.035, 0, 0, Math.PI * 2);
  ctx.fill();

  // Tombstone body — shape varies
  const shapeType = Math.floor(h(seed, 0, 241) * 3);
  ctx.fillStyle = stoneColor;
  ctx.beginPath();

  if (shapeType === 0) {
    // Rounded arch top
    ctx.moveTo(stoneX, 0);
    ctx.lineTo(stoneX, stoneY + stoneW / 2);
    ctx.arc(0, stoneY + stoneW / 2, stoneW / 2, Math.PI, 0);
    ctx.lineTo(stoneX + stoneW, 0);
    ctx.closePath();
  } else if (shapeType === 1) {
    // Peaked/gothic top
    ctx.moveTo(stoneX, 0);
    ctx.lineTo(stoneX, stoneY + stoneH * 0.25);
    ctx.lineTo(0, stoneY - stoneH * 0.05);
    ctx.lineTo(stoneX + stoneW, stoneY + stoneH * 0.25);
    ctx.lineTo(stoneX + stoneW, 0);
    ctx.closePath();
  } else {
    // Flat-topped rectangle with chamfered corners
    ctx.moveTo(stoneX, 0);
    ctx.lineTo(stoneX, stoneY + 3);
    ctx.lineTo(stoneX + 3, stoneY);
    ctx.lineTo(stoneX + stoneW - 3, stoneY);
    ctx.lineTo(stoneX + stoneW, stoneY + 3);
    ctx.lineTo(stoneX + stoneW, 0);
    ctx.closePath();
  }
  ctx.fill();

  // Stone border
  ctx.strokeStyle = shiftColor(stoneColor, -10);
  ctx.lineWidth = 0.7;
  ctx.stroke();

  // Light edge (catch-light on left side)
  ctx.strokeStyle = hexAlpha(palette.highlight, 0.1);
  ctx.lineWidth = 0.5;
  ctx.beginPath();
  ctx.moveTo(stoneX + 1, 0);
  ctx.lineTo(stoneX + 1, stoneY + stoneH * 0.3);
  ctx.stroke();

  // Engraved cross (center of tombstone)
  const crossCY = stoneY + stoneH * 0.35;
  ctx.strokeStyle = shiftColor(stoneColor, -8);
  ctx.lineWidth = 1;
  ctx.beginPath();
  // Vertical bar
  ctx.moveTo(0, crossCY - stoneH * 0.15);
  ctx.lineTo(0, crossCY + stoneH * 0.15);
  // Horizontal bar
  ctx.moveTo(-stoneW * 0.2, crossCY - stoneH * 0.04);
  ctx.lineTo(stoneW * 0.2, crossCY - stoneH * 0.04);
  ctx.stroke();

  // Crack lines (1-2 hairline fractures)
  if (h(seed, 0, 242) > 0.3) {
    ctx.strokeStyle = shiftColor(stoneColor, -14);
    ctx.lineWidth = 0.4;
    ctx.beginPath();
    const crackStartY = stoneY + stoneH * (0.2 + h(seed, 0, 243) * 0.4);
    ctx.moveTo(-stoneW * 0.1, crackStartY);
    ctx.lineTo(stoneW * 0.05, crackStartY + stoneH * 0.2);
    ctx.lineTo(-stoneW * 0.05, crackStartY + stoneH * 0.35);
    ctx.stroke();
  }
  if (h(seed, 1, 242) > 0.6) {
    ctx.strokeStyle = shiftColor(stoneColor, -12);
    ctx.lineWidth = 0.3;
    ctx.beginPath();
    ctx.moveTo(stoneW * 0.15, stoneY + stoneH * 0.5);
    ctx.lineTo(stoneW * 0.08, stoneY + stoneH * 0.7);
    ctx.stroke();
  }

  // Moss / lichen patches at base
  for (let m = 0; m < 2; m++) {
    if (h(seed, m, 244) > 0.5) continue;
    const mx = (h(seed, m, 245) - 0.5) * stoneW * 0.6;
    const my = -stoneH * 0.05 + h(seed, m, 246) * stoneH * 0.1;
    ctx.fillStyle = 'rgba(45, 75, 35, 0.18)';
    ctx.beginPath();
    ctx.arc(mx, my, size * 0.02 + h(seed, m, 247) * size * 0.01, 0, Math.PI * 2);
    ctx.fill();
  }

  // Weathering texture (subtle noise stipple)
  ctx.fillStyle = shiftColor(stoneColor, -5);
  for (let d = 0; d < 6; d++) {
    const dx = stoneX + h(seed, d, 248) * stoneW;
    const dy = stoneY + h(seed, d, 249) * stoneH * 0.8 + stoneH * 0.1;
    ctx.fillRect(dx, dy, 1, 1);
  }

  ctx.restore();
}

// ═══════════════════════════════════════════════════════════
//  NEW PROPS (Variety Expansion Batch)
// ═══════════════════════════════════════════════════════════

/**
 * Lectern — Open book on a wooden stand with angled reading
 * surface. Thin pedestal, two visible pages, faint text lines.
 * Theme affinity: Cathedral, Silent Vault, Library, Shrine.
 */
function drawProp_lectern(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const baseY = y + size * 0.82;
  const woodColor = palette.furniture || palette.secondary;

  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.15)';
  ctx.beginPath();
  ctx.ellipse(cx + 1, baseY + 2, size * 0.1, size * 0.04, 0, 0, Math.PI * 2);
  ctx.fill();

  // Pedestal
  ctx.strokeStyle = shiftColor(woodColor, 3);
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(cx, baseY);
  ctx.lineTo(cx, y + size * 0.4);
  ctx.stroke();

  // Base foot
  ctx.fillStyle = shiftColor(woodColor, -2);
  ctx.fillRect(cx - size * 0.08, baseY - 2, size * 0.16, 3);

  // Book rest (angled surface)
  const restTop = y + size * 0.25;
  const restBot = y + size * 0.42;
  const restW = size * 0.3;
  ctx.fillStyle = shiftColor(woodColor, 5);
  ctx.beginPath();
  ctx.moveTo(cx - restW / 2, restBot);
  ctx.lineTo(cx - restW / 2 - 2, restTop + 4);
  ctx.lineTo(cx + restW / 2 + 2, restTop);
  ctx.lineTo(cx + restW / 2, restBot);
  ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = shiftColor(woodColor, -8);
  ctx.lineWidth = 0.6;
  ctx.stroke();

  // Open book — two pages
  const bookY = restTop + 2;
  const pageW = restW * 0.4;
  ctx.fillStyle = lerpColor('#d8d0c0', palette.secondary, 0.15);
  ctx.fillRect(cx - pageW - 1, bookY, pageW, size * 0.12);
  ctx.fillRect(cx + 1, bookY, pageW, size * 0.12);

  // Spine line
  ctx.strokeStyle = shiftColor(woodColor, -5);
  ctx.lineWidth = 0.8;
  ctx.beginPath();
  ctx.moveTo(cx, bookY - 1);
  ctx.lineTo(cx, bookY + size * 0.13);
  ctx.stroke();

  // Text lines on pages
  ctx.strokeStyle = 'rgba(0,0,0,0.15)';
  ctx.lineWidth = 0.4;
  for (let i = 0; i < 3; i++) {
    const ly = bookY + 2 + i * 3;
    ctx.beginPath();
    ctx.moveTo(cx - pageW + 2, ly);
    ctx.lineTo(cx - 3, ly);
    ctx.moveTo(cx + 3, ly);
    ctx.lineTo(cx + pageW - 2, ly);
    ctx.stroke();
  }
}

/**
 * Desk — Small writing desk with quill, papers, and ink pot.
 * Rectangular table surface on short legs. Scholarly feel.
 * Theme affinity: Silent Vault, Cathedral, Library.
 */
function drawProp_desk(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const woodColor = palette.furniture || palette.secondary;
  const dw = size * 0.6, dh = size * 0.4;
  const dx = cx - dw / 2, dy = y + size * 0.35;

  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.15)';
  ctx.fillRect(dx + 2, dy + dh + 1, dw, 3);

  // Table surface
  ctx.fillStyle = shiftColor(woodColor, 5);
  ctx.fillRect(dx, dy, dw, dh);

  // Border
  ctx.strokeStyle = shiftColor(woodColor, -8);
  ctx.lineWidth = 0.8;
  ctx.strokeRect(dx, dy, dw, dh);

  // Front edge shadow (thickness)
  ctx.fillStyle = shiftColor(woodColor, -5);
  ctx.fillRect(dx, dy + dh, dw, 3);

  // Legs
  ctx.strokeStyle = shiftColor(woodColor, -3);
  ctx.lineWidth = 1.5;
  const legH = size * 0.18;
  ctx.beginPath();
  ctx.moveTo(dx + 2, dy + dh + 3);
  ctx.lineTo(dx + 2, dy + dh + 3 + legH);
  ctx.moveTo(dx + dw - 2, dy + dh + 3);
  ctx.lineTo(dx + dw - 2, dy + dh + 3 + legH);
  ctx.stroke();

  // Paper on surface
  ctx.fillStyle = lerpColor('#d8d0c0', palette.secondary, 0.1);
  ctx.fillRect(dx + dw * 0.15, dy + dh * 0.15, dw * 0.35, dh * 0.6);

  // Quill
  ctx.strokeStyle = shiftColor(palette.metal || palette.secondary, 8);
  ctx.lineWidth = 0.8;
  ctx.beginPath();
  ctx.moveTo(dx + dw * 0.65, dy + dh * 0.2);
  ctx.lineTo(dx + dw * 0.8, dy + dh * 0.7);
  ctx.stroke();

  // Ink pot
  ctx.fillStyle = 'rgba(10, 10, 20, 0.6)';
  ctx.beginPath();
  ctx.arc(dx + dw * 0.75, dy + dh * 0.3, size * 0.02, 0, Math.PI * 2);
  ctx.fill();
}

/**
 * Crate — Nailed wooden supply crate with X bracing and
 * plank lines. Complements barrels in storage areas.
 * Theme affinity: Cellar, Iron Depths, Armory, Loot rooms.
 */
function drawProp_crate(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2, cy = y + size / 2;
  const woodColor = palette.furniture || palette.secondary;
  const crateS = size * 0.14;

  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.15)';
  ctx.beginPath();
  ctx.ellipse(cx + 1, cy + crateS + 2, crateS * 1.5, size * 0.04, 0, 0, Math.PI * 2);
  ctx.fill();

  // Crate body
  ctx.fillStyle = lerpColor(woodColor, '#5C3310', 0.4);
  ctx.fillRect(cx - crateS, cy - crateS, crateS * 2, crateS * 2);

  // Border
  ctx.strokeStyle = shiftColor(woodColor, -10);
  ctx.lineWidth = 0.8;
  ctx.strokeRect(cx - crateS, cy - crateS, crateS * 2, crateS * 2);

  // Plank lines
  ctx.strokeStyle = shiftColor(woodColor, -6);
  ctx.lineWidth = 0.5;
  const third = crateS * 2 / 3;
  ctx.beginPath();
  ctx.moveTo(cx - crateS, cy - crateS + third);
  ctx.lineTo(cx + crateS, cy - crateS + third);
  ctx.moveTo(cx - crateS, cy - crateS + third * 2);
  ctx.lineTo(cx + crateS, cy - crateS + third * 2);
  ctx.stroke();

  // X bracing
  ctx.strokeStyle = shiftColor(palette.metal || palette.secondary, 5);
  ctx.lineWidth = 0.7;
  ctx.beginPath();
  ctx.moveTo(cx - crateS + 2, cy - crateS + 2);
  ctx.lineTo(cx + crateS - 2, cy + crateS - 2);
  ctx.moveTo(cx + crateS - 2, cy - crateS + 2);
  ctx.lineTo(cx - crateS + 2, cy + crateS - 2);
  ctx.stroke();

  // Corner nails
  ctx.fillStyle = shiftColor(palette.metal || palette.secondary, 10);
  for (const [nx, ny] of [
    [cx - crateS + 3, cy - crateS + 3], [cx + crateS - 3, cy - crateS + 3],
    [cx - crateS + 3, cy + crateS - 3], [cx + crateS - 3, cy + crateS - 3],
  ]) {
    ctx.beginPath();
    ctx.arc(nx, ny, 0.8, 0, Math.PI * 2);
    ctx.fill();
  }

  // Top highlight
  ctx.fillStyle = shiftColor(woodColor, 4);
  ctx.fillRect(cx - crateS + 1, cy - crateS + 1, crateS * 2 - 2, 1);
}

/**
 * Bone Pile — Scattered long bones, ribcage fragments, and
 * femur shapes. Less "skull tower", more "aftermath".
 * Theme affinity: Catacombs, Ossuary, Torture, Graveyard.
 */
function drawProp_bone_pile(ctx, x, y, size, seed, palette) {
  const h = cellHash;
  const cx = x + size / 2;
  const baseY = y + size * 0.65;
  const boneColor = lerpColor(palette.secondary, '#d8d0c0', 0.35);

  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.1)';
  ctx.beginPath();
  ctx.ellipse(cx, baseY + 3, size * 0.22, size * 0.05, 0, 0, Math.PI * 2);
  ctx.fill();

  // Scattered long bones (4-6 angled lines with knob ends)
  const count = 4 + Math.floor(h(seed, 0, 250) * 3);
  for (let i = 0; i < count; i++) {
    const bx = cx + (h(seed, i, 251) - 0.5) * size * 0.35;
    const by = baseY - size * 0.05 + (h(seed, i, 252) - 0.5) * size * 0.15;
    const angle = (h(seed, i, 253) - 0.5) * Math.PI * 0.6;
    const boneLen = size * 0.12 + h(seed, i, 254) * size * 0.08;

    ctx.save();
    ctx.translate(bx, by);
    ctx.rotate(angle);

    // Bone shaft
    ctx.strokeStyle = shiftColor(boneColor, Math.floor((h(seed, i, 255) - 0.5) * 10));
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(-boneLen / 2, 0);
    ctx.lineTo(boneLen / 2, 0);
    ctx.stroke();

    // Bone knobs at ends
    ctx.fillStyle = shiftColor(boneColor, 3);
    ctx.beginPath();
    ctx.arc(-boneLen / 2, 0, 1.5, 0, Math.PI * 2);
    ctx.arc(boneLen / 2, 0, 1.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }

  // Rib curve
  if (h(seed, 0, 256) > 0.3) {
    const ribX = cx + (h(seed, 0, 257) - 0.5) * size * 0.15;
    const ribY = baseY - size * 0.08;
    ctx.strokeStyle = shiftColor(boneColor, -3);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(ribX, ribY, size * 0.08, Math.PI * 0.2, Math.PI * 0.8);
    ctx.stroke();
  }
}

/**
 * Hanging Lantern — Ceiling-hung iron lantern with warm glow.
 * Chain suspension, rectangular frame, glass panes, inner flame.
 * Different silhouette from sconces and braziers.
 * Theme affinity: Cathedral, Silent Vault, Library, Shrine.
 */
function drawProp_hanging_lantern(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const metalColor = palette.metal || palette.secondary;
  const lanternTop = y + size * 0.25;
  const lanternBot = y + size * 0.52;
  const lanternW = size * 0.18;
  const lanternMid = (lanternTop + lanternBot) / 2;

  // Warm glow
  const grad = ctx.createRadialGradient(cx, lanternMid, 1, cx, lanternMid, size * 0.38);
  grad.addColorStop(0, 'rgba(255, 190, 80, 0.14)');
  grad.addColorStop(0.5, 'rgba(255, 140, 40, 0.05)');
  grad.addColorStop(1, 'rgba(255, 100, 20, 0)');
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(cx, lanternMid, size * 0.38, 0, Math.PI * 2);
  ctx.fill();

  // Chain from ceiling
  ctx.strokeStyle = shiftColor(metalColor, 5);
  ctx.lineWidth = 0.8;
  for (let ly = y; ly < lanternTop; ly += 3) {
    const off = ((ly / 3) | 0) % 2 === 0 ? -0.3 : 0.3;
    ctx.beginPath();
    ctx.moveTo(cx + off, ly);
    ctx.lineTo(cx + off, Math.min(ly + 2, lanternTop));
    ctx.stroke();
  }

  // Lantern frame
  ctx.strokeStyle = shiftColor(metalColor, 3);
  ctx.lineWidth = 1;
  ctx.strokeRect(cx - lanternW / 2, lanternTop, lanternW, lanternBot - lanternTop);

  // Top cap
  ctx.fillStyle = shiftColor(metalColor, 6);
  ctx.beginPath();
  ctx.moveTo(cx - lanternW / 2 - 2, lanternTop);
  ctx.lineTo(cx + lanternW / 2 + 2, lanternTop);
  ctx.lineTo(cx + lanternW * 0.2, lanternTop - 3);
  ctx.lineTo(cx - lanternW * 0.2, lanternTop - 3);
  ctx.closePath();
  ctx.fill();

  // Bottom cap
  ctx.fillStyle = shiftColor(metalColor, 4);
  ctx.fillRect(cx - lanternW / 2 - 1, lanternBot, lanternW + 2, 2);

  // Glass panes
  ctx.fillStyle = hexAlpha(palette.accent, 0.12);
  ctx.fillRect(cx - lanternW / 2 + 1, lanternTop + 1, lanternW - 2, lanternBot - lanternTop - 2);

  // Inner flame
  ctx.fillStyle = 'rgba(255, 200, 60, 0.6)';
  ctx.beginPath();
  ctx.arc(cx, lanternMid, 2, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = 'rgba(255, 240, 120, 0.75)';
  ctx.beginPath();
  ctx.arc(cx, lanternMid, 1, 0, Math.PI * 2);
  ctx.fill();

  // Center vertical frame bar
  ctx.strokeStyle = shiftColor(metalColor, 0);
  ctx.lineWidth = 0.5;
  ctx.beginPath();
  ctx.moveTo(cx, lanternTop);
  ctx.lineTo(cx, lanternBot);
  ctx.stroke();

  // Bottom shadow
  ctx.fillStyle = 'rgba(0,0,0,0.06)';
  ctx.beginPath();
  ctx.ellipse(cx, lanternBot + size * 0.12, lanternW * 0.6, 2, 0, 0, Math.PI * 2);
  ctx.fill();
}

// ═══════════════════════════════════════════════════════════
//  OVERLAY DECORATION DRAW FUNCTIONS
//  Single-tile preview versions of archetype overlay elements
// ═══════════════════════════════════════════════════════════

/**
 * Corner Pillar — Boss room corner column with highlight ring.
 */
function drawProp_corner_pillar(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size / 2;
  const r = size * 0.28;
  const pillarColor = lerpColor(palette.metal || palette.secondary, palette.highlight, 0.3);

  // Shadow
  ctx.fillStyle = shiftColor(palette.primary, -10);
  ctx.beginPath();
  ctx.arc(cx + 1, cy + 1, r + 1, 0, Math.PI * 2);
  ctx.fill();

  // Pillar body
  ctx.fillStyle = pillarColor;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fill();

  // Highlight ring
  ctx.strokeStyle = hexAlpha(palette.highlight, 0.35);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(cx, cy, r - 2, 0, Math.PI * 2);
  ctx.stroke();
}

/**
 * Floor Sigil — Geometric circle + diamond pattern for boss rooms.
 */
function drawProp_floor_sigil(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size / 2;
  const r = size * 0.4;

  // Outer circle
  ctx.strokeStyle = hexAlpha(palette.accent, 0.25);
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.stroke();

  // Inner diamond
  const dr = r * 0.65;
  ctx.strokeStyle = hexAlpha(palette.highlight, 0.20);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(cx, cy - dr);
  ctx.lineTo(cx + dr, cy);
  ctx.lineTo(cx, cy + dr);
  ctx.lineTo(cx - dr, cy);
  ctx.closePath();
  ctx.stroke();

  // Center dot
  ctx.fillStyle = hexAlpha(palette.highlight, 0.30);
  ctx.beginPath();
  ctx.arc(cx, cy, 2.5, 0, Math.PI * 2);
  ctx.fill();
}

/**
 * Wall Torch — Enemy room wall-mounted torch with glow.
 */
function drawProp_wall_torch(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;

  // Glow radius
  ctx.fillStyle = hexAlpha(palette.highlight, 0.06);
  ctx.beginPath();
  ctx.arc(cx, y + size / 2, size * 0.4, 0, Math.PI * 2);
  ctx.fill();

  // Bracket on wall
  ctx.fillStyle = shiftColor(palette.metal || palette.secondary, 10);
  ctx.fillRect(cx - 2, y + size * 0.3, 4, size * 0.4);

  // Flame outer
  ctx.fillStyle = hexAlpha(palette.accent, 0.4);
  ctx.beginPath();
  ctx.arc(cx, y + size * 0.28, 5, 0, Math.PI * 2);
  ctx.fill();

  // Flame core
  ctx.fillStyle = hexAlpha(palette.highlight, 0.7);
  ctx.beginPath();
  ctx.arc(cx, y + size * 0.28, 3, 0, Math.PI * 2);
  ctx.fill();
}

/**
 * Wall Alcove — Loot room recessed niche in wall.
 */
function drawProp_wall_alcove(ctx, x, y, size, seed, palette) {
  const alcoveColor = shiftColor(palette.primary, -5);
  const alcoveHighlight = shiftColor(palette.secondary, 8);

  ctx.fillStyle = alcoveColor;
  ctx.fillRect(x + size * 0.2, y + size * 0.15, size * 0.6, size * 0.7);
  ctx.strokeStyle = alcoveHighlight;
  ctx.lineWidth = 0.5;
  ctx.strokeRect(x + size * 0.2, y + size * 0.15, size * 0.6, size * 0.7);
}

/**
 * Corner Ornament — Loot room corner filigree L-shape with dot.
 */
function drawProp_corner_ornament(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size / 2;

  ctx.strokeStyle = hexAlpha(palette.highlight, 0.30);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(cx, cy + 8);
  ctx.lineTo(cx, cy);
  ctx.lineTo(cx + 8, cy);
  ctx.stroke();

  ctx.fillStyle = hexAlpha(palette.highlight, 0.25);
  ctx.beginPath();
  ctx.arc(cx, cy, 2, 0, Math.PI * 2);
  ctx.fill();
}

/**
 * Arrival Circle — Spawn room center mark with glow.
 */
function drawProp_arrival_circle(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size / 2;

  // Outer glow
  ctx.fillStyle = hexAlpha(palette.highlight, 0.04);
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.45, 0, Math.PI * 2);
  ctx.fill();

  // Circle mark
  ctx.strokeStyle = hexAlpha(palette.highlight, 0.18);
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.3, 0, Math.PI * 2);
  ctx.stroke();

  // Inner dot
  ctx.fillStyle = hexAlpha(palette.highlight, 0.15);
  ctx.beginPath();
  ctx.arc(cx, cy, 2.5, 0, Math.PI * 2);
  ctx.fill();
}

/**
 * Archway — Spawn room flanking archway columns with curved top.
 */
function drawProp_archway(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const colW = 6;
  const colH = size * 0.7;

  // Left column
  ctx.fillStyle = lerpColor(palette.secondary, palette.highlight, 0.25);
  ctx.fillRect(cx - size * 0.3, y + size * 0.2, colW, colH);
  // Right column
  ctx.fillRect(cx + size * 0.3 - colW, y + size * 0.2, colW, colH);

  // Arch top
  ctx.strokeStyle = hexAlpha(palette.highlight, 0.18);
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(cx - size * 0.3, y + size * 0.25);
  ctx.quadraticCurveTo(cx, y + size * 0.05, cx + size * 0.3, y + size * 0.25);
  ctx.stroke();
}

/**
 * Corner Rubble — Empty room corner debris cluster.
 */
function drawProp_corner_rubble(ctx, x, y, size, seed, palette) {
  const rubbleColor = shiftColor(palette.secondary, -8);

  ctx.fillStyle = rubbleColor;
  ctx.fillRect(x + size * 0.15, y + size * 0.55, 10, 6);
  ctx.fillRect(x + size * 0.3, y + size * 0.45, 8, 5);
  ctx.fillRect(x + size * 0.1, y + size * 0.6, 6, 4);

  // Shadow underneath
  ctx.fillStyle = 'rgba(0,0,0,0.15)';
  ctx.fillRect(x + size * 0.12, y + size * 0.68, 14, 2);
}

/**
 * Stair Descent — Concentric border rings suggesting depth.
 */
function drawProp_stair_descent(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size / 2;

  // Gradient darker toward center
  const grad = ctx.createRadialGradient(cx, cy, size * 0.05, cx, cy, size * 0.45);
  grad.addColorStop(0, 'rgba(0,0,0,0.20)');
  grad.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.45, 0, Math.PI * 2);
  ctx.fill();

  // Concentric rings
  ctx.strokeStyle = hexAlpha(palette.accent, 0.15);
  ctx.lineWidth = 0.8;
  for (let r = 1; r <= 3; r++) {
    ctx.beginPath();
    ctx.arc(cx, cy, size * 0.1 * r, 0, Math.PI * 2);
    ctx.stroke();
  }
}

/**
 * Wall Banner — Shrine room hanging banner with tattered edge.
 */
function drawProp_wall_banner(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const bw = size * 0.3;
  const bh = size * 0.6;
  const by = y + size * 0.1;

  // Rod
  ctx.fillStyle = shiftColor(palette.metal || palette.secondary, 5);
  ctx.fillRect(cx - bw / 2 - 2, by, bw + 4, 2);

  // Fabric body
  ctx.fillStyle = hexAlpha(palette.accent, 0.5);
  ctx.fillRect(cx - bw / 2, by + 2, bw, bh - 8);

  // Tattered bottom
  ctx.beginPath();
  ctx.moveTo(cx - bw / 2, by + bh - 8);
  const teeth = 3;
  const toothW = bw / teeth;
  for (let t = 0; t < teeth; t++) {
    ctx.lineTo(cx - bw / 2 + t * toothW + toothW / 2, by + bh);
    ctx.lineTo(cx - bw / 2 + (t + 1) * toothW, by + bh - 8);
  }
  ctx.closePath();
  ctx.fill();
}

/**
 * Wall Chains — Prison room dangling chain links on wall.
 */
function drawProp_wall_chains(ctx, x, y, size, seed, palette) {
  const chainColor = shiftColor(palette.metal || palette.secondary, 5);
  const h = cellHash;

  for (let i = 0; i < 3; i++) {
    const cx = x + size * 0.2 + (i / 2) * size * 0.6;
    const chainLen = size * 0.5 + h(seed, i, 81) * size * 0.3;
    ctx.strokeStyle = chainColor;
    ctx.lineWidth = 1;
    for (let ly = 0; ly < chainLen; ly += 4) {
      const linkX = cx + ((ly / 4) % 2 === 0 ? -0.5 : 0.5);
      ctx.beginPath();
      ctx.moveTo(linkX, y + size * 0.1 + ly);
      ctx.lineTo(linkX, y + size * 0.1 + Math.min(ly + 3, chainLen));
      ctx.stroke();
    }
  }
}

/**
 * Iron Bars — Prison room vertical bars across a doorway.
 */
function drawProp_iron_bars(ctx, x, y, size, seed, palette) {
  ctx.strokeStyle = shiftColor(palette.metal || palette.secondary, 10);
  ctx.lineWidth = 1.5;
  for (let bar = 0; bar < 3; bar++) {
    const barX = x + size * 0.2 + bar * (size * 0.3);
    ctx.beginPath();
    ctx.moveTo(barX, y + size * 0.1);
    ctx.lineTo(barX, y + size * 0.9);
    ctx.stroke();
  }
  // Horizontal cross bar
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x + size * 0.15, y + size * 0.35);
  ctx.lineTo(x + size * 0.85, y + size * 0.35);
  ctx.stroke();
}

/**
 * Ripple Pool — Flooded room concentric water ripple arcs.
 */
function drawProp_ripple_pool(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size / 2;

  // Water tint
  ctx.fillStyle = 'rgba(10, 50, 70, 0.20)';
  ctx.beginPath();
  ctx.ellipse(cx, cy, size * 0.35, size * 0.25, 0, 0, Math.PI * 2);
  ctx.fill();

  // Ripple arcs
  ctx.strokeStyle = 'rgba(100, 190, 230, 0.18)';
  ctx.lineWidth = 0.6;
  for (let ring = 0; ring < 3; ring++) {
    const r = size * 0.08 + ring * size * 0.1;
    ctx.beginPath();
    ctx.arc(cx, cy, r, Math.PI * 0.1, Math.PI * 0.9);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(cx, cy, r, Math.PI * 1.1, Math.PI * 1.7);
    ctx.stroke();
  }
}

/**
 * Nave Aisle — Cathedral center aisle darker strip with border lines.
 */
function drawProp_nave_aisle(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const aisleW = size * 0.7;

  // Aisle strip
  ctx.fillStyle = 'rgba(0,0,0,0.06)';
  ctx.fillRect(cx - aisleW / 2, y, aisleW, size);

  // Border lines
  ctx.strokeStyle = hexAlpha(palette.highlight, 0.12);
  ctx.lineWidth = 0.8;
  ctx.beginPath();
  ctx.moveTo(cx - aisleW / 2, y);
  ctx.lineTo(cx - aisleW / 2, y + size);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(cx + aisleW / 2, y);
  ctx.lineTo(cx + aisleW / 2, y + size);
  ctx.stroke();
}

/**
 * Rose Window — Cathedral circular stained-glass motif with radial spokes.
 */
function drawProp_rose_window(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size / 2;
  const r = size * 0.35;

  // Outer ring
  ctx.strokeStyle = hexAlpha(palette.accent, 0.20);
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.stroke();

  // Inner ring
  ctx.strokeStyle = hexAlpha(palette.highlight, 0.15);
  ctx.lineWidth = 0.8;
  ctx.beginPath();
  ctx.arc(cx, cy, r * 0.55, 0, Math.PI * 2);
  ctx.stroke();

  // 8 radial spokes
  ctx.strokeStyle = hexAlpha(palette.accent, 0.12);
  ctx.lineWidth = 0.5;
  for (let i = 0; i < 8; i++) {
    const angle = (i / 8) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(angle) * r * 0.3, cy + Math.sin(angle) * r * 0.3);
    ctx.lineTo(cx + Math.cos(angle) * r * 0.9, cy + Math.sin(angle) * r * 0.9);
    ctx.stroke();
  }

  // Center gem
  ctx.fillStyle = hexAlpha(palette.highlight, 0.25);
  ctx.beginPath();
  ctx.arc(cx, cy, 2.5, 0, Math.PI * 2);
  ctx.fill();
}

/**
 * Arcane Circle — Ritual room glowing containment ring with center glow.
 */
function drawProp_arcane_circle(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size / 2;

  // Center glow
  const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, size * 0.4);
  grad.addColorStop(0, hexAlpha(palette.accent, 0.08));
  grad.addColorStop(0.5, hexAlpha(palette.accent, 0.03));
  grad.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.4, 0, Math.PI * 2);
  ctx.fill();

  // Containment ring
  ctx.strokeStyle = hexAlpha(palette.accent, 0.15);
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.35, 0, Math.PI * 2);
  ctx.stroke();
}

/**
 * Floor Rune — Ritual room small cross-shaped rune mark.
 */
function drawProp_floor_rune(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size / 2;

  ctx.strokeStyle = hexAlpha(palette.accent, 0.22);
  ctx.lineWidth = 0.7;
  // Vertical
  ctx.beginPath();
  ctx.moveTo(cx, cy - 4);
  ctx.lineTo(cx, cy + 4);
  ctx.stroke();
  // Horizontal
  ctx.beginPath();
  ctx.moveTo(cx - 3, cy);
  ctx.lineTo(cx + 3, cy);
  ctx.stroke();
}

/**
 * Disturbed Earth — Graveyard irregular darker earth patch.
 */
function drawProp_disturbed_earth(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size / 2;
  const h = cellHash;

  for (let i = 0; i < 3; i++) {
    const px = cx + (h(seed, i, 160) - 0.5) * size * 0.4;
    const py = cy + (h(seed, i, 161) - 0.5) * size * 0.3;
    const rx = size * 0.12 + h(seed, i, 162) * size * 0.08;
    const ry = size * 0.08 + h(seed, i, 163) * size * 0.05;
    ctx.fillStyle = 'rgba(20, 15, 8, 0.12)';
    ctx.beginPath();
    ctx.ellipse(px, py, rx, ry, h(seed, i, 164) * Math.PI, 0, Math.PI * 2);
    ctx.fill();
  }

  // Soil dots
  ctx.fillStyle = shiftColor(palette.floor || palette.primary, -6);
  for (let d = 0; d < 5; d++) {
    const dx = x + size * 0.2 + h(seed, d, 165) * size * 0.6;
    const dy = y + size * 0.2 + h(seed, d, 166) * size * 0.6;
    ctx.fillRect(dx, dy, 1.5, 1);
  }
}

/**
 * Weapon Peg — Armory wall-mounted display pegs for weapons.
 */
function drawProp_weapon_peg(ctx, x, y, size, seed, palette) {
  ctx.fillStyle = shiftColor(palette.metal || palette.secondary, 12);
  // Two pegs
  ctx.fillRect(x + size * 0.3, y + size * 0.2, 2, 6);
  ctx.fillRect(x + size * 0.6, y + size * 0.2, 2, 6);

  // Rack bar
  const trimColor = shiftColor(palette.metal || palette.secondary, 8);
  ctx.fillStyle = trimColor;
  ctx.fillRect(x + size * 0.15, y + size * 0.15, size * 0.7, 3);
  ctx.fillStyle = hexAlpha(palette.highlight, 0.10);
  ctx.fillRect(x + size * 0.15, y + size * 0.15, size * 0.7, 1);
}

/**
 * Wall Light — Armory warm glow spot on wall.
 */
function drawProp_wall_light(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size / 2;

  const grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, size * 0.4);
  grad.addColorStop(0, 'rgba(255, 180, 80, 0.12)');
  grad.addColorStop(1, 'rgba(255, 120, 40, 0)');
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.4, 0, Math.PI * 2);
  ctx.fill();

  // Small fixture mark
  ctx.fillStyle = shiftColor(palette.metal || palette.secondary, 10);
  ctx.fillRect(cx - 2, cy - 3, 4, 6);
}

/**
 * Bone Wall — Ossuary horizontal bone-layer texture on wall.
 */
function drawProp_bone_wall(ctx, x, y, size, seed, palette) {
  const boneColor = 'rgba(180, 170, 150, 0.12)';
  for (let row = 0; row < 5; row++) {
    const ly = y + 4 + row * ((size - 8) / 5);
    ctx.fillStyle = boneColor;
    ctx.fillRect(x + 4, ly, size - 8, 2);
  }
  // Subtle frame
  ctx.strokeStyle = 'rgba(180, 170, 150, 0.06)';
  ctx.lineWidth = 0.5;
  ctx.strokeRect(x + 2, y + 2, size - 4, size - 4);
}

/**
 * Bone Alcove — Ossuary dark inset recess with border.
 */
function drawProp_bone_alcove(ctx, x, y, size, seed, palette) {
  const alcoveColor = shiftColor(palette.primary, -5);
  ctx.fillStyle = alcoveColor;
  ctx.fillRect(x + size * 0.15, y + size * 0.1, size * 0.7, size * 0.4);
  ctx.strokeStyle = shiftColor(palette.secondary, 5);
  ctx.lineWidth = 0.5;
  ctx.strokeRect(x + size * 0.15, y + size * 0.1, size * 0.7, size * 0.4);
}

/**
 * Glow Pool — Fungal grotto bioluminescent center glow.
 */
function drawProp_glow_pool(ctx, x, y, size, seed, palette) {
  const cx = x + size / 2;
  const cy = y + size / 2;
  const glowColor = palette.accent;

  const grad = ctx.createRadialGradient(cx, cy, 1, cx, cy, size * 0.4);
  grad.addColorStop(0, hexAlpha(glowColor, 0.12));
  grad.addColorStop(0.6, hexAlpha(glowColor, 0.04));
  grad.addColorStop(1, hexAlpha(glowColor, 0));
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.4, 0, Math.PI * 2);
  ctx.fill();

  // Damp highlight
  ctx.fillStyle = 'rgba(100, 180, 120, 0.06)';
  ctx.beginPath();
  ctx.ellipse(cx, cy, size * 0.2, size * 0.12, 0, 0, Math.PI * 2);
  ctx.fill();
}

// ═══════════════════════════════════════════════════════════
//  PROP DISPATCH MAP
// ═══════════════════════════════════════════════════════════

const PROP_DRAW_MAP = {
  pillar:            drawProp_pillar,
  rubble:            drawProp_rubble,
  brazier:           drawProp_brazier,
  coffin:            drawProp_coffin,
  bookshelf:         drawProp_bookshelf,
  altar:             drawProp_altar,
  puddle:            drawProp_puddle,
  barrel:            drawProp_barrel,
  chains:            drawProp_chains,
  banner:            drawProp_banner,
  statue:            drawProp_statue,
  throne:            drawProp_throne,
  cage:              drawProp_cage,
  weapon_rack:       drawProp_weapon_rack,
  torch_sconce:      drawProp_torch_sconce,
  skull_pile:        drawProp_skull_pile,
  mushroom_cluster:  drawProp_mushroom_cluster,
  web:               drawProp_web,
  fountain:          drawProp_fountain,
  candelabra:        drawProp_candelabra,
  ritual_circle:     drawProp_ritual_circle,
  iron_maiden:       drawProp_iron_maiden,
  tombstone:         drawProp_tombstone,
  lectern:           drawProp_lectern,
  desk:              drawProp_desk,
  crate:             drawProp_crate,
  bone_pile:         drawProp_bone_pile,
  hanging_lantern:   drawProp_hanging_lantern,
  // Overlay decorations (archetype-specific structural elements)
  corner_pillar:     drawProp_corner_pillar,
  floor_sigil:       drawProp_floor_sigil,
  wall_torch:        drawProp_wall_torch,
  wall_alcove:       drawProp_wall_alcove,
  corner_ornament:   drawProp_corner_ornament,
  arrival_circle:    drawProp_arrival_circle,
  archway:           drawProp_archway,
  corner_rubble:     drawProp_corner_rubble,
  stair_descent:     drawProp_stair_descent,
  wall_banner:       drawProp_wall_banner,
  wall_chains:       drawProp_wall_chains,
  iron_bars:         drawProp_iron_bars,
  ripple_pool:       drawProp_ripple_pool,
  nave_aisle:        drawProp_nave_aisle,
  rose_window:       drawProp_rose_window,
  arcane_circle:     drawProp_arcane_circle,
  floor_rune:        drawProp_floor_rune,
  disturbed_earth:   drawProp_disturbed_earth,
  weapon_peg:        drawProp_weapon_peg,
  wall_light:        drawProp_wall_light,
  bone_wall:         drawProp_bone_wall,
  bone_alcove:       drawProp_bone_alcove,
  glow_pool:         drawProp_glow_pool,
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
//  ARCHETYPE PROP SLOTS (Budget + Focal System)
// ═══════════════════════════════════════════════════════════

/**
 * Defines prop placement rules per room archetype.
 *
 * Each archetype config:
 *   - maxProps: max number of prop slots activated (prevents clutter)
 *   - focal: (optional) mutually exclusive center props — exactly one
 *            is chosen via weighted random. Gives each room a unique
 *            identity (altar room vs throne room vs ritual chamber).
 *            Each entry: { prop, weight }
 *   - accents: supporting props that fill remaining budget.
 *            Each entry: { prop, position, chance }
 *
 * Props that an archetype overlay already draws (pillars, torches,
 * bookshelves, etc.) are intentionally excluded here to prevent
 * visual doubling.
 */
export const ARCHETYPE_PROP_SLOTS = {
  // Boss overlay draws: corner pillars, center sigil, wall trim
  boss: {
    maxProps: 5,
    focal: [
      { prop: 'altar',         weight: 0.45 },
      { prop: 'throne',        weight: 0.30 },
      { prop: 'ritual_circle', weight: 0.25 },
    ],
    accents: [
      { prop: 'brazier',      position: 'flanking_center',  chance: 0.7 },
      { prop: 'banner',       position: 'on_wall_top',      chance: 0.5 },
      { prop: 'statue',       position: 'wall_left',        chance: 0.4 },
      { prop: 'candelabra',   position: 'flanking_center',  chance: 0.35 },
      { prop: 'weapon_rack',  position: 'on_wall_right',    chance: 0.3 },
    ],
  },
  // Enemy overlay draws: paired torches L/R walls, door path
  enemy: {
    maxProps: 4,
    accents: [
      { prop: 'brazier',      position: 'wall_left',        chance: 0.5 },
      { prop: 'brazier',      position: 'wall_right',       chance: 0.5 },
      { prop: 'chains',       position: 'on_wall_top',      chance: 0.35 },
      { prop: 'weapon_rack',  position: 'on_wall_top',      chance: 0.55 },
      { prop: 'crate',        position: 'corners',          chance: 0.25 },
      { prop: 'rubble',       position: 'random_floor',     chance: 0.25 },
      { prop: 'banner',       position: 'on_wall_left',     chance: 0.3 },
    ],
  },
  // Loot overlay draws: polished floor, wall alcoves, corner filigree (no prop overlap)
  loot: {
    maxProps: 4,
    accents: [
      { prop: 'barrel',       position: 'corners',          chance: 0.6 },
      { prop: 'crate',        position: 'random_floor',     chance: 0.4 },
      { prop: 'barrel',       position: 'random_floor',     chance: 0.3 },
      { prop: 'brazier',      position: 'wall_left',        chance: 0.3 },
      { prop: 'torch_sconce', position: 'on_wall_right',    chance: 0.3 },
      { prop: 'hanging_lantern', position: 'on_wall_left',   chance: 0.3 },
      { prop: 'web',          position: 'corners',          chance: 0.15 },
    ],
  },
  // Spawn overlay draws: archway highlights, arrival circle (no prop overlap)
  spawn: {
    maxProps: 3,
    accents: [
      { prop: 'banner',       position: 'on_wall_top',      chance: 0.5 },
      { prop: 'brazier',      position: 'flanking_center',  chance: 0.4 },
      { prop: 'torch_sconce', position: 'on_wall_left',     chance: 0.3 },
    ],
  },
  // Empty overlay draws: corner rubble, dark wash, wall darkening
  empty: {
    maxProps: 3,
    accents: [
      { prop: 'rubble',       position: 'random_floor',     chance: 0.4 },
      { prop: 'web',          position: 'corners',          chance: 0.45 },
      { prop: 'chains',       position: 'on_wall_left',     chance: 0.2 },
      { prop: 'bone_pile',    position: 'random_floor',     chance: 0.25 },
      { prop: 'skull_pile',   position: 'random_floor',     chance: 0.12 },
      { prop: 'tombstone',    position: 'random_floor',     chance: 0.12 },
      { prop: 'hanging_lantern', position: 'on_wall_right', chance: 0.2 },
    ],
  },
  // Stairs overlay draws: wall streaks, floor borders (no prop overlap)
  stairs: {
    maxProps: 3,
    accents: [
      { prop: 'pillar',       position: 'wall_left',        chance: 0.4 },
      { prop: 'pillar',       position: 'wall_right',       chance: 0.4 },
      { prop: 'torch_sconce', position: 'on_wall_top',      chance: 0.5 },
    ],
  },
  // Shrine overlay draws: center altar+gem, flanking braziers, top-wall banners
  shrine: {
    maxProps: 3,
    accents: [
      { prop: 'statue',          position: 'corners',          chance: 0.4 },
      { prop: 'candelabra',      position: 'wall_right',       chance: 0.45 },
      { prop: 'hanging_lantern', position: 'on_wall_left',  chance: 0.25 },
      { prop: 'torch_sconce',    position: 'on_wall_left',     chance: 0.35 },
    ],
  },
  // Library overlay draws: bookshelves on top/bottom walls, lighter floor, dust motes.
  library: {
    maxProps: 4,
    focal: [
      { prop: 'lectern', weight: 0.6 },
      { prop: 'desk',    weight: 0.4 },
    ],
    accents: [
      { prop: 'hanging_lantern', position: 'on_wall_left',    chance: 0.35 },
      { prop: 'torch_sconce',   position: 'on_wall_left',     chance: 0.4 },
      { prop: 'torch_sconce',   position: 'on_wall_right',    chance: 0.3 },
    ],
  },
  // Prison overlay draws: chains on L/R walls, doorway iron bars, corner vignette
  prison: {
    maxProps: 4,
    focal: [
      { prop: 'cage',         weight: 0.55 },
      { prop: 'iron_maiden',  weight: 0.45 },
    ],
    accents: [
      { prop: 'chains',       position: 'on_wall_top',      chance: 0.4 },
      { prop: 'skull_pile',   position: 'random_floor',     chance: 0.2 },
      { prop: 'iron_maiden',  position: 'wall_right',       chance: 0.3 },
    ],
  },
  // Flooded overlay draws: water tint, reflective edges, ripple lines. Props own: puddles, mushrooms, fountain.
  flooded: {
    maxProps: 5,
    focal: [
      { prop: 'fountain',          weight: 0.45 },
      { prop: 'puddle',            weight: 0.55 },
    ],
    accents: [
      { prop: 'puddle',            position: 'random_floor',     chance: 0.65 },
      { prop: 'puddle',            position: 'corners',          chance: 0.4 },
      { prop: 'mushroom_cluster',  position: 'wall_left',        chance: 0.45 },
      { prop: 'mushroom_cluster',  position: 'wall_right',       chance: 0.3 },
      { prop: 'hanging_lantern',   position: 'on_wall_left',     chance: 0.25 },
    ],
  },
  // Cathedral overlay draws: central aisle, rose window, wall streaks (no center prop)
  cathedral: {
    maxProps: 5,
    focal: [
      { prop: 'fountain',     weight: 0.40 },
      { prop: 'statue',       weight: 0.35 },
      { prop: 'candelabra',   weight: 0.25 },
    ],
    accents: [
      { prop: 'candelabra',      position: 'wall_left',        chance: 0.4 },
      { prop: 'candelabra',      position: 'wall_right',       chance: 0.4 },
      { prop: 'banner',          position: 'on_wall_top',      chance: 0.5 },
      { prop: 'hanging_lantern', position: 'on_wall_left',  chance: 0.3 },
      { prop: 'statue',          position: 'corners',          chance: 0.35 },
      { prop: 'rubble',          position: 'random_floor',     chance: 0.15 },
      { prop: 'tombstone',       position: 'random_floor',     chance: 0.15 },
    ],
  },
  // Ritual overlay draws: central glow, corner darkening, floor runes, containment ring
  ritual: {
    maxProps: 4,
    focal: [
      { prop: 'ritual_circle', weight: 1.0 },
    ],
    accents: [
      { prop: 'candelabra',   position: 'corners',          chance: 0.5 },
      { prop: 'brazier',      position: 'flanking_center',  chance: 0.4 },
      { prop: 'skull_pile',   position: 'random_floor',     chance: 0.25 },
    ],
  },
  // Torture overlay draws: blood stains, scratch marks, metal brackets, heavy vignette
  torture: {
    maxProps: 5,
    focal: [
      { prop: 'cage',         weight: 0.40 },
      { prop: 'iron_maiden',  weight: 0.60 },
    ],
    accents: [
      { prop: 'chains',       position: 'on_wall_top',      chance: 0.75 },
      { prop: 'chains',       position: 'on_wall_right',    chance: 0.4 },
      { prop: 'bone_pile',    position: 'random_floor',     chance: 0.5 },
      { prop: 'skull_pile',   position: 'corners',          chance: 0.3 },
      { prop: 'torch_sconce', position: 'on_wall_left',     chance: 0.45 },
    ],
  },
  // Graveyard overlay draws: earth wash, soil patches, mist, row markers, grave mounds
  graveyard: {
    maxProps: 7,
    focal: [
      { prop: 'tombstone',    weight: 0.70 },
      { prop: 'coffin',       weight: 0.30 },
    ],
    accents: [
      { prop: 'tombstone',    position: 'wall_top',         chance: 0.75 },
      { prop: 'tombstone',    position: 'corners',          chance: 0.6 },
      { prop: 'tombstone',    position: 'random_floor',     chance: 0.6 },
      { prop: 'coffin',       position: 'wall_top',         chance: 0.4 },
      { prop: 'bone_pile',    position: 'random_floor',     chance: 0.35 },
      { prop: 'torch_sconce', position: 'on_wall_left',     chance: 0.3 },
      { prop: 'skull_pile',   position: 'random_floor',     chance: 0.2 },
      { prop: 'web',          position: 'corners',          chance: 0.2 },
    ],
  },
  // Armory overlay draws: metal trim, weapon pegs on top wall, lighting glow, door path
  armory: {
    maxProps: 5,
    accents: [
      { prop: 'weapon_rack',  position: 'on_wall_top',      chance: 0.7 },
      { prop: 'weapon_rack',  position: 'on_wall_left',     chance: 0.5 },
      { prop: 'crate',        position: 'random_floor',     chance: 0.35 },
      { prop: 'barrel',       position: 'corners',          chance: 0.5 },
      { prop: 'torch_sconce', position: 'on_wall_right',    chance: 0.45 },
      { prop: 'barrel',       position: 'random_floor',     chance: 0.25 },
    ],
  },
  // Ossuary overlay draws: bone-stack wall texture, wall alcoves, candle warm spots
  ossuary: {
    maxProps: 5,
    focal: [
      { prop: 'altar',        weight: 0.35 },
      { prop: 'coffin',       weight: 0.35 },
      { prop: 'candelabra',   weight: 0.30 },
    ],
    accents: [
      { prop: 'skull_pile',   position: 'wall_left',        chance: 0.6 },
      { prop: 'skull_pile',   position: 'wall_right',       chance: 0.6 },
      { prop: 'skull_pile',   position: 'corners',          chance: 0.4 },
      { prop: 'bone_pile',    position: 'random_floor',     chance: 0.3 },
      { prop: 'coffin',       position: 'wall_top',         chance: 0.4 },
      { prop: 'tombstone',    position: 'random_floor',     chance: 0.25 },
    ],
  },
  // Fungal grotto overlay draws: green wash, glow pools, organic wall bumps, spore motes, mycelium tendrils
  fungal_grotto: {
    maxProps: 6,
    focal: [
      { prop: 'mushroom_cluster', weight: 0.75 },
      { prop: 'puddle',           weight: 0.25 },
    ],
    accents: [
      { prop: 'mushroom_cluster', position: 'wall_left',    chance: 0.85 },
      { prop: 'mushroom_cluster', position: 'wall_right',   chance: 0.85 },
      { prop: 'mushroom_cluster', position: 'corners',      chance: 0.6 },
      { prop: 'mushroom_cluster', position: 'random_floor', chance: 0.4 },
      { prop: 'puddle',           position: 'random_floor', chance: 0.45 },
      { prop: 'web',              position: 'corners',      chance: 0.2 },
    ],
  },
};

// ═══════════════════════════════════════════════════════════
//  PROP PLACEMENT ENGINE
// ═══════════════════════════════════════════════════════════

/**
 * Check if a tile is on or adjacent to any door position.
 * @param {number} tx - Tile X
 * @param {number} ty - Tile Y
 * @param {Array<{x: number, y: number}>} doorPositions
 * @returns {boolean}
 */
function _isNearDoor(tx, ty, doorPositions) {
  if (!doorPositions || doorPositions.length === 0) return false;
  for (const d of doorPositions) {
    if (Math.abs(tx - d.x) <= 1 && Math.abs(ty - d.y) <= 1) return true;
  }
  return false;
}

/**
 * Resolve a position keyword into actual tile coordinates within a room.
 * Returns an array of { x, y } in room-grid coordinates.
 * Tiles on or adjacent to doors are automatically excluded.
 *
 * @param {string} position - Position keyword
 * @param {Object} bounds - { x_min, y_min, x_max, y_max } inner floor area
 * @param {number} seed - Room seed for deterministic random placement
 * @param {Array<{x: number, y: number}>} [doorPositions] - Door tile coords
 * @param {Set<string>} [walkableTiles] - Set of "x,y" keys for valid floor tiles
 * @returns {Array<{x: number, y: number}>}
 */
function _resolvePosition(position, bounds, seed, doorPositions, walkableTiles) {
  const { x_min, y_min, x_max, y_max } = bounds;
  const floorW = x_max - x_min + 1;
  const floorH = y_max - y_min + 1;
  const midX = Math.floor((x_min + x_max) / 2);
  const midY = Math.floor((y_min + y_max) / 2);
  const _isWalkable = (p) => !walkableTiles || walkableTiles.has(`${p.x},${p.y}`);

  let tiles;

  switch (position) {
    case 'center':
      tiles = [{ x: midX, y: midY }];
      break;

    case 'corners':
      tiles = [
        { x: x_min, y: y_min },
        { x: x_max, y: y_min },
        { x: x_min, y: y_max },
        { x: x_max, y: y_max },
      ];
      break;

    case 'flanking_center':
      tiles = [
        { x: midX - 1, y: midY },
        { x: midX + 1, y: midY },
      ];
      break;

    case 'wall_left': {
      // Spread along the left wall — pick a tile offset from midY by seed
      const wallTiles = [];
      for (let ty = y_min + 1; ty < y_max; ty++) wallTiles.push({ x: x_min, y: ty });
      if (wallTiles.length === 0) { tiles = [{ x: x_min, y: midY }]; break; }
      const pick = Math.floor(cellHash(seed, 0, 93) * wallTiles.length);
      tiles = [wallTiles[pick]];
      break;
    }

    case 'wall_right': {
      const wallTiles = [];
      for (let ty = y_min + 1; ty < y_max; ty++) wallTiles.push({ x: x_max, y: ty });
      if (wallTiles.length === 0) { tiles = [{ x: x_max, y: midY }]; break; }
      const pick = Math.floor(cellHash(seed, 0, 94) * wallTiles.length);
      tiles = [wallTiles[pick]];
      break;
    }

    case 'wall_top': {
      // Every other tile along the top interior edge
      tiles = [];
      for (let tx = x_min + 1; tx < x_max; tx += 2) {
        tiles.push({ x: tx, y: y_min });
      }
      break;
    }

    case 'wall_bottom': {
      tiles = [];
      for (let tx = x_min + 1; tx < x_max; tx += 2) {
        tiles.push({ x: tx, y: y_max });
      }
      break;
    }

    case 'random_floor': {
      // Wall-adjacent floor: place 1-2 tiles within 1 tile of a wall,
      // never at room center. Reads as intentional environmental detail.
      const count = 1 + Math.floor(cellHash(seed, 0, 90) * 2);
      tiles = [];
      const candidates = [];
      for (let fy = y_min; fy <= y_max; fy++) {
        for (let fx = x_min; fx <= x_max; fx++) {
          // Must be within 1 tile of a wall edge
          const nearWall = (fx <= x_min + 1 || fx >= x_max - 1 ||
                            fy <= y_min + 1 || fy >= y_max - 1);
          // Must NOT be at room center (2-tile exclusion radius)
          const nearCenter = Math.abs(fx - midX) <= 1 && Math.abs(fy - midY) <= 1;
          if (nearWall && !nearCenter && _isWalkable({ x: fx, y: fy })) candidates.push({ x: fx, y: fy });
        }
      }
      if (candidates.length === 0) break;
      for (let i = 0; i < count; i++) {
        const idx = Math.floor(cellHash(seed, i, 91) * candidates.length);
        tiles.push(candidates[idx]);
      }
      break;
    }

    case 'on_wall_top': {
      // Actual wall tiles above the room floor — for wall-mounted decorations
      tiles = [];
      for (let tx = x_min + 1; tx < x_max; tx += 2) {
        tiles.push({ x: tx, y: y_min - 1 });
      }
      // Wall tiles bypass walkability check
      return tiles.filter(t => !_isNearDoor(t.x, t.y, doorPositions));
    }

    case 'on_wall_left': {
      // Actual wall tile to the left of room floor
      const wallTilesL = [];
      for (let ty = y_min + 1; ty < y_max; ty++) wallTilesL.push({ x: x_min - 1, y: ty });
      if (wallTilesL.length === 0) return [{ x: x_min - 1, y: midY }].filter(t => !_isNearDoor(t.x, t.y, doorPositions));
      const pickL = Math.floor(cellHash(seed, 0, 95) * wallTilesL.length);
      return [wallTilesL[pickL]].filter(t => !_isNearDoor(t.x, t.y, doorPositions));
    }

    case 'on_wall_right': {
      // Actual wall tile to the right of room floor
      const wallTilesR = [];
      for (let ty = y_min + 1; ty < y_max; ty++) wallTilesR.push({ x: x_max + 1, y: ty });
      if (wallTilesR.length === 0) return [{ x: x_max + 1, y: midY }].filter(t => !_isNearDoor(t.x, t.y, doorPositions));
      const pickR = Math.floor(cellHash(seed, 0, 96) * wallTilesR.length);
      return [wallTilesR[pickR]].filter(t => !_isNearDoor(t.x, t.y, doorPositions));
    }

    default:
      tiles = [];
  }

  // Filter out tiles that aren't walkable, then tiles on or adjacent to doors
  if (walkableTiles && tiles.length > 0) {
    tiles = tiles.filter(_isWalkable);
  }
  return tiles.filter(t => !_isNearDoor(t.x, t.y, doorPositions));
}

/**
 * Pick exactly one focal prop from a weighted list, filtered by theme affinity.
 * @param {Array} focalOptions - [{ prop, weight }]
 * @param {number} seed
 * @param {Object} affinities - theme.propAffinities
 * @returns {string|null} prop name or null if none valid
 */
function _pickFocal(focalOptions, seed, affinities) {
  const valid = focalOptions.filter(f => {
    const aff = affinities[f.prop];
    return aff !== undefined && aff > 0;
  });
  if (valid.length === 0) return null;

  const weighted = valid.map(f => ({
    prop: f.prop,
    weight: f.weight * (affinities[f.prop] || 0),
  }));

  const totalWeight = weighted.reduce((sum, w) => sum + w.weight, 0);
  if (totalWeight <= 0) return null;

  let roll = cellHash(seed, 0, 200) * totalWeight;
  for (const w of weighted) {
    roll -= w.weight;
    if (roll <= 0) return w.prop;
  }
  return weighted[weighted.length - 1].prop;
}

// Position priority for accent ordering — structural first, scatter last
const _POSITION_PRIORITY = {
  center: 0,
  flanking_center: 1,
  corners: 2,
  on_wall_top: 3,
  on_wall_left: 3,
  on_wall_right: 3,
  wall_top: 3,
  wall_bottom: 3,
  wall_left: 4,
  wall_right: 4,
  random_floor: 5,
};

/**
 * Draw all props for a room based on its archetype and theme.
 * Uses a budget system (maxProps) plus focal/accent split to
 * produce intentional, uncluttered rooms.
 *
 * Call this AFTER base floor tiles are drawn, BEFORE room archetype overlay.
 */
export function drawRoomProps(ctx, opts) {
  const { archetype, theme, tileSize, roomOffsetX, roomOffsetY, bounds, seed, doorPositions, walkableTiles } = opts;

  const config = ARCHETYPE_PROP_SLOTS[archetype];
  if (!config) return;

  const affinities = theme.propAffinities || {};
  const maxProps = config.maxProps || 99;
  let propsPlaced = 0;

  // Track claimed tiles — key: "x,y" — prevents prop stacking
  const claimed = new Set();

  // --- Helper: place prop at resolved positions, returns true if any placed ---
  const _placeSlot = (propName, position, slotSeed) => {
    const positions = _resolvePosition(position, bounds, slotSeed, doorPositions, walkableTiles);
    let placedAny = false;
    for (const pos of positions) {
      const key = `${pos.x},${pos.y}`;
      if (claimed.has(key)) continue;
      claimed.add(key);
      placedAny = true;
      const px = roomOffsetX + pos.x * tileSize;
      const py = roomOffsetY + pos.y * tileSize;
      const tileSeed = cellHash(pos.x, pos.y, seed);
      drawTileProp(ctx, propName, px, py, tileSize, tileSeed, theme.palette);
    }
    return placedAny;
  };

  // --- FOCAL PROP: pick exactly one from weighted group ---
  if (config.focal && config.focal.length > 0 && propsPlaced < maxProps) {
    const focalProp = _pickFocal(config.focal, seed, affinities);
    if (focalProp && _placeSlot(focalProp, 'center', seed)) {
      propsPlaced++;
    }
  }

  // --- ACCENT PROPS: fill remaining budget ---
  if (config.accents) {
    const sortedAccents = config.accents.map((s, i) => ({ ...s, _origIdx: i }))
      .sort((a, b) => (_POSITION_PRIORITY[a.position] ?? 9) - (_POSITION_PRIORITY[b.position] ?? 9));

    for (const slot of sortedAccents) {
      if (propsPlaced >= maxProps) break;

      const i = slot._origIdx;
      const affinity = affinities[slot.prop];
      if (affinity === undefined || affinity <= 0) continue;

      const effectiveChance = slot.chance * affinity;
      const roll = cellHash(seed, i, 100);
      if (roll >= effectiveChance) continue;

      if (_placeSlot(slot.prop, slot.position, seed + i * 13)) {
        propsPlaced++;
      }
    }
  }
}

/**
 * Compute a Map of "x,y" → propName for a room, mirroring drawRoomProps logic
 * but without drawing. Used for hover tooltips and debugging.
 *
 * @param {Object} opts - Same options as drawRoomProps
 * @returns {Map<string, string>} Map of "x,y" → prop name
 */
export function computeRoomPropMap(opts) {
  const { archetype, theme, bounds, seed, doorPositions, walkableTiles } = opts;
  const result = new Map();

  const config = ARCHETYPE_PROP_SLOTS[archetype];
  if (!config) return result;

  const affinities = theme.propAffinities || {};
  const maxProps = config.maxProps || 99;
  let propsPlaced = 0;

  const claimed = new Set();

  const _placeSlot = (propName, position, slotSeed) => {
    const positions = _resolvePosition(position, bounds, slotSeed, doorPositions, walkableTiles);
    let placedAny = false;
    for (const pos of positions) {
      const key = `${pos.x},${pos.y}`;
      if (claimed.has(key)) continue;
      claimed.add(key);
      placedAny = true;
      result.set(key, propName);
    }
    return placedAny;
  };

  // Focal prop
  if (config.focal && config.focal.length > 0 && propsPlaced < maxProps) {
    const focalProp = _pickFocal(config.focal, seed, affinities);
    if (focalProp && _placeSlot(focalProp, 'center', seed)) {
      propsPlaced++;
    }
  }

  // Accent props
  if (config.accents) {
    const sortedAccents = config.accents.map((s, i) => ({ ...s, _origIdx: i }))
      .sort((a, b) => (_POSITION_PRIORITY[a.position] ?? 9) - (_POSITION_PRIORITY[b.position] ?? 9));

    for (const slot of sortedAccents) {
      if (propsPlaced >= maxProps) break;
      const i = slot._origIdx;
      const affinity = affinities[slot.prop];
      if (affinity === undefined || affinity <= 0) continue;
      const effectiveChance = slot.chance * affinity;
      const roll = cellHash(seed, i, 100);
      if (roll >= effectiveChance) continue;
      if (_placeSlot(slot.prop, slot.position, seed + i * 13)) {
        propsPlaced++;
      }
    }
  }

  return result;
}

export { PROP_DRAW_MAP };
