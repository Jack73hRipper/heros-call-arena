// ─────────────────────────────────────────────────────────
// themeRenderer.js — Theme-aware dungeon tile renderer
//
// Orchestrates procedural tile drawing with an offscreen
// canvas tile cache for performance. Pre-renders tile
// variants on theme load, then blits from cache during
// frame rendering.
//
// Usage:
//   const renderer = new ThemeRenderer();
//   renderer.setTheme(themeConfig);
//   renderer.drawTile(ctx, 'wall', px, py, tileSize, gridX, gridY);
// ─────────────────────────────────────────────────────────

import { getTheme } from './themes.js';
import { cellHash } from './noiseUtils.js';
import {
  WALL_DRAW_MAP,
  FLOOR_DRAW_MAP,
  drawCorridor,
  drawDoor,
  drawChest,
  drawStairs,
  drawSpawn,
} from './tilePatterns.js';

const VARIANTS_PER_TYPE = 8;   // Number of cached variants per tile type
const DEFAULT_TILE_SIZE = 48;

export class ThemeRenderer {
  constructor() {
    this.theme = null;
    this.tileSize = DEFAULT_TILE_SIZE;
    this.cache = new Map();  // key → OffscreenCanvas or regular Canvas
    this._initialized = false;
  }

  /**
   * Set the active theme and rebuild the tile cache.
   * @param {string|Object} themeOrId - Theme ID string or full theme config object
   * @param {number} tileSize - Tile size in pixels (default 48)
   */
  setTheme(themeOrId, tileSize = DEFAULT_TILE_SIZE) {
    this.theme = typeof themeOrId === 'string' ? getTheme(themeOrId) : themeOrId;
    this.tileSize = tileSize;
    this._buildCache();
    this._initialized = true;
  }

  /**
   * Check if a theme is loaded and cache is ready.
   */
  isReady() {
    return this._initialized && this.theme !== null;
  }

  /**
   * Get the current theme config.
   */
  getTheme() {
    return this.theme;
  }

  /**
   * Draw a themed tile at the given pixel position.
   * Uses the tile cache for wall/floor/corridor tiles.
   * Special tiles (door, chest, stairs) are drawn directly.
   *
   * @param {CanvasRenderingContext2D} ctx - Target canvas context
   * @param {string} tileType - 'wall', 'floor', 'corridor', 'door', 'chest', 'stairs', 'spawn'
   * @param {number} px - Destination pixel X
   * @param {number} py - Destination pixel Y
   * @param {number} gridX - Grid X coordinate (for variant selection)
   * @param {number} gridY - Grid Y coordinate (for variant selection)
   * @param {Object} extra - Extra state: { doorOpen, chestOpened }
   */
  drawTile(ctx, tileType, px, py, gridX, gridY, extra = {}) {
    if (!this._initialized) return false;

    const size = this.tileSize;

    switch (tileType) {
      case 'wall': {
        const variant = this._pickVariant(gridX, gridY, 'wall');
        const cached = this.cache.get(variant);
        if (cached) {
          ctx.drawImage(cached, px, py);
          return true;
        }
        break;
      }

      case 'floor': {
        const variant = this._pickVariant(gridX, gridY, 'floor');
        const cached = this.cache.get(variant);
        if (cached) {
          ctx.drawImage(cached, px, py);
          return true;
        }
        break;
      }

      case 'corridor': {
        const variant = this._pickVariant(gridX, gridY, 'corridor');
        const cached = this.cache.get(variant);
        if (cached) {
          ctx.drawImage(cached, px, py);
          return true;
        }
        break;
      }

      case 'spawn': {
        const variant = this._pickVariant(gridX, gridY, 'spawn');
        const cached = this.cache.get(variant);
        if (cached) {
          ctx.drawImage(cached, px, py);
          return true;
        }
        break;
      }

      case 'door': {
        const isOpen = extra.doorOpen === true;
        // Doors are drawn directly (state-dependent)
        drawDoor(ctx, px, py, size, this._tileSeed(gridX, gridY), this.theme.palette, this.theme, isOpen);
        return true;
      }

      case 'chest': {
        const isOpened = extra.chestOpened === true;
        drawChest(ctx, px, py, size, this._tileSeed(gridX, gridY), this.theme.palette, this.theme, isOpened);
        return true;
      }

      case 'stairs': {
        drawStairs(ctx, px, py, size, this._tileSeed(gridX, gridY), this.theme.palette, this.theme);
        return true;
      }

      default: {
        // Unknown tile type → draw as wall
        const variant = this._pickVariant(gridX, gridY, 'wall');
        const cached = this.cache.get(variant);
        if (cached) {
          ctx.drawImage(cached, px, py);
          return true;
        }
        break;
      }
    }

    return false;
  }

