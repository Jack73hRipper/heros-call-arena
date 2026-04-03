#!/usr/bin/env python3
"""
generate_sfx.py — Procedural SFX generator for Hero's Call Arena
================================================================
Synthesises ~85 unique .wav files using numpy + scipy, organized
into the same category folders the game expects.

Each sound is designed for a grimdark pixel-art roguelike:
  - Short (0.05–2s), punchy, lo-fi character
  - Noise bursts for impacts, filtered sweeps for magic
  - Tonal chimes for heals, crunchy clips for crits
  - Dark drones for debuffs, sharp pops for UI

Run:
    python generate_sfx.py                  # → outputs into ./generated/
    python generate_sfx.py --out ../../client/public/audio  # → direct into game

The script also writes generated-manifest.json listing every file
produced with metadata, used by the Audio Workbench synth tab.
"""

import argparse
import json
import os
import struct
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, lfilter, sawtooth, square
from scipy.ndimage import minimum_filter1d, uniform_filter1d

# ═══════════════════════════════════════════════════════════════
# Core DSP primitives
# ═══════════════════════════════════════════════════════════════

RATE = 44100  # Sample rate


def _t(dur):
    """Time array for given duration in seconds."""
    return np.linspace(0, dur, int(RATE * dur), endpoint=False)


def _env_adsr(n, a=0.01, d=0.05, s=0.6, r=0.15):
    """ADSR envelope. a/d/r in seconds, s = sustain level (0-1)."""
    a_n = int(a * RATE)
    d_n = int(d * RATE)
    r_n = int(r * RATE)
    s_n = max(0, n - a_n - d_n - r_n)
    env = np.concatenate([
        np.linspace(0, 1, a_n),
        np.linspace(1, s, d_n),
        np.full(s_n, s),
        np.linspace(s, 0, r_n),
    ])
    return env[:n]


def _env_perc(n, attack=0.005, decay_frac=1.0):
    """Percussive envelope — fast attack, exponential decay."""
    a_n = max(1, int(attack * RATE))
    d_n = n - a_n
    attack_env = np.linspace(0, 1, a_n)
    decay_env = np.exp(-np.linspace(0, 5 * decay_frac, d_n))
    return np.concatenate([attack_env, decay_env])[:n]


def _env_fade_in(n, dur=0.3):
    """Fade-in then sustain."""
    f = int(dur * RATE)
    if f >= n:
        return np.linspace(0, 1, n)
    return np.concatenate([np.linspace(0, 1, f), np.ones(n - f)])


def _noise(n, color='white'):
    """Generate noise: white, pink, or brown."""
    white = np.random.randn(n)
    if color == 'white':
        return white
    elif color == 'pink':
        # Simple pink noise via cumulative filter
        b = [0.049922035, -0.095993537, 0.050612699, -0.004709510]
        a = [1, -2.494956002, 2.017265875, -0.522189400]
        return lfilter(b, a, white)
    elif color == 'brown':
        return np.cumsum(white) / np.sqrt(n)
    return white


def _lowpass(sig, cutoff, order=4):
    """Butterworth low-pass filter."""
    nyq = RATE / 2
    b, a = butter(order, min(cutoff / nyq, 0.99), btype='low')
    return lfilter(b, a, sig)


def _highpass(sig, cutoff, order=4):
    """Butterworth high-pass filter."""
    nyq = RATE / 2
    b, a = butter(order, min(cutoff / nyq, 0.99), btype='high')
    return lfilter(b, a, sig)


def _bandpass(sig, low, high, order=3):
    """Butterworth band-pass filter."""
    nyq = RATE / 2
    b, a = butter(order, [min(low / nyq, 0.98), min(high / nyq, 0.99)], btype='band')
    return lfilter(b, a, sig)


def _distort(sig, gain=3.0, clip=0.7):
    """Soft-clip distortion."""
    return np.tanh(sig * gain) * clip


def _mix(*signals):
    """Mix signals of potentially different lengths, zero-padding shorter ones."""
    max_n = max(len(s) for s in signals)
    result = np.zeros(max_n)
    for s in signals:
        result[:len(s)] += s
    return result


def _normalize(sig, peak=0.9):
    """Normalize to peak amplitude."""
    mx = np.max(np.abs(sig))
    if mx > 0:
        return sig * (peak / mx)
    return sig


def _write_wav(path, sig):
    """Write mono or stereo 16-bit WAV at 44100 Hz.

    sig can be:
      - 1-D array (mono)
      - 2-D array with shape (2, N) — [left, right]
    """
    if sig.ndim == 2:
        # Stereo — normalize each channel relative to global peak
        peak = max(np.max(np.abs(sig[0])), np.max(np.abs(sig[1])))
        if peak > 0:
            sig = sig * (0.85 / peak)
        # Master dynamics — multiband compression + limiting per channel
        sig = np.array([_master_dynamics(sig[0]), _master_dynamics(sig[1])])
        sig = np.clip(sig, -1, 1)
        # Interleave L/R for WAV format
        interleaved = np.empty(sig.shape[1] * 2, dtype=np.int16)
        interleaved[0::2] = (sig[0] * 32767).astype(np.int16)
        interleaved[1::2] = (sig[1] * 32767).astype(np.int16)
        channels = 2
        data = interleaved.tobytes()
    else:
        sig = _normalize(sig, 0.85)
        # Master dynamics — multiband compression + limiting
        sig = _master_dynamics(sig)
        sig = np.clip(sig, -1, 1)
        channels = 1
        data = (sig * 32767).astype(np.int16).tobytes()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(str(path), 'w') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(data)


def _sine(freq, dur):
    return np.sin(2 * np.pi * freq * _t(dur))


def _saw(freq, dur):
    return sawtooth(2 * np.pi * freq * _t(dur))


def _sq(freq, dur, duty=0.5):
    return square(2 * np.pi * freq * _t(dur), duty=duty)


def _sweep(f0, f1, dur):
    """Linear frequency sweep."""
    t = _t(dur)
    phase = 2 * np.pi * (f0 * t + (f1 - f0) * t ** 2 / (2 * dur))
    return np.sin(phase)


# ═══════════════════════════════════════════════════════════════
# Advanced DSP — Reverb, Chorus, Stereo, Resonant Filter Sweeps,
#                FM Synthesis, Bitcrusher, Ring Mod, Delay,
#                Formant Filter, Tremolo, Pitch Envelope
# ═══════════════════════════════════════════════════════════════


def _fm_osc(carrier_freq, mod_freq, mod_index, dur):
    """FM synthesis oscillator.

    carrier_freq: carrier frequency (Hz)
    mod_freq: modulator frequency (Hz)
    mod_index: modulation depth (0 = pure sine, higher = more harmonics)
    Returns a mono signal.

    Low mod_index (0.5–2): warm/bell tones
    Mid mod_index (3–6): metallic / plucked string
    High mod_index (7+): harsh / aggressive
    """
    t = _t(dur)
    modulator = mod_index * np.sin(2 * np.pi * mod_freq * t)
    return np.sin(2 * np.pi * carrier_freq * t + modulator)


def _bitcrush(sig, bit_depth=8, downsample=4):
    """Bit-crusher / sample-rate reduction for lo-fi retro character.

    bit_depth: quantization depth (1–16, lower = crunchier)
    downsample: sample-rate reduction factor (1 = none, higher = grittier)
    """
    bit_depth = max(1, min(16, int(bit_depth)))
    downsample = max(1, int(downsample))
    # Quantize amplitude
    levels = 2 ** bit_depth
    sig = np.round(sig * levels / 2) / (levels / 2)
    # Sample-rate reduction (sample-and-hold)
    if downsample > 1:
        for i in range(0, len(sig), downsample):
            sig[i:i + downsample] = sig[i]
    return sig


def _ring_mod(sig, mod_freq, mix=0.5):
    """Ring modulation — multiply signal by a modulator oscillator.

    Produces inharmonic sum/difference frequencies for metallic,
    alien, and otherworldly tones.

    mod_freq: modulator frequency (Hz).
    mix: 0.0 = dry only, 1.0 = full ring mod.
    """
    n = len(sig)
    t = np.arange(n) / RATE
    modulator = np.sin(2 * np.pi * mod_freq * t)
    wet = sig * modulator
    return sig * (1 - mix) + wet * mix


def _delay(sig, delay_ms=150, feedback=0.3, wet=0.3, filter_cutoff=0):
    """Delay / echo effect with optional feedback filtering.

    delay_ms: delay time in milliseconds
    feedback: amount of output fed back (0–0.85, clamped for safety)
    wet: mix level of delayed signal
    filter_cutoff: if > 0, lowpass the feedback path (darkening echoes)
    """
    delay_samp = max(1, int(delay_ms * RATE / 1000))
    feedback = min(0.85, max(0.0, feedback))
    n = len(sig)
    buf = np.zeros(n + delay_samp * 8)  # extra space for tail
    buf[:n] = sig
    for i in range(delay_samp, len(buf)):
        buf[i] += feedback * buf[i - delay_samp]
    # Optional feedback darkening
    if filter_cutoff > 0:
        tail = buf[n:]
        if len(tail) > 0:
            tail = _lowpass(tail, filter_cutoff, order=2)
            buf[n:] = tail
    # Trim to original length + one echo tail
    out_len = min(len(buf), n + delay_samp * 4)
    out = np.zeros(out_len)
    out[:n] = sig * (1 - wet)
    out[:out_len] += buf[:out_len] * wet
    return out[:out_len]


def _formant(sig, vowel='a', intensity=0.5):
    """Formant filter — resonant peaks simulating vowel shapes.

    Adds voice-like character to tones.
    vowel: 'a', 'e', 'i', 'o', 'u'
    intensity: 0.0–1.0, how strong the formant coloring is.
    """
    formants = {
        'a': [(800, 80), (1150, 90), (2900, 120)],
        'e': [(400, 60), (1600, 80), (2700, 120)],
        'i': [(350, 50), (2100, 90), (2900, 100)],
        'o': [(450, 70), (800, 80), (2830, 100)],
        'u': [(325, 50), (700, 60), (2530, 100)],
    }
    peaks = formants.get(vowel, formants['a'])
    n = len(sig)
    nyq = RATE / 2

    colored = np.zeros(n)
    for center, bw in peaks:
        low = max(20, center - bw)
        high = min(nyq * 0.95, center + bw)
        if low >= high:
            continue
        try:
            b, a = butter(2, [low / nyq, high / nyq], btype='band')
            colored += lfilter(b, a, sig) * (1.0 / len(peaks))
        except Exception:
            pass
    return sig * (1 - intensity) + colored * intensity


def _tremolo(sig, rate=5.0, depth=0.5, shape='sine'):
    """Tremolo — amplitude modulation.

    rate: LFO speed in Hz
    depth: modulation depth (0.0–1.0)
    shape: 'sine' or 'triangle'
    """
    n = len(sig)
    t = np.arange(n) / RATE
    if shape == 'triangle':
        lfo = 2 * np.abs(2 * (t * rate - np.floor(t * rate + 0.5))) - 1
    else:
        lfo = np.sin(2 * np.pi * rate * t)
    # LFO range: 1-depth … 1
    envelope = 1.0 - depth * 0.5 * (1.0 - lfo)
    return sig * envelope


def _pitch_env_osc(freq, dur, env_type='drop', amount=1.0, waveform='sine'):
    """Oscillator with pitch envelope for more expressive tones.

    env_type:
      'drop'  — starts at freq * (1 + amount), drops to freq
      'rise'  — starts at freq / (1 + amount), rises to freq
      'overshoot' — overshoots up then settles to freq
    amount: intensity of pitch movement (0–5)
    """
    t = _t(dur)
    n = len(t)

    if env_type == 'drop':
        # Exponential pitch drop
        pitch_env = freq * (1.0 + amount * np.exp(-t * 20))
    elif env_type == 'rise':
        pitch_env = freq * (1.0 - (amount / (1 + amount)) * np.exp(-t * 15))
    else:  # overshoot
        pitch_env = freq * (1.0 + amount * 0.5 * np.exp(-t * 12) * np.cos(2 * np.pi * 8 * t))

    phase = np.cumsum(2 * np.pi * pitch_env / RATE)

    if waveform == 'saw':
        return sawtooth(phase)
    elif waveform == 'square':
        return square(phase)
    return np.sin(phase)


def _reverb(sig, decay=0.3, wet=0.25, room='dungeon'):
    """Reverb processor — algorithmic or convolution.

    Algorithmic (Schroeder) presets:
      'dungeon' — short, dark (default).  Low-ceiling stone room.
      'hall'    — longer tail, brighter.   Cathedral / boss room.
      'tight'  — very short, metallic.     Impacts / UI.

    Convolution presets (higher quality, realistic spatial imaging):
      'stone_chamber' — Dense reflections, medium dark tail. Dungeon rooms.
      'cathedral'     — Wide, long bright tail. Boss rooms / holy magic.
      'metal_room'    — Short, bright, ringy. Weapon impacts.
      'crypt'         — Tight, dark, oppressive. Death / horror sounds.
    """
    # Convolution reverb rooms — delegate to _conv_reverb
    if room in CONV_REVERB_ROOMS:
        return _conv_reverb(sig, room=room, wet=wet, decay=decay)

    presets = {
        'dungeon': {
            'comb_delays': [1117, 1189, 1277, 1361],  # in samples
            'comb_gains':  [0.40, 0.37, 0.33, 0.30],
            'ap_delays':   [227, 131],
            'ap_gain':     0.5,
            'damping':     2500,   # LP cutoff on feedback
        },
        'hall': {
            'comb_delays': [1557, 1617, 1741, 1847],
            'comb_gains':  [0.45, 0.42, 0.38, 0.35],
            'ap_delays':   [307, 181, 107],
            'ap_gain':     0.5,
            'damping':     5000,
        },
        'tight': {
            'comb_delays': [557, 613, 691, 743],
            'comb_gains':  [0.30, 0.27, 0.24, 0.21],
            'ap_delays':   [127, 79],
            'ap_gain':     0.45,
            'damping':     2000,
        },
    }
    p = presets.get(room, presets['dungeon'])
    n = len(sig)

    # Scale comb gains by the decay parameter
    comb_sum = np.zeros(n)
    for delay, gain in zip(p['comb_delays'], p['comb_gains']):
        buf = np.zeros(n)
        g = gain * decay / 0.3  # normalize around default decay
        g = min(g, 0.65)  # safety clamp to prevent blow-up
        for i in range(delay, n):
            buf[i] = sig[i] + g * buf[i - delay]
        # Damp the comb output
        buf = _lowpass(buf, p['damping'], order=2)
        comb_sum += buf

    comb_sum /= len(p['comb_delays'])

    # Allpass filters in series
    out = comb_sum
    for delay in p['ap_delays']:
        g = p['ap_gain']
        buf = np.zeros(n)
        for i in range(delay, n):
            buf[i] = -g * out[i] + out[i - delay] + g * buf[i - delay]
        out = buf

    return sig * (1 - wet) + out * wet


def _chorus(sig, voices=3, max_delay_ms=8, depth_ms=3, rate_hz=1.2):
    """Chorus effect — layers detuned/delayed copies for thickness.

    voices:  number of chorus copies (not counting dry signal)
    max_delay_ms: base delay in ms for each voice
    depth_ms: LFO modulation depth in ms
    rate_hz: LFO speed
    """
    n = len(sig)
    t = np.arange(n) / RATE
    out = sig.copy()

    for v in range(voices):
        # Each voice gets a different LFO phase offset
        phase = 2 * np.pi * v / voices
        lfo = np.sin(2 * np.pi * rate_hz * t + phase)

        # Time-varying delay in samples
        base_delay = int(max_delay_ms * RATE / 1000)
        depth_samp = int(depth_ms * RATE / 1000)
        delay_arr = base_delay + (lfo * depth_samp).astype(int)
        delay_arr = np.clip(delay_arr, 1, n - 1)

        # Build delayed signal using integer delay (efficient)
        indices = np.arange(n) - delay_arr
        indices = np.clip(indices, 0, n - 1)
        delayed = sig[indices]

        # Slight detune per voice (±3–6 cents via pitch-shift approximation)
        # Done by a tiny speed-up/slow-down of the index reading
        cents = (v - voices / 2) * 4  # spread ±cents
        ratio = 2 ** (cents / 1200)
        resampled_indices = (np.arange(n) * ratio).astype(int)
        resampled_indices = np.clip(resampled_indices, 0, n - 1)
        delayed = delayed[resampled_indices]

        out += delayed * (0.35 / voices)

    return _normalize(out)


def _stereo(sig, width=0.4, mode='haas'):
    """Convert mono signal to stereo (2, N) array.

    Modes:
      'haas'    — short delay on one channel (natural stereo width)
      'spread'  — decorrelate with slight pitch/delay offset each channel
      'mid_side'— duplicate with subtle filtering difference per channel
    Returns shape (2, N).
    """
    n = len(sig)

    if mode == 'haas':
        delay_samp = int(width * 0.02 * RATE)  # width 0–1 → 0–20ms
        delay_samp = max(1, min(delay_samp, int(0.025 * RATE)))
        left = sig.copy()
        right = np.zeros(n)
        right[delay_samp:] = sig[:-delay_samp] if delay_samp > 0 else sig
        # Attenuate delayed channel slightly
        right *= 0.95
        return np.array([left, right])

    elif mode == 'spread':
        # Different micro-delays + subtle detune per channel
        delay_l = int(3 * RATE / 1000)   # 3ms
        delay_r = int(7 * RATE / 1000)   # 7ms
        left = np.zeros(n)
        right = np.zeros(n)
        left[delay_l:] = sig[:-delay_l] if delay_l > 0 else sig
        right[delay_r:] = sig[:-delay_r] if delay_r > 0 else sig
        # Tiny pitch shift on right channel (2 cents)
        ratio = 2 ** (2 / 1200)
        idx = (np.arange(n) * ratio).astype(int)
        idx = np.clip(idx, 0, n - 1)
        right = right[idx] * 0.97
        return np.array([left, right])

    else:  # mid_side
        left = sig.copy()
        right = _lowpass(sig.copy(), 6000, order=2)  # slightly darker right
        # Tiny noise decorrelation
        right += np.random.randn(n) * 0.003
        return np.array([left, right])


def _resonant_sweep(sig, f_start, f_end, q=4.0, order=2):
    """Apply a resonant bandpass filter whose center frequency sweeps
    from f_start to f_end over the signal duration.

    Processes in overlapping chunks to simulate time-varying cutoff.
    q: resonance / quality factor (higher = sharper peak).
    """
    n = len(sig)
    chunk_size = max(256, int(RATE * 0.01))  # ~10ms chunks
    n_chunks = max(1, n // chunk_size)
    out = np.zeros(n)
    freqs = np.linspace(f_start, f_end, n_chunks)
    nyq = RATE / 2

    for i in range(n_chunks):
        start = i * chunk_size
        end = min(start + chunk_size + 64, n)  # slight overlap for continuity

        fc = freqs[i]
        bw = fc / q
        low = max(20, fc - bw / 2)
        high = min(nyq * 0.95, fc + bw / 2)
        if low >= high:
            low = max(20, high - 50)
        try:
            b, a = butter(order, [low / nyq, high / nyq], btype='band')
            chunk = lfilter(b, a, sig[start:end])
            # Write only the non-overlapping portion
            write_end = min(start + chunk_size, n)
            out[start:write_end] = chunk[:write_end - start]
        except Exception:
            out[start:min(start + chunk_size, n)] = sig[start:min(start + chunk_size, n)]

    return out


# ═══════════════════════════════════════════════════════════════
# Pro DSP — Convolution Reverb, Karplus-Strong, Modal Synthesis,
#            Multiband Compressor, Brick-wall Limiter
# ═══════════════════════════════════════════════════════════════


# ── Convolution Reverb ────────────────────────────────────────

_IR_CACHE = {}  # Cached impulse responses keyed by (room_type, duration)


def _generate_ir(room_type='stone_chamber', duration=1.0):
    """Generate a synthetic impulse response for convolution reverb.

    Produces realistic spatial characteristics by modeling early
    reflections as discrete taps and the diffuse tail as shaped,
    filtered noise with exponential decay.

    Rooms:
      'stone_chamber' — Dense early reflections, medium dark tail
      'cathedral'     — Wide, long bright tail with late diffusion
      'metal_room'    — Short, bright, ringy. Weapon impacts.
      'crypt'         — Tight, dark, oppressive. Horror/death.
    """
    n = int(RATE * duration)
    ir = np.zeros(n)

    configs = {
        'stone_chamber': {
            'early_taps': [
                (0.008, 0.60), (0.013, 0.45), (0.019, 0.35),
                (0.027, 0.28), (0.034, 0.22), (0.043, 0.18),
                (0.055, 0.14), (0.068, 0.10),
            ],
            'tail_decay': 4.5,
            'tail_lp': 3000,
            'tail_hp': 80,
            'predelay': 0.005,
            'density': 1.0,
            'diffusion_lp': 4000,
        },
        'cathedral': {
            'early_taps': [
                (0.012, 0.50), (0.022, 0.40), (0.035, 0.35),
                (0.048, 0.30), (0.065, 0.25), (0.082, 0.20),
                (0.105, 0.16), (0.130, 0.12), (0.160, 0.09),
            ],
            'tail_decay': 2.8,
            'tail_lp': 5000,
            'tail_hp': 60,
            'predelay': 0.015,
            'density': 1.5,
            'diffusion_lp': 6000,
        },
        'metal_room': {
            'early_taps': [
                (0.003, 0.70), (0.006, 0.55), (0.010, 0.40),
                (0.015, 0.30), (0.020, 0.22), (0.026, 0.15),
            ],
            'tail_decay': 7.0,
            'tail_lp': 6000,
            'tail_hp': 200,
            'predelay': 0.002,
            'density': 0.8,
            'diffusion_lp': 8000,
        },
        'crypt': {
            'early_taps': [
                (0.006, 0.65), (0.011, 0.50), (0.017, 0.38),
                (0.024, 0.28), (0.032, 0.20), (0.041, 0.14),
            ],
            'tail_decay': 5.5,
            'tail_lp': 2000,
            'tail_hp': 50,
            'predelay': 0.004,
            'density': 1.2,
            'diffusion_lp': 2500,
        },
    }

    cfg = configs.get(room_type, configs['stone_chamber'])
    pd_samples = int(cfg['predelay'] * RATE)

    # Early reflections — discrete taps with alternating polarity
    for i, (delay, amp) in enumerate(cfg['early_taps']):
        tap_idx = pd_samples + int(delay * RATE)
        if tap_idx < n:
            polarity = 1 if i % 2 == 0 else -1
            ir[tap_idx] = amp * polarity

    # Diffuse tail — exponentially-decaying shaped noise
    last_tap = cfg['early_taps'][-1][0] if cfg['early_taps'] else 0
    tail_start = pd_samples + int(last_tap * RATE)
    tail_len = n - tail_start
    if tail_len > 0:
        rng = np.random.RandomState(42 + abs(hash(room_type)) % 1000)
        tail = rng.randn(tail_len) * cfg['density']
        decay_env = np.exp(-np.linspace(0, cfg['tail_decay'], tail_len))
        tail *= decay_env
        tail = _lowpass(tail, cfg['tail_lp'], order=2)
        if cfg['tail_hp'] > 20:
            tail = _highpass(tail, cfg['tail_hp'], order=2)
        # Smooth onset
        fade_n = min(int(0.005 * RATE), tail_len)
        if fade_n > 0:
            tail[:fade_n] *= np.linspace(0, 1, fade_n)
        ir[tail_start:] += tail * 0.3

    # Diffusion pass — convolve with tiny random kernel for density
    diff_n = max(2, int(0.001 * RATE))
    rng2 = np.random.RandomState(123 + abs(hash(room_type)) % 500)
    diff_kernel = rng2.randn(diff_n)
    diff_kernel *= np.exp(-np.linspace(0, 3, diff_n))
    diff_kernel /= np.sqrt(np.sum(diff_kernel ** 2) + 1e-10)
    ir = fftconvolve(ir, diff_kernel, mode='same')

    # Final shaping
    ir = _lowpass(ir, cfg['diffusion_lp'], order=2)

    # Normalize IR
    ir_max = np.max(np.abs(ir))
    if ir_max > 0:
        ir = ir / ir_max

    return ir


def _get_ir(room_type, duration=1.0):
    """Retrieve (or generate and cache) an impulse response."""
    key = (room_type, round(duration, 3))
    if key not in _IR_CACHE:
        _IR_CACHE[key] = _generate_ir(room_type, duration)
    return _IR_CACHE[key]


CONV_REVERB_ROOMS = {'stone_chamber', 'cathedral', 'metal_room', 'crypt'}


def _conv_reverb(sig, room='stone_chamber', wet=0.25, decay=0.3):
    """Convolution reverb using synthetic impulse responses.

    Produces far more natural spatial characteristics than
    algorithmic (Schroeder) reverb — realistic early reflections,
    smooth diffuse tail, and authentic room coloring.

    room: 'stone_chamber', 'cathedral', 'metal_room', 'crypt'
    wet: wet/dry mix (0.0–1.0)
    decay: scales IR duration and intensity (0.05–1.5)
    """
    ir_dur = max(0.2, min(2.0, decay * 2.5))
    ir = _get_ir(room, ir_dur)

    # Scale IR energy by decay
    ir_scaled = ir * np.clip(decay, 0.05, 1.5)

    # FFT-based convolution (fast, even for long signals)
    wet_sig = fftconvolve(sig, ir_scaled, mode='full')[:len(sig)]

    return sig * (1 - wet) + wet_sig * wet


# ── Karplus-Strong / Physical Modeling ────────────────────────

def _karplus_strong(freq, dur, brightness=0.5, damping=0.5,
                    pluck_position=0.5, body_size=0.0):
    """Karplus-Strong plucked string synthesis.

    Physical modeling of a vibrating string.  Produces realistic
    plucked string, metallic, and bell-like tones that sound
    *physical* rather than electronic.

    freq:           fundamental frequency (Hz)
    dur:            duration in seconds
    brightness:     0.0 = very dark/muted, 1.0 = bright/metallic
    damping:        0.0 = long ring, 1.0 = dies quickly
    pluck_position: 0.0–1.0, affects harmonic content
                    0.5 = full harmonics, near 0 or 1 = thinner
    body_size:      0.0 = no body resonance, 1.0 = warm body
    """
    n = int(RATE * dur)
    period = max(2, int(RATE / freq))

    # Initial excitation — filtered noise burst
    rng = np.random.RandomState(int(freq * 100) % 2**31)
    excitation = rng.randn(period)

    # Pluck position comb filter — removes harmonics at pluck point
    if 0.01 < pluck_position < 0.99:
        pp = max(1, int(period * pluck_position))
        exc_f = np.zeros(period)
        for i in range(period):
            exc_f[i] = excitation[i]
            if i >= pp:
                exc_f[i] -= excitation[i - pp] * 0.5
        excitation = exc_f

    # Brightness shapes initial spectrum
    if brightness < 0.95:
        cutoff = 600 + brightness * 9000
        nyq = RATE / 2
        if cutoff < nyq * 0.95:
            b, a = butter(2, cutoff / nyq, btype='low')
            excitation = lfilter(b, a, excitation)

    # Normalize excitation
    exc_max = np.max(np.abs(excitation))
    if exc_max > 0:
        excitation /= exc_max

    # Output buffer
    out = np.zeros(n)
    out[:period] = excitation

    # Damping coefficient for the averaging filter
    damp = 0.3 + damping * 0.55  # Range: 0.3–0.85

    # Extended KS with first-order IIR lowpass in feedback loop
    prev = 0.0
    for i in range(period, n):
        current = out[i - period]
        filtered = (1 - damp) * current + damp * prev
        out[i] = filtered
        prev = filtered

    # Body resonance — warmth through resonant lowpass
    if body_size > 0.01:
        body_freq = 80 + (1 - body_size) * 200
        body = _lowpass(out.copy(), body_freq, order=2) * body_size * 0.3
        out = out + body

    return out


def _modal_synthesis(modes, dur):
    """Modal synthesis for metallic / resonant body sounds.

    Each mode represents a resonant frequency of a physical object
    (bell, metal plate, shield, sword strike).

    modes: list of (freq_hz, amplitude, decay_seconds) tuples
    dur: total duration in seconds
    """
    n = int(RATE * dur)
    t = _t(dur)
    out = np.zeros(n)

    for freq, amp, decay_time in modes:
        mode_sig = np.sin(2 * np.pi * freq * t)
        mode_env = np.exp(-t / max(0.001, decay_time))
        out += mode_sig * mode_env * amp

    return out


# ── Multiband Compressor + Limiter ────────────────────────────

def _compress_band(sig, threshold_db=-12.0, ratio=3.0,
                   attack_ms=5.0, release_ms=50.0, makeup_db=0.0):
    """Single-band dynamic range compressor.

    Shapes dynamics for punchier, more consistent output.

    threshold_db: level above which compression starts
    ratio:        compression ratio (e.g. 3.0 = 3:1)
    attack_ms:    how fast compressor responds to transients
    release_ms:   how fast compressor releases
    makeup_db:    post-compression gain
    """
    n = len(sig)
    if n == 0:
        return sig

    threshold = 10 ** (threshold_db / 20.0)
    attack_coeff = np.exp(-1.0 / max(1, attack_ms * RATE / 1000.0))
    release_coeff = np.exp(-1.0 / max(1, release_ms * RATE / 1000.0))

    # Envelope follower
    env = np.zeros(n)
    env[0] = abs(sig[0])
    for i in range(1, n):
        abs_val = abs(sig[i])
        if abs_val > env[i - 1]:
            env[i] = attack_coeff * env[i - 1] + (1 - attack_coeff) * abs_val
        else:
            env[i] = release_coeff * env[i - 1] + (1 - release_coeff) * abs_val

    # Gain computation — compress above threshold
    gain = np.ones(n)
    above = env > threshold
    if np.any(above):
        # Output level for samples above threshold
        compressed_env = threshold * (env[above] / threshold) ** (1.0 / ratio)
        gain[above] = compressed_env / (env[above] + 1e-10)

    out = sig * gain

    # Makeup gain
    if makeup_db != 0:
        out *= 10 ** (makeup_db / 20.0)

    return out


def _multiband_compress(sig, low_cut=250, high_cut=4000,
                        low_thresh=-10, mid_thresh=-14, high_thresh=-12,
                        low_ratio=2.5, mid_ratio=3.0, high_ratio=2.5,
                        low_makeup=2.0, mid_makeup=1.5, high_makeup=2.0):
    """3-band dynamic range compressor.

    Splits signal into low/mid/high bands via Butterworth crossovers,
    compresses each band independently, then recombines.

    Produces professional, balanced output where lows are punchy,
    mids are present, and highs are controlled.
    """
    n = len(sig)
    if n < 64:
        return sig

    nyq = RATE / 2

    # Crossover filters (2nd-order Butterworth)
    b_lo, a_lo = butter(2, min(low_cut / nyq, 0.95), btype='low')
    b_hi, a_hi = butter(2, min(high_cut / nyq, 0.95), btype='high')

    low = lfilter(b_lo, a_lo, sig)
    high = lfilter(b_hi, a_hi, sig)
    mid = sig - low - high  # Residual mid band

    # Compress each band
    low_c = _compress_band(low, threshold_db=low_thresh, ratio=low_ratio,
                           attack_ms=10, release_ms=80, makeup_db=low_makeup)
    mid_c = _compress_band(mid, threshold_db=mid_thresh, ratio=mid_ratio,
                           attack_ms=5, release_ms=50, makeup_db=mid_makeup)
    high_c = _compress_band(high, threshold_db=high_thresh, ratio=high_ratio,
                            attack_ms=3, release_ms=40, makeup_db=high_makeup)

    return low_c + mid_c + high_c


def _limiter(sig, ceiling_db=-0.5):
    """Brick-wall peak limiter with smooth gain reduction.

    Prevents any sample from exceeding the ceiling level.
    Uses minimum_filter look-ahead and smoothing for transparent,
    click-free limiting.
    """
    ceiling = 10 ** (ceiling_db / 20.0)
    if len(sig) == 0 or np.max(np.abs(sig)) <= ceiling:
        return sig

    abs_sig = np.abs(sig) + 1e-10
    gain = np.minimum(1.0, ceiling / abs_sig)

    # Look-ahead minimum + smoothing for click-free operation (2ms window)
    win = max(3, int(0.002 * RATE))
    gain = minimum_filter1d(gain, size=win)
    gain = uniform_filter1d(gain, size=win)

    return sig * gain


# Master dynamics enable flag — set False to bypass
MASTER_DYNAMICS_ENABLED = True


def _master_dynamics(sig):
    """Master dynamics chain: multiband compression → brick-wall limiter.

    Applied automatically to every sound during _write_wav for
    professional, consistent output levels.
    """
    if not MASTER_DYNAMICS_ENABLED:
        return sig
    if len(sig) < 64:
        return sig

    # Multiband compression — tightens dynamics per frequency band
    sig = _multiband_compress(sig)

    # Brick-wall limiter — ceiling at -0.5 dB
    sig = _limiter(sig, ceiling_db=-0.5)

    return sig


# ═══════════════════════════════════════════════════════════════
# Sound generators — one function per sound character
# ═══════════════════════════════════════════════════════════════

# ── COMBAT ────────────────────────────────────────────────────

def gen_melee_hit(variant=1):
    """Crunchy impact — noise burst + low thud, slightly varied per variant."""
    dur = 0.15 + variant * 0.02
    n = int(RATE * dur)
    # Noise burst (body of the hit)
    hit = _noise(n, 'white') * _env_perc(n, attack=0.002, decay_frac=1.2)
    hit = _bandpass(hit, 200 + variant * 80, 3000 + variant * 200)
    # Low thump sub with pitch-drop for weight
    sub = _pitch_env_osc(60 + variant * 5, dur, env_type='drop', amount=1.2)
    sub *= _env_perc(n, attack=0.001, decay_frac=0.8)
    # Transient click
    click_n = int(RATE * 0.008)
    click = _noise(click_n, 'white') * np.linspace(1, 0, click_n) * 0.8
    mono = _normalize(_mix(hit * 0.7, sub * 0.5, click * 0.9))
    mono = _reverb(mono, decay=0.15, wet=0.15, room='tight')
    return _stereo(mono, width=0.3, mode='haas')


def gen_melee_crit(variant=1):
    """Heavier impact — distorted burst + FM metallic ring."""
    dur = 0.25
    n = int(RATE * dur)
    hit = _noise(n, 'white') * _env_perc(n, attack=0.001, decay_frac=1.5)
    hit = _distort(hit, gain=4.0, clip=0.8)
    hit = _bandpass(hit, 150, 4000)
    # FM metallic ring — richer inharmonic spectrum than pure sine
    ring = _fm_osc(1200 + variant * 200, 1800 + variant * 100,
                   mod_index=2.5, dur=dur)
    ring *= _env_perc(n, decay_frac=2.0) * 0.15
    ring = _chorus(ring, voices=2, max_delay_ms=5, depth_ms=2, rate_hz=1.5)
    sub = _sine(50, dur) * _env_perc(n, decay_frac=0.6) * 0.4
    mono = _normalize(_mix(hit * 0.8, ring, sub))
    mono = _reverb(mono, decay=0.2, wet=0.18, room='tight')
    return _stereo(mono, width=0.4, mode='haas')


def gen_ranged_hit(variant=1):
    """Arrow/bolt impact — short whoosh into thunk."""
    dur = 0.18
    n = int(RATE * dur)
    # Whoosh (bandpassed noise sweep)
    whoosh = _noise(n, 'pink') * _env_perc(n, attack=0.005, decay_frac=1.0)
    whoosh = _highpass(whoosh, 800 + variant * 100)
    # Thunk (low impact)
    thunk_dur = 0.06
    thunk_n = int(RATE * thunk_dur)
    thunk = _sine(80, thunk_dur) * _env_perc(thunk_n, decay_frac=0.5) * 0.6
    combined = np.zeros(n)
    combined[:len(whoosh)] += whoosh * 0.5
    offset = int(RATE * 0.08)
    combined[offset:offset + thunk_n] += thunk
    mono = _normalize(combined)
    mono = _reverb(mono, decay=0.15, wet=0.12, room='tight')
    return _stereo(mono, width=0.35, mode='haas')


def gen_miss(variant=1):
    """Quick airy whoosh — filtered noise sweep."""
    dur = 0.2 + variant * 0.03
    n = int(RATE * dur)
    sig = _noise(n, 'pink') * _env_perc(n, attack=0.01, decay_frac=0.7)
    sig = _highpass(sig, 1500 + variant * 200)
    sig = _lowpass(sig, 5000)
    mono = _normalize(sig * 0.6)
    return _stereo(mono, width=0.5, mode='spread')


def gen_dodge(variant=1):
    """Swift dodge — quick frequency sweep up."""
    dur = 0.12
    n = int(RATE * dur)
    sig = _sweep(300, 2000 + variant * 500, dur) * _env_perc(n, decay_frac=0.6)
    noise = _noise(n, 'white') * _env_perc(n, decay_frac=0.4) * 0.15
    sig = _highpass(sig + noise, 400)
    mono = _normalize(sig * 0.5)
    return _stereo(mono, width=0.6, mode='spread')


def gen_block(variant=1):
    """Shield/weapon block — ring-modulated metallic clang + noise."""
    dur = 0.2
    n = int(RATE * dur)
    # Metallic frequencies
    f1 = 800 + variant * 150
    f2 = 1600 + variant * 200
    metal = (_sine(f1, dur) * 0.5 + _sine(f2, dur) * 0.3) * _env_perc(n, decay_frac=1.8)
    # Ring mod adds inharmonic metallic resonance
    metal = _ring_mod(metal, 350 + variant * 40, mix=0.4)
    metal = _chorus(metal, voices=2, max_delay_ms=4, depth_ms=1.5, rate_hz=2.0)
    # Impact noise
    impact = _noise(n, 'white') * _env_perc(n, attack=0.001, decay_frac=0.5)
    impact = _bandpass(impact, 500, 4000) * 0.4
    mono = _normalize(_mix(metal, impact))
    mono = _reverb(mono, decay=0.2, wet=0.18, room='dungeon')
    return _stereo(mono, width=0.35, mode='haas')


def gen_death(variant=1):
    """Death thud — low rumble + collapse with pitch-drop weight."""
    dur = 0.5
    n = int(RATE * dur)
    # Deep thud with pitch-drop for visceral weight
    thud = _pitch_env_osc(40 + variant * 5, dur, env_type='drop', amount=1.5)
    thud *= _env_perc(n, attack=0.005, decay_frac=1.0)
    # Noise collapse
    collapse = _noise(n, 'brown') * _env_perc(n, attack=0.01, decay_frac=1.5)
    collapse = _lowpass(collapse, 600) * 0.5
    # Tonal downer — resonant sweep gives it an eerie closing feel
    downer = _sweep(200, 50, dur) * _env_perc(n, decay_frac=1.2) * 0.2
    downer = _resonant_sweep(downer, 300, 80, q=3.0)
    mono = _normalize(_mix(thud * 0.7, collapse, downer))
    mono = _reverb(mono, decay=0.35, wet=0.22, room='dungeon')
    return _stereo(mono, width=0.3, mode='haas')


def gen_stun_hit(variant=1):
    """Stun impact — ring-modulated dissonant metallic ring + thud."""
    dur = 0.3
    n = int(RATE * dur)
    ring1 = _sine(600 + variant * 50, dur) * _env_perc(n, decay_frac=2.0) * 0.4
    ring2 = _sine(900 + variant * 70, dur) * _env_perc(n, decay_frac=1.8) * 0.3
    rings = _mix(ring1, ring2)
    # Ring mod adds alien dissonance to the bell-like tones
    rings = _ring_mod(rings, 180, mix=0.5)
    rings = _chorus(rings, voices=2, max_delay_ms=6, depth_ms=2, rate_hz=1.0)
    impact = _noise(n, 'white') * _env_perc(n, attack=0.001, decay_frac=0.4)
    impact = _lowpass(impact, 2000) * 0.5
    mono = _normalize(_mix(rings, impact))
    mono = _reverb(mono, decay=0.25, wet=0.2, room='dungeon')
    return _stereo(mono, width=0.4, mode='haas')


def gen_stun_locked():
    """Turn locked by stun — oppressive low warble."""
    dur = 0.4
    n = int(RATE * dur)
    t = _t(dur)
    warble = _sine(120, dur) * (1 + 0.3 * _sine(6, dur))
    warble *= _env_adsr(n, a=0.02, d=0.05, s=0.7, r=0.2)
    warble = _chorus(warble, voices=2, max_delay_ms=10, depth_ms=4, rate_hz=0.8)
    noise = _noise(n, 'brown') * 0.1
    noise = _lowpass(noise, 300)
    mono = _normalize((warble * 0.6 + noise) * 0.8)
    mono = _reverb(mono, decay=0.3, wet=0.2, room='dungeon')
    return _stereo(mono, width=0.3, mode='mid_side')


# ── SKILLS ────────────────────────────────────────────────────

def gen_skill_cast():
    """Generic skill activation — FM arcane ignition with modal chime tail."""
    dur = 0.35
    n = int(RATE * dur)
    # FM ignition burst — carrier sweeps upward through modulation
    fm = _fm_osc(carrier_freq=350, mod_freq=520, mod_index=2.2, dur=dur)
    fm *= _env_perc(n, attack=0.005, decay_frac=1.0)
    fm = _resonant_sweep(fm, 300, 1200, q=3.0)
    # Modal chime — arcane crystalline activation ping
    chime_modes = [(880, 0.5, 0.12), (1320, 0.3, 0.08), (1760, 0.15, 0.05)]
    chime = _modal_synthesis(chime_modes, dur)
    chime *= _env_perc(n, attack=0.001, decay_frac=0.8) * 0.20
    # Sub presence
    sub = _pitch_env_osc(80, 0.1, env_type='drop', amount=1.0)
    sub_n = len(sub)
    combined = np.zeros(n)
    combined[:n] += fm * 0.35
    combined[:n] += chime
    combined[:sub_n] += sub * 0.15
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.20, decay=0.22)
    return _stereo(mono, width=0.4, mode='spread')


