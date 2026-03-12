// ─────────────────────────────────────────────────────────
// spriteMap.js — Data model for per-module sprite assignments
//
// A sprite map stores, for each module, a per-cell assignment
// of base and overlay sprite regions from the atlas.
// This is the core data structure that gets exported for
// the game renderer to consume.
// ─────────────────────────────────────────────────────────

/**
 * Create an empty sprite map for a module.
 * @param {number} width - Module width in tiles (default 6)
 * @param {number} height - Module height in tiles (default 6)
 * @returns {Object} Empty sprite assignment grid
 */
export function createEmptySpriteMap(width = 6, height = 6) {
  const cells = [];
  for (let row = 0; row < height; row++) {
    const rowData = [];
    for (let col = 0; col < width; col++) {
      rowData.push({
        base: null,    // { x, y, w, h } atlas region or null
        overlay: null, // { x, y, w, h } atlas region or null
      });
    }
    cells.push(rowData);
  }
  return { cells };
}

/**
 * Set the base sprite for a specific cell.
 * @param {Object} spriteMap - The sprite map to modify
 * @param {number} row
 * @param {number} col
 * @param {Object|null} region - { x, y, w, h } or null to clear
 */
export function setBaseSprite(spriteMap, row, col, region) {
  if (spriteMap.cells[row] && spriteMap.cells[row][col]) {
    spriteMap.cells[row][col].base = region ? { ...region } : null;
  }
}

/**
 * Set the overlay sprite for a specific cell.
 * @param {Object} spriteMap - The sprite map to modify
 * @param {number} row
 * @param {number} col
 * @param {Object|null} region - { x, y, w, h } or null to clear
 */
export function setOverlaySprite(spriteMap, row, col, region) {
  if (spriteMap.cells[row] && spriteMap.cells[row][col]) {
    spriteMap.cells[row][col].overlay = region ? { ...region } : null;
  }
}

/**
 * Get the sprite assignment for a cell.
 * @param {Object} spriteMap
 * @param {number} row
 * @param {number} col
 * @returns {Object} { base, overlay }
 */
export function getCellSprite(spriteMap, row, col) {
  if (spriteMap.cells[row] && spriteMap.cells[row][col]) {
    return spriteMap.cells[row][col];
  }
  return { base: null, overlay: null };
}

/**
 * Rotate a sprite map 90° clockwise.
 * Used when a module is rotated during WFC assembly.
 * @param {Object} spriteMap
 * @returns {Object} New rotated sprite map
 */
export function rotateSpriteMap90(spriteMap) {
  const { cells } = spriteMap;
  const rows = cells.length;
  const cols = cells[0].length;
  const rotated = [];

  for (let col = 0; col < cols; col++) {
    const newRow = [];
    for (let row = rows - 1; row >= 0; row--) {
      newRow.push({ ...cells[row][col] });
    }
    rotated.push(newRow);
  }

  return { cells: rotated };
}

/**
 * Generate all 4 rotation variants of a sprite map.
 * @param {Object} spriteMap - Original (0°) sprite map
 * @returns {Object[]} Array of 4 sprite maps [0°, 90°, 180°, 270°]
 */
export function generateRotationVariants(spriteMap) {
  const r0 = spriteMap;
  const r90 = rotateSpriteMap90(r0);
  const r180 = rotateSpriteMap90(r90);
  const r270 = rotateSpriteMap90(r180);
  return [r0, r90, r180, r270];
}

/**
 * Check if a sprite map has any assignments (is not entirely empty).
 * @param {Object} spriteMap
 * @returns {boolean}
 */
export function hasAnySprites(spriteMap) {
  for (const row of spriteMap.cells) {
    for (const cell of row) {
      if (cell.base || cell.overlay) return true;
    }
  }
  return false;
}

/**
 * Count the total assigned cells in a sprite map.
 * @param {Object} spriteMap
 * @returns {{ baseCount: number, overlayCount: number }}
 */
export function countAssignments(spriteMap) {
  let baseCount = 0;
  let overlayCount = 0;
  for (const row of spriteMap.cells) {
    for (const cell of row) {
      if (cell.base) baseCount++;
      if (cell.overlay) overlayCount++;
    }
  }
  return { baseCount, overlayCount };
}

/**
 * Serialize a full module sprite library for export.
 * @param {string} atlasFile - Atlas image filename
 * @param {number} tileSize - Source tile size (16)
 * @param {Object} moduleMap - Map of moduleId → spriteMap
 * @returns {Object} Serializable JSON object
 */
export function serializeSpriteLibrary(atlasFile, tileSize, moduleMap) {
  const modules = {};
  for (const [moduleId, spriteMap] of Object.entries(moduleMap)) {
    if (hasAnySprites(spriteMap)) {
      modules[moduleId] = {
        cells: spriteMap.cells.map(row =>
          row.map(cell => ({
            base: cell.base ? { x: cell.base.x, y: cell.base.y, w: cell.base.w, h: cell.base.h } : null,
            overlay: cell.overlay ? { x: cell.overlay.x, y: cell.overlay.y, w: cell.overlay.w, h: cell.overlay.h } : null,
          }))
        ),
      };
    }
  }

  return {
    version: 1,
    atlas: atlasFile,
    tileSize,
    modules,
  };
}

/**
 * Deserialize a sprite library JSON back into working module maps.
 * @param {Object} data - Parsed JSON data
 * @returns {Object} Map of moduleId → spriteMap
 */
export function deserializeSpriteLibrary(data) {
  const moduleMap = {};
  if (data && data.modules) {
    for (const [moduleId, moduleData] of Object.entries(data.modules)) {
      moduleMap[moduleId] = {
        cells: moduleData.cells.map(row =>
          row.map(cell => ({
            base: cell.base ? { ...cell.base } : null,
            overlay: cell.overlay ? { ...cell.overlay } : null,
          }))
        ),
      };
    }
  }
  return moduleMap;
}

/**
 * Deep clone a sprite map.
 * @param {Object} spriteMap
 * @returns {Object}
 */
export function cloneSpriteMap(spriteMap) {
  return {
    cells: spriteMap.cells.map(row =>
      row.map(cell => ({
        base: cell.base ? { ...cell.base } : null,
        overlay: cell.overlay ? { ...cell.overlay } : null,
      }))
    ),
  };
}
