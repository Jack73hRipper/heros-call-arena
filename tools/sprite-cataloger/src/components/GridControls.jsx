import React, { useCallback } from 'react';
import { useAtlas } from '../context/AtlasContext';

/**
 * GridControls — Adjustable sliders for grid cell size, offset, and spacing.
 */
export default function GridControls() {
  const { state, actions } = useAtlas();
  const { cellW, cellH, offsetX, offsetY, spacingX, spacingY } = state.grid;

  const update = useCallback((field, value) => {
    actions.updateGrid({ [field]: value });
  }, [actions]);

  return (
    <div className="panel grid-controls">
      <h3 className="panel-title">Grid Settings</h3>

      <div className="control-row">
        <label>Cell Width</label>
        <input
          type="range" min="4" max="512" value={cellW}
          onChange={(e) => update('cellW', parseInt(e.target.value))}
        />
        <input
          type="number" min="1" max="2048" value={cellW}
          onChange={(e) => update('cellW', parseInt(e.target.value) || 1)}
          className="num-input"
        />
        <div className="nudge-btns">
          <button onClick={() => update('cellW', cellW - 1)} title="-1">−</button>
          <button onClick={() => update('cellW', cellW + 1)} title="+1">+</button>
        </div>
      </div>

      <div className="control-row">
        <label>Cell Height</label>
        <input
          type="range" min="4" max="512" value={cellH}
          onChange={(e) => update('cellH', parseInt(e.target.value))}
        />
        <input
          type="number" min="1" max="2048" value={cellH}
          onChange={(e) => update('cellH', parseInt(e.target.value) || 1)}
          className="num-input"
        />
        <div className="nudge-btns">
          <button onClick={() => update('cellH', cellH - 1)}>−</button>
          <button onClick={() => update('cellH', cellH + 1)}>+</button>
        </div>
      </div>

      <div className="control-row">
        <label>Offset X</label>
        <input
          type="range" min="0" max="128" value={offsetX}
          onChange={(e) => update('offsetX', parseInt(e.target.value))}
        />
        <input
          type="number" min="0" max="2048" value={offsetX}
          onChange={(e) => update('offsetX', parseInt(e.target.value) || 0)}
          className="num-input"
        />
        <div className="nudge-btns">
          <button onClick={() => update('offsetX', Math.max(0, offsetX - 1))}>−</button>
          <button onClick={() => update('offsetX', offsetX + 1)}>+</button>
        </div>
      </div>

      <div className="control-row">
        <label>Offset Y</label>
        <input
          type="range" min="0" max="128" value={offsetY}
          onChange={(e) => update('offsetY', parseInt(e.target.value))}
        />
        <input
          type="number" min="0" max="2048" value={offsetY}
          onChange={(e) => update('offsetY', parseInt(e.target.value) || 0)}
          className="num-input"
        />
        <div className="nudge-btns">
          <button onClick={() => update('offsetY', Math.max(0, offsetY - 1))}>−</button>
          <button onClick={() => update('offsetY', offsetY + 1)}>+</button>
        </div>
      </div>

      <div className="control-row">
        <label>Spacing X</label>
        <input
          type="range" min="0" max="32" value={spacingX}
          onChange={(e) => update('spacingX', parseInt(e.target.value))}
        />
        <input
          type="number" min="0" max="128" value={spacingX}
          onChange={(e) => update('spacingX', parseInt(e.target.value) || 0)}
          className="num-input"
        />
      </div>

      <div className="control-row">
        <label>Spacing Y</label>
        <input
          type="range" min="0" max="32" value={spacingY}
          onChange={(e) => update('spacingY', parseInt(e.target.value))}
        />
        <input
          type="number" min="0" max="128" value={spacingY}
          onChange={(e) => update('spacingY', parseInt(e.target.value) || 0)}
          className="num-input"
        />
      </div>

      {state.sheetWidth > 0 && (
        <div className="grid-info">
          {Math.floor((state.sheetWidth - offsetX) / (cellW + spacingX))} cols
          × {Math.floor((state.sheetHeight - offsetY) / (cellH + spacingY))} rows
        </div>
      )}
    </div>
  );
}
