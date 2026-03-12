// ─────────────────────────────────────────────────────────
// PhysicsControls.jsx — Physics tab: gravity, friction, wind, bounce
// ─────────────────────────────────────────────────────────

import React from 'react';
import { Slider } from './Controls.jsx';

export default function PhysicsControls({ preset, updatePreset }) {
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
      <h3 className="section-title">Gravity</h3>

      <Slider
        label="Gravity X"
        value={em.gravity?.x ?? 0}
        min={-200} max={200} step={1}
        onChange={v => set('gravity.x', v)}
        defaultValue={0}
        title="Horizontal gravitational pull (px/sec²)"
      />

      <Slider
        label="Gravity Y"
        value={em.gravity?.y ?? 0}
        min={-200} max={200} step={1}
        onChange={v => set('gravity.y', v)}
        defaultValue={0}
        title="Vertical gravitational pull. Positive = downward."
      />

      <h3 className="section-title">Damping</h3>

      <Slider
        label="Friction"
        value={em.friction ?? 0}
        min={0} max={0.2} step={0.001}
        onChange={v => set('friction', v)}
        defaultValue={0}
        title="Velocity damping per frame. Higher = particles slow faster."
      />

      <h3 className="section-title">Wind</h3>

      <Slider
        label="Wind X"
        value={em.wind?.x ?? 0}
        min={-100} max={100} step={1}
        onChange={v => set('wind.x', v)}
        defaultValue={0}
        title="Constant horizontal force applied to all particles."
      />

      <h3 className="section-title">Performance</h3>

      <Slider
        label="Max Particles"
        value={preset.maxParticles || 500}
        min={10} max={2000} step={10}
        onChange={v => updatePreset(p => { p.maxParticles = v; })}
        defaultValue={500}
        title="Object pool size. Caps the maximum concurrent particles."
      />
    </div>
  );
}
