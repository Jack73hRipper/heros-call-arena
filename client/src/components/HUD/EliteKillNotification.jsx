import React, { useState, useEffect, useCallback } from 'react';

/**
 * Phase 18F: EliteKillNotification — center-screen notification when a
 * Rare or Super Unique enemy is slain.
 *
 * Shows a brief dramatic notification with the enemy's display name,
 * colored by rarity (gold for rare, purple for super unique).
 *
 * Props:
 *   notifications - Array of { id, displayName, monsterRarity, timestamp }
 *   onDismiss     - Callback to remove a notification by id
 */

const RARITY_STYLES = {
  rare: {
    color: '#ffcc00',
    label: '⚔ Elite Slain ⚔',
    glowColor: 'rgba(255, 204, 0, 0.4)',
    duration: 3500,
  },
  super_unique: {
    color: '#cc66ff',
    label: '💀 Boss Vanquished 💀',
    glowColor: 'rgba(204, 102, 255, 0.4)',
    duration: 5000,
  },
};

export default function EliteKillNotification({ notifications, onDismiss }) {
  if (!notifications || notifications.length === 0) return null;

  return (
    <div className="elite-kill-container">
      {notifications.map(notif => (
        <EliteKillItem
          key={notif.id}
          notif={notif}
          onDismiss={onDismiss}
        />
      ))}
    </div>
  );
}

function EliteKillItem({ notif, onDismiss }) {
  const [fading, setFading] = useState(false);
  const rarity = notif.monsterRarity || 'rare';
  const style = RARITY_STYLES[rarity] || RARITY_STYLES.rare;

  useEffect(() => {
    const fadeTimer = setTimeout(() => setFading(true), style.duration - 800);
    const removeTimer = setTimeout(() => onDismiss?.(notif.id), style.duration);
    return () => {
      clearTimeout(fadeTimer);
      clearTimeout(removeTimer);
    };
  }, [notif.id, style.duration, onDismiss]);

  const handleClick = useCallback(() => {
    onDismiss?.(notif.id);
  }, [notif.id, onDismiss]);

  return (
    <div
      className={`elite-kill-notification ${fading ? 'elite-kill-fading' : 'elite-kill-enter'} elite-kill-${rarity}`}
      style={{
        '--elite-color': style.color,
        '--elite-glow': style.glowColor,
      }}
      onClick={handleClick}
    >
      <div className="elite-kill-label">{style.label}</div>
      <div className="elite-kill-name" style={{ color: style.color }}>
        {notif.displayName}
      </div>
      <div className="elite-kill-subtitle">has been vanquished!</div>
    </div>
  );
}
