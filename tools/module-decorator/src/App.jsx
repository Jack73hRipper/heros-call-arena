// ─────────────────────────────────────────────────────────
// App.jsx — Module Sprite Decorator root component
//
// State hub for the entire tool. Manages:
// - Atlas loading and sprite selection
// - Module selection and navigation
// - Sprite map per module (base + overlay layers)
// - Undo/redo history
// - Import/export of sprite library
// ─────────────────────────────────────────────────────────

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { parseAtlas, buildFullGrid } from './engine/atlasLoader.js';
import { PRESET_MODULES } from './engine/modulePresets.js';
import {
  createEmptySpriteMap,
  setBaseSprite,
  setOverlaySprite,
  cloneSpriteMap,
  serializeSpriteLibrary,
  deserializeSpriteLibrary,
  hasAnySprites,
  countAssignments,
  generateRotationVariants,
} from './engine/spriteMap.js';
import { autoDecorate, AUTO_DECORATE_PRESETS } from './engine/autoDecorator.js';

import Toolbar from './components/Toolbar.jsx';
import AtlasPalette from './components/AtlasPalette.jsx';
import ModuleSelector from './components/ModuleSelector.jsx';
import ModuleCanvas from './components/ModuleCanvas.jsx';
import LayerPanel from './components/LayerPanel.jsx';
import PreviewPanel from './components/PreviewPanel.jsx';
import ExportPanel from './components/ExportPanel.jsx';

import './styles/module-decorator.css';

// ─── Default atlas JSON (embedded, matching mainlevbuild-atlas.json) ────
const DEFAULT_ATLAS = {
  version: 1,
  sheetFile: 'mainlevbuild.png',
  sheetWidth: 1024,
  sheetHeight: 640,
  gridDefaults: { cellW: 16, cellH: 16, offsetX: 0, offsetY: 0, spacingX: 0, spacingY: 0 },
  categories: ['Uncategorized', 'Heros', 'Monsters', 'Floor_Tiles', 'Wall_Tiles'],
  sprites: {
    'Floor_Tile_Cobble1': { id: 'sprite_484', x: 736, y: 272, w: 16, h: 16, category: 'Floor_Tiles', row: 17, col: 46 },
    'Floor_Tile_Cobble2': { id: 'sprite_486', x: 752, y: 272, w: 16, h: 16, category: 'Floor_Tiles', row: 17, col: 47 },
    'Floor_Tile_Cobble3': { id: 'sprite_490', x: 736, y: 288, w: 16, h: 16, category: 'Floor_Tiles', row: 18, col: 46 },
    'Floor_Tile_Cobble4': { id: 'sprite_488', x: 752, y: 288, w: 16, h: 16, category: 'Floor_Tiles', row: 18, col: 47 },
    'Floor_Tile_Smooth1': { id: 'sprite_502', x: 752, y: 208, w: 16, h: 16, category: 'Floor_Tiles', row: 13, col: 47 },
    'Floor_Tile_Smooth2': { id: 'sprite_500', x: 736, y: 208, w: 16, h: 16, category: 'Floor_Tiles', row: 13, col: 46 },
    'Floor_Tile_Smooth3': { id: 'sprite_508', x: 752, y: 224, w: 16, h: 16, category: 'Floor_Tiles', row: 14, col: 47 },
    'Floor_Tile_Smooth4': { id: 'sprite_506', x: 736, y: 224, w: 16, h: 16, category: 'Floor_Tiles', row: 14, col: 46 },
    'Floor_Tile_Smooth5': { id: 'sprite_512', x: 736, y: 240, w: 16, h: 16, category: 'Floor_Tiles', row: 15, col: 46 },
    'Floor_Tile_Smooth6': { id: 'sprite_510', x: 752, y: 240, w: 16, h: 16, category: 'Floor_Tiles', row: 15, col: 47 },
    'Wall_Brick': { id: 'sprite_516', x: 272, y: 304, w: 16, h: 16, category: 'Wall_Tiles', row: 19, col: 17 },
    'Wall_Cobble': { id: 'sprite_518', x: 80, y: 368, w: 16, h: 16, category: 'Wall_Tiles', row: 23, col: 5 },
    'Wall_Stone': { id: 'sprite_520', x: 384, y: 432, w: 16, h: 16, category: 'Wall_Tiles', row: 27, col: 24 },
  },
  animations: {},
};

