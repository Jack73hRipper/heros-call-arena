// ─────────────────────────────────────────────────────────
// Toolbar.jsx — Top toolbar with actions and stats
// ─────────────────────────────────────────────────────────

import React from 'react';

export default function Toolbar({
  onNew, onSave, onDuplicate, onExport, onExportAll, onImport,
  onCopy, onPaste, onUndo, onRedo, onRandomize,
  canUndo, canRedo, presetName, particleCount, fps,
  viewMode, compoundMode, onToggleCompound, compoundLayerCount,
  projectileMode, onToggleProjectile,
}) {
  return (
    <div className="toolbar">
      <div className="toolbar-left">
        <span className="toolbar-title">⚡ Particle Lab</span>
        <span className="toolbar-preset-name">{presetName}</span>
        <div className="toolbar-sep" />
        <button
          className={`toolbar-mode-btn ${compoundMode ? 'mode-active' : ''}`}
          onClick={onToggleCompound}
          title="Toggle Compound Effect Preview — stack multiple presets as layers"
        >
          {compoundMode ? '🔷 Compound' : '◇ Compound'}
          {compoundMode && compoundLayerCount > 0 && (
            <span className="mode-count">{compoundLayerCount}</span>
          )}
        </button>
        <button
          className={`toolbar-mode-btn ${projectileMode ? 'mode-active mode-projectile' : ''}`}
          onClick={onToggleProjectile}
          title="Toggle Projectile Preview — test trail/impact effects traveling A→B"
        >
          {projectileMode ? '🚀 Projectile' : '→ Projectile'}
        </button>
      </div>

      <div className="toolbar-actions">
        <button onClick={onNew} title="New blank preset">New</button>
        <button onClick={onSave} title="Save preset (Ctrl+S)">Save</button>
        <button onClick={onDuplicate} title="Duplicate current preset">Duplicate</button>
        <div className="toolbar-sep" />
        <button onClick={onUndo} disabled={!canUndo} title="Undo (Ctrl+Z)">Undo</button>
        <button onClick={onRedo} disabled={!canRedo} title="Redo (Ctrl+Y)">Redo</button>
        <div className="toolbar-sep" />
        <button onClick={onImport} title="Import JSON preset(s)">Import</button>
        <button onClick={onExport} title="Export current preset (Ctrl+E)">Export</button>
        <button onClick={onExportAll} title="Export all presets as a bundle">Export All</button>
        <div className="toolbar-sep" />
        <button onClick={onCopy} title="Copy preset JSON to clipboard">Copy</button>
        <button onClick={onPaste} title="Paste preset JSON from clipboard">Paste</button>
        <div className="toolbar-sep" />
        <button onClick={onRandomize} title="Generate a random effect" className="btn-randomize">🎲 Random</button>
      </div>

      <div className="toolbar-stats">
        <span className="stat" title="Active particles">
          ● {particleCount}
        </span>
        <span className={`stat ${fps < 30 ? 'stat-warn' : ''}`} title="Frames per second">
          {fps} FPS
        </span>
      </div>
    </div>
  );
}
