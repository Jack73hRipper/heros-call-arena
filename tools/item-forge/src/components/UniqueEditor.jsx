// ─────────────────────────────────────────────────────────
// UniqueEditor.jsx — Unique item card browser & editor
// ─────────────────────────────────────────────────────────

import React, { useState, useMemo } from 'react';

const ALL_SLOTS = ['weapon', 'armor', 'accessory', 'helmet', 'boots'];
const CLASSES = ['crusader', 'confessor', 'inquisitor', 'ranger', 'hexblade', 'all'];

/** Format stat value for display */
function fmtStat(stat, val, meta) {
  if (val === 0 || val === undefined) return null;
  const info = meta?.stats?.[stat];
  if (!info) return `${stat}: ${val}`;
  if (info.type === 'float') return `+${(val * 100).toFixed(0)}% ${info.label}`;
  return `${val > 0 ? '+' : ''}${val} ${info.label}`;
}

/** Calculate stat budget */
function calcBudget(statBonuses, statsMeta) {
  if (!statBonuses || !statsMeta?.stats) return 0;
  let total = 0;
  for (const [stat, val] of Object.entries(statBonuses)) {
    if (val === 0) continue;
    const info = statsMeta.stats[stat];
    if (!info) continue;
    total += Math.abs(val) * info.budget_pts;
  }
  return Math.round(total * 10) / 10;
}

