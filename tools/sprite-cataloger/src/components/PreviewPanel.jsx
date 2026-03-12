import React, { useRef, useEffect, useMemo } from 'react';
import { useAtlas } from '../context/AtlasContext';

/**
 * PreviewPanel — Shows the selected sprite at game scale (40px tile size).
 * Also shows a zoomed-in raw-pixel view for precision checking.
 */
const GAME_TILE = 40; // matches TILE_SIZE in ArenaRenderer.js

export default function PreviewPanel() {
  const { state } = useAtlas();
  const canvasRef = useRef(null);
  const zoomedRef = useRef(null);
  const imgRef = useRef(null);

  const sprite = state.selectedSpriteId ? state.sprites[state.selectedSpriteId] : null;

  // Keep img ref in sync
  useEffect(() => {
    if (!state.sheetSrc) { imgRef.current = null; return; }
    const img = new Image();
    img.onload = () => { imgRef.current = img; };
    img.src = state.sheetSrc;
  }, [state.sheetSrc]);

  // Draw preview
  useEffect(() => {
    const canvas = canvasRef.current;
    const zoomed = zoomedRef.current;
    if (!canvas || !zoomed) return;
    const ctx = canvas.getContext('2d');
    const zCtx = zoomed.getContext('2d');

    // Clear
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    zCtx.fillStyle = '#1a1a2e';
    zCtx.fillRect(0, 0, zoomed.width, zoomed.height);

    if (!sprite || !imgRef.current) {
      ctx.fillStyle = '#666';
      ctx.font = '12px Segoe UI';
      ctx.textAlign = 'center';
      ctx.fillText('No sprite selected', canvas.width / 2, canvas.height / 2);
      return;
    }

    // Checkerboard
    drawCheckerboard(ctx, canvas.width, canvas.height);
    drawCheckerboard(zCtx, zoomed.width, zoomed.height);

    // Game-scale preview (fit to GAME_TILE)
    const scale = Math.min(GAME_TILE / sprite.w, GAME_TILE / sprite.h);
    const dw = sprite.w * scale;
    const dh = sprite.h * scale;
    const dx = (canvas.width - dw) / 2;
    const dy = (canvas.height - dh) / 2;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(imgRef.current, sprite.x, sprite.y, sprite.w, sprite.h, dx, dy, dw, dh);

    // Zoomed pixel view (4x zoom)
    const zoomLevel = 4;
    const zdw = sprite.w * zoomLevel;
    const zdh = sprite.h * zoomLevel;
    const zdx = (zoomed.width - zdw) / 2;
    const zdy = (zoomed.height - zdh) / 2;
    zCtx.imageSmoothingEnabled = false;
    zCtx.drawImage(imgRef.current, sprite.x, sprite.y, sprite.w, sprite.h, zdx, zdy, zdw, zdh);

    // Draw grid on zoomed view
    zCtx.strokeStyle = '#ffffff22';
    zCtx.lineWidth = 0.5;
    for (let px = 0; px < sprite.w; px++) {
      const x = zdx + px * zoomLevel;
      zCtx.beginPath();
      zCtx.moveTo(x, zdy);
      zCtx.lineTo(x, zdy + zdh);
      zCtx.stroke();
    }
    for (let py = 0; py < sprite.h; py++) {
      const y = zdy + py * zoomLevel;
      zCtx.beginPath();
      zCtx.moveTo(zdx, y);
      zCtx.lineTo(zdx + zdw, y);
      zCtx.stroke();
    }
  }, [sprite, state.sheetSrc]);

  return (
    <div className="panel preview-panel">
      <h3 className="panel-title">Preview</h3>

      <div className="preview-section">
        <span className="preview-label">Game Scale ({GAME_TILE}px)</span>
        <canvas ref={canvasRef} width={80} height={80} className="preview-canvas" />
      </div>

      <div className="preview-section">
        <span className="preview-label">Zoomed (4×)</span>
        <canvas ref={zoomedRef} width={200} height={200} className="preview-canvas zoomed" />
      </div>

      {sprite && (
        <div className="preview-info">
          <span>{sprite.name}</span>
          <span className="muted">{sprite.w}×{sprite.h}px</span>
        </div>
      )}
    </div>
  );
}

function drawCheckerboard(ctx, w, h) {
  const size = 6;
  for (let y = 0; y < h; y += size) {
    for (let x = 0; x < w; x += size) {
      ctx.fillStyle = ((x / size + y / size) % 2 === 0) ? '#2a2a3e' : '#22223a';
      ctx.fillRect(x, y, size, size);
    }
  }
}
