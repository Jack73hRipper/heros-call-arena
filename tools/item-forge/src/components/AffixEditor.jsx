// ─────────────────────────────────────────────────────────
// AffixEditor.jsx — Prefix/Suffix browser, editor, creator
// ─────────────────────────────────────────────────────────

import React, { useState, useMemo } from 'react';

const ALL_SLOTS = ['weapon', 'armor', 'accessory', 'helmet', 'boots'];

/** Format a stat value for display */
function fmtVal(val, stat, meta) {
  const info = meta?.stats?.[stat];
  if (!info) return String(val);
  if (info.type === 'float') return `${(val * 100).toFixed(1)}%`;
  return String(val);
}

/** Calculate total weight for a list of affixes */
function totalWeight(affixes) {
  return Object.values(affixes).reduce((sum, a) => sum + (a.weight || 0), 0);
}

/** Color palette for weight chart segments */
const COLORS = [
  '#ff6b6b', '#ffa94d', '#ffd43b', '#69db7c', '#38d9a9',
  '#4dabf7', '#748ffc', '#b197fc', '#f783ac', '#a9e34b',
  '#63e6be', '#74c0fc',
];

export default function AffixEditor({ config, statsMeta, onUpdate }) {
  const [filter, setFilter] = useState('all'); // 'all' | 'prefixes' | 'suffixes'
  const [slotFilter, setSlotFilter] = useState('all');
  const [statFilter, setStatFilter] = useState('all');
  const [sortCol, setSortCol] = useState('name');
  const [sortDir, setSortDir] = useState('asc');
  const [editingAffix, setEditingAffix] = useState(null);
  const [showCreate, setShowCreate] = useState(false);

  if (!config) {
    return <div className="empty-state"><h3>No affixes config found</h3><p>affixes_config.json not loaded</p></div>;
  }

  const prefixes = config.prefixes || {};
  const suffixes = config.suffixes || {};

  // Build flat list of all affixes with their type tag
  const allAffixes = useMemo(() => {
    const list = [];
    if (filter === 'all' || filter === 'prefixes') {
      for (const [id, affix] of Object.entries(prefixes)) {
        list.push({ ...affix, _id: id, _type: 'prefix' });
      }
    }
    if (filter === 'all' || filter === 'suffixes') {
      for (const [id, affix] of Object.entries(suffixes)) {
        list.push({ ...affix, _id: id, _type: 'suffix' });
      }
    }
    // Apply slot filter
    const filtered = slotFilter === 'all'
      ? list
      : list.filter(a => (a.allowed_slots || []).includes(slotFilter));
    // Apply stat filter
    const statFiltered = statFilter === 'all'
      ? filtered
      : filtered.filter(a => a.stat === statFilter);
    // Sort
    statFiltered.sort((a, b) => {
      let va = a[sortCol], vb = b[sortCol];
      if (typeof va === 'string') va = va.toLowerCase();
      if (typeof vb === 'string') vb = vb.toLowerCase();
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return statFiltered;
  }, [prefixes, suffixes, filter, slotFilter, statFilter, sortCol, sortDir]);

  // All unique stats in use
  const allStats = useMemo(() => {
    const s = new Set();
    Object.values(prefixes).forEach(a => s.add(a.stat));
    Object.values(suffixes).forEach(a => s.add(a.stat));
    return [...s].sort();
  }, [prefixes, suffixes]);

  // Sort handler
  function handleSort(col) {
    if (sortCol === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortCol(col);
      setSortDir('asc');
    }
  }

  // Delete an affix
  function handleDelete(affixId, type) {
    if (!window.confirm(`Delete affix "${affixId}"? This cannot be undone.`)) return;
    const section = type === 'prefix' ? 'prefixes' : 'suffixes';
    const updated = { ...config };
    updated[section] = { ...updated[section] };
    delete updated[section][affixId];
    onUpdate(updated);
  }

  // Save an edited affix
  function handleSaveAffix(affixId, type, data) {
    const section = type === 'prefix' ? 'prefixes' : 'suffixes';
    const updated = { ...config };
    updated[section] = { ...updated[section], [affixId]: data };
    onUpdate(updated);
    setEditingAffix(null);
  }

  // Create a new affix
  function handleCreateAffix(affixId, type, data) {
    const section = type === 'prefix' ? 'prefixes' : 'suffixes';
    const updated = { ...config };
    updated[section] = { ...updated[section], [affixId]: { affix_id: affixId, ...data } };
    onUpdate(updated);
    setShowCreate(false);
  }

  const sortArrow = (col) => sortCol === col ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '';

  return (
    <div>
      {/* Header */}
      <div className="section-header">
        <h2>Affix Registry</h2>
        <span className="count-badge">{Object.keys(prefixes).length} prefixes</span>
        <span className="count-badge">{Object.keys(suffixes).length} suffixes</span>
        <button className="btn btn-primary ml-auto" onClick={() => setShowCreate(true)}>
          + New Affix
        </button>
      </div>

      {/* Weight Distribution Bar */}
      <div className="mb-8">
        <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 4 }}>
          Weight Distribution — {filter === 'suffixes' ? 'Suffixes' : filter === 'prefixes' ? 'Prefixes' : 'All Affixes'}
        </div>
        <WeightBar affixes={allAffixes} />
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <select value={filter} onChange={e => setFilter(e.target.value)}>
          <option value="all">All Types</option>
          <option value="prefixes">Prefixes Only</option>
          <option value="suffixes">Suffixes Only</option>
        </select>
        <select value={slotFilter} onChange={e => setSlotFilter(e.target.value)}>
          <option value="all">All Slots</option>
          {ALL_SLOTS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={statFilter} onChange={e => setStatFilter(e.target.value)}>
          <option value="all">All Stats</option>
          {allStats.map(s => (
            <option key={s} value={s}>{statsMeta?.stats?.[s]?.label || s}</option>
          ))}
        </select>
        <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
          {allAffixes.length} affix{allAffixes.length !== 1 ? 'es' : ''} shown
        </span>
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th onClick={() => handleSort('_type')} className={sortCol === '_type' ? 'sorted' : ''}>
                Type{sortArrow('_type')}
              </th>
              <th onClick={() => handleSort('name')} className={sortCol === 'name' ? 'sorted' : ''}>
                Name{sortArrow('name')}
              </th>
              <th onClick={() => handleSort('stat')} className={sortCol === 'stat' ? 'sorted' : ''}>
                Stat{sortArrow('stat')}
              </th>
              <th onClick={() => handleSort('min_value')} className={sortCol === 'min_value' ? 'sorted' : ''}>
                Min{sortArrow('min_value')}
              </th>
              <th onClick={() => handleSort('max_value')} className={sortCol === 'max_value' ? 'sorted' : ''}>
                Max{sortArrow('max_value')}
              </th>
              <th onClick={() => handleSort('ilvl_scaling')} className={sortCol === 'ilvl_scaling' ? 'sorted' : ''}>
                iLvl Scale{sortArrow('ilvl_scaling')}
              </th>
              <th onClick={() => handleSort('weight')} className={sortCol === 'weight' ? 'sorted' : ''}>
                Weight{sortArrow('weight')}
              </th>
              <th>Slots</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {allAffixes.map(affix => (
              <tr key={affix._id}>
                <td>
                  <span style={{
                    color: affix._type === 'prefix' ? '#4dabf7' : '#b197fc',
                    fontWeight: 600,
                    fontSize: 11,
                    textTransform: 'uppercase'
                  }}>
                    {affix._type}
                  </span>
                </td>
                <td style={{ fontWeight: 600 }}>{affix.name}</td>
                <td>
                  <span className="stat-tooltip" data-tip={affix.description || ''}>
                    {statsMeta?.stats?.[affix.stat]?.label || affix.stat}
                  </span>
                </td>
                <td className="mono">{fmtVal(affix.min_value, affix.stat, statsMeta)}</td>
                <td className="mono">{fmtVal(affix.max_value, affix.stat, statsMeta)}</td>
                <td className="mono">{affix.ilvl_scaling}</td>
                <td className="mono">{affix.weight}</td>
                <td>
                  {(affix.allowed_slots || []).map(s => (
                    <span key={s} className={`slot-badge ${s}`}>{s}</span>
                  ))}
                </td>
                <td>
                  <div className="flex-row gap-sm">
                    <button className="btn btn-sm" onClick={() => setEditingAffix({ ...affix })}>
                      ✏️ Edit
                    </button>
                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete(affix._id, affix._type)}>
                      🗑️
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Edit Modal */}
      {editingAffix && (
        <AffixModal
          affix={editingAffix}
          statsMeta={statsMeta}
          mode="edit"
          onSave={(data) => handleSaveAffix(editingAffix._id, editingAffix._type, data)}
          onClose={() => setEditingAffix(null)}
        />
      )}

      {/* Create Modal */}
      {showCreate && (
        <AffixModal
          affix={null}
          statsMeta={statsMeta}
          mode="create"
          onSave={(id, type, data) => handleCreateAffix(id, type, data)}
          onClose={() => setShowCreate(false)}
        />
      )}
    </div>
  );
}

// ── Weight Distribution Bar ──────────────────────────────
function WeightBar({ affixes }) {
  const total = affixes.reduce((s, a) => s + (a.weight || 0), 0);
  if (total === 0) return null;

  return (
    <div className="weight-bar">
      {affixes.map((affix, i) => {
        const pct = ((affix.weight || 0) / total * 100);
        if (pct < 0.5) return null;
        return (
          <div
            key={affix._id}
            className="weight-segment"
            style={{
              width: `${pct}%`,
              background: COLORS[i % COLORS.length],
            }}
          >
            <div className="weight-segment-tooltip">
              {affix.name}: {affix.weight} ({pct.toFixed(1)}%)
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Affix Edit/Create Modal ──────────────────────────────
function AffixModal({ affix, statsMeta, mode, onSave, onClose }) {
  const allStatKeys = Object.keys(statsMeta?.stats || {});

  const [form, setForm] = useState(() => {
    if (mode === 'edit' && affix) {
      return {
        affix_id: affix.affix_id || affix._id,
        name: affix.name || '',
        stat: affix.stat || 'attack_damage',
        min_value: affix.min_value ?? 0,
        max_value: affix.max_value ?? 0,
        ilvl_scaling: affix.ilvl_scaling ?? 0,
        weight: affix.weight ?? 50,
        allowed_slots: affix.allowed_slots || ['weapon'],
        description: affix.description || '',
        _type: affix._type || 'prefix',
      };
    }
    return {
      affix_id: '',
      name: '',
      stat: 'attack_damage',
      min_value: 0,
      max_value: 0,
      ilvl_scaling: 0,
      weight: 50,
      allowed_slots: ['weapon'],
      description: '',
      _type: 'prefix',
    };
  });

  function update(key, val) {
    setForm(prev => ({ ...prev, [key]: val }));
  }

  function toggleSlot(slot) {
    setForm(prev => {
      const slots = prev.allowed_slots.includes(slot)
        ? prev.allowed_slots.filter(s => s !== slot)
        : [...prev.allowed_slots, slot];
      return { ...prev, allowed_slots: slots };
    });
  }

  function handleSubmit() {
    // Determine if stat is float-based
    const statInfo = statsMeta?.stats?.[form.stat];
    const isFloat = statInfo?.type === 'float';

    const data = {
      affix_id: form.affix_id,
      name: form.name,
      stat: form.stat,
      min_value: isFloat ? parseFloat(form.min_value) : parseInt(form.min_value),
      max_value: isFloat ? parseFloat(form.max_value) : parseInt(form.max_value),
      ilvl_scaling: parseFloat(form.ilvl_scaling),
      weight: parseInt(form.weight),
      allowed_slots: form.allowed_slots,
      description: form.description,
    };

    if (mode === 'edit') {
      onSave(data);
    } else {
      onSave(form.affix_id, form._type, data);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2>{mode === 'edit' ? `Edit: ${form.name}` : 'Create New Affix'}</h2>

        {mode === 'create' && (
          <div className="form-row">
            <div className="form-group">
              <label>Affix ID</label>
              <input type="text" value={form.affix_id} onChange={e => update('affix_id', e.target.value)}
                placeholder="e.g. blazing" />
            </div>
            <div className="form-group">
              <label>Type</label>
              <select value={form._type} onChange={e => update('_type', e.target.value)}>
                <option value="prefix">Prefix</option>
                <option value="suffix">Suffix</option>
              </select>
            </div>
          </div>
        )}

        <div className="form-row">
          <div className="form-group">
            <label>Display Name</label>
            <input type="text" value={form.name} onChange={e => update('name', e.target.value)}
              placeholder={form._type === 'prefix' ? 'e.g. Blazing' : 'e.g. of Flame'} />
          </div>
          <div className="form-group">
            <label>Stat</label>
            <select value={form.stat} onChange={e => update('stat', e.target.value)}>
              {allStatKeys.map(s => (
                <option key={s} value={s}>{statsMeta.stats[s].label}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Min Value</label>
            <input type="number" step="any" value={form.min_value}
              onChange={e => update('min_value', e.target.value)} />
          </div>
          <div className="form-group">
            <label>Max Value</label>
            <input type="number" step="any" value={form.max_value}
              onChange={e => update('max_value', e.target.value)} />
          </div>
          <div className="form-group">
            <label>iLvl Scaling</label>
            <input type="number" step="any" value={form.ilvl_scaling}
              onChange={e => update('ilvl_scaling', e.target.value)} />
          </div>
          <div className="form-group">
            <label>Weight</label>
            <input type="number" value={form.weight}
              onChange={e => update('weight', e.target.value)} />
          </div>
        </div>

        <div className="form-group">
          <label>Description</label>
          <input type="text" value={form.description} onChange={e => update('description', e.target.value)}
            style={{ width: '100%' }} placeholder="What this affix does" />
        </div>

        <div className="form-group">
          <label>Allowed Slots</label>
          <div className="checkbox-group">
            {ALL_SLOTS.map(slot => (
              <label key={slot}>
                <input type="checkbox" checked={form.allowed_slots.includes(slot)}
                  onChange={() => toggleSlot(slot)} />
                <span className={`slot-badge ${slot}`}>{slot}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Value preview at different item levels */}
        <div style={{ marginTop: 12 }}>
          <label style={{ fontSize: 12, color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase' }}>
            Value Preview by Item Level
          </label>
          <div style={{ display: 'flex', gap: 16, marginTop: 6, fontFamily: 'var(--font-mono)', fontSize: 12 }}>
            {[1, 5, 10, 15, 18].map(ilvl => {
              const minV = parseFloat(form.min_value) || 0;
              const maxV = parseFloat(form.max_value) || 0;
              const scale = parseFloat(form.ilvl_scaling) || 0;
              const scaledMax = Math.min(maxV, minV + scale * ilvl);
              const statInfo = statsMeta?.stats?.[form.stat];
              const fmt = (v) => statInfo?.type === 'float' ? `${(v * 100).toFixed(1)}%` : Math.round(v);
              return (
                <div key={ilvl} style={{ textAlign: 'center' }}>
                  <div style={{ color: 'var(--text-dim)' }}>iLvl {ilvl}</div>
                  <div style={{ color: 'var(--success)' }}>{fmt(minV)}–{fmt(Math.max(minV, scaledMax))}</div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="modal-actions">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit}>
            {mode === 'edit' ? '💾 Save Changes' : '✨ Create Affix'}
          </button>
        </div>
      </div>
    </div>
  );
}
