// ─────────────────────────────────────────────────────────
// ColorControls.jsx — Colors tab: gradient editor, alpha, blend mode
// ─────────────────────────────────────────────────────────

import React from 'react';
import { Slider, Select } from './Controls.jsx';

const BLEND_MODES = [
  { value: 'lighter', label: 'Additive (lighter)' },
  { value: 'source-over', label: 'Normal (source-over)' },
  { value: 'screen', label: 'Screen' },
  { value: 'multiply', label: 'Multiply' },
];

const EASINGS = ['linear', 'easeInQuad', 'easeOutQuad', 'easeInOutQuad',
  'easeInCubic', 'easeOutCubic', 'easeInOutCubic',
  'easeOutElastic', 'easeOutBounce'];

export default function ColorControls({ preset, updatePreset }) {
  const pc = preset.particle || {};
  const gradient = pc.color?.gradient || [
    { stop: 0, color: '#ffffff' },
    { stop: 1, color: '#ff6600' },
  ];

  const setGradientStop = (index, field, value) => {
    updatePreset(p => {
      if (!p.particle) p.particle = {};
      if (!p.particle.color) p.particle.color = {};
      if (!p.particle.color.gradient) {
        p.particle.color.gradient = [
          { stop: 0, color: '#ffffff' },
          { stop: 1, color: '#ff6600' },
        ];
      }
      p.particle.color.gradient[index][field] = value;
    });
  };

  const addGradientStop = () => {
    updatePreset(p => {
      if (!p.particle) p.particle = {};
      if (!p.particle.color) p.particle.color = {};
      if (!p.particle.color.gradient) {
        p.particle.color.gradient = [{ stop: 0, color: '#ffffff' }];
      }
      const stops = p.particle.color.gradient;
      // Insert at midpoint of last two stops
      const lastStop = stops.length > 0 ? stops[stops.length - 1].stop : 0;
      const newStop = Math.min(1, lastStop + 0.1);
      stops.push({ stop: newStop, color: '#888888' });
      // Sort by stop
      stops.sort((a, b) => a.stop - b.stop);
    });
  };

  const removeGradientStop = (index) => {
    updatePreset(p => {
      if (p.particle?.color?.gradient && p.particle.color.gradient.length > 2) {
        p.particle.color.gradient.splice(index, 1);
      }
    });
  };

  // Generate CSS gradient for preview bar
  const gradientCSS = gradient
    .map(s => `${s.color} ${s.stop * 100}%`)
    .join(', ');

  return (
    <div className="controls-section">
      <h3 className="section-title">Color Gradient</h3>

      {/* Gradient preview bar */}
      <div
        className="gradient-preview"
        style={{ background: `linear-gradient(to right, ${gradientCSS})` }}
      />

      {/* Gradient stops */}
      <div className="gradient-stops">
        {gradient.map((stop, i) => (
          <div key={i} className="gradient-stop-row">
            <input
              type="color"
              className="color-picker"
              value={stop.color}
              onChange={e => setGradientStop(i, 'color', e.target.value)}
              title={`Color at ${Math.round(stop.stop * 100)}%`}
            />
            <input
              type="range"
              className="slider-input"
              min={0} max={1} step={0.01}
              value={stop.stop}
              onChange={e => setGradientStop(i, 'stop', Number(e.target.value))}
            />
            <span className="stop-value">{Math.round(stop.stop * 100)}%</span>
            {gradient.length > 2 && (
              <button
                className="btn-remove-stop"
                onClick={() => removeGradientStop(i)}
                title="Remove this color stop"
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>

      <button className="btn-add-stop" onClick={addGradientStop}>
        + Add Color Stop
      </button>

      <h3 className="section-title">Alpha</h3>

      <Slider
        label="Start Alpha"
        value={pc.alpha?.start ?? 1}
        min={0} max={1} step={0.01}
        onChange={v => updatePreset(p => {
          if (!p.particle) p.particle = {};
          if (!p.particle.alpha) p.particle.alpha = {};
          p.particle.alpha.start = v;
        })}
        defaultValue={1}
        title="Initial opacity"
      />

      <Slider
        label="End Alpha"
        value={pc.alpha?.end ?? 0}
        min={0} max={1} step={0.01}
        onChange={v => updatePreset(p => {
          if (!p.particle) p.particle = {};
          if (!p.particle.alpha) p.particle.alpha = {};
          p.particle.alpha.end = v;
        })}
        defaultValue={0}
        title="Final opacity"
      />

      <Select
        label="Alpha Easing"
        value={pc.alpha?.easing || 'easeOutCubic'}
        options={EASINGS}
        onChange={v => updatePreset(p => {
          if (!p.particle) p.particle = {};
          if (!p.particle.alpha) p.particle.alpha = {};
          p.particle.alpha.easing = v;
        })}
        title="How opacity transitions over the particle's lifetime"
      />

      <h3 className="section-title">Blend Mode</h3>

      <Select
        label="Blend"
        value={pc.blendMode || 'lighter'}
        options={BLEND_MODES}
        onChange={v => updatePreset(p => {
          if (!p.particle) p.particle = {};
          p.particle.blendMode = v;
        })}
        title="Canvas composite operation. 'Lighter' = additive glow."
      />
    </div>
  );
}
