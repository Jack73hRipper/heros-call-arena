// ─────────────────────────────────────────────────────────────────────────────
// AudioManager.js — Web Audio API manager for the Arena game
//
// Data-driven: reads audio-effects.json to decide which sounds play for
// which game events. Change the mapping JSON to swap sounds — no code edits.
//
// Mirrors the ParticleManager pattern: plain JS singleton held via useRef,
// with init() → start() → destroy() lifecycle.
//
// Browser autoplay policy: AudioContext is created in a 'suspended' state
// and resumed on the first user interaction (called from useAudio hook).
// ─────────────────────────────────────────────────────────────────────────────

export class AudioManager {
  constructor() {
    /** @type {AudioContext|null} */
    this.context = null;

    // ── Volume levels (0–1) ──
    this.masterVolume = 0.7;
    this.sfxVolume = 1.0;
    this.ambientVolume = 0.4;
    this.uiVolume = 0.6;

    /** @type {boolean} Global mute toggle */
    this.muted = false;

    // ── Gain nodes (created in init) ──
    /** @type {GainNode|null} */ this._masterGain = null;
    /** @type {GainNode|null} */ this._sfxGain = null;
    /** @type {GainNode|null} */ this._ambientGain = null;
    /** @type {GainNode|null} */ this._uiGain = null;

    // ── Audio buffer cache ──
    /** @type {Map<string, AudioBuffer>} Decoded buffers keyed by sound key */
    this._buffers = new Map();

    // ── Effect mapping (loaded from audio-effects.json) ──
    /** @type {object|null} */
    this.effectMap = null;

    // ── Ambient loop state ──
    /** @type {AudioBufferSourceNode|null} Currently playing ambient source */
    this._ambientSource = null;
    /** @type {string|null} Key of the current ambient track */
    this._ambientKey = null;

    // ── Initialization state ──
    this._initialized = false;
    this._preloadPromise = null;

    // ── Sound throttling ──
    // Prevents audio chaos when many actions fire simultaneously
    /** @type {number} Max concurrent SFX voices (prevents ear-shredding turns) */
    this._maxConcurrent = 6;
    /** @type {number} Current active voice count */
    this._activeVoices = 0;
    /** @type {Map<string, number>} Per-key cooldown timestamps (ms) */
    this._keyCooldowns = new Map();
    /** @type {number} Minimum ms between same sound key */
    this._cooldownMs = 80;

    // ── Music playlist state ──
    // Uses HTML5 Audio for streaming (too large for Web Audio buffer decode)
    /** @type {HTMLAudioElement|null} */
    this._musicAudio = null;
    /** @type {Array<{title: string, path: string}>} Shuffled playlist */
    this._musicPlaylist = [];
    /** @type {number} Current index in the shuffled playlist */
    this._musicIndex = -1;
    /** @type {boolean} Whether music is paused by user */
    this._musicPaused = false;
    /** @type {number} Music volume (0–1), separate from ambient */
    this.musicVolume = 0.5;
    /** @type {Function|null} Callback when track changes */
    this._onMusicChange = null;

    // ── Tab-visibility lifecycle ──
    // When the tab is hidden, skip firing new sounds to avoid a burst
    // of stacked audio when the user comes back.
    this._hidden = document.hidden;
    this._onVisibilityChange = this._onVisibilityChange.bind(this);
    document.addEventListener('visibilitychange', this._onVisibilityChange);
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Initialization
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Initialize the AudioContext, gain node graph, load the effect mapping,
   * and preload all sound buffers defined in the sound map.
   *
   * Safe to call multiple times — subsequent calls return the initial promise.
   */
  async init() {
    if (this._preloadPromise) return this._preloadPromise;

    this._preloadPromise = this._doInit();
    return this._preloadPromise;
  }

  async _doInit() {
    try {
      // ── Create AudioContext ──
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      this.context = new AudioCtx();

      // ── Build gain node graph ──
      //
      //   sfxGain ─────┐
      //   ambientGain ──┤── masterGain ── destination
      //   uiGain ───────┘
      //
      this._masterGain = this.context.createGain();
      this._masterGain.connect(this.context.destination);

      this._sfxGain = this.context.createGain();
      this._sfxGain.connect(this._masterGain);

      this._ambientGain = this.context.createGain();
      this._ambientGain.connect(this._masterGain);

      this._uiGain = this.context.createGain();
      this._uiGain.connect(this._masterGain);

      // Apply saved volume settings
      this._loadSettings();
      this._applyVolumes();

      // ── Load effect mapping ──
      const baseUrl = import.meta.env.BASE_URL;
      const cacheBust = `?t=${Date.now()}`;
      const mapRes = await fetch(`${baseUrl}audio-effects.json${cacheBust}`);
      if (mapRes.ok) {
        this.effectMap = await mapRes.json();

        // ── Preload all referenced sound files ──
        const allPaths = this._collectSoundPaths(this.effectMap);
        const unique = [...new Set(allPaths)];

        console.log(`[AudioManager] Preloading ${unique.length} sound files...`);
        const results = await Promise.allSettled(
          unique.map(entry => this._preloadBuffer(entry.key, entry.path))
        );

        const loaded = results.filter(r => r.status === 'fulfilled').length;
        const failed = results.filter(r => r.status === 'rejected').length;
        console.log(`[AudioManager] ✓ ${loaded} sounds loaded, ${failed} failed`);

        if (failed > 0) {
          const failedEntries = results
            .map((r, i) => r.status === 'rejected' ? unique[i] : null)
            .filter(Boolean);
          for (const entry of failedEntries) {
            console.warn(`[AudioManager]   ✗ "${entry.key}" → ${entry.path}`);
          }
        }
      } else {
        console.warn('[AudioManager] Could not load audio-effects.json — audio disabled');
      }

      this._initialized = true;
      console.log('[AudioManager] Initialized');

      // If the AudioContext was already resumed (user clicked before init finished),
      // auto-start the music playlist now.
      if (this.context?.state === 'running' && this._musicIndex === -1 && this.effectMap?.music?.tracks?.length) {
        this.initMusic();
      }
    } catch (err) {
      console.warn('[AudioManager] Init failed:', err);
    }
  }

  /**
   * Resume the AudioContext after a user gesture (required by browser policy).
   * Call this from the first click/keypress handler.
   */
  async resume() {
    if (this.context && this.context.state === 'suspended') {
      try {
        await this.context.resume();
        console.log('[AudioManager] AudioContext resumed');
      } catch (err) {
        console.warn('[AudioManager] Failed to resume AudioContext:', err);
      }
    }

    // Start music playlist on first user gesture (if not already started).
    // This is outside the suspended check because init() may not have finished
    // loading the effectMap by the time the first click resumes the context.
    if (this._initialized && this._musicIndex === -1 && this.effectMap?.music?.tracks?.length) {
      this.initMusic();
    }
  }

  /**
   * Clean up: stop ambient, close context, remove listeners.
   */
  destroy() {
    this.stopAmbient();
    this.stopMusic();
    if (this.context) {
      this.context.close().catch(() => {});
      this.context = null;
    }
    document.removeEventListener('visibilitychange', this._onVisibilityChange);
    this._buffers.clear();
    this._initialized = false;
    this._preloadPromise = null;
    console.log('[AudioManager] Destroyed');
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Playback — One-Shot SFX
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Play a one-shot sound effect by key.
   *
   * @param {string} key — Sound key (must match a key in audio-effects.json)
   * @param {object} [options]
   * @param {number} [options.volume=1.0] — Per-sound volume multiplier (0–1)
   * @param {number} [options.pitchVariance=0] — Random pitch shift range (e.g. 0.1 = ±10%)
   * @param {string} [options.channel='sfx'] — Gain channel: 'sfx' | 'ui' | 'ambient'
   */
  play(key, options = {}) {
    if (!this._canPlay()) return;

    const buffer = this._buffers.get(key);
    if (!buffer) {
      // Silent fail — sound not loaded (asset not yet mapped)
      return;
    }

    // ── Throttle: max concurrent voices ──
    if (this._activeVoices >= this._maxConcurrent) return;

    // ── Throttle: per-key cooldown (prevent same sound stacking) ──
    const now = performance.now();
    const lastPlayed = this._keyCooldowns.get(key) || 0;
    if (now - lastPlayed < this._cooldownMs) return;
    this._keyCooldowns.set(key, now);

    const { volume = 1.0, pitchVariance = 0, channel = 'sfx' } = options;

    // Create buffer source
    const source = this.context.createBufferSource();
    source.buffer = buffer;

    // Pitch variance: randomize playback rate within ± pitchVariance
    if (pitchVariance > 0) {
      const shift = 1 + (Math.random() * 2 - 1) * pitchVariance;
      source.playbackRate.value = shift;
    }

    // Per-sound volume node
    const gainNode = this.context.createGain();
    gainNode.gain.value = volume;

    // Route: source → per-sound gain → channel gain → master → destination
    const channelGain = this._getChannelGain(channel);
    source.connect(gainNode);
    gainNode.connect(channelGain);

    source.start(0);
    this._activeVoices++;

    // Auto-cleanup on end
    source.onended = () => {
      source.disconnect();
      gainNode.disconnect();
      this._activeVoices = Math.max(0, this._activeVoices - 1);
    };
  }

  /**
   * Play a random variant from a set of keys.
   * e.g. playVariant(['swing1', 'swing2', 'swing3']) picks one at random.
   *
   * @param {string[]} keys — Array of sound keys
   * @param {object} [options] — Same as play()
   */
  playVariant(keys, options = {}) {
    if (!keys || keys.length === 0) return;
    const key = keys[Math.floor(Math.random() * keys.length)];
    this.play(key, options);
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Playback — Ambient Loops
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Start an ambient loop. Crossfades if a different ambient is already playing.
   *
   * @param {string} key — Sound key for the ambient track
   * @param {number} [fadeDuration=1.5] — Crossfade duration in seconds
   */
  playAmbient(key, fadeDuration = 1.5) {
    if (!this._canPlay()) return;
    if (this._ambientKey === key) return; // Already playing this track

    const buffer = this._buffers.get(key);
    if (!buffer) return;

    // Fade out current ambient (if any)
    this.stopAmbient(fadeDuration);

    // Create new looping source
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.loop = true;

    // Fade-in gain
    const fadeGain = this.context.createGain();
    fadeGain.gain.setValueAtTime(0, this.context.currentTime);
    fadeGain.gain.linearRampToValueAtTime(1, this.context.currentTime + fadeDuration);

    source.connect(fadeGain);
    fadeGain.connect(this._ambientGain);
    source.start(0);

    this._ambientSource = source;
    this._ambientFadeGain = fadeGain;
    this._ambientKey = key;
  }

  /**
   * Stop the current ambient loop with a fade-out.
   *
   * @param {number} [fadeDuration=1.0] — Fade-out duration in seconds
   */
  stopAmbient(fadeDuration = 1.0) {
    if (!this._ambientSource || !this.context) return;

    const source = this._ambientSource;
    const fadeGain = this._ambientFadeGain;

    if (fadeGain) {
      fadeGain.gain.setValueAtTime(fadeGain.gain.value, this.context.currentTime);
      fadeGain.gain.linearRampToValueAtTime(0, this.context.currentTime + fadeDuration);
    }

    // Schedule stop after fade completes
    setTimeout(() => {
      try {
        source.stop();
        source.disconnect();
        if (fadeGain) fadeGain.disconnect();
      } catch (_) {
        // Source may already be stopped
      }
    }, fadeDuration * 1000 + 50);

    this._ambientSource = null;
    this._ambientFadeGain = null;
    this._ambientKey = null;
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Event Processing — Data-Driven Sound Triggers
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Process turn actions and play appropriate sounds.
   * Mirrors ParticleManager.processActions() — consumes the same
   * lastTurnActions data structure.
   *
   * @param {Array} actions — Array of action results from TURN_RESULT
   * @param {Object} players — Current players map (for position/visibility)
   */
  processActions(actions, players) {
    if (!this._canPlay() || !this.effectMap || !actions) return;
    if (this._hidden) return;

    const combat = this.effectMap.combat || {};
    const skills = this.effectMap.skills || {};

    for (const act of actions) {
      if (!act.success) {
        // Handle miss/dodge/block sounds
        this._processMiss(act, combat);
        continue;
      }

      switch (act.action_type) {
        case 'attack': {
          // Phase 15D: Crit distinction — high damage plays melee_crit instead
          const CRIT_THRESHOLD = 25;
          if (act.damage_dealt && act.damage_dealt >= CRIT_THRESHOLD && combat.melee_crit) {
            this._playCombatSound(combat.melee_crit, act);
          } else {
            this._playCombatSound(combat.melee_hit, act);
          }
          if (act.killed) this._playCombatSound(combat.death, act);
          break;
        }

        case 'ranged_attack':
          this._playCombatSound(combat.ranged_hit, act);
          if (act.killed) this._playCombatSound(combat.death, act);
          break;

        case 'skill':
          this._processSkillSound(act, skills, combat);
          break;

        case 'use_item':
          this._playCombatSound(combat.potion_use, act);
          break;

        case 'loot':
          this._playCombatSound(combat.loot_pickup, act);
          break;

        default:
          break;
      }
    }
  }

  /**
   * Process environment events (doors, chests).
   * Mirrors ParticleManager.processEnvironment().
   *
   * @param {Array} doorChanges — Door state changes from TURN_RESULT
   * @param {Array} chestOpened — Chest opened events from TURN_RESULT
   */
  processEnvironment(doorChanges, chestOpened) {
    if (!this._canPlay() || !this.effectMap) return;
    if (this._hidden) return;

    const env = this.effectMap.environment || {};

    if (doorChanges && doorChanges.length > 0) {
      // Play door sound once even if multiple doors change
      this._playCombatSound(env.door_open);
    }

    if (chestOpened && chestOpened.length > 0) {
      this._playCombatSound(env.chest_open);
    }
  }

  /**
   * Process special game events (portal, wave clear, floor descend, etc.)
   *
   * @param {string} eventKey — Event key matching a key in effectMap.events
   */
  processEvent(eventKey) {
    if (!this._canPlay() || !this.effectMap) return;
    if (this._hidden) return;

    const events = this.effectMap.events || {};
    this._playCombatSound(events[eventKey]);
  }

  /**
   * Play a UI sound (button clicks, menu interactions).
   *
   * @param {string} eventKey — Event key matching a key in effectMap.ui
   */
  playUI(eventKey) {
    if (!this._canPlay() || !this.effectMap) return;

    const ui = this.effectMap.ui || {};
    const mapping = ui[eventKey];
    if (!mapping) return;

    if (mapping.variants) {
      this.playVariant(mapping.variants, {
        volume: mapping.volume ?? 1.0,
        pitchVariance: mapping.pitchVariance ?? 0,
        channel: 'ui',
      });
    } else if (mapping.key) {
      this.play(mapping.key, {
        volume: mapping.volume ?? 1.0,
        pitchVariance: mapping.pitchVariance ?? 0,
        channel: 'ui',
      });
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Volume Control
  // ═══════════════════════════════════════════════════════════════════════════

  setMasterVolume(v) {
    this.masterVolume = Math.max(0, Math.min(1, v));
    this._applyVolumes();
    this._saveSettings();
  }

  setSfxVolume(v) {
    this.sfxVolume = Math.max(0, Math.min(1, v));
    this._applyVolumes();
    this._saveSettings();
  }

  setAmbientVolume(v) {
    this.ambientVolume = Math.max(0, Math.min(1, v));
    this._applyVolumes();
    this._saveSettings();
  }

  setUIVolume(v) {
    this.uiVolume = Math.max(0, Math.min(1, v));
    this._applyVolumes();
    this._saveSettings();
  }

  toggleMute() {
    this.muted = !this.muted;
    this._applyVolumes();
    this._saveSettings();
    return this.muted;
  }

  setMusicVolume(v) {
    this.musicVolume = Math.max(0, Math.min(1, v));
    if (this._musicAudio) {
      this._musicAudio.volume = this.muted ? 0 : this.musicVolume * this.masterVolume;
    }
    this._saveSettings();
  }

  /** Get all volume settings as a plain object (for UI display). */
  getSettings() {
    return {
      masterVolume: this.masterVolume,
      sfxVolume: this.sfxVolume,
      ambientVolume: this.ambientVolume,
      uiVolume: this.uiVolume,
      musicVolume: this.musicVolume,
      muted: this.muted,
    };
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Music Playlist
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Initialize the music playlist from the effectMap.
   * Shuffles the track list and begins playback.
   */
  initMusic() {
    if (!this.effectMap?.music?.tracks?.length) {
      console.warn('[AudioManager] No music tracks in effectMap');
      return;
    }

    // Build shuffled playlist
    this._musicPlaylist = this._shuffle([...this.effectMap.music.tracks]);
    this._musicIndex = 0;
    this._musicPaused = false;

    this._playCurrentTrack();
  }

  /** Play the track at the current playlist index. */
  _playCurrentTrack() {
    if (this._musicPlaylist.length === 0) return;

    const track = this._musicPlaylist[this._musicIndex];
    if (!track) return;

    // Clean up previous audio element
    if (this._musicAudio) {
      this._musicAudio.pause();
      this._musicAudio.removeAttribute('src');
      this._musicAudio.load();
    }

    // Normalize absolute paths for Electron file:// protocol
    const baseUrl = import.meta.env.BASE_URL;
    const resolvedPath = track.path.startsWith('/') ? `${baseUrl}${track.path.slice(1)}` : track.path;
    const audio = new Audio(resolvedPath);
    audio.volume = this.muted ? 0 : this.musicVolume * this.masterVolume;
    audio.loop = false;

    // Auto-advance to next track when current one ends
    audio.addEventListener('ended', () => {
      this.nextTrack();
    });

    audio.addEventListener('error', (e) => {
      console.warn(`[AudioManager] Music error for "${track.title}":`, e);
      // Skip to next track on error
      setTimeout(() => this.nextTrack(), 500);
    });

    this._musicAudio = audio;

    if (!this._musicPaused) {
      audio.play().catch((err) => {
        console.warn('[AudioManager] Music play blocked:', err.message);
      });
    }

    // Notify listeners (UI) about track change
    if (this._onMusicChange) {
      this._onMusicChange(this.getMusicState());
    }
  }

  /** Advance to the next track. */
  nextTrack() {
    if (this._musicPlaylist.length === 0) return;
    this._musicIndex = (this._musicIndex + 1) % this._musicPlaylist.length;

    // Reshuffle when we loop back to start
    if (this._musicIndex === 0) {
      this._musicPlaylist = this._shuffle([...this._musicPlaylist]);
    }

    this._playCurrentTrack();
  }

  /** Go to the previous track. */
  prevTrack() {
    if (this._musicPlaylist.length === 0) return;
    this._musicIndex = (this._musicIndex - 1 + this._musicPlaylist.length) % this._musicPlaylist.length;
    this._playCurrentTrack();
  }

  /** Toggle play/pause for music. Returns new paused state. */
  toggleMusic() {
    if (!this._musicAudio) {
      // First time — start playing
      this.initMusic();
      return false;
    }

    if (this._musicPaused) {
      this._musicPaused = false;
      this._musicAudio.play().catch(() => {});
    } else {
      this._musicPaused = true;
      this._musicAudio.pause();
    }

    if (this._onMusicChange) {
      this._onMusicChange(this.getMusicState());
    }

    return this._musicPaused;
  }

  /** Stop music entirely. */
  stopMusic() {
    if (this._musicAudio) {
      this._musicAudio.pause();
      this._musicAudio.removeAttribute('src');
      this._musicAudio.load();
      this._musicAudio = null;
    }
    this._musicPaused = false;
    this._musicIndex = -1;
  }

  /** Get current music state for UI display. */
  getMusicState() {
    const track = this._musicPlaylist[this._musicIndex];
    return {
      playing: !this._musicPaused && !!this._musicAudio,
      paused: this._musicPaused,
      title: track?.title || '',
      index: this._musicIndex,
      total: this._musicPlaylist.length,
    };
  }

  /** Register a callback for music state changes (for React UI). */
  onMusicChange(callback) {
    this._onMusicChange = callback;
  }

  /** Fisher-Yates shuffle. */
  _shuffle(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Internal Helpers
  // ═══════════════════════════════════════════════════════════════════════════

  /** @returns {boolean} Whether the manager is ready to play sounds */
  _canPlay() {
    return this._initialized && this.context && !this.muted;
  }

  /** Get the appropriate gain node for a channel name */
  _getChannelGain(channel) {
    switch (channel) {
      case 'ambient': return this._ambientGain;
      case 'ui': return this._uiGain;
      case 'sfx':
      default: return this._sfxGain;
    }
  }

  /** Apply current volume levels to all gain nodes */
  _applyVolumes() {
    if (!this._masterGain) return;

    const master = this.muted ? 0 : this.masterVolume;
    this._masterGain.gain.setValueAtTime(master, this.context?.currentTime || 0);
    this._sfxGain.gain.setValueAtTime(this.sfxVolume, this.context?.currentTime || 0);
    this._ambientGain.gain.setValueAtTime(this.ambientVolume, this.context?.currentTime || 0);
    this._uiGain.gain.setValueAtTime(this.uiVolume, this.context?.currentTime || 0);

    // Music uses HTML5 Audio — apply volume directly
    if (this._musicAudio) {
      this._musicAudio.volume = this.muted ? 0 : this.musicVolume * this.masterVolume;
    }
  }

  /**
   * Fetch and decode a single audio file into the buffer cache.
   *
   * @param {string} key — Cache key
   * @param {string} url — Path to the audio file (relative to public/)
   */
  async _preloadBuffer(key, url) {
    try {
      // Normalize absolute paths for Electron file:// protocol
      const baseUrl = import.meta.env.BASE_URL;
      const resolvedUrl = url.startsWith('/') ? `${baseUrl}${url.slice(1)}` : url;
      const response = await fetch(resolvedUrl);
      if (!response.ok) throw new Error(`HTTP ${response.status} for ${url}`);
      const arrayBuffer = await response.arrayBuffer();
      const audioBuffer = await this.context.decodeAudioData(arrayBuffer);
      this._buffers.set(key, audioBuffer);
    } catch (err) {
      console.warn(`[AudioManager] Failed to preload "${key}" from ${url}:`, err.message);
      throw err;
    }
  }

  /**
   * Walk the effect map and collect all unique { key, path } entries
   * that need to be preloaded.
   */
  _collectSoundPaths(effectMap) {
    const entries = [];
    const soundFiles = effectMap._soundFiles || {};

    // _soundFiles is the canonical key → path mapping
    for (const [key, path] of Object.entries(soundFiles)) {
      entries.push({ key, path });
    }

    return entries;
  }

  /**
   * Play a sound from a combat/environment mapping entry.
   * Supports single key, variant arrays, and per-sound options.
   */
  _playCombatSound(mapping, _act) {
    if (!mapping) return;

    if (mapping.variants) {
      this.playVariant(mapping.variants, {
        volume: mapping.volume ?? 1.0,
        pitchVariance: mapping.pitchVariance ?? 0.08,
        channel: 'sfx',
      });
    } else if (mapping.key) {
      this.play(mapping.key, {
        volume: mapping.volume ?? 1.0,
        pitchVariance: mapping.pitchVariance ?? 0.08,
        channel: 'sfx',
      });
    }
  }

  /** Handle miss/dodge/block sounds for failed actions. */
  _processMiss(act, combat) {
    const msg = (act.message || '').toLowerCase();
    if (msg.includes('dodged') || msg.includes('evaded')) {
      this._playCombatSound(combat.dodge, act);
    } else if (msg.includes('blocked') || msg.includes('reflects')) {
      this._playCombatSound(combat.block, act);
    } else if (act.action_type === 'attack' || act.action_type === 'ranged_attack') {
      this._playCombatSound(combat.miss, act);
    }
  }

  /** Handle skill-specific sounds, falling back to generic skill_cast. */
  _processSkillSound(act, skills, combat) {
    // Phase 25F: Undying Will revive trigger — dramatic resurrection sound
    // The revive action has heal_amount set (the revive HP), distinguishing
    // it from the initial buff cast (which has buff_applied). Play a unique
    // dramatic sound instead of the normal cast sound.
    if (act.skill_id === 'undying_will' && act.heal_amount) {
      this._playCombatSound({ key: 'skill_undying_revive', volume: 0.9, pitchVariance: 0 }, act);
      return;
    }

    // Check for a skill-specific sound mapping first
    const skillMapping = skills[act.skill_id];
    if (skillMapping) {
      this._playCombatSound(skillMapping, act);
    } else {
      // Fallback: generic skill cast sound
      this._playCombatSound(combat.skill_cast, act);
    }

    // Additional sounds for skill side-effects
    if (act.killed) {
      this._playCombatSound(combat.death, act);
    }
    if (act.heal_amount) {
      this._playCombatSound(combat.heal, act);
    }
  }

  // ── Tab-visibility lifecycle ──

  _onVisibilityChange() {
    this._hidden = document.hidden;
  }

  // ── Settings persistence (localStorage) ──

  _saveSettings() {
    try {
      const settings = {
        masterVolume: this.masterVolume,
        sfxVolume: this.sfxVolume,
        ambientVolume: this.ambientVolume,
        uiVolume: this.uiVolume,
        musicVolume: this.musicVolume,
        muted: this.muted,
      };
      localStorage.setItem('arena_audio_settings', JSON.stringify(settings));
    } catch (_) {
      // localStorage may not be available
    }
  }

  _loadSettings() {
    try {
      const raw = localStorage.getItem('arena_audio_settings');
      if (!raw) return;
      const settings = JSON.parse(raw);
      if (typeof settings.masterVolume === 'number') this.masterVolume = settings.masterVolume;
      if (typeof settings.sfxVolume === 'number') this.sfxVolume = settings.sfxVolume;
      if (typeof settings.ambientVolume === 'number') this.ambientVolume = settings.ambientVolume;
      if (typeof settings.uiVolume === 'number') this.uiVolume = settings.uiVolume;
      if (typeof settings.musicVolume === 'number') this.musicVolume = settings.musicVolume;
      if (typeof settings.muted === 'boolean') this.muted = settings.muted;
    } catch (_) {
      // Corrupted or unavailable — use defaults
    }
  }
}
