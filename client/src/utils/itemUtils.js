/**
 * Item utility functions — shared across components.
 *
 * Phase 13-1C: Extracted from HeroDetailPanel.jsx, HeroRoster.jsx, Bank.jsx,
 * and Inventory.jsx to eliminate duplication.
 * Phase 16A: Expanded to support all new combat stats.
 * Phase 16C: Added getRarityColor(), getRarityDisplayName(), compareItems().
 * Phase 16E: Added getItemSetInfo(), formatSetBonuses() for set item display.
 * Phase 16G: Added compareItems() stat delta, formatAffixLines(), isNotableRarity(),
 *            getRarityIcon(), RARITY_NOTIFICATION_CONFIG for loot presentation.
 */

/**
 * Phase 16C: Canonical rarity color map (hex).
 * Matches server RARITY_COLORS, overlayRenderer RARITY_COLORS, and CSS variables.
 */
export const RARITY_COLORS = {
  common:   '#9d9d9d',
  uncommon: '#9d9d9d',  // Legacy alias (same as common)
  magic:    '#4488ff',
  rare:     '#ffcc00',
  epic:     '#b040ff',
  unique:   '#ff8800',
  set:      '#00cc44',
};

/**
 * Phase 16G: Rarity tiers that trigger drop notifications.
 * Maps rarity to notification config (duration ms, icon, label).
 */
export const RARITY_NOTIFICATION_CONFIG = {
  rare:   { duration: 3000, icon: '★', label: 'RARE ITEM DROPPED' },
  epic:   { duration: 5000, icon: '★★', label: 'EPIC ITEM DROPPED' },
  unique: { duration: 6000, icon: '◆', label: 'UNIQUE ITEM DROPPED' },
  set:    { duration: 6000, icon: '◈', label: 'SET ITEM DROPPED' },
};

/**
 * Get the hex color for a rarity tier.
 * @param {string} rarity - Rarity string (e.g. "magic", "rare", "epic")
 * @returns {string} Hex color code
 */
export function getRarityColor(rarity) {
  return RARITY_COLORS[rarity] || RARITY_COLORS.common;
}

/**
 * Get a human-readable display name for a rarity tier.
 * @param {string} rarity
 * @returns {string}
 */
export function getRarityDisplayName(rarity) {
  const names = {
    common:   'Common',
    uncommon: 'Common',
    magic:    'Magic',
    rare:     'Rare',
    epic:     'Epic',
    unique:   'Unique',
    set:      'Set',
  };
  return names[rarity] || 'Common';
}

/**
 * Phase 16G: Check if a rarity is notable enough for a drop notification.
 * @param {string} rarity
 * @returns {boolean}
 */
export function isNotableRarity(rarity) {
  return rarity in RARITY_NOTIFICATION_CONFIG;
}

/**
 * All stat keys with display metadata for formatting and comparison.
 * Ordered by display priority.
 */
const STAT_DEFINITIONS = [
  // Core stats
  { key: 'attack_damage', label: 'Melee', format: 'flat' },
  { key: 'ranged_damage', label: 'Ranged', format: 'flat' },
  { key: 'armor', label: 'Armor', format: 'flat' },
  { key: 'max_hp', label: 'HP', format: 'flat' },
  // Tier 1
  { key: 'crit_chance', label: 'Crit Chance', format: 'pct' },
  { key: 'crit_damage', label: 'Crit Damage', format: 'pct' },
  { key: 'dodge_chance', label: 'Dodge', format: 'pct' },
  { key: 'damage_reduction_pct', label: 'Damage Reduction', format: 'pct' },
  { key: 'hp_regen', label: 'HP Regen', format: 'flat' },
  { key: 'move_speed', label: 'Move Speed', format: 'flat' },
  // Tier 2
  { key: 'life_on_hit', label: 'Life on Hit', format: 'flat' },
  { key: 'cooldown_reduction_pct', label: 'CDR', format: 'pct' },
  { key: 'skill_damage_pct', label: 'Skill Damage', format: 'pct' },
  { key: 'thorns', label: 'Thorns', format: 'flat' },
  { key: 'gold_find_pct', label: 'Gold Find', format: 'pct' },
  { key: 'magic_find_pct', label: 'Magic Find', format: 'pct' },
  // Tier 3
  { key: 'holy_damage_pct', label: 'Holy Damage', format: 'pct' },
  { key: 'dot_damage_pct', label: 'DoT Damage', format: 'pct' },
  { key: 'heal_power_pct', label: 'Heal Power', format: 'pct' },
  { key: 'armor_pen', label: 'Armor Penetration', format: 'flat' },
];

