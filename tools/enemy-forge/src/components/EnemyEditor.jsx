// ─────────────────────────────────────────────────────────
// EnemyEditor.jsx — Edit enemy stats, skills, tags, colors
// ─────────────────────────────────────────────────────────

import React, { useState, useEffect, useRef, useCallback } from 'react';
import SpritePicker from './SpritePicker.jsx';
import SkillDetailCard from './SkillDetailCard.jsx';

const SHEET_URL = '/spritesheet.png';

const STAT_FIELDS = [
  { key: 'base_hp',            label: 'HP',              min: 1,  max: 9999, step: 5 },
  { key: 'base_melee_damage',  label: 'Melee Damage',    min: 0,  max: 100,  step: 1 },
  { key: 'base_ranged_damage', label: 'Ranged Damage',   min: 0,  max: 100,  step: 1 },
  { key: 'base_armor',         label: 'Armor',           min: 0,  max: 30,   step: 1 },
  { key: 'base_vision_range',  label: 'Vision Range',    min: 1,  max: 12,   step: 1 },
  { key: 'ranged_range',       label: 'Ranged Range',    min: 1,  max: 8,    step: 1 },
];

const ALL_TAGS = ['undead', 'demon', 'beast', 'construct', 'aberration', 'humanoid'];

function makeDefaultEnemy(id) {
  return {
    enemy_id: id,
    name: 'New Enemy',
    role: 'Swarm',
    description: 'A new enemy type.',
    base_hp: 100,
    base_melee_damage: 10,
    base_ranged_damage: 0,
    base_armor: 3,
    base_vision_range: 6,
    ranged_range: 1,
    ai_behavior: 'aggressive',
    color: '#cc4444',
    shape: 'diamond',
    is_boss: false,
    tags: [],
  };
}

