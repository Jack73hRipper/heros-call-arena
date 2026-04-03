/**
 * chestRenderer — Detailed treasure chest drawing for dungeon tiles.
 *
 * Draws a proper barrel-lidded chest with curved dome lid, wood plank
 * texture, metal corner brackets, prominent lock plate, ground shadow,
 * and tier-specific structural details (rope, rivets, runes, gems).
 * Supports both unopened and opened states with visual depth.
 */

import { getChestTierConfig } from '../utils/chestUtils.js';

// ── Tier-specific feature flags ──
const TIER_FEATURES = {
  wooden:     { planks: true, rope: true,  rivets: false, cornerBrackets: false, gem: false, runes: false, lockStyle: 'simple' },
  iron:       { planks: true, rope: false, rivets: true,  cornerBrackets: true,  gem: false, runes: false, lockStyle: 'iron' },
  gold:       { planks: true, rope: false, rivets: true,  cornerBrackets: true,  gem: true,  runes: false, lockStyle: 'ornate' },
  obsidian:   { planks: false, rope: false, rivets: true,  cornerBrackets: true,  gem: true,  runes: true,  lockStyle: 'skull' },
  boss_chest: { planks: true, rope: false, rivets: true,  cornerBrackets: true,  gem: true,  runes: true,  lockStyle: 'ornate' },
};

/**
 * Draw a detailed treasure chest icon on a tile.
 *
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} px - Pixel X of tile top-left
 * @param {number} py - Pixel Y of tile top-left
 * @param {number} s  - Tile size in pixels
 * @param {string} tier - Chest tier: "wooden", "iron", "gold", "obsidian", "boss_chest"
 * @param {boolean} isOpened - Whether the chest has been opened
 * @param {Object} [paletteOverride] - Optional theme palette to tint colors
 */
export function drawChestIcon(ctx, px, py, s, tier, isOpened, paletteOverride) {
  const cfg = getChestTierConfig(tier);
  const feat = TIER_FEATURES[tier] || TIER_FEATURES.wooden;

  // Chest proportions relative to tile
  const cw = s * 0.58;       // chest width
  const ch = s * 0.42;       // chest body height
  const lidH = s * 0.18;     // lid height (taller for dome)
  const cx = px + (s - cw) / 2;
  const cy = py + (s - ch - lidH) / 2 + s * 0.08;
  const lidY = cy - lidH;

  ctx.save();

  // ── Ground shadow ──
  ctx.fillStyle = 'rgba(0, 0, 0, 0.35)';
  ctx.beginPath();
  ctx.ellipse(cx + cw / 2, cy + ch + s * 0.02, cw * 0.52, s * 0.05, 0, 0, Math.PI * 2);
  ctx.fill();

  // ── Tier glow (gold, obsidian, boss) ──
  if (cfg.glowColor && !isOpened) {
    ctx.shadowColor = cfg.glowColor;
    ctx.shadowBlur = s * 0.3;
    ctx.fillStyle = cfg.glowColor;
    ctx.globalAlpha = 0.4;
    ctx.beginPath();
    ctx.ellipse(cx + cw / 2, cy + ch / 2, cw * 0.6, ch * 0.7, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.globalAlpha = 1.0;
  }

  if (isOpened) {
    _drawOpenedChest(ctx, cx, cy, cw, ch, lidH, lidY, s, cfg, feat, tier);
  } else {
    _drawClosedChest(ctx, cx, cy, cw, ch, lidH, lidY, s, cfg, feat, tier);
  }

  ctx.restore();
}

// ── Helper: draw a barrel-curved lid path ──
function _lidPath(ctx, lx, lidY, lw, lidH, domeH) {
  ctx.beginPath();
  ctx.moveTo(lx, lidY + lidH);
  ctx.lineTo(lx, lidY + lidH - domeH * 0.3);
  ctx.quadraticCurveTo(lx + lw * 0.5, lidY - domeH * 0.4, lx + lw, lidY + lidH - domeH * 0.3);
  ctx.lineTo(lx + lw, lidY + lidH);
  ctx.closePath();
}

// ── Helper: draw wood plank lines on a rectangular area ──
function _drawPlanks(ctx, x, y, w, h, color, count) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 0.7;
  const gap = w / (count + 1);
  for (let i = 1; i <= count; i++) {
    const px = x + gap * i;
    ctx.beginPath();
    ctx.moveTo(px, y + 1);
    ctx.lineTo(px, y + h - 1);
    ctx.stroke();
  }
}

