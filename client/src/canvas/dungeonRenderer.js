/**
 * dungeonRenderer — Dungeon tile and fog rendering.
 *
 * Extracted from ArenaRenderer.js (P4 refactoring).
 * Handles drawDungeonTiles (walls, floors, corridors, doors, chests),
 * drawFog (three-state fog of war overlay), and drawPortal (Phase 12C).
 *
 * Rendering priority (first match wins):
 *   1. ThemeEngine  — procedural themed tiles (grimdark style)
 *   2. TileSheet    — sprite-based tiles (TileLoader)
 *   3. DUNGEON_COLORS — flat color fallback
 */

import { TILE_SIZE, DUNGEON_COLORS } from './renderConstants.js';
import { isTileSheetLoaded, drawFloorTile, drawWallTile } from './TileLoader.js';
import { themeEngine } from './ThemeEngine.js';

/**
 * Draw the full dungeon tile grid using the tiles array and tile_legend.
 * Replaces the generic obstacle + grid rendering for dungeon maps.
 */
export function drawDungeonTiles(ctx, tiles, tileLegend, doorStates, chestStates, offsetX = 0, offsetY = 0) {
  if (!tiles || !tileLegend) return;

  const useTheme = themeEngine.isReady();

  for (let y = 0; y < tiles.length; y++) {
    const row = tiles[y];
    for (let x = 0; x < row.length; x++) {
      const ch = row[x];
      const tileType = tileLegend[ch] || 'wall';
      const px = (x - offsetX) * TILE_SIZE;
      const py = (y - offsetY) * TILE_SIZE;
      const doorKey = `${x},${y}`;
      const chestKey = `${x},${y}`;

      // ── ThemeEngine path (procedural grimdark tiles) ──
      if (useTheme) {
        const extra = {};
        if (tileType === 'door') extra.doorOpen = doorStates[doorKey] === 'open';
        if (tileType === 'chest') extra.chestOpened = chestStates[chestKey] === 'opened';
        if (themeEngine.drawTile(ctx, tileType, px, py, x, y, extra)) continue;
      }

      // ── Sprite / flat-color fallback (original rendering) ──
      switch (tileType) {
        case 'wall':
          if (isTileSheetLoaded() && drawWallTile(ctx, px, py, TILE_SIZE, x, y, 'brick')) {
            // Sprite wall drawn
          } else {
            ctx.fillStyle = DUNGEON_COLORS.wall;
            ctx.fillRect(px + 1, py + 1, TILE_SIZE - 2, TILE_SIZE - 2);
            ctx.strokeStyle = DUNGEON_COLORS.wallBorder;
            ctx.lineWidth = 1;
            ctx.strokeRect(px + 1, py + 1, TILE_SIZE - 2, TILE_SIZE - 2);
          }
          break;

        case 'floor':
        case 'spawn': {
          const floorStyle = tileType === 'spawn' ? 'smooth' : 'cobble';
          if (isTileSheetLoaded() && drawFloorTile(ctx, px, py, TILE_SIZE, x, y, floorStyle)) {
            // Sprite floor drawn — add subtle grid line on top
            ctx.strokeStyle = 'rgba(0,0,0,0.15)';
            ctx.lineWidth = 0.5;
            ctx.strokeRect(px, py, TILE_SIZE, TILE_SIZE);
          } else {
            ctx.fillStyle = tileType === 'spawn' ? DUNGEON_COLORS.spawn : DUNGEON_COLORS.floor;
            ctx.fillRect(px, py, TILE_SIZE, TILE_SIZE);
            ctx.strokeStyle = '#222240';
            ctx.lineWidth = 0.5;
            ctx.strokeRect(px, py, TILE_SIZE, TILE_SIZE);
          }
          break;
        }

        case 'corridor':
          if (isTileSheetLoaded() && drawFloorTile(ctx, px, py, TILE_SIZE, x, y, 'smooth')) {
            ctx.strokeStyle = 'rgba(0,0,0,0.15)';
            ctx.lineWidth = 0.5;
            ctx.strokeRect(px, py, TILE_SIZE, TILE_SIZE);
          } else {
            ctx.fillStyle = DUNGEON_COLORS.corridor;
            ctx.fillRect(px, py, TILE_SIZE, TILE_SIZE);
            ctx.strokeStyle = '#1a1a30';
            ctx.lineWidth = 0.5;
            ctx.strokeRect(px, py, TILE_SIZE, TILE_SIZE);
          }
          break;

        case 'door': {
          const isOpen = doorStates[doorKey] === 'open';
          // Floor background — use tile sprite if available
          if (isTileSheetLoaded()) {
            drawFloorTile(ctx, px, py, TILE_SIZE, x, y, 'cobble');
          } else {
            ctx.fillStyle = isOpen ? DUNGEON_COLORS.doorOpenBg : DUNGEON_COLORS.floor;
            ctx.fillRect(px, py, TILE_SIZE, TILE_SIZE);
          }

          if (isOpen) {
            // Open door — brown outline only
            ctx.strokeStyle = DUNGEON_COLORS.doorOpen;
            ctx.lineWidth = 2;
            ctx.strokeRect(px + 4, py + 4, TILE_SIZE - 8, TILE_SIZE - 8);
            // Small "open" indicator
            ctx.fillStyle = DUNGEON_COLORS.doorOpen;
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('○', px + TILE_SIZE / 2, py + TILE_SIZE / 2 + 4);
          } else {
            // Closed door — solid brown square
            ctx.fillStyle = DUNGEON_COLORS.doorClosed;
            ctx.fillRect(px + 4, py + 4, TILE_SIZE - 8, TILE_SIZE - 8);
            ctx.strokeStyle = '#5C3310';
            ctx.lineWidth = 1;
            ctx.strokeRect(px + 4, py + 4, TILE_SIZE - 8, TILE_SIZE - 8);
            // Door handle
            ctx.fillStyle = '#DAA520';
            ctx.beginPath();
            ctx.arc(px + TILE_SIZE / 2 + 6, py + TILE_SIZE / 2, 2, 0, Math.PI * 2);
            ctx.fill();
          }
          break;
        }

        case 'chest': {
          // Floor background — use tile sprite if available
          if (isTileSheetLoaded()) {
            drawFloorTile(ctx, px, py, TILE_SIZE, x, y, 'cobble');
          } else {
            ctx.fillStyle = DUNGEON_COLORS.floor;
            ctx.fillRect(px, py, TILE_SIZE, TILE_SIZE);
            ctx.strokeStyle = '#222240';
            ctx.lineWidth = 0.5;
            ctx.strokeRect(px, py, TILE_SIZE, TILE_SIZE);
          }

          const isOpened = chestStates[chestKey] === 'opened';
          const chestColor = isOpened ? DUNGEON_COLORS.chestOpened : DUNGEON_COLORS.chest;

          // Chest icon — small box
          const cw = TILE_SIZE * 0.5;
          const ch2 = TILE_SIZE * 0.4;
          const cx = px + (TILE_SIZE - cw) / 2;
          const cy = py + (TILE_SIZE - ch2) / 2;

          ctx.fillStyle = chestColor;
          ctx.fillRect(cx, cy, cw, ch2);
          ctx.strokeStyle = '#333';
          ctx.lineWidth = 1;
          ctx.strokeRect(cx, cy, cw, ch2);

          // Latch/clasp
          if (!isOpened) {
            ctx.fillStyle = '#FFD700';
            ctx.fillRect(cx + cw / 2 - 3, cy + ch2 / 2 - 2, 6, 4);
          } else {
            // Open chest — lid line
            ctx.strokeStyle = chestColor;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(cx, cy);
            ctx.lineTo(cx + cw, cy);
            ctx.stroke();
          }
          break;
        }

        case 'stairs': {
          // Floor background
          if (isTileSheetLoaded()) {
            drawFloorTile(ctx, px, py, TILE_SIZE, x, y, 'smooth');
          } else {
            ctx.fillStyle = DUNGEON_COLORS.stairs || '#2a3a2a';
            ctx.fillRect(px, py, TILE_SIZE, TILE_SIZE);
          }
          // Stairs icon — descending steps
          const stairColor = DUNGEON_COLORS.stairsIcon || '#88CC88';
          const borderColor = DUNGEON_COLORS.stairsBorder || '#66AA66';
          const stepW = TILE_SIZE * 0.55;
          const stepH = TILE_SIZE * 0.12;
          const stairX = px + (TILE_SIZE - stepW) / 2;
          for (let s = 0; s < 3; s++) {
            const sy = py + TILE_SIZE * 0.22 + s * (stepH + 2);
            const sw = stepW - s * 4;
            const sx = stairX + s * 2;
            ctx.fillStyle = stairColor;
            ctx.fillRect(sx, sy, sw, stepH);
            ctx.strokeStyle = borderColor;
            ctx.lineWidth = 1;
            ctx.strokeRect(sx, sy, sw, stepH);
          }
          // Down-arrow indicator
          ctx.fillStyle = stairColor;
          ctx.font = `${TILE_SIZE * 0.3}px sans-serif`;
          ctx.textAlign = 'center';
          ctx.fillText('▼', px + TILE_SIZE / 2, py + TILE_SIZE - 3);
          break;
        }

        default:
          if (isTileSheetLoaded() && drawWallTile(ctx, px, py, TILE_SIZE, x, y, 'brick')) {
            // Sprite wall fallback drawn
          } else {
            ctx.fillStyle = DUNGEON_COLORS.wall;
            ctx.fillRect(px + 1, py + 1, TILE_SIZE - 2, TILE_SIZE - 2);
          }
          break;
      }
    }
  }
}

