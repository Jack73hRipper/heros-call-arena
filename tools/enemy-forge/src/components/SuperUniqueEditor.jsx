// ─────────────────────────────────────────────────────────
// SuperUniqueEditor.jsx — Create/edit super unique encounters
// Phase 18J5: Boss skills, retinue skills, encounter summary
// ─────────────────────────────────────────────────────────

import React, { useState, useMemo } from 'react';

function makeDefaultSuperUnique(id) {
  return {
    id: id,
    base_enemy: 'demon',
    name: 'New Super Unique',
    title: 'Unknown Terror',
    flavor_text: 'A mysterious boss awaits...',
    floor_range: [3, 5],
    room_type: 'boss',
    base_hp: 400,
    base_melee_damage: 25,
    base_ranged_damage: 0,
    base_armor: 8,
    affixes: [],
    retinue: [],
    loot_table: {
      drop_chance: 1.0,
      min_items: 3,
      max_items: 4,
      guaranteed_rarity: 'rare',
      unique_item_chance: 0.15,
      pools: [],
    },
    tags: [],
    color: '#cc66ff',
    shape: 'star',
  };
}

/* ── Skill Resolution Helpers (J5.2 / J5.3) ──────────── */

/** Resolve class_id → array of skill objects from skills_config */
function resolveSkillsForClass(classId, skillsConfig) {
  if (!classId || !skillsConfig?.class_skills || !skillsConfig?.skills) return [];
  const skillIds = skillsConfig.class_skills[classId];
  if (!skillIds) return [];
  return skillIds.map(sid => skillsConfig.skills[sid]).filter(Boolean);
}

/** Get a one-line summary for a skill */
function skillOneLiner(skill) {
  if (!skill) return '';
  // Build a short summary from effects
  for (const eff of (skill.effects || [])) {
    if (eff.type === 'passive_enrage') {
      return `+${Math.round(((eff.damage_multiplier || 1) - 1) * 100)}% melee below ${Math.round((eff.hp_threshold || 0) * 100)}% HP`;
    }
    if (eff.type === 'damage_absorb') {
      return `absorbs ${eff.absorb_amount || 0} dmg for ${eff.duration_turns || 0} turns`;
    }
    if (eff.type === 'passive_aura_ally_buff') {
      return `+${eff.value || 0} ${(eff.stat || '').replace(/_/g, ' ')} per nearby ${eff.requires_tag || 'ally'}`;
    }
    if (eff.type === 'buff' && eff.stat === 'melee_damage_multiplier') {
      return `+${Math.round(((eff.magnitude || 1) - 1) * 100)}% melee dmg for ${eff.duration_turns || 0} turns`;
    }
    if (eff.type === 'buff' && eff.stat === 'damage_reduction_pct') {
      return `${Math.round((eff.magnitude || 0) * 100)}% dmg reduction for ${eff.duration_turns || 0} turns`;
    }
    if (eff.type === 'heal') {
      return `heals ${eff.magnitude || eff.amount || 0} HP`;
    }
    if (eff.type === 'melee_damage') {
      return `${eff.hits || 1} hit(s) at ${eff.damage_multiplier || 1}× dmg`;
    }
    if (eff.type === 'ranged_damage') {
      return `ranged ${eff.damage_multiplier || 1}× dmg`;
    }
    if (eff.type === 'dot') {
      return `${eff.damage_per_tick || 0} dmg/turn for ${eff.duration_turns || 0} turns`;
    }
    if (eff.type === 'aoe_damage') {
      return `AoE ${eff.damage_multiplier || 1}× dmg, radius ${eff.radius || 0}`;
    }
    if (eff.type === 'taunt') {
      return `taunt radius ${eff.radius || 0} for ${eff.duration_turns || 0} turns`;
    }
    if (eff.type === 'evasion') {
      return `${eff.charges || 0} dodge charges for ${eff.duration_turns || 0} turns`;
    }
    if (eff.type === 'teleport') {
      return 'teleport to target tile';
    }
    if (eff.type === 'shield_charges') {
      return `${eff.charges || 0} shield charges, reflects ${eff.reflect_damage || 0}`;
    }
  }
  return skill.description || '';
}

