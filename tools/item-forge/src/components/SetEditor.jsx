// ─────────────────────────────────────────────────────────
// SetEditor.jsx — Set item manager & creator
// ─────────────────────────────────────────────────────────
// Phase 16E sets_config.json — full CRUD for set items,
// their pieces, stat bonuses, set bonus tiers, and
// skill modifiers.

import React, { useState, useMemo } from 'react';

const ALL_SLOTS = ['weapon', 'armor', 'accessory', 'helmet', 'boots'];
const CLASSES = ['crusader', 'confessor', 'inquisitor', 'ranger', 'hexblade'];

/** Format stat for display */
function fmtStat(stat, val, meta) {
  const info = meta?.stats?.[stat];
  if (!info) return `${stat}: ${val}`;
  if (info.type === 'float') return `+${(val * 100).toFixed(0)}% ${info.label}`;
  return `${val > 0 ? '+' : ''}${val} ${info.label}`;
}

export default function SetEditor({ config, statsMeta, onUpdate }) {
  const [editingSet, setEditingSet] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [classFilter, setClassFilter] = useState('all');

  // If no config, show scaffold UI to create one
  const sets = config?.sets || {};

  const setList = useMemo(() => {
    let list = Object.entries(sets).map(([id, s]) => ({ ...s, _id: id }));
    if (classFilter !== 'all') {
      list = list.filter(s => s.class_affinity === classFilter);
    }
    return list;
  }, [sets, classFilter]);

  function handleCreateSet(id, data) {
    const updated = config
      ? { ...config, sets: { ...config.sets, [id]: data } }
      : { sets: { [id]: data } };
    onUpdate(updated);
    setShowCreate(false);
  }

  function handleSaveSet(id, data) {
    const updated = { ...config, sets: { ...config.sets, [id]: data } };
    onUpdate(updated);
    setEditingSet(null);
  }

  function handleDeleteSet(id) {
    if (!window.confirm(`Delete set "${id}"? This cannot be undone.`)) return;
    const updated = { ...config, sets: { ...config.sets } };
    delete updated.sets[id];
    onUpdate(updated);
  }

  // ── No config at all ──────────────────────────────────
  if (!config) {
    return (
      <div>
        <div className="section-header">
          <h2>Set Items</h2>
          <button className="btn btn-primary ml-auto" onClick={() => setShowCreate(true)}>
            + Create First Set
          </button>
        </div>
        <div className="empty-state">
          <h3>No sets_config.json found</h3>
          <p>Phase 16E hasn't been implemented yet. Create a set below to generate the config file.</p>
          <p style={{ fontSize: 12, color: 'var(--text-dim)' }}>
            The config will be saved to server/configs/sets_config.json
          </p>
        </div>
        {showCreate && (
          <SetModal
            set={null} statsMeta={statsMeta} mode="create"
            onSave={(id, data) => handleCreateSet(id, data)}
            onClose={() => setShowCreate(false)}
          />
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="section-header">
        <h2>Set Items</h2>
        <span className="count-badge">{Object.keys(sets).length} sets</span>
        <span className="count-badge">
          {Object.values(sets).reduce((sum, s) => sum + (s.pieces || []).length, 0)} pieces
        </span>
        <button className="btn btn-primary ml-auto" onClick={() => setShowCreate(true)}>
          + New Set
        </button>
      </div>

      <div className="filter-bar">
        <select value={classFilter} onChange={e => setClassFilter(e.target.value)}>
          <option value="all">All Classes</option>
          {CLASSES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {/* Set Cards */}
      {setList.map(set => (
        <div key={set._id} className="card" style={{ marginBottom: 16, borderLeft: '3px solid var(--rarity-set)' }}>
          <div className="flex-row" style={{ marginBottom: 12 }}>
            <h3 style={{ margin: 0, color: 'var(--rarity-set)' }}>{set.name}</h3>
            <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>
              ({(set.pieces || []).length} pieces · {set.class_affinity || 'any'})
            </span>
            <div className="ml-auto flex-row gap-sm">
              <button className="btn btn-sm" onClick={() => setEditingSet({ ...set })}>✏️ Edit</button>
              <button className="btn btn-sm btn-danger" onClick={() => handleDeleteSet(set._id)}>🗑️</button>
            </div>
          </div>

          {/* Pieces */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 10, marginBottom: 12 }}>
            {(set.pieces || []).map((piece, i) => (
              <div key={i} style={{ background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: 10 }}>
                <div className="flex-row" style={{ marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, color: 'var(--rarity-set)', fontSize: 13 }}>{piece.name}</span>
                  <span className={`slot-badge ${piece.equip_slot}`} style={{ marginLeft: 'auto' }}>{piece.equip_slot}</span>
                </div>
                <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>
                  {Object.entries(piece.stat_bonuses || {}).map(([stat, val]) => {
                    if (val === 0) return null;
                    return <div key={stat} style={{ color: 'var(--success)' }}>{fmtStat(stat, val, statsMeta)}</div>;
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Set Bonuses */}
          <div style={{ fontSize: 12 }}>
            <div style={{ color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>Set Bonuses</div>
            {(set.bonuses || []).map((bonus, i) => (
              <div key={i} style={{ marginBottom: 4, paddingLeft: 8, borderLeft: '2px solid var(--rarity-set)' }}>
                <span style={{ color: 'var(--rarity-set)', fontWeight: 600 }}>{bonus.pieces_required} pieces: </span>
                <span style={{ color: 'var(--text)' }}>{bonus.description}</span>
                {bonus.stat_bonuses && Object.entries(bonus.stat_bonuses).map(([stat, val]) => (
                  <span key={stat} style={{ color: 'var(--success)', marginLeft: 8, fontFamily: 'var(--font-mono)' }}>
                    {fmtStat(stat, val, statsMeta)}
                  </span>
                ))}
              </div>
            ))}
          </div>
        </div>
      ))}

      {editingSet && (
        <SetModal
          set={editingSet} statsMeta={statsMeta} mode="edit"
          onSave={(data) => handleSaveSet(editingSet._id, data)}
          onClose={() => setEditingSet(null)}
        />
      )}
      {showCreate && (
        <SetModal
          set={null} statsMeta={statsMeta} mode="create"
          onSave={(id, data) => handleCreateSet(id, data)}
          onClose={() => setShowCreate(false)}
        />
      )}
    </div>
  );
}

// ── Set Create/Edit Modal ────────────────────────────────
function SetModal({ set, statsMeta, mode, onSave, onClose }) {
  const allStatKeys = Object.keys(statsMeta?.stats || {});

  const [form, setForm] = useState(() => {
    if (mode === 'edit' && set) {
      return {
        set_id: set.set_id || set._id || '',
        name: set.name || '',
        class_affinity: set.class_affinity || 'crusader',
        pieces: (set.pieces || []).map(p => ({ ...p, stat_bonuses: { ...p.stat_bonuses } })),
        bonuses: (set.bonuses || []).map(b => ({
          ...b,
          stat_bonuses: b.stat_bonuses ? { ...b.stat_bonuses } : {},
        })),
      };
    }
    return {
      set_id: '',
      name: '',
      class_affinity: 'crusader',
      pieces: [
        { piece_id: '', name: '', equip_slot: 'weapon', item_type: 'weapon', stat_bonuses: {} },
        { piece_id: '', name: '', equip_slot: 'armor', item_type: 'armor', stat_bonuses: {} },
        { piece_id: '', name: '', equip_slot: 'accessory', item_type: 'accessory', stat_bonuses: {} },
      ],
      bonuses: [
        { pieces_required: 2, description: '', stat_bonuses: {} },
        { pieces_required: 3, description: '', stat_bonuses: {} },
      ],
    };
  });

  function updateRoot(key, val) {
    setForm(prev => ({ ...prev, [key]: val }));
  }

  function updatePiece(idx, key, val) {
    setForm(prev => {
      const pieces = [...prev.pieces];
      pieces[idx] = { ...pieces[idx], [key]: val };
      return { ...prev, pieces };
    });
  }

  function updatePieceStat(idx, stat, val) {
    setForm(prev => {
      const pieces = [...prev.pieces];
      pieces[idx] = { ...pieces[idx], stat_bonuses: { ...pieces[idx].stat_bonuses, [stat]: val } };
      return { ...prev, pieces };
    });
  }

  function addPiece() {
    setForm(prev => ({
      ...prev,
      pieces: [...prev.pieces, { piece_id: '', name: '', equip_slot: 'weapon', item_type: 'weapon', stat_bonuses: {} }],
    }));
  }

  function removePiece(idx) {
    setForm(prev => ({ ...prev, pieces: prev.pieces.filter((_, i) => i !== idx) }));
  }

  function updateBonus(idx, key, val) {
    setForm(prev => {
      const bonuses = [...prev.bonuses];
      bonuses[idx] = { ...bonuses[idx], [key]: val };
      return { ...prev, bonuses };
    });
  }

  function updateBonusStat(idx, stat, val) {
    setForm(prev => {
      const bonuses = [...prev.bonuses];
      bonuses[idx] = { ...bonuses[idx], stat_bonuses: { ...bonuses[idx].stat_bonuses, [stat]: val } };
      return { ...prev, bonuses };
    });
  }

  function addBonus() {
    setForm(prev => ({
      ...prev,
      bonuses: [...prev.bonuses, { pieces_required: prev.pieces.length, description: '', stat_bonuses: {} }],
    }));
  }

  function removeBonus(idx) {
    setForm(prev => ({ ...prev, bonuses: prev.bonuses.filter((_, i) => i !== idx) }));
  }

  function handleSubmit() {
    // Clean all stat_bonuses
    const cleanPieces = form.pieces.map(p => {
      const clean = {};
      for (const [k, v] of Object.entries(p.stat_bonuses || {})) {
        const num = parseFloat(v) || 0;
        if (num !== 0) clean[k] = num;
      }
      return { ...p, stat_bonuses: clean, piece_id: p.piece_id || `${form.set_id}_${p.equip_slot}` };
    });

    const cleanBonuses = form.bonuses.map(b => {
      const clean = {};
      for (const [k, v] of Object.entries(b.stat_bonuses || {})) {
        const num = parseFloat(v) || 0;
        if (num !== 0) clean[k] = num;
      }
      return { ...b, stat_bonuses: clean, pieces_required: parseInt(b.pieces_required) || 2 };
    });

    const data = {
      set_id: form.set_id,
      name: form.name,
      class_affinity: form.class_affinity,
      pieces: cleanPieces,
      bonuses: cleanBonuses,
    };

    if (mode === 'edit') onSave(data);
    else onSave(form.set_id, data);
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ minWidth: 700, maxWidth: '90vw' }}>
        <h2 style={{ color: 'var(--rarity-set)' }}>
          {mode === 'edit' ? `Edit: ${form.name}` : 'Create New Set'}
        </h2>

        {/* Set basics */}
        <div className="form-row">
          {mode === 'create' && (
            <div className="form-group">
              <label>Set ID</label>
              <input type="text" value={form.set_id}
                onChange={e => updateRoot('set_id', e.target.value)}
                placeholder="e.g. crusaders_oath" />
            </div>
          )}
          <div className="form-group" style={{ flex: 2 }}>
            <label>Set Name</label>
            <input type="text" value={form.name}
              onChange={e => updateRoot('name', e.target.value)}
              placeholder="Crusader's Oath" style={{ width: '100%' }} />
          </div>
          <div className="form-group">
            <label>Class Affinity</label>
            <select value={form.class_affinity} onChange={e => updateRoot('class_affinity', e.target.value)}>
              {CLASSES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>

        {/* Pieces */}
        <div style={{ marginTop: 16 }}>
          <div className="flex-row mb-8">
            <label style={{ fontSize: 12, color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase' }}>
              Pieces ({form.pieces.length})
            </label>
            <button className="btn btn-sm ml-auto" onClick={addPiece}>+ Add Piece</button>
          </div>
          {form.pieces.map((piece, idx) => (
            <div key={idx} style={{ background: 'var(--bg-dark)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: 12, marginBottom: 8 }}>
              <div className="form-row">
                <div className="form-group">
                  <label>Name</label>
                  <input type="text" value={piece.name}
                    onChange={e => updatePiece(idx, 'name', e.target.value)}
                    placeholder="Set Warhammer" />
                </div>
                <div className="form-group">
                  <label>Slot</label>
                  <select value={piece.equip_slot}
                    onChange={e => { updatePiece(idx, 'equip_slot', e.target.value); updatePiece(idx, 'item_type', e.target.value === 'accessory' ? 'accessory' : e.target.value); }}>
                    {ALL_SLOTS.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <button className="btn btn-sm btn-danger" style={{ alignSelf: 'flex-end' }}
                  onClick={() => removePiece(idx)}>🗑️</button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 4, marginTop: 8 }}>
                {allStatKeys.map(stat => {
                  const info = statsMeta.stats[stat];
                  return (
                    <div key={stat} className="flex-row gap-sm" style={{ fontSize: 11 }}>
                      <label style={{ width: 80, color: 'var(--text-dim)' }}>{info.label}</label>
                      <input type="number" step={info.type === 'float' ? '0.01' : '1'}
                        value={piece.stat_bonuses[stat] ?? ''}
                        onChange={e => updatePieceStat(idx, stat, e.target.value)}
                        style={{ width: 60 }} placeholder="0" />
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Set Bonuses */}
        <div style={{ marginTop: 16 }}>
          <div className="flex-row mb-8">
            <label style={{ fontSize: 12, color: 'var(--text-dim)', fontWeight: 600, textTransform: 'uppercase' }}>
              Set Bonuses ({form.bonuses.length})
            </label>
            <button className="btn btn-sm ml-auto" onClick={addBonus}>+ Add Bonus Tier</button>
          </div>
          {form.bonuses.map((bonus, idx) => (
            <div key={idx} style={{ background: 'var(--bg-dark)', border: '1px solid var(--rarity-set)', borderRadius: 'var(--radius-sm)', padding: 12, marginBottom: 8 }}>
              <div className="form-row">
                <div className="form-group">
                  <label>Pieces Required</label>
                  <input type="number" value={bonus.pieces_required}
                    onChange={e => updateBonus(idx, 'pieces_required', e.target.value)} style={{ width: 60 }} />
                </div>
                <div className="form-group" style={{ flex: 3 }}>
                  <label>Description</label>
                  <input type="text" value={bonus.description}
                    onChange={e => updateBonus(idx, 'description', e.target.value)}
                    style={{ width: '100%' }}
                    placeholder="Describe the bonus effect..." />
                </div>
                <button className="btn btn-sm btn-danger" style={{ alignSelf: 'flex-end' }}
                  onClick={() => removeBonus(idx)}>🗑️</button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 4, marginTop: 8 }}>
                {allStatKeys.map(stat => {
                  const info = statsMeta.stats[stat];
                  return (
                    <div key={stat} className="flex-row gap-sm" style={{ fontSize: 11 }}>
                      <label style={{ width: 80, color: 'var(--text-dim)' }}>{info.label}</label>
                      <input type="number" step={info.type === 'float' ? '0.01' : '1'}
                        value={bonus.stat_bonuses[stat] ?? ''}
                        onChange={e => updateBonusStat(idx, stat, e.target.value)}
                        style={{ width: 60 }} placeholder="0" />
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <div className="modal-actions">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit}>
            {mode === 'edit' ? '💾 Save Changes' : '✨ Create Set'}
          </button>
        </div>
      </div>
    </div>
  );
}