export default function EnemyEditor({ enemy, enemyId, allEnemies, skills, classes, meta, spriteAtlas, onUpdate, onCreate, onDelete }) {
  const [showCreate, setShowCreate] = useState(false);
  const [newId, setNewId] = useState('');
  const canvasRef = useRef(null);
  const [sheetImage, setSheetImage] = useState(null);

  // Load spritesheet for preview
  useEffect(() => {
    const img = new Image();
    img.onload = () => setSheetImage(img);
    img.src = SHEET_URL;
  }, []);

  // Resolve the sprite region from the atlas for this enemy's sprite_id
  const getSpriteRegion = useCallback(() => {
    if (!enemy?.sprite_id || !spriteAtlas?.sprites) return null;
    const sid = enemy.sprite_id;
    // Search atlas sprites for a match (atlas names are PascalCase like "Demon_1")
    for (const [name, data] of Object.entries(spriteAtlas.sprites)) {
      const normalized = name
        .replace(/_1$/, '')
        .replace(/([a-z])([A-Z])/g, '$1_$2')
        .replace(/\s+/g, '_')
        .toLowerCase();
      if (normalized === sid) {
        return data;
      }
    }
    return null;
  }, [enemy?.sprite_id, spriteAtlas]);

  // Draw preview
  const drawPreview = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !enemy) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const tiers = [
      { label: 'Normal',  color: '#ffffff',  scale: 1.0 },
      { label: 'Champion', color: '#6688ff', scale: 1.0 },
      { label: 'Rare',    color: '#ffcc00',  scale: 1.1 },
      { label: 'Super',   color: '#cc66ff',  scale: 1.2 },
    ];

    const spriteRegion = getSpriteRegion();
    const hasSprite = spriteRegion && sheetImage;

    const cellW = w / 4;
    tiers.forEach((tier, i) => {
      const cx = cellW * i + cellW / 2;
      const cy = h / 2 - 8;
      const size = 18 * tier.scale;

      // Outline glow for rarity
      if (tier.label !== 'Normal') {
        ctx.save();
        ctx.strokeStyle = tier.color;
        ctx.lineWidth = tier.label === 'Rare' ? 3 : tier.label === 'Super' ? 4 : 2;
        ctx.globalAlpha = 0.5;
        ctx.shadowColor = tier.color;
        ctx.shadowBlur = tier.label === 'Super' ? 12 : 8;
        ctx.beginPath();
        ctx.arc(cx, cy, size + 4, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }

      if (hasSprite) {
        // Draw actual sprite
        const spriteDrawSize = size * 2.6;
        ctx.drawImage(
          sheetImage,
          spriteRegion.x, spriteRegion.y, spriteRegion.w, spriteRegion.h,
          cx - spriteDrawSize / 2, cy - spriteDrawSize / 2 - 2,
          spriteDrawSize, spriteDrawSize
        );
      } else {
        // Shape fallback
        ctx.fillStyle = enemy.color || '#888';
        drawShape(ctx, enemy.shape, cx, cy, size);
        ctx.fill();

        ctx.strokeStyle = tier.color;
        ctx.lineWidth = 1.5;
        drawShape(ctx, enemy.shape, cx, cy, size);
        ctx.stroke();
      }

      // Label
      ctx.fillStyle = tier.color;
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(tier.label, cx, h - 6);
    });
  }, [enemy, sheetImage, getSpriteRegion]);

  useEffect(() => { drawPreview(); }, [drawPreview]);

  if (!enemy && !showCreate) {
    return (
      <div className="enemy-editor">
        <div className="empty-state">
          <h3>Select an enemy to edit</h3>
          <p>Choose from the list on the left, or create a new one.</p>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            + Create New Enemy
          </button>
        </div>
      </div>
    );
  }

  if (showCreate || !enemy) {
    return (
      <div className="enemy-editor">
        <div className="card">
          <h3>Create New Enemy</h3>
          <div className="form-group">
            <label>Enemy ID (snake_case)</label>
            <input
              type="text"
              value={newId}
              onChange={e => setNewId(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
              placeholder="e.g. fire_elemental"
            />
          </div>
          {newId && allEnemies[newId] && (
            <div style={{ color: 'var(--danger)', fontSize: 12, marginBottom: 8 }}>
              ID already exists!
            </div>
          )}
          <div className="flex-row">
            <button
              className="btn btn-primary"
              disabled={!newId || allEnemies[newId]}
              onClick={() => {
                onCreate(newId, makeDefaultEnemy(newId));
                setShowCreate(false);
                setNewId('');
              }}
            >
              Create
            </button>
            <button className="btn" onClick={() => { setShowCreate(false); setNewId(''); }}>
              Cancel
            </button>
          </div>
        </div>
      </div>
    );
  }

  const update = (field, value) => {
    onUpdate(enemyId, { ...enemy, [field]: value });
  };

  // Get class skills for preview
  const classSkills = [];
  if (enemy.class_id && skills?.class_skills) {
    const skillIds = skills.class_skills[enemy.class_id] || [];
    skillIds.forEach(sid => {
      const sk = skills.skills?.[sid];
      if (sk) classSkills.push(sk);
    });
  }

  // Build dropdown options from class_skills keys, sorted alphabetically
  // Hero classes (not typically assigned to enemies) are grouped at the bottom
  const HERO_CLASSES = new Set(['crusader', 'confessor', 'inquisitor', 'ranger', 'hexblade', 'mage']);
  const classSkillKeys = Object.keys(skills?.class_skills || {});
  const enemyClassOptions = classSkillKeys
    .filter(k => !HERO_CLASSES.has(k))
    .sort((a, b) => a.localeCompare(b));
  const heroClassOptions = classSkillKeys
    .filter(k => HERO_CLASSES.has(k))
    .sort((a, b) => a.localeCompare(b));

  const getSkillCount = (classId) => (skills?.class_skills?.[classId] || []).length;

  return (
    <div className="enemy-editor">
      <div className="editor-header">
        <h3 style={{ color: enemy.color }}>
          {enemy.name}
          {enemy.is_boss && <span className="tag-badge boss-badge" style={{ marginLeft: 8 }}>BOSS</span>}
        </h3>
        <div className="flex-row gap-sm">
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>+ New</button>
          <button className="btn btn-danger btn-sm" onClick={() => {
            if (confirm(`Delete ${enemy.name}?`)) onDelete(enemyId);
          }}>🗑️ Delete</button>
        </div>
      </div>

      {/* Live Preview Canvas */}
      <div className="card mb-8">
        <label className="form-label">Rarity Preview</label>
        <canvas ref={canvasRef} width={400} height={100} className="preview-canvas" />
      </div>

      {/* Identity */}
      <div className="card mb-8">
        <h4>Identity</h4>
        <div className="form-row">
          <div className="form-group">
            <label>Name</label>
            <input type="text" value={enemy.name || ''} onChange={e => update('name', e.target.value)} />
          </div>
          <div className="form-group">
            <label>Enemy ID</label>
            <input type="text" value={enemy.enemy_id || ''} disabled className="text-dim" />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label>Role</label>
            <input type="text" value={enemy.role || ''} onChange={e => update('role', e.target.value)} />
          </div>
          <div className="form-group">
            <label>AI Behavior</label>
            <select value={enemy.ai_behavior || 'aggressive'} onChange={e => update('ai_behavior', e.target.value)}>
              {(meta?.ai_behaviors || []).map(b => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>
        </div>
        <div className="form-group">
          <label>Description</label>
          <textarea
            value={enemy.description || ''}
            onChange={e => update('description', e.target.value)}
            rows={2}
          />
        </div>
      </div>

      {/* Stats */}
      <div className="card mb-8">
        <h4>Base Stats</h4>
        <div className="stat-grid">
          {STAT_FIELDS.map(sf => (
            <div key={sf.key} className="stat-slider-row">
              <label>{sf.label}</label>
              <input
                type="range"
                min={sf.min}
                max={sf.max}
                step={sf.step}
                value={enemy[sf.key] || 0}
                onChange={e => update(sf.key, parseInt(e.target.value))}
              />
              <input
                type="number"
                min={sf.min}
                max={sf.max}
                step={sf.step}
                value={enemy[sf.key] || 0}
                onChange={e => update(sf.key, parseInt(e.target.value) || 0)}
                className="stat-num-input"
              />
            </div>
          ))}
        </div>
        {/* Effective DPS callout */}
        <div className="stat-callout">
          <span>Effective HP: <strong>{enemy.base_hp || 0}</strong></span>
          <span>Melee DPS: <strong>{(enemy.base_melee_damage || 0).toFixed(0)}/turn</strong></span>
          <span>Ranged DPS: <strong>{enemy.base_ranged_damage > 0 ? `${enemy.base_ranged_damage}/turn` : '—'}</strong></span>
          <span>Armor: <strong>{enemy.base_armor || 0}</strong></span>
        </div>
      </div>

      {/* Visuals */}
      <div className="card mb-8">
        <h4>Visuals</h4>
        <div className="form-row">
          <div className="form-group">
            <label>Color (shape fallback)</label>
            <div className="flex-row gap-sm">
              <input type="color" value={enemy.color || '#888888'} onChange={e => update('color', e.target.value)} />
              <input type="text" value={enemy.color || ''} onChange={e => update('color', e.target.value)} style={{ width: 90 }} />
            </div>
          </div>
          <div className="form-group">
            <label>Shape (fallback)</label>
            <select value={enemy.shape || 'diamond'} onChange={e => update('shape', e.target.value)}>
              {(meta?.shapes || []).map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>

        {/* Sprite Assignment */}
        <div className="sprite-section">
          <label className="form-label">Sprite Assignment</label>
          <SpritePicker
            spriteAtlas={spriteAtlas}
            enemyId={enemyId}
            enemy={enemy}
            onUpdate={onUpdate}
          />
        </div>
      </div>

      {/* Tags & Flags */}
      <div className="card mb-8">
        <h4>Tags & Flags</h4>
        <div className="checkbox-group">
          {ALL_TAGS.map(tag => (
            <label key={tag}>
              <input
                type="checkbox"
                checked={(enemy.tags || []).includes(tag)}
                onChange={e => {
                  const tags = [...(enemy.tags || [])];
                  if (e.target.checked) tags.push(tag);
                  else tags.splice(tags.indexOf(tag), 1);
                  update('tags', tags);
                }}
              />
              {tag}
            </label>
          ))}
        </div>
        <div className="form-row mt-12">
          <label>
            <input type="checkbox" checked={enemy.is_boss || false} onChange={e => update('is_boss', e.target.checked)} />
            Is Boss
          </label>
          <label>
            <input
              type="checkbox"
              checked={enemy.allow_rarity_upgrade !== false}
              onChange={e => update('allow_rarity_upgrade', e.target.checked)}
            />
            Allow Rarity Upgrade
          </label>
        </div>
      </div>

      {/* Class / Skills */}
      <div className="card mb-8">
        <h4>Class & Skills</h4>
        <div className="form-group">
          <label>Class ID (links to skill set)</label>
          <select
            value={enemy.class_id || ''}
            onChange={e => update('class_id', e.target.value || undefined)}
          >
            <option value="">(none — no skills)</option>
            {enemyClassOptions.length > 0 && (
              <optgroup label="Enemy Classes">
                {enemyClassOptions.map(cid => (
                  <option key={cid} value={cid}>
                    {cid} ({getSkillCount(cid)} {getSkillCount(cid) === 1 ? 'skill' : 'skills'})
                  </option>
                ))}
              </optgroup>
            )}
            {heroClassOptions.length > 0 && (
              <optgroup label="Hero Classes">
                {heroClassOptions.map(cid => (
                  <option key={cid} value={cid}>
                    {cid} ({getSkillCount(cid)} {getSkillCount(cid) === 1 ? 'skill' : 'skills'})
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        </div>
        {classSkills.length > 0 && (
          <div className="skill-preview">
            <label className="form-label">Skills from class: {enemy.class_id}</label>
            <div className="skill-detail-list">
              {classSkills.map(sk => (
                <SkillDetailCard key={sk.skill_id} skill={sk} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Excluded Affixes */}
      <div className="card mb-8">
        <h4>Excluded Affixes</h4>
        <p className="text-dim" style={{ fontSize: 12 }}>Affixes that should never roll on this enemy type.</p>
        <input
          type="text"
          value={(enemy.excluded_affixes || []).join(', ')}
          onChange={e => {
            const val = e.target.value.trim();
            update('excluded_affixes', val ? val.split(',').map(s => s.trim()).filter(Boolean) : undefined);
          }}
          placeholder="e.g. teleporter, shielded"
        />
      </div>
    </div>
  );
}

/** Draw a unit shape on canvas */
function drawShape(ctx, shape, cx, cy, size) {
  ctx.beginPath();
  switch (shape) {
    case 'circle':
      ctx.arc(cx, cy, size, 0, Math.PI * 2);
      break;
    case 'square':
      ctx.rect(cx - size, cy - size, size * 2, size * 2);
      break;
    case 'diamond':
      ctx.moveTo(cx, cy - size);
      ctx.lineTo(cx + size, cy);
      ctx.lineTo(cx, cy + size);
      ctx.lineTo(cx - size, cy);
      ctx.closePath();
      break;
    case 'triangle':
      ctx.moveTo(cx, cy - size);
      ctx.lineTo(cx + size, cy + size * 0.8);
      ctx.lineTo(cx - size, cy + size * 0.8);
      ctx.closePath();
      break;
    case 'star': {
      const spikes = 5;
      const outerR = size;
      const innerR = size * 0.5;
      for (let i = 0; i < spikes * 2; i++) {
        const r = i % 2 === 0 ? outerR : innerR;
        const angle = (Math.PI / spikes) * i - Math.PI / 2;
        const x = cx + Math.cos(angle) * r;
        const y = cy + Math.sin(angle) * r;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      break;
    }
    case 'hexagon': {
      for (let i = 0; i < 6; i++) {
        const angle = (Math.PI / 3) * i - Math.PI / 6;
        const x = cx + Math.cos(angle) * size;
        const y = cy + Math.sin(angle) * size;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      break;
    }
    default:
      ctx.arc(cx, cy, size, 0, Math.PI * 2);
  }
}