// ── Helper: draw corner brackets ──
function _drawCornerBrackets(ctx, cx, cy, cw, ch, color, highlightColor) {
  const bLen = Math.max(3, cw * 0.14);
  const bW = Math.max(1.5, cw * 0.04);
  ctx.fillStyle = color;
  // Top-left
  ctx.fillRect(cx, cy, bLen, bW);
  ctx.fillRect(cx, cy, bW, bLen);
  // Top-right
  ctx.fillRect(cx + cw - bLen, cy, bLen, bW);
  ctx.fillRect(cx + cw - bW, cy, bW, bLen);
  // Bottom-left
  ctx.fillRect(cx, cy + ch - bW, bLen, bW);
  ctx.fillRect(cx, cy + ch - bLen, bW, bLen);
  // Bottom-right
  ctx.fillRect(cx + cw - bLen, cy + ch - bW, bLen, bW);
  ctx.fillRect(cx + cw - bW, cy + ch - bLen, bW, bLen);
  // Corner rivets
  const rr = Math.max(1, bW * 0.7);
  ctx.fillStyle = highlightColor;
  for (const [rx, ry] of [
    [cx + bW, cy + bW],
    [cx + cw - bW, cy + bW],
    [cx + bW, cy + ch - bW],
    [cx + cw - bW, cy + ch - bW],
  ]) {
    ctx.beginPath();
    ctx.arc(rx, ry, rr, 0, Math.PI * 2);
    ctx.fill();
  }
}

// ── Helper: draw rivets along a band ──
function _drawBandRivets(ctx, cx, cw, bandY, bandH, color) {
  const rr = Math.max(0.8, bandH * 0.5);
  ctx.fillStyle = color;
  const rivetCount = 3;
  for (let i = 0; i < rivetCount; i++) {
    const rx = cx + cw * (0.2 + i * 0.3);
    ctx.beginPath();
    ctx.arc(rx, bandY + bandH / 2, rr, 0, Math.PI * 2);
    ctx.fill();
  }
}

// ── Helper: draw rune lines on body (obsidian/boss) ──
function _drawRunes(ctx, cx, cy, cw, ch, color) {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 0.8;
  ctx.globalAlpha = 0.6;
  // Simple rune-like marks
  const midX = cx + cw / 2;
  const midY = cy + ch / 2;
  // Vertical center rune
  ctx.beginPath();
  ctx.moveTo(midX, cy + ch * 0.15);
  ctx.lineTo(midX, cy + ch * 0.85);
  ctx.stroke();
  // Cross marks
  ctx.beginPath();
  ctx.moveTo(midX - cw * 0.12, midY - ch * 0.15);
  ctx.lineTo(midX + cw * 0.12, midY + ch * 0.15);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(midX + cw * 0.12, midY - ch * 0.15);
  ctx.lineTo(midX - cw * 0.12, midY + ch * 0.15);
  ctx.stroke();
  ctx.restore();
}

