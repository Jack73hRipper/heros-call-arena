import React, { useState, useEffect, useCallback, useRef } from 'react';

/**
 * IntroSequence — Cinematic intro screens before the login lobby.
 *
 * Flow: studio splash (Rune Gate) → game title (Hero's Call Arena) → done
 * Click/key at any point fast-forwards through remaining screens.
 *
 * @param {object} props
 * @param {Function} props.onComplete — Called when the intro sequence finishes
 * @param {React.RefObject} props.audioManager — AudioManager ref for triggering music
 */
export default function IntroSequence({ onComplete, audioManager }) {
  // 'studio' → 'studio-fade' → 'title' → 'title-fade' → 'done'
  const [phase, setPhase] = useState('studio');
  const timerRef = useRef(null);
  const musicStartedRef = useRef(false);

  // Start music on first user interaction during intro
  const startMusic = useCallback(() => {
    if (musicStartedRef.current) return;
    const mgr = audioManager?.current;
    if (!mgr) return;
    // Resume AudioContext (browser autoplay policy)
    mgr.resume();
    // Start playlist if not already running
    if (mgr._musicIndex === -1 && mgr.effectMap?.music?.tracks?.length) {
      mgr.initMusic();
    }
    musicStartedRef.current = true;
  }, [audioManager]);

  // Generate the portal whoosh sound using Web Audio synthesis
  const playStudioCue = useCallback(() => {
    const mgr = audioManager?.current;
    if (!mgr?.context) return;
    const ctx = mgr.context;
    const now = ctx.currentTime;

    // Create a breathy noise burst filtered through a bandpass
    const duration = 2.0;
    const sampleRate = ctx.sampleRate;
    const bufferSize = sampleRate * duration;
    const noiseBuffer = ctx.createBuffer(1, bufferSize, sampleRate);
    const data = noiseBuffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * 0.5;
    }

    const noise = ctx.createBufferSource();
    noise.buffer = noiseBuffer;

    // Bandpass filter sweeping upward for a "whoosh" feel
    const filter = ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.Q.value = 2.5;
    filter.frequency.setValueAtTime(200, now);
    filter.frequency.exponentialRampToValueAtTime(1200, now + 0.6);
    filter.frequency.exponentialRampToValueAtTime(400, now + 1.8);

    // Low-frequency sine hum underneath
    const hum = ctx.createOscillator();
    hum.type = 'sine';
    hum.frequency.setValueAtTime(80, now);
    hum.frequency.linearRampToValueAtTime(120, now + 1.0);
    hum.frequency.linearRampToValueAtTime(60, now + 2.0);

    const humGain = ctx.createGain();
    humGain.gain.setValueAtTime(0, now);
    humGain.gain.linearRampToValueAtTime(0.06, now + 0.5);
    humGain.gain.linearRampToValueAtTime(0.03, now + 1.5);
    humGain.gain.linearRampToValueAtTime(0, now + 2.0);

    // Envelope for the noise whoosh
    const noiseGain = ctx.createGain();
    noiseGain.gain.setValueAtTime(0, now);
    noiseGain.gain.linearRampToValueAtTime(0.08, now + 0.3);
    noiseGain.gain.setValueAtTime(0.08, now + 0.8);
    noiseGain.gain.linearRampToValueAtTime(0, now + 1.8);

    // Route through the AudioManager's UI gain so it respects volume settings
    const outputNode = mgr._uiGain || mgr._masterGain || ctx.destination;

    noise.connect(filter);
    filter.connect(noiseGain);
    noiseGain.connect(outputNode);

    hum.connect(humGain);
    humGain.connect(outputNode);

    noise.start(now);
    noise.stop(now + duration);
    hum.start(now);
    hum.stop(now + duration);
  }, [audioManager]);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // Auto-advance through phases on timers
  useEffect(() => {
    switch (phase) {
      case 'studio':
        // Play the synthesized portal cue
        playStudioCue();
        timerRef.current = setTimeout(() => setPhase('studio-fade'), 3200);
        break;
      case 'studio-fade':
        timerRef.current = setTimeout(() => setPhase('title'), 1000);
        break;
      case 'title':
        timerRef.current = setTimeout(() => setPhase('title-fade'), 4500);
        break;
      case 'title-fade':
        timerRef.current = setTimeout(() => setPhase('done'), 800);
        break;
      case 'done':
        onComplete();
        break;
      default:
        break;
    }
    return () => clearTimer();
  }, [phase, onComplete, clearTimer, playStudioCue]);

  // Click/keypress fast-forwards through remaining screens
  const handleSkip = useCallback(() => {
    clearTimer();
    startMusic();
    switch (phase) {
      case 'studio':
        // Skip to title screen
        setPhase('studio-fade');
        timerRef.current = setTimeout(() => setPhase('title'), 600);
        break;
      case 'studio-fade':
        setPhase('title');
        break;
      case 'title':
        setPhase('title-fade');
        timerRef.current = setTimeout(() => setPhase('done'), 500);
        break;
      case 'title-fade':
        setPhase('done');
        break;
      default:
        break;
    }
  }, [phase, clearTimer, startMusic]);

  // Listen for keypress to skip
  useEffect(() => {
    const onKey = (e) => {
      // Don't skip on modifier keys alone
      if (['Shift', 'Control', 'Alt', 'Meta'].includes(e.key)) return;
      startMusic();
      handleSkip();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [handleSkip, startMusic]);

  // Also resume audio + start music on any click within the intro
  const handleClick = useCallback(() => {
    startMusic();
    handleSkip();
  }, [handleSkip, startMusic]);

  if (phase === 'done') return null;

  return (
    <div className="intro-sequence" onClick={handleClick}>
      {/* Screen 1: Rune Gate Studio */}
      {(phase === 'studio' || phase === 'studio-fade') && (
        <div className={`intro-studio${phase === 'studio-fade' ? ' intro-studio--fading' : ''}`}>
          <div className="intro-studio-bloom" />
          <img
            className="intro-studio-logo"
            src={`${import.meta.env.BASE_URL}rune-gate-studio.png`}
            alt="Rune Gate Studio"
            draggable={false}
          />
          <div className="intro-studio-particles" />
        </div>
      )}

      {/* Screen 2: Game Title */}
      {(phase === 'title' || phase === 'title-fade') && (
        <div className={`intro-title${phase === 'title-fade' ? ' intro-title--fading' : ''}`}>
          <div className="intro-title-bloom" />
          <div className="intro-title-embers" />
          <h1 className="intro-title-main">HERO&apos;S CALL</h1>
          <div className="intro-title-sub">A R E N A</div>
          <div className="intro-title-divider">◆</div>
          <p className="intro-title-tagline">
            Glory awaits those bold enough to answer the call.
          </p>
        </div>
      )}

      <span className="intro-skip-hint">Click or press any key to skip</span>
    </div>
  );
}
