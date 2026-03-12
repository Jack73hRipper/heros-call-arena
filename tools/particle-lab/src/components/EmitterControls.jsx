// ─────────────────────────────────────────────────────────
// EmitterControls.jsx — Emitter tab: spawn mode, shape, rate, direction
// ─────────────────────────────────────────────────────────

import React from 'react';
import { Slider, RangeSlider, Select, Toggle } from './Controls.jsx';

const SPAWN_SHAPES = ['point', 'circle', 'ring', 'line', 'rect'];

export default function EmitterControls({ preset, updatePreset }) {
  const em = preset.emitter || {};

  const set = (path, value) => {
    updatePreset(p => {
      if (!p.emitter) p.emitter = {};
      const parts = path.split('.');
      let obj = p.emitter;
      for (let i = 0; i < parts.length - 1; i++) {
        if (!obj[parts[i]]) obj[parts[i]] = {};
        obj = obj[parts[i]];
      }
      obj[parts[parts.length - 1]] = value;
    });
  };

  return (
    <div className="controls-section">
      <h3 className="section-title">Spawn Mode</h3>

      <Toggle
        label="Burst Mode"
        value={em.burstMode !== false}
        onChange={v => set('burstMode', v)}
        title="Burst: emit all particles at once. Continuous: emit over time."
      />

      {em.burstMode !== false ? (
        <Slider
          label="Burst Count"
          value={em.burstCount || 20}
          min={1} max={200} step={1}
          onChange={v => set('burstCount', v)}
          defaultValue={20}
          title="Number of particles per burst"
        />
      ) : (
        <Slider
          label="Spawn Rate"
          value={em.spawnRate || 30}
          min={1} max={500} step={1}
          onChange={v => set('spawnRate', v)}
          defaultValue={30}
          title="Particles per second"
        />
      )}

      <Slider
        label="Duration"
        value={preset.duration || 1}
        min={0.1} max={10} step={0.1}
        onChange={v => updatePreset(p => { p.duration = v; })}
        defaultValue={1}
        title="How long the emitter runs (seconds)"
      />

      <Toggle
        label="Loop"
        value={preset.loop || false}
        onChange={v => updatePreset(p => { p.loop = v; })}
        title="Repeat when duration ends"
      />

      <h3 className="section-title">Spawn Shape</h3>

      <Select
        label="Shape"
        value={em.spawnShape || 'point'}
        options={SPAWN_SHAPES}
        onChange={v => set('spawnShape', v)}
        title="Area shape where particles spawn"
      />

      {(em.spawnShape === 'circle' || em.spawnShape === 'ring') && (
        <Slider
          label="Radius"
          value={em.spawnRadius || 0}
          min={0} max={100} step={1}
          onChange={v => set('spawnRadius', v)}
          defaultValue={0}
          title="Spawn area radius"
        />
      )}

      {(em.spawnShape === 'line' || em.spawnShape === 'rect') && (
        <Slider
          label="Width"
          value={em.spawnWidth || 0}
          min={0} max={200} step={1}
          onChange={v => set('spawnWidth', v)}
          defaultValue={0}
          title="Spawn area width"
        />
      )}

      {em.spawnShape === 'rect' && (
        <Slider
          label="Height"
          value={em.spawnHeight || 0}
          min={0} max={200} step={1}
          onChange={v => set('spawnHeight', v)}
          defaultValue={0}
          title="Spawn area height"
        />
      )}

      <h3 className="section-title">Direction & Speed</h3>

      <RangeSlider
        label="Emit Angle"
        minVal={em.angle?.min ?? 0}
        maxVal={em.angle?.max ?? 360}
        min={0} max={360} step={1}
        onChangeMin={v => set('angle.min', v)}
        onChangeMax={v => set('angle.max', v)}
        title="Direction range in degrees (0=right, 90=down, 270=up)"
      />

      <RangeSlider
        label="Speed"
        minVal={em.speed?.min ?? 20}
        maxVal={em.speed?.max ?? 80}
        min={0} max={500} step={1}
        onChangeMin={v => set('speed.min', v)}
        onChangeMax={v => set('speed.max', v)}
        title="Initial particle speed (px/sec)"
      />
    </div>
  );
}
