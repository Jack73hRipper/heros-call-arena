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
