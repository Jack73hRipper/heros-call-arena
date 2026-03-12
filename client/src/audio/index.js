// ─────────────────────────────────────────────────────────────────────────────
// audio/index.js — Barrel export for the audio system
// ─────────────────────────────────────────────────────────────────────────────

export { AudioManager } from './AudioManager.js';
export { useAudio, useAudioEvents, useAmbientAudio } from './useAudio.js';
export { SOUND_KEYS, SOUND_CATEGORIES, validateEffectMap } from './soundMap.js';
export { AudioProvider, useUISound, useAudioSettings } from './AudioContext.jsx';