/**
 * Draw fog of war overlay on tiles outside the player's FOV.
 * Supports three fog states for dungeon exploration:
 *   - Visible (in current FOV): no fog overlay
 *   - Revealed (previously seen but not in FOV): dimmed overlay
 *   - Unexplored (never seen): fully black
 *
 * For arena maps (no revealedTiles), all non-visible tiles get the same dim fog.
 */
export function drawFog(ctx, gridWidth, gridHeight, visibleTiles, offsetX = 0, offsetY = 0, revealedTiles = null) {
  if (!visibleTiles) return; // No FOV data = show everything

  // Use theme fog colors when available
  if (themeEngine.isReady()) {
    themeEngine.drawFog(ctx, gridWidth, gridHeight, visibleTiles, offsetX, offsetY, revealedTiles);
    return;
  }

  for (let x = 0; x < gridWidth; x++) {
    for (let y = 0; y < gridHeight; y++) {
      const key = `${x},${y}`;
      if (visibleTiles.has(key)) continue; // Currently visible — no fog

      if (revealedTiles && revealedTiles.has(key)) {
        // Previously seen — dim fog (can still see terrain layout)
        ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
      } else if (revealedTiles) {
        // Never seen — fully black (unexplored)
        ctx.fillStyle = 'rgba(0, 0, 0, 1.0)';
      } else {
        // Arena mode (no revealed tracking) — standard fog
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      }

      ctx.fillRect((x - offsetX) * TILE_SIZE, (y - offsetY) * TILE_SIZE, TILE_SIZE, TILE_SIZE);
    }
  }
}

