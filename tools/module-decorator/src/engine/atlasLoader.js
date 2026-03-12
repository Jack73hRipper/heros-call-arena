// ─────────────────────────────────────────────────────────
// atlasLoader.js — Parse sprite atlas JSON and build searchable index
//
// Loads the mainlevbuild atlas metadata and provides lookup
// utilities for browsing, filtering, and selecting sprites.
// ─────────────────────────────────────────────────────────

/**
 * Parse atlas JSON into a structured sprite index.
 * @param {Object} atlasData - The raw atlas JSON object
 * @returns {Object} Parsed atlas with sprites array, categories, tags index, and dimensions
 */
export function parseAtlas(atlasData) {
  const sprites = [];
  const categories = new Set(atlasData.categories || []);
  const allTags = new Set();
  const groups = {};  // { groupName: [sprite, sprite, ...] }
  const { sheetWidth, sheetHeight, gridDefaults } = atlasData;
  const cellW = gridDefaults?.cellW || 16;
  const cellH = gridDefaults?.cellH || 16;

  // Convert sprites object to array with normalized fields
  if (atlasData.sprites) {
    for (const [name, sprite] of Object.entries(atlasData.sprites)) {
      const tags = sprite.tags || [];
      tags.forEach(t => allTags.add(t));

      const entry = {
        name: name || `sprite_${sprite.row}_${sprite.col}`,
        id: sprite.id,
        x: sprite.x,
        y: sprite.y,
        w: sprite.w || cellW,
        h: sprite.h || cellH,
        category: sprite.category || 'Uncategorized',
        row: sprite.row,
        col: sprite.col,
        tags,
        group: sprite.group || null,
        groupPart: sprite.groupPart || null,
      };

      sprites.push(entry);

      // Track groups for stamp/multi-tile features
      if (sprite.group) {
        if (!groups[sprite.group]) groups[sprite.group] = [];
        groups[sprite.group].push(entry);
      }
    }
  }

  // Sort by category then by position
  sprites.sort((a, b) => {
    if (a.category !== b.category) return a.category.localeCompare(b.category);
    if (a.row !== b.row) return a.row - b.row;
    return a.col - b.col;
  });

  return {
    sheetFile: atlasData.sheetFile,
    sheetWidth,
    sheetHeight,
    cellW,
    cellH,
    categories: Array.from(categories),
    tags: Array.from(allTags).sort(),
    groups,
    sprites,
  };
}

/**
 * Build a grid-based index of all tiles in the atlas sheet.
 * This creates entries for EVERY 16x16 cell in the sheet, even unnamed ones.
 * Named sprites from the atlas get their names, unnamed cells are auto-labeled.
 *
 * @param {Object} parsedAtlas - Output of parseAtlas()
 * @returns {Array} Full grid of tile entries
 */
export function buildFullGrid(parsedAtlas) {
  const { sheetWidth, sheetHeight, cellW, cellH, sprites } = parsedAtlas;
  const cols = Math.floor(sheetWidth / cellW);
  const rows = Math.floor(sheetHeight / cellH);

  // Build lookup by row,col
  const namedLookup = {};
  for (const sprite of sprites) {
    namedLookup[`${sprite.row},${sprite.col}`] = sprite;
  }

  const grid = [];
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const key = `${row},${col}`;
      const named = namedLookup[key];
      grid.push({
        name: named ? named.name : `tile_${row}_${col}`,
        id: named ? named.id : `auto_${row}_${col}`,
        x: col * cellW,
        y: row * cellH,
        w: cellW,
        h: cellH,
        category: named ? named.category : 'Uncategorized',
        row,
        col,
        isNamed: !!named,
        tags: named ? (named.tags || []) : [],
        group: named ? named.group : null,
        groupPart: named ? named.groupPart : null,
      });
    }
  }

  return grid;
}

/**
 * Filter sprites by category.
 * @param {Array} sprites
 * @param {string} category - Category to filter by, or 'All' for everything
 * @returns {Array} Filtered sprites
 */
export function filterByCategory(sprites, category) {
  if (!category || category === 'All') return sprites;
  return sprites.filter(s => s.category === category);
}

/**
 * Filter sprites by search text (matches name).
 * @param {Array} sprites
 * @param {string} searchText
 * @returns {Array} Filtered sprites
 */
export function filterBySearch(sprites, searchText) {
  if (!searchText) return sprites;
  const lower = searchText.toLowerCase();
  return sprites.filter(s => s.name.toLowerCase().includes(lower));
}

/**
 * Filter sprites by tag(s). All specified tags must be present (AND logic).
 * @param {Array} sprites
 * @param {string[]} tags - Tags to filter by
 * @returns {Array} Filtered sprites
 */
export function filterByTags(sprites, tags) {
  if (!tags || tags.length === 0) return sprites;
  return sprites.filter(s => {
    const spriteTags = s.tags || [];
    return tags.every(t => spriteTags.includes(t));
  });
}

/**
 * Filter sprites by group name.
 * @param {Array} sprites
 * @param {string} groupName - Group to filter by
 * @returns {Array} Filtered sprites in group order (top, mid, bot)
 */
export function filterByGroup(sprites, groupName) {
  if (!groupName) return sprites;
  const partOrder = { top: 0, tl: 1, tr: 2, mid: 3, left: 4, right: 5, bl: 6, br: 7, bot: 8 };
  return sprites
    .filter(s => s.group === groupName)
    .sort((a, b) => (partOrder[a.groupPart] ?? 99) - (partOrder[b.groupPart] ?? 99));
}

/**
 * Get a sprite region descriptor suitable for storing in a sprite map.
 * @param {Object} sprite - Sprite entry from the atlas
 * @returns {Object} { x, y, w, h } region descriptor
 */
export function spriteRegion(sprite) {
  return { x: sprite.x, y: sprite.y, w: sprite.w, h: sprite.h };
}
