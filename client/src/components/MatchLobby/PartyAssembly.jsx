import React, { useState, useEffect, useCallback } from 'react';
import { useGameState, useGameDispatch } from '../../context/GameStateContext';
import { apiFetch } from '../../utils/serverUrl';
import HeroSprite from '../TownHub/HeroSprite';

/**
 * PartyAssembly — Hero roster picker + controlled hero designation.
 *
 * Phase L2: Core hero roster picker + controlled hero designation.
 * Phase L3: Team cap awareness — blocks hero additions when team is full (5 units).
 *
 * Sends `hero_roster_select` WS message with { hero_ids, controlled_hero_id }
 */

const MAX_PARTY = 5;

export default function PartyAssembly({ isReady, sendAction, availableClasses, teamSlots, playerTeam }) {
  const gameState = useGameState();
  const dispatch = useGameDispatch();
  const [roster, setRoster] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const selectedIds = gameState.selectedRosterHeroes || [];
  const controlledId = gameState.controlledHeroId || null;

  // Fetch hero roster on mount
  useEffect(() => {
    if (!gameState.username) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    apiFetch(`/api/town/roster?username=${encodeURIComponent(gameState.username)}`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        if (!cancelled) {
          setRoster(data.heroes || []);
          setLoading(false);
        }
      })
      .catch(err => {
        if (!cancelled) {
          console.error('[PartyAssembly] Failed to fetch roster:', err);
          setError('Failed to load hero roster');
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [gameState.username]);

  const aliveHeroes = roster.filter(h => h.is_alive);

  const getClassName = (classId) => {
    const cls = availableClasses?.[classId];
    return cls?.name || classId || 'Unknown';
  };

  // Phase L3: Compute team slot availability
  const myTeam = playerTeam || 'a';
  const myTeamSlots = teamSlots?.[myTeam];
  // Team remaining counts all slots; our controlled hero already occupies one,
  // so available ally slots = remaining - (already selected allies not yet server-confirmed)
  const teamRemaining = myTeamSlots?.remaining ?? MAX_PARTY;
  // The player's own human slot is already counted in "used", so max allies = teamRemaining
  // But the per-player cap (MAX_PARTY) also applies
  const allyCount = selectedIds.length > 0 ? selectedIds.length - 1 : 0; // controlled hero is not an extra slot
  const teamFull = teamRemaining <= 0 && selectedIds.length > 0;
  const effectiveMax = Math.min(MAX_PARTY, allyCount + teamRemaining + 1); // +1 for controlled hero

  // Add hero to party
  const handleAddHero = useCallback((heroId) => {
    if (isReady) return;
    if (selectedIds.includes(heroId)) return;
    if (selectedIds.length >= MAX_PARTY) return;
    // Phase L3: Block if team is full (only allies consume team slots, not the controlled hero)
    if (selectedIds.length > 0 && teamRemaining <= 0) return;

    const newSelected = [...selectedIds, heroId];
    const newControlled = controlledId || heroId; // Auto-designate first hero as controlled

    dispatch({ type: 'SET_SELECTED_ROSTER_HEROES', payload: newSelected });
    if (!controlledId) {
      dispatch({ type: 'SET_CONTROLLED_HERO', payload: heroId });
    }

    // Send to server
    sendAction({
      type: 'hero_roster_select',
      hero_ids: newSelected,
      controlled_hero_id: newControlled,
    });
  }, [isReady, selectedIds, controlledId, teamRemaining, dispatch, sendAction]);

  // Remove hero from party
  const handleRemoveHero = useCallback((heroId) => {
    if (isReady) return;
    const newSelected = selectedIds.filter(id => id !== heroId);

    // If removing the controlled hero, designate the first remaining (or null)
    let newControlled = controlledId;
    if (heroId === controlledId) {
      newControlled = newSelected.length > 0 ? newSelected[0] : null;
    }

    dispatch({ type: 'SET_SELECTED_ROSTER_HEROES', payload: newSelected });
    dispatch({ type: 'SET_CONTROLLED_HERO', payload: newControlled });

    if (newSelected.length > 0 && newControlled) {
      sendAction({
        type: 'hero_roster_select',
        hero_ids: newSelected,
        controlled_hero_id: newControlled,
      });
    }
  }, [isReady, selectedIds, controlledId, dispatch, sendAction]);

  // Designate controlled hero
  const handleSetControlled = useCallback((heroId) => {
    if (isReady) return;
    if (!selectedIds.includes(heroId)) return;

    dispatch({ type: 'SET_CONTROLLED_HERO', payload: heroId });

    sendAction({
      type: 'hero_roster_select',
      hero_ids: selectedIds,
      controlled_hero_id: heroId,
    });
  }, [isReady, selectedIds, dispatch, sendAction]);

  // Find hero data by ID
  const getHero = (id) => roster.find(h => h.hero_id === id);

  return (
    <div className="party-assembly">
      <h3 className="grim-header grim-header--left grim-header--sm">Party Assembly</h3>

      {loading && (
        <div className="party-assembly-loading">Loading roster...</div>
      )}

      {error && (
        <div className="party-assembly-error">{error}</div>
      )}

      {!loading && !error && (
        <div className="party-assembly-content">
          {/* Left: Hero Roster */}
          <div className="party-assembly-roster">
            <h4 className="party-assembly-section-title">Your Hero Roster</h4>
            {aliveHeroes.length === 0 ? (
              <p className="party-assembly-empty">No heroes available. Visit the Hiring Hall in Town.</p>
            ) : (
              <div className="party-assembly-roster-grid">
                {aliveHeroes.map(hero => {
                  const isSelected = selectedIds.includes(hero.hero_id);
                  const isPersonalFull = selectedIds.length >= MAX_PARTY;
                  // Phase L3: Also check team cap — if we already have a controlled hero,
                  // adding more means adding allies which need team slots
                  const isTeamBlocked = selectedIds.length > 0 && teamRemaining <= 0;
                  const isFull = isPersonalFull || isTeamBlocked;
                  return (
                    <div
                      key={hero.hero_id}
                      className={`party-roster-card ${isSelected ? 'party-roster-card--selected' : ''} ${!isSelected && isFull ? 'party-roster-card--disabled' : ''}`}
                    >
                      <div className="party-roster-card-sprite">
                        <HeroSprite classId={hero.class_id} variant={hero.sprite_variant || 1} size={36} />
                      </div>
                      <div className="party-roster-card-info">
                        <span className="party-roster-card-name">{hero.name}</span>
                        <span className="party-roster-card-class">{getClassName(hero.class_id)}</span>
                        <span className="party-roster-card-stats">
                          HP {hero.stats?.hp || '?'} · ATK {hero.stats?.attack_damage || '?'}
                        </span>
                      </div>
                      <div className="party-roster-card-actions">
                        {isSelected ? (
                          <button
                            className="grim-btn grim-btn--xs grim-btn--crimson"
                            onClick={() => handleRemoveHero(hero.hero_id)}
                            disabled={isReady}
                            title="Remove from party"
                          >
                            ✕
                          </button>
                        ) : (
                          <button
                            className="grim-btn grim-btn--xs grim-btn--ember"
                            onClick={() => handleAddHero(hero.hero_id)}
                            disabled={isReady || isFull}
                            title={isTeamBlocked ? 'Team full (5 units max)' : isPersonalFull ? 'Party full (max 5)' : 'Add to party'}
                          >
                            +
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Right: Selected Party */}
          <div className="party-assembly-lineup">
            <h4 className="party-assembly-section-title">
              Selected Party
              <span className="party-assembly-count">{selectedIds.length}/{MAX_PARTY}</span>
            </h4>
            {teamFull && (
              <div className="party-assembly-team-full">
                Team full — {myTeamSlots?.used ?? '?'}/{myTeamSlots?.max ?? 5} slots occupied
              </div>
            )}
            {selectedIds.length === 0 ? (
              <p className="party-assembly-empty">Select heroes from your roster to form your party.</p>
            ) : (
              <div className="party-assembly-lineup-list">
                {selectedIds.map(heroId => {
                  const hero = getHero(heroId);
                  if (!hero) return null;
                  const isControlled = heroId === controlledId;
                  return (
                    <div
                      key={heroId}
                      className={`party-lineup-card ${isControlled ? 'party-lineup-card--controlled' : ''}`}
                    >
                      <button
                        className={`party-lineup-crown ${isControlled ? 'party-lineup-crown--active' : ''}`}
                        onClick={() => handleSetControlled(heroId)}
                        disabled={isReady || isControlled}
                        title={isControlled ? 'You will play as this hero' : 'Play as this hero'}
                      >
                        {isControlled ? '👑' : '☆'}
                      </button>
                      <div className="party-lineup-card-sprite">
                        <HeroSprite classId={hero.class_id} variant={hero.sprite_variant || 1} size={36} />
                      </div>
                      <div className="party-lineup-card-info">
                        <span className="party-lineup-card-name">{hero.name}</span>
                        <span className="party-lineup-card-class">{getClassName(hero.class_id)}</span>
                        <span className="party-lineup-card-role">
                          {isControlled ? 'Controlled' : 'AI Ally'}
                        </span>
                      </div>
                      <button
                        className="grim-btn grim-btn--xs grim-btn--crimson party-lineup-remove"
                        onClick={() => handleRemoveHero(heroId)}
                        disabled={isReady}
                        title="Remove from party"
                      >
                        ✕
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
            {isReady && selectedIds.length > 0 && (
              <p className="party-assembly-locked">⚔ Selections locked — unready to change.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
