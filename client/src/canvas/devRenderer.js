/**
 * devRenderer.js — Canvas rendering functions for the developer overlay.
 *
 * Drawn AFTER the normal renderFrame() to add debug visualizations
 * on top of the game view. All functions are pure canvas drawing operations.
 */
import { TILE_SIZE } from './renderConstants.js';

// Room bound colors — cycle through these for different rooms
const ROOM_COLORS = [
  'rgba(255, 100, 100, 0.15)',
  'rgba(100, 255, 100, 0.15)',
  'rgba(100, 100, 255, 0.15)',
  'rgba(255, 255, 100, 0.15)',
  'rgba(255, 100, 255, 0.15)',
  'rgba(100, 255, 255, 0.15)',
  'rgba(255, 180, 100, 0.15)',
  'rgba(180, 100, 255, 0.15)',
];

const ROOM_BORDER_COLORS = [
  'rgba(255, 100, 100, 0.7)',
  'rgba(100, 255, 100, 0.7)',
  'rgba(100, 100, 255, 0.7)',
  'rgba(255, 255, 100, 0.7)',
  'rgba(255, 100, 255, 0.7)',
  'rgba(100, 255, 255, 0.7)',
  'rgba(255, 180, 100, 0.7)',
  'rgba(180, 100, 255, 0.7)',
];

/**
 * Draw tile coordinates on each visible tile.
 */
export function drawDevGridCoords(ctx, gridWidth, gridHeight, offsetX, offsetY) {
  const canvasW = ctx.canvas.width;
  const canvasH = ctx.canvas.height;
  const tilesX = Math.ceil(canvasW / TILE_SIZE);
  const tilesY = Math.ceil(canvasH / TILE_SIZE);
  const startX = Math.floor(offsetX);
  const startY = Math.floor(offsetY);
  const endX = Math.min(gridWidth, startX + tilesX + 1);
  const endY = Math.min(gridHeight, startY + tilesY + 1);

  ctx.save();
  ctx.font = '9px monospace';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'bottom';

  for (let x = startX; x < endX; x++) {
    for (let y = startY; y < endY; y++) {
      const px = (x - offsetX) * TILE_SIZE + TILE_SIZE / 2;
      const py = (y - offsetY) * TILE_SIZE + TILE_SIZE;
      const text = `${x},${y}`;
      const metrics = ctx.measureText(text);

      // Background pill for readability
      ctx.fillStyle = 'rgba(0, 0, 0, 0.55)';
      ctx.fillRect(
        px - metrics.width / 2 - 2,
        py - 10,
        metrics.width + 4,
        11
      );

      ctx.fillStyle = 'rgba(180, 180, 200, 0.75)';
      ctx.fillText(text, px, py - 1);
    }
  }
  ctx.restore();
}

/**
 * Draw room boundaries with archetype labels.
 */
export function drawDevRoomBounds(ctx, rooms, offsetX, offsetY) {
  if (!rooms || rooms.length === 0) return;

  ctx.save();
  rooms.forEach((room, i) => {
    if (!room.bounds) return;
    const { x_min, y_min, x_max, y_max } = room.bounds;
    const color = ROOM_COLORS[i % ROOM_COLORS.length];
    const borderColor = ROOM_BORDER_COLORS[i % ROOM_BORDER_COLORS.length];

    const px = (x_min - offsetX) * TILE_SIZE;
    const py = (y_min - offsetY) * TILE_SIZE;
    const w = (x_max - x_min + 1) * TILE_SIZE;
    const h = (y_max - y_min + 1) * TILE_SIZE;

    // Fill
    ctx.fillStyle = color;
    ctx.fillRect(px, py, w, h);

    // Dashed border
    ctx.strokeStyle = borderColor;
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.strokeRect(px + 1, py + 1, w - 2, h - 2);
    ctx.setLineDash([]);

    // Archetype label in top-left corner
    if (room.archetype) {
      ctx.font = 'bold 10px monospace';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      const label = `R${i}: ${room.archetype}`;
      const metrics = ctx.measureText(label);

      ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
      ctx.fillRect(px + 3, py + 3, metrics.width + 8, 15);
      ctx.fillStyle = borderColor;
      ctx.fillText(label, px + 7, py + 5);
    }
  });
  ctx.restore();
}

/**
 * Highlight spawn point tiles.
 */
export function drawDevSpawnMarkers(ctx, tiles, tileLegend, offsetX, offsetY) {
  if (!tiles || !tileLegend) return;

  const spawnTypes = new Set(['spawn', 'player_spawn', 'enemy_spawn']);

  ctx.save();
  for (let y = 0; y < tiles.length; y++) {
    for (let x = 0; x < (tiles[y]?.length || 0); x++) {
      const tileChar = tiles[y][x];
      const tileType = tileLegend[tileChar];
      if (!tileType || !spawnTypes.has(tileType)) continue;

      const px = (x - offsetX) * TILE_SIZE;
      const py = (y - offsetY) * TILE_SIZE;

      // Yellow highlight
      ctx.fillStyle = 'rgba(255, 215, 0, 0.2)';
      ctx.fillRect(px, py, TILE_SIZE, TILE_SIZE);

      // Border
      ctx.strokeStyle = 'rgba(255, 215, 0, 0.5)';
      ctx.lineWidth = 1.5;
      ctx.strokeRect(px + 1, py + 1, TILE_SIZE - 2, TILE_SIZE - 2);

      // "S" marker
      ctx.font = 'bold 10px monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = 'rgba(255, 215, 0, 0.8)';
      ctx.fillText('S', px + TILE_SIZE / 2, py + TILE_SIZE / 2);
    }
  }
  ctx.restore();
}

/**
 * Draw enhanced dev unit labels above all units (type, rarity, ID).
 */
export function drawDevUnitLabels(ctx, players, offsetX, offsetY, myPlayerId) {
  if (!players) return;

  ctx.save();
  ctx.font = '8px monospace';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'bottom';

  for (const [pid, p] of Object.entries(players)) {
    if (p.is_alive === false || p.extracted) continue;
    if (!p.position) continue;

    const px = (p.position.x - offsetX) * TILE_SIZE + TILE_SIZE / 2;
    const py = (p.position.y - offsetY) * TILE_SIZE - 2;

    // Determine type label
    let typeLabel = '';
    let labelColor = '#aaa';
    if (p.is_boss) {
      typeLabel = 'BOSS';
      labelColor = '#ff4444';
    } else if (p.monster_rarity === 'super_unique') {
      typeLabel = 'S.UNIQUE';
      labelColor = '#ff66ff';
    } else if (p.monster_rarity === 'rare') {
      typeLabel = 'RARE';
      labelColor = '#ffaa00';
    } else if (p.monster_rarity === 'champion') {
      typeLabel = 'CHAMP';
      labelColor = '#44aaff';
    } else if (p.unit_type === 'enemy') {
      typeLabel = 'MOB';
      labelColor = '#ff6666';
    } else if (pid === myPlayerId) {
      typeLabel = 'YOU';
      labelColor = '#66ff66';
    } else {
      typeLabel = 'ALLY';
      labelColor = '#6666ff';
    }

    const metrics = ctx.measureText(typeLabel);
    ctx.fillStyle = 'rgba(0, 0, 0, 0.65)';
    ctx.fillRect(px - metrics.width / 2 - 2, py - 10, metrics.width + 4, 10);
    ctx.fillStyle = labelColor;
    ctx.fillText(typeLabel, px, py - 1);
  }
  ctx.restore();
}
