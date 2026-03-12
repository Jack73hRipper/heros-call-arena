/**
 * TileLoader — Loads the environment tile sheet and provides
 * tile drawing utilities for floors, walls, and obstacles.
 *
 * Tile mappings are derived from the cataloged mainlevbuild atlas.
 * Source tiles are 16×16 and get scaled up to TILE_SIZE (40×40).
 */

const TILESHEET_PATH = '/tilesheet.png';

// Tile regions from the atlas (x, y, w, h on the 1024×640 sheet)
// Only includes named/cataloged tiles.

// Floor tile variants — randomly picked per position for visual variety
const FLOOR_TILES = {
  cobble: [
    { x: 736, y: 272, w: 16, h: 16 },  // Floor_Tile_Cobble1
    { x: 752, y: 272, w: 16, h: 16 },  // Floor_Tile_Cobble2
    { x: 736, y: 288, w: 16, h: 16 },  // Floor_Tile_Cobble3
    { x: 752, y: 288, w: 16, h: 16 },  // Floor_Tile_Cobble4
  ],
  smooth: [
    { x: 736, y: 208, w: 16, h: 16 },  // Floor_Tile_Smooth1 (used for corridors/spawn)
    { x: 752, y: 208, w: 16, h: 16 },  // Floor_Tile_Smooth2
    { x: 752, y: 224, w: 16, h: 16 },  // Floor_Tile_Smooth3
    { x: 736, y: 224, w: 16, h: 16 },  // Floor_Tile_Smooth4
    { x: 736, y: 240, w: 16, h: 16 },  // Floor_Tile_Smooth5
    { x: 752, y: 240, w: 16, h: 16 },  // Floor_Tile_Smooth6
  ],
};

// Wall tile variants
const WALL_TILES = {
  brick:  { x: 272, y: 304, w: 16, h: 16 },  // Wall_Brick
  cobble: { x: 80,  y: 368, w: 16, h: 16 },  // Wall_Cobble
  stone:  { x: 384, y: 432, w: 16, h: 16 },  // Wall_Stone
};

let tileImage = null;
let tileLoadPromise = null;
let tileLoaded = false;

// Deterministic pseudo-random per tile position (seeded by coords)
// so the same tile always shows the same variant — no flickering on re-render
function tileVariantIndex(x, y, count) {
  const hash = ((x * 7919) + (y * 6271)) & 0x7FFFFFFF;
  return hash % count;
}

/**
 * Start loading the tile sheet. Safe to call multiple times.
 */
export function loadTileSheet() {
  if (tileLoadPromise) return tileLoadPromise;

  tileLoadPromise = new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      tileImage = img;
      tileLoaded = true;
      console.log('[TileLoader] Tile sheet loaded:', img.width, 'x', img.height);
      resolve(img);
    };
    img.onerror = (err) => {
      console.warn('[TileLoader] Failed to load tile sheet:', err);
      tileLoadPromise = null;
      reject(err);
    };
    img.src = TILESHEET_PATH;
  });

  return tileLoadPromise;
}

/**
 * Returns true if the tile sheet has finished loading.
 */
export function isTileSheetLoaded() {
  return tileLoaded;
}

/**
 * Draw a floor tile at the given pixel position.
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} px - Destination pixel X
 * @param {number} py - Destination pixel Y
 * @param {number} tileSize - Destination width/height
 * @param {number} gridX - Grid X coordinate (for variant seeding)
 * @param {number} gridY - Grid Y coordinate (for variant seeding)
 * @param {'cobble'|'smooth'} style - Floor style
 * @returns {boolean} true if drawn
 */
export function drawFloorTile(ctx, px, py, tileSize, gridX, gridY, style = 'cobble') {
  if (!tileLoaded || !tileImage) return false;

  const variants = FLOOR_TILES[style] || FLOOR_TILES.cobble;
  const idx = tileVariantIndex(gridX, gridY, variants.length);
  const src = variants[idx];

  ctx.drawImage(tileImage, src.x, src.y, src.w, src.h, px, py, tileSize, tileSize);
  return true;
}

/**
 * Draw a wall tile at the given pixel position.
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} px - Destination pixel X
 * @param {number} py - Destination pixel Y
 * @param {number} tileSize - Destination width/height
 * @param {number} gridX - Grid X coordinate (for variant seeding)
 * @param {number} gridY - Grid Y coordinate (for variant seeding)
 * @param {'brick'|'cobble'|'stone'} style - Wall style
 * @returns {boolean} true if drawn
 */
export function drawWallTile(ctx, px, py, tileSize, gridX, gridY, style = 'brick') {
  if (!tileLoaded || !tileImage) return false;

  const src = WALL_TILES[style] || WALL_TILES.brick;
  ctx.drawImage(tileImage, src.x, src.y, src.w, src.h, px, py, tileSize, tileSize);
  return true;
}
