import React, { useState } from 'react';
import { useGameState, useGameDispatch } from '../../context/GameStateContext';
import { apiFetch } from '../../utils/serverUrl';
import HeroSprite from './HeroSprite';

/**
 * HiringHall — displays tavern heroes available for hire.
 * Fetches from GET /api/town/tavern, hires via POST /api/town/hire.
 *
 * Phase 4E-4: Overhauled cards with class identity (role, description, skill
 * preview) and random starting gear display. Stat variation removed.
 */

/** Rarity color map for item display */
const RARITY_COLORS = {
  common: '#9d9d9d',
  magic: '#4a8fd0',
  rare: '#f0e060',
  epic: '#a050f0',
  unique: '#e07020',
  set: '#40c040',
};

/** Role icon map */
const ROLE_ICONS = {
  'Tank': '🛡️',
  'Support': '✚',
  'Scout': '👁',
  'Ranged DPS': '🏹',
  'Hybrid DPS': '⚔',
  'Caster DPS': '🔥',
  'Offensive Support': '🎵',
  'Sustain Melee DPS': '🩸',
  'Controller': '☠',
  'Retaliation Tank': '⛓',
  'Totemic Healer': '🪵',
};

export default function HiringHall({ availableClasses }) {
  const gameState = useGameState();
  const dispatch = useGameDispatch();
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [hoveredSkill, setHoveredSkill] = useState(null);

  const tavernHeroes = gameState.tavernHeroes || [];
  const gold = gameState.gold;

  const handleHire = async (heroId) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/town/hire', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: gameState.username, hero_id: heroId }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to hire hero');
      }
      const data = await res.json();
      dispatch({ type: 'HIRE_HERO', payload: { hero: data.hero, gold: data.gold } });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshTavern = async () => {
    setRefreshing(true);
    setError(null);
    try {
      const res = await apiFetch('/api/town/tavern/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: gameState.username }),
      });
      if (!res.ok) throw new Error('Failed to refresh tavern');
      const data = await res.json();
      dispatch({ type: 'SET_TAVERN', payload: { heroes: data.heroes, gold: data.gold } });
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  const getClassDef = (classId) => availableClasses?.[classId] || {};

  /** Count how many gear slots are filled */
  const getGearCount = (equipment) => {
    if (!equipment) return 0;
    return ['weapon', 'armor', 'accessory'].filter(s => equipment[s]).length;
  };

  return (
    <div className="hiring-hall">
      <div className="hiring-hall-header">
        <h3>Hiring Hall</h3>
        <button
          className="btn-refresh-tavern"
          onClick={handleRefreshTavern}
          disabled={refreshing}
        >
          {refreshing ? 'Refreshing...' : 'New Heroes'}
        </button>
      </div>

      {error && <p className="town-error">{error}</p>}

      {tavernHeroes.length === 0 ? (
        <p className="town-placeholder">The tavern is empty... refreshing soon.</p>
      ) : (
        <div className="tavern-hero-grid">
          {tavernHeroes.map((hero) => {
            const classDef = getClassDef(hero.class_id);
            const canAfford = gold >= hero.hire_cost;
            const gearCount = getGearCount(hero.equipment);
            const skills = classDef.skills || [];
            return (
              <div key={hero.hero_id} className="tavern-hero-card">
                {/* --- Header: Sprite + Name + Role --- */}
                <div className="hero-card-header">
                  <HeroSprite
                    classId={hero.class_id}
                    variant={hero.sprite_variant || 1}
                    size={64}
                    className="hero-card-sprite"
                  />
                  <div className="hero-card-name-block">
                    <strong className="hero-name">{hero.name}</strong>
                    <span className="hero-class-label" style={{ color: classDef.color || '#aaa' }}>
                      {classDef.name || hero.class_id}
                    </span>
                    {classDef.role && (
                      <span className="hero-role-tag" style={{ borderColor: classDef.color || '#555' }}>
                        <span className="hero-role-icon">{ROLE_ICONS[classDef.role] || '⚔'}</span>
                        {classDef.role}
                      </span>
                    )}
                  </div>
                </div>

                {/* --- Class Description --- */}
                {classDef.description && (
                  <p className="hero-card-description">{classDef.description}</p>
                )}

                {/* --- Skills Preview --- */}
                {skills.length > 0 && (
                  <div className="hero-card-skills">
                    <span className="hero-skills-label">Skills</span>
                    <div className="hero-skill-badges">
                      {skills.map((skill) => (
                        <div
                          key={skill.skill_id}
                          className="hero-skill-badge"
                          onMouseEnter={() => setHoveredSkill(`${hero.hero_id}-${skill.skill_id}`)}
                          onMouseLeave={() => setHoveredSkill(null)}
                        >
                          <span className="skill-badge-icon">{skill.icon || '◆'}</span>
                          {hoveredSkill === `${hero.hero_id}-${skill.skill_id}` && (
                            <div className="skill-tooltip">
                              <div className="skill-tooltip-name">{skill.name}</div>
                              <div className="skill-tooltip-desc">{skill.description}</div>
                              {skill.cooldown_turns > 0 && (
                                <div className="skill-tooltip-cd">{skill.cooldown_turns} turn cooldown</div>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* --- Stats Block --- */}
                <div className="hero-card-stats">
                  <StatRow label="HP" value={hero.stats.max_hp} />
                  <StatRow label="Melee" value={hero.stats.attack_damage} />
                  <StatRow label="Ranged" value={hero.stats.ranged_damage} />
                  <StatRow label="Armor" value={hero.stats.armor} />
                  <StatRow label="Vision" value={hero.stats.vision_range} />
                  <StatRow label="Range" value={hero.stats.ranged_range} />
                </div>

                {/* --- Starting Gear --- */}
                {gearCount > 0 && (
                  <div className="hero-card-gear">
                    <span className="hero-gear-label">Comes With</span>
                    <div className="hero-gear-slots">
                      {['weapon', 'armor', 'accessory'].map((slot) => {
                        const item = hero.equipment?.[slot];
                        if (!item) return null;
                        const rarityColor = RARITY_COLORS[item.rarity] || RARITY_COLORS.common;
                        return (
                          <div key={slot} className="hero-gear-item" style={{ borderColor: rarityColor }}>
                            <span className="gear-item-name" style={{ color: rarityColor }}>
                              {item.display_name || item.name}
                            </span>
                            <span className="gear-item-slot">{slot}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* --- Footer: Cost + Hire --- */}
                <div className="hero-card-footer">
                  <div className="hero-hire-cost-block">
                    <span className="hero-hire-cost">{hero.hire_cost}g</span>
                    {gearCount > 0 && (
                      <span className="hero-cost-breakdown">{BASE_HIRE_COST}g base + gear</span>
                    )}
                  </div>
                  <button
                    className={`btn-hire ${!canAfford ? 'btn-hire-disabled' : ''}`}
                    onClick={() => handleHire(hero.hero_id)}
                    disabled={loading || !canAfford}
                    title={!canAfford ? `Need ${hero.hire_cost}g (have ${gold}g)` : `Hire for ${hero.hire_cost}g`}
                  >
                    {loading ? '...' : 'Hire'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

const BASE_HIRE_COST = 30;

/** Stat row — flat display, no diff (stats are now always class base) */
function StatRow({ label, value }) {
  return (
    <div className="hero-stat-row">
      <span className="hero-stat-label">{label}</span>
      <span className="hero-stat-value">{value}</span>
    </div>
  );
}
