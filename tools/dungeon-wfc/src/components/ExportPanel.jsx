// ─────────────────────────────────────────────────────────
// ExportPanel.jsx — Export/Import dungeon maps & module library
//
// Export generated dungeons as game-compatible JSON.
// Import existing maps for preview.
// Export/import the module library as the canonical shared JSON format.
// ─────────────────────────────────────────────────────────

import React, { useRef, useCallback, useState } from 'react';
import { exportToGameJSON, importFromGameJSON } from '../utils/exportMap.js';
import { exportModuleLibrary, importModuleLibrary, MODULE_LIBRARY_VERSION } from '../utils/moduleLibrary.js';

export default function ExportPanel({ tileMap, wfcGrid, variants, modules, onImportMap, onModulesChange }) {
  const fileInputRef = useRef(null);
  const libraryInputRef = useRef(null);
  const [mapName, setMapName] = useState('WFC Dungeon');
  const [lastExport, setLastExport] = useState(null);
  const [saving, setSaving] = useState(false);
  const [librarySaving, setLibrarySaving] = useState(false);
  const [libraryFeedback, setLibraryFeedback] = useState(null);

  const handleExport = useCallback(() => {
    if (!tileMap) return;

    const json = exportToGameJSON(tileMap, wfcGrid, variants, mapName);
    const text = JSON.stringify(json, null, 2);
    const blob = new Blob([text], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    // Sanitize filename
    const filename = mapName.toLowerCase().replace(/[^a-z0-9]+/g, '_') + '.json';
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    setLastExport(filename);
  }, [tileMap, wfcGrid, variants, mapName]);

  const handleCopyJSON = useCallback(() => {
    if (!tileMap) return;

    const json = exportToGameJSON(tileMap, wfcGrid, variants, mapName);
    const text = JSON.stringify(json, null, 2);
    navigator.clipboard.writeText(text).then(() => {
      setLastExport('Copied to clipboard!');
      setTimeout(() => setLastExport(null), 2000);
    });
  }, [tileMap, wfcGrid, variants, mapName]);

  const handleSaveToServer = useCallback(async () => {
    if (!tileMap || saving) return;
    setSaving(true);
    setLastExport(null);
    try {
      const json = exportToGameJSON(tileMap, wfcGrid, variants, mapName);
      const res = await fetch('/api/maps/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ map_data: json }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Upload failed');
      }
      const data = await res.json();
      setLastExport(`Saved to server as ${data.filename} — ready in game!`);
    } catch (err) {
      setLastExport(`Error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }, [tileMap, wfcGrid, variants, mapName, saving]);

  const handleImport = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileLoad = useCallback((e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const json = JSON.parse(ev.target.result);
        const imported = importFromGameJSON(json);
        onImportMap(imported);
        setMapName(imported.name);
      } catch (err) {
        console.error('Failed to import map:', err);
        alert('Invalid map JSON file.');
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  }, [onImportMap]);

  // ── Library Export/Import ──

  const handleExportLibraryToServer = useCallback(async () => {
    if (!modules || modules.length === 0 || librarySaving) return;
    setLibrarySaving(true);
    setLibraryFeedback(null);
    try {
      const libraryJson = exportModuleLibrary(modules);
      const res = await fetch('/api/maps/wfc-modules/library', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(libraryJson),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Upload failed');
      }
      const data = await res.json();
      setLibraryFeedback(`Exported ${data.module_count} modules to server — server will use them on next generation!`);
    } catch (err) {
      setLibraryFeedback(`Error: ${err.message}`);
    } finally {
      setLibrarySaving(false);
    }
  }, [modules, librarySaving]);

  const handleExportLibraryDownload = useCallback(() => {
    if (!modules || modules.length === 0) return;
    const libraryJson = exportModuleLibrary(modules);
    const text = JSON.stringify(libraryJson, null, 2);
    const blob = new Blob([text], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'library.json';
    a.click();
    URL.revokeObjectURL(url);
    setLibraryFeedback('Downloaded library.json');
    setTimeout(() => setLibraryFeedback(null), 3000);
  }, [modules]);

  const handleImportLibrary = useCallback(() => {
    libraryInputRef.current?.click();
  }, []);

  const handleLibraryFileLoad = useCallback((e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const json = JSON.parse(ev.target.result);
        const imported = importModuleLibrary(json);
        if (onModulesChange) {
          onModulesChange(imported);
        }
        setLibraryFeedback(`Imported ${imported.length} modules from library.json`);
        setTimeout(() => setLibraryFeedback(null), 3000);
      } catch (err) {
        console.error('Failed to import module library:', err);
        setLibraryFeedback(`Error: ${err.message}`);
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  }, [onModulesChange]);

  return (
    <div className="export-panel">
      <h3>Export / Import</h3>

      <div className="export-section">
        <label>Map Name:</label>
        <input
          type="text"
          value={mapName}
          onChange={(e) => setMapName(e.target.value)}
          placeholder="My Dungeon"
        />
      </div>

      <div className="export-buttons">
        <button
          className="btn-export"
          onClick={handleExport}
          disabled={!tileMap}
          title="Download as game-compatible JSON"
        >
          Export Map JSON
        </button>
        <button
          className="btn-copy"
          onClick={handleCopyJSON}
          disabled={!tileMap}
          title="Copy JSON to clipboard"
        >
          Copy to Clipboard
        </button>
      </div>

      <div className="export-buttons" style={{ marginTop: '6px' }}>
        <button
          className="btn-save-server"
          onClick={handleSaveToServer}
          disabled={!tileMap || saving}
          title="Save directly to the game server — instantly available in map dropdown"
        >
          {saving ? 'Saving...' : 'Save to Server'}
        </button>
      </div>

      {lastExport && (
        <div className="export-feedback">{lastExport}</div>
      )}

      <hr className="section-divider" />

      <div className="import-section">
        <button onClick={handleImport}>Import Existing Map</button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          style={{ display: 'none' }}
          onChange={handleFileLoad}
        />
        <p className="hint">Load a map from server/configs/maps/ to preview it.</p>
      </div>

      <hr className="section-divider" />

      <div className="library-section">
        <h4>Module Library</h4>
        <p className="hint">
          Export the current module library as the canonical JSON shared between
          the tool and the server. Single source of truth.
        </p>

        <div className="export-buttons">
          <button
            className="btn-export-library"
            onClick={handleExportLibraryToServer}
            disabled={!modules || modules.length === 0 || librarySaving}
            title="Write library.json to server/configs/wfc-modules/ — server picks it up automatically"
          >
            {librarySaving ? 'Saving...' : 'Export Library to Server'}
          </button>
        </div>

        <div className="export-buttons" style={{ marginTop: '6px' }}>
          <button
            className="btn-export"
            onClick={handleExportLibraryDownload}
            disabled={!modules || modules.length === 0}
            title="Download library.json to your computer"
          >
            Download Library JSON
          </button>
          <button
            onClick={handleImportLibrary}
            title="Import a library.json file to replace current modules"
          >
            Import Library
          </button>
          <input
            ref={libraryInputRef}
            type="file"
            accept=".json"
            style={{ display: 'none' }}
            onChange={handleLibraryFileLoad}
          />
        </div>

        {libraryFeedback && (
          <div className="export-feedback">{libraryFeedback}</div>
        )}
      </div>
    </div>
  );
}
