import React, { useMemo } from 'react';
import { useGameState } from '../../context/GameStateContext';
import HeroSprite from '../TownHub/HeroSprite';

/**
 * PostMatchScreen — immersive post-match summary with hero roster, stats, and thematic messaging.
 *
 * Phase 13-1D: Extracted from App.jsx into standalone component.
 * Phase 15 Chunk 6: Enhanced with dramatic banners, ornate hero cards,
 *   combat ledger stats, treasure-chest loot panel, grim-frame system,
 *   decorative separators, and .grim-btn action buttons.
 * Battle Scoreboard: Added full team-vs-team scoreboard showing all units
 *   (human + AI) with team headers, MVP highlight, and team comparison bars.
 */
export default function PostMatchScreen({ onBackToTown, onLeave }) {
  const gameState = useGameState();
  const summary = gameState.postMatchSummary;
  const heroDeaths = gameState.heroDeaths || [];
  const heroOutcomes = summary?.heroOutcomes || {};
  const playerId = gameState.playerId;
  const battleScoreboard = summary?.battleScoreboard || null;
  const teamTotals = summary?.teamTotals || null;

  const isDungeon = summary?.isDungeon || false;
  const bossKilled = summary?.bossKilled || false;
  const winner = summary?.winner;

  // Determine outcome type for thematic header
  const outcomeType = useMemo(() => {
    if (isDungeon) {
      if (winner === 'dungeon_extract' && bossKilled) return 'dungeon_cleared';
      if (winner === 'dungeon_extract' && !bossKilled) return 'dungeon_escaped';
      if (winner === 'party_wipe') return 'party_wipe';
      // Fallback: team_a won (legacy) with boss killed
      if (bossKilled) return 'dungeon_cleared';
      return 'dungeon_escaped';
    }
    // PVPVE modes
    if (summary?.matchType === 'pvpve') {
      if (winner === 'draw') return 'arena_draw';
      // Check if my team won
      const myTeam = summary?.myTeam;
      if (myTeam && winner === `team_${myTeam}`) return 'pvpve_victory';
      return 'pvpve_defeat';
    }
    // Arena modes
    const myOutcome = heroOutcomes[playerId];
    if (myOutcome && myOutcome.status === 'survived') return 'arena_victory';
    if (winner === 'draw') return 'arena_draw';
    return 'arena_defeat';
  }, [isDungeon, winner, bossKilled, heroOutcomes, playerId, summary]);

  // Thematic headers based on outcome
  const headerMessages = {
    dungeon_cleared: 'The terrors of this realm have been vanquished',
    dungeon_escaped: 'You flee, but the darkness endures',
    party_wipe: 'Darkness consumes all...',
    arena_victory: 'Champion of the Arena',
    arena_defeat: 'The Arena shows no mercy',
    arena_draw: 'No victor emerges from the carnage',
    pvpve_victory: 'Last Team Standing',
    pvpve_defeat: 'Your team has fallen',
  };

  const headerSubtext = {
    dungeon_cleared: 'Your party has conquered the dungeon and returned triumphant.',
    dungeon_escaped: 'The dungeon\'s horrors remain for the next who dare enter.',
    party_wipe: 'None escaped the abyss. Your fallen heroes are lost forever.',
    arena_victory: 'Only the strong remain standing.',
    arena_defeat: 'Bested in combat — but not broken.',
    arena_draw: 'The dust settles on a battlefield with no champion.',
    pvpve_victory: 'You conquered the dungeon and crushed your rivals.',
    pvpve_defeat: 'The dungeon claims another team to its depths.',
  };

  // Build hero roster from outcomes (filter only party members — human + hero allies)
  const heroRoster = useMemo(() => {
    return Object.values(heroOutcomes)
      .filter(o => o.hero_id || o.player_id === playerId)
      .sort((a, b) => {
        // Player first, then alive, then by kills
        if (a.player_id === playerId) return -1;
        if (b.player_id === playerId) return 1;
        if (a.status === 'survived' && b.status !== 'survived') return -1;
        if (b.status === 'survived' && a.status !== 'survived') return 1;
        return (b.enemy_kills || 0) - (a.enemy_kills || 0);
      });
  }, [heroOutcomes, playerId]);

  // Compute match totals
  const totals = useMemo(() => {
    const vals = Object.values(heroOutcomes);
    return {
      totalKills: vals.reduce((s, o) => s + (o.enemy_kills || 0), 0),
      totalBossKills: vals.reduce((s, o) => s + (o.boss_kills || 0), 0),
      totalGold: vals.reduce((s, o) => s + (o.gold_earned || 0), 0),
      totalDamage: vals.reduce((s, o) => s + (o.damage_dealt || 0), 0),
      totalHealing: vals.reduce((s, o) => s + (o.healing_done || 0), 0),
    };
  }, [heroOutcomes]);

  // Whether there are any loot-worthy totals to display
  const hasLootSummary = totals.totalKills > 0 || totals.totalGold > 0 || totals.totalDamage > 0;

  // Class display names
  const classNames = {
    crusader: 'Crusader',
    confessor: 'Confessor',
    inquisitor: 'Inquisitor',
    ranger: 'Ranger',
    hexblade: 'Hexblade',
    mage: 'Mage',
  };

  // Team display names + colors
  const teamLabels = { a: 'Team A', b: 'Team B', c: 'Team C', d: 'Team D', pve: 'PVE' };

  // Build team-grouped scoreboard from battleScoreboard data
  const teamGroups = useMemo(() => {
    if (!battleScoreboard || battleScoreboard.length === 0) return null;

    // Group units by team (exclude PVE team from scoreboard display)
    const groups = {};
    for (const unit of battleScoreboard) {
      const team = unit.team || 'b';
      if (team === 'pve') continue; // Phase 27E: PVE enemies not shown in team scoreboard
      if (!groups[team]) groups[team] = [];
      groups[team].push(unit);
    }

    // Sort each team: survived first, then by damage dealt descending
    for (const team of Object.keys(groups)) {
      groups[team].sort((a, b) => {
        if (a.status === 'survived' && b.status !== 'survived') return -1;
        if (b.status === 'survived' && a.status !== 'survived') return 1;
        return (b.damage_dealt || 0) - (a.damage_dealt || 0);
      });
    }

    return groups;
  }, [battleScoreboard]);

  // Determine match MVP (highest damage across all units)
  const matchMvp = useMemo(() => {
    if (!battleScoreboard || battleScoreboard.length === 0) return null;
    return battleScoreboard.reduce(
      (best, u) => ((u.damage_dealt || 0) > (best.damage_dealt || 0) ? u : best),
      battleScoreboard[0]
    );
  }, [battleScoreboard]);

  // Are we in a PvP-style match with multiple teams? (show scoreboard)
  const isPvpve = summary?.matchType === 'pvpve';
  const showBattleScoreboard = teamGroups && Object.keys(teamGroups).length >= 2 && (!isDungeon || isPvpve);

  return (
    <div className="post-match-screen">
      {/* Thematic Header — dramatic victory/defeat banner */}
      <div className={`post-match-header outcome-${outcomeType}`}>
        <div className="post-match-banner-line" />
        <h2 className="post-match-title">{headerMessages[outcomeType]}</h2>
        <p className="post-match-subtext">{headerSubtext[outcomeType]}</p>
        <div className="post-match-meta">
          <span className="meta-turns">Turn {summary?.finalTurn || '?'}</span>
          {totals.totalKills > 0 && (
            <span className="meta-stat">{totals.totalKills} enemies slain</span>
          )}
          {totals.totalGold > 0 && (
            <span className="meta-stat">{totals.totalGold}g earned</span>
          )}
          {isPvpve && summary?.pveKills > 0 && (
            <span className="meta-stat">{summary.pveKills} PVE kills</span>
          )}
          {isPvpve && summary?.bossKilled && (
            <span className="meta-stat">💀 Boss slain</span>
          )}
        </div>
      </div>

      {/* Decorative separator */}
      <div className="grim-separator grim-separator--ember">◆</div>

      {/* ── Battle Scoreboard — Full team-vs-team display (PvP only) ── */}
      {showBattleScoreboard && (
        <div className="battle-scoreboard-section">
          <h3 className="grim-header grim-header--sm">Battle Scoreboard</h3>

          {/* Team comparison bars (only for exactly 2 player teams) */}
          {teamTotals && Object.keys(teamTotals).filter(t => t !== 'pve').length === 2 && (() => {
            const teams = Object.keys(teamTotals).filter(t => t !== 'pve').sort();
            const maxDmg = Math.max(...teams.map(t => teamTotals[t].damage_dealt || 0), 1);
            const maxHeal = Math.max(...teams.map(t => teamTotals[t].healing_done || 0), 1);
            const maxKills = Math.max(...teams.map(t => teamTotals[t].kills || 0), 1);
            return (
              <div className="team-comparison-panel">
                {[
                  { label: 'Damage', key: 'damage_dealt', max: maxDmg, colorA: '#c05050', colorB: '#5078b0' },
                  { label: 'Healing', key: 'healing_done', max: maxHeal, colorA: '#8cb860', colorB: '#60a860' },
                  { label: 'Kills', key: 'kills', max: maxKills, colorA: '#daa84a', colorB: '#a0a0c0' },
                ].map(({ label, key, max, colorA, colorB }) => (
                  <div key={key} className="team-compare-row">
                    <span className="team-compare-val team-compare-val--a">{teamTotals[teams[0]]?.[key] || 0}</span>
                    <div className="team-compare-bar-container">
                      <div
                        className="team-compare-bar team-compare-bar--a"
                        style={{
                          width: `${((teamTotals[teams[0]]?.[key] || 0) / max) * 50}%`,
                          background: colorA,
                        }}
                      />
                      <span className="team-compare-label">{label}</span>
                      <div
                        className="team-compare-bar team-compare-bar--b"
                        style={{
                          width: `${((teamTotals[teams[1]]?.[key] || 0) / max) * 50}%`,
                          background: colorB,
                        }}
                      />
                    </div>
                    <span className="team-compare-val team-compare-val--b">{teamTotals[teams[1]]?.[key] || 0}</span>
                  </div>
                ))}
              </div>
            );
          })()}

          {/* Team columns */}
          <div className="battle-scoreboard-teams">
            {Object.keys(teamGroups).sort().map(team => {
              const units = teamGroups[team];
              const isWinningTeam = winner === `team_${team}`;
              const totals_t = teamTotals?.[team];
              return (
                <div key={team} className={`battle-team-column ${isWinningTeam ? 'team-winner' : 'team-loser'}`}>
                  <div className="battle-team-header">
                    <span className={`battle-team-name team-color-${team}`}>
                      {teamLabels[team] || `Team ${team.toUpperCase()}`}
                    </span>
                    {isWinningTeam && <span className="battle-team-badge badge-victory">Victory</span>}
                    {!isWinningTeam && winner !== 'draw' && <span className="battle-team-badge badge-defeat">Defeat</span>}
                    {winner === 'draw' && <span className="battle-team-badge badge-draw">Draw</span>}
                    {totals_t && (
                      <span className="battle-team-score">
                        {totals_t.kills} kills · {totals_t.survived} alive
                      </span>
                    )}
                  </div>
                  <div className="battle-team-units">
                    {units.map(unit => {
                      const isDead = unit.status === 'died';
                      const isMvp = matchMvp && unit.unit_id === matchMvp.unit_id;
                      const isMe = unit.unit_id === playerId;
                      return (
                        <div
                          key={unit.unit_id}
                          className={`battle-unit-card ${isDead ? 'battle-unit-dead' : 'battle-unit-alive'} ${isMvp ? 'battle-unit-mvp' : ''} ${isMe ? 'battle-unit-self' : ''}`}
                        >
                          <div className="battle-unit-header">
                            <HeroSprite
                              classId={unit.class_id}
                              variant={1}
                              size={36}
                              grayscale={isDead}
                            />
                            <div className="battle-unit-identity">
                              <span className="battle-unit-name">
                                {unit.username}
                                {unit.is_ai && <span className="battle-ai-badge">AI</span>}
                                {isMvp && <span className="battle-mvp-badge">MVP</span>}
                              </span>
                              <span className="battle-unit-class">{classNames[unit.class_id] || unit.class_id || 'Unknown'}</span>
                            </div>
                            <span className={`battle-unit-status ${isDead ? 'status-fallen' : 'status-survived'}`}>
                              {isDead ? '☠' : '✦'}
                            </span>
                          </div>
                          <div className="battle-unit-stats">
                            <span className="battle-stat" title="Damage Dealt">⚔ {unit.damage_dealt || 0}</span>
                            {(unit.healing_done || 0) > 0 && (
                              <span className="battle-stat battle-stat--heal" title="Healing Done">✦ {unit.healing_done}</span>
                            )}
                            <span className="battle-stat battle-stat--kills" title="Kills">💀 {unit.kills || 0}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Separator between scoreboard and personal ledger */}
      {showBattleScoreboard && <div className="grim-separator grim-separator--subtle">⬥</div>}

      {/* Hero Roster Cards — ornate outcome cards */}
      <div className="post-match-roster-section">
        <h3 className="grim-header grim-header--sm">Combat Ledger</h3>
        <div className="post-match-roster">
          {heroRoster.map((hero) => {
            const isDead = hero.status === 'died';
            const isMe = hero.player_id === playerId;
            return (
              <div key={hero.player_id} className={`roster-card ${isDead ? 'roster-dead' : 'roster-alive'} ${isMe ? 'roster-self' : ''}`}>
                <div className="roster-card-header">
                  <HeroSprite
                    classId={hero.class_id}
                    variant={hero.sprite_variant || 1}
                    size={48}
                    grayscale={isDead}
                  />
                  <div className="roster-card-identity">
                    <span className="roster-name">{hero.hero_name || hero.username}</span>
                    <span className="roster-class">{classNames[hero.class_id] || hero.class_id || 'Unknown'}</span>
                    <span className={`roster-status ${isDead ? 'status-fallen' : 'status-survived'}`}>
                      {isDead ? '☠ Fallen' : '✦ Survived'}
                    </span>
                  </div>
                </div>
                <div className="roster-card-stats">
                  <div className="stat-row">
                    <span className="stat-label">Kills</span>
                    <span className="stat-value">{hero.enemy_kills || 0}</span>
                  </div>
                  {(hero.boss_kills || 0) > 0 && (
                    <div className="stat-row stat-boss">
                      <span className="stat-label">Boss Kills</span>
                      <span className="stat-value">{hero.boss_kills}</span>
                    </div>
                  )}
                  <div className="stat-row">
                    <span className="stat-label">Damage Dealt</span>
                    <span className="stat-value">{hero.damage_dealt || 0}</span>
                  </div>
                  <div className="stat-row">
                    <span className="stat-label">Damage Taken</span>
                    <span className="stat-value">{hero.damage_taken || 0}</span>
                  </div>
                  {(hero.healing_done || 0) > 0 && (
                    <div className="stat-row stat-heal">
                      <span className="stat-label">Healing Done</span>
                      <span className="stat-value">{hero.healing_done}</span>
                    </div>
                  )}
                  {(hero.items_looted || 0) > 0 && (
                    <div className="stat-row">
                      <span className="stat-label">Items Looted</span>
                      <span className="stat-value">{hero.items_looted}</span>
                    </div>
                  )}
                  {(hero.gold_earned || 0) > 0 && (
                    <div className="stat-row stat-gold">
                      <span className="stat-label">Gold Earned</span>
                      <span className="stat-value">+{hero.gold_earned}g</span>
                    </div>
                  )}
                  <div className="stat-row">
                    <span className="stat-label">Turns Survived</span>
                    <span className="stat-value">{hero.turns_survived || 0}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Loot Summary — treasure chest panel */}
      {hasLootSummary && (
        <div className="post-match-loot-section">
          <div className="grim-separator grim-separator--subtle">⬥</div>
          <h3 className="grim-header grim-header--sm">Spoils of War</h3>
          <div className="post-match-loot-panel">
            <div className="loot-totals">
              {totals.totalGold > 0 && (
                <div className="loot-total-item">
                  <span className="loot-total-icon">🪙</span>
                  <span className="loot-total-label">Gold</span>
                  <span className="loot-total-value loot-total-value--gold">+{totals.totalGold}g</span>
                </div>
              )}
              {totals.totalKills > 0 && (
                <div className="loot-total-item">
                  <span className="loot-total-icon">⚔</span>
                  <span className="loot-total-label">Enemies Slain</span>
                  <span className="loot-total-value loot-total-value--kills">{totals.totalKills}</span>
                </div>
              )}
              {totals.totalBossKills > 0 && (
                <div className="loot-total-item">
                  <span className="loot-total-icon">💀</span>
                  <span className="loot-total-label">Bosses Felled</span>
                  <span className="loot-total-value loot-total-value--kills">{totals.totalBossKills}</span>
                </div>
              )}
              {totals.totalDamage > 0 && (
                <div className="loot-total-item">
                  <span className="loot-total-icon">🗡</span>
                  <span className="loot-total-label">Total Damage</span>
                  <span className="loot-total-value loot-total-value--damage">{totals.totalDamage}</span>
                </div>
              )}
              {totals.totalHealing > 0 && (
                <div className="loot-total-item">
                  <span className="loot-total-icon">✦</span>
                  <span className="loot-total-label">Total Healing</span>
                  <span className="loot-total-value loot-total-value--healing">{totals.totalHealing}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Permadeath notifications */}
      {heroDeaths.length > 0 && (
        <>
          <div className="grim-separator grim-separator--crimson">☠</div>
          <div className="permadeath-section">
            <h3 className="permadeath-header">Fallen Heroes — Lost Forever</h3>
            {heroDeaths.map((death, i) => (
              <div key={i} className="permadeath-card">
                <div className="permadeath-name">
                  <HeroSprite
                    classId={death.class_id}
                    size={32}
                    grayscale={true}
                  />
                  <div className="permadeath-info">
                    <strong>{death.hero_name}</strong>
                    <span className="permadeath-class">{classNames[death.class_id] || death.class_id}</span>
                  </div>
                </div>
                {death.lost_items && death.lost_items.length > 0 && (
                  <div className="permadeath-lost-items">
                    <span className="lost-items-label">Lost items:</span>
                    {death.lost_items.map((item, j) => (
                      <span key={j} className={`lost-item rarity-${item.rarity || 'common'}`}>
                        {item.name}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {/* Decorative separator above actions */}
      <div className="grim-separator grim-separator--subtle">⬥</div>

      {/* Action Buttons — prominent, centered */}
      <div className="post-match-actions">
        <button className="grim-btn grim-btn--lg grim-btn--ember grim-btn-pulse" onClick={onBackToTown}>
          Return to Town
        </button>
        <button className="grim-btn grim-btn--sm grim-btn--steel" onClick={onLeave}>
          Leave
        </button>
      </div>
    </div>
  );
}