/**
 * Format a single stat value for display.
 * @param {number} value
 * @param {'flat'|'pct'} format
 * @returns {string}
 */
function formatStatValue(value, format) {
  if (format === 'pct') return `${(value * 100).toFixed(0)}%`;
  return `${value}`;
}

/**
 * Format stat bonuses into human-readable strings.
 *
 * @param {Object} bonuses - Stat bonuses object from an item
 * @returns {string[]} Array of formatted stat strings (e.g. "+3 Melee")
 */
export function formatStatBonuses(bonuses) {
  if (!bonuses) return [];
  const lines = [];
  for (const { key, label, format } of STAT_DEFINITIONS) {
    const val = bonuses[key];
    if (val) {
      lines.push(`+${formatStatValue(val, format)} ${label}`);
    }
  }
  return lines;
}

/**
 * Phase 16G: Format affix lines separately from base stats.
 * Returns arrays of {text, isBase} for color-coding in tooltips.
 *
 * @param {Object} item - Full item data (with affixes, base_stats, stat_bonuses)
 * @returns {{ baseLines: string[], affixLines: string[] }}
 */
export function formatItemStatSections(item) {
  if (!item) return { baseLines: [], affixLines: [] };

  const baseStats = item.base_stats || {};
  const affixes = item.affixes || [];

  // Base stat lines (gray in tooltip)
  const baseLines = formatStatBonuses(baseStats);

  // Affix stat lines (blue in tooltip) — from the affix list  
  const affixLines = [];
  for (const affix of affixes) {
    if (affix.type === 'set_bonus') continue; // Set bonuses displayed separately
    const def = STAT_DEFINITIONS.find(d => d.key === affix.stat);
    if (def) {
      const val = affix.value;
      affixLines.push(`+${formatStatValue(val, def.format)} ${def.label}`);
    }
  }

  // If item has no affixes array but has stat_bonuses (legacy items), use those
  if (baseLines.length === 0 && affixLines.length === 0) {
    return { baseLines: formatStatBonuses(item.stat_bonuses), affixLines: [] };
  }

  return { baseLines, affixLines };
}

/**
 * Phase 16G: Compare two items for the same slot and produce stat deltas.
 *
 * @param {Object} newItem - Item being compared (potential equip)
 * @param {Object} equippedItem - Currently equipped item (or null)
 * @returns {Array<{label: string, oldVal: string, newVal: string, delta: number, direction: 'up'|'down'|'new'|'lost'}>}
 */
export function compareItems(newItem, equippedItem) {
  if (!newItem) return [];

  const newBonuses = newItem.stat_bonuses || {};
  const oldBonuses = equippedItem?.stat_bonuses || {};
  const results = [];

  for (const { key, label, format } of STAT_DEFINITIONS) {
    const newVal = newBonuses[key] || 0;
    const oldVal = oldBonuses[key] || 0;

    if (newVal === 0 && oldVal === 0) continue;

    const delta = newVal - oldVal;
    let direction = 'up';
    if (oldVal === 0) direction = 'new';
    else if (newVal === 0) direction = 'lost';
    else if (delta < 0) direction = 'down';
    else if (delta === 0) direction = 'same';

    results.push({
      label,
      oldVal: formatStatValue(oldVal, format),
      newVal: formatStatValue(newVal, format),
      delta,
      deltaText: delta > 0 ? `+${formatStatValue(delta, format)}` : (delta < 0 ? formatStatValue(delta, format) : ''),
      direction,
    });
  }

  return results;
}

/**
 * Phase 16E: Extract set info from an item's affixes (if it's a set piece).
 *
 * @param {Object} item - Item data object
 * @returns {{ setId: string, setName: string } | null} Set info or null
 */
export function getItemSetInfo(item) {
  if (!item || item.rarity !== 'set') return null;
  const affixes = item.affixes || [];
  for (const affix of affixes) {
    if (affix.type === 'set_bonus') {
      return {
        setId: affix.value,
        setName: affix.name,
      };
    }
  }
  return null;
}

/**
 * Phase 16E: Format active set bonuses for display in tooltips/panels.
 *
 * @param {Object[]} activeSets - Active set bonus data from player state
 * @returns {Object[]} Formatted set bonus entries for display
 */
