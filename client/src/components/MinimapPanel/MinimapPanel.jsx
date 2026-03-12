import React, { useRef, useEffect, useMemo } from 'react';
import { drawMinimap, getMinimapSize, MINIMAP_TILE_NORMAL, MINIMAP_TILE_EXPANDED } from '../../canvas/minimapRenderer.js';

/**
 * MinimapPanel — Dedicated minimap component rendered as its own canvas
 * in the right panel of the Arena layout, above HUD/Party/Enemy panels.
 *
 * Two modes:
 *   - Normal  (default): 5px/tile, compact overview — always visible
 *   - Expanded (M key):  ~9px/tile, fills panel width — detailed view
 *
 * The minimap respects FOV / fog of war in both modes.
 */
export default function MinimapPanel({
  minimapMode = 'normal',   // 'normal' | 'expanded'
  gridWidth, gridHeight,
  isDungeon, tiles, tileLegend,
  doorStates, chestStates,
  obstacles,
  players,
  visibleTiles,
  revealedTiles,
  myPlayerId,
  myTeam,
  viewportOffsetX,
  viewportOffsetY,
  canvasPixelW,
  canvasPixelH,
  portal,
  currentTurn,
  isPvpve = false,
  bossRoom = null,
}) {
  const canvasRef = useRef(null);

  // Compute tile size to keep minimap a uniform fixed size regardless of map dimensions.
  const tileSize = useMemo(() => {
    const longest = Math.max(gridWidth, gridHeight);
    if (minimapMode === 'expanded') {
      return Math.max(2, Math.floor(380 / longest));
    }
    return Math.max(2, Math.floor(192 / longest));
  }, [minimapMode, gridWidth, gridHeight]);

  // Compute canvas dimensions
  const { width: canvasW, height: canvasH } = useMemo(
    () => getMinimapSize(gridWidth, gridHeight, tileSize),
    [gridWidth, gridHeight, tileSize]
  );

  // Re-render minimap on every relevant state change
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || gridWidth <= 0 || gridHeight <= 0) return;

    canvas.width = canvasW;
    canvas.height = canvasH;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    drawMinimap(ctx, {
      gridWidth, gridHeight,
      isDungeon, tiles, tileLegend,
      doorStates, chestStates,
      obstacles,
      players,
      visibleTiles,
      revealedTiles,
      myPlayerId,
      myTeam,
      viewportOffsetX,
      viewportOffsetY,
      canvasPixelW,
      canvasPixelH,
      portal,
      currentTurn,
      tileSize,
      isPvpve,
      bossRoom,
    });
  });

  // Don't render if no map data
  if (gridWidth <= 0 || gridHeight <= 0) return null;

  const isExpanded = minimapMode === 'expanded';

  return (
    <div className={`minimap-wrap ${isExpanded ? 'minimap-expanded' : 'minimap-normal'}`}>
      <canvas
        ref={canvasRef}
        width={canvasW}
        height={canvasH}
        className="minimap-canvas"
      />
    </div>
  );
}
