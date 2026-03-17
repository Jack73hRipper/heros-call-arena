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
 * PlayerVitals — Prominent HP frame overlay anchored to the bottom-left of the canvas.
 * Replaces the small inline HP bar from HeaderBar with a larger, more visible display.
 */
export default function PlayerVitals() {
  const { players, playerId } = useGameState();
  const myPlayer = players[playerId];

  if (!myPlayer) return null;

  const hpRatio = myPlayer.max_hp > 0 ? myPlayer.hp / myPlayer.max_hp : 0;
  const hpPercent = Math.max(0, Math.min(100, hpRatio * 100));
  const isLowHp = hpRatio <= 0.25;
  const isMidHp = hpRatio > 0.25 && hpRatio <= 0.5;
  const isDead = myPlayer.is_alive === false;
  const classId = myPlayer.class_id;
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
    'player-vitals',
    isLowHp && !isDead ? 'pv-danger' : '',
    isDead ? 'pv-dead' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={frameClass} style={{ '--class-color': classColor }}>
      {/* Class identity row */}
      <div className="pv-class-row">
        <span className="pv-class-icon">{classIcon}</span>
        <span className="pv-class-name" style={{ color: classColor }}>{className}</span>
        <span className="pv-player-name">{myPlayer.username}</span>
      </div>

      {/* HP bar */}
      <div className="pv-hp-bar-bg">
        <div
          className={barClass}
          style={{ width: `${hpPercent}%` }}
        />
        <span className="pv-hp-text">
          {isDead ? '💀 DEAD' : `${myPlayer.hp} / ${myPlayer.max_hp}`}
        </span>
      </div>
    </div>
  );
}