export function formatSetBonuses(activeSets) {
  if (!activeSets || !activeSets.length) return [];
  return activeSets.map(set => ({
    setId: set.set_id,
    setName: set.set_name,
    piecesEquipped: set.pieces_equipped,
    piecesTotal: set.pieces_total,
    bonuses: (set.bonuses || []).map(b => ({
      piecesRequired: b.pieces_required,
      description: b.description,
      active: set.pieces_equipped >= b.pieces_required,
    })),
  }));
}

/**
 * Phase 21B: Class → preferred armor category mapping.
 * Mirrors server/configs/classes_config.json preferred_armor values.
 */
const CLASS_PREFERRED_ARMOR = {
  crusader:      'heavy',
  revenant:      'heavy',
  blood_knight:  'heavy',
  confessor:     'cloth',
  shaman:        'cloth',
  mage:          'cloth',
  bard:          'cloth',
  plague_doctor: 'cloth',
  ranger:        'light',
  inquisitor:    'light',
  hexblade:      'light',
};

/** Phase 21B: Default affinity bonus percentage (matches server default). */
const DEFAULT_AFFINITY_BONUS = 0.15;

/** Phase 21B: Human-readable armor category labels. */
export const ARMOR_CATEGORY_LABELS = {
  heavy: 'Heavy Armor',
  light: 'Light Armor',
  cloth: 'Cloth Armor',
};

/**
 * Phase 21B: Check if an armor item matches a class's preferred armor category.
 *
 * @param {Object} item - Item data object (must have armor_category)
 * @param {string} classId - Player's class_id (e.g. "crusader", "mage")
 * @returns {{ isMatch: boolean, bonusPct: number, categoryLabel: string, className: string } | null}
 *   Returns null if item is not armor or has no category.
 */
export function getArmorAffinityInfo(item, classId) {
  if (!item || !item.armor_category || !classId) return null;

  const preferred = CLASS_PREFERRED_ARMOR[classId];
  const categoryLabel = ARMOR_CATEGORY_LABELS[item.armor_category] || item.armor_category;
  const className = classId.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  return {
    isMatch: item.armor_category === preferred,
    bonusPct: item.armor_category === preferred ? DEFAULT_AFFINITY_BONUS : 0,
    categoryLabel,
    className,
  };
}

/**
 * Phase 21D: Stat display groups for tier organization in tooltips.
 */
export const STAT_DISPLAY_GROUPS = [
  { label: 'Core', keys: ['attack_damage', 'ranged_damage', 'armor', 'max_hp'] },
  { label: 'Offensive', keys: ['crit_chance', 'crit_damage', 'skill_damage_pct', 'holy_damage_pct', 'dot_damage_pct', 'armor_pen'] },
  { label: 'Defensive', keys: ['dodge_chance', 'damage_reduction_pct', 'hp_regen', 'life_on_hit', 'thorns'] },
  { label: 'Utility', keys: ['cooldown_reduction_pct', 'move_speed', 'heal_power_pct', 'gold_find_pct', 'magic_find_pct'] },
];

/**
 * Phase 21D: Inline comparison between two items with tier grouping info.
 * Returns array of stat comparisons with formatted values for direct tooltip rendering.
 *
 * @param {Object} newItem - The item being inspected (potential equip)
 * @param {Object} equippedItem - The currently equipped item in the same slot
 * @returns {Array<{key, label, format, newVal, oldVal, delta, direction, tier, newValFormatted, oldValFormatted, deltaFormatted}>}
 */
export function compareItemsInline(newItem, equippedItem) {
  if (!newItem) return [];

  const newBonuses = newItem.stat_bonuses || {};
  const oldBonuses = equippedItem?.stat_bonuses || {};

  const statToTier = {};
  for (const group of STAT_DISPLAY_GROUPS) {
    for (const key of group.keys) {
      statToTier[key] = group.label;
    }
  }

  const results = [];

  for (const { key, label, format } of STAT_DEFINITIONS) {
    const newVal = newBonuses[key] || 0;
    const oldVal = oldBonuses[key] || 0;

    if (newVal === 0 && oldVal === 0) continue;

    const delta = newVal - oldVal;
    let direction = 'same';
    if (oldVal === 0 && newVal !== 0) direction = 'new';
    else if (newVal === 0 && oldVal !== 0) direction = 'lost';
    else if (delta > 0) direction = 'up';
    else if (delta < 0) direction = 'down';

    results.push({
      key,
      label,
      format,
      newVal,
      oldVal,
      delta,
      direction,
      tier: statToTier[key] || 'Utility',
      newValFormatted: newVal !== 0 ? `+${formatStatValue(newVal, format)}` : '',
      oldValFormatted: oldVal !== 0 ? formatStatValue(oldVal, format) : '',
      deltaFormatted: delta > 0 ? `▲ +${formatStatValue(delta, format)}`
                    : delta < 0 ? `▼ ${formatStatValue(delta, format)}`
                    : '—',
    });
  }

  return results;
}

