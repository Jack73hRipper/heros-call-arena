/**
 * minimapRenderer.js — Roguelike minimap rendered on a dedicated DOM canvas.
 *
 * Draws a compact bird's-eye view of the entire map onto its own canvas element,
 * positioned in the right panel of the Arena layout. Shows terrain, FOV state,
 * friendly/enemy unit blips, and a viewport rectangle indicating the currently
 * visible area on the main game canvas.
 *
 * Two modes controlled by the M key:
 *   - Normal  (default, always visible): 5px per tile — compact overview
 *   - Expanded (M key toggle):           tile size scales to fill panel width — detailed view
 *
 * Design choices:
 *   - FOV is respected: unexplored tiles are black, revealed-but-not-visible
 *     tiles are dimmed, and enemies only appear on tiles currently in FOV.
 *   - The player's own position blinks white for easy identification.
 *   - A cyan rectangle outlines the current viewport area.
 *   - Semi-transparent dark background with a 1px border.
 */

import { TILE_SIZE } from './renderConstants.js';

// ---------- Minimap constants ----------

/** Default pixels per tile (normal mode) */
export const MINIMAP_TILE_NORMAL = 7;

/** Expanded pixels per tile (M key enlarged mode) */
export const MINIMAP_TILE_EXPANDED = 14;

/** Panel padding inside the border (px) */
const PANEL_PAD = 0;

// ---------- Tile colors (minimap-specific, simplified) ----------

const TILE_COLORS = {
  wall:     '#2a2a3a',
  floor:    '#1a1a2e',
  corridor: '#151528',
  spawn:    '#1a2a1a',
  door:     '#8B4513',
  doorOpen: '#A0764B',
  chest:    '#DAA520',
  chestOpened: '#8B7355',
  stairs:   '#88CC88',
  portal:   '#00F5D4',
};

// Unit blip colors
const BLIP_SELF       = '#ffffff';  // White (blinks)
const BLIP_ALLY       = '#4a9ff5';  // Blue
const BLIP_ENEMY      = '#f54a4a';  // Red
const BLIP_BOSS       = '#ff2222';  // Brighter red, larger

// Phase 18E (E8): Rarity-based enemy blip colors
const BLIP_CHAMPION   = '#6688ff';  // Blue (champion)
const BLIP_RARE       = '#ffcc00';  // Gold (rare)
const BLIP_SUPER_UNIQUE = '#cc66ff'; // Purple (super unique)

// Phase 27E: PVPVE team blip colors (enemy teams)
const BLIP_TEAM = {
  a: '#4a8fd0',   // Blue
  b: '#e04040',   // Red
  c: '#40c040',   // Green
  d: '#d4a017',   // Yellow
  pve: '#888888',  // Gray for PVE enemies
};

// Viewport rectangle color
const VIEWPORT_COLOR  = 'rgba(196, 151, 58, 0.6)';

// Revealed-but-not-visible dim overlay
const DIM_OVERLAY     = 'rgba(0, 0, 0, 0.55)';
const UNEXPLORED_COLOR = '#000000';

// Arena mode obstacle
const OBSTACLE_COLOR  = '#3a3a4a';
const ARENA_FLOOR     = '#111120';

// ---------- Public API ----------

/**
 * Compute the canvas dimensions needed for the minimap at a given tile size.
 *
 * @param {number} gridWidth  - Map width in tiles
 * @param {number} gridHeight - Map height in tiles
 * @param {number} tileSize   - Pixels per tile (MINIMAP_TILE_NORMAL or MINIMAP_TILE_EXPANDED)
 * @returns {{ width: number, height: number }}
 */
export function getMinimapSize(gridWidth, gridHeight, tileSize) {
  const mapW = gridWidth * tileSize;
  const mapH = gridHeight * tileSize;
  return {
    width: mapW + PANEL_PAD * 2,
    height: mapH + PANEL_PAD * 2,
  };
}

/**
 * Draw the minimap onto a dedicated canvas element.
 *
 * The canvas should be sized to match getMinimapSize(). The minimap draws
 * starting at (0, 0) — positioning is handled by CSS/DOM layout.
 *
 * @param {CanvasRenderingContext2D} ctx - The minimap canvas 2D context.
 * @param {object} opts - All the game state needed for rendering.
 */