def gen_skill_cast_energy():
    """Energy riser — KS sparkle cascade with FM harmonic swell."""
    dur = 0.4
    n = int(RATE * dur)
    # Rising KS sparkles — rapid ascending plucks
    sparkles = np.zeros(n)
    spark_freqs = [800, 1200, 1800, 2600]
    for i, sf in enumerate(spark_freqs):
        sp = _karplus_strong(sf, 0.12, brightness=0.9, damping=0.5, pluck_position=0.2)
        offset = int(RATE * (i * 0.06))
        sp_n = len(sp)
        end = min(offset + sp_n, n)
        sparkles[offset:end] += sp[:end - offset] * 0.15
    # FM harmonic swell underneath
    swell = _fm_osc(carrier_freq=440, mod_freq=660, mod_index=1.5, dur=dur)
    swell *= _env_adsr(n, a=0.05, d=0.08, s=0.5, r=0.15)
    swell = _formant(swell, vowel='e', intensity=0.3)
    combined = np.zeros(n)
    combined[:n] += sparkles
    combined[:n] += swell * 0.22
    mono = _normalize(combined)
    mono = _chorus(mono, voices=3, max_delay_ms=6, depth_ms=2.5, rate_hz=1.5)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.22, decay=0.25)
    return _stereo(mono, width=0.5, mode='spread')


def gen_skill_cast_dark():
    """Hollow dark spell — FM dark mass with formant whisper and crypt reverb."""
    dur = 0.45
    n = int(RATE * dur)
    # FM dark mass — low, heavy, unstable
    mass = _fm_osc(carrier_freq=65, mod_freq=45, mod_index=3.5, dur=dur)
    mass *= _env_adsr(n, a=0.06, d=0.1, s=0.5, r=0.2)
    mass = _lowpass(mass, 350)
    mass = _ring_mod(mass, mod_freq=22, mix=0.25)  # subtle otherworldly modulation
    # Spectral breath — formant 'u' whisper
    breath = _noise(n, 'brown') * _env_adsr(n, a=0.08, d=0.08, s=0.35, r=0.18)
    breath = _formant(breath, vowel='u', intensity=0.55) * 0.20
    breath = _bandpass(breath, 100, 800)
    # Modal dark clang — single foreboding hit
    clang_modes = [(90, 0.6, 0.20), (173, 0.3, 0.12), (290, 0.15, 0.06)]
    clang = _modal_synthesis(clang_modes, dur)
    clang *= _env_perc(n, attack=0.003, decay_frac=1.2) * 0.15
    combined = np.zeros(n)
    combined[:n] += mass * 0.35
    combined[:n] += breath
    combined[:n] += clang
    mono = _normalize(combined)
    mono = _tremolo(mono, rate=2.0, depth=0.25, shape='triangle')
    mono = _conv_reverb(mono, room='crypt', wet=0.30, decay=0.38)
    return _stereo(mono, width=0.38, mode='mid_side')


def gen_skill_cast_power():
    """Powerful energy blast — FM detonation with pitch-drop impact."""
    dur = 0.35
    n = int(RATE * dur)
    # FM detonation — harsh carrier+modulator for explosive aggression
    blast = _fm_osc(carrier_freq=200, mod_freq=300, mod_index=5.0, dur=0.12)
    blast_n = len(blast)
    blast *= _env_perc(blast_n, attack=0.001, decay_frac=0.4)
    blast = _distort(blast, gain=2.5, clip=0.65)
    # Pitch-drop sub impact — visceral weight
    sub = _pitch_env_osc(45, 0.2, env_type='drop', amount=2.5, waveform='sine')
    sub_n = len(sub)
    sub *= _env_perc(sub_n, attack=0.002, decay_frac=0.6)
    # Modal ring tail — power resonance
    ring_modes = [(400, 0.4, 0.10), (650, 0.2, 0.06)]
    ring = _modal_synthesis(ring_modes, dur)
    ring *= _env_perc(n, attack=0.002, decay_frac=1.2) * 0.18
    # Noise transient
    hit_n = int(RATE * 0.02)
    hit = _noise(hit_n, 'white') * _env_perc(hit_n, attack=0.001, decay_frac=0.2) * 0.4
    hit = _bandpass(hit, 400, 5000)
    combined = np.zeros(n)
    combined[:blast_n] += blast * 0.40
    combined[:sub_n] += sub * 0.28
    combined[:n] += ring
    combined[:hit_n] += hit
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='metal_room', wet=0.18, decay=0.18)
    return _stereo(mono, width=0.38, mode='haas')


def gen_skill_cast_sphere():
    """Sphere rising — KS crystalline orb formation with FM overtone."""
    dur = 0.3
    n = int(RATE * dur)
    # KS orb core — clean, glassy pluck
    orb = _karplus_strong(660, dur, brightness=0.85, damping=0.4,
                          pluck_position=0.25, body_size=0.15)
    orb *= _env_adsr(n, a=0.01, d=0.05, s=0.7, r=0.1) * 0.40
    # FM rising overtone — clean, shimmering
    overtone = _fm_osc(carrier_freq=880, mod_freq=880, mod_index=0.8, dur=dur)
    overtone *= _env_adsr(n, a=0.03, d=0.05, s=0.5, r=0.08) * 0.18
    # High bell ping — sphere solidifying
    bell = _modal_synthesis([(1760, 0.3, 0.08), (2640, 0.15, 0.04)], dur)
    bell *= _env_perc(n, attack=0.001, decay_frac=0.6) * 0.10
    combined = np.zeros(n)
    combined[:n] += orb
    combined[:n] += overtone
    combined[:n] += bell
    mono = _normalize(combined)
    mono = _chorus(mono, voices=2, max_delay_ms=5, depth_ms=2, rate_hz=1.5)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.20, decay=0.18)
    return _stereo(mono, width=0.45, mode='spread')


def gen_heal():
    """Healing light — crystalline Karplus-Strong harp tones cascading
    through cathedral reverb. Warm, layered, magical."""
    dur = 0.6
    n = int(RATE * dur)
    # Cascading KS harp tones — C5, E5, G5  (major triad, bright)
    notes = [(523, 0.0), (659, 0.06), (784, 0.12)]
    combined = np.zeros(n)
    for freq, delay in notes:
        s = _karplus_strong(freq, dur - delay,
                            brightness=0.7, damping=0.25,
                            pluck_position=0.35, body_size=0.3)
        offset = int(delay * RATE)
        end = min(n, offset + len(s))
        combined[offset:end] += s[:end - offset] * 0.4
    # Gentle bell shimmer on top — modal overtones
    bell_modes = [(1568, 0.3, 0.15), (2349, 0.15, 0.08)]
    bell = _modal_synthesis(bell_modes, dur) * _env_perc(n, decay_frac=1.2) * 0.12
    combined[:len(bell)] += bell
    mono = _normalize(combined)
    mono = _chorus(mono, voices=3, max_delay_ms=9, depth_ms=3.5, rate_hz=0.6)
    mono = _conv_reverb(mono, room='cathedral', wet=0.3, decay=0.4)
    return _stereo(mono, width=0.55, mode='spread')


def gen_heal_alt():
    """Healing breath — breathy formant whisper layered with KS strings
    and crypt reverb for a ghostly, nurturing feel."""
    dur = 0.7
    n = int(RATE * dur)
    # Breathy formant layer — 'o' vowel for warmth
    breath = _noise(n, 'pink') * _env_adsr(n, a=0.1, d=0.1, s=0.3, r=0.3)
    breath = _formant(breath, vowel='o', intensity=0.6) * 0.3
    # KS string bed — two warm plucked strings
    s1 = _karplus_strong(440, dur, brightness=0.5, damping=0.3,
                         pluck_position=0.4, body_size=0.5)
    s2 = _karplus_strong(660, dur, brightness=0.45, damping=0.3,
                         pluck_position=0.45, body_size=0.4)
    strings = (s1 * 0.3 + s2 * 0.2) * _env_adsr(n, a=0.08, d=0.1, s=0.4, r=0.3)
    mono = _normalize(_mix(breath, strings))
    mono = _chorus(mono, voices=3, max_delay_ms=12, depth_ms=4, rate_hz=0.5)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.28, decay=0.35)
    return _stereo(mono, width=0.5, mode='spread')


def gen_buff_apply():
    """Buff apply — resonant modal chime with ascending KS pluck.
    Clear "something activated" feeling."""
    dur = 0.4
    n = int(RATE * dur)
    # Quick ascending KS pluck (like a magic string being struck)
    pluck = _karplus_strong(880, dur, brightness=0.8, damping=0.4,
                            pluck_position=0.3, body_size=0.2)
    pluck *= _env_perc(n, attack=0.002, decay_frac=1.0) * 0.5
    # Modal chime resonance — bright, clear
    chime_modes = [
        (1047, 1.0, 0.12),   # C6
        (1568, 0.6, 0.08),   # G6
        (2093, 0.3, 0.05),   # C7
    ]
    chime = _modal_synthesis(chime_modes, dur)
    chime *= _env_perc(n, attack=0.001, decay_frac=1.5) * 0.25
    mono = _normalize(_mix(pluck, chime))
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.2, decay=0.25)
    return _stereo(mono, width=0.45, mode='spread')


def gen_buff_shimmer():
    """Buff shimmer — sparkling metallic body resonance with KS harmonics.
    Continuous sparkle texture."""
    dur = 0.5
    n = int(RATE * dur)
    # Modal "glass wind-chime" cluster — high, bright, inharmonic
    modes = [
        (2200, 1.0, 0.18),
        (3350, 0.7, 0.12),
        (4700, 0.4, 0.07),
        (6300, 0.15, 0.04),
    ]
    shimmer = _modal_synthesis(modes, dur)
    shimmer *= _env_adsr(n, a=0.02, d=0.08, s=0.35, r=0.2) * 0.4
    # Tiny KS plucks — staggered twinkle
    twinkle = np.zeros(n)
    for freq, delay in [(3500, 0.0), (4200, 0.08), (3800, 0.16), (4500, 0.24)]:
        s = _karplus_strong(freq, 0.15, brightness=0.9, damping=0.6,
                            pluck_position=0.2, body_size=0.0)
        off = int(delay * RATE)
        end = min(n, off + len(s))
        twinkle[off:end] += s[:end - off] * 0.12
    mono = _normalize(_mix(shimmer, twinkle))
    mono = _chorus(mono, voices=3, max_delay_ms=8, depth_ms=3, rate_hz=1.0)
    mono = _conv_reverb(mono, room='cathedral', wet=0.25, decay=0.3)
    return _stereo(mono, width=0.6, mode='spread')


def gen_buff_stats():
    """Stats-up — ascending power arpeggio using KS plucked strings.
    Quick, punchy, heroic."""
    dur = 0.35
    n = int(RATE * dur)
    # Ascending KS arpeggio: C5 → E5 → G5 → C6 (fast heroic run)
    notes = [(523, 0.0), (659, 0.06), (784, 0.12), (1047, 0.18)]
    combined = np.zeros(n)
    for freq, delay in notes:
        s = _karplus_strong(freq, dur - delay,
                            brightness=0.75, damping=0.45,
                            pluck_position=0.3, body_size=0.15)
        offset = int(delay * RATE)
        end = min(n, offset + len(s))
        combined[offset:end] += s[:end - offset] * 0.4
    # Top it off with a tiny bright modal ping
    ping_modes = [(2093, 0.5, 0.04), (3136, 0.2, 0.02)]
    ping = _modal_synthesis(ping_modes, 0.15) * 0.15
    p_off = int(0.2 * RATE)
    p_end = min(n, p_off + len(ping))
    combined[p_off:p_end] += ping[:p_end - p_off]
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.18, decay=0.2)
    return _stereo(mono, width=0.45, mode='spread')


def gen_buff_vigor():
    """Invigoration — energizing metallic body burst with KS snap.
    Feels like adrenaline hitting."""
    dur = 0.35
    n = int(RATE * dur)
    # Metallic "energy charge" body — bright modes, fast attack
    modes = [
        (600, 1.0, 0.10),
        (1440, 0.6, 0.06),
        (2800, 0.3, 0.04),
    ]
    body = _modal_synthesis(modes, dur)
    body *= _env_perc(n, attack=0.002, decay_frac=1.2) * 0.4
    # Taut KS snap — high tension string
    snap = _karplus_strong(1200, 0.15, brightness=0.9, damping=0.55,
                           pluck_position=0.15, body_size=0.0)
    snap *= 0.3
    # Sub power thump
    sub = _sine(80, 0.12) * _env_perc(int(RATE * 0.12), decay_frac=0.3) * 0.3
    combined = np.zeros(n)
    combined[:len(body)] += body
    combined[:len(snap)] += snap
    combined[:len(sub)] += sub
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='metal_room', wet=0.18, decay=0.2)
    return _stereo(mono, width=0.4, mode='haas')


def gen_regen():
    """Regen tick — warm KS pluck with gentle modal resonance.
    Soft, comforting, repeatable."""
    dur = 0.3
    n = int(RATE * dur)
    # Warm plucked tone — muted, like a soft guitar harmonic
    pluck = _karplus_strong(440, dur, brightness=0.45, damping=0.3,
                            pluck_position=0.5, body_size=0.5)
    pluck *= _env_perc(n, decay_frac=0.9) * 0.5
    # Gentle Bell overtone
    bell = _modal_synthesis([(880, 0.4, 0.08), (1320, 0.15, 0.04)], dur)
    bell *= _env_perc(n, decay_frac=0.6) * 0.12
    mono = _normalize(_mix(pluck, bell))
    mono = _chorus(mono, voices=2, max_delay_ms=6, depth_ms=2, rate_hz=0.8)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.2, decay=0.2)
    return _stereo(mono, width=0.35, mode='spread')


def gen_debuff_enemy():
    """Enemy debuff — dark modal clang with descending KS growl.
    Menacing, heavy, wrong-sounding."""
    dur = 0.4
    n = int(RATE * dur)
    # Dark descending KS string — low, detuned, ominous
    growl = _karplus_strong(150, dur, brightness=0.3, damping=0.2,
                            pluck_position=0.6, body_size=0.7)
    growl *= _env_adsr(n, a=0.02, d=0.08, s=0.5, r=0.15) * 0.5
    # Inharmonic dark metal body — "cursed" sound
    curse_modes = [
        (185, 1.0, 0.15),
        (437, 0.6, 0.10),
        (823, 0.3, 0.06),
    ]
    curse = _modal_synthesis(curse_modes, dur)
    curse *= _env_perc(n, attack=0.005, decay_frac=1.5) * 0.3
    # Nasty distortion
    combined = _mix(growl, curse)
    combined = _distort(combined, gain=1.8, clip=0.5)
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='crypt', wet=0.25, decay=0.3)
    return _stereo(mono, width=0.4, mode='mid_side')


def gen_debuff_speed():
    """Speed debuff — heavy dragging modal resonance with detuned strings.
    Sluggish, tar-like, oppressive."""
    dur = 0.35
    n = int(RATE * dur)
    # Very low, slow KS strings — feels like being dragged
    drag1 = _karplus_strong(100, dur, brightness=0.25, damping=0.15,
                            pluck_position=0.6, body_size=0.8)
    drag2 = _karplus_strong(103, dur, brightness=0.25, damping=0.15,
                            pluck_position=0.55, body_size=0.8)
    drag = (drag1 + drag2) * _env_adsr(n, a=0.03, d=0.05, s=0.45, r=0.15) * 0.35
    # Dark modal hum — rattling chains
    chain_modes = [
        (120, 1.0, 0.12),
        (280, 0.5, 0.08),
        (510, 0.2, 0.05),
    ]
    chains = _modal_synthesis(chain_modes, dur)
    chains *= _env_perc(n, decay_frac=1.0) * 0.25
    mono = _normalize(_mix(drag, chains))
    mono = _chorus(mono, voices=2, max_delay_ms=12, depth_ms=5, rate_hz=0.4)
    mono = _conv_reverb(mono, room='crypt', wet=0.22, decay=0.25)
    return _stereo(mono, width=0.3, mode='mid_side')


# ── CRUSADER ──────────────────────────────────────────────────

def gen_taunt():
    """Taunt — formant-filtered aggressive growl + metallic ring."""
    dur = 0.4
    n = int(RATE * dur)
    growl = _saw(100, dur) * _env_adsr(n, a=0.03, d=0.08, s=0.5, r=0.15)
    growl = _lowpass(growl, 500) * 0.5
    # Formant 'a' gives it a throaty, vocal growl character
    growl = _formant(growl, vowel='a', intensity=0.6)
    growl = _chorus(growl, voices=2, max_delay_ms=8, depth_ms=3, rate_hz=0.9)
    ring = _sine(800, dur) * _env_perc(n, decay_frac=1.5) * 0.2
    mono = _normalize(growl + ring)
    mono = _reverb(mono, decay=0.3, wet=0.22, room='dungeon')
    return _stereo(mono, width=0.35, mode='haas')


def gen_shield_bash():
    """Shield bash — heavy metallic slam."""
    dur = 0.2
    n = int(RATE * dur)
    slam = _noise(n, 'white') * _env_perc(n, attack=0.001, decay_frac=0.8)
    slam = _bandpass(slam, 300, 2500) * 0.6
    metal = _sine(900, dur) * _env_perc(n, decay_frac=1.5) * 0.3
    metal = _chorus(metal, voices=2, max_delay_ms=4, depth_ms=1.5, rate_hz=2.0)
    sub = _sine(70, dur) * _env_perc(n, decay_frac=0.4) * 0.4
    mono = _normalize(_mix(slam, metal, sub))
    mono = _reverb(mono, decay=0.18, wet=0.15, room='tight')
    return _stereo(mono, width=0.3, mode='haas')


def gen_holy_ground():
    """Holy ground — KS harp chord with cathedral reverb and ethereal FM shimmer."""
    dur = 0.6
    n = int(RATE * dur)
    # KS harp chord — warm, heavenly major triad strum
    harp = np.zeros(n)
    chord_notes = [(523, 0.0), (659, 0.04), (784, 0.08)]  # C5 E5 G5
    for freq, delay in chord_notes:
        s = _karplus_strong(freq, dur - delay, brightness=0.65, damping=0.2,
                            pluck_position=0.40, body_size=0.35)
        offset = int(delay * RATE)
        end = min(n, offset + len(s))
        harp[offset:end] += s[:end - offset] * 0.28
    # FM ethereal shimmer — high, bell-like celestial atmosphere
    shimmer = _fm_osc(carrier_freq=1200, mod_freq=1800, mod_index=0.6, dur=dur)
    shimmer *= _env_fade_in(n, 0.2) * _env_adsr(n, a=0.15, d=0.1, s=0.4, r=0.2)
    shimmer = _tremolo(shimmer, rate=3.5, depth=0.3, shape='sine')
    # Gentle formant breath — holy whisper
    breath = _noise(n, 'pink') * _env_adsr(n, a=0.12, d=0.08, s=0.2, r=0.25)
    breath = _formant(breath, vowel='a', intensity=0.4) * 0.08
    breath = _highpass(breath, 600)
    combined = np.zeros(n)
    combined[:n] += harp
    combined[:n] += shimmer * 0.12
    combined[:n] += breath
    mono = _normalize(combined)
    mono = _chorus(mono, voices=3, max_delay_ms=10, depth_ms=4, rate_hz=0.6)
    mono = _conv_reverb(mono, room='cathedral', wet=0.35, decay=0.40)
    return _stereo(mono, width=0.6, mode='spread')


def gen_bulwark():
    """Bulwark — heavy modal shield wall erection with FM force pulse."""
    dur = 0.35
    n = int(RATE * dur)
    # Modal shield wall — heavy metallic barrier slamming into place
    wall_modes = [
        (160, 0.7, 0.15),  # deep resonant body
        (380, 0.4, 0.10),  # mid structure
        (620, 0.25, 0.06), # bright edge
        (950, 0.12, 0.03), # high ring
    ]
    wall = _modal_synthesis(wall_modes, dur)
    wall *= _env_perc(n, attack=0.002, decay_frac=1.3)
    # FM force pulse — magical energy pushing outward
    pulse = _fm_osc(carrier_freq=250, mod_freq=380, mod_index=2.0, dur=0.15)
    pulse_n = len(pulse)
    pulse *= _env_perc(pulse_n, attack=0.003, decay_frac=0.6)
    # Noise slam transient
    slam_n = int(RATE * 0.02)
    slam = _noise(slam_n, 'white') * _env_perc(slam_n, attack=0.001, decay_frac=0.2) * 0.4
    slam = _lowpass(slam, 3000)
    combined = np.zeros(n)
    combined[:n] += wall * 0.30
    combined[:pulse_n] += pulse * 0.25
    combined[:slam_n] += slam
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.20, decay=0.22)
    return _stereo(mono, width=0.35, mode='haas')


# ── RANGER ────────────────────────────────────────────────────

def gen_power_shot():
    """Power shot — KS bowstring snap with FM arrow whistle and impact thud."""
    dur = 0.25
    n = int(RATE * dur)
    # KS bowstring snap — tight, bright pluck
    bowstring = _karplus_strong(350, 0.08, brightness=0.9, damping=0.7,
                                pluck_position=0.1, body_size=0.05)
    bow_n = len(bowstring)
    # FM arrow whistle — high frequency doppler effect
    whistle = _fm_osc(carrier_freq=1800, mod_freq=2400, mod_index=0.5, dur=0.12)
    whistle_n = len(whistle)
    whistle *= _env_perc(whistle_n, attack=0.002, decay_frac=0.5)
    whistle = _highpass(whistle, 1200)
    # Noise whoosh — arrow flight
    whoosh_n = int(RATE * 0.10)
    whoosh = _noise(whoosh_n, 'pink') * _env_perc(whoosh_n, attack=0.005, decay_frac=0.6)
    whoosh = _bandpass(whoosh, 1500, 5000) * 0.20
    # Impact thud at arrival
    thud = _pitch_env_osc(100, 0.04, env_type='drop', amount=1.5)
    thud_n = len(thud)
    thud *= _env_perc(thud_n, attack=0.001, decay_frac=0.3) * 0.22
    combined = np.zeros(n)
    combined[:bow_n] += bowstring * 0.25
    combined[int(RATE*0.03):int(RATE*0.03)+whistle_n] += whistle * 0.18
    combined[int(RATE*0.02):int(RATE*0.02)+whoosh_n] += whoosh
    combined[int(RATE*0.15):int(RATE*0.15)+thud_n] += thud
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.14, decay=0.12)
    return _stereo(mono, width=0.45, mode='haas')


def gen_volley():
    """Volley — rapid KS bowstring snaps with staggered FM arrow whistles."""
    dur = 0.4
    n = int(RATE * dur)
    combined = np.zeros(n)
    for i in range(4):
        offset = int(RATE * (i * 0.08))
        # KS snap per arrow
        snap = _karplus_strong(300 + i * 80, 0.06, brightness=0.85, damping=0.75,
                               pluck_position=0.12)
        snap_n = len(snap)
        end = min(offset + snap_n, n)
        combined[offset:end] += snap[:end - offset] * 0.15
        # FM whistle per arrow (rising pitch variation)
        wh = _fm_osc(carrier_freq=1600 + i * 200, mod_freq=2200, mod_index=0.4, dur=0.05)
        wh_n = len(wh)
        wh *= _env_perc(wh_n, attack=0.001, decay_frac=0.4)
        wh_offset = offset + int(RATE * 0.02)
        wh_end = min(wh_offset + wh_n, n)
        combined[wh_offset:wh_end] += wh[:wh_end - wh_offset] * 0.10
    # Overall whoosh envelope
    whoosh = _noise(n, 'pink') * _env_adsr(n, a=0.02, d=0.05, s=0.3, r=0.15)
    whoosh = _bandpass(whoosh, 2000, 6000) * 0.08
    combined[:n] += whoosh
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.15, decay=0.12)
    return _stereo(mono, width=0.55, mode='spread')


def gen_evasion():
    """Evasion buff — fast KS shimmer burst with airy FM doppler."""
    dur = 0.22
    n = int(RATE * dur)
    # KS shimmer burst — quick bright pluck like wind passing
    shimmer = _karplus_strong(2000, 0.12, brightness=0.95, damping=0.6,
                              pluck_position=0.1)
    shim_n = min(len(shimmer), n)
    # FM doppler — something whooshing past
    doppler = _fm_osc(carrier_freq=600, mod_freq=900, mod_index=0.8, dur=dur)
    doppler *= _env_perc(n, attack=0.005, decay_frac=0.5)
    doppler = _highpass(doppler, 400)
    # Airy noise trail
    air = _noise(n, 'pink') * _env_perc(n, attack=0.008, decay_frac=0.3)
    air = _highpass(air, 3000) * 0.10
    combined = np.zeros(n)
    combined[:shim_n] += shimmer[:shim_n] * 0.22
    combined[:n] += doppler * 0.25
    combined[:n] += air
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.10, decay=0.10)
    return _stereo(mono, width=0.55, mode='spread')


