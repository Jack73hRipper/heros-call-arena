/**
 * SpriteLoader — Loads the combined sprite sheet and provides
 * sprite drawing utilities for hero classes and enemy types.
 *
 * Sprite mappings are derived from the cataloged sprite atlas.
 * Heroes use static sprites (no animation).
 * Enemy types with named sprites get sprite rendering; others fall back to shapes.
 */

const SPRITESHEET_PATH = `${import.meta.env.BASE_URL}spritesheet.png`;

// Sprite regions from the atlas (x, y, w, h on the 4096×3072 sheet)
// Only includes named/cataloged sprites mapped to game entities.
const SPRITE_MAP = {
  // ── Hero classes — variant 1 (default) ──
  crusader:     { x: 270,  y: 0,    w: 270, h: 270 },   // Crusader_1
  confessor:    { x: 540,  y: 540,  w: 270, h: 270 },   // Confessor_1
  inquisitor:   { x: 0,    y: 1080, w: 270, h: 270 },   // Inquisitor_1
  ranger:       { x: 810,  y: 270,  w: 270, h: 270 },   // Ranger_1
  hexblade:     { x: 810,  y: 540,  w: 270, h: 270 },   // Hexblade_1
  mage:         { x: 1890, y: 1350, w: 270, h: 270 },   // Mage_1
  bard:          { x: 2430, y: 2160, w: 270, h: 270 },   // Bard_1
  blood_knight:  { x: 2700, y: 2160, w: 270, h: 270 },   // BloodKnight_Female_1
  plague_doctor:  { x: 2160, y: 2430, w: 270, h: 270 },   // Witch_Doctor1
  revenant:       { x: 2970, y: 2430, w: 270, h: 270 },   // Reaver_1
  shaman:          { x: 3240, y: 2430, w: 270, h: 270 },   // Shaman_1

  // ── Hero classes — variant 2 ──
  crusader_2:   { x: 1080, y: 0,    w: 270, h: 270 },   // Crusader_2
  confessor_2:  { x: 270,  y: 540,  w: 270, h: 270 },   // Confessor_2
  inquisitor_2: { x: 1620, y: 1080, w: 270, h: 270 },   // Inquisitor_2
  ranger_2:     { x: 810,  y: 810,  w: 270, h: 270 },   // Ranger_2
  hexblade_2:   { x: 1080, y: 2160, w: 270, h: 270 },   // Hexblade_2
  mage_2:       { x: 270,  y: 810,  w: 270, h: 270 },   // Mage_2
  blood_knight_2:{ x: 2700, y: 2430, w: 270, h: 270 },   // Blood_Knight_Female_2
  plague_doctor_2:{ x: 2160, y: 2700, w: 270, h: 270 },   // Witch_Doctor2

  // ── Hero classes — variant 3 ──
  crusader_3:   { x: 540,  y: 2430, w: 270, h: 270 },   // Crusader_3
  confessor_3:  { x: 540,  y: 2160, w: 270, h: 270 },   // Confessor_3
  inquisitor_3: { x: 1890, y: 0,    w: 270, h: 270 },   // Inquisitor_3
  ranger_3:     { x: 2160, y: 1350, w: 270, h: 270 },   // Ranger_3
  hexblade_3:   { x: 1620, y: 0,    w: 270, h: 270 },   // Hexblade_3
  mage_3:       { x: 0,    y: 270,  w: 270, h: 270 },   // Mage_3
  blood_knight_3:{ x: 2970, y: 2160, w: 270, h: 270 },   // Blood_Knight_Female_3
  plague_doctor_3:{ x: 2430, y: 2430, w: 270, h: 270 },   // Witch_Doctor3

  // ── Hero classes — variant 4 ──
  crusader_4:   { x: 1080, y: 540,  w: 270, h: 270 },   // Crusader_4
  confessor_4:  { x: 0,    y: 0,    w: 270, h: 270 },   // Confessor_4
  inquisitor_4: { x: 2430, y: 1080, w: 270, h: 270 },   // Inquisitor_4
  ranger_4:     { x: 2970, y: 0,    w: 270, h: 270 },   // Ranger_4
  hexblade_4:   { x: 1620, y: 1890, w: 270, h: 270 },   // Hexblade_4
  mage_4:       { x: 0,    y: 2700, w: 270, h: 270 },   // Mage_4
  blood_knight_4:{ x: 3240, y: 2160, w: 270, h: 270 },   // Blood_Knight_Male_1

  // ── Hero classes — variant 5 ──
  crusader_5:   { x: 540,  y: 0,    w: 270, h: 270 },   // Crusader_5
  confessor_5:  { x: 1080, y: 810,  w: 270, h: 270 },   // Confessor_5
  inquisitor_5: { x: 0,    y: 810,  w: 270, h: 270 },   // Inquisitor_5
  hexblade_5:   { x: 1890, y: 1080, w: 270, h: 270 },   // Hexblade_5
  mage_5:       { x: 2700, y: 540,  w: 270, h: 270 },   // Mage_5

  // ── Hero classes — variant 6 ──
  crusader_6:   { x: 540,  y: 270,  w: 270, h: 270 },   // Crusader_6
  confessor_6:  { x: 0,    y: 2430, w: 270, h: 270 },   // Confessor_6
  inquisitor_6: { x: 1350, y: 2160, w: 270, h: 270 },   // Inquisitor_6
  hexblade_6:   { x: 270,  y: 270,  w: 270, h: 270 },   // Hexblade_6
  mage_6:       { x: 2430, y: 540,  w: 270, h: 270 },   // Mage_6

  // ── Hero classes — variant 7+ ──
  inquisitor_7: { x: 270,  y: 2430, w: 270, h: 270 },   // Inquisitor_7
  mage_7:       { x: 1890, y: 270,  w: 270, h: 270 },   // Mage_7
  hexblade_7:   { x: 540,  y: 1620, w: 270, h: 270 },   // Hexblade_7
  hexblade_8:   { x: 2970, y: 1620, w: 270, h: 270 },   // Hexblade_8
  hexblade_9:   { x: 2430, y: 1350, w: 270, h: 270 },   // Hexblade_9
  mage_8:       { x: 2160, y: 2160, w: 270, h: 270 },   // Mage_8

  // ── Enemy types — base sprites ──
  demon:        { x: 1620, y: 2160, w: 270, h: 270 },   // Demon_1 (fixed — was incorrectly mapped to Imp_3)
  skeleton:     { x: 1890, y: 2700, w: 270, h: 270 },   // Skeleton_1
  undead_knight:{ x: 2160, y: 1080, w: 270, h: 270 },   // Undead_Knight
  imp:          { x: 1350, y: 1890, w: 270, h: 270 },   // Imp_1 (NEW — imp had no sprite before)
  wraith:       { x: 1890, y: 1890, w: 270, h: 270 },   // Wraith
  medusa:       { x: 1350, y: 1620, w: 270, h: 270 },   // Medusa
  acolyte:      { x: 2430, y: 1620, w: 270, h: 270 },   // Acolyte
  werewolf:     { x: 0,    y: 1350, w: 270, h: 270 },   // Werewolf
  reaper:       { x: 0,    y: 2160, w: 270, h: 270 },   // Reaper
  construct:    { x: 810,  y: 0,    w: 270, h: 270 },   // Construct_1

  // ── Enemy types — variant sprites ──
  demon_2:        { x: 1890, y: 2160, w: 270, h: 270 },   // Demon_2
  undead_knight_2:{ x: 2430, y: 1890, w: 270, h: 270 },   // Undead_Knight_2
  undead_knight_3:{ x: 1620, y: 540,  w: 270, h: 270 },   // Undead_Knight_3
  imp_2:          { x: 270,  y: 2160, w: 270, h: 270 },   // Imp_2
  imp_3:          { x: 540,  y: 810,  w: 270, h: 270 },   // Imp_3
  imp_4:          { x: 1620, y: 1350, w: 270, h: 270 },   // Imp_4
  wraith_2:       { x: 1890, y: 810,  w: 270, h: 270 },   // Wraith_2
  wraith_3:       { x: 540,  y: 1080, w: 270, h: 270 },   // Wraith_3
  medusa_2:       { x: 1350, y: 540,  w: 270, h: 270 },   // Medusa_2
  acolyte_2:      { x: 0,    y: 1620, w: 270, h: 270 },   // Acolyte_2
  acolyte_3:      { x: 1620, y: 2430, w: 270, h: 270 },   // Acolyte_3
  werewolf_2:     { x: 810,  y: 2700, w: 270, h: 270 },   // Werewolf_2
  construct_2:    { x: 2430, y: 0,    w: 270, h: 270 },   // Construct_2
  construct_3:    { x: 1350, y: 1080, w: 270, h: 270 },   // Construct_3

  // ── New enemy types ──
  imp_lord:         { x: 2700, y: 1350, w: 270, h: 270 },   // Imp_Lord
  demon_boss:       { x: 1350, y: 0,    w: 270, h: 270 },   // Demon_Boss
  demon_knight:     { x: 270,  y: 1350, w: 270, h: 270 },   // Demon_Knight1
  construct_boss:   { x: 540,  y: 2700, w: 270, h: 270 },   // Construct_Boss
  ghoul:            { x: 2160, y: 1620, w: 270, h: 270 },   // Ghoul
  necromancer:      { x: 2970, y: 540,  w: 270, h: 270 },   // Necromancer_1
  undead_caster:    { x: 1350, y: 2700, w: 270, h: 270 },   // Undead_Caster
  horror:           { x: 2700, y: 270,  w: 270, h: 270 },   // Horror_1
  horror_2:         { x: 810,  y: 2430, w: 270, h: 270 },   // Horror_2
  insectoid:        { x: 270,  y: 1890, w: 270, h: 270 },   // Insectoid_1
  insectoid_2:      { x: 2160, y: 810,  w: 270, h: 270 },   // Insectoid_2
  caster:           { x: 1080, y: 270,  w: 270, h: 270 },   // Caster_1
  caster_2:         { x: 0,    y: 540,  w: 270, h: 270 },   // Caster_2
  evil_snail:       { x: 2970, y: 1350, w: 270, h: 270 },   // Evil_Snail
  goblin_spearman:  { x: 2160, y: 1890, w: 270, h: 270 },   // Goblin_Spearman
  shade:            { x: 2970, y: 1890, w: 270, h: 270 },   // Monsters_37 → Shade
};

