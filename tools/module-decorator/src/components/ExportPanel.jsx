// ─────────────────────────────────────────────────────────
// ExportPanel.jsx — Export/import sprite library and atlas
// ─────────────────────────────────────────────────────────

import React, { useCallback } from 'react';

export default function ExportPanel({
  onExport,
  onImportLibrary,
  onImportAtlas,
  atlasData,
  decoratedCount,
  totalModules,
}) {
  // Export sprite library as JSON download
  const handleExportDownload = useCallback(() => {
    const data = onExport();
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'module-sprites.json';
    a.click();
    URL.revokeObjectURL(url);
  }, [onExport]);

  // Copy to clipboard
  const handleCopyClipboard = useCallback(() => {
    const data = onExport();
    const json = JSON.stringify(data, null, 2);
    navigator.clipboard.writeText(json).then(() => {
      alert('Sprite library JSON copied to clipboard!');
    }).catch(err => {
      console.error('Failed to copy:', err);
    });
  }, [onExport]);

  // Import sprite library from JSON file
  const handleImportLibrary = useCallback(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        try {
          const data = JSON.parse(ev.target.result);
          if (data.modules) {
            onImportLibrary(data);
            alert(`Imported ${Object.keys(data.modules).length} module sprite maps!`);
          } else {
            alert('Invalid sprite library JSON — must have "modules" field.');
          }
        } catch (err) {
          alert('Failed to parse JSON: ' + err.message);
        }
      };
      reader.readAsText(file);
    };
    input.click();
  }, [onImportLibrary]);

  // Import atlas JSON
  const handleImportAtlas = useCallback(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        try {
          const data = JSON.parse(ev.target.result);
          if (data.sprites && data.sheetWidth) {
            onImportAtlas(data);
            alert('Atlas JSON loaded successfully! Now load the atlas image.');
          } else {
            alert('Invalid atlas JSON — must have "sprites" and "sheetWidth" fields.');
          }
        } catch (err) {
          alert('Failed to parse atlas JSON: ' + err.message);
        }
      };
      reader.readAsText(file);
    };
    input.click();
  }, [onImportAtlas]);

  return (
    <div className="export-panel">
      <div className="panel-section">
        <h4>Export</h4>
        <p className="section-desc">
          Export sprite maps for {decoratedCount} decorated module{decoratedCount !== 1 ? 's' : ''} out of {totalModules} total.
        </p>
        <div className="export-buttons">
          <button
            className="action-btn primary"
            onClick={handleExportDownload}
            disabled={decoratedCount === 0}
          >
            Export module-sprites.json
          </button>
          <button
            className="action-btn"
            onClick={handleCopyClipboard}
            disabled={decoratedCount === 0}
          >
            Copy to Clipboard
          </button>
        </div>
      </div>

      <div className="panel-section">
        <h4>Import</h4>
        <div className="export-buttons">
          <button className="action-btn" onClick={handleImportLibrary}>
            Import Sprite Library
          </button>
          <button className="action-btn" onClick={handleImportAtlas}>
            Import Atlas JSON
          </button>
        </div>
      </div>

      <div className="panel-section">
        <h4>Atlas Info</h4>
        <div className="stat-row">
          <span>Sheet:</span>
          <span className="stat-value">{atlasData.sheetFile}</span>
        </div>
        <div className="stat-row">
          <span>Size:</span>
          <span className="stat-value">{atlasData.sheetWidth}×{atlasData.sheetHeight}</span>
        </div>
        <div className="stat-row">
          <span>Tile size:</span>
          <span className="stat-value">{atlasData.cellW}×{atlasData.cellH}</span>
        </div>
        <div className="stat-row">
          <span>Named sprites:</span>
          <span className="stat-value">{atlasData.sprites.length}</span>
        </div>
      </div>
    </div>
  );
}
