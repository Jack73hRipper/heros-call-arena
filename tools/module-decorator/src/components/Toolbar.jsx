// ─────────────────────────────────────────────────────────
// Toolbar.jsx — Top bar with tabs, undo/redo, and stats
// ─────────────────────────────────────────────────────────

import React from 'react';

export default function Toolbar({
  activeTab,
  onTabChange,
  undoCount,
  redoCount,
  onUndo,
  onRedo,
  decoratedCount,
  totalModules,
}) {
  return (
    <div className="toolbar">
      <div className="toolbar-left">
        <h1 className="toolbar-title">Module Sprite Decorator</h1>
        <span className="toolbar-subtitle">Arena MMO</span>
      </div>

      <div className="toolbar-center">
        <button
          className={`tab-btn ${activeTab === 'editor' ? 'active' : ''}`}
          onClick={() => onTabChange('editor')}
        >
          Editor
        </button>
        <button
          className={`tab-btn ${activeTab === 'preview' ? 'active' : ''}`}
          onClick={() => onTabChange('preview')}
        >
          Dungeon Preview
        </button>
      </div>

      <div className="toolbar-right">
        <button
          className="tool-btn"
          onClick={onUndo}
          disabled={undoCount === 0}
          title="Undo (Ctrl+Z)"
        >
          ↩ {undoCount > 0 && <span className="badge">{undoCount}</span>}
        </button>
        <button
          className="tool-btn"
          onClick={onRedo}
          disabled={redoCount === 0}
          title="Redo (Ctrl+Y)"
        >
          ↪ {redoCount > 0 && <span className="badge">{redoCount}</span>}
        </button>
        <span className="toolbar-stats">
          {decoratedCount}/{totalModules} decorated
        </span>
      </div>
    </div>
  );
}
