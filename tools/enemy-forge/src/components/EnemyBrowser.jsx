// ─────────────────────────────────────────────────────────
// EnemyBrowser.jsx — Left sidebar listing all enemy types
// ─────────────────────────────────────────────────────────

import React, { useState, useMemo, useEffect, useRef } from 'react';

const SHEET_URL = '/spritesheet.png';

const TAG_COLORS = {
  undead:     '#8866cc',
  demon:      '#cc4444',
  beast:      '#88aa44',
  construct:  '#7788aa',
  aberration: '#aa44aa',
  humanoid:   '#cc8833',
};

export default function EnemyBrowser({ enemies, meta, selectedEnemy, onSelect, spriteAtlas, skills }) {
  const [search, setSearch] = useState('');
  const [tagFilter, setTagFilter] = useState('all');
  const [roleFilter, setRoleFilter] = useState('all');
  const [skillFilter, setSkillFilter] = useState('all');
  const [sheetImage, setSheetImage] = useState(null);

  // ── Skill resolution helpers ────────────────────────
  /** Resolve class_id → skill IDs from skills config */
  const getSkillsForClassId = (classId) => {
    if (!classId || !skills?.class_skills) return [];
    return skills.class_skills[classId] || [];
  };

  /** Get count of skills for a class_id */
  const getSkillCount = (classId) => getSkillsForClassId(classId).length;

  /** Check if any skill for this class_id is passive */
  const hasPassiveSkill = (classId) => {
    const skillIds = getSkillsForClassId(classId);
    return skillIds.some(sid => skills?.skills?.[sid]?.is_passive);
  };

  // Load spritesheet for thumbnails
  useEffect(() => {
    const img = new Image();
    img.onload = () => setSheetImage(img);
    img.src = SHEET_URL;
  }, []);

  // Resolve sprite region for a given sprite_id
  const getSpriteRegion = (spriteId) => {
    if (!spriteId || !spriteAtlas?.sprites) return null;
    for (const [name, data] of Object.entries(spriteAtlas.sprites)) {
      const normalized = name
        .replace(/_1$/, '')
        .replace(/([a-z])([A-Z])/g, '$1_$2')
        .replace(/\s+/g, '_')
        .toLowerCase();
      if (normalized === spriteId) return data;
    }
    return null;
  };

  const enemyList = useMemo(() => {
    return Object.entries(enemies)
      .map(([id, data]) => ({ id, ...data }))
      .filter(e => {
        if (search && !e.name.toLowerCase().includes(search.toLowerCase()) &&
            !e.enemy_id.toLowerCase().includes(search.toLowerCase())) return false;
        if (tagFilter !== 'all' && !(e.tags || []).includes(tagFilter)) return false;
        if (roleFilter !== 'all') {
          if (roleFilter === 'boss' && !e.is_boss) return false;
          if (roleFilter === 'non-boss' && e.is_boss) return false;
        }
        if (skillFilter !== 'all') {
          const count = getSkillCount(e.class_id);
          if (skillFilter === 'has-skills' && count === 0) return false;
          if (skillFilter === 'no-skills' && count > 0) return false;
        }
        return true;
      })
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [enemies, search, tagFilter, roleFilter, skillFilter, skills]);

  const allTags = useMemo(() => {
    const tags = new Set();
    Object.values(enemies).forEach(e => (e.tags || []).forEach(t => tags.add(t)));
    return [...tags].sort();
  }, [enemies]);

  return (
    <div className="enemy-browser">
      <div className="browser-header">
        <h3>Enemies ({Object.keys(enemies).length})</h3>
      </div>

      <div className="browser-filters">
        <input
          type="text"
          placeholder="Search enemies..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="search-input"
        />
        <div className="filter-row">
          <select value={tagFilter} onChange={e => setTagFilter(e.target.value)}>
            <option value="all">All Tags</option>
            {allTags.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <select value={roleFilter} onChange={e => setRoleFilter(e.target.value)}>
            <option value="all">All Roles</option>
            <option value="boss">Boss Only</option>
            <option value="non-boss">Non-Boss</option>
          </select>
          <select value={skillFilter} onChange={e => setSkillFilter(e.target.value)}>
            <option value="all">All Skills</option>
            <option value="has-skills">Has Skills</option>
            <option value="no-skills">No Skills</option>
          </select>
        </div>
      </div>

      <div className="browser-list">
        {enemyList.map(enemy => {
          const spriteRegion = getSpriteRegion(enemy.sprite_id);
          return (
            <div
              key={enemy.id}
              className={`browser-item ${selectedEnemy === enemy.id ? 'selected' : ''}`}
              onClick={() => onSelect(enemy.id)}
            >
              {spriteRegion && sheetImage ? (
                <BrowserSpriteThumb region={spriteRegion} sheetImage={sheetImage} />
              ) : (
                <div
                  className="enemy-color-dot"
                  style={{ background: enemy.color || '#888' }}
                />
              )}
              <div className="enemy-info">
                <div className="enemy-name">{enemy.name}</div>
                <div className="enemy-role">{enemy.role}</div>
              </div>
              <div className="enemy-tags">
                {(enemy.tags || []).map(t => (
                  <span
                    key={t}
                    className="tag-badge"
                    style={{ borderColor: TAG_COLORS[t] || '#666', color: TAG_COLORS[t] || '#666' }}
                  >
                    {t}
                  </span>
                ))}
                {enemy.is_boss && <span className="tag-badge boss-badge">BOSS</span>}
                {(() => {
                  const count = getSkillCount(enemy.class_id);
                  if (count === 0) return null;
                  const passive = hasPassiveSkill(enemy.class_id);
                  return (
                    <>
                      <span className="tag-badge skill-badge" title={`${count} skill${count !== 1 ? 's' : ''} (class: ${enemy.class_id})`}>
                        ⚔ {count}
                      </span>
                      {passive && (
                        <span className="tag-badge passive-badge" title="Has passive skill(s)">
                          P
                        </span>
                      )}
                    </>
                  );
                })()}
              </div>
            </div>
          );
        })}
        {enemyList.length === 0 && (
          <div className="empty-state">
            <p>No enemies match your filters.</p>
          </div>
        )}
      </div>
    </div>
  );
}

/** Tiny sprite thumbnail for the browser sidebar */
function BrowserSpriteThumb({ region, sheetImage }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !sheetImage) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, 24, 24);
    ctx.drawImage(
      sheetImage,
      region.x, region.y, region.w, region.h,
      1, 1, 22, 22
    );
  }, [region, sheetImage]);

  return (
    <canvas
      ref={canvasRef}
      width={24}
      height={24}
      className="browser-sprite-thumb"
    />
  );
}
