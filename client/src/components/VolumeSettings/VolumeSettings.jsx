// ─────────────────────────────────────────────────────────────────────────────
// VolumeSettings.jsx — Floating volume control panel + music player
//
// A small speaker icon in the top-right corner that toggles mute on click
// and expands a panel with volume sliders and a music player on expand.
//
// Uses the useAudioSettings() hook from AudioContext to control volumes
// and music playback.
// ─────────────────────────────────────────────────────────────────────────────

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useAudioSettings } from '../../audio';

/**
 * Speaker icon SVGs (inline to avoid external asset dependencies).
 */
const SpeakerIcon = ({ muted }) => (
  <svg
    viewBox="0 0 24 24"
    width="18"
    height="18"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    {/* Speaker body */}
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="currentColor" opacity="0.3" />
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
    {muted ? (
      <>
        {/* X for muted */}
        <line x1="23" y1="9" x2="17" y2="15" />
        <line x1="17" y1="9" x2="23" y2="15" />
      </>
    ) : (
      <>
        {/* Sound waves */}
        <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
        <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
      </>
    )}
  </svg>
);

/**
 * Single volume slider row.
 */
function VolumeSlider({ label, value, onChange, icon }) {
  const pct = Math.round(value * 100);
  return (
    <div className="vol-slider-row">
      <span className="vol-slider-icon">{icon}</span>
      <label className="vol-slider-label">{label}</label>
      <input
        type="range"
        className="vol-slider-input"
        min="0"
        max="100"
        value={pct}
        onChange={(e) => onChange(parseInt(e.target.value, 10) / 100)}
      />
      <span className="vol-slider-value">{pct}%</span>
    </div>
  );
}

/**
 * Music player transport controls.
 */
function MusicPlayer({ musicState, onToggle, onNext, onPrev }) {
  return (
    <div className="music-player">
      <div className="music-player__title-row">
        <span className="music-player__now-playing">
          {musicState.title || 'No track loaded'}
        </span>
        {musicState.total > 0 && (
          <span className="music-player__track-num">
            {musicState.index + 1}/{musicState.total}
          </span>
        )}
      </div>
      <div className="music-player__controls">
        <button
          className="music-player__btn"
          onClick={onPrev}
          title="Previous track"
          data-ui-sound=""
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
            <rect x="3" y="5" width="3" height="14" rx="1" />
            <polygon points="20 5 9 12 20 19" />
          </svg>
        </button>
        <button
          className="music-player__btn music-player__btn--play"
          onClick={onToggle}
          title={musicState.playing ? 'Pause' : 'Play'}
          data-ui-sound=""
        >
          {musicState.playing ? (
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <rect x="6" y="4" width="4" height="16" rx="1" />
              <rect x="14" y="4" width="4" height="16" rx="1" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <polygon points="6 3 20 12 6 21" />
            </svg>
          )}
        </button>
        <button
          className="music-player__btn"
          onClick={onNext}
          title="Next track"
          data-ui-sound=""
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
            <polygon points="4 5 15 12 4 19" />
            <rect x="18" y="5" width="3" height="14" rx="1" />
          </svg>
        </button>
      </div>
    </div>
  );
}

/**
 * VolumeSettings — Floating audio control widget + music player.
 */
