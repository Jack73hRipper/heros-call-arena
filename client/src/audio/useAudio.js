// ─────────────────────────────────────────────────────────────────────────────
// useAudio.js — React hook that bridges AudioManager with the game's
// React component tree
//
// Mirrors how ParticleManager is used in Arena.jsx:
//   - Singleton AudioManager held in a useRef
//   - init() called on mount
//   - processActions() called in a useEffect watching lastTurnActions
//   - destroy() called on unmount
//
// Usage in App.jsx:
//   const { audioManager, resumeAudio } = useAudio();
//
// Usage in Arena.jsx (wire to turn events):
//   useAudioEvents(audioManager, lastTurnActions, players, screen, isDungeon);
//
// The hook is split in two:
//   useAudio()       — creates & manages the singleton (use in App.jsx)
//   useAudioEvents() — wires game events to sounds (use in Arena.jsx)
// ─────────────────────────────────────────────────────────────────────────────

import { useRef, useEffect, useCallback } from 'react';
import { AudioManager } from './AudioManager.js';

/**
 * Global UI sound delegate — attaches a single click listener to the document
 * that detects button clicks by CSS class and fires the appropriate UI sound.
 *
 * This avoids modifying every component individually. It covers:
 *   .grim-btn           → 'click' (or 'confirm' for --lg / --ember)
 *   .town-nav-item      → 'click'
 *   .skill-slot-btn     → 'click'
 *   .btn-bar            → 'click'
 *   [data-ui-sound]     → custom key via data attribute
 *
 * Call once from the useAudio hook to wire it up globally.
 */
function useGlobalUIClickSounds(managerRef) {
  useEffect(() => {
    const handler = (e) => {
      const mgr = managerRef.current;
      if (!mgr) return;

      const el = e.target.closest('[data-ui-sound], .grim-btn, .town-nav-item, .skill-slot-btn, .btn-bar');
      if (!el) return;

      // Custom override via data attribute
      const custom = el.getAttribute('data-ui-sound');
      if (custom) {
        mgr.playUI(custom);
        return;
      }

      // Big confirm buttons
      if (el.classList.contains('grim-btn')) {
        const isConfirm = el.classList.contains('grim-btn--lg') ||
                          el.classList.contains('grim-btn--ember') ||
                          el.classList.contains('grim-btn--verdant') ||
                          el.classList.contains('grim-btn--crimson');
        mgr.playUI(isConfirm ? 'confirm' : 'click');
        return;
      }

      // Everything else → generic click
      mgr.playUI('click');
    };

    document.addEventListener('click', handler, true); // capture to fire before React
    return () => document.removeEventListener('click', handler, true);
  }, [managerRef]);
}

/**
 * Create and manage the AudioManager singleton.
 * Call once at the top level (App.jsx / AppInner).
 *
 * @returns {{
 *   audioManager: AudioManager | null,
 *   resumeAudio: () => void,
 *   getSettings: () => object,
 *   setMasterVolume: (v: number) => void,
 *   setSfxVolume: (v: number) => void,
 *   setAmbientVolume: (v: number) => void,
 *   setUIVolume: (v: number) => void,
 *   setMusicVolume: (v: number) => void,
 *   toggleMute: () => boolean,
 *   toggleMusic: () => boolean,
 *   nextTrack: () => void,
 *   prevTrack: () => void,
 *   getMusicState: () => object,
 *   onMusicChange: (cb: Function) => void,
 * }}
 */
