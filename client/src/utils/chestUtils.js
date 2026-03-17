/**
 * chestUtils — Chest tier parsing and visual configuration.
 *
 * Chest states use the format "unopened:tier" / "opened:tier"
 * (e.g. "unopened:iron", "opened:gold"). Plain "unopened"/"opened"
 * are treated as "wooden" tier for backward compatibility.
 */

// ── Chest Tier Visual Configuration ──

export const CHEST_TIERS = {
  wooden: {
    name: 'Wooden Chest',
    bodyColor:       '#8B6914',
    bodyDark:        '#6B4F10',
    bodyHighlight:   '#A8801A',
    bandColor:       '#5C4033',
    latchColor:      '#C8AA6E',
    lidColor:        '#9B7924',
    openedColor:     '#6B5B3A',
    glowColor:       null,
    minimapColor:    '#B8860B',
    minimapOpened:   '#6B5B3A',
  },
  iron: {
    name: 'Iron Chest',
    bodyColor:       '#5A5A6E',
    bodyDark:        '#3E3E50',
    bodyHighlight:   '#7A7A90',
    bandColor:       '#3A3A4A',
    latchColor:      '#C0C0D0',
    lidColor:        '#6A6A7E',
    openedColor:     '#4A4A5A',
    glowColor:       null,
    minimapColor:    '#7A7A8E',
    minimapOpened:   '#4A4A5A',
  },
  gold: {
    name: 'Gold Chest',
    bodyColor:       '#DAA520',
    bodyDark:        '#B8860B',
    bodyHighlight:   '#FFD700',
    bandColor:       '#8B6914',
    latchColor:      '#FFD700',
    lidColor:        '#E8B830',
    openedColor:     '#8B7355',
    glowColor:       'rgba(255, 215, 0, 0.25)',
    minimapColor:    '#FFD700',
    minimapOpened:   '#8B7355',
  },
  obsidian: {
    name: 'Obsidian Chest',
    bodyColor:       '#2A1A3A',
    bodyDark:        '#1A0A2A',
    bodyHighlight:   '#4A2A5A',
    bandColor:       '#6A3A8A',
    latchColor:      '#C77DFF',
    lidColor:        '#3A2A4A',
    openedColor:     '#2A1A30',
    glowColor:       'rgba(180, 80, 255, 0.3)',
    minimapColor:    '#9B59B6',
    minimapOpened:   '#2A1A30',
  },
  boss_chest: {
    name: 'Boss Chest',
    bodyColor:       '#8B0000',
    bodyDark:        '#5C0000',
    bodyHighlight:   '#CC2200',
    bandColor:       '#DAA520',
    latchColor:      '#FFD700',
    lidColor:        '#AA1100',
    openedColor:     '#5A2A2A',
    glowColor:       'rgba(255, 50, 0, 0.3)',
    minimapColor:    '#FF4444',
    minimapOpened:   '#5A2A2A',
  },
};

const DEFAULT_TIER = 'wooden';

/**
 * Parse a chest state string into { isOpened, tier }.
 * Handles both new format ("unopened:iron") and legacy ("unopened").
 */
export function parseChestState(state) {
  if (!state) return { isOpened: false, tier: DEFAULT_TIER };
  const parts = state.split(':');
  const status = parts[0];
  const tier = parts[1] || DEFAULT_TIER;
  return { isOpened: status === 'opened', tier };
}

/** Check if a chest state represents an unopened chest. */
export function isChestUnopened(state) {
  if (!state) return false;
  return state === 'unopened' || state.startsWith('unopened:');
}

/** Check if a chest state represents an opened chest. */
export function isChestOpened(state) {
  if (!state) return false;
  return state === 'opened' || state.startsWith('opened:');
}

/** Get the tier config for a given tier ID. */
export function getChestTierConfig(tier) {
  return CHEST_TIERS[tier] || CHEST_TIERS[DEFAULT_TIER];
}

/**
 * Get minimap color for a chest based on its state string.
 */
export function getChestMinimapColor(state) {
  const { isOpened, tier } = parseChestState(state);
  const config = getChestTierConfig(tier);
  return isOpened ? config.minimapOpened : config.minimapColor;
}