function _drawClosedChest(ctx, cx, cy, cw, ch, lidH, lidY, s, cfg, feat, tier) {
  const lidOverhang = cw * 0.06;
  const lx = cx - lidOverhang;
  const lw = cw + lidOverhang * 2;
  const domeH = lidH * 0.85;

  // ── Body ──
  ctx.fillStyle = cfg.bodyColor;
  ctx.fillRect(cx, cy, cw, ch);

  // Wood plank lines
  if (feat.planks) {
    _drawPlanks(ctx, cx, cy, cw, ch, cfg.bodyDark, 3);
  }

  // Right-edge shadow for 3D depth
  ctx.fillStyle = cfg.bodyDark;
  ctx.fillRect(cx + cw - cw * 0.12, cy, cw * 0.12, ch);
  // Left-edge highlight
  ctx.fillStyle = cfg.bodyHighlight;
  ctx.fillRect(cx, cy, cw * 0.06, ch);
  // Body border
  ctx.strokeStyle = cfg.bodyDark;
  ctx.lineWidth = 1;
  ctx.strokeRect(cx, cy, cw, ch);

  // ── Rune engravings (obsidian/boss) ──
  if (feat.runes) {
    _drawRunes(ctx, cx, cy, cw, ch, cfg.latchColor);
  }

  // ── Metal bands (2 horizontal straps, thicker) ──
  const bandH = Math.max(2, s * 0.05);
  const band1Y = cy + ch * 0.22;
  const band2Y = cy + ch * 0.68;
  ctx.fillStyle = cfg.bandColor;
  ctx.fillRect(cx, band1Y, cw, bandH);
  ctx.fillRect(cx, band2Y, cw, bandH);
  // Band highlight (top edge)
  ctx.fillStyle = cfg.bodyHighlight;
  ctx.globalAlpha = 0.3;
  ctx.fillRect(cx, band1Y, cw, 1);
  ctx.fillRect(cx, band2Y, cw, 1);
  ctx.globalAlpha = 1.0;
  // Band shadow (bottom edge)
  ctx.fillStyle = cfg.bodyDark;
  ctx.fillRect(cx, band1Y + bandH - 1, cw, 1);
  ctx.fillRect(cx, band2Y + bandH - 1, cw, 1);

  // Band rivets (iron+)
  if (feat.rivets) {
    _drawBandRivets(ctx, cx, cw, band1Y, bandH, cfg.bodyHighlight);
    _drawBandRivets(ctx, cx, cw, band2Y, bandH, cfg.bodyHighlight);
  }

  // ── Rope binding (wooden tier) ──
  if (feat.rope) {
    ctx.strokeStyle = '#A08050';
    ctx.lineWidth = Math.max(1, s * 0.02);
    // Diagonal rope cross
    ctx.beginPath();
    ctx.moveTo(cx + cw * 0.25, cy);
    ctx.lineTo(cx + cw * 0.35, cy + ch);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(cx + cw * 0.75, cy);
    ctx.lineTo(cx + cw * 0.65, cy + ch);
    ctx.stroke();
  }

  // ── Corner brackets (iron+) ──
  if (feat.cornerBrackets) {
    _drawCornerBrackets(ctx, cx, cy, cw, ch, cfg.bandColor, cfg.bodyHighlight);
  }

  // ── Curved lid ──
  // Lid fill
  ctx.fillStyle = cfg.lidColor;
  _lidPath(ctx, lx, lidY, lw, lidH, domeH);
  ctx.fill();
  // Lid highlight (top curve)
  ctx.save();
  _lidPath(ctx, lx, lidY, lw, lidH, domeH);
  ctx.clip();
  ctx.fillStyle = cfg.bodyHighlight;
  ctx.globalAlpha = 0.35;
  ctx.fillRect(lx + 2, lidY, lw - 4, lidH * 0.35);
  ctx.globalAlpha = 1.0;
  ctx.restore();
  // Lid border
  ctx.strokeStyle = cfg.bodyDark;
  ctx.lineWidth = 1;
  _lidPath(ctx, lx, lidY, lw, lidH, domeH);
  ctx.stroke();

  // Lid metal band (center horizontal strap across dome)
  const lidBandY = lidY + lidH * 0.55;
  ctx.fillStyle = cfg.bandColor;
  ctx.fillRect(lx + 1, lidBandY, lw - 2, Math.max(1.5, s * 0.03));

  // ── Lock / clasp ──
  _drawLock(ctx, cx, cy, cw, ch, s, cfg, feat, tier);

  // ── Lid-to-body seam ──
  ctx.strokeStyle = cfg.bodyDark;
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(cx - lidOverhang * 0.5, cy);
  ctx.lineTo(cx + cw + lidOverhang * 0.5, cy);
  ctx.stroke();
}