def gen_crippling_shot():
    """Crippling shot — KS impact ping + FM descending debuff warble."""
    dur = 0.3
    n = int(RATE * dur)
    # KS impact — sharp metallic arrowhead hitting
    impact = _karplus_strong(600, 0.08, brightness=0.85, damping=0.6,
                             pluck_position=0.15)
    imp_n = len(impact)
    # FM descending debuff — crippling warble that sounds painful
    debuff = _fm_osc(carrier_freq=400, mod_freq=550, mod_index=2.5, dur=0.2)
    debuff_n = len(debuff)
    debuff *= _env_perc(debuff_n, attack=0.005, decay_frac=1.0)
    # Apply a pitch-drop feel via formant shift
    debuff = _formant(debuff, vowel='u', intensity=0.4)
    debuff = _ring_mod(debuff, mod_freq=120, mix=0.3)
    # Noise transient
    crack_n = int(RATE * 0.01)
    crack = _noise(crack_n, 'white') * np.linspace(1, 0, crack_n) * 0.5
    combined = np.zeros(n)
    combined[:crack_n] += crack
    combined[:imp_n] += impact * 0.25
    combined[int(RATE*0.04):int(RATE*0.04)+debuff_n] += debuff * 0.28
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.18, decay=0.18)
    return _stereo(mono, width=0.38, mode='haas')


# ── CONFESSOR ─────────────────────────────────────────────────

def gen_skill_heal():
    """Confessor heal — warm tonal chime + sparkle."""
    dur = 0.5
    n = int(RATE * dur)
    tone = _sine(660, dur) * _env_adsr(n, a=0.04, d=0.08, s=0.5, r=0.25)
    tone = _chorus(tone, voices=3, max_delay_ms=8, depth_ms=3, rate_hz=0.8)
    sparkle = _sine(1320, dur) * _env_perc(n, decay_frac=1.5) * 0.15
    mono = _normalize(tone * 0.5 + sparkle)
    mono = _reverb(mono, decay=0.35, wet=0.25, room='hall')
    return _stereo(mono, width=0.5, mode='spread')


def gen_rebuke():
    """Rebuke — FM divine lightning zap with modal crack and ring mod."""
    dur = 0.25
    n = int(RATE * dur)
    # FM divine zap — fast rising carrier
    zap = _fm_osc(carrier_freq=600, mod_freq=1200, mod_index=3.5, dur=0.12)
    zap_n = len(zap)
    zap *= _env_perc(zap_n, attack=0.001, decay_frac=0.5)
    zap = _ring_mod(zap, mod_freq=400, mix=0.35)
    # Modal crack — sharp metallic divine impact
    crack_modes = [(2200, 1.0, 0.02), (3500, 0.5, 0.015), (5000, 0.2, 0.01)]
    crack = _modal_synthesis(crack_modes, 0.08)
    crack_n = len(crack)
    crack *= _env_perc(crack_n, attack=0.001, decay_frac=0.3) * 0.30
    # Noise transient
    trans_n = int(RATE * 0.008)
    trans = _noise(trans_n, 'white') * np.linspace(1, 0, trans_n) * 0.4
    combined = np.zeros(n)
    combined[:trans_n] += trans
    combined[:zap_n] += zap * 0.30
    combined[:crack_n] += crack
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.15, decay=0.12)
    return _stereo(mono, width=0.35, mode='haas')


def gen_exorcism():
    """Exorcism — dissonant FM blast with modal shattering and dark formant."""
    dur = 0.35
    n = int(RATE * dur)
    # FM dissonant blast — tritone-based carrier/mod for unsettling feel
    blast = _fm_osc(carrier_freq=400, mod_freq=567, mod_index=4.0, dur=dur)
    blast *= _env_perc(n, attack=0.005, decay_frac=1.0) * 0.30
    blast = _ring_mod(blast, mod_freq=233, mix=0.4)
    # Modal shattering — inharmonic piercing modes
    shatter_modes = [
        (567, 1.0, 0.06),   # Tritone
        (1134, 0.5, 0.04),  # Double tritone
        (1800, 0.25, 0.02), # High dissonant
    ]
    shatter = _modal_synthesis(shatter_modes, dur)
    shatter *= _env_perc(n, attack=0.003, decay_frac=0.7) * 0.20
    # Dark formant — demonic presence
    dark = _fm_osc(carrier_freq=120, mod_freq=180, mod_index=2.0, dur=dur)
    dark = _formant(dark, vowel='u', intensity=0.5)
    dark *= _env_adsr(n, a=0.02, d=0.06, s=0.3, r=0.12) * 0.18
    # Noise burst for exorcism violence
    burst_n = int(RATE * 0.03)
    burst = _noise(burst_n, 'white') * np.linspace(1, 0, burst_n) * 0.35
    combined = np.zeros(n)
    combined[:burst_n] += burst
    combined[:n] += blast + shatter + dark
    mono = _normalize(combined)
    mono = _chorus(mono, voices=2, max_delay_ms=7, depth_ms=3, rate_hz=1.5)
    mono = _conv_reverb(mono, room='crypt', wet=0.25, decay=0.25)
    return _stereo(mono, width=0.45, mode='spread')


def gen_prayer():
    """Prayer — layered KS chanting with formant choir and FM ethereal drone."""
    dur = 0.5
    n = int(RATE * dur)
    # KS chanting voices — stacked fifths for choral warmth
    voice1 = _karplus_strong(220, dur, brightness=0.3, damping=0.2,
                             pluck_position=0.5, body_size=0.7)
    voice2 = _karplus_strong(330, dur, brightness=0.28, damping=0.22,
                             pluck_position=0.45, body_size=0.65)
    voices = (voice1 * 0.20 + voice2 * 0.15) * _env_adsr(n, a=0.08, d=0.1, s=0.4, r=0.25)
    # Formant choir with slow vibrato
    choir = _fm_osc(carrier_freq=165, mod_freq=5, mod_index=0.08, dur=dur)
    choir = _formant(choir, vowel='a', intensity=0.6)
    choir *= _env_adsr(n, a=0.1, d=0.1, s=0.35, r=0.2) * 0.20
    # FM ethereal drone — subtle heavenly wash
    ethereal = _fm_osc(carrier_freq=440, mod_freq=660, mod_index=0.5, dur=dur)
    ethereal *= _env_adsr(n, a=0.12, d=0.1, s=0.2, r=0.2) * 0.10
    ethereal = _tremolo(ethereal, rate=2.5, depth=0.25, shape='sine')
    mono = _normalize(voices + choir + ethereal)
    mono = _chorus(mono, voices=3, max_delay_ms=12, depth_ms=5, rate_hz=0.5)
    mono = _conv_reverb(mono, room='cathedral', wet=0.35, decay=0.40)
    return _stereo(mono, width=0.5, mode='spread')


def gen_shield_of_faith():
    """Shield of Faith — modal protective dome with KS chime cascade and FM shimmer."""
    dur = 0.5
    n = int(RATE * dur)
    # Modal protective dome — broad resonant body
    dome_modes = [
        (400, 1.0, 0.12),  # Warm body
        (800, 0.5, 0.08),  # Octave
        (1200, 0.3, 0.05), # Fifth above octave
    ]
    dome = _modal_synthesis(dome_modes, dur)
    dome *= _env_adsr(n, a=0.04, d=0.08, s=0.4, r=0.2) * 0.25
    # KS chime cascade — protective shimmer
    chimes = np.zeros(n)
    for i, freq in enumerate([880, 1100, 1320]):
        offset = int(RATE * (i * 0.06))
        ch = _karplus_strong(freq, 0.2, brightness=0.7, damping=0.5,
                             pluck_position=0.2, body_size=0.3)
        ch_n = len(ch)
        end = min(offset + ch_n, n)
        chimes[offset:end] += ch[:end - offset] * 0.12
    # FM ethereal shimmer
    shimmer = _fm_osc(carrier_freq=1200, mod_freq=1800, mod_index=0.3, dur=dur)
    shimmer *= _env_adsr(n, a=0.05, d=0.1, s=0.25, r=0.2) * 0.10
    shimmer = _tremolo(shimmer, rate=3.0, depth=0.3, shape='sine')
    mono = _normalize(dome + chimes + shimmer)
    mono = _chorus(mono, voices=3, max_delay_ms=8, depth_ms=3, rate_hz=0.8)
    mono = _conv_reverb(mono, room='cathedral', wet=0.28, decay=0.30)
    return _stereo(mono, width=0.5, mode='spread')


def gen_divine_sense():
    """Divine sense — FM scanning pulse with modal crystalline ping and KS spirit echo."""
    dur = 0.4
    n = int(RATE * dur)
    # FM scanning pulse — expanding outward wave
    scan = _fm_osc(carrier_freq=600, mod_freq=800, mod_index=1.2, dur=dur)
    scan *= _env_adsr(n, a=0.02, d=0.08, s=0.3, r=0.2) * 0.22
    scan = _tremolo(scan, rate=6.0, depth=0.4, shape='sine')
    # Modal crystalline ping — divine detection chime
    ping_modes = [(1200, 1.0, 0.08), (1800, 0.5, 0.05), (2400, 0.25, 0.03)]
    ping = _modal_synthesis(ping_modes, dur)
    ping *= _env_perc(n, attack=0.005, decay_frac=0.6) * 0.18
    # KS spirit echo — ethereal trailing response
    echo = _karplus_strong(900, dur, brightness=0.5, damping=0.4,
                           pluck_position=0.3, body_size=0.4)
    echo *= _env_perc(n, attack=0.05, decay_frac=1.0) * 0.12
    mono = _normalize(scan + ping + echo)
    mono = _delay(mono, delay_ms=80, feedback=0.3, wet=0.25)
    mono = _conv_reverb(mono, room='cathedral', wet=0.25, decay=0.30)
    return _stereo(mono, width=0.5, mode='spread')


# ── HEXBLADE ──────────────────────────────────────────────────

def gen_shadow_step():
    """Shadow step — dark FM void collapse with KS shadow whisper and pitch-drop sub."""
    dur = 0.25
    n = int(RATE * dur)
    # FM void collapse — dark descending swirl
    void = _fm_osc(carrier_freq=500, mod_freq=700, mod_index=3.0, dur=dur)
    void *= _env_perc(n, attack=0.002, decay_frac=0.7) * 0.25
    void = _ring_mod(void, mod_freq=180, mix=0.35)
    # KS shadow whisper — dark, muffled
    whisper = _karplus_strong(150, dur, brightness=0.15, damping=0.12,
                              pluck_position=0.7, body_size=0.8)
    whisper *= _env_perc(n, attack=0.01, decay_frac=0.5) * 0.18
    # Pitch-drop sub — teleport displacement
    sub = _pitch_env_osc(80, 0.08, env_type='drop', amount=2.0)
    sub_n = len(sub)
    sub *= _env_perc(sub_n, attack=0.001, decay_frac=0.3) * 0.22
    # Dark noise smear
    smear = _noise(n, 'brown') * _env_perc(n, decay_frac=0.4) * 0.10
    smear = _lowpass(smear, 400)
    combined = np.zeros(n)
    combined[:n] += void + whisper + smear
    combined[:sub_n] += sub
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='crypt', wet=0.22, decay=0.20)
    return _stereo(mono, width=0.5, mode='spread')


def gen_wither():
    """Wither — cursed corroding metal with spectral decay.
    Dark modal body crumbling through crypt reverb."""
    dur = 0.45
    n = int(RATE * dur)
    # Corroding metal — inharmonic, ugly, dissonant modes
    rust_modes = [
        (173, 1.0, 0.18),   # Deep rumble
        (411, 0.7, 0.12),   # Dissonant
        (777, 0.4, 0.07),   # Gritty mid
        (1230, 0.15, 0.04), # Harsh upper
    ]
    body = _modal_synthesis(rust_modes, dur)
    body *= _env_adsr(n, a=0.03, d=0.08, s=0.45, r=0.15) * 0.4
    # Descending KS moan — low, dark
    moan = _karplus_strong(180, dur, brightness=0.2, damping=0.15,
                           pluck_position=0.7, body_size=0.8)
    moan *= _env_adsr(n, a=0.05, d=0.1, s=0.4, r=0.15) * 0.3
    combined = _mix(body, moan)
    combined = _distort(combined, gain=1.6, clip=0.5)
    mono = _normalize(combined)
    mono = _chorus(mono, voices=2, max_delay_ms=10, depth_ms=4, rate_hz=0.6)
    mono = _conv_reverb(mono, room='crypt', wet=0.28, decay=0.3)
    return _stereo(mono, width=0.4, mode='mid_side')


def gen_wither_tick():
    """Wither DoT tick — quick dark metallic ping with crypt tail.
    Subtle but sinister."""
    dur = 0.15
    n = int(RATE * dur)
    # Dark modal ping — single inharmonic strike
    modes = [(200, 1.0, 0.05), (467, 0.4, 0.03)]
    ping = _modal_synthesis(modes, dur)
    ping *= _env_perc(n, attack=0.001, decay_frac=0.5) * 0.35
    # Touch of distortion for grit
    ping = _distort(ping, gain=1.3, clip=0.45)
    mono = _normalize(ping)
    mono = _conv_reverb(mono, room='crypt', wet=0.15, decay=0.12)
    return _stereo(mono, width=0.2, mode='haas')


def gen_ward():
    """Ward — modal force shield bubble with KS crystalline edge and FM hum."""
    dur = 0.3
    n = int(RATE * dur)
    # Modal force bubble — resonant protective shell
    bubble_modes = [
        (500, 1.0, 0.10),  # Core resonance
        (1100, 0.5, 0.06), # Bright overtone
        (1700, 0.2, 0.03), # Shimmer
    ]
    bubble = _modal_synthesis(bubble_modes, dur)
    bubble *= _env_adsr(n, a=0.02, d=0.05, s=0.5, r=0.15) * 0.30
    # KS crystalline edge — sharp shield activation
    edge = _karplus_strong(1500, 0.1, brightness=0.8, damping=0.6,
                           pluck_position=0.15, body_size=0.2)
    edge_n = len(edge)
    # FM low hum — sustained wardfield
    hum = _fm_osc(carrier_freq=200, mod_freq=300, mod_index=0.4, dur=dur)
    hum *= _env_adsr(n, a=0.03, d=0.05, s=0.35, r=0.12) * 0.12
    combined = np.zeros(n)
    combined[:n] += bubble + hum
    combined[:edge_n] += edge * 0.18
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.18, decay=0.18)
    return _stereo(mono, width=0.4, mode='spread')


def gen_soul_reap():
    """Soul reap — KS spectral chain slash with FM dark rip and formant ghost cry."""
    dur = 0.25
    n = int(RATE * dur)
    # KS spectral chain — metallic ghostly slash
    chain = _karplus_strong(800, 0.12, brightness=0.6, damping=0.5,
                            pluck_position=0.2, body_size=0.3)
    chain_n = len(chain)
    chain = _ring_mod(chain, mod_freq=300, mix=0.4)
    # FM dark rip — tearing sound
    rip = _fm_osc(carrier_freq=250, mod_freq=400, mod_index=4.0, dur=0.12)
    rip_n = len(rip)
    rip *= _env_perc(rip_n, attack=0.001, decay_frac=0.5) * 0.28
    # Formant ghost cry — brief spectral wail
    cry = _fm_osc(carrier_freq=500, mod_freq=600, mod_index=1.0, dur=0.15)
    cry = _formant(cry, vowel='e', intensity=0.5)
    cry_n = len(cry)
    cry *= _env_perc(cry_n, attack=0.005, decay_frac=0.6) * 0.15
    # Noise burst
    burst_n = int(RATE * 0.01)
    burst = _noise(burst_n, 'white') * np.linspace(1, 0, burst_n) * 0.4
    combined = np.zeros(n)
    combined[:burst_n] += burst
    combined[:chain_n] += chain * 0.22
    combined[int(RATE*0.01):int(RATE*0.01)+rip_n] += rip
    combined[int(RATE*0.03):int(RATE*0.03)+cry_n] += cry
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='crypt', wet=0.20, decay=0.18)
    return _stereo(mono, width=0.4, mode='haas')


def gen_venom_gaze():
    """Venom gaze — FM toxic bubbling with ring mod acid and formant hiss."""
    dur = 0.3
    n = int(RATE * dur)
    # FM toxic bubbling — modulated slimy oscillation
    bubble = _fm_osc(carrier_freq=300, mod_freq=15, mod_index=2.5, dur=dur)
    bubble *= _env_perc(n, attack=0.01, decay_frac=0.9) * 0.25
    bubble = _ring_mod(bubble, mod_freq=80, mix=0.3)
    # KS drip impacts — acid droplets
    drips = np.zeros(n)
    for i in range(3):
        offset = int(RATE * (i * 0.07 + 0.02))
        drip = _karplus_strong(500 + i * 150, 0.04, brightness=0.7, damping=0.6,
                               pluck_position=0.2, body_size=0.15)
        drip_n = len(drip)
        end = min(offset + drip_n, n)
        drips[offset:end] += drip[:end - offset] * 0.10
    # Formant hiss — venomous sibilant
    hiss = _noise(n, 'white') * _env_perc(n, attack=0.02, decay_frac=0.5)
    hiss = _formant(hiss, vowel='i', intensity=0.4)
    hiss = _highpass(hiss, 2000) * 0.10
    mono = _normalize(bubble + drips + hiss)
    mono = _conv_reverb(mono, room='crypt', wet=0.18, decay=0.15)
    return _stereo(mono, width=0.3, mode='haas')


# ── BARD ──────────────────────────────────────────────────────

def gen_ballad_of_might():
    """Ballad of might — KS heroic lute arpeggio with FM brass swell and formant power."""
    dur_total = 0.5
    n = int(RATE * dur_total)
    combined = np.zeros(n)
    # KS lute arpeggio — ascending major (A4, C#5, E5 + octave)
    notes = [440, 554, 659, 880]
    for i, freq in enumerate(notes):
        offset = int(RATE * (i * 0.09))
        pluck = _karplus_strong(freq, 0.18, brightness=0.6, damping=0.4,
                                pluck_position=0.35, body_size=0.4)
        pluck_n = len(pluck)
        end = min(offset + pluck_n, n)
        combined[offset:end] += pluck[:end - offset] * 0.18
    # FM brass swell — heroic power underneath
    brass = _fm_osc(carrier_freq=220, mod_freq=330, mod_index=1.5, dur=dur_total)
    brass = _formant(brass, vowel='o', intensity=0.4)
    brass *= _env_adsr(n, a=0.1, d=0.08, s=0.35, r=0.2) * 0.15
    combined[:n] += brass
    mono = _normalize(combined)
    mono = _chorus(mono, voices=2, max_delay_ms=6, depth_ms=2, rate_hz=1.2)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.22, decay=0.25)
    return _stereo(mono, width=0.45, mode='spread')


def gen_dirge_of_weakness():
    """Dirge of weakness — KS dark descending lament with FM dissonance and formant moan."""
    dur_total = 0.5
    n = int(RATE * dur_total)
    combined = np.zeros(n)
    # KS dark descending — minor feel (A4, G4, E4, D4)
    notes = [440, 392, 330, 294]
    for i, freq in enumerate(notes):
        offset = int(RATE * (i * 0.10))
        pluck = _karplus_strong(freq, 0.15, brightness=0.25, damping=0.2,
                                pluck_position=0.6, body_size=0.7)
        pluck_n = len(pluck)
        end = min(offset + pluck_n, n)
        combined[offset:end] += pluck[:end - offset] * 0.18
    # FM dissonant drone — oppressive tritone undertone
    drone = _fm_osc(carrier_freq=150, mod_freq=212, mod_index=2.0, dur=dur_total)
    drone *= _env_adsr(n, a=0.06, d=0.1, s=0.3, r=0.2) * 0.12
    drone = _ring_mod(drone, mod_freq=60, mix=0.2)
    # Formant moan — despairing vocal
    moan = _fm_osc(carrier_freq=180, mod_freq=5, mod_index=0.1, dur=dur_total)
    moan = _formant(moan, vowel='u', intensity=0.5)
    moan *= _env_adsr(n, a=0.08, d=0.1, s=0.25, r=0.15) * 0.12
    combined[:n] += drone + moan
    mono = _normalize(combined)
    mono = _chorus(mono, voices=2, max_delay_ms=10, depth_ms=4, rate_hz=0.6)
    mono = _conv_reverb(mono, room='crypt', wet=0.25, decay=0.28)
    return _stereo(mono, width=0.4, mode='mid_side')


def gen_war_hymn():
    """War Hymn — warm radiant pulse with KS harp tones and FM choir shimmer."""
    dur_total = 0.3
    n = int(RATE * dur_total)
    combined = np.zeros(n)
    # KS rapid ascending twinkle — C5 E5 G5 C6 (bright, fast)
    notes = [523, 659, 784, 1047]
    for i, freq in enumerate(notes):
        offset = int(RATE * (i * 0.05))
        twinkle = _karplus_strong(freq, 0.10, brightness=0.85, damping=0.6,
                                  pluck_position=0.15, body_size=0.2)
        tw_n = len(twinkle)
        end = min(offset + tw_n, n)
        combined[offset:end] += twinkle[:end - offset] * 0.18
    # FM sparkle shimmer — high airy overlay
    shimmer = _fm_osc(carrier_freq=2000, mod_freq=3000, mod_index=0.3, dur=dur_total)
    shimmer *= _env_perc(n, attack=0.005, decay_frac=0.4) * 0.08
    combined[:n] += shimmer
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.15, decay=0.12)
    return _stereo(mono, width=0.5, mode='spread')


def gen_cacophony():
    """Cacophony — dissonant FM chaos with modal clatter, bitcrush, and ring mod assault."""
    dur = 0.35
    n = int(RATE * dur)
    # FM chaotic base — tritone horror with high mod index
    chaos1 = _fm_osc(carrier_freq=300, mod_freq=427, mod_index=5.0, dur=dur)
    chaos1 *= _env_perc(n, attack=0.005, decay_frac=0.9) * 0.22
    chaos2 = _fm_osc(carrier_freq=567, mod_freq=300, mod_index=3.5, dur=dur)
    chaos2 *= _env_perc(n, attack=0.008, decay_frac=0.8) * 0.18
    # Modal dissonant clatter
    clatter_modes = [
        (300, 1.0, 0.05),   # Low grind
        (427, 0.8, 0.04),   # Tritone
        (567, 0.6, 0.03),   # Cluster
        (650, 0.3, 0.02),   # Snarl
    ]
    clatter = _modal_synthesis(clatter_modes, dur)
    clatter *= _env_perc(n, attack=0.003, decay_frac=0.7) * 0.15
    # Ring mod for maximum dissonance
    combined = chaos1 + chaos2 + clatter
    combined = _ring_mod(combined, mod_freq=170, mix=0.35)
    combined = _bitcrush(combined, bit_depth=8, downsample=3)
    combined = _distort(combined, gain=2.0, clip=0.6)
    mono = _normalize(combined)
    mono = _chorus(mono, voices=2, max_delay_ms=6, depth_ms=3, rate_hz=1.5)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.20, decay=0.18)
    return _stereo(mono, width=0.5, mode='spread')


# ── BLOOD KNIGHT ──────────────────────────────────────────────

def gen_blood_strike():
    """Blood strike — KS bone-blade slash with FM wet visceral tear and sub thud."""
    dur = 0.2
    n = int(RATE * dur)
    # KS bone-blade — sharp jagged metallic slash
    blade = _karplus_strong(600, 0.08, brightness=0.75, damping=0.6,
                            pluck_position=0.12, body_size=0.2)
    blade_n = len(blade)
    # FM wet tear — vampiric flesh ripping
    tear = _fm_osc(carrier_freq=250, mod_freq=350, mod_index=3.0, dur=0.10)
    tear_n = len(tear)
    tear *= _env_perc(tear_n, attack=0.001, decay_frac=0.5) * 0.25
    tear = _formant(tear, vowel='a', intensity=0.3)
    # Sub thud — vampiric impact
    thud = _pitch_env_osc(80, 0.05, env_type='drop', amount=1.5)
    thud_n = len(thud)
    thud *= _env_perc(thud_n, attack=0.001, decay_frac=0.3) * 0.20
    # Noise transient for slash
    trans_n = int(RATE * 0.008)
    trans = _noise(trans_n, 'white') * np.linspace(1, 0, trans_n) * 0.4
    combined = np.zeros(n)
    combined[:trans_n] += trans
    combined[:blade_n] += blade * 0.22
    combined[int(RATE*0.01):int(RATE*0.01)+tear_n] += tear
    combined[:thud_n] += thud
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.14, decay=0.12)
    return _stereo(mono, width=0.35, mode='haas')


def gen_crimson_veil():
    """Crimson veil — FM dark blood swirl with KS ghostly strings and formant whisper."""
    dur = 0.4
    n = int(RATE * dur)
    # FM dark blood swirl — slow ominous rotation
    swirl = _fm_osc(carrier_freq=200, mod_freq=3, mod_index=1.5, dur=dur)
    swirl *= _env_adsr(n, a=0.05, d=0.08, s=0.45, r=0.2) * 0.22
    swirl = _ring_mod(swirl, mod_freq=60, mix=0.2)
    # KS ghostly strings — dark sustained
    ghost1 = _karplus_strong(165, dur, brightness=0.2, damping=0.15,
                             pluck_position=0.6, body_size=0.75)
    ghost2 = _karplus_strong(220, dur, brightness=0.18, damping=0.15,
                             pluck_position=0.55, body_size=0.7)
    ghosts = (ghost1 * 0.15 + ghost2 * 0.12) * _env_adsr(n, a=0.06, d=0.1, s=0.35, r=0.15)
    # Formant dark whisper
    whisper = _noise(n, 'pink') * _env_adsr(n, a=0.08, d=0.1, s=0.2, r=0.15)
    whisper = _formant(whisper, vowel='u', intensity=0.5)
    whisper *= 0.08
    mono = _normalize(swirl + ghosts + whisper)
    mono = _chorus(mono, voices=3, max_delay_ms=10, depth_ms=4, rate_hz=0.6)
    mono = _conv_reverb(mono, room='crypt', wet=0.28, decay=0.30)
    return _stereo(mono, width=0.4, mode='mid_side')


def gen_sanguine_burst():
    """Sanguine burst — modal visceral explosion with FM blood wave and KS bone shatter."""
    dur = 0.3
    n = int(RATE * dur)
    # Modal visceral explosion — wet, meaty
    gore_modes = [
        (120, 1.0, 0.08),  # Deep organ thud
        (280, 0.6, 0.05),  # Body cavity
        (550, 0.3, 0.03),  # Splatter mid
    ]
    gore = _modal_synthesis(gore_modes, dur)
    gore *= _env_perc(n, attack=0.002, decay_frac=0.7) * 0.30
    # FM blood wave — expanding crimson burst
    wave = _fm_osc(carrier_freq=150, mod_freq=200, mod_index=3.5, dur=0.15)
    wave_n = len(wave)
    wave *= _env_perc(wave_n, attack=0.002, decay_frac=0.5) * 0.28
    # KS bone shatter — jagged fragments
    shatter = _karplus_strong(1200, 0.06, brightness=0.8, damping=0.7,
                              pluck_position=0.1, body_size=0.1)
    shatter_n = len(shatter)
    # Sub punch
    sub = _pitch_env_osc(60, 0.06, env_type='drop', amount=2.0)
    sub_n = len(sub)
    sub *= _env_perc(sub_n, attack=0.001, decay_frac=0.3) * 0.25
    combined = np.zeros(n)
    combined[:n] += gore
    combined[:wave_n] += wave
    combined[:shatter_n] += shatter * 0.15
    combined[:sub_n] += sub
    mono = _normalize(combined)
    mono = _distort(mono, gain=1.5, clip=0.55)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.18, decay=0.18)
    return _stereo(mono, width=0.45, mode='haas')


def gen_blood_frenzy():
    """Blood frenzy — FM heartbeat with modal bone percussion and KS dark energy surge."""
    dur = 0.5
    n = int(RATE * dur)
    combined = np.zeros(n)
    # FM heartbeat thumps — two deep visceral beats
    for i, offset_s in enumerate([0.0, 0.18]):
        offset = int(RATE * offset_s)
        heart = _fm_osc(carrier_freq=45, mod_freq=60, mod_index=2.0, dur=0.10)
        heart_n = len(heart)
        heart *= _env_perc(heart_n, attack=0.002, decay_frac=0.4) * 0.30
        end = min(offset + heart_n, n)
        combined[offset:end] += heart[:end - offset]
    # Modal bone percussion — frenetic rattling
    bone_modes = [(350, 1.0, 0.04), (700, 0.5, 0.025), (1050, 0.25, 0.015)]
    bones = _modal_synthesis(bone_modes, 0.08)
    bones_n = len(bones)
    bones *= _env_perc(bones_n, attack=0.001, decay_frac=0.3) * 0.15
    combined[int(RATE*0.10):int(RATE*0.10)+bones_n] += bones
    # KS dark energy surge — rising power
    surge = _karplus_strong(130, dur * 0.6, brightness=0.3, damping=0.2,
                            pluck_position=0.5, body_size=0.6)
    surge_n = len(surge)
    surge *= _env_adsr(surge_n, a=0.05, d=0.1, s=0.4, r=0.2) * 0.18
    combined[int(RATE*0.15):int(RATE*0.15)+surge_n] += surge
    # Ring mod for frenzy distortion
    combined = _ring_mod(combined, mod_freq=40, mix=0.15)
    mono = _normalize(combined)
    mono = _tremolo(mono, rate=6.0, depth=0.3, shape='sine')
    mono = _conv_reverb(mono, room='crypt', wet=0.22, decay=0.22)
    return _stereo(mono, width=0.35, mode='haas')


# ── PLAGUE DOCTOR ─────────────────────────────────────────────

def gen_miasma():
    """Miasma — FM toxic gas with modal bubbling resonance and formant sickly breath."""
    dur = 0.55
    n = int(RATE * dur)
    # FM toxic gas — churning poisonous cloud
    gas = _fm_osc(carrier_freq=120, mod_freq=8, mod_index=3.0, dur=dur)
    gas *= _env_adsr(n, a=0.08, d=0.1, s=0.4, r=0.25) * 0.20
    gas = _ring_mod(gas, mod_freq=35, mix=0.25)
    # Modal bubbling resonance — sickly liquid pops
    bubble_modes = [
        (180, 1.0, 0.06),  # Deep gurgle
        (350, 0.5, 0.04),  # Mid bubble
        (580, 0.25, 0.02), # High pop
    ]
    bubbles = _modal_synthesis(bubble_modes, dur)
    bubbles *= _tremolo(np.ones(n), rate=8.0, depth=0.6, shape='sine')
    bubbles *= _env_adsr(n, a=0.06, d=0.1, s=0.3, r=0.15) * 0.15
    # Formant sickly breath — diseased exhale
    breath = _noise(n, 'pink') * _env_adsr(n, a=0.1, d=0.1, s=0.25, r=0.2)
    breath = _formant(breath, vowel='u', intensity=0.5)
    breath *= 0.10
    # High toxic hiss
    hiss = _noise(n, 'white') * _env_adsr(n, a=0.08, d=0.1, s=0.3, r=0.2)
    hiss = _highpass(hiss, 4000) * 0.08
    mono = _normalize(gas + bubbles + breath + hiss)
    mono = _chorus(mono, voices=2, max_delay_ms=10, depth_ms=4, rate_hz=0.5)
    mono = _conv_reverb(mono, room='crypt', wet=0.30, decay=0.35)
    return _stereo(mono, width=0.5, mode='spread')


def gen_plague_flask():
    """Plague flask — modal glass shatter with FM liquid splash and KS cork pop."""
    dur = 0.3
    n = int(RATE * dur)
    # KS cork pop — sharp bright snap
    pop = _karplus_strong(1500, 0.03, brightness=0.9, damping=0.8,
                          pluck_position=0.1, body_size=0.05)
    pop_n = len(pop)
    # Modal glass shatter — flask breaking
    glass_modes = [
        (2000, 1.0, 0.03),  # Bright shard
        (3200, 0.6, 0.02),  # High ring
        (4500, 0.3, 0.015), # Tinkle
    ]
    glass = _modal_synthesis(glass_modes, 0.10)
    glass_n = len(glass)
    glass *= _env_perc(glass_n, attack=0.001, decay_frac=0.4) * 0.20
    # FM liquid splash — toxic contents spilling
    splash = _fm_osc(carrier_freq=400, mod_freq=12, mod_index=4.0, dur=0.15)
    splash_n = len(splash)
    splash *= _env_perc(splash_n, attack=0.005, decay_frac=0.6) * 0.18
    # Noise spray
    spray = _noise(int(RATE * 0.12), 'pink') * _env_perc(int(RATE * 0.12), decay_frac=0.5)
    spray = _bandpass(spray, 800, 4000) * 0.10
    spray_n = len(spray)
    combined = np.zeros(n)
    combined[:pop_n] += pop * 0.25
    combined[int(RATE*0.02):int(RATE*0.02)+glass_n] += glass
    combined[int(RATE*0.04):int(RATE*0.04)+splash_n] += splash
    combined[int(RATE*0.05):int(RATE*0.05)+spray_n] += spray
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.15, decay=0.15)
    return _stereo(mono, width=0.35, mode='haas')


