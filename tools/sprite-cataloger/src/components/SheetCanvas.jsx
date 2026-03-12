import React, { useRef, useEffect, useCallback } from 'react';
import { useAtlas } from '../context/AtlasContext';

/**
 * SheetCanvas — Main canvas showing the sprite sheet with grid overlay.
 * Supports: zoom, pan, click-to-select/add sprites, hover highlighting.
 */
export default function SheetCanvas() {
  const { state, actions } = useAtlas();
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const isPanning = useRef(false);
  const lastMouse = useRef({ x: 0, y: 0 });

  // Load image when sheetSrc changes
  useEffect(() => {
    if (!state.sheetSrc) {
      imgRef.current = null;
      return;
    }
    const img = new Image();
    img.onload = () => {
      imgRef.current = img;
      draw();
    };
    img.src = state.sheetSrc;
  }, [state.sheetSrc]);

  // Redraw whenever relevant state changes
  useEffect(() => {
    draw();
  }, [state.grid, state.sprites, state.selectedSpriteId, state.hoveredCell,
      state.zoom, state.panX, state.panY, state.multiSelect, state.categories]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const { width, height } = canvas.getBoundingClientRect();
    canvas.width = width * window.devicePixelRatio;
    canvas.height = height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    // Dark background
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, width, height);

    if (!imgRef.current) {
      // Draw placeholder
      ctx.fillStyle = '#666';
      ctx.font = '18px Segoe UI';
      ctx.textAlign = 'center';
      ctx.fillText('Drop a sprite sheet here or use Import', width / 2, height / 2 - 10);
      ctx.font = '13px Segoe UI';
      ctx.fillStyle = '#888';
      ctx.fillText('Supports PNG images', width / 2, height / 2 + 15);
      return;
    }

    ctx.save();
    ctx.translate(state.panX, state.panY);
    ctx.scale(state.zoom, state.zoom);

    // Draw checkerboard background (transparency indicator)
    drawCheckerboard(ctx, state.sheetWidth, state.sheetHeight);

    // Draw the sprite sheet image
    ctx.imageSmoothingEnabled = state.zoom < 2;
    ctx.drawImage(imgRef.current, 0, 0);

    // Draw grid overlay
    drawGrid(ctx, state);

    // Draw cataloged sprites (colored borders)
    drawCatalogedSprites(ctx, state);

    // Draw hovered cell highlight
    if (state.hoveredCell) {
      const { row, col } = state.hoveredCell;
      const { cellW, cellH, offsetX, offsetY, spacingX, spacingY } = state.grid;
      const x = offsetX + col * (cellW + spacingX);
      const y = offsetY + row * (cellH + spacingY);
      ctx.strokeStyle = '#ffffff88';
      ctx.lineWidth = 2 / state.zoom;
      ctx.strokeRect(x, y, cellW, cellH);
    }

    ctx.restore();
  }, [state]);

  // ─── Mouse Handlers ───────────────────────────────────────────
  const screenToSheet = useCallback((clientX, clientY) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const sx = (clientX - rect.left - state.panX) / state.zoom;
    const sy = (clientY - rect.top - state.panY) / state.zoom;
    return { x: sx, y: sy };
  }, [state.panX, state.panY, state.zoom]);

  const getCellAt = useCallback((sheetX, sheetY) => {
    const { cellW, cellH, offsetX, offsetY, spacingX, spacingY } = state.grid;
    const col = Math.floor((sheetX - offsetX) / (cellW + spacingX));
    const row = Math.floor((sheetY - offsetY) / (cellH + spacingY));
    if (col < 0 || row < 0) return null;
    const maxCols = Math.floor((state.sheetWidth - offsetX) / (cellW + spacingX));
    const maxRows = Math.floor((state.sheetHeight - offsetY) / (cellH + spacingY));
    if (col >= maxCols || row >= maxRows) return null;
    return { row, col };
  }, [state.grid, state.sheetWidth, state.sheetHeight]);

  const findSpriteAtCell = useCallback((row, col) => {
    return Object.values(state.sprites).find(s => s.row === row && s.col === col);
  }, [state.sprites]);

  const handleMouseDown = useCallback((e) => {
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
      // Middle click or Alt+left = start panning
      isPanning.current = true;
      lastMouse.current = { x: e.clientX, y: e.clientY };
      e.preventDefault();
      return;
    }

    if (e.button === 0 && imgRef.current) {
      const pos = screenToSheet(e.clientX, e.clientY);
      if (!pos) return;
      const cell = getCellAt(pos.x, pos.y);
      if (!cell) {
        actions.clearSelection();
        return;
      }

      const existing = findSpriteAtCell(cell.row, cell.col);

      if (e.shiftKey) {
        // Shift+click: multi-select
        if (existing) {
          actions.toggleMultiSelect(existing.id);
        }
        return;
      }

      if (existing) {
        actions.selectSprite(existing.id);
      } else {
        // Add new sprite at this cell
        const { cellW, cellH, offsetX, offsetY, spacingX, spacingY } = state.grid;
        actions.addSprite({
          x: offsetX + cell.col * (cellW + spacingX),
          y: offsetY + cell.row * (cellH + spacingY),
          w: cellW,
          h: cellH,
          row: cell.row,
          col: cell.col,
        });
      }
    }
  }, [screenToSheet, getCellAt, findSpriteAtCell, actions, state.grid]);

  const handleMouseMove = useCallback((e) => {
    if (isPanning.current) {
      const dx = e.clientX - lastMouse.current.x;
      const dy = e.clientY - lastMouse.current.y;
      actions.setPan(state.panX + dx, state.panY + dy);
      lastMouse.current = { x: e.clientX, y: e.clientY };
      return;
    }

    if (imgRef.current) {
      const pos = screenToSheet(e.clientX, e.clientY);
      if (!pos) return;
      const cell = getCellAt(pos.x, pos.y);
      actions.setHoveredCell(cell);
    }
  }, [screenToSheet, getCellAt, actions, state.panX, state.panY]);

  const handleMouseUp = useCallback(() => {
    isPanning.current = false;
  }, []);

  const handleWheel = useCallback((e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = state.zoom * delta;

    // Zoom toward cursor
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const newPanX = mx - (mx - state.panX) * (newZoom / state.zoom);
    const newPanY = my - (my - state.panY) * (newZoom / state.zoom);

    actions.setZoom(newZoom);
    actions.setPan(newPanX, newPanY);
  }, [state.zoom, state.panX, state.panY, actions]);

  // Handle drop (image files)
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    const file = e.dataTransfer?.files?.[0];
    if (file && file.type.startsWith('image/')) {
      loadImageFile(file, actions);
    }
  }, [actions]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="sheet-canvas"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onWheel={handleWheel}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      tabIndex={0}
    />
  );
}

