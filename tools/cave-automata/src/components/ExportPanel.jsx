// ─────────────────────────────────────────────────────────
// ExportPanel.jsx — Export/import JSON, save to gallery, batch generate
// ─────────────────────────────────────────────────────────

import React, { useRef } from 'react';

export default function ExportPanel({
  onExport,
  onImport,
  onSaveToGallery,
  onLoadFromGallery,
  gallery,
  onDeleteFromGallery,
  onBatchGenerate,
  batchCount,
  onBatchCountChange,
  onUndo,
  onRedo,
  canUndo,
  canRedo,
}) {
  const fileInputRef = useRef(null);

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const json = JSON.parse(ev.target.result);
        onImport(json);
      } catch (err) {
        alert('Invalid JSON file: ' + err.message);
      }
    };
    reader.readAsText(file);
    // Reset so same file can be re-imported
    e.target.value = '';
  };

  return (
    <div className="panel export-panel">
      <h3 className="panel-title">History</h3>
      <div className="param-group btn-row">
        <button onClick={onUndo} className="btn btn-secondary" disabled={!canUndo} title="Undo (Ctrl+Z)">
          Undo
        </button>
        <button onClick={onRedo} className="btn btn-secondary" disabled={!canRedo} title="Redo (Ctrl+Y)">
          Redo
        </button>
      </div>

      <h3 className="panel-title" style={{ marginTop: 16 }}>Export / Import</h3>

      <div className="param-group">
        <button onClick={onExport} className="btn btn-primary btn-full">
          Export JSON
        </button>
        <span className="param-hint">Download game-compatible map JSON</span>
      </div>

      <div className="param-group">
        <button onClick={handleImportClick} className="btn btn-secondary btn-full">
          Import JSON
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
        <span className="param-hint">Load an existing map file</span>
      </div>

      <h3 className="panel-title" style={{ marginTop: 16 }}>Batch Generate</h3>
      <div className="param-group">
        <label className="param-label">
          Count: {batchCount}
          <input
            type="range"
            min={2}
            max={20}
            value={batchCount}
            onChange={e => onBatchCountChange(parseInt(e.target.value))}
            className="input-range"
          />
        </label>
        <button onClick={onBatchGenerate} className="btn btn-secondary btn-full">
          Batch Generate & Rank
        </button>
        <span className="param-hint">Generate N maps, rank by quality</span>
      </div>

      <h3 className="panel-title" style={{ marginTop: 16 }}>Saved Maps ({gallery.length})</h3>

      <div className="param-group">
        <button onClick={onSaveToGallery} className="btn btn-secondary btn-full">
          Save Current to Gallery
        </button>
      </div>

      <div className="gallery-list">
        {gallery.length === 0 && (
          <p className="panel-empty">No saved maps yet</p>
        )}
        {gallery.map((item, idx) => (
          <div key={item.id} className="gallery-item">
            <div className="gallery-info" onClick={() => onLoadFromGallery(idx)}>
              <span className="gallery-name">{item.name}</span>
              <span className="gallery-meta">{item.width}x{item.height} — {item.date}</span>
            </div>
            <button
              onClick={() => onDeleteFromGallery(idx)}
              className="btn btn-small btn-danger"
              title="Delete"
            >
              X
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