def gen_enfeeble():
    """Enfeeble — FM oppressive pressure wave with modal grinding and formant despair."""
    dur = 0.35
    n = int(RATE * dur)
    # FM oppressive pressure — heavy descending weight
    pressure = _fm_osc(carrier_freq=200, mod_freq=280, mod_index=2.5, dur=dur)
    pressure *= _env_adsr(n, a=0.03, d=0.08, s=0.4, r=0.15) * 0.25
    pressure = _ring_mod(pressure, mod_freq=50, mix=0.2)
    # Modal grinding — crushing, debilitating
    grind_modes = [
        (100, 1.0, 0.08),  # Heavy base
        (230, 0.5, 0.05),  # Dissonant mid
        (450, 0.2, 0.03),  # Gritty upper
    ]
    grind = _modal_synthesis(grind_modes, dur)
    grind *= _env_perc(n, attack=0.01, decay_frac=0.8) * 0.18
    # Formant despair moan
    moan = _fm_osc(carrier_freq=130, mod_freq=5, mod_index=0.1, dur=dur)
    moan = _formant(moan, vowel='u', intensity=0.5)
    moan *= _env_adsr(n, a=0.05, d=0.08, s=0.25, r=0.12) * 0.10
    mono = _normalize(pressure + grind + moan)
    mono = _conv_reverb(mono, room='crypt', wet=0.22, decay=0.22)
    return _stereo(mono, width=0.35, mode='mid_side')


def gen_inoculate():
    """Inoculate — modal cleansing chime with KS crystal cascade and FM purifying tone."""
    dur = 0.35
    n = int(RATE * dur)
    # Modal cleansing chime — pure, bright, healing
    chime_modes = [
        (880, 1.0, 0.08),   # Pure fundamental
        (1320, 0.5, 0.06),  # Fifth overtone
        (1760, 0.3, 0.04),  # Octave
        (2640, 0.15, 0.02), # High sparkle
    ]
    chime = _modal_synthesis(chime_modes, dur)
    chime *= _env_adsr(n, a=0.02, d=0.05, s=0.4, r=0.2) * 0.25
    # KS crystal cascade — sparkling purification
    crystals = np.zeros(n)
    for i, freq in enumerate([1100, 1650, 2200]):
        offset = int(RATE * (i * 0.04))
        cr = _karplus_strong(freq, 0.1, brightness=0.8, damping=0.6,
                             pluck_position=0.15, body_size=0.15)
        cr_n = len(cr)
        end = min(offset + cr_n, n)
        crystals[offset:end] += cr[:end - offset] * 0.10
    # FM purifying tone — clean sustained
    pure = _fm_osc(carrier_freq=660, mod_freq=990, mod_index=0.3, dur=dur)
    pure *= _env_adsr(n, a=0.03, d=0.06, s=0.3, r=0.15) * 0.10
    mono = _normalize(chime + crystals + pure)
    mono = _chorus(mono, voices=2, max_delay_ms=6, depth_ms=2, rate_hz=1.2)
    mono = _conv_reverb(mono, room='cathedral', wet=0.22, decay=0.22)
    return _stereo(mono, width=0.45, mode='spread')


# ── REVENANT ──────────────────────────────────────────────────

def gen_deaths_embrace():
    """Death's Embrace — dark bone/shard aura activation with modal eruption, KS thorn spikes and FM rumble."""
    dur = 0.25
    n = int(RATE * dur)
    # Modal bone eruption — sharp cracking inharmonic
    bone_modes = [
        (400, 1.0, 0.04),   # Crack base
        (900, 0.6, 0.025),  # Mid snap
        (1800, 0.3, 0.015), # High splinter
    ]
    bones = _modal_synthesis(bone_modes, dur)
    bones *= _env_perc(n, attack=0.002, decay_frac=0.6) * 0.28
    bones = _distort(bones, gain=1.8, clip=0.55)
    # KS thorn spikes — rapid jagged pings
    spikes = np.zeros(n)
    for i in range(3):
        offset = int(RATE * (i * 0.04))
        spike = _karplus_strong(1200 + i * 400, 0.04, brightness=0.8, damping=0.7,
                                pluck_position=0.1, body_size=0.08)
        sp_n = len(spike)
        end = min(offset + sp_n, n)
        spikes[offset:end] += spike[:end - offset] * 0.12
    # FM dark rumble — earth displacement
    rumble = _fm_osc(carrier_freq=60, mod_freq=80, mod_index=2.0, dur=0.10)
    rumble_n = len(rumble)
    rumble *= _env_perc(rumble_n, attack=0.002, decay_frac=0.4) * 0.20
    combined = np.zeros(n)
    combined[:n] += bones + spikes
    combined[:rumble_n] += rumble
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='crypt', wet=0.18, decay=0.15)
    return _stereo(mono, width=0.35, mode='haas')


def gen_grasp_of_the_grave():
    """Grasp of the Grave — KS spectral chain rattle with modal dark links and FM ground rumble."""
    dur = 0.4
    n = int(RATE * dur)
    # KS chain rattle — metallic link impacts
    chains = np.zeros(n)
    for i in range(6):
        offset = int(RATE * i * 0.05)
        link = _karplus_strong(800 + i * 200, 0.05, brightness=0.7, damping=0.6,
                               pluck_position=0.15, body_size=0.15)
        link_n = len(link)
        end = min(offset + link_n, n)
        chains[offset:end] += link[:end - offset] * 0.12
    chains = _ring_mod(chains, mod_freq=250, mix=0.3)
    # Modal dark links — heavy spectral body
    link_modes = [
        (300, 1.0, 0.06),  # Heavy chain
        (600, 0.5, 0.04),  # Rattle mid
        (1200, 0.2, 0.02), # Tinkle
    ]
    dark_links = _modal_synthesis(link_modes, dur)
    dark_links *= _env_perc(n, attack=0.01, decay_frac=0.8) * 0.15
    # FM ghost wail — spectral undertone
    wail = _fm_osc(carrier_freq=200, mod_freq=250, mod_index=1.5, dur=dur)
    wail = _formant(wail, vowel='o', intensity=0.4)
    wail *= _env_adsr(n, a=0.05, d=0.1, s=0.2, r=0.15) * 0.10
    mono = _normalize(chains + dark_links + wail)
    mono = _chorus(mono, voices=2, max_delay_ms=5, depth_ms=2, rate_hz=1.5)
    mono = _conv_reverb(mono, room='crypt', wet=0.25, decay=0.25)
    return _stereo(mono, width=0.45, mode='spread')


def gen_undying_fury():
    """Undying Fury cast — FM deep doom drone with modal dark power and KS spectral pulse."""
    dur = 0.5
    n = int(RATE * dur)
    # FM doom drone — ominous sustained power
    doom = _fm_osc(carrier_freq=80, mod_freq=100, mod_index=1.8, dur=dur)
    doom *= _env_adsr(n, a=0.05, d=0.1, s=0.5, r=0.25) * 0.22
    doom = _ring_mod(doom, mod_freq=30, mix=0.15)
    # Modal dark power — resonant bone-like body
    power_modes = [
        (80, 1.0, 0.15),   # Deep fundamental
        (160, 0.6, 0.10),  # Octave
        (250, 0.3, 0.06),  # Dark overtone
    ]
    power = _modal_synthesis(power_modes, dur)
    power *= _env_adsr(n, a=0.06, d=0.1, s=0.4, r=0.2) * 0.18
    # KS spectral pulse — undead heartbeat
    pulse = _karplus_strong(50, dur * 0.5, brightness=0.15, damping=0.1,
                            pluck_position=0.7, body_size=0.9)
    pulse_n = len(pulse)
    pulse *= 0.15
    combined = np.zeros(n)
    combined[:n] += doom + power
    combined[:pulse_n] += pulse
    mono = _normalize(combined)
    mono = _tremolo(mono, rate=4.0, depth=0.35, shape='sine')
    mono = _chorus(mono, voices=3, max_delay_ms=12, depth_ms=5, rate_hz=0.5)
    mono = _conv_reverb(mono, room='crypt', wet=0.30, decay=0.35)
    return _stereo(mono, width=0.35, mode='mid_side')


def gen_undying_fury_trigger():
    """Undying Fury trigger — dramatic FM resurrection explosion with modal dark ring and KS spirit cascade."""
    dur = 0.6
    n = int(RATE * dur)
    # FM resurrection blast — explosive ascending force
    blast = _fm_osc(carrier_freq=150, mod_freq=200, mod_index=3.5, dur=0.20)
    blast_n = len(blast)
    blast *= _env_perc(blast_n, attack=0.005, decay_frac=0.6) * 0.28
    # Modal divine ring — triumphant resonance
    divine_modes = [
        (523, 1.0, 0.12),  # C5 fundamental
        (659, 0.6, 0.10),  # E5 major third
        (784, 0.4, 0.08),  # G5 fifth
        (1047, 0.2, 0.05), # C6 octave shimmer
    ]
    divine = _modal_synthesis(divine_modes, dur)
    divine *= _env_adsr(n, a=0.08, d=0.1, s=0.4, r=0.3) * 0.22
    # KS spirit cascade — ascending ethereal plucks
    spirits = np.zeros(n)
    for i, freq in enumerate([440, 660, 880, 1320]):
        offset = int(RATE * (0.05 + i * 0.08))
        sp = _karplus_strong(freq, 0.2, brightness=0.5, damping=0.35,
                             pluck_position=0.3, body_size=0.4)
        sp_n = len(sp)
        end = min(offset + sp_n, n)
        spirits[offset:end] += sp[:end - offset] * 0.10
    # Sub impact
    sub = _pitch_env_osc(60, 0.08, env_type='drop', amount=2.0)
    sub_n = len(sub)
    sub *= _env_perc(sub_n, attack=0.002, decay_frac=0.3) * 0.20
    combined = np.zeros(n)
    combined[:blast_n] += blast
    combined[:sub_n] += sub
    combined[:n] += divine + spirits
    mono = _normalize(combined)
    mono = _chorus(mono, voices=3, max_delay_ms=10, depth_ms=4, rate_hz=0.7)
    mono = _conv_reverb(mono, room='cathedral', wet=0.30, decay=0.35)
    return _stereo(mono, width=0.55, mode='spread')


def gen_soul_rend():
    """Soul rend — FM spectral slash with KS ghost blade and modal dark impact."""
    dur = 0.2
    n = int(RATE * dur)
    # FM spectral slash — tearing ethereal fabric
    slash = _fm_osc(carrier_freq=500, mod_freq=700, mod_index=4.0, dur=0.10)
    slash_n = len(slash)
    slash *= _env_perc(slash_n, attack=0.001, decay_frac=0.4) * 0.28
    slash = _ring_mod(slash, mod_freq=200, mix=0.35)
    # KS ghost blade — spectral metallic edge
    blade = _karplus_strong(1000, 0.08, brightness=0.65, damping=0.55,
                            pluck_position=0.2, body_size=0.2)
    blade_n = len(blade)
    # Modal dark impact — soul-tearing thud
    dark_modes = [(180, 1.0, 0.04), (420, 0.4, 0.025)]
    dark = _modal_synthesis(dark_modes, 0.08)
    dark_n = len(dark)
    dark *= _env_perc(dark_n, attack=0.001, decay_frac=0.3) * 0.22
    # Noise transient
    trans_n = int(RATE * 0.006)
    trans = _noise(trans_n, 'white') * np.linspace(1, 0, trans_n) * 0.4
    combined = np.zeros(n)
    combined[:trans_n] += trans
    combined[:slash_n] += slash
    combined[:blade_n] += blade * 0.18
    combined[:dark_n] += dark
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='crypt', wet=0.18, decay=0.15)
    return _stereo(mono, width=0.4, mode='haas')


def gen_soul_rend_empowered():
    """Soul Rend (empowered) — deeper, more aggressive FM slash with KS blade resonance and bleed undertone."""
    dur = 0.3
    n = int(RATE * dur)
    # FM heavy spectral slash — deeper and wider than normal Soul Rend
    slash = _fm_osc(carrier_freq=350, mod_freq=500, mod_index=5.0, dur=0.15)
    slash_n = len(slash)
    slash *= _env_perc(slash_n, attack=0.001, decay_frac=0.5) * 0.32
    slash = _ring_mod(slash, mod_freq=150, mix=0.4)
    slash = _distort(slash, gain=2.0, clip=0.6)
    # KS ghost blade — heavier, darker edge
    blade = _karplus_strong(700, 0.12, brightness=0.55, damping=0.45,
                            pluck_position=0.25, body_size=0.35)
    blade_n = len(blade)
    # Modal dark impact — deep soul-tearing thud
    dark_modes = [(120, 1.0, 0.06), (300, 0.5, 0.035), (600, 0.2, 0.02)]
    dark = _modal_synthesis(dark_modes, 0.12)
    dark_n = len(dark)
    dark *= _env_perc(dark_n, attack=0.001, decay_frac=0.35) * 0.25
    # Bleed undertone — wet dripping FM tail
    bleed = _fm_osc(carrier_freq=100, mod_freq=160, mod_index=2.0, dur=0.15)
    bleed_n = len(bleed)
    bleed *= _env_adsr(bleed_n, a=0.01, d=0.04, s=0.2, r=0.08) * 0.12
    # Noise transient — sharper than normal
    trans_n = int(RATE * 0.008)
    trans = _noise(trans_n, 'white') * np.linspace(1, 0, trans_n) * 0.5
    combined = np.zeros(n)
    combined[:trans_n] += trans
    combined[:slash_n] += slash
    combined[:blade_n] += blade * 0.20
    combined[:dark_n] += dark
    combined[:bleed_n] += bleed
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='crypt', wet=0.22, decay=0.20)
    return _stereo(mono, width=0.5, mode='haas')


# ── SHAMAN ────────────────────────────────────────────────────

def gen_healing_totem():
    """Healing totem placement — earthy modal slam + KS spirit drone.
    Physical impact into warm spiritual resonance."""
    dur = 0.45
    n = int(RATE * dur)
    # Heavy earthy slam — wooden/stone modal body
    earth_modes = [
        (85, 1.0, 0.10),    # Deep thud
        (210, 0.5, 0.06),   # Body resonance
        (480, 0.2, 0.03),   # Mid knock
    ]
    slam = _modal_synthesis(earth_modes, dur)
    slam *= _env_perc(n, attack=0.002, decay_frac=0.8) * 0.5
    # Spirit drone — warm KS strings evoking nature
    spirit1 = _karplus_strong(220, dur, brightness=0.4, damping=0.25,
                              pluck_position=0.5, body_size=0.6)
    spirit2 = _karplus_strong(330, dur, brightness=0.35, damping=0.25,
                              pluck_position=0.45, body_size=0.5)
    spirits = (spirit1 * 0.25 + spirit2 * 0.2) * _env_adsr(n, a=0.08, d=0.1, s=0.3, r=0.15)
    mono = _normalize(_mix(slam, spirits))
    mono = _chorus(mono, voices=2, max_delay_ms=8, depth_ms=3, rate_hz=0.7)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.25, decay=0.3)
    return _stereo(mono, width=0.45, mode='spread')


def gen_healing_totem_tick():
    """Healing totem pulse — soft KS pluck with modal bell overtone.
    Warm, earthy, repeating."""
    dur = 0.25
    n = int(RATE * dur)
    # Soft warm pluck — like a wooden instrument
    pluck = _karplus_strong(550, dur, brightness=0.4, damping=0.35,
                            pluck_position=0.5, body_size=0.5)
    pluck *= _env_perc(n, decay_frac=0.7) * 0.45
    # Gentle bell overtone — single modal ping
    bell = _modal_synthesis([(1100, 0.3, 0.06)], dur)
    bell *= _env_perc(n, decay_frac=0.4) * 0.1
    # Sub earth presence
    sub = _sine(220, dur) * _env_perc(n, decay_frac=0.3) * 0.12
    mono = _normalize(_mix(pluck, bell, sub))
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.18, decay=0.18)
    return _stereo(mono, width=0.38, mode='spread')


def gen_searing_totem():
    """Searing totem — modal earth slam with FM fire roar, KS crackle, and pitch-drop impact."""
    dur = 0.45
    n = int(RATE * dur)
    # Modal earth slam — heavy stone/wood thud
    earth_modes = [
        (75, 1.0, 0.08),   # Deep impact
        (190, 0.5, 0.05),  # Body resonance
        (380, 0.2, 0.03),  # Mid knock
    ]
    slam = _modal_synthesis(earth_modes, dur)
    slam *= _env_perc(n, attack=0.002, decay_frac=0.7) * 0.28
    # FM fire roar — aggressive flame sound
    fire = _fm_osc(carrier_freq=90, mod_freq=7, mod_index=4.0, dur=dur)
    fire *= _env_adsr(n, a=0.03, d=0.08, s=0.35, r=0.15) * 0.18
    fire = _ring_mod(fire, mod_freq=45, mix=0.2)
    # KS crackle — rapid fire pops
    crackle = np.zeros(n)
    for i in range(5):
        offset = int(RATE * (0.05 + i * 0.06))
        pop = _karplus_strong(2000 + i * 500, 0.02, brightness=0.9, damping=0.8,
                              pluck_position=0.05, body_size=0.03)
        pop_n = len(pop)
        end = min(offset + pop_n, n)
        crackle[offset:end] += pop[:end - offset] * 0.08
    # Pitch-drop impact sub
    sub = _pitch_env_osc(70, 0.06, env_type='drop', amount=2.0)
    sub_n = len(sub)
    sub *= _env_perc(sub_n, attack=0.001, decay_frac=0.3) * 0.18
    combined = np.zeros(n)
    combined[:n] += slam + fire + crackle
    combined[:sub_n] += sub
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.20, decay=0.22)
    return _stereo(mono, width=0.42, mode='haas')


def gen_soul_anchor():
    """Soul anchor — FM deep ethereal chord with modal spirit resonance and KS anchor chain."""
    dur = 0.5
    n = int(RATE * dur)
    # FM deep ethereal chord — mystic binding
    chord1 = _fm_osc(carrier_freq=165, mod_freq=220, mod_index=0.8, dur=dur)
    chord2 = _fm_osc(carrier_freq=220, mod_freq=330, mod_index=0.6, dur=dur)
    chord = (chord1 * 0.20 + chord2 * 0.15) * _env_adsr(n, a=0.05, d=0.1, s=0.4, r=0.25)
    # Modal spirit resonance — otherworldly presence
    spirit_modes = [
        (165, 1.0, 0.12),  # Deep root
        (330, 0.5, 0.08),  # Octave
        (495, 0.3, 0.05),  # Fifth
    ]
    spirit = _modal_synthesis(spirit_modes, dur)
    spirit *= _env_adsr(n, a=0.06, d=0.1, s=0.3, r=0.2) * 0.18
    # KS anchor chain thud
    anchor = _karplus_strong(80, 0.15, brightness=0.2, damping=0.15,
                             pluck_position=0.7, body_size=0.9)
    anchor_n = len(anchor)
    anchor *= _env_perc(anchor_n, attack=0.002, decay_frac=0.4) * 0.22
    # Sub impact
    sub = _pitch_env_osc(55, 0.08, env_type='drop', amount=1.5)
    sub_n = len(sub)
    sub *= _env_perc(sub_n, attack=0.001, decay_frac=0.3) * 0.15
    combined = np.zeros(n)
    combined[:n] += chord + spirit
    combined[:anchor_n] += anchor
    combined[:sub_n] += sub
    mono = _normalize(combined)
    mono = _chorus(mono, voices=3, max_delay_ms=10, depth_ms=4, rate_hz=0.6)
    mono = _conv_reverb(mono, room='crypt', wet=0.28, decay=0.30)
    return _stereo(mono, width=0.4, mode='mid_side')


def gen_soul_anchor_save():
    """Soul anchor save — dramatic FM rescue burst with modal divine ring and KS spirit chime."""
    dur = 0.4
    n = int(RATE * dur)
    # FM rescue burst — explosive ascending salvation
    burst = _fm_osc(carrier_freq=250, mod_freq=400, mod_index=3.0, dur=0.15)
    burst_n = len(burst)
    burst *= _env_perc(burst_n, attack=0.003, decay_frac=0.5) * 0.30
    # Modal divine ring — salvation resonance
    divine_modes = [
        (880, 1.0, 0.10),  # Bright ring
        (1320, 0.5, 0.07), # Fifth shimmer
        (1760, 0.3, 0.04), # Octave sparkle
    ]
    divine = _modal_synthesis(divine_modes, dur)
    divine *= _env_adsr(n, a=0.03, d=0.08, s=0.35, r=0.2) * 0.20
    # KS spirit chime cascade
    chimes = np.zeros(n)
    for i, freq in enumerate([1200, 1500, 1800]):
        offset = int(RATE * (i * 0.05 + 0.05))
        ch = _karplus_strong(freq, 0.12, brightness=0.7, damping=0.5,
                             pluck_position=0.2, body_size=0.2)
        ch_n = len(ch)
        end = min(offset + ch_n, n)
        chimes[offset:end] += ch[:end - offset] * 0.10
    # Formant breath of life
    breath = _fm_osc(carrier_freq=400, mod_freq=500, mod_index=0.5, dur=0.15)
    breath = _formant(breath, vowel='a', intensity=0.5)
    breath_n = len(breath)
    breath *= _env_perc(breath_n, attack=0.01, decay_frac=0.6) * 0.12
    combined = np.zeros(n)
    combined[:burst_n] += burst
    combined[:n] += divine + chimes
    combined[int(RATE*0.08):int(RATE*0.08)+breath_n] += breath
    mono = _normalize(combined)
    mono = _chorus(mono, voices=2, max_delay_ms=6, depth_ms=2, rate_hz=1.2)
    mono = _conv_reverb(mono, room='cathedral', wet=0.28, decay=0.28)
    return _stereo(mono, width=0.5, mode='spread')


def gen_earthgrasp():
    """Earthgrasp — modal stone eruption with FM grinding rumble and KS root tentacles."""
    dur = 0.35
    n = int(RATE * dur)
    # Modal stone eruption — heavy earth cracking
    stone_modes = [
        (60, 1.0, 0.10),   # Deep rumble
        (150, 0.6, 0.06),  # Body crash
        (350, 0.3, 0.03),  # Crack
        (700, 0.1, 0.015), # Debris
    ]
    stone = _modal_synthesis(stone_modes, dur)
    stone *= _env_perc(n, attack=0.005, decay_frac=0.8) * 0.28
    # FM grinding rumble — earth displacement
    grind = _fm_osc(carrier_freq=50, mod_freq=70, mod_index=3.0, dur=0.15)
    grind_n = len(grind)
    grind *= _env_perc(grind_n, attack=0.002, decay_frac=0.5) * 0.22
    grind = _distort(grind, gain=1.5, clip=0.5)
    # KS root tentacles — scraping organic growth
    roots = np.zeros(n)
    for i in range(3):
        offset = int(RATE * (0.03 + i * 0.06))
        root = _karplus_strong(200 + i * 80, 0.08, brightness=0.3, damping=0.2,
                               pluck_position=0.6, body_size=0.6)
        root = _ring_mod(root, mod_freq=100, mix=0.2)
        root_n = len(root)
        end = min(offset + root_n, n)
        roots[offset:end] += root[:end - offset] * 0.10
    # Sub thud
    sub = _pitch_env_osc(50, 0.06, env_type='drop', amount=2.0)
    sub_n = len(sub)
    sub *= _env_perc(sub_n, attack=0.001, decay_frac=0.3) * 0.18
    combined = np.zeros(n)
    combined[:n] += stone + roots
    combined[:grind_n] += grind
    combined[:sub_n] += sub
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.22, decay=0.22)
    return _stereo(mono, width=0.35, mode='haas')


# ── MAGE (war_cry reused for bard, double_strike for melee) ──

def gen_war_cry():
    """War cry — FM guttural battle roar with formant power, modal armor rattle, and KS horn blast."""
    dur = 0.35
    n = int(RATE * dur)
    # FM guttural roar — primal battle cry
    roar = _fm_osc(carrier_freq=150, mod_freq=200, mod_index=3.0, dur=dur)
    roar = _formant(roar, vowel='o', intensity=0.6)
    roar *= _env_perc(n, attack=0.01, decay_frac=0.9) * 0.25
    roar = _distort(roar, gain=1.5, clip=0.6)
    # Modal armor rattle — warrior equipment shaking
    armor_modes = [
        (500, 1.0, 0.04),  # Chain rattle
        (1100, 0.4, 0.025),# Link jingle
        (1800, 0.15, 0.015),# High clink
    ]
    armor = _modal_synthesis(armor_modes, 0.10)
    armor_n = len(armor)
    armor *= _env_perc(armor_n, attack=0.002, decay_frac=0.4) * 0.12
    # KS horn blast — short aggressive brass
    horn = _karplus_strong(110, 0.15, brightness=0.4, damping=0.25,
                           pluck_position=0.5, body_size=0.6)
    horn_n = len(horn)
    horn = _formant(horn, vowel='a', intensity=0.3)
    horn *= _env_perc(horn_n, attack=0.008, decay_frac=0.5) * 0.15
    # Sub impact
    sub = _pitch_env_osc(80, 0.06, env_type='drop', amount=1.5)
    sub_n = len(sub)
    sub *= _env_perc(sub_n, attack=0.002, decay_frac=0.3) * 0.18
    combined = np.zeros(n)
    combined[:n] += roar
    combined[:armor_n] += armor
    combined[:horn_n] += horn
    combined[:sub_n] += sub
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.20, decay=0.20)
    return _stereo(mono, width=0.4, mode='haas')


def gen_double_strike():
    """Double strike — two modal metallic impacts with KS blade ring and FM body hit."""
    dur = 0.2
    n = int(RATE * dur)
    combined = np.zeros(n)
    for i in range(2):
        offset = int(RATE * (i * 0.08))
        # Modal impact — metallic strike
        hit_modes = [
            (350 + i * 50, 1.0, 0.03),  # Core
            (800 + i * 100, 0.5, 0.02), # Ring
            (1500 + i * 150, 0.2, 0.01),# Bright
        ]
        hit = _modal_synthesis(hit_modes, 0.06)
        hit_n = len(hit)
        hit *= _env_perc(hit_n, attack=0.001, decay_frac=0.3) * 0.28
        end = min(offset + hit_n, n)
        combined[offset:end] += hit[:end - offset]
        # KS blade ring
        ring = _karplus_strong(900 + i * 200, 0.04, brightness=0.75, damping=0.65,
                               pluck_position=0.12, body_size=0.12)
        ring_n = len(ring)
        ring_end = min(offset + ring_n, n)
        combined[offset:ring_end] += ring[:ring_end - offset] * 0.12
        # Noise transient
        trans_n = int(RATE * 0.005)
        trans = _noise(trans_n, 'white') * np.linspace(1, 0, trans_n) * 0.35
        trans_end = min(offset + trans_n, n)
        combined[offset:trans_end] += trans[:trans_end - offset]
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='metal_room', wet=0.12, decay=0.10)
    return _stereo(mono, width=0.3, mode='haas')


# ── ITEMS ─────────────────────────────────────────────────────

def gen_potion_use():
    """Potion consume — glorpy liquid bubble + satisfying gulp."""
    dur = 0.35
    n = int(RATE * dur)
    t = _t(dur)
    # Richer bubble — two modulated tones for liquid character
    bubble1 = _sine(400, dur) * (1 + 0.35 * _sine(10, dur))
    bubble2 = _sine(520, dur) * (1 + 0.25 * _sine(13, dur)) * 0.3
    bubble = (bubble1 + bubble2) * _env_perc(n, decay_frac=0.9) * 0.35
    # Resonant liquid filter sweep
    bubble = _resonant_sweep(bubble, 300, 700, q=3.5)
    # Gulp — filtered noise burst
    gulp_n = int(RATE * 0.1)
    gulp = _noise(gulp_n, 'pink') * np.linspace(1, 0, gulp_n) * 0.35
    gulp = _lowpass(gulp, 1400)
    # Tiny fizz tail
    fizz = _noise(n, 'white') * _env_perc(n, attack=0.08, decay_frac=0.5)
    fizz = _highpass(fizz, 3500) * 0.03
    combined = np.zeros(n)
    combined[:len(bubble)] += bubble
    combined[int(RATE * 0.15):int(RATE * 0.15) + gulp_n] += gulp
    combined[:len(fizz)] += fizz
    mono = _normalize(combined)
    mono = _reverb(mono, decay=0.15, wet=0.12, room='tight')
    return _stereo(mono, width=0.3, mode='haas')


def gen_loot_pickup():
    """Loot pickup — rewarding coin cascade with shimmer."""
    dur = 0.35
    n = int(RATE * dur)
    notes = [1200, 1500, 1800, 2200]
    sig = np.zeros(n)
    for i, f in enumerate(notes):
        offset = int(RATE * i * 0.04)
        note_n = int(RATE * 0.1)
        if offset + note_n > n:
            break
        note = _sine(f, 0.1) * _env_perc(note_n, decay_frac=0.7) * 0.3
        sig[offset:offset + note_n] += note
    # Coin rattle shimmer layer
    shimmer = _noise(n, 'white') * _env_perc(n, attack=0.01, decay_frac=0.8)
    shimmer = _bandpass(shimmer, 3000, 7000) * 0.06
    mono = _normalize(sig + shimmer)
    mono = _chorus(mono, voices=2, max_delay_ms=5, depth_ms=1.5, rate_hz=1.5)
    mono = _reverb(mono, decay=0.18, wet=0.14, room='tight')
    return _stereo(mono, width=0.45, mode='spread')


def gen_equip():
    """Equip item — metallic click + settle."""
    dur = 0.15
    n = int(RATE * dur)
    click = _noise(int(RATE * 0.01), 'white') * np.linspace(1, 0, int(RATE * 0.01)) * 0.7
    metal = _sine(1000, dur) * _env_perc(n, decay_frac=1.0) * 0.2
    combined = np.zeros(n)
    combined[:len(click)] += click
    combined[:len(metal)] += metal
    mono = _normalize(combined)
    mono = _reverb(mono, decay=0.1, wet=0.08, room='tight')
    return _stereo(mono, width=0.2, mode='haas')


def gen_buy():
    """Buy item — coin spend."""
    dur = 0.2
    n = int(RATE * dur)
    coin = _sine(1500, 0.06) * _env_perc(int(RATE * 0.06), decay_frac=0.4) * 0.4
    settle = _sine(800, dur) * _env_perc(n, decay_frac=0.8) * 0.2
    combined = np.zeros(n)
    combined[:len(coin)] += coin
    combined[:len(settle)] += settle
    mono = _normalize(combined)
    mono = _reverb(mono, decay=0.08, wet=0.06, room='tight')
    return _stereo(mono, width=0.15, mode='haas')


def gen_sell():
    """Sell item — magic coin."""
    dur = 0.2
    n = int(RATE * dur)
    coin = _sine(1800, 0.08) * _env_perc(int(RATE * 0.08), decay_frac=0.5) * 0.4
    shimmer = _sine(2200, dur) * _env_perc(n, decay_frac=1.0) * 0.1
    combined = np.zeros(n)
    combined[:len(coin)] += coin
    combined[:len(shimmer)] += shimmer
    mono = _normalize(combined)
    mono = _reverb(mono, decay=0.08, wet=0.06, room='tight')
    return _stereo(mono, width=0.15, mode='haas')


# ── EVENTS ────────────────────────────────────────────────────

def gen_portal_channel():
    """Portal channeling — dimensional tear with FM warble, KS shimmer, and formant chanting."""
    dur = 1.5
    n = int(RATE * dur)
    t = _t(dur)

    # Layer 1: FM drone — carrier sweeps up slowly, modulator creates alien warble
    fm_lo = _fm_osc(carrier_freq=80, mod_freq=55, mod_index=3.0, dur=dur)
    fm_lo *= _env_adsr(n, a=0.3, d=0.15, s=0.7, r=0.4)
    fm_lo = _formant(fm_lo, vowel='o', intensity=0.45)

    # Layer 2: Higher FM oscillator — unstable dimensional rift
    fm_hi = _fm_osc(carrier_freq=320, mod_freq=200, mod_index=1.8, dur=dur)
    fm_hi *= _env_fade_in(n, 0.5) * _env_adsr(n, a=0.4, d=0.1, s=0.5, r=0.35)
    fm_hi = _tremolo(fm_hi, rate=2.5, depth=0.4, shape='triangle')

    # Layer 3: KS metallic shimmer — portal sparks
    spark1 = _karplus_strong(1100, 0.4, brightness=0.9, damping=0.3, pluck_position=0.3)
    spark2 = _karplus_strong(1650, 0.35, brightness=0.85, damping=0.35, pluck_position=0.4)
    spark3 = _karplus_strong(2200, 0.3, brightness=0.8, damping=0.4, pluck_position=0.25)
    sparks = np.zeros(n)
    for i, sp in enumerate([spark1, spark2, spark3]):
        offset = int(RATE * (0.2 + i * 0.35))
        end = min(offset + len(sp), n)
        sparks[offset:end] += sp[:end - offset] * 0.12

    # Layer 4: Sub-bass pulse — dimensional heartbeat
    sub_pulse = _pitch_env_osc(40, dur, env_type='overshoot', amount=0.6, waveform='sine')
    sub_pulse *= _env_adsr(n, a=0.15, d=0.1, s=0.5, r=0.5)
    sub_pulse = _tremolo(sub_pulse, rate=1.5, depth=0.55)
    sub_pulse = _lowpass(sub_pulse, 120)

    # Mix layers
    combined = np.zeros(n)
    combined[:len(fm_lo)] += fm_lo * 0.30
    combined[:len(fm_hi)] += fm_hi * 0.18
    combined[:len(sparks)] += sparks
    combined[:len(sub_pulse)] += sub_pulse * 0.22

    mono = _normalize(combined)
    mono = _chorus(mono, voices=4, max_delay_ms=15, depth_ms=6, rate_hz=0.4)
    mono = _delay(mono, delay_ms=220, feedback=0.40, wet=0.30)
    mono = _conv_reverb(mono, room='cathedral', wet=0.32, decay=0.45)
    return _stereo(mono, width=0.6, mode='spread')


