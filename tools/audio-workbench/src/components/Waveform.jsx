// ─────────────────────────────────────────────────────────
// Waveform.jsx — Web Audio waveform visualization
// ─────────────────────────────────────────────────────────

import React, { useRef, useEffect } from 'react';

const CANVAS_W = 280;
const CANVAS_H = 48;
const BAR_COLOR = '#6e8efb';
const BAR_COLOR_PLAYING = '#ff6b6b';

/**
 * Draws waveform bars from an AudioBuffer.
 * If no buffer, draws a flat line.
 */
function drawWaveform(canvas, audioBuffer, isPlaying) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  if (!audioBuffer) {
    ctx.strokeStyle = '#333';
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();
    return;
  }

  const data = audioBuffer.getChannelData(0);
  const barCount = Math.min(80, w / 3);
  const samplesPerBar = Math.floor(data.length / barCount);
  const barWidth = Math.max(2, (w / barCount) - 1);
  const color = isPlaying ? BAR_COLOR_PLAYING : BAR_COLOR;

  for (let i = 0; i < barCount; i++) {
    let sum = 0;
    const start = i * samplesPerBar;
    for (let j = start; j < start + samplesPerBar && j < data.length; j++) {
      sum += Math.abs(data[j]);
    }
    const avg = sum / samplesPerBar;
    const barH = Math.max(1, avg * h * 1.8);
    const x = i * (w / barCount);
    ctx.fillStyle = color;
    ctx.fillRect(x, (h - barH) / 2, barWidth, barH);
  }
}

/**
 * Waveform — renders amplitude bars of a decoded audio buffer.
 *
 * Props:
 *  - src: string URL of audio file
 *  - getAudioCtx: () => AudioContext
 *  - isPlaying: boolean
 *  - compact: boolean (uses smaller canvas)
 */
export default function Waveform({ src, getAudioCtx, isPlaying = false, compact = false }) {
  const canvasRef = useRef(null);
  const bufferRef = useRef(null);
  const prevSrcRef = useRef(null);

  const w = compact ? 140 : CANVAS_W;
  const h = compact ? 32 : CANVAS_H;

  useEffect(() => {
    if (!src || src === prevSrcRef.current) {
      // Just redraw on isPlaying change
      if (canvasRef.current) drawWaveform(canvasRef.current, bufferRef.current, isPlaying);
      return;
    }
    prevSrcRef.current = src;
    bufferRef.current = null;

    const ctx = getAudioCtx();
    let cancelled = false;

    fetch(src)
      .then(r => r.arrayBuffer())
      .then(buf => ctx.decodeAudioData(buf))
      .then(decoded => {
        if (cancelled) return;
        bufferRef.current = decoded;
        if (canvasRef.current) drawWaveform(canvasRef.current, decoded, isPlaying);
      })
      .catch(() => {
        if (canvasRef.current) drawWaveform(canvasRef.current, null, false);
      });

    return () => { cancelled = true; };
  }, [src, getAudioCtx, isPlaying]);

  // Redraw when playing state changes
  useEffect(() => {
    if (canvasRef.current) drawWaveform(canvasRef.current, bufferRef.current, isPlaying);
  }, [isPlaying]);

  return (
    <canvas
      ref={canvasRef}
      className="wb-waveform"
      width={w}
      height={h}
      style={{ width: w, height: h }}
    />
  );
}
