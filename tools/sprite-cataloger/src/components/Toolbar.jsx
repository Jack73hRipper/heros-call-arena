import React, { useRef, useCallback } from 'react';
import { useAtlas } from '../context/AtlasContext';
import { loadImageFile } from './SheetCanvas';
import { exportAtlasJSON, downloadJSON, parseAtlasJSON } from '../utils/exporters';
import { detectGrid, suggestGridSizes } from '../utils/gridDetector';

/**
 * Toolbar — Top bar with import/export actions and grid auto-detect.
 */
export default function Toolbar() {
  const { state, actions } = useAtlas();
  const fileInputRef = useRef(null);
  const atlasInputRef = useRef(null);

  const handleImportSheet = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback((e) => {
    const file = e.target.files?.[0];
    if (file) {
      loadImageFile(file, actions);
    }
    e.target.value = '';
  }, [actions]);

  const handleImportAtlas = useCallback(() => {
    atlasInputRef.current?.click();
  }, []);

  const handleAtlasChange = useCallback((e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const atlasData = parseAtlasJSON(ev.target.result);
        actions.importAtlas(atlasData);
      } catch (err) {
        alert('Failed to parse atlas JSON: ' + err.message);
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  }, [actions]);

  const handleExport = useCallback(() => {
    const atlas = exportAtlasJSON(state);
    const filename = state.sheetFileName
      ? state.sheetFileName.replace(/\.[^.]+$/, '') + '-atlas.json'
      : 'sprite-atlas.json';
    downloadJSON(atlas, filename);
  }, [state]);

  const handleAutoDetect = useCallback(() => {
    if (!state.sheetSrc) {
      alert('Load a sprite sheet first.');
      return;
    }
    const img = new Image();
    img.onload = () => {
      const result = detectGrid(img);
      actions.updateGrid({
        cellW: result.cellW,
        cellH: result.cellH,
        offsetX: result.offsetX,
        offsetY: result.offsetY,
        spacingX: result.spacingX,
        spacingY: result.spacingY,
      });
      alert(`Auto-detected: ${result.cellW}×${result.cellH} cells (${result.confidence}% confidence)\n\nOffset: ${result.offsetX}, ${result.offsetY}\nSpacing: ${result.spacingX}, ${result.spacingY}`);
    };
    img.src = state.sheetSrc;
  }, [state.sheetSrc, actions]);

  const handleSuggest = useCallback(() => {
    if (!state.sheetSrc) {
      alert('Load a sprite sheet first.');
      return;
    }
    const img = new Image();
    img.onload = () => {
      const suggestions = suggestGridSizes(img);
      const top5 = suggestions.slice(0, 5);
      const msg = top5.map((s, i) =>
        `${i + 1}. ${s.cellW}×${s.cellH} → ${s.cols} cols × ${s.rows} rows (${s.totalCells} cells, ${s.evenness}% fit)`
      ).join('\n');
      alert(`Suggested grid sizes:\n\n${msg}`);
    };
    img.src = state.sheetSrc;
  }, [state.sheetSrc]);

  const handleClearAll = useCallback(() => {
    if (Object.keys(state.sprites).length === 0) return;
    if (confirm('Delete all cataloged sprites? This cannot be undone.')) {
      actions.deleteAllSprites();
    }
  }, [state.sprites, actions]);

  const spriteCount = Object.keys(state.sprites).length;

  return (
    <div className="toolbar">
      <div className="toolbar-left">
        <span className="toolbar-title">🎨 Sprite Cataloger</span>
        <button onClick={handleImportSheet} className="btn btn-primary">
          📂 Import Sheet
        </button>
        <button onClick={handleImportAtlas} className="btn">
          📥 Import Atlas
        </button>
        <button onClick={handleExport} className="btn btn-success" disabled={spriteCount === 0}>
          💾 Export Atlas
        </button>
        <div className="toolbar-divider" />
        <button onClick={handleAutoDetect} className="btn btn-detect" disabled={!state.sheetSrc}>
          🔍 Auto-Detect Grid
        </button>
        <button onClick={handleSuggest} className="btn" disabled={!state.sheetSrc}>
          📐 Suggest Sizes
        </button>
      </div>
      <div className="toolbar-right">
        <span className="toolbar-info">
          {state.sheetFileName
            ? `${state.sheetFileName} (${state.sheetWidth}×${state.sheetHeight})`
            : 'No sheet loaded'
          }
          {spriteCount > 0 && ` — ${spriteCount} sprite${spriteCount !== 1 ? 's' : ''}`}
        </span>
        {spriteCount > 0 && (
          <button onClick={handleClearAll} className="btn btn-danger btn-small">
            🗑 Clear All
          </button>
        )}
      </div>
      <input ref={fileInputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleFileChange} />
      <input ref={atlasInputRef} type="file" accept=".json" style={{ display: 'none' }} onChange={handleAtlasChange} />
    </div>
  );
}