function _drawLock(ctx, cx, cy, cw, ch, s, cfg, feat, tier) {
  const lockCenterX = cx + cw / 2;
  const lockTopY = cy + ch * 0.30;

  if (feat.lockStyle === 'simple') {
    // Wooden: simple circular latch
    const r = Math.max(3, s * 0.055);
    ctx.fillStyle = cfg.latchColor;
    ctx.beginPath();
    ctx.arc(lockCenterX, lockTopY + r, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = cfg.bodyDark;
    ctx.lineWidth = 0.8;
    ctx.stroke();
    // Keyhole
    ctx.fillStyle = cfg.bodyDark;
    ctx.beginPath();
    ctx.arc(lockCenterX, lockTopY + r, r * 0.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillRect(lockCenterX - r * 0.12, lockTopY + r, r * 0.24, r * 0.6);
  } else if (feat.lockStyle === 'iron') {
    // Iron: shield-shaped plate with keyhole
    const pw = Math.max(5, s * 0.12);
    const ph = Math.max(7, s * 0.14);
    const plx = lockCenterX - pw / 2;
    const ply = lockTopY;
    ctx.fillStyle = cfg.latchColor;
    ctx.beginPath();
    ctx.moveTo(plx, ply);
    ctx.lineTo(plx + pw, ply);
    ctx.lineTo(plx + pw, ply + ph * 0.6);
    ctx.lineTo(lockCenterX, ply + ph);
    ctx.lineTo(plx, ply + ph * 0.6);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = cfg.bodyDark;
    ctx.lineWidth = 0.8;
    ctx.stroke();
    // Keyhole
    ctx.fillStyle = cfg.bodyDark;
    const khY = ply + ph * 0.35;
    ctx.beginPath();
    ctx.arc(lockCenterX, khY, Math.max(1.2, s * 0.02), 0, Math.PI * 2);
    ctx.fill();
    ctx.fillRect(lockCenterX - s * 0.008, khY, s * 0.016, ph * 0.3);
  } else if (feat.lockStyle === 'ornate') {
    // Gold/Boss: ornate circular lock plate with gem
    const r = Math.max(3.5, s * 0.06);
    ctx.fillStyle = cfg.latchColor;
    ctx.beginPath();
    ctx.arc(lockCenterX, lockTopY + r, r, 0, Math.PI * 2);
    ctx.fill();
    // Ornate ring
    ctx.strokeStyle = cfg.bandColor;
    ctx.lineWidth = Math.max(1.2, s * 0.025);
    ctx.stroke();
    // Inner ring
    ctx.strokeStyle = cfg.bodyHighlight;
    ctx.lineWidth = 0.6;
    ctx.beginPath();
    ctx.arc(lockCenterX, lockTopY + r, r * 0.65, 0, Math.PI * 2);
    ctx.stroke();
    // Gem in center
    if (feat.gem) {
      const gemR = Math.max(1.5, r * 0.4);
      const gemColor = tier === 'boss_chest' ? '#FF3030' : tier === 'obsidian' ? '#C77DFF' : '#50FF50';
      ctx.fillStyle = gemColor;
      ctx.beginPath();
      ctx.arc(lockCenterX, lockTopY + r, gemR, 0, Math.PI * 2);
      ctx.fill();
      // Gem highlight
      ctx.fillStyle = 'rgba(255,255,255,0.5)';
      ctx.beginPath();
      ctx.arc(lockCenterX - gemR * 0.25, lockTopY + r - gemR * 0.25, gemR * 0.35, 0, Math.PI * 2);
      ctx.fill();
    }
  } else if (feat.lockStyle === 'skull') {
    // Obsidian: skull-shaped lock
    const r = Math.max(3.5, s * 0.06);
    const skY = lockTopY + r;
    // Skull circle
    ctx.fillStyle = cfg.latchColor;
    ctx.beginPath();
    ctx.arc(lockCenterX, skY, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = cfg.bodyDark;
    ctx.lineWidth = 0.8;
    ctx.stroke();
    // Eye sockets
    ctx.fillStyle = cfg.bodyDark;
    const eyeR = Math.max(0.8, r * 0.22);
    ctx.beginPath();
    ctx.arc(lockCenterX - r * 0.3, skY - r * 0.1, eyeR, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(lockCenterX + r * 0.3, skY - r * 0.1, eyeR, 0, Math.PI * 2);
    ctx.fill();
    // Jaw line
    ctx.strokeStyle = cfg.bodyDark;
    ctx.lineWidth = 0.6;
    ctx.beginPath();
    ctx.moveTo(lockCenterX - r * 0.3, skY + r * 0.3);
    ctx.lineTo(lockCenterX + r * 0.3, skY + r * 0.3);
    ctx.stroke();
    // Gem in forehead
    if (feat.gem) {
      const gemR = Math.max(1, r * 0.25);
      ctx.fillStyle = '#C77DFF';
      ctx.beginPath();
      ctx.arc(lockCenterX, skY - r * 0.4, gemR, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.4)';
      ctx.beginPath();
      ctx.arc(lockCenterX - gemR * 0.2, skY - r * 0.4 - gemR * 0.2, gemR * 0.3, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

function _drawOpenedChest(ctx, cx, cy, cw, ch, lidH, lidY, s, cfg, feat, tier) {
  const lidOverhang = cw * 0.06;
  const lx = cx - lidOverhang;
  const lw = cw + lidOverhang * 2;
  const domeH = lidH * 0.85;
  const darkened = cfg.bodyDark;

  // ── Body ──
  ctx.fillStyle = cfg.openedColor;
  ctx.fillRect(cx, cy, cw, ch);

  // Wood plank lines (faded)
  if (feat.planks) {
    ctx.globalAlpha = 0.5;
    _drawPlanks(ctx, cx, cy, cw, ch, darkened, 3);
    ctx.globalAlpha = 1.0;
  }

  // Right-edge shadow
  ctx.fillStyle = darkened;
  ctx.fillRect(cx + cw - cw * 0.12, cy, cw * 0.12, ch);
  // Body border
  ctx.strokeStyle = darkened;
  ctx.lineWidth = 1;
  ctx.strokeRect(cx, cy, cw, ch);

  // ── Metal bands (faded) ──
  const bandH = Math.max(2, s * 0.05);
  ctx.fillStyle = cfg.bandColor;
  ctx.globalAlpha = 0.45;
  ctx.fillRect(cx, cy + ch * 0.22, cw, bandH);
  ctx.fillRect(cx, cy + ch * 0.68, cw, bandH);
  ctx.globalAlpha = 1.0;

  // ── Corner brackets (faded) ──
  if (feat.cornerBrackets) {
    ctx.globalAlpha = 0.5;
    _drawCornerBrackets(ctx, cx, cy, cw, ch, cfg.bandColor, cfg.bodyHighlight);
    ctx.globalAlpha = 1.0;
  }

  // ── Interior (visible inside, dark cavity with golden rim) ──
  const interiorH = ch * 0.40;
  // Golden inner rim
  ctx.fillStyle = cfg.latchColor;
  ctx.globalAlpha = 0.25;
  ctx.fillRect(cx + 1, cy, cw - 2, 2);
  ctx.globalAlpha = 1.0;
  // Dark cavity
  ctx.fillStyle = '#08081A';
  ctx.fillRect(cx + 2, cy + 2, cw - 4, interiorH);
  // Gold gleam inside (if not wooden)
  if (tier !== 'wooden') {
    ctx.fillStyle = 'rgba(255, 215, 0, 0.2)';
    ctx.fillRect(cx + 3, cy + 3, cw - 6, interiorH - 2);
    // Sparkle dots (loot glint)
    const sparkles = tier === 'boss_chest' ? 4 : tier === 'obsidian' ? 3 : 2;
    for (let i = 0; i < sparkles; i++) {
      const sx = cx + cw * 0.2 + (cw * 0.6) * (i / sparkles);
      const sy = cy + interiorH * 0.3 + (i % 2) * interiorH * 0.3;
      const sr = Math.max(0.8, s * 0.015);
      const sparkColor = tier === 'obsidian' ? '#D8A0FF' : '#FFE880';
      ctx.fillStyle = sparkColor;
      ctx.beginPath();
      ctx.arc(sx, sy, sr, 0, Math.PI * 2);
      ctx.fill();
      // Tiny white center
      ctx.fillStyle = 'rgba(255,255,255,0.8)';
      ctx.beginPath();
      ctx.arc(sx, sy, sr * 0.4, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // ── Open lid (curved, tilted back behind the chest) ──
  const openLidH = lidH * 0.5;
  const openLidY = lidY - openLidH * 0.2;
  // Foreshortened dome (just the bottom portion visible from this angle)
  ctx.fillStyle = cfg.openedColor;
  ctx.beginPath();
  ctx.moveTo(lx, openLidY + openLidH);
  ctx.lineTo(lx, openLidY + openLidH * 0.4);
  ctx.quadraticCurveTo(lx + lw * 0.5, openLidY - openLidH * 0.2, lx + lw, openLidY + openLidH * 0.4);
  ctx.lineTo(lx + lw, openLidY + openLidH);
  ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = darkened;
  ctx.lineWidth = 1;
  ctx.stroke();
  // Lid inside (dark underside visible)
  ctx.fillStyle = darkened;
  ctx.fillRect(lx + 2, openLidY + openLidH * 0.7, lw - 4, openLidH * 0.3);

  // ── Hinge dots ──
  ctx.fillStyle = cfg.bandColor;
  const hingeR = Math.max(1.2, s * 0.02);
  ctx.beginPath();
  ctx.arc(cx + 2, cy, hingeR, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.arc(cx + cw - 2, cy, hingeR, 0, Math.PI * 2);
  ctx.fill();
}
