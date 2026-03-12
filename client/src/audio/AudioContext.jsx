// ─────────────────────────────────────────────────────────────────────────────
// AudioContext.jsx — React context that makes playUI() available to any
// component without prop-drilling. Wrap your app in <AudioProvider> and call
// useUISound() from any button/component that needs click feedback.
// ─────────────────────────────────────────────────────────────────────────────

import React, { createContext, useContext } from 'react';

/**
 * @typedef {Object} AudioContextValue
 * @property {(eventKey: string) => void} playUI — Play a UI sound effect
 * @property {React.RefObject<import('./AudioManager').AudioManager>} audioManager
 * @property {(v: number) => void} setMasterVolume
 * @property {(v: number) => void} setSfxVolume
 * @property {(v: number) => void} setAmbientVolume
 * @property {(v: number) => void} setUIVolume
 * @property {() => boolean} toggleMute
 * @property {() => object} getSettings
 */

/** @type {React.Context<AudioContextValue|null>} */
const AudioCtx = createContext(null);

/**
 * Provider — wrap around the app (inside GameStateProvider).
 * Receives the audioManager ref, playUI, and volume controls from useAudio().
 */
export function AudioProvider({ audioManager, playUI, volumeControls, children }) {
  return (
    <AudioCtx.Provider value={{ audioManager, playUI, ...volumeControls }}>
      {children}
    </AudioCtx.Provider>
  );
}

/**
 * Hook — returns playUI for direct use.
 *
 * Usage:
 *   const { playUI } = useUISound();
 *   <button onClick={() => { playUI('click'); doStuff(); }}>
 *
 * Or use the convenience wrapper:
 *   const { withClick, withConfirm } = useUISound();
 *   <button onClick={withClick(doStuff)}>        // plays 'click' then fires callback
 *   <button onClick={withConfirm(doStuff)}>      // plays 'confirm' then fires callback
 */
export function useUISound() {
  const ctx = useContext(AudioCtx);

  // Safe fallback if used outside provider (e.g., Storybook, tests)
  const noop = () => {};
  const playUI = ctx?.playUI || noop;
  const audioManager = ctx?.audioManager || null;

  // Convenience wrappers that play a UI sound then call the original handler
  const withClick = (handler) => (...args) => {
    playUI('click');
    if (handler) handler(...args);
  };

  const withConfirm = (handler) => (...args) => {
    playUI('confirm');
    if (handler) handler(...args);
  };

  const withCancel = (handler) => (...args) => {
    playUI('cancel');
    if (handler) handler(...args);
  };

  return { playUI, audioManager, withClick, withConfirm, withCancel };
}

/**
 * Hook — returns volume control functions from the audio context.
 *
 * Usage:
 *   const { setMasterVolume, toggleMute, getSettings } = useAudioSettings();
 */
export function useAudioSettings() {
  const ctx = useContext(AudioCtx);
  const noop = () => {};
  const noopSettings = () => ({
    masterVolume: 0.7,
    sfxVolume: 1.0,
    ambientVolume: 0.4,
    uiVolume: 0.6,
    muted: false,
  });

  return {
    setMasterVolume: ctx?.setMasterVolume || noop,
    setSfxVolume: ctx?.setSfxVolume || noop,
    setAmbientVolume: ctx?.setAmbientVolume || noop,
    setUIVolume: ctx?.setUIVolume || noop,
    setMusicVolume: ctx?.setMusicVolume || noop,
    toggleMute: ctx?.toggleMute || noop,
    toggleMusic: ctx?.toggleMusic || noop,
    nextTrack: ctx?.nextTrack || noop,
    prevTrack: ctx?.prevTrack || noop,
    getMusicState: ctx?.getMusicState || (() => ({ playing: false, paused: true, title: '', index: -1, total: 0 })),
    onMusicChange: ctx?.onMusicChange || noop,
    getSettings: ctx?.getSettings || noopSettings,
  };
}