// Number of sprite variants available per hero class
export const HERO_SPRITE_VARIANTS = {
  crusader: 6,
  confessor: 6,
  inquisitor: 7,
  ranger: 4,
  hexblade: 9,
  mage: 8,
  bard: 1,
  blood_knight: 4,
  plague_doctor: 3,
  revenant: 1,
  shaman: 1,
};

// Number of sprite variants available per enemy type
export const ENEMY_SPRITE_VARIANTS = {
  demon: 2,
  skeleton: 1,
  undead_knight: 3,
  imp: 4,
  wraith: 3,
  medusa: 2,
  acolyte: 3,
  werewolf: 2,
  reaper: 1,
  construct: 3,
  imp_lord: 1,
  demon_boss: 1,
  demon_knight: 1,
  construct_boss: 1,
  ghoul: 1,
  necromancer: 1,
  undead_caster: 1,
  horror: 2,
  insectoid: 2,
  caster: 2,
  evil_snail: 1,
  goblin_spearman: 1,
  shade: 1,
};

let spriteImage = null;
let loadPromise = null;
let loaded = false;

/**
 * Start loading the sprite sheet. Safe to call multiple times.
 * Returns a promise that resolves when the image is ready.
 */
export function loadSpriteSheet() {
  if (loadPromise) return loadPromise;

  loadPromise = new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      spriteImage = img;
      loaded = true;
      console.log('[SpriteLoader] Sprite sheet loaded:', img.width, 'x', img.height);
      resolve(img);
    };
    img.onerror = (err) => {
      console.warn('[SpriteLoader] Failed to load sprite sheet:', err);
      loadPromise = null; // Allow retry
      reject(err);
    };
    img.src = SPRITESHEET_PATH;
  });

  return loadPromise;
}