const STORAGE_KEY = 'module-decorator-library';

export default function App() {
  // ─── Atlas state ──────────────────────────────────────
  const [atlasData, setAtlasData] = useState(() => parseAtlas(DEFAULT_ATLAS));
  const [fullGrid, setFullGrid] = useState(() => buildFullGrid(parseAtlas(DEFAULT_ATLAS)));
  const [atlasImage, setAtlasImage] = useState(null);
  const [atlasLoaded, setAtlasLoaded] = useState(false);

  // ─── Module state ─────────────────────────────────────
  const [modules, setModules] = useState(PRESET_MODULES);
  const [selectedModuleId, setSelectedModuleId] = useState(PRESET_MODULES[0]?.id || null);

  // ─── Sprite maps (moduleId → spriteMap) ───────────────
  const [spriteMaps, setSpriteMaps] = useState(() => {
    // Attempt to load from localStorage
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const data = JSON.parse(saved);
        return deserializeSpriteLibrary(data);
      }
    } catch (e) { /* ignore */ }
    return {};
  });

  // ─── Editing state ────────────────────────────────────
  const [selectedSprite, setSelectedSprite] = useState(null); // atlas region to paint
  const [activeLayer, setActiveLayer] = useState('base'); // 'base' or 'overlay'
  const [showGameplayLayer, setShowGameplayLayer] = useState(true);
  const [showBaseLayer, setShowBaseLayer] = useState(true);
  const [showOverlayLayer, setShowOverlayLayer] = useState(true);
  const [baseOpacity, setBaseOpacity] = useState(1.0);
  const [overlayOpacity, setOverlayOpacity] = useState(1.0);
  const [gameplayOpacity, setGameplayOpacity] = useState(0.3);

  // ─── Undo/Redo ────────────────────────────────────────
  const [undoStack, setUndoStack] = useState([]);
  const [redoStack, setRedoStack] = useState([]);
  const MAX_UNDO = 50;

  // ─── Tab state ────────────────────────────────────────
  const [activeTab, setActiveTab] = useState('editor'); // 'editor' or 'preview'

  // ─── Derived ──────────────────────────────────────────
  const selectedModule = modules.find(m => m.id === selectedModuleId) || null;
  const currentSpriteMap = selectedModuleId
    ? (spriteMaps[selectedModuleId] || createEmptySpriteMap(6, 6))
    : null;

  // ─── Load atlas image ─────────────────────────────────
  useEffect(() => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      setAtlasImage(img);
      setAtlasLoaded(true);
    };
    img.onerror = () => {
      console.warn('[ModuleDecorator] Atlas image not found, will work in color-fallback mode');
    };
    // Try loading from multiple possible locations
    img.src = '/mainlevbuild.png';
  }, []);

  // ─── Auto-save to localStorage ────────────────────────
  useEffect(() => {
    try {
      const data = serializeSpriteLibrary(
        atlasData.sheetFile,
        atlasData.cellW,
        spriteMaps
      );
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) { /* ignore */ }
  }, [spriteMaps, atlasData]);

  // ─── Push undo state ──────────────────────────────────
  const pushUndo = useCallback(() => {
    if (!selectedModuleId || !currentSpriteMap) return;
    setUndoStack(prev => {
      const next = [...prev, { moduleId: selectedModuleId, spriteMap: cloneSpriteMap(currentSpriteMap) }];
      if (next.length > MAX_UNDO) next.shift();
      return next;
    });
    setRedoStack([]);
  }, [selectedModuleId, currentSpriteMap]);

  // ─── Undo ─────────────────────────────────────────────
  const handleUndo = useCallback(() => {
    if (undoStack.length === 0) return;
    const last = undoStack[undoStack.length - 1];
    setRedoStack(prev => [...prev, { moduleId: selectedModuleId, spriteMap: cloneSpriteMap(currentSpriteMap) }]);
    setSpriteMaps(prev => ({ ...prev, [last.moduleId]: last.spriteMap }));
    setUndoStack(prev => prev.slice(0, -1));
  }, [undoStack, selectedModuleId, currentSpriteMap]);

  // ─── Redo ─────────────────────────────────────────────
  const handleRedo = useCallback(() => {
    if (redoStack.length === 0) return;
    const last = redoStack[redoStack.length - 1];
    setUndoStack(prev => [...prev, { moduleId: selectedModuleId, spriteMap: cloneSpriteMap(currentSpriteMap) }]);
    setSpriteMaps(prev => ({ ...prev, [last.moduleId]: last.spriteMap }));
    setRedoStack(prev => prev.slice(0, -1));
  }, [redoStack, selectedModuleId, currentSpriteMap]);

  // ─── Paint a cell ─────────────────────────────────────
  const handlePaintCell = useCallback((row, col) => {
    if (!selectedModuleId || !selectedSprite) return;

    pushUndo();
    setSpriteMaps(prev => {
      const existing = prev[selectedModuleId] || createEmptySpriteMap(6, 6);
      const updated = cloneSpriteMap(existing);
      const region = { x: selectedSprite.x, y: selectedSprite.y, w: selectedSprite.w, h: selectedSprite.h };

      if (activeLayer === 'base') {
        setBaseSprite(updated, row, col, region);
      } else {
        setOverlaySprite(updated, row, col, region);
      }

      return { ...prev, [selectedModuleId]: updated };
    });
  }, [selectedModuleId, selectedSprite, activeLayer, pushUndo]);

  // ─── Erase a cell ─────────────────────────────────────
  const handleEraseCell = useCallback((row, col) => {
    if (!selectedModuleId) return;

    pushUndo();
    setSpriteMaps(prev => {
      const existing = prev[selectedModuleId] || createEmptySpriteMap(6, 6);
      const updated = cloneSpriteMap(existing);

      if (activeLayer === 'base') {
        setBaseSprite(updated, row, col, null);
      } else {
        setOverlaySprite(updated, row, col, null);
      }

      return { ...prev, [selectedModuleId]: updated };
    });
  }, [selectedModuleId, activeLayer, pushUndo]);

  // ─── Auto-decorate current module ─────────────────────
  const handleAutoDecorate = useCallback((presetName) => {
    if (!selectedModule) return;

    pushUndo();
    const opts = AUTO_DECORATE_PRESETS[presetName] || AUTO_DECORATE_PRESETS['Grimdark Brick'];
    const newMap = autoDecorate(selectedModule.tiles, { ...opts, seed: Date.now() % 100000 });

    setSpriteMaps(prev => ({ ...prev, [selectedModuleId]: newMap }));
  }, [selectedModule, selectedModuleId, pushUndo]);

  // ─── Clear current module sprites ─────────────────────
  const handleClearModule = useCallback(() => {
    if (!selectedModuleId) return;
    pushUndo();
    setSpriteMaps(prev => ({ ...prev, [selectedModuleId]: createEmptySpriteMap(6, 6) }));
  }, [selectedModuleId, pushUndo]);

  // ─── Auto-decorate ALL modules ────────────────────────
  const handleAutoDecorateAll = useCallback((presetName) => {
    const opts = AUTO_DECORATE_PRESETS[presetName] || AUTO_DECORATE_PRESETS['Grimdark Brick'];
    const updated = { ...spriteMaps };

    modules.forEach((mod, idx) => {
      if (!hasAnySprites(updated[mod.id] || createEmptySpriteMap(6, 6))) {
        updated[mod.id] = autoDecorate(mod.tiles, { ...opts, seed: idx * 137 + 42 });
      }
    });

    setSpriteMaps(updated);
  }, [modules, spriteMaps]);

  // ─── Import atlas JSON ────────────────────────────────
  const handleImportAtlas = useCallback((jsonData) => {
    const parsed = parseAtlas(jsonData);
    setAtlasData(parsed);
    setFullGrid(buildFullGrid(parsed));
  }, []);

  // ─── Import module JSON ───────────────────────────────
  const handleImportModule = useCallback((moduleData) => {
    // Add to module list if not already there
    setModules(prev => {
      if (prev.find(m => m.id === moduleData.id)) return prev;
      return [...prev, moduleData];
    });
    setSelectedModuleId(moduleData.id);
  }, []);

  // ─── Export sprite library ────────────────────────────
  const handleExport = useCallback(() => {
    const data = serializeSpriteLibrary(
      atlasData.sheetFile,
      atlasData.cellW,
      spriteMaps
    );
    return data;
  }, [atlasData, spriteMaps]);

  // ─── Import sprite library ────────────────────────────
  const handleImportLibrary = useCallback((data) => {
    const imported = deserializeSpriteLibrary(data);
    setSpriteMaps(prev => ({ ...prev, ...imported }));
  }, []);

  // ─── Keyboard shortcuts ───────────────────────────────
  useEffect(() => {
    const handleKey = (e) => {
      if (e.ctrlKey && e.key === 'z') {
        e.preventDefault();
        handleUndo();
      } else if (e.ctrlKey && (e.key === 'y' || (e.shiftKey && e.key === 'Z'))) {
        e.preventDefault();
        handleRedo();
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [handleUndo, handleRedo]);

  // ─── Module decoration stats ──────────────────────────
  const decoratedCount = modules.filter(m => hasAnySprites(spriteMaps[m.id] || createEmptySpriteMap(6, 6))).length;
  const currentStats = currentSpriteMap ? countAssignments(currentSpriteMap) : { baseCount: 0, overlayCount: 0 };

  return (
    <div className="app-container">
      <Toolbar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        undoCount={undoStack.length}
        redoCount={redoStack.length}
        onUndo={handleUndo}
        onRedo={handleRedo}
        decoratedCount={decoratedCount}
        totalModules={modules.length}
      />

      <div className="main-layout">
        {/* Left sidebar — Module Selector */}
        <div className="sidebar-left">
          <ModuleSelector
            modules={modules}
            selectedModuleId={selectedModuleId}
            onSelectModule={setSelectedModuleId}
            spriteMaps={spriteMaps}
            onImportModule={handleImportModule}
          />
        </div>

        {/* Center — Editor or Preview */}
        <div className="center-panel">
          {activeTab === 'editor' ? (
            <div className="editor-layout">
              <ModuleCanvas
                module={selectedModule}
                spriteMap={currentSpriteMap}
                atlasImage={atlasImage}
                atlasLoaded={atlasLoaded}
                selectedSprite={selectedSprite}
                activeLayer={activeLayer}
                showGameplayLayer={showGameplayLayer}
                showBaseLayer={showBaseLayer}
                showOverlayLayer={showOverlayLayer}
                baseOpacity={baseOpacity}
                overlayOpacity={overlayOpacity}
                gameplayOpacity={gameplayOpacity}
                onPaintCell={handlePaintCell}
                onEraseCell={handleEraseCell}
              />
              <div className="editor-sidebar">
                <LayerPanel
                  activeLayer={activeLayer}
                  onSetActiveLayer={setActiveLayer}
                  showGameplayLayer={showGameplayLayer}
                  showBaseLayer={showBaseLayer}
                  showOverlayLayer={showOverlayLayer}
                  onToggleGameplay={() => setShowGameplayLayer(v => !v)}
                  onToggleBase={() => setShowBaseLayer(v => !v)}
                  onToggleOverlay={() => setShowOverlayLayer(v => !v)}
                  baseOpacity={baseOpacity}
                  overlayOpacity={overlayOpacity}
                  gameplayOpacity={gameplayOpacity}
                  onBaseOpacityChange={setBaseOpacity}
                  onOverlayOpacityChange={setOverlayOpacity}
                  onGameplayOpacityChange={setGameplayOpacity}
                  stats={currentStats}
                  onAutoDecorate={handleAutoDecorate}
                  onAutoDecorateAll={handleAutoDecorateAll}
                  onClearModule={handleClearModule}
                />
                <ExportPanel
                  onExport={handleExport}
                  onImportLibrary={handleImportLibrary}
                  onImportAtlas={handleImportAtlas}
                  atlasData={atlasData}
                  decoratedCount={decoratedCount}
                  totalModules={modules.length}
                />
              </div>
            </div>
          ) : (
            <PreviewPanel
              modules={modules}
              spriteMaps={spriteMaps}
              atlasImage={atlasImage}
              atlasLoaded={atlasLoaded}
            />
          )}
        </div>

        {/* Right sidebar — Atlas Palette */}
        <div className="sidebar-right">
          <AtlasPalette
            atlasData={atlasData}
            fullGrid={fullGrid}
            atlasImage={atlasImage}
            atlasLoaded={atlasLoaded}
            selectedSprite={selectedSprite}
            onSelectSprite={setSelectedSprite}
          />
        </div>
      </div>
    </div>
  );
}
