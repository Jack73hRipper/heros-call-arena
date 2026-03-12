import React, { useMemo } from 'react';
import MeterBar from './MeterBar';

/**
 * DamageTakenView — Sorted descending by total damage taken.
 * Shows who is absorbing the most punishment (tank metric).
 */
export default function DamageTakenView({ unitStats, playerId, currentTurn, onSelectUnit }) {
  const sorted = useMemo(() => {
    return Object.values(unitStats)
      .filter(u => u.damage_taken > 0)
      .sort((a, b) => b.damage_taken - a.damage_taken);
  }, [unitStats]);

  const maxValue = sorted.length > 0 ? sorted[0].damage_taken : 0;

  if (sorted.length === 0) {
    return <div className="meter-empty">No damage taken yet</div>;
  }

  return (
    <div className="meter-view">
      {sorted.map((unit, i) => (
        <MeterBar
          key={unit.unitId}
          rank={i + 1}
          username={unit.username}
          classId={unit.classId}
          team={unit.team}
          value={unit.damage_taken}
          maxValue={maxValue}
          perTurn={currentTurn > 0 ? unit.damage_taken / currentTurn : 0}
          isPlayer={unit.unitId === playerId}
          onClick={() => onSelectUnit && onSelectUnit(unit.unitId)}
        />
      ))}
    </div>
  );
}