/**
 * Phase 12C: Draw the portal entity on the dungeon map.
 * Renders an animated glowing purple portal ring with a turn counter.
 * @param {CanvasRenderingContext2D} ctx
 * @param {object} portal - { active, x, y, turns_remaining, owner_id }
 * @param {number} turnNumber - current turn for animation phase
 * @param {number} offsetX - camera offset X
 * @param {number} offsetY - camera offset Y
 */
// Module-level animation clock for portal (frame-rate independent)
let _portalAnimTime = 0;
let _portalLastFrame = 0;

export function drawPortal(ctx, portal, turnNumber, offsetX = 0, offsetY = 0) {
  if (!portal || !portal.active) return;

  // Advance animation clock
  const now = performance.now() / 1000;
  if (_portalLastFrame > 0) {
    _portalAnimTime += Math.min(now - _portalLastFrame, 0.1); // cap dt
  }
  _portalLastFrame = now;

  const t = _portalAnimTime;
  const px = (portal.x - offsetX) * TILE_SIZE;
  const py = (portal.y - offsetY) * TILE_SIZE;
  const cx = px + TILE_SIZE / 2;
  const cy = py + TILE_SIZE / 2;

  // ── 1. Deep ambient glow (purple, slow pulse) ──
  const ambientPulse = 0.55 + 0.15 * Math.sin(t * 1.2);
  const ambientR = TILE_SIZE * 0.55 + Math.sin(t * 0.9) * 4;
  const glow1 = ctx.createRadialGradient(cx, cy, 0, cx, cy, ambientR);
  glow1.addColorStop(0, `rgba(90, 24, 154, ${ambientPulse * 0.5})`);
  glow1.addColorStop(0.4, `rgba(123, 47, 190, ${ambientPulse * 0.3})`);
  glow1.addColorStop(0.7, `rgba(60, 9, 108, ${ambientPulse * 0.15})`);
  glow1.addColorStop(1, 'rgba(36, 0, 70, 0)');
  ctx.fillStyle = glow1;
  ctx.beginPath();
  ctx.arc(cx, cy, ambientR, 0, Math.PI * 2);
  ctx.fill();

  // ── 2. Turquoise core glow (bright center, fast pulse) ──
  const corePulse = 0.6 + 0.25 * Math.sin(t * 2.8);
  const coreR = TILE_SIZE * 0.22 + Math.sin(t * 3.5) * 2;
  const glow2 = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR);
  glow2.addColorStop(0, `rgba(0, 245, 212, ${corePulse})`);
  glow2.addColorStop(0.35, `rgba(0, 187, 212, ${corePulse * 0.6})`);
  glow2.addColorStop(0.7, `rgba(157, 78, 221, ${corePulse * 0.25})`);
  glow2.addColorStop(1, 'rgba(123, 47, 190, 0)');
  ctx.fillStyle = glow2;
  ctx.beginPath();
  ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
  ctx.fill();

  // ── 3. Outer spinning ring (turquoise arc segments) ──
  const ringR = TILE_SIZE * 0.32;
  const spinAngle = t * 1.5; // radians per second
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(spinAngle);
  ctx.lineWidth = 2.5;
  ctx.lineCap = 'round';
  // Draw 3 arc segments with varying opacity
  for (let i = 0; i < 3; i++) {
    const segStart = (i * Math.PI * 2) / 3;
    const segEnd = segStart + Math.PI * 0.55;
    const segAlpha = 0.5 + 0.3 * Math.sin(t * 2 + i * 2);
    ctx.strokeStyle = `rgba(0, 245, 212, ${segAlpha})`;
    ctx.beginPath();
    ctx.arc(0, 0, ringR, segStart, segEnd);
    ctx.stroke();
  }
  ctx.restore();

  // ── 4. Inner spinning ring (purple, opposite direction) ──
  const innerR = TILE_SIZE * 0.2;
  const innerSpin = -t * 2.2;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(innerSpin);
  ctx.lineWidth = 1.8;
  ctx.lineCap = 'round';
  for (let i = 0; i < 4; i++) {
    const segStart = (i * Math.PI * 2) / 4;
    const segEnd = segStart + Math.PI * 0.35;
    const segAlpha = 0.4 + 0.25 * Math.sin(t * 3 + i * 1.5);
    ctx.strokeStyle = `rgba(199, 125, 255, ${segAlpha})`;
    ctx.beginPath();
    ctx.arc(0, 0, innerR, segStart, segEnd);
    ctx.stroke();
  }
  ctx.restore();

  // ── 5. Bright center dot (white→turquoise) ──
  const dotR = 2.5 + Math.sin(t * 4) * 1;
  const dotGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, dotR);
  dotGrad.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
  dotGrad.addColorStop(0.5, 'rgba(192, 255, 244, 0.7)');
  dotGrad.addColorStop(1, 'rgba(0, 245, 212, 0)');
  ctx.fillStyle = dotGrad;
  ctx.beginPath();
  ctx.arc(cx, cy, dotR, 0, Math.PI * 2);
  ctx.fill();

  // ── 6. Orbiting motes (small bright dots circling the portal) ──
  const moteCount = 5;
  const moteOrbitR = TILE_SIZE * 0.27;
  for (let i = 0; i < moteCount; i++) {
    const moteAngle = t * 1.8 + (i * Math.PI * 2) / moteCount;
    const moteWobble = Math.sin(t * 3.5 + i * 1.7) * 3;
    const mx = cx + Math.cos(moteAngle) * (moteOrbitR + moteWobble);
    const my = cy + Math.sin(moteAngle) * (moteOrbitR + moteWobble);
    const moteAlpha = 0.4 + 0.4 * Math.sin(t * 4 + i * 2.3);
    const moteSize = 1.2 + Math.sin(t * 5 + i) * 0.5;
    // Alternate turquoise and purple motes
    if (i % 2 === 0) {
      ctx.fillStyle = `rgba(0, 245, 212, ${moteAlpha})`;
    } else {
      ctx.fillStyle = `rgba(199, 125, 255, ${moteAlpha})`;
    }
    ctx.beginPath();
    ctx.arc(mx, my, moteSize, 0, Math.PI * 2);
    ctx.fill();
  }

  // ── 7. Turn counter ──
  ctx.fillStyle = DUNGEON_COLORS.portalText;
  ctx.font = 'bold 10px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.fillText(`${portal.turns_remaining}`, cx, py + TILE_SIZE - 12);
}

