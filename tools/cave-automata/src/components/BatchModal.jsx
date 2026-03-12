// ─────────────────────────────────────────────────────────
// BatchModal.jsx — Modal for batch generation results
//
// Shows a ranked list of generated caves with mini-previews.
// User can pick the best one to load into the editor.
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect } from 'react';
import { TILE_COLORS } from '../utils/tileColors.js';

export default function BatchModal({ results, onSelect, onClose }) {
  if (!results || results.length === 0) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Batch Generation Results ({results.length} maps)</h3>
          <button onClick={onClose} className="btn btn-small">Close</button>
        </div>
        <p className="modal-subtitle">Ranked by connectivity + openness. Click to select.</p>
        <div className="batch-grid">
          {results.map((result, idx) => (
            <BatchPreview
              key={idx}
              result={result}
              rank={idx + 1}
              onClick={() => onSelect(result)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function BatchPreview({ result, rank, onClick }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const tileMap = result.tileMap;
    const h = tileMap.length;
    const w = tileMap[0]?.length || 0;

    const cellSize = Math.max(2, Math.min(Math.floor(140 / w), Math.floor(140 / h)));
    canvas.width = w * cellSize;
    canvas.height = h * cellSize;

    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        ctx.fillStyle = TILE_COLORS[tileMap[y][x]] || '#333';
        ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);
      }
    }
  }, [result]);

  return (
    <div className="batch-item" onClick={onClick}>
      <div className="batch-rank">#{rank}</div>
      <canvas ref={canvasRef} className="batch-canvas" />
      <div className="batch-stats">
        <span>Regions: {result.regionCount}</span>
        <span>Floor: {result.floorPercent}%</span>
        <span>Rooms: {result.roomCount}</span>
        <span>Score: {result.score.toFixed(1)}</span>
        <span>Seed: {result.seed}</span>
      </div>
    </div>
  );
}
