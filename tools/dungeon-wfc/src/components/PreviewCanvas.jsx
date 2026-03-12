// ─────────────────────────────────────────────────────────
// PreviewCanvas.jsx — Renders the generated dungeon tile map
//
// Full dungeon preview with tile-level rendering.
// Supports zoom and pan. Shows module grid overlay.
// Click a module cell to open a picker to swap it or rotate it.
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect, useCallback, useState, useMemo } from 'react';
import { MODULE_SIZE, expandModules, deriveSockets } from '../engine/moduleUtils.js';
import { TILE_COLORS, TILE_BORDERS } from '../utils/tileColors.js';

const MIN_CELL = 6;
const MAX_CELL = 40;
const DEFAULT_CELL = 16;

/** Opposite direction map */
const OPPOSITE = { north: 'south', south: 'north', east: 'west', west: 'east' };
const OFFSETS = { north: { dr: -1, dc: 0 }, south: { dr: 1, dc: 0 }, east: { dr: 0, dc: 1 }, west: { dr: 0, dc: -1 } };

export default function PreviewCanvas({ tileMap, wfcGrid, variants, modules, onSwapModule, decoratedRooms }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const [cellSize, setCellSize] = useState(DEFAULT_CELL);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [dragMoved, setDragMoved] = useState(false);
  const [showGrid, setShowGrid] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  // Module picker state
  const [selectedCell, setSelectedCell] = useState(null); // { row, col }
  const [pickerPos, setPickerPos] = useState({ x: 0, y: 0 });
  const [showAllModules, setShowAllModules] = useState(false);

  const mapH = tileMap?.length || 0;
  const mapW = tileMap?.[0]?.length || 0;

  // Expand all modules into variants for the picker
  const allVariants = useMemo(() => {
    if (!modules) return [];
    return expandModules(modules);
  }, [modules]);

  // ── Compute compatible variants for the selected cell ──
  const compatibleVariants = useMemo(() => {
    if (!selectedCell || !wfcGrid || !variants || allVariants.length === 0) return [];
    const { row, col } = selectedCell;
    const gridRows = wfcGrid.length;
    const gridCols = wfcGrid[0]?.length || 0;

    // Gather neighbor socket requirements
    const neighborConstraints = {}; // direction → required socket on our side
    for (const [dir, { dr, dc }] of Object.entries(OFFSETS)) {
      const nr = row + dr;
      const nc = col + dc;
      if (nr >= 0 && nr < gridRows && nc >= 0 && nc < gridCols) {
        const neighborCell = wfcGrid[nr][nc];
        if (neighborCell.chosenVariant != null) {
          const nv = variants[neighborCell.chosenVariant];
          // Our `dir` side must match neighbor's opposite side
          neighborConstraints[dir] = nv.sockets[OPPOSITE[dir]];
        }
      }
    }

    // Filter all variants by compatibility with neighbors
    return allVariants.filter(v => {
      for (const [dir, requiredSocket] of Object.entries(neighborConstraints)) {
        if (v.sockets[dir] !== requiredSocket) return false;
      }
      return true;
    });
  }, [selectedCell, wfcGrid, variants, allVariants]);

  // Group compatible variants by source module for cleaner display
  const groupedVariants = useMemo(() => {
    const groups = {};
    for (const v of compatibleVariants) {
      if (!groups[v.sourceId]) {
        groups[v.sourceId] = { name: v.sourceName, purpose: v.purpose, variants: [] };
      }
      groups[v.sourceId].variants.push(v);
    }
    return Object.values(groups);
  }, [compatibleVariants]);

  // Group ALL variants for the "Show All" mode
  const allGroupedVariants = useMemo(() => {
    const groups = {};
    for (const v of allVariants) {
      if (!groups[v.sourceId]) {
        groups[v.sourceId] = { name: v.sourceName, purpose: v.purpose, variants: [] };
      }
      groups[v.sourceId].variants.push(v);
    }
    return Object.values(groups);
  }, [allVariants]);

  // Choose which list to display based on toggle
  const displayGrouped = showAllModules ? allGroupedVariants : groupedVariants;
  const displayCount = showAllModules ? allVariants.length : compatibleVariants.length;

  // Current variant info for selected cell
  const currentVariant = useMemo(() => {
    if (!selectedCell || !wfcGrid || !variants) return null;
    const cell = wfcGrid[selectedCell.row]?.[selectedCell.col];
    if (!cell || cell.chosenVariant == null) return null;
    return variants[cell.chosenVariant];
  }, [selectedCell, wfcGrid, variants]);

  // ── Draw ──
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !tileMap || mapW === 0) return;

    const ctx = canvas.getContext('2d');
    const cw = canvas.width;
    const ch = canvas.height;

    ctx.fillStyle = '#0e0e1a';
    ctx.fillRect(0, 0, cw, ch);

    ctx.save();
    ctx.translate(offset.x, offset.y);

    // Draw tiles
    for (let r = 0; r < mapH; r++) {
      for (let c = 0; c < mapW; c++) {
        const tile = tileMap[r][c];
        const x = c * cellSize;
        const y = r * cellSize;

        ctx.fillStyle = TILE_COLORS[tile] || '#444';
        ctx.fillRect(x, y, cellSize, cellSize);

        if (cellSize >= 12) {
          ctx.strokeStyle = TILE_BORDERS[tile] || '#333';
          ctx.lineWidth = 0.5;
          ctx.strokeRect(x + 0.5, y + 0.5, cellSize - 1, cellSize - 1);
        }

        // Tile letter if zoomed in enough
        if (cellSize >= 20 && showLabels) {
          ctx.fillStyle = '#ccc';
          ctx.font = `${Math.max(8, cellSize * 0.4)}px monospace`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(tile, x + cellSize / 2, y + cellSize / 2);
        }
      }
    }

    // Module grid overlay
    if (showGrid && wfcGrid) {
      const gridRows = wfcGrid.length;
      const gridCols = wfcGrid[0]?.length || 0;
      const modPx = MODULE_SIZE * cellSize;

      ctx.strokeStyle = 'rgba(255, 200, 50, 0.4)';
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);

      for (let gr = 0; gr <= gridRows; gr++) {
        ctx.beginPath();
        ctx.moveTo(0, gr * modPx);
        ctx.lineTo(gridCols * modPx, gr * modPx);
        ctx.stroke();
      }
      for (let gc = 0; gc <= gridCols; gc++) {
        ctx.beginPath();
        ctx.moveTo(gc * modPx, 0);
        ctx.lineTo(gc * modPx, gridRows * modPx);
        ctx.stroke();
      }

      ctx.setLineDash([]);

      // Module names + decorator role labels
      if (cellSize >= 10 && variants) {
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';

        // Build a lookup for decorated room roles
        const decoratedLookup = {};
        if (decoratedRooms) {
          for (const dr of decoratedRooms) {
            decoratedLookup[`${dr.gridRow},${dr.gridCol}`] = dr;
          }
        }

        const roleColors = {
          enemy: 'rgba(230, 100, 100, 0.85)',
          loot: 'rgba(230, 200, 50, 0.85)',
          boss: 'rgba(200, 80, 180, 0.85)',
          spawn: 'rgba(100, 200, 100, 0.85)',
          empty: 'rgba(150, 150, 150, 0.5)',
        };

        for (let gr = 0; gr < gridRows; gr++) {
          for (let gc = 0; gc < gridCols; gc++) {
            const cell = wfcGrid[gr][gc];
            if (cell.chosenVariant != null) {
              const v = variants[cell.chosenVariant];
              const label = v.sourceName + (v.rotation ? ` ${v.rotation}°` : '');
              ctx.fillStyle = 'rgba(255, 200, 50, 0.7)';
              ctx.fillText(label, gc * modPx + 3, gr * modPx + 3);

              // Show decorator role badge
              const decRoom = decoratedLookup[`${gr},${gc}`];
              if (decRoom && decRoom.assignedRole !== 'empty') {
                const badgeText = `[${decRoom.assignedRole.toUpperCase()}]`;
                ctx.fillStyle = roleColors[decRoom.assignedRole] || 'rgba(200,200,200,0.7)';
                ctx.font = 'bold 10px sans-serif';
                ctx.fillText(badgeText, gc * modPx + 3, gr * modPx + 15);
                ctx.font = '10px sans-serif';
              }
            }
          }
        }
      }

      // Highlight selected cell
      if (selectedCell) {
        const { row, col } = selectedCell;
        ctx.strokeStyle = 'rgba(100, 200, 255, 0.9)';
        ctx.lineWidth = 3;
        ctx.setLineDash([]);
        ctx.strokeRect(col * modPx + 1, row * modPx + 1, modPx - 2, modPx - 2);
      }
    }

    ctx.restore();
  }, [tileMap, mapW, mapH, cellSize, offset, showGrid, showLabels, wfcGrid, variants, selectedCell, decoratedRooms]);

  useEffect(() => { draw(); }, [draw]);

  // Auto-size canvas to container
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(() => {
      const canvas = canvasRef.current;
      if (canvas) {
        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight;
        draw();
      }
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [draw]);

  // ── Zoom ──
  const handleWheel = useCallback((e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -2 : 2;
    setCellSize(prev => Math.max(MIN_CELL, Math.min(MAX_CELL, prev + delta)));
  }, []);

  // ── Pan ──
  const handleMouseDown = useCallback((e) => {
    if (e.button === 1 || e.button === 0) {
      setIsDragging(true);
      setDragMoved(false);
      setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
    }
  }, [offset]);

  const handleMouseMove = useCallback((e) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStart.x - offset.x;
    const dy = e.clientY - dragStart.y - offset.y;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
      setDragMoved(true);
    }
    setOffset({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  }, [isDragging, dragStart, offset]);

  const handleMouseUp = useCallback((e) => {
    const wasDragging = isDragging;
    setIsDragging(false);

    // If panning didn't move, treat as click to select a module cell
    if (wasDragging && !dragMoved && wfcGrid && e.button === 0) {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left - offset.x;
      const my = e.clientY - rect.top - offset.y;
      const modPx = MODULE_SIZE * cellSize;
      const col = Math.floor(mx / modPx);
      const row = Math.floor(my / modPx);
      const gridRows = wfcGrid.length;
      const gridCols = wfcGrid[0]?.length || 0;

      if (row >= 0 && row < gridRows && col >= 0 && col < gridCols) {
        setSelectedCell(prev => {
          if (prev && prev.row === row && prev.col === col) return null; // Toggle off
          return { row, col };
        });
        // Position picker near the click but within the preview area
        setPickerPos({ x: e.clientX - rect.left + 12, y: e.clientY - rect.top + 12 });
      } else {
        setSelectedCell(null);
      }
    }
  }, [isDragging, dragMoved, wfcGrid, offset, cellSize]);

  // Close picker on escape
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Escape') setSelectedCell(null);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const handleSwapVariant = useCallback((variant) => {
    if (!selectedCell || !onSwapModule) return;
    onSwapModule(selectedCell.row, selectedCell.col, variant);
    setSelectedCell(null);
  }, [selectedCell, onSwapModule]);

  const handleReset = useCallback(() => {
    setOffset({ x: 0, y: 0 });
    setCellSize(DEFAULT_CELL);
    setSelectedCell(null);
  }, []);

  if (!tileMap) {
    return (
      <div className="preview-canvas empty-preview">
        <p>Generate a dungeon to see the preview here.</p>
        <p className="hint">Configure settings in the Generator panel, then click Generate.</p>
      </div>
    );
  }

  return (
    <div className="preview-canvas">
      <div className="preview-toolbar">
        <button onClick={handleReset} title="Reset zoom/pan">Reset View</button>
        <label className="checkbox-label">
          <input type="checkbox" checked={showGrid} onChange={(e) => setShowGrid(e.target.checked)} />
          Module Grid
        </label>
        <label className="checkbox-label">
          <input type="checkbox" checked={showLabels} onChange={(e) => setShowLabels(e.target.checked)} />
          Tile Labels
        </label>
        <span className="zoom-info">Zoom: {cellSize}px</span>
        <span className="map-info">{mapW}×{mapH} tiles</span>
        {selectedCell && (
          <span className="cell-info">
            Cell [{selectedCell.row},{selectedCell.col}]
            {currentVariant && `: ${currentVariant.sourceName}${currentVariant.rotation ? ` ${currentVariant.rotation}°` : ''}`}
          </span>
        )}
      </div>
      <div
        ref={containerRef}
        className="preview-container"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => setIsDragging(false)}
      >
        <canvas ref={canvasRef} className="preview-canvas-el" />

        {/* Module Picker Overlay */}
        {selectedCell && onSwapModule && (
          <ModulePicker
            pos={pickerPos}
            containerRef={containerRef}
            currentVariant={currentVariant}
            groupedVariants={displayGrouped}
            compatibleCount={displayCount}
            showAll={showAllModules}
            onToggleShowAll={() => setShowAllModules(prev => !prev)}
            totalCount={allVariants.length}
            compatibleOnlyCount={compatibleVariants.length}
            onSelect={handleSwapVariant}
            onClose={() => setSelectedCell(null)}
          />
        )}
      </div>
    </div>
  );
}