def gen_portal_open():
    """Portal opens — reality crack with modal shatter, FM blast, and reverse swell."""
    dur = 0.6
    n = int(RATE * dur)

    # Layer 1: Modal synthesis — crystalline shatter like glass breaking between dimensions
    shatter_modes = [
        (1200, 0.5, 0.25),   # bright fundamental
        (1900, 0.35, 0.18),  # inharmonic partial — alien
        (2750, 0.25, 0.12),  # high shimmer
        (3400, 0.15, 0.08),  # brilliance
        (680, 0.4, 0.30),    # warm body
    ]
    shatter = _modal_synthesis(shatter_modes, dur)
    shatter *= _env_perc(n, attack=0.001, decay_frac=1.5)

    # Layer 2: FM blast — the portal energy discharging
    blast = _fm_osc(carrier_freq=400, mod_freq=600, mod_index=5.0, dur=0.15)
    blast_n = len(blast)
    blast *= _env_perc(blast_n, attack=0.001, decay_frac=0.5)
    blast = _ring_mod(blast, mod_freq=250, mix=0.35)

    # Layer 3: Sub impact — massive low thud as the portal rips open
    sub = _pitch_env_osc(35, 0.2, env_type='drop', amount=2.0, waveform='sine')
    sub_n = len(sub)
    sub *= _env_perc(sub_n, attack=0.001, decay_frac=0.6) * 0.5

    # Layer 4: White noise burst — energy discharge spray
    spray_n = int(RATE * 0.08)
    spray = _noise(spray_n, 'white') * _env_perc(spray_n, attack=0.001, decay_frac=0.3)
    spray = _bandpass(spray, 1500, 8000) * 0.25

    # Layer 5: KS ring — portal edge resonance
    ring = _karplus_strong(880, 0.4, brightness=0.95, damping=0.2, pluck_position=0.15)
    ring_n = min(len(ring), n)

    # Assemble
    combined = np.zeros(n)
    combined[:len(shatter)] += shatter * 0.30
    combined[:blast_n] += blast * 0.35
    combined[:sub_n] += sub
    combined[:spray_n] += spray
    combined[:ring_n] += ring[:ring_n] * 0.15

    mono = _normalize(combined)
    mono = _bitcrush(mono, bit_depth=14, downsample=2)  # subtle grit
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.30, decay=0.35)
    return _stereo(mono, width=0.6, mode='spread')


def gen_wave_clear():
    """Wave clear — heroic KS brass fanfare with modal bell strikes and FM power chord."""
    dur = 0.75
    n = int(RATE * dur)

    # Layer 1: KS string fanfare — ascending heroic motif (C5→E5→G5→C6)
    fanfare_notes = [
        (523, 0.10, 0.0),    # C5
        (659, 0.10, 0.10),   # E5
        (784, 0.12, 0.20),   # G5
        (1047, 0.20, 0.32),  # C6 — longest, most triumphant
    ]
    fanfare = np.zeros(n)
    for freq, note_dur, offset_sec in fanfare_notes:
        offset = int(RATE * offset_sec)
        note = _karplus_strong(freq, note_dur, brightness=0.75, damping=0.3,
                               pluck_position=0.4, body_size=0.2)
        note_n = len(note)
        end = min(offset + note_n, n)
        fanfare[offset:end] += note[:end - offset] * 0.30

    # Layer 2: Modal bell strike on the final note — victory bell
    bell_modes = [
        (1047, 0.6, 0.35),   # C6 fundamental
        (2094, 0.25, 0.20),  # octave
        (2637, 0.15, 0.15),  # E7
        (3136, 0.10, 0.10),  # G7
    ]
    bell = _modal_synthesis(bell_modes, 0.4)
    bell_n = len(bell)
    bell *= _env_perc(bell_n, attack=0.001, decay_frac=1.2)
    bell_offset = int(RATE * 0.32)

    # Layer 3: FM brass swell — heroic power chord tail
    brass = _fm_osc(carrier_freq=523, mod_freq=523, mod_index=1.5, dur=0.35)
    brass += _fm_osc(carrier_freq=659, mod_freq=659, mod_index=1.2, dur=0.35) * 0.6
    brass += _fm_osc(carrier_freq=784, mod_freq=784, mod_index=1.0, dur=0.35) * 0.4
    brass_n = len(brass)
    brass *= _env_adsr(brass_n, a=0.02, d=0.05, s=0.55, r=0.15)
    brass = _formant(brass, vowel='o', intensity=0.4)
    brass_offset = int(RATE * 0.35)

    # Layer 4: Sparkle cascade — high KS plinks celebrating victory
    sparkle = np.zeros(n)
    sparkle_freqs = [2093, 2637, 3136, 3520]
    for i, sf in enumerate(sparkle_freqs):
        sp = _karplus_strong(sf, 0.12, brightness=0.95, damping=0.45, pluck_position=0.2)
        sp_offset = int(RATE * (0.40 + i * 0.06))
        sp_n = len(sp)
        end = min(sp_offset + sp_n, n)
        sparkle[sp_offset:end] += sp[:end - sp_offset] * 0.08

    # Assemble
    combined = np.zeros(n)
    combined[:n] += fanfare
    bell_end = min(bell_offset + bell_n, n)
    combined[bell_offset:bell_end] += bell[:bell_end - bell_offset] * 0.20
    brass_end = min(brass_offset + brass_n, n)
    combined[brass_offset:brass_end] += brass[:brass_end - brass_offset] * 0.22
    combined[:n] += sparkle

    mono = _normalize(combined)
    mono = _chorus(mono, voices=3, max_delay_ms=8, depth_ms=3, rate_hz=0.8)
    mono = _conv_reverb(mono, room='cathedral', wet=0.28, decay=0.35)
    return _stereo(mono, width=0.6, mode='spread')


def gen_floor_descend():
    """Floor descend — grinding stone, chain rattle, pitch-drop bass, and oppressive crypt ambience."""
    dur = 0.9
    n = int(RATE * dur)

    # Layer 1: Grinding stone — modal synthesis with descending pitch
    stone_modes = [
        (120, 0.5, 0.5),    # deep rumble
        (185, 0.35, 0.40),  # stone scrape harmonic
        (310, 0.2, 0.25),   # mid grit
        (75, 0.45, 0.6),    # sub resonance
    ]
    stone = _modal_synthesis(stone_modes, dur)
    stone *= _env_adsr(n, a=0.05, d=0.1, s=0.6, r=0.3)
    stone = _distort(stone, gain=2.0, clip=0.55)
    stone = _ring_mod(stone, mod_freq=18, mix=0.3)  # slow rhythmic grind

    # Layer 2: Pitch-drop sub bass — gut-punch descent
    sub = _pitch_env_osc(50, 0.35, env_type='drop', amount=2.5, waveform='sine')
    sub_n = len(sub)
    sub *= _env_perc(sub_n, attack=0.005, decay_frac=0.8)
    sub = _lowpass(sub, 100)

    # Layer 3: Chain rattle — fast KS metallic bursts in sequence
    chains = np.zeros(n)
    chain_times = [0.05, 0.18, 0.33, 0.50, 0.65]
    chain_freqs = [450, 380, 520, 400, 350]
    for ct, cf in zip(chain_times, chain_freqs):
        ch = _karplus_strong(cf, 0.1, brightness=0.85, damping=0.6, pluck_position=0.15)
        ch_offset = int(RATE * ct)
        ch_n = len(ch)
        end = min(ch_offset + ch_n, n)
        chains[ch_offset:end] += ch[:end - ch_offset] * 0.10

    # Layer 4: Falling debris — filtered brown noise with tremolo
    debris = _noise(n, 'brown') * _env_adsr(n, a=0.02, d=0.05, s=0.4, r=0.4)
    debris = _bandpass(debris, 60, 800)
    debris = _tremolo(debris, rate=6.0, depth=0.5, shape='triangle')

    # Layer 5: Eerie FM undertone — something lurking below
    lurk = _fm_osc(carrier_freq=45, mod_freq=30, mod_index=2.0, dur=dur)
    lurk *= _env_fade_in(n, 0.3) * _env_adsr(n, a=0.2, d=0.1, s=0.4, r=0.35)
    lurk = _lowpass(lurk, 200)

    # Assemble
    combined = np.zeros(n)
    combined[:len(stone)] += stone * 0.25
    combined[:sub_n] += sub * 0.30
    combined[:n] += chains
    combined[:len(debris)] += debris * 0.15
    combined[:len(lurk)] += lurk * 0.18

    mono = _normalize(combined)
    mono = _bitcrush(mono, bit_depth=12, downsample=3)  # gritty texture
    mono = _conv_reverb(mono, room='crypt', wet=0.35, decay=0.45)
    return _stereo(mono, width=0.45, mode='mid_side')


def gen_match_start():
    """Match start — war horn FM blast, sub impact, ascending KS arpeggios, power chord ring."""
    dur = 0.7
    n = int(RATE * dur)

    # Layer 1: War horn — FM brass with formant for organic vocal quality
    horn = _fm_osc(carrier_freq=220, mod_freq=220, mod_index=2.0, dur=0.4)
    horn += _fm_osc(carrier_freq=330, mod_freq=330, mod_index=1.5, dur=0.4) * 0.5
    horn_n = len(horn)
    horn *= _env_adsr(horn_n, a=0.015, d=0.08, s=0.6, r=0.15)
    horn = _formant(horn, vowel='o', intensity=0.5)
    horn = _resonant_sweep(horn, 250, 900, q=2.5)

    # Layer 2: Massive sub impact — the "go" signal
    sub = _pitch_env_osc(30, 0.18, env_type='drop', amount=3.0, waveform='sine')
    sub_n = len(sub)
    sub *= _env_perc(sub_n, attack=0.001, decay_frac=0.5)
    # Noise transient layered on the sub
    hit_n = int(RATE * 0.025)
    hit = _noise(hit_n, 'white') * _env_perc(hit_n, attack=0.001, decay_frac=0.2)
    hit = _bandpass(hit, 300, 4000) * 0.4

    # Layer 3: Ascending KS arpeggio — building energy
    arp = np.zeros(n)
    arp_notes = [
        (261, 0.08, 0.05),   # C4
        (329, 0.08, 0.10),   # E4
        (392, 0.08, 0.15),   # G4
        (523, 0.10, 0.20),   # C5
        (659, 0.08, 0.27),   # E5
        (784, 0.12, 0.32),   # G5
    ]
    for freq, note_dur, offset_sec in arp_notes:
        offset = int(RATE * offset_sec)
        note = _karplus_strong(freq, note_dur, brightness=0.80, damping=0.35,
                               pluck_position=0.35, body_size=0.15)
        note_len = len(note)
        end = min(offset + note_len, n)
        arp[offset:end] += note[:end - offset] * 0.15

    # Layer 4: Power chord ring — modal synthesis heroic sustain
    chord_modes = [
        (523, 0.5, 0.30),    # C5
        (784, 0.35, 0.25),   # G5
        (1047, 0.25, 0.20),  # C6
        (1319, 0.15, 0.15),  # E6
    ]
    chord = _modal_synthesis(chord_modes, 0.35)
    chord_n = len(chord)
    chord *= _env_perc(chord_n, attack=0.002, decay_frac=1.5)
    chord = _chorus(chord, voices=3, max_delay_ms=6, depth_ms=3, rate_hz=1.0)
    chord_offset = int(RATE * 0.30)

    # Assemble
    combined = np.zeros(n)
    combined[:horn_n] += horn * 0.28
    combined[:sub_n] += sub * 0.30
    combined[:hit_n] += hit
    combined[:n] += arp
    chord_end = min(chord_offset + chord_n, n)
    combined[chord_offset:chord_end] += chord[:chord_end - chord_offset] * 0.22

    mono = _normalize(combined)
    mono = _delay(mono, delay_ms=120, feedback=0.20, wet=0.15)
    mono = _conv_reverb(mono, room='cathedral', wet=0.25, decay=0.30)
    return _stereo(mono, width=0.6, mode='spread')


def gen_match_end():
    """Match end — deep bell toll, descending FM drone, and echoing metallic clang into silence."""
    dur = 0.85
    n = int(RATE * dur)

    # Layer 1: Deep bell toll — modal synthesis church bell, low and final
    bell_modes = [
        (180, 0.6, 0.50),    # deep fundamental
        (360, 0.30, 0.35),   # octave
        (540, 0.15, 0.22),   # 3rd partial
        (455, 0.20, 0.28),   # minor third — somber inharmonic
        (720, 0.10, 0.15),   # high ring
    ]
    bell = _modal_synthesis(bell_modes, dur)
    bell *= _env_perc(n, attack=0.002, decay_frac=2.0)

    # Layer 2: Descending FM drone — the finality, everything winding down
    drone = _fm_osc(carrier_freq=150, mod_freq=100, mod_index=2.5, dur=dur)
    drone *= _env_adsr(n, a=0.01, d=0.1, s=0.4, r=0.45)
    # Pitch falls over time using manual phase
    t = _t(dur)
    pitch_fall = np.sin(2 * np.pi * (150 * np.exp(-t * 1.5)) * t)
    pitch_fall *= _env_adsr(n, a=0.01, d=0.1, s=0.35, r=0.4)
    drone = drone * 0.5 + pitch_fall * 0.5
    drone = _lowpass(drone, 600)

    # Layer 3: Metallic clang — KS struck string that fades out
    clang = _karplus_strong(280, 0.5, brightness=0.7, damping=0.25,
                            pluck_position=0.2, body_size=0.3)
    clang_n = len(clang)
    clang *= _env_perc(clang_n, attack=0.001, decay_frac=1.8)
    clang = _ring_mod(clang, mod_freq=90, mix=0.25)

    # Layer 4: Fading breath — filtered noise whisper, life leaving
    breath = _noise(n, 'pink') * _env_perc(n, attack=0.05, decay_frac=2.5)
    breath = _bandpass(breath, 200, 2000)
    breath = _formant(breath, vowel='u', intensity=0.35)

    # Layer 5: Sub fade — deep finality rumble
    sub = _sine(40, dur) * _env_perc(n, decay_frac=2.0)
    sub = _lowpass(sub, 80)

    # Assemble
    combined = np.zeros(n)
    combined[:len(bell)] += bell * 0.28
    combined[:len(drone)] += drone * 0.20
    combined[:clang_n] += clang[:min(clang_n, n)] * 0.18
    combined[:len(breath)] += breath * 0.08
    combined[:len(sub)] += sub * 0.15

    mono = _normalize(combined)
    mono = _delay(mono, delay_ms=250, feedback=0.35, wet=0.25)
    mono = _conv_reverb(mono, room='crypt', wet=0.35, decay=0.45)
    return _stereo(mono, width=0.45, mode='mid_side')


# ── ENVIRONMENT ───────────────────────────────────────────────

def gen_door_open():
    """Door open — heavy creaky wood + latch click + dungeon echo."""
    dur = 0.45
    n = int(RATE * dur)
    t = _t(dur)
    # Creak = slow modulated noise with resonant character
    creak = _noise(n, 'pink') * (0.5 + 0.5 * _sine(6, dur))
    creak = _bandpass(creak, 200, 1500) * _env_adsr(n, a=0.02, d=0.05, s=0.45, r=0.2)
    creak = _resonant_sweep(creak, 300, 800, q=2.5)
    # Heavier latch mechanism
    click_n = int(RATE * 0.02)
    click = _noise(click_n, 'white') * np.linspace(1, 0, click_n) * 0.7
    # Low wood thud as door swings
    thud = _sine(90, 0.08) * _env_perc(int(RATE * 0.08), decay_frac=0.3) * 0.2
    # Hinge groan
    groan = _saw(55, 0.15) * _env_adsr(int(RATE * 0.15), a=0.02, d=0.03, s=0.3, r=0.05)
    groan = _lowpass(groan, 250) * 0.1
    combined = np.zeros(n)
    combined[:len(creak)] += creak * 0.35
    click_offset = int(RATE * 0.02)
    combined[click_offset:click_offset + click_n] += click
    combined[int(RATE * 0.04):int(RATE * 0.04) + len(thud)] += thud
    combined[int(RATE * 0.01):int(RATE * 0.01) + len(groan)] += groan
    mono = _normalize(combined)
    mono = _reverb(mono, decay=0.35, wet=0.25, room='dungeon')
    return _stereo(mono, width=0.38, mode='haas')


def gen_chest_open():
    """Chest open — heavy latch + treasure shimmer cascade."""
    dur = 0.5
    n = int(RATE * dur)
    # Heavier latch/creak
    latch_n = int(RATE * 0.03)
    latch = _noise(latch_n, 'white') * np.linspace(1, 0, latch_n) * 0.8
    # Wooden lid creak
    creak_n = int(RATE * 0.08)
    creak = _noise(creak_n, 'pink') * (0.5 + 0.5 * _sine(12, 0.08)[:creak_n])
    creak = _bandpass(creak, 400, 1800) * 0.25
    # Ascending treasure shimmer — the reward!
    shimmer_notes = [1200, 1500, 1800, 2400]
    shimmer = np.zeros(n)
    for i, f in enumerate(shimmer_notes):
        offset = int(RATE * (0.06 + i * 0.04))
        sn = int(RATE * 0.15)
        if offset + sn > n:
            break
        s = _sine(f, 0.15) * _env_perc(sn, decay_frac=0.9) * 0.2
        shimmer[offset:offset + sn] += s
    shimmer = _chorus(shimmer, voices=2, max_delay_ms=6, depth_ms=2, rate_hz=1.2)
    # Sparkle noise layer
    sparkle = _noise(n, 'white') * _env_perc(n, attack=0.05, decay_frac=1.2)
    sparkle = _highpass(sparkle, 4000) * 0.04
    combined = np.zeros(n)
    combined[:latch_n] += latch
    combined[int(RATE * 0.02):int(RATE * 0.02) + creak_n] += creak
    combined[:len(shimmer)] += shimmer
    combined[:len(sparkle)] += sparkle
    mono = _normalize(combined)
    mono = _reverb(mono, decay=0.3, wet=0.22, room='dungeon')
    return _stereo(mono, width=0.5, mode='spread')


# ── UI ────────────────────────────────────────────────────────

def gen_ui_click(variant=1):
    """UI click — short metallic tap."""
    dur = 0.06
    n = int(RATE * dur)
    freq = 1200 + variant * 300
    sig = _sine(freq, dur) * _env_perc(n, decay_frac=0.3)
    click = _noise(int(RATE * 0.005), 'white') * np.linspace(1, 0, int(RATE * 0.005)) * 0.4
    combined = np.zeros(n)
    combined[:len(sig)] += sig * 0.3
    combined[:len(click)] += click
    mono = _normalize(combined)
    mono = _reverb(mono, decay=0.06, wet=0.04, room='tight')
    return _stereo(mono, width=0.1, mode='haas')


def gen_ui_confirm(variant=1):
    """UI confirm — strong affirmative click."""
    dur = 0.1
    n = int(RATE * dur)
    s1 = _sine(800 + variant * 100, dur) * _env_perc(n, decay_frac=0.5) * 0.4
    s2 = _sine(1200 + variant * 100, 0.06) * _env_perc(int(RATE * 0.06), decay_frac=0.3) * 0.3
    combined = np.zeros(n)
    combined[:len(s1)] += s1
    combined[:len(s2)] += s2
    mono = _normalize(combined)
    mono = _reverb(mono, decay=0.06, wet=0.04, room='tight')
    return _stereo(mono, width=0.1, mode='haas')


def gen_ui_cancel():
    """UI cancel — descending denied tone."""
    dur = 0.12
    n = int(RATE * dur)
    sig = _sweep(600, 200, dur) * _env_perc(n, decay_frac=0.5)
    mono = _normalize(sig * 0.4)
    mono = _reverb(mono, decay=0.06, wet=0.04, room='tight')
    return _stereo(mono, width=0.1, mode='haas')


def gen_ui_lock():
    """UI lock — mechanical click."""
    dur = 0.08
    n = int(RATE * dur)
    click = _noise(int(RATE * 0.008), 'white') * np.linspace(1, 0, int(RATE * 0.008)) * 0.7
    metal = _sine(900, dur) * _env_perc(n, decay_frac=0.4) * 0.2
    combined = np.zeros(n)
    combined[:len(click)] += click
    combined[:len(metal)] += metal
    mono = _normalize(combined)
    mono = _reverb(mono, decay=0.06, wet=0.04, room='tight')
    return _stereo(mono, width=0.1, mode='haas')


def gen_ui_select():
    """UI select — zappy selection."""
    dur = 0.08
    n = int(RATE * dur)
    sig = _sweep(800, 2000, dur) * _env_perc(n, decay_frac=0.3)
    mono = _normalize(sig * 0.35)
    mono = _reverb(mono, decay=0.06, wet=0.04, room='tight')
    return _stereo(mono, width=0.1, mode='haas')


# ── MOVEMENT ──────────────────────────────────────────────────

def gen_step(variant='dungeon'):
    """Footstep — filtered noise thump."""
    dur = 0.1
    n = int(RATE * dur)
    step = _noise(n, 'brown') * _env_perc(n, attack=0.002, decay_frac=0.3)
    if variant == 'dungeon':
        step = _lowpass(step, 500) * 0.5
    elif variant == 'hard':
        step = _bandpass(step, 200, 2000) * 0.6
    else:
        step = _lowpass(step, 800) * 0.5
    mono = _normalize(step)
    mono = _reverb(mono, decay=0.15, wet=0.12, room='dungeon')
    return _stereo(mono, width=0.2, mode='haas')


# ── NEW DSP SHOWCASE — Karplus-Strong / Modal / Convolution ──

def gen_lute_strum():
    """Bard lute strum — cascading Karplus-Strong strings with body resonance."""
    dur = 0.8
    n = int(RATE * dur)
    # D minor chord: D3, A3, D4, F4
    notes = [(147, 0.00), (220, 0.02), (294, 0.04), (349, 0.06)]
    combined = np.zeros(n)
    for freq, delay in notes:
        s = _karplus_strong(freq, dur - delay,
                            brightness=0.55, damping=0.35,
                            pluck_position=0.4, body_size=0.6)
        offset = int(delay * RATE)
        end = min(n, offset + len(s))
        combined[offset:end] += s[:end - offset] * 0.5
    mono = _normalize(combined)
    mono = _chorus(mono, voices=2, max_delay_ms=8, depth_ms=3, rate_hz=0.6)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.22, decay=0.35)
    return _stereo(mono, width=0.5, mode='spread')


def gen_harp_heal():
    """Ethereal healing harp — bright Karplus-Strong arpeggiated chord
    through cathedral convolution reverb."""
    dur = 1.2
    n = int(RATE * dur)
    # C major arpeggio ascending: C4, E4, G4, C5, E5
    notes = [(262, 0.0), (330, 0.08), (392, 0.16), (523, 0.24), (659, 0.32)]
    combined = np.zeros(n)
    for freq, delay in notes:
        s = _karplus_strong(freq, dur - delay,
                            brightness=0.75, damping=0.25,
                            pluck_position=0.35, body_size=0.3)
        offset = int(delay * RATE)
        end = min(n, offset + len(s))
        combined[offset:end] += s[:end - offset] * 0.4
    mono = _normalize(combined)
    mono = _chorus(mono, voices=3, max_delay_ms=10, depth_ms=4, rate_hz=0.5)
    mono = _conv_reverb(mono, room='cathedral', wet=0.35, decay=0.5)
    return _stereo(mono, width=0.6, mode='spread')


def gen_sword_draw():
    """Sword unsheathing — metallic Karplus-Strong ring + noise scrape."""
    dur = 0.4
    n = int(RATE * dur)
    # High metallic string ring (very bright, short)
    ring = _karplus_strong(1800, dur, brightness=0.95, damping=0.6,
                           pluck_position=0.2, body_size=0.0)
    ring *= _env_perc(n, attack=0.002, decay_frac=1.2) * 0.5
    # Secondary lower ring
    ring2 = _karplus_strong(900, dur, brightness=0.85, damping=0.55,
                            pluck_position=0.3, body_size=0.0)
    ring2 *= _env_perc(n, attack=0.005, decay_frac=0.8) * 0.25
    # Scraping noise — bandpassed with sweep for movement feel
    scrape = _noise(n, 'white') * _env_perc(n, attack=0.002, decay_frac=0.5)
    scrape = _resonant_sweep(scrape, 2000, 5000, q=3.0)
    scrape *= 0.2
    mono = _normalize(_mix(ring, ring2, scrape))
    mono = _conv_reverb(mono, room='metal_room', wet=0.18, decay=0.2)
    return _stereo(mono, width=0.4, mode='haas')


def gen_shield_clang():
    """Heavy shield impact — modal synthesis metallic body + noise transient."""
    dur = 0.5
    n = int(RATE * dur)
    # Shield modal frequencies — inharmonic, like a struck metal disc
    modes = [
        (340, 1.0, 0.20),    # Fundamental — low, heavy
        (940, 0.65, 0.12),   # Mode 2 — bright ring
        (1836, 0.40, 0.08),  # Mode 3 — high shimmer
        (3040, 0.18, 0.05),  # Mode 4 — air
    ]
    body = _modal_synthesis(modes, dur)
    body *= _env_perc(n, attack=0.001, decay_frac=2.0)
    # Impact transient — short crunchy noise burst
    trans_n = int(RATE * 0.015)
    transient = _noise(trans_n, 'white') * np.linspace(1, 0, trans_n)
    transient = _bandpass(transient, 400, 5000)
    # Sub thud for weight
    sub = _pitch_env_osc(55, dur, env_type='drop', amount=1.5)
    sub *= _env_perc(n, decay_frac=0.4) * 0.35
    combined = np.zeros(n)
    combined[:len(body)] += body * 0.6
    combined[:trans_n] += transient * 0.8
    combined[:len(sub)] += sub
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.2, decay=0.25)
    return _stereo(mono, width=0.35, mode='haas')


def gen_anvil_strike():
    """Blacksmith anvil — extremely bright modal strike with long ring."""
    dur = 0.7
    n = int(RATE * dur)
    # Anvil modes — very inharmonic, bright, long-ringing steel
    modes = [
        (750, 1.0, 0.35),
        (2073, 0.7, 0.25),
        (4050, 0.45, 0.18),
        (6698, 0.20, 0.10),
        (9000, 0.08, 0.06),
    ]
    body = _modal_synthesis(modes, dur)
    body *= _env_perc(n, attack=0.001, decay_frac=3.0)
    # Hammer impact noise
    impact = _noise(int(RATE * 0.012), 'white')
    impact *= np.linspace(1, 0, len(impact))
    impact = _bandpass(impact, 500, 8000)
    # Sub thump from the mass of the hammer
    sub = _sine(80, 0.1) * _env_perc(int(RATE * 0.1), decay_frac=0.3) * 0.3
    combined = np.zeros(n)
    combined[:len(body)] += body * 0.5
    combined[:len(impact)] += impact * 0.9
    combined[:len(sub)] += sub
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='metal_room', wet=0.22, decay=0.3)
    return _stereo(mono, width=0.4, mode='haas')


def gen_bell_toll():
    """Deep dungeon bell — modal synthesis with cathedral reverb.
    Ominous, foreboding atmosphere."""
    dur = 2.0
    n = int(RATE * dur)
    # Church bell modes (based on typical minor-third bell tuning)
    fund = 220
    modes = [
        (fund * 0.5,  0.4, 1.5),   # Hum tone (octave below)
        (fund,        1.0, 1.2),   # Fundamental
        (fund * 1.2,  0.55, 0.9),  # Minor third
        (fund * 1.5,  0.40, 0.7),  # Fifth
        (fund * 2.0,  0.30, 0.5),  # Octave
        (fund * 2.52, 0.15, 0.3),  # Upper partial
        (fund * 3.0,  0.08, 0.2),  # High ring
    ]
    bell = _modal_synthesis(modes, dur)
    bell *= _env_perc(n, attack=0.003, decay_frac=4.0)
    # Tremolo adds the beating/warble real bells have
    bell = _tremolo(bell, rate=2.5, depth=0.15, shape='sine')
    # Gentle clapper click at the very start
    click_n = int(RATE * 0.008)
    click = _noise(click_n, 'white') * np.linspace(1, 0, click_n) * 0.4
    combined = np.zeros(n)
    combined[:len(bell)] += bell * 0.6
    combined[:click_n] += click
    mono = _normalize(combined)
    mono = _conv_reverb(mono, room='cathedral', wet=0.4, decay=0.6)
    return _stereo(mono, width=0.55, mode='spread')


def gen_crypt_whisper():
    """Crypt whisper — noise formant-filtered through crypt reverb.
    Ghostly ambient texture."""
    dur = 1.5
    n = int(RATE * dur)
    # Breathy noise with formant filtering for ghostly vocal quality
    breath = _noise(n, 'pink') * _env_adsr(n, a=0.3, d=0.2, s=0.3, r=0.5)
    breath = _formant(breath, vowel='u', intensity=0.7)
    # Slow pitch-shifting sub drone
    drone = _sine(65, dur) * _env_adsr(n, a=0.4, d=0.2, s=0.25, r=0.4)
    drone *= (1 + 0.2 * _sine(0.5, dur))
    # Ghost shimmer — detuned high strings
    shimmer = _karplus_strong(2200, dur, brightness=0.3, damping=0.15,
                              pluck_position=0.5, body_size=0.0) * 0.08
    mono = _normalize(_mix(breath * 0.4, drone * 0.3, shimmer))
    mono = _chorus(mono, voices=3, max_delay_ms=15, depth_ms=6, rate_hz=0.3)
    mono = _conv_reverb(mono, room='crypt', wet=0.45, decay=0.5)
    return _stereo(mono, width=0.6, mode='spread')


def gen_sword_hit_pro():
    """Pro sword slash — layered KS metallic ring + modal body + noise impact.
    The upgraded version of melee_hit using all new DSP."""
    dur = 0.3
    n = int(RATE * dur)
    # Layer 1: Impact transient (noise burst, tight)
    trans = _noise(n, 'white') * _env_perc(n, attack=0.001, decay_frac=0.6)
    trans = _bandpass(trans, 300, 3500) * 0.5
    # Layer 2: Metallic ring (modal — sword blade vibration)
    blade_modes = [
        (1200, 1.0, 0.08),
        (3312, 0.5, 0.05),
        (5600, 0.2, 0.03),
    ]
    blade = _modal_synthesis(blade_modes, dur)
    blade *= _env_perc(n, attack=0.001, decay_frac=1.5) * 0.3
    # Layer 3: Sub-bass thud (the weight of the blow)
    sub = _pitch_env_osc(55, dur, env_type='drop', amount=1.8)
    sub *= _env_perc(n, decay_frac=0.5) * 0.4
    # Layer 4: KS string snap (adds a physical "cut" character)
    snap = _karplus_strong(800, 0.1, brightness=0.9, damping=0.7,
                           pluck_position=0.15, body_size=0.0)
    mono = _normalize(_mix(trans, blade, sub, snap * 0.2))
    mono = _conv_reverb(mono, room='stone_chamber', wet=0.15, decay=0.2)
    return _stereo(mono, width=0.35, mode='haas')


# ═══════════════════════════════════════════════════════════════
# Master build table — maps sound key → generator
# ═══════════════════════════════════════════════════════════════

