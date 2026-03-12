// ─────────────────────────────────────────────────────────
// BaseItemEditor.jsx — Base item type browser & editor
// ─────────────────────────────────────────────────────────

import React, { useState, useMemo } from 'react';

const ALL_SLOTS = ['weapon', 'armor', 'accessory', 'helmet', 'boots'];
const ALL_TYPES = ['weapon', 'armor', 'accessory', 'consumable'];

/** Calculate stat budget for an item */
function calcBudget(statBonuses, statsMeta) {
  if (!statBonuses || !statsMeta?.stats) return 0;
  let total = 0;
  for (const [stat, val] of Object.entries(statBonuses)) {
    if (val === 0) continue;
    const info = statsMeta.stats[stat];
    if (!info) continue;
    if (info.type === 'float') {
      total += val * info.budget_pts;
    } else {
      total += val * info.budget_pts;
    }
  }
  return Math.round(total * 10) / 10;
}

/** Format stat value for display */
function fmtStat(stat, val, meta) {
  if (val === 0 || val === undefined) return null;
  const info = meta?.stats?.[stat];
  if (!info) return `${stat}: ${val}`;
  if (info.type === 'float') return `${info.label}: ${(val * 100).toFixed(1)}%`;
  return `${info.label}: ${val > 0 ? '+' : ''}${val}`;
}

