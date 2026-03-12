import React, { useState, useEffect, useCallback } from 'react';
import { getRarityColor, getRarityDisplayName, RARITY_NOTIFICATION_CONFIG } from '../../utils/itemUtils';

/**
 * Phase 16G: LootNotification — shows a brief notification when a Rare+ item drops.
 *
 * Notifications auto-fade after a configured duration based on rarity.
 * Epic/Unique/Set notifications are larger and persist longer.
 *
 * Props:
 *   notifications - Array of { id, item, rarity, timestamp }
 *   onDismiss     - Callback to remove a notification by id
 */
export default function LootNotification({ notifications, onDismiss }) {
  if (!notifications || notifications.length === 0) return null;

  return (
    <div className="loot-notification-container">
      {notifications.map(notif => (
        <LootNotificationItem
          key={notif.id}
          notif={notif}
          onDismiss={onDismiss}
        />
      ))}
    </div>
  );
}

/**
 * Individual notification item with auto-fade timer.
 */
function LootNotificationItem({ notif, onDismiss }) {
  const [fading, setFading] = useState(false);
  const rarity = notif.rarity || 'rare';
  const config = RARITY_NOTIFICATION_CONFIG[rarity] || RARITY_NOTIFICATION_CONFIG.rare;
  const rarityColor = getRarityColor(rarity);
  const rarityLabel = getRarityDisplayName(rarity);
  const isHighTier = rarity === 'epic' || rarity === 'unique' || rarity === 'set';

  useEffect(() => {
    // Start fade-out slightly before removal
    const fadeTimer = setTimeout(() => setFading(true), config.duration - 500);
    const removeTimer = setTimeout(() => onDismiss?.(notif.id), config.duration);
    return () => {
      clearTimeout(fadeTimer);
      clearTimeout(removeTimer);
    };
  }, [notif.id, config.duration, onDismiss]);

  const handleClick = useCallback(() => {
    onDismiss?.(notif.id);
  }, [notif.id, onDismiss]);

  return (
    <div
      className={`loot-notification ${fading ? 'loot-notification-fading' : ''} ${isHighTier ? 'loot-notification-high' : ''} rarity-${rarity}`}
      style={{ '--rarity-color': rarityColor }}
      onClick={handleClick}
    >
      <div className="loot-notification-header">
        <span className="loot-notification-icon">{config.icon}</span>
        <span className="loot-notification-label">{config.label}</span>
        <span className="loot-notification-icon">{config.icon}</span>
      </div>
      <div className="loot-notification-name" style={{ color: rarityColor }}>
        {notif.item?.name || 'Unknown Item'}
      </div>
      {notif.item?.display_name && (
        <div className="loot-notification-type">
          {rarityLabel} {notif.item.display_name}
          {notif.floorLabel ? ` · ${notif.floorLabel}` : ''}
        </div>
      )}
    </div>
  );
}