def build_sound_table():
    """Returns a list of dicts: {key, category, filename, generator, description}."""
    sounds = []

    def add(key, cat, filename, gen_fn, desc):
        sounds.append({
            'key': key,
            'category': cat,
            'filename': filename,
            'generator': gen_fn,
            'description': desc,
        })

    # ── Combat variants ──
    for i in range(1, 10):
        add(f'melee_hit_{i}', 'combat', f'melee-hit_{i}.wav',
            lambda v=i: gen_melee_hit(v), f'Melee hit variant {i}')
    add('melee_hit_retro', 'combat', 'melee-hit_retro.wav',
        lambda: (lambda s: np.array([_normalize(_distort(s[0], 4.0, 0.5)), _normalize(_distort(s[1], 4.0, 0.5))]))(gen_melee_hit(1)),
        'Retro bit-crush melee hit')
    for i in range(1, 3):
        suffix = '' if i == 1 else f'_{i}'
        add(f'melee_crit{suffix}', 'combat', f'melee-crit_{i}.wav',
            lambda v=i: gen_melee_crit(v), f'Melee critical hit {i}')
    for i in range(1, 7):
        add(f'ranged_hit_{i}', 'combat', f'ranged-hit_{i}.wav',
            lambda v=i: gen_ranged_hit(v), f'Ranged hit variant {i}')
    for i in range(1, 5):
        add(f'miss_{i}', 'combat', f'miss_{i}.wav',
            lambda v=i: gen_miss(v), f'Miss whoosh variant {i}')
    add('dodge', 'combat', 'dodge.wav', gen_dodge, 'Dodge / evade')
    for i in range(1, 8):
        add(f'block_{i}', 'combat', f'block_{i}.wav',
            lambda v=i: gen_block(v), f'Block clang variant {i}')
    for i in range(1, 6):
        add(f'death_{i}', 'combat', f'death_{i}.wav',
            lambda v=i: gen_death(v), f'Death collapse variant {i}')
    for i in range(1, 3):
        add(f'stun_hit{"" if i == 1 else "_2"}', 'combat', f'stun-hit_{i}.wav',
            lambda v=i: gen_stun_hit(v), f'Stun impact {i}')
    add('stun_locked', 'combat', 'stun-locked.wav', gen_stun_locked, 'Stun turn-locked warble')

    # ── Skills — generic casts ──
    add('skill_cast', 'skills', 'cast_generic.wav', gen_skill_cast, 'Generic skill activation')
    add('skill_cast_energy', 'skills', 'cast_energy.wav', gen_skill_cast_energy, 'Energy riser cast')
    add('skill_cast_dark', 'skills', 'cast_dark.wav', gen_skill_cast_dark, 'Dark hollow spell cast')
    add('skill_cast_power', 'skills', 'cast_power.wav', gen_skill_cast_power, 'Powerful energy blast')
    add('skill_cast_sphere', 'skills', 'cast_sphere.wav', gen_skill_cast_sphere, 'Sphere rising cast')

    # ── Skills — per-class ──
    add('skill_taunt', 'skills', 'taunt.wav', gen_taunt, 'Crusader — Taunt')
    add('skill_shield_bash', 'skills', 'shield-bash.wav', gen_shield_bash, 'Crusader — Shield Bash')
    add('skill_holy_ground', 'skills', 'holy-ground.wav', gen_holy_ground, 'Crusader — Holy Ground')
    add('skill_bulwark', 'skills', 'bulwark.wav', gen_bulwark, 'Crusader — Bulwark')
    add('skill_power_shot', 'skills', 'power-shot.wav', gen_power_shot, 'Ranger — Power Shot')
    add('skill_volley', 'skills', 'volley.wav', gen_volley, 'Ranger — Volley')
    add('skill_evasion', 'skills', 'evasion.wav', gen_evasion, 'Ranger — Evasion')
    add('skill_crippling_shot', 'skills', 'crippling-shot.wav', gen_crippling_shot, 'Ranger — Crippling Shot')
    add('skill_heal', 'skills', 'heal.wav', gen_skill_heal, 'Confessor — Heal')
    add('skill_rebuke', 'skills', 'rebuke.wav', gen_rebuke, 'Confessor — Rebuke')
    add('skill_exorcism', 'skills', 'exorcism.wav', gen_exorcism, 'Confessor — Exorcism')
    add('skill_prayer', 'skills', 'prayer.wav', gen_prayer, 'Confessor — Prayer')
    add('skill_shield_of_faith', 'skills', 'shield-of-faith.wav', gen_shield_of_faith, 'Confessor — Shield of Faith')
    add('skill_divine_sense', 'skills', 'divine-sense.wav', gen_divine_sense, 'Inquisitor — Divine Sense')
    add('skill_shadow_step', 'skills', 'shadow-step.wav', gen_shadow_step, 'Hexblade — Shadow Step')
    add('skill_wither', 'skills', 'wither.wav', gen_wither, 'Hexblade — Wither')
    add('skill_ward', 'skills', 'ward.wav', gen_ward, 'Hexblade — Ward')
    add('skill_soul_reap', 'skills', 'soul-reap.wav', gen_soul_reap, 'Hexblade — Soul Reap')
    add('skill_venom_gaze', 'skills', 'venom-gaze.wav', gen_venom_gaze, 'Inquisitor — Venom Gaze')
    add('skill_war_cry', 'skills', 'war-cry.wav', gen_war_cry, 'Bard — War Cry')
    add('skill_double_strike', 'skills', 'double-strike.wav', gen_double_strike, 'Double Strike')
    add('skill_ballad_of_might', 'skills', 'ballad-of-might.wav', gen_ballad_of_might, 'Bard — Ballad of Might')
    add('skill_dirge_of_weakness', 'skills', 'dirge-of-weakness.wav', gen_dirge_of_weakness, 'Bard — Dirge of Weakness')
    add('skill_war_hymn', 'skills', 'war-hymn.wav', gen_war_hymn, 'Bard — War Hymn')
    add('skill_cacophony', 'skills', 'cacophony.wav', gen_cacophony, 'Bard — Cacophony')
    add('skill_blood_strike', 'skills', 'blood-strike.wav', gen_blood_strike, 'Blood Knight — Blood Strike')
    add('skill_crimson_veil', 'skills', 'crimson-veil.wav', gen_crimson_veil, 'Blood Knight — Crimson Veil')
    add('skill_sanguine_burst', 'skills', 'sanguine-burst.wav', gen_sanguine_burst, 'Blood Knight — Sanguine Burst')
    add('skill_blood_frenzy', 'skills', 'blood-frenzy.wav', gen_blood_frenzy, 'Blood Knight — Blood Frenzy')
    add('skill_miasma', 'skills', 'miasma.wav', gen_miasma, 'Plague Doctor — Miasma')
    add('skill_plague_flask', 'skills', 'plague-flask.wav', gen_plague_flask, 'Plague Doctor — Plague Flask')
    add('skill_enfeeble', 'skills', 'enfeeble.wav', gen_enfeeble, 'Plague Doctor — Enfeeble')
    add('skill_inoculate', 'skills', 'inoculate.wav', gen_inoculate, 'Plague Doctor — Inoculate')
    add('skill_grasp_of_the_grave', 'skills', 'grasp-of-the-grave.wav', gen_grasp_of_the_grave, 'Revenant — Grasp of the Grave')
    add('skill_deaths_embrace', 'skills', 'deaths-embrace.wav', gen_deaths_embrace, 'Revenant — Death\'s Embrace')
    add('skill_undying_fury', 'skills', 'undying-fury.wav', gen_undying_fury, 'Revenant — Undying Fury (cast)')
    add('skill_undying_fury_trigger', 'skills', 'undying-fury-trigger.wav', gen_undying_fury_trigger, 'Revenant — Undying Fury (trigger)')
    add('skill_soul_rend', 'skills', 'soul-rend.wav', gen_soul_rend, 'Revenant — Soul Rend')
    add('skill_soul_rend_empowered', 'skills', 'soul-rend-empowered.wav', gen_soul_rend_empowered, 'Revenant — Soul Rend (empowered)')
    add('skill_healing_totem', 'skills', 'healing-totem.wav', gen_healing_totem, 'Shaman — Healing Totem')
    add('skill_searing_totem', 'skills', 'searing-totem.wav', gen_searing_totem, 'Shaman — Searing Totem')
    add('skill_soul_anchor', 'skills', 'soul-anchor.wav', gen_soul_anchor, 'Shaman — Soul Anchor')
    add('skill_soul_anchor_save', 'skills', 'soul-anchor-save.wav', gen_soul_anchor_save, 'Shaman — Soul Anchor Save')
    add('skill_earthgrasp', 'skills', 'earthgrasp.wav', gen_earthgrasp, 'Shaman — Earthgrasp')

    # ── Buffs / Debuffs ──
    add('heal', 'buffs', 'heal.wav', gen_heal, 'Generic heal chime')
    add('heal_alt', 'buffs', 'heal-alt.wav', gen_heal_alt, 'Healing gusts')
    add('buff_apply', 'buffs', 'buff-apply.wav', gen_buff_apply, 'Generic buff apply')
    add('buff_shimmer', 'buffs', 'buff-shimmer.wav', gen_buff_shimmer, 'Buff shimmer sparkle')
    add('buff_stats', 'buffs', 'buff-stats.wav', gen_buff_stats, 'Stats-up power chord')
    add('buff_vigor', 'buffs', 'buff-vigor.wav', gen_buff_vigor, 'Invigoration buzz')
    add('regen', 'buffs', 'regen.wav', gen_regen, 'Regen tick')
    add('debuff_enemy', 'buffs', 'debuff-enemy.wav', gen_debuff_enemy, 'Enemy debuff')
    add('debuff_speed', 'buffs', 'debuff-speed.wav', gen_debuff_speed, 'Speed debuff warble')
    add('wither_tick', 'buffs', 'wither-tick.wav', gen_wither_tick, 'Wither DoT tick')
    add('healing_totem_tick', 'buffs', 'healing-totem-tick.wav', gen_healing_totem_tick, 'Healing totem pulse')

    # ── Items ──
    add('potion_use', 'items', 'potion-use.wav', gen_potion_use, 'Potion consume')
    add('loot_pickup', 'items', 'loot-pickup.wav', gen_loot_pickup, 'Loot / coin pickup')
    add('ui_equip', 'items', 'equip.wav', gen_equip, 'Equip item')
    add('ui_buy', 'items', 'buy.wav', gen_buy, 'Buy from merchant')
    add('ui_sell', 'items', 'sell.wav', gen_sell, 'Sell to merchant')

    # ── Events ──
    add('portal_channel', 'events', 'portal-channel.wav', gen_portal_channel, 'Portal channeling')
    add('portal_open', 'events', 'portal-open.wav', gen_portal_open, 'Portal opens')
    add('wave_clear', 'events', 'wave-clear.wav', gen_wave_clear, 'Wave cleared fanfare')
    add('floor_descend', 'events', 'floor-descend.wav', gen_floor_descend, 'Floor descend rumble')
    add('match_start', 'events', 'match-start.wav', gen_match_start, 'Match start stinger')
    add('match_end', 'events', 'match-end.wav', gen_match_end, 'Match end decay')

    # ── Environment ──
    add('door_open', 'events', 'door-open.wav', gen_door_open, 'Door opens')
    add('chest_open', 'events', 'chest-open.wav', gen_chest_open, 'Chest opens')

    # ── UI ──
    for i in range(1, 6):
        add(f'ui_click_{i}', 'ui', f'click_{i}.wav',
            lambda v=i: gen_ui_click(v), f'UI click variant {i}')
    add('ui_confirm', 'ui', 'confirm.wav', lambda: gen_ui_confirm(1), 'UI confirm click')
    add('ui_confirm_2', 'ui', 'confirm-alt.wav', lambda: gen_ui_confirm(2), 'UI confirm alt')
    add('ui_cancel', 'ui', 'cancel.wav', gen_ui_cancel, 'UI cancel / denied')
    add('ui_lock', 'ui', 'lock.wav', gen_ui_lock, 'UI lock click')
    add('ui_select', 'ui', 'select.wav', gen_ui_select, 'UI select zap')

    # ── Movement ──
    add('step_dungeon', 'movement', 'step-dungeon.wav',
        lambda: gen_step('dungeon'), 'Footstep — dungeon')
    add('step_generic', 'movement', 'step-generic.wav',
        lambda: gen_step('generic'), 'Footstep — generic')
    add('step_hard', 'movement', 'step-hard.wav',
        lambda: gen_step('hard'), 'Footstep — hard surface')

    # ── DSP Showcase (new tools test) ──
    add('lute_strum', 'showcase', 'lute-strum.wav', gen_lute_strum,
        'Bard lute strum — Karplus-Strong + stone_chamber reverb')
    add('harp_heal', 'showcase', 'harp-heal.wav', gen_harp_heal,
        'Ethereal healing harp — Karplus-Strong + cathedral reverb')
    add('sword_draw', 'showcase', 'sword-draw.wav', gen_sword_draw,
        'Sword unsheathe — metallic KS ring + noise scrape')
    add('shield_clang', 'showcase', 'shield-clang.wav', gen_shield_clang,
        'Shield impact — modal synthesis + noise transient')
    add('anvil_strike', 'showcase', 'anvil-strike.wav', gen_anvil_strike,
        'Blacksmith anvil — bright modal strike + hammer noise')
    add('bell_toll', 'showcase', 'bell-toll.wav', gen_bell_toll,
        'Dungeon bell — modal synthesis + cathedral reverb')
    add('crypt_whisper', 'showcase', 'crypt-whisper.wav', gen_crypt_whisper,
        'Ghostly crypt whisper — formant noise + KS shimmer + crypt reverb')
    add('sword_hit_pro', 'showcase', 'sword-hit-pro.wav', gen_sword_hit_pro,
        'Pro sword slash — KS + modal + noise layered')

    return sounds


# ═══════════════════════════════════════════════════════════════
# Parameterized Template System — Sound Editor support
# ═══════════════════════════════════════════════════════════════
# Templates let the UI offer editable knobs per sound. Each
# template is a fully-parameterized generator that covers an
# archetype (impact, sweep, chord, …). Every existing sound
# key is mapped to a template + default params that approximate
# its original bespoke generator output.
# ═══════════════════════════════════════════════════════════════

# ── Common post-processing params (all templates) ─────────

COMMON_PARAM_SCHEMA = {
    'reverb_decay':  {'default': 0.25, 'min': 0.0, 'max': 0.8, 'step': 0.05, 'label': 'Reverb Decay'},
    'reverb_wet':    {'default': 0.2,  'min': 0.0, 'max': 0.5, 'step': 0.02, 'label': 'Reverb Mix'},
    'reverb_room':   {'default': 'dungeon', 'options': ['dungeon', 'hall', 'tight', 'stone_chamber', 'cathedral', 'metal_room', 'crypt'], 'label': 'Reverb Room'},
    'stereo_width':  {'default': 0.4, 'min': 0.0, 'max': 1.0, 'step': 0.05, 'label': 'Stereo Width'},
    'stereo_mode':   {'default': 'haas', 'options': ['haas', 'spread', 'mid_side'], 'label': 'Stereo Mode'},
    'chorus_voices': {'default': 0, 'min': 0, 'max': 5, 'step': 1, 'label': 'Chorus Voices'},
    'chorus_depth':  {'default': 3.0, 'min': 0.5, 'max': 10.0, 'step': 0.5, 'label': 'Chorus Depth'},
    'chorus_rate':   {'default': 1.2, 'min': 0.2, 'max': 5.0, 'step': 0.1, 'label': 'Chorus Rate'},
    'tremolo_rate':  {'default': 0.0, 'min': 0.0, 'max': 20.0, 'step': 0.5, 'label': 'Tremolo Rate'},
    'tremolo_depth': {'default': 0.5, 'min': 0.0, 'max': 1.0, 'step': 0.05, 'label': 'Tremolo Depth'},
    'delay_ms':      {'default': 0,   'min': 0,   'max': 500, 'step': 10, 'label': 'Delay Time (ms)'},
    'delay_feedback': {'default': 0.3, 'min': 0.0, 'max': 0.8, 'step': 0.05, 'label': 'Delay Feedback'},
    'delay_wet':     {'default': 0.25, 'min': 0.0, 'max': 0.6, 'step': 0.02, 'label': 'Delay Mix'},
    'bitcrush_depth': {'default': 0, 'min': 0, 'max': 16, 'step': 1, 'label': 'Bitcrush Depth'},
    'bitcrush_downsample': {'default': 1, 'min': 1, 'max': 16, 'step': 1, 'label': 'Bitcrush Downsample'},
}

# ── Template definitions ──────────────────────────────────

TEMPLATE_SCHEMAS = {
    'impact': {
        'label': 'Impact / Hit',
        'description': 'Noise burst with sub-bass thud. Good for melee hits, blocks, stuns.',
        'params': {
            'duration':        {'default': 0.2,   'min': 0.05, 'max': 0.8, 'step': 0.01, 'label': 'Duration (s)'},
            'noise_color':     {'default': 'white', 'options': ['white', 'pink', 'brown'], 'label': 'Noise Color'},
            'body_freq_low':   {'default': 200,   'min': 50,  'max': 2000, 'step': 10,  'label': 'Body Low Freq'},
            'body_freq_high':  {'default': 3000,  'min': 500, 'max': 8000, 'step': 100, 'label': 'Body High Freq'},
            'sub_freq':        {'default': 60,    'min': 30,  'max': 200,  'step': 5,   'label': 'Sub Frequency'},
            'sub_level':       {'default': 0.5,   'min': 0.0, 'max': 1.0,  'step': 0.05, 'label': 'Sub Level'},
            'click_level':     {'default': 0.8,   'min': 0.0, 'max': 1.0,  'step': 0.05, 'label': 'Transient Click'},
            'attack':          {'default': 0.002, 'min': 0.001, 'max': 0.05, 'step': 0.001, 'label': 'Attack'},
            'decay_frac':      {'default': 1.2,   'min': 0.2, 'max': 3.0,  'step': 0.1,  'label': 'Decay'},
            'distortion_gain': {'default': 0.0,   'min': 0.0, 'max': 8.0,  'step': 0.1,  'label': 'Distortion'},
            'distortion_clip': {'default': 0.7,   'min': 0.1, 'max': 1.0,  'step': 0.05, 'label': 'Clip Level'},
            'pitch_env':       {'default': 'none', 'options': ['none', 'drop', 'rise', 'overshoot'], 'label': 'Sub Pitch Env'},
            'pitch_env_amt':   {'default': 1.0,   'min': 0.0, 'max': 5.0,  'step': 0.1,  'label': 'Pitch Env Amount'},
            'ring_mod_freq':   {'default': 0,     'min': 0,   'max': 2000, 'step': 10,   'label': 'Ring Mod Freq'},
            'ring_mod_mix':    {'default': 0.3,   'min': 0.0, 'max': 1.0,  'step': 0.05, 'label': 'Ring Mod Mix'},
        },
    },
    'sweep': {
        'label': 'Frequency Sweep',
        'description': 'Sine sweep with optional resonance. Good for casts, whooshes, risers.',
        'params': {
            'duration':        {'default': 0.35, 'min': 0.1,  'max': 2.0, 'step': 0.01, 'label': 'Duration (s)'},
            'freq_start':      {'default': 200,  'min': 30,   'max': 5000, 'step': 10,  'label': 'Start Freq'},
            'freq_end':        {'default': 800,  'min': 30,   'max': 5000, 'step': 10,  'label': 'End Freq'},
            'resonance_q':     {'default': 3.5,  'min': 1.0,  'max': 10.0, 'step': 0.5, 'label': 'Resonance Q'},
            'use_resonance':   {'default': True, 'options': [True, False], 'label': 'Resonant Filter'},
            'shimmer_freq':    {'default': 0,    'min': 0,    'max': 5000, 'step': 50,  'label': 'Shimmer Freq'},
            'shimmer_level':   {'default': 0.15, 'min': 0.0,  'max': 0.5,  'step': 0.02, 'label': 'Shimmer Level'},
            'env_attack':      {'default': 0.02, 'min': 0.005, 'max': 0.2, 'step': 0.005, 'label': 'Env Attack'},
            'env_sustain':     {'default': 0.7,  'min': 0.1,  'max': 1.0,  'step': 0.05, 'label': 'Env Sustain'},
            'env_release':     {'default': 0.15, 'min': 0.01, 'max': 0.5,  'step': 0.01, 'label': 'Env Release'},
            'distortion_gain': {'default': 0.0,  'min': 0.0,  'max': 5.0,  'step': 0.1,  'label': 'Distortion'},
            'ring_mod_freq':   {'default': 0,    'min': 0,    'max': 2000, 'step': 10,   'label': 'Ring Mod Freq'},
            'ring_mod_mix':    {'default': 0.3,  'min': 0.0,  'max': 1.0,  'step': 0.05, 'label': 'Ring Mod Mix'},
            'pitch_env':       {'default': 'none', 'options': ['none', 'drop', 'rise', 'overshoot'], 'label': 'Pitch Envelope'},
            'pitch_env_amt':   {'default': 1.0,  'min': 0.0,  'max': 5.0,  'step': 0.1,  'label': 'Pitch Env Amount'},
        },
    },
    'chord': {
        'label': 'Chord / Tonal',
        'description': 'Harmonic tones forming a chord. Good for heals, buffs, holy effects.',
        'params': {
            'duration':          {'default': 0.5,    'min': 0.1,  'max': 2.0, 'step': 0.01, 'label': 'Duration (s)'},
            'root_freq':         {'default': 523,    'min': 100,  'max': 2000, 'step': 1,   'label': 'Root Frequency'},
            'interval_2':        {'default': 1.26,   'min': 1.0,  'max': 2.0,  'step': 0.01, 'label': 'Interval 2 Ratio'},
            'interval_3':        {'default': 1.50,   'min': 1.0,  'max': 2.0,  'step': 0.01, 'label': 'Interval 3 Ratio'},
            'level_2':           {'default': 0.7,    'min': 0.0,  'max': 1.0,  'step': 0.05, 'label': 'Voice 2 Level'},
            'level_3':           {'default': 0.5,    'min': 0.0,  'max': 1.0,  'step': 0.05, 'label': 'Voice 3 Level'},
            'env_attack':        {'default': 0.05,   'min': 0.01, 'max': 0.3,  'step': 0.01, 'label': 'Attack'},
            'env_sustain':       {'default': 0.5,    'min': 0.1,  'max': 1.0,  'step': 0.05, 'label': 'Sustain'},
            'env_release':       {'default': 0.25,   'min': 0.01, 'max': 0.5,  'step': 0.01, 'label': 'Release'},
            'shimmer':           {'default': 0.05,   'min': 0.0,  'max': 0.2,  'step': 0.01, 'label': 'Air / Shimmer'},
            'formant_vowel':     {'default': 'none', 'options': ['none', 'a', 'e', 'i', 'o', 'u'], 'label': 'Formant Vowel'},
            'formant_intensity': {'default': 0.5,    'min': 0.0,  'max': 1.0,  'step': 0.05, 'label': 'Formant Intensity'},
        },
    },
    'arpeggio': {
        'label': 'Arpeggio / Sequence',
        'description': 'Sequence of notes played in order. Good for fanfares, jingles, UI cues.',
        'params': {
            'note_1':        {'default': 523,    'min': 100, 'max': 3000, 'step': 1, 'label': 'Note 1 Freq'},
            'note_2':        {'default': 659,    'min': 100, 'max': 3000, 'step': 1, 'label': 'Note 2 Freq'},
            'note_3':        {'default': 784,    'min': 0,   'max': 3000, 'step': 1, 'label': 'Note 3 Freq'},
            'note_4':        {'default': 0,      'min': 0,   'max': 3000, 'step': 1, 'label': 'Note 4 Freq'},
            'note_duration': {'default': 0.1,    'min': 0.03, 'max': 0.5, 'step': 0.01, 'label': 'Note Duration'},
            'gap_duration':  {'default': 0.0,    'min': 0.0, 'max': 0.1, 'step': 0.005, 'label': 'Gap Between Notes'},
            'waveform':      {'default': 'sine', 'options': ['sine', 'saw', 'square', 'plucked'], 'label': 'Waveform'},
            'decay_frac':    {'default': 0.6,    'min': 0.2, 'max': 2.0, 'step': 0.1, 'label': 'Note Decay'},
        },
    },
    'noise_texture': {
        'label': 'Noise Texture',
        'description': 'Filtered noise with envelope shaping. Good for whooshes, gas, ambience.',
        'params': {
            'duration':         {'default': 0.3,    'min': 0.05, 'max': 2.0, 'step': 0.01, 'label': 'Duration (s)'},
            'noise_color':      {'default': 'pink',  'options': ['white', 'pink', 'brown'], 'label': 'Noise Color'},
            'filter_low':       {'default': 200,     'min': 20,  'max': 5000, 'step': 10, 'label': 'Filter Low'},
            'filter_high':      {'default': 3000,    'min': 200, 'max': 10000, 'step': 100, 'label': 'Filter High'},
            'env_attack':       {'default': 0.02,    'min': 0.005, 'max': 0.3, 'step': 0.005, 'label': 'Attack'},
            'decay_frac':       {'default': 1.0,     'min': 0.2, 'max': 3.0, 'step': 0.1, 'label': 'Decay'},
            'secondary_layer':  {'default': False,   'options': [True, False], 'label': 'Secondary Layer'},
            'secondary_color':  {'default': 'brown', 'options': ['white', 'pink', 'brown'], 'label': '2nd Noise Color'},
            'secondary_cutoff': {'default': 300,     'min': 50, 'max': 2000, 'step': 10, 'label': '2nd Cutoff'},
            'secondary_level':  {'default': 0.3,     'min': 0.0, 'max': 1.0, 'step': 0.05, 'label': '2nd Level'},
        },
    },
    'drone': {
        'label': 'Drone / Sustained',
        'description': 'Sustained oscillator with modulation. Good for buffs, debuffs, warbles.',
        'params': {
            'duration':          {'default': 0.4,    'min': 0.1,  'max': 2.0, 'step': 0.01, 'label': 'Duration (s)'},
            'base_freq':         {'default': 200,    'min': 30,   'max': 1000, 'step': 5,  'label': 'Base Frequency'},
            'waveform':          {'default': 'sine', 'options': ['sine', 'saw', 'square', 'plucked'], 'label': 'Waveform'},
            'mod_freq':          {'default': 5.0,    'min': 0.5,  'max': 30.0, 'step': 0.5, 'label': 'Modulation Freq'},
            'mod_depth':         {'default': 0.3,    'min': 0.0,  'max': 1.0, 'step': 0.05, 'label': 'Mod Depth'},
            'filter_cutoff':     {'default': 500,    'min': 50,   'max': 5000, 'step': 50, 'label': 'Filter Cutoff'},
            'env_attack':        {'default': 0.05,   'min': 0.01, 'max': 0.3, 'step': 0.01, 'label': 'Attack'},
            'env_sustain':       {'default': 0.5,    'min': 0.1,  'max': 1.0, 'step': 0.05, 'label': 'Sustain'},
            'env_release':       {'default': 0.2,    'min': 0.01, 'max': 0.5, 'step': 0.01, 'label': 'Release'},
            'formant_vowel':     {'default': 'none', 'options': ['none', 'a', 'e', 'i', 'o', 'u'], 'label': 'Formant Vowel'},
            'formant_intensity': {'default': 0.5,    'min': 0.0,  'max': 1.0, 'step': 0.05, 'label': 'Formant Intensity'},
            'ring_mod_freq':     {'default': 0,      'min': 0,    'max': 2000, 'step': 10,   'label': 'Ring Mod Freq'},
            'ring_mod_mix':      {'default': 0.3,    'min': 0.0,  'max': 1.0,  'step': 0.05, 'label': 'Ring Mod Mix'},
        },
    },
    'tonal_hit': {
        'label': 'Tonal Hit / Ring',
        'description': 'Tonal elements with percussive decay. Good for metal clangs, chimes, pings.',
        'params': {
            'duration':     {'default': 0.2,  'min': 0.05, 'max': 0.8, 'step': 0.01, 'label': 'Duration (s)'},
            'freq_1':       {'default': 800,  'min': 100,  'max': 5000, 'step': 10, 'label': 'Frequency 1'},
            'freq_2':       {'default': 1600, 'min': 0,    'max': 5000, 'step': 10, 'label': 'Frequency 2'},
            'level_2':      {'default': 0.5,  'min': 0.0,  'max': 1.0, 'step': 0.05, 'label': 'Freq 2 Level'},
            'decay_frac':   {'default': 1.5,  'min': 0.3,  'max': 4.0, 'step': 0.1, 'label': 'Ring Decay'},
            'noise_level':  {'default': 0.3,  'min': 0.0,  'max': 1.0, 'step': 0.05, 'label': 'Noise Bite'},
            'body_low':     {'default': 500,  'min': 50,   'max': 3000, 'step': 50, 'label': 'Body Low Freq'},
            'body_high':    {'default': 4000, 'min': 500,  'max': 10000, 'step': 100, 'label': 'Body High Freq'},
            'fm_mod_freq':  {'default': 0,    'min': 0,    'max': 5000, 'step': 10,  'label': 'FM Mod Freq'},
            'fm_mod_index': {'default': 1.0,  'min': 0.0,  'max': 10.0, 'step': 0.1, 'label': 'FM Mod Index'},
            'ring_mod_freq':{'default': 0,    'min': 0,    'max': 2000, 'step': 10,  'label': 'Ring Mod Freq'},
            'ring_mod_mix': {'default': 0.3,  'min': 0.0,  'max': 1.0,  'step': 0.05,'label': 'Ring Mod Mix'},
        },
    },
    'percussive': {
        'label': 'Percussive / Click',
        'description': 'Very short click or tick. Good for UI sounds, footsteps, small cues.',
        'params': {
            'duration':    {'default': 0.08, 'min': 0.02, 'max': 0.3, 'step': 0.01, 'label': 'Duration (s)'},
            'freq':        {'default': 1200, 'min': 200,  'max': 5000, 'step': 50,  'label': 'Tone Frequency'},
            'tone_level':  {'default': 0.3,  'min': 0.0,  'max': 1.0, 'step': 0.05, 'label': 'Tone Level'},
            'click_level': {'default': 0.7,  'min': 0.0,  'max': 1.0, 'step': 0.05, 'label': 'Click Level'},
            'decay_frac':  {'default': 0.3,  'min': 0.1,  'max': 2.0, 'step': 0.1,  'label': 'Decay'},
        },
    },
    'plucked_string': {
        'label': 'Plucked String (Karplus-Strong)',
        'description': 'Physical-modeled plucked string. Realistic lute/harp for bard skills, metallic pings for impacts.',
        'params': {
            'duration':       {'default': 0.4,  'min': 0.1,  'max': 2.0,  'step': 0.01, 'label': 'Duration (s)'},
            'freq':           {'default': 440,  'min': 50,   'max': 3000, 'step': 1,    'label': 'Frequency (Hz)'},
            'brightness':     {'default': 0.5,  'min': 0.0,  'max': 1.0,  'step': 0.05, 'label': 'Brightness'},
            'damping':        {'default': 0.5,  'min': 0.0,  'max': 1.0,  'step': 0.05, 'label': 'Damping'},
            'pluck_position': {'default': 0.5,  'min': 0.05, 'max': 0.95, 'step': 0.05, 'label': 'Pluck Position'},
            'body_size':      {'default': 0.0,  'min': 0.0,  'max': 1.0,  'step': 0.05, 'label': 'Body Resonance'},
            'note_2_freq':    {'default': 0,    'min': 0,    'max': 3000, 'step': 1,    'label': '2nd String Freq'},
            'note_2_level':   {'default': 0.5,  'min': 0.0,  'max': 1.0,  'step': 0.05, 'label': '2nd String Level'},
            'note_2_delay':   {'default': 0.0,  'min': 0.0,  'max': 0.2,  'step': 0.005,'label': '2nd String Delay (s)'},
        },
    },
    'metallic_body': {
        'label': 'Metallic Body (Modal)',
        'description': 'Modal synthesis for realistic metal impacts — shields, swords, bells, anvils.',
        'params': {
            'duration':        {'default': 0.3,  'min': 0.05, 'max': 1.0,  'step': 0.01, 'label': 'Duration (s)'},
            'fundamental':     {'default': 800,  'min': 100,  'max': 5000, 'step': 10,   'label': 'Fundamental (Hz)'},
            'mode_2_ratio':    {'default': 2.76, 'min': 1.5,  'max': 6.0,  'step': 0.01, 'label': 'Mode 2 Ratio'},
            'mode_3_ratio':    {'default': 5.40, 'min': 2.0,  'max': 12.0, 'step': 0.01, 'label': 'Mode 3 Ratio'},
            'mode_4_ratio':    {'default': 8.93, 'min': 3.0,  'max': 20.0, 'step': 0.01, 'label': 'Mode 4 Ratio'},
            'decay_base':      {'default': 0.15, 'min': 0.02, 'max': 1.0,  'step': 0.01, 'label': 'Decay Time'},
            'high_decay_mult': {'default': 0.5,  'min': 0.1,  'max': 1.0,  'step': 0.05, 'label': 'High Freq Decay'},
            'noise_level':     {'default': 0.3,  'min': 0.0,  'max': 1.0,  'step': 0.05, 'label': 'Impact Noise'},
            'noise_freq_low':  {'default': 500,  'min': 100,  'max': 3000, 'step': 50,   'label': 'Noise Low Freq'},
            'noise_freq_high': {'default': 5000, 'min': 1000, 'max': 12000,'step': 100,  'label': 'Noise High Freq'},
        },
    },
}


# ── Template generators ──────────────────────────────────

def _p(params, key, fallback=None):
    """Get a parameter value, using template default as fallback."""
    return params.get(key, fallback)


def _apply_post_processing(mono, p):
    """Apply bitcrush → tremolo → chorus → delay → reverb → stereo from common params."""
    # Bitcrusher (before other effects for authentic lo-fi)
    bc = int(_p(p, 'bitcrush_depth', 0))
    if bc > 0:
        mono = _bitcrush(mono, bit_depth=bc,
                         downsample=int(_p(p, 'bitcrush_downsample', 1)))
    # Tremolo
    tr = float(_p(p, 'tremolo_rate', 0.0))
    if tr > 0:
        mono = _tremolo(mono, rate=tr,
                        depth=_p(p, 'tremolo_depth', 0.5))
    # Chorus
    cv = int(_p(p, 'chorus_voices', 0))
    if cv > 0:
        mono = _chorus(mono, voices=cv,
                       max_delay_ms=8,
                       depth_ms=_p(p, 'chorus_depth', 3.0),
                       rate_hz=_p(p, 'chorus_rate', 1.2))
    # Delay / Echo
    dm = int(_p(p, 'delay_ms', 0))
    if dm > 0:
        mono = _delay(mono, delay_ms=dm,
                      feedback=_p(p, 'delay_feedback', 0.3),
                      wet=_p(p, 'delay_wet', 0.25))
    # Reverb
    rd = _p(p, 'reverb_decay', 0.25)
    rw = _p(p, 'reverb_wet', 0.2)
    if rw > 0:
        mono = _reverb(mono, decay=rd, wet=rw,
                       room=_p(p, 'reverb_room', 'dungeon'))
    return _stereo(mono,
                   width=_p(p, 'stereo_width', 0.4),
                   mode=_p(p, 'stereo_mode', 'haas'))


def _tmpl_osc(freq, dur, waveform='sine'):
    """Oscillator helper for templates."""
    if waveform == 'saw':
        return _saw(freq, dur)
    elif waveform == 'square':
        return _sq(freq, dur)
    elif waveform == 'plucked':
        return _karplus_strong(freq, dur, brightness=0.6, damping=0.4)
    return _sine(freq, dur)