/** Build threat notes for the encounter summary (J5.6) */
function buildThreatNotes(su, enemies, skillsConfig) {
  const notes = [];
  const baseEnemy = enemies[su.base_enemy];
  const bossClassId = baseEnemy?.class_id;
  const bossSkills = resolveSkillsForClass(bossClassId, skillsConfig);

  // Check boss skills for threats
  for (const skill of bossSkills) {
    for (const eff of (skill.effects || [])) {
      if (eff.type === 'passive_enrage') {
        const threshHp = Math.round(su.base_hp * (eff.hp_threshold || 0.3));
        notes.push(`⚠ Boss enrages at ${threshHp} HP — watch for damage spike`);
      }
      if (eff.type === 'damage_absorb') {
        notes.push(`⚠ Boss can absorb ${eff.absorb_amount || 0} damage with ${skill.name}`);
      }
    }
  }

  // Check retinue for threats
  const retinue = su.retinue || [];
  for (const r of retinue) {
    const retEnemy = enemies[r.enemy_type];
    if (!retEnemy) continue;
    const retSkills = resolveSkillsForClass(retEnemy.class_id, skillsConfig);
    for (const skill of retSkills) {
      for (const eff of (skill.effects || [])) {
        if (eff.type === 'passive_aura_ally_buff' && r.count > 1) {
          const bonusPerUnit = (eff.value || 0) * (r.count - 1);
          notes.push(`⚠ ${retEnemy.name}s gain +${bonusPerUnit} ${(eff.stat || 'dmg').replace(/_/g, ' ')} each from ${skill.name} (${r.count - 1} nearby)`);
        }
        if (eff.type === 'buff' && eff.stat === 'damage_reduction_pct') {
          notes.push(`⚠ ${retEnemy.name} will ward lowest-HP ally, extending fight`);
        }
        if (eff.type === 'buff' && eff.stat === 'melee_damage_multiplier') {
          notes.push(`⚠ ${retEnemy.name} buffs ally melee damage by +${Math.round(((eff.magnitude || 1) - 1) * 100)}%`);
        }
        if (eff.type === 'heal') {
          notes.push(`⚠ ${retEnemy.name} can heal allies — prioritize killing`);
        }
      }
    }
  }

  return notes;
}

