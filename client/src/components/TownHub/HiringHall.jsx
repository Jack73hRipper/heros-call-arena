import React, { useState } from 'react';
import { useGameState, useGameDispatch } from '../../context/GameStateContext';
import HeroSprite from './HeroSprite';

/**
 * HiringHall — displays tavern heroes available for hire.
 * Fetches from GET /api/town/tavern, hires via POST /api/town/hire.
 *
 * Phase 4E-3: Consumes stable 4E-1 REST API.
 */
export default function HiringHall({ availableClasses }) {
  const gameState = useGameState();
  const dispatch = useGameDispatch();
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const tavernHeroes = gameState.tavernHeroes || [];
  const gold = gameState.gold;

  const handleHire = async (heroId) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/town/hire', {
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
      const res = await fetch('/api/town/tavern/refresh', {
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

  const getStatDiff = (heroStat, baseStat) => {
    if (baseStat === 0 && heroStat === 0) return null;
    const diff = heroStat - baseStat;
    if (diff === 0) return null;
    return diff > 0
      ? { text: `+${diff}`, className: 'stat-bonus' }
      : { text: `${diff}`, className: 'stat-penalty' };
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
            return (
              <div key={hero.hero_id} className="tavern-hero-card">
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
                  </div>
                </div>

                <div className="hero-card-stats">
                  <StatRow label="HP" value={hero.stats.max_hp} base={classDef.base_hp} diff={getStatDiff(hero.stats.max_hp, classDef.base_hp)} />
                  <StatRow label="Melee" value={hero.stats.attack_damage} base={classDef.base_melee_damage} diff={getStatDiff(hero.stats.attack_damage, classDef.base_melee_damage)} />
                  <StatRow label="Ranged" value={hero.stats.ranged_damage} base={classDef.base_ranged_damage} diff={getStatDiff(hero.stats.ranged_damage, classDef.base_ranged_damage)} />
                  <StatRow label="Armor" value={hero.stats.armor} base={classDef.base_armor} diff={getStatDiff(hero.stats.armor, classDef.base_armor)} />
                  <StatRow label="Vision" value={hero.stats.vision_range} base={classDef.base_vision_range} diff={getStatDiff(hero.stats.vision_range, classDef.base_vision_range)} />
                </div>

                <div className="hero-card-footer">
                  <span className="hero-hire-cost">
                    {hero.hire_cost}g
                  </span>
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

/** Stat row with optional diff indicator */
function StatRow({ label, value, base, diff }) {
  return (
    <div className="hero-stat-row">
      <span className="hero-stat-label">{label}</span>
      <span className="hero-stat-value">{value}</span>
      {diff && (
        <span className={`hero-stat-diff ${diff.className}`}>
          ({diff.text})
        </span>
      )}
    </div>
  );
}
