// ─────────────────────────────────────────────────────────
// ProjectilePanel.jsx — Controls for projectile preview mode
//
// Lets the user configure:
//   • Trail preset (dropdown from library)
//   • Head preset (dropdown)
//   • Impact preset + extras (dropdown)
//   • Speed (px/s slider)
//   • Arc (0–0.5 slider)
//
// Also shows a "Game Projectiles" library — pre-configured
// projectiles copied from the real particle-effects.json
// mappings so you can preview any in-game projectile.
// ─────────────────────────────────────────────────────────

import React, { useState, useCallback } from 'react';

/**
 * Built-in projectile configurations from the game's particle-effects.json.
 * Each entry mirrors a skill/combat mapping that has a `projectile` block.
 */
const GAME_PROJECTILES = [
  {
    name: 'Ranged Auto-Attack',
    skill: 'ranged_attack',
    trail: 'arrow-trail',
    head: 'arrow-head',
    impact: 'ranged-hit',
    extras: [],
    speed: 350,
    arc: 0.15,
  },
  {
    name: 'Power Shot',
    skill: 'power_shot',
    trail: 'power-shot-trail',
    head: 'power-shot-head',
    impact: 'power-shot-impact',
    extras: [],
    speed: 400,
    arc: 0.2,
  },
  {
    name: 'Crippling Shot',
    skill: 'crippling_shot',
    trail: 'crip-shot-trail',
    head: 'ice-arrow-head',
    impact: 'crippling-shot-impact',
    extras: ['ice-shard'],
    speed: 350,
    arc: 0.15,
  },
  {
    name: 'Rebuke',
    skill: 'rebuke',
    trail: 'rebuke-trail',
    head: 'holy-head',
    impact: 'holy-smite',
    extras: [],
    speed: 450,
    arc: 0.05,
  },
  {
    name: 'Exorcism',
    skill: 'exorcism',
    trail: 'exorcism-trail',
    head: 'holy-head',
    impact: 'exorcism-flare',
    extras: [],
    speed: 400,
    arc: 0,
  },
  {
    name: 'Wither',
    skill: 'wither',
    trail: 'wither-trail',
    head: 'dark-head',
    impact: 'wither-curse',
    extras: [],
    speed: 300,
    arc: 0.08,
  },
  {
    name: 'Soul Reap',
    skill: 'soul_reap',
    trail: 'soul-reap-trail',
    head: 'dark-head',
    impact: 'soul-reap-rend',
    extras: [],
    speed: 350,
    arc: 0,
  },
  {
    name: 'Venom Gaze',
    skill: 'venom_gaze',
    trail: 'venom-trail',
    head: 'venom-head',
    impact: 'venom-gaze-bolt',
    extras: [],
    speed: 300,
    arc: 0,
  },
];

export default function ProjectilePanel({
  config,
  onConfigChange,
  presetLibrary,
  onLaunch,
}) {
  const [showGameLib, setShowGameLib] = useState(true);
  const [selectedGame, setSelectedGame] = useState(null);

  // All preset names for dropdowns
  const presetNames = presetLibrary.map(p => p.name).sort();

  const update = useCallback((field, value) => {
    onConfigChange({ ...config, [field]: value });
  }, [config, onConfigChange]);

  const loadGameProjectile = useCallback((entry) => {
    setSelectedGame(entry.name);
    onConfigChange({
      trailPreset: entry.trail,
      headPreset: entry.head || '',
      impactPreset: entry.impact,
      impactExtras: entry.extras || [],
      speed: entry.speed,
      arc: entry.arc,
    });
  }, [onConfigChange]);

  return (
    <div className="projectile-panel">
      {/* ── Launch Button ── */}
      <div className="proj-launch-section">
        <button className="btn-launch-projectile" onClick={onLaunch}>
          🚀 Launch Projectile
        </button>
      </div>

      {/* ── Quick Config ── */}
      <div className="proj-section">
        <h3 className="proj-section-title">Projectile Config</h3>

        <div className="proj-field">
          <label className="proj-label">Trail Preset</label>
          <select
            className="proj-select"
            value={config.trailPreset || ''}
            onChange={e => update('trailPreset', e.target.value)}
          >
            <option value="">(none)</option>
            {presetNames.map(n => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>

        <div className="proj-field">
          <label className="proj-label">Head Preset</label>
          <select
            className="proj-select"
            value={config.headPreset || ''}
            onChange={e => update('headPreset', e.target.value)}
          >
            <option value="">(none)</option>
            {presetNames.map(n => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>

        <div className="proj-field">
          <label className="proj-label">Impact Preset</label>
          <select
            className="proj-select"
            value={config.impactPreset || ''}
            onChange={e => update('impactPreset', e.target.value)}
          >
            <option value="">(none)</option>
            {presetNames.map(n => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>

        <div className="proj-field">
          <label className="proj-label">Impact Extras</label>
          <input
            type="text"
            className="proj-input"
            placeholder="comma-separated preset names"
            value={(config.impactExtras || []).join(', ')}
            onChange={e => update('impactExtras', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
          />
        </div>

        <div className="proj-field">
          <label className="proj-label">
            Speed <span className="proj-value">{config.speed || 350} px/s</span>
          </label>
          <input
            type="range"
            className="proj-slider"
            min={50}
            max={800}
            step={10}
            value={config.speed || 350}
            onChange={e => update('speed', Number(e.target.value))}
          />
        </div>

        <div className="proj-field">
          <label className="proj-label">
            Arc <span className="proj-value">{(config.arc || 0).toFixed(2)}</span>
          </label>
          <input
            type="range"
            className="proj-slider"
            min={0}
            max={0.5}
            step={0.01}
            value={config.arc || 0}
            onChange={e => update('arc', Number(e.target.value))}
          />
          <div className="proj-arc-labels">
            <span>Flat</span>
            <span>High Lob</span>
          </div>
        </div>
      </div>

      {/* ── Game Projectiles Library ── */}
      <div className="proj-section">
        <div
          className="proj-section-header clickable"
          onClick={() => setShowGameLib(!showGameLib)}
        >
          <h3 className="proj-section-title">
            {showGameLib ? '▾' : '▸'} Game Projectiles
          </h3>
          <span className="proj-count">{GAME_PROJECTILES.length}</span>
        </div>

        {showGameLib && (
          <div className="proj-game-list">
            {GAME_PROJECTILES.map((entry) => (
              <div
                key={entry.name}
                className={`proj-game-item ${selectedGame === entry.name ? 'active' : ''}`}
                onClick={() => loadGameProjectile(entry)}
              >
                <div className="proj-game-name">{entry.name}</div>
                <div className="proj-game-detail">
                  <span className="proj-game-tag">{entry.trail || '—'}</span>
                  <span className="proj-game-speed">{entry.speed}px/s</span>
                  {entry.arc > 0 && <span className="proj-game-arc">arc {entry.arc}</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Tips ── */}
      <div className="proj-tips">
        <p>🎯 <strong>Drag</strong> the A/B handles on the canvas to change distance & angle.</p>
        <p>🖱️ <strong>Click</strong> the canvas background to fire.</p>
        <p>⚡ Trail/Head presets are <em>continuous</em> emitters that follow the projectile. Impact fires on arrival.</p>
      </div>
    </div>
  );
}
