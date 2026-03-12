import React, { useMemo } from 'react';

/**
 * OverviewView — Compact table showing all stats for every unit that has participated in combat.
 */
export default function OverviewView({ unitStats, playerId, currentTurn, onSelectUnit }) {
  const sorted = useMemo(() => {
    return Object.values(unitStats)
      .filter(u => u.damage_dealt > 0 || u.healing_done > 0 || u.damage_taken > 0 || u.kills > 0)
      .sort((a, b) => b.damage_dealt - a.damage_dealt);
  }, [unitStats]);

  if (sorted.length === 0) {
    return <div className="meter-empty">No combat data yet</div>;
  }

  return (
    <div className="meter-view meter-overview-scroll">
      <table className="meter-table meter-table-overview meter-table-clickable">
        <thead>
          <tr>
            <th>Unit</th>
            <th title="Total Damage Dealt">Dmg</th>
            <th title="Damage Per Turn">DPT</th>
            <th title="Total Healing Done">Heal</th>
            <th title="Healing Per Turn">HPT</th>
            <th title="Total Damage Taken">Taken</th>
            <th title="Kill Count">Kills</th>
            <th title="Deaths">Deaths</th>
            <th title="Potions Used">Pots</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((unit) => {
            const dpt = currentTurn > 0 ? (unit.damage_dealt / currentTurn).toFixed(1) : '0.0';
            const hpt = currentTurn > 0 ? (unit.healing_done / currentTurn).toFixed(1) : '0.0';
            return (
              <tr
                key={unit.unitId}
                className={`${unit.unitId === playerId ? 'meter-row-self' : ''} meter-row-clickable`}
                onClick={() => onSelectUnit && onSelectUnit(unit.unitId)}
              >
                <td className="meter-name">{unit.username}</td>
                <td className="meter-val meter-dmg">{unit.damage_dealt.toLocaleString()}</td>
                <td className="meter-val meter-dpt">{dpt}</td>
                <td className="meter-val meter-heal">{unit.healing_done.toLocaleString()}</td>
                <td className="meter-val meter-hpt">{hpt}</td>
                <td className="meter-val meter-taken">{unit.damage_taken.toLocaleString()}</td>
                <td className="meter-val">{unit.kills}</td>
                <td className="meter-val">{unit.deaths}</td>
                <td className="meter-val">{unit.potions_used}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
