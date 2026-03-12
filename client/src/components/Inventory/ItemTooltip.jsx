import React, { useRef, useLayoutEffect, useState } from 'react';
import {
  getRarityColor, getRarityDisplayName,
  formatStatBonuses, formatItemStatSections,
  compareItems, getItemSetInfo, formatSetBonuses,
} from '../../utils/itemUtils';

/**
 * Item type icon mapping (text-based, no emojis).
 */
const ITEM_ICONS = {
  weapon: 'W',
  armor: 'A',
  accessory: 'R',
  consumable: 'P',
};

/**
 * Phase 16G: Enhanced ItemTooltip — full Diablo-style item tooltip.
 *
 * Displays:
 * - Rarity-colored name with icon
 * - Rarity label + base type + item level
 * - Base stats (gray) separated from affix stats (blue)
 * - Set bonus info (active/inactive)
 * - Item comparison vs equipped (when provided)
 * - Sell value + flavor text
 *
 * Props:
 *   item          - The item to display
 *   equippedItem  - (optional) Currently equipped item in same slot, for comparison
 *   activeSets    - (optional) Player's active set bonuses array
 *   hint          - (optional) Action hint text (e.g. "Click to equip")
 *   rect          - (optional) DOMRect for fixed positioning
 *   showComparison - (optional) Whether to show stat comparison panel
 */
