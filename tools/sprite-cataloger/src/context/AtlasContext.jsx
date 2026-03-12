import React, { createContext, useContext, useReducer, useCallback } from 'react';

// ─── Initial State ────────────────────────────────────────────────
const initialState = {
  // Sheet image
  sheetSrc: null,       // data URL of loaded image
  sheetWidth: 0,
  sheetHeight: 0,
  sheetFileName: '',

  // Grid settings
  grid: {
    cellW: 32,
    cellH: 32,
    offsetX: 0,
    offsetY: 0,
    spacingX: 0,
    spacingY: 0,
  },

  // Cataloged sprites: { [id]: { id, name, category, x, y, w, h, row, col, tags, group, groupPart } }
  sprites: {},

  // Categories: string[] — dungeon tileset taxonomy
  categories: [
    'Floor_Stone', 'Floor_Dirt', 'Floor_Special',
    'Wall_Face', 'Wall_Top', 'Wall_Edge', 'Wall_Accent',
    'Door', 'Stair',
    'Deco_Wall', 'Deco_Floor',
    'Furniture', 'Container', 'Column',
    'Water', 'Vegetation',
    'Character', 'Monster', 'Effect', 'UI',
    'Uncategorized',
  ],

  // Last-used category for smart auto-naming
  lastUsedCategory: null,

  // Selection
  selectedSpriteId: null,
  hoveredCell: null,      // { row, col }
  multiSelect: [],        // array of sprite ids

  // Animations: { [name]: { name, frames: string[], fps: number, loop: boolean } }
  animations: {},

  // Canvas view
  zoom: 1,
  panX: 0,
  panY: 0,

  // Undo stack (simple: store last N states)
  history: [],
  historyIndex: -1,
};

// ─── Action Types ─────────────────────────────────────────────────
const Actions = {
  SET_SHEET: 'SET_SHEET',
  UPDATE_GRID: 'UPDATE_GRID',
  ADD_SPRITE: 'ADD_SPRITE',
  UPDATE_SPRITE: 'UPDATE_SPRITE',
  DELETE_SPRITE: 'DELETE_SPRITE',
  SELECT_SPRITE: 'SELECT_SPRITE',
  SET_HOVERED_CELL: 'SET_HOVERED_CELL',
  TOGGLE_MULTI_SELECT: 'TOGGLE_MULTI_SELECT',
  CLEAR_SELECTION: 'CLEAR_SELECTION',
  ADD_CATEGORY: 'ADD_CATEGORY',
  RENAME_CATEGORY: 'RENAME_CATEGORY',
  DELETE_CATEGORY: 'DELETE_CATEGORY',
  ADD_ANIMATION: 'ADD_ANIMATION',
  UPDATE_ANIMATION: 'UPDATE_ANIMATION',
  DELETE_ANIMATION: 'DELETE_ANIMATION',
  SET_ZOOM: 'SET_ZOOM',
  SET_PAN: 'SET_PAN',
  IMPORT_ATLAS: 'IMPORT_ATLAS',
  BATCH_ASSIGN_CATEGORY: 'BATCH_ASSIGN_CATEGORY',
  BATCH_NAME_PREFIX: 'BATCH_NAME_PREFIX',
  DELETE_ALL_SPRITES: 'DELETE_ALL_SPRITES',
  SET_LAST_USED_CATEGORY: 'SET_LAST_USED_CATEGORY',
  BATCH_ASSIGN_TAGS: 'BATCH_ASSIGN_TAGS',
  BATCH_ASSIGN_GROUP: 'BATCH_ASSIGN_GROUP',
};

// ─── Helpers ──────────────────────────────────────────────────────
let spriteCounter = 0;
function genId() {
  return `sprite_${++spriteCounter}_${Date.now()}`;
}