  /**
   * Draw full fog of war using theme fog colors.
   * @param {CanvasRenderingContext2D} ctx
   * @param {number} gridWidth
   * @param {number} gridHeight
   * @param {Set} visibleTiles - Set of "x,y" strings currently visible
   * @param {number} offsetX - Camera offset X
   * @param {number} offsetY - Camera offset Y
   * @param {Set|null} revealedTiles - Previously seen tiles (dungeon mode)
   */
  drawFog(ctx, gridWidth, gridHeight, visibleTiles, offsetX, offsetY, revealedTiles) {
    if (!visibleTiles) return;

    const fog = this.theme?.fog || {};
    const exploredTint = fog.exploredTint || 'rgba(0, 0, 0, 0.6)';
    const unexploredColor = fog.unexploredColor || 'rgba(0, 0, 0, 1.0)';

    for (let x = 0; x < gridWidth; x++) {
      for (let y = 0; y < gridHeight; y++) {
        const key = `${x},${y}`;
        if (visibleTiles.has(key)) continue;

        if (revealedTiles && revealedTiles.has(key)) {
          ctx.fillStyle = exploredTint;
        } else if (revealedTiles) {
          ctx.fillStyle = unexploredColor;
        } else {
          ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        }

        ctx.fillRect(
          (x - offsetX) * this.tileSize,
          (y - offsetY) * this.tileSize,
          this.tileSize,
          this.tileSize
        );
      }
    }
  }

  // ─── Internal ──────────────────────────────────────────

  /**
   * Build the offscreen tile cache. Pre-renders N variants
   * of each tile type so frame rendering is just a blit.
   */
  _buildCache() {
    this.cache.clear();
    if (!this.theme) return;

    const size = this.tileSize;
    const palette = this.theme.palette;

    // Cache wall variants
    const wallStyle = this.theme.wall?.style || 'cracked_stone';
    const wallFn = WALL_DRAW_MAP[wallStyle] || WALL_DRAW_MAP.cracked_stone;
    for (let v = 0; v < VARIANTS_PER_TYPE; v++) {
      const canvas = this._createTileCanvas(size);
      const ctx = canvas.getContext('2d');
      wallFn(ctx, 0, 0, size, v * 137, palette, this.theme.wall);
      this.cache.set(`wall_${v}`, canvas);
    }

    // Cache floor variants
    const floorStyle = this.theme.floor?.style || 'flagstone';
    const floorFn = FLOOR_DRAW_MAP[floorStyle] || FLOOR_DRAW_MAP.flagstone;
    for (let v = 0; v < VARIANTS_PER_TYPE; v++) {
      const canvas = this._createTileCanvas(size);
      const ctx = canvas.getContext('2d');
      floorFn(ctx, 0, 0, size, v * 251, palette, this.theme.floor);
      this.cache.set(`floor_${v}`, canvas);
    }

    // Cache corridor variants
    for (let v = 0; v < VARIANTS_PER_TYPE; v++) {
      const canvas = this._createTileCanvas(size);
      const ctx = canvas.getContext('2d');
      drawCorridor(ctx, 0, 0, size, v * 349, palette, this.theme);
      this.cache.set(`corridor_${v}`, canvas);
    }

    // Cache spawn variants (corridor + indicator)
    for (let v = 0; v < VARIANTS_PER_TYPE; v++) {
      const canvas = this._createTileCanvas(size);
      const ctx = canvas.getContext('2d');
      drawSpawn(ctx, 0, 0, size, v * 503, palette, this.theme);
      this.cache.set(`spawn_${v}`, canvas);
    }

    console.log(`[ThemeRenderer] Cache built: ${this.cache.size} tiles for theme "${this.theme.name}"`);
  }

  /**
   * Create a small offscreen canvas for tile caching.
   * Uses OffscreenCanvas where available, falls back to regular Canvas.
   */
  _createTileCanvas(size) {
    if (typeof OffscreenCanvas !== 'undefined') {
      return new OffscreenCanvas(size, size);
    }
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    return canvas;
  }

  /**
   * Pick a variant index for a tile at (gridX, gridY).
   * Returns a cache key like "wall_3".
   */
  _pickVariant(gridX, gridY, tileType) {
    const hash = cellHash(gridX, gridY, 0);
    const variant = Math.floor(hash * VARIANTS_PER_TYPE);
    return `${tileType}_${variant}`;
  }

  /**
   * Get a deterministic seed for a tile at (gridX, gridY).
   */
  _tileSeed(gridX, gridY) {
    return ((gridX * 7919) + (gridY * 6271)) & 0x7FFFFFFF;
  }
}

/**
 * Singleton instance for convenience.
 * Import and use: themeRenderer.setTheme(...); themeRenderer.drawTile(...);
 */
export const themeRenderer = new ThemeRenderer();
