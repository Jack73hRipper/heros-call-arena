import React, { useMemo } from 'react';
import MeterBar from './MeterBar';

/**
 * DamageDoneView — Sorted descending by total damage dealt.
 * Shows each unit's damage output with DPS (damage per turn).
 */
export default function DamageDoneView({ unitStats, playerId, currentTurn, onSelectUnit }) {
  const sorted = useMemo(() => {
    return Object.values(unitStats)
      .filter(u => u.damage_dealt > 0)
      .sort((a, b) => b.damage_dealt - a.damage_dealt);
  }, [unitStats]);

  const maxValue = sorted.length > 0 ? sorted[0].damage_dealt : 0;

  if (sorted.length === 0) {
    return <div className="meter-empty">No damage dealt yet</div>;
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
          value={unit.damage_dealt}
          maxValue={maxValue}
          perTurn={currentTurn > 0 ? unit.damage_dealt / currentTurn : 0}
          isPlayer={unit.unitId === playerId}
          onClick={() => onSelectUnit && onSelectUnit(unit.unitId)}
        />
      ))}
    </div>
  );
}