/**
 * Returns true if the sprite sheet has finished loading.
 */
export function isSpriteSheetLoaded() {
  return loaded;
}

/**
 * Check if we have a sprite for a given class_id or enemy_type.
 */
export function hasSprite(classId, enemyType) {
  if (enemyType && SPRITE_MAP[enemyType]) return true;
  if (classId && SPRITE_MAP[classId]) return true;
  return false;
}

/**
 * Draw a sprite from the sprite sheet onto the canvas.
 *
 * @param {CanvasRenderingContext2D} ctx - Canvas context
 * @param {string} key - The SPRITE_MAP key (class_id or enemy_type)
 * @param {number} destX - Destination X (top-left pixel)
 * @param {number} destY - Destination Y (top-left pixel)
 * @param {number} destW - Destination width in pixels
 * @param {number} destH - Destination height in pixels
 */
export function drawSprite(ctx, key, destX, destY, destW, destH) {
  if (!loaded || !spriteImage) return false;

  const region = SPRITE_MAP[key];
  if (!region) return false;

  ctx.drawImage(
    spriteImage,
    region.x, region.y, region.w, region.h,  // source rect
    destX, destY, destW, destH                // destination rect
  );
  return true;
}

/**
 * Get the sprite key for a unit. Enemy type takes priority over class.
 * Supports hero sprite variants (e.g. crusader_2 for variant 2).
 * @param {string} classId - Hero class ID
 * @param {string} enemyType - Enemy type (takes priority)
 * @param {number} [spriteVariant=1] - Hero sprite variant (1, 2, or 3)
 * Returns null if no sprite is available.
 */