def generate_impact(p):
    """Template generator: impact/hit."""
    dur = _p(p, 'duration', 0.2)
    n = int(RATE * dur)
    # Body noise burst
    hit = _noise(n, _p(p, 'noise_color', 'white'))
    hit *= _env_perc(n, attack=_p(p, 'attack', 0.002),
                     decay_frac=_p(p, 'decay_frac', 1.2))
    hit = _bandpass(hit, _p(p, 'body_freq_low', 200),
                    _p(p, 'body_freq_high', 3000))
    # Sub thud with optional pitch envelope
    pe = _p(p, 'pitch_env', 'none')
    sub_freq = _p(p, 'sub_freq', 60)
    if pe != 'none':
        sub = _pitch_env_osc(sub_freq, dur, env_type=pe,
                             amount=_p(p, 'pitch_env_amt', 1.0))
    else:
        sub = _sine(sub_freq, dur)
    sub *= _env_perc(n, attack=0.001, decay_frac=0.8) * _p(p, 'sub_level', 0.5)
    # Transient click
    cl = _p(p, 'click_level', 0.8)
    click_n = int(RATE * 0.008)
    click = _noise(click_n, 'white') * np.linspace(1, 0, click_n) * cl
    mono = _normalize(_mix(hit * 0.7, sub, click * 0.9))
    # Ring modulation
    rmf = _p(p, 'ring_mod_freq', 0)
    if rmf > 0:
        mono = _ring_mod(mono, rmf, mix=_p(p, 'ring_mod_mix', 0.3))
    # Optional distortion
    dg = _p(p, 'distortion_gain', 0.0)
    if dg > 0:
        mono = _distort(mono, gain=dg, clip=_p(p, 'distortion_clip', 0.7))
        mono = _normalize(mono)
    return _apply_post_processing(mono, p)


def generate_sweep(p):
    """Template generator: frequency sweep."""
    dur = _p(p, 'duration', 0.35)
    n = int(RATE * dur)
    # Optional pitch envelope on sweep base freq
    pe = _p(p, 'pitch_env', 'none')
    fs = _p(p, 'freq_start', 200)
    fe = _p(p, 'freq_end', 800)
    if pe != 'none':
        sig = _pitch_env_osc(fs, dur, env_type=pe,
                             amount=_p(p, 'pitch_env_amt', 1.0))
    else:
        sig = _sweep(fs, fe, dur)
    sig *= _env_adsr(n, a=_p(p, 'env_attack', 0.02), d=0.05,
                     s=_p(p, 'env_sustain', 0.7),
                     r=_p(p, 'env_release', 0.15))
    if _p(p, 'use_resonance', True):
        q = _p(p, 'resonance_q', 3.5)
        sig = _resonant_sweep(sig, fs * 1.1, fe * 1.1, q=q)
    # Ring modulation
    rmf = _p(p, 'ring_mod_freq', 0)
    if rmf > 0:
        sig = _ring_mod(sig, rmf, mix=_p(p, 'ring_mod_mix', 0.3))
    # Shimmer
    sf = _p(p, 'shimmer_freq', 0)
    if sf > 0:
        shimmer = _sine(sf, dur) * _env_perc(n, decay_frac=0.8)
        shimmer *= _p(p, 'shimmer_level', 0.15)
        sig = _mix(sig * 0.7, shimmer)
    else:
        sig = sig * 0.7
    mono = _normalize(sig)
    dg = _p(p, 'distortion_gain', 0.0)
    if dg > 0:
        mono = _distort(mono, gain=dg, clip=0.6)
        mono = _normalize(mono)
    return _apply_post_processing(mono, p)


def generate_chord(p):
    """Template generator: chord/tonal."""
    dur = _p(p, 'duration', 0.5)
    n = int(RATE * dur)
    root = _p(p, 'root_freq', 523)
    v1 = _sine(root, dur)
    v2 = _sine(root * _p(p, 'interval_2', 1.26), dur) * _p(p, 'level_2', 0.7)
    v3 = _sine(root * _p(p, 'interval_3', 1.50), dur) * _p(p, 'level_3', 0.5)
    chord = (v1 + v2 + v3) * _env_adsr(n, a=_p(p, 'env_attack', 0.05), d=0.1,
                                         s=_p(p, 'env_sustain', 0.5),
                                         r=_p(p, 'env_release', 0.25))
    # Formant filter
    fv = _p(p, 'formant_vowel', 'none')
    if fv != 'none':
        chord = _formant(chord, vowel=fv,
                         intensity=_p(p, 'formant_intensity', 0.5))
    # Air/shimmer
    sh = _p(p, 'shimmer', 0.05)
    if sh > 0:
        shimmer = _noise(n, 'pink') * _env_perc(n, decay_frac=2.0) * sh
        shimmer = _highpass(shimmer, 3000)
        chord = chord * 0.5 + shimmer
    else:
        chord = chord * 0.5
    mono = _normalize(chord)
    return _apply_post_processing(mono, p)


def generate_arpeggio(p):
    """Template generator: arpeggio/sequence."""
    notes = [_p(p, f'note_{i}', 0) for i in range(1, 5)]
    notes = [f for f in notes if f and f > 0]
    if not notes:
        notes = [523, 659, 784]
    dur_each = _p(p, 'note_duration', 0.1)
    gap = _p(p, 'gap_duration', 0.0)
    wf = _p(p, 'waveform', 'sine')
    df = _p(p, 'decay_frac', 0.6)
    parts = []
    for freq in notes:
        nn = int(RATE * dur_each)
        part = _tmpl_osc(freq, dur_each, wf) * _env_perc(nn, decay_frac=df)
        parts.append(part)
        if gap > 0:
            parts.append(np.zeros(int(RATE * gap)))
    mono = _normalize(np.concatenate(parts) * 0.5)
    return _apply_post_processing(mono, p)


def generate_noise_texture(p):
    """Template generator: noise texture."""
    dur = _p(p, 'duration', 0.3)
    n = int(RATE * dur)
    sig = _noise(n, _p(p, 'noise_color', 'pink'))
    sig *= _env_perc(n, attack=_p(p, 'env_attack', 0.02),
                     decay_frac=_p(p, 'decay_frac', 1.0))
    fl = _p(p, 'filter_low', 200)
    fh = _p(p, 'filter_high', 3000)
    if fl > 20 and fh < 10000:
        sig = _bandpass(sig, fl, fh)
    elif fl > 20:
        sig = _highpass(sig, fl)
    elif fh < 10000:
        sig = _lowpass(sig, fh)
    mono = sig * 0.5
    if _p(p, 'secondary_layer', False):
        sec = _noise(n, _p(p, 'secondary_color', 'brown'))
        sec *= _env_perc(n, decay_frac=_p(p, 'decay_frac', 1.0))
        sec = _lowpass(sec, _p(p, 'secondary_cutoff', 300))
        sec *= _p(p, 'secondary_level', 0.3)
        mono = mono + sec
    mono = _normalize(mono)
    return _apply_post_processing(mono, p)


def generate_drone(p):
    """Template generator: drone/sustained."""
    dur = _p(p, 'duration', 0.4)
    n = int(RATE * dur)
    wf = _p(p, 'waveform', 'sine')
    base = _tmpl_osc(_p(p, 'base_freq', 200), dur, wf)
    md = _p(p, 'mod_depth', 0.3)
    if md > 0:
        mod = _sine(_p(p, 'mod_freq', 5.0), dur)
        base = base * (1 + md * mod)
    base *= _env_adsr(n, a=_p(p, 'env_attack', 0.05), d=0.1,
                      s=_p(p, 'env_sustain', 0.5),
                      r=_p(p, 'env_release', 0.2))
    fc = _p(p, 'filter_cutoff', 500)
    if fc < 4000:
        base = _lowpass(base, fc)
    # Formant filter
    fv = _p(p, 'formant_vowel', 'none')
    if fv != 'none':
        base = _formant(base, vowel=fv,
                        intensity=_p(p, 'formant_intensity', 0.5))
    # Ring modulation
    rmf = _p(p, 'ring_mod_freq', 0)
    if rmf > 0:
        base = _ring_mod(base, rmf, mix=_p(p, 'ring_mod_mix', 0.3))
    mono = _normalize(base * 0.6)
    return _apply_post_processing(mono, p)


def generate_tonal_hit(p):
    """Template generator: tonal hit/ring."""
    dur = _p(p, 'duration', 0.2)
    n = int(RATE * dur)
    df = _p(p, 'decay_frac', 1.5)
    # Primary tone — use FM synthesis if mod freq set
    fmf = _p(p, 'fm_mod_freq', 0)
    if fmf > 0:
        t1 = _fm_osc(_p(p, 'freq_1', 800), fmf,
                     mod_index=_p(p, 'fm_mod_index', 1.0), dur=dur)
        t1 *= _env_perc(n, decay_frac=df)
    else:
        t1 = _sine(_p(p, 'freq_1', 800), dur) * _env_perc(n, decay_frac=df)
    f2 = _p(p, 'freq_2', 1600)
    if f2 > 0:
        t2 = _sine(f2, dur) * _env_perc(n, decay_frac=df * 0.9)
        t2 *= _p(p, 'level_2', 0.5)
        tonal = _mix(t1, t2)
    else:
        tonal = t1
    # Ring modulation
    rmf = _p(p, 'ring_mod_freq', 0)
    if rmf > 0:
        tonal = _ring_mod(tonal, rmf, mix=_p(p, 'ring_mod_mix', 0.3))
    nl = _p(p, 'noise_level', 0.3)
    if nl > 0:
        noise = _noise(n, 'white') * _env_perc(n, attack=0.001, decay_frac=0.5)
        noise = _bandpass(noise, _p(p, 'body_low', 500), _p(p, 'body_high', 4000))
        noise *= nl
        mono = _normalize(_mix(tonal, noise))
    else:
        mono = _normalize(tonal)
    return _apply_post_processing(mono, p)


def generate_percussive(p):
    """Template generator: percussive/click."""
    dur = _p(p, 'duration', 0.08)
    n = int(RATE * dur)
    freq = _p(p, 'freq', 1200)
    tl = _p(p, 'tone_level', 0.3)
    cl = _p(p, 'click_level', 0.7)
    df = _p(p, 'decay_frac', 0.3)
    tone = _sine(freq, dur) * _env_perc(n, decay_frac=df) * tl
    click_n = int(RATE * 0.005)
    click = _noise(click_n, 'white') * np.linspace(1, 0, click_n) * cl
    combined = np.zeros(n)
    combined[:len(tone)] += tone
    combined[:len(click)] += click
    mono = _normalize(combined)
    return _apply_post_processing(mono, p)


def generate_plucked_string(p):
    """Template generator: Karplus-Strong plucked string."""
    dur = _p(p, 'duration', 0.4)
    freq = _p(p, 'freq', 440)
    s1 = _karplus_strong(
        freq, dur,
        brightness=_p(p, 'brightness', 0.5),
        damping=_p(p, 'damping', 0.5),
        pluck_position=_p(p, 'pluck_position', 0.5),
        body_size=_p(p, 'body_size', 0.0),
    )
    # Optional second string
    f2 = _p(p, 'note_2_freq', 0)
    if f2 > 0:
        s2 = _karplus_strong(
            f2, dur,
            brightness=_p(p, 'brightness', 0.5),
            damping=_p(p, 'damping', 0.5),
            pluck_position=_p(p, 'pluck_position', 0.5),
            body_size=_p(p, 'body_size', 0.0),
        ) * _p(p, 'note_2_level', 0.5)
        delay_samp = int(_p(p, 'note_2_delay', 0.0) * RATE)
        n = int(RATE * dur)
        combined = np.zeros(n)
        combined[:len(s1)] += s1
        if delay_samp < n:
            end = min(n, delay_samp + len(s2))
            combined[delay_samp:end] += s2[:end - delay_samp]
        mono = _normalize(combined)
    else:
        mono = _normalize(s1)
    return _apply_post_processing(mono, p)


def generate_metallic_body(p):
    """Template generator: modal synthesis metallic body."""
    dur = _p(p, 'duration', 0.3)
    n = int(RATE * dur)
    fund = _p(p, 'fundamental', 800)
    decay_base = _p(p, 'decay_base', 0.15)
    hdm = _p(p, 'high_decay_mult', 0.5)

    # Build modal frequencies — inharmonic ratios typical of metal objects
    modes = [
        (fund,                              1.0,  decay_base),
        (fund * _p(p, 'mode_2_ratio', 2.76), 0.6,  decay_base * hdm),
        (fund * _p(p, 'mode_3_ratio', 5.40), 0.35, decay_base * hdm * 0.7),
        (fund * _p(p, 'mode_4_ratio', 8.93), 0.15, decay_base * hdm * 0.5),
    ]
    # Filter out modes above Nyquist
    modes = [(f, a, d) for f, a, d in modes if f < RATE / 2]
    tonal = _modal_synthesis(modes, dur)

    # Impact noise transient
    nl = _p(p, 'noise_level', 0.3)
    if nl > 0:
        noise = _noise(n, 'white') * _env_perc(n, attack=0.001, decay_frac=0.4)
        noise = _bandpass(noise, _p(p, 'noise_freq_low', 500),
                          _p(p, 'noise_freq_high', 5000))
        mono = _normalize(_mix(tonal, noise * nl))
    else:
        mono = _normalize(tonal)
    return _apply_post_processing(mono, p)


TEMPLATE_GENERATORS = {
    'impact':          generate_impact,
    'sweep':           generate_sweep,
    'chord':           generate_chord,
    'arpeggio':        generate_arpeggio,
    'noise_texture':   generate_noise_texture,
    'drone':           generate_drone,
    'tonal_hit':       generate_tonal_hit,
    'percussive':      generate_percussive,
    'plucked_string':  generate_plucked_string,
    'metallic_body':   generate_metallic_body,
}


# ── Sound-key → template + default overrides ─────────────