export default function UniqueEditor({ config, statsMeta, onUpdate }) {
  const [slotFilter, setSlotFilter] = useState('all');
  const [classFilter, setClassFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [editingUnique, setEditingUnique] = useState(null);
  const [showCreate, setShowCreate] = useState(false);

  if (!config || !config.uniques) {
    return <div className="empty-state"><h3>No uniques config found</h3><p>uniques_config.json not loaded</p></div>;
  }

  const uniques = config.uniques;
  const dropRules = config.drop_rules || {};
  const enemyWeights = config.enemy_type_weights || {};

  // Filtered list
  const uniqueList = useMemo(() => {
    let list = Object.entries(uniques).map(([id, u]) => ({ ...u, _id: id }));
    if (slotFilter !== 'all') list = list.filter(u => u.equip_slot === slotFilter);
    if (classFilter !== 'all') list = list.filter(u => (u.best_for || []).includes(classFilter));
    if (search) {
      const s = search.toLowerCase();
      list = list.filter(u => u.name.toLowerCase().includes(s) || u._id.toLowerCase().includes(s));
    }
    return list;
  }, [uniques, slotFilter, classFilter, search]);

  function handleDelete(id) {
    if (!window.confirm(`Delete unique "${id}"? This cannot be undone.`)) return;
    const updated = { ...config, uniques: { ...config.uniques } };
    delete updated.uniques[id];
    onUpdate(updated);
  }

  function handleSaveUnique(id, data) {
    const updated = { ...config, uniques: { ...config.uniques, [id]: data } };
    onUpdate(updated);
    setEditingUnique(null);
  }

  function handleCreateUnique(id, data) {
    const updated = { ...config, uniques: { ...config.uniques, [id]: { unique_id: id, ...data } } };
    onUpdate(updated);
    setShowCreate(false);
  }

  function handleUpdateDropRules(newRules) {
    const updated = { ...config, drop_rules: newRules };
    onUpdate(updated);
  }

  return (
    <div>
      <div className="section-header">
        <h2>Unique Items</h2>
        <span className="count-badge">{Object.keys(uniques).length} uniques</span>
        <button className="btn btn-primary ml-auto" onClick={() => setShowCreate(true)}>
          + New Unique
        </button>
      </div>

      {/* Drop Rules Summary */}
      <div className="card mb-8" style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 8, fontWeight: 600, textTransform: 'uppercase' }}>
          Drop Rules
        </div>
        <div className="flex-row" style={{ gap: 24, fontSize: 13, flexWrap: 'wrap' }}>
          <div>
            <span style={{ color: 'var(--text-dim)' }}>Base Chance: </span>
            <span className="mono" style={{ color: 'var(--accent)' }}>{(dropRules.base_drop_chance * 100).toFixed(1)}%</span>
          </div>
          <div>
            <span style={{ color: 'var(--text-dim)' }}>Min Tier: </span>
            <span style={{ color: 'var(--text)' }}>{dropRules.min_enemy_tier}</span>
          </div>
          <div>
            <span style={{ color: 'var(--text-dim)' }}>Max per Run: </span>
            <span className="mono">{dropRules.max_per_run}</span>
          </div>
          <div>
            <span style={{ color: 'var(--text-dim)' }}>MF Scaling: </span>
            <span style={{ color: dropRules.magic_find_scaling ? 'var(--success)' : 'var(--danger)' }}>
              {dropRules.magic_find_scaling ? 'Yes' : 'No'}
            </span>
          </div>
        </div>
        {dropRules.floor_scaling && (
          <div style={{ marginTop: 8, fontSize: 12 }}>
            <span style={{ color: 'var(--text-dim)' }}>Floor Scaling: </span>
            {Object.entries(dropRules.floor_scaling).map(([floor, mult]) => (
              <span key={floor} className="mono" style={{ marginRight: 12 }}>
                F{floor}: {mult}×
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <input type="text" placeholder="🔍 Search uniques..." value={search}
          onChange={e => setSearch(e.target.value)} style={{ minWidth: 180 }} />
        <select value={slotFilter} onChange={e => setSlotFilter(e.target.value)}>
          <option value="all">All Slots</option>
          {ALL_SLOTS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={classFilter} onChange={e => setClassFilter(e.target.value)}>
          <option value="all">All Classes</option>
          {CLASSES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
          {uniqueList.length} unique{uniqueList.length !== 1 ? 's' : ''} shown
        </span>
      </div>

      {/* Card Grid */}
      <div className="card-grid">
        {uniqueList.map(unique => (
          <div key={unique._id} className="item-card rarity-unique">
            <div className="item-card-header">
              <h3 style={{ color: 'var(--rarity-unique)' }}>{unique.name}</h3>
              <span className={`slot-badge ${unique.equip_slot}`}>{unique.equip_slot}</span>
            </div>

            {/* Stats */}
            <div className="item-card-stats">
              {Object.entries(unique.stat_bonuses || {}).map(([stat, val]) => {
                const display = fmtStat(stat, val, statsMeta);
                if (!display) return null;
                return (
                  <div key={stat} className="stat-line">
                    <span className="stat-value" style={{ color: val < 0 ? 'var(--danger)' : 'var(--success)' }}>
                      {display}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Budget */}
            <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>
              Budget: {calcBudget(unique.stat_bonuses, statsMeta)} pts · iLvl {unique.item_level} · Sell {unique.sell_value}g
            </div>

            {/* Special Effect */}
            {unique.special_effect && (
              <div className="item-card-effect">
                <div className="effect-label">Special Effect</div>
                <div className="effect-desc">{unique.special_effect.description}</div>
              </div>
            )}

            {/* Flavor */}
            {unique.description && (
              <div className="item-card-flavor">"{unique.description}"</div>
            )}

            {/* Footer */}
            <div className="item-card-footer">
              <span className="best-for">Best for:</span>
              {(unique.best_for || []).map(c => (
                <span key={c} className="class-tag">{c}</span>
              ))}
              <div className="ml-auto flex-row gap-sm">
                <button className="btn btn-sm" onClick={() => setEditingUnique({ ...unique })}>✏️ Edit</button>
                <button className="btn btn-sm btn-danger" onClick={() => handleDelete(unique._id)}>🗑️</button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Edit Modal */}
      {editingUnique && (
        <UniqueModal
          unique={editingUnique}
          statsMeta={statsMeta}
          mode="edit"
          onSave={(data) => handleSaveUnique(editingUnique._id, data)}
          onClose={() => setEditingUnique(null)}
        />
      )}

      {/* Create Modal */}
      {showCreate && (
        <UniqueModal
          unique={null}
          statsMeta={statsMeta}
          mode="create"
          onSave={(id, data) => handleCreateUnique(id, data)}
          onClose={() => setShowCreate(false)}
        />
      )}
    </div>
  );
}

// ── Unique Edit/Create Modal ─────────────────────────────
function UniqueModal({ unique, statsMeta, mode, onSave, onClose }) {
  const allStatKeys = Object.keys(statsMeta?.stats || {});

  const [form, setForm] = useState(() => {
    if (mode === 'edit' && unique) {
      return {
        unique_id: unique.unique_id || unique._id,
        name: unique.name || '',
        item_type: unique.item_type || 'weapon',
        equip_slot: unique.equip_slot || 'weapon',
        description: unique.description || '',
        stat_bonuses: { ...unique.stat_bonuses },
        special_effect: unique.special_effect ? { ...unique.special_effect } : {
          effect_id: '', description: '', type: '', value: 0
        },
        best_for: [...(unique.best_for || [])],
        sell_value: unique.sell_value || 100,
        item_level: unique.item_level || 14,
      };
    }
    return {
      unique_id: '',
      name: '',
      item_type: 'weapon',
      equip_slot: 'weapon',
      description: '',
      stat_bonuses: {},
      special_effect: { effect_id: '', description: '', type: '', value: 0 },
      best_for: [],
      sell_value: 100,
      item_level: 14,
    };
  });

  function update(key, val) {
    setForm(prev => ({ ...prev, [key]: val }));
  }

  function updateStat(stat, val) {
    setForm(prev => ({
      ...prev,
      stat_bonuses: { ...prev.stat_bonuses, [stat]: val },
    }));
  }

  function updateEffect(key, val) {
    setForm(prev => ({
      ...prev,
      special_effect: { ...prev.special_effect, [key]: val },
    }));
  }

  function toggleClass(cls) {
    setForm(prev => {
      const bf = prev.best_for.includes(cls)
        ? prev.best_for.filter(c => c !== cls)
        : [...prev.best_for, cls];
      return { ...prev, best_for: bf };
    });
  }

  const budget = calcBudget(form.stat_bonuses, statsMeta);

  function handleSubmit() {
    // Clean stats
    const cleanStats = {};
    for (const [k, v] of Object.entries(form.stat_bonuses)) {
      const num = parseFloat(v) || 0;
      if (num !== 0) cleanStats[k] = num;
    }

    const data = {
      unique_id: form.unique_id,
      name: form.name,
      item_type: form.item_type,
      equip_slot: form.equip_slot,
      description: form.description,
      stat_bonuses: cleanStats,
      special_effect: form.special_effect,
      best_for: form.best_for,
      sell_value: parseInt(form.sell_value) || 100,
      item_level: parseInt(form.item_level) || 14,
    };

    if (mode === 'edit') onSave(data);
    else onSave(form.unique_id, data);
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ minWidth: 650 }}>
        <h2 style={{ color: 'var(--rarity-unique)' }}>
          {mode === 'edit' ? `Edit: ${form.name}` : 'Create New Unique'}
        </h2>

        {mode === 'create' && (
          <div className="form-group">
            <label>Unique ID</label>
            <input type="text" value={form.unique_id}
              onChange={e => update('unique_id', e.target.value)}
              placeholder="e.g. unique_my_weapon" />
          </div>
        )}

        <div className="form-row">
          <div className="form-group" style={{ flex: 2 }}>
            <label>Name</label>
            <input type="text" value={form.name} onChange={e => update('name', e.target.value)}
              placeholder="Souldrinker" style={{ width: '100%' }} />
          </div>
          <div className="form-group">
            <label>Slot</label>
            <select value={form.equip_slot} onChange={e => { update('equip_slot', e.target.value); update('item_type', e.target.value === 'accessory' ? 'accessory' : e.target.value); }}>
              {ALL_SLOTS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Item Level</label>
            <input type="number" value={form.item_level}
              onChange={e => update('item_level', e.target.value)} />
          </div>
          <div className="form-group">
            <label>Sell Value</label>
            <input type="number" value={form.sell_value}
              onChange={e => update('sell_value', e.target.value)} />
          </div>
        </div>

        <div className="form-group">
          <label>Flavor Text</label>
          <textarea value={form.description} onChange={e => update('description', e.target.value)}
            rows={2} style={{ width: '100%', resize: 'vertical' }}
            placeholder="A blade forged in darkness..." />
        </div>

        {/* Stat Bonuses */}
        <div className="form-group">
          <label>Stat Bonuses (budget: {budget} pts)</label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
            {allStatKeys.map(stat => {
              const info = statsMeta.stats[stat];
              const val = form.stat_bonuses[stat] ?? '';
              return (
                <div key={stat} className="flex-row gap-sm" style={{ fontSize: 12 }}>
                  <label style={{ width: 100, color: 'var(--text-dim)', fontSize: 11 }}>{info.label}</label>
                  <input
                    type="number"
                    step={info.type === 'float' ? '0.01' : '1'}
                    value={val}
                    onChange={e => updateStat(stat, e.target.value)}
                    style={{ width: 70 }}
                    placeholder="0"
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* Special Effect */}
        <div className="form-group" style={{ background: 'var(--bg-dark)', padding: 12, borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
          <label style={{ color: 'var(--accent)' }}>Special Effect</label>
          <div className="form-row">
            <div className="form-group">
              <label>Effect ID</label>
              <input type="text" value={form.special_effect.effect_id}
                onChange={e => updateEffect('effect_id', e.target.value)}
                placeholder="my_unique_effect" />
            </div>
            <div className="form-group">
              <label>Type</label>
              <input type="text" value={form.special_effect.type}
                onChange={e => updateEffect('type', e.target.value)}
                placeholder="e.g. melee_lifesteal_pct" />
            </div>
            <div className="form-group">
              <label>Value</label>
              <input type="number" step="any" value={form.special_effect.value ?? ''}
                onChange={e => updateEffect('value', parseFloat(e.target.value) || 0)} />
            </div>
          </div>
          <div className="form-group">
            <label>Description</label>
            <input type="text" value={form.special_effect.description}
              onChange={e => updateEffect('description', e.target.value)}
              style={{ width: '100%' }}
              placeholder="Heals 15% of melee damage dealt" />
          </div>
        </div>

        {/* Best For */}
        <div className="form-group">
          <label>Best For Classes</label>
          <div className="checkbox-group">
            {CLASSES.map(cls => (
              <label key={cls}>
                <input type="checkbox" checked={form.best_for.includes(cls)}
                  onChange={() => toggleClass(cls)} />
                <span style={{ textTransform: 'capitalize' }}>{cls}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="modal-actions">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit}>
            {mode === 'edit' ? '💾 Save Changes' : '✨ Create Unique'}
          </button>
        </div>
      </div>
    </div>
  );
}