/**
 * Phase 21D: Compute overall comparison verdict from inline comparison results.
 *
 * @param {Array} comparison - Result from compareItemsInline()
 * @returns {{ upgrades: number, downgrades: number, label: string, color: string }}
 */
export function getComparisonVerdict(comparison) {
  const upgrades = comparison.filter(c => c.direction === 'up' || c.direction === 'new').length;
  const downgrades = comparison.filter(c => c.direction === 'down' || c.direction === 'lost').length;

  let label, color;
  if (upgrades > 0 && downgrades === 0) {
    label = `◆ ${upgrades} upgrade${upgrades > 1 ? 's' : ''}`;
    color = 'green';
  } else if (upgrades > 0 && downgrades > 0) {
    label = `◆ ${upgrades} upgrade${upgrades > 1 ? 's' : ''}, ${downgrades} downgrade${downgrades > 1 ? 's' : ''}`;
    color = 'amber';
  } else if (downgrades > 0) {
    label = `◆ ${downgrades} downgrade${downgrades > 1 ? 's' : ''}`;
    color = 'red';
  } else {
    label = '◆ Same stats';
    color = 'gray';
  }

  return { upgrades, downgrades, label, color };
}

/**
 * Phase 21G-1: Compare an item against all party members' equipped gear in the same slot.
 * Returns an array of { unitId, className, displayName, verdict, fitScore,
 *                        isAffinityMatch, isBestFit, isCurrentHero }
 */
export function getPartyFitRoster(item, partyMembers, partyInventories, players, currentUnitId) {
  if (!item?.equip_slot || !partyMembers?.length) return [];

  const slot = item.equip_slot;
  const results = partyMembers
    .filter(m => m.is_alive)
    .map(member => {
      const memberEquip = partyInventories[member.unit_id]?.equipment || {};
      const equippedItem = memberEquip[slot] || null;

      let verdict, fitScore;
      if (!equippedItem) {
        verdict = { upgrades: 1, downgrades: 0, label: '▲ empty slot', color: 'green' };
        fitScore = 1;
      } else {
        const comparison = compareItemsInline(item, equippedItem);
        verdict = getComparisonVerdict(comparison);
        fitScore = verdict.upgrades - verdict.downgrades;
      }

      const affinity = getArmorAffinityInfo(item, member.class_id);

      return {
        unitId: member.unit_id,
        className: players[member.unit_id]?.class_id || member.class_id,
        displayName: member.username,
        verdict,
        fitScore,
        isAffinityMatch: affinity?.isMatch || false,
        isBestFit: false,
        isCurrentHero: member.unit_id === currentUnitId,
      };
    });

  // Determine best fit
  const bestScore = Math.max(...results.map(r => r.fitScore));
  if (bestScore > 0) {
    const bestCandidates = results.filter(r => r.fitScore === bestScore);
    const best = bestCandidates.find(r => r.isAffinityMatch) || bestCandidates[0];
    best.isBestFit = true;
  }

  return results;
}

/**
 * Phase 21G-3: Class abbreviation map for bag-slot best-fit badges.
 */
export const CLASS_BADGE_ABBREV = {
  crusader: 'Cr', revenant: 'Re', blood_knight: 'BK',
  confessor: 'Co', shaman: 'Sh', mage: 'Ma', bard: 'Ba',
  plague_doctor: 'PD', ranger: 'Ra', inquisitor: 'In', hexblade: 'Hx',
};

/**
 * Phase 21G-3: From a partyFitRoster result, return badge info for a bag slot overlay.
 * Returns null if no upgrades exist for any party member.
 */
export function getBestFitBadge(roster) {
  if (!roster?.length) return null;

  const upgraders = roster.filter(r => r.fitScore > 0);
  if (upgraders.length === 0) return null;

  const best = roster.find(r => r.isBestFit);
  if (!best) return null;

  if (upgraders.length > 1) {
    return { label: `▲${upgraders.length}`, color: 'gold', tooltip: `Upgrade for ${upgraders.length} heroes` };
  }

  const abbrev = CLASS_BADGE_ABBREV[best.className] || best.className.charAt(0).toUpperCase();
  return { label: `▲${abbrev}`, color: best.isCurrentHero ? 'green-bright' : 'green', tooltip: `Upgrade for ${best.displayName}` };
}
