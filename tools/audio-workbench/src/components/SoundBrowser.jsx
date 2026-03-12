// ─────────────────────────────────────────────────────────
// SoundBrowser.jsx — Browse, preview & categorize sounds
// ─────────────────────────────────────────────────────────

import React, { useState, useRef, useCallback, useMemo } from 'react';
import Waveform from './Waveform.jsx';

const API_BASE = 'http://localhost:5211';

/** Format file size in human-readable form */
function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Find the sound key that maps to a given file path */
function findKeyForPath(soundFiles, filePath) {
  for (const [key, path] of Object.entries(soundFiles)) {
    if (path === filePath) return key;
  }
  return null;
}

export default function SoundBrowser({
  diskFiles,
  config,
  validation,
  getAudioCtx,
  onAddToCompare,
  onUpdateConfig,
}) {
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [showOnly, setShowOnly] = useState('all'); // 'all' | 'mapped' | 'orphaned' | 'broken'
  const [playingPath, setPlayingPath] = useState(null);
  const [sortBy, setSortBy] = useState('name'); // 'name' | 'category' | 'size'
  const sourceRef = useRef(null);

  // ── Categories from disk files ─────────────────────────
  const categories = useMemo(() => {
    const cats = new Set(diskFiles.map(f => f.category));
    return ['all', ...Array.from(cats).sort()];
  }, [diskFiles]);

  // ── Filtered + sorted file list ────────────────────────
  const filteredFiles = useMemo(() => {
    let files = [...diskFiles];

    // Category filter
    if (filter !== 'all') {
      files = files.filter(f => f.category === filter);
    }

    // Status filter
    const soundFiles = config?._soundFiles || {};
    const mappedPaths = new Set(Object.values(soundFiles));
    const brokenKeys = new Set(validation.broken.map(b => b.path));

    if (showOnly === 'mapped') {
      files = files.filter(f => mappedPaths.has(f.path));
    } else if (showOnly === 'orphaned') {
      files = files.filter(f => !mappedPaths.has(f.path));
    } else if (showOnly === 'broken') {
      // Show broken references as virtual entries
      return validation.broken.map(b => ({
        name: b.path.split('/').pop(),
        path: b.path,
        category: b.path.split('/')[2] || 'unknown',
        size: 0,
        modified: '',
        _broken: true,
        _key: b.key,
      }));
    }

    // Search filter
    if (search.trim()) {
      const q = search.toLowerCase();
      files = files.filter(f =>
        f.name.toLowerCase().includes(q) ||
        f.path.toLowerCase().includes(q) ||
        (findKeyForPath(soundFiles, f.path) || '').toLowerCase().includes(q)
      );
    }

    // Sort
    files.sort((a, b) => {
      if (sortBy === 'name') return a.name.localeCompare(b.name);
      if (sortBy === 'category') return a.category.localeCompare(b.category) || a.name.localeCompare(b.name);
      if (sortBy === 'size') return b.size - a.size;
      return 0;
    });

    return files;
  }, [diskFiles, filter, search, showOnly, sortBy, config, validation]);

  // ── Playback ───────────────────────────────────────────
  const playSound = useCallback(async (filePath) => {
    try {
      // Stop current
      if (sourceRef.current) {
        try { sourceRef.current.stop(); } catch (_) {}
        sourceRef.current = null;
      }

      // If clicking the same sound, just stop it
      if (playingPath === filePath) {
        setPlayingPath(null);
        return;
      }

      const ctx = getAudioCtx();
      const url = `${API_BASE}${filePath}`;
      const response = await fetch(url);
      const arrayBuf = await response.arrayBuffer();
      const audioBuf = await ctx.decodeAudioData(arrayBuf);

      const source = ctx.createBufferSource();
      source.buffer = audioBuf;
      source.connect(ctx.destination);
      source.onended = () => {
        setPlayingPath(null);
        sourceRef.current = null;
      };
      source.start();
      sourceRef.current = source;
      setPlayingPath(filePath);
    } catch (err) {
      console.error('Playback error:', err);
      setPlayingPath(null);
    }
  }, [playingPath, getAudioCtx]);

  // ── Quick-map: add orphaned file to _soundFiles ────────
  const quickMap = useCallback((file) => {
    // Generate a key from the filename: "melee-hit_sword-slash.wav" → "melee_hit_sword_slash"
    const baseName = file.name.replace(/\.(wav|mp3|ogg|flac)$/i, '');
    const key = baseName.replace(/[-\s]/g, '_').toLowerCase();

    onUpdateConfig(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      next._soundFiles[key] = file.path;
      return next;
    });
  }, [onUpdateConfig]);

  const soundFiles = config?._soundFiles || {};
  const mappedPaths = new Set(Object.values(soundFiles));

  return (
    <div className="wb-browser">
      {/* ── Toolbar ─────────────────────────────────── */}
      <div className="wb-browser__toolbar">
        <div className="wb-browser__filters">
          <input
            className="wb-input wb-input--search"
            type="text"
            placeholder="Search sounds..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />

          <select
            className="wb-select"
            value={filter}
            onChange={e => setFilter(e.target.value)}
          >
            {categories.map(c => (
              <option key={c} value={c}>
                {c === 'all' ? '📁 All categories' : `📂 ${c}`}
              </option>
            ))}
          </select>

          <select
            className="wb-select"
            value={showOnly}
            onChange={e => setShowOnly(e.target.value)}
          >
            <option value="all">All files</option>
            <option value="mapped">✓ Mapped only</option>
            <option value="orphaned">⚠ Unmapped only</option>
            <option value="broken">✗ Broken refs</option>
          </select>

          <select
            className="wb-select wb-select--sort"
            value={sortBy}
            onChange={e => setSortBy(e.target.value)}
          >
            <option value="name">Sort: Name</option>
            <option value="category">Sort: Category</option>
            <option value="size">Sort: Size</option>
          </select>
        </div>

        <div className="wb-browser__count">
          {filteredFiles.length} file{filteredFiles.length !== 1 ? 's' : ''}
        </div>
      </div>

      {/* ── File List ───────────────────────────────── */}
      <div className="wb-browser__list">
        {filteredFiles.length === 0 && (
          <div className="wb-empty">No sounds match the current filters.</div>
        )}

        {filteredFiles.map(file => {
          const isPlaying = playingPath === file.path;
          const isMapped = mappedPaths.has(file.path);
          const isBroken = file._broken;
          const soundKey = isBroken ? file._key : findKeyForPath(soundFiles, file.path);

          return (
            <div
              key={file.path}
              className={`wb-sound-row ${isPlaying ? 'wb-sound-row--playing' : ''} ${isBroken ? 'wb-sound-row--broken' : ''}`}
            >
              {/* Play button */}
              <button
                className={`wb-play-btn ${isPlaying ? 'wb-play-btn--active' : ''}`}
                onClick={() => !isBroken && playSound(file.path)}
                disabled={isBroken}
                title={isBroken ? 'File not found on disk' : 'Play / Stop'}
              >
                {isPlaying ? '⏹' : '▶'}
              </button>

              {/* Waveform */}
              {!isBroken && (
                <Waveform
                  src={`${API_BASE}${file.path}`}
                  getAudioCtx={getAudioCtx}
                  isPlaying={isPlaying}
                  compact
                />
              )}

              {/* File info */}
              <div className="wb-sound-row__info">
                <span className="wb-sound-row__name">{file.name}</span>
                <span className="wb-sound-row__meta">
                  <span className="wb-sound-row__category">{file.category}</span>
                  {file.size > 0 && <span className="wb-sound-row__size">{formatSize(file.size)}</span>}
                  {soundKey && <span className="wb-sound-row__key" title="Sound key">🔑 {soundKey}</span>}
                </span>
              </div>

              {/* Status badge */}
              <div className="wb-sound-row__status">
                {isBroken && <span className="wb-badge wb-badge--error" title="File missing from disk">BROKEN</span>}
                {!isBroken && isMapped && <span className="wb-badge wb-badge--ok" title="Mapped in config">MAPPED</span>}
                {!isBroken && !isMapped && <span className="wb-badge wb-badge--warn" title="Not in config">UNMAPPED</span>}
              </div>

              {/* Actions */}
              <div className="wb-sound-row__actions">
                {!isBroken && !isMapped && (
                  <button
                    className="wb-btn wb-btn--sm wb-btn--secondary"
                    onClick={() => quickMap(file)}
                    title="Quick-map: add to _soundFiles"
                  >
                    + Map
                  </button>
                )}
                {!isBroken && (
                  <button
                    className="wb-btn wb-btn--sm wb-btn--ghost"
                    onClick={() => onAddToCompare(file.path, file.name)}
                    title="Add to compare panel"
                  >
                    ⚖️
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
