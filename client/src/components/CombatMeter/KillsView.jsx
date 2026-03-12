import React, { useMemo } from 'react';

/**
 * KillsView — Kill leaderboard with boss kills highlighted.
 */
export default function KillsView({ unitStats, playerId, onSelectUnit }) {
  const sorted = useMemo(() => {
    return Object.values(unitStats)
      .filter(u => u.kills > 0)
      .sort((a, b) => b.kills - a.kills || b.boss_kills - a.boss_kills);
  }, [unitStats]);

  if (sorted.length === 0) {
    return <div className="meter-empty">No kills yet</div>;
  }

  return (
    <div className="meter-view">
      <table className="meter-table meter-table-clickable">
        <thead>
          <tr>
            <th>#</th>
            <th>Unit</th>
            <th>Kills</th>
            <th>Boss</th>
            <th>Best Hit</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((unit, i) => (
            <tr
              key={unit.unitId}
              className={`${unit.unitId === playerId ? 'meter-row-self' : ''} meter-row-clickable`}
              onClick={() => onSelectUnit && onSelectUnit(unit.unitId)}
            >
              <td className="meter-rank">{i + 1}</td>
              <td className="meter-name">{unit.username}</td>
              <td className="meter-val">{unit.kills}</td>
              <td className="meter-val meter-boss">{unit.boss_kills || '—'}</td>
              <td className="meter-val">{unit.highest_hit || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
