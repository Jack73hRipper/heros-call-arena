// ─────────────────────────────────────────────────────────
// App.jsx — Cave Automata Lab root component
//
// All state lives here and is passed down as props.
// Manages: generation, painting, undo/redo, gallery,
// room detection, connectivity, and export/import.
// ─────────────────────────────────────────────────────────

import React, { useState, useCallback, useEffect, useRef } from 'react';
import Toolbar from './components/Toolbar.jsx';
import ParameterPanel from './components/ParameterPanel.jsx';
import CaveCanvas from './components/CaveCanvas.jsx';
import EntityPanel from './components/EntityPanel.jsx';
import RoomPanel from './components/RoomPanel.jsx';
import StatsPanel from './components/StatsPanel.jsx';
import ExportPanel from './components/ExportPanel.jsx';
import BatchModal from './components/BatchModal.jsx';

import { generateCave, stepAutomata, WALL, FLOOR } from './engine/cellularAutomata.js';
import { detectRooms, removeSmallRooms } from './engine/roomDetection.js';
import { checkConnectivity, ensureConnectivity } from './engine/connectivity.js';
import { smooth, erode, dilate } from './engine/postProcessing.js';
import { randomSeed } from './engine/prng.js';
import { getPreset, PRESETS } from './engine/presets.js';
import { exportToGameJSON, importFromGameJSON, gridToTileMap } from './utils/exportMap.js';

import './styles/cave-automata.css';

// ─── Constants ─────────────────────────────────────────

const STORAGE_KEY = 'cave-automata-gallery';
const MAX_UNDO = 50;

// ─── Default state ─────────────────────────────────────

const DEFAULT_PARAMS = {
  fillPercent: 48,
  birthThreshold: 5,
  survivalThreshold: 4,
  iterations: 5,
  seed: randomSeed(),
  solidBorder: true,
};

function createEmptyTileMap(width, height) {
  return Array.from({ length: height }, () => new Array(width).fill('W'));
}

// ─── App ───────────────────────────────────────────────

