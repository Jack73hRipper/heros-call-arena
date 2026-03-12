/**
 * SkillIconMap — Maps skill_id to sprite regions on the 64x64 skill icon sheet.
 *
 * Source: Assets/Sprites/64x64-atlas.json (cataloged in Sprite Cataloger)
 * Sheet: /skill-icons.png (1024 × 8768, 64×64 grid)
 *
 * Skills without atlas entries fall back to their emoji icon from skills_config.
 */

const SKILL_ICON_SHEET = '/skill-icons.png';

/**
 * Sprite regions: { x, y, w, h } on the skill-icons.png sheet.
 * Keys are skill_id values from skills_config.json.
 */
const SKILL_SPRITE_MAP = {
  // Auto attacks (shared icon)
  auto_attack_melee:  { x: 0,   y: 2880, w: 64, h: 64 },
  auto_attack_ranged: { x: 0,   y: 2880, w: 64, h: 64 },

  // Class skills
  heal:              { x: 512,  y: 4928, w: 64, h: 64 },
  double_strike:     { x: 704,  y: 5312, w: 64, h: 64 },
  power_shot:        { x: 768,  y: 5312, w: 64, h: 64 },
  war_cry:           { x: 384,  y: 5248, w: 64, h: 64 },
  shadow_step:       { x: 128,  y: 4800, w: 64, h: 64 },
  wither:            { x: 384,  y: 2944, w: 64, h: 64 },
  ward:              { x: 768,  y: 4672, w: 64, h: 64 },
  potion:            { x: 192,  y: 1088, w: 64, h: 64 },
  divine_sense:      { x: 704,  y: 5120, w: 64, h: 64 },
  venom_gaze:        null,  // No atlas entry yet — uses emoji fallback
  soul_reap:         null,  // No atlas entry yet — uses emoji fallback
  rebuke:            null,  // No atlas entry yet — uses emoji fallback
  shield_of_faith:   { x: 0,    y: 4992, w: 64, h: 64 },
  exorcism:          { x: 768,  y: 4928, w: 64, h: 64 },
  prayer:            { x: 640,  y: 4928, w: 64, h: 64 },

  // Phase 12: Crusader new skills
  taunt:             null,  // No atlas entry yet — uses emoji fallback
  shield_bash:       null,  // No atlas entry yet — uses emoji fallback
  holy_ground:       null,  // No atlas entry yet — uses emoji fallback
  bulwark:           null,  // No atlas entry yet — uses emoji fallback

  // Phase 12: Ranger new skills
  volley:            null,  // No atlas entry yet — uses emoji fallback
  evasion:           null,  // No atlas entry yet — uses emoji fallback
  crippling_shot:    null,  // No atlas entry yet — uses emoji fallback

  // Phase 25: Revenant skills
  grave_thorns:      null,  // No atlas entry yet — uses emoji fallback
  grave_chains:      null,  // No atlas entry yet — uses emoji fallback
  undying_will:      null,  // No atlas entry yet — uses emoji fallback
  soul_rend:         null,  // No atlas entry yet — uses emoji fallback
};

// Emoji fallbacks for skills without sprite icons
const EMOJI_FALLBACKS = {
  auto_attack_melee:  '⚔️',
  auto_attack_ranged: '🏹',
  heal:               '💚',
  double_strike:      '⚔️⚔️',
  power_shot:         '🎯',
  war_cry:            '📯',
  shadow_step:        '👤',
  wither:             '🩸',
  ward:               '🛡️',
  divine_sense:       '👁️',
  venom_gaze:         '🐍',
  soul_reap:          '💀',
  rebuke:             '⚡',
  shield_of_faith:    '✨',
  exorcism:           '☀️',
  prayer:             '🙏',
  potion:             '🧪',

  // Phase 12: Crusader new skills
  taunt:              '🗣️',
  shield_bash:        '🛡️💥',
  holy_ground:        '✝️',
  bulwark:            '🏰',

  // Phase 12: Ranger new skills
  volley:             '🌧️🏹',
  evasion:            '💨',
  crippling_shot:     '🦵🏹',

  // Phase 25: Revenant skills
  grave_thorns:       '🦴',
  grave_chains:       '⛓️',
  undying_will:       '💀',
  soul_rend:          '⚔️',
};

// ---- Sprite sheet loader (singleton) ----

let iconImage = null;
let iconLoadPromise = null;
let iconLoaded = false;

/**
 * Start loading the skill icon sprite sheet. Safe to call multiple times.
 */
export function loadSkillIconSheet() {
  if (iconLoadPromise) return iconLoadPromise;

  iconLoadPromise = new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      iconImage = img;
      iconLoaded = true;
      resolve(img);
    };
    img.onerror = (err) => {
      console.warn('[SkillIconMap] Failed to load skill icon sheet:', err);
      iconLoadPromise = null;
      reject(err);
    };
    img.src = SKILL_ICON_SHEET;
  });

  return iconLoadPromise;
}

/**
 * Check if a skill has a sprite icon on the sheet.
 */
export function hasSkillSprite(skillId) {
  return SKILL_SPRITE_MAP[skillId] != null;
}

/**
 * Get the sprite region for a skill, or null if not available.
 */
export function getSkillSpriteRegion(skillId) {
  return SKILL_SPRITE_MAP[skillId] || null;
}

/**
 * Get the emoji fallback for a skill.
 */
export function getSkillEmoji(skillId) {
  return EMOJI_FALLBACKS[skillId] || '❓';
}

/**
 * Get the loaded icon image element, or null if not yet loaded.
 */
export function getSkillIconImage() {
  return iconLoaded ? iconImage : null;
}

/**
 * Check if the skill icon sheet is loaded.
 */
export function isSkillIconSheetLoaded() {
  return iconLoaded;
}

export { SKILL_ICON_SHEET, SKILL_SPRITE_MAP, EMOJI_FALLBACKS };
