// ─────────────────────────────────────────────────────────
// AffixEditor.jsx — Browse, edit, create affixes
// ─────────────────────────────────────────────────────────

import React, { useState, useMemo } from 'react';

// ── Category metadata ────────────────────────────────────
const AFFIX_CATEGORIES = [
  'offensive', 'defensive', 'mobility', 'on_death', 'on_hit',
  'retaliation', 'disruption', 'debuff', 'sustain',
];

const CATEGORY_META = {
  offensive:   { label: 'Offensive',   color: '#ff4444', icon: '⚔️' },
  defensive:   { label: 'Defensive',   color: '#4488ff', icon: '🛡️' },
  mobility:    { label: 'Mobility',    color: '#44ddcc', icon: '💨' },
  on_death:    { label: 'On Death',    color: '#cc44ff', icon: '💀' },
  on_hit:      { label: 'On Hit',      color: '#ff8844', icon: '🎯' },
  retaliation: { label: 'Retaliation', color: '#dd6644', icon: '🔥' },
  disruption:  { label: 'Disruption',  color: '#aa44dd', icon: '⚡' },
  debuff:      { label: 'Debuff',      color: '#cc6688', icon: '🩸' },
  sustain:     { label: 'Sustain',     color: '#44cc66', icon: '💚' },
};

// ── Effect type metadata: labels, descriptions, icons ────
const EFFECT_TYPES = [
  'stat_multiplier', 'cooldown_reduction_flat', 'aura_ally_buff', 'aura_enemy_debuff',
  'on_hit_extend_cooldowns', 'on_hit_slow', 'on_death_explosion', 'life_steal_pct',
  'grant_ward', 'auto_shadow_step', 'set_stat', 'extra_ranged_target', 'hp_regen_pct',
];

const EFFECT_META = {
  stat_multiplier: {
    label: 'Stat Multiplier',
    icon: '📊',
    desc: 'Multiplies a base stat by a factor. A value of 1.5 means +50% to that stat.',
  },
  cooldown_reduction_flat: {
    label: 'Cooldown Reduction (Flat)',
    icon: '⏱️',
    desc: 'Reduces all skill cooldowns by a flat number of turns. Stacks additively.',
  },
  aura_ally_buff: {
    label: 'Aura: Ally Buff',
    icon: '🔆',
    desc: 'Passively buffs all nearby allies within the radius each turn. The multiplier is applied to the specified stat.',
  },
  aura_enemy_debuff: {
    label: 'Aura: Enemy Debuff',
    icon: '🌑',
    desc: 'Passively weakens all nearby enemies within the radius each turn. A negative value reduces the stat.',
  },
  on_hit_extend_cooldowns: {
    label: 'On Hit: Extend Cooldowns',
    icon: '⏳',
    desc: 'When this enemy lands a hit, the target\'s active skill cooldowns are extended by N turns.',
  },
  on_hit_slow: {
    label: 'On Hit: Slow',
    icon: '❄️',
    desc: 'Each hit has a chance to slow the target, preventing movement for the duration.',
  },
  on_death_explosion: {
    label: 'On Death: Explosion',
    icon: '💥',
    desc: 'Explodes on death, dealing flat damage to all units within the blast radius.',
  },
  life_steal_pct: {
    label: 'Life Steal (%)',
    icon: '🩸',
    desc: 'Heals for a percentage of damage dealt on each hit. 0.20 = heals 20% of damage.',
  },
  grant_ward: {
    label: 'Ward Shield',
    icon: '🛡️',
    desc: 'Grants damage-absorbing ward charges. When struck, a charge is consumed and reflects damage back.',
  },
  auto_shadow_step: {
    label: 'Auto Teleport',
    icon: '🌀',
    desc: 'Automatically teleports to a nearby tile on a cooldown. Overrides shadow_step skill.',
  },
  set_stat: {
    label: 'Set Stat (Flat)',
    icon: '📌',
    desc: 'Sets a stat to a fixed flat value. Used for stats like thorns that don\'t exist by default.',
  },
  extra_ranged_target: {
    label: 'Extra Ranged Target',
    icon: '🏹',
    desc: 'Fires at additional targets per attack. Splash radius determines the area around secondary targets.',
  },
  hp_regen_pct: {
    label: 'HP Regen (% / turn)',
    icon: '💚',
    desc: 'Regenerates a percentage of max HP each turn. 0.03 = 3% HP regenerated per turn.',
  },
};

// ── Stat name formatting ─────────────────────────────────
const STAT_LABELS = {
  attack_damage: 'Attack Damage',
  armor: 'Armor',
  hp: 'HP',
  max_hp: 'Max HP',
  vision_range: 'Vision Range',
  attack_range: 'Attack Range',
  thorns: 'Thorns',
};