export default function BaseItemEditor({ config, statsMeta, onUpdate }) {
  const [slotFilter, setSlotFilter] = useState('all');
  const [rarityFilter, setRarityFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [sortCol, setSortCol] = useState('name');
  const [sortDir, setSortDir] = useState('asc');
  const [editingItem, setEditingItem] = useState(null);
  const [showCreate, setShowCreate] = useState(false);

  if (!config || !config.items) {
    return <div className="empty-state"><h3>No items config found</h3><p>items_config.json not loaded</p></div>;
  }

  const items = config.items;

  // Build filtered + sorted list
  const itemList = useMemo(() => {
    let list = Object.entries(items).map(([id, item]) => ({
      ...item,
      _id: id,
      _budget: calcBudget(item.stat_bonuses, statsMeta),
    }));

    if (slotFilter !== 'all') list = list.filter(i => i.equip_slot === slotFilter);
    if (rarityFilter !== 'all') list = list.filter(i => i.rarity === rarityFilter);
    if (typeFilter !== 'all') list = list.filter(i => i.item_type === typeFilter);
    if (search) {
      const s = search.toLowerCase();
      list = list.filter(i => i.name.toLowerCase().includes(s) || i._id.toLowerCase().includes(s));
    }

    list.sort((a, b) => {
      let va = a[sortCol], vb = b[sortCol];
      if (sortCol === '_budget') { va = a._budget; vb = b._budget; }
      if (typeof va === 'string') { va = va.toLowerCase(); vb = (vb || '').toLowerCase(); }
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });

    return list;
  }, [items, slotFilter, rarityFilter, typeFilter, search, sortCol, sortDir, statsMeta]);

  // Unique rarities in data
  const rarities = useMemo(() => {
    const s = new Set(Object.values(items).map(i => i.rarity));
    return [...s].sort();
  }, [items]);

  function handleSort(col) {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortCol(col); setSortDir('asc'); }
  }

  function handleDelete(id) {
    if (!window.confirm(`Delete base item "${id}"? This cannot be undone.`)) return;
    const updated = { ...config, items: { ...config.items } };
    delete updated.items[id];
    onUpdate(updated);
  }

  function handleSaveItem(id, data) {
    const updated = { ...config, items: { ...config.items, [id]: data } };
    onUpdate(updated);
    setEditingItem(null);
  }

  function handleCreateItem(id, data) {
    const updated = { ...config, items: { ...config.items, [id]: { item_id: id, ...data } } };
    onUpdate(updated);
    setShowCreate(false);
  }

  const sortArrow = (col) => sortCol === col ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '';

  // Active stat columns (only show stats that at least one item uses)
  const activeStats = useMemo(() => {
    const used = new Set();
    Object.values(items).forEach(item => {
      if (!item.stat_bonuses) return;
      for (const [k, v] of Object.entries(item.stat_bonuses)) {
        if (v !== 0) used.add(k);
      }
    });
    return [...used].sort();
  }, [items]);

  return (
    <div>
      <div className="section-header">
        <h2>Base Item Types</h2>
        <span className="count-badge">{Object.keys(items).length} items</span>
        <button className="btn btn-primary ml-auto" onClick={() => setShowCreate(true)}>
          + New Base Item
        </button>
      </div>

      <div className="filter-bar">
        <input type="text" placeholder="🔍 Search items..." value={search}
          onChange={e => setSearch(e.target.value)} style={{ minWidth: 180 }} />
        <select value={slotFilter} onChange={e => setSlotFilter(e.target.value)}>
          <option value="all">All Slots</option>
          {ALL_SLOTS.map(s => <option key={s} value={s}>{s}</option>)}
          <option value="null">No Slot (consumable)</option>
        </select>
        <select value={rarityFilter} onChange={e => setRarityFilter(e.target.value)}>
          <option value="all">All Rarities</option>
          {rarities.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
          <option value="all">All Types</option>
          {ALL_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
          {itemList.length} item{itemList.length !== 1 ? 's' : ''} shown
        </span>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th onClick={() => handleSort('name')} className={sortCol === 'name' ? 'sorted' : ''}>
                Name{sortArrow('name')}
              </th>
              <th onClick={() => handleSort('rarity')} className={sortCol === 'rarity' ? 'sorted' : ''}>
                Rarity{sortArrow('rarity')}
              </th>
              <th onClick={() => handleSort('equip_slot')} className={sortCol === 'equip_slot' ? 'sorted' : ''}>
                Slot{sortArrow('equip_slot')}
              </th>
              {activeStats.map(stat => (
                <th key={stat} className="center" style={{ fontSize: 10 }}>
                  {statsMeta?.stats?.[stat]?.label || stat}
                </th>
              ))}
              <th onClick={() => handleSort('_budget')} className={sortCol === '_budget' ? 'sorted' : ''}>
                Budget{sortArrow('_budget')}
              </th>
              <th onClick={() => handleSort('sell_value')} className={sortCol === 'sell_value' ? 'sorted' : ''}>
                Sell{sortArrow('sell_value')}
              </th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {itemList.map(item => {
              const budgetRange = statsMeta?.stat_budget_ranges?.[item.rarity];
              const budgetClass = budgetRange
                ? (item._budget > budgetRange.max ? 'over' : item._budget >= budgetRange.min ? 'ok' : 'warn')
                : 'ok';
              return (
                <tr key={item._id}>
                  <td style={{ fontWeight: 600 }}>{item.name}</td>
                  <td><span className={`rarity-label rarity-${item.rarity}`}>{item.rarity}</span></td>
                  <td>
                    {item.equip_slot
                      ? <span className={`slot-badge ${item.equip_slot}`}>{item.equip_slot}</span>
                      : <span style={{ color: 'var(--text-dim)' }}>—</span>
                    }
                  </td>
                  {activeStats.map(stat => {
                    const val = item.stat_bonuses?.[stat] || 0;
                    return (
                      <td key={stat} className="mono center" style={{
                        color: val > 0 ? 'var(--success)' : val < 0 ? 'var(--danger)' : 'var(--text-dim)'
                      }}>
                        {val !== 0 ? (statsMeta?.stats?.[stat]?.type === 'float' ? `${(val * 100).toFixed(0)}%` : val) : '—'}
                      </td>
                    );
                  })}
                  <td className="mono" style={{ color: `var(--${budgetClass === 'over' ? 'danger' : budgetClass === 'warn' ? 'warning' : 'success'})` }}>
                    {item._budget}
                  </td>
                  <td className="mono" style={{ color: 'var(--warning)' }}>{item.sell_value}g</td>
                  <td>
                    <div className="flex-row gap-sm">
                      <button className="btn btn-sm" onClick={() => setEditingItem({ ...item })}>✏️</button>
                      <button className="btn btn-sm btn-danger" onClick={() => handleDelete(item._id)}>🗑️</button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {editingItem && (
        <ItemModal
          item={editingItem}
          statsMeta={statsMeta}
          mode="edit"
          onSave={(data) => handleSaveItem(editingItem._id, data)}
          onClose={() => setEditingItem(null)}
        />
      )}

      {showCreate && (
        <ItemModal
          item={null}
          statsMeta={statsMeta}
          mode="create"
          onSave={(id, data) => handleCreateItem(id, data)}
          onClose={() => setShowCreate(false)}
        />
      )}
    </div>
  );
}

// ── Item Edit/Create Modal ───────────────────────────────
function ItemModal({ item, statsMeta, mode, onSave, onClose }) {
  const allStatKeys = Object.keys(statsMeta?.stats || {});

  const [form, setForm] = useState(() => {
    if (mode === 'edit' && item) {
      return {
        item_id: item.item_id || item._id,
        name: item.name || '',
        item_type: item.item_type || 'weapon',
        rarity: item.rarity || 'common',
        equip_slot: item.equip_slot || 'weapon',
        stat_bonuses: { ...item.stat_bonuses },
        description: item.description || '',
        sell_value: item.sell_value || 0,
        consumable_effect: item.consumable_effect || null,
      };
    }
    return {
      item_id: '',
      name: '',
      item_type: 'weapon',
      rarity: 'common',
      equip_slot: 'weapon',
      stat_bonuses: { attack_damage: 0, ranged_damage: 0, armor: 0, max_hp: 0 },
      description: '',
      sell_value: 10,
      consumable_effect: null,
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

  const budget = calcBudget(form.stat_bonuses, statsMeta);
  const budgetRange = statsMeta?.stat_budget_ranges?.[form.rarity];

  function handleSubmit() {
    // Clean stat_bonuses: convert string values to proper numbers
    const cleanStats = {};
    for (const [k, v] of Object.entries(form.stat_bonuses)) {
      const info = statsMeta?.stats?.[k];
      const num = parseFloat(v) || 0;
      if (num !== 0 || k === 'attack_damage' || k === 'ranged_damage' || k === 'armor' || k === 'max_hp') {
        cleanStats[k] = info?.type === 'float' ? num : Math.round(num);
      }
    }

    const data = {
      item_id: form.item_id,
      name: form.name,
      item_type: form.item_type,
      rarity: form.rarity,
      equip_slot: form.item_type === 'consumable' ? null : form.equip_slot,
      stat_bonuses: cleanStats,
      description: form.description,
      sell_value: parseInt(form.sell_value) || 0,
    };
    if (form.consumable_effect) data.consumable_effect = form.consumable_effect;

    if (mode === 'edit') {
      onSave(data);
    } else {
      onSave(form.item_id, data);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ minWidth: 600 }}>
        <h2>{mode === 'edit' ? `Edit: ${form.name}` : 'Create New Base Item'}</h2>

        {mode === 'create' && (
          <div className="form-group">
            <label>Item ID</label>
            <input type="text" value={form.item_id}
              onChange={e => update('item_id', e.target.value)}
              placeholder="e.g. common_longsword" />
          </div>
        )}

        <div className="form-row">
          <div className="form-group">
            <label>Name</label>
            <input type="text" value={form.name} onChange={e => update('name', e.target.value)}
              placeholder="Rusty Longsword" style={{ width: '100%' }} />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Item Type</label>
            <select value={form.item_type} onChange={e => update('item_type', e.target.value)}>
              {ALL_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Rarity</label>
            <select value={form.rarity} onChange={e => update('rarity', e.target.value)}>
              {['common', 'magic', 'rare', 'epic'].map(r => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
          {form.item_type !== 'consumable' && (
            <div className="form-group">
              <label>Equip Slot</label>
              <select value={form.equip_slot || ''} onChange={e => update('equip_slot', e.target.value)}>
                {ALL_SLOTS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          )}
          <div className="form-group">
            <label>Sell Value</label>
            <input type="number" value={form.sell_value}
              onChange={e => update('sell_value', e.target.value)} />
          </div>
        </div>

        <div className="form-group">
          <label>Description</label>
          <input type="text" value={form.description} onChange={e => update('description', e.target.value)}
            style={{ width: '100%' }} placeholder="A fine blade..." />
        </div>

        {/* Stat Bonuses */}
        <div className="form-group">
          <label>Stat Bonuses</label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
            {allStatKeys.map(stat => {
              const info = statsMeta.stats[stat];
              const val = form.stat_bonuses[stat] ?? 0;
              return (
                <div key={stat} className="flex-row gap-sm" style={{ fontSize: 12 }}>
                  <label style={{ width: 100, color: 'var(--text-dim)', fontSize: 11 }}>{info.label}</label>
                  <input
                    type="number"
                    step={info.type === 'float' ? '0.01' : '1'}
                    value={val}
                    onChange={e => updateStat(stat, e.target.value)}
                    style={{ width: 70 }}
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* Budget bar */}
        <div className="budget-bar-container">
          <div className="budget-bar-label">
            <span>Stat Budget: {budget} pts</span>
            {budgetRange && <span>Target: {budgetRange.min}–{budgetRange.max} pts for {form.rarity}</span>}
          </div>
          <div className="budget-bar">
            <div
              className={`budget-bar-fill ${
                budgetRange
                  ? (budget > budgetRange.max ? 'over' : budget >= budgetRange.min ? 'ok' : 'warn')
                  : 'ok'
              }`}
              style={{ width: `${Math.min(100, budgetRange ? (budget / budgetRange.max * 100) : 50)}%` }}
            />
          </div>
        </div>

        <div className="modal-actions">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit}>
            {mode === 'edit' ? '💾 Save Changes' : '✨ Create Item'}
          </button>
        </div>
      </div>
    </div>
  );
}