export function drawMinimap(ctx, {
  gridWidth, gridHeight,
  isDungeon = false, tiles = null, tileLegend = null,
  doorStates = {}, chestStates = {},
  obstacles = [],
  players = {},
  visibleTiles = null,
  revealedTiles = null,
  myPlayerId = null,
  myTeam = null,
  viewportOffsetX = 0,
  viewportOffsetY = 0,
  canvasPixelW = 0,
  canvasPixelH = 0,
  portal = null,
  currentTurn = 0,
  tileSize = MINIMAP_TILE_NORMAL,
  isPvpve = false,
  bossRoom = null,
}) {
  const MTILE = tileSize;
  const mapW = gridWidth * MTILE;
  const mapH = gridHeight * MTILE;
  const panelW = mapW + PANEL_PAD * 2;
  const panelH = mapH + PANEL_PAD * 2;

  // Clear entire minimap canvas
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);

  // Panel starts at (0, 0) — positioned by DOM
  const panelX = 0;
  const panelY = 0;

  ctx.save();

  // Translate so (0,0) is the top-left of the map area inside the panel
  const mapOriginX = panelX + PANEL_PAD;
  const mapOriginY = panelY + PANEL_PAD;

  // --- Build obstacle set for arena mode ---
  let obstacleSet = null;
  if (!isDungeon && obstacles.length > 0) {
    obstacleSet = new Set(obstacles.map(o => `${o.x},${o.y}`));
  }

  // --- Draw tiles ---
  for (let y = 0; y < gridHeight; y++) {
    for (let x = 0; x < gridWidth; x++) {
      const key = `${x},${y}`;
      const px = mapOriginX + x * MTILE;
      const py = mapOriginY + y * MTILE;

      // Determine FOV state
      const isVisible = !visibleTiles || visibleTiles.has(key);
      const isRevealed = revealedTiles ? revealedTiles.has(key) : true;

      // Unexplored: solid black
      if (!isVisible && !isRevealed) {
        ctx.fillStyle = UNEXPLORED_COLOR;
        ctx.fillRect(px, py, MTILE, MTILE);
        continue;
      }

      // Determine tile color
      let color;
      if (isDungeon && tiles && tileLegend) {
        const tileChar = tiles[y]?.[x];
        const tileType = tileChar ? tileLegend[tileChar] : null;

        if (tileType === 'wall') {
          color = TILE_COLORS.wall;
        } else if (tileType === 'door') {
          const doorState = doorStates[key];
          color = doorState === 'open' ? TILE_COLORS.doorOpen : TILE_COLORS.door;
        } else if (tileType === 'chest') {
          const chestState = chestStates[key];
          color = chestState === 'opened' ? TILE_COLORS.chestOpened : TILE_COLORS.chest;
        } else if (tileType === 'stairs') {
          color = TILE_COLORS.stairs;
        } else if (tileType === 'corridor') {
          color = TILE_COLORS.corridor;
        } else if (tileType === 'spawn') {
          color = TILE_COLORS.spawn;
        } else if (tileType === 'floor') {
          color = TILE_COLORS.floor;
        } else {
          // Unknown tile or null — treat as floor
          color = TILE_COLORS.floor;
        }
      } else {
        // Arena mode
        if (obstacleSet && obstacleSet.has(key)) {
          color = OBSTACLE_COLOR;
        } else {
          color = ARENA_FLOOR;
        }
      }

      ctx.fillStyle = color;
      ctx.fillRect(px, py, MTILE, MTILE);

      // Apply dim overlay for revealed-but-not-visible tiles
      if (!isVisible && isRevealed) {
        ctx.fillStyle = DIM_OVERLAY;
        ctx.fillRect(px, py, MTILE, MTILE);
      }
    }
  }

  // --- Draw portal ---
  if (portal && portal.x != null && portal.y != null) {
    const pk = `${portal.x},${portal.y}`;
    const portalVisible = !visibleTiles || visibleTiles.has(pk);
    const portalRevealed = revealedTiles ? revealedTiles.has(pk) : true;
    if (portalVisible || portalRevealed) {
      const px = mapOriginX + portal.x * MTILE;
      const py = mapOriginY + portal.y * MTILE;
      // Pulsing purple glow
      const pulse = 0.6 + 0.4 * Math.sin((currentTurn * 0.5) + Date.now() * 0.003);
      ctx.fillStyle = `rgba(153, 51, 255, ${pulse})`;
      ctx.fillRect(px, py, MTILE, MTILE);
    }
  }

  // --- Phase 27E: Draw boss room marker for PVPVE ---
  if (isPvpve && bossRoom && bossRoom.bounds) {
    const b = bossRoom.bounds;
    const bx = mapOriginX + b.x_min * MTILE;
    const by = mapOriginY + b.y_min * MTILE;
    const bw = (b.x_max - b.x_min + 1) * MTILE;
    const bh = (b.y_max - b.y_min + 1) * MTILE;
    const pulse = 0.3 + 0.2 * Math.sin(Date.now() * 0.002);
    ctx.strokeStyle = `rgba(255, 50, 50, ${pulse})`;
    ctx.lineWidth = tileSize >= MINIMAP_TILE_EXPANDED ? 2 : 1;
    ctx.strokeRect(bx + 0.5, by + 0.5, bw - 1, bh - 1);
    // Skull indicator at center
    if (tileSize >= MINIMAP_TILE_EXPANDED) {
      const cx = bx + bw / 2;
      const cy = by + bh / 2;
      ctx.fillStyle = `rgba(255, 50, 50, ${pulse + 0.3})`;
      ctx.beginPath();
      ctx.arc(cx, cy, MTILE * 0.8, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // --- Draw unit blips ---
  // Blink timer for self indicator (blinks every ~500ms)
  const blinkOn = Math.floor(Date.now() / 500) % 2 === 0;

  const playerEntries = Object.entries(players);
  for (const [pid, p] of playerEntries) {
    if (!p.position || p.is_alive === false) continue;
    if (p.extracted) continue;

    const ux = p.position.x;
    const uy = p.position.y;
    const unitKey = `${ux},${uy}`;

    // Self is always drawn
    const isSelf = pid === myPlayerId;

    // Other units: only draw if in current FOV
    if (!isSelf && visibleTiles && !visibleTiles.has(unitKey)) continue;

    const px = mapOriginX + ux * MTILE;
    const py = mapOriginY + uy * MTILE;

    if (isSelf) {
      // Player's own unit: blinking white dot
      ctx.fillStyle = blinkOn ? BLIP_SELF : 'rgba(255, 255, 255, 0.4)';
      ctx.fillRect(px, py, MTILE, MTILE);
    } else {
      // Determine friend or foe
      const isAlly = myTeam && p.team === myTeam;
      const isBoss = p.is_boss || false;
      const monsterRarity = p.monster_rarity || null;

      if (isAlly) {
        ctx.fillStyle = BLIP_ALLY;
        ctx.fillRect(px, py, MTILE, MTILE);
      } else if (isPvpve && p.team && BLIP_TEAM[p.team]) {
        // Phase 27E: PVPVE team-colored blips for enemy teams and PVE
        let blipColor = BLIP_TEAM[p.team];
        let blipEnlarge = 0;
        // Still apply rarity enlargement for PVE enemies
        if (p.team === 'pve') {
          if (monsterRarity === 'super_unique' || isBoss) {
            blipEnlarge = MTILE >= 3 ? 2 : 1;
          } else if (monsterRarity === 'rare') {
            blipColor = BLIP_RARE;
            blipEnlarge = MTILE >= 3 ? 1 : 0;
          } else if (monsterRarity === 'champion') {
            blipColor = BLIP_CHAMPION;
          }
        }
        ctx.fillStyle = blipColor;
        if (blipEnlarge > 0) {
          ctx.fillRect(px - blipEnlarge, py - blipEnlarge, MTILE + blipEnlarge * 2, MTILE + blipEnlarge * 2);
        } else {
          ctx.fillRect(px, py, MTILE, MTILE);
        }
      } else {
        // Phase 18E (E8): Rarity-based enemy blip colors + sizes
        let blipColor = BLIP_ENEMY;
        let blipEnlarge = 0; // extra px in each direction
        if (monsterRarity === 'super_unique') {
          blipColor = BLIP_SUPER_UNIQUE;
          blipEnlarge = MTILE >= 3 ? 2 : 1;
        } else if (monsterRarity === 'rare') {
          blipColor = BLIP_RARE;
          blipEnlarge = MTILE >= 3 ? 1 : 0;
        } else if (monsterRarity === 'champion') {
          blipColor = BLIP_CHAMPION;
        } else if (isBoss) {
          blipColor = BLIP_BOSS;
          blipEnlarge = MTILE >= 3 ? 1 : 0;
        }

        ctx.fillStyle = blipColor;
        if (blipEnlarge > 0) {
          ctx.fillRect(px - blipEnlarge, py - blipEnlarge, MTILE + blipEnlarge * 2, MTILE + blipEnlarge * 2);
        } else {
          ctx.fillRect(px, py, MTILE, MTILE);
        }
      }
    }
  }

  // --- Draw viewport rectangle ---
  // Shows which portion of the map is currently visible on the main canvas
  const tilesVisibleX = Math.floor(canvasPixelW / TILE_SIZE);
  const tilesVisibleY = Math.floor(canvasPixelH / TILE_SIZE);

  // Only draw if the map is larger than the viewport
  if (gridWidth > tilesVisibleX || gridHeight > tilesVisibleY) {
    const vpX = mapOriginX + viewportOffsetX * MTILE;
    const vpY = mapOriginY + viewportOffsetY * MTILE;
    const vpW = Math.min(tilesVisibleX, gridWidth) * MTILE;
    const vpH = Math.min(tilesVisibleY, gridHeight) * MTILE;

    ctx.strokeStyle = VIEWPORT_COLOR;
    ctx.lineWidth = tileSize >= MINIMAP_TILE_EXPANDED ? 2 : 1;
    ctx.strokeRect(vpX + 0.5, vpY + 0.5, vpW - 1, vpH - 1);
  }

  ctx.restore();
}