function formatStatName(stat) {
  return STAT_LABELS[stat] || stat.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ── Human-readable value formatters ──────────────────────
function formatMultiplier(val) {
  if (val === undefined || val === null) return '';
  const pct = Math.round((val - 1) * 100);
  return pct >= 0 ? `+${pct}%` : `${pct}%`;
}

function formatPercent(val) {
  if (val === undefined || val === null) return '';
  return `${Math.round(val * 100)}%`;
}

function formatFlat(val, unit = '') {
  if (val === undefined || val === null) return '';
  const sign = val > 0 ? '+' : '';
  return `${sign}${val}${unit}`;
}

// ── Generate a human-readable summary line for one effect ─
function describeEffect(effect) {
  const t = effect.type;
  if (t === 'stat_multiplier') {
    return `${formatMultiplier(effect.value)} ${formatStatName(effect.stat || '')}`;
  }
  if (t === 'cooldown_reduction_flat') {
    return `−${effect.value} turn${effect.value !== 1 ? 's' : ''} on all cooldowns`;
  }
  if (t === 'aura_ally_buff') {
    return `Aura: ${formatMultiplier(effect.multiplier)} ${formatStatName(effect.stat || '')} to allies within ${effect.radius} tiles`;
  }
  if (t === 'aura_enemy_debuff') {
    return `Aura: ${formatFlat(effect.value)} ${formatStatName(effect.stat || '')} to enemies within ${effect.radius} tiles`;
  }
  if (t === 'on_hit_extend_cooldowns') {
    const target = effect.target ? ` (${effect.target.replace(/_/g, ' ')})` : '';
    return `On hit: extend target's cooldowns by ${effect.turns} turn${effect.turns !== 1 ? 's' : ''}${target}`;
  }
  if (t === 'on_hit_slow') {
    return `On hit: ${formatPercent(effect.chance)} chance to slow for ${effect.duration} turn${effect.duration !== 1 ? 's' : ''}`;
  }
  if (t === 'on_death_explosion') {
    return `On death: ${effect.damage} damage in ${effect.radius}-tile radius`;
  }
  if (t === 'life_steal_pct') {
    return `Life steal: heals ${formatPercent(effect.value)} of damage dealt`;
  }
  if (t === 'grant_ward') {
    return `Ward: ${effect.charges} charges, reflects ${effect.reflect_damage || 0} damage`;
  }
  if (t === 'auto_shadow_step') {
    return `Auto-teleport every ${effect.cooldown} turns`;
  }
  if (t === 'set_stat') {
    return `${formatStatName(effect.stat || '')} set to ${effect.value}`;
  }
  if (t === 'extra_ranged_target') {
    return `+${effect.count} extra ranged target${effect.count !== 1 ? 's' : ''} (${effect.splash_radius || 0}-tile splash)`;
  }
  if (t === 'hp_regen_pct') {
    return `Regenerates ${formatPercent(effect.value)} max HP per turn`;
  }
  return t.replace(/_/g, ' ');
}

// ── Short sidebar summary (all effects in one line) ──────
function summarizeAffix(affix) {
  if (!affix.effects || affix.effects.length === 0) return 'No effects';
  return affix.effects.map(describeEffect).join(' · ');
}

function makeDefaultAffix(id) {
  return {
    affix_id: id,
    name: 'New Affix',
    category: 'offensive',
    effects: [{ type: 'stat_multiplier', stat: 'attack_damage', value: 1.3 }],
    prefixes: ['Mighty'],
    suffixes: ['the Strong'],
  };
}

export default function AffixEditor({ config, meta, onUpdate }) {
  const [selectedAffix, setSelectedAffix] = useState(null);
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [showCreate, setShowCreate] = useState(false);
  const [newId, setNewId] = useState('');

  const affixes = config?.affixes || {};
  const rules = config?.affix_rules || {};

  const affixList = useMemo(() => {
    return Object.entries(affixes)
      .map(([id, data]) => ({ id, ...data }))
      .filter(a => categoryFilter === 'all' || a.category === categoryFilter)
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [affixes, categoryFilter]);

  const affix = selectedAffix ? affixes[selectedAffix] : null;

  const updateAffix = (id, field, value) => {
    const updated = { ...config, affixes: { ...config.affixes, [id]: { ...config.affixes[id], [field]: value } } };
    onUpdate(updated);
  };

  const deleteAffix = (id) => {
    const newAffixes = { ...config.affixes };
    delete newAffixes[id];
    onUpdate({ ...config, affixes: newAffixes });
    if (selectedAffix === id) setSelectedAffix(null);
  };

  const createAffix = () => {
    if (!newId || affixes[newId]) return;
    const updated = { ...config, affixes: { ...config.affixes, [newId]: makeDefaultAffix(newId) } };
    onUpdate(updated);
    setSelectedAffix(newId);
    setShowCreate(false);
    setNewId('');
  };

  const updateEffect = (affixId, effectIdx, field, value) => {
    const effects = [...config.affixes[affixId].effects];
    effects[effectIdx] = { ...effects[effectIdx], [field]: value };
    updateAffix(affixId, 'effects', effects);
  };

  const removeEffect = (affixId, effectIdx) => {
    const effects = config.affixes[affixId].effects.filter((_, i) => i !== effectIdx);
    updateAffix(affixId, 'effects', effects);
  };

  return (
    <div className="affix-editor-layout">
      {/* Affix List */}
      <div className="affix-browser">
        <div className="browser-header">
          <h3>Affixes ({Object.keys(affixes).length})</h3>
          <button className="btn btn-sm btn-primary" onClick={() => setShowCreate(true)}>+ New</button>
        </div>

        <div className="filter-row" style={{ padding: '8px 12px' }}>
          <select value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)}>
            <option value="all">All Categories</option>
            {AFFIX_CATEGORIES.map(c => {
              const m = CATEGORY_META[c] || {};
              return <option key={c} value={c}>{m.icon || ''} {m.label || c}</option>;
            })}
          </select>
        </div>

        <div className="browser-list">
          {affixList.map(a => {
            const catMeta = CATEGORY_META[a.category] || {};
            return (
              <div
                key={a.id}
                className={`browser-item ${selectedAffix === a.id ? 'selected' : ''}`}
                onClick={() => setSelectedAffix(a.id)}
              >
                <div className="affix-item-info">
                  <div className="affix-item-name">{a.name}</div>
                  <div className="affix-item-badges">
                    <span
                      className="affix-cat-badge"
                      style={{ '--cat-color': catMeta.color || 'var(--text-dim)' }}
                    >
                      {catMeta.icon} {catMeta.label || a.category}
                    </span>
                    {a.is_aura && <span className="affix-aura-badge">AURA</span>}
                    {a.applies_to && a.applies_to !== 'all' && (
                      <span className="affix-applies-badge">
                        {a.applies_to === 'ranged_only' ? '🏹' : '⚔️'} {a.applies_to.replace('_', ' ')}
                      </span>
                    )}
                  </div>
                  <div className="affix-item-summary">{summarizeAffix(a)}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Affix Detail */}
      <div className="affix-detail">
        {showCreate && (
          <div className="card mb-8">
            <h4>Create New Affix</h4>
            <div className="form-group">
              <label>Affix ID (snake_case)</label>
              <input
                type="text"
                value={newId}
                onChange={e => setNewId(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                placeholder="e.g. lightning_enchanted"
              />
            </div>
            {newId && affixes[newId] && <div style={{ color: 'var(--danger)', fontSize: 12 }}>ID already exists!</div>}
            <div className="flex-row gap-sm">
              <button className="btn btn-primary" disabled={!newId || !!affixes[newId]} onClick={createAffix}>Create</button>
              <button className="btn" onClick={() => { setShowCreate(false); setNewId(''); }}>Cancel</button>
            </div>
          </div>
        )}

        {!affix && !showCreate && (
          <div className="empty-state">
            <h3>Select an affix to edit</h3>
            <p>Choose from the list on the left, or create a new one.</p>
          </div>
        )}

        {affix && (
          <>
            {/* ── Effect Summary Banner ─────────────────── */}
            <div className="affix-summary-banner" style={{ '--cat-color': (CATEGORY_META[affix.category] || {}).color || 'var(--text-dim)' }}>
              <div className="summary-header">
                <span className="summary-icon">{(CATEGORY_META[affix.category] || {}).icon}</span>
                <span className="summary-name">{affix.name}</span>
                <span className="affix-cat-badge" style={{ '--cat-color': (CATEGORY_META[affix.category] || {}).color }}>
                  {(CATEGORY_META[affix.category] || {}).label || affix.category}
                </span>
                {affix.is_aura && <span className="affix-aura-badge">AURA</span>}
              </div>
              <div className="summary-effects">
                {(affix.effects || []).map((effect, idx) => {
                  const em = EFFECT_META[effect.type] || {};
                  return (
                    <div key={idx} className="summary-effect-line">
                      <span className="summary-effect-icon">{em.icon || '•'}</span>
                      <span className="summary-effect-text">{describeEffect(effect)}</span>
                    </div>
                  );
                })}
                {(!affix.effects || affix.effects.length === 0) && (
                  <div className="summary-effect-line dim">No effects configured</div>
                )}
              </div>
              {affix.applies_to && affix.applies_to !== 'all' && (
                <div className="summary-restriction">
                  Restriction: {affix.applies_to === 'ranged_only' ? '🏹 Ranged enemies only' : '⚔️ Melee enemies only'}
                </div>
              )}
            </div>

            {/* Identity */}
            <div className="card mb-8">
              <div className="flex-row" style={{ justifyContent: 'space-between' }}>
                <h4>{affix.name}</h4>
                <button className="btn btn-danger btn-sm" onClick={() => {
                  if (confirm(`Delete ${affix.name}?`)) deleteAffix(selectedAffix);
                }}>🗑️</button>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Name</label>
                  <input type="text" value={affix.name} onChange={e => updateAffix(selectedAffix, 'name', e.target.value)} />
                </div>
                <div className="form-group">
                  <label>Category</label>
                  <select value={affix.category} onChange={e => updateAffix(selectedAffix, 'category', e.target.value)}>
                    {AFFIX_CATEGORIES.map(c => {
                      const m = CATEGORY_META[c] || {};
                      return <option key={c} value={c}>{m.icon} {m.label || c}</option>;
                    })}
                  </select>
                </div>
              </div>
              <div className="form-row">
                <label>
                  <input
                    type="checkbox"
                    checked={affix.is_aura || false}
                    onChange={e => updateAffix(selectedAffix, 'is_aura', e.target.checked || undefined)}
                  />
                  Is Aura
                </label>
                <div className="form-group">
                  <label>Applies To</label>
                  <select
                    value={affix.applies_to || 'all'}
                    onChange={e => updateAffix(selectedAffix, 'applies_to', e.target.value === 'all' ? undefined : e.target.value)}
                  >
                    <option value="all">All enemies</option>
                    <option value="ranged_only">Ranged only</option>
                    <option value="melee_only">Melee only</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Effects */}
            <div className="card mb-8">
              <h4>Effects</h4>
              {(affix.effects || []).map((effect, idx) => {
                const em = EFFECT_META[effect.type] || {};
                return (
                  <div key={idx} className="effect-row">
                    {/* Human-readable summary for this effect */}
                    <div className="effect-summary-line">
                      <span className="effect-summary-icon">{em.icon || '•'}</span>
                      <span className="effect-summary-text">{describeEffect(effect)}</span>
                      <button
                        className="btn btn-danger btn-xs"
                        title="Remove effect"
                        onClick={() => removeEffect(selectedAffix, idx)}
                      >✕</button>
                    </div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>Type</label>
                        <select value={effect.type} onChange={e => updateEffect(selectedAffix, idx, 'type', e.target.value)}>
                          {EFFECT_TYPES.map(t => {
                            const m = EFFECT_META[t] || {};
                            return <option key={t} value={t}>{m.icon || ''} {m.label || t}</option>;
                          })}
                        </select>
                      </div>
                      {effect.stat && (
                        <div className="form-group">
                          <label>Stat</label>
                          <input type="text" value={effect.stat} onChange={e => updateEffect(selectedAffix, idx, 'stat', e.target.value)} />
                        </div>
                      )}
                      {effect.value !== undefined && (
                        <div className="form-group">
                          <label>
                            Value
                            {effect.type === 'stat_multiplier' && effect.value != null && (
                              <span className="field-hint">{formatMultiplier(effect.value)}</span>
                            )}
                            {effect.type === 'life_steal_pct' && effect.value != null && (
                              <span className="field-hint">{formatPercent(effect.value)}</span>
                            )}
                            {effect.type === 'hp_regen_pct' && effect.value != null && (
                              <span className="field-hint">{formatPercent(effect.value)} / turn</span>
                            )}
                          </label>
                          <input type="number" step="0.01" value={effect.value} onChange={e => updateEffect(selectedAffix, idx, 'value', parseFloat(e.target.value))} />
                        </div>
                      )}
                      {effect.multiplier !== undefined && (
                        <div className="form-group">
                          <label>
                            Multiplier
                            <span className="field-hint">{formatMultiplier(effect.multiplier)}</span>
                          </label>
                          <input type="number" step="0.05" value={effect.multiplier} onChange={e => updateEffect(selectedAffix, idx, 'multiplier', parseFloat(e.target.value))} />
                        </div>
                      )}
                      {effect.radius !== undefined && (
                        <div className="form-group">
                          <label>Radius <span className="field-hint">{effect.radius} tile{effect.radius !== 1 ? 's' : ''}</span></label>
                          <input type="number" value={effect.radius} onChange={e => updateEffect(selectedAffix, idx, 'radius', parseInt(e.target.value))} />
                        </div>
                      )}
                      {effect.damage !== undefined && (
                        <div className="form-group">
                          <label>Damage <span className="field-hint">{effect.damage} flat</span></label>
                          <input type="number" value={effect.damage} onChange={e => updateEffect(selectedAffix, idx, 'damage', parseInt(e.target.value))} />
                        </div>
                      )}
                      {effect.chance !== undefined && (
                        <div className="form-group">
                          <label>Chance <span className="field-hint">{formatPercent(effect.chance)}</span></label>
                          <input type="number" step="0.05" value={effect.chance} onChange={e => updateEffect(selectedAffix, idx, 'chance', parseFloat(e.target.value))} />
                        </div>
                      )}
                      {effect.duration !== undefined && (
                        <div className="form-group">
                          <label>Duration <span className="field-hint">{effect.duration} turn{effect.duration !== 1 ? 's' : ''}</span></label>
                          <input type="number" value={effect.duration} onChange={e => updateEffect(selectedAffix, idx, 'duration', parseInt(e.target.value))} />
                        </div>
                      )}
                      {effect.turns !== undefined && (
                        <div className="form-group">
                          <label>Turns <span className="field-hint">{effect.turns} turn{effect.turns !== 1 ? 's' : ''}</span></label>
                          <input type="number" value={effect.turns} onChange={e => updateEffect(selectedAffix, idx, 'turns', parseInt(e.target.value))} />
                        </div>
                      )}
                      {effect.charges !== undefined && (
                        <div className="form-group">
                          <label>Charges <span className="field-hint">{effect.charges} hit{effect.charges !== 1 ? 's' : ''}</span></label>
                          <input type="number" value={effect.charges} onChange={e => updateEffect(selectedAffix, idx, 'charges', parseInt(e.target.value))} />
                        </div>
                      )}
                      {effect.cooldown !== undefined && (
                        <div className="form-group">
                          <label>Cooldown <span className="field-hint">every {effect.cooldown} turn{effect.cooldown !== 1 ? 's' : ''}</span></label>
                          <input type="number" value={effect.cooldown} onChange={e => updateEffect(selectedAffix, idx, 'cooldown', parseInt(e.target.value))} />
                        </div>
                      )}
                      {effect.count !== undefined && (
                        <div className="form-group">
                          <label>Count <span className="field-hint">+{effect.count} extra</span></label>
                          <input type="number" value={effect.count} onChange={e => updateEffect(selectedAffix, idx, 'count', parseInt(e.target.value))} />
                        </div>
                      )}
                    </div>
                    {/* Inline help text */}
                    <div className="effect-help-text">{em.desc || 'No description available for this effect type.'}</div>
                  </div>
                );
              })}
              <button className="btn btn-sm mt-12" onClick={() => {
                const effects = [...(affix.effects || []), { type: 'stat_multiplier', stat: 'attack_damage', value: 1.2 }];
                updateAffix(selectedAffix, 'effects', effects);
              }}>+ Add Effect</button>
            </div>

            {/* Name Pools */}
            <div className="card mb-8">
              <h4>Name Pools</h4>
              <div className="form-group">
                <label>Prefixes (comma-separated)</label>
                <input
                  type="text"
                  value={(affix.prefixes || []).join(', ')}
                  onChange={e => updateAffix(selectedAffix, 'prefixes', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                />
              </div>
              <div className="form-group">
                <label>Suffixes (comma-separated)</label>
                <input
                  type="text"
                  value={(affix.suffixes || []).join(', ')}
                  onChange={e => updateAffix(selectedAffix, 'suffixes', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                />
              </div>
            </div>

            {/* Compatibility Rules */}
            <div className="card mb-8">
              <h4>Compatibility</h4>
              <div className="form-group">
                <label>Excludes class skills (comma-separated skill IDs)</label>
                <input
                  type="text"
                  value={(affix.excludes_class_skills || []).join(', ')}
                  onChange={e => {
                    const val = e.target.value.trim();
                    updateAffix(selectedAffix, 'excludes_class_skills', val ? val.split(',').map(s => s.trim()).filter(Boolean) : undefined);
                  }}
                />
              </div>
              <p className="text-dim" style={{ fontSize: 12 }}>
                Global forbidden combos are defined in affix_rules. Current max affixes: {rules.max_affixes || '?'},
                max auras: {rules.max_auras || '?'}, max on-death: {rules.max_on_death || '?'}
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
