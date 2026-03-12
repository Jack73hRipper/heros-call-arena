// ─────────────────────────────────────────────────────────
// ComparePanel.jsx — A/B sound comparison & testing
// ─────────────────────────────────────────────────────────

import React, { useState, useRef, useCallback } from 'react';
import Waveform from './Waveform.jsx';

const API_BASE = 'http://localhost:5211';

export default function ComparePanel({
  compareList,
  getAudioCtx,
  onRemove,
  onClear,
}) {
  const [playingPath, setPlayingPath] = useState(null);
  const [volume, setVolume] = useState(0.8);
  const [pitchVariance, setPitchVariance] = useState(0);
  const [loopMode, setLoopMode] = useState(false);
  const sourceRef = useRef(null);
  const gainRef = useRef(null);

  // ── Playback with adjustable volume & pitch ────────────
  const playSound = useCallback(async (filePath) => {
    try {
      if (sourceRef.current) {
        try { sourceRef.current.stop(); } catch (_) {}
        sourceRef.current = null;
      }
      if (playingPath === filePath) {
        setPlayingPath(null);
        return;
      }

      const ctx = getAudioCtx();
      const response = await fetch(`${API_BASE}${filePath}`);
      const arrayBuf = await response.arrayBuffer();
      const audioBuf = await ctx.decodeAudioData(arrayBuf);

      const source = ctx.createBufferSource();
      source.buffer = audioBuf;
      source.loop = loopMode;

      // Apply pitch variance
      if (pitchVariance > 0) {
        const variance = (Math.random() * 2 - 1) * pitchVariance;
        source.playbackRate.value = 1.0 + variance;
      }

      // Apply volume via gain node
      const gain = ctx.createGain();
      gain.gain.value = volume;
      source.connect(gain);
      gain.connect(ctx.destination);

      source.onended = () => {
        setPlayingPath(null);
        sourceRef.current = null;
      };

      source.start();
      sourceRef.current = source;
      gainRef.current = gain;
      setPlayingPath(filePath);
    } catch (err) {
      console.error('Compare playback error:', err);
      setPlayingPath(null);
    }
  }, [playingPath, getAudioCtx, volume, pitchVariance, loopMode]);

  // Rapid-fire A/B: cycle through all sounds sequentially
  const [rapidIdx, setRapidIdx] = useState(0);
  const playNext = useCallback(() => {
    if (compareList.length === 0) return;
    const idx = (rapidIdx) % compareList.length;
    playSound(compareList[idx].path);
    setRapidIdx(idx + 1);
  }, [compareList, rapidIdx, playSound]);

  // Play random (simulates variant behavior)
  const playRandom = useCallback(() => {
    if (compareList.length === 0) return;
    const pick = compareList[Math.floor(Math.random() * compareList.length)];
    playSound(pick.path);
  }, [compareList, playSound]);

  // Update volume on already-playing sound
  const onVolumeChange = useCallback((val) => {
    setVolume(val);
    if (gainRef.current) {
      gainRef.current.gain.value = val;
    }
  }, []);

  // ── Render ─────────────────────────────────────────────
  if (compareList.length === 0) {
    return (
      <div className="wb-compare wb-compare--empty">
        <div className="wb-compare__placeholder">
          <span className="wb-compare__placeholder-icon">⚖️</span>
          <h2>No sounds to compare</h2>
          <p>Click the ⚖️ button on any sound in the Browser or Editor to add it here.</p>
          <p>Then play them side-by-side to find the best fit.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="wb-compare">
      {/* ── Controls ─────────────────────────────────── */}
      <div className="wb-compare__controls">
        <div className="wb-compare__control-group">
          <label>Volume</label>
          <input
            type="range"
            min="0" max="1" step="0.05"
            value={volume}
            onChange={e => onVolumeChange(parseFloat(e.target.value))}
          />
          <span>{(volume * 100).toFixed(0)}%</span>
        </div>

        <div className="wb-compare__control-group">
          <label>Pitch Variance</label>
          <input
            type="range"
            min="0" max="0.2" step="0.01"
            value={pitchVariance}
            onChange={e => setPitchVariance(parseFloat(e.target.value))}
          />
          <span>±{(pitchVariance * 100).toFixed(0)}%</span>
        </div>

        <label className="wb-compare__toggle">
          <input
            type="checkbox"
            checked={loopMode}
            onChange={e => setLoopMode(e.target.checked)}
          />
          Loop
        </label>

        <div className="wb-compare__buttons">
          <button className="wb-btn wb-btn--primary" onClick={playNext} title="Play next in sequence">
            ⏭ Next (A/B)
          </button>
          <button className="wb-btn wb-btn--secondary" onClick={playRandom} title="Play random pick">
            🎲 Random
          </button>
          <button className="wb-btn wb-btn--ghost" onClick={onClear} title="Clear all">
            🗑️ Clear
          </button>
        </div>
      </div>

      {/* ── Sound Cards ──────────────────────────────── */}
      <div className="wb-compare__grid">
        {compareList.map((sound, idx) => {
          const isPlaying = playingPath === sound.path;
          return (
            <div
              key={sound.path}
              className={`wb-compare__card ${isPlaying ? 'wb-compare__card--playing' : ''}`}
            >
              <div className="wb-compare__card-header">
                <span className="wb-compare__card-num">{idx + 1}</span>
                <span className="wb-compare__card-label" title={sound.path}>{sound.label}</span>
                <button
                  className="wb-btn wb-btn--sm wb-btn--ghost"
                  onClick={() => onRemove(sound.path)}
                  title="Remove"
                >
                  ✗
                </button>
              </div>

              <Waveform
                src={`${API_BASE}${sound.path}`}
                getAudioCtx={getAudioCtx}
                isPlaying={isPlaying}
              />

              <button
                className={`wb-compare__play-main ${isPlaying ? 'wb-compare__play-main--active' : ''}`}
                onClick={() => playSound(sound.path)}
              >
                {isPlaying ? '⏹ Stop' : '▶ Play'}
              </button>

              <div className="wb-compare__card-path">{sound.path}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
