// ─────────────────────────────────────────────────────────
// ChampionTypeEditor.jsx — Edit champion type definitions
// ─────────────────────────────────────────────────────────

import React, { useState } from 'react';

const CHAMPION_FIELDS = [
  { key: 'damage_bonus',          label: 'Damage Bonus',        type: 'float', step: 0.05 },
  { key: 'enrage_threshold',      label: 'Enrage HP Threshold', type: 'float', step: 0.05 },
  { key: 'enrage_damage_bonus',   label: 'Enrage Damage Bonus', type: 'float', step: 0.05 },
  { key: 'cooldown_reduction',    label: 'Cooldown Reduction',  type: 'int',   step: 1 },
  { key: 'dodge_chance',          label: 'Dodge Chance',        type: 'float', step: 0.05 },
  { key: 'hp_multiplier',         label: 'HP Multiplier',       type: 'float', step: 0.1 },
  { key: 'armor_bonus',           label: 'Armor Bonus',         type: 'int',   step: 1 },
  { key: 'death_explosion_damage', label: 'Death Explosion Damage', type: 'int', step: 5 },
  { key: 'death_explosion_radius', label: 'Death Explosion Radius', type: 'int', step: 1 },
];

export default function ChampionTypeEditor({ config, meta, onUpdate }) {
  const [selected, setSelected] = useState(null);
  const championTypes = config?.champion_types || {};
  const ct = selected ? championTypes[selected] : null;

  const updateType = (id, field, value) => {
    const updated = {
      ...config,
      champion_types: {
        ...config.champion_types,
        [id]: { ...config.champion_types[id], [field]: value }
      }
    };
    onUpdate(updated);
  };

  return (
    <div className="champion-editor-layout">
      <div className="champion-list">
        <div className="browser-header">
          <h3>Champion Types ({Object.keys(championTypes).length})</h3>
        </div>
        <div className="browser-list">
          {Object.entries(championTypes).map(([id, data]) => (
            <div
              key={id}
              className={`browser-item ${selected === id ? 'selected' : ''}`}
              onClick={() => setSelected(id)}
            >
              <div
                className="enemy-color-dot"
                style={{ background: data.visual_tint || '#888' }}
              />
              <div className="enemy-info">
                <div className="enemy-name">{data.name}</div>
                <div className="enemy-role">{id}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="champion-detail">
        {!ct && (
          <div className="empty-state">
            <h3>Select a champion type to edit</h3>
            <p>Champion types define how Champion-tier enemies behave differently.</p>
          </div>
        )}

        {ct && (
          <>
            <div className="card mb-8">
              <h4 style={{ color: ct.visual_tint }}>{ct.name}</h4>
              <div className="form-row">
                <div className="form-group">
                  <label>Name</label>
                  <input type="text" value={ct.name} onChange={e => updateType(selected, 'name', e.target.value)} />
                </div>
                <div className="form-group">
                  <label>Visual Tint</label>
                  <div className="flex-row gap-sm">
                    <input type="color" value={ct.visual_tint || '#888888'} onChange={e => updateType(selected, 'visual_tint', e.target.value)} />
                    <input type="text" value={ct.visual_tint || ''} onChange={e => updateType(selected, 'visual_tint', e.target.value)} style={{ width: 90 }} />
                  </div>
                </div>
              </div>
              <label>
                <input
                  type="checkbox"
                  checked={!!ct.phase_through_units}
                  onChange={e => updateType(selected, 'phase_through_units', e.target.checked || undefined)}
                />
                Phase Through Units
              </label>
            </div>

            <div className="card mb-8">
              <h4>Stats</h4>
              <div className="stat-grid">
                {CHAMPION_FIELDS.map(f => {
                  if (ct[f.key] === undefined && f.key !== 'damage_bonus') return null;
                  return (
                    <div key={f.key} className="stat-slider-row">
                      <label>{f.label}</label>
                      <input
                        type="number"
                        step={f.step}
                        value={ct[f.key] ?? ''}
                        onChange={e => {
                          const val = e.target.value === '' ? undefined : (f.type === 'int' ? parseInt(e.target.value) : parseFloat(e.target.value));
                          updateType(selected, f.key, val);
                        }}
                        className="stat-num-input"
                        style={{ width: 100 }}
                      />
                    </div>
                  );
                })}
              </div>
              <p className="text-dim" style={{ fontSize: 12, marginTop: 8 }}>
                Leave fields blank/undefined if this champion type doesn't have that modifier.
              </p>
            </div>

            {/* Summary */}
            <div className="card">
              <h4>Effect Summary</h4>
              <div className="summary-text">
                <strong>{ct.name}</strong> champions
                {ct.damage_bonus ? ` deal ${(ct.damage_bonus * 100).toFixed(0)}% bonus damage` : ''}
                {ct.hp_multiplier ? `, have ${ct.hp_multiplier}× HP` : ''}
                {ct.armor_bonus ? `, +${ct.armor_bonus} armor` : ''}
                {ct.dodge_chance ? `, ${(ct.dodge_chance * 100).toFixed(0)}% dodge chance` : ''}
                {ct.cooldown_reduction ? `, -${ct.cooldown_reduction} turn cooldowns` : ''}
                {ct.phase_through_units ? ', can phase through units' : ''}
                {ct.enrage_threshold ? `, enrage below ${(ct.enrage_threshold * 100).toFixed(0)}% HP for +${((ct.enrage_damage_bonus || 0) * 100).toFixed(0)}% damage` : ''}
                {ct.death_explosion_damage ? `, explode on death for ${ct.death_explosion_damage} damage in ${ct.death_explosion_radius}-tile radius` : ''}
                .
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