// ─── Reducer ──────────────────────────────────────────────────────
function atlasReducer(state, action) {
  switch (action.type) {

    case Actions.SET_SHEET:
      return {
        ...state,
        sheetSrc: action.payload.src,
        sheetWidth: action.payload.width,
        sheetHeight: action.payload.height,
        sheetFileName: action.payload.fileName,
        sprites: {},
        selectedSpriteId: null,
        multiSelect: [],
        zoom: 1,
        panX: 0,
        panY: 0,
      };

    case Actions.UPDATE_GRID:
      return {
        ...state,
        grid: { ...state.grid, ...action.payload },
      };

    case Actions.ADD_SPRITE: {
      const id = genId();
      // Smart auto-name: if lastUsedCategory is set, suggest category-based name
      let autoName = action.payload.name;
      if (!autoName) {
        const cat = action.payload.category || state.lastUsedCategory || 'Uncategorized';
        if (cat && cat !== 'Uncategorized') {
          // Count existing sprites in this category to get next number
          const catCount = Object.values(state.sprites).filter(s => s.category === cat).length;
          autoName = `${cat}_${catCount + 1}`;
        } else {
          autoName = `sprite_${Object.keys(state.sprites).length + 1}`;
        }
      }
      const sprite = {
        id,
        name: autoName,
        category: action.payload.category || state.lastUsedCategory || 'Uncategorized',
        x: action.payload.x,
        y: action.payload.y,
        w: action.payload.w || state.grid.cellW,
        h: action.payload.h || state.grid.cellH,
        row: action.payload.row,
        col: action.payload.col,
        tags: action.payload.tags || [],
        group: action.payload.group || null,
        groupPart: action.payload.groupPart || null,
      };
      return {
        ...state,
        sprites: { ...state.sprites, [id]: sprite },
        selectedSpriteId: id,
      };
    }

    case Actions.UPDATE_SPRITE: {
      const { id, ...updates } = action.payload;
      if (!state.sprites[id]) return state;
      return {
        ...state,
        sprites: {
          ...state.sprites,
          [id]: { ...state.sprites[id], ...updates },
        },
      };
    }

    case Actions.DELETE_SPRITE: {
      const { [action.payload]: _, ...rest } = state.sprites;
      return {
        ...state,
        sprites: rest,
        selectedSpriteId: state.selectedSpriteId === action.payload ? null : state.selectedSpriteId,
        multiSelect: state.multiSelect.filter(id => id !== action.payload),
      };
    }

    case Actions.SELECT_SPRITE:
      return { ...state, selectedSpriteId: action.payload };

    case Actions.SET_HOVERED_CELL:
      return { ...state, hoveredCell: action.payload };

    case Actions.TOGGLE_MULTI_SELECT: {
      const id = action.payload;
      const idx = state.multiSelect.indexOf(id);
      const next = idx >= 0
        ? state.multiSelect.filter(i => i !== id)
        : [...state.multiSelect, id];
      return { ...state, multiSelect: next, selectedSpriteId: id };
    }

    case Actions.CLEAR_SELECTION:
      return { ...state, selectedSpriteId: null, multiSelect: [] };

    case Actions.ADD_CATEGORY:
      if (state.categories.includes(action.payload)) return state;
      return { ...state, categories: [...state.categories, action.payload] };

    case Actions.RENAME_CATEGORY: {
      const { oldName, newName } = action.payload;
      if (state.categories.includes(newName)) return state;
      const cats = state.categories.map(c => c === oldName ? newName : c);
      const sprites = { ...state.sprites };
      for (const id in sprites) {
        if (sprites[id].category === oldName) {
          sprites[id] = { ...sprites[id], category: newName };
        }
      }
      return { ...state, categories: cats, sprites };
    }

    case Actions.DELETE_CATEGORY: {
      const catName = action.payload;
      if (catName === 'Uncategorized') return state; // protect default
      const cats = state.categories.filter(c => c !== catName);
      const sprites = { ...state.sprites };
      for (const id in sprites) {
        if (sprites[id].category === catName) {
          sprites[id] = { ...sprites[id], category: 'Uncategorized' };
        }
      }
      return { ...state, categories: cats, sprites };
    }

    case Actions.ADD_ANIMATION: {
      const anim = {
        name: action.payload.name,
        frames: action.payload.frames || [],
        fps: action.payload.fps || 4,
        loop: action.payload.loop !== undefined ? action.payload.loop : true,
      };
      return {
        ...state,
        animations: { ...state.animations, [anim.name]: anim },
      };
    }

    case Actions.UPDATE_ANIMATION: {
      const { name, ...updates } = action.payload;
      if (!state.animations[name]) return state;
      return {
        ...state,
        animations: {
          ...state.animations,
          [name]: { ...state.animations[name], ...updates },
        },
      };
    }

    case Actions.DELETE_ANIMATION: {
      const { [action.payload]: _, ...rest } = state.animations;
      return { ...state, animations: rest };
    }

    case Actions.SET_ZOOM:
      return { ...state, zoom: Math.max(0.1, Math.min(10, action.payload)) };

    case Actions.SET_PAN:
      return { ...state, panX: action.payload.x, panY: action.payload.y };

    case Actions.IMPORT_ATLAS:
      return {
        ...state,
        ...action.payload,
      };

    case Actions.BATCH_ASSIGN_CATEGORY: {
      const { ids, category } = action.payload;
      const sprites = { ...state.sprites };
      ids.forEach(id => {
        if (sprites[id]) sprites[id] = { ...sprites[id], category };
      });
      return { ...state, sprites };
    }

    case Actions.BATCH_NAME_PREFIX: {
      const { ids, prefix } = action.payload;
      const sprites = { ...state.sprites };
      ids.forEach((id, i) => {
        if (sprites[id]) sprites[id] = { ...sprites[id], name: `${prefix}_${i + 1}` };
      });
      return { ...state, sprites };
    }

    case Actions.DELETE_ALL_SPRITES:
      return { ...state, sprites: {}, selectedSpriteId: null, multiSelect: [] };

    case Actions.SET_LAST_USED_CATEGORY:
      return { ...state, lastUsedCategory: action.payload };

    case Actions.BATCH_ASSIGN_TAGS: {
      const { ids, tags } = action.payload;
      const sprites = { ...state.sprites };
      ids.forEach(id => {
        if (sprites[id]) {
          // Merge tags (add new, preserve existing)
          const existing = sprites[id].tags || [];
          const merged = [...new Set([...existing, ...tags])];
          sprites[id] = { ...sprites[id], tags: merged };
        }
      });
      return { ...state, sprites };
    }

    case Actions.BATCH_ASSIGN_GROUP: {
      const { ids, group, parts } = action.payload;
      const sprites = { ...state.sprites };
      ids.forEach((id, i) => {
        if (sprites[id]) {
          sprites[id] = {
            ...sprites[id],
            group,
            groupPart: parts && parts[i] ? parts[i] : null,
          };
        }
      });
      return { ...state, sprites };
    }

    default:
      return state;
  }
}

