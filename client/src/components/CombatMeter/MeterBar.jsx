import React from 'react';

/**
 * MeterBar — A single horizontal bar representing one unit's stat value.
 * Shows a colored fill proportional to the max value in the dataset,
 * with the unit name on the left and the value on the right.
 */

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

const TEAM_COLORS = {
  a: '#4a8fd0',
  b: '#e04040',
  c: '#40c040',
  d: '#f0e060',
};

export default function MeterBar({ username, classId, team, value, maxValue, perTurn, isPlayer, rank, onClick }) {
  const pct = maxValue > 0 ? Math.min(100, (value / maxValue) * 100) : 0;
  const barColor = CLASS_COLORS[classId] || TEAM_COLORS[team] || '#888';
  // Slightly dim for non-player entries
  const opacity = isPlayer ? 1 : 0.85;

  return (
    <div
      className={`meter-bar-row meter-bar-clickable ${isPlayer ? 'meter-bar-self' : ''}`}
      style={{ opacity }}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter') onClick(); } : undefined}
    >
      <span className="meter-bar-rank">{rank}</span>
      <span className="meter-bar-name" title={username}>{username}</span>
      <div className="meter-bar-track">
        <div
          className="meter-bar-fill"
          style={{
            width: `${pct}%`,
            backgroundColor: barColor,
          }}
        />
        <span className="meter-bar-value">{value.toLocaleString()}</span>
      </div>
      {perTurn !== undefined && (
        <span className="meter-bar-dps" title="Per turn">{perTurn.toFixed(1)}/t</span>
      )}
    </div>
  );
}
