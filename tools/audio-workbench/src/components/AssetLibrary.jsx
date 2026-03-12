// ─────────────────────────────────────────────────────────
// AssetLibrary.jsx — Browse & import from Helton Yan sound pack
// ─────────────────────────────────────────────────────────
// Lets user preview sounds from the full asset library
// (Assets/Audio/Helton Yan's Pixel Combat - Single Files),
// compare them with currently-mapped game sounds, and
// replace/import selected files into the game's audio folder.

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import Waveform from './Waveform.jsx';

const API_BASE = 'http://localhost:5211';

/** Format file size in human-readable form */
function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Group library files by displayName to collapse variants */
function groupBySound(files) {
  const groups = new Map();
  for (const f of files) {
    const key = `${f.category}::${f.displayName}`;
    if (!groups.has(key)) {
      groups.set(key, { displayName: f.displayName, category: f.category, variants: [] });
    }
    groups.get(key).variants.push(f);
  }
  return Array.from(groups.values());
}

export default function AssetLibrary({
  config,
  diskFiles,
  getAudioCtx,
  onUpdateConfig,
  onAddToCompare,
  onRefreshDiskFiles,
}) {
  // ── Library data ───────────────────────────────────────
  const [libraryFiles, setLibraryFiles] = useState([]);
  const [libraryAvailable, setLibraryAvailable] = useState(true);
  const [loading, setLoading] = useState(true);

  // ── Filters ────────────────────────────────────────────
  const [search, setSearch] = useState('');
  const [catFilter, setCatFilter] = useState('all');

  // ── Playback ───────────────────────────────────────────
  const [playingPath, setPlayingPath] = useState(null);
  const sourceRef = useRef(null);

  // ── Replace workflow ───────────────────────────────────
  const [replaceTarget, setReplaceTarget] = useState(null); // { soundKey, currentPath, eventSection, eventKey }
  const [importing, setImporting] = useState(null); // filename being imported

  // ── Load library on mount ──────────────────────────────
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/library`);
        const data = await res.json();
        setLibraryFiles(data.files || []);
        setLibraryAvailable(data.available !== false);
      } catch (err) {
        console.error('Failed to load library:', err);
        setLibraryAvailable(false);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // ── Categories present in library ──────────────────────
  const categories = useMemo(() => {
    const cats = new Set(libraryFiles.map(f => f.category));
    return ['all', ...Array.from(cats).sort()];
  }, [libraryFiles]);

  // ── Sound groups (collapsed variants) ──────────────────
  const soundGroups = useMemo(() => {
    let files = libraryFiles;

    if (catFilter !== 'all') {
      files = files.filter(f => f.category === catFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      files = files.filter(f =>
        f.displayName.toLowerCase().includes(q) ||
        f.name.toLowerCase().includes(q) ||
        f.category.toLowerCase().includes(q)
      );
    }

    return groupBySound(files);
  }, [libraryFiles, catFilter, search]);

  // ── Currently mapped sound keys for the "Replace" dropdown ──
  const mappedSounds = useMemo(() => {
    if (!config?._soundFiles) return [];
    return Object.entries(config._soundFiles).map(([key, path]) => ({
      key,
      path,
      label: key,
    })).sort((a, b) => a.key.localeCompare(b.key));
  }, [config]);

  // ── Playback ───────────────────────────────────────────
  const playSound = useCallback(async (url) => {
    try {
      if (sourceRef.current) {
        try { sourceRef.current.stop(); } catch (_) {}
        sourceRef.current = null;
      }
      if (playingPath === url) {
        setPlayingPath(null);
        return;
      }
      const ctx = getAudioCtx();
      const response = await fetch(`${API_BASE}${url}`);
      const arrayBuf = await response.arrayBuffer();
      const audioBuf = await ctx.decodeAudioData(arrayBuf);
      const source = ctx.createBufferSource();
      source.buffer = audioBuf;
      source.connect(ctx.destination);
      source.onended = () => { setPlayingPath(null); sourceRef.current = null; };
      source.start();
      sourceRef.current = source;
      setPlayingPath(url);
    } catch (err) {
      console.error('Library playback error:', err);
      setPlayingPath(null);
    }
  }, [playingPath, getAudioCtx]);

  // ── Import & Replace ───────────────────────────────────
  const handleImportAndReplace = useCallback(async (libraryFile, targetSoundKey, targetCategory) => {
    setImporting(libraryFile.name);
    try {
      // Determine the appropriate game audio category folder
      const currentPath = config._soundFiles[targetSoundKey] || '';
      // e.g., "/audio/combat/melee-hit_sword-slash.wav" → "combat"
      const pathParts = currentPath.split('/').filter(Boolean);
      const gameCategory = targetCategory || (pathParts.length >= 2 ? pathParts[1] : 'combat');

      // Generate a clean filename for the game folder
      const cleanName = libraryFile.name
        .replace(/\s+/g, '-')
        .toLowerCase();

      // Copy file from library to game audio folder
      const importRes = await fetch(`${API_BASE}/api/library/import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          libraryFileName: libraryFile.name,
          category: gameCategory,
          newFileName: cleanName,
        }),
      });
      const result = await importRes.json();
      if (!result.success) throw new Error(result.error);

      // Update the config: change the _soundFiles entry to point to the new file
      onUpdateConfig(prev => {
        const next = JSON.parse(JSON.stringify(prev));
        next._soundFiles[targetSoundKey] = result.path;
        return next;
      });

      // Refresh disk files to pick up the newly imported file
      if (onRefreshDiskFiles) onRefreshDiskFiles();

      setImporting(null);
      setReplaceTarget(null);
    } catch (err) {
      console.error('Import failed:', err);
      alert(`Import failed: ${err.message}`);
      setImporting(null);
    }
  }, [config, onUpdateConfig, onRefreshDiskFiles]);

  // ── Import as new (not replacing an existing key) ──────
  const handleImportAsNew = useCallback(async (libraryFile, targetCategory) => {
    setImporting(libraryFile.name);
    try {
      const cleanName = libraryFile.name.replace(/\s+/g, '-').toLowerCase();

      const importRes = await fetch(`${API_BASE}/api/library/import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          libraryFileName: libraryFile.name,
          category: targetCategory,
          newFileName: cleanName,
        }),
      });
      const result = await importRes.json();
      if (!result.success) throw new Error(result.error);

      // Generate a sound key from filename
      const baseName = cleanName.replace(/\.(wav|mp3|ogg|flac)$/i, '');
      const key = baseName.replace(/[-\s]/g, '_').toLowerCase();

      // Add to _soundFiles
      onUpdateConfig(prev => {
        const next = JSON.parse(JSON.stringify(prev));
        next._soundFiles[key] = result.path;
        return next;
      });

      if (onRefreshDiskFiles) onRefreshDiskFiles();
      setImporting(null);
    } catch (err) {
      console.error('Import failed:', err);
      alert(`Import failed: ${err.message}`);
      setImporting(null);
    }
  }, [onUpdateConfig, onRefreshDiskFiles]);

  // ── Render ─────────────────────────────────────────────
  if (loading) {
    return (
      <div className="wb-library wb-library--loading">
        <div className="wb-spinner" />
        <p>Scanning asset library...</p>
      </div>
    );
  }

  if (!libraryAvailable) {
    return (
      <div className="wb-library wb-library--unavailable">
        <div className="wb-library__placeholder">
          <div className="wb-library__placeholder-icon">📦</div>
          <h2>Asset Library Not Found</h2>
          <p>
            Expected folder:<br/>
            <code>Assets/Audio/Helton Yan's Pixel Combat - Single Files/</code>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="wb-library">
      {/* ── Toolbar ─────────────────────────────────── */}
      <div className="wb-library__toolbar">
        <div className="wb-library__filters">
          <input
            className="wb-input wb-input--search"
            type="text"
            placeholder="Search library sounds..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <select
            className="wb-select"
            value={catFilter}
            onChange={e => setCatFilter(e.target.value)}
          >
            {categories.map(c => (
              <option key={c} value={c}>
                {c === 'all' ? '📦 All categories' : `📂 ${c}`}
              </option>
            ))}
          </select>
        </div>
        <div className="wb-library__stats">
          {libraryFiles.length} files · {soundGroups.length} sounds
        </div>
      </div>

      {/* ── Replace mode banner ────────────────────── */}
      {replaceTarget && (
        <div className="wb-library__replace-banner">
          <span className="wb-library__replace-label">
            🔄 Replacing: <strong>{replaceTarget.soundKey}</strong>
          </span>
          <span className="wb-library__replace-current">
            Current: <code>{config._soundFiles[replaceTarget.soundKey]}</code>
          </span>
          <button
            className="wb-btn wb-btn--sm wb-btn--danger"
            onClick={() => setReplaceTarget(null)}
          >
            ✗ Cancel
          </button>
        </div>
      )}

      {/* ── Sound Key Picker (quick replace mode entry) ── */}
      {!replaceTarget && (
        <div className="wb-library__replace-picker">
          <label className="wb-library__picker-label">Replace an existing sound:</label>
          <select
            className="wb-select wb-library__picker-select"
            value=""
            onChange={e => {
              if (e.target.value) {
                setReplaceTarget({
                  soundKey: e.target.value,
                  currentPath: config._soundFiles[e.target.value],
                });
              }
            }}
          >
            <option value="">— Select a sound key to replace —</option>
            {mappedSounds.map(s => (
              <option key={s.key} value={s.key}>
                {s.key} → {s.path}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* ── Sound Groups List ──────────────────────── */}
      <div className="wb-library__list">
        {soundGroups.length === 0 && (
          <div className="wb-empty">No sounds match the current filters.</div>
        )}

        {soundGroups.map(group => (
          <SoundGroup
            key={`${group.category}::${group.displayName}`}
            group={group}
            playingPath={playingPath}
            onPlay={playSound}
            onAddToCompare={onAddToCompare}
            replaceTarget={replaceTarget}
            onReplace={handleImportAndReplace}
            onImportNew={handleImportAsNew}
            importing={importing}
            getAudioCtx={getAudioCtx}
          />
        ))}
      </div>
    </div>
  );
}


/** 
 * SoundGroup — A collapsible group of variant files for one sound name.
 */
function SoundGroup({
  group,
  playingPath,
  onPlay,
  onAddToCompare,
  replaceTarget,
  onReplace,
  onImportNew,
  importing,
  getAudioCtx,
}) {
  const [expanded, setExpanded] = useState(false);
  const [importCategory, setImportCategory] = useState('combat');

  const IMPORT_CATEGORIES = ['buffs', 'combat', 'events', 'items', 'movement', 'music', 'skills', 'ui'];

  return (
    <div className="wb-lib-group">
      {/* Group header */}
      <div
        className="wb-lib-group__header"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="wb-lib-group__expand">{expanded ? '▼' : '▶'}</span>
        <span className="wb-lib-group__name">{group.displayName}</span>
        <span className="wb-badge wb-badge--info">{group.category}</span>
        <span className="wb-lib-group__count">{group.variants.length} variant{group.variants.length !== 1 ? 's' : ''}</span>

        {/* Quick play first variant */}
        <button
          className={`wb-play-btn wb-play-btn--sm ${playingPath === group.variants[0]?.previewPath ? 'wb-play-btn--active' : ''}`}
          onClick={e => { e.stopPropagation(); onPlay(group.variants[0]?.previewPath); }}
          title="Preview first variant"
        >
          {playingPath === group.variants[0]?.previewPath ? '⏹' : '▶'}
        </button>
      </div>

      {/* Expanded variant list */}
      {expanded && (
        <div className="wb-lib-group__variants">
          {group.variants.map(file => {
            const isPlaying = playingPath === file.previewPath;
            const isImporting = importing === file.name;
            return (
              <div
                key={file.name}
                className={`wb-lib-variant ${isPlaying ? 'wb-lib-variant--playing' : ''}`}
              >
                <button
                  className={`wb-play-btn wb-play-btn--sm ${isPlaying ? 'wb-play-btn--active' : ''}`}
                  onClick={() => onPlay(file.previewPath)}
                >
                  {isPlaying ? '⏹' : '▶'}
                </button>

                <Waveform
                  src={`${API_BASE}${file.previewPath}`}
                  getAudioCtx={getAudioCtx}
                  isPlaying={isPlaying}
                  compact
                />

                <div className="wb-lib-variant__info">
                  <span className="wb-lib-variant__name">Variant {file.variant}</span>
                  <span className="wb-lib-variant__size">{formatSize(file.size)}</span>
                </div>

                <div className="wb-lib-variant__actions">
                  {/* Add to compare */}
                  <button
                    className="wb-btn wb-btn--sm wb-btn--ghost"
                    onClick={() => onAddToCompare(file.previewPath, `${group.displayName} #${file.variant}`)}
                    title="Add to compare panel"
                  >
                    ⚖️
                  </button>

                  {/* Replace action (when in replace mode) */}
                  {replaceTarget && (
                    <button
                      className="wb-btn wb-btn--sm wb-btn--primary"
                      disabled={isImporting}
                      onClick={() => onReplace(file, replaceTarget.soundKey)}
                      title={`Replace ${replaceTarget.soundKey} with this sound`}
                    >
                      {isImporting ? '...' : '🔄 Replace'}
                    </button>
                  )}

                  {/* Import as new (when not in replace mode) */}
                  {!replaceTarget && (
                    <div className="wb-lib-variant__import">
                      <select
                        className="wb-select wb-select--sm"
                        value={importCategory}
                        onChange={e => setImportCategory(e.target.value)}
                        onClick={e => e.stopPropagation()}
                      >
                        {IMPORT_CATEGORIES.map(c => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                      <button
                        className="wb-btn wb-btn--sm wb-btn--secondary"
                        disabled={isImporting}
                        onClick={() => onImportNew(file, importCategory)}
                        title="Import as new sound"
                      >
                        {isImporting ? '...' : '📥 Import'}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