// ─── Context ──────────────────────────────────────────────────────
const AtlasContext = createContext(null);

export function AtlasProvider({ children }) {
  const [state, dispatch] = useReducer(atlasReducer, initialState);

  // Convenience action creators
  const actions = {
    setSheet: useCallback((src, width, height, fileName) =>
      dispatch({ type: Actions.SET_SHEET, payload: { src, width, height, fileName } }), []),
    updateGrid: useCallback((updates) =>
      dispatch({ type: Actions.UPDATE_GRID, payload: updates }), []),
    addSprite: useCallback((sprite) =>
      dispatch({ type: Actions.ADD_SPRITE, payload: sprite }), []),
    updateSprite: useCallback((id, updates) =>
      dispatch({ type: Actions.UPDATE_SPRITE, payload: { id, ...updates } }), []),
    deleteSprite: useCallback((id) =>
      dispatch({ type: Actions.DELETE_SPRITE, payload: id }), []),
    selectSprite: useCallback((id) =>
      dispatch({ type: Actions.SELECT_SPRITE, payload: id }), []),
    setHoveredCell: useCallback((cell) =>
      dispatch({ type: Actions.SET_HOVERED_CELL, payload: cell }), []),
    toggleMultiSelect: useCallback((id) =>
      dispatch({ type: Actions.TOGGLE_MULTI_SELECT, payload: id }), []),
    clearSelection: useCallback(() =>
      dispatch({ type: Actions.CLEAR_SELECTION }), []),
    addCategory: useCallback((name) =>
      dispatch({ type: Actions.ADD_CATEGORY, payload: name }), []),
    renameCategory: useCallback((oldName, newName) =>
      dispatch({ type: Actions.RENAME_CATEGORY, payload: { oldName, newName } }), []),
    deleteCategory: useCallback((name) =>
      dispatch({ type: Actions.DELETE_CATEGORY, payload: name }), []),
    addAnimation: useCallback((anim) =>
      dispatch({ type: Actions.ADD_ANIMATION, payload: anim }), []),
    updateAnimation: useCallback((name, updates) =>
      dispatch({ type: Actions.UPDATE_ANIMATION, payload: { name, ...updates } }), []),
    deleteAnimation: useCallback((name) =>
      dispatch({ type: Actions.DELETE_ANIMATION, payload: name }), []),
    setZoom: useCallback((zoom) =>
      dispatch({ type: Actions.SET_ZOOM, payload: zoom }), []),
    setPan: useCallback((x, y) =>
      dispatch({ type: Actions.SET_PAN, payload: { x, y } }), []),
    importAtlas: useCallback((atlas) =>
      dispatch({ type: Actions.IMPORT_ATLAS, payload: atlas }), []),
    batchAssignCategory: useCallback((ids, category) =>
      dispatch({ type: Actions.BATCH_ASSIGN_CATEGORY, payload: { ids, category } }), []),
    batchNamePrefix: useCallback((ids, prefix) =>
      dispatch({ type: Actions.BATCH_NAME_PREFIX, payload: { ids, prefix } }), []),
    deleteAllSprites: useCallback(() =>
      dispatch({ type: Actions.DELETE_ALL_SPRITES }), []),
    setLastUsedCategory: useCallback((category) =>
      dispatch({ type: Actions.SET_LAST_USED_CATEGORY, payload: category }), []),
    batchAssignTags: useCallback((ids, tags) =>
      dispatch({ type: Actions.BATCH_ASSIGN_TAGS, payload: { ids, tags } }), []),
    batchAssignGroup: useCallback((ids, group, parts) =>
      dispatch({ type: Actions.BATCH_ASSIGN_GROUP, payload: { ids, group, parts } }), []),
  };

  return (
    <AtlasContext.Provider value={{ state, actions, dispatch }}>
      {children}
    </AtlasContext.Provider>
  );
}

export function useAtlas() {
  const ctx = useContext(AtlasContext);
  if (!ctx) throw new Error('useAtlas must be used within AtlasProvider');
  return ctx;
}

export { Actions };
export default AtlasContext;
