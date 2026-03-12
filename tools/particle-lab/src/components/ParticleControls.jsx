// ─────────────────────────────────────────────────────────
// ParticleControls.jsx — Particle tab: shape, size, lifetime, rotation, trails
// ─────────────────────────────────────────────────────────

import React from 'react';
import { Slider, RangeSlider, Select } from './Controls.jsx';

const SHAPES = ['circle', 'square', 'triangle', 'star', 'line'];
const EASINGS = ['linear', 'easeInQuad', 'easeOutQuad', 'easeInOutQuad',
  'easeInCubic', 'easeOutCubic', 'easeInOutCubic',
  'easeOutElastic', 'easeOutBounce', 'easeInExpo', 'easeOutExpo'];

export default function ParticleControls({ preset, updatePreset }) {
  const pc = preset.particle || {};

  const set = (path, value) => {
    updatePreset(p => {
      if (!p.particle) p.particle = {};
      const parts = path.split('.');
      let obj = p.particle;
      for (let i = 0; i < parts.length - 1; i++) {
        if (!obj[parts[i]]) obj[parts[i]] = {};
        obj = obj[parts[i]];
      }
      obj[parts[parts.length - 1]] = value;
    });
  };

  return (
    <div className="controls-section">
      <h3 className="section-title">Shape</h3>

      <Select
        label="Shape"
        value={pc.shape || 'circle'}
        options={SHAPES}
        onChange={v => set('shape', v)}
        title="Visual shape of each particle"
      />

      <h3 className="section-title">Lifetime</h3>

      <RangeSlider
        label="Lifetime"
        minVal={pc.lifetime?.min ?? 0.3}
        maxVal={pc.lifetime?.max ?? 1.0}
        min={0.05} max={10} step={0.05}
        onChangeMin={v => set('lifetime.min', v)}
        onChangeMax={v => set('lifetime.max', v)}
        title="How long each particle lives (seconds)"
      />

      <h3 className="section-title">Size</h3>

      <RangeSlider
        label="Start Size"
        minVal={pc.size?.start?.min ?? 3}
        maxVal={pc.size?.start?.max ?? 6}
        min={0.5} max={50} step={0.5}
        onChangeMin={v => set('size.start.min', v)}
        onChangeMax={v => set('size.start.max', v)}
        title="Initial particle size range"
      />

      <RangeSlider
        label="End Size"
        minVal={pc.size?.end?.min ?? 0}
        maxVal={pc.size?.end?.max ?? 1}
        min={0} max={50} step={0.5}
        onChangeMin={v => set('size.end.min', v)}
        onChangeMax={v => set('size.end.max', v)}
        title="Final particle size range"
      />

      <Select
        label="Size Easing"
        value={pc.size?.easing || 'easeOutQuad'}
        options={EASINGS}
        onChange={v => set('size.easing', v)}
        title="How size transitions over the particle's lifetime"
      />

      <h3 className="section-title">Rotation</h3>

      <RangeSlider
        label="Rotation Speed"
        minVal={pc.rotation?.speed?.min ?? 0}
        maxVal={pc.rotation?.speed?.max ?? 0}
        min={-10} max={10} step={0.1}
        onChangeMin={v => set('rotation.speed.min', v)}
        onChangeMax={v => set('rotation.speed.max', v)}
        title="Angular velocity (radians/sec)"
      />

      <h3 className="section-title">Trail</h3>

      <Slider
        label="Trail Length"
        value={pc.trail?.length || 0}
        min={0} max={20} step={1}
        onChange={v => set('trail.length', v)}
        defaultValue={0}
        title="Number of trail positions to render behind each particle"
      />
    </div>
  );
}