def _build_template_map():
    """Map every existing sound key to a template + params that
    approximate the original bespoke generator output."""
    m = {}

    # ── Combat ────────────────────────────────────────
    for i in range(1, 10):
        m[f'melee_hit_{i}'] = {'template': 'impact', 'params': {
            'duration': 0.15 + i * 0.02,
            'body_freq_low': 200 + i * 80, 'body_freq_high': 3000 + i * 200,
            'sub_freq': 60 + i * 5, 'sub_level': 0.5, 'click_level': 0.9,
            'pitch_env': 'drop', 'pitch_env_amt': 1.2,
            'reverb_decay': 0.15, 'reverb_wet': 0.15, 'reverb_room': 'tight',
            'stereo_width': 0.3,
        }}
    m['melee_hit_retro'] = {'template': 'impact', 'params': {
        'duration': 0.17, 'distortion_gain': 4.0, 'distortion_clip': 0.5,
        'reverb_decay': 0.15, 'reverb_wet': 0.15, 'reverb_room': 'tight',
        'stereo_width': 0.3,
    }}
    for i in range(1, 3):
        m[f'melee_crit{"" if i == 1 else "_2"}'] = {'template': 'impact', 'params': {
            'duration': 0.25, 'distortion_gain': 4.0, 'distortion_clip': 0.8,
            'body_freq_low': 150, 'body_freq_high': 4000,
            'sub_freq': 50, 'sub_level': 0.4, 'decay_frac': 1.5,
            'reverb_decay': 0.2, 'reverb_wet': 0.18, 'reverb_room': 'tight',
            'stereo_width': 0.4, 'chorus_voices': 2,
        }}
    # Note: bespoke gen_melee_crit uses _fm_osc for metallic ring — not expressible
    # in the impact template. The template approximation uses distortion + chorus instead.
    for i in range(1, 7):
        m[f'ranged_hit_{i}'] = {'template': 'impact', 'params': {
            'duration': 0.18, 'noise_color': 'pink',
            'body_freq_low': 800 + i * 100, 'body_freq_high': 5000,
            'sub_freq': 80, 'sub_level': 0.6, 'click_level': 0.0,
            'reverb_decay': 0.15, 'reverb_wet': 0.12, 'reverb_room': 'tight',
            'stereo_width': 0.35,
        }}
    for i in range(1, 5):
        m[f'miss_{i}'] = {'template': 'noise_texture', 'params': {
            'duration': 0.2 + i * 0.03, 'noise_color': 'pink',
            'filter_low': 1500 + i * 200, 'filter_high': 5000,
            'decay_frac': 0.7,
            'reverb_wet': 0.0, 'stereo_width': 0.5, 'stereo_mode': 'spread',
        }}
    m['dodge'] = {'template': 'sweep', 'params': {
        'duration': 0.12, 'freq_start': 300, 'freq_end': 2500,
        'use_resonance': False, 'env_sustain': 0.5, 'env_release': 0.05,
        'reverb_wet': 0.0, 'stereo_width': 0.6, 'stereo_mode': 'spread',
    }}
    for i in range(1, 8):
        m[f'block_{i}'] = {'template': 'tonal_hit', 'params': {
            'duration': 0.2,
            'freq_1': 800 + i * 150, 'freq_2': 1600 + i * 200,
            'level_2': 0.6, 'decay_frac': 1.8, 'noise_level': 0.4,
            'body_low': 500, 'body_high': 4000,
            'ring_mod_freq': 350 + i * 40, 'ring_mod_mix': 0.4,
            'chorus_voices': 2, 'chorus_depth': 1.5, 'chorus_rate': 2.0,
            'reverb_decay': 0.2, 'reverb_wet': 0.18,
            'stereo_width': 0.35,
        }}
    for i in range(1, 6):
        m[f'death_{i}'] = {'template': 'sweep', 'params': {
            'duration': 0.5, 'freq_start': 200, 'freq_end': 50,
            'resonance_q': 3.0, 'shimmer_freq': 0,
            'pitch_env': 'drop', 'pitch_env_amt': 1.5,
            'env_attack': 0.005, 'env_sustain': 0.5, 'env_release': 0.2,
            'reverb_decay': 0.35, 'reverb_wet': 0.22,
            'stereo_width': 0.3,
        }}
    for i in range(1, 3):
        m[f'stun_hit{"" if i == 1 else "_2"}'] = {'template': 'tonal_hit', 'params': {
            'duration': 0.3,
            'freq_1': 600 + i * 50, 'freq_2': 900 + i * 70, 'level_2': 0.75,
            'decay_frac': 2.0, 'noise_level': 0.5, 'body_low': 200, 'body_high': 2000,
            'ring_mod_freq': 180, 'ring_mod_mix': 0.5,
            'chorus_voices': 2,
            'reverb_decay': 0.25, 'reverb_wet': 0.2,
            'stereo_width': 0.4,
        }}
    m['stun_locked'] = {'template': 'drone', 'params': {
        'duration': 0.4, 'base_freq': 120, 'waveform': 'sine',
        'mod_freq': 6.0, 'mod_depth': 0.3, 'filter_cutoff': 500,
        'env_attack': 0.02, 'env_sustain': 0.7, 'env_release': 0.2,
        'chorus_voices': 2, 'chorus_depth': 4.0, 'chorus_rate': 0.8,
        'reverb_decay': 0.3, 'reverb_wet': 0.2,
        'stereo_width': 0.3, 'stereo_mode': 'mid_side',
    }}

    # ── Skills — generic ──────────────────────────────
    # Note: Bespoke generators use FM, modal, KS synthesis. Templates approximate.
    m['skill_cast'] = {'template': 'tonal_hit', 'params': {
        'duration': 0.35, 'freq_1': 350, 'freq_2': 520,
        'level_2': 0.5, 'decay_frac': 0.8, 'noise_level': 0.0,
        'pitch_env': 'drop', 'pitch_env_amt': 0.8,
        'reverb_decay': 0.20, 'reverb_wet': 0.18,
        'stereo_width': 0.4, 'stereo_mode': 'spread',
    }}
    m['skill_cast_energy'] = {'template': 'plucked_string', 'params': {
        'duration': 0.4, 'freq': 800, 'brightness': 0.7, 'damping': 0.5,
        'body_size': 0.3,
        'chorus_voices': 2, 'chorus_depth': 3.0, 'chorus_rate': 1.0,
        'reverb_decay': 0.22, 'reverb_wet': 0.20,
        'stereo_width': 0.45, 'stereo_mode': 'spread',
    }}
    m['skill_cast_dark'] = {'template': 'drone', 'params': {
        'duration': 0.45, 'base_freq': 65, 'waveform': 'sine',
        'mod_freq': 0.8, 'mod_depth': 0.0, 'filter_cutoff': 400,
        'formant_vowel': 'u', 'formant_intensity': 0.5,
        'tremolo_rate': 5.0, 'tremolo_depth': 0.3,
        'chorus_voices': 2, 'chorus_depth': 5.0, 'chorus_rate': 0.6,
        'reverb_decay': 0.35, 'reverb_wet': 0.30,
        'stereo_width': 0.35, 'stereo_mode': 'mid_side',
    }}
    m['skill_cast_power'] = {'template': 'impact', 'params': {
        'duration': 0.3, 'body_freq_low': 200, 'body_freq_high': 3000,
        'sub_freq': 60, 'sub_level': 0.5, 'click_level': 0.6,
        'pitch_env': 'drop', 'pitch_env_amt': 1.5,
        'reverb_decay': 0.18, 'reverb_wet': 0.18,
        'stereo_width': 0.35,
    }}
    m['skill_cast_sphere'] = {'template': 'plucked_string', 'params': {
        'duration': 0.3, 'freq': 600, 'brightness': 0.65, 'damping': 0.45,
        'body_size': 0.3,
        'chorus_voices': 2,
        'reverb_decay': 0.20, 'reverb_wet': 0.18,
        'stereo_width': 0.4, 'stereo_mode': 'spread',
    }}

    # ── Skills — per class ────────────────────────────
    # Crusader
    m['skill_taunt'] = {'template': 'drone', 'params': {
        'duration': 0.4, 'base_freq': 100, 'waveform': 'sine',
        'filter_cutoff': 500, 'mod_depth': 0.0,
        'formant_vowel': 'a', 'formant_intensity': 0.6,
        'pitch_env': 'drop', 'pitch_env_amt': 1.0,
        'reverb_decay': 0.25, 'reverb_wet': 0.22,
        'stereo_width': 0.35,
    }}
    m['skill_shield_bash'] = {'template': 'metallic_body', 'params': {
        'duration': 0.2, 'num_modes': 4,
        'freq_1': 400, 'freq_2': 900, 'freq_3': 1500, 'freq_4': 2200,
        'ring_mod_freq': 350, 'ring_mod_mix': 0.35,
        'reverb_decay': 0.16, 'reverb_wet': 0.15,
        'stereo_width': 0.3,
    }}
    m['skill_holy_ground'] = {'template': 'plucked_string', 'params': {
        'duration': 0.6, 'freq': 523, 'brightness': 0.55, 'damping': 0.35,
        'body_size': 0.5,
        'tremolo_rate': 3.0, 'tremolo_depth': 0.25,
        'chorus_voices': 3, 'chorus_depth': 4.0, 'chorus_rate': 0.7,
        'reverb_decay': 0.40, 'reverb_wet': 0.32,
        'stereo_width': 0.55, 'stereo_mode': 'spread',
    }}
    m['skill_bulwark'] = {'template': 'metallic_body', 'params': {
        'duration': 0.3, 'num_modes': 4,
        'freq_1': 350, 'freq_2': 700, 'freq_3': 1100, 'freq_4': 1800,
        'reverb_decay': 0.18, 'reverb_wet': 0.18,
        'stereo_width': 0.3,
    }}
    # Ranger
    m['skill_power_shot'] = {'template': 'plucked_string', 'params': {
        'duration': 0.25, 'freq': 350, 'brightness': 0.9, 'damping': 0.7,
        'body_size': 0.05, 'pluck_position': 0.1,
        'pitch_env': 'drop', 'pitch_env_amt': 1.5,
        'reverb_decay': 0.14, 'reverb_wet': 0.14,
        'stereo_width': 0.45,
    }}
    m['skill_volley'] = {'template': 'plucked_string', 'params': {
        'duration': 0.4, 'freq': 300, 'brightness': 0.85, 'damping': 0.75,
        'body_size': 0.1,
        'reverb_decay': 0.15, 'reverb_wet': 0.15,
        'stereo_width': 0.55, 'stereo_mode': 'spread',
    }}
    m['skill_evasion'] = {'template': 'plucked_string', 'params': {
        'duration': 0.22, 'freq': 2000, 'brightness': 0.95, 'damping': 0.6,
        'body_size': 0.1,
        'reverb_decay': 0.10, 'reverb_wet': 0.10,
        'stereo_width': 0.55, 'stereo_mode': 'spread',
    }}
    m['skill_crippling_shot'] = {'template': 'tonal_hit', 'params': {
        'duration': 0.3, 'freq_1': 600, 'freq_2': 400,
        'level_2': 0.5, 'decay_frac': 0.8,
        'ring_mod_freq': 120, 'ring_mod_mix': 0.3,
        'formant_vowel': 'u', 'formant_intensity': 0.4,
        'reverb_decay': 0.18, 'reverb_wet': 0.18,
        'stereo_width': 0.38,
    }}
    # Confessor
    m['skill_heal'] = {'template': 'plucked_string', 'params': {
        'duration': 0.5, 'freq': 440, 'brightness': 0.45, 'damping': 0.3,
        'body_size': 0.6,
        'formant_vowel': 'a', 'formant_intensity': 0.5,
        'chorus_voices': 3, 'chorus_depth': 3.0, 'chorus_rate': 0.8,
        'reverb_decay': 0.35, 'reverb_wet': 0.30,
        'stereo_width': 0.5, 'stereo_mode': 'spread',
    }}
    m['skill_rebuke'] = {'template': 'metallic_body', 'params': {
        'duration': 0.25, 'num_modes': 3,
        'freq_1': 2200, 'freq_2': 3500, 'freq_3': 5000,
        'ring_mod_freq': 400, 'ring_mod_mix': 0.35,
        'reverb_decay': 0.15, 'reverb_wet': 0.15,
        'stereo_width': 0.35,
    }}
    m['skill_exorcism'] = {'template': 'tonal_hit', 'params': {
        'duration': 0.35, 'freq_1': 400, 'freq_2': 567, 'level_2': 0.6,
        'decay_frac': 1.0, 'noise_level': 0.3,
        'ring_mod_freq': 233, 'ring_mod_mix': 0.4,
        'formant_vowel': 'u', 'formant_intensity': 0.5,
        'chorus_voices': 2,
        'reverb_decay': 0.25, 'reverb_wet': 0.25,
        'stereo_width': 0.45, 'stereo_mode': 'spread',
    }}
    m['skill_prayer'] = {'template': 'drone', 'params': {
        'duration': 0.5, 'base_freq': 165, 'waveform': 'sine',
        'mod_freq': 5.0, 'mod_depth': 0.08, 'filter_cutoff': 3000,
        'formant_vowel': 'a', 'formant_intensity': 0.6,
        'tremolo_rate': 2.5, 'tremolo_depth': 0.25,
        'env_attack': 0.1, 'env_sustain': 0.4, 'env_release': 0.25,
        'chorus_voices': 3, 'chorus_depth': 5.0, 'chorus_rate': 0.5,
        'reverb_decay': 0.40, 'reverb_wet': 0.35,
        'stereo_width': 0.5, 'stereo_mode': 'spread',
    }}
    m['skill_shield_of_faith'] = {'template': 'metallic_body', 'params': {
        'duration': 0.5, 'num_modes': 3,
        'freq_1': 400, 'freq_2': 800, 'freq_3': 1200,
        'tremolo_rate': 3.0, 'tremolo_depth': 0.3,
        'chorus_voices': 3, 'chorus_depth': 3.0, 'chorus_rate': 0.8,
        'reverb_decay': 0.30, 'reverb_wet': 0.28,
        'stereo_width': 0.5, 'stereo_mode': 'spread',
    }}
    # Inquisitor
    m['skill_divine_sense'] = {'template': 'tonal_hit', 'params': {
        'duration': 0.4, 'freq_1': 600, 'freq_2': 1200,
        'level_2': 0.5, 'decay_frac': 0.8,
        'tremolo_rate': 6.0, 'tremolo_depth': 0.4,
        'reverb_decay': 0.30, 'reverb_wet': 0.25,
        'stereo_width': 0.5, 'stereo_mode': 'spread',
    }}
    # Hexblade
    m['skill_shadow_step'] = {'template': 'drone', 'params': {
        'duration': 0.25, 'base_freq': 150, 'waveform': 'sine',
        'mod_depth': 0.0, 'filter_cutoff': 400,
        'ring_mod_freq': 180, 'ring_mod_mix': 0.35,
        'pitch_env': 'drop', 'pitch_env_amt': 2.0,
        'reverb_decay': 0.22, 'reverb_wet': 0.22,
        'stereo_width': 0.5, 'stereo_mode': 'spread',
    }}
    m['skill_wither'] = {'template': 'metallic_body', 'params': {
        'duration': 0.45, 'num_modes': 4,
        'freq_1': 173, 'freq_2': 411, 'freq_3': 777, 'freq_4': 1230,
        'distortion_gain': 1.6, 'distortion_clip': 0.5,
        'chorus_voices': 2, 'chorus_depth': 4.0, 'chorus_rate': 0.6,
        'reverb_decay': 0.30, 'reverb_wet': 0.28,
        'stereo_width': 0.4, 'stereo_mode': 'mid_side',
    }}
    m['skill_ward'] = {'template': 'metallic_body', 'params': {
        'duration': 0.3, 'num_modes': 3,
        'freq_1': 500, 'freq_2': 1100, 'freq_3': 1700,
        'reverb_decay': 0.18, 'reverb_wet': 0.18,
        'stereo_width': 0.4, 'stereo_mode': 'spread',
    }}
    m['skill_soul_reap'] = {'template': 'tonal_hit', 'params': {
        'duration': 0.25, 'freq_1': 800, 'freq_2': 250,
        'level_2': 0.5, 'decay_frac': 0.6,
        'ring_mod_freq': 300, 'ring_mod_mix': 0.4,
        'formant_vowel': 'e', 'formant_intensity': 0.5,
        'reverb_decay': 0.20, 'reverb_wet': 0.20,
        'stereo_width': 0.4,
    }}
    m['skill_venom_gaze'] = {'template': 'drone', 'params': {
        'duration': 0.3, 'base_freq': 300, 'waveform': 'sine',
        'mod_freq': 15.0, 'mod_depth': 2.5, 'filter_cutoff': 1500,
        'ring_mod_freq': 80, 'ring_mod_mix': 0.3,
        'formant_vowel': 'i', 'formant_intensity': 0.4,
        'reverb_decay': 0.18, 'reverb_wet': 0.18,
        'stereo_width': 0.3,
    }}
    # Misc melee / war
    m['skill_war_cry'] = {'template': 'drone', 'params': {
        'duration': 0.35, 'base_freq': 150, 'waveform': 'sine',
        'mod_depth': 0.0, 'filter_cutoff': 800,
        'formant_vowel': 'o', 'formant_intensity': 0.6,
        'distortion_gain': 1.5, 'distortion_clip': 0.6,
        'pitch_env': 'drop', 'pitch_env_amt': 1.5,
        'reverb_decay': 0.20, 'reverb_wet': 0.20,
        'stereo_width': 0.4,
    }}
    m['skill_double_strike'] = {'template': 'metallic_body', 'params': {
        'duration': 0.2, 'num_modes': 3,
        'freq_1': 350, 'freq_2': 800, 'freq_3': 1500,
        'reverb_decay': 0.12, 'reverb_wet': 0.12,
        'stereo_width': 0.3,
    }}
    # Bard
    m['skill_ballad_of_might'] = {'template': 'arpeggio', 'params': {
        'note_1': 440, 'note_2': 554, 'note_3': 659, 'note_4': 880,
        'note_duration': 0.09, 'waveform': 'plucked', 'decay_frac': 0.6,
        'formant_vowel': 'o', 'formant_intensity': 0.4,
        'chorus_voices': 2, 'chorus_depth': 2.0, 'chorus_rate': 1.2,
        'reverb_decay': 0.25, 'reverb_wet': 0.22,
        'stereo_width': 0.45, 'stereo_mode': 'spread',
    }}
    m['skill_dirge_of_weakness'] = {'template': 'arpeggio', 'params': {
        'note_1': 440, 'note_2': 392, 'note_3': 330, 'note_4': 294,
        'note_duration': 0.10, 'waveform': 'plucked', 'decay_frac': 0.7,
        'ring_mod_freq': 60, 'ring_mod_mix': 0.2,
        'formant_vowel': 'u', 'formant_intensity': 0.5,
        'chorus_voices': 2, 'chorus_depth': 4.0, 'chorus_rate': 0.6,
        'reverb_decay': 0.28, 'reverb_wet': 0.25,
        'stereo_width': 0.4, 'stereo_mode': 'mid_side',
    }}
    m['skill_war_hymn'] = {'template': 'arpeggio', 'params': {
        'note_1': 523, 'note_2': 659, 'note_3': 784, 'note_4': 1047,
        'note_duration': 0.05, 'waveform': 'plucked', 'decay_frac': 0.4,
        'reverb_decay': 0.15, 'reverb_wet': 0.15,
        'stereo_width': 0.5, 'stereo_mode': 'spread',
    }}
    m['skill_cacophony'] = {'template': 'tonal_hit', 'params': {
        'duration': 0.35, 'freq_1': 300, 'freq_2': 427, 'level_2': 0.85,
        'decay_frac': 0.9, 'noise_level': 0.0,
        'ring_mod_freq': 170, 'ring_mod_mix': 0.35,
        'distortion_gain': 2.0, 'distortion_clip': 0.6,
        'chorus_voices': 2,
        'reverb_decay': 0.20, 'reverb_wet': 0.20,
        'stereo_width': 0.5, 'stereo_mode': 'spread',
    }}
    # Blood Knight
    m['skill_blood_strike'] = {'template': 'tonal_hit', 'params': {
        'duration': 0.2, 'freq_1': 600, 'freq_2': 250,
        'level_2': 0.5, 'decay_frac': 0.5, 'noise_level': 0.4,
        'formant_vowel': 'a', 'formant_intensity': 0.3,
        'pitch_env': 'drop', 'pitch_env_amt': 1.5,
        'reverb_decay': 0.14, 'reverb_wet': 0.14,
        'stereo_width': 0.35,
    }}
    m['skill_crimson_veil'] = {'template': 'drone', 'params': {
        'duration': 0.4, 'base_freq': 200, 'waveform': 'sine',
        'mod_freq': 3.0, 'mod_depth': 1.5, 'filter_cutoff': 800,
        'ring_mod_freq': 60, 'ring_mod_mix': 0.2,
        'formant_vowel': 'u', 'formant_intensity': 0.5,
        'env_attack': 0.06, 'env_sustain': 0.4, 'env_release': 0.15,
        'chorus_voices': 3, 'chorus_depth': 4.0, 'chorus_rate': 0.6,
        'reverb_decay': 0.30, 'reverb_wet': 0.28,
        'stereo_width': 0.4, 'stereo_mode': 'mid_side',
    }}
    m['skill_sanguine_burst'] = {'template': 'metallic_body', 'params': {
        'duration': 0.3, 'num_modes': 3,
        'freq_1': 120, 'freq_2': 280, 'freq_3': 550,
        'distortion_gain': 1.5, 'distortion_clip': 0.55,
        'pitch_env': 'drop', 'pitch_env_amt': 2.0,
        'reverb_decay': 0.18, 'reverb_wet': 0.18,
        'stereo_width': 0.45,
    }}
    m['skill_blood_frenzy'] = {'template': 'drone', 'params': {
        'duration': 0.5, 'base_freq': 45, 'waveform': 'sine',
        'mod_depth': 0.0, 'filter_cutoff': 400,
        'ring_mod_freq': 40, 'ring_mod_mix': 0.15,
        'tremolo_rate': 6.0, 'tremolo_depth': 0.3,
        'reverb_decay': 0.22, 'reverb_wet': 0.22,
        'stereo_width': 0.35,
    }}
    # Plague Doctor
    m['skill_miasma'] = {'template': 'drone', 'params': {
        'duration': 0.55, 'base_freq': 120, 'waveform': 'sine',
        'mod_freq': 8.0, 'mod_depth': 3.0, 'filter_cutoff': 600,
        'ring_mod_freq': 35, 'ring_mod_mix': 0.25,
        'formant_vowel': 'u', 'formant_intensity': 0.5,
        'chorus_voices': 2, 'chorus_depth': 4.0, 'chorus_rate': 0.5,
        'reverb_decay': 0.35, 'reverb_wet': 0.30,
        'stereo_width': 0.5, 'stereo_mode': 'spread',
    }}
    m['skill_plague_flask'] = {'template': 'metallic_body', 'params': {
        'duration': 0.3, 'num_modes': 3,
        'freq_1': 2000, 'freq_2': 3200, 'freq_3': 4500,
        'reverb_decay': 0.15, 'reverb_wet': 0.15,
        'stereo_width': 0.35,
    }}
    m['skill_enfeeble'] = {'template': 'drone', 'params': {
        'duration': 0.35, 'base_freq': 200, 'waveform': 'sine',
        'mod_depth': 0.0, 'filter_cutoff': 500,
        'ring_mod_freq': 50, 'ring_mod_mix': 0.2,
        'formant_vowel': 'u', 'formant_intensity': 0.5,
        'reverb_decay': 0.22, 'reverb_wet': 0.22,
        'stereo_width': 0.35, 'stereo_mode': 'mid_side',
    }}
    m['skill_inoculate'] = {'template': 'metallic_body', 'params': {
        'duration': 0.35, 'num_modes': 4,
        'freq_1': 880, 'freq_2': 1320, 'freq_3': 1760, 'freq_4': 2640,
        'chorus_voices': 2, 'chorus_depth': 2.0, 'chorus_rate': 1.2,
        'reverb_decay': 0.22, 'reverb_wet': 0.22,
        'stereo_width': 0.45, 'stereo_mode': 'spread',
    }}
    # Revenant (Phase 25R rework)
    m['skill_grasp_of_the_grave'] = {'template': 'plucked_string', 'params': {
        'duration': 0.4, 'freq': 800, 'brightness': 0.7, 'damping': 0.6,
        'body_size': 0.15,
        'ring_mod_freq': 250, 'ring_mod_mix': 0.3,
        'formant_vowel': 'o', 'formant_intensity': 0.4,
        'chorus_voices': 2, 'chorus_depth': 2.0, 'chorus_rate': 1.5,
        'reverb_decay': 0.25, 'reverb_wet': 0.25,
        'stereo_width': 0.45, 'stereo_mode': 'spread',
    }}
    m['skill_deaths_embrace'] = {'template': 'metallic_body', 'params': {
        'duration': 0.25, 'num_modes': 3,
        'freq_1': 400, 'freq_2': 900, 'freq_3': 1800,
        'distortion_gain': 1.8, 'distortion_clip': 0.55,
        'reverb_decay': 0.18, 'reverb_wet': 0.18,
        'stereo_width': 0.35,
    }}
    m['skill_undying_fury'] = {'template': 'drone', 'params': {
        'duration': 0.5, 'base_freq': 80, 'waveform': 'sine',
        'mod_depth': 0.0, 'filter_cutoff': 400,
        'ring_mod_freq': 30, 'ring_mod_mix': 0.15,
        'tremolo_rate': 4.0, 'tremolo_depth': 0.35,
        'chorus_voices': 3, 'chorus_depth': 5.0, 'chorus_rate': 0.5,
        'reverb_decay': 0.35, 'reverb_wet': 0.30,
        'stereo_width': 0.35, 'stereo_mode': 'mid_side',
    }}
    m['skill_undying_fury_trigger'] = {'template': 'metallic_body', 'params': {
        'duration': 0.6, 'num_modes': 4,
        'freq_1': 523, 'freq_2': 659, 'freq_3': 784, 'freq_4': 1047,
        'pitch_env': 'overshoot', 'pitch_env_amt': 1.5,
        'chorus_voices': 3, 'chorus_depth': 4.0, 'chorus_rate': 0.7,
        'reverb_decay': 0.35, 'reverb_wet': 0.30,
        'stereo_width': 0.55, 'stereo_mode': 'spread',
    }}
    m['skill_soul_rend'] = {'template': 'tonal_hit', 'params': {
        'duration': 0.2, 'freq_1': 500, 'freq_2': 1000,
        'level_2': 0.5, 'decay_frac': 0.5,
        'ring_mod_freq': 200, 'ring_mod_mix': 0.35,
        'reverb_decay': 0.18, 'reverb_wet': 0.18,
        'stereo_width': 0.4,
    }}
    m['skill_soul_rend_empowered'] = {'template': 'tonal_hit', 'params': {
        'duration': 0.3, 'freq_1': 350, 'freq_2': 700,
        'level_2': 0.6, 'decay_frac': 0.55,
        'distortion_gain': 2.0, 'distortion_clip': 0.6,
        'ring_mod_freq': 150, 'ring_mod_mix': 0.4,
        'reverb_decay': 0.22, 'reverb_wet': 0.22,
        'stereo_width': 0.5,
    }}
    # Shaman
    m['skill_healing_totem'] = {'template': 'metallic_body', 'params': {
        'duration': 0.45, 'num_modes': 3,
        'freq_1': 85, 'freq_2': 210, 'freq_3': 480,
        'chorus_voices': 2, 'chorus_depth': 3.0, 'chorus_rate': 0.7,
        'reverb_decay': 0.30, 'reverb_wet': 0.25,
        'stereo_width': 0.45, 'stereo_mode': 'spread',
    }}
    m['skill_searing_totem'] = {'template': 'metallic_body', 'params': {
        'duration': 0.45, 'num_modes': 3,
        'freq_1': 75, 'freq_2': 190, 'freq_3': 380,
        'pitch_env': 'drop', 'pitch_env_amt': 2.0,
        'reverb_decay': 0.22, 'reverb_wet': 0.20,
        'stereo_width': 0.42,
    }}
    m['skill_soul_anchor'] = {'template': 'chord', 'params': {
        'duration': 0.5, 'root_freq': 165, 'interval_2': 1.33, 'interval_3': 1.50,
        'level_2': 0.5, 'level_3': 0.3, 'shimmer': 0.0,
        'env_attack': 0.05, 'env_sustain': 0.4, 'env_release': 0.25,
        'chorus_voices': 3, 'chorus_depth': 4.0, 'chorus_rate': 0.6,
        'reverb_decay': 0.30, 'reverb_wet': 0.28,
        'stereo_width': 0.4, 'stereo_mode': 'mid_side',
    }}
    m['skill_soul_anchor_save'] = {'template': 'metallic_body', 'params': {
        'duration': 0.4, 'num_modes': 3,
        'freq_1': 880, 'freq_2': 1320, 'freq_3': 1760,
        'formant_vowel': 'a', 'formant_intensity': 0.5,
        'chorus_voices': 2, 'chorus_depth': 2.0, 'chorus_rate': 1.2,
        'reverb_decay': 0.28, 'reverb_wet': 0.28,
        'stereo_width': 0.5, 'stereo_mode': 'spread',
    }}
    m['skill_earthgrasp'] = {'template': 'metallic_body', 'params': {
        'duration': 0.35, 'num_modes': 4,
        'freq_1': 60, 'freq_2': 150, 'freq_3': 350, 'freq_4': 700,
        'distortion_gain': 1.5, 'distortion_clip': 0.5,
        'pitch_env': 'drop', 'pitch_env_amt': 2.0,
        'reverb_decay': 0.22, 'reverb_wet': 0.22,
        'stereo_width': 0.35,
    }}

    # ── Buffs / Debuffs ───────────────────────────────
    m['heal'] = {'template': 'plucked_string', 'params': {
        'duration': 0.6, 'frequency': 523, 'brightness': 0.7, 'damping': 0.25,
        'pluck_position': 0.35, 'body_size': 0.3,
        'chorus_voices': 3,
        'reverb_decay': 0.4, 'reverb_wet': 0.3, 'reverb_room': 'cathedral',
        'stereo_width': 0.55, 'stereo_mode': 'spread',
    }}
    m['heal_alt'] = {'template': 'plucked_string', 'params': {
        'duration': 0.7, 'frequency': 440, 'brightness': 0.5, 'damping': 0.3,
        'pluck_position': 0.4, 'body_size': 0.5,
        'chorus_voices': 3,
        'reverb_decay': 0.35, 'reverb_wet': 0.28, 'reverb_room': 'stone_chamber',
        'stereo_width': 0.5, 'stereo_mode': 'spread',
    }}
    m['buff_apply'] = {'template': 'metallic_body', 'params': {
        'duration': 0.4,
        'mode_1_freq': 1047, 'mode_1_amp': 1.0, 'mode_1_decay': 0.12,
        'mode_2_freq': 1568, 'mode_2_amp': 0.6, 'mode_2_decay': 0.08,
        'mode_3_freq': 2093, 'mode_3_amp': 0.3, 'mode_3_decay': 0.05,
        'reverb_decay': 0.25, 'reverb_wet': 0.2, 'reverb_room': 'stone_chamber',
        'stereo_width': 0.45, 'stereo_mode': 'spread',
    }}
    m['buff_shimmer'] = {'template': 'metallic_body', 'params': {
        'duration': 0.5,
        'mode_1_freq': 2200, 'mode_1_amp': 1.0, 'mode_1_decay': 0.18,
        'mode_2_freq': 3350, 'mode_2_amp': 0.7, 'mode_2_decay': 0.12,
        'mode_3_freq': 4700, 'mode_3_amp': 0.4, 'mode_3_decay': 0.07,
        'chorus_voices': 3,
        'reverb_decay': 0.3, 'reverb_wet': 0.25, 'reverb_room': 'cathedral',
        'stereo_width': 0.6, 'stereo_mode': 'spread',
    }}
    m['buff_stats'] = {'template': 'plucked_string', 'params': {
        'duration': 0.35, 'frequency': 523, 'brightness': 0.75, 'damping': 0.45,
        'pluck_position': 0.3, 'body_size': 0.15,
        'reverb_decay': 0.2, 'reverb_wet': 0.18, 'reverb_room': 'stone_chamber',
        'stereo_width': 0.45, 'stereo_mode': 'spread',
    }}
    m['buff_vigor'] = {'template': 'metallic_body', 'params': {
        'duration': 0.35,
        'mode_1_freq': 600, 'mode_1_amp': 1.0, 'mode_1_decay': 0.10,
        'mode_2_freq': 1440, 'mode_2_amp': 0.6, 'mode_2_decay': 0.06,
        'mode_3_freq': 2800, 'mode_3_amp': 0.3, 'mode_3_decay': 0.04,
        'reverb_decay': 0.2, 'reverb_wet': 0.18, 'reverb_room': 'metal_room',
        'stereo_width': 0.4,
    }}
    m['regen'] = {'template': 'plucked_string', 'params': {
        'duration': 0.3, 'frequency': 440, 'brightness': 0.45, 'damping': 0.3,
        'pluck_position': 0.5, 'body_size': 0.5,
        'chorus_voices': 2, 'chorus_depth': 2.0, 'chorus_rate': 0.8,
        'reverb_decay': 0.2, 'reverb_wet': 0.2, 'reverb_room': 'stone_chamber',
        'stereo_width': 0.35, 'stereo_mode': 'spread',
    }}
    m['debuff_enemy'] = {'template': 'metallic_body', 'params': {
        'duration': 0.4,
        'mode_1_freq': 185, 'mode_1_amp': 1.0, 'mode_1_decay': 0.15,
        'mode_2_freq': 437, 'mode_2_amp': 0.6, 'mode_2_decay': 0.10,
        'mode_3_freq': 823, 'mode_3_amp': 0.3, 'mode_3_decay': 0.06,
        'distortion_gain': 1.8,
        'reverb_decay': 0.3, 'reverb_wet': 0.25, 'reverb_room': 'crypt',
        'stereo_width': 0.4, 'stereo_mode': 'mid_side',
    }}
    m['debuff_speed'] = {'template': 'plucked_string', 'params': {
        'duration': 0.35, 'frequency': 100, 'brightness': 0.25, 'damping': 0.15,
        'pluck_position': 0.6, 'body_size': 0.8,
        'chorus_voices': 2, 'chorus_depth': 5.0, 'chorus_rate': 0.4,
        'reverb_decay': 0.25, 'reverb_wet': 0.22, 'reverb_room': 'crypt',
        'stereo_width': 0.3, 'stereo_mode': 'mid_side',
    }}
    m['wither_tick'] = {'template': 'metallic_body', 'params': {
        'duration': 0.15,
        'mode_1_freq': 200, 'mode_1_amp': 1.0, 'mode_1_decay': 0.05,
        'mode_2_freq': 467, 'mode_2_amp': 0.4, 'mode_2_decay': 0.03,
        'distortion_gain': 1.3,
        'reverb_decay': 0.12, 'reverb_wet': 0.15, 'reverb_room': 'crypt',
        'stereo_width': 0.2,
    }}
    m['healing_totem_tick'] = {'template': 'plucked_string', 'params': {
        'duration': 0.25, 'frequency': 550, 'brightness': 0.4, 'damping': 0.35,
        'pluck_position': 0.5, 'body_size': 0.5,
        'reverb_decay': 0.18, 'reverb_wet': 0.18, 'reverb_room': 'stone_chamber',
        'stereo_width': 0.38, 'stereo_mode': 'spread',
    }}

    # ── Items ─────────────────────────────────────────
    m['potion_use'] = {'template': 'drone', 'params': {
        'duration': 0.35, 'base_freq': 400, 'waveform': 'sine',
        'mod_freq': 10.0, 'mod_depth': 0.35, 'filter_cutoff': 1400,
        'reverb_decay': 0.15, 'reverb_wet': 0.12, 'reverb_room': 'tight',
        'stereo_width': 0.3,
    }}
    m['loot_pickup'] = {'template': 'arpeggio', 'params': {
        'note_1': 1200, 'note_2': 1500, 'note_3': 1800, 'note_4': 2200,
        'note_duration': 0.1, 'gap_duration': 0.0, 'decay_frac': 0.7,
        'chorus_voices': 2, 'chorus_depth': 1.5, 'chorus_rate': 1.5,
        'reverb_decay': 0.18, 'reverb_wet': 0.14, 'reverb_room': 'tight',
        'stereo_width': 0.45, 'stereo_mode': 'spread',
    }}
    m['ui_equip'] = {'template': 'percussive', 'params': {
        'duration': 0.15, 'freq': 1000, 'tone_level': 0.2, 'click_level': 0.7,
        'reverb_decay': 0.1, 'reverb_wet': 0.08, 'reverb_room': 'tight',
        'stereo_width': 0.2,
    }}
    m['ui_buy'] = {'template': 'percussive', 'params': {
        'duration': 0.2, 'freq': 1500, 'tone_level': 0.4, 'click_level': 0.0,
        'decay_frac': 0.4,
        'reverb_decay': 0.08, 'reverb_wet': 0.06, 'reverb_room': 'tight',
        'stereo_width': 0.15,
    }}
    m['ui_sell'] = {'template': 'percussive', 'params': {
        'duration': 0.2, 'freq': 1800, 'tone_level': 0.4, 'click_level': 0.0,
        'decay_frac': 0.5,
        'reverb_decay': 0.08, 'reverb_wet': 0.06, 'reverb_room': 'tight',
        'stereo_width': 0.15,
    }}

    # ── Events ────────────────────────────────────────
    m['portal_channel'] = {'template': 'drone', 'params': {
        'duration': 1.5, 'base_freq': 80, 'waveform': 'sine',
        'mod_freq': 55, 'mod_depth': 3.0,
        'formant_vowel': 'o', 'formant_intensity': 0.45,
        'tremolo_rate': 1.5, 'tremolo_depth': 0.55,
        'delay_ms': 220, 'delay_feedback': 0.40, 'delay_wet': 0.30,
        'chorus_voices': 4, 'chorus_depth': 6.0, 'chorus_rate': 0.4,
        'reverb_decay': 0.45, 'reverb_wet': 0.32, 'reverb_room': 'cathedral',
        'stereo_width': 0.6, 'stereo_mode': 'spread',
    }}
    m['portal_open'] = {'template': 'metallic_body', 'params': {
        'duration': 0.6, 'fundamental': 680,
        'mode_2_ratio': 1.76, 'mode_3_ratio': 4.04, 'mode_4_ratio': 5.0,
        'decay_base': 0.25, 'high_decay_mult': 0.5,
        'noise_level': 0.25, 'noise_freq_low': 1500, 'noise_freq_high': 8000,
        'ring_mod_freq': 250, 'ring_mod_mix': 0.35,
        'bitcrush_depth': 14, 'bitcrush_downsample': 2,
        'reverb_decay': 0.35, 'reverb_wet': 0.30, 'reverb_room': 'stone_chamber',
        'stereo_width': 0.6, 'stereo_mode': 'spread',
    }}
    m['wave_clear'] = {'template': 'plucked_string', 'params': {
        'duration': 0.75, 'freq': 523,
        'brightness': 0.75, 'damping': 0.3, 'pluck_position': 0.4, 'body_size': 0.2,
        'chorus_voices': 3, 'chorus_depth': 3.0, 'chorus_rate': 0.8,
        'reverb_decay': 0.35, 'reverb_wet': 0.28, 'reverb_room': 'cathedral',
        'stereo_width': 0.6, 'stereo_mode': 'spread',
    }}
    m['floor_descend'] = {'template': 'metallic_body', 'params': {
        'duration': 0.9, 'fundamental': 75,
        'mode_2_ratio': 1.6, 'mode_3_ratio': 2.47, 'mode_4_ratio': 4.13,
        'decay_base': 0.5, 'high_decay_mult': 0.6,
        'noise_level': 0.15, 'noise_freq_low': 60, 'noise_freq_high': 800,
        'ring_mod_freq': 18, 'ring_mod_mix': 0.3,
        'bitcrush_depth': 12, 'bitcrush_downsample': 3,
        'reverb_decay': 0.45, 'reverb_wet': 0.35, 'reverb_room': 'crypt',
        'stereo_width': 0.45, 'stereo_mode': 'mid_side',
    }}
    m['match_start'] = {'template': 'drone', 'params': {
        'duration': 0.7, 'base_freq': 220, 'waveform': 'sine',
        'mod_freq': 220, 'mod_depth': 2.0,
        'formant_vowel': 'o', 'formant_intensity': 0.5,
        'delay_ms': 120, 'delay_feedback': 0.20, 'delay_wet': 0.15,
        'chorus_voices': 3, 'chorus_depth': 3.0, 'chorus_rate': 1.0,
        'reverb_decay': 0.30, 'reverb_wet': 0.25, 'reverb_room': 'cathedral',
        'stereo_width': 0.6, 'stereo_mode': 'spread',
    }}
    m['match_end'] = {'template': 'metallic_body', 'params': {
        'duration': 0.85, 'fundamental': 180,
        'mode_2_ratio': 2.0, 'mode_3_ratio': 2.53, 'mode_4_ratio': 4.0,
        'decay_base': 0.5, 'high_decay_mult': 0.5,
        'noise_level': 0.08, 'noise_freq_low': 200, 'noise_freq_high': 2000,
        'ring_mod_freq': 90, 'ring_mod_mix': 0.25,
        'delay_ms': 250, 'delay_feedback': 0.35, 'delay_wet': 0.25,
        'reverb_decay': 0.45, 'reverb_wet': 0.35, 'reverb_room': 'crypt',
        'stereo_width': 0.45, 'stereo_mode': 'mid_side',
    }}
    m['door_open'] = {'template': 'noise_texture', 'params': {
        'duration': 0.45, 'noise_color': 'pink',
        'filter_low': 200, 'filter_high': 1500, 'env_attack': 0.02,
        'reverb_decay': 0.35, 'reverb_wet': 0.25,
        'stereo_width': 0.38,
    }}
    m['chest_open'] = {'template': 'tonal_hit', 'params': {
        'duration': 0.5, 'freq_1': 1500, 'freq_2': 2400,
        'level_2': 0.5, 'decay_frac': 1.8, 'noise_level': 0.6,
        'chorus_voices': 2, 'chorus_depth': 2.0, 'chorus_rate': 1.2,
        'reverb_decay': 0.3, 'reverb_wet': 0.22,
        'stereo_width': 0.5, 'stereo_mode': 'spread',
    }}

    # ── UI ────────────────────────────────────────────
    for i in range(1, 6):
        m[f'ui_click_{i}'] = {'template': 'percussive', 'params': {
            'duration': 0.06, 'freq': 1200 + i * 300,
            'tone_level': 0.3, 'click_level': 0.4, 'decay_frac': 0.3,
            'reverb_decay': 0.06, 'reverb_wet': 0.04, 'reverb_room': 'tight',
            'stereo_width': 0.1,
        }}
    m['ui_confirm'] = {'template': 'percussive', 'params': {
        'duration': 0.1, 'freq': 900, 'tone_level': 0.4, 'click_level': 0.3,
        'decay_frac': 0.5,
        'reverb_decay': 0.06, 'reverb_wet': 0.04, 'reverb_room': 'tight',
        'stereo_width': 0.1,
    }}
    m['ui_confirm_2'] = {'template': 'percussive', 'params': {
        'duration': 0.1, 'freq': 1000, 'tone_level': 0.4, 'click_level': 0.3,
        'decay_frac': 0.5,
        'reverb_decay': 0.06, 'reverb_wet': 0.04, 'reverb_room': 'tight',
        'stereo_width': 0.1,
    }}
    m['ui_cancel'] = {'template': 'sweep', 'params': {
        'duration': 0.12, 'freq_start': 600, 'freq_end': 200,
        'use_resonance': False, 'shimmer_freq': 0,
        'reverb_decay': 0.06, 'reverb_wet': 0.04, 'reverb_room': 'tight',
        'stereo_width': 0.1,
    }}
    m['ui_lock'] = {'template': 'percussive', 'params': {
        'duration': 0.08, 'freq': 900, 'tone_level': 0.2, 'click_level': 0.7,
        'decay_frac': 0.4,
        'reverb_decay': 0.06, 'reverb_wet': 0.04, 'reverb_room': 'tight',
        'stereo_width': 0.1,
    }}
    m['ui_select'] = {'template': 'sweep', 'params': {
        'duration': 0.08, 'freq_start': 800, 'freq_end': 2000,
        'use_resonance': False, 'shimmer_freq': 0,
        'env_sustain': 0.5, 'env_release': 0.03,
        'reverb_decay': 0.06, 'reverb_wet': 0.04, 'reverb_room': 'tight',
        'stereo_width': 0.1,
    }}

    # ── Movement ──────────────────────────────────────
    m['step_dungeon'] = {'template': 'noise_texture', 'params': {
        'duration': 0.1, 'noise_color': 'brown',
        'filter_low': 20, 'filter_high': 500, 'decay_frac': 0.3,
        'reverb_decay': 0.15, 'reverb_wet': 0.12,
        'stereo_width': 0.2,
    }}
    m['step_generic'] = {'template': 'noise_texture', 'params': {
        'duration': 0.1, 'noise_color': 'brown',
        'filter_low': 20, 'filter_high': 800, 'decay_frac': 0.3,
        'reverb_decay': 0.15, 'reverb_wet': 0.12,
        'stereo_width': 0.2,
    }}
    m['step_hard'] = {'template': 'noise_texture', 'params': {
        'duration': 0.1, 'noise_color': 'brown',
        'filter_low': 200, 'filter_high': 2000, 'decay_frac': 0.3,
        'reverb_decay': 0.15, 'reverb_wet': 0.12,
        'stereo_width': 0.2,
    }}

    return m


SOUND_TEMPLATE_MAP = _build_template_map()


def generate_from_params(template_name, params):
    """Generate a sound from a template name and custom params dict.

    Merges custom params over template defaults + common defaults.
    Returns a numpy array (mono or stereo).
    """
    gen_fn = TEMPLATE_GENERATORS.get(template_name)
    if not gen_fn:
        raise ValueError(f'Unknown template: {template_name}')

    # Build merged params: common defaults → template defaults → custom
    merged = {}
    for k, v in COMMON_PARAM_SCHEMA.items():
        merged[k] = v['default']
    schema = TEMPLATE_SCHEMAS.get(template_name, {})
    for k, v in schema.get('params', {}).items():
        merged[k] = v['default']
    if params:
        merged.update(params)

    return gen_fn(merged)


def get_sound_editor_info(sound_key, template_override=None):
    """Get the template, merged param schema with current values for a sound key.

    Returns dict with: template, params (list of {key, label, value, ...}).
    Used by the UI to render the editor panel.
    If the key is not in the map but template_override is given, use that
    template with its defaults (for creating brand-new sounds).
    """
    mapping = SOUND_TEMPLATE_MAP.get(sound_key)
    if not mapping:
        if template_override and template_override in TEMPLATE_SCHEMAS:
            mapping = {'template': template_override, 'params': {}}
        else:
            return None

    tmpl_name = mapping['template']
    overrides = mapping.get('params', {})
    schema = TEMPLATE_SCHEMAS.get(tmpl_name, {})

    # Merge: common schema + template schema, with overrides as current values
    param_list = []
    for key, pdef in schema.get('params', {}).items():
        entry = dict(pdef)
        entry['key'] = key
        entry['value'] = overrides.get(key, pdef['default'])
        entry['group'] = 'sound'
        param_list.append(entry)
    for key, pdef in COMMON_PARAM_SCHEMA.items():
        entry = dict(pdef)
        entry['key'] = key
        entry['value'] = overrides.get(key, pdef['default'])
        entry['group'] = 'post'
        param_list.append(entry)

    return {
        'template': tmpl_name,
        'templateLabel': schema.get('label', tmpl_name),
        'templateDescription': schema.get('description', ''),
        'params': param_list,
    }


def get_all_templates_info():
    """Return full template info for the create-new-sound UI."""
    result = {}
    for name, schema in TEMPLATE_SCHEMAS.items():
        params = []
        for key, pdef in schema.get('params', {}).items():
            entry = dict(pdef)
            entry['key'] = key
            entry['value'] = pdef['default']
            entry['group'] = 'sound'
            params.append(entry)
        for key, pdef in COMMON_PARAM_SCHEMA.items():
            entry = dict(pdef)
            entry['key'] = key
            entry['value'] = pdef['default']
            entry['group'] = 'post'
            params.append(entry)
        result[name] = {
            'label': schema['label'],
            'description': schema['description'],
            'params': params,
        }
    return result


# ═══════════════════════════════════════════════════════════════
# Presets — persistent custom param overrides
# ═══════════════════════════════════════════════════════════════

PRESETS_PATH = Path(__file__).parent / 'synth-presets.json'


def load_presets():
    """Load saved presets from disk. Returns dict keyed by sound key."""
    if PRESETS_PATH.exists():
        with open(str(PRESETS_PATH)) as f:
            return json.load(f)
    return {}


def save_presets(presets):
    """Save presets dict to disk."""
    with open(str(PRESETS_PATH), 'w') as f:
        json.dump(presets, f, indent=2)


# ═══════════════════════════════════════════════════════════════
# Main — generate all sounds
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Generate SFX for Hero\'s Call Arena')
    parser.add_argument('--out', default=None,
                        help='Output directory (default: ./generated)')
    parser.add_argument('--key', default=None,
                        help='Generate only this sound key (for single preview)')
    parser.add_argument('--manifest', default='generated-manifest.json',
                        help='Manifest filename')
    parser.add_argument('--params-json', default=None,
                        help='JSON string of custom params (use with --key)')
    parser.add_argument('--template', default=None,
                        help='Template name for create-new-sound (use with --key --params-json)')
    parser.add_argument('--list-templates', action='store_true',
                        help='Print all templates as JSON and exit')
    parser.add_argument('--editor-info', default=None,
                        help='Print editor info for a sound key as JSON and exit')
    args = parser.parse_args()

    # ── Info-only modes ───────────────────────────────
    if args.list_templates:
        print(json.dumps(get_all_templates_info(), indent=2))
        return

    if args.editor_info:
        info = get_sound_editor_info(args.editor_info, template_override=args.template)
        if info:
            print(json.dumps(info, indent=2))
        else:
            print(json.dumps({'error': f'Unknown key: {args.editor_info}'}))
        return

    out_dir = Path(args.out) if args.out else Path(__file__).parent / 'generated'

    # ── Single-key generation with custom params ──────
    if args.key and (args.params_json or args.template):
        custom_params = json.loads(args.params_json) if args.params_json else {}
        tmpl = args.template

        # If no explicit template, look up from the sound-key map
        if not tmpl:
            mapping = SOUND_TEMPLATE_MAP.get(args.key)
            if mapping:
                tmpl = mapping['template']
                # Merge: mapping defaults → custom overrides
                merged = dict(mapping.get('params', {}))
                merged.update(custom_params)
                custom_params = merged
            else:
                print(json.dumps({'error': f'No template mapping for key: {args.key}'}))
                return

        try:
            sig = generate_from_params(tmpl, custom_params)
            # Determine category + filename from existing table or custom
            table = {s['key']: s for s in build_sound_table()}
            entry = table.get(args.key)
            cat = entry['category'] if entry else 'custom'
            fname = entry['filename'] if entry else f'{args.key}.wav'
            rel_path = f'{cat}/{fname}'
            full_path = out_dir / rel_path
            _write_wav(str(full_path), sig)
            dur = sig.shape[1] / RATE if sig.ndim == 2 else len(sig) / RATE
            result = {
                'success': True,
                'key': args.key,
                'path': f'/audio-synth/{rel_path}',
                'category': cat,
                'filename': fname,
                'duration': round(dur, 3),
            }
            print(json.dumps(result))
        except Exception as e:
            print(json.dumps({'success': False, 'error': str(e)}))
        return

    # ── Standard batch generation ─────────────────────
    sounds = build_sound_table()

    if args.key:
        sounds = [s for s in sounds if s['key'] == args.key]
        if not sounds:
            print(f'Unknown key: {args.key}')
            return

    manifest_entries = []
    print(f'Generating {len(sounds)} sounds into {out_dir}...')

    for s in sounds:
        rel_path = f"{s['category']}/{s['filename']}"
        full_path = out_dir / rel_path
        try:
            sig = s['generator']()
            _write_wav(str(full_path), sig)
            duration = sig.shape[1] / RATE if sig.ndim == 2 else len(sig) / RATE
            # Include editor info in manifest
            editor = get_sound_editor_info(s['key'])
            manifest_entries.append({
                'key': s['key'],
                'category': s['category'],
                'filename': s['filename'],
                'path': f'/audio-synth/{rel_path}',
                'description': s['description'],
                'duration': round(duration, 3),
                'editable': editor is not None,
                'template': editor['template'] if editor else None,
            })
            print(f'  [OK] {s["key"]:30s} -> {rel_path}')
        except Exception as e:
            print(f'  [FAIL] {s["key"]:30s} -- ERROR: {e}')

    # Write manifest
    manifest_path = out_dir / args.manifest
    with open(str(manifest_path), 'w') as f:
        json.dump({
            'version': 2,
            'generated': True,
            'totalCount': len(manifest_entries),
            'sounds': manifest_entries,
        }, f, indent=2)

    print(f'\nDone: {len(manifest_entries)} sounds generated')
    print(f'  Manifest: {manifest_path}')


if __name__ == '__main__':
    main()