export default function VolumeSettings() {
  const {
    setMasterVolume,
    setSfxVolume,
    setAmbientVolume,
    setUIVolume,
    setMusicVolume,
    toggleMute,
    toggleMusic,
    nextTrack,
    prevTrack,
    getMusicState,
    onMusicChange,
    getSettings,
  } = useAudioSettings();

  const [open, setOpen] = useState(false);
  const [settings, setSettings] = useState(getSettings);
  const [musicState, setMusicState] = useState(() => getMusicState());
  const panelRef = useRef(null);

  // Register for music state changes from AudioManager
  useEffect(() => {
    onMusicChange((state) => setMusicState(state));
    return () => onMusicChange(null);
  }, [onMusicChange]);

  // Refresh settings from AudioManager when panel opens
  useEffect(() => {
    if (open) {
      setSettings(getSettings());
      setMusicState(getMusicState());
    }
  }, [open, getSettings, getMusicState]);

  // Close panel on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handler);
    }, 0);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handler);
    };
  }, [open]);

  const handleMuteToggle = useCallback((e) => {
    e.stopPropagation();
    const newMuted = toggleMute();
    setSettings((prev) => ({ ...prev, muted: newMuted }));
  }, [toggleMute]);

  const handlePanelToggle = useCallback((e) => {
    e.stopPropagation();
    setOpen((prev) => !prev);
  }, []);

  const handleMusicToggle = useCallback(() => {
    toggleMusic();
    // Sync full state (including title) from AudioManager
    setMusicState(getMusicState());
  }, [toggleMusic, getMusicState]);

  const handleNext = useCallback(() => {
    nextTrack();
    setMusicState(getMusicState());
  }, [nextTrack, getMusicState]);

  const handlePrev = useCallback(() => {
    prevTrack();
    setMusicState(getMusicState());
  }, [prevTrack, getMusicState]);

  // Slider change handlers
  const handleMaster = useCallback((v) => {
    setMasterVolume(v);
    setSettings((prev) => ({ ...prev, masterVolume: v }));
  }, [setMasterVolume]);

  const handleSfx = useCallback((v) => {
    setSfxVolume(v);
    setSettings((prev) => ({ ...prev, sfxVolume: v }));
  }, [setSfxVolume]);

  const handleAmbient = useCallback((v) => {
    setAmbientVolume(v);
    setSettings((prev) => ({ ...prev, ambientVolume: v }));
  }, [setAmbientVolume]);

  const handleUI = useCallback((v) => {
    setUIVolume(v);
    setSettings((prev) => ({ ...prev, uiVolume: v }));
  }, [setUIVolume]);

  const handleMusic = useCallback((v) => {
    setMusicVolume(v);
    setSettings((prev) => ({ ...prev, musicVolume: v }));
  }, [setMusicVolume]);

  return (
    <div className="volume-settings" ref={panelRef}>
      {/* Mute toggle button */}
      <button
        className={`volume-settings__mute-btn${settings.muted ? ' volume-settings__mute-btn--muted' : ''}`}
        onClick={handleMuteToggle}
        title={settings.muted ? 'Unmute' : 'Mute'}
        data-ui-sound=""
      >
        <SpeakerIcon muted={settings.muted} />
      </button>

      {/* Gear/expand button */}
      <button
        className="volume-settings__expand-btn"
        onClick={handlePanelToggle}
        title="Volume Settings"
        data-ui-sound=""
      >
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points={open ? '18 15 12 9 6 15' : '6 9 12 15 18 9'} />
        </svg>
      </button>

      {/* Slider panel */}
      {open && (
        <div className="volume-settings__panel">
          {/* ── Music Player ── */}
          <div className="volume-settings__section-title">Music</div>
          <MusicPlayer
            musicState={musicState}
            onToggle={handleMusicToggle}
            onNext={handleNext}
            onPrev={handlePrev}
          />
          <VolumeSlider
            label="Music"
            icon="♪"
            value={settings.musicVolume ?? 0.5}
            onChange={handleMusic}
          />

          {/* ── Volume Sliders ── */}
          <div className="volume-settings__section-title">Volume</div>
          <VolumeSlider
            label="Master"
            icon="♛"
            value={settings.masterVolume}
            onChange={handleMaster}
          />
          <VolumeSlider
            label="SFX"
            icon="⚔"
            value={settings.sfxVolume}
            onChange={handleSfx}
          />
          <VolumeSlider
            label="Ambient"
            icon="♫"
            value={settings.ambientVolume}
            onChange={handleAmbient}
          />
          <VolumeSlider
            label="UI"
            icon="◈"
            value={settings.uiVolume}
            onChange={handleUI}
          />
          <button
            className="volume-settings__mute-all"
            onClick={handleMuteToggle}
          >
            {settings.muted ? '🔇 Unmute All' : '🔊 Mute All'}
          </button>
        </div>
      )}
    </div>
  );
}