export default function ItemTooltip({ item, equippedItem, activeSets, hint, rect, showComparison = true }) {
  if (!item) return null;

  const rarity = item.rarity || 'common';
  const rarityColor = getRarityColor(rarity);
  const rarityLabel = getRarityDisplayName(rarity);
  const displayName = item.display_name || item.name;
  const baseTypeName = item.display_name ? `${rarityLabel} ${item.display_name}` : `${rarityLabel} ${item.item_type || ''}`;
  const hasAffixes = item.affixes && item.affixes.length > 0;

  // Stat sections — base vs affix
  const { baseLines, affixLines } = hasAffixes
    ? formatItemStatSections(item)
    : { baseLines: formatStatBonuses(item.stat_bonuses), affixLines: [] };

  // Set info
  const setInfo = getItemSetInfo(item);
  const formattedSets = setInfo && activeSets ? formatSetBonuses(activeSets).filter(s => s.setId === setInfo.setId) : [];

  // Item comparison
  const comparison = showComparison && equippedItem ? compareItems(item, equippedItem) : [];

  // Phase 19: Edge-clamped tooltip positioning
  const tooltipRef = useRef(null);
  const [clampedStyle, setClampedStyle] = useState(null);

  // Compute initial position from rect (center-above the slot)
  const baseStyle = {};
  if (rect) {
    baseStyle.position = 'fixed';
    baseStyle.left = rect.left + rect.width / 2;
    baseStyle.top = rect.top - 8;
    baseStyle.transform = 'translate(-50%, -100%)';
    baseStyle.zIndex = 600;
  }

  // After render, measure the tooltip and clamp to viewport edges
  useLayoutEffect(() => {
    if (!rect || !tooltipRef.current) {
      setClampedStyle(null);
      return;
    }
    const el = tooltipRef.current;
    const { width: tw, height: th } = el.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const pad = 8; // min distance from viewport edge

    // Desired center-above position
    let left = rect.left + rect.width / 2 - tw / 2;
    let top = rect.top - 8 - th;

    // If tooltip goes above viewport, flip below the slot
    if (top < pad) {
      top = rect.bottom + 8;
    }
    // Clamp horizontal
    if (left < pad) left = pad;
    if (left + tw > vw - pad) left = vw - pad - tw;
    // Clamp bottom
    if (top + th > vh - pad) top = vh - pad - th;

    setClampedStyle({
      position: 'fixed',
      left,
      top,
      zIndex: 600,
    });
  }, [rect]);

  const tooltipStyle = clampedStyle || baseStyle;

  return (
    <div ref={tooltipRef} className={`item-tooltip rarity-${rarity}`} style={tooltipStyle}>
      {/* Name */}
      <div className={`item-tooltip-name rarity-${rarity}`}>
        {ITEM_ICONS[item.item_type] || '?'} {item.name}
      </div>

      {/* Rarity + base type */}
      <div className="item-tooltip-type">
        {baseTypeName}{item.equip_slot ? ` — ${item.equip_slot}` : ''}
      </div>

      {/* Item Level (for generated items) */}
      {item.item_level > 1 && (
        <div className="item-tooltip-ilvl">Item Level: {item.item_level}</div>
      )}

      {/* Base stats (gray) */}
      {baseLines.length > 0 && (
        <div className="item-tooltip-stats item-tooltip-base-stats">
          {baseLines.map((s, i) => <span key={`b${i}`}>{s}</span>)}
        </div>
      )}

      {/* Separator between base and affix stats */}
      {baseLines.length > 0 && affixLines.length > 0 && (
        <div className="item-tooltip-separator" />
      )}

      {/* Affix stats (blue) */}
      {affixLines.length > 0 && (
        <div className="item-tooltip-stats item-tooltip-affix-stats">
          {affixLines.map((s, i) => <span key={`a${i}`}>{s}</span>)}
        </div>
      )}

      {/* Consumable effects */}
      {item.consumable_effect && (
        <div className="item-tooltip-stats">
          {item.consumable_effect.type === 'heal' && (
            <span>Restores {item.consumable_effect.magnitude} HP</span>
          )}
          {item.consumable_effect.type === 'portal' && (
            <span>Teleports party out of dungeon</span>
          )}
        </div>
      )}

      {/* Set bonus section */}
      {formattedSets.length > 0 && formattedSets.map(set => (
        <div key={set.setId} className="item-tooltip-set-section">
          <div className="item-tooltip-separator" />
          <div className="item-tooltip-set-header">
            {set.setName} ({set.piecesEquipped}/{set.piecesTotal})
          </div>
          {set.bonuses.map((b, i) => (
            <div
              key={i}
              className={`item-tooltip-set-bonus ${b.active ? 'set-bonus-active' : 'set-bonus-inactive'}`}
            >
              <span className="set-bonus-icon">{b.active ? '✓' : '○'}</span>
              <span className="set-bonus-text">{b.description}</span>
            </div>
          ))}
        </div>
      ))}

      {/* Set info hint (when no active set data available) */}
      {setInfo && formattedSets.length === 0 && (
        <div className="item-tooltip-set-section">
          <div className="item-tooltip-separator" />
          <div className="item-tooltip-set-header">
            {setInfo.setName}
          </div>
        </div>
      )}

      {/* Item Comparison */}
      {comparison.length > 0 && (
        <div className="item-tooltip-comparison">
          <div className="item-tooltip-separator" />
          <div className="item-tooltip-compare-header">vs Equipped</div>
          {comparison.map((c, i) => (
            <div key={i} className={`compare-row compare-${c.direction}`}>
              <span className="compare-label">{c.label}</span>
              <span className="compare-delta">
                {c.direction === 'new' && <span className="compare-new">(new) {c.newVal}</span>}
                {c.direction === 'lost' && <span className="compare-lost">(lost) -{c.oldVal}</span>}
                {c.direction === 'up' && <span className="compare-up">▲ {c.deltaText}</span>}
                {c.direction === 'down' && <span className="compare-down">▼ {c.deltaText}</span>}
                {c.direction === 'same' && <span className="compare-same">—</span>}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Sell value */}
      {item.sell_value > 0 && (
        <div className="item-tooltip-sell">Sell: {item.sell_value}g</div>
      )}

      {/* Flavor text / description */}
      {item.description && (
        <div className="item-tooltip-desc">"{item.description}"</div>
      )}

      {/* Action hint */}
      {hint && (
        <div className="item-tooltip-hint">{hint}</div>
      )}
    </div>
  );
}