export function getSpriteKey(classId, enemyType, spriteVariant) {
  if (enemyType) {
    // Try variant-specific key for enemy type (e.g. demon_2, wraith_3)
    if (spriteVariant && spriteVariant > 1) {
      const variantKey = `${enemyType}_${spriteVariant}`;
      if (SPRITE_MAP[variantKey]) return variantKey;
    }
    // Fall back to base enemy key (variant 1)
    if (SPRITE_MAP[enemyType]) return enemyType;
  }
  if (classId) {
    // Try variant-specific key (e.g. crusader_2, crusader_3)
    if (spriteVariant && spriteVariant > 1) {
      const variantKey = `${classId}_${spriteVariant}`;
      if (SPRITE_MAP[variantKey]) return variantKey;
    }
    // Fall back to base key (variant 1)
    if (SPRITE_MAP[classId]) return classId;
  }
  return null;
}

/**
 * Get the sprite region data for a class + variant (for use in CSS backgrounds).
 * Returns { x, y, w, h } or null if not found.
 */
export function getSpriteRegion(classId, spriteVariant = 1) {
  if (spriteVariant > 1) {
    const variantKey = `${classId}_${spriteVariant}`;
    if (SPRITE_MAP[variantKey]) return SPRITE_MAP[variantKey];
  }
  return SPRITE_MAP[classId] || null;
}

/**
 * Sheet dimensions for CSS background-size calculations.
 */
export const SPRITESHEET_WIDTH = 4096;
export const SPRITESHEET_HEIGHT = 3072;
export const SPRITE_CELL_SIZE = 270;
