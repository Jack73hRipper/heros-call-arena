import React, { useRef, useLayoutEffect, useState } from 'react';
import {
  getRarityDisplayName,
  formatStatBonuses, formatItemStatSections,
  compareItemsInline, getComparisonVerdict,
  getItemSetInfo, formatSetBonuses,
  getArmorAffinityInfo, getPartyFitRoster,
  STAT_DISPLAY_GROUPS,
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
export default function ItemTooltip({ item, equippedItem, activeSets, hint, rect, showComparison = true, classId, compareHeroName, compareHeroIndex, compareHeroTotal, partyMembers, partyInventories, players, currentUnitId }) {
  if (!item) return null;

  const rarity = item.rarity || 'common';
  const rarityLabel = getRarityDisplayName(rarity);
  const baseTypeName = item.display_name ? `${rarityLabel} ${item.display_name}` : `${rarityLabel} ${item.item_type || ''}`;

  // Set info
  const setInfo = getItemSetInfo(item);
  const formattedSets = setInfo && activeSets ? formatSetBonuses(activeSets).filter(s => s.setId === setInfo.setId) : [];

  // Phase 21B: Armor affinity info
  const affinityInfo = getArmorAffinityInfo(item, classId);

  // Phase 21D: Inline comparison
  const isComparing = showComparison && !!equippedItem;
  const inlineComparison = isComparing ? compareItemsInline(item, equippedItem) : null;
  const verdict = inlineComparison && inlineComparison.length > 0
    ? getComparisonVerdict(inlineComparison)
    : null;

  // Group comparison by tier
  const comparisonGroups = inlineComparison
    ? STAT_DISPLAY_GROUPS
        .map(group => ({
          label: group.label,
          stats: inlineComparison.filter(s => s.tier === group.label),
        }))
        .filter(g => g.stats.length > 0)
    : [];

  // Phase 21G-1: Party Fit Roster
  const showPartyFit = partyMembers && partyMembers.length > 1 && !!item.equip_slot;
  const partyFitRoster = showPartyFit
    ? getPartyFitRoster(item, partyMembers, partyInventories, players, currentUnitId)
    : [];

  // Source tracking for color coding (base=gray, affix=blue)
  const baseStatKeys = new Set(
    Object.entries(item.base_stats || {})
      .filter(([, v]) => v && v !== 0)
      .map(([k]) => k)
  );

  // Compact mode: merged stat list (no comparison)
  let compactStatLines = [];
  if (!isComparing) {
    compactStatLines = formatStatBonuses(item.stat_bonuses);
    if (compactStatLines.length === 0) {
      const sections = formatItemStatSections(item);
      compactStatLines = [...sections.baseLines, ...sections.affixLines];
    }
  }

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
    <div ref={tooltipRef} className={`item-tooltip rarity-${rarity}${isComparing ? ' has-comparison' : ''}`} style={tooltipStyle}>
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

      {/* Phase 21B: Armor category tag */}
      {affinityInfo && (
        <div className="item-tooltip-armor-category">
          [{affinityInfo.categoryLabel}]
        </div>
      )}

      {/* Phase 21B: Affinity bonus line (gold accent when matched) */}
      {affinityInfo && affinityInfo.isMatch && (
        <div className="item-tooltip-affinity-bonus">
          ✦ {affinityInfo.className} Affinity — +{Math.round(affinityInfo.bonusPct * 100)}% base stats
        </div>
      )}

      {/* Phase 21G-2: Comparison target header (Q-to-Cycle) */}
      {compareHeroName && (
        <div className="tooltip-compare-target">
          Comparing for: <span className="compare-target-name">{compareHeroName}</span>
          <span className="compare-target-index">({compareHeroIndex}/{compareHeroTotal})</span>
          <span className="compare-target-hint">[Q]</span>
        </div>
      )}

      {/* COMPARISON MODE: Tier-grouped inline comparison */}
      {comparisonGroups.length > 0 && (
        <div className="tooltip-inline-comparison">
          {comparisonGroups.map(group => (
            <div key={group.label} className="tooltip-stat-group">
              <div className="tooltip-stat-group-header">{group.label}</div>
              {group.stats.map(stat => (
                <div key={stat.key} className={`tooltip-stat-row stat-dir-${stat.direction}`}>
                  <span className={`tooltip-stat-value ${baseStatKeys.has(stat.key) ? 'stat-source-base' : 'stat-source-affix'}`}>
                    {stat.direction !== 'lost' ? stat.newValFormatted : ''}
                  </span>
                  <span className="tooltip-stat-label">{stat.label}</span>
                  <span className="tooltip-stat-compare">
                    {(stat.direction === 'up' || stat.direction === 'down' || stat.direction === 'same') && (
                      <span className="tooltip-stat-equipped">(eq: {stat.oldValFormatted})</span>
                    )}
                    {stat.direction === 'new' && <span className="tooltip-stat-new-tag">(new)</span>}
                    {stat.direction === 'lost' && <span className="tooltip-stat-lost-tag">(losing {stat.oldValFormatted})</span>}
                  </span>
                  <span className={`tooltip-stat-delta delta-${stat.direction}`}>
                    {stat.direction === 'up' || stat.direction === 'down' || stat.direction === 'lost'
                      ? stat.deltaFormatted
                      : stat.direction === 'same' ? '—' : ''}
                  </span>
                </div>
              ))}
            </div>
          ))}
          {verdict && (
            <>
              <div className="item-tooltip-separator" />
              <div className={`tooltip-verdict verdict-${verdict.color}`}>
                {verdict.label}
              </div>
            </>
          )}
        </div>
      )}

      {/* COMPACT MODE: Merged stat list */}
      {!isComparing && compactStatLines.length > 0 && (
        <div className="item-tooltip-stats item-tooltip-compact-stats">
          {compactStatLines.map((s, i) => <span key={`c${i}`}>{s}</span>)}
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

      {/* Phase 21G-1: Party Fit Roster */}
      {partyFitRoster.length > 0 && (
        <div className={`tooltip-party-fit${partyFitRoster.length === 1 ? ' single-hero' : ''}`}>
          <div className="tooltip-party-fit-header">Party Fit</div>
          {partyFitRoster.map(r => {
            let verdictClass = 'fit-same';
            let verdictText = '— same';
            if (r.fitScore > 0) {
              verdictClass = 'fit-upgrade';
              verdictText = r.verdict.label === '▲ empty slot' ? '▲ empty slot' : '▲ upgrade';
            } else if (r.fitScore < 0) {
              verdictClass = 'fit-worse';
              verdictText = '▼ worse';
            } else if (r.verdict.upgrades > 0 && r.verdict.downgrades > 0) {
              verdictClass = 'fit-tradeoff';
              verdictText = '↔ trade-off';
            }
            return (
              <div key={r.unitId} className="party-fit-row">
                <span className="party-fit-name">{r.displayName}</span>
                <span className={`party-fit-verdict ${verdictClass}`}>{verdictText}</span>
                <span className="party-fit-badges">
                  {r.isBestFit && <span className="party-fit-best" title="Best fit">★ best fit</span>}
                  {r.isAffinityMatch && <span className="party-fit-affinity" title="Armor affinity match">✦</span>}
                </span>
                {r.isCurrentHero && <span className="party-fit-current">(current)</span>}
              </div>
            );
          })}
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