/** Purpose → color badge */
const PURPOSE_COLORS = {
  empty: '#666',
  corridor: '#68a',
  spawn: '#8c8',
  enemy: '#c66',
  loot: '#cc8',
  boss: '#c6c',
};

/** Module picker popover shown when clicking a cell in the preview */
function ModulePicker({ pos, containerRef, currentVariant, groupedVariants, compatibleCount, showAll, onToggleShowAll, totalCount, compatibleOnlyCount, onSelect, onClose }) {
  const pickerRef = useRef(null);

  // Clamp picker position to stay within container bounds
  const [adjustedPos, setAdjustedPos] = useState(pos);
  useEffect(() => {
    const picker = pickerRef.current;
    const container = containerRef.current;
    if (!picker || !container) {
      setAdjustedPos(pos);
      return;
    }
    const cRect = container.getBoundingClientRect();
    const pRect = picker.getBoundingClientRect();
    let x = pos.x;
    let y = pos.y;
    if (x + pRect.width > cRect.width) x = Math.max(4, cRect.width - pRect.width - 4);
    if (y + pRect.height > cRect.height) y = Math.max(4, cRect.height - pRect.height - 4);
    setAdjustedPos({ x, y });
  }, [pos, containerRef]);

  return (
    <div
      ref={pickerRef}
      className="module-picker"
      style={{ left: adjustedPos.x, top: adjustedPos.y }}
      onMouseDown={(e) => e.stopPropagation()} // Don't start panning when clicking the picker
    >
      <div className="picker-header">
        <span className="picker-title">Swap Module</span>
        <button className="picker-close" onClick={onClose}>×</button>
      </div>

      {currentVariant && (
        <div className="picker-current">
          <span className="picker-current-label">Current:</span>
          <span className="picker-current-name">{currentVariant.sourceName}</span>
          {currentVariant.rotation > 0 && <span className="picker-rotation">{currentVariant.rotation}°</span>}
          <span className="picker-purpose" style={{ background: PURPOSE_COLORS[currentVariant.purpose] || '#666' }}>
            {currentVariant.purpose}
          </span>
        </div>
      )}

      <div className="picker-compat-count">
        {showAll ? (
          <>
            <span className="picker-count-all">All {totalCount} variants</span>
            <span className="picker-count-compat"> ({compatibleOnlyCount} compatible)</span>
          </>
        ) : (
          <>{compatibleCount} compatible variant{compatibleCount !== 1 ? 's' : ''}</>
        )}
      </div>

      <div className="picker-filter-toggle">
        <label className="picker-show-all-label">
          <input
            type="checkbox"
            checked={showAll}
            onChange={onToggleShowAll}
          />
          Show All Modules
        </label>
        {showAll && <span className="picker-warn">Socket mismatches may occur</span>}
      </div>

      <div className="picker-list">
        {groupedVariants.length === 0 && (
          <div className="picker-empty">No compatible modules found</div>
        )}
        {groupedVariants.map(group => (
          <div key={group.name} className="picker-group">
            <div className="picker-group-header">
              <span className="picker-group-name">{group.name}</span>
              <span className="picker-purpose" style={{ background: PURPOSE_COLORS[group.purpose] || '#666' }}>
                {group.purpose}
              </span>
            </div>
            <div className="picker-group-variants">
              {group.variants.map((v, i) => {
                const isCurrent = currentVariant &&
                  v.sourceId === currentVariant.sourceId &&
                  v.rotation === currentVariant.rotation;
                return (
                  <button
                    key={`${v.sourceId}_${v.rotation}`}
                    className={`picker-variant-btn ${isCurrent ? 'current' : ''}`}
                    onClick={() => onSelect(v)}
                    title={`${v.sourceName} ${v.rotation}° — click to place`}
                  >
                    <span className="variant-rotation">
                      {v.rotation === 0 ? '0°' : `${v.rotation}°`}
                    </span>
                    <MiniModulePreview tiles={v.tiles} />
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Tiny inline canvas preview of a module's tiles */
function MiniModulePreview({ tiles }) {
  const canvasRef = useRef(null);
  const size = MODULE_SIZE;
  const px = 4; // pixels per tile

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !tiles) return;
    const ctx = canvas.getContext('2d');
    for (let r = 0; r < size; r++) {
      for (let c = 0; c < size; c++) {
        ctx.fillStyle = TILE_COLORS[tiles[r]?.[c]] || '#444';
        ctx.fillRect(c * px, r * px, px, px);
      }
    }
  }, [tiles]);

  return <canvas ref={canvasRef} width={size * px} height={size * px} className="mini-module-canvas" />;
}