/**
 * Phase 12C: Draw channeling indicator above the caster.
 * Shows a small progress bar + swirl hint on the casting hero.
 * @param {CanvasRenderingContext2D} ctx
 * @param {object} channeling - { player_id, turns_remaining, tile_x, tile_y }
 * @param {object} players - players snapshot to locate the caster
 * @param {number} offsetX
 * @param {number} offsetY
 */
export function drawChanneling(ctx, channeling, players, offsetX = 0, offsetY = 0) {
  if (!channeling) return;

  const caster = players?.[channeling.player_id];
  if (!caster) return;

  const px = (caster.position.x - offsetX) * TILE_SIZE;
  const py = (caster.position.y - offsetY) * TILE_SIZE;
  const cx = px + TILE_SIZE / 2;

  // Channel bar background
  const barWidth = TILE_SIZE * 0.7;
  const barHeight = 4;
  const barX = cx - barWidth / 2;
  const barY = py - 8;

  ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
  ctx.fillRect(barX - 1, barY - 1, barWidth + 2, barHeight + 2);

  // Channel bar fill (3 turns total, decreasing = more filled)
  const totalTurns = 3;
  const elapsed = totalTurns - channeling.turns_remaining;
  const progress = elapsed / totalTurns;

  ctx.fillStyle = DUNGEON_COLORS.portalGlow;
  ctx.fillRect(barX, barY, barWidth * progress, barHeight);

  // Border
  ctx.strokeStyle = DUNGEON_COLORS.portalCore;
  ctx.lineWidth = 0.5;
  ctx.strokeRect(barX, barY, barWidth, barHeight);
}
