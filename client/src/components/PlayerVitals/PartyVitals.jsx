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

const CLASS_ICONS = {
  crusader: '🛡️',
  confessor: '✝️',
  inquisitor: '⚖️',
  ranger: '🏹',
  hexblade: '⚔️',
  mage: '🔮',
  bard: '🎵',
  blood_knight: '🩸',
  plague_doctor: '🧪',
};

/**
 * PartyVitals — Displays HP bars for all party members using the same
 * gradient style as PlayerVitals. Rendered side by side in the vitals row.
 */
export default function PartyVitals() {
  const { partyMembers, players, playerId } = useGameState();

  if (!partyMembers || partyMembers.length === 0) return null;

  return (
    <div className="party-vitals">
      {partyMembers.map((member) => {
        const unit = players[member.unit_id];
        if (!unit) return null;
        // Skip the player themselves — they have their own PlayerVitals
        if (member.unit_id === playerId) return null;

        const hpRatio = unit.max_hp > 0 ? unit.hp / unit.max_hp : 0;
        const hpPercent = Math.max(0, Math.min(100, hpRatio * 100));
        const isLowHp = hpRatio <= 0.25;
        const isMidHp = hpRatio > 0.25 && hpRatio <= 0.5;
        const isDead = unit.is_alive === false;
        const classId = member.class_id || unit.class_id;
        const classColor = CLASS_COLORS[classId] || '#888';
        const className = CLASS_NAMES[classId] || classId || 'Unknown';
        const classIcon = CLASS_ICONS[classId] || '⚔️';

        const barClass = [
          'pv-hp-bar-fill',
          isLowHp ? 'pv-hp-low' : '',
          isMidHp ? 'pv-hp-mid' : '',
          isDead ? 'pv-hp-dead' : '',
        ].filter(Boolean).join(' ');

        const frameClass = [
          'party-vital',
          isLowHp && !isDead ? 'pv-danger' : '',
          isDead ? 'pv-dead' : '',
        ].filter(Boolean).join(' ');

        return (
          <div key={member.unit_id} className={frameClass} style={{ '--class-color': classColor }}>
            <div className="pv-class-row">
              <span className="pv-class-icon">{classIcon}</span>
              <span className="pv-class-name" style={{ color: classColor }}>{className}</span>
              <span className="pv-player-name">{unit.username}</span>
            </div>
            <div className="pv-hp-bar-bg">
              <div className={barClass} style={{ width: `${hpPercent}%` }} />
              <span className="pv-hp-text">
                {isDead ? '💀 DEAD' : `${unit.hp} / ${unit.max_hp}`}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
