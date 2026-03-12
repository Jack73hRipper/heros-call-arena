import React from 'react';
import { useGameState } from '../../context/GameStateContext';

const CLASS_COLORS = {
  crusader: '#4a8fd0',
  confessor: '#f0e060',
  inquisitor: '#a050f0',
  ranger: '#40c040',
  hexblade: '#e04040',
  mage: '#e07020',
  bard: '#d4a017',
  blood_knight: '#8B0000',
  plague_doctor: '#50C878',
};

const CLASS_NAMES = {
  crusader: 'Crusader',
  confessor: 'Confessor',
  inquisitor: 'Inquisitor',
  ranger: 'Ranger',
  hexblade: 'Hexblade',
  mage: 'Mage',
  bard: 'Bard',
  blood_knight: 'Blood Knight',
  plague_doctor: 'Plague Doctor',
};

/**
 * Format buff names for display.
 */
function formatBuffName(buffId) {
  const names = {
    war_cry: 'War Cry',
    double_strike: 'Double Strike',
    power_shot: 'Power Shot',
    heal: 'Heal',
    shadow_step: 'Shadow Step',
    wither: 'Wither',
    ward: 'Ward',
    divine_sense: 'Divine Sense',
    rebuke: 'Rebuke',
    shield_of_faith: 'Shield of Faith',
    exorcism: 'Exorcism',
    prayer: 'Prayer',
    detected: 'Detected',
    crimson_veil: 'Crimson Veil',
    blood_frenzy: 'Blood Frenzy',
    miasma: 'Miasma',
    plague_flask: 'Plague Flask',
    enfeeble: 'Enfeeble',
    inoculate: 'Inoculate',
  };
  return names[buffId] || buffId.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/**
 * Format buff effect description.
 */
function formatBuffEffect(buff) {
  if (buff.type === 'dot') return `${buff.damage_per_tick} dmg/turn`;
  if (buff.type === 'hot') return `+${buff.heal_per_tick} hp/turn`;
  if (buff.type === 'shield_charges') return `${buff.charges} charges (${buff.reflect_damage} reflect)`;
  if (buff.type === 'detection') return `Revealed`;
  if (buff.stat === 'melee_damage_multiplier') return `${buff.magnitude}x melee`;
  if (buff.stat === 'ranged_damage_multiplier') return `${buff.magnitude}x ranged`;
  if (buff.stat === 'damage_reduction') return `${Math.round((1 - buff.magnitude) * 100)}% dmg red`;
  if (buff.stat === 'damage_dealt_multiplier') {
    const pct = Math.round((1 - buff.magnitude) * 100);
    return `-${pct}% damage dealt`;
  }
  if (buff.stat === 'armor') return `+${buff.magnitude} armor`;
  return buff.stat ? `${buff.magnitude}x ${buff.stat.replace(/_/g, ' ')}` : 'active';
}

const PVPVE_TEAM_COLORS = {
  a: '#4a8fd0',
  b: '#e04040',
  c: '#40c040',
  d: '#d4a017',
};

/**
 * HeaderBar — Compact single-row top bar showing turn, timer, HP, class, buffs, and mode.
 * Extracted from HUD as part of Phase 6E-2.
 * Phase 27E: Added PVPVE team indicators and teams-remaining counter.
 */
export default function HeaderBar({ turnTimer }) {
  const gameState = useGameState();
  const { players, playerId, currentTurn, tickRate, matchType, isDungeon,
          teamA, teamB, teamC, teamD } = gameState;

  const myPlayer = players[playerId];
  const isAlive = myPlayer?.is_alive !== false;

  // Timer ratio for the visual bar (1.0 = full, 0.0 = empty)
  const timerRatio = tickRate > 0 ? Math.max(0, turnTimer / tickRate) : 0;
  const timerColor = timerRatio > 0.5 ? '#4f4' : timerRatio > 0.25 ? '#ff0' : '#f44';

  // HP bar color
  const hpRatio = myPlayer ? myPlayer.hp / myPlayer.max_hp : 0;
  const hpColor = hpRatio > 0.5 ? '#4f4' : hpRatio > 0.25 ? '#ff0' : '#f44';

  // Mode label
  const isPvpve = matchType === 'pvpve';
  const modeLabel = isPvpve ? 'PVPVE' : isDungeon ? 'Dungeon' : 'Arena';

  // PVPVE: compute teams remaining (teams with at least 1 alive non-pve unit)
  const pvpveTeamsRemaining = (() => {
    if (!isPvpve) return null;
    const teamLists = { a: teamA, b: teamB, c: teamC, d: teamD };
    let alive = 0;
    let total = 0;
    for (const [teamKey, memberIds] of Object.entries(teamLists)) {
      if (!memberIds || memberIds.length === 0) continue;
      total++;
      const hasAlive = memberIds.some(id => {
        const p = players[id];
        return p && p.is_alive !== false && p.team !== 'pve';
      });
      if (hasAlive) alive++;
    }
    return { alive, total };
  })();

  // PVPVE: my team
  const myTeamKey = myPlayer?.team;

  return (
    <div className="header-bar">
      {/* Turn + Mode */}
      <div className="header-section header-turn-info">
        <span className="header-turn">Turn: <strong>{currentTurn}</strong></span>
        <span className={`header-mode-badge${isPvpve ? ' header-mode-badge--pvpve' : ''}`}>{modeLabel}</span>
        {matchType && matchType !== 'pvp' && matchType !== 'pvpve' && (
          <span className="header-match-type">{matchType.toUpperCase().replace('_', ' ')}</span>
        )}
        {isPvpve && myTeamKey && (
          <span className="header-team-indicator" style={{ color: PVPVE_TEAM_COLORS[myTeamKey] || '#fff' }}>
            Team {myTeamKey.toUpperCase()}
          </span>
        )}
        {pvpveTeamsRemaining && (
          <span className="header-teams-remaining">
            Teams: {pvpveTeamsRemaining.alive}/{pvpveTeamsRemaining.total}
          </span>
        )}
      </div>

      {/* Turn Timer */}
      <div className="header-section header-timer">
        <span className="header-timer-label">Timer</span>
        <div className="header-timer-bar-bg">
          <div
            className="header-timer-bar-fill"
            style={{ width: `${timerRatio * 100}%`, backgroundColor: timerColor }}
          />
        </div>
        <span className="header-timer-value">{Math.ceil(turnTimer)}s</span>
      </div>

      {/* Player HP */}
      {myPlayer && (
        <div className="header-section header-hp">
          <span className="header-hp-label">HP</span>
          <div className="header-hp-bar-bg">
            <div
              className="header-hp-bar-fill"
              style={{ width: `${hpRatio * 100}%`, backgroundColor: hpColor }}
            />
          </div>
          <span className="header-hp-value">{myPlayer.hp}/{myPlayer.max_hp}</span>
        </div>
      )}

      {/* Class */}
      {myPlayer?.class_id && (
        <div className="header-section header-class">
          <span
            className="header-class-name"
            style={{ color: CLASS_COLORS[myPlayer.class_id] || '#fff' }}
          >
            {CLASS_NAMES[myPlayer.class_id] || myPlayer.class_id}
          </span>
        </div>
      )}

      {/* Active Buffs */}
      {myPlayer?.active_buffs && myPlayer.active_buffs.length > 0 && (
        <div className="header-section header-buffs">
          {myPlayer.active_buffs.map((buff, i) => {
            const icon = buff.type === 'dot' ? '🩸' : buff.type === 'hot' ? '💚' : buff.type === 'shield_charges' ? '🛡️' : buff.type === 'detection' ? '👁️' : buff.stat === 'armor' ? '✨' : '🔷';
            const pillClass = `header-buff-pill${buff.type === 'dot' ? ' buff-dot' : buff.type === 'hot' ? ' buff-hot' : buff.type === 'shield_charges' ? ' buff-shield' : buff.type === 'detection' ? ' buff-detection' : buff.stat === 'armor' ? ' buff-armor' : ''}`;
            const durationText = buff.type === 'shield_charges' ? `${buff.charges}ch` : `${buff.turns_remaining}t`;
            return (
              <span key={`${buff.buff_id}-${i}`} className={pillClass} title={`${formatBuffName(buff.buff_id)}: ${formatBuffEffect(buff)}`}>
                {icon} {formatBuffName(buff.buff_id)} ({durationText})
              </span>
            );
          })}
        </div>
      )}

      {/* Status */}
      {!isAlive && (
        <div className="header-section header-status-dead">
          💀 Eliminated
        </div>
      )}
    </div>
  );
}
