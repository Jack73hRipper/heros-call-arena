// ─────────────────────────────────────────────────────────
// LayerPanel.jsx — Layer visibility, opacity, and auto-decorate controls
// ─────────────────────────────────────────────────────────

import React from 'react';
import { AUTO_DECORATE_PRESETS } from '../engine/autoDecorator.js';

export default function LayerPanel({
  activeLayer,
  onSetActiveLayer,
  showGameplayLayer,
  showBaseLayer,
  showOverlayLayer,
  onToggleGameplay,
  onToggleBase,
  onToggleOverlay,
  baseOpacity,
  overlayOpacity,
  gameplayOpacity,
  onBaseOpacityChange,
  onOverlayOpacityChange,
  onGameplayOpacityChange,
  stats,
  onAutoDecorate,
  onAutoDecorateAll,
  onClearModule,
}) {
  return (
    <div className="layer-panel">
      {/* Active Layer Selection */}
      <div className="panel-section">
        <h4>Paint Target</h4>
        <div className="layer-buttons">
          <button
            className={`layer-btn ${activeLayer === 'base' ? 'active base-active' : ''}`}
            onClick={() => onSetActiveLayer('base')}
          >
            🎨 Base
          </button>
          <button
            className={`layer-btn ${activeLayer === 'overlay' ? 'active overlay-active' : ''}`}
            onClick={() => onSetActiveLayer('overlay')}
          >
            ✨ Overlay
          </button>
        </div>
      </div>

      {/* Layer Visibility */}
      <div className="panel-section">
        <h4>Layer Visibility</h4>
        <div className="layer-toggle">
          <label>
            <input type="checkbox" checked={showBaseLayer} onChange={onToggleBase} />
            Base Layer
          </label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={baseOpacity}
            onChange={e => onBaseOpacityChange(parseFloat(e.target.value))}
            disabled={!showBaseLayer}
          />
          <span className="opacity-val">{Math.round(baseOpacity * 100)}%</span>
        </div>
        <div className="layer-toggle">
          <label>
            <input type="checkbox" checked={showOverlayLayer} onChange={onToggleOverlay} />
            Overlay Layer
          </label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={overlayOpacity}
            onChange={e => onOverlayOpacityChange(parseFloat(e.target.value))}
            disabled={!showOverlayLayer}
          />
          <span className="opacity-val">{Math.round(overlayOpacity * 100)}%</span>
        </div>
        <div className="layer-toggle">
          <label>
            <input type="checkbox" checked={showGameplayLayer} onChange={onToggleGameplay} />
            Gameplay Ghost
          </label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={gameplayOpacity}
            onChange={e => onGameplayOpacityChange(parseFloat(e.target.value))}
            disabled={!showGameplayLayer}
          />
          <span className="opacity-val">{Math.round(gameplayOpacity * 100)}%</span>
        </div>
      </div>

      {/* Stats */}
      <div className="panel-section">
        <h4>Current Module Stats</h4>
        <div className="stat-row">
          <span>Base sprites:</span>
          <span className="stat-value">{stats.baseCount}/36</span>
        </div>
        <div className="stat-row">
          <span>Overlay sprites:</span>
          <span className="stat-value">{stats.overlayCount}/36</span>
        </div>
      </div>

      {/* Auto Decorate */}
      <div className="panel-section">
        <h4>Auto-Decorate</h4>
        <p className="section-desc">Apply rule-based sprites to this module based on tile types.</p>
        <div className="auto-decorate-buttons">
          {Object.keys(AUTO_DECORATE_PRESETS).map(name => (
            <button
              key={name}
              className="small-btn"
              onClick={() => onAutoDecorate(name)}
              title={`Auto-decorate with ${name} style`}
            >
              {name}
            </button>
          ))}
        </div>
        <div className="auto-decorate-actions">
          <button className="small-btn warning" onClick={onClearModule}>
            Clear Module
          </button>
          <button
            className="small-btn"
            onClick={() => onAutoDecorateAll('Grimdark Brick')}
            title="Auto-decorate all undecorated modules"
          >
            Auto-Decorate All
          </button>
        </div>
      </div>
    </div>
  );
}