export default function App() {
  // Map state
  const [mapWidth, setMapWidth] = useState(25);
  const [mapHeight, setMapHeight] = useState(25);
  const [mapName, setMapName] = useState('Cave Map');
  const [tileMap, setTileMap] = useState(() => createEmptyTileMap(25, 25));

  // CA parameters
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [selectedPreset, setSelectedPreset] = useState('natural-caves');

  // Binary grid (kept for step-by-step iteration)
  const binaryGridRef = useRef(null);

  // Room detection
  const [rooms, setRooms] = useState([]);
  const [connectivityInfo, setConnectivityInfo] = useState(null);
  const [smallRoomThreshold, setSmallRoomThreshold] = useState(10);

  // Display / paint state
  const [paintTile, setPaintTile] = useState(null);
  const [brushSize, setBrushSize] = useState(1);
  const [showGrid, setShowGrid] = useState(true);
  const [showRooms, setShowRooms] = useState(true);

  // Undo/redo
  const [undoStack, setUndoStack] = useState([]);
  const [redoStack, setRedoStack] = useState([]);

  // Gallery (localStorage)
  const [gallery, setGallery] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch { return []; }
  });

  // Batch generation
  const [batchCount, setBatchCount] = useState(5);
  const [batchResults, setBatchResults] = useState(null);

  // Sidebar tab
  const [activeTab, setActiveTab] = useState('params'); // 'params' | 'paint' | 'rooms' | 'export'

  // ─── Gallery persistence ───────────────────────────────

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(gallery));
    } catch { /* quota exceeded — ignore */ }
  }, [gallery]);

  // ─── Undo/Redo helpers ─────────────────────────────────

  const pushUndo = useCallback((map) => {
    setUndoStack(prev => {
      const next = [...prev, map.map(r => [...r])];
      if (next.length > MAX_UNDO) next.shift();
      return next;
    });
    setRedoStack([]);
  }, []);

  const handleUndo = useCallback(() => {
    setUndoStack(prev => {
      if (prev.length === 0) return prev;
      const next = [...prev];
      const snapshot = next.pop();
      setRedoStack(r => [...r, tileMap.map(row => [...row])]);
      setTileMap(snapshot);
      return next;
    });
  }, [tileMap]);

  const handleRedo = useCallback(() => {
    setRedoStack(prev => {
      if (prev.length === 0) return prev;
      const next = [...prev];
      const snapshot = next.pop();
      setUndoStack(u => [...u, tileMap.map(row => [...row])]);
      setTileMap(snapshot);
      return next;
    });
  }, [tileMap]);

  // ─── Room detection ────────────────────────────────────

  const updateRooms = useCallback((map) => {
    const binaryGrid = map.map(row => row.map(t => t === 'W' ? WALL : FLOOR));
    const detected = detectRooms(binaryGrid);
    // Preserve room names/purposes from previous state
    const enriched = detected.map(room => ({
      ...room,
      name: room.name || `Chamber ${room.id + 1}`,
      purpose: room.purpose || 'empty',
    }));
    setRooms(enriched);
    const connectivity = checkConnectivity(binaryGrid);
    setConnectivityInfo(connectivity);
  }, []);

  // ─── Generation ────────────────────────────────────────

  const handleGenerate = useCallback(() => {
    pushUndo(tileMap);

    const result = generateCave({
      width: mapWidth,
      height: mapHeight,
      ...params,
    });

    binaryGridRef.current = result.grid;
    const newMap = gridToTileMap(result.grid);
    setTileMap(newMap);
    updateRooms(newMap);
  }, [mapWidth, mapHeight, params, tileMap, pushUndo, updateRooms]);

  const handleClear = useCallback(() => {
    pushUndo(tileMap);
    const empty = createEmptyTileMap(mapWidth, mapHeight);
    setTileMap(empty);
    setRooms([]);
    setConnectivityInfo(null);
    binaryGridRef.current = null;
  }, [mapWidth, mapHeight, tileMap, pushUndo]);

  const handleStepOnce = useCallback(() => {
    pushUndo(tileMap);

    // Convert tileMap to binary grid
    let grid = tileMap.map(row => row.map(t => t === 'W' ? WALL : FLOOR));
    grid = stepAutomata(grid, params.birthThreshold, params.survivalThreshold, params.solidBorder);

    binaryGridRef.current = grid;
    const newMap = gridToTileMap(grid);
    setTileMap(newMap);
    updateRooms(newMap);
  }, [tileMap, params, pushUndo, updateRooms]);

  // ─── Post-processing ──────────────────────────────────

  const applyPostProcess = useCallback((processFn) => {
    pushUndo(tileMap);
    let grid = tileMap.map(row => row.map(t => t === 'W' ? WALL : FLOOR));
    grid = processFn(grid);
    binaryGridRef.current = grid;
    const newMap = gridToTileMap(grid);
    setTileMap(newMap);
    updateRooms(newMap);
  }, [tileMap, pushUndo, updateRooms]);

  const handleSmooth = useCallback(() => applyPostProcess(g => smooth(g)), [applyPostProcess]);
  const handleErode = useCallback(() => applyPostProcess(g => erode(g)), [applyPostProcess]);
  const handleDilate = useCallback(() => applyPostProcess(g => dilate(g)), [applyPostProcess]);

  // ─── Connectivity ─────────────────────────────────────

  const handleEnsureConnectivity = useCallback(() => {
    pushUndo(tileMap);
    const grid = tileMap.map(row => row.map(t => t === 'W' ? WALL : FLOOR));
    const result = ensureConnectivity(grid);
    binaryGridRef.current = result.grid;
    const newMap = gridToTileMap(result.grid);
    setTileMap(newMap);
    updateRooms(newMap);
  }, [tileMap, pushUndo, updateRooms]);

  // ─── Paint ─────────────────────────────────────────────

  const handlePaintCell = useCallback((x, y, tile) => {
    setTileMap(prev => {
      if (prev[y]?.[x] === tile) return prev; // No change
      const next = prev.map(r => [...r]);
      next[y][x] = tile;
      return next;
    });
  }, []);

  // Debounced undo push for painting (push on mouse down, handled in canvas)
  const handlePaintStart = useCallback(() => {
    pushUndo(tileMap);
  }, [tileMap, pushUndo]);

  // Update rooms after painting stops (debounced)
  const paintTimeoutRef = useRef(null);
  const handlePaintCellWithUndo = useCallback((x, y, tile) => {
    // Push undo on first paint stroke
    handlePaintCell(x, y, tile);

    // Debounce room update
    clearTimeout(paintTimeoutRef.current);
    paintTimeoutRef.current = setTimeout(() => {
      setTileMap(current => {
        updateRooms(current);
        return current;
      });
    }, 300);
  }, [handlePaintCell, updateRooms]);

  // ─── Size change ──────────────────────────────────────

  const handleSizeChange = useCallback((w, h) => {
    const cw = Math.max(8, Math.min(100, w));
    const ch = Math.max(8, Math.min(100, h));
    setMapWidth(cw);
    setMapHeight(ch);
    pushUndo(tileMap);
    const empty = createEmptyTileMap(cw, ch);
    setTileMap(empty);
    setRooms([]);
    setConnectivityInfo(null);
  }, [tileMap, pushUndo]);

  // ─── Preset change ────────────────────────────────────

  const handlePresetChange = useCallback((presetId) => {
    setSelectedPreset(presetId);
    if (presetId) {
      const preset = getPreset(presetId);
      if (preset) {
        setParams(prev => ({ ...prev, ...preset.params }));
      }
    }
  }, []);

  const handleRandomSeed = useCallback(() => {
    setParams(prev => ({ ...prev, seed: randomSeed() }));
  }, []);

  // ─── Room editing ─────────────────────────────────────

  const handleRoomPurposeChange = useCallback((roomId, purpose) => {
    setRooms(prev => prev.map(r => r.id === roomId ? { ...r, purpose } : r));
  }, []);

  const handleRoomNameChange = useCallback((roomId, name) => {
    setRooms(prev => prev.map(r => r.id === roomId ? { ...r, name } : r));
  }, []);

  const handleRemoveSmallRooms = useCallback(() => {
    pushUndo(tileMap);
    const grid = tileMap.map(row => row.map(t => t === 'W' ? WALL : FLOOR));
    const result = removeSmallRooms(grid, [...rooms], smallRoomThreshold);
    binaryGridRef.current = result.grid;
    const newMap = gridToTileMap(result.grid);
    setTileMap(newMap);
    updateRooms(newMap);
  }, [tileMap, rooms, smallRoomThreshold, pushUndo, updateRooms]);

  // ─── Export / Import ──────────────────────────────────

  const handleExport = useCallback(() => {
    const json = exportToGameJSON(tileMap, rooms, mapName);
    const blob = new Blob([JSON.stringify(json, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${mapName.replace(/\s+/g, '_').toLowerCase()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [tileMap, rooms, mapName]);

  const handleImport = useCallback((json) => {
    pushUndo(tileMap);
    const data = importFromGameJSON(json);
    setMapWidth(data.width);
    setMapHeight(data.height);
    setMapName(data.name);
    setTileMap(data.tileMap);
    updateRooms(data.tileMap);
  }, [tileMap, pushUndo, updateRooms]);

  // ─── Gallery ──────────────────────────────────────────

  const handleSaveToGallery = useCallback(() => {
    const entry = {
      id: Date.now(),
      name: mapName,
      width: mapWidth,
      height: mapHeight,
      tileMap: tileMap.map(r => [...r]),
      rooms: rooms.map(r => ({ id: r.id, name: r.name, purpose: r.purpose, bounds: r.bounds, size: r.size, center: r.center })),
      date: new Date().toLocaleDateString(),
      params: { ...params },
    };
    setGallery(prev => [entry, ...prev]);
  }, [mapName, mapWidth, mapHeight, tileMap, rooms, params]);

  const handleLoadFromGallery = useCallback((idx) => {
    const entry = gallery[idx];
    if (!entry) return;
    pushUndo(tileMap);
    setMapWidth(entry.width);
    setMapHeight(entry.height);
    setMapName(entry.name);
    setTileMap(entry.tileMap);
    if (entry.params) setParams(prev => ({ ...prev, ...entry.params }));
    updateRooms(entry.tileMap);
  }, [gallery, tileMap, pushUndo, updateRooms]);

  const handleDeleteFromGallery = useCallback((idx) => {
    setGallery(prev => prev.filter((_, i) => i !== idx));
  }, []);

  // ─── Batch generate ───────────────────────────────────

  const handleBatchGenerate = useCallback(() => {
    const results = [];
    for (let i = 0; i < batchCount; i++) {
      const seed = (params.seed + i * 7919) | 0; // Varied seeds
      const result = generateCave({
        width: mapWidth,
        height: mapHeight,
        ...params,
        seed,
      });

      const tm = gridToTileMap(result.grid);
      const connectivity = checkConnectivity(result.grid);
      const totalCells = mapWidth * mapHeight;
      const floorCells = result.grid.flat().filter(c => c === FLOOR).length;
      const floorPercent = ((floorCells / totalCells) * 100).toFixed(1);

      // Score: connected is strongly preferred, then balance connectivity + openness
      const connectBonus = connectivity.connected ? 50 : 0;
      const regionPenalty = Math.max(0, (connectivity.regionCount - 1) * 10);
      const openness = floorCells / totalCells;
      const opennessScore = (1 - Math.abs(openness - 0.45)) * 50; // Prefer ~45% floor
      const score = connectBonus - regionPenalty + opennessScore;

      results.push({
        seed,
        tileMap: tm,
        grid: result.grid,
        regionCount: connectivity.regionCount,
        roomCount: connectivity.rooms.length,
        floorPercent,
        score,
      });
    }

    // Sort by score descending
    results.sort((a, b) => b.score - a.score);
    setBatchResults(results);
  }, [batchCount, params, mapWidth, mapHeight]);

  const handleBatchSelect = useCallback((result) => {
    pushUndo(tileMap);
    setTileMap(result.tileMap);
    setParams(prev => ({ ...prev, seed: result.seed }));
    updateRooms(result.tileMap);
    setBatchResults(null);
  }, [tileMap, pushUndo, updateRooms]);

  // ─── Keyboard shortcuts ───────────────────────────────

  useEffect(() => {
    const handleKey = (e) => {
      // Ctrl+Z = Undo
      if (e.ctrlKey && e.key === 'z') {
        e.preventDefault();
        handleUndo();
      }
      // Ctrl+Y = Redo
      if (e.ctrlKey && e.key === 'y') {
        e.preventDefault();
        handleRedo();
      }
      // Enter = Generate
      if (e.key === 'Enter' && !e.ctrlKey && !e.shiftKey && e.target.tagName !== 'INPUT') {
        e.preventDefault();
        handleGenerate();
      }
      // Number keys 1-8 = paint tile shortcuts
      if (e.key >= '1' && e.key <= '8' && !e.ctrlKey && e.target.tagName !== 'INPUT') {
        const tiles = ['W', 'F', 'D', 'C', 'S', 'X', 'E', 'B'];
        const idx = parseInt(e.key) - 1;
        if (idx < tiles.length) setPaintTile(tiles[idx]);
      }
      // 0 or Escape = no paint
      if ((e.key === '0' || e.key === 'Escape') && e.target.tagName !== 'INPUT') {
        setPaintTile(null);
      }
      // [ ] = brush size
      if (e.key === '[') setBrushSize(prev => Math.max(1, prev - 1));
      if (e.key === ']') setBrushSize(prev => Math.min(5, prev + 1));
    };

    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [handleUndo, handleRedo, handleGenerate]);

  // ─── Render ────────────────────────────────────────────

  return (
    <div className="app">
      <Toolbar
        mapWidth={mapWidth}
        mapHeight={mapHeight}
        onSizeChange={handleSizeChange}
        selectedPreset={selectedPreset}
        onPresetChange={handlePresetChange}
        onGenerate={handleGenerate}
        onClear={handleClear}
        mapName={mapName}
        onMapNameChange={setMapName}
      />

      <div className="main-layout">
        {/* Left sidebar — tabs */}
        <div className="sidebar sidebar-left">
          <div className="sidebar-tabs">
            <button
              className={`tab-btn ${activeTab === 'params' ? 'active' : ''}`}
              onClick={() => setActiveTab('params')}
            >
              Gen
            </button>
            <button
              className={`tab-btn ${activeTab === 'paint' ? 'active' : ''}`}
              onClick={() => setActiveTab('paint')}
            >
              Paint
            </button>
            <button
              className={`tab-btn ${activeTab === 'rooms' ? 'active' : ''}`}
              onClick={() => setActiveTab('rooms')}
            >
              Rooms
            </button>
            <button
              className={`tab-btn ${activeTab === 'export' ? 'active' : ''}`}
              onClick={() => setActiveTab('export')}
            >
              IO
            </button>
          </div>

          <div className="sidebar-content">
            {activeTab === 'params' && (
              <ParameterPanel
                params={params}
                onParamChange={setParams}
                onRandomSeed={handleRandomSeed}
                onStepOnce={handleStepOnce}
                onApplySmooth={handleSmooth}
                onApplyErode={handleErode}
                onApplyDilate={handleDilate}
                onEnsureConnectivity={handleEnsureConnectivity}
                connectivityInfo={connectivityInfo}
              />
            )}
            {activeTab === 'paint' && (
              <EntityPanel
                paintTile={paintTile}
                onPaintTileChange={setPaintTile}
                brushSize={brushSize}
                onBrushSizeChange={setBrushSize}
                showGrid={showGrid}
                onShowGridChange={setShowGrid}
                showRooms={showRooms}
                onShowRoomsChange={setShowRooms}
              />
            )}
            {activeTab === 'rooms' && (
              <RoomPanel
                rooms={rooms}
                onRoomPurposeChange={handleRoomPurposeChange}
                onRoomNameChange={handleRoomNameChange}
                onRemoveSmallRooms={handleRemoveSmallRooms}
                smallRoomThreshold={smallRoomThreshold}
                onSmallRoomThresholdChange={setSmallRoomThreshold}
              />
            )}
            {activeTab === 'export' && (
              <ExportPanel
                onExport={handleExport}
                onImport={handleImport}
                onSaveToGallery={handleSaveToGallery}
                onLoadFromGallery={handleLoadFromGallery}
                gallery={gallery}
                onDeleteFromGallery={handleDeleteFromGallery}
                onBatchGenerate={handleBatchGenerate}
                batchCount={batchCount}
                onBatchCountChange={setBatchCount}
                onUndo={handleUndo}
                onRedo={handleRedo}
                canUndo={undoStack.length > 0}
                canRedo={redoStack.length > 0}
              />
            )}
          </div>
        </div>

        {/* Center — Canvas */}
        <div className="canvas-area">
          <CaveCanvas
            tileMap={tileMap}
            rooms={rooms}
            showRooms={showRooms}
            showGrid={showGrid}
            paintTile={paintTile}
            onPaintCell={handlePaintCellWithUndo}
            brushSize={brushSize}
          />
        </div>

        {/* Right sidebar — Stats */}
        <div className="sidebar sidebar-right">
          <StatsPanel
            tileMap={tileMap}
            rooms={rooms}
            connectivityInfo={connectivityInfo}
          />
        </div>
      </div>

      {/* Batch modal */}
      {batchResults && (
        <BatchModal
          results={batchResults}
          onSelect={handleBatchSelect}
          onClose={() => setBatchResults(null)}
        />
      )}
    </div>
  );
}