export function useAudio() {
  const managerRef = useRef(null);
  const musicChangeCbRef = useRef(null); // Stores pending callback for child timing

  // Create and initialize on mount
  useEffect(() => {
    const manager = new AudioManager();
    managerRef.current = manager;

    // Apply any music-change callback registered before manager was created
    if (musicChangeCbRef.current) {
      manager.onMusicChange(musicChangeCbRef.current);
    }

    manager.init().then(() => {
      console.log('[useAudio] AudioManager ready');
    });

    return () => {
      manager.destroy();
      managerRef.current = null;
    };
  }, []);

  // Global UI click sound delegation
  useGlobalUIClickSounds(managerRef);

  // Resume AudioContext on user gesture (call from first click/keypress)
  const resumeAudio = useCallback(() => {
    if (managerRef.current) {
      managerRef.current.resume();
    }
  }, []);

  // Volume control helpers — stable callbacks
  const setMasterVolume = useCallback((v) => {
    managerRef.current?.setMasterVolume(v);
  }, []);

  const setSfxVolume = useCallback((v) => {
    managerRef.current?.setSfxVolume(v);
  }, []);

  const setAmbientVolume = useCallback((v) => {
    managerRef.current?.setAmbientVolume(v);
  }, []);

  const setUIVolume = useCallback((v) => {
    managerRef.current?.setUIVolume(v);
  }, []);

  const toggleMute = useCallback(() => {
    return managerRef.current?.toggleMute() ?? false;
  }, []);

  const getSettings = useCallback(() => {
    return managerRef.current?.getSettings() ?? {
      masterVolume: 0.7,
      sfxVolume: 1.0,
      ambientVolume: 0.4,
      uiVolume: 0.6,
      musicVolume: 0.5,
      muted: false,
    };
  }, []);

  const playUI = useCallback((eventKey) => {
    managerRef.current?.playUI(eventKey);
  }, []);

  // Music control helpers
  const setMusicVolume = useCallback((v) => {
    managerRef.current?.setMusicVolume(v);
  }, []);

  const toggleMusic = useCallback(() => {
    return managerRef.current?.toggleMusic() ?? true;
  }, []);

  const nextTrack = useCallback(() => {
    managerRef.current?.nextTrack();
  }, []);

  const prevTrack = useCallback(() => {
    managerRef.current?.prevTrack();
  }, []);

  const getMusicState = useCallback(() => {
    return managerRef.current?.getMusicState() ?? {
      playing: false, paused: true, title: '', index: -1, total: 0,
    };
  }, []);

  const onMusicChange = useCallback((cb) => {
    musicChangeCbRef.current = cb; // Always store — manager may not exist yet
    if (managerRef.current) managerRef.current.onMusicChange(cb);
  }, []);

  return {
    audioManager: managerRef,
    resumeAudio,
    getSettings,
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
    playUI,
  };
}

/**
 * Wire game events to audio triggers.
 * Call in Arena.jsx (or any component that receives turn data).
 *
 * Mirrors the useEffect pattern used for particles:
 *   useEffect watching lastTurnActions → mgr.processActions()
 *
 * @param {React.RefObject<AudioManager>} audioManagerRef — Ref to the AudioManager
 * @param {object} lastTurnActions — { actions, doorChanges, chestOpened }
 * @param {object} players — Current players map
 */
export function useAudioEvents(audioManagerRef, lastTurnActions, players) {
  // ── Process turn combat/environment sounds ──
  useEffect(() => {
    if (!lastTurnActions || !audioManagerRef?.current) return;
    const mgr = audioManagerRef.current;
    mgr.processActions(lastTurnActions.actions, players);
    mgr.processEnvironment(lastTurnActions.doorChanges, lastTurnActions.chestOpened);
  }, [lastTurnActions]); // eslint-disable-line react-hooks/exhaustive-deps
}

/**
 * Manage ambient track based on current screen and game context.
 * Switches ambient loops on screen transitions.
 *
 * @param {React.RefObject<AudioManager>} audioManagerRef — Ref to the AudioManager
 * @param {string} screen — Current screen ('lobby' | 'town' | 'arena' | etc.)
 * @param {boolean} isDungeon — Whether the current match is a dungeon
 */
export function useAmbientAudio(audioManagerRef, screen, isDungeon) {
  useEffect(() => {
    if (!audioManagerRef?.current) return;
    const mgr = audioManagerRef.current;

    switch (screen) {
      case 'town':
        mgr.playAmbient('ambient_town');
        break;
      case 'arena':
        mgr.playAmbient(isDungeon ? 'ambient_dungeon' : 'ambient_arena');
        break;
      case 'lobby':
      case 'postmatch':
      default:
        mgr.stopAmbient();
        break;
    }
  }, [screen, isDungeon]); // eslint-disable-line react-hooks/exhaustive-deps
}
