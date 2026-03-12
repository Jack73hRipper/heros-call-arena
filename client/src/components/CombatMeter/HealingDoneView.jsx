import React, { useMemo } from 'react';
import MeterBar from './MeterBar';

/**
 * HealingDoneView — Sorted descending by total healing done.
 * Shows healer output (skills + potions + HoTs).
 */
export default function HealingDoneView({ unitStats, playerId, currentTurn, onSelectUnit }) {
  const sorted = useMemo(() => {
    return Object.values(unitStats)
      .filter(u => u.healing_done > 0)
      .sort((a, b) => b.healing_done - a.healing_done);
  }, [unitStats]);

  const maxValue = sorted.length > 0 ? sorted[0].healing_done : 0;

  if (sorted.length === 0) {
    return <div className="meter-empty">No healing done yet</div>;
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
          value={unit.healing_done}
          maxValue={maxValue}
          perTurn={currentTurn > 0 ? unit.healing_done / currentTurn : 0}
          isPlayer={unit.unitId === playerId}
          onClick={() => onSelectUnit && onSelectUnit(unit.unitId)}
        />
      ))}
    </div>
  );
}
