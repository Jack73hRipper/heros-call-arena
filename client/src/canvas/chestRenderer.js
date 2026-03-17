/**
 * chestRenderer — Detailed treasure chest drawing for dungeon tiles.
 *
 * Draws a proper barrel-lidded chest with 3D shading, metal bands,
 * a clasp/lock, and tier-based color coding. Supports both unopened
 * and opened states with visual depth.
 */

import { getChestTierConfig } from '../utils/chestUtils.js';

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

  // Chest proportions relative to tile
  const cw = s * 0.58;       // chest width
  const ch = s * 0.42;       // chest body height
  const lidH = s * 0.14;     // lid height
  const cx = px + (s - cw) / 2;             // chest left X
  const cy = py + (s - ch - lidH) / 2 + s * 0.06; // chest top Y (body top, below lid)
  const lidY = cy - lidH;    // lid top Y

  // ── Tier glow (gold, obsidian, boss) ──
  if (cfg.glowColor && !isOpened) {
    ctx.save();
    ctx.shadowColor = cfg.glowColor;
    ctx.shadowBlur = s * 0.25;
    ctx.fillStyle = cfg.glowColor;
    ctx.fillRect(cx - 2, lidY - 2, cw + 4, ch + lidH + 4);
    ctx.restore();
  }

  if (isOpened) {
    _drawOpenedChest(ctx, cx, cy, cw, ch, lidH, lidY, s, cfg);
  } else {
    _drawClosedChest(ctx, cx, cy, cw, ch, lidH, lidY, s, cfg);
  }
}

function _drawClosedChest(ctx, cx, cy, cw, ch, lidH, lidY, s, cfg) {
  // ── Lid (slightly wider than body, rounded top feel) ──
  const lidOverhang = cw * 0.04;
  const lx = cx - lidOverhang;
  const lw = cw + lidOverhang * 2;

  // Lid body
  ctx.fillStyle = cfg.lidColor;
  ctx.fillRect(lx, lidY, lw, lidH);
  // Lid highlight (top edge)
  ctx.fillStyle = cfg.bodyHighlight;
  ctx.fillRect(lx + 1, lidY, lw - 2, 2);
  // Lid border
  ctx.strokeStyle = cfg.bodyDark;
  ctx.lineWidth = 1;
  ctx.strokeRect(lx, lidY, lw, lidH);

  // ── Body ──
  ctx.fillStyle = cfg.bodyColor;
  ctx.fillRect(cx, cy, cw, ch);
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

  // ── Metal bands (2 horizontal straps) ──
  ctx.fillStyle = cfg.bandColor;
  const bandH = Math.max(2, s * 0.04);
  const band1Y = cy + ch * 0.25;
  const band2Y = cy + ch * 0.70;
  ctx.fillRect(cx + 1, band1Y, cw - 2, bandH);
  ctx.fillRect(cx + 1, band2Y, cw - 2, bandH);

  // ── Center latch/lock ──
  const latchW = Math.max(4, s * 0.10);
  const latchH = Math.max(6, s * 0.12);
  const latchX = cx + cw / 2 - latchW / 2;
  const latchY = cy + ch * 0.35;
  ctx.fillStyle = cfg.latchColor;
  ctx.fillRect(latchX, latchY, latchW, latchH);
  ctx.strokeStyle = cfg.bodyDark;
  ctx.lineWidth = 0.5;
  ctx.strokeRect(latchX, latchY, latchW, latchH);
  // Keyhole dot
  ctx.fillStyle = cfg.bodyDark;
  const khR = Math.max(1, s * 0.02);
  ctx.beginPath();
  ctx.arc(latchX + latchW / 2, latchY + latchH * 0.6, khR, 0, Math.PI * 2);
  ctx.fill();

  // ── Lid-to-body seam (dark line at the joint) ──
  ctx.strokeStyle = cfg.bodyDark;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(cx + cw, cy);
  ctx.stroke();
}

function _drawOpenedChest(ctx, cx, cy, cw, ch, lidH, lidY, s, cfg) {
  // ── Body (same as closed but faded) ──
  ctx.fillStyle = cfg.openedColor;
  ctx.fillRect(cx, cy, cw, ch);
  // Right-edge shadow
  const darkened = cfg.bodyDark;
  ctx.fillStyle = darkened;
  ctx.fillRect(cx + cw - cw * 0.12, cy, cw * 0.12, ch);
  // Body border
  ctx.strokeStyle = darkened;
  ctx.lineWidth = 1;
  ctx.strokeRect(cx, cy, cw, ch);

  // ── Metal bands (faded) ──
  ctx.fillStyle = cfg.bandColor;
  ctx.globalAlpha = 0.5;
  const bandH = Math.max(2, s * 0.04);
  ctx.fillRect(cx + 1, cy + ch * 0.25, cw - 2, bandH);
  ctx.fillRect(cx + 1, cy + ch * 0.70, cw - 2, bandH);
  ctx.globalAlpha = 1.0;

  // ── Interior (visible inside, dark cavity) ──
  const interiorH = ch * 0.35;
  ctx.fillStyle = '#0a0a14';
  ctx.fillRect(cx + 2, cy + 1, cw - 4, interiorH);
  // Gold gleam inside (if not wooden)
  if (cfg.latchColor !== cfg.bandColor) {
    ctx.fillStyle = 'rgba(255, 215, 0, 0.15)';
    ctx.fillRect(cx + 3, cy + 2, cw - 6, interiorH - 2);
  }

  // ── Open lid (tilted back behind the chest, as a narrow rectangle) ──
  const lidOverhang = cw * 0.04;
  const lx = cx - lidOverhang;
  const lw = cw + lidOverhang * 2;
  const openLidH = lidH * 0.6; // Foreshortened (viewed at angle)
  const openLidY = lidY - openLidH * 0.3;

  ctx.fillStyle = cfg.openedColor;
  ctx.fillRect(lx, openLidY, lw, openLidH);
  ctx.strokeStyle = darkened;
  ctx.lineWidth = 1;
  ctx.strokeRect(lx, openLidY, lw, openLidH);
  // Hinge dots
  ctx.fillStyle = cfg.bandColor;
  const hingeR = Math.max(1, s * 0.015);
  ctx.beginPath();
  ctx.arc(cx + 2, cy, hingeR, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.arc(cx + cw - 2, cy, hingeR, 0, Math.PI * 2);
  ctx.fill();
}
