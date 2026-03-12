/**
 * Export / Import utilities for the Sprite Atlas
 */

/**
 * Export current atlas state to a JSON object suitable for saving.
 */
export function exportAtlasJSON(state) {
  const atlas = {
    version: 1,
    sheetFile: state.sheetFileName,
    sheetWidth: state.sheetWidth,
    sheetHeight: state.sheetHeight,
    gridDefaults: { ...state.grid },
    categories: [...state.categories],
    sprites: {},
    animations: {},
  };

  for (const [id, sprite] of Object.entries(state.sprites)) {
    const entry = {
      id,
      x: sprite.x,
      y: sprite.y,
      w: sprite.w,
      h: sprite.h,
      category: sprite.category,
      row: sprite.row,
      col: sprite.col,
    };
    // Only include tags if non-empty
    if (sprite.tags && sprite.tags.length > 0) {
      entry.tags = [...sprite.tags];
    }
    // Only include group fields if set
    if (sprite.group) {
      entry.group = sprite.group;
      if (sprite.groupPart) {
        entry.groupPart = sprite.groupPart;
      }
    }
    atlas.sprites[sprite.name] = entry;
  }

  for (const [name, anim] of Object.entries(state.animations)) {
    atlas.animations[name] = {
      frames: anim.frames.map(id => {
        const sprite = state.sprites[id];
        return sprite ? sprite.name : id;
      }),
      fps: anim.fps,
      loop: anim.loop,
    };
  }

  return atlas;
}

/**
 * Download a JSON file.
 */
export function downloadJSON(data, filename = 'sprite-atlas.json') {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Import a JSON atlas file and return state updates.
 * The sheet image must be re-loaded separately.
 */
export function parseAtlasJSON(json) {
  const atlas = typeof json === 'string' ? JSON.parse(json) : json;

  const sprites = {};
  let counter = 0;
  const nameToId = {};

  for (const [name, sprite] of Object.entries(atlas.sprites || {})) {
    const id = sprite.id || `imported_${++counter}`;
    sprites[id] = {
      id,
      name,
      x: sprite.x,
      y: sprite.y,
      w: sprite.w,
      h: sprite.h,
      category: sprite.category || 'Uncategorized',
      row: sprite.row,
      col: sprite.col,
      tags: sprite.tags || [],
      group: sprite.group || null,
      groupPart: sprite.groupPart || null,
    };
    nameToId[name] = id;
  }

  const animations = {};
  for (const [name, anim] of Object.entries(atlas.animations || {})) {
    animations[name] = {
      name,
      frames: (anim.frames || []).map(frameName => nameToId[frameName] || frameName),
      fps: anim.fps || 4,
      loop: anim.loop !== undefined ? anim.loop : true,
    };
  }

  return {
    grid: atlas.gridDefaults || { cellW: 32, cellH: 32, offsetX: 0, offsetY: 0, spacingX: 0, spacingY: 0 },
    categories: atlas.categories || ['Uncategorized'],
    sprites,
    animations,
    sheetFileName: atlas.sheetFile || '',
    sheetWidth: atlas.sheetWidth || 0,
    sheetHeight: atlas.sheetHeight || 0,
  };
}

/**
 * Crop a single sprite from a sheet and return as a data URL.
 */
export function cropSprite(img, x, y, w, h, scale = 1) {
  const canvas = document.createElement('canvas');
  canvas.width = w * scale;
  canvas.height = h * scale;
  const ctx = canvas.getContext('2d');
  if (scale !== 1) {
    ctx.imageSmoothingEnabled = false;
  }
  ctx.drawImage(img, x, y, w, h, 0, 0, w * scale, h * scale);
  return canvas.toDataURL('image/png');
}

/**
 * Download a single cropped sprite as a PNG.
 */
export function downloadSpritePNG(img, sprite, scale = 1) {
  const dataUrl = cropSprite(img, sprite.x, sprite.y, sprite.w, sprite.h, scale);
  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = `${sprite.name}.png`;
  a.click();
}