export default function SuperUniqueEditor({ config, enemies, rarity, skills, meta, onUpdate }) {
  const [selected, setSelected] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newId, setNewId] = useState('');

  const superUniques = config?.super_uniques || {};
  const spawnRules = config?.spawn_rules || {};
  const su = selected ? superUniques[selected] : null;

  const updateSU = (id, field, value) => {
    const updated = {
      ...config,
      super_uniques: {
        ...config.super_uniques,
        [id]: { ...config.super_uniques[id], [field]: value }
      }
    };
    onUpdate(updated);
  };

  const deleteSU = (id) => {
    const newSU = { ...config.super_uniques };
    delete newSU[id];
    onUpdate({ ...config, super_uniques: newSU });
    if (selected === id) setSelected(null);
  };

  const createSU = () => {
    if (!newId || superUniques[newId]) return;
    const updated = {
      ...config,
      super_uniques: { ...config.super_uniques, [newId]: makeDefaultSuperUnique(newId) }
    };
    onUpdate(updated);
    setSelected(newId);
    setShowCreate(false);
    setNewId('');
  };

  const updateRetinue = (suId, idx, field, value) => {
    const retinue = [...(config.super_uniques[suId].retinue || [])];
    retinue[idx] = { ...retinue[idx], [field]: value };
    updateSU(suId, 'retinue', retinue);
  };

  return (
    <div className="su-editor-layout">
      {/* List */}
      <div className="su-browser">
        <div className="browser-header">
          <h3>Super Uniques ({Object.keys(superUniques).length})</h3>
          <button className="btn btn-sm btn-primary" onClick={() => setShowCreate(true)}>+ New</button>
        </div>
        <div className="browser-list">
          {Object.entries(superUniques).map(([id, data]) => (
            <div
              key={id}
              className={`browser-item ${selected === id ? 'selected' : ''}`}
              onClick={() => setSelected(id)}
            >
              <div className="enemy-color-dot" style={{ background: data.color || '#cc66ff' }} />
              <div className="enemy-info">
                <div className="enemy-name" style={{ color: '#cc66ff' }}>{data.name}</div>
                <div className="enemy-role">{data.title}</div>
              </div>
            </div>
          ))}
          {Object.keys(superUniques).length === 0 && (
            <div className="empty-state" style={{ padding: 16 }}>
              <p>No super uniques defined yet.</p>
            </div>
          )}
        </div>

        {/* Spawn Rules */}
        <div className="card" style={{ margin: 12, padding: 10, fontSize: 12 }}>
          <h4 style={{ fontSize: 13 }}>Spawn Rules</h4>
          <div className="text-dim">
            Per-floor chance: {(spawnRules.per_floor_chance || 0.25) * 100}%<br />
            Max per run: {spawnRules.max_per_run || 1}<br />
            Min floor: {spawnRules.min_floor || 3}
          </div>
        </div>
      </div>

      {/* Detail */}
      <div className="su-detail">
        {showCreate && (
          <div className="card mb-8">
            <h4>Create Super Unique</h4>
            <div className="form-group">
              <label>ID (snake_case)</label>
              <input
                type="text"
                value={newId}
                onChange={e => setNewId(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                placeholder="e.g. skull_lord"
              />
            </div>
            {newId && superUniques[newId] && <div style={{ color: 'var(--danger)', fontSize: 12 }}>ID already exists!</div>}
            <div className="flex-row gap-sm">
              <button className="btn btn-primary" disabled={!newId || !!superUniques[newId]} onClick={createSU}>Create</button>
              <button className="btn" onClick={() => { setShowCreate(false); setNewId(''); }}>Cancel</button>
            </div>
          </div>
        )}

        {!su && !showCreate && (
          <div className="empty-state">
            <h3>Select a Super Unique to edit</h3>
            <p>Hand-crafted named bosses with fixed affixes, retinue, and loot tables.</p>
          </div>
        )}

        {su && (
          <>
            {/* Identity */}
            <div className="card mb-8">
              <div className="flex-row" style={{ justifyContent: 'space-between' }}>
                <h4 style={{ color: '#cc66ff' }}>{su.name}</h4>
                <button className="btn btn-danger btn-sm" onClick={() => {
                  if (confirm(`Delete ${su.name}?`)) deleteSU(selected);
                }}>🗑️</button>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Name</label>
                  <input type="text" value={su.name || ''} onChange={e => updateSU(selected, 'name', e.target.value)} />
                </div>
                <div className="form-group">
                  <label>Title</label>
                  <input type="text" value={su.title || ''} onChange={e => updateSU(selected, 'title', e.target.value)} />
                </div>
              </div>
              <div className="form-group">
                <label>Flavor Text</label>
                <textarea
                  value={su.flavor_text || ''}
                  onChange={e => updateSU(selected, 'flavor_text', e.target.value)}
                  rows={2}
                  style={{ fontStyle: 'italic' }}
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Base Enemy</label>
                  <select value={su.base_enemy || ''} onChange={e => updateSU(selected, 'base_enemy', e.target.value)}>
                    {Object.entries(enemies).map(([id, e]) => (
                      <option key={id} value={id}>{e.name}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>Floor Range</label>
                  <div className="flex-row gap-sm">
                    <input type="number" value={(su.floor_range || [1, 1])[0]} onChange={e => updateSU(selected, 'floor_range', [parseInt(e.target.value) || 1, (su.floor_range || [1, 1])[1]])} style={{ width: 60 }} />
                    <span>–</span>
                    <input type="number" value={(su.floor_range || [1, 1])[1]} onChange={e => updateSU(selected, 'floor_range', [(su.floor_range || [1, 1])[0], parseInt(e.target.value) || 1])} style={{ width: 60 }} />
                  </div>
                </div>
                <div className="form-group">
                  <label>Room Type</label>
                  <input type="text" value={su.room_type || 'boss'} onChange={e => updateSU(selected, 'room_type', e.target.value)} />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Color</label>
                  <div className="flex-row gap-sm">
                    <input type="color" value={su.color || '#cc66ff'} onChange={e => updateSU(selected, 'color', e.target.value)} />
                    <input type="text" value={su.color || ''} onChange={e => updateSU(selected, 'color', e.target.value)} style={{ width: 90 }} />
                  </div>
                </div>
                <div className="form-group">
                  <label>Shape</label>
                  <select value={su.shape || 'star'} onChange={e => updateSU(selected, 'shape', e.target.value)}>
                    {(meta?.shapes || []).map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
              </div>
            </div>

            {/* Stats */}
            <div className="card mb-8">
              <h4>Fixed Stats (overrides base enemy)</h4>
              <div className="stat-grid">
                {[
                  { key: 'base_hp', label: 'HP' },
                  { key: 'base_melee_damage', label: 'Melee Damage' },
                  { key: 'base_ranged_damage', label: 'Ranged Damage' },
                  { key: 'base_armor', label: 'Armor' },
                ].map(f => (
                  <div key={f.key} className="stat-slider-row">
                    <label>{f.label}</label>
                    <input
                      type="number"
                      value={su[f.key] || 0}
                      onChange={e => updateSU(selected, f.key, parseInt(e.target.value) || 0)}
                      className="stat-num-input"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Affixes */}
            <div className="card mb-8">
              <h4>Fixed Affixes</h4>
              <div className="checkbox-group">
                {Object.keys(rarity?.affixes || {}).map(aid => (
                  <label key={aid}>
                    <input
                      type="checkbox"
                      checked={(su.affixes || []).includes(aid)}
                      onChange={e => {
                        const affixes = [...(su.affixes || [])];
                        if (e.target.checked) affixes.push(aid);
                        else affixes.splice(affixes.indexOf(aid), 1);
                        updateSU(selected, 'affixes', affixes);
                      }}
                    />
                    {rarity.affixes[aid].name}
                  </label>
                ))}
              </div>
            </div>

            {/* Tags */}
            <div className="card mb-8">
              <h4>Tags</h4>
              <div className="checkbox-group">
                {['undead', 'demon', 'beast', 'construct', 'aberration', 'humanoid'].map(tag => (
                  <label key={tag}>
                    <input
                      type="checkbox"
                      checked={(su.tags || []).includes(tag)}
                      onChange={e => {
                        const tags = [...(su.tags || [])];
                        if (e.target.checked) tags.push(tag);
                        else tags.splice(tags.indexOf(tag), 1);
                        updateSU(selected, 'tags', tags);
                      }}
                    />
                    {tag}
                  </label>
                ))}
              </div>
            </div>

            {/* Retinue */}
            <div className="card mb-8">
              <h4>Retinue (fixed followers)</h4>
              {(su.retinue || []).map((r, i) => (
                <div key={i} className="flex-row gap-sm mb-8">
                  <select value={r.enemy_type} onChange={e => updateRetinue(selected, i, 'enemy_type', e.target.value)}>
                    {Object.entries(enemies).map(([id, e]) => (
                      <option key={id} value={id}>{e.name}</option>
                    ))}
                  </select>
                  <span>×</span>
                  <input type="number" min="1" max="8" value={r.count || 1} onChange={e => updateRetinue(selected, i, 'count', parseInt(e.target.value) || 1)} style={{ width: 50 }} />
                  <button className="btn btn-danger btn-sm" onClick={() => {
                    const ret = [...(su.retinue || [])];
                    ret.splice(i, 1);
                    updateSU(selected, 'retinue', ret);
                  }}>✕</button>
                </div>
              ))}
              <button className="btn btn-sm" onClick={() => {
                const ret = [...(su.retinue || []), { enemy_type: 'imp', count: 2 }];
                updateSU(selected, 'retinue', ret);
              }}>+ Add Retinue</button>
            </div>

            {/* Loot Table Summary */}
            <div className="card mb-8">
              <h4>Loot Table</h4>
              <div className="form-row">
                <div className="form-group">
                  <label>Drop Chance</label>
                  <input type="number" step="0.1" min="0" max="1" value={su.loot_table?.drop_chance ?? 1.0} onChange={e => updateSU(selected, 'loot_table', { ...su.loot_table, drop_chance: parseFloat(e.target.value) })} />
                </div>
                <div className="form-group">
                  <label>Min Items</label>
                  <input type="number" min="0" max="10" value={su.loot_table?.min_items ?? 3} onChange={e => updateSU(selected, 'loot_table', { ...su.loot_table, min_items: parseInt(e.target.value) })} />
                </div>
                <div className="form-group">
                  <label>Max Items</label>
                  <input type="number" min="0" max="10" value={su.loot_table?.max_items ?? 4} onChange={e => updateSU(selected, 'loot_table', { ...su.loot_table, max_items: parseInt(e.target.value) })} />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Guaranteed Rarity</label>
                  <select value={su.loot_table?.guaranteed_rarity || 'rare'} onChange={e => updateSU(selected, 'loot_table', { ...su.loot_table, guaranteed_rarity: e.target.value })}>
                    <option value="common">Common</option>
                    <option value="magic">Magic</option>
                    <option value="rare">Rare</option>
                    <option value="epic">Epic</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Unique Item Chance</label>
                  <input type="number" step="0.05" min="0" max="1" value={su.loot_table?.unique_item_chance ?? 0.15} onChange={e => updateSU(selected, 'loot_table', { ...su.loot_table, unique_item_chance: parseFloat(e.target.value) })} />
                </div>
              </div>
            </div>

            {/* Preview — J5 Enhanced Encounter Preview */}
            <EncounterPreview su={su} enemies={enemies} rarity={rarity} skills={skills} />
          </>
        )}
      </div>
    </div>
  );
}


/* ── J5.4–J5.6: Encounter Preview with Skills & Threat Analysis ── */

function EncounterPreview({ su, enemies, rarity, skills }) {
  if (!su) return null;

  const baseEnemy = enemies[su.base_enemy];
  const bossClassId = baseEnemy?.class_id;
  const bossSkills = useMemo(
    () => resolveSkillsForClass(bossClassId, skills),
    [bossClassId, skills]
  );

  // J5.3: Resolve retinue skills, grouped by enemy type
  const retinueGroups = useMemo(() => {
    return (su.retinue || []).map(r => {
      const retEnemy = enemies[r.enemy_type];
      const retSkills = resolveSkillsForClass(retEnemy?.class_id, skills);
      return {
        enemy_type: r.enemy_type,
        name: retEnemy?.name || r.enemy_type,
        count: r.count || 1,
        hp: retEnemy?.base_hp || 0,
        skills: retSkills,
      };
    });
  }, [su.retinue, enemies, skills]);

  // J5.6: Encounter summary
  const totalRetinueCount = retinueGroups.reduce((sum, g) => sum + g.count, 0);
  const totalEnemies = 1 + totalRetinueCount;
  const bossHp = su.base_hp || 0;
  const retinueHpTotal = retinueGroups.reduce((sum, g) => sum + g.hp * g.count, 0);
  const totalHpPool = bossHp + retinueHpTotal;

  const threatNotes = useMemo(
    () => buildThreatNotes(su, enemies, skills),
    [su, enemies, skills]
  );

  return (
    <div className="card">
      <h4>Encounter Preview</h4>
      <div className="su-preview">
        {/* Identity */}
        <div className="su-preview-name" style={{ color: '#cc66ff', fontSize: 18, fontWeight: 700 }}>
          {su.name}
        </div>
        <div className="text-dim" style={{ fontStyle: 'italic', marginBottom: 8 }}>
          {su.title}
        </div>
        <div className="text-dim" style={{ fontStyle: 'italic', fontSize: 13, marginBottom: 12 }}>
          "{su.flavor_text}"
        </div>

        {/* Stats */}
        <div className="stat-callout">
          <span>HP: <strong>{su.base_hp}</strong></span>
          <span>Melee: <strong>{su.base_melee_damage || 0}</strong></span>
          <span>Ranged: <strong>{su.base_ranged_damage || 0}</strong></span>
          <span>Armor: <strong>{su.base_armor || 0}</strong></span>
        </div>

        {/* Affixes */}
        <div style={{ marginTop: 8, fontSize: 12 }}>
          <strong>Affixes:</strong> {(su.affixes || []).map(a => rarity?.affixes?.[a]?.name || a).join(', ') || 'none'}
        </div>

        {/* Retinue */}
        <div style={{ marginTop: 4, fontSize: 12 }}>
          <strong>Retinue:</strong> {(su.retinue || []).map(r => `${r.count}× ${enemies[r.enemy_type]?.name || r.enemy_type}`).join(', ') || 'none'}
        </div>

        {/* Floors */}
        <div style={{ marginTop: 4, fontSize: 12 }}>
          <strong>Floors:</strong> {(su.floor_range || [1, 1]).join('–')}
        </div>

        {/* ── J5.4: Boss Skills ── */}
        {bossSkills.length > 0 && (
          <div className="su-skills-section">
            <div className="su-skills-heading">Boss Skills</div>
            <div className="su-skills-list">
              {bossSkills.map((sk, i) => (
                <div key={i} className={`su-skill-row ${sk.is_passive ? 'su-skill-passive' : ''}`}>
                  <span className="su-skill-icon">{sk.icon || '⚙️'}</span>
                  <span className="su-skill-name">{sk.name}</span>
                  {sk.is_passive && <span className="su-skill-badge passive">passive</span>}
                  <span className="su-skill-summary">— {skillOneLiner(sk)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── J5.5: Retinue Skills ── */}
        {retinueGroups.length > 0 && retinueGroups.some(g => g.skills.length > 0) && (
          <div className="su-skills-section">
            <div className="su-skills-heading">Retinue Skills</div>
            <div className="su-skills-list">
              {retinueGroups.map((g, gi) => (
                g.skills.length > 0 && (
                  <div key={gi} className="su-retinue-skill-group">
                    <div className="su-retinue-label">
                      {g.name} (×{g.count}):
                    </div>
                    {g.skills.map((sk, si) => (
                      <div key={si} className={`su-skill-row su-retinue-skill ${sk.is_passive ? 'su-skill-passive' : ''}`}>
                        <span className="su-skill-icon">{sk.icon || '⚙️'}</span>
                        <span className="su-skill-name">{sk.name}</span>
                        {sk.is_passive && <span className="su-skill-badge passive">passive</span>}
                        <span className="su-skill-summary">— {skillOneLiner(sk)}</span>
                      </div>
                    ))}
                  </div>
                )
              ))}
            </div>
          </div>
        )}

        {/* ── J5.6: Encounter Summary ── */}
        <div className="su-encounter-summary">
          <div className="su-skills-heading">Encounter Summary</div>
          <div className="su-summary-stats">
            <span>Total enemies: <strong>{totalEnemies}</strong> (1 boss + {totalRetinueCount} retinue)</span>
            <span>Total HP pool: <strong>{bossHp}</strong>{retinueGroups.map(g => ` + ${g.hp * g.count}`).join('')} = <strong>{totalHpPool}</strong></span>
          </div>
          {threatNotes.length > 0 && (
            <div className="su-threat-notes">
              <div className="su-threat-heading">Threat Notes</div>
              {threatNotes.map((note, i) => (
                <div key={i} className="su-threat-note">{note}</div>
              ))}
            </div>
          )}
          {threatNotes.length === 0 && (
            <div className="su-threat-notes su-threat-none">
              <span className="text-dim">No special skill threats detected.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