// ─── Drawing Helpers ────────────────────────────────────────────

function drawCheckerboard(ctx, w, h) {
  const size = 8;
  for (let y = 0; y < h; y += size) {
    for (let x = 0; x < w; x += size) {
      ctx.fillStyle = ((x / size + y / size) % 2 === 0) ? '#2a2a3e' : '#22223a';
      ctx.fillRect(x, y, size, size);
    }
  }
}

function drawGrid(ctx, state) {
  const { cellW, cellH, offsetX, offsetY, spacingX, spacingY } = state.grid;
  const { sheetWidth, sheetHeight, zoom } = state;

  ctx.strokeStyle = '#4af59f33';
  ctx.lineWidth = 1 / zoom;

  const totalCellW = cellW + spacingX;
  const totalCellH = cellH + spacingY;
  const cols = Math.floor((sheetWidth - offsetX) / totalCellW);
  const rows = Math.floor((sheetHeight - offsetY) / totalCellH);

  for (let r = 0; r <= rows; r++) {
    const y = offsetY + r * totalCellH;
    ctx.beginPath();
    ctx.moveTo(offsetX, y);
    ctx.lineTo(offsetX + cols * totalCellW, y);
    ctx.stroke();
  }

  for (let c = 0; c <= cols; c++) {
    const x = offsetX + c * totalCellW;
    ctx.beginPath();
    ctx.moveTo(x, offsetY);
    ctx.lineTo(x, offsetY + rows * totalCellH);
    ctx.stroke();
  }
}

// Category colors for sprite overlays
const CATEGORY_COLORS = [
  '#4a9ff5', '#f54a4a', '#4af59f', '#f5c542',
  '#c44af5', '#f5884a', '#4af5f5', '#f54aa5',
  '#9ff54a', '#f5f54a', '#4a4af5', '#f54af5',
];

function getCategoryColor(categories, category) {
  const idx = categories.indexOf(category);
  return CATEGORY_COLORS[idx % CATEGORY_COLORS.length];
}

function drawCatalogedSprites(ctx, state) {
  const { sprites, selectedSpriteId, multiSelect, categories, zoom } = state;

  for (const sprite of Object.values(sprites)) {
    const color = getCategoryColor(categories, sprite.category);
    const isSelected = sprite.id === selectedSpriteId;
    const isMultiSelected = multiSelect.includes(sprite.id);

    // Fill with transparent category color
    ctx.fillStyle = color + '25';
    ctx.fillRect(sprite.x, sprite.y, sprite.w, sprite.h);

    // Border
    ctx.strokeStyle = isSelected ? '#ffffff' : isMultiSelected ? '#ffff00' : color + '99';
    ctx.lineWidth = (isSelected ? 3 : isMultiSelected ? 2 : 1.5) / zoom;
    ctx.strokeRect(sprite.x, sprite.y, sprite.w, sprite.h);

    // Small label
    const fontSize = Math.max(8, Math.min(12, sprite.w / 6));
    ctx.font = `${fontSize}px Segoe UI`;
    ctx.fillStyle = '#ffffffcc';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    const label = sprite.name.length > 12 ? sprite.name.slice(0, 11) + '…' : sprite.name;
    ctx.fillText(label, sprite.x + 2, sprite.y + 2);
  }
}

/**
 * Load an image file from a File object and set it as the sheet.
 */
export function loadImageFile(file, actions) {
  const reader = new FileReader();
  reader.onload = (e) => {
    const img = new Image();
    img.onload = () => {
      actions.setSheet(e.target.result, img.naturalWidth, img.naturalHeight, file.name);
    };
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
}
